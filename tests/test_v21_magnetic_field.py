#!/usr/bin/env python3
"""
Assertion-Free R5 Unit, Zone-B Adversarial & Mutation-Isolation Suite for `aletheia.magnetic_field_v21`.

Zero bare `assert` statements (`100%` `python3 -O` parity). Covers strict Zone-B certificate I/O,
starvation-capped verifier routing, Law-1b omni-vein solenoidal field-coupling dispatch,
Gate-8 pre-registration timestamp ordering, and the 7-gate deterministic pre-push hygiene bundle.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import redirect_stderr, redirect_stdout
import ctypes
from fractions import Fraction
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

CLI_ROOT = Path(__file__).resolve().parent.parent
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

from aletheia import magnetic_field_v21 as mf


class _EvilPath(type(Path())):
    pass


class _LyingSequence(Sequence):
    def __init__(self, items: list[int]) -> None:
        self._items = items

    def __len__(self) -> int:
        return 1

    def __getitem__(self, idx: int) -> int:
        return self._items[idx]

    def __iter__(self):
        return iter(self._items)


class _LyingMapping(Mapping):
    def __init__(self, data: dict[str, int]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> int:
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


class _IntSub(int):
    pass


class _ListSub(list):
    pass


class _DictSub(dict):
    pass


class _StrSub(str):
    pass


class TestStrictCertIO(unittest.TestCase):
    def test_is_symlink_at_returns_exact_bool(self) -> None:
        # R5 guard_except_reject: an OSError from lstat must yield exact False, not a falsy None.
        with tempfile.TemporaryDirectory() as td:
            Path(td, "reg").write_bytes(b"x")
            os.symlink("reg", os.path.join(td, "lnk"))
            dfd = os.open(td, os.O_RDONLY | os.O_DIRECTORY)
            try:
                self.assertIs(mf._is_symlink_at(dfd, "lnk"), True, "symlink -> True")
                self.assertIs(mf._is_symlink_at(dfd, "reg"), False, "regular file -> False")
                self.assertIs(mf._is_symlink_at(dfd, "missing"), False, "ENOENT -> exact False")
                self.assertIs(mf._is_symlink_at(dfd, "reg/child"), False, "ENOTDIR -> exact False")
            finally:
                os.close(dfd)

    def test_primitives_and_zero_fstring_int_dos(self) -> None:
        max_2048 = (1 << mf.MAX_INT_BITS) - 1
        over_2048 = 1 << mf.MAX_INT_BITS
        self.assertEqual(mf.require_int(max_2048, "m"), max_2048)
        self.assertEqual(mf.require_int(-max_2048, "m"), -max_2048)
        self.assertEqual(mf.require_int(3, "x", lo=3, hi=7), 3)
        self.assertEqual(mf.require_int(7, "x", lo=3, hi=7), 7)

        for bad in (True, False, _IntSub(1), json.loads("1.0"), "1", None):
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.require_int(bad, "x")
            self.assertEqual(cm.exception.code, "INVALID_INT_TYPE")

        for huge in (over_2048, -over_2048, 10**5000, -(10**5000)):
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.require_int(huge, "huge", lo=0, hi=10)
            self.assertEqual(cm.exception.code, "INT_BIT_LIMIT")
            self.assertIn("bit_length=", str(cm.exception))

        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.require_int(2, "x", lo=3, hi=7)
        self.assertEqual(cm.exception.code, "INT_BELOW_MIN")
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.require_int(1, "x", lo=10**5000)
        self.assertEqual(cm.exception.code, "INT_BELOW_MIN")
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.require_int(8, "x", lo=3, hi=7)
        self.assertEqual(cm.exception.code, "INT_ABOVE_MAX")
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.require_int(1, "x", hi=-(10**5000))
        self.assertEqual(cm.exception.code, "INT_ABOVE_MAX")

        self.assertIs(mf.require_bool(True, "b"), True)
        self.assertIs(mf.require_bool(False, "b"), False)
        for bad in (0, 1, "true", None):
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.require_bool(bad, "b")
            self.assertEqual(cm.exception.code, "INVALID_BOOL_TYPE")

        self.assertEqual(mf.require_str("a", "s", min_len=1, max_len=3), "a")
        self.assertEqual(mf.require_str("abc", "s", min_len=1, max_len=3), "abc")
        for bad in (_StrSub("a"), 1, None, b"a"):
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.require_str(bad, "s")
            self.assertEqual(cm.exception.code, "INVALID_STR_TYPE")
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.require_str("", "s", min_len=1, max_len=3)
        self.assertEqual(cm.exception.code, "STR_TOO_SHORT")
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.require_str("abcd", "s", min_len=1, max_len=3)
        self.assertEqual(cm.exception.code, "STR_TOO_LONG")
        for bad_sur in (chr(0xD800), chr(0xDC00)):
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.require_str(bad_sur, "s")
            self.assertEqual(cm.exception.code, "INVALID_UTF8")
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.require_mapping({bad_sur: 1}, "m")
            self.assertEqual(cm.exception.code, "INVALID_UTF8")

        self.assertEqual(mf.require_seq([1], "q", min_len=1, max_len=2), (1,))
        self.assertEqual(mf.require_seq((1, 2), "q", min_len=1, max_len=2), (1, 2))
        for bad in (_LyingSequence([1, 2, 3]), _ListSub([1]), "ab", {1: 2}, None):
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.require_seq(bad, "q", min_len=1, max_len=3)
            self.assertEqual(cm.exception.code, "INVALID_SEQ_TYPE")
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.require_seq([], "q", min_len=1, max_len=2)
        self.assertEqual(cm.exception.code, "SEQ_TOO_SHORT")
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.require_seq([1, 2, 3], "q", min_len=1, max_len=2)
        self.assertEqual(cm.exception.code, "SEQ_TOO_LONG")

        self.assertEqual(mf.require_mapping({"a": 1}, "m"), {"a": 1})
        for bad in (_LyingMapping({"a": 1}), _DictSub({"a": 1}), [], None):
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.require_mapping(bad, "m")
            self.assertEqual(cm.exception.code, "INVALID_MAPPING_TYPE")
        for bad_k in ({1: "a"}, {True: "a"}, {_StrSub("a"): 1}):
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.require_mapping(bad_k, "m")
            self.assertEqual(cm.exception.code, "NON_STR_KEY")

        good = "0123456789abcdef" * 4
        other = "fedcba9876543210" * 4
        self.assertTrue(mf.constant_time_hex64_equal(good, good))
        self.assertFalse(mf.constant_time_hex64_equal(good, other))
        for bad_t in (123, None, _StrSub(good), b"a" * 64):
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.require_hex64_ascii(bad_t)
            self.assertEqual(cm.exception.code, "INVALID_DIGEST_TYPE")
        for bad_len in ("a" * 63, "a" * 65, ""):
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.require_hex64_ascii(bad_len)
            self.assertEqual(cm.exception.code, "INVALID_DIGEST_LEN")
        for bad_hex in ("\u00e9" * 64, chr(0xD800) * 64, "A" * 64, "g" * 64):
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.constant_time_hex64_equal(bad_hex, good)
            self.assertEqual(cm.exception.code, "INVALID_DIGEST_HEX")

        self.assertEqual(mf.fmt_q(Fraction(6, 3)), "2")
        self.assertEqual(mf.fmt_q(Fraction(5, 7)), "5/7")
        self.assertEqual(mf.fmt_q(Fraction(max_2048, 1)), str(max_2048))
        self.assertEqual(mf.fmt_q(Fraction(1, max_2048)), f"1/{max_2048}")
        for huge_q in (
            Fraction(over_2048, 1),
            Fraction(1, over_2048),
            Fraction(10**5000, 1),
            Fraction(1, 10**5000),
        ):
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.fmt_q(huge_q)
            self.assertEqual(cm.exception.code, "FRACTION_BIT_LIMIT")
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.fmt_q(1)  # type: ignore[arg-type]
        self.assertEqual(cm.exception.code, "INVALID_FRACTION_TYPE")
        self.assertEqual(mf.ratio_q(4, 8), Fraction(1, 2))
        with self.assertRaises(mf.MagneticFieldError):
            mf.ratio_q(1, 0)

    def test_json_parser_validator_and_file_loaders(self) -> None:
        exact64: object = 0
        for _ in range(mf.MAX_JSON_DEPTH):
            exact64 = [exact64]
        mf.validate_json_value(exact64)
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.validate_json_value([exact64])
        self.assertEqual(cm.exception.code, "MAX_DEPTH_EXCEEDED")

        cyc: list[object] = []
        cyc.append(cyc)
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.validate_json_value(cyc)
        self.assertEqual(cm.exception.code, "MAX_DEPTH_EXCEEDED")

        max_2048 = (1 << mf.MAX_INT_BITS) - 1
        over_2048 = 1 << mf.MAX_INT_BITS
        mf.validate_json_value({"n": max_2048, "m": -max_2048})
        self.assertEqual(mf._parse_capped_int_token(str(max_2048)), max_2048)
        self.assertEqual(mf._parse_capped_int_token("-" + str(max_2048)), -max_2048)
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf._parse_capped_int_token(str(over_2048))
        self.assertEqual(cm.exception.code, "INT_BIT_LIMIT")

        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.parse_strict_json_text('{"n":' + ("1" + "0" * (mf.MAX_INT_DIGITS - 1)) + "}")
        self.assertEqual(cm.exception.code, "INT_BIT_LIMIT")
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.parse_strict_json_text('{"n":' + ("9" * (mf.MAX_INT_DIGITS + 1)) + "}")
        self.assertEqual(cm.exception.code, "INT_DIGIT_LIMIT")

        for bad_obj, code in (
            ({1: "a"}, "NON_STR_KEY"),
            ({"x": json.loads("1.5")}, "FLOAT_FORBIDDEN"),
            ({"x": _IntSub(1)}, "UNSUPPORTED_JSON_TYPE"),
            ({"x": (1, 2)}, "UNSUPPORTED_JSON_TYPE"),
            ({"x": over_2048}, "INT_BIT_LIMIT"),
            ({"x": 10**5000}, "INT_BIT_LIMIT"),
            ({"x": chr(0xD800)}, "INVALID_UTF8"),
            ({"x": chr(0xDC00)}, "INVALID_UTF8"),
            ({chr(0xD800): 1}, "INVALID_UTF8"),
        ):
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.validate_json_value(bad_obj)
            self.assertEqual(cm.exception.code, code)
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.canonical_json_bytes({"x": chr(0xD800)})
        self.assertEqual(cm.exception.code, "INVALID_UTF8")

        for bad_txt, code in (
            ('{"x":1.2}', "JSON_FLOAT_FORBIDDEN"),
            ('{"x":NaN}', "JSON_CONSTANT_FORBIDDEN"),
            ('{"a":1,"a":2}', "JSON_DUPLICATE_KEY"),
            ("", "EMPTY_JSON_INPUT"),
            ("   \n", "EMPTY_JSON_INPUT"),
            ("{bad", "JSON_SYNTAX_ERROR"),
            ('{"s":"' + chr(0xD800) + '"}', "INVALID_UTF8"),
            ('{"x":"\\ud800"}', "INVALID_UTF8"),
            ('{"x":"\\udc00"}', "INVALID_UTF8"),
            ('{"\\ud800":1}', "INVALID_UTF8"),
            ("[1,2]", "JSON_ROOT_NOT_OBJECT"),
        ):
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.parse_strict_json_text(bad_txt, require_object=True)
            self.assertEqual(cm.exception.code, code)

        self.assertEqual(mf.loads_strict_json("[1,2]", require_object=False), [1, 2])
        self.assertEqual(mf.parse_strict_json_text('{"a":null,"b":true}', require_object=True)["a"], None)

        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.parse_strict_json_text(b"{}")  # type: ignore[arg-type]
        self.assertEqual(cm.exception.code, "INVALID_JSON_INPUT")

        exact_cap = '{"s":"' + ("a" * (mf.MAX_JSON_BYTES - 8)) + '"}'
        self.assertIn("s", mf.parse_strict_json_text(exact_cap))
        over_cap = '{"s":"' + ("a" * (mf.MAX_JSON_BYTES - 7)) + '"}'
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.parse_strict_json_text(over_cap)
        self.assertEqual(cm.exception.code, "JSON_TOO_LARGE")

        for bad_p in ("not_a_path", _EvilPath("x.json")):
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.require_no_symlink_path(bad_p)  # type: ignore[arg-type]
            self.assertEqual(cm.exception.code, "INVALID_PATH_TYPE")
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.require_no_symlink_path(Path("bad\x00path.json"))
        self.assertEqual(cm.exception.code, "INVALID_PATH_NUL")
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.require_no_symlink_path(Path("bad" + chr(0xD800) + ".json"))
        self.assertEqual(cm.exception.code, "INVALID_UTF8")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cert_obj = {"audit_id": "TEST", "payload": {"k": 1}}
            payload_sha = mf.canonical_sha256(cert_obj["payload"])
            raw_cert = mf.canonical_json_bytes(cert_obj)

            cfile = root / "cert.json"
            cfile.write_bytes(raw_cert + b"\n")
            self.assertEqual(mf.load_strict_json_file(cfile)["audit_id"], "TEST")
            ver = mf.verify_canonical_cert_file(cfile, expected_payload_sha256=payload_sha)
            self.assertTrue(ver["valid"])
            cfile_no_nl = root / "cert_nonl.json"
            cfile_no_nl.write_bytes(raw_cert)
            self.assertTrue(mf.verify_canonical_cert_file(cfile_no_nl)["valid"])

            no_pay = root / "nopay.json"
            no_pay.write_bytes(b'{"a":1}\n')
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.verify_canonical_cert_file(no_pay, expected_payload_sha256=payload_sha)
            self.assertEqual(cm.exception.code, "MISSING_PAYLOAD_KEY")

            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.verify_canonical_cert_file(cfile, expected_payload_sha256="0" * 64)
            self.assertEqual(cm.exception.code, "PAYLOAD_SHA_MISMATCH")

            noncan = root / "noncan.json"
            noncan.write_bytes(b'{"audit_id": "TEST", "payload": {"k": 1}}\n')
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.verify_canonical_cert_file(noncan)
            self.assertEqual(cm.exception.code, "NON_CANONICAL_CERT_BYTES")

            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.load_strict_json_file(root / "missing.json")
            self.assertEqual(cm.exception.code, "FILE_NOT_FOUND")

            sym = root / "sym.json"
            sym.symlink_to(cfile)
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.load_strict_json_file(sym)
            self.assertEqual(cm.exception.code, "SYMLINK_FORBIDDEN")

            sub = root / "sub"
            sub.mkdir()
            (sub / "c.json").write_bytes(raw_cert)
            symdir = root / "symdir"
            symdir.symlink_to(sub)
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.load_strict_json_file(symdir / "c.json")
            self.assertEqual(cm.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")

            exact_f = root / "exact_cap.json"
            exact_f.write_bytes(exact_cap.encode("ascii"))
            self.assertIn("s", mf.load_strict_json_file(exact_f))
            big_f = root / "big.json"
            big_f.write_bytes(b"a" * (mf.MAX_JSON_BYTES + 1))
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.load_strict_json_file(big_f)
            self.assertEqual(cm.exception.code, "FILE_TOO_LARGE")

            for fname, data, code in (
                ("bare_cr.json", b'{"a":1}\r', "CR_LINE_ENDINGS_FORBIDDEN"),
                ("crlf.json", b'{"a":1}\r\n', "CR_LINE_ENDINGS_FORBIDDEN"),
                ("bad_utf8.json", b"\xff\xfe", "INVALID_UTF8"),
            ):
                p = root / fname
                p.write_bytes(data)
                with self.assertRaises(mf.MagneticFieldError) as cm:
                    mf.load_strict_json_file(p)
                self.assertEqual(cm.exception.code, code)

            empty_l = root / "empty.jsonl"
            empty_l.write_bytes(b"")
            self.assertEqual(mf.load_strict_jsonl_file(empty_l), [])

            ok_l = root / "ok.jsonl"
            ok_l.write_bytes(b'{"a":1}\n{"b":2}\n')
            self.assertEqual(len(mf.load_strict_jsonl_file(ok_l)), 2)

            ws_l = root / "ws.jsonl"
            ws_l.write_bytes(b"   \n  ")
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.load_strict_jsonl_file(ws_l)
            self.assertEqual(cm.exception.code, "JSONL_WHITESPACE_ONLY")

            blank_l = root / "blank.jsonl"
            blank_l.write_bytes(b'{"a":1}\n\n{"b":2}\n')
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.load_strict_jsonl_file(blank_l)
            self.assertEqual(cm.exception.code, "JSONL_BLANK_LINE")

            # F6: LF-only splitting preserves Unicode line separators inside JSON strings
            u2028_l = root / "u2028.jsonl"
            u2028_l.write_bytes(('{"a":"x\u2028y"}\n').encode("utf-8"))
            self.assertEqual(mf.load_strict_jsonl_file(u2028_l), [{"a": "x\u2028y"}])
            trail_blank = root / "trail_blank.jsonl"
            trail_blank.write_bytes(b'{"a":1}\n\n')
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.load_strict_jsonl_file(trail_blank)
            self.assertEqual(cm.exception.code, "JSONL_BLANK_LINE")


class TestRouterCouplingAndGate8(unittest.TestCase):
    def test_routing_boundaries_and_errors(self) -> None:
        v_list = [
            {"verifier_id": "verifier-a", "queue_depth": 2, "max_concurrent": 1},
            {"verifier_id": "verifier-b", "queue_depth": 1, "max_concurrent": 1},
        ]
        r_none = mf.route_verification_task(v_list, oldest_wait_s=1800, starvation_cap_s=1800)
        self.assertEqual(r_none["target"], "verifier-b")
        self.assertFalse(r_none["starvation_triggered"])
        self.assertEqual(r_none["reason"], "LEAST_LOAD")

        r_none_starve = mf.route_verification_task(v_list, oldest_wait_s=1801, starvation_cap_s=1800)
        self.assertTrue(r_none_starve["starvation_triggered"])
        self.assertEqual(r_none_starve["reason"], "STARVATION_PREEMPT")

        eq_list = [
            {"verifier_id": "verifier-a", "queue_depth": 2, "max_concurrent": 2},
            {"verifier_id": "verifier-b", "queue_depth": 1, "max_concurrent": 1},
        ]
        r_pref_eq = mf.route_verification_task(eq_list, preferred_verifier="verifier-a", oldest_wait_s=100)
        self.assertEqual(r_pref_eq["target"], "verifier-a")
        self.assertEqual(r_pref_eq["reason"], "PREFERRED_BALANCED")

        r_rebal = mf.route_verification_task(v_list, preferred_verifier="verifier-a", oldest_wait_s=100)
        self.assertEqual(r_rebal["target"], "verifier-b")
        self.assertEqual(r_rebal["reason"], "LOAD_REBALANCE")

        r_starve = mf.route_verification_task(eq_list, preferred_verifier="verifier-a", oldest_wait_s=1801)
        self.assertEqual(r_starve["target"], "verifier-b")
        self.assertEqual(r_starve["reason"], "STARVATION_REROUTE")
        self.assertTrue(r_starve["starvation_triggered"])

        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.route_verification_task([v_list[0], v_list[0]])
        self.assertEqual(cm.exception.code, "DUPLICATE_VERIFIER_ID")

        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.route_verification_task(v_list, preferred_verifier="ghost")
        self.assertEqual(cm.exception.code, "UNKNOWN_PREFERRED_VERIFIER")

        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.route_verification_task([{"verifier_id": "v1", "queue_depth": 10**5000}, v_list[1]])
        self.assertEqual(cm.exception.code, "INT_BIT_LIMIT")

    def test_omni_vein_field_coupling_cadence_and_gate8(self) -> None:
        res = mf.compute_field_coupling_dispatch(
            "DEF-12", "vein-a", ["vein-a", "vein-b", "vein-c"], ["vein-a"]
        )
        self.assertEqual(res["dispatch_target_veins"], ["vein-b", "vein-c"])
        self.assertEqual(res["uncovered_veins"], [])
        self.assertTrue(res["zero_sink_conserved"])

        # Independent dispatched_veins conservation check (complete vs siloed/incomplete)
        res_full = mf.compute_field_coupling_dispatch(
            "DEF-12", "vein-a", ["vein-a", "vein-b", "vein-c"], ["vein-a"], dispatched_veins=["vein-b", "vein-c"]
        )
        self.assertTrue(res_full["zero_sink_conserved"])
        self.assertEqual(res_full["uncovered_veins"], [])
        self.assertEqual(res_full["post_coupling_coverage_q"], "1")

        res_silo = mf.compute_field_coupling_dispatch(
            "DEF-12", "vein-a", ["vein-a", "vein-b", "vein-c"], ["vein-a"], dispatched_veins=["vein-b"]
        )
        self.assertFalse(res_silo["zero_sink_conserved"])
        self.assertEqual(res_silo["uncovered_veins"], ["vein-c"])
        self.assertEqual(res_silo["post_coupling_coverage_q"], "2/3")

        for kwargs, code in (
            ({"active_veins": ["a", "a"], "source_vein": "a"}, "DUPLICATE_ACTIVE_VEIN"),
            ({"active_veins": ["a", "b"], "source_vein": "z"}, "UNKNOWN_SOURCE_VEIN"),
            ({"active_veins": ["a", "b"], "source_vein": "a", "already_hardened_veins": ["a", "a"]}, "DUPLICATE_HARDENED_VEIN"),
            ({"active_veins": ["a", "b"], "source_vein": "a", "already_hardened_veins": ["z"]}, "UNKNOWN_HARDENED_VEIN"),
            ({"active_veins": ["a", "b"], "source_vein": "a", "dispatched_veins": ["b", "b"]}, "DUPLICATE_DISPATCHED_VEIN"),
            ({"active_veins": ["a", "b"], "source_vein": "a", "dispatched_veins": ["z"]}, "UNKNOWN_DISPATCHED_VEIN"),
        ):
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.compute_field_coupling_dispatch("SIG", **kwargs)
            self.assertEqual(cm.exception.code, code)

        self.assertTrue(mf.evaluate_monitor_cadence(25, 1, 10, 100)["efficient"])
        self.assertEqual(mf.evaluate_monitor_cadence(25, 1, 100, 100)["drag_flags"], ["COORDINATOR_PR_POLL_DRAG"])
        r_tpp = mf.evaluate_monitor_cadence(26, 1, 10, 100)
        self.assertEqual(r_tpp["drag_flags"], ["MONITOR_SERIAL_POLL_DRAG"])
        r_poll = mf.evaluate_monitor_cadence(25, 1, 11, 100)
        self.assertEqual(r_poll["drag_flags"], ["COORDINATOR_PR_POLL_DRAG"])
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.evaluate_monitor_cadence(10, 1, 101, 100)
        self.assertEqual(cm.exception.code, "POLL_TASKS_EXCEED_TOTAL")

        # Gate-8 pre-registration timestamp ordering exact boundaries
        g8_eq = mf.verify_gate8_prereg_order(1000, 1060, min_lead_s=60)
        self.assertTrue(g8_eq["passed"])
        self.assertEqual(g8_eq["verdict"], "PREREGISTERED_PRIOR")
        self.assertEqual(g8_eq["lead_s"], 60)

        g8_short = mf.verify_gate8_prereg_order(1000, 1059, min_lead_s=60)
        self.assertFalse(g8_short["passed"])
        self.assertEqual(g8_short["verdict"], "POST_HOC_OR_INSUFFICIENT_LEAD")

        g8_post = mf.verify_gate8_prereg_order(1001, 1000)
        self.assertFalse(g8_post["passed"])
        self.assertEqual(g8_post["lead_s"], -1)

        # F3: strict obs > pre even when min_lead_s=0 (equal timestamps MUST fail)
        g8_tie = mf.verify_gate8_prereg_order(100, 100, min_lead_s=0)
        self.assertFalse(g8_tie["passed"])
        self.assertEqual(g8_tie["verdict"], "POST_HOC_OR_INSUFFICIENT_LEAD")
        g8_one = mf.verify_gate8_prereg_order(100, 101, min_lead_s=0)
        self.assertTrue(g8_one["passed"])
        self.assertEqual(g8_one["verdict"], "PREREGISTERED_PRIOR")

        for bad in ((-1, 10, 0), (10, -1, 0), (10, 20, -1), (True, 10, 0), (10**5000, 10, 0)):
            with self.assertRaises(mf.MagneticFieldError):
                mf.verify_gate8_prereg_order(bad[0], bad[1], min_lead_s=bad[2])  # type: ignore[arg-type]


class TestPrePushGateAndCLI(unittest.TestCase):
    def test_all_gates_boundaries_hygiene_and_cli(self) -> None:
        self.assertTrue(mf.check_dco_signoff("feat: x\n\nSigned-off-by: Ada Lovelace <ada@example.org>\n"))
        for bad_dco in (
            "feat: x\nSigned-off-by: no-email-here",
            "Ada Lovelace <ada@example.org>",
            "XXXXXXXXXXXXXX Ada <ada@example.org>",
            "Signed-off-by: Ada <ada@example.orgX",
            "Signed-off-by:<ada@example.org>",
            "Signed-off-by:Ada <ada@example.org>",
            "Signed-off-by: Ada<ada@example.org>",
            "Signed-off-by:   <ada@example.org>",
            "Signed-off-by: Ada <a b@example.org>",
            "Signed-off-by: Ada <a<b@example.org>",
            "Signed-off-by: Ada <a@b>c.org>",
            "Signed-off-by: Ada <a@b.c@d>",
            "Signed-off-by: Ada <@example.org>",
            "Signed-off-by: Ada <ada@localhost>",
            "Signed-off-by: Ada <ada@.org>",
            "Signed-off-by: Ada <ada@example.>",
        ):
            self.assertFalse(mf.check_dco_signoff(bad_dco), f"should reject bad DCO {bad_dco!r}")
        # F2: O(n) ReDoS resistance on 64 KB pathological DCO line (was 84.11 s under regex)
        t0 = time.monotonic()
        self.assertFalse(mf.check_dco_signoff("Signed-off-by: " + ("a " * 32000)))
        self.assertTrue(mf.check_dco_signoff("Signed-off-by: " + ("a " * 32000) + "<a@b.c>"))
        self.assertLess(time.monotonic() - t0, 1)

        self.assertTrue(mf.check_repo_visibility(False, False))
        self.assertTrue(mf.check_repo_visibility(True, True))
        self.assertFalse(mf.check_repo_visibility(True, False))

        self.assertTrue(mf.check_graphql_file_completeness(100, 100))
        self.assertFalse(mf.check_graphql_file_completeness(101, 100))

        self.assertTrue(mf.check_openblas_pin(1))
        self.assertFalse(mf.check_openblas_pin(0))
        self.assertFalse(mf.check_openblas_pin(8))

        self.assertTrue(mf.check_pr_review_action(False, "APPROVE"))
        self.assertTrue(mf.check_pr_review_action(True, "COMMENT"))
        self.assertFalse(mf.check_pr_review_action(True, "APPROVE"))
        self.assertFalse(mf.check_pr_review_action(True, "REQUEST_CHANGES"))
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.check_pr_review_action(False, "BOGUS")
        self.assertEqual(cm.exception.code, "INVALID_REVIEW_ACTION")

        self.assertEqual(mf.check_gitignore_receipt_integrity(["a.log", "b.json"], ["a.log", "b.json"]), [])
        self.assertEqual(mf.check_gitignore_receipt_integrity(["a.log", "b.json"], ["b.json"]), ["a.log"])

        self.assertEqual(mf.check_text_hygiene("clean text\n"), [])
        home_sample = "path " + chr(47) + "ho" + "me" + chr(47) + "alice/x"
        self.assertEqual(mf.check_text_hygiene(home_sample), ["PERSONAL_UNIX_HOME_PATH"])
        pat_sample = "tok=" + "gh" + "p_" + ("A" * 24)
        self.assertEqual(mf.check_text_hygiene(pat_sample), ["CREDENTIAL_GH_PAT"])
        coauth_sample = "Co-" + "Authored-By: Bot <bot@example.org>"
        self.assertEqual(mf.check_text_hygiene(coauth_sample), ["CO_AUTHORED_BY_TRAILER"])
        self.assertEqual(mf.check_text_hygiene("line1\rline2"), ["CR_LINE_ENDINGS_FORBIDDEN"])

        clean_bundle = {
            "commit_message": "fix: ok\n\nSigned-off-by: Dev <dev@example.org>\n",
            "repo_is_private": False,
            "explicit_private_allowed": False,
            "git_changed_files": 2,
            "graphql_files_listed": 2,
            "openblas_num_threads": 1,
            "pr_is_self_authored": False,
            "review_action": "COMMENT",
            "manifest_files": ["a.json"],
            "git_tracked_files": ["a.json"],
            "staged_text": "clean\n",
        }
        self.assertTrue(mf.evaluate_pre_push_bundle(clean_bundle)["passed"])

        for field, val, expected_code in (
            ("commit_message", "no trailer", "MISSING_DCO_SIGNOFF"),
            ("repo_is_private", True, "PRIVATE_REPO_BLOCKED"),
            ("git_changed_files", 3, "GRAPHQL_100_FILE_TRUNCATION"),
            ("openblas_num_threads", 4, "OPENBLAS_THREADS_UNPINNED"),
            ("pr_is_self_authored", True, None),
        ):
            mod_b = dict(clean_bundle)
            mod_b[field] = val
            res = mf.evaluate_pre_push_bundle(mod_b)
            if expected_code is None:
                self.assertTrue(res["passed"])
            else:
                self.assertEqual(res["violations"], [expected_code])

        mod_422 = dict(clean_bundle, pr_is_self_authored=True, review_action="APPROVE")
        self.assertEqual(mf.evaluate_pre_push_bundle(mod_422)["violations"], ["SELF_AUTHORED_REVIEW_422"])

        mod_drop = dict(clean_bundle, manifest_files=["a.json", "dropped.log"])
        self.assertEqual(mf.evaluate_pre_push_bundle(mod_drop)["violations"], ["GITIGNORE_DROPPED_MANIFEST_FILES"])

        mod_hyg = dict(clean_bundle, staged_text="bad\r\n")
        self.assertEqual(mf.evaluate_pre_push_bundle(mod_hyg)["violations"], ["CR_LINE_ENDINGS_FORBIDDEN"])

        # Strict key-set enforcement: unknown/typo keys and missing required staged_text fail closed.
        typo_bundle = dict(clean_bundle)
        typo_bundle.pop("staged_text")
        typo_bundle["staged_diff"] = "leaked"
        with self.assertRaises(mf.MagneticFieldError) as cm_u:
            mf.evaluate_pre_push_bundle(typo_bundle)
        self.assertEqual(cm_u.exception.code, "UNKNOWN_BUNDLE_KEYS")

        missing_staged = dict(clean_bundle)
        missing_staged.pop("staged_text")
        with self.assertRaises(mf.MagneticFieldError) as cm_m:
            mf.evaluate_pre_push_bundle(missing_staged)
        self.assertEqual(cm_m.exception.code, "MISSING_BUNDLE_KEYS")

        # --self-test exits non-zero (rc=2) when all_passed is False (both plain and --json).
        with mock.patch.object(mf, "check_openblas_pin", return_value=True):
            out_fail = io.StringIO()
            with redirect_stdout(out_fail):
                self.assertEqual(mf.main(["--self-test"]), 2)
            self.assertIn("FAIL magnetic_field_v21 all_passed=False", out_fail.getvalue())

            out_fail_j = io.StringIO()
            with redirect_stdout(out_fail_j):
                self.assertEqual(mf.main(["--self-test", "--json"]), 2)
            self.assertFalse(json.loads(out_fail_j.getvalue())["all_passed"])

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ok_p = root / "ok.json"
            ok_p.write_bytes(mf.canonical_json_bytes(clean_bundle) + b"\n")
            out_buf = io.StringIO()
            with redirect_stdout(out_buf):
                self.assertEqual(mf.main(["--check-bundle", str(ok_p)]), 0)
            self.assertIn("PASS magnetic_field_v21", out_buf.getvalue())

            bad_p = root / "bad.json"
            bad_p.write_bytes(mf.canonical_json_bytes(mod_drop) + b"\n")
            out_buf = io.StringIO()
            with redirect_stdout(out_buf):
                self.assertEqual(mf.main(["--check-bundle", str(bad_p), "--json"]), 2)
            self.assertFalse(json.loads(out_buf.getvalue())["passed"])

            err_buf = io.StringIO()
            with redirect_stderr(err_buf):
                self.assertEqual(mf.main(["--check-bundle", str(root / "nope.json")]), 2)
            self.assertIn("REJECT FILE_NOT_FOUND", err_buf.getvalue())

        out_buf = io.StringIO()
        with redirect_stdout(out_buf):
            self.assertEqual(mf.main([]), 0)
        self.assertIn("OK magnetic_field_v21", out_buf.getvalue())

        json_buf = io.StringIO()
        with redirect_stdout(json_buf):
            self.assertEqual(mf.main(["--self-test", "--json"]), 0)
        parsed = json.loads(json_buf.getvalue())
        self.assertTrue(parsed["all_passed"])
        self.assertEqual(parsed["strict_io"]["vectors_blocked"], 14)

    def test_r3_atomic_dirfd_streaming_renameat2_dco_and_guards(self) -> None:
        # Typed INVALID_BOUND_TYPE on require_int lo/hi & INVALID_BOOL_TYPE on require_object
        for bad_b in (True, "1", _IntSub(1)):
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.require_int(5, "x", lo=bad_b)  # type: ignore[arg-type]
            self.assertEqual(cm.exception.code, "INVALID_BOUND_TYPE")
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.require_int(5, "x", hi=bad_b)  # type: ignore[arg-type]
            self.assertEqual(cm.exception.code, "INVALID_BOUND_TYPE")
        with self.assertRaises(mf.MagneticFieldError) as cm:
            mf.parse_strict_json_text("{}", require_object=1)  # type: ignore[arg-type]
        self.assertEqual(cm.exception.code, "INVALID_BOOL_TYPE")

        # Reject angle brackets in DCO author name
        for bad_dco in (
            "Signed-off-by: Alice <evil> <a@b.c>",
            "Signed-off-by: Alice <evil <a@b.c>",
            "Signed-off-by: Alice >evil <a@b.c>",
        ):
            self.assertFalse(mf.check_dco_signoff(bad_dco))

        with tempfile.TemporaryDirectory(prefix="mf_r3_io_") as td:
            root = Path(td)
            real_dir = root / "real"
            real_dir.mkdir()
            bundle = {
                "commit_message": "fix: ok\n\nSigned-off-by: Dev <dev@example.org>\n",
                "repo_is_private": False,
                "explicit_private_allowed": False,
                "git_changed_files": 2,
                "graphql_files_listed": 2,
                "openblas_num_threads": 1,
                "pr_is_self_authored": False,
                "review_action": "COMMENT",
                "manifest_files": ["a.json"],
                "git_tracked_files": ["a.json"],
                "staged_text": "clean\n",
            }
            good_f = real_dir / "bundle.json"
            good_f.write_bytes(mf.canonical_json_bytes(bundle) + b"\n")
            sym_dir = root / "sym_dir"
            sym_dir.symlink_to(real_dir)
            sym_f = root / "sym_f.json"
            sym_f.symlink_to(good_f)

            # require_no_symlink_path edge cases & $PWD checks
            mf.require_no_symlink_path(Path("/"))
            mf.require_no_symlink_path(root / "no_dir" / "x.json")
            mf.require_no_symlink_path(root / "missing.json")
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.require_no_symlink_path(sym_f)
            self.assertEqual(cm.exception.code, "SYMLINK_FORBIDDEN")
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.require_no_symlink_path(sym_dir / "bundle.json")
            self.assertEqual(cm.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")

            orig_cwd = os.getcwd()
            try:
                os.chdir(real_dir)
                with mock.patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("PWD", None)
                    mf.require_no_symlink_path(Path("."))
                    mf.require_no_symlink_path(Path("bundle.json"))
                    self.assertEqual(mf.load_strict_json_file(Path("bundle.json"))["git_changed_files"], 2)
                with mock.patch.dict(os.environ, {"PWD": "rel_" + chr(0xDC80)}):
                    mf.require_no_symlink_path(Path("bundle.json"))
                with mock.patch.dict(os.environ, {"PWD": "/tmp/" + chr(0xDC80)}):
                    with self.assertRaises(mf.MagneticFieldError) as cm:
                        mf.require_no_symlink_path(Path("bundle.json"))
                    self.assertEqual(cm.exception.code, "INVALID_UTF8")
                with mock.patch.dict(os.environ, {"PWD": str(root / "missing_pwd")}):
                    mf.require_no_symlink_path(Path("bundle.json"))
                with mock.patch.dict(os.environ, {"PWD": str(sym_dir)}):
                    with self.assertRaises(mf.MagneticFieldError) as cm:
                        mf.require_no_symlink_path(Path("bundle.json"))
                    self.assertEqual(cm.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")
                    with self.assertRaises(mf.MagneticFieldError) as cm:
                        mf.load_strict_json_file(Path("bundle.json"))
                    self.assertEqual(cm.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")
                    # Absolute path outside symlink MUST succeed even when $PWD is a symlink
                    mf.require_no_symlink_path(good_f)
                    self.assertEqual(mf.load_strict_json_file(good_f)["git_changed_files"], 2)
            finally:
                os.chdir(orig_cwd)

            # Live subprocess CLI check under symlink $PWD
            env_sym = dict(os.environ)
            env_sym["PWD"] = str(sym_dir)
            proc_rel = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    str(CLI_ROOT / "aletheia" / "magnetic_field_v21.py"),
                    "--check-bundle",
                    "bundle.json",
                ],
                cwd=str(real_dir),
                env=env_sym,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(proc_rel.returncode, 2)
            self.assertIn("SYMLINK_ANCESTOR_FORBIDDEN", proc_rel.stderr)
            proc_abs = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    str(CLI_ROOT / "aletheia" / "magnetic_field_v21.py"),
                    "--check-bundle",
                    str(good_f),
                ],
                cwd=str(real_dir),
                env=env_sym,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(proc_abs.returncode, 0)

            # _open_parent_dir_fd boundary & ancestor branches
            for bad_p, exp_code in (
                (Path("/"), "FILE_NOT_FOUND"),
                (real_dir / "..", "FILE_NOT_FOUND"),
                (root / "no_dir" / "x.json", "FILE_NOT_FOUND"),
                (good_f / "x.json", "FILE_NOT_FOUND"),
                (sym_dir / "bundle.json", "SYMLINK_ANCESTOR_FORBIDDEN"),
            ):
                with self.assertRaises(mf.MagneticFieldError) as cm:
                    mf._open_parent_dir_fd(bad_p)
                self.assertEqual(cm.exception.code, exp_code)

            # chmod 000 leaf & ancestor -> typed FILE_READ_ERROR (zero raw PermissionError)
            if os.geteuid() != 0:
                noperm_f = root / "noperm.json"
                noperm_f.write_bytes(b"{}\n")
                noperm_d = root / "noperm_dir"
                noperm_d.mkdir()
                os.chmod(noperm_f, 0o000)
                os.chmod(noperm_d, 0o000)
                try:
                    with self.assertRaises(mf.MagneticFieldError) as cm:
                        mf.load_strict_json_file(noperm_f)
                    self.assertEqual(cm.exception.code, "FILE_READ_ERROR")
                    with self.assertRaises(mf.MagneticFieldError) as cm:
                        mf.load_strict_json_file(noperm_d / "x.json")
                    self.assertEqual(cm.exception.code, "FILE_READ_ERROR")
                finally:
                    os.chmod(noperm_f, 0o600)
                    os.chmod(noperm_d, 0o700)

            # FIFO, directory leaf, os.read OSError, & /proc/kallsyms streaming cap
            fifo_p = root / "pipe.fifo"
            os.mkfifo(fifo_p)
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.load_strict_json_file(fifo_p)
            self.assertEqual(cm.exception.code, "FILE_NOT_FOUND")
            with self.assertRaises(mf.MagneticFieldError) as cm:
                mf.load_strict_json_file(real_dir)
            self.assertEqual(cm.exception.code, "FILE_NOT_FOUND")
            with mock.patch.object(mf.os, "read", side_effect=OSError("simulated EIO")):
                with self.assertRaises(mf.MagneticFieldError) as cm:
                    mf.load_strict_json_file(good_f)
                self.assertEqual(cm.exception.code, "FILE_READ_ERROR")
            kallsyms = Path("/proc/kallsyms")
            if kallsyms.exists():
                with mock.patch.object(mf, "MAX_JSON_BYTES", 1024):
                    with self.assertRaises(mf.MagneticFieldError) as cm:
                        mf.load_strict_json_file(kallsyms)
                    self.assertEqual(cm.exception.code, "FILE_TOO_LARGE")

            # Live renameat2(RENAME_EXCHANGE) TOCTOU race: 0 canary leaks
            canary_f = root / "canary.json"
            canary_f.write_bytes(b'{"canary":"TOP_CANARY_LEAK"}\n')
            victim_f = root / "victim.json"
            victim_f.write_bytes(b'{"pub":1}\n')
            bait_sym = root / "bait_sym.json"
            bait_sym.symlink_to(canary_f)
            stop_ev = threading.Event()
            swap_errs: list[str] = []
            arch = os.uname().machine
            sys_nr = 316 if arch == "x86_64" else 276
            libc = ctypes.CDLL(None, use_errno=True)

            def _swap() -> None:
                while not stop_ev.is_set():
                    rc = libc.syscall(sys_nr, -100, os.fsencode(victim_f), -100, os.fsencode(bait_sym), 2)
                    if rc != 0:
                        swap_errs.append(str(ctypes.get_errno()))
                        break

            th = threading.Thread(target=_swap)
            th.start()
            leaks = 0
            try:
                for _ in range(300):
                    try:
                        obj = mf.load_strict_json_file(victim_f)
                        if "canary" in obj:
                            leaks += 1
                    except mf.MagneticFieldError as exc:
                        self.assertEqual(exc.code, "SYMLINK_FORBIDDEN")
            finally:
                stop_ev.set()
                th.join(timeout=10)
            self.assertEqual(swap_errs, [])
            self.assertEqual(leaks, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
