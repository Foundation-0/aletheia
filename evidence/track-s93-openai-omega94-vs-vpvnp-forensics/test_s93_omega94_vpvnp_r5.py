#!/usr/bin/env python3
"""Track S93: Assertion-Free R5 Verification, Adversarial Re-Signed Tamper,
Zone-B I/O, R10+ Lean Escape (incl. end-anchored decide-native boolean exprs),
and Zero-Skip Dual-Environment Test Suite.
"""
from __future__ import annotations

import ast
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
import unittest
from unittest import mock

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import s93_omega94_vpvnp_oracle as oracle  # noqa: E402
import verify_s93_omega94_vpvnp as verifier  # noqa: E402


class Test01StaticHygiene(unittest.TestCase):
    def test_ast_and_text_hygiene(self) -> None:
        home_tok = b"/" + b"home/"
        devnull_tok = b"/" + b"dev/null"
        for name in ("s93_omega94_vpvnp_oracle.py", "verify_s93_omega94_vpvnp.py"):
            raw = (_THIS_DIR / name).read_bytes()
            self.assertNotIn(b"\r", raw)
            self.assertNotIn(home_tok, raw)
            self.assertNotIn(devnull_tok, raw)
            tree = ast.parse(raw.decode("utf-8"))
            for node in ast.walk(tree):
                self.assertFalse(isinstance(node, ast.Assert), f"bare assert in {name}")
                if isinstance(node, ast.Constant):
                    self.assertFalse(type(node.value) is float, f"float literal in {name}")
                if isinstance(node, ast.Name):
                    self.assertNotEqual(node.id, "float")
                if isinstance(node, ast.Attribute):
                    self.assertNotEqual(node.attr, "isdigit")
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotEqual(alias.name, "random")
                if isinstance(node, ast.ImportFrom):
                    self.assertNotEqual(node.module, "random")
        test_raw = (_THIS_DIR / "test_s93_omega94_vpvnp_r5.py").read_bytes()
        self.assertNotIn(b"\r", test_raw)
        self.assertNotIn(home_tok, test_raw)
        self.assertNotIn(devnull_tok, test_raw)
        for node in ast.walk(ast.parse(test_raw.decode("utf-8"))):
            self.assertFalse(isinstance(node, ast.Assert))

    def test_disk_certificate_canonical_zero_float(self) -> None:
        raw = (_THIS_DIR / "s93_omega94_vpvnp_certificate.json").read_bytes()
        cert = verifier.parse_strict_json_bytes(raw, "disk_cert", require_canonical=True)
        self.assertEqual(cert["track_id"], oracle.TRACK_ID)
        self.assertEqual(cert["payload"]["pinned_artifacts"]["lean_theorem_count"], 18)
        self.assertEqual(cert["payload"]["wave6_provenance"]["pinned_sources_count"], 12)


class Test02OraclePrimitivesAndPillars(unittest.TestCase):
    def _assert_s93(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S93Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_type_and_hex_guards(self) -> None:
        oracle.require_ok(True, "X", "x")
        self._assert_s93("X", oracle.require_ok, False, "X", "x")
        self._assert_s93("X", oracle.require_ok, 1, "X", "x")
        self.assertTrue(oracle.require_bool(True, "b"))
        self.assertFalse(oracle.require_bool(False, "b"))
        self._assert_s93("INVALID_BOOL", oracle.require_bool, 1, "b")
        self.assertEqual(oracle.require_exact_int(5, "n", lo=5, hi=5), 5)
        self._assert_s93("INVALID_INT", oracle.require_exact_int, True, "n")
        self._assert_s93("INT_OUT_OF_RANGE", oracle.require_exact_int, 4, "n", lo=5)
        self._assert_s93("INT_OUT_OF_RANGE", oracle.require_exact_int, 6, "n", hi=5)
        self.assertEqual(oracle.require_exact_str("ok", "s"), "ok")
        self._assert_s93("INVALID_STR", oracle.require_exact_str, 9, "s")
        good_hex = "0123456789abcdef" * 4
        self.assertEqual(oracle.require_hex64(good_hex, "h"), good_hex)
        self._assert_s93("INVALID_HEX64", oracle.require_hex64, "ab", "h")
        self._assert_s93("INVALID_HEX64", oracle.require_hex64, "A" * 64, "h")

    def test_validate_strict_json_tree_and_formatters(self) -> None:
        oracle.validate_strict_json_tree({"a": [1, "s", True, False, None, (1 << 2047)]})
        self._assert_s93("INT_BIT_LIMIT", oracle.validate_strict_json_tree, {"a": 1 << 2048})
        self._assert_s93("INVALID_JSON_KEY", oracle.validate_strict_json_tree, {1: "a"})
        self._assert_s93("FORBIDDEN_JSON_TYPE", oracle.validate_strict_json_tree, {"a": (1, 2)})
        self._assert_s93("FORBIDDEN_JSON_TYPE", oracle.validate_strict_json_tree, object())
        deep: dict = {}
        cur = deep
        for _ in range(34):
            nxt: dict = {}
            cur["k"] = nxt
            cur = nxt
        self._assert_s93("JSON_DEPTH_EXCEEDED", oracle.validate_strict_json_tree, deep)
        ok_deep: dict = {}
        cur2 = ok_deep
        for _ in range(32):
            nxt2: dict = {}
            cur2["k"] = nxt2
            cur2 = nxt2
        oracle.validate_strict_json_tree(ok_deep)

        self.assertEqual(oracle.fmt_q(Fraction(7, 1)), "7")
        self.assertEqual(oracle.fmt_q(Fraction(-3, 4)), "-3/4")
        self._assert_s93("INVALID_FRACTION", oracle.fmt_q, 7)

        self.assertEqual(oracle.fmt_dec_q(Fraction(1, 2), 0), "1")
        self.assertEqual(oracle.fmt_dec_q(Fraction(-1, 2), 0), "-1")
        self.assertEqual(oracle.fmt_dec_q(Fraction(-1, 100), 0), "0")
        self.assertEqual(oracle.fmt_dec_q(Fraction(0, 1), 0), "0")
        self.assertEqual(oracle.fmt_dec_q(Fraction(-1, 1000), 2), "0.00")
        self.assertEqual(oracle.fmt_dec_q(Fraction(-3, 4), 2), "-0.75")
        self.assertEqual(oracle.fmt_dec_q(Fraction(1, 8), 2), "0.13")
        self.assertEqual(oracle.fmt_dec_q(Fraction(1, 3), 4), "0.3333")
        self._assert_s93("INVALID_FRACTION", oracle.fmt_dec_q, 1, 2)
        self._assert_s93("INT_OUT_OF_RANGE", oracle.fmt_dec_q, Fraction(1, 2), -1)
        self._assert_s93("INT_OUT_OF_RANGE", oracle.fmt_dec_q, Fraction(1, 2), 19)

    def test_math_helpers_and_pillars(self) -> None:
        # openai_rectangular_omega boundaries & rejections
        self.assertEqual(oracle.openai_rectangular_omega(Fraction(1), Fraction(1), Fraction(1)), Fraction(9, 4))
        self.assertEqual(oracle.openai_rectangular_omega(Fraction(1), Fraction(1), Fraction(0)), Fraction(2))
        self.assertEqual(oracle.openai_rectangular_omega(Fraction(1), Fraction(1), Fraction(1, 2)), Fraction(2))
        self.assertEqual(oracle.openai_rectangular_omega(Fraction(1), Fraction(1), Fraction(2, 3)), Fraction(49, 24))
        self._assert_s93("INVALID_WEIGHTS", oracle.openai_rectangular_omega, Fraction(-1), Fraction(1), Fraction(1))
        self._assert_s93("INVALID_WEIGHTS", oracle.openai_rectangular_omega, Fraction(1), Fraction(-1), Fraction(1))
        self._assert_s93("INVALID_WEIGHTS", oracle.openai_rectangular_omega, Fraction(1), Fraction(1), Fraction(-1))

        # exact_det_q singular, pivot swap, and regular
        self.assertEqual(oracle.exact_det_q([[Fraction(0), Fraction(1)], [Fraction(1), Fraction(0)]]), Fraction(-1))
        self.assertEqual(oracle.exact_det_q([[Fraction(0), Fraction(0)], [Fraction(0), Fraction(1)]]), Fraction(0))
        self.assertEqual(oracle.exact_det_q([[Fraction(2), Fraction(1)], [Fraction(1), Fraction(2)]]), Fraction(3))

        # eval_trust_scorecard all 8 Boolean combinations
        for a in (False, True):
            for b in (False, True):
                for c in (False, True):
                    self.assertEqual(oracle.eval_trust_scorecard(a, b, c), a and b and c)
        self._assert_s93("INVALID_BOOL", oracle.eval_trust_scorecard, 1, True, True)

        # is_non_euclidean_blocked all 4 sign combos
        self.assertTrue(oracle.is_non_euclidean_blocked(Fraction(-1), Fraction(-1)))
        self.assertFalse(oracle.is_non_euclidean_blocked(Fraction(0), Fraction(-1)))
        self.assertFalse(oracle.is_non_euclidean_blocked(Fraction(-1), Fraction(0)))
        self.assertFalse(oracle.is_non_euclidean_blocked(Fraction(1), Fraction(1)))

        # c4_edge_fn & c4_biclique_fn exhaustive 16-input truth table
        expected_c4 = {
            0b0000: False, 0b0001: False, 0b0010: False, 0b0011: True,
            0b0100: False, 0b0101: False, 0b0110: True,  0b0111: True,
            0b1000: False, 0b1001: True,  0b1010: False, 0b1011: True,
            0b1100: True,  0b1101: True,  0b1110: True,  0b1111: True,
        }
        for mask, exp in expected_c4.items():
            x0, x1, x2, x3 = (bool((mask >> i) & 1) for i in range(4))
            self.assertEqual(oracle.c4_edge_fn(x0, x1, x2, x3), exp)
            self.assertEqual(oracle.c4_biclique_fn(x0, x1, x2, x3), exp)

        # is_three_of_four_funnel all discriminating combos
        self.assertTrue(oracle.is_three_of_four_funnel(0, 1, 1, 1))
        self.assertFalse(oracle.is_three_of_four_funnel(1, 1, 1, 1))
        self.assertFalse(oracle.is_three_of_four_funnel(0, 2, 1, 1))
        self.assertFalse(oracle.is_three_of_four_funnel(0, 1, 1, 2))
        self.assertFalse(oracle.is_three_of_four_funnel(0, 1, 2, 3))

        # Main oracle CLI stdout
        buf = io.StringIO()
        with mock.patch.object(sys, "stdout", buf):
            self.assertEqual(oracle.main(), 0)
        self.assertEqual(buf.getvalue().encode("ascii"), (_THIS_DIR / "s93_omega94_vpvnp_certificate.json").read_bytes())


class Test03ZoneBIOAndParsers(unittest.TestCase):
    def _assert_s93(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S93Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_path_and_darwin_normalization(self) -> None:
        self.assertEqual(verifier._normalize_darwin_private_prefix("/private/tmp"), "/tmp")
        self.assertEqual(verifier._normalize_darwin_private_prefix("/private/tmp/a"), "/tmp/a")
        self.assertEqual(verifier._normalize_darwin_private_prefix("/private/var"), "/var")
        self.assertEqual(verifier._normalize_darwin_private_prefix("/private/var/a"), "/var/a")
        self.assertEqual(verifier._normalize_darwin_private_prefix("/private/tmp2"), "/private/tmp2")
        self.assertEqual(verifier._normalize_darwin_private_prefix("/private/var2"), "/private/var2")
        self.assertEqual(verifier._normalize_darwin_private_prefix("/tmp/x"), "/tmp/x")

        self.assertEqual(verifier._check_path_str(Path("abc"), "p"), Path("abc"))
        self._assert_s93("INVALID_STR", verifier._check_path_str, 42, "p")
        self._assert_s93("EMPTY_PATH", verifier._check_path_str, "", "p")
        self._assert_s93("NUL_BYTE_FORBIDDEN", verifier._check_path_str, "a\x00b", "p")
        self._assert_s93("INVALID_UTF8_SURROGATE", verifier._check_path_str, "\ud800", "p")

    def test_safe_cwd_and_pwd_checks(self) -> None:
        verifier._check_safe_cwd()
        with mock.patch.object(verifier.os, "getcwd", side_effect=OSError("deleted")):
            self._assert_s93("CWD_ERROR", verifier._check_safe_cwd)
        with tempfile.TemporaryDirectory() as td:
            real_d = Path(td) / "real"
            real_d.mkdir()
            sym_d = Path(td) / "sym"
            os.symlink(real_d, sym_d)
            with mock.patch.object(verifier.os, "getcwd", return_value=str(real_d)), mock.patch.dict(
                os.environ, {"PWD": str(sym_d)}
            ):
                self._assert_s93("SYMLINK_IN_PATH", verifier._check_safe_cwd)
            self_sym = real_d / "self_sym"
            os.symlink(real_d, self_sym)
            old_cwd = os.getcwd()
            try:
                os.chdir(real_d)
                with mock.patch.dict(os.environ, {"PWD": "self_sym"}):
                    verifier._check_safe_cwd()
            finally:
                os.chdir(old_cwd)
            with mock.patch.object(verifier.os, "getcwd", return_value=str(real_d)), mock.patch.dict(
                os.environ, {"PWD": str(Path(td) / "missing_dir")}
            ):
                verifier._check_safe_cwd()
            other_d = Path(td) / "other"
            other_d.mkdir()
            sym_other = Path(td) / "sym_other"
            os.symlink(other_d, sym_other)
            with mock.patch.object(verifier.os, "getcwd", return_value=str(real_d)), mock.patch.dict(
                os.environ, {"PWD": str(sym_other)}
            ):
                verifier._check_safe_cwd()
            st_real = os.stat(real_d)
            fake_dev = os.stat_result((st_real.st_mode, st_real.st_ino, st_real.st_dev + 999, 1, 0, 0, 0, 0, 0, 0))
            with mock.patch.object(verifier.os, "getcwd", return_value=str(real_d)), mock.patch.dict(
                os.environ, {"PWD": str(sym_d)}
            ), mock.patch.object(verifier.os, "stat", side_effect=[fake_dev, st_real]):
                verifier._check_safe_cwd()
            env_no_pwd = {k: v for k, v in os.environ.items() if k != "PWD"}
            with mock.patch.dict(os.environ, env_no_pwd, clear=True):
                verifier._check_safe_cwd()
        with mock.patch.object(verifier.os, "lstat", side_effect=PermissionError("denied")):
            self._assert_s93("IO_STAT_ERROR", verifier._check_no_symlink_components, Path("/tmp/a"), "p")

    def test_read_and_write_zone_b_adversarial(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            reg = tdp / "ok.json"
            self.assertEqual(verifier.write_regular_bytes_atomic_0600(reg, b'{"a":1}\n', "w"), reg)
            self.assertEqual(stat.S_IMODE(os.lstat(reg).st_mode), 0o600)
            self.assertEqual(verifier.read_regular_bytes_capped(reg, "r", max_bytes=8), b'{"a":1}\n')
            self._assert_s93("FILE_TOO_LARGE", verifier.read_regular_bytes_capped, reg, "r", max_bytes=7)
            self._assert_s93("INT_OUT_OF_RANGE", verifier.read_regular_bytes_capped, reg, "r", max_bytes=0)
            self._assert_s93("INT_OUT_OF_RANGE", verifier.read_regular_bytes_capped, reg, "r", max_bytes=64 * 1024 * 1024 + 1)

            # Streaming overflow when st_size lies (0) + st_size cap kill on 0-byte file
            fake_st = os.stat_result((stat.S_IFREG | 0o600, 1, 1, 1, 0, 0, 0, 0, 0, 0))
            with mock.patch.object(verifier.os, "fstat", return_value=fake_st):
                self._assert_s93("FILE_TOO_LARGE", verifier.read_regular_bytes_capped, reg, "r", max_bytes=4)
            empty_f = tdp / "empty.json"
            empty_f.write_bytes(b"")
            big_st = os.stat_result((stat.S_IFREG | 0o600, 1, 1, 1, 0, 0, 100, 0, 0, 0))
            with mock.patch.object(verifier.os, "fstat", return_value=big_st):
                self._assert_s93("FILE_TOO_LARGE", verifier.read_regular_bytes_capped, empty_f, "r", max_bytes=8)

            sym = tdp / "sym.json"
            os.symlink(reg, sym)
            self._assert_s93("SYMLINK_IN_PATH", verifier.read_regular_bytes_capped, sym, "r")
            self._assert_s93("SYMLINK_IN_PATH", verifier.write_regular_bytes_atomic_0600, sym, b"x", "w")

            hl = tdp / "hl.json"
            os.link(reg, hl)
            self._assert_s93("HARDLINK_FORBIDDEN", verifier.read_regular_bytes_capped, hl, "r")
            self._assert_s93("HARDLINK_FORBIDDEN", verifier.write_regular_bytes_atomic_0600, hl, b"x", "w")
            os.unlink(hl)

            fifo = tdp / "pipe"
            os.mkfifo(fifo)
            self._assert_s93("NOT_REGULAR_FILE", verifier.read_regular_bytes_capped, fifo, "r")
            self._assert_s93("TARGET_NOT_REGULAR", verifier.write_regular_bytes_atomic_0600, fifo, b"x", "w")

            self._assert_s93("IO_OPEN_ERROR", verifier.read_regular_bytes_capped, tdp / "missing.json", "r")
            self._assert_s93("INVALID_BYTES", verifier.write_regular_bytes_atomic_0600, reg, "not-bytes", "w")
            self._assert_s93("PARENT_MISSING", verifier.write_regular_bytes_atomic_0600, tdp / "no_dir" / "a", b"x", "w")
            self._assert_s93("PARENT_NOT_DIR", verifier.write_regular_bytes_atomic_0600, reg / "child", b"x", "w")

            # Simulated error branches on write (bypassing _check_no_symlink_components to reach target lstat)
            with mock.patch.object(verifier, "_check_no_symlink_components", return_value=reg), mock.patch.object(
                verifier.os, "lstat", side_effect=[os.lstat(tdp), PermissionError("e")]
            ):
                self._assert_s93("IO_STAT_ERROR", verifier.write_regular_bytes_atomic_0600, reg, b"x", "w")
            with mock.patch.object(verifier.os, "open", side_effect=OSError("dir")):
                self._assert_s93("IO_OPEN_ERROR", verifier.write_regular_bytes_atomic_0600, reg, b"x", "w")
            with mock.patch.object(verifier.os, "write", return_value=0):
                self._assert_s93("IO_WRITE_ERROR", verifier.write_regular_bytes_atomic_0600, tdp / "w_err", b"abc", "w")
            bad_mode_st = os.stat_result((stat.S_IFIFO | 0o600, 1, 1, 1, 0, 0, 1, 0, 0, 0))
            with mock.patch.object(verifier.os, "fstat", return_value=bad_mode_st):
                self._assert_s93("TMP_TAMPERED", verifier.write_regular_bytes_atomic_0600, tdp / "w_m", b"x", "w")
            bad_nlink_st = os.stat_result((stat.S_IFREG | 0o600, 1, 1, 2, 0, 0, 1, 0, 0, 0))
            with mock.patch.object(verifier.os, "fstat", return_value=bad_nlink_st):
                self._assert_s93("TMP_TAMPERED", verifier.write_regular_bytes_atomic_0600, tdp / "w_n", b"x", "w")
            with mock.patch.object(verifier.os, "write", return_value=0), mock.patch.object(
                verifier.os, "unlink", side_effect=OSError("unlink fail")
            ):
                self._assert_s93("IO_WRITE_ERROR", verifier.write_regular_bytes_atomic_0600, tdp / "w_u", b"x", "w")

    def test_strict_json_and_rational_parsers(self) -> None:
        self.assertEqual(verifier.parse_strict_json_bytes(b'{"a":1}\n', "j"), {"a": 1})
        self.assertEqual(verifier.parse_strict_json_bytes(b'{ "a": 1 }', "j", require_canonical=False), {"a": 1})
        self._assert_s93("INVALID_BYTES", verifier.parse_strict_json_bytes, "str", "j")
        self._assert_s93("JSON_TOO_LARGE", verifier.parse_strict_json_bytes, b" " * (verifier.MAX_JSON_BYTES + 1), "j")
        exact_prefix = b'{"a":"'
        exact_suffix = b'"}\n'
        exact_pad = b"x" * (verifier.MAX_JSON_BYTES - len(exact_prefix) - len(exact_suffix))
        self.assertEqual(
            len(verifier.parse_strict_json_bytes(exact_prefix + exact_pad + exact_suffix, "j_max")["a"]),
            len(exact_pad),
        )
        self._assert_s93("JSON_BAD_BYTES", verifier.parse_strict_json_bytes, b'{"a":1}\r\n', "j")
        self._assert_s93("JSON_BAD_BYTES", verifier.parse_strict_json_bytes, b'{"a":1}\x00', "j")
        self._assert_s93("NON_ASCII_JSON", verifier.parse_strict_json_bytes, b'{"a":"\xc3\xa9"}\n', "j")
        self._assert_s93("FORBIDDEN_JSON_FLOAT", verifier.parse_strict_json_bytes, b'{"a":1.5}\n', "j")
        self._assert_s93("FORBIDDEN_JSON_CONST", verifier.parse_strict_json_bytes, b'{"a":NaN}\n', "j")
        self._assert_s93("DUPLICATE_JSON_KEY", verifier.parse_strict_json_bytes, b'{"a":1,"a":2}\n', "j")
        self._assert_s93("NON_CANONICAL_JSON", verifier.parse_strict_json_bytes, b'{ "a": 1 }\n', "j")
        self._assert_s93("INVALID_JSON", verifier.parse_strict_json_bytes, b"{bad", "j")
        big_i = ("9" * (verifier.MAX_JSON_INT_DIGITS + 1)).encode("ascii")
        self._assert_s93("JSON_INT_TOO_LARGE", verifier.parse_strict_json_bytes, b'{"a":' + big_i + b"}\n", "j")
        self._assert_s93("JSON_INT_TOO_LARGE", verifier.parse_strict_json_bytes, b'{"a":-' + big_i + b"}\n", "j")
        self._assert_s93("JSON_INT_TOO_LARGE", verifier.parse_strict_json_bytes, b"{" + big_i, "j")
        ok_i = ("9" * verifier.MAX_JSON_INT_DIGITS).encode("ascii")
        self.assertEqual(verifier.parse_strict_json_bytes(b'{"a":-' + ok_i + b"}\n", "j")["a"], -int(ok_i))
        self._assert_s93("JSON_INT_TOO_LARGE", verifier._strict_int_parse, "9" * (verifier.MAX_JSON_INT_DIGITS + 1))
        self._assert_s93("INVALID_JSON_INT", verifier._strict_int_parse, "01")
        self.assertEqual(verifier._require_nonempty_str("x", "s"), "x")
        self._assert_s93("EMPTY_STR", verifier._require_nonempty_str, "", "s")
        self._assert_s93("INVALID_STR", verifier._require_nonempty_str, 7, "s")

        self.assertEqual(verifier.parse_canonical_rational_str("0", "q"), Fraction(0))
        self.assertEqual(verifier.parse_canonical_rational_str("-3/4", "q"), Fraction(-3, 4))
        exact_256 = "1" + "0" * (verifier.MAX_RATIONAL_STR_LEN - 1)
        self.assertEqual(verifier.parse_canonical_rational_str(exact_256, "q_max"), Fraction(10 ** (verifier.MAX_RATIONAL_STR_LEN - 1), 1))
        self._assert_s93("RATIONAL_STR_TOO_LONG", verifier.parse_canonical_rational_str, "9" * (verifier.MAX_RATIONAL_STR_LEN + 1), "q_over")
        self._assert_s93("RATIONAL_STR_TOO_LONG", verifier.parse_canonical_rational_str, "9" * 5000, "q_5000")
        self._assert_s93("INVALID_RATIONAL_STR", verifier.parse_canonical_rational_str, "+1/2", "q")
        self._assert_s93("INVALID_RATIONAL_STR", verifier.parse_canonical_rational_str, "1/0", "q")
        self._assert_s93("NON_CANONICAL_RATIONAL", verifier.parse_canonical_rational_str, "3/1", "q")
        self._assert_s93("NON_REDUCED_RATIONAL", verifier.parse_canonical_rational_str, "2/4", "q")
        self._assert_s93("INVALID_DICT", verifier._require_exact_dict, [], frozenset(), "d")
        self._assert_s93("KEYSET_MISMATCH", verifier._require_exact_dict, {"a": 1}, frozenset({"b"}), "d")


class Test04SecondaryAuditReplayAndCLI(unittest.TestCase):
    def setUp(self) -> None:
        self.cert = json.loads((_THIS_DIR / "s93_omega94_vpvnp_certificate.json").read_text(encoding="ascii"))

    def _assert_s93(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S93Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def _resign(self, payload: dict) -> dict:
        psha = oracle.sha256_hex(oracle.canonical_json_bytes(payload))
        core = {
            "schema_version": oracle.SCHEMA_VERSION,
            "track_id": oracle.TRACK_ID,
            "payload_sha256": psha,
            "payload": payload,
        }
        return {**core, "certificate_sha256": oracle.sha256_hex(oracle.canonical_json_bytes(core))}

    def test_envelope_and_load_artifacts_errors(self) -> None:
        self._assert_s93("INVALID_BOOL", verifier.verify_certificate_dict, self.cert, full_replay=1)
        self._assert_s93("INVALID_CERT_TYPE", verifier.verify_certificate_dict, [], full_replay=False)
        bad = copy.deepcopy(self.cert)
        bad["schema_version"] = "bad"
        self._assert_s93("SCHEMA_MISMATCH", verifier.verify_certificate_dict, bad, full_replay=False)
        bad = copy.deepcopy(self.cert)
        bad["track_id"] = "bad"
        self._assert_s93("SCHEMA_MISMATCH", verifier.verify_certificate_dict, bad, full_replay=False)
        bad = copy.deepcopy(self.cert)
        bad["payload_sha256"] = "0" * 64
        self._assert_s93("PAYLOAD_SHA_MISMATCH", verifier.verify_certificate_dict, bad, full_replay=False)
        bad = copy.deepcopy(self.cert)
        bad["certificate_sha256"] = "0" * 64
        self._assert_s93("CERT_SHA_MISMATCH", verifier.verify_certificate_dict, bad, full_replay=False)

        # S93-FACT-01 honest T-14 dual-kernel grading & immutable global/output isolation
        s93_row = self.cert["payload"]["pillar2_forensic_trust_audit"]["trust_scorecard_matrix"][3]
        self.assertFalse(s93_row["t14_dual_kernel_nanoda"])
        self.assertFalse(s93_row["all_three_v23_gates_pass"])
        for tbl in (
            oracle.PINNED_WAVE6_SOURCES,
            oracle.UPSTREAM_EXPEDITION_CERTS,
            oracle.PEQUALNP_NOTE1_ROWS,
            oracle.PEQUALNP_CIRCUIT_HELPERS,
        ):
            with self.assertRaises(TypeError):
                tbl[0]["_mut"] = "forbidden"  # type: ignore[index]
        p_iso = oracle.build_payload()
        p_iso["wave6_provenance"]["pinned_sources"][0]["role"] = "mutated"
        p_iso["upstream_expedition_bridges"][0]["bridge"] = "mutated"
        p_iso["pillar4_pequalnp_barriers"]["note1_statements"][0]["run"] = "mutated"
        p_iso["pillar4_pequalnp_barriers"]["circuit_helpers"][0]["barrier_class"] = "mutated"
        self.assertEqual(oracle.canonical_json_bytes(oracle.build_payload()), oracle.canonical_json_bytes(self.cert["payload"]))

        # Field-complete SEC/FR0/FR1 rejection on re-signed narrative forgery & direct REPLAY_MISMATCH kill
        p_mod = copy.deepcopy(self.cert["payload"])
        p_mod["pillar2_forensic_trust_audit"]["openai_comparator_model"] = "altered-nonempty-model-description"
        self._assert_s93("PAYLOAD_CANONICAL_PIN_MISMATCH", verifier.secondary_audit_payload, p_mod)
        self._assert_s93("PAYLOAD_CANONICAL_PIN_MISMATCH", verifier.verify_certificate_dict, self._resign(p_mod), full_replay=False)
        self._assert_s93("PAYLOAD_CANONICAL_PIN_MISMATCH", verifier.verify_certificate_dict, self._resign(p_mod), full_replay=True)
        with mock.patch.object(oracle, "build_certificate", return_value={"diverged": True}):
            self._assert_s93("REPLAY_MISMATCH", verifier.verify_certificate_dict, self.cert, full_replay=True)

        # _load_track_artifacts & pin mismatch paths
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            (tdp / "lean-toolchain").write_bytes(b"\xff\xfe")
            (tdp / "lakefile.toml").write_text("x", encoding="ascii")
            self._assert_s93("INVALID_UTF8", verifier._load_track_artifacts, tdp)
            (tdp / "lean-toolchain").write_text("leanprover/lean4:v4.0.0\n", encoding="ascii")
            self._assert_s93("TOOLCHAIN_MISMATCH", verifier._load_track_artifacts, tdp)

        fake_live = {"lean_version": "4.36.0", "theorems_verified": 18, "lean_source_sha256": oracle.PINNED_LEAN_SOURCE_SHA256}
        with mock.patch.object(verifier, "_load_track_artifacts", return_value=("0" * 64, oracle.PINNED_LEAN_TOOLCHAIN_SHA256, oracle.PINNED_LAKEFILE_SHA256, fake_live)):
            self._assert_s93("LEAN_SHA_MISMATCH", verifier.verify_certificate_dict, self.cert, full_replay=True)
        with mock.patch.object(verifier, "_load_track_artifacts", return_value=(oracle.PINNED_LEAN_SOURCE_SHA256, "0" * 64, oracle.PINNED_LAKEFILE_SHA256, fake_live)):
            self._assert_s93("TOOLCHAIN_SHA_MISMATCH", verifier.verify_certificate_dict, self.cert, full_replay=True)
        with mock.patch.object(verifier, "_load_track_artifacts", return_value=(oracle.PINNED_LEAN_SOURCE_SHA256, oracle.PINNED_LEAN_TOOLCHAIN_SHA256, "0" * 64, fake_live)):
            self._assert_s93("LAKEFILE_SHA_MISMATCH", verifier.verify_certificate_dict, self.cert, full_replay=True)

    def test_secondary_audit_exhaustive_tamper_kills(self) -> None:
        base = self.cert["payload"]
        self.assertTrue(verifier.secondary_audit_payload(base)["secondary_audit_passed"])
        self._assert_s93("INVALID_PAYLOAD_TYPE", verifier.secondary_audit_payload, [])

        def tamper(code: str, mut_fn) -> None:
            p = copy.deepcopy(base)
            mut_fn(p)
            self._assert_s93(code, verifier.secondary_audit_payload, p)
            self._assert_s93(code, verifier.verify_certificate_dict, self._resign(p), full_replay=False)

        # Top-level & provenance
        tamper("SCHEMA_MISMATCH", lambda p: p.__setitem__("schema_version", "x"))
        tamper("SCHEMA_MISMATCH", lambda p: p.__setitem__("track_id", "x"))
        tamper("SCHEMA_MISMATCH", lambda p: p.__setitem__("oracle_class", "approx"))
        tamper("SCHEMA_MISMATCH", lambda p: p.__setitem__("novelty_classification", "N2"))
        tamper("PROV_OAI_REPO", lambda p: p["wave6_provenance"].__setitem__("openai_math_repo", "x"))
        tamper("PROV_OAI_COMMIT", lambda p: p["wave6_provenance"].__setitem__("openai_math_commit", "x"))
        tamper("PROV_OAI_TC", lambda p: p["wave6_provenance"].__setitem__("openai_math_toolchain", "x"))
        tamper("PROV_PNP_REPO", lambda p: p["wave6_provenance"].__setitem__("pequalnp_repo", "x"))
        tamper("PROV_PNP_COMMIT", lambda p: p["wave6_provenance"].__setitem__("pequalnp_commit", "x"))
        tamper("PROV_PNP_TC", lambda p: p["wave6_provenance"].__setitem__("pequalnp_toolchain", "x"))
        tamper("PROV_SRCS_LEN", lambda p: p["wave6_provenance"].__setitem__("pinned_sources", "123456789012"))
        tamper("PROV_SRCS_LEN", lambda p: p["wave6_provenance"].__setitem__("pinned_sources", []))
        tamper("PROV_SRCS_PIN", lambda p: p["wave6_provenance"]["pinned_sources"][0].__setitem__("sha256", "0" * 64))
        tamper("EMPTY_STR", lambda p: p["wave6_provenance"]["pinned_sources"][0].__setitem__("role", ""))
        tamper("UP_LEN", lambda p: p.__setitem__("upstream_expedition_bridges", "1234"))
        tamper("UP_LEN", lambda p: p.__setitem__("upstream_expedition_bridges", []))
        tamper("UP_PIN", lambda p: p["upstream_expedition_bridges"][0].__setitem__("cert_sha256", "0" * 64))
        tamper("EMPTY_STR", lambda p: p["upstream_expedition_bridges"][0].__setitem__("bridge", ""))
        tamper("SCHEMA_MISMATCH", lambda p: p["pinned_artifacts"].__setitem__("lean_source", "other.lean"))
        tamper("SCHEMA_MISMATCH", lambda p: p["pinned_artifacts"].__setitem__("lean_toolchain", "bad"))
        tamper("PINNED_SHA_MISMATCH", lambda p: p["pinned_artifacts"].__setitem__("lean_source_sha256", "0" * 64))
        tamper("THEOREM_LIST_MISMATCH", lambda p: p["pinned_artifacts"].__setitem__("lean_theorem_names", {t: 0 for t in oracle.LEAN_THEOREM_NAMES}))
        tamper("THEOREM_LIST_MISMATCH", lambda p: p["pinned_artifacts"].__setitem__("lean_theorem_names", ["x"] * 18))

        # Pillar 1
        tamper("P1_CORE", lambda p: (p["pillar1_openai_omega94"].__setitem__("square_omega_q", "2"), p["pillar1_openai_omega94"].__setitem__("irreducible_excess_above_2_q", "0")))
        tamper("P1_CORE", lambda p: p["pillar1_openai_omega94"].__setitem__("dual_alpha_q", "1/3"))
        tamper("P1_CORE", lambda p: p["pillar1_openai_omega94"].__setitem__("irreducible_excess_above_2_q", "1/2"))
        tamper("P1_CURVE_LEN", lambda p: p["pillar1_openai_omega94"].__setitem__("rectangular_1_1_t_curve", "123456789"))
        tamper("P1_CURVE_LEN", lambda p: p["pillar1_openai_omega94"].__setitem__("rectangular_1_1_t_curve", []))
        tamper("P1_T_RANGE", lambda p: p["pillar1_openai_omega94"]["rectangular_1_1_t_curve"][0].__setitem__("t_q", "-1/2"))
        tamper("P1_T_RANGE", lambda p: p["pillar1_openai_omega94"]["rectangular_1_1_t_curve"][-1].__setitem__("t_q", "3/2"))
        tamper("P1_T_ORDER", lambda p: p["pillar1_openai_omega94"]["rectangular_1_1_t_curve"].__setitem__(1, copy.deepcopy(p["pillar1_openai_omega94"]["rectangular_1_1_t_curve"][0])))
        tamper("P1_CURVE_MATH", lambda p: (
            p["pillar1_openai_omega94"]["rectangular_1_1_t_curve"][0].__setitem__("omega_q", "5/2"),
            p["pillar1_openai_omega94"]["rectangular_1_1_t_curve"][0].__setitem__("penalty_above_2_q", "1/2"),
        ))
        tamper("P1_CURVE_MATH", lambda p: p["pillar1_openai_omega94"]["rectangular_1_1_t_curve"][0].__setitem__("penalty_above_2_q", "1"))
        tamper("P1_CURVE_MATH", lambda p: p["pillar1_openai_omega94"]["rectangular_1_1_t_curve"][0].__setitem__("cor13_lower_bound_q", "1"))
        tamper("P1_CURVE_FLAG", lambda p: p["pillar1_openai_omega94"]["rectangular_1_1_t_curve"][0].__setitem__("in_linear_o_n2_regime", False))
        tamper("P1_CURVE_FLAG", lambda p: p["pillar1_openai_omega94"]["rectangular_1_1_t_curve"][0].__setitem__("strictly_exceeds_cor13", True))
        tamper("P1_CURVE_DEC", lambda p: p["pillar1_openai_omega94"]["rectangular_1_1_t_curve"][0].__setitem__("omega_dec6", "0.000000"))
        tamper("P1_SYM_LEN", lambda p: p["pillar1_openai_omega94"].__setitem__("s3_symmetry_triple_q", "123"))
        tamper("P1_SYM_LEN", lambda p: p["pillar1_openai_omega94"].__setitem__("s3_symmetry_triple_q", ["1"]))
        tamper("P1_SYM_MATH", lambda p: p["pillar1_openai_omega94"].__setitem__("s3_symmetry_omega_q", "2"))
        tamper("P1_SYM_MATH", lambda p: p["pillar1_openai_omega94"].__setitem__("s3_all_6_permutations_equal", False))
        tamper("P1_SYM_DEC", lambda p: p["pillar1_openai_omega94"].__setitem__("s3_symmetry_omega_dec6", "0.000000"))
        tamper("P1_HARM", lambda p: p["pillar1_openai_omega94"].__setitem__("general_sub_harmonic_omega_q", "2"))
        tamper("P1_CONV_LEN", lambda p: p["pillar1_openai_omega94"].__setitem__("midpoint_convexity_checks", "123"))
        tamper("P1_CONV_LEN", lambda p: p["pillar1_openai_omega94"].__setitem__("midpoint_convexity_checks", []))
        tamper("P1_CONV_DOM", lambda p: (
            p["pillar1_openai_omega94"]["midpoint_convexity_checks"][0].__setitem__("t1_q", "1/4"),
            p["pillar1_openai_omega94"]["midpoint_convexity_checks"][0].__setitem__("tmid_q", "5/8"),
        ))
        tamper("P1_CONV_DOM", lambda p: (
            p["pillar1_openai_omega94"]["midpoint_convexity_checks"][0].__setitem__("t1_q", "3/4"),
            p["pillar1_openai_omega94"]["midpoint_convexity_checks"][0].__setitem__("t2_q", "3/4"),
            p["pillar1_openai_omega94"]["midpoint_convexity_checks"][0].__setitem__("tmid_q", "3/4"),
        ))
        tamper("P1_CONV_DOM", lambda p: (
            p["pillar1_openai_omega94"]["midpoint_convexity_checks"][0].__setitem__("t2_q", "3/2"),
            p["pillar1_openai_omega94"]["midpoint_convexity_checks"][0].__setitem__("tmid_q", "1"),
        ))
        tamper("P1_CONV_DOM", lambda p: p["pillar1_openai_omega94"]["midpoint_convexity_checks"][0].__setitem__("tmid_q", "1/2"))
        tamper("P1_CONV_MATH", lambda p: (
            p["pillar1_openai_omega94"]["midpoint_convexity_checks"][0].__setitem__("jensen_gap_q", "1/2"),
            p["pillar1_openai_omega94"]["midpoint_convexity_checks"][0].__setitem__("jensen_gap_dec6", "0.500000"),
        ))
        tamper("P1_CONV_MATH", lambda p: p["pillar1_openai_omega94"]["midpoint_convexity_checks"][0].__setitem__("jensen_gap_dec6", "0.000000"))
        tamper("P1_STRASSEN", lambda p: p["pillar1_openai_omega94"].__setitem__("strassen_2_280_lt_7_100_lt_2_281", False))
        tamper("P1_BENCH_LEN", lambda p: p["pillar1_openai_omega94"].__setitem__("historical_benchmarks", "123456"))
        tamper("P1_BENCH_LEN", lambda p: p["pillar1_openai_omega94"].__setitem__("historical_benchmarks", []))
        tamper("P1_BENCH_MATH", lambda p: (
            p["pillar1_openai_omega94"]["historical_benchmarks"][0].__setitem__("gap_above_9_4_q", "1"),
            p["pillar1_openai_omega94"]["historical_benchmarks"][0].__setitem__("gap_dec6", "1.000000"),
        ))
        tamper("P1_BENCH_MATH", lambda p: (
            p["pillar1_openai_omega94"]["historical_benchmarks"][-1].__setitem__("exponent_q", "2"),
            p["pillar1_openai_omega94"]["historical_benchmarks"][-1].__setitem__("gap_above_9_4_q", "-1/4"),
            p["pillar1_openai_omega94"]["historical_benchmarks"][-1].__setitem__("gap_dec6", "-0.250000"),
        ))
        tamper("P1_BENCH_MATH", lambda p: p["pillar1_openai_omega94"]["historical_benchmarks"][0].__setitem__("gap_dec6", "0.000000"))
        tamper("P1_BENCH_ORDER", lambda p: (
            p["pillar1_openai_omega94"]["historical_benchmarks"][1].__setitem__("exponent_q", "3"),
            p["pillar1_openai_omega94"]["historical_benchmarks"][1].__setitem__("gap_above_9_4_q", "3/4"),
            p["pillar1_openai_omega94"]["historical_benchmarks"][1].__setitem__("gap_dec6", "0.750000"),
        ))
        tamper("P1_FLOOR_LEN", lambda p: p["pillar1_openai_omega94"].__setitem__("corollary12_finite_floors", "123"))
        tamper("P1_FLOOR_LEN", lambda p: p["pillar1_openai_omega94"].__setitem__("corollary12_finite_floors", []))
        tamper("P1_FLOOR_MATH", lambda p: (
            p["pillar1_openai_omega94"]["corollary12_finite_floors"][0].__setitem__("side_n", 17),
            p["pillar1_openai_omega94"]["corollary12_finite_floors"][0].__setitem__("output_entries_n2", 289),
            p["pillar1_openai_omega94"]["corollary12_finite_floors"][0].__setitem__("naive_cubic_n3", 4913),
            p["pillar1_openai_omega94"]["corollary12_finite_floors"][0].__setitem__("rank_over_output_q", "512/289"),
        ))
        tamper("P1_FLOOR_MATH", lambda p: (
            p["pillar1_openai_omega94"]["corollary12_finite_floors"][0].__setitem__("output_entries_n2", 512),
            p["pillar1_openai_omega94"]["corollary12_finite_floors"][0].__setitem__("rank_over_output_q", "1"),
        ))
        tamper("P1_FLOOR_MATH", lambda p: (
            p["pillar1_openai_omega94"]["corollary12_finite_floors"][0].__setitem__("border_rank_lb_n94", 514),
            p["pillar1_openai_omega94"]["corollary12_finite_floors"][0].__setitem__("nonscalar_gate_lb", 257),
            p["pillar1_openai_omega94"]["corollary12_finite_floors"][0].__setitem__("rank_over_output_q", "257/128"),
        ))
        tamper("P1_FLOOR_MATH", lambda p: p["pillar1_openai_omega94"]["corollary12_finite_floors"][0].__setitem__("nonscalar_gate_lb", 257))
        tamper("P1_FLOOR_MATH", lambda p: p["pillar1_openai_omega94"]["corollary12_finite_floors"][0].__setitem__("naive_cubic_n3", 4097))
        tamper("P1_FLOOR_MATH", lambda p: p["pillar1_openai_omega94"]["corollary12_finite_floors"][0].__setitem__("rank_over_output_q", "3"))

        # Pillar 2
        tamper("P2_DUAL", lambda p: p["pillar2_forensic_trust_audit"].__setitem__("openai_math_dual_model_verified", False))
        tamper("EMPTY_STR", lambda p: p["pillar2_forensic_trust_audit"].__setitem__("openai_comparator_model", ""))
        tamper("INVALID_STR", lambda p: p["pillar2_forensic_trust_audit"]["pequalnp_checker_controls"].__setitem__(0, None))
        tamper("INVALID_BOOL", lambda p: p["pillar2_forensic_trust_audit"]["trust_scorecard_matrix"][0].__setitem__("uses_mathlib_classical", 1))
        tamper("EMPTY_STR", lambda p: p["pillar2_forensic_trust_audit"]["trust_scorecard_matrix"][0].__setitem__("key_scope_note", ""))
        tamper("P2_CTRL_LEN", lambda p: p["pillar2_forensic_trust_audit"].__setitem__("pequalnp_checker_controls", "12345"))
        tamper("P2_CTRL_LEN", lambda p: p["pillar2_forensic_trust_audit"].__setitem__("pequalnp_checker_controls", []))
        tamper("P2_MAT_LEN", lambda p: p["pillar2_forensic_trust_audit"].__setitem__("trust_scorecard_matrix", "1234"))
        tamper("P2_MAT_LEN", lambda p: p["pillar2_forensic_trust_audit"].__setitem__("trust_scorecard_matrix", []))
        tamper("P2_SCORECARD", lambda p: p["pillar2_forensic_trust_audit"]["trust_scorecard_matrix"][1].__setitem__("all_three_v23_gates_pass", True))

        # Pillar 3
        tamper("P3_FLAGS", lambda p: p["pillar3_law5_reconciliation"].__setitem__("ambient_space_unified_cat0", False))
        tamper("P3_FLAGS", lambda p: p["pillar3_law5_reconciliation"].__setitem__("spectral_flat_law_imports_catzero", False))
        tamper("P3_FLAT_LEN", lambda p: p["pillar3_law5_reconciliation"].__setitem__("euclidean_flat_charts", "123"))
        tamper("P3_FLAT_LEN", lambda p: p["pillar3_law5_reconciliation"].__setitem__("euclidean_flat_charts", []))
        tamper("P3_SIDES", lambda p: p["pillar3_law5_reconciliation"]["euclidean_flat_charts"][0].__setitem__("sides_q", "123"))
        tamper("P3_SIDES", lambda p: p["pillar3_law5_reconciliation"]["euclidean_flat_charts"][0].__setitem__("sides_q", ["3", "4"]))
        tamper("P3_FLAT_MATH", lambda p: (
            p["pillar3_law5_reconciliation"]["euclidean_flat_charts"][0].__setitem__("perimeter_q", "10"),
            p["pillar3_law5_reconciliation"]["euclidean_flat_charts"][0].__setitem__("normalized_mean_width_q", "5"),
        ))
        tamper("P3_FLAT_MATH", lambda p: p["pillar3_law5_reconciliation"]["euclidean_flat_charts"][0].__setitem__("normalized_mean_width_q", "5"))
        tamper("P3_FLAT_MATH", lambda p: p["pillar3_law5_reconciliation"]["euclidean_flat_charts"][0].__setitem__("perimeter_over_mean_width_q", "3"))
        tamper("P3_FLAT_MATH", lambda p: p["pillar3_law5_reconciliation"]["euclidean_flat_charts"][0].__setitem__("gram_det_q", "1"))
        tamper("P3_FLAT_MATH", lambda p: (
            p["pillar3_law5_reconciliation"]["euclidean_flat_charts"][0].__setitem__("sides_q", ["1", "1", "2"]),
            p["pillar3_law5_reconciliation"]["euclidean_flat_charts"][0].__setitem__("perimeter_q", "4"),
            p["pillar3_law5_reconciliation"]["euclidean_flat_charts"][0].__setitem__("normalized_mean_width_q", "2"),
            p["pillar3_law5_reconciliation"]["euclidean_flat_charts"][0].__setitem__("gram_det_q", "0"),
        ))
        tamper("P3_FLAT_B94", lambda p: p["pillar3_law5_reconciliation"]["euclidean_flat_charts"][0].__setitem__("strictly_below_9_4", False))
        tamper("P3_RECT", lambda p: (
            p["pillar3_law5_reconciliation"]["planar_rectangle_3x4"].__setitem__("perimeter_q", "12"),
            p["pillar3_law5_reconciliation"]["planar_rectangle_3x4"].__setitem__("normalized_mean_width_q", "6"),
        ))
        tamper("P3_RECT", lambda p: p["pillar3_law5_reconciliation"]["planar_rectangle_3x4"].__setitem__("normalized_mean_width_q", "6"))
        tamper("P3_RECT", lambda p: p["pillar3_law5_reconciliation"]["planar_rectangle_3x4"].__setitem__("interior_insertion_delta_q", "1"))
        tamper("P3_RECT", lambda p: p["pillar3_law5_reconciliation"]["planar_rectangle_3x4"].__setitem__("monotone_above_345_triangle", False))

        tamper("P3_TGM", lambda p: p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("gram_matrix_q", "123"))
        tamper("P3_TGM", lambda p: p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("gram_matrix_q", [["1", "0", "0"]]))
        tamper("P3_TGM", lambda p: p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("gram_matrix_q", ["123", "123", "123"]))
        tamper("P3_TGM", lambda p: p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("gram_matrix_q", [["1"], ["1"], ["1"]]))
        tamper("P3_TVEC", lambda p: p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("neg_quad_witness_vec", "123"))
        tamper("P3_TVEC", lambda p: p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("neg_quad_witness_vec", [1]))
        tamper("P3_TRIPOD_MATH", lambda p: (
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("arm_length_q", "2"),
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("tip_distance_q", "4"),
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("triangle_perimeter_q", "12"),
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("shared_label_rate_q", "16/3"),
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("curvature_defect_below_flat_q", "2/3"),
        ))
        tamper("P3_TRIPOD_MATH", lambda p: (
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("tip_distance_q", "3"),
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("triangle_perimeter_q", "9"),
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("curvature_defect_below_flat_q", "11/6"),
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("ratio_perimeter_over_rate_q", "27/8"),
        ))
        tamper("P3_TRIPOD_MATH", lambda p: (
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("triangle_perimeter_q", "8"),
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("curvature_defect_below_flat_q", "4/3"),
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("ratio_perimeter_over_rate_q", "3"),
        ))
        tamper("P3_TRIPOD_MATH", lambda p: (
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("shared_label_rate_q", "3"),
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("curvature_defect_below_flat_q", "0"),
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("ratio_perimeter_over_rate_q", "2"),
        ))
        tamper("P3_TRIPOD_MATH", lambda p: p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("curvature_defect_below_flat_q", "0"))
        tamper("P3_TRIPOD_MATH", lambda p: p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("ratio_perimeter_over_rate_q", "2"))
        tamper("P3_TRIPOD_MATH", lambda p: p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("gram_det_q", "-1"))
        tamper("P3_TRIPOD_MATH", lambda p: (
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("gram_matrix_q", [["-1", "0", "0"], ["0", "-1", "0"], ["0", "0", "-1"]]),
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("gram_det_q", "-1"),
        ))
        # Direct non-list tuple kills on _audit_pillar3 Gram matrices
        p3_tup1 = copy.deepcopy(base["pillar3_law5_reconciliation"])
        p3_tup1["openai_cat0_tripod_witness"]["gram_matrix_q"] = tuple(p3_tup1["openai_cat0_tripod_witness"]["gram_matrix_q"])
        self._assert_s93("P3_TGM", verifier._audit_pillar3, p3_tup1)
        p3_tup2 = copy.deepcopy(base["pillar3_law5_reconciliation"])
        p3_tup2["vpvnp_rem_d3_witness"]["gram_matrix_q"] = tuple(p3_tup2["vpvnp_rem_d3_witness"]["gram_matrix_q"])
        self._assert_s93("P3_VGM", verifier._audit_pillar3, p3_tup2)
        tamper("P3_TRIPOD_MATH", lambda p: p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("neg_quad_form_q", "-1"))
        tamper("P3_TRIPOD_MATH", lambda p: (
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("neg_quad_witness_vec", [0, 0, 0]),
            p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("neg_quad_form_q", "0"),
        ))
        tamper("P3_TRIPOD_MATH", lambda p: p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("bruhat_tits_cn_slack_q", "1"))
        tamper("P3_TRIPOD_MATH", lambda p: p["pillar3_law5_reconciliation"]["openai_cat0_tripod_witness"].__setitem__("isometric_euclidean_chart_blocked", False))

        tamper("P3_VPTS", lambda p: p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("points", "12345"))
        tamper("P3_VPTS", lambda p: p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("points", []))
        tamper("EMPTY_STR", lambda p: p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"]["points"].__setitem__(0, ""))
        tamper("P3_VGM", lambda p: p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("gram_matrix_q", "1234"))
        tamper("P3_VGM", lambda p: p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("gram_matrix_q", []))
        tamper("P3_VGM", lambda p: p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("gram_matrix_q", ["1234"] * 4))
        tamper("P3_VGM", lambda p: p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("gram_matrix_q", [["1"]] * 4))
        tamper("P3_VVEC", lambda p: p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("neg_quad_witness_vec", "1234"))
        tamper("P3_VVEC", lambda p: p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("neg_quad_witness_vec", [1]))
        tamper("P3_VPVNP_MATH", lambda p: p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("gram_det_q", "-1"))
        tamper("P3_VPVNP_MATH", lambda p: (
            p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("gram_matrix_q", [["1", "0", "0", "0"], ["0", "1", "0", "0"], ["0", "0", "1", "0"], ["0", "0", "0", "-1"]]),
            p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("gram_det_q", "-1"),
            p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("neg_quad_witness_vec", [0, 0, 0, 1]),
        ))
        tamper("P3_VPVNP_MATH", lambda p: p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("neg_quad_witness_vec", [0, 0, 0, 0]))
        tamper("P3_VPVNP_MATH", lambda p: (
            p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("neg_quad_witness_vec", [0, 0, 0, 0]),
            p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("neg_quad_form_q", "0"),
            p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("two_g_quad_form", 0),
        ))
        tamper("P3_VPVNP_MATH", lambda p: p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("two_g_quad_form", -3))
        tamper("P3_VPVNP_MATH", lambda p: p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("isometric_euclidean_chart_blocked", False))
        tamper("P3_VERD", lambda p: p["pillar3_law5_reconciliation"]["law5_reconciliation_verdict"].__setitem__("naive_contradiction", True))

        # Pillar 4
        tamper("P4_STMT_LEN", lambda p: p["pillar4_pequalnp_barriers"].__setitem__("note1_statements", "1234567890"))
        tamper("P4_STMT_LEN", lambda p: p["pillar4_pequalnp_barriers"].__setitem__("note1_statements", []))
        tamper("P4_STMT_PIN", lambda p: p["pillar4_pequalnp_barriers"]["note1_statements"][0].__setitem__("sha256", "0" * 64))
        tamper("EMPTY_STR", lambda p: p["pillar4_pequalnp_barriers"]["note1_statements"][0].__setitem__("summary", ""))
        tamper("P4_HELP_LEN", lambda p: p["pillar4_pequalnp_barriers"].__setitem__("circuit_helpers", "12345"))
        tamper("P4_HELP_LEN", lambda p: p["pillar4_pequalnp_barriers"].__setitem__("circuit_helpers", []))
        tamper("P4_HELP_PIN", lambda p: p["pillar4_pequalnp_barriers"]["circuit_helpers"][0].__setitem__("sha256", "0" * 64))
        tamper("P4_PATH_LEN", lambda p: p["pillar4_pequalnp_barriers"].__setitem__("path_exact_sizes", "1234567"))
        tamper("P4_PATH_LEN", lambda p: p["pillar4_pequalnp_barriers"].__setitem__("path_exact_sizes", []))
        tamper("P4_PATH_DOM", lambda p: p["pillar4_pequalnp_barriers"]["path_exact_sizes"].__setitem__(1, copy.deepcopy(p["pillar4_pequalnp_barriers"]["path_exact_sizes"][0])))
        tamper("P4_PATH_MATH", lambda p: (
            p["pillar4_pequalnp_barriers"]["path_exact_sizes"][0].__setitem__("edges", 2),
            p["pillar4_pequalnp_barriers"]["path_exact_sizes"][0].__setitem__("exact_circuit_size", 2),
        ))
        tamper("P4_PATH_MATH", lambda p: (
            p["pillar4_pequalnp_barriers"]["path_exact_sizes"][0].__setitem__("tau", 2),
            p["pillar4_pequalnp_barriers"]["path_exact_sizes"][0].__setitem__("exact_circuit_size", 2),
        ))
        tamper("P4_PATH_MATH", lambda p: p["pillar4_pequalnp_barriers"]["path_exact_sizes"][0].__setitem__("exact_circuit_size", 2))
        tamper("P4_CYC_LEN", lambda p: p["pillar4_pequalnp_barriers"].__setitem__("cycle_exact_sizes", "123456"))
        tamper("P4_CYC_LEN", lambda p: p["pillar4_pequalnp_barriers"].__setitem__("cycle_exact_sizes", []))
        tamper("P4_CYC_DOM", lambda p: p["pillar4_pequalnp_barriers"]["cycle_exact_sizes"].__setitem__(1, copy.deepcopy(p["pillar4_pequalnp_barriers"]["cycle_exact_sizes"][0])))
        tamper("P4_CYC_MATH", lambda p: (
            p["pillar4_pequalnp_barriers"]["cycle_exact_sizes"][0].__setitem__("edges", 6),
            p["pillar4_pequalnp_barriers"]["cycle_exact_sizes"][0].__setitem__("exact_circuit_size", 8),
        ))
        tamper("P4_CYC_MATH", lambda p: (
            p["pillar4_pequalnp_barriers"]["cycle_exact_sizes"][0].__setitem__("tau", 4),
            p["pillar4_pequalnp_barriers"]["cycle_exact_sizes"][0].__setitem__("exact_circuit_size", 8),
        ))
        tamper("P4_CYC_MATH", lambda p: p["pillar4_pequalnp_barriers"]["cycle_exact_sizes"][0].__setitem__("exact_circuit_size", 8))
        tamper("P4_C4_MATH", lambda p: p["pillar4_pequalnp_barriers"]["c4_biclique_obstruction"].__setitem__("biclique_gate_deficit", 1))
        tamper("P4_C4_PF", lambda p: p["pillar4_pequalnp_barriers"]["c4_biclique_obstruction"].__setitem__("pair_funnel_three_of_four_coincide", False))
        tamper("P4_LINDSEY_MATH", lambda p: p["pillar4_pequalnp_barriers"]["lindsey_n3_witness"].__setitem__("lindsey_lhs_sq", 1))
        tamper("P4_LINDSEY_MATH", lambda p: p["pillar4_pequalnp_barriers"]["lindsey_n3_witness"].__setitem__("lindsey_rhs_2n_ab", 100))
        tamper("P4_LINDSEY_MATH", lambda p: (
            p["pillar4_pequalnp_barriers"]["lindsey_n3_witness"].__setitem__("rect_a_size", 1),
            p["pillar4_pequalnp_barriers"]["lindsey_n3_witness"].__setitem__("rect_b_size", 1),
            p["pillar4_pequalnp_barriers"]["lindsey_n3_witness"].__setitem__("discrepancy_sum", 3),
            p["pillar4_pequalnp_barriers"]["lindsey_n3_witness"].__setitem__("lindsey_lhs_sq", 9),
            p["pillar4_pequalnp_barriers"]["lindsey_n3_witness"].__setitem__("lindsey_rhs_2n_ab", 8),
        ))
        tamper("P4_SMOL_LEN", lambda p: p["pillar4_pequalnp_barriers"].__setitem__("parity_smol_central_sq_checks", "123456789"))
        tamper("P4_SMOL_LEN", lambda p: p["pillar4_pequalnp_barriers"].__setitem__("parity_smol_central_sq_checks", []))
        tamper("P4_SMOL_DOM", lambda p: p["pillar4_pequalnp_barriers"]["parity_smol_central_sq_checks"].__setitem__(1, copy.deepcopy(p["pillar4_pequalnp_barriers"]["parity_smol_central_sq_checks"][0])))
        tamper("P4_SMOL_MATH", lambda p: (
            p["pillar4_pequalnp_barriers"]["parity_smol_central_sq_checks"][0].__setitem__("central_binom", 2),
            p["pillar4_pequalnp_barriers"]["parity_smol_central_sq_checks"][0].__setitem__("lhs", 4),
        ))
        tamper("P4_SMOL_MATH", lambda p: p["pillar4_pequalnp_barriers"]["parity_smol_central_sq_checks"][0].__setitem__("lhs", 2))
        tamper("P4_SMOL_MATH", lambda p: p["pillar4_pequalnp_barriers"]["parity_smol_central_sq_checks"][0].__setitem__("rhs_16k", 2))
        tamper("P4_SAT5_LEN", lambda p: p["pillar4_pequalnp_barriers"].__setitem__("sat_five_4bit_block_checks", "1234"))
        tamper("P4_SAT5_LEN", lambda p: p["pillar4_pequalnp_barriers"].__setitem__("sat_five_4bit_block_checks", []))
        tamper("P4_SAT5_DOM", lambda p: p["pillar4_pequalnp_barriers"]["sat_five_4bit_block_checks"].__setitem__(1, copy.deepcopy(p["pillar4_pequalnp_barriers"]["sat_five_4bit_block_checks"][0])))
        tamper("P4_SAT5_MATH", lambda p: p["pillar4_pequalnp_barriers"]["sat_five_4bit_block_checks"][0].__setitem__("encoded_len", 1))
        tamper("P4_CW_LEN", lambda p: p["pillar4_pequalnp_barriers"].__setitem__("barrier_crosswalk_s41_s44_s75_s93", "12345"))
        tamper("P4_CW_LEN", lambda p: p["pillar4_pequalnp_barriers"].__setitem__("barrier_crosswalk_s41_s44_s75_s93", []))
        tamper("EMPTY_STR", lambda p: p["pillar4_pequalnp_barriers"]["barrier_crosswalk_s41_s44_s75_s93"][0].__setitem__("status", ""))

        # AUDIT-193 S93-VER-01: all 11 F01, F04-F13 re-signed semantic forgeries + S93-FACT-01 flip
        # rejected across SEC, FR0, AND FR1 by field-complete canonical pinning.
        def tamper_all3(code: str, mut_fn) -> None:
            p = copy.deepcopy(base)
            mut_fn(p)
            resigned = self._resign(p)
            self._assert_s93(code, verifier.secondary_audit_payload, p)
            self._assert_s93(code, verifier.verify_certificate_dict, resigned, full_replay=False)
            self._assert_s93(code, verifier.verify_certificate_dict, resigned, full_replay=True)

        tamper_all3("PAYLOAD_CANONICAL_PIN_MISMATCH", lambda p: (
            p["pillar2_forensic_trust_audit"]["trust_scorecard_matrix"][1].__setitem__("t14_dual_kernel_nanoda", True),
            p["pillar2_forensic_trust_audit"]["trust_scorecard_matrix"][1].__setitem__("all_three_v23_gates_pass", True),
        ))
        tamper_all3("PAYLOAD_CANONICAL_PIN_MISMATCH", lambda p: (
            p["pillar2_forensic_trust_audit"]["trust_scorecard_matrix"][3].__setitem__("t14_dual_kernel_nanoda", True),
            p["pillar2_forensic_trust_audit"]["trust_scorecard_matrix"][3].__setitem__("all_three_v23_gates_pass", True),
        ))
        tamper_all3("PAYLOAD_CANONICAL_PIN_MISMATCH", lambda p: p["pillar2_forensic_trust_audit"].__setitem__("openai_comparator_model", "FAKE_MODEL"))
        tamper_all3("PAYLOAD_CANONICAL_PIN_MISMATCH", lambda p: p["pillar4_pequalnp_barriers"]["barrier_crosswalk_s41_s44_s75_s93"][0].__setitem__("evades_natural_proofs", True))
        tamper_all3("PAYLOAD_CANONICAL_PIN_MISMATCH", lambda p: (
            p["pillar4_pequalnp_barriers"]["lindsey_n3_witness"].__setitem__("rect_a_size", 1),
            p["pillar4_pequalnp_barriers"]["lindsey_n3_witness"].__setitem__("rect_b_size", 1),
            p["pillar4_pequalnp_barriers"]["lindsey_n3_witness"].__setitem__("discrepancy_sum", 0),
            p["pillar4_pequalnp_barriers"]["lindsey_n3_witness"].__setitem__("lindsey_lhs_sq", 0),
            p["pillar4_pequalnp_barriers"]["lindsey_n3_witness"].__setitem__("lindsey_rhs_2n_ab", 8),
        ))
        tamper_all3("PAYLOAD_CANONICAL_PIN_MISMATCH", lambda p: (
            p["pillar1_openai_omega94"].__setitem__("s3_symmetry_triple_q", ["1", "1", "1"]),
            p["pillar1_openai_omega94"].__setitem__("s3_symmetry_omega_q", "9/4"),
            p["pillar1_openai_omega94"].__setitem__("s3_symmetry_omega_dec6", "2.250000"),
        ))
        tamper_all3("PAYLOAD_CANONICAL_PIN_MISMATCH", lambda p: (
            p["pillar1_openai_omega94"]["historical_benchmarks"][0].__setitem__("name", "FAKE"),
            p["pillar1_openai_omega94"]["historical_benchmarks"][0].__setitem__("exponent_q", "100"),
            p["pillar1_openai_omega94"]["historical_benchmarks"][0].__setitem__("gap_above_9_4_q", "391/4"),
            p["pillar1_openai_omega94"]["historical_benchmarks"][0].__setitem__("gap_dec6", "97.750000"),
        ))
        tamper_all3("PAYLOAD_CANONICAL_PIN_MISMATCH", lambda p: p["pillar3_law5_reconciliation"]["vpvnp_rem_d3_witness"].__setitem__("points", ["a", "b", "c", "d", "e"]))
        tamper_all3("PAYLOAD_CANONICAL_PIN_MISMATCH", lambda p: p["pillar4_pequalnp_barriers"]["note1_statements"][0].__setitem__("run", "FAKE-RUN"))
        tamper_all3("PAYLOAD_CANONICAL_PIN_MISMATCH", lambda p: p["wave6_provenance"]["pinned_sources"][0].__setitem__("relpath", "FAKE.md"))

        def _forge_f12(p: dict) -> None:
            alt_ts = [Fraction(i, 10) for i in range(9)]
            rows = []
            for t in alt_ts:
                om = oracle.openai_rectangular_omega(Fraction(1), Fraction(1), t)
                cor = max(Fraction(2), Fraction(3, 4) * (2 + t))
                rows.append({
                    "t_q": oracle.fmt_q(t),
                    "omega_q": oracle.fmt_q(om),
                    "omega_dec6": oracle.fmt_dec_q(om, 6),
                    "penalty_above_2_q": oracle.fmt_q(om - 2),
                    "in_linear_o_n2_regime": om == 2,
                    "cor13_lower_bound_q": oracle.fmt_q(cor),
                    "strictly_exceeds_cor13": om > cor,
                })
            p["pillar1_openai_omega94"]["rectangular_1_1_t_curve"] = rows

        tamper_all3("PAYLOAD_CANONICAL_PIN_MISMATCH", _forge_f12)
        tamper_all3("PAYLOAD_CANONICAL_PIN_MISMATCH", lambda p: (
            p["pillar3_law5_reconciliation"]["euclidean_flat_charts"][0].__setitem__("sides_q", ["2", "2", "2"]),
            p["pillar3_law5_reconciliation"]["euclidean_flat_charts"][0].__setitem__("perimeter_q", "6"),
            p["pillar3_law5_reconciliation"]["euclidean_flat_charts"][0].__setitem__("normalized_mean_width_q", "3"),
            p["pillar3_law5_reconciliation"]["euclidean_flat_charts"][0].__setitem__("perimeter_over_mean_width_q", "2"),
            p["pillar3_law5_reconciliation"]["euclidean_flat_charts"][0].__setitem__("gram_det_q", "12"),
        ))

    def test_y_full_replay_and_fr0_pass(self) -> None:
        try:
            verifier.resolve_lean_binary()
            has_lean = True
        except oracle.S93Error:
            has_lean = False
        if has_lean or os.environ.get("ALETHEIA_REQUIRE_LEAN") == "1":
            r_full = verifier.verify_certificate_dict(self.cert, full_replay=True)
            self.assertTrue(r_full["valid"])
            self.assertTrue(r_full["full_replay"])
            self.assertIn("lean_live", r_full)
        else:
            self._assert_s93("LEAN_BINARY_UNAVAILABLE", verifier.verify_certificate_dict, self.cert, full_replay=True)
            lean_sha = oracle.sha256_hex((_THIS_DIR / "OmegaNineFourthsAndSpectrum.lean").read_bytes())
            stub = {"lean_version": "4.36.0", "theorems_verified": len(oracle.LEAN_THEOREM_NAMES), "lean_source_sha256": lean_sha}
            with mock.patch.object(verifier, "verify_lean4_file_live", return_value=stub):
                r_full = verifier.verify_certificate_dict(self.cert, full_replay=True)
                self.assertTrue(r_full["valid"])
                self.assertTrue(r_full["full_replay"])
                self.assertIn("lean_live", r_full)

        r_fr0 = verifier.verify_certificate_dict(self.cert, full_replay=False)
        self.assertTrue(r_fr0["valid"])
        self.assertFalse(r_fr0["full_replay"])
        self.assertNotIn("lean_live", r_fr0)

    def test_z_cli_modes_and_rejections(self) -> None:
        def run_cli(argv) -> tuple[int, str, str]:
            out_buf = io.StringIO()
            err_buf = io.StringIO()
            with mock.patch.object(verifier.sys, "stdout", out_buf), mock.patch.object(verifier.sys, "stderr", err_buf):
                rc = verifier.main(argv)
            return rc, out_buf.getvalue(), err_buf.getvalue()

        with tempfile.TemporaryDirectory() as td:
            out_p = Path(td) / "cert.json"
            try:
                verifier.resolve_lean_binary()
                has_lean = True
            except oracle.S93Error:
                has_lean = False
            if has_lean or os.environ.get("ALETHEIA_REQUIRE_LEAN") == "1":
                rc, out, err = run_cli(["--check", str(_THIS_DIR / "s93_omega94_vpvnp_certificate.json"), "--json"])
                self.assertEqual((rc, err), (0, ""))
                chk_obj = json.loads(out)
                self.assertTrue(chk_obj["valid"])
                live_receipt = chk_obj["lean_live"]
            else:
                rc, out, err = run_cli(["--check", str(_THIS_DIR / "s93_omega94_vpvnp_certificate.json"), "--json"])
                self.assertEqual(rc, 2)
                self.assertEqual(out, "")
                self.assertEqual(json.loads(err)["code"], "LEAN_BINARY_UNAVAILABLE")
                live_receipt = {
                    "lean_version": "4.36.0",
                    "theorems_verified": len(oracle.LEAN_THEOREM_NAMES),
                    "lean_source_sha256": oracle.sha256_hex((_THIS_DIR / "OmegaNineFourthsAndSpectrum.lean").read_bytes()),
                }

            with mock.patch.object(verifier, "verify_lean4_file_live", return_value=live_receipt):
                rc, out, err = run_cli(["--write", str(out_p), "--json"])
                self.assertEqual((rc, err), (0, ""))
                self.assertEqual(stat.S_IMODE(os.lstat(out_p).st_mode), 0o600)
                self.assertTrue(json.loads(out)["written"])

                rc, out, err = run_cli(["--write=" + str(out_p)])
                self.assertEqual((rc, err), (0, ""))
                self.assertTrue(out.startswith("WROTE "))

                rc, out, err = run_cli(["--check=" + str(out_p)])
                self.assertEqual((rc, err), (0, ""))
                self.assertTrue(out.startswith("OK "))

                rc, out, err = run_cli(["--standalone"])
                self.assertEqual((rc, err), (0, ""))
                self.assertEqual(out.encode("ascii"), (_THIS_DIR / "s93_omega94_vpvnp_certificate.json").read_bytes())

                rc, out, err = run_cli([])
                self.assertEqual((rc, err), (0, ""))
                self.assertTrue(out.startswith("OK "))

                rc, out, err = run_cli(["--json"])
                self.assertEqual((rc, err), (0, ""))
                self.assertTrue(json.loads(out)["valid"])

                with mock.patch.object(verifier.sys, "argv", ["verify_s93_omega94_vpvnp.py", "--json"]):
                    rc, out, err = run_cli(None)
                    self.assertEqual((rc, err), (0, ""))
                    self.assertTrue(json.loads(out)["valid"])

            for bad_argv, code in (
                (123, "INVALID_ARGV"),
                (["--json", "--json"], "DUPLICATE_FLAG"),
                (["--standalone", "--check", str(out_p)], "CONFLICTING_MODE"),
                (["--check", str(out_p), "--standalone"], "CONFLICTING_MODE"),
                (["--check", str(out_p), "--write=" + str(out_p)], "CONFLICTING_MODE"),
                (["--check"], "MISSING_PATH_ARG"),
                (["--check", ""], "INVALID_PATH_ARG"),
                (["--check", "-bad"], "INVALID_PATH_ARG"),
                (["--check="], "INVALID_PATH_ARG"),
                (["--write=-bad"], "INVALID_PATH_ARG"),
                (["--unknown"], "UNKNOWN_FLAG"),
                (["--check\x00"], "NUL_BYTE_FORBIDDEN"),
                (["--check", "a\x00b"], "NUL_BYTE_FORBIDDEN"),
                (["--check", "\ud800"], "INVALID_UTF8_SURROGATE"),
            ):
                rc, out, err = run_cli(bad_argv)
                self.assertEqual(rc, 2, f"argv={bad_argv!r}")
                self.assertEqual(out, "")
                self.assertEqual(json.loads(err)["code"], code)
            self._assert_s93("NUL_BYTE_FORBIDDEN", verifier._parse_cli_args, ["--check", "a\x00b"])
            self.assertEqual(verifier._parse_cli_args([])["mode"], "default")


class Test05LeanGatesR10Plus(unittest.TestCase):
    def _assert_s93(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S93Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_strip_and_r10_plus_static_gate(self) -> None:
        lean_src = (_THIS_DIR / "OmegaNineFourthsAndSpectrum.lean").read_text(encoding="utf-8")
        verifier.static_gate_lean4_source(lean_src)
        # Positive controls: zero false positives on clean Lean constructs
        verifier.static_gate_lean4_source(lean_src + "\nprivate theorem _c1 : 1 = 1 := by decide (native := false)\n")
        verifier.static_gate_lean4_source(lean_src + "\nprivate theorem _c2 : 1 = 1 := by decide (native := Bool.false)\n")
        verifier.static_gate_lean4_source(lean_src + "\nprivate theorem _c3 : 1 = 1 := by decide (config := { native := false })\n")
        verifier.static_gate_lean4_source(lean_src + "\nprivate theorem _c4 : 1 = 1 := by decide (config := { native := Bool.false })\n")
        verifier.static_gate_lean4_source(lean_src + "\nexport Nat (succ)\n")
        verifier.static_gate_lean4_source(lean_src + "\nattribute [simp] init\n")
        verifier.static_gate_lean4_source(lean_src + "\ndef _c5 := SmoothShell.partial\n")
        verifier.static_gate_lean4_source(
            lean_src.replace("theorem omega_square_exact_nine_fourths", "private theorem omega_square_exact_nine_fourths")
        )
        verifier.static_gate_lean4_source(
            lean_src.replace("theorem omega_square_exact_nine_fourths", "protected theorem omega_square_exact_nine_fourths")
        )

        stripped = verifier._strip_lean4_for_static_gate(
            "/- outer / - /- sorry -/ -/ -- axiom\n"
            "def x := a / b - c\n"
            "-- eof comment"
        )
        self.assertNotIn("sorry", stripped)
        self.assertNotIn("axiom", stripped)
        self.assertIn("a / b - c", stripped)
        self.assertEqual(verifier._strip_lean4_for_static_gate("/- a - sorry -/\n").strip(), "")
        self.assertEqual(verifier._strip_lean4_for_static_gate("/- a / sorry -/\n").strip(), "")
        self._assert_s93("LEAN4_UNTERMINATED_LEX", verifier._strip_lean4_for_static_gate, "/- unclosed")

        self._assert_s93("LEAN4_BAD_CHARS", verifier.static_gate_lean4_source, lean_src + "\r")
        self._assert_s93("LEAN4_BAD_CHARS", verifier.static_gate_lean4_source, lean_src + "\x00")

        for escape in (
            "\nsorry\n",
            "\nadmit\n",
            "\naxiom bad : Prop\n",
            "\nunsafe def u := 0\n",
            "\ntheorem t : True := by native_decide\n",
            "\ndef s := sorryAx\n",
            "\nset_option debug.skipKernelTC true\n",
            "\nset_option debug.byAsSorry true\n",
            "\nset_option debug.terminalTacticsAsSorry true\n",
            "\ntheorem t : True := by bv_decide\n",
            "\nset_option «debug».«skipKernelTC» true\n",
            "\n@[extern \"c_fn\"] def f : Nat := 0\n",
            "\nattribute [implemented_by f] g\n",
            "\n@[csimp] theorem c : True := trivial\n",
            "\nopaque hidden : Nat := 0\n",
            "\npartial def loop : Nat := loop\n",
            "\ntheorem t : True := by decide +native\n",
            "\nprivate theorem _e1 : 1 = 1 := by decide -revert +native\n",
            "\nprivate theorem _e2 : 1 = 1 := by decide +revert +native\n",
            "\ntheorem t : 1 + 1 = 2 := by decide (native := false || true)\n",
            "\ntheorem t : 1 + 1 = 2 := by decide (native := false == false)\n",
            "\ntheorem t : 1 + 1 = 2 := by decide (native := false != true)\n",
            "\ntheorem t : 1 + 1 = 2 := by decide (native := false.not)\n",
            "\ntheorem t : 1 + 1 = 2 := by decide (native := Bool.false || true)\n",
            "\ntheorem t : 1 + 1 = 2 := by decide (native := false\n  || true)\n",
            "\ntheorem t : 1 = 1 := by decide (config := { native := false || true })\n",
            "\ntheorem t : 1 = 1 := by decide (config := myCfg)\n",
            "\ndef native : Bool := true\ntheorem t : 1 = 1 := by decide +revert (config := { native })\n",
            "\ndef native : Bool := true\ntheorem t : 1 = 1 := by decide (revert := false) (config := { native })\n",
            "\ndef native : Bool := true\ntheorem t : 1 = 1 := by decide +revert (config := { ({} : _) with native })\n",
            "\n#guard_msgs in theorem _gm : True := trivial\n",
            "\ndef cfg : DecideConfig := {}\n",
            "\ntheorem t : True := by decide (native := !false)\n",
            "\n#eval 1 + 1\n",
            "\n#reduce 1\n",
            "\n#exit\n",
            "\n#print Nat\n",
            "\nimport Mathlib\n",
            "\nmacro \"bad\" : term => `(sorry)\n",
            "\nmacro_rules | `(bad) => `(sorry)\n",
            "\nelab \"bad\" : command => pure ()\n",
            "\nsyntax \"bad\" : term\n",
            "\ndeclare_syntax_cat evil\n",
            '\nnotation "openq\\"" => 0\n',
            '\ndef x := s!"{(by sorry : String)}"\n',
            '\ndef _a := r#"""#\naxiom evil : False\ndef _b := r#"""#\n',
            "\ndef q1 : Char := '\"'\n#eval 1\ndef q2 : Char := '\"'\n",
            '\ndbg_trace "{(by sorry : Nat)}"\n',
            "\ndef _dt := dbgTrace\n",
            "\ndef _dt2 := _root_.dbgTrace\n",
            "\ndef _dt3 := dbgTraceVal 0\n",
            "\ndef _dt4 := dbgTraceIfShared\n",
            "\ndef _ds1 := dbgSleep 0\n",
            "\ndef _ds2 := dbgStackTrace\n",
            "\ndef _ds3 := dbg_sleep 0\n",
            "\ndef _ds4 := dbg_stack_trace\n",
            "\ndef _p1 := panic! 0\n",
            "\ndef _p2 := unreachable!\n",
            "\ndef _p3 := panicWithPosWithDecl\n",
            "\nset_option pp.all true\n",
            "\ndef _ws := warn.sorry\n",
            "\n#guard 1 = 1\n",
            "\n@[export c_sym] def _ex : Nat := 0\n",
            "\nattribute [export c_sym] _ex\n",
            "\n@[init] def _in1 : Nat := 0\n",
            "\nattribute [init] _in1\n",
            "\n@[builtin_init] def _in2 : Nat := 0\n",
            "\nattribute [builtin_init] _in2\n",
            "\n@[term_elab _te] def _in3 : Nat := 0\n",
            "\n@[command_elab _ce] def _in4 : Nat := 0\n",
            "\n@[tactic _ta] def _in5 : Nat := 0\n",
            "\n@[macro _ma] def _in6 : Nat := 0\n",
            "\n@[simp\n",
            "\n]\n@[init] def _in7 : Nat := 0\n",
            "\ndef _lc := Lean.Elab.Command.elabCommand\n",
            "\ndef c : Char := '\"'\ntheorem t_char : (1 : Nat) = 2 := sorry\ndef d : Char := '\"'\n",
            "\ntheorem t : False := by «sorry»\n",
        ):
            self._assert_s93("LEAN4_TRUST_ESCAPE", verifier.static_gate_lean4_source, lean_src + escape)

        self._assert_s93(
            "LEAN4_MISSING_THEOREM",
            verifier.static_gate_lean4_source,
            lean_src.replace("theorem omega_square_exact_nine_fourths", "theorem renamed_thm"),
        )
        self._assert_s93(
            "LEAN4_MISSING_THEOREM",
            verifier.static_gate_lean4_source,
            lean_src.replace("theorem omega_square_exact_nine_fourths", "theorem omega_square_exact_nine_fourths_extra"),
        )
        self._assert_s93(
            "LEAN4_MISSING_PRINT_AXIOMS",
            verifier.static_gate_lean4_source,
            lean_src.replace("#print axioms OmegaNineFourthsAndSpectrum.omega_square_exact_nine_fourths", ""),
        )

    def test_resolve_and_verify_lean_live_and_mocked(self) -> None:
        try:
            verifier.resolve_lean_binary()
            has_lean = True
        except oracle.S93Error:
            has_lean = False
        poison_keys = (
            "LEAN_PATH",
            "LEAN_OPTS",
            "LEAN_SRC_PATH",
            "LEAN_SYSROOT",
            "ELAN_TOOLCHAIN",
            "ELAN_HOME",
            "LAKE_HOME",
            "LEAN_CC",
            "LD_PRELOAD",
            "LD_LIBRARY_PATH",
            "DYLD_INSERT_LIBRARIES",
            "S93_UNLISTED_AMBIENT",
        )
        poison_env = {k: "/nonexistent/s93_poison" for k in poison_keys}
        poison_env["LANG"] = "C"
        if has_lean or os.environ.get("ALETHEIA_REQUIRE_LEAN") == "1":
            with mock.patch.dict(os.environ, poison_env):
                live = verifier.verify_lean4_file_live(_THIS_DIR / "OmegaNineFourthsAndSpectrum.lean")
            self.assertEqual(live["theorems_verified"], len(oracle.LEAN_THEOREM_NAMES))
            self.assertIn("4.36.0", live["lean_version"])
        else:
            self._assert_s93("LEAN_BINARY_UNAVAILABLE", verifier.verify_lean4_file_live, _THIS_DIR / "OmegaNineFourthsAndSpectrum.lean")

        with tempfile.TemporaryDirectory() as td:
            fake_bin = Path(td) / "lean"
            fake_bin.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(fake_bin, 0o700)
            noexec_bin = Path(td) / "lean_noexec"
            noexec_bin.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(noexec_bin, 0o600)
            dir_bin = Path(td) / "lean_dir"
            dir_bin.mkdir(mode=0o700)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(fake_bin)}):
                self.assertEqual(verifier.resolve_lean_binary(), str(fake_bin))
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(Path(td) / "missing")}):
                self._assert_s93("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(noexec_bin)}):
                self._assert_s93("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(dir_bin)}):
                self._assert_s93("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)

            home_d = Path(td) / "h"
            (home_d / ".local" / "bin" / "lean").mkdir(parents=True)
            (home_d / ".elan" / "bin").mkdir(parents=True)
            elan_lean = home_d / ".elan" / "bin" / "lean"
            elan_lean.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(elan_lean, 0o600)

            with mock.patch.dict(os.environ, {"HOME": str(home_d)}, clear=True):
                with mock.patch.object(verifier.shutil, "which", return_value=str(fake_bin)):
                    self.assertEqual(verifier.resolve_lean_binary(), str(fake_bin))
                with mock.patch.object(verifier.shutil, "which", return_value=str(noexec_bin)):
                    self._assert_s93("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
                os.chmod(elan_lean, 0o700)
                with mock.patch.object(verifier.shutil, "which", return_value=None):
                    self.assertEqual(verifier.resolve_lean_binary(), str(elan_lean))
                os.unlink(elan_lean)
                with mock.patch.object(verifier.shutil, "which", return_value=None):
                    self._assert_s93("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
            (home_d / ".elan" / "bin" / "lean").write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(home_d / ".elan" / "bin" / "lean", 0o700)
            old_cwd = os.getcwd()
            try:
                os.chdir(home_d)
                with mock.patch.dict(os.environ, {"HOME": ""}, clear=True):
                    with mock.patch.object(verifier.shutil, "which", return_value=None):
                        self._assert_s93("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
            finally:
                os.chdir(old_cwd)
            os.unlink(home_d / ".elan" / "bin" / "lean")
            with mock.patch.dict(os.environ, {}, clear=True):
                with mock.patch.object(verifier.shutil, "which", return_value=None):
                    self._assert_s93("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)

            bad_utf8 = Path(td) / "bad.lean"
            bad_utf8.write_bytes(b"\xff\xfe")
            self._assert_s93("INVALID_UTF8", verifier.verify_lean4_file_live, bad_utf8)

        lean_path = _THIS_DIR / "OmegaNineFourthsAndSpectrum.lean"
        ok_ver = subprocess.CompletedProcess(["lean", "--version"], 0, "Lean (version 4.36.0, x86_64)\n", "")
        good_lines = [f"'{t}' depends on axioms: [propext, Quot.sound]" for t in oracle.LEAN_THEOREM_NAMES]
        good_lines[0] = f"'{oracle.LEAN_THEOREM_NAMES[0]}' does not depend on any axioms"
        good_lines[1] = f"'{oracle.LEAN_THEOREM_NAMES[1]}' depends on axioms: [\n  propext,\n  Quot.sound\n]"
        ok_run = subprocess.CompletedProcess(["lean", str(lean_path)], 0, "\n\n" + "\n".join(good_lines) + "\n", "")

        with mock.patch.object(verifier, "resolve_lean_binary", return_value="/bin/lean"):
            with mock.patch.dict(os.environ, poison_env):
                with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, ok_run]) as m_run:
                    res = verifier.verify_lean4_file_live(lean_path)
                    self.assertEqual(res["theorems_verified"], len(oracle.LEAN_THEOREM_NAMES))
                    self.assertEqual(m_run.call_count, 2)
                    for c in m_run.call_args_list:
                        passed_env = c.kwargs["env"]
                        self.assertEqual(passed_env.get("LANG"), "C")
                        self.assertTrue(set(passed_env.keys()) <= verifier.SAFE_LEAN_ENV_KEYS)
                        for bad_k in poison_keys:
                            self.assertNotIn(bad_k, passed_env)
            with mock.patch.object(verifier.subprocess, "run", side_effect=OSError("no exec")):
                self._assert_s93("LEAN_EXEC_ERROR", verifier.verify_lean4_file_live, lean_path)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[subprocess.CompletedProcess([], 1, "4.36.0", "")]):
                self._assert_s93("LEAN_VERSION_MISMATCH", verifier.verify_lean4_file_live, lean_path)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[subprocess.CompletedProcess([], 0, "Lean 4.10.0", "")]):
                self._assert_s93("LEAN_VERSION_MISMATCH", verifier.verify_lean4_file_live, lean_path)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.TimeoutExpired(["lean"], 1)]):
                self._assert_s93("LEAN_EXEC_ERROR", verifier.verify_lean4_file_live, lean_path)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.CompletedProcess([], 1, "", "")]):
                self._assert_s93("LEAN_COMPILE_FAIL", verifier.verify_lean4_file_live, lean_path)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.CompletedProcess([], 0, "", "err")]):
                self._assert_s93("LEAN_STDERR_NONEMPTY", verifier.verify_lean4_file_live, lean_path)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.CompletedProcess([], 0, "warning: x", "")]):
                self._assert_s93("LEAN_WARNING_FORBIDDEN", verifier.verify_lean4_file_live, lean_path)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.CompletedProcess([], 0, "'X' depends on axioms: [propext\n", "")]):
                self._assert_s93("LEAN_UNEXPECTED_STDOUT", verifier.verify_lean4_file_live, lean_path)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.CompletedProcess([], 0, "garbage\n", "")]):
                self._assert_s93("LEAN_UNEXPECTED_STDOUT", verifier.verify_lean4_file_live, lean_path)
            dup_none = f"'{oracle.LEAN_THEOREM_NAMES[0]}' does not depend on any axioms\n" * 2
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.CompletedProcess([], 0, dup_none, "")]):
                self._assert_s93("LEAN_DUPLICATE_THEOREM", verifier.verify_lean4_file_live, lean_path)
            dup_dep = f"'{oracle.LEAN_THEOREM_NAMES[0]}' depends on axioms: [propext]\n" * 2
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.CompletedProcess([], 0, dup_dep, "")]):
                self._assert_s93("LEAN_DUPLICATE_THEOREM", verifier.verify_lean4_file_live, lean_path)
            bad_ax = f"'{oracle.LEAN_THEOREM_NAMES[0]}' depends on axioms: [Classical.choice]\n"
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.CompletedProcess([], 0, bad_ax, "")]):
                self._assert_s93("LEAN_FORBIDDEN_AXIOM", verifier.verify_lean4_file_live, lean_path)
            short_out = f"'{oracle.LEAN_THEOREM_NAMES[0]}' does not depend on any axioms\n"
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.CompletedProcess([], 0, short_out, "")]):
                self._assert_s93("LEAN_THEOREM_SET_MISMATCH", verifier.verify_lean4_file_live, lean_path)


if __name__ == "__main__":
    unittest.main()
