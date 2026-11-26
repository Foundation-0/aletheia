#!/usr/bin/env python3
r"""
`aletheia.magnetic_field_v21`: Unified v2.1 Zone-B Strict Certificate I/O,
Law-1b Solenoidal Omni-Vein Field-Coupling Router, Gate-8 Pre-Registration Ordering,
and Deterministic Pre-Push / Pre-Review Hygiene Gate.

Pure Python 3 stdlib (`int`, `fractions.Fraction`, `0` floats, `0` bare asserts,
`0` external dependencies).

Provides four cohesive capability groups:
  1. Zone-B-Hardened Strict Certificate I/O (`require_int`, `require_bool`, `require_str`,
     `require_seq`, `require_mapping`, `require_hex64_ascii`, `constant_time_hex64_equal`,
     `fmt_q`, `ratio_q`, `validate_json_value`, `parse_strict_json_text`, `loads_strict_json`,
     `canonical_json_bytes`, `canonical_sha256`, `require_no_symlink_path`,
     `load_strict_json_file`, `load_strict_jsonl_file`, `verify_canonical_cert_file`).
  2. Starvation-Capped Dual-Verifier Router & Law-1b Solenoidal Field-Coupling Dispatcher
     (`route_verification_task`, `compute_field_coupling_dispatch`, `evaluate_monitor_cadence`).
  3. Gate-8 Pre-Registration Timestamp-Order Guard (`verify_gate8_prereg_order`).
  4. Deterministic Pre-Push, Pre-Review & Workspace Hygiene Gate (`check_dco_signoff`,
     `check_repo_visibility`, `check_graphql_file_completeness`, `check_openblas_pin`,
     `check_pr_review_action`, `check_gitignore_receipt_integrity`, `check_text_hygiene`,
     `evaluate_pre_push_bundle`).

Usage:
  python3 -I -B aletheia/magnetic_field_v21.py --self-test --json
  python3 -I -B aletheia/magnetic_field_v21.py --check-bundle <bundle.json> [--json]
"""
from __future__ import annotations

import argparse
import errno
from fractions import Fraction
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any

MAX_JSON_DEPTH = 64
MAX_JSON_BYTES = 2_000_000
_READ_CHUNK_BYTES = 65_536
MAX_INT_BITS = 2048
MAX_INT_DIGITS = 620
MAX_SEQ_LEN = 4096

DEFAULT_STARVATION_CAP_S = 1800
MAX_POLLING_TURNS_PER_POST = 25
MAX_PR_POLL_SHARE_Q = Fraction(1, 10)

_EXACT_PATH_TYPES = (Path, type(Path()))
_HEX_LOWER = frozenset("0123456789abcdef")
_VALID_REVIEW_ACTIONS = frozenset({"NONE", "COMMENT", "APPROVE", "REQUEST_CHANGES"})


class MagneticFieldError(ValueError):
    """Fail-closed typed validation error (never stripped under `python3 -O`)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


# ---------------------------------------------------------------------------
# 1. Unified Zone-B-Hardened Strict Certificate I/O
# ---------------------------------------------------------------------------


def require_int(
    val: Any,
    label: str = "int",
    *,
    lo: int | None = None,
    hi: int | None = None,
) -> int:
    """Strict `int` guard rejecting bools/subclasses and >2048-bit integers (zero f-string int DoS)."""
    if type(val) is not int:
        raise MagneticFieldError("INVALID_INT_TYPE", f"{label} must be strict int, got {type(val).__name__}")
    blen = val.bit_length()
    if blen > MAX_INT_BITS:
        raise MagneticFieldError("INT_BIT_LIMIT", f"{label} bit_length={blen} exceeds {MAX_INT_BITS}")
    if lo is not None:
        if type(lo) is not int:
            raise MagneticFieldError("INVALID_BOUND_TYPE", f"{label} lo must be strict int")
        if val < lo:
            raise MagneticFieldError("INT_BELOW_MIN", f"{label} bit_length={blen} below min_bits={lo.bit_length()}")
    if hi is not None:
        if type(hi) is not int:
            raise MagneticFieldError("INVALID_BOUND_TYPE", f"{label} hi must be strict int")
        if val > hi:
            raise MagneticFieldError("INT_ABOVE_MAX", f"{label} bit_length={blen} above max_bits={hi.bit_length()}")
    return val


def require_bool(val: Any, label: str = "bool") -> bool:
    if type(val) is not bool:
        raise MagneticFieldError("INVALID_BOOL_TYPE", f"{label} must be strict bool, got {type(val).__name__}")
    return val


def _require_valid_utf8_str(s: str, label: str = "str") -> str:
    try:
        s.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise MagneticFieldError("INVALID_UTF8", f"{label} contains unpaired UTF-16 surrogate") from exc
    return s


def require_str(val: Any, label: str = "str", *, min_len: int = 1, max_len: int = 1024) -> str:
    if type(val) is not str:
        raise MagneticFieldError("INVALID_STR_TYPE", f"{label} must be strict str, got {type(val).__name__}")
    _require_valid_utf8_str(val, label)
    n = len(val)
    if n < min_len:
        raise MagneticFieldError("STR_TOO_SHORT", f"{label} length {n} < min_bits={min_len.bit_length()}")
    if n > max_len:
        raise MagneticFieldError("STR_TOO_LONG", f"{label} length {n} > max_bits={max_len.bit_length()}")
    return val


def require_seq(
    val: Any,
    label: str = "seq",
    *,
    min_len: int = 1,
    max_len: int = MAX_SEQ_LEN,
) -> tuple[Any, ...]:
    """Strict list/tuple guard rejecting lying `Sequence` implementations and list subclasses."""
    if type(val) not in (list, tuple):
        raise MagneticFieldError("INVALID_SEQ_TYPE", f"{label} must be strict list or tuple")
    n = len(val)
    if n < min_len:
        raise MagneticFieldError("SEQ_TOO_SHORT", f"{label} length {n} < min_bits={min_len.bit_length()}")
    if n > max_len:
        raise MagneticFieldError("SEQ_TOO_LONG", f"{label} length {n} > max_bits={max_len.bit_length()}")
    return tuple(val)


def require_mapping(val: Any, label: str = "mapping") -> dict[str, Any]:
    """Strict dict guard rejecting lying `Mapping` implementations, dict subclasses, and non-str keys."""
    if type(val) is not dict:
        raise MagneticFieldError("INVALID_MAPPING_TYPE", f"{label} must be strict dict")
    for k in val:
        if type(k) is not str:
            raise MagneticFieldError("NON_STR_KEY", f"{label} keys must be strict str")
        _require_valid_utf8_str(k, f"{label}.key")
    return val


def require_hex64_ascii(val: Any, label: str = "sha256") -> str:
    """Validate strict 64-char lowercase ASCII hex BEFORE any `hmac.compare_digest` call."""
    if type(val) is not str:
        raise MagneticFieldError("INVALID_DIGEST_TYPE", f"{label} must be strict str")
    if len(val) != 64:
        raise MagneticFieldError("INVALID_DIGEST_LEN", f"{label} must have length 64")
    for ch in val:
        if ch not in _HEX_LOWER:
            raise MagneticFieldError("INVALID_DIGEST_HEX", f"{label} must be lowercase ASCII hex")
    return val


def constant_time_hex64_equal(left: Any, right: Any, label: str = "sha256") -> bool:
    """Zone-B-safe constant-time SHA-256 comparison (never leaks raw `TypeError` on non-ASCII)."""
    a = require_hex64_ascii(left, f"{label}.left")
    b = require_hex64_ascii(right, f"{label}.right")
    return hmac.compare_digest(a, b)


def fmt_q(q: Fraction) -> str:
    if type(q) is not Fraction:
        raise MagneticFieldError("INVALID_FRACTION_TYPE", "q must be strict Fraction")
    nb = q.numerator.bit_length()
    db = q.denominator.bit_length()
    if nb > MAX_INT_BITS or db > MAX_INT_BITS:
        raise MagneticFieldError("FRACTION_BIT_LIMIT", f"fraction bit_lengths=({nb},{db}) exceed {MAX_INT_BITS}")
    if q.denominator == 1:
        return str(q.numerator)
    return f"{q.numerator}/{q.denominator}"


def ratio_q(num: int, den: int, label: str = "ratio") -> Fraction:
    n = require_int(num, f"{label}.num")
    d = require_int(den, f"{label}.den", lo=1)
    return Fraction(n, d)


def validate_json_value(obj: Any, *, max_depth: int = MAX_JSON_DEPTH) -> None:
    """Iterative zero-float, depth-capped, bit-length-capped, strict-type JSON validator."""
    limit = require_int(max_depth, "max_depth", lo=1, hi=128)
    stack: list[tuple[Any, int]] = [(obj, 0)]
    while stack:
        cur, depth = stack.pop()
        if depth > limit:
            raise MagneticFieldError("MAX_DEPTH_EXCEEDED", f"JSON nesting exceeds {limit}")
        t = type(cur)
        if t is dict:
            for k, v in cur.items():
                if type(k) is not str:
                    raise MagneticFieldError("NON_STR_KEY", "JSON object keys must be strict str")
                _require_valid_utf8_str(k, "json_key")
                stack.append((v, depth + 1))
        elif t is list:
            for item in cur:
                stack.append((item, depth + 1))
        elif t is int:
            blen = cur.bit_length()
            if blen > MAX_INT_BITS:
                raise MagneticFieldError("INT_BIT_LIMIT", f"JSON int bit_length={blen} exceeds {MAX_INT_BITS}")
        elif t is str:
            _require_valid_utf8_str(cur, "json_str")
        elif t is bool or cur is None:
            continue
        elif t is float:
            raise MagneticFieldError("FLOAT_FORBIDDEN", "float values are forbidden in exact JSON")
        else:
            raise MagneticFieldError("UNSUPPORTED_JSON_TYPE", f"unsupported JSON type {t.__name__}")


def _reject_float_token(tok: str) -> Any:
    raise MagneticFieldError("JSON_FLOAT_FORBIDDEN", f"float literal forbidden: {tok!r}")


def _reject_constant_token(tok: str) -> Any:
    raise MagneticFieldError("JSON_CONSTANT_FORBIDDEN", f"non-RFC8259 constant forbidden: {tok!r}")


def _parse_capped_int_token(tok: str) -> int:
    digits = tok[1:] if tok.startswith("-") else tok
    if len(digits) > MAX_INT_DIGITS:
        raise MagneticFieldError("INT_DIGIT_LIMIT", f"integer token exceeds {MAX_INT_DIGITS} digits")
    val = int(tok)
    blen = val.bit_length()
    if blen > MAX_INT_BITS:
        raise MagneticFieldError("INT_BIT_LIMIT", f"integer token bit_length={blen} exceeds {MAX_INT_BITS}")
    return val


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise MagneticFieldError("JSON_DUPLICATE_KEY", f"duplicate JSON key: {k!r}")
        out[k] = v
    return out


def parse_strict_json_text(
    raw_text: str,
    *,
    require_object: bool = True,
    max_depth: int = MAX_JSON_DEPTH,
) -> Any:
    """Zone-B-hardened exact JSON parser rejecting floats, NaN/Inf, duplicates, huge ints, and surrogates."""
    require_bool(require_object, "require_object")
    if type(raw_text) is not str:
        raise MagneticFieldError("INVALID_JSON_INPUT", "JSON text must be strict str")
    try:
        encoded = raw_text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise MagneticFieldError("INVALID_UTF8", f"JSON text contains unpaired surrogate: {exc}") from exc
    if len(encoded) > MAX_JSON_BYTES:
        raise MagneticFieldError("JSON_TOO_LARGE", f"JSON exceeds {MAX_JSON_BYTES} bytes")
    if len(raw_text.strip()) == 0:
        raise MagneticFieldError("EMPTY_JSON_INPUT", "JSON text must be non-empty")
    try:
        obj = json.loads(
            raw_text,
            parse_float=_reject_float_token,
            parse_constant=_reject_constant_token,
            parse_int=_parse_capped_int_token,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except MagneticFieldError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise MagneticFieldError("JSON_SYNTAX_ERROR", str(exc)) from exc
    validate_json_value(obj, max_depth=max_depth)
    if require_object and type(obj) is not dict:
        raise MagneticFieldError("JSON_ROOT_NOT_OBJECT", "top-level JSON payload must be an object")
    return obj


def loads_strict_json(raw_text: str, *, require_object: bool = False, max_depth: int = MAX_JSON_DEPTH) -> Any:
    return parse_strict_json_text(raw_text, require_object=require_object, max_depth=max_depth)


def canonical_json_bytes(obj: Any) -> bytes:
    """Serialize strictly validated exact JSON tree to canonical ASCII bytes."""
    validate_json_value(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def canonical_sha256(obj: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


def _validate_path_obj(path: Any) -> str:
    if type(path) not in _EXACT_PATH_TYPES:
        raise MagneticFieldError("INVALID_PATH_TYPE", "path must be concrete pathlib.Path")
    raw_s = str(path)
    _require_valid_utf8_str(raw_s, "path")
    if "\x00" in raw_s:
        raise MagneticFieldError("INVALID_PATH_NUL", "NUL byte forbidden in path")
    return raw_s


def _is_symlink_at(dfd: int, name: str) -> bool:
    try:
        return stat.S_ISLNK(os.lstat(name, dir_fd=dfd).st_mode)
    except OSError:
        return False


def _check_pwd_no_symlinks() -> None:
    pwd = os.environ.get("PWD")
    if pwd is None or not os.path.isabs(pwd):
        return
    _require_valid_utf8_str(pwd, "PWD")
    cur_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in Path(pwd).parts[1:]:
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if _is_symlink_at(cur_fd, comp):
                    raise MagneticFieldError("SYMLINK_ANCESTOR_FORBIDDEN", "symlink ancestor directory in PWD") from exc
                return
            os.close(cur_fd)
            cur_fd = nxt
    finally:
        os.close(cur_fd)


def require_no_symlink_path(path: Path) -> None:
    """Reject symlinks, non-concrete Path subclasses, unpaired UTF-16 surrogates, and NUL bytes."""
    _validate_path_obj(path)
    is_abs = path.is_absolute()
    if not is_abs:
        _check_pwd_no_symlinks()
    parts = path.parts[1:] if is_abs else path.parts
    if not parts:
        return
    ancestors, leaf = parts[:-1], parts[-1]
    cur_fd = os.open("/" if is_abs else ".", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in ancestors:
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if _is_symlink_at(cur_fd, comp):
                    raise MagneticFieldError("SYMLINK_ANCESTOR_FORBIDDEN", "symlink ancestor directory forbidden") from exc
                return
            os.close(cur_fd)
            cur_fd = nxt
        if _is_symlink_at(cur_fd, leaf):
            raise MagneticFieldError("SYMLINK_FORBIDDEN", "symlink target path forbidden")
    finally:
        os.close(cur_fd)


def _open_parent_dir_fd(path: Path) -> tuple[int, str]:
    _validate_path_obj(path)
    is_abs = path.is_absolute()
    if not is_abs:
        _check_pwd_no_symlinks()
    parts = path.parts[1:] if is_abs else path.parts
    if len(parts) == 0 or parts[-1] == "..":
        raise MagneticFieldError("FILE_NOT_FOUND", "path must name a regular file")
    ancestors, leaf = parts[:-1], parts[-1]
    cur_fd = os.open("/" if is_abs else ".", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in ancestors:
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if _is_symlink_at(cur_fd, comp):
                    raise MagneticFieldError("SYMLINK_ANCESTOR_FORBIDDEN", "symlink ancestor directory forbidden") from exc
                if exc.errno in (errno.ENOENT, errno.ENOTDIR):
                    raise MagneticFieldError("FILE_NOT_FOUND", "ancestor directory not found") from exc
                raise MagneticFieldError("FILE_READ_ERROR", f"cannot open ancestor: {exc}") from exc
            os.close(cur_fd)
            cur_fd = nxt
        return cur_fd, leaf
    except BaseException:
        os.close(cur_fd)
        raise


def _read_strict_utf8_file(path: Path) -> tuple[bytes, str]:
    dfd, leaf = _open_parent_dir_fd(path)
    try:
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise MagneticFieldError("SYMLINK_FORBIDDEN", "symlink target path forbidden") from exc
            if exc.errno in (errno.ENOENT, errno.ENOTDIR, errno.EISDIR):
                raise MagneticFieldError("FILE_NOT_FOUND", "regular file not found") from exc
            raise MagneticFieldError("FILE_READ_ERROR", f"cannot open file: {exc}") from exc
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                raise MagneticFieldError("FILE_NOT_FOUND", "regular file not found")
            chunks: list[bytes] = []
            total = 0
            while True:
                try:
                    chunk = os.read(fd, _READ_CHUNK_BYTES)
                except OSError as exc:
                    raise MagneticFieldError("FILE_READ_ERROR", f"cannot read file: {exc}") from exc
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_JSON_BYTES:
                    raise MagneticFieldError("FILE_TOO_LARGE", f"file exceeds {MAX_JSON_BYTES} bytes")
                chunks.append(chunk)
            raw = b"".join(chunks)
        finally:
            os.close(fd)
    finally:
        os.close(dfd)
    if b"\r" in raw:
        raise MagneticFieldError("CR_LINE_ENDINGS_FORBIDDEN", "CR/CRLF line endings forbidden")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MagneticFieldError("INVALID_UTF8", f"invalid UTF-8: {exc}") from exc
    return raw, text


def load_strict_json_file(
    path: Path,
    *,
    require_object: bool = True,
    max_depth: int = MAX_JSON_DEPTH,
) -> Any:
    """Fail-closed exact JSON file loader rejecting symlinks, CR/CRLF, oversize files, and Zone-B payloads."""
    _, text = _read_strict_utf8_file(path)
    return parse_strict_json_text(text, require_object=require_object, max_depth=max_depth)


def load_strict_jsonl_file(
    path: Path,
    *,
    require_object: bool = True,
    max_depth: int = MAX_JSON_DEPTH,
) -> list[Any]:
    """Fail-closed LF-only JSONL loader rejecting symlinks, CR/CRLF, blank/whitespace lines, and Zone-B payloads."""
    raw, text = _read_strict_utf8_file(path)
    if len(raw) == 0:
        return []
    if len(text.strip()) == 0:
        raise MagneticFieldError("JSONL_WHITESPACE_ONLY", "whitespace-only non-empty JSONL file")
    body = text[:-1] if text.endswith("\n") else text
    records: list[Any] = []
    for lineno, line in enumerate(body.split("\n"), start=1):
        if len(line.strip()) == 0:
            raise MagneticFieldError("JSONL_BLANK_LINE", f"blank line at line {lineno}")
        records.append(parse_strict_json_text(line, require_object=require_object, max_depth=max_depth))
    return records


def verify_canonical_cert_file(
    path: Path,
    *,
    expected_payload_sha256: str | None = None,
    max_depth: int = MAX_JSON_DEPTH,
) -> dict[str, Any]:
    """Verify exact canonical JSON file bytes and optional payload digest with Zone-B immunity."""
    raw, text = _read_strict_utf8_file(path)
    parsed = parse_strict_json_text(text, require_object=True, max_depth=max_depth)
    canonical_raw = canonical_json_bytes(parsed)
    if raw not in (canonical_raw, canonical_raw + b"\n"):
        raise MagneticFieldError("NON_CANONICAL_CERT_BYTES", "certificate file is not canonical JSON")
    file_sha = hashlib.sha256(canonical_raw).hexdigest()
    if expected_payload_sha256 is not None:
        want = require_hex64_ascii(expected_payload_sha256, "expected_payload_sha256")
        if "payload" not in parsed:
            raise MagneticFieldError("MISSING_PAYLOAD_KEY", "certificate missing payload key")
        got = canonical_sha256(parsed["payload"])
        if not constant_time_hex64_equal(got, want, "payload_sha256"):
            raise MagneticFieldError("PAYLOAD_SHA_MISMATCH", "payload SHA-256 mismatch")
    return {"valid": True, "canonical_sha256": file_sha, "parsed": parsed}


# ---------------------------------------------------------------------------
# 2. Starvation-Capped Dual-Verifier Router & Law-1b Field-Coupling Dispatcher
# ---------------------------------------------------------------------------


def route_verification_task(
    verifiers: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    preferred_verifier: str | None = None,
    oldest_wait_s: int = 0,
    starvation_cap_s: int = DEFAULT_STARVATION_CAP_S,
) -> dict[str, Any]:
    """Deterministic starvation-capped least-loaded verifier router (`N >= 2` verifiers)."""
    rows = require_seq(verifiers, "verifiers", min_len=2)
    wait = require_int(oldest_wait_s, "oldest_wait_s", lo=0)
    cap = require_int(starvation_cap_s, "starvation_cap_s", lo=60)
    pref: str | None = None
    if preferred_verifier is not None:
        pref = require_str(preferred_verifier, "preferred_verifier", min_len=1, max_len=64)

    parsed: list[tuple[Fraction, int, str]] = []
    by_id: dict[str, tuple[Fraction, int]] = {}
    for item in rows:
        m = require_mapping(item, "verifier_slot")
        vid = require_str(m.get("verifier_id"), "verifier_id", min_len=1, max_len=64)
        if vid in by_id:
            raise MagneticFieldError("DUPLICATE_VERIFIER_ID", f"duplicate verifier_id {vid}")
        qdepth = require_int(m.get("queue_depth"), "queue_depth", lo=0)
        max_conc = require_int(m.get("max_concurrent", 1), "max_concurrent", lo=1, hi=64)
        load = ratio_q(qdepth, max_conc, "verifier_load")
        by_id[vid] = (load, qdepth)
        parsed.append((load, qdepth, vid))

    if pref is not None and pref not in by_id:
        raise MagneticFieldError("UNKNOWN_PREFERRED_VERIFIER", f"unknown preferred_verifier {pref}")

    parsed.sort(key=lambda t: (t[0], t[1], t[2]))
    best_load, _best_q, best_vid = parsed[0]
    worst_q = max(t[1] for t in parsed)
    min_q = min(t[1] for t in parsed)
    starvation_triggered = wait > cap

    if pref is None:
        target = best_vid
        reason = "STARVATION_PREEMPT" if starvation_triggered else "LEAST_LOAD"
    elif starvation_triggered:
        alts = [t for t in parsed if t[2] != pref]
        target = alts[0][2]
        reason = "STARVATION_REROUTE"
    elif by_id[pref][0] <= best_load:
        target = pref
        reason = "PREFERRED_BALANCED"
    else:
        target = best_vid
        reason = "LOAD_REBALANCE"

    return {
        "target": target,
        "reason": reason,
        "starvation_triggered": starvation_triggered,
        "selected_load_q": fmt_q(by_id[target][0]),
        "queue_imbalance": worst_q - min_q,
    }


def compute_field_coupling_dispatch(
    defect_signature: str,
    source_vein: str,
    active_veins: list[str] | tuple[str, ...],
    already_hardened_veins: list[str] | tuple[str, ...] = (),
    *,
    dispatched_veins: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Law-1b omni-directional solenoidal field-coupling dispatcher and conservation verifier."""
    sig = require_str(defect_signature, "defect_signature", min_len=1, max_len=128)
    src = require_str(source_vein, "source_vein", min_len=1, max_len=64)
    act_seq = require_seq(active_veins, "active_veins", min_len=1)
    hard_seq = require_seq(already_hardened_veins, "already_hardened_veins", min_len=0)

    active_set: set[str] = set()
    for v in act_seq:
        vn = require_str(v, "active_vein", min_len=1, max_len=64)
        if vn in active_set:
            raise MagneticFieldError("DUPLICATE_ACTIVE_VEIN", f"duplicate active vein {vn}")
        active_set.add(vn)

    if src not in active_set:
        raise MagneticFieldError("UNKNOWN_SOURCE_VEIN", f"source_vein {src} not in active_veins")

    hardened_set: set[str] = set()
    for v in hard_seq:
        vn = require_str(v, "hardened_vein", min_len=1, max_len=64)
        if vn in hardened_set:
            raise MagneticFieldError("DUPLICATE_HARDENED_VEIN", f"duplicate hardened vein {vn}")
        if vn not in active_set:
            raise MagneticFieldError("UNKNOWN_HARDENED_VEIN", f"hardened vein {vn} not in active_veins")
        hardened_set.add(vn)

    targets = sorted(active_set - hardened_set)
    hardened_sorted = sorted(hardened_set)
    if dispatched_veins is None:
        actual_dispatched = targets
        covered_set = active_set
    else:
        disp_seq = require_seq(dispatched_veins, "dispatched_veins", min_len=0)
        disp_set: set[str] = set()
        for v in disp_seq:
            vn = require_str(v, "dispatched_vein", min_len=1, max_len=64)
            if vn in disp_set:
                raise MagneticFieldError("DUPLICATE_DISPATCHED_VEIN", f"duplicate dispatched vein {vn}")
            if vn not in active_set:
                raise MagneticFieldError("UNKNOWN_DISPATCHED_VEIN", f"dispatched vein {vn} not in active_veins")
            disp_set.add(vn)
        actual_dispatched = sorted(disp_set)
        covered_set = hardened_set | disp_set

    uncovered = sorted(active_set - covered_set)
    coverage_after = ratio_q(len(covered_set), len(active_set), "coverage_after")
    return {
        "defect_signature": sig,
        "source_vein": src,
        "active_vein_count": len(active_set),
        "already_hardened_veins": hardened_sorted,
        "dispatch_target_veins": targets,
        "dispatched_veins": actual_dispatched,
        "uncovered_veins": uncovered,
        "dispatch_count": len(targets),
        "zero_sink_conserved": len(uncovered) == 0,
        "post_coupling_coverage_q": fmt_q(coverage_after),
    }


def evaluate_monitor_cadence(
    monitor_turns: int,
    monitor_board_posts: int,
    pr_poll_tasks: int,
    total_coordinator_tasks: int,
    *,
    max_turns_per_post: int = MAX_POLLING_TURNS_PER_POST,
    max_poll_share_num: int = 1,
    max_poll_share_den: int = 10,
) -> dict[str, Any]:
    """Exact-Q telemetry guard flagging serial polling drags."""
    m_turns = require_int(monitor_turns, "monitor_turns", lo=0)
    m_posts = require_int(monitor_board_posts, "monitor_board_posts", lo=1)
    p_tasks = require_int(pr_poll_tasks, "pr_poll_tasks", lo=0)
    t_tasks = require_int(total_coordinator_tasks, "total_coordinator_tasks", lo=1)
    if p_tasks > t_tasks:
        raise MagneticFieldError("POLL_TASKS_EXCEED_TOTAL", "pr_poll_tasks cannot exceed total_coordinator_tasks")
    tpp_cap = require_int(max_turns_per_post, "max_turns_per_post", lo=1)
    share_cap = ratio_q(
        require_int(max_poll_share_num, "max_poll_share_num", lo=0),
        require_int(max_poll_share_den, "max_poll_share_den", lo=1),
        "poll_share_cap",
    )

    tpp = ratio_q(m_turns, m_posts, "monitor_turns_per_post")
    poll_share = ratio_q(p_tasks, t_tasks, "pr_poll_share")
    flags: list[str] = []
    if tpp > Fraction(tpp_cap, 1):
        flags.append("MONITOR_SERIAL_POLL_DRAG")
    if poll_share > share_cap:
        flags.append("COORDINATOR_PR_POLL_DRAG")

    return {
        "efficient": len(flags) == 0,
        "monitor_turns_per_post_q": fmt_q(tpp),
        "pr_poll_share_q": fmt_q(poll_share),
        "drag_flags": flags,
    }


# ---------------------------------------------------------------------------
# 3. Gate-8 Pre-Registration Timestamp-Order Guard
# ---------------------------------------------------------------------------


def verify_gate8_prereg_order(
    prereg_epoch_s: int,
    observation_epoch_s: int,
    *,
    min_lead_s: int = 1,
) -> dict[str, Any]:
    """Verify Gate-8 pre-registration strictly precedes observation (obs > pre and obs - pre >= max(1, min_lead_s))."""
    pre = require_int(prereg_epoch_s, "prereg_epoch_s", lo=0)
    obs = require_int(observation_epoch_s, "observation_epoch_s", lo=0)
    lead_req = require_int(min_lead_s, "min_lead_s", lo=0)
    lead_s = obs - pre
    effective_min_lead = lead_req if lead_req >= 1 else 1
    strictly_prior = lead_s >= effective_min_lead
    verdict = "PREREGISTERED_PRIOR" if strictly_prior else "POST_HOC_OR_INSUFFICIENT_LEAD"
    return {
        "passed": strictly_prior,
        "verdict": verdict,
        "prereg_epoch_s": pre,
        "observation_epoch_s": obs,
        "lead_s": lead_s,
        "min_lead_s": lead_req,
    }


# ---------------------------------------------------------------------------
# 4. Deterministic Pre-Push, Pre-Review & Workspace Hygiene Gate
# ---------------------------------------------------------------------------


def _hygiene_regexes() -> tuple[tuple[str, re.Pattern[str]], ...]:
    """Assemble hygiene regexes programmatically so static scanners never self-trigger."""
    slash = chr(47)
    bslash = chr(92)
    return (
        ("PERSONAL_UNIX_HOME_PATH", re.compile(slash + "ho" + "me" + slash + r"[A-Za-z0-9._-]+")),
        ("PERSONAL_MAC_USERS_PATH", re.compile(slash + "Us" + "ers" + slash + r"[A-Za-z0-9._-]+")),
        (
            "PERSONAL_WIN_USERS_PATH",
            re.compile(r"[A-Za-z]:" + bslash + bslash + "Us" + "ers" + bslash + bslash + r"[A-Za-z0-9._-]+"),
        ),
        ("CREDENTIAL_GH_PAT", re.compile("gh" + "p_" + r"[A-Za-z0-9]{20,}")),
        ("CREDENTIAL_GH_FINE_PAT", re.compile("github_" + "pat_" + r"[A-Za-z0-9_]{20,}")),
        ("CREDENTIAL_AWS_KEY", re.compile("AK" + "IA" + r"[0-9A-Z]{16}")),
        ("CREDENTIAL_PRIVATE_KEY", re.compile("-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
        ("CO_AUTHORED_BY_TRAILER", re.compile(r"(?im)^Co-" + r"Authored-By:")),
    )


def _is_valid_dco_line(raw_line: str) -> bool:
    """O(n) linear DCO trailer validator (zero catastrophic regex backtracking)."""
    s = raw_line.strip()
    prefix = "Signed-off-by:"
    if not s.startswith(prefix) or not s.endswith(">"):
        return False
    lt_idx = s.rfind("<")
    if lt_idx <= len(prefix):
        return False
    mid = s[len(prefix) : lt_idx]
    if not mid[0].isspace() or not mid[-1].isspace() or len(mid.strip()) == 0:
        return False
    if any(ch in "<>" for ch in mid):
        return False
    email = s[lt_idx + 1 : -1]
    if any(ch.isspace() or ch in "<>" for ch in email):
        return False
    at_parts = email.split("@")
    if len(at_parts) != 2 or len(at_parts[0]) == 0 or "." not in at_parts[1]:
        return False
    return all(len(lbl) > 0 for lbl in at_parts[1].split("."))


def check_dco_signoff(commit_message: str) -> bool:
    """Return True iff commit_message contains a valid `Signed-off-by: Name <email>` trailer line."""
    msg = require_str(commit_message, "commit_message", min_len=1, max_len=65536)
    for line in msg.split("\n"):
        if _is_valid_dco_line(line):
            return True
    return False


def check_repo_visibility(repo_is_private: bool, explicit_private_allowed: bool) -> bool:
    """Fail closed when repository is private unless explicitly authorized."""
    is_priv = require_bool(repo_is_private, "repo_is_private")
    allow_priv = require_bool(explicit_private_allowed, "explicit_private_allowed")
    return not (is_priv and not allow_priv)


def check_graphql_file_completeness(git_changed_files: int, graphql_files_listed: int) -> bool:
    """Detect GitHub GraphQL 100-file cap truncation (`git_changed_files > graphql_files_listed`)."""
    g_files = require_int(git_changed_files, "git_changed_files", lo=0)
    q_files = require_int(graphql_files_listed, "graphql_files_listed", lo=0)
    return g_files <= q_files


def check_openblas_pin(openblas_num_threads: int) -> bool:
    """Enforce `OPENBLAS_NUM_THREADS == 1` to prevent thread-pool deadlocks."""
    threads = require_int(openblas_num_threads, "openblas_num_threads", lo=0)
    return threads == 1


def check_pr_review_action(pr_is_self_authored: bool, review_action: str) -> bool:
    """Block HTTP 422 from APPROVE / REQUEST_CHANGES on self-authored pull requests."""
    self_auth = require_bool(pr_is_self_authored, "pr_is_self_authored")
    action = require_str(review_action, "review_action", min_len=1, max_len=32)
    if action not in _VALID_REVIEW_ACTIONS:
        raise MagneticFieldError("INVALID_REVIEW_ACTION", f"unknown review_action {action}")
    return not (self_auth and action in ("APPROVE", "REQUEST_CHANGES"))


def check_gitignore_receipt_integrity(
    manifest_files: list[str] | tuple[str, ...],
    git_tracked_files: list[str] | tuple[str, ...],
) -> list[str]:
    """Return sorted list of manifest-referenced files missing from git-tracked tree."""
    man_seq = require_seq(manifest_files, "manifest_files", min_len=0)
    trk_seq = require_seq(git_tracked_files, "git_tracked_files", min_len=0)
    man_set = {require_str(p, "manifest_file", min_len=1, max_len=512) for p in man_seq}
    trk_set = {require_str(p, "tracked_file", min_len=1, max_len=512) for p in trk_seq}
    return sorted(man_set - trk_set)


def check_text_hygiene(text: str) -> list[str]:
    """Return sorted unique hygiene violation codes found in staged text."""
    body = require_str(text, "text", min_len=0, max_len=500_000)
    found: set[str] = set()
    if "\r" in body:
        found.add("CR_LINE_ENDINGS_FORBIDDEN")
    for code, rx in _hygiene_regexes():
        if rx.search(body) is not None:
            found.add(code)
    return sorted(found)


_PRE_PUSH_REQUIRED_KEYS = frozenset({
    "commit_message",
    "repo_is_private",
    "explicit_private_allowed",
    "git_changed_files",
    "graphql_files_listed",
    "openblas_num_threads",
    "pr_is_self_authored",
    "review_action",
    "staged_text",
})
_PRE_PUSH_ALLOWED_KEYS = _PRE_PUSH_REQUIRED_KEYS | frozenset({
    "manifest_files",
    "git_tracked_files",
})


def evaluate_pre_push_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Unified fail-closed pre-push & pre-review gate over a strict-key bundle dictionary."""
    m = require_mapping(bundle, "pre_push_bundle")
    keys = set(m.keys())
    unknown_keys = sorted(keys - _PRE_PUSH_ALLOWED_KEYS)
    if unknown_keys:
        raise MagneticFieldError("UNKNOWN_BUNDLE_KEYS", f"unexpected pre_push_bundle keys: {unknown_keys}")
    missing_keys = sorted(_PRE_PUSH_REQUIRED_KEYS - keys)
    if missing_keys:
        raise MagneticFieldError("MISSING_BUNDLE_KEYS", f"missing required pre_push_bundle keys: {missing_keys}")
    violations: list[str] = []

    if not check_dco_signoff(m["commit_message"]):
        violations.append("MISSING_DCO_SIGNOFF")
    if not check_repo_visibility(m["repo_is_private"], m["explicit_private_allowed"]):
        violations.append("PRIVATE_REPO_BLOCKED")
    if not check_graphql_file_completeness(m["git_changed_files"], m["graphql_files_listed"]):
        violations.append("GRAPHQL_100_FILE_TRUNCATION")
    if not check_openblas_pin(m["openblas_num_threads"]):
        violations.append("OPENBLAS_THREADS_UNPINNED")
    if not check_pr_review_action(m["pr_is_self_authored"], m["review_action"]):
        violations.append("SELF_AUTHORED_REVIEW_422")

    dropped = check_gitignore_receipt_integrity(
        m.get("manifest_files", []),  # type: ignore[arg-type]
        m.get("git_tracked_files", []),  # type: ignore[arg-type]
    )
    if len(dropped) > 0:
        violations.append("GITIGNORE_DROPPED_MANIFEST_FILES")

    text_issues = check_text_hygiene(m["staged_text"])
    for issue in text_issues:
        violations.append(issue)

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "dropped_manifest_files": dropped,
    }


def run_self_test() -> dict[str, Any]:
    """Deterministic self-test across Zone-B strict I/O, Law-1b routing, Gate-8 order, and pre-push gates."""
    class _IntSub(int):
        pass

    deep: Any = 0
    for _ in range(1500):
        deep = [deep]
    good_sha = "a" * 64
    io_vectors = (
        ("non_ascii_hmac", lambda: constant_time_hex64_equal("\u00e9" * 64, good_sha)),
        ("surrogate_hmac", lambda: constant_time_hex64_equal(chr(0xD800) * 64, good_sha)),
        ("int_10_pow_5000", lambda: require_int(10**5000, "huge")),
        ("json_5000_digits", lambda: parse_strict_json_text('{"n":' + ("9" * 5000) + "}")),
        ("deep_1500_list", lambda: validate_json_value(deep)),
        ("deep_100_json", lambda: parse_strict_json_text("[" * 100 + "0" + "]" * 100, require_object=False)),
        ("bool_as_int", lambda: require_int(True, "flag")),
        ("int_subclass", lambda: validate_json_value({"n": _IntSub(1)})),
        ("dup_json_key", lambda: parse_strict_json_text('{"a":1,"a":2}')),
        ("float_literal", lambda: parse_strict_json_text('{"x":1.5}')),
        ("surrogate_json", lambda: parse_strict_json_text('{"s":"' + chr(0xD800) + '"}')),
        ("escaped_surrogate_json", lambda: parse_strict_json_text('{"s":"\\ud800"}')),
        ("fmt_q_huge_fraction", lambda: fmt_q(Fraction(10**5000, 1))),
        ("non_str_key", lambda: require_mapping({1: "a"}, "m")),
    )
    io_results: list[dict[str, Any]] = []
    for name, fn in io_vectors:
        try:
            fn()
        except MagneticFieldError as exc:
            io_results.append({"vector": name, "blocked": True, "code": exc.code})
        else:
            io_results.append({"vector": name, "blocked": False, "code": "UNBLOCKED"})
    io_pos = constant_time_hex64_equal(good_sha, good_sha)

    starve_reroute = route_verification_task(
        [
            {"verifier_id": "verifier-a", "queue_depth": 4, "max_concurrent": 1},
            {"verifier_id": "verifier-b", "queue_depth": 0, "max_concurrent": 1},
        ],
        preferred_verifier="verifier-a",
        oldest_wait_s=7091,
    )
    balanced = route_verification_task(
        [
            {"verifier_id": "verifier-a", "queue_depth": 1, "max_concurrent": 1},
            {"verifier_id": "verifier-b", "queue_depth": 2, "max_concurrent": 1},
        ],
        preferred_verifier="verifier-a",
        oldest_wait_s=300,
    )
    coupling = compute_field_coupling_dispatch(
        "DEF-12_non_ascii_hmac_and_int_bit_cap",
        "vein-alpha",
        ["vein-alpha", "vein-beta", "vein-gamma", "vein-delta", "vein-epsilon"],
        ["vein-alpha", "vein-beta"],
        dispatched_veins=["vein-gamma", "vein-delta", "vein-epsilon"],
    )
    coupling_silo = compute_field_coupling_dispatch(
        "DEF-12_non_ascii_hmac_and_int_bit_cap",
        "vein-alpha",
        ["vein-alpha", "vein-beta", "vein-gamma", "vein-delta", "vein-epsilon"],
        ["vein-alpha", "vein-beta"],
        dispatched_veins=["vein-gamma"],
    )
    historical_drag = evaluate_monitor_cadence(1122, 6, 32, 108)
    upgraded_cadence = evaluate_monitor_cadence(60, 6, 4, 108)
    gate8_ok = verify_gate8_prereg_order(1_700_000_000, 1_700_000_480, min_lead_s=60)
    gate8_post_hoc = verify_gate8_prereg_order(1_700_000_500, 1_700_000_480, min_lead_s=0)

    clean_bundle = evaluate_pre_push_bundle({
        "commit_message": "study: add verified exact audit\n\nSigned-off-by: Author <author@example.org>\n",
        "repo_is_private": False,
        "explicit_private_allowed": False,
        "git_changed_files": 5,
        "graphql_files_listed": 5,
        "openblas_num_threads": 1,
        "pr_is_self_authored": False,
        "review_action": "APPROVE",
        "manifest_files": ["SHA256SUMS", "receipts.jsonl"],
        "git_tracked_files": ["SHA256SUMS", "receipts.jsonl"],
        "staged_text": "Clean public PR body with exact SHA-256 receipts.\n",
    })
    dirty_text = "Leaked " + chr(47) + "ho" + "me" + chr(47) + "user/work\r\n"
    dirty_bundle = evaluate_pre_push_bundle({
        "commit_message": "fix: forgot DCO trailer",
        "repo_is_private": True,
        "explicit_private_allowed": False,
        "git_changed_files": 463,
        "graphql_files_listed": 100,
        "openblas_num_threads": 16,
        "pr_is_self_authored": True,
        "review_action": "REQUEST_CHANGES",
        "manifest_files": ["receipts.jsonl", "run.log"],
        "git_tracked_files": ["README.md"],
        "staged_text": dirty_text,
    })

    checks = (
        all(r["blocked"] for r in io_results),
        io_pos,
        starve_reroute["target"] == "verifier-b",
        starve_reroute["starvation_triggered"],
        balanced["target"] == "verifier-a",
        coupling["dispatch_count"] == 3,
        coupling["zero_sink_conserved"],
        not coupling_silo["zero_sink_conserved"],
        coupling_silo["uncovered_veins"] == ["vein-delta", "vein-epsilon"],
        not historical_drag["efficient"],
        upgraded_cadence["efficient"],
        gate8_ok["passed"],
        not gate8_post_hoc["passed"],
        clean_bundle["passed"],
        not dirty_bundle["passed"],
        len(dirty_bundle["violations"]) == 8,
    )
    body = {
        "module": "aletheia.magnetic_field_v21",
        "version": "2.1.0-draft",
        "strict_io": {
            "vectors_blocked": sum(1 for r in io_results if r["blocked"]),
            "vectors_total": len(io_results),
            "positive_control_ok": io_pos,
            "results": io_results,
        },
        "routing": {
            "starvation_reroute": starve_reroute,
            "balanced_route": balanced,
            "omni_vein_coupling": coupling,
            "omni_vein_silo_detected": coupling_silo,
            "historical_drag": historical_drag,
            "upgraded_cadence": upgraded_cadence,
        },
        "gate8_prereg": {
            "prior_ok": gate8_ok,
            "post_hoc_blocked": gate8_post_hoc,
        },
        "pre_push_gate": {
            "clean_passed": clean_bundle["passed"],
            "dirty_passed": dirty_bundle["passed"],
            "dirty_violation_count": len(dirty_bundle["violations"]),
            "dirty_violations": dirty_bundle["violations"],
            "dirty_dropped_files": dirty_bundle["dropped_manifest_files"],
        },
        "all_passed": all(checks),
    }
    body["sha256"] = canonical_sha256(body)
    return body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aletheia v2.1 — Zone-B Strict I/O, Law-1b Field-Coupling Router, Gate-8 Order & Pre-Push Gate"
    )
    parser.add_argument("--self-test", action="store_true", help="Run built-in v2.1 self-test")
    parser.add_argument("--json", action="store_true", help="Emit canonical JSON output")
    parser.add_argument("--check-bundle", type=str, help="Validate a pre-push JSON bundle file fail-closed")
    args = parser.parse_args(argv)
    try:
        if args.check_bundle is not None:
            bundle = load_strict_json_file(Path(args.check_bundle), require_object=True)
            res = evaluate_pre_push_bundle(bundle)
            if args.json:
                sys.stdout.write(canonical_json_bytes(res).decode("ascii") + "\n")
            else:
                status = "PASS" if res["passed"] else "FAIL"
                print(f"{status} magnetic_field_v21 violations={len(res['violations'])}")
            return 0 if res["passed"] else 2
        res = run_self_test()
        if args.json:
            sys.stdout.write(canonical_json_bytes(res).decode("ascii") + "\n")
        else:
            status = "OK" if res["all_passed"] else "FAIL"
            print(
                f"{status} magnetic_field_v21 all_passed={res['all_passed']} "
                f"io_blocked={res['strict_io']['vectors_blocked']}/{res['strict_io']['vectors_total']} "
                f"sha256={res['sha256']}"
            )
        return 0 if res["all_passed"] else 2
    except (MagneticFieldError, OSError) as exc:
        print(f"REJECT {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
