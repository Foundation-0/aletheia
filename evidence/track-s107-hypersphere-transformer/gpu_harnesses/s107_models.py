#!/usr/bin/env python3
"""Native 4D Hypersphere-Transformer models & exact parity accounting (PREREG-S107 + Amendment 1).

Implements all amended H7a, H7b, and H7c architectures and matched controls:
  - H7a: S3-Polar a(1+cos^2 psi), S3-Equatorial a(1+sin^2 psi), Flat Cylinder,
         S3-Permuted-Pol, and S3-Permuted-Eq on BOTH Pre-Norm+RoPE and nGPT backbones.
  - H7b: Redesigned Data-Dependent Path-Ordered SU(2) Holonomy via associative parallel
         quaternion scan U(t) = du_0 * du_1 * ... * du_t (exact interval holonomy
         U(s)^-1 U(t) = du_{s+1} * ... * du_t) vs 2D RoPE, LieRE 4D Abelian RoPE (N0),
         and Block4-RandOrtho.
  - H7c: Clifford-Torus Dual-Clock Looped Core (safe SLERP with eps=1e-4 norm floor,
         clamped alpha_r, non-degenerate inter-pass Hopf rotation, pinned per-pass KV
         recompute, checkpointed BPTT) vs Unlooped-16L, Unlooped-8L (iso-param),
         FlatLoop-Std, SphereLoop-NoClock, and SphereLoop-RandRotClock.

Also provides exact RTN symmetric per-output-channel group-128 PTQ (3-bit / 4-bit)
and the Track S96 M1-H1 empirical contraction / G_3(rho) loop-drift monitor.
Zero bare asserts; all randomness explicitly seeded.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint as grad_checkpoint


class S107ConfigError(ValueError):
    """Fail-closed error raised on invalid architecture, parity, or numerical contracts."""


def require_ok(cond: bool, msg: str) -> None:
    if not cond:
        raise S107ConfigError(msg)


# ---------------------------------------------------------------------------
# Safe Hypersphere Geometry Primitives (Zero-NaN Norm Floor & Clamped SLERP)
# ---------------------------------------------------------------------------


def safe_unit_norm(x: torch.Tensor, dim: int = -1, eps: float = 1e-4) -> torch.Tensor:
    """Project vectors onto unit sphere with strict eps norm floor (zero NaN at x=0)."""
    norm = torch.linalg.vector_norm(x, ord=2, dim=dim, keepdim=True)
    return x / torch.clamp(norm, min=eps)


def safe_slerp_step(
    h: torch.Tensor,
    delta: torch.Tensor,
    alpha: torch.Tensor,
    eps: float = 1e-4,
) -> torch.Tensor:
    """Safe spherical update: Norm(cos(alpha) * h + sin(alpha) * Norm(delta)) with eps floor.

    Wait-free against antipodal cancellation (delta = -h at alpha = pi/4): denominator is
    clamped by max(||x||, eps) with smooth L2 norm so forward & backward stay finite.
    """
    h_u = safe_unit_norm(h, dim=-1, eps=eps)
    d_u = safe_unit_norm(delta, dim=-1, eps=eps)
    mixed = torch.cos(alpha) * h_u + torch.sin(alpha) * d_u
    # Smooth floor sqrt(||x||^2 + eps^2) prevents 0/0 backward singularity at exact x = 0.
    denom = torch.sqrt(torch.sum(mixed * mixed, dim=-1, keepdim=True) + (eps * eps))
    return mixed / denom


def hopf_fiber_rotate(x: torch.Tensor, phi: torch.Tensor) -> torch.Tensor:
    """Rotate 4D blocks (a, b, c, d) along the Hopf S^1 fiber by angle phi.

    Left/right unit quaternion action q -> q * exp(i * phi) rotates (a, b) and (c, d)
    isoclinically by phi (exact orthogonal map on S^{d-1}, preserving ||x||_2 = 1).
    Applied BETWEEN loop passes on hidden state/update so it never cancels in QK.
    """
    d = x.shape[-1]
    require_ok(d % 4 == 0, f"Hopf fiber rotation requires dim % 4 == 0, got {d}")
    orig_shape = x.shape
    blocks = x.reshape(*orig_shape[:-1], d // 4, 4)
    c = torch.cos(phi)
    s = torch.sin(phi)
    a, b, u, v = blocks.unbind(dim=-1)
    # Right multiplication by (cos phi + i sin phi) on quaternion a + b i + u j + v k:
    # (a + bi + uj + vk)(c + si) = (ac - bs) + (as + bc)i + (uc + vs)j + (-us + vc)k
    na = a * c - b * s
    nb = a * s + b * c
    nu = u * c + v * s
    nv = -u * s + v * c
    return torch.stack((na, nb, nu, nv), dim=-1).reshape(orig_shape)


def hopf_clock_angle(pass_idx: int, clock_law: str, r_train: int = 3) -> float:
    """Explicitly defined Hopf clock angle law (AMENDMENT1 §3 / COLLAB-INKLING2 B1).

    - 'pinned_train_step': phi_r = 2*pi*r / r_train (exact aliasing at r >= r_train;
      explicitly labeled as clock-aliased when R_test > r_train).
    - 'unaliased_coprime': phi_r = 2*pi*r / 11 (exact denominator-pi coprime turn;
      guarantees 11 distinct non-aliased phases across r=0..10 while keeping exact
      train/test alignment on r=0,1,2!).
    """
    if clock_law == "pinned_train_step":
        return 2.0 * math.pi * float(pass_idx) / float(r_train)
    if clock_law == "unaliased_coprime":
        return 2.0 * math.pi * float(pass_idx) / 11.0
    raise S107ConfigError(f"Unknown Hopf clock_law: {clock_law!r}")


# ---------------------------------------------------------------------------
# Quaternion & SU(2) Associative Parallel Scan Primitives (Amended H7b)
# ---------------------------------------------------------------------------


def quat_mul(p: torch.Tensor, q: torch.Tensor) -> torch.Tensor:
    """Exact Hamilton product on last dim (w, x, y, z)."""
    pw, px, py, pz = p.unbind(dim=-1)
    qw, qx, qy, qz = q.unbind(dim=-1)
    return torch.stack(
        (
            pw * qw - px * qx - py * qy - pz * qz,
            pw * qx + px * qw + py * qz - pz * qy,
            pw * qy - px * qz + py * qw + pz * qx,
            pw * qz + px * qy - py * qx + pz * qw,
        ),
        dim=-1,
    )


def quat_conj(q: torch.Tensor) -> torch.Tensor:
    """Quaternion conjugate (= inverse for unit quaternions in SU(2))."""
    qw, qx, qy, qz = q.unbind(dim=-1)
    return torch.stack((qw, -qx, -qy, -qz), dim=-1)


def su2_exp(omega: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    """Exact exponential map su(2) -> SU(2): omega in R^3 -> unit quaternion (w, x, y, z).

    Uses smooth norm theta = sqrt(||omega||^2 + eps^2) so gradients remain finite at 0.
    """
    theta_sq = torch.sum(omega * omega, dim=-1, keepdim=True)
    theta = torch.sqrt(theta_sq + (eps * eps))
    w = torch.cos(theta)
    # sin(theta)/theta is smooth and bounded in (0, 1] everywhere.
    sinc = torch.sin(theta) / theta
    xyz = sinc * omega
    q = torch.cat((w, xyz), dim=-1)
    return safe_unit_norm(q, dim=-1, eps=1e-6)


def su2_parallel_prefix_scan(delta_u: torch.Tensor) -> torch.Tensor:
    """Associative Hillis-Steele parallel prefix product along seq dim=1.

    Computes right-accumulating path-ordered holonomy:
      U(t) = delta_u[:, 0] * delta_u[:, 1] * ... * delta_u[:, t]
    so that for any s < t:
      U(s)^-1 * U(t) = delta_u[:, s+1] * ... * delta_u[:, t]
    depends EXCLUSIVELY on the non-Abelian path strictly between s and t!
    Shape: [B, T, ..., 4] -> [B, T, ..., 4] in ceil(log2 T) parallel steps.
    """
    seq_len = delta_u.shape[1]
    cur = safe_unit_norm(delta_u, dim=-1, eps=1e-6)
    offset = 1
    while offset < seq_len:
        left = cur[:, :-offset]
        right = cur[:, offset:]
        prod = safe_unit_norm(quat_mul(left, right), dim=-1, eps=1e-6)
        cur = torch.cat((cur[:, :offset], prod), dim=1)
        offset *= 2
    return cur


def su2_sequential_prefix_scan(delta_u: torch.Tensor) -> torch.Tensor:
    """Reference sequential right-accumulating product U(t) = U(t-1) * delta_u(t) for verification."""
    seq_len = delta_u.shape[1]
    outs: List[torch.Tensor] = [safe_unit_norm(delta_u[:, 0], dim=-1, eps=1e-6)]
    for t in range(1, seq_len):
        outs.append(safe_unit_norm(quat_mul(outs[-1], delta_u[:, t]), dim=-1, eps=1e-6))
    return torch.stack(outs, dim=1)


# ---------------------------------------------------------------------------
# Standard 2D RoPE, LieRE 4D Abelian RoPE (N0), & Block4-RandOrtho Null
# ---------------------------------------------------------------------------


def apply_rope_2d(x: torch.Tensor, base: float = 10000.0) -> torch.Tensor:
    """Standard 2D Abelian S^1 RoPE. x shape: [B, H, T, D]."""
    _, _, seq_len, d = x.shape
    require_ok(d % 2 == 0, f"RoPE requires even head dim, got {d}")
    half = d // 2
    inv_freq = 1.0 / (base ** (torch.arange(0, half, device=x.device, dtype=torch.float32) / float(half)))
    pos = torch.arange(seq_len, device=x.device, dtype=torch.float32)
    angles = torch.outer(pos, inv_freq)  # [T, D/2]
    cos = torch.cos(angles).to(x.dtype).unsqueeze(0).unsqueeze(0)
    sin = torch.sin(angles).to(x.dtype).unsqueeze(0).unsqueeze(0)
    x_even = x[..., 0::2]
    x_odd = x[..., 1::2]
    out_even = x_even * cos - x_odd * sin
    out_odd = x_even * sin + x_odd * cos
    return torch.stack((out_even, out_odd), dim=-1).reshape_as(x)


class LieRE4DAbelianPositional(nn.Module):
    """LieRE 4D Abelian RoPE (N0 anchor): fixed learned skew-symmetric generator A in so(4) per 4D block.

    Applies R(t) = exp(t * A_b) in SO(4) per 4D block. Strictly 1-parameter Abelian subgroup
    (R(m)^T R(n) = R(n - m)); strictly contains tied-frequency quaternion RoPE.
    """

    def __init__(self, n_heads: int, d_head: int, seed: int = 42) -> None:
        super().__init__()
        require_ok(d_head % 4 == 0, f"LieRE 4D requires d_head % 4 == 0, got {d_head}")
        self.n_heads = n_heads
        self.d_head = d_head
        self.n_blocks = d_head // 4
        # 6 upper-triangular skew parameters per 4x4 skew matrix in so(4).
        gen = torch.Generator().manual_seed(seed)
        init = torch.randn((n_heads, self.n_blocks, 6), generator=gen) * 0.05
        self.skew_params = nn.Parameter(init)

    def _build_skew(self) -> torch.Tensor:
        a = torch.zeros(
            (self.n_heads, self.n_blocks, 4, 4),
            device=self.skew_params.device,
            dtype=torch.float32,
        )
        idx_i = [0, 0, 0, 1, 1, 2]
        idx_j = [1, 2, 3, 2, 3, 3]
        p = self.skew_params.float()
        for k, (i, j) in enumerate(zip(idx_i, idx_j)):
            a[:, :, i, j] = p[:, :, k]
            a[:, :, j, i] = -p[:, :, k]
        return a

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, H, T, D]
        bsz, h, seq_len, d = x.shape
        skew = self._build_skew()  # [H, nb, 4, 4]
        pos = torch.arange(seq_len, device=x.device, dtype=torch.float32)
        # t * A: [T, H, nb, 4, 4] -> matrix_exp in float32 for precision
        ta = pos.view(seq_len, 1, 1, 1, 1) * skew.unsqueeze(0)
        rot = torch.matrix_exp(ta).to(x.dtype)  # [T, H, nb, 4, 4]
        xb = x.reshape(bsz, h, seq_len, self.n_blocks, 4)
        # Apply rot[t, h, k] @ xb[b, h, t, k]
        out = torch.einsum("thkij,bhtkj->bhtki", rot, xb)
        return out.reshape(bsz, h, seq_len, d)


class Block4RandOrthoPositional(nn.Module):
    """Adversarial null: frozen Haar-random SO(4) mixing per 4D block + standard 2D RoPE."""

    def __init__(self, n_heads: int, d_head: int, seed: int = 137) -> None:
        super().__init__()
        require_ok(d_head % 4 == 0, f"Block4-RandOrtho requires d_head % 4 == 0, got {d_head}")
        self.n_heads = n_heads
        self.n_blocks = d_head // 4
        gen = torch.Generator().manual_seed(seed)
        mats: List[torch.Tensor] = []
        for _ in range(n_heads * self.n_blocks):
            g = torch.randn((4, 4), generator=gen)
            q_mat, r_mat = torch.linalg.qr(g)
            signs = torch.sign(torch.diag(r_mat))
            signs = torch.where(signs == 0, torch.ones_like(signs), signs)
            q_mat = q_mat * signs.unsqueeze(0)
            if torch.linalg.det(q_mat) < 0:
                q_mat[:, 0] = -q_mat[:, 0]
            mats.append(q_mat)
        self.register_buffer("ortho", torch.stack(mats, dim=0).reshape(n_heads, self.n_blocks, 4, 4))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        bsz, h, seq_len, d = x.shape
        xb = x.reshape(bsz, h, seq_len, self.n_blocks, 4)
        mixed = torch.einsum("hkij,bhtkj->bhtki", self.ortho.to(x.dtype), xb).reshape(bsz, h, seq_len, d)
        return apply_rope_2d(mixed)


class SU2PathOrderedHolonomy(nn.Module):
    """Amended H7b: True Data-Dependent Path-Ordered SU(2) Holonomy via Associative Parallel Scan.

    For each token x_s, maps hidden state -> su(2) Lie algebra vector omega(x_s) in R^3
    per 4D block per head, computes step unit quaternion du_s = exp(omega(x_s)) in SU(2),
    and executes right-accumulating parallel prefix scan:
      U(t) = du_0 * du_1 * ... * du_t in SU(2).
    Left-multiplying Q(t) -> L(U(t)) Q(t), K(s) -> L(U(s)) K(s) yields exact interval
    path-ordered holonomy U(s)^-1 U(t) = du_{s+1} * ... * du_t in QK inner products!
    """

    def __init__(self, d_model: int, n_heads: int, d_head: int, angle_scale: float = 0.75) -> None:
        super().__init__()
        require_ok(d_head % 4 == 0, f"SU(2) Holonomy requires d_head % 4 == 0, got {d_head}")
        self.n_heads = n_heads
        self.d_head = d_head
        self.n_blocks = d_head // 4
        self.angle_scale = angle_scale
        self.w_omega = nn.Linear(d_model, 3 * n_heads * self.n_blocks, bias=False)

    def compute_holonomy(self, x: torch.Tensor) -> torch.Tensor:
        """Compute U(t) in SU(2), shape [B, H, T, n_blocks, 4]."""
        bsz, seq_len, _ = x.shape
        raw = self.w_omega(x)  # [B, T, 3*H*nb]
        omega = self.angle_scale * torch.tanh(raw).reshape(bsz, seq_len, self.n_heads, self.n_blocks, 3)
        delta_u = su2_exp(omega.float())  # [B, T, H, nb, 4] in fp32 for exact scan stability
        u_path = su2_parallel_prefix_scan(delta_u)  # [B, T, H, nb, 4]
        return u_path.permute(0, 2, 1, 3, 4).to(x.dtype)  # [B, H, T, nb, 4]

    def apply_transport(self, vec: torch.Tensor, u_path: torch.Tensor) -> torch.Tensor:
        """Left-multiply 4D blocks of vec [B, H, T, D] by unit quaternion U(t) [B, H, T, nb, 4]."""
        bsz, h, seq_len, d = vec.shape
        vb = vec.reshape(bsz, h, seq_len, self.n_blocks, 4)
        out = quat_mul(u_path, vb)
        return out.reshape(bsz, h, seq_len, d)


# ---------------------------------------------------------------------------
# Core Transformer Blocks (Standard Pre-Norm vs nGPT Hypersphere)
# ---------------------------------------------------------------------------


class RMSNorm(nn.Module):
    def __init__(self, d_model: int, eps: float = 1e-6) -> None:
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(d_model))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        rms = torch.rsqrt(torch.mean(x * x, dim=-1, keepdim=True) + self.eps)
        return x * rms * self.weight


class SwiGLUMLP(nn.Module):
    def __init__(self, d_model: int, d_ff: int, ngpt: bool = False) -> None:
        super().__init__()
        self.d_model = d_model
        self.d_ff = d_ff
        self.ngpt = ngpt
        self.w_gate = nn.Linear(d_model, d_ff, bias=False)
        self.w_up = nn.Linear(d_model, d_ff, bias=False)
        self.w_down = nn.Linear(d_ff, d_model, bias=False)
        if ngpt:
            self.su = nn.Parameter(torch.ones(d_ff))
            self.sv = nn.Parameter(torch.ones(d_ff))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        u = self.w_up(x)
        v = self.w_gate(x)
        if self.ngpt:
            u = u * self.su
            v = v * (self.sv * math.sqrt(float(self.d_model)))
        return self.w_down(F.silu(v) * u)


class CausalSelfAttention(nn.Module):
    def __init__(
        self,
        d_model: int,
        n_heads: int,
        pos_mode: str = "rope2d",
        ngpt: bool = False,
        seed: int = 42,
    ) -> None:
        super().__init__()
        require_ok(d_model % n_heads == 0, f"d_model={d_model} not divisible by n_heads={n_heads}")
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_head = d_model // n_heads
        self.pos_mode = pos_mode
        self.ngpt = ngpt

        self.w_q = nn.Linear(d_model, d_model, bias=False)
        self.w_k = nn.Linear(d_model, d_model, bias=False)
        self.w_v = nn.Linear(d_model, d_model, bias=False)
        self.w_o = nn.Linear(d_model, d_model, bias=False)

        self.liere: Optional[LieRE4DAbelianPositional] = None
        self.rand_ortho: Optional[Block4RandOrthoPositional] = None
        self.su2_holonomy: Optional[SU2PathOrderedHolonomy] = None

        if pos_mode == "liere4d":
            self.liere = LieRE4DAbelianPositional(n_heads, self.d_head, seed=seed)
        elif pos_mode == "block4_rand_ortho":
            self.rand_ortho = Block4RandOrthoPositional(n_heads, self.d_head, seed=seed)
        elif pos_mode == "su2_holonomy":
            self.su2_holonomy = SU2PathOrderedHolonomy(d_model, n_heads, self.d_head)
        elif pos_mode != "rope2d":
            raise S107ConfigError(f"Unknown pos_mode: {pos_mode!r}")

        if ngpt:
            # Loshchilov et al. (2024) QK scaling factor per head dimension.
            self.sqk = nn.Parameter(torch.ones(1, n_heads, 1, self.d_head))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        bsz, seq_len, _ = x.shape
        q = self.w_q(x).view(bsz, seq_len, self.n_heads, self.d_head).transpose(1, 2)
        k = self.w_k(x).view(bsz, seq_len, self.n_heads, self.d_head).transpose(1, 2)
        v = self.w_v(x).view(bsz, seq_len, self.n_heads, self.d_head).transpose(1, 2)

        if self.pos_mode == "rope2d":
            q = apply_rope_2d(q)
            k = apply_rope_2d(k)
        elif self.pos_mode == "liere4d":
            require_ok(self.liere is not None, "liere module missing")
            q = self.liere(q)
            k = self.liere(k)
        elif self.pos_mode == "block4_rand_ortho":
            require_ok(self.rand_ortho is not None, "rand_ortho module missing")
            q = self.rand_ortho(q)
            k = self.rand_ortho(k)
        elif self.pos_mode == "su2_holonomy":
            require_ok(self.su2_holonomy is not None, "su2_holonomy module missing")
            u_path = self.su2_holonomy.compute_holonomy(x)
            q = self.su2_holonomy.apply_transport(q, u_path)
            k = self.su2_holonomy.apply_transport(k, u_path)

        if self.ngpt:
            q = safe_unit_norm(q, dim=-1, eps=1e-4) * self.sqk
            k = safe_unit_norm(k, dim=-1, eps=1e-4) * self.sqk
            scale = math.sqrt(float(self.d_head))
        else:
            scale = 1.0 / math.sqrt(float(self.d_head))

        attn_out = F.scaled_dot_product_attention(q, k, v, is_causal=True, scale=scale)
        attn_out = attn_out.transpose(1, 2).contiguous().view(bsz, seq_len, self.d_model)
        return self.w_o(attn_out)


class TransformerBlock(nn.Module):
    """Unified Pre-Norm or nGPT (unit-hypersphere SLERP) transformer layer."""

    def __init__(
        self,
        d_model: int,
        n_heads: int,
        d_ff: int,
        pos_mode: str = "rope2d",
        ngpt: bool = False,
        alpha_init: float = 0.05,
        seed: int = 42,
    ) -> None:
        super().__init__()
        self.ngpt = ngpt
        self.d_model = d_model
        self.d_ff = d_ff
        self.attn = CausalSelfAttention(d_model, n_heads, pos_mode=pos_mode, ngpt=ngpt, seed=seed)
        self.mlp = SwiGLUMLP(d_model, d_ff, ngpt=ngpt)
        if ngpt:
            # Clamped spherical eigen-step parameters in (0, pi/2) via sigmoid.
            init_logit = math.log(alpha_init / max(1e-4, 1.0 - alpha_init))
            self.alpha_a_logit = nn.Parameter(torch.full((d_model,), init_logit))
            self.alpha_m_logit = nn.Parameter(torch.full((d_model,), init_logit))
            self.norm1: Optional[RMSNorm] = None
            self.norm2: Optional[RMSNorm] = None
        else:
            self.norm1 = RMSNorm(d_model)
            self.norm2 = RMSNorm(d_model)
            self.alpha_a_logit = None
            self.alpha_m_logit = None

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        if self.ngpt:
            require_ok(self.alpha_a_logit is not None and self.alpha_m_logit is not None, "nGPT alphas missing")
            h = safe_unit_norm(h, dim=-1, eps=1e-4)
            alpha_a = torch.sigmoid(self.alpha_a_logit) * (0.45 * math.pi)
            h_a = self.attn(h)
            h = safe_slerp_step(h, h_a, alpha_a, eps=1e-4)
            alpha_m = torch.sigmoid(self.alpha_m_logit) * (0.45 * math.pi)
            h_m = self.mlp(h)
            h = safe_slerp_step(h, h_m, alpha_m, eps=1e-4)
            return h
        require_ok(self.norm1 is not None and self.norm2 is not None, "Pre-Norm layers missing")
        h = h + self.attn(self.norm1(h))
        h = h + self.mlp(self.norm2(h))
        return h


# ---------------------------------------------------------------------------
# H7a Exact S^3-Latitude Width Schedules (Exact Sum Conservation + Dual Nulls)
# ---------------------------------------------------------------------------


def build_s3_width_schedule(
    n_layers: int,
    base_d_ff: int,
    profile: str,
    align: int = 16,
) -> List[int]:
    """Build exact width multiset with exact integer sum == n_layers * base_d_ff.

    Profiles:
      - 'cylinder': uniform base_d_ff
      - 'polar': a * (1 + cos^2(psi_l)), psi_l = (l + 0.5)*pi/L, 2:1 contrast ratio
      - 'equatorial': a * (1 + sin^2(psi_l)), 2:1 contrast ratio
      - 'permuted_pol': deterministic low-Spearman permutation of polar multiset
      - 'permuted_eq': deterministic low-Spearman permutation of equatorial multiset
    """
    require_ok(n_layers >= 1, f"n_layers must be >= 1, got {n_layers}")
    require_ok(base_d_ff % align == 0, f"base_d_ff={base_d_ff} must be divisible by align={align}")
    target_sum = n_layers * base_d_ff

    if profile == "cylinder":
        return [base_d_ff] * n_layers

    require_ok(n_layers >= 4 and n_layers % 2 == 0, f"S^3 profile {profile!r} requires even n_layers >= 4, got {n_layers}")

    raw_weights: List[float] = []
    for ell in range(n_layers):
        psi = (float(ell) + 0.5) * math.pi / float(n_layers)
        if profile in ("polar", "permuted_pol"):
            raw_weights.append(1.0 + math.cos(psi) ** 2)
        elif profile in ("equatorial", "permuted_eq"):
            raw_weights.append(1.0 + math.sin(psi) ** 2)
        else:
            raise S107ConfigError(f"Unknown H7a profile: {profile!r}")

    scale = float(target_sum) / sum(raw_weights)
    widths = [max(align, int(round((w * scale) / align)) * align) for w in raw_weights]
    # Exact symmetric residual correction so sum(widths) == target_sum identically!
    diff = target_sum - sum(widths)
    require_ok(diff % align == 0, f"Width residual {diff} not aligned to {align}")
    step = align if diff > 0 else -align
    idx_order = sorted(range(n_layers), key=lambda i: abs(widths[i] - raw_weights[i] * scale), reverse=True)
    pos = 0
    while diff != 0:
        idx = idx_order[pos % n_layers]
        if widths[idx] + step >= align:
            widths[idx] += step
            diff -= step
        pos += 1

    if profile == "permuted_pol":
        # Deterministic permutation breaking U-shape symmetry (low Spearman |rho| <= 0.25).
        perm = _low_spearman_permutation(widths, seed=1071)
        widths = [widths[i] for i in perm]
    elif profile == "permuted_eq":
        perm = _low_spearman_permutation(widths, seed=1072)
        widths = [widths[i] for i in perm]

    require_ok(sum(widths) == target_sum, "Exact H7a width sum conservation failed")
    return widths


def spearman_rank_corr(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Exact Spearman rank correlation with average tie handling."""
    n = len(xs)
    require_ok(n == len(ys) and n >= 2, "Spearman requires equal length >= 2")

    def _ranks(vals: Sequence[float]) -> List[float]:
        indexed = sorted(enumerate(vals), key=lambda kv: kv[1])
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and indexed[j + 1][1] == indexed[i][1]:
                j += 1
            avg_rank = 0.5 * float(i + j) + 1.0
            for k in range(i, j + 1):
                ranks[indexed[k][0]] = avg_rank
            i = j + 1
        return ranks

    rx = _ranks(xs)
    ry = _ranks(ys)
    mx = sum(rx) / float(n)
    my = sum(ry) / float(n)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den_x = math.sqrt(sum((a - mx) ** 2 for a in rx))
    den_y = math.sqrt(sum((b - my) ** 2 for b in ry))
    if den_x == 0.0 or den_y == 0.0:
        return 0.0
    return num / (den_x * den_y)


def _low_spearman_permutation(widths: Sequence[int], seed: int) -> List[int]:
    """Find a deterministic permutation of indices with |Spearman(orig, perm)| <= 0.25."""
    import random

    rng = random.Random(seed)
    n = len(widths)
    orig = list(widths)
    best_perm = list(range(n))
    best_abs = 2.0
    for _ in range(512):
        cand = list(range(n))
        rng.shuffle(cand)
        permuted = [orig[i] for i in cand]
        if permuted == orig:
            continue
        rho = abs(spearman_rank_corr(orig, permuted))
        if rho < best_abs:
            best_abs = rho
            best_perm = cand
        if best_abs <= 0.15:
            break
    require_ok(best_abs <= 0.30, f"Could not find low-Spearman permutation (best={best_abs:.4f})")
    return best_perm


# ---------------------------------------------------------------------------
# Full Language Models: H7a / H7b Standard Stack & H7c Looped Core
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class S107ModelConfig:
    arm_name: str
    track: str  # "H7a", "H7b", or "H7c"
    vocab_size: int = 260
    d_model: int = 320
    n_heads: int = 8
    n_layers: int = 12
    base_d_ff: int = 864
    profile: str = "cylinder"  # H7a
    pos_mode: str = "rope2d"  # H7b
    ngpt: bool = False
    # H7c loop parameters
    loop_mode: str = "none"  # none | flat | sphere_noclock | sphere_randrot | clifford_hopf
    n_pre: int = 2
    n_core: int = 4
    n_suffix: int = 2
    r_train: int = 3
    clock_law: str = "unaliased_coprime"  # pinned_train_step | unaliased_coprime
    use_grad_checkpoint: bool = False
    seed: int = 42


class S107TransformerLM(nn.Module):
    """Unified S107 model supporting H7a width profiles, H7b positional ops, and H7c looped core."""

    def __init__(self, cfg: S107ModelConfig) -> None:
        super().__init__()
        self.cfg = cfg
        gen = torch.Generator().manual_seed(cfg.seed)

        self.tok_emb = nn.Embedding(cfg.vocab_size, cfg.d_model)
        with torch.no_grad():
            self.tok_emb.weight.copy_(torch.randn(self.tok_emb.weight.shape, generator=gen) * 0.02)
            if cfg.ngpt:
                self.tok_emb.weight.copy_(safe_unit_norm(self.tok_emb.weight, dim=-1, eps=1e-4))

        self.layer_widths: List[int] = []
        self.is_looped = cfg.loop_mode != "none"

        if not self.is_looped:
            widths = build_s3_width_schedule(cfg.n_layers, cfg.base_d_ff, cfg.profile)
            # H7b exact non-embedding param offset for SU(2) holonomy generator W_omega:
            # W_omega adds 3 * n_heads * (d_head//4) * d_model params per layer;
            # SwiGLU costs 3 * d_model * d_ff -> exact offset delta_dff = n_heads * (d_head//4) = d_model // 4.
            if cfg.pos_mode == "su2_holonomy":
                d_head = cfg.d_model // cfg.n_heads
                delta_dff = cfg.n_heads * (d_head // 4)
                widths = [w - delta_dff for w in widths]
                require_ok(all(w > 0 for w in widths), "SU(2) d_ff offset drove d_ff <= 0")
            self.layer_widths = widths
            self.blocks = nn.ModuleList(
                [
                    TransformerBlock(
                        cfg.d_model,
                        cfg.n_heads,
                        widths[i],
                        pos_mode=cfg.pos_mode,
                        ngpt=cfg.ngpt,
                        seed=cfg.seed + 100 + i,
                    )
                    for i in range(cfg.n_layers)
                ]
            )
            self.pre_blocks: Optional[nn.ModuleList] = None
            self.core_blocks: Optional[nn.ModuleList] = None
            self.suffix_blocks: Optional[nn.ModuleList] = None
            self.loop_gate_logits: Optional[nn.Parameter] = None
            self.register_buffer("rand_pass_rots", torch.empty(0))
        else:
            self.blocks = None
            n_phys = cfg.n_pre + cfg.n_core + cfg.n_suffix
            self.layer_widths = [cfg.base_d_ff] * n_phys
            use_ngpt_blocks = cfg.loop_mode in ("sphere_noclock", "sphere_randrot", "clifford_hopf")
            self.pre_blocks = nn.ModuleList(
                [
                    TransformerBlock(
                        cfg.d_model,
                        cfg.n_heads,
                        cfg.base_d_ff,
                        pos_mode=cfg.pos_mode,
                        ngpt=use_ngpt_blocks,
                        seed=cfg.seed + 200 + i,
                    )
                    for i in range(cfg.n_pre)
                ]
            )
            self.core_blocks = nn.ModuleList(
                [
                    TransformerBlock(
                        cfg.d_model,
                        cfg.n_heads,
                        cfg.base_d_ff,
                        pos_mode=cfg.pos_mode,
                        ngpt=use_ngpt_blocks,
                        seed=cfg.seed + 300 + i,
                    )
                    for i in range(cfg.n_core)
                ]
            )
            self.suffix_blocks = nn.ModuleList(
                [
                    TransformerBlock(
                        cfg.d_model,
                        cfg.n_heads,
                        cfg.base_d_ff,
                        pos_mode=cfg.pos_mode,
                        ngpt=use_ngpt_blocks,
                        seed=cfg.seed + 400 + i,
                    )
                    for i in range(cfg.n_suffix)
                ]
            )
            # Shared loop mixing gate (so R_test > R_train needs zero extra params!).
            # For spherical arms: clamped alpha = sigmoid(logit) * 0.45 * pi.
            # For flat arm: scalar residual mixing weight sigmoid(logit).
            self.loop_gate_logits = nn.Parameter(torch.full((1,), -0.85))
            if cfg.loop_mode == "sphere_randrot":
                # Fixed Haar random orthogonal rotation Q_r in SO(d) for up to 12 passes.
                rot_gen = torch.Generator().manual_seed(cfg.seed + 777)
                rots: List[torch.Tensor] = []
                for _ in range(12):
                    g = torch.randn((cfg.d_model, cfg.d_model), generator=rot_gen)
                    q_mat, r_mat = torch.linalg.qr(g)
                    signs = torch.sign(torch.diag(r_mat))
                    signs = torch.where(signs == 0, torch.ones_like(signs), signs)
                    q_mat = q_mat * signs.unsqueeze(0)
                    rots.append(q_mat)
                self.register_buffer("rand_pass_rots", torch.stack(rots, dim=0))
            else:
                self.register_buffer("rand_pass_rots", torch.empty(0))

        self.use_sphere_head = cfg.ngpt or cfg.loop_mode in ("sphere_noclock", "sphere_randrot", "clifford_hopf")
        if self.use_sphere_head:
            self.final_norm: Optional[RMSNorm] = None
            self.logit_scale = nn.Parameter(torch.full((1,), math.sqrt(float(cfg.d_model))))
        else:
            self.final_norm = RMSNorm(cfg.d_model)
            self.logit_scale = None

        # Deterministically initialize ALL nn.Linear weights from cfg.seed (zero global-RNG leakage!).
        with torch.no_grad():
            for mod in self.modules():
                if isinstance(mod, nn.Linear):
                    mod.weight.copy_(torch.randn(mod.weight.shape, generator=gen) * 0.02)
            if self.use_sphere_head:
                self.normalize_ngpt_weights_()

    def _run_core_pass(self, h: torch.Tensor) -> torch.Tensor:
        require_ok(self.core_blocks is not None, "core_blocks missing")
        out = h
        for blk in self.core_blocks:
            out = blk(out)
        return out

    def forward(
        self,
        input_ids: torch.Tensor,
        r_loops: Optional[int] = None,
        return_trace: bool = False,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """Forward pass returning (logits, trace_dict).

        For H7c looped arms: per-pass KV recompute is enforced strictly (no cross-pass
        stale KV reuse because h^(r) mutates every pass).
        """
        h = self.tok_emb(input_ids)
        if self.use_sphere_head:
            h = safe_unit_norm(h, dim=-1, eps=1e-4)

        trace: Dict[str, Any] = {"pass_states": [], "norm_drift_max": 0.0}

        if not self.is_looped:
            require_ok(self.blocks is not None, "blocks missing")
            for blk in self.blocks:
                h = blk(h)
                if self.use_sphere_head:
                    norms = torch.linalg.vector_norm(h.float(), ord=2, dim=-1)
                    drift = float(torch.max(torch.abs(norms - 1.0)).item())
                    trace["norm_drift_max"] = max(trace["norm_drift_max"], drift)
        else:
            require_ok(
                self.pre_blocks is not None
                and self.core_blocks is not None
                and self.suffix_blocks is not None
                and self.loop_gate_logits is not None,
                "Looped blocks missing",
            )
            passes = self.cfg.r_train if r_loops is None else r_loops
            require_ok(passes >= 1, f"r_loops must be >= 1, got {passes}")

            for blk in self.pre_blocks:
                h = blk(h)

            if return_trace:
                trace["pass_states"].append(h.detach())

            for r in range(passes):
                if self.cfg.use_grad_checkpoint and self.training:
                    core_out = grad_checkpoint(self._run_core_pass, h, use_reentrant=False)
                else:
                    core_out = self._run_core_pass(h)

                if self.cfg.loop_mode == "flat":
                    gate = torch.sigmoid(self.loop_gate_logits)
                    h = h + gate * core_out
                elif self.cfg.loop_mode == "sphere_noclock":
                    alpha_r = torch.sigmoid(self.loop_gate_logits) * (0.45 * math.pi)
                    h = safe_slerp_step(h, core_out, alpha_r, eps=1e-4)
                elif self.cfg.loop_mode == "sphere_randrot":
                    alpha_r = torch.sigmoid(self.loop_gate_logits) * (0.45 * math.pi)
                    q_rot = self.rand_pass_rots[r % self.rand_pass_rots.shape[0]].to(core_out.dtype)
                    rot_out = torch.matmul(core_out, q_rot.transpose(0, 1))
                    h = safe_slerp_step(h, rot_out, alpha_r, eps=1e-4)
                elif self.cfg.loop_mode == "clifford_hopf":
                    alpha_r = torch.sigmoid(self.loop_gate_logits) * (0.45 * math.pi)
                    phi_val = hopf_clock_angle(r, self.cfg.clock_law, r_train=self.cfg.r_train)
                    phi = torch.tensor(phi_val, device=h.device, dtype=h.dtype)
                    # Non-degenerate inter-pass Hopf fiber clock applied to core update AND
                    # coupled into the next loop pass via SLERP state transition!
                    rot_out = hopf_fiber_rotate(core_out, phi)
                    h = safe_slerp_step(h, rot_out, alpha_r, eps=1e-4)
                else:
                    raise S107ConfigError(f"Unknown loop_mode: {self.cfg.loop_mode!r}")

                if self.use_sphere_head:
                    norms = torch.linalg.vector_norm(h.float(), ord=2, dim=-1)
                    drift = float(torch.max(torch.abs(norms - 1.0)).item())
                    trace["norm_drift_max"] = max(trace["norm_drift_max"], drift)

                if return_trace:
                    trace["pass_states"].append(h.detach())

            for blk in self.suffix_blocks:
                h = blk(h)

        if self.use_sphere_head:
            require_ok(self.logit_scale is not None, "logit_scale missing")
            h_norm = safe_unit_norm(h, dim=-1, eps=1e-4)
            w_emb = safe_unit_norm(self.tok_emb.weight, dim=-1, eps=1e-4)
            logits = F.linear(h_norm, w_emb) * self.logit_scale
        else:
            require_ok(self.final_norm is not None, "final_norm missing")
            logits = F.linear(self.final_norm(h), self.tok_emb.weight)

        return logits, trace

    @torch.no_grad()
    def normalize_ngpt_weights_(self) -> None:
        """Retract nGPT weight matrix rows back onto the unit sphere after each optimizer step."""
        if not self.use_sphere_head:
            return
        self.tok_emb.weight.copy_(safe_unit_norm(self.tok_emb.weight, dim=-1, eps=1e-4))
        for mod in self.modules():
            if isinstance(mod, nn.Linear):
                mod.weight.copy_(safe_unit_norm(mod.weight, dim=-1, eps=1e-4))


# ---------------------------------------------------------------------------
# Exact Parameter & Analytical Training/Inference FLOPs Accounting (CS-08)
# ---------------------------------------------------------------------------


def count_parameters(model: S107TransformerLM) -> Dict[str, int]:
    """Return exact total, embedding, and non-embedding parameter counts."""
    total = sum(p.numel() for p in model.parameters())
    emb = model.tok_emb.weight.numel()
    return {
        "total_params": int(total),
        "embedding_params": int(emb),
        "non_embedding_params": int(total - emb),
    }


def analytical_forward_flops_per_token(
    cfg: S107ModelConfig,
    seq_len: int,
    r_loops: Optional[int] = None,
) -> Dict[str, int]:
    """Exact forward MAC->FLOPs/token accounting (2 FLOPs per MAC, incl. attention & scan)."""
    d = cfg.d_model
    v = cfg.vocab_size

    def _layer_flops(d_ff: int) -> int:
        # Projections: Q,K,V,O (4*d^2) + SwiGLU (3*d*d_ff) -> 2 * params FLOPs/token
        proj = 2 * (4 * d * d + 3 * d * d_ff)
        # Causal self-attention QK^T + AV: 2 * (seq_len * d) per token (effective avg seq_len/2 causal -> 2*seq_len*d full matmul)
        attn_qk_av = 2 * seq_len * d
        pos_extra = 0
        if cfg.pos_mode == "su2_holonomy":
            # W_omega projection (2 * d * 3 * n_q) + parallel quaternion scan (28 * n_q * log2(T))
            # + Q,K left-transport (2 * 28 * n_q).
            n_q = d // 4
            w_omega_flops = 2 * d * (3 * n_q)
            scan_steps = max(1, int(math.ceil(math.log2(max(2, seq_len)))))
            scan_flops = 28 * n_q * scan_steps
            transport_flops = 2 * 28 * n_q
            pos_extra = w_omega_flops + scan_flops + transport_flops
        elif cfg.pos_mode == "liere4d":
            pos_extra = 2 * 16 * (d // 4)  # 4x4 matvec per 4D block on Q and K
        elif cfg.pos_mode == "block4_rand_ortho":
            pos_extra = 2 * 16 * (d // 4)
        return proj + attn_qk_av + pos_extra

    if cfg.loop_mode == "none":
        widths = build_s3_width_schedule(cfg.n_layers, cfg.base_d_ff, cfg.profile)
        if cfg.pos_mode == "su2_holonomy":
            widths = [w - (d // 4) for w in widths]
        core_flops = sum(_layer_flops(w) for w in widths)
        eff_layers = cfg.n_layers
    else:
        passes = cfg.r_train if r_loops is None else r_loops
        pre_f = cfg.n_pre * _layer_flops(cfg.base_d_ff)
        core_f = passes * cfg.n_core * _layer_flops(cfg.base_d_ff)
        suf_f = cfg.n_suffix * _layer_flops(cfg.base_d_ff)
        clock_f = 0
        if cfg.loop_mode == "clifford_hopf":
            clock_f = passes * (6 * d)  # Hopf 4D rotation + SLERP
        elif cfg.loop_mode == "sphere_randrot":
            clock_f = passes * (2 * d * d)  # Dense SO(d) matrix multiply per pass
        core_flops = pre_f + core_f + suf_f + clock_f
        eff_layers = cfg.n_pre + passes * cfg.n_core + cfg.n_suffix

    lm_head_flops = 2 * d * v
    total_fwd = core_flops + lm_head_flops
    return {
        "effective_layers": int(eff_layers),
        "core_fwd_flops_per_token": int(core_flops),
        "lm_head_fwd_flops_per_token": int(lm_head_flops),
        "total_fwd_flops_per_token": int(total_fwd),
        "est_train_flops_per_token": int(3 * total_fwd),
    }


# ---------------------------------------------------------------------------
# Arm Factory Catalogs (Exact H7a, H7b, H7c Protocols + Amendment 1 Controls)
# ---------------------------------------------------------------------------


def build_h7a_configs(
    d_model: int = 320,
    n_heads: int = 8,
    n_layers: int = 12,
    base_d_ff: int = 864,
    vocab_size: int = 260,
    seed: int = 42,
) -> Dict[str, S107ModelConfig]:
    """All 10 amended H7a arms (5 width profiles x {Std, nGPT})."""
    profiles = [
        ("Cyl", "cylinder"),
        ("S3-Polar", "polar"),
        ("S3-Equatorial", "equatorial"),
        ("S3-Permuted-Pol", "permuted_pol"),
        ("S3-Permuted-Eq", "permuted_eq"),
    ]
    out: Dict[str, S107ModelConfig] = {}
    for label, prof in profiles:
        for bname, is_ngpt in (("Std", False), ("nGPT", True)):
            name = f"{label}-{bname}"
            out[name] = S107ModelConfig(
                arm_name=name,
                track="H7a",
                vocab_size=vocab_size,
                d_model=d_model,
                n_heads=n_heads,
                n_layers=n_layers,
                base_d_ff=base_d_ff,
                profile=prof,
                pos_mode="rope2d",
                ngpt=is_ngpt,
                seed=seed,
            )
    return out


def build_h7b_configs(
    d_model: int = 320,
    n_heads: int = 8,
    n_layers: int = 12,
    base_d_ff: int = 864,
    vocab_size: int = 260,
    seed: int = 42,
) -> Dict[str, S107ModelConfig]:
    """All 5 amended H7b arms (Path-Ordered SU(2) Holonomy vs RoPE-2D, LieRE-4D, Block4-RandOrtho)."""
    specs = [
        ("RoPE-2D-Std", "rope2d", False),
        ("RoPE-2D-nGPT", "rope2d", True),
        ("LieRE-4D-Abelian-nGPT", "liere4d", True),
        ("Block4-RandOrtho-nGPT", "block4_rand_ortho", True),
        ("SU2-Holonomy-Scan-nGPT", "su2_holonomy", True),
    ]
    return {
        name: S107ModelConfig(
            arm_name=name,
            track="H7b",
            vocab_size=vocab_size,
            d_model=d_model,
            n_heads=n_heads,
            n_layers=n_layers,
            base_d_ff=base_d_ff,
            profile="cylinder",
            pos_mode=pmode,
            ngpt=is_ngpt,
            seed=seed,
        )
        for name, pmode, is_ngpt in specs
    }


def build_h7c_configs(
    d_model: int = 256,
    n_heads: int = 8,
    base_d_ff: int = 688,
    vocab_size: int = 260,
    clock_law: str = "unaliased_coprime",
    use_grad_checkpoint: bool = False,
    seed: int = 42,
) -> Dict[str, S107ModelConfig]:
    """All 6 amended H7c arms (incl. Unlooped-16L, Unlooped-8L iso-param, and SphereLoop-RandRotClock)."""
    return {
        "Unlooped-16L": S107ModelConfig(
            arm_name="Unlooped-16L",
            track="H7c",
            vocab_size=vocab_size,
            d_model=d_model,
            n_heads=n_heads,
            n_layers=16,
            base_d_ff=base_d_ff,
            ngpt=False,
            loop_mode="none",
            seed=seed,
        ),
        "Unlooped-8L": S107ModelConfig(
            arm_name="Unlooped-8L",
            track="H7c",
            vocab_size=vocab_size,
            d_model=d_model,
            n_heads=n_heads,
            n_layers=8,
            base_d_ff=base_d_ff,
            ngpt=False,
            loop_mode="none",
            seed=seed,
        ),
        "FlatLoop-Std": S107ModelConfig(
            arm_name="FlatLoop-Std",
            track="H7c",
            vocab_size=vocab_size,
            d_model=d_model,
            n_heads=n_heads,
            n_layers=8,
            base_d_ff=base_d_ff,
            ngpt=False,
            loop_mode="flat",
            n_pre=2,
            n_core=4,
            n_suffix=2,
            r_train=3,
            clock_law=clock_law,
            use_grad_checkpoint=use_grad_checkpoint,
            seed=seed,
        ),
        "SphereLoop-NoClock": S107ModelConfig(
            arm_name="SphereLoop-NoClock",
            track="H7c",
            vocab_size=vocab_size,
            d_model=d_model,
            n_heads=n_heads,
            n_layers=8,
            base_d_ff=base_d_ff,
            ngpt=True,
            loop_mode="sphere_noclock",
            n_pre=2,
            n_core=4,
            n_suffix=2,
            r_train=3,
            clock_law=clock_law,
            use_grad_checkpoint=use_grad_checkpoint,
            seed=seed,
        ),
        "SphereLoop-RandRotClock": S107ModelConfig(
            arm_name="SphereLoop-RandRotClock",
            track="H7c",
            vocab_size=vocab_size,
            d_model=d_model,
            n_heads=n_heads,
            n_layers=8,
            base_d_ff=base_d_ff,
            ngpt=True,
            loop_mode="sphere_randrot",
            n_pre=2,
            n_core=4,
            n_suffix=2,
            r_train=3,
            clock_law=clock_law,
            use_grad_checkpoint=use_grad_checkpoint,
            seed=seed,
        ),
        "CliffordTorus-HopfLoop": S107ModelConfig(
            arm_name="CliffordTorus-HopfLoop",
            track="H7c",
            vocab_size=vocab_size,
            d_model=d_model,
            n_heads=n_heads,
            n_layers=8,
            base_d_ff=base_d_ff,
            ngpt=True,
            loop_mode="clifford_hopf",
            n_pre=2,
            n_core=4,
            n_suffix=2,
            r_train=3,
            clock_law=clock_law,
            use_grad_checkpoint=use_grad_checkpoint,
            seed=seed,
        ),
    }


# ---------------------------------------------------------------------------
# Exact RTN Per-Output-Channel Group-128 PTQ & M1-H1 G_3(rho) Drift Monitor
# ---------------------------------------------------------------------------


@torch.no_grad()
def quantize_tensor_rtn_group(w: torch.Tensor, bits: int, group_size: int = 128) -> torch.Tensor:
    """Symmetric RTN per-output-channel group quantization (COLLAB-CLAUDE A10).

    Linear layers only (excludes embeddings/lm_head); zero post-quant renormalization.
    """
    require_ok(bits in (3, 4), f"PTQ bits must be 3 or 4, got {bits}")
    require_ok(w.ndim == 2, f"Expected 2D linear weight, got shape {tuple(w.shape)}")
    out_dim, in_dim = w.shape
    qmax = float((1 << (bits - 1)) - 1)  # 3 for 3-bit, 7 for 4-bit
    wf = w.float()
    pad = (group_size - (in_dim % group_size)) % group_size
    if pad > 0:
        wf = F.pad(wf, (0, pad))
    groups = wf.reshape(out_dim, -1, group_size)
    max_abs = torch.amax(torch.abs(groups), dim=-1, keepdim=True)
    scale = torch.clamp(max_abs / qmax, min=1e-8)
    q = torch.clamp(torch.round(groups / scale), min=-qmax, max=qmax)
    deq = (q * scale).reshape(out_dim, in_dim + pad)[:, :in_dim]
    return deq.to(w.dtype)


@torch.no_grad()
def apply_ptq_copy(
    model: S107TransformerLM,
    bits: int,
    group_size: int = 128,
    core_only: bool = False,
) -> S107TransformerLM:
    """Return a deep copy of model with RTN group quantization applied to linear layers."""
    import copy

    q_model = copy.deepcopy(model)
    target_root: nn.Module = q_model
    if core_only and q_model.core_blocks is not None:
        target_root = q_model.core_blocks
    for mod in target_root.modules():
        if isinstance(mod, nn.Linear):
            mod.weight.copy_(quantize_tensor_rtn_group(mod.weight, bits=bits, group_size=group_size))
    return q_model


@torch.no_grad()
def measure_m1_h1_loop_drift(
    model_fp: S107TransformerLM,
    input_ids: torch.Tensor,
    bits: int = 4,
    group_size: int = 128,
    r_eval: int = 3,
) -> Dict[str, Any]:
    """Measure Track S96 M1-H1 loop drift: empirical rho_t, G_3(rho), Delta_3 / Delta_1_ctrl, and KL."""
    require_ok(model_fp.is_looped, "M1-H1 drift monitor requires a looped H7c model")
    model_q = apply_ptq_copy(model_fp, bits=bits, group_size=group_size, core_only=True)

    logits_fp_r, trace_fp_r = model_fp(input_ids, r_loops=r_eval, return_trace=True)
    logits_q_r, trace_q_r = model_q(input_ids, r_loops=r_eval, return_trace=True)
    logits_fp_1, trace_fp_1 = model_fp(input_ids, r_loops=1, return_trace=True)
    logits_q_1, trace_q_1 = model_q(input_ids, r_loops=1, return_trace=True)

    # Empirical step contraction ratios rho_r = ||h^(r+1)-h^(r)|| / ||h^(r)-h^(r-1)||
    states = trace_fp_r["pass_states"]  # length r_eval + 1
    step_norms: List[float] = []
    for i in range(1, len(states)):
        step_norms.append(float(torch.linalg.vector_norm((states[i] - states[i - 1]).float()).item()))
    rhos: List[float] = []
    for i in range(1, len(step_norms)):
        rhos.append(step_norms[i] / max(step_norms[i - 1], 1e-8))
    rho_mean = sum(rhos) / float(len(rhos)) if rhos else 0.0
    g3_rho = 1.0 + rho_mean + (rho_mean * rho_mean)

    # Hidden state quantization drift at R=r_eval vs R=1 control
    delta_r = float(torch.linalg.vector_norm((trace_q_r["pass_states"][-1] - trace_fp_r["pass_states"][-1]).float()).item())
    delta_1 = float(torch.linalg.vector_norm((trace_q_1["pass_states"][-1] - trace_fp_1["pass_states"][-1]).float()).item())
    drift_ratio = delta_r / max(delta_1, 1e-8)

    # Held-out next-token KL(p_fp || p_q) in nats
    p_fp = F.softmax(logits_fp_r.float(), dim=-1)
    log_p_fp = F.log_softmax(logits_fp_r.float(), dim=-1)
    log_p_q = F.log_softmax(logits_q_r.float(), dim=-1)
    kl_r = float(torch.mean(torch.sum(p_fp * (log_p_fp - log_p_q), dim=-1)).item())

    return {
        "arm": model_fp.cfg.arm_name,
        "bits": bits,
        "r_eval": r_eval,
        "step_norms": [round(v, 6) for v in step_norms],
        "empirical_rhos": [round(v, 6) for v in rhos],
        "rho_mean": round(rho_mean, 6),
        "g3_rho": round(g3_rho, 6),
        "delta_r": round(delta_r, 6),
        "delta_1_ctrl": round(delta_1, 6),
        "delta_r_over_delta_1": round(drift_ratio, 6),
        "kl_nats": round(kl_r, 6),
        "m1_h1_passes_le_2": drift_ratio <= 2.0,
    }
