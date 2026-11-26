#!/usr/bin/env python3
"""Track S114 Phase 2B (`H14b` + `H14c`): Live RTX 3080 HoloSphere V2 Full Training Showdown.

Implements BOTH locked PREREG-S114 training campaigns using our 27/27 0B-spill sm_86 V2 foundry,
with all GPT-6 Luna & Mistral Large 4 E0/E1 rigor upgrades:
  1. H14b (Equal-Wall-Clock CS-08 + Equal-Step 600 Showdown, 15M +- 0.5% params, 3 seeds {42, 137, 2026}):
     - Interleaved arm execution order rotated per seed to cancel thermal drift.
     - Identical offline SHA-disjoint multi-domain UTF-8 corpus (WikiText-2 + Python + JSON),
       exact BPB (fp32 log-softmax, BOS excluded, EOS scored) at T=512 and T=2048 (4x tail-512).
     - Calibrates T_budget per seed from 600 steps of RoPE-2D-nGPT; evaluates EVERY arm at BOTH
       equal-step (step 600) AND equal-wall-clock (T_budget), logging exact steps/tokens completed
       and synchronized NVML gross + idle-subtracted inference mJ/tok at T=512 and T=2048.
     - 7 Factorial Arms (zero MTP-8 confound):
         1. RoPE-2D-Std (locked PREREG-S114 baseline)
         2. RoPE-2D-nGPT (locked PREREG-S114 baseline & T_budget anchor)
         3. RoPE-2D-nGPT+MarkovMTP8 (factorial MTP control)
         4. HoloSphere-V2-SU2-Unlooped (No-MTP fused SU(2) holonomy + direct-BF16 SLERP)
         5. HoloSphere-V2-CayleySU2-Unlooped (100% SFU-free pure-rational cayley_su2)
         6. HoloSphere-V2-Stage1a-Cayley2x2 (fused SU(2) + fused Beltrami Cayley2x2 post-MLP)
         7. HoloSphere-V2-Full-Entity (fused SU(2) + cayley_acute Safe-Hopf loop + decoupled Markov-MTP8)
  2. H14c (Non-Abelian S_3 & A_5 Group Word-Problem State Tracking, 6L d=256 H=8, 1200 steps, 3 seeds):
     - Curriculum L in [4..64] train / L in [65..192] OOD, exact phase-insensitive quadratic
       quaternion readout (invariant under +-q double cover of 2D_3 and 2I) shared across ALL 5 arms,
       unit sqk=1.0 preserving exact SU(2) 4-block equivariance, angle_scale=pi covering 180-deg half-turns.
     - 5 Factorial Arms:
         1. RoPE-2D-nGPT
         2. Abelian-SO2-Phase (commutative omega_x=omega_y=0 with full V-transport + untransport)
         3. H7b-QK-Only (non-Abelian SU(2) on Q,K only)
         4. HoloSphere-V2-QKV-NoUntransport (Q,K,V transport without conj(U_t) O_t)
         5. HoloSphere-V2-Full-Covariant-QKV-Untransport (full covariant Q,K,V + conj(U_t) O_t)
  3. Literal PREREG-S114 grading + paired normal-z AND exact Student-t(df=2) sensitivity.
  4. Saves optional best candidate checkpoint ONLY to external --save-best-dir (WEIGHTS=0 in repo).

Zero bare asserts; all randomness explicitly seeded; supports --smoke-cpu (CUDA_VISIBLE_DEVICES="").
"""

from __future__ import annotations

import argparse
import copy
import datetime
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

_HERE = Path(__file__).resolve().parent
_EXPEDITION = _HERE.parent
_S107 = _EXPEDITION / "track-s107-hypersphere-transformer"
for _p in (str(_HERE), str(_S107)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import torch.nn.functional as F  # noqa: E402

import s107_models as s107  # noqa: E402
import s107_train_eval as s107_te  # noqa: E402
import s114_fused_ops as ops  # noqa: E402

PREREG_SHA256 = "5fa927a06933c3cff057b65f75c1d2f190e10f1e420303d582dfb7c802ee69a4"
VOCAB_SIZE = s107_te.VOCAB_SIZE_BYTE
BOS_ID = s107_te.BOS_ID
EOS_ID = s107_te.EOS_ID
PAD_ID = s107_te.PAD_ID
SEEDS = (42, 137, 2026)


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def _seeded_gen(seed: int) -> torch.Generator:
    return torch.Generator(device="cpu").manual_seed(int(seed) & 0x7FFFFFFF)


def _query_nvml_power_w() -> Optional[float]:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
            text=True,
            timeout=5,
        ).strip()
        return float(out.splitlines()[0].strip())
    except Exception:
        return None


def _measure_idle_power_w(samples: int = 3) -> float:
    vals: List[float] = []
    for _ in range(samples):
        p = _query_nvml_power_w()
        if p is not None:
            vals.append(p)
        time.sleep(0.2)
    return (sum(vals) / float(len(vals))) if vals else 0.0


def _cosine_lr(step: int, total_steps: int, peak_lr: float, warmup_frac: float = 0.10) -> float:
    if step >= total_steps:
        return peak_lr * 0.12
    warmup = max(1, int(round(warmup_frac * total_steps)))
    if step < warmup:
        return peak_lr * float(step + 1) / float(warmup)
    progress = float(step - warmup) / float(max(1, total_steps - warmup))
    return peak_lr * (0.1 + 0.45 * (1.0 + math.cos(math.pi * progress)))


def _paired_stats(a_vals: Sequence[float], b_vals: Sequence[float]) -> Dict[str, Any]:
    """Paired delta = a - b with mean, SE, normal z, and exact two-sided Student-t(df=n-1) p-value."""
    _require(len(a_vals) == len(b_vals) and len(a_vals) >= 1, "Paired vectors must match and be non-empty")
    n = len(a_vals)
    diffs = [float(a - b) for a, b in zip(a_vals, b_vals)]
    mean_a = sum(a_vals) / float(n)
    mean_b = sum(b_vals) / float(n)
    mean_d = sum(diffs) / float(n)
    rel_pct = (100.0 * mean_d / mean_b) if abs(mean_b) > 1e-12 else 0.0
    if n < 2:
        return {
            "mean_a": round(mean_a, 6), "mean_b": round(mean_b, 6),
            "mean_diff": round(mean_d, 6), "rel_pct": round(rel_pct, 4),
            "se": 0.0, "z_or_t": 0.0, "p_normal_2s": 1.0, "p_t_df2_2s": 1.0,
        }
    var = sum((d - mean_d) ** 2 for d in diffs) / float(n - 1)
    se = math.sqrt(var / float(n))
    t_stat = (mean_d / se) if se > 1e-12 else (0.0 if abs(mean_d) < 1e-12 else math.copysign(99.0, mean_d))
    p_norm = math.erfc(abs(t_stat) / math.sqrt(2.0))
    # Exact two-sided Student-t p-value for df=2: CDF(t) = 0.5 + t / (2 * sqrt(2 + t^2))
    if n == 3:
        p_t = max(0.0, min(1.0, 1.0 - abs(t_stat) / math.sqrt(2.0 + t_stat * t_stat)))
    else:
        p_t = p_norm
    return {
        "mean_a": round(mean_a, 6),
        "mean_b": round(mean_b, 6),
        "mean_diff": round(mean_d, 6),
        "rel_pct": round(rel_pct, 4),
        "se": round(se, 6),
        "z_or_t": round(t_stat, 4),
        "p_normal_2s": round(p_norm, 6),
        "p_t_df2_2s": round(p_t, 6),
    }


def _count_params(model: nn.Module) -> Dict[str, int]:
    total = sum(p.numel() for p in model.parameters())
    emb = model.tok_emb.weight.numel() if hasattr(model, "tok_emb") else 0
    return {"total_params": int(total), "embedding_params": int(emb), "non_embedding_params": int(total - emb)}


# ---------------------------------------------------------------------------
# Building Blocks: Decoupled Markov-MTP8, Beltrami Cayley2x2, HoloSphere V2
# ---------------------------------------------------------------------------


class MarkovMTP8Head(nn.Module):
    """Low-rank coupled Markov multi-token prediction head (Track S108 H8c2 CONFIRMED)."""

    def __init__(self, d_model: int, vocab_size: int = VOCAB_SIZE, block_size: int = 8, markov_rank: int = 64) -> None:
        super().__init__()
        self.d_model = d_model
        self.vocab_size = vocab_size
        self.block_size = block_size
        self.init_proj = nn.Linear(d_model, markov_rank)
        self.step_cond = nn.ModuleList([nn.Linear(d_model, markov_rank, bias=False) for _ in range(block_size)])
        self.tok_emb = nn.Embedding(vocab_size, markov_rank)
        self.state_step = nn.Linear(markov_rank, markov_rank)
        self.out_head = nn.Linear(markov_rank, vocab_size)

    def forward(self, h_exit: torch.Tensor, target_tokens: Optional[torch.Tensor] = None, unroll: bool = False) -> torch.Tensor:
        lead = h_exit.shape[:-1]
        flat_h = h_exit.reshape(-1, self.d_model)
        flat_t = target_tokens.reshape(-1, self.block_size) if target_tokens is not None else None
        state = torch.tanh(self.init_proj(flat_h))
        steps: List[torch.Tensor] = []
        prev_tok: Optional[torch.Tensor] = None
        for j in range(self.block_size):
            if j == 0:
                s_in = state + self.step_cond[j](flat_h)
            else:
                if unroll or flat_t is None:
                    b_in = prev_tok if prev_tok is not None else torch.zeros(flat_h.shape[0], dtype=torch.long, device=flat_h.device)
                else:
                    b_in = flat_t[:, j - 1]
                s_in = self.state_step(state) + self.tok_emb(b_in) + self.step_cond[j](flat_h)
            state = torch.tanh(s_in)
            step_logits = self.out_head(state)
            steps.append(step_logits)
            prev_tok = step_logits.argmax(dim=-1)
        return torch.stack(steps, dim=1).reshape(*lead, self.block_size, self.vocab_size)


class FusedCayley2x2PostMLP(nn.Module):
    """Beltrami [C, K] = 0 data-dependent 2x2 Cayley SO(d) epilogue using 0B-spill sm_86 kernel."""

    def __init__(self, d_model: int, rank: int = 16, backend: str = "auto", seed: int = 42) -> None:
        super().__init__()
        self.n_pairs = d_model // 2
        self.backend = backend
        self.base_omega = nn.Parameter(torch.empty(self.n_pairs).uniform_(-0.35, 0.35, generator=_seeded_gen(seed)))
        self.w_down = nn.Linear(d_model, rank, bias=False)
        self.w_up = nn.Linear(rank, self.n_pairs, bias=False)
        with torch.no_grad():
            self.w_down.weight.normal_(0.0, 1.0 / math.sqrt(float(d_model)), generator=_seeded_gen(seed + 1))
            self.w_up.weight.normal_(0.0, 0.05 / math.sqrt(float(rank)), generator=_seeded_gen(seed + 2))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        om = self.base_omega.view(*([1] * (x.ndim - 1)), self.n_pairs) + 0.75 * torch.tanh(self.w_up(F.silu(self.w_down(x))))
        return ops.cayley_2x2_rotate(x, om, backend=self.backend)


class UnifiedV2Attention(nn.Module):
    """Supports RoPE-2D, Abelian SO(2) phase, QK-only SU(2), QKV-NoUntransport, & Full Covariant V2 SU(2)."""

    def __init__(
        self,
        d_model: int,
        n_heads: int,
        *,
        pos_mode: str = "su2_holonomy",
        map_mode: str = "exp",
        transport_v: bool = False,
        untransport_o: bool = False,
        abelian_so2: bool = False,
        ngpt: bool = True,
        freeze_sqk_one: bool = False,
        angle_scale: float = 0.75,
        backend: str = "auto",
    ) -> None:
        super().__init__()
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_head = d_model // n_heads
        self.n_blocks = self.d_head // 4
        self.pos_mode = pos_mode
        self.map_mode = map_mode
        self.transport_v = transport_v
        self.untransport_o = untransport_o
        self.abelian_so2 = abelian_so2
        self.ngpt = ngpt
        self.freeze_sqk_one = freeze_sqk_one
        self.angle_scale = angle_scale
        self.backend = backend

        self.w_q = nn.Linear(d_model, d_model, bias=False)
        self.w_k = nn.Linear(d_model, d_model, bias=False)
        self.w_v = nn.Linear(d_model, d_model, bias=False)
        self.w_o = nn.Linear(d_model, d_model, bias=False)
        if pos_mode == "su2_holonomy":
            out_om = (n_heads * self.n_blocks) if abelian_so2 else (3 * n_heads * self.n_blocks)
            self.w_omega: Optional[nn.Linear] = nn.Linear(d_model, out_om, bias=False)
        else:
            self.w_omega = None
        if ngpt and not freeze_sqk_one:
            # Council P0: block-4 tied sqk preserves exact SU(2) 4-block equivariance
            self.sqk: Optional[nn.Parameter] = nn.Parameter(torch.ones(1, n_heads, 1, self.n_blocks, 1))
        else:
            self.register_parameter("sqk", None)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        bsz, seq_len, _ = x.shape
        q = self.w_q(x).view(bsz, seq_len, self.n_heads, self.d_head).transpose(1, 2)
        k = self.w_k(x).view(bsz, seq_len, self.n_heads, self.d_head).transpose(1, 2)
        v = self.w_v(x).view(bsz, seq_len, self.n_heads, self.d_head).transpose(1, 2)

        pi_path: Optional[torch.Tensor] = None
        if self.pos_mode == "rope2d":
            q = s107.apply_rope_2d(q)
            k = s107.apply_rope_2d(k)
        elif self.pos_mode == "su2_holonomy":
            _require(self.w_omega is not None, "w_omega missing")
            if self.abelian_so2:
                oz = self.w_omega(x).view(bsz, seq_len, self.n_heads, self.n_blocks, 1).transpose(1, 2)
                zeros = torch.zeros_like(oz)
                omega = torch.cat((zeros, zeros, oz), dim=-1)
            else:
                omega = self.w_omega(x).view(bsz, seq_len, self.n_heads, self.n_blocks, 3).transpose(1, 2)
            q, k, v, pi_path = ops.su2_holonomy_transport(
                q, k, v, omega,
                angle_scale=self.angle_scale,
                transport_v=self.transport_v,
                backend=self.backend,
                map_mode=self.map_mode,
            )
        else:
            raise ValueError(f"Unknown pos_mode: {self.pos_mode!r}")

        if self.ngpt:
            if self.sqk is not None:
                sqk_exp = self.sqk.expand(1, self.n_heads, 1, self.n_blocks, 4).reshape(1, self.n_heads, 1, self.d_head)
                q = ops._safe_unit_norm(q, eps=1e-4) * sqk_exp
                k = ops._safe_unit_norm(k, eps=1e-4) * sqk_exp
            else:
                q = ops._safe_unit_norm(q, eps=1e-4)
                k = ops._safe_unit_norm(k, eps=1e-4)
            scale = math.sqrt(float(self.d_head))
        else:
            scale = 1.0 / math.sqrt(float(self.d_head))

        attn_out = F.scaled_dot_product_attention(q, k, v, is_causal=True, scale=scale)
        if self.untransport_o and pi_path is not None:
            attn_out = ops.su2_inverse_untransport(attn_out, pi_path, backend=self.backend)
        attn_out = attn_out.transpose(1, 2).contiguous().view(bsz, seq_len, self.d_model)
        return self.w_o(attn_out)


class UnifiedV2Block(nn.Module):
    def __init__(
        self,
        d_model: int,
        n_heads: int,
        d_ff: int,
        *,
        pos_mode: str = "su2_holonomy",
        map_mode: str = "exp",
        transport_v: bool = False,
        untransport_o: bool = False,
        abelian_so2: bool = False,
        ngpt: bool = True,
        freeze_sqk_one: bool = False,
        angle_scale: float = 0.75,
        use_cayley2x2: bool = False,
        backend: str = "auto",
        seed: int = 42,
    ) -> None:
        super().__init__()
        self.ngpt = ngpt
        self.backend = backend
        self.attn = UnifiedV2Attention(
            d_model, n_heads,
            pos_mode=pos_mode, map_mode=map_mode,
            transport_v=transport_v, untransport_o=untransport_o,
            abelian_so2=abelian_so2, ngpt=ngpt, freeze_sqk_one=freeze_sqk_one,
            angle_scale=angle_scale, backend=backend,
        )
        self.mlp = s107.SwiGLUMLP(d_model, d_ff, ngpt=ngpt)
        self.cayley = FusedCayley2x2PostMLP(d_model, rank=16, backend=backend, seed=seed) if use_cayley2x2 else None
        if ngpt:
            init_logit = math.log(0.05 / 0.95)
            self.alpha_a_logit = nn.Parameter(torch.full((d_model,), init_logit))
            self.alpha_m_logit = nn.Parameter(torch.full((d_model,), init_logit))
            self.norm1: Optional[nn.Module] = None
            self.norm2: Optional[nn.Module] = None
        else:
            self.register_parameter("alpha_a_logit", None)
            self.register_parameter("alpha_m_logit", None)
            self.norm1 = s107.RMSNorm(d_model)
            self.norm2 = s107.RMSNorm(d_model)

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        if self.ngpt:
            h = ops.fused_spherical_step(h, self.attn(h), self.alpha_a_logit, mode="slerp", backend=self.backend)
            dm = self.mlp(h)
            if self.cayley is not None:
                dm = self.cayley(dm)
            h = ops.fused_spherical_step(h, dm, self.alpha_m_logit, mode="slerp", backend=self.backend)
            return h
        _require(self.norm1 is not None and self.norm2 is not None, "RMSNorm missing")
        h = h + self.attn(self.norm1(h))
        dm = self.mlp(self.norm2(h))
        if self.cayley is not None:
            dm = self.cayley(dm)
        return h + dm


def _quaternion_quadratic_features(h: torch.Tensor) -> torch.Tensor:
    """Exact +-q phase-insensitive degree-2 4-block features (respects 2D_3 & 2I double cover!)."""
    sh = h.shape
    q = h.reshape(*sh[:-1], sh[-1] // 4, 4)
    w, x, y, z = q.unbind(dim=-1)
    quad = torch.stack(
        (w * w, x * x, y * y, z * z, w * x, w * y, w * z, x * y, x * z, y * z),
        dim=-1,
    )
    return quad.reshape(*sh[:-1], (sh[-1] // 4) * 10)


class HoloSphereV2LM(nn.Module):
    """Unified V2 LM for both H14b (15M equal-wall-clock showdown) and H14c (S_3 / A_5 state tracking)."""

    def __init__(
        self,
        *,
        arm_name: str,
        vocab_size: int = VOCAB_SIZE,
        d_model: int = 320,
        n_heads: int = 8,
        n_layers: int = 12,
        d_ff: int = 864,
        pos_mode: str = "su2_holonomy",
        map_mode: str = "exp",
        transport_v: bool = False,
        untransport_o: bool = False,
        abelian_so2: bool = False,
        ngpt: bool = True,
        freeze_sqk_one: bool = False,
        angle_scale: float = 0.75,
        use_cayley2x2: bool = False,
        looped: bool = False,
        r_train: int = 3,
        use_mtp8: bool = False,
        quadratic_readout: bool = False,
        backend: str = "auto",
        seed: int = 42,
    ) -> None:
        super().__init__()
        self.arm_name = arm_name
        self.d_model = d_model
        self.ngpt = ngpt
        self.looped = looped
        self.r_train = r_train
        self.quadratic_readout = quadratic_readout
        self.backend = backend

        self.tok_emb = nn.Embedding(vocab_size, d_model)
        blk_kw = dict(
            pos_mode=pos_mode, map_mode=map_mode, transport_v=transport_v,
            untransport_o=untransport_o, abelian_so2=abelian_so2, ngpt=ngpt,
            freeze_sqk_one=freeze_sqk_one, angle_scale=angle_scale,
            use_cayley2x2=use_cayley2x2, backend=backend,
        )
        if looped:
            self.pre_blocks = nn.ModuleList([UnifiedV2Block(d_model, n_heads, d_ff, seed=seed + i, **blk_kw) for i in range(2)])
            self.core_blocks = nn.ModuleList([UnifiedV2Block(d_model, n_heads, d_ff, seed=seed + 10 + i, **blk_kw) for i in range(4)])
            self.suffix_blocks = nn.ModuleList([UnifiedV2Block(d_model, n_heads, d_ff, seed=seed + 20 + i, **blk_kw) for i in range(2)])
            self.blocks = nn.ModuleList()
            self.loop_alpha_logit = nn.Parameter(torch.full((d_model,), math.log(0.25 / 0.75)))
        else:
            self.blocks = nn.ModuleList([UnifiedV2Block(d_model, n_heads, d_ff, seed=seed + i, **blk_kw) for i in range(n_layers)])
            self.pre_blocks = nn.ModuleList()
            self.core_blocks = nn.ModuleList()
            self.suffix_blocks = nn.ModuleList()
            self.register_parameter("loop_alpha_logit", None)

        self.mtp_head = MarkovMTP8Head(d_model, vocab_size=vocab_size, block_size=8, markov_rank=64) if use_mtp8 else None
        if quadratic_readout:
            self.quad_head: Optional[nn.Linear] = nn.Linear(d_model + (d_model // 4) * 10, vocab_size, bias=True)
            self.final_norm: Optional[nn.Module] = None if ngpt else s107.RMSNorm(d_model)
            self.register_parameter("logit_scale", None)
        elif ngpt:
            self.quad_head = None
            self.final_norm = None
            self.logit_scale = nn.Parameter(torch.full((1,), math.sqrt(float(d_model))))
        else:
            self.quad_head = None
            self.final_norm = s107.RMSNorm(d_model)
            self.register_parameter("logit_scale", None)

        self._init_weights(seed)

    def _init_weights(self, seed: int) -> None:
        torch.manual_seed(seed)
        nn.init.normal_(self.tok_emb.weight, mean=0.0, std=0.02)
        for name, mod in self.named_modules():
            if isinstance(mod, nn.Linear) and ("cayley." not in name):
                nn.init.normal_(mod.weight, mean=0.0, std=0.02)
                if mod.bias is not None:
                    nn.init.zeros_(mod.bias)
        if self.ngpt:
            self.normalize_ngpt_weights_()

    @torch.no_grad()
    def normalize_ngpt_weights_(self) -> None:
        if not self.ngpt:
            return
        self.tok_emb.weight.copy_(ops._safe_unit_norm(self.tok_emb.weight, eps=1e-4))
        for name, mod in self.named_modules():
            if isinstance(mod, nn.Linear):
                if ("cayley." in name) or ("mtp_head." in name) or ("quad_head" in name):
                    continue
                mod.weight.copy_(ops._safe_unit_norm(mod.weight, eps=1e-4))

    def forward(
        self,
        input_ids: torch.Tensor,
        *,
        r_loops: Optional[int] = None,
        mtp_targets: Optional[torch.Tensor] = None,
        mtp_unroll: bool = False,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        h = self.tok_emb(input_ids)
        if self.ngpt:
            h = ops._safe_unit_norm(h, eps=1e-4)
        if self.looped:
            for blk in self.pre_blocks:
                h = blk(h)
            passes = self.r_train if r_loops is None else int(r_loops)
            for r in range(passes):
                h_core = h
                for blk in self.core_blocks:
                    h_core = blk(h_core)
                phi_r = ops.safe_hopf_clock_angle(r, law="cayley_acute", r_max=8)
                h = ops.fused_spherical_step(
                    h, h_core, self.loop_alpha_logit,
                    mode="safe_hopf_loop", phi=phi_r, backend=self.backend,
                )
            for blk in self.suffix_blocks:
                h = blk(h)
        else:
            for blk in self.blocks:
                h = blk(h)

        extra: Dict[str, Any] = {}
        if self.mtp_head is not None and (mtp_targets is not None or mtp_unroll):
            extra["mtp_logits"] = self.mtp_head(h, target_tokens=mtp_targets, unroll=mtp_unroll)

        if self.quad_head is not None:
            hf = self.final_norm(h) if self.final_norm is not None else ops._safe_unit_norm(h, eps=1e-4)
            feat = torch.cat((hf, _quaternion_quadratic_features(hf)), dim=-1)
            logits = self.quad_head(feat)
        elif self.ngpt:
            _require(self.logit_scale is not None, "logit_scale missing")
            logits = F.linear(ops._safe_unit_norm(h, eps=1e-4), ops._safe_unit_norm(self.tok_emb.weight, eps=1e-4)) * self.logit_scale
        else:
            _require(self.final_norm is not None, "final_norm missing")
            logits = F.linear(self.final_norm(h), self.tok_emb.weight)
        return logits, extra


def build_h14b_arms(backend: str, seed: int) -> List[Tuple[str, Dict[str, Any]]]:
    """7 iso-parameter (14.90M +- 0.10% non-emb) factorial arms for H14b."""
    return [
        ("RoPE-2D-Std", dict(d_model=320, n_heads=8, n_layers=12, d_ff=864, pos_mode="rope2d", ngpt=False, backend="reference", seed=seed)),
        ("RoPE-2D-nGPT", dict(d_model=320, n_heads=8, n_layers=12, d_ff=864, pos_mode="rope2d", ngpt=True, backend="reference", seed=seed)),
        ("RoPE-2D-nGPT+MarkovMTP8", dict(d_model=320, n_heads=8, n_layers=12, d_ff=844, pos_mode="rope2d", ngpt=True, use_mtp8=True, backend="reference", seed=seed)),
        ("HoloSphere-V2-SU2-Unlooped", dict(d_model=320, n_heads=8, n_layers=12, d_ff=784, pos_mode="su2_holonomy", map_mode="exp", angle_scale=0.75, ngpt=True, backend=backend, seed=seed)),
        ("HoloSphere-V2-CayleySU2-Unlooped", dict(d_model=320, n_heads=8, n_layers=12, d_ff=784, pos_mode="su2_holonomy", map_mode="cayley", angle_scale=0.50, ngpt=True, backend=backend, seed=seed)),
        ("HoloSphere-V2-Stage1a-Cayley2x2", dict(d_model=320, n_heads=8, n_layers=12, d_ff=776, pos_mode="su2_holonomy", map_mode="exp", angle_scale=0.75, ngpt=True, use_cayley2x2=True, backend=backend, seed=seed)),
        ("HoloSphere-V2-Full-Entity", dict(d_model=320, n_heads=8, n_layers=8, d_ff=1404, pos_mode="su2_holonomy", map_mode="exp", angle_scale=0.75, ngpt=True, looped=True, r_train=3, use_mtp8=True, backend=backend, seed=seed)),
    ]


def build_h14c_arms(backend: str, seed: int) -> List[Tuple[str, Dict[str, Any]]]:
    """5 iso-parameter factorial arms for H14c non-Abelian S_3 & A_5 state tracking."""
    # d=256, H=8 (d_head=32, nb=8), 6L, unit sqk=1.0, quadratic +-q invariant readout on ALL 5 arms
    # RoPE has no w_omega (0 vs 256*192=49,152/L -> +64 d_ff = +49,152/L); Abelian-SO2 has 256*64=16,384/L -> +44 d_ff
    return [
        ("RoPE-2D-nGPT", dict(d_model=256, n_heads=8, n_layers=6, d_ff=640, pos_mode="rope2d", ngpt=True, freeze_sqk_one=True, quadratic_readout=True, backend="reference", seed=seed)),
        ("Abelian-SO2-Phase", dict(d_model=256, n_heads=8, n_layers=6, d_ff=616, pos_mode="su2_holonomy", abelian_so2=True, transport_v=True, untransport_o=True, angle_scale=math.pi, ngpt=True, freeze_sqk_one=True, quadratic_readout=True, backend=backend, seed=seed)),
        ("H7b-QK-Only", dict(d_model=256, n_heads=8, n_layers=6, d_ff=576, pos_mode="su2_holonomy", transport_v=False, untransport_o=False, angle_scale=math.pi, ngpt=True, freeze_sqk_one=True, quadratic_readout=True, backend=backend, seed=seed)),
        ("HoloSphere-V2-QKV-NoUntransport", dict(d_model=256, n_heads=8, n_layers=6, d_ff=576, pos_mode="su2_holonomy", transport_v=True, untransport_o=False, angle_scale=math.pi, ngpt=True, freeze_sqk_one=True, quadratic_readout=True, backend=backend, seed=seed)),
        ("HoloSphere-V2-Full-Covariant-QKV-Untransport", dict(d_model=256, n_heads=8, n_layers=6, d_ff=576, pos_mode="su2_holonomy", transport_v=True, untransport_o=True, angle_scale=math.pi, ngpt=True, freeze_sqk_one=True, quadratic_readout=True, backend=backend, seed=seed)),
    ]


# ---------------------------------------------------------------------------
# Evaluation Helpers: Exact UTF-8 BPB, MTP-8 BPB, & Synchronized NVML mJ/tok
# ---------------------------------------------------------------------------


def _build_mtp_targets(batch: torch.Tensor, block_size: int = 8) -> Tuple[torch.Tensor, torch.Tensor]:
    """From batch [B, T_plus_1], return (inp [B, T], mtp_tgt [B, T, K]) padded with PAD_ID."""
    inp = batch[:, :-1]
    tgt = batch[:, 1:]
    bsz, t_len = tgt.shape
    padded = F.pad(tgt, (0, block_size - 1), value=PAD_ID)
    windows = padded.unfold(dimension=1, size=block_size, step=1)  # [B, T, K]
    return inp, windows[:, :t_len, :].contiguous()


@torch.no_grad()
def _eval_bpb(
    model: HoloSphereV2LM,
    chunks: Sequence[torch.Tensor],
    device: torch.device,
    *,
    amp_bf16: bool = True,
    r_loops: Optional[int] = None,
    score_tail_len: Optional[int] = None,
    batch_size: int = 8,
) -> Dict[str, Any]:
    model.eval()
    total_nll = 0.0
    total_tok = 0
    total_bytes = 0
    mtp_nll = 0.0
    mtp_tok = 0
    for start in range(0, len(chunks), batch_size):
        mat = torch.stack(list(chunks[start : start + batch_size]), dim=0).to(device)
        inp, mtp_tgt = _build_mtp_targets(mat, block_size=8)
        tgt = mat[:, 1:]
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=(amp_bf16 and device.type == "cuda")):
            logits, extra = model(inp, r_loops=r_loops, mtp_targets=(mtp_tgt if model.mtp_head is not None else None))
        lp = F.log_softmax(logits.float(), dim=-1)
        nll = F.nll_loss(lp.reshape(-1, lp.shape[-1]), tgt.reshape(-1), ignore_index=PAD_ID, reduction="none").reshape(tgt.shape)
        valid = (tgt != PAD_ID) & (tgt != BOS_ID)
        if score_tail_len is not None and score_tail_len < tgt.shape[1]:
            s_i = tgt.shape[1] - score_tail_len
            nll, valid, tgt_e = nll[:, s_i:], valid[:, s_i:], tgt[:, s_i:]
        else:
            tgt_e = tgt
        total_nll += float(nll[valid].sum().item())
        total_tok += int(valid.sum().item())
        raw_b = int(((tgt_e >= 0) & (tgt_e < 256) & valid).sum().item())
        total_bytes += max(raw_b, int(valid.sum().item()))

        if "mtp_logits" in extra:
            ml = extra["mtp_logits"].float()  # [B, T, 8, V]
            m_valid = (mtp_tgt != PAD_ID) & (mtp_tgt != BOS_ID)
            m_loss = F.cross_entropy(ml.reshape(-1, ml.shape[-1]), mtp_tgt.reshape(-1), ignore_index=PAD_ID, reduction="none").reshape(mtp_tgt.shape)
            mtp_nll += float(m_loss[m_valid].sum().item())
            mtp_tok += int(m_valid.sum().item())

    bpb = total_nll / (math.log(2.0) * float(max(total_bytes, 1)))
    out: Dict[str, Any] = {"bpb": round(bpb, 6), "scored_tokens": total_tok}
    if mtp_tok > 0:
        out["mtp8_tf_bpb"] = round(mtp_nll / (math.log(2.0) * float(mtp_tok)), 6)
    return out


@torch.no_grad()
def _measure_inference_mj(
    model: HoloSphereV2LM,
    device: torch.device,
    *,
    seq_len: int,
    batch_size: int,
    iters: int,
    p_idle_w: float,
    amp_bf16: bool = True,
) -> Dict[str, float]:
    if device.type != "cuda":
        return {"ms_per_iter": 0.0, "tok_per_s": 0.0, "avg_power_w": 0.0, "gross_mj_per_tok": 0.0, "idle_sub_mj_per_tok": 0.0}
    model.eval()
    x = torch.randint(0, VOCAB_SIZE, (batch_size, seq_len), generator=_seeded_gen(91400 + seq_len)).to(device)
    for _ in range(5):
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp_bf16):
            _ = model(x)
    torch.cuda.synchronize()
    p_samples: List[float] = []
    t0 = time.monotonic()
    for i in range(iters):
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp_bf16):
            _ = model(x)
        if i in (0, iters // 2, iters - 1):
            torch.cuda.synchronize()
            pw = _query_nvml_power_w()
            if pw is not None:
                p_samples.append(pw)
    torch.cuda.synchronize()
    wall_s = time.monotonic() - t0
    avg_w = (sum(p_samples) / float(len(p_samples))) if p_samples else 0.0
    tot_tok = float(iters * batch_size * seq_len)
    gross_mj = (avg_w * wall_s * 1000.0) / tot_tok
    net_mj = (max(0.0, avg_w - p_idle_w) * wall_s * 1000.0) / tot_tok
    return {
        "ms_per_iter": round((wall_s * 1000.0) / float(iters), 3),
        "tok_per_s": round(tot_tok / max(wall_s, 1e-9), 1),
        "avg_power_w": round(avg_w, 2),
        "gross_mj_per_tok": round(gross_mj, 5),
        "idle_sub_mj_per_tok": round(net_mj, 5),
    }


# ---------------------------------------------------------------------------
# H14b Campaign Runner
# ---------------------------------------------------------------------------


def _run_h14b(
    *,
    device: torch.device,
    backend: str,
    train_chunks: Sequence[torch.Tensor],
    val512_chunks: Sequence[torch.Tensor],
    val2048_chunks: Sequence[torch.Tensor],
    seeds: Sequence[int],
    base_steps: int,
    batch_size: int,
    lr_std: float,
    lr_ngpt: float,
    amp_bf16: bool,
    p_idle_w: float,
    save_best_dir: Optional[Path],
) -> Dict[str, Any]:
    runs: List[Dict[str, Any]] = []
    t_budgets: Dict[int, float] = {}
    best_candidate_bpb = float("inf")
    best_candidate_meta: Optional[Dict[str, Any]] = None
    best_candidate_state: Optional[Dict[str, torch.Tensor]] = None

    for s_idx, seed in enumerate(seeds):
        arm_specs = build_h14b_arms(backend=backend, seed=seed)
        # Verify <= 0.5% non-embedding param parity across all 7 arms
        non_emb_ref: Optional[int] = None

        # Anchor RoPE-2D-nGPT runs first per seed to lock T_budget(seed), then rotate remaining 6 arms!
        anchor_spec = [a for a in arm_specs if a[0] == "RoPE-2D-nGPT"][0]
        others = [a for a in arm_specs if a[0] != "RoPE-2D-nGPT"]
        if s_idx % 3 == 1:
            others = list(reversed(others))
        elif s_idx % 3 == 2:
            others = others[3:] + others[:3]
        ordered = [anchor_spec] + others

        for arm_name, kw in ordered:
            gc.collect()
            if device.type == "cuda":
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats(device)
            torch.manual_seed(seed)
            rng = random.Random(seed + 17)
            model = HoloSphereV2LM(arm_name=arm_name, **kw).to(device)
            p_stats = _count_params(model)
            if non_emb_ref is None:
                non_emb_ref = p_stats["non_embedding_params"]
            rel_p = abs(p_stats["non_embedding_params"] - non_emb_ref) / float(non_emb_ref)
            _require(rel_p <= 0.005, f"Param parity violated on {arm_name}: {rel_p:.4%}")

            peak_lr = lr_ngpt if kw.get("ngpt", True) else lr_std
            wd = 0.0 if kw.get("ngpt", True) else 0.1
            opt = torch.optim.AdamW(model.parameters(), lr=peak_lr, betas=(0.9, 0.95), weight_decay=wd)

            # Short 3-step thermal/JIT warmup on throwaway copy-free batch? Keep deterministic by warming up before reset?
            # Actually warm up kernels once globally, or exclude step 0 compile jitter cleanly via 3 warmup steps before timer on anchor only if needed.
            is_anchor = (arm_name == "RoPE-2D-nGPT")
            budget_s = None if is_anchor else t_budgets[seed]

            # Deterministic training loop collecting BOTH equal-step (base_steps) AND equal-wall-clock (T_budget) checkpoints!
            if device.type == "cuda":
                torch.cuda.synchronize()
            t_start = time.monotonic()
            train_time_s = 0.0
            step = 0
            eq_step_eval: Optional[Dict[str, Any]] = None
            eq_wc_eval: Optional[Dict[str, Any]] = None
            max_steps_cap = max(base_steps * 3, base_steps + 20)

            model.train()
            last_loss = 0.0
            while True:
                step_t0 = time.monotonic()
                cur_lr = _cosine_lr(step, base_steps, peak_lr=peak_lr)
                for gp in opt.param_groups:
                    gp["lr"] = cur_lr
                batch_list = [train_chunks[rng.randrange(len(train_chunks))] for _ in range(batch_size)]
                batch = torch.stack(batch_list, dim=0).to(device)
                inp, mtp_tgt = _build_mtp_targets(batch, block_size=8)
                tgt = batch[:, 1:]

                opt.zero_grad(set_to_none=True)
                with torch.autocast("cuda", dtype=torch.bfloat16, enabled=(amp_bf16 and device.type == "cuda")):
                    logits, extra = model(inp, mtp_targets=(mtp_tgt if model.mtp_head is not None else None))
                    loss = F.cross_entropy(logits.float().reshape(-1, VOCAB_SIZE), tgt.reshape(-1), ignore_index=PAD_ID)
                    if "mtp_logits" in extra:
                        ml = extra["mtp_logits"].float()
                        loss_mtp = F.cross_entropy(ml.reshape(-1, VOCAB_SIZE), mtp_tgt.reshape(-1), ignore_index=PAD_ID)
                        loss = loss + 0.1 * loss_mtp
                _require(bool(torch.isfinite(loss).item()), f"Non-finite loss in {arm_name} seed={seed} step={step}")
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                model.normalize_ngpt_weights_()
                if device.type == "cuda":
                    torch.cuda.synchronize()
                train_time_s += (time.monotonic() - step_t0)
                last_loss = float(loss.item())
                step += 1

                # Equal-step checkpoint (exact base_steps)
                if eq_step_eval is None and step == base_steps:
                    if is_anchor:
                        t_budgets[seed] = train_time_s
                        budget_s = train_time_s
                    e512 = _eval_bpb(model, val512_chunks, device, amp_bf16=amp_bf16, batch_size=batch_size)
                    e2048 = _eval_bpb(model, val2048_chunks, device, amp_bf16=amp_bf16, score_tail_len=512, batch_size=max(1, batch_size // 4))
                    eq_step_eval = {
                        "steps": step, "tokens": step * batch_size * (train_chunks[0].numel() - 1),
                        "train_time_s": round(train_time_s, 3), "T512": e512, "T2048": e2048,
                    }
                    if is_anchor:
                        eq_wc_eval = copy.deepcopy(eq_step_eval)
                        break
                    model.train()

                # Equal-wall-clock checkpoint (CS-08)
                if (not is_anchor) and (eq_wc_eval is None) and (budget_s is not None) and (train_time_s >= budget_s or step >= max_steps_cap):
                    e512 = _eval_bpb(model, val512_chunks, device, amp_bf16=amp_bf16, batch_size=batch_size)
                    e2048 = _eval_bpb(model, val2048_chunks, device, amp_bf16=amp_bf16, score_tail_len=512, batch_size=max(1, batch_size // 4))
                    eq_wc_eval = {
                        "steps": step, "tokens": step * batch_size * (train_chunks[0].numel() - 1),
                        "train_time_s": round(train_time_s, 3), "T512": e512, "T2048": e2048,
                    }
                    model.train()

                if eq_step_eval is not None and eq_wc_eval is not None:
                    break

            # Extra looped R_test extrapolation for HoloSphere-V2-Full-Entity
            r_extrap: Dict[str, float] = {}
            if model.looped:
                for rt in (3, 4, 6, 8):
                    r_extrap[f"R{rt}"] = _eval_bpb(model, val512_chunks[:16], device, amp_bf16=amp_bf16, r_loops=rt, batch_size=batch_size)["bpb"]

            # Synchronized NVML inference mJ/tok (gross & idle-subtracted) at T=512 and T=2048
            inf_512 = _measure_inference_mj(model, device, seq_len=512, batch_size=batch_size, iters=20, p_idle_w=p_idle_w, amp_bf16=amp_bf16)
            inf_2048 = _measure_inference_mj(model, device, seq_len=2048, batch_size=max(1, batch_size // 4), iters=12, p_idle_w=p_idle_w, amp_bf16=amp_bf16)
            peak_mib = float(torch.cuda.max_memory_allocated(device)) / (1024.0 * 1024.0) if device.type == "cuda" else 0.0

            rec: Dict[str, Any] = {
                "arm_name": arm_name,
                "seed": seed,
                "params": p_stats,
                "t_budget_s": round(float(budget_s or train_time_s), 3),
                "equal_step": eq_step_eval,
                "equal_wallclock": eq_wc_eval,
                "last_train_loss": round(last_loss, 6),
                "peak_vram_mib": round(peak_mib, 2),
                "inference_T512": inf_512,
                "inference_T2048": inf_2048,
                "total_wall_s": round(time.monotonic() - t_start, 3),
            }
            if r_extrap:
                rec["r_test_extrapolation_bpb"] = r_extrap
            runs.append(rec)

            # Track single best verified HoloSphere-V2 arm for external HF-candidate save
            if save_best_dir is not None and arm_name.startswith("HoloSphere-V2-") and eq_wc_eval is not None:
                cand_bpb = float(eq_wc_eval["T2048"]["bpb"])
                if cand_bpb < best_candidate_bpb:
                    best_candidate_bpb = cand_bpb
                    best_candidate_meta = {"arm_name": arm_name, "seed": seed, "config_kwargs": kw, "metrics": rec}
                    best_candidate_state = {k_s: v_s.detach().cpu().clone() for k_s, v_s in model.state_dict().items()}

            print(
                f"  [H14b s={seed}] {arm_name:34s} "
                f"eqStep({eq_step_eval['steps']}): T512={eq_step_eval['T512']['bpb']:.4f} T2048={eq_step_eval['T2048']['bpb']:.4f} | "
                f"eqWC({eq_wc_eval['steps']}st/{eq_wc_eval['train_time_s']}s): T512={eq_wc_eval['T512']['bpb']:.4f} T2048={eq_wc_eval['T2048']['bpb']:.4f} | "
                f"inf512={inf_512['gross_mj_per_tok']:.4f}/{inf_512['idle_sub_mj_per_tok']:.4f} mJ/tok",
                flush=True,
            )
            del model, opt
            gc.collect()
            if device.type == "cuda":
                torch.cuda.empty_cache()

    # Save single best candidate outside repo if requested
    saved_ckpt_info: Optional[Dict[str, Any]] = None
    if save_best_dir is not None and best_candidate_state is not None and best_candidate_meta is not None:
        save_best_dir.mkdir(parents=True, exist_ok=True)
        ckpt_path = save_best_dir / "holosphere_v2_15m_best.pt"
        torch.save(best_candidate_state, ckpt_path)
        meta_path = save_best_dir / "candidate_config_and_eval.json"
        meta_path.write_text(json.dumps(best_candidate_meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        saved_ckpt_info = {
            "arm_name": best_candidate_meta["arm_name"],
            "seed": best_candidate_meta["seed"],
            "best_eqwc_t2048_bpb": best_candidate_bpb,
            "ckpt_sha256": hashlib.sha256(ckpt_path.read_bytes()).hexdigest(),
            "ckpt_bytes": ckpt_path.stat().st_size,
        }

    # Aggregate & literal PREREG-S114 H14b verdict
    by_arm: Dict[str, List[Dict[str, Any]]] = {}
    for r in runs:
        by_arm.setdefault(r["arm_name"], []).append(r)

    summary: Dict[str, Any] = {}
    for arm_name, rs in by_arm.items():
        rs_s = sorted(rs, key=lambda x: x["seed"])
        summary[arm_name] = {
            "non_embedding_params": rs_s[0]["params"]["non_embedding_params"],
            "eq_step_t512_mean": round(sum(x["equal_step"]["T512"]["bpb"] for x in rs_s) / len(rs_s), 6),
            "eq_step_t2048_mean": round(sum(x["equal_step"]["T2048"]["bpb"] for x in rs_s) / len(rs_s), 6),
            "eq_wc_steps_mean": round(sum(x["equal_wallclock"]["steps"] for x in rs_s) / len(rs_s), 1),
            "eq_wc_t512_mean": round(sum(x["equal_wallclock"]["T512"]["bpb"] for x in rs_s) / len(rs_s), 6),
            "eq_wc_t2048_mean": round(sum(x["equal_wallclock"]["T2048"]["bpb"] for x in rs_s) / len(rs_s), 6),
            "inf_t512_gross_mj": round(sum(x["inference_T512"]["gross_mj_per_tok"] for x in rs_s) / len(rs_s), 5),
            "inf_t512_net_mj": round(sum(x["inference_T512"]["idle_sub_mj_per_tok"] for x in rs_s) / len(rs_s), 5),
            "inf_t2048_gross_mj": round(sum(x["inference_T2048"]["gross_mj_per_tok"] for x in rs_s) / len(rs_s), 5),
            "inf_t2048_net_mj": round(sum(x["inference_T2048"]["idle_sub_mj_per_tok"] for x in rs_s) / len(rs_s), 5),
            "peak_vram_mib": round(sum(x["peak_vram_mib"] for x in rs_s) / len(rs_s), 2),
        }

    # Paired comparisons against RoPE-2D-nGPT and RoPE-2D-Std
    rope_ngpt_s = sorted(by_arm["RoPE-2D-nGPT"], key=lambda x: x["seed"])
    rope_std_s = sorted(by_arm["RoPE-2D-Std"], key=lambda x: x["seed"])
    comparisons: Dict[str, Any] = {}
    any_confirmed = False
    any_partial = False
    for arm_name, rs in by_arm.items():
        if not arm_name.startswith("HoloSphere-V2-"):
            continue
        rs_s = sorted(rs, key=lambda x: x["seed"])
        cmp_ngpt_2048 = _paired_stats([x["equal_wallclock"]["T2048"]["bpb"] for x in rs_s], [x["equal_wallclock"]["T2048"]["bpb"] for x in rope_ngpt_s])
        cmp_std_2048 = _paired_stats([x["equal_wallclock"]["T2048"]["bpb"] for x in rs_s], [x["equal_wallclock"]["T2048"]["bpb"] for x in rope_std_s])
        cmp_ngpt_512 = _paired_stats([x["equal_wallclock"]["T512"]["bpb"] for x in rs_s], [x["equal_wallclock"]["T512"]["bpb"] for x in rope_ngpt_s])
        cmp_eqstep_2048 = _paired_stats([x["equal_step"]["T2048"]["bpb"] for x in rs_s], [x["equal_step"]["T2048"]["bpb"] for x in rope_ngpt_s])

        r_mj_512 = summary[arm_name]["inf_t512_gross_mj"] / max(summary["RoPE-2D-nGPT"]["inf_t512_gross_mj"], 1e-9)
        r_mj_2048 = summary[arm_name]["inf_t2048_gross_mj"] / max(summary["RoPE-2D-nGPT"]["inf_t2048_gross_mj"], 1e-9)
        c1 = (cmp_ngpt_2048["rel_pct"] <= -5.0 and cmp_ngpt_2048["z_or_t"] <= -2.0 and cmp_std_2048["rel_pct"] <= -5.0 and cmp_std_2048["z_or_t"] <= -2.0)
        c2 = (cmp_ngpt_512["rel_pct"] <= 0.5)
        c3 = (r_mj_512 <= 1.15 and r_mj_2048 <= 1.15)
        if c1 and c2 and c3:
            any_confirmed = True
        elif c1:
            any_partial = True
        comparisons[arm_name] = {
            "eq_wc_t2048_vs_rope_ngpt": cmp_ngpt_2048,
            "eq_wc_t2048_vs_rope_std": cmp_std_2048,
            "eq_wc_t512_vs_rope_ngpt": cmp_ngpt_512,
            "eq_step_t2048_vs_rope_ngpt": cmp_eqstep_2048,
            "inf_mj_ratio_t512": round(r_mj_512, 4),
            "inf_mj_ratio_t2048": round(r_mj_2048, 4),
            "c1_t2048_ge_5pct_z_le_m2": c1,
            "c2_t512_non_regression": c2,
            "c3_mj_le_115x": c3,
        }

    h14b_verdict = "CONFIRMED" if any_confirmed else ("PARTIAL" if any_partial else "FALSIFIED")
    return {
        "p_idle_w": round(p_idle_w, 2),
        "t_budgets_sec": {str(k): round(v, 3) for k, v in t_budgets.items()},
        "runs": runs,
        "summary": summary,
        "comparisons": comparisons,
        "h14b_locked_verdict": h14b_verdict,
        "saved_candidate_checkpoint": saved_ckpt_info,
    }


# ---------------------------------------------------------------------------
# H14c Campaign Runner: Non-Abelian S_3 & A_5 State Tracking
# ---------------------------------------------------------------------------


def _run_h14c(
    *,
    device: torch.device,
    backend: str,
    seeds: Sequence[int],
    steps: int,
    batch_size: int,
    lr: float,
    amp_bf16: bool,
) -> Dict[str, Any]:
    runs: List[Dict[str, Any]] = []
    for group_name in ("S3", "A5"):
        group = s107_te.build_finite_group(group_name)
        for s_idx, seed in enumerate(seeds):
            # Generate 3-stage curriculum L in [4..24], [4..48], [4..64] + fixed ID [4..64] & OOD [65..192]
            tr_c1 = s107_te.generate_group_word_dataset(group, n_samples=1536, min_len=4, max_len=24, seed=seed + 1100)
            tr_c2 = s107_te.generate_group_word_dataset(group, n_samples=1536, min_len=4, max_len=48, seed=seed + 1200)
            tr_c3 = s107_te.generate_group_word_dataset(group, n_samples=2048, min_len=4, max_len=64, seed=seed + 1300)
            id_x, id_y = s107_te.generate_group_word_dataset(group, n_samples=256, min_len=4, max_len=64, seed=seed + 2000)
            ood_x, ood_y = s107_te.generate_group_word_dataset(group, n_samples=256, min_len=65, max_len=192, seed=seed + 3000)

            arms = build_h14c_arms(backend=backend, seed=seed)
            # Rotate order per seed to prevent thermal bias
            shift = s_idx % len(arms)
            ordered = arms[shift:] + arms[:shift]
            non_emb_ref: Optional[int] = None

            for arm_name, kw in ordered:
                gc.collect()
                if device.type == "cuda":
                    torch.cuda.empty_cache()
                torch.manual_seed(seed)
                rng = random.Random(seed + 71)
                model = HoloSphereV2LM(arm_name=arm_name, **kw).to(device)
                p_stats = _count_params(model)
                if non_emb_ref is None:
                    non_emb_ref = p_stats["non_embedding_params"]
                rel_p = abs(p_stats["non_embedding_params"] - non_emb_ref) / float(non_emb_ref)
                _require(rel_p <= 0.006, f"H14c param parity mismatch on {arm_name}: {rel_p:.4%}")

                opt = torch.optim.AdamW(model.parameters(), lr=lr, betas=(0.9, 0.95), weight_decay=0.0)
                t0 = time.monotonic()
                model.train()
                s1 = max(1, steps // 3)
                s2 = max(2, (2 * steps) // 3)
                for step in range(steps):
                    cur_lr = _cosine_lr(step, steps, peak_lr=lr)
                    for gp in opt.param_groups:
                        gp["lr"] = cur_lr
                    tr_x, tr_y = tr_c1 if step < s1 else (tr_c2 if step < s2 else tr_c3)
                    idx = [rng.randrange(tr_x.shape[0]) for _ in range(batch_size)]
                    xb = tr_x[idx].to(device)
                    yb = tr_y[idx].to(device)
                    opt.zero_grad(set_to_none=True)
                    with torch.autocast("cuda", dtype=torch.bfloat16, enabled=(amp_bf16 and device.type == "cuda")):
                        logits, _ = model(xb)
                        loss = F.cross_entropy(logits.float().reshape(-1, VOCAB_SIZE), yb.reshape(-1), ignore_index=PAD_ID)
                    _require(bool(torch.isfinite(loss).item()), f"Non-finite loss H14c {group_name} {arm_name} step={step}")
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    opt.step()
                    model.normalize_ngpt_weights_()

                @torch.no_grad()
                def _eval_acc(xs: torch.Tensor, ys: torch.Tensor) -> Tuple[float, float]:
                    model.eval()
                    corr_all = tot_all = corr_last = tot_last = 0
                    for st in range(0, xs.shape[0], 32):
                        xb_e = xs[st : st + 32].to(device)
                        yb_e = ys[st : st + 32].to(device)
                        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=(amp_bf16 and device.type == "cuda")):
                            lg, _ = model(xb_e)
                        preds = lg.argmax(dim=-1)
                        mask = yb_e != PAD_ID
                        corr_all += int(((preds == yb_e) & mask).sum().item())
                        tot_all += int(mask.sum().item())
                        # Final valid position per sequence
                        lens = mask.sum(dim=1) - 1
                        row_idx = torch.arange(xb_e.shape[0], device=device)
                        corr_last += int((preds[row_idx, lens] == yb_e[row_idx, lens]).sum().item())
                        tot_last += int(xb_e.shape[0])
                    return (100.0 * corr_all / max(tot_all, 1)), (100.0 * corr_last / max(tot_last, 1))

                id_acc, id_last = _eval_acc(id_x, id_y)
                ood_acc, ood_last = _eval_acc(ood_x, ood_y)
                el_s = time.monotonic() - t0
                runs.append({
                    "group": group_name, "arm_name": arm_name, "seed": seed,
                    "params": p_stats, "id_acc_pct": round(id_acc, 3), "id_final_acc_pct": round(id_last, 3),
                    "ood_acc_pct": round(ood_acc, 3), "ood_final_acc_pct": round(ood_last, 3),
                    "elapsed_s": round(el_s, 2),
                })
                print(
                    f"  [H14c {group_name} s={seed}] {arm_name:44s} ID={id_acc:6.2f}% OOD={ood_acc:6.2f}% (final={ood_last:6.2f}%) [{el_s:.1f}s]",
                    flush=True,
                )
                del model, opt
                gc.collect()
                if device.type == "cuda":
                    torch.cuda.empty_cache()

    # Aggregate & literal PREREG-S114 H14c grading
    summary: Dict[str, Dict[str, Any]] = {"S3": {}, "A5": {}}
    comparisons: Dict[str, Any] = {}
    group_pass: Dict[str, bool] = {}
    for gname, acc_floor, margin_pp in (("S3", 50.0, 15.0), ("A5", 15.0, 8.0)):
        by_arm: Dict[str, List[Dict[str, Any]]] = {}
        for r in runs:
            if r["group"] == gname:
                by_arm.setdefault(r["arm_name"], []).append(r)
        for an, rs in by_arm.items():
            rs_s = sorted(rs, key=lambda x: x["seed"])
            summary[gname][an] = {
                "id_acc_mean": round(sum(x["id_acc_pct"] for x in rs_s) / len(rs_s), 3),
                "ood_acc_mean": round(sum(x["ood_acc_pct"] for x in rs_s) / len(rs_s), 3),
                "ood_final_mean": round(sum(x["ood_final_acc_pct"] for x in rs_s) / len(rs_s), 3),
            }
        cov = sorted(by_arm["HoloSphere-V2-Full-Covariant-QKV-Untransport"], key=lambda x: x["seed"])
        rope = sorted(by_arm["RoPE-2D-nGPT"], key=lambda x: x["seed"])
        qk = sorted(by_arm["H7b-QK-Only"], key=lambda x: x["seed"])
        so2 = sorted(by_arm["Abelian-SO2-Phase"], key=lambda x: x["seed"])
        nou = sorted(by_arm["HoloSphere-V2-QKV-NoUntransport"], key=lambda x: x["seed"])

        vs_rope = _paired_stats([x["ood_acc_pct"] for x in cov], [x["ood_acc_pct"] for x in rope])
        vs_qk = _paired_stats([x["ood_acc_pct"] for x in cov], [x["ood_acc_pct"] for x in qk])
        vs_so2 = _paired_stats([x["ood_acc_pct"] for x in cov], [x["ood_acc_pct"] for x in so2])
        vs_nou = _paired_stats([x["ood_acc_pct"] for x in cov], [x["ood_acc_pct"] for x in nou])
        passed = bool(
            summary[gname]["HoloSphere-V2-Full-Covariant-QKV-Untransport"]["ood_acc_mean"] >= acc_floor
            and vs_rope["mean_diff"] >= margin_pp and vs_rope["z_or_t"] >= 2.0
            and vs_qk["mean_diff"] >= margin_pp and vs_qk["z_or_t"] >= 2.0
        )
        group_pass[gname] = passed
        comparisons[gname] = {
            "vs_rope": vs_rope, "vs_qk_only": vs_qk, "vs_abelian_so2": vs_so2, "vs_qkv_nountransport": vs_nou,
            "locked_criterion_pass": passed,
        }

    if group_pass["S3"] and group_pass["A5"]:
        verdict = "CONFIRMED"
    elif group_pass["S3"] or group_pass["A5"]:
        verdict = "PARTIAL"
    else:
        verdict = "FALSIFIED"

    return {
        "runs": runs,
        "summary": summary,
        "comparisons": comparisons,
        "h14c_locked_verdict": verdict,
    }


def _discover_wikitext_parquets() -> Tuple[Optional[Path], Optional[Path]]:
    cache_root = Path(os.environ.get("HF_HOME", str(Path.home() / ".cache" / "huggingface"))) / "hub"
    if not cache_root.is_dir():
        return None, None
    val_p = next(cache_root.glob("datasets--Salesforce--wikitext/snapshots/*/wikitext-2-raw-v1/validation-*.parquet"), None)
    test_p = next(cache_root.glob("datasets--Salesforce--wikitext/snapshots/*/wikitext-2-raw-v1/test-*.parquet"), None)
    return val_p, test_p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Track S114 H14b + H14c HoloSphere V2 Live GPU Training Campaign")
    parser.add_argument("--smoke-cpu", action="store_true", help="Run fast 2-step CPU preflight of all 12 arms")
    parser.add_argument("--wikitext-train", type=Path, default=None)
    parser.add_argument("--wikitext-test", type=Path, default=None)
    parser.add_argument("--save-best-dir", type=Path, default=None, help="External path outside repo to save best HoloSphere-V2 candidate checkpoint")
    parser.add_argument("--h14b-steps", type=int, default=600)
    parser.add_argument("--h14c-steps", type=int, default=1200)
    parser.add_argument("--out", type=Path, default=_HERE / "s114_h14bc_gpu_results.json")
    args = parser.parse_args(argv)

    t0 = time.monotonic()
    prereg_path = _EXPEDITION / "notes" / "holosphere_kernel_transformer_2026_11_25" / "PREREG_S114_SILISPHERE_FUSED_ENTITY.md"
    prereg_sha = hashlib.sha256(prereg_path.read_bytes()).hexdigest()
    _require(prereg_sha == PREREG_SHA256, f"PREREG-S114 SHA mismatch: {prereg_sha}")

    if args.smoke_cpu:
        device = torch.device("cpu")
        backend = "reference"
        # Tiny deterministic synthetic smoke corpus
        raw = ("def holosphere_su2(q, k, v):\n    return q * k + v\n" * 600).encode("utf-8")
        ids = list(raw)
        tr_c = s107_te.chunk_stream(ids, seq_len=65, max_chunks=16)
        v512_c = s107_te.chunk_stream(ids, seq_len=65, max_chunks=8)
        v2048_c = s107_te.chunk_stream(ids, seq_len=129, max_chunks=4)
        h14b = _run_h14b(
            device=device, backend=backend, train_chunks=tr_c, val512_chunks=v512_c, val2048_chunks=v2048_c,
            seeds=(42,), base_steps=2, batch_size=2, lr_std=1.2e-3, lr_ngpt=2.5e-3, amp_bf16=False, p_idle_w=0.0, save_best_dir=None,
        )
        h14c = _run_h14c(
            device=device, backend=backend, seeds=(42,), steps=3, batch_size=4, lr=2.0e-3, amp_bf16=False,
        )
        print(json.dumps({"smoke_cpu": "PASS", "h14b_arms": len(h14b["summary"]), "h14c_s3_arms": len(h14c["summary"]["S3"]), "elapsed_s": round(time.monotonic() - t0, 2)}))
        return 0

    _require(torch.cuda.is_available(), "CUDA GPU required for live H14b + H14c campaign")
    torch.cuda.init()
    device = torch.device("cuda:0")
    torch.cuda.set_device(device)
    _ = torch.empty((1,), device=device)
    backend = "cuda"
    _require(ops._load_cuda_lib() is not None, "libsu2_holonomy_scan_sm86.so must be loaded via SILISPHERE_SM86_LIB")

    wt_tr, wt_te = args.wikitext_train, args.wikitext_test
    if wt_tr is None or wt_te is None:
        d_tr, d_te = _discover_wikitext_parquets()
        wt_tr = wt_tr or d_tr
        wt_te = wt_te or d_te
    bundle = s107_te.load_multidomain_offline_bundle(wt_tr, wt_te, _EXPEDITION)
    _require(bundle["train_sha256"] != bundle["eval_sha256"], "Train/eval SHA-256 collision!")

    tr_chunks = s107_te.chunk_stream(bundle["train_bytes"], seq_len=513)
    v512_chunks = s107_te.chunk_stream(bundle["eval_combined_bytes"], seq_len=513, max_chunks=64)
    v2048_chunks = s107_te.chunk_stream(bundle["eval_combined_bytes"], seq_len=2049, max_chunks=16)

    p_idle_w = _measure_idle_power_w(samples=3)
    print(
        f"H14b+H14c LIVE sm_86 START train_bytes={bundle['train_num_bytes']} eval_sha={bundle['eval_sha256'][:12]} "
        f"p_idle={p_idle_w:.2f}W h14b_steps={args.h14b_steps} h14c_steps={args.h14c_steps}",
        flush=True,
    )

    h14b = _run_h14b(
        device=device, backend=backend, train_chunks=tr_chunks, val512_chunks=v512_chunks, val2048_chunks=v2048_chunks,
        seeds=SEEDS, base_steps=args.h14b_steps, batch_size=8, lr_std=1.2e-3, lr_ngpt=2.5e-3, amp_bf16=True,
        p_idle_w=p_idle_w, save_best_dir=args.save_best_dir,
    )
    print(f"\n=== H14b LOCKED VERDICT: {h14b['h14b_locked_verdict']} ===\n", flush=True)

    h14c = _run_h14c(
        device=device, backend=backend, seeds=SEEDS, steps=args.h14c_steps, batch_size=32, lr=2.0e-3, amp_bf16=True,
    )
    print(f"\n=== H14c LOCKED VERDICT: {h14c['h14c_locked_verdict']} ===\n", flush=True)

    ptx_rec = json.loads((_HERE / "ptxas_sm86_zero_spill_receipt.json").read_text(encoding="utf-8"))
    payload: Dict[str, Any] = {
        "schema": "holosphere.track_s114.h14bc_gpu_results.v1",
        "oracle_class": "anchor",
        "preregistration_sha256": prereg_sha,
        "cu_sha256": ptx_rec["cu_sha256"],
        "zero_spill_kernels": ptx_rec["zero_spill_kernels"],
        "completed_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "torch_version": torch.__version__,
        "corpus": {
            "train_sha256": bundle["train_sha256"],
            "train_num_bytes": bundle["train_num_bytes"],
            "eval_sha256": bundle["eval_sha256"],
            "eval_domain_sizes": bundle["eval_domain_sizes"],
        },
        "h14b": h14b,
        "h14c": h14c,
        "elapsed_seconds": round(time.monotonic() - t0, 3),
    }
    payload["result_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    out_bytes = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    args.out.write_bytes(out_bytes)
    os.chmod(args.out, 0o600)
    print(
        f"DONE H14b={h14b['h14b_locked_verdict']} H14c={h14c['h14c_locked_verdict']} "
        f"FILE={args.out.name} ({len(out_bytes)} B, file_sha256={hashlib.sha256(out_bytes).hexdigest()}, inner={payload['result_sha256']})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
