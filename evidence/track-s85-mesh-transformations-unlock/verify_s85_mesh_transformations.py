#!/usr/bin/env python3
"""Zone-B Hardened Standalone Verifier, R10+ Live Lean 4.36.0 & Secondary Auditor for Track S85.

100% pure Python 3 stdlib, zero IEEE-754 floats, zero bare asserts, zero .isdigit(),
zero mathematical RNG (secrets.token_hex used strictly for atomic temp filenames).
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
import threading
from typing import Any, Sequence

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import s85_mesh_transformations_oracle as oracle  # noqa: E402

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

_CERT_KEYS = frozenset({"schema_version", "track_id", "payload_sha256", "certificate_sha256", "payload"})
_PAYLOAD_KEYS = frozenset({
    "schema_version",
    "track_id",
    "oracle_class",
    "novelty_classification",
    "pinned_artifacts",
    "t1_line_graph_and_hodge",
    "t2_signed_laplacian_and_double_cover",
    "t3_obstruction_blowup_surgery",
    "t4_directed_ceer_loop_schur",
    "t5_borromean_hypergraph_promotion",
    "t6_kron_renormalization_and_curvature",
})
_PINNED_KEYS = frozenset({
    "lean_source",
    "lean_source_sha256",
    "lakefile_sha256",
    "lean_toolchain",
    "lean_toolchain_sha256",
    "lean_theorem_count",
    "lean_theorem_names",
    "upstream_cert_shas",
})
_T1_KEYS = frozenset({
    "line_graph_vertices",
    "line_graph_incident_edges",
    "line_graph_disjoint_pairs",
    "disjoint_same_operator_tag_bridges",
    "disjoint_same_class_and_tag_bridges",
    "disjoint_bridges_by_tag",
    "sample_disjoint_functor_bridges",
    "b1_b2_exact_zero",
    "l1_equals_8_identity",
    "l1_down_inertia",
    "l1_up_inertia",
    "betti_1_harmonic_dim",
    "wall_cochain_norm_sq_q",
    "wall_grad_energy_q",
    "wall_curl_energy_q",
    "wall_grad_pct_dec2",
    "wall_curl_pct_dec2",
    "grad_curl_inner_product_q",
})
_T1_TAG_KEYS = frozenset({
    "BOUNDARY_WALL",
    "GAUGE_QUOTIENT",
    "HOLONOMY_CURVATURE",
    "PHASE_CROSSOVER",
    "SCHUR_PUSHFORWARD",
})
_T2_KEYS = frozenset({
    "n_obstruction_walls",
    "l0_inertia",
    "l0_det_q",
    "l_sigma_inertia",
    "l_sigma_det_q",
    "gauges_exhaustively_checked",
    "min_weighted_frustration_cut_q",
    "min_weighted_quadratic_energy_q",
    "min_unweighted_frustration_cut",
    "best_unweighted_switch_mask",
    "double_cover_nodes",
    "double_cover_positive_edges",
    "double_cover_negative_edges",
    "double_cover_frustrated_triangles",
    "double_cover_total_conductance_q",
    "double_cover_inertia",
    "antipodal_resistance_equals_2_lsigma_inv_diag",
    "antipodal_sheet_resistances_q",
    "min_sheet_separation_r_dec4",
    "max_sheet_separation_r_dec4",
    "law5_irreducible_double_sheet_connected",
})
_T3_KEYS = frozenset({
    "base_frustrated_triangles",
    "base_multi_wall_triangles",
    "base_exact_transitive_closures",
    "base_sum_geff_dec4",
    "base_kirchhoff_dec4",
    "base_lambda2_lo_dec5",
    "base_lambda2_hi_dec5",
    "single_surgery_rows",
    "all_6_walls_holonomy_ranking",
    "isolated_wall_v6_v7_flips_all_6",
    "braess_unmasking_wall_v1_v4_delta",
    "three_step_cascade",
    "superadditive_transitive_synergy_emergent_v0_v1_v5",
})
_T3_ROW_KEYS = frozenset({
    "pair",
    "original_class",
    "original_w",
    "upgraded_w",
    "mediator",
    "frustrated_after",
    "delta_frustrated",
    "multi_wall_after",
    "exact_transitive_after",
    "delta_exact_transitive",
    "delta_sum_geff_dec4",
    "delta_kirchhoff_dec5",
    "lambda2_lo_dec5",
    "lambda2_strictly_lifted",
    "kirchhoff_strictly_reduced",
    "sum_geff_strictly_lifted",
})
_T3_CASCADE_KEYS = frozenset({
    "step",
    "added_pair",
    "frustrated_triangles",
    "multi_wall_triangles",
    "exact_transitive_closures",
    "sum_geff_dec4",
    "delta_sum_geff_vs_base_dec4",
    "kirchhoff_dec4",
})
_T4_KEYS = frozenset({
    "asymmetric_gains_a_b_q",
    "monodromy_rho_q",
    "g_loop_forward_q",
    "g_loop_reversed_q",
    "directional_curvature_asymmetry_q",
    "directional_curvature_asymmetry_dec4",
    "readout_schur_forward_q",
    "readout_schur_reversed_q",
    "adjoint_gain_direction_invariant_q",
    "epistemic_curl_frobenius_sq_q",
    "nonnormal_t1_t2_t3_t10_q",
    "symmetric_t1_t2_t3_q",
    "transient_boost_over_symmetric_t1_t2_t3_q",
    "ungated_monodromy_divergent_q",
    "law3_damping_gamma_q",
    "gated_monodromy_contractive_q",
    "gated_h_pc_inertia",
    "gated_h_pc_det_q",
})
_T5_KEYS = frozenset({"h3_borromean_s23", "h4_sovereign_8gib_stack"})
_T5_H3_KEYS = frozenset({
    "s23a_pairwise_linking_all_zero",
    "s23a_abelian_mutual_helicity_q",
    "s23b_su2_k2_norm_sq",
    "milnor_triple_abs",
    "pairwise_laplacian_inertia",
    "hypergraph_h3_inertia",
    "hypergraph_h3_lambda2_q",
    "hypergraph_h3_pair_geff_q",
})
_T5_H4_KEYS = frozenset({
    "vram_budget_mib",
    "materialized_45bpw_oom_mib",
    "stack_30bpw_cce_base_mib",
    "lora_r64_mib",
    "csr_sidecar_mib",
    "full_4way_stack_mib",
    "headroom_mib",
    "csr_overhead_ratio_q",
    "subsets_checked",
    "proper_subsets_failed",
    "only_full_4body_feasible",
    "pairwise_laplacian_inertia",
    "hypergraph_h4_inertia",
    "hypergraph_h4_lambda2_q",
    "hypergraph_h4_pair_geff_q",
})
_T6_KEYS = frozenset({
    "kron_core4_inertia",
    "kron_comp4_inertia",
    "kron_core4_r_eff_exact_all_6",
    "kron_comp4_r_eff_exact_all_6",
    "kron_core4_foster_q",
    "kron_comp4_foster_q",
    "k8_resistance_gram_inertia",
    "k4_resistance_gram_inertia",
    "k4_resistance_gram_det_q",
    "k4_resistance_gram_det_dec8",
    "s81_r3_tetrahedron_gram_inertia",
    "s81_r3_tetrahedron_gram_det_q",
    "s75_cat0_rank_gram_inertia",
    "s75_cat0_rank_gram_det_q",
    "s75_cat0_neg_witness_quad_q",
    "curvature_trichotomy_strictly_disjoint",
})

# R12 Lean 4 static trust-escape rules (pure-Init algebraic file: forbids all quotes/guillemets, dbg/panic, meta/elab)
_LEAN4_BANNED_RE = re.compile(
    r"\b(?:sorry|admit|axiom|unsafe|native_decide|bv_decide|sorryAx|ofReduceBool|ofReduceNat|"
    r"trustCompiler|mkSorry|run_cmd|run_meta|initialize|builtin_initialize|"
    r"macro|macro_rules|elab|elab_rules|syntax|declare_syntax_cat|interpolatedStr|"
    r"dbg_trace|dbg_sleep|dbg_stack_trace|dbgTrace|dbgTraceVal|dbgTraceValId|dbgTraceIfShared|dbgSleep|dbgStackTrace|"
    r"panicCore|panicWithPosWithDecl|panicWithPos|throwError|"
    r"notation|prefix|infix|infixl|infixr|postfix|csimp|opaque|partial|noncomputable|set_option)\b"
    r"|\b(?:panic|unreachable|assert|debug_assert)!"
    r"|\b(?:debug|warn)\s*\.\s*(?:skipKernelTC|byAsSorry|proofAsSorry|terminalTacticsAsSorry|sorry)\b"
    r"|(?:@|(?<!\.)\battribute\s*)\[[^\]]*\b(?:extern|implemented_by|export|init|builtin_init|"
    r"term_elab|command_elab|tactic|macro|macro_rules|"
    r"builtin_term_elab|builtin_command_elab|builtin_tactic|builtin_macro|builtin_macro_rules)\b"
    r"|(?<!\w)\+\s*native\b|\bnative\s*:=(?!\s*(?:Bool\.)?false[ \t]*[),}])"
    r"|\bDecide(?:Config|\.Config)\b|\bconfig\s*:=|\bwith\s+native\b|\{[^{}]*\bnative\b(?!\s*:=\s*(?:Bool\.)?false[ \t]*[,}])"
    r"|#(?:eval!?(?![\w'!?])|reduce(?![\w'!?])|check(?![\w'!?])|synth(?![\w'!?])|exit(?![\w'!?])|guard(?:_msgs)?(?![\w'!?])|"
    r"print(?![\w'!?])(?!\s+axioms[ \t]+MeshTransformationsUnlock\.))"
    r"|(?:^|\n)[ \t]*(?:(?:public|private|meta)\s+)*import\s+"
    r"|[\"'«»]",
    flags=re.DOTALL,
)
_LEAN4_AXIOM_NONE_RE = re.compile(r"^'([^']+)' does not depend on any axioms$")
_LEAN4_AXIOM_DEP_RE = re.compile(r"^'([^']+)' depends on axioms: \[([^\]]*)\]$")
_LEAN_ENV_ALLOWLIST = frozenset({"PATH", "HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "LC_ALL", "TERM"})

# Canonical S85 K_8 pinned witnesses for field-complete 337/337 leaf SEC/FR0 verification
_T1_SAMPLE_BRIDGES: tuple[str, ...] = (
    "v0-v1 <-> v2-v5 [GAUGE_QUOTIENT]",
    "v0-v1 <-> v3-v5 [GAUGE_QUOTIENT]",
    "v0-v1 <-> v4-v5 [GAUGE_QUOTIENT]",
    "v0-v2 <-> v5-v7 [PHASE_CROSSOVER]",
)
_T2_ANTIPODAL_Q: tuple[Fraction, ...] = (
    Fraction(1329983, 6670656),
    Fraction(3399977, 17047232),
    Fraction(11249699, 51141696),
    Fraction(33971929, 153425088),
    Fraction(1454351, 6670656),
    Fraction(30741721, 153425088),
    Fraction(3222401, 17047232),
    Fraction(9471731, 51141696),
)
_T3_BASE_DEC_Q: tuple[Fraction, Fraction, Fraction, Fraction] = (
    Fraction(2697213, 10000),
    Fraction(30096, 10000),
    Fraction(1122461, 100000),
    Fraction(1122510, 100000),
)
_T3_ROW_EXACT: dict[str, tuple[str, int, Fraction, Fraction, Fraction]] = {
    "v6-v7": (
        "Deterministic Fixed-Order CCE Mediator (cures tl.atomic_cas ULP drift)",
        7,
        Fraction(106346, 10000),
        Fraction(-8885, 100000),
        Fraction(1122998, 100000),
    ),
    "v1-v5": (
        "Quantized-Wishart Mediator (bridges discrete rank to Marchenko-Pastur)",
        6,
        Fraction(117597, 10000),
        Fraction(-11134, 100000),
        Fraction(1126465, 100000),
    ),
    "v0-v4": (
        "Ambient-Dimension Lift Mediator (v0-v4 3D SE(3) star wall)",
        4,
        Fraction(128682, 10000),
        Fraction(-18189, 100000),
        Fraction(1377100, 100000),
    ),
    "v2-v4": (
        "Ambient-Dimension Lift Mediator (v2-v4 3D SE(3) star wall)",
        4,
        Fraction(136664, 10000),
        Fraction(-19694, 100000),
        Fraction(1386377, 100000),
    ),
    "v3-v4": (
        "Ambient-Dimension Lift Mediator (v3-v4 3D SE(3) star wall)",
        4,
        Fraction(136454, 10000),
        Fraction(-19617, 100000),
        Fraction(1376563, 100000),
    ),
    "v1-v4": (
        "Ambient-Dimension Lift Mediator (v1-v4 3D SE(3) + CAT(0) hub wall)",
        3,
        Fraction(135211, 10000),
        Fraction(-19343, 100000),
        Fraction(1388916, 100000),
    ),
    "v0-v1": (
        "Orthogonalized Cayley/Householder Lift (promotes v0-v1 real-shear bridge 2->4)",
        7,
        Fraction(71350, 10000),
        Fraction(-6291, 100000),
        Fraction(1122705, 100000),
    ),
}
_T3_CASC_EXACT: tuple[tuple[str, int, int, int, Fraction, Fraction, Fraction], ...] = (
    ("v6-v7", 16, 7, 5, Fraction(2803559, 10000), Fraction(106346, 10000), Fraction(29207, 10000)),
    ("v1-v5", 12, 6, 6, Fraction(2925801, 10000), Fraction(228588, 10000), Fraction(28096, 10000)),
    ("v0-v1", 12, 6, 9, Fraction(2997872, 10000), Fraction(300659, 10000), Fraction(27566, 10000)),
)


# ---------------------------------------------------------------------------
# Zone-B Path, Darwin Alias Normalization, CWD/$PWD, Atomic dir_fd & Write
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
        raise oracle.S85Error("CWD_UNAVAILABLE", f"{label}: CWD unavailable") from exc
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
        raise oracle.S85Error("CWD_UNAVAILABLE", f"{label}: cannot open root for PWD") from exc
    try:
        for part in pwd_path.parts[1:]:
            try:
                next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise oracle.S85Error("SYMLINK_ANCESTOR_FORBIDDEN", f"{label}: symlink PWD ancestor") from exc
                raise oracle.S85Error("CWD_UNAVAILABLE", f"{label}: PWD ancestor unavailable") from exc
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
        raise oracle.S85Error(err_code, f"{label}: cannot open root") from exc
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
                        raise oracle.S85Error("FILE_WRITE_ERROR", f"{label}: mkdir failed") from mk_exc
                    try:
                        next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
                    except OSError as re_exc:
                        raise oracle.S85Error("FILE_WRITE_ERROR", f"{label}: open created dir failed") from re_exc
                elif exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise oracle.S85Error("SYMLINK_FORBIDDEN", f"{label}: symlink ancestor forbidden") from exc
                else:
                    raise oracle.S85Error(err_code, f"{label}: ancestor unavailable") from exc
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
                raise oracle.S85Error("SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden") from exc
            raise oracle.S85Error("FILE_READ_ERROR", f"{label}: open failed") from exc
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
    except oracle.S85Error:
        raise
    except OSError as exc:
        raise oracle.S85Error("FILE_READ_ERROR", f"{label}: read failed") from exc
    finally:
        os.close(fd)
    oracle.require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"{label}: stream exceeds cap")
    return b"".join(chunks)


def _check_existing_regular_target(dfd: int, leaf: str, label: str) -> None:
    try:
        st_ex = os.lstat(leaf, dir_fd=dfd)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise oracle.S85Error("FILE_WRITE_ERROR", f"{label}: lstat failed") from exc
    oracle.require_ok(not stat.S_ISLNK(st_ex.st_mode), "SYMLINK_FORBIDDEN", f"{label}: symlink leaf")
    oracle.require_ok(stat.S_ISREG(st_ex.st_mode), "NOT_A_REGULAR_FILE", f"{label}: non-regular target")
    oracle.require_ok(st_ex.st_nlink <= 1, "HARDLINK_FORBIDDEN", f"{label}: hardlinked target")


def write_regular_bytes_safe(path: Path, payload: bytes, label: str = "output") -> None:
    global _TEMP_SEQ
    oracle.require_ok(type(payload) is bytes, "INVALID_PAYLOAD_BYTES", f"{label}: exact bytes required")
    target = _require_concrete_path(path, label)
    dfd, leaf = _open_dir_chain(target, label, create_parents=True)
    tmp_name: str | None = None
    try:
        _check_existing_regular_target(dfd, leaf, label)
        pid = os.getpid()
        for _ in range(64):
            with _TEMP_NAME_LOCK:
                _TEMP_SEQ += 1
                seq_num = _TEMP_SEQ
                cand = f".s85.{pid}.{seq_num}.{secrets.token_hex(8)}.tmp"
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
                raise oracle.S85Error("FILE_WRITE_ERROR", f"{label}: temp open failed") from exc
        else:
            raise oracle.S85Error("FILE_WRITE_ERROR", f"{label}: temp slots exhausted")

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
        except oracle.S85Error:
            raise
        except OSError as exc:
            raise oracle.S85Error("FILE_WRITE_ERROR", f"{label}: write/fsync failed") from exc
        finally:
            os.close(fd)

        # Second lstat TOCTOU check immediately before atomic replace
        _check_existing_regular_target(dfd, leaf, label)
        try:
            os.replace(tmp_name, leaf, src_dir_fd=dfd, dst_dir_fd=dfd)
            tmp_name = None
            os.fsync(dfd)
        except OSError as exc:
            raise oracle.S85Error("FILE_WRITE_ERROR", f"{label}: atomic replace failed") from exc
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
        os.close(dfd)


# ---------------------------------------------------------------------------
# Strict Zero-Float Canonical JSON & Rational Parsers
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
    raise oracle.S85Error("FLOAT_FORBIDDEN", f"IEEE-754 float forbidden: {token!r}")


def _reject_const(token: str) -> Any:
    raise oracle.S85Error("NONFINITE_JSON_CONSTANT", f"JSON constant forbidden: {token!r}")


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
        raise oracle.S85Error("INVALID_UTF8", f"{label}: invalid UTF-8") from exc
    try:
        obj = json.loads(
            text,
            parse_float=_reject_float,
            parse_int=_parse_bounded_int,
            parse_constant=_reject_const,
            object_pairs_hook=_no_dup_pairs,
        )
    except oracle.S85Error:
        raise
    except (ValueError, RecursionError) as exc:
        raise oracle.S85Error("INVALID_JSON", f"{label}: malformed JSON") from exc
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
    if "/" in s:
        parts = s.split("/")
        oracle.require_ok(len(parts) == 2, "INVALID_RATIONAL", f"{label}: multiple slashes")
        num = _parse_bounded_int(parts[0])
        oracle.require_ok(not parts[1].startswith("-"), "INVALID_RATIONAL", f"{label}: negative den")
        den = _parse_bounded_int(parts[1])
        oracle.require_ok(den > 1, "NONCANONICAL_RATIONAL", f"{label}: den must be > 1")
        q = Fraction(num, den)
        oracle.require_ok(q.denominator == den, "NONCANONICAL_RATIONAL", f"{label}: not reduced")
        return q
    return Fraction(_parse_bounded_int(s), 1)


def parse_decimal_str_to_q(val: Any, places: int, label: str) -> Fraction:
    oracle.require_exact_int(places, f"{label}.places", lo=1, hi=18)
    s = oracle.require_exact_str(val, label)
    neg = s.startswith("-")
    body = s[1:] if neg else s
    parts = body.split(".")
    oracle.require_ok(len(parts) == 2, "INVALID_DECIMAL", f"{label}: expected fixed decimal")
    int_s, frac_s = parts[0], parts[1]
    oracle.require_ok(oracle.is_ascii_digits(int_s), "INVALID_DECIMAL", f"{label}: bad integer part")
    oracle.require_ok(len(int_s) <= oracle.MAX_INT_DIGITS, "INT_TOO_LARGE", f"{label}: integer part too large")
    oracle.require_ok(oracle.is_ascii_digits(frac_s) and len(frac_s) == places, "INVALID_DECIMAL", f"{label}: bad scale")
    oracle.require_ok(not (len(int_s) > 1 and int_s[0] == "0"), "INVALID_DECIMAL", f"{label}: leading zero")
    mag = int(int_s) * (10 ** places) + int(frac_s)
    return Fraction(-mag if neg else mag, 10 ** places)


def _require_exact_dict(obj: Any, keys: frozenset[str], label: str) -> dict[str, Any]:
    oracle.require_ok(type(obj) is dict, "INVALID_SCHEMA_DICT", f"{label}: exact dict required")
    oracle.require_ok(frozenset(obj.keys()) == keys, "INVALID_SCHEMA_KEYS", f"{label}: keyset mismatch")
    return obj


# ---------------------------------------------------------------------------
# R10+ Static Lean 4 Gate & Zero-TOCTOU Live Lean 4.36.0 Runner
# ---------------------------------------------------------------------------

def _strip_lean4_comments(source: str) -> str:
    """Strip nested block comments and line comments fail-closed without loop-bound BoolOp hazards."""
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
            nl = source.find("\n", i + 2)
            end = n if nl == -1 else nl
            out.append(" " * (end - i))
            i = end
        else:
            out.append(ch)
            i += 1
    oracle.require_ok(depth == 0, "LEAN4_UNTERMINATED_LEX", "unterminated Lean block comment")
    return "".join(out)


def static_gate_lean4_source(source: str) -> None:
    s = oracle.require_exact_str(source, "lean_source")
    oracle.require_ok("\r" not in s and "\x00" not in s, "LEAN4_BAD_CHARS", "CR/NUL in Lean source")
    cleaned = _strip_lean4_comments(s)
    m = _LEAN4_BANNED_RE.search(cleaned)
    oracle.require_ok(m is None, "LEAN4_TRUST_ESCAPE", f"banned Lean construct: {m.group(0)!r}" if m else "")
    for thm in oracle.LEAN_THEOREM_NAMES:
        short = thm.split(".")[-1]
        oracle.require_ok(
            re.search(rf"(?m)^[ \t]*theorem[ \t]+{re.escape(short)}\b", cleaned) is not None,
            "LEAN4_MISSING_THEOREM",
            f"missing {short}",
        )
        oracle.require_ok(
            re.search(rf"(?m)^[ \t]*#print[ \t]+axioms[ \t]+{re.escape(thm)}[ \t]*$", cleaned) is not None,
            "LEAN4_MISSING_PRINT_AXIOMS",
            f"missing #print axioms {thm}",
        )


def _clean_lean_env() -> dict[str, str]:
    """Allowlisted child env for live Lean subprocesses (scrubs LEAN_PATH/LEAN_OPTS/ELAN_*/LAKE_*/LD_*)."""
    return {k: v for k, v in os.environ.items() if k in _LEAN_ENV_ALLOWLIST}


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
    raise oracle.S85Error("LEAN_BINARY_UNAVAILABLE", "lean executable not found")


def _parse_lean_axiom_stdout(stdout: str) -> dict[str, list[str]]:
    joined_lines: list[str] = []
    pending = ""
    for raw_line in stdout.splitlines():
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
    return seen


def verify_lean4_file_live(lean_path: Path, *, require_pinned_sha: bool = True) -> dict[str, Any]:
    oracle.require_bool(require_pinned_sha, "require_pinned_sha")
    raw = read_regular_bytes_capped(lean_path, "lean_source", max_bytes=1024 * 1024)
    file_sha = oracle.sha256_hex(raw)
    if require_pinned_sha:
        oracle.require_ok(
            hmac.compare_digest(file_sha, oracle.EXPECTED_LEAN_SOURCE_SHA256),
            "LEAN_SHA_MISMATCH",
            "Lean artifact SHA-256 does not match pinned MeshTransformationsUnlock.lean",
        )
    try:
        src = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise oracle.S85Error("INVALID_UTF8", "Lean source not UTF-8") from exc
    static_gate_lean4_source(src)
    lean_bin = resolve_lean_binary()
    lean_env = _clean_lean_env()
    try:
        v_proc = subprocess.run([lean_bin, "--version"], env=lean_env, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise oracle.S85Error("LEAN_EXEC_ERROR", "lean --version failed") from exc
    oracle.require_ok(v_proc.returncode == 0 and "4.36.0" in v_proc.stdout, "LEAN_VERSION_MISMATCH", "Lean 4.36.0 required")
    try:
        # Execute via --stdin on the exact verified bytes to eliminate read-to-compile TOCTOU
        proc = subprocess.run([lean_bin, "--stdin"], input=src, env=lean_env, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise oracle.S85Error("LEAN_EXEC_ERROR", "lean elaboration failed") from exc
    oracle.require_ok(proc.returncode == 0, "LEAN_COMPILE_FAIL", f"lean rc={proc.returncode}")
    oracle.require_ok(proc.stderr.strip() == "", "LEAN_STDERR_NONEMPTY", "lean stderr must be empty")
    oracle.require_ok("warning:" not in proc.stdout.lower(), "LEAN_WARNING_FORBIDDEN", "lean warning forbidden")
    seen = _parse_lean_axiom_stdout(proc.stdout)
    return {
        "lean_version": v_proc.stdout.strip().splitlines()[0],
        "theorems_verified": len(seen),
        "lean_source_sha256": file_sha,
        "axioms_by_theorem": seen,
    }


# ---------------------------------------------------------------------------
# Fail-Closed Secondary Audit (SEC) & Full Replay Verifier (FR0 / FR1)
# ---------------------------------------------------------------------------

def _require_inertia(val: Any, expected: list[int], label: str) -> None:
    oracle.require_ok(type(val) is list, "INVALID_INERTIA", label)
    oracle.require_ok(len(val) == 3, "INVALID_INERTIA", label)
    for elem in val:
        oracle.require_exact_int(elem, label, lo=0, hi=28)
    oracle.require_ok(val == expected, "INERTIA_MISMATCH", f"{label}: expected {expected}")


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Fail-closed semantic & algebraic auditor across all 6 transformations (SEC surface)."""
    oracle.require_ok(type(payload) is dict, "INVALID_PAYLOAD_TYPE", "payload must be exact dict")
    oracle.validate_strict_json_tree(payload, "payload")
    _require_exact_dict(payload, _PAYLOAD_KEYS, "payload")
    oracle.require_ok(payload["schema_version"] == oracle.SCHEMA_VERSION, "SCHEMA_MISMATCH", "schema_version")
    oracle.require_ok(payload["track_id"] == oracle.TRACK_ID, "SCHEMA_MISMATCH", "track_id")
    oracle.require_ok(payload["oracle_class"] == "exact", "SCHEMA_MISMATCH", "oracle_class")
    oracle.require_ok(payload["novelty_classification"] == "N1", "SCHEMA_MISMATCH", "novelty")

    pa = _require_exact_dict(payload["pinned_artifacts"], _PINNED_KEYS, "pinned_artifacts")
    oracle.require_ok(pa["lean_source"] == "MeshTransformationsUnlock.lean", "SCHEMA_MISMATCH", "lean_source")
    oracle.require_ok(
        hmac.compare_digest(oracle.require_hex64(pa["lean_source_sha256"], "lean_source_sha256"), oracle.EXPECTED_LEAN_SOURCE_SHA256),
        "LEAN_PIN_MISMATCH",
        "lean_source_sha256 mismatch",
    )
    oracle.require_ok(
        hmac.compare_digest(oracle.require_hex64(pa["lakefile_sha256"], "lakefile_sha256"), oracle.EXPECTED_LAKEFILE_SHA256),
        "LEAN_PIN_MISMATCH",
        "lakefile_sha256 mismatch",
    )
    oracle.require_ok(pa["lean_toolchain"] == oracle.EXPECTED_LEAN_TOOLCHAIN, "SCHEMA_MISMATCH", "lean_toolchain")
    oracle.require_ok(
        hmac.compare_digest(oracle.require_hex64(pa["lean_toolchain_sha256"], "lean_toolchain_sha256"), oracle.EXPECTED_TOOLCHAIN_SHA256),
        "LEAN_PIN_MISMATCH",
        "lean_toolchain_sha256 mismatch",
    )
    thm_n = oracle.require_exact_int(pa["lean_theorem_count"], "lean_theorem_count", lo=18, hi=18)
    thms = pa["lean_theorem_names"]
    oracle.require_ok(type(thms) is list, "THEOREM_LIST_MISMATCH", "lean_theorem_names type")
    oracle.require_ok(tuple(thms) == oracle.LEAN_THEOREM_NAMES, "THEOREM_LIST_MISMATCH", "lean_theorem_names")
    ups = _require_exact_dict(pa["upstream_cert_shas"], frozenset(oracle.UPSTREAM_CERT_SHAS.keys()), "upstream_cert_shas")
    for k, exp_sha in oracle.UPSTREAM_CERT_SHAS.items():
        oracle.require_ok(oracle.require_hex64(ups[k], f"ups.{k}") == exp_sha, "UPSTREAM_SHA_MISMATCH", k)

    # T1: Line-graph & Hodge invariants
    t1 = _require_exact_dict(payload["t1_line_graph_and_hodge"], _T1_KEYS, "t1")
    oracle.require_exact_int(t1["line_graph_vertices"], "t1.v", lo=28, hi=28)
    oracle.require_exact_int(t1["line_graph_incident_edges"], "t1.inc", lo=168, hi=168)
    oracle.require_exact_int(t1["line_graph_disjoint_pairs"], "t1.disj", lo=210, hi=210)
    oracle.require_exact_int(t1["disjoint_same_operator_tag_bridges"], "t1.dtag", lo=18, hi=18)
    oracle.require_exact_int(t1["disjoint_same_class_and_tag_bridges"], "t1.dct", lo=11, hi=11)
    by_tag = _require_exact_dict(t1["disjoint_bridges_by_tag"], _T1_TAG_KEYS, "t1.by_tag")
    for tk, tv_exp in (
        ("BOUNDARY_WALL", 5),
        ("GAUGE_QUOTIENT", 3),
        ("HOLONOMY_CURVATURE", 3),
        ("PHASE_CROSSOVER", 4),
        ("SCHUR_PUSHFORWARD", 3),
    ):
        oracle.require_exact_int(by_tag[tk], f"t1.tag.{tk}", lo=tv_exp, hi=tv_exp)
    oracle.require_ok(
        t1["sample_disjoint_functor_bridges"] == list(_T1_SAMPLE_BRIDGES),
        "T1_SAMPLE",
        "sample bridges mismatch",
    )
    oracle.require_ok(oracle.require_bool(t1["b1_b2_exact_zero"], "t1.b1b2") is True, "T1_FALSE", "b1_b2")
    oracle.require_ok(oracle.require_bool(t1["l1_equals_8_identity"], "t1.l1_8i") is True, "T1_FALSE", "l1_8i")
    _require_inertia(t1["l1_down_inertia"], [7, 0, 21], "t1.down")
    _require_inertia(t1["l1_up_inertia"], [21, 0, 7], "t1.up")
    oracle.require_exact_int(t1["betti_1_harmonic_dim"], "t1.betti1", lo=0, hi=0)
    nw = parse_canonical_rational_str(t1["wall_cochain_norm_sq_q"], "t1.nw")
    ng = parse_canonical_rational_str(t1["wall_grad_energy_q"], "t1.ng")
    nc = parse_canonical_rational_str(t1["wall_curl_energy_q"], "t1.nc")
    igc = parse_canonical_rational_str(t1["grad_curl_inner_product_q"], "t1.igc")
    oracle.require_ok(ng == Fraction(13, 4), "T1_HODGE_NG", "grad != 13/4")
    oracle.require_ok(nc == Fraction(11, 4), "T1_HODGE_NC", "curl != 11/4")
    oracle.require_ok(nw == ng + nc, "T1_HODGE_SUM", "Pythagorean sum")
    oracle.require_ok(igc == 0, "T1_HODGE_ORTH", "inner product != 0")
    oracle.require_ok(t1["wall_grad_pct_dec2"] == oracle.dec_from_q(ng * 100 / nw, 2), "T1_PCT", "grad pct")
    oracle.require_ok(t1["wall_curl_pct_dec2"] == oracle.dec_from_q(nc * 100 / nw, 2), "T1_PCT", "curl pct")

    # T2: Signed frustration Laplacian & 16-node double cover
    t2 = _require_exact_dict(payload["t2_signed_laplacian_and_double_cover"], _T2_KEYS, "t2")
    oracle.require_exact_int(t2["n_obstruction_walls"], "t2.walls", lo=6, hi=6)
    _require_inertia(t2["l0_inertia"], [7, 0, 1], "t2.l0")
    oracle.require_ok(parse_canonical_rational_str(t2["l0_det_q"], "t2.l0_det") == 0, "T2_DET", "det L0 != 0")
    _require_inertia(t2["l_sigma_inertia"], [8, 0, 0], "t2.lsig")
    oracle.require_ok(parse_canonical_rational_str(t2["l_sigma_det_q"], "t2.lsig_det") == 1841101056, "T2_DET", "det Lsig mismatch")
    oracle.require_exact_int(t2["gauges_exhaustively_checked"], "t2.gauges", lo=128, hi=128)
    mw = parse_canonical_rational_str(t2["min_weighted_frustration_cut_q"], "t2.mw")
    mq = parse_canonical_rational_str(t2["min_weighted_quadratic_energy_q"], "t2.mq")
    oracle.require_ok(mw == 6, "T2_FRUST_MW", "min weighted cut != 6")
    oracle.require_ok(mq == 4 * mw, "T2_FRUST_EQ", "weighted energy mismatch")
    oracle.require_exact_int(t2["min_unweighted_frustration_cut"], "t2.mu", lo=5, hi=5)
    oracle.require_exact_int(t2["best_unweighted_switch_mask"], "t2.mask", lo=119, hi=119)
    oracle.require_exact_int(t2["double_cover_nodes"], "t2.dc_n", lo=16, hi=16)
    oracle.require_exact_int(t2["double_cover_positive_edges"], "t2.dc_pe", lo=56, hi=56)
    oracle.require_exact_int(t2["double_cover_negative_edges"], "t2.dc_ne", lo=0, hi=0)
    oracle.require_exact_int(t2["double_cover_frustrated_triangles"], "t2.dc_ft", lo=0, hi=0)
    oracle.require_ok(parse_canonical_rational_str(t2["double_cover_total_conductance_q"], "t2.dc_w") == 140, "T2_DC_W", "dc_w != 140")
    _require_inertia(t2["double_cover_inertia"], [15, 0, 1], "t2.dc_in")
    oracle.require_ok(oracle.require_bool(t2["antipodal_resistance_equals_2_lsigma_inv_diag"], "t2.anti") is True, "T2_FALSE", "antipodal")
    oracle.require_ok(oracle.require_bool(t2["law5_irreducible_double_sheet_connected"], "t2.law5") is True, "T2_FALSE", "law5")
    anti = _require_exact_dict(t2["antipodal_sheet_resistances_q"], frozenset(oracle.S83_NODES), "t2.anti_map")
    anti_vals = [parse_canonical_rational_str(anti[nid], f"t2.r.{nid}") for nid in oracle.S83_NODES]
    oracle.require_ok(anti_vals == list(_T2_ANTIPODAL_Q), "T2_ANTI_EXACT", "antipodal sheet resistances mismatch")
    oracle.require_ok(t2["min_sheet_separation_r_dec4"] == oracle.dec_from_q(min(anti_vals), 4), "T2_MIN_R", "min sheet R")
    oracle.require_ok(t2["max_sheet_separation_r_dec4"] == oracle.dec_from_q(max(anti_vals), 4), "T2_MAX_R", "max sheet R")

    # T3: Obstruction blow-up & cascade invariants
    t3 = _require_exact_dict(payload["t3_obstruction_blowup_surgery"], _T3_KEYS, "t3")
    b_fr = oracle.require_exact_int(t3["base_frustrated_triangles"], "t3.bfr", lo=22, hi=22)
    oracle.require_exact_int(t3["base_multi_wall_triangles"], "t3.bmu", lo=7, hi=7)
    b_ex = oracle.require_exact_int(t3["base_exact_transitive_closures"], "t3.bex", lo=3, hi=3)
    base_sum_geff = parse_decimal_str_to_q(t3["base_sum_geff_dec4"], 4, "t3.bg")
    base_kirchhoff = parse_decimal_str_to_q(t3["base_kirchhoff_dec4"], 4, "t3.bk")
    bl2_lo = parse_decimal_str_to_q(t3["base_lambda2_lo_dec5"], 5, "t3.bl2lo")
    bl2_hi = parse_decimal_str_to_q(t3["base_lambda2_hi_dec5"], 5, "t3.bl2hi")
    oracle.require_ok(
        (base_sum_geff, base_kirchhoff, bl2_lo, bl2_hi) == _T3_BASE_DEC_Q,
        "T3_BASE_DEC",
        "base T3 decimals mismatch",
    )
    srows = t3["single_surgery_rows"]
    oracle.require_ok(type(srows) is list, "T3_ROWS_TYPE", "surgery rows type")
    oracle.require_ok(len(srows) == 7, "T3_ROWS_LEN", "7 surgery rows")
    seen_pairs: dict[str, dict[str, Any]] = {}
    wall_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(srows):
        rr = _require_exact_dict(row, _T3_ROW_KEYS, f"t3.row[{idx}]")
        pair_s = oracle.require_exact_str(rr["pair"], f"t3.row[{idx}].pair")
        oracle.require_ok(pair_s in _T3_ROW_EXACT, "T3_PAIR_UNKNOWN", f"unknown surgery pair {pair_s}")
        oracle.require_ok(pair_s not in seen_pairs, "T3_DUP_PAIR", f"duplicate surgery pair {pair_s}")
        seen_pairs[pair_s] = rr
        exp_med, exp_mw, exp_dg, exp_dk, exp_l2 = _T3_ROW_EXACT[pair_s]
        oracle.require_ok(rr["original_class"] in ("EXACT_OBSTRUCTION", "CONDITIONAL_BRIDGE"), "T3_CLS", "orig cls")
        if rr["original_class"] == "EXACT_OBSTRUCTION":
            wall_rows.append(rr)
        exp_ow = 1 if rr["original_class"] == "EXACT_OBSTRUCTION" else 2
        oracle.require_exact_int(rr["original_w"], "t3.ow", lo=exp_ow, hi=exp_ow)
        oracle.require_exact_int(rr["upgraded_w"], "t3.uw", lo=4, hi=4)
        oracle.require_ok(oracle.require_exact_str(rr["mediator"], "t3.med") == exp_med, "T3_MED", pair_s)
        fa = oracle.require_exact_int(rr["frustrated_after"], "t3.fa", lo=0, hi=56)
        df = oracle.require_exact_int(rr["delta_frustrated"], "t3.df", lo=-6, hi=6)
        oracle.require_ok(fa - b_fr == df, "T3_DF", "delta_frustrated mismatch")
        oracle.require_exact_int(rr["multi_wall_after"], "t3.ma", lo=exp_mw, hi=exp_mw)
        ea = oracle.require_exact_int(rr["exact_transitive_after"], "t3.ea", lo=b_ex, hi=56)
        de = oracle.require_exact_int(rr["delta_exact_transitive"], "t3.de", lo=0, hi=56)
        oracle.require_ok(ea - b_ex == de, "T3_DE", "delta_exact_transitive mismatch")
        dg_q = parse_decimal_str_to_q(rr["delta_sum_geff_dec4"], 4, "t3.dg")
        dk_q = parse_decimal_str_to_q(rr["delta_kirchhoff_dec5"], 5, "t3.dk")
        l2_q = parse_decimal_str_to_q(rr["lambda2_lo_dec5"], 5, "t3.l2")
        oracle.require_ok((dg_q, dk_q, l2_q) == (exp_dg, exp_dk, exp_l2), "T3_ROW_DEC", pair_s)
        for bflag in ("lambda2_strictly_lifted", "kirchhoff_strictly_reduced", "sum_geff_strictly_lifted"):
            oracle.require_ok(oracle.require_bool(rr[bflag], f"t3.{bflag}") is True, "T3_FALSE", bflag)
    oracle.require_ok(len(wall_rows) == 6, "T3_WALL_COUNT", "6 obstruction walls required")
    expected_rank6 = [
        r["pair"]
        for r in sorted(wall_rows, key=lambda r: (r["delta_frustrated"], -r["delta_exact_transitive"], r["pair"]))
    ]
    rank6 = t3["all_6_walls_holonomy_ranking"]
    oracle.require_ok(type(rank6) is list, "T3_RANK_TYPE", "rank type")
    oracle.require_ok(rank6 == expected_rank6, "T3_RANK_ORDER", "holonomy ranking mismatch")
    oracle.require_ok(rank6[0] == "v6-v7", "T3_RANK_HEAD", "v6-v7 must lead holonomy rank")
    oracle.require_ok(seen_pairs["v6-v7"]["delta_frustrated"] == -6, "T3_V67_DELTA", "v6-v7 must flip -6")
    oracle.require_ok(oracle.require_bool(t3["isolated_wall_v6_v7_flips_all_6"], "t3.v67") is True, "T3_FALSE", "v6_v7_flips_6")
    braess_d = oracle.require_exact_int(t3["braess_unmasking_wall_v1_v4_delta"], "t3.braess", lo=2, hi=2)
    oracle.require_ok(seen_pairs["v1-v4"]["delta_frustrated"] == braess_d, "T3_BRAESS_DELTA", "v1-v4 delta mismatch")
    casc = t3["three_step_cascade"]
    oracle.require_ok(type(casc) is list, "T3_CASC_TYPE", "cascade type")
    oracle.require_ok(len(casc) == 3, "T3_CASC_LEN", "3 cascade steps")
    casc_pairs: list[str] = []
    for idx, step in enumerate(casc):
        sc = _require_exact_dict(step, _T3_CASCADE_KEYS, f"t3.casc[{idx}]")
        oracle.require_exact_int(sc["step"], "t3.cstep", lo=idx + 1, hi=idx + 1)
        exp_cpair, exp_cfr, exp_cmu, exp_cex, exp_cg, exp_cdg, exp_ck = _T3_CASC_EXACT[idx]
        cpair = oracle.require_exact_str(sc["added_pair"], "t3.cpair")
        oracle.require_ok(cpair == exp_cpair, "T3_CASC_PAIR", f"unexpected cascade pair {cpair}")
        casc_pairs.append(cpair)
        oracle.require_exact_int(sc["frustrated_triangles"], "t3.cfr", lo=exp_cfr, hi=exp_cfr)
        oracle.require_exact_int(sc["multi_wall_triangles"], "t3.cmu", lo=exp_cmu, hi=exp_cmu)
        oracle.require_exact_int(sc["exact_transitive_closures"], "t3.cex", lo=exp_cex, hi=exp_cex)
        cg = parse_decimal_str_to_q(sc["sum_geff_dec4"], 4, "t3.cg")
        cdg = parse_decimal_str_to_q(sc["delta_sum_geff_vs_base_dec4"], 4, "t3.cdg")
        ck = parse_decimal_str_to_q(sc["kirchhoff_dec4"], 4, "t3.ck")
        oracle.require_ok((cg, cdg, ck) == (exp_cg, exp_cdg, exp_ck), "T3_CASC_DEC", f"casc[{idx}]")
    sum_single_de = sum(seen_pairs[cp]["delta_exact_transitive"] for cp in casc_pairs)
    oracle.require_ok(
        casc[-1]["exact_transitive_closures"] > b_ex + sum_single_de,
        "T3_SYNERGY_SUPERADD",
        "final exact closures not super-additive over single surgeries",
    )
    oracle.require_ok(oracle.require_bool(t3["superadditive_transitive_synergy_emergent_v0_v1_v5"], "t3.syn") is True, "T3_FALSE", "synergy")

    # T4: Directed asymmetric CEER Loop-Schur invariants
    t4 = _require_exact_dict(payload["t4_directed_ceer_loop_schur"], _T4_KEYS, "t4")
    ab = t4["asymmetric_gains_a_b_q"]
    oracle.require_ok(type(ab) is list, "T4_AB_TYPE", "a,b type")
    oracle.require_ok(len(ab) == 2, "T4_AB_LEN", "a,b len 2")
    a_q = parse_canonical_rational_str(ab[0], "t4.a")
    b_q = parse_canonical_rational_str(ab[1], "t4.b")
    oracle.require_ok(a_q == Fraction(3, 2), "T4_A_EXACT", "a != 3/2")
    oracle.require_ok(b_q == Fraction(1, 3), "T4_B_EXACT", "b != 1/3")
    rho_q = parse_canonical_rational_str(t4["monodromy_rho_q"], "t4.rho")
    gf = parse_canonical_rational_str(t4["g_loop_forward_q"], "t4.gf")
    gr = parse_canonical_rational_str(t4["g_loop_reversed_q"], "t4.gr")
    asym_q = parse_canonical_rational_str(t4["directional_curvature_asymmetry_q"], "t4.asym")
    sf = parse_canonical_rational_str(t4["readout_schur_forward_q"], "t4.sf")
    sr = parse_canonical_rational_str(t4["readout_schur_reversed_q"], "t4.sr")
    adj = parse_canonical_rational_str(t4["adjoint_gain_direction_invariant_q"], "t4.adj")
    oracle.require_ok(rho_q == a_q * b_q, "T4_RHO_EQ", "rho != a*b")
    oracle.require_ok(gf == 1 + b_q * b_q, "T4_GF", "g_loop_fwd")
    oracle.require_ok(gr == 1 + a_q * a_q, "T4_GR", "g_loop_rev")
    oracle.require_ok(asym_q == gr / gf, "T4_ASYM_EQ", "asym != gr/gf")
    oracle.require_ok(sf == (1 - rho_q) ** 2 / gf, "T4_SF", "readout_fwd")
    oracle.require_ok(sr == (1 - rho_q) ** 2 / gr, "T4_SR", "readout_rev")
    oracle.require_ok(adj == Fraction(1) / (1 - rho_q), "T4_ADJ", "adjoint_gain")
    oracle.require_ok(t4["directional_curvature_asymmetry_dec4"] == oracle.dec_from_q(asym_q, 4), "T4_DEC", "asym dec")
    oracle.require_ok(parse_canonical_rational_str(t4["epistemic_curl_frobenius_sq_q"], "t4.curl") == 2, "T4_CURL", "curl != 2")
    nn_l = t4["nonnormal_t1_t2_t3_t10_q"]
    sy_l = t4["symmetric_t1_t2_t3_q"]
    bo_l = t4["transient_boost_over_symmetric_t1_t2_t3_q"]
    oracle.require_ok(type(nn_l) is list, "T4_NN_TYPE", "nn type")
    oracle.require_ok(len(nn_l) == 4, "T4_NN_LEN", "nn len 4")
    oracle.require_ok(type(sy_l) is list, "T4_SY_TYPE", "sy type")
    oracle.require_ok(len(sy_l) == 3, "T4_SY_LEN", "sy len 3")
    oracle.require_ok(type(bo_l) is list, "T4_BO_TYPE", "bo type")
    oracle.require_ok(len(bo_l) == 3, "T4_BO_LEN", "bo len 3")
    nn_q = [parse_canonical_rational_str(x, "t4.nn") for x in nn_l]
    sy_q = [parse_canonical_rational_str(x, "t4.sy") for x in sy_l]
    bo_q = [parse_canonical_rational_str(x, "t4.bo") for x in bo_l]
    oracle.require_ok(
        nn_q == [Fraction(17, 4), Fraction(65, 16), Fraction(145, 64), Fraction(1601, 1048576)],
        "T4_NN_EXACT",
        "nn trajectory mismatch",
    )
    for idx in range(3):
        oracle.require_ok(sy_q[idx] > 0, "T4_SY_POS", f"sy[{idx}] <= 0")
    oracle.require_ok(sy_q == [Fraction(1, 4), Fraction(1, 16), Fraction(1, 64)], "T4_SY_EXACT", "sy trajectory mismatch")
    for idx in range(3):
        oracle.require_ok(bo_q[idx] == nn_q[idx] / sy_q[idx], "T4_BOOST_EQ", "boost ratio")
    ung = parse_canonical_rational_str(t4["ungated_monodromy_divergent_q"], "t4.ung")
    gam = parse_canonical_rational_str(t4["law3_damping_gamma_q"], "t4.gam")
    gat = parse_canonical_rational_str(t4["gated_monodromy_contractive_q"], "t4.gat")
    oracle.require_ok(ung == Fraction(3, 2), "T4_UNG", "ungated != 3/2")
    oracle.require_ok(gam == Fraction(1, 3), "T4_GAM", "gamma != 1/3")
    oracle.require_ok(gat == gam * ung, "T4_GAT_EQ", "gated != gamma*ung")
    _require_inertia(t4["gated_h_pc_inertia"], [2, 0, 0], "t4.hpc_in")
    oracle.require_ok(parse_canonical_rational_str(t4["gated_h_pc_det_q"], "t4.hpc_det") == (1 - gat) ** 2, "T4_HPC_DET", "det H_PC")

    # T5: Borromean H_3 & H_4 hypergraph promotion
    t5 = _require_exact_dict(payload["t5_borromean_hypergraph_promotion"], _T5_KEYS, "t5")
    h3 = _require_exact_dict(t5["h3_borromean_s23"], _T5_H3_KEYS, "t5.h3")
    oracle.require_ok(oracle.require_bool(h3["s23a_pairwise_linking_all_zero"], "t5.h3.lk") is True, "T5_FALSE", "lk zero")
    oracle.require_ok(parse_canonical_rational_str(h3["s23a_abelian_mutual_helicity_q"], "t5.h3.hel") == 0, "T5_HEL", "helicity != 0")
    oracle.require_exact_int(h3["s23b_su2_k2_norm_sq"], "t5.h3.su2", lo=4, hi=4)
    oracle.require_exact_int(h3["milnor_triple_abs"], "t5.h3.milnor", lo=1, hi=1)
    _require_inertia(h3["pairwise_laplacian_inertia"], [0, 0, 3], "t5.h3.pair")
    _require_inertia(h3["hypergraph_h3_inertia"], [2, 0, 1], "t5.h3.in")
    oracle.require_ok(parse_canonical_rational_str(h3["hypergraph_h3_lambda2_q"], "t5.h3.l2") == 3, "T5_H3_L2", "h3 lam2")
    oracle.require_ok(parse_canonical_rational_str(h3["hypergraph_h3_pair_geff_q"], "t5.h3.geff") == Fraction(3, 2), "T5_H3_G", "h3 geff")

    h4 = _require_exact_dict(t5["h4_sovereign_8gib_stack"], _T5_H4_KEYS, "t5.h4")
    vbud = oracle.require_exact_int(h4["vram_budget_mib"], "t5.h4.bud", lo=8192, hi=8192)
    oracle.require_exact_int(h4["materialized_45bpw_oom_mib"], "t5.h4.oom", lo=8256, hi=8256)
    b_mib = oracle.require_exact_int(h4["stack_30bpw_cce_base_mib"], "t5.h4.base", lo=3044, hi=3044)
    l_mib = oracle.require_exact_int(h4["lora_r64_mib"], "t5.h4.lora", lo=192, hi=192)
    c_mib = oracle.require_exact_int(h4["csr_sidecar_mib"], "t5.h4.csr", lo=64, hi=64)
    f_mib = oracle.require_exact_int(h4["full_4way_stack_mib"], "t5.h4.full", lo=1, hi=vbud - 1)
    hr_mib = oracle.require_exact_int(h4["headroom_mib"], "t5.h4.hr", lo=1, hi=vbud)
    oracle.require_ok(f_mib == b_mib + l_mib + c_mib, "T5_H4_SUM", "MiB sum")
    oracle.require_ok(hr_mib == vbud - f_mib, "T5_H4_HR", "headroom sum")
    oracle.require_ok(parse_canonical_rational_str(h4["csr_overhead_ratio_q"], "t5.h4.csrr") == Fraction(26, 35), "T5_CSR", "csr ratio != 26/35")
    oracle.require_exact_int(h4["subsets_checked"], "t5.h4.sub", lo=16, hi=16)
    oracle.require_exact_int(h4["proper_subsets_failed"], "t5.h4.fail", lo=15, hi=15)
    oracle.require_ok(oracle.require_bool(h4["only_full_4body_feasible"], "t5.h4.only4") is True, "T5_FALSE", "only4")
    _require_inertia(h4["pairwise_laplacian_inertia"], [0, 0, 4], "t5.h4.pair")
    _require_inertia(h4["hypergraph_h4_inertia"], [3, 0, 1], "t5.h4.in")
    oracle.require_ok(parse_canonical_rational_str(h4["hypergraph_h4_lambda2_q"], "t5.h4.l2") == 4, "T5_H4_L2", "h4 lam2")
    oracle.require_ok(parse_canonical_rational_str(h4["hypergraph_h4_pair_geff_q"], "t5.h4.geff") == 2, "T5_H4_G", "h4 geff")

    # T6: Kron renormalization & metric-curvature trichotomy
    t6 = _require_exact_dict(payload["t6_kron_renormalization_and_curvature"], _T6_KEYS, "t6")
    _require_inertia(t6["kron_core4_inertia"], [3, 0, 1], "t6.core4")
    _require_inertia(t6["kron_comp4_inertia"], [3, 0, 1], "t6.comp4")
    oracle.require_ok(oracle.require_bool(t6["kron_core4_r_eff_exact_all_6"], "t6.ka") is True, "T6_FALSE", "ka")
    oracle.require_ok(oracle.require_bool(t6["kron_comp4_r_eff_exact_all_6"], "t6.kb") is True, "T6_FALSE", "kb")
    oracle.require_ok(parse_canonical_rational_str(t6["kron_core4_foster_q"], "t6.fa") == 3, "T6_FOSTER", "fa != 3")
    oracle.require_ok(parse_canonical_rational_str(t6["kron_comp4_foster_q"], "t6.fb") == 3, "T6_FOSTER", "fb != 3")
    _require_inertia(t6["k8_resistance_gram_inertia"], [7, 0, 0], "t6.gk8")
    _require_inertia(t6["k4_resistance_gram_inertia"], [3, 0, 0], "t6.gk4")
    dk4 = parse_canonical_rational_str(t6["k4_resistance_gram_det_q"], "t6.dk4")
    oracle.require_ok(dk4 == Fraction(3218, 7036691), "T6_DK4_EXACT", "dk4 != 3218/7036691")
    oracle.require_ok(t6["k4_resistance_gram_det_dec8"] == oracle.dec_from_q(dk4, 8), "T6_DK4_DEC", "dk4 dec")
    _require_inertia(t6["s81_r3_tetrahedron_gram_inertia"], [3, 0, 1], "t6.gr3")
    dr3 = parse_canonical_rational_str(t6["s81_r3_tetrahedron_gram_det_q"], "t6.dr3")
    _require_inertia(t6["s75_cat0_rank_gram_inertia"], [3, 1, 0], "t6.grank")
    drk = parse_canonical_rational_str(t6["s75_cat0_rank_gram_det_q"], "t6.drk")
    nq = parse_canonical_rational_str(t6["s75_cat0_neg_witness_quad_q"], "t6.nq")
    oracle.require_ok(dr3 == 0, "T6_DR3", "dr3 != 0")
    oracle.require_ok(drk == Fraction(-1, 4), "T6_DRK", "drk != -1/4")
    oracle.require_ok(nq == -1, "T6_NQ", "nq != -1")
    oracle.require_ok(oracle.require_bool(t6["curvature_trichotomy_strictly_disjoint"], "t6.disj") is True, "T6_FALSE", "trichotomy")

    return {
        "secondary_audit_passed": True,
        "transformations_checked": 6,
        "lean_theorem_count": thm_n,
    }


def _load_local_lean_pins(track_dir: Path) -> tuple[str, str, str]:
    lean_raw = read_regular_bytes_capped(track_dir / "MeshTransformationsUnlock.lean", "lean_source", max_bytes=1024 * 1024)
    try:
        lean_src = lean_raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise oracle.S85Error("INVALID_UTF8", "Lean source not UTF-8") from exc
    static_gate_lean4_source(lean_src)
    lake_raw = read_regular_bytes_capped(track_dir / "lakefile.toml", "lakefile.toml", max_bytes=4096)
    tc_raw = read_regular_bytes_capped(track_dir / "lean-toolchain", "lean-toolchain", max_bytes=256)
    try:
        tc_text = tc_raw.decode("utf-8", "strict").strip()
    except UnicodeDecodeError as exc:
        raise oracle.S85Error("INVALID_UTF8", "lean-toolchain not UTF-8") from exc
    oracle.require_ok(tc_text == oracle.EXPECTED_LEAN_TOOLCHAIN, "TOOLCHAIN_MISMATCH", "unexpected lean-toolchain")
    return oracle.sha256_hex(lean_raw), oracle.sha256_hex(lake_raw), oracle.sha256_hex(tc_raw)


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
    if full_replay:
        root = Path(_THIS_DIR) if track_dir is None else _require_concrete_path(track_dir, "track_dir")
        l_sha, lk_sha, tc_sha = _load_local_lean_pins(root)
        expected = oracle.build_certificate(
            lean_source_sha256=l_sha,
            lakefile_sha256=lk_sha,
            toolchain_sha256=tc_sha,
        )
        oracle.require_ok(
            hmac.compare_digest(oracle.canonical_json_bytes(cert), oracle.canonical_json_bytes(expected)),
            "FULL_REPLAY_MISMATCH",
            "certificate differs from clean-room pure-Z/Q recomputation",
        )
        replayed = True

    return {
        "valid": True,
        "full_replay": replayed,
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "secondary_audit": sec_res,
    }


def write_certificate_file(path: Path, *, track_dir: Path | None = None) -> dict[str, Any]:
    root = Path(_THIS_DIR) if track_dir is None else _require_concrete_path(track_dir, "track_dir")
    l_sha, lk_sha, tc_sha = _load_local_lean_pins(root)
    cert = oracle.build_certificate(
        lean_source_sha256=l_sha,
        lakefile_sha256=lk_sha,
        toolchain_sha256=tc_sha,
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
    oracle.require_bool(full_replay, "full_replay")
    raw = read_regular_bytes_capped(path, "certificate")
    cert = parse_strict_json_bytes(raw, "certificate", require_canonical=True)
    res = verify_certificate_dict(cert, full_replay=full_replay, track_dir=track_dir)
    res["file_sha256"] = oracle.sha256_hex(raw)
    return res


# ---------------------------------------------------------------------------
# Strict CLI Entrypoint
# ---------------------------------------------------------------------------

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
        elif arg in ("--check", "--write", "--verify-lean"):
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "conflicting mode flags")
            oracle.require_ok(i + 1 < n, "MISSING_PATH_ARG", f"{arg} requires a path")
            val = oracle.require_exact_str(argv[i + 1], f"{arg} path")
            oracle.require_ok("\x00" not in val, "NUL_BYTE_FORBIDDEN", f"NUL byte in {arg} path")
            oracle.require_ok(len(val) > 0 and not val.startswith("-"), "INVALID_PATH_ARG", f"invalid path {val!r}")
            mode = arg[2:]
            target_path = val
            i += 2
        elif arg.startswith("--check=") or arg.startswith("--write=") or arg.startswith("--verify-lean="):
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "conflicting mode flags")
            flag_name, val = arg.split("=", 1)
            oracle.require_ok(len(val) > 0 and not val.startswith("-"), "INVALID_PATH_ARG", f"invalid path {val!r}")
            mode = flag_name[2:]
            target_path = val
            i += 1
        else:
            raise oracle.S85Error("UNKNOWN_FLAG", f"unsupported flag: {arg!r}")
    return {"mode": mode or "default", "target": target_path, "json": want_json}


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv: Any = list(sys.argv[1:]) if argv is None else argv
    try:
        opts = _parse_cli_args(raw_argv)
        mode = opts["mode"]
        if mode == "standalone":
            l_sha, lk_sha, tc_sha = _load_local_lean_pins(Path(_THIS_DIR))
            cert = oracle.build_certificate(
                lean_source_sha256=l_sha,
                lakefile_sha256=lk_sha,
                toolchain_sha256=tc_sha,
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
        if mode == "verify-lean":
            res = verify_lean4_file_live(Path(opts["target"]), require_pinned_sha=True)
            if opts["json"]:
                sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii"))
            else:
                sys.stdout.write(f"LEAN_OK {res['theorems_verified']} {res['lean_source_sha256']}\n")
            return 0
        target = Path(_THIS_DIR) / "s85_mesh_transformations_certificate.json" if mode == "default" else Path(opts["target"])
        res = check_certificate_file(target, full_replay=True)
        if opts["json"]:
            sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii"))
        else:
            sys.stdout.write(f"OK {res['certificate_sha256']}\n")
        return 0
    except oracle.S85Error as exc:
        err_obj = {"error": True, "code": exc.code, "detail": exc.detail}
        sys.stderr.write(json.dumps(err_obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
