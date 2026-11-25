#!/usr/bin/env python3
"""Zone-B Hardened Standalone CLI, Full Pure-Z/Q Replay & Secondary Auditor for CS-24 Gate.

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

import cs24_mock_anchor_oracle as oracle  # noqa: E402

MAX_JSON_BYTES = 1_048_576
MAX_ALLOWED_CAP_BYTES = 64 * 1024 * 1024
_READ_CHUNK_BYTES = 65_536
MAX_JSON_DEPTH = 64
MAX_JSON_INT_DIGITS = oracle.MAX_INT_DIGITS
MAX_JSON_INT_BITS = oracle.MAX_INT_BITS
_EXACT_PATH_TYPES = (Path, type(Path()))
_HEX_LOWER = frozenset("0123456789abcdef")
_ASCII_DIGITS = frozenset("0123456789")
_CERT_KEYS = frozenset({"schema_version", "track_id", "payload_sha256", "certificate_sha256", "payload"})
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
        raise oracle.CS24MockAnchorError("INVALID_STR", f"{label}: exact str required")
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise oracle.CS24MockAnchorError("INVALID_UTF8_SURROGATE", f"{label}: lone UTF-16 surrogate forbidden") from exc
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
        raise oracle.CS24MockAnchorError("CWD_UNAVAILABLE", f"{label}: CWD unavailable ({type(exc).__name__})") from exc


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
            raise oracle.CS24MockAnchorError("CWD_UNAVAILABLE", f"{label}: cannot open root for PWD") from exc
        try:
            for part in pwd_path.parts[1:]:
                if part == ".":
                    continue
                try:
                    next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
                except OSError as exc:
                    if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                        raise oracle.CS24MockAnchorError(
                            "SYMLINK_ANCESTOR_FORBIDDEN", f"{label}: symlink PWD ancestor forbidden"
                        ) from exc
                    raise oracle.CS24MockAnchorError(
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
        raise oracle.CS24MockAnchorError(err_code, f"{label}: cannot open root") from exc
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
                        raise oracle.CS24MockAnchorError(
                            "FILE_WRITE_ERROR", f"{label}: mkdir failed ({type(mk_exc).__name__})"
                        ) from mk_exc
                    try:
                        next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
                    except OSError as re_exc:
                        raise oracle.CS24MockAnchorError(
                            "FILE_WRITE_ERROR", f"{label}: cannot open created dir ({type(re_exc).__name__})"
                        ) from re_exc
                elif exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise oracle.CS24MockAnchorError(
                        "SYMLINK_FORBIDDEN", f"{label}: symlink or non-directory ancestor forbidden"
                    ) from exc
                else:
                    raise oracle.CS24MockAnchorError(
                        err_code, f"{label}: cannot traverse ancestor ({type(exc).__name__})"
                    ) from exc
            os.close(dfd)
            dfd = next_fd
        return dfd, leaf
    except BaseException:
        os.close(dfd)
        raise


def read_regular_bytes_capped(path: Path, label: str = "file", max_bytes: int = MAX_JSON_BYTES) -> bytes:
    """Read regular file bytes under strict cap using atomic dir_fd openat + fstat S_ISREG + 64 KiB chunks."""
    target = _require_concrete_path(path, label)
    oracle.require_exact_int(max_bytes, "max_bytes", lo=1, hi=MAX_ALLOWED_CAP_BYTES)
    dfd, leaf = _open_dir_chain(target, label, create_parents=False)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        try:
            fd = os.open(leaf, flags, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise oracle.CS24MockAnchorError("SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden") from exc
            raise oracle.CS24MockAnchorError("FILE_READ_ERROR", f"{label}: cannot open ({type(exc).__name__})") from exc
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
    except oracle.CS24MockAnchorError:
        raise
    except OSError as exc:
        raise oracle.CS24MockAnchorError("FILE_READ_ERROR", f"{label}: read failed ({type(exc).__name__})") from exc
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
            raise oracle.CS24MockAnchorError("FILE_WRITE_ERROR", f"{label}: lstat failed ({type(exc).__name__})") from exc
        if st_existing is not None:
            oracle.require_ok(not stat.S_ISLNK(st_existing.st_mode), "SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden")
            oracle.require_ok(stat.S_ISREG(st_existing.st_mode), "NOT_A_REGULAR_FILE", f"{label}: non-regular target")
            oracle.require_ok(st_existing.st_nlink <= 1, "HARDLINK_FORBIDDEN", f"{label}: hardlinked target forbidden")

        pid = os.getpid()
        for _ in range(64):
            with _TEMP_NAME_LOCK:
                _TEMP_SEQ += 1
                seq_num = _TEMP_SEQ
                cand = f".s56.{pid}.{seq_num}.{secrets.token_hex(8)}.tmp"
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
                raise oracle.CS24MockAnchorError(
                    "FILE_WRITE_ERROR", f"{label}: create temp failed ({type(exc).__name__})"
                ) from exc
        else:
            raise oracle.CS24MockAnchorError("FILE_WRITE_ERROR", f"{label}: exhausted temp file slots")

        try:
            view = memoryview(payload)
            written = 0
            while written < len(view):
                written += os.write(fd, view[written:])
            os.fsync(fd)
            st_tmp = os.fstat(fd)
            oracle.require_ok(st_tmp.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: temp link count altered")
        except oracle.CS24MockAnchorError:
            raise
        except OSError as exc:
            raise oracle.CS24MockAnchorError("FILE_WRITE_ERROR", f"{label}: write failed ({type(exc).__name__})") from exc
        finally:
            os.close(fd)

        try:
            os.replace(tmp_name, leaf, src_dir_fd=dfd, dst_dir_fd=dfd)
            tmp_name = None
            os.fsync(dfd)
        except OSError as exc:
            raise oracle.CS24MockAnchorError("FILE_WRITE_ERROR", f"{label}: atomic replace failed ({type(exc).__name__})") from exc
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

def require_hex64_lower_ascii(val: Any, label: str = "sha256") -> str:
    s = _require_utf8_no_surrogate(val, label)
    oracle.require_ok(len(s) == 64, "INVALID_HEX64", f"{label}: expected 64-char lowercase ASCII hex")
    for ch in s:
        oracle.require_ok(ch in _HEX_LOWER, "INVALID_HEX64", f"{label}: non-hex-lowercase char")
    return s


def _parse_bounded_int(token: str) -> int:
    """Strict ASCII-only 0-9 signed integer parser (rejects '-0', '007', Unicode digits, huge ints)."""
    s = _require_utf8_no_surrogate(token, "json_int")
    oracle.require_ok(s != "-0", "INVALID_JSON_INT", "negative zero forbidden")
    digits = s[1:] if s.startswith("-") else s
    oracle.require_ok(len(digits) >= 1, "INVALID_JSON_INT", "JSON int has no digits")
    oracle.require_ok(len(digits) <= MAX_JSON_INT_DIGITS, "INT_DIGIT_LIMIT", "JSON int exceeds digit cap")
    oracle.require_ok(digits == "0" or not digits.startswith("0"), "INVALID_JSON_INT", "leading zero forbidden")
    for ch in digits:
        oracle.require_ok(ch in _ASCII_DIGITS, "INVALID_JSON_INT", "non-ASCII digit forbidden")
    val = int(s)
    oracle.require_ok(abs(val).bit_length() <= MAX_JSON_INT_BITS, "INT_BIT_LIMIT", "JSON int exceeds bit cap")
    return val


def parse_exact_rational(token: Any, label: str = "rational") -> Fraction:
    """Strict ASCII-only canonical exact rational parser ('n' or reduced 'n/d' with d >= 2)."""
    s = _require_utf8_no_surrogate(token, label)
    parts = s.split("/")
    oracle.require_ok(len(parts) in (1, 2), "INVALID_RATIONAL", f"{label}: expected 'n' or 'n/d'")
    num = _parse_bounded_int(parts[0])
    if len(parts) == 1:
        return oracle.require_fraction(Fraction(num, 1), label)
    den = _parse_bounded_int(parts[1])
    oracle.require_ok(den >= 2, "INVALID_RATIONAL", f"{label}: denominator must be >= 2")
    oracle.require_ok(math.gcd(abs(num), den) == 1, "NON_CANONICAL_RATIONAL", f"{label}: not in lowest terms")
    return oracle.require_fraction(Fraction(num, den), label)


def _validate_json_tree(root: Any, label: str = "json") -> None:
    """Iterative validator: depth cap (blocks cycles), bit cap, UTF-8 surrogate check, zero floats/subclasses."""
    stack: list[tuple[Any, int]] = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        oracle.require_ok(depth <= MAX_JSON_DEPTH, "JSON_DEPTH_LIMIT", f"{label}: nesting exceeds {MAX_JSON_DEPTH}")
        t = type(node)
        if node is None or t is bool:
            continue
        if t is int:
            oracle.require_ok(
                abs(node).bit_length() <= MAX_JSON_INT_BITS,
                "INT_BIT_LIMIT",
                f"{label}: int exceeds {MAX_JSON_INT_BITS} bits",
            )
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
        raise oracle.CS24MockAnchorError("FORBIDDEN_JSON_TYPE", f"{label}: unsupported type {t.__name__}")


def _reject_float(token: str) -> Any:
    raise oracle.CS24MockAnchorError("FLOAT_LITERAL_FORBIDDEN", f"float literal forbidden: {token}")


def _reject_constant(token: str) -> Any:
    raise oracle.CS24MockAnchorError("NONFINITE_LITERAL_FORBIDDEN", f"non-finite constant forbidden: {token}")


def _strict_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        _require_utf8_no_surrogate(k, "json_key")
        oracle.require_ok(k not in out, "DUPLICATE_JSON_KEY", f"duplicate key {k!r}")
        out[k] = v
    return out


def parse_strict_json_text(text: Any, *, require_object: bool = True) -> Any:
    s = _require_utf8_no_surrogate(text, "json_text")
    oracle.require_bool(require_object, "require_object")
    oracle.require_ok(len(s.encode("utf-8")) <= MAX_JSON_BYTES, "JSON_TOO_LARGE", "JSON text exceeds size cap")
    try:
        parsed = json.loads(
            s,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
            parse_int=_parse_bounded_int,
            object_pairs_hook=_strict_pairs_hook,
        )
    except oracle.CS24MockAnchorError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise oracle.CS24MockAnchorError("JSON_PARSE_ERROR", f"invalid JSON ({type(exc).__name__})") from exc
    _validate_json_tree(parsed, "parsed_json")
    if require_object and type(parsed) is not dict:
        raise oracle.CS24MockAnchorError("JSON_ROOT_NOT_OBJECT", "JSON root must be an object")
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


# ---------------------------------------------------------------------------
# Bijective Pinned Spec & Secondary Algebraic Cross-Checker
# ---------------------------------------------------------------------------

_EXPECTED_PAYLOAD: dict[str, Any] = {
    "novelty_classification": "N1",
    "oracle_class": "exact",
    "pillar1_commutator_obstruction": {
        "all_verified": True,
        "divergence_rate_q": "1",
        "false_green_divergences": 4,
        "power_roofline_commutator": {
            "ac_bf16_gflops": 35031,
            "ac_power_w": 110,
            "battery_bf16_gflops": 31880,
            "battery_power_w": 55,
            "bf16_ratio_q": "35031/31880",
            "bf16_relative_uplift_pct_dec4": "9.8839",
            "bf16_relative_uplift_q": "3151/31880",
            "power_cap_ratio_q": "2",
            "power_envelope_diverges": True,
        },
        "witnesses": [
            {
                "commutator_defect": 1,
                "live_silicon_reality": "Real Linux pciutils rejects -Dnns without -s <slot>, yielding igpu_model=null; fix requires lspci -Dnn for 0000:00:02.0 [8086:9a60]",
                "mock_assumption": "lspci -Dnns parses Intel iGPU without slot argument (16/16 mocked tests green)",
                "mocked_tests_passed": 16,
                "mocked_tests_total": 16,
                "non_commuting": True,
                "subsystem": "ml_os.probe.lspci",
                "v_mock": 1,
                "v_silicon": 0,
                "witness_id": "W1_LSPCI_DNNS_FLAG",
            },
            {
                "commutator_defect": 1,
                "live_silicon_reality": "NVIDIA Linux driver 615.78.08 (GA104M) retains 2 MiB internal KMD metadata with 0 graphics/compute processes",
                "mock_assumption": "Idle Linux GPU reports exactly 0 MiB VRAM with zero processes (16/16 mocked tests green)",
                "mocked_tests_passed": 16,
                "mocked_tests_total": 16,
                "non_commuting": True,
                "subsystem": "ml_os.stamp_run.vram_baseline",
                "v_mock": 1,
                "v_silicon": 0,
                "witness_id": "W2_NVIDIA_KMD_2MIB_BASELINE",
            },
            {
                "commutator_defect": 1,
                "live_silicon_reality": "Live UX582HS exposes DP-3 + elan9009:00-04f3:2c23 and Omarchy 4.5.0 Lua hl.dsp.exec_cmd dispatch contract",
                "mock_assumption": "Mocked display/touch fixture and classic hyprctl dispatch exec match desktop target",
                "mocked_tests_passed": 7,
                "mocked_tests_total": 7,
                "non_commuting": True,
                "subsystem": "aletheia_shell.display_hud",
                "v_mock": 1,
                "v_silicon": 0,
                "witness_id": "W3_UX582HS_DP3_ELAN9009_LUA",
            },
            {
                "commutator_defect": 1,
                "live_silicon_reality": "Quoted external power-state figures (battery 55W vs AC 110W, BF16 GEMM 31.880 -> 35.031 TFLOPS, +9.8839%) are an unverified illustration, not a measured result",
                "mock_assumption": "Unpinned mocked power envelope treated as equivalent across battery and AC states",
                "mocked_tests_passed": 18,
                "mocked_tests_total": 18,
                "non_commuting": True,
                "subsystem": "quoted_external_track_anchor.roofline",
                "v_mock": 1,
                "v_silicon": 0,
                "witness_id": "W4_AC110W_VS_BAT55W_ROOFLINE",
            },
        ],
        "witnesses_total": 4,
    },
    "pillar2_ux582hs_mock_divergences": {
        "all_verified": True,
        "cases": [
            {"claim_id": "W1_LSPCI_DNNS_FLAG", "cs24_triggered": True, "domain": "hardware_probe", "reason_codes": ["CS24_MOCK_ANCHOR_UNVERIFIED"], "verdict": "DENY"},
            {"claim_id": "W2_NVIDIA_KMD_2MIB_BASELINE", "cs24_triggered": True, "domain": "driver_isolation", "reason_codes": ["CS24_MOCK_ANCHOR_UNVERIFIED"], "verdict": "DENY"},
            {"claim_id": "W3_UX582HS_DP3_ELAN9009_LUA", "cs24_triggered": True, "domain": "display_shell", "reason_codes": ["CS24_MOCK_ANCHOR_UNVERIFIED"], "verdict": "DENY"},
            {"claim_id": "W4_AC110W_VS_BAT55W_ROOFLINE", "cs24_triggered": True, "domain": "silicon_roofline", "reason_codes": ["CS24_MOCK_ANCHOR_UNVERIFIED"], "verdict": "DENY"},
        ],
        "denied_count": 4,
        "total_count": 4,
    },
    "pillar3_benign_and_forged_matrix": {
        "all_verified": True,
        "benign_allowed_count": 3,
        "benign_live_controls": [
            {"claim_id": "C1_MLOS_PR7_UX582HS_STAMP", "cs24_triggered": False, "domain": "hardware_probe", "reason_codes": [], "verdict": "ALLOW"},
            {"claim_id": "C2_RTX3080_ZONEB_RECEIPT", "cs24_triggered": False, "domain": "silicon_roofline", "reason_codes": [], "verdict": "ALLOW"},
            {"claim_id": "C3_SHELL_PR8_DP3_LUA_CONTROL", "cs24_triggered": False, "domain": "display_shell", "reason_codes": [], "verdict": "ALLOW"},
        ],
        "forged_bypass_attempts": [
            {"claim_id": "F1_KMD_ZERO_PROCESS_SPOOF", "cs24_triggered": True, "domain": "driver_isolation", "reason_codes": ["CS24_KMD_BASELINE_SPOOFED"], "verdict": "DENY"},
            {"claim_id": "F2_UNPINNED_ZERO_SHA", "cs24_triggered": True, "domain": "hardware_probe", "reason_codes": ["CS24_RECEIPT_SHA_UNPINNED"], "verdict": "DENY"},
            {"claim_id": "F3_BATTERY_MASKED_AC_ROOFLINE", "cs24_triggered": True, "domain": "silicon_roofline", "reason_codes": ["CS24_POWER_REGIME_MISMATCH"], "verdict": "DENY"},
            {"claim_id": "F4_MOCKED_SUBPROCESS_RECEIPT", "cs24_triggered": True, "domain": "display_shell", "reason_codes": ["CS24_SUBPROCESS_MOCKED_IN_RECEIPT"], "verdict": "DENY"},
            {"claim_id": "F5_BOOL_INT_FLOAT_CONTAMINATION", "cs24_triggered": True, "domain": "driver_isolation", "reason_codes": ["CS24_RECEIPT_TYPE_CONTAMINATION"], "verdict": "DENY"},
        ],
        "forged_denied_count": 5,
        "pinned_live_receipts": {
            "mlos_ux582hs_stamp_sha256": "4ba28f3ed9b037f314bd857c41010d8dd280a37286c69508a93f9e5acf70516a",
            "rtx3080_zoneb_receipt_sha256": "de1a1b18b65497c629cfa6116eb0be70d4fcdf399e8c2cb2d157b005c051102d",
            "shell_dp3_lua_receipt_sha256": "6f05ea43e03bee87d4bc127fb1410198c59106dc1ea98fd5967ac3baf7f83b53",
        },
        "runtime_float_contamination_denied": True,
        "runtime_float_reason_codes": ["CS24_RECEIPT_TYPE_CONTAMINATION"],
    },
    "pillar4_contingency_and_bounds": {
        "accuracy_q": "1",
        "all_verified": True,
        "false_negatives": 0,
        "false_positives": 0,
        "max_int_bits": 3321,
        "max_linux_kmd_baseline_mib": 4,
        "precision_q": "1",
        "sensitivity_q": "1",
        "specificity_q": "1",
        "total_evaluated": 12,
        "true_negatives": 3,
        "true_positives": 9,
    },
    "prior_art_n0": [
        "Meszaros (2007) xUnit Test Patterns \u2014 fragile test-double and mock-drift taxonomy",
        "POSIX / Linux pciutils lspci(8) CLI specification (-Dnn vs -s slot semantics)",
        "NVIDIA NVML / Linux Kernel Mode Driver (KMD) internal metadata VRAM accounting",
        "Hardware-in-the-Loop (HIL) verification discipline for physical/driver contracts",
    ],
    "schema_version": "aletheia.track_s56.cs24_mock_anchor.v1",
    "summary": {
        "all_four_pillars_verified": True,
        "bare_assert_count": 0,
        "float_count_on_trust_path": 0,
        "pillar_count": 4,
        "rng_calls": 0,
    },
    "track_id": "TRACK-S56-CS24-MOCK-ANCHOR-GATE",
}


def _verify_exact_payload_tree(actual: Any, expected: Any, root_label: str) -> None:
    """Iterative bijective schema & pinned-leaf verifier: exact types, keysets, lengths, values."""
    stack: list[tuple[Any, Any, str]] = [(actual, expected, root_label)]
    while stack:
        act, exp, path = stack.pop()
        oracle.require_ok(type(act) is type(exp), "INVALID_SCHEMA_TYPE", f"{path}: exact type mismatch")
        t = type(exp)
        if t is dict:
            oracle.require_ok(
                frozenset(act.keys()) == frozenset(exp.keys()),
                "INVALID_SCHEMA_KEYS",
                f"{path}: exact keyset mismatch",
            )
            for k, exp_v in exp.items():
                stack.append((act[k], exp_v, f"{path}.{k}"))
        elif t is list:
            oracle.require_ok(
                len(act) == len(exp),
                "INVALID_SCHEMA_LIST",
                f"{path}: list length mismatch",
            )
            for idx, (act_i, exp_i) in enumerate(zip(act, exp)):
                stack.append((act_i, exp_i, f"{path}[{idx}]"))
        else:
            oracle.require_ok(act == exp, "SCHEMA_VALUE_MISMATCH", f"{path}: pinned leaf mismatch")


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Fail-closed secondary algebraic & bijective cross-check (safe under direct call & full_replay=False)."""
    oracle.require_ok(type(payload) is dict, "INVALID_PAYLOAD", "payload must be exact dict")
    _validate_json_tree(payload, "payload")

    # Bijective structural + type + keyset + pinned-leaf verification first (eliminates KeyError/TypeError on tamper)
    _verify_exact_payload_tree(payload, _EXPECTED_PAYLOAD, "payload")

    # Independent division-free algebraic cross-checks across all 4 pillars
    p1 = payload["pillar1_commutator_obstruction"]
    for w in p1["witnesses"]:
        oracle.require_ok(w["v_mock"] - w["v_silicon"] == w["commutator_defect"], "AUDIT_P1_COMM", "commutator defect mismatch")
    pw = p1["power_roofline_commutator"]
    oracle.require_ok(
        parse_exact_rational(pw["power_cap_ratio_q"], "p1.pr") * pw["battery_power_w"] == pw["ac_power_w"],
        "AUDIT_P1_POWER",
        "power cap ratio mismatch",
    )
    oracle.require_ok(
        parse_exact_rational(pw["bf16_relative_uplift_q"], "p1.up") * pw["battery_bf16_gflops"]
        == pw["ac_bf16_gflops"] - pw["battery_bf16_gflops"],
        "AUDIT_P1_UPLIFT",
        "BF16 uplift rational mismatch",
    )

    p4 = payload["pillar4_contingency_and_bounds"]
    tp, tn, fp, fn = p4["true_positives"], p4["true_negatives"], p4["false_positives"], p4["false_negatives"]
    oracle.require_ok(tp + tn + fp + fn == p4["total_evaluated"], "AUDIT_P4_TOTAL", "contingency total mismatch")
    oracle.require_ok(parse_exact_rational(p4["sensitivity_q"], "p4.sens") * (tp + fn) == tp, "AUDIT_P4_SENS", "sensitivity mismatch")
    oracle.require_ok(parse_exact_rational(p4["specificity_q"], "p4.spec") * (tn + fp) == tn, "AUDIT_P4_SPEC", "specificity mismatch")

    return {
        "secondary_audit_passed": True,
        "pillars_audited": 4,
    }


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
    oracle.require_bool(full_replay, "full_replay")
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
        raise oracle.CS24MockAnchorError("INVALID_UTF8", "certificate is not valid UTF-8") from exc
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


# ---------------------------------------------------------------------------
# Strict Fail-Closed CLI (Space & Equals Flag-Like Rejection)
# ---------------------------------------------------------------------------

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
            raise oracle.CS24MockAnchorError("UNKNOWN_FLAG", f"unrecognized CLI argument: {tok}")

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
    except oracle.CS24MockAnchorError as exc:
        err = {"valid": False, "error_code": exc.code, "error_message": exc.message}
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
