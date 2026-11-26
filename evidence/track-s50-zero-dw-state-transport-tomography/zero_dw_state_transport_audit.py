#!/usr/bin/env python3
"""Strict Fail-Closed Independent Secondary Audit & CLI for Zero-Delta-W State-Transport Tomography.

Provides:
  - Division-free independent pure-Z/Q algebraic verification of all pillars
    plus bijective strict-typed full-schema equality under secondary_audit_payload;
  - Symlink-hardened O_DIRECTORY | O_NOFOLLOW dir_fd file I/O (including logical
    $PWD verification, streaming read cap, 0o600 O_EXCL + fsync + pre-replace
    st_nlink==1 + atomic dir_fd os.replace);
  - Fail-closed CLI supporting zero-arg, --standalone --json, --write <path>,
    and --check <path> with structured JSON errors and zero raw tracebacks.

Pure Python 3 standard library int / Fraction only. Zero floats, zero bare
asserts, zero mathematical RNG, zero external dependencies.
"""

from __future__ import annotations

import errno
from fractions import Fraction
import os
import secrets
import stat
import sys
import threading
from typing import Any

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.append(_SCRIPT_DIR)

from zero_dw_state_transport_oracle import (
    MAX_JSON_BYTES,
    MAX_READ_CAP_BYTES,
    NOVELTY_TIER,
    ORACLE_CLASS,
    SCHEMA_VERSION,
    TRACK_ID,
    ZeroDwStateTransportError,
    build_standalone_certificate,
    canonical_json_bytes,
    parse_exact_rational,
    parse_strict_json_text,
    require_exact_bool,
    require_exact_int,
    require_exact_str,
    require_ok,
    validate_json_tree,
    verify_certificate_payload,
)

_TMP_COUNTER_LOCK = threading.Lock()
_TMP_COUNTER = 0
_MAX_EEXIST_RETRIES = 32
_READ_CHUNK_BYTES = 65_536
_CACHED_EXPECTED_PAYLOAD: dict[str, Any] | None = None


def _expected_payload() -> dict[str, Any]:
    global _CACHED_EXPECTED_PAYLOAD
    if _CACHED_EXPECTED_PAYLOAD is None:
        _CACHED_EXPECTED_PAYLOAD = build_standalone_certificate()["payload"]
    return _CACHED_EXPECTED_PAYLOAD


def _next_tmp_token() -> str:
    global _TMP_COUNTER
    with _TMP_COUNTER_LOCK:
        _TMP_COUNTER += 1
        seq = _TMP_COUNTER
    return f"{os.getpid()}.{seq}.{secrets.token_hex(8)}"


def _require_dict_field(obj: dict[str, Any], key: str, label: str) -> dict[str, Any]:
    require_ok(key in obj, "MISSING_FIELD", f"{label}.{key} missing")
    val = obj[key]
    require_ok(type(val) is dict, "FIELD_NOT_OBJECT", f"{label}.{key} must be dict")
    return val


def _require_list_field(obj: dict[str, Any], key: str, label: str) -> list[Any]:
    require_ok(key in obj, "MISSING_FIELD", f"{label}.{key} missing")
    val = obj[key]
    require_ok(type(val) is list, "FIELD_NOT_LIST", f"{label}.{key} must be list")
    return val


def _parse_rat_field(obj: dict[str, Any], key: str, label: str) -> Fraction:
    require_ok(key in obj, "MISSING_FIELD", f"{label}.{key} missing")
    return parse_exact_rational(obj[key], f"{label}.{key}")


def _exact_json_tree_equal(actual: Any, expected: Any, label: str = "payload") -> None:
    """Iterative bijective strict-typed equality (zero recursion, zero subclasses, zero extra keys)."""
    stack: list[tuple[Any, Any, str]] = [(actual, expected, label)]
    while stack:
        a, b, path = stack.pop()
        require_ok(type(a) is type(b), "SCHEMA_TYPE_MISMATCH", f"{path}: expected {type(b).__name__}")
        t = type(b)
        if t is dict:
            require_ok(frozenset(a.keys()) == frozenset(b.keys()), "SCHEMA_KEYS_MISMATCH", f"{path}: key set mismatch")
            for k in b:
                stack.append((a[k], b[k], f"{path}.{k}"))
        elif t is list:
            require_ok(len(a) == len(b), "SCHEMA_LIST_LEN_MISMATCH", f"{path}: list length mismatch")
            for idx in range(len(b)):
                stack.append((a[idx], b[idx], f"{path}[{idx}]"))
        else:
            require_ok(a == b, "PAYLOAD_VALUE_MISMATCH", f"{path}: value mismatch")


def verify_algebraic_invariants(payload: Any) -> dict[str, Any]:
    """Independent division-free pure-Z/Q cross-check of all three mathematical pillars."""
    require_ok(type(payload) is dict, "PAYLOAD_NOT_OBJECT", "payload must be exact dict")
    validate_json_tree(payload, "payload")

    # Pillar 1: GDN-2 Channel-2B (+2 -> -83/25, dm = -133/25, ||Delta S||_F^2 = 212/5 >= 106/5, rank=1, S4=1)
    p1 = _require_dict_field(payload, "pillar1_gdn2_zero_dw_state_transport", "payload")
    ch2b = _require_dict_field(p1, "channel2b_tomography", "p1")
    m0 = _parse_rat_field(ch2b, "margin_before", "p1.ch2b")
    m1 = _parse_rat_field(ch2b, "margin_after", "p1.ch2b")
    dm = _parse_rat_field(ch2b, "margin_delta", "p1.ch2b")
    frob = _parse_rat_field(ch2b, "delta_s_frob_norm_sq", "p1.ch2b")
    s4 = _parse_rat_field(ch2b, "delta_s_schatten_s4", "p1.ch2b")
    cs_lb = _parse_rat_field(p1, "universal_capacity_lb", "p1")
    parseval = _parse_rat_field(p1, "l5_parseval_error_sq", "p1")
    cs_lhs = _parse_rat_field(ch2b, "cauchy_schwarz_margin_sq", "p1.ch2b")
    cs_rhs = _parse_rat_field(ch2b, "cauchy_schwarz_upper_bound", "p1.ch2b")

    require_ok(m0 == Fraction(2, 1), "ALGEBRAIC_P1_MARGIN", "clean margin must equal 2")
    require_ok(m1 == Fraction(-83, 25), "ALGEBRAIC_P1_MARGIN", "poisoned margin must equal -83/25")
    require_ok(m1 - m0 == dm, "ALGEBRAIC_P1_MARGIN", "margin_delta != margin_after - margin_before")
    require_ok(frob == Fraction(212, 5), "ALGEBRAIC_P1_FROB", "GDN-2 frob_norm_sq must equal 212/5")
    require_ok(cs_lb == Fraction(106, 5), "ALGEBRAIC_P1_CAPACITY", "universal capacity lb must equal 106/5")
    require_ok(parseval == frob, "ALGEBRAIC_P1_PARSEVAL", "Parseval error must equal frob_norm_sq")
    require_ok(s4 == Fraction(1, 1), "ALGEBRAIC_P1_RANK1", "rank-1 S4 must equal 1")
    require_ok(dm * dm == cs_lhs, "ALGEBRAIC_P1_CS", "cauchy_schwarz_margin_sq != dm^2")
    require_ok(cs_lhs <= cs_rhs, "ALGEBRAIC_P1_CS", "Cauchy-Schwarz bound violated")

    # Pillar 2: Viscoplastic ReLU wall advection (1 -> 4, +1/2 -> -5/8) & S^2 Gauss-Stokes (+13 - 13 = 0 vs -4)
    p2 = _require_dict_field(payload, "pillar2_yield_wall_and_s2_cohomology", "payload")
    wall = _require_dict_field(p2, "yield_wall_advection_zero_dw", "p2")
    x0 = _parse_rat_field(wall, "wall_x_t0", "p2.wall")
    x1 = _parse_rat_field(wall, "wall_x_t1", "p2.wall")
    dx = _parse_rat_field(wall, "wall_displacement", "p2.wall")
    require_ok(x0 == Fraction(1, 1), "ALGEBRAIC_P2_WALL", "wall_x_t0 must equal 1")
    require_ok(x1 == Fraction(4, 1), "ALGEBRAIC_P2_WALL", "wall_x_t1 must equal 4")
    require_ok(x1 - x0 == dx, "ALGEBRAIC_P2_WALL", "wall_displacement != x1 - x0")

    coh = _require_dict_field(p2, "s2_cohomological_obstruction", "p2")
    gs_pos = require_exact_int(coh.get("gauss_stokes_positive_sum"), "p2.coh.pos")
    gs_neg = require_exact_int(coh.get("gauss_stokes_negative_sum"), "p2.coh.neg")
    gs_net = require_exact_int(coh.get("gauss_stokes_net_sum"), "p2.coh.net")
    relu_div = require_exact_int(coh.get("relu_global_div_residual"), "p2.coh.relu_div")
    comm_sum = require_exact_int(coh.get("commutator_relu_delta1_sum"), "p2.coh.comm_sum")
    require_ok(gs_pos == 13, "ALGEBRAIC_P2_GS", "Gauss-Stokes positive sum must equal 13")
    require_ok(gs_neg == -13, "ALGEBRAIC_P2_GS", "Gauss-Stokes negative sum must equal -13")
    require_ok(gs_pos + gs_neg == gs_net, "ALGEBRAIC_P2_GS", "Gauss-Stokes net sum != pos + neg")
    require_ok(relu_div == -4, "ALGEBRAIC_P2_RELU", "ReLU divergence residual must equal -4")
    require_ok(comm_sum == 13, "ALGEBRAIC_P2_COMM", "ReLU-delta1 commutator sum must equal 13")

    # Pillar 3: Iso-Frobenius blindness (32x toy, 75,968x analytical) & 4-channel airlock
    p3 = _require_dict_field(payload, "pillar3_iso_frobenius_and_4ch_airlock", "payload")
    iso = _require_dict_field(p3, "iso_frobenius_state_separation", "p3")
    iso_gap = _parse_rat_field(iso, "frobenius_energy_gap", "p3.iso")
    require_ok(iso_gap == 0, "ALGEBRAIC_P3_ISO", "state iso-Frobenius gap must equal 0")

    dpi = _require_dict_field(p3, "dpi_iso_frobenius_weight_anchor", "p3")
    v_rows = require_exact_int(dpi.get("analytical_vocab_rows"), "p3.dpi.vocab_rows", min_val=2)
    two_row_conc = _parse_rat_field(dpi, "analytical_two_row_min_concentration", "p3.dpi")
    sep_32 = _parse_rat_field(dpi, "toy_64x16_concentration_ratio_factor", "p3.dpi")
    require_ok(two_row_conc * 2 == Fraction(v_rows, 1), "ALGEBRAIC_P3_DPI", "2 * min_conc != vocab_rows")
    require_ok(two_row_conc == Fraction(75_968, 1), "ALGEBRAIC_P3_DPI", "analytical min conc must equal 75968")
    require_ok(sep_32 == Fraction(32, 1), "ALGEBRAIC_P3_DPI", "toy separation factor must equal 32")

    air = _require_dict_field(p3, "four_channel_state_transport_airlock", "p3")
    benigns = _require_list_field(air, "benign_controls", "p3.air")
    negs = _require_list_field(air, "negative_controls", "p3.air")
    require_ok(len(benigns) == 3, "ALGEBRAIC_P3_AIRLOCK", "expected 3 benign controls")
    require_ok(len(negs) == 5, "ALGEBRAIC_P3_AIRLOCK", "expected 5 negative controls")
    for idx, item in enumerate(benigns):
        require_ok(type(item) is dict, "ALGEBRAIC_P3_AIRLOCK", f"benign[{idx}] must be dict")
        require_ok(item.get("airlock_4ch_decision") == "ALLOW", "ALGEBRAIC_P3_AIRLOCK", f"benign[{idx}] must ALLOW")
    for idx, item in enumerate(negs):
        require_ok(type(item) is dict, "ALGEBRAIC_P3_AIRLOCK", f"neg[{idx}] must be dict")
        require_ok(item.get("airlock_4ch_decision") == "DENY", "ALGEBRAIC_P3_AIRLOCK", f"neg[{idx}] must DENY")

    return {
        "algebraic_checks_passed": True,
        "p1_margin_flip": ["2", "-83/25"],
        "p2_wall_advection": ["1", "4"],
        "p2_gauss_stokes_vs_relu": [0, -4],
        "p3_dpi_analytical_factor": "75968",
    }


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Independent fail-closed secondary audit: JSON validation + algebraic cross-checks + exact schema match."""
    validate_json_tree(payload, "payload")
    alg = verify_algebraic_invariants(payload)
    _exact_json_tree_equal(payload, _expected_payload(), "payload")
    return {
        "secondary_audit_passed": True,
        "oracle_class": ORACLE_CLASS,
        "novelty_tier": NOVELTY_TIER,
        "algebraic_summary": alg,
    }


def verify_certificate_dict(cert: Any, *, full_replay: bool = True) -> dict[str, Any]:
    """Combined fail-closed verification (oracle structural/digest/replay + independent secondary audit)."""
    replay_flag = require_exact_bool(full_replay, "full_replay")
    primary = verify_certificate_payload(cert, full_replay=replay_flag)
    secondary = secondary_audit_payload(cert["payload"])
    return {
        "valid": True,
        "full_replay": replay_flag,
        "track_id": primary["track_id"],
        "payload_sha256": primary["payload_sha256"],
        "certificate_sha256": primary["certificate_sha256"],
        "secondary_audit_passed": secondary["secondary_audit_passed"],
    }


# ---------------------------------------------------------------------------
# Symlink-Hardened Atomic dir_fd File I/O
# ---------------------------------------------------------------------------

_DARWIN_SYSTEM_ROOT_ALIASES: dict[str, tuple[str, ...]] = {
    "var": ("private/var", "/private/var"),
    "tmp": ("private/tmp", "/private/tmp"),
    "etc": ("private/etc", "/private/etc"),
}


def _normalize_darwin_system_prefix(components: list[str]) -> list[str]:
    """Map verified root-owned macOS /var, /tmp, /etc ancestor prefixes to /private/*."""
    if sys.platform != "darwin":
        return components
    if not components or ".." in components:
        return components
    head = components[0]
    allowed_targets = _DARWIN_SYSTEM_ROOT_ALIASES.get(head)
    if allowed_targets is None:
        return components
    alias = "/" + head
    try:
        st = os.lstat(alias)
        if not stat.S_ISLNK(st.st_mode) or st.st_uid != 0:
            return components
        target = os.readlink(alias)
    except OSError:
        return components
    if target not in allowed_targets:
        return components
    return ["private", *components]


def _validate_raw_path(raw_path: Any, label: str = "path") -> str:
    s = require_exact_str(raw_path, label)
    require_ok("\x00" not in s, "INVALID_PATH_NUL", f"{label} contains NUL byte")
    return s


def _open_dir_chain_nofollow(components: list[str], start_fd: int) -> int:
    """Walk directory components strictly via O_RDONLY | O_DIRECTORY | O_NOFOLLOW."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    cur_fd = start_fd
    try:
        for comp in components:
            try:
                next_fd = os.open(comp, flags, dir_fd=cur_fd)
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise ZeroDwStateTransportError("SYMLINK_FORBIDDEN", f"symlink or non-dir ancestor: {comp}") from exc
                raise ZeroDwStateTransportError("DIR_OPEN_ERROR", f"cannot open directory {comp}: {exc}") from exc
            os.close(cur_fd)
            cur_fd = next_fd
        return cur_fd
    except BaseException:
        os.close(cur_fd)
        raise


def _check_cwd_and_logical_pwd_nofollow() -> int:
    """Verify current working directory exists and neither real CWD nor logical $PWD has symlink ancestors."""
    try:
        cwd_st = os.stat(".")
        real_cwd = os.getcwd()
    except OSError as exc:
        raise ZeroDwStateTransportError("CWD_UNAVAILABLE", f"working directory unavailable: {exc}") from exc

    # Verify real CWD ancestor chain from /
    root_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    real_parts = _normalize_darwin_system_prefix([p for p in real_cwd.split("/") if p])
    real_fd = _open_dir_chain_nofollow(real_parts, root_fd)

    # Also verify logical $PWD when it refers to the same directory (detects symlinked $PWD)
    logical_pwd = os.environ.get("PWD", "")
    if logical_pwd.startswith("/"):
        try:
            pwd_st = os.stat(logical_pwd)
        except OSError:
            pwd_st = None
        if pwd_st is not None and (pwd_st.st_dev, pwd_st.st_ino) == (cwd_st.st_dev, cwd_st.st_ino):
            pwd_parts = _normalize_darwin_system_prefix([p for p in logical_pwd.split("/") if p])
            try:
                pwd_root = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
                pwd_fd = _open_dir_chain_nofollow(pwd_parts, pwd_root)
                os.close(pwd_fd)
            except BaseException:
                os.close(real_fd)
                raise

    return real_fd


def _open_parent_dir_fd_nofollow(raw_path: Any) -> tuple[int, str]:
    """Resolve parent directory strictly without following symlinks and return (dir_fd, leaf_name)."""
    s = _validate_raw_path(raw_path, "path")
    require_ok(not s.endswith("/"), "PATH_IS_DIRECTORY", "path must refer to a file, not a directory")
    is_abs = s.startswith("/")
    raw_parts = [p for p in s.split("/") if p and p != "."]
    require_ok(len(raw_parts) > 0, "INVALID_PATH", "path has no file component")
    leaf = raw_parts[-1]
    require_ok(leaf != "..", "INVALID_LEAF", "leaf component cannot be '..'")
    ancestors = raw_parts[:-1]

    if is_abs:
        ancestors = _normalize_darwin_system_prefix(ancestors)
        start_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    else:
        start_fd = _check_cwd_and_logical_pwd_nofollow()

    parent_fd = _open_dir_chain_nofollow(ancestors, start_fd)
    return parent_fd, leaf


def read_regular_file_bytes_strict(raw_path: Any, *, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    """Read a regular file via dir_fd + O_NOFOLLOW + O_NONBLOCK with streaming size enforcement."""
    require_exact_int(max_bytes, "max_bytes", min_val=1, max_val=MAX_READ_CAP_BYTES)
    parent_fd, leaf = _open_parent_dir_fd_nofollow(raw_path)
    fd = -1
    try:
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise ZeroDwStateTransportError("SYMLINK_FORBIDDEN", f"refusing symlink leaf: {leaf}") from exc
            raise ZeroDwStateTransportError("FILE_READ_ERROR", f"cannot open file {leaf}: {exc}") from exc

        st = os.fstat(fd)
        require_ok(stat.S_ISREG(st.st_mode), "NON_REGULAR_FILE", f"{leaf} is not a regular file")
        chunks: list[bytes] = []
        total = 0
        while True:
            try:
                chunk = os.read(fd, _READ_CHUNK_BYTES)
            except OSError as exc:
                raise ZeroDwStateTransportError("FILE_READ_ERROR", f"read failed on {leaf}: {exc}") from exc
            if not chunk:
                break
            total += len(chunk)
            require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"{leaf} exceeds {max_bytes} bytes")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(parent_fd)


def _assert_target_safe_for_replace(parent_fd: int, leaf: str) -> None:
    try:
        tgt_st = os.lstat(leaf, dir_fd=parent_fd)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ZeroDwStateTransportError("FILE_STAT_ERROR", f"cannot stat target {leaf}: {exc}") from exc
    require_ok(not stat.S_ISLNK(tgt_st.st_mode), "SYMLINK_FORBIDDEN", f"target {leaf} is symlink")
    require_ok(stat.S_ISREG(tgt_st.st_mode), "NON_REGULAR_FILE", f"target {leaf} is not a regular file")
    require_ok(tgt_st.st_nlink <= 1, "HARDLINK_FORBIDDEN", f"target {leaf} has st_nlink > 1")


def atomic_write_regular_file_0600(raw_path: Any, data: Any) -> None:
    """Atomically write bytes to a regular file with 0o600 mode, O_EXCL temp, fsync, and hardlink defense."""
    require_ok(type(data) is bytes, "INVALID_WRITE_DATA", "data must be exact bytes")
    parent_fd, leaf = _open_parent_dir_fd_nofollow(raw_path)
    tmp_name: str | None = None
    tmp_fd = -1
    try:
        _assert_target_safe_for_replace(parent_fd, leaf)

        # Create unique 0o600 temp sibling via O_CREAT | O_EXCL | O_NOFOLLOW | O_NONBLOCK
        open_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK
        for _ in range(_MAX_EEXIST_RETRIES):
            cand = f".{leaf}.tmp.{_next_tmp_token()}"
            try:
                tmp_fd = os.open(cand, open_flags, 0o600, dir_fd=parent_fd)
                tmp_name = cand
                break
            except FileExistsError:
                continue
            except OSError as exc:
                raise ZeroDwStateTransportError("TMP_CREATE_ERROR", f"cannot create temp file: {exc}") from exc
        require_ok(tmp_name is not None, "TMP_CREATE_EXHAUSTED", "exhausted temp file retries")

        # Enforce 0o600 explicitly regardless of process umask
        os.fchmod(tmp_fd, 0o600)
        view = memoryview(data)
        written = 0
        while written < len(view):
            n = os.write(tmp_fd, view[written:])
            require_ok(n > 0, "SHORT_WRITE", "os.write returned 0 bytes")
            written += n
        os.fsync(tmp_fd)

        # Pre-replace hardlink guard on temp file
        tmp_st = os.fstat(tmp_fd)
        require_ok(tmp_st.st_nlink == 1, "HARDLINK_FORBIDDEN", "temp file hardlinked before replace")
        os.close(tmp_fd)
        tmp_fd = -1

        # Re-check target immediately before replace (shrinks rename/hardlink race window)
        _assert_target_safe_for_replace(parent_fd, leaf)

        os.replace(tmp_name, leaf, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        tmp_name = None
        os.fsync(parent_fd)
    except ZeroDwStateTransportError:
        raise
    except OSError as exc:
        raise ZeroDwStateTransportError("ATOMIC_WRITE_ERROR", f"atomic write failed: {exc}") from exc
    finally:
        if tmp_fd >= 0:
            os.close(tmp_fd)
        if tmp_name is not None:
            try:
                os.unlink(tmp_name, dir_fd=parent_fd)
            except OSError:
                pass
        os.close(parent_fd)


def write_certificate_file(path: Any) -> dict[str, Any]:
    cert = build_standalone_certificate()
    raw = canonical_json_bytes(cert)
    atomic_write_regular_file_0600(path, raw)
    return {
        "written": True,
        "track_id": TRACK_ID,
        "bytes": len(raw),
        "payload_sha256": cert["payload_sha256"],
        "certificate_sha256": cert["certificate_sha256"],
    }


def check_certificate_file(path: Any, *, full_replay: bool = True) -> dict[str, Any]:
    raw = read_regular_file_bytes_strict(path, max_bytes=MAX_JSON_BYTES)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ZeroDwStateTransportError("INVALID_UTF8", f"file is not valid UTF-8: {exc}") from exc
    cert = parse_strict_json_text(text, require_object=True, max_bytes=MAX_JSON_BYTES)
    require_ok(
        raw == canonical_json_bytes(cert),
        "NON_CANONICAL_JSON_BYTES",
        "certificate file must be exact canonical single-line LF-only ASCII JSON",
    )
    return verify_certificate_dict(cert, full_replay=full_replay)


# ---------------------------------------------------------------------------
# Fail-Closed Strict CLI
# ---------------------------------------------------------------------------

def _validate_cli_path_arg(arg: str, flag_name: str) -> str:
    s = _validate_raw_path(arg, flag_name)
    require_ok(not s.startswith("-"), "FLAG_LIKE_PATH", f"{flag_name} path must not start with '-'")
    return s


def _parse_cli_args(argv: Any) -> tuple[str, str | None]:
    require_ok(type(argv) is list, "INVALID_ARGV", "argv must be exact list")
    cleaned: list[str] = []
    for idx, tok in enumerate(argv):
        cleaned.append(require_exact_str(tok, f"argv[{idx}]"))

    if len(cleaned) == 0:
        return ("emit", None)
    if cleaned == ["--standalone", "--json"]:
        return ("emit", None)
    if len(cleaned) == 2 and cleaned[0] == "--write":
        return ("write", _validate_cli_path_arg(cleaned[1], "--write"))
    if len(cleaned) == 2 and cleaned[0] == "--check":
        return ("check", _validate_cli_path_arg(cleaned[1], "--check"))
    raise ZeroDwStateTransportError(
        "INVALID_CLI_ARGS",
        "supported modes: (none) | --standalone --json | --write <path> | --check <path>",
    )


def main(argv: Any = None) -> int:
    raw_argv = sys.argv[1:] if argv is None else argv
    try:
        mode, path = _parse_cli_args(raw_argv)
        if mode == "emit":
            out = canonical_json_bytes(build_standalone_certificate()).decode("ascii")
        elif mode == "write":
            out = canonical_json_bytes(write_certificate_file(path)).decode("ascii")
        else:
            out = canonical_json_bytes(check_certificate_file(path, full_replay=True)).decode("ascii")
        sys.stdout.write(out)
        return 0
    except ZeroDwStateTransportError as exc:
        err_obj = {"valid": False, "error_code": exc.code, "message": exc.message}
        sys.stderr.write(canonical_json_bytes(err_obj).decode("ascii"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
