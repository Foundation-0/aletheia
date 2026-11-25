#!/usr/bin/env python3
"""
Independent Pure-Z/Q Verifier:
Silicon-to-Universal Exact-Operator Correspondence & Obstruction Atlas.

Zero-dependency stdlib verifier hardening all untrusted boundary paths:
  - Iterative JSON tree validation (depth <= 64, int bit_length <= 2048,
    strict int/bool/str/list/dict types, zero floats, zero lone surrogates).
  - Positive rational denominator guards before every division.
  - Constant-time hmac.compare_digest SHA-256 checks + bijective canonical
    payload pin against independent recomputation.
  - Hardened dir_fd I/O (O_DIRECTORY | O_NOFOLLOW ancestor walk, inode-matched
    $PWD symlink audit, verified root-owned Darwin prefix normalization,
    O_NONBLOCK + S_ISREG + st_nlink == 1 + streaming read cap, durable 0o600
    atomic write with bounded EEXIST retries and typed ATOMIC_WRITE_ERROR).
  - Full live hardware receipt & raw integer array replay (--verify-receipts).
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import threading
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import silicon_universal_oracle as oracle

MAX_JSON_BYTES = 2_097_152
_READ_CHUNK_BYTES = 65_536
MAX_JSON_DEPTH = 64
MAX_INT_BITS = 2048
_MAX_TMP_RETRIES = 8
_EXACT_PATH_TYPES = (Path, type(Path()))
_TEMP_NAME_LOCK = threading.Lock()
_HEX_LOWER = frozenset("0123456789abcdef")
_ASCII_DIGITS = frozenset("0123456789")
_DARWIN_SYSTEM_LINKS = frozenset({"tmp", "var", "etc"})
_CERT_KEYS = frozenset({"schema", "track_id", "payload_sha256", "certificate_sha256", "payload"})

# --check is a self-consistency pin: it compares the disk certificate against the payload
# produced by the CURRENT oracle build_payload(), so editing oracle literals would not be
# caught by --check alone. The semantic anchor is --verify-receipts, which re-reads the raw
# capture from disk and replays it through the oracle, cross-checking the payload fields.
_EXPECTED_PAYLOAD_BYTES: bytes = oracle.canonical_json_bytes(oracle.build_payload())


class AuditError(ValueError):
    """Fail-closed typed error for Track S64 verification and hardened I/O."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


# ---------------------------------------------------------------------------
# Strict Zero-Float Validation & Exact Rational Parsing
# ---------------------------------------------------------------------------

def _is_ascii_digits(text: str) -> bool:
    if not text:
        return False
    for ch in text:
        if ch not in _ASCII_DIGITS:
            return False
    return True


def _req_dict(val: Any, label: str) -> dict[str, Any]:
    if type(val) is not dict:
        raise AuditError("INVALID_DICT", f"{label} must be exact dict")
    return val


def _req_list(val: Any, label: str) -> list[Any]:
    if type(val) is not list:
        raise AuditError("INVALID_LIST", f"{label} must be exact list")
    return val


def _req_str(val: Any, label: str) -> str:
    if type(val) is not str:
        raise AuditError("INVALID_STR", f"{label} must be exact str")
    try:
        val.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise AuditError("INVALID_UNICODE_STR", f"{label} has lone surrogate: {exc}") from exc
    return val


def _req_bool(val: Any, label: str) -> bool:
    if type(val) is not bool:
        raise AuditError("INVALID_BOOL", f"{label} must be exact bool")
    return val


def _req_int(val: Any, label: str) -> int:
    if type(val) is not int:
        raise AuditError("INVALID_INT", f"{label} must be exact int")
    if val.bit_length() > MAX_INT_BITS:
        raise AuditError("INT_BIT_LIMIT", f"{label} exceeds {MAX_INT_BITS} bits")
    return val


def _req_sha256(val: Any, label: str) -> str:
    text = _req_str(val, label)
    if len(text) != 64:
        raise AuditError("INVALID_SHA256", f"{label} must be 64 lowercase hex chars")
    for ch in text:
        if ch not in _HEX_LOWER:
            raise AuditError("INVALID_SHA256", f"{label} has non-hex character")
    return text


def _parse_rational(val: Any, label: str) -> Fraction:
    text = _req_str(val, label)
    if "/" in text:
        parts = text.split("/")
        if len(parts) != 2:
            raise AuditError("INVALID_RATIONAL", f"{label} malformed rational")
        num_s, den_s = parts[0], parts[1]
        neg = num_s.startswith("-")
        body = num_s[1:] if neg else num_s
        if not _is_ascii_digits(body) or not _is_ascii_digits(den_s):
            raise AuditError("INVALID_RATIONAL", f"{label} non-digit rational")
        if len(body) > 620 or len(den_s) > 620:
            raise AuditError("RATIONAL_DIGIT_LIMIT", f"{label} exceeds digit cap")
        den = int(den_s)
        if den <= 0:
            raise AuditError("INVALID_RATIONAL", f"{label} denominator must be positive")
        num = -int(body) if neg else int(body)
        q = Fraction(num, den)
        if oracle.q_str(q) != text:
            raise AuditError("NON_CANONICAL_RATIONAL", f"{label} not in reduced canonical form")
        return q
    neg = text.startswith("-")
    body = text[1:] if neg else text
    if not _is_ascii_digits(body):
        raise AuditError("INVALID_RATIONAL", f"{label} non-digit integer rational")
    if len(body) > 620:
        raise AuditError("RATIONAL_DIGIT_LIMIT", f"{label} exceeds digit cap")
    num = -int(body) if neg else int(body)
    q = Fraction(num, 1)
    if oracle.q_str(q) != text:
        raise AuditError("NON_CANONICAL_RATIONAL", f"{label} not in canonical form")
    return q


def _parse_positive_rational(val: Any, label: str) -> Fraction:
    q = _parse_rational(val, label)
    if q <= 0:
        raise AuditError("NONPOSITIVE_VALUE", f"{label} must be strictly positive")
    return q


def _validate_json_tree(root: Any, label: str = "root") -> None:
    """Iteratively validate exact JSON-compatible types, depth, and integer bounds."""
    stack: list[tuple[Any, int, str]] = [(root, 0, label)]
    while stack:
        node, depth, path = stack.pop()
        if depth > MAX_JSON_DEPTH:
            raise AuditError("JSON_DEPTH_EXCEEDED", f"{path} exceeds depth {MAX_JSON_DEPTH}")
        t = type(node)
        if t is dict:
            for k, v in node.items():
                if type(k) is not str:
                    raise AuditError("NON_STR_KEY", f"{path} has non-str key")
                _req_str(k, f"{path}.key")
                stack.append((v, depth + 1, f"{path}.{k}"))
        elif t is list:
            for idx, item in enumerate(node):
                stack.append((item, depth + 1, f"{path}[{idx}]"))
        elif t is str:
            _req_str(node, path)
        elif t is bool:
            pass
        elif t is int:
            _req_int(node, path)
        elif node is None:
            pass
        else:
            raise AuditError("FORBIDDEN_TYPE", f"{path} has forbidden type {t.__name__}")


def _strict_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise AuditError("DUPLICATE_JSON_KEY", f"duplicate key: {k}")
        out[k] = v
    return out


def _reject_float_constant(token: str) -> Any:
    raise AuditError("NONFINITE_JSON_CONSTANT", f"forbidden JSON constant: {token}")


def _reject_float_literal(token: str) -> Any:
    raise AuditError("FLOAT_LITERAL_FORBIDDEN", f"forbidden JSON float literal: {token}")


def _parse_bounded_int_token(token: str) -> int:
    body = token[1:] if token.startswith("-") else token
    if len(body) > 620:
        raise AuditError("INT_DIGIT_LIMIT", "JSON integer exceeds 620 digits")
    val = int(token)
    if val.bit_length() > MAX_INT_BITS:
        raise AuditError("INT_BIT_LIMIT", f"JSON integer exceeds {MAX_INT_BITS} bits")
    return val


def parse_strict_json_bytes(raw: bytes, *, allow_floats: bool = False) -> Any:
    if b"\r" in raw:
        raise AuditError("CRLF_FORBIDDEN", "CR/CRLF line endings forbidden")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AuditError("INVALID_UTF8", f"invalid UTF-8: {exc}") from exc
    try:
        obj = json.loads(
            text,
            object_pairs_hook=_strict_pairs_hook,
            parse_constant=_reject_float_constant,
            parse_float=None if allow_floats else _reject_float_literal,
            parse_int=_parse_bounded_int_token,
        )
    except AuditError:
        raise
    except (ValueError, RecursionError) as exc:
        raise AuditError("INVALID_JSON", f"JSON parse error: {exc}") from exc
    if not allow_floats:
        _validate_json_tree(obj, "json")
    return obj


# ---------------------------------------------------------------------------
# Hardened dir_fd File I/O
# ---------------------------------------------------------------------------

def _validate_path_obj(path: Any) -> str:
    if type(path) not in _EXACT_PATH_TYPES:
        raise AuditError("INVALID_PATH_TYPE", "path must be concrete pathlib.Path")
    raw = str(path)
    try:
        raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise AuditError("INVALID_UNICODE_STR", f"lone surrogate in path: {exc}") from exc
    if "\x00" in raw:
        raise AuditError("INVALID_PATH", "NUL path forbidden")
    return raw


def _is_symlink_at(dfd: int, name: str) -> bool:
    try:
        return stat.S_ISLNK(os.lstat(name, dir_fd=dfd).st_mode)
    except OSError:
        return False


def _normalize_darwin_system_prefix(path: Path) -> Path:
    if sys.platform != "darwin" or not path.is_absolute():
        return path
    parts = path.parts
    if len(parts) >= 2 and parts[1] in _DARWIN_SYSTEM_LINKS:
        root_link = Path("/") / parts[1]
        try:
            st = os.lstat(root_link)
            if stat.S_ISLNK(st.st_mode) and st.st_uid == 0:
                target = os.readlink(root_link)
                if target == f"private/{parts[1]}":
                    return Path("/private") / parts[1] / Path(*parts[2:])
        except OSError:
            return path
    return path


def _check_pwd_no_symlinks() -> None:
    pwd = os.environ.get("PWD")
    if pwd is None or not os.path.isabs(pwd):
        return
    try:
        pwd.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise AuditError("INVALID_UNICODE_STR", f"lone surrogate in PWD: {exc}") from exc
    try:
        st_dot = os.stat(".")
        st_pwd = os.stat(pwd)
    except (OSError, ValueError):
        return
    if (st_dot.st_dev, st_dot.st_ino) != (st_pwd.st_dev, st_pwd.st_ino):
        return
    norm_pwd = _normalize_darwin_system_prefix(Path(pwd))
    cur_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in norm_pwd.parts[1:]:
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if _is_symlink_at(cur_fd, comp):
                    raise AuditError("SYMLINK_ANCESTOR_FORBIDDEN", f"symlink in PWD: {comp}") from exc
                raise AuditError("PWD_WALK_ERROR", f"failed walking PWD: {exc}") from exc
            os.close(cur_fd)
            cur_fd = nxt
    finally:
        os.close(cur_fd)


def _open_parent_dir_fd(path: Path, *, create_parents: bool = False) -> tuple[int, str]:
    _validate_path_obj(path)
    norm = _normalize_darwin_system_prefix(path)
    is_abs = norm.is_absolute()
    if not is_abs:
        _check_pwd_no_symlinks()
    parts = norm.parts[1:] if is_abs else norm.parts
    if not parts:
        raise AuditError("INVALID_PATH", "path has no leaf component")
    ancestors, leaf = parts[:-1], parts[-1]
    if leaf in (".", ".."):
        raise AuditError("INVALID_PATH", f"invalid leaf component: {leaf}")
    cur_fd = os.open("/" if is_abs else ".", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in ancestors:
            if comp == "..":
                raise AuditError("PARENT_TRAVERSAL_FORBIDDEN", "'..' forbidden in path")
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except FileNotFoundError as exc:
                if not create_parents:
                    raise AuditError("FILE_NOT_FOUND", f"missing directory: {comp}") from exc
                try:
                    os.mkdir(comp, 0o700, dir_fd=cur_fd)
                    nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
                except OSError as mk_exc:
                    raise AuditError("ATOMIC_WRITE_ERROR", f"cannot create ancestor {comp}: {mk_exc}") from mk_exc
            except OSError as exc:
                if _is_symlink_at(cur_fd, comp):
                    raise AuditError("SYMLINK_ANCESTOR_FORBIDDEN", f"symlink ancestor: {comp}") from exc
                raise AuditError("DIR_OPEN_ERROR", f"cannot open ancestor {comp}: {exc}") from exc
            os.close(cur_fd)
            cur_fd = nxt
        return cur_fd, leaf
    except Exception:
        os.close(cur_fd)
        raise


def read_regular_bytes_safe(path: Path, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    parent_fd, leaf = _open_parent_dir_fd(path, create_parents=False)
    try:
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
        try:
            fd = os.open(leaf, flags, dir_fd=parent_fd)
        except FileNotFoundError as exc:
            raise AuditError("FILE_NOT_FOUND", f"missing file: {path}") from exc
        except OSError as exc:
            if _is_symlink_at(parent_fd, leaf):
                raise AuditError("SYMLINK_FORBIDDEN", f"symlink forbidden: {path}") from exc
            raise AuditError("FILE_OPEN_ERROR", f"cannot open file {path}: {exc}") from exc
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                raise AuditError("NON_REGULAR_FILE", f"not a regular file: {path}")
            if st.st_nlink != 1:
                raise AuditError("HARDLINK_FORBIDDEN", f"hardlink count={st.st_nlink} != 1")
            if st.st_size > max_bytes:
                raise AuditError("FILE_TOO_LARGE", f"file exceeds {max_bytes} bytes")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(fd, _READ_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise AuditError("FILE_TOO_LARGE", f"stream exceeds {max_bytes} bytes")
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(fd)
    finally:
        os.close(parent_fd)


def write_regular_bytes_atomic_0600(path: Path, data: bytes) -> None:
    parent_fd, leaf = _open_parent_dir_fd(path, create_parents=True)
    try:
        if _is_symlink_at(parent_fd, leaf):
            raise AuditError("SYMLINK_FORBIDDEN", f"target is symlink: {path}")
        try:
            existing = os.lstat(leaf, dir_fd=parent_fd)
            if not stat.S_ISREG(existing.st_mode):
                raise AuditError("NON_REGULAR_TARGET", f"target is not regular file: {path}")
            if existing.st_nlink > 1:
                raise AuditError("HARDLINK_FORBIDDEN", f"target hardlink count={existing.st_nlink} > 1")
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise AuditError("ATOMIC_WRITE_ERROR", f"cannot inspect target {path}: {exc}") from exc

        wflags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
        tmp_name = ""
        fd: int | None = None
        for _ in range(_MAX_TMP_RETRIES):
            with _TEMP_NAME_LOCK:
                tmp_name = f".{leaf}.tmp.{secrets.token_hex(8)}"
            try:
                fd = os.open(tmp_name, wflags, 0o600, dir_fd=parent_fd)
                break
            except FileExistsError:
                continue
            except OSError as exc:
                raise AuditError("ATOMIC_WRITE_ERROR", f"cannot create temp file: {exc}") from exc
        if fd is None:
            raise AuditError("ATOMIC_WRITE_ERROR", "exhausted temp filename retries")

        fd_open = True
        try:
            os.fchmod(fd, 0o600)
            view = memoryview(data)
            written = 0
            while written < len(view):
                n = os.write(fd, view[written:])
                if n <= 0:
                    raise AuditError("SHORT_WRITE", "os.write returned 0")
                written += n
            os.fsync(fd)
            st_tmp = os.fstat(fd)
            if st_tmp.st_nlink != 1:
                raise AuditError("HARDLINK_FORBIDDEN", "temp file gained hardlink")
            os.close(fd)
            fd_open = False
            os.replace(tmp_name, leaf, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            os.fsync(parent_fd)
        except AuditError:
            if fd_open:
                os.close(fd)
            try:
                os.unlink(tmp_name, dir_fd=parent_fd)
            except OSError:
                pass
            raise
        except OSError as exc:
            if fd_open:
                os.close(fd)
            try:
                os.unlink(tmp_name, dir_fd=parent_fd)
            except OSError:
                pass
            raise AuditError("ATOMIC_WRITE_ERROR", f"atomic write failed: {exc}") from exc
    finally:
        os.close(parent_fd)


# ---------------------------------------------------------------------------
# Independent Pure-Z/Q Secondary Semantic Audit (All 6 Pillars + Bijective Pin)
# ---------------------------------------------------------------------------

def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Independently verify all 6 pillars, exact inequalities, obstructions, and canonical pin."""
    _validate_json_tree(payload, "payload")
    p = _req_dict(payload, "payload")
    if set(p.keys()) != {"exact", "sampled", "anchor"}:
        raise AuditError("PAYLOAD_KEYS_MISMATCH", "payload must contain exact, sampled, anchor")

    exact = _req_dict(p["exact"], "exact")
    if _req_str(exact.get("provenance_tier"), "exact.tier") != "exact":
        raise AuditError("TIER_MISMATCH", "exact tier mismatch")

    s39_ex = _req_dict(exact.get("s39_nyquist_third_prism_exact"), "exact.s39")
    wn_list = [_parse_positive_rational(v, f"wn[{i}]") for i, v in enumerate(_req_list(s39_ex.get("white_noise_r2_to_r5_q"), "wn"))]
    rw_list = [_parse_positive_rational(v, f"rw[{i}]") for i, v in enumerate(_req_list(s39_ex.get("random_walk_r2_to_r5_q"), "rw"))]
    if wn_list != [Fraction(3, 1), Fraction(10, 3), Fraction(7, 2), Fraction(18, 5)]:
        raise AuditError("S39_WN_MISMATCH", "white noise prism mismatch")
    if rw_list != [Fraction(2, 1), Fraction(3, 1), Fraction(10, 3), Fraction(7, 2)]:
        raise AuditError("S39_RW_MISMATCH", "random walk prism mismatch")

    codes_ex = _req_dict(exact.get("universal_code_and_lattice_exact"), "exact.codes")
    if _req_int(codes_ex.get("c16_11_4_codeword_count"), "c16_cnt") != 2048:
        raise AuditError("CODE_INVARIANT_MISMATCH", "C_[16,11,4] codeword count != 2048")
    if _req_int(codes_ex.get("rm14_subset_c16_verified_count"), "rm14_cnt") != 32:
        raise AuditError("CODE_INVARIANT_MISMATCH", "RM(1,4) subset count != 32")
    if _req_int(codes_ex.get("e8_total_minimal_roots"), "e8_roots") != 240:
        raise AuditError("CODE_INVARIANT_MISMATCH", "E_8 minimal root count != 240")

    gauge_ex = _req_dict(exact.get("stage_a_gauge_invariance_exact"), "exact.gauge")
    if not _req_bool(gauge_ex.get("exact_zero_gauge_drift"), "exact_zero_gauge_drift"):
        raise AuditError("GAUGE_DRIFT", "Stage-A gauge invariance must be exact zero")

    sampled = _req_dict(p["sampled"], "sampled")
    if _req_str(sampled.get("provenance_tier"), "sampled.tier") != "sampled":
        raise AuditError("TIER_MISMATCH", "sampled tier mismatch")
    if not _req_bool(sampled.get("measured_live_silicon"), "measured_live_silicon"):
        raise AuditError("LIVE_SILICON_FLAG", "measured_live_silicon must be true")

    priv = _req_dict(sampled.get("privacy_locks"), "privacy_locks")
    if (
        _req_bool(priv.get("audio_capture_accessed"), "audio")
        or _req_bool(priv.get("camera_accessed"), "camera")
        or _req_bool(priv.get("display_modified"), "display")
    ):
        raise AuditError("PRIVACY_VIOLATION", "privacy locks must all be false")

    mlos_r = _req_dict(sampled.get("ring0_mlos_receipt"), "ring0_mlos_receipt")
    if not _req_bool(mlos_r.get("clean_hardware_run"), "clean_hardware_run"):
        raise AuditError("RING0_DIRTY", "clean_hardware_run must be true")
    if _req_int(mlos_r.get("exit_code"), "exit_code") != 0 or _req_int(mlos_r.get("anomaly_count"), "anomaly_count") != 0:
        raise AuditError("RING0_ANOMALY", "Ring-0 exit_code and anomaly_count must be 0")
    vram_mib = _req_int(mlos_r.get("linux_kmd_baseline_vram_mib"), "vram_mib")
    if vram_mib < 0 or vram_mib > 4:
        raise AuditError("RING0_VRAM_EXCESS", f"baseline VRAM {vram_mib} outside [0,4]")
    if _req_bool(mlos_r.get("thermal_throttled"), "thermal_throttled") or _req_bool(mlos_r.get("slowdown_active"), "slowdown_active"):
        raise AuditError("RING0_THROTTLED", "thermal_throttled and slowdown_active must be false")

    # Pillar 1 semantic checks
    p1 = _req_dict(sampled.get("pillar_1_dark_mode_schur_and_gauge"), "pillar_1")
    s53_etas = [_parse_positive_rational(v, f"s53_eta[{i}]") for i, v in enumerate(_req_list(p1.get("s53_multisecond_eta_ladder_q"), "s53_etas"))]
    if len(s53_etas) != 3 or not (s53_etas[0] > s53_etas[1] > s53_etas[2]):
        raise AuditError("P1_LADDER_ORDER", "S53 eta ladder must strictly decrease")
    m_pkg = _parse_positive_rational(p1.get("live_100hz_mean_pkg_mw_q"), "mean_pkg_mw")
    m_psys = _parse_positive_rational(p1.get("live_100hz_mean_psys_mw_q"), "mean_psys_mw")
    _parse_positive_rational(p1.get("live_100hz_mean_dark_inpkg_mw_q"), "mean_dark_mw")
    if m_pkg <= m_psys:
        raise AuditError("P1_PSYS_OBSTRUCTION", "psys vendor-scale obstruction violated")
    if oracle.round_q_1e6(m_pkg / m_psys) != _parse_positive_rational(p1.get("psys_vendor_scale_obstruction_ratio_r6_q"), "psys_ratio"):
        raise AuditError("P1_RATIO_MISMATCH", "pkg/psys ratio mismatch")
    if _parse_positive_rational(p1.get("schur_100hz_mean_eta_r6_q"), "schur_100hz_eta") <= s53_etas[0]:
        raise AuditError("P1_RC_OBSTRUCTION", "100 Hz Schur eta must exceed multi-second baseline")

    # Pillar 2 semantic checks
    p2 = _req_dict(sampled.get("pillar_2_hysteresis_and_yield_wall"), "pillar_2")
    l1_p50 = _parse_positive_rational(p2.get("l1_16kib_p50_cyc_per_step_q"), "l1_p50")
    l3_p50 = _parse_positive_rational(p2.get("l3_16mib_p50_cyc_per_step_q"), "l3_p50")
    dr_p50 = _parse_positive_rational(p2.get("dram_64mib_p50_cyc_per_step_q"), "dram_p50")
    if l3_p50 / l1_p50 != _parse_positive_rational(p2.get("l3_over_l1_latency_cliff_q"), "l3_cliff"):
        raise AuditError("P2_CLIFF_MISMATCH", "L3/L1 latency cliff mismatch")
    if dr_p50 / l1_p50 != _parse_positive_rational(p2.get("dram_over_l1_latency_cliff_q"), "dram_cliff"):
        raise AuditError("P2_CLIFF_MISMATCH", "DRAM/L1 latency cliff mismatch")
    if _req_int(p2.get("green_2area_tpkg_cpufan_closed"), "area_tf") == 0 or _req_int(p2.get("green_2area_tpkg_ppkg_closed"), "area_tp") == 0:
        raise AuditError("P2_ZERO_HYSTERESIS", "closed hysteresis areas must be nonzero")

    # Pillar 3 semantic checks
    p3 = _req_dict(sampled.get("pillar_3_spectral_prism_and_nulls"), "pillar_3")
    r_dram = _req_dict(p3.get("rdtsc_dram_64mib"), "p3.dram")
    r_dram_obs = [_parse_positive_rational(v, f"dram_r[{i}]") for i, v in enumerate(_req_list(r_dram.get("s39_r2_to_r5_r6_q"), "dram_r"))]
    r_dram_null = [_parse_positive_rational(v, f"dram_null[{i}]") for i, v in enumerate(_req_list(r_dram.get("s39_shuffle_null_r2_to_r5_r6_q"), "dram_null"))]
    if len(r_dram_obs) != 4 or len(r_dram_null) != 4:
        raise AuditError("P3_PRISM_LEN", "DRAM prism and shuffle-null lists must have length 4")
    if not (r_dram_obs[0] < r_dram_null[0]):
        raise AuditError("P3_DRAM_NULL", "DRAM R2 must be below its amplitude-preserving shuffle null")
    ch100 = _req_dict(p3.get("live_100hz_channels"), "p3.ch100")
    dark_r_list = _req_list(_req_dict(ch100.get("dark_inpkg_mw"), "dark").get("s39_r2_to_r5_r6_q"), "dark_r")
    if len(dark_r_list) != 4:
        raise AuditError("P3_PRISM_LEN", "dark_inpkg_mw prism list must have length 4")
    dark_r2 = _parse_positive_rational(dark_r_list[0], "dark_r2")
    if dark_r2 <= Fraction(3, 1):
        raise AuditError("P3_SUPER_NYQUIST", "dark_inpkg_mw R2 must exceed white-noise 3.0")

    # Pillar 4 semantic checks
    p4 = _req_dict(sampled.get("pillar_4_allometric_pl1_ceiling"), "pillar_4")
    wpc = [_parse_positive_rational(v, f"wpc[{i}]") for i, v in enumerate(_req_list(p4.get("work_per_core_gops_s_r6_q"), "wpc"))]
    if len(wpc) != 5 or not (wpc[0] > wpc[1] > wpc[2] > wpc[3] > wpc[4]):
        raise AuditError("P4_WPC_ORDER", "work per core must strictly decrease across p=1,2,4,6,8")
    if _parse_positive_rational(p4.get("pkg_power_spread_pct_r6_q"), "spread") >= Fraction(1, 1):
        raise AuditError("P4_PL1_FLATNESS", "PL1 ceiling spread must stay below 1%")

    # Pillar 5 semantic checks
    p5 = _req_dict(sampled.get("pillar_5_landauer_thermodynamic_gap"), "pillar_5")
    b_p8 = _req_list(p5.get("exp3_p8_landauer_ratio_bracket"), "b_p8")
    b_p1 = _req_list(p5.get("exp3_p1_landauer_ratio_bracket"), "b_p1")
    if len(b_p8) != 2 or len(b_p1) != 2:
        raise AuditError("P5_BRACKET_LEN", "Landauer brackets must have length 2")
    if not (_req_int(b_p1[0], "b_p1_lo") > _req_int(b_p8[1], "b_p8_hi") > 10**10):
        raise AuditError("P5_LANDAUER_GAP", "Landauer scale gap ordering violated")

    # Pillar 6 semantic checks
    p6 = _req_dict(sampled.get("pillar_6_universal_code_vs_weight_anisotropy"), "pillar_6")
    kl_05 = _parse_positive_rational(p6.get("qwen_05b_a16_block_h2_over_axis_wt_kl_q"), "kl_05")
    kl_15 = _parse_positive_rational(p6.get("qwen_15b_a16_block_h2_over_axis_wt_kl_q"), "kl_15")
    if not (kl_05 > Fraction(1, 1) and kl_15 < Fraction(1, 1)):
        raise AuditError("P6_CROSSOVER", "A16_BlockH2 crossover 0.5B (>1) -> 1.5B (<1) violated")
    if _req_int(p6.get("qwen_15b_regime1_axis_layers"), "r1") + _req_int(p6.get("qwen_15b_regime2_rotated_layers"), "r2") != _req_int(p6.get("qwen_15b_total_layers"), "tot"):
        raise AuditError("P6_LAYER_SUM", "Regime I + Regime II layer counts must sum to 196")

    # Anchor CS-13 citations
    anchor = _req_dict(p["anchor"], "anchor")
    if _req_str(anchor.get("provenance_tier"), "anchor.tier") != "anchor":
        raise AuditError("TIER_MISMATCH", "anchor tier mismatch")
    cites = _req_list(anchor.get("cs13_citations"), "cs13_citations")
    if len(cites) < 6:
        raise AuditError("ANCHOR_CITES_SHORT", "expected at least 6 CS-13 citations")

    # Exact bijective canonical pin (closes all unpinned-leaf & extra-key attacks)
    if oracle.canonical_json_bytes(p) != _EXPECTED_PAYLOAD_BYTES:
        raise AuditError("PAYLOAD_PIN_MISMATCH", "payload diverges from exact Track S64 oracle")

    return {
        "valid": True,
        "pillars_verified": 6,
        "s53_eta_drop_verified": True,
        "psys_vendor_scale_obstruction_verified": True,
        "stage_a_gauge_zero_drift": True,
    }


def verify_certificate_object(cert: Any) -> dict[str, Any]:
    _validate_json_tree(cert, "cert")
    c = _req_dict(cert, "cert")
    if set(c.keys()) != _CERT_KEYS:
        raise AuditError("CERT_KEYS_MISMATCH", "certificate top-level keys mismatch")
    if _req_str(c["schema"], "schema") != oracle.CERT_SCHEMA:
        raise AuditError("SCHEMA_MISMATCH", "certificate schema mismatch")
    if _req_str(c["track_id"], "track_id") != oracle.CERT_TRACK_ID:
        raise AuditError("TRACK_ID_MISMATCH", "certificate track_id mismatch")
    p_sha = _req_sha256(c["payload_sha256"], "payload_sha256")
    c_sha = _req_sha256(c["certificate_sha256"], "certificate_sha256")

    actual_p_sha = oracle.sha256_hex(oracle.canonical_json_bytes(c["payload"]))
    if not hmac.compare_digest(p_sha, actual_p_sha):
        raise AuditError("PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")

    body = {
        "schema": c["schema"],
        "track_id": c["track_id"],
        "payload_sha256": p_sha,
        "payload": c["payload"],
    }
    actual_c_sha = oracle.sha256_hex(oracle.canonical_json_bytes(body))
    if not hmac.compare_digest(c_sha, actual_c_sha):
        raise AuditError("CERT_SHA_MISMATCH", "certificate_sha256 mismatch")

    sec = secondary_audit_payload(c["payload"])
    return {
        "valid": True,
        "schema": c["schema"],
        "track_id": c["track_id"],
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "secondary_audit": sec,
    }


def check_certificate_file(cert_path: Path) -> dict[str, Any]:
    raw = read_regular_bytes_safe(cert_path)
    obj = parse_strict_json_bytes(raw, allow_floats=False)
    if oracle.canonical_json_bytes(obj) != raw:
        raise AuditError("NON_CANONICAL_BYTES", "certificate file bytes are not canonical JSON")
    res = verify_certificate_object(obj)
    res["file_sha256"] = oracle.sha256_hex(raw)
    return res


def verify_live_receipts(work_dir: Path) -> dict[str, Any]:
    """Verify disk SHA-256 receipts, Ring-0 mlos receipt, and full raw integer replay."""
    _validate_path_obj(work_dir)
    expected = oracle.PINNED_S64_DIGESTS
    file_map = {
        "granular_silicon_microprobe_c": work_dir / "granular_silicon_microprobe.c",
        "granular_silicon_capture_json": work_dir / "granular_silicon_capture.json",
        "mlos_zone_b_receipt_json": work_dir / "mlos_zone_b_receipt.json",
    }
    raw_bytes: dict[str, bytes] = {}
    for key, fpath in file_map.items():
        data = read_regular_bytes_safe(fpath)
        digest = oracle.sha256_hex(data)
        if not hmac.compare_digest(digest, expected[key]):
            raise AuditError("RECEIPT_SHA_MISMATCH", f"{key} digest mismatch")
        raw_bytes[key] = data

    # Check Ring-0 mlos Zone-B receipt (allows float timing/telemetry fields in mlos schema)
    rcp = parse_strict_json_bytes(raw_bytes["mlos_zone_b_receipt_json"], allow_floats=True)
    rcp_d = _req_dict(rcp, "mlos_receipt")
    if rcp_d.get("clean_hardware_run") is not True:
        raise AuditError("MLOS_DIRTY_RUN", "mlos receipt clean_hardware_run != true")
    if rcp_d.get("anomalies") != []:
        raise AuditError("MLOS_ANOMALIES", "mlos receipt has anomalies")
    if rcp_d.get("determinism_zone") != "B":
        raise AuditError("MLOS_ZONE_MISMATCH", "mlos receipt determinism_zone != B")
    if not hmac.compare_digest(_req_sha256(rcp_d.get("receipt_sha256"), "inner_sha"), expected["mlos_receipt_inner_sha256"]):
        raise AuditError("MLOS_INNER_SHA_MISMATCH", "mlos receipt_sha256 mismatch")
    if not hmac.compare_digest(_req_sha256(rcp_d.get("profile_sha256"), "profile_sha"), expected["mlos_profile_sha256"]):
        raise AuditError("MLOS_PROFILE_SHA_MISMATCH", "mlos profile_sha256 mismatch")

    # Strict zero-float replay of raw integer granular_silicon_capture.json
    cap = parse_strict_json_bytes(raw_bytes["granular_silicon_capture_json"], allow_floats=False)
    cap_d = _req_dict(cap, "capture")
    replayed = oracle.recompute_from_raw_capture(cap_d)
    payload = oracle.build_payload()["sampled"]

    # Cross-check every single replayed field against certified payload!
    p1 = payload["pillar_1_dark_mode_schur_and_gauge"]
    e2 = replayed["exp2"]
    for ck, rk in (
        ("live_100hz_mean_pkg_mw_q", "mean_pkg_mw_q"),
        ("live_100hz_mean_core_mw_q", "mean_core_mw_q"),
        ("live_100hz_mean_uncore_mw_q", "mean_uncore_mw_q"),
        ("live_100hz_mean_dark_inpkg_mw_q", "mean_dark_inpkg_mw_q"),
        ("live_100hz_mean_psys_mw_q", "mean_psys_mw_q"),
        ("psys_vendor_scale_obstruction_ratio_r6_q", "pkg_over_psys_vendor_scale_r6_q"),
        ("r2_psys_vs_pkg_scale_invariant_r6_q", "r2_psys_vs_pkg_r6_q"),
        ("r2_tpkg_vs_ppkg_100hz_r6_q", "r2_tpkg_vs_ppkg_r6_q"),
        ("schur_100hz_mean_eta_r6_q", "schur_100hz_mean_eta_r6_q"),
        ("schur_100hz_raw_r2_r6_q", "schur_100hz_raw_r2_r6_q"),
        ("schur_100hz_res_rho2_r6_q", "schur_100hz_res_rho2_r6_q"),
        ("live_11ch_stage_a_gauge_exact_zero", "live_11ch_stage_a_gauge_exact_zero"),
    ):
        if p1[ck] != e2[rk]:
            raise AuditError("REPLAY_MISMATCH", f"Pillar-1 replay mismatch on {ck}")

    p2 = payload["pillar_2_hysteresis_and_yield_wall"]
    e1 = replayed["exp1"]
    for k in (
        "green_2area_tpkg_cpufan_open",
        "green_2area_tpkg_cpufan_closed",
        "green_2area_tpkg_ppkg_open",
        "green_2area_tpkg_ppkg_closed",
        "ramp_up_2c_mean_tpkg_mc_q",
        "ramp_down_2c_mean_tpkg_mc_q",
        "cpu_fan_min_rpm",
        "cpu_fan_max_rpm",
    ):
        if p2[k] != e2[k]:
            raise AuditError("REPLAY_MISMATCH", f"Pillar-2 replay mismatch on {k}")
    for pk, reg_name, ek in (
        ("l1_16kib_p50_cyc_per_step_q", "l1_16kib_quiescent", "p50_cyc_per_step_q"),
        ("l3_16mib_p50_cyc_per_step_q", "l3_16mib_boundary", "p50_cyc_per_step_q"),
        ("dram_64mib_p50_cyc_per_step_q", "dram_64mib_chase", "p50_cyc_per_step_q"),
        ("l1_max_avalanche_len", "l1_16kib_quiescent", "max_avalanche_len"),
        ("l3_max_avalanche_len", "l3_16mib_boundary", "max_avalanche_len"),
        ("dram_max_avalanche_len", "dram_64mib_chase", "max_avalanche_len"),
    ):
        if p2[pk] != e1[reg_name][ek]:
            raise AuditError("REPLAY_MISMATCH", f"Pillar-2 exp1 replay mismatch on {pk}")

    p3 = payload["pillar_3_spectral_prism_and_nulls"]
    if (
        p3["rdtsc_l1_16kib"] != e1["l1_16kib_quiescent"]
        or p3["rdtsc_l3_16mib"] != e1["l3_16mib_boundary"]
        or p3["rdtsc_dram_64mib"] != e1["dram_64mib_chase"]
        or p3["live_100hz_channels"] != e2["channels_spectral"]
    ):
        raise AuditError("REPLAY_MISMATCH", "Pillar-3 spectral replay mismatch")

    p4 = payload["pillar_4_allometric_pl1_ceiling"]
    e3 = replayed["exp3"]
    for k in (
        "core_counts",
        "pkg_power_w_r6_q",
        "work_gops_s_r6_q",
        "work_per_core_gops_s_r6_q",
        "energy_pj_per_op_r6_q",
        "pkg_power_spread_pct_r6_q",
        "work_8c_over_1c_r6_q",
        "energy_per_op_1c_over_8c_r6_q",
        "d2_work_at_p4_r6_q",
        "d2_work_at_p6_r6_q",
    ):
        if p4[k] != e3[k]:
            raise AuditError("REPLAY_MISMATCH", f"Pillar-4 replay mismatch on {k}")

    p5 = payload["pillar_5_landauer_thermodynamic_gap"]
    for pk, ek in (
        ("exp3_p1_temp_k_q", "p1_temp_k_q"),
        ("exp3_p8_temp_k_q", "p8_temp_k_q"),
        ("exp3_p1_landauer_ratio_bracket", "p1_landauer_ratio_bracket"),
        ("exp3_p8_landauer_ratio_bracket", "p8_landauer_ratio_bracket"),
    ):
        if p5[pk] != e3[ek]:
            raise AuditError("REPLAY_MISMATCH", f"Pillar-5 replay mismatch on {pk}")

    return {
        "all_verified": True,
        "files_verified": len(file_map),
        "raw_integer_replay_exact": True,
        "live_11ch_stage_a_gauge_exact_zero": e2["live_11ch_stage_a_gauge_exact_zero"],
    }


# ---------------------------------------------------------------------------
# Fail-Closed CLI Entry Point
# ---------------------------------------------------------------------------

def _validate_cli_path(raw_arg: str) -> Path:
    if not raw_arg or raw_arg.startswith("-"):
        raise AuditError("INVALID_CLI_ARGS", f"invalid path argument: {raw_arg}")
    return Path(raw_arg)


def _parse_cli_args(argv: Any) -> dict[str, Any]:
    if type(argv) not in (list, tuple):
        raise AuditError("INVALID_CLI_ARGS", "argv must be a sequence of strict str")
    for item in argv:
        if type(item) is not str:
            raise AuditError("INVALID_CLI_ARGS", "argv must be a sequence of strict str")
    opts: dict[str, Any] = {
        "standalone": False,
        "write": None,
        "check": None,
        "verify_receipts": None,
        "json": False,
    }
    i = 0
    n = len(argv)
    while i < n:
        tok = argv[i]
        if tok == "--standalone":
            opts["standalone"] = True
            i += 1
        elif tok == "--json":
            opts["json"] = True
            i += 1
        elif tok == "--write":
            if i + 1 >= n:
                raise AuditError("INVALID_CLI_ARGS", "--write requires a path")
            opts["write"] = _validate_cli_path(argv[i + 1])
            i += 2
        elif tok == "--check":
            if i + 1 >= n:
                raise AuditError("INVALID_CLI_ARGS", "--check requires a path")
            opts["check"] = _validate_cli_path(argv[i + 1])
            i += 2
        elif tok == "--verify-receipts":
            if i + 1 < n and not argv[i + 1].startswith("-"):
                opts["verify_receipts"] = _validate_cli_path(argv[i + 1])
                i += 2
            else:
                opts["verify_receipts"] = Path(".")
                i += 1
        else:
            raise AuditError("INVALID_CLI_ARGS", f"unknown argument: {tok}")
    if opts["write"] is None and opts["check"] is None and opts["verify_receipts"] is None:
        opts["standalone"] = True
    return opts


def main(argv: Any = None) -> int:
    try:
        args_in = sys.argv[1:] if argv is None else argv
        opts = _parse_cli_args(args_in)
        out: dict[str, Any] = {}
        if opts["standalone"]:
            cert = oracle.build_certificate()
            verify_certificate_object(cert)
            sys.stdout.write(oracle.canonical_json_bytes(cert).decode("utf-8"))
            return 0
        if opts["write"] is not None:
            cert = oracle.build_certificate()
            verify_certificate_object(cert)
            raw = oracle.canonical_json_bytes(cert)
            write_regular_bytes_atomic_0600(opts["write"], raw)
            out["written"] = True
            out["file_sha256"] = oracle.sha256_hex(raw)
            out["certificate_sha256"] = cert["certificate_sha256"]
        if opts["check"] is not None:
            out["check"] = check_certificate_file(opts["check"])
        if opts["verify_receipts"] is not None:
            out["receipts"] = verify_live_receipts(opts["verify_receipts"])
        out["valid"] = True
        sys.stdout.write(oracle.canonical_json_bytes(out).decode("utf-8"))
        return 0
    except AuditError as exc:
        err = {"valid": False, "error_code": exc.code, "error": exc.message}
        sys.stdout.write(oracle.canonical_json_bytes(err).decode("utf-8"))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
