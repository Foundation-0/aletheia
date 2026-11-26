#!/usr/bin/env python3
"""Zone-B Hardened Standalone CLI, Replay & Secondary Auditor for Track S61.

100% pure Python 3 stdlib, zero IEEE-754 floats, zero bare asserts, zero .isdigit(),
zero mathematical RNG (secrets.token_hex used strictly for atomic temp filename uniqueness).
"""
from __future__ import annotations

import errno
from fractions import Fraction
import hmac
import json
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

import rapl_landauer_oracle as oracle  # noqa: E402

MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_ALLOWED_CAP_BYTES = 64 * 1024 * 1024
_READ_CHUNK_BYTES = 65_536
MAX_JSON_DEPTH = 64
MAX_JSON_INT_DIGITS = oracle.MAX_INT_DIGITS
MAX_JSON_INT_BITS = oracle.MAX_INT_BITS
_EXACT_PATH_TYPES = (Path, type(Path()))
_ASCII_DIGITS = frozenset("0123456789")
_CERT_KEYS = frozenset({"schema_version", "track_id", "payload_sha256", "certificate_sha256", "payload"})
_PAYLOAD_KEYS = frozenset({
    "schema_version",
    "track_id",
    "measured_live_silicon",
    "privacy_locks",
    "snapshot_sha256",
    "x_anonymous_sha256",
    "microkernels_c_sha256",
    "mlos_receipt_sha256",
    "pillar1_step_algebra",
    "pillar2_regime_physics_and_landauer",
    "pillar3_blind_schur_tomography",
})
_P2_KEYS = frozenset({"per_regime", "landauer_r2_bridge", "pairwise_contrasts"})
_REGIME_ROW_KEYS = frozenset({
    "idx", "id", "n_samples", "total_dt_us", "wall_ns", "total_ops",
    "total_erased_bits", "total_toggle_bits",
    "pkg_w_q", "pkg_w_dec3", "core_w_q", "core_w_dec3", "uncore_w_q", "uncore_w_dec3",
    "psys_w_q", "psys_w_dec3", "mmio_w_q", "mmio_w_dec3",
    "pkg_in_package_dark_w_q", "pkg_in_package_dark_w_dec3",
    "psys_minus_pkg_w_q", "psys_minus_pkg_w_dec3",
    "pkg_minus_mmio_w_q", "pkg_minus_mmio_w_dec3",
    "mean_temp_pkg_k_q", "mean_temp_pkg_k_dec3",
    "mean_freq_mhz_q", "mean_freq_mhz_dec1",
    "mean_fan_cpu_rpm_dec1", "mean_fan_gpu_rpm_dec1",
    "ops_per_sec_dec0", "pkg_pj_per_op_q", "pkg_pj_per_op_dec4",
    "core_pj_per_op_q", "core_pj_per_op_dec4",
})
_LANDAUER_KEYS = frozenset({
    "r2_temp_pkg_k_q", "r2_temp_pkg_k_dec3", "r2_erased_bits",
    "r2_core_j_dec6", "r2_pkg_j_dec6",
    "eta_gross_core_floor_int", "eta_gross_core_ceil_int",
    "eta_gross_pkg_floor_int", "eta_gross_pkg_ceil_int",
    "eta_net_core_floor_int", "eta_net_core_ceil_int",
    "r2_pkg_landauer_bits_lo", "r2_pkg_landauer_bits_hi",
    "h1_cmos_landauer_obstruction_confirmed",
})
_CONTRAST_KEYS = frozenset({
    "perm_reps",
    "r2_minus_r1_core_w_q", "r2_minus_r1_core_w_dec3", "p_r2_vs_r1_core_q",
    "r3_minus_r1_core_w_q", "r3_minus_r1_core_w_dec3", "p_r3_vs_r1_core_q",
    "r4_minus_r1_core_w_q", "r4_minus_r1_core_w_dec3", "p_r4_vs_r1_core_q",
    "r4_minus_r1_freq_mhz_q", "r4_minus_r1_freq_mhz_dec1",
    "r5_minus_r4_core_w_q", "r5_minus_r4_core_w_dec3",
    "r4_fp64_over_r5_vnni_pj_per_op_q", "r4_fp64_over_r5_vnni_pj_per_op_dec3",
    "r6_minus_r1_uncore_w_q", "r6_minus_r1_uncore_w_dec3", "p_r6_vs_r1_uncore_q",
    "r6_minus_r1_pkg_dark_w_q", "r6_minus_r1_pkg_dark_w_dec3", "p_r6_vs_r1_pkg_dark_q",
    "r6_minus_r4_pkg_dark_w_q", "r6_minus_r4_pkg_dark_w_dec3", "p_r6_vs_r4_pkg_dark_q",
    "r6_minus_r1_psys_w_q", "r6_minus_r1_psys_w_dec3", "p_r6_vs_r1_psys_q",
    "psys_vendor_scale_obstruction_detected",
})
_P3_KEYS = frozenset({
    "n_rows", "n_cols", "active_indices", "zero_var_indices",
    "mean_offdiag_r2_q", "mean_offdiag_r2_dec4",
    "psys_vs_pkg_r2_q", "psys_vs_pkg_r2_dec4",
    "uncore_vs_pkg_r2_q", "uncore_vs_pkg_r2_dec4",
    "blind_r2_threshold_q", "blind_cluster_labels", "blind_cluster_count",
    "blind_modularity_q", "blind_modularity_dec4",
    "blind_rapl_best_cluster_id", "blind_rapl_precision_q", "blind_rapl_recall_q",
    "physical_partition_schur", "stage_a_gauge_invariance", "circular_shift_null",
})
_SCHUR_KEYS = frozenset({
    "ridge_lambda_q", "a_active_positions", "b_active_positions", "inertia",
    "mean_unexplained_variance_eta_q", "mean_unexplained_variance_eta_dec4",
    "mean_raw_offdiag_r2_q", "mean_raw_offdiag_r2_dec4",
    "mean_residual_rho2_q", "mean_residual_rho2_dec4",
})
_GAUGE_KEYS = frozenset({
    "exact_zero_deviation", "max_r2_diff_q", "eta_diff_q", "res_rho2_diff_q",
    "blind_cluster_gauge_ari_q", "inertia_exact_match",
})
_CIRC_KEYS = frozenset({"reps", "ge_count", "p_mean_offdiag_r2_q", "p_mean_offdiag_r2_dec4"})

_TEMP_NAME_LOCK = threading.Lock()
_TEMP_SEQ = 0
_DIR_OPEN_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_DARWIN_SYSTEM_ROOT_ALIASES: tuple[tuple[str, str], ...] = (
    ("/var", "/private/var"),
    ("/tmp", "/private/tmp"),
    ("/etc", "/private/etc"),
)


# ---------------------------------------------------------------------------
# Zone-B Path, Darwin Alias Normalization, CWD, Atomic dir_fd & Atomic Write
# ---------------------------------------------------------------------------

def _require_utf8_no_surrogate(text: Any, label: str) -> str:
    if type(text) is not str:
        raise oracle.RaplLandauerError("INVALID_STR", f"{label}: exact str required")
    try:
        text.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise oracle.RaplLandauerError("INVALID_UTF8_SURROGATE", f"{label}: lone UTF-16 surrogate forbidden") from exc
    return text


def _require_concrete_path(path: Any, label: str) -> Path:
    oracle.require_ok(
        type(path) in _EXACT_PATH_TYPES,
        "INVALID_PATH_TYPE",
        f"{label}: concrete pathlib.Path required",
    )
    raw_s = _require_utf8_no_surrogate(str(path), label)
    oracle.require_ok("\x00" not in raw_s, "NUL_BYTE_FORBIDDEN", f"{label}: NUL byte forbidden")
    return path


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


def _safe_cwd(label: str) -> Path:
    try:
        return Path.cwd()
    except OSError as exc:
        raise oracle.RaplLandauerError("CWD_UNAVAILABLE", f"{label}: CWD unavailable ({type(exc).__name__})") from exc


def _check_pwd_no_symlinks(label: str) -> None:
    pwd = os.environ.get("PWD", "")
    if pwd.startswith("/"):
        _require_utf8_no_surrogate(pwd, f"{label} PWD")
        pwd_path = _normalize_darwin_system_prefix(Path(pwd), allow_exact=True)
        try:
            pwd_st = os.stat(pwd_path)
            cwd_st = os.stat(".")
        except (OSError, ValueError):
            return
        if (pwd_st.st_dev, pwd_st.st_ino) != (cwd_st.st_dev, cwd_st.st_ino):
            return
        try:
            dfd = os.open("/", _DIR_OPEN_FLAGS)
        except OSError as exc:
            raise oracle.RaplLandauerError("CWD_UNAVAILABLE", f"{label}: cannot open root for PWD") from exc
        try:
            for part in pwd_path.parts[1:]:
                if part == ".":
                    continue
                try:
                    next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
                except OSError as exc:
                    if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                        raise oracle.RaplLandauerError(
                            "SYMLINK_ANCESTOR_FORBIDDEN", f"{label}: symlink PWD ancestor forbidden"
                        ) from exc
                    raise oracle.RaplLandauerError(
                        "CWD_UNAVAILABLE", f"{label}: PWD ancestor unavailable ({type(exc).__name__})"
                    ) from exc
                os.close(dfd)
                dfd = next_fd
        finally:
            os.close(dfd)


def _open_dir_chain(target: Path, label: str, *, create_parents: bool) -> tuple[int, str]:
    """Open ancestor directory chain atomically via dir_fd + O_DIRECTORY | O_NOFOLLOW."""
    if target.is_absolute():
        parts = _normalize_darwin_system_prefix(target).parts[1:]
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
        raise oracle.RaplLandauerError(err_code, f"{label}: cannot open root") from exc
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
                        raise oracle.RaplLandauerError(
                            "FILE_WRITE_ERROR", f"{label}: mkdir failed ({type(mk_exc).__name__})"
                        ) from mk_exc
                    try:
                        next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
                    except OSError as re_exc:
                        raise oracle.RaplLandauerError(
                            "FILE_WRITE_ERROR", f"{label}: cannot open created dir ({type(re_exc).__name__})"
                        ) from re_exc
                elif exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise oracle.RaplLandauerError(
                        "SYMLINK_FORBIDDEN", f"{label}: symlink or non-directory ancestor forbidden"
                    ) from exc
                else:
                    raise oracle.RaplLandauerError(
                        err_code, f"{label}: cannot traverse ancestor ({type(exc).__name__})"
                    ) from exc
            os.close(dfd)
            dfd = next_fd
        return dfd, leaf
    except BaseException:
        os.close(dfd)
        raise


def read_regular_bytes_capped(path: Path, label: str = "file", max_bytes: int = MAX_JSON_BYTES) -> bytes:
    """Read regular non-hardlinked file bytes under strict cap using atomic dir_fd openat + 64 KiB chunks."""
    target = _require_concrete_path(path, label)
    oracle.require_exact_int(max_bytes, "max_bytes", lo=1, hi=MAX_ALLOWED_CAP_BYTES)
    dfd, leaf = _open_dir_chain(target, label, create_parents=False)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        try:
            fd = os.open(leaf, flags, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise oracle.RaplLandauerError("SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden") from exc
            raise oracle.RaplLandauerError("FILE_READ_ERROR", f"{label}: cannot open ({type(exc).__name__})") from exc
    finally:
        os.close(dfd)

    chunks: list[bytes] = []
    total = 0
    try:
        st_f = os.fstat(fd)
        oracle.require_ok(stat.S_ISREG(st_f.st_mode), "NOT_A_REGULAR_FILE", f"{label}: not a regular file")
        oracle.require_ok(st_f.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: hardlinked file forbidden")
        oracle.require_ok(st_f.st_size <= max_bytes, "FILE_TOO_LARGE", f"{label}: size exceeds {max_bytes} bytes")
        while total <= max_bytes:
            chunk = os.read(fd, min(_READ_CHUNK_BYTES, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    except oracle.RaplLandauerError:
        raise
    except OSError as exc:
        raise oracle.RaplLandauerError("FILE_READ_ERROR", f"{label}: read failed ({type(exc).__name__})") from exc
    finally:
        os.close(fd)
    oracle.require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"{label}: exceeds {max_bytes} bytes")
    return b"".join(chunks)


def write_regular_bytes_safe(path: Path, payload: bytes, label: str = "output") -> None:
    """Atomic dir_fd write: 0o600 temp, lock+seq+CSPRNG+EEXIST retry, fsync, st_nlink==1, os.replace, dir fsync."""
    global _TEMP_SEQ
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
            raise oracle.RaplLandauerError("FILE_WRITE_ERROR", f"{label}: lstat failed ({type(exc).__name__})") from exc
        if st_existing is not None:
            oracle.require_ok(not stat.S_ISLNK(st_existing.st_mode), "SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden")
            oracle.require_ok(stat.S_ISREG(st_existing.st_mode), "NOT_A_REGULAR_FILE", f"{label}: non-regular target")
            oracle.require_ok(st_existing.st_nlink <= 1, "HARDLINK_FORBIDDEN", f"{label}: hardlinked target forbidden")

        pid = os.getpid()
        for _ in range(64):
            with _TEMP_NAME_LOCK:
                _TEMP_SEQ += 1
                seq_num = _TEMP_SEQ
                cand = f".s61.{pid}.{seq_num}.{secrets.token_hex(8)}.tmp"
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
                raise oracle.RaplLandauerError(
                    "FILE_WRITE_ERROR", f"{label}: create temp failed ({type(exc).__name__})"
                ) from exc
        else:
            raise oracle.RaplLandauerError("FILE_WRITE_ERROR", f"{label}: exhausted temp file slots")

        try:
            view = memoryview(payload)
            written = 0
            while written < len(view):
                n_written = os.write(fd, view[written:])
                oracle.require_ok(n_written > 0, "FILE_WRITE_ERROR", f"{label}: short write returned 0")
                written += n_written
            os.fsync(fd)
            st_tmp = os.fstat(fd)
            oracle.require_ok(st_tmp.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: temp link count altered")
        except oracle.RaplLandauerError:
            raise
        except OSError as exc:
            raise oracle.RaplLandauerError("FILE_WRITE_ERROR", f"{label}: write failed ({type(exc).__name__})") from exc
        finally:
            os.close(fd)

        try:
            os.replace(tmp_name, leaf, src_dir_fd=dfd, dst_dir_fd=dfd)
            tmp_name = None
            os.fsync(dfd)
        except OSError as exc:
            raise oracle.RaplLandauerError("FILE_WRITE_ERROR", f"{label}: atomic replace failed ({type(exc).__name__})") from exc
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
        os.close(dfd)


# ---------------------------------------------------------------------------
# Strict ASCII Parsers, Iterative Tree Validation & Canonical JSON
# ---------------------------------------------------------------------------

def _is_ascii_digits(s: str) -> bool:
    if len(s) == 0:
        return False
    for ch in s:
        if ch not in _ASCII_DIGITS:
            return False
    return True


def _parse_bounded_int(token: str) -> int:
    s = _require_utf8_no_surrogate(token, "json_int")
    neg = s.startswith("-")
    body = s[1:] if neg else s
    oracle.require_ok(_is_ascii_digits(body), "INVALID_JSON_INT", f"non-ASCII digits in {s!r}")
    if neg:
        oracle.require_ok(body != "0", "INVALID_JSON_INT", "negative zero integer forbidden")
    if len(body) > 1:
        oracle.require_ok(body[0] != "0", "INVALID_JSON_INT", "leading zero integer forbidden")
    oracle.require_ok(len(body) <= MAX_JSON_INT_DIGITS, "INT_DIGIT_LIMIT", f"exceeds {MAX_JSON_INT_DIGITS} digits")
    val = int(s)
    oracle.require_ok(abs(val).bit_length() <= MAX_JSON_INT_BITS, "INT_BIT_LIMIT", f"exceeds {MAX_JSON_INT_BITS} bits")
    return val


def parse_canonical_rational_str(val: Any, label: str = "rational") -> Fraction:
    s = oracle.require_str(val, label, non_empty=True)
    if "/" in s:
        parts = s.split("/")
        oracle.require_ok(len(parts) == 2, "INVALID_RATIONAL_STR", f"{label}: malformed fraction {s!r}")
        num_s, den_s = parts[0], parts[1]
        num = _parse_bounded_int(num_s)
        oracle.require_ok(_is_ascii_digits(den_s) and den_s[0] != "0", "INVALID_RATIONAL_STR", f"{label}: bad denominator")
        den = _parse_bounded_int(den_s)
        q = Fraction(num, den)
        oracle.require_ok(oracle.format_rational(q) == s, "NON_CANONICAL_RATIONAL", f"{label}: fraction not reduced")
        return q
    num = _parse_bounded_int(s)
    return Fraction(num, 1)


def _reject_json_float(token: str) -> Any:
    raise oracle.RaplLandauerError("FORBIDDEN_JSON_FLOAT", f"JSON float literal forbidden: {token!r}")


def _reject_json_constant(token: str) -> Any:
    raise oracle.RaplLandauerError("FORBIDDEN_JSON_CONSTANT", f"JSON constant forbidden: {token!r}")


def _strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        _require_utf8_no_surrogate(k, "json_key")
        oracle.require_ok(k not in out, "DUPLICATE_JSON_KEY", f"duplicate JSON key: {k!r}")
        out[k] = v
    return out


def _validate_json_tree(root: Any, label: str = "json") -> None:
    """Iterative depth-bounded exact-type JSON tree validator (delegates to oracle)."""
    oracle.validate_strict_json_tree(root, label)


def _parse_canonical_decimal_str(val: Any, places: int, label: str) -> Fraction:
    """Parse canonical fixed-point ASCII decimal string with exact `places` fractional digits."""
    s = oracle.require_str(val, label, non_empty=True)
    if places == 0:
        return Fraction(_parse_bounded_int(s), 1)
    neg = s.startswith("-")
    body = s[1:] if neg else s
    parts = body.split(".")
    oracle.require_ok(len(parts) == 2, "INVALID_DECIMAL_STR", f"{label}: expected decimal point")
    whole_s, frac_s = parts[0], parts[1]
    oracle.require_ok(
        _is_ascii_digits(whole_s) and _is_ascii_digits(frac_s) and len(frac_s) == places,
        "INVALID_DECIMAL_STR",
        f"{label}: malformed decimal digits",
    )
    if len(whole_s) > 1:
        oracle.require_ok(whole_s[0] != "0", "INVALID_DECIMAL_STR", f"{label}: leading zero forbidden")
    scaled = int(whole_s + frac_s)
    if neg:
        oracle.require_ok(scaled != 0, "INVALID_DECIMAL_STR", f"{label}: negative zero forbidden")
        scaled = -scaled
    return Fraction(scaled, 10**places)


def _require_decimal_in_interval(
    val: Any,
    lo_q: Fraction,
    hi_q: Fraction,
    places: int,
    label: str,
) -> Fraction:
    d = _parse_canonical_decimal_str(val, places, label)
    lo_d = _parse_canonical_decimal_str(oracle.format_decimal(lo_q, places), places, label)
    hi_d = _parse_canonical_decimal_str(oracle.format_decimal(hi_q, places), places, label)
    oracle.require_ok(lo_d <= d <= hi_d, "DECIMAL_MISMATCH", f"{label}: {val!r} outside [{lo_d}, {hi_d}]")
    return d


def _require_dec_matches_floor_q(val: Any, q_val: Fraction, q_pow10: int, places: int, label: str) -> Fraction:
    return _require_decimal_in_interval(val, q_val, q_val + Fraction(1, 10**q_pow10), places, label)


def _require_landauer_bracket(
    lo_i: int,
    hi_i: int,
    e_lo: Fraction,
    e_hi: Fraction,
    d_min: Fraction,
    d_max: Fraction,
    label: str,
) -> None:
    min_f = int(e_lo // d_max)
    max_f = int(e_hi // d_min)
    oracle.require_ok(
        lo_i < hi_i and min_f <= lo_i <= max_f and min_f + 1 <= hi_i <= max_f + 1,
        "LANDAUER_BRACKET_INVALID",
        f"{label}: Landauer bracket [{lo_i}, {hi_i}] outside [{min_f}, {max_f + 1}]",
    )


def parse_strict_json_bytes(raw: bytes, label: str = "json", *, require_canonical: bool = True) -> dict[str, Any]:
    """Parse canonical LF-terminated ASCII JSON with zero floats, zero duplicates, exact depth/int bounds."""
    oracle.require_ok(type(raw) is bytes and len(raw) > 0, "EMPTY_FILE", f"{label}: empty input")
    oracle.require_ok(b"\r" not in raw, "CRLF_FORBIDDEN", f"{label}: CR/CRLF forbidden")
    oracle.require_ok(raw.endswith(b"\n"), "MISSING_TRAILING_LF", f"{label}: trailing LF required")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise oracle.RaplLandauerError("INVALID_UTF8", f"{label}: invalid UTF-8") from exc
    try:
        parsed = json.loads(
            text,
            parse_int=_parse_bounded_int,
            parse_float=_reject_json_float,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_strict_object_pairs,
        )
    except oracle.RaplLandauerError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise oracle.RaplLandauerError("JSON_PARSE_ERROR", f"{label}: invalid JSON ({type(exc).__name__})") from exc
    oracle.require_ok(type(parsed) is dict, "INVALID_JSON_ROOT", f"{label}: root must be exact dict")
    _validate_json_tree(parsed, label)
    if require_canonical:
        expected = oracle.canonical_json_bytes(parsed)
        oracle.require_ok(expected == raw, "NON_CANONICAL_BYTES", f"{label}: non-canonical JSON framing")
    return parsed


# ---------------------------------------------------------------------------
# Independent Secondary Payload Audit & Full Certificate Verification
# ---------------------------------------------------------------------------

def _require_exact_dict_keys(obj: Any, expected: frozenset[str], label: str) -> dict[str, Any]:
    oracle.require_ok(type(obj) is dict, "INVALID_SCHEMA_DICT", f"{label}: exact dict required")
    oracle.require_ok(frozenset(obj.keys()) == expected, "INVALID_SCHEMA_KEYS", f"{label}: keyset mismatch")
    return obj


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Fail-closed structural & algebraic audit of Track S61 payload (safe for direct calls)."""
    oracle.require_ok(type(payload) is dict, "INVALID_PAYLOAD_TYPE", "payload must be exact dict")
    _validate_json_tree(payload, "payload")
    oracle.require_ok(frozenset(payload.keys()) == _PAYLOAD_KEYS, "INVALID_SCHEMA_KEYS", "payload keyset mismatch")
    oracle.require_ok(payload["schema_version"] == oracle.SCHEMA_VERSION, "SCHEMA_VALUE_MISMATCH", "schema_version")
    oracle.require_ok(payload["track_id"] == oracle.TRACK_ID, "SCHEMA_VALUE_MISMATCH", "track_id")
    oracle.require_ok(payload["measured_live_silicon"] is True, "SCHEMA_VALUE_MISMATCH", "measured_live_silicon")

    pl = _require_exact_dict_keys(
        payload["privacy_locks"],
        frozenset({"audio_capture_accessed", "camera_accessed", "display_modified"}),
        "privacy_locks",
    )
    oracle.require_ok(
        pl["audio_capture_accessed"] is False
        and pl["camera_accessed"] is False
        and pl["display_modified"] is False,
        "PRIVACY_LOCK_VIOLATION",
        "privacy_locks must all be exact False",
    )
    for dk in ("snapshot_sha256", "x_anonymous_sha256", "microkernels_c_sha256", "mlos_receipt_sha256"):
        oracle.require_hex64(payload[dk], dk)

    # Pillar 1 exact replay check
    p1 = payload["pillar1_step_algebra"]
    oracle.require_ok(type(p1) is dict, "INVALID_SCHEMA_DICT", "pillar1 must be exact dict")
    expected_p1 = oracle.prove_step_algebra()
    oracle.require_ok(
        oracle.canonical_json_bytes(p1) == oracle.canonical_json_bytes(expected_p1),
        "PILLAR1_MISMATCH",
        "pillar1_step_algebra does not match exact pure-Z proof",
    )

    # Pillar 2 schema, conservation, decimal parity, and SI-2019 Landauer cross-checks
    p2 = _require_exact_dict_keys(payload["pillar2_regime_physics_and_landauer"], _P2_KEYS, "pillar2")
    per_reg = p2["per_regime"]
    oracle.require_ok(type(per_reg) is list and len(per_reg) == 7, "INVALID_SCHEMA_LIST", "per_regime must have 7 items")
    reg_pkg: list[Fraction] = []
    reg_core: list[Fraction] = []
    reg_unc: list[Fraction] = []
    reg_psys: list[Fraction] = []
    reg_dark: list[Fraction] = []
    reg_temp: list[Fraction] = []
    reg_freq: list[Fraction] = []
    reg_core_pj: list[Fraction] = []
    tol_q = Fraction(3, 10**6)
    eps6 = Fraction(1, 10**6)
    for idx, row in enumerate(per_reg):
        _require_exact_dict_keys(row, _REGIME_ROW_KEYS, f"regime[{idx}]")
        oracle.require_exact_int(row["idx"], f"regime[{idx}].idx", lo=idx, hi=idx)
        oracle.require_ok(row["id"] == oracle.EXPECTED_REGIME_IDS[idx], "SCHEMA_VALUE_MISMATCH", f"regime[{idx}].id")
        oracle.require_exact_int(row["n_samples"], f"regime[{idx}].n_samples", lo=1, hi=2048)
        oracle.require_exact_int(row["total_dt_us"], f"regime[{idx}].total_dt_us", lo=1)
        wall_ns = oracle.require_exact_int(row["wall_ns"], f"regime[{idx}].wall_ns", lo=1)
        total_ops = oracle.require_exact_int(row["total_ops"], f"regime[{idx}].total_ops", lo=0)
        erased_bits = oracle.require_exact_int(row["total_erased_bits"], f"regime[{idx}].total_erased_bits", lo=0)
        toggle_bits = oracle.require_exact_int(row["total_toggle_bits"], f"regime[{idx}].total_toggle_bits", lo=0)
        if idx == 0:
            oracle.require_ok(
                total_ops == 0 and erased_bits == 0 and toggle_bits == 0,
                "REGIME_INVARIANT_MISMATCH",
                "R0_IDLE must have zero ops/erased/toggle bits",
            )
        else:
            oracle.require_ok(total_ops > 0, "REGIME_INVARIANT_MISMATCH", f"regime[{idx}] total_ops must be > 0")
            if idx == 2:
                oracle.require_ok(erased_bits > 0 and toggle_bits > 0, "REGIME_INVARIANT_MISMATCH", "R2 must erase and toggle bits")
            else:
                oracle.require_ok(erased_bits == 0, "REGIME_INVARIANT_MISMATCH", f"regime[{idx}] erased_bits must be 0")
                if idx in (1, 3):
                    oracle.require_ok(toggle_bits > 0, "REGIME_INVARIANT_MISMATCH", f"regime[{idx}] toggle_bits must be > 0")
                else:
                    oracle.require_ok(toggle_bits == 0, "REGIME_INVARIANT_MISMATCH", f"regime[{idx}] toggle_bits must be 0")

        pkg_w = parse_canonical_rational_str(row["pkg_w_q"], "pkg_w_q")
        core_w = parse_canonical_rational_str(row["core_w_q"], "core_w_q")
        unc_w = parse_canonical_rational_str(row["uncore_w_q"], "uncore_w_q")
        psys_w = parse_canonical_rational_str(row["psys_w_q"], "psys_w_q")
        mmio_w = parse_canonical_rational_str(row["mmio_w_q"], "mmio_w_q")
        dark_w = parse_canonical_rational_str(row["pkg_in_package_dark_w_q"], "pkg_in_package_dark_w_q")
        psys_diff = parse_canonical_rational_str(row["psys_minus_pkg_w_q"], "psys_minus_pkg_w_q")
        mmio_diff = parse_canonical_rational_str(row["pkg_minus_mmio_w_q"], "pkg_minus_mmio_w_q")
        t_k = parse_canonical_rational_str(row["mean_temp_pkg_k_q"], "mean_temp_pkg_k_q")
        freq_mhz = parse_canonical_rational_str(row["mean_freq_mhz_q"], "mean_freq_mhz_q")
        pkg_pj = parse_canonical_rational_str(row["pkg_pj_per_op_q"], "pkg_pj_per_op_q")
        core_pj = parse_canonical_rational_str(row["core_pj_per_op_q"], "core_pj_per_op_q")

        oracle.require_ok(pkg_w >= 0 and core_w >= 0 and unc_w >= 0 and psys_w >= 0 and mmio_w >= 0, "NEGATIVE_POWER", "negative RAPL power")
        oracle.require_ok(t_k >= Fraction(273, 1) and t_k <= Fraction(420, 1), "INVALID_TEMP_RANGE", "temperature out of silicon range")
        oracle.require_ok(freq_mhz > 0, "INVALID_FREQ", "frequency must be > 0")
        # Conservation tolerance <= 3e-6 W from 10^-6 floor quantization of 3 terms
        oracle.require_ok(abs((pkg_w - core_w - unc_w) - dark_w) <= tol_q, "CONSERVATION_MISMATCH", "pkg_dark mismatch")
        oracle.require_ok(abs((psys_w - pkg_w) - psys_diff) <= tol_q, "CONSERVATION_MISMATCH", "psys_minus_pkg mismatch")
        oracle.require_ok(abs((pkg_w - mmio_w) - mmio_diff) <= tol_q, "CONSERVATION_MISMATCH", "pkg_minus_mmio mismatch")

        for dec_k, q_v, qp, pl in (
            ("pkg_w_dec3", pkg_w, 6, 3),
            ("core_w_dec3", core_w, 6, 3),
            ("uncore_w_dec3", unc_w, 6, 3),
            ("psys_w_dec3", psys_w, 6, 3),
            ("mmio_w_dec3", mmio_w, 6, 3),
            ("pkg_in_package_dark_w_dec3", dark_w, 6, 3),
            ("psys_minus_pkg_w_dec3", psys_diff, 6, 3),
            ("pkg_minus_mmio_w_dec3", mmio_diff, 6, 3),
            ("mean_temp_pkg_k_dec3", t_k, 4, 3),
            ("mean_freq_mhz_dec1", freq_mhz, 3, 1),
        ):
            _require_dec_matches_floor_q(row[dec_k], q_v, qp, pl, f"regime[{idx}].{dec_k}")
        for fan_k in ("mean_fan_cpu_rpm_dec1", "mean_fan_gpu_rpm_dec1"):
            fan_q = _parse_canonical_decimal_str(row[fan_k], 1, f"regime[{idx}].{fan_k}")
            oracle.require_ok(Fraction(0, 1) <= fan_q <= Fraction(15_000, 1), "INVALID_FAN_RPM", f"regime[{idx}].{fan_k}")

        if total_ops == 0:
            oracle.require_ok(
                row["ops_per_sec_dec0"] == "0"
                and pkg_pj == 0
                and core_pj == 0
                and row["pkg_pj_per_op_dec4"] == "0.0000"
                and row["core_pj_per_op_dec4"] == "0.0000",
                "ENERGY_PER_OP_MISMATCH",
                "R0_IDLE ops/s and pJ/op must be zero",
            )
        else:
            ops_s = Fraction(total_ops * 10**9, wall_ns)
            oracle.require_ok(
                row["ops_per_sec_dec0"] == oracle.format_decimal(ops_s, 0),
                "DECIMAL_MISMATCH",
                f"regime[{idx}].ops_per_sec_dec0",
            )
            for pj_q, w_q, pj_dec_k in (
                (pkg_pj, pkg_w, "pkg_pj_per_op_dec4"),
                (core_pj, core_w, "core_pj_per_op_dec4"),
            ):
                pj_lo = (w_q / ops_s) * 10**12
                pj_hi = ((w_q + eps6) / ops_s) * 10**12
                oracle.require_ok(
                    oracle.q_quantize_floor(pj_lo, 6) <= pj_q <= oracle.q_quantize_floor(pj_hi, 6),
                    "ENERGY_PER_OP_MISMATCH",
                    f"regime[{idx}].{pj_dec_k}",
                )
                _require_decimal_in_interval(row[pj_dec_k], pj_lo, pj_hi, 4, f"regime[{idx}].{pj_dec_k}")

        reg_pkg.append(pkg_w)
        reg_core.append(core_w)
        reg_unc.append(unc_w)
        reg_psys.append(psys_w)
        reg_dark.append(dark_w)
        reg_temp.append(t_k)
        reg_freq.append(freq_mhz)
        reg_core_pj.append(core_pj)

    lb = _require_exact_dict_keys(p2["landauer_r2_bridge"], _LANDAUER_KEYS, "landauer")
    oracle.require_ok(
        lb["r2_temp_pkg_k_q"] == per_reg[2]["mean_temp_pkg_k_q"]
        and lb["r2_temp_pkg_k_dec3"] == per_reg[2]["mean_temp_pkg_k_dec3"],
        "LANDAUER_TEMP_MISMATCH",
        "r2_temp_pkg_k must match per_regime[2]",
    )
    r2_er = oracle.require_exact_int(lb["r2_erased_bits"], "r2_erased_bits", lo=1)
    oracle.require_ok(r2_er == per_reg[2]["total_erased_bits"], "LANDAUER_ERASED_MISMATCH", "erased bits")
    egc_lo = oracle.require_exact_int(lb["eta_gross_core_floor_int"], "eta_gross_core_floor_int", lo=0)
    egc_hi = oracle.require_exact_int(lb["eta_gross_core_ceil_int"], "eta_gross_core_ceil_int", lo=1)
    egp_lo = oracle.require_exact_int(lb["eta_gross_pkg_floor_int"], "eta_gross_pkg_floor_int", lo=0)
    egp_hi = oracle.require_exact_int(lb["eta_gross_pkg_ceil_int"], "eta_gross_pkg_ceil_int", lo=1)
    enc_lo = oracle.require_exact_int(lb["eta_net_core_floor_int"], "eta_net_core_floor_int", lo=0)
    enc_hi = oracle.require_exact_int(lb["eta_net_core_ceil_int"], "eta_net_core_ceil_int", lo=1)
    bits_lo = oracle.require_exact_int(lb["r2_pkg_landauer_bits_lo"], "r2_pkg_landauer_bits_lo", lo=0)
    bits_hi = oracle.require_exact_int(lb["r2_pkg_landauer_bits_hi"], "r2_pkg_landauer_bits_hi", lo=1)

    r2_wall_s = Fraction(per_reg[2]["wall_ns"], 10**9)
    c_j_lo, c_j_hi = reg_core[2] * r2_wall_s, (reg_core[2] + eps6) * r2_wall_s
    p_j_lo, p_j_hi = reg_pkg[2] * r2_wall_s, (reg_pkg[2] + eps6) * r2_wall_s
    _require_decimal_in_interval(lb["r2_core_j_dec6"], c_j_lo, c_j_hi, 6, "r2_core_j_dec6")
    _require_decimal_in_interval(lb["r2_pkg_j_dec6"], p_j_lo, p_j_hi, 6, "r2_pkg_j_dec6")
    kt_min = oracle.KB_SI_2019_Q * reg_temp[2] * oracle.LN2_LO_Q
    kt_max = oracle.KB_SI_2019_Q * (reg_temp[2] + Fraction(1, 10**4)) * oracle.LN2_HI_Q
    nc_w_lo = max(Fraction(0, 1), reg_core[2] - reg_core[0] - eps6)
    nc_w_hi = max(Fraction(0, 1), reg_core[2] + eps6 - reg_core[0])
    _require_landauer_bracket(egc_lo, egc_hi, c_j_lo, c_j_hi, r2_er * kt_min, r2_er * kt_max, "eta_gross_core")
    _require_landauer_bracket(egp_lo, egp_hi, p_j_lo, p_j_hi, r2_er * kt_min, r2_er * kt_max, "eta_gross_pkg")
    _require_landauer_bracket(enc_lo, enc_hi, nc_w_lo * r2_wall_s, nc_w_hi * r2_wall_s, r2_er * kt_min, r2_er * kt_max, "eta_net_core")
    _require_landauer_bracket(bits_lo, bits_hi, p_j_lo, p_j_hi, kt_min, kt_max, "r2_pkg_landauer_bits")
    h1_ok = oracle.require_bool(lb["h1_cmos_landauer_obstruction_confirmed"], "h1_cmos_landauer_obstruction_confirmed")
    oracle.require_ok(h1_ok == (egc_lo >= 10**6), "LANDAUER_H1_FLAG_MISMATCH", "H1 boolean mismatch")

    pc = _require_exact_dict_keys(p2["pairwise_contrasts"], _CONTRAST_KEYS, "contrasts")
    oracle.require_exact_int(pc["perm_reps"], "perm_reps", lo=oracle.PERM_TEST_REPS, hi=oracle.PERM_TEST_REPS)
    perm_grid = 1 + oracle.PERM_TEST_REPS
    for pk in (
        "p_r2_vs_r1_core_q", "p_r3_vs_r1_core_q", "p_r4_vs_r1_core_q",
        "p_r6_vs_r1_uncore_q", "p_r6_vs_r1_pkg_dark_q", "p_r6_vs_r4_pkg_dark_q", "p_r6_vs_r1_psys_q",
    ):
        pv = parse_canonical_rational_str(pc[pk], pk)
        oracle.require_ok(
            Fraction(1, perm_grid) <= pv <= Fraction(1, 1) and (pv * perm_grid).denominator == 1,
            "INVALID_PVALUE",
            pk,
        )
    for qk, dk, exp_diff, c_tol, qp, pl in (
        ("r2_minus_r1_core_w_q", "r2_minus_r1_core_w_dec3", reg_core[2] - reg_core[1], tol_q, 6, 3),
        ("r3_minus_r1_core_w_q", "r3_minus_r1_core_w_dec3", reg_core[3] - reg_core[1], tol_q, 6, 3),
        ("r4_minus_r1_core_w_q", "r4_minus_r1_core_w_dec3", reg_core[4] - reg_core[1], tol_q, 6, 3),
        ("r4_minus_r1_freq_mhz_q", "r4_minus_r1_freq_mhz_dec1", reg_freq[4] - reg_freq[1], Fraction(3, 10**3), 3, 1),
        ("r5_minus_r4_core_w_q", "r5_minus_r4_core_w_dec3", reg_core[5] - reg_core[4], tol_q, 6, 3),
        ("r6_minus_r1_uncore_w_q", "r6_minus_r1_uncore_w_dec3", reg_unc[6] - reg_unc[1], tol_q, 6, 3),
        ("r6_minus_r1_pkg_dark_w_q", "r6_minus_r1_pkg_dark_w_dec3", reg_dark[6] - reg_dark[1], tol_q, 6, 3),
        ("r6_minus_r4_pkg_dark_w_q", "r6_minus_r4_pkg_dark_w_dec3", reg_dark[6] - reg_dark[4], tol_q, 6, 3),
        ("r6_minus_r1_psys_w_q", "r6_minus_r1_psys_w_dec3", reg_psys[6] - reg_psys[1], tol_q, 6, 3),
    ):
        dv = parse_canonical_rational_str(pc[qk], qk)
        oracle.require_ok(abs(dv - exp_diff) <= c_tol, "CONTRAST_MISMATCH", qk)
        _require_dec_matches_floor_q(pc[dk], dv, qp, pl, dk)
    ratio_q = parse_canonical_rational_str(pc["r4_fp64_over_r5_vnni_pj_per_op_q"], "r4_fp64_over_r5_vnni_pj_per_op_q")
    oracle.require_ok(reg_core_pj[5] > 0, "CONTRAST_MISMATCH", "R5 core pJ/op must be > 0")
    rat_lo = reg_core_pj[4] / (reg_core_pj[5] + eps6)
    rat_hi = (reg_core_pj[4] + eps6) / reg_core_pj[5]
    oracle.require_ok(
        oracle.q_quantize_floor(rat_lo, 6) <= ratio_q <= oracle.q_quantize_floor(rat_hi, 6),
        "CONTRAST_MISMATCH",
        "r4_fp64_over_r5_vnni_pj_per_op_q",
    )
    _require_decimal_in_interval(pc["r4_fp64_over_r5_vnni_pj_per_op_dec3"], rat_lo, rat_hi, 3, "r4_fp64_over_r5_vnni_pj_per_op_dec3")
    psys_obs = oracle.require_bool(pc["psys_vendor_scale_obstruction_detected"], "psys_vendor_scale_obstruction_detected")
    oracle.require_ok(psys_obs == (reg_psys[4] < reg_pkg[4]), "PSYS_FLAG_MISMATCH", "psys scale flag mismatch")

    # Pillar 3 schema, Schur bounds, exact Stage-A 0-diff gauge invariance, and circular-shift null
    p3 = _require_exact_dict_keys(payload["pillar3_blind_schur_tomography"], _P3_KEYS, "pillar3")
    oracle.require_exact_int(p3["n_rows"], "n_rows", lo=21, hi=2048)
    oracle.require_exact_int(p3["n_cols"], "n_cols", lo=20, hi=20)
    act = p3["active_indices"]
    zvar = p3["zero_var_indices"]
    oracle.require_ok(type(act) is list and type(zvar) is list, "INVALID_SCHEMA_LIST", "active/zero_var lists")
    for idx_v in act:
        oracle.require_exact_int(idx_v, "active_idx", lo=0, hi=19)
    for idx_v in zvar:
        oracle.require_exact_int(idx_v, "zero_var_idx", lo=0, hi=19)
    oracle.require_ok(
        len(set(act)) == len(act)
        and len(set(zvar)) == len(zvar)
        and set(act).isdisjoint(set(zvar))
        and set(act) | set(zvar) == set(range(20)),
        "PARTITION_MISMATCH",
        "active + zero_var must partition 0..19",
    )
    p3_r2: dict[str, Fraction] = {}
    for rk in ("mean_offdiag_r2_q", "psys_vs_pkg_r2_q", "uncore_vs_pkg_r2_q", "blind_rapl_precision_q", "blind_rapl_recall_q"):
        rv = parse_canonical_rational_str(p3[rk], rk)
        oracle.require_ok(Fraction(0, 1) <= rv <= Fraction(1, 1), "R2_OUT_OF_RANGE", rk)
        p3_r2[rk] = rv
    for qk, dk in (
        ("mean_offdiag_r2_q", "mean_offdiag_r2_dec4"),
        ("psys_vs_pkg_r2_q", "psys_vs_pkg_r2_dec4"),
        ("uncore_vs_pkg_r2_q", "uncore_vs_pkg_r2_dec4"),
    ):
        _require_dec_matches_floor_q(p3[dk], p3_r2[qk], 6, 4, dk)
    oracle.require_ok(
        parse_canonical_rational_str(p3["blind_r2_threshold_q"], "blind_r2_threshold_q") == oracle.BLIND_R2_EDGE_THRESHOLD_Q,
        "SCHEMA_VALUE_MISMATCH",
        "blind_r2_threshold_q",
    )
    blbl = p3["blind_cluster_labels"]
    oracle.require_ok(type(blbl) is list and len(blbl) == len(act), "INVALID_SCHEMA_LIST", "blind_cluster_labels")
    for c_v in blbl:
        oracle.require_exact_int(c_v, "blind_lbl", lo=0, hi=19)
    uniq_blbl = set(blbl)
    oracle.require_ok(uniq_blbl == set(range(len(uniq_blbl))), "INVALID_CLUSTER_IDS", "blind cluster labels must be 0..k-1")
    oracle.require_exact_int(p3["blind_cluster_count"], "blind_cluster_count", lo=len(uniq_blbl), hi=len(uniq_blbl))
    mod_q = parse_canonical_rational_str(p3["blind_modularity_q"], "blind_modularity_q")
    oracle.require_ok(Fraction(-1, 2) <= mod_q <= Fraction(1, 1), "R2_OUT_OF_RANGE", "blind_modularity_q")
    _require_dec_matches_floor_q(p3["blind_modularity_dec4"], mod_q, 6, 4, "blind_modularity_dec4")
    best_cid = oracle.require_exact_int(p3["blind_rapl_best_cluster_id"], "blind_rapl_best_cluster_id", lo=0, hi=len(uniq_blbl) - 1)

    sp = _require_exact_dict_keys(p3["physical_partition_schur"], _SCHUR_KEYS, "schur")
    oracle.require_ok(
        parse_canonical_rational_str(sp["ridge_lambda_q"], "ridge_lambda_q") == oracle.SCHUR_RIDGE_LAMBDA_Q,
        "SCHEMA_VALUE_MISMATCH",
        "ridge_lambda_q",
    )
    a_pos = sp["a_active_positions"]
    b_pos = sp["b_active_positions"]
    oracle.require_ok(type(a_pos) is list and type(b_pos) is list and len(a_pos) >= 2 and len(b_pos) >= 1, "INVALID_SCHEMA_LIST", "schur a/b")
    for v in a_pos:
        oracle.require_exact_int(v, "a_pos", lo=0, hi=len(act) - 1)
    for v in b_pos:
        oracle.require_exact_int(v, "b_pos", lo=0, hi=len(act) - 1)
    oracle.require_ok(
        len(set(a_pos)) == len(a_pos)
        and len(set(b_pos)) == len(b_pos)
        and set(a_pos).isdisjoint(set(b_pos))
        and set(a_pos) | set(b_pos) == set(range(len(act))),
        "PARTITION_MISMATCH",
        "schur a/b must partition active positions without duplicates",
    )
    best_size = sum(1 for c in blbl if c == best_cid)
    inter_p = p3_r2["blind_rapl_precision_q"] * best_size
    inter_r = p3_r2["blind_rapl_recall_q"] * len(b_pos)
    oracle.require_ok(
        inter_p == inter_r and inter_p.denominator == 1,
        "BLIND_CLUSTER_CONSISTENCY",
        "blind RAPL precision/recall inconsistent with cluster size and |B|",
    )
    iner = sp["inertia"]
    oracle.require_ok(type(iner) is list and len(iner) == 3, "INVALID_SCHEMA_LIST", "inertia len 3")
    for iv in iner:
        oracle.require_exact_int(iv, "inertia_elem", lo=0, hi=len(a_pos))
    oracle.require_ok(iner == [len(a_pos), 0, 0], "INERTIA_SUM_MISMATCH", "SPD Schur inertia must equal [|A|, 0, 0]")
    for sk, dk in (
        ("mean_unexplained_variance_eta_q", "mean_unexplained_variance_eta_dec4"),
        ("mean_raw_offdiag_r2_q", "mean_raw_offdiag_r2_dec4"),
        ("mean_residual_rho2_q", "mean_residual_rho2_dec4"),
    ):
        sv = parse_canonical_rational_str(sp[sk], sk)
        oracle.require_ok(Fraction(0, 1) <= sv <= Fraction(1, 1), "SCHUR_OUT_OF_RANGE", sk)
        _require_dec_matches_floor_q(sp[dk], sv, 6, 4, dk)

    gi = _require_exact_dict_keys(p3["stage_a_gauge_invariance"], _GAUGE_KEYS, "gauge")
    oracle.require_ok(
        gi["exact_zero_deviation"] is True
        and gi["inertia_exact_match"] is True
        and gi["max_r2_diff_q"] == "0"
        and gi["eta_diff_q"] == "0"
        and gi["res_rho2_diff_q"] == "0"
        and gi["blind_cluster_gauge_ari_q"] == "1",
        "GAUGE_INVARIANCE_BROKEN",
        "Stage-A gauge invariance must be exact zero deviation",
    )

    cn = _require_exact_dict_keys(p3["circular_shift_null"], _CIRC_KEYS, "circ")
    oracle.require_exact_int(cn["reps"], "circ_reps", lo=oracle.CIRC_SHIFT_REPS, hi=oracle.CIRC_SHIFT_REPS)
    ge_c = oracle.require_exact_int(cn["ge_count"], "ge_count", lo=0, hi=oracle.CIRC_SHIFT_REPS)
    cp = parse_canonical_rational_str(cn["p_mean_offdiag_r2_q"], "p_mean_offdiag_r2_q")
    oracle.require_ok(cp == Fraction(1 + ge_c, 1 + oracle.CIRC_SHIFT_REPS), "CIRC_PVALUE_MISMATCH", "p != (1+ge)/(1+reps)")
    oracle.require_ok(
        cn["p_mean_offdiag_r2_dec4"] == oracle.format_decimal(cp, 4),
        "DECIMAL_MISMATCH",
        "p_mean_offdiag_r2_dec4",
    )

    return {
        "secondary_audit_passed": True,
        "regimes_checked": 7,
        "active_channels": len(act),
        "h1_cmos_landauer_obstruction_confirmed": h1_ok,
        "stage_a_gauge_exact_zero": True,
    }


def _load_default_snapshot_and_receipt() -> tuple[dict[str, Any], str]:
    base = Path(_THIS_DIR)
    snap_path = base / "rapl_landauer_snapshot.json"
    snap_raw = read_regular_bytes_capped(snap_path, "snapshot")
    snap_obj = parse_strict_json_bytes(snap_raw, "snapshot", require_canonical=True)
    receipt_path = base / "mlos_zone_b_receipt.json"
    rec_raw = read_regular_bytes_capped(receipt_path, "mlos_receipt")
    rec_sha = oracle.sha256_hex(rec_raw)
    return snap_obj, rec_sha


def verify_certificate_dict(
    cert: Any,
    *,
    full_replay: bool = True,
    snapshot: dict[str, Any] | None = None,
    mlos_receipt_sha256: str | None = None,
) -> dict[str, Any]:
    """Fail-closed verifier for Track S61 certificates (supports full_replay=True/False)."""
    oracle.require_bool(full_replay, "full_replay")
    oracle.require_ok(type(cert) is dict, "INVALID_CERT_TYPE", "certificate must be exact dict")
    _validate_json_tree(cert, "certificate")
    oracle.require_ok(frozenset(cert.keys()) == _CERT_KEYS, "INVALID_CERT_KEYS", "certificate keyset mismatch")
    oracle.require_ok(cert["schema_version"] == oracle.SCHEMA_VERSION, "SCHEMA_VALUE_MISMATCH", "cert schema_version")
    oracle.require_ok(cert["track_id"] == oracle.TRACK_ID, "SCHEMA_VALUE_MISMATCH", "cert track_id")

    p_sha = oracle.require_hex64(cert["payload_sha256"], "payload_sha256")
    c_sha = oracle.require_hex64(cert["certificate_sha256"], "certificate_sha256")
    payload = cert["payload"]
    sec_res = secondary_audit_payload(payload)

    recomputed_p_sha = oracle.sha256_hex(oracle.canonical_json_bytes(payload))
    oracle.require_ok(hmac.compare_digest(p_sha, recomputed_p_sha), "PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")

    env_body = {
        "schema_version": cert["schema_version"],
        "track_id": cert["track_id"],
        "payload_sha256": p_sha,
        "payload": payload,
    }
    recomputed_c_sha = oracle.sha256_hex(oracle.canonical_json_bytes(env_body))
    oracle.require_ok(hmac.compare_digest(c_sha, recomputed_c_sha), "CERT_SHA_MISMATCH", "certificate_sha256 mismatch")

    replayed = False
    if full_replay:
        if snapshot is None:
            snapshot, rec_sha = _load_default_snapshot_and_receipt()
            use_rec_sha = mlos_receipt_sha256 if mlos_receipt_sha256 is not None else rec_sha
        else:
            use_rec_sha = mlos_receipt_sha256 if mlos_receipt_sha256 is not None else payload["mlos_receipt_sha256"]
        expected = oracle.build_certificate_from_snapshot(snapshot, mlos_receipt_sha256=use_rec_sha)
        oracle.require_ok(
            hmac.compare_digest(oracle.canonical_json_bytes(cert), oracle.canonical_json_bytes(expected)),
            "FULL_REPLAY_MISMATCH",
            "certificate does not match exact pure-Z/Q replay from snapshot",
        )
        replayed = True

    return {
        "valid": True,
        "full_replay": replayed,
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "secondary_audit": sec_res,
    }


def write_certificate_file(
    path: Path,
    *,
    snapshot: dict[str, Any] | None = None,
    mlos_receipt_sha256: str | None = None,
) -> dict[str, Any]:
    if snapshot is None:
        snapshot, rec_sha = _load_default_snapshot_and_receipt()
        use_rec_sha = mlos_receipt_sha256 if mlos_receipt_sha256 is not None else rec_sha
    else:
        use_rec_sha = mlos_receipt_sha256
    cert = oracle.build_certificate_from_snapshot(snapshot, mlos_receipt_sha256=use_rec_sha)
    raw = oracle.canonical_json_bytes(cert)
    write_regular_bytes_safe(path, raw, "certificate")
    return {
        "written": True,
        "bytes": len(raw),
        "file_sha256": oracle.sha256_hex(raw),
        "certificate_sha256": cert["certificate_sha256"],
    }


def check_certificate_file(
    path: Path,
    *,
    snapshot_path: Path | None = None,
    mlos_receipt_path: Path | None = None,
    full_replay: bool = True,
) -> dict[str, Any]:
    raw = read_regular_bytes_capped(path, "certificate")
    cert = parse_strict_json_bytes(raw, "certificate", require_canonical=True)
    snap_obj: dict[str, Any] | None = None
    rec_sha: str | None = None
    if snapshot_path is not None:
        snap_raw = read_regular_bytes_capped(snapshot_path, "snapshot")
        snap_obj = parse_strict_json_bytes(snap_raw, "snapshot", require_canonical=True)
    if mlos_receipt_path is not None:
        rec_raw = read_regular_bytes_capped(mlos_receipt_path, "mlos_receipt")
        rec_sha = oracle.sha256_hex(rec_raw)
    res = verify_certificate_dict(cert, full_replay=full_replay, snapshot=snap_obj, mlos_receipt_sha256=rec_sha)
    res["file_sha256"] = oracle.sha256_hex(raw)
    return res


# ---------------------------------------------------------------------------
# Strict CLI Entrypoint
# ---------------------------------------------------------------------------

def _parse_cli_args(argv: Any) -> dict[str, Any]:
    oracle.require_ok(type(argv) is list, "INVALID_ARGV", "argv must be exact list")
    mode: str | None = None
    target_path: str | None = None
    snapshot_path: str | None = None
    want_json = False
    i = 0
    n = len(argv)
    while i < n:
        arg = _require_utf8_no_surrogate(argv[i], "argv")
        oracle.require_ok("\x00" not in arg, "NUL_BYTE_FORBIDDEN", "NUL byte in argv")
        if arg == "--json":
            oracle.require_ok(not want_json, "DUPLICATE_FLAG", "--json repeated")
            want_json = True
            i += 1
        elif arg == "--standalone":
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "conflicting mode flags")
            mode = "standalone"
            i += 1
        elif arg in ("--check", "--write"):
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "conflicting mode flags")
            oracle.require_ok(i + 1 < n, "MISSING_PATH_ARG", f"{arg} requires a path")
            val = _require_utf8_no_surrogate(argv[i + 1], f"{arg} path")
            oracle.require_ok("\x00" not in val, "NUL_BYTE_FORBIDDEN", f"NUL byte in {arg} path")
            oracle.require_ok(len(val) > 0 and not val.startswith("-"), "INVALID_PATH_ARG", f"invalid path {val!r}")
            mode = arg[2:]
            target_path = val
            i += 2
        elif arg.startswith("--check=") or arg.startswith("--write="):
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "conflicting mode flags")
            flag_name, val = arg.split("=", 1)
            oracle.require_ok(len(val) > 0 and not val.startswith("-"), "INVALID_PATH_ARG", f"invalid path {val!r}")
            mode = flag_name[2:]
            target_path = val
            i += 1
        elif arg == "--snapshot":
            oracle.require_ok(snapshot_path is None, "DUPLICATE_FLAG", "--snapshot repeated")
            oracle.require_ok(i + 1 < n, "MISSING_PATH_ARG", "--snapshot requires a path")
            val = _require_utf8_no_surrogate(argv[i + 1], "--snapshot path")
            oracle.require_ok("\x00" not in val, "NUL_BYTE_FORBIDDEN", "NUL byte in --snapshot path")
            oracle.require_ok(len(val) > 0 and not val.startswith("-"), "INVALID_PATH_ARG", f"invalid snapshot {val!r}")
            snapshot_path = val
            i += 2
        elif arg.startswith("--snapshot="):
            oracle.require_ok(snapshot_path is None, "DUPLICATE_FLAG", "--snapshot repeated")
            _, val = arg.split("=", 1)
            oracle.require_ok(len(val) > 0 and not val.startswith("-"), "INVALID_PATH_ARG", f"invalid snapshot {val!r}")
            snapshot_path = val
            i += 1
        else:
            raise oracle.RaplLandauerError("UNKNOWN_FLAG", f"unsupported CLI flag: {arg!r}")
    return {"mode": mode or "default", "target": target_path, "snapshot": snapshot_path, "json": want_json}


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv: Any = list(sys.argv[1:]) if argv is None else argv
    try:
        opts = _parse_cli_args(raw_argv)
        snap_p = Path(opts["snapshot"]) if opts["snapshot"] is not None else None
        mode = opts["mode"]
        if mode == "standalone":
            if snap_p is not None:
                snap_obj = parse_strict_json_bytes(read_regular_bytes_capped(snap_p, "snapshot"), "snapshot")
                rec_sha = None
            else:
                snap_obj, rec_sha = _load_default_snapshot_and_receipt()
            cert = oracle.build_certificate_from_snapshot(snap_obj, mlos_receipt_sha256=rec_sha)
            sys.stdout.write(oracle.canonical_json_bytes(cert).decode("ascii"))
            return 0
        if mode == "write":
            if snap_p is not None:
                snap_obj = parse_strict_json_bytes(read_regular_bytes_capped(snap_p, "snapshot"), "snapshot")
                rec_sha = None
            else:
                snap_obj, rec_sha = _load_default_snapshot_and_receipt()
            res = write_certificate_file(Path(opts["target"]), snapshot=snap_obj, mlos_receipt_sha256=rec_sha)
            if opts["json"]:
                sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii"))
            else:
                sys.stdout.write(f"WROTE {res['file_sha256']}\n")
            return 0
        if mode == "check":
            res = check_certificate_file(Path(opts["target"]), snapshot_path=snap_p, full_replay=True)
            if opts["json"]:
                sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii"))
            else:
                sys.stdout.write(f"OK {res['certificate_sha256']}\n")
            return 0
        # Default zero-arg mode: build from sibling snapshot & verify end-to-end
        snap_obj, rec_sha = _load_default_snapshot_and_receipt()
        cert = oracle.build_certificate_from_snapshot(snap_obj, mlos_receipt_sha256=rec_sha)
        res = verify_certificate_dict(cert, full_replay=True, snapshot=snap_obj, mlos_receipt_sha256=rec_sha)
        if opts["json"]:
            sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii"))
        else:
            sys.stdout.write(f"OK {res['certificate_sha256']}\n")
        return 0
    except oracle.RaplLandauerError as exc:
        err_obj = {"error_code": exc.code, "message": exc.message}
        sys.stderr.write(oracle.canonical_json_bytes(err_obj).decode("ascii"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
