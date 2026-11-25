#!/usr/bin/env python3
"""Zone-B Hardened Standalone CLI (`aletheia mesh`), Secondary Auditor & Live Lean 4.36.0 Gate.

Track S88: Supports certificate verification (--check, --write, --standalone), live Lean 4.36.0
kernel verification (--verify-lean), live external mesh analysis (--analyze <mesh.json>),
and parametric K_N scaling (--parametric <N>).

Zero IEEE-754 floats, zero bare asserts, zero .isdigit(), zero host-home tilde paths,
full R10+ Lean 4 anti-bypass static + live kernel hardening.
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

import aletheia_mesh_engine as engine  # noqa: E402

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
    "s83_k8_live_analysis",
    "parametric_scaling_summary",
    "aletheia_cli_plugin_spec",
})
_PINNED_KEYS = frozenset({
    "lean_source",
    "lean_source_sha256",
    "lean_toolchain",
    "lean_toolchain_sha256",
    "lakefile_sha256",
    "lean_theorem_count",
    "lean_theorem_names",
    "s83_certificate_sha256",
    "s83_payload_sha256",
})
_LIVE_WRAP_KEYS = frozenset({"analysis_sha256", "analysis"})
_ANALYSIS_KEYS = frozenset({
    "mesh_id",
    "n_nodes",
    "node_ids",
    "higher_order_convergence",
    "t1_line_graph_hodge",
    "t2_signed_frustration_double_cover",
    "t3_auto_blowup_ranker",
    "t4_directed_loop_schur_gate",
    "t5_borromean_hyperedge_detector",
    "t6_kron_coarsening_and_curvature",
    "law3_contagion_firewall",
})
_ORDERS_KEYS = frozenset({
    "order1_schur",
    "order2_triangles",
    "order3_tetrahedra",
    "order4_five_cells_and_silo_cuts",
})
_O1_KEYS = frozenset({
    "n_nodes",
    "n_edges",
    "pathway_class_counts",
    "total_conductance_q",
    "laplacian_inertia",
    "foster_sum_q",
    "foster_identity_exact",
    "all_pairs_strictly_compounded",
    "min_compounding_gain_pair",
    "min_compounding_gain_q",
    "min_compounding_gain_dec4",
    "max_compounding_gain_pair",
    "max_compounding_gain_q",
    "max_compounding_gain_dec4",
    "total_effective_conductance_q",
    "total_effective_conductance_dec4",
    "kirchhoff_index_q",
    "kirchhoff_index_dec4",
    "lambda2_bracket_q",
    "lambda2_bracket_dec4",
    "resistance_triangle_inequalities_verified",
})
_O2_KEYS = frozenset({
    "n_triangles",
    "classification_counts",
    "odd_z2_holonomy_triangles",
    "even_z2_holonomy_triangles",
    "exact_transitive_closures",
})
_O3_KEYS = frozenset({
    "n_tetrahedra",
    "bianchi_coboundary_zero_all",
    "frustrated_face_distribution",
    "zero_obstruction_k4_count",
    "all_commute_k4_count",
})
_O4_KEYS = frozenset({
    "n_five_cells",
    "zero_obstruction_five_cells",
    "all_commute_five_cells",
    "silo_cut_curves",
})
_T1_KEYS = frozenset({
    "line_graph_vertices",
    "line_graph_edges",
    "vertex_disjoint_edge_pairs",
    "same_tag_disjoint_functor_bridges",
    "b1_b2_zero_exact",
    "hodge1_equals_n_identity",
    "obstruction_flow_norm_sq_q",
    "obstruction_grad_energy_q",
    "obstruction_curl_energy_q",
    "obstruction_hodge_orthogonal_exact",
    "obstruction_hodge_reconstruction_exact",
})
_T2_KEYS = frozenset({
    "obstruction_edge_count",
    "signed_laplacian_inertia",
    "signed_laplacian_det_q",
    "is_frustrated",
    "frustration_lambda1_bracket_q",
    "frustration_lambda1_bracket_dec4",
    "double_cover_vertices",
    "double_cover_edges",
    "double_cover_inertia",
    "double_cover_connected",
    "double_cover_frustrated_triangles",
    "lifted_closed_triangles",
    "lifted_open_6cycles",
    "law5_gauge_sheet_obstruction_active",
})
_T3_KEYS = frozenset({
    "target_class",
    "baseline_lambda2_bracket_q",
    "n_obstruction_candidates",
    "ranked_unlocks",
    "top_frustration_unlock_pair",
    "top_conductance_unlock_pair",
    "top_lambda2_unlock_pair",
    "pareto_multi_wall_obstruction_detected",
})
_T3_ROW_KEYS = frozenset({
    "rank",
    "pair",
    "operator_tag",
    "incident_triangles",
    "frustrated_resolved",
    "multi_wall_exposed",
    "net_frustrated_delta",
    "global_schur_conductance_gain_q",
    "global_schur_conductance_gain_dec4",
    "pair_direct_gain_q",
    "kirchhoff_reduction_q",
    "kirchhoff_reduction_dec4",
    "lambda2_after_bracket_q",
    "lambda2_after_bracket_dec4",
    "lambda2_strict_lift_certified",
    "signed_det_after_q",
    "signed_lambda1_after_bracket_dec4",
})
_T4_KEYS = frozenset({
    "dimension",
    "curl_frobenius_sq_q",
    "non_normal_commutator_sq_q",
    "is_non_normal",
    "directed_col0_response_q",
    "symmetrized_col0_response_q",
    "directional_asymmetry_certified",
    "stable_lyapunov_inertia",
    "stable_gate_passed",
    "unstable_lyapunov_inertia",
    "unstable_gate_rejected",
    "law3_damping_factor_q",
    "damped_lyapunov_inertia",
    "damped_gate_restored",
})
_T5_KEYS = frozenset({"borromean_3body_helicity", "borromean_4way_sovereign_stack"})
_T5_H3_KEYS = frozenset({
    "order",
    "pairwise_laplacian_inertia",
    "hypergraph_laplacian_inertia",
    "pairwise_blind_hypergraph_unlocked",
})
_T5_H4_KEYS = frozenset({
    "order",
    "components",
    "vram_cap_mib",
    "full_4way_vram_mib",
    "headroom_mib",
    "proper_nonempty_subsets_tested",
    "proper_nonempty_subsets_failed",
    "full_4way_feasible",
    "pairwise_laplacian_inertia",
    "hypergraph_laplacian_inertia",
    "borromean_irreducible_certified",
})
_T6_KEYS = frozenset({
    "kept_nodes",
    "eliminated_count",
    "kron_inertia",
    "all_kept_edges_strictly_boosted",
    "all_kept_pairs_r_eff_exact_invariant",
    "r_eff_gram_inertia",
    "r_eff_gram_det_q",
    "cat0_rank_metric_det_q",
    "cat0_rank_metric_inertia",
    "se3_r3_gram_det_q",
    "se3_r3_gram_inertia",
    "three_regime_curvature_separated",
})
_FW_KEYS = frozenset({
    "compromised_node",
    "clean_anchor_node",
    "direct_edge_flux_q",
    "ungated_total_flux_q",
    "ungated_flux_amplification_q",
    "ungated_flux_amplification_dec4",
    "flux_equals_schur_g_eff",
    "all_interior_nodes_corrupted",
    "gated_firewall_flux_q",
    "gated_firewall_interior_max_error_q",
    "retained_submesh_nodes",
    "retained_edges",
    "retained_triangles",
    "retained_all_pairs_compounded",
    "retained_min_compounding_gain_q",
    "retained_min_compounding_gain_dec4",
})
_PARAM_ROW_KEYS = frozenset({
    "n_nodes",
    "n_edges",
    "n_triangles",
    "n_tetrahedra",
    "n_five_cells",
    "foster_identity_exact",
    "all_pairs_strictly_compounded",
    "bianchi_coboundary_zero_all",
    "hodge_b1_b2_zero_exact",
    "hodge1_equals_n_identity",
    "signed_is_frustrated",
    "kron_r_eff_exact_invariant",
    "firewall_zero_flux",
    "balanced_split",
    "balanced_silo_cut",
})
_PLUGIN_KEYS = frozenset({
    "subcommand",
    "entrypoint",
    "input_schemas",
    "modes",
    "node_bounds",
    "zero_float_strict",
    "r4_three_mode_deterministic",
})

# R12 Lean 4 static trust-escape rules (pure-Init file: no quotes, guillemets, macros, imports, +native, dbg/panic, set_option)
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
    r"|(?<!\w)\+\s*native\b|\bnative\s*:=(?!\s*(?:Bool\.)?false[ \t]*[),}])|\bDecide(?:Config|\.Config)\b"
    r"|\bconfig\s*:=|\bwith\s+native\b|\{[^{}]*\bnative\b(?!\s*:=\s*(?:Bool\.)?false[ \t]*[,}])"
    r"|#(?:eval!?(?![\w'!?])|reduce(?![\w'!?])|check(?![\w'!?])|synth(?![\w'!?])|exit(?![\w'!?])|guard(?:_msgs)?(?![\w'!?])|"
    r"print(?![\w'!?])(?!\s+axioms[ \t]+AletheiaMeshEngine\.))"
    r"|(?:^|\n)[ \t]*(?:(?:public|private|meta)\s+)*import\s+"
    r'|["«»]',
    flags=re.DOTALL,
)
_LEAN4_AXIOM_NONE_RE = re.compile(r"^'([^']+)' does not depend on any axioms$")
_LEAN4_AXIOM_DEP_RE = re.compile(r"^'([^']+)' depends on axioms: \[([^\]]*)\]$")
_LEAN_ENV_ALLOWLIST = frozenset({"PATH", "HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "LC_ALL", "TERM"})
_K8_NODE_SET = frozenset(f"v{i}" for i in range(8))
_K8_PAIR_SET = frozenset(f"v{i}-v{j}" for i in range(8) for j in range(i + 1, 8))
_K8_TRIPLE_SET = frozenset(f"v{i}-v{j}-v{k}" for i in range(8) for j in range(i + 1, 8) for k in range(j + 1, 8))
_VALID_OPERATOR_TAGS = frozenset(engine._OPERATOR_TAGS)
_DEC4_NONNEG_RE = re.compile(r"^(?:0|[1-9][0-9]{0,20})\.[0-9]{4}$")


# ---------------------------------------------------------------------------
# Zone-B Path, CWD/$PWD, Atomic dir_fd Read & Atomic Write
# ---------------------------------------------------------------------------

def _require_concrete_path(path: Any, label: str) -> Path:
    engine.require_ok(type(path) in _EXACT_PATH_TYPES, "INVALID_PATH_TYPE", f"{label}: concrete Path required")
    raw_s = engine.require_exact_str(str(path), label)
    engine.require_ok("\x00" not in raw_s, "NUL_BYTE_FORBIDDEN", f"{label}: NUL byte forbidden")
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
        raise engine.MeshError("CWD_UNAVAILABLE", f"{label}: CWD unavailable") from exc
    engine.require_exact_str(str(cwd), f"{label} CWD")
    return cwd


def _check_pwd_no_symlinks(label: str) -> None:
    pwd = os.environ.get("PWD", "")
    if not pwd.startswith("/"):
        return
    engine.require_exact_str(pwd, f"{label} PWD")
    engine.require_ok("\x00" not in pwd, "NUL_BYTE_FORBIDDEN", f"{label} PWD: NUL byte forbidden")
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
        raise engine.MeshError("CWD_UNAVAILABLE", f"{label}: cannot open root for PWD") from exc
    try:
        for part in pwd_path.parts[1:]:
            try:
                next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise engine.MeshError("SYMLINK_ANCESTOR_FORBIDDEN", f"{label}: symlink PWD ancestor") from exc
                raise engine.MeshError("CWD_UNAVAILABLE", f"{label}: PWD ancestor unavailable") from exc
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
    engine.require_ok(
        len(parts) >= 1 and parts[-1] != "..",
        "NOT_A_REGULAR_FILE",
        f"{label}: path does not name a regular file leaf",
    )
    parent_parts, leaf = parts[:-1], parts[-1]
    err_code = "FILE_WRITE_ERROR" if create_parents else "FILE_READ_ERROR"
    try:
        dfd = os.open("/", _DIR_OPEN_FLAGS)
    except OSError as exc:
        raise engine.MeshError(err_code, f"{label}: cannot open root") from exc
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
                        raise engine.MeshError("FILE_WRITE_ERROR", f"{label}: mkdir failed") from mk_exc
                    try:
                        next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
                    except OSError as re_exc:
                        raise engine.MeshError("FILE_WRITE_ERROR", f"{label}: open created dir failed") from re_exc
                elif exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise engine.MeshError("SYMLINK_FORBIDDEN", f"{label}: symlink ancestor forbidden") from exc
                else:
                    raise engine.MeshError(err_code, f"{label}: ancestor unavailable") from exc
            os.close(dfd)
            dfd = next_fd
        return dfd, leaf
    except BaseException:
        os.close(dfd)
        raise


def read_regular_bytes_capped(path: Path, label: str = "file", max_bytes: int = MAX_JSON_BYTES) -> bytes:
    target = _require_concrete_path(path, label)
    engine.require_exact_int(max_bytes, "max_bytes", lo=1, hi=MAX_ALLOWED_CAP_BYTES)
    dfd, leaf = _open_dir_chain(target, label, create_parents=False)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        try:
            fd = os.open(leaf, flags, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise engine.MeshError("SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden") from exc
            raise engine.MeshError("FILE_READ_ERROR", f"{label}: open failed") from exc
    finally:
        os.close(dfd)

    chunks: list[bytes] = []
    total = 0
    try:
        st_f = os.fstat(fd)
        engine.require_ok(stat.S_ISREG(st_f.st_mode), "NOT_A_REGULAR_FILE", f"{label}: not a regular file")
        engine.require_ok(st_f.st_nlink <= 1, "HARDLINK_FORBIDDEN", f"{label}: hardlink forbidden")
        engine.require_ok(st_f.st_size <= max_bytes, "FILE_TOO_LARGE", f"{label}: size exceeds cap")
        while total <= max_bytes:
            chunk = os.read(fd, min(_READ_CHUNK_BYTES, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    except engine.MeshError:
        raise
    except OSError as exc:
        raise engine.MeshError("FILE_READ_ERROR", f"{label}: read failed") from exc
    finally:
        os.close(fd)
    engine.require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"{label}: stream exceeds cap")
    return b"".join(chunks)


def write_regular_bytes_safe(path: Path, payload: bytes, label: str = "output") -> None:
    global _TEMP_SEQ
    engine.require_ok(type(payload) is bytes, "INVALID_PAYLOAD_BYTES", f"{label}: exact bytes required")
    target = _require_concrete_path(path, label)
    dfd, leaf = _open_dir_chain(target, label, create_parents=True)
    tmp_name: str | None = None
    try:
        try:
            st_existing = os.lstat(leaf, dir_fd=dfd)
        except FileNotFoundError:
            st_existing = None
        except OSError as exc:
            raise engine.MeshError("FILE_WRITE_ERROR", f"{label}: lstat failed") from exc
        if st_existing is not None:
            engine.require_ok(not stat.S_ISLNK(st_existing.st_mode), "SYMLINK_FORBIDDEN", f"{label}: symlink leaf")
            engine.require_ok(stat.S_ISREG(st_existing.st_mode), "NOT_A_REGULAR_FILE", f"{label}: non-regular target")
            engine.require_ok(st_existing.st_nlink <= 1, "HARDLINK_FORBIDDEN", f"{label}: hardlinked target")

        pid = os.getpid()
        for _ in range(64):
            with _TEMP_NAME_LOCK:
                _TEMP_SEQ += 1
                seq_num = _TEMP_SEQ
                cand = f".s88.{pid}.{seq_num}.{secrets.token_hex(8)}.tmp"
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
                raise engine.MeshError("FILE_WRITE_ERROR", f"{label}: temp open failed") from exc
        else:
            raise engine.MeshError("FILE_WRITE_ERROR", f"{label}: temp slots exhausted")

        try:
            os.fchmod(fd, 0o600)
            view = memoryview(payload)
            written = 0
            while written < len(view):
                n_written = os.write(fd, view[written:])
                engine.require_ok(n_written > 0, "FILE_WRITE_ERROR", f"{label}: short write 0")
                written += n_written
            os.fsync(fd)
            st_tmp = os.fstat(fd)
            engine.require_ok(st_tmp.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: temp nlink altered")
        except engine.MeshError:
            raise
        except OSError as exc:
            raise engine.MeshError("FILE_WRITE_ERROR", f"{label}: write/fsync failed") from exc
        finally:
            os.close(fd)

        try:
            st_pre = os.lstat(leaf, dir_fd=dfd)
        except FileNotFoundError:
            st_pre = None
        except OSError as exc:
            raise engine.MeshError("FILE_WRITE_ERROR", f"{label}: pre-replace lstat failed") from exc
        if st_pre is not None:
            engine.require_ok(not stat.S_ISLNK(st_pre.st_mode), "SYMLINK_FORBIDDEN", f"{label}: pre-replace symlink leaf")
            engine.require_ok(stat.S_ISREG(st_pre.st_mode), "NOT_A_REGULAR_FILE", f"{label}: pre-replace non-regular target")
            engine.require_ok(st_pre.st_nlink <= 1, "HARDLINK_FORBIDDEN", f"{label}: pre-replace hardlinked target")

        try:
            os.replace(tmp_name, leaf, src_dir_fd=dfd, dst_dir_fd=dfd)
            tmp_name = None
            os.fsync(dfd)
        except OSError as exc:
            raise engine.MeshError("FILE_WRITE_ERROR", f"{label}: atomic replace failed") from exc
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
    s = engine.require_exact_str(token, "json_int")
    neg = s.startswith("-")
    body = s[1:] if neg else s
    engine.require_ok(engine.is_ascii_digits(body), "INVALID_INT_TOKEN", "non-ASCII digits")
    engine.require_ok(len(body) <= engine.MAX_INT_DIGITS, "INT_TOO_LARGE", "int digits cap")
    engine.require_ok(not (len(body) > 1 and body[0] == "0"), "NONCANONICAL_INT", "leading zero")
    engine.require_ok(not (neg and body == "0"), "NONCANONICAL_INT", "negative zero")
    val = int(s)
    engine.require_ok(val.bit_length() <= engine.MAX_INT_BITS, "INT_TOO_LARGE", "int bits cap")
    return val


def _reject_float(token: str) -> Any:
    raise engine.MeshError("FLOAT_FORBIDDEN", f"IEEE-754 float forbidden: {token!r}")


def _reject_const(token: str) -> Any:
    raise engine.MeshError("NONFINITE_JSON_CONSTANT", f"JSON constant forbidden: {token!r}")


def _no_dup_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        engine.require_ok(k not in out, "DUPLICATE_JSON_KEY", f"duplicate key {k!r}")
        out[k] = v
    return out


def parse_strict_json_bytes(raw: bytes, label: str = "json", *, require_canonical: bool = True) -> dict[str, Any]:
    engine.require_ok(type(raw) is bytes, "INVALID_BYTES", f"{label}: exact bytes required")
    engine.require_ok(not raw.startswith(b"\xef\xbb\xbf"), "BOM_FORBIDDEN", f"{label}: UTF-8 BOM forbidden")
    engine.require_ok(b"\r" not in raw, "CRLF_FORBIDDEN", f"{label}: CR forbidden")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise engine.MeshError("INVALID_UTF8", f"{label}: invalid UTF-8") from exc
    try:
        obj = json.loads(
            text,
            parse_float=_reject_float,
            parse_int=_parse_bounded_int,
            parse_constant=_reject_const,
            object_pairs_hook=_no_dup_pairs,
        )
    except engine.MeshError:
        raise
    except (ValueError, RecursionError) as exc:
        raise engine.MeshError("INVALID_JSON", f"{label}: malformed JSON") from exc
    engine.require_ok(type(obj) is dict, "INVALID_ROOT_TYPE", f"{label}: root must be dict")
    engine.validate_strict_json_tree(obj, label)
    if require_canonical:
        engine.require_ok(
            hmac.compare_digest(raw, engine.canonical_json_bytes(obj)),
            "NONCANONICAL_JSON",
            f"{label}: not canonical ASCII LF JSON",
        )
    return obj


def parse_canonical_rational_str(val: Any, label: str) -> Fraction:
    s = engine.require_exact_str(val, label)
    engine.require_ok(len(s) > 0, "INVALID_RATIONAL", f"{label}: empty")
    if "/" in s:
        parts = s.split("/")
        engine.require_ok(len(parts) == 2, "INVALID_RATIONAL", f"{label}: multiple slashes")
        num = _parse_bounded_int(parts[0])
        engine.require_ok(not parts[1].startswith("-"), "INVALID_RATIONAL", f"{label}: negative den")
        den = _parse_bounded_int(parts[1])
        engine.require_ok(den > 1, "NONCANONICAL_RATIONAL", f"{label}: den must be > 1")
        q = Fraction(num, den)
        engine.require_ok(q.denominator == den, "NONCANONICAL_RATIONAL", f"{label}: not reduced")
        return q
    return Fraction(_parse_bounded_int(s), 1)


def _require_exact_dict(obj: Any, keys: frozenset[str], label: str) -> dict[str, Any]:
    engine.require_ok(type(obj) is dict, "INVALID_SCHEMA_DICT", f"{label}: exact dict required")
    engine.require_ok(frozenset(obj.keys()) == keys, "INVALID_SCHEMA_KEYS", f"{label}: keyset mismatch")
    return obj


def _require_inertia(val: Any, expected: list[int], label: str) -> None:
    engine.require_ok(type(val) is list and len(val) == 3, "INVALID_INERTIA", label)
    for elem in val:
        engine.require_exact_int(elem, label, lo=0, hi=32)
    engine.require_ok(val == expected, "INERTIA_MISMATCH", f"{label}: expected {expected}")


# ---------------------------------------------------------------------------
# R10+ Static & Live Lean 4.36.0 Verification Gate (Zero-TOCTOU Private Temp)
# ---------------------------------------------------------------------------

def _strip_lean4_for_static_gate(source: str) -> str:
    """Strip Lean 4 nested block comments and line comments fail-closed."""
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
    engine.require_ok(depth == 0, "LEAN4_UNTERMINATED_LEX", "unterminated Lean block comment")
    return "".join(out)


def static_gate_lean4_source(source: str) -> None:
    s = engine.require_exact_str(source, "lean_source")
    engine.require_ok("\r" not in s and "\x00" not in s, "LEAN4_BAD_CHARS", "CR/NUL in Lean source")
    cleaned = _strip_lean4_for_static_gate(s)
    m = _LEAN4_BANNED_RE.search(cleaned)
    engine.require_ok(m is None, "LEAN4_TRUST_ESCAPE", f"banned Lean construct: {m.group(0)!r}" if m else "")
    for thm in engine.LEAN_THEOREM_NAMES:
        short = thm.split(".")[-1]
        engine.require_ok(
            re.search(rf"(?m)^[ \t]*theorem[ \t]+{re.escape(short)}\b", cleaned) is not None,
            "LEAN4_MISSING_THEOREM",
            f"missing {short}",
        )
        engine.require_ok(
            re.search(rf"(?m)^[ \t]*#print[ \t]+axioms[ \t]+{re.escape(thm)}[ \t]*$", cleaned) is not None,
            "LEAN4_MISSING_PRINT_AXIOMS",
            f"missing #print axioms {thm}",
        )


def _clean_lean_env() -> dict[str, str]:
    """Allowlisted child env for live Lean subprocesses (scrubs LEAN_PATH/LEAN_OPTS/ELAN_*/LEAN_CC)."""
    return {k: v for k, v in os.environ.items() if k in _LEAN_ENV_ALLOWLIST}


def resolve_lean_binary() -> str:
    env_bin = os.environ.get("ALETHEIA_LEAN_BIN")
    if env_bin is not None:
        engine.require_exact_str(env_bin, "ALETHEIA_LEAN_BIN")
        p = Path(env_bin)
        engine.require_ok(p.is_file() and os.access(str(p), os.X_OK), "LEAN_BINARY_UNAVAILABLE", "ALETHEIA_LEAN_BIN unusable")
        return str(p)
    found = shutil.which("lean")
    if found is not None and os.access(found, os.X_OK):
        return found
    home_env = os.environ.get("HOME", "")
    if home_env:
        home_path = Path(home_env)
        for rel in ((".local", "bin", "lean"), (".elan", "bin", "lean")):
            cand = home_path.joinpath(*rel)
            if cand.is_file() and os.access(str(cand), os.X_OK):
                return str(cand)
    raise engine.MeshError("LEAN_BINARY_UNAVAILABLE", "lean executable not found on PATH or standard user bin directories")


def verify_lean4_file_live(lean_path: Path, *, enforce_sha256: bool = True) -> dict[str, Any]:
    engine.require_bool(enforce_sha256, "enforce_sha256")
    raw = read_regular_bytes_capped(lean_path, "lean_source", max_bytes=1024 * 1024)
    file_sha = engine.sha256_hex(raw)
    if enforce_sha256:
        engine.require_ok(
            hmac.compare_digest(file_sha, engine.EXPECTED_LEAN_SHA256),
            "LEAN_SHA256_MISMATCH",
            "Lean source SHA-256 does not match pinned certificate artifact",
        )
    try:
        src = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise engine.MeshError("INVALID_UTF8", "Lean source not UTF-8") from exc
    static_gate_lean4_source(src)
    lean_bin = resolve_lean_binary()
    lean_env = _clean_lean_env()
    try:
        v_proc = subprocess.run([lean_bin, "--version"], env=lean_env, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise engine.MeshError("LEAN_EXEC_ERROR", "lean --version failed") from exc
    engine.require_ok(v_proc.returncode == 0 and "4.36.0" in v_proc.stdout, "LEAN_VERSION_MISMATCH", "Lean 4.36.0 required")

    # Zero-TOCTOU private temp execution of exact hashed bytes
    with tempfile.TemporaryDirectory(prefix="s88_lean_") as tmp_dir:
        os.chmod(tmp_dir, 0o700)
        tmp_file = Path(tmp_dir) / "AletheiaMeshEngine.lean"
        tmp_file.write_bytes(raw)
        try:
            proc = subprocess.run([lean_bin, str(tmp_file)], env=lean_env, capture_output=True, text=True, timeout=120, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise engine.MeshError("LEAN_EXEC_ERROR", "lean elaboration failed") from exc

    engine.require_ok(proc.returncode == 0, "LEAN_COMPILE_FAIL", f"lean rc={proc.returncode}")
    engine.require_ok(proc.stderr.strip() == "", "LEAN_STDERR_NONEMPTY", "lean stderr must be empty")
    engine.require_ok("warning:" not in proc.stdout.lower(), "LEAN_WARNING_FORBIDDEN", "lean warning forbidden")

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
    engine.require_ok(pending == "", "LEAN_UNEXPECTED_STDOUT", "unterminated axiom list")

    seen: dict[str, list[str]] = {}
    for s_line in joined_lines:
        m_none = _LEAN4_AXIOM_NONE_RE.match(s_line)
        if m_none is not None:
            thm_name = m_none.group(1)
            engine.require_ok(thm_name not in seen, "LEAN_DUPLICATE_THEOREM", f"duplicate axiom line: {thm_name}")
            seen[thm_name] = []
            continue
        m_dep = _LEAN4_AXIOM_DEP_RE.match(s_line)
        engine.require_ok(m_dep is not None, "LEAN_UNEXPECTED_STDOUT", f"unexpected lean line: {s_line[:80]}")
        thm_name = m_dep.group(1)
        engine.require_ok(thm_name not in seen, "LEAN_DUPLICATE_THEOREM", f"duplicate axiom line: {thm_name}")
        axs = [a.strip() for a in m_dep.group(2).split(",") if a.strip()]
        for ax in axs:
            engine.require_ok(ax in _ALLOWED_LEAN_AXIOMS, "LEAN_FORBIDDEN_AXIOM", f"forbidden axiom {ax}")
        seen[thm_name] = axs
    engine.require_ok(frozenset(seen.keys()) == frozenset(engine.LEAN_THEOREM_NAMES), "LEAN_THEOREM_SET_MISMATCH", "axioms set mismatch")
    return {
        "mode": "verify-lean",
        "ok": True,
        "static_clean": True,
        "lean_version": v_proc.stdout.strip().splitlines()[0],
        "theorems_verified": len(seen),
        "lean_sha256": file_sha,
        "axioms_by_theorem": seen,
    }


# ---------------------------------------------------------------------------
# Fail-Closed Field-Complete Secondary Audit (FR0 / SEC) & Full Replay (FR1)
# ---------------------------------------------------------------------------

def _audit_bracket_pair(q_pair: Any, d_pair: Any, label: str, *, strict_pos: bool) -> tuple[Fraction, Fraction]:
    engine.require_ok(type(q_pair) is list and len(q_pair) == 2, "INVALID_BRACKET", f"{label}.q")
    engine.require_ok(type(d_pair) is list and len(d_pair) == 2, "INVALID_BRACKET", f"{label}.dec4")
    lo = parse_canonical_rational_str(q_pair[0], f"{label}.lo")
    hi = parse_canonical_rational_str(q_pair[1], f"{label}.hi")
    engine.require_ok(lo <= hi and (lo > 0 if strict_pos else lo >= 0), "INVALID_BRACKET_RANGE", label)
    engine.require_ok(
        d_pair[0] == engine.dec_from_q(lo, 4) and d_pair[1] == engine.dec_from_q(hi, 4),
        "BRACKET_DEC_MISMATCH",
        label,
    )
    return lo, hi


def _audit_dec4_nonneg_bracket(val: Any, label: str) -> None:
    engine.require_ok(type(val) is list and len(val) == 2, "T3_SL1_DEC", label)
    s0 = engine.require_exact_str(val[0], f"{label}[0]")
    s1 = engine.require_exact_str(val[1], f"{label}[1]")
    engine.require_ok(
        _DEC4_NONNEG_RE.match(s0) is not None
        and _DEC4_NONNEG_RE.match(s1) is not None
        and int(s0.replace(".", "")) <= int(s1.replace(".", "")),
        "T3_SL1_DEC",
        label,
    )


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Fail-closed semantic + algebraic auditor enforced under BOTH full_replay=True and False."""
    engine.require_ok(type(payload) is dict, "INVALID_PAYLOAD_TYPE", "payload must be exact dict")
    engine.validate_strict_json_tree(payload, "payload")
    _require_exact_dict(payload, _PAYLOAD_KEYS, "payload")
    engine.require_ok(payload["schema_version"] == engine.SCHEMA_VERSION, "SCHEMA_MISMATCH", "schema_version")
    engine.require_ok(payload["track_id"] == engine.TRACK_ID, "SCHEMA_MISMATCH", "track_id")
    engine.require_ok(payload["oracle_class"] == "exact", "SCHEMA_MISMATCH", "oracle_class")
    engine.require_ok(payload["novelty_classification"] == "N1", "SCHEMA_MISMATCH", "novelty")

    pa = _require_exact_dict(payload["pinned_artifacts"], _PINNED_KEYS, "pinned_artifacts")
    engine.require_ok(pa["lean_source"] == "AletheiaMeshEngine.lean", "SCHEMA_MISMATCH", "lean_source")
    engine.require_ok(
        hmac.compare_digest(engine.require_hex64(pa["lean_source_sha256"], "lean_sha"), engine.EXPECTED_LEAN_SHA256)
        and hmac.compare_digest(engine.require_hex64(pa["lean_toolchain_sha256"], "tc_sha"), engine.EXPECTED_TOOLCHAIN_SHA256)
        and hmac.compare_digest(engine.require_hex64(pa["lakefile_sha256"], "lk_sha"), engine.EXPECTED_LAKEFILE_SHA256)
        and hmac.compare_digest(engine.require_hex64(pa["s83_certificate_sha256"], "s83_c"), engine.PINNED_S83_CERT_SHA256)
        and hmac.compare_digest(engine.require_hex64(pa["s83_payload_sha256"], "s83_p"), engine.PINNED_S83_PAYLOAD_SHA256),
        "PINNED_SHA_MISMATCH",
        "pinned artifact sha256 mismatch",
    )
    engine.require_ok(pa["lean_toolchain"] == engine.EXPECTED_LEAN_TOOLCHAIN, "SCHEMA_MISMATCH", "lean_toolchain")
    thm_n = engine.require_exact_int(
        pa["lean_theorem_count"], "lean_theorem_count", lo=len(engine.LEAN_THEOREM_NAMES), hi=len(engine.LEAN_THEOREM_NAMES)
    )
    engine.require_ok(
        type(pa["lean_theorem_names"]) is list and tuple(pa["lean_theorem_names"]) == engine.LEAN_THEOREM_NAMES,
        "THEOREM_LIST_MISMATCH",
        "lean_theorem_names",
    )

    # Audit S83 K_8 live analysis wrapper & inner hash
    wrap = _require_exact_dict(payload["s83_k8_live_analysis"], _LIVE_WRAP_KEYS, "s83_k8_live_analysis")
    a_sha = engine.require_hex64(wrap["analysis_sha256"], "analysis_sha256")
    an = _require_exact_dict(wrap["analysis"], _ANALYSIS_KEYS, "analysis")
    engine.require_ok(
        hmac.compare_digest(a_sha, engine.sha256_hex(engine.canonical_json_bytes(an))),
        "ANALYSIS_SHA_MISMATCH",
        "analysis_sha256 mismatch",
    )
    engine.require_ok(an["mesh_id"] == "s83_k8_epistemic_mesh", "MESH_ID_MISMATCH", "mesh_id")
    n = engine.require_exact_int(an["n_nodes"], "n_nodes", lo=8, hi=8)
    engine.require_ok(an["node_ids"] == [f"v{i}" for i in range(8)], "NODE_IDS_MISMATCH", "node_ids")

    # Orders 1-4
    ho = _require_exact_dict(an["higher_order_convergence"], _ORDERS_KEYS, "higher_order_convergence")
    o1 = _require_exact_dict(ho["order1_schur"], _O1_KEYS, "order1_schur")
    engine.require_exact_int(o1["n_nodes"], "o1.n", lo=8, hi=8)
    engine.require_exact_int(o1["n_edges"], "o1.e", lo=28, hi=28)
    o1_cls = _require_exact_dict(o1["pathway_class_counts"], frozenset(engine.PATHWAY_WEIGHTS.keys()), "o1.cls")
    c_ex = engine.require_exact_int(o1_cls["EXACT_COMMUTE"], "o1.ex", lo=10, hi=10)
    c_br = engine.require_exact_int(o1_cls["CONDITIONAL_BRIDGE"], "o1.br", lo=12, hi=12)
    c_ob = engine.require_exact_int(o1_cls["EXACT_OBSTRUCTION"], "o1.ob", lo=6, hi=6)
    engine.require_ok(
        parse_canonical_rational_str(o1["total_conductance_q"], "o1.tot") == Fraction(4 * c_ex + 2 * c_br + c_ob, 1),
        "O1_CONDUCTANCE_MISMATCH",
        "pathway class sum/conductance",
    )
    _require_inertia(o1["laplacian_inertia"], [7, 0, 1], "o1.inertia")
    min_p = engine.require_exact_str(o1["min_compounding_gain_pair"], "o1.min_p")
    max_p = engine.require_exact_str(o1["max_compounding_gain_pair"], "o1.max_p")
    engine.require_ok(min_p == "v1-v2" and max_p == "v6-v7", "O1_PAIR_INVALID", "compounding gain pairs")
    min_g = parse_canonical_rational_str(o1["min_compounding_gain_q"], "o1.min_g")
    max_g = parse_canonical_rational_str(o1["max_compounding_gain_q"], "o1.max_g")
    sum_g = parse_canonical_rational_str(o1["total_effective_conductance_q"], "o1.sum_g")
    kf = parse_canonical_rational_str(o1["kirchhoff_index_q"], "o1.kf")
    engine.require_ok(
        parse_canonical_rational_str(o1["foster_sum_q"], "o1.foster") == Fraction(7, 1)
        and engine.require_bool(o1["foster_identity_exact"], "o1.foster_b") is True
        and engine.require_bool(o1["all_pairs_strictly_compounded"], "o1.comp_b") is True
        and min_g == Fraction(7036691, 2633272)
        and max_g == Fraction(7036691, 681655)
        and o1["min_compounding_gain_dec4"] == engine.dec_from_q(min_g, 4)
        and o1["max_compounding_gain_dec4"] == engine.dec_from_q(max_g, 4)
        and sum_g > 0
        and o1["total_effective_conductance_dec4"] == engine.dec_from_q(sum_g, 4)
        and kf == Fraction(1524767464, 63330219)
        and o1["kirchhoff_index_dec4"] == engine.dec_from_q(kf, 4),
        "O1_ALGEBRA_FAIL",
        "order1 algebraic checks",
    )
    l2_base = _audit_bracket_pair(o1["lambda2_bracket_q"], o1["lambda2_bracket_dec4"], "o1.lam2", strict_pos=True)
    engine.require_ok(l2_base == (Fraction(11487, 1024), Fraction(22995, 2048)), "O1_LAM2_MISMATCH", "o1.lam2")
    engine.require_exact_int(o1["resistance_triangle_inequalities_verified"], "o1.tri_ineq", lo=168, hi=168)

    o2 = _require_exact_dict(ho["order2_triangles"], _O2_KEYS, "order2_triangles")
    engine.require_exact_int(o2["n_triangles"], "o2.n", lo=56, hi=56)
    o2c = _require_exact_dict(
        o2["classification_counts"],
        frozenset({
            "EXACT_TRANSITIVE_CLOSURE",
            "CONDITIONAL_COMPOUNDING_CLOSURE",
            "FRUSTRATED_CURVATURE_LOOP",
            "MULTI_WALL_BOUNDARY_SECTOR",
        }),
        "o2.cls",
    )
    o2_et = engine.require_exact_int(o2c["EXACT_TRANSITIVE_CLOSURE"], "o2.et", lo=1, hi=56)
    o2_cc = engine.require_exact_int(o2c["CONDITIONAL_COMPOUNDING_CLOSURE"], "o2.cc", lo=1, hi=56)
    o2_fr = engine.require_exact_int(o2c["FRUSTRATED_CURVATURE_LOOP"], "o2.fr", lo=1, hi=56)
    o2_mw = engine.require_exact_int(o2c["MULTI_WALL_BOUNDARY_SECTOR"], "o2.mw", lo=1, hi=56)
    o2_odd = engine.require_exact_int(o2["odd_z2_holonomy_triangles"], "o2.odd", lo=1, hi=56)
    o2_ev = engine.require_exact_int(o2["even_z2_holonomy_triangles"], "o2.even", lo=1, hi=56)
    et_list = o2["exact_transitive_closures"]
    engine.require_ok(
        o2_et + o2_cc + o2_fr + o2_mw == 56
        and o2_odd + o2_ev == 56
        and o2_odd >= o2_fr
        and type(et_list) is list
        and len(et_list) == o2_et,
        "O2_ALGEBRA_FAIL",
        "order2 counts",
    )
    seen_et: set[str] = set()
    for idx_et, et_item in enumerate(et_list):
        et_s = engine.require_exact_str(et_item, f"o2.et[{idx_et}]")
        engine.require_ok(et_s in _K8_TRIPLE_SET and et_s not in seen_et, "O2_CLOSURE_INVALID", et_s)
        seen_et.add(et_s)

    o3 = _require_exact_dict(ho["order3_tetrahedra"], _O3_KEYS, "order3_tetrahedra")
    engine.require_exact_int(o3["n_tetrahedra"], "o3.n", lo=70, hi=70)
    engine.require_ok(engine.require_bool(o3["bianchi_coboundary_zero_all"], "o3.bi") is True, "O3_BIANCHI_FAIL", "bianchi")
    fdist = _require_exact_dict(o3["frustrated_face_distribution"], frozenset({"0", "1", "2", "3", "4"}), "o3.fdist")
    fd0 = engine.require_exact_int(fdist["0"], "o3.fd0", lo=0, hi=70)
    fd1 = engine.require_exact_int(fdist["1"], "o3.fd1", lo=0, hi=0)
    fd2 = engine.require_exact_int(fdist["2"], "o3.fd2", lo=0, hi=70)
    fd3 = engine.require_exact_int(fdist["3"], "o3.fd3", lo=0, hi=0)
    fd4 = engine.require_exact_int(fdist["4"], "o3.fd4", lo=0, hi=70)
    engine.require_ok(fd0 + fd1 + fd2 + fd3 + fd4 == 70, "O3_FDIST_FAIL", "tetrahedra sum != 70")
    engine.require_exact_int(o3["zero_obstruction_k4_count"], "o3.k4z", lo=16, hi=16)
    engine.require_exact_int(o3["all_commute_k4_count"], "o3.k4c", lo=0, hi=0)

    o4 = _require_exact_dict(ho["order4_five_cells_and_silo_cuts"], _O4_KEYS, "order4")
    engine.require_exact_int(o4["n_five_cells"], "o4.n5", lo=56, hi=56)
    engine.require_exact_int(o4["zero_obstruction_five_cells"], "o4.c5z", lo=4, hi=4)
    engine.require_exact_int(o4["all_commute_five_cells"], "o4.c5c", lo=0, hi=0)
    sc = _require_exact_dict(o4["silo_cut_curves"], frozenset({"1|7", "2|6", "3|5", "4|4"}), "o4.sc")
    for s_sz in (1, 2, 3, 4):
        s_row = _require_exact_dict(sc[f"{s_sz}|{8 - s_sz}"], frozenset({"k2", "k3", "k4", "k5"}), f"o4.sc.{s_sz}")
        for k_ord in (2, 3, 4, 5):
            kr = _require_exact_dict(s_row[f"k{k_ord}"], frozenset({"total", "destroyed", "destroyed_pct_dec2"}), f"o4.k{k_ord}")
            exp_tot = engine.comb_k(8, k_ord)
            exp_dest = exp_tot - engine.comb_k(s_sz, k_ord) - engine.comb_k(8 - s_sz, k_ord)
            engine.require_exact_int(kr["total"], "kr.tot", lo=exp_tot, hi=exp_tot)
            engine.require_exact_int(kr["destroyed"], "kr.dest", lo=exp_dest, hi=exp_dest)
            engine.require_ok(
                kr["destroyed_pct_dec2"] == engine.dec_from_q(Fraction(exp_dest * 100, exp_tot), 2),
                "O4_SILO_PCT_MISMATCH",
                f"{s_sz}/k{k_ord}",
            )

    # T_1 Line Graph & Hodge
    t1 = _require_exact_dict(an["t1_line_graph_hodge"], _T1_KEYS, "t1")
    engine.require_exact_int(t1["line_graph_vertices"], "t1.v", lo=28, hi=28)
    engine.require_exact_int(t1["line_graph_edges"], "t1.e", lo=168, hi=168)
    engine.require_exact_int(t1["vertex_disjoint_edge_pairs"], "t1.d", lo=210, hi=210)
    engine.require_exact_int(t1["same_tag_disjoint_functor_bridges"], "t1.st", lo=18, hi=18)
    f_norm = parse_canonical_rational_str(t1["obstruction_flow_norm_sq_q"], "t1.norm")
    f_grad = parse_canonical_rational_str(t1["obstruction_grad_energy_q"], "t1.grad")
    f_curl = parse_canonical_rational_str(t1["obstruction_curl_energy_q"], "t1.curl")
    engine.require_ok(
        engine.require_bool(t1["b1_b2_zero_exact"], "t1.b1b2") is True
        and engine.require_bool(t1["hodge1_equals_n_identity"], "t1.h1") is True
        and engine.require_bool(t1["obstruction_hodge_orthogonal_exact"], "t1.orth") is True
        and engine.require_bool(t1["obstruction_hodge_reconstruction_exact"], "t1.recon") is True
        and f_grad == Fraction(13, 4)
        and f_curl == Fraction(11, 4)
        and f_grad + f_curl == f_norm,
        "T1_HODGE_FAIL",
        "T1 Hodge invariant",
    )

    # T_2 Signed Frustration & Double Cover
    t2 = _require_exact_dict(an["t2_signed_frustration_double_cover"], _T2_KEYS, "t2")
    engine.require_exact_int(t2["obstruction_edge_count"], "t2.obs", lo=c_ob, hi=c_ob)
    _require_inertia(t2["signed_laplacian_inertia"], [8, 0, 0], "t2.sig_in")
    engine.require_ok(
        parse_canonical_rational_str(t2["signed_laplacian_det_q"], "t2.det") == Fraction(1841101056, 1),
        "T2_DET_FAIL",
        "signed_laplacian_det_q",
    )
    engine.require_ok(engine.require_bool(t2["is_frustrated"], "t2.fr") is True, "T2_FRUST_FAIL", "is_frustrated")
    l1_t2 = _audit_bracket_pair(t2["frustration_lambda1_bracket_q"], t2["frustration_lambda1_bracket_dec4"], "t2.l1", strict_pos=True)
    engine.require_ok(l1_t2 == (Fraction(4985, 2048), Fraction(2495, 1024)), "T2_L1_MISMATCH", "t2.l1")
    engine.require_exact_int(t2["double_cover_vertices"], "t2.dcv", lo=16, hi=16)
    engine.require_exact_int(t2["double_cover_edges"], "t2.dce", lo=56, hi=56)
    _require_inertia(t2["double_cover_inertia"], [15, 0, 1], "t2.dc_in")
    engine.require_exact_int(t2["double_cover_frustrated_triangles"], "t2.dcf", lo=0, hi=0)
    engine.require_exact_int(t2["lifted_closed_triangles"], "t2.lct", lo=2 * o2_ev, hi=2 * o2_ev)
    engine.require_exact_int(t2["lifted_open_6cycles"], "t2.lo6", lo=o2_odd, hi=o2_odd)
    engine.require_ok(
        engine.require_bool(t2["double_cover_connected"], "t2.dcc") is True
        and engine.require_bool(t2["law5_gauge_sheet_obstruction_active"], "t2.l5") is True,
        "T2_DC_FAIL",
        "double cover flags",
    )

    # T_3 Auto-Blow-Up Mediator Ranker
    t3 = _require_exact_dict(an["t3_auto_blowup_ranker"], _T3_KEYS, "t3")
    engine.require_ok(t3["target_class"] == "EXACT_COMMUTE", "T3_TARGET", "target_class")
    engine.require_ok(t3["baseline_lambda2_bracket_q"] == o1["lambda2_bracket_q"], "T3_BASE_L2", "baseline_lambda2")
    engine.require_exact_int(t3["n_obstruction_candidates"], "t3.n", lo=c_ob, hi=c_ob)
    unlocks = t3["ranked_unlocks"]
    engine.require_ok(type(unlocks) is list and len(unlocks) == c_ob, "T3_LEN", "ranked_unlocks length")
    prev_net = -100
    best_dg: tuple[Fraction, str] = (Fraction(-1), "")
    best_l2: tuple[Fraction, str] = (Fraction(-1), "")
    seen_t3_pairs: set[str] = set()
    for idx_r, urow in enumerate(unlocks, 1):
        rr = _require_exact_dict(urow, _T3_ROW_KEYS, f"t3.row[{idx_r}]")
        engine.require_exact_int(rr["rank"], "t3.rank", lo=idx_r, hi=idx_r)
        pair_s = engine.require_exact_str(rr["pair"], "t3.pair")
        tag_s = engine.require_exact_str(rr["operator_tag"], "t3.tag")
        engine.require_ok(
            pair_s in _K8_PAIR_SET and pair_s not in seen_t3_pairs and tag_s in _VALID_OPERATOR_TAGS,
            "T3_PAIR_TAG_INVALID",
            f"row[{idx_r}]",
        )
        seen_t3_pairs.add(pair_s)
        engine.require_exact_int(rr["incident_triangles"], "t3.inc", lo=6, hi=6)
        fr_r = engine.require_exact_int(rr["frustrated_resolved"], "t3.fr", lo=0, hi=6)
        mw_r = engine.require_exact_int(rr["multi_wall_exposed"], "t3.mw", lo=0, hi=6 - fr_r)
        net_r = engine.require_exact_int(rr["net_frustrated_delta"], "t3.net", lo=-6, hi=6)
        engine.require_ok(net_r == mw_r - fr_r and net_r >= prev_net, "T3_ORDER_FAIL", pair_s)
        prev_net = net_r
        dg_q = parse_canonical_rational_str(rr["global_schur_conductance_gain_q"], "t3.dg")
        pdg_q = parse_canonical_rational_str(rr["pair_direct_gain_q"], "t3.pdg")
        dkf_q = parse_canonical_rational_str(rr["kirchhoff_reduction_q"], "t3.dkf")
        l2_a = _audit_bracket_pair(rr["lambda2_after_bracket_q"], rr["lambda2_after_bracket_dec4"], "t3.l2", strict_pos=True)
        _audit_dec4_nonneg_bracket(rr["signed_lambda1_after_bracket_dec4"], f"t3.sl1[{idx_r}]")
        engine.require_ok(
            dg_q > 0
            and pdg_q > 0
            and dkf_q > 0
            and rr["global_schur_conductance_gain_dec4"] == engine.dec_from_q(dg_q, 4)
            and rr["kirchhoff_reduction_dec4"] == engine.dec_from_q(dkf_q, 4)
            and engine.require_bool(rr["lambda2_strict_lift_certified"], "t3.l2lift") is (l2_a[0] > l2_base[1])
            and parse_canonical_rational_str(rr["signed_det_after_q"], "t3.sdet") > 0,
            "T3_ROW_ALGEBRA",
            pair_s,
        )
        if dg_q > best_dg[0]:
            best_dg = (dg_q, pair_s)
        if (l2_a[0] + l2_a[1]) > best_l2[0]:
            best_l2 = (l2_a[0] + l2_a[1], pair_s)
    engine.require_ok(
        t3["top_frustration_unlock_pair"] == unlocks[0]["pair"]
        and t3["top_conductance_unlock_pair"] == best_dg[1]
        and t3["top_lambda2_unlock_pair"] == best_l2[1]
        and engine.require_bool(t3["pareto_multi_wall_obstruction_detected"], "t3.pareto")
        is (t3["top_frustration_unlock_pair"] != t3["top_conductance_unlock_pair"]),
        "T3_PARETO_FAIL",
        "top frustration / conductance / lambda2 / pareto check",
    )

    # T_4 Directed Loop-Schur Gate
    t4 = _require_exact_dict(an["t4_directed_loop_schur_gate"], _T4_KEYS, "t4")
    engine.require_exact_int(t4["dimension"], "t4.dim", lo=3, hi=3)
    d_resp = parse_canonical_rational_str(t4["directed_col0_response_q"], "t4.dir")
    s_resp = parse_canonical_rational_str(t4["symmetrized_col0_response_q"], "t4.sym")
    _require_inertia(t4["stable_lyapunov_inertia"], [3, 0, 0], "t4.st_in")
    _require_inertia(t4["damped_lyapunov_inertia"], [3, 0, 0], "t4.dp_in")
    u_in = t4["unstable_lyapunov_inertia"]
    engine.require_ok(type(u_in) is list and len(u_in) == 3, "T4_UNSTABLE_FAIL", "unstable inertia len")
    u_vals = [engine.require_exact_int(x, f"t4.u_in[{i}]", lo=0, hi=3) for i, x in enumerate(u_in)]
    engine.require_ok(sum(u_vals) == 3 and u_vals != [3, 0, 0], "T4_UNSTABLE_FAIL", "unstable inertia must fail SPD")
    engine.require_ok(
        parse_canonical_rational_str(t4["curl_frobenius_sq_q"], "t4.curl") == Fraction(137, 900)
        and parse_canonical_rational_str(t4["non_normal_commutator_sq_q"], "t4.comm") == Fraction(12403, 405000)
        and engine.require_bool(t4["is_non_normal"], "t4.nn") is True
        and d_resp == Fraction(1560, 809)
        and s_resp == Fraction(156, 79)
        and engine.require_bool(t4["directional_asymmetry_certified"], "t4.asym") is True
        and engine.require_bool(t4["stable_gate_passed"], "t4.sg") is True
        and engine.require_bool(t4["unstable_gate_rejected"], "t4.ug") is True
        and parse_canonical_rational_str(t4["law3_damping_factor_q"], "t4.damp") == Fraction(2, 5)
        and engine.require_bool(t4["damped_gate_restored"], "t4.dg") is True,
        "T4_GATE_FAIL",
        "T4 directed loop invariants",
    )

    # T_5 Borromean Hyperedge Detector
    t5 = _require_exact_dict(an["t5_borromean_hyperedge_detector"], _T5_KEYS, "t5")
    h3 = _require_exact_dict(t5["borromean_3body_helicity"], _T5_H3_KEYS, "t5.h3")
    engine.require_exact_int(h3["order"], "t5.h3.o", lo=3, hi=3)
    _require_inertia(h3["pairwise_laplacian_inertia"], [0, 0, 3], "t5.h3.p")
    _require_inertia(h3["hypergraph_laplacian_inertia"], [2, 0, 1], "t5.h3.h")
    engine.require_ok(engine.require_bool(h3["pairwise_blind_hypergraph_unlocked"], "t5.h3.u") is True, "T5_H3_FAIL", "H3")
    h4 = _require_exact_dict(t5["borromean_4way_sovereign_stack"], _T5_H4_KEYS, "t5.h4")
    engine.require_exact_int(h4["order"], "t5.h4.o", lo=4, hi=4)
    comps = h4["components"]
    engine.require_ok(type(comps) is list and len(comps) == 4, "T5_H4_COMP", "4 components")
    seen_comp: set[str] = set()
    for idx_c, c_item in enumerate(comps):
        c_s = engine.require_exact_str(c_item, f"t5.h4.comp[{idx_c}]")
        engine.require_ok(c_s != "" and c_s not in seen_comp, "T5_H4_COMP", f"component[{idx_c}]")
        seen_comp.add(c_s)
    cap_mib = engine.require_exact_int(h4["vram_cap_mib"], "t5.cap", lo=8192, hi=8192)
    full_mib = engine.require_exact_int(h4["full_4way_vram_mib"], "t5.full", lo=4821, hi=4821)
    head_mib = engine.require_exact_int(h4["headroom_mib"], "t5.head", lo=1, hi=cap_mib)
    engine.require_exact_int(h4["proper_nonempty_subsets_tested"], "t5.st", lo=14, hi=14)
    engine.require_exact_int(h4["proper_nonempty_subsets_failed"], "t5.sf", lo=14, hi=14)
    _require_inertia(h4["pairwise_laplacian_inertia"], [0, 0, 4], "t5.h4.p")
    _require_inertia(h4["hypergraph_laplacian_inertia"], [3, 0, 1], "t5.h4.h")
    engine.require_ok(
        full_mib + head_mib == cap_mib
        and engine.require_bool(h4["full_4way_feasible"], "t5.h4.f") is True
        and engine.require_bool(h4["borromean_irreducible_certified"], "t5.h4.b") is True,
        "T5_H4_FAIL",
        "H4 sovereign stack",
    )

    # T_6 Kron Coarsening & Curvature
    t6 = _require_exact_dict(an["t6_kron_coarsening_and_curvature"], _T6_KEYS, "t6")
    engine.require_ok(t6["kept_nodes"] == ["v0", "v1", "v2", "v3"], "T6_KEEP", "kept_nodes")
    engine.require_exact_int(t6["eliminated_count"], "t6.el", lo=4, hi=4)
    _require_inertia(t6["kron_inertia"], [3, 0, 1], "t6.kin")
    _require_inertia(t6["r_eff_gram_inertia"], [3, 0, 0], "t6.gin")
    _require_inertia(t6["cat0_rank_metric_inertia"], [3, 1, 0], "t6.cat0_in")
    _require_inertia(t6["se3_r3_gram_inertia"], [3, 0, 1], "t6.se3_in")
    engine.require_ok(
        engine.require_bool(t6["all_kept_edges_strictly_boosted"], "t6.boost") is True
        and engine.require_bool(t6["all_kept_pairs_r_eff_exact_invariant"], "t6.inv") is True
        and parse_canonical_rational_str(t6["r_eff_gram_det_q"], "t6.rdet") == Fraction(3218, 7036691)
        and parse_canonical_rational_str(t6["cat0_rank_metric_det_q"], "t6.cdet") == Fraction(-1, 4)
        and parse_canonical_rational_str(t6["se3_r3_gram_det_q"], "t6.sdet") == 0
        and engine.require_bool(t6["three_regime_curvature_separated"], "t6.sep") is True,
        "T6_KRON_FAIL",
        "T6 Kron/curvature",
    )

    # Law-3 Contagion Firewall
    fw = _require_exact_dict(an["law3_contagion_firewall"], _FW_KEYS, "fw")
    comp_n = engine.require_exact_str(fw["compromised_node"], "fw.comp")
    anch_n = engine.require_exact_str(fw["clean_anchor_node"], "fw.anch")
    engine.require_ok(
        comp_n in _K8_NODE_SET and anch_n in _K8_NODE_SET and comp_n != anch_n,
        "FW_NODE_INVALID",
        "compromised/anchor node",
    )
    j_dir = parse_canonical_rational_str(fw["direct_edge_flux_q"], "fw.dir")
    j_ung = parse_canonical_rational_str(fw["ungated_total_flux_q"], "fw.ung")
    amp = parse_canonical_rational_str(fw["ungated_flux_amplification_q"], "fw.amp")
    rmg = parse_canonical_rational_str(fw["retained_min_compounding_gain_q"], "fw.rmg")
    engine.require_exact_int(fw["retained_submesh_nodes"], "fw.rn", lo=7, hi=7)
    engine.require_exact_int(fw["retained_edges"], "fw.re", lo=21, hi=21)
    engine.require_exact_int(fw["retained_triangles"], "fw.rt", lo=35, hi=35)
    engine.require_ok(
        j_dir == Fraction(4, 1)
        and j_ung == Fraction(126660438, 10774199)
        and amp == j_ung / j_dir
        and fw["ungated_flux_amplification_dec4"] == engine.dec_from_q(amp, 4)
        and engine.require_bool(fw["flux_equals_schur_g_eff"], "fw.schur") is True
        and engine.require_bool(fw["all_interior_nodes_corrupted"], "fw.corr") is True
        and parse_canonical_rational_str(fw["gated_firewall_flux_q"], "fw.gf") == 0
        and parse_canonical_rational_str(fw["gated_firewall_interior_max_error_q"], "fw.ge") == 0
        and engine.require_bool(fw["retained_all_pairs_compounded"], "fw.rc") is True
        and rmg == Fraction(653951, 283764)
        and fw["retained_min_compounding_gain_dec4"] == engine.dec_from_q(rmg, 4),
        "FW_ALGEBRA_FAIL",
        "Law-3 firewall checks",
    )

    # Parametric scaling rows (K_4, K_6, K_16)
    p_rows = payload["parametric_scaling_summary"]
    engine.require_ok(type(p_rows) is list and len(p_rows) == 3, "PARAM_LEN_FAIL", "3 parametric rows required")
    for idx_p, (exp_n, prow) in enumerate(zip((4, 6, 16), p_rows)):
        pr = _require_exact_dict(prow, _PARAM_ROW_KEYS, f"param[{idx_p}]")
        engine.require_exact_int(pr["n_nodes"], "p.n", lo=exp_n, hi=exp_n)
        engine.require_exact_int(pr["n_edges"], "p.e", lo=engine.comb_k(exp_n, 2), hi=engine.comb_k(exp_n, 2))
        engine.require_exact_int(pr["n_triangles"], "p.t", lo=engine.comb_k(exp_n, 3), hi=engine.comb_k(exp_n, 3))
        engine.require_exact_int(pr["n_tetrahedra"], "p.tet", lo=engine.comb_k(exp_n, 4), hi=engine.comb_k(exp_n, 4))
        engine.require_exact_int(pr["n_five_cells"], "p.c5", lo=engine.comb_k(exp_n, 5), hi=engine.comb_k(exp_n, 5))
        engine.require_ok(
            engine.require_bool(pr["foster_identity_exact"], "p.f") is True
            and engine.require_bool(pr["all_pairs_strictly_compounded"], "p.c") is True
            and engine.require_bool(pr["bianchi_coboundary_zero_all"], "p.b") is True
            and engine.require_bool(pr["hodge_b1_b2_zero_exact"], "p.h0") is True
            and engine.require_bool(pr["hodge1_equals_n_identity"], "p.h1") is True
            and engine.require_bool(pr["signed_is_frustrated"], "p.sf") is True
            and engine.require_bool(pr["kron_r_eff_exact_invariant"], "p.kr") is True
            and engine.require_bool(pr["firewall_zero_flux"], "p.fw") is True
            and pr["balanced_split"] == f"{exp_n // 2}|{exp_n - exp_n // 2}",
            "PARAM_ROW_FAIL",
            f"K_{exp_n}",
        )

        bsc = _require_exact_dict(pr["balanced_silo_cut"], frozenset({"k2", "k3", "k4", "k5"}), f"param[{idx_p}].bsc")
        half = exp_n // 2
        for k_ord in (2, 3, 4, 5):
            kr = _require_exact_dict(bsc[f"k{k_ord}"], frozenset({"total", "destroyed", "destroyed_pct_dec2"}), f"p.k{k_ord}")
            etot = engine.comb_k(exp_n, k_ord)
            edest = 0 if etot == 0 else etot - engine.comb_k(half, k_ord) - engine.comb_k(exp_n - half, k_ord)
            epct = "0.00" if etot == 0 else engine.dec_from_q(Fraction(edest * 100, etot), 2)
            engine.require_exact_int(kr["total"], "pk.tot", lo=etot, hi=etot)
            engine.require_exact_int(kr["destroyed"], "pk.dest", lo=edest, hi=edest)
            engine.require_ok(kr["destroyed_pct_dec2"] == epct, "PARAM_SILO_PCT", f"K_{exp_n}/k{k_ord}")

    # Plugin spec
    ps = _require_exact_dict(payload["aletheia_cli_plugin_spec"], _PLUGIN_KEYS, "plugin_spec")
    engine.require_ok(
        ps["subcommand"] == "mesh"
        and ps["entrypoint"] == "aletheia.mesh:run_mesh_cli"
        and ps["input_schemas"] == [engine.S83_CERT_SCHEMA, engine.MESH_SPEC_SCHEMA]
        and ps["modes"] == ["--analyze", "--parametric", "--check", "--write", "--standalone", "--verify-lean"]
        and engine.require_bool(ps["zero_float_strict"], "ps.zf") is True
        and engine.require_bool(ps["r4_three_mode_deterministic"], "ps.r4") is True
        and ps["node_bounds"] == [engine.MIN_MESH_NODES, engine.MAX_MESH_NODES],
        "PLUGIN_SPEC_FAIL",
        "aletheia_cli_plugin_spec",
    )

    return {
        "secondary_audit_passed": True,
        "lean_theorem_count": thm_n,
        "s83_nodes": n,
        "s83_top_blowup_pair": t3["top_frustration_unlock_pair"],
        "parametric_sizes": [4, 6, 16],
    }


def _verify_static_lean_bundle(track_dir: Path) -> tuple[str, str, str]:
    """Static R10+ Lean source + toolchain + lakefile verification (works with or without lean binary)."""
    tc_raw = read_regular_bytes_capped(track_dir / "lean-toolchain", "lean-toolchain", max_bytes=256)
    try:
        tc_text = tc_raw.decode("utf-8", "strict").strip()
    except UnicodeDecodeError as exc:
        raise engine.MeshError("INVALID_UTF8", "lean-toolchain invalid UTF-8") from exc
    engine.require_ok(tc_text == engine.EXPECTED_LEAN_TOOLCHAIN, "TOOLCHAIN_MISMATCH", "unexpected lean-toolchain")
    lake_raw = read_regular_bytes_capped(track_dir / "lakefile.toml", "lakefile.toml", max_bytes=4096)
    lean_raw = read_regular_bytes_capped(track_dir / "AletheiaMeshEngine.lean", "lean_source", max_bytes=1024 * 1024)
    try:
        lean_src = lean_raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise engine.MeshError("INVALID_UTF8", "Lean source invalid UTF-8") from exc
    static_gate_lean4_source(lean_src)
    return engine.sha256_hex(lean_raw), engine.sha256_hex(tc_raw), engine.sha256_hex(lake_raw)


def verify_certificate_dict(
    cert: Any,
    *,
    full_replay: bool = True,
    track_dir: Path | None = None,
) -> dict[str, Any]:
    engine.require_bool(full_replay, "full_replay")
    engine.require_ok(type(cert) is dict, "INVALID_CERT_TYPE", "certificate must be exact dict")
    engine.validate_strict_json_tree(cert, "certificate")
    _require_exact_dict(cert, _CERT_KEYS, "certificate")
    engine.require_ok(cert["schema_version"] == engine.SCHEMA_VERSION, "SCHEMA_MISMATCH", "cert schema_version")
    engine.require_ok(cert["track_id"] == engine.TRACK_ID, "SCHEMA_MISMATCH", "cert track_id")

    p_sha = engine.require_hex64(cert["payload_sha256"], "payload_sha256")
    c_sha = engine.require_hex64(cert["certificate_sha256"], "certificate_sha256")
    payload = cert["payload"]
    sec_res = secondary_audit_payload(payload)

    recomputed_p = engine.sha256_hex(engine.canonical_json_bytes(payload))
    engine.require_ok(hmac.compare_digest(p_sha, recomputed_p), "PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")
    env = {
        "schema_version": cert["schema_version"],
        "track_id": cert["track_id"],
        "payload_sha256": p_sha,
        "payload": payload,
    }
    recomputed_c = engine.sha256_hex(engine.canonical_json_bytes(env))
    engine.require_ok(hmac.compare_digest(c_sha, recomputed_c), "CERT_SHA_MISMATCH", "certificate_sha256 mismatch")

    replayed = False
    if full_replay:
        root = Path(_THIS_DIR) if track_dir is None else _require_concrete_path(track_dir, "track_dir")
        l_sha, tc_sha, lk_sha = _verify_static_lean_bundle(root)
        expected = engine.build_s88_certificate(
            lean_source_sha256=l_sha,
            toolchain_sha256=tc_sha,
            lakefile_sha256=lk_sha,
        )
        engine.require_ok(
            hmac.compare_digest(engine.canonical_json_bytes(cert), engine.canonical_json_bytes(expected)),
            "FULL_REPLAY_MISMATCH",
            "certificate does not match pure-Z/Q engine replay",
        )
        replayed = True

    return {
        "mode": "check",
        "ok": True,
        "valid": True,
        "full_replay": replayed,
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "secondary_audit": sec_res,
    }


def write_certificate_file(path: Path, *, track_dir: Path | None = None) -> dict[str, Any]:
    root = Path(_THIS_DIR) if track_dir is None else _require_concrete_path(track_dir, "track_dir")
    l_sha, tc_sha, lk_sha = _verify_static_lean_bundle(root)
    cert = engine.build_s88_certificate(
        lean_source_sha256=l_sha,
        toolchain_sha256=tc_sha,
        lakefile_sha256=lk_sha,
    )
    raw = engine.canonical_json_bytes(cert)
    write_regular_bytes_safe(path, raw, "certificate")
    return {
        "mode": "write",
        "ok": True,
        "written": True,
        "bytes": len(raw),
        "file_sha256": engine.sha256_hex(raw),
        "certificate_sha256": cert["certificate_sha256"],
    }


def check_certificate_file(path: Path, *, full_replay: bool = True, track_dir: Path | None = None) -> dict[str, Any]:
    raw = read_regular_bytes_capped(path, "certificate")
    cert = parse_strict_json_bytes(raw, "certificate", require_canonical=True)
    res = verify_certificate_dict(cert, full_replay=full_replay, track_dir=track_dir)
    res["file_sha256"] = engine.sha256_hex(raw)
    return res


def analyze_mesh_file(path: Path) -> dict[str, Any]:
    """Read ANY external S83 certificate or aletheia.mesh.spec.v1 JSON safely and run full analysis."""
    raw = read_regular_bytes_capped(path, "mesh_json")
    obj = parse_strict_json_bytes(raw, "mesh_json", require_canonical=False)
    res = engine.analyze_mesh_full(obj)
    res["input_file_sha256"] = engine.sha256_hex(raw)
    res["mode"] = "analyze"
    res["ok"] = True
    return res


# ---------------------------------------------------------------------------
# Strict CLI Argument Parser & Entrypoint (`aletheia mesh` compatible)
# ---------------------------------------------------------------------------

def _parse_cli_args(argv: Any) -> dict[str, Any]:
    engine.require_ok(type(argv) is list, "INVALID_ARGV", "argv must be exact list")
    mode: str | None = None
    target_val: str | None = None
    want_json = False
    i = 0
    n = len(argv)
    value_flags = ("--check", "--write", "--verify-lean", "--analyze", "--parametric")
    while i < n:
        arg = engine.require_exact_str(argv[i], "argv")
        engine.require_ok("\x00" not in arg, "NUL_BYTE_FORBIDDEN", "NUL byte in argv")
        if arg == "--json":
            engine.require_ok(not want_json, "DUPLICATE_FLAG", "--json repeated")
            want_json = True
            i += 1
        elif arg == "--standalone":
            engine.require_ok(mode is None, "CONFLICTING_MODE", "conflicting mode flags")
            mode = "standalone"
            i += 1
        elif arg in value_flags:
            engine.require_ok(mode is None, "CONFLICTING_MODE", "conflicting mode flags")
            engine.require_ok(i + 1 < n, "MISSING_VALUE_ARG", f"{arg} requires a value")
            val = engine.require_exact_str(argv[i + 1], f"{arg} value")
            engine.require_ok("\x00" not in val, "NUL_BYTE_FORBIDDEN", f"NUL byte in {arg}")
            engine.require_ok(len(val) > 0 and not val.startswith("-"), "INVALID_VALUE_ARG", f"invalid value {val!r}")
            mode = arg[2:]
            target_val = val
            i += 2
        elif "=" in arg:
            flag_name, val = arg.split("=", 1)
            engine.require_ok(flag_name in value_flags, "UNKNOWN_FLAG", f"unsupported flag: {arg!r}")
            engine.require_ok(mode is None, "CONFLICTING_MODE", "conflicting mode flags")
            engine.require_ok(len(val) > 0 and not val.startswith("-"), "INVALID_VALUE_ARG", f"invalid value {val!r}")
            mode = flag_name[2:]
            target_val = val
            i += 1
        else:
            raise engine.MeshError("UNKNOWN_FLAG", f"unsupported flag: {arg!r}")
    return {"mode": mode or "default", "target": target_val, "json": want_json}


def _format_blowup_summary(analysis_wrap: dict[str, Any]) -> str:
    an = analysis_wrap["analysis"]
    t3 = an["t3_auto_blowup_ranker"]
    lines = [
        f"MESH {an['mesh_id']} (N={an['n_nodes']}) analysis_sha256={analysis_wrap['analysis_sha256']}",
        f"TOP_FRUSTRATION_UNLOCK={t3['top_frustration_unlock_pair']} TOP_CONDUCTANCE_UNLOCK={t3['top_conductance_unlock_pair']} PARETO_WALL={t3['pareto_multi_wall_obstruction_detected']}",
    ]
    for row in t3["ranked_unlocks"]:
        lines.append(
            f"  #{row['rank']} {row['pair']} net_frust={row['net_frustrated_delta']:+d} "
            f"(res={row['frustrated_resolved']},mw={row['multi_wall_exposed']}) "
            f"dSumG=+{row['global_schur_conductance_gain_dec4']} dKf=-{row['kirchhoff_reduction_dec4']}"
        )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv: Any = list(sys.argv[1:]) if argv is None else argv
    try:
        opts = _parse_cli_args(raw_argv)
        mode = opts["mode"]
        if mode == "standalone":
            root = Path(_THIS_DIR)
            l_sha, tc_sha, lk_sha = _verify_static_lean_bundle(root)
            cert = engine.build_s88_certificate(
                lean_source_sha256=l_sha,
                toolchain_sha256=tc_sha,
                lakefile_sha256=lk_sha,
            )
            sys.stdout.write(engine.canonical_json_bytes(cert).decode("ascii"))
            return 0
        if mode == "write":
            res = write_certificate_file(Path(opts["target"]))
            if opts["json"]:
                sys.stdout.write(engine.canonical_json_bytes(res).decode("ascii"))
            else:
                sys.stdout.write(f"WROTE {res['file_sha256']}\n")
            return 0
        if mode == "check":
            res = check_certificate_file(Path(opts["target"]), full_replay=True)
            if opts["json"]:
                sys.stdout.write(engine.canonical_json_bytes(res).decode("ascii"))
            else:
                sys.stdout.write(f"OK {res['certificate_sha256']}\n")
            return 0
        if mode == "verify-lean":
            res = verify_lean4_file_live(Path(opts["target"]), enforce_sha256=True)
            if opts["json"]:
                sys.stdout.write(engine.canonical_json_bytes(res).decode("ascii"))
            else:
                sys.stdout.write(f"LEAN_OK {res['theorems_verified']} {res['lean_sha256']}\n")
            return 0
        if mode == "analyze":
            res = analyze_mesh_file(Path(opts["target"]))
            if opts["json"]:
                sys.stdout.write(engine.canonical_json_bytes(res).decode("ascii"))
            else:
                sys.stdout.write(_format_blowup_summary(res))
            return 0
        if mode == "parametric":
            n_val = _parse_bounded_int(opts["target"])
            spec = engine.build_parametric_kn_spec(n_val)
            res = engine.analyze_mesh_full(spec, spectral_steps=8)
            res["mode"] = "parametric"
            res["ok"] = True
            if opts["json"]:
                sys.stdout.write(engine.canonical_json_bytes(res).decode("ascii"))
            else:
                sys.stdout.write(_format_blowup_summary(res))
            return 0
        res = check_certificate_file(Path(_THIS_DIR) / "s88_aletheia_mesh_certificate.json", full_replay=True)
        if opts["json"]:
            sys.stdout.write(engine.canonical_json_bytes(res).decode("ascii"))
        else:
            sys.stdout.write(f"OK {res['certificate_sha256']}\n")
        return 0
    except engine.MeshError as exc:
        err_obj = {"error": True, "code": exc.code, "detail": exc.detail}
        sys.stderr.write(json.dumps(err_obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
