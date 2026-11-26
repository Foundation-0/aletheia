#!/usr/bin/env python3
"""Aletheia R5 Adversarial, Zone-B, R10+ Lean-Gate & Mutation-Killer Test Suite for Track S91.

100% pure Python 3 stdlib, zero bare asserts, zero AST floats, zero .isdigit(),
zero random imports, CI chmod-644 compatible, zero-skip no-Lean CI compatible.
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
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import s91_transhistorical_k26_oracle as oracle  # noqa: E402
import verify_s91_transhistorical_k26 as verifier  # noqa: E402


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


def _has_lean_436() -> bool:
    try:
        lb = verifier.resolve_lean_binary()
        proc = subprocess.run([lb, "--version"], capture_output=True, text=True, timeout=15, check=False)
        return proc.returncode == 0 and "4.36.0" in proc.stdout
    except (oracle.S91Error, OSError, subprocess.TimeoutExpired):
        return False


def _load_disk_cert() -> dict:
    raw = verifier.read_regular_bytes_capped(_THIS_DIR / "s91_transhistorical_k26_certificate.json", "cert")
    return verifier.parse_strict_json_bytes(raw, "cert", require_canonical=True)


def _load_disk_anchor() -> tuple[dict, str]:
    raw = verifier.read_regular_bytes_capped(_THIS_DIR / "s91_tusi_circularep_live_anchor.json", "anchor")
    return verifier.parse_strict_json_bytes(raw, "anchor", require_canonical=True), oracle.sha256_hex(raw)


class Test01StaticHygiene(unittest.TestCase):
    def test_ast_and_text_hygiene(self) -> None:
        r4_bad = re.compile(r"(?i)" + "4-" + "mode|" + "all " + r"four (isolated|python|execution)|" + "four " + "isolated")
        for fname in (
            "s91_transhistorical_k26_oracle.py",
            "verify_s91_transhistorical_k26.py",
            "test_s91_transhistorical_k26_r5.py",
        ):
            raw = (_THIS_DIR / fname).read_bytes()
            self.assertNotIn(b"\r", raw, fname)
            src = raw.decode("utf-8", "strict")
            self.assertNotIn("/" + "home/", src, fname)
            self.assertNotIn("/dev/" + "null", src, fname)
            self.assertIsNone(r4_bad.search(src), fname)
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

    def test_disk_jsons_zero_float_canonical_and_edges_disjoint(self) -> None:
        cert = _load_disk_cert()
        self.assertIs(type(cert), dict)
        anchor, _ = _load_disk_anchor()
        self.assertIs(type(anchor), dict)
        self.assertEqual(len(oracle._EXACT_COMMUTE_PAIRS & oracle._EXACT_OBSTRUCTION_PAIRS), 0)
        self.assertEqual(len(oracle.K26_NODES), 26)


class Test02OraclePrimitivesAndMath(unittest.TestCase):
    def _assert_s91(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S91Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_primitive_guards_and_json_tree(self) -> None:
        self.assertIs(oracle.require_bool(True, "b"), True)
        self.assertIs(oracle.require_bool(False, "b"), False)
        for bad in (0, 1, "true", None):
            self._assert_s91("INVALID_BOOL", oracle.require_bool, bad, "b")

        self.assertEqual(oracle.require_exact_int(5, "x", lo=5, hi=5), 5)
        max_exact_int = (1 << oracle.MAX_INT_BITS) - 1
        self.assertEqual(oracle.require_exact_int(max_exact_int, "x"), max_exact_int)
        self._assert_s91("INVALID_INT", oracle.require_exact_int, True, "x")
        self._assert_s91("INVALID_INT", oracle.require_exact_int, _IntSub(5), "x")
        self._assert_s91("INT_OUT_OF_RANGE", oracle.require_exact_int, 4, "x", lo=5)
        self._assert_s91("INT_OUT_OF_RANGE", oracle.require_exact_int, 6, "x", hi=5)
        self._assert_s91("INT_TOO_LARGE", oracle.require_exact_int, 1 << oracle.MAX_INT_BITS, "x")

        self.assertEqual(oracle.require_exact_str("ok", "s"), "ok")
        self._assert_s91("INVALID_STR", oracle.require_exact_str, _StrSub("a"), "s")
        self._assert_s91("INVALID_UTF8_SURROGATE", oracle.require_exact_str, "\ud800", "s")

        h64 = "0123456789abcdef" * 4
        self.assertEqual(oracle.require_hex64(h64, "h"), h64)
        self._assert_s91("INVALID_HEX64", oracle.require_hex64, h64[:-1], "h")
        self._assert_s91("INVALID_HEX64", oracle.require_hex64, "A" + h64[1:], "h")

        self.assertTrue(oracle.is_ascii_digits("0123456789"))
        self.assertFalse(oracle.is_ascii_digits(""))
        self.assertFalse(oracle.is_ascii_digits("12x"))
        self.assertFalse(oracle.is_ascii_digits("\u00b2"))

        shared = [1, 2]
        oracle.validate_strict_json_tree({"a": shared, "b": shared, "n": None, "t": True, "s": "ok"})
        oracle.validate_strict_json_tree(max_exact_int)
        nested: list = []
        cur = nested
        for _ in range(oracle.MAX_JSON_DEPTH):
            nxt: list = []
            cur.append(nxt)
            cur = nxt
        oracle.validate_strict_json_tree(nested)
        cur.append(0)
        self._assert_s91("JSON_DEPTH_EXCEEDED", oracle.validate_strict_json_tree, nested)
        self._assert_s91("INT_TOO_LARGE", oracle.validate_strict_json_tree, 1 << oracle.MAX_INT_BITS)
        cyc_l: list = []
        cyc_l.append(cyc_l)
        self._assert_s91("JSON_CYCLE", oracle.validate_strict_json_tree, cyc_l)
        cyc_d: dict = {}
        cyc_d["self"] = cyc_d
        self._assert_s91("JSON_CYCLE", oracle.validate_strict_json_tree, cyc_d)
        self._assert_s91("INVALID_JSON_TYPE", oracle.validate_strict_json_tree, _ListSub([1]))
        self._assert_s91("INVALID_JSON_TYPE", oracle.validate_strict_json_tree, _DictSub({"a": 1}))
        self._assert_s91("INVALID_JSON_TYPE", oracle.validate_strict_json_tree, (1, 2))

    def test_dec_and_sci_parsers_and_linear_algebra(self) -> None:
        self.assertEqual(oracle.dec_from_q(Fraction(-1, 200), 1), "0.0")
        self.assertEqual(oracle.dec_from_q(Fraction(5, 2), 0), "3")
        self.assertEqual(oracle.dec_from_q(Fraction(-5, 2), 0), "-3")
        self.assertEqual(oracle.q_str(Fraction(4, 1)), "4")
        self.assertEqual(oracle.q_str(Fraction(3, 4)), "3/4")

        self.assertEqual(oracle.parse_decimal_or_sci_to_q("1.25e+2", "d"), Fraction(125, 1))
        self.assertEqual(oracle.parse_decimal_or_sci_to_q("-2.5E-2", "d"), Fraction(-1, 40))
        self.assertEqual(oracle.parse_decimal_or_sci_to_q("42e1", "d"), Fraction(420, 1))
        self.assertEqual(oracle.parse_decimal_or_sci_to_q("42", "d"), Fraction(42, 1))
        self.assertEqual(oracle.parse_decimal_or_sci_to_q("1e-100", "d"), Fraction(1, 10 ** 100))
        self.assertEqual(oracle.parse_decimal_or_sci_to_q("1e100", "d"), Fraction(10 ** 100, 1))
        self.assertEqual(oracle.parse_decimal_or_sci_to_q("1" * 64, "d"), Fraction(int("1" * 64), 1))
        for bad in (
            "", "1e2e3", "1e+", "1e00001", "1e12345", "1e200", "1e-200", "1.2.3", "a.1", "1.b", "12a", "1" * 65,
        ):
            self._assert_s91("INVALID_DEC_STR", oracle.parse_decimal_or_sci_to_q, bad, "d")

        # q_invert_spd non-SPD rejection
        self._assert_s91("NOT_SPD", oracle.q_invert_spd, [[Fraction(0)]])
        self._assert_s91("NOT_SPD", oracle.q_invert_spd, [[Fraction(-1)]])

        # q_symmetric_inertia: negative diag, zero-diag swap, 2x2 hyperbolic pivot, zero row
        self.assertEqual(oracle.q_symmetric_inertia([[Fraction(-2)]]), [0, 1, 0])
        self.assertEqual(
            oracle.q_symmetric_inertia([[Fraction(0), Fraction(0)], [Fraction(0), Fraction(3)]]),
            [1, 0, 1],
        )
        self.assertEqual(
            oracle.q_symmetric_inertia([
                [Fraction(0), Fraction(0), Fraction(2)],
                [Fraction(0), Fraction(0), Fraction(0)],
                [Fraction(2), Fraction(0), Fraction(0)],
            ]),
            [1, 1, 1],
        )
        # r_eff_from_g_red all branches
        g2 = [[Fraction(2), Fraction(1)], [Fraction(1), Fraction(3)]]
        self.assertEqual(oracle.r_eff_from_g_red(g2, 0, 1), Fraction(2))
        self.assertEqual(oracle.r_eff_from_g_red(g2, 1, 0), Fraction(2))
        self.assertEqual(oracle.r_eff_from_g_red(g2, 1, 2), Fraction(3))

        # _comb boundary branches & _simulate_relay_switches (kills all BoolOp flips/drops)
        self.assertEqual(oracle._comb(5, -1), 0)
        self.assertEqual(oracle._comb(5, 6), 0)
        self.assertEqual(oracle._comb(5, 2), 10)
        self.assertEqual(oracle._simulate_relay_switches((80, 90, 92, 80, 90), 76, 88), 1)
        self.assertEqual(oracle._simulate_relay_switches((80, 90, 75, 70), 76, 88), 2)

        # Pillar 1 anchor validation guards
        anchor, a_sha = _load_disk_anchor()
        self._assert_s91("INVALID_ANCHOR", oracle.compute_pillar1_tusi_cure, [], a_sha)
        bad_a = copy.deepcopy(anchor)
        bad_a["schema_version"] = "wrong"
        self._assert_s91("ANCHOR_SCHEMA", oracle.compute_pillar1_tusi_cure, bad_a, a_sha)
        bad_a = copy.deepcopy(anchor)
        bad_a["upstream"]["commit_sha"] = "0" * 40
        self._assert_s91("ANCHOR_COMMIT", oracle.compute_pillar1_tusi_cure, bad_a, a_sha)
        bad_a = copy.deepcopy(anchor)
        bad_a["upstream"]["best_json_sha256"] = "0" * 64
        self._assert_s91("ANCHOR_BEST_SHA", oracle.compute_pillar1_tusi_cure, bad_a, a_sha)
        bad_a = copy.deepcopy(anchor)
        bad_a["upstream"]["puzzles_json_sha256"] = "0" * 64
        self._assert_s91("ANCHOR_PUZ_SHA", oracle.compute_pillar1_tusi_cure, bad_a, a_sha)
        h64 = "a" * 64
        self._assert_s91("INVALID_HEX64", oracle.build_certificate, anchor=anchor, anchor_sha256="bad", lean_source_sha256=h64, toolchain_sha256=h64, lakefile_sha256=h64)
        self._assert_s91("INVALID_HEX64", oracle.build_certificate, anchor=anchor, anchor_sha256=h64, lean_source_sha256="bad", toolchain_sha256=h64, lakefile_sha256=h64)
        self._assert_s91("INVALID_HEX64", oracle.build_certificate, anchor=anchor, anchor_sha256=h64, lean_source_sha256=h64, toolchain_sha256="bad", lakefile_sha256=h64)
        self._assert_s91("INVALID_HEX64", oracle.build_certificate, anchor=anchor, anchor_sha256=h64, lean_source_sha256=h64, toolchain_sha256=h64, lakefile_sha256="bad")


class Test03ZoneBIOAndDarwinAndPWD(unittest.TestCase):
    def _assert_s91(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S91Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_path_darwin_cwd_pwd_guards(self) -> None:
        self._assert_s91("INVALID_PATH_TYPE", verifier._require_concrete_path, _PathSub("/tmp"), "p")
        self._assert_s91("INVALID_PATH_TYPE", verifier._require_concrete_path, "/tmp", "p")
        self._assert_s91("NUL_BYTE_FORBIDDEN", verifier._require_concrete_path, Path("/tmp/a\x00b"), "p")

        # Darwin alias normalization (mocked — kills L104, L108, L116 flip & drops)
        p_var = Path("/var/folders/x")
        fake_st = os.stat_result((stat.S_IFLNK | 0o777, 0, 0, 1, 0, 0, 0, 0, 0, 0))
        with mock.patch.object(verifier.sys, "platform", "linux"), mock.patch.object(verifier.os, "lstat", return_value=fake_st), mock.patch.object(verifier.os, "readlink", return_value="private/var"):
            self.assertEqual(verifier._normalize_darwin_system_prefix(p_var), p_var)
        with mock.patch.object(verifier.sys, "platform", "darwin"):
            with mock.patch.object(verifier.os, "lstat", return_value=fake_st), mock.patch.object(verifier.os, "readlink", return_value="private/var"):
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("x/var/folders")), Path("x/var/folders"))
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/var")), Path("/var"))
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/var/../folders/x")), Path("/var/../folders/x"))
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/opt/x/y")), Path("/opt/x/y"))
                self.assertEqual(verifier._normalize_darwin_system_prefix(p_var), Path("/private/var/folders/x"))
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/var"), allow_exact=True), Path("/private/var"))
            fake_nonroot = os.stat_result((stat.S_IFLNK | 0o777, 0, 0, 1, 1000, 0, 0, 0, 0, 0))
            with mock.patch.object(verifier.os, "lstat", return_value=fake_nonroot), mock.patch.object(verifier.os, "readlink", return_value="private/var"):
                self.assertEqual(verifier._normalize_darwin_system_prefix(p_var), p_var)
            fake_dir = os.stat_result((stat.S_IFDIR | 0o755, 0, 0, 1, 0, 0, 0, 0, 0, 0))
            with mock.patch.object(verifier.os, "lstat", return_value=fake_dir), mock.patch.object(verifier.os, "readlink", return_value="private/var"):
                self.assertEqual(verifier._normalize_darwin_system_prefix(p_var), p_var)
            with mock.patch.object(verifier.os, "lstat", return_value=fake_st), mock.patch.object(verifier.os, "readlink", return_value="/evil"):
                self.assertEqual(verifier._normalize_darwin_system_prefix(p_var), p_var)
            with mock.patch.object(verifier.os, "lstat", side_effect=OSError("no")):
                self.assertEqual(verifier._normalize_darwin_system_prefix(p_var), p_var)

        with mock.patch.object(verifier.Path, "cwd", side_effect=OSError("gone")):
            self._assert_s91("CWD_UNAVAILABLE", verifier._safe_cwd, "cwd")

        # NUL in PWD kills M004
        with mock.patch.object(verifier.os.environ, "get", return_value="/tmp/a\x00b"):
            self._assert_s91("NUL_BYTE_FORBIDDEN", verifier._check_pwd_no_symlinks, "rel")

        # Live symlinked $PWD test
        with tempfile.TemporaryDirectory(prefix="s91_pwd_") as td:
            real_sub = Path(td) / "real"
            real_sub.mkdir()
            (real_sub / "a.txt").write_bytes(b"hi")
            sym_sub = Path(td) / "sym"
            sym_sub.symlink_to(real_sub)
            orig_cwd = os.getcwd()
            orig_pwd = os.environ.get("PWD")
            try:
                os.chdir(str(real_sub))
                os.environ["PWD"] = str(sym_sub)
                self._assert_s91("SYMLINK_ANCESTOR_FORBIDDEN", verifier.read_regular_bytes_capped, Path("a.txt"), "rel")
                os.environ["PWD"] = str(real_sub)
                self.assertEqual(verifier.read_regular_bytes_capped(Path("a.txt"), "rel"), b"hi")
                os.environ["PWD"] = "relative"
                verifier._check_pwd_no_symlinks("rel")
                os.environ["PWD"] = "/nonexistent_s91_dir_xyz"
                verifier._check_pwd_no_symlinks("rel")
                os.environ["PWD"] = "/"
                verifier._check_pwd_no_symlinks("rel")
                os.environ["PWD"] = str(real_sub)
                with mock.patch.object(verifier.os, "open", side_effect=OSError(errno.EACCES, "denied")):
                    self._assert_s91("CWD_UNAVAILABLE", verifier._check_pwd_no_symlinks, "rel")
            finally:
                os.chdir(orig_cwd)
                if orig_pwd is None:
                    os.environ.pop("PWD", None)
                else:
                    os.environ["PWD"] = orig_pwd

    def test_read_and_write_zone_b_guards(self) -> None:
        with tempfile.TemporaryDirectory(prefix="s91_io_") as td:
            base = Path(td)
            reg = base / "reg.bin"
            reg.write_bytes(b"hello")
            self.assertEqual(verifier.read_regular_bytes_capped(reg, "r", max_bytes=5), b"hello")
            self._assert_s91("FILE_TOO_LARGE", verifier.read_regular_bytes_capped, reg, "r", max_bytes=4)
            self._assert_s91("NOT_A_REGULAR_FILE", verifier.read_regular_bytes_capped, Path("/"), "r")
            self._assert_s91("NOT_A_REGULAR_FILE", verifier._open_dir_chain, base / "..", "r", create_parents=False)
            self._assert_s91("NOT_A_REGULAR_FILE", verifier.read_regular_bytes_capped, base, "r")
            self._assert_s91("FILE_READ_ERROR", verifier.read_regular_bytes_capped, base / "missing.bin", "r")
            self._assert_s91("FILE_READ_ERROR", verifier.read_regular_bytes_capped, base / "no_dir" / "x", "r")
            self.assertFalse((base / "no_dir").exists())

            # Symlink leaf & symlink ancestor
            sym_leaf = base / "sym.bin"
            sym_leaf.symlink_to(reg)
            self._assert_s91("SYMLINK_FORBIDDEN", verifier.read_regular_bytes_capped, sym_leaf, "r")
            sub = base / "sub"
            sub.mkdir()
            (sub / "f.bin").write_bytes(b"ok")
            sym_dir = base / "sym_dir"
            sym_dir.symlink_to(sub)
            self._assert_s91("SYMLINK_FORBIDDEN", verifier.read_regular_bytes_capped, sym_dir / "f.bin", "r")
            self._assert_s91("SYMLINK_FORBIDDEN", verifier.write_regular_bytes_safe, sym_dir / "w.bin", b"x", "w")

            # Hardlink read & write rejection
            hl = base / "hardlink.bin"
            os.link(reg, hl)
            self._assert_s91("HARDLINK_FORBIDDEN", verifier.read_regular_bytes_capped, hl, "r")
            self._assert_s91("HARDLINK_FORBIDDEN", verifier.write_regular_bytes_safe, hl, b"x", "w")
            os.unlink(hl)

            # Live FIFO non-hanging rejection
            fifo = base / "pipe.fifo"
            os.mkfifo(fifo)
            self._assert_s91("NOT_A_REGULAR_FILE", verifier.read_regular_bytes_capped, fifo, "r")
            self._assert_s91("NOT_A_REGULAR_FILE", verifier.write_regular_bytes_safe, fifo, b"x", "w")

            # Write guards: non-bytes, symlink target, nested parent create, umask 077 -> 0o600
            self._assert_s91("INVALID_PAYLOAD_BYTES", verifier.write_regular_bytes_safe, base / "o", "notbytes", "w")
            self._assert_s91("SYMLINK_FORBIDDEN", verifier.write_regular_bytes_safe, sym_leaf, b"x", "w")
            nested_out = base / "new_a" / "new_b" / "out.json"
            old_um = os.umask(0o022)
            try:
                verifier.write_regular_bytes_safe(nested_out, b'{"ok":true}\n', "w")
            finally:
                os.umask(old_um)
            self.assertEqual(stat.S_IMODE(nested_out.stat().st_mode), 0o600)
            self.assertEqual(nested_out.read_bytes(), b'{"ok":true}\n')
            # Overwrite existing regular single-link file cleanly
            verifier.write_regular_bytes_safe(nested_out, b'{"ok":false}\n', "w")
            self.assertEqual(nested_out.read_bytes(), b'{"ok":false}\n')

            # Kill all OSError & st_size guards in Zone-B I/O (M009, M011, M012, M023, M025, M029, M034, M040, M041)
            with mock.patch.object(verifier.os, "open", side_effect=OSError(errno.EACCES, "root")):
                self._assert_s91("FILE_READ_ERROR", verifier.read_regular_bytes_capped, reg, "r")
            with mock.patch.object(verifier.os, "mkdir", side_effect=OSError(errno.EACCES, "mk")):
                with self.assertRaises(oracle.S91Error) as mk_ctx:
                    verifier.write_regular_bytes_safe(base / "mkfail" / "a", b"x", "w")
                self.assertEqual(mk_ctx.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("mkdir failed", mk_ctx.exception.detail)
            orig_open = os.open
            def _fail_reopen(path, flags, *a, **kw):
                if path == "mkfail2":
                    raise OSError(errno.EACCES, "reopen")
                return orig_open(path, flags, *a, **kw)
            with mock.patch.object(verifier.os, "open", side_effect=_fail_reopen):
                self._assert_s91("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, base / "mkfail2" / "a", b"x", "w")
            def _fail_reopen_after_mk(path, flags, *a, **kw):
                if path == "mkfail3" and (base / "mkfail3").exists():
                    raise OSError(errno.EACCES, "reopen_post")
                return orig_open(path, flags, *a, **kw)
            with mock.patch.object(verifier.os, "open", side_effect=_fail_reopen_after_mk):
                self._assert_s91("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, base / "mkfail3" / "a", b"x", "w")
            orig_fstat = os.fstat
            def _big_st_size(fd: int):
                st = orig_fstat(fd)
                return os.stat_result((st.st_mode, st.st_ino, st.st_dev, st.st_nlink, st.st_uid, st.st_gid, 99, st.st_atime, st.st_mtime, st.st_ctime))
            with mock.patch.object(verifier.os, "fstat", side_effect=_big_st_size):
                self._assert_s91("FILE_TOO_LARGE", verifier.read_regular_bytes_capped, reg, "r", max_bytes=5)
            with mock.patch.object(verifier.os, "read", side_effect=OSError(errno.EIO, "io")):
                self._assert_s91("FILE_READ_ERROR", verifier.read_regular_bytes_capped, reg, "r")
            with mock.patch.object(verifier.os, "lstat", side_effect=OSError(errno.EACCES, "ls")):
                self._assert_s91("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, base / "lsfail", b"x", "w")
            def _fail_tmp_open(path, flags, *a, **kw):
                if isinstance(path, str) and path.startswith(".s91."):
                    raise OSError(errno.EACCES, "tmp")
                return orig_open(path, flags, *a, **kw)
            with mock.patch.object(verifier.os, "open", side_effect=_fail_tmp_open):
                with self.assertRaises(oracle.S91Error) as tmp_ctx:
                    verifier.write_regular_bytes_safe(base / "tmpfail", b"x", "w")
                self.assertEqual(tmp_ctx.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("temp open failed", tmp_ctx.exception.detail)
            with mock.patch.object(verifier.os, "write", side_effect=OSError(errno.ENOSPC, "full")):
                self._assert_s91("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, base / "wrfail", b"x", "w")
            with mock.patch.object(verifier.os, "replace", side_effect=OSError(errno.EXDEV, "rep")):
                self._assert_s91("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, base / "repfail", b"x", "w")

            # Streaming cap overflow & mocked write edge errors
            with mock.patch.object(verifier.os, "read", side_effect=[b"12345", b"6", b""]):
                self._assert_s91("FILE_TOO_LARGE", verifier.read_regular_bytes_capped, reg, "r", max_bytes=5)
            with mock.patch.object(verifier.os, "write", return_value=0):
                self._assert_s91("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, base / "short.bin", b"abc", "w")
            def _bad_nlink(fd: int):
                st = orig_fstat(fd)
                return os.stat_result((st.st_mode, st.st_ino, st.st_dev, 2, st.st_uid, st.st_gid, st.st_size, st.st_atime, st.st_mtime, st.st_ctime))
            with mock.patch.object(verifier.os, "fstat", side_effect=_bad_nlink):
                self._assert_s91("HARDLINK_FORBIDDEN", verifier.write_regular_bytes_safe, base / "nl.bin", b"abc", "w")


class Test04StrictJSONAndRationalParsers(unittest.TestCase):
    def _assert_s91(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S91Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_strict_json_and_rational_edges(self) -> None:
        self._assert_s91("INVALID_BYTES", verifier.parse_strict_json_bytes, "str", "j")
        self._assert_s91("BOM_FORBIDDEN", verifier.parse_strict_json_bytes, b"\xef\xbb\xbf{}\n", "j")
        self._assert_s91("CRLF_FORBIDDEN", verifier.parse_strict_json_bytes, b"{}\r\n", "j")
        self._assert_s91("INVALID_UTF8", verifier.parse_strict_json_bytes, b"\xff\xfe", "j")
        self._assert_s91("FLOAT_FORBIDDEN", verifier.parse_strict_json_bytes, b'{"x":1.5}\n', "j")
        self._assert_s91("NONFINITE_JSON_CONSTANT", verifier.parse_strict_json_bytes, b'{"x":NaN}\n', "j")
        self._assert_s91("DUPLICATE_JSON_KEY", verifier.parse_strict_json_bytes, b'{"a":1,"a":2}\n', "j")
        self._assert_s91("INVALID_JSON", verifier.parse_strict_json_bytes, b"{bad", "j")
        self._assert_s91("INVALID_ROOT_TYPE", verifier.parse_strict_json_bytes, b"[1,2]\n", "j")
        self._assert_s91("NONCANONICAL_JSON", verifier.parse_strict_json_bytes, b'{"a": 1}\n', "j", require_canonical=True)
        self.assertEqual(verifier.parse_strict_json_bytes(b'{"a": 1}\n', "j", require_canonical=False), {"a": 1})
        self._assert_s91("INT_TOO_LARGE", verifier.parse_strict_json_bytes, (f'{{"a":{"9" * (oracle.MAX_INT_DIGITS + 1)}}}\n').encode("ascii"), "j")
        self._assert_s91("NONCANONICAL_INT", verifier._parse_bounded_int, "01")
        self._assert_s91("NONCANONICAL_INT", verifier._parse_bounded_int, "-0")
        self._assert_s91("INVALID_INT_TOKEN", verifier._parse_bounded_int, "12a")
        self.assertEqual(verifier._parse_bounded_int("0"), 0)
        self.assertEqual(verifier._parse_bounded_int("-10"), -10)
        # Exact MAX_INT_DIGITS (2467) & MAX_INT_BITS (8192) boundaries (kills M043, M044, M047, M048)
        max_exact_bits = (1 << oracle.MAX_INT_BITS) - 1
        self.assertEqual(len(str(max_exact_bits)), oracle.MAX_INT_DIGITS)
        self.assertEqual(verifier._parse_bounded_int(str(max_exact_bits)), max_exact_bits)
        self._assert_s91("INT_TOO_LARGE", verifier._parse_bounded_int, str(1 << oracle.MAX_INT_BITS))
        self._assert_s91("INT_TOO_LARGE", verifier._parse_bounded_int, "9" * 5000)

        # Direct _require_exact_dict guards (kills M067, M069)
        self._assert_s91("INVALID_SCHEMA_DICT", verifier._require_exact_dict, [], frozenset({"a"}), "d")
        self._assert_s91("INVALID_SCHEMA_KEYS", verifier._require_exact_dict, {"b": 1}, frozenset({"a"}), "d")

        self.assertEqual(verifier.parse_canonical_rational_str("7", "q"), Fraction(7, 1))
        self.assertEqual(verifier.parse_canonical_rational_str("-3/5", "q"), Fraction(-3, 5))
        self._assert_s91("INVALID_RATIONAL", verifier.parse_canonical_rational_str, "", "q")
        self._assert_s91("INVALID_RATIONAL", verifier.parse_canonical_rational_str, "1/2/3", "q")
        self._assert_s91("INVALID_RATIONAL", verifier.parse_canonical_rational_str, "1/-2", "q")
        self._assert_s91("NONCANONICAL_RATIONAL", verifier.parse_canonical_rational_str, "3/1", "q")
        self._assert_s91("NONCANONICAL_RATIONAL", verifier.parse_canonical_rational_str, "2/4", "q")


class Test05R11PlusLeanStaticAndLiveGate(unittest.TestCase):
    def _assert_s91(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S91Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_r11_plus_static_lean_exploits_and_clean_controls(self) -> None:
        real_src = (_THIS_DIR / "TranshistoricalK26AndTusiCure.lean").read_text(encoding="utf-8")
        verifier.static_gate_lean4_source(real_src)
        # Nested block comments, '/' in code, positive clean controls (0 FP), & EOF comment
        clean_with_nested = (
            "/- outer /- sorry axiom -/ outer -/\n"
            "-- native_decide\n"
            "def ratio_ok := 1 / 1\n"
            "export Nat (succ)\n"
            "attribute [simp] init\n"
            "theorem pos_ctrl1 : 1 = 1 := by decide (native := false)\n"
            "theorem pos_ctrl2 : 1 = 1 := by decide (native := Bool.false)\n"
            + real_src
            + "-- eof"
        )
        verifier.static_gate_lean4_source(clean_with_nested)

        # Bad chars & unterminated block comment
        self._assert_s91("LEAN4_BAD_CHARS", verifier.static_gate_lean4_source, real_src + "\r\n")
        self._assert_s91("LEAN4_BAD_CHARS", verifier.static_gate_lean4_source, real_src + "\x00")
        self._assert_s91("LEAN4_UNTERMINATED_LEX", verifier.static_gate_lean4_source, real_src + "\n/- unclosed")
        self._assert_s91("LEAN4_UNTERMINATED_LEX", verifier.static_gate_lean4_source, "/- a /- b -/\n" + real_src)

        # Missing theorem & missing #print axioms
        first_thm = oracle.LEAN_THEOREM_NAMES[0]
        first_short = first_thm.split(".")[-1]
        self._assert_s91("LEAN4_MISSING_THEOREM", verifier.static_gate_lean4_source, real_src.replace(f"theorem {first_short}", "theorem renamed_x"))
        self._assert_s91("LEAN4_MISSING_PRINT_AXIOMS", verifier.static_gate_lean4_source, real_src.replace(f"#print axioms {first_thm}", ""))

        # Full R11+ adversarial trust-escape probes (incl. AUDIT-191 S91-F2 multiline & attribute exploits)
        exploits = (
            "theorem bad : True := by sorry",
            "theorem bad : True := by admit",
            "axiom bad : False",
            "unsafe def bad := 0",
            "theorem bad : 1 = 1 := by native_decide",
            "def bad := sorryAx",
            "def bad := _root_.sorryAx",
            "def bad := Lean.Meta.mkSorry",
            "def bad := ofReduceBool",
            "def bad := Lean.ofReduceBool",
            "def bad := ofReduceNat",
            "def bad := Lean.ofReduceNat",
            "def bad := trustCompiler",
            "def bad := Lean.trustCompiler",
            "def bad := Lean.Elab.Command.elabCommand",
            "def bad := mkSorry",
            "run_cmd pure ()",
            "macro x : term => x",
            "elab x : term => x",
            "declare_syntax_cat evil",
            "def bad := dbg_trace 1",
            "def bad := dbgTrace 1",
            "def bad := dbgTraceVal 1",
            "def bad := dbgTraceValId 1",
            "def bad := dbgTraceIfShared 1",
            "def bad := dbgSleep 1",
            "def bad := dbgStackTrace 1",
            "def bad := panicWithPosWithDecl 1",
            "def bad : Nat := panic! (String.ofList [])",
            "def bad : Nat := unreachable!",
            "def bad := throwError 1",
            "notation x => x",
            "@[csimp] theorem x : True := trivial",
            "opaque bad : Nat",
            "set_option debug.skipKernelTC true",
            "set_option warn.sorry false",
            "@[extern c] def bad : Nat := 0",
            "@[export evil_c] def bad : Nat := 0",
            "attribute [export evil_c] bad",
            "@[init] def bad : IO Unit := pure ()",
            "attribute [init] bad",
            "@[builtin_init] def bad : IO Unit := pure ()",
            "attribute [builtin_init] bad",
            "partial def bad : Nat := bad",
            "partial theorem bad : True := trivial",
            "theorem bad : 1 = 1 := by decide +native",
            "theorem bad : 1 = 1 := by decide -revert +native",
            "theorem bad : 1 = 1 := by decide (config := { native := true })",
            "theorem bad : 1 = 1 := by decide +revert (config := { native })",
            "theorem bad : 1 = 1 := by decide (revert := false) (config := { native })",
            "def bad := { ({} : _) with native }",
            "theorem bad : 1 = 1 := by decide (native := false || true)",
            "theorem bad : 1 = 1 := by decide (native := false == false)",
            "theorem bad : 1 = 1 := by decide (native := false != true)",
            "theorem bad : 1 = 1 := by decide (native := false.not)",
            "theorem bad : 1 = 1 := by\n  decide (native := false\n    || true)",
            "theorem bad : 1 = 1 := by\n  decide (native := false\n    == false)",
            "theorem bad : 1 = 1 := by\n  decide (native := false -- c\n    || true)",
            "def bad : Decide.Config := default",
            "#eval 1 + 1",
            "#reduce 1 + 1",
            "#exit",
            "#guard_msgs in #print axioms x",
            "#guard 1 = 1",
            "#check 1",
            "#synth Inhabited Nat",
            "#print example",
            "import Init",
            'def s := "quoted"',
            "def «debug».«skipKernelTC» := 1",
        )
        # Minimal valid 18-theorem stub keeps 68-probe R12+ sweep fast while real_src is already gated above
        stub_src = "\n".join(
            [f"theorem {t.split('.')[-1]} : True := trivial" for t in oracle.LEAN_THEOREM_NAMES]
            + [f"#print axioms {t}" for t in oracle.LEAN_THEOREM_NAMES]
        ) + "\n"
        verifier.static_gate_lean4_source(stub_src)
        for payload_line in exploits:
            self._assert_s91("LEAN4_TRUST_ESCAPE", verifier.static_gate_lean4_source, stub_src + payload_line + "\n")

    def test_resolve_lean_and_live_runner_edge_cases(self) -> None:
        with tempfile.TemporaryDirectory(prefix="s91_lb_") as td:
            fake_exe = Path(td) / "lean"
            fake_exe.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(fake_exe, 0o755)
            non_exe = Path(td) / "noexec"
            non_exe.write_text("x", encoding="utf-8")
            os.chmod(non_exe, 0o644)

            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(fake_exe)}, clear=False):
                self.assertEqual(verifier.resolve_lean_binary(), str(fake_exe))
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(non_exe)}, clear=False):
                self._assert_s91("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(td)}, clear=False):
                self._assert_s91("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(Path(td) / "missing")}, clear=False):
                self._assert_s91("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)

            env_no_bin = {k: v for k, v in os.environ.items() if k not in ("ALETHEIA_LEAN_BIN", "HOME")}
            with mock.patch.dict(os.environ, env_no_bin, clear=True):
                with mock.patch.object(verifier.shutil, "which", return_value=str(fake_exe)):
                    self.assertEqual(verifier.resolve_lean_binary(), str(fake_exe))
                with mock.patch.object(verifier.shutil, "which", return_value=str(non_exe)):
                    self._assert_s91("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
                # Home fallback .local/bin/lean as directory (not file), non-exec file, then valid exec (kills BoolOp flip/drops)
                lbin = Path(td) / ".local" / "bin"
                lbin.mkdir(parents=True)
                home_lean = lbin / "lean"
                home_lean.mkdir()
                with mock.patch.dict(os.environ, {"HOME": str(td)}, clear=False), mock.patch.object(verifier.shutil, "which", return_value=None):
                    self._assert_s91("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
                home_lean.rmdir()
                home_lean.write_text("#!/bin/sh\n", encoding="utf-8")
                os.chmod(home_lean, 0o644)
                with mock.patch.dict(os.environ, {"HOME": str(td)}, clear=False), mock.patch.object(verifier.shutil, "which", return_value=None):
                    self._assert_s91("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
                os.chmod(home_lean, 0o755)
                with mock.patch.dict(os.environ, {"HOME": str(td)}, clear=False), mock.patch.object(verifier.shutil, "which", return_value=None):
                    self.assertEqual(verifier.resolve_lean_binary(), str(home_lean))

            # Invalid UTF-8 Lean file kills M077
            bad_utf8 = Path(td) / "bad.lean"
            bad_utf8.write_bytes(b"\xff\xfe")
            self._assert_s91("INVALID_UTF8", verifier.verify_lean4_file_live, bad_utf8)

        lean_path = _THIS_DIR / "TranshistoricalK26AndTusiCure.lean"
        v_ok = subprocess.CompletedProcess(["lean", "--version"], 0, "Lean (version 4.36.0, Release)\n", "")
        good_lines = [f"'{oracle.LEAN_THEOREM_NAMES[0]}' does not depend on any axioms"]
        for t in oracle.LEAN_THEOREM_NAMES[1:-1]:
            good_lines.append(f"'{t}' depends on axioms: [propext, Quot.sound]")
        good_lines.append(f"'{oracle.LEAN_THEOREM_NAMES[-1]}' depends on axioms: [propext,\n Quot.sound]")
        good_out = "\n".join(good_lines) + "\n"

        with mock.patch.object(verifier, "resolve_lean_binary", return_value="/usr/bin/lean"):
            poison_env = {
                "LEAN_PATH": "/evil/olean",
                "LEAN_OPTS": "-DwarningAsError=false",
                "LEAN_SRC_PATH": "/evil/src",
                "LEAN_SYSROOT": "/evil/sysroot",
                "LEAN_CC": "/evil/cc",
                "ELAN_TOOLCHAIN": "evil",
                "ELAN_HOME": "/evil/elan",
                "LD_PRELOAD": "/evil/preload.so",
                "LD_LIBRARY_PATH": "/evil/lib",
                "DYLD_INSERT_LIBRARIES": "/evil/preload.dylib",
            }
            with mock.patch.dict(os.environ, poison_env, clear=False):
                with mock.patch.object(
                    verifier.subprocess,
                    "run",
                    side_effect=[v_ok, subprocess.CompletedProcess(["lean"], 0, good_out, "")],
                ) as run_mock:
                    res = verifier.verify_lean4_file_live(lean_path)
                    self.assertEqual(res["theorems_verified"], len(oracle.LEAN_THEOREM_NAMES))
                    self.assertEqual(run_mock.call_count, 2)
                    for call in run_mock.call_args_list:
                        passed_env = call.kwargs.get("env")
                        self.assertIsNotNone(passed_env)
                        for forbidden_var in poison_env:
                            self.assertNotIn(forbidden_var, passed_env)
            with mock.patch.object(verifier.subprocess, "run", side_effect=OSError("boom")):
                self._assert_s91("LEAN_EXEC_ERROR", verifier.verify_lean4_file_live, lean_path)
            with mock.patch.object(verifier.subprocess, "run", return_value=subprocess.CompletedProcess(["lean"], 1, "4.36.0", "")):
                self._assert_s91("LEAN_VERSION_MISMATCH", verifier.verify_lean4_file_live, lean_path)
            with mock.patch.object(verifier.subprocess, "run", return_value=subprocess.CompletedProcess(["lean"], 0, "4.99.0", "")):
                self._assert_s91("LEAN_VERSION_MISMATCH", verifier.verify_lean4_file_live, lean_path)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[v_ok, OSError("boom")]):
                self._assert_s91("LEAN_EXEC_ERROR", verifier.verify_lean4_file_live, lean_path)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[v_ok, subprocess.CompletedProcess(["lean"], 1, "", "")]):
                self._assert_s91("LEAN_COMPILE_FAIL", verifier.verify_lean4_file_live, lean_path)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[v_ok, subprocess.CompletedProcess(["lean"], 0, good_out, "err")]):
                self._assert_s91("LEAN_STDERR_NONEMPTY", verifier.verify_lean4_file_live, lean_path)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[v_ok, subprocess.CompletedProcess(["lean"], 0, "warning: unused\n" + good_out, "")]):
                self._assert_s91("LEAN_WARNING_FORBIDDEN", verifier.verify_lean4_file_live, lean_path)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[v_ok, subprocess.CompletedProcess(["lean"], 0, "'x' depends on axioms: [propext\n", "")]):
                self._assert_s91("LEAN_UNEXPECTED_STDOUT", verifier.verify_lean4_file_live, lean_path)
            with mock.patch.object(verifier.subprocess, "run", side_effect=[v_ok, subprocess.CompletedProcess(["lean"], 0, "garbage\n", "")]):
                self._assert_s91("LEAN_UNEXPECTED_STDOUT", verifier.verify_lean4_file_live, lean_path)
            dup_none = f"'{oracle.LEAN_THEOREM_NAMES[0]}' does not depend on any axioms\n" * 2
            with mock.patch.object(verifier.subprocess, "run", side_effect=[v_ok, subprocess.CompletedProcess(["lean"], 0, dup_none, "")]):
                self._assert_s91("LEAN_DUPLICATE_THEOREM", verifier.verify_lean4_file_live, lean_path)
            dup_dep = f"'{oracle.LEAN_THEOREM_NAMES[0]}' depends on axioms: [propext]\n" * 2
            with mock.patch.object(verifier.subprocess, "run", side_effect=[v_ok, subprocess.CompletedProcess(["lean"], 0, dup_dep, "")]):
                self._assert_s91("LEAN_DUPLICATE_THEOREM", verifier.verify_lean4_file_live, lean_path)
            bad_ax = good_out.replace("Quot.sound", "Classical.choice")
            with mock.patch.object(verifier.subprocess, "run", side_effect=[v_ok, subprocess.CompletedProcess(["lean"], 0, bad_ax, "")]):
                self._assert_s91("LEAN_FORBIDDEN_AXIOM", verifier.verify_lean4_file_live, lean_path)
            short_out = "\n".join(good_lines[:-2]) + "\n"
            with mock.patch.object(verifier.subprocess, "run", side_effect=[v_ok, subprocess.CompletedProcess(["lean"], 0, short_out, "")]):
                self._assert_s91("LEAN_THEOREM_SET_MISMATCH", verifier.verify_lean4_file_live, lean_path)

    def test_live_lean_or_no_lean_ci_fail_closed(self) -> None:
        lean_path = _THIS_DIR / "TranshistoricalK26AndTusiCure.lean"
        if _has_lean_436():
            res = verifier.verify_lean4_file_live(lean_path)
            self.assertEqual(res["theorems_verified"], 18)
        else:
            # Zero skips in no-Lean CI: verify fail-closed LEAN_BINARY_UNAVAILABLE
            self._assert_s91("LEAN_BINARY_UNAVAILABLE", verifier.verify_lean4_file_live, lean_path)


class Test06SecondaryAuditAndReplayTampers(unittest.TestCase):
    def _assert_s91(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S91Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_exhaustive_secondary_audit_tamper_killers(self) -> None:
        base_cert = _load_disk_cert()
        base_payload = base_cert["payload"]
        res0 = verifier.verify_certificate_dict(base_cert, full_replay=False)
        self.assertTrue(res0["valid"])
        self.assertFalse(res0["full_replay"])

        # Envelope & full_replay type checks
        for bad_fr in (0, 1, "true", None):
            self._assert_s91("INVALID_BOOL", verifier.verify_certificate_dict, base_cert, full_replay=bad_fr)
        self._assert_s91("INVALID_CERT_TYPE", verifier.verify_certificate_dict, [], full_replay=False)
        self._assert_s91("INVALID_PAYLOAD_TYPE", verifier.secondary_audit_payload, [])

        def _mut_p(mutator, code: str) -> None:
            p = copy.deepcopy(base_payload)
            mutator(p)
            self._assert_s91(code, verifier.secondary_audit_payload, p)

        # Top-level & pinned artifacts tampers (incl. all 4 frozen SHA pins)
        _mut_p(lambda p: p.__setitem__("schema_version", "bad"), "SCHEMA_MISMATCH")
        _mut_p(lambda p: p.__setitem__("track_id", "bad"), "SCHEMA_MISMATCH")
        _mut_p(lambda p: p.__setitem__("oracle_class", "bad"), "SCHEMA_MISMATCH")
        _mut_p(lambda p: p.__setitem__("novelty_classification", "N2"), "SCHEMA_MISMATCH")
        _mut_p(lambda p: p["pinned_artifacts"].__setitem__("heritage_corpus_commit_sha", "0" * 40), "SCHEMA_MISMATCH")
        _mut_p(lambda p: p["pinned_artifacts"].__setitem__("anchor_file", "bad.json"), "SCHEMA_MISMATCH")
        _mut_p(lambda p: p["pinned_artifacts"].__setitem__("anchor_sha256", "0" * 64), "PINNED_SHA_MISMATCH")
        _mut_p(lambda p: p["pinned_artifacts"].__setitem__("lean_source", "bad.lean"), "SCHEMA_MISMATCH")
        _mut_p(lambda p: p["pinned_artifacts"].__setitem__("lean_source_sha256", "0" * 64), "PINNED_SHA_MISMATCH")
        _mut_p(lambda p: p["pinned_artifacts"].__setitem__("lean_toolchain", "bad"), "SCHEMA_MISMATCH")
        _mut_p(lambda p: p["pinned_artifacts"].__setitem__("lean_toolchain_sha256", "0" * 64), "PINNED_SHA_MISMATCH")
        _mut_p(lambda p: p["pinned_artifacts"].__setitem__("lakefile_sha256", "0" * 64), "PINNED_SHA_MISMATCH")
        _mut_p(lambda p: p["pinned_artifacts"].__setitem__("lean_theorem_names", {t: 1 for t in oracle.LEAN_THEOREM_NAMES}), "THEOREM_LIST_MISMATCH")
        _mut_p(lambda p: p["pinned_artifacts"]["lean_theorem_names"].__setitem__(0, "bad"), "THEOREM_LIST_MISMATCH")

        # Nodes tampers (exact length dict + exact pin match)
        _mut_p(lambda p: p.__setitem__("k26_nodes", {str(i): 1 for i in range(26)}), "INVALID_NODES")
        _mut_p(lambda p: p["k26_nodes"].pop(), "INVALID_NODES")
        _mut_p(lambda p: p["k26_nodes"][0].__setitem__("id", "bad"), "INVALID_NODE_PIN")
        _mut_p(lambda p: p["k26_nodes"][0].__setitem__("era", "classical"), "INVALID_NODE_PIN")
        _mut_p(lambda p: p["k26_nodes"][0].__setitem__("source_sha256", "0" * 64), "INVALID_NODE_PIN")
        _mut_p(lambda p: p["k26_nodes"][0].__setitem__("extra", 1), "INVALID_SCHEMA_KEYS")

        # Pillar 1 exact_q_witnesses tampers (algebraic + Vieta + exact boundaries)
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"].__setitem__("anchor_sha256", "0" * 64), "PILLAR1_ANCHOR_SHA")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"].__setitem__("upstream_commit_sha", "bad"), "PILLAR1_COMMIT")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"].__setitem__("upstream_best_json_sha256", "bad"), "PILLAR1_BEST")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"].__setitem__("planar_tusi_couple", []), "INVALID_SCHEMA_DICT")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["planar_tusi_couple"].__setitem__("injected_key", 1), "INVALID_SCHEMA_KEYS")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["planar_tusi_couple"].__setitem__("discriminant_t_q", "1"), "PILLAR1_DISC")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["planar_tusi_couple"].__setitem__("t_fro_sq_q", "1"), "PILLAR1_TF")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["planar_tusi_couple"].__setitem__("k_fro_sq_q", "1"), "PILLAR1_KF")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["planar_tusi_couple"].__setitem__("m_fro_sq_q", "99"), "PILLAR1_PYTH")
        for fk in ("discriminant_nonneg", "h2_off_diag_zero", "pythagorean_exact"):
            _mut_p(lambda p, fk=fk: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["planar_tusi_couple"].__setitem__(fk, False), "PILLAR1_WITNESS_FLAGS")
        # Eigenvalues type, len, Vieta sum/prod (kills OP_SWAP + SUBCOND_DEL), and t_rho exact match
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["s76_elliptic_curl"].__setitem__("t_eigenvalues_q", {"a": 1, "b": 2}), "PILLAR1_EIGS")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["s76_elliptic_curl"].__setitem__("t_eigenvalues_q", ["9/10"]), "PILLAR1_EIGS")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["s76_elliptic_curl"].__setitem__("t_eigenvalues_q", ["3/5", "0"]), "PILLAR1_VIETA")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["s76_elliptic_curl"].__setitem__("t_eigenvalues_q", ["27/100", "-1"]), "PILLAR1_VIETA")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["s76_elliptic_curl"].__setitem__("t_rho_q", "1/2"), "PILLAR1_TRHO")
        # Witness-specific post-algebra checks (consistent algebra so only target check fires!)
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["planar_tusi_couple"].update({"t12_q": "1/5", "discriminant_t_q": "4/25", "t_fro_sq_q": "4/5", "m_fro_sq_q": "52/25"}), "PILLAR1_PLANAR")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["planar_tusi_couple"].update({"k12_q": "0", "k_fro_sq_q": "0", "m_fro_sq_q": "18/25"}), "PILLAR1_PLANAR_K")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["s76_elliptic_curl"].update({"t11_q": "1", "t12_q": "0", "t22_q": "0", "discriminant_t_q": "1", "t_fro_sq_q": "1", "m_fro_sq_q": "3", "t_eigenvalues_q": ["1", "0"], "t_rho_q": "1"}), "PILLAR1_ELLIPTIC")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["law5_nonnormal_destabilization"].update({"t11_q": "1", "t12_q": "0", "t22_q": "0", "discriminant_t_q": "1", "t_fro_sq_q": "1", "m_fro_sq_q": "3", "t_eigenvalues_q": ["1", "0"], "t_rho_q": "1"}), "PILLAR1_LAW5")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["law5_nonnormal_destabilization"].__setitem__("raw_rho_q", "1"), "PILLAR1_LAW5")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["law5_nonnormal_destabilization"].__setitem__("destabilizes_contractive_loop", False), "PILLAR1_LAW5_FLAG")

        # Pillar 1 live_300_puzzle_summary tampers (all 24 keys + exact boundaries)
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"].__setitem__("live_300_puzzle_summary", []), "INVALID_SCHEMA_DICT")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("injected_key", 1), "INVALID_SCHEMA_KEYS")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("tusi_pi60_cx_median_sci", "0.000000e+00"), "PILLAR1_PI_ORDER")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("tusi_pi60_cx_median_sci", "0.069364"), "PILLAR1_PI_ORDER")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].update({"raw_pi60_cx_median_dec6": "1.000000", "tusi_pi60_cx_median_sci": "1.000000e-06", "cx_median_error_reduction_sci": "1.000000e+06"}), "PILLAR1_REDUCTION")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].update({"raw_pi60_cx_median_dec6": "1.000000", "tusi_pi60_cx_median_sci": "1.000000e-07", "cx_median_error_reduction_sci": "1.001000e+07"}), "PILLAR1_RED_RATIO")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("tusi_cx_vs_re_disparity_dec4", "0.0000"), "PILLAR1_TDISP")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].update({"tusi_cx_vs_re_disparity_dec4": "2.0000", "raw_cx_vs_re_disparity_sci": "2.000000e+09", "disparity_collapse_factor_sci": "1.000000e+09"}), "PILLAR1_COLLAPSE")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].update({"tusi_cx_vs_re_disparity_dec4": "1.0000", "raw_cx_vs_re_disparity_sci": "2.000000e+09", "disparity_collapse_factor_sci": "2.002000e+09"}), "PILLAR1_COLL_RATIO")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("norm2_median_drop_pct_dec2", "0.00"), "PILLAR1_N2DROP")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("norm2_median_drop_pct_dec2", "100.00"), "PILLAR1_N2DROP")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("law5_rho_median_lift_pct_dec2", "0.00"), "PILLAR1_RHOLIFT")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("law5_rho_median_lift_pct_dec2", "100.00"), "PILLAR1_RHOLIFT")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("skew_fro_fraction_median_dec6", "0.000000"), "PILLAR1_SKEW")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("skew_fro_fraction_median_dec6", "1.000000"), "PILLAR1_SKEW")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("tusi_max_abs_imag_sci", "1.000000e-03"), "PILLAR1_IMAG")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("tusi_max_normality_dev_sci", "0.000000e+00"), "PAYLOAD_CANONICAL_PIN_MISMATCH")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("tusi_max_normality_dev_sci", "-1.000000e-15"), "PILLAR1_NORMDEV")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("tusi_max_normality_dev_sci", "1.000000e-12"), "PILLAR1_NORMDEV")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("twin_h2_block_diag_max_err_sci", "0.000000e+00"), "PAYLOAD_CANONICAL_PIN_MISMATCH")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("twin_h2_block_diag_max_err_sci", "-1.000000e-18"), "PILLAR1_H2ERR")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("twin_h2_block_diag_max_err_sci", "1.000000e-12"), "PILLAR1_H2ERR")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("worst_puzzle_id", "test-9999"), "PILLAR1_WORST_ID")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("worst_puzzle_tusi_err_sci", "0.000000e+00"), "PILLAR1_WORST_ERR")
        _mut_p(lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("worst_puzzle_tusi_err_sci", "0.228466"), "PILLAR1_WORST_ERR")

        # Pillar 2 tampers (all 4 witnesses + exact cubic & boundary killers)
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"].__setitem__("narrow_range_p45_witness", []), "INVALID_SCHEMA_DICT")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("p_q", "0"), "PILLAR2_PA")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("radius_q", "0"), "PILLAR2_RA")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("exact_root_q", "1/5"), "PILLAR2_XR")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("q_q", "1"), "PILLAR2_CUBIC")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("lipschitz_q", "1/374"), "PILLAR2_LIP_EQ")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].update({"p_q": "300", "radius_q": "1", "exact_root_q": "1/10", "q_q": "29999/1000", "lipschitz_q": "1/100"}), "PILLAR2_LIP")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("kashi_step_errs_dec15", "abc"), "PILLAR2_KERRS")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("kashi_step_errs_dec15", ["0.000000014811523"]), "PILLAR2_KERRS")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("kashi_step_errs_dec15", ["0.000000000009874", "0.000000000009874", "0.000000000000007"]), "PILLAR2_KDEC")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("kashi_step_errs_dec15", ["0.000000014811523", "0.000000000000007", "0.000000000000007"]), "PILLAR2_KDEC")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("kashi_step_errs_dec15", ["0.000000014811523", "0.000000000009874", "0.000000000000000"]), "PILLAR2_KDEC")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("newton_step_errs_dec15", "abc"), "PILLAR2_NERRS")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("newton_step_errs_dec15", ["0.000000000003294"]), "PILLAR2_NERRS")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("newton_step_errs_dec15", ["0.000000014811523", "0.000000000000000", "0.000000000000000"]), "PILLAR2_NDEC")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("newton_step_errs_dec15", ["0.000000000003294", "0.000000000004000", "0.000000000000000"]), "PILLAR2_NDEC")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("newton_step_errs_dec15", ["0.000000000003294", "0.000000000000000", "0.000000000000001"]), "PILLAR2_NDEC")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("newton_step_errs_dec15", ["0.000000000003294", "0.000000000000000", "-0.000000000000001"]), "PILLAR2_NDEC")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("newton_step_errs_dec15", ["0.000000000003294", "0.000000000003294", "0.000000000000000"]), "PAYLOAD_CANONICAL_PIN_MISMATCH")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("chebyshev_deg3_err_dec15", "0.000000000009874"), "PILLAR2_CHEB")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("kashi_2step_beats_deg3_poly", False), "PILLAR2_BEATS")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("kashi_3step_ops", 999999), "INT_OUT_OF_RANGE")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("newton_3step_ops", 999), "INT_OUT_OF_RANGE")

        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"].__setitem__("sin_1deg_unscaled_witness", {}), "INVALID_SCHEMA_KEYS")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["sin_1deg_unscaled_witness"].__setitem__("p_q", "0"), "PILLAR2_SIN_P")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["sin_1deg_unscaled_witness"].__setitem__("q_q", "0"), "PILLAR2_SIN_Q")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["sin_1deg_unscaled_witness"].__setitem__("radius_q", "0"), "PILLAR2_SIN_R")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["sin_1deg_unscaled_witness"].__setitem__("lipschitz_q", "1/399"), "PILLAR2_SIN_LIP_EQ")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["sin_1deg_unscaled_witness"].update({"radius_q": "1/10", "lipschitz_q": "1/100"}), "PILLAR2_SIN_LIP")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["sin_1deg_unscaled_witness"].__setitem__("sin_1deg_3step_dec10", "0.0000000000"), "PILLAR2_SIN_RANGE")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["sin_1deg_unscaled_witness"].__setitem__("sin_1deg_3step_dec10", "0.0250000000"), "PILLAR2_SIN_RANGE")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["sin_1deg_unscaled_witness"].update({"sin_1deg_3step_dec10": "0.0100000000", "q_q": "5999201/100000000"}), "PILLAR2_SIN_RES")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["sin_1deg_unscaled_witness"].__setitem__("step3_delta_dec12", "0.000000000000"), "PAYLOAD_CANONICAL_PIN_MISMATCH")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["sin_1deg_unscaled_witness"].__setitem__("step3_delta_dec12", "-0.000000000001"), "PILLAR2_SIN_DELTA")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["sin_1deg_unscaled_witness"].__setitem__("step3_delta_dec12", "0.000000001000"), "PILLAR2_SIN_DELTA")

        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"].__setitem__("law5_near_cliff_newton_wins", []), "INVALID_SCHEMA_DICT")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["law5_near_cliff_newton_wins"].__setitem__("p_q", "0"), "PILLAR2_NC_P")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["law5_near_cliff_newton_wins"].__setitem__("q_q", "1"), "PILLAR2_NC_CUBIC")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["law5_near_cliff_newton_wins"].__setitem__("slope_at_root_q", "4/5"), "PILLAR2_NC_SLOPE_EQ")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["law5_near_cliff_newton_wins"].update({"p_q": "6", "exact_root_q": "1", "q_q": "5", "slope_at_root_q": "1/2"}), "PILLAR2_NC_SLOPE")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["law5_near_cliff_newton_wins"].update({"p_q": "3", "exact_root_q": "1", "q_q": "2", "slope_at_root_q": "1"}), "PILLAR2_NC_SLOPE")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["law5_near_cliff_newton_wins"].__setitem__("newton_3step_err_dec12", "0.000000000000"), "PILLAR2_NC_RATIO")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["law5_near_cliff_newton_wins"].__setitem__("kashi_3step_err_dec6", "0.019511616000"), "PILLAR2_NC_RATIO")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["law5_near_cliff_newton_wins"].__setitem__("newton_beats_kashi_by_1000x", False), "PILLAR2_NWINS")

        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"].__setitem__("law5_post_cliff_kashi_diverges", []), "INVALID_SCHEMA_DICT")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["law5_post_cliff_kashi_diverges"].__setitem__("p_q", "0"), "PILLAR2_PC_P")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["law5_post_cliff_kashi_diverges"].__setitem__("q_q", "1"), "PILLAR2_PC_CUBIC")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["law5_post_cliff_kashi_diverges"].__setitem__("slope_at_root_q", "2"), "PILLAR2_SLOPE_EQ")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["law5_post_cliff_kashi_diverges"].update({"p_q": "3", "exact_root_q": "1", "q_q": "2", "slope_at_root_q": "1"}), "PILLAR2_SLOPE")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["law5_post_cliff_kashi_diverges"].__setitem__("newton_3step_err_dec12", "0.000000000000"), "PILLAR2_PC_ORDER")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["law5_post_cliff_kashi_diverges"].__setitem__("newton_3step_err_dec12", "0.050000000000"), "PILLAR2_PC_ORDER")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["law5_post_cliff_kashi_diverges"].__setitem__("kashi_3step_err_dec6", "0.050000"), "PILLAR2_PC_ORDER")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["law5_post_cliff_kashi_diverges"].__setitem__("kashi_strictly_diverges", False), "PILLAR2_DIV")
        _mut_p(lambda p: p["pillar2_kashi_cubic_vs_newton"]["law5_post_cliff_kashi_diverges"].__setitem__("newton_strictly_converges", False), "PILLAR2_CONV")

        # Pillar 3 tampers
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"].__setitem__("banu_musa_aletheion_thermal", []), "INVALID_SCHEMA_DICT")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["banu_musa_aletheion_thermal"].__setitem__("aletheion_guard_sha256", "0" * 64), "PILLAR3_GSHA")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["banu_musa_aletheion_thermal"].__setitem__("aletheion_thermal_receipt_sha256", "0" * 64), "PILLAR3_RSHA")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["banu_musa_aletheion_thermal"].__setitem__("gpu_deadband_c", -999), "INT_OUT_OF_RANGE")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["banu_musa_aletheion_thermal"].__setitem__("live_cpu_rosen_discriminant_q", "0"), "PILLAR3_CPUD")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["banu_musa_aletheion_thermal"].__setitem__("live_gpu_rosen_discriminant_q", "0"), "PILLAR3_GPUD")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["banu_musa_aletheion_thermal"].__setitem__("law5_analog_vs_discrete_obstruction", "no analog/discrete gap exists"), "PILLAR3_BM_OBS")

        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"].__setitem__("ibn_al_nafis_septal_firewall", []), "INVALID_SCHEMA_DICT")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["ibn_al_nafis_septal_firewall"].__setitem__("galen_inertia", "bad"), "INVALID_INERTIA")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["ibn_al_nafis_septal_firewall"].__setitem__("galen_inertia", [3, 0]), "INVALID_INERTIA")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["ibn_al_nafis_septal_firewall"].__setitem__("galen_inertia", [2, 1, 1]), "INERTIA_MISMATCH")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["ibn_al_nafis_septal_firewall"].__setitem__("galen_foster_q", "2"), "PILLAR3_GFOST")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["ibn_al_nafis_septal_firewall"].__setitem__("nafis_foster_q", "2"), "PILLAR3_NFOST")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["ibn_al_nafis_septal_firewall"].__setitem__("nafis_g_eff_rv_lv_q", "2"), "PILLAR3_RAYLEIGH")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["ibn_al_nafis_septal_firewall"].__setitem__("nafis_g_eff_rv_lv_q", "0"), "PILLAR3_RAYLEIGH")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["ibn_al_nafis_septal_firewall"].__setitem__("rayleigh_conductance_drop_q", "0"), "PILLAR3_DROP")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["ibn_al_nafis_septal_firewall"].__setitem__("galen_pulmonary_frac_q", "0"), "PILLAR3_GPULM")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["ibn_al_nafis_septal_firewall"].__setitem__("galen_pulmonary_frac_q", "1"), "PILLAR3_GPULM")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["ibn_al_nafis_septal_firewall"].__setitem__("galen_shunt_bypass_frac_q", "1/3"), "PILLAR3_GSHUNT")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["ibn_al_nafis_septal_firewall"].__setitem__("nafis_shunt_bypass_frac_q", "1/2"), "PILLAR3_SHUNT")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["ibn_al_nafis_septal_firewall"].__setitem__("nafis_pulmonary_frac_q", "1/2"), "PILLAR3_PULM")
        _mut_p(lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["ibn_al_nafis_septal_firewall"].__setitem__("law5_valved_asymmetry_obstruction", "undirected graph includes one-way valves"), "PILLAR3_NF_OBS")

        # Pillar 4 tampers (incl. _require_node_pair, _audit_silo_cut, and all T09..T14 + BoolOp killers)
        _mut_p(lambda p: p.__setitem__("pillar4_k26_transhistorical_mesh", []), "INVALID_SCHEMA_DICT")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"].__setitem__("injected_key", 1), "INVALID_SCHEMA_KEYS")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["edge_class_counts"].__setitem__("EXACT_COMMUTE", 0), "INT_OUT_OF_RANGE")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"].__setitem__("total_conductance", 700), "INT_OUT_OF_RANGE")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["edge_era_counts"].__setitem__("cross_millennium", 0), "INT_OUT_OF_RANGE")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"].__setitem__("foster_sum_q", "24"), "PILLAR4_FOSTER")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"].__setitem__("kirchhoff_index_dec4", "0.0000"), "PILLAR4_KIRCH")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"].__setitem__("kirchhoff_index_dec4", "-999.0000"), "PILLAR4_KIRCH")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"].__setitem__("all_325_pairs_strictly_compounded", False), "PILLAR4_COMP")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"].__setitem__("min_compounding_gain_dec4", "1.0000"), "PILLAR4_GAIN")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"].__setitem__("min_compounding_gain_dec4", "29.2691"), "PILLAR4_GAIN")
        for bad_pair in ("m00", "m00-m01-m02", "z99-m01", "m00-z99", "m00-m00"):
            _mut_p(lambda p, bp=bad_pair: p["pillar4_k26_transhistorical_mesh"].__setitem__("min_compounding_pair", bp), "INVALID_NODE_PAIR")

        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"].__setitem__("cross_millennium_schur_compounding", []), "INVALID_SCHEMA_DICT")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["cross_millennium_schur_compounding"].__setitem__("isolated_k16_foster_q", "14"), "PILLAR4_XM_F16")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["cross_millennium_schur_compounding"].__setitem__("isolated_k10_foster_q", "8"), "PILLAR4_XM_F10")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["cross_millennium_schur_compounding"].__setitem__("all_120_modern_pairs_boosted_by_classical", False), "PILLAR4_XM_M")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["cross_millennium_schur_compounding"].__setitem__("all_45_classical_pairs_boosted_by_modern", False), "PILLAR4_XM_C")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["cross_millennium_schur_compounding"].__setitem__("modern_boost_min_pct_dec2", "0.00"), "PILLAR4_XM_MORD")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["cross_millennium_schur_compounding"].__setitem__("modern_boost_min_pct_dec2", "57.72"), "PILLAR4_XM_MORD")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["cross_millennium_schur_compounding"].__setitem__("modern_boost_median_pct_dec2", "69.24"), "PILLAR4_XM_MORD")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["cross_millennium_schur_compounding"].__setitem__("classical_boost_min_pct_dec2", "0.00"), "PILLAR4_XM_CORD")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["cross_millennium_schur_compounding"].__setitem__("classical_boost_min_pct_dec2", "146.16"), "PILLAR4_XM_CORD")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["cross_millennium_schur_compounding"].__setitem__("classical_boost_median_pct_dec2", "173.59"), "PILLAR4_XM_CORD")

        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"].__setitem__("higher_order_simplices", []), "INVALID_SCHEMA_DICT")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["higher_order_simplices"].__setitem__("order2_triangle_counts", {}), "INVALID_SCHEMA_KEYS")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["higher_order_simplices"].__setitem__("order3_bianchi_coboundary_zero_all", False), "PILLAR4_BIANCHI")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["higher_order_simplices"].__setitem__("order4_5cells_obstruction_hist", {str(i): 1 for i in range(11)}), "PILLAR4_HIST")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["higher_order_simplices"].__setitem__("order4_5cells_obstruction_hist", [65780]), "PILLAR4_HIST")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["higher_order_simplices"]["order4_5cells_obstruction_hist"].__setitem__(0, 0), "PILLAR4_HIST")

        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"].__setitem__("silo_cut_destruction", []), "INVALID_SCHEMA_DICT")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["silo_cut_destruction"]["era_silo_16_10"]["order1_edges"].__setitem__("destroyed", 0), "INT_OUT_OF_RANGE")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["silo_cut_destruction"]["balanced_13_13"]["order1_edges"].__setitem__("destroyed_pct_dec2", "0.00"), "PILLAR4_SILO_PCT")

        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"].__setitem__("t3_cross_millennium_blowup", []), "INVALID_SCHEMA_DICT")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"].__setitem__("sherman_morrison_matches_direct_inversion_on_top1", False), "PILLAR4_T3_SM")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"].__setitem__("ranked_edges", "x" * 12), "PILLAR4_T3_LEN")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"]["ranked_edges"].pop(), "PILLAR4_T3_LEN")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"]["ranked_edges"][0].__setitem__("pair", "z99-h07"), "PILLAR4_T3_PAIR")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"]["ranked_edges"].__setitem__(1, copy.deepcopy(base_payload["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"]["ranked_edges"][0])), "PILLAR4_T3_PAIR")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"]["ranked_edges"][0].__setitem__("obstruction", "forged"), "PILLAR4_T3_OBS")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"]["ranked_edges"][0].__setitem__("clean_frustrated", 3), "PILLAR4_T3_SUM")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"]["ranked_edges"][0].__setitem__("net_frustrated_reduction", -999), "INT_OUT_OF_RANGE")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"]["ranked_edges"][0].__setitem__("r_eff_before_dec6", "0.000000"), "PILLAR4_T3_REFF")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"]["ranked_edges"][0].__setitem__("delta_kirchhoff_q", "0"), "PILLAR4_T3_DK")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"]["ranked_edges"][0].__setitem__("delta_kirchhoff_dec6", "0.999999"), "PILLAR4_T3_DK_DEC")
        # Exact tie & swapped order kill > -> >= and deletion on PILLAR4_T3_ORDER
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"]["ranked_edges"][1].update({"delta_kirchhoff_q": p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"]["ranked_edges"][0]["delta_kirchhoff_q"], "delta_kirchhoff_dec6": p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"]["ranked_edges"][0]["delta_kirchhoff_dec6"]}), "PILLAR4_T3_ORDER")
        _mut_p(lambda p: p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"]["ranked_edges"].__setitem__(slice(0, 2), [p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"]["ranked_edges"][1], p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"]["ranked_edges"][0]]), "PILLAR4_T3_ORDER")

        # Envelope schema & SHA tampers + FR1 mismatch tamper
        bad_c = copy.deepcopy(base_cert)
        bad_c["schema_version"] = "bad"
        self._assert_s91("SCHEMA_MISMATCH", verifier.verify_certificate_dict, bad_c, full_replay=False)
        bad_c = copy.deepcopy(base_cert)
        bad_c["track_id"] = "bad"
        self._assert_s91("SCHEMA_MISMATCH", verifier.verify_certificate_dict, bad_c, full_replay=False)
        bad_c = copy.deepcopy(base_cert)
        bad_c["payload_sha256"] = "0" * 64
        self._assert_s91("PAYLOAD_SHA_MISMATCH", verifier.verify_certificate_dict, bad_c, full_replay=False)
        bad_c = copy.deepcopy(base_cert)
        bad_c["certificate_sha256"] = "0" * 64
        self._assert_s91("CERT_SHA_MISMATCH", verifier.verify_certificate_dict, bad_c, full_replay=False)

        # AUDIT-191 S91-F1 Regression: ALL 14/14 re-signed semantic forgeries (T01..T14) MUST fail SEC, FR0, AND FR1!
        anchor, a_sha = _load_disk_anchor()
        l_sha = base_payload["pinned_artifacts"]["lean_source_sha256"]
        tc_sha = base_payload["pinned_artifacts"]["lean_toolchain_sha256"]
        lk_sha = base_payload["pinned_artifacts"]["lakefile_sha256"]
        fake_loaded = (anchor, a_sha, l_sha, tc_sha, lk_sha, {"lean_version": "4.36.0", "theorems_verified": 18, "lean_source_sha256": l_sha})
        audit191_forgeries = (
            ("T01", lambda p: p["pinned_artifacts"].__setitem__("lean_source_sha256", "0" * 64)),
            ("T02", lambda p: p["k26_nodes"][0].__setitem__("source_sha256", "0" * 64)),
            ("T03", lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("disparity_collapse_factor_sci", "1.000000e+00")),
            ("T04", lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("injected_key", 1)),
            ("T05", lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["planar_tusi_couple"].__setitem__("injected_key", 1)),
            ("T06", lambda p: p["pillar2_kashi_cubic_vs_newton"].__setitem__("sin_1deg_unscaled_witness", {})),
            ("T07", lambda p: p["pillar2_kashi_cubic_vs_newton"]["narrow_range_p45_witness"].__setitem__("kashi_3step_ops", 999999)),
            ("T08", lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["banu_musa_aletheion_thermal"].__setitem__("gpu_deadband_c", -999)),
            ("T09", lambda p: p["pillar4_k26_transhistorical_mesh"].__setitem__("edge_class_counts", {"EXACT_COMMUTE": 0, "CONDITIONAL_BRIDGE": 0, "EXACT_OBSTRUCTION": 0})),
            ("T10", lambda p: p["pillar4_k26_transhistorical_mesh"].__setitem__("kirchhoff_index_dec4", "-999.0000")),
            ("T11", lambda p: p["pillar4_k26_transhistorical_mesh"]["silo_cut_destruction"]["era_silo_16_10"]["order1_edges"].__setitem__("destroyed", 0)),
            ("T12", lambda p: p["pillar4_k26_transhistorical_mesh"]["higher_order_simplices"].__setitem__("order2_triangle_counts", {})),
            ("T13", lambda p: p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"]["ranked_edges"][0].__setitem__("net_frustrated_reduction", -999)),
            ("T14", lambda p: p["pillar4_k26_transhistorical_mesh"].__setitem__("injected_key", 1)),
        )
        with mock.patch.object(verifier, "_load_track_artifacts", return_value=fake_loaded):
            ok_fr1 = verifier.verify_certificate_dict(base_cert, full_replay=True)
            self.assertTrue(ok_fr1["full_replay"])
            for tag, mutator in audit191_forgeries:
                forged = copy.deepcopy(base_cert)
                mutator(forged["payload"])
                forged = _resign_cert(forged)
                with self.assertRaises(oracle.S91Error, msg=f"{tag} bypassed SEC"):
                    verifier.secondary_audit_payload(forged["payload"])
                with self.assertRaises(oracle.S91Error, msg=f"{tag} bypassed FR0"):
                    verifier.verify_certificate_dict(forged, full_replay=False)
                with self.assertRaises(oracle.S91Error, msg=f"{tag} bypassed FR1"):
                    verifier.verify_certificate_dict(forged, full_replay=True)

            # AUDIT-191R3-GLM53 Regression: range-only scalar mutations & trailing-zero canonicality leaks fail SEC/FR0/FR1!
            audit191r3_forgeries = (
                ("R3_RAW_RHO", lambda p: p["pillar1_tusi_circularep_cure"]["exact_q_witnesses"]["law5_nonnormal_destabilization"].__setitem__("raw_rho_q", "1/20")),
                ("R3_CPU_ROSEN", lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["banu_musa_aletheion_thermal"].__setitem__("live_cpu_rosen_discriminant_q", "-7/850")),
                ("R3_GPU_ROSEN", lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["banu_musa_aletheion_thermal"].__setitem__("live_gpu_rosen_discriminant_q", "23/780")),
                ("R3_INIT_ERR", lambda p: p["pillar2_kashi_cubic_vs_newton"]["law5_post_cliff_kashi_diverges"].__setitem__("init_err_q", "1/200")),
                ("R3_CHATTER", lambda p: p["pillar3_banu_musa_and_ibn_al_nafis"]["banu_musa_aletheion_thermal"].__setitem__("zero_deadband_chatter_switches", 10)),
                ("R3_DEC_ZERO_LIFT", lambda p: p["pillar1_tusi_circularep_cure"]["live_300_puzzle_summary"].__setitem__("law5_rho_median_lift_pct_dec2", "47.820")),
                ("R3_DEC_ZERO_KIRCH", lambda p: p["pillar4_k26_transhistorical_mesh"].__setitem__("kirchhoff_index_dec4", "11.52260")),
                ("R3_DEC_ZERO_REFF", lambda p: p["pillar4_k26_transhistorical_mesh"]["t3_cross_millennium_blowup"]["ranked_edges"][0].__setitem__("r_eff_before_dec6", "0.0371710")),
            )
            for tag, mutator in audit191r3_forgeries:
                forged = copy.deepcopy(base_cert)
                mutator(forged["payload"])
                forged = _resign_cert(forged)
                self._assert_s91("PAYLOAD_CANONICAL_PIN_MISMATCH", verifier.secondary_audit_payload, forged["payload"])
                self._assert_s91("PAYLOAD_CANONICAL_PIN_MISMATCH", verifier.verify_certificate_dict, forged, full_replay=False)
                self._assert_s91("PAYLOAD_CANONICAL_PIN_MISMATCH", verifier.verify_certificate_dict, forged, full_replay=True)

        # FR1 replay tamper against clean SEC-passing cert (simulated on-disk drift kills FULL_REPLAY_MISMATCH)
        drifted_loaded = (anchor, a_sha, l_sha, tc_sha, "0" * 64, {"lean_version": "4.36.0", "theorems_verified": 18, "lean_source_sha256": l_sha})
        with mock.patch.object(verifier, "_load_track_artifacts", return_value=drifted_loaded):
            self._assert_s91("FULL_REPLAY_MISMATCH", verifier.verify_certificate_dict, base_cert, full_replay=True)

        # _load_track_artifacts bad toolchain
        with tempfile.TemporaryDirectory(prefix="s91_tc_") as td:
            p_td = Path(td)
            (p_td / "s91_tusi_circularep_live_anchor.json").write_bytes((_THIS_DIR / "s91_tusi_circularep_live_anchor.json").read_bytes())
            (p_td / "lean-toolchain").write_bytes(b"\xff\xfe")
            self._assert_s91("INVALID_UTF8", verifier._load_track_artifacts, p_td)
            (p_td / "lean-toolchain").write_text("leanprover/lean4:v4.0.0\n", encoding="utf-8")
            self._assert_s91("TOOLCHAIN_MISMATCH", verifier._load_track_artifacts, p_td)


class Test07CLIMainAndEndToEnd(unittest.TestCase):
    def _assert_s91(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S91Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_cli_arg_parsing_and_main_modes(self) -> None:
        self._assert_s91("INVALID_ARGV", verifier._parse_cli_args, ("--json",))
        self._assert_s91("NUL_BYTE_FORBIDDEN", verifier._parse_cli_args, ["--json\x00"])
        self._assert_s91("DUPLICATE_FLAG", verifier._parse_cli_args, ["--json", "--json"])
        self._assert_s91("CONFLICTING_MODE", verifier._parse_cli_args, ["--standalone", "--standalone"])
        self._assert_s91("CONFLICTING_MODE", verifier._parse_cli_args, ["--standalone", "--check", "x"])
        self._assert_s91("CONFLICTING_MODE", verifier._parse_cli_args, ["--standalone", "--check=x"])
        self._assert_s91("MISSING_PATH_ARG", verifier._parse_cli_args, ["--check"])
        self._assert_s91("NUL_BYTE_FORBIDDEN", verifier._parse_cli_args, ["--check", "a\x00b"])
        self._assert_s91("INVALID_PATH_ARG", verifier._parse_cli_args, ["--check", ""])
        self._assert_s91("INVALID_PATH_ARG", verifier._parse_cli_args, ["--check", "-x"])
        self._assert_s91("INVALID_PATH_ARG", verifier._parse_cli_args, ["--check="])
        self._assert_s91("INVALID_PATH_ARG", verifier._parse_cli_args, ["--write=-x"])
        self._assert_s91("UNKNOWN_FLAG", verifier._parse_cli_args, ["--bogus"])

        self.assertEqual(verifier._parse_cli_args([]), {"mode": "default", "target": None, "json": False})
        self.assertEqual(verifier._parse_cli_args(["--check=foo.json", "--json"]), {"mode": "check", "target": "foo.json", "json": True})
        self.assertEqual(verifier._parse_cli_args(["--write=bar.json"]), {"mode": "write", "target": "bar.json", "json": False})

        # Exercise all main() modes cleanly (live Lean is verified in test_live_lean_or_no_lean_ci_fail_closed & subprocess below!)
        base_cert = _load_disk_cert()
        anchor, a_sha = _load_disk_anchor()
        pa = base_cert["payload"]["pinned_artifacts"]
        fake_loaded = (anchor, a_sha, pa["lean_source_sha256"], pa["lean_toolchain_sha256"], pa["lakefile_sha256"], {"lean_version": "4.36.0", "theorems_verified": 18, "lean_source_sha256": pa["lean_source_sha256"]})
        ctx = mock.patch.object(verifier, "_load_track_artifacts", return_value=fake_loaded)

        with tempfile.TemporaryDirectory(prefix="s91_cli_") as td:
            out_path = Path(td) / "cert.json"
            with ctx:
                buf = io.StringIO()
                with mock.patch.object(sys, "stdout", buf):
                    rc = verifier.main(["--standalone"])
                self.assertEqual(rc, 0)
                self.assertEqual(buf.getvalue().encode("ascii"), oracle.canonical_json_bytes(base_cert))

                for args, expect in (
                    (["--write", str(out_path)], "WROTE "),
                    (["--write", str(out_path), "--json"], '"written":true'),
                    (["--check", str(out_path)], "OK "),
                    (["--check", str(out_path), "--json"], '"valid":true'),
                    ([], "OK "),
                    (["--json"], '"valid":true'),
                ):
                    b = io.StringIO()
                    with mock.patch.object(sys, "stdout", b):
                        self.assertEqual(verifier.main(args), 0)
                    self.assertIn(expect, b.getvalue())

            err_buf = io.StringIO()
            with mock.patch.object(sys, "stderr", err_buf):
                self.assertEqual(verifier.main(["--bogus"]), 2)
            self.assertIn("UNKNOWN_FLAG", err_buf.getvalue())

        # Subprocess parity check
        proc = subprocess.run(
            [sys.executable, "-I", "-B", str(_THIS_DIR / "verify_s91_transhistorical_k26.py"), "--check", str(_THIS_DIR / "s91_transhistorical_k26_certificate.json")],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if _has_lean_436():
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("OK ", proc.stdout)
        else:
            self.assertEqual(proc.returncode, 2)
            self.assertIn("LEAN_BINARY_UNAVAILABLE", proc.stderr)


if __name__ == "__main__":
    unittest.main()
