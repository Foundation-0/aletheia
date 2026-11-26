#!/usr/bin/env python3
"""Track S106 GPU/CPU Mathematical Quantization Operators.

Implements exact-bpw zero-CS-08-leakage operators for PREREG-SPHERE-PI-FORCES-V1:
  - SphereMap (Sinkhorn-L2 dual row/col FP16 scaling + orthogonal block Hadamard H_64)
  - Adversarial Null-Shuffle SphereMap control (destroys quadrupole structure)
  - Exact Conway-Sloane E_8 (S^7) & A_16 (S^15) nearest-lattice decoders with live syndrome checks
  - Exact 9-step bisection radial pullback guaranteeing 0 out-of-ball blocks
  - siliquant-matched per-128 (16b scale) and per-32 (8b scale) A_16 / E_8 ball baselines
  - Global-scale SphereMap balls: E_8 (S^7), A_16 (S^15), A_16^8 (S^127)
  - H3a: Power-gamma radial sphere warp + universal Gaussian integer shell LUT rho[m] (0 extra bpw)
  - H3b: EM/Hodge transverse-weighted lattice selection (lambda_perp * ||d_perp||^2 + ||d_par||^2)
  - H2a: Closed-form LUT-free Denominator-pi EQ(S^3) (Leopardi-8c & Hopf-Hex-4b) and EQ(S^7) (Haar-R7)
         vs Numerator-pi angle grids vs trained spherical k-means
  - H3c: Gravity-only vs Gravity+Coulomb (1/r) vs Gravity+Yukawa (exp(-mu*r)/r) S^3/S^7 codebooks
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

import numpy as np
import torch

PREREG_SHA256 = "ac3e62116bc4841320d2c713787c23568beed1ae738bf9b284b7f0c2a118d72a"

# Exact integer theta-series ball bounds verified via exact BigInt polynomial powers
# Per-block siliquant#85 matched-bpw bounds:
#   g=128 (16b FP16 scale = 0.125 bpw): payload <= 1.875 / 2.875 / 4.375 -> total 2.000 / 3.000 / 4.500 bpw
#   g=32  ( 8b scale      = 0.250 bpw): payload <= 1.750 / 2.750 / 4.250 -> total 2.000 / 3.000 / 4.500 bpw
PER_BLOCK_BOUNDS: dict[str, dict[int, dict[str, tuple[int, float]]]] = {
    "2.0": {
        128: {"A16": (162, 1.87487), "E8": (104, 1.86973)},
        32: {"A16": (36, 1.73413), "E8": (22, 1.70131)},
    },
    "3.0": {
        128: {"A16": (650, 2.87403), "E8": (420, 2.87208)},
        32: {"A16": (150, 2.74948), "E8": (96, 2.74270)},
    },
    "4.5": {
        128: {"A16": (5212, 4.37473), "E8": (3380, 4.37450)},
        32: {"A16": (1206, 4.24910), "E8": (782, 4.24850)},
    },
}

# Global-scale SphereMap ball bounds strictly leaving >= 0.030 bpw headroom for FP16 row/col radii
# so total exact_bpw <= target_bpw on every held-out model (zero CS-08 advantage!).
GLOBAL_BALL_BOUNDS: dict[str, dict[str, tuple[int, float]]] = {
    "2.0": {
        "E8": (10, 1.97446),       # 8D,  M=5 shells
        "A16": (26, 1.93000),      # 16D, M=13 shells
        "A16_128": (184, 1.96626), # 128D product ball A_16^8
    },
    "3.0": {
        "E8": (42, 2.96510),       # 8D,  M=21 shells (strictly <= 3.000 with SphereMap!)
        "A16": (112, 2.96787),     # 16D, M=56 shells
        "A16_128": (742, 2.96938), # 128D product ball A_16^8 (strictly <= 3.000 with SphereMap!)
        "A16_128_B368": (650, 2.87403),  # Identical B=368 payload as per-128 -> ~2.90 bpw (-0.10 bpw!)
    },
    "4.5": {
        "E8": (344, 4.46799),      # 8D,  M=172 shells
        "A16": (906, 4.46943),     # 16D, M=453 shells
        "A16_128": (5946, 4.46976),# 128D product ball A_16^8
    },
}

_HADAMARD_CACHE: dict[tuple[int, str, torch.dtype], torch.Tensor] = {}


def get_hadamard(n: int, device: torch.device, dtype: torch.dtype = torch.float32) -> torch.Tensor:
    key = (n, str(device), dtype)
    if key not in _HADAMARD_CACHE:
        h = torch.tensor([[1.0]], device=device, dtype=dtype)
        while h.shape[0] < n:
            h = torch.cat([torch.cat([h, h], dim=1), torch.cat([h, -h], dim=1)], dim=0)
        _HADAMARD_CACHE[key] = h / math.sqrt(float(n))
    return _HADAMARD_CACHE[key]


def apply_block_hadamard(w: torch.Tensor, block_size: int = 64) -> torch.Tensor:
    m, n = w.shape
    h = get_hadamard(block_size, w.device, w.dtype)
    return (w.reshape(m, n // block_size, block_size) @ h).reshape(m, n)


def ellipsoid_whiten_sinkhorn(
    w: torch.Tensor, n_iter: int = 8
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, float]:
    """Sinkhorn-L2 alternating RMS row/col whitening with honest FP16 scale quantization."""
    m, n = w.shape
    dr = torch.ones(m, device=w.device, dtype=torch.float32)
    dc = torch.ones(n, device=w.device, dtype=torch.float32)
    x = w.to(torch.float32)
    for _ in range(n_iter):
        r_rms = torch.sqrt(torch.mean(x * x, dim=1)).clamp_min(1e-8)
        x = x / r_rms.unsqueeze(1)
        dr = dr * r_rms
        c_rms = torch.sqrt(torch.mean(x * x, dim=0)).clamp_min(1e-8)
        x = x / c_rms.unsqueeze(0)
        dc = dc * c_rms
    dr_q = dr.to(torch.float16).to(torch.float32).clamp_min(1e-8)
    dc_q = dc.to(torch.float16).to(torch.float32).clamp_min(1e-8)
    w_ell = w.to(torch.float32) / (dr_q.unsqueeze(1) * dc_q.unsqueeze(0))
    # Count 16 bits per row + 16 bits per col + 16 bits for global RMS scalar
    extra_bpw = 16.0 * float(m + n + 1) / float(m * n)
    return w_ell, dr_q, dc_q, extra_bpw


def spheremap_forward(
    w: torch.Tensor, block_size: int = 64, n_iter: int = 8
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, float, float, float]:
    """Apply SphereMap = Sinkhorn dual_scale + H_64. Returns (W_sp, dr, dc, extra_bpw, k_raw, k_post)."""
    wf = w.to(torch.float32)
    m2_raw = float(torch.mean(wf * wf).clamp_min(1e-30).item())
    m4_raw = float(torch.mean(wf ** 4).item())
    k_raw = m4_raw / (m2_raw * m2_raw)
    w_ell, dr, dc, extra_bpw = ellipsoid_whiten_sinkhorn(wf, n_iter=n_iter)
    w_sp = apply_block_hadamard(w_ell, block_size=block_size)
    m2_post = float(torch.mean(w_sp * w_sp).clamp_min(1e-30).item())
    m4_post = float(torch.mean(w_sp ** 4).item())
    k_post = m4_post / (m2_post * m2_post)
    return w_sp, dr, dc, extra_bpw, k_raw, k_post


def spheremap_inverse(
    w_sp_q: torch.Tensor, dr: torch.Tensor, dc: torch.Tensor, block_size: int = 64
) -> torch.Tensor:
    return apply_block_hadamard(w_sp_q, block_size=block_size) * dr.unsqueeze(1) * dc.unsqueeze(0)


def make_null_shuffle_perm(shape: tuple[int, int], seed_tag: str, device: torch.device) -> torch.Tensor:
    h = int(hashlib.sha256(seed_tag.encode("utf-8")).hexdigest()[:8], 16)
    gen = torch.Generator(device="cpu").manual_seed(h)
    return torch.randperm(shape[0] * shape[1], generator=gen).to(device)


# ---------------------------------------------------------------------------
# Exact Lattice Nearest-Point Decoders with Live Syndrome/Parity Checks
# ---------------------------------------------------------------------------
def e8_closest(u8: torch.Tensor, check_syn: bool = True) -> tuple[torch.Tensor, int]:
    """Exact Conway-Sloane nearest point in E_8 = D_8 U (D_8 + (1/2)^8)."""
    f1 = torch.round(u8)
    odd1 = (torch.sum(f1.to(torch.int64), dim=1) & 1) != 0
    if odd1.any():
        diff1 = u8 - f1
        idx1 = diff1.abs().argmax(dim=1)
        step1 = torch.where(diff1.gather(1, idx1.unsqueeze(1)).squeeze(1) >= 0, 1.0, -1.0)
        f1 = f1.clone()
        rows1 = torch.nonzero(odd1, as_tuple=False).squeeze(1)
        f1[rows1, idx1[rows1]] += step1[rows1]

    u_s = u8 - 0.5
    f2i = torch.round(u_s)
    odd2 = (torch.sum(f2i.to(torch.int64), dim=1) & 1) != 0
    if odd2.any():
        diff2 = u_s - f2i
        idx2 = diff2.abs().argmax(dim=1)
        step2 = torch.where(diff2.gather(1, idx2.unsqueeze(1)).squeeze(1) >= 0, 1.0, -1.0)
        f2i = f2i.clone()
        rows2 = torch.nonzero(odd2, as_tuple=False).squeeze(1)
        f2i[rows2, idx2[rows2]] += step2[rows2]
    f2 = f2i + 0.5

    d1 = ((u8 - f1) ** 2).sum(dim=1)
    d2 = ((u8 - f2) ** 2).sum(dim=1)
    out = torch.where((d1 <= d2).unsqueeze(1), f1, f2)
    if not check_syn:
        return out, 0

    doubled = torch.round(out * 2.0).to(torch.int64)
    non_half = ((out * 2.0 - doubled.to(out.dtype)).abs() > 1e-4).any(dim=1)
    par0 = doubled[:, 0:1] & 1
    mixed_par = ((doubled & 1) != par0).any(dim=1)
    bad_sum = (doubled.sum(dim=1) & 3) != 0
    errs = int((non_half | mixed_par | bad_sum).sum().item())
    return out, errs


def a16_closest(u16: torch.Tensor, check_syn: bool = True) -> tuple[torch.Tensor, int]:
    """Exact nearest lattice point in A_16 = 2*Z^16 + C_{[16,11,4]} with live syndrome check."""
    e_val = 2.0 * torch.round(u16 * 0.5)
    o_val = 2.0 * torch.floor(u16 * 0.5) + 1.0
    de = (u16 - e_val) ** 2
    do = (u16 - o_val) ** 2
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
    out_b = bits.clone() if check_syn else None

    odd_m = p0 == 1
    if odd_m.any():
        ro = torch.nonzero(odd_m, as_tuple=False).squeeze(1)
        co = syn[ro].to(torch.int64)
        out[ro, co] = alt[ro, co]
        if out_b is not None:
            out_b[ro, co] ^= 1

    ev_m = (p0 == 0) & (syn != 0)
    if ev_m.any():
        re_i = torch.nonzero(ev_m, as_tuple=False).squeeze(1)
        se = syn[re_i].to(torch.int64)
        jg = torch.arange(16, device=u16.device, dtype=torch.int64).unsqueeze(0)
        pg = jg ^ se.unsqueeze(1)
        pc = fc[re_i] + fc[re_i].gather(1, pg)
        bj = pc.argmin(dim=1)
        bp = bj ^ se
        out[re_i, bj] = alt[re_i, bj]
        out[re_i, bp] = alt[re_i, bp]
        if out_b is not None:
            out_b[re_i, bj] ^= 1
            out_b[re_i, bp] ^= 1

    if out_b is None:
        return out, 0

    vp0 = out_b.sum(dim=1) & 1
    vs0 = out_b[:, 1::2].sum(dim=1) & 1
    vs1 = (out_b[:, 2::4].sum(dim=1) + out_b[:, 3::4].sum(dim=1)) & 1
    vs2 = (out_b[:, 4:8].sum(dim=1) + out_b[:, 12:16].sum(dim=1)) & 1
    vs3 = out_b[:, 8:16].sum(dim=1) & 1
    errs = int(((vp0 | vs0 | vs1 | vs2 | vs3) != 0).sum().item())
    return out, errs


def snap_in_ball(
    y: torch.Tensor,
    lattice: str,
    r2_max: float,
    group_dim: int | None = None,
    bisect_steps: int = 10,
) -> tuple[torch.Tensor, int, int]:
    """Snap y to nearest lattice point in ball ||q||^2 <= r2_max via exact bisection pullback."""
    blk_dim = 16 if lattice == "A16" else 8
    g_dim = blk_dim if group_dim is None else group_dim
    yg = y.reshape(-1, g_dim)
    fn = a16_closest if lattice == "A16" else e8_closest

    q_flat, syn = fn(yg.reshape(-1, blk_dim), check_syn=True)
    q = q_flat.reshape(-1, g_dim)
    n2 = (q * q).sum(dim=1)
    over = n2 > r2_max + 0.25
    if over.any():
        xo = yg[over]
        lo = torch.zeros(xo.shape[0], device=y.device, dtype=y.dtype)
        hi = torch.ones(xo.shape[0], device=y.device, dtype=y.dtype)
        for _ in range(bisect_steps):
            mid = 0.5 * (lo + hi)
            qt, _ = fn((xo * mid.unsqueeze(1)).reshape(-1, blk_dim), check_syn=False)
            qt = qt.reshape(-1, g_dim)
            ok = (qt * qt).sum(dim=1) <= r2_max + 0.25
            lo = torch.where(ok, mid, lo)
            hi = torch.where(ok, hi, mid)
            del qt, ok
        qf, syn2 = fn((xo * lo.unsqueeze(1)).reshape(-1, blk_dim), check_syn=True)
        q = q.clone()
        q[over] = qf.reshape(-1, g_dim)
        syn += syn2
    oob = int(((q * q).sum(dim=1) > r2_max + 0.25).sum().item())
    return q.reshape(y.shape), syn, oob


# ---------------------------------------------------------------------------
# Per-Block siliquant Baseline (g=128 FP16 scale / g=32 FP8/int8 scale)
# ---------------------------------------------------------------------------
def quant_per_block_ball_matrix(
    w_f32: torch.Tensor,
    bpw_key: str,
    lattice: str,
    group_size: int,
    block_h: int = 0,
    row_chunk: int = 512,
) -> tuple[torch.Tensor, dict[str, Any]]:
    """Exact siliquant#85 per-group ball quantizer with honest scale-bit accounting."""
    r2_max, payload_bpw = PER_BLOCK_BOUNDS[bpw_key][group_size][lattice]
    scale_bits = 16 if group_size == 128 else 8
    exact_bpw = payload_bpw + float(scale_bits) / float(group_size)
    blk_dim = 16 if lattice == "A16" else 8
    r_ball = math.sqrt(float(r2_max))
    margin = math.sqrt(group_size / 4.0 + 1.5 * (group_size / blk_dim))
    fn = a16_closest if lattice == "A16" else e8_closest

    m = w_f32.shape[0]
    parts: list[torch.Tensor] = []
    syn_tot = 0
    oob_tot = 0

    for r0 in range(0, m, row_chunk):
        r1 = min(r0 + row_chunk, m)
        xc = w_f32[r0:r1].clone()
        if block_h > 0:
            xc = apply_block_hadamard(xc, block_size=block_h)
        xg = xc.reshape(-1, group_size)
        gn = torch.sqrt((xg * xg).sum(dim=1)).clamp_min(1e-30)
        lo = gn / (r_ball + margin) * 0.99
        hi = gn / max(r_ball - margin, 0.05 * r_ball) * 1.01
        for _ in range(12):
            mid = torch.sqrt(lo * hi)
            y_t, _ = fn((xg / mid.unsqueeze(1)).reshape(-1, blk_dim), check_syn=False)
            y_t = y_t.reshape(-1, group_size)
            ok = (y_t * y_t).sum(dim=1) <= r2_max + 0.25
            hi = torch.where(ok, mid, hi)
            lo = torch.where(ok, lo, mid)
            del y_t, ok
        scaled = xg / hi.unsqueeze(1)
        yf, syn_c, oob_c = snap_in_ball(scaled, lattice, float(r2_max), group_dim=group_size, bisect_steps=12)
        syn_tot += syn_c
        oob_tot += oob_c
        if scale_bits == 16:
            sc_q = hi.to(torch.float16).to(torch.float32)
        else:
            # Honest 8-bit log-uniform positive scale per g=32 block (E4M3-equivalent dynamic range)
            log_s = torch.log2(hi.clamp_min(1e-12))
            lmin = float(log_s.min().item())
            lmax = float(log_s.max().item())
            span = max(lmax - lmin, 1e-6)
            q8 = torch.round((log_s - lmin) / span * 255.0).clamp(0.0, 255.0)
            sc_q = torch.pow(2.0, lmin + q8 * (span / 255.0))
        wq_c = (yf * sc_q.unsqueeze(1)).reshape(xc.shape)
        if block_h > 0:
            wq_c = apply_block_hadamard(wq_c, block_size=block_h)
        parts.append(wq_c)

    wq = torch.cat(parts, dim=0)
    return wq, {
        "exact_bpw": exact_bpw,
        "payload_bpw": payload_bpw,
        "scale_bpw": float(scale_bits) / float(group_size),
        "syndrome_errors": syn_tot,
        "oob_groups": oob_tot,
    }


# ---------------------------------------------------------------------------
# Global-Scale Lattice Ball Quantizer (Linear, H3a Radial Warp + Shell LUT, H3b Hodge)
# ---------------------------------------------------------------------------
def quant_global_ball_matrix(
    w_sp: torch.Tensor,
    lattice_key: str,
    bpw_key: str,
    *,
    gamma: float = 1.0,
    scale_s: float | None = None,
    shell_lut: torch.Tensor | None = None,
    hodge_lambda_perp: float = 1.0,
    hodge_alphas: tuple[float, ...] = (0.86, 0.93, 1.00, 1.06, 1.12),
    extra_bpw: float = 0.0,
    row_chunk: int = 1024,
) -> tuple[torch.Tensor, dict[str, Any]]:
    """Quantize a SphereMap-normalized tensor with E_8, A_16, or A_16^8 (128D) ball."""
    r2_max, payload_bpw = GLOBAL_BALL_BOUNDS[bpw_key][lattice_key]
    if lattice_key == "E8":
        lat, blk_dim, g_dim = "E8", 8, 8
    elif lattice_key == "A16":
        lat, blk_dim, g_dim = "A16", 16, 16
    elif lattice_key in ("A16_128", "A16_128_B368"):
        lat, blk_dim, g_dim = "A16", 16, 128
    else:
        raise ValueError(f"Unknown lattice_key: {lattice_key}")

    orig_shape = w_sp.shape
    rms = torch.sqrt(torch.mean(w_sp * w_sp)).clamp_min(1e-12)
    rms_q = rms.to(torch.float16).to(torch.float32).clamp_min(1e-12)
    z_all = w_sp / rms_q

    # Universal or single-global-scalar scale selection (counted in SphereMap extra_bpw!)
    if scale_s is None:
        # Closed-form optimal universal Gaussian scale for linear ball (or light 9-pt check on 8k slice)
        s_nom = math.sqrt(float(r2_max) / float(g_dim))
        sub = z_all.reshape(-1, g_dim)[: min(8192, z_all.numel() // g_dim)]
        best_s = s_nom
        best_mse = 1e30
        for mult in (0.68, 0.76, 0.84, 0.90, 0.96, 1.02, 1.08, 1.15):
            sc = s_nom * mult
            qt, _, _ = snap_in_ball(sub * sc, lat, float(r2_max), group_dim=g_dim, bisect_steps=8)
            mse = float(torch.mean((sub - qt / sc) ** 2).item())
            if mse < best_mse:
                best_mse = mse
                best_s = sc
        use_s = best_s
    else:
        use_s = float(scale_s)

    lut_dev = shell_lut.to(device=w_sp.device, dtype=torch.float32) if shell_lut is not None else None
    max_shell = (lut_dev.shape[0] - 1) if lut_dev is not None else 0

    m = w_sp.shape[0]
    parts: list[torch.Tensor] = []
    syn_tot = 0
    oob_tot = 0
    rad_err_sum = 0.0
    tot_err_sum = 0.0

    eff_chunk = min(row_chunk, 512) if hodge_lambda_perp > 1.0 + 1e-9 else row_chunk
    for r0 in range(0, m, eff_chunk):
        r1 = min(r0 + eff_chunk, m)
        zc = z_all[r0:r1].reshape(-1, g_dim)
        if abs(gamma - 1.0) > 1e-9:
            rn = torch.norm(zc, dim=1, keepdim=True).clamp_min(1e-12)
            yc = zc * (torch.pow(rn, gamma - 1.0) * use_s)
        else:
            yc = zc * use_s

        if hodge_lambda_perp > 1.0 + 1e-9:
            # EM/Hodge selection: minimize ||delta_par||^2 + lambda_perp * ||delta_perp||^2
            zn = torch.norm(zc, dim=1, keepdim=True).clamp_min(1e-12)
            zhat = zc / zn
            best_q = None
            best_cost = None
            for alpha in hodge_alphas:
                qa, syn_a, oob_a = snap_in_ball(yc * alpha, lat, float(r2_max), group_dim=g_dim, bisect_steps=8)
                syn_tot += syn_a
                oob_tot += oob_a
                if lut_dev is not None:
                    m_idx = torch.round((qa * qa).sum(dim=1) * 0.5).long().clamp(0, max_shell)
                    re_a = qa * lut_dev[m_idx].unsqueeze(1)
                else:
                    re_a = qa / use_s
                delta = re_a - zc
                d_par = (delta * zhat).sum(dim=1)
                d_sq = (delta * delta).sum(dim=1)
                d_perp_sq = (d_sq - d_par * d_par).clamp_min(0.0)
                cost = d_par * d_par + hodge_lambda_perp * d_perp_sq
                if best_cost is None:
                    best_cost = cost
                    best_q = re_a
                else:
                    better = cost < best_cost
                    best_cost = torch.where(better, cost, best_cost)
                    best_q = torch.where(better.unsqueeze(1), re_a, best_q)
                del qa, re_a, delta, d_par, d_sq, d_perp_sq, cost
            rec = best_q
            del best_cost, zn, zhat
        else:
            q, syn_c, oob_c = snap_in_ball(yc, lat, float(r2_max), group_dim=g_dim, bisect_steps=10)
            syn_tot += syn_c
            oob_tot += oob_c
            if lut_dev is not None:
                m_idx = torch.round((q * q).sum(dim=1) * 0.5).long().clamp(0, max_shell)
                rec = q * lut_dev[m_idx].unsqueeze(1)
            else:
                rec = q / use_s

        # Measure radial vs transverse error split (Hodge diagnostic)
        err = rec - zc
        zhat = zc / torch.norm(zc, dim=1, keepdim=True).clamp_min(1e-12)
        ep = (err * zhat).sum(dim=1)
        rad_err_sum += float((ep * ep).sum().item())
        tot_err_sum += float((err * err).sum().item())
        parts.append(rec.reshape(r1 - r0, orig_shape[1]) * rms_q)

    wq = torch.cat(parts, dim=0)
    return wq, {
        "exact_bpw": payload_bpw + extra_bpw,
        "payload_bpw": payload_bpw,
        "scale_bpw": extra_bpw,
        "syndrome_errors": syn_tot,
        "oob_groups": oob_tot,
        "rad_err_frac": rad_err_sum / max(tot_err_sum, 1e-30),
    }


# ---------------------------------------------------------------------------
# 1D Lloyd-Max + Closed-Form Denominator-pi EQ(S^3), EQ(S^7) & Force Codebooks
# ---------------------------------------------------------------------------
def fit_lloyd_max_1d(samples: np.ndarray, n_levels: int, n_iter: int = 40) -> list[float]:
    qs = np.linspace(0.5 / n_levels, 1.0 - 0.5 / n_levels, n_levels)
    c = np.quantile(samples, qs).astype(np.float64)
    s = np.sort(samples.astype(np.float64))
    for _ in range(n_iter):
        mids = 0.5 * (c[:-1] + c[1:])
        idx = np.searchsorted(s, mids)
        starts = np.concatenate(([0], idx))
        ends = np.concatenate((idx, [len(s)]))
        new_c = c.copy()
        for k in range(n_levels):
            if ends[k] > starts[k]:
                new_c[k] = s[starts[k] : ends[k]].mean()
        if np.max(np.abs(new_c - c)) < 1e-10:
            break
        c = new_c
    return [float(v) for v in c.tolist()]


def quant_cartesian_lloyd_max_matrix(
    w_sp: torch.Tensor,
    cb_1d: torch.Tensor,
    bits: int,
    extra_bpw: float = 0.0,
) -> tuple[torch.Tensor, dict[str, Any]]:
    rms = torch.sqrt(torch.mean(w_sp * w_sp)).clamp_min(1e-12)
    rms_q = rms.to(torch.float16).to(torch.float32).clamp_min(1e-12)
    z = w_sp / rms_q
    cb = cb_1d.to(device=w_sp.device, dtype=torch.float32)
    mids = 0.5 * (cb[:-1] + cb[1:])
    idx = torch.bucketize(z, mids)
    wq = cb[idx] * rms_q
    return wq, {
        "exact_bpw": float(bits) + extra_bpw,
        "payload_bpw": float(bits),
        "scale_bpw": extra_bpw,
        "syndrome_errors": 0,
        "oob_groups": 0,
    }


def build_numerator_pi_s3(n_psi: int = 4, n_th: int = 8, n_phi: int = 8) -> torch.Tensor:
    """Numerator-pi uniform angle grid on S^3 (K = n_psi * n_th * n_phi = 256)."""
    pts: list[list[float]] = []
    for i in range(n_psi):
        psi = (i + 0.5) * math.pi / float(n_psi)
        for j in range(n_th):
            th = (j + 0.5) * math.pi / float(n_th)
            for k in range(n_phi):
                ph = -math.pi + (k + 0.5) * 2.0 * math.pi / float(n_phi)
                pts.append([
                    math.cos(psi),
                    math.sin(psi) * math.cos(th),
                    math.sin(psi) * math.sin(th) * math.cos(ph),
                    math.sin(psi) * math.sin(th) * math.sin(ph),
                ])
    c = torch.tensor(pts, dtype=torch.float32)
    return c / torch.norm(c, dim=-1, keepdim=True)


def _inv_s3_cdf(u_val: float) -> float:
    lo, hi = 0.0, math.pi
    for _ in range(52):
        mid = 0.5 * (lo + hi)
        if (mid - math.sin(mid) * math.cos(mid)) / math.pi < u_val:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def build_eq_s3_leopardi(counts: tuple[int, ...] = (2, 20, 44, 62, 62, 44, 20, 2)) -> torch.Tensor:
    """Closed-form LUT-free Denominator-pi Equal-Sphere-Fraction EQ(S^3) via Leopardi + Archimedes S^2."""
    total = sum(counts)
    golden = math.pi * (3.0 - math.sqrt(5.0))
    pts: list[list[float]] = []
    cum = 0
    for r, nk in enumerate(counts):
        u0 = float(cum) / float(total)
        u1 = float(cum + nk) / float(total)
        cum += nk
        psi = _inv_s3_cdf(0.5 * (u0 + u1))
        spsi, cpsi = math.sin(psi), math.cos(psi)
        for j in range(nk):
            z = -1.0 + (2.0 * float(j) + 1.0) / float(nk)
            rad = math.sqrt(max(0.0, 1.0 - z * z))
            phi = (float(j) + 0.5 + float(r) * 0.3819660112501051) * golden
            pts.append([cpsi, spsi * rad * math.cos(phi), spsi * rad * math.sin(phi), spsi * z])
    c = torch.tensor(pts, dtype=torch.float32)
    return c / torch.norm(c, dim=-1, keepdim=True)


def build_eq_s3_hopf_hex(
    bands: tuple[tuple[int, int], ...] = ((16, 3), (10, 8), (8, 10), (3, 16)),
) -> torch.Tensor:
    """Closed-form LUT-free Denominator-pi Hopf-Hex EQ(S^3): exact 1/256 Haar measure, zero trig CDF inverse."""
    total = sum(a * b for a, b in bands)
    pts: list[list[float]] = []
    cum = 0
    for bidx, (n1, n2) in enumerate(bands):
        cnt = n1 * n2
        u0 = float(cum) / float(total)
        u1 = float(cum + cnt) / float(total)
        cum += cnt
        e_r1 = (2.0 / 3.0) * ((1.0 - u0) ** 1.5 - (1.0 - u1) ** 1.5) / (u1 - u0)
        e_r2 = (2.0 / 3.0) * (u1 ** 1.5 - u0 ** 1.5) / (u1 - u0)
        rn = math.hypot(e_r1, e_r2)
        r1, r2 = e_r1 / rn, e_r2 / rn
        o1 = float(bidx) * (math.pi / float(n1)) * 0.5
        for i in range(n1):
            p1 = -math.pi + o1 + (float(i) + 0.5) * (2.0 * math.pi / float(n1))
            stagger = 0.5 if (i % 2 == 1) else 0.0
            for j in range(n2):
                p2 = -math.pi + (float(j) + stagger + 0.25) * (2.0 * math.pi / float(n2))
                pts.append([r1 * math.cos(p1), r1 * math.sin(p1), r2 * math.cos(p2), r2 * math.sin(p2)])
    c = torch.tensor(pts, dtype=torch.float32)
    return c / torch.norm(c, dim=-1, keepdim=True)


def build_eq_s7_haar(k_pts: int = 4096) -> torch.Tensor:
    """Closed-form LUT-free Denominator-pi EQ(S^7) via exact Beta(2,2) inverse cubic + Roberts R_7."""
    phi7 = 1.1127756842787055
    alphas = [pow(1.0 / phi7, k + 1) for k in range(7)]
    pts: list[list[float]] = []
    for idx in range(k_pts):
        u = [((float(idx) + 0.5) * a) % 1.0 for a in alphas]
        v, q1, q2 = u[0], u[1], u[2]
        p = 0.5 - math.cos((math.acos(max(-1.0, min(1.0, 1.0 - 2.0 * v))) + math.pi) / 3.0)
        r0 = math.sqrt(max(0.0, p * q1))
        r1 = math.sqrt(max(0.0, p * (1.0 - q1)))
        r2 = math.sqrt(max(0.0, (1.0 - p) * q2))
        r3 = math.sqrt(max(0.0, (1.0 - p) * (1.0 - q2)))
        t0, t1, t2, t3 = [2.0 * math.pi * u[3 + j] for j in range(4)]
        pts.append([
            r0 * math.cos(t0), r0 * math.sin(t0),
            r1 * math.cos(t1), r1 * math.sin(t1),
            r2 * math.cos(t2), r2 * math.sin(t2),
            r3 * math.cos(t3), r3 * math.sin(t3),
        ])
    c = torch.tensor(pts, dtype=torch.float32)
    return c / torch.norm(c, dim=-1, keepdim=True)


def build_numerator_pi_s7(k_pts: int = 256) -> torch.Tensor:
    """Numerator-pi uniform angle grid on S^7 (2^6 x 4 = 256)."""
    pts: list[list[float]] = []
    for idx in range(k_pts):
        angs: list[float] = []
        tmp = idx
        for _ in range(6):
            b = tmp & 1
            tmp >>= 1
            angs.append((float(b) + 0.5) * math.pi / 2.0)
        ph = -math.pi + (float(tmp) + 0.5) * 2.0 * math.pi / 4.0
        v: list[float] = []
        sprod = 1.0
        for a in angs:
            v.append(sprod * math.cos(a))
            sprod *= math.sin(a)
        v.append(sprod * math.cos(ph))
        v.append(sprod * math.sin(ph))
        pts.append(v)
    c = torch.tensor(pts, dtype=torch.float32)
    return c / torch.norm(c, dim=-1, keepdim=True)


def train_force_spherical_codebook(
    x_unit: torch.Tensor,
    k_pts: int,
    *,
    force_mode: str,
    mu: float = 3.5,
    lam: float = 0.05,
    steps: int = 20,
    seed: int = 42,
) -> torch.Tensor:
    """Train K codewords on S^{d-1} under Gravity-only, Gravity+Coulomb (1/r), or Gravity+Yukawa."""
    gen = torch.Generator(device="cpu").manual_seed(seed)
    d = x_unit.shape[1]
    c = torch.randn((k_pts, d), generator=gen, dtype=torch.float32).to(x_unit.device)
    c = c / torch.norm(c, dim=-1, keepdim=True).clamp_min(1e-12)
    eye_mask = 1.0 - torch.eye(k_pts, device=x_unit.device, dtype=torch.float32)

    for st in range(steps):
        dots = x_unit @ c.T
        assign = torch.argmax(dots, dim=-1)
        c_new = torch.zeros_like(c)
        c_new.index_add_(0, assign, x_unit)
        counts = torch.bincount(assign, minlength=k_pts).float()
        empty = counts == 0
        if empty.any():
            best_dots = dots.gather(1, assign.unsqueeze(-1)).squeeze(-1)
            worst_idx = torch.topk(-best_dots, int(empty.sum().item())).indices
            c_new[empty] = x_unit[worst_idx]
        c_grav = c_new / torch.norm(c_new, dim=-1, keepdim=True).clamp_min(1e-12)

        if force_mode == "gravity_only" or lam <= 0.0:
            c = c_grav
            continue

        diff = c_grav.unsqueeze(1) - c_grav.unsqueeze(0)
        dist = torch.sqrt(torch.sum(diff * diff, dim=-1) + 1e-6)
        if force_mode == "coulomb":
            # Unscreened 1/r potential -> force magnitude 1/r^2
            fmag = (1.0 / (dist * dist + 1e-4)) * eye_mask
        elif force_mode == "yukawa":
            # Screened Yukawa exp(-mu*r)/r -> force exp(-mu*r)*(mu*r + 1)/r^2
            fmag = (torch.exp(-mu * dist) * (mu * dist + 1.0) / (dist * dist + 1e-4)) * eye_mask
        else:
            raise ValueError(f"Unknown force_mode: {force_mode}")
        force = torch.sum(diff * (fmag / dist).unsqueeze(-1), dim=1)
        eta = lam * (1.0 - 0.7 * float(st) / float(max(1, steps - 1)))
        c = c_grav + eta * force
        c = c / torch.norm(c, dim=-1, keepdim=True).clamp_min(1e-12)
    return c


def quant_spherical_codebook_matrix(
    w_sp: torch.Tensor,
    codebook_unit: torch.Tensor,
    gain_cb: torch.Tensor,
    *,
    rad_bits: int,
    extra_bpw: float = 0.0,
    codebook_stored_bytes: int = 0,
    total_model_weights: int = 1,
    chunk_vecs: int = 65536,
) -> tuple[torch.Tensor, dict[str, Any]]:
    """Quantize w_sp in blocks of d = codebook_unit.shape[1] with unit direction + rad_bits gain."""
    orig_shape = w_sp.shape
    k_pts, d = codebook_unit.shape
    rms = torch.sqrt(torch.mean(w_sp * w_sp)).clamp_min(1e-12)
    rms_q = rms.to(torch.float16).to(torch.float32).clamp_min(1e-12)
    z = (w_sp / rms_q).reshape(-1, d)

    cb_u = codebook_unit.to(device=w_sp.device, dtype=torch.float32)
    cb_g = gain_cb.to(device=w_sp.device, dtype=torch.float32)
    mids = 0.5 * (cb_g[:-1] + cb_g[1:]) if cb_g.numel() > 1 else None

    out = torch.empty_like(z)
    n_vecs = z.shape[0]
    for i0 in range(0, n_vecs, chunk_vecs):
        i1 = min(i0 + chunk_vecs, n_vecs)
        zc = z[i0:i1]
        dots = zc @ cb_u.T
        g, idx = torch.max(dots, dim=-1)
        if mids is None:
            gq = cb_g[0]
            out[i0:i1] = cb_u[idx] * gq
        else:
            gq = cb_g[torch.bucketize(g, mids)]
            out[i0:i1] = cb_u[idx] * gq.unsqueeze(-1)

    payload_bpw = (math.log2(float(k_pts)) + float(rad_bits)) / float(d)
    lut_amort_bpw = float(codebook_stored_bytes * 8) / float(max(total_model_weights, 1))
    return out.reshape(orig_shape) * rms_q, {
        "exact_bpw": payload_bpw + extra_bpw + lut_amort_bpw,
        "payload_bpw": payload_bpw,
        "scale_bpw": extra_bpw,
        "lut_amort_bpw": lut_amort_bpw,
        "codebook_stored_bytes": codebook_stored_bytes,
        "syndrome_errors": 0,
        "oob_groups": 0,
    }


def fit_universal_radial_warp_lut(
    lattice: str,
    r2_max: int,
    gamma: float,
    device: torch.device,
    n_samples: int = 65536,
    seed: int = 20261125,
) -> tuple[float, list[float], float]:
    """Fit universal Gaussian scale s and integer shell LUT rho[m] STRICTLY on synthetic N(0,1)."""
    d = 16 if lattice == "A16" else 8
    rng = np.random.default_rng(seed)
    zg = torch.tensor(rng.standard_normal((n_samples, d)), dtype=torch.float32, device=device)
    rn = torch.norm(zg, dim=1, keepdim=True).clamp_min(1e-12)
    z_warped = zg * torch.pow(rn, gamma - 1.0) if abs(gamma - 1.0) > 1e-9 else zg
    r_warped_rms = float(torch.sqrt(torch.mean((z_warped * z_warped).sum(dim=1))).item())
    s_nom = math.sqrt(float(r2_max)) / max(r_warped_rms, 1e-12)

    m_max = r2_max // 2
    best_s = s_nom
    best_mse = 1e30
    best_lut: list[float] = [0.0] * (m_max + 1)

    for mult in np.linspace(0.65, 1.35, 19):
        sc = s_nom * float(mult)
        q, syn, oob = snap_in_ball(z_warped * sc, lattice, float(r2_max), group_dim=d, bisect_steps=10)
        if syn != 0 or oob != 0:
            continue
        m_idx = torch.round((q * q).sum(dim=1) * 0.5).long().clamp(0, m_max)
        lut = torch.zeros(m_max + 1, device=device, dtype=torch.float32)
        for m_val in range(1, m_max + 1):
            mask = m_idx == m_val
            cnt = int(mask.sum().item())
            if cnt >= 8:
                num = float(torch.sum(zg[mask] * q[mask]).item())
                den = float(torch.sum(q[mask] * q[mask]).item())
                lut[m_val] = num / max(den, 1e-12)
            else:
                # Analytic inverse power law fallback: ||y|| = s * r^gamma -> r = (sqrt(2m)/s)^(1/gamma)
                r_q = math.sqrt(2.0 * float(m_val))
                r_est = pow(r_q / max(sc, 1e-12), 1.0 / gamma)
                lut[m_val] = r_est / max(r_q, 1e-12)
        rec = q * lut[m_idx].unsqueeze(1)
        mse = float(torch.mean((zg - rec) ** 2).item())
        if mse < best_mse:
            best_mse = mse
            best_s = sc
            best_lut = [round(float(x), 7) for x in lut.cpu().tolist()]

    sig = float(torch.mean(zg * zg).item())
    snr = 10.0 * math.log10(sig / max(best_mse, 1e-30))
    return round(float(best_s), 7), best_lut, round(snr, 4)


def fit_universal_gain_cb(
    codebook_unit: torch.Tensor,
    rad_bits: int,
    device: torch.device,
    n_samples: int = 65536,
    seed: int = 20261125,
) -> list[float]:
    """Fit universal Gaussian gain Lloyd-Max levels for a unit spherical codebook."""
    d = codebook_unit.shape[1]
    rng = np.random.default_rng(seed)
    zg = torch.tensor(rng.standard_normal((n_samples, d)), dtype=torch.float32, device=device)
    cb = codebook_unit.to(device=device, dtype=torch.float32)
    g_vals = []
    for i0 in range(0, n_samples, 16384):
        dots = zg[i0 : i0 + 16384] @ cb.T
        g_vals.append(torch.max(dots, dim=-1).values.cpu().numpy())
    g_all = np.concatenate(g_vals)
    if rad_bits == 0:
        return [round(float(np.mean(g_all)), 7)]
    return [round(v, 7) for v in fit_lloyd_max_1d(g_all, 1 << rad_bits, n_iter=40)]
