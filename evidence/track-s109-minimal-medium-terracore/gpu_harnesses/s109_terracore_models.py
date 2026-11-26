#!/usr/bin/env python3
"""Exact-operator modules for Track S109 (PREREG-S109 + Amendments 1, 2, & 3 TerraCore).

Implements:
  - Minimal zero-language computational medium M (canonical symbolic IR, zero English inside Core)
    plus strictly tuple-disjoint Regime I (structured formal reasoning with CB-6 purely syntactic
    outer transducer) and Regime II (multi-surface ambiguous word problems with implicit pragmatic
    modifier stressing Track S92 Translator-DPI without leaking the target answer into residual r).
  - Raw-deflate lossless compression stream + decompressor-emulation & probe-LM helpers (H9a).
  - Shell 1: RigidInnerCore (zero-language M -> M antipodal-safe Clifford-Torus Hopf-looped Core
    with W10-OBS-31 non-antipodal clock phi_r = pi*(r+1)/(2R+1), scaled per-loop embedding,
    causal <EOS> non-pad pooling, h^(mid) latent-CoT supervision, SHA-256 weight pinning, strict
    Stage-2 freeze, core-only discrete M scoring, and exact counterfactual h^(r) state patching).
  - Shell 2: ViscoplasticAsthenosphere (<= 96-bit capped S^{k-1} residual with k <= 32 at 3 bpw,
    Track S43 Bingham two-sided ReLU soft-thresholding across Y in {0, 1/4, 1/2, 3/4, 1}, Track S50
    orthogonal Poloidal/Toroidal Hodge split <u_pol, u_tor> = 0, non-strawman matched-rank
    unstructured NoHodge ablation, and Channel-2B airlock telemetry).
  - Shell 3: Swappable Lithospheric Plates (MHPlate ExternalSurfacePlate with multi-head cross-
    attention IR+residual extraction, AuditTraceDecoder, PlateSeamRouter with exact cocycle
    conservation sum(alpha_i) = 1 for zero-retrain §SWAP & §PLATE-SWAP).
  - Fair Steelman MonolithicByteReasoner (2-step explicit CoT conditioning for Arm A, direct floor
    for Arm A', raw-deflate for Arm B) with exact 15M triple CS-08 parity.
  - Mandatory CS-21 anti-smuggling guards: zero-skip-path graph check, <= 50k MLP CS21_RESIDUAL_LEAK
    kill probe, CB-1..CB-6 helpers, Portal-5 Darboux dark-mode kernel-loss diagnostic.

Zero bare assert statements; strictly CPU-safe and RTX-3080 ready.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Any, Sequence
import zlib

import torch
import torch.nn as nn
import torch.nn.functional as F

PREREG_S109_SHA256 = "1ca8a38fa3c7fd8dda5823741c867b93be09c2342eb35bafde18e9e7e510b1c9"
AMENDMENT1_SHA256 = "6f3d1e0b28d16e4290486e9adeb76c49bd8ebbf0954efb19d88621dc354bdcfd"
AMENDMENT2_SHA256 = "faf225067917b464ac25b2ae68ae1fa7bdf3179a2c461ec883490ea24ff9d7e3"
AMENDMENT3_SHA256 = "e441b07a97205f857a65f1b232b373cdcdc60fa6526d044d5c6fef856761e70e"

MAX_RESIDUAL_DIM = 32
MAX_RESIDUAL_BPW = 3
MAX_RESIDUAL_BITS = 96
YIELD_SWEEP_VALUES = (0.0, 0.25, 0.5, 0.75, 1.0)


def safe_clamped_unit(x: torch.Tensor, dim: int = -1, floor: float = 1e-4) -> torch.Tensor:
    """Unit projection with hard norm floor preventing Norm(0) -> NaN."""
    norm = torch.linalg.vector_norm(x, dim=dim, keepdim=True).clamp_min(floor)
    return x / norm


def _last_nonpad_indices(token_ids: torch.Tensor, pad_id: int = 0) -> torch.Tensor:
    """Return index of final non-pad token per row (clamped to >= 0), preserving strict causality."""
    lengths = (token_ids != pad_id).sum(dim=1)
    return (lengths - 1).clamp(min=0, max=int(token_ids.shape[1]) - 1)


# ---------------------------------------------------------------------------
# Zero-Language Minimal Medium M & Strictly Tuple-Disjoint Dual-Regime Dataset
# ---------------------------------------------------------------------------


class MinimalMediumVocab:
    """Strict zero-language symbolic IR vocabulary (M): opcodes, small ints, registers, punctuation."""

    TOKENS: tuple[str, ...] = (
        "<PAD>",
        "<BOS>",
        "<EOS>",
        "<SEP>",
        "OP_ADD",
        "OP_SUB",
        "OP_MUL",
        "OP_XOR",
        "MOD16",
        "STEP",
        "ANS",
        "(",
        ")",
        *[f"N{i}" for i in range(16)],
        *[f"R{i}" for i in range(4)],
    )

    def __init__(self) -> None:
        self.tok_to_id = {tok: idx for idx, tok in enumerate(self.TOKENS)}
        self.id_to_tok = list(self.TOKENS)
        self.vocab_size = len(self.TOKENS)
        self.pad_id = self.tok_to_id["<PAD>"]

    def encode(self, toks: Sequence[str], max_len: int) -> list[int]:
        ids = [self.tok_to_id[t] for t in toks[:max_len]]
        if len(ids) < max_len:
            ids.extend([self.pad_id] * (max_len - len(ids)))
        return ids

    def decode(self, ids: Sequence[int]) -> list[str]:
        return [self.id_to_tok[int(i)] for i in ids if int(i) != self.pad_id]


def regime1_syntactic_transducer(surface_expr: str, m_vocab: MinimalMediumVocab, max_len: int = 12) -> list[int]:
    """CB-6 purely syntactic transducer: maps surface tokens 1-to-1 into M without ANY evaluation!"""
    token_map = {
        "+": "OP_ADD",
        "-": "OP_SUB",
        "*": "OP_MUL",
        "^": "OP_XOR",
        "%16": "MOD16",
        "(": "(",
        ")": ")",
    }
    out = ["<BOS>"]
    for part in surface_expr.strip().split():
        if part in token_map:
            out.append(token_map[part])
        elif part.isdigit() and 0 <= int(part) < 16:
            out.append(f"N{int(part)}")
    out.append("<EOS>")
    return m_vocab.encode(out, max_len=max_len)


@dataclass(frozen=True)
class S109Example:
    regime: str
    a: int
    b: int
    c: int
    op_id: int  # 0=ADD, 1=SUB, 2=MUL, 3=XOR
    modifier: int  # 0 or 1 (Regime I always 0; Regime II implicit surface nuance)
    intermediate: int  # (a op b) mod 16
    answer: int  # (intermediate + c + modifier) mod 16
    surface_en: str
    surface_alt: str  # Paraphrase / Arabic-script surface for §SWAP
    surface_mixed: str  # Mixed English + symbolic surface for §PLATE-SWAP
    canonical_ir_ids: tuple[int, ...]
    english_cot: str
    deflate_bytes: bytes


def _eval_mod16_op(a: int, b: int, op_id: int) -> int:
    if op_id == 0:
        return (a + b) % 16
    if op_id == 1:
        return (a - b) % 16
    if op_id == 2:
        return (a * b) % 16
    return (a ^ b) % 16


def generate_s109_dataset(
    n_regime1: int,
    n_regime2: int,
    seed: int = 42,
    ir_len: int = 12,
) -> tuple[list[S109Example], list[S109Example], str]:
    """Deterministic paired Regime-I & Regime-II datasets with STRICT 0% train/eval tuple overlap."""
    m_vocab = MinimalMediumVocab()
    op_syms = ("+", "-", "*", "^")
    op_en = ("plus", "minus", "times", "xor")
    op_ar = ("جمع", "طرح", "ضرب", "مغاير")

    train_tuples: list[tuple[int, int, int, int]] = []
    eval_tuples: list[tuple[int, int, int, int]] = []
    for op_id in range(4):
        for a in range(16):
            for b in range(16):
                for c in range(16):
                    digest = hashlib.sha256(f"s109:part:{a}:{b}:{c}:{op_id}".encode("ascii")).digest()
                    if (digest[0] & 3) == 3:
                        eval_tuples.append((a, b, c, op_id))
                    else:
                        train_tuples.append((a, b, c, op_id))

    def _shuffle_with_seed(items: list[tuple[int, int, int, int]], tag: str) -> list[tuple[int, int, int, int]]:
        keyed = [
            (hashlib.sha256(f"s109:order:{seed}:{tag}:{t[0]}:{t[1]}:{t[2]}:{t[3]}".encode("ascii")).digest(), t)
            for t in items
        ]
        keyed.sort(key=lambda x: x[0])
        return [t for _, t in keyed]

    def _make_example(regime: str, idx: int, tup: tuple[int, int, int, int]) -> S109Example:
        a, b, c, op_id = tup
        h = hashlib.sha256(f"s109:ex:{seed}:{regime}:{idx}:{a}:{b}:{c}:{op_id}".encode("ascii")).digest()
        modifier = 0 if regime == "regime1" else (h[0] & 1)
        inter = _eval_mod16_op(a, b, op_id)
        ans = (inter + c + modifier) % 16
        sym_expr = f"( {a} {op_syms[op_id]} {b} ) + {c} %16"
        ir_ids = tuple(regime1_syntactic_transducer(sym_expr, m_vocab, max_len=ir_len))

        if regime == "regime1":
            surf_en = sym_expr
            surf_alt = f"CALC {sym_expr}"
            surf_mix = f"@ir {sym_expr}"
            cot = f"step1: {a} {op_syms[op_id]} {b} mod 16 = {inter}; step2: ({inter} + {c}) mod 16 = {ans}"
        else:
            mod_en = "including the reserve unit" if modifier == 1 else "excluding any reserve unit"
            mod_alt = "مع وحدة الاحتياط الإضافية" if modifier == 1 else "دون أي وحدة احتياط"
            mod_mix = f"[plate:en] {mod_en} | [plate:sym] {sym_expr}"
            distractor = h[1] % 16
            surf_en = (
                f"Start with {a} {op_en[op_id]} {b} (ignore note {distractor}), "
                f"add {c} modulo 16, {mod_en}."
            )
            surf_alt = (
                f"احسب {a} {op_ar[op_id]} {b} ثم أضف {c} باقي 16 {mod_alt} (تجاهل {distractor})."
            )
            surf_mix = mod_mix
            cot = (
                f"step1: {a} {op_en[op_id]} {b} mod 16 = {inter}; "
                f"mod={modifier}; step2: ({inter}+{c}+{modifier}) mod 16 = {ans}"
            )

        deflated = zlib.compress(surf_en.encode("utf-8"), level=9, wbits=-15)
        return S109Example(
            regime=regime,
            a=a,
            b=b,
            c=c,
            op_id=op_id,
            modifier=modifier,
            intermediate=inter,
            answer=ans,
            surface_en=surf_en,
            surface_alt=surf_alt,
            surface_mixed=surf_mix,
            canonical_ir_ids=ir_ids,
            english_cot=cot,
            deflate_bytes=deflated,
        )

    def _build_split(regime: str, n_total: int) -> list[S109Example]:
        n_tr = (n_total * 3) // 4
        n_ev = n_total - n_tr
        tr_ord = _shuffle_with_seed(train_tuples, f"{regime}:tr")
        ev_ord = _shuffle_with_seed(eval_tuples, f"{regime}:ev")
        out_tr = [_make_example(regime, i, tr_ord[i % len(tr_ord)]) for i in range(n_tr)]
        out_ev = [_make_example(regime, n_tr + i, ev_ord[i % len(ev_ord)]) for i in range(n_ev)]
        return out_tr + out_ev

    r1 = _build_split("regime1", n_regime1)
    r2 = _build_split("regime2", n_regime2)
    hasher = hashlib.sha256()
    for ex in r1 + r2:
        hasher.update(f"{ex.regime}|{ex.surface_en}|{ex.intermediate}|{ex.answer}\n".encode("utf-8"))
    return r1, r2, hasher.hexdigest()


def encode_utf8_bytes_fixed(text: str, seq_len: int) -> list[int]:
    raw = list(text.encode("utf-8")[:seq_len])
    if len(raw) < seq_len:
        raw.extend([0] * (seq_len - len(raw)))
    return raw


def encode_raw_bytes_fixed(raw_bytes: bytes, seq_len: int) -> list[int]:
    raw = list(raw_bytes[:seq_len])
    if len(raw) < seq_len:
        raw.extend([0] * (seq_len - len(raw)))
    return raw


def empirical_binary_entropy_and_redundancy(raw_streams: Sequence[bytes]) -> dict[str, float]:
    """Compute empirical Shannon entropy H2 (bits/byte) and residual redundancy Delta(B) = 8 - H2."""
    counts = [0] * 256
    total = 0
    for s in raw_streams:
        for b in s:
            counts[b] += 1
            total += 1
    if total == 0:
        return {"entropy_bits_per_byte": 0.0, "redundancy_bits_per_byte": 8.0, "mean_len_bytes": 0.0}
    h2 = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            h2 -= p * math.log2(p)
    return {
        "entropy_bits_per_byte": round(h2, 6),
        "redundancy_bits_per_byte": round(8.0 - h2, 6),
        "mean_len_bytes": round(total / max(len(raw_streams), 1), 3),
    }


# ---------------------------------------------------------------------------
# Shell 2: Viscoplastic Asthenosphere (<= 96-bit cap, S43 Bingham, S50 Hodge)
# ---------------------------------------------------------------------------


def _build_hodge_bases(k: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Deterministic orthogonal Poloidal/Toroidal split AND matched-rank non-orthogonal NoHodge pair."""
    gen = torch.Generator(device="cpu")
    gen.manual_seed(109050)
    a = torch.randn((k, k), generator=gen, dtype=torch.float64)
    q, _ = torch.linalg.qr(a)
    half = k // 2
    q_pol = q[:, :half]
    q_tor = q[:, half:]
    p_pol = q_pol @ q_pol.T
    p_tor = q_tor @ q_tor.T

    # Non-strawman matched-rank unstructured coupling (NoHodge): same rank k//2, 75% shared span
    overlap = max(1, (3 * half) // 4)
    q_lat_unstruct = torch.cat([q_pol[:, :overlap], q_tor[:, : half - overlap]], dim=1)
    p_unstruct_rad = p_pol
    p_unstruct_lat = q_lat_unstruct @ q_lat_unstruct.T
    return (
        q_pol.to(torch.float32),
        q_tor.to(torch.float32),
        p_pol.to(torch.float32),
        p_tor.to(torch.float32),
        p_unstruct_rad.to(torch.float32),
        p_unstruct_lat.to(torch.float32),
    )


def canonical_poloidal_axis(k: int = 32, device: torch.device | None = None) -> torch.Tensor:
    """Return unit vector q_0 = Q_pol[:, 0] defining canonical chart Q_0 inside Poloidal subspace."""
    q_pol, *_ = _build_hodge_bases(k)
    axis = q_pol[:, 0].clone()
    if device is not None:
        axis = axis.to(device)
    return axis


def ste_uniform_quantize_3bpw(x: torch.Tensor, bits: int = 3) -> torch.Tensor:
    """Deterministic STE uniform scalar quantizer on [-1, 1] using exact `bits` per coordinate."""
    if bits < 1 or bits > MAX_RESIDUAL_BPW:
        raise ValueError(f"bits must be in 1..{MAX_RESIDUAL_BPW}, got {bits}")
    levels = (1 << bits) - 1
    clamped = x.clamp(-1.0, 1.0)
    scaled = (clamped + 1.0) * 0.5 * levels
    q = torch.round(scaled) / levels * 2.0 - 1.0
    return q - clamped.detach() + clamped


class ViscoplasticAsthenosphere(nn.Module):
    """Shell 2 coupling layer obeying §H9c-CONTRACT, Track S43 Bingham yield, and Track S50 Hodge split."""

    def __init__(
        self,
        k: int = 32,
        bits_per_dim: int = 3,
        yield_number: float = 0.5,
        use_hodge: bool = True,
    ) -> None:
        super().__init__()
        if k <= 0 or k > MAX_RESIDUAL_DIM:
            raise ValueError(f"residual dim k must be in 1..{MAX_RESIDUAL_DIM}, got {k}")
        if bits_per_dim <= 0 or bits_per_dim > MAX_RESIDUAL_BPW:
            raise ValueError(f"bits_per_dim must be in 1..{MAX_RESIDUAL_BPW}, got {bits_per_dim}")
        if k * bits_per_dim > MAX_RESIDUAL_BITS:
            raise ValueError(
                f"residual bit budget {k * bits_per_dim} exceeds hard §H9c-CONTRACT cap {MAX_RESIDUAL_BITS}"
            )
        if not (0.0 <= yield_number <= 1.0):
            raise ValueError(f"yield_number Y must be in [0, 1], got {yield_number}")
        self.k = int(k)
        self.bits_per_dim = int(bits_per_dim)
        self.max_residual_bits = int(k * bits_per_dim)
        self.yield_number = float(yield_number)
        self.use_hodge = bool(use_hodge)
        q_pol, q_tor, p_pol, p_tor, p_urad, p_ulat = _build_hodge_bases(k)
        self.register_buffer("Q_pol", q_pol)
        self.register_buffer("Q_tor", q_tor)
        self.register_buffer("P_pol", p_pol)
        self.register_buffer("P_tor", p_tor)
        self.register_buffer("P_unstruct_rad", p_urad)
        self.register_buffer("P_unstruct_lat", p_ulat)

    def bingham_soft_threshold(self, u: torch.Tensor) -> torch.Tensor:
        """Track S43 two-sided ReLU proximal operator: ReLU(u - tau_Y) - ReLU(-u - tau_Y)."""
        if self.yield_number >= 1.0:
            return torch.zeros_like(u)
        if self.yield_number <= 0.0:
            return u
        sigma_u = u.detach().abs().amax(dim=-1, keepdim=True).clamp_min(1e-8)
        tau_y = self.yield_number * sigma_u
        return F.relu(u - tau_y) - F.relu(-u - tau_y)

    def forward(self, u: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, dict[str, float]]:
        """Return (r_pol_to_core [B, k], u_tor_lateral [B, k], channel2b_airlock_diag)."""
        u_f = u.float()
        if self.use_hodge:
            c_pol = torch.matmul(u_f, self.Q_pol)
            u_pol = torch.matmul(c_pol, self.Q_pol.T)
            u_tor = torch.matmul(u_f, self.P_tor)
            v_c = self.bingham_soft_threshold(c_pol)
            v = torch.matmul(v_c, self.Q_pol.T)
            active_src = v_c
        else:
            u_pol = torch.matmul(u_f, self.P_unstruct_rad)
            u_tor = torch.matmul(u_f, self.P_unstruct_lat)
            v = self.bingham_soft_threshold(u_pol)
            active_src = v

        if u_f.numel() > 0:
            denom = (
                torch.linalg.vector_norm(u_pol, dim=-1) * torch.linalg.vector_norm(u_tor, dim=-1)
            ).clamp_min(1e-8)
            orth_err = float((torch.sum(u_pol * u_tor, dim=-1).abs() / denom).max().item())
        else:
            orth_err = 0.0

        v_norm = torch.linalg.vector_norm(v, dim=-1, keepdim=True)
        nonzero_mask = (v_norm > 1e-12).to(u_f.dtype)
        v_unit = (v / v_norm.clamp_min(1e-8)) * nonzero_mask
        v_q = ste_uniform_quantize_3bpw(v_unit, bits=self.bits_per_dim) * nonzero_mask
        vq_norm = torch.linalg.vector_norm(v_q, dim=-1, keepdim=True)
        q_mask = (vq_norm > 1e-12).to(u_f.dtype)
        r = (v_q / vq_norm.clamp_min(1e-8)) * q_mask

        advection_norm = float(torch.linalg.vector_norm(r - v_unit, dim=-1).mean().item()) if u_f.numel() > 0 else 0.0
        active_frac = float((active_src.abs() > 1e-12).float().mean().item()) if u_f.numel() > 0 else 0.0
        diag = {
            "yield_number": self.yield_number,
            "use_hodge": self.use_hodge,
            "max_residual_bits": float(self.max_residual_bits),
            "pol_tor_orthogonality_err": orth_err,
            "channel2b_advection_norm": advection_norm,
            "active_flux_fraction": active_frac,
        }
        return r.to(u.dtype), u_tor.to(u.dtype), diag


# ---------------------------------------------------------------------------
# Shell 1: Rigid Crystalline Zero-Language Inner Core (M -> M, Amendment 3)
# ---------------------------------------------------------------------------


class CausalCoreBlock(nn.Module):
    def __init__(self, d_model: int, n_heads: int, mlp_mult: int = 2, ffn_dim: int | None = None) -> None:
        super().__init__()
        self.d_model = d_model
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        self.ffn_dim = int(ffn_dim if ffn_dim is not None else d_model * mlp_mult)
        self.norm1 = nn.RMSNorm(d_model)
        self.qkv = nn.Linear(d_model, 3 * d_model, bias=False)
        self.out_proj = nn.Linear(d_model, d_model, bias=False)
        self.norm2 = nn.RMSNorm(d_model)
        self.fc1 = nn.Linear(d_model, self.ffn_dim, bias=False)
        self.fc2 = nn.Linear(self.ffn_dim, d_model, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, t, d = x.shape
        h = self.norm1(x)
        qkv = self.qkv(h).reshape(b, t, 3, self.n_heads, self.head_dim)
        q, k, v = qkv[:, :, 0].transpose(1, 2), qkv[:, :, 1].transpose(1, 2), qkv[:, :, 2].transpose(1, 2)
        attn = F.scaled_dot_product_attention(q, k, v, is_causal=True).transpose(1, 2).reshape(b, t, d)
        x = x + self.out_proj(attn)
        x = x + self.fc2(F.gelu(self.fc1(self.norm2(x))))
        return x


class RigidInnerCore(nn.Module):
    """Shell 1: Zero-language M -> M Safe-Hopf Latent-CoT looped Core (AMENDMENT3 SteelmanCore)."""

    def __init__(
        self,
        m_vocab_size: int,
        d_model: int,
        n_heads: int,
        n_layers: int = 2,
        n_loops: int = 4,
        k_res: int = 32,
        n_classes: int = 16,
    ) -> None:
        super().__init__()
        if d_model % 2 != 0:
            raise ValueError(f"d_model must be even for Hopf 2x2 clock, got {d_model}")
        if k_res > MAX_RESIDUAL_DIM:
            raise ValueError(f"k_res ({k_res}) exceeds hard cap {MAX_RESIDUAL_DIM}")
        self.m_vocab_size = m_vocab_size
        self.d_model = d_model
        self.n_layers = n_layers
        self.n_loops = n_loops
        self.k_res = k_res
        self.n_classes = n_classes

        self.m_emb = nn.Embedding(m_vocab_size, d_model)
        self.pos_emb = nn.Embedding(64, d_model)
        self.res_proj = nn.Linear(k_res, d_model, bias=False)
        self.loop_emb = nn.Parameter(torch.randn(n_loops, d_model) * 0.02)
        self.blocks = nn.ModuleList([CausalCoreBlock(d_model, n_heads, mlp_mult=2) for _ in range(n_layers)])
        self.alpha_raw = nn.Parameter(torch.full((n_loops,), -1.2))
        self.norm_out = nn.RMSNorm(d_model)
        self.inter_head = nn.Linear(d_model, n_classes)
        self.ans_head = nn.Linear(d_model, n_classes)
        self.frozen_sha256: str | None = None

    def core_weights_sha256(self) -> str:
        h = hashlib.sha256()
        for name, p in sorted(self.named_parameters()):
            h.update(name.encode("ascii") + b"\x00")
            h.update(p.detach().cpu().contiguous().numpy().tobytes())
        return h.hexdigest()

    def freeze_and_pin(self) -> str:
        self.zero_grad(set_to_none=True)
        for p in self.parameters():
            p.requires_grad_(False)
        self.frozen_sha256 = self.core_weights_sha256()
        return self.frozen_sha256

    def _hopf_clock(self, x: torch.Tensor, r: int) -> torch.Tensor:
        """Strictly non-antipodal Hopf clock (W10-OBS-31): phi_r = pi*(r+1)/(2*R + 1) in (0, pi/2)."""
        phi = math.pi * float(r + 1) / float(2 * max(self.n_loops, 1) + 1)
        c = math.cos(phi)
        s = math.sin(phi)
        xe = x[..., 0::2]
        xo = x[..., 1::2]
        return torch.stack([xe * c - xo * s, xe * s + xo * c], dim=-1).reshape_as(x)

    def forward(
        self,
        m_token_ids: torch.Tensor,
        residual_r: torch.Tensor | None = None,
        patch_pass_idx: int | None = None,
        patch_state: torch.Tensor | None = None,
        m_soft_embeds: torch.Tensor | None = None,
    ) -> dict[str, Any]:
        """Execute zero-language M -> M looped reasoning with causal <EOS> pooling & h^(r) patching."""
        b = int(m_token_ids.shape[0])
        if m_soft_embeds is not None:
            seq_len = int(m_soft_embeds.shape[1])
            pos = torch.arange(seq_len, device=m_soft_embeds.device)
            x = m_soft_embeds + self.pos_emb(pos).unsqueeze(0)
        else:
            seq_len = int(m_token_ids.shape[1])
            pos = torch.arange(seq_len, device=m_token_ids.device)
            x = self.m_emb(m_token_ids) + self.pos_emb(pos).unsqueeze(0)
        if residual_r is not None:
            x = x + self.res_proj(residual_r).unsqueeze(1)
        h = safe_clamped_unit(x, dim=-1, floor=1e-4)

        loop_states: list[torch.Tensor] = []
        for r in range(self.n_loops):
            y = h + self.loop_emb[r].view(1, 1, -1)
            for blk in self.blocks:
                y = blk(y)
            alpha = torch.sigmoid(self.alpha_raw[r]) * (0.5 * math.pi)
            rot = self._hopf_clock(safe_clamped_unit(y - h, dim=-1, floor=1e-4), r)
            h = safe_clamped_unit(torch.cos(alpha) * h + torch.sin(alpha) * rot, dim=-1, floor=1e-4)
            if patch_pass_idx is not None and r == patch_pass_idx and patch_state is not None:
                h = patch_state
            loop_states.append(h)

        # Causal last-non-pad (<EOS>) pooling: bit-identical across ir_len=12 Native & ir_len=24 Human modes!
        last_idx = _last_nonpad_indices(m_token_ids, pad_id=0)
        batch_idx = torch.arange(b, device=m_token_ids.device)
        mid_idx = max(0, self.n_loops // 2 - 1)
        mid_pooled = self.norm_out(loop_states[mid_idx][batch_idx, last_idx])
        pooled = self.norm_out(h[batch_idx, last_idx])
        return {
            "inter_logits": self.inter_head(mid_pooled),
            "ans_logits": self.ans_head(pooled),
            "pooled_hidden": pooled,
            "last_idx": last_idx,
            "loop_states": loop_states,
        }


# ---------------------------------------------------------------------------
# Shell 3: Swappable Lithospheric Plates (MHPlate), Audit Decoder, & Seam Router
# ---------------------------------------------------------------------------


class ExternalSurfacePlate(nn.Module):
    """Shell 3 modular external converter (MHPlate, Amendment 3): strictly outside frozen Core; zero skip paths!"""

    def __init__(
        self,
        d_ext: int,
        m_vocab_size: int,
        ir_len: int,
        k_res: int = 32,
        n_classes: int = 16,
        max_surf_len: int = 128,
        n_heads: int = 8,
        n_layers: int = 1,
    ) -> None:
        super().__init__()
        if d_ext % n_heads != 0:
            # Automatically select largest divisor <= n_heads for arbitrary test d_ext
            for h_try in range(min(n_heads, d_ext), 0, -1):
                if d_ext % h_try == 0:
                    n_heads = h_try
                    break
        self.d_ext = d_ext
        self.n_heads = n_heads
        self.head_dim = d_ext // n_heads
        self.n_layers = n_layers
        self.m_vocab_size = m_vocab_size
        self.ir_len = ir_len
        self.k_res = k_res
        self.max_surf_len = max_surf_len

        self.byte_emb = nn.Embedding(256, d_ext)
        self.pos_emb = nn.Embedding(max_surf_len, d_ext)
        self.conv = nn.Conv1d(d_ext, d_ext, kernel_size=5, padding=2)
        self.enc_blocks = nn.ModuleList([CausalCoreBlock(d_ext, n_heads, mlp_mult=2) for _ in range(n_layers)])
        self.norm_seq = nn.RMSNorm(d_ext)
        # Multi-head cross-attention queries: ir_len IR token queries + 1 residual query
        self.ir_queries = nn.Parameter(torch.randn(ir_len + 1, d_ext) * 0.05)
        self.q_proj = nn.Linear(d_ext, d_ext, bias=False)
        self.kv_proj = nn.Linear(d_ext, 2 * d_ext, bias=False)
        self.xattn_out = nn.Linear(d_ext, d_ext, bias=False)
        self.norm_out = nn.RMSNorm(d_ext)
        # ext_in heads: per-slot IR token IDs and pre-Bingham residual u in R^k
        self.ir_head = nn.Linear(d_ext, m_vocab_size)
        self.res_head = nn.Linear(d_ext, k_res)
        # ext_out head: purely formats Core's discrete M answer logits (NEVER takes ext_in features!)
        self.ext_out_head = nn.Linear(n_classes, n_classes)

    def encode_surface(self, surface_bytes: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Map raw UTF-8 surface bytes -> (ir_token_logits [B, ir_len, V_M], pre_bingham_u [B, k])."""
        b, seq_len = surface_bytes.shape
        if seq_len > self.max_surf_len:
            raise ValueError(f"surface seq_len {seq_len} exceeds max_surf_len {self.max_surf_len}")
        pos = torch.arange(seq_len, device=surface_bytes.device)
        h = self.byte_emb(surface_bytes) + self.pos_emb(pos).unsqueeze(0)
        h = h + F.silu(self.conv(h.transpose(1, 2))).transpose(1, 2)
        for blk in self.enc_blocks:
            h = blk(h)
        seq = self.norm_seq(h)
        q = self.q_proj(self.ir_queries).unsqueeze(0).expand(b, -1, -1)
        q = q.reshape(b, self.ir_len + 1, self.n_heads, self.head_dim).transpose(1, 2)
        kv = self.kv_proj(seq).reshape(b, seq_len, 2, self.n_heads, self.head_dim)
        k_t = kv[:, :, 0].transpose(1, 2)
        v_t = kv[:, :, 1].transpose(1, 2)
        attn = F.scaled_dot_product_attention(q, k_t, v_t).transpose(1, 2).reshape(b, self.ir_len + 1, self.d_ext)
        out = self.norm_out(self.xattn_out(attn))
        ir_logits = self.ir_head(out[:, :-1, :])
        u = self.res_head(out[:, -1, :])
        return ir_logits, u

    def decode_core_output(self, core_ans_logits: torch.Tensor) -> torch.Tensor:
        """External output converter taking ONLY the Core's discrete M output channel."""
        return self.ext_out_head(core_ans_logits)


class AuditTraceDecoder(nn.Module):
    """Mandatory human-readable audit decoder mapping intermediate Core state h^(r) -> step trace.

    Explicitly charged in P_total and F_infer (AMENDMENT1 §3.1) and audited via counterfactual
    h^(r) state patching (AMENDMENT1 §5.1).
    """

    def __init__(self, d_model: int, n_classes: int = 16) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.SiLU(),
            nn.Linear(d_model, n_classes * 2),
        )
        self.n_classes = n_classes

    def forward(self, h_mid: torch.Tensor, last_idx: torch.Tensor | None = None) -> tuple[torch.Tensor, torch.Tensor]:
        if last_idx is not None:
            batch_idx = torch.arange(int(h_mid.shape[0]), device=h_mid.device)
            pooled = h_mid[batch_idx, last_idx]
        else:
            pooled = h_mid[:, -1, :]
        out = self.net(pooled)
        return out[:, : self.n_classes], out[:, self.n_classes :]


class PlateSeamRouter(nn.Module):
    """Track S43 Pillar-3 multi-plate seam router with exact cocycle conservation sum(alpha_i) = 1."""

    def __init__(self, k_res: int, n_plates: int) -> None:
        super().__init__()
        self.k_res = k_res
        self.n_plates = n_plates
        self.seam_scorer = nn.Linear(k_res, 1)
        self.ir_router = nn.Sequential(nn.Linear(k_res * n_plates, 32), nn.SiLU(), nn.Linear(32, n_plates))
        self.res_router = nn.Sequential(nn.Linear(k_res * n_plates, 32), nn.SiLU(), nn.Linear(32, n_plates))

    def blend_plates(
        self,
        plate_ir_logits: Sequence[torch.Tensor],
        plate_u_tor: Sequence[torch.Tensor],
        plate_r_pol: Sequence[torch.Tensor],
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Combine P plates using orthogonal Toroidal channel u_tor with exact sum(alpha_i) == 1."""
        if len(plate_ir_logits) != self.n_plates:
            raise ValueError(f"expected {self.n_plates} plates, got {len(plate_ir_logits)}")
        scores = torch.cat([self.seam_scorer(u_t) for u_t in plate_u_tor], dim=-1)
        alphas = F.softmax(scores, dim=-1)
        blended_ir = sum(alphas[:, i].view(-1, 1, 1) * plate_ir_logits[i] for i in range(self.n_plates))
        blended_r = sum(alphas[:, i].view(-1, 1) * plate_r_pol[i] for i in range(self.n_plates))
        return blended_ir, blended_r, alphas

    def blend_plates_dual(
        self,
        plate_ir_logits: Sequence[torch.Tensor],
        plate_u_tor: Sequence[torch.Tensor],
        plate_r_pol: Sequence[torch.Tensor],
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Dual-seam cocycle-conserving routing (sum alpha_ir == 1, sum alpha_res == 1) from lateral u_tor."""
        if len(plate_ir_logits) != self.n_plates:
            raise ValueError(f"expected {self.n_plates} plates, got {len(plate_ir_logits)}")
        cat_tor = torch.cat(list(plate_u_tor), dim=-1)
        alphas_ir = F.softmax(self.ir_router(cat_tor), dim=-1)
        alphas_res = F.softmax(self.res_router(cat_tor), dim=-1)
        blended_ir = sum(alphas_ir[:, i].view(-1, 1, 1) * plate_ir_logits[i] for i in range(self.n_plates))
        blended_r = sum(alphas_res[:, i].view(-1, 1) * plate_r_pol[i] for i in range(self.n_plates))
        return blended_ir, blended_r, alphas_ir, alphas_res


# ---------------------------------------------------------------------------
# Monolithic / English-CoT (2-Step Steelman) / Direct / Compressed-Binary Controls
# ---------------------------------------------------------------------------


class MonolithicByteReasoner(nn.Module):
    """Fair compact byte-level reasoner for Arm A (2-step CoT), Arm A' (Direct), & Arm B (Deflate)."""

    def __init__(
        self,
        d_model: int,
        n_heads: int,
        n_layers: int,
        n_classes: int = 16,
        max_len: int = 128,
        mlp_mult: int = 2,
        ffn_dim: int | None = None,
    ) -> None:
        super().__init__()
        self.d_model = d_model
        self.n_layers = n_layers
        self.mlp_mult = mlp_mult
        self.ffn_dim = int(ffn_dim if ffn_dim is not None else d_model * mlp_mult)
        self.byte_emb = nn.Embedding(256, d_model)
        self.pos_emb = nn.Embedding(max_len, d_model)
        self.inter_emb = nn.Embedding(n_classes, d_model)
        self.blocks = nn.ModuleList(
            [CausalCoreBlock(d_model, n_heads, mlp_mult=mlp_mult, ffn_dim=self.ffn_dim) for _ in range(n_layers)]
        )
        self.norm_out = nn.RMSNorm(d_model)
        self.inter_head = nn.Linear(d_model, n_classes)
        self.ans_head = nn.Linear(d_model, n_classes)

    def encode_sequence(self, byte_ids: torch.Tensor) -> torch.Tensor:
        seq_len = int(byte_ids.shape[1])
        pos = torch.arange(seq_len, device=byte_ids.device)
        x = self.byte_emb(byte_ids) + self.pos_emb(pos).unsqueeze(0)
        for blk in self.blocks:
            x = blk(x)
        return self.norm_out(x)

    def forward(
        self,
        byte_ids: torch.Tensor,
        use_cot_conditioning: bool = False,
        teacher_inter: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Run single-pass (Arm A'/B) OR genuine 2-step CoT conditioning (Arm A, Amendment 3)."""
        b, seq_len = byte_ids.shape
        pos = torch.arange(seq_len, device=byte_ids.device)
        last_idx = _last_nonpad_indices(byte_ids, pad_id=0)
        batch_idx = torch.arange(b, device=byte_ids.device)

        x = self.byte_emb(byte_ids) + self.pos_emb(pos).unsqueeze(0)
        if not use_cot_conditioning:
            for blk in self.blocks:
                x = blk(x)
            pooled = self.norm_out(x[batch_idx, last_idx])
            return {"inter_logits": self.inter_head(pooled), "ans_logits": self.ans_head(pooled)}

        # Genuine 2-step CoT: first half computes inter = (a op b) mod 16, injects CoT step token at <EOS>,
        # second half computes final answer = (inter + c + mod) mod 16!
        split = max(1, self.n_layers // 2)
        for blk in self.blocks[:split]:
            x = blk(x)
        inter_logits = self.inter_head(self.norm_out(x[batch_idx, last_idx]))
        inter_tok = teacher_inter if teacher_inter is not None else inter_logits.detach().argmax(dim=-1)
        x = x.clone()
        x[batch_idx, last_idx] = x[batch_idx, last_idx] + self.inter_emb(inter_tok)
        for blk in self.blocks[split:]:
            x = blk(x)
        pooled = self.norm_out(x[batch_idx, last_idx])
        return {"inter_logits": inter_logits, "ans_logits": self.ans_head(pooled)}


class ByteStreamProbeAndDecompressor(nn.Module):
    """Matched byte-level sequence head (tied to byte_emb) for H9a decompressor emulation & probe-LM."""

    def __init__(
        self,
        d_model: int,
        n_heads: int,
        n_layers: int,
        max_len: int = 128,
        mlp_mult: int = 2,
        ffn_dim: int | None = None,
    ) -> None:
        super().__init__()
        self.backbone = MonolithicByteReasoner(
            d_model=d_model, n_heads=n_heads, n_layers=n_layers, max_len=max_len, mlp_mult=mlp_mult, ffn_dim=ffn_dim
        )

    def forward(self, byte_ids: torch.Tensor) -> torch.Tensor:
        h = self.backbone.encode_sequence(byte_ids)
        return F.linear(h, self.backbone.byte_emb.weight)


# ---------------------------------------------------------------------------
# CS-21 Anti-Smuggling Verification, Residual-Leak Probe, & Portal-5 Darboux Diagnostic
# ---------------------------------------------------------------------------


def verify_zero_skip_paths(
    plate: ExternalSurfacePlate,
    asthenosphere: ViscoplasticAsthenosphere,
    core: RigidInnerCore,
    surface_bytes: torch.Tensor,
    ir_ids: torch.Tensor,
) -> dict[str, Any]:
    """Graph check proving zero edges connect ext_in directly to ext_out bypassing Shell-1 Core."""
    plate.zero_grad(set_to_none=True)
    _, u = plate.encode_surface(surface_bytes)
    r_pol, _, _ = asthenosphere(u)
    core_out = core(ir_ids, residual_r=r_pol)
    ext_out_detached = plate.decode_core_output(core_out["ans_logits"].detach())
    ext_out_detached.sum().backward()
    ext_in_grad = 0.0
    for name, p in plate.named_parameters():
        if not name.startswith("ext_out_head") and p.grad is not None:
            ext_in_grad = max(ext_in_grad, float(p.grad.abs().max().item()))
    plate.zero_grad(set_to_none=True)
    return {"zero_skip_path_verified": ext_in_grad == 0.0, "max_skip_grad": ext_in_grad}


def run_residual_leak_probe(
    r_train: torch.Tensor,
    y_train: torch.Tensor,
    r_eval: torch.Tensor,
    y_eval: torch.Tensor,
    n_classes: int = 16,
    steps: int = 120,
    seed: int = 42,
) -> dict[str, Any]:
    """AMENDMENT1 §1.4 adversarial <= 50k-param MLP probe predicting answer directly from r alone.

    Fails closed (`cs21_residual_leak_triggered = True`) if probe_acc >= chance + 0.25.
    """
    torch.manual_seed(seed)
    k = int(r_train.shape[-1])
    probe = nn.Sequential(nn.Linear(k, 128), nn.ReLU(), nn.Linear(128, 64), nn.ReLU(), nn.Linear(64, n_classes)).to(
        r_train.device
    )
    probe_params = sum(p.numel() for p in probe.parameters())
    if probe_params > 50_000:
        raise RuntimeError(f"residual leak probe exceeds 50k cap: {probe_params}")
    opt = torch.optim.AdamW(probe.parameters(), lr=1.5e-2)
    r_tr = r_train.detach().float()
    r_ev = r_eval.detach().float()
    for _ in range(steps):
        opt.zero_grad(set_to_none=True)
        loss = F.cross_entropy(probe(r_tr), y_train)
        loss.backward()
        opt.step()
    probe.eval()
    with torch.no_grad():
        preds = probe(r_ev).argmax(dim=-1)
        acc = float((preds == y_eval).float().mean().item())
    chance = 1.0 / float(n_classes)
    margin = acc - chance
    return {
        "probe_params": probe_params,
        "chance_acc": round(chance, 6),
        "probe_acc": round(acc, 6),
        "above_chance": round(margin, 6),
        "cs21_residual_leak_triggered": margin >= 0.25,
    }


def darboux_dark_mode_diagnostic(A: torch.Tensor, x_batch: torch.Tensor, shift_c: float = 1.0 / 7.0) -> dict[str, Any]:
    """Portal-5 Darboux isospectral intertwining & exact dark-mode kernel-loss diagnostic."""
    a64 = A.detach().to(torch.float64)
    x64 = x_batch.detach().to(torch.float64)
    m, n = a64.shape
    l1 = a64.T @ a64 + shift_c * torch.eye(n, dtype=torch.float64, device=a64.device)
    l2 = a64 @ a64.T + shift_c * torch.eye(m, dtype=torch.float64, device=a64.device)
    intertwine_err = float(torch.linalg.matrix_norm(a64 @ l1 - l2 @ a64).item())

    _, s_vals, vh = torch.linalg.svd(a64, full_matrices=True)
    tol = max(m, n) * 1e-10 * float(s_vals[0].item() if s_vals.numel() > 0 else 1.0)
    rank = int((s_vals > tol).sum().item())
    dark_dim = n - rank
    v_range = vh[:rank, :].T
    proj_r = v_range @ v_range.T
    x_recon = x64 @ proj_r
    residual = x64 - x_recon
    total_energy = float((x64 * x64).sum(dim=-1).clamp_min(1e-12).mean().item())
    dark_mass = float((residual * residual).sum(dim=-1).mean().item())
    dark_fraction = float(((residual * residual).sum(dim=-1) / (x64 * x64).sum(dim=-1).clamp_min(1e-12)).mean().item())
    return {
        "shape_m_n": [m, n],
        "rank": rank,
        "dark_dim": dark_dim,
        "darboux_intertwine_err": intertwine_err,
        "mean_input_energy": round(total_energy, 6),
        "mean_dark_mode_loss": round(dark_mass, 6),
        "mean_dark_mode_fraction": round(dark_fraction, 6),
    }


# ---------------------------------------------------------------------------
# Triple CS-08 Resource Parity Accounting (P_total, F_train_total, F_infer)
# ---------------------------------------------------------------------------


def count_module_params(mod: nn.Module) -> int:
    return sum(p.numel() for p in mod.parameters())


def compute_system_resource_ledger(
    *,
    p_core: int,
    p_ext_in: int,
    p_ext_out: int,
    p_audit_head: int,
    core_d: int,
    core_layers: int,
    core_loops: int,
    core_seq: int,
    ext_d: int,
    ext_seq: int,
    train_steps_total: int,
    batch_size: int,
    mlp_mult: int = 2,
    core_ffn_dim: int | None = None,
    ext_layers: int = 1,
    m_vocab_size: int = 33,
) -> dict[str, int]:
    """Exact CS-08 / CS-21 resource accounting charging Core + MHPlate ext_in + ext_out + audit_head."""
    p_total = p_core + p_ext_in + p_ext_out + p_audit_head
    c_ffn = int(core_ffn_dim if core_ffn_dim is not None else core_d * mlp_mult)
    core_per_layer = 2 * (4 * core_d * core_d + 2 * core_seq * core_d + 2 * core_d * c_ffn)
    f_core_infer = core_seq * core_layers * core_loops * core_per_layer
    if ext_d > 0 and ext_seq > 0:
        ext_per_layer = 2 * (4 * ext_d * ext_d + 2 * ext_seq * ext_d + 2 * ext_d * (ext_d * 2))
        f_ext_infer = (
            2 * ext_seq * (5 * ext_d * ext_d)
            + ext_seq * ext_layers * ext_per_layer
            + 2 * (core_seq + 1) * (2 * ext_d * ext_d + 2 * ext_seq * ext_d)
            + 2 * ext_seq * (2 * ext_d * ext_d)
            + 2 * (p_ext_out + p_audit_head + (core_seq + 1) * ext_d * m_vocab_size)
        )
    else:
        f_ext_infer = 0
    f_infer = int(f_core_infer + f_ext_infer)
    f_train_total = int(3 * f_infer * batch_size * train_steps_total)
    return {
        "P_core": int(p_core),
        "P_ext_in": int(p_ext_in),
        "P_ext_out": int(p_ext_out),
        "P_audit_head": int(p_audit_head),
        "P_total": int(p_total),
        "F_core_infer": int(f_core_infer),
        "F_infer": f_infer,
        "F_train_total": f_train_total,
    }
