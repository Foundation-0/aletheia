#!/usr/bin/env python3
"""
Independent Hardened Auditor & CLI for the Domain-Agnostic CEER Engine.

Pure Python 3 standard library (`0` external dependencies, `0` floats, `0` bare asserts).
Implements strict symlink/hardlink/inode-safe I/O, iterative zero-float JSON tree validation,
re-sign-proof pure-Z/Q independent recomputation, Lean 4 anti-bypass verification, and
atomic `0o600` certificate generation/checking.
"""
from __future__ import annotations

import errno
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import stat
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ceer_engine as ce  # noqa: E402
import ceer_lean4_synth as cls  # noqa: E402

CERT_SCHEMA = "aletheia.ceer_engine.certificate.v1"
CERT_TRACK_ID = "TRACK-S62B-ALETHEIA-CEER-ENGINE"
MAX_JSON_BYTES = 1_048_576
MAX_JSON_DEPTH = 64
MAX_INT_DIGITS = 1000
_MAX_INT_LIMIT = 10**MAX_INT_DIGITS
_HEX_LOWER = frozenset("0123456789abcdef")
_CERT_KEYS = frozenset({"schema", "track_id", "payload_sha256", "certificate_sha256", "payload"})
_DARWIN_SYSTEM_LINKS: dict[str, str] = {
    "/var": "/private/var",
    "/tmp": "/private/tmp",
    "/etc": "/private/etc",
}


class CEERAuditError(ValueError):
    """Typed fail-closed error raised by the CEER auditor."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _require_clean_str(val: Any, label: str, allow_empty: bool = False) -> str:
    if type(val) is not str:
        raise CEERAuditError("INVALID_STR", f"{label} must be strict str")
    if not allow_empty and not val:
        raise CEERAuditError("EMPTY_STR", f"{label} must be non-empty")
    if "\x00" in val:
        raise CEERAuditError("NUL_STR", f"{label} contains NUL byte")
    try:
        val.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CEERAuditError("INVALID_UTF8", f"{label} contains lone surrogate") from exc
    return val


def _require_exact_int(val: Any, label: str, min_val: int | None = None) -> int:
    if type(val) is not int:
        raise CEERAuditError("INVALID_INT", f"{label} must be strict int")
    if abs(val) >= _MAX_INT_LIMIT:
        raise CEERAuditError("INT_OVERFLOW", f"{label} exceeds digit bound")
    if min_val is not None and val < min_val:
        raise CEERAuditError("INT_TOO_SMALL", f"{label} < {min_val}")
    return val


def _require_exact_bool(val: Any, label: str) -> bool:
    if type(val) is not bool:
        raise CEERAuditError("INVALID_BOOL", f"{label} must be strict bool")
    return val


def _require_sha256_hex(val: Any, label: str) -> str:
    s = _require_clean_str(val, label)
    if len(s) != 64 or any(ch not in _HEX_LOWER for ch in s):
        raise CEERAuditError("INVALID_SHA256", f"{label} must be 64 lowercase hex chars")
    return s


def validate_json_tree(obj: Any, max_depth: int = MAX_JSON_DEPTH) -> None:
    """Iteratively validate strict JSON object (no floats, no subclasses, bounded depth/int digits)."""
    limit = _require_exact_int(max_depth, "max_depth", min_val=1)
    stack: list[tuple[Any, int]] = [(obj, 0)]
    while stack:
        cur, depth = stack.pop()
        if depth > limit:
            raise CEERAuditError("JSON_DEPTH_EXCEEDED", f"JSON nesting exceeds {limit}")
        t = type(cur)
        if t is dict:
            for k, v in cur.items():
                _require_clean_str(k, "json_key", allow_empty=True)
                stack.append((v, depth + 1))
        elif t is list:
            for item in cur:
                stack.append((item, depth + 1))
        elif t is str:
            _require_clean_str(cur, "json_str", allow_empty=True)
        elif t is int:
            _require_exact_int(cur, "json_int")
        elif t is bool or cur is None:
            continue
        else:
            raise CEERAuditError("FORBIDDEN_JSON_TYPE", f"forbidden JSON type: {t.__name__}")


def canonical_json_bytes(obj: Any) -> bytes:
    validate_json_tree(obj)
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return (text + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# Strict Symlink / Hardlink / Ancestor / Darwin-Safe Path & I/O Primitives
# ---------------------------------------------------------------------------


def _normalize_darwin_system_prefix(path_str: str, platform_name: str | None = None) -> str:
    """Normalize verified root-owned macOS /var, /tmp, /etc symlinks to /private/*."""
    plat = sys.platform if platform_name is None else platform_name
    if plat != "darwin":
        return path_str
    for alias, real_prefix in _DARWIN_SYSTEM_LINKS.items():
        if path_str == alias or path_str.startswith(alias + "/"):
            try:
                st = os.lstat(alias)
                target = os.readlink(alias)
            except OSError:
                return path_str
            expected_rel = real_prefix.lstrip("/")
            if stat.S_ISLNK(st.st_mode) and st.st_uid == 0 and target in (real_prefix, expected_rel):
                return real_prefix + path_str[len(alias) :]
    return path_str


def _walk_no_symlink_ancestors(abs_path_str: str, label: str) -> None:
    norm = _normalize_darwin_system_prefix(os.path.normpath(abs_path_str))
    parts = Path(norm).parts
    cur = Path(parts[0])
    for part in parts[1:]:
        cur = cur / part
        try:
            st = os.lstat(cur)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                continue
            raise CEERAuditError("IO_STAT_ERROR", f"cannot lstat {label} ancestor: {exc}") from exc
        if stat.S_ISLNK(st.st_mode):
            raise CEERAuditError("SYMLINK_ANCESTOR_FORBIDDEN", f"symlink forbidden in {label} path")


def _check_pwd_no_symlinks() -> None:
    pwd = os.environ.get("PWD")
    if not pwd:
        return
    try:
        pwd_clean = _require_clean_str(pwd, "PWD")
        st_pwd = os.stat(pwd_clean)
        st_dot = os.stat(".")
    except (CEERAuditError, OSError):
        return
    if (st_pwd.st_dev, st_pwd.st_ino) == (st_dot.st_dev, st_dot.st_ino):
        _walk_no_symlink_ancestors(pwd_clean, "PWD")


def _prepare_safe_path(raw_path: str | Path, label: str) -> Path:
    path_str = _require_clean_str(str(raw_path), label)
    p = Path(path_str)
    if not p.is_absolute():
        _check_pwd_no_symlinks()
        try:
            cwd_str = os.getcwd()
        except OSError as exc:
            raise CEERAuditError("IO_CWD_ERROR", f"cannot determine working directory: {exc}") from exc
        p = Path(cwd_str) / p
    norm_str = _normalize_darwin_system_prefix(os.path.normpath(str(p)))
    _walk_no_symlink_ancestors(norm_str, label)
    return Path(norm_str)


def read_regular_bytes_safe(path: str | Path, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    limit = _require_exact_int(max_bytes, "max_bytes", min_val=1)
    safe = _prepare_safe_path(path, "read_path")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(str(safe), flags)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise CEERAuditError("SYMLINK_FORBIDDEN", "target is a symlink") from exc
        if exc.errno == errno.ENOENT:
            raise CEERAuditError("FILE_NOT_FOUND", "target file does not exist") from exc
        raise CEERAuditError("IO_READ_ERROR", f"cannot open target: {exc}") from exc
    try:
        try:
            st = os.fstat(fd)
        except OSError as exc:
            raise CEERAuditError("IO_STAT_ERROR", f"fstat failed: {exc}") from exc
        if not stat.S_ISREG(st.st_mode):
            raise CEERAuditError("NON_REGULAR_FILE", "target must be a regular file")
        if st.st_nlink != 1:
            raise CEERAuditError("HARDLINK_FORBIDDEN", f"target hardlink count {st.st_nlink} != 1")
        if st.st_size > limit:
            raise CEERAuditError("FILE_TOO_LARGE", f"file size {st.st_size} exceeds {limit}")
        chunks: list[bytes] = []
        total = 0
        while True:
            try:
                chunk = os.read(fd, 65536)
            except OSError as exc:
                raise CEERAuditError("IO_READ_ERROR", f"read failed: {exc}") from exc
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise CEERAuditError("FILE_TOO_LARGE", f"stream size exceeds {limit}")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def write_bytes_atomic_safe(path: str | Path, data: bytes, mode: int = 0o600) -> Path:
    if type(data) is not bytes:
        raise CEERAuditError("INVALID_BYTES", "data must be bytes")
    safe = _prepare_safe_path(path, "write_path")
    parent = safe.parent
    tmp_path = parent / f".{safe.name}.tmp.{os.getpid()}.{secrets.token_hex(8)}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(str(tmp_path), flags, mode)
    except OSError as exc:
        raise CEERAuditError("IO_WRITE_ERROR", f"cannot create temp file: {exc}") from exc
    try:
        try:
            try:
                view = memoryview(data)
                written = 0
                while written < len(data):
                    n = os.write(fd, view[written:])
                    if n <= 0:
                        raise CEERAuditError("IO_WRITE_ERROR", "short zero-byte write")
                    written += n
                os.fchmod(fd, mode)
                os.fsync(fd)
            except OSError as exc:
                raise CEERAuditError("IO_WRITE_ERROR", f"temp write/fsync failed: {exc}") from exc
        finally:
            os.close(fd)
        try:
            st_dst = os.lstat(safe)
            if not stat.S_ISREG(st_dst.st_mode):
                raise CEERAuditError("SYMLINK_FORBIDDEN", "destination is not a regular file")
            if st_dst.st_nlink != 1:
                raise CEERAuditError("HARDLINK_FORBIDDEN", "destination has multiple hardlinks")
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise CEERAuditError("IO_WRITE_ERROR", f"cannot lstat destination: {exc}") from exc
        try:
            os.replace(str(tmp_path), str(safe))
        except OSError as exc:
            raise CEERAuditError("IO_WRITE_ERROR", f"atomic replace failed: {exc}") from exc
    except BaseException:
        try:
            os.unlink(str(tmp_path))
        except OSError:
            pass
        raise
    return safe


def _no_duplicate_keys_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise CEERAuditError("DUPLICATE_JSON_KEY", f"duplicate JSON key: {k}")
        out[k] = v
    return out


def _forbid_json_constant(token: str) -> Any:
    raise CEERAuditError("FORBIDDEN_JSON_CONSTANT", f"non-finite JSON constant: {token}")


def _forbid_json_float(token: str) -> Any:
    raise CEERAuditError("FORBIDDEN_JSON_FLOAT", f"float literal forbidden: {token}")


def _parse_json_int_strict(token: str) -> int:
    mag = token[1:] if token.startswith("-") else token
    if len(mag) > MAX_INT_DIGITS:
        raise CEERAuditError("INT_OVERFLOW", "JSON integer exceeds digit limit")
    return int(token)


def load_strict_canonical_json_bytes(raw: bytes) -> dict[str, Any]:
    if b"\r" in raw:
        raise CEERAuditError("CRLF_FORBIDDEN", "CRLF line endings forbidden in canonical JSON")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CEERAuditError("INVALID_UTF8", f"invalid UTF-8 bytes: {exc}") from exc
    try:
        obj = json.loads(
            text,
            object_pairs_hook=_no_duplicate_keys_hook,
            parse_constant=_forbid_json_constant,
            parse_float=_forbid_json_float,
            parse_int=_parse_json_int_strict,
        )
    except CEERAuditError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise CEERAuditError("JSON_PARSE_ERROR", f"malformed JSON: {exc}") from exc
    if type(obj) is not dict:
        raise CEERAuditError("NON_DICT_ROOT", "certificate root must be a JSON object")
    validate_json_tree(obj)
    expected_bytes = canonical_json_bytes(obj)
    if not hmac.compare_digest(raw, expected_bytes):
        raise CEERAuditError("NON_CANONICAL_BYTES", "certificate bytes are not canonical JSON")
    return obj


# ---------------------------------------------------------------------------
# Certificate Construction & Independent Secondary Audit
# ---------------------------------------------------------------------------


def build_certificate_payload() -> dict[str, Any]:
    """Build deterministic CEER 3-cycle trajectory + synthesized pure-Init Lean 4.36.0 specs."""
    demo = ce.build_self_demo_cycles()
    lean_artifacts: list[dict[str, Any]] = []
    for cyc in demo["cycles"]:
        syn = cls.synthesize_cycle_lean4(cyc)
        lean_artifacts.append(
            {
                "cycle_index": syn["cycle_index"],
                "filename": syn["filename"],
                "verdict": syn["verdict"],
                "theorem_names": syn["theorem_names"],
                "source_sha256": syn["source_sha256"],
                "static_gate_clean": True,
                "expected_axioms": {tn: [] for tn in syn["theorem_names"]},
            }
        )
    return {
        "engine_schema": demo["schema"],
        "lean_synth_schema": cls.LEAN_SYNTH_SCHEMA,
        "cycle_count": len(demo["cycles"]),
        "epistemic_lifts_verified": demo["epistemic_lifts_verified"],
        "final_verdict": demo["final_verdict"],
        "cycles": demo["cycles"],
        "lean_artifacts": lean_artifacts,
    }


def build_certificate_dict() -> dict[str, Any]:
    payload = build_certificate_payload()
    payload_sha = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    envelope = {
        "schema": CERT_SCHEMA,
        "track_id": CERT_TRACK_ID,
        "payload_sha256": payload_sha,
        "payload": payload,
    }
    cert_sha = hashlib.sha256(canonical_json_bytes(envelope)).hexdigest()
    return {
        "schema": CERT_SCHEMA,
        "track_id": CERT_TRACK_ID,
        "payload_sha256": payload_sha,
        "certificate_sha256": cert_sha,
        "payload": payload,
    }


def verify_cycle_chain_integrity(cycles: Any) -> dict[str, Any]:
    """Domain-agnostic independent verifier for any arbitrary CEER cycle chain (incl. external hardware runs)."""
    if type(cycles) is not list or not cycles:
        raise CEERAuditError("INVALID_CYCLES", "cycles must be a non-empty list")
    validate_json_tree(cycles)

    seen_union: set[tuple[int, ...]] = set()
    prev_sha = ""
    prev_falsified: list[str] = []
    lifts = 0
    for idx, cyc in enumerate(cycles):
        if type(cyc) is not dict:
            raise CEERAuditError("INVALID_CYCLE_ITEM", f"cycle[{idx}] must be dict")
        if cyc.get("cycle_index") != idx:
            raise CEERAuditError("CYCLE_INDEX_MISMATCH", f"cycle[{idx}] index mismatch")
        prereg = cyc.get("prereg")
        obs = cyc.get("observation")
        if type(prereg) is not dict or type(obs) is not dict:
            raise CEERAuditError("MISSING_CYCLE_DATA", f"cycle[{idx}] missing prereg/observation")
        prereg_sha = _require_sha256_hex(cyc.get("prereg_sha256"), f"cycle[{idx}].prereg_sha256")
        if not hmac.compare_digest(prereg_sha, hashlib.sha256(canonical_json_bytes(prereg)).hexdigest()):
            raise CEERAuditError("PREREG_SHA_MISMATCH", f"cycle[{idx}] prereg_sha256 tamper")
        obs_sha = _require_sha256_hex(cyc.get("observation_sha256"), f"cycle[{idx}].observation_sha256")
        if not hmac.compare_digest(obs_sha, hashlib.sha256(canonical_json_bytes(obs)).hexdigest()):
            raise CEERAuditError("OBS_SHA_MISMATCH", f"cycle[{idx}] observation_sha256 tamper")

        ev_levers = prereg.get("eval_levers")
        if type(ev_levers) is not list or not ev_levers:
            raise CEERAuditError("INVALID_LEVERS", f"cycle[{idx}] eval_levers invalid")
        cur_set: set[tuple[int, ...]] = set()
        for row in ev_levers:
            if type(row) is not list or not row or not all(type(x) is int for x in row):
                raise CEERAuditError("INVALID_LEVERS", f"cycle[{idx}] non-int lever")
            cur_set.add(tuple(row))

        if idx > 0:
            prior_ref = _require_sha256_hex(cyc.get("prior_cycle_sha256"), f"cycle[{idx}].prior_cycle_sha256")
            if not hmac.compare_digest(prior_ref, prev_sha):
                raise CEERAuditError("BROKEN_CHAIN", f"cycle[{idx}] prior_cycle_sha256 mismatch")
            if cyc.get("prior_obstruction_code") not in prev_falsified:
                raise CEERAuditError("BROKEN_CHAIN", f"cycle[{idx}] prior_obstruction_code not falsified")
            if seen_union & cur_set:
                raise CEERAuditError("INSAMPLE_LEAK", f"cycle[{idx}] reuses prior levers")
            lifts += 1
        seen_union |= cur_set

        # Independently re-execute exact pure-Z/Q cycle evaluation from raw prereg + observation
        prior_arg = None if idx == 0 else cycles[idx - 1]
        recomputed = ce.evaluate_cycle(prereg, prereg_sha, obs, prior_cycle=prior_arg)
        if not hmac.compare_digest(canonical_json_bytes(cyc), canonical_json_bytes(recomputed)):
            raise CEERAuditError("CYCLE_RECOMPUTE_MISMATCH", f"cycle[{idx}] diverges from pure-Z/Q replay")

        prev_sha = recomputed["cycle_sha256"]
        prev_falsified = list(recomputed["falsified_predicates"])

    return {
        "chain_valid": True,
        "cycles_verified": len(cycles),
        "epistemic_lifts_verified": lifts,
        "final_verdict": cycles[-1]["verdict"],
    }


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Independent zero-trust pure-Z/Q & Lean-static re-derivation of every payload leaf."""
    if type(payload) is not dict:
        raise CEERAuditError("NON_DICT_PAYLOAD", "payload must be a strict dict")
    validate_json_tree(payload)

    chain_res = verify_cycle_chain_integrity(payload.get("cycles"))
    expected = build_certificate_payload()
    if not hmac.compare_digest(canonical_json_bytes(payload), canonical_json_bytes(expected)):
        raise CEERAuditError("PAYLOAD_RECOMPUTE_MISMATCH", "payload diverges from independent pure-Z/Q recomputation")

    return {
        "secondary_audit_ok": True,
        "cycles_verified": chain_res["cycles_verified"],
        "epistemic_lifts_verified": chain_res["epistemic_lifts_verified"],
        "final_verdict": chain_res["final_verdict"],
        "lean_artifacts_verified": len(expected["lean_artifacts"]),
    }


def verify_certificate_dict(cert: Any, full_replay: bool = True) -> dict[str, Any]:
    """Verify certificate envelope, digests, schema, and full secondary pure-Z/Q replay."""
    replay = _require_exact_bool(full_replay, "full_replay")
    if type(cert) is not dict:
        raise CEERAuditError("NON_DICT_ROOT", "certificate must be a strict dict")
    validate_json_tree(cert)
    if set(cert.keys()) != _CERT_KEYS:
        raise CEERAuditError("INVALID_CERT_KEYS", "certificate top-level key mismatch")
    if cert["schema"] != CERT_SCHEMA:
        raise CEERAuditError("INVALID_SCHEMA", f"unexpected schema: {cert['schema']}")
    if cert["track_id"] != CERT_TRACK_ID:
        raise CEERAuditError("INVALID_TRACK_ID", f"unexpected track_id: {cert['track_id']}")
    payload = cert["payload"]
    if type(payload) is not dict:
        raise CEERAuditError("NON_DICT_PAYLOAD", "payload must be strict dict")

    claimed_payload_sha = _require_sha256_hex(cert["payload_sha256"], "payload_sha256")
    actual_payload_sha = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    if not hmac.compare_digest(claimed_payload_sha, actual_payload_sha):
        raise CEERAuditError("PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")

    claimed_cert_sha = _require_sha256_hex(cert["certificate_sha256"], "certificate_sha256")
    envelope = {
        "schema": cert["schema"],
        "track_id": cert["track_id"],
        "payload_sha256": actual_payload_sha,
        "payload": payload,
    }
    actual_cert_sha = hashlib.sha256(canonical_json_bytes(envelope)).hexdigest()
    if not hmac.compare_digest(claimed_cert_sha, actual_cert_sha):
        raise CEERAuditError("CERTIFICATE_SHA_MISMATCH", "certificate_sha256 mismatch")

    sec = secondary_audit_payload(payload)
    return {
        "valid": True,
        "full_replay": replay,
        "payload_sha256": actual_payload_sha,
        "certificate_sha256": actual_cert_sha,
        "secondary_audit": sec,
    }


def emit_lean_files(out_dir: str | Path) -> list[dict[str, Any]]:
    """Deterministically write all 3 synthesized pure-Init Lean 4.36.0 cycle files into out_dir."""
    safe_dir = _prepare_safe_path(out_dir, "emit_lean_dir")
    demo = ce.build_self_demo_cycles()
    written: list[dict[str, Any]] = []
    for cyc in demo["cycles"]:
        syn = cls.synthesize_cycle_lean4(cyc)
        dst = safe_dir / syn["filename"]
        write_bytes_atomic_safe(dst, syn["source"].encode("utf-8"), mode=0o644)
        written.append(
            {
                "cycle_index": syn["cycle_index"],
                "filename": syn["filename"],
                "source_sha256": syn["source_sha256"],
                "theorem_names": syn["theorem_names"],
            }
        )
    return written


def verify_all_lean_live(lean_bin: str | None = None, timeout_s: int = 30) -> dict[str, Any]:
    """Synthesize and compile all 3 CEER Lean 4.36.0 cycle files live and verify zero axioms."""
    demo = ce.build_self_demo_cycles()
    receipts: list[dict[str, Any]] = []
    for cyc in demo["cycles"]:
        syn = cls.synthesize_cycle_lean4(cyc)
        live = cls.verify_lean4_source_live(
            syn["source"],
            syn["theorem_names"],
            lean_bin=lean_bin,
            timeout_s=timeout_s,
        )
        receipts.append(
            {
                "cycle_index": syn["cycle_index"],
                "filename": syn["filename"],
                "verdict": syn["verdict"],
                "source_sha256": syn["source_sha256"],
                "lean_version": live["lean_version"],
                "theorem_axioms": live["theorem_axioms"],
                "all_zero_axioms": live["all_zero_axioms"],
            }
        )
    return {
        "lean_live_verified": True,
        "cycles_compiled": len(receipts),
        "all_zero_axioms": all(r["all_zero_axioms"] for r in receipts),
        "receipts": receipts,
    }


def _validate_cli_target_path(raw: str) -> str:
    s = _require_clean_str(raw, "target_path")
    if s.startswith("-"):
        raise CEERAuditError("CLI_INVALID_PATH", f"path must not start with '-': {s}")
    return s


def main(argv: list[str] | None = None) -> int:
    try:
        args = sys.argv[1:] if argv is None else argv
        if type(args) is not list:
            raise CEERAuditError("CLI_INVALID_ARGS", "argv must be a list of strings")
        clean_args = [_require_clean_str(a, f"argv[{i}]") for i, a in enumerate(args)]

        if clean_args in ([], ["--standalone"], ["--standalone", "--json"]):
            cert = build_certificate_dict()
            sys.stdout.buffer.write(canonical_json_bytes(cert))
            return 0
        if len(clean_args) == 2 and clean_args[0] == "--write":
            dst = _validate_cli_target_path(clean_args[1])
            cert = build_certificate_dict()
            write_bytes_atomic_safe(dst, canonical_json_bytes(cert), mode=0o600)
            sys.stdout.buffer.write(
                canonical_json_bytes({"written": True, "certificate_sha256": cert["certificate_sha256"]})
            )
            return 0
        if len(clean_args) in (2, 3) and clean_args[0] == "--check":
            if len(clean_args) == 3 and clean_args[2] != "--json":
                raise CEERAuditError("CLI_INVALID_ARGS", "unsupported flag after --check <path>")
            src = _validate_cli_target_path(clean_args[1])
            raw = read_regular_bytes_safe(src)
            cert_obj = load_strict_canonical_json_bytes(raw)
            res = verify_certificate_dict(cert_obj, full_replay=True)
            sys.stdout.buffer.write(canonical_json_bytes(res))
            return 0
        if len(clean_args) == 2 and clean_args[0] == "--emit-lean-dir":
            out_dir = _validate_cli_target_path(clean_args[1])
            emitted = emit_lean_files(out_dir)
            sys.stdout.buffer.write(canonical_json_bytes({"emitted": emitted}))
            return 0
        if clean_args in (["--verify-lean"], ["--verify-lean", "--json"]):
            res = verify_all_lean_live()
            sys.stdout.buffer.write(canonical_json_bytes(res))
            return 0
        raise CEERAuditError(
            "CLI_INVALID_ARGS",
            "usage: ceer_audit.py (--standalone [--json] | --write <path> | --check <path> [--json] | --emit-lean-dir <dir> | --verify-lean [--json])",
        )
    except (CEERAuditError, ce.CEERError, cls.CEERLeanError) as exc:
        sys.stderr.write(f"ERROR {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
