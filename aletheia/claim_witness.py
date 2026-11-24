#!/usr/bin/env python3
"""
`aletheia.claim_witness`: Executable 3-Pillar Claim-to-Witness Binding Operator (`P_CTW`).

Pure Python 3 stdlib, exact Z/Q arithmetic only (`0` floats on trust paths, `0` bare asserts,
full Zone-B strict I/O hardening).

Closes the claim-to-witness semantic boundary across three orthogonal executable pillars:
  1. Quantitative Prose-to-Artifact Binding (slot-packing bpw, integer ranges, C hot tables, prose invariants)
  2. Operator, Spec & Attribution Provenance Typing (surrogates, cross-experiment attribution, spec completeness, delivery scope)
  3. Semantic Destruction Sensitivity Gate (Law 2b anti-hollow witness verification)

Usage:
  python3 -I -B aletheia/claim_witness.py --self-test --json
  python3 -I -B aletheia/claim_witness.py --check <certificate.json> [--json]
"""
from __future__ import annotations

import argparse
import copy
import errno
from fractions import Fraction
import hashlib
import hmac
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any, Callable

MAX_JSON_DEPTH = 64
MAX_JSON_BYTES = 2_000_000
_READ_CHUNK_BYTES = 65_536
MAX_INT_BITS = 2048
MAX_INT_DIGITS = 620

SCHEMA_VERSION = "aletheia.claim_witness.v1"
COMPONENT_ID = "aletheia-v21-claim-witness"
REQUIRED_CERT_KEYS = frozenset((
    "schema_version",
    "component_id",
    "oracle_class",
    "novelty_tier",
    "payload",
    "payload_sha256",
    "certificate_sha256",
))

_EXACT_PATH_TYPES = (Path, type(Path()))
_ASCII_DIGITS = frozenset("0123456789")
_HEX64_CHARS = frozenset("0123456789abcdef")
_OPERATOR_PROVENANCE = frozenset(("exact_operator", "surrogate_operator"))
_METRIC_PROVENANCE = frozenset((
    "same_experiment_measurement",
    "cross_experiment_anchor",
    "unmeasured_hypothesis",
))
_SCOPE_TIERS: dict[str, int] = {
    "research_prototype": 1,
    "ctypes_benchmark_harness": 2,
    "packed_file_integration": 3,
    "production_deployment": 4,
}


class ClaimWitnessError(ValueError):
    """Fail-closed error carrying a stable machine-readable error code."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        self.message = detail
        super().__init__(f"{code}: {detail}")


def _require_valid_utf8_str(val: Any, field: str) -> str:
    if type(val) is not str:
        raise ClaimWitnessError("INVALID_STR_TYPE", f"{field} must be exact str")
    try:
        val.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ClaimWitnessError("INVALID_UTF8_SURROGATE", f"{field} contains unpaired surrogate") from exc
    return val


def require_str(val: Any, field: str, *, non_empty: bool = False) -> str:
    s = _require_valid_utf8_str(val, field)
    if non_empty and len(s) == 0:
        raise ClaimWitnessError("EMPTY_STR", f"{field} must be non-empty")
    return s


def require_bool(val: Any, field: str) -> bool:
    if type(val) is not bool:
        raise ClaimWitnessError("INVALID_BOOL_TYPE", f"{field} must be exact bool")
    return val


def require_int(
    val: Any,
    field: str,
    *,
    min_value: int | None = None,
    max_value: int | None = None,
    max_bits: int = MAX_INT_BITS,
) -> int:
    if type(val) is not int:
        raise ClaimWitnessError("INVALID_INT_TYPE", f"{field} must be exact int")
    if type(max_bits) is not int or max_bits < 1:
        raise ClaimWitnessError("INVALID_BOUND_TYPE", f"{field} max_bits must be positive exact int")
    bits = val.bit_length()
    if bits > max_bits:
        raise ClaimWitnessError(
            "INT_BIT_LIMIT_EXCEEDED",
            f"{field} has {bits} bits, exceeding limit {max_bits}",
        )
    if min_value is not None:
        if type(min_value) is not int:
            raise ClaimWitnessError("INVALID_BOUND_TYPE", f"{field} min_value must be exact int")
        if val < min_value:
            raise ClaimWitnessError("INT_BELOW_MIN", f"{field} below minimum bound")
    if max_value is not None:
        if type(max_value) is not int:
            raise ClaimWitnessError("INVALID_BOUND_TYPE", f"{field} max_value must be exact int")
        if val > max_value:
            raise ClaimWitnessError("INT_ABOVE_MAX", f"{field} above maximum bound")
    return val


def _parse_bounded_int_str(token: str, field: str) -> int:
    s = _require_valid_utf8_str(token, field)
    if len(s) == 0:
        raise ClaimWitnessError("INVALID_INT_LITERAL", f"{field} empty integer literal")
    digits = s[1:] if s[0] == "-" else s
    if len(digits) == 0 or any(ch not in _ASCII_DIGITS for ch in digits):
        raise ClaimWitnessError("INVALID_INT_LITERAL", f"{field} invalid ASCII integer literal")
    if len(digits) > MAX_INT_DIGITS:
        raise ClaimWitnessError(
            "INT_DIGIT_LIMIT_EXCEEDED",
            f"{field} has {len(digits)} digits, exceeding limit {MAX_INT_DIGITS}",
        )
    return require_int(int(s), field)


def require_exact_fraction(val: Any, field: str) -> Fraction:
    if type(val) is int:
        return Fraction(require_int(val, field), 1)
    if type(val) is Fraction:
        num = require_int(val.numerator, f"{field}.numerator")
        den = require_int(val.denominator, f"{field}.denominator", min_value=1)
        return Fraction(num, den)
    if type(val) is str:
        s = _require_valid_utf8_str(val, field)
        parts = s.split("/")
        if len(parts) == 1:
            return Fraction(_parse_bounded_int_str(parts[0], field), 1)
        if len(parts) == 2:
            num = _parse_bounded_int_str(parts[0], f"{field}.numerator")
            den = _parse_bounded_int_str(parts[1], f"{field}.denominator")
            if den <= 0:
                raise ClaimWitnessError("NON_POSITIVE_DENOMINATOR", f"{field} denominator must be > 0")
            return Fraction(num, den)
        raise ClaimWitnessError("INVALID_FRACTION_STR", f"{field} invalid rational format")
    raise ClaimWitnessError("INVALID_FRACTION_TYPE", f"{field} must be int, Fraction, or rational str")


def fmt_q(val: Fraction) -> str:
    q = require_exact_fraction(val, "rational")
    if q.denominator == 1:
        return str(q.numerator)
    return f"{q.numerator}/{q.denominator}"


def require_hex64_ascii(val: Any, field: str) -> str:
    s = _require_valid_utf8_str(val, field)
    if len(s) != 64:
        raise ClaimWitnessError("INVALID_HEX64_LEN", f"{field} must be exactly 64 hex chars")
    for ch in s:
        if ch not in _HEX64_CHARS:
            raise ClaimWitnessError("INVALID_HEX64_CHAR", f"{field} must be lowercase ASCII hex")
    return s


def constant_time_hex64_equal(left: Any, right: Any, field: str = "digest") -> bool:
    a = require_hex64_ascii(left, f"{field}.left")
    b = require_hex64_ascii(right, f"{field}.right")
    return hmac.compare_digest(a.encode("ascii"), b.encode("ascii"))


def require_exact_dict(val: Any, field: str) -> dict[str, Any]:
    if type(val) is not dict:
        raise ClaimWitnessError("INVALID_DICT_TYPE", f"{field} must be exact dict")
    for k in val:
        _require_valid_utf8_str(k, f"{field}.key")
    return val


def require_exact_list(val: Any, field: str, *, non_empty: bool = False) -> list[Any]:
    if type(val) is not list:
        raise ClaimWitnessError("INVALID_LIST_TYPE", f"{field} must be exact list")
    if non_empty and len(val) == 0:
        raise ClaimWitnessError("EMPTY_LIST", f"{field} must be non-empty")
    return val


def validate_json_value(obj: Any, *, max_depth: int = MAX_JSON_DEPTH) -> None:
    """Iteratively validate exact JSON-compatible tree (zero floats, bounded depth/ints, valid UTF-8)."""
    depth_limit = require_int(max_depth, "max_depth", min_value=1, max_value=MAX_JSON_DEPTH)
    stack: list[tuple[Any, int]] = [(obj, 0)]
    while stack:
        cur, depth = stack.pop()
        if depth > depth_limit:
            raise ClaimWitnessError("JSON_DEPTH_EXCEEDED", f"nesting exceeds depth {depth_limit}")
        t = type(cur)
        if cur is None or t is bool:
            continue
        if t is int:
            require_int(cur, "json.int")
            continue
        if t is str:
            _require_valid_utf8_str(cur, "json.str")
            continue
        if t is list:
            for item in cur:
                stack.append((item, depth + 1))
            continue
        if t is dict:
            for k, v in cur.items():
                _require_valid_utf8_str(k, "json.key")
                stack.append((v, depth + 1))
            continue
        raise ClaimWitnessError("UNSUPPORTED_JSON_TYPE", f"unsupported type {t.__name__}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        _require_valid_utf8_str(k, "json.key")
        if k in out:
            raise ClaimWitnessError("JSON_DUPLICATE_KEY", f"duplicate JSON key: {k}")
        out[k] = v
    return out


def _reject_float_literal(raw: str) -> Any:
    raise ClaimWitnessError("JSON_FLOAT_FORBIDDEN", f"float literal forbidden: {raw}")


def _reject_constant_literal(raw: str) -> Any:
    raise ClaimWitnessError("JSON_CONSTANT_FORBIDDEN", f"non-standard JSON constant forbidden: {raw}")


def _bounded_json_int(raw: str) -> int:
    return _parse_bounded_int_str(raw, "json.int")


def parse_strict_json_text(
    raw_text: str,
    *,
    require_object: bool = True,
    max_depth: int = MAX_JSON_DEPTH,
    max_bytes: int = MAX_JSON_BYTES,
) -> Any:
    require_bool(require_object, "require_object")
    text = _require_valid_utf8_str(raw_text, "raw_text")
    byte_limit = require_int(max_bytes, "max_bytes", min_value=1, max_value=MAX_JSON_BYTES)
    if len(text.encode("utf-8")) > byte_limit:
        raise ClaimWitnessError("JSON_TOO_LARGE", f"JSON text exceeds {byte_limit} bytes")
    try:
        obj = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=_reject_float_literal,
            parse_int=_bounded_json_int,
            parse_constant=_reject_constant_literal,
        )
    except ClaimWitnessError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise ClaimWitnessError("JSON_SYNTAX_ERROR", str(exc)) from exc
    validate_json_value(obj, max_depth=max_depth)
    if require_object and type(obj) is not dict:
        raise ClaimWitnessError("JSON_ROOT_NOT_OBJECT", "top-level JSON payload must be an object")
    return obj


def canonical_json_bytes(obj: Any) -> bytes:
    validate_json_value(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def canonical_sha256(obj: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


def _validate_path_obj(path: Any) -> str:
    if type(path) not in _EXACT_PATH_TYPES:
        raise ClaimWitnessError("INVALID_PATH_TYPE", "path must be concrete pathlib.Path")
    raw_s = _require_valid_utf8_str(str(path), "path")
    if "\x00" in raw_s:
        raise ClaimWitnessError("INVALID_PATH_NUL", "NUL byte forbidden in path")
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
                    raise ClaimWitnessError("SYMLINK_ANCESTOR_FORBIDDEN", "symlink ancestor in PWD") from exc
                return
            os.close(cur_fd)
            cur_fd = nxt
    finally:
        os.close(cur_fd)


def require_no_symlink_path(path: Path) -> None:
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
                    raise ClaimWitnessError("SYMLINK_ANCESTOR_FORBIDDEN", "symlink ancestor forbidden") from exc
                return
            os.close(cur_fd)
            cur_fd = nxt
        if _is_symlink_at(cur_fd, leaf):
            raise ClaimWitnessError("SYMLINK_FORBIDDEN", "symlink target path forbidden")
    finally:
        os.close(cur_fd)


def _open_parent_dir_fd(path: Path) -> tuple[int, str]:
    _validate_path_obj(path)
    is_abs = path.is_absolute()
    if not is_abs:
        _check_pwd_no_symlinks()
    parts = path.parts[1:] if is_abs else path.parts
    if len(parts) == 0 or parts[-1] == "..":
        raise ClaimWitnessError("FILE_NOT_FOUND", "path must name a regular file")
    ancestors, leaf = parts[:-1], parts[-1]
    cur_fd = os.open("/" if is_abs else ".", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in ancestors:
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if _is_symlink_at(cur_fd, comp):
                    raise ClaimWitnessError("SYMLINK_ANCESTOR_FORBIDDEN", "symlink ancestor forbidden") from exc
                if exc.errno in (errno.ENOENT, errno.ENOTDIR):
                    raise ClaimWitnessError("FILE_NOT_FOUND", "ancestor directory not found") from exc
                raise ClaimWitnessError("FILE_READ_ERROR", f"cannot open ancestor: {exc}") from exc
            os.close(cur_fd)
            cur_fd = nxt
        return cur_fd, leaf
    except BaseException:
        os.close(cur_fd)
        raise


def read_strict_utf8_file(path: Path, *, max_bytes: int = MAX_JSON_BYTES) -> tuple[bytes, str]:
    byte_limit = require_int(max_bytes, "max_bytes", min_value=1, max_value=MAX_JSON_BYTES)
    dfd, leaf = _open_parent_dir_fd(path)
    try:
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise ClaimWitnessError("SYMLINK_FORBIDDEN", "symlink target path forbidden") from exc
            if exc.errno in (errno.ENOENT, errno.ENOTDIR, errno.EISDIR):
                raise ClaimWitnessError("FILE_NOT_FOUND", "regular file not found") from exc
            raise ClaimWitnessError("FILE_READ_ERROR", f"cannot open file: {exc}") from exc
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                raise ClaimWitnessError("FILE_NOT_FOUND", "regular file not found")
            chunks: list[bytes] = []
            total = 0
            while True:
                try:
                    chunk = os.read(fd, _READ_CHUNK_BYTES)
                except OSError as exc:
                    raise ClaimWitnessError("FILE_READ_ERROR", f"cannot read file: {exc}") from exc
                if not chunk:
                    break
                total += len(chunk)
                if total > byte_limit:
                    raise ClaimWitnessError("FILE_TOO_LARGE", f"file exceeds {byte_limit} bytes")
                chunks.append(chunk)
            raw = b"".join(chunks)
        finally:
            os.close(fd)
    finally:
        os.close(dfd)
    if b"\r" in raw:
        raise ClaimWitnessError("CR_LINE_ENDINGS_FORBIDDEN", "CR/CRLF line endings forbidden")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ClaimWitnessError("INVALID_UTF8", f"invalid UTF-8: {exc}") from exc
    return raw, text


# ---------------------------------------------------------------------------
# Pillar 1: Quantitative Prose-to-Artifact Binding
# ---------------------------------------------------------------------------


def _check_slot_packing_bpw(rec: dict[str, Any]) -> dict[str, Any]:
    bid = require_str(rec.get("id"), "binding.id", non_empty=True)
    n_values = require_int(rec.get("n_values"), "n_values", min_value=1)
    kept_values = require_int(rec.get("kept_values"), "kept_values", min_value=0, max_value=n_values)
    kept_bits = require_int(rec.get("kept_bits_per_val"), "kept_bits_per_val", min_value=1)
    block_size = require_int(rec.get("rest_block_size"), "rest_block_size", min_value=1)
    block_bits = require_int(rec.get("rest_bits_per_block"), "rest_bits_per_block", min_value=1)
    group_size = require_int(rec.get("scale_group_size"), "scale_group_size", min_value=1)
    scale_bits = require_int(rec.get("scale_bits_per_slot"), "scale_bits_per_slot", min_value=0)
    extra_bits = require_int(rec.get("extra_header_bits", 0), "extra_header_bits", min_value=0)
    claimed_bpw = require_exact_fraction(rec.get("claimed_bpw"), "claimed_bpw")

    rest_values = n_values - kept_values
    if rest_values % block_size != 0:
        raise ClaimWitnessError("NON_DIVISIBLE_REST_BLOCK", "rest_values must be divisible by rest_block_size")
    rest_blocks = rest_values // block_size
    scale_slots = (n_values + group_size - 1) // group_size
    actual_bits = (
        kept_values * kept_bits
        + rest_blocks * block_bits
        + scale_slots * scale_bits
        + extra_bits
    )
    actual_bpw = Fraction(actual_bits, n_values)
    delta = claimed_bpw - actual_bpw
    passed = claimed_bpw == actual_bpw
    reasons = [] if passed else ["PROSE_BPW_ARITHMETIC_MISMATCH"]
    return {
        "id": bid,
        "kind": "slot_packing_bpw",
        "passed": passed,
        "reasons": reasons,
        "claimed_bpw": fmt_q(claimed_bpw),
        "actual_bpw": fmt_q(actual_bpw),
        "delta_bpw": fmt_q(delta),
        "allocated_scale_slots": scale_slots,
    }


def _check_integer_range_binding(rec: dict[str, Any]) -> dict[str, Any]:
    bid = require_str(rec.get("id"), "binding.id", non_empty=True)
    c_cnt = require_int(rec.get("claimed_count"), "claimed_count", min_value=1)
    c_min = require_int(rec.get("claimed_min"), "claimed_min")
    c_max = require_int(rec.get("claimed_max"), "claimed_max", min_value=c_min)
    a_cnt = require_int(rec.get("artifact_count"), "artifact_count", min_value=1)
    a_min = require_int(rec.get("artifact_min"), "artifact_min")
    a_max = require_int(rec.get("artifact_max"), "artifact_max", min_value=a_min)

    reasons: list[str] = []
    if c_cnt != a_cnt:
        reasons.append("PROSE_COUNT_MISMATCH")
    if c_min != a_min or c_max != a_max:
        reasons.append("PROSE_RANGE_MISMATCH")
    return {
        "id": bid,
        "kind": "integer_range_binding",
        "passed": len(reasons) == 0,
        "reasons": reasons,
        "claimed": [c_cnt, c_min, c_max],
        "artifact": [a_cnt, a_min, a_max],
    }


def _check_c_allocation_table(rec: dict[str, Any]) -> dict[str, Any]:
    bid = require_str(rec.get("id"), "binding.id", non_empty=True)
    claimed_hot = require_int(rec.get("claimed_hot_bytes"), "claimed_hot_bytes", min_value=0)
    arrays = require_exact_list(rec.get("allocated_arrays"), "allocated_arrays", non_empty=True)

    actual_hot = 0
    actual_total = 0
    seen_names: set[str] = set()
    for idx, entry in enumerate(arrays):
        item = require_exact_dict(entry, f"allocated_arrays[{idx}]")
        name = require_str(item.get("name"), f"allocated_arrays[{idx}].name", non_empty=True)
        if name in seen_names:
            raise ClaimWitnessError("DUPLICATE_ARRAY_NAME", f"duplicate array {name}")
        seen_names.add(name)
        nbytes = require_int(item.get("bytes"), f"allocated_arrays[{idx}].bytes", min_value=1)
        is_hot = require_bool(item.get("hot_read"), f"allocated_arrays[{idx}].hot_read")
        actual_total += nbytes
        if is_hot:
            actual_hot += nbytes

    reasons: list[str] = []
    if claimed_hot != actual_hot:
        reasons.append("C_HOT_FOOTPRINT_MISMATCH")

    cache_fit_checked = False
    actual_fits_cache: bool | None = None
    if "claimed_cache_limit_bytes" in rec or "claimed_fits_cache" in rec:
        limit = require_int(rec.get("claimed_cache_limit_bytes"), "claimed_cache_limit_bytes", min_value=1)
        claimed_fits = require_bool(rec.get("claimed_fits_cache"), "claimed_fits_cache")
        cache_fit_checked = True
        actual_fits_cache = actual_hot <= limit
        if claimed_fits != actual_fits_cache:
            reasons.append("CACHE_FIT_CLAIM_MISMATCH")

    return {
        "id": bid,
        "kind": "c_allocation_table",
        "passed": len(reasons) == 0,
        "reasons": reasons,
        "claimed_hot_bytes": claimed_hot,
        "actual_hot_bytes": actual_hot,
        "actual_total_bytes": actual_total,
        "omitted_hot_bytes": actual_hot - claimed_hot,
        "cache_fit_checked": cache_fit_checked,
        "actual_fits_cache": actual_fits_cache,
    }


def _check_prose_invariant_binding(rec: dict[str, Any]) -> dict[str, Any]:
    bid = require_str(rec.get("id"), "binding.id", non_empty=True)
    rule = require_str(rec.get("rule"), "rule", non_empty=True)
    if rule != "min_non_whitespace_chars":
        raise ClaimWitnessError("UNKNOWN_INVARIANT_RULE", f"unsupported rule: {rule}")
    threshold = require_int(rec.get("threshold"), "threshold", min_value=1)
    sample = require_str(rec.get("sample_input"), "sample_input")
    code_admitted = require_bool(rec.get("code_admitted"), "code_admitted")

    non_ws = sum(1 for ch in sample if not ch.isspace())
    prose_admits = non_ws >= threshold
    passed = code_admitted == prose_admits
    reasons = [] if passed else ["PROSE_INVARIANT_MISMATCH"]
    return {
        "id": bid,
        "kind": "prose_invariant_binding",
        "passed": passed,
        "reasons": reasons,
        "non_whitespace_chars": non_ws,
        "prose_admits": prose_admits,
        "code_admitted": code_admitted,
    }


def verify_prose_artifact_bindings(bindings: list[dict[str, Any]]) -> dict[str, Any]:
    """Pillar 1: Verify exact quantitative bindings between prose claims and code/cert artifacts."""
    items = require_exact_list(bindings, "bindings", non_empty=True)
    results: list[dict[str, Any]] = []
    for idx, raw in enumerate(items):
        rec = require_exact_dict(raw, f"bindings[{idx}]")
        kind = require_str(rec.get("kind"), f"bindings[{idx}].kind", non_empty=True)
        if kind == "slot_packing_bpw":
            results.append(_check_slot_packing_bpw(rec))
        elif kind == "integer_range_binding":
            results.append(_check_integer_range_binding(rec))
        elif kind == "c_allocation_table":
            results.append(_check_c_allocation_table(rec))
        elif kind == "prose_invariant_binding":
            results.append(_check_prose_invariant_binding(rec))
        else:
            raise ClaimWitnessError("UNKNOWN_BINDING_KIND", f"unknown binding kind: {kind}")
    failed_ids = [r["id"] for r in results if not r["passed"]]
    return {
        "pillar": "pillar1_prose_artifact_binding",
        "passed": len(failed_ids) == 0,
        "checked_count": len(results),
        "failed_count": len(failed_ids),
        "failed_ids": failed_ids,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Pillar 2: Operator, Spec & Attribution Provenance Typing
# ---------------------------------------------------------------------------


def _check_operator_equivalence(rec: dict[str, Any]) -> dict[str, Any]:
    cid = require_str(rec.get("id"), "claim.id", non_empty=True)
    c_op = require_str(rec.get("claimed_operator"), "claimed_operator", non_empty=True)
    c_prov = require_str(rec.get("claimed_provenance"), "claimed_provenance", non_empty=True)
    w_op = require_str(rec.get("witness_operator"), "witness_operator", non_empty=True)
    w_prov = require_str(rec.get("witness_provenance"), "witness_provenance", non_empty=True)
    if c_prov not in _OPERATOR_PROVENANCE:
        raise ClaimWitnessError("UNKNOWN_OPERATOR_PROVENANCE", f"invalid claimed_provenance: {c_prov}")
    if w_prov not in _OPERATOR_PROVENANCE:
        raise ClaimWitnessError("UNKNOWN_OPERATOR_PROVENANCE", f"invalid witness_provenance: {w_prov}")
    claims_grad = require_bool(rec.get("claims_gradient_coverage"), "claims_gradient_coverage")
    witness_grad = require_bool(rec.get("witness_has_gradient_coverage"), "witness_has_gradient_coverage")
    claims_causal = require_bool(rec.get("claims_causal_impossibility"), "claims_causal_impossibility")
    dist_only = require_bool(
        rec.get("witness_proves_only_distributional_symmetry"),
        "witness_proves_only_distributional_symmetry",
    )

    reasons: list[str] = []
    if c_prov == "exact_operator" and w_prov != "exact_operator":
        reasons.append("SURROGATE_OVERCLAIMED_AS_EXACT")
    if c_op != w_op:
        reasons.append("OPERATOR_IDENTITY_MISMATCH")
    if claims_grad and not witness_grad:
        reasons.append("UNVERIFIED_GRADIENT_COVERAGE")
    if claims_causal and dist_only:
        reasons.append("DISTRIBUTIONAL_OVERCLAIMED_AS_CAUSAL")
    return {
        "id": cid,
        "kind": "operator_equivalence",
        "passed": len(reasons) == 0,
        "reasons": reasons,
    }


def _check_metric_attribution(rec: dict[str, Any]) -> dict[str, Any]:
    cid = require_str(rec.get("id"), "claim.id", non_empty=True)
    c_subj = require_str(rec.get("claimed_subject"), "claimed_subject", non_empty=True)
    m_subj = require_str(rec.get("measured_subject"), "measured_subject", non_empty=True)
    c_prov = require_str(rec.get("claimed_provenance"), "claimed_provenance", non_empty=True)
    w_prov = require_str(rec.get("witness_provenance"), "witness_provenance", non_empty=True)
    if c_prov not in _METRIC_PROVENANCE:
        raise ClaimWitnessError("UNKNOWN_METRIC_PROVENANCE", f"invalid claimed_provenance: {c_prov}")
    if w_prov not in _METRIC_PROVENANCE:
        raise ClaimWitnessError("UNKNOWN_METRIC_PROVENANCE", f"invalid witness_provenance: {w_prov}")
    executed = require_bool(
        rec.get("experiment_executed_for_claimed_subject"),
        "experiment_executed_for_claimed_subject",
    )

    reasons: list[str] = []
    if c_prov == "same_experiment_measurement":
        if w_prov != "same_experiment_measurement" or c_subj != m_subj or not executed:
            reasons.append("CROSS_EXPERIMENT_ATTRIBUTION_SMUGGLING")
    if c_prov == "cross_experiment_anchor" and w_prov == "unmeasured_hypothesis":
        reasons.append("UNMEASURED_HYPOTHESIS_OVERCLAIM")
    return {
        "id": cid,
        "kind": "metric_attribution",
        "passed": len(reasons) == 0,
        "reasons": reasons,
    }


def _check_spec_completeness(rec: dict[str, Any]) -> dict[str, Any]:
    cid = require_str(rec.get("id"), "claim.id", non_empty=True)
    req_raw = require_exact_list(rec.get("required_clauses"), "required_clauses", non_empty=True)
    imp_raw = require_exact_list(rec.get("implemented_clauses"), "implemented_clauses")
    claims_exact = require_bool(rec.get("claimed_exact_spec_equivalence"), "claimed_exact_spec_equivalence")

    required: set[str] = set()
    for idx, item in enumerate(req_raw):
        clause = require_str(item, f"required_clauses[{idx}]", non_empty=True)
        if clause in required:
            raise ClaimWitnessError("DUPLICATE_SPEC_CLAUSE", f"duplicate required clause: {clause}")
        required.add(clause)

    implemented: set[str] = set()
    for idx, item in enumerate(imp_raw):
        clause = require_str(item, f"implemented_clauses[{idx}]", non_empty=True)
        implemented.add(clause)

    missing = sorted(required - implemented)
    reasons: list[str] = []
    if claims_exact and len(missing) > 0:
        reasons.append("INCOMPLETE_SPEC_EQUIVALENCE")
    return {
        "id": cid,
        "kind": "spec_completeness",
        "passed": len(reasons) == 0,
        "reasons": reasons,
        "missing_clauses": missing,
    }


def _check_delivery_scope(rec: dict[str, Any]) -> dict[str, Any]:
    cid = require_str(rec.get("id"), "claim.id", non_empty=True)
    c_scope = require_str(rec.get("claimed_scope_tier"), "claimed_scope_tier", non_empty=True)
    w_scope = require_str(rec.get("witnessed_scope_tier"), "witnessed_scope_tier", non_empty=True)
    if c_scope not in _SCOPE_TIERS:
        raise ClaimWitnessError("UNKNOWN_SCOPE_TIER", f"unknown claimed_scope_tier: {c_scope}")
    if w_scope not in _SCOPE_TIERS:
        raise ClaimWitnessError("UNKNOWN_SCOPE_TIER", f"unknown witnessed_scope_tier: {w_scope}")

    passed = _SCOPE_TIERS[c_scope] <= _SCOPE_TIERS[w_scope]
    reasons = [] if passed else ["DELIVERY_SCOPE_OVERCLAIM"]
    return {
        "id": cid,
        "kind": "delivery_scope",
        "passed": passed,
        "reasons": reasons,
        "claimed_rank": _SCOPE_TIERS[c_scope],
        "witnessed_rank": _SCOPE_TIERS[w_scope],
    }


def verify_provenance_claims(claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Pillar 2: Enforce strict provenance typing for operators, metrics, specs, and delivery scope."""
    items = require_exact_list(claims, "claims", non_empty=True)
    results: list[dict[str, Any]] = []
    for idx, raw in enumerate(items):
        rec = require_exact_dict(raw, f"claims[{idx}]")
        kind = require_str(rec.get("kind"), f"claims[{idx}].kind", non_empty=True)
        if kind == "operator_equivalence":
            results.append(_check_operator_equivalence(rec))
        elif kind == "metric_attribution":
            results.append(_check_metric_attribution(rec))
        elif kind == "spec_completeness":
            results.append(_check_spec_completeness(rec))
        elif kind == "delivery_scope":
            results.append(_check_delivery_scope(rec))
        else:
            raise ClaimWitnessError("UNKNOWN_PROVENANCE_KIND", f"unknown provenance kind: {kind}")
    failed_ids = [r["id"] for r in results if not r["passed"]]
    return {
        "pillar": "pillar2_provenance_typing",
        "passed": len(failed_ids) == 0,
        "checked_count": len(results),
        "failed_count": len(failed_ids),
        "failed_ids": failed_ids,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Pillar 3: Semantic Destruction Sensitivity Gate (Law 2b Anti-Hollow Witness)
# ---------------------------------------------------------------------------


def _resolve_parent_dict(root: dict[str, Any], path: list[str]) -> tuple[dict[str, Any], str]:
    cur: Any = root
    for seg in path[:-1]:
        if type(cur) is not dict or seg not in cur:
            raise ClaimWitnessError("DESTRUCTION_PATH_MISSING", f"missing path segment: {seg}")
        cur = cur[seg]
    if type(cur) is not dict:
        raise ClaimWitnessError("DESTRUCTION_PARENT_NOT_DICT", "target parent must be a dict")
    leaf = path[-1]
    if leaf not in cur:
        raise ClaimWitnessError("DESTRUCTION_LEAF_MISSING", f"missing leaf key: {leaf}")
    return cur, leaf


def _apply_semantic_destruction(
    witness: dict[str, Any],
    spec: dict[str, Any],
) -> dict[str, Any]:
    mutated = copy.deepcopy(witness)
    op = require_str(spec.get("op"), "perturbation.op", non_empty=True)
    raw_path = require_exact_list(spec.get("path"), "perturbation.path", non_empty=True)
    path = [require_str(seg, f"perturbation.path[{i}]", non_empty=True) for i, seg in enumerate(raw_path)]
    parent, leaf = _resolve_parent_dict(mutated, path)

    if op == "empty_mapping_field":
        if type(parent[leaf]) is not dict or len(parent[leaf]) == 0:
            raise ClaimWitnessError("TARGET_NOT_NONEMPTY_DICT", "empty_mapping_field requires non-empty dict")
        parent[leaf] = {}
    elif op == "replace_list_with_arbitrary_dict":
        if type(parent[leaf]) is not list or len(parent[leaf]) == 0:
            raise ClaimWitnessError("TARGET_NOT_NONEMPTY_LIST", "replace_list requires non-empty list")
        parent[leaf] = [{"arbitrary": "not-a-valid-witness-entry"}]
    elif op == "drop_required_field":
        del parent[leaf]
    elif op == "corrupt_pinned_hash":
        old_hex = require_hex64_ascii(parent[leaf], "corrupt_pinned_hash.target")
        flipped = "1" if old_hex[0] == "0" else "0"
        parent[leaf] = flipped + old_hex[1:]
    elif op == "invert_numeric_claim":
        old_val = require_int(parent[leaf], "invert_numeric_claim.target")
        parent[leaf] = old_val + 1
    else:
        raise ClaimWitnessError("UNKNOWN_DESTRUCTION_OP", f"unsupported op: {op}")

    if "resign_hash_field" in spec:
        hfield = require_str(spec.get("resign_hash_field"), "resign_hash_field", non_empty=True)
        if hfield not in mutated:
            raise ClaimWitnessError("RESIGN_FIELD_MISSING", f"resign hash field missing: {hfield}")
        body = {k: v for k, v in mutated.items() if k != hfield}
        mutated[hfield] = canonical_sha256(body)
    return mutated


def _invoke_verifier_strict(verifier_fn: Callable[[dict[str, Any]], bool], witness: dict[str, Any]) -> bool:
    try:
        res = verifier_fn(witness)
    except Exception:
        return False
    if type(res) is not bool:
        raise ClaimWitnessError("INVALID_VERIFIER_RETURN_TYPE", "verifier_fn must return exact bool")
    return res


def run_semantic_destruction_gate(
    verifier_fn: Callable[[dict[str, Any]], bool],
    valid_witness: dict[str, Any],
    perturbations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Pillar 3 (Law 2b): Fail closed if verifier accepts ANY semantically destroyed witness."""
    if not callable(verifier_fn):
        raise ClaimWitnessError("VERIFIER_NOT_CALLABLE", "verifier_fn must be callable")
    base = require_exact_dict(valid_witness, "valid_witness")
    validate_json_value(base)
    specs = require_exact_list(perturbations, "perturbations", non_empty=True)

    valid_accepted = _invoke_verifier_strict(verifier_fn, copy.deepcopy(base))
    if not valid_accepted:
        return {
            "pillar": "pillar3_semantic_destruction_gate",
            "passed": False,
            "verdict": "VALID_WITNESS_REJECTED",
            "valid_witness_accepted": False,
            "perturbations_tested": 0,
            "hollow_survivals": 0,
            "surviving_ids": [],
            "results": [],
        }

    results: list[dict[str, Any]] = []
    for idx, raw_spec in enumerate(specs):
        spec = require_exact_dict(raw_spec, f"perturbations[{idx}]")
        pid = require_str(spec.get("id"), f"perturbations[{idx}].id", non_empty=True)
        destroyed = _apply_semantic_destruction(base, spec)
        survived = _invoke_verifier_strict(verifier_fn, destroyed)
        results.append({"id": pid, "op": spec["op"], "survived": survived})

    surviving_ids = [r["id"] for r in results if r["survived"]]
    passed = len(surviving_ids) == 0
    return {
        "pillar": "pillar3_semantic_destruction_gate",
        "passed": passed,
        "verdict": "STRICT_SEMANTIC_VERIFIER" if passed else "HOLLOW_WITNESS_VERIFIER",
        "valid_witness_accepted": True,
        "perturbations_tested": len(results),
        "hollow_survivals": len(surviving_ids),
        "surviving_ids": surviving_ids,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Built-In Reference Self-Test Suite (6 Escape Classes + 6 Clean Controls)
# ---------------------------------------------------------------------------


def _make_neuron_witness() -> tuple[dict[str, Any], str]:
    body: dict[str, Any] = {
        "study": "slot-and-homology-witness",
        "empirical_join": {
            "layer_joins": {"layer_15": 16, "layer_19": 4},
            "top40_first_seventh": 29,
        },
    }
    digest = canonical_sha256(body)
    body["canonical_sha256"] = digest
    return body, digest


def _hollow_self_hash_verifier(cert: dict[str, Any]) -> bool:
    """Foil verifier: checks self-hash consistency only, ignoring payload semantics and pin."""
    body = {k: v for k, v in cert.items() if k != "canonical_sha256"}
    return constant_time_hex64_equal(cert["canonical_sha256"], canonical_sha256(body))


def _strict_pinned_verifier(pinned_digest: str) -> Callable[[dict[str, Any]], bool]:
    def _verify(cert: dict[str, Any]) -> bool:
        body = {k: v for k, v in cert.items() if k != "canonical_sha256"}
        recomputed = canonical_sha256(body)
        if not constant_time_hex64_equal(cert["canonical_sha256"], recomputed):
            return False
        if not constant_time_hex64_equal(recomputed, pinned_digest):
            return False
        emp = cert["empirical_join"]
        joins = emp["layer_joins"]
        if joins.get("layer_15") != 16 or joins.get("layer_19") != 4:
            return False
        return emp["top40_first_seventh"] == 29

    return _verify


def _hollow_fault_verifier(record: dict[str, Any]) -> bool:
    """Foil verifier: checks list shape and non-empty dict count only."""
    faults = record["faults"]
    return (
        type(faults) is list
        and len(faults) == record["n_faults"]
        and all(type(f) is dict and len(f) > 0 for f in faults)
    )


def _strict_fault_verifier(record: dict[str, Any]) -> bool:
    """Strict verifier: requires circuit-fault fields, zero syndrome, and nontrivial logical flip."""
    faults = record["faults"]
    if type(faults) is not list or len(faults) != record["n_faults"]:
        return False
    for f in faults:
        if type(f) is not dict:
            return False
        if "qubit" not in f or "pauli" not in f or "syndrome_weight" not in f or "logical_flip" not in f:
            return False
        if f["syndrome_weight"] != 0 or f["logical_flip"] is not True:
            return False
    return True


def evaluate_reference_escape_suite() -> dict[str, Any]:
    """Execute P_CTW across 6 canonical shared-nullspace escape classes AND 6 clean positive controls."""
    neuron_witness, neuron_pin = _make_neuron_witness()
    neuron_perts = [
        {
            "id": "esc1_empty_layer_joins_resigned",
            "op": "empty_mapping_field",
            "path": ["empirical_join", "layer_joins"],
            "resign_hash_field": "canonical_sha256",
        },
        {
            "id": "esc1_drop_empirical_join_resigned",
            "op": "drop_required_field",
            "path": ["empirical_join"],
            "resign_hash_field": "canonical_sha256",
        },
    ]

    quantum_witness: dict[str, Any] = {
        "sector": "X",
        "n_faults": 1,
        "faults": [{"qubit": 17, "pauli": "X", "syndrome_weight": 0, "logical_flip": True}],
    }
    quantum_perts = [
        {
            "id": "esc3_arbitrary_non_fault_dict",
            "op": "replace_list_with_arbitrary_dict",
            "path": ["faults"],
        },
    ]

    # --- 6 Negative Controls (Canonical Shared-Nullspace Escape Classes: EVERY ONE MUST BE CAUGHT) ---
    esc1_p1 = verify_prose_artifact_bindings([{
        "id": "ESC1-partial-scale-group-bpw",
        "kind": "slot_packing_bpw",
        "n_values": 1024,
        "kept_values": 64,
        "kept_bits_per_val": 16,
        "rest_block_size": 8,
        "rest_bits_per_block": 28,
        "scale_group_size": 128,
        "scale_bits_per_slot": 16,
        "claimed_bpw": "4504/1024",
    }])
    esc1_p3 = run_semantic_destruction_gate(_hollow_self_hash_verifier, neuron_witness, neuron_perts)

    esc2_p1 = verify_prose_artifact_bindings([{
        "id": "ESC2-internal-whitespace-token",
        "kind": "prose_invariant_binding",
        "rule": "min_non_whitespace_chars",
        "threshold": 16,
        "sample_input": "a" + (" " * 14) + "b",
        "code_admitted": True,
    }])
    esc2_p2 = verify_provenance_claims([{
        "id": "ESC2-upstream-spec-completeness",
        "kind": "spec_completeness",
        "required_clauses": [
            "tied_rounds_counted",
            "f16_max_inward_gap_and_overflow_65520",
            "cross_format_nearest_cell",
            "absent_cell_infinite_error",
            "fwer_independence_assumption_declared",
        ],
        "implemented_clauses": [],
        "claimed_exact_spec_equivalence": True,
    }])

    esc3_p1 = verify_prose_artifact_bindings([{
        "id": "ESC3-integer-order-range-drift",
        "kind": "integer_range_binding",
        "claimed_count": 34,
        "claimed_min": 101,
        "claimed_max": 359,
        "artifact_count": 34,
        "artifact_min": 9,
        "artifact_max": 197,
    }])
    esc3_p3 = run_semantic_destruction_gate(_hollow_fault_verifier, quantum_witness, quantum_perts)

    esc4_p2 = verify_provenance_claims([{
        "id": "ESC4-surrogate-and-causal-overclaim",
        "kind": "operator_equivalence",
        "claimed_operator": "SiLU_RMSNorm",
        "claimed_provenance": "exact_operator",
        "witness_operator": "rational_silu_rmslike",
        "witness_provenance": "surrogate_operator",
        "claims_gradient_coverage": True,
        "witness_has_gradient_coverage": False,
        "claims_causal_impossibility": True,
        "witness_proves_only_distributional_symmetry": True,
    }])

    esc5_p1 = verify_prose_artifact_bindings([
        {
            "id": "ESC5a-c-hot-table-l1-flip",
            "kind": "c_allocation_table",
            "claimed_hot_bytes": 21994,
            "claimed_cache_limit_bytes": 32768,
            "claimed_fits_cache": True,
            "allocated_arrays": [
                {"name": "shell_dp_tables", "bytes": 21994, "hot_read": True},
                {"name": "recip_and_even_c8", "bytes": 12056, "hot_read": True},
                {"name": "checkpoint_meta", "bytes": 3504, "hot_read": False},
            ],
        },
        {
            "id": "ESC5b-c-hot-table-omitted-recip",
            "kind": "c_allocation_table",
            "claimed_hot_bytes": 70780,
            "allocated_arrays": [
                {"name": "z32_dp_tables", "bytes": 70780, "hot_read": True},
                {"name": "z32_recip_tables", "bytes": 112896, "hot_read": True},
            ],
        },
    ])
    esc5_p2 = verify_provenance_claims([{
        "id": "ESC5-packed-file-scope-overclaim",
        "kind": "delivery_scope",
        "claimed_scope_tier": "packed_file_integration",
        "witnessed_scope_tier": "ctypes_benchmark_harness",
    }])

    esc6_p2 = verify_provenance_claims([{
        "id": "ESC6-cross-experiment-metric-smuggling",
        "kind": "metric_attribution",
        "claimed_subject": "E8_Had",
        "measured_subject": "E8_standard_EBG32_b136s8",
        "claimed_provenance": "same_experiment_measurement",
        "witness_provenance": "cross_experiment_anchor",
        "experiment_executed_for_claimed_subject": False,
    }])

    negative_cases = [
        {
            "escape_id": "ESC-01",
            "category": "slot_packing_and_hollow_self_hash",
            "pillars_catching": [
                p for p, ok in (("pillar1", esc1_p1["passed"]), ("pillar3", esc1_p3["passed"])) if not ok
            ],
            "caught": all(not r["passed"] for r in (esc1_p1, esc1_p3)),
            "evidence": {"pillar1": esc1_p1, "pillar3": esc1_p3},
        },
        {
            "escape_id": "ESC-02",
            "category": "prose_invariant_and_spec_completeness",
            "pillars_catching": [
                p for p, ok in (("pillar1", esc2_p1["passed"]), ("pillar2", esc2_p2["passed"])) if not ok
            ],
            "caught": all(not r["passed"] for r in (esc2_p1, esc2_p2)),
            "evidence": {"pillar1": esc2_p1, "pillar2": esc2_p2},
        },
        {
            "escape_id": "ESC-03",
            "category": "range_drift_and_hollow_fault_witness",
            "pillars_catching": [
                p for p, ok in (("pillar1", esc3_p1["passed"]), ("pillar3", esc3_p3["passed"])) if not ok
            ],
            "caught": all(not r["passed"] for r in (esc3_p1, esc3_p3)),
            "evidence": {"pillar1": esc3_p1, "pillar3": esc3_p3},
        },
        {
            "escape_id": "ESC-04",
            "category": "surrogate_and_causal_overclaim",
            "pillars_catching": [p for p, ok in (("pillar2", esc4_p2["passed"]),) if not ok],
            "caught": not esc4_p2["passed"],
            "evidence": {"pillar2": esc4_p2},
        },
        {
            "escape_id": "ESC-05",
            "category": "c_footprint_and_delivery_scope",
            "pillars_catching": [
                p for p, ok in (("pillar1", esc5_p1["passed"]), ("pillar2", esc5_p2["passed"])) if not ok
            ],
            "caught": all(not r["passed"] for r in (esc5_p1, esc5_p2)),
            "evidence": {"pillar1": esc5_p1, "pillar2": esc5_p2},
        },
        {
            "escape_id": "ESC-06",
            "category": "cross_experiment_metric_attribution",
            "pillars_catching": [p for p, ok in (("pillar2", esc6_p2["passed"]),) if not ok],
            "caught": not esc6_p2["passed"],
            "evidence": {"pillar2": esc6_p2},
        },
    ]

    # --- 6 Positive Controls (Remediated / Clean Artifacts: EVERY ONE MUST PASS, 0 FP) ---
    pos1_p1 = verify_prose_artifact_bindings([{
        "id": "POS1-whole-scale-group",
        "kind": "slot_packing_bpw",
        "n_values": 1024,
        "kept_values": 64,
        "kept_bits_per_val": 16,
        "rest_block_size": 8,
        "rest_bits_per_block": 28,
        "scale_group_size": 128,
        "scale_bits_per_slot": 16,
        "claimed_bpw": "4512/1024",
    }])
    pos1_p3 = run_semantic_destruction_gate(
        _strict_pinned_verifier(neuron_pin), neuron_witness, neuron_perts
    )

    pos2_p1 = verify_prose_artifact_bindings([{
        "id": "POS2-non-ws-enforced",
        "kind": "prose_invariant_binding",
        "rule": "min_non_whitespace_chars",
        "threshold": 16,
        "sample_input": "a" + (" " * 14) + "b",
        "code_admitted": False,
    }])
    pos2_p2 = verify_provenance_claims([{
        "id": "POS2-spec-complete",
        "kind": "spec_completeness",
        "required_clauses": [
            "tied_rounds_counted",
            "f16_max_inward_gap_and_overflow_65520",
            "cross_format_nearest_cell",
            "absent_cell_infinite_error",
            "fwer_independence_assumption_declared",
        ],
        "implemented_clauses": [
            "tied_rounds_counted",
            "f16_max_inward_gap_and_overflow_65520",
            "cross_format_nearest_cell",
            "absent_cell_infinite_error",
            "fwer_independence_assumption_declared",
        ],
        "claimed_exact_spec_equivalence": True,
    }])

    pos3_p1 = verify_prose_artifact_bindings([{
        "id": "POS3-exact-range",
        "kind": "integer_range_binding",
        "claimed_count": 34,
        "claimed_min": 9,
        "claimed_max": 197,
        "artifact_count": 34,
        "artifact_min": 9,
        "artifact_max": 197,
    }])
    pos3_p3 = run_semantic_destruction_gate(_strict_fault_verifier, quantum_witness, quantum_perts)

    pos4_p2 = verify_provenance_claims([{
        "id": "POS4-narrowed-surrogate-distributional",
        "kind": "operator_equivalence",
        "claimed_operator": "rational_silu_rmslike",
        "claimed_provenance": "surrogate_operator",
        "witness_operator": "rational_silu_rmslike",
        "witness_provenance": "surrogate_operator",
        "claims_gradient_coverage": True,
        "witness_has_gradient_coverage": True,
        "claims_causal_impossibility": False,
        "witness_proves_only_distributional_symmetry": True,
    }])

    pos5_p1 = verify_prose_artifact_bindings([
        {
            "id": "POS5a-c-hot-exact",
            "kind": "c_allocation_table",
            "claimed_hot_bytes": 34050,
            "claimed_cache_limit_bytes": 32768,
            "claimed_fits_cache": False,
            "allocated_arrays": [
                {"name": "shell_dp_tables", "bytes": 21994, "hot_read": True},
                {"name": "recip_and_even_c8", "bytes": 12056, "hot_read": True},
                {"name": "checkpoint_meta", "bytes": 3504, "hot_read": False},
            ],
        },
        {
            "id": "POS5b-c-hot-z32-exact",
            "kind": "c_allocation_table",
            "claimed_hot_bytes": 183676,
            "allocated_arrays": [
                {"name": "z32_dp_tables", "bytes": 70780, "hot_read": True},
                {"name": "z32_recip_tables", "bytes": 112896, "hot_read": True},
            ],
        },
    ])
    pos5_p2 = verify_provenance_claims([{
        "id": "POS5-narrowed-research-scope",
        "kind": "delivery_scope",
        "claimed_scope_tier": "ctypes_benchmark_harness",
        "witnessed_scope_tier": "ctypes_benchmark_harness",
    }])

    pos6_p2 = verify_provenance_claims([{
        "id": "POS6-narrowed-cross-experiment-anchor",
        "kind": "metric_attribution",
        "claimed_subject": "E8_Had",
        "measured_subject": "E8_standard_EBG32_b136s8",
        "claimed_provenance": "cross_experiment_anchor",
        "witness_provenance": "cross_experiment_anchor",
        "experiment_executed_for_claimed_subject": False,
    }])

    positive_cases = [
        {"control_id": "POS-01", "passed": all(r["passed"] for r in (pos1_p1, pos1_p3))},
        {"control_id": "POS-02", "passed": all(r["passed"] for r in (pos2_p1, pos2_p2))},
        {"control_id": "POS-03", "passed": all(r["passed"] for r in (pos3_p1, pos3_p3))},
        {"control_id": "POS-04", "passed": pos4_p2["passed"]},
        {"control_id": "POS-05", "passed": all(r["passed"] for r in (pos5_p1, pos5_p2))},
        {"control_id": "POS-06", "passed": pos6_p2["passed"]},
    ]

    caught_count = sum(1 for c in negative_cases if c["caught"])
    pos_pass_count = sum(1 for c in positive_cases if c["passed"])
    return {
        "negative_escapes_total": len(negative_cases),
        "negative_escapes_caught": caught_count,
        "positive_controls_total": len(positive_cases),
        "positive_controls_passed": pos_pass_count,
        "false_positives": len(positive_cases) - pos_pass_count,
        "negative_cases": negative_cases,
        "positive_cases": positive_cases,
    }


def compute_blind_spot_tomography() -> dict[str, Any]:
    """Compute exact Z/Q shared-nullspace tomography over anonymized verifier families and P_CTW."""
    verifier_families = [f"verifier_family_{i:02d}" for i in range(1, 12)]
    baseline_signatures: list[dict[str, Any]] = [
        {"id": "SIG-01", "families": ["verifier_family_04"]},
        {"id": "SIG-02", "families": ["verifier_family_04", "verifier_family_05", "verifier_family_07", "verifier_family_01"]},
        {"id": "SIG-03", "families": ["verifier_family_06", "verifier_family_05", "verifier_family_01"]},
        {"id": "SIG-04", "families": ["verifier_family_03"]},
        {"id": "SIG-05", "families": ["verifier_family_07", "verifier_family_03"]},
        {"id": "SIG-06", "families": ["verifier_family_07"]},
        {"id": "SIG-07", "families": ["verifier_family_02"]},
        {"id": "SIG-08", "families": ["verifier_family_01"]},
    ]

    per_family_sig_counts: dict[str, int] = {fam: 0 for fam in verifier_families}
    exclusive_sigs = 0
    for sig in baseline_signatures:
        fams = sig["families"]
        if len(fams) == 1:
            exclusive_sigs += 1
        for fam in fams:
            per_family_sig_counts[fam] += 1

    suite = evaluate_reference_escape_suite()
    n_internal_sigs = len(baseline_signatures)
    n_escape_sigs = suite["negative_escapes_total"]
    n_total_sigs = n_internal_sigs + n_escape_sigs
    n_escapes_caught = suite["negative_escapes_caught"]
    n_pos_total = suite["positive_controls_total"]
    n_pos_passed = suite["positive_controls_passed"]

    max_single_family_sigs = max(per_family_sig_counts.values())
    pillar1_caught = sum(1 for c in suite["negative_cases"] if "pillar1" in c["pillars_catching"])
    pillar2_caught = sum(1 for c in suite["negative_cases"] if "pillar2" in c["pillars_catching"])
    pillar3_caught = sum(1 for c in suite["negative_cases"] if "pillar3" in c["pillars_catching"])

    before_recall = Fraction(n_internal_sigs, n_total_sigs)
    after_recall = Fraction(n_internal_sigs + n_escapes_caught, n_total_sigs)
    recall_gain = after_recall - before_recall

    return {
        "verifier_families_count": len(verifier_families),
        "baseline_orthogonal_signatures_count": n_internal_sigs,
        "baseline_exclusive_signatures_count": exclusive_sigs,
        "baseline_exclusive_share_q": fmt_q(Fraction(exclusive_sigs, n_internal_sigs)),
        "baseline_max_single_family_sigs": max_single_family_sigs,
        "baseline_max_single_family_share_q": fmt_q(Fraction(max_single_family_sigs, n_internal_sigs)),
        "shared_nullspace_escapes_count": n_escape_sigs,
        "total_corpus_signatures_count": n_total_sigs,
        "before_pctw_corpus_recall_q": fmt_q(before_recall),
        "before_pctw_shared_nullspace_share_q": fmt_q(Fraction(n_escape_sigs, n_total_sigs)),
        "after_pctw_escape_recall_q": fmt_q(Fraction(n_escapes_caught, n_escape_sigs)),
        "after_pctw_positive_specificity_q": fmt_q(Fraction(n_pos_passed, n_pos_total)),
        "after_pctw_false_positive_rate_q": fmt_q(Fraction(suite["false_positives"], n_pos_total)),
        "after_pctw_corpus_recall_q": fmt_q(after_recall),
        "corpus_recall_gain_q": fmt_q(recall_gain),
        "per_pillar_escape_coverage": {
            "pillar1_count": pillar1_caught,
            "pillar1_share_q": fmt_q(Fraction(pillar1_caught, n_escape_sigs)),
            "pillar2_count": pillar2_caught,
            "pillar2_share_q": fmt_q(Fraction(pillar2_caught, n_escape_sigs)),
            "pillar3_count": pillar3_caught,
            "pillar3_share_q": fmt_q(Fraction(pillar3_caught, n_escape_sigs)),
        },
        "per_family_baseline_sig_counts": per_family_sig_counts,
        "reference_escape_suite": suite,
        "law4_residual_blind_spot_bounds": {
            "in_sample_closure_note": (
                "14/14 recall is in-sample over the 8 baseline signatures plus 6 canonical "
                "escape classes, NOT proof of zero universal blind spot."
            ),
            "irreducible_residual_classes": [
                "unextracted_prose_claims_omitted_from_binding_manifest",
                "undiscovered_upstream_spec_edge_cases_absent_from_clause_list",
                "external_hardware_or_real_model_measurements_without_committed_raw_data",
                "novel_mathematical_or_statistical_dependence_counterexamples",
            ],
        },
    }


def build_certificate() -> dict[str, Any]:
    """Deterministically build the exact Z/Q claim-to-witness self-test certificate."""
    payload = compute_blind_spot_tomography()
    suite = payload["reference_escape_suite"]
    if (
        suite["negative_escapes_caught"] != suite["negative_escapes_total"]
        or suite["false_positives"] != 0
        or suite["positive_controls_passed"] != suite["positive_controls_total"]
    ):
        raise ClaimWitnessError(
            "SELF_TEST_FAILED",
            f"self-test failed: escapes={suite['negative_escapes_caught']}/{suite['negative_escapes_total']} "
            f"false_positives={suite['false_positives']}",
        )
    payload_sha = canonical_sha256(payload)
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "component_id": COMPONENT_ID,
        "oracle_class": "exact+empirical-corpus",
        "novelty_tier": "N1",
        "payload": payload,
        "payload_sha256": payload_sha,
    }
    cert_sha = canonical_sha256(body)
    body["certificate_sha256"] = cert_sha
    return body


def verify_certificate_file(path: Path) -> dict[str, Any]:
    """Fail-closed verification of canonical JSON bytes, digests, and exact recomputation."""
    raw, text = read_strict_utf8_file(path)
    parsed = require_exact_dict(parse_strict_json_text(text, require_object=True), "certificate")
    canonical_raw = canonical_json_bytes(parsed)
    if raw not in (canonical_raw, canonical_raw + b"\n"):
        raise ClaimWitnessError("NON_CANONICAL_CERT_BYTES", "certificate file is not canonical JSON")

    if frozenset(parsed.keys()) != REQUIRED_CERT_KEYS:
        raise ClaimWitnessError("CERT_KEYS_MISMATCH", "certificate top-level key set mismatch")

    expected = build_certificate()
    parsed_payload = require_exact_dict(parsed["payload"], "certificate.payload")
    recomputed_payload_sha = canonical_sha256(parsed_payload)
    if not constant_time_hex64_equal(parsed["payload_sha256"], recomputed_payload_sha, "payload_sha256"):
        raise ClaimWitnessError("PAYLOAD_SHA_MISMATCH", "recorded payload_sha256 does not match payload")

    body_without_cert_sha = {k: v for k, v in parsed.items() if k != "certificate_sha256"}
    recomputed_cert_sha = canonical_sha256(body_without_cert_sha)
    if not constant_time_hex64_equal(parsed["certificate_sha256"], recomputed_cert_sha, "certificate_sha256"):
        raise ClaimWitnessError("CERTIFICATE_SHA_MISMATCH", "recorded certificate_sha256 does not match body")

    if not constant_time_hex64_equal(recomputed_payload_sha, expected["payload_sha256"], "expected_payload_sha256"):
        raise ClaimWitnessError("PAYLOAD_RECOMPUTATION_MISMATCH", "payload diverges from deterministic recomputation")

    if not constant_time_hex64_equal(recomputed_cert_sha, expected["certificate_sha256"], "expected_cert_sha256"):
        raise ClaimWitnessError("CERT_RECOMPUTATION_MISMATCH", "certificate diverges from deterministic recomputation")

    return {
        "valid": True,
        "payload_sha256": recomputed_payload_sha,
        "certificate_sha256": recomputed_cert_sha,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aletheia v2.1 — 3-Pillar Claim-to-Witness Binding Operator")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--self-test", "--standalone", dest="standalone", action="store_true", help="Compute and emit self-test certificate")
    mode.add_argument("--check", type=Path, help="Verify a canonical certificate JSON file fail-closed")
    parser.add_argument("--json", action="store_true", help="Emit canonical JSON output")
    args = parser.parse_args(argv)

    if args.check is None:
        try:
            cert = build_certificate()
        except ClaimWitnessError as exc:
            sys.stderr.write(f"FAIL {exc.code}: {exc.detail}\n")
            return 1
        if args.json:
            sys.stdout.write(canonical_json_bytes(cert).decode("ascii") + "\n")
            return 0
        sys.stdout.write(
            f"OK {COMPONENT_ID} payload_sha256={cert['payload_sha256']} "
            f"certificate_sha256={cert['certificate_sha256']}\n"
        )
        return 0

    try:
        verdict = verify_certificate_file(args.check)
    except (ClaimWitnessError, OSError) as exc:
        if isinstance(exc, ClaimWitnessError):
            sys.stderr.write(f"FAIL {exc.code}: {exc.detail}\n")
        else:
            sys.stderr.write(f"FAIL IO_ERROR: {exc}\n")
        return 1

    if args.json:
        sys.stdout.write(canonical_json_bytes(verdict).decode("ascii") + "\n")
        return 0
    sys.stdout.write(
        f"OK verified payload_sha256={verdict['payload_sha256']} "
        f"certificate_sha256={verdict['certificate_sha256']}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
