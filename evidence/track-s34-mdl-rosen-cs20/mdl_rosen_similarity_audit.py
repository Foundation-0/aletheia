#!/usr/bin/env python3
"""Zone-B hardened standalone CLI & certificate verifier for Track S34 (Portal 31).

100% pure Python 3 stdlib, zero IEEE-754 floats, zero bare asserts, zero scientific RNG.
Uniform Zone-B Gold Standard (R2 hardened):
  - Concrete pathlib.Path check + NUL-byte and lone UTF-16 surrogate path refusal
  - Deleted-CWD OSError wrapping -> CWD_UNAVAILABLE (rc=2)
  - Relative-path atomic dir_fd PWD walk + atomic per-component dir_fd openat
    (O_RDONLY | O_DIRECTORY | O_NOFOLLOW, ELOOP/ENOTDIR handling)
  - Leaf dir_fd O_RDONLY | O_NOFOLLOW | O_NONBLOCK + fstat S_ISREG + streaming
    64 KiB capped os.read (strict cap max_bytes <= 64 MiB)
  - Atomic write: type(payload) is bytes BEFORE dir/temp open -> dir_fd lstat
    (SYMLINK_FORBIDDEN, NOT_A_REGULAR_FILE, HARDLINK_FORBIDDEN on st_nlink > 1)
    -> thread-locked CSPRNG O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_NONBLOCK (0o600)
    temp file in same dfd -> os.fsync(tmp_fd) -> pre-replace os.fstat(tmp_fd).st_nlink == 1
    -> atomic os.replace(tmp, leaf, src_dir_fd=dfd, dst_dir_fd=dfd) -> os.fsync(dfd)
  - Strict ASCII-only 0-9 integer (no -0, no leading zeros) and canonical exact
    rational parsers (zero .isdigit(), zero bare ValueError)
  - Strict canonical_json_bytes tree validation (int bit cap, depth cap, no floats/cycles)
  - Strict exact-str argv validation, space- & equals-syntax flag-like/empty CLI
    path refusal (--write --json, --write=--json, --check=--json -> rc=2, 0 files)
  - Strict 64-char lowercase ASCII hex check BEFORE hmac.compare_digest +
    self-consistent SHA-256 + schema-safe fail-closed exact-int secondary_audit_payload
    (even with full_replay=False) + default full pure-Q deterministic replay
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
from typing import Any

_ROOT_DIR = str(Path(__file__).resolve().parent)
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import mdl_rosen_similarity_oracle as oracle  # noqa: E402

MAX_JSON_BYTES = 1_048_576
MAX_ALLOWED_CAP_BYTES = 64 * 1024 * 1024
_READ_CHUNK_BYTES = 65_536
MAX_JSON_DEPTH = 64
MAX_JSON_INT_DIGITS = 1_235
_EXACT_PATH_TYPES = (Path, type(Path()))
_HEX_LOWER = frozenset("0123456789abcdef")
_ASCII_DIGITS = frozenset("0123456789")
_CERT_KEYS = frozenset({"schema_version", "track_id", "payload_sha256", "certificate_sha256", "payload"})
_TEMP_NAME_LOCK = threading.Lock()
DEFAULT_CERT_NAME = "mdl_rosen_similarity_certificate.json"


def _require_utf8_no_surrogate(text: str, label: str) -> None:
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise oracle.MdlRosenError("INVALID_UTF8_SURROGATE", f"{label}: lone UTF-16 surrogate forbidden") from exc


def _require_concrete_path(path: Any, label: str) -> Path:
    oracle.require_ok(
        type(path) in _EXACT_PATH_TYPES,
        "INVALID_PATH_TYPE",
        f"{label}: concrete pathlib.Path required",
    )
    raw_s = str(path)
    oracle.require_ok("\x00" not in raw_s, "NUL_BYTE_FORBIDDEN", f"{label}: NUL byte forbidden")
    _require_utf8_no_surrogate(raw_s, label)
    return path


def _safe_cwd(label: str) -> Path:
    try:
        return Path.cwd()
    except OSError as exc:
        raise oracle.MdlRosenError("CWD_UNAVAILABLE", f"{label}: CWD unavailable ({exc})") from exc


def _check_pwd_no_symlinks(label: str) -> None:
    pwd = os.environ.get("PWD")
    if pwd and os.path.isabs(pwd):
        _require_utf8_no_surrogate(pwd, f"{label} PWD")
        pwd_path = Path(pwd)
        dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        try:
            dfd = os.open("/", dir_flags)
        except OSError as exc:
            raise oracle.MdlRosenError("CWD_UNAVAILABLE", f"{label}: cannot open root for PWD ({exc})") from exc
        try:
            for part in pwd_path.parts[1:]:
                try:
                    next_fd = os.open(part, dir_flags, dir_fd=dfd)
                except OSError as exc:
                    if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                        raise oracle.MdlRosenError(
                            "SYMLINK_ANCESTOR_FORBIDDEN",
                            f"{label}: symlink PWD ancestor forbidden",
                        ) from exc
                    raise oracle.MdlRosenError(
                        "CWD_UNAVAILABLE",
                        f"{label}: PWD ancestor unavailable ({exc})",
                    ) from exc
                os.close(dfd)
                dfd = next_fd
        finally:
            os.close(dfd)


def _open_dir_chain(target: Path, label: str, *, create_parents: bool) -> tuple[int, str]:
    """Open ancestor directory chain atomically via dir_fd + O_DIRECTORY | O_NOFOLLOW."""
    if target.is_absolute():
        parts = target.parts[1:]
    else:
        cwd = _safe_cwd(label)
        _check_pwd_no_symlinks(label)
        parts = cwd.parts[1:] + target.parts
    oracle.require_ok(
        len(parts) >= 1 and parts[-1] not in ("", ".", ".."),
        "NOT_A_REGULAR_FILE",
        f"{label}: path does not name a regular file leaf",
    )
    parent_parts = parts[:-1]
    leaf = parts[-1]
    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    err_code = "FILE_WRITE_ERROR" if create_parents else "FILE_READ_ERROR"
    try:
        dfd = os.open("/", dir_flags)
    except OSError as exc:
        raise oracle.MdlRosenError(err_code, f"{label}: cannot open root ({exc})") from exc
    try:
        for part in parent_parts:
            if part == ".":
                continue
            try:
                next_fd = os.open(part, dir_flags, dir_fd=dfd)
            except OSError as exc:
                if create_parents and exc.errno == errno.ENOENT:
                    try:
                        os.mkdir(part, 0o755, dir_fd=dfd)
                    except FileExistsError:
                        pass
                    except OSError as mk_exc:
                        raise oracle.MdlRosenError("FILE_WRITE_ERROR", f"{label}: mkdir failed ({mk_exc})") from mk_exc
                    try:
                        next_fd = os.open(part, dir_flags, dir_fd=dfd)
                    except OSError as reopen_exc:
                        raise oracle.MdlRosenError(
                            "FILE_WRITE_ERROR", f"{label}: cannot open created dir ({reopen_exc})"
                        ) from reopen_exc
                elif exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    try:
                        is_lnk = stat.S_ISLNK(os.lstat(part, dir_fd=dfd).st_mode)
                    except OSError:
                        is_lnk = exc.errno == errno.ELOOP
                    if is_lnk:
                        raise oracle.MdlRosenError("SYMLINK_FORBIDDEN", f"{label}: symlink component forbidden") from exc
                    raise oracle.MdlRosenError(err_code, f"{label}: non-directory ancestor ({exc})") from exc
                else:
                    raise oracle.MdlRosenError(err_code, f"{label}: cannot open ancestor ({exc})") from exc
            os.close(dfd)
            dfd = next_fd
        return dfd, leaf
    except BaseException:
        os.close(dfd)
        raise


def read_regular_bytes_capped(path: Path, label: str, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    """Read regular file bytes under strict cap using atomic dir_fd openat O_NOFOLLOW|O_NONBLOCK + fstat S_ISREG."""
    target = _require_concrete_path(path, label)
    oracle.require_exact_int(max_bytes, "max_bytes", lo=1, hi=MAX_ALLOWED_CAP_BYTES)
    dfd, leaf = _open_dir_chain(target, label, create_parents=False)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        try:
            fd = os.open(leaf, flags, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise oracle.MdlRosenError("SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden") from exc
            raise oracle.MdlRosenError("FILE_READ_ERROR", f"{label}: cannot open ({exc})") from exc
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
    except oracle.MdlRosenError:
        raise
    except OSError as exc:
        raise oracle.MdlRosenError("FILE_READ_ERROR", f"{label}: read failed ({exc})") from exc
    finally:
        os.close(fd)
    oracle.require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"{label}: exceeds {max_bytes} bytes")
    return b"".join(chunks)


def write_regular_bytes_safe(path: Path, payload: bytes, label: str) -> None:
    """Write bytes atomically via dir_fd O_CREAT|O_EXCL|O_NOFOLLOW + fsync + os.replace + dir fsync."""
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
            raise oracle.MdlRosenError("FILE_WRITE_ERROR", f"{label}: stat failed ({exc})") from exc
        if st_existing is not None:
            oracle.require_ok(not stat.S_ISLNK(st_existing.st_mode), "SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden")
            oracle.require_ok(stat.S_ISREG(st_existing.st_mode), "NOT_A_REGULAR_FILE", f"{label}: non-regular target")
            oracle.require_ok(st_existing.st_nlink <= 1, "HARDLINK_FORBIDDEN", f"{label}: hardlinked target forbidden")
        pid = os.getpid()
        for _ in range(64):
            with _TEMP_NAME_LOCK:
                cand = f".s34.{pid}.{secrets.token_hex(8)}.tmp"
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
                raise oracle.MdlRosenError("FILE_WRITE_ERROR", f"{label}: create temp failed ({exc})") from exc
        else:
            raise oracle.MdlRosenError("FILE_WRITE_ERROR", f"{label}: exhausted temp file slots")
        try:
            view = memoryview(payload)
            written = 0
            while written < len(view):
                written += os.write(fd, view[written:])
            os.fsync(fd)
            st_tmp = os.fstat(fd)
            oracle.require_ok(st_tmp.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: temp file link count altered")
        except OSError as exc:
            raise oracle.MdlRosenError("FILE_WRITE_ERROR", f"{label}: write failed ({exc})") from exc
        finally:
            os.close(fd)
        try:
            os.replace(tmp_name, leaf, src_dir_fd=dfd, dst_dir_fd=dfd)
            tmp_name = None
            os.fsync(dfd)
        except OSError as exc:
            raise oracle.MdlRosenError("FILE_WRITE_ERROR", f"{label}: atomic replace failed ({exc})") from exc
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
        os.close(dfd)


def require_hex64_lower_ascii(val: Any, label: str) -> str:
    oracle.require_ok(
        type(val) is str and len(val) == 64,
        "INVALID_HEX64",
        f"{label}: expected 64-char lowercase ASCII hex",
    )
    for ch in val:
        oracle.require_ok(ch in _HEX_LOWER, "INVALID_HEX64", f"{label}: non-hex-lowercase character")
    return val


def _parse_bounded_int(token: str) -> int:
    """Strict ASCII-only 0-9 signed integer parser (zero .isdigit(), zero bare ValueError)."""
    oracle.require_ok(type(token) is str, "INVALID_JSON_INT", "JSON int token must be exact str")
    oracle.require_ok(token != "-0", "INVALID_JSON_INT", "negative zero forbidden")
    digits = token[1:] if token.startswith("-") else token
    oracle.require_ok(len(digits) >= 1, "INVALID_JSON_INT", "JSON int token has no digits")
    oracle.require_ok(len(digits) <= MAX_JSON_INT_DIGITS, "INT_DIGIT_LIMIT", "JSON int exceeds digit cap")
    oracle.require_ok(digits == "0" or not digits.startswith("0"), "INVALID_JSON_INT", "leading zero forbidden")
    for ch in digits:
        oracle.require_ok(ch in _ASCII_DIGITS, "INVALID_JSON_INT", "JSON int token must contain ASCII digits 0-9 only")
    return int(token)


def parse_exact_rational(token: Any, label: str = "rational") -> Fraction:
    """Strict ASCII-only canonical exact rational parser for 'n' or reduced 'n/d' (d >= 2)."""
    oracle.require_ok(type(token) is str, "INVALID_RATIONAL", f"{label}: rational token must be exact str")
    parts = token.split("/")
    oracle.require_ok(len(parts) in (1, 2), "INVALID_RATIONAL", f"{label}: expected 'n' or 'n/d'")
    num_s = parts[0]
    oracle.require_ok(num_s != "-0", "INVALID_RATIONAL", f"{label}: negative zero forbidden")
    num_digits = num_s[1:] if num_s.startswith("-") else num_s
    oracle.require_ok(len(num_digits) >= 1, "INVALID_RATIONAL", f"{label}: empty numerator")
    oracle.require_ok(len(num_digits) <= MAX_JSON_INT_DIGITS, "INVALID_RATIONAL", f"{label}: numerator too long")
    oracle.require_ok(num_digits == "0" or not num_digits.startswith("0"), "INVALID_RATIONAL", f"{label}: leading zero")
    for ch in num_digits:
        oracle.require_ok(ch in _ASCII_DIGITS, "INVALID_RATIONAL", f"{label}: non-ASCII digit in numerator")
    num = int(num_s)
    if len(parts) == 1:
        return Fraction(num, 1)
    den_s = parts[1]
    oracle.require_ok(len(den_s) >= 1, "INVALID_RATIONAL", f"{label}: empty denominator")
    oracle.require_ok(len(den_s) <= MAX_JSON_INT_DIGITS, "INVALID_RATIONAL", f"{label}: denominator too long")
    oracle.require_ok(not den_s.startswith("0"), "INVALID_RATIONAL", f"{label}: leading zero in denominator")
    for ch in den_s:
        oracle.require_ok(ch in _ASCII_DIGITS, "INVALID_RATIONAL", f"{label}: non-ASCII digit in denominator")
    den = int(den_s)
    oracle.require_ok(den >= 2, "INVALID_RATIONAL", f"{label}: denominator must be >= 2")
    oracle.require_ok(math.gcd(num, den) == 1, "INVALID_RATIONAL", f"{label}: non-reduced rational forbidden")
    return Fraction(num, den)


def _reject_dup_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        oracle.require_ok(k not in out, "DUPLICATE_JSON_KEY", f"duplicate key {k!r}")
        out[k] = v
    return out


def _reject_nonfinite(token: str) -> Any:
    raise oracle.MdlRosenError("NONFINITE_JSON", f"non-finite JSON constant {token!r}")


def _reject_float(token: str) -> Any:
    raise oracle.MdlRosenError("FLOAT_FORBIDDEN", f"JSON float token forbidden: {token!r}")


def _validate_json_tree(root: Any, label: str) -> None:
    stack: list[tuple[Any, int]] = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        oracle.require_ok(depth <= MAX_JSON_DEPTH, "MAX_DEPTH_EXCEEDED", f"{label}: depth > {MAX_JSON_DEPTH}")
        t = type(node)
        if t is str:
            oracle.require_ok("\x00" not in node, "NUL_BYTE_FORBIDDEN", f"{label}: NUL byte in string")
            _require_utf8_no_surrogate(node, label)
        elif t is dict:
            for k, v in node.items():
                oracle.require_ok(type(k) is str, "INVALID_JSON_KEY", f"{label}: dict keys must be exact str")
                stack.append((k, depth + 1))
                stack.append((v, depth + 1))
        elif t is list:
            for item in node:
                stack.append((item, depth + 1))
        elif t is int:
            oracle.require_ok(
                node.bit_length() <= oracle.MAX_JSON_INT_BITS,
                "INT_BIT_LIMIT",
                f"{label}: integer exceeds {oracle.MAX_JSON_INT_BITS} bits",
            )
        elif t is bool or node is None:
            pass
        else:
            raise oracle.MdlRosenError("INVALID_JSON_VALUE", f"{label}: unsupported type {t.__name__}")


def parse_strict_json_text(text: str, label: str, *, require_object: bool = True) -> Any:
    oracle.require_ok(type(text) is str, "INVALID_JSON_TEXT", f"{label}: text must be exact str")
    oracle.require_exact_bool(require_object, "require_object")
    oracle.require_ok(not text.startswith("\ufeff"), "BOM_FORBIDDEN", f"{label}: UTF-8 BOM forbidden")
    oracle.require_ok("\x00" not in text, "NUL_BYTE_FORBIDDEN", f"{label}: NUL byte forbidden")
    _require_utf8_no_surrogate(text, label)
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_reject_dup_keys,
            parse_int=_parse_bounded_int,
            parse_constant=_reject_nonfinite,
            parse_float=_reject_float,
        )
    except oracle.MdlRosenError:
        raise
    except (ValueError, RecursionError) as exc:
        raise oracle.MdlRosenError("INVALID_JSON", f"{label}: {exc}") from exc
    if require_object:
        oracle.require_ok(type(parsed) is dict, "JSON_ROOT_NOT_OBJECT", f"{label}: JSON root must be dict")
    _validate_json_tree(parsed, label)
    return parsed


def canonical_json_bytes(obj: Any) -> bytes:
    _validate_json_tree(obj, "canonical_json")
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")


def build_certificate() -> dict[str, Any]:
    payload = oracle.compute_s34_payload()
    payload_sha = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    envelope = {
        "schema_version": oracle.SCHEMA_VERSION,
        "track_id": oracle.TRACK_ID,
        "payload_sha256": payload_sha,
        "payload": payload,
    }
    cert_sha = hashlib.sha256(canonical_json_bytes(envelope)).hexdigest()
    return {
        "schema_version": oracle.SCHEMA_VERSION,
        "track_id": oracle.TRACK_ID,
        "payload_sha256": payload_sha,
        "certificate_sha256": cert_sha,
        "payload": payload,
    }


def _req_dict(obj: Any, label: str) -> dict[str, Any]:
    oracle.require_ok(type(obj) is dict, "SECONDARY_AUDIT_SCHEMA_ERROR", f"{label}: expected exact dict")
    return obj


def _req_list(obj: Any, label: str) -> list[Any]:
    oracle.require_ok(type(obj) is list, "SECONDARY_AUDIT_SCHEMA_ERROR", f"{label}: expected exact list")
    return obj


def _req_key(d: dict[str, Any], key: str, label: str) -> Any:
    oracle.require_ok(key in d, "SECONDARY_AUDIT_SCHEMA_ERROR", f"{label}: missing key {key!r}")
    return d[key]


def _req_int(val: Any, label: str) -> int:
    return oracle.require_exact_int(val, label)


def _req_int_fields(d: dict[str, Any], keys: tuple[str, ...], label: str) -> None:
    for k in keys:
        _req_int(_req_key(d, k, label), f"{label}.{k}")


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Schema-safe fail-closed exact-int secondary algebraic cross-check on ANY crafted payload."""
    pl = _req_dict(payload, "payload")
    p1 = _req_dict(_req_key(pl, "pillar1_mdl_prequential_requential", "payload"), "p1")
    p2 = _req_dict(_req_key(pl, "pillar2_siliquant_mdl_pareto", "payload"), "p2")
    p3 = _req_dict(_req_key(pl, "pillar3_rosen_similarity_bifurcation", "payload"), "p3")
    p4 = _req_dict(_req_key(pl, "pillar4_mdl_blindness_misfolding", "payload"), "p4")
    p5 = _req_dict(_req_key(pl, "pillar5_cs20_extrapolation_gate", "payload"), "p5")

    # Pillar 1 algebraic & exact-int checks
    _req_int_fields(
        p1,
        (
            "alphabet_size",
            "stream_length_T",
            "L_uniform_bits",
            "L_theta_T_bits",
            "L_online_raw_bits",
            "cumulative_regret_R_bits",
            "overhead_c_bits",
        ),
        "p1",
    )
    p1_tw = _req_dict(_req_key(p1, "three_way_separation", "p1"), "p1.three_way_separation")
    _req_int(_req_key(p1_tw, "steps_T", "p1_tw"), "p1_tw.steps_T")
    req_delta = parse_exact_rational(_req_key(p1_tw, "requential_kl_delta_bits", "p1_tw"), "requential_kl_delta_bits")
    preq_delta = parse_exact_rational(_req_key(p1_tw, "prequential_delta_bits", "p1_tw"), "prequential_delta_bits")
    p1_regimes = _req_list(_req_key(p1, "offline_vs_online_regimes", "p1"), "p1.regimes")
    regimes_ok = len(p1_regimes) == 3
    for idx, reg in enumerate(p1_regimes):
        rd = _req_dict(reg, f"p1.regimes[{idx}]")
        _req_int_fields(
            rd,
            ("b_theta_bits", "regret_R_bits", "L_offline_bits", "L_online_bits", "L_diff_bits", "cancellation_residual"),
            f"p1.regimes[{idx}]",
        )
        if rd["cancellation_residual"] != 0:
            regimes_ok = False
    p1_hc = _req_list(_req_key(p1, "hardcode_no_profit_checks", "p1"), "p1.hardcode")
    for idx, item in enumerate(p1_hc):
        hd = _req_dict(item, f"p1.hardcode[{idx}]")
        _req_int_fields(
            hd,
            ("T", "L_uniform_bits", "L_hardcode_zero_overhead", "L_hardcode_with_decoder"),
            f"p1.hardcode[{idx}]",
        )
    p1_reuse = _req_list(_req_key(p1, "reuse_threshold_checks", "p1"), "p1.reuse")
    for idx, item in enumerate(p1_reuse):
        ru = _req_dict(item, f"p1.reuse[{idx}]")
        _req_int_fields(ru, ("reuse_count_m", "net_saving_bits"), f"p1.reuse[{idx}]")

    # Pillar 2 algebraic & exact-int checks
    _req_int_fields(p2, ("active_weights_N", "active_matrices"), "p2")
    p2_prov = _req_dict(_req_key(p2, "source_provenance", "p2"), "p2.provenance")
    require_hex64_lower_ascii(_req_key(p2_prov, "source_file_sha256", "p2.provenance"), "source_file_sha256")
    p2_par = _req_dict(_req_key(p2, "pareto_EBG128_vs_Q4_K_M", "p2"), "p2.pareto")
    d_wiki = parse_exact_rational(_req_key(p2_par, "delta_kl_wiki_q", "p2_par"), "delta_kl_wiki_q")
    d_py = parse_exact_rational(_req_key(p2_par, "delta_kl_py_q", "p2_par"), "delta_kl_py_q")
    p2_law = _req_dict(_req_key(p2, "log_convex_bitrate_law", "p2"), "p2.law")

    # Pillar 3 algebraic & exact-int checks
    p3_crit = _req_dict(_req_key(p3, "vdw_critical_point_1_1_1", "p3"), "p3.crit")
    p3_vdw = _req_dict(_req_key(p3, "vdw_phase_discriminants", "p3"), "p3.vdw")
    p3_cusp = _req_dict(_req_key(p3, "cusp_normal_form_obstruction", "p3"), "p3.cusp")
    vdw_super = parse_exact_rational(_req_key(p3_vdw, "supercritical_Pr1_Tr2", "p3_vdw"), "supercritical_Pr1_Tr2")
    vdw_sub = parse_exact_rational(_req_key(p3_vdw, "subcritical_Pr_half_Tr_7_8", "p3_vdw"), "subcritical_Pr_half_Tr_7_8")
    p3_c_sup = _req_dict(_req_key(p3_cusp, "supercritical_a1_b0", "p3_cusp"), "p3.cusp.super")
    p3_c_sup2 = _req_dict(_req_key(p3_cusp, "supercritical_a2_b3", "p3_cusp"), "p3.cusp.super2")
    p3_f_pos = _req_dict(_req_key(p3_cusp, "fold_a_neg3_b_pos2", "p3_cusp"), "p3.cusp.fpos")
    p3_f_neg = _req_dict(_req_key(p3_cusp, "fold_a_neg3_b_neg2", "p3_cusp"), "p3.cusp.fneg")
    p3_c_mul = _req_dict(_req_key(p3_cusp, "multi_phase_a_neg4_b0", "p3_cusp"), "p3.cusp.multi")
    p3_c_mul2 = _req_dict(_req_key(p3_cusp, "multi_phase_a_neg7_b6", "p3_cusp"), "p3.cusp.multi2")
    sup_roots = _req_int(_req_key(p3_c_sup, "sturm_real_roots", "p3_c_sup"), "p3_c_sup.sturm_real_roots")
    _req_int(_req_key(p3_c_sup2, "sturm_real_roots", "p3_c_sup2"), "p3_c_sup2.sturm_real_roots")
    _req_int(_req_key(p3_f_pos, "double_root_x", "p3_f_pos"), "p3_f_pos.double_root_x")
    _req_int(_req_key(p3_f_neg, "double_root_x", "p3_f_neg"), "p3_f_neg.double_root_x")
    mul_roots = _req_int(_req_key(p3_c_mul, "sturm_real_roots", "p3_c_mul"), "p3_c_mul.sturm_real_roots")
    _req_int(_req_key(p3_c_mul2, "sturm_real_roots", "p3_c_mul2"), "p3_c_mul2.sturm_real_roots")
    for m_lbl, m_dict in (("p3_c_mul", p3_c_mul), ("p3_c_mul2", p3_c_mul2)):
        for r_idx, rv in enumerate(_req_list(_req_key(m_dict, "explicit_roots", m_lbl), f"{m_lbl}.roots")):
            _req_int(rv, f"{m_lbl}.explicit_roots[{r_idx}]")

    # Pillar 4 algebraic & exact-int checks
    _req_int_fields(
        p4,
        (
            "vocab_rows",
            "hidden_dim",
            "total_model_weights",
            "base_model_bits",
            "patch_description_bits",
            "control_queries_checked",
            "control_queries_identical",
            "control_delta_L_theta_bits",
            "trigger_argmax_W0",
            "trigger_argmax_W1",
        ),
        "p4",
    )
    rel_mdl = parse_exact_rational(_req_key(p4, "relative_model_bit_overhead_q", "p4"), "relative_model_bit_overhead_q")
    ctrl_kl = parse_exact_rational(_req_key(p4, "control_requential_kl_bits", "p4"), "control_requential_kl_bits")
    trig_def = parse_exact_rational(_req_key(p4, "trigger_rosen_commutation_l1_defect", "p4"), "trigger_l1_defect")
    dpi_ratio = parse_exact_rational(_req_key(p4, "dpi_separation_ratio", "p4"), "dpi_separation_ratio")

    # Pillar 5 algebraic & exact-int checks
    _req_int_fields(p5, ("clean_within_phase_pairs_checked", "cross_boundary_witnesses_checked"), "p5")
    p5_clean = _req_list(_req_key(p5, "clean_within_phase_results", "p5"), "p5.clean")
    p5_deny = _req_list(_req_key(p5, "cross_boundary_witness_results", "p5"), "p5.deny")
    p5_clean_ok = len(p5_clean) == 3
    for idx, item in enumerate(p5_clean):
        it = _req_dict(item, f"p5.clean[{idx}]")
        if _req_key(it, "verdict", f"p5.clean[{idx}]") != "ALLOW_EXTRAPOLATION":
            p5_clean_ok = False
    p5_deny_ok = len(p5_deny) == 5
    for idx, item in enumerate(p5_deny):
        it = _req_dict(item, f"p5.deny[{idx}]")
        if _req_key(it, "verdict", f"p5.deny[{idx}]") != "DENY_PHASE_BIFURCATION":
            p5_deny_ok = False

    ok_all = all(
        (
            _req_key(pl, "all_pillars_verified", "payload") is True,
            _req_key(p1, "all_verified", "p1") is True,
            _req_key(p2, "all_verified", "p2") is True,
            _req_key(p3, "all_verified", "p3") is True,
            _req_key(p4, "all_verified", "p4") is True,
            _req_key(p5, "all_verified", "p5") is True,
            regimes_ok,
            req_delta == 0,
            preq_delta > 0,
            d_wiki < 0,
            d_py < 0,
            _req_key(p2_par, "strict_pareto_dominance_all_T_ge_0", "p2_par") is True,
            _req_key(p2_law, "strictly_convex", "p2_law") is True,
            _req_key(p2_law, "first_order_optimality_all_certified", "p2_law") is True,
            _req_key(p3_crit, "exact_triple_root", "p3_crit") is True,
            vdw_super < 0,
            vdw_sub > 0,
            sup_roots == 1,
            mul_roots == 3,
            rel_mdl <= Fraction(1, 1_000),
            ctrl_kl == 0,
            trig_def > 0,
            dpi_ratio >= Fraction(32, 1),
            p5_clean_ok,
            p5_deny_ok,
        )
    )
    oracle.require_ok(ok_all, "SECONDARY_AUDIT_FAILED", "secondary algebraic cross-check failed")
    return {"secondary_audit_passed": True}


def verify_certificate_dict(
    cert: Any,
    *,
    expected: dict[str, Any] | None = None,
    full_replay: bool = True,
) -> dict[str, Any]:
    """Fail-closed in-memory certificate verifier (schema + self-consistent SHA-256 + secondary audit + optional full pure-Q replay)."""
    oracle.require_exact_bool(full_replay, "full_replay")
    oracle.require_ok(type(cert) is dict, "INVALID_CERT_TYPE", "certificate must be exact dict")
    oracle.require_ok(set(cert.keys()) == _CERT_KEYS, "INVALID_CERT_KEYS", "unexpected or missing cert keys")
    _validate_json_tree(cert, "cert")
    oracle.require_ok(cert["schema_version"] == oracle.SCHEMA_VERSION, "INVALID_SCHEMA_VERSION", "schema_version mismatch")
    oracle.require_ok(cert["track_id"] == oracle.TRACK_ID, "INVALID_TRACK_ID", "track_id mismatch")
    got_psha = require_hex64_lower_ascii(cert["payload_sha256"], "payload_sha256")
    got_csha = require_hex64_lower_ascii(cert["certificate_sha256"], "certificate_sha256")
    calc_psha = hashlib.sha256(canonical_json_bytes(cert["payload"])).hexdigest()
    oracle.require_ok(
        hmac.compare_digest(got_psha, calc_psha),
        "PAYLOAD_SHA_MISMATCH",
        "payload_sha256 does not match payload",
    )
    envelope = {
        "schema_version": cert["schema_version"],
        "track_id": cert["track_id"],
        "payload_sha256": got_psha,
        "payload": cert["payload"],
    }
    calc_csha = hashlib.sha256(canonical_json_bytes(envelope)).hexdigest()
    oracle.require_ok(
        hmac.compare_digest(got_csha, calc_csha),
        "CERTIFICATE_SHA_MISMATCH",
        "certificate_sha256 does not match envelope",
    )
    secondary_audit_payload(cert["payload"])
    if full_replay:
        exp = build_certificate() if expected is None else expected
        oracle.require_ok(
            hmac.compare_digest(canonical_json_bytes(cert), canonical_json_bytes(exp)),
            "CERTIFICATE_MISMATCH",
            "certificate does not match freshly computed exact oracle output",
        )
    return {
        "valid": True,
        "payload_sha256": got_psha,
        "certificate_sha256": got_csha,
    }


def verify_certificate_file(cert_path: Path) -> dict[str, Any]:
    """Fail-closed file certificate verifier (atomic dir_fd read + LF-only canonical bytes + replay)."""
    raw = read_regular_bytes_capped(cert_path, "certificate")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise oracle.MdlRosenError("INVALID_UTF8", f"certificate: invalid UTF-8 ({exc})") from exc
    oracle.require_ok("\r" not in text, "CRLF_FORBIDDEN", "certificate: CRLF line endings forbidden")
    parsed = parse_strict_json_text(text, "certificate", require_object=True)
    expected = build_certificate()
    res = verify_certificate_dict(parsed, expected=expected)
    oracle.require_ok(
        hmac.compare_digest(raw, canonical_json_bytes(expected)),
        "CERTIFICATE_BYTE_MISMATCH",
        "certificate bytes are non-canonical",
    )
    return res


def _validate_cli_argv(argv: Any) -> list[str]:
    oracle.require_ok(type(argv) is list, "INVALID_ARGV", "argv must be exact list")
    for item in argv:
        oracle.require_ok(type(item) is str, "INVALID_ARGV", "argv entries must be exact str")
        oracle.require_ok("\x00" not in item, "NUL_BYTE_FORBIDDEN", "NUL byte forbidden in argv")
        _require_utf8_no_surrogate(item, "argv")
    return argv


def _validate_cli_path_arg(arg: str, flag: str) -> Path:
    oracle.require_ok(
        len(arg) > 0 and not arg.startswith("-"),
        "INVALID_PATH_ARG",
        f"{flag}: path argument must be non-empty and must not start with '-'",
    )
    return Path(arg)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _validate_cli_argv(list(sys.argv[1:]) if argv is None else argv)
        if args in ([], ["--standalone", "--json"]):
            cert = build_certificate()
            sys.stdout.write(canonical_json_bytes(cert).decode("ascii"))
            return 0
        if len(args) == 2 and args[0] == "--write":
            out_path = _validate_cli_path_arg(args[1], "--write")
            cert = build_certificate()
            raw = canonical_json_bytes(cert)
            write_regular_bytes_safe(out_path, raw, "--write")
            summary = {
                "written": True,
                "file_sha256": hashlib.sha256(raw).hexdigest(),
                "payload_sha256": cert["payload_sha256"],
                "certificate_sha256": cert["certificate_sha256"],
            }
            sys.stdout.write(canonical_json_bytes(summary).decode("ascii"))
            return 0
        if len(args) == 2 and args[0] == "--check":
            cert_path = _validate_cli_path_arg(args[1], "--check")
            res = verify_certificate_file(cert_path)
            sys.stdout.write(canonical_json_bytes(res).decode("ascii"))
            return 0
        raise oracle.MdlRosenError(
            "INVALID_CLI_ARGS",
            "usage: mdl_rosen_similarity_audit.py [--standalone --json | --write <path> | --check <path>]",
        )
    except oracle.MdlRosenError as exc:
        err_obj = {"valid": False, "error_code": exc.code, "detail": exc.detail}
        sys.stderr.write(canonical_json_bytes(err_obj).decode("ascii"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
