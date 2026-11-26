#!/usr/bin/env python3
"""Track S103: Assertion-Free R5 Verification, Field-Complete Re-Signed SEC/FR0/FR1
Tamper Matrix, Zone-B I/O, Full R12 Lean Escape & Clean-Control Suite, and
Zero-Skip Dual-Environment Test Suite.
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

import s103_exoplanets_oracle as oracle  # noqa: E402
import verify_s103_exoplanets as verifier  # noqa: E402


class Test01HygieneAndOraclePrimitives(unittest.TestCase):
    def _assert_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S103Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_static_hygiene_and_disk_cert(self) -> None:
        home_tok = b"/" + b"home/"
        devnull_tok = b"/" + b"dev/null"
        for name in ("s103_exoplanets_oracle.py", "verify_s103_exoplanets.py", "test_s103_exoplanets_r5.py"):
            raw = (_THIS_DIR / name).read_bytes()
            self.assertNotIn(b"\r", raw)
            self.assertNotIn(home_tok, raw)
            self.assertNotIn(devnull_tok, raw)
            tree = ast.parse(raw.decode("utf-8"))
            for node in ast.walk(tree):
                self.assertFalse(isinstance(node, ast.Assert), f"bare assert in {name}")
                if name != "test_s103_exoplanets_r5.py":
                    if isinstance(node, ast.Constant):
                        self.assertFalse(type(node.value) is float, f"float literal in {name}")
                    if isinstance(node, ast.Name):
                        self.assertNotEqual(node.id, "float")
                    if isinstance(node, ast.Attribute):
                        self.assertNotEqual(node.attr, "isdigit")
        raw_cert = (_THIS_DIR / "s103_exoplanets_certificate.json").read_bytes()
        cert = verifier.parse_strict_json_bytes(raw_cert, "disk_cert", require_canonical=True)
        self.assertEqual(cert["track_id"], oracle.TRACK_ID)
        self.assertEqual(cert["payload"]["pinned_artifacts"]["lean_theorem_count"], 19)
        self.assertEqual(cert["payload"]["external_provenance"]["pinned_external_count"], 16)
        self.assertEqual(cert["payload"]["external_provenance"]["upstream_bridges_count"], 6)
        buf = io.StringIO()
        with mock.patch.object(sys, "stdout", buf):
            self.assertEqual(oracle.main(), 0)
        self.assertEqual(buf.getvalue().encode("ascii"), raw_cert)

    def test_guards_tree_formatters_and_math_primitives(self) -> None:
        oracle.require_ok(True, "E", "ok")
        self._assert_err("E", oracle.require_ok, False, "E", "no")
        self._assert_err("E", oracle.require_ok, 1, "E", "no")
        self.assertTrue(oracle.require_bool(True, "b"))
        self.assertFalse(oracle.require_bool(False, "b"))
        self._assert_err("INVALID_BOOL", oracle.require_bool, 1, "b")
        self.assertEqual(oracle.require_exact_int(5, "n", lo=5, hi=5), 5)
        self._assert_err("INVALID_INT", oracle.require_exact_int, True, "n")
        self._assert_err("INT_OUT_OF_RANGE", oracle.require_exact_int, 4, "n", lo=5)
        self._assert_err("INT_OUT_OF_RANGE", oracle.require_exact_int, 6, "n", hi=5)
        self.assertEqual(oracle.require_exact_str("x", "s"), "x")
        self._assert_err("INVALID_STR", oracle.require_exact_str, 7, "s")
        hx = "0123456789abcdef" * 4
        self.assertEqual(oracle.require_hex64(hx, "h"), hx)
        self._assert_err("INVALID_HEX64", oracle.require_hex64, "ab", "h")
        self._assert_err("INVALID_HEX64", oracle.require_hex64, "A" * 64, "h")

        oracle.validate_strict_json_tree({"a": [1, "s", True, False, None, (1 << 2047)]})
        self._assert_err("INT_BIT_LIMIT", oracle.validate_strict_json_tree, {"a": 1 << 2048})
        self._assert_err("INVALID_JSON_KEY", oracle.validate_strict_json_tree, {1: "a"})
        self._assert_err("FORBIDDEN_JSON_TYPE", oracle.validate_strict_json_tree, {"a": (1, 2)})
        ok_deep: dict = {}
        cur = ok_deep
        for _ in range(32):
            nxt: dict = {}
            cur["k"] = nxt
            cur = nxt
        oracle.validate_strict_json_tree(ok_deep)
        cur["k"] = {}
        self._assert_err("JSON_DEPTH_EXCEEDED", oracle.validate_strict_json_tree, ok_deep)

        self.assertEqual(oracle.fmt_q(Fraction(4, 1)), "4")
        self.assertEqual(oracle.fmt_q(Fraction(-3, 4)), "-3/4")
        self._assert_err("INVALID_FRACTION", oracle.fmt_q, 4)
        self.assertEqual(oracle.fmt_dec_q(Fraction(1, 2), 0), "1")
        self.assertEqual(oracle.fmt_dec_q(Fraction(-1, 2), 0), "-1")
        self.assertEqual(oracle.fmt_dec_q(Fraction(-1, 100), 0), "0")
        self.assertEqual(oracle.fmt_dec_q(Fraction(0, 1), 0), "0")
        self.assertEqual(oracle.fmt_dec_q(Fraction(-1, 1000), 2), "0.00")
        self.assertEqual(oracle.fmt_dec_q(Fraction(-3, 4), 2), "-0.75")
        self.assertEqual(oracle.fmt_dec_q(Fraction(1, 8), 2), "0.13")
        self.assertEqual(oracle.fmt_dec_q(Fraction(1, 3), 4), "0.3333")
        self._assert_err("INVALID_FRACTION", oracle.fmt_dec_q, 1, 2)
        self._assert_err("INT_OUT_OF_RANGE", oracle.fmt_dec_q, Fraction(1, 2), -1)
        self._assert_err("INT_OUT_OF_RANGE", oracle.fmt_dec_q, Fraction(1, 2), 19)

        # Pure-Q math primitives & boundaries
        self.assertTrue(oracle.both_ok(True, True))
        self.assertFalse(oracle.both_ok(True, False))
        self.assertFalse(oracle.both_ok(False, True))
        self.assertFalse(oracle.both_ok(False, False))
        self.assertEqual(oracle.farey_separation_q(1, 2, 2, 3), (1, Fraction(1, 6)))
        self._assert_err("INVALID_FAREY_ORDER", oracle.farey_separation_q, 2, 3, 1, 2)
        self._assert_err("INVALID_FAREY_ORDER", oracle.farey_separation_q, 1, 2, 1, 2)
        self._assert_err("INT_OUT_OF_RANGE", oracle.farey_separation_q, -1, 2, 1, 2)
        self._assert_err("INT_OUT_OF_RANGE", oracle.farey_separation_q, 1, 0, 1, 2)
        self.assertEqual(oracle.sde_exact_q(Fraction(50), Fraction(10), Fraction(4)), Fraction(10))
        self._assert_err("INVALID_MAD", oracle.sde_exact_q, Fraction(50), Fraction(10), Fraction(0))
        self.assertEqual(oracle.pont_beta_sq_q(12, Fraction(1, 2)), Fraction(4))
        self.assertEqual(oracle.pont_beta_sq_q(1, Fraction(0)), Fraction(1))
        self._assert_err("INT_OUT_OF_RANGE", oracle.pont_beta_sq_q, 0, Fraction(1, 2))
        self._assert_err("INVALID_RED_RATIO", oracle.pont_beta_sq_q, 1, Fraction(-1, 2))
        self.assertEqual(oracle.bayes_fpp_q(Fraction(1, 2), Fraction(1, 2), Fraction(1), Fraction(1)), Fraction(1, 2))
        self._assert_err("INVALID_BAYES_ARGS", oracle.bayes_fpp_q, Fraction(0), Fraction(1), Fraction(1), Fraction(1))
        self._assert_err("INVALID_BAYES_ARGS", oracle.bayes_fpp_q, Fraction(1), Fraction(0), Fraction(1), Fraction(1))
        self._assert_err("INVALID_BAYES_ARGS", oracle.bayes_fpp_q, Fraction(1), Fraction(1), Fraction(0), Fraction(1))
        self._assert_err("INVALID_BAYES_ARGS", oracle.bayes_fpp_q, Fraction(1), Fraction(1), Fraction(1), Fraction(0))

        # Linear solver: pivot swap, singular, regular
        det_sw, sol_sw = oracle.solve_nonsingular_q([[Fraction(0), Fraction(1)], [Fraction(1), Fraction(0)]], [Fraction(3), Fraction(5)])
        self.assertEqual((det_sw, sol_sw), (Fraction(-1), [Fraction(5), Fraction(3)]))
        self.assertEqual(oracle.exact_det_and_solve_q([[Fraction(1), Fraction(1)], [Fraction(1), Fraction(1)]], [Fraction(1), Fraction(1)]), (Fraction(0), None))
        self._assert_err("SINGULAR_SYSTEM", oracle.solve_nonsingular_q, [[Fraction(1), Fraction(1)], [Fraction(1), Fraction(1)]], [Fraction(1), Fraction(1)])


class Test02ZoneBIOAndStrictParsers(unittest.TestCase):
    def _assert_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S103Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_paths_cwd_and_file_io(self) -> None:
        self.assertEqual(verifier._normalize_darwin_private_prefix("/private/tmp"), "/tmp")
        self.assertEqual(verifier._normalize_darwin_private_prefix("/private/tmp/x"), "/tmp/x")
        self.assertEqual(verifier._normalize_darwin_private_prefix("/private/var"), "/var")
        self.assertEqual(verifier._normalize_darwin_private_prefix("/private/var/x"), "/var/x")
        self.assertEqual(verifier._normalize_darwin_private_prefix("/private/tmp2"), "/private/tmp2")
        self.assertEqual(verifier._normalize_darwin_private_prefix("/private/var2"), "/private/var2")
        self.assertEqual(verifier._check_path_str(Path("ok"), "p"), Path("ok"))
        self._assert_err("INVALID_STR", verifier._check_path_str, 7, "p")
        self._assert_err("EMPTY_PATH", verifier._check_path_str, "", "p")
        self._assert_err("NUL_BYTE_FORBIDDEN", verifier._check_path_str, "a\x00b", "p")
        self._assert_err("INVALID_UTF8_SURROGATE", verifier._check_path_str, "\ud800", "p")

        verifier._check_safe_cwd()
        with mock.patch.object(verifier.os, "getcwd", side_effect=OSError("gone")):
            self._assert_err("CWD_ERROR", verifier._check_safe_cwd)
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            real_d = tdp / "real"
            real_d.mkdir()
            sym_d = tdp / "sym"
            os.symlink(real_d, sym_d)
            with mock.patch.object(verifier.os, "getcwd", return_value=str(real_d)), mock.patch.dict(os.environ, {"PWD": str(sym_d)}):
                self._assert_err("SYMLINK_IN_PATH", verifier._check_safe_cwd)
            self_sym = real_d / "self_sym"
            os.symlink(real_d, self_sym)
            old_cwd = os.getcwd()
            try:
                os.chdir(real_d)
                with mock.patch.dict(os.environ, {"PWD": "self_sym"}):
                    verifier._check_safe_cwd()
                with mock.patch.dict(os.environ, {"PWD": ""}):
                    verifier._check_safe_cwd()
            finally:
                os.chdir(old_cwd)
            with mock.patch.object(verifier.os, "getcwd", return_value=str(real_d)), mock.patch.dict(os.environ, {"PWD": str(tdp / "missing")}):
                verifier._check_safe_cwd()
            other_d = tdp / "other"
            other_d.mkdir()
            sym_o = tdp / "sym_o"
            os.symlink(other_d, sym_o)
            with mock.patch.object(verifier.os, "getcwd", return_value=str(real_d)), mock.patch.dict(os.environ, {"PWD": str(sym_o)}):
                verifier._check_safe_cwd()
            st_r = os.stat(real_d)
            fake_dev = os.stat_result((st_r.st_mode, st_r.st_ino, st_r.st_dev + 99, 1, 0, 0, 0, 0, 0, 0))
            with mock.patch.object(verifier.os, "getcwd", return_value=str(real_d)), mock.patch.dict(os.environ, {"PWD": str(sym_d)}), mock.patch.object(verifier.os, "stat", side_effect=[fake_dev, st_r]):
                verifier._check_safe_cwd()
            with mock.patch.dict(os.environ, {k: v for k, v in os.environ.items() if k != "PWD"}, clear=True):
                verifier._check_safe_cwd()
            with mock.patch.object(verifier.os, "lstat", side_effect=PermissionError("no")):
                self._assert_err("IO_STAT_ERROR", verifier._check_no_symlink_components, Path("/tmp/a"), "p")

            reg = tdp / "ok.json"
            self.assertEqual(verifier.write_regular_bytes_atomic_0600(reg, b'{"a":1}\n', "w"), reg)
            self.assertEqual(stat.S_IMODE(os.lstat(reg).st_mode), 0o600)
            self.assertEqual(verifier.read_regular_bytes_capped(reg, "r", max_bytes=8), b'{"a":1}\n')
            self._assert_err("FILE_TOO_LARGE", verifier.read_regular_bytes_capped, reg, "r", max_bytes=7)
            self._assert_err("INT_OUT_OF_RANGE", verifier.read_regular_bytes_capped, reg, "r", max_bytes=0)
            self._assert_err("INT_OUT_OF_RANGE", verifier.read_regular_bytes_capped, reg, "r", max_bytes=64 * 1024 * 1024 + 1)
            zero_st = os.stat_result((stat.S_IFREG | 0o600, 1, 1, 1, 0, 0, 0, 0, 0, 0))
            with mock.patch.object(verifier.os, "fstat", return_value=zero_st):
                self._assert_err("FILE_TOO_LARGE", verifier.read_regular_bytes_capped, reg, "r", max_bytes=4)
            emp = tdp / "empty.json"
            emp.write_bytes(b"")
            big_st = os.stat_result((stat.S_IFREG | 0o600, 1, 1, 1, 0, 0, 100, 0, 0, 0))
            with mock.patch.object(verifier.os, "fstat", return_value=big_st):
                self._assert_err("FILE_TOO_LARGE", verifier.read_regular_bytes_capped, emp, "r", max_bytes=8)

            sym = tdp / "sym.json"
            os.symlink(reg, sym)
            self._assert_err("SYMLINK_IN_PATH", verifier.read_regular_bytes_capped, sym, "r")
            self._assert_err("SYMLINK_IN_PATH", verifier.write_regular_bytes_atomic_0600, sym, b"x", "w")
            hl = tdp / "hl.json"
            os.link(reg, hl)
            self._assert_err("HARDLINK_FORBIDDEN", verifier.read_regular_bytes_capped, hl, "r")
            self._assert_err("HARDLINK_FORBIDDEN", verifier.write_regular_bytes_atomic_0600, hl, b"x", "w")
            os.unlink(hl)
            fifo = tdp / "pipe"
            os.mkfifo(fifo)
            self._assert_err("NOT_REGULAR_FILE", verifier.read_regular_bytes_capped, fifo, "r")
            self._assert_err("TARGET_NOT_REGULAR", verifier.write_regular_bytes_atomic_0600, fifo, b"x", "w")
            self._assert_err("IO_OPEN_ERROR", verifier.read_regular_bytes_capped, tdp / "missing.json", "r")
            self._assert_err("INVALID_BYTES", verifier.write_regular_bytes_atomic_0600, reg, "bad", "w")
            self._assert_err("PARENT_MISSING", verifier.write_regular_bytes_atomic_0600, tdp / "no_dir" / "a", b"x", "w")
            self._assert_err("PARENT_NOT_DIR", verifier.write_regular_bytes_atomic_0600, reg / "c", b"x", "w")
            with mock.patch.object(verifier, "_check_no_symlink_components", return_value=reg), mock.patch.object(verifier.os, "lstat", side_effect=[os.lstat(tdp), PermissionError("e")]):
                self._assert_err("IO_STAT_ERROR", verifier.write_regular_bytes_atomic_0600, reg, b"x", "w")
            with mock.patch.object(verifier.os, "open", side_effect=OSError("no")):
                self._assert_err("IO_OPEN_ERROR", verifier.write_regular_bytes_atomic_0600, reg, b"x", "w")
            with mock.patch.object(verifier.os, "write", return_value=0):
                self._assert_err("IO_WRITE_ERROR", verifier.write_regular_bytes_atomic_0600, tdp / "w1", b"abc", "w")
            with mock.patch.object(verifier.os, "write", return_value=0), mock.patch.object(verifier.os, "unlink", side_effect=OSError("u")):
                self._assert_err("IO_WRITE_ERROR", verifier.write_regular_bytes_atomic_0600, tdp / "w2", b"abc", "w")
            bad_m = os.stat_result((stat.S_IFIFO | 0o600, 1, 1, 1, 0, 0, 1, 0, 0, 0))
            with mock.patch.object(verifier.os, "fstat", return_value=bad_m):
                self._assert_err("TMP_TAMPERED", verifier.write_regular_bytes_atomic_0600, tdp / "w3", b"x", "w")
            bad_n = os.stat_result((stat.S_IFREG | 0o600, 1, 1, 2, 0, 0, 1, 0, 0, 0))
            with mock.patch.object(verifier.os, "fstat", return_value=bad_n):
                self._assert_err("TMP_TAMPERED", verifier.write_regular_bytes_atomic_0600, tdp / "w4", b"x", "w")

    def test_strict_json_and_rational_parsers(self) -> None:
        self.assertEqual(verifier.parse_strict_json_bytes(b'{"a":1}\n', "j"), {"a": 1})
        self.assertEqual(verifier.parse_strict_json_bytes(b'{ "a": 1 }', "j", require_canonical=False), {"a": 1})
        self._assert_err("INVALID_BYTES", verifier.parse_strict_json_bytes, "str", "j")
        self._assert_err("JSON_TOO_LARGE", verifier.parse_strict_json_bytes, b" " * (verifier.MAX_JSON_BYTES + 1), "j")
        pre, suf = b'{"a":"', b'"}\n'
        pad = b"x" * (verifier.MAX_JSON_BYTES - len(pre) - len(suf))
        self.assertEqual(len(verifier.parse_strict_json_bytes(pre + pad + suf, "jm")["a"]), len(pad))
        self._assert_err("JSON_BAD_BYTES", verifier.parse_strict_json_bytes, b'{"a":1}\r\n', "j")
        self._assert_err("JSON_BAD_BYTES", verifier.parse_strict_json_bytes, b'{"a":1}\x00', "j")
        self._assert_err("NON_ASCII_JSON", verifier.parse_strict_json_bytes, b'{"a":"\xc3\xa9"}\n', "j")
        self._assert_err("FORBIDDEN_JSON_FLOAT", verifier.parse_strict_json_bytes, b'{"a":1.5}\n', "j")
        self._assert_err("FORBIDDEN_JSON_CONST", verifier.parse_strict_json_bytes, b'{"a":NaN}\n', "j")
        self._assert_err("DUPLICATE_JSON_KEY", verifier.parse_strict_json_bytes, b'{"a":1,"a":2}\n', "j")
        self._assert_err("NON_CANONICAL_JSON", verifier.parse_strict_json_bytes, b'{ "a": 1 }\n', "j")
        self._assert_err("INVALID_JSON", verifier.parse_strict_json_bytes, b"{bad", "j")
        big_i = ("9" * (verifier.MAX_JSON_INT_DIGITS + 1)).encode("ascii")
        self._assert_err("JSON_INT_TOO_LARGE", verifier.parse_strict_json_bytes, b'{"a":' + big_i + b"}\n", "j")
        self._assert_err("JSON_INT_TOO_LARGE", verifier.parse_strict_json_bytes, b'{"a":-' + big_i + b"}\n", "j")
        self._assert_err("JSON_INT_TOO_LARGE", verifier.parse_strict_json_bytes, b"{" + big_i, "j")
        ok_i = ("9" * verifier.MAX_JSON_INT_DIGITS).encode("ascii")
        self.assertEqual(verifier.parse_strict_json_bytes(b'{"a":-' + ok_i + b"}\n", "j")["a"], -int(ok_i))
        self._assert_err("JSON_INT_TOO_LARGE", verifier._strict_int_parse, "9" * (verifier.MAX_JSON_INT_DIGITS + 1))
        self._assert_err("INVALID_JSON_INT", verifier._strict_int_parse, "01")
        self.assertEqual(verifier.parse_canonical_rational_str("0", "q"), Fraction(0))
        self.assertEqual(verifier.parse_canonical_rational_str("-3/4", "q"), Fraction(-3, 4))
        max_rat = "-" + "9" * 80 + "/" + "1" + "0" * 79
        self.assertEqual(len(max_rat), verifier.MAX_RATIONAL_STR_LEN)
        self.assertEqual(verifier.parse_canonical_rational_str(max_rat, "q"), Fraction(-(10 ** 80 - 1), 10 ** 79))
        self._assert_err("RATIONAL_TOO_LARGE", verifier.parse_canonical_rational_str, "9" * (verifier.MAX_RATIONAL_STR_LEN + 1), "q")
        self._assert_err("RATIONAL_TOO_LARGE", verifier.parse_canonical_rational_str, "9" * 5000, "q")
        self._assert_err("RATIONAL_TOO_LARGE", verifier.parse_canonical_rational_str, "1/" + "9" * 5000, "q")
        self._assert_err("INVALID_RATIONAL_STR", verifier.parse_canonical_rational_str, "+1/2", "q")
        self._assert_err("INVALID_RATIONAL_STR", verifier.parse_canonical_rational_str, "1/0", "q")
        self._assert_err("NON_CANONICAL_RATIONAL", verifier.parse_canonical_rational_str, "3/1", "q")
        self._assert_err("NON_REDUCED_RATIONAL", verifier.parse_canonical_rational_str, "2/4", "q")
        self._assert_err("INVALID_DICT", verifier._require_exact_dict, [], frozenset(), "d")
        self._assert_err("KEYSET_MISMATCH", verifier._require_exact_dict, {"a": 1}, frozenset({"b"}), "d")


class Test03FieldCompleteTamperAndCLI(unittest.TestCase):
    def setUp(self) -> None:
        self.cert = json.loads((_THIS_DIR / "s103_exoplanets_certificate.json").read_text(encoding="ascii"))

    def _assert_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S103Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def _resign(self, payload: dict) -> dict:
        psha = oracle.sha256_hex(oracle.canonical_json_bytes(payload))
        core = {"schema_version": oracle.SCHEMA_VERSION, "track_id": oracle.TRACK_ID, "payload_sha256": psha, "payload": payload}
        return {**core, "certificate_sha256": oracle.sha256_hex(oracle.canonical_json_bytes(core))}

    def test_sec_fr0_fr1_exhaustive_tamper_matrix(self) -> None:
        base = self.cert["payload"]
        self.assertTrue(verifier.secondary_audit_payload(base)["secondary_audit_passed"])
        self._assert_err("INVALID_PAYLOAD_TYPE", verifier.secondary_audit_payload, [])

        def tamper(code: str, mut_fn) -> None:
            p = copy.deepcopy(base)
            mut_fn(p)
            self._assert_err(code, verifier.secondary_audit_payload, p)
            self._assert_err(code, verifier.verify_certificate_dict, self._resign(p), full_replay=False)

        # Top-level, provenance, artifacts
        tamper("SCHEMA_MISMATCH", lambda p: p.__setitem__("schema_version", "x"))
        tamper("SCHEMA_MISMATCH", lambda p: p.__setitem__("track_id", "x"))
        tamper("SCHEMA_MISMATCH", lambda p: p.__setitem__("oracle_class", "approx"))
        tamper("SCHEMA_MISMATCH", lambda p: p.__setitem__("novelty_classification", "N2"))
        tamper("INT_OUT_OF_RANGE", lambda p: p.__setitem__("n2_claims", 1))
        tamper("PROV_EXT_LEN", lambda p: p["external_provenance"].__setitem__("pinned_external_files", "x" * 16))
        tamper("PROV_EXT_LEN", lambda p: p["external_provenance"].__setitem__("pinned_external_files", []))
        tamper("PROV_EXT_PIN", lambda p: p["external_provenance"]["pinned_external_files"][0].__setitem__("relpath", "fake.md"))
        tamper("PROV_UP_LEN", lambda p: p["external_provenance"].__setitem__("upstream_expedition_bridges", "x" * 6))
        tamper("PROV_UP_LEN", lambda p: p["external_provenance"].__setitem__("upstream_expedition_bridges", []))
        tamper("PROV_UP_PIN", lambda p: p["external_provenance"]["upstream_expedition_bridges"][0].__setitem__("bridge", ""))
        tamper("PROV_UP_PIN", lambda p: p["external_provenance"]["upstream_expedition_bridges"][0].__setitem__("bridge", "FORGED bridge"))
        tamper("PROV_UP_PIN", lambda p: p["external_provenance"]["upstream_expedition_bridges"][0].__setitem__("cert_sha256", "0" * 64))
        tamper("SCHEMA_MISMATCH", lambda p: p["pinned_artifacts"].__setitem__("lean_source", "x.lean"))
        tamper("SCHEMA_MISMATCH", lambda p: p["pinned_artifacts"].__setitem__("lean_toolchain", "bad"))
        tamper("PINNED_SHA_MISMATCH", lambda p: p["pinned_artifacts"].__setitem__("lean_source_sha256", "0" * 64))
        tamper("THEOREM_LIST_MISMATCH", lambda p: p["pinned_artifacts"].__setitem__("lean_theorem_names", {t: 0 for t in oracle.LEAN_THEOREM_NAMES}))
        tamper("THEOREM_LIST_MISMATCH", lambda p: p["pinned_artifacts"].__setitem__("lean_theorem_names", ["x"] * 19))

        # Pillar 1
        tamper("P1_COMMIT", lambda p: p["pillar1_sop9_exoplanets_frontier_audit"].__setitem__("main_commit", "0" * 40))
        tamper("P1_SYNTAX", lambda p: p["pillar1_sop9_exoplanets_frontier_audit"].__setitem__("cool_vet_main_syntax_error", False))
        tamper("P1_STALE_LIST", lambda p: p["pillar1_sop9_exoplanets_frontier_audit"].__setitem__("claims_stale_artifacts", ["a"]))
        tamper("P1_BLIND_SNR", lambda p: p["pillar1_sop9_exoplanets_frontier_audit"]["blind_s106_s107_audit"].__setitem__("inverted_artifact_snr_q", "0"))
        tamper("RATIONAL_TOO_LARGE", lambda p: p["pillar1_sop9_exoplanets_frontier_audit"]["blind_s106_s107_audit"].__setitem__("inverted_artifact_snr_q", "9" * 5000))
        tamper("RATIONAL_TOO_LARGE", lambda p: p["pillar1_sop9_exoplanets_frontier_audit"]["blind_s106_s107_audit"].__setitem__("inverted_artifact_snr_q", "1/" + "9" * 5000))
        tamper("P1_PR8_TICS", lambda p: p["pillar1_sop9_exoplanets_frontier_audit"]["pr8_cool_audit_findings"].__setitem__("survivor_tics", [1, 2]))
        tamper("P1_PR8_PUSH", lambda p: p["pillar1_sop9_exoplanets_frontier_audit"]["pr8_cool_audit_findings"].__setitem__("unguarded_main_push", False))
        tamper("P1_PR6_17", lambda p: p["pillar1_sop9_exoplanets_frontier_audit"]["pr6_issue5_synthetic_control"].__setitem__("seeded_17d_mes_q", "1"))
        tamper("P1_PR6_17", lambda p: p["pillar1_sop9_exoplanets_frontier_audit"]["pr6_issue5_synthetic_control"].__setitem__("seeded_17d_sde_q", "1"))
        tamper("P1_PR6_25", lambda p: p["pillar1_sop9_exoplanets_frontier_audit"]["pr6_issue5_synthetic_control"].__setitem__("seeded_25d_mes_q", "1"))
        tamper("P1_PR6_25", lambda p: p["pillar1_sop9_exoplanets_frontier_audit"]["pr6_issue5_synthetic_control"].__setitem__("seeded_25d_sde_q", "1"))
        tamper("P1_PR6_FLAGS", lambda p: p["pillar1_sop9_exoplanets_frontier_audit"]["pr6_issue5_synthetic_control"].__setitem__("seeded_17d_passes_sde", False))
        tamper("P1_PR6_FLAGS", lambda p: p["pillar1_sop9_exoplanets_frontier_audit"]["pr6_issue5_synthetic_control"].__setitem__("seeded_25d_passes_sde", True))
        tamper("P1_PR_MATRIX", lambda p: p["pillar1_sop9_exoplanets_frontier_audit"].__setitem__("pr_matrix", []))
        class _SubList(list):
            pass
        p1_sub = copy.deepcopy(base["pillar1_sop9_exoplanets_frontier_audit"])
        p1_sub["pr_matrix"] = _SubList(p1_sub["pr_matrix"])
        self._assert_err("P1_PR_MATRIX", verifier._audit_pillar1, p1_sub)
        # Zero in-process global aliasing: mutating build_certificate() in place cannot poison SEC/FR0
        c_live = oracle.build_certificate()
        c_live["payload"]["pillar1_sop9_exoplanets_frontier_audit"]["pr_matrix"][0]["conflicts_with_open_prs"].append(99)
        self._assert_err("P1_PR_MATRIX", verifier.secondary_audit_payload, c_live["payload"])
        self._assert_err("P1_PR_MATRIX", verifier.verify_certificate_dict, self._resign(c_live["payload"]), full_replay=False)
        self.assertEqual(oracle.build_certificate()["payload"]["pillar1_sop9_exoplanets_frontier_audit"]["pr_matrix"][0]["conflicts_with_open_prs"], [8])
        # Directly test P1_BLIND_SUM BoolOp on _audit_pillar1 via patched require_exact_int
        p1_bad_sum1 = copy.deepcopy(base["pillar1_sop9_exoplanets_frontier_audit"])
        p1_bad_sum1["blind_s106_s107_audit"]["total_pairs"] = 40
        with mock.patch.object(oracle, "require_exact_int", side_effect=lambda v, l, **kw: v):
            self._assert_err("P1_BLIND_SUM", verifier._audit_pillar1, p1_bad_sum1)
        p1_bad_sum2 = copy.deepcopy(base["pillar1_sop9_exoplanets_frontier_audit"])
        p1_bad_sum2["blind_s106_s107_audit"]["confirmed_on_schedule"] = 21
        with mock.patch.object(oracle, "require_exact_int", side_effect=lambda v, l, **kw: v):
            self._assert_err("P1_BLIND_SUM", verifier._audit_pillar1, p1_bad_sum2)

        # Pillar 2
        p2k = "pillar2_exact_astrophysical_operators"
        tamper("P2_SHARP", lambda p: (
            p[p2k]["bls_and_farey_separation"].__setitem__("sharpening_ratio_q", "50"),
            p[p2k]["bls_and_farey_separation"].__setitem__("sharpening_ratio_dec6", "50.000000"),
        ))
        tamper("P2_SHARP", lambda p: p[p2k]["bls_and_farey_separation"].__setitem__("sharpening_ratio_dec6", "0.000000"))
        tamper("P2_AG", lambda p: p[p2k]["bls_and_farey_separation"].__setitem__("alias_guard_q", "1/100"))
        tamper("P2_FAREY_LEN", lambda p: p[p2k]["bls_and_farey_separation"].__setitem__("farey_resonance_checks", "123456"))
        tamper("P2_FAREY_LEN", lambda p: p[p2k]["bls_and_farey_separation"].__setitem__("farey_resonance_checks", []))
        tamper("P2_FAREY_MATH", lambda p: p[p2k]["bls_and_farey_separation"]["farey_resonance_checks"][0].__setitem__("r1_q", "1/3"))
        tamper("P2_FAREY_MATH", lambda p: p[p2k]["bls_and_farey_separation"]["farey_resonance_checks"][0].__setitem__("r2_q", "3/4"))
        tamper("P2_FAREY_MATH", lambda p: p[p2k]["bls_and_farey_separation"]["farey_resonance_checks"][0].__setitem__("unimodular_det", 2))
        tamper("P2_FAREY_MATH", lambda p: p[p2k]["bls_and_farey_separation"]["farey_resonance_checks"][0].__setitem__("gap_q", "1/12"))
        tamper("P2_FAREY_MATH", lambda p: p[p2k]["bls_and_farey_separation"]["farey_resonance_checks"][0].__setitem__("gap_dec6", "0.000000"))
        tamper("P2_FAREY_MATH", lambda p: p[p2k]["bls_and_farey_separation"]["farey_resonance_checks"][0].__setitem__("collides_alias_guard", True))
        tamper("P2_CS09_MATH", lambda p: (
            p[p2k]["bls_and_farey_separation"]["cs09_sde_truncation_witness"].__setitem__("peak_mes_q", "60"),
            p[p2k]["bls_and_farey_separation"]["cs09_sde_truncation_witness"].__setitem__("wide_sde_q", "25/2"),
            p[p2k]["bls_and_farey_separation"]["cs09_sde_truncation_witness"].__setitem__("narrow_sde_q", "9"),
        ))
        tamper("P2_CS09_MATH", lambda p: p[p2k]["bls_and_farey_separation"]["cs09_sde_truncation_witness"].__setitem__("sde_threshold_q", "8"))
        tamper("P2_CS09_MATH", lambda p: p[p2k]["bls_and_farey_separation"]["cs09_sde_truncation_witness"].__setitem__("wide_sde_q", "9"))
        tamper("P2_CS09_MATH", lambda p: p[p2k]["bls_and_farey_separation"]["cs09_sde_truncation_witness"].__setitem__("narrow_sde_q", "8"))
        tamper("P2_CS09_MATH", lambda p: p[p2k]["bls_and_farey_separation"]["cs09_sde_truncation_witness"].__setitem__("wide_passes", False))
        tamper("P2_CS09_MATH", lambda p: p[p2k]["bls_and_farey_separation"]["cs09_sde_truncation_witness"].__setitem__("narrow_fails_despite_high_mes", False))

        tamper("P2_PONT_MATH", lambda p: (
            p[p2k]["pont_and_eight_gate_bayes"].__setitem__("red_to_white_ratio_q", "0"),
            p[p2k]["pont_and_eight_gate_bayes"].__setitem__("pont_beta_sq_q", "1"),
            p[p2k]["pont_and_eight_gate_bayes"].__setitem__("pont_beta_q", "1"),
            p[p2k]["pont_and_eight_gate_bayes"].__setitem__("corrected_mes_q", "14"),
        ))
        tamper("P2_PONT_MATH", lambda p: (
            p[p2k]["pont_and_eight_gate_bayes"].__setitem__("pont_beta_sq_q", "9"),
            p[p2k]["pont_and_eight_gate_bayes"].__setitem__("pont_beta_q", "3"),
            p[p2k]["pont_and_eight_gate_bayes"].__setitem__("corrected_mes_q", "14/3"),
        ))
        tamper("P2_PONT_MATH", lambda p: (
            p[p2k]["pont_and_eight_gate_bayes"].__setitem__("pont_beta_q", "3"),
            p[p2k]["pont_and_eight_gate_bayes"].__setitem__("corrected_mes_q", "14/3"),
        ))
        tamper("P2_PONT_MATH", lambda p: (
            p[p2k]["pont_and_eight_gate_bayes"].__setitem__("pont_beta_q", "-2"),
            p[p2k]["pont_and_eight_gate_bayes"].__setitem__("corrected_mes_q", "-7"),
        ))
        tamper("P2_PONT_MATH", lambda p: (
            p[p2k]["pont_and_eight_gate_bayes"].__setitem__("raw_mes_q", "16"),
            p[p2k]["pont_and_eight_gate_bayes"].__setitem__("corrected_mes_q", "8"),
        ))
        tamper("P2_PONT_MATH", lambda p: p[p2k]["pont_and_eight_gate_bayes"].__setitem__("mes_threshold_q", "10"))
        tamper("P2_PONT_MATH", lambda p: p[p2k]["pont_and_eight_gate_bayes"].__setitem__("corrected_mes_q", "8"))
        tamper("P2_PONT_MATH", lambda p: p[p2k]["pont_and_eight_gate_bayes"].__setitem__("red_noise_collapses_below_gate", False))

        def _set_bayes(p, pp_q, rg_q, eg_q):
            d = p[p2k]["pont_and_eight_gate_bayes"]
            fi_v = oracle.bayes_fpp_q(pp_q, 1 - pp_q, rg_q ** 8, eg_q ** 8)
            fc_v = oracle.bayes_fpp_q(pp_q, 1 - pp_q, rg_q ** 8, (eg_q ** 4) * Fraction(1, 2))
            d["prior_planet_q"] = oracle.fmt_q(pp_q)
            d["gate_retention_q"] = oracle.fmt_q(rg_q)
            d["gate_leakage_q"] = oracle.fmt_q(eg_q)
            d["indep_8gate_fpp_q"] = oracle.fmt_q(fi_v)
            d["indep_8gate_fpp_dec6"] = oracle.fmt_dec_q(fi_v, 6)
            d["correlated_4gate_fpp_q"] = oracle.fmt_q(fc_v)
            d["correlated_4gate_fpp_dec6"] = oracle.fmt_dec_q(fc_v, 6)

        tamper("P2_BAYES_MATH", lambda p: _set_bayes(p, Fraction(1, 50), Fraction(19, 20), Fraction(1, 4)))
        tamper("P2_BAYES_MATH", lambda p: _set_bayes(p, Fraction(1, 100), Fraction(9, 10), Fraction(1, 4)))
        tamper("P2_BAYES_MATH", lambda p: _set_bayes(p, Fraction(1, 100), Fraction(19, 20), Fraction(1, 5)))
        tamper("P2_BAYES_MATH", lambda p: p[p2k]["pont_and_eight_gate_bayes"].__setitem__("indep_8gate_fpp_q", "1/2"))
        tamper("P2_BAYES_MATH", lambda p: p[p2k]["pont_and_eight_gate_bayes"].__setitem__("indep_8gate_fpp_dec6", "0.000000"))
        tamper("P2_BAYES_MATH", lambda p: p[p2k]["pont_and_eight_gate_bayes"].__setitem__("indep_passes_tier_sval", False))
        tamper("P2_BAYES_MATH", lambda p: p[p2k]["pont_and_eight_gate_bayes"].__setitem__("correlated_4gate_fpp_q", "1/2"))
        tamper("P2_BAYES_MATH", lambda p: p[p2k]["pont_and_eight_gate_bayes"].__setitem__("correlated_4gate_fpp_dec6", "0.000000"))
        tamper("P2_BAYES_MATH", lambda p: p[p2k]["pont_and_eight_gate_bayes"].__setitem__("correlated_violates_tier_sval", False))

        tamper("P2_DESPOT_MATH", lambda p: (
            p[p2k]["harmonic_despot_orthogonality"].__setitem__("spot_amp_ppm_q", "9000"),
            p[p2k]["harmonic_despot_orthogonality"].__setitem__("masked_recovered_spot_q", "9000"),
        ))
        tamper("P2_DESPOT_MATH", lambda p: (
            p[p2k]["harmonic_despot_orthogonality"].__setitem__("injected_depth_ppm_q", "1400"),
            p[p2k]["harmonic_despot_orthogonality"].__setitem__("masked_recovered_depth_q", "1400"),
        ))
        for k, bad_v in (
            ("unmasked_gram_det_q", "512"),
            ("unmasked_recovered_depth_q", "700"), ("unmasked_retention_ratio_q", "1/3"), ("masked_gram_det_q", "256"),
            ("masked_recovered_spot_q", "9999"), ("masked_recovered_depth_q", "1400"), ("masked_retention_ratio_q", "1/2"),
            ("phase_lock_masked_gram_det_q", "1"), ("phase_lock_rank_collapsed", False),
            ("scrambled_null_l2_orig_q", "3800"), ("scrambled_null_l2_preserved", False),
        ):
            tamper("P2_DESPOT_MATH", lambda p, kk=k, vv=bad_v: p[p2k]["harmonic_despot_orthogonality"].__setitem__(kk, vv))

        tamper("P2_OC_WCS_MATH", lambda p: (
            p[p2k]["oc_ttv_and_wcs_affine"].__setitem__("beb_obs_depth_q", "1/50"),
            p[p2k]["oc_ttv_and_wcs_affine"].__setitem__("beb_required_neighbor_depth_q", "201/50"),
            p[p2k]["oc_ttv_and_wcs_affine"].__setitem__("beb_required_neighbor_depth_dec6", "4.020000"),
        ))
        for k, bad_v in (
            ("linear_drift_chi0_q", "2200"), ("linear_drift_chi_lin_q", "1"), ("quadratic_signal_chi_lin_q", "200"),
            ("quadratic_signal_chi_quad_q", "1"), ("drift_1500_orbits_4s_min_q", "99"),
            ("breaches_60min_wall_rescued_by_240min", False), ("wcs_affine_det_q", "8"),
            ("wcs_centroid_equivariant", False), ("dilution_residual_bias_q", "1"),
            ("beb_required_neighbor_depth_q", "2"),
            ("beb_required_neighbor_depth_dec6", "0.000000"), ("beb_physically_excluded", False),
            ("pm_10yr_300mas_shift_arcsec_q", "2"),
        ):
            tamper("P2_OC_WCS_MATH", lambda p, kk=k, vv=bad_v: p[p2k]["oc_ttv_and_wcs_affine"].__setitem__(kk, vv))

        # Pillar 3
        p3k = "pillar3_sop10_astronomy_spine_convergence"
        tamper("P3_PUB", lambda p: p[p3k].__setitem__("all_repos_verified_public", False))
        tamper("P3_SPINE_LEN", lambda p: p[p3k].__setitem__("astronomy_spine_repos", "1234567"))
        tamper("P3_SPINE_LEN", lambda p: p[p3k].__setitem__("astronomy_spine_repos", []))
        tamper("P3_SPINE_PIN", lambda p: p[p3k]["astronomy_spine_repos"][0].__setitem__("unmerged_seam", ""))
        tamper("P3_SPINE_PIN", lambda p: p[p3k]["astronomy_spine_repos"][0].__setitem__("unmerged_seam", "FORGED seam"))
        tamper("P3_SPINE_PIN", lambda p: p[p3k]["astronomy_spine_repos"][0].__setitem__("repo", "fake/repo"))
        tamper("P3_SPINE_PIN", lambda p: p[p3k]["astronomy_spine_repos"][0].__setitem__("is_private", True))
        tamper("P3_SPINE_PIN", lambda p: p[p3k]["astronomy_spine_repos"][0].__setitem__("main_commit", "0" * 40))
        tamper("P3_SPINE_PIN", lambda p: p[p3k]["astronomy_spine_repos"][0].__setitem__("branch_count", 99))
        tamper("P3_SPINE_PIN", lambda p: p[p3k]["astronomy_spine_repos"][0].__setitem__("open_pr_count", 99))
        tamper("P3_SPINE_PIN", lambda p: p[p3k]["astronomy_spine_repos"][0].__setitem__("merged_pr_count", 99))
        tamper("P3_SOP10_LIST", lambda p: p[p3k].__setitem__("eumemic_sop10_high_signal_repos", ["x"]))
        tamper("P3_BR_PIN", lambda p: p[p3k].__setitem__("aletheia_gate_bridges", "123"))
        tamper("P3_BR_PIN", lambda p: p[p3k].__setitem__("aletheia_gate_bridges", []))
        tamper("P3_BR_PIN", lambda p: p[p3k]["aletheia_gate_bridges"].__setitem__(0, ""))
        tamper("P3_BR_PIN", lambda p: p[p3k]["aletheia_gate_bridges"].__setitem__(0, "FORGED gate bridge"))
        # SubList on aletheia_gate_bridges kills type(brs) is list BoolOp!
        p3_sub = copy.deepcopy(base[p3k])
        p3_sub["aletheia_gate_bridges"] = _SubList(p3_sub["aletheia_gate_bridges"])
        self._assert_err("P3_BR_PIN", verifier._audit_pillar3, p3_sub)
        # Simultaneous 3-field narrative forgery rejected on SEC & FR0!
        tamper("PROV_UP_PIN", lambda p: (
            p["external_provenance"]["upstream_expedition_bridges"][0].__setitem__("bridge", "FORGED"),
            p[p3k]["astronomy_spine_repos"][0].__setitem__("unmerged_seam", "FORGED"),
            p[p3k]["aletheia_gate_bridges"].__setitem__(0, "FORGED"),
        ))

        # Envelope & artifact pin errors
        self._assert_err("INVALID_BOOL", verifier.verify_certificate_dict, self.cert, full_replay=1)
        self._assert_err("INVALID_CERT_TYPE", verifier.verify_certificate_dict, [], full_replay=False)
        for fld, val, code in (
            ("schema_version", "x", "SCHEMA_MISMATCH"),
            ("track_id", "x", "SCHEMA_MISMATCH"),
            ("payload_sha256", "0" * 64, "PAYLOAD_SHA_MISMATCH"),
            ("certificate_sha256", "0" * 64, "CERT_SHA_MISMATCH"),
        ):
            bad = copy.deepcopy(self.cert)
            bad[fld] = val
            self._assert_err(code, verifier.verify_certificate_dict, bad, full_replay=False)

        fake_live = {"lean_version": "4.36.0", "theorems_verified": 19, "lean_source_sha256": oracle.PINNED_LEAN_SOURCE_SHA256}
        with mock.patch.object(verifier, "_load_track_artifacts", return_value=(oracle.PINNED_LEAN_SOURCE_SHA256, oracle.PINNED_LEAN_TOOLCHAIN_SHA256, oracle.PINNED_LAKEFILE_SHA256, fake_live)), mock.patch.object(oracle, "build_certificate", return_value={"certificate_sha256": "0" * 64}):
            self._assert_err("REPLAY_MISMATCH", verifier.verify_certificate_dict, self.cert, full_replay=True)
        with mock.patch.object(verifier, "_load_track_artifacts", return_value=("0" * 64, oracle.PINNED_LEAN_TOOLCHAIN_SHA256, oracle.PINNED_LAKEFILE_SHA256, fake_live)):
            self._assert_err("LEAN_SHA_MISMATCH", verifier.verify_certificate_dict, self.cert, full_replay=True)
        with mock.patch.object(verifier, "_load_track_artifacts", return_value=(oracle.PINNED_LEAN_SOURCE_SHA256, "0" * 64, oracle.PINNED_LAKEFILE_SHA256, fake_live)):
            self._assert_err("TOOLCHAIN_SHA_MISMATCH", verifier.verify_certificate_dict, self.cert, full_replay=True)
        with mock.patch.object(verifier, "_load_track_artifacts", return_value=(oracle.PINNED_LEAN_SOURCE_SHA256, oracle.PINNED_LEAN_TOOLCHAIN_SHA256, "0" * 64, fake_live)):
            self._assert_err("LAKEFILE_SHA_MISMATCH", verifier.verify_certificate_dict, self.cert, full_replay=True)

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            (tdp / "lean-toolchain").write_bytes(b"\xff\xfe")
            (tdp / "lakefile.toml").write_text("x", encoding="ascii")
            self._assert_err("INVALID_UTF8", verifier._load_track_artifacts, tdp)
            (tdp / "lean-toolchain").write_text("leanprover/lean4:v4.0.0\n", encoding="ascii")
            self._assert_err("TOOLCHAIN_MISMATCH", verifier._load_track_artifacts, tdp)

    def test_verify_pins_and_cli_modes(self) -> None:
        # Exercise verify_external_pins_on_disk on synthetic temp tree (0 external network/path deps!)
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            cr = tdp / "clones"
            er = tdp / "exp"
            for row in oracle.PINNED_EXTERNAL_FILES:
                fp = cr / row["relpath"]
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_bytes(b"a" * row["bytes"])
            for row in oracle.UPSTREAM_EXPEDITION_CERTS:
                fp = er / row["cert_file"]
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_bytes(b"b")
            self._assert_err("EXT_PIN_MISMATCH", verifier.verify_external_pins_on_disk, cr, er)
            fake_ext_map = {r["sha256"] for r in oracle.PINNED_EXTERNAL_FILES}
            with mock.patch.object(oracle, "sha256_hex", side_effect=[r["sha256"] for r in oracle.PINNED_EXTERNAL_FILES] + ["0" * 64]):
                self._assert_err("UPSTREAM_PIN_MISMATCH", verifier.verify_external_pins_on_disk, cr, er)
            all_shas = [r["sha256"] for r in oracle.PINNED_EXTERNAL_FILES] + [r["cert_sha256"] for r in oracle.UPSTREAM_EXPEDITION_CERTS]
            with mock.patch.object(oracle, "sha256_hex", side_effect=all_shas):
                res_p = verifier.verify_external_pins_on_disk(cr, er)
                self.assertEqual(res_p["status"], "PINS_VERIFIED")
            # Wrong byte length kills len(raw) == row["bytes"] BoolOp!
            first_fp = cr / oracle.PINNED_EXTERNAL_FILES[0]["relpath"]
            first_fp.write_bytes(b"x")
            with mock.patch.object(oracle, "sha256_hex", side_effect=all_shas):
                self._assert_err("EXT_PIN_MISMATCH", verifier.verify_external_pins_on_disk, cr, er)
            self.assertEqual(len(fake_ext_map), 16)

        def run_cli(argv) -> tuple[int, str, str]:
            out_b, err_b = io.StringIO(), io.StringIO()
            with mock.patch.object(verifier.sys, "stdout", out_b), mock.patch.object(verifier.sys, "stderr", err_b):
                rc = verifier.main(argv)
            return rc, out_b.getvalue(), err_b.getvalue()

        # Dual-env live Lean vs Lean-less check (ZERO skips!)
        try:
            verifier.resolve_lean_binary()
            has_lean = True
        except oracle.S103Error:
            has_lean = False
        if has_lean or os.environ.get("ALETHEIA_REQUIRE_LEAN") == "1":
            r_live = verifier.verify_certificate_dict(self.cert, full_replay=True)
            self.assertTrue(r_live["valid"])
            self.assertIn("lean_live", r_live)
            live_stub = r_live["lean_live"]
        else:
            self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.verify_certificate_dict, self.cert, full_replay=True)
            rc, out, err = run_cli(["--check", str(_THIS_DIR / "s103_exoplanets_certificate.json"), "--json"])
            self.assertEqual((rc, out), (2, ""))
            self.assertEqual(json.loads(err)["code"], "LEAN_BINARY_UNAVAILABLE")
            live_stub = {
                "lean_version": "4.36.0",
                "theorems_verified": len(oracle.LEAN_THEOREM_NAMES),
                "lean_source_sha256": oracle.PINNED_LEAN_SOURCE_SHA256,
            }

        r_fr0 = verifier.verify_certificate_dict(self.cert, full_replay=False)
        self.assertTrue(r_fr0["valid"])
        self.assertNotIn("lean_live", r_fr0)

        with tempfile.TemporaryDirectory() as td:
            out_p = Path(td) / "cert.json"
            with mock.patch.object(verifier, "verify_lean4_file_live", return_value=live_stub):
                rc, out, err = run_cli(["--write", str(out_p), "--json"])
                self.assertEqual((rc, err), (0, ""))
                self.assertEqual(stat.S_IMODE(os.lstat(out_p).st_mode), 0o600)
                self.assertTrue(json.loads(out)["written"])
                rc, out, err = run_cli(["--write=" + str(out_p)])
                self.assertEqual((rc, err), (0, ""))
                self.assertTrue(out.startswith("WROTE "))
                rc, out, err = run_cli(["--check=" + str(out_p), "--json"])
                self.assertEqual((rc, err), (0, ""))
                self.assertTrue(json.loads(out)["valid"])
                rc, out, err = run_cli(["--check", str(out_p)])
                self.assertEqual((rc, err), (0, ""))
                self.assertTrue(out.startswith("OK "))
                # Re-signed >4300-digit rational string fails closed via CLI --check (rc=2, no ValueError traceback)
                huge_p = Path(td) / "huge_rat.json"
                p_huge = copy.deepcopy(self.cert["payload"])
                p_huge["pillar1_sop9_exoplanets_frontier_audit"]["blind_s106_s107_audit"]["inverted_artifact_snr_q"] = "9" * 5000
                huge_p.write_bytes(oracle.canonical_json_bytes(self._resign(p_huge)))
                rc, out, err = run_cli(["--check", str(huge_p), "--json"])
                self.assertEqual((rc, out), (2, ""))
                self.assertEqual(json.loads(err)["code"], "RATIONAL_TOO_LARGE")
                rc, out, err = run_cli(["--standalone"])
                self.assertEqual((rc, err), (0, ""))
                self.assertEqual(out.encode("ascii"), (_THIS_DIR / "s103_exoplanets_certificate.json").read_bytes())
                rc, out, err = run_cli([])
                self.assertEqual((rc, err), (0, ""))
                self.assertTrue(out.startswith("OK "))
                with mock.patch.object(verifier.sys, "argv", ["verify_s103_exoplanets.py", "--json"]):
                    rc, out, err = run_cli(None)
                    self.assertEqual((rc, err), (0, ""))
                    self.assertTrue(json.loads(out)["valid"])

            with mock.patch.object(verifier, "verify_external_pins_on_disk", return_value={"status": "PINS_VERIFIED", "external_files_verified": 16, "upstream_certs_verified": 6}):
                rc, out, err = run_cli(["--verify-pins", "--clones-root", td, "--expedition-root", td, "--json"])
                self.assertEqual((rc, err), (0, ""))
                self.assertEqual(json.loads(out)["status"], "PINS_VERIFIED")
                rc, out, err = run_cli(["--verify-pins", "--clones-root", td, "--expedition-root", td])
                self.assertEqual((rc, err), (0, ""))
                self.assertTrue(out.startswith("PINS_OK "))

            for bad_argv, code in (
                (123, "INVALID_ARGV"),
                (["--json", "--json"], "DUPLICATE_FLAG"),
                (["--standalone", "--check", str(out_p)], "CONFLICTING_MODE"),
                (["--check", str(out_p), "--standalone"], "CONFLICTING_MODE"),
                (["--check", str(out_p), "--verify-pins"], "CONFLICTING_MODE"),
                (["--check", str(out_p), "--write=" + str(out_p)], "CONFLICTING_MODE"),
                (["--check"], "MISSING_PATH_ARG"),
                (["--check", ""], "INVALID_PATH_ARG"),
                (["--check", "-bad"], "INVALID_PATH_ARG"),
                (["--check="], "INVALID_PATH_ARG"),
                (["--write=-bad"], "INVALID_PATH_ARG"),
                (["--clones-root"], "MISSING_PATH_ARG"),
                (["--clones-root", ""], "INVALID_PATH_ARG"),
                (["--clones-root", "-x"], "INVALID_PATH_ARG"),
                (["--clones-root", "a\x00b"], "NUL_BYTE_FORBIDDEN"),
                (["--clones-root", td, "--clones-root", td], "DUPLICATE_FLAG"),
                (["--expedition-root", td, "--expedition-root", td], "DUPLICATE_FLAG"),
                (["--verify-pins"], "MISSING_PATH_ARG"),
                (["--verify-pins", "--clones-root", td], "MISSING_PATH_ARG"),
                (["--verify-pins", "--expedition-root", td], "MISSING_PATH_ARG"),
                (["--unknown"], "UNKNOWN_FLAG"),
                (["--check\x00"], "NUL_BYTE_FORBIDDEN"),
                (["--check", "a\x00b"], "NUL_BYTE_FORBIDDEN"),
                (["--check", "\ud800"], "INVALID_UTF8_SURROGATE"),
            ):
                rc, out, err = run_cli(bad_argv)
                self.assertEqual((rc, out), (2, ""), f"argv={bad_argv!r}")
                self.assertEqual(json.loads(err)["code"], code, f"argv={bad_argv!r}")
            self._assert_err("NUL_BYTE_FORBIDDEN", verifier._parse_cli_args, ["--check", "a\x00b"])
            self._assert_err("INVALID_UTF8_SURROGATE", verifier._parse_cli_args, ["\ud800"])


class Test04LeanR11GatesAndMockedLive(unittest.TestCase):
    def _assert_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S103Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_r11_static_gate_escapes_and_clean_controls(self) -> None:
        lean_src = (_THIS_DIR / "ExoplanetsFrontierOperators.lean").read_text(encoding="utf-8")
        verifier.static_gate_lean4_source(lean_src)
        # Clean controls: 0 FP
        for ctrl in (
            "\nprivate theorem _c1 : 1 = 1 := by decide (native := false)\n",
            "\nprivate theorem _c2 : 1 = 1 := by decide (native := Bool.false)\n",
            "\nprivate theorem _c3 : 1 = 1 := by decide (config := { native := false })\n",
            "\nprivate theorem _c4 : 1 = 1 := by decide (config := { native := Bool.false })\n",
            "\nexport Nat (succ)\n",
            "\nattribute [simp] init_eq\n",
        ):
            verifier.static_gate_lean4_source(lean_src + ctrl)

        # Comment stripping & lexical errors
        stripped = verifier._strip_lean4_comments("/- a / - /- sorry -/ -- keep -/ -- axiom\ndef x := a / b - c\n-- eof")
        self.assertNotIn("sorry", stripped)
        self.assertNotIn("axiom", stripped)
        self.assertIn("a / b - c", stripped)
        self.assertEqual(verifier._strip_lean4_comments("/- a - sorry -/\n").strip(), "")
        self.assertEqual(verifier._strip_lean4_comments("/- a / sorry -/\n").strip(), "")
        self.assertEqual(verifier._strip_lean4_comments("/- -- sorry -/\n").strip(), "")
        self.assertIn("-/", verifier._strip_lean4_comments("def x := a -/ b\n"))
        self._assert_err("LEAN4_UNTERMINATED_LEX", verifier._strip_lean4_comments, "/- unclosed")
        self._assert_err("LEAN4_BAD_CHARS", verifier.static_gate_lean4_source, lean_src + "\r")
        self._assert_err("LEAN4_BAD_CHARS", verifier.static_gate_lean4_source, lean_src + "\x00")

        # Full R10+ & R11 escape battery (0 bypasses!)
        for esc in (
            "\nsorry\n",
            "\nadmit\n",
            "\naxiom bad : Prop\n",
            "\nunsafe def u := 0\n",
            "\npartial def loop : Nat := loop\n",
            "\nopaque hidden : Nat := 0\n",
            "\ntheorem t : True := by native_decide\n",
            "\ntheorem t : True := by bv_decide\n",
            "\nprivate theorem _s : False := _root_.sorryAx False false\n",
            "\ndef _b := Lean.ofReduceBool\n",
            "\ndef _n := Lean.ofReduceNat\n",
            "\ndef _tc := Lean.trustCompiler\n",
            "\ndef _ms := Lean.Meta.mkSorry\n",
            "\nset_option debug.skipKernelTC true\n",
            "\nset_option debug.terminalTacticsAsSorry true\n",
            "\nset_option warn.sorry false\n",
            "\nset_option pp.all true\n",
            "\ndbg_trace 1\n",
            "\ndbg_sleep 0\n",
            "\ndbg_stack_trace\n",
            "\nprivate def _d1 : Nat := dbgTrace (String.ofList []) (fun _ => 0)\n",
            "\nprivate def _d2 : Nat := _root_.dbgTrace (String.ofList []) (fun _ => 0)\n",
            "\nprivate def _d3 : Nat := dbgTraceVal 0\n",
            "\nprivate def _d3b : Nat := dbgTraceValId 0\n",
            "\nprivate def _d4 : Nat := dbgTraceIfShared (String.ofList []) 0\n",
            "\nprivate def _d5 : Nat := dbgSleep 0 (fun _ => 0)\n",
            "\nprivate def _d6 : Nat := dbgStackTrace (fun _ => 0)\n",
            "\ninitialize pure ()\n",
            "\nbuiltin_initialize pure ()\n",
            "\n@[init] def _i : IO Unit := pure ()\n",
            "\n@[builtin_init] def _bi : IO Unit := pure ()\n",
            "\n@[term_elab x] def _te : Nat := 0\n",
            "\n@[command_elab x] def _ce : Nat := 0\n",
            "\n@[tactic x] def _ta : Nat := 0\n",
            "\n@[macro x] def _ma : Nat := 0\n",
            "\n@[macro_rules] def _mr : Nat := 0\n",
            "\nattribute [init] foo\n",
            "\nattribute [builtin_init] foo\n",
            "\n@[export foo] def _e : Nat := 0\n",
            "\nattribute [export foo] f\n",
            "\nnoncomputable def _nc : Nat := 0\n",
            "\nprivate def _p1 : Nat := panic! (String.ofList [])\n",
            "\nprivate def _p2 : Nat := panicWithPos (String.ofList []) 0 0 (String.ofList [])\n",
            "\nprivate def _p3 : Nat := panicWithPosWithDecl (String.ofList []) (String.ofList []) 0 0 (String.ofList [])\n",
            "\nprivate def _p4 : Nat := unreachable!\n",
            "\nprivate def _p5 : Nat := assert! true; 0\n",
            "\nprivate def _p6 : Nat := debug_assert! true; 0\n",
            "\ndeclare_syntax_cat mycat\n",
            "\nmacro_rules | `(x) => `(0)\n",
            "\n#guard true\n",
            "\n@[extern \"c\"] def _ex : Nat := 0\n",
            "\nattribute [implemented_by f] g\n",
            "\n@[csimp] theorem c : True := trivial\n",
            "\nimport Mathlib\n",
            "\nrun_cmd pure ()\n",
            "\nrun_meta pure ()\n",
            "\nmacro \"bad\" : term => `(sorry)\n",
            "\nelab \"bad\" : command => pure ()\n",
            "\nelab_rules | `(bad) => pure ()\n",
            "\ntheorem t : True := by decide +native\n",
            "\ntheorem t : 1 = 1 := by decide +revert +native\n",
            "\ntheorem t : 1 = 1 := by decide -kernel +native\n",
            "\ntheorem t : 1 = 1 := by decide (native := false || true)\n",
            "\ntheorem t : 1 = 1 := by decide (native := Bool.false || true)\n",
            "\ntheorem t : 1 = 1 := by decide (native := false\n  || true)\n",
            "\ndef native : Bool := true\ntheorem t : 1 = 1 := by decide +revert (config := { native })\n",
            "\ndef native : Bool := true\ntheorem t : 1 = 1 := by decide (revert := false) (config := { native })\n",
            "\ndef native : Bool := true\ntheorem t : 1 = 1 := by decide +revert (config := { ({} : _) with native })\n",
            "\ndef cfg : DecideConfig := {}\n",
            "\n#eval 1\n",
            "\n#reduce 1\n",
            "\n#exit\n",
            "\n#guard_msgs in #check Nat\n",
            "\n#print Nat\n",
            "\n#print axioms Nat.add_comm\n",
            "\n#print axioms ExoplanetsFrontierOperators.nonexistent_thm\n",
            '\ndef s := "hi"\n',
            "\ntheorem t : False := by «sorry»\n",
        ):
            self._assert_err("LEAN4_TRUST_ESCAPE", verifier.static_gate_lean4_source, lean_src + esc)

        self._assert_err(
            "LEAN4_MISSING_THEOREM",
            verifier.static_gate_lean4_source,
            lean_src.replace("theorem bls_two_stage_sharpening_monotone", "theorem renamed_thm"),
        )
        self._assert_err(
            "LEAN4_MISSING_PRINT_AXIOMS",
            verifier.static_gate_lean4_source,
            lean_src.replace("#print axioms ExoplanetsFrontierOperators.bls_two_stage_sharpening_monotone", ""),
        )

    def test_resolve_lean_and_live_parsing_edges(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            fake_bin = tdp / "lean"
            fake_bin.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(fake_bin, 0o700)
            noexec = tdp / "lean_noexec"
            noexec.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(noexec, 0o600)
            dir_bin = tdp / "lean_dir"
            dir_bin.mkdir(mode=0o700)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(fake_bin)}):
                self.assertEqual(verifier.resolve_lean_binary(), str(fake_bin))
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(tdp / "missing")}):
                self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(noexec)}):
                self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(dir_bin)}):
                self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)

            home_d = tdp / "h"
            (home_d / ".elan" / "bin").mkdir(parents=True)
            elan_lean = home_d / ".elan" / "bin" / "lean"
            elan_lean.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(elan_lean, 0o600)
            with mock.patch.dict(os.environ, {"HOME": str(home_d)}, clear=True):
                with mock.patch.object(verifier.shutil, "which", return_value=str(fake_bin)):
                    self.assertEqual(verifier.resolve_lean_binary(), str(fake_bin))
                with mock.patch.object(verifier.shutil, "which", return_value=str(noexec)):
                    self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
                with mock.patch.object(verifier.shutil, "which", return_value=str(dir_bin)):
                    self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
                os.chmod(elan_lean, 0o700)
                with mock.patch.object(verifier.shutil, "which", return_value=None):
                    self.assertEqual(verifier.resolve_lean_binary(), str(elan_lean))
                os.unlink(elan_lean)
                elan_lean.mkdir(mode=0o700)
                with mock.patch.object(verifier.shutil, "which", return_value=None):
                    self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
                elan_lean.rmdir()
                with mock.patch.object(verifier.shutil, "which", return_value=None):
                    self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
            with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(verifier.shutil, "which", return_value=None):
                self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)

            bad_utf8 = tdp / "bad.lean"
            bad_utf8.write_bytes(b"\xff\xfe")
            self._assert_err("INVALID_UTF8", verifier.verify_lean4_file_live, bad_utf8)

        lean_p = _THIS_DIR / "ExoplanetsFrontierOperators.lean"
        ok_ver = subprocess.CompletedProcess(["lean", "--version"], 0, "Lean (version 4.36.0, x86_64)\n", "")
        good_lines = [f"'{t}' depends on axioms: [propext, Quot.sound]" for t in oracle.LEAN_THEOREM_NAMES]
        good_lines[0] = f"'{oracle.LEAN_THEOREM_NAMES[0]}' does not depend on any axioms"
        good_lines[1] = f"'{oracle.LEAN_THEOREM_NAMES[1]}' depends on axioms: [\n  propext,\n  Quot.sound\n]"
        ok_run = subprocess.CompletedProcess(["lean", "--stdin"], 0, "\n" + "\n".join(good_lines) + "\n", "")

        with mock.patch.object(verifier, "resolve_lean_binary", return_value="/bin/lean"):
            dirty_env = {
                "PATH": "/usr/bin",
                "LEAN_PATH": "/tmp/evil",
                "LEAN_OPTS": "--bad",
                "LEAN_CC": "evil",
                "ELAN_TOOLCHAIN": "evil",
                "ELAN_HOME": "/tmp/evil",
                "LAKE_HOME": "/tmp/evil",
                "LD_PRELOAD": "/tmp/evil.so",
                "LD_LIBRARY_PATH": "/tmp/evil",
            }
            with mock.patch.dict(os.environ, dirty_env, clear=True), mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, ok_run]) as m_run:
                res = verifier.verify_lean4_file_live(lean_p)
                self.assertEqual(res["theorems_verified"], len(oracle.LEAN_THEOREM_NAMES))
                for call in m_run.call_args_list:
                    self.assertEqual(call.kwargs["env"], {"PATH": "/usr/bin"})
            with mock.patch.object(verifier.subprocess, "run", side_effect=OSError("no")):
                self._assert_err("LEAN_EXEC_ERROR", verifier.verify_lean4_file_live, lean_p)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[subprocess.CompletedProcess([], 1, "4.36.0", "")]):
                self._assert_err("LEAN_VERSION_MISMATCH", verifier.verify_lean4_file_live, lean_p)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[subprocess.CompletedProcess([], 0, "Lean 4.10.0", "")]):
                self._assert_err("LEAN_VERSION_MISMATCH", verifier.verify_lean4_file_live, lean_p)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.TimeoutExpired(["lean"], 1)]):
                self._assert_err("LEAN_EXEC_ERROR", verifier.verify_lean4_file_live, lean_p)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.CompletedProcess([], 1, "", "")]):
                self._assert_err("LEAN_COMPILE_FAIL", verifier.verify_lean4_file_live, lean_p)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.CompletedProcess([], 0, "", "err")]):
                self._assert_err("LEAN_STDERR_NONEMPTY", verifier.verify_lean4_file_live, lean_p)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.CompletedProcess([], 0, "warning: x", "")]):
                self._assert_err("LEAN_WARNING_FORBIDDEN", verifier.verify_lean4_file_live, lean_p)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.CompletedProcess([], 0, "'X' depends on axioms: [propext\n", "")]):
                self._assert_err("LEAN_UNEXPECTED_STDOUT", verifier.verify_lean4_file_live, lean_p)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.CompletedProcess([], 0, "junk\n", "")]):
                self._assert_err("LEAN_UNEXPECTED_STDOUT", verifier.verify_lean4_file_live, lean_p)
            dup0 = f"'{oracle.LEAN_THEOREM_NAMES[0]}' does not depend on any axioms\n" * 2
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.CompletedProcess([], 0, dup0, "")]):
                self._assert_err("LEAN_DUPLICATE_THEOREM", verifier.verify_lean4_file_live, lean_p)
            dup1 = f"'{oracle.LEAN_THEOREM_NAMES[0]}' depends on axioms: [propext]\n" * 2
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.CompletedProcess([], 0, dup1, "")]):
                self._assert_err("LEAN_DUPLICATE_THEOREM", verifier.verify_lean4_file_live, lean_p)
            bad_ax = f"'{oracle.LEAN_THEOREM_NAMES[0]}' depends on axioms: [Classical.choice]\n"
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.CompletedProcess([], 0, bad_ax, "")]):
                self._assert_err("LEAN_FORBIDDEN_AXIOM", verifier.verify_lean4_file_live, lean_p)
            short = f"'{oracle.LEAN_THEOREM_NAMES[0]}' does not depend on any axioms\n"
            with mock.patch.object(verifier.subprocess, "run", side_effect=[ok_ver, subprocess.CompletedProcess([], 0, short, "")]):
                self._assert_err("LEAN_THEOREM_SET_MISMATCH", verifier.verify_lean4_file_live, lean_p)


if __name__ == "__main__":
    unittest.main()
