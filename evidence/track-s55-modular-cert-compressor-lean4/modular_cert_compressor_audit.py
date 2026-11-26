#!/usr/bin/env python3
"""Hardened Standalone CLI, Full Pure-Z/Q Replay, Deep Secondary Auditor,
and Live Lean 4.36.0 Companion Verifier for the Modular Certificate Compressor.

100% pure Python 3 stdlib, zero IEEE-754 floats, zero bare asserts, zero `.isdigit()`,
zero `os.path.islink`, zero mathematical RNG (`secrets.token_hex` used strictly for
collision-free atomic temp filenames).
"""
from __future__ import annotations

import errno
from fractions import Fraction
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
from typing import Any

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import modular_cert_compressor_oracle as oracle  # noqa: E402

MAX_JSON_BYTES = oracle.MAX_JSON_BYTES
MAX_ALLOWED_CAP_BYTES = 64 * 1024 * 1024
_READ_CHUNK_BYTES = 65_536
_EXACT_PATH_TYPES = (Path, type(Path()))
_DIR_OPEN_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_TEMP_NAME_LOCK = threading.Lock()
_TEMP_COUNTER = 0

_CERT_KEYS = frozenset({"schema_version", "track_id", "payload_sha256", "certificate_sha256", "payload"})
_PAYLOAD_KEYS = frozenset({
    "track_id",
    "portal_ref",
    "pillar1_modular_hodge_compression",
    "pillar2_adversarial_cheat_blocking",
    "pillar3_lean4_anti_bypass_and_soundness",
    "pillar4_cs13_honest_scope",
    "summary",
})
_P1_KEYS = frozenset({
    "case_id",
    "cleared_scale",
    "q_exponent",
    "mod_prime",
    "monomial_count",
    "cleared_7f_coeff_sum",
    "f_coeff_sum_q",
    "substituted_f_monomial_count",
    "substituted_f_odd_s",
    "substituted_f_odd_t",
    "substituted_a_monomial_count",
    "substituted_a_odd_s",
    "substituted_a_odd_t",
    "det_tau_x",
    "det_tau_y",
    "det_tau_xy",
    "mod5_nonzero_terms",
    "mod5_unique_origin_smooth",
    "compressed_packet_bytes",
    "compressed_packet_sha256",
    "deepmind_ram_gb_envelope",
    "compression_ratio_vs_233gb_q",
    "compression_ratio_gt_20m",
})
_P2_KEYS = frozenset({
    "rank1_honest_exact_rank",
    "rank1_all_2x2_minors_zero",
    "unsat_bqs_boolean_witness_count",
    "rank2_sos_exact_rank",
    "rank2_sos_passes_unsat_moments",
    "rank2_sos_all_15_minors_nonneg",
    "rank2_sos_principal_minors",
    "rank2_sos_witness_minor_02",
    "rank2_sos_minor_mod101",
    "rank2_sos_blocked_by_verifier",
    "polya_total_patterns",
    "polya_f2_collapse_count",
    "polya_z_valid_count",
    "polya_max_perm_matches_out_of_6",
    "hollow_packet_tamper_rejected",
    "non_canonical_unit_den_rejected",
    "zero_den_rejected",
    "f2_freshman_dream_holds",
    "z_carry_cross_term_delta",
})
_P2_MINOR_KEYS = frozenset({"size_1", "size_2", "size_3", "size_4"})
_P3_KEYS = frozenset({
    "lean_companion_filename",
    "lean_companion_sha256",
    "lean_companion_theorem_count",
    "lean_companion_theorems",
    "forbidden_token_count",
    "positive_controls_total",
    "positive_controls_passed",
    "adversarial_fixtures_total",
    "adversarial_fixtures_rejected",
})
_P4_KEYS = frozenset({
    "novelty_tier",
    "oracle_class",
    "max_int_bits_exact_cap",
    "max_int_digits_preparse_ceiling",
    "measured_live_pequalnp_desk_submission",
    "measured_live_deepmind_233gb_comparator",
    "zero_trust_path_floats",
    "zero_bare_asserts",
    "zero_mathematical_rng",
    "prior_literature_n0",
})
_SUMMARY_KEYS = frozenset({"all_pillars_verified", "target_max_cert_bytes"})
_STANDARD_LEAN4_AXIOMS: frozenset[str] = frozenset({"propext", "Classical.choice", "Quot.sound"})
_AXIOM_BLOCK_RE = re.compile(
    r"'([^']+)'\s+(?:(does not depend on any axioms)|depends on axioms:\s*\[([^\]]*)\])",
    flags=re.DOTALL,
)
_DARWIN_SYSTEM_ROOT_ALIASES: tuple[tuple[str, str], ...] = (
    ("/var", "/private/var"),
    ("/tmp", "/private/tmp"),
    ("/etc", "/private/etc"),
)


# ---------------------------------------------------------------------------
# Darwin Alias Normalization, Atomic dir_fd Traversal & Durable 0o600 Write
# ---------------------------------------------------------------------------

def _coerce_exact_path(path: Any, name: str) -> Path:
    if type(path) is str:
        s = oracle.require_exact_str(path, name)
        if "\x00" in s:
            raise oracle.ModularCertError("INVALID_PATH", f"{name} must not contain NUL")
        if s.endswith("/"):
            raise oracle.ModularCertError("INVALID_FILENAME", f"trailing slash refused: {s!r}")
        return Path(s)
    if type(path) in _EXACT_PATH_TYPES:
        raw = oracle.require_exact_str(str(path), name)
        if "\x00" in raw:
            raise oracle.ModularCertError("INVALID_PATH", f"{name} must not contain NUL")
        return path
    raise oracle.ModularCertError("INVALID_PATH_TYPE", f"{name} must be str or Path")


def _normalize_darwin_system_prefix(path: Path, *, allow_exact: bool = False) -> Path:
    """Map root-owned macOS /var, /tmp, /etc aliases to /private/* without resolving user symlinks."""
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


def _open_dir_chain_nofollow(parts: tuple[str, ...], *, root_abs: bool) -> int:
    start = "/" if root_abs else "."
    try:
        cur_fd = os.open(start, _DIR_OPEN_FLAGS)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            raise oracle.ModularCertError("CWD_UNAVAILABLE", f"directory root unavailable: {exc}") from exc
        raise oracle.ModularCertError("DIR_OPEN_FAILED", f"cannot open directory root: {exc}") from exc
    for comp in parts:
        if comp in ("", "."):
            continue
        if comp == "..":
            os.close(cur_fd)
            raise oracle.ModularCertError("PARENT_TRAVERSAL_FORBIDDEN", "path must not contain '..'")
        try:
            next_fd = os.open(comp, _DIR_OPEN_FLAGS, dir_fd=cur_fd)
        except OSError as exc:
            is_sym = exc.errno == errno.ELOOP
            if exc.errno == errno.ENOTDIR:
                try:
                    is_sym = stat.S_ISLNK(os.lstat(comp, dir_fd=cur_fd).st_mode)
                except OSError:
                    is_sym = False
            os.close(cur_fd)
            if is_sym:
                raise oracle.ModularCertError("SYMLINK_FORBIDDEN", f"symlink component rejected: {comp!r}") from exc
            if exc.errno == errno.ENOTDIR:
                raise oracle.ModularCertError("NOT_A_DIRECTORY", f"component is not a directory: {comp!r}") from exc
            raise oracle.ModularCertError("DIR_OPEN_FAILED", f"cannot traverse {comp!r}: {exc}") from exc
        os.close(cur_fd)
        cur_fd = next_fd
    return cur_fd


def _verify_pwd_not_symlink() -> None:
    pwd = os.environ.get("PWD")
    if not pwd or not pwd.startswith("/"):
        return
    oracle.require_exact_str(pwd, "PWD")
    if "\x00" in pwd:
        raise oracle.ModularCertError("INVALID_PATH", "PWD must not contain NUL")
    try:
        st_dot = os.stat(".")
    except OSError as exc:
        raise oracle.ModularCertError("CWD_UNAVAILABLE", f"cannot stat current directory: {exc}") from exc
    try:
        st_logical = os.stat(pwd)
    except OSError:
        return
    if (st_logical.st_dev, st_logical.st_ino) != (st_dot.st_dev, st_dot.st_ino):
        return
    norm_pwd = _normalize_darwin_system_prefix(Path(pwd), allow_exact=True)
    parts = tuple(p for p in norm_pwd.parts if p != "/")
    dfd = _open_dir_chain_nofollow(parts, root_abs=True)
    try:
        st_pwd = os.fstat(dfd)
    finally:
        os.close(dfd)
    if (st_pwd.st_dev, st_pwd.st_ino) != (st_dot.st_dev, st_dot.st_ino):
        raise oracle.ModularCertError("PWD_SYMLINK_MISMATCH", "$PWD changed during verification")


def _open_parent_dir_fd(path_obj: Path) -> tuple[int, str]:
    if path_obj.name in ("", ".", ".."):
        raise oracle.ModularCertError("INVALID_FILENAME", f"invalid target filename: {str(path_obj)!r}")
    if path_obj.is_absolute():
        norm = _normalize_darwin_system_prefix(path_obj)
        parts = tuple(p for p in norm.parts if p != "/")
        return (_open_dir_chain_nofollow(parts[:-1], root_abs=True), parts[-1])
    _verify_pwd_not_symlink()
    try:
        cwd = os.getcwd()
    except OSError as exc:
        raise oracle.ModularCertError("CWD_UNAVAILABLE", f"current working directory unavailable: {exc}") from exc
    norm_cwd = _normalize_darwin_system_prefix(Path(cwd), allow_exact=True)
    full_parts = tuple(p for p in norm_cwd.parts if p != "/") + path_obj.parts
    return (_open_dir_chain_nofollow(full_parts[:-1], root_abs=True), full_parts[-1])


def read_regular_bytes_capped(path: Any, *, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    """Read a regular non-symlink file via atomic dir_fd + O_NOFOLLOW + O_NONBLOCK with streaming cap."""
    p_obj = _coerce_exact_path(path, "read_path")
    cap = oracle.require_exact_int(max_bytes, "max_bytes", min_val=1, max_val=MAX_ALLOWED_CAP_BYTES)
    dfd, fname = _open_parent_dir_fd(p_obj)
    try:
        try:
            lst = os.lstat(fname, dir_fd=dfd)
        except OSError as exc:
            raise oracle.ModularCertError("FILE_UNREADABLE", f"cannot lstat {fname!r}: {exc}") from exc
        if stat.S_ISLNK(lst.st_mode):
            raise oracle.ModularCertError("SYMLINK_FORBIDDEN", f"symlink target refused: {fname!r}")
        if not stat.S_ISREG(lst.st_mode):
            raise oracle.ModularCertError("NON_REGULAR_FILE", f"non-regular file refused: {fname!r}")
        if lst.st_nlink > 1:
            raise oracle.ModularCertError("HARDLINK_FORBIDDEN", f"hardlinked file refused: {fname!r}")
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
        try:
            fd = os.open(fname, flags, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise oracle.ModularCertError("SYMLINK_FORBIDDEN", f"symlink race refused: {fname!r}") from exc
            raise oracle.ModularCertError("FILE_UNREADABLE", f"cannot open {fname!r}: {exc}") from exc
        try:
            try:
                fst = os.fstat(fd)
            except OSError as exc:
                raise oracle.ModularCertError("READ_IO_ERROR", f"fstat failed: {exc}") from exc
            if not stat.S_ISREG(fst.st_mode):
                raise oracle.ModularCertError("NON_REGULAR_FILE", f"opened target not regular: {fname!r}")
            if fst.st_nlink > 1:
                raise oracle.ModularCertError("HARDLINK_FORBIDDEN", f"opened target hardlinked: {fname!r}")
            if (fst.st_dev, fst.st_ino) != (lst.st_dev, lst.st_ino):
                raise oracle.ModularCertError("TOCTOU_SWAP", f"file identity changed during open: {fname!r}")
            chunks: list[bytes] = []
            total = 0
            while True:
                try:
                    buf = os.read(fd, _READ_CHUNK_BYTES)
                except OSError as exc:
                    raise oracle.ModularCertError("READ_IO_ERROR", f"read failed: {exc}") from exc
                if not buf:
                    break
                total += len(buf)
                if total > cap:
                    raise oracle.ModularCertError("FILE_TOO_LARGE", f"file exceeds {cap} byte cap")
                chunks.append(buf)
            return b"".join(chunks)
        finally:
            os.close(fd)
    finally:
        os.close(dfd)


def _next_temp_name(base_name: str) -> str:
    global _TEMP_COUNTER
    with _TEMP_NAME_LOCK:
        _TEMP_COUNTER += 1
        seq = _TEMP_COUNTER
    return f".{base_name}.tmp.{os.getpid()}.{seq}.{secrets.token_hex(8)}"


def write_bytes_atomic_0600(path: Any, data: bytes) -> None:
    """Durable 0o600 atomic write via dir_fd, refusing symlinks and multi-link targets."""
    if type(data) is not bytes:
        raise oracle.ModularCertError("INVALID_BYTES", "data must be exact bytes")
    p_obj = _coerce_exact_path(path, "write_path")
    dfd, fname = _open_parent_dir_fd(p_obj)
    tmp_name: str | None = None
    tmp_fd: int | None = None
    try:
        try:
            lst = os.lstat(fname, dir_fd=dfd)
        except FileNotFoundError:
            lst = None
        except OSError as exc:
            raise oracle.ModularCertError("TARGET_UNSTATTABLE", f"cannot lstat target {fname!r}: {exc}") from exc
        if lst is not None:
            if stat.S_ISLNK(lst.st_mode):
                raise oracle.ModularCertError("SYMLINK_FORBIDDEN", f"refusing symlink write target: {fname!r}")
            if not stat.S_ISREG(lst.st_mode):
                raise oracle.ModularCertError("NON_REGULAR_FILE", f"refusing non-regular write target: {fname!r}")
            if lst.st_nlink > 1:
                raise oracle.ModularCertError("HARDLINK_FORBIDDEN", f"refusing hardlinked target: {fname!r}")

        create_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        for _ in range(32):
            cand = _next_temp_name(fname)
            try:
                tmp_fd = os.open(cand, create_flags, 0o600, dir_fd=dfd)
                tmp_name = cand
                break
            except FileExistsError:
                continue
            except OSError as exc:
                raise oracle.ModularCertError("WRITE_IO_ERROR", f"cannot create temp file: {exc}") from exc
        if tmp_fd is None:
            raise oracle.ModularCertError("TEMP_CREATE_FAILED", "exhausted temp filename retries")

        try:
            view = memoryview(data)
            written = 0
            while written < len(data):
                n = os.write(tmp_fd, view[written:])
                if n <= 0:
                    raise oracle.ModularCertError("SHORT_WRITE", "os.write returned non-positive count")
                written += n
            os.fchmod(tmp_fd, 0o600)
            os.fsync(tmp_fd)
            st_tmp = os.fstat(tmp_fd)
            if not stat.S_ISREG(st_tmp.st_mode) or st_tmp.st_nlink != 1:
                raise oracle.ModularCertError("TEMP_TAMPERED", "temp file mode or link count altered")
            os.close(tmp_fd)
            tmp_fd = None

            try:
                lst2 = os.lstat(fname, dir_fd=dfd)
            except FileNotFoundError:
                lst2 = None
            if lst2 is not None:
                if stat.S_ISLNK(lst2.st_mode):
                    raise oracle.ModularCertError("SYMLINK_FORBIDDEN", f"symlink appeared at target: {fname!r}")
                if not stat.S_ISREG(lst2.st_mode):
                    raise oracle.ModularCertError("NON_REGULAR_FILE", f"non-regular target appeared: {fname!r}")
                if lst2.st_nlink > 1:
                    raise oracle.ModularCertError("HARDLINK_FORBIDDEN", f"hardlink appeared at target: {fname!r}")

            os.replace(tmp_name, fname, src_dir_fd=dfd, dst_dir_fd=dfd)
            tmp_name = None
            os.fsync(dfd)
        except oracle.ModularCertError:
            raise
        except OSError as exc:
            raise oracle.ModularCertError("WRITE_IO_ERROR", f"atomic write failed: {exc}") from exc
    finally:
        if tmp_fd is not None:
            os.close(tmp_fd)
        if tmp_name is not None:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
        os.close(dfd)


# ---------------------------------------------------------------------------
# Strict-Keyset Field-Complete Secondary Auditor & Certificate Verifier
# ---------------------------------------------------------------------------

def _require_dict_exact_keys(obj: Any, expected: frozenset[str], name: str) -> dict[str, Any]:
    if type(obj) is not dict:
        raise oracle.ModularCertError("INVALID_OBJECT", f"{name} must be a dict")
    if frozenset(obj.keys()) != expected:
        raise oracle.ModularCertError("KEYSET_MISMATCH", f"{name} keys do not match schema")
    return obj


def secondary_audit_payload(payload: dict[str, Any]) -> None:
    """Field-complete strict-keyset algebraic cross-check (zero cached summary trust)."""
    oracle._check_json_value_strict(payload)
    p = _require_dict_exact_keys(payload, _PAYLOAD_KEYS, "payload")
    if p["track_id"] != oracle.TRACK_ID:
        raise oracle.ModularCertError("TRACK_ID_MISMATCH", "payload track_id mismatch")
    if p["portal_ref"] != oracle.PORTAL_REF:
        raise oracle.ModularCertError("PORTAL_REF_MISMATCH", "payload portal_ref mismatch")

    # Pillar 1: cross-check every algebraic invariant without division-by-untrusted-zero
    p1 = _require_dict_exact_keys(p["pillar1_modular_hodge_compression"], _P1_KEYS, "pillar1")
    if p1["case_id"] != "symmetric-sextic-residual":
        raise oracle.ModularCertError("P1_CASE_MISMATCH", "unexpected Pillar 1 case_id")
    scale = oracle.require_exact_int(p1["cleared_scale"], "cleared_scale", min_val=1)
    q_exp = oracle.require_exact_int(p1["q_exponent"], "q_exponent", min_val=1)
    mod_p = oracle.require_exact_int(p1["mod_prime"], "mod_prime", min_val=2)
    m_cnt = oracle.require_exact_int(p1["monomial_count"], "monomial_count", min_val=1)
    c_sum = oracle.require_exact_int(p1["cleared_7f_coeff_sum"], "cleared_7f_coeff_sum", min_val=1)
    f_sum_q = oracle.parse_exact_rational(p1["f_coeff_sum_q"], "f_coeff_sum_q")
    if scale != 7 or q_exp != 1 or mod_p != 5 or m_cnt != 42 or c_sum != 447:
        raise oracle.ModularCertError("P1_SCALAR_MISMATCH", "Pillar 1 cleared sextic constants mismatch")
    if f_sum_q * scale != Fraction(c_sum, 1):
        raise oracle.ModularCertError("P1_SUM_MISMATCH", "f_coeff_sum_q * cleared_scale != cleared_7f_coeff_sum")
    if (
        oracle.require_exact_int(p1["substituted_f_monomial_count"], "sub_f_cnt") != 46
        or oracle.require_exact_int(p1["substituted_f_odd_s"], "sub_f_odd_s") != 0
        or oracle.require_exact_int(p1["substituted_f_odd_t"], "sub_f_odd_t") != 0
        or oracle.require_exact_int(p1["substituted_a_monomial_count"], "sub_a_cnt") != 4
        or oracle.require_exact_int(p1["substituted_a_odd_s"], "sub_a_odd_s") != 0
        or oracle.require_exact_int(p1["substituted_a_odd_t"], "sub_a_odd_t") != 0
    ):
        raise oracle.ModularCertError("P1_REFLECTION_MISMATCH", "Pillar 1 reflection parity counts mismatch")
    dtx = oracle.require_exact_int(p1["det_tau_x"], "det_tau_x")
    dty = oracle.require_exact_int(p1["det_tau_y"], "det_tau_y")
    dtxy = oracle.require_exact_int(p1["det_tau_xy"], "det_tau_xy")
    if dtx != -1 or dty != -1 or dtxy != dtx * dty:
        raise oracle.ModularCertError("P1_DET_MISMATCH", "Pillar 1 involution determinants mismatch")
    if oracle.require_exact_int(p1["mod5_nonzero_terms"], "mod5_nonzero_terms") != 6:
        raise oracle.ModularCertError("P1_MOD5_COUNT", "mod5_nonzero_terms must equal 6")
    if oracle.require_exact_bool(p1["mod5_unique_origin_smooth"], "mod5_unique_origin_smooth") is not True:
        raise oracle.ModularCertError("P1_MOD5_SMOOTH", "mod5_unique_origin_smooth must be True")
    pkt_bytes_ref = oracle.canonical_json_bytes(oracle.compress_hodge_sextic_packet())
    pkt_len = oracle.require_exact_int(p1["compressed_packet_bytes"], "compressed_packet_bytes", min_val=1)
    pkt_sha = oracle.require_sha256_hex(p1["compressed_packet_sha256"], "compressed_packet_sha256")
    if pkt_len != len(pkt_bytes_ref) or not oracle.check_digest_eq(pkt_sha, oracle.sha256_bytes(pkt_bytes_ref)):
        raise oracle.ModularCertError("P1_PACKET_PIN_MISMATCH", "compressed Hodge packet size or digest mismatch")
    ram_env = p1["deepmind_ram_gb_envelope"]
    if type(ram_env) is not list or len(ram_env) != 2:
        raise oracle.ModularCertError("P1_RAM_ENVELOPE", "deepmind_ram_gb_envelope must be [230, 233]")
    if (
        oracle.require_exact_int(ram_env[0], "ram_lo") != oracle.DEEPMIND_COMPARATOR_RAM_GB_LO
        or oracle.require_exact_int(ram_env[1], "ram_hi") != oracle.DEEPMIND_COMPARATOR_RAM_GB_HI
    ):
        raise oracle.ModularCertError("P1_RAM_ENVELOPE", "deepmind_ram_gb_envelope bounds mismatch")
    ratio_q = oracle.parse_exact_rational(p1["compression_ratio_vs_233gb_q"], "compression_ratio_vs_233gb_q")
    if ratio_q * pkt_len != Fraction(oracle.DEEPMIND_COMPARATOR_RAM_BYTES_HI, 1):
        raise oracle.ModularCertError("P1_RATIO_MISMATCH", "compression ratio cross-product mismatch")
    if oracle.require_exact_bool(p1["compression_ratio_gt_20m"], "compression_ratio_gt_20m") is not True:
        raise oracle.ModularCertError("P1_RATIO_BOOL", "compression_ratio_gt_20m must be True")

    # Pillar 2: Praxis rank-2 SOS cheat blocking, Polya 0/512, hollow/non-canonical probes
    p2 = _require_dict_exact_keys(p["pillar2_adversarial_cheat_blocking"], _P2_KEYS, "pillar2")
    if (
        oracle.require_exact_int(p2["rank1_honest_exact_rank"], "rank1_rank") != 1
        or oracle.require_exact_bool(p2["rank1_all_2x2_minors_zero"], "rank1_2x2") is not True
        or oracle.require_exact_int(p2["unsat_bqs_boolean_witness_count"], "unsat_cnt") != 0
        or oracle.require_exact_int(p2["rank2_sos_exact_rank"], "rank2_rank") != 2
        or oracle.require_exact_bool(p2["rank2_sos_passes_unsat_moments"], "rank2_moments") is not True
        or oracle.require_exact_bool(p2["rank2_sos_all_15_minors_nonneg"], "rank2_psd") is not True
        or oracle.require_exact_int(p2["rank2_sos_witness_minor_02"], "rank2_minor_02") != 1
        or oracle.require_exact_int(p2["rank2_sos_minor_mod101"], "rank2_minor_101") != 1
        or oracle.require_exact_bool(p2["rank2_sos_blocked_by_verifier"], "rank2_blocked") is not True
    ):
        raise oracle.ModularCertError("P2_PRAXIS_MISMATCH", "Pillar 2 Praxis rank-gap values mismatch")
    minors = _require_dict_exact_keys(p2["rank2_sos_principal_minors"], _P2_MINOR_KEYS, "rank2_minors")
    exp_minors = {
        "size_1": [2, 2, 1, 2],
        "size_2": [0, 1, 0, 1, 0, 1],
        "size_3": [0, 0, 0, 0],
        "size_4": [0],
    }
    for mk, mvals in exp_minors.items():
        got = minors[mk]
        if type(got) is not list or len(got) != len(mvals):
            raise oracle.ModularCertError("P2_MINOR_SHAPE", f"rank2 minor {mk} shape mismatch")
        if [oracle.require_exact_int(v, f"{mk}_val") for v in got] != mvals:
            raise oracle.ModularCertError("P2_MINOR_VALUES", f"rank2 minor {mk} values mismatch")
    if (
        oracle.require_exact_int(p2["polya_total_patterns"], "polya_total") != 512
        or oracle.require_exact_int(p2["polya_f2_collapse_count"], "polya_f2") != 512
        or oracle.require_exact_int(p2["polya_z_valid_count"], "polya_z") != 0
        or oracle.require_exact_int(p2["polya_max_perm_matches_out_of_6"], "polya_max") != 5
        or oracle.require_exact_bool(p2["hollow_packet_tamper_rejected"], "hollow_rej") is not True
        or oracle.require_exact_bool(p2["non_canonical_unit_den_rejected"], "unit_den_rej") is not True
        or oracle.require_exact_bool(p2["zero_den_rejected"], "zero_den_rej") is not True
        or oracle.require_exact_bool(p2["f2_freshman_dream_holds"], "f2_freshman") is not True
        or oracle.require_exact_int(p2["z_carry_cross_term_delta"], "z_carry") != 4
    ):
        raise oracle.ModularCertError("P2_OBSTRUCTION_MISMATCH", "Pillar 2 Polya/hollow/carry values mismatch")

    # Pillar 3: Lean 4 companion pin & anti-bypass counts
    p3 = _require_dict_exact_keys(p["pillar3_lean4_anti_bypass_and_soundness"], _P3_KEYS, "pillar3")
    if p3["lean_companion_filename"] != oracle.LEAN_COMPANION_FILENAME:
        raise oracle.ModularCertError("P3_FILENAME_MISMATCH", "lean_companion_filename mismatch")
    if not oracle.check_digest_eq(
        oracle.require_sha256_hex(p3["lean_companion_sha256"], "lean_companion_sha256"),
        oracle.LEAN_COMPANION_SHA256,
    ):
        raise oracle.ModularCertError("P3_LEAN_SHA_MISMATCH", "lean_companion_sha256 mismatch")
    thms = p3["lean_companion_theorems"]
    if type(thms) is not list or [oracle.require_exact_str(t, "thm") for t in thms] != list(oracle.LEAN_COMPANION_THEOREMS):
        raise oracle.ModularCertError("P3_THEOREMS_MISMATCH", "lean_companion_theorems mismatch")
    if (
        oracle.require_exact_int(p3["lean_companion_theorem_count"], "thm_cnt") != len(oracle.LEAN_COMPANION_THEOREMS)
        or oracle.require_exact_int(p3["forbidden_token_count"], "forb_cnt") != len(oracle._FORBIDDEN_LEAN4_TOKENS)
        or oracle.require_exact_int(p3["positive_controls_total"], "pos_tot") != 7
        or oracle.require_exact_int(p3["positive_controls_passed"], "pos_ok") != 7
        or oracle.require_exact_int(p3["adversarial_fixtures_total"], "adv_tot") != 21
        or oracle.require_exact_int(p3["adversarial_fixtures_rejected"], "adv_ok") != 21
    ):
        raise oracle.ModularCertError("P3_COUNTS_MISMATCH", "Pillar 3 gate counts mismatch")

    # Pillar 4: CS-13 honest scope & summary
    p4 = _require_dict_exact_keys(p["pillar4_cs13_honest_scope"], _P4_KEYS, "pillar4")
    if (
        p4["novelty_tier"] != "N1"
        or p4["oracle_class"] != "exact"
        or oracle.require_exact_int(p4["max_int_bits_exact_cap"], "max_bits") != oracle.MAX_INT_BITS
        or oracle.require_exact_int(p4["max_int_digits_preparse_ceiling"], "max_digits") != oracle.MAX_INT_DIGITS
        or oracle.require_exact_bool(p4["measured_live_pequalnp_desk_submission"], "live_peq") is not False
        or oracle.require_exact_bool(p4["measured_live_deepmind_233gb_comparator"], "live_dm") is not False
        or oracle.require_exact_bool(p4["zero_trust_path_floats"], "zero_floats") is not True
        or oracle.require_exact_bool(p4["zero_bare_asserts"], "zero_asserts") is not True
        or oracle.require_exact_bool(p4["zero_mathematical_rng"], "zero_rng") is not True
    ):
        raise oracle.ModularCertError("P4_SCOPE_MISMATCH", "Pillar 4 CS-13 scope mismatch")
    lit = p4["prior_literature_n0"]
    if type(lit) is not list or [oracle.require_exact_str(x, "lit") for x in lit] != list(oracle._PRIOR_LITERATURE_N0):
        raise oracle.ModularCertError("P4_LIT_MISMATCH", "prior_literature_n0 list mismatch")

    summ = _require_dict_exact_keys(p["summary"], _SUMMARY_KEYS, "summary")
    if (
        oracle.require_exact_bool(summ["all_pillars_verified"], "all_pillars_verified") is not True
        or oracle.require_exact_int(summ["target_max_cert_bytes"], "target_max_cert_bytes") != oracle.TARGET_MAX_CERT_BYTES
    ):
        raise oracle.ModularCertError("SUMMARY_MISMATCH", "summary fields mismatch")


def verify_certificate_dict(cert: Any, *, full_replay: bool = True) -> dict[str, Any]:
    """Verify certificate schema, constant-time digests, secondary audit, and optional full replay."""
    replay_flag = oracle.require_exact_bool(full_replay, "full_replay")
    c = _require_dict_exact_keys(cert, _CERT_KEYS, "certificate")
    if c["schema_version"] != oracle.SCHEMA_VERSION:
        raise oracle.ModularCertError("SCHEMA_MISMATCH", "unexpected schema_version")
    if c["track_id"] != oracle.TRACK_ID:
        raise oracle.ModularCertError("TRACK_ID_MISMATCH", "unexpected track_id")
    decl_p_sha = oracle.require_sha256_hex(c["payload_sha256"], "payload_sha256")
    decl_c_sha = oracle.require_sha256_hex(c["certificate_sha256"], "certificate_sha256")
    payload = _require_dict_exact_keys(c["payload"], _PAYLOAD_KEYS, "payload")

    actual_p_sha = oracle.sha256_bytes(oracle.canonical_json_bytes(payload))
    if not oracle.check_digest_eq(decl_p_sha, actual_p_sha):
        raise oracle.ModularCertError("PAYLOAD_SHA256_MISMATCH", "payload digest mismatch")
    cert_pre = {
        "schema_version": c["schema_version"],
        "track_id": c["track_id"],
        "payload_sha256": decl_p_sha,
        "payload": payload,
    }
    actual_c_sha = oracle.sha256_bytes(oracle.canonical_json_bytes(cert_pre))
    if not oracle.check_digest_eq(decl_c_sha, actual_c_sha):
        raise oracle.ModularCertError("CERTIFICATE_SHA256_MISMATCH", "certificate digest mismatch")

    secondary_audit_payload(payload)

    if replay_flag:
        expected = oracle.build_certificate()
        if not oracle.check_digest_eq(decl_c_sha, expected["certificate_sha256"]):
            raise oracle.ModularCertError("FULL_REPLAY_MISMATCH", "certificate disagrees with deterministic replay")

    return {
        "valid": True,
        "schema_version": oracle.SCHEMA_VERSION,
        "track_id": oracle.TRACK_ID,
        "payload_sha256": actual_p_sha,
        "certificate_sha256": actual_c_sha,
        "full_replay": replay_flag,
        "secondary_audit_passed": True,
    }


def verify_lean_companion_file(path: Any, *, lean_bin: str | None = None) -> dict[str, Any]:
    """Verify ModularCertSoundness.lean digest, anti-bypass scan, and live Lean 4 kernel + #print axioms."""
    raw = read_regular_bytes_capped(path, max_bytes=MAX_JSON_BYTES)
    file_sha = oracle.sha256_bytes(raw)
    if not oracle.check_digest_eq(file_sha, oracle.LEAN_COMPANION_SHA256):
        raise oracle.ModularCertError("LEAN_SHA256_MISMATCH", f"Lean companion SHA-256 mismatch: {file_sha}")
    try:
        src = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise oracle.ModularCertError("LEAN_INVALID_UTF8", "Lean companion is not valid UTF-8") from exc
    scan = oracle.scan_lean4_anti_bypass(src)
    if not scan["clean"]:
        raise oracle.ModularCertError("LEAN_ANTI_BYPASS_FAILED", f"anti-bypass findings: {scan['codes']}")

    if lean_bin is not None:
        resolved_lean = oracle.require_exact_str(lean_bin, "lean_bin")
    else:
        resolved_lean = shutil.which("lean")
    if resolved_lean is None:
        raise oracle.ModularCertError("LEAN_NOT_FOUND", "lean binary not found for live kernel verification")

    with tempfile.TemporaryDirectory(prefix="s55_lean_ax_") as td:
        ax_path = Path(td) / "check_axioms.lean"
        ax_lines = [src, ""]
        for thm in oracle.LEAN_COMPANION_THEOREMS:
            ax_lines.append(f"#print axioms TrackS55.ModularCertSoundness.{thm}")
        ax_path.write_text("\n".join(ax_lines) + "\n", encoding="utf-8")
        try:
            proc = subprocess.run(
                [resolved_lean, str(ax_path)],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise oracle.ModularCertError("LEAN_EXEC_FAILED", f"cannot invoke lean: {exc}") from exc
        if proc.returncode != 0:
            raise oracle.ModularCertError("LEAN_KERNEL_FAILED", f"lean exited {proc.returncode}")
        seen_theorems: set[str] = set()
        for m_ax in _AXIOM_BLOCK_RE.finditer(proc.stdout):
            full_name = m_ax.group(1)
            if m_ax.group(2) is None:
                for tok in m_ax.group(3).split(","):
                    ax = tok.strip()
                    if ax not in _STANDARD_LEAN4_AXIOMS:
                        raise oracle.ModularCertError("LEAN_BANNED_AXIOM", f"disallowed axiom {ax!r} in {full_name}")
            seen_theorems.add(full_name)
        for thm in oracle.LEAN_COMPANION_THEOREMS:
            fq = f"TrackS55.ModularCertSoundness.{thm}"
            if fq not in seen_theorems:
                raise oracle.ModularCertError("LEAN_MISSING_THEOREM", f"theorem {fq!r} missing from #print axioms")
    return {
        "valid": True,
        "lean_companion_sha256": file_sha,
        "anti_bypass_clean": True,
        "kernel_theorems_verified": len(oracle.LEAN_COMPANION_THEOREMS),
        "banned_axioms_found": 0,
    }


# ---------------------------------------------------------------------------
# Strict Manual CLI Parser (Zero Abbreviation, Fail-Closed rc=2)
# ---------------------------------------------------------------------------

def _parse_cli_args(argv: list[str]) -> dict[str, Any]:
    mode = "self_check"
    target_path: str | None = None
    as_json = False
    i = 0
    n = len(argv)
    while i < n:
        arg = argv[i]
        if arg == "--standalone":
            if mode != "self_check":
                raise oracle.ModularCertError("CLI_CONFLICT", "conflicting CLI mode flags")
            mode = "standalone"
            i += 1
        elif arg == "--json":
            if as_json:
                raise oracle.ModularCertError("CLI_DUPLICATE", "duplicate --json flag")
            as_json = True
            i += 1
        elif arg in ("--write", "--check", "--verify-lean"):
            if mode != "self_check":
                raise oracle.ModularCertError("CLI_CONFLICT", "conflicting CLI mode flags")
            if i + 1 >= n:
                raise oracle.ModularCertError("CLI_MISSING_ARG", f"{arg} requires a path argument")
            cand = argv[i + 1]
            if not cand or cand.startswith("-"):
                raise oracle.ModularCertError("CLI_INVALID_PATH", f"{arg} path must not be empty or flag-like")
            mode = arg[2:].replace("-", "_")
            target_path = cand
            i += 2
        else:
            raise oracle.ModularCertError("CLI_UNKNOWN_ARG", f"unknown argument {arg!r}")
    return {"mode": mode, "path": target_path, "json": as_json}


def main(argv: list[str] | tuple[str, ...] | None = None) -> int:
    try:
        if argv is None:
            raw_argv = list(sys.argv[1:])
        else:
            if type(argv) not in (list, tuple):
                raise oracle.ModularCertError("CLI_INVALID_ARGV", "argv must be list, tuple, or None")
            raw_argv = [oracle.require_exact_str(a, "argv", non_empty=False) for a in argv]
        opts = _parse_cli_args(raw_argv)
        mode = opts["mode"]
        if mode == "self_check":
            cert = oracle.build_certificate()
            res = verify_certificate_dict(cert, full_replay=True)
            if opts["json"]:
                sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii") + "\n")
            else:
                sys.stdout.write(f"OK {res['schema_version']} {res['certificate_sha256']}\n")
            return 0
        if mode == "standalone":
            cert = oracle.build_certificate()
            verify_certificate_dict(cert, full_replay=True)
            sys.stdout.write(oracle.canonical_json_bytes(cert).decode("ascii") + "\n")
            return 0
        if mode == "write":
            cert = oracle.build_certificate()
            verify_certificate_dict(cert, full_replay=True)
            out_bytes = oracle.canonical_json_bytes(cert) + b"\n"
            write_bytes_atomic_0600(opts["path"], out_bytes)
            if opts["json"]:
                sys.stdout.write(
                    oracle.canonical_json_bytes({"written": True, "certificate_sha256": cert["certificate_sha256"]}).decode("ascii")
                    + "\n"
                )
            else:
                sys.stdout.write(f"WROTE {cert['certificate_sha256']}\n")
            return 0
        if mode == "check":
            raw_bytes = read_regular_bytes_capped(opts["path"], max_bytes=MAX_JSON_BYTES)
            try:
                raw_text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise oracle.ModularCertError("INVALID_UTF8", "certificate file is not valid UTF-8") from exc
            parsed = oracle.parse_strict_json_text(raw_text)
            canon = oracle.canonical_json_bytes(parsed)
            if raw_bytes not in (canon, canon + b"\n"):
                raise oracle.ModularCertError("NON_CANONICAL_BYTES", "certificate file is not canonical JSON")
            res = verify_certificate_dict(parsed, full_replay=True)
            if opts["json"]:
                sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii") + "\n")
            else:
                sys.stdout.write(f"VALID {res['certificate_sha256']}\n")
            return 0
        res = verify_lean_companion_file(opts["path"])
        if opts["json"]:
            sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii") + "\n")
        else:
            sys.stdout.write(f"LEAN_VALID {res['lean_companion_sha256']} {res['kernel_theorems_verified']}\n")
        return 0
    except oracle.ModularCertError as exc:
        sys.stderr.write(f"ERROR {exc.code}: {exc.message}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
