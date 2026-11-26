#!/usr/bin/env python3
"""Adversarial Strict-I/O, Pure-Z/Q, Lean 4 Lexer & Live Kernel Test Suite.

Zero bare asserts, zero AST floats / float(), zero .isdigit(), zero islink/is_symlink,
zero character-device writes (scratch os.mkfifo only).
"""
from __future__ import annotations

import copy
import errno
from fractions import Fraction
import hashlib
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

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import two_way_transfer_audit as audit  # noqa: E402
import two_way_transfer_oracle as oracle  # noqa: E402

_TRACK_DIR = Path(__file__).resolve().parent
_CERT_PATH = _TRACK_DIR / "two_way_transfer_certificate.json"
_PROBE_PATH = _TRACK_DIR / "two_way_silicon_live_results.json"


class _IntSub(int):
    pass


class _StrSub(str):
    pass


class _DictSub(dict):
    pass


class _ListSub(list):
    pass


class _PathSub(type(Path())):
    pass


def _rehash_cert(payload: dict) -> dict:
    p_sha = hashlib.sha256(oracle.canonical_json_bytes(payload)).hexdigest()
    core = {
        "schema_version": audit.SCHEMA_VERSION,
        "study_id": audit.STUDY_ID,
        "payload_sha256": p_sha,
        "payload": payload,
    }
    c_sha = hashlib.sha256(oracle.canonical_json_bytes(core)).hexdigest()
    return {
        "schema_version": audit.SCHEMA_VERSION,
        "study_id": audit.STUDY_ID,
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "payload": payload,
    }


def _load_disk_cert() -> dict:
    raw = audit.read_regular_bytes_capped(_CERT_PATH, "disk_cert")
    return oracle.parse_strict_json_text(raw.decode("utf-8"), require_object=True)


def _load_disk_probe() -> dict:
    raw = audit.read_regular_bytes_capped(_PROBE_PATH, "disk_probe")
    return oracle.parse_strict_json_text(raw.decode("utf-8"), require_object=True)


class TestTwoWayTransferR5(unittest.TestCase):
    """Fast deterministic & adversarial tests (01-12) first; live Lean 4.36.0 last (90-95)."""

    def _assert_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.TwoWayTransferError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    # ------------------------------------------------------------------
    # 01-03: Exact Type, Integer, Rational & Strict JSON Primitives
    # ------------------------------------------------------------------

    def test_01_require_primitives_and_boundaries(self) -> None:
        oracle.require_ok(True, "X", "ok")
        self._assert_err("INVALID_CONDITION_TYPE", oracle.require_ok, 1, "X", "bad")
        self._assert_err("TEST_FAIL", oracle.require_ok, False, "TEST_FAIL", "fail")

        self.assertIs(oracle.require_exact_bool(True, "b"), True)
        self.assertIs(oracle.require_exact_bool(False, "b"), False)
        self._assert_err("INVALID_BOOL_TYPE", oracle.require_exact_bool, 1, "b")

        max_ok = (1 << oracle.MAX_INT_BITS) - 1
        self.assertEqual(oracle.require_exact_int(max_ok, "i"), max_ok)
        self.assertEqual(oracle.require_exact_int(-max_ok, "i"), -max_ok)
        self._assert_err("INT_BIT_LIMIT", oracle.require_exact_int, 1 << oracle.MAX_INT_BITS, "i")
        self._assert_err("INVALID_INT_TYPE", oracle.require_exact_int, True, "i")
        self._assert_err("INVALID_INT_TYPE", oracle.require_exact_int, _IntSub(5), "i")

        self.assertEqual(oracle.require_exact_int(10, "i", lo=10, hi=10), 10)
        self._assert_err("INT_OUT_OF_RANGE", oracle.require_exact_int, 9, "i", lo=10)
        self._assert_err("INT_OUT_OF_RANGE", oracle.require_exact_int, 11, "i", hi=10)
        self._assert_err("INVALID_BOUND_TYPE", oracle.require_exact_int, 10, "i", lo=True)
        self._assert_err("INVALID_BOUND_TYPE", oracle.require_exact_int, 10, "i", hi=True)

        self.assertEqual(oracle.require_exact_str("", "s", non_empty=False), "")
        self.assertEqual(oracle.require_exact_str("abc", "s", max_len=3), "abc")
        self._assert_err("INVALID_STR", oracle.require_exact_str, _StrSub("a"), "s")
        self._assert_err("NUL_BYTE_FORBIDDEN", oracle.require_exact_str, "a\x00b", "s")
        self._assert_err("EMPTY_STR", oracle.require_exact_str, "", "s")
        self._assert_err("STR_TOO_LONG", oracle.require_exact_str, "abcd", "s", max_len=3)
        self._assert_err("INVALID_UTF8_SURROGATE", oracle.require_exact_str, "\ud800", "s")

        good_sha = "0123456789abcdef" * 4
        self.assertEqual(oracle.require_sha256_hex(good_sha, "h"), good_sha)
        self._assert_err("INVALID_SHA256", oracle.require_sha256_hex, good_sha[:-1], "h")
        self._assert_err("INVALID_SHA256", oracle.require_sha256_hex, "A" * 64, "h")
        self._assert_err("INVALID_SHA256", oracle.require_sha256_hex, "g" * 64, "h")

        good_h16 = "0123456789abcdef"
        self.assertEqual(oracle.require_hex16(good_h16, "h16"), good_h16)
        self._assert_err("INVALID_HEX16", oracle.require_hex16, good_h16[:-1], "h16")
        self._assert_err("INVALID_HEX16", oracle.require_hex16, "A" * 16, "h16")
        self._assert_err("INVALID_HEX16", oracle.require_hex16, "z" * 16, "h16")

    def test_02_ascii_int_rational_and_json_tree(self) -> None:
        self.assertEqual(oracle.parse_exact_int_ascii("0", "n"), 0)
        self.assertEqual(oracle.parse_exact_int_ascii("-42", "n"), -42)
        self.assertEqual(oracle.parse_exact_int_ascii("9" * 100, "n"), int("9" * 100))
        exact_max_dig = "1" + ("0" * (oracle.MAX_INT_DIGITS - 1))
        self.assertEqual(oracle.parse_exact_int_ascii(exact_max_dig, "n"), 10 ** (oracle.MAX_INT_DIGITS - 1))
        self._assert_err("INVALID_INT_ASCII", oracle.parse_exact_int_ascii, "-", "n")
        self._assert_err("INVALID_INT_ASCII", oracle.parse_exact_int_ascii, "+5", "n")
        self._assert_err("INVALID_INT_ASCII", oracle.parse_exact_int_ascii, "\u0665", "n")
        self._assert_err("LEADING_ZERO_FORBIDDEN", oracle.parse_exact_int_ascii, "01", "n")
        self._assert_err("NEG_ZERO_FORBIDDEN", oracle.parse_exact_int_ascii, "-0", "n")
        self._assert_err("INT_DIGIT_LIMIT", oracle.parse_exact_int_ascii, "1" * (oracle.MAX_INT_DIGITS + 1), "n")
        self._assert_err("INT_BIT_LIMIT", oracle.parse_exact_int_ascii, str(1 << oracle.MAX_INT_BITS), "n")

        self.assertEqual(oracle.format_exact_rational(Fraction(7, 1)), "7")
        self.assertEqual(oracle.format_exact_rational(Fraction(-5, 6)), "-5/6")
        self._assert_err("INVALID_FRACTION_TYPE", oracle.format_exact_rational, 5)
        self._assert_err("INT_BIT_LIMIT", oracle.format_exact_rational, Fraction(1 << oracle.MAX_INT_BITS, 1))
        self._assert_err("INT_BIT_LIMIT", oracle.format_exact_rational, Fraction(1, 1 << oracle.MAX_INT_BITS))

        self.assertEqual(oracle.parse_exact_rational("7", "q"), Fraction(7, 1))
        self.assertEqual(oracle.parse_exact_rational("1/2", "q"), Fraction(1, 2))
        self.assertEqual(oracle.parse_exact_rational("-5/6", "q"), Fraction(-5, 6))
        self._assert_err("INVALID_RATIONAL", oracle.parse_exact_rational, "1/2/3", "q")
        self._assert_err("NON_CANONICAL_RATIONAL", oracle.parse_exact_rational, "3/1", "q")
        self._assert_err("NON_CANONICAL_RATIONAL", oracle.parse_exact_rational, "3/0", "q")
        self._assert_err("NON_REDUCED_RATIONAL", oracle.parse_exact_rational, "2/4", "q")
        self._assert_err("NON_REDUCED_RATIONAL", oracle.parse_exact_rational, "-4/6", "q")

        self.assertEqual(oracle.parse_strict_json_text('{"a": 1, "b": [true, null, "x"]}'), {"a": 1, "b": [True, None, "x"]})
        self.assertEqual(oracle.parse_strict_json_text("[1, 2]", require_object=False), [1, 2])
        self._assert_err("JSON_OBJECT_REQUIRED", oracle.parse_strict_json_text, "[1, 2]", require_object=True)
        self._assert_err("FLOAT_FORBIDDEN", oracle.parse_strict_json_text, '{"x": 1.5}')
        self._assert_err("FLOAT_FORBIDDEN", oracle.parse_strict_json_text, '{"x": 1e5}')
        self._assert_err("JSON_CONST_FORBIDDEN", oracle.parse_strict_json_text, '{"x": NaN}')
        self._assert_err("JSON_CONST_FORBIDDEN", oracle.parse_strict_json_text, '{"x": Infinity}')
        self._assert_err("DUPLICATE_JSON_KEY", oracle.parse_strict_json_text, '{"a": 1, "a": 2}')
        self._assert_err("JSON_PARSE_ERROR", oracle.parse_strict_json_text, "{bad")
        self._assert_err("JSON_DEPTH_LIMIT", oracle.parse_strict_json_text, "[" * 100 + "]" * 100)
        with mock.patch.object(oracle.json, "loads", side_effect=RecursionError("deep")):
            self._assert_err("JSON_DEPTH_LIMIT", oracle.parse_strict_json_text, "{}")

        ok_nested: list = []
        cur = ok_nested
        for _ in range(oracle.MAX_JSON_DEPTH):
            nxt: list = []
            cur.append(nxt)
            cur = nxt
        oracle.validate_json_tree(ok_nested)
        cur.append([])
        self._assert_err("JSON_DEPTH_LIMIT", oracle.validate_json_tree, ok_nested)

        oracle.validate_json_tree([0] * (oracle.MAX_JSON_NODES - 1))
        self._assert_err("JSON_NODE_LIMIT", oracle.validate_json_tree, [0] * oracle.MAX_JSON_NODES)

        runtime_float = json.loads("1.25")
        self._assert_err("FLOAT_FORBIDDEN", oracle.canonical_json_bytes, {"x": runtime_float})
        self._assert_err("INVALID_JSON_TYPE", oracle.canonical_json_bytes, _DictSub({"a": 1}))
        self._assert_err("INVALID_JSON_TYPE", oracle.canonical_json_bytes, {"a": _ListSub([1])})
        self._assert_err("INVALID_JSON_TYPE", oracle.canonical_json_bytes, {"a": _IntSub(1)})
        self._assert_err("INVALID_JSON_TYPE", oracle.canonical_json_bytes, {"a": _StrSub("x")})
        self._assert_err("INVALID_JSON_TYPE", oracle.canonical_json_bytes, {"a": (1, 2)})
        self._assert_err("INVALID_STR", oracle.canonical_json_bytes, {1: "a"})

    # ------------------------------------------------------------------
    # 04-05: Strict-I/O Security, OSError Handlers, Darwin Prefix & $PWD
    # ------------------------------------------------------------------

    def test_04_strict_io_symlinks_hardlinks_fifo_and_oserror_handlers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            self._assert_err("INVALID_PATH_TYPE", audit.read_regular_bytes_capped, str(base / "a"))
            self._assert_err("INVALID_PATH_TYPE", audit.read_regular_bytes_capped, _PathSub(base / "a"))
            self._assert_err("INVALID_LEAF_NAME", audit.read_regular_bytes_capped, Path("/"))
            self._assert_err("INVALID_LEAF_NAME", audit.read_regular_bytes_capped, base / "..")
            self._assert_err("INVALID_LEAF_NAME", audit.read_regular_bytes_capped, base / ".." / "x")
            self._assert_err("FILE_READ_ERROR", audit.read_regular_bytes_capped, Path("/no_such_root_file_xyz"))

            nested = base / "sub1" / "sub2" / "cert.json"
            payload_b = b'{"ok":true}\n'
            audit.write_regular_bytes_safe(nested, payload_b)
            self.assertEqual(stat.S_IMODE(os.lstat(nested).st_mode), 0o600)
            self.assertEqual(audit.read_regular_bytes_capped(nested, max_bytes=len(payload_b)), payload_b)
            self._assert_err("FILE_TOO_LARGE", audit.read_regular_bytes_capped, nested, max_bytes=len(payload_b) - 1)
            self._assert_err("INT_OUT_OF_RANGE", audit.read_regular_bytes_capped, nested, max_bytes=0)
            self._assert_err("INT_OUT_OF_RANGE", audit.read_regular_bytes_capped, nested, max_bytes=audit.MAX_ALLOWED_CAP_BYTES + 1)
            self._assert_err("INVALID_PAYLOAD_BYTES", audit.write_regular_bytes_safe, nested, "not-bytes")

            big = b"A" * 70_000
            audit.write_regular_bytes_safe(nested, big)
            self.assertEqual(audit.read_regular_bytes_capped(nested, max_bytes=70_000), big)

            self._assert_err("FILE_READ_ERROR", audit.read_regular_bytes_capped, base / "missing.json")
            self._assert_err("FILE_READ_ERROR", audit.read_regular_bytes_capped, base / "no_dir" / "missing.json")
            self.assertFalse((base / "no_dir").exists())

            d_target = base / "adir"
            d_target.mkdir()
            self._assert_err("NOT_A_REGULAR_FILE", audit.read_regular_bytes_capped, d_target)
            self._assert_err("NOT_A_REGULAR_FILE", audit.write_regular_bytes_safe, d_target, b"x")

            self._assert_err("SYMLINK_FORBIDDEN", audit.read_regular_bytes_capped, nested / "child")
            self._assert_err("SYMLINK_FORBIDDEN", audit.write_regular_bytes_safe, nested / "child", b"x")

            sym_leaf = base / "sym_leaf"
            os.symlink(nested, sym_leaf)
            self._assert_err("SYMLINK_FORBIDDEN", audit.read_regular_bytes_capped, sym_leaf)
            self._assert_err("SYMLINK_FORBIDDEN", audit.write_regular_bytes_safe, sym_leaf, b"x")

            sym_dir = base / "sym_dir"
            os.symlink(d_target, sym_dir)
            self._assert_err("SYMLINK_FORBIDDEN", audit.read_regular_bytes_capped, sym_dir / "f")
            self._assert_err("SYMLINK_FORBIDDEN", audit.write_regular_bytes_safe, sym_dir / "f", b"x")

            # Hardlink rejected on BOTH read and write (pre-lstat before temp creation)
            hl_target = base / "hl_target"
            os.link(nested, hl_target)
            self._assert_err("HARDLINK_FORBIDDEN", audit.read_regular_bytes_capped, hl_target)
            with mock.patch.object(audit.os, "urandom", side_effect=RuntimeError("temp_opened_early")):
                self._assert_err("HARDLINK_FORBIDDEN", audit.write_regular_bytes_safe, hl_target, b"x")
            os.unlink(hl_target)

            # Read-only directory write -> FILE_WRITE_ERROR (verify exact create temp failed path)
            ro_dir = base / "ro_dir"
            ro_dir.mkdir(mode=0o500)
            try:
                self._assert_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, ro_dir / "newsub" / "f.json", b"x")
                with self.assertRaises(oracle.TwoWayTransferError) as ctx_ro:
                    audit.write_regular_bytes_safe(ro_dir / "f.json", b"x")
                self.assertEqual(ctx_ro.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("create temp failed", str(ctx_ro.exception))
            finally:
                os.chmod(ro_dir, 0o700)

            # Kill all guard_except_reject OSError handlers cleanly
            with mock.patch.object(audit.os, "mkdir", side_effect=PermissionError("mk")):
                with self.assertRaises(oracle.TwoWayTransferError) as ctx_mk:
                    audit.write_regular_bytes_safe(base / "new_mk_fail" / "f", b"x")
                self.assertEqual(ctx_mk.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("mkdir failed", str(ctx_mk.exception))

            real_open = os.open
            open_calls = {"n": 0}
            def _open_fail_after_mkdir(p, flags, mode=0o777, *, dir_fd=None):
                if p == "reopen_fail":
                    open_calls["n"] += 1
                    if open_calls["n"] == 1:
                        raise FileNotFoundError(errno.ENOENT, "noent", p)
                    raise PermissionError("reopen")
                return real_open(p, flags, mode, dir_fd=dir_fd) if dir_fd is not None else real_open(p, flags, mode)

            with mock.patch.object(audit.os, "open", side_effect=_open_fail_after_mkdir):
                self._assert_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, base / "reopen_fail" / "f", b"x")

            with mock.patch.object(audit.os, "read", side_effect=OSError("eio")):
                self._assert_err("FILE_READ_ERROR", audit.read_regular_bytes_capped, nested)

            with mock.patch.object(audit.os, "lstat", side_effect=PermissionError("lstat1")):
                self._assert_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, base / "ls1.json", b"x")

            with mock.patch.object(audit.os, "write", side_effect=OSError("enospc")):
                self._assert_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, base / "wfail.json", b"x")

            with mock.patch.object(audit.os, "replace", side_effect=OSError("exdev")):
                self._assert_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, base / "rfail.json", b"x")

            # Temp-slot FileExistsError retry & exhaustion
            def _open_eexist(p, flags, mode=0o777, *, dir_fd=None):
                if isinstance(p, str) and p.startswith(".twt."):
                    raise FileExistsError(p)
                return real_open(p, flags, mode, dir_fd=dir_fd) if dir_fd is not None else real_open(p, flags, mode)

            with mock.patch.object(audit.os, "open", side_effect=_open_eexist):
                self._assert_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, base / "exh.json", b"x")

            # Post-lstat OSError & race checks (symlink, non-regular, hardlink, temp fstat hardlink)
            race_target = base / "race.json"
            real_fstat = os.fstat
            with mock.patch.object(
                audit.os, "fstat",
                side_effect=lambda fd: mock.Mock(st_mode=real_fstat(fd).st_mode, st_nlink=2),
            ):
                self._assert_err("HARDLINK_FORBIDDEN", audit.write_regular_bytes_safe, race_target, b"x")

            for st_mode_race, nlink_race, exp_code in (
                (stat.S_IFLNK | 0o777, 1, "SYMLINK_FORBIDDEN"),
                (stat.S_IFDIR | 0o755, 2, "NOT_A_REGULAR_FILE"),
                (stat.S_IFREG | 0o600, 2, "HARDLINK_FORBIDDEN"),
            ):
                cn = {"n": 0}
                def _lstat_race(name, dir_fd=None, *, _m=st_mode_race, _nl=nlink_race, _c=cn):
                    _c["n"] += 1
                    if _c["n"] == 1:
                        raise FileNotFoundError(name)
                    return mock.Mock(st_mode=_m, st_nlink=_nl)
                with mock.patch.object(audit.os, "lstat", side_effect=_lstat_race):
                    self._assert_err(exp_code, audit.write_regular_bytes_safe, race_target, b"x")

            cn2 = {"n": 0}
            def _lstat2_err(name, dir_fd=None):
                cn2["n"] += 1
                if cn2["n"] == 1:
                    raise FileNotFoundError(name)
                raise PermissionError("lstat2")
            with mock.patch.object(audit.os, "lstat", side_effect=_lstat2_err):
                self._assert_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, race_target, b"x")

            if hasattr(os, "mkfifo"):
                fifo_p = base / "scratch.fifo"
                os.mkfifo(fifo_p, 0o600)
                self._assert_err("NOT_A_REGULAR_FILE", audit.read_regular_bytes_capped, fifo_p)
                self._assert_err("NOT_A_REGULAR_FILE", audit.write_regular_bytes_safe, fifo_p, b"x")

    def test_05_relative_pwd_darwin_prefix_and_concurrency(self) -> None:
        st_lnk_root = mock.Mock(st_mode=stat.S_IFLNK | 0o777, st_uid=0)
        st_lnk_user = mock.Mock(st_mode=stat.S_IFLNK | 0o777, st_uid=501)
        st_dir_root = mock.Mock(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
        st_dir_user = mock.Mock(st_mode=stat.S_IFDIR | 0o755, st_uid=501)
        st_reg_root = mock.Mock(st_mode=stat.S_IFREG | 0o644, st_uid=0)

        with mock.patch.object(audit.sys, "platform", "linux"):
            with mock.patch.object(audit.os, "lstat", side_effect=[st_lnk_root, st_dir_root]):
                with mock.patch.object(audit.os, "readlink", return_value="private/var"):
                    self.assertEqual(audit._normalize_darwin_system_prefix(("var", "f")), ("var", "f"))

        with mock.patch.object(audit.sys, "platform", "darwin"):
            with mock.patch.object(audit.os, "lstat", side_effect=[st_lnk_root, st_dir_root]):
                with mock.patch.object(audit.os, "readlink", return_value="private/var"):
                    self.assertEqual(audit._normalize_darwin_system_prefix(("var",)), ("var",))
            with mock.patch.object(audit.os, "lstat", side_effect=[st_lnk_root, st_dir_root]):
                with mock.patch.object(audit.os, "readlink", return_value="private/usr"):
                    self.assertEqual(audit._normalize_darwin_system_prefix(("usr", "bin")), ("usr", "bin"))
            with mock.patch.object(audit.os, "lstat", side_effect=[st_lnk_root, st_dir_root]):
                with mock.patch.object(audit.os, "readlink", return_value="private/var"):
                    self.assertEqual(audit._normalize_darwin_system_prefix(("var", "f")), ("private", "var", "f"))
            for lstats, tgt in (
                ([st_dir_root, st_dir_root], "private/tmp"),
                ([st_lnk_user, st_dir_root], "private/tmp"),
                ([st_lnk_root, st_dir_root], "evil/tmp"),
                ([st_lnk_root, st_reg_root], "private/tmp"),
                ([st_lnk_root, st_dir_user], "private/tmp"),
            ):
                with mock.patch.object(audit.os, "lstat", side_effect=lstats):
                    with mock.patch.object(audit.os, "readlink", return_value=tgt):
                        self.assertEqual(audit._normalize_darwin_system_prefix(("tmp", "a")), ("tmp", "a"))
            with mock.patch.object(audit.os, "lstat", side_effect=OSError("no")):
                self.assertEqual(audit._normalize_darwin_system_prefix(("var", "a")), ("var", "a"))

        orig_cwd = os.getcwd()
        orig_pwd = os.environ.get("PWD")
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            real_sub = base / "real_sub"
            real_sub.mkdir()
            sym_sub = base / "sym_sub"
            os.symlink(real_sub, sym_sub)
            try:
                os.chdir(real_sub)
                os.environ["PWD"] = str(real_sub)
                rel = Path(".") / "rel_out.json"
                audit.write_regular_bytes_safe(rel, b'{"rel":1}\n')
                self.assertEqual(audit.read_regular_bytes_capped(rel), b'{"rel":1}\n')

                os.environ["PWD"] = str(sym_sub)
                self._assert_err("SYMLINK_ANCESTOR_FORBIDDEN", audit.read_regular_bytes_capped, Path("rel_out.json"))

                os.environ["PWD"] = str(base / "no_such_pwd")
                self.assertEqual(audit.read_regular_bytes_capped(Path("rel_out.json")), b'{"rel":1}\n')
                other_dir = base / "other_sub"
                other_dir.mkdir()
                os.environ["PWD"] = str(other_dir)
                self.assertEqual(audit.read_regular_bytes_capped(Path("rel_out.json")), b'{"rel":1}\n')
                os.environ["PWD"] = "relative/pwd"
                self.assertEqual(audit.read_regular_bytes_capped(Path("rel_out.json")), b'{"rel":1}\n')
                with mock.patch.object(audit.os, "environ", {"PWD": "/tmp/\ud800"}):
                    self._assert_err("INVALID_UTF8_SURROGATE", audit.read_regular_bytes_capped, Path("rel_out.json"))
                with mock.patch.object(audit.os, "environ", {"PWD": "/tmp/a\x00b"}):
                    self._assert_err("NUL_BYTE_FORBIDDEN", audit.read_regular_bytes_capped, Path("rel_out.json"))

                del_dir = base / "ephemeral"
                del_dir.mkdir()
                os.chdir(del_dir)
                os.environ["PWD"] = str(del_dir)
                del_dir.rmdir()
                self._assert_err("CWD_UNAVAILABLE", audit.read_regular_bytes_capped, Path("any.json"))
            finally:
                os.chdir(orig_cwd)
                if orig_pwd is None:
                    os.environ.pop("PWD", None)
                else:
                    os.environ["PWD"] = orig_pwd

            conc_path = base / "concurrent.json"
            errors: list[BaseException] = []

            def _worker(tid: int) -> None:
                try:
                    for step in range(4):
                        audit.write_regular_bytes_safe(conc_path, f'{{"t":{tid},"s":{step}}}\n'.encode("utf-8"))
                except BaseException as exc:  # pragma: no cover
                    errors.append(exc)

            threads = [threading.Thread(target=_worker, args=(i,)) for i in range(12)]
            for th in threads:
                th.start()
            for th in threads:
                th.join()
            self.assertEqual(errors, [])
            self.assertEqual([p.name for p in base.iterdir() if p.name.endswith(".tmp")], [])

    # ------------------------------------------------------------------
    # 06-08: Hardened Lean 4 Lexer (Char/Raw/Interp/Decide), Axioms & Binary
    # ------------------------------------------------------------------

    def test_06_lean4_static_lexer_and_all_escapes(self) -> None:
        clean_src = (
            "/- a - sorry / axiom /- nested sorry -/ still - comment -/\n"
            "-- line comment sorry admit unsafe\n"
            "def div_op : Nat := 4 / 2\n"
            "def s : String := \"sorry \\\"admit\\\"\\n\"\n"
            "def q : Char := '\"'\n"
            "def q2 : Char := '\\''\n"
            "def q3 : Char := '\\\"'\n"
            "def q4 : Char := '\\\\'\n"
            "def r1 : String := r\"sorry \\\"\n"
            "def r2 : String := r#\"sorry \"#\"#\n"
            "def si : String := s!\"ok {(1 + 2)} \\\"end\\\"\"\n"
            "def ss_plain : String := ss\"{sorry}\"\n"
            "def s_bang := s! x\n"
            "def x_bang : String := x!\"{sorry}\"\n"
            "def xs_bang : String := xs!\"{sorry}\"\n"
            "def us_bang : String := _s!\"{sorry}\"\n"
            "def x' : Nat := 1\n"
            "def y' : Nat := x' + 1\n"
            "def ri : Nat := r_id\n"
            "def fn : String := foo!\"sorry\"\n"
            "import Init.Data.Nat.Basic\n"
            "import Std\n"
            "def f0 := ) + 1\n"
            "def safeCfg : DecideConfig := { native := false }\n"
            "def safeCfg2 := ({ native := (Bool.false) } : DecideConfig)\n"
            "theorem t0 : 2 - 1 = 1 := by decide +revert (native := ( false )) (config := (({ native := false, revert := true })))\n"
            "theorem t_c1 : 1 = 1 := by decide (config := { native := false })\n"
            "theorem t0b : 1 = 1 := by decide (config := {})\n"
            "theorem t1 : 1 = 1 := by decide\n"
            "def f1 := decide (foo) + 1\n"
            "def f2 := decide +\n"
            "def f3 := decide (unclosed\n"
            "def g_interp : String := s!\"a {{1}} b\"\n"
            "-- trailing eof comment"
        )
        oracle.static_lean4_source_check(clean_src, "clean")
        oracle.static_lean4_source_check("r", "eof_r")
        oracle.static_lean4_source_check("r#", "eof_rh")
        oracle.static_lean4_source_check("x'", "eof_p1")
        oracle.static_lean4_source_check("x'\\", "eof_p2")
        oracle.static_lean4_source_check('!"{sorry}" -- s', "bang_at_0")
        oracle.static_lean4_source_check('def x\'"sorry"', "prime_before_str")
        oracle.static_lean4_source_check('x\'\\"sorry"', "prime_bs_before_str")

        # Direct span-helper edge tests
        self.assertIs(oracle._is_lean4_native_rhs_false_span("   ", 0, 3), False)
        self.assertIs(oracle._is_lean4_native_rhs_false_span("", 0, 0), False)
        self.assertIs(oracle._is_lean4_native_rhs_false_span("((false))", 0, 9), True)
        self.assertIs(oracle._is_lean4_native_rhs_false_span("(a)", 0, 3), False)
        self.assertIs(oracle._is_lean4_native_rhs_false_span("(falsex", 0, 7), False)
        self.assertIs(oracle._is_lean4_native_rhs_false_span("xfalse)", 0, 7), False)
        self.assertIs(oracle._is_lean4_safe_config_span("   ", 0, 3, {}), False)
        self.assertIs(oracle._is_lean4_safe_config_span("{a", 0, 2, {}), False)
        self.assertIs(oracle._is_lean4_safe_config_span("a}", 0, 2, {}), False)
        self.assertIs(oracle._is_lean4_safe_config_span("abc", 0, 3, {}), False)
        self.assertIs(oracle._is_lean4_safe_config_span("{ native := false }", 0, 19, {}), True)

        self._assert_err("LEAN4_UNTERMINATED_COMMENT", oracle.static_lean4_source_check, "/- unclosed", "u1")
        self._assert_err("LEAN4_UNTERMINATED_STRING", oracle.static_lean4_source_check, 'def x := "unclosed', "u2")
        self._assert_err("LEAN4_UNTERMINATED_STRING", oracle.static_lean4_source_check, 'def x := "abc\\', "u2b")
        self._assert_err("LEAN4_UNTERMINATED_STRING", oracle.static_lean4_source_check, 'def x := s!"abc\\', "u2c")
        self._assert_err("LEAN4_UNTERMINATED_STRING", oracle.static_lean4_source_check, 'def x := r"unclosed', "u3")
        self._assert_err("LEAN4_UNTERMINATED_STRING", oracle.static_lean4_source_check, 'def x := s!"unclosed', "u4")
        self._assert_err("LEAN4_UNTERMINATED_STRING", oracle.static_lean4_source_check, 'def x := s!"{1', "u5")
        self._assert_err("LEAN4_UNTERMINATED_STRING", oracle.static_lean4_source_check, 'def a := xr"\\"', "raw_alnum")
        self._assert_err("LEAN4_UNTERMINATED_STRING", oracle.static_lean4_source_check, 'def a := _r"\\"', "raw_extra")

        forbidden_cases = [
            ("theorem t : False := by sorry", "LEAN4_SORRY"),
            ("theorem t : 4 / 2 = 2 := by sorry\n", "LEAN4_SORRY"),
            ("theorem t : 2 - 1 = 1 := by sorry\n", "LEAN4_SORRY"),
            ("-- ok\ntheorem t : False := by sorry\n", "LEAN4_SORRY"),
            ("theorem t : False := by admit", "LEAN4_ADMIT"),
            ("axiom bogus : False", "LEAN4_AXIOM"),
            ("unsafe def bad : Nat := 0", "LEAN4_UNSAFE"),
            ("theorem t : 1 = 1 := by native_decide", "LEAN4_NATIVE_DECIDE"),
            ("def x := sorryAx", "LEAN4_SORRY_AX"),
            ("def x := Lean.Meta.mkSorry", "LEAN4_MK_SORRY"),
            ("def x := Lean.ofReduceBool", "LEAN4_OF_REDUCE_BOOL"),
            ("def x := Lean.ofReduceNat", "LEAN4_OF_REDUCE_NAT"),
            ("def x := Lean.trustCompiler", "LEAN4_TRUST_COMPILER"),
            # Char-literal, Raw-string, and Interpolated-string bypass probes
            ("def q1 : Char := '\"'\ntheorem evil : False := by sorry\ndef q2 : Char := '\"'\n", "LEAN4_SORRY"),
            ("def q1 : Char := '\\\"'\ntheorem evil : False := by sorry\ndef q2 : Char := '\\\"'\n", "LEAN4_SORRY"),
            ("def q1 : Char := '\\''\ntheorem evil : False := by sorry\n", "LEAN4_SORRY"),
            ("'\\''\"'\" sorry", "LEAN4_SORRY"),
            ("x'\"y'\" sorry", "LEAN4_SORRY"),
            ("def q1 : Char := '\"'\nset_option debug.skipKernelTC true\ndef q2 : Char := '\"'\n", "LEAN4_SKIP_KERNEL_TC"),
            ('r"\\"\ntheorem evil : False := by sorry\n-- " x', "LEAN4_SORRY"),
            ('def r1 : String := r"\\"\ntheorem evil : False := by sorry\n-- "\n', "LEAN4_SORRY"),
            ('def r1 : String := r#"\\"#\ntheorem evil : False := by sorry\n-- "\n', "LEAN4_SORRY"),
            ('s!"{ (by sorry : Nat) }" -- x', "LEAN4_SORRY"),
            ('def s : String := s!"{ (by sorry : Nat) }"\n', "LEAN4_SORRY"),
            ('def s : String := s!"{ (by decide +native : 1 = 1) }"\n', "LEAN4_DECIDE_NATIVE"),
            # All 12 decide native-evaluation escapes
            ("theorem t : 1 = 1 := by decide +native", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide +revert +native", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native := true })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native := false :+ true })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native := false ,+ true })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide +«native»", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide («native» := true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { «native» := true })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide («config» := { native := true })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := ⟨false, true, false, false⟩)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := .mk false true false false)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := c)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { c0 with native := false })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { a := { })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { a := } })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := ({}) + ({}))", "LEAN4_DECIDE_NATIVE"),
            ("def cfg : DecideConfig := { native := true }", "LEAN4_DECIDE_NATIVE"),
            ("def cfg := { native := true } : Decide.Config", "LEAN4_DECIDE_NATIVE"),
            ("def cfg := { native := true : DecideConfig }", "LEAN4_DECIDE_NATIVE"),
            ("set_option debug.skipKernelTC true", "LEAN4_SKIP_KERNEL_TC"),
            ('@[extern "c_fn"] def f : Nat := 0', "LEAN4_ATTR_ESCAPE"),
            ("@[implemented_by g] def f : Nat := 0", "LEAN4_ATTR_ESCAPE"),
            ("partial def loop : Nat := loop", "LEAN4_PARTIAL"),
            ("import Mathlib.Data.Nat.Basic", "LEAN4_NON_INIT_IMPORT"),
            ("public import External.Pkg", "LEAN4_NON_INIT_IMPORT"),
        ]
        for bad_src, exp_code in forbidden_cases:
            self._assert_err(exp_code, oracle.static_lean4_source_check, bad_src, exp_code)

    def test_07_print_axioms_and_lean_binary_resolution(self) -> None:
        good_out = (
            "\n"
            "'A.t1' does not depend on any axioms\n"
            "'A.t2' depends on axioms: [propext, Quot.sound]\n"
            "'A.t3' depends on axioms: [propext,\n"
            " Classical.choice,\n"
            " Quot.sound]\n"
        )
        parsed = audit.parse_print_axioms_output(good_out, ("A.t1", "A.t2", "A.t3"))
        self.assertEqual(parsed["A.t1"], [])
        self.assertEqual(parsed["A.t2"], ["propext", "Quot.sound"])
        self.assertEqual(parsed["A.t3"], ["propext", "Classical.choice", "Quot.sound"])

        self._assert_err("MALFORMED_AXIOM_OUTPUT", audit.parse_print_axioms_output, "'A.t1' depends on axioms: [propext\n", ("A.t1",))
        self._assert_err("UNEXPECTED_LEAN_STDOUT", audit.parse_print_axioms_output, "noise depends on axioms: [propext", ("A.t1",))
        self._assert_err("UNEXPECTED_LEAN_STDOUT", audit.parse_print_axioms_output, "random line", ("A.t1",))
        self._assert_err("EMPTY_AXIOM_BRACKETS", audit.parse_print_axioms_output, "'A.t1' depends on axioms: []", ("A.t1",))
        self._assert_err("FORBIDDEN_LEAN_AXIOM", audit.parse_print_axioms_output, "'A.t1' depends on axioms: [x]", ("A.t1",))
        self._assert_err("MALFORMED_AXIOM_TOKEN", audit.parse_print_axioms_output, "'A.t1' depends on axioms: [propext, ]", ("A.t1",))
        self._assert_err("UNEXPECTED_THEOREM_NAME", audit.parse_print_axioms_output, "'A.other' does not depend on any axioms", ("A.t1",))
        self._assert_err("DUPLICATE_THEOREM_PRINT", audit.parse_print_axioms_output, "'A.t1' does not depend on any axioms\n'A.t1' does not depend on any axioms", ("A.t1",))
        self._assert_err("FORBIDDEN_LEAN_AXIOM", audit.parse_print_axioms_output, "'A.t1' depends on axioms: [sorryAx]", ("A.t1",))
        self._assert_err("MISSING_THEOREM_PRINT", audit.parse_print_axioms_output, "'A.t1' does not depend on any axioms", ("A.t1", "A.t2"))

        with tempfile.TemporaryDirectory() as td:
            missing = str(Path(td) / "no_lean")
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": missing}):
                self._assert_err("LEAN_BINARY_UNAVAILABLE", audit.resolve_lean_binary)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": td}):
                self._assert_err("LEAN_BINARY_UNAVAILABLE", audit.resolve_lean_binary)
            non_exec = Path(td) / "non_exec_lean"
            audit.write_regular_bytes_safe(non_exec, b"#!/bin/sh\n")
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(non_exec)}):
                self._assert_err("LEAN_BINARY_UNAVAILABLE", audit.resolve_lean_binary)
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("ALETHEIA_LEAN_BIN", None)
                with mock.patch.object(audit.shutil, "which", return_value=str(non_exec)):
                    with mock.patch.object(audit.Path, "home", return_value=Path(td)):
                        self._assert_err("LEAN_BINARY_UNAVAILABLE", audit.resolve_lean_binary)
                fake_home_dir = Path(td) / "fhd"
                (fake_home_dir / ".local" / "bin" / "lean").mkdir(parents=True)
                with mock.patch.object(audit.shutil, "which", return_value=None):
                    with mock.patch.object(audit.Path, "home", return_value=fake_home_dir):
                        self._assert_err("LEAN_BINARY_UNAVAILABLE", audit.resolve_lean_binary)
                fake_home = Path(td) / "fh"
                fake_lean = fake_home / ".local" / "bin" / "lean"
                audit.write_regular_bytes_safe(fake_lean, b"#!/bin/sh\n")
                with mock.patch.object(audit.shutil, "which", return_value=None):
                    with mock.patch.object(audit.Path, "home", return_value=fake_home):
                        self._assert_err("LEAN_BINARY_UNAVAILABLE", audit.resolve_lean_binary)
                os.chmod(fake_lean, 0o700)
                with mock.patch.object(audit.shutil, "which", return_value=None):
                    with mock.patch.object(audit.Path, "home", return_value=fake_home):
                        self.assertEqual(audit.resolve_lean_binary(), str(fake_lean))

            lean_bin = audit.resolve_lean_binary()
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": lean_bin}):
                self.assertEqual(audit.resolve_lean_binary(), lean_bin)

            self._assert_err("LEAN_EXEC_ERROR", audit.query_lean_version, missing)
            with mock.patch.object(audit.subprocess, "run", return_value=mock.Mock(returncode=1, stdout="", stderr="err")):
                self._assert_err("LEAN_VERSION_FAILED", audit.query_lean_version, lean_bin)
            with mock.patch.object(audit.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="Lean (version 4.10.0, x)\n", stderr="")):
                self._assert_err("LEAN_VERSION_MISMATCH", audit.query_lean_version, lean_bin)

            bad_tc_root = Path(td) / "bad_tc"
            audit.write_regular_bytes_safe(bad_tc_root / "lean-toolchain", b"\xff\xfe")
            with mock.patch.object(audit, "query_lean_version", return_value=audit.EXPECTED_LEAN_VERSION_LINE):
                self._assert_err("INVALID_UTF8_TOOLCHAIN", audit.build_certificate, bad_tc_root)
            audit.write_regular_bytes_safe(bad_tc_root / "lean-toolchain", b"leanprover/lean4:v4.0.0\n")
            with mock.patch.object(audit, "query_lean_version", return_value=audit.EXPECTED_LEAN_VERSION_LINE):
                self._assert_err("TOOLCHAIN_MISMATCH", audit.build_certificate, bad_tc_root)

    # ------------------------------------------------------------------
    # 08-10: Pillar 1 & 2 Exact Oracles, MLOS Receipt & Payload Tampering
    # ------------------------------------------------------------------

    def test_08_pillar1_and_pillar2_oracles_and_negative_controls(self) -> None:
        p1 = oracle.analyze_competing_potential_scale_flip()
        self.assertIs(p1["wikitext2_h16_sign_inversion"], True)
        self.assertIs(p1["python_h16_sign_inversion"], True)
        self.assertIs(p1["python_05b_strict_sub_barrier_band"], True)
        self.assertIs(p1["block_h2_beats_h16_all_scales"], True)

        # Negative Pillar 1 perturbation checks (kills every sub-condition in flip & sub-barrier flags)
        for mod_idx, split, key, val, flag_k in (
            (1, "python", "A16_BlockH2", 46_000_000, "python_05b_strict_sub_barrier_band"),
            (1, "python", "A16_H16", 45_000_000, "python_05b_strict_sub_barrier_band"),
            (1, "wikitext2", "A16_BlockH2", 50_000_000, "python_05b_strict_sub_barrier_band"),
            (0, "wikitext2", "A16_H16", 60_000_000, "wikitext2_h16_sign_inversion"),
            (1, "wikitext2", "A16_H16", 50_000_000, "wikitext2_h16_sign_inversion"),
            (2, "wikitext2", "A16_H16", 60_000_000, "wikitext2_h16_sign_inversion"),
            (0, "python", "A16_H16", 50_000_000, "python_h16_sign_inversion"),
            (1, "python", "A16_H16", 40_000_000, "python_h16_sign_inversion"),
            (2, "python", "A16_H16", 40_000_000, "python_h16_sign_inversion"),
        ):
            mod_e = copy.deepcopy(list(oracle.FROZEN_SCALE_KL_NANO))
            mod_e[mod_idx][split][key] = val
            out_m = oracle.analyze_competing_potential_scale_flip(mod_e)
            if mod_idx == 1 and split == "wikitext2" and key == "A16_BlockH2":
                # Changing wikitext2 0.5B must NOT affect python_05b_strict_sub_barrier_band
                self.assertIs(out_m[flag_k], True)
                mod_e[1]["python"]["A16_BlockH2"] = 46_000_000
                self.assertIs(oracle.analyze_competing_potential_scale_flip(mod_e)[flag_k], False)
            else:
                self.assertIs(out_m[flag_k], False)

        probe = _load_disk_probe()
        p2 = oracle.analyze_live_silicon_probe(probe)
        self.assertIs(p2["exp_a_checksum_conserved"], True)
        self.assertIs(p2["exp_b_checksum_conserved"], True)
        self.assertIs(p2["idle_baseline"]["psys_vendor_scale_obstruction_detected"], True)
        self.assertEqual(p2["exp_a_summary"]["best_overall_pkg_arm"], "race_to_sleep_free")
        self.assertEqual(p2["exp_a_summary"]["best_fixed_window_pkg_arm"], "bursty_1_pulse_1500ms")
        self.assertEqual(p2["exp_b_summary"]["optimal_pkg_threads"], 16)
        self.assertEqual(p2["exp_b_summary"]["best_physical_pkg_threads"], 8)

        def _bad_probe(mutator, code: str) -> None:
            pr = copy.deepcopy(probe)
            mutator(pr)
            self._assert_err(code, oracle.analyze_live_silicon_probe, pr)

        _bad_probe(lambda d: d.__setitem__("schema", "bad"), "PROBE_SCHEMA_MISMATCH")
        _bad_probe(lambda d: d.__setitem__("measured_live_silicon", False), "MEASURED_FLAG_FALSE")
        _bad_probe(lambda d: d.__setitem__("ops_per_block", 123), "OPS_PER_BLOCK_MISMATCH")
        _bad_probe(lambda d: d.__setitem__("exp_a_total_blocks", 801), "EXP_A_DIVISIBILITY")
        _bad_probe(lambda d: d.__setitem__("exp_a_total_ops", 1), "EXP_A_OPS_MISMATCH")
        _bad_probe(lambda d: d.__setitem__("exp_b_total_blocks", 481), "EXP_B_DIVISIBILITY")
        _bad_probe(lambda d: d.__setitem__("exp_b_total_ops", 1), "EXP_B_OPS_MISMATCH")
        _bad_probe(lambda d: d["exp_a_pacing_vs_bursty"].pop(), "EXP_A_LEN_MISMATCH")
        _bad_probe(lambda d: d.__setitem__("exp_a_pacing_vs_bursty", "12345"), "EXP_A_LEN_MISMATCH")
        _bad_probe(lambda d: d["exp_a_pacing_vs_bursty"][0].__setitem__("arm", "x"), "EXP_A_ARM_NAME")
        _bad_probe(lambda d: d["exp_a_pacing_vs_bursty"][0].__setitem__("slices", 9), "EXP_A_SLICES")
        _bad_probe(lambda d: d["exp_a_pacing_vs_bursty"][0].__setitem__("window_ms", 9), "EXP_A_WIN")
        _bad_probe(lambda d: d["exp_a_pacing_vs_bursty"][0]["trials"].pop(), "EXP_A_TRIALS_LEN")
        _bad_probe(lambda d: d["exp_a_pacing_vs_bursty"][0].__setitem__("trials", "12"), "EXP_A_TRIALS_LEN")
        _bad_probe(lambda d: d["exp_a_pacing_vs_bursty"][0]["trials"][0].__setitem__("checksum_hex", "0" * 16), "EXP_A_CHECKSUM_DRIFT")
        _bad_probe(lambda d: d["exp_b_concurrency_impedance"].pop(), "EXP_B_LEN_MISMATCH")
        _bad_probe(lambda d: d.__setitem__("exp_b_concurrency_impedance", "1234567"), "EXP_B_LEN_MISMATCH")
        _bad_probe(lambda d: d["exp_b_concurrency_impedance"][0].__setitem__("threads", 99), "EXP_B_THREADS")
        _bad_probe(lambda d: d["exp_b_concurrency_impedance"][0].__setitem__("physical_cores_used", 2), "EXP_B_PHYS")
        _bad_probe(lambda d: d["exp_b_concurrency_impedance"][0].__setitem__("smt_siblings_used", 1), "EXP_B_SMT")
        _bad_probe(lambda d: d["exp_b_concurrency_impedance"][0]["trials"].pop(), "EXP_B_TRIALS_LEN")
        _bad_probe(lambda d: d["exp_b_concurrency_impedance"][0].__setitem__("trials", "12"), "EXP_B_TRIALS_LEN")
        _bad_probe(lambda d: d["exp_b_concurrency_impedance"][0]["trials"][0].__setitem__("checksum_hex", "0" * 16), "EXP_B_CHECKSUM_DRIFT")

    def test_09_mlos_receipt_validation_negative_controls(self) -> None:
        raw_mlos = audit.read_regular_bytes_capped(_TRACK_DIR / "mlos_zone_b_receipt.json", "mlos")
        base_obj = json.loads(raw_mlos.decode("utf-8"))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rp = root / "mlos_zone_b_receipt.json"
            audit.write_regular_bytes_safe(rp, b"\xff\xfe")
            self._assert_err("INVALID_UTF8_RECEIPT", audit.load_hardware_provenance, root)
            audit.write_regular_bytes_safe(rp, b"{bad")
            self._assert_err("RECEIPT_JSON_ERROR", audit.load_hardware_provenance, root)
            audit.write_regular_bytes_safe(rp, b'{"a":1,"a":2}')
            self._assert_err("DUPLICATE_JSON_KEY", audit.load_hardware_provenance, root)
            audit.write_regular_bytes_safe(rp, b"[1,2]")
            self._assert_err("RECEIPT_OBJECT_REQUIRED", audit.load_hardware_provenance, root)

            def _bad_mlos(mutator, code: str) -> None:
                o = copy.deepcopy(base_obj)
                mutator(o)
                audit.write_regular_bytes_safe(rp, json.dumps(o).encode("utf-8"))
                self._assert_err(code, audit.load_hardware_provenance, root)

            _bad_mlos(lambda o: o.__setitem__("schema", "bad"), "RECEIPT_SCHEMA_MISMATCH")
            _bad_mlos(lambda o: o.__setitem__("clean_hardware_run", False), "HARDWARE_NOT_CLEAN")
            _bad_mlos(lambda o: o.__setitem__("anomalies", ["throttled"]), "HARDWARE_ANOMALIES")
            _bad_mlos(lambda o: o.__setitem__("anomalies", ""), "HARDWARE_ANOMALIES")
            _bad_mlos(lambda o: o.__setitem__("determinism_zone", "A"), "RECEIPT_ZONE_MISMATCH")
            _bad_mlos(lambda o: o.__setitem__("execution", []), "RECEIPT_EXEC_MISSING")
            _bad_mlos(lambda o: o["execution"].__setitem__("exit_code", 1), "INT_OUT_OF_RANGE")
            _bad_mlos(lambda o: o.__setitem__("start_gpu_telemetry", None), "RECEIPT_GPU_MISSING")
            _bad_mlos(lambda o: o.__setitem__("end_gpu_telemetry", None), "RECEIPT_GPU_MISSING")
            _bad_mlos(lambda o: o["start_gpu_telemetry"].__setitem__("pstate", "P0"), "GPU_NOT_IDLE_P8")
            _bad_mlos(lambda o: o["end_gpu_telemetry"].__setitem__("pstate", "P0"), "GPU_NOT_IDLE_P8")

    def test_10_certificate_envelope_and_secondary_audit_tampering(self) -> None:
        cert = _load_disk_cert()
        verdict = audit.validate_certificate_payload(cert, project_root=_TRACK_DIR, verify_live_lean=False)
        self.assertIs(verdict["verified"], True)
        self.assertEqual(verdict["theorem_count"], 10)

        self._assert_err("INVALID_BOOL_TYPE", audit.validate_certificate_payload, cert, verify_live_lean=0)
        self._assert_err("INVALID_BOOL_TYPE", audit.secondary_audit_payload, cert["payload"], verify_live_lean=0)
        self._assert_err("INVALID_DICT", audit.validate_certificate_payload, [1, 2])

        with mock.patch.object(audit, "resolve_lean_binary", return_value="lean"):
            with mock.patch.object(audit, "query_lean_version", return_value="Lean (version 4.36.0, drift)"):
                self._assert_err("LEAN_VERSION_DRIFT", audit.secondary_audit_payload, cert["payload"], project_root=_TRACK_DIR, verify_live_lean=True)
            with mock.patch.object(audit, "query_lean_version", return_value=cert["payload"]["lean_version_line"]):
                bad_mod = copy.deepcopy(cert["payload"]["lean_module"])
                bad_mod["theorem_count"] = 0
                with mock.patch.object(audit, "run_live_lean_module", return_value=bad_mod):
                    self._assert_err("LIVE_LEAN_DRIFT", audit.secondary_audit_payload, cert["payload"], project_root=_TRACK_DIR, verify_live_lean=True)

        for key, val, code in (
            ("schema_version", "wrong", "SCHEMA_MISMATCH"),
            ("study_id", "wrong", "STUDY_ID_MISMATCH"),
            ("payload_sha256", "0" * 64, "PAYLOAD_HASH_MISMATCH"),
            ("certificate_sha256", "0" * 64, "CERT_HASH_MISMATCH"),
        ):
            b = copy.deepcopy(cert)
            b[key] = val
            self._assert_err(code, audit.validate_certificate_payload, b)

        b_ext = copy.deepcopy(cert)
        b_ext["extra"] = 1
        self._assert_err("KEYSET_MISMATCH", audit.validate_certificate_payload, b_ext)

        def _tamper(mutator, code: str) -> None:
            p = copy.deepcopy(cert["payload"])
            mutator(p)
            c2 = _rehash_cert(p)
            self._assert_err(code, audit.validate_certificate_payload, c2, project_root=_TRACK_DIR, verify_live_lean=False)

        _tamper(lambda p: p.__setitem__("study_id", "X"), "STUDY_ID_MISMATCH")
        _tamper(lambda p: p.__setitem__("novelty_class", "N0"), "NOVELTY_MISMATCH")
        _tamper(lambda p: p.__setitem__("oracle_class", "float"), "ORACLE_CLASS_MISMATCH")
        _tamper(lambda p: p.__setitem__("measured_live_silicon", False), "LIVE_SILICON_FLAG")
        _tamper(lambda p: p.__setitem__("measured_external_mathlib", True), "MATHLIB_FLAG")
        _tamper(lambda p: p["privacy_locks"].__setitem__("audio_capture_accessed", True), "PRIVACY_AUDIO")
        _tamper(lambda p: p["privacy_locks"].__setitem__("camera_accessed", True), "PRIVACY_CAMERA")
        _tamper(lambda p: p["privacy_locks"].__setitem__("display_modified", True), "PRIVACY_DISPLAY")
        _tamper(lambda p: p.__setitem__("lean_toolchain", "leanprover/lean4:v4.0.0"), "TOOLCHAIN_MISMATCH")
        _tamper(lambda p: p.__setitem__("lean_version_line", "Lean (version 4.0.0)"), "LEAN_VERSION_MISMATCH")
        _tamper(lambda p: p["prior_literature_n0"].pop(), "LIT_MISMATCH")
        _tamper(lambda p: p["project_manifest"].__setitem__("theorem_count", 9), "THEOREM_COUNT_MISMATCH")
        _tamper(lambda p: p["project_manifest"].__setitem__("lean_toolchain_sha256", "0" * 64), "TOOLCHAIN_SHA_MISMATCH")
        _tamper(lambda p: p["project_manifest"].__setitem__("lakefile_sha256", "0" * 64), "LAKEFILE_SHA_MISMATCH")
        _tamper(lambda p: p["project_manifest"].__setitem__("c_probe_source_sha256", "0" * 64), "C_PROBE_SHA_MISMATCH")
        _tamper(lambda p: p["project_manifest"].__setitem__("live_probe_json_sha256", "0" * 64), "LIVE_PROBE_SHA_MISMATCH")
        _tamper(lambda p: p["project_manifest"].__setitem__("mlos_receipt_json_sha256", "0" * 64), "MLOS_SHA_MISMATCH")
        _tamper(lambda p: p["hardware_provenance"].__setitem__("profile_id", "wrong"), "HARDWARE_PROVENANCE_MISMATCH")
        _tamper(lambda p: p["lean_module"].__setitem__("rel_path", "Bad.lean"), "REL_PATH_MISMATCH")
        _tamper(lambda p: p["lean_module"].__setitem__("source_sha256", "0" * 64), "LEAN_SHA_SELF_MISMATCH")
        _tamper(lambda p: (p["lean_module"].__setitem__("source_sha256", "0" * 64), p["project_manifest"].__setitem__("lean_source_sha256", "0" * 64)), "LEAN_SOURCE_SHA_MISMATCH")
        _tamper(lambda p: p["lean_module"].__setitem__("line_count", 999), "LEAN_LINE_COUNT_MISMATCH")
        _tamper(lambda p: p["lean_module"].__setitem__("theorem_count", 9), "MOD_THEOREM_COUNT")
        _tamper(lambda p: p["lean_module"].__setitem__("static_envelope_clean", False), "STATIC_ENVELOPE_FLAG")
        _tamper(lambda p: p["lean_module"].__setitem__("kernel_exit_code", 1), "KERNEL_EXIT_NONZERO")
        _tamper(lambda p: p["lean_module"].__setitem__("zero_warnings", False), "WARNINGS_FLAG")
        _tamper(lambda p: p["lean_module"]["theorems"].pop(), "THEOREMS_LIST_MISMATCH")
        _tamper(lambda p: p["lean_module"].__setitem__("theorems", "1234567890"), "THEOREMS_LIST_MISMATCH")
        _tamper(lambda p: p["lean_module"]["theorems"][0].__setitem__("name", "bad"), "THEOREM_NAME_MISMATCH")
        _tamper(lambda p: p["lean_module"]["theorems"][0].__setitem__("standard_axioms_only", False), "THEOREM_AXIOM_FLAG")
        _tamper(lambda p: p["lean_module"]["theorems"][0].__setitem__("axioms", ["a", "b", "c", "d"]), "AXIOM_LIST_INVALID")
        _tamper(lambda p: p["lean_module"]["theorems"][0].__setitem__("axioms", "ab"), "AXIOM_LIST_INVALID")
        _tamper(lambda p: p["lean_module"]["theorems"][0].__setitem__("axioms", ["sorryAx"]), "FORBIDDEN_LEAN_AXIOM")
        _tamper(lambda p: p["lean_module"]["theorems"][0].__setitem__("axioms", ["propext", "propext"]), "DUPLICATE_AXIOM")
        _tamper(lambda p: p["lean_module"]["theorems"][0].__setitem__("axioms", ["propext"]), "AXIOM_SET_MISMATCH")
        _tamper(lambda p: p["pillar1_competing_potential"].__setitem__("wikitext2_h16_sign_inversion", False), "PILLAR1_MISMATCH")
        _tamper(lambda p: p["pillar2_live_silicon"].__setitem__("exp_a_total_blocks", 9999), "PILLAR2_MISMATCH")
        _tamper(lambda p: p["pillar2_live_silicon"]["idle_baseline"].__setitem__("pkg_idle_w_q", "2/4"), "NON_REDUCED_RATIONAL")
        _tamper(lambda p: p["summary"].__setitem__("theorem_count", 9), "SUMMARY_THMS")
        _tamper(lambda p: p["summary"].__setitem__("universal_theorem_count", 7), "SUMMARY_UNIV")
        _tamper(lambda p: p["summary"].__setitem__("zero_axiom_theorem_count", 1), "SUMMARY_ZERO_AX")
        _tamper(lambda p: p["summary"].__setitem__("forbidden_axiom_count", 1), "SUMMARY_FORBIDDEN")
        _tamper(lambda p: p["summary"].__setitem__("lean_kernel_checked", False), "SUMMARY_KERNEL")
        _tamper(lambda p: p["summary"].__setitem__("all_theorems_standard_axioms_only", False), "SUMMARY_STD_AX")
        _tamper(lambda p: p["summary"].__setitem__("live_silicon_verified", False), "SUMMARY_SILICON")
        _tamper(lambda p: p["summary"].__setitem__("float_count_on_trust_path", 1), "SUMMARY_FLOATS")
        _tamper(lambda p: p["summary"].__setitem__("bare_assert_count", 1), "SUMMARY_ASSERTS")
        _tamper(lambda p: p["summary"].__setitem__("rng_calls", 1), "SUMMARY_RNG")
        _tamper(lambda p: p.__setitem__("measured_external_mathlib", 0), "INVALID_BOOL_TYPE")
        _tamper(lambda p: p["summary"].__setitem__("rng_calls", False), "UNEXPECTED_BOOL_LEAF")
        _tamper(lambda p: p["prior_literature_n0"].__setitem__(0, True), "UNEXPECTED_BOOL_ITEM")

    def test_11_cli_error_paths_and_check_file_utf8(self) -> None:
        for bad_argv, exp_err in (
            (["--bogus"], "INVALID_CLI_ARGS"),
            (["--write"], "INVALID_CLI_ARGS"),
            (["--write", ""], "INVALID_CLI_ARGS"),
            (["--write", "--json"], "INVALID_CLI_ARGS"),
            (["--write", "-x"], "INVALID_CLI_ARGS"),
            (["--check"], "INVALID_CLI_ARGS"),
            (["--check", ""], "INVALID_CLI_ARGS"),
            (["--check", "--json"], "INVALID_CLI_ARGS"),
            (["--bogus", "x"], "INVALID_CLI_ARGS"),
            (123, "INVALID_CLI_ARGS"),
            (["--check", 123], "INVALID_STR"),
            (["--write", None], "INVALID_STR"),
        ):
            buf_err = io.StringIO()
            with mock.patch.object(sys, "stderr", buf_err):
                rc = audit.main(bad_argv)
            self.assertEqual(rc, 2)
            self.assertIn(exp_err, buf_err.getvalue())

        with tempfile.TemporaryDirectory() as td:
            bad_utf8 = Path(td) / "bad.json"
            audit.write_regular_bytes_safe(bad_utf8, b"\xff\xfe\xfd")
            self._assert_err("INVALID_UTF8_JSON", audit.check_certificate_file, bad_utf8, verify_live_lean=False)

            bad_json = Path(td) / "bad_syntax.json"
            audit.write_regular_bytes_safe(bad_json, b'{"x": 1.5}')
            buf_err2 = io.StringIO()
            with mock.patch.object(sys, "stderr", buf_err2):
                rc2 = audit.main(["--check", str(bad_json)])
            self.assertEqual(rc2, 2)
            self.assertIn("FLOAT_FORBIDDEN", buf_err2.getvalue())

            cert_raw = audit.read_regular_bytes_capped(_CERT_PATH, "disk_cert")
            crlf_p = Path(td) / "crlf_cert.json"
            audit.write_regular_bytes_safe(crlf_p, cert_raw.replace(b"\n", b"\r\n"))
            self._assert_err("NON_CANONICAL_CERT_BYTES", audit.check_certificate_file, crlf_p, verify_live_lean=False)
            pretty_p = Path(td) / "pretty_cert.json"
            pretty_bytes = (json.dumps(_load_disk_cert(), indent=2, sort_keys=True) + "\n").encode("utf-8")
            audit.write_regular_bytes_safe(pretty_p, pretty_bytes)
            self._assert_err("NON_CANONICAL_CERT_BYTES", audit.check_certificate_file, pretty_p, verify_live_lean=False)

    # ------------------------------------------------------------------
    # 90-95: Live Lean 4.36.0 Kernel Negative Controls & Full Suite
    # ------------------------------------------------------------------

    def test_90_live_lean_module_negative_and_fast_positive(self) -> None:
        lean_bin = audit.resolve_lean_binary()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bad_u = root / "BadUtf8.lean"
            audit.write_regular_bytes_safe(bad_u, b"\xff\xfe")
            self._assert_err("INVALID_UTF8_LEAN", audit.run_live_lean_module, lean_bin, root, "BadUtf8.lean", ("T.t",))
            bad_sorry = root / "BadSorry.lean"
            audit.write_regular_bytes_safe(bad_sorry, b"theorem t : False := by sorry\n")
            self._assert_err("LEAN4_SORRY", audit.run_live_lean_module, lean_bin, root, "BadSorry.lean", ("t",))
            bad_type = root / "BadType.lean"
            audit.write_regular_bytes_safe(bad_type, b"theorem bad : 1 = 2 := by decide\n")
            self._assert_err("LEAN_KERNEL_REJECTED", audit.run_live_lean_module, lean_bin, root, "BadType.lean", ("bad",))
            bad_warn = root / "BadWarn.lean"
            audit.write_regular_bytes_safe(bad_warn, b"theorem w (unused_x : Nat) : 1 = 1 := rfl\n#print axioms w\n")
            self._assert_err("LEAN_WARNING_FORBIDDEN", audit.run_live_lean_module, lean_bin, root, "BadWarn.lean", ("w",))
            good_min = root / "GoodMin.lean"
            audit.write_regular_bytes_safe(good_min, b"theorem ok : 2 + 2 = 4 := rfl\n#print axioms ok\n")
            with mock.patch.object(audit.subprocess, "run", side_effect=OSError("boom")):
                self._assert_err("LEAN_EXEC_ERROR", audit.run_live_lean_module, lean_bin, root, "GoodMin.lean", ("ok",))
            with mock.patch.object(audit.subprocess, "run", side_effect=subprocess.TimeoutExpired("lean", 60)):
                self._assert_err("LEAN_EXEC_ERROR", audit.run_live_lean_module, lean_bin, root, "GoodMin.lean", ("ok",))
            with mock.patch.object(audit.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="", stderr="err")):
                self._assert_err("LEAN_STDERR_NONEMPTY", audit.run_live_lean_module, lean_bin, root, "GoodMin.lean", ("ok",))
            res = audit.run_live_lean_module(lean_bin, root, "GoodMin.lean", ("ok",))
            self.assertEqual(res["kernel_exit_code"], 0)
            self.assertEqual(res["theorems"], [{"name": "ok", "axioms": [], "standard_axioms_only": True}])

    def test_95_live_lean_full_suite_and_cli_parity(self) -> None:
        live_cert = audit.build_certificate(_TRACK_DIR)
        disk_raw = audit.read_regular_bytes_capped(_CERT_PATH, "disk_cert")
        self.assertEqual(oracle.canonical_json_bytes(live_cert) + b"\n", disk_raw)

        out_check = io.StringIO()
        with mock.patch.object(sys, "stdout", out_check):
            rc = audit.main(["--check", str(_CERT_PATH)])
        self.assertEqual(rc, 0)
        chk = oracle.parse_strict_json_text(out_check.getvalue())
        self.assertIs(chk["verified"], True)
        self.assertEqual(chk["theorem_count"], 10)

        with mock.patch.object(audit, "build_certificate", return_value=live_cert):
            out_sum = io.StringIO()
            with mock.patch.object(sys, "stdout", out_sum):
                self.assertEqual(audit.main([]), 0)
            self.assertEqual(oracle.parse_strict_json_text(out_sum.getvalue())["theorem_count"], 10)

            out_st = io.StringIO()
            with mock.patch.object(sys, "stdout", out_st):
                self.assertEqual(audit.main(["--standalone", "--json"]), 0)
            self.assertEqual(out_st.getvalue().encode("utf-8"), disk_raw)

            with tempfile.TemporaryDirectory() as td:
                out_p = Path(td) / "rebuilt.json"
                out_w = io.StringIO()
                with mock.patch.object(sys, "stdout", out_w):
                    self.assertEqual(audit.main(["--write", str(out_p)]), 0)
                w_obj = oracle.parse_strict_json_text(out_w.getvalue())
                self.assertIs(w_obj["written"], True)
                self.assertEqual(w_obj["certificate_sha256"], live_cert["certificate_sha256"])
                self.assertEqual(audit.read_regular_bytes_capped(out_p), disk_raw)


if __name__ == "__main__":
    unittest.main()
