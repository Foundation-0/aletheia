#!/usr/bin/env python3
"""Hardened CLI, Full Pure-Z/Q Replay & Deep Secondary Auditor for Silq x CS-21.

100% pure Python 3 stdlib, zero IEEE-754 floats, zero bare asserts, zero .isdigit(),
zero mathematical RNG (secrets.token_hex used strictly for atomic temp filename uniqueness).
"""
from __future__ import annotations

import errno
from fractions import Fraction
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import secrets
import stat
import sys
import threading
from typing import Any, Sequence

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import silq_cs21_compiler_oracle as oracle  # noqa: E402

MAX_JSON_BYTES = 1_048_576
MAX_ALLOWED_CAP_BYTES = 64 * 1024 * 1024
_READ_CHUNK_BYTES = 65_536
MAX_JSON_DEPTH = 64
MAX_JSON_INT_DIGITS = oracle.MAX_INT_DIGITS
_EXACT_PATH_TYPES = (Path, type(Path()))
_HEX_LOWER = frozenset("0123456789abcdef")
_ASCII_DIGITS = frozenset("0123456789")
_DIR_OPEN_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_DARWIN_SYSTEM_ROOT_ALIASES: tuple[tuple[str, str], ...] = (
    ("/var", "/private/var"),
    ("/tmp", "/private/tmp"),
    ("/etc", "/private/etc"),
)
_TEMP_NAME_LOCK = threading.Lock()
_TEMP_COUNTER = 0

_CERT_KEYS = frozenset({"schema_version", "track_id", "payload_sha256", "certificate_sha256", "payload"})
_PAYLOAD_KEYS = frozenset({
    "track_id",
    "portal_ref",
    "novelty_class",
    "prior_literature_n0",
    "cost_model_weights",
    "pillar1_typed_boundary_compiler",
    "pillar2_noncommutativity_and_cs21",
    "pillar3_pareto_boundary_optimizer",
    "pillar4_lean4_kernel_contract",
    "summary",
})
_WEIGHT_KEYS = frozenset({"w_t_q", "w_ctrl_q", "w_landauer_q", "landauer_and_bracket_q"})
_COST_KEYS = frozenset({
    "t_gates",
    "ctrl_ops",
    "and_erased",
    "reset_erased",
    "landauer_bits_lo_q",
    "landauer_bits_hi_q",
    "t_only_cost_q",
    "classical_ctrl_cost_q",
    "landauer_cost_lo_q",
    "landauer_cost_hi_q",
    "hidden_cost_lo_q",
    "hidden_cost_hi_q",
    "full_cost_lo_q",
    "full_cost_hi_q",
    "full_cost_lo_dec6",
    "full_cost_hi_dec6",
    "scaled_cost_lo_160",
    "scaled_cost_hi_10",
})
_P1_KEYS = frozenset({
    "valid_program_count",
    "must_fail_program_count",
    "valid_programs",
    "must_fail_programs",
    "all_valid_accepted",
    "all_must_fail_rejected",
    "all_verified",
})
_P1_VALID_KEYS = frozenset({
    "name",
    "annotation",
    "well_typed",
    "type_error_code",
    "return_types",
    "synthesized_uncomputations",
    "clifford_ops",
    "boundary_crossings",
    "cost",
})
_P1_FAIL_KEYS = frozenset({
    "name",
    "annotation",
    "well_typed",
    "expected_error_code",
    "actual_error_code",
    "rejected_with_expected_code",
})
_P2_KEYS = frozenset({
    "cs21_s44_mirage",
    "s38_landauer_erasure_proof",
    "noncommutativity_16and_witness",
    "all_verified",
})
_P2_MIRAGE_KEYS = frozenset({
    "circuit_a_qfree_clean",
    "circuit_b_classical_offload",
    "circuit_c_genuine_speedup",
    "apparent_t_speedup_b_vs_a_q",
    "hidden_cost_share_b_q",
    "full_cost_ratio_b_over_a_q",
    "full_cost_ratio_b_over_a_dec6",
    "ordering_reversed_by_full_cost",
    "genuine_speedup_dominates_both",
})
_P2_LAND_KEYS = frozenset({
    "and_power_product_2pow4H",
    "two_pow_19",
    "p_and_pow_4",
    "p_and_pow_5",
    "two_pow_24",
    "bracket_q",
    "bracket_verified",
    "erase_1bit_power_product",
    "toffoli_3bit_power_product",
    "toffoli_involution_exact",
})
_P2_NC_KEYS = frozenset({
    "order1_qfree_uncompute_then_measure",
    "order2_measure_offload_before_uncompute",
    "t_reduction_factor_q",
    "full_cost_lo_ratio_order2_over_order1_q",
    "full_cost_hi_ratio_order2_over_order1_q",
    "noncommutativity_strict_regression_even_at_lo",
})
_P3_KEYS = frozenset({
    "stage_count",
    "edge_count",
    "total_masks_enumerated",
    "legal_cut_count",
    "branch_and_bound",
    "optimal_boundary_cut",
    "all_quantum_baseline_cut",
    "naive_min_t_cut",
    "naive_min_t_penalty_ratio_q",
    "naive_min_t_penalty_ratio_dec6",
    "optimal_savings_vs_all_quantum_q",
    "optimal_savings_vs_naive_min_t_q",
    "pareto_frontier",
    "all_verified",
})
_P3_BB_KEYS = frozenset({"optimal_mask", "nodes_visited", "nodes_pruned", "matches_exhaustive_exact"})
_P3_CUT_KEYS = frozenset({"mask", "placement", "crossings", "cost"})
_P3_PARETO_KEYS = frozenset({"mask", "placement", "t_gates", "full_cost_lo_q", "full_cost_hi_q", "scaled_cost_hi_10"})
_P4_KEYS = frozenset({
    "lean_source_filename",
    "lean_theorem_count",
    "lean_theorem_names",
    "pinned_integer_identities",
    "zero_sorry_zero_native_decide_contract",
    "all_verified",
})
_P4_ID_KEYS = frozenset({
    "cs21_circuit_a_hi10",
    "cs21_circuit_b_hi10",
    "cs21_circuit_c_hi10",
    "noncomm_order1_lo160",
    "noncomm_order2_lo160",
    "pareto_opt_mask52_hi10",
    "pareto_opt_mask52_lo160",
    "all_quantum_mask32_hi10",
    "naive_min_t_mask62_hi10",
})
_SUMMARY_KEYS = frozenset({
    "pillar_count",
    "all_four_pillars_verified",
    "float_count_on_trust_path",
    "bare_assert_count",
    "rng_calls",
})


# ============================================================================
# 1. Hardened Path, CWD, Atomic dir_fd Traversal & Durable 0o600 Atomic Write
# ============================================================================

def _normalize_darwin_system_prefix(path: Path, *, allow_exact: bool = False) -> Path:
    """Map verified root-owned macOS /var, /tmp, /etc aliases to /private/* without resolving user symlinks."""
    if sys.platform != "darwin" or not path.is_absolute():
        return path
    parts = path.parts
    min_parts = 2 if allow_exact else 3
    if len(parts) < min_parts or ".." in parts:
        return path
    top = "/" + parts[1]
    for alias, canonical in _DARWIN_SYSTEM_ROOT_ALIASES:
        if top != alias:
            continue
        try:
            st = os.lstat(alias)
            if not stat.S_ISLNK(st.st_mode) or st.st_uid != 0:
                return path
            target = os.readlink(alias)
            if target not in (canonical, canonical.lstrip("/")):
                return path
        except OSError:
            return path
        return Path(canonical, *parts[2:])
    return path


def _require_utf8_no_surrogate(text: Any, label: str) -> str:
    if type(text) is not str:
        raise oracle.SilqCS21Error("INVALID_STR", f"{label}: exact str required")
    oracle.require_ok("\x00" not in text, "NUL_BYTE_FORBIDDEN", f"{label}: NUL byte forbidden")
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise oracle.SilqCS21Error("INVALID_UTF8_SURROGATE", f"{label}: lone UTF-16 surrogate forbidden") from exc
    return text


def _require_concrete_path(path: Any, label: str) -> Path:
    oracle.require_ok(type(path) in _EXACT_PATH_TYPES, "INVALID_PATH_TYPE", f"{label}: concrete pathlib.Path required")
    _require_utf8_no_surrogate(str(path), label)
    return path


def _safe_cwd(label: str) -> Path:
    try:
        return Path.cwd()
    except OSError as exc:
        raise oracle.SilqCS21Error("CWD_UNAVAILABLE", f"{label}: CWD unavailable ({type(exc).__name__})") from exc


def _check_pwd_no_symlinks(label: str) -> None:
    pwd = os.environ.get("PWD", "")
    if not pwd.startswith("/"):
        return
    _require_utf8_no_surrogate(pwd, f"{label} PWD")
    try:
        st_pwd = os.stat(pwd)
        st_dot = os.stat(".")
    except OSError:
        return
    if (st_pwd.st_dev, st_pwd.st_ino) != (st_dot.st_dev, st_dot.st_ino):
        return
    pwd_path = _normalize_darwin_system_prefix(Path(pwd), allow_exact=True)
    try:
        dfd = os.open("/", _DIR_OPEN_FLAGS)
    except OSError as exc:
        raise oracle.SilqCS21Error("CWD_UNAVAILABLE", f"{label}: cannot open root for PWD") from exc
    try:
        for part in pwd_path.parts[1:]:
            if part == ".":
                continue
            try:
                next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise oracle.SilqCS21Error(
                        "SYMLINK_ANCESTOR_FORBIDDEN", f"{label}: symlink PWD ancestor forbidden"
                    ) from exc
                raise oracle.SilqCS21Error(
                    "CWD_UNAVAILABLE", f"{label}: PWD ancestor unavailable ({type(exc).__name__})"
                ) from exc
            os.close(dfd)
            dfd = next_fd
    finally:
        os.close(dfd)


def _open_dir_chain(target: Path, label: str, *, create_parents: bool) -> tuple[int, str]:
    if target.is_absolute():
        norm_target = _normalize_darwin_system_prefix(target)
        parts = norm_target.parts[1:]
    else:
        cwd = _normalize_darwin_system_prefix(_safe_cwd(label), allow_exact=True)
        _check_pwd_no_symlinks(label)
        parts = cwd.parts[1:] + target.parts
    oracle.require_ok(
        len(parts) >= 1 and parts[-1] not in ("", ".", ".."),
        "NOT_A_REGULAR_FILE",
        f"{label}: path does not name a regular file leaf",
    )
    parent_parts = parts[:-1]
    leaf = parts[-1]
    err_code = "FILE_WRITE_ERROR" if create_parents else "FILE_READ_ERROR"
    try:
        dfd = os.open("/", _DIR_OPEN_FLAGS)
    except OSError as exc:
        raise oracle.SilqCS21Error(err_code, f"{label}: cannot open root") from exc
    try:
        for part in parent_parts:
            if part == ".":
                continue
            try:
                next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
            except OSError as exc:
                if create_parents and exc.errno == errno.ENOENT:
                    try:
                        os.mkdir(part, 0o755, dir_fd=dfd)
                    except FileExistsError:
                        pass
                    except OSError as mk_exc:
                        raise oracle.SilqCS21Error(
                            "FILE_WRITE_ERROR", f"{label}: mkdir failed ({type(mk_exc).__name__})"
                        ) from mk_exc
                    try:
                        next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
                    except OSError as re_exc:
                        raise oracle.SilqCS21Error(
                            "FILE_WRITE_ERROR", f"{label}: cannot open created dir ({type(re_exc).__name__})"
                        ) from re_exc
                elif exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise oracle.SilqCS21Error(
                        "SYMLINK_FORBIDDEN", f"{label}: symlink or non-directory ancestor forbidden"
                    ) from exc
                else:
                    raise oracle.SilqCS21Error(
                        err_code, f"{label}: cannot traverse ancestor ({type(exc).__name__})"
                    ) from exc
            os.close(dfd)
            dfd = next_fd
        return dfd, leaf
    except BaseException:
        os.close(dfd)
        raise


def read_regular_bytes_capped(path: Path, label: str = "file", max_bytes: int = MAX_JSON_BYTES) -> bytes:
    target = _require_concrete_path(path, label)
    oracle.require_exact_int(max_bytes, "max_bytes", lo=1, hi=MAX_ALLOWED_CAP_BYTES)
    dfd, leaf = _open_dir_chain(target, label, create_parents=False)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        try:
            fd = os.open(leaf, flags, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise oracle.SilqCS21Error("SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden") from exc
            raise oracle.SilqCS21Error(
                "FILE_READ_ERROR", f"{label}: cannot open ({type(exc).__name__})"
            ) from exc
    finally:
        os.close(dfd)

    chunks: list[bytes] = []
    total = 0
    try:
        st_f = os.fstat(fd)
        oracle.require_ok(stat.S_ISREG(st_f.st_mode), "NOT_A_REGULAR_FILE", f"{label}: not a regular file")
        while total <= max_bytes:
            chunk = os.read(fd, min(_READ_CHUNK_BYTES, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    except oracle.SilqCS21Error:
        raise
    except OSError as exc:
        raise oracle.SilqCS21Error("FILE_READ_ERROR", f"{label}: read failed ({type(exc).__name__})") from exc
    finally:
        os.close(fd)
    oracle.require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"{label}: exceeds {max_bytes} bytes")
    return b"".join(chunks)


def write_regular_bytes_safe(path: Path, payload: bytes, label: str = "output") -> None:
    global _TEMP_COUNTER
    oracle.require_ok(type(payload) is bytes, "INVALID_PAYLOAD_BYTES", f"{label}: payload must be exact bytes")
    target = _require_concrete_path(path, label)
    dfd, leaf = _open_dir_chain(target, label, create_parents=True)
    tmp_name: str | None = None
    try:
        try:
            st_existing = os.lstat(leaf, dir_fd=dfd)
        except FileNotFoundError:
            st_existing = None
        except OSError as exc:
            raise oracle.SilqCS21Error(
                "FILE_WRITE_ERROR", f"{label}: lstat failed ({type(exc).__name__})"
            ) from exc
        if st_existing is not None:
            oracle.require_ok(not stat.S_ISLNK(st_existing.st_mode), "SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden")
            oracle.require_ok(stat.S_ISREG(st_existing.st_mode), "NOT_A_REGULAR_FILE", f"{label}: non-regular target")
            oracle.require_ok(st_existing.st_nlink <= 1, "HARDLINK_FORBIDDEN", f"{label}: hardlinked target forbidden")

        pid = os.getpid()
        for _ in range(32):
            with _TEMP_NAME_LOCK:
                _TEMP_COUNTER += 1
                seq_num = _TEMP_COUNTER
                cand = f".s54.{pid}.{seq_num}.{secrets.token_hex(8)}.tmp"
            try:
                fd = os.open(
                    cand,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK,
                    0o600,
                    dir_fd=dfd,
                )
                tmp_name = cand
                break
            except FileExistsError:
                continue
            except OSError as exc:
                raise oracle.SilqCS21Error(
                    "FILE_WRITE_ERROR", f"{label}: create temp failed ({type(exc).__name__})"
                ) from exc
        else:
            raise oracle.SilqCS21Error("FILE_WRITE_ERROR", f"{label}: exhausted temp file slots")

        try:
            view = memoryview(payload)
            written = 0
            while written < len(view):
                written += os.write(fd, view[written:])
            os.fsync(fd)
            st_tmp = os.fstat(fd)
            oracle.require_ok(st_tmp.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: temp link count altered")
        except oracle.SilqCS21Error:
            raise
        except OSError as exc:
            raise oracle.SilqCS21Error(
                "FILE_WRITE_ERROR", f"{label}: write failed ({type(exc).__name__})"
            ) from exc
        finally:
            os.close(fd)

        try:
            os.replace(tmp_name, leaf, src_dir_fd=dfd, dst_dir_fd=dfd)
            tmp_name = None
            os.fsync(dfd)
        except OSError as exc:
            raise oracle.SilqCS21Error(
                "FILE_WRITE_ERROR", f"{label}: atomic replace failed ({type(exc).__name__})"
            ) from exc
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
        os.close(dfd)


# ============================================================================
# 2. Strict ASCII Parsers, Binding 3,321-Bit Cap & Canonical JSON
# ============================================================================

def require_hex64_lower_ascii(val: Any, label: str = "sha256") -> str:
    s = _require_utf8_no_surrogate(val, label)
    oracle.require_ok(len(s) == 64, "INVALID_HEX64", f"{label}: expected 64-char lowercase ASCII hex")
    for ch in s:
        oracle.require_ok(ch in _HEX_LOWER, "INVALID_HEX64", f"{label}: non-hex-lowercase char")
    return s


def _parse_bounded_int(token: str) -> int:
    s = _require_utf8_no_surrogate(token, "json_int")
    oracle.require_ok(s != "-0", "INVALID_JSON_INT", "negative zero forbidden")
    digits = s[1:] if s.startswith("-") else s
    oracle.require_ok(len(digits) >= 1, "INVALID_JSON_INT", "JSON int has no digits")
    oracle.require_ok(len(digits) <= MAX_JSON_INT_DIGITS, "INT_DIGIT_LIMIT", "JSON int exceeds digit cap")
    oracle.require_ok(digits == "0" or not digits.startswith("0"), "INVALID_JSON_INT", "leading zero forbidden")
    for ch in digits:
        oracle.require_ok(ch in _ASCII_DIGITS, "INVALID_JSON_INT", "non-ASCII digit forbidden")
    val = int(s)
    oracle.require_ok(val.bit_length() <= oracle.MAX_INT_BITS, "INT_BIT_LIMIT", "JSON int exceeds 3,321-bit cap")
    return val


def parse_exact_rational(token: Any, label: str = "rational") -> Fraction:
    s = _require_utf8_no_surrogate(token, label)
    parts = s.split("/")
    oracle.require_ok(len(parts) in (1, 2), "INVALID_RATIONAL", f"{label}: expected 'n' or 'n/d'")
    num = _parse_bounded_int(parts[0])
    if len(parts) == 1:
        return oracle.require_exact_fraction(Fraction(num, 1), label)
    den = _parse_bounded_int(parts[1])
    oracle.require_ok(den >= 2, "INVALID_RATIONAL", f"{label}: denominator must be >= 2")
    oracle.require_ok(math.gcd(abs(num), den) == 1, "NON_CANONICAL_RATIONAL", f"{label}: not in lowest terms")
    return oracle.require_exact_fraction(Fraction(num, den), label)


def _validate_json_tree(root: Any, label: str = "json") -> None:
    stack: list[tuple[Any, int]] = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        oracle.require_ok(depth <= MAX_JSON_DEPTH, "JSON_DEPTH_LIMIT", f"{label}: nesting exceeds {MAX_JSON_DEPTH}")
        t = type(node)
        if node is None or t is bool:
            continue
        if t is int:
            oracle.require_ok(node.bit_length() <= oracle.MAX_INT_BITS, "INT_BIT_LIMIT", f"{label}: int exceeds 3,321 bits")
            continue
        if t is str:
            _require_utf8_no_surrogate(node, label)
            continue
        if t is list:
            nxt = depth + 1
            for item in node:
                stack.append((item, nxt))
            continue
        if t is dict:
            nxt = depth + 1
            for k, v in node.items():
                _require_utf8_no_surrogate(k, f"{label}.key")
                stack.append((v, nxt))
            continue
        raise oracle.SilqCS21Error("FORBIDDEN_JSON_TYPE", f"{label}: unsupported type {t.__name__}")


def _reject_float(token: str) -> Any:
    raise oracle.SilqCS21Error("FLOAT_LITERAL_FORBIDDEN", f"float literal forbidden: {token}")


def _reject_constant(token: str) -> Any:
    raise oracle.SilqCS21Error("NONFINITE_LITERAL_FORBIDDEN", f"non-finite constant forbidden: {token}")


def _strict_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        _require_utf8_no_surrogate(k, "json_key")
        oracle.require_ok(k not in out, "DUPLICATE_JSON_KEY", f"duplicate key {k!r}")
        out[k] = v
    return out


def parse_strict_json_text(text: Any, *, require_object: bool = True, max_bytes: int = MAX_JSON_BYTES) -> Any:
    s = _require_utf8_no_surrogate(text, "json_text")
    oracle.require_exact_bool(require_object, "require_object")
    oracle.require_exact_int(max_bytes, "max_bytes", lo=1, hi=MAX_ALLOWED_CAP_BYTES)
    oracle.require_ok(len(s.encode("utf-8")) <= max_bytes, "JSON_TOO_LARGE", "JSON text exceeds byte cap")
    try:
        parsed = json.loads(
            s,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
            parse_int=_parse_bounded_int,
            object_pairs_hook=_strict_pairs_hook,
        )
    except oracle.SilqCS21Error:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise oracle.SilqCS21Error("JSON_PARSE_ERROR", f"invalid JSON ({type(exc).__name__})") from exc
    _validate_json_tree(parsed, "parsed_json")
    if require_object and type(parsed) is not dict:
        raise oracle.SilqCS21Error("JSON_ROOT_NOT_OBJECT", "JSON root must be an object")
    return parsed


def canonical_json_bytes(obj: Any) -> bytes:
    _validate_json_tree(obj, "canonical_json")
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_canonical(obj: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


# ============================================================================
# 3. Deep Schema-Safe Secondary Auditor (Live Algebraic & Strict Nested Keys)
# ============================================================================

def _req_dict(val: Any, label: str, expected_keys: frozenset[str]) -> dict[str, Any]:
    oracle.require_ok(type(val) is dict, "INVALID_SCHEMA_DICT", f"{label}: exact dict required")
    oracle.require_ok(frozenset(val.keys()) == expected_keys, "INVALID_SCHEMA_KEYS", f"{label}: key set mismatch")
    return val


def _req_list(val: Any, label: str, exact_len: int) -> list[Any]:
    oracle.require_ok(type(val) is list and len(val) == exact_len, "INVALID_SCHEMA_LIST", f"{label}: list len {exact_len} required")
    return val


def _req_int_f(obj: dict[str, Any], key: str, label: str) -> int:
    return oracle.require_exact_int(obj[key], f"{label}.{key}")


def _req_bool_f(obj: dict[str, Any], key: str, label: str) -> bool:
    return oracle.require_exact_bool(obj[key], f"{label}.{key}")


def _audit_cost_block(val: Any, label: str) -> bool:
    cd = _req_dict(val, label, _COST_KEYS)
    tg = _req_int_f(cd, "t_gates", label)
    co = _req_int_f(cd, "ctrl_ops", label)
    na = _req_int_f(cd, "and_erased", label)
    nr = _req_int_f(cd, "reset_erased", label)
    s_lo = _req_int_f(cd, "scaled_cost_lo_160", label)
    s_hi = _req_int_f(cd, "scaled_cost_hi_10", label)
    f_lo = parse_exact_rational(cd["full_cost_lo_q"], f"{label}.full_lo")
    f_hi = parse_exact_rational(cd["full_cost_hi_q"], f"{label}.full_hi")
    return all((
        s_lo == 160 * tg + 16 * co + 95 * na + 80 * nr,
        s_hi == 10 * tg + co + 6 * na + 5 * nr,
        f_lo * 160 == s_lo,
        f_hi * 10 == s_hi,
    ))


def _audit_cut_block(val: Any, label: str) -> bool:
    cd = _req_dict(val, label, _P3_CUT_KEYS)
    _req_int_f(cd, "mask", label)
    _req_int_f(cd, "crossings", label)
    return _audit_cost_block(cd["cost"], f"{label}.cost")


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Fail-closed strict-nested-keyset + live algebraic cross-check across ALL 4 pillars."""
    _validate_json_tree(payload, "payload")
    pl = _req_dict(payload, "payload", _PAYLOAD_KEYS)
    wt = _req_dict(pl["cost_model_weights"], "weights", _WEIGHT_KEYS)
    wt_br = _req_list(wt["landauer_and_bracket_q"], "wt.bracket", 2)
    p1 = _req_dict(pl["pillar1_typed_boundary_compiler"], "p1", _P1_KEYS)
    p2 = _req_dict(pl["pillar2_noncommutativity_and_cs21"], "p2", _P2_KEYS)
    p2_m = _req_dict(p2["cs21_s44_mirage"], "p2.mirage", _P2_MIRAGE_KEYS)
    p2_l = _req_dict(p2["s38_landauer_erasure_proof"], "p2.landauer", _P2_LAND_KEYS)
    p2_n = _req_dict(p2["noncommutativity_16and_witness"], "p2.noncomm", _P2_NC_KEYS)
    p3 = _req_dict(pl["pillar3_pareto_boundary_optimizer"], "p3", _P3_KEYS)
    p3_bb = _req_dict(p3["branch_and_bound"], "p3.bb", _P3_BB_KEYS)
    p4 = _req_dict(pl["pillar4_lean4_kernel_contract"], "p4", _P4_KEYS)
    p4_id = _req_dict(p4["pinned_integer_identities"], "p4.ids", _P4_ID_KEYS)
    summ = _req_dict(pl["summary"], "summary", _SUMMARY_KEYS)

    ref_p1 = oracle.certify_pillar1_typed_boundary_compiler()
    ref_p2 = oracle.certify_pillar2_noncommutativity_and_cs21()
    ref_p3 = oracle.certify_pillar3_pareto_boundary_optimizer()
    ref_p4 = oracle.certify_pillar4_lean4_kernel_contract()

    # Pillar 1 strict nested program rows & cost checks
    val_rows = _req_list(p1["valid_programs"], "p1.valid", 5)
    p1_val_ok = all(
        all((
            _req_bool_f(rd, "well_typed", f"p1.v[{i}]"),
            _req_int_f(rd, "clifford_ops", f"p1.v[{i}]") >= 0,
            _req_int_f(rd, "boundary_crossings", f"p1.v[{i}]") >= 0,
            _audit_cost_block(rd["cost"], f"p1.v[{i}].cost"),
        ))
        for i, rd in enumerate(_req_dict(r, f"p1.v[{i}]", _P1_VALID_KEYS) for i, r in enumerate(val_rows))
    )
    fail_rows = _req_list(p1["must_fail_programs"], "p1.fail", 8)
    p1_fail_ok = all(
        all((
            not _req_bool_f(rd, "well_typed", f"p1.f[{i}]"),
            _req_bool_f(rd, "rejected_with_expected_code", f"p1.f[{i}]"),
        ))
        for i, rd in enumerate(_req_dict(r, f"p1.f[{i}]", _P1_FAIL_KEYS) for i, r in enumerate(fail_rows))
    )
    p1_ok = all((
        _req_int_f(p1, "valid_program_count", "p1") == 5,
        _req_int_f(p1, "must_fail_program_count", "p1") == 8,
        _req_bool_f(p1, "all_valid_accepted", "p1"),
        _req_bool_f(p1, "all_must_fail_rejected", "p1"),
        _req_bool_f(p1, "all_verified", "p1"),
        p1_val_ok,
        p1_fail_ok,
        canonical_json_bytes(p1) == canonical_json_bytes(ref_p1),
    ))

    # Pillar 2 division-free algebraic cross-checks
    p2_a_ok = _audit_cost_block(p2_m["circuit_a_qfree_clean"], "p2.m.a")
    p2_b_ok = _audit_cost_block(p2_m["circuit_b_classical_offload"], "p2.m.b")
    p2_c_ok = _audit_cost_block(p2_m["circuit_c_genuine_speedup"], "p2.m.c")
    p2_o1_ok = _audit_cost_block(p2_n["order1_qfree_uncompute_then_measure"], "p2.n.o1")
    p2_o2_ok = _audit_cost_block(p2_n["order2_measure_offload_before_uncompute"], "p2.n.o2")
    ratio_ba = parse_exact_rational(p2_m["full_cost_ratio_b_over_a_q"], "p2.m.ratio")
    p_and = _req_int_f(p2_l, "and_power_product_2pow4H", "p2.l")
    p2_ok = all((
        p2_a_ok,
        p2_b_ok,
        p2_c_ok,
        p2_o1_ok,
        p2_o2_ok,
        ratio_ba * p2_m["circuit_a_qfree_clean"]["scaled_cost_hi_10"] == p2_m["circuit_b_classical_offload"]["scaled_cost_hi_10"],
        _req_bool_f(p2_m, "ordering_reversed_by_full_cost", "p2.m"),
        _req_bool_f(p2_m, "genuine_speedup_dominates_both", "p2.m"),
        _req_int_f(p2_l, "two_pow_19", "p2.l") < _req_int_f(p2_l, "p_and_pow_4", "p2.l"),
        _req_int_f(p2_l, "p_and_pow_5", "p2.l") < _req_int_f(p2_l, "two_pow_24", "p2.l"),
        _req_int_f(p2_l, "p_and_pow_4", "p2.l") == p_and**4,
        _req_int_f(p2_l, "p_and_pow_5", "p2.l") == p_and**5,
        _req_bool_f(p2_l, "bracket_verified", "p2.l"),
        _req_bool_f(p2_l, "toffoli_involution_exact", "p2.l"),
        _req_bool_f(p2_n, "noncommutativity_strict_regression_even_at_lo", "p2.n"),
        _req_bool_f(p2, "all_verified", "p2"),
        canonical_json_bytes(p2) == canonical_json_bytes(ref_p2),
    ))

    # Pillar 3 Pareto frontier & branch-and-bound checks
    pf_rows = _req_list(p3["pareto_frontier"], "p3.pareto", 4)
    pf_ok = all(
        all((
            _req_int_f(rd, "mask", f"p3.pf[{i}]") >= 0,
            _req_int_f(rd, "t_gates", f"p3.pf[{i}]") >= 0,
            parse_exact_rational(rd["full_cost_hi_q"], f"p3.pf[{i}].hi") * 10 == _req_int_f(rd, "scaled_cost_hi_10", f"p3.pf[{i}]"),
        ))
        for i, rd in enumerate(_req_dict(r, f"p3.pf[{i}]", _P3_PARETO_KEYS) for i, r in enumerate(pf_rows))
    )
    p3_ok = all((
        _req_int_f(p3, "stage_count", "p3") == 6,
        _req_int_f(p3, "edge_count", "p3") == 6,
        _req_int_f(p3, "total_masks_enumerated", "p3") == 64,
        _req_int_f(p3, "legal_cut_count", "p3") == 16,
        _req_int_f(p3_bb, "optimal_mask", "p3.bb") == 52,
        _req_int_f(p3_bb, "nodes_visited", "p3.bb") > 0,
        _req_int_f(p3_bb, "nodes_pruned", "p3.bb") > 0,
        _req_bool_f(p3_bb, "matches_exhaustive_exact", "p3.bb"),
        _audit_cut_block(p3["optimal_boundary_cut"], "p3.opt"),
        _audit_cut_block(p3["all_quantum_baseline_cut"], "p3.allq"),
        _audit_cut_block(p3["naive_min_t_cut"], "p3.mint"),
        pf_ok,
        _req_bool_f(p3, "all_verified", "p3"),
        canonical_json_bytes(p3) == canonical_json_bytes(ref_p3),
    ))

    # Pillar 4 Lean 4 contract checks
    p4_ok = all((
        _req_int_f(p4, "lean_theorem_count", "p4") == 7,
        _req_int_f(p4_id, "pareto_opt_mask52_hi10", "p4.ids") == 4324,
        _req_int_f(p4_id, "cs21_circuit_b_hi10", "p4.ids") == 6000,
        _req_bool_f(p4, "zero_sorry_zero_native_decide_contract", "p4"),
        _req_bool_f(p4, "all_verified", "p4"),
        canonical_json_bytes(p4) == canonical_json_bytes(ref_p4),
    ))

    ok_all = all((
        pl["track_id"] == oracle.TRACK_ID,
        pl["portal_ref"] == oracle.PORTAL_REF,
        pl["novelty_class"] == oracle.NOVELTY_CLASS,
        canonical_json_bytes(pl["prior_literature_n0"]) == canonical_json_bytes(oracle.PRIOR_LITERATURE_N0),
        parse_exact_rational(wt["w_t_q"], "wt.t") == oracle.WEIGHT_T,
        parse_exact_rational(wt["w_ctrl_q"], "wt.c") == oracle.WEIGHT_CTRL,
        parse_exact_rational(wt["w_landauer_q"], "wt.l") == oracle.WEIGHT_LANDAUER,
        parse_exact_rational(wt_br[0], "wt.bracket[0]") == oracle.LANDAUER_AND_LO,
        parse_exact_rational(wt_br[1], "wt.bracket[1]") == oracle.LANDAUER_AND_HI,
        p1_ok,
        p2_ok,
        p3_ok,
        p4_ok,
        _req_int_f(summ, "pillar_count", "summary") == 4,
        _req_bool_f(summ, "all_four_pillars_verified", "summary"),
        _req_int_f(summ, "float_count_on_trust_path", "summary") == 0,
        _req_int_f(summ, "bare_assert_count", "summary") == 0,
        _req_int_f(summ, "rng_calls", "summary") == 0,
    ))
    oracle.require_ok(ok_all, "SECONDARY_AUDIT_FAILED", "secondary algebraic cross-check failed")
    return {"secondary_audit_passed": True, "pillars_audited": 4}


def build_standalone_certificate() -> dict[str, Any]:
    payload = oracle.build_payload()
    payload_sha = _sha256_canonical(payload)
    outer = {
        "schema_version": oracle.SCHEMA_VERSION,
        "track_id": oracle.TRACK_ID,
        "payload_sha256": payload_sha,
        "payload": payload,
    }
    cert_sha = _sha256_canonical(outer)
    return {
        "schema_version": oracle.SCHEMA_VERSION,
        "track_id": oracle.TRACK_ID,
        "payload_sha256": payload_sha,
        "certificate_sha256": cert_sha,
        "payload": payload,
    }


def verify_certificate_dict(cert: Any, *, full_replay: bool = True) -> dict[str, Any]:
    oracle.require_exact_bool(full_replay, "full_replay")
    oracle.require_ok(type(cert) is dict, "INVALID_CERT_TYPE", "certificate must be exact dict")
    _validate_json_tree(cert, "cert")
    oracle.require_ok(frozenset(cert.keys()) == _CERT_KEYS, "INVALID_CERT_KEYS", "certificate keys mismatch")
    oracle.require_ok(cert["schema_version"] == oracle.SCHEMA_VERSION, "INVALID_SCHEMA", "schema_version mismatch")
    oracle.require_ok(cert["track_id"] == oracle.TRACK_ID, "INVALID_TRACK_ID", "track_id mismatch")
    oracle.require_ok(type(cert["payload"]) is dict, "INVALID_PAYLOAD_TYPE", "payload must be exact dict")

    claimed_p = require_hex64_lower_ascii(cert["payload_sha256"], "payload_sha256")
    claimed_c = require_hex64_lower_ascii(cert["certificate_sha256"], "certificate_sha256")

    actual_p = _sha256_canonical(cert["payload"])
    oracle.require_ok(hmac.compare_digest(claimed_p, actual_p), "PAYLOAD_SHA256_MISMATCH", "payload_sha256 mismatch")

    outer = {
        "schema_version": cert["schema_version"],
        "track_id": cert["track_id"],
        "payload_sha256": claimed_p,
        "payload": cert["payload"],
    }
    actual_c = _sha256_canonical(outer)
    oracle.require_ok(hmac.compare_digest(claimed_c, actual_c), "CERT_SHA256_MISMATCH", "certificate_sha256 mismatch")

    sec = secondary_audit_payload(cert["payload"])
    if full_replay:
        ref = build_standalone_certificate()
        oracle.require_ok(hmac.compare_digest(actual_p, ref["payload_sha256"]), "REPLAY_MISMATCH", "replay mismatch")

    return {
        "valid": True,
        "schema_version": oracle.SCHEMA_VERSION,
        "track_id": oracle.TRACK_ID,
        "payload_sha256": actual_p,
        "certificate_sha256": actual_c,
        "full_replay": full_replay,
        "secondary_audit": sec,
    }


def check_certificate_file(path: Path, *, full_replay: bool = True) -> dict[str, Any]:
    raw = read_regular_bytes_capped(path, "certificate", MAX_JSON_BYTES)
    oracle.require_ok(b"\r" not in raw, "CRLF_FORBIDDEN", "CRLF line endings forbidden")
    oracle.require_ok(raw.endswith(b"\n"), "MISSING_TRAILING_LF", "certificate must end with LF")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise oracle.SilqCS21Error("INVALID_UTF8", "certificate is not valid UTF-8") from exc
    cert = parse_strict_json_text(text, require_object=True)
    canon = canonical_json_bytes(cert)
    oracle.require_ok(raw == canon + b"\n", "NON_CANONICAL_BYTES", "certificate is not canonical ASCII JSON + LF")
    res = verify_certificate_dict(cert, full_replay=full_replay)
    res["canonical_sha256"] = hashlib.sha256(canon).hexdigest()
    res["file_sha256"] = hashlib.sha256(raw).hexdigest()
    return res


def write_certificate_file(path: Path) -> dict[str, Any]:
    cert = build_standalone_certificate()
    canon = canonical_json_bytes(cert)
    raw = canon + b"\n"
    write_regular_bytes_safe(path, raw, "certificate")
    return {
        "written": True,
        "schema_version": oracle.SCHEMA_VERSION,
        "track_id": oracle.TRACK_ID,
        "payload_sha256": cert["payload_sha256"],
        "certificate_sha256": cert["certificate_sha256"],
        "file_sha256": hashlib.sha256(raw).hexdigest(),
    }


# ============================================================================
# 4. Strict Fail-Closed CLI (Space & Equals Flag-Like Rejection)
# ============================================================================

def _reject_bad_path_arg(tok: str, val: str) -> Path:
    oracle.require_ok(bool(val) and not val.startswith("-"), "INVALID_PATH_ARG", f"{tok} path empty or flag-like")
    return Path(val)


def _parse_cli_argv(argv: Sequence[str]) -> tuple[str, Path | None, bool]:
    oracle.require_ok(type(argv) in (list, tuple), "INVALID_ARGV", "argv must be list or tuple")
    for item in argv:
        _require_utf8_no_surrogate(item, "argv_item")

    mode: str | None = None
    target: Path | None = None
    as_json = False
    i = 0
    n = len(argv)
    while i < n:
        tok = argv[i]
        if tok == "--json":
            oracle.require_ok(not as_json, "DUPLICATE_FLAG", "duplicate --json flag")
            as_json = True
            i += 1
        elif tok == "--standalone":
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "multiple mode flags forbidden")
            mode = "standalone"
            i += 1
        elif tok in ("--check", "--write"):
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "multiple mode flags forbidden")
            oracle.require_ok(i + 1 < n, "MISSING_PATH_ARG", f"{tok} requires a path argument")
            target = _reject_bad_path_arg(tok, argv[i + 1])
            mode = "check" if tok == "--check" else "write"
            i += 2
        elif tok.startswith("--check=") or tok.startswith("--write="):
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "multiple mode flags forbidden")
            flag_name, val = tok.split("=", 1)
            target = _reject_bad_path_arg(flag_name, val)
            mode = "check" if flag_name == "--check" else "write"
            i += 1
        else:
            raise oracle.SilqCS21Error("UNKNOWN_FLAG", f"unrecognized CLI argument: {tok}")

    if mode is None:
        mode = "standalone"
    return mode, target, as_json


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv: Any = sys.argv[1:] if argv is None else argv
    try:
        mode, target, as_json = _parse_cli_argv(raw_argv)
        if mode == "standalone":
            out: dict[str, Any] = build_standalone_certificate()
        elif mode == "write":
            out = write_certificate_file(target)  # type: ignore[arg-type]
        else:
            out = check_certificate_file(target)  # type: ignore[arg-type]
    except oracle.SilqCS21Error as exc:
        err = {"valid": False, "error_code": exc.code, "error_message": exc.detail}
        sys.stderr.write(canonical_json_bytes(err).decode("ascii") + "\n")
        return 2

    if as_json:
        sys.stdout.write(canonical_json_bytes(out).decode("ascii") + "\n")
    else:
        sys.stdout.write(
            f"OK {oracle.SCHEMA_VERSION} payload_sha256={out['payload_sha256']} "
            f"certificate_sha256={out['certificate_sha256']}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
