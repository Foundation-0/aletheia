#!/usr/bin/env python3
"""Assertion-free R5 verification & mutation-killing test suite for Track S119.

Uses zero bare assert statements and emits zero stdout bytes on PASS.
Exercises every algebraic theorem, exact Q(sqrt(5)) & IEEE-754 FP32 DAG invariant,
boundary condition, and fail-closed tamper control in barrington_su2_dag_compiler.py.
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

import barrington_su2_dag_compiler as s119


def fail(msg: str) -> None:
    raise RuntimeError(f"R5_TEST_FAILURE: {msg}")


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


def test_q5_and_quaternion_primitives() -> None:
    # Exact Q(sqrt(5)) field axioms, canonical reduction, zero floats
    phi = s119.Q5(Fraction(1, 2), Fraction(1, 2))
    inv_phi = s119.Q5(Fraction(-1, 2), Fraction(1, 2))
    check(phi * inv_phi == s119.Q5_ONE, "phi * phi^-1 != 1")
    check(phi.inv() == inv_phi, "phi.inv() != phi^-1")
    check(phi - inv_phi == s119.Q5_ONE, "phi - phi^-1 != 1")
    check((phi / phi) == s119.Q5_ONE, "phi / phi != 1")
    check(phi.as_fractions() == (Fraction(1, 2), Fraction(1, 2)), "as_fractions mismatch")
    check(s119.Q5_ZERO.sign() == 0, "sign(0) != 0")
    check(s119.Q5_PHI_HALF.sign() == 1, "sign(phi/2) != 1")
    check((-s119.Q5_PHI_HALF).sign() == -1, "sign(-phi/2) != -1")
    check(s119.Q5_INVPHI_HALF.sign() == 1, "sign((sqrt5-1)/4) != 1")
    check((-s119.Q5_INVPHI_HALF).sign() == -1, "sign((1-sqrt5)/4) != -1")
    check(s119.Q5(3, -1).sign() == 1, "sign(3 - sqrt5) != 1")
    check(s119.Q5(2, -1).sign() == -1, "sign(2 - sqrt5) != -1")
    check(s119.Q5(-2, 1).sign() == 1, "sign(-2 + sqrt5) != 1")
    check(s119.Q5(-3, 1).sign() == -1, "sign(-3 + sqrt5) != -1")
    check(not (s119.Q5_ONE == 1), "Q5.__eq__ non-Q5 must be False")

    # Negative controls: Q5 division by zero, Cayley pole, non-unit order, infinite order
    check_raises_value_error(lambda: s119.Q5_ZERO.inv(), "Q5(0).inv()", match="Q5 division by zero")
    check_raises_value_error(
        lambda: s119.cayley_inverse_q5(s119.Q5_NEG_ID),
        "Cayley pole -I",
        match="CayleySU2 antipodal pole",
    )
    non_unit = (s119.Q5_TWO, s119.Q5_ZERO, s119.Q5_ZERO, s119.Q5_ZERO)
    check_raises_value_error(lambda: s119.q5_order(non_unit), "q5_order non-unit", match="unit norm")
    # Rational Cayley rotation with q0 = (1-5)/(1+5) = -2/3 has infinite order in SU(2)
    inf_ord_q = s119.cayley_forward_q5((s119.Q5_ONE, s119.Q5_TWO, s119.Q5_ZERO))
    check(s119.q5_norm2(inf_ord_q) == s119.Q5_ONE, "inf_ord_q must be unit norm")
    check_raises_value_error(
        lambda: s119.q5_order(inf_ord_q),
        "q5_order infinite order",
        match="exceeded finite 2I bound",
    )

    # Exact spinor decoder negative controls
    check(s119.decode_spinor_q5(s119.Q5_ID) == 0, "decode(+I) != 0")
    check(s119.decode_spinor_q5(s119.TAU0) == 1, "decode(+tau0) != 1")
    check_raises_value_error(lambda: s119.decode_spinor_q5(s119.Q5_NEG_ID), "decode_spinor_q5(-I)")
    check_raises_value_error(lambda: s119.decode_spinor_q5(s119.G_BETA), "decode_spinor_q5(G_BETA)")

    # FP32 decoder positive, negative, and exact boundary (min_dist == tol -> must raise!)
    check(s119.decode_spinor_f32(s119.ID_F32, tol=1e-5) == 0, "decode_f32(+I) != 0")
    check(s119.decode_spinor_f32(s119.TAU0_F32, tol=1e-5) == 1, "decode_f32(+tau0) != 1")
    check_raises_value_error(
        lambda: s119.decode_spinor_f32(s119.ID_F64, tol=0.0),
        "decode_spinor_f32 exact boundary tol==0.0",
    )
    check_raises_value_error(
        lambda: s119.decode_spinor_f32((0.9, 0.2, 0.2, 0.0), tol=0.05),
        "decode_spinor_f32 midpoint drift",
    )


def test_dag_builder_and_vm_guards() -> None:
    # Boundary & negative checks on DAGBuilder.add_not / add_and / build
    b = s119.DAGBuilder("guard_test")
    w0 = b.add_input()
    w1 = b.add_input()
    check_raises_value_error(lambda: b.add_not(-1), "add_not(-1)")
    check_raises_value_error(lambda: b.add_not(2), "add_not(len)")
    check_raises_value_error(lambda: b.add_and(-1, w0), "add_and(-1, 0)")
    check_raises_value_error(lambda: b.add_and(2, w0), "add_and(len, 0)")
    check_raises_value_error(lambda: b.add_and(w0, -1), "add_and(0, -1)")
    check_raises_value_error(lambda: b.add_and(w0, 2), "add_and(0, len)")
    w2 = b.add_and(w0, w1)
    check_raises_value_error(lambda: b.build(()), "build empty outputs")
    check_raises_value_error(lambda: b.build((-1,)), "build output -1")
    check_raises_value_error(lambda: b.build((3,)), "build output len")

    dag = b.build((w2,))
    # Depth boundary guards for parametric DAG constructors (depth=1 valid, depth=0 invalid)
    d1_diamond = s119.build_shared_diamond_dag(1)
    check(s119.compile_dag_to_holosphere_vring(d1_diamond).and_depth == 1, "diamond depth=1")
    d1_lyap = s119.build_all_ones_lyapunov_chain(1)
    check(s119.compile_dag_to_holosphere_vring(d1_lyap).and_depth == 1, "lyapunov depth=1")
    check_raises_value_error(lambda: s119.build_shared_diamond_dag(0), "diamond depth=0")
    check_raises_value_error(lambda: s119.build_all_ones_lyapunov_chain(0), "lyapunov depth=0")

    # eval_boolean and VM input guards
    check_raises_value_error(lambda: s119.eval_boolean(dag, (0,)), "eval_boolean short bits")
    check_raises_value_error(lambda: s119.eval_boolean(dag, (0, 1, 0)), "eval_boolean long bits")
    check_raises_value_error(lambda: s119.eval_boolean(dag, (0, 2)), "eval_boolean bit=2")
    check_raises_value_error(lambda: s119.eval_boolean(dag, (-1, 1)), "eval_boolean bit=-1")

    prog = s119.compile_dag_to_holosphere_vring(dag)
    check_raises_value_error(lambda: s119.run_q5_program(prog, (0,)), "run_q5_program width mismatch")
    check_raises_value_error(
        lambda: s119.run_fp32_program(prog, (0, 1), mode="bogus"),
        "run_fp32_program unknown mode",
    )
    check_raises_value_error(
        lambda: s119.run_fp32_program(prog, (0,), mode="cayley_reproj"),
        "run_fp32_program width mismatch",
    )


def test_semantic_circuit_truth_tables() -> None:
    # Independently verify semantic truth of adder, XOR, MAJ5, and 3-SAT against mathematical definitions
    xor4 = s119.build_xor_chain_4()
    for m in range(16):
        bits = tuple((m >> i) & 1 for i in range(4))
        check(s119.eval_boolean(xor4, bits) == (sum(bits) % 2,), f"xor4 mismatch at {bits}")

    adder = s119.build_ripple_carry_adder_4bit()
    for a_val in range(16):
        for b_val in range(16):
            bits = tuple((a_val >> i) & 1 for i in range(4)) + tuple((b_val >> i) & 1 for i in range(4))
            out = s119.eval_boolean(adder, bits)
            got = sum(out[i] << i for i in range(5))
            check(got == a_val + b_val, f"4-bit adder mismatch: {a_val}+{b_val} -> {got}")

    maj5 = s119.build_majority_5()
    for m in range(32):
        bits = tuple((m >> i) & 1 for i in range(5))
        check(s119.eval_boolean(maj5, bits) == (1 if sum(bits) >= 3 else 0,), f"maj5 mismatch at {bits}")

    sat4 = s119.build_three_sat_4var()
    sat_count = 0
    for m in range(16):
        x0, x1, x2, x3 = ((m >> i) & 1 for i in range(4))
        expected = int(
            (x0 or (not x1) or x2)
            and ((not x0) or x1 or x3)
            and (x1 or (not x2) or (not x3))
            and ((not x0) or (not x2) or x3)
            and (x0 or x2 or (not x3))
        )
        got_bit = s119.eval_boolean(sat4, (x0, x1, x2, x3))[0]
        check(got_bit == expected, f"3-SAT mismatch at {(x0, x1, x2, x3)}")
        sat_count += got_bit
    check(0 < sat_count < 16, "3-SAT instance must be non-trivial")


def test_certificate_and_tamper_controls() -> None:
    # Verify CLI --json runs build_full_certificate + validate_certificate end-to-end
    buf_json = io.StringIO()
    with redirect_stdout(buf_json):
        rc = s119.main(["--json"])
    check(rc == 0, "CLI --json returned nonzero")
    cert = json.loads(buf_json.getvalue())
    s119.validate_certificate(cert)

    # Verify summary formatter and --check CLI determinism
    summary = s119.format_summary(cert)
    check(cert["payload_sha256"] in summary, "Summary missing payload_sha256")
    check("shared_diamond_d16" in summary, "Summary missing shared_diamond_d16")

    buf_check = io.StringIO()
    with redirect_stdout(buf_check):
        rc = s119.main(["--check"])
    check(rc == 0 and f"PASS S119 payload_sha256={cert['payload_sha256']}" in buf_check.getvalue(), "CLI --check failed")

    # Exhaustive fail-closed tamper tests covering EVERY require_ok guard & boundary in validate_certificate
    def tamper(mutator: Callable[[dict[str, Any]], None], label: str) -> None:
        bad = copy.deepcopy(cert)
        mutator(bad)
        check_raises_value_error(lambda: s119.validate_certificate(bad), label)

    # Group 2I invariants
    tamper(lambda d: d["group_2i"].__setitem__("group_order", 119), "group_order != 120")
    tamper(lambda d: d["group_2i"].__setitem__("unit_norm_all_ok", False), "unit_norm_all_ok")
    tamper(lambda d: d["group_2i"].__setitem__("inverse_closed", False), "inverse_closed")
    tamper(lambda d: d["group_2i"].__setitem__("closure_all_ok", False), "closure_all_ok")
    tamper(lambda d: d["group_2i"].__setitem__("closure_pairs_checked", 14399), "closure_pairs_checked")
    tamper(lambda d: d["group_2i"].__setitem__("a5_quotient_order", 59), "a5_quotient_order")
    tamper(lambda d: d["group_2i"].__setitem__("cayley_q0_ge_0_count", 74), "cayley_q0_ge_0_count")
    tamper(lambda d: d["group_2i"].__setitem__("cayley_ge0_roundtrip_ok", 74), "cayley_ge0_roundtrip_ok")
    tamper(lambda d: d["group_2i"].__setitem__("cayley_ge0_r2_le1_ok", 74), "cayley_ge0_r2_le1_ok")
    tamper(lambda d: d["group_2i"].__setitem__("cayley_pole_count", 0), "cayley_pole_count")

    # Spinor commutator theorem invariants
    tamper(lambda d: d["spinor_commutator_theorem"].__setitem__("trace_identity_pairs_checked", 100), "trace_pairs")
    tamper(lambda d: d["spinor_commutator_theorem"].__setitem__("trace_identity_mismatches", 1), "trace_mismatches")
    tamper(lambda d: d["spinor_commutator_theorem"].__setitem__("num_conjugacy_classes", 8), "num_classes")
    tamper(
        lambda d: next(r for r in d["spinor_commutator_theorem"]["conjugacy_classes"] if r["order"] == 5).__setitem__("pos_hits", 1),
        "ord5_pos_hits",
    )
    tamper(
        lambda d: next(r for r in d["spinor_commutator_theorem"]["conjugacy_classes"] if r["order"] == 5).__setitem__("neg_hits", 9),
        "ord5_neg_hits",
    )
    tamper(
        lambda d: next(r for r in d["spinor_commutator_theorem"]["conjugacy_classes"] if r["order"] == 10 and r["q0_float"] > 0.8).__setitem__("pos_hits", 9),
        "ord10_pos_hits",
    )
    tamper(
        lambda d: next(r for r in d["spinor_commutator_theorem"]["conjugacy_classes"] if r["order"] == 10 and r["q0_float"] > 0.8).__setitem__("neg_hits", 1),
        "ord10_neg_hits",
    )
    tamper(
        lambda d: next(r for r in d["spinor_commutator_theorem"]["conjugacy_classes"] if r["order"] == 10 and r["q0_float"] > 0.8).__setitem__("q0_float", 0.8),
        "ord10_q0_boundary_0.8",
    )

    # Witness invariants & exact boundary 0.8
    for field, bad_val in (
        ("tau0_in_2i", False),
        ("tau0_order", 5),
        ("tau0_pow5_is_neg_id", False),
        ("comm_alpha_beta_equals_pos_tau0", False),
        ("sigma0_ord5_pow5_is_pos_id", False),
        ("order5_commutator_equals_neg_sigma0", False),
        ("and_truth_table_exact", False),
        ("not_truth_table_exact", False),
        ("max_intermediate_cayley_norm", 0.8),
    ):
        tamper(lambda d, k=field, v=bad_val: d["spinor_commutator_theorem"]["witness"].__setitem__(k, v), f"witness.{field}")

    # Benchmark invariants & exact boundaries
    tamper(lambda d: d["benchmarks"].pop(), "benchmark count != 7")
    tamper(lambda d: d["benchmarks"][0].__setitem__("q5_exact_matches", 0), "q5_exact_matches")
    tamper(lambda d: d["benchmarks"][0]["fp32_modes"]["s3_norm"].__setitem__("exact_decode_matches", 0), "s3_decode")
    tamper(lambda d: d["benchmarks"][0]["fp32_modes"]["cayley_reproj"].__setitem__("overflow_count", 1), "cayley_overflow")
    tamper(lambda d: d["benchmarks"][0]["fp32_modes"]["cayley_reproj"].__setitem__("max_quat_l2_err", 1e-5), "cayley_drift_boundary")
    tamper(lambda d: d["benchmarks"][0]["fp32_modes"]["binary_refresh"].__setitem__("max_quat_l2_err", 1e-6), "refresh_drift_boundary")

    # Depth-16 specific invariants & boundaries
    def d16_row(d: dict[str, Any]) -> dict[str, Any]:
        return next(r for r in d["benchmarks"] if r["name"] == "shared_diamond_d16")

    tamper(lambda d: d16_row(d).__setitem__("barrington_exact_tree_len", 100), "d16_barrington_len")
    tamper(lambda d: d16_row(d).__setitem__("vring_slots", 200), "d16_vring_slots_boundary")
    tamper(lambda d: d16_row(d)["fp32_modes"]["unnormalized"].__setitem__("overflow_count", 0), "d16_unnorm_overflow_boundary")
    tamper(lambda d: d16_row(d)["fp32_modes"]["s3_norm"].__setitem__("max_quat_l2_err", 1e-5), "d16_s3_drift_boundary")


def main() -> int:
    test_q5_and_quaternion_primitives()
    test_dag_builder_and_vm_guards()
    test_semantic_circuit_truth_tables()
    test_certificate_and_tamper_controls()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
