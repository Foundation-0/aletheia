#!/usr/bin/env python3
"""Adversarial, Pure-Z/Q & Live Lean 4.36.0 Kernel-Certified Bridge Test Suite.

Zero bare asserts, zero AST floats / float(), zero .isdigit(), zero islink/is_symlink,
zero system null device writes (scratch os.mkfifo only), zero CodeQL secret* variable names.
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
import sys
import tempfile
import threading
import unittest
from unittest import mock

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import lean4_kernel_bridge_audit as audit  # noqa: E402

_TRACK_DIR = Path(__file__).resolve().parent
_CERT_PATH = _TRACK_DIR / "lean4_kernel_bridge_certificate.json"


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
    p_sha = hashlib.sha256(audit.canonical_json_bytes(payload)).hexdigest()
    core = {
        "schema_version": audit.SCHEMA_VERSION,
        "track_id": audit.TRACK_ID,
        "payload_sha256": p_sha,
        "payload": payload,
    }
    c_sha = hashlib.sha256(audit.canonical_json_bytes(core)).hexdigest()
    return {
        "schema_version": audit.SCHEMA_VERSION,
        "track_id": audit.TRACK_ID,
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "payload": payload,
    }


def _load_disk_cert() -> dict:
    raw = audit.read_regular_bytes_capped(_CERT_PATH, "disk_cert")
    return audit.parse_strict_json_text(raw.decode("utf-8"), require_object=True)


class TestTrackS48Lean4KernelBridgeR5(unittest.TestCase):
    """Fast deterministic & adversarial tests first (01-25), live Lean 4.36.0 last (90-95)."""

    def _assert_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(audit.Lean4KernelBridgeError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    # ------------------------------------------------------------------
    # 01-05: Exact Type, Integer, Rational & Strict JSON Primitives
    # ------------------------------------------------------------------

    def test_01_require_primitives_and_boundaries(self) -> None:
        audit.require_ok(True, "X", "ok")
        self._assert_err("INVALID_CONDITION_TYPE", audit.require_ok, 1, "X", "bad")
        self._assert_err("TEST_FAIL", audit.require_ok, False, "TEST_FAIL", "fail")

        self.assertIs(audit.require_exact_bool(True, "b"), True)
        self.assertIs(audit.require_exact_bool(False, "b"), False)
        self._assert_err("INVALID_BOOL_TYPE", audit.require_exact_bool, 1, "b")

        max_ok = (1 << audit.MAX_INT_BITS) - 1
        self.assertEqual(audit.require_exact_int(max_ok, "i"), max_ok)
        self.assertEqual(audit.require_exact_int(-max_ok, "i"), -max_ok)
        self._assert_err("INT_BIT_LIMIT", audit.require_exact_int, 1 << audit.MAX_INT_BITS, "i")
        self._assert_err("INVALID_INT_TYPE", audit.require_exact_int, True, "i")
        self._assert_err("INVALID_INT_TYPE", audit.require_exact_int, _IntSub(5), "i")

        self.assertEqual(audit.require_exact_int(10, "i", lo=10, hi=10), 10)
        self._assert_err("INT_OUT_OF_RANGE", audit.require_exact_int, 9, "i", lo=10)
        self._assert_err("INT_OUT_OF_RANGE", audit.require_exact_int, 11, "i", hi=10)
        self._assert_err("INVALID_BOUND_TYPE", audit.require_exact_int, 10, "i", lo=True)
        self._assert_err("INVALID_BOUND_TYPE", audit.require_exact_int, 10, "i", hi=True)

        self.assertEqual(audit.require_exact_str("", "s", non_empty=False), "")
        self.assertEqual(audit.require_exact_str("abc", "s", max_len=3), "abc")
        self._assert_err("INVALID_STR", audit.require_exact_str, _StrSub("a"), "s")
        self._assert_err("NUL_BYTE_FORBIDDEN", audit.require_exact_str, "a\x00b", "s")
        self._assert_err("EMPTY_STR", audit.require_exact_str, "", "s")
        self._assert_err("STR_TOO_LONG", audit.require_exact_str, "abcd", "s", max_len=3)
        self._assert_err("INVALID_UTF8_SURROGATE", audit.require_exact_str, "\ud800", "s")

        good_sha = "0123456789abcdef" * 4
        self.assertEqual(audit.require_sha256_hex(good_sha, "h"), good_sha)
        self._assert_err("INVALID_SHA256", audit.require_sha256_hex, good_sha[:-1], "h")
        self._assert_err("INVALID_SHA256", audit.require_sha256_hex, "A" * 64, "h")
        self._assert_err("INVALID_SHA256", audit.require_sha256_hex, "g" * 64, "h")

    def test_02_ascii_int_and_rational_parsers(self) -> None:
        self.assertEqual(audit.parse_exact_int_ascii("0", "n"), 0)
        self.assertEqual(audit.parse_exact_int_ascii("-42", "n"), -42)
        self.assertEqual(audit.parse_exact_int_ascii("9" * 100, "n"), int("9" * 100))
        self._assert_err("INVALID_INT_ASCII", audit.parse_exact_int_ascii, "-", "n")
        self._assert_err("INVALID_INT_ASCII", audit.parse_exact_int_ascii, "+5", "n")
        self._assert_err("INVALID_INT_ASCII", audit.parse_exact_int_ascii, "\u0665", "n")
        self._assert_err("LEADING_ZERO_FORBIDDEN", audit.parse_exact_int_ascii, "01", "n")
        self._assert_err("NEG_ZERO_FORBIDDEN", audit.parse_exact_int_ascii, "-0", "n")
        self._assert_err("INT_DIGIT_LIMIT", audit.parse_exact_int_ascii, "1" * (audit.MAX_INT_DIGITS + 1), "n")
        self._assert_err("INT_BIT_LIMIT", audit.parse_exact_int_ascii, str(1 << audit.MAX_INT_BITS), "n")

        self.assertEqual(audit.format_exact_rational(Fraction(7, 1)), "7")
        self.assertEqual(audit.format_exact_rational(Fraction(-5, 6)), "-5/6")
        self._assert_err("INVALID_FRACTION_TYPE", audit.format_exact_rational, 5)
        self._assert_err("INT_BIT_LIMIT", audit.format_exact_rational, Fraction(1 << audit.MAX_INT_BITS, 1))
        self._assert_err("INT_BIT_LIMIT", audit.format_exact_rational, Fraction(1, 1 << audit.MAX_INT_BITS))

        self.assertEqual(audit.parse_exact_rational("7", "q"), Fraction(7, 1))
        self.assertEqual(audit.parse_exact_rational("1/2", "q"), Fraction(1, 2))
        self.assertEqual(audit.parse_exact_rational("-5/6", "q"), Fraction(-5, 6))
        self._assert_err("INVALID_RATIONAL", audit.parse_exact_rational, "1/2/3", "q")
        self._assert_err("NON_CANONICAL_RATIONAL", audit.parse_exact_rational, "3/1", "q")
        self._assert_err("NON_CANONICAL_RATIONAL", audit.parse_exact_rational, "3/0", "q")
        self._assert_err("NON_REDUCED_RATIONAL", audit.parse_exact_rational, "2/4", "q")
        self._assert_err("NON_REDUCED_RATIONAL", audit.parse_exact_rational, "-4/6", "q")

    def test_03_strict_json_parser_and_tree_limits(self) -> None:
        self.assertEqual(audit.parse_strict_json_text('{"a": 1, "b": [true, null, "x"]}'), {"a": 1, "b": [True, None, "x"]})
        self.assertEqual(audit.parse_strict_json_text("[1, 2]", require_object=False), [1, 2])
        self._assert_err("JSON_OBJECT_REQUIRED", audit.parse_strict_json_text, "[1, 2]", require_object=True)
        self._assert_err("FLOAT_FORBIDDEN", audit.parse_strict_json_text, '{"x": 1.5}')
        self._assert_err("FLOAT_FORBIDDEN", audit.parse_strict_json_text, '{"x": 1e5}')
        self._assert_err("JSON_CONST_FORBIDDEN", audit.parse_strict_json_text, '{"x": NaN}')
        self._assert_err("JSON_CONST_FORBIDDEN", audit.parse_strict_json_text, '{"x": Infinity}')
        self._assert_err("DUPLICATE_JSON_KEY", audit.parse_strict_json_text, '{"a": 1, "a": 2}')
        self._assert_err("JSON_PARSE_ERROR", audit.parse_strict_json_text, "{bad")
        self._assert_err("JSON_DEPTH_LIMIT", audit.parse_strict_json_text, "[" * 100 + "]" * 100)

        # Depth boundary: depth == MAX_JSON_DEPTH passes, MAX_JSON_DEPTH + 1 fails
        ok_nested: list = []
        cur = ok_nested
        for _ in range(audit.MAX_JSON_DEPTH):
            nxt: list = []
            cur.append(nxt)
            cur = nxt
        audit._validate_json_tree(ok_nested)
        cur.append([])
        self._assert_err("JSON_DEPTH_LIMIT", audit._validate_json_tree, ok_nested)

        # Node cap exact boundary: MAX_JSON_NODES passes, MAX_JSON_NODES + 1 fails
        audit._validate_json_tree([0] * (audit.MAX_JSON_NODES - 1))
        self._assert_err("JSON_NODE_LIMIT", audit._validate_json_tree, [0] * audit.MAX_JSON_NODES)

        # Float object (created via json.loads without any AST float literal) & disallowed subclasses
        runtime_float = json.loads("1.25")
        self._assert_err("FLOAT_FORBIDDEN", audit.canonical_json_bytes, {"x": runtime_float})
        self._assert_err("INVALID_JSON_TYPE", audit.canonical_json_bytes, _DictSub({"a": 1}))
        self._assert_err("INVALID_JSON_TYPE", audit.canonical_json_bytes, {"a": _ListSub([1])})
        self._assert_err("INVALID_JSON_TYPE", audit.canonical_json_bytes, {"a": _IntSub(1)})
        self._assert_err("INVALID_JSON_TYPE", audit.canonical_json_bytes, {"a": _StrSub("x")})
        self._assert_err("INVALID_JSON_TYPE", audit.canonical_json_bytes, {"a": (1, 2)})
        self._assert_err("INVALID_STR", audit.canonical_json_bytes, {1: "a"})

    # ------------------------------------------------------------------
    # 04-06: Hardened Filesystem Security, Scratch FIFO, Hardlinks & Races
    # ------------------------------------------------------------------

    def test_04_zone_b_read_write_symlinks_fifo_caps(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            # Path type checks
            self._assert_err("INVALID_PATH_TYPE", audit.read_regular_bytes_capped, str(base / "a"))
            self._assert_err("INVALID_PATH_TYPE", audit.read_regular_bytes_capped, _PathSub(base / "a"))
            self._assert_err("INVALID_LEAF_NAME", audit.read_regular_bytes_capped, Path("/"))
            self._assert_err("INVALID_LEAF_NAME", audit.read_regular_bytes_capped, base / "..")

            # Nested auto-mkdir write + exact 0o600 mode + overwrite
            nested = base / "sub1" / "sub2" / "cert.json"
            payload_b = b'{"ok":true}\n'
            audit.write_regular_bytes_safe(nested, payload_b)
            st_mode = stat.S_IMODE(os.lstat(nested).st_mode)
            self.assertEqual(st_mode, 0o600)
            self.assertEqual(audit.read_regular_bytes_capped(nested, max_bytes=len(payload_b)), payload_b)
            self._assert_err("FILE_TOO_LARGE", audit.read_regular_bytes_capped, nested, max_bytes=len(payload_b) - 1)
            self._assert_err("INT_OUT_OF_RANGE", audit.read_regular_bytes_capped, nested, max_bytes=0)
            self._assert_err("INT_OUT_OF_RANGE", audit.read_regular_bytes_capped, nested, max_bytes=audit.MAX_ALLOWED_CAP_BYTES + 1)
            self._assert_err("INVALID_PAYLOAD_BYTES", audit.write_regular_bytes_safe, nested, "not-bytes")

            # Overwrite existing regular file cleanly + multi-chunk > 64 KiB read
            big = b"A" * 70_000
            audit.write_regular_bytes_safe(nested, big)
            self.assertEqual(audit.read_regular_bytes_capped(nested, max_bytes=70_000), big)

            # Nonexistent read & nonexistent ancestor (read must NEVER create missing parent dir)
            self._assert_err("FILE_READ_ERROR", audit.read_regular_bytes_capped, base / "missing.json")
            self._assert_err("FILE_READ_ERROR", audit.read_regular_bytes_capped, base / "no_dir" / "missing.json")
            self.assertFalse((base / "no_dir").exists())

            # Directory target rejected on read & write
            d_target = base / "adir"
            d_target.mkdir()
            self._assert_err("NOT_A_REGULAR_FILE", audit.read_regular_bytes_capped, d_target)
            self._assert_err("NOT_A_REGULAR_FILE", audit.write_regular_bytes_safe, d_target, b"x")

            # Non-directory ancestor (regular file used as dir)
            self._assert_err("SYMLINK_FORBIDDEN", audit.read_regular_bytes_capped, nested / "child")
            self._assert_err("SYMLINK_FORBIDDEN", audit.write_regular_bytes_safe, nested / "child", b"x")

            # Symlink leaf & symlink ancestor rejected on both read & write
            sym_leaf = base / "sym_leaf"
            os.symlink(nested, sym_leaf)
            self._assert_err("SYMLINK_FORBIDDEN", audit.read_regular_bytes_capped, sym_leaf)
            self._assert_err("SYMLINK_FORBIDDEN", audit.write_regular_bytes_safe, sym_leaf, b"x")

            sym_dir = base / "sym_dir"
            os.symlink(d_target, sym_dir)
            self._assert_err("SYMLINK_FORBIDDEN", audit.read_regular_bytes_capped, sym_dir / "f")
            self._assert_err("SYMLINK_FORBIDDEN", audit.write_regular_bytes_safe, sym_dir / "f", b"x")

            # Hardlink target rejected on BOTH read and write (before creating temp file)
            hl_target = base / "hl_target"
            os.link(nested, hl_target)
            try:
                self._assert_err("HARDLINK_FORBIDDEN", audit.read_regular_bytes_capped, hl_target)
                with mock.patch.object(audit.secrets, "token_hex", side_effect=RuntimeError("temp_opened_early")):
                    self._assert_err("HARDLINK_FORBIDDEN", audit.write_regular_bytes_safe, hl_target, b"x")
            finally:
                os.unlink(hl_target)

            # Simulated TOCTOU races: temp nlink altered, and pre-replace symlink / non-reg / hardlink swap
            race_target = base / "race.json"
            real_fstat = os.fstat
            with mock.patch.object(
                audit.os,
                "fstat",
                side_effect=lambda fd: mock.Mock(st_mode=real_fstat(fd).st_mode, st_nlink=2),
            ):
                self._assert_err("HARDLINK_FORBIDDEN", audit.write_regular_bytes_safe, race_target, b"x")

            for st_mode_race, nlink_race, exp_race_code in (
                (stat.S_IFLNK | 0o777, 1, "SYMLINK_FORBIDDEN"),
                (stat.S_IFDIR | 0o755, 2, "NOT_A_REGULAR_FILE"),
                (stat.S_IFREG | 0o600, 2, "HARDLINK_FORBIDDEN"),
            ):
                call_n = {"n": 0}

                def _lstat_race(name, dir_fd=None, *, _m=st_mode_race, _nl=nlink_race, _c=call_n):
                    _c["n"] += 1
                    if _c["n"] == 1:
                        raise FileNotFoundError(name)
                    return mock.Mock(st_mode=_m, st_nlink=_nl)

                with mock.patch.object(audit.os, "lstat", side_effect=_lstat_race):
                    self._assert_err(exp_race_code, audit.write_regular_bytes_safe, race_target, b"x")

            # Pre-replace second lstat OSError wrapped cleanly as FILE_WRITE_ERROR
            lstat_err_n = {"n": 0}

            def _lstat_pre_err(name, dir_fd=None):
                lstat_err_n["n"] += 1
                if lstat_err_n["n"] == 1:
                    raise FileNotFoundError(name)
                raise PermissionError("pre_lstat_denied")

            with mock.patch.object(audit.os, "lstat", side_effect=_lstat_pre_err):
                with self.assertRaises(audit.Lean4KernelBridgeError) as ctx_pl:
                    audit.write_regular_bytes_safe(race_target, b"x")
                self.assertEqual(ctx_pl.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("pre-replace lstat failed", str(ctx_pl.exception))

            # Short-write (0 bytes) rejected & multi-chunk partial write completes cleanly
            short_target = base / "short.json"
            with mock.patch.object(audit.os, "write", return_value=0):
                self._assert_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, short_target, b"hello")
            self.assertFalse(short_target.exists())

            real_write = os.write
            chunks_seen = {"n": 0}

            def _partial_write(fd: int, data) -> int:
                chunks_seen["n"] += 1
                if chunks_seen["n"] == 1:
                    return real_write(fd, bytes(data)[:3])
                return real_write(fd, data)

            with mock.patch.object(audit.os, "write", side_effect=_partial_write):
                audit.write_regular_bytes_safe(short_target, b"abcdefgh")
            self.assertEqual(audit.read_regular_bytes_capped(short_target), b"abcdefgh")
            self.assertGreaterEqual(chunks_seen["n"], 2)

            # OSError error-path hardening in _open_dir_chain, read_regular_bytes_capped, and write_regular_bytes_safe
            with mock.patch.object(audit.os, "mkdir", side_effect=PermissionError("no_mkdir")):
                with self.assertRaises(audit.Lean4KernelBridgeError) as ctx_mk:
                    audit.write_regular_bytes_safe(base / "mk_fail_dir" / "f.json", b"x")
                self.assertEqual(ctx_mk.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("mkdir failed", str(ctx_mk.exception))

            real_open_os = os.open
            reopen_hits = {"n": 0}

            def _open_fail_after_mkdir(path, flags, *args, **kwargs):
                if path == "reopen_fail_dir" and kwargs.get("dir_fd") is not None:
                    reopen_hits["n"] += 1
                    if reopen_hits["n"] == 1:
                        raise FileNotFoundError(errno.ENOENT, "missing", path)
                    raise PermissionError("reopen_denied")
                return real_open_os(path, flags, *args, **kwargs)

            with mock.patch.object(audit.os, "open", side_effect=_open_fail_after_mkdir):
                with self.assertRaises(audit.Lean4KernelBridgeError) as ctx_ro:
                    audit.write_regular_bytes_safe(base / "reopen_fail_dir" / "f.json", b"x")
                self.assertEqual(ctx_ro.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("open created dir failed", str(ctx_ro.exception))

            with mock.patch.object(audit.os, "read", side_effect=OSError("read_io_err")):
                self._assert_err("FILE_READ_ERROR", audit.read_regular_bytes_capped, short_target)

            with mock.patch.object(audit.os, "lstat", side_effect=PermissionError("lstat_denied")):
                self._assert_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, base / "ls_fail.json", b"x")

            def _open_fail_tmp(path, flags, *args, **kwargs):
                if flags & os.O_CREAT:
                    raise PermissionError("tmp_denied")
                return real_open_os(path, flags, *args, **kwargs)

            with mock.patch.object(audit.os, "open", side_effect=_open_fail_tmp):
                with self.assertRaises(audit.Lean4KernelBridgeError) as ctx_tmp:
                    audit.write_regular_bytes_safe(base / "tmp_fail.json", b"x")
                self.assertEqual(ctx_tmp.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("create temp failed", str(ctx_tmp.exception))

            with mock.patch.object(audit.os, "write", side_effect=OSError("disk_full")):
                self._assert_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, base / "wr_fail.json", b"x")

            with mock.patch.object(audit.os, "replace", side_effect=OSError("replace_fail")):
                self._assert_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, base / "rp_fail.json", b"x")

            # Scratch FIFO (zero system null device writes) rejected on both read & write
            if hasattr(os, "mkfifo"):
                fifo_p = base / "scratch.fifo"
                os.mkfifo(fifo_p, 0o600)
                self._assert_err("NOT_A_REGULAR_FILE", audit.read_regular_bytes_capped, fifo_p)
                self._assert_err("NOT_A_REGULAR_FILE", audit.write_regular_bytes_safe, fifo_p, b"x")

    def test_05_zone_b_relative_pwd_symlink_deleted_cwd_and_concurrency(self) -> None:
        orig_cwd = os.getcwd()
        orig_pwd = os.environ.get("PWD")
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            real_sub = base / "real_sub"
            real_sub.mkdir()
            other_sub = base / "other_sub"
            other_sub.mkdir()
            sym_sub = base / "sym_sub"
            os.symlink(real_sub, sym_sub)

            try:
                os.chdir(real_sub)
                os.environ["PWD"] = str(real_sub)
                rel = Path(".") / "rel_out.json"
                audit.write_regular_bytes_safe(rel, b'{"rel":1}\n')
                self.assertEqual(audit.read_regular_bytes_capped(rel), b'{"rel":1}\n')

                # Symlink in PWD matching current CWD inode rejected on relative path
                os.environ["PWD"] = str(sym_sub)
                self._assert_err("SYMLINK_ANCESTOR_FORBIDDEN", audit.read_regular_bytes_capped, Path("rel_out.json"))

                # Stale nonexistent PWD, mismatched-inode existing PWD, and relative PWD ignored cleanly
                os.environ["PWD"] = str(base / "no_such_pwd")
                self.assertEqual(audit.read_regular_bytes_capped(Path("rel_out.json")), b'{"rel":1}\n')

                os.environ["PWD"] = str(other_sub)
                self.assertEqual(audit.read_regular_bytes_capped(Path("rel_out.json")), b'{"rel":1}\n')

                os.environ["PWD"] = "relative_pwd"
                self.assertEqual(audit.read_regular_bytes_capped(Path("rel_out.json")), b'{"rel":1}\n')

                # Lone surrogate in PWD rejected before os.stat
                with mock.patch.object(audit.os, "environ", {"PWD": "/tmp/\ud800"}):
                    self._assert_err(
                        "INVALID_UTF8_SURROGATE",
                        audit.read_regular_bytes_capped,
                        Path("rel_out.json"),
                    )

                # TOCTOU race during PWD ancestor walk surfaces CWD_UNAVAILABLE
                os.environ["PWD"] = str(real_sub)
                real_open = os.open

                def _fail_pwd_open(path, flags, *args, **kwargs):
                    if path == "real_sub" and kwargs.get("dir_fd") is not None:
                        raise PermissionError("race")
                    return real_open(path, flags, *args, **kwargs)

                with mock.patch.object(audit.os, "open", side_effect=_fail_pwd_open):
                    self._assert_err("CWD_UNAVAILABLE", audit._check_pwd_no_symlinks, "pwd_race")

                # Deleted CWD rejected
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

            # Verified root-owned macOS system-root prefix normalization
            root_lnk = mock.Mock(st_mode=stat.S_IFLNK | 0o777, st_uid=0)
            root_dir = mock.Mock(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
            user_lnk = mock.Mock(st_mode=stat.S_IFLNK | 0o777, st_uid=1000)

            with mock.patch.object(audit.sys, "platform", "darwin"):
                with mock.patch.object(audit.os, "lstat", return_value=root_lnk):
                    with mock.patch.object(audit.os, "readlink", return_value="private/var"):
                        self.assertEqual(
                            audit._normalize_darwin_system_prefix(Path("/var/folders/xx/cert.json")),
                            Path("/private/var/folders/xx/cert.json"),
                        )
                        self.assertEqual(
                            audit._normalize_darwin_system_prefix(Path("a/var/folders/xx/cert.json")),
                            Path("a/var/folders/xx/cert.json"),
                        )
                        self.assertEqual(
                            audit._normalize_darwin_system_prefix(Path("/var/folders/../cert.json")),
                            Path("/var/folders/../cert.json"),
                        )
                        self.assertEqual(
                            audit._normalize_darwin_system_prefix(Path("/opt/folders/cert.json")),
                            Path("/opt/folders/cert.json"),
                        )
                        self.assertEqual(
                            audit._normalize_darwin_system_prefix(Path("/"), allow_exact=True),
                            Path("/"),
                        )
                    with mock.patch.object(audit.os, "readlink", return_value="/private/tmp"):
                        self.assertEqual(
                            audit._normalize_darwin_system_prefix(Path("/tmp"), allow_exact=True),
                            Path("/private/tmp"),
                        )
                        self.assertEqual(
                            audit._normalize_darwin_system_prefix(Path("/tmp"), allow_exact=False),
                            Path("/tmp"),
                        )
                    with mock.patch.object(audit.os, "readlink", return_value="private/etc"):
                        self.assertEqual(
                            audit._normalize_darwin_system_prefix(Path("/etc/hosts")),
                            Path("/private/etc/hosts"),
                        )
                    with mock.patch.object(audit.os, "readlink", return_value="private/evil"):
                        self.assertEqual(
                            audit._normalize_darwin_system_prefix(Path("/var/folders/xx/cert.json")),
                            Path("/var/folders/xx/cert.json"),
                        )
                with mock.patch.object(audit.os, "readlink", return_value="private/var"):
                    with mock.patch.object(audit.os, "lstat", return_value=root_dir):
                        self.assertEqual(
                            audit._normalize_darwin_system_prefix(Path("/var/folders/xx/cert.json")),
                            Path("/var/folders/xx/cert.json"),
                        )
                    with mock.patch.object(audit.os, "lstat", return_value=user_lnk):
                        self.assertEqual(
                            audit._normalize_darwin_system_prefix(Path("/var/folders/xx/cert.json")),
                            Path("/var/folders/xx/cert.json"),
                        )
                with mock.patch.object(audit.os, "lstat", side_effect=OSError("stat_err")):
                    self.assertEqual(
                        audit._normalize_darwin_system_prefix(Path("/var/folders/xx/cert.json")),
                        Path("/var/folders/xx/cert.json"),
                    )

                # Verify allow_exact=False on absolute target vs allow_exact=True on cwd/PWD
                with mock.patch.object(audit.os, "lstat", return_value=root_lnk):
                    with mock.patch.object(audit.os, "readlink", return_value="private/tmp"):
                        opened_abs: list[str] = []

                        def _trace_abs(p, flags, *args, **kwargs):
                            opened_abs.append(str(p))
                            if p == "/":
                                return 999
                            raise OSError(errno.ELOOP, "eloop")

                        with mock.patch.object(audit.os, "open", side_effect=_trace_abs):
                            with mock.patch.object(audit.os, "close"):
                                self._assert_err(
                                    "SYMLINK_FORBIDDEN",
                                    audit.read_regular_bytes_capped,
                                    Path("/tmp"),
                                )
                        self.assertEqual(opened_abs, ["/", "tmp"])

                        opened_rel: list[str] = []

                        def _trace_rel(p, flags, *args, **kwargs):
                            opened_rel.append(str(p))
                            if p == "file.json":
                                raise OSError(errno.ENOENT, "missing")
                            return 998

                        same_st = mock.Mock(st_dev=1, st_ino=2)
                        with mock.patch.object(audit.Path, "cwd", return_value=Path("/tmp")):
                            with mock.patch.dict(os.environ, {"PWD": "/tmp"}):
                                with mock.patch.object(audit.os, "stat", return_value=same_st):
                                    with mock.patch.object(audit.os, "open", side_effect=_trace_rel):
                                        with mock.patch.object(audit.os, "close"):
                                            self._assert_err(
                                                "FILE_READ_ERROR",
                                                audit.read_regular_bytes_capped,
                                                Path("file.json"),
                                            )
                        self.assertEqual(opened_rel, ["/", "private", "tmp", "/", "private", "tmp", "file.json"])

            with mock.patch.object(audit.sys, "platform", "linux"):
                with mock.patch.object(audit.os, "lstat", return_value=root_lnk):
                    with mock.patch.object(audit.os, "readlink", return_value="private/var"):
                        self.assertEqual(
                            audit._normalize_darwin_system_prefix(Path("/var/folders/xx/cert.json")),
                            Path("/var/folders/xx/cert.json"),
                        )

            # 16-thread concurrent atomic writes to same file: 0 errors, 0 leftover .tmp files
            conc_path = base / "concurrent.json"
            errors: list[BaseException] = []

            def _worker(tid: int) -> None:
                try:
                    for step in range(4):
                        audit.write_regular_bytes_safe(conc_path, f'{{"t":{tid},"s":{step}}}\n'.encode("utf-8"))
                except BaseException as exc:  # pragma: no cover
                    errors.append(exc)

            threads = [threading.Thread(target=_worker, args=(i,)) for i in range(16)]
            for th in threads:
                th.start()
            for th in threads:
                th.join()
            self.assertEqual(errors, [])
            leftover = [p.name for p in base.iterdir() if p.name.endswith(".tmp")]
            self.assertEqual(leftover, [])
            final_obj = audit.parse_strict_json_text(audit.read_regular_bytes_capped(conc_path).decode("utf-8"))
            self.assertIn("t", final_obj)

    # ------------------------------------------------------------------
    # 06-08: Lean 4 Static Envelope Gate & `#print axioms` Parser
    # ------------------------------------------------------------------

    def test_06_lean_static_envelope_and_comment_stripping(self) -> None:
        clean_src = (
            "/- a - sorry / axiom /- nested sorry -/ still - comment -/\n"
            "-- line comment sorry admit unsafe\n"
            "def s : String := \"sorry \\\"admit\\\"\\n\"\n"
            "import Init.Data.Nat.Basic\n"
            "import Std\n"
            "theorem t : 2 - 1 = 1 := by decide\n"
            "-- trailing eof comment without newline"
        )
        audit.static_lean_source_check(clean_src, "clean")

        self._assert_err("LEAN4_UNTERMINATED_COMMENT", audit.static_lean_source_check, "/- unclosed", "u1")
        self._assert_err("LEAN4_UNTERMINATED_COMMENT", audit.static_lean_source_check, 'def s := s!"a { /- unclosed', "u1b")
        self._assert_err("LEAN4_UNTERMINATED_STRING", audit.static_lean_source_check, 'def x := "unclosed', "u2")
        self._assert_err("LEAN4_UNTERMINATED_STRING", audit.static_lean_source_check, 'def x := "abc\\', "u3")
        self._assert_err("LEAN4_UNTERMINATED_STRING", audit.static_lean_source_check, 'def x := s!"unclosed', "u4")
        self._assert_err("LEAN4_UNTERMINATED_STRING", audit.static_lean_source_check, 'def x := s!"abc\\', "u5")
        self._assert_err("LEAN4_UNTERMINATED_STRING", audit.static_lean_source_check, 'def x := s!"a { 1', "u6")
        self._assert_err("LEAN4_UNTERMINATED_STRING", audit.static_lean_source_check, 'def x := r"unclosed', "u7")
        self._assert_err("LEAN4_UNTERMINATED_STRING", audit.static_lean_source_check, 'def x := r#"unclosed', "u8")
        # Single minus operator must NOT start a line comment hiding sorry, and line comment must stop at newline
        self._assert_err("LEAN4_SORRY", audit.static_lean_source_check, "theorem t : 2 - 1 = 1 := by sorry\n", "sub_sorry")
        self._assert_err("LEAN4_SORRY", audit.static_lean_source_check, "-- ok\ntheorem t : False := by sorry\n", "after_line_comment")

        # Hardened Lean 4 lexer: char literals ('"'), raw strings (r"..."/r#"..."#), interpolated strings (s!/m!/f!)
        for bad_lex, exp_lex_code in (
            ('\'"\' \ntheorem t : False := by sorry', "LEAN4_SORRY"),
            ('def _q1 : Char := \'"\'\nset_option debug.skipKernelTC true\ndef _q2 : Char := \'"\'\n', "LEAN4_SKIP_KERNEL_TC"),
            ('def _c := [\'\\\'\',\'"\']\ntheorem t : False := by sorry\n-- "', "LEAN4_SORRY"),
            ('theorem t : 1 = 1 := by decide \'\\\'\'+native\n', "LEAN4_DECIDE_NATIVE"),
            ('r"\\"\ntheorem t : False := by sorry', "LEAN4_SORRY"),
            ('def _r1 : String := r"\\"\nset_option debug.skipKernelTC true\n-- "', "LEAN4_SKIP_KERNEL_TC"),
            ('def _r2 : String := r#"\\" sorry "#\ntheorem t : False := by sorry\n-- "', "LEAN4_SORRY"),
            ('def s := s!"{ (by sorry : Nat) }"\n', "LEAN4_SORRY"),
            ('s!"{sorry}" ++ x', "LEAN4_SORRY"),
            ('def s := m!"a {let _ := { y := 1 }; sorry} b"\n', "LEAN4_SORRY"),
            ('def s := f!"a {if true then "ok" else sorry} b"\n', "LEAN4_SORRY"),
            ('def s := s!"{ (by decide +native : 1 = 1) }"\n', "LEAN4_DECIDE_NATIVE"),
            ('def s := s!"line1\nline2"\ntheorem t : False := by sorry\n', "LEAN4_SORRY"),
            ('def s := s!"\\\n"\ntheorem t : False := by sorry\n', "LEAN4_SORRY"),
            ('!"{"\ntheorem t : False := by sorry\ndef b := "}" ++ s', "LEAN4_SORRY"),
            ('def a := p!"{"\ntheorem t : False := by sorry\ndef b := "}"\n', "LEAN4_SORRY"),
            ('def a := foos!"{"\ntheorem t : False := by sorry\ndef b := "}"\n', "LEAN4_SORRY"),
            ('def a := Foo.s!"{"\ntheorem t : False := by sorry\ndef b := "}"\n', "LEAN4_SORRY"),
            ('def s := "\\""\ntheorem t : False := by sorry\n-- "', "LEAN4_SORRY"),
        ):
            self._assert_err(exp_lex_code, audit.static_lean_source_check, bad_lex, exp_lex_code)

        for ok_lex in (
            'def a := foor"\\" sorry "',
            'def a := sf"{sorry}"',
            'def s := s!x',
            'def x := a\'"\' sorry "',
            'def x := \'a"\' sorry "',
            'def x := \'\\a" sorry "\'',
            'def x := \'',
            'def x := \'\\\'',
            'def x := r#',
            'def x := r a',
            'def s := r##"\\" sorry "##\n',
            'def s := s!"prefix \\{sorry\\} {1 + 2} suffix"\n',
            'def s := s!"a {s!"ok"} b"\n',
            'def c := \'\\n\'\ndef c2 := \'a\'\n',
        ):
            audit.static_lean_source_check(ok_lex, "ok_lex")

        forbidden_cases = [
            ("theorem t : False := by sorry", "LEAN4_SORRY"),
            ("theorem t : False := by admit", "LEAN4_ADMIT"),
            ("axiom bogus : False", "LEAN4_AXIOM"),
            ("unsafe def bad : Nat := 0", "LEAN4_UNSAFE"),
            ("theorem t : 1 = 1 := by native_decide", "LEAN4_NATIVE_DECIDE"),
            ("def x := sorryAx", "LEAN4_SORRY_AX"),
            ("def x := Lean.Meta.mkSorry", "LEAN4_MK_SORRY"),
            ("def x := Lean.ofReduceBool", "LEAN4_OF_REDUCE_BOOL"),
            ("def x := Lean.ofReduceNat", "LEAN4_OF_REDUCE_NAT"),
            ("def x := Lean.trustCompiler", "LEAN4_TRUST_COMPILER"),
            ("theorem t : 1 = 1 := by decide +native", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide +revert +native", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide -revert +native", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (revert := true) +native", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := Bool.true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := !false)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := )", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := false) (native := true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native := true })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := (({ native := true })))", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native := false, native := true })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native := false :+ false })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native := false ,+ false })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native := false, extra })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native := false }) +native", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := cfg)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := \u27e8false, true, false, false\u27e9)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := .mk false true false false)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := DecideConfig.mk false true false false)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { c0 with native := false })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { a := { })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { a := } })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { x)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := x })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := ({ native := false }) (x))", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := )", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by \u00abdecide\u00bb +\u00abnative\u00bb", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (\u00abnative\u00bb := true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (\u00abconfig\u00bb := { \u00abnative\u00bb := true })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (\u00abconfig\u00bb := \u00abcfg\u00bb)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : False := by \u00absorry\u00bb", "LEAN4_SORRY"),
            ("theorem t : 1 = 1 := by \u00abnative_decide\u00bb", "LEAN4_NATIVE_DECIDE"),
            ("set_option debug.skipKernelTC true", "LEAN4_SKIP_KERNEL_TC"),
            ('@[extern "c_fn"] def f : Nat := 0', "LEAN4_ATTR_ESCAPE"),
            ("@[implemented_by g] def f : Nat := 0", "LEAN4_ATTR_ESCAPE"),
            ("partial def loop : Nat := loop", "LEAN4_PARTIAL"),
            ("import Mathlib.Data.Nat.Basic", "LEAN4_NON_INIT_IMPORT"),
            ("public import External.Pkg", "LEAN4_NON_INIT_IMPORT"),
        ]
        for bad_src, exp_code in forbidden_cases:
            self._assert_err(exp_code, audit.static_lean_source_check, bad_src, exp_code)

        # Direct span boundary & paren-peel checks for _is_lean4_native_rhs_false_span
        self.assertIs(audit._is_lean4_native_rhs_false_span("", 0, 0), False)
        self.assertIs(audit._is_lean4_native_rhs_false_span("false", 0, 5), True)
        self.assertIs(audit._is_lean4_native_rhs_false_span("  ( ( Bool.false ) )  ", 0, 22), True)
        self.assertIs(audit._is_lean4_native_rhs_false_span("(falsex", 0, 7), False)
        self.assertIs(audit._is_lean4_native_rhs_false_span("xfalse)", 0, 7), False)
        self.assertIs(audit._is_lean4_native_rhs_false_span("(false) || (true)", 0, 17), False)

        # Safe non-native `decide` forms and edge cases must pass cleanly
        safe_cases = [
            "theorem ok : 2 + 2 = 4 := rfl\n",
            "theorem t : 1 = 1 := by decide",
            "theorem t : 1 = 1 := by decide   ",
            ") theorem t : 1 = 1 := by decide (native := false)",
            "theorem t : 1 = 1 := by decide -native",
            "theorem t : 1 = 1 := by decide +kernel",
            "theorem t : 1 = 1 := by decide +",
            "theorem t : 1 = 1 := by decide (foo)",
            "theorem t : 1 = 1 := by decide (",
            "theorem t : 1 = 1 := by decide (kernel := true)",
            "theorem t : 1 = 1 := by decide (native := false)",
            "theorem t : 1 = 1 := by decide (native := ((Bool.false)))",
            "theorem t : 1 = 1 := by decide (config := {})",
            "theorem t : 1 = 1 := by decide (config := { kernel := true })",
            "theorem t : 1 = 1 := by decide (config := { native := false })",
            "theorem t : 1 = 1 := by decide (config := { native := ((Bool.false)), kernel := true })",
            "theorem t : 1 = 1 := by decide (config := { native := false, })",
            "theorem t : 1 = 1 := by decide (config := (({ native := false })))",
            "theorem t : 1 = 1 := by decide (config := { native := \u00abBool\u00bb.\u00abfalse\u00bb })",
            "theorem t : 1 = 1 := by decide (config := { with_flag := true, my_native := true })",
        ]
        for idx, ok_src in enumerate(safe_cases):
            audit.static_lean_source_check(ok_src, f"safe_{idx}")

        # Offline validate_certificate_payload (verify_live_lean=False) rejects decide escapes on disk
        base_cert = _load_disk_cert()
        for inject_line in (
            "theorem forged : 1 = 1 := by decide (native := true)\n",
            "theorem forged : 1 = 1 := by decide (config := { native := true })\n",
            "theorem forged : 1 = 1 := by decide +\u00abnative\u00bb\n",
            "theorem forged : 1 = 1 := by decide (config := cfg)\n",
        ):
            with tempfile.TemporaryDirectory() as td:
                tmp_root = Path(td)
                for fname in ("lean-toolchain", "lakefile.toml"):
                    audit.write_regular_bytes_safe(
                        tmp_root / fname,
                        audit.read_regular_bytes_capped(_TRACK_DIR / fname, fname),
                    )
                tampered_payload = copy.deepcopy(base_cert["payload"])
                for idx, spec in enumerate(audit.MODULE_SPECS):
                    rel = spec["rel_path"]
                    raw = audit.read_regular_bytes_capped(_TRACK_DIR / rel, rel)
                    if idx == 2:
                        raw = raw + inject_line.encode("utf-8")
                        tampered_payload["theorem_modules"][idx]["source_sha256"] = hashlib.sha256(raw).hexdigest()
                        tampered_payload["theorem_modules"][idx]["line_count"] = len(raw.splitlines())
                    audit.write_regular_bytes_safe(tmp_root / rel, raw)
                forged_cert = _rehash_cert(tampered_payload)
                self._assert_err(
                    "LEAN4_DECIDE_NATIVE",
                    audit.validate_certificate_payload,
                    forged_cert,
                    project_root=tmp_root,
                    verify_live_lean=False,
                )

    def test_07_print_axioms_parser_positive_and_negative(self) -> None:
        good_out = (
            "\n"
            "'A.t1' does not depend on any axioms\n"
            "'A.t2' depends on axioms: [propext, Quot.sound]\n"
            "'A.t3' depends on axioms: [propext,\n"
            " Classical.choice,\n"
            " Quot.sound]\n"
        )
        parsed = audit.parse_print_axioms_output(good_out, ("A.t1", "A.t2", "A.t3"))
        self.assertEqual(
            parsed,
            {
                "A.t1": [],
                "A.t2": ["propext", "Quot.sound"],
                "A.t3": ["propext", "Classical.choice", "Quot.sound"],
            },
        )

        self._assert_err("MALFORMED_AXIOM_OUTPUT", audit.parse_print_axioms_output, "'A.t1' depends on axioms: [propext\n", ("A.t1",))
        self._assert_err("UNEXPECTED_LEAN_STDOUT", audit.parse_print_axioms_output, "noise depends on axioms: [propext", ("A.t1",))
        self._assert_err("UNEXPECTED_LEAN_STDOUT", audit.parse_print_axioms_output, "random line", ("A.t1",))
        self._assert_err("EMPTY_AXIOM_BRACKETS", audit.parse_print_axioms_output, "'A.t1' depends on axioms: []", ("A.t1",))
        self._assert_err("FORBIDDEN_LEAN_AXIOM", audit.parse_print_axioms_output, "'A.t1' depends on axioms: [x]", ("A.t1",))
        self._assert_err("MALFORMED_AXIOM_TOKEN", audit.parse_print_axioms_output, "'A.t1' depends on axioms: [propext, ]", ("A.t1",))
        self._assert_err("UNEXPECTED_THEOREM_NAME", audit.parse_print_axioms_output, "'A.other' does not depend on any axioms", ("A.t1",))
        self._assert_err(
            "DUPLICATE_THEOREM_PRINT",
            audit.parse_print_axioms_output,
            "'A.t1' does not depend on any axioms\n'A.t1' does not depend on any axioms",
            ("A.t1",),
        )
        self._assert_err(
            "FORBIDDEN_LEAN_AXIOM",
            audit.parse_print_axioms_output,
            "'A.t1' depends on axioms: [propext, sorryAx]",
            ("A.t1",),
        )
        self._assert_err(
            "FORBIDDEN_LEAN_AXIOM",
            audit.parse_print_axioms_output,
            "'A.t1' depends on axioms: [Lean.ofReduceBool]",
            ("A.t1",),
        )
        self._assert_err(
            "MISSING_THEOREM_PRINT",
            audit.parse_print_axioms_output,
            "'A.t1' does not depend on any axioms",
            ("A.t1", "A.t2"),
        )

    def test_08_resolve_lean_and_version_error_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            missing = str(Path(td) / "no_lean")
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": missing}):
                self._assert_err("LEAN_BINARY_UNAVAILABLE", audit.resolve_lean_binary)
            # Directory (executable bit set, not a file) and non-executable file rejected via ALETHEIA_LEAN_BIN
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": td}):
                self._assert_err("LEAN_BINARY_UNAVAILABLE", audit.resolve_lean_binary)
            non_exec = Path(td) / "non_exec_lean"
            audit.write_regular_bytes_safe(non_exec, b"#!/bin/sh\n")
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(non_exec)}):
                self._assert_err("LEAN_BINARY_UNAVAILABLE", audit.resolve_lean_binary)

            # Fallback when PATH has non-exec lean or no lean, and fake home dir/non-exec/exec checks
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("ALETHEIA_LEAN_BIN", None)
                with mock.patch.object(audit.shutil, "which", return_value=str(non_exec)):
                    with mock.patch.object(audit.Path, "home", return_value=Path(td)):
                        self._assert_err("LEAN_BINARY_UNAVAILABLE", audit.resolve_lean_binary)
                fake_home = Path(td) / "home_dir_lean"
                (fake_home / ".local" / "bin" / "lean").mkdir(parents=True)
                with mock.patch.object(audit.shutil, "which", return_value=None):
                    with mock.patch.object(audit.Path, "home", return_value=fake_home):
                        self._assert_err("LEAN_BINARY_UNAVAILABLE", audit.resolve_lean_binary)
                fake_home2 = Path(td) / "home_nonexec_lean"
                fake_lean2 = fake_home2 / ".local" / "bin" / "lean"
                audit.write_regular_bytes_safe(fake_lean2, b"#!/bin/sh\n")
                with mock.patch.object(audit.shutil, "which", return_value=None):
                    with mock.patch.object(audit.Path, "home", return_value=fake_home2):
                        self._assert_err("LEAN_BINARY_UNAVAILABLE", audit.resolve_lean_binary)
                os.chmod(fake_lean2, 0o700)
                with mock.patch.object(audit.shutil, "which", return_value=None):
                    with mock.patch.object(audit.Path, "home", return_value=fake_home2):
                        self.assertEqual(audit.resolve_lean_binary(), str(fake_lean2))

            # Live binary resolved cleanly
            lean_bin = audit.resolve_lean_binary()
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": lean_bin}):
                self.assertEqual(audit.resolve_lean_binary(), lean_bin)

            # Version failure modes
            self._assert_err("LEAN_EXEC_ERROR", audit.query_lean_version, missing)
            fake_fail = mock.Mock(returncode=1, stdout="", stderr="err")
            with mock.patch.object(audit.subprocess, "run", return_value=fake_fail):
                self._assert_err("LEAN_VERSION_FAILED", audit.query_lean_version, lean_bin)
            fake_badver = mock.Mock(returncode=0, stdout="Lean (version 4.10.0, other)\n", stderr="")
            with mock.patch.object(audit.subprocess, "run", return_value=fake_badver):
                self._assert_err("LEAN_VERSION_MISMATCH", audit.query_lean_version, lean_bin)

            # Toolchain mismatch and invalid UTF-8 toolchain inside build_certificate
            bad_tc_root = Path(td) / "bad_tc"
            audit.write_regular_bytes_safe(bad_tc_root / "lean-toolchain", b"leanprover/lean4:v4.0.0\n")
            with mock.patch.object(audit, "query_lean_version", return_value="Lean (version 4.36.0, test)"):
                self._assert_err("TOOLCHAIN_MISMATCH", audit.build_certificate, bad_tc_root)

            bad_tc_utf8 = Path(td) / "bad_tc_utf8"
            audit.write_regular_bytes_safe(bad_tc_utf8 / "lean-toolchain", b"\xff\xfe\n")
            with mock.patch.object(audit, "query_lean_version", return_value="Lean (version 4.36.0, test)"):
                self._assert_err("INVALID_UTF8_TOOLCHAIN", audit.build_certificate, bad_tc_utf8)

    # ------------------------------------------------------------------
    # 09-12: Pure-Z/Q Math Cross-Checks, Certificate Tampering & CLI Errors
    # ------------------------------------------------------------------

    def test_09_python_exact_cross_checks(self) -> None:
        cross = audit.compute_python_exact_cross_checks()
        self.assertIs(cross["all_five_cross_checks_verified"], True)
        self.assertEqual(cross["theorem1_hamming_f64"]["hamming16_d_min"], 4)
        self.assertEqual(cross["theorem1_hamming_f64"]["hamming16_a4_weight4_count"], 140)
        self.assertEqual(cross["theorem2_block_h2_int8"]["block_h2_max_entry"], 78)
        self.assertEqual(cross["theorem2_block_h2_int8"]["wht8_max_entry"], 156)
        self.assertEqual(cross["theorem3_cs01_blind_window"]["witness_delta_blind"], 2411)
        self.assertEqual(cross["theorem3_cs01_blind_window"]["witness_m_trig"], 3709)
        self.assertEqual(cross["theorem4_cs21_landauer"]["net_cost_ratio_b_over_a_q"], "600/401")
        self.assertEqual(cross["theorem4_cs21_landauer"]["landauer_and_power_product"], 27)
        self.assertEqual(cross["theorem5_polya_fermat_sextic"]["polya_valid_count"], 0)
        self.assertEqual(cross["theorem5_polya_fermat_sextic"]["hodge_f5_singular_affine_count"], 1)

    def test_10_certificate_envelope_and_secondary_audit_tampering(self) -> None:
        cert = _load_disk_cert()
        verdict = audit.validate_certificate_payload(cert, project_root=_TRACK_DIR, verify_live_lean=False)
        self.assertIs(verdict["verified"], True)
        self.assertEqual(verdict["module_count"], 5)
        self.assertEqual(verdict["theorem_count"], 34)

        # Non-dict rejected at _require_exact_keys and non-bool verify_live_lean rejected strictly
        self._assert_err("INVALID_DICT", audit.validate_certificate_payload, [1, 2])
        for bad_flag in (0, 1, "false", None):
            self._assert_err(
                "INVALID_BOOL_TYPE",
                audit.secondary_audit_payload,
                cert["payload"],
                project_root=_TRACK_DIR,
                verify_live_lean=bad_flag,
            )
            self._assert_err(
                "INVALID_BOOL_TYPE",
                audit.validate_certificate_payload,
                cert,
                project_root=_TRACK_DIR,
                verify_live_lean=bad_flag,
            )
            self._assert_err(
                "INVALID_BOOL_TYPE",
                audit.check_certificate_file,
                _CERT_PATH,
                project_root=_TRACK_DIR,
                verify_live_lean=bad_flag,
            )

        # Non-UTF-8 .lean file matching source_sha256 & line_count raises typed INVALID_UTF8_LEAN (never raw UnicodeDecodeError)
        with tempfile.TemporaryDirectory() as td_u:
            u_root = Path(td_u)
            for fname in ("lean-toolchain", "lakefile.toml"):
                audit.write_regular_bytes_safe(
                    u_root / fname,
                    audit.read_regular_bytes_capped(_TRACK_DIR / fname, fname),
                )
            u_payload = copy.deepcopy(cert["payload"])
            for idx, spec in enumerate(audit.MODULE_SPECS):
                rel = spec["rel_path"]
                raw = audit.read_regular_bytes_capped(_TRACK_DIR / rel, rel)
                if idx == 0:
                    raw = b"\xff\xfe\n" * 10
                    u_payload["theorem_modules"][idx]["source_sha256"] = hashlib.sha256(raw).hexdigest()
                    u_payload["theorem_modules"][idx]["line_count"] = 10
                audit.write_regular_bytes_safe(u_root / rel, raw)
            self._assert_err(
                "INVALID_UTF8_LEAN",
                audit.validate_certificate_payload,
                _rehash_cert(u_payload),
                project_root=u_root,
                verify_live_lean=False,
            )

        # Live Lean version drift and live module drift inside secondary_audit_payload
        with mock.patch.object(audit, "resolve_lean_binary", return_value="lean"):
            with mock.patch.object(audit, "query_lean_version", return_value="Lean (version 4.36.0, drift)"):
                self._assert_err(
                    "LEAN_VERSION_DRIFT",
                    audit.secondary_audit_payload,
                    cert["payload"],
                    project_root=_TRACK_DIR,
                    verify_live_lean=True,
                )
            with mock.patch.object(audit, "query_lean_version", return_value=cert["payload"]["lean_version_line"]):
                bad_mod = copy.deepcopy(cert["payload"]["theorem_modules"][0])
                bad_mod["theorem_count"] = 0
                with mock.patch.object(audit, "run_live_lean_module", return_value=bad_mod):
                    self._assert_err(
                        "LIVE_LEAN_DRIFT",
                        audit.secondary_audit_payload,
                        cert["payload"],
                        project_root=_TRACK_DIR,
                        verify_live_lean=True,
                    )

        # Envelope tampering
        bad = copy.deepcopy(cert)
        bad["schema_version"] = "wrong"
        self._assert_err("SCHEMA_MISMATCH", audit.validate_certificate_payload, bad)

        bad = copy.deepcopy(cert)
        bad["track_id"] = "wrong"
        self._assert_err("TRACK_ID_MISMATCH", audit.validate_certificate_payload, bad)

        bad = copy.deepcopy(cert)
        bad["payload_sha256"] = "0" * 64
        self._assert_err("PAYLOAD_HASH_MISMATCH", audit.validate_certificate_payload, bad)

        bad = copy.deepcopy(cert)
        bad["certificate_sha256"] = "0" * 64
        self._assert_err("CERT_HASH_MISMATCH", audit.validate_certificate_payload, bad)

        bad = copy.deepcopy(cert)
        bad["extra"] = 1
        self._assert_err("KEYSET_MISMATCH", audit.validate_certificate_payload, bad)

        # Payload tampering with rehashed valid envelope
        def _tamper(mutator, exp_code: str, *, use_root: bool = False) -> None:
            p = copy.deepcopy(cert["payload"])
            mutator(p)
            c2 = _rehash_cert(p)
            self._assert_err(
                exp_code,
                audit.validate_certificate_payload,
                c2,
                project_root=(_TRACK_DIR if use_root else None),
                verify_live_lean=False,
            )

        _tamper(lambda p: p.__setitem__("track_id", "X"), "TRACK_ID_MISMATCH")
        _tamper(lambda p: p.__setitem__("novelty_class", "N0"), "NOVELTY_MISMATCH")
        _tamper(lambda p: p.__setitem__("oracle_class", "float"), "ORACLE_CLASS_MISMATCH")
        _tamper(lambda p: p.__setitem__("measured_external_mathlib", True), "MATHLIB_FLAG_MISMATCH")
        _tamper(lambda p: p.__setitem__("lean_toolchain", "leanprover/lean4:v4.0.0"), "TOOLCHAIN_MISMATCH")
        _tamper(lambda p: p.__setitem__("lean_version_line", "Lean (version 4.0.0)"), "LEAN_VERSION_MISMATCH")
        _tamper(lambda p: p["portals_covered"].pop(), "PORTALS_MISMATCH")
        _tamper(lambda p: p["prior_literature_n0"].pop(), "LIT_MISMATCH")
        _tamper(lambda p: p["project_manifest"].__setitem__("module_count", 4), "MODULE_COUNT_MISMATCH")
        _tamper(lambda p: p["project_manifest"].__setitem__("total_theorem_count", 33), "THEOREM_COUNT_MISMATCH")
        _tamper(lambda p: p["project_manifest"].__setitem__("lean_toolchain_sha256", "0" * 64), "TOOLCHAIN_SHA_MISMATCH", use_root=True)
        _tamper(lambda p: p["project_manifest"].__setitem__("lakefile_sha256", "0" * 64), "LAKEFILE_SHA_MISMATCH", use_root=True)
        _tamper(lambda p: p["theorem_modules"].pop(), "MODULE_LIST_MISMATCH")
        _tamper(lambda p: p.__setitem__("theorem_modules", "12345"), "MODULE_LIST_MISMATCH")
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("module_id", "BAD"), "MODULE_ID_MISMATCH")
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("portal_ref", "BAD"), "PORTAL_REF_MISMATCH")
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("rel_path", "BAD.lean"), "REL_PATH_MISMATCH")
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("source_sha256", "0" * 64), "LEAN_SOURCE_SHA_MISMATCH", use_root=True)
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("line_count", 999), "LEAN_LINE_COUNT_MISMATCH", use_root=True)
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("theorem_count", 8), "MOD_THEOREM_COUNT")
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("static_envelope_clean", False), "STATIC_ENVELOPE_FLAG")
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("kernel_exit_code", 1), "KERNEL_EXIT_NONZERO")
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("zero_warnings", False), "WARNINGS_FLAG")
        _tamper(lambda p: p["theorem_modules"][0]["theorems"].pop(), "THEOREMS_LIST_MISMATCH")
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("theorems", "123456789"), "THEOREMS_LIST_MISMATCH")
        _tamper(lambda p: p["theorem_modules"][0]["theorems"][0].__setitem__("name", "bad"), "THEOREM_NAME_MISMATCH")
        _tamper(lambda p: p["theorem_modules"][0]["theorems"][0].__setitem__("standard_axioms_only", False), "THEOREM_AXIOM_FLAG")
        _tamper(lambda p: p["theorem_modules"][0]["theorems"][0].__setitem__("axioms", ["a", "b", "c", "d"]), "AXIOM_LIST_INVALID")
        _tamper(lambda p: p["theorem_modules"][0]["theorems"][0].__setitem__("axioms", "ab"), "AXIOM_LIST_INVALID")
        _tamper(lambda p: p["theorem_modules"][0]["theorems"][0].__setitem__("axioms", ["sorryAx"]), "FORBIDDEN_LEAN_AXIOM")
        _tamper(lambda p: p["theorem_modules"][0]["theorems"][0].__setitem__("axioms", ["propext", "propext"]), "DUPLICATE_AXIOM")
        _tamper(lambda p: p["theorem_modules"][0]["theorems"][0].__setitem__("axioms", ["propext"]), "AXIOM_SET_MISMATCH")
        _tamper(lambda p: p["python_exact_cross_checks"]["theorem1_hamming_f64"].__setitem__("hamming16_d_min", 3), "CROSS_CHECK_MISMATCH")
        _tamper(lambda p: p["python_exact_cross_checks"]["theorem3_cs01_blind_window"].__setitem__("legacy_threshold_q", "14/40"), "NON_REDUCED_RATIONAL")
        _tamper(lambda p: p["python_exact_cross_checks"]["theorem4_cs21_landauer"].__setitem__("landauer_lower_q", "38/32"), "NON_REDUCED_RATIONAL")
        _tamper(lambda p: p["summary"].__setitem__("module_count", 4), "SUMMARY_MODULE_COUNT")
        _tamper(lambda p: p["summary"].__setitem__("theorem_count", 33), "SUMMARY_THEOREM_COUNT")
        _tamper(lambda p: p["summary"].__setitem__("zero_warning_modules", 4), "SUMMARY_ZERO_WARNINGS")
        _tamper(lambda p: p["summary"].__setitem__("forbidden_axiom_count", 1), "SUMMARY_FORBIDDEN_AXIOMS")
        _tamper(lambda p: p["summary"].__setitem__("all_five_modules_kernel_checked", False), "SUMMARY_KERNEL_FLAG")
        _tamper(lambda p: p["summary"].__setitem__("all_theorems_standard_axioms_only", False), "SUMMARY_AXIOM_FLAG")
        _tamper(lambda p: p["summary"].__setitem__("float_count_on_trust_path", 1), "SUMMARY_FLOATS")
        _tamper(lambda p: p["summary"].__setitem__("bare_assert_count", 1), "SUMMARY_ASSERTS")
        _tamper(lambda p: p["summary"].__setitem__("rng_calls", 1), "SUMMARY_RNG")

        # Bool-leaf bijection tamper checks
        _tamper(lambda p: p.__setitem__("measured_external_mathlib", 0), "INVALID_BOOL_TYPE")
        _tamper(lambda p: p["summary"].__setitem__("rng_calls", False), "UNEXPECTED_BOOL_LEAF")
        _tamper(lambda p: p["portals_covered"].__setitem__(0, True), "UNEXPECTED_BOOL_ITEM")

    def test_11_cli_error_paths_and_check_file_utf8(self) -> None:
        with mock.patch.object(audit, "build_certificate", side_effect=RuntimeError("must_not_build")):
            for bad_argv in (
                ["--bogus"],
                ["--write"],
                ["--bogus", "x"],
                ["--check"],
                ["--write", "--json"],
                ["--write", "-x"],
                ["--write", ""],
                ["--check", "--json"],
                ["--check", "-x"],
                ["--check", ""],
                123,
                "--check",
                ["--check", 123],
                ["--write", None],
                [_StrSub("--check"), "x"],
            ):
                buf_err = io.StringIO()
                with mock.patch.object(sys, "stderr", buf_err):
                    rc = audit.main(bad_argv)
                self.assertEqual(rc, 2)
                self.assertIn("INVALID_CLI_ARGS", buf_err.getvalue())

            buf_nul = io.StringIO()
            with mock.patch.object(sys, "stderr", buf_nul):
                rc_nul = audit.main(["--write", "a\x00b"])
            self.assertEqual(rc_nul, 2)
            self.assertIn("NUL_BYTE_FORBIDDEN", buf_nul.getvalue())

            buf_sys = io.StringIO()
            with mock.patch.object(sys, "argv", ["prog", "--bogus"]):
                with mock.patch.object(sys, "stderr", buf_sys):
                    rc_sys = audit.main(None)
            self.assertEqual(rc_sys, 2)
            self.assertIn("INVALID_CLI_ARGS", buf_sys.getvalue())

        # Single-char path passes CLI target validation and reaches FILE_READ_ERROR
        orig_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as td:
            try:
                os.chdir(td)
                buf_1c = io.StringIO()
                with mock.patch.object(sys, "stderr", buf_1c):
                    rc_1c = audit.main(["--check", "x"])
                self.assertEqual(rc_1c, 2)
                self.assertIn("FILE_READ_ERROR", buf_1c.getvalue())
                self.assertEqual(list(Path(td).iterdir()), [])
            finally:
                os.chdir(orig_cwd)

        with tempfile.TemporaryDirectory() as td:
            bad_utf8 = Path(td) / "bad.json"
            audit.write_regular_bytes_safe(bad_utf8, b"\xff\xfe\xfd")
            self._assert_err("INVALID_UTF8_JSON", audit.check_certificate_file, bad_utf8, verify_live_lean=False)

            bad_json = Path(td) / "bad_syntax.json"
            audit.write_regular_bytes_safe(bad_json, b'{"x": 1.5}')
            buf_err2 = io.StringIO()
            with mock.patch.object(sys, "stderr", buf_err2):
                rc2 = audit.main(("--check", str(bad_json)))
            self.assertEqual(rc2, 2)
            self.assertIn("FLOAT_FORBIDDEN", buf_err2.getvalue())

            # Non-canonical CRLF and pretty-printed certificate bytes rejected cleanly
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
            # 1. Invalid UTF-8
            bad_u = root / "BadUtf8.lean"
            audit.write_regular_bytes_safe(bad_u, b"\xff\xfe")
            self._assert_err(
                "INVALID_UTF8_LEAN",
                audit.run_live_lean_module,
                lean_bin, root, "BadUtf8.lean", ("T.t",), "M_U", "P",
            )
            # 2. Static sorry rejected BEFORE Lean exec
            bad_sorry = root / "BadSorry.lean"
            audit.write_regular_bytes_safe(bad_sorry, b"theorem t : False := by sorry\n")
            self._assert_err(
                "LEAN4_SORRY",
                audit.run_live_lean_module,
                lean_bin, root, "BadSorry.lean", ("t",), "M_S", "P",
            )
            # 3. Genuine live Lean type error -> LEAN_KERNEL_REJECTED
            bad_type = root / "BadType.lean"
            audit.write_regular_bytes_safe(bad_type, b"theorem bad : 1 = 2 := by decide\n")
            self._assert_err(
                "LEAN_KERNEL_REJECTED",
                audit.run_live_lean_module,
                lean_bin, root, "BadType.lean", ("bad",), "M_T", "P",
            )
            # 4. Genuine live Lean compiler warning -> LEAN_WARNING_FORBIDDEN
            bad_warn = root / "BadWarn.lean"
            audit.write_regular_bytes_safe(
                bad_warn,
                b"theorem w (unused_x : Nat) : 1 = 1 := rfl\n#print axioms w\n",
            )
            self._assert_err(
                "LEAN_WARNING_FORBIDDEN",
                audit.run_live_lean_module,
                lean_bin, root, "BadWarn.lean", ("w",), "M_W", "P",
            )
            # 5. Live Lean exec failure / stderr failure (mocked cleanly)
            good_min = root / "GoodMin.lean"
            audit.write_regular_bytes_safe(
                good_min,
                b"theorem ok : 2 + 2 = 4 := rfl\n#print axioms ok\n",
            )
            with mock.patch.object(audit.subprocess, "run", side_effect=OSError("boom")):
                self._assert_err(
                    "LEAN_EXEC_ERROR",
                    audit.run_live_lean_module,
                    lean_bin, root, "GoodMin.lean", ("ok",), "M_E", "P",
                )
            with mock.patch.object(audit.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="", stderr="err")):
                self._assert_err(
                    "LEAN_STDERR_NONEMPTY",
                    audit.run_live_lean_module,
                    lean_bin, root, "GoodMin.lean", ("ok",), "M_SE", "P",
                )
            # 6. Genuine live Lean compilation of minimal theorem succeeds
            res = audit.run_live_lean_module(lean_bin, root, "GoodMin.lean", ("ok",), "M_OK", "P")
            self.assertEqual(res["kernel_exit_code"], 0)
            self.assertEqual(res["theorems"], [{"name": "ok", "axioms": [], "standard_axioms_only": True}])

    def test_95_live_lean_full_bridge_and_cli_parity(self) -> None:
        # Live Lean 4.36.0 build across all 5 modules & 34 theorems matches disk certificate byte-for-byte
        live_cert = audit.build_certificate(_TRACK_DIR)
        disk_raw = audit.read_regular_bytes_capped(_CERT_PATH, "disk_cert")
        self.assertEqual(audit.canonical_json_bytes(live_cert) + b"\n", disk_raw)

        # Live --check verifies disk certificate + disk files + live Lean kernel
        out_check = io.StringIO()
        with mock.patch.object(sys, "stdout", out_check):
            rc = audit.main(["--check", str(_CERT_PATH)])
        self.assertEqual(rc, 0)
        chk = audit.parse_strict_json_text(out_check.getvalue())
        self.assertIs(chk["verified"], True)
        self.assertEqual(chk["theorem_count"], 34)

        # Zero-arg summary, --standalone --json, and --write CLI paths (avoid repeating 5-module build 3x by mocking build_certificate ONLY for CLI formatting dispatch, after already executing live build_certificate + live --check above)
        with mock.patch.object(audit, "build_certificate", return_value=live_cert):
            out_sum = io.StringIO()
            with mock.patch.object(sys, "stdout", out_sum):
                self.assertEqual(audit.main([]), 0)
            self.assertEqual(audit.parse_strict_json_text(out_sum.getvalue())["theorem_count"], 34)

            out_st = io.StringIO()
            with mock.patch.object(sys, "stdout", out_st):
                self.assertEqual(audit.main(["--standalone", "--json"]), 0)
            self.assertEqual(out_st.getvalue().encode("utf-8"), disk_raw)

            with tempfile.TemporaryDirectory() as td:
                out_p = Path(td) / "written_cert.json"
                out_w = io.StringIO()
                with mock.patch.object(sys, "stdout", out_w):
                    self.assertEqual(audit.main(["--write", str(out_p)]), 0)
                self.assertEqual(audit.read_regular_bytes_capped(out_p), disk_raw)


if __name__ == "__main__":
    unittest.main()
