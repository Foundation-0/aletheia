#!/usr/bin/env python3
"""Track S38 (Portal 36): Zone-B Hardened CLI, Deterministic Replay & Secondary Algebraic Auditor.

Zero external dependencies, zero AST floats, zero float() calls, zero bare
asserts, zero .isdigit(), zero mathematical RNG (secrets.token_hex(8) used
solely for collision-free atomic temp file naming under concurrent writers).

Provides full pure-Q deterministic replay and secondary algebraic cross-checking
with atomic per-component dir_fd (openat + O_NOFOLLOW | O_DIRECTORY) traversal,
dir_fd PWD symlink check, 65536-byte streaming capped reads, locked + random +
bounded EEXIST retry 0o600 atomic writes with os.fsync(tmp_fd), pre-replace
fstat(tmp_fd).st_nlink == 1 guard, target st_nlink <= 1 check, os.replace(...,
dir_fd), directory os.fsync(dfd), deleted-CWD CWD_UNAVAILABLE handling, lone
UTF-16 surrogate rejection, and strict zero-abbreviation CLI parsing.
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

from silq_boundary_calculus_oracle import (
    HARD_MAX_BYTES_CAP,
    MAX_JSON_BYTES,
    SCHEMA_VERSION,
    SilqBoundaryError,
    TRACK_ID,
    _qsqrt2_nonneg,
    build_standalone_certificate,
    canonical_json_bytes,
    format_decimal_trunc,
    parse_exact_rational,
    parse_strict_json_text,
    require_bool,
    require_int,
    validate_certificate_payload,
)

_EXACT_PATH_TYPE = type(Path("."))
_READ_CHUNK_BYTES = 65536
_TMP_LOCK = threading.Lock()
_TMP_COUNTER = 0
_TMP_MAX_ATTEMPTS = 32
_EXPECTED_GROUP_RELATIONS = frozenset({
    "CCX2_eq_I",
    "CNOT2_eq_I",
    "CZ2_eq_I",
    "H2_eq_I",
    "HXH_eq_Z",
    "HZH_eq_X",
    "IH_CNOT_IH_eq_CZ",
    "S2_eq_Z",
    "T2_eq_S",
    "T4_eq_Z",
    "T8_eq_I",
    "X2_eq_I",
    "Y2_eq_I",
    "Z2_eq_I",
})
_EXPECTED_BORN_VECTORS: dict[str, list[list[str]]] = {
    "bell_pair": [["1/2", "0"], ["0", "0"], ["0", "0"], ["1/2", "0"]],
    "magic_HTH_ket0": [["1/2", "1/4"], ["1/2", "-1/4"]],
    "ghz_3q": [["1/2", "0"], ["0", "0"], ["0", "0"], ["0", "0"], ["0", "0"], ["0", "0"], ["0", "0"], ["1/2", "0"]],
    "toffoli_superposed": [["1/4", "0"], ["0", "0"], ["1/4", "0"], ["0", "0"], ["1/4", "0"], ["0", "0"], ["0", "0"], ["1/4", "0"]],
}
_EXPECTED_RING_REPR = "a + b*sqrt(2) + i*(c + d*sqrt(2)), (a,b,c,d) in D^4"
_EXPECTED_LITERATURE_ANCHORS = [
    "Bichsel, Baader, Gehr, Vechev (PLDI 2020): Silq High-Level Quantum Language",
    "Landauer (IBM J. Res. Dev. 1961): Irreversibility and Heat Generation",
]
_EXPECTED_VALID_PROGRAMS: dict[str, tuple[str, list[str], list[str]]] = {
    "bell_pair_mfree": ("mfree", ["B", "B"], []),
    "deutsch_jozsa_kickback_mfree": ("mfree", ["B", "B"], []),
    "toffoli_lifted_auto_uncompute": ("mfree", [], ["CCX(a,b,tmp)"]),
    "grover_2q_diffusion_mfree": ("mfree", ["B", "B"], []),
    "observe_4d_slice_explicit_measure": ("general", ["B", "!B"], []),
    "classical_dup_and_lifted_oracle": ("lifted", ["B"], []),
}
_EXPECTED_MUST_FAIL_PROGRAMS: dict[str, tuple[str, str, str]] = {
    "fail_silent_drop_entangled_H": (
        "general",
        "UNCONSUMED_QUANTUM_DROP",
        "silent drop of non-uncomputable quantum variable H",
    ),
    "fail_clone_quantum_wire": (
        "mfree",
        "QUANTUM_CLONING_FORBIDDEN",
        "cannot clone linear quantum variable q: B",
    ),
    "fail_H_inside_qfree": (
        "qfree",
        "NON_QFREE_OP_IN_QFREE",
        "gate H forbidden inside qfree function",
    ),
    "fail_measure_inside_mfree": (
        "mfree",
        "MEASURE_IN_MFREE_OR_QFREE",
        "measure forbidden inside mfree function",
    ),
    "fail_forget_after_dep_mutated": (
        "mfree",
        "UNCOMPUTATION_FAILED",
        "cannot uncompute tmp (not lifted or dependency mutated)",
    ),
    "fail_modify_const_param": (
        "qfree",
        "CONST_MODIFICATION_FORBIDDEN",
        "cannot mutate const parameter a with X",
    ),
    "fail_nonconst_param_in_lifted": (
        "lifted",
        "LIFTED_REQUIRES_CONST_QPARAMS",
        "lifted param a: B must be const",
    ),
}
_P1_KEYS = frozenset({
    "ring_representation",
    "gate_certifications",
    "all_gates_unitary_and_dyadic",
    "group_relations_verified",
    "all_group_relations_verified",
    "born_witnesses",
    "all_witnesses_unit_norm",
    "must_fail_non_unitary_rejected",
    "pillar_verified",
})
_P1_GATE_KEYS = frozenset({"gate", "dim", "is_unitary", "is_dyadic"})
_P1_BORN_KEYS = frozenset({"born_probs_qsqrt2", "sum_q", "sum_sqrt2", "born_sum_is_one", "all_born_nonneg", "all_dyadic"})
_P2_KEYS = frozenset({
    "valid_program_count",
    "valid_programs",
    "all_valid_accepted",
    "must_fail_program_count",
    "must_fail_programs",
    "all_must_fail_rejected",
    "pillar_verified",
})
_P2_VALID_KEYS = frozenset({
    "name",
    "annotation",
    "well_typed",
    "return_types",
    "synthesized_uncomputations",
    "type_error_code",
    "type_error_detail",
})
_P2_FAIL_KEYS = frozenset({
    "name",
    "annotation",
    "well_typed",
    "expected_error_code",
    "type_error_code",
    "type_error_detail",
    "synthesized_uncomputations",
})
_P3_KEYS = frozenset({
    "deutsch_jozsa_uncomputed_clean",
    "deutsch_jozsa_dropped_garbage",
    "toffoli_grover_uncomputed_clean",
    "toffoli_grover_dropped_garbage",
    "purity_strictly_dropped",
    "pillar_verified",
})
_P3_CLEAN_KEYS = frozenset({
    "dim",
    "hermitian",
    "trace_is_one",
    "purity_Tr_rho_sq",
    "linear_entropy_S_L",
    "purity_imag_and_sqrt2_zero",
    "diagonal_probabilities",
    "interference_preserved",
})
_P3_GARBAGE_KEYS = frozenset({
    "dim",
    "hermitian",
    "trace_is_one",
    "purity_Tr_rho_sq",
    "linear_entropy_S_L",
    "purity_imag_and_sqrt2_zero",
    "diagonal_probabilities",
    "interference_destroyed",
})
_P4_KEYS = frozenset({
    "irreversible_and_2_to_1",
    "irreversible_reset_1_to_1",
    "reversible_toffoli_3_to_3",
    "nested_simulation_table_n1_to_n20",
    "overhead_strictly_increasing_from_n2",
    "algebraic_group_isomorphic_l0_l2",
    "pillar_verified",
})
_P4_AND_KEYS = frozenset({
    "n_in_bits",
    "n_out_bits",
    "input_state_count",
    "distinct_output_count",
    "max_fiber_size",
    "fiber_sizes",
    "is_bijection",
    "involution_verified",
    "two_pow_N_H_X_given_Y",
    "landauer_erasure_lower_bound_bits",
    "landauer_erasure_upper_bound_bits",
    "erasure_bracket_verified",
})
_P4_BASE_MAP_KEYS = frozenset({
    "n_in_bits",
    "n_out_bits",
    "input_state_count",
    "distinct_output_count",
    "max_fiber_size",
    "fiber_sizes",
    "is_bijection",
    "involution_verified",
    "two_pow_N_H_X_given_Y",
})
_P4_SIM_ROW_KEYS = frozenset({
    "n_qubits",
    "hilbert_dim_2n",
    "cyclotomic_q_components_4x2n",
    "density_matrix_entries_4n",
    "overhead_2n_over_n",
    "overhead_decimal_trunc2",
})


# ---------------------------------------------------------------------------
# Zone-B Hardened Atomic dir_fd File I/O (TOCTOU, PWD, Hardlinks, Surrogates)
# ---------------------------------------------------------------------------

def _require_utf8_str(raw: str, label: str) -> str:
    try:
        raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise SilqBoundaryError("INVALID_UTF8_SURROGATE", f"{label} contains lone UTF-16 surrogate") from exc
    return raw


def _step_dir_fd_chain(start_fd: int, components: Sequence[str], label: str) -> int:
    """Atomically traverse directory components via openat(O_RDONLY|O_DIRECTORY|O_NOFOLLOW)."""
    dfd = start_fd
    for comp in components:
        try:
            nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dfd)
        except OSError as exc:
            if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                try:
                    is_sym = stat.S_ISLNK(os.lstat(comp, dir_fd=dfd).st_mode)
                except OSError:
                    is_sym = True
                os.close(dfd)
                if is_sym:
                    raise SilqBoundaryError("SYMLINK_FORBIDDEN", f"symlink forbidden at {label}") from exc
                raise SilqBoundaryError("PATH_STAT_ERROR", f"non-directory ancestor at {label}") from exc
            os.close(dfd)
            raise SilqBoundaryError("FILE_IO_ERROR", f"cannot traverse {label}: {type(exc).__name__}") from exc
        os.close(dfd)
        dfd = nxt
    return dfd


def _check_pwd_no_symlinks() -> None:
    pwd_env = os.environ.get("PWD")
    if not pwd_env or not pwd_env.startswith("/"):
        return
    _require_utf8_str(pwd_env, "PWD")
    pwd_parts = [p for p in Path(pwd_env).parts[1:] if p not in ("", ".")]
    try:
        root_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    except OSError as exc:
        raise SilqBoundaryError("CWD_UNAVAILABLE", f"cannot open root: {type(exc).__name__}") from exc
    end_fd = _step_dir_fd_chain(root_fd, pwd_parts, "pwd_ancestor")
    os.close(end_fd)


def _open_parent_dir_fd(path: Any) -> tuple[int, str]:
    """Validate exact Path and atomically pin parent dir_fd against TOCTOU swaps."""
    if type(path) is not _EXACT_PATH_TYPE:
        raise SilqBoundaryError("INVALID_PATH_TYPE", "path must be exact pathlib.Path")
    raw_str = str(path)
    if "\x00" in raw_str:
        raise SilqBoundaryError("INVALID_PATH", "path contains NUL byte")
    _require_utf8_str(raw_str, "path")

    if path.is_absolute():
        raw_parts = [p for p in path.parts[1:] if p not in ("", ".")]
        try:
            start_fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
        except OSError as exc:
            raise SilqBoundaryError("FILE_IO_ERROR", f"cannot open root anchor: {type(exc).__name__}") from exc
    else:
        try:
            os.getcwd()
            start_fd = os.open(".", os.O_RDONLY | os.O_DIRECTORY)
        except OSError as exc:
            raise SilqBoundaryError("CWD_UNAVAILABLE", f"current working directory unavailable: {type(exc).__name__}") from exc
        try:
            _check_pwd_no_symlinks()
        except SilqBoundaryError:
            os.close(start_fd)
            raise
        raw_parts = [p for p in path.parts if p not in ("", ".")]

    if not raw_parts or raw_parts[-1] == "..":
        os.close(start_fd)
        raise SilqBoundaryError("NON_REGULAR_FILE", "target path names a directory")

    dfd = _step_dir_fd_chain(start_fd, raw_parts[:-1], "path_component")
    return dfd, raw_parts[-1]


def require_safe_path(path: Any) -> Path:
    """Verify exact Path type, CWD/PWD safety, ancestor traversal, and non-symlink leaf."""
    dfd, leaf = _open_parent_dir_fd(path)
    try:
        try:
            st = os.lstat(leaf, dir_fd=dfd)
        except FileNotFoundError:
            return path
        except OSError as exc:
            raise SilqBoundaryError("PATH_STAT_ERROR", f"cannot lstat target: {type(exc).__name__}") from exc
        if stat.S_ISLNK(st.st_mode):
            raise SilqBoundaryError("SYMLINK_FORBIDDEN", "symlink forbidden at leaf")
        return path
    finally:
        os.close(dfd)


def read_regular_bytes_capped(path: Path, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    """Stream regular file in bounded 65536-byte chunks via dir_fd + O_NOFOLLOW."""
    cap = require_int(max_bytes, "max_bytes", lo=1, hi=HARD_MAX_BYTES_CAP)
    dfd, leaf = _open_parent_dir_fd(path)
    fd = -1
    try:
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise SilqBoundaryError("SYMLINK_FORBIDDEN", "symlink forbidden at leaf") from exc
            raise SilqBoundaryError("FILE_READ_ERROR", f"cannot open file: {type(exc).__name__}") from exc
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise SilqBoundaryError("NON_REGULAR_FILE", "target is not a regular file")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, _READ_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > cap:
                raise SilqBoundaryError("FILE_TOO_LARGE", f"file exceeds {cap} bytes")
            chunks.append(chunk)
        return b"".join(chunks)
    except SilqBoundaryError:
        raise
    except OSError as exc:
        raise SilqBoundaryError("FILE_READ_ERROR", f"failed reading file: {type(exc).__name__}") from exc
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(dfd)


def write_regular_file_bytes(path: Path, payload: bytes) -> None:
    """Thread-safe atomic 0o600 dir_fd write with EEXIST retry, fsync, and st_nlink guards."""
    global _TMP_COUNTER
    if type(payload) is not bytes:
        raise SilqBoundaryError("INVALID_WRITE_DATA", "payload must be exact bytes")
    dfd, leaf = _open_parent_dir_fd(path)
    tmp_fd = -1
    created_tmp = False
    tmp_name = ""
    try:
        try:
            st = os.lstat(leaf, dir_fd=dfd)
        except FileNotFoundError:
            st = None
        except OSError as exc:
            raise SilqBoundaryError("FILE_WRITE_ERROR", f"cannot stat target: {type(exc).__name__}") from exc
        if st is not None:
            if stat.S_ISLNK(st.st_mode):
                raise SilqBoundaryError("SYMLINK_FORBIDDEN", "cannot write to symlink target")
            if not stat.S_ISREG(st.st_mode):
                raise SilqBoundaryError("NON_REGULAR_FILE", "cannot write to non-regular file")
            if st.st_nlink > 1:
                raise SilqBoundaryError("HARDLINK_FORBIDDEN", "cannot write through hardlinked file")

        try:
            for _ in range(_TMP_MAX_ATTEMPTS):
                with _TMP_LOCK:
                    _TMP_COUNTER += 1
                    seq = _TMP_COUNTER
                cand = f".s38_silq_tmp_{os.getpid()}_{seq}_{secrets.token_hex(8)}"
                try:
                    tmp_fd = os.open(
                        cand,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK,
                        0o600,
                        dir_fd=dfd,
                    )
                    tmp_name = cand
                    created_tmp = True
                    break
                except FileExistsError:
                    continue
            if not created_tmp:
                raise SilqBoundaryError("TEMP_RETRY_EXHAUSTED", "exhausted atomic temp file retries")
            view = memoryview(payload)
            written = 0
            while written < len(payload):
                written += os.write(tmp_fd, view[written:])
            os.fsync(tmp_fd)
            if os.fstat(tmp_fd).st_nlink != 1:
                raise SilqBoundaryError("HARDLINK_FORBIDDEN", "temp file hardlinked before replace")
            os.replace(tmp_name, leaf, src_dir_fd=dfd, dst_dir_fd=dfd)
            created_tmp = False
            os.close(tmp_fd)
            tmp_fd = -1
            os.fsync(dfd)
        except SilqBoundaryError:
            raise
        except OSError as exc:
            raise SilqBoundaryError("FILE_WRITE_ERROR", f"failed atomic write: {type(exc).__name__}") from exc
    finally:
        if tmp_fd >= 0:
            os.close(tmp_fd)
        if created_tmp:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
        os.close(dfd)


# ---------------------------------------------------------------------------
# Secondary Algebraic Cross-Check Over All 4 Mathematical Pillars
# ---------------------------------------------------------------------------

def _require_exact_dict(val: Any, expected_keys: frozenset[str], err_code: str, label: str) -> dict[str, Any]:
    if type(val) is not dict:
        raise SilqBoundaryError("AUDIT_SCHEMA_TYPE", f"{label} must be strict dict")
    if frozenset(val.keys()) != expected_keys:
        raise SilqBoundaryError(err_code, f"{label} keyset mismatch")
    return val


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Schema, cross-field, Born-sum, rational/decimal, and strict-type secondary audit across all 4 pillars."""
    if type(payload) is not dict:
        raise SilqBoundaryError("AUDIT_PAYLOAD_TYPE", "payload must be strict dict")
    if not require_bool(payload.get("all_verified"), "all_verified"):
        raise SilqBoundaryError("AUDIT_ALL_VERIFIED_FALSE", "payload.all_verified must be True")

    try:
        if payload["literature_anchors_n0"] != _EXPECTED_LITERATURE_ANCHORS:
            raise SilqBoundaryError("AUDIT_META_ANCHORS", "literature_anchors_n0 mismatch")

        # Pillar 1: Dyadic cyclotomic Clifford+T engine
        p1 = _require_exact_dict(payload["pillar1_cyclotomic_clifford_t"], _P1_KEYS, "AUDIT_SCHEMA_ERROR", "pillar1")
        if p1["ring_representation"] != _EXPECTED_RING_REPR:
            raise SilqBoundaryError("AUDIT_P1_RING", "ring_representation mismatch")
        gcerts = p1["gate_certifications"]
        if [g["gate"] for g in gcerts] != ["X", "Y", "Z", "H", "S", "T", "CNOT", "CZ", "CCX"]:
            raise SilqBoundaryError("AUDIT_P1_GATES", "all 9 canonical Clifford+T gates required")
        if [require_int(g["dim"], "gate.dim") for g in gcerts] != [2, 2, 2, 2, 2, 2, 4, 4, 8]:
            raise SilqBoundaryError("AUDIT_P1_GATE_DIMS", "canonical gate dimensions mismatch")
        if not all((
            require_bool(p1["all_gates_unitary_and_dyadic"], "p1.all_gates"),
            *(frozenset(g.keys()) == _P1_GATE_KEYS for g in gcerts),
            *(require_bool(g["is_unitary"], "gate.is_unitary") for g in gcerts),
            *(require_bool(g["is_dyadic"], "gate.is_dyadic") for g in gcerts),
        )):
            raise SilqBoundaryError("AUDIT_P1_UNITARY", "all 9 gates must be unitary, dyadic, and schema-strict")
        rels = p1["group_relations_verified"]
        if type(rels) is not dict or frozenset(rels.keys()) != _EXPECTED_GROUP_RELATIONS:
            raise SilqBoundaryError("AUDIT_P1_RELATIONS", "exact 14 Clifford+T group relation keys required")
        if not all((
            require_bool(p1["all_group_relations_verified"], "p1.all_rels"),
            *(require_bool(v, "group_rel") for v in rels.values()),
        )):
            raise SilqBoundaryError("AUDIT_P1_RELATIONS", "all 14 Clifford+T group relations must hold")
        wits = p1["born_witnesses"]
        if type(wits) is not dict or frozenset(wits.keys()) != frozenset(_EXPECTED_BORN_VECTORS.keys()):
            raise SilqBoundaryError("AUDIT_P1_BORN", "exact 4 canonical Born witnesses required")
        if not require_bool(p1["all_witnesses_unit_norm"], "p1.all_wit"):
            raise SilqBoundaryError("AUDIT_P1_BORN", "all_witnesses_unit_norm must be True")
        for wname, exp_vec in _EXPECTED_BORN_VECTORS.items():
            w = _require_exact_dict(wits[wname], _P1_BORN_KEYS, "AUDIT_P1_BORN", f"{wname} witness")
            probs = w["born_probs_qsqrt2"]
            if not all((type(probs) is list, len(probs) == len(exp_vec))):
                raise SilqBoundaryError("AUDIT_P1_BORN_SHAPE", f"{wname} born_probs_qsqrt2 length must be {len(exp_vec)}")
            su = Fraction(0, 1)
            sv = Fraction(0, 1)
            for pair in probs:
                if not all((type(pair) is list, len(pair) == 2)):
                    raise SilqBoundaryError("AUDIT_P1_BORN_PAIR", f"{wname} Born probability must be [u, v]")
                u = parse_exact_rational(pair[0], f"{wname}.u")
                v = parse_exact_rational(pair[1], f"{wname}.v")
                if not all((u.denominator & (u.denominator - 1) == 0, v.denominator & (v.denominator - 1) == 0)):
                    raise SilqBoundaryError("AUDIT_P1_NON_DYADIC", f"{wname} contains non-dyadic Born denominator")
                if not _qsqrt2_nonneg(u, v):
                    raise SilqBoundaryError("AUDIT_P1_BORN_NEGATIVE", f"{wname} contains negative Born probability")
                su += u
                sv += v
            if not all((
                su == Fraction(1, 1),
                sv == Fraction(0, 1),
                probs == exp_vec,
                parse_exact_rational(w["sum_q"], f"{wname}.sum_q") == su,
                parse_exact_rational(w["sum_sqrt2"], f"{wname}.sum_sqrt2") == sv,
                require_bool(w["born_sum_is_one"], f"{wname}.sum1"),
                require_bool(w["all_born_nonneg"], f"{wname}.nonneg"),
                require_bool(w["all_dyadic"], f"{wname}.dyadic"),
            )):
                raise SilqBoundaryError("AUDIT_P1_BORN", f"{wname} Born witness failed exact unit-norm/vector check")
        if not all((
            require_bool(p1["must_fail_non_unitary_rejected"], "p1.non_unitary"),
            require_bool(p1["pillar_verified"], "p1.verified"),
        )):
            raise SilqBoundaryError("AUDIT_P1_NONUNITARY", "non-unitary negative control and pillar flag must hold")

        # Pillar 2: Executable Silq static type-checker
        p2 = _require_exact_dict(payload["pillar2_silq_static_typechecker"], _P2_KEYS, "AUDIT_SCHEMA_ERROR", "pillar2")
        vprogs = p2["valid_programs"]
        fprogs = p2["must_fail_programs"]
        if (require_int(p2["valid_program_count"], "valid_program_count"), len(vprogs)) != (6, 6):
            raise SilqBoundaryError("AUDIT_P2_VALID_COUNT", "must certify all 6 valid Silq programs")
        if not all((
            require_bool(p2["all_valid_accepted"], "p2.all_valid"),
            require_bool(p2["pillar_verified"], "p2.verified"),
            {r["name"] for r in vprogs} == frozenset(_EXPECTED_VALID_PROGRAMS.keys()),
            *(
                all((
                    type(r) is dict,
                    frozenset(r.keys()) == _P2_VALID_KEYS,
                    require_bool(r["well_typed"], "vprog.well_typed"),
                    r["type_error_code"] is None,
                    r["type_error_detail"] is None,
                    (r["annotation"], r["return_types"], r["synthesized_uncomputations"])
                    == _EXPECTED_VALID_PROGRAMS.get(r["name"]),
                ))
                for r in vprogs
            ),
        )):
            raise SilqBoundaryError("AUDIT_P2_VALID_TYPED", "all 6 distinct valid Silq programs must typecheck")
        if (require_int(p2["must_fail_program_count"], "must_fail_program_count"), len(fprogs)) != (7, 7):
            raise SilqBoundaryError("AUDIT_P2_FAIL_COUNT", "must certify all 7 must-fail Silq programs")
        if not all((
            require_bool(p2["all_must_fail_rejected"], "p2.all_fail"),
            {r["name"] for r in fprogs} == frozenset(_EXPECTED_MUST_FAIL_PROGRAMS.keys()),
            *(
                all((
                    type(r) is dict,
                    frozenset(r.keys()) == _P2_FAIL_KEYS,
                    not require_bool(r["well_typed"], "fprog.well_typed"),
                    r["synthesized_uncomputations"] == [],
                    r["type_error_code"] == r["expected_error_code"],
                    (r["annotation"], r["expected_error_code"], r["type_error_detail"])
                    == _EXPECTED_MUST_FAIL_PROGRAMS.get(r["name"]),
                ))
                for r in fprogs
            ),
        )):
            raise SilqBoundaryError("AUDIT_P2_FAIL_REJECTED", "all 7 distinct must-fail programs must reject cleanly")

        # Pillar 3: Exact uncomputation vs dropped-garbage partial trace
        p3 = _require_exact_dict(payload["pillar3_uncomputation_partial_trace"], _P3_KEYS, "AUDIT_SCHEMA_ERROR", "pillar3")
        for wkey, flag_key, exp_keys, exp_dim, exp_pur, exp_sl, exp_diag, err_code in (
            ("deutsch_jozsa_uncomputed_clean", "interference_preserved", _P3_CLEAN_KEYS, 2, Fraction(1, 1), Fraction(0, 1), ["0", "1"], "AUDIT_P3_DJ_CLEAN"),
            ("deutsch_jozsa_dropped_garbage", "interference_destroyed", _P3_GARBAGE_KEYS, 2, Fraction(1, 2), Fraction(1, 2), ["1/2", "1/2"], "AUDIT_P3_DJ_GARBAGE"),
            ("toffoli_grover_uncomputed_clean", "interference_preserved", _P3_CLEAN_KEYS, 4, Fraction(1, 1), Fraction(0, 1), ["0", "0", "0", "1"], "AUDIT_P3_GROVER_CLEAN"),
            ("toffoli_grover_dropped_garbage", "interference_destroyed", _P3_GARBAGE_KEYS, 4, Fraction(5, 8), Fraction(3, 8), ["1/8", "1/8", "1/8", "5/8"], "AUDIT_P3_GROVER_GARBAGE"),
        ):
            w = p3[wkey]
            if not all((
                type(w) is dict,
                frozenset(w.keys()) == exp_keys,
                require_int(w["dim"], f"{wkey}.dim") == exp_dim,
                parse_exact_rational(w["purity_Tr_rho_sq"], f"{wkey}.pur") == exp_pur,
                parse_exact_rational(w["linear_entropy_S_L"], f"{wkey}.sl") == exp_sl,
                w["diagonal_probabilities"] == exp_diag,
                require_bool(w["hermitian"], f"{wkey}.herm"),
                require_bool(w["trace_is_one"], f"{wkey}.tr1"),
                require_bool(w["purity_imag_and_sqrt2_zero"], f"{wkey}.exactq"),
                require_bool(w[flag_key], f"{wkey}.{flag_key}"),
            )):
                raise SilqBoundaryError(err_code, f"{wkey} partial-trace witness mismatch")
        if not all((
            require_bool(p3["purity_strictly_dropped"], "p3.drop"),
            require_bool(p3["pillar_verified"], "p3.verified"),
        )):
            raise SilqBoundaryError("AUDIT_P3_FLAGS", "Pillar 3 purity drop and pillar flag must be True")

        # Pillar 4: Landauer erasure vs reversible Toffoli & nested-simulation table
        p4 = _require_exact_dict(payload["pillar4_landauer_nested_simulation"], _P4_KEYS, "AUDIT_SCHEMA_ERROR", "pillar4")
        and_s = p4["irreversible_and_2_to_1"]
        if not all((
            type(and_s) is dict,
            frozenset(and_s.keys()) == _P4_AND_KEYS,
            require_int(and_s["n_in_bits"], "and.nin") == 2,
            require_int(and_s["n_out_bits"], "and.nout") == 1,
            require_int(and_s["input_state_count"], "and.nstates") == 4,
            require_int(and_s["distinct_output_count"], "and.nout_cnt") == 2,
            require_int(and_s["max_fiber_size"], "and.maxfib") == 3,
            not require_bool(and_s["is_bijection"], "and.bij"),
            not require_bool(and_s["involution_verified"], "and.inv"),
            require_bool(and_s["erasure_bracket_verified"], "and.brk"),
            require_int(and_s["two_pow_N_H_X_given_Y"], "and.pow") == 27,
            parse_exact_rational(and_s["landauer_erasure_lower_bound_bits"], "and.lo") == Fraction(19, 16),
            parse_exact_rational(and_s["landauer_erasure_upper_bound_bits"], "and.hi") == Fraction(6, 5),
            {k: require_int(v, "and.fib") for k, v in and_s["fiber_sizes"].items()} == {"0": 3, "1": 1},
        )):
            raise SilqBoundaryError("AUDIT_P4_LANDAUER_AND", "AND Landauer erasure witness mismatch")
        erase_s = p4["irreversible_reset_1_to_1"]
        if not all((
            type(erase_s) is dict,
            frozenset(erase_s.keys()) == _P4_BASE_MAP_KEYS,
            require_int(erase_s["n_in_bits"], "erase.nin") == 1,
            require_int(erase_s["n_out_bits"], "erase.nout") == 1,
            require_int(erase_s["input_state_count"], "erase.nstates") == 2,
            require_int(erase_s["distinct_output_count"], "erase.nout_cnt") == 1,
            require_int(erase_s["max_fiber_size"], "erase.maxfib") == 2,
            not require_bool(erase_s["is_bijection"], "erase.bij"),
            not require_bool(erase_s["involution_verified"], "erase.inv"),
            require_int(erase_s["two_pow_N_H_X_given_Y"], "erase.pow") == 4,
            {k: require_int(v, "erase.fib") for k, v in erase_s["fiber_sizes"].items()} == {"0": 2},
        )):
            raise SilqBoundaryError("AUDIT_P4_LANDAUER_ERASE", "1-bit reset ERASE witness mismatch")
        ccx_s = p4["reversible_toffoli_3_to_3"]
        if not all((
            type(ccx_s) is dict,
            frozenset(ccx_s.keys()) == _P4_BASE_MAP_KEYS,
            require_int(ccx_s["n_in_bits"], "ccx.nin") == 3,
            require_int(ccx_s["n_out_bits"], "ccx.nout") == 3,
            require_int(ccx_s["input_state_count"], "ccx.nstates") == 8,
            require_int(ccx_s["distinct_output_count"], "ccx.nout_cnt") == 8,
            require_int(ccx_s["max_fiber_size"], "ccx.maxfib") == 1,
            require_bool(ccx_s["is_bijection"], "ccx.bij"),
            require_bool(ccx_s["involution_verified"], "ccx.inv"),
            require_int(ccx_s["two_pow_N_H_X_given_Y"], "ccx.pow") == 1,
            {k: require_int(v, "ccx.fib") for k, v in ccx_s["fiber_sizes"].items()} == {str(k): 1 for k in range(8)},
        )):
            raise SilqBoundaryError("AUDIT_P4_TOFFOLI", "Toffoli reversible bijection witness mismatch")
        tbl = p4["nested_simulation_table_n1_to_n20"]
        if [require_int(r["n_qubits"], "n_qubits") for r in tbl] != list(range(1, 21)):
            raise SilqBoundaryError("AUDIT_P4_SIM_N", "nested simulation table must cover exact n=1..20")
        for r in tbl:
            nq = r["n_qubits"]
            ov = Fraction(1 << nq, nq)
            if not all((
                type(r) is dict,
                frozenset(r.keys()) == _P4_SIM_ROW_KEYS,
                require_int(r["hilbert_dim_2n"], "dim") == (1 << nq),
                require_int(r["cyclotomic_q_components_4x2n"], "qcomps") == 4 * (1 << nq),
                require_int(r["density_matrix_entries_4n"], "rho") == (1 << (2 * nq)),
                parse_exact_rational(r["overhead_2n_over_n"], "ov") == ov,
                r["overhead_decimal_trunc2"] == format_decimal_trunc(ov, places=2),
            )):
                raise SilqBoundaryError("AUDIT_P4_SIM_SCALING", "nested simulation scaling mismatch")
        if not all((
            require_bool(p4["overhead_strictly_increasing_from_n2"], "p4.inc"),
            require_bool(p4["algebraic_group_isomorphic_l0_l2"], "p4.iso"),
            require_bool(p4["pillar_verified"], "p4.verified"),
        )):
            raise SilqBoundaryError("AUDIT_P4_ISO", "Pillar 4 scaling and shared unitary-law flags must be True")
    except SilqBoundaryError:
        raise
    except (KeyError, TypeError, AttributeError) as exc:
        raise SilqBoundaryError("AUDIT_SCHEMA_ERROR", f"malformed payload structure: {type(exc).__name__}") from exc

    return {
        "secondary_audit_passed": True,
        "pillars_checked": 4,
        "gates_checked": len(gcerts),
        "valid_silq_programs_checked": len(vprogs),
        "must_fail_silq_programs_checked": len(fprogs),
        "nested_simulation_rows_checked": len(tbl),
    }


def check_certificate_file(path: Path) -> dict[str, Any]:
    raw = read_regular_bytes_capped(path)
    if b"\r" in raw:
        raise SilqBoundaryError("CRLF_FORBIDDEN", "CRLF line endings forbidden in certificate")
    if not raw.endswith(b"\n"):
        raise SilqBoundaryError("MISSING_TRAILING_LF", "certificate must end with a single LF")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SilqBoundaryError("INVALID_UTF8", "certificate is not valid UTF-8") from exc
    cert = parse_strict_json_text(text, require_object=True)
    canonical_raw = canonical_json_bytes(cert)
    if raw != canonical_raw + b"\n":
        raise SilqBoundaryError("NON_CANONICAL_BYTES", "certificate bytes are not canonical ASCII JSON + LF")
    res = validate_certificate_payload(cert, full_replay=True)
    sec = secondary_audit_payload(cert["payload"])
    res["canonical_sha256"] = hashlib.sha256(canonical_raw).hexdigest()
    res["file_sha256"] = hashlib.sha256(raw).hexdigest()
    res["secondary_audit"] = sec
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
# Strict Zero-Abbreviation Fail-Closed CLI Parsing
# ---------------------------------------------------------------------------

def _validate_cli_path_value(flag: str, val: str) -> Path:
    _require_utf8_str(val, f"{flag}.path")
    if not val or val.startswith("-"):
        raise SilqBoundaryError("INVALID_PATH_ARG", f"{flag} path cannot be empty or flag-like")
    return Path(val)


def _parse_cli_argv(argv: Sequence[str]) -> tuple[str, Path | None, bool]:
    if type(argv) not in (list, tuple) or any(type(item) is not str for item in argv):
        raise SilqBoundaryError("INVALID_ARGV", "argv must be exact list/tuple of strict str")

    mode: str | None = None
    target: Path | None = None
    as_json = False
    i = 0
    n = len(argv)
    while i < n:
        tok = _require_utf8_str(argv[i], "argv")
        if tok == "--json":
            if as_json:
                raise SilqBoundaryError("DUPLICATE_FLAG", "duplicate --json flag")
            as_json = True
            i += 1
        elif tok == "--standalone":
            if mode is not None:
                raise SilqBoundaryError("CONFLICTING_MODE", "multiple mode flags forbidden")
            mode = "standalone"
            i += 1
        elif tok in ("--check", "--write"):
            if mode is not None:
                raise SilqBoundaryError("CONFLICTING_MODE", "multiple mode flags forbidden")
            if i + 1 >= n:
                raise SilqBoundaryError("MISSING_PATH_ARG", f"{tok} requires a path argument")
            mode = "check" if tok == "--check" else "write"
            target = _validate_cli_path_value(tok, argv[i + 1])
            i += 2
        elif tok.startswith("--check=") or tok.startswith("--write="):
            if mode is not None:
                raise SilqBoundaryError("CONFLICTING_MODE", "multiple mode flags forbidden")
            flag_name, raw_val = tok.split("=", 1)
            mode = "check" if flag_name == "--check" else "write"
            target = _validate_cli_path_value(flag_name, raw_val)
            i += 1
        else:
            raise SilqBoundaryError("UNKNOWN_FLAG", f"unrecognized CLI argument: {tok}")

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
    except SilqBoundaryError as exc:
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
