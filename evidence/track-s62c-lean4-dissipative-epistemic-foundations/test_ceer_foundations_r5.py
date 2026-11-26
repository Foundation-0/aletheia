#!/usr/bin/env python3
"""Track S62c R1-R5 Adversarial, Zone-B, Darwin-Prefix, Pure-Z/Q & Live Lean 4.36.0 Test Suite.

Zero bare asserts, zero AST floats / float(), zero .isdigit(), zero islink/is_symlink,
zero character-device writes (scratch os.mkfifo only), zero CodeQL secret* variable names.
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

import ceer_foundations_audit as audit  # noqa: E402

_TRACK_DIR = Path(__file__).resolve().parent
_CERT_PATH = _TRACK_DIR / "ceer_foundations_certificate.json"


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


class TestTrackS62cCeerFoundationsR5(unittest.TestCase):
    """Fast deterministic & adversarial tests first (01-11), live Lean 4.36.0 last (90-95)."""

    def _assert_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(audit.CeerFoundationsError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    # ------------------------------------------------------------------
    # 01-03: Exact Type, Integer, Rational & Strict JSON Primitives
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

        ok_nested: list = []
        cur = ok_nested
        for _ in range(audit.MAX_JSON_DEPTH):
            nxt: list = []
            cur.append(nxt)
            cur = nxt
        audit._validate_json_tree(ok_nested)
        cur.append([])
        self._assert_err("JSON_DEPTH_LIMIT", audit._validate_json_tree, ok_nested)

        audit._validate_json_tree([0] * (audit.MAX_JSON_NODES - 1))
        self._assert_err("JSON_NODE_LIMIT", audit._validate_json_tree, [0] * audit.MAX_JSON_NODES)

        runtime_float = json.loads("1.25")
        self._assert_err("FLOAT_FORBIDDEN", audit.canonical_json_bytes, {"x": runtime_float})
        self._assert_err("INVALID_JSON_TYPE", audit.canonical_json_bytes, _DictSub({"a": 1}))
        self._assert_err("INVALID_JSON_TYPE", audit.canonical_json_bytes, {"a": _ListSub([1])})
        self._assert_err("INVALID_JSON_TYPE", audit.canonical_json_bytes, {"a": _IntSub(1)})
        self._assert_err("INVALID_JSON_TYPE", audit.canonical_json_bytes, {"a": _StrSub("x")})
        self._assert_err("INVALID_JSON_TYPE", audit.canonical_json_bytes, {"a": (1, 2)})
        self._assert_err("INVALID_STR", audit.canonical_json_bytes, {1: "a"})

    # ------------------------------------------------------------------
    # 04-05: Zone-B Filesystem Security, Darwin Prefix, Scratch FIFO & Races
    # ------------------------------------------------------------------

    def test_04_zone_b_read_write_symlinks_fifo_caps(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            self._assert_err("INVALID_PATH_TYPE", audit.read_regular_bytes_capped, str(base / "a"))
            self._assert_err("INVALID_PATH_TYPE", audit.read_regular_bytes_capped, _PathSub(base / "a"))
            self._assert_err("INVALID_UTF8_SURROGATE", audit.read_regular_bytes_capped, base / "bad_\ud800.json")
            self._assert_err("INVALID_LEAF_NAME", audit.read_regular_bytes_capped, Path("/"))
            self._assert_err("INVALID_LEAF_NAME", audit.read_regular_bytes_capped, base / "..")

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

            hl_target = base / "hl_target"
            os.link(nested, hl_target)
            self._assert_err("HARDLINK_FORBIDDEN", audit.read_regular_bytes_capped, hl_target)
            with mock.patch.object(audit.secrets, "token_hex", side_effect=RuntimeError("temp_opened_early")):
                self._assert_err("HARDLINK_FORBIDDEN", audit.write_regular_bytes_safe, hl_target, b"x")
            os.unlink(hl_target)

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

            if hasattr(os, "mkfifo"):
                fifo_p = base / "scratch.fifo"
                os.mkfifo(fifo_p, 0o600)
                self._assert_err("NOT_A_REGULAR_FILE", audit.read_regular_bytes_capped, fifo_p)
                self._assert_err("NOT_A_REGULAR_FILE", audit.write_regular_bytes_safe, fifo_p, b"x")

            # Wrapped OSError paths (mkdir, reopen-after-mkdir, read, lstat, temp-open, write, re-lstat, replace)
            with mock.patch.object(audit.os, "mkdir", side_effect=PermissionError("no")):
                with self.assertRaises(audit.CeerFoundationsError) as cm_mk:
                    audit.write_regular_bytes_safe(base / "new_ro_dir" / "f", b"x")
                self.assertEqual(cm_mk.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("mkdir failed", str(cm_mk.exception))
            real_open = os.open

            def _fail_reopen_after_mkdir(p_arg, flags, *oargs, **okwargs):
                if p_arg == "reopen_fail_dir":
                    raise FileNotFoundError(errno.ENOENT, "gone", p_arg)
                return real_open(p_arg, flags, *oargs, **okwargs)

            with mock.patch.object(audit.os, "open", side_effect=_fail_reopen_after_mkdir):
                self._assert_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, base / "reopen_fail_dir" / "f", b"x")
            with mock.patch.object(audit.os, "read", side_effect=OSError("io")):
                self._assert_err("FILE_READ_ERROR", audit.read_regular_bytes_capped, nested)
            with mock.patch.object(audit.os, "lstat", side_effect=PermissionError("no")):
                self._assert_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, race_target, b"x")
            relstat_calls = {"n": 0}

            def _fail_second_lstat(name, dir_fd=None):
                relstat_calls["n"] += 1
                if relstat_calls["n"] == 1:
                    raise FileNotFoundError(name)
                raise PermissionError("re-lstat denied")

            with mock.patch.object(audit.os, "lstat", side_effect=_fail_second_lstat):
                self._assert_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, race_target, b"x")

            tmp_open_calls = {"n": 0}

            def _fail_tmp_open(p_arg, flags, *oargs, **okwargs):
                if isinstance(p_arg, str) and p_arg.startswith(".s62c."):
                    tmp_open_calls["n"] += 1
                    raise PermissionError("no tmp")
                return real_open(p_arg, flags, *oargs, **okwargs)

            with mock.patch.object(audit.os, "open", side_effect=_fail_tmp_open):
                with self.assertRaises(audit.CeerFoundationsError) as cm_tmp:
                    audit.write_regular_bytes_safe(race_target, b"x")
                self.assertEqual(cm_tmp.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("create temp failed", str(cm_tmp.exception))
                self.assertEqual(tmp_open_calls["n"], 1)
            with mock.patch.object(audit.os, "write", side_effect=OSError("disk full")):
                self._assert_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, race_target, b"x")
            with mock.patch.object(audit.os, "replace", side_effect=OSError("exdev")):
                self._assert_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, race_target, b"x")

    def test_05_zone_b_relative_pwd_darwin_prefix_and_concurrency(self) -> None:
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
                    self.assertEqual(
                        audit._normalize_darwin_system_prefix(("var", "f")),
                        ("private", "var", "f"),
                    )

            with mock.patch.object(audit.os, "lstat", side_effect=[st_dir_root, st_dir_root]):
                with mock.patch.object(audit.os, "readlink", return_value="private/tmp"):
                    self.assertEqual(audit._normalize_darwin_system_prefix(("tmp", "a")), ("tmp", "a"))
            with mock.patch.object(audit.os, "lstat", side_effect=[st_lnk_user, st_dir_root]):
                with mock.patch.object(audit.os, "readlink", return_value="private/tmp"):
                    self.assertEqual(audit._normalize_darwin_system_prefix(("tmp", "a")), ("tmp", "a"))
            with mock.patch.object(audit.os, "lstat", side_effect=[st_lnk_root, st_dir_root]):
                with mock.patch.object(audit.os, "readlink", return_value="evil/tmp"):
                    self.assertEqual(audit._normalize_darwin_system_prefix(("tmp", "a")), ("tmp", "a"))
            with mock.patch.object(audit.os, "lstat", side_effect=[st_lnk_root, st_reg_root]):
                with mock.patch.object(audit.os, "readlink", return_value="private/etc"):
                    self.assertEqual(audit._normalize_darwin_system_prefix(("etc", "a")), ("etc", "a"))
            with mock.patch.object(audit.os, "lstat", side_effect=[st_lnk_root, st_dir_user]):
                with mock.patch.object(audit.os, "readlink", return_value="private/etc"):
                    self.assertEqual(audit._normalize_darwin_system_prefix(("etc", "a")), ("etc", "a"))
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

                with mock.patch.object(audit.os, "environ", {"PWD": "/tmp/surr_\ud800"}):
                    self._assert_err("INVALID_UTF8_SURROGATE", audit.read_regular_bytes_capped, Path("rel_out.json"))

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
            'def s : String := "sorry \\"admit\\"\\n"\n'
            'def rs0 : String := r"sorry\nadmit"\n'
            'def rs1 : String := r#"sorry"admit"#\n'
            'def red : Nat := 1\n'
            'def div_ok : Nat := 6 / 2\n'
            'def ar_ok := ar"\\" sorry \\""\n'
            'def _r_ok := _r"\\" sorry \\""\n'
            'def si0 := s!"hello { 1 + 2 } sorry \\{ sorry } \\n world"\n'
            'def si1 := m!"{ { a := 1 } }"\n'
            'def si2 := f!"{ "}" }"\n'
            'def s_emp := s""\n'
            'def s_sp := s! 1\n'
            'def x_bang := x!"{ sorry }"\n'
            'def as_bang := as!"{ sorry }"\n'
            "def ch0 : Char := 'a'\n"
            "def ch1 : Char := '\"'\n"
            "def ch2 : Char := '\\\"'\n"
            "def ch3 : Char := '\\''\n"
            "def ch4 : Char := '\\\\'\n"
            "def ch_prime (x' : Char -> Nat) := x' '\"'\n"
            'def ch_esc_noq := \'\\"sorry"\'\n'
            'def ch_no_bs := \'a"\' sorry "\n'
            'def ch_no_q := \'a"sorry"\n'
            "import Init.Data.Nat.Basic\n"
            "import Std\n"
            "def f0 := ) + 1\n"
            "def safeCfg : DecideConfig := { native := false }\n"
            "def safeCfg2 := ({ native := (Bool.false) } : DecideConfig)\n"
            "theorem t0 : 2 - 1 = 1 := by decide +revert (native := ( false )) (config := (({ native := false })))\n"
            "theorem t0b : 1 = 1 := by decide (config := {})\n"
            "theorem t1 : 1 = 1 := by decide\n"
            "def f1 := decide (foo) + 1\n"
            "def f2 := decide +\n"
            "def f3 := decide (unclosed\n"
            "-- trailing eof comment without newline"
        )
        audit.static_lean_source_check(clean_src, "clean")
        audit.static_lean_source_check("def ch_prime (x' : Char -> Nat) := x' '\"'", "ch_prime")
        audit.static_lean_source_check('!"{ sorry }"\n-- s', "bang_at_zero")
        audit.static_lean_source_check("def r_eof := r#", "r_eof")
        audit.static_lean_source_check("def c_eof1 := '", "c_eof1")
        audit.static_lean_source_check("def c_eof2 := '\\", "c_eof2")
        self.assertIs(audit._is_lean4_native_rhs_false("(falsex"), False)
        self.assertIs(audit._is_lean4_native_rhs_false("xfalse)"), False)
        self.assertIs(audit._is_lean4_native_rhs_false("((false))"), True)

        self._assert_err("LEAN4_UNTERMINATED_COMMENT", audit.static_lean_source_check, "/- unclosed", "u1")
        self._assert_err("LEAN4_UNTERMINATED_STRING", audit.static_lean_source_check, 'def x := "unclosed', "u2")
        self._assert_err("LEAN4_UNTERMINATED_STRING", audit.static_lean_source_check, 'def x := "abc\\', "u3")
        self._assert_err("LEAN4_UNTERMINATED_STRING", audit.static_lean_source_check, 'def x := r"unclosed', "u4")
        self._assert_err("LEAN4_UNTERMINATED_STRING", audit.static_lean_source_check, 'def x := r#"unclosed"', "u5")
        self._assert_err("LEAN4_UNTERMINATED_STRING", audit.static_lean_source_check, 'def x := s!"unclosed', "u6")
        self._assert_err("LEAN4_UNTERMINATED_STRING", audit.static_lean_source_check, 'def x := s!"unclosed\\', "u7")
        self._assert_err("LEAN4_UNTERMINATED_STRING", audit.static_lean_source_check, 'def x := s!"{ 1', "u8")
        self._assert_err("LEAN4_SORRY", audit.static_lean_source_check, "theorem t : 2 - 1 = 1 := by sorry\n", "sub_sorry")
        self._assert_err("LEAN4_SORRY", audit.static_lean_source_check, "-- ok\ntheorem t : False := by sorry\n", "after_line_comment")

        forbidden_cases = [
            ("theorem t : False := by sorry", "LEAN4_SORRY"),
            ("def _q1 : Char := '\"'\nset_option debug.skipKernelTC true\ndef _q2 : Char := '\"'", "LEAN4_SKIP_KERNEL_TC"),
            ("def q1 : Char := '\"'\ntheorem evil : False := by sorry\ndef q2 : Char := '\"'", "LEAN4_SORRY"),
            ('r"\\"\ntheorem evil : False := by sorry\n-- "x', "LEAN4_SORRY"),
            ('def r1 : String := r#"\\"#\ntheorem evil : False := by sorry\n-- "', "LEAN4_SORRY"),
            ('def s : String := s!"{ (by sorry : Nat) }"', "LEAN4_SORRY"),
            ('def s : String := s!"{ (by decide +native : (1 : Nat) = 1) }"', "LEAN4_DECIDE_NATIVE"),
            ('def s : String := s!"\\\\{ (by sorry : Nat) }"', "LEAN4_SORRY"),
            ("theorem t : False := by admit", "LEAN4_ADMIT"),
            ("axiom bogus : False", "LEAN4_AXIOM"),
            ("unsafe def bad : Nat := 0", "LEAN4_UNSAFE"),
            ("theorem t : 1 = 1 := by native_decide", "LEAN4_NATIVE_DECIDE"),
            ("def x := sorryAx", "LEAN4_SORRY_AX"),
            ("def x := Lean.ofReduceBool", "LEAN4_OF_REDUCE_BOOL"),
            ("def x := Lean.trustCompiler", "LEAN4_TRUST_COMPILER"),
            ("theorem t : 1 = 1 := by decide +native", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide +revert +native", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native := true })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native := false :+ true })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native := false ,+ true })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { revert := true }) +native", "LEAN4_DECIDE_NATIVE"),
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
            ("theorem t : 1 = 1 := by decide (config := { a := 1)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := a := 1 })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := )", "LEAN4_DECIDE_NATIVE"),
            ("def cfg : DecideConfig := { native := true }", "LEAN4_DECIDE_NATIVE"),
            ("def cfg := { native := true } : Decide.Config", "LEAN4_DECIDE_NATIVE"),
            ("set_option debug.skipKernelTC true", "LEAN4_SKIP_KERNEL_TC"),
            ('@[extern "c_fn"] def f : Nat := 0', "LEAN4_ATTR_ESCAPE"),
            ("@[implemented_by g] def f : Nat := 0", "LEAN4_ATTR_ESCAPE"),
            ("partial def loop : Nat := loop", "LEAN4_PARTIAL"),
            ("import Mathlib.Data.Nat.Basic", "LEAN4_NON_INIT_IMPORT"),
            ("public import External.Pkg", "LEAN4_NON_INIT_IMPORT"),
        ]
        for bad_src, exp_code in forbidden_cases:
            self._assert_err(exp_code, audit.static_lean_source_check, bad_src, exp_code)

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
                with mock.patch.object(audit.shutil, "which", return_value=None):
                    with mock.patch.object(audit.Path, "home", side_effect=RuntimeError("no home")):
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

            lean_bin = audit.resolve_lean_binary()
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": lean_bin}):
                self.assertEqual(audit.resolve_lean_binary(), lean_bin)

            self._assert_err("LEAN_EXEC_ERROR", audit.query_lean_version, missing)
            fake_fail = mock.Mock(returncode=1, stdout="", stderr="err")
            with mock.patch.object(audit.subprocess, "run", return_value=fake_fail):
                self._assert_err("LEAN_VERSION_FAILED", audit.query_lean_version, lean_bin)
            fake_badver = mock.Mock(returncode=0, stdout="Lean (version 4.10.0, other)\n", stderr="")
            with mock.patch.object(audit.subprocess, "run", return_value=fake_badver):
                self._assert_err("LEAN_VERSION_MISMATCH", audit.query_lean_version, lean_bin)

            bad_tc_root = Path(td) / "bad_tc"
            audit.write_regular_bytes_safe(bad_tc_root / "lean-toolchain", b"leanprover/lean4:v4.0.0\n")
            with mock.patch.object(audit, "query_lean_version", return_value="Lean (version 4.36.0, test)"):
                self._assert_err("TOOLCHAIN_MISMATCH", audit.build_certificate, bad_tc_root)
                audit.write_regular_bytes_safe(bad_tc_root / "lean-toolchain", b"\xff\xfe\n")
                self._assert_err("INVALID_UTF8_TOOLCHAIN", audit.build_certificate, bad_tc_root)

    # ------------------------------------------------------------------
    # 09-11: Pure-Z/Q CEER Cross-Checks, Tampering & CLI Errors
    # ------------------------------------------------------------------

    def test_09_python_exact_cross_checks(self) -> None:
        cross = audit.compute_python_exact_cross_checks()
        self.assertIs(cross["all_three_cross_checks_verified"], True)

        m1 = cross["module1_hysteresis_concavity_cliff"]
        self.assertEqual(m1["memoryless_quadratic_loop_area"], 0)
        self.assertEqual(m1["memoryless_cubic_loop_area"], 0)
        self.assertEqual(m1["affine_asymmetric_loop_area"], 0)
        self.assertEqual(m1["thermal_hysteresis_loop_area"], -250)
        self.assertEqual(m1["concave_second_diff"], -50)
        self.assertEqual(m1["concave_slope_12_q"], "8")
        self.assertEqual(m1["concave_slope_23_q"], "14/3")
        self.assertEqual(m1["cliff_slope_q"], "45")

        m2 = cross["module2_schur_dark_mode_gauge"]
        self.assertEqual(m2["sensor_det_d"], 16)
        self.assertEqual(m2["stage0_variance_q"], "100")
        self.assertEqual(m2["stage1_variance_q"], "64")
        self.assertEqual(m2["stage2_variance_q"], "60")
        self.assertEqual(m2["stage1_eta_q"], "16/25")
        self.assertEqual(m2["stage2_eta_q"], "3/5")
        self.assertEqual(m2["nested_identity_lhs"], 3840)
        self.assertEqual(m2["nested_identity_rhs"], 3840)
        self.assertEqual(m2["gauge_scale_factor_k"], 1225)
        self.assertEqual(m2["eta_raw_q"], m2["eta_transformed_q"])

        m3 = cross["module3_laplacian_thermal_coupling"]
        self.assertEqual(m3["greens_col8"], [10923, 5462, 2732, 1368, 688, 352, 192, 128])
        self.assertEqual(m3["greens_q8"], 21845)
        self.assertIs(m3["energy_conservation_exact"], True)
        self.assertIs(m3["strict_monotonicity_exact"], True)
        self.assertIs(m3["strict_flux_decay_exact"], True)
        self.assertEqual(m3["ratio_t1_over_t7_q"], "2731/64")
        self.assertIs(m3["heatpipe_refutes_isotropic"], True)

    def test_10_certificate_envelope_and_secondary_audit_tampering(self) -> None:
        cert = _load_disk_cert()
        verdict = audit.validate_certificate_payload(cert, project_root=_TRACK_DIR, verify_live_lean=False)
        self.assertIs(verdict["verified"], True)
        self.assertEqual(verdict["module_count"], 3)
        self.assertEqual(verdict["theorem_count"], 24)

        self._assert_err("INVALID_DICT", audit.validate_certificate_payload, [1, 2])
        self._assert_err("INVALID_BOOL_TYPE", audit.secondary_audit_payload, cert["payload"], verify_live_lean=0)
        self._assert_err("INVALID_BOOL_TYPE", audit.secondary_audit_payload, cert["payload"], verify_live_lean="false")
        self._assert_err("INVALID_BOOL_TYPE", audit.validate_certificate_payload, {"bad": 1}, verify_live_lean=0)
        self._assert_err("INVALID_BOOL_TYPE", audit.check_certificate_file, Path("/nonexistent.json"), verify_live_lean=0)

        with tempfile.TemporaryDirectory() as td:
            bad_root = Path(td)
            tc_raw = audit.read_regular_bytes_capped(_TRACK_DIR / "lean-toolchain", "tc")
            lk_raw = audit.read_regular_bytes_capped(_TRACK_DIR / "lakefile.toml", "lk")
            audit.write_regular_bytes_safe(bad_root / "lean-toolchain", tc_raw)
            audit.write_regular_bytes_safe(bad_root / "lakefile.toml", lk_raw)
            bad_lean_bytes = b"\xff\xfe\n" * 10
            m0_rel = audit.MODULE_SPECS[0]["rel_path"]
            audit.write_regular_bytes_safe(bad_root / m0_rel, bad_lean_bytes)
            p_utf8 = copy.deepcopy(cert["payload"])
            p_utf8["theorem_modules"][0]["source_sha256"] = hashlib.sha256(bad_lean_bytes).hexdigest()
            p_utf8["theorem_modules"][0]["line_count"] = 10
            self._assert_err(
                "INVALID_UTF8_LEAN",
                audit.secondary_audit_payload,
                p_utf8,
                project_root=bad_root,
                verify_live_lean=False,
            )

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
        _tamper(lambda p: p["ceer_pillars_covered"].pop(), "PILLARS_MISMATCH")
        _tamper(lambda p: p["prior_literature_n0"].pop(), "LIT_MISMATCH")
        _tamper(lambda p: p["project_manifest"].__setitem__("module_count", 2), "MODULE_COUNT_MISMATCH")
        _tamper(lambda p: p["project_manifest"].__setitem__("total_theorem_count", 23), "THEOREM_COUNT_MISMATCH")
        _tamper(lambda p: p["project_manifest"].__setitem__("lean_toolchain_sha256", "0" * 64), "TOOLCHAIN_SHA_MISMATCH", use_root=True)
        _tamper(lambda p: p["project_manifest"].__setitem__("lakefile_sha256", "0" * 64), "LAKEFILE_SHA_MISMATCH", use_root=True)
        _tamper(lambda p: p["theorem_modules"].pop(), "MODULE_LIST_MISMATCH")
        _tamper(lambda p: p.__setitem__("theorem_modules", "123"), "MODULE_LIST_MISMATCH")
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("module_id", "BAD"), "MODULE_ID_MISMATCH")
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("pillar_ref", "BAD"), "PILLAR_REF_MISMATCH")
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("rel_path", "BAD.lean"), "REL_PATH_MISMATCH")
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("source_sha256", "0" * 64), "LEAN_SOURCE_SHA_MISMATCH", use_root=True)
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("line_count", 999), "LEAN_LINE_COUNT_MISMATCH", use_root=True)
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("theorem_count", 7), "MOD_THEOREM_COUNT")
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("static_envelope_clean", False), "STATIC_ENVELOPE_FLAG")
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("kernel_exit_code", 1), "KERNEL_EXIT_NONZERO")
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("zero_warnings", False), "WARNINGS_FLAG")
        _tamper(lambda p: p["theorem_modules"][0]["theorems"].pop(), "THEOREMS_LIST_MISMATCH")
        _tamper(lambda p: p["theorem_modules"][0].__setitem__("theorems", "12345678"), "THEOREMS_LIST_MISMATCH")
        _tamper(lambda p: p["theorem_modules"][0]["theorems"][0].__setitem__("name", "bad"), "THEOREM_NAME_MISMATCH")
        _tamper(lambda p: p["theorem_modules"][0]["theorems"][0].__setitem__("standard_axioms_only", False), "THEOREM_AXIOM_FLAG")
        _tamper(lambda p: p["theorem_modules"][0]["theorems"][0].__setitem__("axioms", ["a", "b", "c", "d"]), "AXIOM_LIST_INVALID")
        _tamper(lambda p: p["theorem_modules"][0]["theorems"][0].__setitem__("axioms", "ab"), "AXIOM_LIST_INVALID")
        _tamper(lambda p: p["theorem_modules"][0]["theorems"][0].__setitem__("axioms", ["sorryAx"]), "FORBIDDEN_LEAN_AXIOM")
        _tamper(lambda p: p["theorem_modules"][0]["theorems"][0].__setitem__("axioms", ["propext", "propext"]), "DUPLICATE_AXIOM")
        _tamper(lambda p: p["theorem_modules"][0]["theorems"][0].__setitem__("axioms", ["propext"]), "AXIOM_SET_MISMATCH")
        _tamper(lambda p: p["python_exact_cross_checks"]["module1_hysteresis_concavity_cliff"].__setitem__("thermal_hysteresis_loop_area", -249), "CROSS_CHECK_MISMATCH")
        _tamper(lambda p: p["python_exact_cross_checks"]["module1_hysteresis_concavity_cliff"].__setitem__("concave_slope_23_q", "28/6"), "NON_REDUCED_RATIONAL")
        _tamper(lambda p: p["python_exact_cross_checks"]["module2_schur_dark_mode_gauge"].__setitem__("stage2_eta_q", "6/10"), "NON_REDUCED_RATIONAL")
        _tamper(lambda p: p["python_exact_cross_checks"]["module3_laplacian_thermal_coupling"].__setitem__("ratio_t1_over_t7_q", "5462/128"), "NON_REDUCED_RATIONAL")
        _tamper(lambda p: p["summary"].__setitem__("module_count", 2), "SUMMARY_MODULE_COUNT")
        _tamper(lambda p: p["summary"].__setitem__("theorem_count", 23), "SUMMARY_THEOREM_COUNT")
        _tamper(lambda p: p["summary"].__setitem__("zero_warning_modules", 2), "SUMMARY_ZERO_WARNINGS")
        _tamper(lambda p: p["summary"].__setitem__("forbidden_axiom_count", 1), "SUMMARY_FORBIDDEN_AXIOMS")
        _tamper(lambda p: p["summary"].__setitem__("all_three_modules_kernel_checked", False), "SUMMARY_KERNEL_FLAG")
        _tamper(lambda p: p["summary"].__setitem__("all_theorems_standard_axioms_only", False), "SUMMARY_AXIOM_FLAG")
        _tamper(lambda p: p["summary"].__setitem__("float_count_on_trust_path", 1), "SUMMARY_FLOATS")
        _tamper(lambda p: p["summary"].__setitem__("bare_assert_count", 1), "SUMMARY_ASSERTS")
        _tamper(lambda p: p["summary"].__setitem__("rng_calls", 1), "SUMMARY_RNG")

        _tamper(lambda p: p.__setitem__("measured_external_mathlib", 0), "INVALID_BOOL_TYPE")
        _tamper(lambda p: p["summary"].__setitem__("rng_calls", False), "UNEXPECTED_BOOL_LEAF")
        _tamper(lambda p: p["ceer_pillars_covered"].__setitem__(0, True), "UNEXPECTED_BOOL_ITEM")

    def test_11_cli_error_paths_and_check_file_utf8(self) -> None:
        for bad_argv, exp_err in (
            (["--bogus"], "INVALID_CLI_ARGS"),
            (["--write"], "INVALID_CLI_ARGS"),
            (["--write", "--json"], "INVALID_CLI_ARGS"),
            (["--write", "-x"], "INVALID_CLI_ARGS"),
            (["--check", "--json"], "INVALID_CLI_ARGS"),
            (["--bogus", "x"], "INVALID_CLI_ARGS"),
            (["--check"], "INVALID_CLI_ARGS"),
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
            self._assert_err(
                "INVALID_UTF8_LEAN",
                audit.run_live_lean_module,
                lean_bin, root, "BadUtf8.lean", ("T.t",), "M_U", "P",
            )
            bad_sorry = root / "BadSorry.lean"
            audit.write_regular_bytes_safe(bad_sorry, b"theorem t : False := by sorry\n")
            self._assert_err(
                "LEAN4_SORRY",
                audit.run_live_lean_module,
                lean_bin, root, "BadSorry.lean", ("t",), "M_S", "P",
            )
            bad_type = root / "BadType.lean"
            audit.write_regular_bytes_safe(bad_type, b"theorem bad : 1 = 2 := by decide\n")
            self._assert_err(
                "LEAN_KERNEL_REJECTED",
                audit.run_live_lean_module,
                lean_bin, root, "BadType.lean", ("bad",), "M_T", "P",
            )
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
            res = audit.run_live_lean_module(lean_bin, root, "GoodMin.lean", ("ok",), "M_OK", "P")
            self.assertEqual(res["kernel_exit_code"], 0)
            self.assertEqual(res["theorems"], [{"name": "ok", "axioms": [], "standard_axioms_only": True}])

    def test_95_live_lean_full_suite_and_cli_parity(self) -> None:
        live_cert = audit.build_certificate(_TRACK_DIR)
        disk_raw = audit.read_regular_bytes_capped(_CERT_PATH, "disk_cert")
        self.assertEqual(audit.canonical_json_bytes(live_cert) + b"\n", disk_raw)

        out_check = io.StringIO()
        with mock.patch.object(sys, "stdout", out_check):
            rc = audit.main(["--check", str(_CERT_PATH)])
        self.assertEqual(rc, 0)
        chk = audit.parse_strict_json_text(out_check.getvalue())
        self.assertIs(chk["verified"], True)
        self.assertEqual(chk["theorem_count"], 24)

        with mock.patch.object(audit, "build_certificate", return_value=live_cert):
            out_sum = io.StringIO()
            with mock.patch.object(sys, "stdout", out_sum):
                self.assertEqual(audit.main([]), 0)
            self.assertEqual(audit.parse_strict_json_text(out_sum.getvalue())["theorem_count"], 24)

            out_st = io.StringIO()
            with mock.patch.object(sys, "stdout", out_st):
                self.assertEqual(audit.main(["--standalone", "--json"]), 0)
            self.assertEqual(out_st.getvalue().encode("utf-8"), disk_raw)

            with tempfile.TemporaryDirectory() as td:
                out_p = Path(td) / "rebuilt.json"
                out_w = io.StringIO()
                with mock.patch.object(sys, "stdout", out_w):
                    self.assertEqual(audit.main(["--write", str(out_p)]), 0)
                w_obj = audit.parse_strict_json_text(out_w.getvalue())
                self.assertIs(w_obj["written"], True)
                self.assertEqual(w_obj["certificate_sha256"], live_cert["certificate_sha256"])
                self.assertEqual(audit.read_regular_bytes_capped(out_p), disk_raw)


if __name__ == "__main__":
    unittest.main()
