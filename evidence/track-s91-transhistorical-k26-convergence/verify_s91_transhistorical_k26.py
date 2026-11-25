#!/usr/bin/env python3
"""Zone-B Hardened Standalone CLI, Live Lean 4.36.0 & Secondary Auditor for Track S91.

100% pure Python 3 stdlib, zero IEEE-754 floats, zero bare asserts, zero .isdigit(),
zero mathematical RNG (secrets.token_hex used strictly for atomic temp filenames).
Full R11+ Lean 4 static & live private-temp-copy (LEAN_PATH/LEAN_OPTS scrubbed) hardening.
"""
from __future__ import annotations

import errno
from fractions import Fraction
import hmac
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
from typing import Any, Sequence

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import s91_transhistorical_k26_oracle as oracle  # noqa: E402

MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_ALLOWED_CAP_BYTES = 64 * 1024 * 1024
_READ_CHUNK_BYTES = 65_536
_EXACT_PATH_TYPES = (Path, type(Path()))
_DIR_OPEN_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_DARWIN_SYSTEM_ROOT_ALIASES: tuple[tuple[str, str], ...] = (
    ("/var", "/private/var"),
    ("/tmp", "/private/tmp"),
    ("/etc", "/private/etc"),
)
_TEMP_NAME_LOCK = threading.Lock()
_TEMP_SEQ = 0
_ALLOWED_LEAN_AXIOMS = frozenset({"propext", "Quot.sound"})
_SAFE_LEAN_ENV_KEYS: tuple[str, ...] = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")
_EXPECTED_WORST_PUZZLE_ID = "test-0133"
_EXPECTED_BM_OBSTRUCTION = "Banu Musa analog float lacks discrete 15s/30s dwell timers and manual-override preemption"
_EXPECTED_NF_OBSTRUCTION = "Undirected graph Laplacian omits one-way cardiac valves and incurs 50% Rayleigh conductance drop"

_CERT_KEYS = frozenset({"schema_version", "track_id", "payload_sha256", "certificate_sha256", "payload"})
_PAYLOAD_KEYS = frozenset({
    "schema_version",
    "track_id",
    "oracle_class",
    "novelty_classification",
    "pinned_artifacts",
    "k26_nodes",
    "pillar1_tusi_circularep_cure",
    "pillar2_kashi_cubic_vs_newton",
    "pillar3_banu_musa_and_ibn_al_nafis",
    "pillar4_k26_transhistorical_mesh",
})
_PINNED_KEYS = frozenset({
    "heritage_corpus_commit_sha",
    "anchor_file",
    "anchor_sha256",
    "lean_source",
    "lean_source_sha256",
    "lean_toolchain",
    "lean_toolchain_sha256",
    "lakefile_sha256",
    "lean_theorem_count",
    "lean_theorem_names",
})
_NODE_KEYS = frozenset({"id", "era", "label", "source_rel", "source_sha256"})
_K26_NODE_IDS = frozenset(row["id"] for row in oracle.K26_NODES)
_CROSS_PAIR_LABELS: dict[str, str] = {
    f"{oracle.K26_NODES[u]['id']}-{oracle.K26_NODES[v]['id']}": lbl
    for (u, v), lbl in oracle.CROSS_OBSTRUCTION_LABELS.items()
}

# Frozen on-disk artifact SHA-256 pins (enforced in BOTH SEC/FR0 and FR1)
EXPECTED_ANCHOR_SHA256 = "8e09f6f981941f77a5e9778d92336f225fad1f31d8cffa5a4c51f152757acd0d"
EXPECTED_LEAN_SOURCE_SHA256 = "81922b3cf483fc42a51e37e3403448db5bbf51987e0158d82ddaee6ed12a1d29"
EXPECTED_TOOLCHAIN_SHA256 = "582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a"
EXPECTED_LAKEFILE_SHA256 = "bf19267efb49a34c164dcb6e3d08794276fb955f662f6532e6ab058b3353735c"
EXPECTED_PAYLOAD_SHA256 = "27cf2e39de0384167ff2d98b1a2c1de7e69e6c3d3c6be7d8155a934c21c0cc3b"

_P1_KEYS = frozenset({"anchor_sha256", "upstream_commit_sha", "upstream_best_json_sha256", "exact_q_witnesses", "live_300_puzzle_summary"})
_P1_WITNESS_KEYS = frozenset({"planar_tusi_couple", "s76_elliptic_curl", "law5_nonnormal_destabilization"})
_P1_W_PLANAR_KEYS = frozenset({
    "discriminant_nonneg", "discriminant_t_q", "h2_off_diag_zero", "k12_q",
    "k_fro_sq_q", "m_fro_sq_q", "pythagorean_exact", "t11_q", "t12_q", "t22_q", "t_fro_sq_q",
})
_P1_W_EIG_KEYS = _P1_W_PLANAR_KEYS | frozenset({"t_eigenvalues_q", "t_rho_q"})
_P1_W_LAW5_KEYS = _P1_W_EIG_KEYS | frozenset({"destabilizes_contractive_loop", "raw_rho_q"})
_P1_L300_KEYS = frozenset({
    "bendixson_bound_verified_count", "cx_median_error_reduction_sci", "disparity_collapse_factor_sci",
    "law5_cs21_jvp_cost_multiplier", "law5_norm2_tusi_lt_norm2_raw_count", "law5_rho_median_lift_pct_dec2",
    "law5_rho_tusi_gt_rho_raw_count", "law5_tusi_contractive_count", "n_puzzles", "norm2_median_drop_pct_dec2",
    "raw_complex_dominant_count", "raw_cx_vs_re_disparity_sci", "raw_pi60_cx_median_dec6",
    "skew_fro_fraction_median_dec6", "tusi_complex_dominant_count", "tusi_cx_improved_count",
    "tusi_cx_vs_re_disparity_dec4", "tusi_max_abs_imag_sci", "tusi_max_normality_dev_sci",
    "tusi_pi60_cx_median_sci", "twin_h2_block_diag_max_err_sci", "worst_puzzle_id",
    "worst_puzzle_raw_err_dec6", "worst_puzzle_tusi_err_sci",
})
_P2_KEYS = frozenset({"narrow_range_p45_witness", "sin_1deg_unscaled_witness", "law5_near_cliff_newton_wins", "law5_post_cliff_kashi_diverges"})
_P2_NR_KEYS = frozenset({
    "chebyshev_deg3_err_dec15", "exact_root_q", "kashi_2step_beats_deg3_poly", "kashi_3step_fdivs",
    "kashi_3step_ops", "kashi_step_errs_dec15", "lipschitz_q", "newton_3step_fdivs", "newton_3step_ops",
    "newton_step_errs_dec15", "p_q", "q_q", "radius_q",
})
_P2_SIN_KEYS = frozenset({"lipschitz_q", "p_q", "q_q", "radius_q", "sin_1deg_3step_dec10", "step3_delta_dec12"})
_P2_NC_KEYS = frozenset({"exact_root_q", "kashi_3step_err_dec6", "newton_3step_err_dec12", "newton_beats_kashi_by_1000x", "p_q", "q_q", "slope_at_root_q"})
_P2_PC_KEYS = frozenset({"exact_root_q", "init_err_q", "kashi_3step_err_dec6", "kashi_strictly_diverges", "newton_3step_err_dec12", "newton_strictly_converges", "p_q", "q_q", "slope_at_root_q"})
_P3_KEYS = frozenset({"banu_musa_aletheion_thermal", "ibn_al_nafis_septal_firewall"})
_P3_BM_KEYS = frozenset({
    "aletheion_guard_sha256", "aletheion_thermal_receipt_sha256", "cpu_deadband_c", "cpu_restore_c", "cpu_shed_c",
    "gpu_deadband_c", "gpu_restore_c", "gpu_shed_c", "hysteretic_deadband_switches",
    "law5_analog_vs_discrete_obstruction", "live_cpu_rosen_discriminant_q", "live_gpu_rosen_discriminant_q",
    "restore_hold_s", "shed_hold_s", "zero_deadband_chatter_switches",
})
_P3_NF_KEYS = frozenset({
    "galen_foster_q", "galen_g_eff_rv_lv_q", "galen_inertia", "galen_pulmonary_frac_q", "galen_shunt_bypass_frac_q",
    "law5_valved_asymmetry_obstruction", "nafis_foster_q", "nafis_g_eff_rv_lv_q", "nafis_inertia",
    "nafis_pulmonary_frac_q", "nafis_shunt_bypass_frac_q", "rayleigh_conductance_drop_q",
})
_P4_KEYS = frozenset({
    "all_325_pairs_strictly_compounded", "cross_millennium_schur_compounding", "edge_class_counts",
    "edge_era_counts", "foster_sum_q", "higher_order_simplices", "kirchhoff_index_dec4", "laplacian_inertia",
    "max_compounding_gain_dec4", "max_compounding_pair", "min_compounding_gain_dec4", "min_compounding_pair",
    "n_classical_nodes", "n_edges", "n_modern_nodes", "n_nodes", "silo_cut_destruction",
    "t3_cross_millennium_blowup", "total_conductance",
})
_P4_ECC_KEYS = frozenset({"EXACT_COMMUTE", "CONDITIONAL_BRIDGE", "EXACT_OBSTRUCTION"})
_P4_EEC_KEYS = frozenset({"modern_modern", "classical_classical", "cross_millennium"})
_P4_XM_KEYS = frozenset({
    "all_120_modern_pairs_boosted_by_classical", "all_45_classical_pairs_boosted_by_modern",
    "classical_boost_max_pct_dec2", "classical_boost_median_pct_dec2", "classical_boost_min_pct_dec2",
    "isolated_k10_foster_q", "isolated_k10_inertia", "isolated_k16_foster_q", "isolated_k16_inertia",
    "modern_boost_max_pct_dec2", "modern_boost_median_pct_dec2", "modern_boost_min_pct_dec2",
})
_P4_HO_KEYS = frozenset({
    "order2_triangle_counts", "order2_triangles_total", "order3_bianchi_coboundary_zero_all",
    "order3_k4_exact_locks", "order3_tetrahedra_total", "order4_5cells_obstruction_hist",
    "order4_5cells_total", "order4_5cells_zero_obstruction", "order4_k5_exact_locks",
})
_P4_TRI_KEYS = frozenset({"EXACT_TRANSITIVE", "CONDITIONAL_CLEAN", "FRUSTRATED_ODD_Z2", "MULTI_WALL_EVEN"})
_P4_SC_KEYS = frozenset({"balanced_13_13", "era_silo_16_10"})
_P4_CUT_ORDER_KEYS = frozenset({"order1_edges", "order2_triangles", "order3_tetrahedra", "order4_5cells"})
_P4_CUT_ENTRY_KEYS = frozenset({"destroyed", "total", "destroyed_pct_dec2"})
_P4_T3_KEYS = frozenset({"cross_obstructions_ranked", "ranked_edges", "sherman_morrison_matches_direct_inversion_on_top1"})
_P4_T3_ROW_KEYS = frozenset({
    "pair", "obstruction", "incident_triangles_flipped", "frustrated_resolved",
    "clean_frustrated", "net_frustrated_reduction", "r_eff_before_dec6",
    "delta_kirchhoff_q", "delta_kirchhoff_dec6",
})

# Full R12+ Lean 4 static trust-escape rules (pure-Init file: no quotes, guillemets, macros, imports, +native, set_option, panic!/unreachable!)
_LEAN4_BANNED_RE = re.compile(
    r"\b(?:sorry|admit|axiom|unsafe|native_decide|sorryAx|ofReduceBool|ofReduceNat|"
    r"trustCompiler|mkSorry|run_cmd|run_meta|initialize|builtin_initialize|"
    r"macro|macro_rules|elab|elab_rules|syntax|declare_syntax_cat|interpolatedStr|"
    r"dbg_trace|dbgTrace|dbgTraceVal|dbgTraceValId|dbgTraceIfShared|dbgSleep|dbgStackTrace|"
    r"panicWithPosWithDecl|throwError|set_option|"
    r"notation|prefix|infix|infixl|infixr|postfix|csimp|opaque|partial)\b"
    r"|\b(?:panic|unreachable)!(?![\w'!?])"
    r"|\bLean\s*\."
    r"|\bdebug\s*\.\s*(?:skipKernelTC|byAsSorry|proofAsSorry|terminalTacticsAsSorry)\b"
    r"|(?:@|(?<!\.)\battribute\s*)\[[^\]]*\b(?:extern|implemented_by|export|init|builtin_init)\b"
    r"|(?<!\w)\+\s*native\b|\bnative\b(?!\s*:=\s*(?:Bool\.)?false\s*[),}])|\bDecide(?:Config|\.Config)\b|\bconfig\s*:="
    r"|#(?:eval!?(?![\w'!?])|reduce(?![\w'!?])|exit(?![\w'!?])|guard(?:_msgs)?(?![\w'!?])|check(?![\w'!?])|synth(?![\w'!?])|print(?![\w'!?])(?!\s+axioms[ \t]+[A-Za-z_]))"
    r"|(?:^|\n)[ \t]*(?:(?:public|private|meta)\s+)*import\s+"
    r'|["«»]',
    flags=re.DOTALL,
)
_LEAN4_AXIOM_NONE_RE = re.compile(r"^'([^']+)' does not depend on any axioms$")
_LEAN4_AXIOM_DEP_RE = re.compile(r"^'([^']+)' depends on axioms: \[([^\]]*)\]$")


# ---------------------------------------------------------------------------
# Zone-B Path, Darwin Prefix, CWD/$PWD, Atomic dir_fd & Atomic Write
# ---------------------------------------------------------------------------

def _require_concrete_path(path: Any, label: str) -> Path:
    oracle.require_ok(type(path) in _EXACT_PATH_TYPES, "INVALID_PATH_TYPE", f"{label}: concrete Path required")
    raw_s = oracle.require_exact_str(str(path), label)
    oracle.require_ok("\x00" not in raw_s, "NUL_BYTE_FORBIDDEN", f"{label}: NUL byte forbidden")
    return path


def _normalize_darwin_system_prefix(path: Path, *, allow_exact: bool = False) -> Path:
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
        cwd = Path.cwd()
    except OSError as exc:
        raise oracle.S91Error("CWD_UNAVAILABLE", f"{label}: CWD unavailable") from exc
    oracle.require_exact_str(str(cwd), f"{label} CWD")
    return cwd


def _check_pwd_no_symlinks(label: str) -> None:
    pwd = os.environ.get("PWD", "")
    if not pwd.startswith("/"):
        return
    oracle.require_exact_str(pwd, f"{label} PWD")
    oracle.require_ok("\x00" not in pwd, "NUL_BYTE_FORBIDDEN", f"{label} PWD: NUL byte forbidden")
    pwd_path = _normalize_darwin_system_prefix(Path(pwd), allow_exact=True)
    try:
        pwd_st = os.stat(pwd_path)
        cwd_st = os.stat(".")
    except OSError:
        return
    if (pwd_st.st_dev, pwd_st.st_ino) != (cwd_st.st_dev, cwd_st.st_ino):
        return
    try:
        dfd = os.open("/", _DIR_OPEN_FLAGS)
    except OSError as exc:
        raise oracle.S91Error("CWD_UNAVAILABLE", f"{label}: cannot open root for PWD") from exc
    try:
        for part in pwd_path.parts[1:]:
            try:
                next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise oracle.S91Error("SYMLINK_ANCESTOR_FORBIDDEN", f"{label}: symlink PWD ancestor") from exc
                raise oracle.S91Error("CWD_UNAVAILABLE", f"{label}: PWD ancestor unavailable") from exc
            os.close(dfd)
            dfd = next_fd
    finally:
        os.close(dfd)


def _open_dir_chain(target: Path, label: str, *, create_parents: bool) -> tuple[int, str]:
    if target.is_absolute():
        parts = _normalize_darwin_system_prefix(target).parts[1:]
    else:
        cwd = _normalize_darwin_system_prefix(_safe_cwd(label), allow_exact=True)
        _check_pwd_no_symlinks(label)
        parts = cwd.parts[1:] + target.parts
    oracle.require_ok(
        len(parts) >= 1 and parts[-1] != "..",
        "NOT_A_REGULAR_FILE",
        f"{label}: path does not name a regular file leaf",
    )
    parent_parts, leaf = parts[:-1], parts[-1]
    err_code = "FILE_WRITE_ERROR" if create_parents else "FILE_READ_ERROR"
    try:
        dfd = os.open("/", _DIR_OPEN_FLAGS)
    except OSError as exc:
        raise oracle.S91Error(err_code, f"{label}: cannot open root") from exc
    try:
        for part in parent_parts:
            try:
                next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
            except OSError as exc:
                if create_parents and exc.errno == errno.ENOENT:
                    try:
                        os.mkdir(part, 0o755, dir_fd=dfd)
                    except FileExistsError:
                        pass
                    except OSError as mk_exc:
                        raise oracle.S91Error("FILE_WRITE_ERROR", f"{label}: mkdir failed") from mk_exc
                    try:
                        next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
                    except OSError as re_exc:
                        raise oracle.S91Error("FILE_WRITE_ERROR", f"{label}: open created dir failed") from re_exc
                elif exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise oracle.S91Error("SYMLINK_FORBIDDEN", f"{label}: symlink ancestor forbidden") from exc
                else:
                    raise oracle.S91Error(err_code, f"{label}: ancestor unavailable") from exc
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
                raise oracle.S91Error("SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden") from exc
            raise oracle.S91Error("FILE_READ_ERROR", f"{label}: open failed") from exc
    finally:
        os.close(dfd)

    chunks: list[bytes] = []
    total = 0
    try:
        st_f = os.fstat(fd)
        oracle.require_ok(stat.S_ISREG(st_f.st_mode), "NOT_A_REGULAR_FILE", f"{label}: not a regular file")
        oracle.require_ok(st_f.st_nlink <= 1, "HARDLINK_FORBIDDEN", f"{label}: hardlink forbidden")
        oracle.require_ok(st_f.st_size <= max_bytes, "FILE_TOO_LARGE", f"{label}: size exceeds cap")
        while total <= max_bytes:
            chunk = os.read(fd, min(_READ_CHUNK_BYTES, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    except oracle.S91Error:
        raise
    except OSError as exc:
        raise oracle.S91Error("FILE_READ_ERROR", f"{label}: read failed") from exc
    finally:
        os.close(fd)
    oracle.require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"{label}: stream exceeds cap")
    return b"".join(chunks)


def write_regular_bytes_safe(path: Path, payload: bytes, label: str = "output") -> None:
    global _TEMP_SEQ
    oracle.require_ok(type(payload) is bytes, "INVALID_PAYLOAD_BYTES", f"{label}: exact bytes required")
    target = _require_concrete_path(path, label)
    dfd, leaf = _open_dir_chain(target, label, create_parents=True)
    tmp_name: str | None = None
    try:
        try:
            st_existing = os.lstat(leaf, dir_fd=dfd)
        except FileNotFoundError:
            st_existing = None
        except OSError as exc:
            raise oracle.S91Error("FILE_WRITE_ERROR", f"{label}: lstat failed") from exc
        if st_existing is not None:
            oracle.require_ok(not stat.S_ISLNK(st_existing.st_mode), "SYMLINK_FORBIDDEN", f"{label}: symlink leaf")
            oracle.require_ok(stat.S_ISREG(st_existing.st_mode), "NOT_A_REGULAR_FILE", f"{label}: non-regular target")
            oracle.require_ok(st_existing.st_nlink <= 1, "HARDLINK_FORBIDDEN", f"{label}: hardlinked target")

        pid = os.getpid()
        for _ in range(64):
            with _TEMP_NAME_LOCK:
                _TEMP_SEQ += 1
                seq_num = _TEMP_SEQ
                cand = f".s91.{pid}.{seq_num}.{secrets.token_hex(8)}.tmp"
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
                raise oracle.S91Error("FILE_WRITE_ERROR", f"{label}: temp open failed") from exc
        else:
            raise oracle.S91Error("FILE_WRITE_ERROR", f"{label}: temp slots exhausted")

        try:
            os.fchmod(fd, 0o600)
            view = memoryview(payload)
            written = 0
            while written < len(view):
                n_written = os.write(fd, view[written:])
                oracle.require_ok(n_written > 0, "FILE_WRITE_ERROR", f"{label}: short write 0")
                written += n_written
            os.fsync(fd)
            st_tmp = os.fstat(fd)
            oracle.require_ok(st_tmp.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: temp nlink altered")
        except oracle.S91Error:
            raise
        except OSError as exc:
            raise oracle.S91Error("FILE_WRITE_ERROR", f"{label}: write/fsync failed") from exc
        finally:
            os.close(fd)

        try:
            os.replace(tmp_name, leaf, src_dir_fd=dfd, dst_dir_fd=dfd)
            tmp_name = None
            os.fsync(dfd)
        except OSError as exc:
            raise oracle.S91Error("FILE_WRITE_ERROR", f"{label}: atomic replace failed") from exc
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
        os.close(dfd)


# ---------------------------------------------------------------------------
# Strict Zero-Float Canonical JSON & Canonical Rational Parsers
# ---------------------------------------------------------------------------

def _parse_bounded_int(token: str) -> int:
    s = oracle.require_exact_str(token, "json_int")
    neg = s.startswith("-")
    body = s[1:] if neg else s
    oracle.require_ok(oracle.is_ascii_digits(body), "INVALID_INT_TOKEN", "non-ASCII digits")
    oracle.require_ok(len(body) <= oracle.MAX_INT_DIGITS, "INT_TOO_LARGE", "int digits cap")
    oracle.require_ok(not (len(body) > 1 and body[0] == "0"), "NONCANONICAL_INT", "leading zero")
    oracle.require_ok(not (neg and body == "0"), "NONCANONICAL_INT", "negative zero")
    val = int(s)
    oracle.require_ok(val.bit_length() <= oracle.MAX_INT_BITS, "INT_TOO_LARGE", "int bits cap")
    return val


def _reject_float(token: str) -> Any:
    raise oracle.S91Error("FLOAT_FORBIDDEN", f"IEEE-754 float forbidden: {token!r}")


def _reject_const(token: str) -> Any:
    raise oracle.S91Error("NONFINITE_JSON_CONSTANT", f"JSON constant forbidden: {token!r}")


def _no_dup_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        oracle.require_ok(k not in out, "DUPLICATE_JSON_KEY", f"duplicate key {k!r}")
        out[k] = v
    return out


def parse_strict_json_bytes(raw: bytes, label: str = "json", *, require_canonical: bool = True) -> dict[str, Any]:
    oracle.require_ok(type(raw) is bytes, "INVALID_BYTES", f"{label}: exact bytes required")
    oracle.require_ok(not raw.startswith(b"\xef\xbb\xbf"), "BOM_FORBIDDEN", f"{label}: UTF-8 BOM forbidden")
    oracle.require_ok(b"\r" not in raw, "CRLF_FORBIDDEN", f"{label}: CR forbidden")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise oracle.S91Error("INVALID_UTF8", f"{label}: invalid UTF-8") from exc
    try:
        obj = json.loads(
            text,
            parse_float=_reject_float,
            parse_int=_parse_bounded_int,
            parse_constant=_reject_const,
            object_pairs_hook=_no_dup_pairs,
        )
    except oracle.S91Error:
        raise
    except (ValueError, RecursionError) as exc:
        raise oracle.S91Error("INVALID_JSON", f"{label}: malformed JSON") from exc
    oracle.require_ok(type(obj) is dict, "INVALID_ROOT_TYPE", f"{label}: root must be dict")
    oracle.validate_strict_json_tree(obj, label)
    if require_canonical:
        oracle.require_ok(
            hmac.compare_digest(raw, oracle.canonical_json_bytes(obj)),
            "NONCANONICAL_JSON",
            f"{label}: not canonical ASCII LF JSON",
        )
    return obj


def parse_canonical_rational_str(val: Any, label: str) -> Fraction:
    s = oracle.require_exact_str(val, label)
    oracle.require_ok(len(s) > 0, "INVALID_RATIONAL", f"{label}: empty")
    if "/" in s:
        parts = s.split("/")
        oracle.require_ok(len(parts) == 2, "INVALID_RATIONAL", f"{label}: multiple slashes")
        num_s, den_s = parts[0], parts[1]
        num = _parse_bounded_int(num_s)
        oracle.require_ok(not den_s.startswith("-"), "INVALID_RATIONAL", f"{label}: negative den")
        den = _parse_bounded_int(den_s)
        oracle.require_ok(den > 1, "NONCANONICAL_RATIONAL", f"{label}: den must be > 1")
        q = Fraction(num, den)
        oracle.require_ok(q.denominator == den, "NONCANONICAL_RATIONAL", f"{label}: not reduced")
        return q
    return Fraction(_parse_bounded_int(s), 1)


def _require_exact_dict(obj: Any, keys: frozenset[str], label: str) -> dict[str, Any]:
    oracle.require_ok(type(obj) is dict, "INVALID_SCHEMA_DICT", f"{label}: exact dict required")
    oracle.require_ok(frozenset(obj.keys()) == keys, "INVALID_SCHEMA_KEYS", f"{label}: keyset mismatch")
    return obj


# ---------------------------------------------------------------------------
# Live Lean 4.36.0 (Zero-TOCTOU Private Temp Copy) & R11+ Static Lean Gate
# ---------------------------------------------------------------------------

def _strip_lean4_for_static_gate(source: str) -> str:
    out: list[str] = []
    i = 0
    n = len(source)
    depth = 0
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if depth > 0:
            if ch == "/" and nxt == "-":
                depth += 1
                out.append("  ")
                i += 2
            elif ch == "-" and nxt == "/":
                depth -= 1
                out.append("  ")
                i += 2
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if ch == "/" and nxt == "-":
            depth = 1
            out.append("  ")
            i += 2
        elif ch == "-" and nxt == "-":
            out.append("  ")
            i += 2
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
        else:
            out.append(ch)
            i += 1
    oracle.require_ok(depth == 0, "LEAN4_UNTERMINATED_LEX", "unterminated Lean block comment")
    return "".join(out)


def static_gate_lean4_source(source: str) -> None:
    s = oracle.require_exact_str(source, "lean_source")
    oracle.require_ok("\r" not in s and "\x00" not in s, "LEAN4_BAD_CHARS", "CR/NUL in Lean source")
    cleaned = _strip_lean4_for_static_gate(s)
    m = _LEAN4_BANNED_RE.search(cleaned)
    oracle.require_ok(m is None, "LEAN4_TRUST_ESCAPE", f"banned Lean construct: {m.group(0)!r}" if m else "")
    for thm in oracle.LEAN_THEOREM_NAMES:
        short = thm.split(".")[-1]
        oracle.require_ok(f"theorem {short}" in cleaned, "LEAN4_MISSING_THEOREM", f"missing {short}")
        oracle.require_ok(f"#print axioms {thm}" in cleaned, "LEAN4_MISSING_PRINT_AXIOMS", f"missing #print axioms {thm}")


def resolve_lean_binary() -> str:
    env_bin = os.environ.get("ALETHEIA_LEAN_BIN")
    if env_bin is not None:
        oracle.require_exact_str(env_bin, "ALETHEIA_LEAN_BIN")
        p = Path(env_bin)
        oracle.require_ok(p.is_file() and os.access(str(p), os.X_OK), "LEAN_BINARY_UNAVAILABLE", "ALETHEIA_LEAN_BIN unusable")
        return str(p)
    found = shutil.which("lean")
    if found is not None and os.access(found, os.X_OK):
        return found
    home_env = os.environ.get("HOME")
    if home_env:
        home_path = Path(home_env)
        for rel in ((".local", "bin", "lean"), (".elan", "bin", "lean")):
            cand = home_path.joinpath(*rel)
            if cand.is_file() and os.access(str(cand), os.X_OK):
                return str(cand)
    raise oracle.S91Error("LEAN_BINARY_UNAVAILABLE", "lean executable not found")


def verify_lean4_file_live(lean_path: Path) -> dict[str, Any]:
    raw = read_regular_bytes_capped(lean_path, "lean_source", max_bytes=1024 * 1024)
    try:
        src = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise oracle.S91Error("INVALID_UTF8", "Lean source not UTF-8") from exc
    static_gate_lean4_source(src)
    lean_bin = resolve_lean_binary()
    clean_env = {k: os.environ[k] for k in _SAFE_LEAN_ENV_KEYS if k in os.environ}
    try:
        v_proc = subprocess.run([lean_bin, "--version"], capture_output=True, text=True, timeout=30, check=False, env=clean_env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise oracle.S91Error("LEAN_EXEC_ERROR", "lean --version failed") from exc
    oracle.require_ok(v_proc.returncode == 0 and "4.36.0" in v_proc.stdout, "LEAN_VERSION_MISMATCH", "Lean 4.36.0 required")

    # Zero-TOCTOU: elaborate exact audited bytes from a private 0o700 temp dir with scrubbed LEAN_PATH/LEAN_OPTS
    with tempfile.TemporaryDirectory(prefix="s91_lean_") as tmp_dir:
        os.chmod(tmp_dir, 0o700)
        tmp_lean = Path(tmp_dir) / "TranshistoricalK26AndTusiCure.lean"
        write_regular_bytes_safe(tmp_lean, raw, "tmp_lean")
        try:
            proc = subprocess.run([lean_bin, str(tmp_lean)], capture_output=True, text=True, timeout=120, check=False, env=clean_env)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise oracle.S91Error("LEAN_EXEC_ERROR", "lean elaboration failed") from exc

    oracle.require_ok(proc.returncode == 0, "LEAN_COMPILE_FAIL", f"lean rc={proc.returncode}")
    oracle.require_ok(proc.stderr.strip() == "", "LEAN_STDERR_NONEMPTY", "lean stderr must be empty")
    oracle.require_ok("warning:" not in proc.stdout.lower(), "LEAN_WARNING_FORBIDDEN", "lean warning forbidden")

    joined_lines: list[str] = []
    pending = ""
    for raw_line in proc.stdout.splitlines():
        s_line = raw_line.strip()
        if not s_line:
            continue
        if pending:
            pending = f"{pending} {s_line}"
            if "]" in s_line:
                joined_lines.append(pending)
                pending = ""
        elif "[" in s_line and "]" not in s_line:
            pending = s_line
        else:
            joined_lines.append(s_line)
    oracle.require_ok(pending == "", "LEAN_UNEXPECTED_STDOUT", "unterminated axiom list")

    seen: dict[str, list[str]] = {}
    for s_line in joined_lines:
        m_none = _LEAN4_AXIOM_NONE_RE.match(s_line)
        if m_none is not None:
            thm_name = m_none.group(1)
            oracle.require_ok(thm_name not in seen, "LEAN_DUPLICATE_THEOREM", f"duplicate axiom line: {thm_name}")
            seen[thm_name] = []
            continue
        m_dep = _LEAN4_AXIOM_DEP_RE.match(s_line)
        oracle.require_ok(m_dep is not None, "LEAN_UNEXPECTED_STDOUT", f"unexpected lean line: {s_line[:80]}")
        thm_name = m_dep.group(1)
        oracle.require_ok(thm_name not in seen, "LEAN_DUPLICATE_THEOREM", f"duplicate axiom line: {thm_name}")
        axs = [a.strip() for a in m_dep.group(2).split(",") if a.strip()]
        for ax in axs:
            oracle.require_ok(ax in _ALLOWED_LEAN_AXIOMS, "LEAN_FORBIDDEN_AXIOM", f"forbidden axiom {ax}")
        seen[thm_name] = axs
    oracle.require_ok(frozenset(seen.keys()) == frozenset(oracle.LEAN_THEOREM_NAMES), "LEAN_THEOREM_SET_MISMATCH", "axioms set mismatch")
    return {
        "lean_version": v_proc.stdout.strip().splitlines()[0],
        "theorems_verified": len(seen),
        "lean_source_sha256": oracle.sha256_hex(raw),
    }


# ---------------------------------------------------------------------------
# Fail-Closed Secondary Audit (FR0 / SEC) & Full Replay (FR1)
# ---------------------------------------------------------------------------

def _require_inertia(val: Any, expected: list[int], label: str) -> None:
    oracle.require_ok(type(val) is list and len(val) == 3, "INVALID_INERTIA", label)
    for elem in val:
        oracle.require_exact_int(elem, label, lo=0, hi=26)
    oracle.require_ok(val == expected, "INERTIA_MISMATCH", f"{label}: expected {expected}")


def _require_node_pair(val: Any, label: str) -> str:
    s = oracle.require_exact_str(val, label)
    parts = s.split("-")
    oracle.require_ok(
        len(parts) == 2 and parts[0] in _K26_NODE_IDS and parts[1] in _K26_NODE_IDS and parts[0] != parts[1],
        "INVALID_NODE_PAIR",
        label,
    )
    return s


def _audit_silo_cut(cut_obj: Any, expected_destroyed: tuple[int, int, int, int], label: str) -> None:
    cut = _require_exact_dict(cut_obj, _P4_CUT_ORDER_KEYS, label)
    specs = (
        ("order1_edges", expected_destroyed[0], 325),
        ("order2_triangles", expected_destroyed[1], 2600),
        ("order3_tetrahedra", expected_destroyed[2], 14950),
        ("order4_5cells", expected_destroyed[3], 65780),
    )
    for order_k, exp_d, exp_tot in specs:
        entry = _require_exact_dict(cut[order_k], _P4_CUT_ENTRY_KEYS, f"{label}.{order_k}")
        oracle.require_exact_int(entry["destroyed"], f"{label}.{order_k}.d", lo=exp_d, hi=exp_d)
        oracle.require_exact_int(entry["total"], f"{label}.{order_k}.t", lo=exp_tot, hi=exp_tot)
        exp_pct = oracle.dec_from_q(Fraction(exp_d * 100, exp_tot), 2)
        oracle.require_ok(entry["destroyed_pct_dec2"] == exp_pct, "PILLAR4_SILO_PCT", f"{label}.{order_k}")


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Fail-closed field-complete semantic & algebraic auditor enforced under BOTH full_replay=True and False."""
    oracle.require_ok(type(payload) is dict, "INVALID_PAYLOAD_TYPE", "payload must be exact dict")
    oracle.validate_strict_json_tree(payload, "payload")
    _require_exact_dict(payload, _PAYLOAD_KEYS, "payload")
    oracle.require_ok(payload["schema_version"] == oracle.SCHEMA_VERSION, "SCHEMA_MISMATCH", "schema_version")
    oracle.require_ok(payload["track_id"] == oracle.TRACK_ID, "SCHEMA_MISMATCH", "track_id")
    oracle.require_ok(payload["oracle_class"] == "exact+anchor", "SCHEMA_MISMATCH", "oracle_class")
    oracle.require_ok(payload["novelty_classification"] == "N1", "SCHEMA_MISMATCH", "novelty")

    pa = _require_exact_dict(payload["pinned_artifacts"], _PINNED_KEYS, "pinned_artifacts")
    oracle.require_ok(pa["heritage_corpus_commit_sha"] == oracle.HERITAGE_CORPUS_SHA, "SCHEMA_MISMATCH", "heritage_sha")
    oracle.require_ok(pa["anchor_file"] == "s91_tusi_circularep_live_anchor.json", "SCHEMA_MISMATCH", "anchor_file")
    oracle.require_ok(pa["anchor_sha256"] == EXPECTED_ANCHOR_SHA256, "PINNED_SHA_MISMATCH", "anchor_sha256")
    oracle.require_ok(pa["lean_source"] == "TranshistoricalK26AndTusiCure.lean", "SCHEMA_MISMATCH", "lean_source")
    oracle.require_ok(pa["lean_source_sha256"] == EXPECTED_LEAN_SOURCE_SHA256, "PINNED_SHA_MISMATCH", "lean_source_sha256")
    oracle.require_ok(pa["lean_toolchain"] == oracle.EXPECTED_LEAN_TOOLCHAIN, "SCHEMA_MISMATCH", "lean_toolchain")
    oracle.require_ok(pa["lean_toolchain_sha256"] == EXPECTED_TOOLCHAIN_SHA256, "PINNED_SHA_MISMATCH", "lean_toolchain_sha256")
    oracle.require_ok(pa["lakefile_sha256"] == EXPECTED_LAKEFILE_SHA256, "PINNED_SHA_MISMATCH", "lakefile_sha256")
    thm_n = oracle.require_exact_int(
        pa["lean_theorem_count"], "lean_theorem_count", lo=len(oracle.LEAN_THEOREM_NAMES), hi=len(oracle.LEAN_THEOREM_NAMES)
    )
    thms = pa["lean_theorem_names"]
    oracle.require_ok(type(thms) is list and tuple(thms) == oracle.LEAN_THEOREM_NAMES, "THEOREM_LIST_MISMATCH", "lean_theorem_names")

    # 26 Pinned Nodes (exact dict & exact pin match against K26_NODES)
    nodes = payload["k26_nodes"]
    oracle.require_ok(type(nodes) is list and len(nodes) == 26, "INVALID_NODES", "26 nodes required")
    for idx, nd in enumerate(nodes):
        row = _require_exact_dict(nd, _NODE_KEYS, f"node[{idx}]")
        oracle.require_ok(row == oracle.K26_NODES[idx], "INVALID_NODE_PIN", f"node[{idx}]")

    # Pillar 1: Al-Tusi Counter-Rotating Dual-Loop Cure + Law-5 Trade-off
    p1 = _require_exact_dict(payload["pillar1_tusi_circularep_cure"], _P1_KEYS, "pillar1")
    oracle.require_ok(p1["anchor_sha256"] == EXPECTED_ANCHOR_SHA256, "PILLAR1_ANCHOR_SHA", "anchor sha mismatch")
    oracle.require_ok(p1["upstream_commit_sha"] == oracle.CIRCULAREP_COMMIT_SHA, "PILLAR1_COMMIT", "commit mismatch")
    oracle.require_ok(p1["upstream_best_json_sha256"] == oracle.CIRCULAREP_BEST_SHA, "PILLAR1_BEST", "best sha mismatch")
    w1 = _require_exact_dict(p1["exact_q_witnesses"], _P1_WITNESS_KEYS, "p1.witnesses")
    for wname, wkeys in (
        ("planar_tusi_couple", _P1_W_PLANAR_KEYS),
        ("s76_elliptic_curl", _P1_W_EIG_KEYS),
        ("law5_nonnormal_destabilization", _P1_W_LAW5_KEYS),
    ):
        ww = _require_exact_dict(w1[wname], wkeys, f"p1.{wname}")
        t11 = parse_canonical_rational_str(ww["t11_q"], f"{wname}.t11")
        t12 = parse_canonical_rational_str(ww["t12_q"], f"{wname}.t12")
        t22 = parse_canonical_rational_str(ww["t22_q"], f"{wname}.t22")
        k12 = parse_canonical_rational_str(ww["k12_q"], f"{wname}.k12")
        disc = parse_canonical_rational_str(ww["discriminant_t_q"], f"{wname}.disc")
        tf = parse_canonical_rational_str(ww["t_fro_sq_q"], f"{wname}.tf")
        kf = parse_canonical_rational_str(ww["k_fro_sq_q"], f"{wname}.kf")
        mf = parse_canonical_rational_str(ww["m_fro_sq_q"], f"{wname}.mf")
        oracle.require_ok(disc == (t11 + t22) ** 2 - 4 * (t11 * t22 - t12 * t12), "PILLAR1_DISC", wname)
        oracle.require_ok(tf == t11 * t11 + 2 * t12 * t12 + t22 * t22, "PILLAR1_TF", wname)
        oracle.require_ok(kf == 2 * k12 * k12, "PILLAR1_KF", wname)
        oracle.require_ok(mf == tf + kf, "PILLAR1_PYTH", wname)
        oracle.require_ok(
            all(oracle.require_bool(ww[fk], f"{wname}.{fk}") for fk in ("discriminant_nonneg", "h2_off_diag_zero", "pythagorean_exact")),
            "PILLAR1_WITNESS_FLAGS",
            wname,
        )
        if "t_eigenvalues_q" in ww:
            eigs = ww["t_eigenvalues_q"]
            oracle.require_ok(type(eigs) is list and len(eigs) == 2, "PILLAR1_EIGS", wname)
            e0 = parse_canonical_rational_str(eigs[0], f"{wname}.e0")
            e1 = parse_canonical_rational_str(eigs[1], f"{wname}.e1")
            oracle.require_ok(e0 + e1 == t11 + t22 and e0 * e1 == t11 * t22 - t12 * t12, "PILLAR1_VIETA", wname)
            oracle.require_ok(parse_canonical_rational_str(ww["t_rho_q"], f"{wname}.trho") == max(abs(e0), abs(e1)), "PILLAR1_TRHO", wname)
    oracle.require_ok(parse_canonical_rational_str(w1["planar_tusi_couple"]["t12_q"], "planar.t12") == 0, "PILLAR1_PLANAR", "planar curl != 0")
    oracle.require_ok(parse_canonical_rational_str(w1["planar_tusi_couple"]["k12_q"], "planar.k12") != 0, "PILLAR1_PLANAR_K", "planar skew == 0")
    oracle.require_ok(parse_canonical_rational_str(w1["s76_elliptic_curl"]["t_rho_q"], "ell.trho") < 1, "PILLAR1_ELLIPTIC", "elliptic rho >= 1")
    oracle.require_ok(parse_canonical_rational_str(w1["law5_nonnormal_destabilization"]["t_rho_q"], "nn.trho") > 1, "PILLAR1_LAW5", "destab rho <= 1")
    oracle.require_ok(parse_canonical_rational_str(w1["law5_nonnormal_destabilization"]["raw_rho_q"], "nn.rrho") < 1, "PILLAR1_LAW5", "raw rho >= 1")
    oracle.require_ok(
        oracle.require_bool(w1["law5_nonnormal_destabilization"]["destabilizes_contractive_loop"], "nn.destab") is True,
        "PILLAR1_LAW5_FLAG",
        "destabilizes_contractive_loop",
    )

    l300 = _require_exact_dict(p1["live_300_puzzle_summary"], _P1_L300_KEYS, "p1.l300")
    oracle.require_exact_int(l300["n_puzzles"], "l300.n", lo=300, hi=300)
    oracle.require_exact_int(l300["raw_complex_dominant_count"], "l300.raw_cx", lo=39, hi=39)
    oracle.require_exact_int(l300["tusi_complex_dominant_count"], "l300.tusi_cx", lo=0, hi=0)
    oracle.require_exact_int(l300["tusi_cx_improved_count"], "l300.imp", lo=39, hi=39)
    oracle.require_exact_int(l300["bendixson_bound_verified_count"], "l300.bend", lo=300, hi=300)
    oracle.require_exact_int(l300["law5_norm2_tusi_lt_norm2_raw_count"], "l300.n2lt", lo=300, hi=300)
    oracle.require_exact_int(l300["law5_rho_tusi_gt_rho_raw_count"], "l300.rhogt", lo=300, hi=300)
    oracle.require_exact_int(l300["law5_tusi_contractive_count"], "l300.contr", lo=300, hi=300)
    oracle.require_exact_int(l300["law5_cs21_jvp_cost_multiplier"], "l300.jvp", lo=2, hi=2)
    raw_pi = oracle.parse_decimal_or_sci_to_q(l300["raw_pi60_cx_median_dec6"], "l300.raw_pi")
    tusi_pi = oracle.parse_decimal_or_sci_to_q(l300["tusi_pi60_cx_median_sci"], "l300.tusi_pi")
    red_q = oracle.parse_decimal_or_sci_to_q(l300["cx_median_error_reduction_sci"], "l300.red")
    oracle.require_ok(0 < tusi_pi < raw_pi, "PILLAR1_PI_ORDER", "pi60 median ordering")
    oracle.require_ok(red_q > Fraction(1_000_000, 1), "PILLAR1_REDUCTION", "expected >1e6x error reduction")
    oracle.require_ok(abs(red_q * tusi_pi - raw_pi) < raw_pi * Fraction(1, 1000), "PILLAR1_RED_RATIO", "reduction ratio mismatch")
    raw_disp = oracle.parse_decimal_or_sci_to_q(l300["raw_cx_vs_re_disparity_sci"], "l300.rdisp")
    tusi_disp = oracle.parse_decimal_or_sci_to_q(l300["tusi_cx_vs_re_disparity_dec4"], "l300.tdisp")
    coll_q = oracle.parse_decimal_or_sci_to_q(l300["disparity_collapse_factor_sci"], "l300.coll")
    oracle.require_ok(tusi_disp > 0, "PILLAR1_TDISP", "tusi disparity <= 0")
    oracle.require_ok(coll_q > Fraction(1_000_000_000, 1), "PILLAR1_COLLAPSE", "expected >1e9x disparity collapse")
    oracle.require_ok(abs(coll_q * tusi_disp - raw_disp) < raw_disp * Fraction(1, 1000), "PILLAR1_COLL_RATIO", "disparity ratio mismatch")
    oracle.require_ok(0 < oracle.parse_decimal_or_sci_to_q(l300["norm2_median_drop_pct_dec2"], "l300.n2drop") < 100, "PILLAR1_N2DROP", "norm2 drop pct")
    oracle.require_ok(0 < oracle.parse_decimal_or_sci_to_q(l300["law5_rho_median_lift_pct_dec2"], "l300.rlift") < 100, "PILLAR1_RHOLIFT", "rho lift pct")
    oracle.require_ok(0 < oracle.parse_decimal_or_sci_to_q(l300["skew_fro_fraction_median_dec6"], "l300.skew") < 1, "PILLAR1_SKEW", "skew fraction")
    oracle.require_ok(oracle.parse_decimal_or_sci_to_q(l300["tusi_max_abs_imag_sci"], "l300.im") == 0, "PILLAR1_IMAG", "Tusi max |Im| must be 0")
    oracle.require_ok(0 <= oracle.parse_decimal_or_sci_to_q(l300["tusi_max_normality_dev_sci"], "l300.ndev") < Fraction(1, 10**12), "PILLAR1_NORMDEV", "normality dev")
    oracle.require_ok(0 <= oracle.parse_decimal_or_sci_to_q(l300["twin_h2_block_diag_max_err_sci"], "l300.h2err") < Fraction(1, 10**12), "PILLAR1_H2ERR", "H2 block err")
    oracle.require_ok(l300["worst_puzzle_id"] == _EXPECTED_WORST_PUZZLE_ID, "PILLAR1_WORST_ID", "worst_puzzle_id")
    w_raw = oracle.parse_decimal_or_sci_to_q(l300["worst_puzzle_raw_err_dec6"], "l300.wraw")
    w_tusi = oracle.parse_decimal_or_sci_to_q(l300["worst_puzzle_tusi_err_sci"], "l300.wtusi")
    oracle.require_ok(0 < w_tusi < w_raw, "PILLAR1_WORST_ERR", "worst puzzle error ordering")

    # Pillar 2: Al-Kashi Contractive Cubic vs Newton
    p2 = _require_exact_dict(payload["pillar2_kashi_cubic_vs_newton"], _P2_KEYS, "pillar2")
    nr = _require_exact_dict(p2["narrow_range_p45_witness"], _P2_NR_KEYS, "p2.nr")
    p_a = parse_canonical_rational_str(nr["p_q"], "nr.p")
    q_a = parse_canonical_rational_str(nr["q_q"], "nr.q")
    x_a = parse_canonical_rational_str(nr["exact_root_q"], "nr.x")
    r_a = parse_canonical_rational_str(nr["radius_q"], "nr.r")
    lip_a = parse_canonical_rational_str(nr["lipschitz_q"], "nr.lip")
    oracle.require_ok(p_a > 0, "PILLAR2_PA", "p_a <= 0")
    oracle.require_ok(r_a > 0, "PILLAR2_RA", "r_a <= 0")
    oracle.require_ok(abs(x_a) < r_a, "PILLAR2_XR", "|x_a| >= r_a")
    oracle.require_ok(p_a * x_a - x_a ** 3 == q_a, "PILLAR2_CUBIC", "cubic residual")
    oracle.require_ok(lip_a == 3 * r_a * r_a / p_a, "PILLAR2_LIP_EQ", "lipschitz formula")
    oracle.require_ok(lip_a < Fraction(1, 100), "PILLAR2_LIP", "narrow-range Lipschitz bound")
    k_errs = nr["kashi_step_errs_dec15"]
    oracle.require_ok(type(k_errs) is list and len(k_errs) == 3, "PILLAR2_KERRS", "kashi errs len")
    ke0, ke1, ke2 = (oracle.parse_decimal_or_sci_to_q(e, "nr.ke") for e in k_errs)
    oracle.require_ok(ke0 > ke1 > ke2 > 0, "PILLAR2_KDEC", "kashi errs decay")
    n_errs = nr["newton_step_errs_dec15"]
    oracle.require_ok(type(n_errs) is list and len(n_errs) == 3, "PILLAR2_NERRS", "newton errs len")
    ne0, ne1, ne2 = (oracle.parse_decimal_or_sci_to_q(e, "nr.ne") for e in n_errs)
    oracle.require_ok(ke0 > ne0 >= ne1 >= ne2 >= 0, "PILLAR2_NDEC", "newton errs decay")
    cheb_e = oracle.parse_decimal_or_sci_to_q(nr["chebyshev_deg3_err_dec15"], "nr.cheb")
    oracle.require_ok(ke1 < cheb_e, "PILLAR2_CHEB", "kashi 2-step >= cheb")
    oracle.require_ok(oracle.require_bool(nr["kashi_2step_beats_deg3_poly"], "nr.beats") is True, "PILLAR2_BEATS", "kashi beats poly")
    oracle.require_exact_int(nr["kashi_3step_ops"], "nr.kops", lo=9, hi=9)
    oracle.require_exact_int(nr["kashi_3step_fdivs"], "nr.kfdiv", lo=0, hi=0)
    oracle.require_exact_int(nr["newton_3step_ops"], "nr.nops", lo=15, hi=15)
    oracle.require_exact_int(nr["newton_3step_fdivs"], "nr.nfdiv", lo=3, hi=3)

    sb = _require_exact_dict(p2["sin_1deg_unscaled_witness"], _P2_SIN_KEYS, "p2.sin")
    p_b = parse_canonical_rational_str(sb["p_q"], "sin.p")
    q_b = parse_canonical_rational_str(sb["q_q"], "sin.q")
    r_b = parse_canonical_rational_str(sb["radius_q"], "sin.r")
    lip_b = parse_canonical_rational_str(sb["lipschitz_q"], "sin.lip")
    oracle.require_ok(p_b > 0, "PILLAR2_SIN_P", "sin p <= 0")
    oracle.require_ok(q_b > 0, "PILLAR2_SIN_Q", "sin q <= 0")
    oracle.require_ok(r_b > 0, "PILLAR2_SIN_R", "sin r <= 0")
    oracle.require_ok(lip_b == 3 * r_b * r_b / p_b, "PILLAR2_SIN_LIP_EQ", "sin lipschitz formula")
    oracle.require_ok(lip_b < Fraction(1, 100), "PILLAR2_SIN_LIP", "sin lipschitz bound")
    u_b = 2 * oracle.parse_decimal_or_sci_to_q(sb["sin_1deg_3step_dec10"], "sin.est")
    oracle.require_ok(0 < u_b < r_b, "PILLAR2_SIN_RANGE", "sin estimate range")
    oracle.require_ok(abs(p_b * u_b - u_b ** 3 - q_b) < Fraction(1, 10**8), "PILLAR2_SIN_RES", "sin cubic residual")
    oracle.require_ok(0 <= oracle.parse_decimal_or_sci_to_q(sb["step3_delta_dec12"], "sin.delta") < Fraction(1, 10**9), "PILLAR2_SIN_DELTA", "sin step3 delta")

    nc = _require_exact_dict(p2["law5_near_cliff_newton_wins"], _P2_NC_KEYS, "p2.nc")
    p_c = parse_canonical_rational_str(nc["p_q"], "nc.p")
    q_c = parse_canonical_rational_str(nc["q_q"], "nc.q")
    x_c = parse_canonical_rational_str(nc["exact_root_q"], "nc.x")
    s_c = parse_canonical_rational_str(nc["slope_at_root_q"], "nc.slope")
    oracle.require_ok(p_c > 0, "PILLAR2_NC_P", "nc p <= 0")
    oracle.require_ok(p_c * x_c - x_c ** 3 == q_c, "PILLAR2_NC_CUBIC", "nc cubic")
    oracle.require_ok(s_c == 3 * x_c * x_c / p_c, "PILLAR2_NC_SLOPE_EQ", "nc slope formula")
    oracle.require_ok(Fraction(1, 2) < s_c < 1, "PILLAR2_NC_SLOPE", "nc slope bounds")
    ke_c = oracle.parse_decimal_or_sci_to_q(nc["kashi_3step_err_dec6"], "nc.ke")
    ne_c = oracle.parse_decimal_or_sci_to_q(nc["newton_3step_err_dec12"], "nc.ne")
    oracle.require_ok(0 < 1000 * ne_c < ke_c, "PILLAR2_NC_RATIO", "newton 1000x ratio")
    oracle.require_ok(oracle.require_bool(nc["newton_beats_kashi_by_1000x"], "nc.nwins") is True, "PILLAR2_NWINS", "newton wins near cliff")

    pc = _require_exact_dict(p2["law5_post_cliff_kashi_diverges"], _P2_PC_KEYS, "p2.pc")
    p_d = parse_canonical_rational_str(pc["p_q"], "pc.p")
    q_d = parse_canonical_rational_str(pc["q_q"], "pc.q")
    x_d = parse_canonical_rational_str(pc["exact_root_q"], "pc.x")
    s_d = parse_canonical_rational_str(pc["slope_at_root_q"], "pc.slope")
    init_d = parse_canonical_rational_str(pc["init_err_q"], "pc.init")
    oracle.require_ok(p_d > 0, "PILLAR2_PC_P", "pc p <= 0")
    oracle.require_ok(p_d * x_d - x_d ** 3 == q_d, "PILLAR2_PC_CUBIC", "pc cubic")
    oracle.require_ok(s_d == 3 * x_d * x_d / p_d, "PILLAR2_SLOPE_EQ", "pc slope formula")
    oracle.require_ok(s_d > 1, "PILLAR2_SLOPE", "post-cliff slope <= 1")
    ke_d = oracle.parse_decimal_or_sci_to_q(pc["kashi_3step_err_dec6"], "pc.ke")
    ne_d = oracle.parse_decimal_or_sci_to_q(pc["newton_3step_err_dec12"], "pc.ne")
    oracle.require_ok(0 < ne_d < init_d < ke_d, "PILLAR2_PC_ORDER", "post-cliff divergence ordering")
    oracle.require_ok(oracle.require_bool(pc["kashi_strictly_diverges"], "pc.div") is True, "PILLAR2_DIV", "kashi must diverge")
    oracle.require_ok(oracle.require_bool(pc["newton_strictly_converges"], "pc.conv") is True, "PILLAR2_CONV", "newton must converge")

    # Pillar 3: Banu Musa & Ibn al-Nafis
    p3 = _require_exact_dict(payload["pillar3_banu_musa_and_ibn_al_nafis"], _P3_KEYS, "pillar3")
    bm = _require_exact_dict(p3["banu_musa_aletheion_thermal"], _P3_BM_KEYS, "p3.bm")
    oracle.require_ok(bm["aletheion_guard_sha256"] == oracle.ALETHEION_GUARD_SHA, "PILLAR3_GSHA", "guard sha")
    oracle.require_ok(bm["aletheion_thermal_receipt_sha256"] == oracle.ALETHEION_THERM_RECEIPT_SHA, "PILLAR3_RSHA", "receipt sha")
    c_lo = oracle.require_exact_int(bm["cpu_restore_c"], "bm.clo", lo=76, hi=76)
    c_hi = oracle.require_exact_int(bm["cpu_shed_c"], "bm.chi", lo=88, hi=88)
    oracle.require_exact_int(bm["cpu_deadband_c"], "bm.cdb", lo=c_hi - c_lo, hi=c_hi - c_lo)
    g_lo = oracle.require_exact_int(bm["gpu_restore_c"], "bm.glo", lo=70, hi=70)
    g_hi = oracle.require_exact_int(bm["gpu_shed_c"], "bm.ghi", lo=80, hi=80)
    oracle.require_exact_int(bm["gpu_deadband_c"], "bm.gdb", lo=g_hi - g_lo, hi=g_hi - g_lo)
    oracle.require_exact_int(bm["shed_hold_s"], "bm.shold", lo=15, hi=15)
    oracle.require_exact_int(bm["restore_hold_s"], "bm.rhold", lo=30, hi=30)
    oracle.require_exact_int(bm["zero_deadband_chatter_switches"], "bm.zsw", lo=1, hi=100)
    oracle.require_exact_int(bm["hysteretic_deadband_switches"], "bm.hsw", lo=0, hi=0)
    oracle.require_ok(parse_canonical_rational_str(bm["live_cpu_rosen_discriminant_q"], "bm.cpud") < 0, "PILLAR3_CPUD", "cpu disc >= 0")
    oracle.require_ok(parse_canonical_rational_str(bm["live_gpu_rosen_discriminant_q"], "bm.gpud") > 0, "PILLAR3_GPUD", "gpu disc <= 0")
    oracle.require_ok(bm["law5_analog_vs_discrete_obstruction"] == _EXPECTED_BM_OBSTRUCTION, "PILLAR3_BM_OBS", "bm obs mismatch")

    nf = _require_exact_dict(p3["ibn_al_nafis_septal_firewall"], _P3_NF_KEYS, "p3.nf")
    _require_inertia(nf["galen_inertia"], [3, 0, 1], "nf.gi")
    _require_inertia(nf["nafis_inertia"], [3, 0, 1], "nf.ni")
    oracle.require_ok(parse_canonical_rational_str(nf["galen_foster_q"], "nf.gf") == Fraction(3, 1), "PILLAR3_GFOST", "galen foster != 3")
    oracle.require_ok(parse_canonical_rational_str(nf["nafis_foster_q"], "nf.nf") == Fraction(3, 1), "PILLAR3_NFOST", "nafis foster != 3")
    g_gal = parse_canonical_rational_str(nf["galen_g_eff_rv_lv_q"], "nf.ggal")
    g_naf = parse_canonical_rational_str(nf["nafis_g_eff_rv_lv_q"], "nf.gnaf")
    oracle.require_ok(0 < g_naf < g_gal, "PILLAR3_RAYLEIGH", "Rayleigh conductance drop")
    oracle.require_ok(parse_canonical_rational_str(nf["rayleigh_conductance_drop_q"], "nf.drop") == g_gal - g_naf, "PILLAR3_DROP", "drop mismatch")
    g_pulm = parse_canonical_rational_str(nf["galen_pulmonary_frac_q"], "nf.gpulm")
    g_shunt = parse_canonical_rational_str(nf["galen_shunt_bypass_frac_q"], "nf.gshunt")
    oracle.require_ok(0 < g_pulm < 1, "PILLAR3_GPULM", "galen pulmonary frac")
    oracle.require_ok(g_pulm + g_shunt == 1, "PILLAR3_GSHUNT", "galen flux conservation")
    oracle.require_ok(parse_canonical_rational_str(nf["nafis_shunt_bypass_frac_q"], "nf.shunt") == 0, "PILLAR3_SHUNT", "shunt != 0")
    oracle.require_ok(parse_canonical_rational_str(nf["nafis_pulmonary_frac_q"], "nf.pulm") == 1, "PILLAR3_PULM", "pulm != 1")
    oracle.require_ok(nf["law5_valved_asymmetry_obstruction"] == _EXPECTED_NF_OBSTRUCTION, "PILLAR3_NF_OBS", "nf obs mismatch")

    # Pillar 4: K_26 Transhistorical Mesh
    p4 = _require_exact_dict(payload["pillar4_k26_transhistorical_mesh"], _P4_KEYS, "pillar4")
    oracle.require_exact_int(p4["n_nodes"], "p4.n", lo=26, hi=26)
    oracle.require_exact_int(p4["n_modern_nodes"], "p4.nm", lo=16, hi=16)
    oracle.require_exact_int(p4["n_classical_nodes"], "p4.nc", lo=10, hi=10)
    oracle.require_exact_int(p4["n_edges"], "p4.e", lo=325, hi=325)
    ecc = _require_exact_dict(p4["edge_class_counts"], _P4_ECC_KEYS, "p4.ecc")
    ec_n = oracle.require_exact_int(ecc["EXACT_COMMUTE"], "p4.ec", lo=47, hi=47)
    cb_n = oracle.require_exact_int(ecc["CONDITIONAL_BRIDGE"], "p4.cb", lo=247, hi=247)
    eo_n = oracle.require_exact_int(ecc["EXACT_OBSTRUCTION"], "p4.eo", lo=31, hi=31)
    tot_cond = 4 * ec_n + 2 * cb_n + eo_n
    oracle.require_exact_int(p4["total_conductance"], "p4.cond", lo=tot_cond, hi=tot_cond)
    eec = _require_exact_dict(p4["edge_era_counts"], _P4_EEC_KEYS, "p4.eec")
    oracle.require_exact_int(eec["modern_modern"], "p4.mm", lo=120, hi=120)
    oracle.require_exact_int(eec["classical_classical"], "p4.cc", lo=45, hi=45)
    oracle.require_exact_int(eec["cross_millennium"], "p4.cm", lo=160, hi=160)
    _require_inertia(p4["laplacian_inertia"], [25, 0, 1], "p4.inertia")
    oracle.require_ok(parse_canonical_rational_str(p4["foster_sum_q"], "p4.foster") == Fraction(25, 1), "PILLAR4_FOSTER", "Foster != 25")
    oracle.require_ok(oracle.parse_decimal_or_sci_to_q(p4["kirchhoff_index_dec4"], "p4.k") > 0, "PILLAR4_KIRCH", "Kirchhoff <= 0")
    oracle.require_ok(oracle.require_bool(p4["all_325_pairs_strictly_compounded"], "p4.comp") is True, "PILLAR4_COMP", "all 325 compounded")
    min_g = oracle.parse_decimal_or_sci_to_q(p4["min_compounding_gain_dec4"], "p4.ming")
    max_g = oracle.parse_decimal_or_sci_to_q(p4["max_compounding_gain_dec4"], "p4.maxg")
    oracle.require_ok(1 < min_g < max_g, "PILLAR4_GAIN", "compounding gain bounds")
    _require_node_pair(p4["min_compounding_pair"], "p4.minp")
    _require_node_pair(p4["max_compounding_pair"], "p4.maxp")

    xm = _require_exact_dict(p4["cross_millennium_schur_compounding"], _P4_XM_KEYS, "p4.xm")
    _require_inertia(xm["isolated_k16_inertia"], [15, 0, 1], "xm.in16")
    oracle.require_ok(parse_canonical_rational_str(xm["isolated_k16_foster_q"], "xm.f16") == Fraction(15, 1), "PILLAR4_XM_F16", "k16 foster")
    _require_inertia(xm["isolated_k10_inertia"], [9, 0, 1], "xm.in10")
    oracle.require_ok(parse_canonical_rational_str(xm["isolated_k10_foster_q"], "xm.f10") == Fraction(9, 1), "PILLAR4_XM_F10", "k10 foster")
    oracle.require_ok(oracle.require_bool(xm["all_120_modern_pairs_boosted_by_classical"], "xm.m120") is True, "PILLAR4_XM_M", "modern boost")
    oracle.require_ok(oracle.require_bool(xm["all_45_classical_pairs_boosted_by_modern"], "xm.c45") is True, "PILLAR4_XM_C", "classical boost")
    m_min = oracle.parse_decimal_or_sci_to_q(xm["modern_boost_min_pct_dec2"], "xm.mmin")
    m_med = oracle.parse_decimal_or_sci_to_q(xm["modern_boost_median_pct_dec2"], "xm.mmed")
    m_max = oracle.parse_decimal_or_sci_to_q(xm["modern_boost_max_pct_dec2"], "xm.mmax")
    oracle.require_ok(0 < m_min < m_med < m_max, "PILLAR4_XM_MORD", "modern boost ordering")
    c_min = oracle.parse_decimal_or_sci_to_q(xm["classical_boost_min_pct_dec2"], "xm.cmin")
    c_med = oracle.parse_decimal_or_sci_to_q(xm["classical_boost_median_pct_dec2"], "xm.cmed")
    c_max = oracle.parse_decimal_or_sci_to_q(xm["classical_boost_max_pct_dec2"], "xm.cmax")
    oracle.require_ok(0 < c_min < c_med < c_max, "PILLAR4_XM_CORD", "classical boost ordering")

    ho = _require_exact_dict(p4["higher_order_simplices"], _P4_HO_KEYS, "p4.ho")
    oracle.require_exact_int(ho["order2_triangles_total"], "ho.t", lo=2600, hi=2600)
    tc = _require_exact_dict(ho["order2_triangle_counts"], _P4_TRI_KEYS, "ho.tc")
    oracle.require_exact_int(tc["EXACT_TRANSITIVE"], "ho.tc.et", lo=11, hi=11)
    oracle.require_exact_int(tc["CONDITIONAL_CLEAN"], "ho.tc.cc", lo=1929, hi=1929)
    oracle.require_exact_int(tc["FRUSTRATED_ODD_Z2"], "ho.tc.fr", lo=582, hi=582)
    oracle.require_exact_int(tc["MULTI_WALL_EVEN"], "ho.tc.mw", lo=78, hi=78)
    oracle.require_exact_int(ho["order3_tetrahedra_total"], "ho.tet", lo=14950, hi=14950)
    oracle.require_ok(oracle.require_bool(ho["order3_bianchi_coboundary_zero_all"], "ho.bi") is True, "PILLAR4_BIANCHI", "Bianchi != 0")
    oracle.require_exact_int(ho["order3_k4_exact_locks"], "ho.k4", lo=1, hi=1)
    oracle.require_exact_int(ho["order4_5cells_total"], "ho.c5", lo=65780, hi=65780)
    oracle.require_exact_int(ho["order4_k5_exact_locks"], "ho.k5", lo=0, hi=0)
    hist = ho["order4_5cells_obstruction_hist"]
    oracle.require_ok(type(hist) is list and len(hist) == 11, "PILLAR4_HIST", "5-cell hist len != 11")
    for elem in hist:
        oracle.require_exact_int(elem, "ho.hist", lo=0, hi=65780)
    oracle.require_ok(sum(hist) == 65780, "PILLAR4_HIST", "5-cell hist sum != 65780")
    oracle.require_exact_int(ho["order4_5cells_zero_obstruction"], "ho.z0", lo=hist[0], hi=hist[0])

    sc = _require_exact_dict(p4["silo_cut_destruction"], _P4_SC_KEYS, "p4.sc")
    _audit_silo_cut(sc["balanced_13_13"], (169, 2028, 13520, 63206), "b13")
    _audit_silo_cut(sc["era_silo_16_10"], (160, 1920, 12920, 61160), "e16")

    t3 = _require_exact_dict(p4["t3_cross_millennium_blowup"], _P4_T3_KEYS, "p4.t3")
    oracle.require_exact_int(t3["cross_obstructions_ranked"], "t3.cnt", lo=12, hi=12)
    oracle.require_ok(oracle.require_bool(t3["sherman_morrison_matches_direct_inversion_on_top1"], "t3.sm") is True, "PILLAR4_T3_SM", "SM check")
    ranked = t3["ranked_edges"]
    oracle.require_ok(type(ranked) is list and len(ranked) == 12, "PILLAR4_T3_LEN", "12 ranked edges")
    seen_pairs: set[str] = set()
    prev_rank_key: tuple[int, Fraction] | None = None
    for raw_row in ranked:
        row = _require_exact_dict(raw_row, _P4_T3_ROW_KEYS, "t3.row")
        pair_s = oracle.require_exact_str(row["pair"], "t3.pair")
        oracle.require_ok(pair_s in _CROSS_PAIR_LABELS and pair_s not in seen_pairs, "PILLAR4_T3_PAIR", pair_s)
        seen_pairs.add(pair_s)
        oracle.require_ok(row["obstruction"] == _CROSS_PAIR_LABELS[pair_s], "PILLAR4_T3_OBS", pair_s)
        flips = oracle.require_exact_int(row["incident_triangles_flipped"], "t3.flip", lo=24, hi=24)
        f_res = oracle.require_exact_int(row["frustrated_resolved"], "t3.res", lo=0, hi=24)
        c_fru = oracle.require_exact_int(row["clean_frustrated"], "t3.cfru", lo=0, hi=24)
        oracle.require_ok(f_res + c_fru == flips, "PILLAR4_T3_SUM", pair_s)
        net = oracle.require_exact_int(row["net_frustrated_reduction"], "t3.net", lo=f_res - c_fru, hi=f_res - c_fru)
        oracle.require_ok(oracle.parse_decimal_or_sci_to_q(row["r_eff_before_dec6"], "t3.reff") > 0, "PILLAR4_T3_REFF", pair_s)
        dk = parse_canonical_rational_str(row["delta_kirchhoff_q"], "t3.dk")
        oracle.require_ok(dk > 0, "PILLAR4_T3_DK", pair_s)
        oracle.require_ok(row["delta_kirchhoff_dec6"] == oracle.dec_from_q(dk, 6), "PILLAR4_T3_DK_DEC", pair_s)
        cur_rank_key = (net, dk)
        if prev_rank_key is not None:
            oracle.require_ok(prev_rank_key > cur_rank_key, "PILLAR4_T3_ORDER", pair_s)
        prev_rank_key = cur_rank_key

    oracle.require_ok(
        hmac.compare_digest(
            oracle.sha256_hex(oracle.canonical_json_bytes(payload)),
            EXPECTED_PAYLOAD_SHA256,
        ),
        "PAYLOAD_CANONICAL_PIN_MISMATCH",
        "payload digest does not match frozen canonical Track S91 payload",
    )

    return {
        "secondary_audit_passed": True,
        "lean_theorem_count": thm_n,
        "k26_edges": 325,
        "k26_5cells": 65780,
        "t3_top1_pair": ranked[0]["pair"],
    }


def _load_track_artifacts(track_dir: Path) -> tuple[dict[str, Any], str, str, str, str, dict[str, Any]]:
    anchor_raw = read_regular_bytes_capped(track_dir / "s91_tusi_circularep_live_anchor.json", "live_anchor")
    anchor_obj = parse_strict_json_bytes(anchor_raw, "live_anchor", require_canonical=True)
    tc_raw = read_regular_bytes_capped(track_dir / "lean-toolchain", "lean-toolchain", max_bytes=256)
    try:
        tc_text = tc_raw.decode("utf-8", "strict").strip()
    except UnicodeDecodeError as exc:
        raise oracle.S91Error("INVALID_UTF8", "lean-toolchain invalid UTF-8") from exc
    oracle.require_ok(tc_text == oracle.EXPECTED_LEAN_TOOLCHAIN, "TOOLCHAIN_MISMATCH", "unexpected lean-toolchain")
    lake_raw = read_regular_bytes_capped(track_dir / "lakefile.toml", "lakefile.toml", max_bytes=4096)
    lean_res = verify_lean4_file_live(track_dir / "TranshistoricalK26AndTusiCure.lean")
    return (
        anchor_obj,
        oracle.sha256_hex(anchor_raw),
        lean_res["lean_source_sha256"],
        oracle.sha256_hex(tc_raw),
        oracle.sha256_hex(lake_raw),
        lean_res,
    )


def verify_certificate_dict(
    cert: Any,
    *,
    full_replay: bool = True,
    track_dir: Path | None = None,
) -> dict[str, Any]:
    oracle.require_bool(full_replay, "full_replay")
    oracle.require_ok(type(cert) is dict, "INVALID_CERT_TYPE", "certificate must be exact dict")
    oracle.validate_strict_json_tree(cert, "certificate")
    _require_exact_dict(cert, _CERT_KEYS, "certificate")
    oracle.require_ok(cert["schema_version"] == oracle.SCHEMA_VERSION, "SCHEMA_MISMATCH", "cert schema_version")
    oracle.require_ok(cert["track_id"] == oracle.TRACK_ID, "SCHEMA_MISMATCH", "cert track_id")

    p_sha = oracle.require_hex64(cert["payload_sha256"], "payload_sha256")
    c_sha = oracle.require_hex64(cert["certificate_sha256"], "certificate_sha256")
    payload = cert["payload"]
    sec_res = secondary_audit_payload(payload)

    recomputed_p = oracle.sha256_hex(oracle.canonical_json_bytes(payload))
    oracle.require_ok(hmac.compare_digest(p_sha, recomputed_p), "PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")
    env = {
        "schema_version": cert["schema_version"],
        "track_id": cert["track_id"],
        "payload_sha256": p_sha,
        "payload": payload,
    }
    recomputed_c = oracle.sha256_hex(oracle.canonical_json_bytes(env))
    oracle.require_ok(hmac.compare_digest(c_sha, recomputed_c), "CERT_SHA_MISMATCH", "certificate_sha256 mismatch")

    replayed = False
    lean_live: dict[str, Any] | None = None
    if full_replay:
        root = Path(_THIS_DIR) if track_dir is None else _require_concrete_path(track_dir, "track_dir")
        anchor_obj, a_sha, l_sha, tc_sha, lk_sha, lean_live = _load_track_artifacts(root)
        expected = oracle.build_certificate(
            anchor=anchor_obj,
            anchor_sha256=a_sha,
            lean_source_sha256=l_sha,
            toolchain_sha256=tc_sha,
            lakefile_sha256=lk_sha,
        )
        oracle.require_ok(
            hmac.compare_digest(oracle.canonical_json_bytes(cert), oracle.canonical_json_bytes(expected)),
            "FULL_REPLAY_MISMATCH",
            "certificate does not match pure-Z/Q + Lean 4.36.0 replay",
        )
        replayed = True

    out: dict[str, Any] = {
        "valid": True,
        "full_replay": replayed,
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "secondary_audit": sec_res,
    }
    if lean_live is not None:
        out["lean_live"] = lean_live
    return out


def write_certificate_file(path: Path, *, track_dir: Path | None = None) -> dict[str, Any]:
    root = Path(_THIS_DIR) if track_dir is None else _require_concrete_path(track_dir, "track_dir")
    anchor_obj, a_sha, l_sha, tc_sha, lk_sha, _ = _load_track_artifacts(root)
    cert = oracle.build_certificate(
        anchor=anchor_obj,
        anchor_sha256=a_sha,
        lean_source_sha256=l_sha,
        toolchain_sha256=tc_sha,
        lakefile_sha256=lk_sha,
    )
    raw = oracle.canonical_json_bytes(cert)
    write_regular_bytes_safe(path, raw, "certificate")
    return {
        "written": True,
        "bytes": len(raw),
        "file_sha256": oracle.sha256_hex(raw),
        "certificate_sha256": cert["certificate_sha256"],
    }


def check_certificate_file(path: Path, *, full_replay: bool = True, track_dir: Path | None = None) -> dict[str, Any]:
    raw = read_regular_bytes_capped(path, "certificate")
    cert = parse_strict_json_bytes(raw, "certificate", require_canonical=True)
    res = verify_certificate_dict(cert, full_replay=full_replay, track_dir=track_dir)
    res["file_sha256"] = oracle.sha256_hex(raw)
    return res


def _parse_cli_args(argv: Any) -> dict[str, Any]:
    oracle.require_ok(type(argv) is list, "INVALID_ARGV", "argv must be exact list")
    mode: str | None = None
    target_path: str | None = None
    want_json = False
    i = 0
    n = len(argv)
    while i < n:
        arg = oracle.require_exact_str(argv[i], "argv")
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
            val = oracle.require_exact_str(argv[i + 1], f"{arg} path")
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
        else:
            raise oracle.S91Error("UNKNOWN_FLAG", f"unsupported flag: {arg!r}")
    return {"mode": mode or "default", "target": target_path, "json": want_json}


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv: Any = list(sys.argv[1:]) if argv is None else argv
    try:
        opts = _parse_cli_args(raw_argv)
        mode = opts["mode"]
        if mode == "standalone":
            root = Path(_THIS_DIR)
            anchor_obj, a_sha, l_sha, tc_sha, lk_sha, _ = _load_track_artifacts(root)
            cert = oracle.build_certificate(
                anchor=anchor_obj,
                anchor_sha256=a_sha,
                lean_source_sha256=l_sha,
                toolchain_sha256=tc_sha,
                lakefile_sha256=lk_sha,
            )
            sys.stdout.write(oracle.canonical_json_bytes(cert).decode("ascii"))
            return 0
        if mode == "write":
            res = write_certificate_file(Path(opts["target"]))
            if opts["json"]:
                sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii"))
            else:
                sys.stdout.write(f"WROTE {res['file_sha256']}\n")
            return 0
        if mode == "check":
            res = check_certificate_file(Path(opts["target"]), full_replay=True)
            if opts["json"]:
                sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii"))
            else:
                sys.stdout.write(f"OK {res['certificate_sha256']}\n")
            return 0
        res = check_certificate_file(Path(_THIS_DIR) / "s91_transhistorical_k26_certificate.json", full_replay=True)
        if opts["json"]:
            sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii"))
        else:
            sys.stdout.write(f"OK {res['certificate_sha256']}\n")
        return 0
    except oracle.S91Error as exc:
        err_obj = {"error": True, "code": exc.code, "detail": exc.detail}
        sys.stderr.write(json.dumps(err_obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
