#!/usr/bin/env python3
"""Track S44 R5 Test Suite: 4 Pillars, Exported-Helper Soundness, 100% Mutation/BoolOp Killers,
>= 38 Re-Signed Non-Replay Tamper Kills & Zone-B Security.

Pure Python 3 standard library: zero AST floats, zero bare asserts, zero `.isdigit()`, zero mathematical RNG.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import formal_agent_quantum_hodge_oracle as oracle
import formal_agent_quantum_hodge_audit as audit

Err = oracle.FormalAgentQuantumHodgeError


class _SubInt(int):
    pass


class _SubStr(str):
    pass


class _SubFrac(Fraction):
    pass


class _SubPath(type(Path("."))):
    pass


class TestTrackS44FormalAgentQuantumHodgeR5(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cert = oracle.build_standalone_certificate()
        cls.payload = cls.cert["payload"]

    # -----------------------------------------------------------------------
    # 1. Four Exact Pillars
    # -----------------------------------------------------------------------

    def test_01_pillar1_hodge_symmetric_sextic(self) -> None:
        self.assertEqual(self.payload["novelty_tier"], "N1")
        self.assertEqual(self.payload["oracle_class"], "exact")
        self.assertIs(self.payload["measured_live_lean4_kernel_execution"], False)
        self.assertIs(self.payload["measured_live_deepmind_230gb_comparator"], False)
        self.assertIs(self.payload["measured_live_pequalnp_desk_submission"], False)
        self.assertIs(self.payload["zero_trust_path_floats"], True)
        self.assertIs(self.payload["zero_bare_asserts"], True)
        self.assertIs(self.payload["zero_mathematical_rng"], True)

        p1 = self.payload["pillar1_hodge_symmetric_sextic"]
        self.assertEqual(p1["case_id"], "symmetric-sextic-residual")
        self.assertEqual(p1["f_monomial_count"], 42)
        self.assertEqual(p1["f_coeff_sum"], "447/7")
        self.assertEqual(p1["cleared_7f_coeff_sum"], 447)
        self.assertEqual(p1["substituted_f_monomial_count"], 46)
        self.assertEqual(p1["substituted_f_odd_s_count"], 0)
        self.assertEqual(p1["substituted_f_odd_t_count"], 0)
        self.assertIs(p1["f_separately_even_in_s_and_t"], True)
        self.assertEqual(p1["substituted_a_monomial_count"], 4)
        self.assertIs(p1["a_separately_even_in_s_and_t"], True)
        self.assertEqual((p1["det_tau_x"], p1["det_tau_y"], p1["det_tau_xy_diagonal"]), (-1, -1, 1))
        self.assertIs(p1["residue_sign_character_neg1_neg1_certified"], True)
        self.assertEqual(p1["mod5_nonzero_term_count"], 6)
        self.assertIs(p1["mod5_matches_2_sum_sixth_powers"], True)
        self.assertIs(p1["mod5_all_6_partials_2_zk5"], True)
        self.assertIs(p1["mod5_unique_origin_smooth_certified"], True)
        self.assertIs(p1["negative_control_broken_x_parity"]["broken_x_parity_rejected"], True)
        self.assertIs(
            p1["negative_control_diagonal_permutation"]["diagonal_only_invariant_yet_breaks_independent_parity"],
            True,
        )
        self.assertIs(p1["pillar1_hodge_sextic_certified"], True)

    def test_02_pillar2_deepmind_quantum_cs21_costing(self) -> None:
        p2 = self.payload["pillar2_deepmind_quantum_cs21_costing"]
        self.assertEqual(p2["apparent_t_only_speedup_b_vs_a"], "4")
        self.assertEqual(p2["full_cost_ratio_b_over_a"], "600/401")
        self.assertEqual(p2["full_cost_ratio_b_over_a_4dp"], "1.4962")
        self.assertEqual(p2["circuit_a_silq_clean"]["full_boundary_cost"], "401")
        self.assertEqual(p2["circuit_b_classical_offload"]["full_boundary_cost"], "600")
        self.assertEqual(p2["circuit_b_classical_offload"]["hidden_cost_share"], "5/6")
        self.assertEqual(p2["circuit_c_genuine_speedup"]["full_boundary_cost"], "102")
        self.assertEqual(p2["circuit_ac_sequential"]["full_boundary_cost"], "503")
        self.assertIs(p2["appears_4x_cheaper_on_t_only"], True)
        self.assertIs(p2["full_cost_reverses_ordering"], True)
        self.assertIs(p2["genuine_speedup_wins_both_models"], True)
        self.assertIs(p2["hoare_sequential_additivity_exact"], True)
        self.assertIs(p2["cs21_offloading_obstruction_certified"], True)

        dm = p2["deepmind_discoveries_audit"]
        self.assertEqual(dm["total_reported_lean_lines"], 1_433_602)
        self.assertEqual(dm["five_suite_module_sum"], 626)
        self.assertEqual(dm["five_suite_line_sum"], 1_430_893)
        self.assertEqual(dm["shared_infra_lean_lines"], 2_709)
        self.assertIs(dm["total_lines_accounting_exact"], True)
        self.assertEqual((dm["comparator_ram_gb_lo"], dm["comparator_ram_gb_hi"]), (230, 233))
        self.assertIs(dm["ram_envelope_exceeds_200gb"], True)
        self.assertEqual(dm["grover_over_arcsin_spread_2dp"], "2803.71")
        self.assertEqual(len(dm["suites"]), 5)

    def test_03_pillar3_lean4_proof_envelope_gate(self) -> None:
        p3 = self.payload["pillar3_lean4_proof_envelope_gate"]
        self.assertEqual(p3["pinned_namespace"], "PEqualNP.Outside.lem_042")
        self.assertEqual(p3["pinned_theorem_name"], "rank_gap_obstruction")
        self.assertEqual(p3["forbidden_token_count"], 14)
        self.assertEqual(p3["adversarial_fixture_count"], 26)
        self.assertEqual(len(p3["positive_controls"]), 5)
        self.assertIs(p3["all_positive_controls_passed"], True)
        self.assertIs(p3["all_adversarial_fixtures_rejected"], True)
        self.assertIs(p3["pillar3_lean4_envelope_gate_certified"], True)

    def test_04_pillar4_cs13_honest_scope_ledger(self) -> None:
        p4 = self.payload["pillar4_cs13_honest_scope_ledger"]
        self.assertEqual(len(p4["n0_upstream_anchors"]), 3)
        self.assertEqual(len(p4["n1_certified_contributions"]), 3)
        self.assertEqual(p4["max_int_bits_exact_cap"], 3321)
        self.assertEqual(p4["max_int_digits_preparse_ceiling"], 1000)
        self.assertIs(p4["int_bits_3321_exact_cap_not_digit_biconditional"], True)
        self.assertIs(p4["zero_off_pr_internal_audit_tags"], True)
        self.assertIs(p4["cs13_honest_ledger_certified"], True)

    # -----------------------------------------------------------------------
    # 2. Exported Primitives, Domain Helpers & Canonical JSON Guards
    # -----------------------------------------------------------------------

    def test_05_primitive_parsers_formatters_and_int_bounds(self) -> None:
        self.assertEqual(oracle.require_exact_int(5, "x", min_val=5, max_val=5), 5)
        for bad in (True, False, int(5) / int(2), "5", None, _SubInt(5)):
            with self.assertRaises(Err):
                oracle.require_exact_int(bad, "x")
        with self.assertRaises(Err):
            oracle.require_exact_int(4, "x", min_val=5)
        with self.assertRaises(Err):
            oracle.require_exact_int(6, "x", max_val=5)

        self.assertIs(oracle.require_exact_bool(True, "b"), True)
        with self.assertRaises(Err):
            oracle.require_exact_bool(1, "b")
        self.assertEqual(oracle.require_exact_str("", "s", non_empty=False), "")
        with self.assertRaises(Err):
            oracle.require_exact_str("", "s", non_empty=True)
        with self.assertRaises(Err):
            oracle.require_exact_str(_SubStr("a"), "s")
        with self.assertRaises(Err):
            oracle.require_exact_str("bad\ud800sur", "s")
        self.assertEqual(oracle.require_sha256_hex("a" * 64, "h"), "a" * 64)
        for bad_hex in ("a" * 63, "A" * 64, "g" * 64, "\u00e9" * 64):
            with self.assertRaises(Err):
                oracle.require_sha256_hex(bad_hex, "h")

        self.assertEqual(oracle.require_exact_fraction(Fraction(0, 1), "q", non_negative=True), Fraction(0, 1))
        self.assertEqual(oracle.require_exact_fraction(Fraction(1, 2), "q", positive=True), Fraction(1, 2))
        for bad in (1, True, int(1) / int(2), "1/2", None, _SubFrac(1, 2)):
            with self.assertRaises(Err):
                oracle.require_exact_fraction(bad, "q")
        with self.assertRaises(Err):
            oracle.require_exact_fraction(Fraction(0, 1), "q", positive=True)
        with self.assertRaises(Err):
            oracle.require_exact_fraction(Fraction(-1, 3), "q", non_negative=True)

        self.assertEqual(oracle.parse_exact_int_ascii("0", "n"), 0)
        self.assertEqual(oracle.parse_exact_int_ascii("-42", "n"), -42)
        max_ok = (1 << oracle.MAX_INT_BITS) - 1
        too_big = 1 << oracle.MAX_INT_BITS
        self.assertEqual(len(str(max_ok)), oracle.MAX_INT_DIGITS)
        self.assertEqual(oracle.parse_exact_int_ascii(str(max_ok), "n"), max_ok)
        self.assertEqual(oracle.parse_exact_int_ascii(str(-max_ok), "n"), -max_ok)
        self.assertEqual(oracle.parse_exact_rational(oracle.format_exact_rational(Fraction(max_ok, 1)), "r"), Fraction(max_ok, 1))
        self.assertEqual(oracle.parse_exact_rational(oracle.format_exact_rational(Fraction(-max_ok, max_ok - 1)), "r"), Fraction(-max_ok, max_ok - 1))
        self.assertEqual(
            oracle.parse_strict_json_text(oracle.canonical_json_bytes({"k": max_ok}).decode("ascii"), require_object=True),
            {"k": max_ok},
        )
        # 10^1000 - 1 has 1000 digits (<= MAX_INT_DIGITS) yet 3322 bits (> MAX_INT_BITS) -> fails closed!
        for bad in ("", "-", "-0", "00", "007", "-01", "+5", " 5", "1_0", "\u00b2", "\u0661", str(too_big), "9" * oracle.MAX_INT_DIGITS, "9" * (oracle.MAX_INT_DIGITS + 1)):
            with self.assertRaises(Err):
                oracle.parse_exact_int_ascii(bad, "n")

        self.assertEqual(oracle.parse_exact_rational("7", "r"), Fraction(7, 1))
        self.assertEqual(oracle.parse_exact_rational("-3/4", "r"), Fraction(-3, 4))
        for bad in ("1/2/3", "3/1", "3/0", "3/-2", "2/4", "1/\u0662"):
            with self.assertRaises(Err):
                oracle.parse_exact_rational(bad, "r")
        self.assertEqual(oracle.format_exact_rational(Fraction(5, 1)), "5")
        self.assertEqual(oracle.format_exact_rational(Fraction(-5, 3)), "-5/3")
        self.assertEqual(oracle.format_decimal_trunc(Fraction(-7, 4), 2), "-1.75")
        self.assertEqual(oracle.format_decimal_trunc(Fraction(7, 4), 2), "1.75")
        self.assertEqual(oracle.format_decimal_trunc(Fraction(7, 4), 0), "1")
        self.assertEqual(oracle.format_decimal_trunc(Fraction(-1, 1000), 2), "0.00")
        self.assertEqual(oracle.format_decimal_trunc(Fraction(-1, 1000), 0), "0")
        self.assertEqual(oracle.format_decimal_trunc(Fraction(1, 3), 18), "0.333333333333333333")
        with self.assertRaises(Err):
            oracle.format_decimal_trunc(Fraction(1, 2), 19)

        self.assertEqual(oracle.format_exact_rational(Fraction(max_ok, 1)), str(max_ok))
        self.assertEqual(oracle.format_decimal_trunc(Fraction(max_ok, 1), 0), str(max_ok))
        for bad_q in (Fraction(too_big, 1), Fraction(1, too_big), Fraction(10 ** 4500, 1), Fraction(1, 10 ** 4500)):
            with self.assertRaises(Err) as cm_r:
                oracle.format_exact_rational(bad_q)
            self.assertEqual(cm_r.exception.code, "INT_TOO_LARGE")
            with self.assertRaises(Err) as cm_d:
                oracle.format_decimal_trunc(bad_q, 2)
            self.assertEqual(cm_d.exception.code, "INT_TOO_LARGE")

    def test_06_json_canonicalization_cycles_and_strict_parser(self) -> None:
        raw = oracle.canonical_json_bytes({"b": [1, True, None, "x"], "a": 0})
        self.assertEqual(raw, b'{"a":0,"b":[1,true,null,"x"]}')
        with self.assertRaises(Err):
            oracle.canonical_json_bytes({"f": Fraction(1, 2)})
        with self.assertRaises(Err):
            oracle.canonical_json_bytes({"f": int(3) / int(2)})
        cyc: dict[str, object] = {}
        cyc["self"] = cyc
        with self.assertRaises(Err) as cm_cyc:
            oracle.canonical_json_bytes(cyc)
        self.assertEqual(cm_cyc.exception.code, "JSON_TOO_DEEP")

        max_ok = (1 << oracle.MAX_INT_BITS) - 1
        self.assertIn(str(max_ok).encode("ascii"), oracle.canonical_json_bytes({"ok": max_ok}))
        for huge in (1 << oracle.MAX_INT_BITS, -(1 << oracle.MAX_INT_BITS), 10 ** 4300):
            with self.assertRaises(Err) as cm_hi:
                oracle.canonical_json_bytes({"big": huge})
            self.assertEqual(cm_hi.exception.code, "INT_TOO_LARGE")
        with self.assertRaises(Err) as cm_hj:
            oracle.parse_strict_json_text('{"big":' + "9" * 4500 + "}", require_object=True)
        self.assertEqual(cm_hj.exception.code, "INT_TOKEN_TOO_LONG")

        nested_ok: object = 0
        for _ in range(oracle.MAX_JSON_DEPTH):
            nested_ok = [nested_ok]
        oracle.canonical_json_bytes(nested_ok)
        with self.assertRaises(Err):
            oracle.canonical_json_bytes([nested_ok])

        exact_payload = {"s": "a" * (oracle.MAX_JSON_BYTES - 8)}
        exact_raw = oracle.canonical_json_bytes(exact_payload)
        self.assertEqual(len(exact_raw), oracle.MAX_JSON_BYTES)
        self.assertEqual(oracle.parse_strict_json_text(exact_raw.decode("ascii"), require_object=True), exact_payload)
        with self.assertRaises(Err) as cm_j1:
            oracle.canonical_json_bytes({"s": "a" * oracle.MAX_JSON_BYTES})
        self.assertEqual(cm_j1.exception.code, "JSON_TOO_LARGE")
        with self.assertRaises(Err) as cm_j2:
            oracle.parse_strict_json_text('{"s":"' + "\u00e9" * (oracle.MAX_JSON_BYTES // 2) + '"}')
        self.assertEqual(cm_j2.exception.code, "JSON_TOO_LARGE")
        for bad_json in ('{"a":1.5}', '{"a":NaN}', '{"a":1,"a":2}', "[1,2]", "{bad"):
            with self.assertRaises(Err):
                oracle.parse_strict_json_text(bad_json, require_object=True)
        self.assertEqual(oracle.parse_strict_json_text("[1,2]", require_object=False), [1, 2])

    def test_07_poly_bareiss_hoare_and_lean4_helper_boundaries(self) -> None:
        # Bareiss determinant boundaries
        sing_m = [[Fraction(1, 1), Fraction(1, 1)], [Fraction(1, 1), Fraction(1, 1)]]
        self.assertEqual(oracle.bareiss_det_exact(sing_m), Fraction(0, 1))
        id16 = [[Fraction(1, 1) if i == j else Fraction(0, 1) for j in range(16)] for i in range(16)]
        self.assertEqual(oracle.bareiss_det_exact(id16), Fraction(1, 1))
        id17 = [[Fraction(1, 1) if i == j else Fraction(0, 1) for j in range(17)] for i in range(17)]
        for bad_mat, exp_c in (
            (123, "INVALID_MATRIX"),
            ([], "INVALID_MATRIX"),
            (id17, "INVALID_MATRIX"),
            (["a"], "NON_SQUARE_MATRIX"),
            ([[Fraction(1, 1), Fraction(2, 1)]], "NON_SQUARE_MATRIX"),
        ):
            with self.assertRaises(Err) as cm_m:
                oracle.bareiss_det_exact(bad_mat)
            self.assertEqual(cm_m.exception.code, exp_c)

        # Multivariate polynomial exact arithmetic & cancellation boundaries
        p_x = {(1,): Fraction(1, 1)}
        p_neg_x = {(1,): Fraction(-1, 1)}
        self.assertEqual(oracle.poly_add_exact(p_x, p_neg_x, 1), {})
        self.assertEqual(oracle.poly_scale_exact(p_x, Fraction(0, 1), 1), {})
        self.assertEqual(oracle.poly_add_exact({(1,): Fraction(0, 1)}, p_x, 1), p_x)
        # Cancellation in poly_mul_exact: (x - 1)(x + 1) = x^2 - 1 (x term cancels!)
        p_diff = {(1,): Fraction(1, 1), (0,): Fraction(-1, 1)}
        p_sum = {(1,): Fraction(1, 1), (0,): Fraction(1, 1)}
        self.assertEqual(oracle.poly_mul_exact(p_diff, p_sum, 1), {(2,): Fraction(1, 1), (0,): Fraction(-1, 1)})
        for bad_p, exp_c in (
            ("bad", "INVALID_POLY"),
            ({"a": Fraction(1, 1)}, "INVALID_MONOMIAL"),
            ({(1, 2): Fraction(1, 1)}, "INVALID_MONOMIAL"),
        ):
            with self.assertRaises(Err) as cm_p:
                oracle.poly_scale_exact(bad_p, Fraction(1, 1), 1)
            self.assertEqual(cm_p.exception.code, exp_c)
        for bad_sub in ("a", [p_x, p_x]):
            with self.assertRaises(Err) as cm_sub:
                oracle.poly_substitute_exact(p_x, bad_sub, 1)
            self.assertEqual(cm_sub.exception.code, "INVALID_SUBS")

        # Hoare triple zero-cost boundary
        z_res = oracle.evaluate_hoare_resource_triple(0, 0, 0)
        self.assertEqual(z_res["full_boundary_cost"], "0")
        self.assertEqual(z_res["hidden_cost_share"], "0")

        # Lean 4 lexer: comments, char literals, raw strings, interpolated strings (kill every guard & BoolOp!)
        self.assertEqual(oracle.strip_lean4_comments_and_strings('a - b / c /- d/e - f -/ "x\\"y\nz" g -- h\ni').split(), ["a", "-", "b", "/", "c", "g", "i"])
        self.assertEqual(oracle.strip_lean4_comments_and_strings('r"\\" keep bar"\\"" r#"a"b\nc"# r#').split(), ["keep", "bar", "r#"])
        self.assertEqual(oracle.strip_lean4_comments_and_strings('r"\\" tail').split(), ["tail"])
        self.assertEqual(oracle.strip_lean4_comments_and_strings("r").split(), ["r"])
        self.assertEqual(oracle.strip_lean4_comments_and_strings("r_id").split(), ["r_id"])
        # Char literal boundaries: index 0, escapes, max escape len 8 vs 9, newline breaks, EOF, identifier primes
        self.assertEqual(oracle.strip_lean4_comments_and_strings("'\"' keep").split(), ["keep"])
        self.assertEqual(oracle.strip_lean4_comments_and_strings("let c := '\\'' + '\\x22' + '\\1234567'").split(), ["let", "c", ":=", "+", "+"])
        self.assertEqual(oracle.strip_lean4_comments_and_strings("x' + y'").split(), ["x'", "+", "y'"])
        self.assertEqual(oracle.strip_lean4_comments_and_strings("let _ := '\\12345678'").split(), ["let", "_", ":=", "'\\12345678'"])
        self.assertEqual(oracle.strip_lean4_comments_and_strings("let _ := '\\\n' ok").split(), ["let", "_", ":=", "'\\", "'", "ok"])
        self.assertEqual(oracle.strip_lean4_comments_and_strings("let _ := '\\a\n' ok").split(), ["let", "_", ":=", "'\\a", "'", "ok"])
        self.assertEqual(oracle.strip_lean4_comments_and_strings("let _ := '\\a").split(), ["let", "_", ":=", "'\\a"])
        self.assertEqual(oracle.strip_lean4_comments_and_strings("let _ := 'a").split(), ["let", "_", ":=", "'a"])
        self.assertEqual(oracle.strip_lean4_comments_and_strings("let _ := '' 'ab' '\n'").split(), ["let", "_", ":=", "''", "'ab'", "'", "'"])
        # Interpolated strings: s!"...", m!"...", f!"...", nested interp/braces/strings/comments, normal strings, !true
        self.assertEqual(oracle.strip_lean4_comments_and_strings('s!"hello {n} sorry"').split(), ["s", "n"])
        self.assertEqual(oracle.strip_lean4_comments_and_strings('s!"hello \\{sorry}"').split(), ["s"])
        self.assertEqual(oracle.strip_lean4_comments_and_strings('let x := "hello {sorry}"').split(), ["let", "x", ":="])
        self.assertEqual(oracle.strip_lean4_comments_and_strings('f!"a {s!"{sorry}"} b"').split(), ["f", "s", "sorry"])
        self.assertEqual(oracle.strip_lean4_comments_and_strings('s!"a { -- }\n sorry } b"').split(), ["s", "sorry"])
        self.assertEqual(oracle.strip_lean4_comments_and_strings('s!"a { let _q := "}"; sorry } b"').split(), ["s", "let", "_q", ":=", ";", "sorry"])
        self.assertEqual(oracle.strip_lean4_comments_and_strings('r#"s!"{sorry}""#').split(), [])
        self.assertEqual(oracle.strip_lean4_comments_and_strings('!true { a := 1 }').split(), ["!true", "{", "a", ":=", "1", "}"])
        with self.assertRaises(Err) as cm_ub:
            oracle.strip_lean4_comments_and_strings("/- unclosed /- inner -/")
        self.assertEqual(cm_ub.exception.code, "UNCLOSED_BLOCK_COMMENT")
        with self.assertRaises(Err) as cm_us:
            oracle.strip_lean4_comments_and_strings('let s := "unclosed')
        self.assertEqual(cm_us.exception.code, "UNCLOSED_STRING_LITERAL")
        with self.assertRaises(Err) as cm_ui:
            oracle.strip_lean4_comments_and_strings('let s := s!"unclosed {x')
        self.assertEqual(cm_ui.exception.code, "UNCLOSED_STRING_LITERAL")
        with self.assertRaises(Err) as cm_ur:
            oracle.strip_lean4_comments_and_strings('let s := r#"unclosed"')
        self.assertEqual(cm_ur.exception.code, "UNCLOSED_STRING_LITERAL")
        with self.assertRaises(Err) as cm_es:
            oracle.canonical_lean_statement_sha256("   \n\t  ")
        self.assertEqual(cm_es.exception.code, "EMPTY_STATEMENT")

        lid = "lem_042"
        tname = "rank_gap_obstruction"
        stmt = "theorem rank_gap_obstruction (n : Nat) (h : n >= 1) : n + 1 > n"
        sha = oracle.canonical_lean_statement_sha256(stmt)
        # No trailing newline + `=` at depth 0 + `:=` inside binder + benign decide variants (0 FP)
        stmt_bind = "theorem rank_gap_obstruction (n : Nat := 1) : n = n"
        sha_bind = oracle.canonical_lean_statement_sha256(stmt_bind)
        ok_bind = (
            f"namespace PEqualNP.Outside.{lid}\n{stmt_bind} := by\n"
            "  let _d1 := decide +native_ok\n"
            "  let _d2 := decide -revert\n"
            "  let _d3 := decide +revert -native\n"
            "  let _d4 := decide (config := { native := false })\n"
            "  let _d5 := decide (config := { my_native := true })\n"
            "  rfl\n"
            f"end PEqualNP.Outside.{lid}"
        )
        self.assertIs(oracle.verify_lean4_proof_envelope(ok_bind, lemma_id=lid, theorem_name=tname, expected_statement_sha256=sha_bind)["passed"], True)
        # Multiline DecideConfig and multi-flag decide +native must fail closed
        for bad_decide in (
            f"namespace PEqualNP.Outside.{lid}\n{stmt} := by\n  decide +kernel -revert +native\nend PEqualNP.Outside.{lid}\n",
            f"namespace PEqualNP.Outside.{lid}\n{stmt} := by\n  decide (config := {{\n    revert := true,\n    native := true\n  }})\nend PEqualNP.Outside.{lid}\n",
        ):
            with self.assertRaises(Err) as cm_dec:
                oracle.verify_lean4_proof_envelope(bad_decide, lemma_id=lid, theorem_name=tname, expected_statement_sha256=sha)
            self.assertEqual(cm_dec.exception.code, "FORBIDDEN_TOKEN")
        # Trailing `:` at exact EOF inside _extract_statement_before_assign
        with self.assertRaises(Err) as cm_eof_col:
            oracle._extract_statement_before_assign("theorem t :", 0)
        self.assertEqual(cm_eof_col.exception.code, "MISSING_PROOF_ASSIGN")

        for bad_src, exp_c in (
            (f"namespace PEqualNP.Outside.{lid}\nnamespace PEqualNP.Outside.{lid}\n{stmt} := by\n  omega\nend PEqualNP.Outside.{lid}\n", "INVALID_NAMESPACE"),
            (f"namespace PEqualNP.Outside.{lid}\n{stmt} := by\n  omega\nend PEqualNP.Outside.{lid}\nend PEqualNP.Outside.{lid}\n", "NAMESPACE_MISMATCH"),
            (f"namespace PEqualNP.Outside.{lid}\n{stmt} := by\n  omega\nend PEqualNP.Other.{lid}\n", "NAMESPACE_MISMATCH"),
            (f"namespace PEqualNP.Outside.{lid}\ndef helper := 1\n{stmt} := by\n  omega\nend PEqualNP.Outside.{lid}\n", "UNEXPECTED_DECLARATION"),
            (f"namespace PEqualNP.Outside.{lid}\nend PEqualNP.Outside.{lid}\n", "THEOREM_COUNT_INVALID"),
            (f"namespace PEqualNP.Outside.{lid}\ntheorem wrong_name (n : Nat) : n + 1 > n := by\n  omega\nend PEqualNP.Outside.{lid}\n", "THEOREM_NAME_MISMATCH"),
            (f"namespace PEqualNP.Outside.{lid}\n{stmt}\nend PEqualNP.Outside.{lid}\n", "MISSING_PROOF_ASSIGN"),
            (f"namespace PEqualNP.Outside.{lid}\n{stmt} : x\nend PEqualNP.Outside.{lid}\n", "MISSING_PROOF_ASSIGN"),
        ):
            with self.assertRaises(Err) as cm_l:
                oracle.verify_lean4_proof_envelope(bad_src, lemma_id=lid, theorem_name=tname, expected_statement_sha256=sha)
            self.assertEqual(cm_l.exception.code, exp_c)

    # -----------------------------------------------------------------------
    # 3. Certificate Validation, Non-Replay Schema & >= 38 Tamper Kills
    # -----------------------------------------------------------------------

    def test_08_certificate_validation_nonreplay_and_secondary_audit_killers(self) -> None:
        res_ok = audit.verify_certificate_dict(self.cert, full_replay=True)
        self.assertIs(res_ok["valid"], True)
        self.assertIs(res_ok["secondary_audit"]["secondary_audit_passed"], True)
        res_nr = audit.verify_certificate_dict(self.cert, full_replay=False)
        self.assertIs(res_nr["full_replay"], False)

        for bad_flag in ("yes", 1, 0, None):
            with self.assertRaises(Err) as cm_bf:
                oracle.validate_certificate_payload(self.cert, full_replay=bad_flag)  # type: ignore[arg-type]
            self.assertEqual(cm_bf.exception.code, "INVALID_BOOL")

        with self.assertRaises(Err) as cm_c0:
            oracle.validate_certificate_payload("not_dict")
        self.assertEqual(cm_c0.exception.code, "CERT_NOT_OBJECT")
        c_extra = copy.deepcopy(self.cert)
        c_extra["extra"] = 1
        with self.assertRaises(Err) as cm_ck:
            oracle.validate_certificate_payload(c_extra)
        self.assertEqual(cm_ck.exception.code, "INVALID_CERT_KEYS")
        for field, bad_val, exp_code in (
            ("schema", "wrong", "INVALID_SCHEMA"),
            ("track_id", "wrong", "INVALID_TRACK_ID"),
            ("payload", [], "PAYLOAD_NOT_OBJECT"),
            ("payload_sha256", "0" * 64, "PAYLOAD_SHA_MISMATCH"),
            ("certificate_sha256", "0" * 64, "CERT_SHA_MISMATCH"),
        ):
            c_bad = copy.deepcopy(self.cert)
            c_bad[field] = bad_val
            with self.assertRaises(Err) as cm_f:
                oracle.validate_certificate_payload(c_bad, full_replay=False)
            self.assertEqual(cm_f.exception.code, exp_code)

        def _resign(payload_mut: dict[str, object]) -> dict[str, object]:
            p_sha = oracle.hashlib.sha256(oracle.canonical_json_bytes(payload_mut)).hexdigest()
            core = {"schema": oracle.SCHEMA_VERSION, "track_id": oracle.TRACK_ID, "payload_sha256": p_sha, "payload": payload_mut}
            c_sha = oracle.hashlib.sha256(oracle.canonical_json_bytes(core)).hexdigest()
            return {"schema": oracle.SCHEMA_VERSION, "track_id": oracle.TRACK_ID, "payload_sha256": p_sha, "certificate_sha256": c_sha, "payload": payload_mut}

        p_tamp_replay = copy.deepcopy(self.payload)
        p_tamp_replay["pillar1_hodge_symmetric_sextic"]["f_monomial_count"] = 36
        with self.assertRaises(Err) as cm_rep:
            oracle.validate_certificate_payload(_resign(p_tamp_replay), full_replay=True)
        self.assertEqual(cm_rep.exception.code, "REPLAY_MISMATCH")

        nonreplay_mutators = [
            lambda p: p.clear(),
            lambda p: p.__setitem__("novelty_tier", "N0"),
            lambda p: p.__setitem__("oracle_class", "approx"),
            lambda p: p.__setitem__("measured_live_lean4_kernel_execution", True),
            lambda p: p.__setitem__("zero_mathematical_rng", False),
            lambda p: p.__setitem__("pillar1_hodge_symmetric_sextic", []),
            lambda p: p["pillar1_hodge_symmetric_sextic"].__setitem__("all_monomials_degree_6", 1),
            lambda p: p["pillar1_hodge_symmetric_sextic"].__setitem__("f_monomial_count", True),
            lambda p: p["pillar4_cs13_honest_scope_ledger"]["n0_upstream_anchors"].__setitem__(0, False),
        ]
        for fn in nonreplay_mutators:
            pm = copy.deepcopy(self.payload)
            fn(pm)
            with self.assertRaises(Err):
                oracle.validate_certificate_payload(_resign(pm), full_replay=False)

        with self.assertRaises(Err):
            audit.secondary_audit_payload("not_dict")
        with self.assertRaises(Err):
            audit.secondary_audit_payload({})
        with self.assertRaises(Err):
            audit._require_list_exact_len(("a", "b"), "x", 2, "ERR_LIST")
        with self.assertRaises(Err):
            audit._require_list_exact_len(["a"], "x", 2, "ERR_LIST")

        # >= 38 re-signed full_replay=False tamper kills covering EVERY pillar, nested key & semantic field!
        resigned_tamper_mutators = [
            lambda p: p.__setitem__("measured_live_deepmind_230gb_comparator", True),
            lambda p: p.__setitem__("zero_bare_asserts", False),
            lambda p: p["pillar1_hodge_symmetric_sextic"].__setitem__("extra", 1),
            lambda p: p["pillar1_hodge_symmetric_sextic"].__setitem__("case_id", "other"),
            lambda p: p["pillar1_hodge_symmetric_sextic"].__setitem__("f_monomial_count", 36),
            lambda p: p["pillar1_hodge_symmetric_sextic"].__setitem__("f_coeff_sum", "446/7"),
            lambda p: p["pillar1_hodge_symmetric_sextic"].__setitem__("cleared_7f_coeff_sum", 446),
            lambda p: p["pillar1_hodge_symmetric_sextic"].__setitem__("substituted_f_odd_s_count", 1),
            lambda p: p["pillar1_hodge_symmetric_sextic"].__setitem__("det_tau_x", 1),
            lambda p: p["pillar1_hodge_symmetric_sextic"].__setitem__("mod5_unique_origin_smooth_certified", False),
            lambda p: p["pillar1_hodge_symmetric_sextic"]["negative_control_broken_x_parity"].__setitem__("extra", 1),
            lambda p: p["pillar1_hodge_symmetric_sextic"]["negative_control_broken_x_parity"].__setitem__("odd_s_count", 0),
            lambda p: p["pillar1_hodge_symmetric_sextic"]["negative_control_diagonal_permutation"].__setitem__("odd_s_plus_t_count", 1),
            lambda p: p["pillar1_hodge_symmetric_sextic"]["negative_control_diagonal_permutation"].__setitem__("diagonal_only_invariant_yet_breaks_independent_parity", False),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"].__setitem__("extra", 1),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"].__setitem__("full_cost_reverses_ordering", False),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"]["cost_model_weights"].__setitem__("w_ctrl", "1/5"),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"]["circuit_a_silq_clean"].__setitem__("full_boundary_cost", "400"),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"]["circuit_b_classical_offload"].__setitem__("erased_bits", 0),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"]["circuit_c_genuine_speedup"].__setitem__("t_gates", 400),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"]["circuit_ac_sequential"].__setitem__("full_boundary_cost", "502"),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"].__setitem__("full_cost_ratio_b_over_a_4dp", "1.4963"),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"]["deepmind_discoveries_audit"].__setitem__("total_reported_lean_lines", 1_430_893),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"]["deepmind_discoveries_audit"].__setitem__("ram_envelope_exceeds_200gb", False),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"]["deepmind_discoveries_audit"].__setitem__("suites", []),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"]["deepmind_discoveries_audit"]["suites"].__setitem__(0, []),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"]["deepmind_discoveries_audit"]["suites"][0].__setitem__("extra", 1),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"]["deepmind_discoveries_audit"]["suites"][1].__setitem__("reported_speedup", "289"),
            lambda p: p["pillar3_lean4_proof_envelope_gate"].__setitem__("pinned_namespace", "PEqualNP.Core.lem_042"),
            lambda p: p["pillar3_lean4_proof_envelope_gate"].__setitem__("all_adversarial_fixtures_rejected", False),
            lambda p: p["pillar3_lean4_proof_envelope_gate"].__setitem__("forbidden_token_count", 10),
            lambda p: p["pillar3_lean4_proof_envelope_gate"].__setitem__("adversarial_fixture_count", 17),
            lambda p: p["pillar3_lean4_proof_envelope_gate"]["positive_controls"].__setitem__(0, []),
            lambda p: p["pillar3_lean4_proof_envelope_gate"]["positive_controls"][0].__setitem__("extra", 1),
            lambda p: p["pillar3_lean4_proof_envelope_gate"]["positive_controls"][0].__setitem__("fixture", "other"),
            lambda p: p["pillar3_lean4_proof_envelope_gate"]["adversarial_fixtures"].__setitem__(0, []),
            lambda p: p["pillar3_lean4_proof_envelope_gate"]["adversarial_fixtures"][0].__setitem__("extra", 1),
            lambda p: p["pillar3_lean4_proof_envelope_gate"]["adversarial_fixtures"][25].__setitem__("actual_error_code", "UNEXPECTED_PASS"),
            lambda p: p["pillar4_cs13_honest_scope_ledger"].__setitem__("max_int_bits_exact_cap", 4096),
            lambda p: p["pillar4_cs13_honest_scope_ledger"].__setitem__("zero_off_pr_internal_audit_tags", False),
            lambda p: p["pillar4_cs13_honest_scope_ledger"]["n0_upstream_anchors"].__setitem__(0, "tampered"),
        ]
        self.assertGreaterEqual(len(resigned_tamper_mutators), 40)
        for fn in resigned_tamper_mutators:
            pm = copy.deepcopy(self.payload)
            fn(pm)
            with self.assertRaises(Err):
                audit.verify_certificate_dict(_resign(pm), full_replay=False)

        # Zero-denominator & cross-multiplication regression tests (never raise raw ZeroDivisionError!)
        zero_denom_mutators = [
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"]["circuit_a_silq_clean"].__setitem__("full_boundary_cost", "0"),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"]["circuit_b_classical_offload"].__setitem__("full_boundary_cost", "0"),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"]["circuit_c_genuine_speedup"].__setitem__("full_boundary_cost", "0"),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"]["circuit_ac_sequential"].__setitem__("full_boundary_cost", "0"),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"]["circuit_a_silq_clean"].__setitem__("hidden_cost_share", "1/0"),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"]["cost_model_weights"].__setitem__("w_t", "0"),
            lambda p: p["pillar2_deepmind_quantum_cs21_costing"]["deepmind_discoveries_audit"]["suites"][0].__setitem__("reported_speedup", "0"),
            lambda p: p["pillar1_hodge_symmetric_sextic"].__setitem__("f_coeff_sum", "0"),
        ]
        for fn_z in zero_denom_mutators:
            pm = copy.deepcopy(self.payload)
            fn_z(pm)
            with self.assertRaises(Err):
                audit.verify_certificate_dict(_resign(pm), full_replay=False)
            with self.assertRaises(Err):
                audit.secondary_audit_payload(pm)

        for fn_direct in (
            lambda p: p.__setitem__("extra_top", 1),
            lambda p: p.__setitem__("novelty_tier", "N0"),
            lambda p: p.__setitem__("pillar1_hodge_symmetric_sextic", []),
        ):
            pm = copy.deepcopy(self.payload)
            fn_direct(pm)
            with self.assertRaises(Err):
                audit.secondary_audit_payload(pm)

    # -----------------------------------------------------------------------
    # 4. Zone-B File I/O Security, Concurrency & CLI Traps
    # -----------------------------------------------------------------------

    def test_09_zone_b_io_hardening_streaming_hardlinks_and_concurrency(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            cert_path = tdp / "cert.json"

            wres = audit.write_certificate_file(cert_path)
            self.assertIs(wres["written"], True)
            self.assertEqual(stat.S_IMODE(cert_path.stat().st_mode), 0o600)
            wres2 = audit.write_certificate_file(cert_path)
            self.assertIs(wres2["written"], True)
            self.assertEqual(audit.require_safe_path(cert_path), cert_path)
            self.assertEqual(audit.require_safe_path(tdp / "nonexistent.json"), tdp / "nonexistent.json")
            self.assertEqual(audit.require_safe_path(Path("/")), Path("/"))
            cres = audit.check_certificate_file(cert_path)
            self.assertIs(cres["valid"], True)
            self.assertIs(cres["secondary_audit"]["secondary_audit_passed"], True)

            old_cwd = os.getcwd()
            old_pwd = os.environ.get("PWD")
            try:
                os.chdir(td)
                os.environ["PWD"] = td
                self.assertEqual(audit.require_safe_path(Path("cert.json")), Path("cert.json"))
                sym_dir = tdp / "symdir"
                os.symlink(tdp, sym_dir)
                os.environ["PWD"] = str(sym_dir)
                with self.assertRaises(Err):
                    audit.require_safe_path(Path("cert.json"))
                os.environ["PWD"] = str(tdp / "no_such_dir")
                self.assertEqual(audit.require_safe_path(Path("cert.json")), Path("cert.json"))
            finally:
                os.chdir(old_cwd)
                if old_pwd is None:
                    os.environ.pop("PWD", None)
                else:
                    os.environ["PWD"] = old_pwd

            with self.assertRaises(Err):
                audit.require_safe_path("cert.json")
            with self.assertRaises(Err):
                audit.require_safe_path(_SubPath(cert_path))
            with self.assertRaises(Err):
                audit.require_safe_path(Path(f"{td}/a\x00b"))
            for bad_data in ("not_bytes", bytearray(b"x")):
                with self.assertRaises(Err) as cm_wd:
                    audit.write_regular_file_bytes(tdp / "missing_dir" / "out.json", bad_data)  # type: ignore[arg-type]
                self.assertEqual(cm_wd.exception.code, "INVALID_WRITE_DATA")
            with self.assertRaises(Err):
                audit.read_regular_bytes_capped(Path("/"))
            with self.assertRaises(Err):
                audit.write_regular_file_bytes(Path("/"), b"{}")
            with self.assertRaises(Err):
                audit.read_regular_bytes_capped(tdp)
            with self.assertRaises(Err):
                audit.write_regular_file_bytes(tdp, b"{}")

            leaf_sym = tdp / "leaf_sym.json"
            os.symlink(cert_path, leaf_sym)
            for fn_call in (
                lambda: audit.require_safe_path(leaf_sym),
                lambda: audit.read_regular_bytes_capped(leaf_sym),
                lambda: audit.write_regular_file_bytes(leaf_sym, b"{}\n"),
            ):
                with self.assertRaises(Err) as cm_s:
                    fn_call()
                self.assertEqual(cm_s.exception.code, "SYMLINK_FORBIDDEN")
            with self.assertRaises(Err) as cm_noent:
                audit.read_regular_bytes_capped(tdp / "missing.json")
            self.assertEqual(cm_noent.exception.code, "FILE_READ_ERROR")
            inter_sym = tdp / "inter_sym"
            os.symlink(tdp, inter_sym)
            with self.assertRaises(Err) as cm_is:
                audit.read_regular_bytes_capped(inter_sym / "cert.json")
            self.assertEqual(cm_is.exception.code, "SYMLINK_FORBIDDEN")
            with self.assertRaises(Err) as cm_md:
                audit.read_regular_bytes_capped(tdp / "no_dir" / "cert.json")
            self.assertEqual(cm_md.exception.code, "PATH_NOT_FOUND")

            hl_target = tdp / "hl.json"
            os.link(cert_path, hl_target)
            with self.assertRaises(Err) as cm_hl:
                audit.write_regular_file_bytes(hl_target, b"{}\n")
            self.assertEqual(cm_hl.exception.code, "HARDLINK_FORBIDDEN")
            os.unlink(hl_target)

            fifo_p = tdp / "p.fifo"
            os.mkfifo(fifo_p)
            with self.assertRaises(Err):
                audit.read_regular_bytes_capped(fifo_p)
            with self.assertRaises(Err):
                audit.write_regular_file_bytes(fifo_p, b"{}\n")

            stream_p = tdp / "stream140k.bin"
            blob140 = b"z" * 140_000
            stream_p.write_bytes(blob140)
            self.assertEqual(audit.read_regular_bytes_capped(stream_p, 140_000), blob140)
            with self.assertRaises(Err) as cm_sz:
                audit.read_regular_bytes_capped(stream_p, 139_999)
            self.assertEqual(cm_sz.exception.code, "FILE_TOO_LARGE")
            with self.assertRaises(Err) as cm_cap:
                audit.read_regular_bytes_capped(stream_p, 1 << 100)
            self.assertEqual(cm_cap.exception.code, "INT_ABOVE_MAX")
            with self.assertRaises(Err):
                audit.read_regular_bytes_capped(stream_p, 0)

            for name, raw_b, exp_code in (
                ("crlf.json", cert_path.read_bytes().replace(b"\n", b"\r\n"), "CRLF_FORBIDDEN"),
                ("nolf.json", cert_path.read_bytes().rstrip(b"\n"), "MISSING_TRAILING_LF"),
                ("badutf.json", b"\xff\xfe\n", "INVALID_UTF8"),
                ("noncan.json", b" " + cert_path.read_bytes(), "NON_CANONICAL_BYTES"),
            ):
                p = tdp / name
                p.write_bytes(raw_b)
                with self.assertRaises(Err) as cm_c:
                    audit.check_certificate_file(p)
                self.assertEqual(cm_c.exception.code, exp_code)

            tn1 = audit._next_tmp_name("col.json")
            tn2 = audit._next_tmp_name("col.json")
            self.assertNotEqual(tn1, tn2)
            seq1 = oracle.parse_exact_int_ascii(tn1.split(".")[-2], "seq1")
            seq2 = oracle.parse_exact_int_ascii(tn2.split(".")[-2], "seq2")
            self.assertEqual(seq2, seq1 + 1)

            col_target = tdp / "col.json"
            (tdp / ".col.json.s44tmp.fixed0").write_bytes(b"occupy")
            with mock.patch.object(audit, "_next_tmp_name", side_effect=[".col.json.s44tmp.fixed0", ".col.json.s44tmp.fixed1"]):
                audit.write_regular_file_bytes(col_target, b"ok\n")
            self.assertEqual(col_target.read_bytes(), b"ok\n")

            (tdp / ".col2.json.s44tmp.occ").write_bytes(b"x")
            with mock.patch.object(audit, "_next_tmp_name", return_value=".col2.json.s44tmp.occ"):
                with self.assertRaises(Err) as cm_col2:
                    audit.write_regular_file_bytes(tdp / "col2.json", b"ok\n")
            self.assertEqual(cm_col2.exception.code, "TEMP_RETRY_EXHAUSTED")

            hl_tmp_target = tdp / "hl_tmp.json"
            real_fstat = os.fstat

            def _fake_fstat(fd: int) -> os.stat_result:
                st = real_fstat(fd)
                return os.stat_result((st.st_mode, st.st_ino, st.st_dev, 2, st.st_uid, st.st_gid, st.st_size, st.st_atime, st.st_mtime, st.st_ctime))

            with mock.patch.object(audit.os, "fstat", side_effect=_fake_fstat):
                with self.assertRaises(Err) as cm_ht:
                    audit.write_regular_file_bytes(hl_tmp_target, b"ok\n")
            self.assertEqual(cm_ht.exception.code, "HARDLINK_FORBIDDEN")
            self.assertEqual(list(tdp.glob(".hl_tmp.json.s44tmp.*")), [])

            conc_target = tdp / "conc.json"
            conc_errs: list[str] = []
            conc_lock = threading.Lock()
            conc_ok = 0

            def _w(tid: int) -> None:
                nonlocal conc_ok
                data_b = f'{{"tid":{tid}}}\n'.encode("ascii")
                for _ in range(2):
                    try:
                        audit.write_regular_file_bytes(conc_target, data_b)
                        with conc_lock:
                            conc_ok += 1
                    except Exception as exc:  # pragma: no cover
                        with conc_lock:
                            conc_errs.append(f"{tid}:{type(exc).__name__}:{exc}")

            ths = [threading.Thread(target=_w, args=(i,)) for i in range(16)]
            for th in ths:
                th.start()
            for th in ths:
                th.join()
            self.assertEqual(conc_errs, [])
            self.assertEqual(conc_ok, 32)
            self.assertEqual(list(tdp.glob(".conc.json.s44tmp.*")), [])

            if os.geteuid() != 0:
                unr = tdp / "unr.json"
                unr.write_bytes(b"{}\n")
                os.chmod(unr, 0o000)
                try:
                    with self.assertRaises(Err):
                        audit.read_regular_bytes_capped(unr)
                finally:
                    os.chmod(unr, 0o600)
                unr_d = tdp / "unr_d"
                unr_d.mkdir()
                os.chmod(unr_d, 0o000)
                try:
                    with self.assertRaises(Err):
                        audit.read_regular_bytes_capped(unr_d / "x.json")
                    with self.assertRaises(Err):
                        audit.write_regular_file_bytes(unr_d / "x.json", b"{}\n")
                finally:
                    os.chmod(unr_d, 0o700)

    def test_10_cli_parsing_deleted_cwd_and_flag_traps(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            out_path = tdp / "cli_cert.json"

            for argv_ok in (
                [],
                ["--standalone"],
                ["--standalone", "--json"],
                ["--write", str(out_path), "--json"],
                ["--check", str(out_path)],
                ["--check", str(out_path), "--json"],
            ):
                buf_out = io.StringIO()
                buf_err = io.StringIO()
                old_out, old_err = sys.stdout, sys.stderr
                try:
                    sys.stdout, sys.stderr = buf_out, buf_err
                    rc = audit.main(argv_ok)
                finally:
                    sys.stdout, sys.stderr = old_out, old_err
                self.assertEqual(rc, 0)
                self.assertEqual(buf_err.getvalue(), "")

            bad_argvs: list[object] = [
                ["--write", "--json"],
                ["--write=--json"],
                ["--check=--json"],
                ["--check", "--json"],
                ["--json", "--json"],
                ["--standalone", "--standalone"],
                ["--standalone", "--check", str(out_path)],
                ["--write"],
                ["--check"],
                ["--write", ""],
                ["--stand"],
                ["--js"],
                ["--unknown"],
                ["--write", "bad\ud800.json"],
                "not_a_list",
            ]
            old_cwd = os.getcwd()
            os.chdir(td)
            try:
                for bad in bad_argvs:
                    buf_out = io.StringIO()
                    buf_err = io.StringIO()
                    old_out, old_err = sys.stdout, sys.stderr
                    try:
                        sys.stdout, sys.stderr = buf_out, buf_err
                        rc = audit.main(bad)  # type: ignore[arg-type]
                    finally:
                        sys.stdout, sys.stderr = old_out, old_err
                    self.assertEqual(rc, 2)
                    err_obj = json.loads(buf_err.getvalue())
                    self.assertIs(err_obj["valid"], False)
                    if bad == "not_a_list":
                        self.assertEqual(err_obj["error_code"], "INVALID_ARGV")
                    if bad == ["--write", ""]:
                        self.assertEqual(err_obj["error_code"], "INVALID_PATH_ARG")
                self.assertFalse((tdp / "--json").exists())
            finally:
                os.chdir(old_cwd)

            del_dir = tdp / "vanishing"
            del_dir.mkdir()
            script = (
                "import os, sys; "
                f"sys.path.insert(0, {str(_THIS_DIR)!r}); "
                "import formal_agent_quantum_hodge_audit as a; "
                f"os.chdir({str(del_dir)!r}); os.rmdir({str(del_dir)!r}); "
                "raise SystemExit(a.main(['--check', 'rel.json']))"
            )
            proc = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True, text=True, timeout=15)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("CWD_UNAVAILABLE", proc.stderr)

            kallsyms = Path("/proc/kallsyms")
            if kallsyms.exists():
                with self.assertRaises(Err) as cm_proc:
                    audit.read_regular_bytes_capped(kallsyms)
                self.assertEqual(cm_proc.exception.code, "FILE_TOO_LARGE")

    def test_11_disk_certificate_matches_standalone(self) -> None:
        disk_cert = _THIS_DIR / "formal_agent_quantum_hodge_certificate.json"
        if disk_cert.exists():
            res = audit.check_certificate_file(disk_cert)
            self.assertIs(res["valid"], True)
            self.assertEqual(res["payload_sha256"], self.cert["payload_sha256"])
            self.assertEqual(res["certificate_sha256"], self.cert["certificate_sha256"])


if __name__ == "__main__":
    unittest.main()
