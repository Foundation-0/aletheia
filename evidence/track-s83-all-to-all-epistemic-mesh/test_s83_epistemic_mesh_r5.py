#!/usr/bin/env python3
"""Aletheia R5 Adversarial, Zone-B, R10+ Lean-Gate & Mutation-Killer Test Suite for Track S83.

100% pure Python 3 stdlib, zero bare asserts, zero AST floats, zero .isdigit(),
zero random imports, CI chmod-644 compatible.
"""
from __future__ import annotations

import ast
import copy
import errno
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

import s83_epistemic_mesh_oracle as oracle  # noqa: E402
import verify_s83_epistemic_mesh as verifier  # noqa: E402


class _IntSub(int):
    pass


class _StrSub(str):
    pass


class _ListSub(list):
    pass


class _DictSub(dict):
    pass


class _PathSub(type(Path())):
    pass


def _resign_cert(cert: dict) -> dict:
    c = copy.deepcopy(cert)
    p_sha = oracle.sha256_hex(oracle.canonical_json_bytes(c["payload"]))
    c["payload_sha256"] = p_sha
    env = {
        "schema_version": c["schema_version"],
        "track_id": c["track_id"],
        "payload_sha256": p_sha,
        "payload": c["payload"],
    }
    c["certificate_sha256"] = oracle.sha256_hex(oracle.canonical_json_bytes(env))
    return c


class Test01StaticHygiene(unittest.TestCase):
    def test_ast_and_text_hygiene(self) -> None:
        for fname in (
            "s83_epistemic_mesh_oracle.py",
            "verify_s83_epistemic_mesh.py",
            "test_s83_epistemic_mesh_r5.py",
        ):
            raw = (_THIS_DIR / fname).read_bytes()
            self.assertNotIn(b"\r", raw, fname)
            src = raw.decode("utf-8", "strict")
            self.assertNotIn("/" + "home/", src, fname)
            self.assertNotIn("/dev/" + "null", src, fname)
            tree = ast.parse(src, filename=fname)
            for node in ast.walk(tree):
                self.assertNotIsInstance(node, ast.Assert, fname)
                if isinstance(node, ast.Constant):
                    self.assertNotIsInstance(node.value, float, fname)
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        self.assertNotIn(node.func.id, ("float", "eval", "exec"), fname)
                    if isinstance(node.func, ast.Attribute):
                        self.assertNotEqual(node.func.attr, "isdigit", fname)
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotEqual(alias.name, "random", fname)
                if isinstance(node, ast.ImportFrom):
                    self.assertNotEqual(node.module, "random", fname)

    def test_disk_certificate_strict_zero_float_canonical(self) -> None:
        raw = verifier.read_regular_bytes_capped(_THIS_DIR / "s83_epistemic_mesh_certificate.json", "cert")
        obj = verifier.parse_strict_json_bytes(raw, "cert", require_canonical=True)
        self.assertIs(type(obj), dict)


class Test02OraclePrimitivesAndMeshMath(unittest.TestCase):
    def _assert_s83(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S83Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_type_and_hex_guards(self) -> None:
        self.assertIs(oracle.require_bool(True, "b"), True)
        self.assertIs(oracle.require_bool(False, "b"), False)
        for bad in (0, 1, "true", None):
            self._assert_s83("INVALID_BOOL", oracle.require_bool, bad, "b")

        self.assertEqual(oracle.require_exact_int(5, "x", lo=5, hi=5), 5)
        self._assert_s83("INVALID_INT", oracle.require_exact_int, True, "x")
        self._assert_s83("INVALID_INT", oracle.require_exact_int, _IntSub(5), "x")
        self._assert_s83("INT_OUT_OF_RANGE", oracle.require_exact_int, 4, "x", lo=5)
        self._assert_s83("INT_OUT_OF_RANGE", oracle.require_exact_int, 6, "x", hi=5)
        big_ok = (1 << oracle.MAX_INT_BITS) - 1
        self.assertEqual(oracle.require_exact_int(big_ok, "x"), big_ok)
        self._assert_s83("INT_TOO_LARGE", oracle.require_exact_int, 1 << oracle.MAX_INT_BITS, "x")

        self.assertEqual(oracle.require_exact_str("abc", "s"), "abc")
        self._assert_s83("INVALID_STR", oracle.require_exact_str, _StrSub("a"), "s")
        self._assert_s83("INVALID_UTF8_SURROGATE", oracle.require_exact_str, "\ud800", "s")

        h64 = "0123456789abcdef" * 4
        self.assertEqual(oracle.require_hex64(h64, "h"), h64)
        self._assert_s83("INVALID_HEX64", oracle.require_hex64, h64[:-1], "h")
        self._assert_s83("INVALID_HEX64", oracle.require_hex64, "A" + h64[1:], "h")

        self.assertTrue(oracle.is_ascii_digits("0123456789"))
        self.assertFalse(oracle.is_ascii_digits(""))
        self.assertFalse(oracle.is_ascii_digits("12a"))
        self.assertFalse(oracle.is_ascii_digits("\u00b2"))

    def test_validate_strict_json_tree_edges(self) -> None:
        shared = [1, 2]
        oracle.validate_strict_json_tree({"a": shared, "b": shared, "n": None, "t": True, "s": "ok"})

        nested: list = []
        cur = nested
        for _ in range(oracle.MAX_JSON_DEPTH):
            nxt: list = []
            cur.append(nxt)
            cur = nxt
        oracle.validate_strict_json_tree(nested)
        cur.append(0)
        self._assert_s83("JSON_DEPTH_EXCEEDED", oracle.validate_strict_json_tree, nested)

        oracle.validate_strict_json_tree((1 << oracle.MAX_INT_BITS) - 1)
        self._assert_s83("INT_TOO_LARGE", oracle.validate_strict_json_tree, 1 << oracle.MAX_INT_BITS)

        cyc_l: list = []
        cyc_l.append(cyc_l)
        self._assert_s83("JSON_CYCLE", oracle.validate_strict_json_tree, cyc_l)
        cyc_d: dict = {}
        cyc_d["self"] = cyc_d
        self._assert_s83("JSON_CYCLE", oracle.validate_strict_json_tree, cyc_d)

        self._assert_s83("INVALID_UTF8_SURROGATE", oracle.validate_strict_json_tree, {"k": "\ud800"})
        self._assert_s83("INVALID_UTF8_SURROGATE", oracle.validate_strict_json_tree, {"\ud800": 1})
        self._assert_s83("INVALID_STR", oracle.validate_strict_json_tree, {1: "a"})
        for bad in ((1, 2), b"abc", _IntSub(1), _StrSub("a"), _ListSub([1]), _DictSub({"a": 1})):
            self._assert_s83("INVALID_JSON_TYPE", oracle.validate_strict_json_tree, bad)

    def test_q_formatting_algebra_inertia_and_helpers(self) -> None:
        self.assertEqual(oracle.q_str(Fraction(4, 1)), "4")
        self.assertEqual(oracle.q_str(Fraction(-3, 2)), "-3/2")
        self.assertEqual(oracle.dec_from_q(Fraction(1, 200), 2), "0.01")
        self.assertEqual(oracle.dec_from_q(Fraction(1, 300), 2), "0.00")
        self.assertEqual(oracle.dec_from_q(Fraction(-1, 1000), 2), "0.00")
        self.assertEqual(oracle.dec_from_q(Fraction(-3, 200), 2), "-0.02")
        self.assertEqual(oracle.dec_from_q(Fraction(5, 2), 0), "3")
        self.assertEqual(oracle.dec_from_q(Fraction(-5, 2), 0), "-3")

        swap_m = [[Fraction(0), Fraction(2)], [Fraction(3), Fraction(1)]]
        self.assertEqual(oracle.q_solve(swap_m, [[Fraction(4)], [Fraction(5)]]), [[Fraction(1)], [Fraction(2)]])
        sing_m = [[Fraction(1), Fraction(2)], [Fraction(2), Fraction(4)]]
        self._assert_s83("SINGULAR_MATRIX", oracle.q_solve, sing_m, [[Fraction(1)], [Fraction(2)]])

        diag_swap = [
            [Fraction(0), Fraction(0), Fraction(0)],
            [Fraction(0), Fraction(3), Fraction(0)],
            [Fraction(0), Fraction(0), Fraction(-2)],
        ]
        self.assertEqual(oracle.q_sylvester_inertia(diag_swap), [1, 1, 1])
        off_4 = [
            [Fraction(0), Fraction(0), Fraction(0), Fraction(0)],
            [Fraction(0), Fraction(0), Fraction(0), Fraction(2)],
            [Fraction(0), Fraction(0), Fraction(0), Fraction(1)],
            [Fraction(0), Fraction(2), Fraction(1), Fraction(0)],
        ]
        self.assertEqual(oracle.q_sylvester_inertia(off_4), [1, 1, 2])
        off_full = [
            [Fraction(0), Fraction(0), Fraction(1), Fraction(2)],
            [Fraction(0), Fraction(0), Fraction(2), Fraction(1)],
            [Fraction(1), Fraction(2), Fraction(0), Fraction(0)],
            [Fraction(2), Fraction(1), Fraction(0), Fraction(0)],
        ]
        self.assertEqual(oracle.q_sylvester_inertia(off_full), [2, 2, 0])
        self.assertEqual(oracle.q_sylvester_inertia(oracle.q_zeros(3, 3)), [0, 0, 3])

        # BoolOp & guard killers for oracle helpers
        self.assertTrue(oracle.check_triangle_strict_ineq(Fraction(2), Fraction(2), Fraction(3)))
        self.assertFalse(oracle.check_triangle_strict_ineq(Fraction(2), Fraction(2), Fraction(4)))
        self.assertFalse(oracle.check_triangle_strict_ineq(Fraction(4), Fraction(2), Fraction(2)))
        self.assertFalse(oracle.check_triangle_strict_ineq(Fraction(2), Fraction(4), Fraction(2)))

        self.assertTrue(oracle.check_core4_strict_compounding(Fraction(3), Fraction(2)))
        self.assertFalse(oracle.check_core4_strict_compounding(Fraction(2), Fraction(2)))
        self.assertFalse(oracle.check_core4_strict_compounding(Fraction(1), Fraction(0)))

        ok_s2 = [[Fraction(5), Fraction(-5)], [Fraction(-5), Fraction(5)]]
        self.assertEqual(oracle.verify_schur_2x2_laplacian(ok_s2, "ok"), Fraction(5))
        self._assert_s83("SCHUR_2X2_SYMMETRY_FAIL", oracle.verify_schur_2x2_laplacian, [[Fraction(5), Fraction(-5)], [Fraction(-5), Fraction(4)]], "b1")
        self._assert_s83("SCHUR_2X2_SYMMETRY_FAIL", oracle.verify_schur_2x2_laplacian, [[Fraction(5), Fraction(-4)], [Fraction(-5), Fraction(5)]], "b2")
        self._assert_s83("SCHUR_2X2_SYMMETRY_FAIL", oracle.verify_schur_2x2_laplacian, [[Fraction(5), Fraction(-5)], [Fraction(-4), Fraction(5)]], "b3")

        self.assertEqual(oracle.classify_triangle_holonomy(3, 0), ("EXACT_TRANSITIVE_CLOSURE", 0))
        self.assertEqual(oracle.classify_triangle_holonomy(2, 0), ("CONDITIONAL_COMPOUNDING_CLOSURE", 0))
        self.assertEqual(oracle.classify_triangle_holonomy(2, 1), ("FRUSTRATED_CURVATURE_LOOP", 1))
        self.assertEqual(oracle.classify_triangle_holonomy(0, 2), ("MULTI_WALL_BOUNDARY_SECTOR", 0))

        # Exact K_8 oracle assertions
        p1 = oracle.certify_pillar1_schur_compounding()
        self.assertEqual(p1["foster_sum_q"], "7")
        self.assertEqual(p1["laplacian_inertia"], [7, 0, 1])
        self.assertEqual(p1["resistance_triangle_inequalities_verified"], 168)
        self.assertTrue(p1["all_28_pairs_strictly_compounded"])
        p2 = oracle.certify_pillar2_triangle_holonomy()
        self.assertEqual(p2["n_triangles"], 56)
        self.assertTrue(p2["bianchi_coboundary_zero_all_70"])
        p3 = oracle.certify_pillar3_silo_cuts_and_contagion_firewall()
        self.assertEqual(p3["split_summary"]["4|4"]["triangles_destroyed"], 48)
        self.assertEqual(p3["split_summary"]["3|5"]["triangles_destroyed"], 45)
        self.assertEqual(p3["contagion_firewall_case"]["gated_k7_pathways_retained"], 21)


class Test03ZoneBIOAndParsers(unittest.TestCase):
    def _assert_s83(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S83Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_path_and_darwin_normalization(self) -> None:
        self._assert_s83("INVALID_PATH_TYPE", verifier._require_concrete_path, "/tmp/a", "p")
        self._assert_s83("INVALID_PATH_TYPE", verifier._require_concrete_path, _PathSub("/tmp/a"), "p")
        self._assert_s83("INVALID_UTF8_SURROGATE", verifier._require_concrete_path, Path("/tmp/\ud800"), "p")
        self._assert_s83("NUL_BYTE_FORBIDDEN", verifier._require_concrete_path, Path("/tmp/a\x00b"), "p")

        fake_lnk = os.stat_result((stat.S_IFLNK | 0o777, 1, 1, 1, 0, 0, 0, 0, 0, 0))
        fake_nonroot = os.stat_result((stat.S_IFLNK | 0o777, 1, 1, 1, 1000, 0, 0, 0, 0, 0))
        fake_dir = os.stat_result((stat.S_IFDIR | 0o755, 1, 1, 1, 0, 0, 0, 0, 0, 0))

        with mock.patch.object(verifier.sys, "platform", "linux"), mock.patch.object(
            verifier.os, "lstat", return_value=fake_lnk
        ), mock.patch.object(verifier.os, "readlink", return_value="private/tmp"):
            self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/tmp/a")), Path("/tmp/a"))

        with mock.patch.object(verifier.sys, "platform", "darwin"):
            self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/usr/bin")), Path("/usr/bin"))
            with mock.patch.object(verifier.os, "lstat", return_value=fake_lnk), mock.patch.object(
                verifier.os, "readlink", return_value="private/tmp"
            ):
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("x/tmp/a")), Path("x/tmp/a"))
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/tmp/../a")), Path("/tmp/../a"))
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/tmp"), allow_exact=False), Path("/tmp"))
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/tmp"), allow_exact=True), Path("/private/tmp"))
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/tmp/x")), Path("/private/tmp/x"))
            with mock.patch.object(verifier.os, "lstat", return_value=fake_lnk), mock.patch.object(
                verifier.os, "readlink", return_value="/private/var"
            ):
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/var/x")), Path("/private/var/x"))
            with mock.patch.object(verifier.os, "lstat", return_value=fake_lnk), mock.patch.object(
                verifier.os, "readlink", return_value="/evil/tmp"
            ):
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/tmp/x")), Path("/tmp/x"))
            with mock.patch.object(verifier.os, "lstat", return_value=fake_nonroot), mock.patch.object(
                verifier.os, "readlink", return_value="private/tmp"
            ):
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/tmp/x")), Path("/tmp/x"))
            with mock.patch.object(verifier.os, "lstat", return_value=fake_dir), mock.patch.object(
                verifier.os, "readlink", return_value="private/tmp"
            ):
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/tmp/x")), Path("/tmp/x"))
            with mock.patch.object(verifier.os, "lstat", side_effect=OSError(errno.ENOENT, "no")):
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/tmp/x")), Path("/tmp/x"))

    def test_safe_cwd_and_pwd_checks(self) -> None:
        with mock.patch.object(verifier.Path, "cwd", side_effect=OSError(errno.ENOENT, "gone")):
            self._assert_s83("CWD_UNAVAILABLE", verifier._safe_cwd, "lbl")

        with tempfile.TemporaryDirectory() as td:
            real_d = Path(td) / "real"
            real_d.mkdir()
            link_d = Path(td) / "link"
            link_d.symlink_to(real_d)
            old_cwd = os.getcwd()
            try:
                os.chdir(real_d)
                with mock.patch.dict(os.environ, {"PWD": "relative"}):
                    verifier._check_pwd_no_symlinks("lbl")
                with mock.patch.dict(os.environ, {"PWD": "/nonexistent_s83_dir_xyz"}):
                    verifier._check_pwd_no_symlinks("lbl")
                with mock.patch.dict(os.environ, {"PWD": str(Path(td))}):
                    verifier._check_pwd_no_symlinks("lbl")
                with mock.patch.object(verifier.os, "environ", {"PWD": "/tmp/\x00bad"}):
                    self._assert_s83("NUL_BYTE_FORBIDDEN", verifier._check_pwd_no_symlinks, "lbl")
                with mock.patch.dict(os.environ, {"PWD": str(link_d)}):
                    self._assert_s83("SYMLINK_ANCESTOR_FORBIDDEN", verifier._check_pwd_no_symlinks, "lbl")
                with mock.patch.dict(os.environ, {"PWD": str(real_d)}):
                    verifier._check_pwd_no_symlinks("lbl")
                    with mock.patch.object(verifier.os, "open", side_effect=OSError(errno.EACCES, "denied")):
                        self._assert_s83("CWD_UNAVAILABLE", verifier._check_pwd_no_symlinks, "lbl")
                    orig_open = os.open

                    def fail_step(path, flags, *a, **kw):
                        if path != "/":
                            raise OSError(errno.EACCES, "denied")
                        return orig_open(path, flags, *a, **kw)

                    with mock.patch.object(verifier.os, "open", side_effect=fail_step):
                        self._assert_s83("CWD_UNAVAILABLE", verifier._check_pwd_no_symlinks, "lbl")
            finally:
                os.chdir(old_cwd)

    def test_read_and_write_zone_b_adversarial(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            f_ok = root / "ok.bin"
            verifier.write_regular_bytes_safe(f_ok, b"hello", "ok")
            self.assertEqual(stat.S_IMODE(os.lstat(f_ok).st_mode), 0o600)
            self.assertEqual(verifier.read_regular_bytes_capped(f_ok, "ok", max_bytes=5), b"hello")
            self._assert_s83("FILE_TOO_LARGE", verifier.read_regular_bytes_capped, f_ok, "ok", max_bytes=4)
            self._assert_s83("INT_OUT_OF_RANGE", verifier.read_regular_bytes_capped, f_ok, "ok", max_bytes=0)
            self._assert_s83("INT_OUT_OF_RANGE", verifier.read_regular_bytes_capped, f_ok, "ok", max_bytes=verifier.MAX_ALLOWED_CAP_BYTES + 1)

            small_st = os.stat_result((stat.S_IFREG | 0o600, 1, 1, 1, 0, 0, 2, 0, 0, 0))
            with mock.patch.object(verifier.os, "fstat", return_value=small_st):
                self._assert_s83("FILE_TOO_LARGE", verifier.read_regular_bytes_capped, f_ok, "ok", max_bytes=3)

            empty_f = root / "empty.bin"
            verifier.write_regular_bytes_safe(empty_f, b"", "empty")
            big_st = os.stat_result((stat.S_IFREG | 0o600, 1, 1, 1, 0, 0, 999, 0, 0, 0))
            with mock.patch.object(verifier.os, "fstat", return_value=big_st):
                self._assert_s83("FILE_TOO_LARGE", verifier.read_regular_bytes_capped, empty_f, "empty", max_bytes=10)

            old_cwd = os.getcwd()
            try:
                os.chdir(root)
                with mock.patch.dict(os.environ, {"PWD": str(root)}):
                    verifier.write_regular_bytes_safe(Path("sub/nested/rel.bin"), b"xyz", "rel")
                    self.assertEqual(verifier.read_regular_bytes_capped(Path("sub/nested/rel.bin"), "rel"), b"xyz")
            finally:
                os.chdir(old_cwd)

            self._assert_s83("NOT_A_REGULAR_FILE", verifier.read_regular_bytes_capped, Path("/"), "root")
            self._assert_s83("NOT_A_REGULAR_FILE", verifier._open_dir_chain, root / "..", "dotdot", create_parents=False)
            self._assert_s83("NOT_A_REGULAR_FILE", verifier.read_regular_bytes_capped, root / "..", "dotdot")
            self._assert_s83("NOT_A_REGULAR_FILE", verifier.read_regular_bytes_capped, root / "sub", "dir")
            self._assert_s83("NOT_A_REGULAR_FILE", verifier.write_regular_bytes_safe, root / "sub", b"x", "dir")
            self._assert_s83("INVALID_PAYLOAD_BYTES", verifier.write_regular_bytes_safe, f_ok, "str", "bad")

            fifo = root / "pipe.fifo"
            os.mkfifo(fifo)
            self._assert_s83("NOT_A_REGULAR_FILE", verifier.read_regular_bytes_capped, fifo, "fifo")
            self._assert_s83("NOT_A_REGULAR_FILE", verifier.write_regular_bytes_safe, fifo, b"x", "fifo")

            sym_leaf = root / "sym_leaf"
            sym_leaf.symlink_to(f_ok)
            self._assert_s83("SYMLINK_FORBIDDEN", verifier.read_regular_bytes_capped, sym_leaf, "sym")
            self._assert_s83("SYMLINK_FORBIDDEN", verifier.write_regular_bytes_safe, sym_leaf, b"x", "sym")

            sym_dir = root / "sym_dir"
            sym_dir.symlink_to(root / "sub")
            self._assert_s83("SYMLINK_FORBIDDEN", verifier.read_regular_bytes_capped, sym_dir / "a", "symd")
            self._assert_s83("SYMLINK_FORBIDDEN", verifier.write_regular_bytes_safe, sym_dir / "a", b"x", "symd")

            hl = root / "hardlink"
            os.link(f_ok, hl)
            self._assert_s83("HARDLINK_FORBIDDEN", verifier.read_regular_bytes_capped, hl, "hl")
            self._assert_s83("HARDLINK_FORBIDDEN", verifier.write_regular_bytes_safe, hl, b"x", "hl")
            os.unlink(hl)

            self._assert_s83("FILE_READ_ERROR", verifier.read_regular_bytes_capped, root / "missing.bin", "miss")
            self._assert_s83("FILE_READ_ERROR", verifier.read_regular_bytes_capped, root / "nodir" / "x", "missd")
            self.assertFalse((root / "nodir").exists())
            with mock.patch.object(verifier.os, "open", side_effect=OSError(errno.EACCES, "denied")):
                self._assert_s83("FILE_READ_ERROR", verifier.read_regular_bytes_capped, f_ok, "rd")
                self._assert_s83("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, f_ok, b"x", "wr")
            with mock.patch.object(verifier.os, "read", side_effect=OSError(errno.EIO, "io")):
                self._assert_s83("FILE_READ_ERROR", verifier.read_regular_bytes_capped, f_ok, "rd")

            orig_write = os.write
            w_calls = {"w": 0}

            def partial_write(fd, buf):
                w_calls["w"] += 1
                if w_calls["w"] == 1:
                    return orig_write(fd, buf[:2])
                return orig_write(fd, buf)

            with mock.patch.object(verifier.os, "write", side_effect=partial_write):
                verifier.write_regular_bytes_safe(f_ok, b"abcdef", "part")
            self.assertEqual(verifier.read_regular_bytes_capped(f_ok, "part"), b"abcdef")

            orig_open = os.open
            retry_st = {"n": 0}

            def open_retry_once(path, flags, *a, **kw):
                if isinstance(path, str) and path.startswith(".s83.") and retry_st["n"] == 0:
                    retry_st["n"] += 1
                    raise FileExistsError()
                return orig_open(path, flags, *a, **kw)

            with mock.patch.object(verifier.os, "open", side_effect=open_retry_once):
                verifier.write_regular_bytes_safe(f_ok, b"retry", "retry")
            self.assertEqual(verifier.read_regular_bytes_capped(f_ok, "retry"), b"retry")

            def open_always_exists(path, flags, *a, **kw):
                if isinstance(path, str) and path.startswith(".s83."):
                    raise FileExistsError()
                return orig_open(path, flags, *a, **kw)

            with mock.patch.object(verifier.os, "open", side_effect=open_always_exists):
                self._assert_s83("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, f_ok, b"x", "exh")

            nospc_calls = {"n": 0}

            def open_enospc(path, flags, *a, **kw):
                if isinstance(path, str) and path.startswith(".s83."):
                    nospc_calls["n"] += 1
                    raise OSError(errno.ENOSPC, "full")
                return orig_open(path, flags, *a, **kw)

            with mock.patch.object(verifier.os, "open", side_effect=open_enospc):
                self._assert_s83("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, f_ok, b"x", "nospc")
            self.assertEqual(nospc_calls["n"], 1)

            with mock.patch.object(verifier.os, "lstat", side_effect=OSError(errno.EACCES, "denied")):
                self._assert_s83("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, f_ok, b"x", "lst")

            race_dir = root / "racedir"
            orig_mkdir = os.mkdir
            race_flag = {"first": True}

            def open_race(path, flags, *a, **kw):
                if path == "racedir" and race_flag["first"]:
                    race_flag["first"] = False
                    raise OSError(errno.ENOENT, "enoent")
                return orig_open(path, flags, *a, **kw)

            race_dir.mkdir()
            with mock.patch.object(verifier.os, "open", side_effect=open_race), mock.patch.object(
                verifier.os, "mkdir", side_effect=FileExistsError()
            ):
                verifier.write_regular_bytes_safe(race_dir / "f.bin", b"ok", "race")
            self.assertEqual(verifier.read_regular_bytes_capped(race_dir / "f.bin", "race"), b"ok")

            with mock.patch.object(verifier.os, "mkdir", side_effect=OSError(errno.EACCES, "denied")):
                with self.assertRaises(oracle.S83Error) as mk_ctx:
                    verifier.write_regular_bytes_safe(root / "newd1" / "f", b"x", "mk")
                self.assertEqual(mk_ctx.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("mkdir failed", mk_ctx.exception.detail)

            def open_parent_eacces(path, flags, *a, **kw):
                if path == "noacc":
                    raise OSError(errno.EACCES, "denied")
                return orig_open(path, flags, *a, **kw)

            with mock.patch.object(verifier.os, "open", side_effect=open_parent_eacces), mock.patch.object(
                verifier.os, "mkdir"
            ) as mk_spy:
                self._assert_s83("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, root / "noacc" / "f", b"x", "ea")
                mk_spy.assert_not_called()

            def open_reopen_fail(path, flags, *a, **kw):
                if path == "newd2":
                    raise OSError(errno.ENOENT, "enoent")
                return orig_open(path, flags, *a, **kw)

            with mock.patch.object(verifier.os, "open", side_effect=open_reopen_fail), mock.patch.object(
                verifier.os, "mkdir", side_effect=orig_mkdir
            ):
                self._assert_s83("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, root / "newd2" / "f", b"x", "re")

            with mock.patch.object(verifier.os, "write", return_value=0):
                self._assert_s83("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, f_ok, b"x", "sw0")
            with mock.patch.object(verifier.os, "fchmod", side_effect=OSError(errno.EPERM, "perm")):
                self._assert_s83("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, f_ok, b"x", "fch")
            with mock.patch.object(verifier.os, "fsync", side_effect=OSError(errno.EIO, "io")):
                self._assert_s83("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, f_ok, b"x", "fsy")
            bad_nlink = os.stat_result((stat.S_IFREG | 0o600, 1, 1, 2, 0, 0, 1, 0, 0, 0))
            with mock.patch.object(verifier.os, "fstat", return_value=bad_nlink):
                self._assert_s83("HARDLINK_FORBIDDEN", verifier.write_regular_bytes_safe, f_ok, b"x", "nl")

            rep_dir = root / "rep_fail"
            rep_dir.mkdir()
            with mock.patch.object(verifier.os, "replace", side_effect=OSError(errno.EXDEV, "xdev")), mock.patch.object(
                verifier.os, "unlink", side_effect=OSError(errno.ENOENT, "gone")
            ):
                self._assert_s83("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, rep_dir / "f.bin", b"x", "rep")

            conc_dir = root / "conc_dir"
            conc_dir.mkdir()
            conc_f = conc_dir / "concurrent.bin"
            errs: list[BaseException] = []

            def worker(idx: int) -> None:
                try:
                    data = f"worker-{idx:02d}\n".encode("ascii")
                    for _ in range(8):
                        verifier.write_regular_bytes_safe(conc_f, data, "conc")
                        got = verifier.read_regular_bytes_capped(conc_f, "conc")
                        if not got.startswith(b"worker-"):
                            errs.append(ValueError("corrupt read"))
                except BaseException as exc:  # pragma: no cover
                    errs.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errs, [])
            leftovers = [p.name for p in conc_dir.iterdir() if p.name.startswith(".s83.") and p.name.endswith(".tmp")]
            self.assertEqual(leftovers, [])

    def test_strict_json_and_rational_parsers(self) -> None:
        self.assertEqual(verifier._parse_bounded_int("0"), 0)
        self.assertEqual(verifier._parse_bounded_int("-42"), -42)
        self.assertEqual(len(str(verifier._parse_bounded_int("9" * oracle.MAX_INT_DIGITS))), oracle.MAX_INT_DIGITS)
        self._assert_s83("INVALID_INT_TOKEN", verifier._parse_bounded_int, "12a")
        self._assert_s83("INT_TOO_LARGE", verifier._parse_bounded_int, "9" * (oracle.MAX_INT_DIGITS + 1))
        self._assert_s83("NONCANONICAL_INT", verifier._parse_bounded_int, "01")
        self._assert_s83("NONCANONICAL_INT", verifier._parse_bounded_int, "-0")
        with mock.patch.object(oracle, "MAX_INT_DIGITS", 3000):
            max_bits_ok = (1 << oracle.MAX_INT_BITS) - 1
            self.assertEqual(verifier._parse_bounded_int(str(max_bits_ok)), max_bits_ok)
            self._assert_s83("INT_TOO_LARGE", verifier._parse_bounded_int, str(1 << oracle.MAX_INT_BITS))

        self.assertEqual(verifier.parse_strict_json_bytes(b'{"a":1}\n'), {"a": 1})
        self.assertEqual(verifier.parse_strict_json_bytes(b'{ "a" : 1 }', require_canonical=False), {"a": 1})
        self._assert_s83("INVALID_BYTES", verifier.parse_strict_json_bytes, '{"a":1}\n')
        self._assert_s83("BOM_FORBIDDEN", verifier.parse_strict_json_bytes, b'\xef\xbb\xbf{"a":1}\n')
        self._assert_s83("CRLF_FORBIDDEN", verifier.parse_strict_json_bytes, b'{"a":1}\r\n')
        self._assert_s83("INVALID_UTF8", verifier.parse_strict_json_bytes, b"\xff")
        self._assert_s83("FLOAT_FORBIDDEN", verifier.parse_strict_json_bytes, b'{"a":1.0}\n')
        self._assert_s83("NONFINITE_JSON_CONSTANT", verifier.parse_strict_json_bytes, b'{"a":NaN}\n')
        self._assert_s83("DUPLICATE_JSON_KEY", verifier.parse_strict_json_bytes, b'{"a":1,"a":2}\n')
        self._assert_s83("INVALID_JSON", verifier.parse_strict_json_bytes, b"{bad")
        self._assert_s83("INVALID_ROOT_TYPE", verifier.parse_strict_json_bytes, b"[1]\n")
        self._assert_s83("NONCANONICAL_JSON", verifier.parse_strict_json_bytes, b'{"a": 1}\n', require_canonical=True)

        self.assertEqual(verifier.parse_canonical_rational_str("0", "q"), Fraction(0))
        self.assertEqual(verifier.parse_canonical_rational_str("-3/4", "q"), Fraction(-3, 4))
        for bad, code in (
            ("", "INVALID_RATIONAL"),
            ("1/2/3", "INVALID_RATIONAL"),
            ("1/-2", "INVALID_RATIONAL"),
            ("3/1", "NONCANONICAL_RATIONAL"),
            ("1/0", "NONCANONICAL_RATIONAL"),
            ("2/4", "NONCANONICAL_RATIONAL"),
            ("0/2", "NONCANONICAL_RATIONAL"),
        ):
            self._assert_s83(code, verifier.parse_canonical_rational_str, bad, "q")


class Test04SecondaryAuditReplayAndCLI(unittest.TestCase):
    def setUp(self) -> None:
        raw = verifier.read_regular_bytes_capped(_THIS_DIR / "s83_epistemic_mesh_certificate.json", "cert")
        self.cert = verifier.parse_strict_json_bytes(raw, "cert", require_canonical=True)

    def _assert_s83(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S83Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_envelope_hash_and_full_replay_mismatch(self) -> None:
        self._assert_s83("INVALID_BOOL", verifier.verify_certificate_dict, self.cert, full_replay=1)
        self._assert_s83("INVALID_CERT_TYPE", verifier.verify_certificate_dict, [], full_replay=False)
        self._assert_s83("INVALID_PAYLOAD_TYPE", verifier.secondary_audit_payload, [])

        bad_schema = copy.deepcopy(self.cert)
        bad_schema["schema_version"] = "bad"
        self._assert_s83("SCHEMA_MISMATCH", verifier.verify_certificate_dict, bad_schema, full_replay=False)

        bad_tid = copy.deepcopy(self.cert)
        bad_tid["track_id"] = "bad"
        self._assert_s83("SCHEMA_MISMATCH", verifier.verify_certificate_dict, bad_tid, full_replay=False)

        bad_psha = copy.deepcopy(self.cert)
        bad_psha["payload_sha256"] = "0" * 64
        self._assert_s83("PAYLOAD_SHA_MISMATCH", verifier.verify_certificate_dict, bad_psha, full_replay=False)

        bad_csha = copy.deepcopy(self.cert)
        bad_csha["certificate_sha256"] = "0" * 64
        self._assert_s83("CERT_SHA_MISMATCH", verifier.verify_certificate_dict, bad_csha, full_replay=False)

        fr1_only = copy.deepcopy(self.cert)
        fr1_only["payload"]["pinned_artifacts"]["lakefile_sha256"] = "0" * 64
        fr1_only = _resign_cert(fr1_only)
        self.assertTrue(verifier.verify_certificate_dict(fr1_only, full_replay=False)["valid"])
        cached_lean = {
            "lean_version": "Lean (version 4.36.0)",
            "theorems_verified": len(oracle.LEAN_THEOREM_NAMES),
            "lean_source_sha256": self.cert["payload"]["pinned_artifacts"]["lean_source_sha256"],
        }
        with mock.patch.object(verifier, "verify_lean4_file_live", return_value=cached_lean):
            self._assert_s83("FULL_REPLAY_MISMATCH", verifier.verify_certificate_dict, fr1_only, full_replay=True)

    def test_load_track_artifacts_errors(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "lean-toolchain").write_bytes(b"\xff\xfe")
            self._assert_s83("INVALID_UTF8", verifier._load_track_artifacts, root)
            (root / "lean-toolchain").write_bytes(b"leanprover/lean4:v4.10.0\n")
            self._assert_s83("TOOLCHAIN_MISMATCH", verifier._load_track_artifacts, root)

    def test_secondary_audit_exhaustive_tamper_kills(self) -> None:
        def tamper(code: str, fn) -> None:
            c = copy.deepcopy(self.cert)
            fn(c["payload"])
            self._assert_s83(code, verifier.secondary_audit_payload, c["payload"])
            resigned = _resign_cert(c)
            self._assert_s83(code, verifier.verify_certificate_dict, resigned, full_replay=False)

        tamper("INVALID_SCHEMA_KEYS", lambda p: p.__setitem__("extra", 1))
        tamper("INVALID_SCHEMA_DICT", lambda p: p.__setitem__("pinned_artifacts", []))
        tamper("SCHEMA_MISMATCH", lambda p: p.__setitem__("schema_version", "bad"))
        tamper("SCHEMA_MISMATCH", lambda p: p.__setitem__("track_id", "bad"))
        tamper("SCHEMA_MISMATCH", lambda p: p.__setitem__("oracle_class", "bad"))
        tamper("SCHEMA_MISMATCH", lambda p: p.__setitem__("novelty_classification", "N2"))
        tamper("SCHEMA_MISMATCH", lambda p: p["pinned_artifacts"].__setitem__("lean_source", "x.lean"))
        tamper("SCHEMA_MISMATCH", lambda p: p["pinned_artifacts"].__setitem__("lean_toolchain", "bad"))
        tamper("THEOREM_LIST_MISMATCH", lambda p: p["pinned_artifacts"].__setitem__("lean_theorem_names", []))
        tamper("THEOREM_LIST_MISMATCH", lambda p: p["pinned_artifacts"].__setitem__("lean_theorem_names", {k: 0 for k in oracle.LEAN_THEOREM_NAMES}))
        tamper("THEOREM_LIST_MISMATCH", lambda p: p["pinned_artifacts"]["lean_theorem_names"].__setitem__(0, "bad"))

        # Nodes
        tamper("INVALID_NODES", lambda p: p.__setitem__("mesh_nodes", []))
        tamper("INVALID_NODES", lambda p: p.__setitem__("mesh_nodes", "12345678"))
        tamper("INVALID_NODE_ID", lambda p: p["mesh_nodes"][0].__setitem__("id", "v9"))

        # Pillar 1
        tamper("PILLAR1_COUNTS", lambda p: p["pillar1_schur_compounding"]["pathway_class_counts"].__setitem__("EXACT_COMMUTE", 9))
        tamper("PILLAR1_ALGEBRA", lambda p: p["pillar1_schur_compounding"].__setitem__("total_conductance_q", "69"))
        tamper("INVALID_INERTIA", lambda p: p["pillar1_schur_compounding"].__setitem__("laplacian_inertia", [7, 0]))
        tamper("INVALID_INERTIA", lambda p: p["pillar1_schur_compounding"].__setitem__("laplacian_inertia", "701"))
        tamper("INERTIA_MISMATCH", lambda p: p["pillar1_schur_compounding"].__setitem__("laplacian_inertia", [6, 1, 1]))
        tamper("PILLAR1_FOSTER_FAIL", lambda p: p["pillar1_schur_compounding"].__setitem__("foster_sum_q", "6"))
        tamper("PILLAR1_FOSTER_FAIL", lambda p: p["pillar1_schur_compounding"].__setitem__("foster_identity_exact", False))
        tamper("PILLAR1_FOSTER_FAIL", lambda p: p["pillar1_schur_compounding"].__setitem__("all_28_pairs_strictly_compounded", False))
        tamper("PILLAR1_CORE4_FAIL", lambda p: p["pillar1_schur_compounding"].__setitem__("core4_all_6_edges_strictly_boosted", False))
        tamper("PILLAR1_PAIRS", lambda p: p["pillar1_schur_compounding"].__setitem__("pair_rows", []))
        tamper("PILLAR1_PAIRS", lambda p: p["pillar1_schur_compounding"].__setitem__("pair_rows", "x" * 28))
        tamper("PILLAR1_PAIR_CLS", lambda p: p["pillar1_schur_compounding"]["pair_rows"][0].__setitem__("pathway_class", "BAD"))

        # Targeted isolated subcondition kills on pair_rows[0] (L711)
        def _t_pair0(p, **kw):
            p["pillar1_schur_compounding"]["pair_rows"][0].update(kw)

        tamper("PILLAR1_PAIR_ALGEBRA", lambda p: _t_pair0(p, direct_w_q="4", schur_boost_q="1", g_eff_q="5", r_eff_q="1/5", compounding_gain_q="5/4", compounding_gain_dec4="1.2500"))
        tamper("PILLAR1_PAIR_ALGEBRA", lambda p: _t_pair0(p, schur_boost_q="0", g_eff_q="2", r_eff_q="1/2", compounding_gain_q="1", compounding_gain_dec4="1.0000"))
        tamper("PILLAR1_PAIR_ALGEBRA", lambda p: _t_pair0(p, schur_boost_q="1", g_eff_q="4", r_eff_q="1/4", compounding_gain_q="2", compounding_gain_dec4="2.0000"))
        tamper("PILLAR1_PAIR_ALGEBRA", lambda p: _t_pair0(p, schur_boost_q="2", g_eff_q="4", r_eff_q="1/5", compounding_gain_q="2", compounding_gain_dec4="2.0000"))
        tamper("PILLAR1_PAIR_ALGEBRA", lambda p: _t_pair0(p, schur_boost_q="2", g_eff_q="4", r_eff_q="1/4", compounding_gain_q="3", compounding_gain_dec4="3.0000"))
        tamper("PILLAR1_PAIR_ALGEBRA", lambda p: _t_pair0(p, compounding_gain_dec4="9.9999"))
        # Consistent valid pair_rows[0] change breaks recomputed Foster sum != 7
        tamper("PILLAR1_FOSTER_FAIL", lambda p: _t_pair0(p, schur_boost_q="2", g_eff_q="4", r_eff_q="1/4", compounding_gain_q="2", compounding_gain_dec4="2.0000"))

        tamper("PILLAR1_EXTREMA", lambda p: p["pillar1_schur_compounding"].__setitem__("min_compounding_gain_q", "1"))
        tamper("PILLAR1_EXTREMA", lambda p: p["pillar1_schur_compounding"].__setitem__("min_compounding_gain_dec4", "1.0000"))
        tamper("PILLAR1_EXTREMA", lambda p: p["pillar1_schur_compounding"].__setitem__("max_compounding_gain_q", "1"))
        tamper("PILLAR1_EXTREMA", lambda p: p["pillar1_schur_compounding"].__setitem__("max_compounding_gain_dec4", "1.0000"))
        tamper("PILLAR1_CORE4_LEN", lambda p: p["pillar1_schur_compounding"].__setitem__("core4_edges", []))
        tamper("PILLAR1_CORE4_LEN", lambda p: p["pillar1_schur_compounding"].__setitem__("core4_edges", "123456"))

        def _t_c4(p, **kw):
            p["pillar1_schur_compounding"]["core4_edges"][0].update(kw)

        tamper("PILLAR1_CORE4_ALGEBRA", lambda p: _t_c4(p, direct_w_q="-1", core4_boost_q="3", core4_eff_w_q="2", core4_ratio_dec4="-2.0000"))
        tamper("PILLAR1_CORE4_ALGEBRA", lambda p: _t_c4(p, direct_w_q="2", core4_boost_q="0", core4_eff_w_q="2", core4_ratio_dec4="1.0000"))
        tamper("PILLAR1_CORE4_ALGEBRA", lambda p: _t_c4(p, direct_w_q="2", core4_boost_q="1", core4_eff_w_q="4", core4_ratio_dec4="2.0000"))
        tamper("PILLAR1_CORE4_ALGEBRA", lambda p: _t_c4(p, core4_ratio_dec4="9.9999"))

        # Pillar 2
        tamper("PILLAR2_SUM", lambda p: p["pillar2_triangle_holonomy"]["classification_counts"].__setitem__("EXACT_TRANSITIVE_CLOSURE", 2))
        tamper("PILLAR2_PARITY", lambda p: p["pillar2_triangle_holonomy"].__setitem__("even_z2_holonomy_triangles", 33))
        tamper("PILLAR2_PARITY", lambda p: (
            p["pillar2_triangle_holonomy"].__setitem__("odd_z2_holonomy_triangles", 21),
            p["pillar2_triangle_holonomy"].__setitem__("even_z2_holonomy_triangles", 35),
        ))
        tamper("PILLAR2_LISTS", lambda p: p["pillar2_triangle_holonomy"].__setitem__("exact_transitive_closures", "abc"))
        tamper("PILLAR2_LISTS", lambda p: p["pillar2_triangle_holonomy"].__setitem__("exact_transitive_closures", []))
        tamper("PILLAR2_LISTS", lambda p: p["pillar2_triangle_holonomy"].__setitem__("frustrated_curvature_loops", "x" * 22))
        tamper("PILLAR2_LISTS", lambda p: p["pillar2_triangle_holonomy"].__setitem__("frustrated_curvature_loops", []))
        tamper("PILLAR2_LISTS", lambda p: p["pillar2_triangle_holonomy"].__setitem__("multi_wall_boundary_sectors", "x" * 7))
        tamper("PILLAR2_LISTS", lambda p: p["pillar2_triangle_holonomy"].__setitem__("multi_wall_boundary_sectors", []))
        tamper("PILLAR2_BIANCHI", lambda p: p["pillar2_triangle_holonomy"].__setitem__("bianchi_coboundary_zero_all_70", False))
        tamper("PILLAR2_BOOST", lambda p: p["pillar2_triangle_holonomy"].__setitem__("min_3node_schur_boost_q", "0"))
        tamper("PILLAR2_BOOST", lambda p: p["pillar2_triangle_holonomy"].__setitem__("max_3node_schur_boost_q", "1/4"))
        # Boundary PASS for b_min == b_max
        ok_b = copy.deepcopy(self.cert["payload"])
        ok_b["pillar2_triangle_holonomy"]["max_3node_schur_boost_q"] = ok_b["pillar2_triangle_holonomy"]["min_3node_schur_boost_q"]
        self.assertTrue(verifier.secondary_audit_payload(ok_b)["secondary_audit_passed"])

        # Pillar 3
        tamper("PILLAR3_SPLIT_PCT", lambda p: p["pillar3_silo_cuts_and_firewall"]["split_summary"]["4|4"].__setitem__("pathways_severed_pct_dec2", "50.00"))
        tamper("PILLAR3_SPLIT_PCT", lambda p: p["pillar3_silo_cuts_and_firewall"]["split_summary"]["4|4"].__setitem__("triangles_destroyed_pct_dec2", "80.00"))
        tamper("PILLAR3_CUT_W", lambda p: p["pillar3_silo_cuts_and_firewall"]["split_summary"]["4|4"].__setitem__("min_weighted_cut_q", "0"))
        tamper("PILLAR3_CUT_W", lambda p: p["pillar3_silo_cuts_and_firewall"]["split_summary"]["4|4"].__setitem__("max_weighted_cut_q", "30"))
        ok_w = copy.deepcopy(self.cert["payload"])
        ok_w["pillar3_silo_cuts_and_firewall"]["split_summary"]["4|4"]["max_weighted_cut_q"] = "33"
        self.assertTrue(verifier.secondary_audit_payload(ok_w)["secondary_audit_passed"])

        def _t_fw(p, **kw):
            p["pillar3_silo_cuts_and_firewall"]["contagion_firewall_case"].update(kw)

        tamper("PILLAR3_CONTAGION", lambda p: _t_fw(p, injected_error_q="2"))
        tamper("PILLAR3_CONTAGION", lambda p: _t_fw(p, direct_edge_flux_q="-1", ungated_total_flux_q="1", ungated_flux_amplification_q="-1", ungated_flux_amplification_dec4="-1.0000"))
        tamper("PILLAR3_CONTAGION", lambda p: _t_fw(p, direct_edge_flux_q="4", ungated_total_flux_q="4", ungated_flux_amplification_q="1", ungated_flux_amplification_dec4="1.0000"))
        tamper("PILLAR3_CONTAGION", lambda p: _t_fw(p, ungated_flux_amplification_q="2", ungated_flux_amplification_dec4="2.0000"))
        tamper("PILLAR3_CONTAGION", lambda p: _t_fw(p, ungated_flux_amplification_dec4="9.9999"))
        tamper("PILLAR3_CONTAGION", lambda p: _t_fw(p, flux_equals_schur_g_eff=False))
        tamper("PILLAR3_CONTAGION", lambda p: _t_fw(p, all_6_interior_nodes_corrupted=False))
        tamper("PILLAR3_IE_RANGE", lambda p: p["pillar3_silo_cuts_and_firewall"]["contagion_firewall_case"]["interior_node_errors_q"].__setitem__("v1", "0"))
        tamper("PILLAR3_IE_RANGE", lambda p: p["pillar3_silo_cuts_and_firewall"]["contagion_firewall_case"]["interior_node_errors_q"].__setitem__("v1", "1"))
        tamper("PILLAR3_FIREWALL", lambda p: _t_fw(p, gated_firewall_flux_q="1"))
        tamper("PILLAR3_FIREWALL", lambda p: _t_fw(p, gated_firewall_interior_max_error_q="1"))
        tamper("PILLAR3_FIREWALL", lambda p: _t_fw(p, gated_k7_pathways_retained_pct_dec2="70.00"))
        tamper("PILLAR3_FIREWALL", lambda p: _t_fw(p, gated_k7_triangles_retained_pct_dec2="60.00"))
        tamper("PILLAR3_FIREWALL", lambda p: _t_fw(p, gated_k7_all_21_pairs_compounded=False))
        tamper("PILLAR3_K7_GAIN", lambda p: _t_fw(p, gated_k7_min_compounding_gain_q="1", gated_k7_min_compounding_gain_dec4="1.0000"))
        tamper("PILLAR3_K7_GAIN", lambda p: _t_fw(p, gated_k7_min_compounding_gain_dec4="9.9999"))

    def test_y_full_replay_and_fr0_pass(self) -> None:
        try:
            verifier.resolve_lean_binary()
            has_lean = True
        except oracle.S83Error:
            has_lean = False
        if has_lean or os.environ.get("ALETHEIA_REQUIRE_LEAN") == "1":
            r_full = verifier.verify_certificate_dict(self.cert, full_replay=True)
            self.assertTrue(r_full["valid"])
            self.assertTrue(r_full["full_replay"])
            self.assertIn("lean_live", r_full)
        else:
            self._assert_s83("LEAN_BINARY_UNAVAILABLE", verifier.verify_certificate_dict, self.cert, full_replay=True)
            lean_sha = oracle.sha256_hex((_THIS_DIR / "AllToAllEpistemicMesh.lean").read_bytes())
            stub = {
                "lean_version": "4.36.0",
                "theorems_verified": len(oracle.LEAN_THEOREM_NAMES),
                "lean_source_sha256": lean_sha,
            }
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
            except oracle.S83Error:
                has_lean = False
            if has_lean or os.environ.get("ALETHEIA_REQUIRE_LEAN") == "1":
                rc, out, err = run_cli(["--check", str(_THIS_DIR / "s83_epistemic_mesh_certificate.json"), "--json"])
                self.assertEqual((rc, err), (0, ""))
                chk_obj = json.loads(out)
                self.assertTrue(chk_obj["valid"])
                live_receipt = chk_obj["lean_live"]
            else:
                rc, out, err = run_cli(["--check", str(_THIS_DIR / "s83_epistemic_mesh_certificate.json"), "--json"])
                self.assertEqual(rc, 2)
                self.assertEqual(out, "")
                self.assertEqual(json.loads(err)["code"], "LEAN_BINARY_UNAVAILABLE")
                live_receipt = {
                    "lean_version": "4.36.0",
                    "theorems_verified": len(oracle.LEAN_THEOREM_NAMES),
                    "lean_source_sha256": oracle.sha256_hex((_THIS_DIR / "AllToAllEpistemicMesh.lean").read_bytes()),
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
                self.assertEqual(out.encode("ascii"), (_THIS_DIR / "s83_epistemic_mesh_certificate.json").read_bytes())

                rc, out, err = run_cli([])
                self.assertEqual((rc, err), (0, ""))
                self.assertTrue(out.startswith("OK "))

                rc, out, err = run_cli(["--json"])
                self.assertEqual((rc, err), (0, ""))
                self.assertTrue(json.loads(out)["valid"])

                with mock.patch.object(verifier.sys, "argv", ["verify_s83_epistemic_mesh.py", "--json"]):
                    rc, out, err = run_cli(None)
                    self.assertEqual((rc, err), (0, ""))
                    self.assertTrue(json.loads(out)["valid"])

            bad_cases = [
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
            ]
            for bad_argv, code in bad_cases:
                rc, out, err = run_cli(bad_argv)
                self.assertEqual(rc, 2, f"argv={bad_argv!r}")
                self.assertEqual(out, "")
                self.assertEqual(json.loads(err)["code"], code)
            self._assert_s83("NUL_BYTE_FORBIDDEN", verifier._parse_cli_args, ["--check", "a\x00b"])
            self.assertEqual(verifier._parse_cli_args([])["mode"], "default")


class Test05LeanGatesR10Plus(unittest.TestCase):
    def _assert_s83(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S83Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_strip_and_r10_plus_static_gate(self) -> None:
        lean_src = (_THIS_DIR / "AllToAllEpistemicMesh.lean").read_text(encoding="utf-8")
        verifier.static_gate_lean4_source(lean_src)

        stripped = verifier._strip_lean4_for_static_gate(
            "/- outer / - /- sorry -/ -/ -- axiom\n"
            "def x := a / b - c\n"
            "-- eof comment"
        )
        self.assertNotIn("sorry", stripped)
        self.assertNotIn("axiom", stripped)
        self.assertIn("a / b - c", stripped)
        s_dash = verifier._strip_lean4_for_static_gate("/- a - sorry -/\n")
        self.assertNotIn("sorry", s_dash)
        self.assertEqual(s_dash.strip(), "")
        s_slash = verifier._strip_lean4_for_static_gate("/- a / sorry -/\n")
        self.assertNotIn("sorry", s_slash)
        self.assertEqual(s_slash.strip(), "")
        self._assert_s83("LEAN4_UNTERMINATED_LEX", verifier._strip_lean4_for_static_gate, "/- unclosed")

        self._assert_s83("LEAN4_BAD_CHARS", verifier.static_gate_lean4_source, lean_src + "\r")
        self._assert_s83("LEAN4_BAD_CHARS", verifier.static_gate_lean4_source, lean_src + "\x00")

        for escape in (
            "\nsorry\n",
            "\nadmit\n",
            "\naxiom bad : Prop\n",
            "\nunsafe def u := 0\n",
            "\ntheorem t : True := by native_decide\n",
            "\ndef s := sorryAx\n",
            "\nset_option debug.skipKernelTC true\n",
            "\nset_option debug.byAsSorry true\n",
            "\nset_option «debug».«skipKernelTC» true\n",
            "\n@[extern \"c_fn\"] def f : Nat := 0\n",
            "\nattribute [implemented_by f] g\n",
            "\n@[csimp] theorem c : True := trivial\n",
            "\nopaque hidden : Nat := 0\n",
            "\npartial def loop : Nat := loop\n",
            "\ndef ok := 1; partial def loop : Nat := loop\n",
            "\ntheorem t : True := by decide +native\n",
            "\nprivate theorem _e1 : 1 = 1 := by decide -revert +native\n",
            "\nprivate theorem _e2 : 1 = 1 := by decide +revert +native\n",
            "\ntheorem t : 1 = 1 := by decide (revert := true) +native\n",
            "\ntheorem t : 1 = 1 := by decide (config := myCfg)\n",
            "\ndef cfg : DecideConfig := {}\n",
            "\ntheorem t : True := by decide (native := !false)\n",
            "\ntheorem t : True := by decide (native := (true))\n",
            "\n#eval 1 + 1\n",
            "\n#reduce 1\n",
            "\n#exit\n",
            "\n#print Nat\n",
            "\nimport Mathlib\n",
            "\nimport Lean\n",
            "\nimport Std\n",
            "\nmacro \"bad\" : term => `(sorry)\n",
            "\nmacro_rules | `(bad) => `(sorry)\n",
            "\nelab \"bad\" : command => pure ()\n",
            "\nsyntax \"bad\" : term\n",
            "\ndeclare_syntax_cat evil\n",
            '\nnotation "openq\\"" => 0\n',
            '\ndef x := s!"{(by sorry : String)}"\n',
            '\ndef x := f!"{(by sorry : String)}"\n',
            '\ndef x := foo!"bad"\n',
            '\ndef x := r"\\"\n',
            '\ndef _a := r#"""#\naxiom evil : False\ndef _b := r#"""#\n',
            "\ndef q1 : Char := '\"'\n#eval 1\ndef q2 : Char := '\"'\n",
            '\ndbg_trace "{(by sorry : Nat)}"\n',
            "\ntheorem t : False := by «sorry»\n",
        ):
            self._assert_s83("LEAN4_TRUST_ESCAPE", verifier.static_gate_lean4_source, lean_src + escape)

        self._assert_s83(
            "LEAN4_MISSING_THEOREM",
            verifier.static_gate_lean4_source,
            lean_src.replace("theorem schur_3node_conductance_exact", "theorem renamed_thm"),
        )
        self._assert_s83(
            "LEAN4_MISSING_PRINT_AXIOMS",
            verifier.static_gate_lean4_source,
            lean_src.replace("#print axioms AllToAllEpistemicMesh.schur_3node_conductance_exact", ""),
        )

    def test_resolve_and_verify_lean_live_and_mocked(self) -> None:
        try:
            verifier.resolve_lean_binary()
            has_lean = True
        except oracle.S83Error:
            has_lean = False
        if has_lean or os.environ.get("ALETHEIA_REQUIRE_LEAN") == "1":
            live = verifier.verify_lean4_file_live(_THIS_DIR / "AllToAllEpistemicMesh.lean")
            self.assertEqual(live["theorems_verified"], len(oracle.LEAN_THEOREM_NAMES))
            self.assertIn("4.36.0", live["lean_version"])
        else:
            self._assert_s83("LEAN_BINARY_UNAVAILABLE", verifier.verify_lean4_file_live, _THIS_DIR / "AllToAllEpistemicMesh.lean")

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
                self._assert_s83("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(noexec_bin)}):
                self._assert_s83("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(dir_bin)}):
                self._assert_s83("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)

            env_no = {k: v for k, v in os.environ.items() if k != "ALETHEIA_LEAN_BIN"}
            with mock.patch.dict(os.environ, env_no, clear=True):
                with mock.patch.object(verifier.shutil, "which", return_value=str(fake_bin)):
                    self.assertEqual(verifier.resolve_lean_binary(), str(fake_bin))
                home_d = Path(td) / "h"
                (home_d / ".local" / "bin" / "lean").mkdir(parents=True)
                (home_d / ".elan" / "bin").mkdir(parents=True)
                elan_lean = home_d / ".elan" / "bin" / "lean"
                elan_lean.write_text("#!/bin/sh\n", encoding="utf-8")
                os.chmod(elan_lean, 0o600)
                with mock.patch.object(verifier.shutil, "which", return_value=str(noexec_bin)), mock.patch.object(
                    verifier.Path, "home", return_value=home_d
                ):
                    self._assert_s83("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
                os.chmod(elan_lean, 0o700)
                with mock.patch.object(verifier.shutil, "which", return_value=None), mock.patch.object(
                    verifier.Path, "home", return_value=home_d
                ):
                    self.assertEqual(verifier.resolve_lean_binary(), str(elan_lean))
                os.unlink(elan_lean)
                with mock.patch.object(verifier.shutil, "which", return_value=None), mock.patch.object(
                    verifier.Path, "home", return_value=home_d
                ):
                    self._assert_s83("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)

            bad_utf8 = Path(td) / "bad.lean"
            bad_utf8.write_bytes(b"\xff\xfe")
            self._assert_s83("INVALID_UTF8", verifier.verify_lean4_file_live, bad_utf8)

            base_lean = (_THIS_DIR / "AllToAllEpistemicMesh.lean").read_text(encoding="utf-8")
            for idx_e, exploit_tail in enumerate((
                "\nprivate theorem _e1 : 1 = 1 := by decide -revert +native\n",
                "\nprivate theorem _e2 : 1 = 1 := by decide +revert +native\n",
                "\ndef q1 : Char := '\"'\n#eval 1\ndef q2 : Char := '\"'\n",
                "\nset_option «debug».«skipKernelTC» true\n",
            )):
                exp_p = Path(td) / f"exp_{idx_e}.lean"
                exp_p.write_text(base_lean + exploit_tail, encoding="utf-8")
                self._assert_s83("LEAN4_TRUST_ESCAPE", verifier.verify_lean4_file_live, exp_p)

        lean_path = _THIS_DIR / "AllToAllEpistemicMesh.lean"
        ok_ver = subprocess.CompletedProcess(["lean", "--version"], 0, "Lean (version 4.36.0, x86_64)\n", "")

        def run_mock(ver_res, comp_res):
            seq = [ver_res, comp_res]

            def side_eff(*a, **kw):
                item = seq.pop(0)
                if isinstance(item, BaseException):
                    raise item
                return item

            return mock.patch.object(verifier.subprocess, "run", side_effect=side_eff)

        with mock.patch.object(verifier, "resolve_lean_binary", return_value="lean"):
            with run_mock(OSError("no"), ok_ver):
                self._assert_s83("LEAN_EXEC_ERROR", verifier.verify_lean4_file_live, lean_path)
            with run_mock(subprocess.CompletedProcess(["lean"], 0, "Lean (version 4.10.0)\n", ""), ok_ver):
                self._assert_s83("LEAN_VERSION_MISMATCH", verifier.verify_lean4_file_live, lean_path)
            with run_mock(subprocess.CompletedProcess(["lean"], 1, "Lean (version 4.36.0)\n", ""), ok_ver):
                self._assert_s83("LEAN_VERSION_MISMATCH", verifier.verify_lean4_file_live, lean_path)
            with run_mock(ok_ver, subprocess.TimeoutExpired(["lean"], 120)):
                self._assert_s83("LEAN_EXEC_ERROR", verifier.verify_lean4_file_live, lean_path)
            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 1, "", "")):
                self._assert_s83("LEAN_COMPILE_FAIL", verifier.verify_lean4_file_live, lean_path)
            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 0, "", "err")):
                self._assert_s83("LEAN_STDERR_NONEMPTY", verifier.verify_lean4_file_live, lean_path)
            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 0, "warning: unused\n", "")):
                self._assert_s83("LEAN_WARNING_FORBIDDEN", verifier.verify_lean4_file_live, lean_path)
            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 0, "weird line\n", "")):
                self._assert_s83("LEAN_UNEXPECTED_STDOUT", verifier.verify_lean4_file_live, lean_path)

            lines_ok = [f"'{oracle.LEAN_THEOREM_NAMES[0]}' does not depend on any axioms", ""]
            lines_ok.append(f"'{oracle.LEAN_THEOREM_NAMES[1]}' depends on axioms: []")
            lines_ok.append(f"'{oracle.LEAN_THEOREM_NAMES[2]}' depends on axioms: [propext,")
            lines_ok.append("  ,")
            lines_ok.append("  Quot.sound]")
            for t in oracle.LEAN_THEOREM_NAMES[3:]:
                lines_ok.append(f"'{t}' depends on axioms: [propext, Quot.sound]")
            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 0, "\n".join(lines_ok) + "\n", "")):
                res = verifier.verify_lean4_file_live(lean_path)
                self.assertEqual(res["theorems_verified"], len(oracle.LEAN_THEOREM_NAMES))

            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 0, f"'{oracle.LEAN_THEOREM_NAMES[0]}' depends on axioms: [propext,\n", "")):
                self._assert_s83("LEAN_UNEXPECTED_STDOUT", verifier.verify_lean4_file_live, lean_path)
            dup_none = f"'{oracle.LEAN_THEOREM_NAMES[0]}' does not depend on any axioms\n" * 2
            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 0, dup_none, "")):
                self._assert_s83("LEAN_DUPLICATE_THEOREM", verifier.verify_lean4_file_live, lean_path)
            dup_dep = f"'{oracle.LEAN_THEOREM_NAMES[0]}' depends on axioms: [propext]\n" * 2
            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 0, dup_dep, "")):
                self._assert_s83("LEAN_DUPLICATE_THEOREM", verifier.verify_lean4_file_live, lean_path)

            bad_ax = f"'{oracle.LEAN_THEOREM_NAMES[0]}' depends on axioms: [Classical.choice]\n"
            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 0, bad_ax, "")):
                self._assert_s83("LEAN_FORBIDDEN_AXIOM", verifier.verify_lean4_file_live, lean_path)
            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 0, "\n".join(lines_ok[:-1]) + "\n", "")):
                self._assert_s83("LEAN_THEOREM_SET_MISMATCH", verifier.verify_lean4_file_live, lean_path)


if __name__ == "__main__":
    unittest.main()
