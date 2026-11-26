#!/usr/bin/env python3
"""
Track S98 Hardened R5 Test Suite: 5-Org Cross-Language Trust Boundary Unification.

Pure stdlib, ZERO floats, ZERO bare asserts, ZERO .isdigit(), ZERO skips across
all execution modes (including bare `env -i PATH=/usr/bin:/bin`, `HOME=/nonexistent`,
and read-only CI directories).
"""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any, Callable, Dict, List, Tuple

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import s98_trust_boundary_oracle as oracle
import verify_s98_trust_boundary as verifier


class R5Failure(RuntimeError):
    """Explicit failure raised by assertion-free R5 checks."""


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise R5Failure(msg)


def check_raises(exc_type: type[BaseException], fn: Callable[[], Any], expected_code: str = "", label: str = "") -> None:
    try:
        fn()
    except exc_type as exc:
        if expected_code:
            got_code = getattr(exc, "code", "")
            check(got_code == expected_code, f"{label}: expected code {expected_code!r}, got {got_code!r} ({exc})")
        return
    raise R5Failure(f"{label}: expected {exc_type.__name__} ({expected_code}), but succeeded")


def resign_cert(payload: Dict[str, Any]) -> Dict[str, Any]:
    p_sha = hashlib.sha256(oracle.canonical_json_bytes(payload)).hexdigest()
    body = {
        "schema": oracle.SCHEMA_VERSION,
        "track_id": oracle.TRACK_ID,
        "payload_sha256": p_sha,
        "payload": payload,
    }
    c_sha = hashlib.sha256(oracle.canonical_json_bytes(body)).hexdigest()
    return {
        "schema": oracle.SCHEMA_VERSION,
        "track_id": oracle.TRACK_ID,
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "payload": payload,
    }


def _make_exec_script(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    os.chmod(str(path), 0o700)
    return path


def _with_env(overrides: Dict[str, str | None], fn: Callable[[], Any]) -> Any:
    saved: Dict[str, str | None] = {}
    for k, v in overrides.items():
        saved[k] = os.environ.get(k)
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        return fn()
    finally:
        for k, old in saved.items():
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old


def test_1_certificate_standalone_and_cli() -> None:
    cert_path = THIS_DIR / "s98_trust_boundary_certificate.json"
    cert = oracle.build_certificate()
    expected_bytes = oracle.canonical_json_bytes(cert) + b"\n"
    disk_bytes = cert_path.read_bytes()
    check(disk_bytes == expected_bytes, "certificate on disk differs from standalone oracle")

    # Oracle CLI --standalone --json and --write
    buf = io.StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = buf
        rc = oracle.main(["--standalone", "--json"])
    finally:
        sys.stdout = old_stdout
    check(rc == 0 and buf.getvalue().encode("utf-8") == expected_bytes, "oracle CLI --standalone --json mismatch")

    tmp_dir = tempfile.mkdtemp(prefix="s98_t1_")
    try:
        os.chmod(tmp_dir, 0o700)
        out_cert = Path(tmp_dir) / "written_cert.json"
        buf2 = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = buf2
            rc_w = oracle.main(["--write", str(out_cert)])
        finally:
            sys.stdout = old_stdout
        check(rc_w == 0 and buf2.getvalue() == "", "oracle --write should stay silent without --json")
        st_mode = stat.S_IMODE(os.lstat(str(out_cert)).st_mode)
        check(st_mode == 0o600, f"expected 0o600 on written cert, got {oct(st_mode)}")
        check(out_cert.read_bytes() == expected_bytes, "written cert bytes mismatch")

        # Exercise every oracle.main output-condition branch independently
        for o_args in (["--write", str(out_cert), "--json"], ["--write", str(out_cert), "--standalone"], []):
            buf_o = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = buf_o
                rc_o = oracle.main(o_args)
            finally:
                sys.stdout = old_stdout
            check(rc_o == 0 and buf_o.getvalue().encode("utf-8") == expected_bytes, f"oracle.main({o_args}) mismatch")

        # Verifier CLI --check, --no-replay, --json
        for argv_args in (
            ["--check", str(out_cert)],
            ["--check", str(out_cert), "--json"],
            ["--check", str(out_cert), "--no-replay", "--json"],
        ):
            out_buf = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = out_buf
                rc_v = verifier.main(argv_args)
            finally:
                sys.stdout = old_stdout
            check(rc_v == 0, f"verifier.main({argv_args}) failed with {rc_v}")
            if "--json" in argv_args:
                parsed_out = json.loads(out_buf.getvalue())
                check(parsed_out["status"] == "PASS", "CLI JSON status not PASS")
                check(parsed_out["full_replay"] == ("--no-replay" not in argv_args), "CLI full_replay mismatch")

        # Verifier CLI fail cases (text and --json) + usage error codes
        bad_file = Path(tmp_dir) / "bad.json"
        bad_file.write_bytes(b"{}\n")
        for fail_args, expect_json in (
            (["--check", str(bad_file)], False),
            (["--check", str(bad_file), "--json"], True),
        ):
            out_buf = io.StringIO()
            err_buf = io.StringIO()
            old_out, old_err = sys.stdout, sys.stderr
            try:
                sys.stdout, sys.stderr = out_buf, err_buf
                rc_f = verifier.main(fail_args)
            finally:
                sys.stdout, sys.stderr = old_out, old_err
            check(rc_f == 1, f"expected rc=1 for {fail_args}, got {rc_f}")
            if expect_json:
                jobj = json.loads(out_buf.getvalue())
                check(jobj["status"] == "FAIL" and jobj["code"] == "KEYSET_MISMATCH", f"bad json fail: {jobj}")
            else:
                check("KEYSET_MISMATCH" in err_buf.getvalue(), "missing error code on stderr")

        # Default 0-flag invocation checks canonical certificate & prints JSON (R4 parity)
        def_buf = io.StringIO()
        old_out = sys.stdout
        try:
            sys.stdout = def_buf
            rc_def = verifier.main([])
        finally:
            sys.stdout = old_out
        check(rc_def == 0 and json.loads(def_buf.getvalue())["status"] == "PASS", "default 0-flag verifier.main([]) failed")

        for bad_cli in (["--check", str(out_cert), "--verify-lean", str(out_cert)], ["--unknown-flag"]):
            err_buf = io.StringIO()
            old_err = sys.stderr
            try:
                sys.stderr = err_buf
                rc_u = verifier.main(bad_cli)
            finally:
                sys.stderr = old_err
            check(rc_u == 2, f"expected rc=2 for {bad_cli}, got {rc_u}")

        # Envelope tamper & strict full_replay type checks
        check_raises(verifier.S98Error, lambda: verifier.verify_certificate_dict(cert, full_replay=1), "INVALID_FULL_REPLAY", "int full_replay")  # type: ignore[arg-type]
        check_raises(verifier.S98Error, lambda: verifier.verify_certificate_dict([]), "TYPE_MISMATCH", "list cert")
        bad_keys = dict(cert)
        bad_keys["extra"] = 1
        check_raises(verifier.S98Error, lambda: verifier.verify_certificate_dict(bad_keys), "KEYSET_MISMATCH", "extra top key")
        for field, val, code in (
            ("schema", "wrong", "HEADER_MISMATCH"),
            ("track_id", "S99", "HEADER_MISMATCH"),
            ("payload_sha256", 123, "INVALID_HEX64"),
            ("payload_sha256", "a" * 63, "INVALID_HEX64"),
            ("payload_sha256", "A" * 64, "INVALID_HEX64"),
            ("certificate_sha256", "z" * 64, "INVALID_HEX64"),
            ("payload_sha256", "0" * 64, "PAYLOAD_SHA_MISMATCH"),
            ("certificate_sha256", "0" * 64, "CERT_SHA_MISMATCH"),
        ):
            mut = copy.deepcopy(cert)
            mut[field] = val
            check_raises(verifier.S98Error, lambda m=mut: verifier.verify_certificate_dict(m), code, f"envelope {field}")

        # Test ORACLE_DRIFT on FR1 while FR0 still passes
        orig_build = oracle.build_certificate
        try:
            def _fake_build() -> Dict[str, Any]:
                c2 = orig_build()
                c2["certificate_sha256"] = "0" * 64
                return c2

            oracle.build_certificate = _fake_build  # type: ignore[assignment]
            check(verifier.verify_certificate_dict(cert, full_replay=False)["status"] == "PASS", "FR0 should pass during oracle drift test")
            check_raises(verifier.S98Error, lambda: verifier.verify_certificate_dict(cert, full_replay=True), "ORACLE_DRIFT", "oracle drift")
        finally:
            oracle.build_certificate = orig_build  # type: ignore[assignment]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_2_safe_io_and_strict_json_zone_b() -> None:
    tmp_dir = tempfile.mkdtemp(prefix="s98_t2_")
    try:
        os.chmod(tmp_dir, 0o700)
        td = Path(tmp_dir)
        real_dir = td / "real"
        real_dir.mkdir()
        reg_file = real_dir / "cert.json"
        cert = oracle.build_certificate()
        canon_bytes = oracle.canonical_json_bytes(cert) + b"\n"
        reg_file.write_bytes(canon_bytes)

        # Invalid path types, empty, NUL, traversal, missing
        check_raises(verifier.S98Error, lambda: verifier.read_safe_regular_file(123), "INVALID_PATH_TYPE", "int path")
        check_raises(verifier.S98Error, lambda: verifier.read_safe_regular_file(""), "INVALID_PATH", "empty path")
        check_raises(verifier.S98Error, lambda: verifier.read_safe_regular_file("a\x00b"), "INVALID_PATH", "nul path")
        check_raises(verifier.S98Error, lambda: verifier.read_safe_regular_file(str(real_dir) + "/../real/cert.json"), "PARENT_TRAVERSAL", "dotdot")
        check_raises(verifier.S98Error, lambda: verifier.read_safe_regular_file(td / "no_such_file.json"), "PATH_UNREADABLE", "missing")

        # Symlink target, parent symlink, PWD symlink, directory, FIFO, permission denied
        sym_file = td / "sym.json"
        sym_file.symlink_to(reg_file)
        check_raises(verifier.S98Error, lambda: verifier.read_safe_regular_file(sym_file), "SYMLINK_FORBIDDEN", "file symlink")

        sym_dir = td / "sym_dir"
        sym_dir.symlink_to(real_dir)
        check_raises(verifier.S98Error, lambda: verifier.read_safe_regular_file(sym_dir / "cert.json"), "SYMLINK_FORBIDDEN", "parent symlink")

        old_cwd = os.getcwd()
        try:
            os.chdir(str(real_dir))
            _with_env({"PWD": str(sym_dir)}, lambda: check_raises(verifier.S98Error, lambda: verifier.read_safe_regular_file("cert.json"), "PWD_SYMLINK", "pwd symlink"))
            got_rel = _with_env({"PWD": ""}, lambda: verifier.read_safe_regular_file("cert.json"))
            check(got_rel == canon_bytes, "relative read without PWD failed")
            got_pwd = _with_env({"PWD": os.path.realpath(str(real_dir))}, lambda: verifier.read_safe_regular_file("cert.json"))
            check(got_pwd == canon_bytes, "relative read with real PWD failed")
        finally:
            os.chdir(old_cwd)

        check_raises(verifier.S98Error, lambda: verifier.read_safe_regular_file(real_dir), "NOT_REGULAR_FILE", "directory")

        fifo_path = td / "pipe.fifo"
        os.mkfifo(str(fifo_path))
        check_raises(verifier.S98Error, lambda: verifier.read_safe_regular_file(fifo_path), "NOT_REGULAR_FILE", "fifo")

        unreadable = td / "no_read.json"
        unreadable.write_bytes(b"{}\n")
        os.chmod(str(unreadable), 0o000)
        try:
            if os.geteuid() != 0:
                check_raises(verifier.S98Error, lambda: verifier.read_safe_regular_file(unreadable), "OPEN_FAILED", "chmod 000")
        finally:
            os.chmod(str(unreadable), 0o600)

        # File size exact boundary MAX_FILE_BYTES vs MAX_FILE_BYTES + 1
        exact_max = td / "exact_max.bin"
        exact_max.write_bytes(b"a" * verifier.MAX_FILE_BYTES)
        check(len(verifier.read_safe_regular_file(exact_max)) == verifier.MAX_FILE_BYTES, "exact MAX_FILE_BYTES rejected")
        too_big = td / "too_big.bin"
        too_big.write_bytes(b"a" * (verifier.MAX_FILE_BYTES + 1))
        check_raises(verifier.S98Error, lambda: verifier.read_safe_regular_file(too_big), "FILE_TOO_LARGE", "file > MAX_FILE_BYTES")

        # Non-canonical bytes (CRLF, pretty-printed, missing LF)
        crlf_file = td / "crlf.json"
        crlf_file.write_bytes(oracle.canonical_json_bytes(cert) + b"\r\n")
        check_raises(verifier.S98Error, lambda: verifier.verify_certificate_file(crlf_file), "NONCANONICAL_BYTES", "CRLF")
        pretty_file = td / "pretty.json"
        pretty_file.write_bytes((json.dumps(cert, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        check_raises(verifier.S98Error, lambda: verifier.verify_certificate_file(pretty_file), "NONCANONICAL_BYTES", "pretty")

        # parse_strict_json_bytes exhaustive checks (including exact MAX_FILE_BYTES acceptance)
        exact_json = b"{" + b" " * (verifier.MAX_FILE_BYTES - 2) + b"}"
        check(verifier.parse_strict_json_bytes(exact_json) == {}, "exact MAX_FILE_BYTES JSON rejected")
        check_raises(verifier.S98Error, lambda: verifier.parse_strict_json_bytes(b" " * (verifier.MAX_FILE_BYTES + 1)), "FILE_TOO_LARGE", "raw > MAX")
        check_raises(verifier.S98Error, lambda: verifier.parse_strict_json_bytes(b"\xff\xfe"), "INVALID_UTF8", "bad utf8")
        check_raises(verifier.S98Error, lambda: verifier.parse_strict_json_bytes(b'{"a":"\x00"}'), "NUL_IN_JSON", "raw nul")
        check_raises(verifier.S98Error, lambda: verifier.parse_strict_json_bytes(b"{"), "INVALID_JSON", "bad json")
        check_raises(verifier.S98Error, lambda: verifier.parse_strict_json_bytes(b'{"a":' * 5000 + b"1" + b"}" * 5000), "", "deep recursion json")
        check_raises(verifier.S98Error, lambda: verifier.parse_strict_json_bytes(b'{"a":' * 65 + b"1" + b"}" * 65), "MAX_DEPTH_EXCEEDED", "depth 65 json")
        check_raises(verifier.S98Error, lambda: verifier.parse_strict_json_bytes(b"[1,2]"), "ROOT_NOT_OBJECT", "array root")
        check_raises(verifier.S98Error, lambda: verifier.parse_strict_json_bytes(b'{"x":1.5}'), "JSON_FLOAT_FORBIDDEN", "float")
        check_raises(verifier.S98Error, lambda: verifier.parse_strict_json_bytes(b'{"x":NaN}'), "JSON_CONSTANT_FORBIDDEN", "NaN")
        check_raises(verifier.S98Error, lambda: verifier.parse_strict_json_bytes(b'{"x":-0}'), "NEGATIVE_ZERO", "-0")
        check_raises(verifier.S98Error, lambda: verifier.parse_strict_json_bytes(b'{"a":1,"a":2}'), "JSON_DUPLICATE_KEY", "dup key")

        # Integer digit (2467) vs bit (8192) independent boundaries (including direct _parse_int_strict)
        pos_ok = 10**2466
        neg_ok = -(10**2466)
        check(len(str(pos_ok)) == 2467 and pos_ok.bit_length() <= 8192, "sanity 10**2466")
        p_ok = verifier.parse_strict_json_bytes(f'{{"p":{pos_ok},"n":{neg_ok}}}'.encode("ascii"))
        check(p_ok["p"] == pos_ok and p_ok["n"] == neg_ok, "exact 2467-digit +/- int should pass")
        bit_over = 1 << 8192
        check(len(str(bit_over)) == 2467 and bit_over.bit_length() == 8193, "sanity 2**8192")
        check_raises(verifier.S98Error, lambda: verifier._parse_int_strict(str(bit_over)), "INT_BITS_EXCEEDED", "direct _parse_int_strict 8193 bits")
        check_raises(verifier.S98Error, lambda: verifier.parse_strict_json_bytes(f'{{"x":{bit_over}}}'.encode("ascii")), "INT_BITS_EXCEEDED", "8193 bits")
        dig_over = "1" + "0" * 2467
        check_raises(verifier.S98Error, lambda: verifier.parse_strict_json_bytes(f'{{"x":{dig_over}}}'.encode("ascii")), "INT_DIGITS_EXCEEDED", "2468 digits")

        # _validate_tree direct checks (depth, nodes, NUL, surrogates, strict runtime subclasses)
        nested_ok: Any = 0
        for _ in range(verifier.MAX_JSON_DEPTH):
            nested_ok = [nested_ok]
        verifier._validate_tree(nested_ok)
        check_raises(verifier.S98Error, lambda: verifier._validate_tree([nested_ok]), "MAX_DEPTH_EXCEEDED", "depth 65")

        exact_nodes = [0] * (verifier.MAX_JSON_NODES - 1)
        verifier._validate_tree(exact_nodes)
        check_raises(verifier.S98Error, lambda: verifier._validate_tree([0] * verifier.MAX_JSON_NODES), "MAX_NODES_EXCEEDED", "nodes 16385")

        check_raises(verifier.S98Error, lambda: verifier._validate_tree({1: "a"}), "NON_STRING_KEY", "int key")
        check_raises(verifier.S98Error, lambda: verifier._validate_tree({"a\x00b": 1}), "NUL_IN_STRING", "nul key")
        check_raises(verifier.S98Error, lambda: verifier._validate_tree({"a\ud800": 1}), "SURROGATE_STRING", "surrogate key lo")
        check_raises(verifier.S98Error, lambda: verifier._validate_tree({"a\udfff": 1}), "SURROGATE_STRING", "surrogate key hi")
        check_raises(verifier.S98Error, lambda: verifier._validate_tree({"k": "v\x00"}), "NUL_IN_STRING", "nul val")
        check_raises(verifier.S98Error, lambda: verifier._validate_tree({"k": "\ud800"}), "SURROGATE_STRING", "surrogate val lo")
        check_raises(verifier.S98Error, lambda: verifier._validate_tree({"k": "\udfff"}), "SURROGATE_STRING", "surrogate val hi")
        verifier._validate_tree({"k": "\ud7ff\ue000", "b": True, "n": None, "i": (1 << 8192) - 1})
        check_raises(verifier.S98Error, lambda: verifier._validate_tree({"i": 1 << 8192}), "INT_BITS_EXCEEDED", "tree 8193 bits")

        class SubInt(int):
            pass

        class SubStr(str):
            pass

        class SubDict(dict):
            pass

        class SubList(list):
            pass

        for bad_val in (SubInt(1), SubStr("a"), SubDict(a=1), SubList([1]), (1, 2)):
            check_raises(verifier.S98Error, lambda v=bad_val: verifier._validate_tree({"x": v}), "FORBIDDEN_TYPE", f"subclass {type(bad_val).__name__}")

        # _parse_q_dict checks
        check(verifier._parse_q_dict({"num": -3, "den": 4}, "q") == Fraction(-3, 4), "valid negative q")
        check_raises(verifier.S98Error, lambda: verifier._parse_q_dict({"num": True, "den": 1}, "q"), "RATIONAL_TYPE", "bool num")
        check_raises(verifier.S98Error, lambda: verifier._parse_q_dict({"num": 1, "den": True}, "q"), "RATIONAL_TYPE", "bool den")
        check_raises(verifier.S98Error, lambda: verifier._parse_q_dict({"num": 1, "den": 0}, "q"), "RATIONAL_DEN", "zero den")
        check_raises(verifier.S98Error, lambda: verifier._parse_q_dict({"num": 1, "den": -2}, "q"), "RATIONAL_DEN", "neg den")
        check_raises(verifier.S98Error, lambda: verifier._parse_q_dict({"num": 2, "den": 4}, "q"), "RATIONAL_UNREDUCED", "unreduced q")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_3_pillar1_zone_canon_and_rust_parity() -> None:
    # fmt_dec4 boundaries
    check(oracle.fmt_dec4(Fraction(0, 1)) == "0.0000", "fmt_dec4 zero")
    check(oracle.fmt_dec4(Fraction(-3, 4)) == "-0.7500", "fmt_dec4 neg")
    check(oracle.fmt_dec4(Fraction(9, 32)) == "0.2813", "fmt_dec4 pos")

    # Exhaustive iterative parser & encoder accept cases
    for name, prof, raw_inp in oracle.ZONE_CANON_ACCEPT_VECTORS:
        c1, r1, d1 = oracle.canonicalize_zone_v1(raw_inp, prof)
        c2, r2, d2 = verifier._independent_zone_canon(raw_inp, prof)
        check(c1 == c2 and r1 == r2 and d1 == d2, f"parser drift on {name}")

    # All JSON escape sequences, UTF-8 vs ASCII boundary code points, empty containers, bools/null
    esc_inp = r'{"a":"\"\\\/\b\f\n\r\t\u0001\u001f ~\u007f\u0080\ud7ff\ue000\uffff\ud800\udc00\udbff\udfff","b":[true,false,null,[],{}],"c":0}'
    c_u8, _, _ = oracle.canonicalize_zone_v1(esc_inp, "v1_utf8")
    c_as, _, _ = oracle.canonicalize_zone_v1(esc_inp, "v1_ascii")
    c_u8_ind, _, _ = verifier._independent_zone_canon(esc_inp, "v1_utf8")
    c_as_ind, _, _ = verifier._independent_zone_canon(esc_inp, "v1_ascii")
    check(c_u8 == c_u8_ind and c_as == c_as_ind and c_u8 != c_as, "escape/codepoint encoding parity failed")

    # Exact integer range and container depth/node boundaries
    check(oracle.parse_zone_canon_iterative(str(oracle.JS_SAFE_INT_MAX), "mde_v0_utf8") == oracle.JS_SAFE_INT_MAX, "js max")
    check(oracle.parse_zone_canon_iterative(str(-oracle.JS_SAFE_INT_MAX), "mde_v0_utf8") == -oracle.JS_SAFE_INT_MAX, "js min")
    check(oracle.parse_zone_canon_iterative(str(oracle.SIGNED_INT256_MAX), "v1_utf8") == oracle.SIGNED_INT256_MAX, "i256 max")
    check(oracle.parse_zone_canon_iterative(str(oracle.SIGNED_INT256_MIN), "v1_utf8") == oracle.SIGNED_INT256_MIN, "i256 min")

    depth64_arr = "[" * 64 + "]" * 64
    check(oracle.parse_zone_canon_iterative(depth64_arr, "v1_utf8") is not None, "arr depth 64 should pass")
    depth64_obj = '{"a":' * 63 + "{}" + "}" * 63
    check(oracle.parse_zone_canon_iterative(depth64_obj, "v1_utf8") is not None, "obj depth 64 should pass")
    depth65_obj = '{"a":' * 64 + "{}" + "}" * 64
    check_raises(oracle.ZoneCanonError, lambda: oracle.parse_zone_canon_iterative(depth65_obj, "v1_utf8"), "MAX_DEPTH_EXCEEDED", "obj depth 65")

    nodes4096 = "[" + ",".join(["0"] * 4095) + "]"
    check(len(oracle.parse_zone_canon_iterative(nodes4096, "v1_utf8")) == 4095, "4096 nodes should pass")
    nodes4097 = "[" + ",".join(["0"] * 4096) + "]"
    check_raises(oracle.ZoneCanonError, lambda: oracle.parse_zone_canon_iterative(nodes4097, "v1_utf8"), "MAX_NODES_EXCEEDED", "4097 nodes")

    # Exact MAX_INPUT_BYTES boundary (1 MiB accepted vs 1 MiB + 1 rejected)
    max_str_ok = '"' + ("a" * (oracle.ZONE_CANON_MAX_BYTES - 2)) + '"'
    check(len(max_str_ok) == oracle.ZONE_CANON_MAX_BYTES, "sanity max_str_ok")
    check(len(oracle.parse_zone_canon_iterative(max_str_ok, "v1_utf8")) == oracle.ZONE_CANON_MAX_BYTES - 2, "exact 1 MiB input should pass")
    check_raises(oracle.ZoneCanonError, lambda: oracle.parse_zone_canon_iterative(max_str_ok + " ", "v1_utf8"), "INPUT_TOO_LARGE", "1 MiB + 1 oracle")

    # Every reject code in oracle iterative parser
    reject_cases: List[Tuple[str, str, str]] = [
        ("bad_profile", "{}", "UNKNOWN_PROFILE"),
        ("v1_utf8", "", "UNEXPECTED_EOF"),
        ("v1_utf8", "tru", "BAD_TOKEN"),
        ("v1_utf8", "{} 1", "TRAILING_DATA"),
        ("v1_utf8", "{1:2}", "EXPECTED_KEY"),
        ("v1_utf8", "{", "EXPECTED_KEY"),
        ("v1_utf8", '{"a" 1}', "EXPECTED_COLON"),
        ("v1_utf8", '{"a"', "EXPECTED_COLON"),
        ("v1_utf8", '{"a":1,"a":2}', "DUPLICATE_KEY"),
        ("v1_utf8", '{"a":1,2:3}', "EXPECTED_KEY"),
        ("v1_utf8", '{"a":1,', "EXPECTED_KEY"),
        ("v1_utf8", '{"a":1,"b" 2}', "EXPECTED_COLON"),
        ("v1_utf8", '{"a":1,"b"', "EXPECTED_COLON"),
        ("v1_utf8", '{"a":1 "b":2}', "EXPECTED_COMMA_OR_RBRACE"),
        ("v1_utf8", '{"a":1', "EXPECTED_COMMA_OR_RBRACE"),
        ("v1_utf8", "[", "UNEXPECTED_EOF"),
        ("v1_utf8", "[1 2]", "EXPECTED_COMMA_OR_RBRACKET"),
        ("v1_utf8", "[1", "EXPECTED_COMMA_OR_RBRACKET"),
        ("v1_utf8", '"\\q"', "INVALID_ESCAPE"),
        ("v1_utf8", '"\\', "TRUNCATED_ESCAPE"),
        ("v1_utf8", '"abc', "UNTERMINATED_STRING"),
        ("v1_utf8", '"\x1f"', "UNESCAPED_CONTROL_CHAR"),
        ("v1_utf8", '"\ud800"', "LONE_SURROGATE"),
        ("v1_utf8", '"\udfff"', "LONE_SURROGATE"),
        ("v1_utf8", '"\\u123"', "BAD_HEX_ESCAPE"),
        ("v1_utf8", '"\\u123', "TRUNCATED_UNICODE_ESCAPE"),
        ("v1_utf8", '"\\u123g"', "BAD_HEX_ESCAPE"),
        ("v1_utf8", '"\\ud800"', "LONE_HIGH_SURROGATE"),
        ("v1_utf8", '"\\ud800x"', "LONE_HIGH_SURROGATE"),
        ("v1_utf8", '"\\ud800\\u12"', "LONE_HIGH_SURROGATE"),
        ("v1_utf8", '"\\ud800abcdef"', "LONE_HIGH_SURROGATE"),
        ("v1_utf8", '"\\ud800\\u0041"', "INVALID_LOW_SURROGATE"),
        ("v1_utf8", '"\\ud800\\udbff"', "INVALID_LOW_SURROGATE"),
        ("v1_utf8", '"\\ud800\\ue000"', "INVALID_LOW_SURROGATE"),
        ("v1_utf8", '"\\udc00"', "LONE_LOW_SURROGATE"),
        ("v1_utf8", '"\\udfff"', "LONE_LOW_SURROGATE"),
        ("v1_utf8", '"\\u0000"', "NUL_FORBIDDEN"),
        ("v1_utf8", "-", "INVALID_NUMBER"),
        ("v1_utf8", "-a", "INVALID_NUMBER"),
        ("v1_utf8", "01", "LEADING_ZERO"),
        ("v1_utf8", "-0", "NEGATIVE_ZERO"),
        ("v1_utf8", "0.5", "FLOAT_FORBIDDEN"),
        ("v1_utf8", "1e2", "FLOAT_FORBIDDEN"),
        ("v1_utf8", "1E2", "FLOAT_FORBIDDEN"),
        ("v1_utf8", "1" + "0" * 78, "INT_DIGITS_EXCEEDED"),
        ("mde_v0_utf8", str(oracle.JS_SAFE_INT_MAX + 1), "INT_RANGE_EXCEEDED"),
        ("mde_v0_utf8", str(-(oracle.JS_SAFE_INT_MAX + 1)), "INT_RANGE_EXCEEDED"),
        ("v1_utf8", str(oracle.SIGNED_INT256_MAX + 1), "INT_256_EXCEEDED"),
        ("v1_utf8", str(oracle.SIGNED_INT256_MIN - 1), "INT_256_EXCEEDED"),
        ("v1_utf8", "1" + "0" * 77, "INT_256_EXCEEDED"),
    ]
    for prof, inp, exp_code in reject_cases:
        check_raises(oracle.ZoneCanonError, lambda p=prof, s=inp: oracle.canonicalize_zone_v1(s, p), exp_code, f"zc reject {exp_code} on {inp!r}")

    # Direct coverage of verifier._independent_zone_canon reject & boundary branches
    ind_rejects: List[Tuple[str, str, str]] = [
        ("v1_utf8", max_str_ok + " ", "INPUT_TOO_LARGE"),
        ("v1_utf8", "-0", "NEGATIVE_ZERO"),
        ("v1_utf8", "1.5", "FLOAT_FORBIDDEN"),
        ("v1_utf8", "NaN", "BAD_TOKEN"),
        ("v1_utf8", "1" + "0" * 78, "INT_DIGITS_EXCEEDED"),
        ("v1_utf8", "-" + "1" + "0" * 78, "INT_DIGITS_EXCEEDED"),
        ("mde_v0_utf8", str(oracle.JS_SAFE_INT_MAX + 1), "INT_RANGE_EXCEEDED"),
        ("v1_utf8", str(oracle.SIGNED_INT256_MAX + 1), "INT_256_EXCEEDED"),
        ("v1_utf8", str(oracle.SIGNED_INT256_MIN - 1), "INT_256_EXCEEDED"),
        ("v1_utf8", "1" + "0" * 77, "INT_256_EXCEEDED"),
        ("v1_utf8", '{"a":1,"a":2}', "DUPLICATE_KEY"),
        ("v1_utf8", '{"a\\u0000":1}', "NUL_FORBIDDEN"),
        ("v1_utf8", '{"s":"\\u0000"}', "NUL_FORBIDDEN"),
        ("v1_utf8", '{"s":"\\ud800"}', "LONE_HIGH_SURROGATE"),
        ("v1_utf8", '{"s":"\\udbff"}', "LONE_HIGH_SURROGATE"),
        ("v1_utf8", '{"s":"\\udc00"}', "LONE_LOW_SURROGATE"),
        ("v1_utf8", '{"s":"\\udfff"}', "LONE_LOW_SURROGATE"),
        ("v1_utf8", depth65_obj, "MAX_DEPTH_EXCEEDED"),
        ("v1_utf8", "[" * 65 + "]" * 65, "MAX_DEPTH_EXCEEDED"),
        ("v1_utf8", nodes4097, "MAX_NODES_EXCEEDED"),
        ("v1_utf8", "{", "ZONE_PARSE_ERR"),
    ]
    for prof, inp, exp_code in ind_rejects:
        check_raises(verifier.S98Error, lambda p=prof, s=inp: verifier._independent_zone_canon(s, p), exp_code, f"ind reject {exp_code}")
    # Also verify exact boundary acceptance in _independent_zone_canon
    verifier._independent_zone_canon(max_str_ok, "v1_utf8")
    verifier._independent_zone_canon(depth64_arr, "v1_utf8")
    verifier._independent_zone_canon(depth64_obj, "v1_utf8")
    verifier._independent_zone_canon(nodes4096, "v1_utf8")
    verifier._independent_zone_canon('{"a":"\\ud7ff\\ue000"}', "v1_utf8")
    verifier._independent_zone_canon(str(oracle.SIGNED_INT256_MIN), "v1_utf8")
    verifier._independent_zone_canon(str(oracle.SIGNED_INT256_MAX), "v1_utf8")
    verifier._independent_zone_canon(str(-oracle.JS_SAFE_INT_MAX), "mde_v0_utf8")

    # Rust verifier fail-closed tests (run unconditionally — zero skips in Rust-less CI!)
    rust_file = THIS_DIR / oracle.RUST_REF_FILE_NAME
    check_raises(verifier.S98Error, lambda: verifier.verify_rust_conformance_live(rust_file, check_pinned_sha=1), "INVALID_CHECK_PINNED_SHA", "rust non-bool")  # type: ignore[arg-type]
    tmp_dir = tempfile.mkdtemp(prefix="s98_t3_")
    try:
        os.chmod(tmp_dir, 0o700)
        td = Path(tmp_dir)
        bad_rs = td / "bad.rs"
        bad_rs.write_text("fn main() {}\n", encoding="utf-8")
        check_raises(verifier.S98Error, lambda: verifier.verify_rust_conformance_live(bad_rs, check_pinned_sha=True), "RUST_SHA_MISMATCH", "rust sha mismatch")

        # Missing rustc binary (returns exit 2 in CLI)
        def _chk_missing_rustc() -> None:
            check_raises(verifier.S98Error, lambda: verifier.verify_rust_conformance_live(rust_file, check_pinned_sha=True), "RUSTC_BINARY_MISSING", "missing rustc")
            out_m = io.StringIO()
            old_out = sys.stdout
            try:
                sys.stdout = out_m
                rc_m = verifier.main(["--verify-rust", str(rust_file), "--json"])
            finally:
                sys.stdout = old_out
            check(rc_m == 2 and json.loads(out_m.getvalue())["code"] == "RUSTC_BINARY_MISSING", "CLI missing rustc must exit 2")

        _with_env({"PATH": "", "HOME": str(td / "empty_home")}, _chk_missing_rustc)

        # Fake rustc failure modes (build fail, accept fail, malformed output, drift, reject bypass) + fake happy path
        fake_bin = td / "fake_bin"
        fake_bin.mkdir()
        fake_rustc = fake_bin / "rustc"

        # 1. Build failure
        _make_exec_script(fake_rustc, "#!/bin/sh\necho build_err >&2\nexit 1\n")
        _with_env({"PATH": f"{fake_bin}:/usr/bin:/bin"}, lambda: check_raises(verifier.S98Error, lambda: verifier.verify_rust_conformance_live(bad_rs, check_pinned_sha=False), "RUSTC_BUILD_FAILED", "fake rustc fail"))

        # Helper to emit a fake rustc that writes a shell script as `-o <bin>` (verifying RUSTFLAGS scrubbing)
        def _write_fake_rustc(target_script: str) -> None:
            rustc_body = (
                "#!/bin/sh\n"
                'if [ -n "$RUSTFLAGS" ]; then echo leaked_rustflags >&2; exit 99; fi\n'
                'out=""\n'
                'while [ "$#" -gt 0 ]; do\n'
                '  if [ "$1" = "-o" ]; then out="$2"; shift 2; else shift; fi\n'
                "done\n"
                'cat > "$out" <<\'EOF\'\n'
                + target_script
                + "\nEOF\n"
                'chmod 700 "$out"\n'
                "exit 0\n"
            )
            _make_exec_script(fake_rustc, rustc_body)

        def _run_fake_rust_target(target_script: str, expected_code: str) -> None:
            _write_fake_rustc(target_script)
            _with_env(
                {"PATH": f"{fake_bin}:/usr/bin:/bin"},
                lambda: check_raises(verifier.S98Error, lambda: verifier.verify_rust_conformance_live(bad_rs, check_pinned_sha=False), expected_code, f"fake rust {expected_code}"),
            )

        _run_fake_rust_target("#!/bin/sh\nexit 1", "RUST_ACCEPT_FAILED")
        _run_fake_rust_target("#!/bin/sh\necho OK 00\nexit 0", "RUST_OUTPUT_MALFORMED")
        _run_fake_rust_target("#!/bin/sh\necho NO 00 00 00\nexit 0", "RUST_OUTPUT_MALFORMED")

        # Single-field drift scripts for exact BoolOp coverage of parts[1], parts[2], parts[3]
        py_exec = sys.executable
        for drift_mode in ("hex", "raw", "dom"):
            drift_script = (
                f"#!{py_exec}\n"
                "import sys\n"
                "sys.dont_write_bytecode = True\n"
                f"sys.path.insert(0, {str(THIS_DIR)!r})\n"
                "import s98_trust_boundary_oracle as o\n"
                "c, r, d = o.canonicalize_zone_v1(sys.stdin.read(), sys.argv[2])\n"
                f"hx = '00' if {drift_mode!r} == 'hex' else c.hex()\n"
                f"rw = '0'*64 if {drift_mode!r} == 'raw' else r\n"
                f"dm = '0'*64 if {drift_mode!r} == 'dom' else d\n"
                "print('OK', hx, rw, dm)\n"
                "sys.exit(0)\n"
            )
            _run_fake_rust_target(drift_script, "RUST_PYTHON_DRIFT")

        # Two distinct reject-bypass modes: (rc=0, 'REJECT ...') and (rc=1, 'OTHER')
        for rj_rc, rj_msg in ((0, "REJECT BAD"), (1, "OTHER")):
            bypass_script = (
                f"#!{py_exec}\n"
                "import sys\n"
                "sys.dont_write_bytecode = True\n"
                f"sys.path.insert(0, {str(THIS_DIR)!r})\n"
                "import s98_trust_boundary_oracle as o\n"
                "prof = sys.argv[2]\n"
                "inp = sys.stdin.read()\n"
                "try:\n"
                "    c, r, d = o.canonicalize_zone_v1(inp, prof)\n"
                "    print('OK', c.hex(), r, d)\n"
                "    sys.exit(0)\n"
                "except o.ZoneCanonError:\n"
                f"    print({rj_msg!r})\n"
                f"    sys.exit({rj_rc})\n"
            )
            _run_fake_rust_target(bypass_script, "RUST_REJECT_BYPASS")

        # Two distinct invalid-UTF8 bypass modes: (rc=0, 'REJECT INVALID_UTF8') and (rc=1, 'OTHER')
        for u_rc, u_msg in ((0, "REJECT INVALID_UTF8"), (1, "OTHER")):
            utf8_bypass = (
                f"#!{py_exec}\n"
                "import sys\n"
                "sys.dont_write_bytecode = True\n"
                f"sys.path.insert(0, {str(THIS_DIR)!r})\n"
                "import s98_trust_boundary_oracle as o\n"
                "prof = sys.argv[2]\n"
                "raw = sys.stdin.buffer.read()\n"
                "try:\n"
                "    inp = raw.decode('utf-8')\n"
                "except UnicodeDecodeError:\n"
                f"    print({u_msg!r})\n"
                f"    sys.exit({u_rc})\n"
                "try:\n"
                "    c, r, d = o.canonicalize_zone_v1(inp, prof)\n"
                "    print('OK', c.hex(), r, d)\n"
                "    sys.exit(0)\n"
                "except o.ZoneCanonError as e:\n"
                "    print('REJECT', e.code)\n"
                "    sys.exit(1)\n"
            )
            _run_fake_rust_target(utf8_bypass, "RUST_UTF8_BYPASS")

        # Fake happy-path target exercising full accept+reject+utf8 parity & CLI --verify-rust even in Rust-less CI
        happy_script = (
            f"#!{py_exec}\n"
            "import sys\n"
            "sys.dont_write_bytecode = True\n"
            f"sys.path.insert(0, {str(THIS_DIR)!r})\n"
            "import s98_trust_boundary_oracle as o\n"
            "prof = sys.argv[2]\n"
            "raw = sys.stdin.buffer.read()\n"
            "try:\n"
            "    inp = raw.decode('utf-8')\n"
            "except UnicodeDecodeError:\n"
            "    print('REJECT INVALID_UTF8')\n"
            "    sys.exit(1)\n"
            "try:\n"
            "    c, r, d = o.canonicalize_zone_v1(inp, prof)\n"
            "    print('OK', c.hex(), r, d)\n"
            "    sys.exit(0)\n"
            "except o.ZoneCanonError as e:\n"
            "    print('REJECT', e.code)\n"
            "    sys.exit(1)\n"
        )
        _write_fake_rustc(happy_script)

        def _chk_fake_rust_ok() -> None:
            buf = io.StringIO()
            old_out = sys.stdout
            try:
                sys.stdout = buf
                rc_r = verifier.main(["--verify-rust", str(rust_file), "--json"])
            finally:
                sys.stdout = old_out
            res_r = json.loads(buf.getvalue())
            check(rc_r == 0 and res_r["status"] == "PASS" and res_r["accept_parity"] == 10 and res_r["reject_parity"] == 15, "fake CLI --verify-rust failed")

        _with_env({"PATH": f"{fake_bin}:/usr/bin:/bin", "RUSTFLAGS": "--evil-flag"}, _chk_fake_rust_ok)

        # Live rustc check when available in environment (zero skips either way)
        real_rustc = verifier.resolve_tool_binary("rustc", ".local/bin/rustc")
        if real_rustc is not None:
            buf = io.StringIO()
            old_out = sys.stdout
            try:
                sys.stdout = buf
                rc_r = verifier.main(["--verify-rust", str(rust_file), "--json"])
            finally:
                sys.stdout = old_out
            res_r = json.loads(buf.getvalue())
            check(rc_r == 0 and res_r["status"] == "PASS" and res_r["accept_parity"] == 10 and res_r["reject_parity"] == 15, "CLI --verify-rust failed")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_4_pillar2_r10_lean_gate_and_live_lean() -> None:
    # All 24 attacks blocked, all 5 controls clean
    for aid, _, _, code in oracle.R10_LIVE_ATTACKS:
        hits = oracle.scan_lean4_r10_plus(code)
        check(len(hits) > 0, f"R10+ missed attack {aid}")
    for cid, code in oracle.R10_CLEAN_CONTROLS:
        hits = oracle.scan_lean4_r10_plus(code)
        check(hits == [], f"R10+ false positive on {cid}: {hits}")

    # Additional comment/string/decide/attribute scanner edge cases
    clean_edges = [
        "/- outer /- inner sorry -/ still comment -/\ntheorem t : True := trivial\n",
        "/- slash / inside comment -/\ntheorem t : True := trivial\n",
        "/- dash - sorry inside comment -/\ntheorem t : True := trivial\n",
        'def s : String := "a\\"sorry"\ntheorem t : True := trivial\n',
        'def s : String := "line1\nline2"\ntheorem t : True := trivial\n',
        "theorem t : True := trivial -- EOF comment sorry",
        "theorem t : 1 + 1 = 2 := by decide (native := (false))\n",
        "theorem t : 1 + 1 = 2 := by decide (native := ((Bool.false)))\n",
        "theorem t : 1 + 1 = 2 := by decide (config := ({ native := false }))\n",
        "theorem t : 1 + 1 = 2 := by decide (config := { revert := true })\n",
        "theorem t : 1 + 1 = 2 := by decide +revert\n",
        "theorem t : 1 + 1 = 2 := by decide (revert := true)\n",
        "def d := decide",
        "def d := decide + 1",
        "def d := decide (",
        "def d := decide (1)",
        "def x := )",
        "def x := ]",
        "@[simp] theorem t : True := trivial\n",
        "import Init\ntheorem t : True := trivial\n",
        "export Nat (succ)\n",
        "attribute [simp] init\n",
        '"sorry"',
        "def f := @[simp",
        "def c1 : Char := '\\''\ndef c2 : Char := '\\\\'\ndef c3 : Char := '\\\"'\ndef c4 : Char := '\"'\ndef c5 : Char := '\\x22'\ndef c6 : Char := '\\u0022'\ntheorem t : True := trivial\n",
        "def x' : String := \"hi\"\ntheorem f' : x' = \"hi\" := rfl\n",
        'def s : String := r#"sorry"#\ntheorem t : True := trivial\n',
        'def s : String := r"\\"\ntheorem t : True := trivial\n',
        'def s : String := r##"a\n"sorry"b"##\ntheorem t : True := trivial\n',
        'def s : String := s!"sorry \\" {1} \\{sorry}"\ntheorem t : True := trivial\n',
        'def s : String := s!"line1\nline2 { { a := 1 } }"\ntheorem t : True := trivial\n',
        'def «a» : Nat := 0\ntheorem t : True := trivial\n',
    ]
    for idx, src in enumerate(clean_edges):
        hits = verifier.scan_lean4_r10_plus(src)
        check(hits == [], f"clean edge {idx} falsely flagged: {hits} for {src!r}")

    # Direct strip_lean4_comments_and_strings & _is_lean4_ident_end unit checks (100% BoolOp + mutation coverage)
    check(oracle._is_lean4_ident_end("a", -1) is False, "idx < 0")
    check(oracle._is_lean4_ident_end(" ", 0) is False, "non ident body")
    check(oracle._is_lean4_ident_end("a 1", 2) is False, "digit literal after ident+space")
    check(oracle._is_lean4_ident_end("x1", 1) is True, "alnum ident")
    check(oracle.strip_lean4_comments_and_strings("a'x'") == ("a'x'", False), "prime ident must not lex as Char")
    check(oracle.strip_lean4_comments_and_strings("x1'x'") == ("x1'x'", False), "alnum prime ident must not lex as Char")
    check(oracle.strip_lean4_comments_and_strings("'") == ("'", False), "bare EOF quote")
    check(oracle.strip_lean4_comments_and_strings("'a'") == ("   ", False), "pos-0 char lit stripped")
    check(oracle.strip_lean4_comments_and_strings("'a") == ("'a", False), "short unclosed char")
    check(oracle.strip_lean4_comments_and_strings("''") == ("''", False), "empty quote pair")
    check(oracle.strip_lean4_comments_and_strings("'\n'") == (" \n ", False), "literal-LF char preserves newline")
    check(oracle.strip_lean4_comments_and_strings("'ab'") == ("'ab'", False), "two-char quote")
    check(oracle.strip_lean4_comments_and_strings("'\\u0022'")[0].strip() == "", "unicode escaped char stripped")
    check(oracle.strip_lean4_comments_and_strings('foo_r"x"') == ('foo_r   ', False), "ident ending in r uses plain string")
    check(oracle.strip_lean4_comments_and_strings('x.r"\\""') == ('x.r    ', False), "field .r uses plain string not raw string")
    check(oracle.strip_lean4_comments_and_strings("r#") == ("r#", False), "r# at EOF")
    check(oracle.strip_lean4_comments_and_strings("r#x") == ("r#x", False), "r# not followed by quote")
    check(oracle.strip_lean4_comments_and_strings('r#"unterminated')[1] is True, "unterminated raw string")
    check(oracle.strip_lean4_comments_and_strings('r#"a\nb"#')[0] == "    \n   ", "multiline raw string preserves LF")
    check(oracle.strip_lean4_comments_and_strings('s!"unterminated')[1] is True, "unterminated interp string")
    check(oracle.strip_lean4_comments_and_strings('s!"{1')[1] is True, "unterminated interp brace")
    check(oracle.strip_lean4_comments_and_strings('def «unterminated')[1] is True, "unterminated guillemet")
    check(oracle.strip_lean4_comments_and_strings('def x := {1}') == ('def x := {1}', False), "normal braces outside interp")
    check(oracle.strip_lean4_comments_and_strings('s!"a { {1} } b"') == ('s!   { {1} }   ', False), "nested braces inside interp")
    check(oracle.strip_lean4_comments_and_strings('s!"a\nb"') == ("s!  \n  ", False), "multiline interp preserves LF")
    check(oracle.strip_lean4_comments_and_strings('!"{}" -- m') == ('!         ', False), "pos-1 bang uses plain string not interp")
    check(oracle.strip_lean4_comments_and_strings('s "{}"') == ('s     ', False), "space after s uses plain string not interp")
    check(oracle.strip_lean4_comments_and_strings('get!"{}"') == ('get!    ', False), "non-sfm bang uses plain string")
    check(oracle.strip_lean4_comments_and_strings('as!"{}"') == ('as!    ', False), "multi-char ident ending in s! uses plain string")

    # Direct unit checks on R10+ paren/brace/with helpers for 100% BoolOp sensitivity
    check(oracle._is_native_rhs_false("(falsex") is False, "unmatched ( must not unwrap")
    check(oracle._is_native_rhs_false("xfalse)") is False, "unmatched ) must not unwrap")
    for cfg_s in ("({native := false}x", "x{native := false})", "xab}", "{abx", "{ a { b }", "{ a } b }", "{ a with native := false }"):
        check(oracle._is_safe_decide_config(cfg_s, 0, len(cfg_s)) is False, f"unsafe cfg accepted: {cfg_s!r}")

    blocked_edges: List[Tuple[str, str]] = [
        ("/- unterminated comment", "LEAN4_UNTERMINATED_DELIM"),
        ('def s := "unterminated', "LEAN4_UNTERMINATED_DELIM"),
        ('def s := r#"unterminated', "LEAN4_UNTERMINATED_DELIM"),
        ('def s := s!"unterminated', "LEAN4_UNTERMINATED_DELIM"),
        ('def s := s!"{1', "LEAN4_UNTERMINATED_DELIM"),
        ('def «unterminated', "LEAN4_UNTERMINATED_DELIM"),
        ('def c : Char := \'"\'\ntheorem t : (1:Nat) = 2 := sorry\ndef d : Char := \'"\'\n', "LEAN4_SORRY"),
        ('def c : Char := \'\\"\'\ntheorem t : (1:Nat) = 2 := sorry\ndef d : Char := \'\\"\'\n', "LEAN4_SORRY"),
        ('def b : Bool := !\'"\'.isDigit\ntheorem t : (1:Nat) = 2 := sorry\ndef d : Char := \'"\'\n', "LEAN4_SORRY"),
        ('def x := f 1\'"\'\ntheorem t : (1:Nat) = 2 := sorry\ndef d : Char := \'"\'\n', "LEAN4_SORRY"),
        ('def y := «x»\'"\'\ntheorem t : (1:Nat) = 2 := sorry\ndef d : Char := \'"\'\n', "LEAN4_SORRY"),
        ('def y := f \'\n\' \'"\'\ntheorem t : (1:Nat) = 2 := sorry\ndef d : Char := \'"\'\n', "LEAN4_SORRY"),
        ('def b : Bool := !"{" == "a"\ntheorem t : (1:Nat) = 2 := sorry\ndef c : String := "}"\n', "LEAN4_SORRY"),
        ('def s1 : String := r#" " "#\ntheorem t : (1:Nat) = 2 := sorry\ndef s2 : String := r#" " "#\n', "LEAN4_SORRY"),
        ('def s1 : String := r"\\"\ntheorem t : (1:Nat) = 2 := sorry\ndef s2 : String := r"\\"\n', "LEAN4_SORRY"),
        ('def s1 : String := s!"hello"\ntheorem t : (1:Nat) = 2 := sorry\ndef s2 : String := s!"\\"x"\n', "LEAN4_SORRY"),
        ('def s1 : String := s!"{ s!"{sorry}" }"\n', "LEAN4_SORRY"),
        ('def «a"b» : Nat := 0\ntheorem t : (1:Nat) = 2 := sorry\ndef «c"d» : Nat := 0\n', "LEAN4_SORRY"),
        ('def «/-» : Nat := 0\ntheorem t : (1:Nat) = 2 := sorry\ndef «-/» : Nat := 0\n', "LEAN4_SORRY"),
        ('def «--» : Nat := 0; theorem t : (1:Nat) = 2 := sorry\n', "LEAN4_SORRY"),
        ('def s := "foo\\\\" sorry\n', "LEAN4_SORRY"),
        ("-- harmless line comment\ntheorem t : True := by sorry\n", "LEAN4_SORRY"),
        ("theorem t : 1 + 1 = 2 := by decide (native := (true))\n", "LEAN4_DECIDE_NATIVE"),
        ("theorem t : 1 + 1 = 2 := by decide -kernel +native\n", "LEAN4_DECIDE_NATIVE"),
        ("theorem t : 1 + 1 = 2 := by decide (config := myCfg)\n", "LEAN4_DECIDE_NATIVE"),
        ("theorem t : 1 + 1 = 2 := by decide (config := { ({} : _) with native })\n", "LEAN4_DECIDE_NATIVE"),
        ("theorem t : 1 + 1 = 2 := by decide (config := { a := { b := 1 } })\n", "LEAN4_DECIDE_NATIVE"),
        ("theorem t : 1 + 1 = 2 := by decide (config := { native := true })\n", "LEAN4_DECIDE_NATIVE"),
        ("theorem t : 1 + 1 = 2 := by decide (native := false) (config := { native := true })\n", "LEAN4_DECIDE_NATIVE"),
        ('attribute [implemented_by f] g\n', "LEAN4_UNSOUND_ATTR"),
        ("@[builtin_init] def b : IO Unit := pure ()\n", "LEAN4_UNSOUND_ATTR"),
        ('@[simp, extern "c_fn"] def e : Nat := 0\n', "LEAN4_UNSOUND_ATTR"),
        ("@[foo [bar], export baz] def e : Nat := 0\n", "LEAN4_UNSOUND_ATTR"),
        ("#guard_msgs in #check Nat\n", "LEAN4_HASH_COMMAND"),
        ("set_option debug.skipKernelTC true\n", "LEAN4_DEBUG_ESCAPE"),
        ("set_option warn.sorry false in private theorem f : False := _root_.sorryAx False false\n", "LEAN4_DEBUG_ESCAPE"),
        ("set_option warn.sorry false in private theorem f : False := _root_.sorryAx False false\n", "LEAN4_KERNEL_TRUST_API"),
        ("private def dt : Nat := _root_.dbgTrace (String.ofList []) (fun _ => 0)\n", "LEAN4_COMPILE_EXEC"),
        ("private def ds : Nat := dbgSleep 1 (fun _ => 0)\n", "LEAN4_COMPILE_EXEC"),
        ("private def dk : Nat := dbgStackTrace (fun _ => 0)\n", "LEAN4_COMPILE_EXEC"),
        ('def badInterp : String := s!"{sorry}"\n', "LEAN4_SORRY"),
        ('def badFmt : String := f!"{sorry}"\n', "LEAN4_SORRY"),
        ("theorem bv : true = true := by bv_decide\n", "LEAN4_BV_DECIDE"),
        ("@[csimp] theorem sub_eq : 1 = 1 := rfl\n", "LEAN4_UNSOUND_ATTR"),
        ("@[tactic foo] def myTac : Nat := 0\n", "LEAN4_UNSOUND_ATTR"),
        ('notation "fake" => 1\n', "LEAN4_META_ESCAPE"),
        ("import Mathlib\ntheorem t : True := trivial\n", "LEAN4_NON_INIT_IMPORT"),
        ("def p : Nat := panic! (String.ofList [])\n", "LEAN4_COMPILE_EXEC"),
        ("def u : Nat := unreachable!\n", "LEAN4_COMPILE_EXEC"),
        ("noncomputable def nc : Nat := 0\n", "LEAN4_OPAQUE"),
        ("#guard 1 + 1 == 2\n", "LEAN4_HASH_COMMAND"),
    ]
    for src, exp_code in blocked_edges:
        hits = oracle.scan_lean4_r10_plus(src)
        check(exp_code in hits, f"expected {exp_code} in {hits} for {src!r}")

    # Live Lean verifier fail-closed tests (unconditional — zero skips in Lean-less CI!)
    lean_file = THIS_DIR / oracle.LEAN_FILE_NAME
    check_raises(verifier.S98Error, lambda: verifier.verify_lean4_file_live(lean_file, check_pinned_sha="yes"), "INVALID_CHECK_PINNED_SHA", "lean non-bool")  # type: ignore[arg-type]

    tmp_dir = tempfile.mkdtemp(prefix="s98_t4_")
    try:
        os.chmod(tmp_dir, 0o700)
        td = Path(tmp_dir)
        other_lean = td / "other.lean"
        other_lean.write_text("theorem ok : 1 = 1 := rfl\n#print axioms ok\n", encoding="utf-8")
        check_raises(verifier.S98Error, lambda: verifier.verify_lean4_file_live(other_lean, check_pinned_sha=True), "LEAN_SHA_MISMATCH", "lean sha mismatch")

        bad_utf8 = td / "bad_utf8.lean"
        bad_utf8.write_bytes(b"\xff\xfe\n")
        check_raises(verifier.S98Error, lambda: verifier.verify_lean4_file_live(bad_utf8, check_pinned_sha=False), "LEAN_INVALID_UTF8", "lean bad utf8")

        evil_lean = td / "evil.lean"
        evil_lean.write_text("theorem t : True := by sorry\n", encoding="utf-8")
        check_raises(verifier.S98Error, lambda: verifier.verify_lean4_file_live(evil_lean, check_pinned_sha=False), "LEAN_R10_BLOCKED", "lean r10 blocked")

        # End-to-end live verifier rejection of Char, unary-bang, literal-LF, raw-string,
        # interpolated-string, and guillemet lexer bypasses
        for lex_name, lex_src in (
            ("char_dquote", 'def c : Char := \'"\'\ntheorem t : (1:Nat) = 2 := sorry\ndef d : Char := \'"\'\n'),
            ("bang_char_dquote", 'def b : Bool := !\'"\'.isDigit\ntheorem t : (1:Nat) = 2 := sorry\ndef z : Char := \'"\'\n'),
            ("lf_char_dquote", 'def y := f \'\n\' \'"\'\ntheorem t : (1:Nat) = 2 := sorry\ndef z : Char := \'"\'\n'),
            ("bang_str_sorry", 'def b : Bool := !"{" == "a"\ntheorem t : (1:Nat) = 2 := sorry\ndef c : String := "}"\n'),
            ("raw_string_dquote", 'def s1 : String := r#" " "#\ntheorem t : (1:Nat) = 2 := sorry\ndef s2 : String := r#" " "#\n'),
            ("interp_swallow", 'def s1 : String := s!"hello"\ntheorem t : (1:Nat) = 2 := sorry\ndef s2 : String := s!"\\"x"\n'),
            ("guil_dquote", 'def «a"b» : Nat := 0\ntheorem t : (1:Nat) = 2 := sorry\ndef «c"d» : Nat := 0\n'),
            ("guil_comment", 'def «/-» : Nat := 0\ntheorem t : (1:Nat) = 2 := sorry\ndef «-/» : Nat := 0\n'),
        ):
            lex_file = td / f"{lex_name}.lean"
            lex_file.write_text(lex_src, encoding="utf-8")
            check_raises(verifier.S98Error, lambda f=lex_file: verifier.verify_lean4_file_live(f, check_pinned_sha=False), "LEAN_R10_BLOCKED", f"live {lex_name}")

        # Missing lean binary -> LEAN_BINARY_MISSING & CLI exit 2
        def _chk_missing_lean() -> None:
            check_raises(verifier.S98Error, lambda: verifier.verify_lean4_file_live(lean_file, check_pinned_sha=True), "LEAN_BINARY_MISSING", "missing lean")
            out_m = io.StringIO()
            old_out = sys.stdout
            try:
                sys.stdout = out_m
                rc_m = verifier.main(["--verify-lean", str(lean_file), "--json"])
            finally:
                sys.stdout = old_out
            check(rc_m == 2 and json.loads(out_m.getvalue())["code"] == "LEAN_BINARY_MISSING", "CLI missing lean must exit 2")

        _with_env({"PATH": "", "HOME": str(td / "no_home")}, _chk_missing_lean)

        # $HOME/.local/bin fallback resolution test (valid exec, directory rejected, non-exec file rejected)
        fake_home = td / "fake_home"
        home_bin = fake_home / ".local" / "bin"
        home_bin.mkdir(parents=True)
        fake_lean_home = _make_exec_script(
            home_bin / "lean",
            "#!/bin/sh\necho \"'ok' does not depend on any axioms\"\nexit 0\n",
        )
        (home_bin / "dirtool").mkdir()
        noexec_file = home_bin / "noexec"
        noexec_file.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(str(noexec_file), 0o600)
        resolved = _with_env({"PATH": "", "HOME": str(fake_home)}, lambda: verifier.resolve_tool_binary("lean", ".local/bin/lean"))
        check(resolved == str(fake_lean_home), "HOME fallback resolve_tool_binary failed")
        check(_with_env({"PATH": "", "HOME": str(fake_home)}, lambda: verifier.resolve_tool_binary("dirtool", ".local/bin/dirtool")) is None, "directory must not resolve as binary")
        check(_with_env({"PATH": "", "HOME": str(fake_home)}, lambda: verifier.resolve_tool_binary("noexec", ".local/bin/noexec")) is None, "non-executable file must not resolve as binary")

        # Fake lean tests: rc!=0, stderr!="", forbidden axiom, 0 theorems, 1 theorem OK, wrong count with pinned SHA
        fake_bin = td / "fake_bin"
        fake_bin.mkdir()
        fake_lean = fake_bin / "lean"

        _make_exec_script(fake_lean, "#!/bin/sh\nexit 1\n")
        _with_env({"PATH": f"{fake_bin}:/usr/bin:/bin"}, lambda: check_raises(verifier.S98Error, lambda: verifier.verify_lean4_file_live(other_lean, check_pinned_sha=False), "LEAN_ELAB_FAILED", "lean rc=1"))

        _make_exec_script(fake_lean, "#!/bin/sh\necho warn >&2\necho \"'ok' does not depend on any axioms\"\nexit 0\n")
        _with_env({"PATH": f"{fake_bin}:/usr/bin:/bin"}, lambda: check_raises(verifier.S98Error, lambda: verifier.verify_lean4_file_live(other_lean, check_pinned_sha=False), "LEAN_ELAB_FAILED", "lean stderr"))

        _make_exec_script(fake_lean, "#!/bin/sh\necho \"'ok' depends on axioms: [propext, Classical.choice]\"\nexit 0\n")
        _with_env({"PATH": f"{fake_bin}:/usr/bin:/bin"}, lambda: check_raises(verifier.S98Error, lambda: verifier.verify_lean4_file_live(other_lean, check_pinned_sha=False), "LEAN_FORBIDDEN_AXIOM", "forbidden axiom"))

        _make_exec_script(fake_lean, "#!/bin/sh\necho \"non axiom output\"\nexit 0\n")
        _with_env({"PATH": f"{fake_bin}:/usr/bin:/bin"}, lambda: check_raises(verifier.S98Error, lambda: verifier.verify_lean4_file_live(other_lean, check_pinned_sha=False), "LEAN_NO_THEOREMS", "0 theorems"))

        _make_exec_script(fake_lean, "#!/bin/sh\necho \"'ok' depends on axioms: [propext]\"\nexit 0\n")
        res_fake_ok = _with_env({"PATH": f"{fake_bin}:/usr/bin:/bin"}, lambda: verifier.verify_lean4_file_live(other_lean, check_pinned_sha=False))
        check(res_fake_ok["status"] == "PASS" and res_fake_ok["theorems_verified"] == 1, "fake 1-thm lean check failed")
        _with_env({"PATH": f"{fake_bin}:/usr/bin:/bin"}, lambda: check_raises(verifier.S98Error, lambda: verifier.verify_lean4_file_live(lean_file, check_pinned_sha=True), "LEAN_THEOREM_COUNT", "wrong thm count"))

        # Fake 19-thm happy path verifying LEAN_PATH/LEAN_OPTS/ELAN_*/LEAN_CC scrubbing & CLI --verify-lean
        lines_19 = "\n".join(f"echo \"'t{i}' depends on axioms: [propext]\"" for i in range(19))
        _make_exec_script(
            fake_lean,
            f"#!/bin/sh\nif [ -n \"$LEAN_PATH$LEAN_OPTS$ELAN_TOOLCHAIN$ELAN_HOME$LEAN_CC\" ]; then echo leaked_env >&2; exit 99; fi\n{lines_19}\nexit 0\n",
        )

        def _chk_fake_lean_ok() -> None:
            buf = io.StringIO()
            old_out = sys.stdout
            try:
                sys.stdout = buf
                rc_l = verifier.main(["--verify-lean", str(lean_file), "--json"])
            finally:
                sys.stdout = old_out
            res_l = json.loads(buf.getvalue())
            check(rc_l == 0 and res_l["status"] == "PASS" and res_l["theorems_verified"] == 19, "fake CLI --verify-lean failed")

        _with_env(
            {
                "PATH": f"{fake_bin}:/usr/bin:/bin",
                "LEAN_PATH": "/evil",
                "LEAN_OPTS": "-D debug.skipKernelTC=true",
                "ELAN_TOOLCHAIN": "evil",
                "ELAN_HOME": "/evil_elan",
                "LEAN_CC": "/evil_cc",
            },
            _chk_fake_lean_ok,
        )

        # Live Lean 4.36.0 check when available
        real_lean = verifier.resolve_tool_binary("lean", ".local/bin/lean")
        if real_lean is not None:
            buf = io.StringIO()
            old_out = sys.stdout
            try:
                sys.stdout = buf
                rc_l = verifier.main(["--verify-lean", str(lean_file), "--json"])
            finally:
                sys.stdout = old_out
            res_l = json.loads(buf.getvalue())
            check(rc_l == 0 and res_l["status"] == "PASS" and res_l["theorems_verified"] == 19 and res_l["r10_findings"] == 0, "CLI --verify-lean failed")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_5_pillar3_c2_anchors_safetensors_e8() -> None:
    # evaluate_exact_c2_gate boundaries
    check(not oracle.evaluate_exact_c2_gate([Fraction(1, 1)], Fraction(1, 1), Fraction(5, 1), Fraction(0, 1))["accepted"], "step_cost=0")
    check(not oracle.evaluate_exact_c2_gate([Fraction(1, 1)], Fraction(1, 1), Fraction(5, 1), Fraction(-1, 1))["accepted"], "step_cost<0")
    check(not oracle.evaluate_exact_c2_gate([Fraction(1, 1)], Fraction(1, 1), Fraction(0, 1), Fraction(1, 1))["accepted"], "budget=0")
    check(not oracle.evaluate_exact_c2_gate([Fraction(1, 1)], Fraction(1, 1), Fraction(-1, 1), Fraction(1, 1))["accepted"], "budget<0")
    check(not oracle.evaluate_exact_c2_gate([Fraction(1, 1)], Fraction(-1, 1), Fraction(5, 1), Fraction(1, 1))["accepted"], "radius<0")
    check(not oracle.evaluate_exact_c2_gate([Fraction(1, 1)], Fraction(1, 1), Fraction(1, 1), Fraction(2, 1))["accepted"], "budget<cost")
    check(not oracle.evaluate_exact_c2_gate([], Fraction(1, 1), Fraction(5, 1), Fraction(1, 1))["accepted"], "empty deltas")

    zero_step = oracle.evaluate_exact_c2_gate([Fraction(0, 1)], Fraction(0, 1), Fraction(1, 1), Fraction(1, 1))
    check(zero_step["accepted"] and zero_step["remaining_budget"] == Fraction(0, 1), "zero delta with radius=0 & budget==cost must pass")

    exact_rad = oracle.evaluate_exact_c2_gate([Fraction(3, 1), Fraction(4, 1)], Fraction(5, 1), Fraction(5, 1), Fraction(1, 1))
    check(exact_rad["accepted"] and exact_rad["remaining_budget"] == Fraction(4, 1), "exact radius boundary must pass")

    over_rad = oracle.evaluate_exact_c2_gate([Fraction(3, 1), Fraction(4, 1)], Fraction(4, 1), Fraction(5, 1), Fraction(1, 1))
    check(not over_rad["accepted"] and over_rad["remaining_budget"] == Fraction(5, 1), "over radius must reject & preserve budget")

    # exact_royalty_split boundaries
    check_raises(ValueError, lambda: oracle.exact_royalty_split(-1, 100), "", "neg gross")
    check_raises(ValueError, lambda: oracle.exact_royalty_split(100, -1), "", "neg bps")
    check_raises(ValueError, lambda: oracle.exact_royalty_split(100, 10001), "", "bps > 10000")
    check(oracle.exact_royalty_split(0, 0) == (0, 0), "0 gross 0 bps")
    check(oracle.exact_royalty_split(100, 10000) == (100, 0), "10000 bps")

    # division_free_mdr_trigger boundaries
    check(oracle.division_free_mdr_trigger(Fraction(5, 1), Fraction(2, 1), Fraction(5, 2), Fraction(5, 1)) is True, "mdr exact boundary")
    check(oracle.division_free_mdr_trigger(Fraction(4, 1), Fraction(1, 1), Fraction(2, 1), Fraction(5, 1)) is False, "mdr below floor")
    check(oracle.division_free_mdr_trigger(Fraction(5, 1), Fraction(3, 1), Fraction(2, 1), Fraction(1, 1)) is False, "mdr below ratio")

    # classify_verifier_owned_tier boundaries
    check(oracle.classify_verifier_owned_tier(True, 4, 4, True) == 0, "self-carried rejected")
    check(oracle.classify_verifier_owned_tier(False, 4, 4, False) == 0, "unsafe rejected")
    check(oracle.classify_verifier_owned_tier(True, 0, 0, False) == 0, "zero total_k rejected")
    check(oracle.classify_verifier_owned_tier(True, 4, 4, False) == 1, "4/4 promote")
    check(oracle.classify_verifier_owned_tier(True, 3, 4, False) == 2, "3/4 stepping stone")
    check(oracle.classify_verifier_owned_tier(True, 2, 4, False) == 0, "2/4 rejected")

    # check_strict_safetensors_dims boundaries
    check(oracle.check_strict_safetensors_dims(0, [4]) == (False, 0), "0 dtype_bits")
    check(oracle.check_strict_safetensors_dims(8, []) == (False, 0), "empty dims")
    check(oracle.check_strict_safetensors_dims(8, [-1]) == (False, 0), "neg dim")
    check(oracle.check_strict_safetensors_dims(8, [4, 0]) == (True, 0), "safe zero dim")
    check(oracle.check_strict_safetensors_dims(oracle.SAFETENSORS_MAX_BITS + 8, [1]) == (False, 0), "dtype_bits > max")
    max_elems = oracle.SAFETENSORS_MAX_BITS // 8
    check(oracle.check_strict_safetensors_dims(8, [max_elems]) == (True, max_elems), "exact max_bits accepted")
    check(oracle.check_strict_safetensors_dims(8, [max_elems + 1]) == (False, 0), "max_bits + 1 rejected")
    check(oracle.check_strict_safetensors_dims(4, [2]) == (True, 1), "aligned sub-byte accepted")
    check(oracle.check_strict_safetensors_dims(4, [3]) == (False, 0), "misaligned sub-byte rejected")

    # check_contiguous_spans boundaries (strict ascending order matching Lean spansContiguous)
    check(oracle.check_contiguous_spans([(0, 16), (16, 16), (16, 32)], 32) is True, "contig ok")
    check(oracle.check_contiguous_spans([(16, 32), (0, 16)], 32) is False, "out-of-order rejected")
    check(oracle.check_contiguous_spans([(0, 16), (17, 32)], 32) is False, "gap")
    check(oracle.check_contiguous_spans([(0, 16), (12, 32)], 32) is False, "overlap")
    check(oracle.check_contiguous_spans([(0, 16), (16, 12)], 12) is False, "inverted")
    check(oracle.check_contiguous_spans([(0, 16)], 32) is False, "short total")


def test_6_resigned_semantic_forgeries_all_surfaces() -> None:
    base_payload = oracle.build_payload()

    def _assert_all_surfaces_reject(mutator: Callable[[Dict[str, Any]], None], expected_code: str, label: str) -> None:
        p = copy.deepcopy(base_payload)
        mutator(p)
        forged_cert = resign_cert(p)
        check_raises(verifier.S98Error, lambda: verifier.secondary_audit_payload(p), expected_code, f"SEC {label}")
        check_raises(verifier.S98Error, lambda: verifier.verify_certificate_dict(forged_cert, full_replay=False), expected_code, f"FR0 {label}")
        check_raises(verifier.S98Error, lambda: verifier.verify_certificate_dict(forged_cert, full_replay=True), expected_code, f"FR1 {label}")

    forgeries: List[Tuple[str, str, Callable[[Dict[str, Any]], None]]] = [
        # Pillar 1 forgeries
        ("p1_spec_id", "P1_SPEC_ID", lambda p: p["pillar_1_zone_canon_v1"].__setitem__("spec_id", "zone-canon-v0")),
        ("p1_max_bytes", "P1_DOS", lambda p: p["pillar_1_zone_canon_v1"]["dos_bounds"].__setitem__("max_input_bytes", 1024)),
        ("p1_max_depth", "P1_DOS", lambda p: p["pillar_1_zone_canon_v1"]["dos_bounds"].__setitem__("max_depth", 65)),
        ("p1_max_nodes", "P1_DOS", lambda p: p["pillar_1_zone_canon_v1"]["dos_bounds"].__setitem__("max_nodes", 4097)),
        ("p1_max_digits", "P1_DOS_INT", lambda p: p["pillar_1_zone_canon_v1"]["dos_bounds"].__setitem__("max_int_digits", 79)),
        ("p1_js_safe", "P1_DOS_INT", lambda p: p["pillar_1_zone_canon_v1"]["dos_bounds"].__setitem__("js_safe_int_max", 1 << 53)),
        ("p1_i64", "P1_DOS_I64", lambda p: p["pillar_1_zone_canon_v1"]["dos_bounds"].__setitem__("signed_int64_max", 0)),
        ("p1_i256_dig", "P1_DOS_I64", lambda p: p["pillar_1_zone_canon_v1"]["dos_bounds"].__setitem__("signed_int256_max_digits", 78)),
        ("p1_ac_len", "P1_AC_LEN", lambda p: p["pillar_1_zone_canon_v1"]["accept_vectors"].pop()),
        ("p1_rj_len", "P1_RJ_LEN", lambda p: p["pillar_1_zone_canon_v1"]["reject_vectors"].pop()),
        ("p1_ac_cnt", "P1_COUNTS", lambda p: p["pillar_1_zone_canon_v1"].__setitem__("accept_count", 9)),
        ("p1_rj_cnt", "P1_COUNTS", lambda p: p["pillar_1_zone_canon_v1"].__setitem__("reject_count", 12)),
        ("p1_ac_name", "P1_AC_ID", lambda p: p["pillar_1_zone_canon_v1"]["accept_vectors"][0].__setitem__("name", "bad")),
        ("p1_ac_prof", "P1_AC_ID", lambda p: p["pillar_1_zone_canon_v1"]["accept_vectors"][0].__setitem__("profile", "v1_ascii")),
        ("p1_ac_hex", "P1_AC_BYTES", lambda p: p["pillar_1_zone_canon_v1"]["accept_vectors"][0].__setitem__("canonical_hex", "00")),
        ("p1_ac_bytes", "P1_AC_BYTES", lambda p: p["pillar_1_zone_canon_v1"]["accept_vectors"][0].__setitem__("canonical_bytes", 99)),
        ("p1_ac_raw_sha", "P1_AC_SHA", lambda p: p["pillar_1_zone_canon_v1"]["accept_vectors"][0].__setitem__("raw_sha256", "0" * 64)),
        ("p1_ac_dom_sha", "P1_AC_SHA", lambda p: p["pillar_1_zone_canon_v1"]["accept_vectors"][0].__setitem__("domain_sha256", "0" * 64)),
        ("p1_rj_name", "P1_RJ_ID", lambda p: p["pillar_1_zone_canon_v1"]["reject_vectors"][0].__setitem__("name", "bad")),
        ("p1_rj_prof", "P1_RJ_ID", lambda p: p["pillar_1_zone_canon_v1"]["reject_vectors"][0].__setitem__("profile", "v1_ascii")),
        ("p1_rj_code_type", "P1_RJ_CODE", lambda p: p["pillar_1_zone_canon_v1"]["reject_vectors"][0].__setitem__("rejected_code", 1)),
        ("p1_rj_code_swap", "P1_RJ_CODE", lambda p: p["pillar_1_zone_canon_v1"]["reject_vectors"][0].__setitem__("rejected_code", "NEGATIVE_ZERO")),
        ("p1_rj_code_unexp", "P1_RJ_CODE", lambda p: p["pillar_1_zone_canon_v1"]["reject_vectors"][0].__setitem__("rejected_code", "UNEXPECTED_ACCEPT")),
        ("p1_rj_code_empty", "P1_RJ_CODE", lambda p: p["pillar_1_zone_canon_v1"]["reject_vectors"][0].__setitem__("rejected_code", "")),
        ("p1_mde7_py_frag", "P1_MDE7_FRAG", lambda p: p["pillar_1_zone_canon_v1"]["mde7_float_drift_cure"].__setitem__("python_legacy_fragment", "x")),
        ("p1_mde7_rs_frag", "P1_MDE7_FRAG", lambda p: p["pillar_1_zone_canon_v1"]["mde7_float_drift_cure"].__setitem__("rust_legacy_fragment", "x")),
        ("p1_mde7_py_sha", "P1_MDE7_PY", lambda p: p["pillar_1_zone_canon_v1"]["mde7_float_drift_cure"].__setitem__("python_legacy_sha256", "0" * 64)),
        ("p1_mde7_rs_sha", "P1_MDE7_RS", lambda p: p["pillar_1_zone_canon_v1"]["mde7_float_drift_cure"].__setitem__("rust_legacy_sha256", "0" * 64)),
        ("p1_mde7_q", "P1_MDE7_Q", lambda p: p["pillar_1_zone_canon_v1"]["mde7_float_drift_cure"].__setitem__("unified_rational_pair", {"num": 1, "den": 1000})),
        ("p1_mde7_ush", "P1_MDE7_SHA", lambda p: p["pillar_1_zone_canon_v1"]["mde7_float_drift_cure"].__setitem__("unified_canonical_sha256", "0" * 64)),
        ("p1_mde7_udm", "P1_MDE7_SHA", lambda p: p["pillar_1_zone_canon_v1"]["mde7_float_drift_cure"].__setitem__("unified_domain_sha256", "0" * 64)),
        ("p1_ups_u_len", "P1_UPS_LEN", lambda p: p["pillar_1_zone_canon_v1"]["unicode_profile_separation"].__setitem__("utf8_bytes_len", 1)),
        ("p1_ups_a_len", "P1_UPS_LEN", lambda p: p["pillar_1_zone_canon_v1"]["unicode_profile_separation"].__setitem__("ascii_bytes_len", 1)),
        ("p1_ups_u_raw", "P1_UPS_RAW", lambda p: p["pillar_1_zone_canon_v1"]["unicode_profile_separation"].__setitem__("utf8_raw_sha256", "0" * 64)),
        ("p1_ups_a_raw", "P1_UPS_RAW", lambda p: p["pillar_1_zone_canon_v1"]["unicode_profile_separation"].__setitem__("ascii_raw_sha256", "0" * 64)),
        ("p1_ups_u_dom", "P1_UPS_DOM", lambda p: p["pillar_1_zone_canon_v1"]["unicode_profile_separation"].__setitem__("utf8_domain_sha256", "0" * 64)),
        ("p1_ups_a_dom", "P1_UPS_DOM", lambda p: p["pillar_1_zone_canon_v1"]["unicode_profile_separation"].__setitem__("ascii_domain_sha256", "0" * 64)),
        ("p1_ups_flag1", "P1_UPS_FLAG", lambda p: p["pillar_1_zone_canon_v1"]["unicode_profile_separation"].__setitem__("raw_digests_distinct", False)),
        ("p1_ups_flag2", "P1_UPS_FLAG", lambda p: p["pillar_1_zone_canon_v1"]["unicode_profile_separation"].__setitem__("domain_digests_distinct", False)),
        ("p1_rust_file", "P1_RUST_PIN", lambda p: p["pillar_1_zone_canon_v1"].__setitem__("rust_reference_file", "x.rs")),
        ("p1_rust_sha", "P1_RUST_PIN", lambda p: p["pillar_1_zone_canon_v1"].__setitem__("rust_reference_sha256", "0" * 64)),
        # Pillar 2 forgeries
        ("p2_am_len", "P2_AM_LEN", lambda p: p["pillar_2_r10_lean_trust_gate"]["attack_matrix"].pop()),
        ("p2_cm_len", "P2_CM_LEN", lambda p: p["pillar_2_r10_lean_trust_gate"]["control_matrix"].pop()),
        ("p2_atk_id", "P2_ATK_META", lambda p: p["pillar_2_r10_lean_trust_gate"]["attack_matrix"][0].__setitem__("attack_id", "bad")),
        ("p2_atk_mc", "P2_ATK_META", lambda p: p["pillar_2_r10_lean_trust_gate"]["attack_matrix"][0].__setitem__("mcproof_pr3_missed", True)),
        ("p2_atk_agy", "P2_ATK_META", lambda p: p["pillar_2_r10_lean_trust_gate"]["attack_matrix"][0].__setitem__("aletheia_r10_missed", True)),
        ("p2_atk_blk", "P2_ATK_HITS", lambda p: p["pillar_2_r10_lean_trust_gate"]["attack_matrix"][0].__setitem__("s98_r10_plus_blocked", False)),
        ("p2_atk_codes", "P2_ATK_HITS", lambda p: p["pillar_2_r10_lean_trust_gate"]["attack_matrix"][0].__setitem__("s98_rule_codes", [])),
        ("p2_ctrl_id", "P2_CTRL", lambda p: p["pillar_2_r10_lean_trust_gate"]["control_matrix"][0].__setitem__("control_id", "bad")),
        ("p2_ctrl_fp", "P2_CTRL", lambda p: p["pillar_2_r10_lean_trust_gate"]["control_matrix"][0].__setitem__("false_positive", True)),
        ("p2_ctrl_codes", "P2_CTRL", lambda p: p["pillar_2_r10_lean_trust_gate"]["control_matrix"][0].__setitem__("rule_codes", ["X"])),
        ("p2_atk_cnt", "P2_ATK_CNT", lambda p: p["pillar_2_r10_lean_trust_gate"].__setitem__("attack_count", 23)),
        ("p2_s98_blk", "P2_ATK_CNT", lambda p: p["pillar_2_r10_lean_trust_gate"].__setitem__("s98_attacks_blocked", 23)),
        ("p2_mc_miss", "P2_MISS_CNT", lambda p: p["pillar_2_r10_lean_trust_gate"].__setitem__("mcproof_pr3_attacks_missed", 0)),
        ("p2_agy_miss", "P2_MISS_CNT", lambda p: p["pillar_2_r10_lean_trust_gate"].__setitem__("aletheia_r10_attacks_missed", 0)),
        ("p2_ctrl_cnt", "P2_CTRL_CNT", lambda p: p["pillar_2_r10_lean_trust_gate"].__setitem__("control_count", 4)),
        ("p2_fp_cnt", "P2_CTRL_CNT", lambda p: p["pillar_2_r10_lean_trust_gate"].__setitem__("false_positives", 1)),
        ("p2_kernels", "P2_KERNELS", lambda p: p["pillar_2_r10_lean_trust_gate"]["six_kernel_comparator_names"].pop()),
        ("p2_bend_repo", "P2_BEND_ID", lambda p: p["pillar_2_r10_lean_trust_gate"]["bendtt_live_audit"].__setitem__("repo", "x")),
        ("p2_bend_file", "P2_BEND_ID", lambda p: p["pillar_2_r10_lean_trust_gate"]["bendtt_live_audit"].__setitem__("file", "x")),
        ("p2_bend_commit", "P2_BEND_SHA", lambda p: p["pillar_2_r10_lean_trust_gate"]["bendtt_live_audit"].__setitem__("commit", "0" * 40)),
        ("p2_bend_sha", "P2_BEND_SHA", lambda p: p["pillar_2_r10_lean_trust_gate"]["bendtt_live_audit"].__setitem__("sha256", "0" * 64)),
        ("p2_bend_lines", "P2_BEND_METRICS", lambda p: p["pillar_2_r10_lean_trust_gate"]["bendtt_live_audit"].__setitem__("lines", 1)),
        ("p2_bend_bytes", "P2_BEND_METRICS", lambda p: p["pillar_2_r10_lean_trust_gate"]["bendtt_live_audit"].__setitem__("bytes", 1)),
        ("p2_bend_plain", "P2_BEND_METRICS", lambda p: p["pillar_2_r10_lean_trust_gate"]["bendtt_live_audit"].__setitem__("plain_theorems_count", 226)),
        ("p2_bend_csimp", "P2_BEND_METRICS", lambda p: p["pillar_2_r10_lean_trust_gate"]["bendtt_live_audit"].__setitem__("csimp_theorems_count", 0)),
        ("p2_bend_thms", "P2_BEND_METRICS", lambda p: p["pillar_2_r10_lean_trust_gate"]["bendtt_live_audit"].__setitem__("theorems_count", 1)),
        ("p2_bend_part", "P2_BEND_METRICS", lambda p: p["pillar_2_r10_lean_trust_gate"]["bendtt_live_audit"].__setitem__("parser_partial_defs_count", 0)),
        ("p2_bend_sorry", "P2_BEND_CLEAN", lambda p: p["pillar_2_r10_lean_trust_gate"]["bendtt_live_audit"].__setitem__("sorry_count", 1)),
        ("p2_bend_nd", "P2_BEND_CLEAN", lambda p: p["pillar_2_r10_lean_trust_gate"]["bendtt_live_audit"].__setitem__("native_decide_count", 1)),
        ("p2_bend_rc", "P2_BEND_CLEAN", lambda p: p["pillar_2_r10_lean_trust_gate"]["bendtt_live_audit"].__setitem__("live_lean436_rc", 1)),
        ("p2_bend_ax", "P2_BEND_AX", lambda p: p["pillar_2_r10_lean_trust_gate"]["bendtt_live_audit"].__setitem__("kernel_axioms", ["propext"])),
        # Pillar 3 forgeries
        ("p3_ov_exp", "P3_OV", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].__setitem__("overflow_scale_exp2", 256)),
        ("p3_ov_norm", "P3_OV", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].__setitem__("overflow_scaled_sq_norm_q", {"num": 1, "den": 1})),
        ("p3_ov_acc", "P3_OV", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].__setitem__("overflow_accepted", False)),
        ("p3_zeno_b", "P3_ZENO", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].__setitem__("zeno_input_budget_q", {"num": 1, "den": 1})),
        ("p3_zeno_c", "P3_ZENO", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].__setitem__("zeno_step_cost_q", {"num": 1, "den": 5})),
        ("p3_zeno_r", "P3_ZENO", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].__setitem__("zeno_remaining_budget_q", {"num": 10**16, "den": 1})),
        ("p3_zeno_dec", "P3_ZENO", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].__setitem__("zeno_strictly_decreased", False)),
        ("p3_neg_acc", "P3_NEG", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].__setitem__("neg_cost_accepted", True)),
        ("p3_neg_pres", "P3_NEG", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].__setitem__("neg_cost_budget_preserved", False)),
        ("p3_uf_acc", "P3_UF", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].__setitem__("underflow_accepted", True)),
        ("p3_uf_pres", "P3_UF", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].__setitem__("underflow_budget_preserved", False)),
        ("p3_roy_gross", "P3_ROY", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].__setitem__("royalty_u64_threshold_wei", 1)),
        ("p3_roy_bps", "P3_ROY", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].__setitem__("royalty_bps", 1000)),
        ("p3_roy_up", "P3_ROY", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].__setitem__("royalty_upstream_wei", 1)),
        ("p3_roy_wv", "P3_ROY", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].__setitem__("royalty_weaver_wei", 1)),
        ("p3_roy_cons", "P3_ROY", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].__setitem__("royalty_conserved", False)),
        ("p3_mdr_dust", "P3_MDR", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].__setitem__("mdr_dust_blocked", False)),
        ("p3_mdr_real", "P3_MDR", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].__setitem__("mdr_real_triggered", False)),
        ("p3_anc", "P3_ANC", lambda p: p["pillar_3_c2_anchors_safetensors"]["spliceware_byzantine_anchor_defense"].__setitem__("host_triangular_anchors", [[0, 0]])),
        ("p3_byz_pass", "P3_BYZ", lambda p: p["pillar_3_c2_anchors_safetensors"]["spliceware_byzantine_anchor_defense"].__setitem__("byzantine_op_in_host_pass", 4)),
        ("p3_byz_err", "P3_BYZ", lambda p: p["pillar_3_c2_anchors_safetensors"]["spliceware_byzantine_anchor_defense"].__setitem__("byzantine_op_in_host_err", 0)),
        ("p3_cf_pass", "P3_CF_ARX", lambda p: p["pillar_3_c2_anchors_safetensors"]["spliceware_byzantine_anchor_defense"].__setitem__("closed_form_loop_free_pass", 3)),
        ("p3_arx_q", "P3_CF_ARX", lambda p: p["pillar_3_c2_anchors_safetensors"]["spliceware_byzantine_anchor_defense"].__setitem__("arx_v3_untouched_lanes_q", {"num": 1, "den": 4})),
        ("p3_tier_sc", "P3_TIERS", lambda p: p["pillar_3_c2_anchors_safetensors"]["spliceware_byzantine_anchor_defense"].__setitem__("tier_self_carried_anchor_verdict", 1)),
        ("p3_tier_un", "P3_TIERS", lambda p: p["pillar_3_c2_anchors_safetensors"]["spliceware_byzantine_anchor_defense"].__setitem__("tier_unsafe_4of4_verdict", 1)),
        ("p3_tier_st", "P3_TIERS", lambda p: p["pillar_3_c2_anchors_safetensors"]["spliceware_byzantine_anchor_defense"].__setitem__("tier_safe_3of4_stepping_stone_verdict", 0)),
        ("p3_tier_pr", "P3_TIERS", lambda p: p["pillar_3_c2_anchors_safetensors"]["spliceware_byzantine_anchor_defense"].__setitem__("tier_safe_4of4_promote_verdict", 2)),
        ("p3_st_pre0", "P3_ST", lambda p: p["pillar_3_c2_anchors_safetensors"]["strict_safetensors_and_rmsnorm_e8"].__setitem__("safetensors_pre_zero_overflow_rejected", False)),
        ("p3_st_u64", "P3_ST", lambda p: p["pillar_3_c2_anchors_safetensors"]["strict_safetensors_and_rmsnorm_e8"].__setitem__("safetensors_u64_zero_overflow_rejected", False)),
        ("p3_st_mis", "P3_ST", lambda p: p["pillar_3_c2_anchors_safetensors"]["strict_safetensors_and_rmsnorm_e8"].__setitem__("safetensors_subbyte_misaligned_rejected", False)),
        ("p3_st_val", "P3_ST", lambda p: p["pillar_3_c2_anchors_safetensors"]["strict_safetensors_and_rmsnorm_e8"].__setitem__("safetensors_valid_f16_4x6_accepted", False)),
        ("p3_st_byt", "P3_ST", lambda p: p["pillar_3_c2_anchors_safetensors"]["strict_safetensors_and_rmsnorm_e8"].__setitem__("safetensors_valid_f16_4x6_bytes", 24)),
        ("p3_st_ctg", "P3_ST", lambda p: p["pillar_3_c2_anchors_safetensors"]["strict_safetensors_and_rmsnorm_e8"].__setitem__("safetensors_contiguous_48b_accepted", False)),
        ("p3_st_gap", "P3_ST", lambda p: p["pillar_3_c2_anchors_safetensors"]["strict_safetensors_and_rmsnorm_e8"].__setitem__("safetensors_gapped_48b_rejected", False)),
        ("p3_e8_eta", "P3_E8_Q", lambda p: p["pillar_3_c2_anchors_safetensors"]["strict_safetensors_and_rmsnorm_e8"].__setitem__("rmsnorm_eta_q", {"num": 1, "den": 2})),
        ("p3_e8_slo", "P3_E8_Q", lambda p: p["pillar_3_c2_anchors_safetensors"]["strict_safetensors_and_rmsnorm_e8"].__setitem__("rmsnorm_s_lower_q", {"num": 1, "den": 10})),
        ("p3_e8_sex", "P3_E8_Q", lambda p: p["pillar_3_c2_anchors_safetensors"]["strict_safetensors_and_rmsnorm_e8"].__setitem__("rmsnorm_s_exact_q", {"num": 1, "den": 4})),
        ("p3_e8_shi", "P3_E8_Q", lambda p: p["pillar_3_c2_anchors_safetensors"]["strict_safetensors_and_rmsnorm_e8"].__setitem__("rmsnorm_s_upper_q", {"num": 1, "den": 2})),
        ("p3_e8_dec4", "P3_E8_DEC4", lambda p: p["pillar_3_c2_anchors_safetensors"]["strict_safetensors_and_rmsnorm_e8"].__setitem__("rmsnorm_s_upper_dec4", "0.2812")),
        ("p3_e8_sl4", "P3_E8_L4", lambda p: p["pillar_3_c2_anchors_safetensors"]["strict_safetensors_and_rmsnorm_e8"].__setitem__("rmsnorm_split_l4_upper_q", {"num": 1, "den": 4})),
        ("p3_e8_sfac", "P3_E8_L4", lambda p: p["pillar_3_c2_anchors_safetensors"]["strict_safetensors_and_rmsnorm_e8"].__setitem__("rmsnorm_split_l4_factor_q", {"num": 2, "den": 1})),
        # Pillar 4 forgeries
        ("p4_lean_file", "P4_LEAN_SHA", lambda p: p["pillar_4_provenance_and_lean"]["lean_companion"].__setitem__("file", "Bad.lean")),
        ("p4_lean_sha", "P4_LEAN_SHA", lambda p: p["pillar_4_provenance_and_lean"]["lean_companion"].__setitem__("sha256", "0" * 64)),
        ("p4_lake_sha", "P4_LAKE_SHA", lambda p: p["pillar_4_provenance_and_lean"]["lean_companion"].__setitem__("lakefile_sha256", "0" * 64)),
        ("p4_tc_sha", "P4_LAKE_SHA", lambda p: p["pillar_4_provenance_and_lean"]["lean_companion"].__setitem__("toolchain_sha256", "0" * 64)),
        ("p4_lean_ns", "P4_LEAN_NS", lambda p: p["pillar_4_provenance_and_lean"]["lean_companion"].__setitem__("namespace", "Wrong")),
        ("p4_lean_cnt", "P4_LEAN_NS", lambda p: p["pillar_4_provenance_and_lean"]["lean_companion"].__setitem__("theorem_count", 18)),
        ("p4_lean_univ", "P4_LEAN_SPLIT", lambda p: p["pillar_4_provenance_and_lean"]["lean_companion"].__setitem__("universal_theorem_count", 17)),
        ("p4_lean_gnd", "P4_LEAN_SPLIT", lambda p: p["pillar_4_provenance_and_lean"]["lean_companion"].__setitem__("ground_witness_count", 2)),
        ("p4_lean_zax", "P4_LEAN_AX", lambda p: p["pillar_4_provenance_and_lean"]["lean_companion"].__setitem__("zero_axiom_count", 7)),
        ("p4_lean_pax", "P4_LEAN_AX", lambda p: p["pillar_4_provenance_and_lean"]["lean_companion"].__setitem__("propext_only_count", 12)),
        ("p4_lean_aax", "P4_LEAN_AX", lambda p: p["pillar_4_provenance_and_lean"]["lean_companion"].__setitem__("allowed_axioms", ["propext", "Quot.sound"])),
        ("p4_pins_len", "P4_PINS_LEN", lambda p: p["pillar_4_provenance_and_lean"]["five_org_upstream_pins"].pop()),
        ("p4_pin_val", "P4_PIN_VAL", lambda p: p["pillar_4_provenance_and_lean"]["five_org_upstream_pins"][0].__setitem__("sha256", "0" * 64)),
        ("p4_l4_tier", "P4_LAW4", lambda p: p["pillar_4_provenance_and_lean"]["law4_honesty"].__setitem__("max_novelty_tier", "N2")),
        ("p4_l4_n0", "P4_LAW4", lambda p: p["pillar_4_provenance_and_lean"]["law4_honesty"].__setitem__("n0_prior_art_anchored", False)),
        ("p4_l4_n1", "P4_LAW4", lambda p: p["pillar_4_provenance_and_lean"]["law4_honesty"].__setitem__("n1_exact_synthesis_verified", False)),
        ("p4_l4_n2", "P4_LAW4", lambda p: p["pillar_4_provenance_and_lean"]["law4_honesty"].__setitem__("n2_claims", 1)),
        # Extra nested key rejection
        ("p4_extra_key", "KEYSET_MISMATCH", lambda p: p["pillar_4_provenance_and_lean"]["law4_honesty"].__setitem__("rogue", 1)),
        # Strict list type check when dict has identical length
        ("p1_ac_dict", "P1_AC_LEN", lambda p: p["pillar_1_zone_canon_v1"].__setitem__("accept_vectors", {str(i): {} for i in range(len(oracle.ZONE_CANON_ACCEPT_VECTORS))})),
        ("p1_rj_dict", "P1_RJ_LEN", lambda p: p["pillar_1_zone_canon_v1"].__setitem__("reject_vectors", {str(i): {} for i in range(len(oracle.ZONE_CANON_REJECT_VECTORS))})),
        ("p2_am_dict", "P2_AM_LEN", lambda p: p["pillar_2_r10_lean_trust_gate"].__setitem__("attack_matrix", {str(i): {} for i in range(len(oracle.R10_LIVE_ATTACKS))})),
        ("p2_cm_dict", "P2_CM_LEN", lambda p: p["pillar_2_r10_lean_trust_gate"].__setitem__("control_matrix", {str(i): {} for i in range(len(oracle.R10_CLEAN_CONTROLS))})),
        ("p4_pins_dict", "P4_PINS_LEN", lambda p: p["pillar_4_provenance_and_lean"].__setitem__("five_org_upstream_pins", {str(i): {} for i in range(7)})),
        # Coupled Pillar-3 mathematical forgeries preserving downstream algebraic identities
        ("p3_zeno_coupled_b", "P3_ZENO", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].update({"zeno_input_budget_q": {"num": 20, "den": 1}, "zeno_remaining_budget_q": {"num": 199, "den": 10}})),
        ("p3_zeno_coupled_c", "P3_ZENO", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].update({"zeno_step_cost_q": {"num": 1, "den": 5}, "zeno_remaining_budget_q": {"num": 5 * 10**16 - 1, "den": 5}})),
        ("p3_roy_coupled_gross", "P3_ROY", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].update({"royalty_u64_threshold_wei": 10000, "royalty_upstream_wei": 1500, "royalty_weaver_wei": 8500})),
        ("p3_roy_coupled_bps", "P3_ROY", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].update({"royalty_bps": 2000, "royalty_upstream_wei": (12297829382473035 * 2000) // 10000, "royalty_weaver_wei": 12297829382473035 - (12297829382473035 * 2000) // 10000})),
        ("p3_roy_coupled_up", "P3_ROY", lambda p: p["pillar_3_c2_anchors_safetensors"]["weft_c2_exact_gate"].update({"royalty_upstream_wei": 100, "royalty_weaver_wei": 12297829382473035 - 100})),
        ("p3_e8_coupled_eta", "P3_E8_Q", lambda p: p["pillar_3_c2_anchors_safetensors"]["strict_safetensors_and_rmsnorm_e8"].update({"rmsnorm_eta_q": {"num": 1, "den": 2}, "rmsnorm_s_lower_q": {"num": 1, "den": 6}, "rmsnorm_s_upper_q": {"num": 1, "den": 4}, "rmsnorm_s_upper_dec4": "0.2500", "rmsnorm_split_l4_upper_q": {"num": 1, "den": 16}})),
    ]
    for label, code, mut in forgeries:
        _assert_all_surfaces_reject(mut, code, label)

    # Self-consistency guards in verifier (P1_RJ_MUST_FAIL, P2_SCAN_MISS, P2_CTRL)
    orig_rj = oracle.ZONE_CANON_REJECT_VECTORS
    try:
        oracle.ZONE_CANON_REJECT_VECTORS = (("fake_rj", "v1_utf8", "{}"),) + orig_rj[1:]
        p_mut = copy.deepcopy(base_payload)
        p_mut["pillar_1_zone_canon_v1"]["reject_vectors"][0]["name"] = "fake_rj"
        p_mut["pillar_1_zone_canon_v1"]["reject_vectors"][0]["profile"] = "v1_utf8"
        check_raises(verifier.S98Error, lambda: verifier.secondary_audit_payload(p_mut), "P1_RJ_MUST_FAIL", "P1_RJ_MUST_FAIL")
    finally:
        oracle.ZONE_CANON_REJECT_VECTORS = orig_rj

    orig_atk = oracle.R10_LIVE_ATTACKS
    try:
        oracle.R10_LIVE_ATTACKS = (("fake_atk", False, False, "theorem ok : 1 = 1 := rfl\n"),) + orig_atk[1:]
        p_mut = copy.deepcopy(base_payload)
        p_mut["pillar_2_r10_lean_trust_gate"]["attack_matrix"][0]["attack_id"] = "fake_atk"
        check_raises(verifier.S98Error, lambda: verifier.secondary_audit_payload(p_mut), "P2_SCAN_MISS", "P2_SCAN_MISS")
    finally:
        oracle.R10_LIVE_ATTACKS = orig_atk

    orig_ctrl = oracle.R10_CLEAN_CONTROLS
    try:
        oracle.R10_CLEAN_CONTROLS = (("fake_ctrl", "theorem bad : True := by sorry\n"),) + orig_ctrl[1:]
        p_mut = copy.deepcopy(base_payload)
        p_mut["pillar_2_r10_lean_trust_gate"]["control_matrix"][0]["control_id"] = "fake_ctrl"
        check_raises(verifier.S98Error, lambda: verifier.secondary_audit_payload(p_mut), "P2_CTRL", "P2_CTRL dirty")
    finally:
        oracle.R10_CLEAN_CONTROLS = orig_ctrl


def run_all() -> int:
    tests = [
        test_1_certificate_standalone_and_cli,
        test_2_safe_io_and_strict_json_zone_b,
        test_5_pillar3_c2_anchors_safetensors_e8,
        test_6_resigned_semantic_forgeries_all_surfaces,
        test_3_pillar1_zone_canon_and_rust_parity,
        test_4_pillar2_r10_lean_gate_and_live_lean,
    ]
    for fn in tests:
        fn()
    sys.stdout.write(f"S98_R5_PASS {len(tests)}/{len(tests)} tests (0 skips)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_all())
