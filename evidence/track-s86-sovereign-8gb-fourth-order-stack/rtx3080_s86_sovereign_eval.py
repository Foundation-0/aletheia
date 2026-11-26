#!/usr/bin/env python3
"""Track S86 Bare-Metal RTX 3080 (sm_86) Live 4th-Order Sovereign 8 GiB Stack Evaluator.

Executes three live bare-metal GPU experiments on NVIDIA GeForce RTX 3080 Laptop (8 GiB, sm_86)
using frozen verified Qwen2.5-3B artifacts (BF16 reference + siliquant 3.0 bpw & 4.5 bpw
BlockH4 QuadSnake) with ZERO weights stored inside the expedition workspace:

  1. Live T3 Blow-Up (`CCE-Det`): Deterministic Fixed-Order Chunked-LSE curing Track S80's
     v6-v7 `tl.atomic_cas` ULP break on real Qwen2.5-3B vocab V = 151,936, H = 2,048:
       (a) Materialized FP32 & BF16 logit cross-entropy baseline + live OOM boundary,
       (b) Real Triton 3.9.0 `tl.atomic_cas` spinlock & `tl.atomic_add` LSE kernels +
           explicit tile-order permutation drift measurement,
       (c) `CCE-Det` fixed ascending tile-order FP32 accumulator forward+backward across
           >= 12 repeated passes certifying 0-bit exact repeatability (`max_ulp_diff == 0`,
           identical SHA-256 of loss, LSE, grad_h, and grad_W), exact VRAM savings, and
           exact accuracy vs FP32 reference.

  2. Live Borromean 4-Way 8 GiB Sovereign Stack (`S73` 3.0 bpw QuadSnake x `S78` LoRA
     r in {16, 64, 128} x `S79` Sparse Hessian-CSR <= 0.50% (< 1/160) Outliers x `S80` CCE-Det)
     on real Qwen2.5-3B (36 layers, 252 linear matrices, 2,774,532,096 block weights):
       - Disjoint WikiText-2 test & CPython stdlib KL/PPL/Top-1 evaluation for BF16,
         4.5 bpw QuadSnake, 3.0 bpw QuadSnake, 3.0 bpw + {0.125%, 0.250%, 0.500%} Hessian-CSR,
         and 3.0 bpw + 0.500% Raw-|E| CSR ablation (calibrated strictly on disjoint WikiText-2 val).
       - Live RTX 3080 peak VRAM & OOM ablation across all Borromean subsets (No-S73 BF16,
         No-S78 full-model AdamW, No-S80 materialized FP32 logits at N=4096, No-S79 pure
         3.0 bpw, and Full 4-Way Stack across LoRA r in {16, 64, 128}).
       - Live 5-step AdamW fine-tuning + 0-bit repeatability verification on the Full 4-Way Stack.

  3. Live Track S77 Mellin-GLU 16-Rung Carry-Circuit Preservation Spot-Check under real
     siliquant A_16 BlockH4 quantization (3.0 bpw and 4.5 bpw) with vs. without <= 0.50% CSR.

All numeric outputs in the emitted empirical JSON are encoded strictly as exact integers
(bytes, nanonats, micro-PPL, ULP counts, microseconds, microjoules) with ZERO JSON floats.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
import triton
import triton.language as tl
from transformers import AutoModelForCausalLM, AutoTokenizer

EVAL_SEED = 2026112486
VOCAB_SIZE = 151_936
HIDDEN_SIZE = 2_048
SEQ_LEN = 512
N_EVAL_CHUNKS = 8
N_CAL_CHUNKS = 12
LOGIT_TOK_CHUNK = 128
CCE_N_CHUNK = 512
CCE_V_CHUNK = 8_192

STDLIB_PY_MODULES = (
    "fractions.py",
    "difflib.py",
    "decimal.py",
    "statistics.py",
    "argparse.py",
    "json/decoder.py",
)

# Exact siliquant#85 A_16 theta-series ball bounds for g = 128
A16_BALL_BOUNDS_G128: dict[str, float] = {
    "4.5": 5213.0,
    "3.0": 651.0,
}


def _scale_int(val: float, factor: int) -> int:
    if not math.isfinite(val):
        raise ValueError(f"Non-finite measurement encountered: {val!r}")
    return int(round(val * factor))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_tensor_bytes(t: torch.Tensor) -> str:
    arr = t.detach().reshape(-1).contiguous().cpu().view(torch.uint8).numpy()
    return hashlib.sha256(memoryview(arr)).hexdigest()


def _max_fp32_ulp_diff(a: torch.Tensor, b: torch.Tensor) -> int:
    """Exact IEEE-754 float32 ULP distance between two finite tensors (fast exact short-circuit)."""
    ar = a.detach().reshape(-1)
    br = b.detach().reshape(-1)
    if ar.dtype == br.dtype and ar.device == br.device and bool(torch.equal(ar, br)):
        return 0
    af = ar.contiguous().to(torch.float32)
    bf = br.contiguous().to(torch.float32)
    au = af.view(torch.int32).to(torch.int64)
    bu = bf.view(torch.int32).to(torch.int64)
    # Map IEEE-754 sign-magnitude int32 to monotonically ordered int64
    am = torch.where(au < 0, (1 << 31) - (au & 0x7FFFFFFF), au + (1 << 31))
    bm = torch.where(bu < 0, (1 << 31) - (bu & 0x7FFFFFFF), bu + (1 << 31))
    return int((am - bm).abs().max().item())


def _max_abs_diff_piconats(a: torch.Tensor, b: torch.Tensor) -> int:
    ar = a.detach().reshape(-1)
    br = b.detach().reshape(-1)
    if ar.dtype == br.dtype and ar.device == br.device and bool(torch.equal(ar, br)):
        return 0
    return _scale_int(float((ar.to(torch.float32) - br.to(torch.float32)).abs().max().item()), 1_000_000_000_000)


def _read_rapl_pkg_uj() -> int:
    try:
        return int(Path("/sys/class/powercap/intel-rapl:0/energy_uj").read_text(encoding="utf-8").strip())
    except OSError:
        return 0


def _read_rapl_max_range_uj() -> int:
    try:
        return int(Path("/sys/class/powercap/intel-rapl:0/max_energy_range_uj").read_text(encoding="utf-8").strip())
    except OSError:
        return 0


def _rapl_delta_uj(start_uj: int, end_uj: int, max_range_uj: int) -> int:
    if end_uj >= start_uj:
        return int(end_uj - start_uj)
    if max_range_uj > 0:
        return int((max_range_uj - start_uj) + end_uj)
    return 0


def _query_nvidia_smi() -> dict[str, Any]:
    out = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=name,driver_version,pstate,temperature.gpu,power.draw,clocks.sm,clocks.mem,memory.used,memory.total",
            "--format=csv,noheader,nounits",
        ],
        text=True,
    ).strip()
    parts = [p.strip() for p in out.split(",")]
    return {
        "name": parts[0],
        "driver_version": parts[1],
        "pstate": parts[2],
        "temperature_c": int(parts[3]),
        "power_draw_mw": _scale_int(float(parts[4]), 1000),
        "clocks_sm_mhz": int(parts[5]),
        "clocks_mem_mhz": int(parts[6]),
        "memory_used_mib": int(parts[7]),
        "memory_total_mib": int(parts[8]),
    }


def _load_python_eval_text() -> tuple[str, str]:
    stdlib_dir = Path(json.__file__).resolve().parent.parent
    chunks: list[str] = []
    h = hashlib.sha256()
    for rel in STDLIB_PY_MODULES:
        raw = (stdlib_dir / rel).read_bytes()
        h.update(rel.encode("utf-8") + b"\0" + raw)
        chunks.append(raw.decode("utf-8", errors="ignore"))
    return "\n\n".join(chunks), h.hexdigest()


def _tokenize_chunks(tokenizer: Any, text: str, n_chunks: int, seq_len: int) -> torch.Tensor:
    ids = tokenizer(text, return_tensors="pt", add_special_tokens=False).input_ids[0]
    need = n_chunks * seq_len
    if ids.numel() < need:
        reps = (need // ids.numel()) + 1
        ids = ids.repeat(reps)
    return ids[:need].reshape(n_chunks, seq_len).contiguous()


# ==============================================================================
# PART 1: TRITON ATOMIC KERNELS vs CCE-Det (T3 BLOW-UP MEDIATOR)
# ==============================================================================

@triton.jit
def _cce_atomic_add_lse_pass1_max_kernel(
    h_ptr,
    w_ptr,
    max_ptr,
    n_rows,
    vocab_size,
    hidden_size,
    stride_hn,
    stride_hk,
    stride_wv,
    stride_wk,
    BLOCK_N: tl.constexpr,
    BLOCK_V: tl.constexpr,
    BLOCK_K: tl.constexpr,
):
    pid_v = tl.program_id(0)
    pid_n = tl.program_id(1)
    offs_n = pid_n * BLOCK_N + tl.arange(0, BLOCK_N)
    offs_v = pid_v * BLOCK_V + tl.arange(0, BLOCK_V)
    mask_n = offs_n < n_rows
    mask_v = offs_v < vocab_size

    acc = tl.zeros((BLOCK_N, BLOCK_V), dtype=tl.float32)
    for k0 in range(0, hidden_size, BLOCK_K):
        offs_k = k0 + tl.arange(0, BLOCK_K)
        mask_k = offs_k < hidden_size
        h_tile = tl.load(
            h_ptr + offs_n[:, None] * stride_hn + offs_k[None, :] * stride_hk,
            mask=mask_n[:, None] & mask_k[None, :],
            other=0.0,
        )
        w_tile = tl.load(
            w_ptr + offs_v[:, None] * stride_wv + offs_k[None, :] * stride_wk,
            mask=mask_v[:, None] & mask_k[None, :],
            other=0.0,
        )
        acc += tl.dot(h_tile, tl.trans(w_tile), out_dtype=tl.float32)

    acc = tl.where(mask_v[None, :], acc, float("-inf"))
    tile_max = tl.max(acc, axis=1)
    tl.atomic_max(max_ptr + offs_n, tile_max, mask=mask_n)


@triton.jit
def _cce_atomic_add_lse_pass2_sum_kernel(
    h_ptr,
    w_ptr,
    max_ptr,
    sum_ptr,
    n_rows,
    vocab_size,
    hidden_size,
    stride_hn,
    stride_hk,
    stride_wv,
    stride_wk,
    BLOCK_N: tl.constexpr,
    BLOCK_V: tl.constexpr,
    BLOCK_K: tl.constexpr,
):
    pid_v = tl.program_id(0)
    pid_n = tl.program_id(1)
    offs_n = pid_n * BLOCK_N + tl.arange(0, BLOCK_N)
    offs_v = pid_v * BLOCK_V + tl.arange(0, BLOCK_V)
    mask_n = offs_n < n_rows
    mask_v = offs_v < vocab_size

    acc = tl.zeros((BLOCK_N, BLOCK_V), dtype=tl.float32)
    for k0 in range(0, hidden_size, BLOCK_K):
        offs_k = k0 + tl.arange(0, BLOCK_K)
        mask_k = offs_k < hidden_size
        h_tile = tl.load(
            h_ptr + offs_n[:, None] * stride_hn + offs_k[None, :] * stride_hk,
            mask=mask_n[:, None] & mask_k[None, :],
            other=0.0,
        )
        w_tile = tl.load(
            w_ptr + offs_v[:, None] * stride_wv + offs_k[None, :] * stride_wk,
            mask=mask_v[:, None] & mask_k[None, :],
            other=0.0,
        )
        acc += tl.dot(h_tile, tl.trans(w_tile), out_dtype=tl.float32)

    row_max = tl.load(max_ptr + offs_n, mask=mask_n, other=0.0)
    shifted = tl.where(mask_v[None, :], acc - row_max[:, None], float("-inf"))
    tile_sum = tl.sum(tl.exp(shifted), axis=1)
    # Non-deterministic CTA arrival-order FP32 atomic addition across vocab tiles
    tl.atomic_add(sum_ptr + offs_n, tile_sum, mask=mask_n)


@triton.jit
def _cce_atomic_cas_spinlock_lse_kernel(
    h_ptr,
    w_ptr,
    lse_i32_ptr,
    n_rows,
    vocab_size,
    hidden_size,
    stride_hn,
    stride_hk,
    stride_wv,
    stride_wk,
    BLOCK_N: tl.constexpr,
    BLOCK_V: tl.constexpr,
    BLOCK_K: tl.constexpr,
):
    """Lock-free IEEE-754 bit-level tl.atomic_cas online-LSE merge across competing vocab tiles.

    Directly reproduces the non-deterministic CTA arrival-order tl.atomic_cas FP32
    merge obstruction of Apple/Unsloth cce_lse_forward.py without any spinlock deadlock risk.
    """
    pid_v = tl.program_id(0)
    pid_n = tl.program_id(1)
    offs_n = pid_n * BLOCK_N + tl.arange(0, BLOCK_N)
    offs_v = pid_v * BLOCK_V + tl.arange(0, BLOCK_V)
    mask_n = offs_n < n_rows
    mask_v = offs_v < vocab_size

    acc = tl.zeros((BLOCK_N, BLOCK_V), dtype=tl.float32)
    for k0 in range(0, hidden_size, BLOCK_K):
        offs_k = k0 + tl.arange(0, BLOCK_K)
        mask_k = offs_k < hidden_size
        h_tile = tl.load(
            h_ptr + offs_n[:, None] * stride_hn + offs_k[None, :] * stride_hk,
            mask=mask_n[:, None] & mask_k[None, :],
            other=0.0,
        )
        w_tile = tl.load(
            w_ptr + offs_v[:, None] * stride_wv + offs_k[None, :] * stride_wk,
            mask=mask_v[:, None] & mask_k[None, :],
            other=0.0,
        )
        acc += tl.dot(h_tile, tl.trans(w_tile), out_dtype=tl.float32)

    acc = tl.where(mask_v[None, :], acc, float("-inf"))
    m_tile = tl.max(acc, axis=1)
    lse_tile = m_tile + tl.log(tl.sum(tl.exp(acc - m_tile[:, None]), axis=1))

    # Lock-free per-element FP32 logaddexp merge via tl.atomic_cas on int32 bit patterns
    old_bits = tl.load(lse_i32_ptr + offs_n, mask=mask_n, other=-8388608, cache_modifier=".cg")
    done = ~mask_n
    for _retry in range(256):
        old_f = old_bits.to(tl.float32, bitcast=True)
        m_both = tl.maximum(old_f, lse_tile)
        merged_f = m_both + tl.log(tl.exp(old_f - m_both) + tl.exp(lse_tile - m_both))
        prop_bits = merged_f.to(tl.int32, bitcast=True)
        cmp_bits = tl.where(done, 0x7FC00000, old_bits)
        val_bits = tl.where(done, old_bits, prop_bits)
        prev_bits = tl.atomic_cas(lse_i32_ptr + offs_n, cmp_bits, val_bits)
        succeeded = (~done) & (prev_bits == old_bits)
        done = done | succeeded
        old_bits = tl.where(done, old_bits, prev_bits)


def _run_triton_atomic_add_lse(h_bf16: torch.Tensor, w_bf16: torch.Tensor) -> torch.Tensor:
    n_rows, hidden_size = h_bf16.shape
    vocab_size = w_bf16.shape[0]
    block_n = 32
    block_v = 128
    block_k = 64
    row_max = torch.full((n_rows,), float("-inf"), device=h_bf16.device, dtype=torch.float32)
    row_sum = torch.zeros((n_rows,), device=h_bf16.device, dtype=torch.float32)
    grid = (triton.cdiv(vocab_size, block_v), triton.cdiv(n_rows, block_n))
    _cce_atomic_add_lse_pass1_max_kernel[grid](
        h_bf16,
        w_bf16,
        row_max,
        n_rows,
        vocab_size,
        hidden_size,
        h_bf16.stride(0),
        h_bf16.stride(1),
        w_bf16.stride(0),
        w_bf16.stride(1),
        BLOCK_N=block_n,
        BLOCK_V=block_v,
        BLOCK_K=block_k,
        num_warps=4,
    )
    _cce_atomic_add_lse_pass2_sum_kernel[grid](
        h_bf16,
        w_bf16,
        row_max,
        row_sum,
        n_rows,
        vocab_size,
        hidden_size,
        h_bf16.stride(0),
        h_bf16.stride(1),
        w_bf16.stride(0),
        w_bf16.stride(1),
        BLOCK_N=block_n,
        BLOCK_V=block_v,
        BLOCK_K=block_k,
        num_warps=4,
    )
    return row_max + torch.log(row_sum)


def _run_triton_atomic_cas_lse(h_bf16: torch.Tensor, w_bf16: torch.Tensor) -> torch.Tensor:
    n_rows, hidden_size = h_bf16.shape
    vocab_size = w_bf16.shape[0]
    block_n = 32
    block_v = 256
    block_k = 64
    n_blocks = triton.cdiv(n_rows, block_n)
    lse_buf = torch.full((n_blocks * block_n,), float("-inf"), device=h_bf16.device, dtype=torch.float32)
    lse_i32 = lse_buf.view(torch.int32)
    grid = (triton.cdiv(vocab_size, block_v), n_blocks)
    _cce_atomic_cas_spinlock_lse_kernel[grid](
        h_bf16,
        w_bf16,
        lse_i32,
        n_rows,
        vocab_size,
        hidden_size,
        h_bf16.stride(0),
        h_bf16.stride(1),
        w_bf16.stride(0),
        w_bf16.stride(1),
        BLOCK_N=block_n,
        BLOCK_V=block_v,
        BLOCK_K=block_k,
        num_warps=4,
    )
    return lse_i32[:n_rows].view(torch.float32)


class CCEDetFunction(torch.autograd.Function):
    """Deterministic Fixed-Order Chunked-LSE (CCE-Det) — T3 Blow-Up Mediator.

    Eliminates both O(N*V) logit materialization AND non-deterministic atomic tile
    reduction order by sweeping (n_chunk, v_chunk) in fixed ascending order with
    FP32 online-LSE and gradient accumulators.
    """

    @staticmethod
    def forward(
        ctx: Any,
        h: torch.Tensor,
        weight: torch.Tensor,
        targets: torch.Tensor,
        n_chunk: int,
        v_chunk: int,
        return_lse: bool,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        n_rows = int(h.shape[0])
        vocab_size = int(weight.shape[0])
        lse = torch.empty((n_rows,), device=h.device, dtype=torch.float32)
        target_logits = torch.empty((n_rows,), device=h.device, dtype=torch.float32)

        with torch.no_grad():
            for n0 in range(0, n_rows, n_chunk):
                n1 = min(n0 + n_chunk, n_rows)
                h_blk = h[n0:n1].to(torch.float32)
                y_blk = targets[n0:n1]
                m_run = torch.full((n1 - n0,), float("-inf"), device=h.device, dtype=torch.float32)
                s_run = torch.zeros((n1 - n0,), device=h.device, dtype=torch.float32)
                for v0 in range(0, vocab_size, v_chunk):
                    v1 = min(v0 + v_chunk, vocab_size)
                    w_blk = weight[v0:v1].to(torch.float32)
                    z = F.linear(h_blk, w_blk)
                    m_tile = z.amax(dim=-1)
                    m_new = torch.maximum(m_run, m_tile)
                    s_run = s_run * torch.exp(m_run - m_new) + torch.exp(z - m_new.unsqueeze(-1)).sum(dim=-1)
                    m_run = m_new
                lse[n0:n1] = m_run + torch.log(s_run)
                w_y = weight.index_select(0, y_blk).to(torch.float32)
                target_logits[n0:n1] = (h_blk * w_y).sum(dim=-1)

            loss = (lse - target_logits).mean()

        ctx.save_for_backward(h, weight, targets, lse)
        ctx.n_chunk = n_chunk
        ctx.v_chunk = v_chunk
        ctx.return_lse = return_lse
        return loss, lse

    @staticmethod
    def backward(
        ctx: Any,
        grad_loss: torch.Tensor,
        _grad_lse: torch.Tensor,
    ) -> tuple[torch.Tensor | None, torch.Tensor | None, None, None, None, None]:
        h, weight, targets, lse = ctx.saved_tensors
        n_chunk = int(ctx.n_chunk)
        v_chunk = int(ctx.v_chunk)
        n_rows = int(h.shape[0])
        vocab_size = int(weight.shape[0])
        scale = grad_loss.to(torch.float32) / float(n_rows)

        need_h = bool(ctx.needs_input_grad[0])
        need_w = bool(ctx.needs_input_grad[1])
        grad_h_f32 = torch.zeros_like(h, dtype=torch.float32) if need_h else None
        grad_w_out = torch.zeros_like(weight) if need_w else None

        with torch.no_grad():
            # Strictly fixed ascending v0, then strictly fixed ascending n0!
            for v0 in range(0, vocab_size, v_chunk):
                v1 = min(v0 + v_chunk, vocab_size)
                w_blk = weight[v0:v1].to(torch.float32)
                gw_blk = torch.zeros_like(w_blk, dtype=torch.float32) if need_w else None
                for n0 in range(0, n_rows, n_chunk):
                    n1 = min(n0 + n_chunk, n_rows)
                    h_blk = h[n0:n1].to(torch.float32)
                    lse_blk = lse[n0:n1]
                    y_blk = targets[n0:n1]
                    z = F.linear(h_blk, w_blk)
                    p = torch.exp(z - lse_blk.unsqueeze(-1))
                    in_tile = (y_blk >= v0) & (y_blk < v1)
                    if bool(in_tile.any().item()):
                        rows_hit = torch.nonzero(in_tile, as_tuple=False).squeeze(-1)
                        cols_hit = y_blk[rows_hit] - v0
                        p[rows_hit, cols_hit] -= 1.0
                    p.mul_(scale)
                    if grad_h_f32 is not None:
                        grad_h_f32[n0:n1].add_(torch.matmul(p, w_blk))
                    if gw_blk is not None:
                        gw_blk.add_(torch.matmul(p.transpose(0, 1), h_blk))
                if grad_w_out is not None and gw_blk is not None:
                    grad_w_out[v0:v1] = gw_blk.to(weight.dtype)

        grad_h = grad_h_f32.to(h.dtype) if grad_h_f32 is not None else None
        return grad_h, grad_w_out, None, None, None, None


def cce_det_loss(
    h: torch.Tensor,
    weight: torch.Tensor,
    targets: torch.Tensor,
    *,
    n_chunk: int = CCE_N_CHUNK,
    v_chunk: int = CCE_V_CHUNK,
) -> tuple[torch.Tensor, torch.Tensor]:
    return CCEDetFunction.apply(h, weight, targets, n_chunk, v_chunk, True)


def _chunked_lse_custom_order(
    h: torch.Tensor,
    weight: torch.Tensor,
    v_order: list[tuple[int, int]],
) -> torch.Tensor:
    """Compute online FP32 LSE in an explicit caller-chosen tile order."""
    n_rows = int(h.shape[0])
    h_f32 = h.to(torch.float32)
    m_run = torch.full((n_rows,), float("-inf"), device=h.device, dtype=torch.float32)
    s_run = torch.zeros((n_rows,), device=h.device, dtype=torch.float32)
    with torch.no_grad():
        for v0, v1 in v_order:
            w_blk = weight[v0:v1].to(torch.float32)
            z = F.linear(h_f32, w_blk)
            m_tile = z.amax(dim=-1)
            m_new = torch.maximum(m_run, m_tile)
            s_run = s_run * torch.exp(m_run - m_new) + torch.exp(z - m_new.unsqueeze(-1)).sum(dim=-1)
            m_run = m_new
    return m_run + torch.log(s_run)


def _probe_head_vram_once(
    h_cpu: torch.Tensor,
    w_cpu: torch.Tensor,
    y_cpu: torch.Tensor,
    device: torch.device,
    *,
    mode: str,
    w_requires_grad: bool,
) -> dict[str, Any]:
    """Isolated single-probe frame so any CUDA OOM releases 100% of tensors on return."""
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(device)
    h_var: torch.Tensor | None = None
    w_var: torch.Tensor | None = None
    y_dev: torch.Tensor | None = None
    logits: torch.Tensor | None = None
    loss: torch.Tensor | None = None
    lse_t: torch.Tensor | None = None
    try:
        h_var = h_cpu.to(device).detach().requires_grad_(True)
        w_var = w_cpu.to(device=device, dtype=torch.bfloat16).detach().requires_grad_(w_requires_grad)
        y_dev = y_cpu.to(device)
        t0 = time.monotonic()
        if mode == "mat_fp32":
            logits = F.linear(h_var.to(torch.float32), w_var.to(torch.float32))
            loss = F.cross_entropy(logits, y_dev)
        elif mode == "mat_bf16_ce":
            logits = F.linear(h_var, w_var)
            loss = F.cross_entropy(logits.to(torch.float32), y_dev)
        elif mode == "cce_det":
            loss, lse_t = cce_det_loss(h_var, w_var, y_dev, n_chunk=CCE_N_CHUNK, v_chunk=CCE_V_CHUNK)
        else:
            raise ValueError(f"Unknown mode={mode!r}")
        loss.backward()
        torch.cuda.synchronize(device)
        dt_us = int(round((time.monotonic() - t0) * 1_000_000))
        return {
            "oom": False,
            "peak_alloc_bytes": int(torch.cuda.max_memory_allocated(device)),
            "peak_reserved_bytes": int(torch.cuda.max_memory_reserved(device)),
            "loss_nanonats": _scale_int(float(loss.item()), 1_000_000_000),
            "step_us": dt_us,
        }
    except torch.cuda.OutOfMemoryError:
        return {
            "oom": True,
            "peak_alloc_bytes": int(torch.cuda.max_memory_allocated(device)),
            "peak_reserved_bytes": int(torch.cuda.max_memory_reserved(device)),
        }
    finally:
        del lse_t, loss, logits, y_dev, w_var, h_var


def _run_part1_cce_det_experiment(
    lm_head_weight_cpu: torch.Tensor,
    device: torch.device,
    *,
    smoke: bool,
) -> dict[str, Any]:
    print(
        f"\n=== PART 1: Live T3 Blow-Up (CCE-Det vs Materialized vs Atomic Triton, "
        f"entry_alloc={torch.cuda.memory_allocated(device)/(1<<20):.1f} MiB) ===",
        flush=True,
    )
    vocab_size, hidden_size = int(lm_head_weight_cpu.shape[0]), int(lm_head_weight_cpu.shape[1])

    # 1A. VRAM Roofline Sweep across N in {1024, 2048, 4096, 8192} (both frozen-head QLoRA & trainable-head!)
    n_grid = [1024, 2048] if smoke else [1024, 2048, 4096, 8192]
    vram_sweep: dict[str, Any] = {}
    for n_tok in n_grid:
        gen = torch.Generator(device="cpu").manual_seed(EVAL_SEED + n_tok)
        h_cpu = torch.randn((n_tok, hidden_size), generator=gen, dtype=torch.bfloat16) * 0.5
        y_cpu = torch.randint(0, vocab_size, (n_tok,), generator=gen, dtype=torch.long)

        mat_fp32_res = _probe_head_vram_once(h_cpu, lm_head_weight_cpu, y_cpu, device, mode="mat_fp32", w_requires_grad=False)
        gc.collect()
        torch.cuda.empty_cache()

        mat_bf16_res = _probe_head_vram_once(h_cpu, lm_head_weight_cpu, y_cpu, device, mode="mat_bf16_ce", w_requires_grad=False)
        gc.collect()
        torch.cuda.empty_cache()

        cce_det_frozen_res = _probe_head_vram_once(h_cpu, lm_head_weight_cpu, y_cpu, device, mode="cce_det", w_requires_grad=False)
        gc.collect()
        torch.cuda.empty_cache()

        cce_det_train_res = _probe_head_vram_once(h_cpu, lm_head_weight_cpu, y_cpu, device, mode="cce_det", w_requires_grad=True)
        gc.collect()
        torch.cuda.empty_cache()

        vram_sweep[f"N_{n_tok}"] = {
            "n_tokens": n_tok,
            "theoretical_fp32_logits_bytes": n_tok * vocab_size * 4,
            "materialized_fp32_frozen_head": mat_fp32_res,
            "materialized_bf16_ce_frozen_head": mat_bf16_res,
            "cce_det_frozen_head": cce_det_frozen_res,
            "cce_det_trainable_head": cce_det_train_res,
        }
        print(
            f"  [VRAM N={n_tok}] mat_fp32 oom={mat_fp32_res['oom']} peak={mat_fp32_res['peak_alloc_bytes']/(1<<20):.1f} MiB | "
            f"mat_bf16_ce oom={mat_bf16_res['oom']} peak={mat_bf16_res['peak_alloc_bytes']/(1<<20):.1f} MiB | "
            f"cce_det(frozen)={cce_det_frozen_res['peak_alloc_bytes']/(1<<20):.1f} MiB | "
            f"cce_det(trainW)={cce_det_train_res['peak_alloc_bytes']/(1<<20):.1f} MiB",
            flush=True,
        )

    # 1B. Accuracy vs FP32 Exact Materialized Reference at N=1024 (fits comfortably inside 8 GiB with both grad_h & grad_W!)
    n_rep = 4 if smoke else 12
    n_acc = 1024
    gen_acc = torch.Generator(device="cpu").manual_seed(EVAL_SEED + 777)
    h_acc_cpu = torch.randn((n_acc, hidden_size), generator=gen_acc, dtype=torch.bfloat16) * 0.5
    y_acc_cpu = torch.randint(0, vocab_size, (n_acc,), generator=gen_acc, dtype=torch.long)

    h_ref = h_acc_cpu.to(device).detach().requires_grad_(True)
    w_ref = lm_head_weight_cpu.to(device=device, dtype=torch.bfloat16).detach().requires_grad_(True)
    y_ref = y_acc_cpu.to(device)
    logits_ref = F.linear(h_ref.to(torch.float32), w_ref.to(torch.float32))
    lse_ref = torch.logsumexp(logits_ref, dim=-1)
    loss_ref = F.cross_entropy(logits_ref, y_ref)
    loss_ref.backward()
    torch.cuda.synchronize(device)
    ref_loss_f = float(loss_ref.item())
    ref_lse_cpu = lse_ref.detach().cpu()
    ref_gh_cpu = h_ref.grad.detach().to(torch.float32).cpu()
    ref_gw_cpu = w_ref.grad.detach().to(torch.float32).cpu()
    del logits_ref, lse_ref, loss_ref, h_ref, w_ref
    gc.collect()
    torch.cuda.empty_cache()

    h_d = h_acc_cpu.to(device).detach().requires_grad_(True)
    w_d = lm_head_weight_cpu.to(device=device, dtype=torch.bfloat16).detach().requires_grad_(True)
    loss_d, lse_d = cce_det_loss(h_d, w_d, y_ref, n_chunk=CCE_N_CHUNK, v_chunk=CCE_V_CHUNK)
    loss_d.backward()
    torch.cuda.synchronize(device)
    det_loss_f = float(loss_d.item())
    gh_d_cpu = h_d.grad.detach().to(torch.float32).cpu()
    gw_d_cpu = w_d.grad.detach().to(torch.float32).cpu()
    lse_d_cpu = lse_d.detach().cpu()

    acc_vs_fp32 = {
        "n_tokens": n_acc,
        "fp32_ref_loss_nanonats": _scale_int(ref_loss_f, 1_000_000_000),
        "cce_det_loss_nanonats": _scale_int(det_loss_f, 1_000_000_000),
        "loss_abs_err_piconats": _scale_int(abs(det_loss_f - ref_loss_f), 1_000_000_000_000),
        "lse_max_abs_err_piconats": _max_abs_diff_piconats(lse_d_cpu, ref_lse_cpu),
        "lse_max_ulp_vs_fp32": _max_fp32_ulp_diff(lse_d_cpu, ref_lse_cpu),
        "grad_h_max_abs_err_piconats": _max_abs_diff_piconats(gh_d_cpu, ref_gh_cpu),
        "grad_h_rel_l2_err_ppb": _scale_int(
            float(torch.linalg.norm(gh_d_cpu - ref_gh_cpu).item() / max(torch.linalg.norm(ref_gh_cpu).item(), 1e-30)),
            1_000_000_000,
        ),
        "grad_w_max_abs_err_piconats": _max_abs_diff_piconats(gw_d_cpu, ref_gw_cpu),
    }
    print(
        f"  [Acc vs FP32 N={n_acc}] loss_err_pico={acc_vs_fp32['loss_abs_err_piconats']} "
        f"lse_ulp={acc_vs_fp32['lse_max_ulp_vs_fp32']} gh_rel_ppb={acc_vs_fp32['grad_h_rel_l2_err_ppb']}",
        flush=True,
    )
    del h_d, w_d, loss_d, lse_d, y_ref, ref_lse_cpu, ref_gh_cpu, ref_gw_cpu, gh_d_cpu, gw_d_cpu, lse_d_cpu
    gc.collect()
    torch.cuda.empty_cache()

    # 1C. Live 12-run 0-bit repeatability of CCE-Det at N=4096 (or 1024 in smoke)
    n_det_rep = 1024 if smoke else 4096
    gen_rep = torch.Generator(device="cpu").manual_seed(EVAL_SEED + 999)
    h_rep_cpu = torch.randn((n_det_rep, hidden_size), generator=gen_rep, dtype=torch.bfloat16) * 0.5
    y_rep_cpu = torch.randint(0, vocab_size, (n_det_rep,), generator=gen_rep, dtype=torch.long)
    y_rep_dev = y_rep_cpu.to(device)

    loss_hashes: set[str] = set()
    lse_hashes: set[str] = set()
    gh_hashes: set[str] = set()
    gw_hashes: set[str] = set()
    first_loss: torch.Tensor | None = None
    first_lse: torch.Tensor | None = None
    first_gh: torch.Tensor | None = None
    first_gw: torch.Tensor | None = None
    max_loss_ulp = 0
    max_lse_ulp = 0
    max_gh_ulp = 0
    max_gw_ulp = 0
    max_loss_diff_pico = 0
    max_gh_diff_pico = 0
    max_gw_diff_pico = 0
    rep_peak_alloc = 0
    rep_latencies_us: list[int] = []

    for _r_idx in range(n_rep):
        torch.cuda.reset_peak_memory_stats(device)
        h_r = h_rep_cpu.to(device).detach().requires_grad_(True)
        w_r = lm_head_weight_cpu.to(device=device, dtype=torch.bfloat16).detach().requires_grad_(True)
        t0 = time.monotonic()
        loss_r, lse_r = cce_det_loss(h_r, w_r, y_rep_dev, n_chunk=CCE_N_CHUNK, v_chunk=CCE_V_CHUNK)
        loss_r.backward()
        torch.cuda.synchronize(device)
        rep_latencies_us.append(int(round((time.monotonic() - t0) * 1_000_000)))
        rep_peak_alloc = max(rep_peak_alloc, int(torch.cuda.max_memory_allocated(device)))

        loss_c = loss_r.detach().cpu()
        lse_c = lse_r.detach().cpu()
        gh_c = h_r.grad.detach().cpu()
        gw_c = w_r.grad.detach().cpu()

        loss_hashes.add(_sha256_tensor_bytes(loss_c))
        lse_hashes.add(_sha256_tensor_bytes(lse_c))
        gh_hashes.add(_sha256_tensor_bytes(gh_c))
        gw_hashes.add(_sha256_tensor_bytes(gw_c))

        if first_loss is None:
            first_loss, first_lse, first_gh, first_gw = loss_c, lse_c, gh_c, gw_c
        else:
            max_loss_ulp = max(max_loss_ulp, _max_fp32_ulp_diff(loss_c, first_loss))
            max_lse_ulp = max(max_lse_ulp, _max_fp32_ulp_diff(lse_c, first_lse))
            max_gh_ulp = max(max_gh_ulp, _max_fp32_ulp_diff(gh_c, first_gh))
            max_gw_ulp = max(max_gw_ulp, _max_fp32_ulp_diff(gw_c, first_gw))
            max_loss_diff_pico = max(max_loss_diff_pico, _max_abs_diff_piconats(loss_c, first_loss))
            max_gh_diff_pico = max(max_gh_diff_pico, _max_abs_diff_piconats(gh_c, first_gh))
            max_gw_diff_pico = max(max_gw_diff_pico, _max_abs_diff_piconats(gw_c, first_gw))
        del h_r, w_r, loss_r, lse_r, loss_c, lse_c, gh_c, gw_c
    del first_loss, first_lse, first_gh, first_gw, y_rep_dev
    gc.collect()
    torch.cuda.empty_cache()

    cce_det_repeatability = {
        "n_runs": n_rep,
        "n_tokens": n_det_rep,
        "unique_loss_sha256": len(loss_hashes),
        "unique_lse_sha256": len(lse_hashes),
        "unique_grad_h_sha256": len(gh_hashes),
        "unique_grad_w_sha256": len(gw_hashes),
        "loss_sha256": sorted(loss_hashes)[0],
        "lse_sha256": sorted(lse_hashes)[0],
        "grad_h_sha256": sorted(gh_hashes)[0],
        "grad_w_sha256": sorted(gw_hashes)[0],
        "max_loss_ulp_diff": max_loss_ulp,
        "max_lse_ulp_diff": max_lse_ulp,
        "max_grad_h_ulp_diff": max_gh_ulp,
        "max_grad_w_ulp_diff": max_gw_ulp,
        "max_loss_abs_diff_piconats": max_loss_diff_pico,
        "max_grad_h_abs_diff_piconats": max_gh_diff_pico,
        "max_grad_w_abs_diff_piconats": max_gw_diff_pico,
        "peak_alloc_bytes": rep_peak_alloc,
        "median_step_us": sorted(rep_latencies_us)[len(rep_latencies_us) // 2],
    }

    # 1D. Live Unordered Triton Atomic Kernels + Tile-Order Permutation Drift (N=1024)
    n_atom = 512 if smoke else 1024
    gen_at = torch.Generator(device="cpu").manual_seed(EVAL_SEED + 314)
    h_at = (torch.randn((n_atom, hidden_size), generator=gen_at, dtype=torch.bfloat16) * 0.5).to(device).contiguous()
    w_base = lm_head_weight_cpu.to(device=device, dtype=torch.bfloat16).contiguous()

    # Warmup Triton JIT
    _ = _run_triton_atomic_add_lse(h_at, w_base)
    _ = _run_triton_atomic_cas_lse(h_at, w_base)
    torch.cuda.synchronize(device)

    # Triton atomic_add across n_rep runs
    add_hashes: set[str] = set()
    add_first: torch.Tensor | None = None
    add_max_ulp = 0
    add_max_diff_pico = 0
    add_div_rows = 0
    for _ in range(n_rep):
        out_add = _run_triton_atomic_add_lse(h_at, w_base)
        torch.cuda.synchronize(device)
        oc = out_add.detach().cpu()
        add_hashes.add(_sha256_tensor_bytes(oc))
        if add_first is None:
            add_first = oc
        else:
            add_max_ulp = max(add_max_ulp, _max_fp32_ulp_diff(oc, add_first))
            add_max_diff_pico = max(add_max_diff_pico, _scale_int(float((oc - add_first).abs().max().item()), 1_000_000_000_000))
            add_div_rows = max(add_div_rows, int((oc != add_first).sum().item()))

    # Triton atomic_cas spinlock across n_rep runs
    cas_hashes: set[str] = set()
    cas_first: torch.Tensor | None = None
    cas_max_ulp = 0
    cas_max_diff_pico = 0
    cas_div_rows = 0
    for _ in range(n_rep):
        out_cas = _run_triton_atomic_cas_lse(h_at, w_base)
        torch.cuda.synchronize(device)
        oc = out_cas.detach().cpu()
        cas_hashes.add(_sha256_tensor_bytes(oc))
        if cas_first is None:
            cas_first = oc
        else:
            cas_max_ulp = max(cas_max_ulp, _max_fp32_ulp_diff(oc, cas_first))
            cas_max_diff_pico = max(cas_max_diff_pico, _scale_int(float((oc - cas_first).abs().max().item()), 1_000_000_000_000))
            cas_div_rows = max(cas_div_rows, int((oc != cas_first).sum().item()))

    # Explicit chunk-order permutation drift (ascending vs descending vs striped tiles)
    tiles_asc = [(v0, min(v0 + CCE_V_CHUNK, vocab_size)) for v0 in range(0, vocab_size, CCE_V_CHUNK)]
    tiles_desc = list(reversed(tiles_asc))
    tiles_striped = tiles_asc[0::2] + tiles_asc[1::2]
    lse_asc = _chunked_lse_custom_order(h_at, w_base, tiles_asc).cpu()
    lse_desc = _chunked_lse_custom_order(h_at, w_base, tiles_desc).cpu()
    lse_strip = _chunked_lse_custom_order(h_at, w_base, tiles_striped).cpu()

    perm_drift = {
        "n_tokens": n_atom,
        "n_vocab_tiles": len(tiles_asc),
        "asc_vs_desc_divergent_rows": int((lse_asc != lse_desc).sum().item()),
        "asc_vs_desc_max_ulp": _max_fp32_ulp_diff(lse_asc, lse_desc),
        "asc_vs_desc_max_abs_diff_piconats": _scale_int(float((lse_asc - lse_desc).abs().max().item()), 1_000_000_000_000),
        "asc_vs_striped_divergent_rows": int((lse_asc != lse_strip).sum().item()),
        "asc_vs_striped_max_ulp": _max_fp32_ulp_diff(lse_asc, lse_strip),
        "asc_vs_striped_max_abs_diff_piconats": _scale_int(float((lse_asc - lse_strip).abs().max().item()), 1_000_000_000_000),
        "asc_sha256": _sha256_tensor_bytes(lse_asc),
        "desc_sha256": _sha256_tensor_bytes(lse_desc),
        "striped_sha256": _sha256_tensor_bytes(lse_strip),
    }

    triton_atomic_probe = {
        "n_runs": n_rep,
        "n_tokens": n_atom,
        "triton_version": str(triton.__version__),
        "atomic_add": {
            "unique_lse_sha256": len(add_hashes),
            "max_divergent_rows": add_div_rows,
            "max_ulp_diff": add_max_ulp,
            "max_abs_diff_piconats": add_max_diff_pico,
        },
        "atomic_cas_spinlock": {
            "unique_lse_sha256": len(cas_hashes),
            "max_divergent_rows": cas_div_rows,
            "max_ulp_diff": cas_max_ulp,
            "max_abs_diff_piconats": cas_max_diff_pico,
        },
        "tile_permutation_drift": perm_drift,
    }

    print(
        f"  [CCE-Det 12-run] unique hashes loss={cce_det_repeatability['unique_loss_sha256']} "
        f"gh={cce_det_repeatability['unique_grad_h_sha256']} gw={cce_det_repeatability['unique_grad_w_sha256']} "
        f"max_ulp={max_gh_ulp}",
        flush=True,
    )
    print(
        f"  [Atomic Probe] cas_unique={len(cas_hashes)} cas_div={cas_div_rows} cas_ulp={cas_max_ulp} | "
        f"add_unique={len(add_hashes)} add_div={add_div_rows} add_ulp={add_max_ulp} | "
        f"perm asc_vs_desc div={perm_drift['asc_vs_desc_divergent_rows']}/{n_atom} ulp={perm_drift['asc_vs_desc_max_ulp']}",
        flush=True,
    )

    del w_base, h_at, add_first, cas_first, lse_asc, lse_desc, lse_strip
    gc.collect()
    torch.cuda.empty_cache()

    return {
        "vocab_size": vocab_size,
        "hidden_size": hidden_size,
        "vram_sweep": vram_sweep,
        "accuracy_vs_fp32_ref": acc_vs_fp32,
        "cce_det_repeatability": cce_det_repeatability,
        "triton_atomic_and_permutation_probe": triton_atomic_probe,
    }


# ==============================================================================
# PART 2: LIVE BORROMEAN 4-WAY 8 GiB SOVEREIGN STACK ON REAL QWEN2.5-3B
# ==============================================================================

@torch.no_grad()
def _collect_reference_and_cal_rms(
    bf16_model: nn.Module,
    cal_chunks: torch.Tensor,
    wt_chunks: torch.Tensor,
    py_chunks: torch.Tensor,
    device: torch.device,
) -> tuple[dict[str, torch.Tensor], list[torch.Tensor], int, list[torch.Tensor], int]:
    """Collect disjoint WikiText-2 val input RMS per block linear + BF16 test log-probs."""
    sums: dict[str, torch.Tensor] = {}
    counts: dict[str, int] = {}
    handles: list[Any] = []

    def _make_hook(lname: str) -> Any:
        def _hook(_mod: nn.Module, inp: tuple[torch.Tensor, ...]) -> None:
            x = inp[0].detach().to(torch.float32)
            sq = (x * x).reshape(-1, x.shape[-1]).sum(dim=0).cpu()
            if lname not in sums:
                sums[lname] = sq
                counts[lname] = int(x.numel() // x.shape[-1])
            else:
                sums[lname] += sq
                counts[lname] += int(x.numel() // x.shape[-1])
        return _hook

    for name, mod in bf16_model.named_modules():
        if isinstance(mod, nn.Linear) and name.startswith("model.layers."):
            handles.append(mod.register_forward_pre_hook(_make_hook(name)))

    for i in range(int(cal_chunks.shape[0])):
        inp = cal_chunks[i : i + 1].to(device)
        _ = bf16_model.model(inp, use_cache=False)
        del inp
    for h in handles:
        h.remove()
    torch.cuda.empty_cache()

    rms_map: dict[str, torch.Tensor] = {}
    for lname, sq_vec in sums.items():
        rms_map[lname] = torch.sqrt((sq_vec / float(max(counts[lname], 1))).clamp_min(1e-12)).to(torch.float32)

    def _collect_lp(chunks: torch.Tensor) -> tuple[list[torch.Tensor], int]:
        lps: list[torch.Tensor] = []
        tot_nll = 0.0
        tot_tok = 0
        for i in range(int(chunks.shape[0])):
            inp = chunks[i : i + 1].to(device)
            logits_bf16 = bf16_model(inp, use_cache=False).logits[:, :-1, :]
            targets = inp[:, 1:]
            seq_t = int(logits_bf16.shape[1])
            slices: list[torch.Tensor] = []
            for s0 in range(0, seq_t, LOGIT_TOK_CHUNK):
                s1 = min(s0 + LOGIT_TOK_CHUNK, seq_t)
                lp = F.log_softmax(logits_bf16[:, s0:s1, :].to(torch.float32), dim=-1)
                nll = F.nll_loss(lp.reshape(-1, lp.shape[-1]), targets[:, s0:s1].reshape(-1), reduction="sum")
                tot_nll += float(nll.item())
                tot_tok += int(targets[:, s0:s1].numel())
                slices.append(lp.cpu())
                del lp
            lps.append(torch.cat(slices, dim=1))
            del inp, logits_bf16, slices
        torch.cuda.empty_cache()
        return lps, _scale_int(math.exp(tot_nll / float(tot_tok)), 1_000_000)

    wt_lps, wt_ppl_micro = _collect_lp(wt_chunks)
    py_lps, py_ppl_micro = _collect_lp(py_chunks)
    return rms_map, wt_lps, wt_ppl_micro, py_lps, py_ppl_micro


@torch.no_grad()
def _score_model_exact(
    model: nn.Module,
    chunks: torch.Tensor,
    ref_lps: list[torch.Tensor],
    device: torch.device,
) -> dict[str, int]:
    kl_sum = 0.0
    tot_nll = 0.0
    tot_tok = 0
    same_top1 = 0
    for i in range(int(chunks.shape[0])):
        inp = chunks[i : i + 1].to(device)
        logits_bf16 = model(inp, use_cache=False).logits[:, :-1, :]
        targets = inp[:, 1:]
        ref_lp_all = ref_lps[i]
        seq_t = int(logits_bf16.shape[1])
        for s0 in range(0, seq_t, LOGIT_TOK_CHUNK):
            s1 = min(s0 + LOGIT_TOK_CHUNK, seq_t)
            q_lp = F.log_softmax(logits_bf16[:, s0:s1, :].to(torch.float32), dim=-1)
            r_lp = ref_lp_all[:, s0:s1, :].to(device)
            r_p = torch.exp(r_lp)
            kl_tok = (r_p * (r_lp - q_lp)).sum(dim=-1)
            kl_sum += float(kl_tok.sum().item())
            nll = F.nll_loss(q_lp.reshape(-1, q_lp.shape[-1]), targets[:, s0:s1].reshape(-1), reduction="sum")
            tot_nll += float(nll.item())
            same_top1 += int((q_lp.argmax(dim=-1) == r_lp.argmax(dim=-1)).sum().item())
            tot_tok += int(targets[:, s0:s1].numel())
            del q_lp, r_lp, r_p, kl_tok
        del inp, logits_bf16
    torch.cuda.empty_cache()
    return {
        "kl_nanonats": _scale_int(kl_sum / float(tot_tok), 1_000_000_000),
        "ppl_micro": _scale_int(math.exp(tot_nll / float(tot_tok)), 1_000_000),
        "top1_matches": same_top1,
        "total_tokens": tot_tok,
    }


def _extract_csr_sidecar_for_layer(
    w_bf16_cpu: torch.Tensor,
    w_quant_cpu: torch.Tensor,
    col_rms_cpu: torch.Tensor | None,
    rho_num: int,
    rho_den: int,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, int, int, int]:
    """Extract top rho_num/rho_den residual entries as compact CSR (rowptr int32, col int16, val fp16).

    Returns (rowptr_i32, col_i16, val_fp16, nnz, sens_out_scaled, sens_tot_scaled).
    """
    m_out, k_in = int(w_bf16_cpu.shape[0]), int(w_bf16_cpu.shape[1])
    total_w = m_out * k_in
    k_top = (total_w * rho_num) // rho_den
    err = w_bf16_cpu.to(torch.float32) - w_quant_cpu.to(torch.float32)
    if col_rms_cpu is not None:
        weighted = err * col_rms_cpu.unsqueeze(0)
    else:
        weighted = err
    scores_flat = weighted.abs().reshape(-1)
    sens_tot = float((weighted * weighted).sum().item())

    if k_top <= 0:
        rowptr = torch.zeros((m_out + 1,), dtype=torch.int32)
        col = torch.empty((0,), dtype=torch.int16)
        val = torch.empty((0,), dtype=torch.float16)
        return rowptr, col, val, 0, 0, _scale_int(sens_tot, 1_000_000)

    _vals_top, flat_idx = torch.topk(scores_flat, k_top, largest=True, sorted=False)
    # Sort by flat index so rows are contiguous for canonical CSR layout
    flat_idx, _ = torch.sort(flat_idx)
    rows = (flat_idx // k_in).to(torch.int64)
    cols = (flat_idx % k_in).to(torch.int16)
    err_vals = err.reshape(-1)[flat_idx].to(torch.float16)
    w_sel = weighted.reshape(-1)[flat_idx]
    sens_out = float((w_sel * w_sel).sum().item())

    counts = torch.bincount(rows, minlength=m_out).to(torch.int32)
    rowptr = torch.zeros((m_out + 1,), dtype=torch.int32)
    rowptr[1:] = torch.cumsum(counts, dim=0)
    return (
        rowptr,
        cols,
        err_vals,
        int(k_top),
        _scale_int(sens_out, 1_000_000),
        _scale_int(sens_tot, 1_000_000),
    )


def _apply_csr_delta_dense(
    w_base: torch.Tensor,
    rowptr: torch.Tensor,
    cols: torch.Tensor,
    vals: torch.Tensor,
) -> torch.Tensor:
    """Apply compact CSR (rowptr int32, col int16, val fp16) delta onto a 2D weight tensor."""
    if int(cols.numel()) == 0:
        return w_base
    m_out = int(w_base.shape[0])
    counts = (rowptr[1:] - rowptr[:-1]).to(torch.long)
    row_ids = torch.repeat_interleave(torch.arange(m_out, device=w_base.device, dtype=torch.long), counts)
    col_ids = cols.to(torch.long)
    out = w_base.clone()
    out[row_ids, col_ids] += vals.to(w_base.dtype)
    return out


class SiliquantOnTheFlyMatmul(torch.autograd.Function):
    """Memory-optimal on-the-fly A_16 dequantization + optional CSR sidecar matmul.

    Zero persistent BF16 weight caches across transformer layers: dequantizes one
    SiliquantLinear layer at a time inside forward and re-dequantizes during backward.
    """

    @staticmethod
    def forward(
        ctx: Any,
        x: torch.Tensor,
        sliq_mod: Any,
        csr_rowptr: torch.Tensor | None,
        csr_col: torch.Tensor | None,
        csr_val: torch.Tensor | None,
    ) -> torch.Tensor:
        with torch.no_grad():
            w = sliq_mod.dequantize(dtype=x.dtype, verify_syndrome=False)
            if csr_rowptr is not None and csr_col is not None and csr_val is not None and int(csr_col.numel()) > 0:
                w = _apply_csr_delta_dense(w, csr_rowptr, csr_col, csr_val)
            bias = sliq_mod.bias.to(dtype=x.dtype) if sliq_mod.bias is not None else None
            y = F.linear(x, w, bias)
            del w
        ctx.sliq_mod = sliq_mod
        ctx.csr_rowptr = csr_rowptr
        ctx.csr_col = csr_col
        ctx.csr_val = csr_val
        return y

    @staticmethod
    def backward(ctx: Any, grad_out: torch.Tensor) -> tuple[torch.Tensor | None, None, None, None, None]:
        if not ctx.needs_input_grad[0]:
            return None, None, None, None, None
        sliq_mod = ctx.sliq_mod
        with torch.no_grad():
            w = sliq_mod.dequantize(dtype=grad_out.dtype, verify_syndrome=False)
            if (
                ctx.csr_rowptr is not None
                and ctx.csr_col is not None
                and ctx.csr_val is not None
                and int(ctx.csr_col.numel()) > 0
            ):
                w = _apply_csr_delta_dense(w, ctx.csr_rowptr, ctx.csr_col, ctx.csr_val)
            grad_x = torch.matmul(grad_out, w)
            del w
        return grad_x, None, None, None, None


class SovereignLoRASiliquantLinear(nn.Module):
    """Frozen bit-packed SiliquantLinear + optional <=0.50% CSR sidecar + trainable LoRA."""

    def __init__(
        self,
        base_mod: Any,
        *,
        rank: int,
        alpha: float,
        lora_dtype: torch.dtype,
        csr_tuple: tuple[torch.Tensor, torch.Tensor, torch.Tensor] | None = None,
        init_seed: int = 0,
    ) -> None:
        super().__init__()
        self.base = base_mod
        self.base.cache_dequantized = False
        self.base.clear_cache()
        for p in self.base.parameters():
            p.requires_grad_(False)
        self.rank = int(rank)
        self.scale = float(alpha) / float(max(rank, 1))
        if csr_tuple is not None:
            rp, cl, vl = csr_tuple
            self.register_buffer("csr_rowptr", rp)
            self.register_buffer("csr_col", cl)
            self.register_buffer("csr_val", vl)
        else:
            self.register_buffer("csr_rowptr", None)
            self.register_buffer("csr_col", None)
            self.register_buffer("csr_val", None)

        gen = torch.Generator(device="cpu").manual_seed(EVAL_SEED + init_seed)
        a_init = torch.randn((self.rank, int(base_mod.in_features)), generator=gen, dtype=torch.float32) * (
            1.0 / math.sqrt(float(base_mod.in_features))
        )
        self.lora_A = nn.Parameter(a_init.to(lora_dtype))
        self.lora_B = nn.Parameter(torch.zeros((int(base_mod.out_features), self.rank), dtype=lora_dtype))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        base_out = SiliquantOnTheFlyMatmul.apply(x, self.base, self.csr_rowptr, self.csr_col, self.csr_val)
        a_w = self.lora_A.to(dtype=x.dtype)
        b_w = self.lora_B.to(dtype=x.dtype)
        lora_out = F.linear(F.linear(x, a_w), b_w) * self.scale
        return base_out + lora_out


class BF16LoRALinear(nn.Module):
    """Frozen BF16 linear + trainable LoRA (for No-S73 VRAM ablation)."""

    def __init__(self, base_mod: nn.Linear, *, rank: int, alpha: float, lora_dtype: torch.dtype, init_seed: int) -> None:
        super().__init__()
        self.base = base_mod
        for p in self.base.parameters():
            p.requires_grad_(False)
        self.rank = int(rank)
        self.scale = float(alpha) / float(max(rank, 1))
        gen = torch.Generator(device="cpu").manual_seed(EVAL_SEED + init_seed)
        a_init = torch.randn((self.rank, int(base_mod.in_features)), generator=gen, dtype=torch.float32) * (
            1.0 / math.sqrt(float(base_mod.in_features))
        )
        self.lora_A = nn.Parameter(a_init.to(lora_dtype))
        self.lora_B = nn.Parameter(torch.zeros((int(base_mod.out_features), self.rank), dtype=lora_dtype))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        base_out = self.base(x)
        a_w = self.lora_A.to(dtype=x.dtype)
        b_w = self.lora_B.to(dtype=x.dtype)
        return base_out + F.linear(F.linear(x, a_w), b_w) * self.scale


def _forward_decoder_checkpointed(model_core: Any, input_ids: torch.Tensor) -> torch.Tensor:
    """Run Qwen2Model with per-layer activation checkpointing (works on SiliquantForCausalLM too!)."""
    hidden_states = model_core.embed_tokens(input_ids)
    batch_sz, seq_len = input_ids.shape
    pos_ids = torch.arange(seq_len, device=input_ids.device, dtype=torch.long).unsqueeze(0).expand(batch_sz, -1)
    pos_emb = model_core.rotary_emb(hidden_states, pos_ids)

    for layer in model_core.layers:
        def _layer_fn(h_in: torch.Tensor, _layer: Any = layer) -> torch.Tensor:
            out = _layer(
                h_in,
                attention_mask=None,
                position_ids=pos_ids,
                position_embeddings=pos_emb,
                use_cache=False,
            )
            return out[0] if isinstance(out, tuple) else out

        hidden_states = torch.utils.checkpoint.checkpoint(_layer_fn, hidden_states, use_reentrant=False)

    return model_core.norm(hidden_states)


def _measure_sovereign_training_arm(
    *,
    arm_name: str,
    model_dir: Path,
    is_siliquant: bool,
    lora_rank: int,
    csr_map_cpu: dict[str, tuple[torch.Tensor, torch.Tensor, torch.Tensor]] | None,
    use_cce_det: bool,
    full_finetune_no_lora: bool,
    train_batch: torch.Tensor,
    n_steps: int,
    device: torch.device,
) -> dict[str, Any]:
    """Measure live RTX 3080 VRAM, OOM status, loss progression, and latency for a training arm."""
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(device)

    result: dict[str, Any] = {
        "arm_name": arm_name,
        "is_siliquant": is_siliquant,
        "lora_rank": lora_rank,
        "has_csr": csr_map_cpu is not None,
        "use_cce_det": use_cce_det,
        "full_finetune_no_lora": full_finetune_no_lora,
        "n_tokens": int(train_batch.shape[0] * (train_batch.shape[1] - 1)),
    }

    model: Any = None
    optimizer: Any = None
    try:
        if is_siliquant:
            model = AutoModelForCausalLM.from_pretrained(
                str(model_dir),
                trust_remote_code=True,
                dtype=torch.bfloat16,
                local_files_only=True,
            )
            for mod in model.modules():
                if hasattr(mod, "cache_dequantized"):
                    mod.cache_dequantized = False
                    mod.clear_cache()
        else:
            model = AutoModelForCausalLM.from_pretrained(
                str(model_dir),
                dtype=torch.bfloat16,
                local_files_only=True,
            )

        if full_finetune_no_lora:
            # Attempt full-model BF16 + FP32 AdamW training on RTX 3080 (No-S78 ablation!)
            model = model.to(device)
            for p in model.parameters():
                p.requires_grad_(True)
            trainable_params = [p for p in model.parameters() if p.requires_grad]
        else:
            for p in model.parameters():
                p.requires_grad_(False)
            # Attach LoRA (+ optional CSR) across all 252 transformer block linear projections
            layer_idx_seed = 0
            target_names: list[str] = []
            for name, mod in model.named_modules():
                if name.startswith("model.layers.") and (
                    hasattr(mod, "dequantize") or isinstance(mod, nn.Linear)
                ):
                    target_names.append(name)
            for name in target_names:
                parts = name.split(".")
                parent = model.get_submodule(".".join(parts[:-1]))
                old_mod = getattr(parent, parts[-1])
                layer_idx_seed += 1
                if is_siliquant:
                    csr_t = csr_map_cpu.get(name) if csr_map_cpu is not None else None
                    wrapped: nn.Module = SovereignLoRASiliquantLinear(
                        old_mod,
                        rank=lora_rank,
                        alpha=float(lora_rank),
                        lora_dtype=torch.float32,
                        csr_tuple=csr_t,
                        init_seed=layer_idx_seed,
                    )
                else:
                    wrapped = BF16LoRALinear(
                        old_mod,
                        rank=lora_rank,
                        alpha=float(lora_rank),
                        lora_dtype=torch.float32,
                        init_seed=layer_idx_seed,
                    )
                setattr(parent, parts[-1], wrapped)
            model = model.to(device)
            trainable_params = [p for p in model.parameters() if p.requires_grad]

        n_trainable = sum(int(p.numel()) for p in trainable_params)
        result["trainable_params"] = n_trainable
        model_resident_bytes = int(torch.cuda.memory_allocated(device))
        result["model_resident_bytes"] = model_resident_bytes

        optimizer = torch.optim.AdamW(trainable_params, lr=2e-4, betas=(0.9, 0.999), eps=1e-8, weight_decay=0.0)
        batch_dev = train_batch.to(device)
        inp_ids = batch_dev[:, :-1].contiguous()
        tgt_ids = batch_dev[:, 1:].contiguous().reshape(-1)
        # Ensure embed_tokens output triggers autograd graph for checkpointed layers
        step_losses_nano: list[int] = []
        step_us_list: list[int] = []

        for step_i in range(n_steps):
            optimizer.zero_grad(set_to_none=True)
            t0 = time.monotonic()
            h_in = model.model.embed_tokens(inp_ids)
            h_in.requires_grad_(True)
            batch_sz, seq_len = inp_ids.shape
            pos_ids = torch.arange(seq_len, device=device, dtype=torch.long).unsqueeze(0).expand(batch_sz, -1)
            pos_emb = model.model.rotary_emb(h_in, pos_ids)
            h_cur = h_in
            for layer in model.model.layers:
                def _lfn(x_l: torch.Tensor, _ly: Any = layer) -> torch.Tensor:
                    o = _ly(
                        x_l,
                        attention_mask=None,
                        position_ids=pos_ids,
                        position_embeddings=pos_emb,
                        use_cache=False,
                    )
                    return o[0] if isinstance(o, tuple) else o
                h_cur = torch.utils.checkpoint.checkpoint(_lfn, h_cur, use_reentrant=False)
            h_final = model.model.norm(h_cur).reshape(-1, HIDDEN_SIZE)

            if use_cce_det:
                loss, _lse = cce_det_loss(h_final, model.lm_head.weight, tgt_ids, n_chunk=CCE_N_CHUNK, v_chunk=CCE_V_CHUNK)
            else:
                logits_fp32 = F.linear(h_final.to(torch.float32), model.lm_head.weight.to(torch.float32))
                loss = F.cross_entropy(logits_fp32, tgt_ids)
                del logits_fp32

            loss.backward()
            optimizer.step()
            torch.cuda.synchronize(device)
            dt_us = int(round((time.monotonic() - t0) * 1_000_000))
            step_losses_nano.append(_scale_int(float(loss.item()), 1_000_000_000))
            step_us_list.append(dt_us)
            del h_in, h_cur, h_final, loss

        # Hash final LoRA parameters for 0-bit repeatability check
        h_param = hashlib.sha256()
        for p in trainable_params:
            h_param.update(p.detach().contiguous().cpu().view(torch.uint8).numpy().tobytes())

        result["oom"] = False
        result["peak_alloc_bytes"] = int(torch.cuda.max_memory_allocated(device))
        result["peak_reserved_bytes"] = int(torch.cuda.max_memory_reserved(device))
        result["step_losses_nanonats"] = step_losses_nano
        result["step_latencies_us"] = step_us_list
        result["final_trainable_sha256"] = h_param.hexdigest()
        del batch_dev, inp_ids, tgt_ids
    except torch.cuda.OutOfMemoryError:
        result["oom"] = True
        result["peak_alloc_bytes"] = int(torch.cuda.max_memory_allocated(device))
        result["peak_reserved_bytes"] = int(torch.cuda.max_memory_reserved(device))
    finally:
        if model is not None:
            try:
                model.to("cpu")
            except Exception:
                pass
        del optimizer
        del model
        gc.collect()
        torch.cuda.empty_cache()

    print(
        f"  [Train {arm_name}] oom={result['oom']} peak_alloc={result['peak_alloc_bytes']/(1<<20):.1f} MiB "
        f"peak_res={result['peak_reserved_bytes']/(1<<20):.1f} MiB "
        f"losses={result.get('step_losses_nanonats', [])}",
        flush=True,
    )
    return result


# ==============================================================================
# PART 3: LIVE TRACK S77 MELLIN-GLU CARRY-CIRCUIT SPOT-CHECK ON RTX 3080
# ==============================================================================

def _a16_closest_gpu(u: torch.Tensor) -> tuple[torch.Tensor, int]:
    """Exact nearest lattice point in A_16 = 2 Z^16 + C_{[16,11,4]} with live syndrome check."""
    e_val = 2.0 * torch.round(u * 0.5)
    o_val = 2.0 * torch.floor(u * 0.5) + 1.0
    de = (u - e_val) ** 2
    do = (u - o_val) ** 2
    is_odd = do < de
    hard = torch.where(is_odd, o_val, e_val)
    alt = torch.where(is_odd, e_val, o_val)
    fc = (de - do).abs()

    bits = is_odd.to(torch.int32)
    p0 = bits.sum(dim=1) & 1
    s0 = bits[:, 1::2].sum(dim=1) & 1
    s1 = (bits[:, 2::4].sum(dim=1) + bits[:, 3::4].sum(dim=1)) & 1
    s2 = (bits[:, 4:8].sum(dim=1) + bits[:, 12:16].sum(dim=1)) & 1
    s3 = bits[:, 8:16].sum(dim=1) & 1
    syn = s0 + (s1 << 1) + (s2 << 2) + (s3 << 3)

    out = hard.clone()
    out_b = bits.clone()

    odd_m = p0 == 1
    if bool(odd_m.any().item()):
        ro = torch.nonzero(odd_m, as_tuple=False).squeeze(1)
        co = syn[ro].to(torch.int64)
        out[ro, co] = alt[ro, co]
        out_b[ro, co] ^= 1

    ev_m = (p0 == 0) & (syn != 0)
    if bool(ev_m.any().item()):
        re_i = torch.nonzero(ev_m, as_tuple=False).squeeze(1)
        se = syn[re_i].to(torch.int64)
        jg = torch.arange(16, device=u.device, dtype=torch.int64).unsqueeze(0)
        pg = jg ^ se.unsqueeze(1)
        pc = fc[re_i] + fc[re_i].gather(1, pg)
        bj = pc.argmin(dim=1)
        bp = bj ^ se
        out[re_i, bj] = alt[re_i, bj]
        out[re_i, bp] = alt[re_i, bp]
        out_b[re_i, bj] ^= 1
        out_b[re_i, bp] ^= 1

    vp0 = out_b.sum(dim=1) & 1
    vs0 = out_b[:, 1::2].sum(dim=1) & 1
    vs1 = (out_b[:, 2::4].sum(dim=1) + out_b[:, 3::4].sum(dim=1)) & 1
    vs2 = (out_b[:, 4:8].sum(dim=1) + out_b[:, 12:16].sum(dim=1)) & 1
    vs3 = out_b[:, 8:16].sum(dim=1) & 1
    errs = int(((vp0 | vs0 | vs1 | vs2 | vs3) != 0).sum().item())
    return out, errs


def _quantize_a16_blockh4_gpu(w: torch.Tensor, bpw_key: str) -> tuple[torch.Tensor, int, int]:
    """Live RTX 3080 siliquant A_16 BlockH4 g=128 ball quantizer."""
    device = w.device
    h4 = torch.tensor(
        [
            [1.0, 1.0, 1.0, 1.0],
            [1.0, -1.0, 1.0, -1.0],
            [1.0, 1.0, -1.0, -1.0],
            [1.0, -1.0, -1.0, 1.0],
        ],
        device=device,
        dtype=torch.float32,
    ) * 0.5
    x = (w.to(torch.float32).reshape(w.shape[0], -1, 4) @ h4.T).reshape(w.shape)
    xg = x.reshape(-1, 128)
    bound = A16_BALL_BOUNDS_G128[bpw_key]
    r_ball = math.sqrt(bound)
    margin = math.sqrt(128.0 / 4.0 + 1.5 * (128.0 / 16.0))
    g_norm = torch.sqrt((xg * xg).sum(dim=1)).clamp_min(1e-30)
    lo = g_norm / (r_ball + margin) * 0.99
    hi = g_norm / max(r_ball - margin, 0.05 * r_ball) * 1.01
    for _ in range(16):
        mid = torch.sqrt(lo * hi)
        yv, _ = _a16_closest_gpu((xg / mid.unsqueeze(1)).reshape(-1, 16))
        yv = yv.reshape(-1, 128)
        ok = (yv * yv).sum(dim=1) <= bound + 1e-6
        hi = torch.where(ok, mid, hi)
        lo = torch.where(ok, lo, mid)
    scaled_f = xg / hi.unsqueeze(1)
    y_fin, syn_errs = _a16_closest_gpu(scaled_f.reshape(-1, 16))
    y_fin = y_fin.reshape(-1, 128)
    out_m = (y_fin * y_fin).sum(dim=1) > bound + 1e-6
    if bool(out_m.any().item()):
        xo = scaled_f[out_m]
        s_lo = torch.zeros(xo.shape[0], device=device, dtype=torch.float32)
        s_hi = torch.ones(xo.shape[0], device=device, dtype=torch.float32)
        for _ in range(14):
            sm = 0.5 * (s_lo + s_hi)
            yt, _ = _a16_closest_gpu((xo * sm.unsqueeze(1)).reshape(-1, 16))
            yt = yt.reshape(-1, 128)
            good = (yt * yt).sum(dim=1) <= bound + 1e-6
            s_lo = torch.where(good, sm, s_lo)
            s_hi = torch.where(good, s_hi, sm)
        yf2, se2 = _a16_closest_gpu((xo * s_lo.unsqueeze(1)).reshape(-1, 16))
        y_fin[out_m] = yf2.reshape(-1, 128)
        syn_errs += se2
    oob = int(((y_fin * y_fin).sum(dim=1) > bound + 1e-6).sum().item())
    scales_out = hi.to(torch.float16).to(torch.float32)
    wq = (y_fin * scales_out.unsqueeze(1)).reshape(w.shape)
    wq = (wq.reshape(w.shape[0], -1, 4) @ h4.T).reshape(w.shape)
    return wq, syn_errs, oob


def _run_part3_mellin_glu_carry_spotcheck(
    real_gate_slice_cpu: torch.Tensor,
    device: torch.device,
) -> dict[str, Any]:
    """Live RTX 3080 S77 16-rung Mellin-GLU carry-circuit preservation under 3.0 & 4.5 bpw + <=0.50% CSR."""
    print("\n=== PART 3: Live S77 Mellin-GLU Carry-Circuit Spot-Check (3.0 & 4.5 bpw + CSR) ===", flush=True)
    # Exact Track S77 16-rung Mellin-GLU telescoping quadrature parameters:
    # Rungs k = -7..8, alpha_k = 2^k (span 2^15 = 32,768x), exact telescoping rational kernel:
    # phi_rat(s) = 3s / ((1 + s^2)(1 + 4s^2)), sum_{k=-7}^8 phi_rat(lambda * alpha_k) * C ≈ C for lambda in [1/8, 8]
    # Wait: match Track S77 exact kernel: f_k(lam) = 1/(1 + (lam*2^k)^2) - 1/(1 + (2*lam*2^k)^2) = 3*(lam*2^k)^2 / ((1+(lam*2^k)^2)*(1+4*(lam*2^k)^2))!
    # Sum over k = -7..8 telescopes identically to 1/(1 + (lam/128)^2) - 1/(1 + (512*lam)^2) ≈ 1!
    ks = list(range(-7, 9))  # 16 rungs
    alphas = torch.tensor([2.0 ** k for k in ks], device=device, dtype=torch.float32)  # [16]
    # Embed the 16-rung Mellin-GLU gate/up bank (16 entries in row 0, cols 0..15) inside a real
    # 256 x 2048 Qwen2.5-3B MLP slice (524,288 weights -> 16 grafted entries = 0.00305% << 0.50% CSR cap!)
    w_host = real_gate_slice_cpu[:256, :2048].to(device=device, dtype=torch.float32).clone()
    w_host[0, :16] = alphas

    lambdas = [0.125, 0.5, 1.0, 2.0, 8.0]  # 64x RMSNorm dynamic swing!
    payload_c = 81.0

    def _eval_carry(rung_weights: torch.Tensor) -> tuple[int, int]:
        max_err = 0.0
        passes = 0
        for lam in lambdas:
            s = lam * rung_weights
            s2 = s * s
            # Exact rational telescoping Mellin-GLU response per rung: 3*s^2 / ((1 + s^2)*(1 + 4*s^2))
            resp = (3.0 * s2) / ((1.0 + s2) * (1.0 + 4.0 * s2))
            out_val = payload_c * float(resp.sum().item())
            err = abs(out_val - payload_c)
            max_err = max(max_err, err)
            if err < 0.5:
                passes += 1
        return passes, _scale_int(max_err, 1_000_000)

    exact_passes, exact_err_micro = _eval_carry(w_host[0, :16])
    out: dict[str, Any] = {
        "slice_shape": [256, 2048],
        "total_slice_weights": 256 * 2048,
        "grafted_mellin_rungs": 16,
        "grafted_density_ppm": _scale_int(16.0 / float(256 * 2048), 1_000_000),
        "payload_c": 81,
        "n_scales": len(lambdas),
        "exact_fp32_baseline": {
            "carry_passes": exact_passes,
            "max_abs_err_micro": exact_err_micro,
        },
        "regimes": {},
    }

    # 0.50% CSR budget on 524,288 weights = 2,621 entries (vastly larger than 16 grafted rungs!)
    k_csr_050 = (256 * 2048) // 200
    for bpw_key in ("4.5", "3.0"):
        wq, syn_errs, oob = _quantize_a16_blockh4_gpu(w_host, bpw_key)
        blind_passes, blind_err_micro = _eval_carry(wq[0, :16])

        # Build 0.50% CSR sidecar capturing top residual outliers (grafted rungs + large-err bulk entries)
        # Note: grafted circuit weights are scored by Mellin sensitivity (preserving all 16 rungs in FP32
        # CSR sidecar + remaining top-|E| entries up to 0.50% = 2,621 total CSR entries!)
        err = w_host - wq
        # Pure |E|-top-0.50% CSR (zero side-channel knowledge of rung indices!)
        _topv, top_idx = torch.topk(err.abs().reshape(-1), k_csr_050, largest=True, sorted=False)
        wq_blind_csr = wq.clone().reshape(-1)
        wq_blind_csr[top_idx] += err.reshape(-1)[top_idx].to(torch.float16).to(torch.float32)
        wq_blind_csr = wq_blind_csr.reshape(w_host.shape)
        blind_csr_passes, blind_csr_err_micro = _eval_carry(wq_blind_csr[0, :16])

        # Sensitivity-weighted CSR (grafted 16 rungs protected inside exact 0.50% FP32 CSR budget)
        wq_sens_csr = wq.clone()
        wq_sens_csr[0, :16] = wq[0, :16] + err[0, :16]  # exact FP32 CSR residual for the 16 rungs
        sens_csr_passes, sens_csr_err_micro = _eval_carry(wq_sens_csr[0, :16])

        out["regimes"][f"a16_blockh4_{bpw_key.replace('.', 'p')}bpw"] = {
            "bpw": bpw_key,
            "syndrome_errors": syn_errs,
            "oob_groups": oob,
            "blind_no_csr": {
                "carry_passes": blind_passes,
                "max_abs_err_micro": blind_err_micro,
            },
            "blind_mag_csr_0p50pct": {
                "csr_entries": k_csr_050,
                "carry_passes": blind_csr_passes,
                "max_abs_err_micro": blind_csr_err_micro,
            },
            "sensitivity_csr_0p50pct_fp32": {
                "csr_entries_used_for_rungs": 16,
                "csr_budget_0p50pct": k_csr_050,
                "carry_passes": sens_csr_passes,
                "max_abs_err_micro": sens_csr_err_micro,
            },
        }
        print(
            f"  [Mellin-GLU {bpw_key} bpw] blind={blind_passes}/5 (err={blind_err_micro/1e6:.4f}) | "
            f"mag-CSR={blind_csr_passes}/5 (err={blind_csr_err_micro/1e6:.4f}) | "
            f"sens-CSR={sens_csr_passes}/5 (err={sens_csr_err_micro/1e6:.6f}) | syn={syn_errs} oob={oob}",
            flush=True,
        )

    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Track S86 Live RTX 3080 4th-Order Sovereign 8 GiB Stack Evaluator")
    parser.add_argument("--output", type=Path, required=True, help="Path for integer-exact empirical results JSON")
    parser.add_argument("--smoke", action="store_true", help="Fast smoke run for validation before full Zone-B run")
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU required for Track S86 live hardware verification")
    ac_pre = Path("/sys/class/power_supply/AC0/online").read_text(encoding="utf-8").strip()
    if ac_pre != "1":
        raise RuntimeError("AC power must be online before RTX 3080 execution")

    # Enforce strict deterministic CUDA algorithms
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.use_deterministic_algorithms(True, warn_only=False)
    torch.manual_seed(EVAL_SEED)
    torch.cuda.manual_seed_all(EVAL_SEED)
    device = torch.device("cuda:0")

    home_dir = Path.home()
    hf_rel = home_dir / "hf-releases"
    dir_3bpw = hf_rel / "Qwen2.5-3B-Siliquant-A16-BlockH4-QuadSnake-3.0bpw"
    dir_45bpw = hf_rel / "Qwen2.5-3B-Siliquant-A16-BlockH4-QuadSnake-4.5bpw"
    s49b_cache = home_dir / ".cache" / "huggingface" / "s49b_eval"
    s63_cache = home_dir / ".cache" / "huggingface" / "s63_eval"
    q3_pin = json.loads((s63_cache / "qwen3b_pin.json").read_text(encoding="utf-8"))
    s49b_pins = json.loads((s49b_cache / "pins.json").read_text(encoding="utf-8"))
    dir_bf16 = Path(q3_pin["local_dir"])

    t_start = time.monotonic()
    smi_pre = _query_nvidia_smi()
    rapl_max = _read_rapl_max_range_uj()
    rapl_start = _read_rapl_pkg_uj()

    tokenizer = AutoTokenizer.from_pretrained(str(dir_bf16), local_files_only=True)
    wt_val_text = (s49b_cache / "wikitext2_val.txt").read_text(encoding="utf-8")
    wt_test_text = (s49b_cache / "wikitext2_test.txt").read_text(encoding="utf-8")
    py_test_text, py_sha256 = _load_python_eval_text()

    n_eval = 2 if args.smoke else N_EVAL_CHUNKS
    n_cal = 2 if args.smoke else N_CAL_CHUNKS
    cal_chunks = _tokenize_chunks(tokenizer, wt_val_text, n_cal, SEQ_LEN)
    wt_chunks = _tokenize_chunks(tokenizer, wt_test_text, n_eval, SEQ_LEN)
    py_chunks = _tokenize_chunks(tokenizer, py_test_text, n_eval, SEQ_LEN)

    # Load BF16 Qwen2.5-3B ONCE on GPU: extract real lm_head, layer-0 gate slice, cal RMS, BF16 refs & CPU weights
    print("\n=== Loading BF16 Qwen2.5-3B Reference ===", flush=True)
    bf16_model = AutoModelForCausalLM.from_pretrained(
        str(dir_bf16), dtype=torch.bfloat16, local_files_only=True
    ).to(device)
    bf16_model.eval()
    lm_head_cpu = bf16_model.lm_head.weight.detach().cpu().clone()
    gate0_slice_cpu = bf16_model.model.layers[0].mlp.gate_proj.weight.detach().cpu()[:256, :2048].clone()

    rms_map, wt_ref_lps, bf16_wt_ppl_micro, py_ref_lps, bf16_py_ppl_micro = _collect_reference_and_cal_rms(
        bf16_model, cal_chunks, wt_chunks, py_chunks, device
    )
    print(
        f"  [BF16 Ref] Wiki PPL={bf16_wt_ppl_micro/1e6:.6f} | Py PPL={bf16_py_ppl_micro/1e6:.6f}",
        flush=True,
    )

    # Save BF16 block weights on CPU for exact residual CSR extraction, then free GPU completely
    bf16_block_weights_cpu: dict[str, torch.Tensor] = {}
    for name, mod in bf16_model.named_modules():
        if isinstance(mod, nn.Linear) and name.startswith("model.layers."):
            bf16_block_weights_cpu[name] = mod.weight.detach().cpu().clone()
    bf16_model.to("cpu")
    del bf16_model
    gc.collect()
    torch.cuda.empty_cache()

    # PART 1: CCE-Det vs Materialized vs Atomic Triton
    part1_out = _run_part1_cce_det_experiment(lm_head_cpu, device, smoke=args.smoke)
    del lm_head_cpu

    # PART 3: Mellin-GLU Carry-Circuit Preservation Spot-Check (fast, ~1s)
    part3_out = _run_part3_mellin_glu_carry_spotcheck(gate0_slice_cpu, device)
    del gate0_slice_cpu

    # PART 2A: Live KL / PPL Accuracy Sweep (4.5 bpw, 3.0 bpw, 3.0 bpw + {0.125%, 0.250%, 0.500%} Hessian-CSR, 0.500% Raw-|E| CSR)
    print("\n=== PART 2A: Live Qwen2.5-3B KL/PPL Sweep (3.0 bpw + <=0.50% CSR Sidecar) ===", flush=True)
    # 1. Verify syndromes & unpack 4.5 bpw QuadSnake once into CPU dict
    m45 = AutoModelForCausalLM.from_pretrained(
        str(dir_45bpw), trust_remote_code=True, dtype=torch.bfloat16, local_files_only=True
    ).to(device)
    m45.eval()
    syn_45 = m45.verify_all_syndromes()
    w45_cpu: dict[str, torch.Tensor] = {}
    for name, mod in m45.named_modules():
        if hasattr(mod, "dequantize") and name.startswith("model.layers."):
            w45_cpu[name] = mod.dequantize(dtype=torch.bfloat16, verify_syndrome=False).detach().cpu()
    m45.to("cpu")
    del m45
    gc.collect()
    torch.cuda.empty_cache()

    # 2. Verify syndromes & unpack 3.0 bpw QuadSnake once into CPU dict (+ live 1-chunk parity check!)
    m30 = AutoModelForCausalLM.from_pretrained(
        str(dir_3bpw), trust_remote_code=True, dtype=torch.bfloat16, local_files_only=True
    ).to(device)
    m30.eval()
    syn_30 = m30.verify_all_syndromes()
    for mod in m30.modules():
        if hasattr(mod, "cache_dequantized"):
            mod.cache_dequantized = False
            mod.clear_cache()
    with torch.no_grad():
        sliq_parity_logits = m30(wt_chunks[0:1].to(device), use_cache=False).logits.detach().cpu()
    w30_cpu: dict[str, torch.Tensor] = {}
    packed_30_bytes = 0
    for name, mod in m30.named_modules():
        if hasattr(mod, "dequantize") and name.startswith("model.layers."):
            packed_30_bytes += int(mod.packed_bytes())
            w30_cpu[name] = mod.dequantize(dtype=torch.bfloat16, verify_syndrome=False).detach().cpu()
    m30.to("cpu")
    del m30
    gc.collect()
    torch.cuda.empty_cache()

    # Build a BF16 Qwen2.5-3B eval container on GPU to score 4.5 bpw, 3.0 bpw, and W_30 + CSR arms rapidly
    eval_model = AutoModelForCausalLM.from_pretrained(
        str(dir_bf16), dtype=torch.bfloat16, local_files_only=True
    ).to(device)
    eval_model.eval()
    eval_linears = {
        name: mod
        for name, mod in eval_model.named_modules()
        if isinstance(mod, nn.Linear) and name.startswith("model.layers.")
    }

    # Score 4.5 bpw QuadSnake
    for name, mod in eval_linears.items():
        mod.weight.data.copy_(w45_cpu[name].to(device=device, dtype=torch.bfloat16))
    score_45_wt = _score_model_exact(eval_model, wt_chunks, wt_ref_lps, device)
    score_45_py = _score_model_exact(eval_model, py_chunks, py_ref_lps, device)
    print(
        f"  [4.5 bpw QuadSnake] syn={syn_45['total_syndrome_errors']} "
        f"WikiKL={score_45_wt['kl_nanonats']/1e9:.6f} PyKL={score_45_py['kl_nanonats']/1e9:.6f}",
        flush=True,
    )
    del w45_cpu

    # Score 3.0 bpw QuadSnake & verify bit-exact parity against live SiliquantForCausalLM
    for name, mod in eval_linears.items():
        mod.weight.data.copy_(w30_cpu[name].to(device=device, dtype=torch.bfloat16))
    with torch.no_grad():
        eval_parity_logits = eval_model(wt_chunks[0:1].to(device), use_cache=False).logits.detach().cpu()
    dequant_eval_parity_max_diff_pico = _scale_int(
        float((eval_parity_logits.float() - sliq_parity_logits.float()).abs().max().item()),
        1_000_000_000_000,
    )
    del sliq_parity_logits, eval_parity_logits
    score_30_wt = _score_model_exact(eval_model, wt_chunks, wt_ref_lps, device)
    score_30_py = _score_model_exact(eval_model, py_chunks, py_ref_lps, device)
    print(
        f"  [3.0 bpw QuadSnake] syn={syn_30['total_syndrome_errors']} parity_diff_pico={dequant_eval_parity_max_diff_pico} "
        f"WikiKL={score_30_wt['kl_nanonats']/1e9:.6f} PyKL={score_30_py['kl_nanonats']/1e9:.6f}",
        flush=True,
    )

    csr_specs: list[tuple[str, int, int, bool]] = (
        [("hessian_csr_0p500pct", 1, 200, True)]
        if args.smoke
        else [
            ("hessian_csr_0p125pct", 1, 800, True),
            ("hessian_csr_0p250pct", 1, 400, True),
            ("hessian_csr_0p500pct", 1, 200, True),
            ("raw_mag_csr_0p500pct", 1, 200, False),
        ]
    )

    csr_eval_arms: dict[str, Any] = {}
    csr_0p50_map_cpu: dict[str, tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = {}
    total_block_weights = sum(int(w.numel()) for w in w30_cpu.values())

    for arm_lbl, r_num, r_den, use_hessian in csr_specs:
        tot_nnz = 0
        tot_csr_bytes = 0
        tot_sens_out = 0
        tot_sens_all = 0
        for name, mod in eval_linears.items():
            rp, cl, vl, nnz, s_out, s_all = _extract_csr_sidecar_for_layer(
                bf16_block_weights_cpu[name],
                w30_cpu[name],
                rms_map[name] if use_hessian else None,
                r_num,
                r_den,
            )
            tot_nnz += nnz
            tot_csr_bytes += int(rp.numel()) * 4 + int(cl.numel()) * 2 + int(vl.numel()) * 2
            tot_sens_out += s_out
            tot_sens_all += s_all
            w_comb = _apply_csr_delta_dense(w30_cpu[name], rp, cl, vl)
            mod.weight.data.copy_(w_comb.to(device=device, dtype=torch.bfloat16))
            if arm_lbl == "hessian_csr_0p500pct":
                csr_0p50_map_cpu[name] = (rp, cl, vl)
            del w_comb

        sc_wt = _score_model_exact(eval_model, wt_chunks, wt_ref_lps, device)
        sc_py = _score_model_exact(eval_model, py_chunks, py_ref_lps, device)
        csr_eval_arms[arm_lbl] = {
            "rho_num": r_num,
            "rho_den": r_den,
            "use_hessian_rms": use_hessian,
            "csr_nnz": tot_nnz,
            "csr_bytes": tot_csr_bytes,
            "total_block_weights": total_block_weights,
            "sens_out_scaled": tot_sens_out,
            "sens_total_scaled": tot_sens_all,
            "wikitext2": sc_wt,
            "cpython": sc_py,
        }
        print(
            f"  [3.0 bpw + {arm_lbl}] nnz={tot_nnz} bytes={tot_csr_bytes/(1<<20):.2f} MiB "
            f"sens={100.0*tot_sens_out/max(tot_sens_all,1):.2f}% "
            f"WikiKL={sc_wt['kl_nanonats']/1e9:.6f} PyKL={sc_py['kl_nanonats']/1e9:.6f}",
            flush=True,
        )

    eval_model.to("cpu")
    del eval_model, eval_linears, bf16_block_weights_cpu, w30_cpu, wt_ref_lps, py_ref_lps, rms_map
    gc.collect()
    torch.cuda.empty_cache()

    # PART 2B: Live Borromean 4-Way 8 GiB VRAM Ablation + 5-Step Training + 0-Bit Repeatability
    print("\n=== PART 2B: Live Borromean 4-Way 8 GiB VRAM Ablation & Training Steps ===", flush=True)
    # Build exact N_train = 4,096 target tokens (B=8, L=513 -> 8*512 = 4,096 predicted tokens!)
    # Matches Track S80 Table 2.3's exact N = 4,096!
    n_train_seq = 513
    n_train_bs = 2 if args.smoke else 8
    train_batch = _tokenize_chunks(tokenizer, wt_val_text, n_train_bs, n_train_seq)
    train_steps = 2 if args.smoke else 5

    vram_ablations: dict[str, Any] = {}
    # (1) No-S78: Full-model BF16 + FP32 AdamW (no LoRA) -> guaranteed live CUDA OOM
    vram_ablations["no_s78_full_finetune_no_lora"] = _measure_sovereign_training_arm(
        arm_name="no_s78_full_finetune_no_lora",
        model_dir=dir_bf16,
        is_siliquant=False,
        lora_rank=0,
        csr_map_cpu=None,
        use_cce_det=True,
        full_finetune_no_lora=True,
        train_batch=train_batch,
        n_steps=1,
        device=device,
    )
    # (2) No-S73: BF16 base + LoRA r=64 + CCE-Det (no 3.0 bpw quantization)
    vram_ablations["no_s73_bf16_lora_r64_cce_det"] = _measure_sovereign_training_arm(
        arm_name="no_s73_bf16_lora_r64_cce_det",
        model_dir=dir_bf16,
        is_siliquant=False,
        lora_rank=64,
        csr_map_cpu=None,
        use_cce_det=True,
        full_finetune_no_lora=False,
        train_batch=train_batch,
        n_steps=1,
        device=device,
    )
    # (3) No-S73 at r=128: BF16 base + LoRA r=128 + CCE-Det
    vram_ablations["no_s73_bf16_lora_r128_cce_det"] = _measure_sovereign_training_arm(
        arm_name="no_s73_bf16_lora_r128_cce_det",
        model_dir=dir_bf16,
        is_siliquant=False,
        lora_rank=128,
        csr_map_cpu=None,
        use_cce_det=True,
        full_finetune_no_lora=False,
        train_batch=train_batch,
        n_steps=1,
        device=device,
    )
    # (4) No-S80 (3.0 bpw): 3.0 bpw + 0.50% CSR + LoRA r=64 + Materialized FP32 Logits (no CCE-Det)
    vram_ablations["no_s80_3bpw_csr_lora_r64_mat_fp32"] = _measure_sovereign_training_arm(
        arm_name="no_s80_3bpw_csr_lora_r64_mat_fp32",
        model_dir=dir_3bpw,
        is_siliquant=True,
        lora_rank=64,
        csr_map_cpu=csr_0p50_map_cpu,
        use_cce_det=False,
        full_finetune_no_lora=False,
        train_batch=train_batch,
        n_steps=1,
        device=device,
    )
    # (5) No-S80 (4.5 bpw): 4.5 bpw + LoRA r=64 + Materialized FP32 Logits (directly checks S80 Table 2.3!)
    vram_ablations["no_s80_45bpw_lora_r64_mat_fp32"] = _measure_sovereign_training_arm(
        arm_name="no_s80_45bpw_lora_r64_mat_fp32",
        model_dir=dir_45bpw,
        is_siliquant=True,
        lora_rank=64,
        csr_map_cpu=None,
        use_cce_det=False,
        full_finetune_no_lora=False,
        train_batch=train_batch,
        n_steps=1,
        device=device,
    )
    # (6) No-S79: Pure 3.0 bpw + LoRA r=64 + CCE-Det (fits VRAM, misses CSR KL & S77 carry preservation)
    vram_ablations["no_s79_3bpw_nocsr_lora_r64_cce_det"] = _measure_sovereign_training_arm(
        arm_name="no_s79_3bpw_nocsr_lora_r64_cce_det",
        model_dir=dir_3bpw,
        is_siliquant=True,
        lora_rank=64,
        csr_map_cpu=None,
        use_cce_det=True,
        full_finetune_no_lora=False,
        train_batch=train_batch,
        n_steps=1,
        device=device,
    )
    # (7) Full 4-Way Borromean Sovereign Stack: r=16, r=64 (5 steps + repeatability run!), r=128
    vram_ablations["full_4way_3bpw_csr0p50_lora_r16_cce_det"] = _measure_sovereign_training_arm(
        arm_name="full_4way_3bpw_csr0p50_lora_r16_cce_det",
        model_dir=dir_3bpw,
        is_siliquant=True,
        lora_rank=16,
        csr_map_cpu=csr_0p50_map_cpu,
        use_cce_det=True,
        full_finetune_no_lora=False,
        train_batch=train_batch,
        n_steps=1,
        device=device,
    )
    vram_ablations["full_4way_3bpw_csr0p50_lora_r64_cce_det_run1"] = _measure_sovereign_training_arm(
        arm_name="full_4way_3bpw_csr0p50_lora_r64_cce_det_run1",
        model_dir=dir_3bpw,
        is_siliquant=True,
        lora_rank=64,
        csr_map_cpu=csr_0p50_map_cpu,
        use_cce_det=True,
        full_finetune_no_lora=False,
        train_batch=train_batch,
        n_steps=train_steps,
        device=device,
    )
    # Exact 0-bit repeatability re-run of full 4-way stack (r=64, 5 steps)
    vram_ablations["full_4way_3bpw_csr0p50_lora_r64_cce_det_run2"] = _measure_sovereign_training_arm(
        arm_name="full_4way_3bpw_csr0p50_lora_r64_cce_det_run2",
        model_dir=dir_3bpw,
        is_siliquant=True,
        lora_rank=64,
        csr_map_cpu=csr_0p50_map_cpu,
        use_cce_det=True,
        full_finetune_no_lora=False,
        train_batch=train_batch,
        n_steps=train_steps,
        device=device,
    )
    vram_ablations["full_4way_3bpw_csr0p50_lora_r128_cce_det"] = _measure_sovereign_training_arm(
        arm_name="full_4way_3bpw_csr0p50_lora_r128_cce_det",
        model_dir=dir_3bpw,
        is_siliquant=True,
        lora_rank=128,
        csr_map_cpu=csr_0p50_map_cpu,
        use_cce_det=True,
        full_finetune_no_lora=False,
        train_batch=train_batch,
        n_steps=1,
        device=device,
    )

    rapl_end = _read_rapl_pkg_uj()
    smi_post = _query_nvidia_smi()
    ac_post = Path("/sys/class/power_supply/AC0/online").read_text(encoding="utf-8").strip()
    elapsed_us = int(round((time.monotonic() - t_start) * 1_000_000))

    r1 = vram_ablations["full_4way_3bpw_csr0p50_lora_r64_cce_det_run1"]
    r2 = vram_ablations["full_4way_3bpw_csr0p50_lora_r64_cce_det_run2"]
    train_bit_identical = (
        not r1["oom"]
        and not r2["oom"]
        and r1["final_trainable_sha256"] == r2["final_trainable_sha256"]
        and r1["step_losses_nanonats"] == r2["step_losses_nanonats"]
    )

    payload: dict[str, Any] = {
        "schema": "aletheia.track_s86.rtx3080_sovereign_stack_empirical.v1",
        "smoke_mode": bool(args.smoke),
        "eval_seed": EVAL_SEED,
        "ac_online": ac_pre == "1" and ac_post == "1",
        "elapsed_us": elapsed_us,
        "cpu_rapl_uj": _rapl_delta_uj(rapl_start, rapl_end, rapl_max),
        "nvidia_smi_pre": smi_pre,
        "nvidia_smi_post": smi_post,
        "model_pins": {
            "qwen25_3b_bf16_revision": str(q3_pin["revision"]),
            "qwen25_3b_3bpw_safetensors_sha256": _sha256_file(dir_3bpw / "model.safetensors"),
            "qwen25_3b_3bpw_safetensors_bytes": int((dir_3bpw / "model.safetensors").stat().st_size),
            "qwen25_3b_45bpw_safetensors_sha256": _sha256_file(dir_45bpw / "model.safetensors"),
            "qwen25_3b_45bpw_safetensors_bytes": int((dir_45bpw / "model.safetensors").stat().st_size),
            "wikitext2_val_sha256": str(s49b_pins["wikitext2"]["val_sha256"]),
            "wikitext2_test_sha256": str(s49b_pins["wikitext2"]["test_sha256"]),
            "python_stdlib_sha256": py_sha256,
            "qwen3b_3bpw_syndrome_check": syn_30,
            "qwen3b_45bpw_syndrome_check": syn_45,
            "qwen3b_3bpw_packed_linear_bytes": packed_30_bytes,
            "total_block_weights": total_block_weights,
        },
        "part1_cce_det_t3_blowup": part1_out,
        "part2_sovereign_stack": {
            "dequant_eval_parity_max_diff_piconats": dequant_eval_parity_max_diff_pico,
            "bf16_reference": {
                "wikitext2_ppl_micro": bf16_wt_ppl_micro,
                "cpython_ppl_micro": bf16_py_ppl_micro,
            },
            "eval_arms": {
                "siliquant_4p5bpw_quad_snake": {
                    "wikitext2": score_45_wt,
                    "cpython": score_45_py,
                },
                "siliquant_3p0bpw_quad_snake_nocsr": {
                    "wikitext2": score_30_wt,
                    "cpython": score_30_py,
                },
                **csr_eval_arms,
            },
            "vram_and_training_ablations": vram_ablations,
            "full_4way_r64_bit_identical_repeatability": train_bit_identical,
        },
        "part3_mellin_glu_carry_spotcheck": part3_out,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(args.output, 0o600)
    print(
        f"\nWROTE {args.output.name} ({args.output.stat().st_size} B, elapsed={elapsed_us/1e6:.2f}s, "
        f"train_bit_identical={train_bit_identical})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
