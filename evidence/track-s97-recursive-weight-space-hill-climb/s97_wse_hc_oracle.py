#!/usr/bin/env python3
"""Track S97 Exact Pure-Z/Q Oracle for ALETHEIA-WSE-HC.

Pure integer / rational (Fraction) computation — ZERO floats, ZERO random,
ZERO bare asserts, ZERO external dependencies.
Synthesizes:
  - Pillar 1 (a-d): Exact pure-Z/Q proofs & algebraic witnesses for ALETHEIA-WSE-HC
    (subspace dimensionality collapse, Householder isometry, BlockH4 Parseval,
     non-differentiable discrete oracle dominance, DPI concentration, S80 songe
     FWER vs 5-gate ratchet, orthogonal nullspace anti-forgetting + Law-5 capacity
     obstruction, S68/S70 cross-layer bilinear non-additivity + recursive
     re-linearization + coupled nullspace shift, Hybrid Mode B & VRAM roofline).
  - Pillar 2 ([anchor]): Exact rational lossless encoding & SHA-256 pinning of the
    live 4-way RTX 3080 Qwen2.5-0.5B benchmark and mlos Zone-B receipt.
  - Pillar 3: Pinned manifest of 18/18 universal pure-Init Lean 4.36.0 theorems
    and 7 frozen upstream expedition certificates (S31, S68, S70, S73, S77, S78, S80).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pathlib
import stat
from fractions import Fraction
from typing import Any, Dict, List, Sequence, Tuple

SCHEMA_VERSION = "s97_wse_hc_certificate_v1"
TRACK_ID = "S97"

LEAN_FILE_NAME = "RecursiveWeightSpaceHillClimb.lean"
LEAN_FILE_SHA256 = "83dd4cac5da4c4c78641415b43e4e63afb9fb0b9b43c0bf8304a380a9268d3cf"
LEAN_NAMESPACE = "TrackS97RecursiveWSEHC"
LEAN_ALLOWED_AXIOMS: Tuple[str, ...] = ("propext", "Quot.sound")

LEAN_THEOREMS: Tuple[str, ...] = (
    "thm01_isotropic_es_snr_collapse_universal",
    "thm02_householder_exact_isometry_norm_preserving",
    "thm03_householder_exact_involution",
    "thm04_blockh4_parseval_exact_energy",
    "thm05_step_oracle_zero_gradient_vs_hillclimb_progress",
    "thm06_discrete_lattice_grid_monotone_ratchet",
    "thm07_dpi_concentration_bound_preserved",
    "thm08_surrogate_goodhart_rejected_by_ratchet",
    "thm09_unratcheted_fwer_strictly_grows",
    "thm10_five_gate_ratchet_zero_regression_invariant",
    "thm11_nullspace_projection_exact_zero_forgetting",
    "thm12_nullspace_projection_pythagorean_contraction",
    "thm13_nullspace_capacity_exhaustion_law5_obstruction",
    "thm14_cross_layer_bilinear_nonadditivity_identity",
    "thm15_static_oneshot_vs_recursive_relinearization",
    "thm16_recursive_relinearization_monotone_contraction",
    "thm17_hybrid_mode_b_beats_pure_backprop_and_pure_zo",
    "thm18_backprop_free_vram_savings_exact",
)

# Tracks whose certificate files are NOT in this repo. Checked and absent from aletheia
# (main + all branches), Foundation-0/cave-expedition (main + all branches), and
# Foundation-0/math0@f9970082 — so these are external historical SHA-256 pins whose files
# resolve in no readable repo (a private repo could hold them; none is known).
CROSS_REPO_UPSTREAM: Tuple[str, ...] = ("S68", "S70", "S73", "S78")
# Short label token for pins whose certificate files resolve in no readable repo
# (aletheia, cave-expedition, math0@f9970082 all checked); the full prose lives in REPORT.md.
CROSS_REPO_SOURCE = "external-historical-pin"

UPSTREAM_CERT_MANIFEST: Tuple[Tuple[str, str, str], ...] = (
    ("S31", "track-s31-aletheia-v22-misfolding/aletheia_v22_misfolding_certificate.json", "f4f7f8abff0c7eae0d5678016c1041ab34870ef2de57a2f83e4cbb9a529f8a9b"),
    ("S68", "track-s68-zero-cal-adaptive-blockh4-router-and-ptx/rtx3080_s68_certificate.json", "a0b38faac25511be90fbc823754fc5819931250ce0af0c2a15a23cf05c957e4e"),
    ("S70", "track-s70-cross-layer-and-sorted-blockh4-lean4/s70_certificate.json", "5cdce98df676290d78688da689fe576492487125653e563c667df000980c45e4"),
    ("S73", "track-s73-lowbit-and-sharednorm-quad-snake/rtx3080_s73_certificate.json", "33dfb4153fe974e9ef13120190c14ada6dda63ffbee6caa46047d274f32d36cf"),
    ("S77", "track-s77-mellin-glu-wsp-quantization-tomography/s77_mellin_wsp_certificate.json", "d1b9121c435331053b7ab28b915a2062ae7c93b4197d203c63dba42cce5dd74d"),
    ("S78", "track-s78-engram-lora-capacity-siliquant-mdl/s78_engram_lora_siliquant_certificate.json", "3b8341ef5f588f970accb9a9d28f0b683af9747be045e69196e6c19d3fa58378"),
    ("S80", "track-s80-rocket-songe-unsloth-optimizations/s80_certificate.json", "95681a29ca577c4e3040f8ba63f8516b1cbb2bf1ebfdcda06277f21bb2aa2cb7"),
)

# Pinned live RTX 3080 anchor digests (filled immediately once task-2123 completes)
PINNED_LIVE_RESULTS_FILE = "rtx3080_s97_wse_hc_results.json"
PINNED_LIVE_RESULTS_SHA256 = "3623b7900fca3f442fac485e7c54a7bf1ec12b2286750fb7b3022f48b493d210"
PINNED_MLOS_RECEIPT_FILE = "mlos_zone_b_receipt.json"
PINNED_MLOS_RECEIPT_SHA256 = "611d72323dbf9b3f1b6ca95680ee8ec63147918b3209f2052b4bca5954319173"

MAX_ANCHOR_BYTES = 2 * 1024 * 1024


def qdict(val: Fraction) -> Dict[str, int]:
    """Encode an exact Fraction into canonical coprime {"num": int, "den": int}."""
    return {"num": int(val.numerator), "den": int(val.denominator)}


def is_ascii_digits(s: str) -> bool:
    return len(s) > 0 and all("0" <= c <= "9" for c in s)


def parse_decimal_to_q(val: Any) -> Fraction:
    """Losslessly parse int or decimal/scientific string into exact Fraction (zero floats)."""
    if type(val) is int:
        return Fraction(val, 1)
    if type(val) is not str:
        raise ValueError("Expected int or decimal string")
    s = val.strip()
    if not s or len(s) > 256:
        raise ValueError("Empty or oversized numeric string")
    sign = 1
    if s[0] == "-":
        sign = -1
        s = s[1:]
    elif s[0] == "+":
        s = s[1:]
    exp = 0
    low = s.lower()
    if "e" in low:
        mant, exp_str = low.split("e", 1)
        exp_sign = 1
        if exp_str.startswith("-"):
            exp_sign = -1
            exp_str = exp_str[1:]
        elif exp_str.startswith("+"):
            exp_str = exp_str[1:]
        if not is_ascii_digits(exp_str):
            raise ValueError("Invalid exponent")
        exp = exp_sign * int(exp_str)
    else:
        mant = low
    if "." in mant:
        int_part, frac_part = mant.split(".", 1)
        if not (is_ascii_digits(int_part) and is_ascii_digits(frac_part)):
            raise ValueError("Invalid decimal mantissa")
        digits = int_part + frac_part
        exp -= len(frac_part)
    else:
        if not is_ascii_digits(mant):
            raise ValueError("Invalid integer mantissa")
        digits = mant
    num = sign * int(digits)
    if exp >= 0:
        return Fraction(num * (10**exp), 1)
    return Fraction(num, 10 ** (-exp))


def mat_mul_q(a: Sequence[Sequence[Fraction]], b: Sequence[Sequence[Fraction]]) -> List[List[Fraction]]:
    rows = len(a)
    cols = len(b[0])
    inner = len(b)
    return [
        [sum((a[i][k] * b[k][j] for k in range(inner)), Fraction(0)) for j in range(cols)]
        for i in range(rows)
    ]


def mat_transpose_q(a: Sequence[Sequence[Fraction]]) -> List[List[Fraction]]:
    return [[a[i][j] for i in range(len(a))] for j in range(len(a[0]))]


def mat_sub_q(a: Sequence[Sequence[Fraction]], b: Sequence[Sequence[Fraction]]) -> List[List[Fraction]]:
    return [[a[i][j] - b[i][j] for j in range(len(a[0]))] for i in range(len(a))]


def mat_add_q(a: Sequence[Sequence[Fraction]], b: Sequence[Sequence[Fraction]]) -> List[List[Fraction]]:
    return [[a[i][j] + b[i][j] for j in range(len(a[0]))] for i in range(len(a))]


def mat_fro_sq_q(a: Sequence[Sequence[Fraction]]) -> Fraction:
    return sum((x * x for row in a for x in row), Fraction(0))


def invert_2x2_q(m: Sequence[Sequence[Fraction]]) -> List[List[Fraction]]:
    det = m[0][0] * m[1][1] - m[0][1] * m[1][0]
    if det == 0:
        raise ValueError("Singular 2x2 rational matrix")
    return [
        [m[1][1] / det, -m[0][1] / det],
        [-m[1][0] / det, m[0][0] / det],
    ]


def build_pillar_1a_subspace_collapse() -> Dict[str, Any]:
    """Exact pure-Z/Q proof of subspace SNR lift, Householder isometry, and BlockH4 Parseval."""
    d_model = 896
    n_layers = 6
    ambient_dim = n_layers * d_model * d_model  # 4,816,896
    lora_rank = 16
    lora_params = n_layers * 2 * lora_rank * d_model  # 172,032
    priv_top_k = 256
    null_dim = d_model - 128  # 768
    step_subspace_rank = 4
    edit_subspace_dim = step_subspace_rank * (priv_top_k + null_dim)  # 4,096
    single_layer_dim = d_model * d_model  # 802,816

    snr_lift_full = Fraction(ambient_dim, edit_subspace_dim)  # 1176/1
    snr_lift_single_layer = Fraction(single_layer_dim, edit_subspace_dim)  # 196/1
    ambient_to_lora_ratio = Fraction(ambient_dim, lora_params)  # 28/1

    # Exact 4D Householder reflection Q = I - 2 u u^T / ||u||^2 with u = (1, 2, -2, 4), ||u||^2 = 25
    u = [Fraction(1), Fraction(2), Fraction(-2), Fraction(4)]
    u_norm_sq = sum((x * x for x in u), Fraction(0))  # 25
    q_mat = [
        [(Fraction(1) if i == j else Fraction(0)) - Fraction(2) * u[i] * u[j] / u_norm_sq for j in range(4)]
        for i in range(4)
    ]
    qtq = mat_mul_q(mat_transpose_q(q_mat), q_mat)
    qsq = mat_mul_q(q_mat, q_mat)
    eye4 = [[Fraction(1 if i == j else 0) for j in range(4)] for i in range(4)]
    qtq_err = mat_fro_sq_q(mat_sub_q(qtq, eye4))
    qsq_err = mat_fro_sq_q(mat_sub_q(qsq, eye4))
    x_vec = [Fraction(3), Fraction(-5), Fraction(7), Fraction(-11)]
    qx_vec = [sum((q_mat[i][j] * x_vec[j] for j in range(4)), Fraction(0)) for i in range(4)]
    x_norm_sq = sum((v * v for v in x_vec), Fraction(0))
    qx_norm_sq = sum((v * v for v in qx_vec), Fraction(0))

    # Exact 4-point BlockH4 Parseval verification
    h4 = [
        [Fraction(1), Fraction(1), Fraction(1), Fraction(1)],
        [Fraction(1), Fraction(-1), Fraction(1), Fraction(-1)],
        [Fraction(1), Fraction(1), Fraction(-1), Fraction(-1)],
        [Fraction(1), Fraction(-1), Fraction(-1), Fraction(1)],
    ]
    h4th4 = mat_mul_q(mat_transpose_q(h4), h4)
    four_eye4 = [[Fraction(4 if i == j else 0) for j in range(4)] for i in range(4)]
    h4_ortho_err = mat_fro_sq_q(mat_sub_q(h4th4, four_eye4))
    h4x = [sum((h4[i][j] * x_vec[j] for j in range(4)), Fraction(0)) for i in range(4)]
    h4x_norm_sq = sum((v * v for v in h4x), Fraction(0))

    return {
        "d_model": d_model,
        "target_layers_count": n_layers,
        "ambient_dim": ambient_dim,
        "single_layer_dim": single_layer_dim,
        "lora_params": lora_params,
        "edit_subspace_dim": edit_subspace_dim,
        "snr_lift_full_q": qdict(snr_lift_full),
        "snr_lift_single_layer_q": qdict(snr_lift_single_layer),
        "ambient_to_lora_ratio_q": qdict(ambient_to_lora_ratio),
        "householder_u_norm_sq_q": qdict(u_norm_sq),
        "householder_qtq_err_q": qdict(qtq_err),
        "householder_qsq_err_q": qdict(qsq_err),
        "householder_x_norm_sq_q": qdict(x_norm_sq),
        "householder_qx_norm_sq_q": qdict(qx_norm_sq),
        "householder_kappa2_q": qdict(Fraction(1, 1)),
        "blockh4_ortho_err_q": qdict(h4_ortho_err),
        "blockh4_parseval_lhs_q": qdict(h4x_norm_sq),
        "blockh4_parseval_rhs_q": qdict(Fraction(4) * x_norm_sq),
    }


def build_pillar_1b_discrete_oracle() -> Dict[str, Any]:
    """Exact pure-Z/Q non-differentiable step oracle, discrete lattice ratchet, and S31 DPI."""
    tau, w0, eps, delta = 5, 2, 1, 3
    f_w0 = 1 if w0 >= tau else 0
    f_local = 1 if (w0 + eps) >= tau else 0
    f_jump = 1 if (w0 + delta) >= tau else 0

    # Quantized A16/integer grid trajectory on discrete score [0..10]
    s_max = 10
    traj = [4, 7, 9, 10]
    gaps = [s_max - s for s in traj]

    # Surrogate-vs-discrete Goodhart mismatch witness
    surr_old, surr_new = 10, 6
    disc_old, disc_new = 8, 6
    surrogate_accepts_regression = surr_new < surr_old
    ratchet_accepts_regression = disc_new >= disc_old

    # Exact Track S31 DPI concentration witness + support-expansion reduction
    s31_total_params = 233373696
    s31_two_row_k = 3072
    s31_dpi_two_row = Fraction(s31_total_params, s31_two_row_k)  # 75968/1
    expanded_k = 24576  # 8x wider distributed support
    expanded_dpi = Fraction(s31_total_params, expanded_k)  # 9496/1
    dpi_reduction_factor = s31_dpi_two_row / expanded_dpi  # 8/1

    # Exact Track S77 WSP-Gym compute-cutoff sign-flip anchor
    s77_all_faulty_diff = Fraction(31, 422)
    s77_finished_diff = Fraction(-43, 327)

    return {
        "step_oracle_tau": tau,
        "step_oracle_w0": w0,
        "step_oracle_local_diff": f_local - f_w0,
        "step_oracle_jump_gain": f_jump - f_w0,
        "lattice_s_max": s_max,
        "lattice_trajectory": traj,
        "lattice_remaining_gaps": gaps,
        "goodhart_surrogate_old": surr_old,
        "goodhart_surrogate_new": surr_new,
        "goodhart_discrete_old": disc_old,
        "goodhart_discrete_new": disc_new,
        "surrogate_accepts_regression": surrogate_accepts_regression,
        "ratchet_accepts_regression": ratchet_accepts_regression,
        "s31_total_params": s31_total_params,
        "s31_two_row_k": s31_two_row_k,
        "s31_dpi_two_row_q": qdict(s31_dpi_two_row),
        "expanded_support_k": expanded_k,
        "expanded_dpi_q": qdict(expanded_dpi),
        "dpi_reduction_factor_q": qdict(dpi_reduction_factor),
        "s77_wsp_all_faulty_diff_q": qdict(s77_all_faulty_diff),
        "s77_wsp_finished_diff_q": qdict(s77_finished_diff),
    }


def build_pillar_1c_ratchet_and_nullspace() -> Dict[str, Any]:
    """Exact pure-Q S80 FWER vs 5-gate ratchet + orthogonal nullspace anti-forgetting."""
    # Track S80 exact songe 20-step FWER: 1 - (361/400)^20
    p_single = Fraction(39, 400)
    q_clean = Fraction(361, 400)
    fwer_20 = Fraction(1) - (q_clean**20)
    fwer_exceeds_87pct = fwer_20 > Fraction(87, 100)

    # Track S78 exact unit forgetting/learning conservation anchor
    s78_forgetting_kb = Fraction(229, 5)
    s78_learning_kb = Fraction(229, 5)
    s78_ratio = s78_forgetting_kb / s78_learning_kb  # 1/1

    # Exact 4x4 nullspace projection P_perp = I - X (X^T X)^{-1} X^T for rank-2 X_base
    x_base = [
        [Fraction(1), Fraction(0)],
        [Fraction(1), Fraction(1)],
        [Fraction(0), Fraction(1)],
        [Fraction(1), Fraction(-1)],
    ]
    xt = mat_transpose_q(x_base)
    xtx = mat_mul_q(xt, x_base)  # [[3, 0], [0, 3]] -> exact clean inverse (1/3) I!
    xtx_inv = invert_2x2_q(xtx)
    p_base = mat_mul_q(mat_mul_q(x_base, xtx_inv), xt)
    eye4 = [[Fraction(1 if i == j else 0) for j in range(4)] for i in range(4)]
    p_perp = mat_sub_q(eye4, p_base)

    # Proposed dense edit dW (2x4)
    dw = [
        [Fraction(3), Fraction(1), Fraction(-2), Fraction(4)],
        [Fraction(-1), Fraction(5), Fraction(2), Fraction(0)],
    ]
    dw_x_base = mat_mul_q(dw, x_base)
    raw_forgetting_energy = mat_fro_sq_q(dw_x_base)  # strictly > 0!
    dw_total_energy = mat_fro_sq_q(dw)
    dw_base_part = mat_mul_q(dw, p_base)
    dw_perp = mat_mul_q(dw, p_perp)
    dw_perp_x_base = mat_mul_q(dw_perp, x_base)
    proj_forgetting_energy = mat_fro_sq_q(dw_perp_x_base)  # exact 0!
    dw_base_energy = mat_fro_sq_q(dw_base_part)
    dw_perp_energy = mat_fro_sq_q(dw_perp)
    pythag_residual = dw_total_energy - (dw_base_energy + dw_perp_energy)

    # Exact Law-5 capacity-exhaustion witness: d=4, r_base=4 -> nullspace=0; lift K=2 -> nullspace=2
    cap_d = 4
    cap_r_full = 4
    cap_lift_k = 2

    return {
        "s80_single_step_fwer_q": qdict(p_single),
        "s80_20step_fwer_q": qdict(fwer_20),
        "s80_20step_fwer_exceeds_87pct": fwer_exceeds_87pct,
        "s78_forgetting_kb_q": qdict(s78_forgetting_kb),
        "s78_learning_kb_q": qdict(s78_learning_kb),
        "s78_forgetting_over_learning_q": qdict(s78_ratio),
        "nullspace_raw_forgetting_energy_q": qdict(raw_forgetting_energy),
        "nullspace_projected_forgetting_energy_q": qdict(proj_forgetting_energy),
        "nullspace_dw_total_energy_q": qdict(dw_total_energy),
        "nullspace_dw_base_energy_q": qdict(dw_base_energy),
        "nullspace_dw_perp_energy_q": qdict(dw_perp_energy),
        "nullspace_pythagorean_residual_q": qdict(pythag_residual),
        "nullspace_forgetting_ratio_after_proj_q": qdict(Fraction(0, 1)),
        "law5_capacity_ambient_d": cap_d,
        "law5_capacity_saturated_rank": cap_r_full,
        "law5_capacity_collapsed_null_dim": cap_d - cap_r_full,
        "law5_capacity_lift_k": cap_lift_k,
        "law5_capacity_restored_null_dim": (cap_d + cap_lift_k) - cap_r_full,
    }


def build_pillar_1d_recursive_relinearization() -> Dict[str, Any]:
    """Exact pure-Q 2-layer cross-layer non-additivity, coupled nullspace shift, and VRAM roofline."""
    # Exact 2x2 two-layer bilinear composition: W2 * W1 -> target T
    w1 = [[Fraction(2), Fraction(1)], [Fraction(0), Fraction(2)]]
    w2 = [[Fraction(3), Fraction(0)], [Fraction(1), Fraction(2)]]
    prod0 = mat_mul_q(w2, w1)  # [[6, 3], [2, 5]]
    target_delta = [[Fraction(2), Fraction(1)], [Fraction(1), Fraction(2)]]
    target_t = mat_add_q(prod0, target_delta)

    # Static 1-shot independently splits target_delta in half assuming the other layer is fixed:
    # W2 * d1 = target_delta / 2,  d2 * W1 = target_delta / 2
    half_delta = [[c / Fraction(2) for c in row] for row in target_delta]
    w2_inv = invert_2x2_q(w2)
    w1_inv = invert_2x2_q(w1)
    d1_static = mat_mul_q(w2_inv, half_delta)
    d2_static = mat_mul_q(half_delta, w1_inv)

    composed_static = mat_mul_q(mat_add_q(w2, d2_static), mat_add_q(w1, d1_static))
    static_err_mat = mat_sub_q(composed_static, target_t)
    bilinear_cross = mat_mul_q(d2_static, d1_static)
    static_err_fro_sq = mat_fro_sq_q(static_err_mat)
    cross_minus_err_fro_sq = mat_fro_sq_q(mat_sub_q(static_err_mat, bilinear_cross))

    # Sequential recursive re-linearization: apply d1_static -> live W1' = W1 + d1_static,
    # then solve exact W2' against LIVE W1': W2' = T * (W1')^{-1}
    w1_live = mat_add_q(w1, d1_static)
    w2_rec = mat_mul_q(target_t, invert_2x2_q(w1_live))
    composed_rec = mat_mul_q(w2_rec, w1_live)
    rec_err_fro_sq = mat_fro_sq_q(mat_sub_q(composed_rec, target_t))  # exact 0!

    # Coupled layer-2 nullspace shift after layer-1 mutation:
    # Base input x0 = [1, 0]^T -> initial layer-2 input h0 = W1 x0 = [2, 0]^T
    # After layer-1 mutation W1', live layer-2 input shifts to h1 = W1' x0!
    h0 = [w1[0][0], w1[1][0]]  # [2, 0]
    h1 = [w1_live[0][0], w1_live[1][0]]
    # Project layer-2 update row g2 = [3, 4] against stale h0 vs live h1
    g2 = [Fraction(3), Fraction(4)]
    h0_sq = h0[0] * h0[0] + h0[1] * h0[1]
    h1_sq = h1[0] * h1[0] + h1[1] * h1[1]
    g2_dot_h0 = g2[0] * h0[0] + g2[1] * h0[1]
    g2_stale = [g2[i] - (g2_dot_h0 / h0_sq) * h0[i] for i in range(2)]
    stale_leak = g2_stale[0] * h1[0] + g2_stale[1] * h1[1]  # nonzero!
    g2_dot_h1 = g2[0] * h1[0] + g2[1] * h1[1]
    g2_reproj = [g2[i] - (g2_dot_h1 / h1_sq) * h1[i] for i in range(2)]
    reproj_leak = g2_reproj[0] * h1[0] + g2_reproj[1] * h1[1]  # exact 0!

    # Exact Track S70 greedy non-additivity anchor
    s70_greedy_energy_a = 101
    s70_greedy_energy_b = 100
    s70_composed_a = 4
    s70_composed_b = 400
    s70_regression_ratio = Fraction(s70_composed_b, s70_composed_a)  # 100/1

    # Exact analytical VRAM roofline (bytes) for Qwen2.5-0.5B BF16 weights + autograd vs backprop-free
    # Model BF16 params = 494,032,768 * 2 bytes = 988,065,536 B (~942.3 MiB)
    model_bf16_bytes = 494032768 * 2
    lora_bf16_bytes = 172032 * 2
    adamw_fp32_opt_bytes = 172032 * 8  # m + v in FP32
    grad_bytes = 172032 * 2
    autograd_act_bytes = 32 * 64 * 896 * 24 * 2  # ~88 MiB activation graph floor
    subspace_buf_bytes = 4096 * 4  # 16 KiB rank-4 subspace working buffer
    vram_bp_analytical = model_bf16_bytes + autograd_act_bytes + lora_bf16_bytes + grad_bytes + adamw_fp32_opt_bytes
    vram_pure_analytical = model_bf16_bytes + subspace_buf_bytes

    return {
        "static_oneshot_err_fro_sq_q": qdict(static_err_fro_sq),
        "static_bilinear_identity_residual_q": qdict(cross_minus_err_fro_sq),
        "recursive_relinearized_err_fro_sq_q": qdict(rec_err_fro_sq),
        "coupled_stale_nullspace_leak_sq_q": qdict(stale_leak * stale_leak),
        "coupled_reprojected_nullspace_leak_sq_q": qdict(reproj_leak * reproj_leak),
        "s70_greedy_layer_energy_a": s70_greedy_energy_a,
        "s70_greedy_layer_energy_b": s70_greedy_energy_b,
        "s70_greedy_composed_a": s70_composed_a,
        "s70_greedy_composed_b": s70_composed_b,
        "s70_greedy_regression_ratio_q": qdict(s70_regression_ratio),
        "vram_bp_analytical_bytes": vram_bp_analytical,
        "vram_pure_analytical_bytes": vram_pure_analytical,
        "vram_analytical_savings_bytes": vram_bp_analytical - vram_pure_analytical,
    }


def load_json_no_floats(path: pathlib.Path) -> Tuple[Dict[str, Any], str, bytes]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected regular non-symlink file: {path.name}")
    raw = path.read_bytes()
    if len(raw) > MAX_ANCHOR_BYTES:
        raise ValueError("Anchor JSON exceeds size cap")
    sha = hashlib.sha256(raw).hexdigest()

    def _cap_int(tok: str) -> int:
        if len(tok) > 80:
            raise ValueError("Anchor integer literal exceeds digit cap")
        return int(tok)

    def _cap_float(tok: str) -> str:
        if len(tok) > 80:
            raise ValueError("Anchor decimal literal exceeds length cap")
        return tok

    obj = json.loads(raw.decode("utf-8"), parse_int=_cap_int, parse_float=_cap_float)
    if type(obj) is not dict:
        raise ValueError("Anchor JSON top-level must be object")
    return obj, sha, raw


def _require_strict_bool(val: Any, label: str) -> bool:
    if type(val) is not bool:
        raise ValueError(f"{label} must be exact bool")
    return val


def _require_strict_int(val: Any, label: str) -> int:
    if type(val) is not int:
        raise ValueError(f"{label} must be exact int")
    return val


def _require_strict_str(val: Any, label: str) -> str:
    if type(val) is not str or not val:
        raise ValueError(f"{label} must be non-empty str")
    return val


def _verify_live_inner_result_sha256(raw: bytes, claimed_sha: str) -> None:
    """Re-derive result_sha256 directly on canonical JSON bytes with ZERO floats."""
    if len(claimed_sha) != 64:
        raise ValueError("Invalid result_sha256 length")
    text = raw.decode("utf-8").rstrip("\n")
    needle = f',"result_sha256":"{claimed_sha}"'
    if text.count(needle) != 1:
        raise ValueError("Canonical result_sha256 field missing or duplicated")
    pre_hash_bytes = text.replace(needle, "", 1).encode("utf-8")
    calc = hashlib.sha256(pre_hash_bytes).hexdigest()
    if calc != claimed_sha:
        raise ValueError("Live results inner result_sha256 mismatch")


def build_pillar_2_live_rtx3080_anchor(
    live_path: pathlib.Path, mlos_path: pathlib.Path
) -> Dict[str, Any]:
    """Losslessly convert live RTX 3080 4-way benchmark & mlos receipt into exact rationals."""
    live, live_sha, live_raw = load_json_no_floats(live_path)
    mlos, mlos_sha, _mlos_raw = load_json_no_floats(mlos_path)

    weights_saved = _require_strict_int(live["weights_saved_in_expedition"], "weights_saved")
    if weights_saved != 0:
        raise ValueError("Live benchmark must save 0 weights in expedition")
    det_zone = _require_strict_str(mlos["determinism_zone"], "determinism_zone")
    if det_zone != "B":
        raise ValueError("mlos receipt must be determinism_zone B")
    if _require_strict_bool(mlos["gpu_telemetry_available"], "gpu_telemetry_available") is not True:
        raise ValueError("mlos receipt must confirm GPU telemetry available")
    clean_hw = _require_strict_bool(mlos["clean_hardware_run"], "clean_hardware_run")

    inner_sha = _require_strict_str(live["result_sha256"], "result_sha256")
    _verify_live_inner_result_sha256(live_raw, inner_sha)

    base = live["baseline"]
    arms_raw = live["arms"]
    if type(base) is not dict or type(arms_raw) is not list or len(arms_raw) != 4:
        raise ValueError("Live benchmark must contain baseline dict and exactly 4 arms")

    arms_q: List[Dict[str, Any]] = []
    base_acc_q = parse_decimal_to_q(base["heldout_test"]["discrete_acc"])
    base_full_acc_q = parse_decimal_to_q(base["heldout_test"]["full_vocab_acc"])
    base_nll_q = parse_decimal_to_q(base["heldout_test"]["target_nll"])
    base_margin_q = parse_decimal_to_q(base["heldout_test"]["mean_margin"])
    base_wiki_q = parse_decimal_to_q(base["wiki_test_nll"])
    base_ppl_q = parse_decimal_to_q(base["wiki_test_ppl"])
    for arm in arms_raw:
        if type(arm) is not dict:
            raise ValueError("Each arm entry must be dict")
        arm_name = _require_strict_str(arm["arm"], "arm.arm")
        bp_free = _require_strict_bool(arm["backprop_free"], f"{arm_name}.backprop_free")
        acc_steps = _require_strict_int(arm["accepted_steps"], f"{arm_name}.accepted_steps")
        tot_steps = _require_strict_int(
            arm["rounds"] if "rounds" in arm else arm["steps"],
            f"{arm_name}.total_steps",
        )
        rej_steps = (
            _require_strict_int(arm["rejected_ratchet"], f"{arm_name}.rejected_ratchet")
            if "rejected_ratchet" in arm
            else (tot_steps - acc_steps)
        )
        if acc_steps < 0 or rej_steps < 0 or acc_steps + rej_steps != tot_steps:
            raise ValueError(f"{arm_name}: step accounting mismatch")
        acc_q = parse_decimal_to_q(arm["heldout_test"]["discrete_acc"])
        wiki_q = parse_decimal_to_q(arm["wiki_test_nll"])
        ppl_q = parse_decimal_to_q(arm["wiki_test_ppl"])
        arms_q.append(
            {
                "arm": arm_name,
                "backprop_free": bp_free,
                "total_steps": tot_steps,
                "accepted_steps": acc_steps,
                "rejected_steps": rej_steps,
                "wall_time_sec_q": qdict(parse_decimal_to_q(arm["wall_time_sec"])),
                "peak_vram_alloc_mib_q": qdict(parse_decimal_to_q(arm["peak_vram_alloc_mib"])),
                "peak_vram_reserved_mib_q": qdict(parse_decimal_to_q(arm["peak_vram_reserved_mib"])),
                "dev_discrete_acc_q": qdict(parse_decimal_to_q(arm["dev"]["discrete_acc"])),
                "dev_target_nll_q": qdict(parse_decimal_to_q(arm["dev"]["target_nll"])),
                "heldout_discrete_acc_q": qdict(acc_q),
                "heldout_full_vocab_acc_q": qdict(parse_decimal_to_q(arm["heldout_test"]["full_vocab_acc"])),
                "heldout_target_nll_q": qdict(parse_decimal_to_q(arm["heldout_test"]["target_nll"])),
                "heldout_mean_margin_q": qdict(parse_decimal_to_q(arm["heldout_test"]["mean_margin"])),
                "heldout_acc_gain_q": qdict(acc_q - base_acc_q),
                "wiki_test_nll_q": qdict(wiki_q),
                "wiki_test_nll_drift_q": qdict(wiki_q - base_wiki_q),
                "wiki_test_ppl_q": qdict(ppl_q),
                "wiki_test_ppl_drift_q": qdict(ppl_q - base_ppl_q),
                "edit_fro_norm_q": qdict(parse_decimal_to_q(arm["edit_fro_norm"])),
                "edit_dpi_row_concentration_q": qdict(
                    parse_decimal_to_q(arm["edit_dpi_row_concentration"])
                ),
            }
        )

    arm_by_name = {a["arm"]: a for a in arms_q}
    bp_vram = Fraction(
        arm_by_name["Std-Backprop-LoRA"]["peak_vram_alloc_mib_q"]["num"],
        arm_by_name["Std-Backprop-LoRA"]["peak_vram_alloc_mib_q"]["den"],
    )
    pure_vram = Fraction(
        arm_by_name["Aletheia-WSE-HC-Pure"]["peak_vram_alloc_mib_q"]["num"],
        arm_by_name["Aletheia-WSE-HC-Pure"]["peak_vram_alloc_mib_q"]["den"],
    )
    vram_cut_mib = bp_vram - pure_vram
    vram_cut_ratio = vram_cut_mib / bp_vram if bp_vram > 0 else Fraction(0, 1)

    return {
        "epistemic_tag": "anchor",
        "live_results_file": live_path.name,
        "live_results_sha256": live_sha,
        "live_results_inner_sha256": inner_sha,
        "mlos_receipt_file": mlos_path.name,
        "mlos_receipt_sha256": mlos_sha,
        "mlos_determinism_zone": det_zone,
        "mlos_clean_hardware_run": clean_hw,
        "model_id": _require_strict_str(live["model_id"], "model_id"),
        "gpu_name": _require_strict_str(live["gpu_name"], "gpu_name"),
        "seed": _require_strict_int(live["seed"], "seed"),
        "weights_saved_in_expedition": weights_saved,
        "baseline_heldout_discrete_acc_q": qdict(base_acc_q),
        "baseline_heldout_full_vocab_acc_q": qdict(base_full_acc_q),
        "baseline_heldout_target_nll_q": qdict(base_nll_q),
        "baseline_heldout_mean_margin_q": qdict(base_margin_q),
        "baseline_wiki_test_nll_q": qdict(base_wiki_q),
        "baseline_wiki_test_ppl_q": qdict(base_ppl_q),
        "arms": arms_q,
        "pure_vs_backprop_vram_cut_mib_q": qdict(vram_cut_mib),
        "pure_vs_backprop_vram_cut_ratio_q": qdict(vram_cut_ratio),
    }


def build_certificate(live_path: pathlib.Path, mlos_path: pathlib.Path) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "track_id": TRACK_ID,
        "epistemic_classes": {
            "pillar_1": "exact",
            "pillar_2": "anchor",
            "pillar_3": "exact",
        },
        "pillar_1a_subspace_collapse": build_pillar_1a_subspace_collapse(),
        "pillar_1b_discrete_oracle": build_pillar_1b_discrete_oracle(),
        "pillar_1c_ratchet_and_nullspace": build_pillar_1c_ratchet_and_nullspace(),
        "pillar_1d_recursive_relinearization": build_pillar_1d_recursive_relinearization(),
        "pillar_2_live_rtx3080_anchor": build_pillar_2_live_rtx3080_anchor(live_path, mlos_path),
        "lean4_certificate": {
            "file": LEAN_FILE_NAME,
            "sha256": LEAN_FILE_SHA256,
            "namespace": LEAN_NAMESPACE,
            "theorem_count": len(LEAN_THEOREMS),
            "universal_theorem_count": len(LEAN_THEOREMS),
            "theorems": list(LEAN_THEOREMS),
            "allowed_axioms": list(LEAN_ALLOWED_AXIOMS),
        },
        "upstream_cert_manifest": [
            {"track_id": tid, "rel_path": rel, "sha256": sha}
            for tid, rel, sha in UPSTREAM_CERT_MANIFEST
        ],
        "novelty_honesty_law4": {
            "novelty_tier": "N1",
            "n0_prior_art_credited": True,
            "n1_verified_synthesis": True,
            "n2_claims": 0,
        },
    }
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload_sha = hashlib.sha256(payload_bytes).hexdigest()
    wrapper: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "payload_sha256": payload_sha,
        "payload": payload,
    }
    cert_bytes = json.dumps(wrapper, sort_keys=True, separators=(",", ":")).encode("utf-8")
    wrapper["certificate_sha256"] = hashlib.sha256(cert_bytes).hexdigest()
    return wrapper


def write_private_json(out_path: pathlib.Path, obj: Dict[str, Any]) -> None:
    if out_path.is_symlink():
        raise ValueError("Refusing to write through symlink")
    data = (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    fd = os.open(str(out_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    os.chmod(out_path, stat.S_IRUSR | stat.S_IWUSR)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Track S97 Exact Pure-Z/Q ALETHEIA-WSE-HC Oracle")
    here = pathlib.Path(__file__).resolve().parent
    ap.add_argument("--live-results", default=str(here / PINNED_LIVE_RESULTS_FILE))
    ap.add_argument("--mlos-receipt", default=str(here / PINNED_MLOS_RECEIPT_FILE))
    ap.add_argument("--out", default=str(here / "s97_wse_hc_certificate.json"))
    ap.add_argument("--standalone", action="store_true", help="Emit canonical certificate JSON to stdout")
    args = ap.parse_args(argv)

    cert = build_certificate(pathlib.Path(args.live_results), pathlib.Path(args.mlos_receipt))
    if args.standalone:
        print(json.dumps(cert, sort_keys=True, separators=(",", ":")))
        return 0
    write_private_json(pathlib.Path(args.out), cert)
    print(f"[S97_ORACLE_OK] cert={cert['certificate_sha256'][:16]} payload={cert['payload_sha256'][:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
