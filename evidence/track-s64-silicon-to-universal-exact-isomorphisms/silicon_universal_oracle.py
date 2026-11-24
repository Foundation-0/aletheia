#!/usr/bin/env python3
"""
Pure-Z/Q Exact-Operator Oracle:
Silicon-to-Universal Exact-Operator Correspondence & Obstruction Atlas.

Strict verification standards:
  - Python 3 standard library only, zero external dependencies.
  - Zero AST float literals, zero float() conversions, zero bare asserts,
    zero str.isdigit() calls (exact ASCII digit validation only).
  - Exact integer and rational (fractions.Fraction) arithmetic across all six
    universal operator pillars and explicit obstruction witnesses.
  - Strict privacy locks: zero audio capture, zero camera access, zero display
    or brightness mutation.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import math
from typing import Any

CERT_SCHEMA = "aletheia.s64.silicon_universal_atlas.certificate.v1"
CERT_TRACK_ID = "TRACK-S64-SILICON-UNIVERSAL-EXACT-ISOMORPHISMS"

# Exact SI-2019 Boltzmann constant: k_B = 1.380649e-23 J/K = 1380649 / 10^29 J/K
KB_EXACT_J_PER_K = Fraction(1380649, 10**29)
# Certified 12-digit rational bracket for ln(2): 0.693147180559 < ln(2) < 0.693147180560
LN2_BRACKET_LO = Fraction(693147180559, 10**12)
LN2_BRACKET_HI = Fraction(693147180560, 10**12)

# Frozen SHA-256 digests of live silicon capture artifacts (Ring-0 mlos stamped)
PINNED_S64_DIGESTS: dict[str, str] = {
    "granular_silicon_microprobe_c": "3e5d6768c252df3691b8734fdb3beebab79d2728cb9cb14b43a793ed1367b239",
    "granular_silicon_capture_json": "c70602cad0159d9619b710870c682997d293fb132cb75cbb3042ee8a63d373ac",
    "mlos_zone_b_receipt_json": "ebbb3ec57a0dfee80df225ee766e5e28072ba92b564004bcde08a5c8f3945cf5",
    "mlos_receipt_inner_sha256": "f8fde165220a3062e080027a5fd06cf04663f37d55fbaa3e89d7e18e530264d7",
    "mlos_profile_sha256": "566c9192d38682a0ec4d652a63a3510aaefb9dc20ef91ae9bdc6d4abbbf5cbe2",
}

# Read-only frozen cross-study certificate anchors (exact disk SHA-256 digests)
PINNED_CROSS_TRACK_CERTS: dict[str, str] = {
    "s53_pre_rapl_baseline_cert": "ac191f235fec87357ee7a73987483ab5d1019721245cae1c1c6b2a7a1d44a8d4",
    "s53_sensor_tomography_cert": "b127d37b3f94a64bd8afbcb39f386d42e9f2ffcc6e542d86a8203909afdbdac7",
    "s53_phase2_controlled_cert": "6379283a41723d96637c83a7217e099da477baddc9715ef68dcbb55913c47338",
    "s58_aletheion_live_llm_cert": "9b6c720c783cac8aaa3793e80ee5df87710c07bfc859f702cdabf428d3727620",
    "s60_rtx3080_qwen15b_cert": "ad661dd42dcceb4e0943244b46e996c7f7e234560e5d8cfe2385cb85b84d724a",
}


# ---------------------------------------------------------------------------
# Pure-Z/Q Helpers & Canonical JSON Serialization
# ---------------------------------------------------------------------------

def q_str(q: Fraction) -> str:
    """Serialize an exact reduced Fraction as 'p' or 'p/q'."""
    if q.denominator == 1:
        return str(q.numerator)
    return f"{q.numerator}/{q.denominator}"


def round_q_1e6(q: Fraction) -> Fraction:
    """Exact integer round-half-to-even to 10^-6 precision (zero floats)."""
    scaled = q * 1_000_000
    n, d = scaled.numerator, scaled.denominator
    quot, rem = divmod(abs(n), d)
    if 2 * rem > d or (2 * rem == d and (quot % 2 == 1)):
        quot += 1
    if n < 0:
        quot = -quot
    return Fraction(quot, 1_000_000)


def landauer_integer_bracket(energy_j: Fraction, temp_k: Fraction) -> list[int]:
    """Return exact integer bracket [floor, ceil] for E / (k_B * T * ln 2)."""
    lo_q = energy_j / (KB_EXACT_J_PER_K * temp_k * LN2_BRACKET_HI)
    hi_q = energy_j / (KB_EXACT_J_PER_K * temp_k * LN2_BRACKET_LO)
    lo_int = lo_q.numerator // lo_q.denominator
    hi_int = (hi_q.numerator + hi_q.denominator - 1) // hi_q.denominator
    return [lo_int, hi_int]


def canonical_json_bytes(obj: Any) -> bytes:
    """Deterministic UTF-8 canonical JSON ending with a single LF."""
    return (
        json.dumps(
            obj,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Pure-Z/Q Universal Operator Primitives (Reusable for Live Capture Replay)
# ---------------------------------------------------------------------------

def compute_s39_prism_exact(seq: list[int]) -> list[Fraction]:
    """Exact Track S39 Nyquist-third prism R_n = ||Delta^n x||_2^2 / ||Delta^{n-1} x||_2^2 (n=1..5)."""
    if len(seq) < 6:
        raise ValueError("S39 prism requires at least 6 samples")
    cur = list(seq)
    energies = [sum(v * v for v in cur)]
    for _ in range(5):
        cur = [cur[i + 1] - cur[i] for i in range(len(cur) - 1)]
        energies.append(sum(v * v for v in cur))
    return [Fraction(energies[k], energies[k - 1]) for k in range(1, 6)]


def compute_haar_octave_ratios_exact(seq: list[int]) -> list[Fraction]:
    """Exact normalized Haar octave variance ratios V_{j+1}/V_j on power-of-two length."""
    arr = list(seq)
    variances: list[Fraction] = []
    while len(arr) >= 2:
        half = len(arr) // 2
        details = [arr[2 * i + 1] - arr[2 * i] for i in range(half)]
        variances.append(Fraction(sum(v * v for v in details), half))
        arr = [arr[2 * i] + arr[2 * i + 1] for i in range(half)]
    norm = [variances[k] / (1 << k) for k in range(len(variances))]
    return [norm[k + 1] / norm[k] for k in range(len(norm) - 1)]


def deterministic_coprime_shuffle(seq: list[int], stride: int) -> list[int]:
    """Amplitude-preserving deterministic permutation using a stride coprime to len(seq)."""
    length = len(seq)
    if length < 1 or math.gcd(stride, length) != 1:
        raise ValueError("stride must be coprime to positive sequence length")
    return [seq[(i * stride) % length] for i in range(length)]


def compute_corr_r2_exact(x: list[int], y: list[int]) -> Fraction:
    """Exact rational squared Pearson correlation R^2(x, y) (scale/shift invariant)."""
    n = len(x)
    sx, sy = sum(x), sum(y)
    dx = [n * v - sx for v in x]
    dy = [n * v - sy for v in y]
    num = sum(a * b for a, b in zip(dx, dy))
    den = sum(a * a for a in dx) * sum(b * b for b in dy)
    return Fraction(num * num, den)


def compute_green_2area_exact(x: list[int], y: list[int]) -> tuple[int, int]:
    """Exact discrete Green's theorem 2*Area = sum (y_{t+1}+y_t)(x_{t+1}-x_t) (open, closed)."""
    n = len(x)
    open_area = sum((y[i + 1] + y[i]) * (x[i + 1] - x[i]) for i in range(n - 1))
    closed_area = open_area + (y[0] + y[-1]) * (x[0] - x[-1])
    return open_area, closed_area


def compute_scale_invariant_schur_exact(
    a_cols: list[list[Fraction]],
    b_cols: list[list[Fraction]],
    lam: Fraction = Fraction(1, 20),
) -> tuple[list[Fraction], Fraction, Fraction, Fraction]:
    """
    Exact square-root-free Stage-A scale-invariant Schur complement S_{A|B}.

    Regularizes C_BB diagonally by lam * diag(C_BB) so every residual variance
    ratio eta_i = S_{ii}/C_{ii}, raw off-diagonal R^2, and residual off-diagonal
    partial correlation rho^2 is algebraically invariant under arbitrary
    permutations and positive rational affine rescalings of every channel.
    """
    all_cols = a_cols + b_cols
    da, db = len(a_cols), len(b_cols)
    m = len(all_cols[0])
    centered: list[list[Fraction]] = []
    for col in all_cols:
        total = sum(col, Fraction(0))
        centered.append([m * v - total for v in col])
    dim = da + db
    cov = [
        [sum((centered[i][t] * centered[j][t] for t in range(m)), Fraction(0)) for j in range(dim)]
        for i in range(dim)
    ]
    mat = [
        [
            cov[da + p][da + q] + (lam * cov[da + p][da + p] if p == q else Fraction(0))
            for q in range(db)
        ]
        for p in range(db)
    ]
    aug = [
        mat[p][:] + [Fraction(1 if p == q else 0) for q in range(db)]
        for p in range(db)
    ]
    for col_idx in range(db):
        piv = col_idx
        while aug[piv][col_idx] == 0:
            piv += 1
        aug[col_idx], aug[piv] = aug[piv], aug[col_idx]
        pv = aug[col_idx][col_idx]
        aug[col_idx] = [val / pv for val in aug[col_idx]]
        for row_idx in range(db):
            if row_idx != col_idx:
                fac = aug[row_idx][col_idx]
                aug[row_idx] = [
                    aug[row_idx][c] - fac * aug[col_idx][c] for c in range(2 * db)
                ]
    m_inv = [row[db:] for row in aug]
    schur = [[Fraction(0)] * da for _ in range(da)]
    for i in range(da):
        for j in range(da):
            sub = Fraction(0)
            for p in range(db):
                cip = cov[i][da + p]
                for q in range(db):
                    sub += cip * m_inv[p][q] * cov[da + q][j]
            schur[i][j] = cov[i][j] - sub
    etas = [schur[i][i] / cov[i][i] for i in range(da)]
    raw_r2s = [
        cov[i][j] * cov[i][j] / (cov[i][i] * cov[j][j])
        for i in range(da)
        for j in range(i + 1, da)
    ]
    res_r2s = [
        schur[i][j] * schur[i][j] / (schur[i][i] * schur[j][j])
        for i in range(da)
        for j in range(i + 1, da)
    ]
    return (
        etas,
        sum(etas, Fraction(0)) / da,
        sum(raw_r2s, Fraction(0)) / len(raw_r2s),
        sum(res_r2s, Fraction(0)) / len(res_r2s),
    )


# ---------------------------------------------------------------------------
# Pillar-0 Exact Universal Algebra Witnesses (Computed Live in Pure Z/Q)
# ---------------------------------------------------------------------------

def verify_exact_s39_analytic_manifolds() -> dict[str, Any]:
    """Derive exact White Noise and Random Walk S39 prism values from binomial sums."""
    wn_exact: list[Fraction] = []
    rw_exact: list[Fraction] = []
    for n in range(2, 6):
        # White noise variance of Delta^n is sum_{k=0}^n C(n,k)^2 = C(2n,n)
        e_n = sum(math.comb(n, k) ** 2 for k in range(n + 1))
        e_prev = sum(math.comb(n - 1, k) ** 2 for k in range(n))
        wn_exact.append(Fraction(e_n, e_prev))
        # Random walk Delta^n = Delta^{n-1}(white noise)
        e_rw_n = sum(math.comb(n - 1, k) ** 2 for k in range(n))
        e_rw_prev = sum(math.comb(n - 2, k) ** 2 for k in range(n - 1))
        rw_exact.append(Fraction(e_rw_n, e_rw_prev))
    return {
        "nyquist_ceiling_q": q_str(Fraction(4, 1)),
        "unity_cutoff_period_samples": 6,
        "white_noise_r2_to_r5_q": [q_str(v) for v in wn_exact],
        "random_walk_r2_to_r5_q": [q_str(v) for v in rw_exact],
        "wn_formula_matches_binomial": all(
            wn_exact[n - 2] == Fraction(2 * (2 * n - 1), n) for n in range(2, 6)
        ),
        "rw_formula_matches_binomial": all(
            rw_exact[n - 2] == Fraction(2 * (2 * n - 3), n - 1) for n in range(2, 6)
        ),
    }


def verify_exact_code_and_lattice_geometry() -> dict[str, Any]:
    """Exhaustively enumerate C_[16,11,4], RM(1,4) containment, and the 240 roots of E_8."""
    # Extended Hamming [16,11,4] parity-check bitmasks over 16 coordinates
    masks = [
        0xFFFF,  # overall parity
        0xAAAA,  # bit 0 of index
        0xCCCC,  # bit 1 of index
        0xF0F0,  # bit 2 of index
        0xFF00,  # bit 3 of index
    ]
    weight_enum: dict[str, int] = {}
    codeword_count = 0
    min_nonzero_wt = 16
    for v in range(65536):
        ok = True
        for m in masks:
            if (v & m).bit_count() & 1:
                ok = False
                break
        if ok:
            codeword_count += 1
            wt = v.bit_count()
            key = str(wt)
            weight_enum[key] = weight_enum.get(key, 0) + 1
            if 0 < wt < min_nonzero_wt:
                min_nonzero_wt = wt

    # First-order Reed-Muller RM(1,4): 32 affine Boolean functions on F_2^4
    rm_codewords = 0
    rm_in_c16 = 0
    for c0 in (0, 1):
        for a in range(16):
            vec = 0
            for x in range(16):
                bit = (c0 ^ ((a & x).bit_count() & 1)) & 1
                vec |= bit << x
            rm_codewords += 1
            if all(((vec & m).bit_count() & 1) == 0 for m in masks):
                rm_in_c16 += 1

    # E_8 minimal roots in doubled integer coordinates 2x in Z^8 with ||2x||^2 = 8
    e8_int_roots = 0
    for i in range(8):
        for j in range(i + 1, 8):
            for s1 in (-2, 2):
                for s2 in (-2, 2):
                    if s1 * s1 + s2 * s2 == 8:
                        e8_int_roots += 1
    e8_half_roots = 0
    for sign_mask in range(256):
        neg_count = sign_mask.bit_count()
        if (neg_count & 1) == 0:
            # 8 coordinates of +/-1 => norm^2 = 8
            e8_half_roots += 1

    return {
        "c16_11_4_exhaustive_vectors": 65536,
        "c16_11_4_codeword_count": codeword_count,
        "c16_11_4_min_distance": min_nonzero_wt,
        "c16_11_4_weight_enumerator": weight_enum,
        "rm14_codeword_count": rm_codewords,
        "rm14_subset_c16_verified_count": rm_in_c16,
        "e8_integer_roots": e8_int_roots,
        "e8_half_integer_roots": e8_half_roots,
        "e8_total_minimal_roots": e8_int_roots + e8_half_roots,
        "a16_wire_bits_per_weight_q": q_str(Fraction(9, 2)),
        "bf16_over_a16_compression_q": q_str(Fraction(32, 9)),
    }


def verify_exact_stage_a_gauge_theorem() -> dict[str, Any]:
    """Prove exact 0-deviation Stage-A permutation + positive rational affine invariance."""
    a_base = [
        [Fraction(10), Fraction(13), Fraction(19), Fraction(21), Fraction(15), Fraction(11)],
        [Fraction(4), Fraction(7), Fraction(11), Fraction(8), Fraction(5), Fraction(3)],
        [Fraction(30), Fraction(28), Fraction(22), Fraction(25), Fraction(29), Fraction(32)],
    ]
    b_base = [
        [Fraction(100), Fraction(120), Fraction(180), Fraction(175), Fraction(140), Fraction(105)],
        [Fraction(7), Fraction(9), Fraction(13), Fraction(12), Fraction(10), Fraction(7)],
    ]
    e0, me0, rr0, sr0 = compute_scale_invariant_schur_exact(a_base, b_base, Fraction(1, 20))
    perm_a = [2, 0, 1]
    perm_b = [1, 0]
    scales_a = [Fraction(7, 3), Fraction(11, 5), Fraction(13, 2)]
    offsets_a = [Fraction(19, 4), Fraction(-23, 3), Fraction(101, 7)]
    scales_b = [Fraction(5, 2), Fraction(15, 1)]  # models 15x psys vendor-scale gauge!
    offsets_b = [Fraction(-17, 5), Fraction(500, 1)]
    a_g = [[scales_a[i] * v + offsets_a[i] for v in a_base[i]] for i in perm_a]
    b_g = [[scales_b[i] * v + offsets_b[i] for v in b_base[i]] for i in perm_b]
    e1, me1, rr1, sr1 = compute_scale_invariant_schur_exact(a_g, b_g, Fraction(1, 20))
    e1_unperm = [Fraction(0)] * len(a_base)
    for pos, orig in enumerate(perm_a):
        e1_unperm[orig] = e1[pos]
    max_eta_diff = max(abs(x - y) for x, y in zip(e0, e1_unperm))
    return {
        "dim_a": 3,
        "dim_b": 2,
        "ridge_lambda_q": q_str(Fraction(1, 20)),
        "psys_gauge_rescale_factor": 15,
        "max_eta_diff_q": q_str(max_eta_diff),
        "mean_eta_diff_q": q_str(abs(me0 - me1)),
        "raw_r2_diff_q": q_str(abs(rr0 - rr1)),
        "res_rho2_diff_q": q_str(abs(sr0 - sr1)),
        "exact_zero_gauge_drift": (
            max(max_eta_diff, abs(me0 - me1), abs(rr0 - rr1), abs(sr0 - sr1)) == 0
        ),
    }


# ---------------------------------------------------------------------------
# Full Live Capture Replay Helper (Pure Z/Q, Used by Audit --verify-receipts)
# ---------------------------------------------------------------------------

def recompute_from_raw_capture(cap: dict[str, Any]) -> dict[str, Any]:
    """Recompute all empirical Track S64 invariants directly from granular_silicon_capture.json."""
    exp1_out: dict[str, Any] = {}
    for reg in cap["exp1_rdtsc_jitter_regimes"]:
        steps = reg["steps_per_sample"]
        coarse = reg["coarse_256_block_sums"]
        prism = compute_s39_prism_exact(coarse)
        prism_null = compute_s39_prism_exact(deterministic_coprime_shuffle(coarse, 97))
        haar = compute_haar_octave_ratios_exact(coarse)
        exp1_out[reg["name"]] = {
            "working_set_bytes": reg["working_set_bytes"],
            "steps_per_sample": steps,
            "n_samples": reg["n_samples"],
            "p50_cyc_per_step_q": q_str(Fraction(reg["p50_cyc"], steps)),
            "p95_cyc_per_step_q": q_str(Fraction(reg["p95_cyc"], steps)),
            "p99_cyc_per_step_q": q_str(Fraction(reg["p99_cyc"], steps)),
            "max_cyc_per_step_q": q_str(Fraction(reg["max_cyc"], steps)),
            "n_avalanches_gt_p95": reg["n_avalanches_gt_p95"],
            "max_avalanche_len": reg["max_avalanche_len"],
            "total_avalanche_excess_cyc": reg["total_avalanche_excess_cyc"],
            "s39_r2_to_r5_r6_q": [q_str(round_q_1e6(v)) for v in prism[1:]],
            "s39_shuffle_null_r2_to_r5_r6_q": [q_str(round_q_1e6(v)) for v in prism_null[1:]],
            "haar_v1_over_v0_r6_q": q_str(round_q_1e6(haar[0])),
            "haar_min_ratio_r6_q": q_str(round_q_1e6(min(haar))),
            "haar_max_ratio_r6_q": q_str(round_q_1e6(max(haar))),
        }

    e2 = cap["exp2_100hz_multitimescale"]
    n = e2["n_ticks"]
    dt = e2["dt_us"]
    p_pkg = [e2["pkg_uj"][i] * 1000 // dt[i] for i in range(n)]
    p_core = [e2["core_uj"][i] * 1000 // dt[i] for i in range(n)]
    p_unc = [e2["uncore_uj"][i] * 1000 // dt[i] for i in range(n)]
    p_psys = [e2["psys_uj"][i] * 1000 // dt[i] for i in range(n)]
    p_dark = [p_pkg[i] - p_core[i] - p_unc[i] for i in range(n)]
    t_pkg = e2["pkg_mc"]
    f_cpu = e2["cpu_fan_rpm"]
    f_gpu = e2["gpu_fan_rpm"]
    freq0 = e2["cpu0_khz"]

    a_cols = [
        [Fraction(v) for v in col]
        for col in (t_pkg, e2["core0_mc"], e2["core1_mc"], e2["core7_mc"], f_cpu, f_gpu, freq0)
    ]
    b_cols = [[Fraction(v) for v in col] for col in (p_pkg, p_core, p_unc, p_psys)]
    etas, mean_eta, raw_r2, res_rho2 = compute_scale_invariant_schur_exact(a_cols, b_cols, Fraction(1, 20))

    # Live 11-channel Stage-A gauge invariance verification including 15x psys rescale
    perm_a = [3, 6, 0, 5, 2, 1, 4]
    perm_b = [2, 0, 3, 1]
    sc_a = [Fraction(7, 3), Fraction(11, 5), Fraction(13, 2), Fraction(5, 7), Fraction(17, 4), Fraction(19, 6), Fraction(23, 8)]
    of_a = [Fraction(101, 3), Fraction(-77, 5), Fraction(409, 7), Fraction(13, 2), Fraction(-55, 4), Fraction(88, 3), Fraction(999, 8)]
    sc_b = [Fraction(3, 2), Fraction(5, 4), Fraction(9, 7), Fraction(15, 1)]
    of_b = [Fraction(17, 3), Fraction(-29, 5), Fraction(41, 7), Fraction(1000, 1)]
    a_g = [[sc_a[i] * v + of_a[i] for v in a_cols[i]] for i in perm_a]
    b_g = [[sc_b[i] * v + of_b[i] for v in b_cols[i]] for i in perm_b]
    etas_g, mean_eta_g, raw_r2_g, res_rho2_g = compute_scale_invariant_schur_exact(a_g, b_g, Fraction(1, 20))
    etas_g_unperm = [Fraction(0)] * len(a_cols)
    for pos, orig in enumerate(perm_a):
        etas_g_unperm[orig] = etas_g[pos]
    live_max_eta_diff = max(abs(x - y) for x, y in zip(etas, etas_g_unperm))

    area_tf_open, area_tf_closed = compute_green_2area_exact(t_pkg, f_cpu)
    area_tp_open, area_tp_closed = compute_green_2area_exact(t_pkg, p_pkg)
    pb = e2["phase_bounds"]
    ru_lo, ru_hi = pb["ramp_up_2c"]
    rd_lo, rd_hi = pb["ramp_down_2c"]

    def _channel_spectral(seq: list[int]) -> dict[str, Any]:
        pr = compute_s39_prism_exact(seq)
        pr_n = compute_s39_prism_exact(deterministic_coprime_shuffle(seq, 401))
        dx = [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]
        return {
            "s39_r2_to_r5_r6_q": [q_str(round_q_1e6(v)) for v in pr[1:]],
            "s39_shuffle_null_r2_to_r5_r6_q": [q_str(round_q_1e6(v)) for v in pr_n[1:]],
            "arrow_sum_dx3": sum(v * v * v for v in dx),
            "arrow_sum_dx2": sum(v * v for v in dx),
        }

    exp2_out = {
        "n_ticks": n,
        "tick_ms_nominal": e2["tick_ms_nominal"],
        "mean_pkg_mw_q": q_str(Fraction(sum(p_pkg), n)),
        "mean_core_mw_q": q_str(Fraction(sum(p_core), n)),
        "mean_uncore_mw_q": q_str(Fraction(sum(p_unc), n)),
        "mean_dark_inpkg_mw_q": q_str(Fraction(sum(p_dark), n)),
        "mean_psys_mw_q": q_str(Fraction(sum(p_psys), n)),
        "pkg_over_psys_vendor_scale_r6_q": q_str(round_q_1e6(Fraction(sum(p_pkg), sum(p_psys)))),
        "r2_psys_vs_pkg_r6_q": q_str(round_q_1e6(compute_corr_r2_exact(p_psys, p_pkg))),
        "r2_tpkg_vs_ppkg_r6_q": q_str(round_q_1e6(compute_corr_r2_exact(t_pkg, p_pkg))),
        "schur_100hz_mean_eta_r6_q": q_str(round_q_1e6(mean_eta)),
        "schur_100hz_raw_r2_r6_q": q_str(round_q_1e6(raw_r2)),
        "schur_100hz_res_rho2_r6_q": q_str(round_q_1e6(res_rho2)),
        "live_11ch_stage_a_gauge_exact_zero": (
            max(
                live_max_eta_diff,
                abs(mean_eta - mean_eta_g),
                abs(raw_r2 - raw_r2_g),
                abs(res_rho2 - res_rho2_g),
            )
            == 0
        ),
        "green_2area_tpkg_cpufan_open": area_tf_open,
        "green_2area_tpkg_cpufan_closed": area_tf_closed,
        "green_2area_tpkg_ppkg_open": area_tp_open,
        "green_2area_tpkg_ppkg_closed": area_tp_closed,
        "ramp_up_2c_mean_tpkg_mc_q": q_str(Fraction(sum(t_pkg[ru_lo:ru_hi]), ru_hi - ru_lo)),
        "ramp_down_2c_mean_tpkg_mc_q": q_str(Fraction(sum(t_pkg[rd_lo:rd_hi]), rd_hi - rd_lo)),
        "cpu_fan_min_rpm": min(f_cpu),
        "cpu_fan_max_rpm": max(f_cpu),
        "channels_spectral": {
            "pkg_mw": _channel_spectral(p_pkg),
            "core_mw": _channel_spectral(p_core),
            "dark_inpkg_mw": _channel_spectral(p_dark),
            "pkg_mc": _channel_spectral(t_pkg),
            "cpu0_khz": _channel_spectral(freq0),
            "cpu_fan_rpm": _channel_spectral(f_cpu),
        },
    }

    e3 = cap["exp3_allometric_core_scaling"]
    w_vals = [Fraction(r["pkg_uj"], r["wall_us"]) for r in e3]
    g_vals = [Fraction(r["total_ops"], r["wall_us"] * 1000) for r in e3]
    pj_vals = [Fraction(r["pkg_uj"] * 1_000_000, r["total_ops"]) for r in e3]
    wpc_vals = [g_vals[i] / e3[i]["p_cores"] for i in range(len(e3))]
    r1, r8 = e3[0], e3[4]
    t1_k = Fraction(r1["pkg_mc_start"] + r1["pkg_mc_end"], 2000) + Fraction(27315, 100)
    t8_k = Fraction(r8["pkg_mc_start"] + r8["pkg_mc_end"], 2000) + Fraction(27315, 100)
    e1_j = Fraction(r1["pkg_uj"], 10**6 * r1["total_ops"])
    e8_j = Fraction(r8["pkg_uj"], 10**6 * r8["total_ops"])
    exp3_out = {
        "core_counts": [r["p_cores"] for r in e3],
        "pkg_power_w_r6_q": [q_str(round_q_1e6(v)) for v in w_vals],
        "work_gops_s_r6_q": [q_str(round_q_1e6(v)) for v in g_vals],
        "work_per_core_gops_s_r6_q": [q_str(round_q_1e6(v)) for v in wpc_vals],
        "energy_pj_per_op_r6_q": [q_str(round_q_1e6(v)) for v in pj_vals],
        "pkg_power_spread_pct_r6_q": q_str(round_q_1e6((max(w_vals) - min(w_vals)) * 100 / min(w_vals))),
        "work_8c_over_1c_r6_q": q_str(round_q_1e6(g_vals[4] / g_vals[0])),
        "energy_per_op_1c_over_8c_r6_q": q_str(
            round_q_1e6(Fraction(r1["pkg_uj"] * r8["total_ops"], r8["pkg_uj"] * r1["total_ops"]))
        ),
        "d2_work_at_p4_r6_q": q_str(round_q_1e6(g_vals[3] - 2 * g_vals[2] + g_vals[1])),
        "d2_work_at_p6_r6_q": q_str(round_q_1e6(g_vals[4] - 2 * g_vals[3] + g_vals[2])),
        "p1_temp_k_q": q_str(t1_k),
        "p8_temp_k_q": q_str(t8_k),
        "p1_landauer_ratio_bracket": landauer_integer_bracket(e1_j, t1_k),
        "p8_landauer_ratio_bracket": landauer_integer_bracket(e8_j, t8_k),
    }

    return {"exp1": exp1_out, "exp2": exp2_out, "exp3": exp3_out}


# ---------------------------------------------------------------------------
# Master Pure-Z/Q Certificate Payload Builder
# ---------------------------------------------------------------------------

def build_payload() -> dict[str, Any]:
    """Build the complete, self-contained pure-Z/Q Track S64 certificate payload."""
    exact_s39 = verify_exact_s39_analytic_manifolds()
    exact_codes = verify_exact_code_and_lattice_geometry()
    exact_gauge = verify_exact_stage_a_gauge_theorem()

    # Exact SI-2019 Landauer brackets for frozen S58 / S60 LLM silicon energies (T_gpu = 63 C = 336.15 K)
    t_gpu_k = Fraction(63, 1) + Fraction(27315, 100)
    e_s58_bb_j = Fraction(4664749, 20000 * 1000)
    e_s58_e2e_j = Fraction(31278711, 100000 * 1000)
    e_s60_st4_j = Fraction(289359, 1000000)
    s58_wt_count = 357826560
    s60_wt_count = 1310195712

    # Exact Landauer brackets for fresh Exp 3 p=1 and p=8
    t1_k = Fraction(7283, 20)
    t8_k = Fraction(7223, 20)
    e1_op_j = Fraction(139968086, 10**6 * 9638264832)
    e8_op_j = Fraction(140278816, 10**6 * 35730754560)

    return {
        "exact": {
            "provenance_tier": "exact",
            "s39_nyquist_third_prism_exact": exact_s39,
            "universal_code_and_lattice_exact": exact_codes,
            "stage_a_gauge_invariance_exact": exact_gauge,
            "si2019_landauer_constants_exact": {
                "kb_j_per_k_q": q_str(KB_EXACT_J_PER_K),
                "ln2_bracket_lo_q": q_str(LN2_BRACKET_LO),
                "ln2_bracket_hi_q": q_str(LN2_BRACKET_HI),
            },
        },
        "sampled": {
            "provenance_tier": "sampled",
            "measured_live_silicon": True,
            "privacy_locks": {
                "audio_capture_accessed": False,
                "camera_accessed": False,
                "display_modified": False,
            },
            "ring0_mlos_receipt": {
                "profile_id": "ux582hs-rtx3080-8gb",
                "determinism_zone": "B",
                "clean_hardware_run": True,
                "exit_code": 0,
                "anomaly_count": 0,
                "graphics_process_count": 0,
                "compute_process_count": 0,
                "linux_kmd_baseline_vram_mib": 2,
                "thermal_throttled": False,
                "slowdown_active": False,
                "rapl_domains_available_count": 5,
            },
            "pinned_sha256": dict(PINNED_S64_DIGESTS),
            "pinned_cross_track_certs": dict(PINNED_CROSS_TRACK_CERTS),
            "pillar_1_dark_mode_schur_and_gauge": {
                "s53_multisecond_eta_ladder_q": [
                    "448340210833/500000000000",
                    "164231638427/250000000000",
                    "117476633903/200000000000",
                ],
                "s53_eta_monotonically_decreasing": True,
                "live_100hz_n_ticks": 1600,
                "live_100hz_tick_ms_nominal": 10,
                "live_100hz_mean_pkg_mw_q": "112072963/1600",
                "live_100hz_mean_core_mw_q": "104627363/1600",
                "live_100hz_mean_uncore_mw_q": "663503/1600",
                "live_100hz_mean_dark_inpkg_mw_q": "6782097/1600",
                "live_100hz_mean_psys_mw_q": "7624099/1600",
                "psys_vendor_scale_obstruction_ratio_r6_q": "1469983/100000",
                "psys_vendor_scale_obstruction_detected": True,
                "r2_psys_vs_pkg_scale_invariant_r6_q": "319381/500000",
                "r2_tpkg_vs_ppkg_100hz_r6_q": "253/125000",
                "schur_100hz_mean_eta_r6_q": "244367/250000",
                "schur_100hz_raw_r2_r6_q": "22997/1000000",
                "schur_100hz_res_rho2_r6_q": "24059/1000000",
                "live_11ch_stage_a_gauge_exact_zero": True,
                "dark_inpkg_arrow_sum_dx3": 17580652974039,
                "dark_inpkg_arrow_sum_dx2": 2743100037,
                "pkg_mc_arrow_sum_dx3": 269000000000,
                "pkg_mc_arrow_sum_dx2": 103000000,
                "thermal_rc_timescale_decoupling_obstruction": True,
            },
            "pillar_2_hysteresis_and_yield_wall": {
                "l1_16kib_p50_cyc_per_step_q": "309/64",
                "l3_16mib_p50_cyc_per_step_q": "5929/16",
                "dram_64mib_p50_cyc_per_step_q": "2719/8",
                "l3_over_l1_latency_cliff_q": "23716/309",
                "dram_over_l1_latency_cliff_q": "21752/309",
                "l1_max_avalanche_len": 11,
                "l3_max_avalanche_len": 200,
                "dram_max_avalanche_len": 317,
                "green_2area_tpkg_cpufan_open": 49200000,
                "green_2area_tpkg_cpufan_closed": 2200000,
                "green_2area_tpkg_ppkg_open": 830398000,
                "green_2area_tpkg_ppkg_closed": 155978000,
                "ramp_up_2c_mean_tpkg_mc_q": "93425",
                "ramp_down_2c_mean_tpkg_mc_q": "91100",
                "cpu_fan_min_rpm": 4700,
                "cpu_fan_max_rpm": 4800,
                "discrete_controller_critical_exponent_obstruction": True,
            },
            "pillar_3_spectral_prism_and_nulls": {
                "rdtsc_l1_16kib": {
                    "working_set_bytes": 16384,
                    "steps_per_sample": 64,
                    "n_samples": 131072,
                    "p50_cyc_per_step_q": "309/64",
                    "p95_cyc_per_step_q": "325/64",
                    "p99_cyc_per_step_q": "179/32",
                    "max_cyc_per_step_q": "5097473/64",
                    "n_avalanches_gt_p95": 4169,
                    "max_avalanche_len": 11,
                    "total_avalanche_excess_cyc": 7216427,
                    "s39_r2_to_r5_r6_q": ["1500259/500000", "1666987/500000", "3500657/1000000", "3600601/1000000"],
                    "s39_shuffle_null_r2_to_r5_r6_q": ["2995053/1000000", "3330937/1000000", "3498657/1000000", "89979/25000"],
                    "haar_v1_over_v0_r6_q": "50187/50000",
                    "haar_min_ratio_r6_q": "86903/200000",
                    "haar_max_ratio_r6_q": "1767/1600",
                },
                "rdtsc_l3_16mib": {
                    "working_set_bytes": 16777216,
                    "steps_per_sample": 16,
                    "n_samples": 131072,
                    "p50_cyc_per_step_q": "5929/16",
                    "p95_cyc_per_step_q": "10463/16",
                    "p99_cyc_per_step_q": "2243/2",
                    "max_cyc_per_step_q": "1726920",
                    "n_avalanches_gt_p95": 3196,
                    "max_avalanche_len": 200,
                    "total_avalanche_excess_cyc": 112397170,
                    "s39_r2_to_r5_r6_q": ["254587/100000", "3252889/1000000", "883949/250000", "73313/20000"],
                    "s39_shuffle_null_r2_to_r5_r6_q": ["2913599/1000000", "3281237/1000000", "433971/125000", "3585659/1000000"],
                    "haar_v1_over_v0_r6_q": "925741/250000",
                    "haar_min_ratio_r6_q": "913723/1000000",
                    "haar_max_ratio_r6_q": "925741/250000",
                },
                "rdtsc_dram_64mib": {
                    "working_set_bytes": 67108864,
                    "steps_per_sample": 16,
                    "n_samples": 131072,
                    "p50_cyc_per_step_q": "2719/8",
                    "p95_cyc_per_step_q": "1459/2",
                    "p99_cyc_per_step_q": "21015/16",
                    "max_cyc_per_step_q": "1282379/8",
                    "n_avalanches_gt_p95": 2033,
                    "max_avalanche_len": 317,
                    "total_avalanche_excess_cyc": 43369046,
                    "s39_r2_to_r5_r6_q": ["2391341/1000000", "1532823/500000", "3332579/1000000", "1739639/500000"],
                    "s39_shuffle_null_r2_to_r5_r6_q": ["29769/10000", "3280181/1000000", "3459103/1000000", "3582893/1000000"],
                    "haar_v1_over_v0_r6_q": "2001391/1000000",
                    "haar_min_ratio_r6_q": "70191/1000000",
                    "haar_max_ratio_r6_q": "4568391/1000000",
                },
                "live_100hz_channels": {
                    "pkg_mw": {
                        "s39_r2_to_r5_r6_q": ["1496621/500000", "3323821/1000000", "349139/100000", "897903/250000"],
                        "s39_shuffle_null_r2_to_r5_r6_q": ["3048087/1000000", "335597/100000", "3507743/1000000", "56249/15625"],
                        "arrow_sum_dx3": 70976573992388,
                        "arrow_sum_dx2": 75732879270,
                    },
                    "core_mw": {
                        "s39_r2_to_r5_r6_q": ["604071/200000", "1670953/500000", "1751417/500000", "3598589/1000000"],
                        "s39_shuffle_null_r2_to_r5_r6_q": ["608699/200000", "418887/125000", "1751687/500000", "143829/40000"],
                        "arrow_sum_dx3": 81464712545879,
                        "arrow_sum_dx2": 72831028585,
                    },
                    "dark_inpkg_mw": {
                        "s39_r2_to_r5_r6_q": ["101023/31250", "690329/200000", "356841/100000", "455461/125000"],
                        "s39_shuffle_null_r2_to_r5_r6_q": ["3044151/1000000", "105347/31250", "3547157/1000000", "1826131/500000"],
                        "arrow_sum_dx3": 17580652974039,
                        "arrow_sum_dx2": 2743100037,
                    },
                    "pkg_mc": {
                        "s39_r2_to_r5_r6_q": ["2", "3", "3333333/1000000", "7/2"],
                        "s39_shuffle_null_r2_to_r5_r6_q": ["341311/125000", "3073319/1000000", "3391579/1000000", "908279/250000"],
                        "arrow_sum_dx3": 269000000000,
                        "arrow_sum_dx2": 103000000,
                    },
                    "cpu0_khz": {
                        "s39_r2_to_r5_r6_q": ["1186967/500000", "2997313/1000000", "3288797/1000000", "1728279/500000"],
                        "s39_shuffle_null_r2_to_r5_r6_q": ["279173/100000", "1564869/500000", "423567/125000", "893743/250000"],
                        "arrow_sum_dx3": -19989411495493837,
                        "arrow_sum_dx2": 2505619270393,
                    },
                    "cpu_fan_rpm": {
                        "s39_r2_to_r5_r6_q": ["2", "3", "3333333/1000000", "7/2"],
                        "s39_shuffle_null_r2_to_r5_r6_q": ["2507463/1000000", "703373/250000", "3150917/1000000", "3453447/1000000"],
                        "arrow_sum_dx3": 0,
                        "arrow_sum_dx2": 60000,
                    },
                },
                "universal_soc_1_over_f_obstructed_by_multipole_haar": True,
            },
            "pillar_4_allometric_pl1_ceiling": {
                "core_counts": [1, 2, 4, 6, 8],
                "pkg_power_w_r6_q": [
                    "34956663/500000",
                    "13980389/200000",
                    "69982613/1000000",
                    "34901291/500000",
                    "3498333/50000",
                ],
                "work_gops_s_r6_q": [
                    "4814263/1000000",
                    "3972321/500000",
                    "1412701/100000",
                    "1525653/100000",
                    "278459/15625",
                ],
                "work_per_core_gops_s_r6_q": [
                    "4814263/1000000",
                    "3972321/1000000",
                    "3531753/1000000",
                    "508551/200000",
                    "278459/125000",
                ],
                "energy_pj_per_op_r6_q": [
                    "1452212493/100000",
                    "8798627921/1000000",
                    "2476908119/500000",
                    "2287629607/500000",
                    "1962998231/500000",
                ],
                "pkg_power_spread_pct_r6_q": "51583/200000",
                "work_8c_over_1c_r6_q": "3701787/1000000",
                "energy_per_op_1c_over_8c_r6_q": "739793/200000",
                "d2_work_at_p4_r6_q": "-315803/62500",
                "d2_work_at_p6_r6_q": "717663/500000",
                "work_per_core_strictly_decreasing": True,
                "smooth_kleiber_power_law_obstructed_by_pl1_ceiling": True,
            },
            "pillar_5_landauer_thermodynamic_gap": {
                "exp3_p1_temp_k_q": q_str(t1_k),
                "exp3_p8_temp_k_q": q_str(t8_k),
                "exp3_p1_landauer_ratio_bracket": landauer_integer_bracket(e1_op_j, t1_k),
                "exp3_p8_landauer_ratio_bracket": landauer_integer_bracket(e8_op_j, t8_k),
                "gpu_ref_temp_k_q": q_str(t_gpu_k),
                "s58_05b_backbone_mj_per_tok_q": "4664749/20000",
                "s58_05b_backbone_landauer_bits_per_tok": landauer_integer_bracket(e_s58_bb_j, t_gpu_k),
                "s58_05b_backbone_landauer_per_weight_op": landauer_integer_bracket(e_s58_bb_j / s58_wt_count, t_gpu_k),
                "s58_05b_e2e_mj_per_tok_q": "31278711/100000",
                "s58_05b_e2e_landauer_bits_per_tok": landauer_integer_bracket(e_s58_e2e_j, t_gpu_k),
                "s60_15b_stacked4_mj_per_tok_q": "289359/1000",
                "s60_15b_stacked4_landauer_bits_per_tok": landauer_integer_bracket(e_s60_st4_j, t_gpu_k),
                "s60_15b_stacked4_landauer_per_weight_op": landauer_integer_bracket(e_s60_st4_j / s60_wt_count, t_gpu_k),
                "s53_sensor_total_landauer_bits": [1639114762572878216469658, 1639114762575242959209074],
                "s53_phase2_total_landauer_bits": [1202330249891633791804104, 1202330249893368387693137],
                "landauer_scale_gap_exceeds_10_to_10": True,
            },
            "pillar_6_universal_code_vs_weight_anisotropy": {
                "qwen_05b_block_weights": s58_wt_count,
                "qwen_15b_block_weights": s60_wt_count,
                "weight_scale_ratio_15b_over_05b_q": q_str(Fraction(s60_wt_count, s58_wt_count)),
                "qwen_05b_a16_block_h2_over_axis_wt_kl_q": "1051/1000",
                "qwen_15b_a16_block_h2_over_axis_wt_kl_q": "45647596/50062401",
                "qwen_15b_a16_h16_over_axis_wt_kl_q": "48376358/50062401",
                "qwen_15b_a16_block_h2_over_h16_wt_kl_q": "22823798/24188179",
                "qwen_15b_e8_h8_over_axis_wt_kl_q": "5335448/5279451",
                "qwen_15b_e8_h8_over_axis_py_kl_q": "15065704/18055065",
                "qwen_15b_total_layers": 196,
                "qwen_15b_regime1_axis_layers": 101,
                "qwen_15b_regime2_rotated_layers": 95,
                "qwen_15b_block_h2_beats_h16_layers": 105,
                "qwen_15b_wt_p5_rand_retention_q": "459079/500000",
                "qwen_15b_py_p5_rand_retention_q": "484927/500000",
                "a16_block_h2_sign_crossover_05b_to_15b": True,
                "isotropic_packing_universality_obstructed_by_anisotropy": True,
            },
        },
        "anchor": {
            "provenance_tier": "anchor",
            "cs13_citations": [
                {
                    "id": "N1-S64-FOUR-REGIME-S39-PRISM",
                    "tier": "N1",
                    "claim": "On a single live i9-11900H processor under Ring-0 mlos Zone-B capture, the pure-Q Track S39 Nyquist-third prism cleanly resolves four distinct dynamical classes: exact White Noise (L1 16 KiB rdtsc R2..R5 = 3.0005..3.6006; closed-loop PL1 pkg_mw 2.9932..3.5916), exact Random Walk (100 Hz thermal pkg_mc and cpu_fan = 2, 3, 10/3, 7/2), intermediate persistent cascades (DRAM 64 MiB R2=2.3913 vs shuffle null 2.9769; DVFS cpu0_khz R2=2.3739 vs null 2.7917), and super-Nyquist anti-persistence (dark_inpkg_mw R2=3.2327 > 3.0).",
                },
                {
                    "id": "N1-S64-EXACT-STAGE-A-GAUGE-INVARIANCE",
                    "tier": "N1",
                    "claim": "Scale-invariant square-root-free Schur complement S_{A|B} achieves exact 0-deviation invariance under arbitrary channel permutations and positive rational affine rescalings (including 15x psys rescale) across both the exact algebraic witness and the live 11-channel 100 Hz silicon matrix, recovering R^2(psys, pkg) = 0.6388 despite psys's 14.70x raw vendor-scale offset.",
                },
                {
                    "id": "N0-S64-PSYS-SCALE-AND-RC-TIMESCALE-OBSTRUCTIONS",
                    "tier": "N0",
                    "claim": "Two explicit Pillar-1 obstructions hold on live silicon: (1) UX582HS intel-rapl:1 (psys) carries an uncalibrated 14.70x scale offset vs package-0 so raw subtraction P_psys - P_pkg is negative (CS-11 unit-gauge trap); (2) instantaneous 100 Hz Schur yields eta = 97.75% (R^2(T_pkg, P_pkg) = 0.0020) because thermal RC capacitance integrates power over seconds, whereas multi-second S53 windows drop eta from 89.67% to 58.74%.",
                },
                {
                    "id": "N0-S64-NON-SOC-AND-DISCRETE-WALL-OBSTRUCTIONS",
                    "tier": "N0",
                    "claim": "Although L3/DRAM pointer chasing triggers a 76.75x latency cliff and 28.8x avalanche expansion and 100 Hz (T_pkg, fan/power) loops have nonzero Green's-theorem areas (+2.2e6 / +1.56e8), Haar octave variance ratios jump non-monotonically (0.07..4.57) and EC fans step in 100-RPM quanta, obstructing naive universal SOC 1/f criticality and continuum thermodynamic critical exponents.",
                },
                {
                    "id": "N0-S64-PL1-CEILING-HOST-SATURATION-OBSTRUCTION",
                    "tier": "N0",
                    "claim": "Under active parallel workstation load pinned at the 70.0 W PL1 thermal ceiling, Exp 3 package power across p in {1,2,4,6,8} is piecewise-flat (69.80..69.98 W, 0.258% spread) rather than smooth Kleiber P ~ p^0.75 allometry, while work scales sublinearly 3.702x (work/core strictly decreasing 4.814 -> 2.228 Gops/s/core); this characterizes the PL1-saturated ceiling regime rather than an unloaded idle-host single-core baseline.",
                },
                {
                    "id": "N0-S64-LANDAUER-AND-ANISOTROPY-OBSTRUCTIONS",
                    "tier": "N0",
                    "claim": "Exact SI-2019 rational brackets prove live CMOS switching runs 1.14e12x..4.17e12x above k_B T ln 2 per Exp 3 op (6.87e10x..2.03e11x per LLM weight-op across S58/S60), while trained Qwen2.5 weights split 101/95 between axis-aligned and rotated regimes with a 0.5B->1.5B A16_BlockH2 sign crossover (1.0510x -> 0.9118x) and corpus-dependent E_8 split, obstructing naive thermodynamic-limit and isotropic-packing universality.",
                },
            ],
        },
    }


def build_certificate() -> dict[str, Any]:
    """Assemble and SHA-256 sign the canonical Track S64 certificate."""
    payload = build_payload()
    payload_sha = sha256_hex(canonical_json_bytes(payload))
    cert_body = {
        "schema": CERT_SCHEMA,
        "track_id": CERT_TRACK_ID,
        "payload_sha256": payload_sha,
        "payload": payload,
    }
    cert_sha = sha256_hex(canonical_json_bytes(cert_body))
    return {
        "schema": CERT_SCHEMA,
        "track_id": CERT_TRACK_ID,
        "payload_sha256": payload_sha,
        "certificate_sha256": cert_sha,
        "payload": payload,
    }


if __name__ == "__main__":
    print(canonical_json_bytes(build_certificate()).decode("utf-8"), end="")
