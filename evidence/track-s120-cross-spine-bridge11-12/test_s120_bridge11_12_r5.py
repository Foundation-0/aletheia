#!/usr/bin/env python3
"""Assertion-free R5 verification & 100% mutation-killing test suite for Track S120.

Uses zero bare assert statements and emits zero stdout bytes on PASS.
Verifies every algebraic primitive, zero-diagonal Sylvester congruence pivot,
BRIDGE_11 / BRIDGE_12 theorem, CLI determinism, and fail-closed tamper control.
"""

from __future__ import annotations

import copy
import io
import json
import sys
from contextlib import redirect_stdout
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

_ROOT = str(Path(__file__).resolve().parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import s120_bridge11_12_certifier as s120


def fail(msg: str) -> None:
    raise RuntimeError(f"R5_S120_TEST_FAILURE: {msg}")


def check(cond: bool, msg: str) -> None:
    if not cond:
        fail(msg)


def check_raises_value_error(
    fn: Callable[[], Any],
    label: str,
    match: str | None = None,
) -> None:
    raised = False
    exc_text = ""
    try:
        fn()
    except ValueError as exc:
        raised = True
        exc_text = str(exc)
    if not raised:
        fail(f"Expected ValueError for negative/tamper control: {label}")
    if match is not None and match not in exc_text:
        fail(f"ValueError message mismatch for {label}: expected {match!r} in {exc_text!r}")


def test_primitives_and_boundary_guards() -> None:
    # Exact Q(sqrt(5)) axioms & sign edge cases
    phi = s120.Q5(Fraction(1, 2), Fraction(1, 2))
    inv_phi = s120.Q5(Fraction(-1, 2), Fraction(1, 2))
    check(phi * inv_phi == s120.Q5_ONE, "phi * phi^-1 != 1")
    check(phi.inv() == inv_phi, "phi.inv() != phi^-1")
    check(phi.a == Fraction(1, 2) and phi.b == Fraction(1, 2), "Fraction property mismatch")
    check(s120.Q5_ZERO.sign() == 0, "sign(0)")
    check(s120.Q5(3, -1).sign() == 1 and s120.Q5(2, -1).sign() == -1, "sign(a>0, b<0)")
    check(s120.Q5(-2, 1).sign() == 1 and s120.Q5(-3, 1).sign() == -1, "sign(a<0, b>0)")
    check(not (s120.Q5_ONE == 1), "Q5.__eq__ non-Q5")
    check_raises_value_error(lambda: s120.Q5_ZERO.inv(), "Q5(0).inv()", match="Q5 division by zero")

    # rho_su2_q5 unit-norm guard
    non_unit = (s120.Q5_TWO, s120.Q5_ZERO, s120.Q5_ZERO, s120.Q5_ZERO)
    check_raises_value_error(lambda: s120.rho_su2_q5(non_unit), "rho_su2_q5 non-unit", match="unit quaternion")

    # Dual inertia cross-check on zero-diagonal off-diagonal pivot & rank-deficient matrices
    z, o = s120.Q5_ZERO, s120.Q5_ONE
    hyperbolic = ((z, o, z), (o, z, z), (z, z, z))  # eigenvalues +1, -1, 0 -> (1, 1, 1)
    check(s120.inertia_descartes_q5(hyperbolic) == (1, 1, 1), "descartes hyperbolic")
    check(s120.inertia_sylvester_q5(hyperbolic) == (1, 1, 1), "sylvester hyperbolic")
    zero_mat = ((z, z, z), (z, z, z), (z, z, z))
    check(s120.inertia_descartes_q5(zero_mat) == (0, 0, 3), "descartes zero")
    check(s120.inertia_sylvester_q5(zero_mat) == (0, 0, 3), "sylvester zero")

    # Non-symmetric guard on both inertia engines
    nonsym = ((o, o, z), (z, o, z), (z, z, o))
    check_raises_value_error(lambda: s120.inertia_descartes_q5(nonsym), "descartes nonsym", match="symmetric")
    check_raises_value_error(lambda: s120.inertia_sylvester_q5(nonsym), "sylvester nonsym", match="symmetric")

    # bent4_quad_f2, bent4_polar_f2, and hadamard16_z exact boundary guards
    check(s120.bent4_quad_f2(0) == 0 and s120.bent4_quad_f2(15) == 0, "bent4 endpoints")
    check_raises_value_error(lambda: s120.bent4_quad_f2(-1), "bent4(-1)")
    check_raises_value_error(lambda: s120.bent4_quad_f2(16), "bent4(16)")
    check(s120.bent4_polar_f2(0, 15) == 0 and s120.bent4_polar_f2(1, 4) == 1, "polar endpoints")
    check_raises_value_error(lambda: s120.bent4_polar_f2(-1, 0), "polar(-1, 0)")
    check_raises_value_error(lambda: s120.bent4_polar_f2(16, 0), "polar(16, 0)")
    check_raises_value_error(lambda: s120.bent4_polar_f2(0, -1), "polar(0, -1)")
    check_raises_value_error(lambda: s120.bent4_polar_f2(0, 16), "polar(0, 16)")
    check_raises_value_error(lambda: s120.hadamard16_z((0,) * 15), "hadamard16 short")
    check_raises_value_error(lambda: s120.hadamard16_z((0,) * 17), "hadamard16 long")


def test_certificate_cli_and_tamper_controls() -> None:
    buf_json = io.StringIO()
    with redirect_stdout(buf_json):
        rc = s120.main(["--json"])
    check(rc == 0, "CLI --json rc != 0")
    cert = json.loads(buf_json.getvalue())
    s120.validate_certificate(cert)

    summary = s120.format_summary(cert)
    check(cert["payload_sha256"] in summary, "summary missing payload_sha256")
    check("BRIDGE_11" in summary and "BRIDGE_12" in summary, "summary missing bridge tags")

    buf_check = io.StringIO()
    with redirect_stdout(buf_check):
        rc = s120.main(["--check"])
    check(rc == 0 and f"PASS S120 payload_sha256={cert['payload_sha256']}" in buf_check.getvalue(), "CLI --check failed")

    # Independent cross-check of canonical Q Krein witness G_3 = diag(3,1,1), L = diag(3/5,6/5,3/5)
    # UL has diagonal (66/25, -83/25, 16/25) -> 1 negative; LU has (66/25, -2/25, -11/25) -> 2 negatives!
    check(cert["bridge_12"]["rotations"][0]["G311_inertia_UL"] == [2, 1, 0], "U_cyc G311 UL != (2,1,0)")
    check(cert["bridge_12"]["rotations"][0]["G311_inertia_LU"] == [1, 2, 0], "U_cyc G311 LU != (1,2,0)")

    # Fail-closed tamper controls covering EVERY single require_ok in validate_certificate
    def tamper(mutator: Callable[[dict[str, Any]], None], label: str) -> None:
        bad = copy.deepcopy(cert)
        mutator(bad)
        check_raises_value_error(lambda: s120.validate_certificate(bad), label)

    # BRIDGE_11 bent4_symplectic
    for field, val in (
        ("s117_bit_matches", 15),
        ("polar_identity_matches", 255),
        ("alternating_ok", False),
        ("symplectic_radical_size", 2),
        ("u4_group_order", 31),
        ("u4_unique_matrices", 31),
        ("u4_homomorphism_matches", 1023),
        ("u4_inverse_matches", 31),
        ("u4_commutator_matches", 1023),
        ("gr_u4_lie_bracket_matches", 255),
        ("pauli_4x4_commutator_matches", 255),
        ("wht_all_abs4", False),
        ("wht_self_dual_matches", 15),
    ):
        tamper(lambda d, k=field, v=val: d["bridge_11"]["bent4_symplectic"].__setitem__(k, v), f"b11.bs.{field}")

    # BRIDGE_11 h256_bent4
    for field, val in (
        ("diag_norm_matches", 255),
        ("off_diag_zero_pairs", 32639),
        ("const_warps_bent4", 1),
        ("max_abs_warp_sum_bent4", 16),
        ("const_warps_raw_h256", 0),
        ("max_abs_warp_sum_raw_h256", 16),
    ):
        tamper(lambda d, k=field, v=val: d["bridge_11"]["h256_bent4"].__setitem__(k, v), f"b11.h256.{field}")

    # BRIDGE_11 a16_secded_carry_cover
    for field, val in (
        ("valid_codewords", 2047),
        ("sec_exhaustive_matches", 32767),
        ("ded_weight2_pairs", 119),
        ("f2_syndrome_linearity_matches", 32767),
        ("bent4_mod2_lift_matches", 255),
        ("upper_nibble_faults_tested", 47),
        ("lsb_only_secded_detected", 1),
        ("integer_h16_shifted", 47),
        ("integer_h16_parseval_exact", 47),
        ("bitplane_rotated_secded_detected", 47),
        ("bridge03_cross_term_z", 0),
        ("bridge03_cross_term_mod2", 1),
    ):
        tamper(lambda d, k=field, v=val: d["bridge_11"]["a16_secded_carry_cover"].__setitem__(k, v), f"b11.cc.{field}")

    # BRIDGE_12 schur_commutant_sym3
    tamper(lambda d: d["bridge_12"]["schur_commutant_sym3"].__setitem__("rank", 4), "b12.schur.rank")
    tamper(lambda d: d["bridge_12"]["schur_commutant_sym3"].__setitem__("nullity", 2), "b12.schur.nullity")

    # BRIDGE_12 rotations count & per-rotation invariants
    tamper(lambda d: d["bridge_12"]["rotations"].pop(), "b12.rotations.count")
    for field, val in (
        ("is_exact_so3", False),
        ("dual_method_all_equal", False),
        ("scalar_I3_charpoly_identical", False),
        ("scalar_I3_inertia_UL", [1, 2, 0]),
        ("scalar_I3_inertia_LU", [1, 2, 0]),
        ("G114_n_minus_split", False),
    ):
        tamper(lambda d, k=field, v=val: d["bridge_12"]["rotations"][0].__setitem__(k, v), f"b12.rot0.{field}")

    # BRIDGE_12 canonical G311 checks
    tamper(lambda d: d["bridge_12"]["rotations"][0].__setitem__("G311_inertia_UL", [1, 2, 0]), "b12.cyc.G311.UL")
    tamper(lambda d: d["bridge_12"]["rotations"][0].__setitem__("G311_inertia_LU", [2, 1, 0]), "b12.cyc.G311.LU")
    tamper(lambda d: d["bridge_12"]["rotations"][3].__setitem__("G311_inertia_UL", [1, 2, 0]), "b12.beta.G311.UL")
    tamper(lambda d: d["bridge_12"]["rotations"][3].__setitem__("G311_inertia_LU", [2, 1, 0]), "b12.beta.G311.LU")

    # BRIDGE_12 holonomy_block_2i
    for field, val in (
        ("group_order", 119),
        ("central_neg_count", 1),
        ("zero_count", 1),
        ("nontrivial_pos_count", 117),
        ("pm_id_sign_blind_count", 119),
        ("h_plus_id_exact", "(1+0*sqrt5)"),
        ("h_tau0_exact", "(0+0*sqrt5)"),
        ("min_pos_h_exact", "(1+0*sqrt5)"),
    ):
        tamper(lambda d, k=field, v=val: d["bridge_12"]["holonomy_block_2i"].__setitem__(k, v), f"b12.hb.{field}")

    # BRIDGE_12 unified_kt_4x4_tau0_G114
    for field, val in (
        ("dual_method_all_equal", False),
        ("UL_false_I", [3, 1, 0]),
        ("LU_false_I", [2, 2, 0]),
        ("UL_true_tau0", [2, 2, 0]),
        ("LU_true_tau0", [3, 1, 0]),
    ):
        tamper(lambda d, k=field, v=val: d["bridge_12"]["unified_kt_4x4_tau0_G114"].__setitem__(k, v), f"b12.kt.{field}")


def main() -> int:
    test_primitives_and_boundary_guards()
    test_certificate_cli_and_tamper_controls()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
