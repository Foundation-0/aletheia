#!/usr/bin/env python3
"""Adversarial Regression, Zone-B, Concurrency/TOCTOU & Mutation-Killing Suite for CS-24 Gate.

Zero bare asserts, zero AST floats, zero float() calls, zero .isdigit(), zero device-path writes,
zero external dependencies, zero mathematical RNG.
"""
from __future__ import annotations

import ast
import copy
import ctypes
from fractions import Fraction
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
from types import SimpleNamespace
from typing import Any
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import cs24_mock_anchor_audit as aud  # noqa: E402
import cs24_mock_anchor_oracle as orc  # noqa: E402


class _EvilPath(type(Path("."))):
    """Path subclass rejected by _require_concrete_path."""


class _EvilInt(int):
    """int subclass rejected by require_exact_int and _validate_json_tree."""


class _EvilStr(str):
    """str subclass rejected by require_str and _validate_json_tree."""


class _EvilFrac(Fraction):
    """Fraction subclass rejected by require_fraction."""


class _EvilDict(dict):
    """dict subclass rejected by _validate_json_tree."""


class _EvilList(list):
    """list subclass rejected by _validate_json_tree."""


def _make_base_claim(**overrides: Any) -> dict[str, Any]:
    sha = "4ba28f3ed9b037f314bd857c41010d8dd280a37286c69508a93f9e5acf70516a"
    rec = orc._make_live_receipt(receipt_sha256=sha)
    claim: dict[str, Any] = {
        "claim_id": "TEST_CLAIM",
        "domain": "hardware_probe",
        "claims_silicon_verification": True,
        "mocked_tests_passed": 10,
        "mocked_tests_total": 10,
        "execution_evidence_mode": "live_silicon_receipt",
        "claimed_power_regime": "ac_p0_110w",
        "receipt": rec,
    }
    claim.update(overrides)
    return claim


class TestStaticHygieneAndOracleGate(unittest.TestCase):
    def test_zero_asserts_floats_isdigit_devnull_and_secret_vars(self) -> None:
        for fname in (
            "cs24_mock_anchor_oracle.py",
            "cs24_mock_anchor_audit.py",
            "test_cs24_mock_anchor_r5.py",
        ):
            src = (_THIS_DIR / fname).read_text(encoding="utf-8")
            self.assertNotIn("\r", src)
            self.assertNotIn("/dev/" + "null", src)
            tree = ast.parse(src)
            self.assertEqual([n.lineno for n in ast.walk(tree) if isinstance(n, ast.Assert)], [])
            self.assertEqual([n.lineno for n in ast.walk(tree) if isinstance(n, ast.Constant) and type(n.value) is float], [])
            self.assertEqual(
                [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "float"],
                [],
            )
            self.assertEqual([n.lineno for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "isdigit"], [])
            if fname.startswith("test_"):
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Name, ast.arg)):
                        nm = node.id if isinstance(node, ast.Name) else node.arg
                        self.assertNotIn("secret", nm.lower())

    def test_oracle_primitives_and_commutator_helpers(self) -> None:
        # require_ok & require_bool
        orc.require_ok(True, "X", "ok")
        with self.assertRaises(orc.CS24MockAnchorError) as cm_c:
            orc.require_ok(1, "X", "bad")
        self.assertEqual(cm_c.exception.code, "INVALID_CONDITION")
        with self.assertRaises(orc.CS24MockAnchorError) as cm_f:
            orc.require_ok(False, "FAIL_CODE", "msg")
        self.assertEqual(cm_f.exception.code, "FAIL_CODE")
        self.assertIs(orc.require_bool(False), False)
        with self.assertRaises(orc.CS24MockAnchorError) as cm_b:
            orc.require_bool(0)
        self.assertEqual(cm_b.exception.code, "INVALID_BOOL")

        # require_exact_int boundaries
        max_i = (1 << orc.MAX_INT_BITS) - 1
        over_i = 1 << orc.MAX_INT_BITS
        self.assertEqual(orc.require_exact_int(max_i), max_i)
        self.assertEqual(orc.require_exact_int(-max_i), -max_i)
        self.assertEqual(orc.require_exact_int(5, lo=5, hi=5), 5)
        for bad_i in (True, _EvilInt(1), "5"):
            with self.assertRaises(orc.CS24MockAnchorError) as cm:
                orc.require_exact_int(bad_i)
            self.assertEqual(cm.exception.code, "INVALID_INT")
        for huge_i in (over_i, -over_i, 10**4300):
            with self.assertRaises(orc.CS24MockAnchorError) as cm:
                orc.require_exact_int(huge_i)
            self.assertEqual(cm.exception.code, "INT_BIT_LIMIT")
        with self.assertRaises(orc.CS24MockAnchorError) as cm_lo:
            orc.require_exact_int(4, lo=5)
        self.assertEqual(cm_lo.exception.code, "INT_OUT_OF_RANGE")
        with self.assertRaises(orc.CS24MockAnchorError) as cm_hi:
            orc.require_exact_int(6, hi=5)
        self.assertEqual(cm_hi.exception.code, "INT_OUT_OF_RANGE")
        with self.assertRaises(orc.CS24MockAnchorError) as cm_blo:
            orc.require_exact_int(5, lo=True)  # type: ignore[arg-type]
        self.assertEqual(cm_blo.exception.code, "INVALID_BOUND")
        with self.assertRaises(orc.CS24MockAnchorError) as cm_bhi:
            orc.require_exact_int(5, hi=True)  # type: ignore[arg-type]
        self.assertEqual(cm_bhi.exception.code, "INVALID_BOUND")

        # require_str & is_valid_hex64
        self.assertEqual(orc.require_str("a" * orc.MAX_STR_LEN, non_empty=True), "a" * orc.MAX_STR_LEN)
        for bad_s, code in (
            (123, "INVALID_STR"),
            (_EvilStr("x"), "INVALID_STR"),
            ("\ud800", "INVALID_UTF8_SURROGATE"),
            ("a\x00b", "NUL_BYTE_FORBIDDEN"),
            ("a" * (orc.MAX_STR_LEN + 1), "STR_TOO_LONG"),
            ("   ", "EMPTY_STR"),
        ):
            with self.assertRaises(orc.CS24MockAnchorError) as cm:
                orc.require_str(bad_s, non_empty=True)
            self.assertEqual(cm.exception.code, code)

        self.assertTrue(orc.is_valid_hex64("0123456789abcdef" * 4))
        self.assertFalse(orc.is_valid_hex64(123))
        self.assertFalse(orc.is_valid_hex64("a" * 63))
        self.assertFalse(orc.is_valid_hex64("A" * 64))
        self.assertFalse(orc.is_valid_hex64("z" * 64))

        # require_fraction, format_rational, format_decimal (-0 suppression & rounding)
        self.assertEqual(orc.require_fraction(Fraction(max_i, 1)), Fraction(max_i, 1))
        self.assertEqual(orc.require_fraction(Fraction(1, max_i)), Fraction(1, max_i))
        for bad_fr in (1, _EvilFrac(1, 2)):
            with self.assertRaises(orc.CS24MockAnchorError) as cm:
                orc.require_fraction(bad_fr)
            self.assertEqual(cm.exception.code, "INVALID_RATIONAL")
        for big_fr in (Fraction(over_i, 1), Fraction(1, over_i)):
            with self.assertRaises(orc.CS24MockAnchorError) as cm:
                orc.require_fraction(big_fr)
            self.assertEqual(cm.exception.code, "RATIONAL_BIT_LIMIT")
        self.assertEqual(orc.format_rational(Fraction(4, 2)), "2")
        self.assertEqual(orc.format_rational(Fraction(3, 2)), "3/2")
        self.assertEqual(orc.format_decimal(Fraction(-1, 10**9), 4), "0.0000")
        self.assertEqual(orc.format_decimal(Fraction(-5, 2), 0), "-3")
        self.assertEqual(orc.format_decimal(Fraction(1, 2), 0), "1")
        self.assertEqual(orc.format_decimal(Fraction(1, 4), 2), "0.25")
        self.assertEqual(orc.format_decimal(Fraction(-3, 8), 2), "-0.38")

        # Commutator & roofline helpers
        c_ok = orc.evaluate_commutator_witness("W", "sub", "m", "s", 1, 2, True)
        self.assertEqual(c_ok["commutator_defect"], -1)
        self.assertTrue(c_ok["non_commuting"])
        c_eq = orc.evaluate_commutator_witness("W", "sub", "m", "s", 2, 2, True)
        self.assertEqual(c_eq["commutator_defect"], 0)
        self.assertFalse(c_eq["non_commuting"])
        with self.assertRaises(orc.CS24MockAnchorError) as cm_tc:
            orc.evaluate_commutator_witness("W", "sub", "m", "s", 3, 2, False)
        self.assertEqual(cm_tc.exception.code, "INVALID_TEST_COUNTS")
        pr = orc.evaluate_power_roofline_divergence(110, 55, 35031, 31880)
        self.assertEqual(pr["power_cap_ratio_q"], "2")
        self.assertEqual(pr["bf16_relative_uplift_pct_dec4"], "9.8839")

    def test_cs24_gate_exhaustive_branch_and_boolop_kills(self) -> None:
        # Claim top-level guards
        with self.assertRaises(orc.CS24MockAnchorError) as cm_ct:
            orc.evaluate_cs24_mock_anchor_gate([])
        self.assertEqual(cm_ct.exception.code, "INVALID_CLAIM_TYPE")
        bad_keys = _make_base_claim()
        bad_keys["extra"] = 1
        with self.assertRaises(orc.CS24MockAnchorError) as cm_ck:
            orc.evaluate_cs24_mock_anchor_gate(bad_keys)
        self.assertEqual(cm_ck.exception.code, "INVALID_CLAIM_KEYS")
        with self.assertRaises(orc.CS24MockAnchorError) as cm_dom:
            orc.evaluate_cs24_mock_anchor_gate(_make_base_claim(domain="bogus"))
        self.assertEqual(cm_dom.exception.code, "INVALID_DOMAIN")
        with self.assertRaises(orc.CS24MockAnchorError) as cm_cnt:
            orc.evaluate_cs24_mock_anchor_gate(_make_base_claim(mocked_tests_passed=11, mocked_tests_total=10))
        self.assertEqual(cm_cnt.exception.code, "INVALID_TEST_COUNTS")
        with self.assertRaises(orc.CS24MockAnchorError) as cm_em:
            orc.evaluate_cs24_mock_anchor_gate(_make_base_claim(execution_evidence_mode="bogus"))
        self.assertEqual(cm_em.exception.code, "INVALID_EVIDENCE_MODE")
        with self.assertRaises(orc.CS24MockAnchorError) as cm_pr:
            orc.evaluate_cs24_mock_anchor_gate(_make_base_claim(claimed_power_regime="bogus"))
        self.assertEqual(cm_pr.exception.code, "INVALID_POWER_REGIME")

        # Not-applicable claim
        na = orc.evaluate_cs24_mock_anchor_gate(_make_base_claim(claims_silicon_verification=False, receipt=None))
        self.assertEqual(na["verdict"], "NOT_APPLICABLE")
        self.assertFalse(na["cs24_triggered"])

        # Valid baseline ALLOW
        ok = orc.evaluate_cs24_mock_anchor_gate(_make_base_claim())
        self.assertEqual(ok["verdict"], "ALLOW")
        self.assertFalse(ok["cs24_triggered"])

        # Both halves of ev_mode != "live_silicon_receipt" or rec is None
        r_m1 = orc.evaluate_cs24_mock_anchor_gate(_make_base_claim(execution_evidence_mode="mocked_only"))
        self.assertEqual(r_m1["reason_codes"], ["CS24_MOCK_ANCHOR_UNVERIFIED"])
        r_m2 = orc.evaluate_cs24_mock_anchor_gate(_make_base_claim(receipt=None))
        self.assertEqual(r_m2["reason_codes"], ["CS24_MOCK_ANCHOR_UNVERIFIED"])

        # Receipt container & keyset errors
        with self.assertRaises(orc.CS24MockAnchorError) as cm_rt:
            orc.evaluate_cs24_mock_anchor_gate(_make_base_claim(receipt=[]))
        self.assertEqual(cm_rt.exception.code, "INVALID_RECEIPT_TYPE")
        bad_rk = _make_base_claim()
        bad_rk["receipt"]["extra"] = 1
        with self.assertRaises(orc.CS24MockAnchorError) as cm_rk:
            orc.evaluate_cs24_mock_anchor_gate(bad_rk)
        self.assertEqual(cm_rk.exception.code, "INVALID_RECEIPT_KEYS")

        # Type & string contamination across int, bit-overflow int, bool, str (incl. NUL/surrogate), anomalies, runtime float
        for key, val in (
            ("exit_code", False),
            ("memory_used_mib", json.loads("2.0")),
            ("memory_used_mib", 1 << orc.MAX_INT_BITS),
            ("clean_hardware_run", 1),
            ("schema", 123),
            ("pci_drm_cuda_witness", "pci\x00bad"),
            ("pci_drm_cuda_witness", "pci\ud800bad"),
            ("anomalies", "not_list"),
            ("anomalies", [123]),
            ("anomalies", ["ok\x00bad"]),
            ("anomalies", ["ok\ud800bad"]),
        ):
            c = _make_base_claim()
            c["receipt"][key] = val
            res = orc.evaluate_cs24_mock_anchor_gate(c)
            self.assertEqual(res["verdict"], "DENY")
            self.assertEqual(res["reason_codes"], ["CS24_RECEIPT_TYPE_CONTAMINATION"])

        # Individual denial subconditions (kills every BoolOp & Compare mutant in evaluate_cs24_mock_anchor_gate!)
        def _expect_reason(rec_patch: dict[str, Any], expected: str, claim_patch: dict[str, Any] | None = None) -> None:
            c = _make_base_claim(**(claim_patch or {}))
            c["receipt"].update(rec_patch)
            res = orc.evaluate_cs24_mock_anchor_gate(c)
            self.assertEqual(res["verdict"], "DENY")
            self.assertIn(expected, res["reason_codes"])

        _expect_reason({"schema": "unknown/v0"}, "CS24_INVALID_RECEIPT_SCHEMA")
        _expect_reason({"subprocess_mocked": True}, "CS24_SUBPROCESS_MOCKED_IN_RECEIPT")
        _expect_reason({"clean_hardware_run": False}, "CS24_UNCLEAN_HARDWARE_RUN")
        _expect_reason({"exit_code": 1}, "CS24_UNCLEAN_HARDWARE_RUN")
        _expect_reason({"anomalies": ["THROTTLE"]}, "CS24_UNCLEAN_HARDWARE_RUN")
        _expect_reason({"determinism_zone": "A"}, "CS24_UNCLEAN_HARDWARE_RUN")

        # SHA pin BoolOp kills (all 4 subconditions independently!)
        _expect_reason({"receipt_sha256": "\u00e9" * 64, "expected_receipt_sha256": "a" * 64}, "CS24_RECEIPT_SHA_UNPINNED")
        _expect_reason({"receipt_sha256": "a" * 64, "expected_receipt_sha256": "\u00e9" * 64}, "CS24_RECEIPT_SHA_UNPINNED")
        _expect_reason({"receipt_sha256": "0" * 64, "expected_receipt_sha256": "0" * 64}, "CS24_RECEIPT_SHA_UNPINNED")
        _expect_reason({"receipt_sha256": "a" * 64, "expected_receipt_sha256": "b" * 64}, "CS24_RECEIPT_SHA_UNPINNED")

        # KMD baseline & host_os BoolOp + boundary kills (0, 4, 5, -1, darwin/windows)
        _expect_reason({"host_os": "freebsd", "linux_kmd_baseline_vram_mib": 0, "memory_used_mib": 0}, "CS24_KMD_BASELINE_SPOOFED")
        _expect_reason({"gpu_processes_queried": False}, "CS24_KMD_BASELINE_SPOOFED")
        _expect_reason({"graphics_processes_count": 1}, "CS24_KMD_BASELINE_SPOOFED")
        _expect_reason({"linux_kmd_baseline_vram_mib": -1, "memory_used_mib": 0}, "CS24_KMD_BASELINE_SPOOFED")
        _expect_reason({"linux_kmd_baseline_vram_mib": 5, "memory_used_mib": 2}, "CS24_KMD_BASELINE_SPOOFED")
        _expect_reason({"linux_kmd_baseline_vram_mib": 2, "memory_used_mib": 3}, "CS24_KMD_BASELINE_SPOOFED")
        _expect_reason({"linux_kmd_baseline_vram_mib": 2, "memory_used_mib": -1}, "CS24_KMD_BASELINE_SPOOFED")
        _expect_reason({"host_os": "darwin", "linux_kmd_baseline_vram_mib": 1, "memory_used_mib": 0}, "CS24_KMD_BASELINE_SPOOFED")
        _expect_reason({"host_os": "darwin", "linux_kmd_baseline_vram_mib": 0, "memory_used_mib": 1}, "CS24_KMD_BASELINE_SPOOFED")

        # Exact legal KMD boundaries (0, 4 on linux; 0, 0 on darwin)
        for rec_ok in (
            {"host_os": "linux", "linux_kmd_baseline_vram_mib": 0, "memory_used_mib": 0},
            {"host_os": "linux", "linux_kmd_baseline_vram_mib": 4, "memory_used_mib": 4},
            {"host_os": "darwin", "linux_kmd_baseline_vram_mib": 0, "memory_used_mib": 0},
        ):
            c_ok = _make_base_claim()
            c_ok["receipt"].update(rec_ok)
            self.assertEqual(orc.evaluate_cs24_mock_anchor_gate(c_ok)["verdict"], "ALLOW")

        # Power regime & missing hardware witness kills
        _expect_reason({"power_regime_measured": "battery_55w"}, "CS24_POWER_REGIME_MISMATCH")
        _expect_reason(
            {"power_regime_measured": "unspecified"},
            "CS24_POWER_REGIME_MISMATCH",
            claim_patch={"claimed_power_regime": "unspecified"},
        )
        _expect_reason({"pci_drm_cuda_witness": "   "}, "CS24_MISSING_HARDWARE_WITNESS")


class TestParsersAuditAndBijectiveTamperKills(unittest.TestCase):
    def test_strict_parsers_and_canonical_json_validation(self) -> None:
        max_b = (1 << aud.MAX_JSON_INT_BITS) - 1
        over_b = 1 << aud.MAX_JSON_INT_BITS
        self.assertEqual(aud._parse_bounded_int("0"), 0)
        self.assertEqual(aud._parse_bounded_int("10"), 10)
        self.assertEqual(aud._parse_bounded_int("-42"), -42)
        self.assertEqual(aud._parse_bounded_int(str(max_b)), max_b)
        for bad_tok, code in (
            ("-0", "INVALID_JSON_INT"),
            ("-", "INVALID_JSON_INT"),
            ("", "INVALID_JSON_INT"),
            ("007", "INVALID_JSON_INT"),
            ("01", "INVALID_JSON_INT"),
            ("+1", "INVALID_JSON_INT"),
            ("1_0", "INVALID_JSON_INT"),
            ("\u0661", "INVALID_JSON_INT"),
            ("9" * (aud.MAX_JSON_INT_DIGITS + 1), "INT_DIGIT_LIMIT"),
            (str(over_b), "INT_BIT_LIMIT"),
        ):
            with self.assertRaises(orc.CS24MockAnchorError) as cm:
                aud._parse_bounded_int(bad_tok)
            self.assertEqual(cm.exception.code, code)

        self.assertEqual(aud.parse_exact_rational("0"), Fraction(0))
        self.assertEqual(aud.parse_exact_rational("1/2"), Fraction(1, 2))
        self.assertEqual(aud.parse_exact_rational("-5/7"), Fraction(-5, 7))
        for bad_r, code in (
            ("1/2/3", "INVALID_RATIONAL"),
            ("3/1", "INVALID_RATIONAL"),
            ("3/0", "INVALID_RATIONAL"),
            ("2/4", "NON_CANONICAL_RATIONAL"),
        ):
            with self.assertRaises(orc.CS24MockAnchorError) as cm:
                aud.parse_exact_rational(bad_r)
            self.assertEqual(cm.exception.code, code)

        good_h = "0123456789abcdef" * 4
        self.assertEqual(aud.require_hex64_lower_ascii(good_h), good_h)
        for bad_h in ("a" * 63, "A" * 64, "z" * 64, "\u00e9" * 64):
            with self.assertRaises(orc.CS24MockAnchorError) as cm:
                aud.require_hex64_lower_ascii(bad_h)
            self.assertEqual(cm.exception.code, "INVALID_HEX64")

        self.assertEqual(aud.parse_strict_json_text("[1,null,true,false]", require_object=False), [1, None, True, False])
        exact_s = '{"k":"' + ("a" * (aud.MAX_JSON_BYTES - 8)) + '"}'
        self.assertEqual(len(aud.parse_strict_json_text(exact_s, require_object=True)["k"]), aud.MAX_JSON_BYTES - 8)
        for bad_txt, code in (
            ("[1]", "JSON_ROOT_NOT_OBJECT"),
            ('{"a":1,"a":2}', "DUPLICATE_JSON_KEY"),
            ('{"a":1,"\\u0061":2}', "DUPLICATE_JSON_KEY"),
            ('{"x":1e2}', "FLOAT_LITERAL_FORBIDDEN"),
            ('{"x":NaN}', "NONFINITE_LITERAL_FORBIDDEN"),
            ('{"x":' + "9" * (aud.MAX_JSON_INT_DIGITS + 1) + "}", "INT_DIGIT_LIMIT"),
            ("{bad", "JSON_PARSE_ERROR"),
            ('{"a":' * (aud.MAX_JSON_DEPTH + 1) + "1" + "}" * (aud.MAX_JSON_DEPTH + 1), "JSON_DEPTH_LIMIT"),
            ('{"k":"' + ("a" * aud.MAX_JSON_BYTES) + '"}', "JSON_TOO_LARGE"),
        ):
            with self.assertRaises(orc.CS24MockAnchorError) as cm:
                aud.parse_strict_json_text(bad_txt, require_object=True)
            self.assertEqual(cm.exception.code, code)

        cyc: dict[str, Any] = {}
        cyc["self"] = cyc
        deep_ok: Any = 1
        for _ in range(aud.MAX_JSON_DEPTH):
            deep_ok = [deep_ok]
        self.assertTrue(aud.canonical_json_bytes(deep_ok).startswith(b"["))
        self.assertTrue(aud.canonical_json_bytes({"v": [None, True, False, max_b, -max_b]}).startswith(b"{"))
        for bad_obj, code in (
            ({"x": over_b}, "INT_BIT_LIMIT"),
            ({"x": -over_b}, "INT_BIT_LIMIT"),
            ({"x": 10**4300}, "INT_BIT_LIMIT"),
            (cyc, "JSON_DEPTH_LIMIT"),
            ([deep_ok], "JSON_DEPTH_LIMIT"),
            ({"x": (1, 2)}, "FORBIDDEN_JSON_TYPE"),
            ({"x": "\ud800"}, "INVALID_UTF8_SURROGATE"),
            ({1: "a"}, "INVALID_STR"),
        ):
            with self.assertRaises(orc.CS24MockAnchorError) as cm:
                aud.canonical_json_bytes(bad_obj)
            self.assertEqual(cm.exception.code, code)

    def test_certificate_verification_and_exhaustive_bijective_tamper_kills(self) -> None:
        cert = aud.build_standalone_certificate()
        self.assertTrue(cert["payload"]["summary"]["all_four_pillars_verified"])
        self.assertTrue(aud.verify_certificate_dict(cert, full_replay=True)["valid"])
        self.assertTrue(aud.verify_certificate_dict(cert, full_replay=False)["valid"])

        for bad_c, code in (
            ([], "INVALID_CERT_TYPE"),
            (dict(cert, extra=1), "INVALID_CERT_KEYS"),
            (dict(cert, schema_version="bad"), "INVALID_SCHEMA"),
            (dict(cert, track_id="bad"), "INVALID_TRACK_ID"),
            (dict(cert, payload=[1]), "INVALID_PAYLOAD_TYPE"),
        ):
            with self.assertRaises(orc.CS24MockAnchorError) as cm:
                aud.verify_certificate_dict(bad_c, full_replay=True)
            self.assertEqual(cm.exception.code, code)

        flip_p = ("0" if cert["payload_sha256"][0] != "0" else "1") + cert["payload_sha256"][1:]
        with self.assertRaises(orc.CS24MockAnchorError) as cm_ps:
            aud.verify_certificate_dict(dict(cert, payload_sha256=flip_p))
        self.assertEqual(cm_ps.exception.code, "PAYLOAD_SHA256_MISMATCH")

        flip_c = ("0" if cert["certificate_sha256"][0] != "0" else "1") + cert["certificate_sha256"][1:]
        with self.assertRaises(orc.CS24MockAnchorError) as cm_cs:
            aud.verify_certificate_dict(dict(cert, certificate_sha256=flip_c))
        self.assertEqual(cm_cs.exception.code, "CERT_SHA256_MISMATCH")

        with mock.patch.object(aud, "build_standalone_certificate", return_value=dict(cert, payload_sha256=flip_p)):
            with self.assertRaises(orc.CS24MockAnchorError) as cm_rep:
                aud.verify_certificate_dict(cert, full_replay=True)
            self.assertEqual(cm_rep.exception.code, "REPLAY_MISMATCH")

        # Direct secondary_audit_payload type, float, subclass, and bool-as-int kills
        with self.assertRaises(orc.CS24MockAnchorError) as cm_nd:
            aud.secondary_audit_payload("not_dict")
        self.assertEqual(cm_nd.exception.code, "INVALID_PAYLOAD")
        for bad_val, expected_code in (
            (json.loads("1.5"), "FORBIDDEN_JSON_TYPE"),
            (_EvilStr("exact"), "FORBIDDEN_JSON_TYPE"),
            (_EvilInt(1), "FORBIDDEN_JSON_TYPE"),
            (_EvilDict({"x": 1}), "FORBIDDEN_JSON_TYPE"),
            (_EvilList([1]), "FORBIDDEN_JSON_TYPE"),
            ("\ud800", "INVALID_UTF8_SURROGATE"),
            (10**4300, "INT_BIT_LIMIT"),
        ):
            p_bad = copy.deepcopy(cert["payload"])
            p_bad["oracle_class"] = bad_val
            with self.assertRaises(orc.CS24MockAnchorError) as cm_sb:
                aud.secondary_audit_payload(p_bad)
            self.assertEqual(cm_sb.exception.code, expected_code)

        # bool-vs-int mismatch (1 == True in Python -> kills exact type check in _verify_exact_payload_tree!)
        p_bi = copy.deepcopy(cert["payload"])
        p_bi["summary"]["all_four_pillars_verified"] = 1
        with self.assertRaises(orc.CS24MockAnchorError) as cm_bi:
            aud.secondary_audit_payload(p_bi)
        self.assertEqual(cm_bi.exception.code, "INVALID_SCHEMA_TYPE")

        # Kill independent algebraic checks in secondary_audit_payload by patching _EXPECTED_PAYLOAD
        def _kill_alg(mutator: Any, code: str) -> None:
            mut = copy.deepcopy(cert["payload"])
            mutator(mut)
            with mock.patch.object(aud, "_EXPECTED_PAYLOAD", mut):
                with self.assertRaises(orc.CS24MockAnchorError) as cm_a:
                    aud.secondary_audit_payload(mut)
                self.assertEqual(cm_a.exception.code, code)

        _kill_alg(lambda p: p["pillar1_commutator_obstruction"]["witnesses"][0].__setitem__("commutator_defect", 0), "AUDIT_P1_COMM")
        _kill_alg(lambda p: p["pillar1_commutator_obstruction"]["power_roofline_commutator"].__setitem__("power_cap_ratio_q", "3"), "AUDIT_P1_POWER")
        _kill_alg(lambda p: p["pillar1_commutator_obstruction"]["power_roofline_commutator"].__setitem__("bf16_relative_uplift_q", "1/2"), "AUDIT_P1_UPLIFT")
        _kill_alg(lambda p: p["pillar4_contingency_and_bounds"].__setitem__("total_evaluated", 11), "AUDIT_P4_TOTAL")
        _kill_alg(lambda p: p["pillar4_contingency_and_bounds"].__setitem__("sensitivity_q", "1/2"), "AUDIT_P4_SENS")
        _kill_alg(lambda p: p["pillar4_contingency_and_bounds"].__setitem__("specificity_q", "1/2"), "AUDIT_P4_SPEC")

        # Exhaustive walk: all 24 dicts extra-key, all 18 lists length, all 146 leaves, all container->scalar
        paths_d: list[tuple[Any, ...]] = []
        paths_l: list[tuple[Any, ...]] = []
        paths_f: list[tuple[Any, ...]] = []

        def _walk(node: Any, path: tuple[Any, ...]) -> None:
            if type(node) is dict:
                paths_d.append(path)
                for k, v in node.items():
                    _walk(v, path + (k,))
            elif type(node) is list:
                paths_l.append(path)
                for idx, v in enumerate(node):
                    _walk(v, path + (idx,))
            else:
                paths_f.append(path)

        _walk(cert["payload"], ())
        self.assertEqual(len(paths_d), 24)
        self.assertEqual(len(paths_l), 18)
        self.assertEqual(len(paths_f), 146)

        def _parent(root_obj: Any, path: tuple[Any, ...]) -> Any:
            cur = root_obj
            for seg in path[:-1]:
                cur = cur[seg]
            return cur

        for dp in paths_d:
            m1 = copy.deepcopy(cert["payload"])
            tgt = m1 if not dp else _parent(m1, dp)[dp[-1]]
            tgt["__forged__"] = 1
            with self.assertRaises(orc.CS24MockAnchorError) as cm_k:
                aud.secondary_audit_payload(m1)
            self.assertEqual(cm_k.exception.code, "INVALID_SCHEMA_KEYS")
            if dp:
                m2 = copy.deepcopy(cert["payload"])
                _parent(m2, dp)[dp[-1]] = 0
                with self.assertRaises(orc.CS24MockAnchorError):
                    aud.secondary_audit_payload(m2)

        for lp in paths_l:
            m1 = copy.deepcopy(cert["payload"])
            tgt = _parent(m1, lp)[lp[-1]]
            tgt.append("extra_item")
            with self.assertRaises(orc.CS24MockAnchorError) as cm_l:
                aud.secondary_audit_payload(m1)
            self.assertEqual(cm_l.exception.code, "INVALID_SCHEMA_LIST")
            m2 = copy.deepcopy(cert["payload"])
            _parent(m2, lp)[lp[-1]] = 0
            with self.assertRaises(orc.CS24MockAnchorError):
                aud.secondary_audit_payload(m2)

        for fp in paths_f:
            m1 = copy.deepcopy(cert["payload"])
            par = _parent(m1, fp)
            val = par[fp[-1]]
            if type(val) is bool:
                par[fp[-1]] = not val
            elif type(val) is int:
                par[fp[-1]] = val + 1
            else:
                par[fp[-1]] = val + "_X"
            with self.assertRaises(orc.CS24MockAnchorError) as cm_v:
                aud.secondary_audit_payload(m1)
            self.assertEqual(cm_v.exception.code, "SCHEMA_VALUE_MISMATCH")


class TestZoneBIOConcurrencyDarwinAndCLI(unittest.TestCase):
    def test_zone_b_io_paths_symlinks_fifo_hardlinks_pwd_and_deleted_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            nested = root / "sub1" / "sub2" / "cert.json"

            w_res = aud.write_certificate_file(nested)
            self.assertTrue(w_res["written"])
            self.assertEqual(stat.S_IMODE(os.lstat(nested).st_mode), 0o600)
            c_res = aud.check_certificate_file(nested)
            self.assertTrue(c_res["valid"])
            self.assertEqual(w_res["file_sha256"], c_res["file_sha256"])

            with self.assertRaises(orc.CS24MockAnchorError) as cm_ep:
                aud.read_regular_bytes_capped(_EvilPath(str(nested)))
            self.assertEqual(cm_ep.exception.code, "INVALID_PATH_TYPE")
            with self.assertRaises(orc.CS24MockAnchorError) as cm_nul:
                aud.read_regular_bytes_capped(Path("a\x00b"))
            self.assertEqual(cm_nul.exception.code, "NUL_BYTE_FORBIDDEN")
            with self.assertRaises(orc.CS24MockAnchorError) as cm_sur:
                aud.read_regular_bytes_capped(Path("bad\ud800.json"))
            self.assertEqual(cm_sur.exception.code, "INVALID_UTF8_SURROGATE")
            with self.assertRaises(orc.CS24MockAnchorError) as cm_cap:
                aud.read_regular_bytes_capped(nested, "c", max_bytes=1 << 100)
            self.assertEqual(cm_cap.exception.code, "INT_OUT_OF_RANGE")

            for bad_dir in (Path("/"), Path("..")):
                with self.assertRaises(orc.CS24MockAnchorError) as cm_od:
                    aud._open_dir_chain(bad_dir, "d", create_parents=False)
                self.assertEqual(cm_od.exception.code, "NOT_A_REGULAR_FILE")
            for bad_dir in (Path("/"), Path("."), Path("..")):
                with self.assertRaises(orc.CS24MockAnchorError) as cm_d:
                    aud.read_regular_bytes_capped(bad_dir)
                self.assertEqual(cm_d.exception.code, "NOT_A_REGULAR_FILE")

            missing_parent = root / "missing_dir"
            with self.assertRaises(orc.CS24MockAnchorError) as cm_mp:
                aud.read_regular_bytes_capped(missing_parent / "x.json")
            self.assertEqual(cm_mp.exception.code, "FILE_READ_ERROR")
            self.assertFalse(missing_parent.exists())

            sym_leaf = root / "sym_leaf.json"
            sym_leaf.symlink_to(nested)
            with self.assertRaises(orc.CS24MockAnchorError) as cm_slr:
                aud.read_regular_bytes_capped(sym_leaf)
            self.assertEqual(cm_slr.exception.code, "SYMLINK_FORBIDDEN")
            with self.assertRaises(orc.CS24MockAnchorError) as cm_slw:
                aud.write_regular_bytes_safe(sym_leaf, b"x")
            self.assertEqual(cm_slw.exception.code, "SYMLINK_FORBIDDEN")

            sym_dir = root / "sym_dir"
            sym_dir.symlink_to(nested.parent)
            with self.assertRaises(orc.CS24MockAnchorError) as cm_sd:
                aud.read_regular_bytes_capped(Path(f"{sym_dir}/../sub2/cert.json"))
            self.assertEqual(cm_sd.exception.code, "SYMLINK_FORBIDDEN")
            with self.assertRaises(orc.CS24MockAnchorError) as cm_sdw:
                aud.write_regular_bytes_safe(sym_dir / "x.json", b"a")
            self.assertEqual(cm_sdw.exception.code, "SYMLINK_FORBIDDEN")

            # Scratch FIFO (zero device-path writes!)
            fifo = root / "p.fifo"
            os.mkfifo(fifo)
            with self.assertRaises(orc.CS24MockAnchorError) as cm_fr:
                aud.read_regular_bytes_capped(fifo)
            self.assertEqual(cm_fr.exception.code, "NOT_A_REGULAR_FILE")
            with self.assertRaises(orc.CS24MockAnchorError) as cm_fw:
                aud.write_regular_bytes_safe(fifo, b"x")
            self.assertEqual(cm_fw.exception.code, "NOT_A_REGULAR_FILE")

            hl_a = root / "hl_a.json"
            hl_a.write_bytes(b"KEEP_ME\n")
            hl_b = root / "hl_b.json"
            os.link(hl_a, hl_b)
            with self.assertRaises(orc.CS24MockAnchorError) as cm_hl:
                aud.write_regular_bytes_safe(hl_b, b"CLOBBER\n")
            self.assertEqual(cm_hl.exception.code, "HARDLINK_FORBIDDEN")
            self.assertEqual(hl_a.read_bytes(), b"KEEP_ME\n")

            with self.assertRaises(orc.CS24MockAnchorError) as cm_nb:
                aud.write_regular_bytes_safe(root / "nb.json", "not_bytes")  # type: ignore[arg-type]
            self.assertEqual(cm_nb.exception.code, "INVALID_PAYLOAD_BYTES")

            fake_st = mock.Mock(st_nlink=2)
            with mock.patch("os.fstat", return_value=fake_st):
                with self.assertRaises(orc.CS24MockAnchorError) as cm_th:
                    aud.write_regular_bytes_safe(root / "tmp_hl.json", b"abc")
                self.assertEqual(cm_th.exception.code, "HARDLINK_FORBIDDEN")
            self.assertFalse((root / "tmp_hl.json").exists())

            exact_f = root / "exact.bin"
            exact_f.write_bytes(b"x" * 70000)
            self.assertEqual(len(aud.read_regular_bytes_capped(exact_f, "ex", max_bytes=70000)), 70000)
            with self.assertRaises(orc.CS24MockAnchorError) as cm_big:
                aud.read_regular_bytes_capped(exact_f, "ex", max_bytes=69999)
            self.assertEqual(cm_big.exception.code, "FILE_TOO_LARGE")

            orig_cwd = os.getcwd()
            try:
                os.chdir(nested.parent)
                with mock.patch.dict(os.environ, {"PWD": str(nested.parent)}, clear=False):
                    self.assertEqual(aud.read_regular_bytes_capped(Path("./cert.json")), nested.read_bytes())
                with mock.patch.dict(os.environ, {"PWD": ""}, clear=False):
                    self.assertEqual(aud.read_regular_bytes_capped(Path("cert.json")), nested.read_bytes())
                with mock.patch.dict(os.environ, {"PWD": str(sym_dir)}, clear=False):
                    with self.assertRaises(orc.CS24MockAnchorError) as cm_pwd:
                        aud.read_regular_bytes_capped(Path("cert.json"))
                    self.assertEqual(cm_pwd.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")
                # Stale/unrelated/unstatable PWD does not reject legitimate relative reads
                for stale_pwd in (str(root / "no_such_pwd"), str(root)):
                    with mock.patch.dict(os.environ, {"PWD": stale_pwd}, clear=False):
                        self.assertEqual(aud.read_regular_bytes_capped(Path("cert.json")), nested.read_bytes())
                with mock.patch.object(aud.os, "environ", {"PWD": "/tmp\x00stale"}):
                    self.assertEqual(aud.read_regular_bytes_capped(Path("cert.json")), nested.read_bytes())
                # Real EACCES/EIO during matching-inode PWD walk still fails closed as CWD_UNAVAILABLE
                real_open = os.open
                def _deny_leaf_dir(path_arg: Any, flags: int, *a: Any, **kw: Any) -> int:
                    if path_arg == nested.parent.name and "dir_fd" in kw:
                        raise OSError(aud.errno.EACCES, "denied")
                    return real_open(path_arg, flags, *a, **kw)
                with (
                    mock.patch.dict(os.environ, {"PWD": str(nested.parent)}, clear=False),
                    mock.patch.object(aud.os, "open", side_effect=_deny_leaf_dir),
                ):
                    with self.assertRaises(orc.CS24MockAnchorError) as cm_gp:
                        aud.read_regular_bytes_capped(Path("cert.json"))
                    self.assertEqual(cm_gp.exception.code, "CWD_UNAVAILABLE")

                def _deny_root_open(path_arg: Any, flags: int, *a: Any, **kw: Any) -> int:
                    if path_arg == "/":
                        raise OSError(aud.errno.EACCES, "root")
                    return real_open(path_arg, flags, *a, **kw)
                with (
                    mock.patch.dict(os.environ, {"PWD": str(nested.parent)}, clear=False),
                    mock.patch.object(aud.os, "open", side_effect=_deny_root_open),
                ):
                    with self.assertRaises(orc.CS24MockAnchorError) as cm_pr:
                        aud.read_regular_bytes_capped(Path("cert.json"))
                    self.assertEqual(cm_pr.exception.code, "CWD_UNAVAILABLE")
                with mock.patch.object(aud.os, "open", side_effect=_deny_root_open):
                    with self.assertRaises(orc.CS24MockAnchorError) as cm_ar:
                        aud.read_regular_bytes_capped(nested)
                    self.assertEqual(cm_ar.exception.code, "FILE_READ_ERROR")

                # Explicit OSError fault-injection coverage across mkdir/reopen/read/lstat/tmp/write/replace
                with mock.patch.object(aud.os, "mkdir", side_effect=OSError(aud.errno.ENOSPC, "nospc")):
                    with self.assertRaises(orc.CS24MockAnchorError) as cm_mk:
                        aud.write_regular_bytes_safe(root / "mk_fail_dir" / "x.json", b"a")
                    self.assertEqual(cm_mk.exception.code, "FILE_WRITE_ERROR")
                    self.assertIn("mkdir failed", cm_mk.exception.message)
                reopen_calls = {"n": 0}
                def _fail_reopen_dir(path_arg: Any, flags: int, *a: Any, **kw: Any) -> int:
                    if path_arg == "reopen_fail_dir" and "dir_fd" in kw:
                        reopen_calls["n"] += 1
                        if reopen_calls["n"] == 1:
                            raise FileNotFoundError(aud.errno.ENOENT, "missing")
                        raise OSError(aud.errno.EACCES, "reopen")
                    return real_open(path_arg, flags, *a, **kw)
                with mock.patch.object(aud.os, "open", side_effect=_fail_reopen_dir):
                    with self.assertRaises(orc.CS24MockAnchorError) as cm_ro:
                        aud.write_regular_bytes_safe(root / "reopen_fail_dir" / "x.json", b"a")
                    self.assertEqual(cm_ro.exception.code, "FILE_WRITE_ERROR")
                with mock.patch.object(aud.os, "read", side_effect=OSError(aud.errno.EIO, "read")):
                    with self.assertRaises(orc.CS24MockAnchorError) as cm_rd:
                        aud.read_regular_bytes_capped(nested)
                    self.assertEqual(cm_rd.exception.code, "FILE_READ_ERROR")
                with mock.patch.object(aud.os, "lstat", side_effect=OSError(aud.errno.EACCES, "lstat")):
                    with self.assertRaises(orc.CS24MockAnchorError) as cm_ls:
                        aud.write_regular_bytes_safe(root / "lstat_fail.json", b"a")
                    self.assertEqual(cm_ls.exception.code, "FILE_WRITE_ERROR")
                def _fail_tmp_open(path_arg: Any, flags: int, *a: Any, **kw: Any) -> int:
                    if type(path_arg) is str and path_arg.startswith(".s56."):
                        raise OSError(aud.errno.ENOSPC, "nospc")
                    return real_open(path_arg, flags, *a, **kw)
                with mock.patch.object(aud.os, "open", side_effect=_fail_tmp_open):
                    with self.assertRaises(orc.CS24MockAnchorError) as cm_to:
                        aud.write_regular_bytes_safe(root / "tmp_fail.json", b"a")
                    self.assertEqual(cm_to.exception.code, "FILE_WRITE_ERROR")
                    self.assertIn("create temp failed", cm_to.exception.message)
                with mock.patch.object(aud.os, "write", side_effect=OSError(aud.errno.EIO, "write")):
                    with self.assertRaises(orc.CS24MockAnchorError) as cm_wr:
                        aud.write_regular_bytes_safe(root / "wr_fail.json", b"a")
                    self.assertEqual(cm_wr.exception.code, "FILE_WRITE_ERROR")
                with mock.patch.object(aud.os, "replace", side_effect=OSError(aud.errno.EXDEV, "replace")):
                    with self.assertRaises(orc.CS24MockAnchorError) as cm_rp:
                        aud.write_regular_bytes_safe(root / "rep_fail.json", b"a")
                    self.assertEqual(cm_rp.exception.code, "FILE_WRITE_ERROR")

                doomed = root / "doomed_cwd"
                doomed.mkdir()
                os.chdir(doomed)
                doomed.rmdir()
                for cli_args in (["--check", "rel.json", "--json"], ["--write", "rel.json", "--json"]):
                    eb = io.StringIO()
                    with redirect_stderr(eb):
                        rc = aud.main(cli_args)
                    self.assertEqual(rc, 2)
                    self.assertEqual(json.loads(eb.getvalue())["error_code"], "CWD_UNAVAILABLE")
            finally:
                os.chdir(orig_cwd)

            if os.geteuid() != 0:
                locked_dir = root / "locked_dir"
                locked_dir.mkdir()
                locked_dir.chmod(0)
                try:
                    with self.assertRaises(orc.CS24MockAnchorError) as cm_ld:
                        aud.write_regular_bytes_safe(locked_dir / "x.json", b"a")
                    self.assertEqual(cm_ld.exception.code, "FILE_WRITE_ERROR")
                finally:
                    locked_dir.chmod(0o755)

            raw_v = nested.read_bytes()
            for fname, blob, code in (
                ("crlf.json", raw_v[:-1] + b"\r\n", "CRLF_FORBIDDEN"),
                ("nolf.json", raw_v[:-1], "MISSING_TRAILING_LF"),
                ("badu.json", b"\xff\xfe\n", "INVALID_UTF8"),
                ("nonc.json", b" " + raw_v, "NON_CANONICAL_BYTES"),
            ):
                p = root / fname
                p.write_bytes(blob)
                with self.assertRaises(orc.CS24MockAnchorError) as cm_fmt:
                    aud.check_certificate_file(p)
                self.assertEqual(cm_fmt.exception.code, code)

    def test_darwin_system_root_alias_normalization(self) -> None:
        root_lnk = SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_uid=0)
        root_dir = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
        user_lnk = SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_uid=1000)

        def _fake_readlink(p: str) -> str:
            return {"/var": "private/var", "/tmp": "/private/tmp", "/etc": "private/etc"}[p]

        with (
            mock.patch.object(aud.sys, "platform", "darwin"),
            mock.patch.object(aud.os, "lstat", return_value=root_lnk),
            mock.patch.object(aud.os, "readlink", side_effect=_fake_readlink),
        ):
            self.assertEqual(
                aud._normalize_darwin_system_prefix(Path("/var/folders/xx/cert.json")),
                Path("/private/var/folders/xx/cert.json"),
            )
            self.assertEqual(
                aud._normalize_darwin_system_prefix(Path("/tmp/cert.json")),
                Path("/private/tmp/cert.json"),
            )
            self.assertEqual(
                aud._normalize_darwin_system_prefix(Path("/etc/hosts")),
                Path("/private/etc/hosts"),
            )
            self.assertEqual(aud._normalize_darwin_system_prefix(Path("/tmp")), Path("/tmp"))
            self.assertEqual(
                aud._normalize_darwin_system_prefix(Path("/tmp"), allow_exact=True),
                Path("/private/tmp"),
            )
            self.assertEqual(aud._normalize_darwin_system_prefix(Path("a/tmp/cert.json")), Path("a/tmp/cert.json"))
            self.assertEqual(aud._normalize_darwin_system_prefix(Path("/tmp/../etc/passwd")), Path("/tmp/../etc/passwd"))
            self.assertEqual(aud._normalize_darwin_system_prefix(Path("/usr/local/bin")), Path("/usr/local/bin"))

        with (
            mock.patch.object(aud.sys, "platform", "linux"),
            mock.patch.object(aud.os, "lstat", return_value=root_lnk),
            mock.patch.object(aud.os, "readlink", side_effect=_fake_readlink),
        ):
            self.assertEqual(aud._normalize_darwin_system_prefix(Path("/tmp/cert.json")), Path("/tmp/cert.json"))

        for st_obj, rl_val in (
            (root_dir, "/private/tmp"),
            (user_lnk, "/private/tmp"),
            (root_lnk, "private/evil"),
        ):
            with (
                mock.patch.object(aud.sys, "platform", "darwin"),
                mock.patch.object(aud.os, "lstat", return_value=st_obj),
                mock.patch.object(aud.os, "readlink", return_value=rl_val),
            ):
                self.assertEqual(aud._normalize_darwin_system_prefix(Path("/tmp/cert.json")), Path("/tmp/cert.json"))

        with (
            mock.patch.object(aud.sys, "platform", "darwin"),
            mock.patch.object(aud.os, "lstat", side_effect=OSError("enoent")),
        ):
            self.assertEqual(aud._normalize_darwin_system_prefix(Path("/tmp/cert.json")), Path("/tmp/cert.json"))

    def test_concurrency_16t_80t_renameat2_and_hardlink_races(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            payload = b'{"ok":true}\n'

            errs_d: list[Exception] = []
            def _w_dist(idx: int) -> None:
                try:
                    p = root / f"d_{idx}.json"
                    aud.write_regular_bytes_safe(p, payload)
                    if aud.read_regular_bytes_capped(p) != payload:
                        errs_d.append(RuntimeError("mismatch"))
                except Exception as exc:  # pragma: no cover
                    errs_d.append(exc)
            ts = [threading.Thread(target=_w_dist, args=(i,)) for i in range(16)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            self.assertEqual(errs_d, [])

            same_p = root / "same.json"
            errs_s: list[Exception] = []
            def _w_same(idx: int) -> None:
                try:
                    aud.write_regular_bytes_safe(same_p, f'{{"id":{idx}}}\n'.encode("ascii"))
                except Exception as exc:  # pragma: no cover
                    errs_s.append(exc)
            ts = [threading.Thread(target=_w_same, args=(i,)) for i in range(16)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            self.assertEqual(errs_s, [])
            self.assertIn(b'"id":', same_p.read_bytes())

            errs_b: list[Exception] = []
            def _w_burst(idx: int) -> None:
                try:
                    aud.write_regular_bytes_safe(root / f"b_{idx % 8}.json", payload)
                except Exception as exc:  # pragma: no cover
                    errs_b.append(exc)
            ts = [threading.Thread(target=_w_burst, args=(i,)) for i in range(80)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            self.assertEqual(errs_b, [])
            self.assertEqual([p.name for p in root.iterdir() if p.name.endswith(".tmp")], [])

            # Live renameat2(RENAME_EXCHANGE) >= 550 iterations (Linux only)
            if sys.platform == "linux":
                try:
                    libc = ctypes.CDLL("libc.so.6", use_errno=True)
                except OSError:
                    libc = None
                if libc is not None and hasattr(libc, "syscall"):
                    outside = root / "outside"
                    outside.mkdir()
                    canary = outside / "target.json"
                    canary.write_bytes(b"CANARY_OUTSIDE\n")
                    slot = root / "slot"
                    slot.mkdir()
                    (slot / "target.json").write_bytes(b"LEGIT_INSIDE\n")
                    sym = root / "sym_swap"
                    sym.symlink_to(outside)
                    stop = threading.Event()
                    b1 = os.fsencode(slot)
                    b2 = os.fsencode(sym)
                    def _swapper() -> None:
                        while not stop.is_set():
                            libc.syscall(316, -100, b1, -100, b2, 2)
                    sw = threading.Thread(target=_swapper, daemon=True)
                    sw.start()
                    leaks = 0
                    clobbers = 0
                    try:
                        for _ in range(550):
                            try:
                                if aud.read_regular_bytes_capped(slot / "target.json") != b"LEGIT_INSIDE\n":
                                    leaks += 1
                            except orc.CS24MockAnchorError:
                                pass
                            try:
                                aud.write_regular_bytes_safe(slot / "target.json", b"LEGIT_INSIDE\n")
                            except orc.CS24MockAnchorError:
                                pass
                            if canary.read_bytes() != b"CANARY_OUTSIDE\n":
                                clobbers += 1
                    finally:
                        stop.set()
                        sw.join(timeout=2)
                    self.assertEqual(leaks, 0)
                    self.assertEqual(clobbers, 0)

            # Live hardlink race (>= 500 iterations)
            hl_dir = root / "hl_race"
            hl_dir.mkdir()
            hl_tgt = hl_dir / "target.json"
            hl_alias = hl_dir / "alias.json"
            hl_tgt.write_bytes(b"INIT\n")
            stop_hl = threading.Event()
            hl_clobbers = 0
            def _hl_racer() -> None:
                while not stop_hl.is_set():
                    try:
                        os.link(hl_tgt, hl_alias)
                    except OSError:
                        pass
                    try:
                        os.unlink(hl_alias)
                    except OSError:
                        pass
            hl_t = threading.Thread(target=_hl_racer, daemon=True)
            hl_t.start()
            try:
                for _ in range(500):
                    try:
                        aud.write_regular_bytes_safe(hl_tgt, b"NEXT\n")
                    except orc.CS24MockAnchorError:
                        pass
                    try:
                        if hl_alias.exists() and hl_alias.read_bytes() not in (b"INIT\n", b"NEXT\n"):
                            hl_clobbers += 1
                    except OSError:
                        pass
            finally:
                stop_hl.set()
                hl_t.join(timeout=2)
            self.assertEqual(hl_clobbers, 0)
            self.assertEqual([p.name for p in hl_dir.iterdir() if p.name.endswith(".tmp")], [])

    def test_cli_modes_space_and_equals_syntax_and_adversarial_argv(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            p1 = root / "c1.json"
            p2 = root / "c2.json"

            out_t = io.StringIO()
            with redirect_stdout(out_t):
                self.assertEqual(aud.main([]), 0)
            self.assertIn("OK ", out_t.getvalue())

            out_j = io.StringIO()
            with redirect_stdout(out_j):
                self.assertEqual(aud.main(["--standalone", "--json"]), 0)
            standalone_b = out_j.getvalue().encode("ascii")

            out_w1 = io.StringIO()
            with redirect_stdout(out_w1):
                self.assertEqual(aud.main(["--write", str(p1), "--json"]), 0)
            self.assertEqual(p1.read_bytes(), standalone_b)

            out_c1 = io.StringIO()
            with redirect_stdout(out_c1):
                self.assertEqual(aud.main(["--check", str(p1), "--json"]), 0)
            self.assertTrue(json.loads(out_c1.getvalue())["valid"])

            out_w2 = io.StringIO()
            with redirect_stdout(out_w2):
                self.assertEqual(aud.main([f"--write={p2}", "--json"]), 0)
            self.assertEqual(p2.read_bytes(), standalone_b)

            out_c2 = io.StringIO()
            with redirect_stdout(out_c2):
                self.assertEqual(aud.main([f"--check={p2}", "--json"]), 0)
            self.assertTrue(json.loads(out_c2.getvalue())["valid"])

            bad_cases: list[tuple[Any, str]] = [
                ("bad", "INVALID_ARGV"),
                ([123], "INVALID_STR"),
                ([_EvilStr("--standalone")], "INVALID_STR"),
                (["\ud800"], "INVALID_UTF8_SURROGATE"),
                (["--json", "--json"], "DUPLICATE_FLAG"),
                (["--standalone", "--standalone"], "CONFLICTING_MODE"),
                (["--standalone", "--check", str(p1)], "CONFLICTING_MODE"),
                (["--standalone", f"--check={p1}"], "CONFLICTING_MODE"),
                (["--check"], "MISSING_PATH_ARG"),
                (["--write"], "MISSING_PATH_ARG"),
                (["--check", ""], "INVALID_PATH_ARG"),
                (["--check", "--json"], "INVALID_PATH_ARG"),
                (["--write", "--json"], "INVALID_PATH_ARG"),
                (["--check=--json"], "INVALID_PATH_ARG"),
                (["--write=--json"], "INVALID_PATH_ARG"),
                (["--write="], "INVALID_PATH_ARG"),
                (["--bogus"], "UNKNOWN_FLAG"),
            ]
            for bad_argv, code in bad_cases:
                eb = io.StringIO()
                with redirect_stderr(eb):
                    rc = aud.main(bad_argv)
                self.assertEqual(rc, 2)
                self.assertEqual(json.loads(eb.getvalue())["error_code"], code)
            self.assertFalse((root / "--json").exists())


if __name__ == "__main__":
    unittest.main()
