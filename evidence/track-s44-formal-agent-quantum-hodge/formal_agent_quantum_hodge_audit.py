#!/usr/bin/env python3
"""Track S44: Zone-B Hardened CLI, Full Pure-Q Replay & Field-Complete Secondary Audit.

Pure Python 3 standard library: zero floats, zero bare asserts, zero `.isdigit()`, zero mathematical RNG.
Zone-B hardening:
  - Concrete pathlib.Path check + NUL-byte and lone UTF-16 surrogate path refusal
  - Deleted-CWD OSError wrapping -> CWD_UNAVAILABLE (rc=2)
  - Atomic dir_fd PWD walk + per-component openat(O_RDONLY | O_DIRECTORY | O_NOFOLLOW) (zero os.path.islink)
  - Leaf O_RDONLY | O_NOFOLLOW | O_NONBLOCK + fstat S_ISREG + 64 KiB streaming capped reads (max_bytes <= 64 MiB)
  - Atomic write: type(data) is bytes BEFORE dir/temp open -> target lstat (st_nlink > 1 -> HARDLINK_FORBIDDEN)
    -> thread-locked monotonic + CSPRNG (secrets.token_hex(8)) 0o600 O_CREAT|O_EXCL|O_NOFOLLOW|O_NONBLOCK
    temp file in same dir_fd -> bounded 32-attempt EEXIST retry -> os.fsync(tmp_fd)
    -> pre-replace os.fstat(tmp_fd).st_nlink == 1 -> os.replace(..., src_dir_fd=dfd, dst_dir_fd=dfd) -> os.fsync(dfd)
  - Strict manual CLI parser (allow_abbrev=False semantics) rejecting flag-like/empty/abbreviated paths
  - Full pure-Q replay + field-complete strict-nested-key secondary_audit_payload (enforced under full_replay=False)
"""
from __future__ import annotations

import errno
from fractions import Fraction
import hashlib
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

from formal_agent_quantum_hodge_oracle import (
    MAX_INT_BITS,
    MAX_INT_DIGITS,
    MAX_JSON_BYTES,
    SCHEMA_VERSION,
    TRACK_ID,
    _PAYLOAD_KEYS,
    FormalAgentQuantumHodgeError,
    build_standalone_certificate,
    canonical_json_bytes,
    canonical_lean_statement_sha256,
    parse_exact_rational,
    parse_strict_json_text,
    require_exact_bool,
    require_exact_int,
    require_exact_str,
    require_sha256_hex,
    validate_certificate_payload,
)

MAX_ALLOWED_CAP_BYTES = 64 * 1024 * 1024
_READ_CHUNK_BYTES = 65_536
_EXACT_PATH_TYPE = type(Path("."))
_DIR_OPEN_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_TMP_LOCK = threading.Lock()
_TMP_COUNTER = 0


def _next_tmp_name(leaf: str) -> str:
    global _TMP_COUNTER
    with _TMP_LOCK:
        _TMP_COUNTER += 1
        seq = _TMP_COUNTER
    return f".{leaf}.s44tmp.{os.getpid()}.{threading.get_ident()}.{seq}.{secrets.token_hex(8)}"


# ---------------------------------------------------------------------------
# Race-Free Zone-B File I/O (Per-Component dir_fd/openat + Atomic os.replace)
# ---------------------------------------------------------------------------

def _open_dir_chain(anchor: str, parts: Sequence[str]) -> int:
    """Walk directory components atomically via `openat(..., O_DIRECTORY | O_NOFOLLOW)`."""
    try:
        dfd = os.open(anchor, _DIR_OPEN_FLAGS)
    except OSError as exc:
        raise FormalAgentQuantumHodgeError("PATH_STAT_ERROR", f"cannot open anchor dir: {type(exc).__name__}") from exc

    for part in parts:
        try:
            nxt = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
        except OSError as exc:
            os.close(dfd)
            if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                raise FormalAgentQuantumHodgeError("SYMLINK_FORBIDDEN", "symlink or non-dir forbidden in path") from exc
            if exc.errno == errno.ENOENT:
                raise FormalAgentQuantumHodgeError("PATH_NOT_FOUND", "directory component not found") from exc
            raise FormalAgentQuantumHodgeError("PATH_STAT_ERROR", f"cannot traverse dir: {type(exc).__name__}") from exc
        os.close(dfd)
        dfd = nxt
    return dfd


def _check_pwd_no_symlinks() -> None:
    pwd_env = require_exact_str(os.environ.get("PWD", ""), "PWD", non_empty=False)
    if pwd_env.startswith("/"):
        pwd_path = Path(pwd_env)
        pwd_parts = [p for p in pwd_path.parts[1:] if p not in ("", ".")]
        try:
            pwd_fd = _open_dir_chain(pwd_path.anchor, pwd_parts)
        except FormalAgentQuantumHodgeError as exc:
            if exc.code != "PATH_NOT_FOUND":
                raise
        else:
            os.close(pwd_fd)


def _validate_path_and_split(path: Any) -> tuple[str, list[str]]:
    if type(path) is not _EXACT_PATH_TYPE:
        raise FormalAgentQuantumHodgeError("INVALID_PATH_TYPE", "path must be exact pathlib.Path")
    raw_str = require_exact_str(str(path), "path")
    if "\x00" in raw_str:
        raise FormalAgentQuantumHodgeError("INVALID_PATH", "path contains NUL byte")

    if not path.is_absolute():
        try:
            Path.cwd()
        except OSError as exc:
            raise FormalAgentQuantumHodgeError("CWD_UNAVAILABLE", f"cannot resolve cwd: {type(exc).__name__}") from exc
        _check_pwd_no_symlinks()
        rel_parts = [p for p in path.parts if p not in ("", ".")]
        return ".", rel_parts
    abs_parts = [p for p in path.parts[1:] if p not in ("", ".")]
    return path.anchor, abs_parts


def require_safe_path(path: Any) -> Path:
    """Validate path type, CWD/PWD, and atomic `openat` directory chain with zero symlinks."""
    anchor, parts = _validate_path_and_split(path)
    if not parts:
        return path
    dfd = _open_dir_chain(anchor, parts[:-1])
    try:
        try:
            st = os.lstat(parts[-1], dir_fd=dfd)
        except FileNotFoundError:
            return path
        except OSError as exc:
            raise FormalAgentQuantumHodgeError("PATH_STAT_ERROR", f"cannot lstat leaf: {type(exc).__name__}") from exc
        if stat.S_ISLNK(st.st_mode):
            raise FormalAgentQuantumHodgeError("SYMLINK_FORBIDDEN", "symlink forbidden at leaf")
    finally:
        os.close(dfd)
    return path


def _open_leaf_for_read(path: Path) -> int:
    anchor, parts = _validate_path_and_split(path)
    if not parts:
        raise FormalAgentQuantumHodgeError("NON_REGULAR_FILE", "target path refers to a directory")
    dfd = _open_dir_chain(anchor, parts[:-1])
    try:
        try:
            return os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise FormalAgentQuantumHodgeError("SYMLINK_FORBIDDEN", "symlink forbidden at leaf") from exc
            raise FormalAgentQuantumHodgeError("FILE_READ_ERROR", f"cannot open file: {type(exc).__name__}") from exc
    finally:
        os.close(dfd)


def read_regular_bytes_capped(path: Path, max_bytes: Any = MAX_JSON_BYTES) -> bytes:
    """Read regular file bytes via atomic dir_fd + O_NOFOLLOW|O_NONBLOCK in bounded 64 KiB streaming chunks."""
    cap = require_exact_int(max_bytes, "max_bytes", min_val=1, max_val=MAX_ALLOWED_CAP_BYTES)
    fd = _open_leaf_for_read(path)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise FormalAgentQuantumHodgeError("NON_REGULAR_FILE", "target is not a regular file")
        chunks: list[bytes] = []
        total = 0
        while True:
            to_read = min(_READ_CHUNK_BYTES, cap + 1 - total)
            chunk = os.read(fd, to_read)
            if not chunk:
                break
            total += len(chunk)
            if total > cap:
                raise FormalAgentQuantumHodgeError("FILE_TOO_LARGE", f"file exceeds {cap} bytes")
            chunks.append(chunk)
        return b"".join(chunks)
    except FormalAgentQuantumHodgeError:
        raise
    except OSError as exc:
        raise FormalAgentQuantumHodgeError("FILE_READ_ERROR", f"failed reading file: {type(exc).__name__}") from exc
    finally:
        os.close(fd)


def write_regular_file_bytes(path: Path, data: bytes) -> None:
    """Write regular file atomically via 0o600 CSPRNG temp file, fsync, pre-replace st_nlink==1 & os.replace."""
    if type(data) is not bytes:
        raise FormalAgentQuantumHodgeError("INVALID_WRITE_DATA", "data must be exact bytes")
    anchor, parts = _validate_path_and_split(path)
    if not parts:
        raise FormalAgentQuantumHodgeError("NON_REGULAR_FILE", "target path refers to a directory")
    leaf = parts[-1]
    dfd = _open_dir_chain(anchor, parts[:-1])
    try:
        try:
            st = os.lstat(leaf, dir_fd=dfd)
        except FileNotFoundError:
            st = None
        except OSError as exc:
            raise FormalAgentQuantumHodgeError("FILE_WRITE_ERROR", f"cannot lstat target: {type(exc).__name__}") from exc
        if st is not None:
            if stat.S_ISLNK(st.st_mode):
                raise FormalAgentQuantumHodgeError("SYMLINK_FORBIDDEN", "symlink forbidden at leaf")
            if not stat.S_ISREG(st.st_mode):
                raise FormalAgentQuantumHodgeError("NON_REGULAR_FILE", "cannot write to non-regular file")
            if st.st_nlink > 1:
                raise FormalAgentQuantumHodgeError("HARDLINK_FORBIDDEN", "cannot write through hardlinked file")

        tmp_fd: int | None = None
        tmp_name = ""
        for _ in range(32):
            cand = _next_tmp_name(leaf)
            try:
                tmp_fd = os.open(
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
                raise FormalAgentQuantumHodgeError("FILE_WRITE_ERROR", f"cannot create temp file: {type(exc).__name__}") from exc
        if tmp_fd is None:
            raise FormalAgentQuantumHodgeError("TEMP_RETRY_EXHAUSTED", "temp file collision limit exceeded")

        try:
            try:
                view = memoryview(data)
                written = 0
                while written < len(data):
                    written += os.write(tmp_fd, view[written:])
                os.fsync(tmp_fd)
                if os.fstat(tmp_fd).st_nlink != 1:
                    raise FormalAgentQuantumHodgeError("HARDLINK_FORBIDDEN", "temp file link count != 1")
            finally:
                os.close(tmp_fd)
            os.replace(tmp_name, leaf, src_dir_fd=dfd, dst_dir_fd=dfd)
            os.fsync(dfd)
        except FormalAgentQuantumHodgeError:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
            raise
        except OSError as exc:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
            raise FormalAgentQuantumHodgeError("FILE_WRITE_ERROR", f"failed writing file: {type(exc).__name__}") from exc
    finally:
        os.close(dfd)


# ---------------------------------------------------------------------------
# Field-Complete Strict-Nested-Key Secondary Algebraic Cross-Check
# ---------------------------------------------------------------------------

_P1_KEYS = frozenset({
    "case_id",
    "q_exponent",
    "f_monomial_count",
    "f_coeff_sum",
    "cleared_7f_coeff_sum",
    "all_monomials_degree_6",
    "cleared_7f_all_integer_coeffs",
    "substituted_f_monomial_count",
    "substituted_f_odd_s_count",
    "substituted_f_odd_t_count",
    "f_separately_even_in_s_and_t",
    "substituted_a_monomial_count",
    "substituted_a_odd_s_count",
    "substituted_a_odd_t_count",
    "a_separately_even_in_s_and_t",
    "det_tau_x",
    "det_tau_y",
    "det_tau_xy_diagonal",
    "residue_sign_character_neg1_neg1_certified",
    "mod5_nonzero_term_count",
    "mod5_matches_2_sum_sixth_powers",
    "mod5_all_6_partials_2_zk5",
    "mod5_unique_origin_smooth_certified",
    "negative_control_broken_x_parity",
    "negative_control_diagonal_permutation",
    "pillar1_hodge_sextic_certified",
})
_NEG_X_KEYS = frozenset({"odd_s_count", "odd_t_count", "broken_x_parity_rejected"})
_NEG_DIAG_KEYS = frozenset({
    "odd_s_count",
    "odd_t_count",
    "odd_s_plus_t_count",
    "diagonal_only_invariant_yet_breaks_independent_parity",
})
_P2_KEYS = frozenset({
    "cost_model_weights",
    "circuit_a_silq_clean",
    "circuit_b_classical_offload",
    "circuit_c_genuine_speedup",
    "circuit_ac_sequential",
    "apparent_t_only_speedup_b_vs_a",
    "full_cost_ratio_b_over_a",
    "full_cost_ratio_b_over_a_4dp",
    "appears_4x_cheaper_on_t_only",
    "full_cost_reverses_ordering",
    "genuine_speedup_wins_both_models",
    "hoare_sequential_additivity_exact",
    "cs21_offloading_obstruction_certified",
    "deepmind_discoveries_audit",
})
_W_KEYS = frozenset({"w_t", "w_ctrl", "w_landauer"})
_CIRC_KEYS = frozenset({
    "t_gates",
    "classical_ctrl_ops",
    "erased_bits",
    "t_only_cost",
    "classical_ctrl_cost",
    "landauer_erasure_cost",
    "hidden_offloaded_cost",
    "full_boundary_cost",
    "hidden_cost_share",
})
_DM_KEYS = frozenset({
    "total_reported_lean_lines",
    "five_suite_module_sum",
    "five_suite_line_sum",
    "shared_infra_lean_lines",
    "total_lines_accounting_exact",
    "comparator_ram_gb_lo",
    "comparator_ram_gb_hi",
    "comparator_ram_gb_mid",
    "ram_envelope_exceeds_200gb",
    "total_lines_per_gb_at_233",
    "grover_over_arcsin_lines_per_speedup_spread",
    "grover_over_arcsin_spread_2dp",
    "suites",
})
_SUITE_KEYS = frozenset({
    "suite",
    "modules",
    "lean_lines",
    "reported_speedup",
    "lines_per_module",
    "lines_per_speedup_unit",
    "lines_per_speedup_2dp",
    "share_of_total_lines",
})
_P3_KEYS = frozenset({
    "pinned_namespace",
    "pinned_theorem_name",
    "pinned_statement_sha256",
    "forbidden_token_count",
    "positive_controls",
    "adversarial_fixtures",
    "adversarial_fixture_count",
    "all_positive_controls_passed",
    "all_adversarial_fixtures_rejected",
    "pillar3_lean4_envelope_gate_certified",
})
_POS_FIX_KEYS = frozenset({"fixture", "passed", "statement_sha256"})
_ADV_FIX_KEYS = frozenset({"fixture", "expected_error_code", "actual_error_code", "passed"})
_P4_KEYS = frozenset({
    "n0_upstream_anchors",
    "n1_certified_contributions",
    "max_int_bits_exact_cap",
    "max_int_digits_preparse_ceiling",
    "int_bits_3321_exact_cap_not_digit_biconditional",
    "zero_off_pr_internal_audit_tags",
    "cs13_honest_ledger_certified",
})

_EXPECTED_N0 = [
    "hodge-computer/sextics (Ben Diamond / Claire Voisin symmetric sextic involution reduction)",
    "brilliant-hq/pequalnp-proofs (pequalnp.com Lean 4 lemma-leasing fleet)",
    "google-deepmind/formal-quantum-computation (arXiv:2611.09822v3 discoveries & 230-233 GB comparator)",
]
_EXPECTED_N1 = [
    "Pure-Z/Q multivariate sextic expansion, independent (s,t) reflection parity & mod-5 smoothness certifier",
    "CS-21 classical-control & Landauer offloading obstruction theorem + Hoare resource comparator",
    "Nested-comment, char-literal, raw- & interpolated-string Lean 4 proof-envelope static pre-filter (26 adversarial fixtures)",
]
_EXPECTED_PINNED_SHA = canonical_lean_statement_sha256(
    "theorem rank_gap_obstruction (n : Nat) (h : n >= 1) : n + 1 > n"
)


def _require_dict_exact_keys(
    mapping: dict[str, Any],
    key: str,
    expected_keys: frozenset[str],
    err_code: str,
) -> dict[str, Any]:
    val = mapping.get(key)
    if type(val) is not dict or frozenset(val.keys()) != expected_keys:
        raise FormalAgentQuantumHodgeError(err_code, f"missing or invalid object key set: {key}")
    return val


def _require_flag(mapping: dict[str, Any], key: str, expected: bool, err_code: str) -> None:
    if require_exact_bool(mapping.get(key), key) is not expected:
        raise FormalAgentQuantumHodgeError(err_code, f"invariant {key} must be {expected}")


def _require_list_exact_len(val: Any, name: str, expected_len: int, err_code: str) -> list[Any]:
    if type(val) is not list or len(val) != expected_len:
        raise FormalAgentQuantumHodgeError(err_code, f"{name} must be list of length {expected_len}")
    return val


def _require_str_list(val: Any, name: str, expected_len: int, err_code: str) -> list[str]:
    items = _require_list_exact_len(val, name, expected_len, err_code)
    return [require_exact_str(item, f"{name}[{i}]") for i, item in enumerate(items)]


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Fail-closed field-complete secondary algebraic invariant cross-check over all four Track S44 pillars."""
    if type(payload) is not dict or frozenset(payload.keys()) != _PAYLOAD_KEYS:
        raise FormalAgentQuantumHodgeError("AUDIT_PAYLOAD_TYPE", "payload must be dict with exact Track S44 keys")
    if (payload["novelty_tier"], payload["oracle_class"]) != ("N1", "exact"):
        raise FormalAgentQuantumHodgeError("AUDIT_META", "unexpected novelty_tier or oracle_class")
    for key in (
        "measured_live_lean4_kernel_execution",
        "measured_live_deepmind_230gb_comparator",
        "measured_live_pequalnp_desk_submission",
    ):
        _require_flag(payload, key, False, "AUDIT_LAW4_FLAG")
    for key in ("zero_trust_path_floats", "zero_bare_asserts", "zero_mathematical_rng"):
        _require_flag(payload, key, True, "AUDIT_HYGIENE_FLAG")

    # Pillar 1: Hodge Symmetric Sextic
    p1 = _require_dict_exact_keys(payload, "pillar1_hodge_symmetric_sextic", _P1_KEYS, "AUDIT_P1_MISSING")
    for fk in (
        "all_monomials_degree_6",
        "cleared_7f_all_integer_coeffs",
        "f_separately_even_in_s_and_t",
        "a_separately_even_in_s_and_t",
        "residue_sign_character_neg1_neg1_certified",
        "mod5_matches_2_sum_sixth_powers",
        "mod5_all_6_partials_2_zk5",
        "mod5_unique_origin_smooth_certified",
        "pillar1_hodge_sextic_certified",
    ):
        _require_flag(p1, fk, True, "AUDIT_P1_FLAG")
    f_sum = parse_exact_rational(p1["f_coeff_sum"], "p1.f_coeff_sum")
    f7_sum = require_exact_int(p1["cleared_7f_coeff_sum"], "p1.cleared_7f_coeff_sum")
    if (
        require_exact_str(p1["case_id"], "p1.case_id"),
        require_exact_int(p1["q_exponent"], "p1.q"),
        require_exact_int(p1["f_monomial_count"], "p1.f_cnt"),
        f_sum,
        f7_sum,
        f_sum * 7 == f7_sum,
        require_exact_int(p1["substituted_f_monomial_count"], "p1.fs_cnt"),
        require_exact_int(p1["substituted_f_odd_s_count"], "p1.fs_os"),
        require_exact_int(p1["substituted_f_odd_t_count"], "p1.fs_ot"),
        require_exact_int(p1["substituted_a_monomial_count"], "p1.as_cnt"),
        require_exact_int(p1["substituted_a_odd_s_count"], "p1.as_os"),
        require_exact_int(p1["substituted_a_odd_t_count"], "p1.as_ot"),
        require_exact_int(p1["det_tau_x"], "p1.dtx"),
        require_exact_int(p1["det_tau_y"], "p1.dty"),
        require_exact_int(p1["det_tau_xy_diagonal"], "p1.dtd"),
        require_exact_int(p1["mod5_nonzero_term_count"], "p1.m5"),
    ) != (
        "symmetric-sextic-residual", 1, 42, Fraction(447, 7), 447, True,
        46, 0, 0, 4, 0, 0, -1, -1, 1, 6,
    ):
        raise FormalAgentQuantumHodgeError("AUDIT_P1_VAL", "Hodge sextic exact invariants mismatch")

    neg_x = _require_dict_exact_keys(p1, "negative_control_broken_x_parity", _NEG_X_KEYS, "AUDIT_P1_NEGX")
    _require_flag(neg_x, "broken_x_parity_rejected", True, "AUDIT_P1_NEGX")
    if (require_exact_int(neg_x["odd_s_count"], "nx.os"), require_exact_int(neg_x["odd_t_count"], "nx.ot")) != (2, 0):
        raise FormalAgentQuantumHodgeError("AUDIT_P1_NEGX_VAL", "broken X-parity negative control mismatch")

    neg_d = _require_dict_exact_keys(p1, "negative_control_diagonal_permutation", _NEG_DIAG_KEYS, "AUDIT_P1_NEGD")
    _require_flag(neg_d, "diagonal_only_invariant_yet_breaks_independent_parity", True, "AUDIT_P1_NEGD")
    if (
        require_exact_int(neg_d["odd_s_count"], "nd.os"),
        require_exact_int(neg_d["odd_t_count"], "nd.ot"),
        require_exact_int(neg_d["odd_s_plus_t_count"], "nd.ost"),
    ) != (4, 4, 0):
        raise FormalAgentQuantumHodgeError("AUDIT_P1_NEGD_VAL", "diagonal-permutation negative control mismatch")

    # Pillar 2: DeepMind Quantum CS-21 Costing & Discoveries Audit
    p2 = _require_dict_exact_keys(payload, "pillar2_deepmind_quantum_cs21_costing", _P2_KEYS, "AUDIT_P2_MISSING")
    for fk in (
        "appears_4x_cheaper_on_t_only",
        "full_cost_reverses_ordering",
        "genuine_speedup_wins_both_models",
        "hoare_sequential_additivity_exact",
        "cs21_offloading_obstruction_certified",
    ):
        _require_flag(p2, fk, True, "AUDIT_P2_FLAG")

    ws = _require_dict_exact_keys(p2, "cost_model_weights", _W_KEYS, "AUDIT_P2_W")
    if (
        parse_exact_rational(ws["w_t"], "w_t"),
        parse_exact_rational(ws["w_ctrl"], "w_ctrl"),
        parse_exact_rational(ws["w_landauer"], "w_land"),
    ) != (Fraction(1, 1), Fraction(1, 10), Fraction(1, 2)):
        raise FormalAgentQuantumHodgeError("AUDIT_P2_W_VAL", "cost model weights mismatch")

    circ_specs = (
        ("circuit_a_silq_clean", 400, 10, 0, Fraction(400, 1), Fraction(1, 1), Fraction(0, 1), Fraction(1, 1), Fraction(401, 1), Fraction(1, 401)),
        ("circuit_b_classical_offload", 100, 4000, 200, Fraction(100, 1), Fraction(400, 1), Fraction(100, 1), Fraction(500, 1), Fraction(600, 1), Fraction(5, 6)),
        ("circuit_c_genuine_speedup", 100, 20, 0, Fraction(100, 1), Fraction(2, 1), Fraction(0, 1), Fraction(2, 1), Fraction(102, 1), Fraction(1, 51)),
        ("circuit_ac_sequential", 500, 30, 0, Fraction(500, 1), Fraction(3, 1), Fraction(0, 1), Fraction(3, 1), Fraction(503, 1), Fraction(3, 503)),
    )
    for ck, *exp_c in circ_specs:
        cd = _require_dict_exact_keys(p2, ck, _CIRC_KEYS, "AUDIT_P2_CIRC")
        t_c = parse_exact_rational(cd["t_only_cost"], f"{ck}.t")
        k_c = parse_exact_rational(cd["classical_ctrl_cost"], f"{ck}.k")
        l_c = parse_exact_rational(cd["landauer_erasure_cost"], f"{ck}.l")
        h_c = parse_exact_rational(cd["hidden_offloaded_cost"], f"{ck}.h")
        f_c = parse_exact_rational(cd["full_boundary_cost"], f"{ck}.f")
        s_c = parse_exact_rational(cd["hidden_cost_share"], f"{ck}.s")
        if (
            require_exact_int(cd["t_gates"], f"{ck}.tg"),
            require_exact_int(cd["classical_ctrl_ops"], f"{ck}.kc"),
            require_exact_int(cd["erased_bits"], f"{ck}.eb"),
            t_c, k_c, l_c, h_c, f_c, s_c,
            h_c == k_c + l_c,
            f_c == t_c + h_c,
            s_c * f_c == h_c,
        ) != (*exp_c, True, True, True):
            raise FormalAgentQuantumHodgeError("AUDIT_P2_CIRC_VAL", f"{ck} resource triple mismatch")

    if (
        parse_exact_rational(p2["apparent_t_only_speedup_b_vs_a"], "p2.app"),
        parse_exact_rational(p2["full_cost_ratio_b_over_a"], "p2.rat"),
        require_exact_str(p2["full_cost_ratio_b_over_a_4dp"], "p2.4dp"),
    ) != (Fraction(4, 1), Fraction(600, 401), "1.4962"):
        raise FormalAgentQuantumHodgeError("AUDIT_P2_RATIO", "CS-21 cost-flip ratios mismatch")

    dm = _require_dict_exact_keys(p2, "deepmind_discoveries_audit", _DM_KEYS, "AUDIT_P2_DM")
    for fk in ("total_lines_accounting_exact", "ram_envelope_exceeds_200gb"):
        _require_flag(dm, fk, True, "AUDIT_P2_DM_FLAG")
    if (
        require_exact_int(dm["total_reported_lean_lines"], "dm.tot"),
        require_exact_int(dm["five_suite_module_sum"], "dm.mods"),
        require_exact_int(dm["five_suite_line_sum"], "dm.lines"),
        require_exact_int(dm["shared_infra_lean_lines"], "dm.infra"),
        require_exact_int(dm["comparator_ram_gb_lo"], "dm.rlo"),
        require_exact_int(dm["comparator_ram_gb_hi"], "dm.rhi"),
        parse_exact_rational(dm["comparator_ram_gb_mid"], "dm.rmid"),
        parse_exact_rational(dm["total_lines_per_gb_at_233"], "dm.lpg"),
        parse_exact_rational(dm["grover_over_arcsin_lines_per_speedup_spread"], "dm.spr"),
        require_exact_str(dm["grover_over_arcsin_spread_2dp"], "dm.spr2"),
    ) != (
        1_433_602, 626, 1_430_893, 2_709, 230, 233, Fraction(463, 2),
        Fraction(1_433_602, 233), Fraction(554_952 * 100 * 290, 257 * 22_335), "2803.71",
    ):
        raise FormalAgentQuantumHodgeError("AUDIT_P2_DM_VAL", "DeepMind discoveries summary mismatch")

    suites = _require_list_exact_len(dm["suites"], "dm.suites", 5, "AUDIT_P2_SUITES")
    suite_exp = (
        ("GroverFindAll", 200, 554_952, Fraction(257, 100), Fraction(554_952, 200), Fraction(554_952 * 100, 257), "215934.63", Fraction(554_952, 1_433_602)),
        ("ArcSin", 16, 22_335, Fraction(290, 1), Fraction(22_335, 16), Fraction(22_335, 290), "77.01", Fraction(22_335, 1_433_602)),
        ("StoppingPower", 176, 457_154, Fraction(12, 1), Fraction(457_154, 176), Fraction(457_154, 12), "38096.16", Fraction(457_154, 1_433_602)),
        ("Photochemistry", 74, 196_621, Fraction(8, 1), Fraction(196_621, 74), Fraction(196_621, 8), "24577.62", Fraction(196_621, 1_433_602)),
        ("P450", 160, 199_831, Fraction(5, 2), Fraction(199_831, 160), Fraction(199_831 * 2, 5), "79932.40", Fraction(199_831, 1_433_602)),
    )
    for idx, item in enumerate(suites):
        if type(item) is not dict or frozenset(item.keys()) != _SUITE_KEYS:
            raise FormalAgentQuantumHodgeError("AUDIT_P2_SUITES", "suite entry must have exact keys")
        if (
            require_exact_str(item["suite"], "s.name"),
            require_exact_int(item["modules"], "s.mods"),
            require_exact_int(item["lean_lines"], "s.lines"),
            parse_exact_rational(item["reported_speedup"], "s.sp"),
            parse_exact_rational(item["lines_per_module"], "s.lpm"),
            parse_exact_rational(item["lines_per_speedup_unit"], "s.lps"),
            require_exact_str(item["lines_per_speedup_2dp"], "s.lps2"),
            parse_exact_rational(item["share_of_total_lines"], "s.sh"),
        ) != suite_exp[idx]:
            raise FormalAgentQuantumHodgeError("AUDIT_P2_SUITE_VAL", f"suite[{idx}] values mismatch")

    # Pillar 3: Lean 4 Proof-Envelope & Statement-Drift Static Pre-Filter
    p3 = _require_dict_exact_keys(payload, "pillar3_lean4_proof_envelope_gate", _P3_KEYS, "AUDIT_P3_MISSING")
    for fk in (
        "all_positive_controls_passed",
        "all_adversarial_fixtures_rejected",
        "pillar3_lean4_envelope_gate_certified",
    ):
        _require_flag(p3, fk, True, "AUDIT_P3_FLAG")
    if (
        require_exact_str(p3["pinned_namespace"], "p3.ns"),
        require_exact_str(p3["pinned_theorem_name"], "p3.thm"),
        require_sha256_hex(p3["pinned_statement_sha256"], "p3.sha"),
        require_exact_int(p3["forbidden_token_count"], "p3.ftc"),
        require_exact_int(p3["adversarial_fixture_count"], "p3.afc"),
    ) != ("PEqualNP.Outside.lem_042", "rank_gap_obstruction", _EXPECTED_PINNED_SHA, 14, 26):
        raise FormalAgentQuantumHodgeError("AUDIT_P3_META", "Lean 4 envelope metadata mismatch")

    pos_list = _require_list_exact_len(p3["positive_controls"], "p3.pos", 5, "AUDIT_P3_POS")
    pos_exp = (
        "valid_clean_proof",
        "valid_nested_comments_and_strings",
        "valid_raw_string_with_quotes_and_tokens",
        "valid_char_literal_double_quote",
        "valid_interpolated_string_benign",
    )
    for idx, item in enumerate(pos_list):
        if type(item) is not dict or frozenset(item.keys()) != _POS_FIX_KEYS:
            raise FormalAgentQuantumHodgeError("AUDIT_P3_POS", "positive control must have exact keys")
        _require_flag(item, "passed", True, "AUDIT_P3_POS")
        if (
            require_exact_str(item["fixture"], "pos.fix"),
            require_sha256_hex(item["statement_sha256"], "pos.sha"),
        ) != (pos_exp[idx], _EXPECTED_PINNED_SHA):
            raise FormalAgentQuantumHodgeError("AUDIT_P3_POS_VAL", f"positive control[{idx}] mismatch")

    adv_list = _require_list_exact_len(p3["adversarial_fixtures"], "p3.adv", 26, "AUDIT_P3_ADV")
    adv_exp = (
        ("adv_01_sorry", "FORBIDDEN_TOKEN"),
        ("adv_02_admit", "FORBIDDEN_TOKEN"),
        ("adv_03_axiom", "FORBIDDEN_TOKEN"),
        ("adv_04_native_decide", "FORBIDDEN_TOKEN"),
        ("adv_05_implemented_by", "FORBIDDEN_TOKEN"),
        ("adv_06_extern", "FORBIDDEN_TOKEN"),
        ("adv_07_set_option_skip_kernel_tc", "FORBIDDEN_TOKEN"),
        ("adv_08_unsafe", "FORBIDDEN_TOKEN"),
        ("adv_09_decide_plus_native", "FORBIDDEN_TOKEN"),
        ("adv_10_lean_of_reduce_bool", "FORBIDDEN_TOKEN"),
        ("adv_11_opaque_extern", "FORBIDDEN_TOKEN"),
        ("adv_12_raw_string_backslash_sorry", "FORBIDDEN_TOKEN"),
        ("adv_13_raw_hash_string_backslash_sorry", "FORBIDDEN_TOKEN"),
        ("adv_14_statement_drift_true_conclusion", "STATEMENT_DRIFT"),
        ("adv_15_statement_drift_weakened_hyp", "STATEMENT_DRIFT"),
        ("adv_16_wrong_namespace", "INVALID_NAMESPACE"),
        ("adv_17_hidden_token_after_nested_comment", "FORBIDDEN_TOKEN"),
        ("adv_18_char_literal_quote_sorry", "FORBIDDEN_TOKEN"),
        ("adv_19_interp_string_s_sorry", "FORBIDDEN_TOKEN"),
        ("adv_20_interp_string_m_admit", "FORBIDDEN_TOKEN"),
        ("adv_21_sorry_ax", "FORBIDDEN_TOKEN"),
        ("adv_22_constant_decl", "FORBIDDEN_TOKEN"),
        ("adv_23_elab_macro", "FORBIDDEN_TOKEN"),
        ("adv_24_lean_meta_mk_sorry", "FORBIDDEN_TOKEN"),
        ("adv_25_decide_minus_flag_native", "FORBIDDEN_TOKEN"),
        ("adv_26_decide_config_native_true", "FORBIDDEN_TOKEN"),
    )
    for idx, item in enumerate(adv_list):
        if type(item) is not dict or frozenset(item.keys()) != _ADV_FIX_KEYS:
            raise FormalAgentQuantumHodgeError("AUDIT_P3_ADV", "adversarial fixture must have exact keys")
        _require_flag(item, "passed", True, "AUDIT_P3_ADV")
        if (
            require_exact_str(item["fixture"], "adv.fix"),
            require_exact_str(item["expected_error_code"], "adv.exp"),
            require_exact_str(item["actual_error_code"], "adv.act"),
        ) != (adv_exp[idx][0], adv_exp[idx][1], adv_exp[idx][1]):
            raise FormalAgentQuantumHodgeError("AUDIT_P3_ADV_VAL", f"adversarial fixture[{idx}] mismatch")

    # Pillar 4: CS-13 Honest Scope Ledger
    p4 = _require_dict_exact_keys(payload, "pillar4_cs13_honest_scope_ledger", _P4_KEYS, "AUDIT_P4_MISSING")
    for fk in (
        "int_bits_3321_exact_cap_not_digit_biconditional",
        "zero_off_pr_internal_audit_tags",
        "cs13_honest_ledger_certified",
    ):
        _require_flag(p4, fk, True, "AUDIT_P4_FLAG")
    if (
        _require_str_list(p4["n0_upstream_anchors"], "p4.n0", 3, "AUDIT_P4_VAL"),
        _require_str_list(p4["n1_certified_contributions"], "p4.n1", 3, "AUDIT_P4_VAL"),
        require_exact_int(p4["max_int_bits_exact_cap"], "p4.bits"),
        require_exact_int(p4["max_int_digits_preparse_ceiling"], "p4.digs"),
    ) != (_EXPECTED_N0, _EXPECTED_N1, MAX_INT_BITS, MAX_INT_DIGITS):
        raise FormalAgentQuantumHodgeError("AUDIT_P4_VAL", "CS-13 honest scope ledger mismatch")

    return {
        "secondary_audit_passed": True,
        "pillars_audited": 4,
        "deepmind_suites_audited": 5,
        "lean4_adversarial_fixtures_audited": 26,
    }


def verify_certificate_dict(cert: Any, *, full_replay: bool = True) -> dict[str, Any]:
    """Validate an in-memory certificate dict with digests, schema, secondary audit & optional full replay."""
    res = validate_certificate_payload(cert, full_replay=full_replay)
    sec = secondary_audit_payload(cert["payload"])
    res["secondary_audit"] = sec
    return res


def check_certificate_file(path: Path) -> dict[str, Any]:
    raw = read_regular_bytes_capped(path, MAX_JSON_BYTES)
    if b"\r" in raw:
        raise FormalAgentQuantumHodgeError("CRLF_FORBIDDEN", "CRLF line endings forbidden in certificate")
    if not raw.endswith(b"\n"):
        raise FormalAgentQuantumHodgeError("MISSING_TRAILING_LF", "certificate must end with a single LF")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FormalAgentQuantumHodgeError("INVALID_UTF8", "certificate is not valid UTF-8") from exc
    cert = parse_strict_json_text(text, require_object=True)
    canonical_raw = canonical_json_bytes(cert)
    if raw != canonical_raw + b"\n":
        raise FormalAgentQuantumHodgeError("NON_CANONICAL_BYTES", "certificate bytes are not canonical ASCII JSON + LF")
    res = verify_certificate_dict(cert, full_replay=True)
    res["canonical_sha256"] = hashlib.sha256(canonical_raw).hexdigest()
    res["file_sha256"] = hashlib.sha256(raw).hexdigest()
    return res


def write_certificate_file(path: Path) -> dict[str, Any]:
    cert = build_standalone_certificate()
    canonical_raw = canonical_json_bytes(cert)
    raw = canonical_raw + b"\n"
    write_regular_file_bytes(path, raw)
    return {
        "written": True,
        "schema": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": cert["payload_sha256"],
        "certificate_sha256": cert["certificate_sha256"],
        "file_sha256": hashlib.sha256(raw).hexdigest(),
    }


# ---------------------------------------------------------------------------
# Strict Fail-Closed Manual CLI Parsing (allow_abbrev=False Semantics)
# ---------------------------------------------------------------------------

def _parse_cli_argv(argv: Sequence[str]) -> tuple[str, Path | None, bool]:
    if type(argv) not in (list, tuple):
        raise FormalAgentQuantumHodgeError("INVALID_ARGV", "argv must be exact list/tuple of strict str")
    for item in argv:
        require_exact_str(item, "argv_item", non_empty=False)

    mode: str | None = None
    target: Path | None = None
    as_json = False
    i = 0
    n = len(argv)
    while i < n:
        tok = argv[i]
        if tok == "--json":
            if as_json:
                raise FormalAgentQuantumHodgeError("DUPLICATE_FLAG", "duplicate --json flag")
            as_json = True
            i += 1
        elif tok == "--standalone":
            if mode is not None:
                raise FormalAgentQuantumHodgeError("CONFLICTING_MODE", "multiple mode flags forbidden")
            mode = "standalone"
            i += 1
        elif tok in ("--check", "--write"):
            if mode is not None:
                raise FormalAgentQuantumHodgeError("CONFLICTING_MODE", "multiple mode flags forbidden")
            if i + 1 >= n:
                raise FormalAgentQuantumHodgeError("MISSING_PATH_ARG", f"{tok} requires a path argument")
            val = argv[i + 1]
            if not val or val.startswith("-"):
                raise FormalAgentQuantumHodgeError("INVALID_PATH_ARG", f"{tok} path cannot be empty or flag-like")
            mode = "check" if tok == "--check" else "write"
            target = Path(val)
            i += 2
        else:
            raise FormalAgentQuantumHodgeError("UNKNOWN_FLAG", f"unrecognized CLI argument: {tok}")

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
    except FormalAgentQuantumHodgeError as exc:
        err = {"valid": False, "error_code": exc.code, "error_message": exc.message}
        sys.stderr.write(canonical_json_bytes(err).decode("ascii") + "\n")
        return 2

    if as_json:
        sys.stdout.write(canonical_json_bytes(out).decode("ascii") + "\n")
    else:
        sys.stdout.write(
            f"OK {SCHEMA_VERSION} payload_sha256={out['payload_sha256']} "
            f"certificate_sha256={out['certificate_sha256']}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
