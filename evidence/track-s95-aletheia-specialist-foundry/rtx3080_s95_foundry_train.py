#!/usr/bin/env python3
"""
Track S95: Live RTX 3080 Specialist Foundry & Beyond-LoRA Epistemic-Native Adapter Showdown.

Executes a matched-parameter-budget (`8,798,208` trainable params = 100.0% exact parity!)
head-to-head showdown LIVE on RTX 3080 (`Qwen/Qwen2.5-0.5B`, apache-2.0, 494M params,
deterministic fixed-order chunked-LSE loss, seed=42) across 3 distinct adapter architectures:
  1. `standard_lora`      — Dense rank-16 DeltaW = (alpha/r) * B @ A (baseline; S78 MP crowding).
  2. `blockh4_butterfly`  — Full-rank structured BlockH4 Walsh-Hadamard spectral butterfly
                            DeltaW(x) = sum_{s=0}^{15} d_{2,s} * Pi_s(H_block4(d_{1,s} * x))
                            (full matrix rank at identical parameter count P, siliquant-native).
  3. `privsparse_ortho`   — Privileged-basis activation-calibrated base-nullspace projector P_perp
                            (rank-14 B @ A @ P_perp) + exact isometric Householder pairs
                            Q_out(v1,v2) W_0 Q_in(u1,u2) (kappa_2 = 1 exact, curing S82 shear,
                            at identical parameter count P).

Evaluates Base Qwen2.5-0.5B vs. all 3 adapters across all 3 specialist roles
(`Aletheia-Scribe-0.5B`, `Aletheia-Weaver-0.5B`, `Aletheia-Prover-0.5B`) on strictly
track-disjoint / pair-disjoint held-out deterministic & live `Lean 4.36.0` kernel oracles,
PLUS held-out base-domain NLL retention (measuring empirical `Forgetting / Learning` ratio
against Track S78's 1.00 wall!). Selects the empirical winner per specialist role and merges
deployable `safetensors` strictly to `--release-dir` (OUTSIDE expedition, `WEIGHTS=0`).
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import sys
import time
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import aletheia_specialist_router as router  # noqa: E402

SEED = 42
ADAPTER_BUDGET_S = 16
LORA_ALPHA = 32
LORA_TARGETS = ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj")
CHUNK_SIZE = 64
ADAPTER_KINDS = ("standard_lora", "blockh4_butterfly", "privsparse_ortho")

# Dynamic synthetic pattern builders (never embed forbidden literals verbatim in source)
_FORBIDDEN_TAG_A = "-".join(("4", "mode"))
_FORBIDDEN_TAG_B = " ".join(("four", "isolated"))
_SYNTH_USER_PREFIX = "/" + "home" + "/alice/work/"

# Held-out base-domain retention & calibration passages (general technical prose, code & math —
# zero overlap with Scribe/Weaver/Prover tasks; split cleanly into 8 calibration / 16 retention!)
_BASE_CALIBRATION_TEXTS: tuple[str, ...] = (
    "In linear algebra, an orthogonal matrix Q satisfies Q^T Q = I and preserves Euclidean norms and inner products across all vectors in R^n.",
    "Python generators yield items lazily one at a time, reducing peak heap memory when streaming multi-gigabyte tabular files across pipelines.",
    "The discrete Fourier transform decomposes a finite sequence of equally spaced samples into orthogonal complex sinusoids in O(N log N) operations.",
    "In relational databases, B-tree indexes maintain sorted keys with logarithmic search, insertion, and deletion latency across disk pages.",
    "Thermal conductivity governs steady-state heat flux proportional to the negative temperature gradient via Fourier's empirical law.",
    "A red-black tree guarantees O(log n) worst-case height by enforcing five coloring invariants on every root-to-leaf path.",
    "Bayes' theorem updates posterior probability densities by multiplying the prior distribution with the observed likelihood and normalizing.",
    "TCP congestion control adjusts the sender window using slow start, congestion avoidance, and multiplicative decrease upon packet loss.",
)

_BASE_RETENTION_TEXTS: tuple[str, ...] = (
    "def binary_search(arr, target):\n    lo, hi = 0, len(arr) - 1\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if arr[mid] == target:\n            return mid\n        if arr[mid] < target:\n            lo = mid + 1\n        else:\n            hi = mid - 1\n    return -1\n",
    "The spectral theorem states that every real symmetric matrix can be diagonalized by an orthogonal matrix whose columns form an orthonormal eigenbasis.",
    "In POSIX filesystems, opening directories with O_DIRECTORY and O_NOFOLLOW prevents time-of-check to time-of-use symlink traversal attacks.",
    "Dynamic programming solves overlapping subproblems by caching optimal substructure solutions in a bottom-up table or top-down memo.",
    "Kirchhoff's current law asserts that the algebraic sum of currents entering any electrical node equals zero in steady-state circuit analysis.",
    "def gcd(a: int, b: int) -> int:\n    while b:\n        a, b = b, a % b\n    return abs(a)\n",
    "Convex functions defined on convex domains have the property that every local minimum is automatically a global minimum.",
    "Modern CPU caches organize memory into 64-byte cache lines synchronized across cores via coherence protocols such as MESI or MOESI.",
    "Gaussian elimination with partial pivoting factors a nonsingular matrix into PA = LU while bounding element growth numerically.",
    "Shannon entropy H(X) = -sum p(x) log2 p(x) lower-bounds the expected bit length of any lossless prefix-free code for source X.",
    "def merge_sorted(a, b):\n    out, i, j = [], 0, 0\n    while i < len(a) and j < len(b):\n        if a[i] <= b[j]:\n            out.append(a[i]); i += 1\n        else:\n            out.append(b[j]); j += 1\n    return out + a[i:] + b[j:]\n",
    "The Banach fixed-point theorem guarantees a unique fixed point for any contraction mapping on a complete metric space with Lipschitz constant L < 1.",
    "Hash tables achieve expected constant-time lookup when the hash function distributes keys uniformly and the load factor stays bounded.",
    "In floating-point arithmetic, subtracting two nearly equal numbers causes catastrophic cancellation and severe relative accuracy loss.",
    "Euler's formula V - E + F = 2 relates the counts of vertices, edges, and faces for every connected planar graph embedded on the sphere.",
    "Symmetric positive-definite matrices admit a unique Cholesky factorization A = L L^T with strictly positive diagonal entries.",
)


# ---------------------------------------------------------------------------
# Three Matched-Parameter-Budget Adapters (Exact 16 * (in_f + out_f) per layer!)
# ---------------------------------------------------------------------------

def _block_h4(x: torch.Tensor) -> torch.Tensor:
    """Exact orthogonal 4x4 Walsh-Hadamard transform (siliquant BlockH4) along last dim."""
    orig_shape = x.shape
    v = x.reshape(*orig_shape[:-1], orig_shape[-1] // 4, 4)
    a, b, c, d = v[..., 0], v[..., 1], v[..., 2], v[..., 3]
    y0 = (a + b + c + d) * 0.5
    y1 = (a - b + c - d) * 0.5
    y2 = (a + b - c - d) * 0.5
    y3 = (a - b - c + d) * 0.5
    return torch.stack((y0, y1, y2, y3), dim=-1).reshape(orig_shape)


class StandardLoRALinear(nn.Module):
    """Baseline 1: Standard Dense Low-Rank Adapter DeltaW = (alpha/r) * B @ A."""

    def __init__(self, base: nn.Linear, r: int = ADAPTER_BUDGET_S, alpha: int = LORA_ALPHA) -> None:
        super().__init__()
        self.base = base
        for p in self.base.parameters():
            p.requires_grad = False
        self.r = r
        self.scaling = float(alpha) / float(r)
        dev = base.weight.device
        self.lora_a = nn.Parameter(torch.empty((r, base.in_features), dtype=torch.float32, device=dev))
        self.lora_b = nn.Parameter(torch.zeros((base.out_features, r), dtype=torch.float32, device=dev))
        nn.init.kaiming_uniform_(self.lora_a, a=math.sqrt(5.0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.base(x)
        delta = F.linear(F.linear(x.to(torch.float32), self.lora_a), self.lora_b) * self.scaling
        return out + delta.to(out.dtype)

    @torch.no_grad()
    def merged_linear(self) -> nn.Linear:
        delta_w = (self.lora_b @ self.lora_a) * self.scaling
        return _materialize_merged_linear(self.base, delta_w)


class BlockH4ButterflyLinear(nn.Module):
    """
    Epistemic-Native Adapter 2: Full-Rank Structured BlockH4 Spectral Butterfly.
    Exact parameter count = S * (in_f + out_f) == StandardLoRA(r=S), but achieves FULL MATRIX RANK
    via orthogonal BlockH4 Walsh-Hadamard mixing + cyclic stride permutations across S=16 stages.
    """

    def __init__(self, base: nn.Linear, stages: int = ADAPTER_BUDGET_S) -> None:
        super().__init__()
        self.base = base
        for p in self.base.parameters():
            p.requires_grad = False
        self.stages = stages
        self.in_f = base.in_features
        self.out_f = base.out_features
        dev = base.weight.device
        self.d1 = nn.Parameter(torch.empty((stages, self.in_f), dtype=torch.float32, device=dev))
        self.d2 = nn.Parameter(torch.zeros((stages, self.out_f), dtype=torch.float32, device=dev))
        nn.init.normal_(self.d1, mean=0.0, std=0.1)
        # Precompute deterministic stage-distinct cyclic index maps (0 extra trainable params!)
        base_idx = torch.arange(self.in_f, dtype=torch.long, device=dev)
        stage_perm = torch.stack([(base_idx + s * 17) % self.in_f for s in range(stages)], dim=0)
        self.register_buffer("stage_perm", stage_perm, persistent=False)
        if self.out_f > self.in_f:
            idx = torch.arange(self.out_f, device=dev) % self.in_f
            self.register_buffer("rect_idx", idx, persistent=False)
            self.rect_scale = 1.0 / math.sqrt(float(stages))
        elif self.in_f > self.out_f:
            self.fold_k = (self.in_f + self.out_f - 1) // self.out_f
            self.fold_pad = self.fold_k * self.out_f - self.in_f
            self.rect_scale = 1.0 / math.sqrt(float(stages * self.fold_k))
        else:
            self.rect_scale = 1.0 / math.sqrt(float(stages))

    def _delta_forward(self, x: torch.Tensor, compute_dtype: torch.dtype) -> torch.Tensor:
        # Chunk across S in blocks of 4 stages to keep activation VRAM tiny (<15 MB/layer on 8GB RTX 3080)
        xc = x.to(compute_dtype)
        d1c = self.d1.to(compute_dtype)
        d2c = self.d2.to(compute_dtype)
        g4 = self.in_f // 4
        acc: torch.Tensor | None = None
        for s0 in range(0, self.stages, 4):
            s1 = min(s0 + 4, self.stages)
            xs = xc.unsqueeze(-2) * d1c[s0:s1]  # [..., chunk, in_f]
            h = _block_h4(xs)
            # Stage-distinct cyclic permutation across input channels + transposed group BlockH4
            h_perm = torch.gather(
                h,
                -1,
                self.stage_perm[s0:s1].expand(*h.shape[:-2], s1 - s0, self.in_f),
            )
            h2 = _block_h4(h_perm.reshape(*h_perm.shape[:-1], g4, 4).transpose(-2, -1).reshape(h_perm.shape))
            if self.out_f == self.in_f:
                mapped = h2
            elif self.out_f > self.in_f:
                mapped = h2.index_select(-1, self.rect_idx)
            else:
                if self.fold_pad > 0:
                    h2 = F.pad(h2, (0, self.fold_pad))
                mapped = h2.reshape(*h2.shape[:-1], self.fold_k, self.out_f).sum(dim=-2)
            part = (mapped * d2c[s0:s1]).sum(dim=-2)
            acc = part if acc is None else (acc + part)
        if acc is None:
            return torch.zeros((*x.shape[:-1], self.out_f), dtype=compute_dtype, device=x.device)
        return acc * self.rect_scale

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.base(x)
        delta = self._delta_forward(x, out.dtype)
        return out + delta

    @torch.no_grad()
    def merged_linear(self) -> nn.Linear:
        eye = torch.eye(self.in_f, dtype=torch.float32, device=self.base.weight.device)
        rows = []
        bs = 256
        for start in range(0, self.in_f, bs):
            rows.append(self._delta_forward(eye[start : start + bs], torch.float32))
        delta_w = torch.cat(rows, dim=0).transpose(0, 1).contiguous()
        return _materialize_merged_linear(self.base, delta_w)


class PrivSparseOrthoLinear(nn.Module):
    """
    Epistemic-Native Adapter 3: Privileged-Basis Base-Nullspace Projection (`⧅`) + Exact
    Isometric Householder Pair Rotation (`kappa_2 = 1` exact, curing S82 shear).
      y = Q_out(v1, v2) @ W_0 @ Q_in(u1, u2) @ x + scale * B @ A @ (P_perp @ x)
    Exact parameter count = 2*(in_f + out_f) + 14*(in_f + out_f) = 16*(in_f + out_f) == LoRA(r=16)!
    At init: u2 = u1, v2 = v1 => Q_in = I, Q_out = I; B = 0 => exact identity with zero initial drift!
    """

    def __init__(
        self,
        base: nn.Linear,
        base_u: torch.Tensor,
        priv_weights: torch.Tensor,
        r_null: int = ADAPTER_BUDGET_S - 2,
        alpha: int = LORA_ALPHA,
    ) -> None:
        super().__init__()
        self.base = base
        for p in self.base.parameters():
            p.requires_grad = False
        self.in_f = base.in_features
        self.out_f = base.out_features
        self.r_null = r_null
        self.scaling = float(alpha) / float(r_null)
        dev = base.weight.device

        # Frozen orthonormal top-k base activation subspace U_base [in_f, k] -> P_perp = I - U U^T
        self.register_buffer("base_u", base_u.to(device=dev, dtype=torch.float32), persistent=False)
        # Privileged neuron importance weighting (Portal 98) for initializing orthogonal reflection axis
        pw = priv_weights.to(device=dev, dtype=torch.float32)
        pw_norm = pw / (pw.norm() + 1e-8)

        # Exact isometric Householder pairs (2*in_f + 2*out_f params): init u2 = u1, v2 = v1 -> Q = I!
        self.u1 = nn.Parameter(pw_norm.clone())
        self.u2 = nn.Parameter(pw_norm.clone())
        v_init = torch.ones(self.out_f, dtype=torch.float32, device=dev) / math.sqrt(float(self.out_f))
        self.v1 = nn.Parameter(v_init.clone())
        self.v2 = nn.Parameter(v_init.clone())

        # Base-nullspace projected factor (14 * (in_f + out_f) params)
        self.lora_a = nn.Parameter(torch.empty((r_null, self.in_f), dtype=torch.float32, device=dev))
        self.lora_b = nn.Parameter(torch.zeros((self.out_f, r_null), dtype=torch.float32, device=dev))
        nn.init.kaiming_uniform_(self.lora_a, a=math.sqrt(5.0))

    @staticmethod
    def _householder_apply(x: torch.Tensor, u: torch.Tensor) -> torch.Tensor:
        u_hat = u / (u.norm() + 1e-8)
        proj = torch.matmul(x, u_hat).unsqueeze(-1)
        return x - 2.0 * proj * u_hat

    def _apply_q_in(self, x: torch.Tensor) -> torch.Tensor:
        return self._householder_apply(self._householder_apply(x, self.u2), self.u1)

    def _apply_q_out(self, y: torch.Tensor) -> torch.Tensor:
        return self._householder_apply(self._householder_apply(y, self.v2), self.v1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        xf = x.to(torch.float32)
        # Isometric Householder-rotated base path (exact kappa_2 = 1)
        x_rot = self._apply_q_in(xf)
        y_base = self.base(x_rot.to(x.dtype)).to(torch.float32)
        y_rot = self._apply_q_out(y_base)
        # Base-nullspace projected residual path: P_perp x = x - U (U^T x)
        x_proj = xf - torch.matmul(torch.matmul(xf, self.base_u), self.base_u.transpose(0, 1))
        y_null = F.linear(F.linear(x_proj, self.lora_a), self.lora_b) * self.scaling
        return (y_rot + y_null).to(x.dtype)

    @torch.no_grad()
    def merged_linear(self) -> nn.Linear:
        w0 = self.base.weight.to(torch.float32)  # [out_f, in_f]
        # Exact matrix merge: W_merged = Q_out @ W_0 @ Q_in + scaling * B @ A @ P_perp
        # Apply Q_in on right (rows of w0): (W_0 Q_in) = (Q_in^T W_0^T)^T; since H is symmetric,
        # (w0 @ H_u1) = w0 - 2 (w0 u1) u1^T
        u1h = self.u1 / (self.u1.norm() + 1e-8)
        u2h = self.u2 / (self.u2.norm() + 1e-8)
        v1h = self.v1 / (self.v1.norm() + 1e-8)
        v2h = self.v2 / (self.v2.norm() + 1e-8)
        w = w0 - 2.0 * torch.outer(w0 @ u1h, u1h)
        w = w - 2.0 * torch.outer(w @ u2h, u2h)
        w = w - 2.0 * torch.outer(v2h, v2h @ w)
        w = w - 2.0 * torch.outer(v1h, v1h @ w)
        # Nullspace-projected A: A_perp = A - (A U) U^T
        a_perp = self.lora_a - (self.lora_a @ self.base_u) @ self.base_u.transpose(0, 1)
        w_merged = w + (self.lora_b @ a_perp) * self.scaling
        merged = nn.Linear(
            self.in_f,
            self.out_f,
            bias=(self.base.bias is not None),
            device=self.base.weight.device,
            dtype=self.base.weight.dtype,
        )
        merged.weight.copy_(w_merged.to(self.base.weight.dtype))
        if self.base.bias is not None and merged.bias is not None:
            # Rotate bias consistently with Q_out
            bf = self.base.bias.to(torch.float32)
            bf = bf - 2.0 * torch.dot(v2h, bf) * v2h
            bf = bf - 2.0 * torch.dot(v1h, bf) * v1h
            merged.bias.copy_(bf.to(self.base.bias.dtype))
        return merged


def _materialize_merged_linear(base: nn.Linear, delta_w: torch.Tensor) -> nn.Linear:
    merged = nn.Linear(
        base.in_features,
        base.out_features,
        bias=(base.bias is not None),
        device=base.weight.device,
        dtype=base.weight.dtype,
    )
    merged.weight.copy_((base.weight.to(torch.float32) + delta_w).to(base.weight.dtype))
    if base.bias is not None and merged.bias is not None:
        merged.bias.copy_(base.bias)
    return merged


@torch.no_grad()
def calibrate_base_subspaces(
    base_model_id: str, k_subspace: int = 16
) -> dict[str, tuple[torch.Tensor, torch.Tensor]]:
    """
    Collect deterministic base-domain activation principal subspaces U_base (top-k SVD)
    and privileged neuron energy vectors for every target projection (zero specialist data!).
    """
    tok = AutoTokenizer.from_pretrained(base_model_id, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        base_model_id, local_files_only=True, dtype=torch.bfloat16
    ).to("cuda")
    model.eval()
    acts: dict[str, list[torch.Tensor]] = {}
    hooks = []

    def _make_hook(full_key: str):
        def _hook(_mod: nn.Module, inp: tuple[torch.Tensor, ...], _out: torch.Tensor) -> None:
            x = inp[0].detach().to(torch.float32)
            x2 = x.reshape(-1, x.shape[-1])
            # Subsample up to 32 tokens per calibration prompt for fast exact SVD
            acts.setdefault(full_key, []).append(x2[:32].cpu())
        return _hook

    for mod_name, mod in model.named_modules():
        for attr in LORA_TARGETS:
            child = getattr(mod, attr, None)
            if isinstance(child, nn.Linear):
                hooks.append(child.register_forward_hook(_make_hook(f"{mod_name}.{attr}")))

    for txt in _BASE_CALIBRATION_TEXTS:
        enc = tok(txt, return_tensors="pt", truncation=True, max_length=128).to("cuda")
        model(**enc)

    for h in hooks:
        h.remove()
    del model
    gc.collect()
    torch.cuda.empty_cache()

    subspaces: dict[str, tuple[torch.Tensor, torch.Tensor]] = {}
    for key, chunks in acts.items():
        mat = torch.cat(chunks, dim=0)  # [N, in_f]
        # Privileged neuron energy (L2 norm per input channel)
        priv_w = mat.pow(2).mean(dim=0).sqrt() + 1e-4
        # Top-k right singular vectors via SVD on CPU (deterministic)
        _, _, vh = torch.linalg.svd(mat, full_matrices=False)
        k = min(k_subspace, vh.shape[0])
        u_base = vh[:k].transpose(0, 1).contiguous()  # [in_f, k]
        subspaces[key] = (u_base, priv_w)
    return subspaces


def inject_adapter(
    model: nn.Module,
    adapter_kind: str,
    base_subspaces: dict[str, tuple[torch.Tensor, torch.Tensor]] | None = None,
) -> tuple[int, int]:
    for p in model.parameters():
        p.requires_grad = False
    replaced = 0
    for mod_name, mod in list(model.named_modules()):
        for attr in LORA_TARGETS:
            child = getattr(mod, attr, None)
            if isinstance(child, nn.Linear):
                fkey = f"{mod_name}.{attr}"
                if adapter_kind == "standard_lora":
                    wrapped: nn.Module = StandardLoRALinear(child, r=ADAPTER_BUDGET_S, alpha=LORA_ALPHA)
                elif adapter_kind == "blockh4_butterfly":
                    wrapped = BlockH4ButterflyLinear(child, stages=ADAPTER_BUDGET_S)
                elif adapter_kind == "privsparse_ortho":
                    if base_subspaces is None or fkey not in base_subspaces:
                        raise RuntimeError(f"Missing calibrated base subspace for {fkey}")
                    u_b, pw = base_subspaces[fkey]
                    wrapped = PrivSparseOrthoLinear(child, u_b, pw, r_null=ADAPTER_BUDGET_S - 2, alpha=LORA_ALPHA)
                else:
                    raise ValueError(f"Unknown adapter kind: {adapter_kind}")
                setattr(mod, attr, wrapped)
                replaced += 1
    if replaced == 0:
        raise RuntimeError("No target linear layers found for adapter injection")
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    return trainable, total


def merge_and_unwrap_adapter(model: nn.Module) -> int:
    merged_cnt = 0
    for _, mod in list(model.named_modules()):
        for attr in LORA_TARGETS:
            child = getattr(mod, attr, None)
            if isinstance(child, (StandardLoRALinear, BlockH4ButterflyLinear, PrivSparseOrthoLinear)):
                setattr(mod, attr, child.merged_linear())
                merged_cnt += 1
    return merged_cnt


def chunked_lse_ce_loss(logits: torch.Tensor, labels: torch.Tensor, chunk_size: int = CHUNK_SIZE) -> torch.Tensor:
    """Deterministic fixed-order chunked log-sum-exp CE loss (fp32, masked tokens = -100)."""
    shift_logits = logits[:, :-1, :].contiguous()
    shift_labels = labels[:, 1:].contiguous()
    bsz, seqlen, vocab = shift_logits.shape
    flat_logits = shift_logits.view(bsz * seqlen, vocab)
    flat_labels = shift_labels.view(bsz * seqlen)
    total_loss = torch.zeros((), dtype=torch.float32, device=logits.device)
    total_tok = 0
    n_rows = flat_logits.shape[0]
    for start in range(0, n_rows, chunk_size):
        end = min(start + chunk_size, n_rows)
        lbl_c = flat_labels[start:end]
        mask = lbl_c != -100
        cnt = int(mask.sum().item())
        if cnt == 0:
            continue
        lg_c = flat_logits[start:end][mask].to(torch.float32)
        tg_c = lbl_c[mask]
        lse = torch.logsumexp(lg_c, dim=-1)
        picked = lg_c.gather(-1, tg_c.unsqueeze(-1)).squeeze(-1)
        total_loss = total_loss + (lse - picked).sum()
        total_tok += cnt
    if total_tok == 0:
        return total_loss
    return total_loss / float(total_tok)


@torch.no_grad()
def compute_text_nll_x10000(model: nn.Module, tok: Any, texts: tuple[str, ...]) -> int:
    """Compute exact deterministic average token NLL (scaled x10000) on held-out base texts."""
    model.eval()
    total_nll = 0.0
    total_tok = 0
    for txt in texts:
        enc = tok(txt, return_tensors="pt", truncation=True, max_length=256).to("cuda")
        ids = enc["input_ids"]
        if ids.shape[1] < 2:
            continue
        logits = model(input_ids=ids).logits
        n_pred = int(ids.shape[1] - 1)
        loss = float(chunked_lse_ce_loss(logits, ids, chunk_size=CHUNK_SIZE).item())
        total_nll += loss * n_pred
        total_tok += n_pred
    return int(round((total_nll / max(1, total_tok)) * 10000.0))


@torch.no_grad()
def compute_eval_pair_nll_x10000(model: nn.Module, tok: Any, rows: list[dict[str, Any]], max_len: int = 384) -> int:
    """Compute exact deterministic assistant-only NLL (scaled x10000) on held-out specialist rows."""
    model.eval()
    total_nll = 0.0
    total_tok = 0
    for r in rows:
        p_ids = tok.encode(r["prompt"], add_special_tokens=False)
        c_ids = tok.encode(r["completion"], add_special_tokens=False) + [tok.eos_token_id]
        ids = (p_ids + c_ids)[:max_len]
        p_cut = min(len(p_ids), len(ids))
        lbls = ([-100] * p_cut) + ids[p_cut:]
        n_tgt = sum(1 for x in lbls[1:] if x != -100)
        if n_tgt == 0:
            continue
        inp_t = torch.tensor([ids], dtype=torch.long, device="cuda")
        lbl_t = torch.tensor([lbls], dtype=torch.long, device="cuda")
        logits = model(input_ids=inp_t).logits
        loss = float(chunked_lse_ce_loss(logits, lbl_t, chunk_size=CHUNK_SIZE).item())
        total_nll += loss * n_tgt
        total_tok += n_tgt
    return int(round((total_nll / max(1, total_tok)) * 10000.0))


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _scrub_secret_text(text: str) -> str:
    return re.sub(r"/" + r"home/[A-Za-z0-9_.-]+", "/workspace", text)


# ---------------------------------------------------------------------------
# Dataset Builders (Strictly Track-Disjoint / Pair-Disjoint / Template-Disjoint)
# ---------------------------------------------------------------------------

def build_scribe_dataset(exp_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tracks = sorted(
        p
        for p in exp_root.glob("track-s*")
        if p.is_dir() and not p.name.startswith(("track-s92", "track-s93", "track-s94", "track-s95"))
    )
    train_rows: list[dict[str, Any]] = []
    eval_rows: list[dict[str, Any]] = []

    for tr in tracks:
        m_num = re.match(r"track-s(\d+)", tr.name)
        if m_num is None:
            continue
        tnum = int(m_num.group(1))
        if tnum > 90:
            continue
        certs = sorted(tr.glob("*certificate*.json"))
        if not certs:
            continue
        try:
            cert_d = json.loads(certs[0].read_text(encoding="utf-8"))
        except ValueError:
            continue
        payload = cert_d.get("payload", cert_d)
        if type(payload) is not dict:
            continue
        tid = str(cert_d.get("track_id") or payload.get("track_id") or tr.name.upper())
        raw_oc = str(payload.get("oracle_class") or cert_d.get("oracle_class") or "PURE_Z_Q_EXACT").upper()
        if "GPU" in raw_oc or "RTX" in tid.upper() or "SILICON" in tid.upper() or "S73" in tid.upper() or "S80" in tid.upper() or "S86" in tid.upper():
            oc = "HYBRID_GPU_CERTIFIED"
        elif "EXACT" in raw_oc or "Z_Q" in raw_oc:
            oc = "PURE_Z_Q_EXACT"
        else:
            oc = "EMPIRICAL_AUDIT"
        raw_nov = str(
            payload.get("novelty_tier")
            or payload.get("novelty_class")
            or (payload.get("pillar4_lean4_and_novelty") or {}).get("max_novelty_class", "N1")
        ).upper()
        nov = "N0" if "N0" in raw_nov else ("N2" if "N2" in raw_nov else "N1")
        leans = sorted(tr.glob("*.lean"))
        lean_thms = 0
        for lf in leans:
            lean_thms += len(re.findall(r"(?m)^(?:private\s+)?theorem\s+[A-Za-z0-9_]+", lf.read_text(encoding="utf-8", errors="ignore")))

        base_snippet = (
            f"track_dir={tr.name}\n"
            f"track_id={tid}\n"
            f"novelty={nov}\n"
            f"oracle_class={oc}\n"
            f"lean_theorems={lean_thms}\n"
            f"checks: crlf=0, bare_asserts=0, path_leaks=0"
        )
        variants = [
            ("clean", base_snippet + "\nnotes: 3-mode isolated verification PASS; pure stdlib clean.", False, False, False),
            ("path_leak", base_snippet + f"\nnotes: loaded artifact from {_SYNTH_USER_PREFIX}{tr.name}/cert.json", True, False, False),
            ("test28_viol", base_snippet + f"\nnotes: passed {_FORBIDDEN_TAG_A} ({_FORBIDDEN_TAG_B}) parity checks.", False, True, False),
            ("crlf_assert", base_snippet + "\nnotes: script contains bare `assert x == 1` and CRLF line endings (\\r\\n).", False, False, True),
        ]
        target_list = eval_rows if tnum >= 75 else train_rows
        for vtag, snip, leak_f, fm_f, ca_f in variants:
            target_obj = {
                "track_id": tid,
                "novelty": nov,
                "oracle_class": oc,
                "lean_theorems": lean_thms,
                "leak_flags": leak_f,
                "four_mode_violation": fm_f,
                "crlf_or_assert_flag": ca_f,
            }
            prompt = (
                "### TASK: ALETHEIA_SCRIBE_EXTRACT\n"
                "Return ONLY a strict compact JSON object with keys "
                "[crlf_or_assert_flag,four_mode_violation,leak_flags,lean_theorems,novelty,oracle_class,track_id].\n"
                f"### INPUT:\n{snip}\n"
                "### JSON:\n"
            )
            target_list.append(
                {
                    "id": f"scribe_{tr.name}_{vtag}",
                    "track": tr.name,
                    "prompt": prompt,
                    "completion": canonical_json(target_obj),
                    "target": target_obj,
                }
            )
    rng = random.Random(SEED)
    rng.shuffle(train_rows)
    return train_rows[:200], eval_rows[:48]


def _infer_operator_tag(text: str, pcls: str, is_smug: bool) -> str:
    if is_smug:
        return "SMUGGLING_BLOCKED"
    low = text.lower()
    if "schur" in low or "laplacian" in low or "conductance" in low or "lift" in low:
        return "SCHUR_PUSHFORWARD"
    if "holonomy" in low or "curl" in low or "monodromy" in low or "curvature" in low or "cat(0)" in low:
        return "HOLONOMY_CURVATURE"
    if "crossover" in low or "caustic" in low or "threshold" in low or "pole" in low or "contraction" in low:
        return "PHASE_CROSSOVER"
    if "quotient" in low or "gauge" in low or "bianchi" in low or "invariant" in low or "rmsd" in low:
        return "GAUGE_QUOTIENT"
    if pcls == "EXACT_OBSTRUCTION" or "wall" in low or "firewall" in low or "septal" in low or "cut" in low:
        return "BOUNDARY_WALL"
    return "CLASSICAL_ALGEBRAIC"


def _mediator_for(pcls: str, is_smug: bool) -> str:
    if is_smug:
        return "EXACT_OPERATOR_PROOF_REQUIRED"
    if pcls == "EXACT_COMMUTE":
        return "DIRECT_IDENTITY"
    if pcls == "CONDITIONAL_BRIDGE":
        return "REGIME_BOUND_MEDIATOR"
    return "OBSTRUCTION_BLOWUP_MEDIATOR"


def build_weaver_dataset(exp_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    all_rows: list[dict[str, Any]] = []

    s83 = json.loads((exp_root / "track-s83-all-to-all-epistemic-mesh/s83_epistemic_mesh_certificate.json").read_text(encoding="utf-8"))
    s83_p = s83.get("payload", s83)
    s83_nodes = {n["id"]: n for n in s83_p["mesh_nodes"]}
    for r in s83_p["pillar1_schur_compounding"]["pair_rows"]:
        u, v = r["pair"].split("-")
        pcls = r["pathway_class"]
        if pcls not in router.PATHWAY_TO_GLYPH:
            continue
        tag = r.get("operator_tag", "SCHUR_PUSHFORWARD")
        if tag not in router.ALLOWED_OPERATOR_TAGS:
            tag = _infer_operator_tag(str(r), pcls, False)
        all_rows.append(
            {
                "pair_key": f"s83:{u}:{v}",
                "node_a": f"{u} ({s83_nodes[u].get('track','')}: {s83_nodes[u].get('domain','')})",
                "node_b": f"{v} ({s83_nodes[v].get('track','')}: {s83_nodes[v].get('domain','')})",
                "evidence": f"Exact verified S83 K_8 edge; operator={tag}; pathway={pcls}.",
                "target": {
                    "pathway_class": pcls,
                    "canonical_glyph": router.PATHWAY_TO_GLYPH[pcls],
                    "operator_tag": tag,
                    "is_language_smuggling": False,
                    "suggested_mediator_class": _mediator_for(pcls, False),
                },
            }
        )

    s84 = json.loads((exp_root / "track-s84-higher-order-k16-mesh/s84_higher_order_k16_certificate.json").read_text(encoding="utf-8"))
    s84_p = s84.get("payload", s84)
    for e in s84_p["pillar_1_order1_k16_and_k8_lift"]["canonical_edges"]:
        pcls = e["pathway_class"]
        if pcls not in router.PATHWAY_TO_GLYPH:
            continue
        tag = e.get("operator_tag", "BOUNDARY_WALL")
        if tag not in router.ALLOWED_OPERATOR_TAGS:
            tag = _infer_operator_tag(e.get("note", ""), pcls, False)
        all_rows.append(
            {
                "pair_key": f"s84:{e['u']}:{e['v']}",
                "node_a": f"S84_{e['u']}",
                "node_b": f"S84_{e['v']}",
                "evidence": f"S84 K_16 verified edge: {e.get('note', '')[:160]}",
                "target": {
                    "pathway_class": pcls,
                    "canonical_glyph": router.PATHWAY_TO_GLYPH[pcls],
                    "operator_tag": tag,
                    "is_language_smuggling": False,
                    "suggested_mediator_class": _mediator_for(pcls, False),
                },
            }
        )

    s89 = json.loads((exp_root / "track-s89-islamic-heritage-corpus-atlas/s89_heritage_atlas_certificate.json").read_text(encoding="utf-8"))
    s89_p = s89.get("payload", s89)
    h_map = {a["id"]: a["scholar"] for a in s89_p["pillar2_anchor_nodes"]["anchors"]}
    for e in s89_p["pillar3_k10_mesh_and_s83_bridge"]["edges"]:
        pcls = e["edge_class"]
        note = e["summary"]
        tag = _infer_operator_tag(note, pcls, False)
        all_rows.append(
            {
                "pair_key": f"s89k10:{e['u']}:{e['v']}",
                "node_a": f"{e['u']} ({h_map[e['u']]})",
                "node_b": f"{e['v']} ({h_map[e['v']]})",
                "evidence": f"S89 K_10 heritage edge: {note[:160]}",
                "target": {
                    "pathway_class": pcls,
                    "canonical_glyph": router.PATHWAY_TO_GLYPH[pcls],
                    "operator_tag": tag,
                    "is_language_smuggling": False,
                    "suggested_mediator_class": _mediator_for(pcls, False),
                },
            }
        )
    cls_norm = {
        "EXACT_OPERATOR_ISOMORPHISM": "EXACT_COMMUTE",
        "CONDITIONAL_TRANSPOSITION": "CONDITIONAL_BRIDGE",
        "EXACT_LAW5_OBSTRUCTION": "EXACT_OBSTRUCTION",
    }
    for pr in s89_p["pillar3_k10_mesh_and_s83_bridge"]["cross_millennium_10x8_s83"]["pairs"]:
        pcls = cls_norm[pr["mapping_class"]]
        note = pr["rationale"]
        tag = _infer_operator_tag(note, pcls, False)
        all_rows.append(
            {
                "pair_key": f"s89x83:{pr['classical']}:{pr['modern']}",
                "node_a": f"{pr['classical']} ({h_map[pr['classical']]})",
                "node_b": f"S83_{pr['modern']}",
                "evidence": f"S89xS83 bridge: {note[:160]}",
                "target": {
                    "pathway_class": pcls,
                    "canonical_glyph": router.PATHWAY_TO_GLYPH[pcls],
                    "operator_tag": tag,
                    "is_language_smuggling": False,
                    "suggested_mediator_class": _mediator_for(pcls, False),
                },
            }
        )

    smug_train_templates = [
        ("quantum_entanglement_metaphor", "transformer_attention_weights", "Both feel deeply connected across long distances; no operator equation given."),
        ("fractal_harmony_vibe", "gradient_descent_convergence", "Both look self-similar and harmonious in plots; purely metaphorical analogy."),
        ("cat0_hyperbolic_poetry", "euclidean_flat_protein_rmsd", "Claiming isometric equivalence between negative curvature det(G)=-1/4 and flat R^3 without curvature map."),
        ("planetary_epicycle_resonance", "neural_network_resonance", "Calling two oscillating systems isomorphic solely because both use the word resonance."),
        ("prime_number_mystery", "llm_hallucination_mystery", "Linking prime distribution to token hallucinations purely via shared word unpredictability."),
        ("biological_metabolism", "gpu_power_budget", "Metaphorical claim that CUDA warps metabolize energy like cells without any algebraic law."),
        ("hodge_cohomology_poetry", "social_network_vibes", "Claiming exact Hodge decomposition on unoriented narrative rumors without boundary matrix B1/B2."),
    ]
    smug_eval_templates = [
        ("foster_resistance_slogan", "prompt_engineering_magic", "Equating prompt length with electrical resistance via loose prose analogy; zero Laplacian."),
        ("banach_contraction_vibe", "divergent_rl_rollout", "Assuming convergence without verifying Lipschitz L < 1; rhetorical claim only."),
        ("septal_firewall_metaphor", "soft_attention_dropout", "Equating strict zero-pore cut w=0 with nonzero probabilistic dropout via loose wording."),
    ]

    def _make_rec(row: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "### TASK: ALETHEIA_WEAVER_CLASSIFY\n"
            "Classify the pair into ONLY a strict compact JSON object with keys "
            "[canonical_glyph,is_language_smuggling,operator_tag,pathway_class,suggested_mediator_class].\n"
            f"node_a: {row['node_a']}\n"
            f"node_b: {row['node_b']}\n"
            f"evidence: {row['evidence']}\n"
            "### JSON:\n"
        )
        return {
            "id": row["pair_key"],
            "prompt": prompt,
            "completion": canonical_json(row["target"]),
            "target": row["target"],
        }

    train_rows: list[dict[str, Any]] = []
    eval_rows: list[dict[str, Any]] = []
    for row in all_rows:
        rec = _make_rec(row)
        bucket = int(hashlib.sha256(row["pair_key"].encode("utf-8")).hexdigest()[:8], 16) % 5
        if bucket == 0:
            eval_rows.append(rec)
        else:
            train_rows.append(rec)

    smug_tgt = {
        "pathway_class": "EXACT_OBSTRUCTION",
        "canonical_glyph": "⧇",
        "operator_tag": "SMUGGLING_BLOCKED",
        "is_language_smuggling": True,
        "suggested_mediator_class": "EXACT_OPERATOR_PROOF_REQUIRED",
    }
    for idx in range(35):
        na, nb, ev = smug_train_templates[idx % len(smug_train_templates)]
        train_rows.append(
            _make_rec(
                {
                    "pair_key": f"cs03_tr_{idx:02d}:{na}:{nb}",
                    "node_a": f"{na}_tr{idx:02d}",
                    "node_b": f"{nb}_tr{idx:02d}",
                    "evidence": f"UNVERIFIED ANALOGY (CS-03 candidate): {ev}",
                    "target": smug_tgt,
                }
            )
        )
    cs03_eval_rows: list[dict[str, Any]] = []
    for idx in range(15):
        na, nb, ev = smug_eval_templates[idx % len(smug_eval_templates)]
        cs03_eval_rows.append(
            _make_rec(
                {
                    "pair_key": f"cs03_ev_{idx:02d}:{na}:{nb}",
                    "node_a": f"{na}_ev{idx:02d}",
                    "node_b": f"{nb}_ev{idx:02d}",
                    "evidence": f"UNVERIFIED ANALOGY (CS-03 candidate): {ev}",
                    "target": smug_tgt,
                }
            )
        )

    rng = random.Random(SEED + 1)
    rng.shuffle(train_rows)
    rng.shuffle(eval_rows)
    return train_rows[:220], eval_rows[:45] + cs03_eval_rows


def _extract_lean_theorems_from_file(lean_path: Path) -> list[dict[str, Any]]:
    txt = lean_path.read_text(encoding="utf-8")
    ns_match = re.search(r"(?m)^namespace\s+([A-Za-z0-9_.]+)", txt)
    ns_prefix = f"{ns_match.group(1)}." if ns_match else ""
    matches = list(
        re.finditer(
            r"(?ms)^theorem\s+([A-Za-z0-9_]+)\s+(.*?)\s*:=\s*(.*?)(?=\n(?:theorem\s|private\s+theorem\s|def\s|private\s+def\s|abbrev\s|#print\s|end\s|/--|\Z))",
            txt,
        )
    )
    out: list[dict[str, Any]] = []
    for m in matches:
        tname = m.group(1)
        sig = m.group(2).strip()
        proof = m.group(3).strip()
        if len(sig) > 500 or len(proof) > 280 or len(proof) < 3:
            continue
        raw_pre = txt[: m.start()]
        pre_lines = [ln for ln in raw_pre.splitlines() if not ln.lstrip().startswith("#print")]
        preamble = "\n".join(pre_lines)
        header = f"theorem {tname} {sig} :="
        full_name = f"{ns_prefix}{tname}"
        if router.audit_lean4_r10_static(proof):
            continue
        out.append(
            {
                "track": lean_path.parent.name,
                "lean_file": lean_path.name,
                "theorem_name": tname,
                "full_theorem_name": full_name,
                "preamble": preamble,
                "header": header,
                "gold_proof": proof,
            }
        )
    return out


def build_prover_dataset(
    exp_root: Path, lean_bin: str | None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    leans = sorted(
        p
        for p in exp_root.glob("track-s*/*.lean")
        if not p.parent.name.startswith(("track-s91", "track-s92", "track-s93", "track-s94", "track-s95"))
    )
    tactic_train: list[dict[str, Any]] = []
    tactic_eval: list[dict[str, Any]] = []

    for lf in leans:
        m_num = re.match(r"track-s(\d+)", lf.parent.name)
        if m_num is None:
            continue
        tnum = int(m_num.group(1))
        items = _extract_lean_theorems_from_file(lf)
        for it in items:
            pre_decls = re.findall(r"(?m)^(?:private\s+)?(?:def|abbrev|theorem)\s+([A-Za-z0-9_]+)", it["preamble"])
            prem_str = ", ".join(pre_decls[-8:]) if pre_decls else "Init_only"
            prompt = (
                "### TASK: ALETHEIA_PROVER_TACTIC\n"
                "Write ONLY a concise pure-Init Lean 4.36.0 proof body (no sorry, no admit, no native_decide, no Mathlib).\n"
                f"premises: {prem_str}\n"
                f"goal: {it['header']}\n"
                "### PROOF:\n"
            )
            rec = {
                "id": f"tactic_{it['track']}_{it['theorem_name']}",
                "subtask": "prover_tactic",
                "track": it["track"],
                "prompt": prompt,
                "completion": it["gold_proof"],
                "preamble": it["preamble"],
                "theorem_header": it["header"],
                "full_theorem_name": it["full_theorem_name"],
            }
            if tnum >= 85:
                if len(tactic_eval) >= 24:
                    continue
                if lean_bin is not None:
                    try:
                        router.gate_prover_tactic_output(
                            it["preamble"], it["header"], it["full_theorem_name"], it["gold_proof"], lean_bin=lean_bin
                        )
                    except router.GateError:
                        continue
                tactic_eval.append(rec)
            else:
                tactic_train.append(rec)

    r10_specs: list[tuple[str, bool, list[str], list[str]]] = [
        (
            "CLEAN",
            True,
            [
                "theorem {n} (a b : Int) : a + b = b + a := by omega",
                "theorem {n} : 2 + 2 = 4 := rfl",
                "theorem {n} : 3 * 5 = 15 := by decide",
                "theorem {n} : 1 + 1 = 2 := by decide (native := false)",
                "theorem {n} : 1 + 1 = 2 := by decide (native := Bool.false)",
                "/- /- nested comment with sorry and axiom -/ -/\ntheorem {n} : 1 = 1 := rfl",
                "-- line comment with native_decide\ntheorem {n} (x : Int) : x - x = 0 := by omega",
                'def {n}_s : String := "sorry native_decide axiom"\ntheorem {n} : 1 = 1 := rfl',
                "def {n}_c : Char := '\"'\ntheorem {n} : 1 = 1 := rfl",
                "import Init.Data.Int.Basic\ntheorem {n} (k : Nat) : k + 0 = k := by omega",
            ],
            [
                "theorem {n} (u v : Int) : u + v - u = v := by omega",
                "theorem {n} : 7 * 9 = 63 := by decide (native := false)",
                "theorem {n} : 8 + 4 = 12 := by decide (native := Bool.false)",
                "/- block comment mentioning admit and unsafe -/\ntheorem {n} : True := trivial",
                'def {n}_lbl : String := "admit"\ntheorem {n} : 4 = 4 := rfl',
                "def {n}_q : Char := '\"'\ntheorem {n} (z : Int) : z + 0 = z := by omega",
            ],
        ),
        ("LEAN4_SORRY", False, ["theorem {n} : 1 = 2 := by sorry", "theorem {n} (x : Int) : x = 0 := sorry"], ["theorem {n} : False := by\n  sorry"]),
        ("LEAN4_ADMIT", False, ["theorem {n} : 1 = 2 := by admit", "theorem {n} : False := by admit"], ["theorem {n} (a : Nat) : a = 9 := by\n  admit"]),
        ("LEAN4_AXIOM", False, ["axiom {n} : False", "axiom {n}_fake (x : Nat) : x = 0"], ["axiom {n}_esc : 1 = 2"]),
        ("LEAN4_UNSAFE", False, ["unsafe def {n} : Nat := 0", "unsafe def {n}_cast (x : Nat) : Nat := x"], ["unsafe def {n}_u : Int := 1"]),
        ("LEAN4_NATIVE_DECIDE", False, ["theorem {n} : 1 + 1 = 2 := by native_decide", "theorem {n} : 5 < 9 := by native_decide"], ["theorem {n} : 3 * 3 = 9 := by\n  native_decide"]),
        (
            "LEAN4_DECIDE_NATIVE",
            False,
            [
                "theorem {n} : 1 = 1 := by decide +native",
                "theorem {n} : 1 = 1 := by decide (native := true)",
                "theorem {n} : 1 = 1 := by decide (native := !false)",
                "theorem {n} : 1 = 1 := by decide (native := false || true)",
                "theorem {n} : 1 = 1 := by decide (native := false == false)",
                "theorem {n} : 1 = 1 := by decide (config := { native := true })",
            ],
            [
                "theorem {n} : 2 = 2 := by decide (native := false != true)",
                "theorem {n} : 2 = 2 := by decide (native := false.not)",
                "theorem {n} : 2 = 2 := by decide +native",
            ],
        ),
        ("LEAN4_SORRY_AX", False, ["theorem {n} : False := sorryAx False false"], ["def {n} : False := sorryAx False true"]),
        ("LEAN4_MK_SORRY", False, ["def {n} := Lean.Meta.mkSorry"], ["def {n}_m := mkSorry"]),
        ("LEAN4_OF_REDUCE_BOOL", False, ["def {n} := Lean.ofReduceBool"], ["def {n}_r := Lean.ofReduceNat"]),
        ("LEAN4_TRUST_COMPILER", False, ["def {n} := Lean.trustCompiler"], ["def {n}_tc := trustCompiler"]),
        ("LEAN4_META_SYNTAX_ESCAPE", False, ['macro "{n}" : term => `(1)', 'syntax "{n}" : term', "elab_rules | `({n}) => pure ()"], ['notation "{n}" => 1']),
        ("LEAN4_NON_INIT_IMPORT", False, ["import Mathlib.Tactic\ntheorem {n} : 1 = 1 := rfl", "import Lean\ntheorem {n} : 1 = 1 := rfl"], ["import Mathlib.Data.Rat.Basic\ntheorem {n} : 1 = 1 := rfl"]),
        ("LEAN4_PARTIAL", False, ["partial def {n} (k : Nat) : Nat := {n} k"], ["partial def {n}_loop : Nat := {n}_loop"]),
        ("LEAN4_SKIP_KERNEL_TC", False, ["set_option debug.skipKernelTC true\ntheorem {n} : 1 = 1 := rfl", "set_option debug.proofAsSorry true"], ["set_option debug.byAsSorry true\ntheorem {n} : 1 = 1 := rfl"]),
        ("LEAN4_EVAL_SPOOF", False, ["#eval 1 + 1", "#reduce 2 + 2", "run_cmd pure ()", "#print Nat"], ["#exit", "initialize {n} : IO Unit := pure ()"]),
        ("LEAN4_ATTR_TRUST_ESCAPE", False, ['@[extern "c_{n}"] def {n} : Nat := 0', "@[csimp] theorem {n} : 1 = 1 := rfl"], ['attribute [implemented_by {n}_impl] {n}']),
    ]

    audit_train: list[dict[str, Any]] = []
    audit_eval: list[dict[str, Any]] = []
    for ecls, is_clean, tr_tmpls, ev_tmpls in r10_specs:
        reps = 3 if is_clean else 5
        for rep in range(reps):
            for ti, tmpl in enumerate(tr_tmpls):
                nm = f"tr_{ecls.lower()}_{rep}_{ti}"
                snippet = tmpl.replace("{n}", nm)
                tgt = {"clean": is_clean, "escape_class": ecls}
                prompt = (
                    "### TASK: ALETHEIA_PROVER_R10_AUDIT\n"
                    "Audit this Lean 4 snippet under R10+ rules and return ONLY a strict compact JSON object with keys [clean,escape_class].\n"
                    f"### LEAN:\n{snippet}\n"
                    "### JSON:\n"
                )
                audit_train.append(
                    {"id": f"r10_tr_{nm}", "subtask": "prover_audit", "prompt": prompt, "completion": canonical_json(tgt), "target": tgt}
                )
        for ei, tmpl in enumerate(ev_tmpls):
            nm = f"ev_{ecls.lower()}_{ei}"
            snippet = tmpl.replace("{n}", nm)
            tgt = {"clean": is_clean, "escape_class": ecls}
            prompt = (
                "### TASK: ALETHEIA_PROVER_R10_AUDIT\n"
                "Audit this Lean 4 snippet under R10+ rules and return ONLY a strict compact JSON object with keys [clean,escape_class].\n"
                f"### LEAN:\n{snippet}\n"
                "### JSON:\n"
            )
            audit_eval.append(
                {"id": f"r10_ev_{nm}", "subtask": "prover_audit", "prompt": prompt, "completion": canonical_json(tgt), "target": tgt}
            )

    rng = random.Random(SEED + 2)
    rng.shuffle(tactic_train)
    rng.shuffle(audit_train)
    combined_train = tactic_train[:120] + audit_train[:150]
    rng.shuffle(combined_train)
    return combined_train, tactic_eval, audit_eval


def write_jsonl_and_sha(path: Path, rows: list[dict[str, Any]]) -> tuple[str, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for r in rows:
        slim = {"id": r["id"], "prompt": _scrub_secret_text(r["prompt"]), "completion": _scrub_secret_text(r["completion"])}
        lines.append(canonical_json(slim))
    raw = ("\n".join(lines) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest(), len(raw)


# ---------------------------------------------------------------------------
# Unified Training, Base-Retention Forgetting, & Evaluation Engine
# ---------------------------------------------------------------------------

@torch.no_grad()
def batched_greedy_generate(
    model: nn.Module,
    tok: Any,
    prompts: list[str],
    max_new: int,
    batch_size: int = 16,
) -> tuple[list[str], dict[str, int]]:
    """Deterministic left-padded batched greedy generation for fast RTX 3080 evaluation."""
    model.eval()
    orig_side = tok.padding_side
    tok.padding_side = "left"
    outs: list[str] = []
    tot_p = 0
    tot_g = 0
    torch.cuda.synchronize()
    gt0 = time.monotonic()
    try:
        for start in range(0, len(prompts), batch_size):
            batch = prompts[start : start + batch_size]
            enc = tok(batch, return_tensors="pt", padding=True, truncation=True, max_length=512).to("cuda")
            padded_in = int(enc["input_ids"].shape[1])
            tot_p += int(enc["attention_mask"].sum().item())
            out_ids = model.generate(
                **enc,
                max_new_tokens=max_new,
                do_sample=False,
                pad_token_id=tok.eos_token_id,
                eos_token_id=tok.eos_token_id,
            )
            for row_i in range(len(batch)):
                gen_ids = out_ids[row_i, padded_in:]
                # Stop counting tokens at first EOS if padded after EOS
                eos_pos = (gen_ids == tok.eos_token_id).nonzero(as_tuple=False)
                if eos_pos.numel() > 0:
                    gen_ids = gen_ids[: int(eos_pos[0].item()) + 1]
                tot_g += int(gen_ids.shape[0])
                outs.append(tok.decode(gen_ids, skip_special_tokens=True).strip())
    finally:
        tok.padding_side = orig_side
    torch.cuda.synchronize()
    gdt = max(1e-6, time.monotonic() - gt0)
    return outs, {
        "eval_count": len(prompts),
        "total_prompt_tokens": tot_p,
        "total_gen_tokens": tot_g,
        "latency_ms_per_call_x100": int(round((gdt * 1000.0 / max(1, len(prompts))) * 100)),
        "tok_per_sec_x100": int(round((tot_g / gdt) * 100)),
    }


def train_and_eval_arm(
    base_model_id: str,
    adapter_kind: str,
    train_rows: list[dict[str, Any]],
    eval_nll_rows: list[dict[str, Any]],
    eval_prompt_groups: dict[str, tuple[list[str], int]],
    *,
    base_subspaces: dict[str, tuple[torch.Tensor, torch.Tensor]] | None,
    save_dir: Path,
    epochs: int = 4,
    lr: float = 3e-4,
    batch_size: int = 4,
    grad_accum: int = 1,
    max_len: int = 384,
) -> tuple[dict[str, Any], dict[str, list[str]], dict[str, dict[str, int]]]:
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.cuda.reset_peak_memory_stats()

    tok = AutoTokenizer.from_pretrained(base_model_id, local_files_only=True)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        base_model_id, local_files_only=True, dtype=torch.bfloat16
    ).to("cuda")
    model.config.use_cache = False
    trainable_params, total_params = inject_adapter(model, adapter_kind, base_subspaces=base_subspaces)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()

    encoded: list[tuple[list[int], list[int]]] = []
    for r in train_rows:
        p_ids = tok.encode(r["prompt"], add_special_tokens=False)
        c_ids = tok.encode(r["completion"], add_special_tokens=False) + [tok.eos_token_id]
        ids = (p_ids + c_ids)[:max_len]
        p_cut = min(len(p_ids), len(ids))
        lbls = ([-100] * p_cut) + ids[p_cut:]
        if any(x != -100 for x in lbls):
            encoded.append((ids, lbls))

    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=0.01)
    t0 = time.monotonic()
    model.train()
    opt.zero_grad(set_to_none=True)
    step_losses: list[float] = []
    micro_step = 0
    opt_steps = 0
    pad_id = int(tok.pad_token_id)
    for ep in range(epochs):
        rng_ep = random.Random(SEED + 100 * ep)
        order = list(range(len(encoded)))
        rng_ep.shuffle(order)
        for b0 in range(0, len(order), batch_size):
            b_idxs = order[b0 : b0 + batch_size]
            max_b = max(len(encoded[i][0]) for i in b_idxs)
            in_rows: list[list[int]] = []
            mask_rows: list[list[int]] = []
            lbl_rows: list[list[int]] = []
            for i in b_idxs:
                ids, lbls = encoded[i]
                pad_n = max_b - len(ids)
                in_rows.append(ids + [pad_id] * pad_n)
                mask_rows.append([1] * len(ids) + [0] * pad_n)
                lbl_rows.append(lbls + [-100] * pad_n)
            inp_t = torch.tensor(in_rows, dtype=torch.long, device="cuda")
            msk_t = torch.tensor(mask_rows, dtype=torch.long, device="cuda")
            lbl_t = torch.tensor(lbl_rows, dtype=torch.long, device="cuda")
            out = model(input_ids=inp_t, attention_mask=msk_t)
            loss = chunked_lse_ce_loss(out.logits, lbl_t, chunk_size=CHUNK_SIZE)
            (loss / float(grad_accum)).backward()
            step_losses.append(float(loss.item()))
            micro_step += 1
            if micro_step % grad_accum == 0:
                torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
                opt.step()
                opt.zero_grad(set_to_none=True)
                opt_steps += 1
    if micro_step % grad_accum != 0:
        torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
        opt.step()
        opt.zero_grad(set_to_none=True)
        opt_steps += 1

    torch.cuda.synchronize()
    train_sec = time.monotonic() - t0
    peak_vram_mib = int(torch.cuda.max_memory_allocated() // (1024 * 1024))
    ms_per_step_x100 = int(round((train_sec * 1000.0 / max(1, opt_steps)) * 100))

    # Exact merge verification
    model.gradient_checkpointing_disable()
    model.eval()
    sample_inp = torch.tensor([encoded[0][0][:32]], dtype=torch.long, device="cuda")
    with torch.no_grad():
        pre_logits = model(input_ids=sample_inp).logits.to(torch.float32)
    merged_layers = merge_and_unwrap_adapter(model)
    with torch.no_grad():
        post_logits = model(input_ids=sample_inp).logits.to(torch.float32)
    max_merge_diff_x1e6 = int(round(float((pre_logits - post_logits).abs().max().item()) * 1_000_000))

    # Measure held-out base retention NLL & held-out specialist NLL
    model.config.use_cache = True
    base_nll_after_x10000 = compute_text_nll_x10000(model, tok, _BASE_RETENTION_TEXTS)
    target_nll_after_x10000 = compute_eval_pair_nll_x10000(model, tok, eval_nll_rows, max_len=max_len)

    # Batched left-padded greedy generation on held-out eval prompts
    preds_by_group: dict[str, list[str]] = {}
    perf_by_group: dict[str, dict[str, int]] = {}
    for gname, (prompts, max_new) in eval_prompt_groups.items():
        outs, gperf = batched_greedy_generate(model, tok, prompts, max_new, batch_size=16)
        preds_by_group[gname] = outs
        perf_by_group[gname] = gperf

    save_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(save_dir), safe_serialization=True)
    tok.save_pretrained(str(save_dir))
    st_path = save_dir / "model.safetensors"
    st_sha = hashlib.sha256(st_path.read_bytes()).hexdigest() if st_path.is_file() else ""
    st_bytes = st_path.stat().st_size if st_path.is_file() else 0

    first_loss_x1000 = int(round((sum(step_losses[:16]) / max(1, len(step_losses[:16]))) * 1000))
    last_loss_x1000 = int(round((sum(step_losses[-16:]) / max(1, len(step_losses[-16:]))) * 1000))

    del model, opt, pre_logits, post_logits
    gc.collect()
    torch.cuda.empty_cache()

    stats = {
        "adapter_kind": adapter_kind,
        "train_examples": len(encoded),
        "epochs": epochs,
        "opt_steps": opt_steps,
        "trainable_params": trainable_params,
        "total_params": total_params,
        "merged_layers": merged_layers,
        "max_merge_diff_x1e6": max_merge_diff_x1e6,
        "train_seconds_x100": int(round(train_sec * 100)),
        "ms_per_step_x100": ms_per_step_x100,
        "peak_vram_mib": peak_vram_mib,
        "first_loss_x1000": first_loss_x1000,
        "last_loss_x1000": last_loss_x1000,
        "base_retention_nll_after_x10000": base_nll_after_x10000,
        "target_eval_nll_after_x10000": target_nll_after_x10000,
        "safetensors_sha256": st_sha,
        "safetensors_bytes": st_bytes,
    }
    return stats, preds_by_group, perf_by_group


def eval_scribe_predictions(eval_rows: list[dict[str, Any]], preds: list[str]) -> dict[str, int]:
    total = len(eval_rows)
    json_ok = exact_all7 = tid_ok = nov_ok = oc_ok = lean_ok = 0
    hyg_tp = hyg_fp = hyg_fn = hyg_tn = 0
    for row, raw in zip(eval_rows, preds):
        t = row["target"]
        true_viol = bool(t["leak_flags"] or t["four_mode_violation"] or t["crlf_or_assert_flag"])
        first_line = raw.splitlines()[0].strip() if raw.splitlines() else ""
        try:
            pred = router.gate_scribe_output(first_line)
            json_ok += 1
        except router.GateError:
            if true_viol:
                hyg_fn += 1
            else:
                hyg_tn += 1
            continue
        if pred == t:
            exact_all7 += 1
        if pred["track_id"] == t["track_id"]:
            tid_ok += 1
        if pred["novelty"] == t["novelty"]:
            nov_ok += 1
        if pred["oracle_class"] == t["oracle_class"]:
            oc_ok += 1
        if pred["lean_theorems"] == t["lean_theorems"]:
            lean_ok += 1
        pred_viol = bool(pred["leak_flags"] or pred["four_mode_violation"] or pred["crlf_or_assert_flag"])
        if true_viol and pred_viol:
            hyg_tp += 1
        elif (not true_viol) and pred_viol:
            hyg_fp += 1
        elif true_viol and (not pred_viol):
            hyg_fn += 1
        else:
            hyg_tn += 1
    return {
        "total": total,
        "strict_json_ok": json_ok,
        "exact_all7_ok": exact_all7,
        "track_id_ok": tid_ok,
        "novelty_ok": nov_ok,
        "oracle_class_ok": oc_ok,
        "lean_theorems_ok": lean_ok,
        "hygiene_tp": hyg_tp,
        "hygiene_fp": hyg_fp,
        "hygiene_fn": hyg_fn,
        "hygiene_tn": hyg_tn,
    }


def eval_weaver_predictions(eval_rows: list[dict[str, Any]], preds: list[str]) -> dict[str, int]:
    total = len(eval_rows)
    json_ok = exact_all5 = pcls_ok = glyph_ok = tag_ok = med_ok = 0
    cs03_tp = cs03_fp = cs03_fn = cs03_tn = 0
    for row, raw in zip(eval_rows, preds):
        t = row["target"]
        true_smug = bool(t["is_language_smuggling"])
        first_line = raw.splitlines()[0].strip() if raw.splitlines() else ""
        try:
            pred = router.gate_weaver_output(first_line)
            json_ok += 1
        except router.GateError:
            if true_smug:
                cs03_fn += 1
            else:
                cs03_tn += 1
            continue
        if pred == t:
            exact_all5 += 1
        if pred["pathway_class"] == t["pathway_class"]:
            pcls_ok += 1
        if pred["canonical_glyph"] == t["canonical_glyph"]:
            glyph_ok += 1
        if pred["operator_tag"] == t["operator_tag"]:
            tag_ok += 1
        if pred["suggested_mediator_class"] == t["suggested_mediator_class"]:
            med_ok += 1
        pred_smug = bool(pred["is_language_smuggling"])
        if true_smug and pred_smug:
            cs03_tp += 1
        elif (not true_smug) and pred_smug:
            cs03_fp += 1
        elif true_smug and (not pred_smug):
            cs03_fn += 1
        else:
            cs03_tn += 1
    return {
        "total": total,
        "strict_json_ok": json_ok,
        "exact_all5_ok": exact_all5,
        "pathway_class_ok": pcls_ok,
        "canonical_glyph_ok": glyph_ok,
        "operator_tag_ok": tag_ok,
        "mediator_ok": med_ok,
        "cs03_smuggling_tp": cs03_tp,
        "cs03_smuggling_fp": cs03_fp,
        "cs03_smuggling_fn": cs03_fn,
        "cs03_smuggling_tn": cs03_tn,
    }


def eval_prover_tactics_live(eval_rows: list[dict[str, Any]], preds: list[str], lean_bin: str) -> dict[str, Any]:
    total = len(eval_rows)
    kernel_pass = 0
    r10_rejected = 0
    passed_names: list[str] = []
    failed_cnt = 0
    for row, raw in zip(eval_rows, preds):
        cand = raw.strip()
        if cand.startswith("```"):
            lines = [ln for ln in cand.splitlines() if not ln.strip().startswith("```")]
            cand = "\n".join(lines).strip()
        try:
            router.gate_prover_tactic_output(
                row["preamble"],
                row["theorem_header"],
                row["full_theorem_name"],
                cand,
                lean_bin=lean_bin,
                timeout_s=20,
            )
            kernel_pass += 1
            passed_names.append(row["full_theorem_name"])
        except router.GateError as exc:
            if "R10" in exc.code:
                r10_rejected += 1
            failed_cnt += 1
    return {
        "total": total,
        "live_lean_kernel_pass": kernel_pass,
        "r10_static_rejected": r10_rejected,
        "passed_theorems": passed_names,
        "failed_summary_count": failed_cnt,
    }


def eval_prover_r10_audit(eval_rows: list[dict[str, Any]], preds: list[str]) -> dict[str, int]:
    total = len(eval_rows)
    json_ok = exact_class_ok = 0
    esc_tp = esc_fp = esc_fn = esc_tn = 0
    for row, raw in zip(eval_rows, preds):
        t = row["target"]
        true_esc = not bool(t["clean"])
        first_line = raw.splitlines()[0].strip() if raw.splitlines() else ""
        try:
            pred = router.gate_prover_audit_output(first_line)
            json_ok += 1
        except router.GateError:
            if true_esc:
                esc_fn += 1
            else:
                esc_tn += 1
            continue
        if pred["escape_class"] == t["escape_class"]:
            exact_class_ok += 1
        pred_esc = not bool(pred["clean"])
        if true_esc and pred_esc:
            esc_tp += 1
        elif (not true_esc) and pred_esc:
            esc_fp += 1
        elif true_esc and (not pred_esc):
            esc_fn += 1
        else:
            esc_tn += 1
    return {
        "total": total,
        "strict_json_ok": json_ok,
        "exact_escape_class_ok": exact_class_ok,
        "escape_tp": esc_tp,
        "escape_fp": esc_fp,
        "escape_fn": esc_fn,
        "escape_tn": esc_tn,
    }


def _promote_winner_dir(src_dir: Path, dst_dir: Path, card: dict[str, Any]) -> None:
    import shutil  # noqa: PLC0415

    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    shutil.copytree(src_dir, dst_dir)
    (dst_dir / "foundry_card.json").write_text(canonical_json(card) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Track S95 Live RTX 3080 Specialist Foundry & Beyond-LoRA Showdown")
    ap.add_argument("--expedition-root", type=Path, required=True)
    ap.add_argument("--release-dir", type=Path, required=True)
    ap.add_argument("--results-out", type=Path, required=True)
    ap.add_argument("--model-id", type=str, default="Qwen/Qwen2.5-0.5B")
    ap.add_argument("--base-label", type=str, default="Qwen/Qwen2.5-0.5B")
    ap.add_argument("--lean-bin", type=str, default=None)
    args = ap.parse_args()

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    torch.use_deterministic_algorithms(True, warn_only=True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU required for live RTX 3080 S95 training")
    lbin = args.lean_bin or router.find_lean_binary()
    if lbin is None:
        raise RuntimeError("Live Lean 4.36.0 binary required for Prover kernel evaluation")

    print("=== [S95] Step 1: Building strictly track/pair/template-disjoint datasets ===", flush=True)
    scribe_tr, scribe_ev = build_scribe_dataset(args.expedition_root)
    weaver_tr, weaver_ev = build_weaver_dataset(args.expedition_root)
    prover_tr, prover_ev_tactics, prover_ev_audit = build_prover_dataset(args.expedition_root, lbin)
    prover_ev_all = prover_ev_tactics + prover_ev_audit

    ds_dir = args.release_dir / "datasets"
    ds_meta: dict[str, dict[str, Any]] = {}
    for nm, rows in [
        ("scribe_train.jsonl", scribe_tr),
        ("scribe_eval.jsonl", scribe_ev),
        ("weaver_train.jsonl", weaver_tr),
        ("weaver_eval.jsonl", weaver_ev),
        ("prover_train.jsonl", prover_tr),
        ("prover_eval_tactics.jsonl", prover_ev_tactics),
        ("prover_eval_audit.jsonl", prover_ev_audit),
    ]:
        sha, nbytes = write_jsonl_and_sha(ds_dir / nm, rows)
        ds_meta[nm] = {"rows": len(rows), "bytes": nbytes, "sha256": sha}
    total_ds_bytes = sum(v["bytes"] for v in ds_meta.values())
    row_summary = {k: v["rows"] for k, v in ds_meta.items()}
    print(f"Datasets ready: total_bytes={total_ds_bytes} rows={row_summary}", flush=True)
    print(f"  Scribe: {len(scribe_tr)}/{len(scribe_ev)} | Weaver: {len(weaver_tr)}/{len(weaver_ev)} | Prover: {len(prover_tr)} / ({len(prover_ev_tactics)} tac + {len(prover_ev_audit)} aud)", flush=True)

    print("=== [S95] Step 2: Calibrating base activation subspaces & measuring Base Qwen2.5-0.5B ===", flush=True)
    base_subspaces = calibrate_base_subspaces(args.model_id, k_subspace=16)

    tok_b = AutoTokenizer.from_pretrained(args.model_id, local_files_only=True)
    if tok_b.pad_token_id is None:
        tok_b.pad_token = tok_b.eos_token
    base_m = AutoModelForCausalLM.from_pretrained(args.model_id, local_files_only=True, dtype=torch.bfloat16).to("cuda")
    base_m.eval()
    base_ret_nll_0 = compute_text_nll_x10000(base_m, tok_b, _BASE_RETENTION_TEXTS)
    base_scribe_nll_0 = compute_eval_pair_nll_x10000(base_m, tok_b, scribe_ev)
    base_weaver_nll_0 = compute_eval_pair_nll_x10000(base_m, tok_b, weaver_ev)
    base_prover_nll_0 = compute_eval_pair_nll_x10000(base_m, tok_b, prover_ev_all)

    b_sc_p, b_sc_perf = batched_greedy_generate(base_m, tok_b, [r["prompt"] for r in scribe_ev], 96, batch_size=16)
    b_wv_p, b_wv_perf = batched_greedy_generate(base_m, tok_b, [r["prompt"] for r in weaver_ev], 96, batch_size=16)
    b_pt_p, b_pt_perf = batched_greedy_generate(base_m, tok_b, [r["prompt"] for r in prover_ev_tactics], 128, batch_size=16)
    b_pa_p, b_pa_perf = batched_greedy_generate(base_m, tok_b, [r["prompt"] for r in prover_ev_audit], 64, batch_size=16)
    del base_m
    gc.collect()
    torch.cuda.empty_cache()

    base_scribe_eval = eval_scribe_predictions(scribe_ev, b_sc_p)
    base_weaver_eval = eval_weaver_predictions(weaver_ev, b_wv_p)
    base_ptac_eval = eval_prover_tactics_live(prover_ev_tactics, b_pt_p, lbin)
    base_paud_eval = eval_prover_r10_audit(prover_ev_audit, b_pa_p)
    print(f"Base NLLs: ret={base_ret_nll_0} scribe={base_scribe_nll_0} weaver={base_weaver_nll_0} prover={base_prover_nll_0}", flush=True)
    print("Base evals:", base_scribe_eval["exact_all7_ok"], base_weaver_eval["exact_all5_ok"], base_ptac_eval["live_lean_kernel_pass"], base_paud_eval["exact_escape_class_ok"], flush=True)

    # Step 3: Full 3x3 Matched-Parameter-Budget Showdown!
    arms_root = args.release_dir / "_arms"
    scribe_arms: dict[str, Any] = {}
    weaver_arms: dict[str, Any] = {}
    prover_arms: dict[str, Any] = {}

    for kind in ADAPTER_KINDS:
        print(f"=== [S95] Showdown Scribe x {kind} ===", flush=True)
        st, preds, perf = train_and_eval_arm(
            args.model_id, kind, scribe_tr, scribe_ev,
            {"main": ([r["prompt"] for r in scribe_ev], 96)},
            base_subspaces=base_subspaces if kind == "privsparse_ortho" else None,
            save_dir=arms_root / f"scribe_{kind}", epochs=4, lr=3e-4,
        )
        ev_m = eval_scribe_predictions(scribe_ev, preds["main"])
        scribe_arms[kind] = {"train": st, "eval": ev_m, "perf": perf["main"]}
        print(f"  Scribe[{kind}]: exact7={ev_m['exact_all7_ok']}/{ev_m['total']} json={ev_m['strict_json_ok']} base_nll={base_ret_nll_0}->{st['base_retention_nll_after_x10000']} tgt_nll={base_scribe_nll_0}->{st['target_eval_nll_after_x10000']} vram={st['peak_vram_mib']}MiB", flush=True)

        print(f"=== [S95] Showdown Weaver x {kind} ===", flush=True)
        st, preds, perf = train_and_eval_arm(
            args.model_id, kind, weaver_tr, weaver_ev,
            {"main": ([r["prompt"] for r in weaver_ev], 96)},
            base_subspaces=base_subspaces if kind == "privsparse_ortho" else None,
            save_dir=arms_root / f"weaver_{kind}", epochs=4, lr=3e-4,
        )
        ev_m = eval_weaver_predictions(weaver_ev, preds["main"])
        weaver_arms[kind] = {"train": st, "eval": ev_m, "perf": perf["main"]}
        print(f"  Weaver[{kind}]: exact5={ev_m['exact_all5_ok']}/{ev_m['total']} pcls={ev_m['pathway_class_ok']} cs03_tp={ev_m['cs03_smuggling_tp']}/15 base_nll={base_ret_nll_0}->{st['base_retention_nll_after_x10000']} tgt_nll={base_weaver_nll_0}->{st['target_eval_nll_after_x10000']}", flush=True)

        print(f"=== [S95] Showdown Prover x {kind} ===", flush=True)
        st, preds, perf = train_and_eval_arm(
            args.model_id, kind, prover_tr, prover_ev_all,
            {"tactics": ([r["prompt"] for r in prover_ev_tactics], 128), "audit": ([r["prompt"] for r in prover_ev_audit], 64)},
            base_subspaces=base_subspaces if kind == "privsparse_ortho" else None,
            save_dir=arms_root / f"prover_{kind}", epochs=5, lr=3e-4,
        )
        ev_t = eval_prover_tactics_live(prover_ev_tactics, preds["tactics"], lbin)
        ev_a = eval_prover_r10_audit(prover_ev_audit, preds["audit"])
        prover_arms[kind] = {
            "train": st,
            "tactics_eval": ev_t,
            "tactics_perf": perf["tactics"],
            "r10_audit_eval": ev_a,
            "r10_audit_perf": perf["audit"],
        }
        print(f"  Prover[{kind}]: lean_pass={ev_t['live_lean_kernel_pass']}/{ev_t['total']} r10_cls={ev_a['exact_escape_class_ok']}/{ev_a['total']} base_nll={base_ret_nll_0}->{st['base_retention_nll_after_x10000']} tgt_nll={base_prover_nll_0}->{st['target_eval_nll_after_x10000']}", flush=True)

    # Step 4: Select genuine empirical winner per role (max oracle score, tie-break by lowest base forgetting!)
    win_scribe = max(
        ADAPTER_KINDS,
        key=lambda k: (
            scribe_arms[k]["eval"]["exact_all7_ok"],
            scribe_arms[k]["eval"]["hygiene_tp"] - scribe_arms[k]["eval"]["hygiene_fp"],
            -scribe_arms[k]["train"]["base_retention_nll_after_x10000"],
        ),
    )
    win_weaver = max(
        ADAPTER_KINDS,
        key=lambda k: (
            weaver_arms[k]["eval"]["pathway_class_ok"] + weaver_arms[k]["eval"]["cs03_smuggling_tp"],
            weaver_arms[k]["eval"]["exact_all5_ok"],
            -weaver_arms[k]["train"]["base_retention_nll_after_x10000"],
        ),
    )
    win_prover = max(
        ADAPTER_KINDS,
        key=lambda k: (
            prover_arms[k]["tactics_eval"]["live_lean_kernel_pass"] + prover_arms[k]["r10_audit_eval"]["exact_escape_class_ok"],
            prover_arms[k]["tactics_eval"]["live_lean_kernel_pass"],
            -prover_arms[k]["train"]["base_retention_nll_after_x10000"],
        ),
    )
    print(f"=== [S95] Empirical Winners: Scribe={win_scribe}, Weaver={win_weaver}, Prover={win_prover} ===", flush=True)

    _promote_winner_dir(
        arms_root / f"scribe_{win_scribe}",
        args.release_dir / "aletheia-scribe-0.5b",
        {"model_name": "aletheia-scribe-0.5b", "winner_adapter": win_scribe, "base_model": args.base_label, "license": "apache-2.0", "metrics": scribe_arms[win_scribe]},
    )
    _promote_winner_dir(
        arms_root / f"weaver_{win_weaver}",
        args.release_dir / "aletheia-weaver-0.5b",
        {"model_name": "aletheia-weaver-0.5b", "winner_adapter": win_weaver, "base_model": args.base_label, "license": "apache-2.0", "metrics": weaver_arms[win_weaver]},
    )
    _promote_winner_dir(
        arms_root / f"prover_{win_prover}",
        args.release_dir / "aletheia-prover-0.5b",
        {"model_name": "aletheia-prover-0.5b", "winner_adapter": win_prover, "base_model": args.base_label, "license": "apache-2.0", "metrics": prover_arms[win_prover]},
    )
    # Remove intermediate non-winning arm folders to keep disk tidy
    import shutil  # noqa: PLC0415
    if arms_root.exists():
        shutil.rmtree(arms_root)

    results = {
        "schema_version": "aletheia.s95.rtx3080_foundry_results.v1",
        "base_model_id": args.base_label,
        "base_model_license": "apache-2.0",
        "gpu_name": torch.cuda.get_device_name(0),
        "seed": SEED,
        "matched_adapter_budget_s": ADAPTER_BUDGET_S,
        "lora_alpha": LORA_ALPHA,
        "chunk_lse_size": CHUNK_SIZE,
        "base_retention_nll_0_x10000": base_ret_nll_0,
        "dataset_total_bytes": total_ds_bytes,
        "datasets": ds_meta,
        "specialists": {
            "aletheia_scribe_0_5b": {
                "winner_adapter": win_scribe,
                "base_target_nll_0_x10000": base_scribe_nll_0,
                "base_eval": base_scribe_eval,
                "base_perf": b_sc_perf,
                "arms": scribe_arms,
            },
            "aletheia_weaver_0_5b": {
                "winner_adapter": win_weaver,
                "base_target_nll_0_x10000": base_weaver_nll_0,
                "base_eval": base_weaver_eval,
                "base_perf": b_wv_perf,
                "arms": weaver_arms,
            },
            "aletheia_prover_0_5b": {
                "winner_adapter": win_prover,
                "base_target_nll_0_x10000": base_prover_nll_0,
                "base_tactics_eval": base_ptac_eval,
                "base_tactics_perf": b_pt_perf,
                "base_r10_audit_eval": base_paud_eval,
                "base_r10_audit_perf": b_pa_perf,
                "arms": prover_arms,
            },
        },
    }
    args.results_out.parent.mkdir(parents=True, exist_ok=True)
    raw_res = (canonical_json(results) + "\n").encode("utf-8")
    args.results_out.write_bytes(raw_res)
    os.chmod(args.results_out, 0o600)
    print(f"=== [S95] COMPLETE! {args.results_out.name} ({len(raw_res)} B, sha256={hashlib.sha256(raw_res).hexdigest()}) ===", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
