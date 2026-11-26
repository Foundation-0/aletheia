#!/usr/bin/env python3
"""PREREG-S110 + Amendment 1 ("Geosphere-Net"): Pruned 4-Operator Architecture & Portal-3 Beltrami Diagnostics.

Implements strictly the 4 sm_86-viable surviving operators mandated by
PREREG_S110_AMENDMENT1_COUNCIL_PRUNING.md (a41399fd...):
  1. 2x2 block-diagonal closed-form Cayley SO(k) feature rotation (4 FMAs/pair, zero LU).
  2. SO(k)-equivariant vector-proximal Poloidal Bingham S_Y^H(u) (no post-renorm, exact Stagnant-Lid).
  3. Diagonal multi-timescale Darcy EMA (exact zero-wraparound cuFFT causal convolution, 0 < alpha < 1).
  4. Integer ACT geothermal loop plumes (r in {1..4}, strict mean r_bar = 2.0) + Fast Surface Draft (MTP-8).

Plus:
  - Portal-3 Beltrami [C, K] = 0 helicity-conservation & symmetric-collapse (O3.5) diagnostic.
  - Baseline Track S50 Channel-2B airlock + outer DPI norm clamp (folded into baseline harness).
  - Pre-normalization (pre-N) counterfactual h^(r) state-patching hook.
  - Fail-closed rejection of pruned Amendment-1 mechanisms (causal Sinkhorn, dense Cayley LU,
    Telluric direct Core<->Surface skip, and coordinate-wise Bingham post-renorm).

Zero bare asserts; all randomness explicitly seeded; WEIGHTS=0 compliant.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint as _grad_checkpoint

PREREG_S110_SHA256 = "2e645597e81a330159b2183caf670f685821a9451a37223a782936e88e30d0fe"
PREREG_S110_AMEND1_SHA256 = "a41399fdb888167288a63cefa540778d921574197f721b8d5322bd8825d0928a"

VOCAB_SIZE_BYTE = 260
BOS_ID = 256
EOS_ID = 257
PAD_ID = 258
UNK_ID = 259


class S110ConfigError(ValueError):
    """Typed fail-closed configuration or invariant violation error."""


def require_ok(cond: bool, msg: str) -> None:
    if not cond:
        raise S110ConfigError(msg)


def _make_gen(seed: int) -> torch.Generator:
    g = torch.Generator(device="cpu")
    g.manual_seed(int(seed) & 0x7FFFFFFF)
    return g


def _init_linear(layer: nn.Linear, std: float, seed: int) -> None:
    g = _make_gen(seed)
    with torch.no_grad():
        layer.weight.normal_(0.0, std, generator=g)
        if layer.bias is not None:
            layer.bias.zero_()


def _l2_normalize_safe(x: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    norm = torch.sqrt((x * x).sum(dim=-1, keepdim=True) + eps * eps)
    return x / norm


# ---------------------------------------------------------------------------
# Operator 1: 2x2 Block-Diagonal Closed-Form Cayley SO(k) Feature Rotation
# ---------------------------------------------------------------------------


class CayleyBlock2x2SO(nn.Module):
    """Closed-form 2x2 block-diagonal Cayley SO(d) rotation (4 FMAs/pair, zero LU).

    For each pair (x_{2j}, x_{2j+1}) and skew parameter omega_j:
      c_j = (1 - w_j^2) / (1 + w_j^2),  s_j = 2 w_j / (1 + w_j^2)
      y_{2j}   =  c_j * x_{2j} + s_j * x_{2j+1}
      y_{2j+1} = -s_j * x_{2j} + c_j * x_{2j+1}
    Exact orthogonality Q^T Q = I_d, det(Q) = +1, <h, Omega h> = 0, ||Q h||_2 = ||h||_2.
    """

    def __init__(
        self,
        d_model: int,
        bottleneck_rank: int = 16,
        data_dependent: bool = True,
        seed: int = 42,
    ) -> None:
        super().__init__()
        require_ok(d_model > 0 and d_model % 2 == 0, "d_model must be positive even for 2x2 Cayley blocks")
        self.d_model = d_model
        self.n_pairs = d_model // 2
        self.data_dependent = bool(data_dependent)
        self.bottleneck_rank = int(bottleneck_rank) if data_dependent else 0

        g = _make_gen(seed)
        with torch.no_grad():
            init_omega = torch.empty(self.n_pairs).uniform_(-0.35, 0.35, generator=g)
        self.base_omega = nn.Parameter(init_omega)
        if self.data_dependent:
            require_ok(self.bottleneck_rank > 0, "bottleneck_rank must be positive when data_dependent=True")
            self.w_down = nn.Linear(d_model, self.bottleneck_rank, bias=False)
            self.w_up = nn.Linear(self.bottleneck_rank, self.n_pairs, bias=False)
            _init_linear(self.w_down, 1.0 / math.sqrt(float(d_model)), seed + 1)
            _init_linear(self.w_up, 0.05 / math.sqrt(float(self.bottleneck_rank)), seed + 2)
        else:
            self.w_down = None
            self.w_up = None

    def compute_omega(self, x: Optional[torch.Tensor] = None) -> torch.Tensor:
        if not self.data_dependent or x is None or self.w_down is None or self.w_up is None:
            return self.base_omega
        # Bounded skew generator so 1 + omega^2 stays well-conditioned in BF16 and FP32.
        delta = 0.75 * torch.tanh(self.w_up(F.silu(self.w_down(x))))
        return self.base_omega.view(*([1] * (x.ndim - 1)), self.n_pairs) + delta

    @staticmethod
    def apply_cayley_2x2(x: torch.Tensor, omega: torch.Tensor) -> torch.Tensor:
        orig_dtype = x.dtype
        xf = x.float().reshape(*x.shape[:-1], -1, 2)
        wf = omega.float()
        w2 = wf * wf
        inv_denom = 1.0 / (1.0 + w2)
        c = (1.0 - w2) * inv_denom
        s = (2.0 * wf) * inv_denom
        x_even, x_odd = xf.unbind(-1)
        # Exactly 4 FMAs per 2D pair.
        y_even = c * x_even + s * x_odd
        y_odd = -s * x_even + c * x_odd
        out = torch.stack((y_even, y_odd), dim=-1).reshape_as(x)
        return out.to(orig_dtype)

    @staticmethod
    def apply_skew_omega(x: torch.Tensor, omega: torch.Tensor) -> torch.Tensor:
        """Apply exact skew generator Omega (Omega^T = -Omega) for workless <h, Omega h> = 0 checks."""
        xf = x.float()
        wf = omega.float()
        x_even = xf[..., 0::2]
        x_odd = xf[..., 1::2]
        # (Omega x)_{2j} = -w_j x_{2j+1}, (Omega x)_{2j+1} = +w_j x_{2j}
        y_even = -wf * x_odd
        y_odd = wf * x_even
        return torch.stack((y_even, y_odd), dim=-1).reshape_as(xf).to(x.dtype)

    def explicit_matrix(self, omega: Optional[torch.Tensor] = None) -> torch.Tensor:
        """Materialize exact d x d block-diagonal Q in float64/float32 for algebraic diagnostics."""
        w = (self.base_omega if omega is None else omega).detach().float().reshape(self.n_pairs)
        w2 = w * w
        inv_d = 1.0 / (1.0 + w2)
        c = (1.0 - w2) * inv_d
        s = (2.0 * w) * inv_d
        q = torch.zeros((self.d_model, self.d_model), dtype=torch.float32, device=w.device)
        idx = torch.arange(self.n_pairs, device=w.device)
        q[2 * idx, 2 * idx] = c
        q[2 * idx, 2 * idx + 1] = s
        q[2 * idx + 1, 2 * idx] = -s
        q[2 * idx + 1, 2 * idx + 1] = c
        return q

    def explicit_skew_matrix(self, omega: Optional[torch.Tensor] = None) -> torch.Tensor:
        """Materialize exact d x d skew generator K (K^T = -K) matching Q = (I - K)(I + K)^{-1}."""
        w = (self.base_omega if omega is None else omega).detach().float().reshape(self.n_pairs)
        k = torch.zeros((self.d_model, self.d_model), dtype=torch.float32, device=w.device)
        idx = torch.arange(self.n_pairs, device=w.device)
        k[2 * idx, 2 * idx + 1] = -w
        k[2 * idx + 1, 2 * idx] = w
        return k

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        omega = self.compute_omega(x)
        return self.apply_cayley_2x2(x, omega)


# ---------------------------------------------------------------------------
# Operator 2: SO(k)-Equivariant Vector-Proximal Poloidal Bingham S_Y^H(u)
# ---------------------------------------------------------------------------


class VectorProximalPoloidalBingham(nn.Module):
    """Repaired SO(k)-equivariant vector-proximal Poloidal Bingham operator (Amendment 1, Discovery 3).

    Splits u = (u_pol, u_tor) with exact Hodge orthogonality <u_pol, u_tor> = 0 in R^d:
      S_Y^H(u) = max(0, 1 - tau_Y / ||u_pol||_2) * u_pol  (+)  u_tor   (NO post-renorm!)

    Guarantees:
      - Exact SO(k) equivariance on the Poloidal k-subspace.
      - Exact Poloidal/Toroidal orthogonality preservation.
      - Exact Stagnant-Lid zeroing (u_pol -> 0 identically when ||u_pol||_2 <= tau_Y).
      - Zero NaN/Inf gradients at ||u_pol||_2 == 0 and on the yield wall ||u_pol||_2 == tau_Y.
      - Frozen Stage-1 quantile threshold tau_Y (zero undefined sigma_u).
    """

    def __init__(
        self,
        d_model: int,
        k_poloidal: Optional[int] = None,
        tau_y: float = 0.0,
        yield_number: float = 0.5,
        post_renorm: bool = False,
    ) -> None:
        super().__init__()
        require_ok(not post_renorm, "PRUNED by Amendment 1 Discovery 3: Bingham post-renorm breaks SO(k) equivariance")
        k_pol = (d_model // 2) if k_poloidal is None else int(k_poloidal)
        require_ok(0 < k_pol < d_model, f"k_poloidal must satisfy 0 < k < d_model (got {k_pol}, {d_model})")
        require_ok(tau_y >= 0.0, f"tau_y must be non-negative (got {tau_y})")
        require_ok(0.0 <= yield_number <= 1.0, f"yield_number must be in [0, 1] (got {yield_number})")
        self.d_model = d_model
        self.k_poloidal = k_pol
        self.yield_number = float(yield_number)
        self.register_buffer("tau_y", torch.tensor(float(tau_y), dtype=torch.float32))

    @torch.no_grad()
    def calibrate_from_activations(
        self,
        u_samples: torch.Tensor,
        yield_number: Optional[float] = None,
    ) -> Dict[str, float]:
        """Freeze tau_Y from Stage-1 empirical quantile of ||u_pol||_2 (Y in {0, 0.25, 0.50, 0.75, 1.0})."""
        y_val = self.yield_number if yield_number is None else float(yield_number)
        require_ok(0.0 <= y_val <= 1.0, f"yield_number must be in [0, 1] (got {y_val})")
        u_pol = u_samples[..., : self.k_poloidal].float()
        norms = torch.linalg.vector_norm(u_pol, ord=2, dim=-1).reshape(-1)
        require_ok(norms.numel() > 0, "Calibration activation tensor must be non-empty")
        if y_val <= 0.0:
            tau = 0.0
        elif y_val >= 1.0:
            tau = float(norms.max().item()) * (1.0 + 1e-5) + 1e-6
        else:
            tau = float(torch.quantile(norms, y_val).item())
        self.yield_number = y_val
        self.tau_y.fill_(tau)
        plug_frac = float((norms <= tau).float().mean().item())
        return {
            "yield_number": y_val,
            "tau_y": tau,
            "norm_min": float(norms.min().item()),
            "norm_median": float(torch.quantile(norms, 0.5).item()),
            "norm_max": float(norms.max().item()),
            "plug_fraction": plug_frac,
        }

    def forward(self, u: torch.Tensor, tau_override: Optional[float] = None) -> Tuple[torch.Tensor, Dict[str, float]]:
        orig_dtype = u.dtype
        uf = u.float()
        u_pol = uf[..., : self.k_poloidal]
        u_tor = uf[..., self.k_poloidal :]
        tau_val = float(self.tau_y.item()) if tau_override is None else float(tau_override)
        require_ok(tau_val >= 0.0, f"tau_override must be non-negative (got {tau_val})")

        if tau_val <= 0.0:
            out_pol = u_pol
            plug_frac = 0.0
        else:
            norm_sq = (u_pol * u_pol).sum(dim=-1, keepdim=True)
            tau_sq = tau_val * tau_val
            active = norm_sq > tau_sq
            # Safe denominator branch guarantees zero 0/0 NaN in both forward & backward at u_pol == 0.
            safe_norm = torch.sqrt(torch.where(active, norm_sq, torch.ones_like(norm_sq)))
            scale = torch.where(active, (1.0 - tau_val / safe_norm).clamp_min(0.0), torch.zeros_like(norm_sq))
            out_pol = scale * u_pol
            with torch.no_grad():
                plug_frac = float((~active).float().mean().item())

        out = torch.cat((out_pol, u_tor), dim=-1).to(orig_dtype)
        return out, {"plug_fraction": plug_frac, "tau_y": tau_val}


# ---------------------------------------------------------------------------
# Operator 3: Diagonal Multi-Timescale Darcy EMA (Exact Parallel Scan)
# ---------------------------------------------------------------------------


class DiagonalDarcyEMA(nn.Module):
    """Diagonal multi-timescale porous-diffusion EMA (Amendment 1, Discovery 4).

    Drops dense K_porous; computes exact contractive recurrence:
      s_t = (1 - alpha) * s_{t-1} + alpha * x_t,   0 < alpha_j < 1
    via exact zero-wraparound cuFFT causal linear convolution (replacing initial Hillis-Steele eager scan).
    """

    def __init__(
        self,
        d_model: int,
        tau_min: float = 2.0,
        tau_max: float = 128.0,
        alpha_eps: float = 1e-4,
        seed: int = 42,
    ) -> None:
        super().__init__()
        require_ok(d_model > 0, "d_model must be positive")
        require_ok(1.0 < tau_min < tau_max, "Require 1.0 < tau_min < tau_max")
        require_ok(0.0 < alpha_eps < 0.05, "alpha_eps must be in (0, 0.05)")
        self.d_model = d_model
        self.alpha_eps = float(alpha_eps)

        # Log-spaced multi-timescale initialization across channels.
        taus = torch.exp(torch.linspace(math.log(tau_min), math.log(tau_max), d_model))
        init_alpha = (1.0 / taus).clamp(alpha_eps * 2.0, 1.0 - alpha_eps * 2.0)
        scaled = (init_alpha - alpha_eps) / (1.0 - 2.0 * alpha_eps)
        init_logits = torch.log(scaled / (1.0 - scaled))
        self.alpha_logits = nn.Parameter(init_logits)
        # Residual mix gate initialized small so Darcy memory injects smoothly without destabilizing early training.
        g = _make_gen(seed)
        with torch.no_grad():
            mix_init = torch.empty(d_model).uniform_(0.08, 0.16, generator=g)
        self.mix_gate = nn.Parameter(mix_init)

    def alpha(self) -> torch.Tensor:
        return self.alpha_eps + (1.0 - 2.0 * self.alpha_eps) * torch.sigmoid(self.alpha_logits.float())

    @staticmethod
    def parallel_ema_scan(x: torch.Tensor, alpha: torch.Tensor) -> torch.Tensor:
        """Exact causal linear convolution via cuFFT (rfft/irfft, zero wraparound) for s_t = (1-a)s_{t-1} + a x_t."""
        # x: [B, T, D], alpha: [D] in (0, 1)
        _, seq_len, _ = x.shape
        xf = x.float().transpose(1, 2)  # [B, D, T]
        af = alpha.float()
        t_idx = torch.arange(seq_len, device=x.device, dtype=torch.float32)
        log_lam = torch.log1p(-af)
        kernel = af.unsqueeze(-1) * torch.exp(log_lam.unsqueeze(-1) * t_idx.unsqueeze(0))  # [D, T]
        n_fft = 1 << max(1, (2 * seq_len - 1).bit_length())
        x_f = torch.fft.rfft(xf, n=n_fft, dim=-1)
        k_f = torch.fft.rfft(kernel, n=n_fft, dim=-1).unsqueeze(0)
        y = torch.fft.irfft(x_f * k_f, n=n_fft, dim=-1)[..., :seq_len]
        return y.transpose(1, 2).contiguous().to(x.dtype)

    @staticmethod
    def sequential_ema_reference(x: torch.Tensor, alpha: torch.Tensor) -> torch.Tensor:
        """Sequential reference implementation for CPU pre-flight exactness verification."""
        b_sz, seq_len, d_dim = x.shape
        xf = x.float()
        af = alpha.float().view(1, d_dim)
        lam = 1.0 - af
        s = torch.zeros((b_sz, d_dim), dtype=torch.float32, device=x.device)
        outs: List[torch.Tensor] = []
        for t in range(seq_len):
            s = lam * s + af * xf[:, t, :]
            outs.append(s)
        return torch.stack(outs, dim=1).to(x.dtype)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        s = self.parallel_ema_scan(x, self.alpha())
        gate = torch.tanh(self.mix_gate.float()).view(1, 1, self.d_model)
        return (x.float() + gate * (s.float() - x.float())).to(x.dtype)


# ---------------------------------------------------------------------------
# Operator 4: Integer ACT Geothermal Loop Plumes (r_bar = 2.0) + MTP-8 Draft
# ---------------------------------------------------------------------------


class GeothermalACTController(nn.Module):
    """Integer ACT loop controller enforcing strict mean budget r_bar = 2.0 (r in {1, 2, 3, 4}).

    Assigns exact discrete integer loop counts r*(b, t) in {1, 2, 3, 4} via rank-quota allocation
    driven by buoyancy surprise (||delta h|| + learned halt score), using Straight-Through Estimator
    (STE) weights during training plus quadratic ponder-cost regularization toward target_mean_r.
    """

    def __init__(
        self,
        d_model: int,
        r_max: int = 4,
        target_mean_r: float = 2.0,
        seed: int = 42,
    ) -> None:
        super().__init__()
        require_ok(r_max == 4, "Locked PREREG-S110 ACT range is r in {1..4}")
        require_ok(1.0 <= target_mean_r <= float(r_max), "target_mean_r must be inside [1, r_max]")
        self.d_model = d_model
        self.r_max = r_max
        self.target_mean_r = float(target_mean_r)
        self.score_proj = nn.Linear(d_model, 1, bias=True)
        _init_linear(self.score_proj, 1.0 / math.sqrt(float(d_model)), seed)
        self.surprise_scale = nn.Parameter(torch.tensor(0.5, dtype=torch.float32))

    def compute_buoyancy_score(self, h_prev: torch.Tensor, h_curr: torch.Tensor) -> torch.Tensor:
        """Higher score -> higher residual surprise -> deeper geothermal plume (more loops)."""
        delta_rms = torch.sqrt(((h_curr.float() - h_prev.float()) ** 2).mean(dim=-1) + 1e-8)
        learned = self.score_proj(h_curr).squeeze(-1).float()
        return learned + self.surprise_scale.float() * delta_rms

    @staticmethod
    def allocate_integer_loops(buoyancy: torch.Tensor) -> torch.Tensor:
        """Exact rank-quota integer allocation in {1, 2, 3, 4} with exact mean r_bar = 2.0.

        Distribution (when N >= 8):
          bottom 37.5% -> r = 1
          next   37.5% -> r = 2
          next   12.5% -> r = 3
          top    12.5% -> r = 4
        Mean = 0.375*1 + 0.375*2 + 0.125*3 + 0.125*4 = 2.000 exactly!
        """
        flat = buoyancy.detach().float().reshape(-1)
        n = flat.numel()
        if n < 4:
            return torch.full_like(buoyancy, 2, dtype=torch.long)
        order = torch.argsort(flat, stable=True)
        counts = torch.full((n,), 2, dtype=torch.long, device=buoyancy.device)
        # Exact balanced pairs around r=2:
        # Each (r=4) pairs with two (r=1) to keep sum = 4 + 1 + 1 = 6 = 3 * 2 (mean 2.0 exact!)
        # Each (r=3) pairs with one (r=1) to keep sum = 3 + 1 = 4 = 2 * 2 (mean 2.0 exact!)
        n4 = n // 8
        n3 = n // 8
        n1 = 2 * n4 + n3
        if n1 > 0:
            counts[order[:n1]] = 1
        if n3 > 0:
            counts[order[n - n4 - n3 : n - n4]] = 3
        if n4 > 0:
            counts[order[n - n4 :]] = 4
        return counts.view_as(buoyancy)

    def select_loop_states(
        self,
        pass_states: Sequence[torch.Tensor],
        buoyancy_r1: torch.Tensor,
        ste: bool = True,
    ) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, float]]:
        """Combine pass_states [r=1..4] using exact integer r* with STE differentiable weights."""
        require_ok(len(pass_states) == self.r_max, f"Expected {self.r_max} pass states")
        stacked = torch.stack([s.float() for s in pass_states], dim=-1)  # [B, T, D, R]
        int_r = self.allocate_integer_loops(buoyancy_r1)  # [B, T] in {1..4}
        hard_oh = F.one_hot(int_r - 1, num_classes=self.r_max).float()  # [B, T, R]

        # Soft unimodal distribution centered on smooth target depth from buoyancy_r1.
        r_vals = torch.arange(1, self.r_max + 1, device=buoyancy_r1.device, dtype=torch.float32)
        z = (buoyancy_r1 - buoyancy_r1.mean()) / (buoyancy_r1.std(unbiased=False) + 1e-5)
        soft_r = (self.target_mean_r + 0.75 * torch.tanh(z)).unsqueeze(-1)  # [B, T, 1]
        soft_w = F.softmax(-1.5 * ((r_vals.view(1, 1, -1) - soft_r) ** 2), dim=-1)

        weights = (hard_oh - soft_w.detach() + soft_w) if ste else hard_oh
        out = (stacked * weights.unsqueeze(-2)).sum(dim=-1).to(pass_states[0].dtype)

        expected_soft_r = (soft_w * r_vals.view(1, 1, -1)).sum(dim=-1).mean()
        ponder_loss = (expected_soft_r - self.target_mean_r) ** 2
        mean_int_r = float(int_r.float().mean().item())
        hist = {f"r{k}_frac": float((int_r == k).float().mean().item()) for k in range(1, self.r_max + 1)}
        stats = {"mean_int_r": mean_int_r, "mean_soft_r": float(expected_soft_r.item()), **hist}
        return out, ponder_loss, stats


class FastSurfaceMTPDraft(nn.Module):
    """Fast shallow surface multi-token draft head (MTP-8, tied embedding output).

    Uses K=8 low-rank residual projections (d_model -> d_draft -> d_model) sharing the
    backbone's tied vocabulary embedding matrix so parameter cost is exact and compact.
    """

    def __init__(
        self,
        d_model: int,
        k_draft: int = 8,
        d_draft: int = 48,
        seed: int = 42,
    ) -> None:
        super().__init__()
        require_ok(k_draft >= 1 and d_draft > 0, "k_draft and d_draft must be positive")
        self.d_model = d_model
        self.k_draft = int(k_draft)
        self.d_draft = int(d_draft)
        self.down = nn.ModuleList([nn.Linear(d_model, d_draft, bias=False) for _ in range(k_draft)])
        self.up = nn.ModuleList([nn.Linear(d_draft, d_model, bias=False) for _ in range(k_draft)])
        for idx in range(k_draft):
            _init_linear(self.down[idx], 1.0 / math.sqrt(float(d_model)), seed + 2 * idx)
            _init_linear(self.up[idx], 0.1 / math.sqrt(float(d_draft)), seed + 2 * idx + 1)

    def forward(self, h: torch.Tensor, lm_weight: torch.Tensor) -> List[torch.Tensor]:
        """Return list of K draft logit tensors [B, T, V] for offsets +1..+K."""
        outs: List[torch.Tensor] = []
        for idx in range(self.k_draft):
            hd = h + self.up[idx](F.silu(self.down[idx](h)))
            outs.append(F.linear(hd, lm_weight))
        return outs


# ---------------------------------------------------------------------------
# Baseline Safety Harness: Track S50 Channel-2B Airlock + DPI Norm Clamp
# ---------------------------------------------------------------------------


class Channel2BAirlockClamp(nn.Module):
    """Outer DPI norm clamp + Channel-2B state-transport airlock (folded into baseline harness).

    Per PREREG-S110 Amendment 1 Discovery 4: NOT counted as a generative accuracy shell;
    provides uniform norm-bounded input protection across baseline & Geosphere arms.
    """

    def __init__(self, max_norm: float = 8.0) -> None:
        super().__init__()
        require_ok(max_norm > 0.0, "max_norm must be positive")
        self.max_norm = float(max_norm)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, float]:
        xf = x.float()
        norms = torch.sqrt((xf * xf).sum(dim=-1, keepdim=True) + 1e-12)
        scale = torch.clamp(self.max_norm / norms, max=1.0)
        clamped_frac = float((norms > self.max_norm).float().mean().item())
        return (xf * scale).to(x.dtype), clamped_frac


# ---------------------------------------------------------------------------
# Portal-3 Beltrami [C, K] = 0 Helicity-Conservation & O3.5 Collapse Diagnostic
# ---------------------------------------------------------------------------


def build_paired_beltrami_operator(d_model: int) -> torch.Tensor:
    """Symmetric parity-balanced shell operator C = diag(lambda_j I_2) commuting with 2x2 block Cayley.

    Every 2x2 block-diagonal skew matrix K satisfies [C, K] = 0 identically (Portal-3 iff law),
    while parity symmetry spec(C) = -spec(C) enforces Portal-3 O3.2 non-chirality.
    """
    require_ok(d_model >= 4 and d_model % 4 == 0, "d_model must be a positive multiple of 4 for parity-balanced C")
    n_pairs = d_model // 2
    n_half = n_pairs // 2
    diag_vals: List[float] = []
    for q in range(n_half):
        lam = float(q + 1) / float(n_half)
        diag_vals.extend([lam, lam, -lam, -lam])
    return torch.diag(torch.tensor(diag_vals, dtype=torch.float32))


@torch.no_grad()
def run_beltrami_helicity_diagnostic(
    cayley_module: CayleyBlock2x2SO,
    n_steps: int = 8,
    seed: int = 42,
) -> Dict[str, Any]:
    """Verify Portal-3 Beltrami [C,K]=0 helicity conservation, non-commuting drift, and O3.5 collapse."""
    d = cayley_module.d_model
    c_op = build_paired_beltrami_operator(d)
    k_comm = cayley_module.explicit_skew_matrix().cpu()
    q_comm = cayley_module.explicit_matrix().cpu()

    g = _make_gen(seed)
    v0 = torch.randn(d, generator=g, dtype=torch.float32)
    v0 = v0 / torch.linalg.vector_norm(v0)

    def moments(v: torch.Tensor) -> List[float]:
        out: List[float] = []
        cv = v.clone()
        for _ in range(5):
            out.append(float(torch.dot(v, cv).item()))
            cv = c_op @ cv
        return out

    # 1. Commuting Cayley: [C, K] = 0 -> all moments m_0..m_4 conserved across n_steps.
    comm_frob = float(torch.linalg.matrix_norm(c_op @ k_comm - k_comm @ c_op, ord="fro").item())
    m0_init = moments(v0)
    v = v0.clone()
    max_moment_drift = 0.0
    for _ in range(n_steps):
        v = q_comm @ v
        m_cur = moments(v)
        for a, b in zip(m0_init, m_cur):
            max_moment_drift = max(max_moment_drift, abs(a - b))
    state_motion = float(torch.linalg.vector_norm(v - v0).item())

    # 2. Non-commuting skew control: mixes maximal-gap Beltrami shells (+1.0 vs -1.0) -> [C, K_cross] != 0.
    k_cross = torch.zeros((d, d), dtype=torch.float32)
    i_pos, i_neg = d - 4, d - 2
    k_cross[i_pos, i_neg] = -0.6
    k_cross[i_neg, i_pos] = 0.6
    k_cross[i_pos + 1, i_neg + 1] = -0.4
    k_cross[i_neg + 1, i_pos + 1] = 0.4
    comm_cross = c_op @ k_cross - k_cross @ c_op
    comm_cross_frob = float(torch.linalg.matrix_norm(comm_cross, ord="fro").item())
    # Instantaneous helicity rate dH/dt = v0^T [C, K_cross] v0 vs finite-difference check.
    expected_dh = float(torch.dot(v0, comm_cross @ v0).item())
    # Exact Cayley step Q_cross = (I - K_cross)(I + K_cross)^{-1} (tiny 4x4 block only, diagnostic control).
    eye_d = torch.eye(d, dtype=torch.float32)
    q_cross = torch.linalg.solve(eye_d + k_cross, eye_d - k_cross)
    v_cross = q_cross @ v0
    energy_drift_cross = abs(float(torch.dot(v_cross, v_cross).item()) - m0_init[0])
    helicity_drift_cross = abs(float(torch.dot(v_cross, c_op @ v_cross).item()) - m0_init[1])
    # Finite-difference instantaneous derivative verification (h = 1e-4)
    eps_t = 1e-4
    v_eps = v0 + eps_t * (k_cross @ v0)
    fd_dh = (float(torch.dot(v_eps, c_op @ v_eps).item()) - m0_init[1]) / eps_t
    # Note: d/dt (v^T C v) = v^T (C K + K^T C) v = v^T (C K - K C) v = v^T [C, K] v.
    dh_law_err = abs(fd_dh - expected_dh)

    # 3. O3.5 Symmetric-residual collapse control: v <- (I + 0.25 C) v strictly increases Rayleigh H/E.
    v_sym = v0.clone()
    rayleigh_seq: List[float] = []
    for _ in range(n_steps + 1):
        e_cur = float(torch.dot(v_sym, v_sym).item())
        h_cur = float(torch.dot(v_sym, c_op @ v_sym).item())
        rayleigh_seq.append(h_cur / e_cur)
        v_sym = v_sym + 0.25 * (c_op @ v_sym)
    strictly_collapsing = all(rayleigh_seq[i + 1] > rayleigh_seq[i] for i in range(n_steps))

    return {
        "d_model": d,
        "n_steps": n_steps,
        "commuting_commutator_frob": comm_frob,
        "commuting_max_moment_drift_m0_m4": max_moment_drift,
        "commuting_state_motion_l2": state_motion,
        "noncommuting_commutator_frob": comm_cross_frob,
        "noncommuting_energy_drift": energy_drift_cross,
        "noncommuting_helicity_drift": helicity_drift_cross,
        "noncommuting_dh_commutator_law_err": dh_law_err,
        "o35_symmetric_rayleigh_start": rayleigh_seq[0],
        "o35_symmetric_rayleigh_end": rayleigh_seq[-1],
        "o35_symmetric_strictly_monotone_collapse": strictly_collapsing,
    }


@torch.no_grad()
def measure_trace_beltrami_rayleigh(pass_states: Sequence[torch.Tensor]) -> List[float]:
    """Compute mean Beltrami Rayleigh quotient H/E = <h, C h> / ||h||^2 across loop passes."""
    if not pass_states:
        return []
    d = pass_states[0].shape[-1]
    if d % 4 != 0:
        return []
    c_diag = torch.diagonal(build_paired_beltrami_operator(d)).to(pass_states[0].device)
    out: List[float] = []
    for h in pass_states:
        hf = h.float()
        e_val = (hf * hf).sum(dim=-1).clamp_min(1e-12)
        h_val = (hf * hf * c_diag.view(1, 1, d)).sum(dim=-1)
        out.append(float((h_val / e_val).mean().item()))
    return out


# ---------------------------------------------------------------------------
# Transformer Building Blocks & Geosphere-Net Model
# ---------------------------------------------------------------------------


class RMSNorm(nn.Module):
    def __init__(self, d_model: int, eps: float = 1e-6) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.ones(d_model))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        xf = x.float()
        rms = torch.rsqrt((xf * xf).mean(dim=-1, keepdim=True) + self.eps)
        return (xf * rms * self.weight.float()).to(x.dtype)


def _apply_rope(q: torch.Tensor, k: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
    # q, k: [B, H, T, Dh]
    _, _, seq_len, d_head = q.shape
    half = d_head // 2
    inv_freq = 1.0 / (10000.0 ** (torch.arange(0, half, device=q.device, dtype=torch.float32) / float(half)))
    pos = torch.arange(seq_len, device=q.device, dtype=torch.float32)
    freqs = torch.outer(pos, inv_freq)  # [T, half]
    cos = freqs.cos().view(1, 1, seq_len, half)
    sin = freqs.sin().view(1, 1, seq_len, half)

    def rot(t: torch.Tensor) -> torch.Tensor:
        tf = t.float()
        t1 = tf[..., 0::2]
        t2 = tf[..., 1::2]
        out1 = t1 * cos - t2 * sin
        out2 = t1 * sin + t2 * cos
        return torch.stack((out1, out2), dim=-1).reshape_as(tf).to(t.dtype)

    return rot(q), rot(k)


class CausalSelfAttention(nn.Module):
    def __init__(self, d_model: int, n_heads: int, ngpt_mode: bool = False, seed: int = 42) -> None:
        super().__init__()
        require_ok(d_model % n_heads == 0, "d_model must be divisible by n_heads")
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_head = d_model // n_heads
        self.ngpt_mode = bool(ngpt_mode)
        self.q_proj = nn.Linear(d_model, d_model, bias=False)
        self.k_proj = nn.Linear(d_model, d_model, bias=False)
        self.v_proj = nn.Linear(d_model, d_model, bias=False)
        self.o_proj = nn.Linear(d_model, d_model, bias=False)
        std = 1.0 / math.sqrt(float(d_model))
        _init_linear(self.q_proj, std, seed + 1)
        _init_linear(self.k_proj, std, seed + 2)
        _init_linear(self.v_proj, std, seed + 3)
        _init_linear(self.o_proj, std * 0.5, seed + 4)
        if self.ngpt_mode:
            self.qk_scale = nn.Parameter(torch.full((n_heads, 1, 1), math.sqrt(float(self.d_head))))
        else:
            self.qk_scale = None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b_sz, seq_len, _ = x.shape
        q = self.q_proj(x).view(b_sz, seq_len, self.n_heads, self.d_head).transpose(1, 2)
        k = self.k_proj(x).view(b_sz, seq_len, self.n_heads, self.d_head).transpose(1, 2)
        v = self.v_proj(x).view(b_sz, seq_len, self.n_heads, self.d_head).transpose(1, 2)
        q, k = _apply_rope(q, k)
        if self.ngpt_mode and self.qk_scale is not None:
            q = _l2_normalize_safe(q) * self.qk_scale.to(q.dtype)
            k = _l2_normalize_safe(k)
            scale = 1.0
        else:
            scale = 1.0 / math.sqrt(float(self.d_head))
        out = F.scaled_dot_product_attention(q, k, v, attn_mask=None, dropout_p=0.0, is_causal=True, scale=scale)
        out = out.transpose(1, 2).contiguous().view(b_sz, seq_len, self.d_model)
        return self.o_proj(out)


class SwiGLUMLP(nn.Module):
    def __init__(self, d_model: int, d_ff: int, seed: int = 42) -> None:
        super().__init__()
        self.w_gate = nn.Linear(d_model, d_ff, bias=False)
        self.w_up = nn.Linear(d_model, d_ff, bias=False)
        self.w_down = nn.Linear(d_ff, d_model, bias=False)
        _init_linear(self.w_gate, 1.0 / math.sqrt(float(d_model)), seed + 1)
        _init_linear(self.w_up, 1.0 / math.sqrt(float(d_model)), seed + 2)
        _init_linear(self.w_down, 0.5 / math.sqrt(float(d_ff)), seed + 3)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.w_down(F.silu(self.w_gate(x)) * self.w_up(x))


class GeosphereBlock(nn.Module):
    """Single transformer block with optional pruned Geosphere operators (Cayley, Darcy EMA, Bingham)."""

    def __init__(
        self,
        d_model: int,
        n_heads: int,
        d_ff: int,
        use_cayley: bool = False,
        cayley_rank: int = 16,
        use_darcy: bool = False,
        use_bingham: bool = False,
        k_poloidal: Optional[int] = None,
        bingham_tau: float = 0.0,
        bingham_yield: float = 0.5,
        ngpt_mode: bool = False,
        seed: int = 42,
    ) -> None:
        super().__init__()
        self.ngpt_mode = bool(ngpt_mode)
        self.norm1 = RMSNorm(d_model)
        self.attn = CausalSelfAttention(d_model, n_heads, ngpt_mode=ngpt_mode, seed=seed + 10)
        self.norm2 = RMSNorm(d_model)
        self.mlp = SwiGLUMLP(d_model, d_ff, seed=seed + 20)
        self.cayley = CayleyBlock2x2SO(d_model, bottleneck_rank=cayley_rank, seed=seed + 30) if use_cayley else None
        self.darcy = DiagonalDarcyEMA(d_model, seed=seed + 40) if use_darcy else None
        self.bingham = (
            VectorProximalPoloidalBingham(
                d_model,
                k_poloidal=k_poloidal,
                tau_y=bingham_tau,
                yield_number=bingham_yield,
                post_renorm=False,
            )
            if use_bingham
            else None
        )
        if self.ngpt_mode:
            self.alpha_attn = nn.Parameter(torch.full((d_model,), 0.15))
            self.alpha_mlp = nn.Parameter(torch.full((d_model,), 0.15))
        else:
            self.alpha_attn = None
            self.alpha_mlp = None

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, float]]:
        stats: Dict[str, float] = {}
        if self.ngpt_mode and self.alpha_attn is not None and self.alpha_mlp is not None:
            h_a = _l2_normalize_safe(self.attn(x))
            a_step = torch.sigmoid(self.alpha_attn.float()).to(x.dtype) * 0.5
            x = _l2_normalize_safe(x + a_step * (h_a - x))
            if self.darcy is not None:
                x = _l2_normalize_safe(self.darcy(x))
            h_m = _l2_normalize_safe(self.mlp(x))
            m_step = torch.sigmoid(self.alpha_mlp.float()).to(x.dtype) * 0.5
            x = _l2_normalize_safe(x + m_step * (h_m - x))
        else:
            x = x + self.attn(self.norm1(x))
            if self.darcy is not None:
                x = self.darcy(x)
            x = x + self.mlp(self.norm2(x))

        if self.cayley is not None:
            x = self.cayley(x)
        if self.bingham is not None:
            x, b_stats = self.bingham(x)
            stats["bingham_plug_fraction"] = b_stats["plug_fraction"]
        return x, stats


@dataclass(frozen=True)
class S110ModelConfig:
    arm_name: str
    stage: str  # "H10a_single_shell", "H10b_coupled_loso", "baseline_anchor"
    vocab_size: int = VOCAB_SIZE_BYTE
    d_model: int = 384
    n_heads: int = 6
    d_ff: int = 1104
    n_pre: int = 2
    n_core: int = 4
    n_post: int = 2
    r_mean: float = 2.0
    r_max: int = 4
    # The 4 Amendment-1 surviving operators:
    use_cayley: bool = False
    cayley_rank: int = 16
    use_bingham: bool = False
    k_poloidal: int = 192
    bingham_yield: float = 0.5
    bingham_tau: float = 0.0
    use_darcy: bool = False
    use_act_plumes: bool = False
    use_mtp_draft: bool = False
    mtp_k: int = 8
    mtp_d_draft: int = 48
    # Baseline & safety flags:
    ngpt_mode: bool = False
    use_airlock_clamp: bool = True
    airlock_max_norm: float = 8.0
    # Unlooped external baseline support (r_mean=1.0, n_core=8 -> 12 phys layers):
    unlooped_cot_token_mult: float = 1.0
    # Pruned Amendment-1 traps (MUST ALWAYS BE FALSE - fail-closed!):
    causal_sinkhorn: bool = False
    dense_cayley_lu: bool = False
    telluric_direct_skip: bool = False
    bingham_post_renorm: bool = False

    def validate(self) -> None:
        # Fail-closed rejection of ALL 4 Amendment-1 pruned mechanisms!
        require_ok(not self.causal_sinkhorn, "PRUNED (Amendment 1 Discovery 1): causal Sinkhorn collapses to I_n")
        require_ok(not self.dense_cayley_lu, "PRUNED (Amendment 1 Discovery 2): dense Cayley LU violates sm_86 wall")
        require_ok(not self.telluric_direct_skip, "PRUNED (Amendment 1 Discovery 4): Telluric skip violates zero-skip graph")
        require_ok(not self.bingham_post_renorm, "PRUNED (Amendment 1 Discovery 3): Bingham post-renorm breaks SO(k)")
        require_ok(self.d_model > 0 and self.d_model % 4 == 0, "d_model must be a positive multiple of 4")
        require_ok(self.d_model % self.n_heads == 0, "d_model must be divisible by n_heads")
        require_ok(self.d_ff > 0 and self.d_ff % 8 == 0, "d_ff must be a positive multiple of 8")
        require_ok(self.n_pre >= 1 and self.n_core >= 1 and self.n_post >= 1, "Need >= 1 pre/core/post blocks")
        require_ok(0 < self.k_poloidal < self.d_model, "k_poloidal must satisfy 0 < k < d_model")
        require_ok(1.0 <= self.r_mean <= float(self.r_max), "r_mean must be in [1, r_max]")


class GeosphereNetLM(nn.Module):
    """Pruned 4-Operator Geosphere-Net Language & Algorithmic Model (PREREG-S110 + Amendment 1).

    Strict zero-skip graph: tok_emb -> Airlock -> Pre -> Core (looped) -> Post -> FinalNorm -> TiedLMHead.
    Supports pre-normalization (pre-N) counterfactual state patching at any core loop step r.
    """

    def __init__(self, cfg: S110ModelConfig, seed: int = 42) -> None:
        super().__init__()
        cfg.validate()
        self.cfg = cfg
        self.seed = int(seed)

        self.tok_emb = nn.Embedding(cfg.vocab_size, cfg.d_model)
        g = _make_gen(seed)
        with torch.no_grad():
            self.tok_emb.weight.normal_(0.0, 0.02, generator=g)

        self.airlock = Channel2BAirlockClamp(cfg.airlock_max_norm) if cfg.use_airlock_clamp else None

        self.pre_blocks = nn.ModuleList(
            [
                GeosphereBlock(
                    cfg.d_model,
                    cfg.n_heads,
                    cfg.d_ff,
                    use_cayley=False,
                    use_darcy=False,
                    use_bingham=False,
                    ngpt_mode=cfg.ngpt_mode,
                    seed=seed + 100 + i * 50,
                )
                for i in range(cfg.n_pre)
            ]
        )
        self.core_blocks = nn.ModuleList(
            [
                GeosphereBlock(
                    cfg.d_model,
                    cfg.n_heads,
                    cfg.d_ff,
                    use_cayley=cfg.use_cayley,
                    cayley_rank=cfg.cayley_rank,
                    use_darcy=cfg.use_darcy,
                    use_bingham=cfg.use_bingham,
                    k_poloidal=cfg.k_poloidal,
                    bingham_tau=cfg.bingham_tau,
                    bingham_yield=cfg.bingham_yield,
                    ngpt_mode=cfg.ngpt_mode,
                    seed=seed + 500 + i * 50,
                )
                for i in range(cfg.n_core)
            ]
        )
        self.post_blocks = nn.ModuleList(
            [
                GeosphereBlock(
                    cfg.d_model,
                    cfg.n_heads,
                    cfg.d_ff,
                    use_cayley=False,
                    use_darcy=False,
                    use_bingham=False,
                    ngpt_mode=cfg.ngpt_mode,
                    seed=seed + 900 + i * 50,
                )
                for i in range(cfg.n_post)
            ]
        )
        self.act_controller = (
            GeothermalACTController(cfg.d_model, r_max=cfg.r_max, target_mean_r=cfg.r_mean, seed=seed + 1300)
            if cfg.use_act_plumes
            else None
        )
        self.mtp_draft = (
            FastSurfaceMTPDraft(cfg.d_model, k_draft=cfg.mtp_k, d_draft=cfg.mtp_d_draft, seed=seed + 1400)
            if cfg.use_mtp_draft
            else None
        )
        self.final_norm = RMSNorm(cfg.d_model)

    @torch.no_grad()
    def calibrate_bingham_quantiles(self, sample_ids: torch.Tensor, yield_number: Optional[float] = None) -> List[Dict[str, float]]:
        """Calibrate & freeze tau_Y quantiles across all core Bingham modules from Stage-1 activations."""
        if not self.cfg.use_bingham:
            return []
        was_training = self.training
        self.eval()
        h = self.tok_emb(sample_ids)
        if self.airlock is not None:
            h, _ = self.airlock(h)
        if self.cfg.ngpt_mode:
            h = _l2_normalize_safe(h)
        for blk in self.pre_blocks:
            h, _ = blk(h)
        receipts: List[Dict[str, float]] = []
        for idx, blk in enumerate(self.core_blocks):
            # Capture pre-Bingham activation distribution inside each core block.
            x = h + blk.attn(blk.norm1(h))
            if blk.darcy is not None:
                x = blk.darcy(x)
            x = x + blk.mlp(blk.norm2(x))
            if blk.cayley is not None:
                x = blk.cayley(x)
            if blk.bingham is not None:
                rec = blk.bingham.calibrate_from_activations(x, yield_number=yield_number)
                rec["core_layer"] = float(idx)
                receipts.append(rec)
                h, _ = blk.bingham(x)
            else:
                h = x
        self.train(was_training)
        return receipts

    def forward(
        self,
        input_ids: torch.Tensor,
        r_loops_override: Optional[int] = None,
        return_trace: bool = False,
        patch_pre_norm_state: Optional[Tuple[int, torch.Tensor]] = None,
        return_draft: bool = False,
        grad_checkpoint: bool = False,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """Forward pass with exact sparse sequence-level ACT routing (r_bar = 2.000) & pre-N patching.

        When use_act_plumes=True and batch_size >= 4 (and no r_loops_override / patch), executes
        strictly sparse sequence-level ACT routing:
          Pass 1: 100% of sequences -> rank-quota integer r* in {1,2,3,4} with mean 2.000
          Pass 2..4: ONLY active sequences with r* >= r execute core_blocks!
        For B=8, total sequence-passes = 8 + 5 + 2 + 1 = 16 = 2.000 * B (exact 1.000x FLOP/VRAM parity!).
        """
        h = self.tok_emb(input_ids)
        airlock_clamped = 0.0
        if self.airlock is not None:
            h, airlock_clamped = self.airlock(h)
        if self.cfg.ngpt_mode:
            h = _l2_normalize_safe(h)

        for blk in self.pre_blocks:
            h, _ = blk(h)

        pass_states: List[torch.Tensor] = []
        bingham_plugs: List[float] = []
        ponder_loss = torch.zeros((), dtype=torch.float32, device=h.device)
        act_stats: Dict[str, float] = {}
        b_sz = h.shape[0]

        def _run_core_pass(state: torch.Tensor) -> torch.Tensor:
            cur = state
            for blk in self.core_blocks:
                if grad_checkpoint and self.training and cur.requires_grad:
                    cur = _grad_checkpoint(lambda t, _b=blk: _b(t)[0], cur, use_reentrant=False)
                else:
                    cur, b_st = blk(cur)
                    if "bingham_plug_fraction" in b_st:
                        bingham_plugs.append(b_st["bingham_plug_fraction"])
            return cur

        h_entry = h
        if (
            r_loops_override is None
            and patch_pre_norm_state is None
            and self.act_controller is not None
            and b_sz >= 4
            and not return_trace
        ):
            # Exact sparse sequence-level geothermal ACT routing (exact mean_r = 2.000 for B % 8 == 0).
            h1 = _run_core_pass(h)
            buoy_tok = self.act_controller.compute_buoyancy_score(h, h1)  # [B, T]
            buoy_seq = buoy_tok.mean(dim=-1)  # [B]
            int_r_seq = self.act_controller.allocate_integer_loops(buoy_seq)  # [B] in {1..4}
            # Differentiable STE ponder gate so buoyancy controller receives finite training gradients.
            r_vals = torch.arange(1, self.cfg.r_max + 1, device=h.device, dtype=torch.float32)
            z_seq = (buoy_seq - buoy_seq.mean()) / (buoy_seq.std(unbiased=False) + 1e-5)
            soft_r_seq = self.cfg.r_mean + 0.75 * torch.tanh(z_seq)
            soft_w_seq = F.softmax(-1.5 * ((r_vals.view(1, -1) - soft_r_seq.unsqueeze(-1)) ** 2), dim=-1)
            expected_soft_r = (soft_w_seq * r_vals.view(1, -1)).sum(dim=-1).mean()
            ponder_loss = (expected_soft_r - self.cfg.r_mean) ** 2

            # Soft STE scaling factor = 1.0 in value, carries gradient into score_proj & surprise_scale.
            ste_scale = (1.0 + 0.05 * (torch.sigmoid(z_seq) - torch.sigmoid(z_seq).detach())).view(b_sz, 1, 1).to(h1.dtype)
            out_states: List[Optional[torch.Tensor]] = [None] * b_sz
            seq_passes_executed = b_sz
            for b_idx in range(b_sz):
                if int(int_r_seq[b_idx].item()) == 1:
                    out_states[b_idx] = h1[b_idx]

            active_mask = int_r_seq >= 2
            cur_indices = torch.nonzero(active_mask, as_tuple=False).squeeze(-1)
            cur_h = h1.index_select(0, cur_indices) if cur_indices.numel() > 0 else h1[:0]
            for r_step in range(2, self.cfg.r_max + 1):
                if cur_indices.numel() == 0:
                    break
                seq_passes_executed += int(cur_indices.numel())
                cur_h = _run_core_pass(cur_h)
                keep_pos: List[int] = []
                for pos_i in range(cur_indices.numel()):
                    orig_b = int(cur_indices[pos_i].item())
                    if int(int_r_seq[orig_b].item()) == r_step or r_step == self.cfg.r_max:
                        out_states[orig_b] = cur_h[pos_i]
                    else:
                        keep_pos.append(pos_i)
                if keep_pos:
                    keep_t = torch.tensor(keep_pos, dtype=torch.long, device=h.device)
                    cur_indices = cur_indices.index_select(0, keep_t)
                    cur_h = cur_h.index_select(0, keep_t)
                else:
                    cur_indices = cur_indices[:0]

            h = torch.stack([s for s in out_states if s is not None], dim=0) * ste_scale
            act_stats = {
                "mean_int_r": float(int_r_seq.float().mean().item()),
                "mean_soft_r": float(expected_soft_r.item()),
                "core_seq_passes_executed": float(seq_passes_executed),
                "r1_frac": float((int_r_seq == 1).float().mean().item()),
                "r2_frac": float((int_r_seq == 2).float().mean().item()),
                "r3_frac": float((int_r_seq == 3).float().mean().item()),
                "r4_frac": float((int_r_seq == 4).float().mean().item()),
            }
        else:
            if r_loops_override is not None:
                n_passes = int(r_loops_override)
                require_ok(n_passes >= 1, "r_loops_override must be >= 1")
                use_act_now = False
            elif self.act_controller is not None:
                n_passes = self.cfg.r_max
                use_act_now = True
            else:
                n_passes = max(1, int(round(self.cfg.r_mean)))
                use_act_now = False

            buoyancy_r1: Optional[torch.Tensor] = None
            for r_idx in range(1, n_passes + 1):
                h_prev = h
                h = _run_core_pass(h)
                if patch_pre_norm_state is not None and patch_pre_norm_state[0] == r_idx:
                    h = patch_pre_norm_state[1].to(dtype=h.dtype, device=h.device)
                if r_idx == 1 and use_act_now and self.act_controller is not None:
                    buoyancy_r1 = self.act_controller.compute_buoyancy_score(h_prev, h)
                pass_states.append(h)

            if use_act_now and self.act_controller is not None and buoyancy_r1 is not None:
                h, ponder_loss, act_stats = self.act_controller.select_loop_states(
                    pass_states, buoyancy_r1, ste=self.training
                )
            else:
                h = pass_states[-1]
                act_stats = {
                    "mean_int_r": float(n_passes),
                    "mean_soft_r": float(n_passes),
                    "core_seq_passes_executed": float(n_passes * b_sz),
                }

        h_pre_post = h
        for blk in self.post_blocks:
            h, _ = blk(h)

        h_pre_final_norm = h
        h_out = self.final_norm(h)
        logits = F.linear(h_out, self.tok_emb.weight)

        draft_logits: Optional[List[torch.Tensor]] = None
        if return_draft and self.mtp_draft is not None:
            draft_logits = self.mtp_draft(h_out, self.tok_emb.weight)

        info: Dict[str, Any] = {
            "ponder_loss": ponder_loss,
            "airlock_clamped_fraction": airlock_clamped,
            "mean_bingham_plug_fraction": (sum(bingham_plugs) / len(bingham_plugs)) if bingham_plugs else 0.0,
            "act_stats": act_stats,
            "draft_logits": draft_logits,
        }
        if return_trace:
            info["h_entry"] = h_entry.detach()
            info["pass_states_pre_norm"] = [s.detach() for s in pass_states]
            info["h_core_exit_pre_norm"] = h_pre_post.detach()
            info["h_pre_final_norm"] = h_pre_final_norm.detach()
            info["beltrami_rayleigh_by_pass"] = measure_trace_beltrami_rayleigh(pass_states)
        return logits, info


# ---------------------------------------------------------------------------
# Exact RTN Group-128 PTQ & Track S96 M1-H1 Loop-Drift Monitor (No Weight Saving)
# ---------------------------------------------------------------------------


@torch.no_grad()
def apply_rtn_ptq_copy(model: GeosphereNetLM, bits: int = 3, group_size: int = 128) -> GeosphereNetLM:
    """Return a deep copy with symmetric per-output-channel group-128 RTN PTQ (embeddings excluded)."""
    require_ok(bits in (3, 4), f"Unsupported RTN bits: {bits}")
    qmax = float((1 << (bits - 1)) - 1)
    q_model = copy.deepcopy(model)
    for name, mod in q_model.named_modules():
        if isinstance(mod, nn.Linear):
            w = mod.weight.data.float()
            out_f, in_f = w.shape
            if in_f >= group_size and in_f % group_size == 0:
                wg = w.view(out_f, in_f // group_size, group_size)
                scale = wg.abs().amax(dim=-1, keepdim=True).clamp_min(1e-8) / qmax
                wq = torch.clamp(torch.round(wg / scale), -qmax, qmax) * scale
                mod.weight.data.copy_(wq.view(out_f, in_f).to(mod.weight.dtype))
            else:
                scale = w.abs().amax(dim=-1, keepdim=True).clamp_min(1e-8) / qmax
                wq = torch.clamp(torch.round(w / scale), -qmax, qmax) * scale
                mod.weight.data.copy_(wq.to(mod.weight.dtype))
    return q_model


@torch.no_grad()
def measure_m1_h1_loop_drift(
    model_fp: GeosphereNetLM,
    model_q: GeosphereNetLM,
    sample_ids: torch.Tensor,
) -> Dict[str, float]:
    """Measure Track S96 M1-H1 3-bit loop-drift amplification delta_3 / delta_1 & empirical rho."""
    model_fp.eval()
    model_q.eval()
    _, tr_fp = model_fp(sample_ids, r_loops_override=4, return_trace=True)
    _, tr_q = model_q(sample_ids, r_loops_override=4, return_trace=True)
    p_fp = tr_fp["pass_states_pre_norm"]
    p_q = tr_q["pass_states_pre_norm"]
    deltas = [
        float(torch.linalg.vector_norm(a.float() - b.float(), dim=-1).mean().item())
        for a, b in zip(p_fp, p_q)
    ]
    d1 = max(1e-9, deltas[0])
    d3 = deltas[2] if len(deltas) >= 3 else deltas[-1]
    d4 = deltas[3] if len(deltas) >= 4 else deltas[-1]
    ratio_3_1 = d3 / d1
    rho = math.sqrt(max(1e-12, ratio_3_1 - 1.0)) if ratio_3_1 > 1.0 else 0.0
    return {
        "delta_1": round(deltas[0], 6),
        "delta_2": round(deltas[1], 6) if len(deltas) >= 2 else round(deltas[0], 6),
        "delta_3": round(d3, 6),
        "delta_4": round(d4, 6),
        "delta_3_over_delta_1": round(ratio_3_1, 4),
        "empirical_rho": round(rho, 4),
    }


@torch.no_grad()
def measure_attention_sink_stats(model: GeosphereNetLM, sample_ids: torch.Tensor) -> Dict[str, float]:
    """Measure final core block attention-sink top-1 weight & normalized entropy (DarcyEMA axis)."""
    model.eval()
    h = model.tok_emb(sample_ids)
    if model.airlock is not None:
        h, _ = model.airlock(h)
    if model.cfg.ngpt_mode:
        h = _l2_normalize_safe(h)
    for blk in model.pre_blocks:
        h, _ = blk(h)
    for blk in model.core_blocks[:-1]:
        h, _ = blk(h)
    last_blk = model.core_blocks[-1]
    x = h if last_blk.ngpt_mode else last_blk.norm1(h)
    attn = last_blk.attn
    b_sz, seq_len, _ = x.shape
    q = attn.q_proj(x).view(b_sz, seq_len, attn.n_heads, attn.d_head).transpose(1, 2)
    k = attn.k_proj(x).view(b_sz, seq_len, attn.n_heads, attn.d_head).transpose(1, 2)
    q, k = _apply_rope(q, k)
    if attn.ngpt_mode and attn.qk_scale is not None:
        q = _l2_normalize_safe(q) * attn.qk_scale.to(q.dtype)
        k = _l2_normalize_safe(k)
        scale = 1.0
    else:
        scale = 1.0 / math.sqrt(float(attn.d_head))
    scores = torch.matmul(q.float(), k.float().transpose(-2, -1)) * scale
    mask = torch.triu(torch.ones((seq_len, seq_len), device=x.device, dtype=torch.bool), diagonal=1)
    scores = scores.masked_fill(mask.view(1, 1, seq_len, seq_len), float("-inf"))
    probs = F.softmax(scores, dim=-1)
    # Measure over second half of sequence where context is substantial.
    mid = max(1, seq_len // 2)
    p_tail = probs[:, :, mid:, :]
    bos_sink = float(p_tail[..., 0].mean().item())
    max_wt = float(p_tail.amax(dim=-1).mean().item())
    ent = -(p_tail * torch.log(p_tail.clamp_min(1e-12))).sum(dim=-1)
    norm_ent = float((ent / math.log(float(seq_len))).mean().item())
    return {
        "bos_sink_weight": round(bos_sink, 6),
        "max_attn_weight": round(max_wt, 6),
        "normalized_attn_entropy": round(norm_ent, 6),
    }


# ---------------------------------------------------------------------------
# Exact Parameter & Analytical FLOP/Token Accounting + Full 15M Arm Matrix
# ---------------------------------------------------------------------------


def count_parameters(model: nn.Module) -> Dict[str, int]:
    total = sum(p.numel() for p in model.parameters())
    emb = 0
    if hasattr(model, "tok_emb") and isinstance(model.tok_emb, nn.Embedding):
        emb = model.tok_emb.weight.numel()
    return {"total_params": int(total), "embedding_params": int(emb), "non_embedding_params": int(total - emb)}


def analytical_forward_flops_per_token(cfg: S110ModelConfig, seq_len: int = 512) -> Dict[str, float]:
    """Analytical forward MAC->FLOPs (2 FLOPs/MAC) per token at effective depth L_eff.

    Includes attention projections + QK^T/AV + SwiGLU MLP + all enabled Geosphere operators
    (Cayley 2x2 4-FMA + bottleneck, Darcy O(log T) scan, Bingham norm/scale, ACT scorer, MTP-8 draft).
    """
    d = float(cfg.d_model)
    dff = float(cfg.d_ff)
    t = float(seq_len)
    l_eff = float(cfg.n_pre) + float(cfg.n_core) * float(cfg.r_mean) + float(cfg.n_post)

    # Standard block FLOPs/token: 4*d^2 (QKV+O) + 2*T*d (QK^T + AV) + 3*d*dff (SwiGLU) -> x2 for FMA
    block_linear = 2.0 * (4.0 * d * d + 3.0 * d * dff)
    block_attn_seq = 4.0 * t * d
    base_flops = l_eff * (block_linear + block_attn_seq)

    core_eff = float(cfg.n_core) * float(cfg.r_mean)
    extra = 0.0
    if cfg.use_cayley:
        # 4 FMAs = 8 FLOPs per pair + bottleneck d -> r -> d/2
        extra += core_eff * (4.0 * d + 2.0 * (d * cfg.cayley_rank + cfg.cayley_rank * (d * 0.5)))
    if cfg.use_darcy:
        # Hillis-Steele log2(T) scan steps: ~3 FLOPs/step/dim
        extra += core_eff * (3.0 * d * math.ceil(math.log2(max(2, seq_len))))
    if cfg.use_bingham:
        # Poloidal L2 norm + radial scale (~3 FLOPs per poloidal dim)
        extra += core_eff * (3.0 * float(cfg.k_poloidal))
    if cfg.use_act_plumes:
        # Buoyancy score + 4-way soft/hard select
        extra += 2.0 * d + 8.0 * d
    if cfg.use_mtp_draft:
        # K_draft low-rank adapters (2 * d * d_draft each); surface draft head amortization
        extra += float(cfg.mtp_k) * 4.0 * d * float(cfg.mtp_d_draft)

    lm_head = 2.0 * d * float(cfg.vocab_size)
    flops_per_tok = base_flops + extra + lm_head
    flops_per_problem_equiv = flops_per_tok * float(cfg.unlooped_cot_token_mult)
    return {
        "l_phys": float(cfg.n_pre + cfg.n_core + cfg.n_post),
        "l_eff": l_eff,
        "flops_per_token": flops_per_tok,
        "flops_per_problem_equiv": flops_per_problem_equiv,
    }


def _select_dff_for_target_params(
    base_kwargs: Dict[str, Any],
    target_params: int,
    step: int = 16,
) -> int:
    """Solve analytically for multiple-of-16 d_ff matching target_params tightly (zero trial bloat)."""
    d = int(base_kwargs["d_model"])
    n_phys = int(base_kwargs["n_pre"]) + int(base_kwargs["n_core"]) + int(base_kwargs["n_post"])
    # Instantiate once with d_ff=64 to get exact non-MLP parameter overhead.
    probe = S110ModelConfig(**{**base_kwargs, "d_ff": 64})
    probe_params = count_parameters(GeosphereNetLM(probe, seed=1))["total_params"]
    mlp_at_64 = n_phys * 3 * d * 64
    fixed_params = probe_params - mlp_at_64
    per_dff = n_phys * 3 * d
    raw_dff = max(step, int(round((target_params - fixed_params) / float(per_dff))))
    snapped = max(step, int(round(raw_dff / float(step))) * step)
    return snapped


def build_s110_arm_configs(
    scale: str = "full15m",
    target_params: int = 15_000_000,
) -> Dict[str, S110ModelConfig]:
    """Build complete Stage-1 (H10a), Stage-2 (H10b + LOSO), and N0 baseline matrix at matched parity.

    scale:
      - "full15m": Production RTX 3080 15M (+/- 0.5%) parity matrix (d_model=384 looped, d_model=320 unlooped).
      - "tiny":    Fast CPU pre-flight / smoke matrix (d_model=64, ~0.35M params) with identical topology.
    """
    if scale == "full15m":
        d_loop, h_loop, cay_r, d_draft = 384, 6, 16, 48
        d_unloop, h_unloop = 320, 8
        t_params = int(target_params)
    elif scale == "tiny":
        d_loop, h_loop, cay_r, d_draft = 64, 4, 8, 16
        d_unloop, h_unloop = 48, 4
        t_params = 420_000
    else:
        raise S110ConfigError(f"Unknown scale: {scale!r} (expected 'full15m' or 'tiny')")

    common_loop = dict(
        vocab_size=VOCAB_SIZE_BYTE,
        d_model=d_loop,
        n_heads=h_loop,
        n_pre=2,
        n_core=4,
        n_post=2,
        r_mean=2.0,
        r_max=4,
        cayley_rank=cay_r,
        k_poloidal=d_loop // 2,
        bingham_yield=0.5,
        bingham_tau=0.0,
        mtp_k=8,
        mtp_d_draft=d_draft,
        use_airlock_clamp=True,
    )

    specs: List[Tuple[str, str, Dict[str, Any]]] = [
        # --- Stage 1 (H10a): Single-Shell Isolation & Pruning Gate ---
        ("H10a_Baseline_Loop", "H10a_single_shell", dict(**common_loop)),
        ("H10a_Shell1_Cayley2x2", "H10a_single_shell", dict(**common_loop, use_cayley=True)),
        ("H10a_Shell2_BinghamProx", "H10a_single_shell", dict(**common_loop, use_bingham=True)),
        ("H10a_Shell3_DarcyEMA", "H10a_single_shell", dict(**common_loop, use_darcy=True)),
        ("H10a_Shell4_ACTPlume_MTP8", "H10a_single_shell", dict(**common_loop, use_act_plumes=True, use_mtp_draft=True)),
        # --- Stage 2 (H10b): Coupled Geosphere-Net + Leave-One-Shell-Out (LOSO) Ablation Matrix ---
        (
            "H10b_Geosphere_Full",
            "H10b_coupled_loso",
            dict(**common_loop, use_cayley=True, use_bingham=True, use_darcy=True, use_act_plumes=True, use_mtp_draft=True),
        ),
        (
            "H10b_LOSO_NoCayley",
            "H10b_coupled_loso",
            dict(**common_loop, use_cayley=False, use_bingham=True, use_darcy=True, use_act_plumes=True, use_mtp_draft=True),
        ),
        (
            "H10b_LOSO_NoBingham",
            "H10b_coupled_loso",
            dict(**common_loop, use_cayley=True, use_bingham=False, use_darcy=True, use_act_plumes=True, use_mtp_draft=True),
        ),
        (
            "H10b_LOSO_NoDarcyEMA",
            "H10b_coupled_loso",
            dict(**common_loop, use_cayley=True, use_bingham=True, use_darcy=False, use_act_plumes=True, use_mtp_draft=True),
        ),
        (
            "H10b_LOSO_NoACTDraft",
            "H10b_coupled_loso",
            dict(**common_loop, use_cayley=True, use_bingham=True, use_darcy=True, use_act_plumes=False, use_mtp_draft=False),
        ),
        # --- N0 External Baselines ---
        ("N0_nGPT_Loop_15M", "baseline_anchor", {**common_loop, "ngpt_mode": True}),
        ("N0_Monolithic_Loop_15M", "baseline_anchor", {**common_loop, "use_airlock_clamp": False}),
        (
            "N0_English_CoT_15M",
            "baseline_anchor",
            dict(
                vocab_size=VOCAB_SIZE_BYTE,
                d_model=d_unloop,
                n_heads=h_unloop,
                n_pre=2,
                n_core=8,
                n_post=2,
                r_mean=1.0,
                r_max=4,
                k_poloidal=d_unloop // 2,
                use_airlock_clamp=False,
                unlooped_cot_token_mult=1.40,  # Explicit CoT token budget parity vs looped core
            ),
        ),
        (
            "N0_nGPT_Unlooped_15M",
            "baseline_anchor",
            dict(
                vocab_size=VOCAB_SIZE_BYTE,
                d_model=d_unloop,
                n_heads=h_unloop,
                n_pre=2,
                n_core=8,
                n_post=2,
                r_mean=1.0,
                r_max=4,
                k_poloidal=d_unloop // 2,
                ngpt_mode=True,
                use_airlock_clamp=False,
                unlooped_cot_token_mult=1.40,
            ),
        ),
    ]

    out: Dict[str, S110ModelConfig] = {}
    for arm_name, stage, kwargs in specs:
        full_kw = {"arm_name": arm_name, "stage": stage, **kwargs}
        dff = _select_dff_for_target_params(full_kw, t_params, step=16 if scale == "full15m" else 8)
        cfg = S110ModelConfig(**full_kw, d_ff=dff)
        cfg.validate()
        out[arm_name] = cfg
    return out
