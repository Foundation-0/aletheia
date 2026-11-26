#!/usr/bin/env python3
"""Adversarial, Mutation-Killing & Hardened I/O Test Suite for the Modular Certificate Compressor.

Pure Python 3 standard library. Zero bare asserts, zero AST floats, zero `float()`,
zero null-device writes (scratch `os.mkfifo` only), zero `secret*` variable names.
"""
from __future__ import annotations

import copy
import ctypes
import errno
from fractions import Fraction
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import modular_cert_compressor_audit as audit  # noqa: E402
import modular_cert_compressor_oracle as oracle  # noqa: E402

_LEAN_COMPANION = _THIS_DIR / oracle.LEAN_COMPANION_FILENAME
_CERT_DISK = _THIS_DIR / "modular_cert_compressor_certificate.json"
_HAS_MKFIFO = hasattr(os, "mkfifo")
_SYS_RENAMEAT2_X86_64 = 316
_RENAME_EXCHANGE = 2


class _SubInt(int):
    pass


class _SubStr(str):
    pass


def _resign_cert(payload: dict[str, object]) -> dict[str, object]:
    p_sha = oracle.sha256_bytes(oracle.canonical_json_bytes(payload))
    cert_pre = {
        "schema_version": oracle.SCHEMA_VERSION,
        "track_id": oracle.TRACK_ID,
        "payload_sha256": p_sha,
        "payload": payload,
    }
    c_sha = oracle.sha256_bytes(oracle.canonical_json_bytes(cert_pre))
    return {
        "schema_version": oracle.SCHEMA_VERSION,
        "track_id": oracle.TRACK_ID,
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "payload": payload,
    }


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with mock.patch.object(sys, "stdout", out_buf), mock.patch.object(sys, "stderr", err_buf):
        rc = audit.main(argv)
    return (rc, out_buf.getvalue(), err_buf.getvalue())


class TestModularCertCompressorR5(unittest.TestCase):
    def test_01_strict_types_rationals_and_json_boundaries(self) -> None:
        self.assertEqual(oracle.require_exact_int(5, "x", min_val=5, max_val=5), 5)
        for bad_i, code in (
            (True, "INVALID_INT"),
            (_SubInt(1), "INVALID_INT"),
            ("1", "INVALID_INT"),
        ):
            with self.assertRaises(oracle.ModularCertError) as cm:
                oracle.require_exact_int(bad_i, "x")
            self.assertEqual(cm.exception.code, code)
        with self.assertRaises(oracle.ModularCertError) as cm_lo:
            oracle.require_exact_int(4, "x", min_val=5)
        self.assertEqual(cm_lo.exception.code, "INT_BELOW_MIN")
        with self.assertRaises(oracle.ModularCertError) as cm_hi:
            oracle.require_exact_int(6, "x", max_val=5)
        self.assertEqual(cm_hi.exception.code, "INT_ABOVE_MAX")

        self.assertIs(oracle.require_exact_bool(True, "b"), True)
        with self.assertRaises(oracle.ModularCertError) as cm_b:
            oracle.require_exact_bool(1, "b")
        self.assertEqual(cm_b.exception.code, "INVALID_BOOL")

        self.assertEqual(oracle.require_exact_str("", "s", non_empty=False), "")
        for bad_s, code in (
            (123, "INVALID_STR"),
            (_SubStr("a"), "INVALID_STR"),
            ("", "EMPTY_STR"),
            ("\ud800", "INVALID_UTF8_STR"),
        ):
            with self.assertRaises(oracle.ModularCertError) as cm:
                oracle.require_exact_str(bad_s, "s")
            self.assertEqual(cm.exception.code, code)

        good_hex = "0123456789abcdef" * 4
        self.assertEqual(oracle.require_sha256_hex(good_hex, "h"), good_hex)
        for bad_h in ("a" * 63, "a" * 65, "A" * 64, "g" * 64):
            with self.assertRaises(oracle.ModularCertError) as cm:
                oracle.require_sha256_hex(bad_h, "h")
            self.assertEqual(cm.exception.code, "INVALID_SHA256")

        # MAX_INT_BITS = 3321 exact boundary vs MAX_INT_DIGITS = 1000
        max_ok = (1 << oracle.MAX_INT_BITS) - 1
        self.assertEqual(oracle.parse_exact_int_ascii(str(max_ok), "ok"), max_ok)
        self.assertEqual(oracle.parse_exact_int_ascii("-" + str(max_ok), "ok"), -max_ok)
        self.assertEqual(oracle.parse_exact_int_ascii("0", "z"), 0)
        for bad_tok, code in (
            ("-", "INVALID_INT_TOKEN"),
            ("9" * (oracle.MAX_INT_DIGITS + 1), "INT_TOKEN_TOO_LONG"),
            ("01", "LEADING_ZERO_INT"),
            ("-01", "LEADING_ZERO_INT"),
            ("1\u0662", "NON_ASCII_DIGIT"),
            ("+1", "NON_ASCII_DIGIT"),
            ("-0", "NEGATIVE_ZERO_INT"),
            (str(1 << oracle.MAX_INT_BITS), "INT_TOO_LARGE"),
            ("9" * oracle.MAX_INT_DIGITS, "INT_TOO_LARGE"),
        ):
            with self.assertRaises(oracle.ModularCertError) as cm:
                oracle.parse_exact_int_ascii(bad_tok, "tok")
            self.assertEqual(cm.exception.code, code)

        self.assertEqual(oracle.fmt_q(Fraction(5, 1)), "5")
        self.assertEqual(oracle.fmt_q(Fraction(447, 7)), "447/7")
        with self.assertRaises(oracle.ModularCertError) as cm_fq:
            oracle.fmt_q(5)  # type: ignore[arg-type]
        self.assertEqual(cm_fq.exception.code, "INVALID_FRACTION")

        self.assertEqual(oracle.parse_exact_rational("5", "q"), Fraction(5, 1))
        self.assertEqual(oracle.parse_exact_rational("-5/7", "q"), Fraction(-5, 7))
        for bad_q, code in (
            ("1/2/3", "INVALID_RATIONAL"),
            ("3/1", "NON_CANONICAL_DEN"),
            ("1/0", "NON_CANONICAL_DEN"),
            ("1/-2", "NON_CANONICAL_DEN"),
            ("2/4", "UNREDUCED_RATIONAL"),
            ("0/2", "UNREDUCED_RATIONAL"),
        ):
            with self.assertRaises(oracle.ModularCertError) as cm:
                oracle.parse_exact_rational(bad_q, "q")
            self.assertEqual(cm.exception.code, code)

        # Strict JSON boundaries (depth, floats, constants, dup keys, CRLF, non-object, oversize, types)
        self.assertEqual(oracle.canonical_json_bytes({"a": [1, True, None, "x"]}), b'{"a":[1,true,null,"x"]}')
        exact_canon_obj = {"s": "a" * (oracle.MAX_JSON_BYTES - 8)}
        self.assertEqual(len(oracle.canonical_json_bytes(exact_canon_obj)), oracle.MAX_JSON_BYTES)
        exact_parse_txt = "{" + " " * (oracle.MAX_JSON_BYTES - 2) + "}"
        self.assertEqual(oracle.parse_strict_json_text(exact_parse_txt), {})
        with self.assertRaises(oracle.ModularCertError) as cm_ft:
            oracle.canonical_json_bytes({"a": (1, 2)})
        self.assertEqual(cm_ft.exception.code, "FORBIDDEN_JSON_TYPE")
        with self.assertRaises(oracle.ModularCertError) as cm_big:
            oracle.canonical_json_bytes({"s": "a" * oracle.MAX_JSON_BYTES})
        self.assertEqual(cm_big.exception.code, "JSON_TOO_LARGE")

        ok_nested: object = 1
        for _ in range(oracle.MAX_JSON_DEPTH):
            ok_nested = [ok_nested]
        self.assertIsInstance(oracle.canonical_json_bytes(ok_nested), bytes)
        with self.assertRaises(oracle.ModularCertError) as cm_md:
            oracle.canonical_json_bytes([ok_nested])
        self.assertEqual(cm_md.exception.code, "MAX_DEPTH_EXCEEDED")

        d_ok_str = '{"a":' * oracle.MAX_JSON_DEPTH + "1" + "}" * oracle.MAX_JSON_DEPTH
        self.assertIsInstance(oracle.parse_strict_json_text(d_ok_str), dict)
        # Brackets inside strings with escapes & extra closing braces do not false-trip or underflow
        self.assertEqual(
            oracle.parse_strict_json_text('{"a":"\\"' + "[" * 50 + '\\\\","b":1}'),
            {"a": '"' + "[" * 50 + "\\", "b": 1},
        )
        d_bad_str = '{"a":' * (oracle.MAX_JSON_DEPTH + 1) + "1" + "}" * (oracle.MAX_JSON_DEPTH + 1)
        for bad_json, code in (
            ("{" + " " * oracle.MAX_JSON_BYTES + "}", "JSON_TOO_LARGE"),
            ('{"a":1}\r\n', "CRLF_FORBIDDEN"),
            (d_bad_str, "MAX_DEPTH_EXCEEDED"),
            ("{}}" + '{"a":' * (oracle.MAX_JSON_DEPTH + 1) + "1" + "}" * (oracle.MAX_JSON_DEPTH + 1), "MAX_DEPTH_EXCEEDED"),
            ('{"a":1.5}', "JSON_FLOAT_FORBIDDEN"),
            ('{"a":NaN}', "JSON_CONSTANT_FORBIDDEN"),
            ('{"a":1,"a":2}', "DUPLICATE_JSON_KEY"),
            ("[1,2,3]", "JSON_ROOT_NOT_OBJECT"),
            ("{bad", "INVALID_JSON"),
        ):
            with self.assertRaises(oracle.ModularCertError) as cm:
                oracle.parse_strict_json_text(bad_json)
            self.assertEqual(cm.exception.code, code)

    def test_02_bareiss_rank_minors_and_hodge_compression(self) -> None:
        with self.assertRaises(oracle.ModularCertError) as cm_sb:
            oracle.sha256_bytes("not-bytes")  # type: ignore[arg-type]
        self.assertEqual(cm_sb.exception.code, "INVALID_BYTES")
        with self.assertRaises(oracle.ModularCertError) as cm_de:
            oracle.check_digest_eq("a" * 64, "\ud800" * 64)
        self.assertEqual(cm_de.exception.code, "INVALID_UTF8_STR")
        with self.assertRaises(oracle.ModularCertError) as cm_de2:
            oracle.check_digest_eq("z" * 64, "a" * 64)
        self.assertEqual(cm_de2.exception.code, "INVALID_SHA256")

        self.assertEqual(oracle.bareiss_det_int([]), 1)
        self.assertEqual(oracle.bareiss_det_int([[0, 1], [1, 0]]), -1)
        self.assertEqual(oracle.bareiss_det_int([[1, 2], [2, 4]]), 0)
        self.assertEqual(oracle.bareiss_det_int([[0, 0], [0, 1]]), 0)
        for bad_mat, exp_c in (
            (123, "INVALID_MATRIX"),
            ("bad", "INVALID_MATRIX"),
            ([[1, 2], 123], "INVALID_MATRIX"),
            ([[1, 2]], "NON_SQUARE_MATRIX"),
        ):
            with self.assertRaises(oracle.ModularCertError) as cm_bm:
                oracle.bareiss_det_int(bad_mat)  # type: ignore[arg-type]
            self.assertEqual(cm_bm.exception.code, exp_c)

        self.assertEqual(oracle.exact_rank_int([]), 0)
        self.assertEqual(oracle.exact_rank_int([[0, 0], [0, 0]]), 0)
        self.assertEqual(oracle.exact_rank_int([[0, 1], [1, 0]]), 2)
        for bad_rk, exp_c in (
            (123, "INVALID_MATRIX"),
            ("bad", "INVALID_MATRIX"),
            ([123], "INVALID_MATRIX"),
            ([[1, 2], 123], "INVALID_MATRIX"),
            ([[1, 2], [3]], "RAGGED_MATRIX"),
        ):
            with self.assertRaises(oracle.ModularCertError) as cm_rk2:
                oracle.exact_rank_int(bad_rk)  # type: ignore[arg-type]
            self.assertEqual(cm_rk2.exception.code, exp_c)

        for bad_pm, exp_c in (
            (123, "INVALID_MATRIX"),
            ("bad", "INVALID_MATRIX"),
            ([[1, 2], 123], "INVALID_MATRIX"),
            ([[1, 2]], "NON_SQUARE_MATRIX"),
        ):
            with self.assertRaises(oracle.ModularCertError) as cm_pm:
                oracle.principal_minors_int(bad_pm)  # type: ignore[arg-type]
            self.assertEqual(cm_pm.exception.code, exp_c)

        with self.assertRaises(oracle.ModularCertError) as cm_vp:
            oracle.verify_compressed_hodge_packet(123)  # type: ignore[arg-type]
        self.assertEqual(cm_vp.exception.code, "INVALID_PACKET")

        pkt = oracle.compress_hodge_sextic_packet()
        p1 = oracle.verify_compressed_hodge_packet(pkt)
        self.assertEqual(p1["monomial_count"], 42)
        self.assertEqual(p1["cleared_7f_coeff_sum"], 447)
        self.assertEqual(p1["f_coeff_sum_q"], "447/7")
        self.assertEqual(p1["det_tau_x"], -1)
        self.assertEqual(p1["det_tau_y"], -1)
        self.assertEqual(p1["det_tau_xy"], 1)
        self.assertTrue(p1["mod5_unique_origin_smooth"])
        self.assertTrue(p1["compression_ratio_gt_20m"])

        # Negative controls for verify_compressed_hodge_packet
        for mod_fn, exp_code in (
            (lambda d: d.__setitem__("cleared_7f_terms", []), "EMPTY_TERMS"),
            (lambda d: d.__setitem__("cleared_7f_terms", "bad"), "EMPTY_TERMS"),
            (lambda d: d.__setitem__("cleared_7f_terms", [[1]]), "MALFORMED_TERM"),
            (lambda d: d.__setitem__("cleared_7f_terms", ["ab"]), "MALFORMED_TERM"),
            (lambda d: d.__setitem__("cleared_7f_terms", [[[1, 2], 1]]), "MALFORMED_EXP"),
            (lambda d: d.__setitem__("cleared_7f_terms", [["123456", 1]]), "MALFORMED_EXP"),
            (lambda d: d.__setitem__("cleared_7f_terms", [[[1, 1, 1, 1, 1, 0], 1]]), "NON_SEXTIC_TERM"),
            (lambda d: d.__setitem__("cleared_7f_terms", [[[6, 0, 0, 0, 0, 0], 7], [[6, 0, 0, 0, 0, 0], 7]]), "DUPLICATE_MONOMIAL"),
            (lambda d: d["cleared_7f_terms"][0].__setitem__(1, 99), "REPLAY_MISMATCH"),
        ):
            bad_pkt = copy.deepcopy(pkt)
            mod_fn(bad_pkt)
            with self.assertRaises(oracle.ModularCertError) as cm:
                oracle.verify_compressed_hodge_packet(bad_pkt)
            self.assertEqual(cm.exception.code, exp_code)

        # Exercise PARITY_VIOLATION and MOD5_MISMATCH guards directly via patched canonical reference
        odd_s_poly = {(5, 1, 0, 0, 0, 0): 1}
        odd_pkt = copy.deepcopy(pkt)
        odd_pkt["cleared_7f_terms"] = [[[5, 1, 0, 0, 0, 0], 1]]
        with mock.patch.object(oracle, "build_hodge_cleared_7f_poly", return_value=odd_s_poly):
            with self.assertRaises(oracle.ModularCertError) as cm_ps:
                oracle.verify_compressed_hodge_packet(odd_pkt)
            self.assertEqual(cm_ps.exception.code, "PARITY_VIOLATION")

        odd_t_poly = {(0, 0, 0, 5, 1, 0): 1}
        odd_t_pkt = copy.deepcopy(pkt)
        odd_t_pkt["cleared_7f_terms"] = [[[0, 0, 0, 5, 1, 0], 1]]
        with mock.patch.object(oracle, "build_hodge_cleared_7f_poly", return_value=odd_t_poly):
            with self.assertRaises(oracle.ModularCertError) as cm_pt:
                oracle.verify_compressed_hodge_packet(odd_t_pkt)
            self.assertEqual(cm_pt.exception.code, "PARITY_VIOLATION")

        bad_mod_pkt = copy.deepcopy(pkt)
        bad_mod_pkt["mod_prime"] = 7
        with self.assertRaises(oracle.ModularCertError) as cm_m5:
            oracle.verify_compressed_hodge_packet(bad_mod_pkt)
        self.assertEqual(cm_m5.exception.code, "MOD5_MISMATCH")

        # Certificate budget guard (< 10 KiB) at exact boundary (4-digit budget shrinks serialized cert by 1 B)
        cert_len = len(oracle.canonical_json_bytes(oracle.build_certificate()))
        with mock.patch.object(oracle, "TARGET_MAX_CERT_BYTES", cert_len - 1):
            with self.assertRaises(oracle.ModularCertError) as cm_sz:
                oracle.build_certificate()
            self.assertEqual(cm_sz.exception.code, "CERT_SIZE_BUDGET_EXCEEDED")
        with mock.patch.object(oracle, "TARGET_MAX_CERT_BYTES", cert_len):
            self.assertEqual(oracle.build_certificate()["payload"]["summary"]["target_max_cert_bytes"], cert_len)

    def test_03_praxis_rank2_polya_and_carry_obstruction(self) -> None:
        for bad_g in (123, "abcd", [[1]]):
            with self.assertRaises(oracle.ModularCertError) as cm_dim:
                oracle.verify_rank1_bqs_gram_witness(bad_g)  # type: ignore[arg-type]
            self.assertEqual(cm_dim.exception.code, "INVALID_GRAM_DIM")
        for bad_gm in (
            123,
            "abcd",
            [[1, 2, 3, 4]],
            [[1, 2, 3, 4], "abcd", [1, 2, 3, 4], [1, 2, 3, 4]],
            [[1, 2, 3, 4], [1], [1, 2, 3, 4], [1, 2, 3, 4]],
        ):
            with self.assertRaises(oracle.ModularCertError) as cm_gm:
                oracle.check_unsat_bqs_sos_moments(bad_gm)  # type: ignore[arg-type]
            self.assertEqual(cm_gm.exception.code, "INVALID_GRAM_DIM")

        g2 = [[2, 2, 1, 2], [2, 2, 1, 2], [1, 1, 1, 1], [2, 2, 1, 2]]
        self.assertTrue(oracle.check_unsat_bqs_sos_moments(g2))
        g2_b1 = copy.deepcopy(g2)
        g2_b1[1][3] = 0
        self.assertFalse(oracle.check_unsat_bqs_sos_moments(g2_b1))
        g2_b2 = copy.deepcopy(g2)
        g2_b2[2][1] = 0
        self.assertFalse(oracle.check_unsat_bqs_sos_moments(g2_b2))
        g2_b3 = copy.deepcopy(g2)
        g2_b3[2][2] = 0
        self.assertFalse(oracle.check_unsat_bqs_sos_moments(g2_b3))
        with self.assertRaises(oracle.ModularCertError) as cm_rk:
            oracle.verify_rank1_bqs_gram_witness(g2)
        self.assertEqual(cm_rk.exception.code, "RANK_GAP_VIOLATION")

        cert = oracle.build_certificate()
        pl = cert["payload"]
        p1_ref = pl["pillar1_modular_hodge_compression"]
        p2_ref = pl["pillar2_adversarial_cheat_blocking"]
        p3_ref = pl["pillar3_lean4_anti_bypass_and_soundness"]
        self.assertTrue(oracle.compute_all_pillars_verified(p1_ref, p2_ref, p3_ref))
        for sec_idx, field, bad_val in (
            (0, "mod5_unique_origin_smooth", False),
            (0, "compression_ratio_gt_20m", False),
            (1, "rank1_all_2x2_minors_zero", False),
            (1, "rank2_sos_blocked_by_verifier", False),
            (1, "polya_z_valid_count", 1),
            (1, "hollow_packet_tamper_rejected", False),
            (2, "positive_controls_passed", 0),
            (2, "adversarial_fixtures_rejected", 0),
        ):
            secs = [copy.deepcopy(p1_ref), copy.deepcopy(p2_ref), copy.deepcopy(p3_ref)]
            secs[sec_idx][field] = bad_val
            self.assertFalse(oracle.compute_all_pillars_verified(secs[0], secs[1], secs[2]))
        p2 = p2_ref
        self.assertEqual(p2["rank1_honest_exact_rank"], 1)
        self.assertTrue(p2["rank1_all_2x2_minors_zero"])
        self.assertEqual(p2["unsat_bqs_boolean_witness_count"], 0)
        self.assertEqual(p2["rank2_sos_exact_rank"], 2)
        self.assertTrue(p2["rank2_sos_passes_unsat_moments"])
        self.assertTrue(p2["rank2_sos_all_15_minors_nonneg"])
        self.assertEqual(p2["rank2_sos_witness_minor_02"], 1)
        self.assertTrue(p2["rank2_sos_blocked_by_verifier"])
        self.assertEqual(p2["polya_f2_collapse_count"], 512)
        self.assertEqual(p2["polya_z_valid_count"], 0)
        self.assertEqual(p2["polya_max_perm_matches_out_of_6"], 5)
        self.assertTrue(p2["hollow_packet_tamper_rejected"])
        self.assertTrue(p2["non_canonical_unit_den_rejected"])
        self.assertTrue(p2["zero_den_rejected"])
        self.assertTrue(p2["f2_freshman_dream_holds"])
        self.assertEqual(p2["z_carry_cross_term_delta"], 4)

    def test_04_lean4_anti_bypass_lexer_and_live_lean4_companion(self) -> None:
        # _is_lean4_native_rhs_false boundaries
        self.assertTrue(oracle._is_lean4_native_rhs_false("false"))
        self.assertTrue(oracle._is_lean4_native_rhs_false("  false  "))
        self.assertTrue(oracle._is_lean4_native_rhs_false("(false)"))
        self.assertTrue(oracle._is_lean4_native_rhs_false("(( Bool.false ))"))
        for bad_rhs in ("", "   ", "(", "()", "true", "(false!", "!false)", "(false) || true"):
            self.assertFalse(oracle._is_lean4_native_rhs_false(bad_rhs))

        # Comprehensive lexer & anti-bypass coverage (raw, interp, char, nested comments, col-0, escapes, unterminated)
        for clean_src in (
            'def x := r"sorry \\ "\n',
            'def x := r#"sorry " \\ "#\n',
            'def x := r"line1\nline2"\n',
            'def x := r#a\n',
            'def x := r#',
            'def x := s!"hello \\{sorry} \\" world"\n',
            'def x := s!"line1\nline2"\n',
            'def x := s!"\\\n"\n',
            'def x := "\\\n"\n',
            'def x := "a\nb"\n',
            'def x := s!"a {let _ := { y := 1 }; 1} b"\n',
            'def x := s "hello {sorry}"\n',
            'def x := s!y\n',
            'def x := x!"bad {sorry} state"\n',
            'def c1 := \'"\'; def c2 := \'\\n\'; def x\' := 1\n',
            '/- /- nested\n  sorry -/ -/\n-- sorry\n',
            'def cfg : DecideConfig := { native := false }\n',
            'theorem t : 2 + 2 = 4 := by decide (native := false)\n',
            'theorem t : 2 + 2 = 4 := by decide (config := (({ native := ((Bool.false)) })))\n',
            'theorem t : 2 + 2 = 4 := by decide (config := { «native» := «Bool».«false» })\n',
            'theorem t : 2 + 2 = 4 := by decide (config := { native := false, maxSteps := 100 })\n',
            'theorem t : 2 + 2 = 4 := by decide (config := { native := false, })\n',
            'def f (decide : Nat) : Nat := decide+1\n',
            'def x := decide ',
            'def x := decide + (1)\n',
            'def x := decide (a + b)\n',
            'def x := decide (\n',
            ') theorem t : 1 = 1 := by decide\n',
            'def a := ("\\" sorry")\n',
            'def x := 4 / 2\n',
            'def x := "hello \\" sorry"\n',
            '-- eof_no_newline',
        ):
            r_ok = oracle.scan_lean4_anti_bypass(clean_src)
            self.assertTrue(r_ok["clean"], msg=f"false positive on {clean_src!r}: {r_ok}")

        # Exact char-literal and comment-boundary stripping checks
        for raw_c, exp_c in (
            ("'a'", "   "),
            ("'\\''", "    "),
            ("'\\n'", "    "),
            ("'a", "'a"),
            ("'\\a", "'\\a"),
            ("'\\ab", "'\\ab"),
            ("a'b'c", "a'b'c"),
            ("_'b'", "_'b'"),
            ("''b'", "''b'"),
            ("'", "'"),
            ("'\\'", "'\\'"),
            ("'ab'", "'ab'"),
        ):
            stripped_c, errs_c = oracle.strip_lean4_comments_and_strings(raw_c)
            self.assertEqual(errs_c, [])
            self.assertEqual(stripped_c, exp_c, msg=f"strip mismatch for {raw_c!r}")

        for bad_src, exp_code in (
            ('theorem t : 2 - 1 = 1 := by sorry\n', "FORBIDDEN_TOKEN:sorry"),
            ('-- comment\ntheorem t : False := sorry\n', "FORBIDDEN_TOKEN:sorry"),
            ('r"\\"\ntheorem t : False := sorry', "FORBIDDEN_TOKEN:sorry"),
            ('def a := foor"\\""\ntheorem t : False := sorry\ndef b := "\\""\n', "FORBIDDEN_TOKEN:sorry"),
            ('s!"{sorry}" ++ x', "FORBIDDEN_TOKEN:sorry"),
            ('!"{"\ntheorem t : False := sorry\ndef b := "}" ++ s', "FORBIDDEN_TOKEN:sorry"),
            ('def a := foos!"{"\ntheorem t : False := sorry\ndef b := "}"\n', "FORBIDDEN_TOKEN:sorry"),
            ('def a := Foo.s!"{"\ntheorem t : False := sorry\ndef b := "}"\n', "FORBIDDEN_TOKEN:sorry"),
            ('let _c := \'"\'\ntheorem t : False := sorry\n-- "\n', "FORBIDDEN_TOKEN:sorry"),
            ('def a := r"unterminated\n', "UNTERMINATED_STRING"),
            ('def a := "unterminated\n', "UNTERMINATED_STRING"),
            ('def a := s!"unterminated\n', "UNTERMINATED_STRING"),
            ('def a := s!"a { 1\n', "UNTERMINATED_STRING"),
            ('/- unclosed\n', "UNTERMINATED_COMMENT"),
            ('theorem t : 1 = 1 := by decide (config := ({ native := true } : DecideConfig))\n', "DECIDE_NATIVE"),
            ('def cfg : DecideConfig := { native := true }\ntheorem t : 1 = 1 := by decide +native\n', "DECIDE_NATIVE"),
            ('theorem t : 1 = 1 := by decide (native := false) +native\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide+native\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide-revert+native\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide (native := ((true)))\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide (native := (false || (true)))\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide (config := (({ native := true })))\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide (kernel := (by decide+native))\n', "DECIDE_NATIVE"),
            # All 12/12 Lean 4.36.0 decide guillemet, positional, constructor, indirect, punning & custom-infix escapes
            ('theorem t : 2 + 2 = 4 := by decide +«native»\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide («native» := true)\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide (config := { «native» := true })\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide («config» := { native := true })\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide (config := ⟨false, true, false, false⟩)\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide (config := .mk false true false false)\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide (config := Lean.Parser.Tactic.DecideConfig.mk false true false false)\n', "DECIDE_NATIVE"),
            ('def c : Lean.Parser.Tactic.DecideConfig := ⟨false, true, false, false⟩\ntheorem t : 1 = 1 := by decide (config := c)\n', "DECIDE_NATIVE"),
            ('def c0 : Lean.Parser.Tactic.DecideConfig := {}\ndef c1 := { c0 with native := true }\ntheorem t : 1 = 1 := by decide (config := c1)\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide (config := { c0 with native := false })\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide (config := { a := { b := 1 } })\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide (config := { { native := false })\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide (config := foo })\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide (config := { a := 1 } })\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide (config := { a := 1)\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide (config := { native })\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide (config := { native := false :+ false })\n', "DECIDE_NATIVE"),
            ('theorem t : 2 + 2 = 4 := by decide (config := { native := false ,+ false })\n', "DECIDE_NATIVE"),
            ('def c : DecideConfig := { native := (true : Bool) }\n', "DECIDE_NATIVE"),
            # Char, raw-string, and interpolated-string escape regression probes
            ('def _q1 : Char := \'"\'\nset_option debug.skipKernelTC true\ndef _q2 : Char := \'"\'\n', "FORBIDDEN_TOKEN:skipKernelTC"),
            ('def _r1 : String := r"\\"\nset_option debug.skipKernelTC true\n-- "\n', "FORBIDDEN_TOKEN:skipKernelTC"),
            ('def _s1 : String := s!"{ (by decide +native : 1 = 1) }"\n', "DECIDE_NATIVE"),
        ):
            r_bad = oracle.scan_lean4_anti_bypass(bad_src)
            self.assertFalse(r_bad["clean"], msg=f"missed {bad_src!r}")
            self.assertIn(exp_code, r_bad["codes"])
        self.assertFalse(oracle._is_lean4_safe_config_span("   ", 0, 3, {}))

        # ReDoS timing guard (< 200 ms each using integer nanoseconds)
        for redos_src, exp_clean in (
            ("{ " * 5000 + "\n", True),
            ("{ native := false " * 2000 + "\n", True),
            ("DecideConfig " * 2000 + "\n", True),
            ("decide " + "(" * 5000 + ")" * 5000 + "\n", True),
            ("decide (" * 5000 + "\n", True),
            ("decide (config := " + "(" * 1500 + "{ native := false }" + ")" * 1500 + "\n", True),
            ("decide (config := " * 1500 + "{ native := false }" + ")" * 1500 + "\n", False),
        ):
            t0_ns = time.monotonic_ns()
            r_perf = oracle.scan_lean4_anti_bypass(redos_src)
            elapsed_ns = time.monotonic_ns() - t0_ns
            self.assertEqual(r_perf["clean"], exp_clean)
            self.assertLess(elapsed_ns, 200_000_000)

        # Live Lean 4.36.0 companion verification on ModularCertSoundness.lean (once live; CLI formatting via fast mock)
        lean_exe = shutil.which("lean")
        if lean_exe is not None:
            res_live = audit.verify_lean_companion_file(_LEAN_COMPANION, lean_bin=lean_exe)
            self.assertTrue(res_live["valid"])
            self.assertEqual(res_live["kernel_theorems_verified"], len(oracle.LEAN_COMPANION_THEOREMS))
            self.assertEqual(res_live["banned_axioms_found"], 0)
        fake_ok_out = "\n".join(
            f"'TrackS55.ModularCertSoundness.{t}' does not depend on any axioms"
            for t in oracle.LEAN_COMPANION_THEOREMS
        )
        fake_ok = subprocess.CompletedProcess(["lean"], 0, fake_ok_out + "\n", "")
        with mock.patch.object(audit.shutil, "which", return_value="lean"), mock.patch.object(
            audit.subprocess, "run", return_value=fake_ok
        ):
            rc_v, out_v, err_v = _run_cli(["--verify-lean", str(_LEAN_COMPANION), "--json"])
            self.assertEqual(rc_v, 0, msg=err_v)
            self.assertTrue(json.loads(out_v)["valid"])
            rc_vt, out_vt, _ = _run_cli(["--verify-lean", str(_LEAN_COMPANION)])
            self.assertEqual(rc_vt, 0)
            self.assertIn("LEAN_VALID", out_vt)

        # Exercise every failure branch of verify_lean_companion_file deterministically via mocks
        with tempfile.TemporaryDirectory(prefix="s55_lean_neg_") as td:
            tdp = Path(td)
            bad_sha = tdp / "bad.lean"
            bad_sha.write_bytes(b"-- wrong\n")
            with self.assertRaises(oracle.ModularCertError) as cm_s:
                audit.verify_lean_companion_file(bad_sha)
            self.assertEqual(cm_s.exception.code, "LEAN_SHA256_MISMATCH")

            bad_utf8 = tdp / "bad_utf8.lean"
            bad_utf8.write_bytes(b"\xff\xfe")
            with mock.patch.object(oracle, "LEAN_COMPANION_SHA256", oracle.sha256_bytes(b"\xff\xfe")):
                with self.assertRaises(oracle.ModularCertError) as cm_u:
                    audit.verify_lean_companion_file(bad_utf8)
                self.assertEqual(cm_u.exception.code, "LEAN_INVALID_UTF8")

            sorry_bytes = b"theorem t : False := sorry\n"
            bad_ab = tdp / "sorry.lean"
            bad_ab.write_bytes(sorry_bytes)
            with mock.patch.object(oracle, "LEAN_COMPANION_SHA256", oracle.sha256_bytes(sorry_bytes)):
                with self.assertRaises(oracle.ModularCertError) as cm_ab:
                    audit.verify_lean_companion_file(bad_ab)
                self.assertEqual(cm_ab.exception.code, "LEAN_ANTI_BYPASS_FAILED")

        with mock.patch.object(audit.shutil, "which", return_value=None):
            with self.assertRaises(oracle.ModularCertError) as cm_nf:
                audit.verify_lean_companion_file(_LEAN_COMPANION)
            self.assertEqual(cm_nf.exception.code, "LEAN_NOT_FOUND")

        with self.assertRaises(oracle.ModularCertError) as cm_lb:
            audit.verify_lean_companion_file(_LEAN_COMPANION, lean_bin="/nonexistent_lean_xyz_999")
        self.assertEqual(cm_lb.exception.code, "LEAN_EXEC_FAILED")

        with mock.patch.object(audit.subprocess, "run", side_effect=subprocess.TimeoutExpired(["lean"], 120)):
            with self.assertRaises(oracle.ModularCertError) as cm_to:
                audit.verify_lean_companion_file(_LEAN_COMPANION, lean_bin="lean")
            self.assertEqual(cm_to.exception.code, "LEAN_EXEC_FAILED")

        fake_fail = subprocess.CompletedProcess(["lean"], 1, "", "kernel error")
        with mock.patch.object(audit.subprocess, "run", return_value=fake_fail):
            with self.assertRaises(oracle.ModularCertError) as cm_kf:
                audit.verify_lean_companion_file(_LEAN_COMPANION, lean_bin="lean")
            self.assertEqual(cm_kf.exception.code, "LEAN_KERNEL_FAILED")

        for bad_ax_out in (
            "'TrackS55.ModularCertSoundness.t' depends on axioms: [sorryAx]\n",
            "'TrackS55.ModularCertSoundness.t' depends on axioms: [t._native.native_decide.ax_1_1]\n",
            "'TrackS55.ModularCertSoundness.t' depends on axioms: [custom_ax]\n",
            "'TrackS55.ModularCertSoundness.t' depends on axioms: []\n",
        ):
            fake_ax = subprocess.CompletedProcess(["lean"], 0, bad_ax_out, "")
            with mock.patch.object(audit.subprocess, "run", return_value=fake_ax):
                with self.assertRaises(oracle.ModularCertError) as cm_ba:
                    audit.verify_lean_companion_file(_LEAN_COMPANION, lean_bin="lean")
                self.assertEqual(cm_ba.exception.code, "LEAN_BANNED_AXIOM")

        fake_miss = subprocess.CompletedProcess(["lean"], 0, "ok\n", "")
        with mock.patch.object(audit.subprocess, "run", return_value=fake_miss):
            with self.assertRaises(oracle.ModularCertError) as cm_mt:
                audit.verify_lean_companion_file(_LEAN_COMPANION, lean_bin="lean")
            self.assertEqual(cm_mt.exception.code, "LEAN_MISSING_THEOREM")

    def test_05_resigned_full_replay_false_and_exhaustive_leaf_zero_denom(self) -> None:
        cert = oracle.build_certificate()
        self.assertTrue(audit.verify_certificate_dict(cert, full_replay=True)["valid"])
        self.assertTrue(audit.verify_certificate_dict(cert, full_replay=False)["valid"])
        for bad_fr in (0, 1, "true", None):
            with self.assertRaises(oracle.ModularCertError) as cm_bfr:
                audit.verify_certificate_dict(cert, full_replay=bad_fr)  # type: ignore[arg-type]
            self.assertEqual(cm_bfr.exception.code, "INVALID_BOOL")

        # Top-level schema / track / digest / full_replay failure branches
        with self.assertRaises(oracle.ModularCertError) as cm_nondict:
            audit.verify_certificate_dict([], full_replay=False)
        self.assertEqual(cm_nondict.exception.code, "INVALID_OBJECT")
        c_ek = copy.deepcopy(cert)
        c_ek["extra"] = 1
        with self.assertRaises(oracle.ModularCertError) as cm_km:
            audit.verify_certificate_dict(c_ek, full_replay=False)
        self.assertEqual(cm_km.exception.code, "KEYSET_MISMATCH")

        for field, val, code in (
            ("schema_version", "wrong", "SCHEMA_MISMATCH"),
            ("track_id", "wrong", "TRACK_ID_MISMATCH"),
            ("payload_sha256", "0" * 64, "PAYLOAD_SHA256_MISMATCH"),
            ("certificate_sha256", "0" * 64, "CERTIFICATE_SHA256_MISMATCH"),
        ):
            c_bad = copy.deepcopy(cert)
            c_bad[field] = val
            with self.assertRaises(oracle.ModularCertError) as cm:
                audit.verify_certificate_dict(c_bad, full_replay=False)
            self.assertEqual(cm.exception.code, code)

        # Trigger FULL_REPLAY_MISMATCH via mocked build_certificate digest
        fake_replay = copy.deepcopy(cert)
        fake_replay["certificate_sha256"] = "0" * 64
        with mock.patch.object(oracle, "build_certificate", return_value=fake_replay):
            with self.assertRaises(oracle.ModularCertError) as cm_fr:
                audit.verify_certificate_dict(cert, full_replay=True)
            self.assertEqual(cm_fr.exception.code, "FULL_REPLAY_MISMATCH")

        # Targeted re-signed payload tampers hitting EVERY branch of secondary_audit_payload
        tampers: list[tuple[str, object, str]] = [
            ("track_id", "WRONG", "TRACK_ID_MISMATCH"),
            ("portal_ref", "WRONG_REF", "PORTAL_REF_MISMATCH"),
            ("pillar1_modular_hodge_compression.case_id", "wrong", "P1_CASE_MISMATCH"),
            ("pillar1_modular_hodge_compression.cleared_scale", 8, "P1_SCALAR_MISMATCH"),
            ("pillar1_modular_hodge_compression.q_exponent", 2, "P1_SCALAR_MISMATCH"),
            ("pillar1_modular_hodge_compression.mod_prime", 7, "P1_SCALAR_MISMATCH"),
            ("pillar1_modular_hodge_compression.monomial_count", 41, "P1_SCALAR_MISMATCH"),
            ("pillar1_modular_hodge_compression.cleared_7f_coeff_sum", 448, "P1_SCALAR_MISMATCH"),
            ("pillar1_modular_hodge_compression.f_coeff_sum_q", "446/7", "P1_SUM_MISMATCH"),
            ("pillar1_modular_hodge_compression.substituted_f_monomial_count", 45, "P1_REFLECTION_MISMATCH"),
            ("pillar1_modular_hodge_compression.substituted_f_odd_s", 1, "P1_REFLECTION_MISMATCH"),
            ("pillar1_modular_hodge_compression.substituted_f_odd_t", 1, "P1_REFLECTION_MISMATCH"),
            ("pillar1_modular_hodge_compression.substituted_a_monomial_count", 3, "P1_REFLECTION_MISMATCH"),
            ("pillar1_modular_hodge_compression.substituted_a_odd_s", 1, "P1_REFLECTION_MISMATCH"),
            ("pillar1_modular_hodge_compression.substituted_a_odd_t", 1, "P1_REFLECTION_MISMATCH"),
            ("pillar1_modular_hodge_compression.det_tau_x", 1, "P1_DET_MISMATCH"),
            ("pillar1_modular_hodge_compression.det_tau_y", 1, "P1_DET_MISMATCH"),
            ("pillar1_modular_hodge_compression.det_tau_xy", -1, "P1_DET_MISMATCH"),
            ("pillar1_modular_hodge_compression.mod5_nonzero_terms", 5, "P1_MOD5_COUNT"),
            ("pillar1_modular_hodge_compression.mod5_unique_origin_smooth", False, "P1_MOD5_SMOOTH"),
            ("pillar1_modular_hodge_compression.compressed_packet_bytes", 1, "P1_PACKET_PIN_MISMATCH"),
            ("pillar1_modular_hodge_compression.compressed_packet_sha256", "0" * 64, "P1_PACKET_PIN_MISMATCH"),
            ("pillar1_modular_hodge_compression.deepmind_ram_gb_envelope", [230], "P1_RAM_ENVELOPE"),
            ("pillar1_modular_hodge_compression.deepmind_ram_gb_envelope", "ab", "P1_RAM_ENVELOPE"),
            ("pillar1_modular_hodge_compression.deepmind_ram_gb_envelope", [229, 233], "P1_RAM_ENVELOPE"),
            ("pillar1_modular_hodge_compression.deepmind_ram_gb_envelope", [230, 234], "P1_RAM_ENVELOPE"),
            ("pillar1_modular_hodge_compression.compression_ratio_vs_233gb_q", "1", "P1_RATIO_MISMATCH"),
            ("pillar1_modular_hodge_compression.compression_ratio_gt_20m", False, "P1_RATIO_BOOL"),
            ("pillar2_adversarial_cheat_blocking.rank1_honest_exact_rank", 2, "P2_PRAXIS_MISMATCH"),
            ("pillar2_adversarial_cheat_blocking.rank1_all_2x2_minors_zero", False, "P2_PRAXIS_MISMATCH"),
            ("pillar2_adversarial_cheat_blocking.unsat_bqs_boolean_witness_count", 1, "P2_PRAXIS_MISMATCH"),
            ("pillar2_adversarial_cheat_blocking.rank2_sos_exact_rank", 1, "P2_PRAXIS_MISMATCH"),
            ("pillar2_adversarial_cheat_blocking.rank2_sos_passes_unsat_moments", False, "P2_PRAXIS_MISMATCH"),
            ("pillar2_adversarial_cheat_blocking.rank2_sos_all_15_minors_nonneg", False, "P2_PRAXIS_MISMATCH"),
            ("pillar2_adversarial_cheat_blocking.rank2_sos_witness_minor_02", 0, "P2_PRAXIS_MISMATCH"),
            ("pillar2_adversarial_cheat_blocking.rank2_sos_minor_mod101", 0, "P2_PRAXIS_MISMATCH"),
            ("pillar2_adversarial_cheat_blocking.rank2_sos_blocked_by_verifier", False, "P2_PRAXIS_MISMATCH"),
            ("pillar2_adversarial_cheat_blocking.rank2_sos_principal_minors.size_1", [2], "P2_MINOR_SHAPE"),
            ("pillar2_adversarial_cheat_blocking.rank2_sos_principal_minors.size_1", "abcd", "P2_MINOR_SHAPE"),
            ("pillar2_adversarial_cheat_blocking.rank2_sos_principal_minors.size_2", [0, 0, 0, 0, 0, 0], "P2_MINOR_VALUES"),
            ("pillar2_adversarial_cheat_blocking.polya_total_patterns", 511, "P2_OBSTRUCTION_MISMATCH"),
            ("pillar2_adversarial_cheat_blocking.polya_f2_collapse_count", 511, "P2_OBSTRUCTION_MISMATCH"),
            ("pillar2_adversarial_cheat_blocking.polya_z_valid_count", 1, "P2_OBSTRUCTION_MISMATCH"),
            ("pillar2_adversarial_cheat_blocking.polya_max_perm_matches_out_of_6", 6, "P2_OBSTRUCTION_MISMATCH"),
            ("pillar2_adversarial_cheat_blocking.hollow_packet_tamper_rejected", False, "P2_OBSTRUCTION_MISMATCH"),
            ("pillar2_adversarial_cheat_blocking.non_canonical_unit_den_rejected", False, "P2_OBSTRUCTION_MISMATCH"),
            ("pillar2_adversarial_cheat_blocking.zero_den_rejected", False, "P2_OBSTRUCTION_MISMATCH"),
            ("pillar2_adversarial_cheat_blocking.f2_freshman_dream_holds", False, "P2_OBSTRUCTION_MISMATCH"),
            ("pillar2_adversarial_cheat_blocking.z_carry_cross_term_delta", 0, "P2_OBSTRUCTION_MISMATCH"),
            ("pillar3_lean4_anti_bypass_and_soundness.lean_companion_filename", "x.lean", "P3_FILENAME_MISMATCH"),
            ("pillar3_lean4_anti_bypass_and_soundness.lean_companion_sha256", "0" * 64, "P3_LEAN_SHA_MISMATCH"),
            ("pillar3_lean4_anti_bypass_and_soundness.lean_companion_theorems", [], "P3_THEOREMS_MISMATCH"),
            (
                "pillar3_lean4_anti_bypass_and_soundness.lean_companion_theorems",
                {t: 1 for t in oracle.LEAN_COMPANION_THEOREMS},
                "P3_THEOREMS_MISMATCH",
            ),
            ("pillar3_lean4_anti_bypass_and_soundness.lean_companion_theorem_count", 9, "P3_COUNTS_MISMATCH"),
            ("pillar3_lean4_anti_bypass_and_soundness.forbidden_token_count", 14, "P3_COUNTS_MISMATCH"),
            ("pillar3_lean4_anti_bypass_and_soundness.positive_controls_total", 5, "P3_COUNTS_MISMATCH"),
            ("pillar3_lean4_anti_bypass_and_soundness.positive_controls_passed", 5, "P3_COUNTS_MISMATCH"),
            ("pillar3_lean4_anti_bypass_and_soundness.adversarial_fixtures_total", 15, "P3_COUNTS_MISMATCH"),
            ("pillar3_lean4_anti_bypass_and_soundness.adversarial_fixtures_rejected", 15, "P3_COUNTS_MISMATCH"),
            ("pillar4_cs13_honest_scope.novelty_tier", "N2", "P4_SCOPE_MISMATCH"),
            ("pillar4_cs13_honest_scope.oracle_class", "sampled", "P4_SCOPE_MISMATCH"),
            ("pillar4_cs13_honest_scope.max_int_bits_exact_cap", 3322, "P4_SCOPE_MISMATCH"),
            ("pillar4_cs13_honest_scope.max_int_digits_preparse_ceiling", 999, "P4_SCOPE_MISMATCH"),
            ("pillar4_cs13_honest_scope.measured_live_pequalnp_desk_submission", True, "P4_SCOPE_MISMATCH"),
            ("pillar4_cs13_honest_scope.measured_live_deepmind_233gb_comparator", True, "P4_SCOPE_MISMATCH"),
            ("pillar4_cs13_honest_scope.zero_trust_path_floats", False, "P4_SCOPE_MISMATCH"),
            ("pillar4_cs13_honest_scope.zero_bare_asserts", False, "P4_SCOPE_MISMATCH"),
            ("pillar4_cs13_honest_scope.zero_mathematical_rng", False, "P4_SCOPE_MISMATCH"),
            ("pillar4_cs13_honest_scope.prior_literature_n0", [], "P4_LIT_MISMATCH"),
            (
                "pillar4_cs13_honest_scope.prior_literature_n0",
                {x: 1 for x in oracle._PRIOR_LITERATURE_N0},
                "P4_LIT_MISMATCH",
            ),
            ("summary.all_pillars_verified", False, "SUMMARY_MISMATCH"),
            ("summary.target_max_cert_bytes", 9999, "SUMMARY_MISMATCH"),
        ]
        for dotted, new_val, exp_code in tampers:
            pl = copy.deepcopy(cert["payload"])
            parts = dotted.split(".")
            cur: Any = pl
            for key in parts[:-1]:
                cur = cur[key]
            cur[parts[-1]] = new_val
            resigned = _resign_cert(pl)
            with self.assertRaises(oracle.ModularCertError, msg=f"tamper {dotted} bypassed") as cm:
                audit.verify_certificate_dict(resigned, full_replay=False)
            self.assertEqual(cm.exception.code, exp_code, msg=f"wrong code for {dotted}: {cm.exception.code}")

        # Coupled det tampers (dtx*dty == dtxy still holds) so dtx != -1 and dty != -1 are each uniquely killed
        for det_key in ("det_tau_x", "det_tau_y"):
            pl_d = copy.deepcopy(cert["payload"])
            pl_d["pillar1_modular_hodge_compression"][det_key] = 1
            pl_d["pillar1_modular_hodge_compression"]["det_tau_xy"] = -1
            with self.assertRaises(oracle.ModularCertError) as cm_det:
                audit.verify_certificate_dict(_resign_cert(pl_d), full_replay=False)
            self.assertEqual(cm_det.exception.code, "P1_DET_MISMATCH")

        # Direct secondary_audit_payload rejects forbidden container/subclass types
        pl_sub = copy.deepcopy(cert["payload"])
        pl_sub["summary"]["target_max_cert_bytes"] = _SubInt(oracle.TARGET_MAX_CERT_BYTES)
        with self.assertRaises(oracle.ModularCertError) as cm_sub:
            audit.secondary_audit_payload(pl_sub)
        self.assertEqual(cm_sub.exception.code, "FORBIDDEN_JSON_TYPE")

        # Exhaustive recursive leaf tamper walk (including "0", "1/0", 0, False, None) -> 0 bypasses, 0 raw exceptions!
        leaf_paths: list[list[object]] = []

        def _collect_leaves(node: Any, path: list[object]) -> None:
            if type(node) is dict:
                for k, v in node.items():
                    _collect_leaves(v, path + [k])
            elif type(node) is list:
                for idx, v in enumerate(node):
                    _collect_leaves(v, path + [idx])
            else:
                leaf_paths.append(path)

        _collect_leaves(cert["payload"], [])
        self.assertGreater(len(leaf_paths), 60)
        for path in leaf_paths:
            for probe in (0, "0", "1/0", False, None):
                pl = copy.deepcopy(cert["payload"])
                cur = pl
                for seg in path[:-1]:
                    cur = cur[seg]
                if cur[path[-1]] == probe and type(cur[path[-1]]) is type(probe):
                    continue
                cur[path[-1]] = probe
                resigned = _resign_cert(pl)
                with self.assertRaises(oracle.ModularCertError, msg=f"leaf {path} -> {probe!r} bypassed"):
                    audit.verify_certificate_dict(resigned, full_replay=False)

    def test_06_zone_b_dirfd_fifo_symlinks_pwd_and_cli_strict(self) -> None:
        # Path coercion, surrogate & Darwin prefix normalization errors
        for bad_p, code in (
            ("", "EMPTY_STR"),
            ("a\x00b", "INVALID_PATH"),
            ("a\ud800b", "INVALID_UTF8_STR"),
            (Path("a\x00b"), "INVALID_PATH"),
            (Path("a\ud800b"), "INVALID_UTF8_STR"),
            (123, "INVALID_PATH_TYPE"),
            (_SubStr("x"), "INVALID_PATH_TYPE"),
        ):
            with self.assertRaises(oracle.ModularCertError) as cm:
                audit._coerce_exact_path(bad_p, "p")
            self.assertEqual(cm.exception.code, code)

        root_lnk = os.stat_result((stat.S_IFLNK | 0o777, 0, 0, 1, 0, 0, 0, 0, 0, 0))
        non_lnk = os.stat_result((stat.S_IFDIR | 0o755, 0, 0, 1, 0, 0, 0, 0, 0, 0))
        user_lnk = os.stat_result((stat.S_IFLNK | 0o777, 0, 0, 1, 1000, 0, 0, 0, 0, 0))
        with (
            mock.patch.object(audit.sys, "platform", "linux"),
            mock.patch.object(audit.os, "lstat", return_value=root_lnk),
            mock.patch.object(audit.os, "readlink", return_value="/private/tmp"),
        ):
            self.assertEqual(audit._normalize_darwin_system_prefix(Path("/tmp/a.json")), Path("/tmp/a.json"))
        with mock.patch.object(audit.sys, "platform", "darwin"):
            with mock.patch.object(audit.os, "lstat", return_value=root_lnk), mock.patch.object(audit.os, "readlink", return_value="private/tmp"):
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("x/tmp/y")), Path("x/tmp/y"))
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("/tmp"), allow_exact=False), Path("/tmp"))
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("/tmp/../a")), Path("/tmp/../a"))
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("/usr/a")), Path("/usr/a"))
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("/tmp/x/y")), Path("/private/tmp/x/y"))
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("/tmp"), allow_exact=True), Path("/private/tmp"))
            with mock.patch.object(audit.os, "lstat", return_value=root_lnk), mock.patch.object(audit.os, "readlink", return_value="/private/var"):
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("/var/x")), Path("/private/var/x"))
            with mock.patch.object(audit.os, "lstat", return_value=non_lnk), mock.patch.object(audit.os, "readlink", return_value="/private/tmp"):
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("/tmp/x")), Path("/tmp/x"))
            with mock.patch.object(audit.os, "lstat", return_value=user_lnk), mock.patch.object(audit.os, "readlink", return_value="/private/tmp"):
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("/tmp/x")), Path("/tmp/x"))
            with mock.patch.object(audit.os, "lstat", return_value=root_lnk), mock.patch.object(audit.os, "readlink", return_value="/evil"):
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("/tmp/x")), Path("/tmp/x"))
            with mock.patch.object(audit.os, "lstat", side_effect=OSError("nope")):
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("/tmp/x")), Path("/tmp/x"))

        with tempfile.TemporaryDirectory(prefix="s55_zb_") as td:
            root = Path(td).resolve()
            real_f = root / "ok.json"
            real_f.write_bytes(b'{"k":1}\n')
            sym_f = root / "sym.json"
            os.symlink(real_f, sym_f)
            sub_dir = root / "sub"
            sub_dir.mkdir()
            sym_dir = root / "sym_dir"
            os.symlink(sub_dir, sym_dir)

            self.assertEqual(audit.read_regular_bytes_capped(real_f, max_bytes=len(b'{"k":1}\n')), b'{"k":1}\n')
            with self.assertRaises(oracle.ModularCertError) as cm_big:
                audit.read_regular_bytes_capped(real_f, max_bytes=3)
            self.assertEqual(cm_big.exception.code, "FILE_TOO_LARGE")

            for bad_r, code in (
                (root / "missing.json", "FILE_UNREADABLE"),
                (sym_f, "SYMLINK_FORBIDDEN"),
                (sym_dir / "x.json", "SYMLINK_FORBIDDEN"),
                (real_f / "child", "NOT_A_DIRECTORY"),
                (root / "sub" / ".." / "ok.json", "PARENT_TRAVERSAL_FORBIDDEN"),
                (str(root) + "/", "INVALID_FILENAME"),
                (Path("/"), "INVALID_FILENAME"),
                (root / "missing_dir" / "a.json", "DIR_OPEN_FAILED"),
                (sub_dir, "NON_REGULAR_FILE"),
            ):
                with self.assertRaises(oracle.ModularCertError, msg=f"expected {code} for {bad_r}") as cm:
                    audit.read_regular_bytes_capped(bad_r)
                self.assertEqual(cm.exception.code, code)

            # Relative path + $PWD symlink / mismatch + deleted CWD
            orig_cwd = os.getcwd()
            orig_pwd = os.environ.get("PWD")
            try:
                os.chdir(sub_dir)
                os.environ["PWD"] = str(sub_dir)
                (sub_dir / "rel.txt").write_bytes(b"rel")
                self.assertEqual(audit.read_regular_bytes_capped("rel.txt"), b"rel")
                os.environ["PWD"] = str(sym_dir)
                with self.assertRaises(oracle.ModularCertError) as cm_ps:
                    audit.read_regular_bytes_capped("rel.txt")
                self.assertEqual(cm_ps.exception.code, "SYMLINK_FORBIDDEN")
                # Stale unrelated & non-existent $PWD pass cleanly; race mismatch & surrogate/NUL $PWD reject cleanly
                os.environ["PWD"] = str(root)
                self.assertEqual(audit.read_regular_bytes_capped("rel.txt"), b"rel")
                os.environ["PWD"] = "/nonexistent_stale_pwd_99999"
                self.assertEqual(audit.read_regular_bytes_capped("rel.txt"), b"rel")
                os.environ["PWD"] = "."
                self.assertEqual(audit.read_regular_bytes_capped("rel.txt"), b"rel")
                os.environ.pop("PWD", None)
                self.assertEqual(audit.read_regular_bytes_capped("rel.txt"), b"rel")
                with mock.patch.object(audit.os, "environ", {"PWD": "/tmp/\ud800"}):
                    with self.assertRaises(oracle.ModularCertError) as cm_surp:
                        audit.read_regular_bytes_capped("rel.txt")
                    self.assertEqual(cm_surp.exception.code, "INVALID_UTF8_STR")
                with mock.patch.object(audit.os, "environ", {"PWD": "/tmp/a\x00b"}):
                    with self.assertRaises(oracle.ModularCertError) as cm_nulp:
                        audit.read_regular_bytes_capped("rel.txt")
                    self.assertEqual(cm_nulp.exception.code, "INVALID_PATH")
                os.environ["PWD"] = str(sub_dir)
                fake_diff_dir = os.stat_result((stat.S_IFDIR | 0o755, 1111111, 2222222, 2, 0, 0, 0, 0, 0, 0))
                with mock.patch.object(audit.os, "fstat", return_value=fake_diff_dir):
                    with self.assertRaises(oracle.ModularCertError) as cm_pm:
                        audit._verify_pwd_not_symlink()
                    self.assertEqual(cm_pm.exception.code, "PWD_SYMLINK_MISMATCH")
            finally:
                os.chdir(orig_cwd)
                if orig_pwd is not None:
                    os.environ["PWD"] = orig_pwd
                else:
                    os.environ.pop("PWD", None)

            # Deleted CWD & dir_open ENOENT / EACCES branches
            with mock.patch.object(audit.os, "open", side_effect=OSError(errno.ENOENT, "gone")):
                with self.assertRaises(oracle.ModularCertError) as cm_eno:
                    audit._open_dir_chain_nofollow((), root_abs=False)
                self.assertEqual(cm_eno.exception.code, "CWD_UNAVAILABLE")
            with mock.patch.object(audit.os, "open", side_effect=OSError(errno.EACCES, "denied")):
                with self.assertRaises(oracle.ModularCertError) as cm_eac:
                    audit._open_dir_chain_nofollow((), root_abs=True)
                self.assertEqual(cm_eac.exception.code, "DIR_OPEN_FAILED")
            with mock.patch.object(audit.os, "stat", side_effect=OSError(errno.ENOENT, "gone")):
                with mock.patch.dict(os.environ, {"PWD": str(root)}):
                    with self.assertRaises(oracle.ModularCertError) as cm_st:
                        audit._verify_pwd_not_symlink()
                    self.assertEqual(cm_st.exception.code, "CWD_UNAVAILABLE")
            with mock.patch.object(audit, "_verify_pwd_not_symlink"), mock.patch.object(
                audit.os, "getcwd", side_effect=OSError(errno.ENOENT, "gone")
            ):
                with self.assertRaises(oracle.ModularCertError) as cm_gc:
                    audit._open_parent_dir_fd(Path("rel.txt"))
                self.assertEqual(cm_gc.exception.code, "CWD_UNAVAILABLE")
            # Exercise empty/dot component skip inside _open_dir_chain_nofollow
            dfd_dot = audit._open_dir_chain_nofollow(("", "."), root_abs=True)
            os.close(dfd_dot)

            # Scratch os.mkfifo non-blocking refusal BEFORE any target/temp os.open (zero null-device writes!)
            orig_open = os.open
            orig_fstat = os.fstat
            if _HAS_MKFIFO:
                fifo = root / "pipe_ctl"
                os.mkfifo(fifo)
                opened_non_dir: list[str] = []

                def _spy_open(path_arg: Any, flags: int, *args: Any, **kwargs: Any) -> int:
                    if not (flags & os.O_DIRECTORY):
                        opened_non_dir.append(str(path_arg))
                    return orig_open(path_arg, flags, *args, **kwargs)

                with mock.patch.object(audit.os, "open", side_effect=_spy_open):
                    with self.assertRaises(oracle.ModularCertError) as cm_fr:
                        audit.read_regular_bytes_capped(fifo)
                    self.assertEqual(cm_fr.exception.code, "NON_REGULAR_FILE")
                    with self.assertRaises(oracle.ModularCertError) as cm_fw:
                        audit.write_bytes_atomic_0600(fifo, b"x")
                    self.assertEqual(cm_fw.exception.code, "NON_REGULAR_FILE")
                self.assertEqual(opened_non_dir, [], msg=f"FIFO opened before lstat gate: {opened_non_dir}")

            # Mocked read races: ELOOP, generic open error, fstat non-reg, TOCTOU swap

            def _open_eloop(path_arg: Any, flags: int, *args: Any, **kwargs: Any) -> int:
                if path_arg == "ok.json":
                    raise OSError(errno.ELOOP, "loop")
                return orig_open(path_arg, flags, *args, **kwargs)

            with mock.patch.object(audit.os, "open", side_effect=_open_eloop):
                with self.assertRaises(oracle.ModularCertError) as cm_el:
                    audit.read_regular_bytes_capped(real_f)
                self.assertEqual(cm_el.exception.code, "SYMLINK_FORBIDDEN")

            def _open_eacces(path_arg: Any, flags: int, *args: Any, **kwargs: Any) -> int:
                if path_arg == "ok.json":
                    raise OSError(errno.EACCES, "denied")
                return orig_open(path_arg, flags, *args, **kwargs)

            with mock.patch.object(audit.os, "open", side_effect=_open_eacces):
                with self.assertRaises(oracle.ModularCertError) as cm_ea:
                    audit.read_regular_bytes_capped(real_f)
                self.assertEqual(cm_ea.exception.code, "FILE_UNREADABLE")

            st_rf = os.lstat(real_f)
            fake_fifo_st = os.stat_result((stat.S_IFIFO | 0o600, st_rf.st_ino, st_rf.st_dev, 1, 0, 0, 0, 0, 0, 0))
            with mock.patch.object(audit.os, "fstat", return_value=fake_fifo_st):
                with self.assertRaises(oracle.ModularCertError) as cm_fnr:
                    audit.read_regular_bytes_capped(real_f)
                self.assertEqual(cm_fnr.exception.code, "NON_REGULAR_FILE")

            with mock.patch.object(audit.os, "fstat", side_effect=OSError("fstat fail")):
                with self.assertRaises(oracle.ModularCertError) as cm_fst:
                    audit.read_regular_bytes_capped(real_f)
                self.assertEqual(cm_fst.exception.code, "READ_IO_ERROR")

            fake_hl_read = os.stat_result((stat.S_IFREG | 0o600, st_rf.st_ino, st_rf.st_dev, 2, 0, 0, 8, 0, 0, 0))
            with mock.patch.object(audit.os, "fstat", return_value=fake_hl_read):
                with self.assertRaises(oracle.ModularCertError) as cm_hlr:
                    audit.read_regular_bytes_capped(real_f)
                self.assertEqual(cm_hlr.exception.code, "HARDLINK_FORBIDDEN")

            fake_swapped = os.stat_result((stat.S_IFREG | 0o600, st_rf.st_ino + 999999, st_rf.st_dev, 1, 0, 0, 0, 0, 0, 0))
            with mock.patch.object(audit.os, "fstat", return_value=fake_swapped):
                with self.assertRaises(oracle.ModularCertError) as cm_sw:
                    audit.read_regular_bytes_capped(real_f)
                self.assertEqual(cm_sw.exception.code, "TOCTOU_SWAP")

            with mock.patch.object(audit.os, "read", side_effect=OSError("read fail")):
                with self.assertRaises(oracle.ModularCertError) as cm_rd:
                    audit.read_regular_bytes_capped(real_f)
                self.assertEqual(cm_rd.exception.code, "READ_IO_ERROR")

            # Atomic writer refusal controls & hardlink refusal on read BEFORE os.open
            with self.assertRaises(oracle.ModularCertError) as cm_nb:
                audit.write_bytes_atomic_0600(root / "w.bin", "not-bytes")  # type: ignore[arg-type]
            self.assertEqual(cm_nb.exception.code, "INVALID_BYTES")
            with self.assertRaises(oracle.ModularCertError) as cm_ws:
                audit.write_bytes_atomic_0600(sym_f, b"x")
            self.assertEqual(cm_ws.exception.code, "SYMLINK_FORBIDDEN")
            hl_a = root / "hl_a.bin"
            hl_b = root / "hl_b.bin"
            hl_a.write_bytes(b"a")
            os.link(hl_a, hl_b)
            hl_opened_tmp: list[str] = []

            def _spy_hl_open(path_arg: Any, flags: int, *args: Any, **kwargs: Any) -> int:
                if not (flags & os.O_DIRECTORY):
                    hl_opened_tmp.append(str(path_arg))
                return orig_open(path_arg, flags, *args, **kwargs)

            with mock.patch.object(audit.os, "open", side_effect=_spy_hl_open):
                with self.assertRaises(oracle.ModularCertError) as cm_hlr0:
                    audit.read_regular_bytes_capped(hl_a)
                self.assertEqual(cm_hlr0.exception.code, "HARDLINK_FORBIDDEN")
                with self.assertRaises(oracle.ModularCertError) as cm_hl:
                    audit.write_bytes_atomic_0600(hl_a, b"b")
                self.assertEqual(cm_hl.exception.code, "HARDLINK_FORBIDDEN")
            self.assertEqual(hl_opened_tmp, [], msg=f"opened hardlinked target before lstat gate: {hl_opened_tmp}")

            # chmod 500 read-only dir cleanly raises typed WRITE_IO_ERROR (never raw PermissionError)
            ro_dir = root / "ro_dir"
            ro_dir.mkdir()
            os.chmod(ro_dir, 0o500)
            try:
                with self.assertRaises(oracle.ModularCertError) as cm_ro:
                    audit.write_bytes_atomic_0600(ro_dir / "deny.json", b"x")
                self.assertEqual(cm_ro.exception.code, "WRITE_IO_ERROR")
            finally:
                os.chmod(ro_dir, 0o700)

            with mock.patch.object(audit.os, "write", side_effect=OSError(errno.ENOSPC, "full")):
                with self.assertRaises(oracle.ModularCertError) as cm_wio:
                    audit.write_bytes_atomic_0600(root / "w_io.bin", b"x")
                self.assertEqual(cm_wio.exception.code, "WRITE_IO_ERROR")

            with mock.patch.object(audit.os, "lstat", side_effect=OSError(errno.EACCES, "denied")):
                with self.assertRaises(oracle.ModularCertError) as cm_us:
                    audit.write_bytes_atomic_0600(root / "w2.bin", b"x")
                self.assertEqual(cm_us.exception.code, "TARGET_UNSTATTABLE")

            def _open_eexist(path_arg: Any, flags: int, *args: Any, **kwargs: Any) -> int:
                if flags & os.O_CREAT:
                    raise FileExistsError("exists")
                return orig_open(path_arg, flags, *args, **kwargs)

            with mock.patch.object(audit.os, "open", side_effect=_open_eexist):
                with self.assertRaises(oracle.ModularCertError) as cm_ex:
                    audit.write_bytes_atomic_0600(root / "w3.bin", b"x")
                self.assertEqual(cm_ex.exception.code, "TEMP_CREATE_FAILED")

            with mock.patch.object(audit.os, "write", return_value=0):
                with self.assertRaises(oracle.ModularCertError) as cm_sh:
                    audit.write_bytes_atomic_0600(root / "w4.bin", b"x")
                self.assertEqual(cm_sh.exception.code, "SHORT_WRITE")

            fake_nlink2 = os.stat_result((stat.S_IFREG | 0o600, 1, 1, 2, 0, 0, 1, 0, 0, 0))
            for bad_tmp_st in (fake_nlink2, fake_fifo_st):
                with mock.patch.object(audit.os, "fstat", return_value=bad_tmp_st):
                    with self.assertRaises(oracle.ModularCertError) as cm_tt:
                        audit.write_bytes_atomic_0600(root / "w5.bin", b"x")
                    self.assertEqual(cm_tt.exception.code, "TEMP_TAMPERED")

            # Pre-replace second lstat races (symlink, non-regular, hardlink)
            for fake_st2, exp_c in (
                (os.stat_result((stat.S_IFLNK | 0o777, 1, 1, 1, 0, 0, 0, 0, 0, 0)), "SYMLINK_FORBIDDEN"),
                (fake_fifo_st, "NON_REGULAR_FILE"),
                (fake_nlink2, "HARDLINK_FORBIDDEN"),
            ):
                calls = {"n": 0}

                def _lstat_race(name_arg: Any, *args: Any, **kwargs: Any) -> os.stat_result:
                    calls["n"] += 1
                    if calls["n"] == 1:
                        raise FileNotFoundError()
                    return fake_st2

                with mock.patch.object(audit.os, "lstat", side_effect=_lstat_race):
                    with self.assertRaises(oracle.ModularCertError) as cm_r2:
                        audit.write_bytes_atomic_0600(root / "w_race.bin", b"x")
                    self.assertEqual(cm_r2.exception.code, exp_c)
            del orig_fstat

            # CLI strict parser & all modes
            rc0, out0, _ = _run_cli([])
            self.assertEqual(rc0, 0)
            self.assertIn("OK ", out0)
            rc0j, out0j, _ = _run_cli(["--json"])
            self.assertEqual(rc0j, 0)
            self.assertTrue(json.loads(out0j)["valid"])
            rcs, outs, _ = _run_cli(["--standalone", "--json"])
            self.assertEqual(rcs, 0)
            out_cert = root / "written_cert.json"
            rcw, outw, _ = _run_cli(["--write", str(out_cert)])
            self.assertEqual(rcw, 0)
            self.assertIn("WROTE ", outw)
            self.assertEqual(stat.S_IMODE(os.lstat(out_cert).st_mode), 0o600)
            self.assertEqual(out_cert.read_text(encoding="ascii"), outs)
            rcwj, outwj, _ = _run_cli(["--write", str(out_cert), "--json"])
            self.assertEqual(rcwj, 0)
            self.assertTrue(json.loads(outwj)["written"])
            rcc, outc, _ = _run_cli(["--check", str(out_cert)])
            self.assertEqual(rcc, 0)
            self.assertIn("VALID ", outc)
            rccj, outcj, _ = _run_cli(["--check", str(out_cert), "--json"])
            self.assertEqual(rccj, 0)
            self.assertTrue(json.loads(outcj)["valid"])

            bad_utf = root / "bad_utf.json"
            bad_utf.write_bytes(b"\xff\xfe")
            rcbu, _, errbu = _run_cli(["--check", str(bad_utf)])
            self.assertEqual(rcbu, 2)
            self.assertIn("INVALID_UTF8", errbu)

            pretty_cert = root / "pretty_cert.json"
            pretty_cert.write_text(json.dumps(oracle.build_certificate(), indent=2) + "\n", encoding="ascii")
            rcpr, _, errpr = _run_cli(["--check", str(pretty_cert)])
            self.assertEqual(rcpr, 2)
            self.assertIn("NON_CANONICAL_BYTES", errpr)

            # Run CLI flag-trap tests in isolated temp dir so mutated CLI_INVALID_PATH leaves no stray file
            with tempfile.TemporaryDirectory(prefix="s55_cli_err_") as err_td:
                saved_cwd = os.getcwd()
                saved_pwd = os.environ.get("PWD")
                try:
                    os.chdir(err_td)
                    os.environ["PWD"] = err_td
                    for bad_argv, exp_err_code in (
                        (123, "CLI_INVALID_ARGV"),
                        (["--unknown", "x"], "CLI_UNKNOWN_ARG"),
                        (["--stand"], "CLI_UNKNOWN_ARG"),
                        (["--json", "--json"], "CLI_DUPLICATE"),
                        (["--standalone", "--check", str(out_cert)], "CLI_CONFLICT"),
                        (["--check", str(out_cert), "--standalone"], "CLI_CONFLICT"),
                        (["--write"], "CLI_MISSING_ARG"),
                        (["--write", "--json"], "CLI_INVALID_PATH"),
                        (["--check", "--json"], "CLI_INVALID_PATH"),
                        (["--write", ""], "CLI_INVALID_PATH"),
                    ):
                        rc_b, _, err_b = _run_cli(bad_argv)  # type: ignore[arg-type]
                        self.assertEqual(rc_b, 2, msg=f"expected rc=2 for {bad_argv}")
                        self.assertIn(exp_err_code, err_b, msg=f"expected {exp_err_code} in {err_b!r} for {bad_argv}")
                finally:
                    os.chdir(saved_cwd)
                    if saved_pwd is not None:
                        os.environ["PWD"] = saved_pwd
                    else:
                        os.environ.pop("PWD", None)

    def test_07_concurrency_0600_burst_renameat2_and_hardlink_races(self) -> None:
        with tempfile.TemporaryDirectory(prefix="s55_conc_") as td:
            root = Path(td).resolve()
            payload = oracle.canonical_json_bytes(oracle.build_certificate()) + b"\n"

            # 16T distinct + 16T same-target + 80T barrier burst
            errors: list[Exception] = []

            def _worker_distinct(tid: int) -> None:
                try:
                    for j in range(10):
                        p = root / f"d_{tid}_{j}.json"
                        audit.write_bytes_atomic_0600(p, payload)
                        self.assertEqual(stat.S_IMODE(os.lstat(p).st_mode), 0o600)
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=_worker_distinct, args=(i,)) for i in range(16)]
            for th in threads:
                th.start()
            for th in threads:
                th.join()
            self.assertEqual(errors, [])

            same_p = root / "same_target.json"
            barrier = threading.Barrier(80)

            def _worker_burst() -> None:
                try:
                    barrier.wait(timeout=10)
                    audit.write_bytes_atomic_0600(same_p, payload)
                except Exception as exc:
                    errors.append(exc)

            bthreads = [threading.Thread(target=_worker_burst) for _ in range(80)]
            for th in bthreads:
                th.start()
            for th in bthreads:
                th.join()
            self.assertEqual(errors, [])
            self.assertEqual(same_p.read_bytes(), payload)
            self.assertEqual(stat.S_IMODE(os.lstat(same_p).st_mode), 0o600)

            # Live hardlink race (>= 500 flips)
            hl_tgt = root / "hl_race.json"
            hl_alias = root / "hl_alias.json"
            hl_tgt.write_bytes(payload)
            stop_hl = threading.Event()
            hl_flips = {"n": 0}

            def _hl_flipper() -> None:
                while not stop_hl.is_set() or hl_flips["n"] < 520:
                    try:
                        os.link(hl_tgt, hl_alias)
                        hl_flips["n"] += 1
                    except OSError:
                        pass
                    try:
                        os.unlink(hl_alias)
                    except OSError:
                        pass
                    if stop_hl.is_set() and hl_flips["n"] >= 520:
                        break

            th_hl = threading.Thread(target=_hl_flipper, daemon=True)
            th_hl.start()
            raw_hl_errs: list[Exception] = []
            for _ in range(60):
                try:
                    audit.write_bytes_atomic_0600(hl_tgt, payload)
                except oracle.ModularCertError:
                    pass
                except Exception as exc:
                    raw_hl_errs.append(exc)
            stop_hl.set()
            th_hl.join(timeout=5)
            self.assertEqual(raw_hl_errs, [])
            self.assertGreaterEqual(hl_flips["n"], 500)

            # Live Linux renameat2(RENAME_EXCHANGE) symlink swapper (>= 550 swaps, victim intact, 0 leaks)
            if sys.platform == "linux" and os.uname().machine == "x86_64":
                libc = ctypes.CDLL("libc.so.6", use_errno=True)
                victim = root / "victim_canary.txt"
                victim.write_bytes(b"VICTIM_INTACT")
                slot_a = root / "slot_target.json"
                slot_b = root / "slot_symlink.json"
                slot_a.write_bytes(payload)
                os.symlink(victim, slot_b)
                dfd = os.open(str(root), os.O_RDONLY | os.O_DIRECTORY)
                stop_sw = threading.Event()
                swaps = {"n": 0}
                a_b = b"slot_target.json"
                b_b = b"slot_symlink.json"

                def _swapper() -> None:
                    while not stop_sw.is_set() or swaps["n"] < 560:
                        rc = libc.syscall(
                            ctypes.c_long(_SYS_RENAMEAT2_X86_64),
                            ctypes.c_int(dfd),
                            ctypes.c_char_p(a_b),
                            ctypes.c_int(dfd),
                            ctypes.c_char_p(b_b),
                            ctypes.c_uint(_RENAME_EXCHANGE),
                        )
                        if rc == 0:
                            swaps["n"] += 1
                        else:
                            break
                        if stop_sw.is_set() and swaps["n"] >= 560:
                            break

                th_sw = threading.Thread(target=_swapper, daemon=True)
                th_sw.start()
                raw_sw_errs: list[Exception] = []
                for _ in range(60):
                    try:
                        audit.write_bytes_atomic_0600(slot_a, payload)
                    except oracle.ModularCertError:
                        pass
                    except Exception as exc:
                        raw_sw_errs.append(exc)
                stop_sw.set()
                th_sw.join(timeout=5)
                os.close(dfd)
                self.assertEqual(raw_sw_errs, [])
                self.assertEqual(victim.read_bytes(), b"VICTIM_INTACT")
                self.assertGreaterEqual(swaps["n"], 550)

            # Zero leaked temp files
            leaks = [p.name for p in root.iterdir() if ".tmp." in p.name]
            self.assertEqual(leaks, [])

        # On-disk frozen certificate parity (when present; 0o600 locally, 0o644 under git checkout)
        if _CERT_DISK.is_file():
            raw_disk = audit.read_regular_bytes_capped(_CERT_DISK)
            self.assertEqual(raw_disk, oracle.canonical_json_bytes(oracle.build_certificate()) + b"\n")
            self.assertIn(stat.S_IMODE(os.lstat(_CERT_DISK).st_mode), (0o600, 0o644))


if __name__ == "__main__":
    unittest.main()
