#!/usr/bin/env python3
"""
Track S100 Assertion-Free R5 Test Suite (0 bare asserts, 0 skips across all CI modes).

Covers:
  1. All exact-Z/Q oracle primitives, boundary inputs, error paths, and PR #39 vs fixed codec.
  2. Certificate determinism, standalone parity, 0o600 atomic writes, and CLI modes.
  3. Full field-complete SEC / FR0 / FR1 semantic forgery rejection (re-signed tampers across all 4 pillars).
  4. Hardened Zone-B JSON / dir_fd / symlink / PWD-symlink / hardlink / FIFO / DoS boundaries.
  5. R11 static & live Lean 4.36.0 trust-escape matrix + Lean-less CI 0-skip path.
  6. Read-only on-disk pin verifier (anchor + certs + tokenizers + wave7/abios fixtures, positive & negative).
"""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

_TRACK_DIR = Path(__file__).resolve().parent
if str(_TRACK_DIR) not in sys.path:
    sys.path.insert(0, str(_TRACK_DIR))

import s100_tokenpage_handoff_oracle as oracle
import verify_s100_tokenpage_handoff as verifier


class _FakeStdout:
    def __init__(self, buf: io.BytesIO) -> None:
        self.buffer = buf

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        raise io.UnsupportedOperation("fileno")


def _fake_stdout(buf: io.BytesIO) -> _FakeStdout:
    return _FakeStdout(buf)


def _resign(cert: dict) -> dict:
    c = copy.deepcopy(cert)
    c["payload_sha256"] = hashlib.sha256(oracle.canonical_json_bytes(c["payload"])).hexdigest()
    body = {
        "schema_version": c["schema_version"],
        "track_id": c["track_id"],
        "payload_sha256": c["payload_sha256"],
        "payload": c["payload"],
    }
    c["certificate_sha256"] = hashlib.sha256(oracle.canonical_json_bytes(body)).hexdigest()
    return c


def _resign_handoff(h: dict) -> dict:
    unsigned = {k: v for k, v in h.items() if k != "manifest_sha256"}
    out = dict(unsigned)
    out["manifest_sha256"] = hashlib.sha256(oracle.canonical_json_bytes(unsigned)).hexdigest()
    return out


class TestS100OraclePrimitives(unittest.TestCase):
    def test_q_str_and_dec_str_exact_boundaries(self) -> None:
        self.assertEqual(oracle.q_str(Fraction(0, 1)), "0")
        self.assertEqual(oracle.q_str(Fraction(-5, 1)), "-5")
        self.assertEqual(oracle.q_str(Fraction(7, 3)), "7/3")
        with self.assertRaisesRegex(ValueError, "^NOT_FRACTION$"):
            oracle.q_str(3)  # type: ignore[arg-type]

        self.assertEqual(oracle.dec_str(Fraction(1, 200), 2), "0.01")
        self.assertEqual(oracle.dec_str(Fraction(1, 201), 2), "0.00")
        self.assertEqual(oracle.dec_str(Fraction(-1, 10000), 2), "0.00")
        self.assertEqual(oracle.dec_str(Fraction(-3, 2), 2), "-1.50")
        self.assertEqual(oracle.dec_str(Fraction(25, 100), 1), "0.3")
        self.assertEqual(oracle.dec_str(Fraction(24, 100), 1), "0.2")
        for bad_val, bad_dig in ((Fraction(1, 2), 0), (Fraction(1, 2), True), ("1/2", 2)):
            with self.assertRaisesRegex(ValueError, "^BAD_DEC_ARGS$"):
                oracle.dec_str(bad_val, bad_dig)  # type: ignore[arg-type]

    def test_discrete_breakeven_compounding_and_sign_reversal(self) -> None:
        be0 = oracle.discrete_breakeven_turn(0, 10, 4)
        self.assertEqual(be0["breakeven_turn_n_star"], 1)
        self.assertFalse(be0["prev_turn_beats_base"])
        self.assertTrue(be0["n_star_beats_base"])

        be_exact = oracle.discrete_breakeven_turn(24, 10, 4)
        self.assertEqual(be_exact["per_turn_savings"], 6)
        self.assertEqual(be_exact["breakeven_turn_n_star"], 5)
        self.assertFalse(be_exact["prev_turn_beats_base"])
        self.assertTrue(be_exact["n_star_beats_base"])

        with self.assertRaisesRegex(ValueError, "^INVALID_BREAKEVEN_PARAMS$"):
            oracle.discrete_breakeven_turn(-1, 10, 4)
        with self.assertRaisesRegex(ValueError, "^INVALID_BREAKEVEN_PARAMS$"):
            oracle.discrete_breakeven_turn(10, 4, 4)

        row_k1 = oracle.compute_compounding_row("t1", 200, 100, 1, 4, 1)
        self.assertEqual(row_k1["edges_m"], 1)
        self.assertEqual(row_k1["bpe_tax_q"], "2")
        self.assertEqual(row_k1["en_over_ar_cost_q"], "2")
        self.assertTrue(row_k1["raw_arabic_strictly_cheaper"])

        row_k2 = oracle.compute_compounding_row("t2", 200, 100, 1, 2, 2)
        self.assertEqual(row_k2["edges_m"], 3)
        self.assertEqual(row_k2["simplex_retention_q"], "1/8")
        self.assertEqual(row_k2["en_over_ar_cost_q"], "4")
        self.assertTrue(row_k2["raw_arabic_strictly_cheaper"])

        row_cheap_en = oracle.compute_compounding_row("t3", 500, 100, 1, 2, 1)
        self.assertEqual(row_cheap_en["en_over_ar_cost_q"], "2/5")
        self.assertFalse(row_cheap_en["raw_arabic_strictly_cheaper"])

        for bad in ((0, 1, 1, 2, 1), (1, 0, 1, 2, 1), (1, 1, 0, 2, 1), (1, 1, 2, 2, 1), (1, 1, 1, 2, 0)):
            with self.assertRaisesRegex(ValueError, "^INVALID_COMPOUND_INPUT$"):
                oracle.compute_compounding_row("bad", *bad)

        self.assertTrue(oracle.is_sign_reversal(Fraction(1, 2), Fraction(-1, 2)))
        self.assertFalse(oracle.is_sign_reversal(Fraction(0, 1), Fraction(-1, 2)))
        self.assertFalse(oracle.is_sign_reversal(Fraction(1, 2), Fraction(0, 1)))
        self.assertFalse(oracle.is_sign_reversal(Fraction(-1, 2), Fraction(-1, 2)))
        self.assertFalse(oracle.is_sign_reversal(Fraction(1, 2), Fraction(1, 2)))

    def test_pr39_wire_lists_repro_and_fixed_codec_all_branches(self) -> None:
        self.assertTrue(oracle._pr39_item_needs_fallback(123))
        self.assertFalse(oracle._pr39_item_needs_fallback(""))
        for trig in ("a\nb", "a\rb", 'a"b', "a[b", "a]b", "a\\", "{x}", "http://x", "123", "-", "p", "g"):
            self.assertTrue(oracle._pr39_item_needs_fallback(trig))
        self.assertFalse(oracle._pr39_item_needs_fallback("hello"))
        self.assertEqual(oracle._pr39_encode_wire([]), "[]")
        self.assertEqual(oracle._pr39_encode_wire(["", "a;b", "c\\d"]), "[\\e;a\\;b;c\\\\d]")
        self.assertEqual(oracle._pr39_decode_wire("[]"), [])
        self.assertEqual(oracle._pr39_decode_wire("[\\e;a\\;b;c\\\\d]"), ["", "a;b", "c\\d"])
        self.assertIsNone(oracle._pr39_decode_wire("no_brackets"))
        self.assertIsNone(oracle._pr39_decode_wire("[unclosed"))
        self.assertIsNone(oracle._pr39_decode_wire("unopened]"))
        self.assertIsNone(oracle._pr39_decode_wire("[a\\]"))
        self.assertIsNone(oracle._pr39_decode_wire("[123]"))
        self.assertIsNone(oracle._pr39_decode_wire("[p]"))
        self.assertEqual(oracle._pr39_decode_wire('["ok","x"]'), ["ok", "x"])
        self.assertEqual(oracle._pr39_decode_wire("[ ]"), [])
        self.assertEqual(oracle._pr39_decode_wire("[1,2]"), ["1,2"])

        # Codec summary helper: verify every single sub-condition
        ok_sum = oracle.summarize_codec_checks([], 1, ["1,2"], 2, 3, None, 6, 6, 6)
        self.assertEqual(ok_sum, {"d1": True, "d2": True, "d3": True, "fixed": True})
        self.assertFalse(oracle.summarize_codec_checks(["x"], 1, ["1,2"], 2, 3, None, 6, 6, 6)["d1"])
        self.assertFalse(oracle.summarize_codec_checks([], 2, ["1,2"], 2, 3, None, 6, 6, 6)["d1"])
        self.assertFalse(oracle.summarize_codec_checks([], 1, ["x"], 2, 3, None, 6, 6, 6)["d2"])
        self.assertFalse(oracle.summarize_codec_checks([], 1, ["1,2"], 1, 3, None, 6, 6, 6)["d2"])
        self.assertFalse(oracle.summarize_codec_checks([], 1, ["1,2"], 2, 2, None, 6, 6, 6)["d3"])
        self.assertFalse(oracle.summarize_codec_checks([], 1, ["1,2"], 2, 3, ["x"], 6, 6, 6)["d3"])
        self.assertFalse(oracle.summarize_codec_checks([], 1, ["1,2"], 2, 3, None, 5, 6, 6)["fixed"])
        self.assertFalse(oracle.summarize_codec_checks([], 1, ["1,2"], 2, 3, None, 6, 5, 6)["fixed"])

        # Fixed codec lossless bijection across all tricky inputs (incl. empty item & % escaping)
        cases = [
            [],
            [""],
            ["alpha", "beta"],
            ["a;b", ""],
            [" "],
            [1, 2],
            ["see [1] now"],
            ["100% pure %20 space"],
            ["p", "123", "-", "{k}", "a,b", "a\\b", "line\nbreak"],
        ]
        for case in cases:
            wire = oracle.encode_fixed_wire_list(case)
            self.assertNotIn(" ", wire)
            self.assertEqual(oracle.decode_fixed_wire_list(wire), case)
        self.assertEqual(oracle.encode_fixed_wire_list(["alpha", "beta"]), "S[alpha;beta]")
        self.assertTrue(oracle.encode_fixed_wire_list([""]).startswith("J:"))
        self.assertTrue(oracle.encode_fixed_wire_list(["123"]).startswith("J:"))
        self.assertTrue(oracle.encode_fixed_wire_list(["p"]).startswith("J:"))
        with self.assertRaisesRegex(ValueError, "^FIXED_CODEC_NOT_LIST$"):
            oracle.encode_fixed_wire_list("not_a_list")  # type: ignore[arg-type]
        for bad_tok, code in (
            ('J:["a b"]', "^FIXED_CODEC_SPACE_IN_TOKEN$"),
            (42, "^FIXED_CODEC_SPACE_IN_TOKEN$"),
            ("S[]", "^FIXED_CODEC_EMPTY_S_BODY$"),
            ("S[alpha", "^FIXED_CODEC_BAD_PREFIX$"),
            ("X:[1,2]", "^FIXED_CODEC_BAD_PREFIX$"),
            ("J:123", "^FIXED_CODEC_JSON_NOT_LIST$"),
        ):
            with self.assertRaisesRegex(ValueError, code):
                oracle.decode_fixed_wire_list(bad_tok)  # type: ignore[arg-type]

    def test_vocab_surgery_dpi_and_borromean_primitives(self) -> None:
        row = oracle.compute_vocab_surgery_row("M", 128, 1_000_000, 16, 40, 10)
        self.assertEqual(row["tied_added_params"], 2048)
        self.assertEqual(row["untied_added_params"], 4096)
        self.assertEqual(row["breakeven_turn_n_star"], 5)
        self.assertEqual(row["net_tokens_saved_100_turns"], 960)
        self.assertEqual(row["net_tokens_saved_1000_turns"], 9960)
        for bad in ((0, 10, 1, 1, 1), (10, 0, 1, 1, 1), (10, 10, 0, 1, 1), (10, 10, 1, 1, 0)):
            with self.assertRaisesRegex(ValueError, "^INVALID_SURGERY_ARGS$"):
                oracle.compute_vocab_surgery_row("M", *bad)

        dpi = oracle.compute_s31_dpi_and_householder_witness(100, 10, 4, 2)
        self.assertEqual(dpi["total_rows"], 110)
        self.assertEqual(dpi["matched_dpi_ratio_q"], "1")
        self.assertEqual(dpi["spike_dpi_ratio_q"], "220/111")
        self.assertTrue(dpi["spike_exceeds_unity"])
        self.assertEqual(dpi["s31_two_row_dpi_anchor_q"], "50")
        self.assertEqual(dpi["householder_norm_before_q"], "70")
        self.assertEqual(dpi["householder_norm_after_q"], "70")
        self.assertEqual(dpi["householder_norm_delta_q"], "0")
        self.assertTrue(dpi["householder_involution_exact"])
        for bad in ((0, 1, 1, 2), (1, 0, 1, 2), (1, 1, 0, 2), (1, 1, 1, 1)):
            with self.assertRaisesRegex(ValueError, "^INVALID_DPI_ARGS$"):
                oracle.compute_s31_dpi_and_householder_witness(*bad)

        self.assertTrue(oracle.evaluate_four_gate_borromean(True, True, True, True)["all_four_gates_pass"])
        for combo in ((False, True, True, True), (True, False, True, True), (True, True, False, True), (True, True, True, False)):
            self.assertFalse(oracle.evaluate_four_gate_borromean(*combo)["all_four_gates_pass"])

        base_abls = {
            "all_four_gates_clean": {"all_four_gates_pass": True},
            "ablate_g1_unpinned_sha": {"all_four_gates_pass": False},
            "ablate_g2_memory_spill": {"all_four_gates_pass": False},
            "ablate_g3_float_predicate": {"all_four_gates_pass": False},
            "ablate_g4_missing_kill_gate": {"all_four_gates_pass": False},
        }
        self.assertTrue(oracle.check_borromean_ablation_table(base_abls))
        for kname in base_abls:
            mut = copy.deepcopy(base_abls)
            mut[kname]["all_four_gates_pass"] = not mut[kname]["all_four_gates_pass"]
            self.assertFalse(oracle.check_borromean_ablation_table(mut))


class TestS100ZoneBAndSemanticForgeries(unittest.TestCase):
    def setUp(self) -> None:
        self.cert = oracle.build_certificate_envelope()

    def test_valid_cert_passes_sec_fr0_fr1_and_exact_equal(self) -> None:
        res1 = verifier.verify_certificate_dict(self.cert, full_replay=True)
        res0 = verifier.verify_certificate_dict(self.cert, full_replay=False)
        self.assertEqual(res1["status"], "PASS")
        self.assertEqual(res0["status"], "PASS")
        self.assertTrue(res1["full_replay"])
        self.assertFalse(res0["full_replay"])
        sec = verifier.secondary_audit_payload(self.cert["payload"])
        self.assertEqual(sec["track_id"], oracle.TRACK_ID)

        self.assertFalse(verifier._is_sha256_hex(123))
        self.assertFalse(verifier._is_sha256_hex("nothex"))
        self.assertTrue(verifier._is_sha256_hex("0" * 64))

        # Direct helper exact-code checks
        with self.assertRaisesRegex(ValueError, "^D_ERR$"):
            verifier._req_dict([], "D_ERR")
        with self.assertRaisesRegex(ValueError, "^I_ERR$"):
            verifier._req_int("1", "I_ERR")
        with self.assertRaisesRegex(ValueError, "^I_ERR$"):
            verifier._req_int(True, "I_ERR")
        with self.assertRaisesRegex(ValueError, "^S_ERR$"):
            verifier._req_str(1, "S_ERR")
        with self.assertRaisesRegex(ValueError, "^L_ERR$"):
            verifier._req_list("abc", 3, "L_ERR")
        with self.assertRaisesRegex(ValueError, "^L_ERR$"):
            verifier._req_list([1, 2], 3, "L_ERR")

        self.assertTrue(verifier.exact_typed_equal({"a": [1, {"b": True}]}, {"a": [1, {"b": True}]}))
        self.assertFalse(verifier.exact_typed_equal(1, True))
        self.assertFalse(verifier.exact_typed_equal({"a": 1}, {"a": 1, "b": 2}))
        self.assertFalse(verifier.exact_typed_equal({"a": 1}, {"b": 1}))
        self.assertFalse(verifier.exact_typed_equal([1, 2], [1]))
        self.assertFalse(verifier.exact_typed_equal([1, 2], [1, 3]))
        with self.assertRaisesRegex(ValueError, "^INVALID_FULL_REPLAY_FLAG$"):
            verifier.verify_certificate_dict(self.cert, full_replay=1)  # type: ignore[arg-type]

    def test_parse_canonical_q_and_strict_json_edges(self) -> None:
        self.assertEqual(verifier.parse_canonical_q("0", "Q"), Fraction(0, 1))
        self.assertEqual(verifier.parse_canonical_q("-7", "Q"), Fraction(-7, 1))
        self.assertEqual(verifier.parse_canonical_q("-3/5", "Q"), Fraction(-3, 5))
        for bad in (
            123, "", "-0", "01", "1/1", "2/4", "1/0", "1/-2", "1/2/3", " 1/2", "1/02",
            "9" * (verifier.MAX_INT_DIGITS + 1),
            "-" + "9" * (verifier.MAX_INT_DIGITS + 1),
            "9" * 4400,
            ("1" + "0" * verifier.MAX_INT_DIGITS) + "/3",
            "1/" + ("9" * (verifier.MAX_INT_DIGITS + 1)),
            "1/" + ("9" * 4400),
            ("9" * 4400) + "/2",
        ):
            with self.assertRaisesRegex(ValueError, "^Q$"):
                verifier.parse_canonical_q(bad, "Q")
        # Exact MAX_INT_DIGITS (617) rational boundaries pass (kills <= -> < on num & den)
        self.assertEqual(verifier.parse_canonical_q("9" * verifier.MAX_INT_DIGITS, "Q"), Fraction(int("9" * verifier.MAX_INT_DIGITS), 1))
        self.assertEqual(verifier.parse_canonical_q("-" + "9" * verifier.MAX_INT_DIGITS, "Q"), Fraction(-int("9" * verifier.MAX_INT_DIGITS), 1))
        self.assertEqual(verifier.parse_canonical_q(("1" + "0" * (verifier.MAX_INT_DIGITS - 1)) + "/3", "Q"), Fraction(10 ** (verifier.MAX_INT_DIGITS - 1), 3))
        self.assertEqual(verifier.parse_canonical_q("1/" + ("9" * verifier.MAX_INT_DIGITS), "Q"), Fraction(1, int("9" * verifier.MAX_INT_DIGITS)))

        # Exact MAX_INT_BITS (2048 bits, 617 digits) passes; 2049 bits & 4400 digits fail with JSON_INT_TOO_LARGE
        ok_max_int = (1 << 2048) - 1
        verifier._check_json_tree({"a": ok_max_int})
        ok_raw = b'{"a":' + str(ok_max_int).encode("ascii") + b"}\n"
        self.assertEqual(verifier.parse_strict_json_bytes(ok_raw)["a"], ok_max_int)

        fail_bits_int = 1 << 2048  # 617 digits, 2049 bits
        with self.assertRaisesRegex(ValueError, "^JSON_INT_TOO_LARGE$"):
            verifier._parse_capped_int(str(fail_bits_int))
        with self.assertRaisesRegex(ValueError, "^JSON_INT_TOO_LARGE$"):
            verifier._check_json_tree({"a": fail_bits_int})
        with self.assertRaisesRegex(ValueError, "^JSON_INT_TOO_LARGE$"):
            verifier.parse_strict_json_bytes(b'{"a":' + str(fail_bits_int).encode("ascii") + b"}\n")
        # 4400-digit token exercises pre-parse MAX_INT_DIGITS guard before Python int() limit
        with self.assertRaisesRegex(ValueError, "^JSON_INT_TOO_LARGE$"):
            verifier.parse_strict_json_bytes(b'{"a":' + (b"9" * 4400) + b"}\n")

        # Exact depth == 48 passes; depth == 49 fails; json.loads RecursionError maps to JSON_MAX_DEPTH_EXCEEDED
        d48: dict = {}
        cur = d48
        for _ in range(48):
            nxt: dict = {}
            cur["a"] = nxt
            cur = nxt
        verifier._check_json_tree(d48)
        cur["a"] = 1  # now 1 is at depth 49 -> must reject!
        with self.assertRaisesRegex(ValueError, "^JSON_MAX_DEPTH_EXCEEDED$"):
            verifier._check_json_tree(d48)
        with mock.patch("json.loads", side_effect=RecursionError("deep")):
            with self.assertRaisesRegex(ValueError, "^JSON_MAX_DEPTH_EXCEEDED$"):
                verifier.parse_strict_json_bytes(b'{"a":1}\n')

        # Strict JSON rejections with exact error codes
        for bad_raw, pat in (
            (b'{"a":1}\r\n', "^CRLF_FORBIDDEN$"),
            (b'{"a":"\x00"}\n', "^NUL_BYTE_IN_JSON$"),
            (b"\xff\xfe", "^INVALID_UTF8$"),
            (b'{"a":1.5}\n', "^JSON_FLOAT_FORBIDDEN"),
            (b'{"a":NaN}\n', "^JSON_CONSTANT_FORBIDDEN"),
            (b'{"a":Infinity}\n', "^JSON_CONSTANT_FORBIDDEN"),
            (b'{"a":1,"a":2}\n', "^JSON_DUPLICATE_KEY"),
            (b"[1,2,3]\n", "^JSON_ROOT_NOT_OBJECT$"),
            (b'{ "a": 1 }\n', "^NON_CANONICAL_JSON_BYTES$"),
            (b'{"b":1,"a":2}\n', "^NON_CANONICAL_JSON_BYTES$"),
        ):
            with self.assertRaisesRegex(ValueError, pat):
                verifier.parse_strict_json_bytes(bad_raw)

        # In-memory tree checks with exact error codes
        cyc_list: list = []
        cyc_list.append(cyc_list)
        with self.assertRaisesRegex(ValueError, "^JSON_CYCLE$"):
            verifier._check_json_tree(cyc_list)
        cyc_dict: dict = {}
        cyc_dict["self"] = cyc_dict
        with self.assertRaisesRegex(ValueError, "^JSON_CYCLE$"):
            verifier._check_json_tree(cyc_dict)
        verifier._check_json_tree({"k": None})
        for bad_obj, pat in (
            ({"k": "\ud800"}, "^JSON_LONE_SURROGATE$"),
            ({"k": "a\x00b"}, "^JSON_NUL_IN_STRING$"),
            ({1: "v"}, "^JSON_NON_STRING_KEY$"),
            ({"k": 1.25}, "^JSON_DISALLOWED_TYPE"),
            ({"k": (1, 2)}, "^JSON_DISALLOWED_TYPE"),
        ):
            with self.assertRaisesRegex(ValueError, pat):
                verifier._check_json_tree(bad_obj)

    def test_resigned_semantic_forgeries_all_rejected_across_sec_fr0_fr1(self) -> None:
        # Envelope tampers with exact error-code checks
        c_bad_key = copy.deepcopy(self.cert)
        c_bad_key["extra"] = 1
        with self.assertRaisesRegex(ValueError, "^CERT_KEYS_MISMATCH$"):
            verifier.verify_certificate_dict(c_bad_key, full_replay=False)
        for fld, val, pat in (
            ("schema_version", "wrong", "^SCHEMA_VERSION_MISMATCH$"),
            ("track_id", "wrong", "^TRACK_ID_MISMATCH$"),
            ("payload_sha256", "nothex", "^INVALID_PAYLOAD_SHA256$"),
            ("certificate_sha256", "nothex", "^INVALID_CERT_SHA256$"),
            ("payload_sha256", "0" * 64, "^PAYLOAD_SHA256_TAMPERED$"),
            ("certificate_sha256", "0" * 64, "^CERTIFICATE_SHA256_TAMPERED$"),
        ):
            cm = copy.deepcopy(self.cert)
            cm[fld] = val
            with self.assertRaisesRegex(ValueError, pat):
                verifier.verify_certificate_dict(cm, full_replay=False)

        def _assert_rejected(mutated_cert: dict, label: str, sec_pat: str | None = None) -> None:
            resigned = _resign(mutated_cert)
            if sec_pat is not None:
                with self.assertRaisesRegex(ValueError, sec_pat, msg=f"SEC code mismatch {label}"):
                    verifier.secondary_audit_payload(resigned["payload"])
            else:
                with self.assertRaises(ValueError, msg=f"SEC failed to reject {label}"):
                    verifier.secondary_audit_payload(resigned["payload"])
            with self.assertRaises(ValueError, msg=f"FR0 failed to reject {label}"):
                verifier.verify_certificate_dict(resigned, full_replay=False)
            with self.assertRaises(ValueError, msg=f"FR1 failed to reject {label}"):
                verifier.verify_certificate_dict(resigned, full_replay=True)

        mutations: list[tuple[str, Any, str | None]] = [
            ("top_extra", lambda p: p.__setitem__("sneaky", 1), "^PAYLOAD_KEYS_MISMATCH$"),
            ("unexpected_bool", lambda p: p["pillar_1_tokenizer_protocol_and_arabic_density"]["abios_sym2p_4form_audit"].__setitem__("packet_count", True), "^UNEXPECTED_BOOL_FIELD"),
            ("bool_in_list", lambda p: p["pillar_2_vocab_surgery_and_s31_dpi_bounds"].__setitem__("k_grid", [16, 32, 64, True]), "^UNEXPECTED_BOOL_ITEM$"),
            ("top_track", lambda p: p.__setitem__("track_id", "WRONG"), "^PAYLOAD_TRACK_MISMATCH$"),
            ("top_oracle", lambda p: p.__setitem__("oracle_class", "WRONG"), "^ORACLE_CLASS_MISMATCH$"),
            ("top_nov", lambda p: p.__setitem__("novelty_tier", "N2"), "^NOVELTY_TIER_MISMATCH$"),
            ("top_verified", lambda p: p.__setitem__("all_pillars_verified", False), "^PILLARS_NOT_VERIFIED$"),
            ("p1_extra", lambda p: p["pillar_1_tokenizer_protocol_and_arabic_density"].__setitem__("extra", 1), "^P1_KEYS$"),
            ("p1_not_ver", lambda p: p["pillar_1_tokenizer_protocol_and_arabic_density"].__setitem__("all_verified", False), "^P1_NOT_VERIFIED$"),
            ("p1_pkt_cnt", lambda p: p["pillar_1_tokenizer_protocol_and_arabic_density"]["abios_sym2p_4form_audit"].__setitem__("packet_count", 11), "^P1_ABIOS_PKT$"),
            ("p1_form_tok", lambda p: p["pillar_1_tokenizer_protocol_and_arabic_density"]["abios_sym2p_4form_audit"]["forms"]["sym2p_jsonl"].__setitem__("qwen25_tokens", 1765), "^P1_FORM_Q$"),
            ("p1_q_bad", lambda p: p["pillar_1_tokenizer_protocol_and_arabic_density"]["abios_sym2p_4form_audit"].__setitem__("qwen25_sym2p_vs_markdown_saving_q", "1/2"), "^P1_AB_QMD$"),
            ("p1_dec4", lambda p: p["pillar_1_tokenizer_protocol_and_arabic_density"]["abios_sym2p_4form_audit"].__setitem__("qwen25_abios3_full_vs_markdown_saving_dec4", "0.4130"), "^P1_AB_QAFM$"),
            ("p1_be", lambda p: p["pillar_1_tokenizer_protocol_and_arabic_density"]["abios_sym2p_4form_audit"].__setitem__("qwen25_abios3_vs_sym2p_breakeven_packets", 4), "^P1_AB_QBE$"),
            ("p1_glyph", lambda p: p["pillar_1_tokenizer_protocol_and_arabic_density"]["aletheia_8glyph_and_5cert_audit"].__setitem__("glyph_qwen25_total_tokens", 16), "^P1_AL_GQ$"),
            ("p1_cert_bpt", lambda p: p["pillar_1_tokenizer_protocol_and_arabic_density"]["aletheia_8glyph_and_5cert_audit"].__setitem__("frozen_cert_qwen25_bytes_per_tok_dec4", "2.3717"), "^P1_AL_QBPT$"),
            ("p1_arabic_extra", lambda p: p["pillar_1_tokenizer_protocol_and_arabic_density"]["s92_arabic_vocab_tax_and_compounding"].__setitem__("treatises_extra_smollm2_tokens", 1), "^P1_AR_TE$"),
            ("p1_comp_row", lambda p: p["pillar_1_tokenizer_protocol_and_arabic_density"]["s92_arabic_vocab_tax_and_compounding"]["compounding_ladder"][4].__setitem__("en_over_ar_cost_dec4", "6.0982"), "^P1_AR_RCOST$"),
            ("p1_comp_bool", lambda p: p["pillar_1_tokenizer_protocol_and_arabic_density"]["s92_arabic_vocab_tax_and_compounding"]["compounding_ladder"][1].__setitem__("raw_arabic_strictly_cheaper", True), "^P1_AR_RCHEAP$"),
            ("p1_gauge", lambda p: p["pillar_1_tokenizer_protocol_and_arabic_density"]["representation_vs_readout_gauge_gap"].__setitem__("abios51_readout_jump_dec4", "0.5218"), "^P1_GG_JMP$"),
            ("p1_codec", lambda p: p["pillar_1_tokenizer_protocol_and_arabic_density"]["abios_pr39_wire_lists_codec_audit"].__setitem__("defect1_decoded_len", 1), "^P1_CD_D1L$"),
            ("p2_not_ver", lambda p: p["pillar_2_vocab_surgery_and_s31_dpi_bounds"].__setitem__("all_verified", False), "^P2_NOT_VERIFIED$"),
            ("p2_kgrid", lambda p: p["pillar_2_vocab_surgery_and_s31_dpi_bounds"].__setitem__("k_grid", [16, 32, 64, 256]), "^P2_KGRID$"),
            ("p2_ppm", lambda p: p["pillar_2_vocab_surgery_and_s31_dpi_bounds"]["protocol_token_surgery_sweep"][0].__setitem__("tied_overhead_ppm_dec2", "29.03"), "^P2_TPPM$"),
            ("p2_dpi", lambda p: p["pillar_2_vocab_surgery_and_s31_dpi_bounds"]["s31_dpi_qwen25_k128_safety_bound"].__setitem__("spike_dpi_ratio_dec4", "15.9985"), "^P2_DQ_SD$"),
            ("p2_hh", lambda p: p["pillar_2_vocab_surgery_and_s31_dpi_bounds"]["s31_dpi_smollm2_k128_safety_bound"].__setitem__("householder_involution_exact", False), "^P2_DS_HI$"),
            ("p3_not_ver", lambda p: p["pillar_3_three_node_m1max_and_edge_handoff_pack"].__setitem__("all_verified", False), "^P3_NOT_VERIFIED$"),
            ("p3_abl_flag", lambda p: p["pillar_3_three_node_m1max_and_edge_handoff_pack"].__setitem__("all_four_ablations_rejected", False), "^P3_ABL_FLAG$"),
            ("p3_nc", lambda p: p["pillar_3_three_node_m1max_and_edge_handoff_pack"].__setitem__("node_count", 2), "^P3_NC$"),
            ("p3_hc", lambda p: p["pillar_3_three_node_m1max_and_edge_handoff_pack"].__setitem__("handoff_count", 3), "^P3_HC$"),
            ("p3_node", lambda p: p["pillar_3_three_node_m1max_and_edge_handoff_pack"]["nodes"][1].__setitem__("vram_or_unified_gb_q", "32"), "^P3_NMEM$"),
            ("p3_h1_nonhex", lambda p: p["pillar_3_three_node_m1max_and_edge_handoff_pack"]["handoffs"][0].__setitem__("manifest_sha256", "\u00e9" * 64), "^P3_H1_SHA$"),
            ("p3_h1_badsha", lambda p: p["pillar_3_three_node_m1max_and_edge_handoff_pack"]["handoffs"][0].__setitem__("manifest_sha256", "0" * 64), "^P3_H1_SHA$"),
            ("p3_h1_raw", lambda p: p["pillar_3_three_node_m1max_and_edge_handoff_pack"]["handoffs"][0].__setitem__("model_num_layers", 25), "^P3_H1_SHA$"),
            ("p3_abl", lambda p: p["pillar_3_three_node_m1max_and_edge_handoff_pack"]["borromean_four_gate_ablations"]["ablate_g2_memory_spill"].__setitem__("all_four_gates_pass", True), "^P3_GALL$"),
            ("p4_zero_cp", lambda p: p["pillar_4_provenance_and_lean4"].__setitem__("zero_dataset_copies_in_expedition", False), "^P4_ZERO_COPIES$"),
            ("p4_lean_sha", lambda p: p["pillar_4_provenance_and_lean4"]["lean4_companion"].__setitem__("sha256", "0" * 64), "^P4_LSHA$"),
            ("p4_non_ascii_sha", lambda p: p["pillar_4_provenance_and_lean4"]["lean4_companion"].__setitem__("sha256", "\u00e9" * 64), "^P4_LSHA$"),
            ("p4_anchor_sha", lambda p: p["pillar_4_provenance_and_lean4"]["anchor_pin"].__setitem__("file_sha256", "0" * 64), "^P4_AP_FS$"),
            ("p4_n2", lambda p: p["pillar_4_provenance_and_lean4"]["novelty_honesty_law4"].__setitem__("n2_claims", 1), "^P4_N2$"),
            ("p4_uc", lambda p: p["pillar_4_provenance_and_lean4"].__setitem__("upstream_cert_count", 4), "^P4_UC$"),
            ("p4_tc", lambda p: p["pillar_4_provenance_and_lean4"].__setitem__("tokenizer_pin_count", 1), "^P4_TC$"),
            ("p4_fc", lambda p: p["pillar_4_provenance_and_lean4"].__setitem__("wave_fixture_pin_count", 4), "^P4_FC$"),
            ("p4_up_sha", lambda p: p["pillar_4_provenance_and_lean4"]["upstream_cert_pins"][0].__setitem__("sha256", "0" * 64), "^P4_UP_SHA$"),
            ("p4_tok_sha", lambda p: p["pillar_4_provenance_and_lean4"]["tokenizer_pins"][1].__setitem__("sha256", "0" * 64), "^P4_TOK_SHA$"),
            ("p4_fix_sha", lambda p: p["pillar_4_provenance_and_lean4"]["wave_fixture_pins"][0].__setitem__("sha256", "0" * 64), "^P4_FIX_SHA$"),
        ]
        for name, fn, pat in mutations:
            cm = copy.deepcopy(self.cert)
            fn(cm["payload"])
            _assert_rejected(cm, name, pat)

        # Re-signed handoff manifest tampers (bypass manifest_sha256, caught by semantic & narrative predicates!)
        for idx, fld, val, pat in (
            (0, "pass_gate_max_eval_wall_sec", 999, "^P3_H1_WT$"),
            (0, "title", "Forged H1 Title", "^P3_H1_TI$"),
            (0, "kill_gate_trigger", "never_kill", "^P3_H1_KG$"),
            (1, "e8_l4_suppression_factor_q", "2", "^P3_H2_SF$"),
            (1, "title", "Forged H2 Title", "^P3_H2_TI$"),
            (1, "kill_gate_trigger", "never_kill", "^P3_H2_KG$"),
            (2, "gemma12b_buggy_blowup_dec4", "2.9779", "^P3_H3_BLOW$"),
            (2, "title", "Forged H3 Title", "^P3_H3_TI$"),
            (2, "kill_gate_trigger", "never_kill", "^P3_H3_KG$"),
            (3, "lan_4096tok_speedup_dec4", "8.6733", "^P3_H4_SP4K$"),
            (3, "title", "Forged H4 Title", "^P3_H4_TI$"),
            (3, "kill_gate_trigger", "never_kill", "^P3_H4_KG$"),
        ):
            cm = copy.deepcopy(self.cert)
            h = cm["payload"]["pillar_3_three_node_m1max_and_edge_handoff_pack"]["handoffs"][idx]
            h[fld] = val
            cm["payload"]["pillar_3_three_node_m1max_and_edge_handoff_pack"]["handoffs"][idx] = _resign_handoff(h)
            _assert_rejected(cm, f"p3_h{idx+1}_{fld}_resigned", pat)

        # Narrative node.role forgery rejected across SEC/FR0/FR1
        for nidx in range(3):
            cm = copy.deepcopy(self.cert)
            cm["payload"]["pillar_3_three_node_m1max_and_edge_handoff_pack"]["nodes"][nidx]["role"] = "forged_role"
            _assert_rejected(cm, f"p3_node{nidx}_role", "^P3_NROLE$")

        # FR1 drift test
        with mock.patch.object(verifier, "build_certificate_envelope") as m_env:
            alt = copy.deepcopy(self.cert)
            alt["certificate_sha256"] = "f" * 64
            m_env.return_value = alt
            with self.assertRaisesRegex(ValueError, "^ORACLE_CERT_DRIFT$"):
                verifier.verify_certificate_dict(self.cert, full_replay=True)
            alt2 = copy.deepcopy(self.cert)
            alt2["payload"]["novelty_tier"] = "DIFF"
            m_env.return_value = alt2
            with self.assertRaisesRegex(ValueError, "^ORACLE_PAYLOAD_DRIFT$"):
                verifier.verify_certificate_dict(self.cert, full_replay=True)


class TestS100HardenedIOAndCLI(unittest.TestCase):
    def test_dir_fd_io_boundaries_and_atomic_0600_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cert_path = root / "cert.json"
            data = oracle.canonical_json_bytes(oracle.build_certificate_envelope()) + b"\n"
            verifier.atomic_write_0600(cert_path, data)
            self.assertEqual(stat.S_IMODE(cert_path.stat().st_mode), 0o600)
            # Exact max_bytes boundary passes (kills <= -> <)
            self.assertEqual(verifier.read_regular_file_bytes(cert_path, max_bytes=len(data)), data)

            # Overwrite existing regular file works
            verifier.atomic_write_0600(cert_path, data)
            self.assertEqual(verifier.check_certificate_file(cert_path)["status"], "PASS")

            # Stat-level oversize fails BEFORE os.read is ever called
            with mock.patch("os.read", side_effect=RuntimeError("should_not_read")):
                with self.assertRaisesRegex(ValueError, "^FILE_TOO_LARGE$"):
                    verifier.read_regular_file_bytes(cert_path, max_bytes=len(data) - 1)

            # Streaming oversize when fstat reports smaller st_size than actual read bytes
            fake_st = mock.Mock(st_mode=stat.S_IFREG | 0o600, st_nlink=1, st_size=1)
            with mock.patch("os.fstat", return_value=fake_st):
                with self.assertRaisesRegex(ValueError, "^FILE_TOO_LARGE$"):
                    verifier.read_regular_file_bytes(cert_path, max_bytes=16)

            # Symlink leaf rejection (read & write) with exact SYMLINK_IN_PATH
            sym = root / "sym.json"
            sym.symlink_to(cert_path)
            with self.assertRaisesRegex(ValueError, "^SYMLINK_IN_PATH"):
                verifier.read_regular_file_bytes(sym)
            with self.assertRaisesRegex(ValueError, "^SYMLINK_IN_PATH"):
                verifier.atomic_write_0600(sym, b"{}")

            # Symlink ancestor directory rejection
            real_sub = root / "real_sub"
            real_sub.mkdir()
            (real_sub / "x.json").write_bytes(b"{}")
            sym_dir = root / "sym_dir"
            sym_dir.symlink_to(real_sub)
            with self.assertRaisesRegex(ValueError, "^SYMLINK_IN_PATH"):
                verifier.read_regular_file_bytes(sym_dir / "x.json")

            # Missing parent / missing file
            with self.assertRaisesRegex(ValueError, "^INVALID_PARENT_DIR"):
                verifier.read_regular_file_bytes(root / "no_such_dir" / "a.json")
            with self.assertRaisesRegex(ValueError, "^FILE_OPEN_ERROR"):
                verifier.read_regular_file_bytes(root / "missing.json")

            # Hardlink rejection (read & write)
            hl = root / "hardlink.json"
            os.link(cert_path, hl)
            with self.assertRaisesRegex(ValueError, "^HARDLINK_FORBIDDEN$"):
                verifier.read_regular_file_bytes(hl)
            with self.assertRaisesRegex(ValueError, "^HARDLINK_FORBIDDEN$"):
                verifier.atomic_write_0600(hl, b"{}")
            hl.unlink()

            # FIFO (non-regular file) rejection
            fifo = root / "pipe.json"
            os.mkfifo(fifo)
            with self.assertRaisesRegex(ValueError, "^NOT_REGULAR_FILE$"):
                verifier.read_regular_file_bytes(fifo)
            with self.assertRaisesRegex(ValueError, "^TARGET_NOT_REGULAR$"):
                verifier.atomic_write_0600(fifo, b"{}")

            # atomic_write_0600 race guards: tmp hardlink & post-close symlink re-check
            with mock.patch("os.fstat", return_value=mock.Mock(st_nlink=2)):
                with self.assertRaisesRegex(ValueError, "^TMP_HARDLINK_DETECTED$"):
                    verifier.atomic_write_0600(root / "race_hl.json", b"{}")
            lstat_calls = [FileNotFoundError("no"), mock.Mock(st_mode=stat.S_IFLNK | 0o777)]
            with mock.patch("os.lstat", side_effect=lstat_calls):
                with self.assertRaisesRegex(ValueError, "^SYMLINK_IN_PATH$"):
                    verifier.atomic_write_0600(root / "race_sym.json", b"{}")

            # Bad path types, NUL, surrogate, dot leaf
            for bad_p, pat in (
                ("str_path", "^INVALID_PATH_TYPE$"),
                (Path("a\x00b"), "^INVALID_PATH$"),
                (Path("a\ud800b"), "^INVALID_PATH_SURROGATE$"),
                (Path("."), "^INVALID_PATH$"),
                (Path(".."), "^INVALID_PATH$"),
                (Path("/"), "^INVALID_PATH$"),
            ):
                with self.assertRaisesRegex(ValueError, pat):
                    verifier._open_parent_dir_fd(bad_p)  # type: ignore[arg-type]

            # Relative path + PWD checks (absent, relative, valid abs, symlink, surrogate, nonexistent)
            old_cwd = os.getcwd()
            try:
                os.chdir(real_sub)
                with mock.patch.object(verifier.os, "environ", {}):
                    self.assertEqual(verifier.read_regular_file_bytes(Path("x.json")), b"{}")
                with mock.patch.object(verifier.os, "environ", {"PWD": "ignored/" + str(sym_dir).lstrip("/")}):
                    self.assertEqual(verifier.read_regular_file_bytes(Path("x.json")), b"{}")
                with mock.patch.object(verifier.os, "environ", {"PWD": str(real_sub)}):
                    self.assertEqual(verifier.read_regular_file_bytes(Path("x.json")), b"{}")
                with mock.patch.object(verifier.os, "environ", {"PWD": str(sym_dir)}):
                    with self.assertRaisesRegex(ValueError, "^SYMLINK_IN_PATH"):
                        verifier.read_regular_file_bytes(Path("x.json"))
                with mock.patch.object(verifier.os, "environ", {"PWD": "/bad\ud800pwd"}):
                    with self.assertRaisesRegex(ValueError, "^INVALID_PWD_SURROGATE$"):
                        verifier.read_regular_file_bytes(Path("x.json"))
                with mock.patch.object(verifier.os, "environ", {"PWD": str(root / "nonexistent_dir")}):
                    self.assertEqual(verifier.read_regular_file_bytes(Path("x.json")), b"{}")
            finally:
                os.chdir(old_cwd)

            with mock.patch("os.write", return_value=0):
                with self.assertRaises(OSError):
                    verifier.atomic_write_0600(root / "short.json", b"abc")

    def test_cli_modes_and_pin_verification(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cert_path = root / "out_cert.json"

            buf = io.BytesIO()
            with mock.patch.object(sys, "stdout", _fake_stdout(buf)):
                rc = verifier.main(["--write", str(cert_path), "--json"])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(buf.getvalue())["status"], "WRITTEN")

            buf2 = io.BytesIO()
            with mock.patch.object(sys, "stdout", _fake_stdout(buf2)):
                rc2 = verifier.main(["--check", str(cert_path), "--json"])
            self.assertEqual(rc2, 0)
            self.assertEqual(json.loads(buf2.getvalue())["status"], "PASS")

            buf3 = io.BytesIO()
            with mock.patch.object(sys, "stdout", _fake_stdout(buf3)):
                rc3 = verifier.main(["--standalone"])
            self.assertEqual(rc3, 0)
            self.assertEqual(buf3.getvalue(), cert_path.read_bytes())

            err = io.StringIO()
            with mock.patch.object(sys, "stderr", err):
                rc_err = verifier.main(["--check", str(root / "nope.json")])
            self.assertEqual(rc_err, 2)
            self.assertIn("ERROR:", err.getvalue())

            err2 = io.StringIO()
            with mock.patch.object(sys, "stderr", err2):
                rc_np = verifier.main(["--verify-pins"])
            self.assertEqual(rc_np, 2)

            # Real anchor pin positive check
            anchor_path = _TRACK_DIR / "s100_tokenizer_anchor.json"
            buf4 = io.BytesIO()
            with mock.patch.object(sys, "stdout", _fake_stdout(buf4)):
                rc4 = verifier.main(["--verify-pins", "--anchor-file", str(anchor_path), "--json"])
            self.assertEqual(rc4, 0)
            self.assertTrue(json.loads(buf4.getvalue())["anchor_verified"])

            # Anchor negative checks (bytes, file SHA, payload SHA, and each drift field)
            anchor_raw = anchor_path.read_bytes()
            anchor_obj = json.loads(anchor_raw.decode("utf-8"))
            short_a = root / "short_anchor.json"
            short_a.write_bytes(b"{}")
            with self.assertRaisesRegex(ValueError, "^ANCHOR_BYTES_MISMATCH$"):
                verifier.verify_pins_on_disk(anchor_file=short_a)
            bad_fsha = root / "bad_fsha.json"
            bad_fsha.write_bytes(b" " * len(anchor_raw))
            with self.assertRaisesRegex(ValueError, "^ANCHOR_FILE_SHA_MISMATCH$"):
                verifier.verify_pins_on_disk(anchor_file=bad_fsha)

            def _check_anchor_drift(mut_fn, pat: str) -> None:
                m_obj = copy.deepcopy(anchor_obj)
                mut_fn(m_obj)
                m_raw = oracle.canonical_json_bytes(m_obj)
                p_tmp = root / "drift_anchor.json"
                p_tmp.write_bytes(m_raw)
                pin_override = {
                    "file": "drift_anchor.json",
                    "bytes": len(m_raw),
                    "file_sha256": hashlib.sha256(m_raw).hexdigest(),
                    "payload_sha256": oracle.ANCHOR_PIN["payload_sha256"],
                }
                with mock.patch.object(verifier, "ANCHOR_PIN", pin_override):
                    with self.assertRaisesRegex(ValueError, pat):
                        verifier.verify_pins_on_disk(anchor_file=p_tmp)

            _check_anchor_drift(lambda o: o.__setitem__("anchor_payload_sha256", "0" * 64), "^ANCHOR_PAYLOAD_SHA_MISMATCH$")
            _check_anchor_drift(lambda o: o["payload"]["corpus_a_abios_sym2p"]["forms"]["sym2p_jsonl"].__setitem__("qwen25_tokens", 1), "^ANCHOR_ABIOS_FORMS_DRIFT$")
            _check_anchor_drift(lambda o: o["payload"]["corpus_c_s92_raw_arabic_treatises"].__setitem__("total_qwen25_tokens", 1), "^ANCHOR_TR_QWEN_DRIFT$")
            _check_anchor_drift(lambda o: o["payload"]["corpus_c_s92_raw_arabic_treatises"].__setitem__("total_smollm2_tokens", 1), "^ANCHOR_TR_SMOL_DRIFT$")
            _check_anchor_drift(lambda o: o["payload"]["corpus_c_s92_bilingual_catalogs"].__setitem__("total_pairs", 1), "^ANCHOR_BI_PAIRS_DRIFT$")
            _check_anchor_drift(lambda o: o["payload"]["corpus_c_s92_bilingual_catalogs"].__setitem__("total_qwen25_ar_tokens", 1), "^ANCHOR_BI_QAR_DRIFT$")
            _check_anchor_drift(lambda o: o["payload"]["corpus_c_s92_bilingual_catalogs"].__setitem__("total_smollm2_ar_tokens", 1), "^ANCHOR_BI_SAR_DRIFT$")

            # Missing root directories fail with exact *_ROOT_INVALID
            with self.assertRaisesRegex(ValueError, "^EXPEDITION_ROOT_INVALID$"):
                verifier.verify_pins_on_disk(expedition_root=root / "missing")
            with self.assertRaisesRegex(ValueError, "^HF_CACHE_ROOT_INVALID$"):
                verifier.verify_pins_on_disk(hf_cache_root=root / "missing")
            with self.assertRaisesRegex(ValueError, "^WAVE7_ROOT_INVALID$"):
                verifier.verify_pins_on_disk(wave7_root=root / "missing")
            with self.assertRaisesRegex(ValueError, "^ABIOS_ROOT_INVALID$"):
                verifier.verify_pins_on_disk(abios_root=root / "missing")

            # Positive & negative (bytes + SHA) checks for upstream/tokenizer/wave7/abios roots
            mock_w7 = root / "w7"
            mock_w7.mkdir()
            (mock_w7 / "inkling2_mini_config.json").write_bytes(b"cfg")
            mock_ab = root / "ab"
            mock_ab.mkdir()
            (mock_ab / "a.txt").write_bytes(b"ab")
            mock_exp = root / "exp"
            (mock_exp / "sub").mkdir(parents=True)
            (mock_exp / "sub/c.json").write_bytes(b"cert")
            mock_hf = root / "hf"
            mock_hf.mkdir()
            (mock_hf / "tok.json").write_bytes(b"tok")
            good_up = ({"track_id": "S1", "relative_ref": "sub/c.json", "bytes": 4, "sha256": hashlib.sha256(b"cert").hexdigest()},)
            good_tk = ({"id": "t1", "rel_cache_path": "tok.json", "bytes": 3, "sha256": hashlib.sha256(b"tok").hexdigest()},)
            good_fx = (
                {"id": "w1", "root_kind": "wave7", "filename": "inkling2_mini_config.json", "bytes": 3, "sha256": hashlib.sha256(b"cfg").hexdigest()},
                {"id": "a1", "root_kind": "abios", "filename": "a.txt", "bytes": 2, "sha256": hashlib.sha256(b"ab").hexdigest()},
            )
            with (
                mock.patch.object(verifier, "UPSTREAM_CERT_PINS", good_up),
                mock.patch.object(verifier, "TOKENIZER_PINS", good_tk),
                mock.patch.object(verifier, "WAVE_FIXTURE_PINS", good_fx),
            ):
                pr = verifier.verify_pins_on_disk(
                    expedition_root=mock_exp, hf_cache_root=mock_hf, wave7_root=mock_w7, abios_root=mock_ab
                )
                self.assertEqual(pr["upstream_certs_verified"], 1)
                self.assertEqual(pr["tokenizers_verified"], 1)
                self.assertEqual(pr["wave7_fixtures_verified"], 1)
                self.assertEqual(pr["abios_fixtures_verified"], 1)

            # Negative bytes & SHA checks for each root
            with mock.patch.object(verifier, "UPSTREAM_CERT_PINS", (dict(good_up[0], bytes=99),)):
                with self.assertRaisesRegex(ValueError, "^UPSTREAM_BYTES_MISMATCH"):
                    verifier.verify_pins_on_disk(expedition_root=mock_exp)
            with mock.patch.object(verifier, "UPSTREAM_CERT_PINS", (dict(good_up[0], sha256="0" * 64),)):
                with self.assertRaisesRegex(ValueError, "^UPSTREAM_SHA_MISMATCH"):
                    verifier.verify_pins_on_disk(expedition_root=mock_exp)
            with mock.patch.object(verifier, "TOKENIZER_PINS", (dict(good_tk[0], bytes=99),)):
                with self.assertRaisesRegex(ValueError, "^TOKENIZER_BYTES_MISMATCH"):
                    verifier.verify_pins_on_disk(hf_cache_root=mock_hf)
            with mock.patch.object(verifier, "TOKENIZER_PINS", (dict(good_tk[0], sha256="0" * 64),)):
                with self.assertRaisesRegex(ValueError, "^TOKENIZER_SHA_MISMATCH"):
                    verifier.verify_pins_on_disk(hf_cache_root=mock_hf)
            with mock.patch.object(verifier, "WAVE_FIXTURE_PINS", (dict(good_fx[0], bytes=99),)):
                with self.assertRaisesRegex(ValueError, "^WAVE7_BYTES_MISMATCH"):
                    verifier.verify_pins_on_disk(wave7_root=mock_w7)
            with mock.patch.object(verifier, "WAVE_FIXTURE_PINS", (dict(good_fx[0], sha256="0" * 64),)):
                with self.assertRaisesRegex(ValueError, "^WAVE7_SHA_MISMATCH"):
                    verifier.verify_pins_on_disk(wave7_root=mock_w7)
            with mock.patch.object(verifier, "WAVE_FIXTURE_PINS", (dict(good_fx[1], bytes=99),)):
                with self.assertRaisesRegex(ValueError, "^ABIOS_BYTES_MISMATCH"):
                    verifier.verify_pins_on_disk(abios_root=mock_ab)
            with mock.patch.object(verifier, "WAVE_FIXTURE_PINS", (dict(good_fx[1], sha256="0" * 64),)):
                with self.assertRaisesRegex(ValueError, "^ABIOS_SHA_MISMATCH"):
                    verifier.verify_pins_on_disk(abios_root=mock_ab)


class TestS100LeanR11AndLive(unittest.TestCase):
    def test_static_lean_r11_escape_matrix_and_controls(self) -> None:
        # Comment stripper single-dash subtraction & EOF line comment without trailing newline
        stripped_eof, errs_eof = verifier.strip_lean_comments_only("a - b -- tail")
        self.assertEqual(errs_eof, [])
        self.assertEqual(stripped_eof, "a - b        ")
        stripped_nl, errs_nl = verifier.strip_lean_comments_only("a - b -- c\nd")
        self.assertEqual(errs_nl, [])
        self.assertEqual(stripped_nl, "a - b     \nd")

        clean_src = (
            "-- comment mentioning sorry native_decide axiom #exit dbgTrace warn.sorry\n"
            "/- nested /- comment with partial def and dbg_trace -/ still comment -/\n"
            "theorem ok_thm (n : Nat) : n - 0 = n := by simp\n"
            "theorem ok_dec : 1 + 1 = 2 := by decide (native := false)\n"
            "#print axioms ok_thm\n"
        )
        res_clean = verifier.audit_lean_source_static(clean_src)
        self.assertTrue(res_clean["clean"], msg=f"Unexpected findings: {res_clean['findings']}")

        real_src = (_TRACK_DIR / oracle.LEAN_FILE_NAME).read_text(encoding="utf-8")
        res_real = verifier.audit_lean_source_static(real_src)
        self.assertTrue(res_real["clean"], msg=f"Real Lean failed static: {res_real['findings']}")

        with self.assertRaisesRegex(ValueError, "^LEAN_SOURCE_NOT_STR$"):
            verifier.audit_lean_source_static(123)  # type: ignore[arg-type]

        # Exhaustive R11 escape battery MUST all be rejected
        escapes = [
            "/- unterminated comment",
            'def s := "quoted"',
            "def c := 'a'",
            "def «sneaky» := 1",
            "theorem t : True := by sorry",
            "theorem t : True := by admit",
            "axiom bad : False",
            "unsafe def u := 0",
            "theorem t : 1 = 1 := by native_decide",
            "def x := sorryAx",
            "def x := _root_.sorryAx",
            "def x := Lean.ofReduceBool",
            "def x := Lean.ofReduceNat",
            "set_option Lean.trustCompiler true",
            "def x := Lean.Meta.mkSorry",
            "elab x : command => pure ()",
            "macro x : term => x",
            "syntax x := ident",
            "notation x => x",
            "initialize x : Nat := pure 1",
            "builtin_initialize x : Nat := pure 1",
            "opaque foo : Nat := 1",
            "def f := dbg_trace 1",
            "def f := dbg_sleep 0",
            "def f := dbg_stack_trace 1",
            "def f := dbgTrace 1",
            "def f := _root_.dbgTrace 1",
            "def f := dbgTraceVal 1",
            "def f := dbgTraceIfShared 1",
            "def f := dbgSleep 1",
            "def f := dbgStackTrace 1",
            "def f := panic! (String.ofList [])",
            "def f := panicCore 0 (Nat.repr 0)",
            "def f := panicWithPosWithDecl (Nat.repr 0) (Nat.repr 0) 0 0 (Nat.repr 0)",
            "def f := unreachable!",
            "theorem t : 1 = 1 := by bv_decide",
            "theorem t : 1 = 1 := by decide_cbv",
            "def f := throwError 1",
            "run_cmd pure ()",
            "run_meta pure ()",
            "partial def loop : Nat := loop",
            "theorem t : 1 = 1 := by decide +native",
            "theorem t : 1 = 1 := by decide +revert +native",
            "theorem t : 1 = 1 := by decide +revert (config := { native })",
            "theorem t : 1 = 1 := by decide (revert := false) (config := { native })",
            "theorem t : 1 = 1 := by decide (native := !false)",
            "theorem t : 1 = 1 := by decide (native := false\n|| true)",
            "theorem t : 1 = 1 := by decide (config := { native })",
            "theorem t : 1 = 1 := by decide (config := myCfg)",
            "def cfg : DecideConfig := {}",
            "theorem t : 1 = 1 := by decide (revert := true)",
            "set_option debug.skipKernelTC true",
            "set_option debug.byAsSorry true",
            "set_option debug.proofAsSorry true",
            "set_option debug.terminalTacticsAsSorry true",
            "set_option warn.sorry false",
            "#eval 1 + 1",
            "#reduce 1 + 1",
            "#guard_msgs in theorem t : True := trivial",
            "#guard true",
            "#exit",
            "#print def",
            "#print Nat",
            "@[extern c_fn] def f : Nat := 0",
            "@[implemented_by f] def g : Nat := 0",
            "@[export c_fn] def f : Nat := 0",
            "@[csimp] theorem t : 1 = 1 := rfl",
            "@[init] def f : IO Unit := pure ()",
            "attribute [builtin_init] f",
            "@[term_elab x] def te := 1",
            "@[command_elab x] def ce := 1",
            "@[tactic x] def tac := 1",
            "@[builtin_macro x] def bm := 1",
            "import Mathlib",
            "meta import Init",
        ]
        for idx, src in enumerate(escapes):
            r = verifier.audit_lean_source_static(src)
            self.assertFalse(r["clean"], msg=f"Escape #{idx} bypassed scanner: {src!r}")

    def test_resolve_lean_binary_and_verify_lean_proof_live_or_mock(self) -> None:
        with mock.patch.dict(os.environ, {"PATH": "/nonexistent", "HOME": "/nonexistent"}, clear=True):
            with self.assertRaisesRegex(ValueError, "^LEAN_BINARY_UNAVAILABLE$"):
                verifier.resolve_lean_binary()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # ALETHEIA_LEAN_BIN: missing, non-exec file (0o600), exec directory (0o700), and valid exec file
            non_exec = root / "non_exec_lean"
            non_exec.write_text("#!/bin/sh\n", encoding="utf-8")
            non_exec.chmod(0o600)
            exec_dir = root / "exec_dir_lean"
            exec_dir.mkdir(mode=0o700)
            for bad_bin in ("/nonexistent/lean", str(non_exec), str(exec_dir)):
                with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": bad_bin}, clear=True):
                    with self.assertRaisesRegex(ValueError, "^LEAN_BINARY_UNAVAILABLE$"):
                        verifier.resolve_lean_binary()

            fake_lean = root / "lean"
            fake_lean.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_lean.chmod(0o700)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(fake_lean)}, clear=True):
                self.assertEqual(verifier.resolve_lean_binary(), str(fake_lean))

            # $HOME/.elan/bin/lean fallback: reject non-exec file & exec dir, accept valid exec
            fake_home = root / "home"
            (fake_home / ".elan/bin").mkdir(parents=True)
            hl = fake_home / ".elan/bin/lean"
            hl.mkdir(mode=0o700)  # directory first
            with mock.patch.dict(os.environ, {"PATH": "/nonexistent", "HOME": str(fake_home)}, clear=True):
                with self.assertRaisesRegex(ValueError, "^LEAN_BINARY_UNAVAILABLE$"):
                    verifier.resolve_lean_binary()
            hl.rmdir()
            hl.write_text("#!/bin/sh\n", encoding="utf-8")
            hl.chmod(0o600)  # non-exec file
            with mock.patch.dict(os.environ, {"PATH": "/nonexistent", "HOME": str(fake_home)}, clear=True):
                with self.assertRaisesRegex(ValueError, "^LEAN_BINARY_UNAVAILABLE$"):
                    verifier.resolve_lean_binary()
            hl.chmod(0o700)  # valid exec file
            with mock.patch.dict(os.environ, {"PATH": "/nonexistent", "HOME": str(fake_home)}, clear=True):
                self.assertEqual(verifier.resolve_lean_binary(), str(hl))

            # verify_lean_proof validation paths with exact codes
            crlf_f = root / "crlf.lean"
            crlf_f.write_bytes(b"theorem t : True := trivial\r\n")
            with self.assertRaisesRegex(ValueError, "^CRLF_FORBIDDEN$"):
                verifier.verify_lean_proof(crlf_f, enforce_sha256=False)

            bad_utf8 = root / "bad.lean"
            bad_utf8.write_bytes(b"\xff\xfe")
            with self.assertRaisesRegex(ValueError, "^LEAN_INVALID_UTF8$"):
                verifier.verify_lean_proof(bad_utf8, enforce_sha256=False)

            with self.assertRaisesRegex(ValueError, "^INVALID_ENFORCE_SHA256_FLAG$"):
                verifier.verify_lean_proof(_TRACK_DIR / oracle.LEAN_FILE_NAME, enforce_sha256=1)  # type: ignore[arg-type]

            tiny_lean = root / "tiny.lean"
            tiny_lean.write_text("theorem ok_t : True := trivial\n#print axioms ok_t\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "^LEAN_SHA256_MISMATCH$"):
                verifier.verify_lean_proof(tiny_lean, enforce_sha256=True)

            dirty_lean = root / "dirty.lean"
            dirty_lean.write_text("theorem bad_t : True := by sorry\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "^LEAN_STATIC_AUDIT_FAILED"):
                verifier.verify_lean_proof(dirty_lean, enforce_sha256=False)

            def _run_mock(rc: int, out: str, err: str = "") -> mock.MagicMock:
                m = mock.MagicMock()
                m.returncode = rc
                m.stdout = out
                m.stderr = err
                return m

            # Scrubbed Lean env allowlist unit test (strips LEAN_*/ELAN_*/LAKE_*/LD_* in all CI modes)
            hostile_env = {
                "LEAN_PATH": "/hostile",
                "LEAN_OPTS": "-Ddebug.skipKernelTC=true",
                "LEAN_SRC_PATH": "/hostile",
                "LEAN_SYSROOT": "/hostile",
                "LEAN_CC": "/hostile/cc",
                "ELAN_TOOLCHAIN": "evil",
                "ELAN_HOME": "/hostile/elan",
                "LAKE_HOME": "/hostile/lake",
                "LD_PRELOAD": "/hostile.so",
            }
            with mock.patch.dict(os.environ, hostile_env, clear=False):
                clean_env = verifier._scrubbed_lean_env()
                for hk in hostile_env:
                    self.assertNotIn(hk, clean_env)
                self.assertIn("PATH", clean_env)
            with mock.patch.dict(os.environ, {"LEAN_PATH": "/hostile"}, clear=True):
                self.assertEqual(verifier._scrubbed_lean_env(), {"PATH": "/usr/bin:/bin"})

            with mock.patch.object(verifier, "resolve_lean_binary", return_value="/bin/lean"):
                # 1-theorem clean check + verify scrubbed env passed to subprocess.run
                with mock.patch.dict(os.environ, hostile_env, clear=False):
                    with mock.patch("subprocess.run", return_value=_run_mock(0, "'A' does not depend on any axioms\n")) as m_run:
                        vr1 = verifier.verify_lean_proof(tiny_lean, enforce_sha256=False)
                        self.assertEqual(vr1["theorems_verified"], 1)
                        passed_env = m_run.call_args.kwargs.get("env")
                        self.assertIsNotNone(passed_env)
                        for hk in hostile_env:
                            self.assertNotIn(hk, passed_env)

                # Multiline propext + zero axiom
                with mock.patch("subprocess.run", return_value=_run_mock(0, "'A' does not depend on any axioms\n'B' depends on axioms: [\n  propext]\n")):
                    vr = verifier.verify_lean_proof(tiny_lean, enforce_sha256=False)
                    self.assertEqual(vr["theorems_verified"], 2)
                    self.assertEqual(vr["zero_axiom_theorems"], 1)
                    self.assertEqual(vr["axioms_used"], ["propext"])

                # Wrong theorem list under enforce_sha256=True
                tiny_sha = hashlib.sha256(tiny_lean.read_bytes()).hexdigest()
                with mock.patch.object(verifier, "EXPECTED_LEAN_SHA256", tiny_sha):
                    with mock.patch("subprocess.run", return_value=_run_mock(0, "'WrongThm' does not depend on any axioms\n")):
                        with self.assertRaisesRegex(ValueError, "^LEAN_THEOREM_LIST_MISMATCH$"):
                            verifier.verify_lean_proof(tiny_lean, enforce_sha256=True)

                # Failure cases with exact codes (incl. rc=1 with empty stderr & leading indented line!)
                for bad_proc, pat in (
                    (_run_mock(1, "", ""), "^LEAN_COMPILE_FAILED"),
                    (_run_mock(0, "'A' does not depend on any axioms\n", "warn"), "^LEAN_NONEMPTY_STDERR"),
                    (_run_mock(0, ""), "^LEAN_NO_THEOREMS_VERIFIED$"),
                    (_run_mock(0, "  indented_first_line\n"), "^LEAN_UNEXPECTED_STDOUT_LINE"),
                    (_run_mock(0, "unexpected line\n"), "^LEAN_UNEXPECTED_STDOUT_LINE"),
                    (_run_mock(0, "'A' does not depend on any axioms\n'A' does not depend on any axioms\n"), "^LEAN_DUPLICATE_THEOREM"),
                    (_run_mock(0, "'A' depends on axioms: [propext]\n'A' depends on axioms: [propext]\n"), "^LEAN_DUPLICATE_THEOREM"),
                    (_run_mock(0, "'A' depends on axioms: [Classical.choice]\n"), "^LEAN_FORBIDDEN_AXIOM"),
                    (_run_mock(0, "'A' depends on axioms: [sorryAx]\n"), "^LEAN_FORBIDDEN_AXIOM"),
                ):
                    with mock.patch("subprocess.run", return_value=bad_proc):
                        with self.assertRaisesRegex(ValueError, pat):
                            verifier.verify_lean_proof(tiny_lean, enforce_sha256=False)

        lean_path = _TRACK_DIR / oracle.LEAN_FILE_NAME
        try:
            _ = verifier.resolve_lean_binary()
            has_lean = True
        except ValueError:
            has_lean = False
        if has_lean:
            buf = io.BytesIO()
            with mock.patch.object(sys, "stdout", _fake_stdout(buf)):
                rc = verifier.main(["--verify-lean", str(lean_path), "--json"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["theorems_verified"], 18)
            self.assertEqual(payload["zero_axiom_theorems"], 1)
            self.assertEqual(payload["axioms_used"], ["propext"])
            self.assertEqual(payload["lean_sha256"], oracle.EXPECTED_LEAN_SHA256)

            # Live poisoned LEAN_PATH Init.olean hijack immunity
            lean_bin = verifier.resolve_lean_binary()
            with tempfile.TemporaryDirectory() as td_hij:
                hij_dir = Path(td_hij)
                (hij_dir / "Init.lean").write_text(
                    "prelude\ninductive HijackInit : Prop where | intro : HijackInit\ndef hijackTriv : HijackInit := HijackInit.intro\n",
                    encoding="utf-8",
                )
                r_init = verifier.subprocess.run(
                    [lean_bin, "-R", str(hij_dir), "-o", str(hij_dir / "Init.olean"), str(hij_dir / "Init.lean")],
                    capture_output=True,
                    text=True,
                    env=verifier._scrubbed_lean_env(),
                    check=False,
                )
                self.assertEqual(r_init.returncode, 0)
                fake_lean_f = hij_dir / "FakeS100.lean"
                fake_lean_f.write_text("theorem ok_t : HijackInit := hijackTriv\n#print axioms ok_t\n", encoding="utf-8")
                with mock.patch.dict(os.environ, {"LEAN_PATH": str(hij_dir)}, clear=False):
                    self.assertEqual(verifier.verify_lean_proof(lean_path, enforce_sha256=True)["theorems_verified"], 18)
                    with self.assertRaisesRegex(ValueError, "^LEAN_COMPILE_FAILED"):
                        verifier.verify_lean_proof(fake_lean_f, enforce_sha256=False)
        else:
            with self.assertRaisesRegex(ValueError, "^LEAN_BINARY_UNAVAILABLE$"):
                verifier.verify_lean_proof(lean_path, enforce_sha256=True)


if __name__ == "__main__":
    unittest.main()
