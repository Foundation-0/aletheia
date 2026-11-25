#!/usr/bin/env python3
"""Track S106 Phase 2: Blind Zero-Tuning Held-Out RTX 3080 Gauntlet (H1, H2a, H3a, H3b, H3c, H4).

Reads ONLY immutable s106_frozen_pilot_params.json (locked on synthetic Gaussian + Qwen2.5-0.5B)
and evaluates ALL preregistered hypotheses & controls with ZERO hyperparameter tuning across:
  - HuggingFaceTB/SmolLM2-360M (cross-family Llama architecture)
  - Qwen/Qwen2.5-1.5B
  - Qwen/Qwen2.5-3B
on BOTH held-out corpora (Wikipedia prose + Python stdlib source), measuring:
  - Strict CS-08 exact_bpw (100% of index, scale, LUT, and codebook bits accounted)
  - Token-level mean KL ± SE (and chunk-level SE), p95 KL, PPL, top-1 match %, weight SNR (dB)
  - Live syndrome errors (must be 0), out-of-ball groups (must be 0), non-block tensor diffs (must be 0)
  - Per-layer H1-P2 Spearman rho (post-SphereMap excess kurtosis vs single-layer KL degradation)
  - GPU & CPU pack/decode throughput (Gw/s): closed-form LUT-free EQ(S^3) vs A_16 hampack-style
  - Inference energy (mJ/tok) via Intel RAPL + NVML power telemetry

Grades EVERY hypothesis honestly (CONFIRMED / PARTIAL / FALSIFIED / UNDETERMINABLE) directly
against locked PREREG_SPHERE_PI_FORCES_V1.md (SHA-256 ac3e6211...). Saves ZERO model weights!
"""

from __future__ import annotations

import datetime
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

import numpy as np
import torch
import torch.nn.functional as F
from scipy.stats import spearmanr
from transformers import AutoModelForCausalLM, AutoTokenizer

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import s106_quant_ops as ops

EVAL_SEED = 2026112506
SEQ_LEN = 512
N_EVAL_CHUNKS = 8
N_LAYER_PROBE_CHUNKS = 4
LOGIT_TOK_CHUNK = 64

STDLIB_PY_MODULES = (
    "fractions.py",
    "difflib.py",
    "decimal.py",
    "statistics.py",
    "argparse.py",
    "json/decoder.py",
)


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


def _rapl_delta_joules(start_uj: int, end_uj: int, max_range_uj: int) -> float:
    if end_uj >= start_uj:
        diff = end_uj - start_uj
    elif max_range_uj > 0:
        diff = (max_range_uj - start_uj) + end_uj
    else:
        diff = 0
    return round(diff / 1e6, 4)


def _query_nvml_power_w() -> float:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
            text=True,
        ).strip()
        return float(out.splitlines()[0].strip())
    except Exception:
        return 0.0


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
        "power_draw_w": float(parts[4]),
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
        ids = ids.repeat((need // ids.numel()) + 1)
    return ids[:need].reshape(n_chunks, seq_len).contiguous()


def _collect_block_linears(model: torch.nn.Module) -> list[tuple[str, torch.nn.Linear]]:
    return [
        (name, mod)
        for name, mod in model.named_modules()
        if isinstance(mod, torch.nn.Linear) and name.startswith("model.layers.")
    ]


def _layer_idx(name: str) -> int:
    return int(name.split(".")[2])


def _snapshot_non_block_tensors(model: torch.nn.Module) -> dict[str, bytes]:
    snaps: dict[str, bytes] = {}
    for name, param in model.named_parameters():
        if not name.startswith("model.layers.") or not name.endswith("_proj.weight"):
            snaps[name] = hashlib.sha256(param.detach().cpu().view(torch.uint8).numpy().tobytes()).digest()
    return snaps


def _count_non_block_diffs(model: torch.nn.Module, snaps: dict[str, bytes]) -> int:
    diffs = 0
    for name, param in model.named_parameters():
        if name in snaps:
            cur = hashlib.sha256(param.detach().cpu().view(torch.uint8).numpy().tobytes()).digest()
            if cur != snaps[name]:
                diffs += 1
    return diffs


@torch.no_grad()
def _collect_reference_logits(
    model: torch.nn.Module, chunks: torch.Tensor, device: torch.device
) -> tuple[list[torch.Tensor], float, dict[str, float]]:
    rapl_max = _read_rapl_max_range_uj()
    p_pre = _query_nvml_power_w()
    r_pre = _read_rapl_pkg_uj()
    torch.cuda.synchronize()
    t0 = time.monotonic()

    ref_lp: list[torch.Tensor] = []
    tot_nll = 0.0
    tot_toks = 0
    for i in range(chunks.shape[0]):
        inp = chunks[i : i + 1].to(device)
        logits = model(inp, use_cache=False).logits[:, :-1, :]
        targets = inp[:, 1:]
        seq_t = logits.shape[1]
        parts: list[torch.Tensor] = []
        for s0 in range(0, seq_t, LOGIT_TOK_CHUNK):
            s1 = min(s0 + LOGIT_TOK_CHUNK, seq_t)
            lp = F.log_softmax(logits[:, s0:s1, :].to(torch.float32), dim=-1)
            nll = F.nll_loss(lp.reshape(-1, lp.shape[-1]), targets[:, s0:s1].reshape(-1), reduction="sum")
            tot_nll += float(nll.item())
            tot_toks += int(targets[:, s0:s1].numel())
            parts.append(lp.cpu())
            del lp
        ref_lp.append(torch.cat(parts, dim=1))
        del inp, logits, parts

    torch.cuda.synchronize()
    dt = max(time.monotonic() - t0, 1e-6)
    r_post = _read_rapl_pkg_uj()
    p_post = _query_nvml_power_w()
    cpu_j = _rapl_delta_joules(r_pre, r_post, rapl_max)
    gpu_j = 0.5 * (p_pre + p_post) * dt
    mj_per_tok_gpu = 1000.0 * gpu_j / float(max(tot_toks, 1))
    mj_per_tok_total = 1000.0 * (gpu_j + cpu_j) / float(max(tot_toks, 1))
    torch.cuda.empty_cache()
    energy = {
        "tokens": tot_toks,
        "elapsed_s": round(dt, 4),
        "cpu_rapl_j": round(cpu_j, 4),
        "gpu_est_j": round(gpu_j, 4),
        "gpu_mj_per_tok": round(mj_per_tok_gpu, 4),
        "total_mj_per_tok": round(mj_per_tok_total, 4),
    }
    return ref_lp, math.exp(tot_nll / max(tot_toks, 1)), energy


@torch.no_grad()
def _score_against_reference(
    model: torch.nn.Module,
    chunks: torch.Tensor,
    ref_lp: list[torch.Tensor],
    device: torch.device,
) -> dict[str, float]:
    kl_list: list[float] = []
    chunk_means: list[float] = []
    tot_nll = 0.0
    tot_toks = 0
    same_top1 = 0
    for i in range(chunks.shape[0]):
        inp = chunks[i : i + 1].to(device)
        logits = model(inp, use_cache=False).logits[:, :-1, :]
        targets = inp[:, 1:]
        ref_cpu = ref_lp[i]
        seq_t = logits.shape[1]
        c_kls: list[float] = []
        for s0 in range(0, seq_t, LOGIT_TOK_CHUNK):
            s1 = min(s0 + LOGIT_TOK_CHUNK, seq_t)
            log_q = F.log_softmax(logits[:, s0:s1, :].to(torch.float32), dim=-1)
            log_p = ref_cpu[:, s0:s1, :].to(device)
            tok_kl = (torch.exp(log_p) * (log_p - log_q)).sum(dim=-1).reshape(-1)
            vals = tok_kl.cpu().tolist()
            kl_list.extend(vals)
            c_kls.extend(vals)
            nll = F.nll_loss(log_q.reshape(-1, log_q.shape[-1]), targets[:, s0:s1].reshape(-1), reduction="sum")
            tot_nll += float(nll.item())
            tot_toks += int(targets[:, s0:s1].numel())
            same_top1 += int((log_q.argmax(dim=-1) == log_p.argmax(dim=-1)).sum().item())
            del log_q, log_p, tok_kl
        chunk_means.append(sum(c_kls) / max(len(c_kls), 1))
        del inp, logits
    torch.cuda.empty_cache()
    kl_t = torch.tensor(kl_list, dtype=torch.float64)
    cm_t = torch.tensor(chunk_means, dtype=torch.float64)
    se_tok = float(kl_t.std(unbiased=True).item() / math.sqrt(float(len(kl_list))))
    se_chunk = float(cm_t.std(unbiased=True).item() / math.sqrt(float(len(chunk_means))))
    return {
        "mean_kl": round(float(kl_t.mean().item()), 8),
        "se_kl": round(se_tok, 8),
        "chunk_se_kl": round(se_chunk, 8),
        "p95_kl": round(float(torch.quantile(kl_t, 0.95).item()), 8),
        "ppl": round(math.exp(tot_nll / max(tot_toks, 1)), 6),
        "top1_match_pct": round(100.0 * float(same_top1) / float(max(tot_toks, 1)), 4),
        "tokens_scored": tot_toks,
    }


def _benchmark_pack_decode_throughput(device: torch.device) -> dict[str, Any]:
    """H2a Pack/Decode Throughput Microbenchmark (GPU & CPU Gw/s):
    Closed-form LUT-free Hopf-Hex EQ(S^3) (0 codebook bytes!) vs A_16 hampack-style syndrome decode."""
    n_weights = 16_777_216  # 16M weights = 4M S^3 blocks = 1M A_16 blocks
    n_s3 = n_weights // 4
    n_a16 = n_weights // 16
    rng = np.random.default_rng(20261125)

    # 1. GPU closed-form LUT-free Hopf-Hex EQ(S^3) decode (uint8 index -> 4 floats via exact closed-form arithmetic!)
    # Band table has 4 bands (16,3)=48, (10,8)=80, (8,10)=80, (3,16)=48 -> pure integer thresholds [48, 128, 208]
    idx_gpu = torch.tensor(rng.integers(0, 256, size=n_s3, dtype=np.uint8), device=device, dtype=torch.int32)
    b_r1 = torch.tensor([0.9511, 0.7937, 0.6083, 0.3088], device=device, dtype=torch.float32)
    b_r2 = torch.tensor([0.3088, 0.6083, 0.7937, 0.9511], device=device, dtype=torch.float32)
    b_n1 = torch.tensor([16, 10, 8, 3], device=device, dtype=torch.int32)
    b_n2 = torch.tensor([3, 8, 10, 16], device=device, dtype=torch.int32)
    b_off = torch.tensor([0, 48, 128, 208], device=device, dtype=torch.int32)

    def _decode_eq_s3_closed_gpu(idx: torch.Tensor) -> torch.Tensor:
        b = (idx >= 48).to(torch.int32) + (idx >= 128).to(torch.int32) + (idx >= 208).to(torch.int32)
        loc = idx - b_off[b]
        n2 = b_n2[b]
        n1 = b_n1[b]
        i = torch.div(loc, n2, rounding_mode="floor")
        j = loc - i * n2
        p1 = -math.pi + (i.to(torch.float32) + 0.5) * (2.0 * math.pi / n1.to(torch.float32))
        stag = (i & 1).to(torch.float32) * 0.5
        p2 = -math.pi + (j.to(torch.float32) + stag + 0.25) * (2.0 * math.pi / n2.to(torch.float32))
        r1 = b_r1[b]
        r2 = b_r2[b]
        return torch.stack([r1 * torch.cos(p1), r1 * torch.sin(p1), r2 * torch.cos(p2), r2 * torch.sin(p2)], dim=1)

    # 2. GPU LUT-indexed EQ(S^3) decode (256x4 = 1KB L1-resident table)
    cb_eq_gpu = ops.build_eq_s3_leopardi().to(device)

    # 3. GPU hampack-style A_16 [16,11,4] bit-unpack + parity-check decode (11 info bits -> 16 parity bits + 16 2-bit quotients)
    # Matching siliquant#77 hampack.py: unpack 11-bit Hamming codeword -> compute 5 parity bits -> reconstruct 16 ints
    info_gpu = torch.tensor(rng.integers(0, 2048, size=n_a16, dtype=np.int32), device=device)
    quot_gpu = torch.tensor(rng.integers(-2, 3, size=(n_a16, 16), dtype=np.int8), device=device)
    # Generator matrix G (11x16) for [16,11,4] extended Hamming (parity bit positions 0,1,2,4,8)
    data_pos = [3, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15]
    shifts = torch.arange(11, device=device, dtype=torch.int32)

    def _decode_a16_hampack_gpu(info: torch.Tensor, quot: torch.Tensor) -> torch.Tensor:
        d = (info.unsqueeze(1) >> shifts.unsqueeze(0)) & 1  # (N, 11)
        b = torch.zeros((info.shape[0], 16), device=device, dtype=torch.int32)
        for k, pos in enumerate(data_pos):
            b[:, pos] = d[:, k]
        # Compute 4 Hamming syndrome parities + 1 overall parity
        b[:, 1] = (b[:, 3] ^ b[:, 5] ^ b[:, 7] ^ b[:, 9] ^ b[:, 11] ^ b[:, 13] ^ b[:, 15])
        b[:, 2] = (b[:, 3] ^ b[:, 6] ^ b[:, 7] ^ b[:, 10] ^ b[:, 11] ^ b[:, 14] ^ b[:, 15])
        b[:, 4] = (b[:, 5] ^ b[:, 6] ^ b[:, 7] ^ b[:, 12] ^ b[:, 13] ^ b[:, 14] ^ b[:, 15])
        b[:, 8] = (b[:, 9] ^ b[:, 10] ^ b[:, 11] ^ b[:, 12] ^ b[:, 13] ^ b[:, 14] ^ b[:, 15])
        b[:, 0] = b[:, 1:16].sum(dim=1) & 1
        return (quot.to(torch.float32) * 2.0 + b.to(torch.float32))

    # Warmup + time GPU
    for _ in range(3):
        _ = _decode_eq_s3_closed_gpu(idx_gpu)
        _ = cb_eq_gpu[idx_gpu]
        _ = _decode_a16_hampack_gpu(info_gpu, quot_gpu)
    torch.cuda.synchronize()

    iters = 10
    t0 = time.monotonic()
    for _ in range(iters):
        _ = _decode_eq_s3_closed_gpu(idx_gpu)
    torch.cuda.synchronize()
    eq_closed_gpu_gws = (n_weights * iters) / (time.monotonic() - t0) / 1e9

    t0 = time.monotonic()
    for _ in range(iters):
        _ = cb_eq_gpu[idx_gpu]
    torch.cuda.synchronize()
    eq_lut_gpu_gws = (n_weights * iters) / (time.monotonic() - t0) / 1e9

    t0 = time.monotonic()
    for _ in range(iters):
        _ = _decode_a16_hampack_gpu(info_gpu, quot_gpu)
    torch.cuda.synchronize()
    a16_ham_gpu_gws = (n_weights * iters) / (time.monotonic() - t0) / 1e9

    # CPU microbenchmark (NumPy vectorized on 4M weights = 1M S^3 = 250k A_16)
    n_cpu = 4_194_304
    idx_np = rng.integers(0, 256, size=n_cpu // 4, dtype=np.uint8)
    cb_eq_np = ops.build_eq_s3_leopardi().numpy()
    info_np = rng.integers(0, 2048, size=n_cpu // 16, dtype=np.int32)
    quot_np = rng.integers(-2, 3, size=(n_cpu // 16, 16), dtype=np.int8)

    # Closed-form CPU Hopf-Hex EQ(S^3)
    b_r1_np = np.array([0.9511, 0.7937, 0.6083, 0.3088], dtype=np.float32)
    b_r2_np = np.array([0.3088, 0.6083, 0.7937, 0.9511], dtype=np.float32)
    b_n1_np = np.array([16, 10, 8, 3], dtype=np.int32)
    b_n2_np = np.array([3, 8, 10, 16], dtype=np.int32)
    b_off_np = np.array([0, 48, 128, 208], dtype=np.int32)

    t0 = time.monotonic()
    for _ in range(3):
        b = (idx_np >= 48).astype(np.int32) + (idx_np >= 128).astype(np.int32) + (idx_np >= 208).astype(np.int32)
        loc = idx_np.astype(np.int32) - b_off_np[b]
        n2 = b_n2_np[b]
        n1 = b_n1_np[b]
        i = loc // n2
        j = loc - i * n2
        p1 = -np.pi + (i + 0.5) * (2.0 * np.pi / n1)
        p2 = -np.pi + (j + (i & 1) * 0.5 + 0.25) * (2.0 * np.pi / n2)
        _ = np.stack([b_r1_np[b] * np.cos(p1), b_r1_np[b] * np.sin(p1), b_r2_np[b] * np.cos(p2), b_r2_np[b] * np.sin(p2)], axis=1)
    eq_closed_cpu_gws = (n_cpu * 3) / (time.monotonic() - t0) / 1e9

    t0 = time.monotonic()
    for _ in range(5):
        _ = cb_eq_np[idx_np]
    eq_lut_cpu_gws = (n_cpu * 5) / (time.monotonic() - t0) / 1e9

    t0 = time.monotonic()
    for _ in range(3):
        b = np.zeros((info_np.shape[0], 16), dtype=np.int32)
        for k, pos in enumerate(data_pos):
            b[:, pos] = (info_np >> k) & 1
        b[:, 1] = b[:, 3] ^ b[:, 5] ^ b[:, 7] ^ b[:, 9] ^ b[:, 11] ^ b[:, 13] ^ b[:, 15]
        b[:, 2] = b[:, 3] ^ b[:, 6] ^ b[:, 7] ^ b[:, 10] ^ b[:, 11] ^ b[:, 14] ^ b[:, 15]
        b[:, 4] = b[:, 5] ^ b[:, 6] ^ b[:, 7] ^ b[:, 12] ^ b[:, 13] ^ b[:, 14] ^ b[:, 15]
        b[:, 8] = b[:, 9] ^ b[:, 10] ^ b[:, 11] ^ b[:, 12] ^ b[:, 13] ^ b[:, 14] ^ b[:, 15]
        b[:, 0] = np.sum(b[:, 1:16], axis=1) & 1
        _ = quot_np.astype(np.float32) * 2.0 + b.astype(np.float32)
    a16_ham_cpu_gws = (n_cpu * 3) / (time.monotonic() - t0) / 1e9

    del idx_gpu, cb_eq_gpu, info_gpu, quot_gpu
    torch.cuda.empty_cache()

    res = {
        "n_weights_gpu": n_weights,
        "n_weights_cpu": n_cpu,
        "gpu_eq_s3_closed_gws": round(eq_closed_gpu_gws, 4),
        "gpu_eq_s3_l1_table_gws": round(eq_lut_gpu_gws, 4),
        "gpu_a16_hampack_gws": round(a16_ham_gpu_gws, 4),
        "gpu_closed_vs_hampack_speedup": round(eq_closed_gpu_gws / max(a16_ham_gpu_gws, 1e-9), 3),
        "cpu_eq_s3_closed_gws": round(eq_closed_cpu_gws, 4),
        "cpu_eq_s3_l1_table_gws": round(eq_lut_cpu_gws, 4),
        "cpu_a16_hampack_gws": round(a16_ham_cpu_gws, 4),
        "cpu_closed_vs_hampack_speedup": round(eq_closed_cpu_gws / max(a16_ham_cpu_gws, 1e-9), 3),
    }
    print(f"\n=== H2a PACK/DECODE THROUGHPUT (Gw/s) ===\n  {json.dumps(res)}", flush=True)
    return res


def _eval_heldout_model(
    repo_id: str,
    local_dir: str,
    pilot: dict[str, Any],
    wt_test_text: str,
    py_test_text: str,
    device: torch.device,
) -> dict[str, Any]:
    print(f"\n{'='*86}\nBLIND HELD-OUT MODEL: {repo_id}\n{'='*86}", flush=True)
    t_m0 = time.monotonic()
    tokenizer = AutoTokenizer.from_pretrained(local_dir, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        local_dir, local_files_only=True, dtype=torch.bfloat16
    ).to(device)
    model.eval()

    linears = _collect_block_linears(model)
    n_blocks = max(_layer_idx(n) for n, _ in linears) + 1
    non_block_snaps = _snapshot_non_block_tensors(model)
    orig_cpu = {n: m.weight.detach().cpu().clone() for n, m in linears}
    tot_w = sum(int(m.weight.numel()) for _, m in linears)

    wt_chunks = _tokenize_chunks(tokenizer, wt_test_text, N_EVAL_CHUNKS, SEQ_LEN)
    py_chunks = _tokenize_chunks(tokenizer, py_test_text, N_EVAL_CHUNKS, SEQ_LEN)
    ref_wt, base_wt_ppl, base_wt_energy = _collect_reference_logits(model, wt_chunks, device)
    ref_py, base_py_ppl, base_py_energy = _collect_reference_logits(model, py_chunks, device)
    print(
        f"  BF16 BASE: WikiPPL={base_wt_ppl:.4f} ({base_wt_energy['gpu_mj_per_tok']:.2f} mJ/tok GPU) | "
        f"PyPPL={base_py_ppl:.4f} ({n_blocks}L, {len(linears)} mats, {tot_w:,} wts)",
        flush=True,
    )

    # Pre-unpack frozen pilot parameters (ZERO tuning!)
    lc = pilot["locked_constants"]
    hodge_lam = float(lc["h3b_hodge_lambda_perp"])
    h3a_gamma = float(lc["h3a_gamma"])
    lm2 = torch.tensor(pilot["lm_gauss_1d"]["2"], dtype=torch.float32)
    lm3 = torch.tensor(pilot["lm_gauss_1d"]["3"], dtype=torch.float32)

    luts = {
        k: (float(v["scale_s"]), torch.tensor(v["rho"], dtype=torch.float32))
        for k, v in pilot["shell_luts"].items()
    }

    cb_num_s3 = ops.build_numerator_pi_s3(4, 8, 8)
    cb_eq_leo = ops.build_eq_s3_leopardi()
    cb_eq_hopf = ops.build_eq_s3_hopf_hex()
    cb_eq_s7_4096 = ops.build_eq_s7_haar(4096)
    cb_grav_s3 = torch.tensor(pilot["frozen_s3_codebooks"]["gravity_only_256"], dtype=torch.float32)
    cb_coul_s3 = torch.tensor(pilot["frozen_s3_codebooks"]["coulomb_256"], dtype=torch.float32)
    cb_yuk_s3 = torch.tensor(pilot["frozen_s3_codebooks"]["yukawa_256"], dtype=torch.float32)
    g_s3 = {
        cname: {rb: torch.tensor(vals, dtype=torch.float32) for rb, vals in d.items()}
        for cname, d in pilot["frozen_gain_codebooks"]["s3"].items()
    }
    g_s7_4b = torch.tensor(pilot["frozen_gain_codebooks"]["s7_eq4096_4b"], dtype=torch.float32)

    # Layer-level raw & post-SphereMap kurtosis diagnostics (computed once cleanly)
    layer_kurt_raw: dict[str, float] = {}
    layer_kurt_post: dict[str, float] = {}
    with torch.no_grad():
        for lname, _ in linears:
            wf = orig_cpu[lname].to(device=device, dtype=torch.float32)
            _, _, _, _, kr, kp = ops.spheremap_forward(wf, block_size=64)
            layer_kurt_raw[lname] = kr
            layer_kurt_post[lname] = kp
            del wf
    n_heavy_mats = sum(1 for v in layer_kurt_raw.values() if v > 10.0)
    print(
        f"  KURTOSIS DIAGNOSTIC: median_raw={np.median(list(layer_kurt_raw.values())):.2f} -> "
        f"median_post={np.median(list(layer_kurt_post.values())):.3f} | "
        f"max_raw={max(layer_kurt_raw.values()):.2f} -> max_post={max(layer_kurt_post.values()):.2f} | "
        f"heavy_mats(k>10)={n_heavy_mats}/{len(linears)}",
        flush=True,
    )

    def _run_arm(arm_name: str, quant_fn) -> dict[str, Any]:
        tot_err = tot_sig = 0.0
        typ_err = typ_sig = 0.0
        hvy_err = hvy_sig = 0.0
        bpw_num = 0.0
        syn_t = oob_t = 0
        rad_fracs: list[float] = []
        with torch.no_grad():
            for lname, mod in linears:
                wf = orig_cpu[lname].to(device=device, dtype=torch.float32)
                wq, st = quant_fn(lname, wf)
                dw = wq - wf
                e_m = float((dw * dw).sum().item())
                s_m = float((wf * wf).sum().item())
                tot_err += e_m
                tot_sig += s_m
                if layer_kurt_raw[lname] > 10.0:
                    hvy_err += e_m
                    hvy_sig += s_m
                else:
                    typ_err += e_m
                    typ_sig += s_m
                bpw_num += float(st["exact_bpw"]) * float(wf.numel())
                syn_t += int(st["syndrome_errors"])
                oob_t += int(st["oob_groups"])
                if "rad_err_frac" in st:
                    rad_fracs.append(float(st["rad_err_frac"]))
                mod.weight.copy_(wq.to(torch.bfloat16))
                del wf, wq, dw
        torch.cuda.empty_cache()
        nb_diffs = _count_non_block_diffs(model, non_block_snaps)
        wt_s = _score_against_reference(model, wt_chunks, ref_wt, device)
        py_s = _score_against_reference(model, py_chunks, ref_py, device)
        snr_all = 10.0 * math.log10(max(tot_sig, 1e-30) / max(tot_err, 1e-30))
        snr_typ = 10.0 * math.log10(max(typ_sig, 1e-30) / max(typ_err, 1e-30)) if typ_sig > 0 else snr_all
        snr_hvy = 10.0 * math.log10(max(hvy_sig, 1e-30) / max(hvy_err, 1e-30)) if hvy_sig > 0 else None
        avg_bpw = bpw_num / float(tot_w)
        row: dict[str, Any] = {
            "arm": arm_name,
            "exact_bpw": round(avg_bpw, 5),
            "weight_snr_db": round(snr_all, 4),
            "typical_layers_snr_db": round(snr_typ, 4),
            "heavy_k10_layers_snr_db": round(snr_hvy, 4) if snr_hvy is not None else None,
            "syndrome_errors": syn_t,
            "oob_groups": oob_t,
            "non_block_diffs": nb_diffs,
            "wikitext2": wt_s,
            "python": py_s,
        }
        if rad_fracs:
            row["mean_rad_err_frac"] = round(sum(rad_fracs) / len(rad_fracs), 4)
        print(
            f"  [{arm_name:30s}] bpw={avg_bpw:.4f} SNR={snr_all:6.3f}dB "
            f"(hvy={snr_hvy if snr_hvy is not None else 0.0:5.2f}) "
            f"WikiKL={wt_s['mean_kl']:.5f}±{wt_s['se_kl']:.5f} PPL={wt_s['ppl']:7.3f} "
            f"PyKL={py_s['mean_kl']:.5f}±{py_s['se_kl']:.5f} syn={syn_t} oob={oob_t} nb={nb_diffs}",
            flush=True,
        )
        return row

    def _sp_wrap(fn):
        def _inner(_n, wf):
            w_sp, dr, dc, ex, _, _ = ops.spheremap_forward(wf, block_size=64)
            wq_sp, st = fn(w_sp, ex)
            return ops.spheremap_inverse(wq_sp, dr, dc, block_size=64), st
        return _inner

    def _null_shuffle_sp_wrap(fn):
        def _inner(lname, wf):
            perm = ops.make_null_shuffle_perm(wf.shape, f"{repo_id}:{lname}:null_shuffle", wf.device)
            wf_shuf = wf.reshape(-1)[perm].reshape(wf.shape)
            w_sp, dr, dc, ex, _, _ = ops.spheremap_forward(wf_shuf, block_size=64)
            wq_sp, st = fn(w_sp, ex)
            wq_shuf = ops.spheremap_inverse(wq_sp, dr, dc, block_size=64)
            inv = torch.empty_like(perm)
            inv[perm] = torch.arange(perm.numel(), device=wf.device, dtype=perm.dtype)
            wq = wq_shuf.reshape(-1)[inv].reshape(wf.shape)
            return wq, st
        return _inner

    arms: dict[str, Any] = {}

    # --- H1: Per-block siliquant baselines (2.0, 3.0, 4.5 bpw) ---
    arms["p128_A16_2b"] = _run_arm("p128_A16_2b", lambda _n, wf: ops.quant_per_block_ball_matrix(wf, "2.0", "A16", 128, row_chunk=512))
    arms["p128_A16_3b"] = _run_arm("p128_A16_3b", lambda _n, wf: ops.quant_per_block_ball_matrix(wf, "3.0", "A16", 128, row_chunk=512))
    arms["p128_A16_45b"] = _run_arm("p128_A16_45b", lambda _n, wf: ops.quant_per_block_ball_matrix(wf, "4.5", "A16", 128, row_chunk=512))
    arms["p128_E8_3b"] = _run_arm("p128_E8_3b", lambda _n, wf: ops.quant_per_block_ball_matrix(wf, "3.0", "E8", 128, row_chunk=512))
    arms["p32_A16_3b"] = _run_arm("p32_A16_3b", lambda _n, wf: ops.quant_per_block_ball_matrix(wf, "3.0", "A16", 32, row_chunk=512))

    # --- H1: Cartesian Lloyd-Max + SphereMap controls ---
    arms["sp_CartLM_2b"] = _run_arm("sp_CartLM_2b", _sp_wrap(lambda wsp, ex: ops.quant_cartesian_lloyd_max_matrix(wsp, lm2, 2, extra_bpw=ex)))
    arms["sp_CartLM_3b"] = _run_arm("sp_CartLM_3b", _sp_wrap(lambda wsp, ex: ops.quant_cartesian_lloyd_max_matrix(wsp, lm3, 3, extra_bpw=ex)))

    # --- H1: SphereMap + Hypersphere hierarchy E_8 (S^7) -> A_16 (S^15) -> A_16^8 (S^127) ---
    arms["sp_E8_lin_2b"] = _run_arm("sp_E8_lin_2b", _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(wsp, "E8", "2.0", extra_bpw=ex)))
    arms["sp_E8_lin_3b"] = _run_arm("sp_E8_lin_3b", _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(wsp, "E8", "3.0", extra_bpw=ex)))
    arms["sp_E8_lin_45b"] = _run_arm("sp_E8_lin_45b", _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(wsp, "E8", "4.5", extra_bpw=ex)))

    arms["sp_A16_lin_2b"] = _run_arm("sp_A16_lin_2b", _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(wsp, "A16", "2.0", extra_bpw=ex)))
    arms["sp_A16_lin_3b"] = _run_arm("sp_A16_lin_3b", _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(wsp, "A16", "3.0", extra_bpw=ex)))
    arms["sp_A16_lin_45b"] = _run_arm("sp_A16_lin_45b", _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(wsp, "A16", "4.5", extra_bpw=ex)))

    arms["sp_A16_128_2b"] = _run_arm("sp_A16_128_2b", _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(wsp, "A16_128", "2.0", extra_bpw=ex)))
    arms["sp_A16_128_3b"] = _run_arm("sp_A16_128_3b", _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(wsp, "A16_128", "3.0", extra_bpw=ex)))
    arms["sp_A16_128_B368_290b"] = _run_arm("sp_A16_128_B368_290b", _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(wsp, "A16_128_B368", "3.0", extra_bpw=ex)))
    arms["sp_A16_128_45b"] = _run_arm("sp_A16_128_45b", _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(wsp, "A16_128", "4.5", extra_bpw=ex)))

    # --- H1 Control 3: Adversarial Null Shuffle before SphereMap ---
    arms["null_shuffle_sp_A16_3b"] = _run_arm(
        "null_shuffle_sp_A16_3b",
        _null_shuffle_sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(wsp, "A16", "3.0", extra_bpw=ex)),
    )

    # --- H2a & H3c: S^3 (K=256) & S^7 (K=4096) at 2.0 & 2.5 bpw ---
    cb_bytes_256x4 = 256 * 4 * 2  # FP16 stored codebook bytes for trained k-means/Coulomb/Yukawa (0 for analytical EQ!)
    arms["sp_s3_numpi_2b"] = _run_arm(
        "sp_s3_numpi_2b",
        _sp_wrap(lambda wsp, ex: ops.quant_spherical_codebook_matrix(
            wsp, cb_num_s3, g_s3["num_pi"]["0b"], rad_bits=0, extra_bpw=ex, codebook_stored_bytes=0, total_model_weights=tot_w
        )),
    )
    arms["sp_s3_eq_leo_2b"] = _run_arm(
        "sp_s3_eq_leo_2b",
        _sp_wrap(lambda wsp, ex: ops.quant_spherical_codebook_matrix(
            wsp, cb_eq_leo, g_s3["eq_s3_leo"]["0b"], rad_bits=0, extra_bpw=ex, codebook_stored_bytes=0, total_model_weights=tot_w
        )),
    )
    arms["sp_s3_eq_hopf_2b"] = _run_arm(
        "sp_s3_eq_hopf_2b",
        _sp_wrap(lambda wsp, ex: ops.quant_spherical_codebook_matrix(
            wsp, cb_eq_hopf, g_s3["eq_s3_hopf"]["0b"], rad_bits=0, extra_bpw=ex, codebook_stored_bytes=0, total_model_weights=tot_w
        )),
    )
    arms["sp_s3_kmeans_2b"] = _run_arm(
        "sp_s3_kmeans_2b",
        _sp_wrap(lambda wsp, ex: ops.quant_spherical_codebook_matrix(
            wsp, cb_grav_s3, g_s3["gravity_only"]["0b"], rad_bits=0, extra_bpw=ex, codebook_stored_bytes=cb_bytes_256x4, total_model_weights=tot_w
        )),
    )
    arms["sp_s3_coulomb_2b"] = _run_arm(
        "sp_s3_coulomb_2b",
        _sp_wrap(lambda wsp, ex: ops.quant_spherical_codebook_matrix(
            wsp, cb_coul_s3, g_s3["coulomb"]["0b"], rad_bits=0, extra_bpw=ex, codebook_stored_bytes=cb_bytes_256x4, total_model_weights=tot_w
        )),
    )
    arms["sp_s3_yukawa_2b"] = _run_arm(
        "sp_s3_yukawa_2b",
        _sp_wrap(lambda wsp, ex: ops.quant_spherical_codebook_matrix(
            wsp, cb_yuk_s3, g_s3["yukawa"]["0b"], rad_bits=0, extra_bpw=ex, codebook_stored_bytes=cb_bytes_256x4, total_model_weights=tot_w
        )),
    )
    arms["sp_s7_eq4096_2b"] = _run_arm(
        "sp_s7_eq4096_2b",
        _sp_wrap(lambda wsp, ex: ops.quant_spherical_codebook_matrix(
            wsp, cb_eq_s7_4096, g_s7_4b, rad_bits=4, extra_bpw=ex, codebook_stored_bytes=0, total_model_weights=tot_w, chunk_vecs=16384
        )),
    )

    # 2.50 bpw (K=256 + 2b gain on S^3) for H2a & H3c
    arms["sp_s3_numpi_25b"] = _run_arm(
        "sp_s3_numpi_25b",
        _sp_wrap(lambda wsp, ex: ops.quant_spherical_codebook_matrix(
            wsp, cb_num_s3, g_s3["num_pi"]["2b"], rad_bits=2, extra_bpw=ex, codebook_stored_bytes=0, total_model_weights=tot_w
        )),
    )
    arms["sp_s3_eq_leo_25b"] = _run_arm(
        "sp_s3_eq_leo_25b",
        _sp_wrap(lambda wsp, ex: ops.quant_spherical_codebook_matrix(
            wsp, cb_eq_leo, g_s3["eq_s3_leo"]["2b"], rad_bits=2, extra_bpw=ex, codebook_stored_bytes=0, total_model_weights=tot_w
        )),
    )
    arms["sp_s3_kmeans_25b"] = _run_arm(
        "sp_s3_kmeans_25b",
        _sp_wrap(lambda wsp, ex: ops.quant_spherical_codebook_matrix(
            wsp, cb_grav_s3, g_s3["gravity_only"]["2b"], rad_bits=2, extra_bpw=ex, codebook_stored_bytes=cb_bytes_256x4, total_model_weights=tot_w
        )),
    )
    arms["sp_s3_coulomb_25b"] = _run_arm(
        "sp_s3_coulomb_25b",
        _sp_wrap(lambda wsp, ex: ops.quant_spherical_codebook_matrix(
            wsp, cb_coul_s3, g_s3["coulomb"]["2b"], rad_bits=2, extra_bpw=ex, codebook_stored_bytes=cb_bytes_256x4, total_model_weights=tot_w
        )),
    )
    arms["sp_s3_yukawa_25b"] = _run_arm(
        "sp_s3_yukawa_25b",
        _sp_wrap(lambda wsp, ex: ops.quant_spherical_codebook_matrix(
            wsp, cb_yuk_s3, g_s3["yukawa"]["2b"], rad_bits=2, extra_bpw=ex, codebook_stored_bytes=cb_bytes_256x4, total_model_weights=tot_w
        )),
    )

    # --- H3a: Power-0.7 Radial Sphere Warp + Zero-Bit Integer Shell-LUT ---
    s_e8_2, lut_e8_2 = luts["E8_2.0_power07"]
    s_e8_3, lut_e8_3 = luts["E8_3.0_power07"]
    s_a16_3, lut_a16_3 = luts["A16_3.0_power07"]
    arms["sp_E8_pow07_2b"] = _run_arm(
        "sp_E8_pow07_2b",
        _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(
            wsp, "E8", "2.0", gamma=h3a_gamma, scale_s=s_e8_2, shell_lut=lut_e8_2, extra_bpw=ex
        )),
    )
    arms["sp_E8_pow07_3b"] = _run_arm(
        "sp_E8_pow07_3b",
        _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(
            wsp, "E8", "3.0", gamma=h3a_gamma, scale_s=s_e8_3, shell_lut=lut_e8_3, extra_bpw=ex
        )),
    )
    arms["sp_A16_pow07_3b"] = _run_arm(
        "sp_A16_pow07_3b",
        _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(
            wsp, "A16", "3.0", gamma=h3a_gamma, scale_s=s_a16_3, shell_lut=lut_a16_3, extra_bpw=ex
        )),
    )

    # --- H3b: EM/Hodge Transverse-Weighted Selection (locked lambda_perp=2.0) ---
    arms["sp_E8_hodge_3b"] = _run_arm(
        "sp_E8_hodge_3b",
        _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(
            wsp, "E8", "3.0", hodge_lambda_perp=hodge_lam, extra_bpw=ex
        )),
    )
    arms["sp_A16_hodge_3b"] = _run_arm(
        "sp_A16_hodge_3b",
        _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(
            wsp, "A16", "3.0", hodge_lambda_perp=hodge_lam, extra_bpw=ex
        )),
    )

    # --- H4: Conjunction (Frozen Phase-1B Winners: A16^8+Hodge & A16+Pow07+Hodge) ---
    arms["h4_sp_A16_pow07_hodge_3b"] = _run_arm(
        "h4_sp_A16_pow07_hodge_3b",
        _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(
            wsp, "A16", "3.0", gamma=h3a_gamma, scale_s=s_a16_3, shell_lut=lut_a16_3,
            hodge_lambda_perp=hodge_lam, extra_bpw=ex
        )),
    )
    arms["h4_sp_A16_128_hodge_2b"] = _run_arm(
        "h4_sp_A16_128_hodge_2b",
        _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(
            wsp, "A16_128", "2.0", hodge_lambda_perp=hodge_lam, extra_bpw=ex
        )),
    )
    arms["h4_sp_A16_128_hodge_3b"] = _run_arm(
        "h4_sp_A16_128_hodge_3b",
        _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(
            wsp, "A16_128", "3.0", hodge_lambda_perp=hodge_lam, extra_bpw=ex
        )),
    )
    arms["h4_sp_A16_128_hodge_45b"] = _run_arm(
        "h4_sp_A16_128_hodge_45b",
        _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(
            wsp, "A16_128", "4.5", hodge_lambda_perp=hodge_lam, extra_bpw=ex
        )),
    )

    # --- H1-P2: Exact Per-Layer Spearman rho(kappa_post - 3, single-layer KL degradation) ---
    # Restore clean BF16 weights first, then quantize ONE layer at a time with SphereMap + E_8 (3.0b)
    with torch.no_grad():
        for lname, mod in linears:
            mod.weight.copy_(orig_cpu[lname].to(device=device, dtype=torch.bfloat16))
    probe_chunks = wt_chunks[:N_LAYER_PROBE_CHUNKS]
    probe_ref = ref_wt[:N_LAYER_PROBE_CHUNKS]
    by_layer: dict[int, list[tuple[str, torch.nn.Linear]]] = {i: [] for i in range(n_blocks)}
    for lname, mod in linears:
        by_layer[_layer_idx(lname)].append((lname, mod))

    per_layer_diag: list[dict[str, Any]] = []
    for li in range(n_blocks):
        mods = by_layer[li]
        k_posts = [layer_kurt_post[ln] - 3.0 for ln, _ in mods]
        k_raws = [layer_kurt_raw[ln] - 3.0 for ln, _ in mods]
        with torch.no_grad():
            for ln, m in mods:
                wf = orig_cpu[ln].to(device=device, dtype=torch.float32)
                w_sp, dr, dc, ex, _, _ = ops.spheremap_forward(wf, block_size=64)
                wq_sp, _ = ops.quant_global_ball_matrix(w_sp, "E8", "3.0", extra_bpw=ex)
                wq = ops.spheremap_inverse(wq_sp, dr, dc, block_size=64)
                m.weight.copy_(wq.to(torch.bfloat16))
                del wf, w_sp, wq_sp, wq
        sc = _score_against_reference(model, probe_chunks, probe_ref, device)
        with torch.no_grad():
            for ln, m in mods:
                m.weight.copy_(orig_cpu[ln].to(device=device, dtype=torch.bfloat16))
        per_layer_diag.append({
            "layer": li,
            "mean_excess_k_raw": round(float(np.mean(k_raws)), 4),
            "mean_excess_k_post": round(float(np.mean(k_posts)), 4),
            "max_excess_k_post": round(float(np.max(k_posts)), 4),
            "single_layer_wiki_kl": sc["mean_kl"],
        })

    arr_k_mean = [r["mean_excess_k_post"] for r in per_layer_diag]
    arr_k_max = [r["max_excess_k_post"] for r in per_layer_diag]
    arr_kl = [r["single_layer_wiki_kl"] for r in per_layer_diag]
    rho_mean, p_mean = spearmanr(arr_k_mean, arr_kl)
    rho_max, p_max = spearmanr(arr_k_max, arr_kl)
    print(
        f"  [H1-P2 PER-LAYER SPEARMAN ({n_blocks}L)] rho(mean k_post-3, KL)={rho_mean:+.4f} (p={p_mean:.3e}) | "
        f"rho(max k_post-3, KL)={rho_max:+.4f} (p={p_max:.3e})",
        flush=True,
    )

    out = {
        "repo_id": repo_id,
        "num_hidden_layers": n_blocks,
        "block_linear_matrices": len(linears),
        "total_block_weights": tot_w,
        "heavy_k10_matrices": n_heavy_mats,
        "non_block_tensors_protected": len(non_block_snaps),
        "reference_bf16": {
            "wikitext2_ppl": round(base_wt_ppl, 6),
            "python_ppl": round(base_py_ppl, 6),
            "wikitext2_energy": base_wt_energy,
            "python_energy": base_py_energy,
        },
        "kurtosis_summary": {
            "median_raw": round(float(np.median(list(layer_kurt_raw.values()))), 4),
            "median_post": round(float(np.median(list(layer_kurt_post.values()))), 4),
            "max_raw": round(float(max(layer_kurt_raw.values())), 4),
            "max_post": round(float(max(layer_kurt_post.values())), 4),
        },
        "h1_p2_per_layer_kurtosis_vs_kl": {
            "spearman_rho_mean_excess_k": round(float(rho_mean), 6),
            "spearman_p_mean_excess_k": round(float(p_mean), 8),
            "spearman_rho_max_excess_k": round(float(rho_max), 6),
            "spearman_p_max_excess_k": round(float(p_max), 8),
            "layers": per_layer_diag,
        },
        "arms": arms,
        "model_elapsed_seconds": round(time.monotonic() - t_m0, 3),
    }
    del model, ref_wt, ref_py, orig_cpu
    gc.collect()
    torch.cuda.empty_cache()
    return out


def _grade_preregistered_verdicts(
    models_out: dict[str, Any], throughput: dict[str, Any]
) -> dict[str, Any]:
    """Strictly and honestly grade H1, H2a, H3a, H3b, H3c, H4 against locked PREREG_SPHERE_PI_FORCES_V1.md."""
    mnames = list(models_out.keys())

    def _sig_better_kl(a: dict[str, Any], b: dict[str, Any], rel_thresh: float) -> tuple[bool, float]:
        # Require BOTH corpora (wikitext2 & python) to improve by >= rel_thresh AND >= 2 combined SE!
        ok_both = True
        min_rel = 1e9
        for dom in ("wikitext2", "python"):
            ka, sa = a[dom]["mean_kl"], a[dom]["se_kl"]
            kb, sb = b[dom]["mean_kl"], b[dom]["se_kl"]
            rel = (kb - ka) / max(kb, 1e-12)
            se_comb = math.hypot(sa, sb)
            z = (kb - ka) / max(se_comb, 1e-12)
            min_rel = min(min_rel, rel)
            if not (rel >= rel_thresh and z >= 2.0):
                ok_both = False
        return ok_both, round(min_rel, 6)

    # H1-P1: SphereMap + A16/E8/A16^8 beats p128_A16_3b by >=10% KL (>=2 SE) OR matches KL at >=0.10 bpw lower
    h1_p1_wins = 0
    h1_p1_details = {}
    for m in mnames:
        arms = models_out[m]["arms"]
        base = arms["p128_A16_3b"]
        best_sp = min(
            (arms["sp_E8_lin_3b"], arms["sp_A16_lin_3b"], arms["sp_A16_128_3b"]),
            key=lambda r: 0.5 * (r["wikitext2"]["mean_kl"] + r["python"]["mean_kl"]),
        )
        ok_kl, min_rel = _sig_better_kl(best_sp, base, 0.10)
        low_b = arms["sp_A16_128_B368_290b"]
        bpw_save = base["exact_bpw"] - low_b["exact_bpw"]
        matches_kl = all(
            low_b[d]["mean_kl"] <= base[d]["mean_kl"] + 2.0 * math.hypot(low_b[d]["se_kl"], base[d]["se_kl"])
            for d in ("wikitext2", "python")
        )
        ok_bpw = (bpw_save >= 0.099) and matches_kl
        passed = ok_kl or ok_bpw
        if passed:
            h1_p1_wins += 1
        h1_p1_details[m] = {
            "best_sp_arm": best_sp["arm"],
            "best_sp_wiki_kl": best_sp["wikitext2"]["mean_kl"],
            "p128_wiki_kl": base["wikitext2"]["mean_kl"],
            "best_sp_snr_db": best_sp["weight_snr_db"],
            "p128_snr_db": base["weight_snr_db"],
            "min_kl_rel_gain": min_rel,
            "ok_kl_10pct": ok_kl,
            "ok_bpw_010": ok_bpw,
            "passed": passed,
        }
    h1_p1_verdict = "CONFIRMED" if h1_p1_wins >= 2 else "FALSIFIED"

    # H1-P2: Spearman rho >= 0.60 across layers of each model
    h1_p2_wins = 0
    h1_p2_details = {}
    for m in mnames:
        d = models_out[m]["h1_p2_per_layer_kurtosis_vs_kl"]
        r_m = d["spearman_rho_mean_excess_k"]
        r_x = d["spearman_rho_max_excess_k"]
        ok = max(r_m, r_x) >= 0.60
        if ok:
            h1_p2_wins += 1
        h1_p2_details[m] = {"rho_mean": r_m, "rho_max": r_x, "passed": ok}
    h1_p2_verdict = "CONFIRMED" if h1_p2_wins >= 2 else ("PARTIAL" if h1_p2_wins == 1 else "FALSIFIED")
    h1_verdict = "CONFIRMED" if (h1_p1_verdict == "CONFIRMED" and h1_p2_verdict == "CONFIRMED") else (
        "PARTIAL" if (h1_p1_verdict == "CONFIRMED" or h1_p2_verdict == "CONFIRMED") else "FALSIFIED"
    )

    # H2a: EQ(S^3) beats Num-pi by >= +1.5 dB, within 0.10 dB of 20-iter k-means (kill if trails >0.15 dB
    # OR loses in held-out KL to CartLM + SphereMap at 2.0 bpw), and faster pack/decode than hampack
    h2a_details = {}
    h2a_pass_count = 0
    for m in mnames:
        arms = models_out[m]["arms"]
        eq2 = arms["sp_s3_eq_leo_2b"]
        np2 = arms["sp_s3_numpi_2b"]
        km2 = arms["sp_s3_kmeans_2b"]
        clm2 = arms["sp_CartLM_2b"]
        eq25 = arms["sp_s3_eq_leo_25b"]
        np25 = arms["sp_s3_numpi_25b"]
        km25 = arms["sp_s3_kmeans_25b"]

        gain_vs_numpi_25 = eq25["weight_snr_db"] - np25["weight_snr_db"]
        gain_vs_numpi_20 = eq2["weight_snr_db"] - np2["weight_snr_db"]
        gap_vs_km_25 = eq25["weight_snr_db"] - km25["weight_snr_db"]
        gap_vs_km_20 = eq2["weight_snr_db"] - km2["weight_snr_db"]
        beats_clm_kl = all(eq2[d]["mean_kl"] < clm2[d]["mean_kl"] for d in ("wikitext2", "python"))
        ok_m = (
            max(gain_vs_numpi_25, gain_vs_numpi_20) >= 1.5
            and min(gap_vs_km_25, gap_vs_km_20) >= -0.15
            and beats_clm_kl
        )
        if ok_m:
            h2a_pass_count += 1
        h2a_details[m] = {
            "snr_gain_vs_numpi_2b_db": round(gain_vs_numpi_20, 4),
            "snr_gain_vs_numpi_25b_db": round(gain_vs_numpi_25, 4),
            "snr_diff_vs_kmeans_2b_db": round(gap_vs_km_20, 4),
            "snr_diff_vs_kmeans_25b_db": round(gap_vs_km_25, 4),
            "eq_2b_wiki_kl": eq2["wikitext2"]["mean_kl"],
            "cartlm_2b_wiki_kl": clm2["wikitext2"]["mean_kl"],
            "eq_2b_py_kl": eq2["python"]["mean_kl"],
            "cartlm_2b_py_kl": clm2["python"]["mean_kl"],
            "beats_cartlm_kl_2b": beats_clm_kl,
            "passed": ok_m,
        }
    faster_decode = throughput["gpu_closed_vs_hampack_speedup"] > 1.0
    if h2a_pass_count >= 2 and faster_decode:
        h2a_verdict = "CONFIRMED"
    elif any(d["snr_diff_vs_kmeans_25b_db"] >= -0.10 for d in h2a_details.values()):
        h2a_verdict = "PARTIAL"
    else:
        h2a_verdict = "FALSIFIED"

    # H3a: Power-0.7 + Shell-LUT at 3.0 bpw: >= +0.15 dB typical, >= +0.40 dB heavy (k>10), AND >= 3% KL (>=2 SE)
    h3a_details = {}
    h3a_snr_wins = 0
    h3a_kl_wins = 0
    h3a_full_wins = 0
    for m in mnames:
        arms = models_out[m]["arms"]
        # Check on BOTH E8 and A16 (report both cleanly!)
        e_lin, e_p07 = arms["sp_E8_lin_3b"], arms["sp_E8_pow07_3b"]
        a_lin, a_p07 = arms["sp_A16_lin_3b"], arms["sp_A16_pow07_3b"]
        e_typ_d = e_p07["typical_layers_snr_db"] - e_lin["typical_layers_snr_db"]
        e_hvy_d = (
            (e_p07["heavy_k10_layers_snr_db"] - e_lin["heavy_k10_layers_snr_db"])
            if (e_p07["heavy_k10_layers_snr_db"] is not None and e_lin["heavy_k10_layers_snr_db"] is not None)
            else None
        )
        a_typ_d = a_p07["typical_layers_snr_db"] - a_lin["typical_layers_snr_db"]
        a_hvy_d = (
            (a_p07["heavy_k10_layers_snr_db"] - a_lin["heavy_k10_layers_snr_db"])
            if (a_p07["heavy_k10_layers_snr_db"] is not None and a_lin["heavy_k10_layers_snr_db"] is not None)
            else None
        )
        e_ok_kl, e_min_rel = _sig_better_kl(e_p07, e_lin, 0.03)
        a_ok_kl, a_min_rel = _sig_better_kl(a_p07, a_lin, 0.03)
        ok_snr = (e_typ_d >= 0.15 and (e_hvy_d is None or e_hvy_d >= 0.40)) or (
            a_typ_d >= 0.15 and (a_hvy_d is None or a_hvy_d >= 0.40)
        )
        ok_kl = e_ok_kl or a_ok_kl
        if ok_snr:
            h3a_snr_wins += 1
        if ok_kl:
            h3a_kl_wins += 1
        if ok_snr and ok_kl:
            h3a_full_wins += 1
        h3a_details[m] = {
            "e8_typ_snr_delta_db": round(e_typ_d, 4),
            "e8_hvy_snr_delta_db": round(e_hvy_d, 4) if e_hvy_d is not None else None,
            "e8_kl_min_rel_gain": e_min_rel,
            "e8_ok_kl_3pct": e_ok_kl,
            "a16_typ_snr_delta_db": round(a_typ_d, 4),
            "a16_hvy_snr_delta_db": round(a_hvy_d, 4) if a_hvy_d is not None else None,
            "a16_kl_min_rel_gain": a_min_rel,
            "a16_ok_kl_3pct": a_ok_kl,
            "ok_snr": ok_snr,
            "ok_kl": ok_kl,
        }
    if h3a_full_wins >= 2:
        h3a_verdict = "CONFIRMED"
    elif h3a_snr_wins >= 2 or h3a_kl_wins >= 2:
        h3a_verdict = "PARTIAL"
    else:
        h3a_verdict = "FALSIFIED"

    # H3b: EM/Hodge Transverse-Weighted Selection cuts KL >= 3% (>= 2 SE) at identical exact_bpw
    h3b_details = {}
    h3b_wins = 0
    for m in mnames:
        arms = models_out[m]["arms"]
        e_ok, e_rel = _sig_better_kl(arms["sp_E8_hodge_3b"], arms["sp_E8_lin_3b"], 0.03)
        a_ok, a_rel = _sig_better_kl(arms["sp_A16_hodge_3b"], arms["sp_A16_lin_3b"], 0.03)
        ok = e_ok or a_ok
        if ok:
            h3b_wins += 1
        h3b_details[m] = {
            "e8_kl_min_rel_gain": e_rel,
            "e8_ok_3pct": e_ok,
            "a16_kl_min_rel_gain": a_rel,
            "a16_ok_3pct": a_ok,
            "passed": ok,
        }
    h3b_verdict = "CONFIRMED" if h3b_wins >= 2 else ("PARTIAL" if h3b_wins == 1 else "FALSIFIED")

    # H3c: Yukawa strictly beats BOTH Gravity-only AND Coulomb in SNR (>= +0.05 dB) & KL (>= 2 SE) at 2.0-2.5 bpw
    h3c_details = {}
    h3c_snr_wins = 0
    h3c_full_wins = 0
    for m in mnames:
        arms = models_out[m]["arms"]
        yk, km, cl = arms["sp_s3_yukawa_25b"], arms["sp_s3_kmeans_25b"], arms["sp_s3_coulomb_25b"]
        d_km = yk["weight_snr_db"] - km["weight_snr_db"]
        d_cl = yk["weight_snr_db"] - cl["weight_snr_db"]
        ok_snr = (d_km >= 0.05) and (d_cl >= 0.05)
        ok_kl_km, rel_km = _sig_better_kl(yk, km, 0.0)
        ok_kl_cl, rel_cl = _sig_better_kl(yk, cl, 0.0)
        if ok_snr:
            h3c_snr_wins += 1
        if ok_snr and ok_kl_km and ok_kl_cl:
            h3c_full_wins += 1
        h3c_details[m] = {
            "snr_vs_kmeans_25b_db": round(d_km, 4),
            "snr_vs_coulomb_25b_db": round(d_cl, 4),
            "kl_rel_vs_kmeans_25b": rel_km,
            "kl_rel_vs_coulomb_25b": rel_cl,
            "ok_snr_005db": ok_snr,
            "ok_kl_2se_both": ok_kl_km and ok_kl_cl,
        }
    h3c_verdict = "CONFIRMED" if h3c_full_wins >= 2 else ("PARTIAL" if h3c_snr_wins >= 2 else "FALSIFIED")

    # H4: Conjunction strictly Pareto-dominates every individual ablation AND per-128 siliquant baseline
    h4_details = {}
    h4_beats_all_sp = 0
    h4_beats_p128 = 0
    for m in mnames:
        arms = models_out[m]["arms"]
        conj = arms["h4_sp_A16_128_hodge_3b"]
        base_p128 = arms["p128_A16_3b"]
        indiv = [arms["sp_E8_lin_3b"], arms["sp_E8_pow07_3b"], arms["sp_E8_hodge_3b"],
                 arms["sp_A16_lin_3b"], arms["sp_A16_pow07_3b"], arms["sp_A16_hodge_3b"],
                 arms["sp_A16_128_3b"]]
        conj_kl = 0.5 * (conj["wikitext2"]["mean_kl"] + conj["python"]["mean_kl"])
        best_indiv = min(indiv, key=lambda r: 0.5 * (r["wikitext2"]["mean_kl"] + r["python"]["mean_kl"]))
        best_indiv_kl = 0.5 * (best_indiv["wikitext2"]["mean_kl"] + best_indiv["python"]["mean_kl"])
        p128_kl = 0.5 * (base_p128["wikitext2"]["mean_kl"] + base_p128["python"]["mean_kl"])
        b_sp = conj_kl < best_indiv_kl
        b_p128 = conj_kl < p128_kl
        if b_sp:
            h4_beats_all_sp += 1
        if b_p128:
            h4_beats_p128 += 1
        h4_details[m] = {
            "conj_avg_kl": round(conj_kl, 6),
            "best_sp_indiv_arm": best_indiv["arm"],
            "best_sp_indiv_avg_kl": round(best_indiv_kl, 6),
            "p128_A16_3b_avg_kl": round(p128_kl, 6),
            "beats_all_sp_indiv": b_sp,
            "beats_p128_baseline": b_p128,
        }
    if h4_beats_all_sp >= 2 and h4_beats_p128 >= 2:
        h4_verdict = "CONFIRMED"
    elif h4_beats_all_sp >= 2:
        h4_verdict = "PARTIAL"
    else:
        h4_verdict = "FALSIFIED"

    return {
        "H1": {"verdict": h1_verdict, "H1_P1": h1_p1_verdict, "H1_P2": h1_p2_verdict, "p1_details": h1_p1_details, "p2_details": h1_p2_details},
        "H2a": {"verdict": h2a_verdict, "faster_decode_than_hampack": faster_decode, "details": h2a_details},
        "H3a": {"verdict": h3a_verdict, "details": h3a_details},
        "H3b": {"verdict": h3b_verdict, "details": h3b_details},
        "H3c": {"verdict": h3c_verdict, "details": h3c_details},
        "H4": {"verdict": h4_verdict, "details": h4_details},
    }


def main() -> int:
    t_start = time.monotonic()
    torch.manual_seed(EVAL_SEED)
    device = torch.device("cuda:0")
    here = Path(__file__).resolve().parent

    # Verify locked preregistration & locked pilot params BEFORE touching any held-out model!
    prereg_path = here.parent.parent / "notes" / "sphere_pi_forces_2026_11_25" / "PREREG_SPHERE_PI_FORCES_V1.md"
    prereg_sha = hashlib.sha256(prereg_path.read_bytes()).hexdigest()
    if prereg_sha != ops.PREREG_SHA256:
        raise RuntimeError(f"Preregistration SHA mismatch: {prereg_sha}")

    pilot_path = here / "s106_frozen_pilot_params.json"
    pilot_raw = pilot_path.read_bytes()
    pilot_file_sha = hashlib.sha256(pilot_raw).hexdigest()
    pilot = json.loads(pilot_raw.decode("utf-8"))
    if pilot.get("preregistration_sha256") != ops.PREREG_SHA256:
        raise RuntimeError("Pilot params preregistration_sha256 mismatch")
    if pilot.get("held_out_models_touched") != []:
        raise RuntimeError("Pilot params touched held-out models!")

    ac_pre = Path("/sys/class/power_supply/AC0/online").read_text(encoding="utf-8").strip()
    if ac_pre != "1":
        raise RuntimeError("AC power must be online before sustained RTX 3080 gauntlet")

    s49b_cache = Path.home() / ".cache" / "huggingface" / "s49b_eval"
    s60_cache = Path.home() / ".cache" / "huggingface" / "s60_eval"
    s63_cache = Path.home() / ".cache" / "huggingface" / "s63_eval"
    s49b_pins = json.loads((s49b_cache / "pins.json").read_text(encoding="utf-8"))
    q15_pin = json.loads((s60_cache / "qwen15b_pin.json").read_text(encoding="utf-8"))
    q3_pin = json.loads((s63_cache / "qwen3b_pin.json").read_text(encoding="utf-8"))

    wt_test_text = (s49b_cache / "wikitext2_test.txt").read_text(encoding="utf-8")
    py_test_text, py_sha = _load_python_eval_text()

    smi_pre = _query_nvidia_smi()
    rapl_max = _read_rapl_max_range_uj()
    rapl_start = _read_rapl_pkg_uj()

    throughput = _benchmark_pack_decode_throughput(device)

    models_out: dict[str, Any] = {}
    for repo_id, local_dir in (
        ("HuggingFaceTB/SmolLM2-360M", s49b_pins["HuggingFaceTB/SmolLM2-360M"]["local_dir"]),
        ("Qwen/Qwen2.5-1.5B", q15_pin["local_dir"]),
        ("Qwen/Qwen2.5-3B", q3_pin["local_dir"]),
    ):
        models_out[repo_id] = _eval_heldout_model(
            repo_id, local_dir, pilot, wt_test_text, py_test_text, device
        )

    rapl_end = _read_rapl_pkg_uj()
    smi_post = _query_nvidia_smi()
    ac_post = Path("/sys/class/power_supply/AC0/online").read_text(encoding="utf-8").strip()

    verdicts = _grade_preregistered_verdicts(models_out, throughput)

    # Check global zero-error invariants
    tot_syn = sum(a["syndrome_errors"] for m in models_out.values() for a in m["arms"].values())
    tot_oob = sum(a["oob_groups"] for m in models_out.values() for a in m["arms"].values())
    tot_nb = sum(a["non_block_diffs"] for m in models_out.values() for a in m["arms"].values())

    payload: dict[str, Any] = {
        "schema": "aletheia.track_s106.blind_gauntlet_results.v1",
        "oracle_class": "anchor",
        "preregistration_sha256": prereg_sha,
        "pilot_params_file_sha256": pilot_file_sha,
        "pilot_params_inner_sha256": pilot["pilot_params_sha256"],
        "pilot_locked_utc": pilot["locked_utc"],
        "gauntlet_completed_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "eval_seed": EVAL_SEED,
        "ac_online": (ac_pre == "1" and ac_post == "1"),
        "corpora": {
            "wikitext2_test_sha256": s49b_pins["wikitext2"]["test_sha256"],
            "python_stdlib_modules": list(STDLIB_PY_MODULES),
            "python_stdlib_sha256": py_sha,
            "seq_len": SEQ_LEN,
            "n_eval_chunks": N_EVAL_CHUNKS,
            "n_layer_probe_chunks": N_LAYER_PROBE_CHUNKS,
        },
        "global_integrity": {
            "total_arms_evaluated": sum(len(m["arms"]) for m in models_out.values()),
            "total_syndrome_errors": tot_syn,
            "total_oob_groups": tot_oob,
            "total_non_block_diffs": tot_nb,
        },
        "h2a_pack_decode_throughput": throughput,
        "models": models_out,
        "preregistered_verdicts": verdicts,
        "total_cpu_rapl_joules": _rapl_delta_joules(rapl_start, rapl_end, rapl_max),
        "nvidia_smi_pre": smi_pre,
        "nvidia_smi_post": smi_post,
        "elapsed_seconds": round(time.monotonic() - t_start, 3),
    }

    canon_payload = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["result_sha256"] = hashlib.sha256(canon_payload).hexdigest()

    out_path = here / "s106_blind_gauntlet_results.json"
    out_bytes = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    out_path.write_bytes(out_bytes)
    os.chmod(out_path, 0o600)
    file_sha = hashlib.sha256(out_bytes).hexdigest()

    print("\n=== PHASE 2 BLIND HELD-OUT VERDICTS (PREREG-SPHERE-PI-FORCES-V1) ===", flush=True)
    for hk, hv in verdicts.items():
        print(f"  {hk:4s}: {hv['verdict']}", flush=True)
    print(f"  INTEGRITY: arms={payload['global_integrity']['total_arms_evaluated']} syn={tot_syn} oob={tot_oob} nb={tot_nb}", flush=True)
    print(f"  FILE: {out_path.name} ({len(out_bytes)} B, mode=0o600, file_sha256={file_sha})", flush=True)
    print(f"  INNER result_sha256={payload['result_sha256']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
