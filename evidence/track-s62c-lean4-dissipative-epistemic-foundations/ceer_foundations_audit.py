#!/usr/bin/env python3
"""Track S62c: Pure-Init Live Lean 4.36.0 Universal Foundations for
Calculational-Experimental Epistemic Recursion (CEER) — Zero-Area Hysteresis,
Concavity/Lipschitz Refutation, Exact Schur Dark-Mode Variance Drop, Stage-A
Affine Gauge Invariance, and 8-Core Die-Chain Graph-Laplacian Monotonicity.

100% pure Python 3 stdlib, zero IEEE-754 floats, zero bare asserts,
zero .isdigit(), zero islink/is_symlink, zero mathematical RNG (secrets.token_hex
used strictly for atomic temp filename uniqueness), zero external Mathlib.
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
import re
import secrets
import shutil
import stat
import subprocess
import sys
import threading
from typing import Any, Sequence

TRACK_ID = "TRACK-S62C-LEAN4-DISSIPATIVE-EPISTEMIC-FOUNDATIONS"
SCHEMA_VERSION = "aletheia.lean4_ceer_foundations.v1"
EXPECTED_LEAN_TOOLCHAIN = "leanprover/lean4:v4.36.0"
EXPECTED_LEAN_VERSION_LINE = (
    "Lean (version 4.36.0, x86_64-unknown-linux-gnu, "
    "commit 611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9, Release)"
)

MAX_INT_BITS = 4096
MAX_INT_DIGITS = 1234
MAX_JSON_BYTES = 1_048_576
MAX_ALLOWED_CAP_BYTES = 64 * 1024 * 1024
MAX_LEAN_BYTES = 262_144
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 16_384
MAX_STR_LEN = 4096
_READ_CHUNK_BYTES = 65_536
_LEAN_TIMEOUT_SECONDS = 60

_EXACT_PATH_TYPES = (Path, type(Path()))
_ASCII_DIGITS = frozenset("0123456789")
_HEX_LOWER = frozenset("0123456789abcdef")
_DARWIN_SYSTEM_LINKS = frozenset({"var", "tmp", "etc"})
_DIR_OPEN_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_TEMP_NAME_LOCK = threading.Lock()
_TEMP_COUNTER = 0

_DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parent

STANDARD_LEAN_AXIOMS: frozenset[str] = frozenset(
    {"propext", "Classical.choice", "Quot.sound"}
)

CEER_PILLARS_COVERED: tuple[str, ...] = (
    "Module 1: Universal Zero-Area Memoryless-Loop Hysteresis, Affine & Lipschitz Cliff Refutation",
    "Module 2: Universal Exact Schur Dark-Mode Variance Drop & Stage-A Affine Gauge Invariance",
    "Module 3: Universal 8-Core Die-Chain Graph-Laplacian M-Matrix Monotonicity & Heat-Pipe Refutation",
)

PRIOR_LITERATURE_N0: tuple[str, ...] = (
    "Green (1828): discrete path-integral signed area and path-reversal cancellation",
    "Lipschitz (1864): Lipschitz continuity and finite-difference slope bounds",
    "Schur (1917) & Haynsworth (1968): Schur complement inertia and nested variance reduction",
    "Pearson (1895): affine gauge invariance of squared correlation and residual variance ratio",
    "Ostrowski (1937) & Varga (1962): tridiagonal M-matrices and discrete Green's function positivity",
    "de Moura & Ullrich (2021): The Lean 4 Theorem Prover (Core Init v4.36.0)",
)

MODULE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "module_id": "M1_HYSTERESIS_CONCAVITY_CLIFF",
        "pillar_ref": "CEER Pillar 1",
        "rel_path": "CEERFoundations/Module1_UniversalHysteresisAndConcavity.lean",
        "theorems": (
            "CEERFoundations.Module1.memoryless_symmetric_loop_zero_area",
            "CEERFoundations.Module1.hysteresis_disproves_all_single_valued",
            "CEERFoundations.Module1.affine_arbitrary_closed_loop_zero_area",
            "CEERFoundations.Module1.affine_vanishing_second_diff",
            "CEERFoundations.Module1.affine_general_collinearity",
            "CEERFoundations.Module1.noncollinear_disproves_all_affine",
            "CEERFoundations.Module1.lipschitz_cliff_disproves_all_L",
            "CEERFoundations.Module1.ceer_cycle_hysteresis_concavity_cliff_witnesses",
        ),
    },
    {
        "module_id": "M2_SCHUR_DARK_MODE_GAUGE",
        "pillar_ref": "CEER Pillar 2",
        "rel_path": "CEERFoundations/Module2_UniversalSchurDarkModeDrop.lean",
        "theorems": (
            "CEERFoundations.Module2.schur_1plus1_variance_drop_universal",
            "CEERFoundations.Module2.schur_1plus2_variance_drop_universal",
            "CEERFoundations.Module2.schur_monotonic_nested_sensor_unveiling",
            "CEERFoundations.Module2.schur_2plus1_trace_and_loewner_drop",
            "CEERFoundations.Module2.centered_cov_shift_invariant",
            "CEERFoundations.Module2.centered_cov_scale_homogeneous",
            "CEERFoundations.Module2.stageA_affine_gauge_invariance_eta",
            "CEERFoundations.Module2.ceer_s53_dark_mode_drop_witness",
        ),
    },
    {
        "module_id": "M3_LAPLACIAN_THERMAL_COUPLING",
        "pillar_ref": "CEER Pillar 3",
        "rel_path": "CEERFoundations/Module3_UniversalLaplacianThermalCoupling.lean",
        "theorems": (
            "CEERFoundations.Module3.die8_laplacian_energy_conservation",
            "CEERFoundations.Module3.die8_far_end_strictly_positive",
            "CEERFoundations.Module3.die8_laplacian_strict_monotonicity",
            "CEERFoundations.Module3.die8_laplacian_strict_flux_decay",
            "CEERFoundations.Module3.die8_pairwise_distance_monotonicity",
            "CEERFoundations.Module3.anisotropic_coupling_refutes_isotropic_chain",
            "CEERFoundations.Module3.die8_greens_exact_solution_exists",
            "CEERFoundations.Module3.die8_g2_h1_and_heatpipe_refutation",
        ),
    },
)

EXPECTED_THEOREM_AXIOMS: dict[str, tuple[str, ...]] = {
    "CEERFoundations.Module1.memoryless_symmetric_loop_zero_area": ("propext", "Quot.sound"),
    "CEERFoundations.Module1.hysteresis_disproves_all_single_valued": ("propext", "Quot.sound"),
    "CEERFoundations.Module1.affine_arbitrary_closed_loop_zero_area": ("propext", "Quot.sound"),
    "CEERFoundations.Module1.affine_vanishing_second_diff": ("propext", "Quot.sound"),
    "CEERFoundations.Module1.affine_general_collinearity": ("propext", "Quot.sound"),
    "CEERFoundations.Module1.noncollinear_disproves_all_affine": ("propext", "Quot.sound"),
    "CEERFoundations.Module1.lipschitz_cliff_disproves_all_L": ("propext", "Quot.sound"),
    "CEERFoundations.Module1.ceer_cycle_hysteresis_concavity_cliff_witnesses": ("propext", "Quot.sound"),
    "CEERFoundations.Module2.schur_1plus1_variance_drop_universal": ("propext", "Classical.choice", "Quot.sound"),
    "CEERFoundations.Module2.schur_1plus2_variance_drop_universal": ("propext", "Quot.sound"),
    "CEERFoundations.Module2.schur_monotonic_nested_sensor_unveiling": ("propext", "Classical.choice", "Quot.sound"),
    "CEERFoundations.Module2.schur_2plus1_trace_and_loewner_drop": ("propext", "Classical.choice", "Quot.sound"),
    "CEERFoundations.Module2.centered_cov_shift_invariant": ("propext", "Classical.choice", "Quot.sound"),
    "CEERFoundations.Module2.centered_cov_scale_homogeneous": ("propext",),
    "CEERFoundations.Module2.stageA_affine_gauge_invariance_eta": ("propext", "Classical.choice", "Quot.sound"),
    "CEERFoundations.Module2.ceer_s53_dark_mode_drop_witness": (),
    "CEERFoundations.Module3.die8_laplacian_energy_conservation": ("propext", "Quot.sound"),
    "CEERFoundations.Module3.die8_far_end_strictly_positive": ("propext", "Quot.sound"),
    "CEERFoundations.Module3.die8_laplacian_strict_monotonicity": ("propext", "Classical.choice", "Quot.sound"),
    "CEERFoundations.Module3.die8_laplacian_strict_flux_decay": ("propext", "Classical.choice", "Quot.sound"),
    "CEERFoundations.Module3.die8_pairwise_distance_monotonicity": ("propext", "Classical.choice", "Quot.sound"),
    "CEERFoundations.Module3.anisotropic_coupling_refutes_isotropic_chain": ("propext", "Classical.choice", "Quot.sound"),
    "CEERFoundations.Module3.die8_greens_exact_solution_exists": ("propext", "Quot.sound"),
    "CEERFoundations.Module3.die8_g2_h1_and_heatpipe_refutation": ("propext", "Classical.choice", "Quot.sound"),
}

_CERT_KEYS = frozenset(
    {"schema_version", "track_id", "payload_sha256", "certificate_sha256", "payload"}
)
_PAYLOAD_KEYS = frozenset(
    {
        "track_id",
        "novelty_class",
        "oracle_class",
        "measured_external_mathlib",
        "lean_toolchain",
        "lean_version_line",
        "ceer_pillars_covered",
        "prior_literature_n0",
        "project_manifest",
        "theorem_modules",
        "python_exact_cross_checks",
        "summary",
    }
)
_MANIFEST_KEYS = frozenset(
    {"lean_toolchain_sha256", "lakefile_sha256", "module_count", "total_theorem_count"}
)
_MODULE_KEYS = frozenset(
    {
        "module_id",
        "pillar_ref",
        "rel_path",
        "source_sha256",
        "line_count",
        "theorem_count",
        "theorems",
        "static_envelope_clean",
        "kernel_exit_code",
        "zero_warnings",
    }
)
_THEOREM_ENTRY_KEYS = frozenset({"name", "axioms", "standard_axioms_only"})
_CROSS_KEYS = frozenset(
    {
        "module1_hysteresis_concavity_cliff",
        "module2_schur_dark_mode_gauge",
        "module3_laplacian_thermal_coupling",
        "all_three_cross_checks_verified",
    }
)
_M1_KEYS = frozenset(
    {
        "memoryless_quadratic_loop_area",
        "memoryless_cubic_loop_area",
        "affine_asymmetric_loop_area",
        "thermal_hysteresis_loop_area",
        "thermal_hysteresis_refutes_single_valued",
        "concave_second_diff",
        "concave_slope_12_q",
        "concave_slope_23_q",
        "concave_refutes_affine",
        "cliff_slope_q",
        "cliff_lipschitz_cap",
        "cliff_refutes_lipschitz",
        "verified",
    }
)
_M2_KEYS = frozenset(
    {
        "sensor_det_d",
        "stage0_variance_q",
        "stage1_variance_q",
        "stage2_variance_q",
        "stage1_eta_q",
        "stage2_eta_q",
        "nested_identity_lhs",
        "nested_identity_rhs",
        "strict_two_stage_drop",
        "gauge_scale_factor_k",
        "eta_raw_q",
        "eta_transformed_q",
        "affine_gauge_invariant",
        "verified",
    }
)
_M3_KEYS = frozenset(
    {
        "g_conductance",
        "h_sink",
        "greens_col8",
        "greens_q8",
        "energy_conservation_exact",
        "strict_monotonicity_exact",
        "flux_drops",
        "strict_flux_decay_exact",
        "ratio_t1_over_t7_q",
        "heatpipe_t1",
        "heatpipe_t7",
        "heatpipe_refutes_isotropic",
        "verified",
    }
)
_SUMMARY_KEYS = frozenset(
    {
        "module_count",
        "theorem_count",
        "zero_warning_modules",
        "forbidden_axiom_count",
        "all_three_modules_kernel_checked",
        "all_theorems_standard_axioms_only",
        "float_count_on_trust_path",
        "bare_assert_count",
        "rng_calls",
    }
)
_BOOL_LEAF_KEYS = frozenset(
    {
        "measured_external_mathlib",
        "static_envelope_clean",
        "zero_warnings",
        "standard_axioms_only",
        "all_three_cross_checks_verified",
        "thermal_hysteresis_refutes_single_valued",
        "concave_refutes_affine",
        "cliff_refutes_lipschitz",
        "strict_two_stage_drop",
        "affine_gauge_invariant",
        "energy_conservation_exact",
        "strict_monotonicity_exact",
        "strict_flux_decay_exact",
        "heatpipe_refutes_isotropic",
        "verified",
        "all_three_modules_kernel_checked",
        "all_theorems_standard_axioms_only",
    }
)

_LEAN_FORBIDDEN_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsorry\b"), "LEAN4_SORRY"),
    (re.compile(r"\badmit\b"), "LEAN4_ADMIT"),
    (re.compile(r"(?<!\.)\baxiom\b"), "LEAN4_AXIOM"),
    (re.compile(r"(?<!\.)\bunsafe\b"), "LEAN4_UNSAFE"),
    (re.compile(r"\bnative_decide\b"), "LEAN4_NATIVE_DECIDE"),
    (re.compile(r"\bsorryAx\b"), "LEAN4_SORRY_AX"),
    (re.compile(r"\b(?:Lean\.)?ofReduceBool\b"), "LEAN4_OF_REDUCE_BOOL"),
    (re.compile(r"\b(?:Lean\.)?trustCompiler\b"), "LEAN4_TRUST_COMPILER"),
    (re.compile(r"\bdebug\s*\.\s*skipKernelTC\b", flags=re.DOTALL), "LEAN4_SKIP_KERNEL_TC"),
    (re.compile(r"@\[[^\]]*\b(?:extern|implemented_by)\b[^\]]*\]", flags=re.DOTALL), "LEAN4_ATTR_ESCAPE"),
    (re.compile(r"(?<!\.)\bpartial\s+(?:def|instance|abbrev)\b", flags=re.DOTALL), "LEAN4_PARTIAL"),
)
_LEAN_DECIDE_KW_RE = re.compile(r"\bdecide\b")
_LEAN_FLAG_TOK_RE = re.compile(r"[+-][A-Za-z0-9_]+")
_LEAN_OPT_PREFIX_RE = re.compile(r"\s*([A-Za-z0-9_]+)\s*:=")
_LEAN_CONFIG_NATIVE_RE = re.compile(
    r"\bnative\b(?:\s*:=\s*([^},]*)(?=\s*(?:$|,(?=\s|$|[A-Za-z_«]))))?"
)
_LEAN_WITH_KW_RE = re.compile(r"\bwith\b")
_LEAN_GUILLEMET_IDENT_RE = re.compile(r"«([A-Za-z_][A-Za-z0-9_']*)»")
_LEAN_DECIDE_CONFIG_BIND_RE = re.compile(
    r"\b(?:DecideConfig|Decide\.Config)\b[ \t)]*:=\s*(?:\(\s*)*\{[^}{]*\bnative\s*:=\s*([^}{,:]*)(?:,[^}{]*)?\}"
    r"|\{[^}{]*\bnative\s*:=\s*([^}{,:]*)(?:,[^}{]*)?\}\s*:\s*(?:[A-Za-z_][A-Za-z0-9_]*\.)*(?:DecideConfig|Decide\.Config)\b",
    flags=re.DOTALL,
)
_LEAN_IMPORT_RE = re.compile(
    r"(?m)^\s*(?:(?:public|private|meta)\s+)*import\s+([A-Za-z0-9_.]+)"
)
_LEAN_IDENT_EXTRA = "_.'!?"
_LEAN_CHAR_PREV_EXTRA = "_'»"
_AXIOM_NONE_RE = re.compile(
    r"\A'([A-Za-z0-9_.]+)' does not depend on any axioms\Z"
)
_AXIOM_LIST_RE = re.compile(
    r"\A'([A-Za-z0-9_.]+)' depends on axioms: \[([^\]]*)\]\Z"
)


class CeerFoundationsError(ValueError):
    """Typed fail-closed error for all Track S62c kernel, math, and Zone-B checks."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


# ============================================================================
# 1. Exact Type, Integer, Rational & Canonical JSON Primitives (Zero Floats)
# ============================================================================

def require_ok(cond: bool, code: str, message: str) -> None:
    if type(cond) is not bool:
        raise CeerFoundationsError("INVALID_CONDITION_TYPE", f"{code}: exact bool required")
    if not cond:
        raise CeerFoundationsError(code, message)


def require_exact_bool(val: Any, label: str) -> bool:
    if type(val) is not bool:
        raise CeerFoundationsError("INVALID_BOOL_TYPE", f"{label}: exact bool required")
    return val


def require_exact_int(
    val: Any,
    label: str,
    *,
    lo: int | None = None,
    hi: int | None = None,
) -> int:
    if type(val) is not int:
        raise CeerFoundationsError("INVALID_INT_TYPE", f"{label}: exact int required")
    if val.bit_length() > MAX_INT_BITS:
        raise CeerFoundationsError("INT_BIT_LIMIT", f"{label}: exceeds {MAX_INT_BITS}-bit cap")
    if lo is not None:
        if type(lo) is not int:
            raise CeerFoundationsError("INVALID_BOUND_TYPE", f"{label}.lo: exact int required")
        if val < lo:
            raise CeerFoundationsError("INT_OUT_OF_RANGE", f"{label}: must be >= {lo}")
    if hi is not None:
        if type(hi) is not int:
            raise CeerFoundationsError("INVALID_BOUND_TYPE", f"{label}.hi: exact int required")
        if val > hi:
            raise CeerFoundationsError("INT_OUT_OF_RANGE", f"{label}: must be <= {hi}")
    return val


def require_exact_str(
    val: Any,
    label: str,
    *,
    max_len: int = MAX_STR_LEN,
    non_empty: bool = True,
) -> str:
    if type(val) is not str:
        raise CeerFoundationsError("INVALID_STR", f"{label}: exact str required")
    require_ok("\x00" not in val, "NUL_BYTE_FORBIDDEN", f"{label}: NUL byte forbidden")
    if non_empty:
        require_ok(len(val) >= 1, "EMPTY_STR", f"{label}: non-empty str required")
    require_ok(len(val) <= max_len, "STR_TOO_LONG", f"{label}: exceeds {max_len} chars")
    try:
        val.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CeerFoundationsError("INVALID_UTF8_SURROGATE", f"{label}: lone UTF-16 surrogate forbidden") from exc
    return val


def require_sha256_hex(val: Any, label: str) -> str:
    s = require_exact_str(val, label, max_len=64)
    require_ok(len(s) == 64 and all(ch in _HEX_LOWER for ch in s), "INVALID_SHA256", f"{label}: 64 lowercase hex required")
    return s


def parse_exact_int_ascii(text: Any, label: str) -> int:
    s = require_exact_str(text, label, max_len=MAX_INT_DIGITS + 2)
    neg = False
    body = s
    if s[0] == "-":
        neg = True
        body = s[1:]
    require_ok(len(body) >= 1, "INVALID_INT_ASCII", f"{label}: missing digits")
    require_ok(len(body) <= MAX_INT_DIGITS, "INT_DIGIT_LIMIT", f"{label}: exceeds {MAX_INT_DIGITS} digits")
    require_ok(all(ch in _ASCII_DIGITS for ch in body), "INVALID_INT_ASCII", f"{label}: non-ASCII digit")
    if len(body) > 1:
        require_ok(body[0] != "0", "LEADING_ZERO_FORBIDDEN", f"{label}: leading zero forbidden")
    if neg:
        require_ok(body != "0", "NEG_ZERO_FORBIDDEN", f"{label}: -0 forbidden")
    val = int(body)
    if neg:
        val = -val
    return require_exact_int(val, label)


def format_exact_rational(q: Fraction, label: str = "rational") -> str:
    if type(q) is not Fraction:
        raise CeerFoundationsError("INVALID_FRACTION_TYPE", f"{label}: exact Fraction required")
    require_exact_int(q.numerator, f"{label}.num")
    require_exact_int(q.denominator, f"{label}.den", lo=1)
    return str(q.numerator) if q.denominator == 1 else f"{q.numerator}/{q.denominator}"


def parse_exact_rational(text: Any, label: str) -> Fraction:
    s = require_exact_str(text, label, max_len=2 * MAX_INT_DIGITS + 5)
    parts = s.split("/")
    require_ok(len(parts) in (1, 2), "INVALID_RATIONAL", f"{label}: expected p or p/q")
    num = parse_exact_int_ascii(parts[0], f"{label}.num")
    if len(parts) == 1:
        return Fraction(num, 1)
    den = parse_exact_int_ascii(parts[1], f"{label}.den")
    require_ok(den >= 2, "NON_CANONICAL_RATIONAL", f"{label}: denominator must be >= 2")
    require_ok(math.gcd(abs(num), den) == 1, "NON_REDUCED_RATIONAL", f"{label}: rational not reduced")
    return Fraction(num, den)


def _validate_json_tree(obj: Any, label: str = "json") -> None:
    stack: list[tuple[Any, int]] = [(obj, 0)]
    nodes = 0
    while stack:
        cur, depth = stack.pop()
        nodes += 1
        require_ok(nodes <= MAX_JSON_NODES, "JSON_NODE_LIMIT", f"{label}: exceeds {MAX_JSON_NODES} nodes")
        require_ok(depth <= MAX_JSON_DEPTH, "JSON_DEPTH_LIMIT", f"{label}: exceeds depth {MAX_JSON_DEPTH}")
        t = type(cur)
        if t is dict:
            for k, v in cur.items():
                require_exact_str(k, f"{label}.key", non_empty=False)
                stack.append((v, depth + 1))
        elif t is list:
            for item in cur:
                stack.append((item, depth + 1))
        elif t is int:
            require_exact_int(cur, f"{label}.int")
        elif t is str:
            require_exact_str(cur, f"{label}.str", non_empty=False)
        elif t is bool or cur is None:
            continue
        elif t is float:
            raise CeerFoundationsError("FLOAT_FORBIDDEN", f"{label}: IEEE-754 float forbidden")
        else:
            raise CeerFoundationsError("INVALID_JSON_TYPE", f"{label}: disallowed type {t.__name__}")


def canonical_json_bytes(obj: Any) -> bytes:
    _validate_json_tree(obj, "canonical_json")
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=True).encode("utf-8")


def parse_strict_json_text(text: Any, *, require_object: bool = True, label: str = "json") -> Any:
    s = require_exact_str(text, label, max_len=MAX_JSON_BYTES)

    def _reject_float(tok: str) -> Any:
        raise CeerFoundationsError("FLOAT_FORBIDDEN", f"{label}: float token '{tok}' forbidden")

    def _reject_const(tok: str) -> Any:
        raise CeerFoundationsError("JSON_CONST_FORBIDDEN", f"{label}: constant '{tok}' forbidden")

    def _parse_int(tok: str) -> int:
        return parse_exact_int_ascii(tok, f"{label}.int")

    def _no_dup_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in pairs:
            require_exact_str(k, f"{label}.key", non_empty=False)
            if k in out:
                raise CeerFoundationsError("DUPLICATE_JSON_KEY", f"{label}: duplicate key '{k}'")
            out[k] = v
        return out

    try:
        parsed = json.loads(
            s,
            parse_float=_reject_float,
            parse_constant=_reject_const,
            parse_int=_parse_int,
            object_pairs_hook=_no_dup_pairs,
        )
    except CeerFoundationsError:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise CeerFoundationsError("JSON_PARSE_ERROR", f"{label}: invalid JSON ({type(exc).__name__})") from exc

    _validate_json_tree(parsed, label)
    if require_object:
        require_ok(type(parsed) is dict, "JSON_OBJECT_REQUIRED", f"{label}: top-level object required")
    return parsed


# ============================================================================
# 2. Zone-B Path, Darwin Prefix Check, Atomic dir_fd Traversal & 0o600 Write
# ============================================================================

def _require_concrete_path(path: Any, label: str) -> Path:
    require_ok(type(path) in _EXACT_PATH_TYPES, "INVALID_PATH_TYPE", f"{label}: concrete pathlib.Path required")
    require_exact_str(str(path), label)
    return path


def _safe_cwd(label: str) -> Path:
    try:
        return Path.cwd()
    except OSError as exc:
        raise CeerFoundationsError("CWD_UNAVAILABLE", f"{label}: CWD unavailable ({type(exc).__name__})") from exc


def _normalize_darwin_system_prefix(parts: tuple[str, ...]) -> tuple[str, ...]:
    """On macOS (darwin) only, normalize verified root-owned /var, /tmp, /etc -> /private/*."""
    if sys.platform != "darwin" or len(parts) < 2 or parts[0] not in _DARWIN_SYSTEM_LINKS:
        return parts
    head = parts[0]
    try:
        st_link = os.lstat("/" + head)
        if not stat.S_ISLNK(st_link.st_mode) or st_link.st_uid != 0:
            return parts
        target_link = os.readlink("/" + head)
        if target_link != f"private/{head}":
            return parts
        st_priv = os.lstat(f"/private/{head}")
        if not stat.S_ISDIR(st_priv.st_mode) or st_priv.st_uid != 0:
            return parts
    except OSError:
        return parts
    return ("private", head) + parts[1:]


def _check_pwd_no_symlinks(cwd: Path, label: str) -> None:
    pwd = os.environ.get("PWD", "")
    if not pwd.startswith("/"):
        return
    require_exact_str(pwd, f"{label}.PWD")
    try:
        st_cwd = os.stat(str(cwd))
        st_pwd = os.stat(pwd)
    except OSError:
        return
    if (st_pwd.st_dev, st_pwd.st_ino) != (st_cwd.st_dev, st_cwd.st_ino):
        return
    pwd_parts = _normalize_darwin_system_prefix(Path(pwd).parts[1:])
    dfd = os.open("/", _DIR_OPEN_FLAGS)
    try:
        for part in pwd_parts:
            if part == ".":
                continue
            try:
                next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise CeerFoundationsError(
                        "SYMLINK_ANCESTOR_FORBIDDEN", f"{label}: symlink PWD ancestor forbidden"
                    ) from exc
                raise CeerFoundationsError(
                    "CWD_UNAVAILABLE", f"{label}: PWD ancestor unavailable ({type(exc).__name__})"
                ) from exc
            os.close(dfd)
            dfd = next_fd
    finally:
        os.close(dfd)


def _open_dir_chain(target: Path, label: str, *, create_parents: bool) -> tuple[int, str]:
    if target.is_absolute():
        parts = _normalize_darwin_system_prefix(target.parts[1:])
    else:
        cwd = _safe_cwd(label)
        _check_pwd_no_symlinks(cwd, label)
        parts = _normalize_darwin_system_prefix(cwd.parts[1:] + target.parts)
    require_ok(
        len(parts) >= 1 and parts[-1] not in ("", ".", ".."),
        "INVALID_LEAF_NAME",
        f"{label}: path does not name a regular file leaf",
    )
    parent_parts = parts[:-1]
    leaf = parts[-1]
    err_code = "FILE_WRITE_ERROR" if create_parents else "FILE_READ_ERROR"
    dfd = os.open("/", _DIR_OPEN_FLAGS)
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
                        raise CeerFoundationsError(
                            "FILE_WRITE_ERROR", f"{label}: mkdir failed ({type(mk_exc).__name__})"
                        ) from mk_exc
                    try:
                        next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
                    except OSError as re_exc:
                        raise CeerFoundationsError(
                            "FILE_WRITE_ERROR", f"{label}: open created dir failed ({type(re_exc).__name__})"
                        ) from re_exc
                elif exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise CeerFoundationsError(
                        "SYMLINK_FORBIDDEN", f"{label}: symlink or non-directory ancestor forbidden"
                    ) from exc
                else:
                    raise CeerFoundationsError(
                        err_code, f"{label}: cannot traverse ancestor ({type(exc).__name__})"
                    ) from exc
            os.close(dfd)
            dfd = next_fd
        return dfd, leaf
    except BaseException:
        os.close(dfd)
        raise


def read_regular_bytes_capped(path: Path, label: str = "file", max_bytes: int = MAX_JSON_BYTES) -> bytes:
    target = _require_concrete_path(path, label)
    require_exact_int(max_bytes, "max_bytes", lo=1, hi=MAX_ALLOWED_CAP_BYTES)
    dfd, leaf = _open_dir_chain(target, label, create_parents=False)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        try:
            fd = os.open(leaf, flags, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise CeerFoundationsError("SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden") from exc
            raise CeerFoundationsError(
                "FILE_READ_ERROR", f"{label}: cannot open ({type(exc).__name__})"
            ) from exc
    finally:
        os.close(dfd)

    chunks: list[bytes] = []
    total = 0
    try:
        st_f = os.fstat(fd)
        require_ok(stat.S_ISREG(st_f.st_mode), "NOT_A_REGULAR_FILE", f"{label}: not a regular file")
        require_ok(st_f.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: hardlinked file forbidden")
        while total <= max_bytes:
            chunk = os.read(fd, min(_READ_CHUNK_BYTES, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    except CeerFoundationsError:
        raise
    except OSError as exc:
        raise CeerFoundationsError("FILE_READ_ERROR", f"{label}: read failed ({type(exc).__name__})") from exc
    finally:
        os.close(fd)
    require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"{label}: exceeds {max_bytes} bytes")
    return b"".join(chunks)


def write_regular_bytes_safe(path: Path, payload: bytes, label: str = "output") -> None:
    global _TEMP_COUNTER
    require_ok(type(payload) is bytes, "INVALID_PAYLOAD_BYTES", f"{label}: payload must be exact bytes")
    target = _require_concrete_path(path, label)
    dfd, leaf = _open_dir_chain(target, label, create_parents=True)
    tmp_name: str | None = None
    try:
        try:
            st_existing = os.lstat(leaf, dir_fd=dfd)
        except FileNotFoundError:
            st_existing = None
        except OSError as exc:
            raise CeerFoundationsError(
                "FILE_WRITE_ERROR", f"{label}: lstat failed ({type(exc).__name__})"
            ) from exc
        if st_existing is not None:
            require_ok(not stat.S_ISLNK(st_existing.st_mode), "SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden")
            require_ok(stat.S_ISREG(st_existing.st_mode), "NOT_A_REGULAR_FILE", f"{label}: non-regular target")
            require_ok(st_existing.st_nlink <= 1, "HARDLINK_FORBIDDEN", f"{label}: hardlinked target forbidden")

        pid = os.getpid()
        for _ in range(32):
            with _TEMP_NAME_LOCK:
                _TEMP_COUNTER += 1
                seq_num = _TEMP_COUNTER
                cand = f".s62c.{pid}.{seq_num}.{secrets.token_hex(8)}.tmp"
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
                raise CeerFoundationsError(
                    "FILE_WRITE_ERROR", f"{label}: create temp failed ({type(exc).__name__})"
                ) from exc
        else:
            raise CeerFoundationsError("FILE_WRITE_ERROR", f"{label}: exhausted temp file slots")

        try:
            view = memoryview(payload)
            written = 0
            while written < len(view):
                written += os.write(fd, view[written:])
            os.fsync(fd)
            st_tmp = os.fstat(fd)
            require_ok(st_tmp.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: temp link count altered")
        except CeerFoundationsError:
            raise
        except OSError as exc:
            raise CeerFoundationsError(
                "FILE_WRITE_ERROR", f"{label}: write failed ({type(exc).__name__})"
            ) from exc
        finally:
            os.close(fd)

        try:
            st_pre = os.lstat(leaf, dir_fd=dfd)
        except FileNotFoundError:
            st_pre = None
        except OSError as exc:
            raise CeerFoundationsError(
                "FILE_WRITE_ERROR", f"{label}: re-lstat failed ({type(exc).__name__})"
            ) from exc
        if st_pre is not None:
            require_ok(not stat.S_ISLNK(st_pre.st_mode), "SYMLINK_FORBIDDEN", f"{label}: symlink race detected")
            require_ok(stat.S_ISREG(st_pre.st_mode), "NOT_A_REGULAR_FILE", f"{label}: non-regular race detected")
            require_ok(st_pre.st_nlink <= 1, "HARDLINK_FORBIDDEN", f"{label}: hardlink race detected")

        try:
            os.replace(tmp_name, leaf, src_dir_fd=dfd, dst_dir_fd=dfd)
            tmp_name = None
            os.fsync(dfd)
        except OSError as exc:
            raise CeerFoundationsError(
                "FILE_WRITE_ERROR", f"{label}: atomic replace failed ({type(exc).__name__})"
            ) from exc
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
        os.close(dfd)


# ============================================================================
# 3. Lean 4 Static Envelope Gate, `#print axioms` Parser & Live Kernel Runner
# ============================================================================

def _is_lean_ident_prev(s: str, i: int, extra: str) -> bool:
    if i == 0:
        return False
    prev = s[i - 1]
    return prev.isalnum() or prev in extra


def strip_lean4_comments_and_strings(source: str, label: str = "lean") -> str:
    """Strip Lean 4 nested block comments, line comments, plain/raw/interpolated strings, and Char literals."""
    s = require_exact_str(source, label, max_len=MAX_LEAN_BYTES, non_empty=False)
    out: list[str] = []
    i = 0
    n = len(s)
    block_depth = 0
    in_str = False
    in_interp = False
    interp_stack: list[int] = []
    raw_hashes = -1
    while i < n:
        ch = s[i]
        nxt = s[i + 1] if i + 1 < n else ""
        if block_depth > 0:
            if ch == "/" and nxt == "-":
                block_depth += 1
                out.append("  ")
                i += 2
            elif ch == "-" and nxt == "/":
                block_depth -= 1
                out.append("  ")
                i += 2
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if raw_hashes >= 0:
            close_seq = '"' + ("#" * raw_hashes)
            if s.startswith(close_seq, i):
                out.append(" " * len(close_seq))
                i += len(close_seq)
                raw_hashes = -1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if in_str:
            if ch == "\\":
                out.append(" \n" if nxt == "\n" else "  ")
                i += 2
            elif ch == '"':
                in_str = False
                out.append(" ")
                i += 1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if in_interp:
            if ch == "\\":
                out.append(" \n" if nxt == "\n" else "  ")
                i += 2
            elif ch == "{":
                interp_stack.append(1)
                in_interp = False
                out.append(" ")
                i += 1
            elif ch == '"':
                in_interp = False
                out.append(" ")
                i += 1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if interp_stack:
            if ch == "{":
                interp_stack[-1] += 1
                out.append(ch)
                i += 1
                continue
            if ch == "}":
                interp_stack[-1] -= 1
                out.append(ch)
                i += 1
                if interp_stack[-1] == 0:
                    interp_stack.pop()
                    in_interp = True
                continue
        if ch == "/" and nxt == "-":
            block_depth = 1
            out.append("  ")
            i += 2
        elif ch == "-" and nxt == "-":
            while i < n and s[i] != "\n":
                out.append(" ")
                i += 1
        elif ch == "r" and not _is_lean_ident_prev(s, i, _LEAN_IDENT_EXTRA):
            j = i + 1
            while j < n and s[j] == "#":
                j += 1
            if j < n and s[j] == '"':
                raw_hashes = j - (i + 1)
                out.append(" " * (j - i + 1))
                i = j + 1
            else:
                out.append(ch)
                i += 1
        elif (
            ch == "!"
            and nxt == '"'
            and i >= 1
            and s[i - 1] in "smf"
            and not _is_lean_ident_prev(s, i - 1, _LEAN_IDENT_EXTRA)
        ):
            in_interp = True
            out.append("  ")
            i += 2
        elif ch == '"':
            in_str = True
            out.append(" ")
            i += 1
        elif ch == "'" and not _is_lean_ident_prev(s, i, _LEAN_CHAR_PREV_EXTRA):
            if i + 3 < n and s[i + 1] == "\\" and s[i + 3] == "'":
                out.append("    ")
                i += 4
            elif i + 2 < n and s[i + 2] == "'":
                out.append("   ")
                i += 3
            else:
                out.append(ch)
                i += 1
        else:
            out.append(ch)
            i += 1
    require_ok(block_depth == 0, "LEAN4_UNTERMINATED_COMMENT", f"{label}: unterminated block comment")
    require_ok(
        not in_str and not in_interp and raw_hashes < 0 and not interp_stack,
        "LEAN4_UNTERMINATED_STRING",
        f"{label}: unterminated string literal",
    )
    return "".join(out)


def _is_lean4_native_rhs_false(raw: str) -> bool:
    cur = raw.strip()
    while cur.startswith("(") and cur.endswith(")"):
        cur = cur[1:-1].strip()
    return cur in ("false", "Bool.false")


def _has_lean4_decide_native(cleaned: str) -> bool:
    """Single-pass O(n) balanced-paren scanner for Lean 4 decide native-evaluation escapes."""
    for m_dc in _LEAN_DECIDE_CONFIG_BIND_RE.finditer(cleaned):
        for g_idx in (1, 2):
            grp = m_dc.group(g_idx)
            if grp is not None and not _is_lean4_native_rhs_false(grp):
                return True
    n = len(cleaned)
    match_rparen: dict[int, int] | None = None

    for m_dec in _LEAN_DECIDE_KW_RE.finditer(cleaned):
        pos = m_dec.end()
        while True:
            ws = pos
            while ws < n and cleaned[ws].isspace():
                ws += 1
            if ws == n:
                break
            ch = cleaned[ws]
            if ch in "+-":
                m_flag = _LEAN_FLAG_TOK_RE.match(cleaned, ws)
                if m_flag is None:
                    break
                if m_flag.group(0) == "+native":
                    return True
                pos = m_flag.end()
                continue
            if ch == "(":
                if match_rparen is None:
                    match_rparen = {}
                    paren_stack: list[int] = []
                    for idx, pch in enumerate(cleaned):
                        if pch == "(":
                            paren_stack.append(idx)
                        elif pch == ")" and paren_stack:
                            match_rparen[paren_stack.pop()] = idx
                close_idx = match_rparen.get(ws)
                if close_idx is None:
                    break
                m_pfx = _LEAN_OPT_PREFIX_RE.match(cleaned, ws + 1, close_idx)
                if m_pfx is None:
                    break
                opt_key = m_pfx.group(1)
                rhs_lo = m_pfx.end()
                if opt_key == "native":
                    if not _is_lean4_native_rhs_false(cleaned[rhs_lo:close_idx]):
                        return True
                elif opt_key == "config":
                    c_lo, c_hi = rhs_lo, close_idx
                    while True:
                        sub = cleaned[c_lo:c_hi]
                        stripped_l = sub.lstrip()
                        c_lo += len(sub) - len(stripped_l)
                        stripped = stripped_l.rstrip()
                        c_hi = c_lo + len(stripped)
                        if match_rparen.get(c_lo) == c_hi - 1:
                            c_lo += 1
                            c_hi -= 1
                            continue
                        break
                    if not (stripped.startswith("{") and stripped.endswith("}")):
                        return True
                    body = stripped[1:-1]
                    if "{" in body or "}" in body or _LEAN_WITH_KW_RE.search(body) is not None:
                        return True
                    for m_nv in _LEAN_CONFIG_NATIVE_RE.finditer(body):
                        nv_rhs = "" if m_nv.group(1) is None else m_nv.group(1)
                        if not _is_lean4_native_rhs_false(nv_rhs):
                            return True
                pos = close_idx + 1
                continue
            break
    return False


def static_lean_source_check(source: str, label: str = "lean") -> None:
    """Fail-closed static proof-envelope pre-filter on a pure-Init Lean 4 file."""
    cleaned = _LEAN_GUILLEMET_IDENT_RE.sub(r"\1", strip_lean4_comments_and_strings(source, label))
    for pat, code in _LEAN_FORBIDDEN_RULES:
        if pat.search(cleaned) is not None:
            raise CeerFoundationsError(code, f"{label}: forbidden Lean 4 escape matched {code}")
    require_ok(
        not _has_lean4_decide_native(cleaned),
        "LEAN4_DECIDE_NATIVE",
        f"{label}: forbidden Lean 4 decide native-evaluation escape",
    )
    for m_imp in _LEAN_IMPORT_RE.finditer(cleaned):
        mod = m_imp.group(1)
        root_pkg = mod.split(".")[0]
        require_ok(
            root_pkg in ("Init", "Std"),
            "LEAN4_NON_INIT_IMPORT",
            f"{label}: disallowed non-Init/Std import '{mod}'",
        )


def parse_print_axioms_output(
    stdout: str,
    expected_theorems: Sequence[str],
    label: str = "print_axioms",
) -> dict[str, list[str]]:
    """Parse Lean 4 `#print axioms` output strictly and verify standard-only axioms."""
    raw = require_exact_str(stdout, label, max_len=MAX_LEAN_BYTES, non_empty=True)
    entries: list[str] = []
    buf: list[str] = []
    in_brackets = False
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if in_brackets:
            buf.append(stripped)
            if stripped.endswith("]"):
                entries.append(" ".join(buf))
                buf = []
                in_brackets = False
        elif stripped.startswith("'") and "depends on axioms: [" in stripped and not stripped.endswith("]"):
            buf = [stripped]
            in_brackets = True
        else:
            entries.append(stripped)
    require_ok(not in_brackets, "MALFORMED_AXIOM_OUTPUT", f"{label}: unclosed axiom bracket")

    expected_set = frozenset(expected_theorems)
    found: dict[str, list[str]] = {}
    for entry in entries:
        m_none = _AXIOM_NONE_RE.match(entry)
        if m_none is not None:
            thm = m_none.group(1)
            axioms: list[str] = []
        else:
            m_list = _AXIOM_LIST_RE.match(entry)
            if m_list is None:
                raise CeerFoundationsError("UNEXPECTED_LEAN_STDOUT", f"{label}: unexpected output '{entry[:80]}'")
            thm = m_list.group(1)
            body = m_list.group(2).strip()
            require_ok(len(body) >= 1, "EMPTY_AXIOM_BRACKETS", f"{label}: empty axiom list for {thm}")
            axioms = [tok.strip() for tok in body.split(",")]
            require_ok(all(len(a) >= 1 for a in axioms), "MALFORMED_AXIOM_TOKEN", f"{label}: blank axiom token")
        require_ok(thm in expected_set, "UNEXPECTED_THEOREM_NAME", f"{label}: unexpected theorem '{thm}'")
        require_ok(thm not in found, "DUPLICATE_THEOREM_PRINT", f"{label}: duplicate theorem '{thm}'")
        for ax in axioms:
            require_ok(ax in STANDARD_LEAN_AXIOMS, "FORBIDDEN_LEAN_AXIOM", f"{label}: disallowed axiom '{ax}' in {thm}")
        found[thm] = axioms

    for exp_thm in expected_theorems:
        require_ok(exp_thm in found, "MISSING_THEOREM_PRINT", f"{label}: missing '#print axioms' for '{exp_thm}'")
    return found


def resolve_lean_binary() -> str:
    """Resolve the live Lean 4 executable without hardcoding user-specific paths."""
    env_bin = os.environ.get("ALETHEIA_LEAN_BIN")
    if env_bin is not None:
        require_exact_str(env_bin, "ALETHEIA_LEAN_BIN")
        p = Path(env_bin)
        require_ok(p.is_file() and os.access(str(p), os.X_OK), "LEAN_BINARY_UNAVAILABLE", "ALETHEIA_LEAN_BIN not executable")
        return str(p)
    found = shutil.which("lean")
    if found is not None and os.access(found, os.X_OK):
        return found
    try:
        home = Path.home()
    except RuntimeError as exc:
        raise CeerFoundationsError("LEAN_BINARY_UNAVAILABLE", "home directory unavailable") from exc
    for rel in ((".local", "bin", "lean"), (".elan", "bin", "lean")):
        cand = home.joinpath(*rel)
        if cand.is_file() and os.access(str(cand), os.X_OK):
            return str(cand)
    raise CeerFoundationsError("LEAN_BINARY_UNAVAILABLE", "lean executable not found in PATH or ~/.local/bin")


def query_lean_version(lean_bin: str) -> str:
    require_exact_str(lean_bin, "lean_bin")
    try:
        proc = subprocess.run(
            [lean_bin, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CeerFoundationsError("LEAN_EXEC_ERROR", f"lean --version failed ({type(exc).__name__})") from exc
    require_ok(proc.returncode == 0, "LEAN_VERSION_FAILED", f"lean --version exited {proc.returncode}")
    line = proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else ""
    require_ok(line.startswith("Lean (version 4.36.0,"), "LEAN_VERSION_MISMATCH", f"unexpected lean version '{line}'")
    return line


def run_live_lean_module(
    lean_bin: str,
    project_root: Path,
    rel_path: str,
    expected_theorems: Sequence[str],
    module_id: str,
    pillar_ref: str,
) -> dict[str, Any]:
    """Read, hash, statically scan, and live-compile one Lean 4 module through the kernel."""
    root = _require_concrete_path(project_root, "project_root")
    require_exact_str(rel_path, "rel_path")
    lean_path = root / rel_path
    raw_bytes = read_regular_bytes_capped(lean_path, f"lean:{module_id}", max_bytes=MAX_LEAN_BYTES)
    try:
        source_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CeerFoundationsError("INVALID_UTF8_LEAN", f"{module_id}: invalid UTF-8") from exc
    static_lean_source_check(source_text, module_id)
    src_sha = hashlib.sha256(raw_bytes).hexdigest()
    line_count = len(raw_bytes.splitlines())

    try:
        proc = subprocess.run(
            [lean_bin, str(lean_path)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=_LEAN_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CeerFoundationsError("LEAN_EXEC_ERROR", f"{module_id}: lean exec failed ({type(exc).__name__})") from exc

    require_ok(proc.returncode == 0, "LEAN_KERNEL_REJECTED", f"{module_id}: lean exited {proc.returncode}")
    require_ok(proc.stderr.strip() == "", "LEAN_STDERR_NONEMPTY", f"{module_id}: non-empty stderr")
    require_ok("warning:" not in proc.stdout, "LEAN_WARNING_FORBIDDEN", f"{module_id}: compiler warning emitted")

    axiom_map = parse_print_axioms_output(proc.stdout, expected_theorems, label=module_id)
    thm_entries = [
        {
            "name": name,
            "axioms": list(axiom_map[name]),
            "standard_axioms_only": all(ax in STANDARD_LEAN_AXIOMS for ax in axiom_map[name]),
        }
        for name in expected_theorems
    ]
    return {
        "module_id": module_id,
        "pillar_ref": pillar_ref,
        "rel_path": rel_path,
        "source_sha256": src_sha,
        "line_count": line_count,
        "theorem_count": len(thm_entries),
        "theorems": thm_entries,
        "static_envelope_clean": True,
        "kernel_exit_code": 0,
        "zero_warnings": True,
    }


# ============================================================================
# 4. Independent Pure-Z/Q Python Cross-Checks for All 3 CEER Foundation Modules
# ============================================================================

def _trapezoid_area(xs: Sequence[int], ys: Sequence[int]) -> int:
    return sum((ys[i + 1] + ys[i]) * (xs[i + 1] - xs[i]) for i in range(len(xs) - 1))


def _cross_check_module1() -> dict[str, Any]:
    xs = [15, 25, 35, 45]
    sym_x = xs + list(reversed(xs))
    quad_area = _trapezoid_area(sym_x, [x * x - 3 * x + 5 for x in sym_x])
    cubic_area = _trapezoid_area(sym_x, [x * x * x + 7 for x in sym_x])
    asym_x = [10, 17, 42, 13, 10]
    aff_area = _trapezoid_area(asym_x, [11 - 3 * x for x in asym_x])

    therm_y = [48, 56, 65, 75, 75, 69, 62, 53]
    therm_area = _trapezoid_area(sym_x, therm_y)
    hyst_ref = therm_area != 0

    p1, p2, p3 = 15, 30, 45
    y1, y2, y3 = 150, 270, 340
    sec_diff = y1 + y3 - 2 * y2
    s12 = Fraction(y2 - y1, p2 - p1)
    s23 = Fraction(y3 - y2, p3 - p2)
    conc_ref = s12 != s23

    cliff_s = Fraction(480 - 120, 24 - 16)
    lip_cap = 40
    cliff_ref = cliff_s > lip_cap

    ok = all(
        (
            quad_area == 0,
            cubic_area == 0,
            aff_area == 0,
            therm_area == -250,
            hyst_ref,
            sec_diff == -50,
            s12 == Fraction(8, 1),
            s23 == Fraction(14, 3),
            conc_ref,
            cliff_s == Fraction(45, 1),
            cliff_ref,
        )
    )
    return {
        "memoryless_quadratic_loop_area": quad_area,
        "memoryless_cubic_loop_area": cubic_area,
        "affine_asymmetric_loop_area": aff_area,
        "thermal_hysteresis_loop_area": therm_area,
        "thermal_hysteresis_refutes_single_valued": hyst_ref,
        "concave_second_diff": sec_diff,
        "concave_slope_12_q": format_exact_rational(s12),
        "concave_slope_23_q": format_exact_rational(s23),
        "concave_refutes_affine": conc_ref,
        "cliff_slope_q": format_exact_rational(cliff_s),
        "cliff_lipschitz_cap": lip_cap,
        "cliff_refutes_lipschitz": cliff_ref,
        "verified": ok,
    }


def _centered_cov(xs: Sequence[int], ys: Sequence[int]) -> int:
    n = len(xs)
    return n * sum(x * y for x, y in zip(xs, ys)) - sum(xs) * sum(ys)


def _cross_check_module2() -> dict[str, Any]:
    a, b1, b2, d11, d12, d22 = 100, 12, 10, 4, 2, 5
    det_d = d11 * d22 - d12 * d12
    drop_12 = b1 * b1 * d22 - 2 * b1 * b2 * d12 + b2 * b2 * d11
    s0 = Fraction(a, 1)
    s1 = Fraction(d11 * a - b1 * b1, d11)
    s2 = Fraction(det_d * a - drop_12, det_d)
    eta1 = s1 / s0
    eta2 = s2 / s0
    lhs = d11 * (det_d * a - drop_12)
    rhs = det_d * (d11 * a - b1 * b1) - (d11 * b2 - d12 * b1) ** 2
    strict_drop = all((s2 < s1, s1 < s0, lhs == rhs))

    sx = [10, 20, 35, 50, 65]
    sy = [42, 55, 68, 84, 96]
    cx, dx, cy, dy = 7, -13, 5, 29
    sx2 = [cx * x + dx for x in sx]
    sy2 = [cy * y + dy for y in sy]
    k_scale = (cx * cx) * (cy * cy)
    vx, vy, cxy = _centered_cov(sx, sx), _centered_cov(sy, sy), _centered_cov(sx, sy)
    vx2, vy2, cxy2 = _centered_cov(sx2, sx2), _centered_cov(sy2, sy2), _centered_cov(sx2, sy2)
    eta_raw = Fraction(vx * vy - cxy * cxy, vx * vy)
    eta_tr = Fraction(vx2 * vy2 - cxy2 * cxy2, vx2 * vy2)
    gauge_inv = all((eta_raw == eta_tr, vx2 * vy2 == k_scale * vx * vy))

    ok = all(
        (
            det_d == 16,
            s0 == Fraction(100, 1),
            s1 == Fraction(64, 1),
            s2 == Fraction(60, 1),
            eta1 == Fraction(16, 25),
            eta2 == Fraction(3, 5),
            strict_drop,
            k_scale == 1225,
            gauge_inv,
        )
    )
    return {
        "sensor_det_d": det_d,
        "stage0_variance_q": format_exact_rational(s0),
        "stage1_variance_q": format_exact_rational(s1),
        "stage2_variance_q": format_exact_rational(s2),
        "stage1_eta_q": format_exact_rational(eta1),
        "stage2_eta_q": format_exact_rational(eta2),
        "nested_identity_lhs": lhs,
        "nested_identity_rhs": rhs,
        "strict_two_stage_drop": strict_drop,
        "gauge_scale_factor_k": k_scale,
        "eta_raw_q": format_exact_rational(eta_raw),
        "eta_transformed_q": format_exact_rational(eta_tr),
        "affine_gauge_invariant": gauge_inv,
        "verified": ok,
    }


def _cross_check_module3() -> dict[str, Any]:
    g, h = 2, 1
    u = [1, g + h]
    for _ in range(6):
        u.append((2 * g + h) * u[-1] - g * g * u[-2])
    col = [(g ** i) * u[7 - i] for i in range(8)]
    q8 = (g + h) * col[0] - g * col[1]
    bal_ok = all(
        (
            (g + h) * col[0] - g * col[1] == q8,
            all((2 * g + h) * col[i] - g * col[i - 1] - g * col[i + 1] == 0 for i in range(1, 7)),
            (g + h) * col[7] - g * col[6] == 0,
        )
    )
    energy_ok = all((bal_ok, h * sum(col) == q8))
    mono_ok = all((all(col[i] > col[i + 1] for i in range(7)), col[7] > 0))
    drops = [col[i] - col[i + 1] for i in range(7)]
    flux_ok = all((all(drops[i] > drops[i + 1] for i in range(6)), drops[6] > 0))
    ratio_17 = Fraction(col[1], col[7])

    pipe = [78, 58, 52, 49, 48, 51, 56, 64]
    pipe_ref = pipe[7] >= pipe[1]

    ok = all(
        (
            col == [10923, 5462, 2732, 1368, 688, 352, 192, 128],
            q8 == 21845,
            energy_ok,
            mono_ok,
            flux_ok,
            ratio_17 == Fraction(2731, 64),
            pipe_ref,
        )
    )
    return {
        "g_conductance": g,
        "h_sink": h,
        "greens_col8": col,
        "greens_q8": q8,
        "energy_conservation_exact": energy_ok,
        "strict_monotonicity_exact": mono_ok,
        "flux_drops": drops,
        "strict_flux_decay_exact": flux_ok,
        "ratio_t1_over_t7_q": format_exact_rational(ratio_17),
        "heatpipe_t1": pipe[1],
        "heatpipe_t7": pipe[7],
        "heatpipe_refutes_isotropic": pipe_ref,
        "verified": ok,
    }


def compute_python_exact_cross_checks() -> dict[str, Any]:
    m1 = _cross_check_module1()
    m2 = _cross_check_module2()
    m3 = _cross_check_module3()
    all_ok = all((m1["verified"], m2["verified"], m3["verified"]))
    return {
        "module1_hysteresis_concavity_cliff": m1,
        "module2_schur_dark_mode_gauge": m2,
        "module3_laplacian_thermal_coupling": m3,
        "all_three_cross_checks_verified": all_ok,
    }


# ============================================================================
# 5. Live Certificate Builder & Deep Fail-Closed Secondary Auditor
# ============================================================================

def build_certificate(project_root: Path | None = None) -> dict[str, Any]:
    """Build live Lean 4.36.0 kernel-certified Track S62c certificate (zero floats)."""
    root = _DEFAULT_PROJECT_ROOT if project_root is None else _require_concrete_path(project_root, "project_root")
    lean_bin = resolve_lean_binary()
    lean_ver = query_lean_version(lean_bin)

    tc_bytes = read_regular_bytes_capped(root / "lean-toolchain", "lean-toolchain", max_bytes=256)
    try:
        tc_text = tc_bytes.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise CeerFoundationsError("INVALID_UTF8_TOOLCHAIN", "lean-toolchain is not valid UTF-8") from exc
    require_ok(tc_text == EXPECTED_LEAN_TOOLCHAIN, "TOOLCHAIN_MISMATCH", f"expected {EXPECTED_LEAN_TOOLCHAIN}")
    lake_bytes = read_regular_bytes_capped(root / "lakefile.toml", "lakefile.toml", max_bytes=16_384)

    modules: list[dict[str, Any]] = []
    for spec in MODULE_SPECS:
        modules.append(
            run_live_lean_module(
                lean_bin=lean_bin,
                project_root=root,
                rel_path=spec["rel_path"],
                expected_theorems=spec["theorems"],
                module_id=spec["module_id"],
                pillar_ref=spec["pillar_ref"],
            )
        )

    cross = compute_python_exact_cross_checks()
    total_thms = sum(m["theorem_count"] for m in modules)

    payload: dict[str, Any] = {
        "track_id": TRACK_ID,
        "novelty_class": "N1",
        "oracle_class": "lean4_kernel_plus_exact_zq",
        "measured_external_mathlib": False,
        "lean_toolchain": tc_text,
        "lean_version_line": lean_ver,
        "ceer_pillars_covered": list(CEER_PILLARS_COVERED),
        "prior_literature_n0": list(PRIOR_LITERATURE_N0),
        "project_manifest": {
            "lean_toolchain_sha256": hashlib.sha256(tc_bytes).hexdigest(),
            "lakefile_sha256": hashlib.sha256(lake_bytes).hexdigest(),
            "module_count": len(modules),
            "total_theorem_count": total_thms,
        },
        "theorem_modules": modules,
        "python_exact_cross_checks": cross,
        "summary": {
            "module_count": len(modules),
            "theorem_count": total_thms,
            "zero_warning_modules": sum(1 for m in modules if m["zero_warnings"]),
            "forbidden_axiom_count": 0,
            "all_three_modules_kernel_checked": all(m["kernel_exit_code"] == 0 for m in modules),
            "all_theorems_standard_axioms_only": all(
                t["standard_axioms_only"] for m in modules for t in m["theorems"]
            ),
            "float_count_on_trust_path": 0,
            "bare_assert_count": 0,
            "rng_calls": 0,
        },
    }

    payload_sha = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    cert_core = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": payload_sha,
        "payload": payload,
    }
    cert_sha = hashlib.sha256(canonical_json_bytes(cert_core)).hexdigest()
    cert: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": payload_sha,
        "certificate_sha256": cert_sha,
        "payload": payload,
    }
    secondary_audit_payload(payload, project_root=root)
    return cert


def _require_exact_keys(obj: Any, expected: frozenset[str], label: str) -> dict[str, Any]:
    require_ok(type(obj) is dict, "INVALID_DICT", f"{label}: exact dict required")
    actual = frozenset(obj.keys())
    require_ok(actual == expected, "KEYSET_MISMATCH", f"{label}: exact keyset mismatch")
    return obj


def _audit_bool_leaf_bijection(obj: Any, label: str = "payload") -> None:
    stack: list[tuple[Any, str]] = [(obj, label)]
    while stack:
        cur, path = stack.pop()
        if type(cur) is dict:
            for k, v in cur.items():
                child_path = f"{path}.{k}"
                if k in _BOOL_LEAF_KEYS:
                    require_exact_bool(v, child_path)
                else:
                    require_ok(type(v) is not bool, "UNEXPECTED_BOOL_LEAF", f"{child_path}: unexpected bool")
                    stack.append((v, child_path))
        elif type(cur) is list:
            for idx, item in enumerate(cur):
                require_ok(type(item) is not bool, "UNEXPECTED_BOOL_ITEM", f"{path}[{idx}]: unexpected bool")
                stack.append((item, f"{path}[{idx}]"))


def secondary_audit_payload(
    payload: Any,
    *,
    project_root: Path | None = None,
    verify_live_lean: bool = False,
) -> dict[str, Any]:
    """Deep independent fail-closed verification of Track S62c payload."""
    require_exact_bool(verify_live_lean, "verify_live_lean")
    _validate_json_tree(payload, "payload")
    p = _require_exact_keys(payload, _PAYLOAD_KEYS, "payload")
    _audit_bool_leaf_bijection(p, "payload")

    require_ok(p["track_id"] == TRACK_ID, "TRACK_ID_MISMATCH", "payload.track_id mismatch")
    require_ok(p["novelty_class"] == "N1", "NOVELTY_MISMATCH", "payload.novelty_class must be N1")
    require_ok(p["oracle_class"] == "lean4_kernel_plus_exact_zq", "ORACLE_CLASS_MISMATCH", "oracle_class mismatch")
    require_ok(p["measured_external_mathlib"] is False, "MATHLIB_FLAG_MISMATCH", "measured_external_mathlib must be False")
    require_ok(p["lean_toolchain"] == EXPECTED_LEAN_TOOLCHAIN, "TOOLCHAIN_MISMATCH", "lean_toolchain mismatch")
    ver_line = require_exact_str(p["lean_version_line"], "lean_version_line")
    require_ok(ver_line == EXPECTED_LEAN_VERSION_LINE, "LEAN_VERSION_MISMATCH", "lean_version_line mismatch")
    require_ok(p["ceer_pillars_covered"] == list(CEER_PILLARS_COVERED), "PILLARS_MISMATCH", "ceer_pillars_covered mismatch")
    require_ok(p["prior_literature_n0"] == list(PRIOR_LITERATURE_N0), "LIT_MISMATCH", "prior_literature_n0 mismatch")

    manifest = _require_exact_keys(p["project_manifest"], _MANIFEST_KEYS, "project_manifest")
    tc_sha = require_sha256_hex(manifest["lean_toolchain_sha256"], "manifest.lean_toolchain_sha256")
    lake_sha = require_sha256_hex(manifest["lakefile_sha256"], "manifest.lakefile_sha256")
    require_ok(manifest["module_count"] == 3, "MODULE_COUNT_MISMATCH", "manifest.module_count must be 3")
    require_ok(manifest["total_theorem_count"] == 24, "THEOREM_COUNT_MISMATCH", "manifest.total_theorem_count must be 24")

    mods = p["theorem_modules"]
    require_ok(type(mods) is list and len(mods) == len(MODULE_SPECS), "MODULE_LIST_MISMATCH", "theorem_modules must have 3 entries")
    root = _DEFAULT_PROJECT_ROOT if project_root is None else _require_concrete_path(project_root, "project_root")
    disk_tc = read_regular_bytes_capped(root / "lean-toolchain", "lean-toolchain", max_bytes=256)
    require_ok(
        hmac.compare_digest(hashlib.sha256(disk_tc).hexdigest(), tc_sha),
        "TOOLCHAIN_SHA_MISMATCH",
        "lean-toolchain sha256 mismatch",
    )
    disk_lake = read_regular_bytes_capped(root / "lakefile.toml", "lakefile.toml", max_bytes=16_384)
    require_ok(
        hmac.compare_digest(hashlib.sha256(disk_lake).hexdigest(), lake_sha),
        "LAKEFILE_SHA_MISMATCH",
        "lakefile.toml sha256 mismatch",
    )
    lean_bin: str | None = None
    if verify_live_lean:
        lean_bin = resolve_lean_binary()
        live_ver = query_lean_version(lean_bin)
        require_ok(live_ver == ver_line, "LEAN_VERSION_DRIFT", "live lean version does not match certificate")

    total_thms = 0
    for idx, (mod_obj, spec) in enumerate(zip(mods, MODULE_SPECS)):
        m = _require_exact_keys(mod_obj, _MODULE_KEYS, f"theorem_modules[{idx}]")
        require_ok(m["module_id"] == spec["module_id"], "MODULE_ID_MISMATCH", f"module[{idx}] id mismatch")
        require_ok(m["pillar_ref"] == spec["pillar_ref"], "PILLAR_REF_MISMATCH", f"module[{idx}] pillar_ref mismatch")
        require_ok(m["rel_path"] == spec["rel_path"], "REL_PATH_MISMATCH", f"module[{idx}] rel_path mismatch")
        mod_sha = require_sha256_hex(m["source_sha256"], f"module[{idx}].source_sha256")
        line_cnt = require_exact_int(m["line_count"], f"module[{idx}].line_count", lo=10, hi=5000)
        exp_thms = spec["theorems"]
        require_ok(m["theorem_count"] == len(exp_thms), "MOD_THEOREM_COUNT", f"module[{idx}] theorem_count mismatch")
        require_ok(m["static_envelope_clean"] is True, "STATIC_ENVELOPE_FLAG", f"module[{idx}] not clean")
        require_ok(m["kernel_exit_code"] == 0, "KERNEL_EXIT_NONZERO", f"module[{idx}] exit code must be 0")
        require_ok(m["zero_warnings"] is True, "WARNINGS_FLAG", f"module[{idx}] zero_warnings must be True")

        thms = m["theorems"]
        require_ok(type(thms) is list and len(thms) == len(exp_thms), "THEOREMS_LIST_MISMATCH", f"module[{idx}] theorems len")
        for t_idx, (t_obj, exp_name) in enumerate(zip(thms, exp_thms)):
            t = _require_exact_keys(t_obj, _THEOREM_ENTRY_KEYS, f"module[{idx}].theorems[{t_idx}]")
            require_ok(t["name"] == exp_name, "THEOREM_NAME_MISMATCH", f"module[{idx}].theorems[{t_idx}] name")
            require_ok(t["standard_axioms_only"] is True, "THEOREM_AXIOM_FLAG", f"{exp_name} not standard_axioms_only")
            axs = t["axioms"]
            require_ok(type(axs) is list and len(axs) <= 3, "AXIOM_LIST_INVALID", f"{exp_name} axioms list invalid")
            seen_ax: set[str] = set()
            for ax in axs:
                ax_s = require_exact_str(ax, f"{exp_name}.axiom")
                require_ok(ax_s in STANDARD_LEAN_AXIOMS, "FORBIDDEN_LEAN_AXIOM", f"{exp_name}: disallowed axiom '{ax_s}'")
                require_ok(ax_s not in seen_ax, "DUPLICATE_AXIOM", f"{exp_name}: duplicate axiom '{ax_s}'")
                seen_ax.add(ax_s)
            require_ok(
                axs == list(EXPECTED_THEOREM_AXIOMS[exp_name]),
                "AXIOM_SET_MISMATCH",
                f"{exp_name}: axiom footprint mismatch",
            )
        total_thms += len(exp_thms)

        raw_b = read_regular_bytes_capped(root / spec["rel_path"], f"lean:{spec['module_id']}", max_bytes=MAX_LEAN_BYTES)
        require_ok(
            hmac.compare_digest(hashlib.sha256(raw_b).hexdigest(), mod_sha),
            "LEAN_SOURCE_SHA_MISMATCH",
            f"{spec['module_id']}: disk sha256 mismatch",
        )
        require_ok(len(raw_b.splitlines()) == line_cnt, "LEAN_LINE_COUNT_MISMATCH", f"{spec['module_id']}: line_count mismatch")
        try:
            src_text = raw_b.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CeerFoundationsError("INVALID_UTF8_LEAN", f"{spec['module_id']}: invalid UTF-8") from exc
        static_lean_source_check(src_text, spec["module_id"])
        if verify_live_lean:
            live_mod = run_live_lean_module(
                lean_bin=str(lean_bin),
                project_root=root,
                rel_path=spec["rel_path"],
                expected_theorems=exp_thms,
                module_id=spec["module_id"],
                pillar_ref=spec["pillar_ref"],
            )
            require_ok(live_mod == m, "LIVE_LEAN_DRIFT", f"{spec['module_id']}: live kernel output mismatch")

    cross = _require_exact_keys(p["python_exact_cross_checks"], _CROSS_KEYS, "python_exact_cross_checks")
    m1 = _require_exact_keys(cross["module1_hysteresis_concavity_cliff"], _M1_KEYS, "cross.module1")
    m2 = _require_exact_keys(cross["module2_schur_dark_mode_gauge"], _M2_KEYS, "cross.module2")
    m3 = _require_exact_keys(cross["module3_laplacian_thermal_coupling"], _M3_KEYS, "cross.module3")
    for rkey in ("concave_slope_12_q", "concave_slope_23_q", "cliff_slope_q"):
        parse_exact_rational(m1[rkey], f"m1.{rkey}")
    for rkey in (
        "stage0_variance_q",
        "stage1_variance_q",
        "stage2_variance_q",
        "stage1_eta_q",
        "stage2_eta_q",
        "eta_raw_q",
        "eta_transformed_q",
    ):
        parse_exact_rational(m2[rkey], f"m2.{rkey}")
    parse_exact_rational(m3["ratio_t1_over_t7_q"], "m3.ratio_t1_over_t7_q")

    expected_cross = compute_python_exact_cross_checks()
    require_ok(cross == expected_cross, "CROSS_CHECK_MISMATCH", "python_exact_cross_checks mismatch")

    summ = _require_exact_keys(p["summary"], _SUMMARY_KEYS, "summary")
    require_ok(summ["module_count"] == 3, "SUMMARY_MODULE_COUNT", "summary.module_count != 3")
    require_ok(summ["theorem_count"] == total_thms, "SUMMARY_THEOREM_COUNT", "summary.theorem_count mismatch")
    require_ok(summ["zero_warning_modules"] == 3, "SUMMARY_ZERO_WARNINGS", "summary.zero_warning_modules != 3")
    require_ok(summ["forbidden_axiom_count"] == 0, "SUMMARY_FORBIDDEN_AXIOMS", "summary.forbidden_axiom_count != 0")
    require_ok(summ["all_three_modules_kernel_checked"] is True, "SUMMARY_KERNEL_FLAG", "kernel_checked flag False")
    require_ok(summ["all_theorems_standard_axioms_only"] is True, "SUMMARY_AXIOM_FLAG", "standard_axioms flag False")
    require_ok(summ["float_count_on_trust_path"] == 0, "SUMMARY_FLOATS", "float_count_on_trust_path != 0")
    require_ok(summ["bare_assert_count"] == 0, "SUMMARY_ASSERTS", "bare_assert_count != 0")
    require_ok(summ["rng_calls"] == 0, "SUMMARY_RNG", "rng_calls != 0")

    return {"verified": True, "module_count": 3, "theorem_count": total_thms}


def validate_certificate_payload(
    cert: Any,
    *,
    project_root: Path | None = None,
    verify_live_lean: bool = False,
) -> dict[str, Any]:
    """Zone-B hardened in-memory certificate validator."""
    require_exact_bool(verify_live_lean, "verify_live_lean")
    _validate_json_tree(cert, "certificate")
    c = _require_exact_keys(cert, _CERT_KEYS, "certificate")
    require_ok(c["schema_version"] == SCHEMA_VERSION, "SCHEMA_MISMATCH", "schema_version mismatch")
    require_ok(c["track_id"] == TRACK_ID, "TRACK_ID_MISMATCH", "certificate track_id mismatch")
    p_sha = require_sha256_hex(c["payload_sha256"], "payload_sha256")
    c_sha = require_sha256_hex(c["certificate_sha256"], "certificate_sha256")

    actual_p_sha = hashlib.sha256(canonical_json_bytes(c["payload"])).hexdigest()
    require_ok(hmac.compare_digest(actual_p_sha, p_sha), "PAYLOAD_HASH_MISMATCH", "payload_sha256 mismatch")

    core = {
        "schema_version": c["schema_version"],
        "track_id": c["track_id"],
        "payload_sha256": p_sha,
        "payload": c["payload"],
    }
    actual_c_sha = hashlib.sha256(canonical_json_bytes(core)).hexdigest()
    require_ok(hmac.compare_digest(actual_c_sha, c_sha), "CERT_HASH_MISMATCH", "certificate_sha256 mismatch")

    res = secondary_audit_payload(
        c["payload"],
        project_root=project_root,
        verify_live_lean=verify_live_lean,
    )
    return {
        "verified": True,
        "track_id": TRACK_ID,
        "schema_version": SCHEMA_VERSION,
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "module_count": res["module_count"],
        "theorem_count": res["theorem_count"],
    }


def check_certificate_file(
    path: Path,
    *,
    project_root: Path | None = None,
    verify_live_lean: bool = True,
) -> dict[str, Any]:
    require_exact_bool(verify_live_lean, "verify_live_lean")
    raw = read_regular_bytes_capped(path, "certificate_file", max_bytes=MAX_JSON_BYTES)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CeerFoundationsError("INVALID_UTF8_JSON", "certificate file is not valid UTF-8") from exc
    cert = parse_strict_json_text(text, require_object=True, label="certificate_file")
    require_ok(
        hmac.compare_digest(raw, canonical_json_bytes(cert) + b"\n"),
        "NON_CANONICAL_CERT_BYTES",
        "certificate file is not canonical compact UTF-8 JSON with trailing LF",
    )
    root = _DEFAULT_PROJECT_ROOT if project_root is None else project_root
    return validate_certificate_payload(cert, project_root=root, verify_live_lean=verify_live_lean)


# ============================================================================
# 6. Strict Fail-Closed CLI
# ============================================================================

def main(argv: Sequence[str] | None = None) -> int:
    try:
        if argv is None:
            raw_args: Sequence[Any] = sys.argv[1:]
        else:
            require_ok(type(argv) in (list, tuple), "INVALID_CLI_ARGS", "argv must be list or tuple")
            raw_args = argv
        args = [require_exact_str(tok, "argv") for tok in raw_args]
        if len(args) == 2 and args[0] == "--check":
            require_ok(not args[1].startswith("-"), "INVALID_CLI_ARGS", "--check target must not start with '-'")
            verdict = check_certificate_file(Path(args[1]), project_root=_DEFAULT_PROJECT_ROOT, verify_live_lean=True)
            sys.stdout.write(canonical_json_bytes(verdict).decode("utf-8") + "\n")
            return 0
        if len(args) == 0:
            cert = build_certificate(_DEFAULT_PROJECT_ROOT)
            summary = {
                "track_id": TRACK_ID,
                "verified": True,
                "lean_toolchain": cert["payload"]["lean_toolchain"],
                "module_count": cert["payload"]["summary"]["module_count"],
                "theorem_count": cert["payload"]["summary"]["theorem_count"],
                "certificate_sha256": cert["certificate_sha256"],
            }
            sys.stdout.write(canonical_json_bytes(summary).decode("utf-8") + "\n")
            return 0
        if args == ["--standalone", "--json"]:
            cert = build_certificate(_DEFAULT_PROJECT_ROOT)
            sys.stdout.write(canonical_json_bytes(cert).decode("utf-8") + "\n")
            return 0
        if len(args) == 2 and args[0] == "--write":
            require_ok(not args[1].startswith("-"), "INVALID_CLI_ARGS", "--write target must not start with '-'")
            cert = build_certificate(_DEFAULT_PROJECT_ROOT)
            write_regular_bytes_safe(Path(args[1]), canonical_json_bytes(cert) + b"\n", label="certificate_out")
            sys.stdout.write(
                canonical_json_bytes(
                    {
                        "written": True,
                        "certificate_sha256": cert["certificate_sha256"],
                        "payload_sha256": cert["payload_sha256"],
                    }
                ).decode("utf-8")
                + "\n"
            )
            return 0
        raise CeerFoundationsError(
            "INVALID_CLI_ARGS",
            "usage: [--standalone --json | --write <path> | --check <path>]",
        )
    except CeerFoundationsError as exc:
        sys.stderr.write(f"ERROR [{exc.code}]: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
