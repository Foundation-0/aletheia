#!/usr/bin/env python3
"""Track S102 R5 Assertion-Free Verification Test Suite (0 bare asserts, 0 skips).

Covers Zone-B filesystem/path/JSON/DoS hardening, exact integer/rational operators,
field-complete SEC/FR0/FR1 re-signed forgery resistance (0 bypasses), R12-grade
static Lean 4 trust-escape scanner + clean controls (0 FP), zero-TOCTOU live &
Lean-less verifier paths, external-pin verifier, and full CLI parity.
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
import subprocess
import sys
import tempfile
from typing import Any, Callable

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import s102_malecns_connectome_oracle as oracle  # noqa: E402
import verify_s102_malecns_connectome as verifier  # noqa: E402


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def expect_s102_error(fn: Callable[[], Any], expected_code: str | None = None, msg: str = "") -> str:
    try:
        fn()
    except oracle.S102Error as exc:
        if expected_code is not None:
            check(
                exc.code == expected_code,
                f"{msg}: expected code {expected_code!r}, got {exc.code!r} ({exc.message})",
            )
        return exc.code
    raise AssertionError(f"{msg}: expected S102Error({expected_code!r}), but succeeded")


def resign_cert(cert: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(cert)
    payload = out["payload"]
    p_sha = oracle.sha256_bytes(oracle.canonical_json_bytes(payload))
    out["payload_sha256"] = p_sha
    body = {
        "schema_version": out["schema_version"],
        "track_id": out["track_id"],
        "payload_sha256": p_sha,
        "payload": payload,
    }
    out["certificate_sha256"] = oracle.sha256_bytes(oracle.canonical_json_bytes(body))
    return out


def _run_cli_capture(argv: list[str]) -> tuple[int, str, str]:
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = out_buf, err_buf
        rc = verifier.main(argv)
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    return rc, out_buf.getvalue(), err_buf.getvalue()


def _make_fake_lean(bin_dir: Path, body: str) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    p = bin_dir / "lean"
    p.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
    os.chmod(p, 0o700)
    return p


def _with_env(updates: dict[str, str | None], fn: Callable[[], Any]) -> Any:
    saved: dict[str, str | None] = {k: os.environ.get(k) for k in updates}
    try:
        for k, v in updates.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return fn()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---------------------------------------------------------------------------
# T01: Standalone, Write, Check, Companion Pins, Determinism
# ---------------------------------------------------------------------------


def test_t01_roundtrip_and_pins() -> None:
    cert = oracle.build_certificate()
    raw = oracle.canonical_json_bytes(cert)
    rc_s, out_s, err_s = _run_cli_capture(["--standalone"])
    check(rc_s == 0 and err_s == "", f"standalone failed: rc={rc_s} err={err_s}")
    check(out_s.encode("ascii") == raw, "standalone bytes mismatch")

    with tempfile.TemporaryDirectory(prefix="s102_t01_") as td:
        out_p = Path(td) / "cert.json"
        rc_w, out_w, err_w = _run_cli_capture(["--write", str(out_p), "--json"])
        check(rc_w == 0 and err_w == "", f"write json failed: {err_w}")
        w_obj = json.loads(out_w)
        check(w_obj["status"] == "WRITTEN", "write status")
        check(w_obj["certificate_sha256"] == cert["certificate_sha256"], "write sha")
        st = os.lstat(out_p)
        check(stat.S_IMODE(st.st_mode) == 0o600, f"expected 0o600, got {oct(st.st_mode)}")
        check(out_p.read_bytes() == raw, "written bytes != canonical")

        # Overwrite existing file in non-json mode
        rc_w2, out_w2, err_w2 = _run_cli_capture(["--write", str(out_p)])
        check(rc_w2 == 0 and err_w2 == "" and "WROTE" in out_w2, "write text failed")

        rc_c, out_c, err_c = _with_env({"PATH": "", "HOME": ""}, lambda: _run_cli_capture(["--check", str(out_p), "--json"]))
        check(rc_c == 0 and err_c == "", f"check json failed: {err_c}")
        c_obj = json.loads(out_c)
        check(c_obj["status"] == "PASS", "check pass")
        check(c_obj["lean"]["static_r12_clean"] is True, "lean static clean")
        check(c_obj["lean"]["theorems_verified"] == 18, "18 theorems")

        rc_c2, out_c2, err_c2 = _with_env({"PATH": "", "HOME": ""}, lambda: _run_cli_capture(["--check", str(out_p)]))
        check(rc_c2 == 0 and err_c2 == "" and "Track S102 PASS" in out_c2, "check text failed")

    # Default committed certificate check
    committed = oracle.TRACK_DIR / oracle.DEFAULT_CERT_FILENAME
    check(committed.is_file(), "committed certificate missing")
    rc_def, out_def, err_def = _run_cli_capture(["--json"])
    check(rc_def == 0 and err_def == "", f"default check failed: {err_def}")
    check(json.loads(out_def)["status"] == "PASS", "default check PASS")

    # Companion pins check & tamper
    pins = verifier.verify_track_companion_pins(oracle.TRACK_DIR)
    check(len(pins) == 4, "expected 4 companion pins")
    with tempfile.TemporaryDirectory(prefix="s102_pins_") as td:
        tdir = Path(td)
        for fname in ("lean-toolchain", "lakefile.toml", "DrosophilaConnectomeOperators.lean", oracle.ANCHOR_FILENAME):
            (tdir / fname).write_bytes((oracle.TRACK_DIR / fname).read_bytes())
        check(len(verifier.verify_track_companion_pins(tdir)) == 4, "copied pins pass")
        (tdir / "lakefile.toml").write_bytes(b"tampered\n")
        expect_s102_error(
            lambda: verifier.verify_track_companion_pins(tdir),
            "COMPANION_SHA_MISMATCH",
            "tampered companion pin",
        )


# ---------------------------------------------------------------------------
# T02: Zone-B Path & Filesystem Hardening
# ---------------------------------------------------------------------------


def test_t02_zone_b_filesystem() -> None:
    # Darwin prefix normalizer
    check(verifier._normalize_darwin_private_prefix("/private/tmp") == "/tmp", "darwin /private/tmp")
    check(verifier._normalize_darwin_private_prefix("/private/tmp/a") == "/tmp/a", "darwin /private/tmp/a")
    check(verifier._normalize_darwin_private_prefix("/private/var") == "/var", "darwin /private/var")
    check(verifier._normalize_darwin_private_prefix("/private/var/b") == "/var/b", "darwin /private/var/b")
    check(verifier._normalize_darwin_private_prefix("/tmp/x") == "/tmp/x", "non-darwin unchanged")

    expect_s102_error(lambda: verifier._check_path_str("", "p"), "EMPTY_PATH", "empty path")
    expect_s102_error(lambda: verifier._check_path_str("a\x00b", "p"), "NUL_BYTE_FORBIDDEN", "nul path")
    expect_s102_error(lambda: verifier._check_path_str("a\ud800b", "p"), "INVALID_UTF8_SURROGATE", "surrogate path")
    expect_s102_error(lambda: verifier._check_path_str(123, "p"), "TYPE_ERROR", "non-str path")
    check(verifier._check_path_str(Path("/tmp/ok"), "p") == Path("/tmp/ok"), "Path accepted")

    with tempfile.TemporaryDirectory(prefix="s102_t02_") as td:
        tdir = Path(td)
        reg = tdir / "reg.json"
        reg.write_bytes(b"{}\n")
        sym = tdir / "sym.json"
        os.symlink(reg, sym)
        hard = tdir / "hard.json"
        os.link(reg, hard)
        sub = tdir / "sub"
        sub.mkdir()
        sym_dir = tdir / "sym_dir"
        os.symlink(sub, sym_dir)
        fifo = tdir / "pipe"
        os.mkfifo(fifo)

        expect_s102_error(lambda: verifier.read_regular_bytes_capped(sym, "s"), "SYMLINK_IN_PATH", "symlink file")
        expect_s102_error(lambda: verifier.read_regular_bytes_capped(sym_dir / "x", "sd"), "SYMLINK_IN_PATH", "symlink dir")
        expect_s102_error(lambda: verifier.read_regular_bytes_capped(hard, "h"), "HARDLINK_FORBIDDEN", "hardlink")
        expect_s102_error(lambda: verifier.read_regular_bytes_capped(sub, "d"), "NOT_REGULAR_FILE", "dir not reg")
        expect_s102_error(lambda: verifier.read_regular_bytes_capped(fifo, "f"), "NOT_REGULAR_FILE", "fifo not reg")
        expect_s102_error(lambda: verifier.read_regular_bytes_capped(tdir / "missing", "m"), "IO_OPEN_ERROR", "missing")
        big = tdir / "big.json"
        big.write_bytes(b"a" * 32)
        expect_s102_error(lambda: verifier.read_regular_bytes_capped(big, "b", max_bytes=16), "FILE_TOO_LARGE", "cap")
        check(len(verifier.read_regular_bytes_capped(big, "b", max_bytes=32)) == 32, "exact max_bytes boundary")
        expect_s102_error(lambda: verifier.read_regular_bytes_capped(big, "b", max_bytes=0), "RANGE_ERROR", "max_bytes=0")

        # Simulate procfs st_size=0 streaming overflow (kills FILE_STREAM_TOO_LARGE guard)
        orig_fstat = os.fstat
        class _ZeroSizeStat:
            def __init__(self, real_st: os.stat_result) -> None:
                self.st_mode = real_st.st_mode
                self.st_nlink = real_st.st_nlink
                self.st_size = 0
        try:
            os.fstat = lambda fd: _ZeroSizeStat(orig_fstat(fd))  # type: ignore[assignment]
            expect_s102_error(
                lambda: verifier.read_regular_bytes_capped(big, "b", max_bytes=16),
                "FILE_STREAM_TOO_LARGE",
                "stream cap",
            )
            check(len(verifier.read_regular_bytes_capped(big, "b", max_bytes=32)) == 32, "exact stream boundary")
        finally:
            os.fstat = orig_fstat

        # OSError paths in lstat / getcwd / write (kills guard_except_reject)
        orig_lstat = os.lstat
        try:
            def _boom_lstat(_p: Any) -> Any:
                raise PermissionError("simulated")
            os.lstat = _boom_lstat  # type: ignore[assignment]
            expect_s102_error(lambda: verifier._check_no_symlink_components(reg, "r"), "IO_STAT_ERROR", "lstat err")
        finally:
            os.lstat = orig_lstat

        orig_getcwd = os.getcwd
        try:
            def _boom_getcwd() -> str:
                raise OSError("simulated")
            os.getcwd = _boom_getcwd  # type: ignore[assignment]
            expect_s102_error(verifier._check_safe_cwd, "CWD_ERROR", "getcwd err")
        finally:
            os.getcwd = orig_getcwd

        # Write hardening
        expect_s102_error(lambda: verifier.write_regular_bytes_atomic_0600(tdir / "x", "str", "w"), "INVALID_BYTES", "non-bytes")
        expect_s102_error(lambda: verifier.write_regular_bytes_atomic_0600(tdir / "no_parent" / "x", b"{}", "w"), "PARENT_STAT_ERROR", "missing parent")
        expect_s102_error(lambda: verifier.write_regular_bytes_atomic_0600(big / "child", b"{}", "w"), "PARENT_NOT_DIR", "parent file")
        expect_s102_error(lambda: verifier.write_regular_bytes_atomic_0600(sub, b"{}", "w"), "TARGET_NOT_REGULAR", "target dir")
        expect_s102_error(lambda: verifier.write_regular_bytes_atomic_0600(hard, b"{}", "w"), "TARGET_HARDLINK", "target hardlink")
        expect_s102_error(lambda: verifier.write_regular_bytes_atomic_0600(sym, b"{}", "w"), "SYMLINK_IN_PATH", "target symlink")
        # Read-only dir write error + target lstat OSError
        ro_dir = tdir / "ro_write"
        ro_dir.mkdir()
        os.chmod(ro_dir, 0o500)
        try:
            expect_s102_error(
                lambda: verifier.write_regular_bytes_atomic_0600(ro_dir / "x.json", b"{}\n", "w"),
                "IO_WRITE_ERROR",
                "ro dir write",
            )
        finally:
            os.chmod(ro_dir, 0o700)
        target_p = tdir / "tgt_err.json"
        orig_lstat2 = os.lstat
        try:
            def _fail_target_lstat(p: Any) -> Any:
                if os.fspath(p) == os.fspath(target_p):
                    raise PermissionError("simulated target lstat")
                return orig_lstat2(p)
            # Only fail on the second call to lstat(target_p) (after _check_no_symlink_components)
            calls = {"n": 0}
            def _fail_second(p: Any) -> Any:
                if os.fspath(p) == os.fspath(target_p):
                    calls["n"] += 1
                    if calls["n"] >= 2:
                        raise PermissionError("simulated target lstat")
                return orig_lstat2(p)
            os.lstat = _fail_second  # type: ignore[assignment]
            expect_s102_error(
                lambda: verifier.write_regular_bytes_atomic_0600(target_p, b"{}\n", "w"),
                "TARGET_STAT_ERROR",
                "target lstat err",
            )
        finally:
            os.lstat = orig_lstat2

        # _check_safe_cwd with symlinked PWD pointing to same inode
        real_dir = tdir / "real_cwd"
        real_dir.mkdir()
        sym_cwd = tdir / "sym_cwd"
        os.symlink(real_dir, sym_cwd)
        old_cwd = os.getcwd()
        try:
            os.chdir(real_dir)
            _with_env(
                {"PWD": str(sym_cwd)},
                lambda: expect_s102_error(verifier._check_safe_cwd, "SYMLINK_IN_PATH", "symlink PWD"),
            )
            # Non-matching PWD or nonexistent PWD is ignored safely
            _with_env({"PWD": str(tdir / "does_not_exist")}, verifier._check_safe_cwd)
            _with_env({"PWD": str(sub)}, verifier._check_safe_cwd)
            _with_env({"PWD": None}, verifier._check_safe_cwd)
            os.symlink(".", real_dir / "rel_sym")
            _with_env({"PWD": "rel_sym"}, verifier._check_safe_cwd)
        finally:
            os.chdir(old_cwd)


# ---------------------------------------------------------------------------
# T03: Strict JSON Parser & DoS Guards
# ---------------------------------------------------------------------------


def test_t03_strict_json_and_rationals() -> None:
    expect_s102_error(lambda: verifier.parse_strict_json_bytes("notbytes"), "INVALID_BYTES", "non-bytes")
    expect_s102_error(lambda: verifier.parse_strict_json_bytes(b""), "EMPTY_JSON", "empty")
    expect_s102_error(
        lambda: verifier.parse_strict_json_bytes(b" " * (verifier.MAX_JSON_BYTES + 1)),
        "FILE_TOO_LARGE",
        "too large",
    )
    expect_s102_error(lambda: verifier.parse_strict_json_bytes(b"{\x00}"), "NUL_BYTE_FORBIDDEN", "nul")
    expect_s102_error(lambda: verifier.parse_strict_json_bytes(b"{}\r\n"), "CRLF_FORBIDDEN", "crlf")
    expect_s102_error(lambda: verifier.parse_strict_json_bytes(b'{"a": 1}\n'), "NON_CANONICAL_JSON", "non-canon")
    expect_s102_error(lambda: verifier.parse_strict_json_bytes(b"\xef\xbb\xbf{}"), "UTF8_BOM_FORBIDDEN", "bom")
    expect_s102_error(lambda: verifier.parse_strict_json_bytes(b"\xff\xfe"), "INVALID_UTF8", "bad utf8")
    # Pre-scan kill witness: invalid JSON syntax after huge integer (M037 pattern!)
    expect_s102_error(
        lambda: verifier.parse_strict_json_bytes(b"{" + b"9" * (verifier.MAX_JSON_INT_DIGITS + 5)),
        "JSON_INT_TOO_LARGE",
        "raw int prescan kill",
    )
    expect_s102_error(
        lambda: verifier.parse_strict_json_bytes(b'{"a": -' + b"9" * (verifier.MAX_JSON_INT_DIGITS + 1) + b"}"),
        "JSON_INT_TOO_LARGE",
        "negative raw int prescan",
    )
    expect_s102_error(
        lambda: verifier._bounded_parse_int("9" * (verifier.MAX_JSON_INT_DIGITS + 1)),
        "JSON_INT_TOO_LARGE",
        "bounded_parse_int direct pos",
    )
    expect_s102_error(
        lambda: verifier._bounded_parse_int("-" + "9" * (verifier.MAX_JSON_INT_DIGITS + 1)),
        "JSON_INT_TOO_LARGE",
        "bounded_parse_int direct neg",
    )
    check(verifier._bounded_parse_int("-42") == -42, "bounded_parse_int valid")
    # Exact boundary tests (kills <= -> < boundary mutants)
    max_int_s = "9" * verifier.MAX_JSON_INT_DIGITS
    check(verifier._bounded_parse_int(max_int_s) == int(max_int_s), "bounded_parse_int exact boundary")
    exact_int_raw = b'{"a":' + max_int_s.encode("ascii") + b"}\n"
    check(verifier.parse_strict_json_bytes(exact_int_raw)["a"] == int(max_int_s), "prescan exact int boundary")
    exact_bytes_raw = b'{"a":"' + b"x" * (verifier.MAX_JSON_BYTES - 9) + b'"}\n'
    check(len(exact_bytes_raw) == verifier.MAX_JSON_BYTES, "exact bytes len")
    check(len(verifier.parse_strict_json_bytes(exact_bytes_raw)["a"]) == verifier.MAX_JSON_BYTES - 9, "exact bytes boundary")
    expect_s102_error(lambda: verifier.parse_strict_json_bytes(b'{"a": 1.5}'), "FLOAT_FORBIDDEN", "float")
    expect_s102_error(lambda: verifier.parse_strict_json_bytes(b'{"a": NaN}'), "JSON_CONSTANT_FORBIDDEN", "NaN")
    expect_s102_error(lambda: verifier.parse_strict_json_bytes(b'{"a": 1, "a": 2}'), "DUPLICATE_JSON_KEY", "dup key")
    expect_s102_error(lambda: verifier.parse_strict_json_bytes(b"[1, 2]"), "JSON_ROOT_NOT_OBJECT", "list root")
    expect_s102_error(lambda: verifier.parse_strict_json_bytes(b'{"a":'), "JSON_SYNTAX_ERROR", "syntax")

    # Tree validator DoS & type guards + exact boundaries
    deep32: Any = 1
    for _ in range(32):
        deep32 = [deep32]
    verifier.validate_strict_json_tree(deep32)
    verifier.validate_strict_json_tree({"x": (1 << verifier.MAX_JSON_INT_BITS) - 1})
    deep: Any = 1
    for _ in range(34):
        deep = [deep]
    expect_s102_error(lambda: verifier.validate_strict_json_tree(deep), "JSON_TOO_DEEP", "depth > 32")
    expect_s102_error(
        lambda: verifier.validate_strict_json_tree({"x": 1 << (verifier.MAX_JSON_INT_BITS + 1)}),
        "JSON_INT_TOO_LARGE",
        "int bit_length > 2048",
    )
    expect_s102_error(lambda: verifier.require_exact_keys([], frozenset(), "k"), "TYPE_ERROR", "require_exact_keys non-dict")
    expect_s102_error(lambda: verifier.validate_strict_json_tree({"x": "a\x00b"}), "NUL_BYTE_FORBIDDEN", "nul str")
    expect_s102_error(lambda: verifier.validate_strict_json_tree({"x": "\ud800"}), "INVALID_UTF8_SURROGATE", "surrogate")
    expect_s102_error(lambda: verifier.validate_strict_json_tree({1: "v"}), "NON_STRING_KEY", "int key")
    expect_s102_error(lambda: verifier.validate_strict_json_tree({"x": 1.25}), "DISALLOWED_JSON_TYPE", "float in tree")
    verifier.validate_strict_json_tree({"a": None, "b": True, "c": [1, "ok"]})

    # Rational string parser
    check(verifier.parse_exact_q("0", "q") == Fraction(0), "q=0")
    check(verifier.parse_exact_q("-7/3", "q") == Fraction(-7, 3), "q=-7/3")
    check(verifier.parse_exact_q("1" + "0" * 255, "q") == Fraction(10**255, 1), "q exact len 256")
    expect_s102_error(lambda: verifier.parse_exact_q("9" * 257, "q"), "RATIONAL_STR_TOO_LONG", "q len > 256")
    expect_s102_error(lambda: verifier.parse_exact_q("9" * 5000, "q"), "RATIONAL_STR_TOO_LONG", "q >4300 digits")
    expect_s102_error(lambda: verifier.parse_exact_q("4/2", "q"), "NON_CANONICAL_Q", "unreduced")
    expect_s102_error(lambda: verifier.parse_exact_q("5/1", "q"), "NON_CANONICAL_Q", "denom 1")
    expect_s102_error(lambda: verifier.parse_exact_q("01/3", "q"), "INVALID_RATIONAL_STR", "leading zero")
    expect_s102_error(lambda: verifier.parse_exact_q(12, "q"), "TYPE_ERROR", "non-str q")

    # SHA256 validator
    expect_s102_error(lambda: verifier.require_sha256_str("abc", "s"), "INVALID_SHA256", "short sha")
    expect_s102_error(lambda: verifier.require_sha256_str("A" * 64, "s"), "INVALID_SHA256", "upper sha")


# ---------------------------------------------------------------------------
# T04: Oracle Math, Operators, and Anchor Loader
# ---------------------------------------------------------------------------


def test_t04_oracle_operators_and_anchor() -> None:
    expect_s102_error(lambda: oracle.require_ok(1, "C", "m"), "C", "non-bool require_ok")  # type: ignore[arg-type]
    expect_s102_error(lambda: oracle.require_ok(False, "C", "m"), "C", "false require_ok")
    expect_s102_error(lambda: oracle.require_exact_int(True, "i"), "TYPE_ERROR", "bool not int")
    expect_s102_error(lambda: oracle.require_exact_int(2, "i", lo=3), "RANGE_ERROR", "below lo")
    expect_s102_error(lambda: oracle.require_exact_int(5, "i", hi=4), "RANGE_ERROR", "above hi")
    check(oracle.require_exact_int(3, "i", lo=3, hi=3) == 3, "exact boundary lo==hi")
    expect_s102_error(lambda: oracle.require_exact_str(1, "s"), "TYPE_ERROR", "not str")
    expect_s102_error(lambda: oracle.require_exact_bool(1, "b"), "TYPE_ERROR", "not bool")
    expect_s102_error(lambda: oracle.fmt_q(3), "TYPE_ERROR", "not Fraction")  # type: ignore[arg-type]
    check(oracle.fmt_q(Fraction(6, 2)) == "3", "fmt_q int")
    check(oracle.fmt_q(Fraction(5, 2)) == "5/2", "fmt_q frac")

    # LDLT & inverse failure modes
    expect_s102_error(lambda: oracle.exact_ldlt_pivots([[0, 1], [1, 0]]), "LDLT_ZERO_PIVOT", "zero pivot")
    expect_s102_error(
        lambda: oracle.exact_mat_inv([[Fraction(1), Fraction(2)], [Fraction(2), Fraction(4)]]),
        "SINGULAR_MATRIX",
        "singular mat",
    )
    # Pivoting swap branch in exact_mat_inv
    inv_swap = oracle.exact_mat_inv([[Fraction(0), Fraction(1)], [Fraction(1), Fraction(0)]])
    check(inv_swap == [[Fraction(0), Fraction(1)], [Fraction(1), Fraction(0)]], "swap inverse")

    # LIF simulation checks
    w_pruned = oracle.simulate_integer_lif_may_fire(120, 600, 300, 20)
    check(w_pruned["may_fire_pruned"] and w_pruned["never_reached_theta"], "LIF pruned")
    check(w_pruned["envelope_monotone_all_steps"] and w_pruned["peak_bounded_by_envelope"], "LIF invariant")
    w_active = oracle.simulate_integer_lif_may_fire(200, 1200, 300, 20)
    check(not w_active["may_fire_pruned"] and not w_active["never_reached_theta"], "LIF active")

    # Anchor loader failure modes
    anc_raw = (oracle.TRACK_DIR / oracle.ANCHOR_FILENAME).read_bytes()
    anc_obj = json.loads(anc_raw.decode("utf-8"))
    expect_s102_error(lambda: oracle.load_anchor_from_bytes(b"{}", check_pinned_sha=True), "ANCHOR_FILE_SHA_MISMATCH", "bad file sha")
    expect_s102_error(lambda: oracle.load_anchor_from_bytes(b'{"a":1.5}', check_pinned_sha=False), "FLOAT_FORBIDDEN", "anchor float")
    expect_s102_error(lambda: oracle.load_anchor_from_bytes(b'{"a":NaN}', check_pinned_sha=False), "JSON_CONSTANT_FORBIDDEN", "anchor NaN")
    expect_s102_error(lambda: oracle.load_anchor_from_bytes(b'{"a":1,"a":2}', check_pinned_sha=False), "DUPLICATE_JSON_KEY", "anchor dup")
    expect_s102_error(lambda: oracle.load_anchor_from_bytes(b"{", check_pinned_sha=False), "ANCHOR_JSON_INVALID", "anchor bad json")
    expect_s102_error(lambda: oracle.load_anchor_from_bytes(b"[]", check_pinned_sha=False), "ANCHOR_TYPE_ERROR", "anchor list")
    bad_schema = dict(anc_obj, schema_version="wrong")
    expect_s102_error(
        lambda: oracle.load_anchor_from_bytes(oracle.canonical_json_bytes(bad_schema), check_pinned_sha=False),
        "ANCHOR_SCHEMA_MISMATCH",
        "anchor schema",
    )
    bad_track = dict(anc_obj, track_id="S999")
    expect_s102_error(
        lambda: oracle.load_anchor_from_bytes(oracle.canonical_json_bytes(bad_track), check_pinned_sha=False),
        "ANCHOR_TRACK_MISMATCH",
        "anchor track",
    )
    bad_pay = dict(anc_obj, payload="notdict")
    expect_s102_error(
        lambda: oracle.load_anchor_from_bytes(oracle.canonical_json_bytes(bad_pay), check_pinned_sha=False),
        "ANCHOR_PAYLOAD_ERROR",
        "anchor payload type",
    )
    bad_psha = dict(anc_obj, payload_sha256="0" * 64)
    expect_s102_error(
        lambda: oracle.load_anchor_from_bytes(oracle.canonical_json_bytes(bad_psha), check_pinned_sha=False),
        "ANCHOR_PAYLOAD_SHA_MISMATCH",
        "anchor payload sha",
    )

    # Regression #1: bounded int/str/depth DoS protection on anchor parser (incl. 4301-digit ints & strings)
    ok_int_p = {"n": int("9" * oracle.ANCHOR_MAX_INT_DIGITS), "neg": -int("9" * oracle.ANCHOR_MAX_INT_DIGITS)}
    ok_int_env = {
        "schema_version": oracle.ANCHOR_SCHEMA_VERSION,
        "track_id": oracle.TRACK_ID,
        "payload_sha256": oracle.sha256_bytes(oracle.canonical_json_bytes(ok_int_p)),
        "payload": ok_int_p,
    }
    check(
        oracle.load_anchor_from_bytes(oracle.canonical_json_bytes(ok_int_env), check_pinned_sha=False) == ok_int_p,
        "anchor exact 80-digit int boundary",
    )
    expect_s102_error(
        lambda: oracle.load_anchor_from_bytes(
            ('{"a":' + "9" * (oracle.ANCHOR_MAX_INT_DIGITS + 1) + "}").encode("ascii"),
            check_pinned_sha=False,
        ),
        "ANCHOR_INT_TOO_LARGE",
        "anchor 81-digit int",
    )
    expect_s102_error(
        lambda: oracle.load_anchor_from_bytes(
            ('{"a":' + "9" * 4301 + "}").encode("ascii"),
            check_pinned_sha=False,
        ),
        "ANCHOR_INT_TOO_LARGE",
        "anchor 4301-digit int",
    )
    ok_str_p = {"k" * oracle.ANCHOR_MAX_STR_LEN: "1" + "0" * (oracle.ANCHOR_MAX_STR_LEN - 1)}
    ok_str_env = {
        "schema_version": oracle.ANCHOR_SCHEMA_VERSION,
        "track_id": oracle.TRACK_ID,
        "payload_sha256": oracle.sha256_bytes(oracle.canonical_json_bytes(ok_str_p)),
        "payload": ok_str_p,
    }
    check(
        oracle.load_anchor_from_bytes(oracle.canonical_json_bytes(ok_str_env), check_pinned_sha=False) == ok_str_p,
        "anchor exact 256-char key & str boundary",
    )
    for bad_str_p, lbl in (
        ({"q": "9" * (oracle.ANCHOR_MAX_STR_LEN + 1)}, "anchor 257-char str"),
        ({"q": "9" * 4301}, "anchor 4301-digit rational str"),
        ({"k" * (oracle.ANCHOR_MAX_STR_LEN + 1): "ok"}, "anchor 257-char key"),
    ):
        bad_env = {
            "schema_version": oracle.ANCHOR_SCHEMA_VERSION,
            "track_id": oracle.TRACK_ID,
            "payload_sha256": oracle.sha256_bytes(oracle.canonical_json_bytes(bad_str_p)),
            "payload": bad_str_p,
        }
        expect_s102_error(
            lambda be=bad_env: oracle.load_anchor_from_bytes(oracle.canonical_json_bytes(be), check_pinned_sha=False),
            "ANCHOR_STR_TOO_LONG",
            lbl,
        )
    deep_anc_ok: Any = 1
    for _ in range(oracle.ANCHOR_MAX_DEPTH):
        deep_anc_ok = [deep_anc_ok]
    oracle._validate_anchor_tree(deep_anc_ok)
    deep_anc_bad: Any = [deep_anc_ok]
    expect_s102_error(lambda: oracle._validate_anchor_tree(deep_anc_bad), "ANCHOR_TOO_DEEP", "anchor depth > 32")

    # Regression #2: immutable globals (MappingProxyType) & zero output aliasing across all 4 pillars
    for immutable_map in (
        oracle.PINNED_LEAN_FILES,
        oracle.FRUITFLY_CALC_CONSTANTS,
        oracle.NFLY_CONSTANTS,
        oracle.FLY_RACER_TIER_S,
        oracle.UPSTREAM_EXPEDITION_BRIDGES[0],
        oracle.FLY_RACER_ARMS[0],
        oracle.SOP10_SIBLING_PORTFOLIO[0],
    ):
        try:
            immutable_map["_mut"] = "forbidden"  # type: ignore[index]
        except TypeError:
            pass
        else:
            raise AssertionError("oracle global dict must be immutable MappingProxyType")
    anc_live = oracle.load_anchor_default()
    anc_snap = oracle.canonical_json_bytes(anc_live)
    c1 = oracle.build_certificate(anc_live)
    c1["payload"]["pillar1_whole_cns_topology"]["dale_edge_synapse_partition"]["excitatory_ach"]["edges"] = -1
    c1["payload"]["pillar1_whole_cns_topology"]["active_neuron_neurotransmitters"]["acetylcholine"] = -1
    c1["payload"]["pillar2_cx_attractor_and_supergraph"]["supergraph_8x8"]["unsigned_synapses_8x8"][0][0] = -1
    c1["payload"]["pillar2_cx_attractor_and_supergraph"]["central_complex_6x6"]["dale_signed_synapses_6x6"][0][0] = -1
    c1["payload"]["pillar2_cx_attractor_and_supergraph"]["central_complex_triads_w10"]["observed"]["ffl_total"] = -1
    c1["payload"]["pillar3_wave9_portal_engineering"]["fly_racer_four_arm_tail_risk"]["arms"][0]["mean_x10"] = -1
    c1["payload"]["pillar3_wave9_portal_engineering"]["sop10_sibling_portfolio"][0]["repo"] = "mut"
    c1["payload"]["pillar4_lean4_and_provenance"]["malecns_external_pins"][0]["bytes"] = -1
    c1["payload"]["pillar4_lean4_and_provenance"]["upstream_expedition_bridges"][0]["track"] = "mut"
    check(oracle.canonical_json_bytes(anc_live) == anc_snap, "anchor mutated via pillar alias")
    check(
        oracle.canonical_json_bytes(oracle.build_certificate(anc_live))
        == (oracle.TRACK_DIR / oracle.DEFAULT_CERT_FILENAME).read_bytes(),
        "subsequent build_certificate unaffected by output mutation",
    )

    # Tampered anchor invariants inside build_pillar1 / build_pillar2
    anc_ok = oracle.load_anchor_default()
    bad_de = copy.deepcopy(anc_ok)
    bad_de["whole_cns_topology"]["dale_edge_synapse_partition"]["excitatory_ach"]["edges"] += 1
    expect_s102_error(lambda: oracle.build_pillar1_whole_cns(bad_de), "DALE_EDGE_SUM", "dale edge sum")
    bad_ds = copy.deepcopy(anc_ok)
    bad_ds["whole_cns_topology"]["dale_edge_synapse_partition"]["excitatory_ach"]["synapses"] += 1
    expect_s102_error(lambda: oracle.build_pillar1_whole_cns(bad_ds), "DALE_SYN_SUM", "dale syn sum")
    bad_tk = copy.deepcopy(anc_ok)
    bad_tk["whole_cns_topology"]["top_k_concentration"] = []
    expect_s102_error(lambda: oracle.build_pillar1_whole_cns(bad_tk), "MISSING_TOP_0P5", "missing top 0.5%")
    bad_cx = copy.deepcopy(anc_ok)
    bad_cx["central_complex_core_6x6"]["dale_signed_synapses_6x6"][0][0] *= -1
    expect_s102_error(lambda: oracle.build_pillar2_cx_and_supergraph(bad_cx), "CX_DALE_ROW_MISMATCH", "cx dale row")
    # Constant split & Pythagorean checks
    fc = oracle.FRUITFLY_CALC_CONSTANTS
    check(fc["encoded_w_ge_2_mb_num"] + fc["encoded_w_eq_1_mb_num"] == fc["encoded_mb_num"], "fc weight split")
    check(fc["ram_mb_num"] + fc["flash_mb_num"] == fc["encoded_mb_num"], "fc ram+flash split")
    ops = oracle.operator_frobenius_and_commutator([[3, 5], [-2, 7]])
    check(4 * ops["frobenius_norm_sq"] == ops["sym_norm_sq_x4"] + ops["skew_norm_sq_x4"], "pythagorean")


# ---------------------------------------------------------------------------
# T05: Field-Complete SEC/FR0/FR1 Re-Signed Forgery Suite (0 Bypasses)
# ---------------------------------------------------------------------------


def test_t05_resigned_semantic_forgeries() -> None:
    anchor = oracle.load_anchor_default()
    base = oracle.build_certificate(anchor)

    # Confirm base passes SEC (explicit + default anchor), FR0, FR1
    verifier.secondary_audit_payload(base["payload"], anchor)
    verifier.secondary_audit_payload(base["payload"])
    check(verifier.verify_certificate_dict(base, full_replay=False)["secondary_audit"] == "PASS", "FR0 pass")
    check(verifier.verify_certificate_dict(base, full_replay=True)["full_replay"] is True, "FR1 pass")

    # Envelope-level tampers
    expect_s102_error(lambda: verifier.verify_certificate_dict(base, full_replay=1), "TYPE_ERROR", "non-bool full_replay")  # type: ignore[arg-type]
    bad_env = dict(base)
    bad_env["extra"] = 1
    expect_s102_error(lambda: verifier.verify_certificate_dict(bad_env), "KEY_SET_MISMATCH", "extra env key")
    expect_s102_error(lambda: verifier.verify_certificate_dict(dict(base, schema_version="bad")), "SCHEMA_MISMATCH", "env schema")
    expect_s102_error(lambda: verifier.verify_certificate_dict(dict(base, track_id="S0")), "TRACK_MISMATCH", "env track")
    expect_s102_error(lambda: verifier.verify_certificate_dict(dict(base, payload=[])), "TYPE_ERROR", "env payload list")
    expect_s102_error(lambda: verifier.verify_certificate_dict(dict(base, payload_sha256="0" * 64)), "PAYLOAD_SHA_MISMATCH", "bad psha")
    expect_s102_error(lambda: verifier.verify_certificate_dict(dict(base, certificate_sha256="0" * 64)), "CERT_SHA_MISMATCH", "bad csha")

    def mutate_and_assert_all_3_layers(mutator: Callable[[dict[str, Any]], None], exp_code: str, label: str) -> None:
        forged = copy.deepcopy(base)
        mutator(forged["payload"])
        resigned = resign_cert(forged)
        expect_s102_error(lambda: verifier.secondary_audit_payload(resigned["payload"], anchor), exp_code, f"SEC {label}")
        expect_s102_error(lambda: verifier.verify_certificate_dict(resigned, full_replay=False), exp_code, f"FR0 {label}")
        expect_s102_error(lambda: verifier.verify_certificate_dict(resigned, full_replay=True), exp_code, f"FR1 {label}")

    # Top-level payload tampers
    mutate_and_assert_all_3_layers(lambda p: p.__setitem__("schema_version", "x"), "SCHEMA_MISMATCH", "p.schema")
    mutate_and_assert_all_3_layers(lambda p: p.__setitem__("track_id", "x"), "TRACK_MISMATCH", "p.track")
    mutate_and_assert_all_3_layers(lambda p: p.__setitem__("oracle_class", "x"), "ORACLE_CLASS_MISMATCH", "p.oracle_class")
    mutate_and_assert_all_3_layers(lambda p: p.__setitem__("novelty_classification", "N2"), "NOVELTY_MISMATCH", "p.novelty")

    # Pillar 1 domain & replay forgeries
    mutate_and_assert_all_3_layers(lambda p: p["pillar1_whole_cns_topology"].__setitem__("mean_weight_per_edge_q", "1"), "P1_MEAN_W", "p1.mean_w")
    mutate_and_assert_all_3_layers(lambda p: p["pillar1_whole_cns_topology"].__setitem__("mean_out_degree_q", "1"), "P1_MEAN_DEG", "p1.mean_deg")
    mutate_and_assert_all_3_layers(lambda p: p["pillar1_whole_cns_topology"].__setitem__("dale_signed_synapses_total", 0), "RANGE_ERROR", "p1.dale_tot=0")
    mutate_and_assert_all_3_layers(lambda p: p["pillar1_whole_cns_topology"].__setitem__("dale_signed_synapses_total", "bad"), "TYPE_ERROR", "p1.dale_tot str")
    mutate_and_assert_all_3_layers(lambda p: p["pillar1_whole_cns_topology"].__setitem__("dale_signed_net_balance", 0), "RANGE_ERROR", "p1.dale_net=0")
    mutate_and_assert_all_3_layers(lambda p: p["pillar1_whole_cns_topology"].__setitem__("dale_signed_net_balance", "bad"), "TYPE_ERROR", "p1.dale_net str")
    mutate_and_assert_all_3_layers(lambda p: p["pillar1_whole_cns_topology"].__setitem__("s86_minus_malecns_top_0p5pct_gap_q", "0"), "P1_GAP_POS", "p1.gap=0")
    mutate_and_assert_all_3_layers(lambda p: p["pillar1_whole_cns_topology"].__setitem__("self_loop_edges", 999), "P1_REPLAY_MISMATCH", "p1.self_loops")
    mutate_and_assert_all_3_layers(lambda p: p["pillar1_whole_cns_topology"].__setitem__("min_edge_weight", True), "P1_REPLAY_MISMATCH", "p1.bool_as_int")

    # Pillar 2 non-dict/missing-key crash resistance + matrix/Dale/operator/Laplacian/Schur/CX/triad forgeries
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"].__setitem__("supergraph_8x8", "bad"), "TYPE_ERROR", "p2.sg str")
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"]["supergraph_8x8"]["schur_complement_io_boundary"].pop("trace_L_BB"), "KEY_SET_MISMATCH", "p2.sch missing trace_L_BB")
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"]["supergraph_8x8"]["schur_complement_io_boundary"].__setitem__("trace_L_BB", "bad"), "TYPE_ERROR", "p2.sch trace_L_BB str")
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"]["supergraph_8x8"]["schur_complement_io_boundary"].__setitem__("trace_L_BB", 0), "RANGE_ERROR", "p2.sch trace_L_BB=0")
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"].__setitem__("central_complex_6x6", "bad"), "TYPE_ERROR", "p2.cx str")
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"].__setitem__("central_complex_triads_w10", "bad"), "TYPE_ERROR", "p2.tri str")
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"]["supergraph_8x8"].__setitem__("unsigned_synapses_8x8", "12345678"), "MAT_ROW_DIM_ERROR", "w8_u non-list len 8")
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"]["supergraph_8x8"].__setitem__("unsigned_synapses_8x8", [[1]]), "MAT_ROW_DIM_ERROR", "w8_u bad rows")
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"]["supergraph_8x8"]["unsigned_synapses_8x8"].__setitem__(0, "12345678"), "MAT_COL_DIM_ERROR", "w8_u row non-list len 8")
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"]["supergraph_8x8"]["unsigned_synapses_8x8"].__setitem__(0, [1]), "MAT_COL_DIM_ERROR", "w8_u bad cols")
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"]["supergraph_8x8"]["dale_signed_synapses_8x8"][0].__setitem__(0, 999_999_999), "DALE_ABS_BOUND", "w8 dale abs bound")
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"]["supergraph_8x8"]["signed_operators"].__setitem__("commutator_norm_sq", 0), "OPERATOR_MISMATCH", "w8 ops")
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"]["supergraph_8x8"].__setitem__("signed_laplacian_ldlt_inertia", [7, 1, 0]), "W8_FRUSTRATION_MISMATCH", "w8 lap inertia")
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"]["supergraph_8x8"].__setitem__("signed_laplacian_structurally_frustrated", False), "W8_FRUSTRATION_MISMATCH", "w8 lap bool")
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"]["supergraph_8x8"]["schur_complement_io_boundary"].__setitem__("trace_dark_shadow_q", "0"), "SCHUR_TRACE_CONSERVATION", "schur trace")
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"]["central_complex_6x6"].__setitem__("dale_row_pure_homogeneous", False), "CX_OPERATOR_INERTIA_MISMATCH", "cx dale bool")
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"]["central_complex_6x6"].__setitem__("signed_laplacian_ldlt_inertia", [5, 1, 0]), "CX_OPERATOR_INERTIA_MISMATCH", "cx lap inertia")
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"]["central_complex_6x6"].__setitem__("symmetrized_dale_krein_inertia", [3, 3, 0]), "CX_OPERATOR_INERTIA_MISMATCH", "cx krein")
    mutate_and_assert_all_3_layers(
        lambda p: p["pillar2_cx_attractor_and_supergraph"]["central_complex_triads_w10"].__setitem__(
            "observed_incoherent_ffl_fraction_q",
            p["pillar2_cx_attractor_and_supergraph"]["central_complex_triads_w10"]["null_incoherent_ffl_fraction_q"],
        ),
        "CX_INCOHERENT_FFL_EXCESS",
        "cx inc ffl eq null",
    )
    mutate_and_assert_all_3_layers(
        lambda p: p["pillar2_cx_attractor_and_supergraph"]["central_complex_triads_w10"].__setitem__(
            "observed_neg_3cycle_fraction_q",
            p["pillar2_cx_attractor_and_supergraph"]["central_complex_triads_w10"]["null_neg_3cycle_fraction_q"],
        ),
        "CX_NEG_3CYC_EXCESS",
        "cx neg 3cyc eq null",
    )
    mutate_and_assert_all_3_layers(lambda p: p["pillar2_cx_attractor_and_supergraph"]["central_complex_triads_w10"].__setitem__("active_nodes", 1), "P2_REPLAY_MISMATCH", "p2 replay")

    # Pillar 3 forgeries (incl. non-dict crash resistance)
    mutate_and_assert_all_3_layers(lambda p: p["pillar3_wave9_portal_engineering"].__setitem__("fly_racer_four_arm_tail_risk", "bad"), "TYPE_ERROR", "p3.fr str")
    mutate_and_assert_all_3_layers(lambda p: p["pillar3_wave9_portal_engineering"].__setitem__("fruitfly_calculator", "bad"), "TYPE_ERROR", "p3.fc str")
    mutate_and_assert_all_3_layers(lambda p: p["pillar3_wave9_portal_engineering"]["fruitfly_calculator"].__setitem__("lif_may_fire_pruned_witness", "bad"), "TYPE_ERROR", "p3.lif_pw str")
    mutate_and_assert_all_3_layers(lambda p: p["pillar3_wave9_portal_engineering"]["fly_racer_four_arm_tail_risk"].__setitem__("fly_minus_mlp_3sigma_margin_q", "0"), "FLY_RACER_MARGIN_NONPOS", "fly-racer margin")
    mutate_and_assert_all_3_layers(lambda p: p["pillar3_wave9_portal_engineering"]["fruitfly_calculator"]["lif_may_fire_pruned_witness"].__setitem__("never_reached_theta", False), "LIF_WITNESS_INVALID", "lif witness")
    mutate_and_assert_all_3_layers(lambda p: p["pillar3_wave9_portal_engineering"]["nfly_law5_bandwidth_bridge"].__setitem__("spmv_edges", 1), "P3_REPLAY_MISMATCH", "p3 replay")

    # Pillar 4 forgeries (incl. non-dict/str crash resistance)
    mutate_and_assert_all_3_layers(lambda p: p["pillar4_lean4_and_provenance"].__setitem__("honest_novelty_scope", "bad"), "TYPE_ERROR", "p4.hns str")
    mutate_and_assert_all_3_layers(lambda p: p["pillar4_lean4_and_provenance"]["honest_novelty_scope"].__setitem__("n2_open_claims_count", "0"), "TYPE_ERROR", "n2 str")
    mutate_and_assert_all_3_layers(lambda p: p["pillar4_lean4_and_provenance"]["honest_novelty_scope"].__setitem__("n2_open_claims_count", 1), "RANGE_ERROR", "n2 claim > 0")
    mutate_and_assert_all_3_layers(lambda p: p["pillar4_lean4_and_provenance"]["honest_novelty_scope"].__setitem__("n2_open_claims_count", -1), "RANGE_ERROR", "n2 claim < 0")
    mutate_and_assert_all_3_layers(lambda p: p["pillar4_lean4_and_provenance"].__setitem__("license", "MIT"), "P4_REPLAY_MISMATCH", "p4 replay")

    # Direct full_replay divergence guard test (kills M132 without weakening SEC)
    orig_build = oracle.build_certificate
    try:
        oracle.build_certificate = lambda anc=None: {"diverged": True}  # type: ignore[assignment]
        expect_s102_error(
            lambda: verifier.verify_certificate_dict(base, full_replay=True),
            "FULL_REPLAY_MISMATCH",
            "full_replay mismatch guard",
        )
    finally:
        oracle.build_certificate = orig_build


# ---------------------------------------------------------------------------
# T06: R12-Grade Static Lean 4 Scanner (All Attacks Blocked + 0 FP Controls)
# ---------------------------------------------------------------------------


def test_t06_r12_lean4_scanner() -> None:
    attacks = [
        "theorem t : True := by sorry",
        "theorem t : True := by admit",
        "axiom bad : False",
        "unsafe def f : Nat := 0",
        "theorem t : 1 = 1 := by native_decide",
        "theorem t : False := _root_.sorryAx False false",
        "def x := Lean.ofReduceBool true",
        "def x := Lean.ofReduceNat 0",
        "def x := Lean.trustCompiler",
        "def x := Lean.Meta.mkSorry",
        "def f (x : Nat) := dbg_trace x; x",
        "def f (x : Nat) := dbgTrace x (fun _ => x)",
        "def f (x : Nat) := dbgTraceVal x",
        "def f (x : Nat) := dbgTraceIfShared x x",
        "def f (x : Nat) := dbgSleep 1 (fun _ => x)",
        "def f (x : Nat) := dbgStackTrace (fun _ => x)",
        "def f (x : Nat) := dbg_sleep 1 x",
        "def f (x : Nat) := dbg_stack_trace x",
        "def f := panic! (String.ofList [])",
        "def f := unreachable!",
        "def f := panicWithPosWithDecl",
        "@[term_elab x] def f := 0",
        "@[command_elab x] def f := 0",
        "@[tactic x] def f := 0",
        "@[macro x] def f := 0",
        "set_option warn.sorry false",
        "debug.skipKernelTC",
        "debug.terminalTacticsAsSorry",
        "warn.sorry",
        "theorem t : True := by bv_decide",
        "opaque f : Nat",
        "partial def loop : Nat := loop",
        "initialize ref : IO.Ref Nat ← IO.mkRef 0",
        "builtin_initialize ref : IO.Ref Nat ← IO.mkRef 0",
        "@[export my_c_sym] def f : Nat := 1",
        "attribute [export my_c_sym] f",
        "@[init] def f : IO Unit := pure ()",
        "attribute [init] f",
        "@[builtin_init] def f : IO Unit := pure ()",
        "attribute [builtin_init] f",
        "@[extern c_fn] def f : Nat := 0",
        "@[implemented_by g] def f : Nat := 0",
        "@[simp",
        "#eval 1 + 1",
        "#exit",
        "#guard_msgs in #print axioms DrosophilaConnectomeOperators.dale_signed_partition_identity",
        "#print Nat",
        "theorem t : 1 = 1 := by decide +revert +native",
        "theorem t : 1 = 1 := by decide -kernel +native",
        "theorem t : 1 = 1 := by decide (native := false\n|| true)",
        "theorem t : 1 = 1 := by decide +revert (config := { native })",
        "theorem t : 1 = 1 := by decide (config := { ({} : _) with native })",
        "def cfg : DecideConfig := { native := true }",
        "theorem «sorry» : True := trivial",
        'def s := "quoted"',
        "import Mathlib.Data.Rat.Basic",
        "-- comment line\ntheorem t : True := by sorry",
        "]\n@[init] def f : IO Unit := pure ()",
    ]
    for snippet in attacks:
        hits = verifier.scan_lean4_source_r12(snippet)
        check(len(hits) > 0, f"R12 scanner missed attack: {snippet!r}")

    expect_s102_error(lambda: verifier.scan_lean4_source_r12("/- unclosed"), "LEAN4_UNTERMINATED_COMMENT", "unclosed comment")
    expect_s102_error(lambda: verifier.scan_lean4_source_r12("a\x00b"), "NUL_BYTE_FORBIDDEN", "nul lean")

    # Clean controls (0 FP)
    controls = [
        "/- /- nested sorry comment -/ -/\ntheorem ok : True := trivial\n",
        "-- sorry axiom native_decide dbgTrace\ntheorem ok : True := trivial\n",
        "-- trailing comment at eof without newline",
        "def div_test := 4 / 2\n",
        "theorem ok : 1 = 1 := by decide (native := false)\n",
        "theorem ok : 1 = 1 := by decide (config := { native := false })\n",
        "export Nat (succ)\n",
        "attribute [simp] init\n",
        "def g (x : SmoothShell) := x.partial\n",
        "#print axioms DrosophilaConnectomeOperators.dale_signed_partition_identity\n",
    ]
    for ctrl in controls:
        hits = verifier.scan_lean4_source_r12(ctrl)
        check(len(hits) == 0, f"R12 false positive on control {ctrl!r}: {hits}")


# ---------------------------------------------------------------------------
# T07: Lean Artifact Verifier (Live, Lean-less, Fake-Lean Parser Coverage)
# ---------------------------------------------------------------------------


def test_t07_lean_verifier_and_resolver() -> None:
    lean_p = oracle.TRACK_DIR / oracle.PINNED_LEAN_FILES["lean_source"]
    real_src = lean_p.read_text(encoding="utf-8")

    expect_s102_error(
        lambda: verifier.verify_lean_artifact(lean_p, require_live_lean=1),  # type: ignore[arg-type]
        "TYPE_ERROR",
        "non-bool require_live_lean",
    )
    expect_s102_error(
        lambda: verifier.verify_lean_artifact(lean_p, expected_sha256="0" * 64),
        "LEAN_SHA_MISMATCH",
        "lean sha mismatch",
    )

    with tempfile.TemporaryDirectory(prefix="s102_t07_") as td:
        tdir = Path(td)
        # Invalid UTF-8
        bad_utf = tdir / "bad_utf.lean"
        bad_utf.write_bytes(b"\xff\xfe")
        expect_s102_error(lambda: verifier.verify_lean_artifact(bad_utf), "INVALID_UTF8", "lean bad utf8")

        # Banned construct
        bad_con = tdir / "bad_con.lean"
        bad_con.write_text(real_src + "\n#eval 1\n", encoding="utf-8")
        expect_s102_error(lambda: verifier.verify_lean_artifact(bad_con), "LEAN4_BANNED_CONSTRUCT", "banned lean")

        # Missing theorem declaration
        miss_thm = tdir / "miss_thm.lean"
        miss_thm.write_text(
            real_src.replace("theorem dale_signed_partition_identity", "theorem renamed_thm"),
            encoding="utf-8",
        )
        expect_s102_error(lambda: verifier.verify_lean_artifact(miss_thm), "LEAN4_MISSING_THEOREM", "missing thm")

        # Missing #print axioms
        miss_pr = tdir / "miss_pr.lean"
        miss_pr.write_text(
            real_src.replace(
                "#print axioms DrosophilaConnectomeOperators.dale_signed_partition_identity",
                "",
            ),
            encoding="utf-8",
        )
        expect_s102_error(lambda: verifier.verify_lean_artifact(miss_pr), "LEAN4_MISSING_AXIOM_PRINT", "missing print")

        # Resolver branches: empty PATH + empty HOME -> None
        res_none = _with_env({"PATH": "", "HOME": ""}, verifier.resolve_lean_executable)
        check(res_none is None, "resolver should return None")
        _with_env(
            {"PATH": "", "HOME": ""},
            lambda: expect_s102_error(
                lambda: verifier.verify_lean_artifact(lean_p, require_live_lean=True),
                "LEAN_NOT_FOUND",
                "require_live_lean when missing",
            ),
        )
        # Lean-less pass when require_live_lean=False
        ll_res = _with_env(
            {"PATH": "", "HOME": ""},
            lambda: verifier.verify_lean_artifact(lean_p, require_live_lean=False),
        )
        check(ll_res["live_lean_executed"] is False and ll_res["static_r12_clean"] is True, "leanless ok")

        # Resolver finds $HOME/.elan/bin/lean only when regular + executable
        fake_home = tdir / "home"
        elan_bin = fake_home / ".elan" / "bin"
        elan_bin.mkdir(parents=True)
        # Directory named lean -> ignored
        (elan_bin / "lean").mkdir()
        check(
            _with_env({"PATH": "", "HOME": str(fake_home)}, verifier.resolve_lean_executable) is None,
            "dir named lean ignored",
        )
        (elan_bin / "lean").rmdir()
        # Non-executable file -> ignored
        (elan_bin / "lean").write_text("#!/bin/sh\n", encoding="utf-8")
        os.chmod(elan_bin / "lean", 0o600)
        check(
            _with_env({"PATH": "", "HOME": str(fake_home)}, verifier.resolve_lean_executable) is None,
            "non-exec lean ignored",
        )
        # Executable .local/bin/lean found
        loc_lean = _make_fake_lean(fake_home / ".local" / "bin", "exit 0")
        got_loc = _with_env({"PATH": "", "HOME": str(fake_home)}, verifier.resolve_lean_executable)
        check(got_loc == str(loc_lean), f"expected .local/bin/lean, got {got_loc}")

        # Fake lean subprocess error & stdout parsing branches (kills all mutants even in Lean-less CI!)
        fbin = tdir / "fbin"
        _make_fake_lean(fbin, "echo boom >&2; exit 1")
        _with_env(
            {"PATH": str(fbin), "HOME": ""},
            lambda: expect_s102_error(lambda: verifier.verify_lean_artifact(lean_p), "LEAN_COMPILE_FAILED", "rc!=0"),
        )
        _make_fake_lean(fbin, "echo warn >&2; exit 0")
        _with_env(
            {"PATH": str(fbin), "HOME": ""},
            lambda: expect_s102_error(lambda: verifier.verify_lean_artifact(lean_p), "LEAN_STDERR_NONEMPTY", "stderr"),
        )
        _make_fake_lean(fbin, "echo 'garbage line'")
        _with_env(
            {"PATH": str(fbin), "HOME": ""},
            lambda: expect_s102_error(lambda: verifier.verify_lean_artifact(lean_p), "LEAN_UNEXPECTED_STDOUT", "bad stdout"),
        )
        _make_fake_lean(
            fbin,
            "echo \"'DrosophilaConnectomeOperators.dale_signed_partition_identity' depends on axioms: [Classical.choice]\"",
        )
        _with_env(
            {"PATH": str(fbin), "HOME": ""},
            lambda: expect_s102_error(lambda: verifier.verify_lean_artifact(lean_p), "LEAN_DISALLOWED_AXIOM", "Classical.choice"),
        )
        _make_fake_lean(
            fbin,
            "echo \"'DrosophilaConnectomeOperators.dale_signed_partition_identity' does not depend on any axioms\"",
        )
        _with_env(
            {"PATH": str(fbin), "HOME": ""},
            lambda: expect_s102_error(lambda: verifier.verify_lean_artifact(lean_p), "LEAN_THEOREM_SET_MISMATCH", "partial thms"),
        )
        # Valid fake lean printing 1 no-axiom + 17 propext/Quot.sound + blank line, asserting all 10 LEAN/ELAN/LAKE/LD env vars scrubbed
        lines = [
            'if [ -n "${LEAN_PATH:-}${LEAN_OPTS:-}${LEAN_SRC_PATH:-}${LEAN_SYSROOT:-}${ELAN_TOOLCHAIN:-}${ELAN_HOME:-}${LAKE_HOME:-}${LEAN_CC:-}${LD_PRELOAD:-}${LD_LIBRARY_PATH:-}" ]; then echo env_leak >&2; exit 3; fi',
            "echo ''",
        ]
        for idx, thm in enumerate(oracle.LEAN_THEOREM_NAMES):
            if idx == 0:
                lines.append(f"echo \"'{thm}' does not depend on any axioms\"")
            else:
                lines.append(f"echo \"'{thm}' depends on axioms: [propext, Quot.sound]\"")
        _make_fake_lean(fbin, "\n".join(lines))
        fres = _with_env(
            {
                "PATH": str(fbin),
                "HOME": "",
                "LEAN_PATH": "/tmp/poison",
                "LEAN_OPTS": "--poison",
                "LEAN_SRC_PATH": "/tmp/poison_src",
                "LEAN_SYSROOT": "/tmp/poison",
                "ELAN_TOOLCHAIN": "malicious-toolchain",
                "ELAN_HOME": "/tmp/poison_elan",
                "LAKE_HOME": "/tmp/poison_lake",
                "LEAN_CC": "/tmp/poison_cc",
                "LD_PRELOAD": "/tmp/poison_preload.so",
                "LD_LIBRARY_PATH": "/tmp/poison_lib",
            },
            lambda: verifier.verify_lean_artifact(lean_p, require_live_lean=True),
        )
        check(fres["live_lean_executed"] is True and fres["theorems_verified"] == 18, "fake lean full pass")
        check(fres["axioms_by_theorem"][oracle.LEAN_THEOREM_NAMES[0]] == [], "empty axioms parsed")


# ---------------------------------------------------------------------------
# T08: External Dataset Verifier & CLI Error Handling
# ---------------------------------------------------------------------------


def test_t08_external_data_and_cli() -> None:
    with tempfile.TemporaryDirectory(prefix="s102_t08_") as td:
        tdir = Path(td)
        m_dir = tdir / "malecns"
        w_dir = tdir / "wave9"
        (w_dir / "repos").mkdir(parents=True)
        m_dir.mkdir(parents=True)
        m_bytes = b"feather_stub_12345"
        w_bytes = b"readme_stub_67890"
        (m_dir / "a.feather").write_bytes(m_bytes)
        (w_dir / "repos" / "r.md").write_bytes(w_bytes)
        fake_anc = {
            "malecns_external_pins": [
                {
                    "id": "ann",
                    "filename": "a.feather",
                    "bytes": len(m_bytes),
                    "sha256": hashlib.sha256(m_bytes).hexdigest(),
                }
            ],
            "wave9_portal_pins": [
                {
                    "id": "fc",
                    "relpath": "repos/r.md",
                    "bytes": len(w_bytes),
                    "sha256": hashlib.sha256(w_bytes).hexdigest(),
                }
            ],
        }
        res = verifier.verify_external_datasets(m_dir, w_dir, fake_anc)
        check(res == {"malecns_files_verified": 1, "wave9_files_verified": 1}, "ext pass")

        bad_mb = copy.deepcopy(fake_anc)
        bad_mb["malecns_external_pins"][0]["bytes"] = 999
        expect_s102_error(lambda: verifier.verify_external_datasets(m_dir, w_dir, bad_mb), "EXT_BYTES_MISMATCH", "m bytes")
        bad_ms = copy.deepcopy(fake_anc)
        bad_ms["malecns_external_pins"][0]["sha256"] = "0" * 64
        expect_s102_error(lambda: verifier.verify_external_datasets(m_dir, w_dir, bad_ms), "EXT_SHA_MISMATCH", "m sha")
        bad_wb = copy.deepcopy(fake_anc)
        bad_wb["wave9_portal_pins"][0]["bytes"] = 999
        expect_s102_error(lambda: verifier.verify_external_datasets(m_dir, w_dir, bad_wb), "WAVE9_BYTES_MISMATCH", "w bytes")
        bad_ws = copy.deepcopy(fake_anc)
        bad_ws["wave9_portal_pins"][0]["sha256"] = "0" * 64
        expect_s102_error(lambda: verifier.verify_external_datasets(m_dir, w_dir, bad_ws), "WAVE9_SHA_MISMATCH", "w sha")
        # Non-regular and hardlink external feather rejection
        (m_dir / "adir").mkdir()
        bad_dir = copy.deepcopy(fake_anc)
        bad_dir["malecns_external_pins"][0]["filename"] = "adir"
        expect_s102_error(lambda: verifier.verify_external_datasets(m_dir, w_dir, bad_dir), "NOT_REGULAR_FILE", "m dir")
        os.link(m_dir / "a.feather", m_dir / "a_hard.feather")
        expect_s102_error(lambda: verifier.verify_external_datasets(m_dir, w_dir, fake_anc), "HARDLINK_FORBIDDEN", "m hardlink")
        os.unlink(m_dir / "a_hard.feather")

    # CLI error cases
    for bad_argv, exp_code in (
        (["--unknown"], "CLI_UNKNOWN_ARG"),
        (["--check"], "CLI_MISSING_ARG"),
        (["--write"], "CLI_MISSING_ARG"),
        (["--verify-data", "/tmp"], "CLI_MISSING_ARG"),
        (["--standalone", "--write", "/tmp/x"], "CLI_CONFLICT"),
        (["--standalone", "--standalone"], "CLI_CONFLICT"),
        (["--check", "/tmp/x", "--standalone"], "CLI_CONFLICT"),
        (["--write", "/tmp/x", "--standalone"], "CLI_CONFLICT"),
        (["--standalone", "--check", "/tmp/x"], "CLI_CONFLICT"),
        (["--write", "/tmp/x", "--check", "/tmp/y"], "CLI_CONFLICT"),
        (["--check", "/tmp/x", "--check", "/tmp/y"], "CLI_CONFLICT"),
        (["--check", "/tmp/x", "--write", "/tmp/y"], "CLI_CONFLICT"),
    ):
        rc, _, err = _run_cli_capture(bad_argv)
        check(rc == 2, f"expected rc=2 for {bad_argv}, got {rc}")
        check(json.loads(err)["code"] == exp_code, f"expected {exp_code} for {bad_argv}, got {err}")

    # CLI --verify-data flag parsed cleanly (fails gracefully on nonexistent dir)
    rc_vd, _, err_vd = _run_cli_capture(["--verify-data", "/tmp/no_such_s102_m", "/tmp/no_such_s102_w"])
    check(rc_vd == 2 and "code" in json.loads(err_vd), "verify-data missing dir rejected")

    # Live subprocess symlinked $PWD test
    with tempfile.TemporaryDirectory(prefix="s102_pwd_") as td:
        real_d = Path(td) / "real"
        real_d.mkdir()
        sym_d = Path(td) / "link"
        os.symlink(real_d, sym_d)
        proc = subprocess.run(
            ["/bin/sh", "-c", f'cd -L "{sym_d}" && "{sys.executable}" -I -B "{verifier.__file__}" --standalone'],
            capture_output=True,
            text=True,
            check=False,
        )
        check(proc.returncode == 2, f"expected rc=2 on symlink PWD, got {proc.returncode}")
        check(json.loads(proc.stderr)["code"] == "SYMLINK_IN_PATH", f"expected SYMLINK_IN_PATH: {proc.stderr}")


ALL_TESTS: tuple[tuple[str, Callable[[], None]], ...] = (
    ("T01_roundtrip_and_pins", test_t01_roundtrip_and_pins),
    ("T02_zone_b_filesystem", test_t02_zone_b_filesystem),
    ("T03_strict_json_and_rationals", test_t03_strict_json_and_rationals),
    ("T04_oracle_operators_and_anchor", test_t04_oracle_operators_and_anchor),
    ("T05_resigned_semantic_forgeries", test_t05_resigned_semantic_forgeries),
    ("T06_r12_lean4_scanner", test_t06_r12_lean4_scanner),
    ("T07_lean_verifier_and_resolver", test_t07_lean_verifier_and_resolver),
    ("T08_external_data_and_cli", test_t08_external_data_and_cli),
)


def main() -> int:
    for name, fn in ALL_TESTS:
        fn()
        sys.stdout.write(f"PASS {name}\n")
    sys.stdout.write(f"ALL {len(ALL_TESTS)}/{len(ALL_TESTS)} S102 R5 TESTS PASSED\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
