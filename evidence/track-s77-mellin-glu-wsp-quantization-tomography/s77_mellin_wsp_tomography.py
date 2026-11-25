#!/usr/bin/env python3
"""
Track S77 Pure-Q Oracle: Mellin-GLU x WSP-Gym x siliquant Quantization Tomography.

Zero-dependency Python 3 stdlib oracle (int, fractions.Fraction, math.comb, hashlib, json).
Zero floats on trust paths, zero bare asserts, zero RNG calls, deterministic canonical JSON.

Covers all four Wave-4 pillars:
  1. Exact-Q primitives of arXiv:2611.26450 ("A CPU Inside an LLM"):
     - Single-layer bias-free GLU quadratic scale collapse (Thm 3.2(1))
     - Runnable exact-Q dyadic Mellin-GLU telescoping quadrature & 2-layer Boolean gate (Thm 3.2(2))
     - Axis-aligned width extension norm scaling & (+254, -256) differential tied readout (Thm 3.4(2))
     - Exact S70 24-permutation hidden-channel SwiGLU invariance
  2. Collision #1 (arXiv:2611.26450 x siliquant Lattice Quantization Margin):
     - Runnable 16-rung (4 x 4) dyadic Mellin-GLU carry circuit (C = 81, 64x RMSNorm swing)
     - Uniform INT4 / Uniform INT8 underflow failure, unsorted BlockH4 cross-scale failure,
       scale-stratified S72/S72b quad INT8 rescue (5/5 exact carry), and SparseSidecar nnz bounds
  3. Collision #2 (Track S31 DPI/BWI x Dormant Grafts x WSP-Gym CS-08/CS-15/CS-18):
     - Runnable exact-Q DPI/BWI 3-regime contrast (dense vs symmetry-hidden diff-DPI vs single-snapshot graft)
     - Exact pinned WSP-Gym SHA-256 digests and exact pure-Q binomial McNemar tests for
       CS-08 (finished-subset sign flip) and CS-15/CS-18 (Qwen3.5-0.8B MATH-500 random-edit wall)
  4. Lean 4.36.0 formal inventory (MellinGluQuantMargin.lean, 18 theorems, <= {propext}) & Law-4 N0/N1 scope.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import itertools
import json
import math
from typing import Any

CERT_SCHEMA = "aletheia.track_s77.mellin_wsp_tomography.certificate.v1"
CERT_TRACK_ID = "TRACK-S77-MELLIN-GLU-WSP-QUANT-TOMOGRAPHY"
MAX_INT_BITS = 2048
MAX_JSON_DEPTH = 64

LEAN_FILE_NAME = "MellinGluQuantMargin.lean"
LEAN_FILE_SHA256 = "41d3c044bc08b82cd16c6a5a77109ff4eae122add5efb4e5870678081c91ba7b"
LEAN_THEOREMS: tuple[str, ...] = (
    "MellinGluQuantMargin.glu_single_layer_zero_collapse",
    "MellinGluQuantMargin.glu_single_layer_quadratic_bound",
    "MellinGluQuantMargin.glu_single_layer_weight_norm_lower_bound",
    "MellinGluQuantMargin.mellin_log_grid_scale_shift",
    "MellinGluQuantMargin.mellin_telescoping_sum_exact",
    "MellinGluQuantMargin.mellin_telescoping_shift_invariance",
    "MellinGluQuantMargin.mellin_rational_kernel_algebraic_identity",
    "MellinGluQuantMargin.axis_aligned_norm_compensation_exact",
    "MellinGluQuantMargin.axis_aligned_drift_decomposition",
    "MellinGluQuantMargin.differential_tied_readout_exact_cancellation",
    "MellinGluQuantMargin.differential_tied_readout_active_push",
    "MellinGluQuantMargin.swiglu4_cycle_perm_invariant",
    "MellinGluQuantMargin.swiglu4_swap_01_invariant",
    "MellinGluQuantMargin.uniform_group_quant_zeroing_obstruction",
    "MellinGluQuantMargin.stratified_quad_grouping_nonzero_rescue",
    "MellinGluQuantMargin.mellin_11rung_int4_int8_underflow_and_stratified_rescue",
    "MellinGluQuantMargin.dpi_row_concentration_iso_frobenius_gap",
    "MellinGluQuantMargin.cs08_budget_wall_sign_flip_exact",
)

# Pinned read-only upstream WSP-Gym artifacts (emeraldant/WSP-Gym HEAD d050d16d...)
WSP_GYM_COMMIT = "d050d16dda5ed3243f5c59d115e931e44ef3da53"
WSP_GYM_PINNED_FILES: tuple[dict[str, Any], ...] = (
    {
        "path": "results/table_vs_reasoning.csv",
        "bytes": 680,
        "sha256": "d352ae308f8ca4e4780dec80631beb476e5ff90eb8a316b9a1b913767150812d",
    },
    {
        "path": "results/table_offshelf.csv",
        "bytes": 7224,
        "sha256": "3c29f5f380a9e227670db6583a2739f6bcb4d663ca24e12a414fc587568ed7d4",
    },
    {
        "path": "results/table_qwen_math500.csv",
        "bytes": 2113,
        "sha256": "e349f52d1dc3ce29c9471f8b71d3660160e31a3130327e9331fac29d0a0b8b90",
    },
    {
        "path": "results/table_qwen_slice_summary.csv",
        "bytes": 397,
        "sha256": "e04df0f4f3ee4a033c9319b906f8e08a274ff7c44d3e6e7d6be41bd9ece165e9",
    },
    {
        "path": "data/test_id.jsonl",
        "bytes": 725456,
        "sha256": "5ca3eb8440c662dc7a005dfca10d0cd6fa45b9391508d33c2c358a482211b7c5",
    },
    {
        "path": "data/real_hf_models.jsonl",
        "bytes": 17781,
        "sha256": "a8e7dde69355759004b9de2d18b95764e039c1032984e3e830e555062f79f605",
    },
    {
        "path": "data/test_audit.jsonl",
        "bytes": 1489725,
        "sha256": "7afba9f991430e5e5e160b23e11088750acb0891095c8527c2aba19fec440b35",
    },
)


class S77Error(ValueError):
    """Fail-closed typed error for Track S77 oracle and verifier."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def require_ok(cond: bool, code: str, message: str) -> None:
    if cond is not True:
        raise S77Error(code, message)


def require_exact_int(val: Any, label: str, min_val: int | None = None, max_val: int | None = None) -> int:
    if type(val) is not int:
        raise S77Error("INVALID_INT", f"{label} must be strict int")
    if val.bit_length() > MAX_INT_BITS:
        raise S77Error("INT_BIT_LIMIT", f"{label} exceeds {MAX_INT_BITS} bits")
    if min_val is not None and val < min_val:
        raise S77Error("INT_TOO_SMALL", f"{label} below {min_val}")
    if max_val is not None and val > max_val:
        raise S77Error("INT_TOO_LARGE", f"{label} above {max_val}")
    return val


def require_exact_fraction(val: Any, label: str) -> Fraction:
    if type(val) is not Fraction:
        raise S77Error("INVALID_FRACTION", f"{label} must be exact Fraction")
    return val


def frac_to_dict(val: Fraction) -> dict[str, int]:
    require_exact_fraction(val, "frac_to_dict")
    return {"num": val.numerator, "den": val.denominator}


def round_half_even_int(val: Fraction) -> int:
    """Exact pure-Q round-to-nearest-integer (ties to even)."""
    require_exact_fraction(val, "round_half_even_int")
    return round(val)


def sym_quant_int(val: int, qmax: int, peak: int) -> int:
    """Exact pure-Z symmetric integer quantizer round(val / (peak / qmax)) for val >= 0."""
    require_exact_int(val, "val", min_val=0)
    require_exact_int(qmax, "qmax", min_val=1)
    require_exact_int(peak, "peak", min_val=1)
    return (2 * qmax * val + peak) // (2 * peak)


def sym_quant_signed_frac(val: Fraction, qmax: int, peak: Fraction) -> Fraction:
    """Exact pure-Q signed symmetric quantizer with scale step peak / qmax."""
    require_exact_fraction(val, "val")
    require_exact_int(qmax, "qmax", min_val=1)
    require_exact_fraction(peak, "peak")
    require_ok(peak > 0, "NONPOSITIVE_PEAK", "quantization peak must be > 0")
    scaled = (val * qmax) / peak
    q_int = round_half_even_int(scaled)
    if q_int > qmax:
        q_int = qmax
    elif q_int < -qmax:
        q_int = -qmax
    return Fraction(q_int, qmax) * peak


def exact_two_sided_mcnemar_p(b10: int, b01: int) -> Fraction:
    """Exact pure-Q two-sided binomial McNemar p-value: min(1, 2 * sum_{i=0}^{min} C(n,i) / 2^n)."""
    require_exact_int(b10, "b10", min_val=0, max_val=2000)
    require_exact_int(b01, "b01", min_val=0, max_val=2000)
    n = b10 + b01
    if n == 0:
        return Fraction(1, 1)
    k = b10 if b10 < b01 else b01
    tail_num = 0
    for i in range(k + 1):
        tail_num += math.comb(n, i)
    p = Fraction(2 * tail_num, 1 << n)
    return Fraction(1, 1) if p > 1 else p


def mellin_rat_phi(s: Fraction, r: int = 2) -> Fraction:
    """Exact pure-Q Mellin-GLU telescoping kernel: phi_r(s) = (r^2 - 1) s / ((1 + s^2)(1 + r^2 s^2))."""
    require_exact_fraction(s, "s")
    require_exact_int(r, "r", min_val=2, max_val=16)
    s2 = s * s
    r2 = r * r
    return (Fraction(r2 - 1, 1) * s) / ((Fraction(1, 1) + s2) * (Fraction(1, 1) + r2 * s2))


def eval_mellin_grid(
    rungs: tuple[Fraction, ...],
    lam: Fraction,
    r0: Fraction,
    x_val: Fraction,
    r: int = 2,
) -> Fraction:
    """Evaluate sum_k phi_r(-alpha_k * lam * r0) * (-alpha_k * lam * x_val) exactly in Q."""
    require_exact_fraction(lam, "lam")
    require_exact_fraction(r0, "r0")
    require_exact_fraction(x_val, "x_val")
    require_ok(r0 > 0, "NONPOSITIVE_R0", "r0 must be > 0")
    total = Fraction(0, 1)
    for alpha in rungs:
        require_exact_fraction(alpha, "alpha")
        g_in = -alpha * lam * r0
        u_in = -alpha * lam * x_val
        total += mellin_rat_phi(g_in, r=r) * u_in
    return total


def eval_mellin_closed_form(
    k_min: int,
    k_max: int,
    lam: Fraction,
    r0: Fraction,
    x_val: Fraction,
    r: int = 2,
) -> Fraction:
    """Exact telescoping closed form (x/r0) * (1/(1+(r^k_min lam r0)^2) - 1/(1+(r^(k_max+1) lam r0)^2))."""
    require_exact_int(k_min, "k_min", min_val=-32, max_val=32)
    require_exact_int(k_max, "k_max", min_val=k_min, max_val=32)
    require_exact_fraction(lam, "lam")
    require_exact_fraction(r0, "r0")
    require_exact_fraction(x_val, "x_val")
    require_ok(r0 > 0, "NONPOSITIVE_R0", "r0 must be > 0")
    t_lo = (Fraction(r, 1) ** k_min) * lam * r0
    t_hi = (Fraction(r, 1) ** (k_max + 1)) * lam * r0
    bracket = Fraction(1, 1) / (Fraction(1, 1) + t_lo * t_lo) - Fraction(1, 1) / (Fraction(1, 1) + t_hi * t_hi)
    return (x_val / r0) * bracket


# ---------------------------------------------------------------------------
# Pillar 1: Exact-Q Primitives of arXiv:2611.26450
# ---------------------------------------------------------------------------

def build_pillar1_primitives() -> dict[str, Any]:
    # 1A. Single-layer bias-free GLU quadratic scale collapse (Thm 3.2(1))
    scales_collapse = (Fraction(1, 1), Fraction(1, 4), Fraction(1, 16), Fraction(1, 256))
    collapse_rows: list[dict[str, Any]] = []
    f_zero = mellin_rat_phi(Fraction(0, 1), r=2) * Fraction(0, 1)
    for lam in scales_collapse:
        out = mellin_rat_phi(lam, r=2) * lam
        bound = Fraction(3, 1) * lam * lam
        collapse_rows.append(
            {
                "lambda": frac_to_dict(lam),
                "f1_output": frac_to_dict(out),
                "quadratic_bound": frac_to_dict(bound),
                "bound_holds": 0 < out <= bound,
            }
        )
    # Weight-norm product lower bound for target 9/10 at lambda_min = 1/256, C = 3: (9/10)/(3 * 256^-2) = 98304/5
    norm_lb = Fraction(9, 10) / (Fraction(3, 1) * Fraction(1, 256) * Fraction(1, 256))

    # 1B. Runnable 21-rung exact-Q Mellin-GLU telescoping quadrature (k = -10..10, 1024x RMSNorm swing)
    k_min, k_max = -10, 10
    rungs_21 = tuple(Fraction(2, 1) ** k for k in range(k_min, k_max + 1))
    carry_c = Fraction(81, 1)
    r0 = Fraction(1, 1)
    swing_scales = (Fraction(1, 32), Fraction(1, 4), Fraction(1, 1), Fraction(4, 1), Fraction(32, 1))
    telescoping_rows: list[dict[str, Any]] = []
    max_abs_err = Fraction(0, 1)
    exact_carry_passes = 0
    for lam in swing_scales:
        q_sum = eval_mellin_grid(rungs_21, lam, r0, carry_c, r=2)
        q_closed = eval_mellin_closed_form(k_min, k_max, lam, r0, carry_c, r=2)
        residual = q_sum - q_closed
        err = abs(q_sum - carry_c)
        if err > max_abs_err:
            max_abs_err = err
        ok_carry = err < Fraction(1, 2)
        if ok_carry:
            exact_carry_passes += 1
        telescoping_rows.append(
            {
                "lambda": frac_to_dict(lam),
                "abs_error": frac_to_dict(err),
                "rounded_value": round_half_even_int(q_sum),
                "telescoping_residual_zero": residual == 0,
                "carry_margin_pass": ok_carry,
            }
        )

    # 1C. 2-layer exact-Q Boolean clause (a AND b) OR (NOT c) across 8 inputs x 3 RMSNorm scales = 24/24
    bool_scales = (Fraction(1, 8), Fraction(1, 1), Fraction(8, 1))
    bool_total = 0
    bool_exact = 0
    for a in (0, 1):
        for b in (0, 1):
            for c in (0, 1):
                truth = 1 if ((a == 1 and b == 1) or c == 0) else 0
                for lam in bool_scales:
                    q_ab = eval_mellin_grid(rungs_21, lam, r0, Fraction(2 * (a + b) - 3, 2), r=2)
                    q_nc = eval_mellin_grid(rungs_21, lam, r0, Fraction(1 - 2 * c, 2), r=2)
                    h_ab = 1 if q_ab > 0 else 0
                    h_nc = 1 if q_nc > 0 else 0
                    q_or = eval_mellin_grid(rungs_21, lam, r0, Fraction(2 * (h_ab + h_nc) - 1, 2), r=2)
                    pred = 1 if q_or > 0 else 0
                    bool_total += 1
                    if pred == truth:
                        bool_exact += 1

    # 1D. Axis-aligned width extension & (+254, -256) differential tied readout (Thm 3.4(2))
    granite_gamma_sq = Fraction(2560, 2560 + 1140)
    qwen_gamma_sq = Fraction(2560, 2560 + 2555)
    granite_nnz_frac = Fraction(1_330_000, 3_660_000_000)
    qwen_nnz_frac = Fraction(2_390_000, 4_206_000_000)
    e_val, h0_val, delta_val = 7, 13, 3
    w_pos, w_neg = 254, -256
    off_trigger = e_val * ((1 + w_pos) * h0_val) + e_val * ((1 + w_neg) * h0_val)
    active_push = e_val * ((1 + w_pos) * (h0_val + delta_val)) + e_val * ((1 + w_neg) * (h0_val - delta_val))

    # 1E. S70 hidden-channel permutation invariance across all 24 permutations of a 4-channel SwiGLU block
    d_vec = (Fraction(3, 1), Fraction(-5, 1), Fraction(7, 1), Fraction(11, 1))
    g_vec = (Fraction(-1, 2), Fraction(-1, 1), Fraction(-2, 1), Fraction(-4, 1))
    u_vec = (Fraction(1, 2), Fraction(1, 1), Fraction(2, 1), Fraction(4, 1))
    base_swiglu = sum(
        (d_vec[i] * mellin_rat_phi(g_vec[i], r=2) * u_vec[i] for i in range(4)),
        Fraction(0, 1),
    )
    perm_count = 0
    perm_max_diff = Fraction(0, 1)
    for perm in itertools.permutations(range(4)):
        val_p = sum(
            (d_vec[i] * mellin_rat_phi(g_vec[i], r=2) * u_vec[i] for i in perm),
            Fraction(0, 1),
        )
        diff = abs(val_p - base_swiglu)
        if diff > perm_max_diff:
            perm_max_diff = diff
        perm_count += 1

    return {
        "single_layer_collapse": {
            "f1_zero": frac_to_dict(f_zero),
            "weight_norm_lb_at_lam_1_256_eps_1_10": frac_to_dict(norm_lb),
            "evaluations": collapse_rows,
        },
        "mellin_21rung_telescoping": {
            "k_min": k_min,
            "k_max": k_max,
            "rung_count": len(rungs_21),
            "weight_dynamic_span": 1 << (k_max - k_min),
            "scale_swing_ratio": 1024,
            "carry_payload": 81,
            "max_abs_error": frac_to_dict(max_abs_err),
            "exact_carry_passes": exact_carry_passes,
            "exact_carry_total": len(swing_scales),
            "evaluations": telescoping_rows,
        },
        "two_layer_boolean_gate": {
            "truth_assignments": 8,
            "scales_tested": len(bool_scales),
            "exact_passes": bool_exact,
            "total_evaluations": bool_total,
        },
        "width_extension_and_tied_readout": {
            "granite_gamma_nl_sq": frac_to_dict(granite_gamma_sq),
            "qwen_gamma_nl_sq": frac_to_dict(qwen_gamma_sq),
            "granite_sparse_nnz_fraction": frac_to_dict(granite_nnz_frac),
            "qwen_sparse_nnz_fraction": frac_to_dict(qwen_nnz_frac),
            "norm_pair": [w_pos, w_neg],
            "off_trigger_residual": off_trigger,
            "active_push_exact": active_push,
            "active_push_formula": 510 * e_val * delta_val,
        },
        "s70_swiglu_perm_invariance": {
            "permutations_checked": perm_count,
            "max_abs_diff": frac_to_dict(perm_max_diff),
            "exact_invariant": perm_max_diff == 0,
        },
    }


# ---------------------------------------------------------------------------
# Pillar 2: Collision #1 (Mellin-GLU x siliquant Lattice Quantization Margin)
# ---------------------------------------------------------------------------

def _h4_apply_exact(quad: tuple[Fraction, Fraction, Fraction, Fraction]) -> tuple[Fraction, Fraction, Fraction, Fraction]:
    """Exact orthogonal Hadamard H_4 / 2 transform over Q (involution: H4(H4(v)) == v)."""
    a, b, c, d = quad
    half = Fraction(1, 2)
    return (
        (a + b + c + d) * half,
        (a - b + c - d) * half,
        (a + b - c - d) * half,
        (a - b - c + d) * half,
    )


def _eval_regime(
    name: str,
    rungs_hat: tuple[Fraction, ...],
    scales: tuple[Fraction, ...],
    carry_c: Fraction,
) -> dict[str, Any]:
    zeroed = sum(1 for a in rungs_hat if a == 0)
    max_err = Fraction(0, 1)
    passes = 0
    for lam in scales:
        val = eval_mellin_grid(rungs_hat, lam, Fraction(1, 1), carry_c, r=2)
        err = abs(val - carry_c)
        if err > max_err:
            max_err = err
        if err < Fraction(1, 2):
            passes += 1
    return {
        "regime": name,
        "zeroed_rungs": zeroed,
        "total_rungs": len(rungs_hat),
        "max_abs_error": frac_to_dict(max_err),
        "carry_passes": passes,
        "carry_total": len(scales),
        "all_carry_pass": passes == len(scales),
    }


def build_pillar2_quantization_collision() -> dict[str, Any]:
    # 16-rung dyadic Mellin-GLU carry circuit (k = -8..7 => 4 exact quads of 4 rungs, dynamic range 32,768x)
    k_vals = tuple(range(-8, 8))
    rungs_exact = tuple(Fraction(2, 1) ** k for k in k_vals)
    peak_global = rungs_exact[-1]  # 2^7 = 128
    carry_c = Fraction(81, 1)
    scales = (Fraction(1, 8), Fraction(1, 4), Fraction(1, 1), Fraction(4, 1), Fraction(8, 1))

    # 1. Exact / FP32 SparseSidecar
    r_exact = _eval_regime("exact_fp32_sparse_sidecar", rungs_exact, scales, carry_c)

    # 2. Uniform whole-group INT4 (qmax = 7)
    rungs_int4 = tuple(
        Fraction(sym_quant_int(1 << (k + 8), 7, 1 << 15), 7) * peak_global
        for k in k_vals
    )
    r_int4 = _eval_regime("uniform_group_int4", rungs_int4, scales, carry_c)

    # 3. Uniform whole-group INT8 (qmax = 127)
    rungs_int8 = tuple(
        Fraction(sym_quant_int(1 << (k + 8), 127, 1 << 15), 127) * peak_global
        for k in k_vals
    )
    r_int8 = _eval_regime("uniform_group_int8", rungs_int8, scales, carry_c)

    # 4. Unsorted / interleaved BlockH4 Hadamard rotation + INT8 (mixes k, k+4, k+8, k+12 across 4096x span)
    rungs_h4_unsorted_list = [Fraction(0, 1)] * 16
    for q_idx in range(4):
        idxs = (q_idx, q_idx + 4, q_idx + 8, q_idx + 12)
        quad = (rungs_exact[idxs[0]], rungs_exact[idxs[1]], rungs_exact[idxs[2]], rungs_exact[idxs[3]])
        rot = _h4_apply_exact(quad)
        rot_peak = max(abs(v) for v in rot)
        rot_q = tuple(sym_quant_signed_frac(v, 127, rot_peak) for v in rot)
        rec = _h4_apply_exact((rot_q[0], rot_q[1], rot_q[2], rot_q[3]))
        for j, idx in enumerate(idxs):
            rungs_h4_unsorted_list[idx] = rec[j]
    r_h4_unsorted = _eval_regime("unsorted_blockh4_int8", tuple(rungs_h4_unsorted_list), scales, carry_c)

    # 5. S72/S72b scale-stratified quad grouping (4 sorted quads of span 8x each) + INT8 (qmax = 127)
    rungs_strat_int8_list: list[Fraction] = []
    for q_idx in range(4):
        quad = rungs_exact[4 * q_idx : 4 * q_idx + 4]
        q_peak = quad[-1]
        for v in quad:
            rungs_strat_int8_list.append(sym_quant_signed_frac(v, 127, q_peak))
    r_strat_int8 = _eval_regime("stratified_s72_quad_int8", tuple(rungs_strat_int8_list), scales, carry_c)

    # 6. Scale-stratified quad INT4 (qmax = 7): 0/16 rungs zeroed (fixes underflow) but step 1/7 > carry margin 0.5/81
    rungs_strat_int4_list: list[Fraction] = []
    for q_idx in range(4):
        quad = rungs_exact[4 * q_idx : 4 * q_idx + 4]
        q_peak = quad[-1]
        for v in quad:
            rungs_strat_int4_list.append(sym_quant_signed_frac(v, 7, q_peak))
    r_strat_int4 = _eval_regime("stratified_s72_quad_int4", tuple(rungs_strat_int4_list), scales, carry_c)

    return {
        "circuit_spec": {
            "k_min": -8,
            "k_max": 7,
            "rung_count": 16,
            "quad_count": 4,
            "global_dynamic_span": 32768,
            "stratified_intra_quad_span": 8,
            "carry_payload": 81,
            "carry_tolerance": frac_to_dict(Fraction(1, 2)),
            "scale_swing_ratio": 64,
        },
        "regimes": [
            r_exact,
            r_int4,
            r_int8,
            r_h4_unsorted,
            r_strat_int8,
            r_strat_int4,
        ],
        "table3_paper_anchors": {
            "w_circ_fp32_g3_g7_pass": 5,
            "w_circ_fp32_g3_g7_total": 5,
            "w_circ_int8_err_tenths": 374,
            "w_circ_int4_err_tenths": 810,
            "qwen_hybrid_alu_correct": 100,
            "qwen_hybrid_ood_triggers": 0,
            "qwen_hybrid_ood_total": 11134,
        },
    }


# ---------------------------------------------------------------------------
# Pillar 3: Collision #2 (Track S31 DPI/BWI x WSP-Gym CS-08 / CS-15 / CS-18)
# ---------------------------------------------------------------------------

def count_offblock_nnz(mat: tuple[tuple[int, ...], ...], split: int) -> int:
    """Count non-zero off-diagonal block couplings between indices [0..split) and [split..n)."""
    n = len(mat)
    require_exact_int(split, "split", min_val=1, max_val=n - 1)
    count = 0
    for r in range(split):
        for c in range(split, n):
            if mat[r][c] != 0:
                count += 1
            if mat[c][r] != 0:
                count += 1
    return count


def compute_matrix_dpi_bwi(mat: tuple[tuple[int, ...], ...]) -> dict[str, Any]:
    """Exact pure-Q Track S31 DPI (row concentration C_row) and BWI (span, overload, L0 density)."""
    n_rows = len(mat)
    require_ok(n_rows >= 2, "DPI_ROWS", "matrix must have >= 2 rows")
    n_cols = len(mat[0])
    require_ok(n_cols >= 2, "DPI_COLS", "matrix must have >= 2 cols")
    row_energies: list[int] = []
    nz_abs: list[int] = []
    total_entries = n_rows * n_cols
    for row in mat:
        require_ok(len(row) == n_cols, "DPI_RECT", "matrix must be rectangular")
        r_sum = 0
        for v in row:
            require_exact_int(v, "mat_entry")
            r_sum += v * v
            if v != 0:
                nz_abs.append(-v if v < 0 else v)
        row_energies.append(r_sum)
    total_e = sum(row_energies)
    require_ok(total_e > 0, "DPI_ZERO_MAT", "matrix must be non-zero")
    max_row_e = max(row_energies)
    c_row = Fraction(n_rows * max_row_e, total_e)
    min_nz = min(nz_abs)
    max_nz = max(nz_abs)
    span = Fraction(max_nz, min_nz)
    # Squared overload: max_entry^2 / mean_nonzero_entry_sq
    sum_sq_nz = total_e
    sq_overload = Fraction(max_nz * max_nz * len(nz_abs), sum_sq_nz)
    l0_density = Fraction(len(nz_abs), total_entries)
    return {
        "rows": n_rows,
        "cols": n_cols,
        "c_row": frac_to_dict(c_row),
        "bwi_span": frac_to_dict(span),
        "bwi_sq_overload": frac_to_dict(sq_overload),
        "l0_density": frac_to_dict(l0_density),
        "nonzero_count": len(nz_abs),
    }


def is_sign_flip(diff_all: Fraction, diff_fin: Fraction) -> bool:
    """True iff overall delta is strictly positive while finished-subset delta is strictly negative."""
    return diff_all > 0 and diff_fin < 0


def build_pillar3_wsp_dpi_collision() -> dict[str, Any]:
    # 3A. Runnable 3-regime DPI/BWI matrix contrast
    w_clean = (
        (3, -2, 4, -1),
        (-2, 3, -1, 4),
        (4, -1, 3, -2),
        (-1, 4, -2, 3),
    )
    # Regime B: WSP-Gym symmetry-hidden sign_flip_in on row 0 (preserves row energies!)
    w_sign_flip = (
        (-3, 2, -4, 1),
        (-2, 3, -1, 4),
        (4, -1, 3, -2),
        (-1, 4, -2, 3),
    )
    dw_sign_flip = tuple(
        tuple(w_sign_flip[r][c] - w_clean[r][c] for c in range(4))
        for r in range(4)
    )
    # Regime C: arXiv:2611.26450 axis-aligned width-extended Mellin-GLU graft (4 NL + 4 circuit channels)
    w_graft = (
        (3, -2, 4, -1, 0, 0, 0, 0),
        (-2, 3, -1, 4, 0, 0, 0, 0),
        (4, -1, 3, -2, 0, 0, 0, 0),
        (-1, 4, -2, 3, 0, 0, 0, 0),
        (0, 0, 0, 0, 1, 0, 0, 0),
        (0, 0, 0, 0, 0, 8, 0, 0),
        (0, 0, 0, 0, 0, 0, 64, 0),
        (0, 0, 0, 0, 0, 0, 0, 1024),
    )
    m_clean = compute_matrix_dpi_bwi(w_clean)
    m_flip = compute_matrix_dpi_bwi(w_sign_flip)
    m_dw = compute_matrix_dpi_bwi(dw_sign_flip)
    m_graft = compute_matrix_dpi_bwi(w_graft)

    offblock_nnz = count_offblock_nnz(w_graft, 4)
    norm_pair_sum = (1 + 254) + (1 - 256)
    norm_sq_overload = 255 * 255

    # 3B. Exact CS-08 Compute-Budget Wall on real WSP-Gym test_id (500 networks = 422 faulty + 78 clean)
    rl_all_ok, rl_all_n = 350, 422
    th_all_ok, th_all_n = 319, 422
    rl_clean_ok, th_clean_ok, clean_n = 78, 60, 78
    rl_tokens, th_tokens = 19_035, 5_298_074
    cutoff_all, cutoff_faulty = 110, 95
    # Paired contingency across 422 faulty networks: b11=273, b10(RL only)=77, b01(Think only)=46, b00=26
    all_b11, all_b10, all_b01, all_b00 = 273, 77, 46, 26

    # Finished subset (327 = 422 - 95 faulty networks where thinking did NOT hit length cutoff):
    fin_n = rl_all_n - cutoff_faulty
    fin_b11, fin_b10, fin_b01, fin_b00 = 273, 3, 46, 5
    fin_rl_ok = fin_b11 + fin_b10
    fin_th_ok = fin_b11 + fin_b01
    cutoff_rl_only_wins = all_b10 - fin_b10  # 74 of 77 RL exclusive wins come strictly from cutoff networks!

    token_compression = Fraction(th_tokens, rl_tokens)
    diff_all = Fraction(rl_all_ok - th_all_ok, rl_all_n)
    diff_fin = Fraction(fin_rl_ok - fin_th_ok, fin_n)
    p_all = exact_two_sided_mcnemar_p(all_b10, all_b01)
    p_fin = exact_two_sided_mcnemar_p(fin_b10, fin_b01)

    # 3C. Exact CS-15/CS-18 Random-Edit Baseline Wall on WSP-Gym Qwen3.5-0.8B MATH-500 (N = 500)
    math500_n = 500
    rand_ok = 188
    math500_specs = (
        ("unedited", 41, 6, 153, 0),
        ("untrained_reason_L23", 191, 61, 58, 1),
        ("real_rl_L23", 186, 53, 55, 1),
        ("formula_rl_L23", 187, 54, 55, 1),
        ("n573_x2_published_edit", 185, 58, 61, 1),
        ("wait_ban_zero_weight_edit", 194, 62, 56, 0),
    )
    math500_rows: list[dict[str, Any]] = []
    for name, ok_cnt, b10_vs_rand, b01_vs_rand, edits_weights in math500_specs:
        p_vs_rand = exact_two_sided_mcnemar_p(b10_vs_rand, b01_vs_rand)
        math500_rows.append(
            {
                "method": name,
                "correct": ok_cnt,
                "total": math500_n,
                "delta_vs_random": ok_cnt - rand_ok,
                "b10_method_only": b10_vs_rand,
                "b01_random_only": b01_vs_rand,
                "mcnemar_two_sided_p_lt_1e_30": p_vs_rand < Fraction(1, 10**30),
                "mcnemar_two_sided_p_gt_4_5": p_vs_rand > Fraction(4, 5),
                "mcnemar_two_sided_p_rounded_1e6": round_half_even_int(p_vs_rand * 1_000_000),
                "edits_weights": edits_weights == 1,
            }
        )

    # 8-layer Qwen3.5-0.8B 256-problem dev slice summary (exact integer hundredths of percentage points)
    slice_summary = {
        "layers_evaluated": 8,
        "dev_problems": 256,
        "random_mean_gain_bp": 1025,
        "untrained_reasoning_mean_gain_bp": 771,
        "formula_rl_mean_gain_bp": 747,
        "real_rl_mean_gain_bp": 688,
        "scale_rl_mean_gain_bp": 190,
        "all_editors_below_random": True,
    }

    return {
        "wsp_gym_upstream": {
            "repo": "emeraldant/WSP-Gym",
            "commit": WSP_GYM_COMMIT,
            "pinned_files": list(WSP_GYM_PINNED_FILES),
        },
        "dpi_bwi_three_regime_model": {
            "clean_dense": m_clean,
            "symmetry_hidden_sign_flip": m_flip,
            "whitebox_diff_dw": m_dw,
            "mellin_glu_graft_single_snapshot": m_graft,
            "graft_offblock_nnz": offblock_nnz,
            "graft_norm_pair_antisym_sum": norm_pair_sum,
            "graft_norm_sq_overload": norm_sq_overload,
            "single_snapshot_blind_to_sign_flip": m_clean["c_row"] == m_flip["c_row"],
            "diff_dpi_exposes_sign_flip": m_dw["c_row"] == {"num": 4, "den": 1},
            "single_snapshot_exposes_mellin_graft": m_graft["bwi_span"] == {"num": 1024, "den": 1},
        },
        "wsp_gym_empirical_dpi_anchors_1e4": {
            "test_id_clean_n78_c_row": 23736,
            "test_id_sign_flip_in_n58_single_c_row": 24777,
            "test_id_sign_flip_in_n58_diff_dw_c_row": 77241,
            "test_id_weight_corrupt_n71_single_c_row": 23612,
            "test_id_weight_corrupt_n71_diff_dw_c_row": 45915,
            "test_audit_backdoors_n500_single_c_row": 30927,
        },
        "cs08_compute_budget_wall": {
            "total_networks": 500,
            "faulty_networks": rl_all_n,
            "clean_networks": clean_n,
            "scale_rl_faulty_correct": rl_all_ok,
            "thinking_faulty_correct": th_all_ok,
            "scale_rl_clean_correct": rl_clean_ok,
            "thinking_clean_correct": th_clean_ok,
            "scale_rl_total_tokens": rl_tokens,
            "thinking_total_tokens": th_tokens,
            "token_compression_ratio": frac_to_dict(token_compression),
            "thinking_cutoffs_all": cutoff_all,
            "thinking_cutoffs_faulty": cutoff_faulty,
            "all_faulty_b10_rl_only": all_b10,
            "all_faulty_b01_think_only": all_b01,
            "all_faulty_diff_rl_minus_think": frac_to_dict(diff_all),
            "all_faulty_mcnemar_p_rounded_1e6": round_half_even_int(p_all * 1_000_000),
            "finished_faulty_n": fin_n,
            "finished_scale_rl_correct": fin_rl_ok,
            "finished_thinking_correct": fin_th_ok,
            "finished_b10_rl_only": fin_b10,
            "finished_b01_think_only": fin_b01,
            "finished_diff_rl_minus_think": frac_to_dict(diff_fin),
            "finished_mcnemar_p_lt_1e_10": p_fin < Fraction(1, 10**10),
            "cutoff_exclusive_rl_wins": cutoff_rl_only_wins,
            "sign_flip_verified": is_sign_flip(diff_all, diff_fin),
        },
        "cs15_cs18_random_edit_wall": {
            "benchmark": "Qwen3.5-0.8B MATH-500",
            "n_problems": math500_n,
            "random_L23_correct": rand_ok,
            "comparisons_vs_random_L23": math500_rows,
            "eight_layer_dev_slice_summary": slice_summary,
        },
    }


# ---------------------------------------------------------------------------
# Pillar 4: Lean 4.36.0 Inventory & Honest Law-4 N0/N1 Scope
# ---------------------------------------------------------------------------

def build_pillar4_formal_and_scope() -> dict[str, Any]:
    return {
        "lean4_certificate": {
            "toolchain": "leanprover/lean4:v4.36.0",
            "file": LEAN_FILE_NAME,
            "sha256": LEAN_FILE_SHA256,
            "theorem_count": len(LEAN_THEOREMS),
            "theorems": list(LEAN_THEOREMS),
            "allowed_axioms": ["propext"],
            "zero_axiom_theorems": 2,
            "propext_only_theorems": 16,
            "external_imports": 0,
            "forbidden_axioms": 0,
            "r9_static_findings": 0,
        },
        "novelty_honesty_law4": {
            "highest_novelty_class": "N1",
            "n2_claims": 0,
            "n0_prior_art": [
                "arXiv:2611.26450 Theorems 3.2-3.4 and Tables 3/6(b) (Mellin-GLU quadrature, width extension, SparseSidecar)",
                "emeraldant/WSP-Gym test_id/test_audit/MATH-500 empirical artifacts and random-edit baseline",
                "Track S31 DPI/BWI tomography, Track S70 SwiGLU permutation symmetry, Track S72/S72b stratified quad grouping",
            ],
            "n1_synthesis": [
                "Pure-Init Lean 4.36.0 machine-checked formalization (18 theorems, <= {propext}, R9 clean)",
                "Exact-Q 16-rung 4-quad Mellin-GLU quantization collision proving S72/S72b stratified quad INT8 rescues 5/5 carry",
                "Exact-Q 3-regime DPI/BWI + CS-08 finished-subset sign flip (319/327 vs 276/327, p < 1e-10) & CS-15/CS-18 McNemar unification",
            ],
        },
    }


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def build_certificate() -> dict[str, Any]:
    payload = {
        "pillar1_mellin_glu_primitives": build_pillar1_primitives(),
        "pillar2_quantization_margin_collision": build_pillar2_quantization_collision(),
        "pillar3_wsp_dpi_security_collision": build_pillar3_wsp_dpi_collision(),
        "pillar4_lean4_and_scope": build_pillar4_formal_and_scope(),
    }
    payload_sha = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    envelope = {
        "schema": CERT_SCHEMA,
        "track_id": CERT_TRACK_ID,
        "payload_sha256": payload_sha,
        "payload": payload,
    }
    cert_sha = hashlib.sha256(canonical_json_bytes(envelope)).hexdigest()
    return {
        "schema": CERT_SCHEMA,
        "track_id": CERT_TRACK_ID,
        "payload_sha256": payload_sha,
        "certificate_sha256": cert_sha,
        "payload": payload,
    }
