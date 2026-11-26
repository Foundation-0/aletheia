#!/usr/bin/env python3
"""Fail-closed CLI auditor and canonical zero-float certificate verifier for Track S21c."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from aska_zoneb_tomography_oracle import (
    TomographyError,
    coerce_exact_path,
    compute_tomography_payload,
    reject_symlinks_on_path,
    verify_live_repos_dir,
)

SCHEMA_ID = "aletheia.track_s21c.aska_physical_zone_b_tomography.v1"
CERT_KEYS = frozenset({"schema", "payload", "payload_sha256", "certificate_sha256"})
HEX_LOWER = frozenset("0123456789abcdef")
MAX_JSON_DEPTH = 64
MAX_INT_DIGITS = 1000
MAX_INT_BITS = MAX_INT_DIGITS * 4


def _int_digit_len(val: int) -> int:
    mag = -val if val < 0 else val
    if mag == 0:
        return 1
    if mag.bit_length() > MAX_INT_BITS:
        return MAX_INT_DIGITS + 1
    return len(str(mag))


def validate_json_tree_iterative(obj: Any, max_depth: int = MAX_JSON_DEPTH) -> None:
    if type(max_depth) is not int or max_depth < 1:
        raise TomographyError("INVALID_DEPTH", "max_depth must be positive exact int")
    stack: list[tuple[Any, int]] = [(obj, 0)]
    while stack:
        cur, depth = stack.pop()
        if depth > max_depth:
            raise TomographyError("JSON_DEPTH_EXCEEDED", "JSON nesting depth exceeded")
        t = type(cur)
        if t is dict:
            for k, v in cur.items():
                if type(k) is not str:
                    raise TomographyError("NON_STR_KEY", "JSON object keys must be exact str")
                try:
                    k.encode("utf-8")
                except UnicodeEncodeError as exc:
                    raise TomographyError("INVALID_UNICODE", "lone UTF-16 surrogate in key") from exc
                stack.append((v, depth + 1))
        elif t is list:
            for item in cur:
                stack.append((item, depth + 1))
        elif t is str:
            try:
                cur.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise TomographyError("INVALID_UNICODE", "lone UTF-16 surrogate in str") from exc
        elif t is int:
            if _int_digit_len(cur) > MAX_INT_DIGITS:
                raise TomographyError("INT_TOO_LARGE", "integer exceeds MAX_INT_DIGITS")
        elif t is bool or cur is None:
            continue
        else:
            raise TomographyError("FORBIDDEN_TYPE", f"forbidden JSON value type: {t.__name__}")


def canonical_json_bytes(obj: Any) -> bytes:
    validate_json_tree_iterative(obj)
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_hex64(val: Any, label: str) -> str:
    if type(val) is not str or len(val) != 64:
        raise TomographyError("INVALID_DIGEST", f"{label} must be 64-char lowercase hex str")
    for ch in val:
        if ch not in HEX_LOWER:
            raise TomographyError("INVALID_DIGEST", f"{label} contains non-hex character")
    return val


def _reject_float_constant(raw: str) -> Any:
    raise TomographyError("FLOAT_FORBIDDEN", f"float literal forbidden: {raw}")


def _strict_int(raw: str) -> int:
    if len(raw) > MAX_INT_DIGITS + 1:
        raise TomographyError("INT_TOO_LARGE", "integer literal exceeds digit cap")
    try:
        val = int(raw, 10)
    except ValueError as exc:
        raise TomographyError("INVALID_INT", "integer parse failure") from exc
    if _int_digit_len(val) > MAX_INT_DIGITS:
        raise TomographyError("INT_TOO_LARGE", "integer literal exceeds MAX_INT_DIGITS")
    return val


def _strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise TomographyError("DUPLICATE_KEY", f"duplicate JSON key: {k}")
        out[k] = v
    return out


def parse_strict_json_text(raw_text: str) -> dict[str, Any]:
    if type(raw_text) is not str or not raw_text.strip():
        raise TomographyError("EMPTY_JSON", "JSON text must be non-empty str")
    try:
        raw_text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise TomographyError("INVALID_UNICODE", "lone surrogate in JSON text") from exc
    try:
        parsed = json.loads(
            raw_text,
            parse_float=_reject_float_constant,
            parse_int=_strict_int,
            parse_constant=_reject_float_constant,
            object_pairs_hook=_strict_object_pairs,
        )
    except TomographyError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise TomographyError("JSON_PARSE_ERROR", f"malformed JSON: {exc}") from exc
    if type(parsed) is not dict:
        raise TomographyError("ROOT_NOT_OBJECT", "JSON root must be an object")
    validate_json_tree_iterative(parsed)
    return parsed


def build_certificate() -> dict[str, Any]:
    payload = compute_tomography_payload()
    payload_sha = sha256_hex(canonical_json_bytes(payload))
    envelope = {
        "schema": SCHEMA_ID,
        "payload": payload,
        "payload_sha256": payload_sha,
    }
    cert_sha = sha256_hex(canonical_json_bytes(envelope))
    return {
        "schema": SCHEMA_ID,
        "payload": payload,
        "payload_sha256": payload_sha,
        "certificate_sha256": cert_sha,
    }


def verify_certificate_dict(cert: Any) -> dict[str, Any]:
    if type(cert) is not dict:
        raise TomographyError("CERT_NOT_DICT", "certificate must be an exact dict")
    validate_json_tree_iterative(cert)
    if frozenset(cert.keys()) != CERT_KEYS:
        raise TomographyError("CERT_KEYS_MISMATCH", "unexpected certificate top-level keys")
    if cert["schema"] != SCHEMA_ID:
        raise TomographyError("SCHEMA_MISMATCH", "unexpected certificate schema")
    claimed_payload_sha = _require_hex64(cert["payload_sha256"], "payload_sha256")
    claimed_cert_sha = _require_hex64(cert["certificate_sha256"], "certificate_sha256")
    if type(cert["payload"]) is not dict:
        raise TomographyError("PAYLOAD_NOT_DICT", "certificate payload must be exact dict")

    actual_payload_sha = sha256_hex(canonical_json_bytes(cert["payload"]))
    if not hmac.compare_digest(claimed_payload_sha, actual_payload_sha):
        raise TomographyError("PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")
    envelope = {
        "schema": cert["schema"],
        "payload": cert["payload"],
        "payload_sha256": claimed_payload_sha,
    }
    actual_cert_sha = sha256_hex(canonical_json_bytes(envelope))
    if not hmac.compare_digest(claimed_cert_sha, actual_cert_sha):
        raise TomographyError("CERT_SHA_MISMATCH", "certificate_sha256 mismatch")

    expected = build_certificate()
    if not hmac.compare_digest(claimed_payload_sha, expected["payload_sha256"]):
        raise TomographyError("ORACLE_PAYLOAD_MISMATCH", "payload disagrees with recomputed oracle")
    return {
        "valid": True,
        "schema": SCHEMA_ID,
        "payload_sha256": claimed_payload_sha,
        "certificate_sha256": claimed_cert_sha,
    }


def check_certificate_file(path: Path | str) -> dict[str, Any]:
    p = coerce_exact_path(path)
    reject_symlinks_on_path(p)
    if not os.path.exists(p):
        raise TomographyError("FILE_NOT_FOUND", "certificate file does not exist")
    if not os.path.isfile(p):
        raise TomographyError("NOT_A_FILE", "certificate path is not a regular file")
    try:
        raw_bytes = p.read_bytes()
    except OSError as exc:
        raise TomographyError("FILE_READ_ERROR", "failed to read certificate file") from exc
    if b"\r" in raw_bytes:
        raise TomographyError("CRLF_FORBIDDEN", "CR/CRLF line endings forbidden")
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TomographyError("INVALID_UTF8", "certificate file is not valid UTF-8") from exc
    cert = parse_strict_json_text(raw_text)
    canonical = canonical_json_bytes(cert)
    stripped = raw_bytes[:-1] if raw_bytes.endswith(b"\n") else raw_bytes
    if stripped != canonical:
        raise TomographyError("NON_CANONICAL_JSON", "certificate bytes are not canonical JSON")
    return verify_certificate_dict(cert)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if args in ([], ["--standalone", "--json"]):
            cert = build_certificate()
            sys.stdout.write(canonical_json_bytes(cert).decode("ascii") + "\n")
            return 0
        if len(args) == 2 and args[0] == "--write":
            out_path = coerce_exact_path(args[1])
            reject_symlinks_on_path(out_path)
            if os.path.lexists(out_path) and not stat.S_ISREG(os.lstat(out_path).st_mode):
                raise TomographyError("NOT_A_FILE", "cannot write certificate to non-regular path")
            cert = build_certificate()
            try:
                out_path.write_bytes(canonical_json_bytes(cert) + b"\n")
            except OSError as exc:
                raise TomographyError("FILE_WRITE_ERROR", "failed to write certificate") from exc
            sys.stdout.write(canonical_json_bytes({"written": str(out_path), "certificate_sha256": cert["certificate_sha256"]}).decode("ascii") + "\n")
            return 0
        if len(args) == 2 and args[0] == "--check":
            res = check_certificate_file(args[1])
            sys.stdout.write(canonical_json_bytes(res).decode("ascii") + "\n")
            return 0
        if len(args) == 2 and args[0] == "--live-dir":
            res = verify_live_repos_dir(args[1])
            sys.stdout.write(canonical_json_bytes(res).decode("ascii") + "\n")
            return 0
        raise TomographyError("INVALID_CLI_ARGS", "usage: --standalone --json | --write <path> | --check <path> | --live-dir <dir>")
    except TomographyError as exc:
        sys.stderr.write(f"ERROR [{exc.code}]: {exc.message}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
