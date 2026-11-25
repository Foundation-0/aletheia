#!/usr/bin/env python3
"""Track S106 Phase 1A — Pure-Q Symbolic Core & H2b Physics Certificate Oracle.

Zero IEEE-754 floating-point operations, zero bare asserts, zero third-party packages,
zero RNG modules, zero shared mutable aliases across calls.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from math import factorial
from pathlib import Path
import sys
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import s106_physics_denom_pi_bench as phys_bench  # noqa: E402

SCHEMA_VERSION = "1.0.0"
TRACK_ID = "TRACK-S106-SPHERE-DENOM-PI-FORCES-PHASE1A"
CERT_FILE_NAME = "s106_formal_physics_certificate.json"
LEAN_SOURCE_NAME = "SphereDenomPiOperators.lean"
LEAN_MODULE = "SphereDenomPiOperators"
EXPECTED_LEAN_TOOLCHAIN = "leanprover/lean4:v4.36.0"

PINNED_LEAN_SOURCE_SHA256 = "3184a96268417396b9583bdecfca941a0b2489f57a5eac7f47939e73cab4908d"
PINNED_LAKEFILE_SHA256 = "46e7baa5d7019b638f5c00391c7b0965a407504b87a8892c02e27e87899e54ff"
PINNED_LEAN_TOOLCHAIN_SHA256 = "582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a"

# External-historical pins: the two files are NOT shipped in this repo and no repo@sha is
# named, so --verify-pins cannot reproduce them (IO_OPEN_ERROR unless supplied externally).
EXTERNAL_PINS: tuple[tuple[str, str, int, str], ...] = (
    ("PREREG_V1", "PREREG_SPHERE_PI_FORCES_V1.md", 10800,
     "ac3e62116bc4841320d2c713787c23568beed1ae738bf9b284b7f0c2a118d72a"),
    ("NOTES_V1", "SPHERE_HYPERSPHERE_DENOM_PI_FORCES_SILIQUANT.md", 9000,
     "ce35640d08c782c588d8859f084e7c26eda72fb16954373212e5b916f59f9ef0"),
)

LEAN_THEOREM_SHORT_NAMES: tuple[str, ...] = (
    "fact_pos",
    "even_sphere_area_to_ball_vol_ratio",
    "binom_linear_lower_bound",
    "zador_step_factor",
    "ball_beats_cube_zador_all_even_dims",
    "cube_to_ball_vol_ratio_even_strict_growth",
    "vDot_comm",
    "normSq_nonneg",
    "hodge_reconstruction",
    "hodge_orthogonality_ref",
    "hodge_orthogonality",
    "hodge_pythagorean_split",
    "hodge_weighted_distortion_ge_euclidean",
    "hodge_radial_rescaling_invariance",
    "hodge_radial_rescaling_order_invariant",
    "hodge_radial_warp_zero_transverse",
    "eq_s2_hatbox_strip_width_invariant",
    "eq_s2_hatbox_total_partition",
    "eq_hopf_u_midpoint_sum",
    "eq_hopf_complementary_midpoint_sum",
    "eq_hopf_3s_quadratic_moment_nat",
    "eq_hopf_3s_quadratic_moment_exact",
    "pow2_not_div_by_three",
    "pow2_not_div_by_five",
    "exceptional_design_slot_waste_universal",
    "thin_shell_chebyshev_monotone",
    "weylBn_step_and_pos",
    "weylBn_strict_mono",
    "weylBn_div_pow2",
    "coxeter_weyl_e8_b8_index",
    "hopf_map_norm_sq",
    "hopf_fiber_norm_sq_scaling",
    "hopf_map_u1_fiber_scaling",
    "hopf_map_u1_fiber_invariance",
)
LEAN_THEOREM_NAMES: tuple[str, ...] = tuple(f"{LEAN_MODULE}.{n}" for n in LEAN_THEOREM_SHORT_NAMES)

_HEX64_CHARS = frozenset("0123456789abcdef")
_LEAF_TYPES = (int, bool, str, type(None))


class S106Error(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def require_ok(cond: bool, code: str, detail: str) -> None:
    if cond is not True:
        raise S106Error(code, detail)


def require_bool(val: Any, label: str) -> bool:
    require_ok(type(val) is bool, "INVALID_BOOL", f"{label} must be exact bool")
    return val


def require_exact_int(val: Any, label: str, lo: int | None = None, hi: int | None = None) -> int:
    require_ok(type(val) is int, "INVALID_INT", f"{label} must be exact int")
    if lo is not None:
        require_ok(val >= lo, "INT_OUT_OF_RANGE", f"{label} < {lo}")
    if hi is not None:
        require_ok(val <= hi, "INT_OUT_OF_RANGE", f"{label} > {hi}")
    return val


def require_exact_str(val: Any, label: str) -> str:
    require_ok(type(val) is str, "INVALID_STR", f"{label} must be exact str")
    return val


def require_hex64(val: Any, label: str) -> str:
    s = require_exact_str(val, label)
    require_ok(len(s) == 64, "INVALID_HEX64", f"{label} must be 64 lowercase hex chars")
    require_ok(frozenset(s) <= _HEX64_CHARS, "INVALID_HEX64", f"{label} has non-hex char")
    return s


def validate_strict_json_tree(obj: Any, label: str = "root") -> None:
    stack: list[tuple[Any, int]] = [(obj, 0)]
    while stack:
        cur, depth = stack.pop()
        require_ok(depth <= 32, "JSON_DEPTH_EXCEEDED", f"{label}: depth > 32")
        t = type(cur)
        if t is int:
            require_ok(cur.bit_length() <= 2048, "INT_BIT_LIMIT", f"{label}: int exceeds 2048 bits")
        elif t is list:
            for item in cur:
                stack.append((item, depth + 1))
        elif t is dict:
            for k, v in cur.items():
                require_ok(type(k) is str, "INVALID_JSON_KEY", f"{label}: dict key must be str")
                stack.append((v, depth + 1))
        else:
            require_ok(t in _LEAF_TYPES, "FORBIDDEN_JSON_TYPE", f"{label}: forbidden type {t.__name__}")


def canonical_json_bytes(obj: Any) -> bytes:
    validate_strict_json_tree(obj, "canonical_json")
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fmt_q(q: Fraction) -> str:
    require_ok(type(q) is Fraction, "INVALID_FRACTION", "expected Fraction")
    return str(q.numerator) if q.denominator == 1 else f"{q.numerator}/{q.denominator}"


def fmt_dec_q(q: Fraction, places: int = 6) -> str:
    require_ok(type(q) is Fraction, "INVALID_FRACTION", "expected Fraction")
    require_exact_int(places, "places", lo=0, hi=18)
    neg = q < 0
    a = -q if neg else q
    scale = 10 ** places
    n = a.numerator * scale
    d = a.denominator
    quo, rem = divmod(n, d)
    if 2 * rem >= d:
        quo += 1
    s = str(quo)
    if places == 0:
        out = s
    else:
        if len(s) <= places:
            s = "0" * (places - len(s) + 1) + s
        out = f"{s[:-places]}.{s[-places:]}"
    return f"-{out}" if neg else out


# ---------------------------------------------------------------------------
# Pillar 1: Sphere-Unit Coordinates & Graded-Period Q[pi] Algebra
# ---------------------------------------------------------------------------

def build_pillar1_sphere_unit_and_qpi() -> dict[str, Any]:
    even_dims = (2, 4, 6, 8, 16, 24, 64, 128)
    pi_lo = Fraction(314, 100)
    pi_hi = Fraction(22, 7)
    rows: list[dict[str, Any]] = []
    for d in even_dims:
        k = d // 2
        g_su = Fraction(1, d + 2)
        vol_pi_coeff = Fraction(1, factorial(k))
        area_pi_coeff = Fraction(2, factorial(k - 1))
        ratio_area_vol = area_pi_coeff / vol_pi_coeff
        # Exact Zador k-th power ratio (G(B^{2k}) / G(cube))^k <= (12^k * k!) / ((2k+2)^k * pi_lo^k)
        zador_bound_k = Fraction((12 ** k) * factorial(k) * (100 ** k), ((d + 2) ** k) * (314 ** k))
        # Cube-to-ball volume lower bound (4/pi_hi)^k * k!
        cube_over_ball_lb = Fraction((4 ** k) * factorial(k) * (7 ** k), 22 ** k)
        rows.append({
            "dim": d,
            "k": k,
            "g_sphere_unit_q": fmt_q(g_su),
            "g_sphere_unit_dec6": fmt_dec_q(g_su, 6),
            "vol_ball_pi_k_coeff_q": fmt_q(vol_pi_coeff) if k <= 12 else f"1/{k}!",
            "area_sphere_pi_k_coeff_q": fmt_q(area_pi_coeff) if k <= 12 else f"2/{k - 1}!",
            "area_over_vol_exact": int(ratio_area_vol),
            "zador_ball_strictly_beats_cube_under_pi_gt_314_100": zador_bound_k < 1,
            "cube_over_ball_vol_lb_gt_1": cube_over_ball_lb > 1,
        })
    g_su_vals = [Fraction(1, d + 2) for d in even_dims]
    return {
        "pi_rational_bracket": {"lo_q": fmt_q(pi_lo), "hi_q": fmt_q(pi_hi)},
        "even_dimensions": rows,
        "g_sphere_unit_strictly_decreasing": all(b < a for a, b in zip(g_su_vals, g_su_vals[1:])),
        "all_even_dims_ball_beats_cube": all(r["zador_ball_strictly_beats_cube_under_pi_gt_314_100"] for r in rows),
        "all_area_over_vol_equals_dim": all(r["area_over_vol_exact"] == r["dim"] for r in rows),
    }


# ---------------------------------------------------------------------------
# Pillar 2: Exact EM / Hodge Orthogonal Splitting & Radial-Rescaling Invariance
# ---------------------------------------------------------------------------

def exact_hodge_split(x: tuple[Fraction, ...], delta: tuple[Fraction, ...]) -> dict[str, Any]:
    require_ok(len(x) >= 1, "EMPTY_VEC", "vector must be non-empty")
    require_ok(len(x) == len(delta), "DIM_MISMATCH", "x and delta must match in length")
    s_x = sum((c * c for c in x), Fraction(0))
    require_ok(s_x > 0, "ZERO_REF_VEC", "reference vector x must be non-zero")
    proj = sum((a * b for a, b in zip(delta, x)), Fraction(0)) / s_x
    d_par = tuple(proj * c for c in x)
    d_perp = tuple(a - b for a, b in zip(delta, d_par))
    n_tot = sum((c * c for c in delta), Fraction(0))
    n_par = sum((c * c for c in d_par), Fraction(0))
    n_perp = sum((c * c for c in d_perp), Fraction(0))
    cross = sum((a * b for a, b in zip(d_par, d_perp)), Fraction(0))
    return {
        "d_par": d_par,
        "d_perp": d_perp,
        "norm_sq_total": n_tot,
        "norm_sq_par": n_par,
        "norm_sq_perp": n_perp,
        "inner_par_perp": cross,
        "pythagorean_exact": n_tot == n_par + n_perp,
        "orthogonal_exact": cross == 0,
    }


def build_pillar2_em_hodge_splitting() -> dict[str, Any]:
    cases: tuple[tuple[str, tuple[int, ...], tuple[int, ...]], ...] = (
        ("S2_R3_general", (3, -4, 12), (1, 2, -1)),
        ("S3_R4_general", (2, -1, 3, 5), (-2, 4, 1, -3)),
        ("S7_R8_E8_like", (2, 0, -2, 0, 1, -1, 1, 1), (1, 1, -1, 2, 0, -1, 1, 0)),
        ("S15_R16_A16_like", (1, -2, 1, 0, 3, -1, 2, -2, 1, 1, -1, 2, 0, -1, 1, -3),
         (0, 1, -1, 2, -1, 1, 0, 1, -2, 1, 0, -1, 1, 1, -1, 1)),
    )
    witnesses: list[dict[str, Any]] = []
    for name, xi, di in cases:
        xf = tuple(Fraction(v) for v in xi)
        df = tuple(Fraction(v) for v in di)
        sp = exact_hodge_split(xf, df)
        # Check radial rescaling invariance for c in {2, -3, 5/7} and lam in {1, 2, 4}
        inv_ok = True
        for c in (Fraction(2), Fraction(-3), Fraction(5, 7)):
            sp_c = exact_hodge_split(tuple(c * v for v in xf), df)
            for lam in (1, 2, 4):
                d1 = sp["norm_sq_par"] + lam * sp["norm_sq_perp"]
                d2 = sp_c["norm_sq_par"] + lam * sp_c["norm_sq_perp"]
                if d1 != d2:
                    inv_ok = False
        # Pure radial warp error delta = (3/5) * x gives exact zero transverse component
        sp_warp = exact_hodge_split(xf, tuple(Fraction(3, 5) * v for v in xf))
        rad_frac = sp["norm_sq_par"] / sp["norm_sq_total"]
        witnesses.append({
            "case": name,
            "dim": len(xi),
            "norm_sq_total_q": fmt_q(sp["norm_sq_total"]),
            "norm_sq_par_q": fmt_q(sp["norm_sq_par"]),
            "norm_sq_perp_q": fmt_q(sp["norm_sq_perp"]),
            "radial_fraction_q": fmt_q(rad_frac),
            "pythagorean_exact": sp["pythagorean_exact"],
            "orthogonal_exact": sp["orthogonal_exact"],
            "radial_rescaling_invariant": inv_ok,
            "radial_warp_zero_transverse": sp_warp["norm_sq_perp"] == 0,
        })
    return {
        "witnesses": witnesses,
        "all_pythagorean": all(w["pythagorean_exact"] for w in witnesses),
        "all_orthogonal": all(w["orthogonal_exact"] for w in witnesses),
        "all_radial_rescaling_invariant": all(w["radial_rescaling_invariant"] for w in witnesses),
        "all_radial_warp_zero_transverse": all(w["radial_warp_zero_transverse"] for w in witnesses),
        "isotropic_radial_expectation_by_dim": {
            f"d={d}": fmt_q(Fraction(1, d)) for d in (2, 4, 8, 16, 24, 64, 128)
        },
    }


# ---------------------------------------------------------------------------
# Pillar 3: Denominator-pi Equal-Sphere-Fraction Invariants & 2^B Slot Utilization
# ---------------------------------------------------------------------------

def build_pillar3_denom_pi_eq_and_slots() -> dict[str, Any]:
    hopf_checks: list[dict[str, Any]] = []
    for a in (1, 2, 4, 8, 16):
        us = [Fraction(2 * i + 1, 2 * a) for i in range(a)]
        mean_u = sum(us, Fraction(0)) / a
        mean_1mu = sum((1 - u for u in us), Fraction(0)) / a
        mean_u2 = sum((u * u for u in us), Fraction(0)) / a
        expected_u2 = Fraction(4 * a * a - 1, 12 * a * a)
        hopf_checks.append({
            "a": a,
            "mean_u_q": fmt_q(mean_u),
            "mean_1_minus_u_q": fmt_q(mean_1mu),
            "mean_u_sq_q": fmt_q(mean_u2),
            "u2_deficit_from_one_third_q": fmt_q(Fraction(1, 3) - mean_u2),
            "exact_mean_u_half": mean_u == Fraction(1, 2),
            "exact_mean_1_minus_u_half": mean_1mu == Fraction(1, 2),
            "exact_3s_quadratic_formula_ok": mean_u2 == expected_u2,
        })
    slot_table: list[dict[str, Any]] = []
    for name, k_pts, bits in (
        ("DenomPi_EQ_6bit", 64, 6),
        ("DenomPi_EQ_8bit", 256, 8),
        ("DenomPi_EQ_10bit", 1024, 10),
        ("D4_24cell_S3", 24, 5),
        ("H4_600cell_2I_S3", 120, 7),
        ("E8_shell1_S7", 240, 8),
        ("E8_shell12_S7", 2400, 12),
        ("Leech_shell1_S23", 196560, 18),
    ):
        cap = 1 << bits
        wasted = cap - k_pts
        slot_table.append({
            "codebook": name,
            "points": k_pts,
            "index_bits": bits,
            "power_of_2_slots": cap,
            "wasted_slots": wasted,
            "utilization_q": fmt_q(Fraction(k_pts, cap)),
            "utilization_dec6": fmt_dec_q(Fraction(k_pts, cap), 6),
            "zero_waste": wasted == 0,
        })
    hopf_u1_checks: list[dict[str, Any]] = []
    for a0, b0, c0, d0, u, v, d_pyth in ((1, 2, -1, 3, 3, 4, 5), (2, -3, 1, 4, 5, 12, 13)):
        hx, hy, hz = 2 * (a0 * c0 + b0 * d0), 2 * (b0 * c0 - a0 * d0), a0 * a0 + b0 * b0 - c0 * c0 - d0 * d0
        n4 = a0 * a0 + b0 * b0 + c0 * c0 + d0 * d0
        ra, rb = u * a0 - v * b0, v * a0 + u * b0
        rc, rd = u * c0 - v * d0, v * c0 + u * d0
        rx, ry, rz = 2 * (ra * rc + rb * rd), 2 * (rb * rc - ra * rd), ra * ra + rb * rb - rc * rc - rd * rd
        d2 = d_pyth * d_pyth
        hopf_u1_checks.append({
            "z": [a0, b0, c0, d0],
            "pythagorean_phase": [u, v, d_pyth],
            "hopf_image": [hx, hy, hz],
            "norm_sq_matches_n4_sq": hx * hx + hy * hy + hz * hz == n4 * n4,
            "u1_fiber_invariant_exact": [rx, ry, rz] == [d2 * hx, d2 * hy, d2 * hz],
        })
    return {
        "hopf_s3_exact_midpoint_moments": hopf_checks,
        "all_hopf_mean_u_half": all(r["exact_mean_u_half"] for r in hopf_checks),
        "all_hopf_mean_1_minus_u_half": all(r["exact_mean_1_minus_u_half"] for r in hopf_checks),
        "all_hopf_3s_quadratic_exact": all(r["exact_3s_quadratic_formula_ok"] for r in hopf_checks),
        "hopf_3s_error_ratio_a4_to_a8_q": fmt_q(Fraction(1, 12 * 16) / Fraction(1, 12 * 64)),
        "hopf_fibration_u1_invariance_witnesses": hopf_u1_checks,
        "slot_utilization_comparison": slot_table,
    }


# ---------------------------------------------------------------------------
# Pillar 4: Hypersphere Thin-Shell Concentration & Coxeter/Weyl Rational Fractions
# ---------------------------------------------------------------------------

def build_pillar4_thin_shell_and_coxeter() -> dict[str, Any]:
    dims = (2, 4, 8, 16, 24, 64, 128)
    ts_rows: list[dict[str, Any]] = []
    for d in dims:
        cv_sq = Fraction(1, 2 * d)
        chi_rel_var = Fraction(2, d)
        ts_rows.append({
            "dim": d,
            "sphere": f"S^{d - 1}",
            "asymp_cv_sq_q": fmt_q(cv_sq),
            "asymp_cv_sq_dec6": fmt_dec_q(cv_sq, 6),
            "chi_sq_rel_var_q": fmt_q(chi_rel_var),
            "chi_sq_rel_var_dec6": fmt_dec_q(chi_rel_var, 6),
        })
    cv_vals = [Fraction(1, 2 * d) for d in dims]
    weyl_b = {d: (1 << d) * factorial(d) for d in (2, 3, 4, 8)}
    weyl_e8 = (2 ** 14) * (3 ** 5) * (5 ** 2) * 7
    weyl_h3 = 120
    weyl_h4 = 14400
    return {
        "thin_shell_rows": ts_rows,
        "thin_shell_cv_sq_strictly_decreasing": all(b < a for a, b in zip(cv_vals, cv_vals[1:])),
        "coxeter_weyl_orders": {
            "W_B2": weyl_b[2],
            "W_B3": weyl_b[3],
            "W_B4": weyl_b[4],
            "W_B8": weyl_b[8],
            "W_H3_icosahedral": weyl_h3,
            "W_H4_600cell": weyl_h4,
            "W_E8": weyl_e8,
            "index_W_E8_over_W_D8": (2 * weyl_e8) // weyl_b[8],
            "two_W_E8_eq_135_W_B8": 2 * weyl_e8 == 135 * weyl_b[8],
            "W_H4_eq_W_H3_sq": weyl_h4 == weyl_h3 * weyl_h3,
        },
    }


def build_payload() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "oracle_class": "exact_plus_deterministic_30digit_decimal_physics",
        "novelty_classification": "N1",
        "n2_claims": 0,
        "prior_art": [
            "Archimedes Hat-Box equal-area cylindrical projection on S^2; Hopf (1931) S^3 fibration",
            "Zador (1982) / Conway-Sloane normalized second moment G(B^d) and E_8 / A_16 / Leech lattices",
            "Fock (1935) / Moser (1970) SO(4) stereographic regularization of 3D Hydrogen and Kepler orbits on S^3",
            "Gauss-Legendre quadrature, Fibonacci spherical lattices, Halton QMC, and 600-cell (2I) spherical 11-design",
            "PREREG-SPHERE-PI-FORCES-V1 locked protocol (SHA-256 pinned in external_pins)",
        ],
        "external_pins": [
            {"id": pid, "relpath": rel, "bytes": nbytes, "sha256": sha}
            for pid, rel, nbytes, sha in EXTERNAL_PINS
        ],
        "pinned_artifacts": {
            "lean_source": LEAN_SOURCE_NAME,
            "lean_source_sha256": PINNED_LEAN_SOURCE_SHA256,
            "lean_toolchain": EXPECTED_LEAN_TOOLCHAIN,
            "lean_toolchain_sha256": PINNED_LEAN_TOOLCHAIN_SHA256,
            "lakefile_sha256": PINNED_LAKEFILE_SHA256,
            "lean_theorem_count": len(LEAN_THEOREM_NAMES),
            "lean_theorem_names": list(LEAN_THEOREM_NAMES),
            "lean_allowed_axioms": ["Quot.sound", "propext"],
        },
        "pillar1_sphere_unit_and_qpi": build_pillar1_sphere_unit_and_qpi(),
        "pillar2_em_hodge_splitting": build_pillar2_em_hodge_splitting(),
        "pillar3_denom_pi_eq_and_slots": build_pillar3_denom_pi_eq_and_slots(),
        "pillar4_thin_shell_and_coxeter": build_pillar4_thin_shell_and_coxeter(),
        "pillar5_h2b_physics_benchmarks": phys_bench.run_h2b_benchmarks(),
        "scope": {
            "phase": "Phase_1A_formal_and_physics",
            "gpu_touch": 0,
            "github_pushes": 0,
            "external_downloads": 0,
            "ieee754_floats": 0,
            "lean_proves_over": "Nat and Int (exact Q[pi] cleared identities, arbitrary-dim Z^d Hodge split, midpoint moment laws, and Coxeter/slot obstructions)",
        },
    }


def build_certificate() -> dict[str, Any]:
    payload = build_payload()
    payload_sha = sha256_hex(canonical_json_bytes(payload))
    core = {"schema_version": SCHEMA_VERSION, "track_id": TRACK_ID, "payload_sha256": payload_sha, "payload": payload}
    cert_sha = sha256_hex(canonical_json_bytes(core))
    return {**core, "certificate_sha256": cert_sha}


def main() -> int:
    print(canonical_json_bytes(build_certificate()).decode("ascii"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
