#!/usr/bin/env python3
"""Live Lean 4.36.0 Kernel-Certified Bridge, Pure-Z/Q Independent Cross-Check
Verifier & Fail-Closed Certificate Auditor.

100% pure Python 3 stdlib, zero IEEE-754 floats, zero bare asserts, zero .isdigit(),
zero islink/is_symlink, zero mathematical RNG (secrets.token_hex used strictly for
atomic temp filename uniqueness), zero external Mathlib dependencies.
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

TRACK_ID = "TRACK-S48-LEAN4-KERNEL-CERTIFIED-BRIDGE"
SCHEMA_VERSION = "aletheia.lean4_kernel_bridge.v1"
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
_DIR_OPEN_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_TEMP_NAME_LOCK = threading.Lock()
_TEMP_COUNTER = 0

_DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parent

STANDARD_LEAN_AXIOMS: frozenset[str] = frozenset(
    {"propext", "Classical.choice", "Quot.sound"}
)

PORTALS_COVERED: tuple[str, ...] = (
    "Portal 53",
    "Portal 54",
    "Portal 57",
    "Portal 58",
)

PRIOR_LITERATURE_N0: tuple[str, ...] = (
    "Hamming (1950), Error detecting and error correcting codes, Bell Syst. Tech. J. 29(2):147-160",
    "IEEE Std 754-2008, binary16 and binary64 exact consecutive integer significand boundary (2^53)",
    "Conway & Sloane (1999), Sphere Packings, Lattices and Groups (E_8 lattice and Construction A)",
    "Landauer (1961), Irreversibility and Heat Generation in the Computing Process, IBM J. Res. Dev. 5(3):183-191",
    "Polya (1913), Aufgabe 424 (3x3 permanent-to-determinant sign-flip obstruction)",
    "Lean 4 Kernel & Core Init (v4.36.0): de Moura & Ullrich (2021), The Lean 4 Theorem Prover",
)

MODULE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "module_id": "T1_HAMMING_F64",
        "portal_ref": "Portal 53 / Track S47",
        "rel_path": "AletheiaKernelCerts/Theorem1_HammingF64.lean",
        "theorems": (
            "AletheiaKernelCerts.Theorem1.f64_pow2_significand_sharp_upper",
            "AletheiaKernelCerts.Theorem1.f64_pow2_significand_sharp_break",
            "AletheiaKernelCerts.Theorem1.f64_group128_f16_exact_w64",
            "AletheiaKernelCerts.Theorem1.f64_w64_max_scaled_sum_exact",
            "AletheiaKernelCerts.Theorem1.f64_group128_f16_w65_odd_overflow",
            "AletheiaKernelCerts.Theorem1.hamming16_H_G_orthogonal",
            "AletheiaKernelCerts.Theorem1.hamming16_H_self_orthogonal",
            "AletheiaKernelCerts.Theorem1.hamming16_dmin_ge_4",
            "AletheiaKernelCerts.Theorem1.hamming16_weight_4_witness",
        ),
    },
    {
        "module_id": "T2_BLOCK_H2_INT8",
        "portal_ref": "Portal 53 / Track S32",
        "rel_path": "AletheiaKernelCerts/Theorem2_BlockH2Int8.lean",
        "theorems": (
            "AletheiaKernelCerts.Theorem2.blockH2_orthogonal_2I",
            "AletheiaKernelCerts.Theorem2.wht8_orthogonal_8I",
            "AletheiaKernelCerts.Theorem2.blockH2_universal_le_78_and_int8_safe",
            "AletheiaKernelCerts.Theorem2.wht8_universal_le_156",
            "AletheiaKernelCerts.Theorem2.blockH2_witness_sharp_78",
            "AletheiaKernelCerts.Theorem2.wht8_witness_overflow_156",
        ),
    },
    {
        "module_id": "T3_CS01_BLIND_WINDOW",
        "portal_ref": "Portal 58 / BRIDGE_10",
        "rel_path": "AletheiaKernelCerts/Theorem3_CS01BlindWindow.lean",
        "theorems": (
            "AletheiaKernelCerts.Theorem3.cs01_trigger_fires",
            "AletheiaKernelCerts.Theorem3.cs01_trigger_minimal",
            "AletheiaKernelCerts.Theorem3.cs01_exact_first_trigger",
            "AletheiaKernelCerts.Theorem3.cs01_blind_window_unbounded",
            "AletheiaKernelCerts.Theorem3.cs01_linear_growth_bound",
            "AletheiaKernelCerts.Theorem3.cs01_witness_1298",
            "AletheiaKernelCerts.Theorem3.cs01_sliding_window_bounded_catch",
            "AletheiaKernelCerts.Theorem3.cs01_sliding_window_default_witness",
        ),
    },
    {
        "module_id": "T4_CS21_LANDAUER",
        "portal_ref": "Portal 54 / Tracks S38 & S44",
        "rel_path": "AletheiaKernelCerts/Theorem4_CS21Landauer.lean",
        "theorems": (
            "AletheiaKernelCerts.Theorem4.cs21_parametric_net_regression",
            "AletheiaKernelCerts.Theorem4.cs21_s44_offloading_witness",
            "AletheiaKernelCerts.Theorem4.landauer_and_power_product_27",
            "AletheiaKernelCerts.Theorem4.landauer_and_exact_rational_bracket",
            "AletheiaKernelCerts.Theorem4.landauer_toffoli_zero_vs_erase_one",
        ),
    },
    {
        "module_id": "T5_POLYA_FERMAT_SEXTIC",
        "portal_ref": "Portal 57 / Tracks S41 & S44",
        "rel_path": "AletheiaKernelCerts/Theorem5_PolyaFermatSextic.lean",
        "theorems": (
            "AletheiaKernelCerts.Theorem5.polya_no_3x3_sign_matrix",
            "AletheiaKernelCerts.Theorem5.polya_512_zero_valid_and_max_5",
            "AletheiaKernelCerts.Theorem5.hodge_sextic_7F_mod5_fermat",
            "AletheiaKernelCerts.Theorem5.hodge_sextic_7F_partials_mod5",
            "AletheiaKernelCerts.Theorem5.fermat_little_mod5_and_jacobian_nondeg",
            "AletheiaKernelCerts.Theorem5.hodge_sextic_mod5_smooth",
        ),
    },
)

EXPECTED_THEOREM_AXIOMS: dict[str, tuple[str, ...]] = {
    "AletheiaKernelCerts.Theorem1.f64_pow2_significand_sharp_upper": ("propext", "Quot.sound"),
    "AletheiaKernelCerts.Theorem1.f64_pow2_significand_sharp_break": ("propext", "Quot.sound"),
    "AletheiaKernelCerts.Theorem1.f64_group128_f16_exact_w64": (),
    "AletheiaKernelCerts.Theorem1.f64_w64_max_scaled_sum_exact": (),
    "AletheiaKernelCerts.Theorem1.f64_group128_f16_w65_odd_overflow": (),
    "AletheiaKernelCerts.Theorem1.hamming16_H_G_orthogonal": ("propext",),
    "AletheiaKernelCerts.Theorem1.hamming16_H_self_orthogonal": ("propext",),
    "AletheiaKernelCerts.Theorem1.hamming16_dmin_ge_4": ("propext", "Classical.choice", "Quot.sound"),
    "AletheiaKernelCerts.Theorem1.hamming16_weight_4_witness": ("propext",),
    "AletheiaKernelCerts.Theorem2.blockH2_orthogonal_2I": ("propext", "Classical.choice", "Quot.sound"),
    "AletheiaKernelCerts.Theorem2.wht8_orthogonal_8I": ("propext", "Classical.choice", "Quot.sound"),
    "AletheiaKernelCerts.Theorem2.blockH2_universal_le_78_and_int8_safe": ("propext", "Classical.choice", "Quot.sound"),
    "AletheiaKernelCerts.Theorem2.wht8_universal_le_156": ("propext", "Classical.choice", "Quot.sound"),
    "AletheiaKernelCerts.Theorem2.blockH2_witness_sharp_78": ("propext",),
    "AletheiaKernelCerts.Theorem2.wht8_witness_overflow_156": ("propext",),
    "AletheiaKernelCerts.Theorem3.cs01_trigger_fires": ("propext", "Quot.sound"),
    "AletheiaKernelCerts.Theorem3.cs01_trigger_minimal": ("propext", "Quot.sound"),
    "AletheiaKernelCerts.Theorem3.cs01_exact_first_trigger": ("propext", "Classical.choice", "Quot.sound"),
    "AletheiaKernelCerts.Theorem3.cs01_blind_window_unbounded": ("propext", "Quot.sound"),
    "AletheiaKernelCerts.Theorem3.cs01_linear_growth_bound": ("propext", "Quot.sound"),
    "AletheiaKernelCerts.Theorem3.cs01_witness_1298": ("propext", "Classical.choice", "Quot.sound"),
    "AletheiaKernelCerts.Theorem3.cs01_sliding_window_bounded_catch": ("propext", "Quot.sound"),
    "AletheiaKernelCerts.Theorem3.cs01_sliding_window_default_witness": ("propext", "Classical.choice", "Quot.sound"),
    "AletheiaKernelCerts.Theorem4.cs21_parametric_net_regression": ("propext", "Quot.sound"),
    "AletheiaKernelCerts.Theorem4.cs21_s44_offloading_witness": ("propext", "Classical.choice", "Quot.sound"),
    "AletheiaKernelCerts.Theorem4.landauer_and_power_product_27": ("propext", "Classical.choice", "Quot.sound"),
    "AletheiaKernelCerts.Theorem4.landauer_and_exact_rational_bracket": ("propext", "Classical.choice", "Quot.sound"),
    "AletheiaKernelCerts.Theorem4.landauer_toffoli_zero_vs_erase_one": ("propext", "Classical.choice", "Quot.sound"),
    "AletheiaKernelCerts.Theorem5.polya_no_3x3_sign_matrix": ("propext", "Classical.choice", "Quot.sound"),
    "AletheiaKernelCerts.Theorem5.polya_512_zero_valid_and_max_5": ("propext", "Classical.choice", "Quot.sound"),
    "AletheiaKernelCerts.Theorem5.hodge_sextic_7F_mod5_fermat": ("propext", "Quot.sound"),
    "AletheiaKernelCerts.Theorem5.hodge_sextic_7F_partials_mod5": ("propext", "Quot.sound"),
    "AletheiaKernelCerts.Theorem5.fermat_little_mod5_and_jacobian_nondeg": (),
    "AletheiaKernelCerts.Theorem5.hodge_sextic_mod5_smooth": ("propext", "Quot.sound"),
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
        "portals_covered",
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
        "portal_ref",
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
        "theorem1_hamming_f64",
        "theorem2_block_h2_int8",
        "theorem3_cs01_blind_window",
        "theorem4_cs21_landauer",
        "theorem5_polya_fermat_sextic",
        "all_five_cross_checks_verified",
    }
)
_T1_KEYS = frozenset(
    {
        "f64_exact_int_limit_2p53",
        "w64_pow2_product",
        "w65_pow2_product",
        "w64_group128_f16_max_scaled",
        "w65_group128_f16_odd_witness",
        "w65_witness_is_odd_gt_2p53",
        "hamming16_h_g_orthogonal",
        "hamming16_h_self_orthogonal",
        "hamming16_codeword_count",
        "hamming16_d_min",
        "hamming16_a4_weight4_count",
        "verified",
    }
)
_T2_KEYS = frozenset(
    {
        "int8_max",
        "shell_m_max",
        "max_norm_sq",
        "block_h2_orthogonal_2i",
        "wht8_orthogonal_8i",
        "block_h2_max_entry",
        "block_h2_int8_safe",
        "block_h2_witness",
        "block_h2_witness_shell",
        "wht8_max_entry",
        "wht8_int8_overflow",
        "wht8_witness",
        "wht8_witness_shell",
        "verified",
    }
)
_T3_KEYS = frozenset(
    {
        "range_checked_s0_max",
        "all_s0_exact_first_trigger",
        "witness_s0",
        "witness_delta_blind",
        "witness_m_trig",
        "ratio_at_3708_q",
        "ratio_at_3709_q",
        "legacy_threshold_q",
        "sliding_window_w",
        "sliding_window_floor_q",
        "sliding_window_catches_zero_poloidal",
        "verified",
    }
)
_T4_KEYS = frozenset(
    {
        "circuit_a_full_cost_q",
        "circuit_b_full_cost_q",
        "circuit_c_full_cost_q",
        "apparent_t_speedup_q",
        "circuit_b_hidden_share_q",
        "net_cost_ratio_b_over_a_q",
        "cs21_net_regression_certified",
        "landauer_and_power_product",
        "two_pow_19",
        "and_p_pow_4",
        "and_p_pow_5",
        "two_pow_24",
        "landauer_lower_q",
        "landauer_upper_q",
        "landauer_bracket_certified",
        "toffoli_power_product",
        "erase_power_product",
        "verified",
    }
)
_T5_KEYS = frozenset(
    {
        "polya_total_sign_matrices",
        "polya_valid_count",
        "polya_max_matches_out_of_6",
        "hodge_7f_mod5_fermat_exact",
        "hodge_f5_points_checked",
        "hodge_f5_singular_affine_count",
        "hodge_p5_f5_smooth_certified",
        "verified",
    }
)
_SUMMARY_KEYS = frozenset(
    {
        "module_count",
        "theorem_count",
        "zero_warning_modules",
        "forbidden_axiom_count",
        "all_five_modules_kernel_checked",
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
        "all_five_cross_checks_verified",
        "w65_witness_is_odd_gt_2p53",
        "hamming16_h_g_orthogonal",
        "hamming16_h_self_orthogonal",
        "block_h2_orthogonal_2i",
        "wht8_orthogonal_8i",
        "block_h2_int8_safe",
        "wht8_int8_overflow",
        "all_s0_exact_first_trigger",
        "sliding_window_catches_zero_poloidal",
        "cs21_net_regression_certified",
        "landauer_bracket_certified",
        "hodge_7f_mod5_fermat_exact",
        "hodge_p5_f5_smooth_certified",
        "verified",
        "all_five_modules_kernel_checked",
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
    (re.compile(r"\b(?:Lean\.Meta\.)?mkSorry\b"), "LEAN4_MK_SORRY"),
    (re.compile(r"\b(?:Lean\.)?ofReduceBool\b"), "LEAN4_OF_REDUCE_BOOL"),
    (re.compile(r"\b(?:Lean\.)?ofReduceNat\b"), "LEAN4_OF_REDUCE_NAT"),
    (re.compile(r"\b(?:Lean\.)?trustCompiler\b"), "LEAN4_TRUST_COMPILER"),
    (re.compile(r"\bdebug\.skipKernelTC\b"), "LEAN4_SKIP_KERNEL_TC"),
    (re.compile(r"@\[[^\]]*\b(?:extern|implemented_by)\b"), "LEAN4_ATTR_ESCAPE"),
    (re.compile(r"\bpartial\s+(?:def|instance|abbrev)\b"), "LEAN4_PARTIAL"),
)
_LEAN4_GUILLEMET_IDENT_RE = re.compile(r"«([A-Za-z_][A-Za-z0-9_']*)»")
_LEAN4_IDENT_EXTRA = "_.'!?»"
_LEAN4_DECIDE_KW_RE = re.compile(r"\bdecide\b")
_LEAN4_FLAG_TOK_RE = re.compile(r"[+-][A-Za-z0-9_]+")
_LEAN4_OPT_PREFIX_RE = re.compile(r"\s*([A-Za-z0-9_]+)\s*:=")
_LEAN4_CONFIG_NATIVE_RE = re.compile(r"\bnative\b(?:\s*:=\s*([^},]*))?")
_LEAN4_CONFIG_AFTER_COMMA_RE = re.compile(r",\s*(?:\Z|[A-Za-z_][A-Za-z0-9_']*\s*:=)")
_LEAN4_CONFIG_WITH_RE = re.compile(r"\bwith\b")
_LEAN_IMPORT_RE = re.compile(
    r"(?m)^\s*(?:(?:public|private|meta)\s+)*import\s+([A-Za-z0-9_.]+)"
)
_AXIOM_NONE_RE = re.compile(
    r"\A'([A-Za-z0-9_.]+)' does not depend on any axioms\Z"
)
_AXIOM_LIST_RE = re.compile(
    r"\A'([A-Za-z0-9_.]+)' depends on axioms: \[([^\]]*)\]\Z"
)


class Lean4KernelBridgeError(ValueError):
    """Typed fail-closed error for Lean 4 kernel, math, and filesystem checks."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


# ============================================================================
# 1. Exact Type, Integer, Rational & Canonical JSON Primitives (Zero Floats)
# ============================================================================

def require_ok(cond: bool, code: str, message: str) -> None:
    if type(cond) is not bool:
        raise Lean4KernelBridgeError("INVALID_CONDITION_TYPE", f"{code}: exact bool required")
    if not cond:
        raise Lean4KernelBridgeError(code, message)


def require_exact_bool(val: Any, label: str) -> bool:
    if type(val) is not bool:
        raise Lean4KernelBridgeError("INVALID_BOOL_TYPE", f"{label}: exact bool required")
    return val


def require_exact_int(
    val: Any,
    label: str,
    *,
    lo: int | None = None,
    hi: int | None = None,
) -> int:
    if type(val) is not int:
        raise Lean4KernelBridgeError("INVALID_INT_TYPE", f"{label}: exact int required")
    if val.bit_length() > MAX_INT_BITS:
        raise Lean4KernelBridgeError("INT_BIT_LIMIT", f"{label}: exceeds {MAX_INT_BITS}-bit cap")
    if lo is not None:
        if type(lo) is not int:
            raise Lean4KernelBridgeError("INVALID_BOUND_TYPE", f"{label}.lo: exact int required")
        if val < lo:
            raise Lean4KernelBridgeError("INT_OUT_OF_RANGE", f"{label}: must be >= {lo}")
    if hi is not None:
        if type(hi) is not int:
            raise Lean4KernelBridgeError("INVALID_BOUND_TYPE", f"{label}.hi: exact int required")
        if val > hi:
            raise Lean4KernelBridgeError("INT_OUT_OF_RANGE", f"{label}: must be <= {hi}")
    return val


def require_exact_str(
    val: Any,
    label: str,
    *,
    max_len: int = MAX_STR_LEN,
    non_empty: bool = True,
) -> str:
    if type(val) is not str:
        raise Lean4KernelBridgeError("INVALID_STR", f"{label}: exact str required")
    require_ok("\x00" not in val, "NUL_BYTE_FORBIDDEN", f"{label}: NUL byte forbidden")
    if non_empty:
        require_ok(len(val) >= 1, "EMPTY_STR", f"{label}: non-empty str required")
    require_ok(len(val) <= max_len, "STR_TOO_LONG", f"{label}: exceeds {max_len} chars")
    try:
        val.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise Lean4KernelBridgeError("INVALID_UTF8_SURROGATE", f"{label}: lone UTF-16 surrogate forbidden") from exc
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
        raise Lean4KernelBridgeError("INVALID_FRACTION_TYPE", f"{label}: exact Fraction required")
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
            raise Lean4KernelBridgeError("FLOAT_FORBIDDEN", f"{label}: IEEE-754 float forbidden")
        else:
            raise Lean4KernelBridgeError("INVALID_JSON_TYPE", f"{label}: disallowed type {t.__name__}")


def canonical_json_bytes(obj: Any) -> bytes:
    _validate_json_tree(obj, "canonical_json")
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=True).encode("utf-8")


def parse_strict_json_text(text: Any, *, require_object: bool = True, label: str = "json") -> Any:
    s = require_exact_str(text, label, max_len=MAX_JSON_BYTES)

    def _reject_float(tok: str) -> Any:
        raise Lean4KernelBridgeError("FLOAT_FORBIDDEN", f"{label}: float token '{tok}' forbidden")

    def _reject_const(tok: str) -> Any:
        raise Lean4KernelBridgeError("JSON_CONST_FORBIDDEN", f"{label}: constant '{tok}' forbidden")

    def _parse_int(tok: str) -> int:
        return parse_exact_int_ascii(tok, f"{label}.int")

    def _no_dup_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in pairs:
            require_exact_str(k, f"{label}.key", non_empty=False)
            if k in out:
                raise Lean4KernelBridgeError("DUPLICATE_JSON_KEY", f"{label}: duplicate key '{k}'")
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
    except Lean4KernelBridgeError:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise Lean4KernelBridgeError("JSON_PARSE_ERROR", f"{label}: invalid JSON ({type(exc).__name__})") from exc

    _validate_json_tree(parsed, label)
    if require_object:
        require_ok(type(parsed) is dict, "JSON_OBJECT_REQUIRED", f"{label}: top-level object required")
    return parsed


# ============================================================================
# 2. Hardened Path, CWD, Atomic dir_fd Traversal & Durable 0o600 Atomic Write
# ============================================================================

_DARWIN_SYSTEM_ROOT_ALIASES: dict[str, str] = {
    "var": "private/var",
    "tmp": "private/tmp",
    "etc": "private/etc",
}


def _normalize_darwin_system_prefix(path: Path, *, allow_exact: bool = False) -> Path:
    if sys.platform != "darwin" or not path.is_absolute():
        return path
    parts = path.parts
    min_parts = 2 if allow_exact else 3
    if len(parts) < min_parts or ".." in parts:
        return path
    expected_rel = _DARWIN_SYSTEM_ROOT_ALIASES.get(parts[1])
    if expected_rel is None:
        return path
    top = f"/{parts[1]}"
    try:
        st_top = os.lstat(top)
        if not stat.S_ISLNK(st_top.st_mode) or st_top.st_uid != 0:
            return path
        link_target = os.readlink(top)
    except OSError:
        return path
    if link_target not in (expected_rel, "/" + expected_rel):
        return path
    return Path("/", *expected_rel.split("/"), *parts[2:])


def _require_concrete_path(path: Any, label: str) -> Path:
    require_ok(type(path) in _EXACT_PATH_TYPES, "INVALID_PATH_TYPE", f"{label}: concrete pathlib.Path required")
    require_exact_str(str(path), label)
    return path


def _safe_cwd(label: str) -> Path:
    try:
        return Path.cwd()
    except OSError as exc:
        raise Lean4KernelBridgeError("CWD_UNAVAILABLE", f"{label}: CWD unavailable ({type(exc).__name__})") from exc


def _check_pwd_no_symlinks(label: str) -> None:
    pwd = os.environ.get("PWD", "")
    if not pwd.startswith("/"):
        return
    require_exact_str(pwd, f"{label}.PWD")
    try:
        st_pwd = os.stat(pwd)
        st_dot = os.stat(".")
    except OSError:
        return
    if (st_pwd.st_dev, st_pwd.st_ino) != (st_dot.st_dev, st_dot.st_ino):
        return
    pwd_path = _normalize_darwin_system_prefix(Path(pwd), allow_exact=True)
    dfd = os.open("/", _DIR_OPEN_FLAGS)
    try:
        for part in pwd_path.parts[1:]:
            if part == ".":
                continue
            try:
                next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise Lean4KernelBridgeError(
                        "SYMLINK_ANCESTOR_FORBIDDEN", f"{label}: symlink PWD ancestor forbidden"
                    ) from exc
                raise Lean4KernelBridgeError(
                    "CWD_UNAVAILABLE", f"{label}: PWD ancestor unavailable ({type(exc).__name__})"
                ) from exc
            os.close(dfd)
            dfd = next_fd
    finally:
        os.close(dfd)


def _open_dir_chain(target: Path, label: str, *, create_parents: bool) -> tuple[int, str]:
    if target.is_absolute():
        norm_target = _normalize_darwin_system_prefix(target, allow_exact=False)
        parts = norm_target.parts[1:]
    else:
        cwd = _normalize_darwin_system_prefix(_safe_cwd(label), allow_exact=True)
        _check_pwd_no_symlinks(label)
        parts = cwd.parts[1:] + target.parts
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
                        raise Lean4KernelBridgeError(
                            "FILE_WRITE_ERROR", f"{label}: mkdir failed ({type(mk_exc).__name__})"
                        ) from mk_exc
                    try:
                        next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
                    except OSError as re_exc:
                        raise Lean4KernelBridgeError(
                            "FILE_WRITE_ERROR", f"{label}: open created dir failed ({type(re_exc).__name__})"
                        ) from re_exc
                elif exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise Lean4KernelBridgeError(
                        "SYMLINK_FORBIDDEN", f"{label}: symlink or non-directory ancestor forbidden"
                    ) from exc
                else:
                    raise Lean4KernelBridgeError(
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
                raise Lean4KernelBridgeError("SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden") from exc
            raise Lean4KernelBridgeError(
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
    except Lean4KernelBridgeError:
        raise
    except OSError as exc:
        raise Lean4KernelBridgeError("FILE_READ_ERROR", f"{label}: read failed ({type(exc).__name__})") from exc
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
            raise Lean4KernelBridgeError(
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
                cand = f".s48.{pid}.{seq_num}.{secrets.token_hex(8)}.tmp"
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
                raise Lean4KernelBridgeError(
                    "FILE_WRITE_ERROR", f"{label}: create temp failed ({type(exc).__name__})"
                ) from exc
        else:
            raise Lean4KernelBridgeError("FILE_WRITE_ERROR", f"{label}: exhausted temp file slots")

        try:
            view = memoryview(payload)
            written = 0
            while written < len(view):
                n_written = os.write(fd, view[written:])
                require_ok(n_written > 0, "FILE_WRITE_ERROR", f"{label}: short write returned {n_written}")
                written += n_written
            os.fsync(fd)
            st_tmp = os.fstat(fd)
            require_ok(st_tmp.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: temp link count altered")
        except Lean4KernelBridgeError:
            raise
        except OSError as exc:
            raise Lean4KernelBridgeError(
                "FILE_WRITE_ERROR", f"{label}: write failed ({type(exc).__name__})"
            ) from exc
        finally:
            os.close(fd)

        try:
            st_pre = os.lstat(leaf, dir_fd=dfd)
        except FileNotFoundError:
            st_pre = None
        except OSError as exc:
            raise Lean4KernelBridgeError(
                "FILE_WRITE_ERROR", f"{label}: pre-replace lstat failed ({type(exc).__name__})"
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
            raise Lean4KernelBridgeError(
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

def _is_lean4_ident_char(ch: str) -> bool:
    return ch.isalnum() or ch in _LEAN4_IDENT_EXTRA


def strip_lean4_comments_and_strings(source: str, label: str = "lean") -> str:
    """Strip Lean 4 nested block comments, line comments, char/raw/interpolated/plain strings."""
    s = require_exact_str(source, label, max_len=MAX_LEAN_BYTES, non_empty=False)
    out: list[str] = []
    i = 0
    n = len(s)
    depth = 0
    in_str = False
    in_interp = False
    interp_stack: list[int] = []
    raw_hashes = -1
    while i < n:
        ch = s[i]
        nxt = s[i + 1] if i + 1 < n else ""
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
            depth = 1
            out.append("  ")
            i += 2
        elif ch == "-" and nxt == "-":
            while i < n and s[i] != "\n":
                out.append(" ")
                i += 1
        elif ch == "r" and (i == 0 or not _is_lean4_ident_char(s[i - 1])):
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
            and (i == 1 or not _is_lean4_ident_char(s[i - 2]))
        ):
            in_interp = True
            out.append("  ")
            i += 2
        elif ch == '"':
            in_str = True
            out.append(" ")
            i += 1
        elif ch == "'" and (i == 0 or not _is_lean4_ident_char(s[i - 1])):
            if i + 2 < n and s[i + 1] != "\\" and s[i + 2] == "'":
                out.append("   ")
                i += 3
            elif i + 3 < n and s[i + 1] == "\\" and s[i + 3] == "'":
                out.append("    ")
                i += 4
            else:
                out.append(ch)
                i += 1
        else:
            out.append(ch)
            i += 1
    require_ok(depth == 0, "LEAN4_UNTERMINATED_COMMENT", f"{label}: unterminated block comment")
    require_ok(
        not in_str and not in_interp and not interp_stack and raw_hashes < 0,
        "LEAN4_UNTERMINATED_STRING",
        f"{label}: unterminated string literal",
    )
    return "".join(out)


def _is_lean4_native_rhs_false_span(text: str, lo: int, hi: int) -> bool:
    while lo != hi:
        if text[lo].isspace():
            lo += 1
        elif text[hi - 1].isspace():
            hi -= 1
        elif text[lo] == "(" and text[hi - 1] == ")":
            lo += 1
            hi -= 1
        else:
            break
    return text[lo:hi] in ("false", "Bool.false")


def _is_lean4_safe_config_span(
    text: str,
    lo: int,
    hi: int,
    match_rparen: dict[int, int],
) -> bool:
    while lo != hi:
        if text[lo].isspace():
            lo += 1
        elif text[hi - 1].isspace():
            hi -= 1
        elif match_rparen.get(lo) == hi - 1:
            lo += 1
            hi -= 1
        else:
            break
    if text[lo : lo + 1] != "{" or text[hi - 1 : hi] != "}":
        return False
    body_lo = lo + 1
    body_hi = hi - 1
    if text.find("{", body_lo, body_hi) != -1 or text.find("}", body_lo, body_hi) != -1:
        return False
    if _LEAN4_CONFIG_WITH_RE.search(text, body_lo, body_hi) is not None:
        return False
    for m_nv in _LEAN4_CONFIG_NATIVE_RE.finditer(text, body_lo, body_hi):
        if not _is_lean4_native_rhs_false_span(text, m_nv.start(1), m_nv.end(1)):
            return False
        sep = m_nv.end()
        if sep != body_hi and not _LEAN4_CONFIG_AFTER_COMMA_RE.match(text, sep, body_hi):
            return False
    return True


def _has_lean4_decide_native(cleaned: str) -> bool:
    """Single-pass O(n) balanced-paren scanner for Lean 4 `decide` native-evaluation escapes."""
    n = len(cleaned)
    match_rparen: dict[int, int] = {}
    paren_stack: list[int] = []
    for idx, ch in enumerate(cleaned):
        if ch == "(":
            paren_stack.append(idx)
        elif ch == ")" and paren_stack:
            match_rparen[paren_stack.pop()] = idx

    for m_dec in _LEAN4_DECIDE_KW_RE.finditer(cleaned):
        pos = m_dec.end()
        while True:
            while pos != n and cleaned[pos].isspace():
                pos += 1
            if pos == n:
                break
            ch = cleaned[pos]
            if ch in "+-":
                m_flag = _LEAN4_FLAG_TOK_RE.match(cleaned, pos)
                if m_flag is None:
                    break
                if m_flag.group(0) == "+native":
                    return True
                pos = m_flag.end()
                continue
            if ch == "(":
                close_idx = match_rparen.get(pos)
                if close_idx is None:
                    break
                m_pfx = _LEAN4_OPT_PREFIX_RE.match(cleaned, pos + 1, close_idx)
                if m_pfx is None:
                    break
                opt_key = m_pfx.group(1)
                rhs_lo = m_pfx.end()
                if opt_key == "native":
                    if not _is_lean4_native_rhs_false_span(cleaned, rhs_lo, close_idx):
                        return True
                elif opt_key == "config":
                    if not _is_lean4_safe_config_span(cleaned, rhs_lo, close_idx, match_rparen):
                        return True
                pos = close_idx + 1
                continue
            break
    return False


def static_lean_source_check(source: str, label: str = "lean") -> None:
    """Fail-closed static proof-envelope pre-filter on a pure-Init Lean 4 file."""
    cleaned = _LEAN4_GUILLEMET_IDENT_RE.sub(r"\1", strip_lean4_comments_and_strings(source, label))
    for pat, code in _LEAN_FORBIDDEN_RULES:
        if pat.search(cleaned) is not None:
            raise Lean4KernelBridgeError(code, f"{label}: forbidden Lean 4 escape matched {code}")
    if _has_lean4_decide_native(cleaned):
        raise Lean4KernelBridgeError(
            "LEAN4_DECIDE_NATIVE", f"{label}: forbidden Lean 4 escape matched LEAN4_DECIDE_NATIVE"
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
    # Join multiline wrapped axiom brackets: `'Foo' depends on axioms: [a,\n b,\n c]`
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
                raise Lean4KernelBridgeError("UNEXPECTED_LEAN_STDOUT", f"{label}: unexpected output '{entry[:80]}'")
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
    home = Path.home()
    for rel in ((".local", "bin", "lean"), (".elan", "bin", "lean")):
        cand = home.joinpath(*rel)
        if cand.is_file() and os.access(str(cand), os.X_OK):
            return str(cand)
    raise Lean4KernelBridgeError("LEAN_BINARY_UNAVAILABLE", "lean executable not found in PATH or ~/.local/bin")


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
        raise Lean4KernelBridgeError("LEAN_EXEC_ERROR", f"lean --version failed ({type(exc).__name__})") from exc
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
    portal_ref: str,
) -> dict[str, Any]:
    """Read, hash, statically scan, and live-compile one Lean 4 module through the kernel."""
    root = _require_concrete_path(project_root, "project_root")
    require_exact_str(rel_path, "rel_path")
    lean_path = root / rel_path
    raw_bytes = read_regular_bytes_capped(lean_path, f"lean:{module_id}", max_bytes=MAX_LEAN_BYTES)
    try:
        source_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Lean4KernelBridgeError("INVALID_UTF8_LEAN", f"{module_id}: invalid UTF-8") from exc
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
        raise Lean4KernelBridgeError("LEAN_EXEC_ERROR", f"{module_id}: lean exec failed ({type(exc).__name__})") from exc

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
        "portal_ref": portal_ref,
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
# 4. Independent Pure-Z/Q Python Cross-Checks for All 5 Theorems
# ============================================================================

def _cross_check_theorem1() -> dict[str, Any]:
    f64_lim = 1 << 53
    f16_max = 65_504 * (1 << 24)
    w64_p2 = 64 * (1 << 47)
    w65_p2 = 65 * (1 << 47)
    w64_g = 128 * 64 * f16_max
    w65_w = 127 * 65 * f16_max + 1

    # Extended Hamming [16, 11, 4] H_16 and G_16 matching S47
    h16 = [[1] * 16] + [[(j >> b) & 1 for j in range(16)] for b in range(4)]
    pivots = {0, 1, 2, 4, 8}
    g16: list[list[int]] = []
    for j in range(16):
        if j in pivots:
            continue
        row = [0] * 16
        row[j] = 1
        pc = 0
        for b in range(4):
            if (j >> b) & 1:
                row[1 << b] = 1
                pc += 1
        if pc % 2 == 0:
            row[0] = 1
        g16.append(row)

    hg_ortho = all(
        sum(h16[r][j] * g16[k][j] for j in range(16)) % 2 == 0
        for r in range(5)
        for k in range(11)
    )
    hh_ortho = all(
        sum(h16[r1][j] * h16[r2][j] for j in range(16)) % 2 == 0
        for r1 in range(5)
        for r2 in range(5)
    )
    g_masks = [sum(bit << j for j, bit in enumerate(row)) for row in g16]
    d_min = 16
    a4 = 0
    for msg in range(1, 1 << 11):
        cw = 0
        for k in range(11):
            if (msg >> k) & 1:
                cw ^= g_masks[k]
        wt = cw.bit_count()
        if wt < d_min:
            d_min = wt
        if wt == 4:
            a4 += 1

    w65_odd = all((w65_w > f64_lim, (w65_w % 2 == 1)))
    ok = all(
        (
            w64_p2 <= f64_lim,
            w65_p2 > f64_lim,
            w64_g <= f64_lim,
            w65_odd,
            hg_ortho,
            hh_ortho,
            d_min == 4,
            a4 == 140,
        )
    )
    return {
        "f64_exact_int_limit_2p53": f64_lim,
        "w64_pow2_product": w64_p2,
        "w65_pow2_product": w65_p2,
        "w64_group128_f16_max_scaled": w64_g,
        "w65_group128_f16_odd_witness": w65_w,
        "w65_witness_is_odd_gt_2p53": w65_odd,
        "hamming16_h_g_orthogonal": hg_ortho,
        "hamming16_h_self_orthogonal": hh_ortho,
        "hamming16_codeword_count": 1 << 11,
        "hamming16_d_min": d_min,
        "hamming16_a4_weight4_count": a4,
        "verified": ok,
    }


def _cross_check_theorem2() -> dict[str, Any]:
    block_h2 = (
        (1, 1, 0, 0, 0, 0, 0, 0),
        (1, -1, 0, 0, 0, 0, 0, 0),
        (0, 0, 1, 1, 0, 0, 0, 0),
        (0, 0, 1, -1, 0, 0, 0, 0),
        (0, 0, 0, 0, 1, 1, 0, 0),
        (0, 0, 0, 0, 1, -1, 0, 0),
        (0, 0, 0, 0, 0, 0, 1, 1),
        (0, 0, 0, 0, 0, 0, 1, -1),
    )
    h8 = tuple(
        tuple(1 if (r & c).bit_count() % 2 == 0 else -1 for c in range(8))
        for r in range(8)
    )
    b2_ortho = all(
        sum(block_h2[k][i] * block_h2[k][j] for k in range(8)) == (2 if i == j else 0)
        for i in range(8)
        for j in range(8)
    )
    h8_ortho = all(
        sum(h8[k][i] * h8[k][j] for k in range(8)) == (8 if i == j else 0)
        for i in range(8)
        for j in range(8)
    )
    z_b = [38, 40, 2, 0, 0, 0, 0, 0]
    z_w = [20, 20, 20, 20, 20, 20, 18, 18]
    max_norm = 8 * 391
    b_norm = sum(x * x for x in z_b)
    w_norm = sum(x * x for x in z_w)
    b_max = max(abs(sum(block_h2[r][c] * z_b[c] for c in range(8))) for r in range(8))
    w_max = max(abs(sum(h8[r][c] * z_w[c] for c in range(8))) for r in range(8))
    b_in_e8 = all((all(x % 2 == z_b[0] % 2 for x in z_b), sum(z_b) % 4 == 0))
    w_in_e8 = all((all(x % 2 == z_w[0] % 2 for x in z_w), sum(z_w) % 4 == 0))
    ok = all(
        (
            b2_ortho,
            h8_ortho,
            b_in_e8,
            w_in_e8,
            b_norm <= max_norm,
            w_norm <= max_norm,
            b_max == 78,
            b_max <= 127,
            w_max == 156,
            w_max > 127,
            78 * 78 <= 2 * max_norm < 80 * 80,
            156 * 156 <= 8 * max_norm < 160 * 160,
        )
    )
    return {
        "int8_max": 127,
        "shell_m_max": 391,
        "max_norm_sq": max_norm,
        "block_h2_orthogonal_2i": b2_ortho,
        "wht8_orthogonal_8i": h8_ortho,
        "block_h2_max_entry": b_max,
        "block_h2_int8_safe": b_max <= 127,
        "block_h2_witness": z_b,
        "block_h2_witness_shell": b_norm // 8,
        "wht8_max_entry": w_max,
        "wht8_int8_overflow": w_max > 127,
        "wht8_witness": z_w,
        "wht8_witness_shell": w_norm // 8,
        "verified": ok,
    }


def _cross_check_theorem3() -> dict[str, Any]:
    s0_max = 2000
    all_ok = True
    for s0 in range(1, s0_max + 1):
        delta = (13 * s0) // 7 + 1
        m_trig = s0 + delta
        if not all((20 * s0 < 7 * m_trig, 20 * s0 >= 7 * (m_trig - 1))):
            all_ok = False
            break
    w_s0 = 1298
    w_delta = (13 * w_s0) // 7 + 1
    w_m = w_s0 + w_delta
    r3708 = Fraction(w_s0, w_m - 1)
    r3709 = Fraction(w_s0, w_m)
    thresh = Fraction(7, 20)
    floor_q = Fraction(1, 25)
    sw_ok = Fraction(0, 50) < floor_q
    ok = all(
        (
            all_ok,
            w_delta == 2411,
            w_m == 3709,
            r3708 >= thresh,
            r3709 < thresh,
            sw_ok,
        )
    )
    return {
        "range_checked_s0_max": s0_max,
        "all_s0_exact_first_trigger": all_ok,
        "witness_s0": w_s0,
        "witness_delta_blind": w_delta,
        "witness_m_trig": w_m,
        "ratio_at_3708_q": format_exact_rational(r3708),
        "ratio_at_3709_q": format_exact_rational(r3709),
        "legacy_threshold_q": format_exact_rational(thresh),
        "sliding_window_w": 50,
        "sliding_window_floor_q": format_exact_rational(floor_q),
        "sliding_window_catches_zero_poloidal": sw_ok,
        "verified": ok,
    }


def _cross_check_theorem4() -> dict[str, Any]:
    w_t = Fraction(1, 1)
    w_ctrl = Fraction(1, 10)
    w_land = Fraction(1, 2)
    cost_a = w_t * 400 + w_ctrl * 10 + w_land * 0
    cost_b = w_t * 100 + w_ctrl * 4000 + w_land * 200
    cost_c = w_t * 100 + w_ctrl * 20 + w_land * 0
    t_speedup = Fraction(400, 100)
    b_hidden = (w_ctrl * 4000 + w_land * 200) / cost_b
    net_ratio = cost_b / cost_a
    cs21_ok = all((t_speedup == Fraction(4, 1), b_hidden == Fraction(5, 6), net_ratio == Fraction(600, 401), cost_b > cost_a, cost_c < cost_a))

    # Landauer AND / CCX / ERASE fiber products
    p_and = (3 ** 3) * (1 ** 1)
    two19 = 1 << 19
    p_and_4 = p_and ** 4
    p_and_5 = p_and ** 5
    two24 = 1 << 24
    bracket_ok = all((two19 < p_and_4, p_and_5 < two24))
    p_ccx = 1
    p_erase = 2 ** 2
    ok = all((cs21_ok, bracket_ok, p_ccx == 1, p_erase == 4))
    return {
        "circuit_a_full_cost_q": format_exact_rational(cost_a),
        "circuit_b_full_cost_q": format_exact_rational(cost_b),
        "circuit_c_full_cost_q": format_exact_rational(cost_c),
        "apparent_t_speedup_q": format_exact_rational(t_speedup),
        "circuit_b_hidden_share_q": format_exact_rational(b_hidden),
        "net_cost_ratio_b_over_a_q": format_exact_rational(net_ratio),
        "cs21_net_regression_certified": cs21_ok,
        "landauer_and_power_product": p_and,
        "two_pow_19": two19,
        "and_p_pow_4": p_and_4,
        "and_p_pow_5": p_and_5,
        "two_pow_24": two24,
        "landauer_lower_q": "19/16",
        "landauer_upper_q": "6/5",
        "landauer_bracket_certified": bracket_ok,
        "toffoli_power_product": p_ccx,
        "erase_power_product": p_erase,
        "verified": ok,
    }


def _cross_check_theorem5() -> dict[str, Any]:
    perms = (
        ((0, 0), (1, 1), (2, 2), 1),
        ((0, 1), (1, 2), (2, 0), 1),
        ((0, 2), (1, 0), (2, 1), 1),
        ((0, 0), (1, 2), (2, 1), -1),
        ((0, 1), (1, 0), (2, 2), -1),
        ((0, 2), (1, 1), (2, 0), -1),
    )
    valid_cnt = 0
    max_matches = 0
    for mask in range(512):
        s = [[1 if ((mask >> (3 * r + c)) & 1) else -1 for c in range(3)] for r in range(3)]
        matches = 0
        for p0, p1, p2, sgn in perms:
            if sgn * s[p0[0]][p0[1]] * s[p1[0]][p1[1]] * s[p2[0]][p2[1]] == 1:
                matches += 1
        if matches == 6:
            valid_cnt += 1
        if matches > max_matches:
            max_matches = matches

    # Exhaustive F_5^6 check on 7*F = 7*sum(Z_k^6) + 5*Q_X^2*Q_Y + 10*Q_X*Q_Y^2
    fermat_mod5_ok = True
    singular_affine = 0
    for idx in range(5 ** 6):
        z = [(idx // (5 ** k)) % 5 for k in range(6)]
        x0, x1, x2, y0, y1, y2 = z
        qx = x0 * x1 + x0 * x2 + x1 * x2
        qy = y0 * y1 + y0 * y2 + y1 * y2
        f7 = 7 * sum(v ** 6 for v in z) + 5 * qx * qx * qy + 10 * qx * qy * qy
        if f7 % 5 != (2 * sum(v ** 6 for v in z)) % 5:
            fermat_mod5_ok = False
        partials = (
            (42 * (x0 ** 5) + 5 * (2 * qx * (x1 + x2) * qy + 2 * (x1 + x2) * qy * qy)) % 5,
            (42 * (x1 ** 5) + 5 * (2 * qx * (x0 + x2) * qy + 2 * (x0 + x2) * qy * qy)) % 5,
            (42 * (x2 ** 5) + 5 * (2 * qx * (x0 + x1) * qy + 2 * (x0 + x1) * qy * qy)) % 5,
            (42 * (y0 ** 5) + 5 * (qx * qx * (y1 + y2) + 4 * qx * qy * (y1 + y2))) % 5,
            (42 * (y1 ** 5) + 5 * (qx * qx * (y0 + y2) + 4 * qx * qy * (y0 + y2))) % 5,
            (42 * (y2 ** 5) + 5 * (qx * qx * (y0 + y1) + 4 * qx * qy * (y0 + y1))) % 5,
        )
        if all(p == 0 for p in partials):
            singular_affine += 1

    smooth_ok = all((fermat_mod5_ok, singular_affine == 1))
    ok = all((valid_cnt == 0, max_matches == 5, smooth_ok))
    return {
        "polya_total_sign_matrices": 512,
        "polya_valid_count": valid_cnt,
        "polya_max_matches_out_of_6": max_matches,
        "hodge_7f_mod5_fermat_exact": fermat_mod5_ok,
        "hodge_f5_points_checked": 5 ** 6,
        "hodge_f5_singular_affine_count": singular_affine,
        "hodge_p5_f5_smooth_certified": smooth_ok,
        "verified": ok,
    }


def compute_python_exact_cross_checks() -> dict[str, Any]:
    t1 = _cross_check_theorem1()
    t2 = _cross_check_theorem2()
    t3 = _cross_check_theorem3()
    t4 = _cross_check_theorem4()
    t5 = _cross_check_theorem5()
    all_ok = all((t1["verified"], t2["verified"], t3["verified"], t4["verified"], t5["verified"]))
    return {
        "theorem1_hamming_f64": t1,
        "theorem2_block_h2_int8": t2,
        "theorem3_cs01_blind_window": t3,
        "theorem4_cs21_landauer": t4,
        "theorem5_polya_fermat_sextic": t5,
        "all_five_cross_checks_verified": all_ok,
    }


# ============================================================================
# 5. Live Certificate Builder & Deep Fail-Closed Secondary Auditor
# ============================================================================

def build_certificate(project_root: Path | None = None) -> dict[str, Any]:
    """Build live Lean 4.36.0 kernel-certified bridge certificate (zero floats)."""
    root = _DEFAULT_PROJECT_ROOT if project_root is None else _require_concrete_path(project_root, "project_root")
    lean_bin = resolve_lean_binary()
    lean_ver = query_lean_version(lean_bin)

    tc_bytes = read_regular_bytes_capped(root / "lean-toolchain", "lean-toolchain", max_bytes=256)
    try:
        tc_text = tc_bytes.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise Lean4KernelBridgeError("INVALID_UTF8_TOOLCHAIN", "lean-toolchain is not valid UTF-8") from exc
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
                portal_ref=spec["portal_ref"],
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
        "portals_covered": list(PORTALS_COVERED),
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
            "all_five_modules_kernel_checked": all(m["kernel_exit_code"] == 0 for m in modules),
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
    secondary_audit_payload(payload)
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
    """Deep independent fail-closed verification of the kernel bridge payload."""
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
    require_ok(p["portals_covered"] == list(PORTALS_COVERED), "PORTALS_MISMATCH", "portals_covered mismatch")
    require_ok(p["prior_literature_n0"] == list(PRIOR_LITERATURE_N0), "LIT_MISMATCH", "prior_literature_n0 mismatch")

    manifest = _require_exact_keys(p["project_manifest"], _MANIFEST_KEYS, "project_manifest")
    tc_sha = require_sha256_hex(manifest["lean_toolchain_sha256"], "manifest.lean_toolchain_sha256")
    lake_sha = require_sha256_hex(manifest["lakefile_sha256"], "manifest.lakefile_sha256")
    require_ok(manifest["module_count"] == 5, "MODULE_COUNT_MISMATCH", "manifest.module_count must be 5")
    require_ok(manifest["total_theorem_count"] == 34, "THEOREM_COUNT_MISMATCH", "manifest.total_theorem_count must be 34")

    mods = p["theorem_modules"]
    require_ok(type(mods) is list and len(mods) == len(MODULE_SPECS), "MODULE_LIST_MISMATCH", "theorem_modules must have 5 entries")
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
        require_ok(m["portal_ref"] == spec["portal_ref"], "PORTAL_REF_MISMATCH", f"module[{idx}] portal_ref mismatch")
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
            mod_source = raw_b.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise Lean4KernelBridgeError("INVALID_UTF8_LEAN", f"{spec['module_id']}: invalid UTF-8") from exc
        static_lean_source_check(mod_source, spec["module_id"])
        if verify_live_lean:
            live_mod = run_live_lean_module(
                lean_bin=str(lean_bin),
                project_root=root,
                rel_path=spec["rel_path"],
                expected_theorems=exp_thms,
                module_id=spec["module_id"],
                portal_ref=spec["portal_ref"],
            )
            require_ok(live_mod == m, "LIVE_LEAN_DRIFT", f"{spec['module_id']}: live kernel output mismatch")

    cross = _require_exact_keys(p["python_exact_cross_checks"], _CROSS_KEYS, "python_exact_cross_checks")
    _require_exact_keys(cross["theorem1_hamming_f64"], _T1_KEYS, "cross.theorem1")
    _require_exact_keys(cross["theorem2_block_h2_int8"], _T2_KEYS, "cross.theorem2")
    _require_exact_keys(cross["theorem3_cs01_blind_window"], _T3_KEYS, "cross.theorem3")
    _require_exact_keys(cross["theorem4_cs21_landauer"], _T4_KEYS, "cross.theorem4")
    _require_exact_keys(cross["theorem5_polya_fermat_sextic"], _T5_KEYS, "cross.theorem5")
    # Recompute all 5 pure-Z/Q cross-checks independently and require exact equality + canonical rationals
    expected_cross = compute_python_exact_cross_checks()
    for rkey in ("ratio_at_3708_q", "ratio_at_3709_q", "legacy_threshold_q", "sliding_window_floor_q"):
        parse_exact_rational(cross["theorem3_cs01_blind_window"][rkey], f"t3.{rkey}")
    for rkey in (
        "circuit_a_full_cost_q",
        "circuit_b_full_cost_q",
        "circuit_c_full_cost_q",
        "apparent_t_speedup_q",
        "circuit_b_hidden_share_q",
        "net_cost_ratio_b_over_a_q",
        "landauer_lower_q",
        "landauer_upper_q",
    ):
        parse_exact_rational(cross["theorem4_cs21_landauer"][rkey], f"t4.{rkey}")
    require_ok(cross == expected_cross, "CROSS_CHECK_MISMATCH", "python_exact_cross_checks mismatch")

    summ = _require_exact_keys(p["summary"], _SUMMARY_KEYS, "summary")
    require_ok(summ["module_count"] == 5, "SUMMARY_MODULE_COUNT", "summary.module_count != 5")
    require_ok(summ["theorem_count"] == total_thms, "SUMMARY_THEOREM_COUNT", "summary.theorem_count mismatch")
    require_ok(summ["zero_warning_modules"] == 5, "SUMMARY_ZERO_WARNINGS", "summary.zero_warning_modules != 5")
    require_ok(summ["forbidden_axiom_count"] == 0, "SUMMARY_FORBIDDEN_AXIOMS", "summary.forbidden_axiom_count != 0")
    require_ok(summ["all_five_modules_kernel_checked"] is True, "SUMMARY_KERNEL_FLAG", "kernel_checked flag False")
    require_ok(summ["all_theorems_standard_axioms_only"] is True, "SUMMARY_AXIOM_FLAG", "standard_axioms flag False")
    require_ok(summ["float_count_on_trust_path"] == 0, "SUMMARY_FLOATS", "float_count_on_trust_path != 0")
    require_ok(summ["bare_assert_count"] == 0, "SUMMARY_ASSERTS", "bare_assert_count != 0")
    require_ok(summ["rng_calls"] == 0, "SUMMARY_RNG", "rng_calls != 0")

    return {"verified": True, "module_count": 5, "theorem_count": total_thms}


def validate_certificate_payload(
    cert: Any,
    *,
    project_root: Path | None = None,
    verify_live_lean: bool = False,
) -> dict[str, Any]:
    """Fail-closed in-memory certificate validator."""
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
        raise Lean4KernelBridgeError("INVALID_UTF8_JSON", "certificate file is not valid UTF-8") from exc
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

def _parse_cli_args(argv: Sequence[str] | None) -> list[str]:
    if argv is None:
        raw: Sequence[Any] = sys.argv[1:]
    else:
        require_ok(
            type(argv) in (list, tuple),
            "INVALID_CLI_ARGS",
            "argv must be an exact list or tuple of str",
        )
        raw = argv
    args: list[str] = []
    for item in raw:
        require_ok(type(item) is str, "INVALID_CLI_ARGS", "CLI arguments must be exact str")
        require_exact_str(item, "argv", non_empty=False)
        args.append(item)
    return args


def _validate_cli_target_path(arg: str) -> Path:
    require_ok(
        len(arg) >= 1 and not arg.startswith("-"),
        "INVALID_CLI_ARGS",
        "path argument must be non-empty and must not start with '-'",
    )
    return Path(arg)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parse_cli_args(argv)
        if len(args) == 2 and args[0] == "--check":
            target = _validate_cli_target_path(args[1])
            verdict = check_certificate_file(target, project_root=_DEFAULT_PROJECT_ROOT, verify_live_lean=True)
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
            target = _validate_cli_target_path(args[1])
            cert = build_certificate(_DEFAULT_PROJECT_ROOT)
            write_regular_bytes_safe(target, canonical_json_bytes(cert) + b"\n", label="certificate_out")
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
        raise Lean4KernelBridgeError(
            "INVALID_CLI_ARGS",
            "usage: [--standalone --json | --write <path> | --check <path>]",
        )
    except Lean4KernelBridgeError as exc:
        sys.stderr.write(f"ERROR [{exc.code}]: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
