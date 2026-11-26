#!/usr/bin/env python3
"""Pure-Z/Q Exact-Operator Oracle & Hardened Lean 4 Static Proof-Envelope Gate.

Implements:
  1. Strict exact-type, integer, canonical rational, and JSON tree primitives (zero floats).
  2. Complete Lean 4 static proof-envelope gate (nested block comments, line comments,
     Char literals, raw r"..."/r#"..."# strings, interpolated s!"{...}" strings,
     French-guillemet identifier normalization, single-pass O(n) balanced-paren decide
     native-escape scanner with fail-closed record allowlist, and Init/Std import guard).
  3. Pillar 1 pure-Q competing-potential scale-flip oracle over frozen 0.36B/0.5B/1.5B
     quantization receipts plus explicit non-commutativity obstruction record.
  4. Pillar 2 pure-Z/Q endoreversible Jensen / race-to-sleep / parallel concurrency
     impedance analyzer over live integer RAPL hardware probe data.
"""
from __future__ import annotations

from fractions import Fraction
import json
import math
import re
from typing import Any, Sequence

MAX_INT_BITS = 4096
MAX_INT_DIGITS = 1234
MAX_STR_LEN = 262_144
MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 16_384
MAX_LEAN_BYTES = 1_048_576
_SHA256_HEX_CHARS = frozenset("0123456789abcdef")

STANDARD_LEAN4_AXIOMS: frozenset[str] = frozenset(
    {"propext", "Classical.choice", "Quot.sound"}
)

# Frozen 10^9-scaled exact rational KL receipts (4,088 tokens per corpus; zero floats).
FROZEN_LLM_PROVENANCE: dict[str, str] = {
    "smollm360m_qwen05b_json_sha256": (
        "42ad90b1ddfba30d3d99b9d0a7a624770192b084dbe86b1e51c3a747cb7181e7"
    ),
    "qwen15b_json_sha256": (
        "9155e1b679c7019cf49071ef27bfae7b3e4f77c21d099b2ff9c9f4ddb90cf27b"
    ),
}

FROZEN_SCALE_KL_NANO: tuple[dict[str, Any], ...] = (
    {
        "model_id": "HuggingFaceTB/SmolLM2-360M",
        "scale_label": "0.36B",
        "block_weights": 314_572_800,
        "group_size": 32,
        "wikitext2": {
            "A16_axis": 65_173_014,
            "A16_BlockH2": 71_701_656,
            "A16_H16": 79_846_518,
        },
        "python": {
            "A16_axis": 56_725_239,
            "A16_BlockH2": 59_324_707,
            "A16_H16": 69_955_577,
        },
    },
    {
        "model_id": "Qwen/Qwen2.5-0.5B",
        "scale_label": "0.5B",
        "block_weights": 357_826_560,
        "group_size": 128,
        "wikitext2": {
            "A16_axis": 52_525_288,
            "A16_BlockH2": 55_205_609,
            "A16_H16": 57_613_895,
        },
        "python": {
            "A16_axis": 45_602_059,
            "A16_BlockH2": 45_392_023,
            "A16_H16": 47_448_949,
        },
    },
    {
        "model_id": "Qwen/Qwen2.5-1.5B",
        "scale_label": "1.5B",
        "block_weights": 1_310_195_712,
        "group_size": 128,
        "wikitext2": {
            "A16_axis": 50_062_401,
            "A16_BlockH2": 45_647_596,
            "A16_H16": 48_376_358,
        },
        "python": {
            "A16_axis": 31_973_308,
            "A16_BlockH2": 30_310_450,
            "A16_H16": 30_465_967,
        },
    },
)

NON_COMMUTATIVITY_OBSTRUCTION: dict[str, Any] = {
    "commuting_operator_class": "two_term_scalar_competing_potential_sign_inversion",
    "shared_exact_law": (
        "Delta(s) = R(s) - A(s) flips sign strictly from repulsion (>0) to net pull (<0) "
        "once coupling ratio A/R crosses unity; reduced-barrier bridge B dominates across "
        "and past the crossover band whenever rho_B * gamma_H < rho_H * gamma_B."
    ),
    "obstruction_domain": "nuclear_su3_confinement_and_wkb_quantum_tunneling",
    "obstruction_reasons": [
        "Non-Abelian SU(3) color-gauge curvature and running coupling have no morphism into real Euclidean lattice quantization.",
        "WKB quantum tunneling relies on complex-phase wavefunction amplitude interference absent from deterministic real integer rounding.",
        "Therefore the cross-domain isomorphism holds strictly at the scalar competing-potential operator level and fails at the microscopic gauge/quantum-phase level.",
    ],
}

_EXP_A_EXPECTED_ARMS: tuple[tuple[str, int, int], ...] = (
    ("race_to_sleep_free", 1, 0),
    ("bursty_1_pulse_1500ms", 1, 1500),
    ("bursty_4_pulses_1500ms", 4, 1500),
    ("paced_40_slices_1500ms", 40, 1500),
    ("paced_100_slices_1500ms", 100, 1500),
)
_EXP_B_EXPECTED_THREADS: tuple[int, ...] = (1, 2, 4, 6, 8, 12, 16)

_MEAS_KEYS: frozenset[str] = frozenset(
    {
        "wall_us",
        "pkg_uj",
        "core_uj",
        "uncore_uj",
        "psys_uj",
        "freq_khz_start",
        "freq_khz_end",
        "temp_mc_end",
        "checksum_hex",
    }
)
_PROBE_KEYS: frozenset[str] = frozenset(
    {
        "schema",
        "measured_live_silicon",
        "host_cpu_model",
        "rapl_max_energy_range_uj",
        "tile_words_u64",
        "inner_rounds",
        "ops_per_block",
        "exp_a_total_blocks",
        "exp_a_total_ops",
        "exp_a_window_ms",
        "exp_a_threads",
        "exp_b_total_blocks",
        "exp_b_total_ops",
        "idle_pre_1500ms",
        "idle_post_1500ms",
        "exp_a_pacing_vs_bursty",
        "exp_b_concurrency_impedance",
    }
)

# ----------------------------------------------------------------------------
# Hardened Lean 4 Static Proof-Envelope Regexes
# ----------------------------------------------------------------------------
_LEAN4_IDENT_EXTRA = "_.'!?"
_LEAN4_HARD_LINE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
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
)
_LEAN4_PARTIAL_DECL_RE = re.compile(
    r"(?<!\.)\bpartial\s+(?:def|instance|abbrev)\b", flags=re.DOTALL
)
_LEAN4_GUILLEMET_IDENT_RE = re.compile(r"«([A-Za-z_][A-Za-z0-9_']*)»")
_LEAN4_DECIDE_KW_RE = re.compile(r"\bdecide\b")
_LEAN4_FLAG_TOK_RE = re.compile(r"[+-][A-Za-z0-9_]+")
_LEAN4_OPT_PREFIX_RE = re.compile(r"\s*([A-Za-z0-9_]+)\s*:=")
_LEAN4_CONFIG_NATIVE_RE = re.compile(r"\bnative\b(?:\s*:=\s*([^},]*))?")
_LEAN4_CONFIG_AFTER_COMMA_RE = re.compile(r",\s*(?:\Z|[A-Za-z_][A-Za-z0-9_']*\s*:=)")
_LEAN4_CONFIG_WITH_RE = re.compile(r"\bwith\b")
_LEAN4_DECIDE_CONFIG_BIND_RE = re.compile(
    r"\b(?:DecideConfig|Decide\.Config)\b[ \t)]*:=\s*(?:\(\s*)*\{[^}{]*\bnative\s*:=\s*([^}{,]*)(?:,[^}{]*)?\}"
    r"|\{[^}{]*\bnative\s*:=\s*([^}{,]*)(?:,[^}{]*)?\}\s*:\s*(?:[A-Za-z_][A-Za-z0-9_]*\.)*(?:DecideConfig|Decide\.Config)\b"
    r"|\{[^}{]*\bnative\s*:=\s*([^}{,:]*)(?:,[^}{]*)?:\s*(?:[A-Za-z_][A-Za-z0-9_]*\.)*(?:DecideConfig|Decide\.Config)\b[^}{]*\}",
    flags=re.DOTALL,
)
_LEAN4_SKIP_KERNEL_TC_RE = re.compile(r"\bdebug\s*\.\s*skipKernelTC\b", flags=re.DOTALL)
_LEAN4_HARD_ATTR_RE = re.compile(
    r"@\[[^\]]*\b(?:extern|implemented_by)\b[^\]]*\]", flags=re.DOTALL
)
_LEAN4_IMPORT_FULL_RE = re.compile(
    r"(?:^|\n)[ \t]*(?:(?:public|private|meta)\s+)*import\s+([A-Za-z0-9_.]+)",
    flags=re.DOTALL,
)


class TwoWayTransferError(ValueError):
    """Typed fail-closed error for all algebraic, Lean 4, and I/O checks."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


# ============================================================================
# 1. Exact Type, Integer, Rational & Strict JSON Primitives (Zero Floats)
# ============================================================================

def require_ok(cond: Any, code: str, message: str) -> None:
    if type(cond) is not bool:
        raise TwoWayTransferError("INVALID_CONDITION_TYPE", f"{code}: condition must be exact bool")
    if not cond:
        raise TwoWayTransferError(code, message)


def require_exact_bool(val: Any, label: str) -> bool:
    if type(val) is not bool:
        raise TwoWayTransferError("INVALID_BOOL_TYPE", f"{label}: exact bool required")
    return val


def require_exact_int(
    val: Any,
    label: str,
    *,
    lo: int | None = None,
    hi: int | None = None,
) -> int:
    if type(val) is not int:
        raise TwoWayTransferError("INVALID_INT_TYPE", f"{label}: exact int required")
    if val.bit_length() > MAX_INT_BITS:
        raise TwoWayTransferError("INT_BIT_LIMIT", f"{label}: exceeds {MAX_INT_BITS} bits")
    if lo is not None:
        if type(lo) is not int:
            raise TwoWayTransferError("INVALID_BOUND_TYPE", f"{label}: lo must be exact int")
        if val < lo:
            raise TwoWayTransferError("INT_OUT_OF_RANGE", f"{label}: {val} < {lo}")
    if hi is not None:
        if type(hi) is not int:
            raise TwoWayTransferError("INVALID_BOUND_TYPE", f"{label}: hi must be exact int")
        if val > hi:
            raise TwoWayTransferError("INT_OUT_OF_RANGE", f"{label}: {val} > {hi}")
    return val


def require_exact_str(
    val: Any,
    label: str,
    *,
    max_len: int = MAX_STR_LEN,
    non_empty: bool = True,
) -> str:
    if type(val) is not str:
        raise TwoWayTransferError("INVALID_STR", f"{label}: exact str required")
    if "\x00" in val:
        raise TwoWayTransferError("NUL_BYTE_FORBIDDEN", f"{label}: NUL byte forbidden")
    if non_empty and len(val) == 0:
        raise TwoWayTransferError("EMPTY_STR", f"{label}: empty string forbidden")
    if len(val) > max_len:
        raise TwoWayTransferError("STR_TOO_LONG", f"{label}: exceeds max_len={max_len}")
    try:
        val.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise TwoWayTransferError("INVALID_UTF8_SURROGATE", f"{label}: lone UTF-16 surrogate forbidden") from exc
    return val


def require_sha256_hex(val: Any, label: str) -> str:
    s = require_exact_str(val, label, max_len=64, non_empty=True)
    if len(s) != 64 or not all(ch in _SHA256_HEX_CHARS for ch in s):
        raise TwoWayTransferError("INVALID_SHA256", f"{label}: must be 64 lowercase ASCII hex chars")
    return s


def require_hex16(val: Any, label: str) -> str:
    s = require_exact_str(val, label, max_len=16, non_empty=True)
    if len(s) != 16 or not all(ch in _SHA256_HEX_CHARS for ch in s):
        raise TwoWayTransferError("INVALID_HEX16", f"{label}: must be 16 lowercase ASCII hex chars")
    return s


def parse_exact_int_ascii(text: str, label: str) -> int:
    s = require_exact_str(text, label, max_len=MAX_INT_DIGITS + 2, non_empty=True)
    neg = s.startswith("-")
    digits = s[1:] if neg else s
    if len(digits) == 0 or not all("0" <= c <= "9" for c in digits):
        raise TwoWayTransferError("INVALID_INT_ASCII", f"{label}: non-ASCII-digit integer")
    if len(digits) > MAX_INT_DIGITS:
        raise TwoWayTransferError("INT_DIGIT_LIMIT", f"{label}: exceeds {MAX_INT_DIGITS} digits")
    if len(digits) > 1 and digits[0] == "0":
        raise TwoWayTransferError("LEADING_ZERO_FORBIDDEN", f"{label}: leading zero forbidden")
    if neg and digits == "0":
        raise TwoWayTransferError("NEG_ZERO_FORBIDDEN", f"{label}: negative zero forbidden")
    val = -int(digits) if neg else int(digits)
    return require_exact_int(val, label)


def format_exact_rational(q: Fraction) -> str:
    if type(q) is not Fraction:
        raise TwoWayTransferError("INVALID_FRACTION_TYPE", "exact Fraction required")
    require_exact_int(q.numerator, "q.numerator")
    require_exact_int(q.denominator, "q.denominator", lo=1)
    if q.denominator == 1:
        return str(q.numerator)
    return f"{q.numerator}/{q.denominator}"


def parse_exact_rational(text: str, label: str) -> Fraction:
    s = require_exact_str(text, label, max_len=2 * MAX_INT_DIGITS + 4, non_empty=True)
    if "/" not in s:
        return Fraction(parse_exact_int_ascii(s, label), 1)
    parts = s.split("/")
    if len(parts) != 2:
        raise TwoWayTransferError("INVALID_RATIONAL", f"{label}: multiple slashes")
    num = parse_exact_int_ascii(parts[0], f"{label}.num")
    den = parse_exact_int_ascii(parts[1], f"{label}.den")
    if den <= 1:
        raise TwoWayTransferError("NON_CANONICAL_RATIONAL", f"{label}: denominator must be >= 2")
    if math.gcd(abs(num), den) != 1:
        raise TwoWayTransferError("NON_REDUCED_RATIONAL", f"{label}: fraction not in lowest terms")
    return Fraction(num, den)


def validate_json_tree(obj: Any, label: str = "json") -> None:
    """Iterative depth-bounded exact-type JSON AST validator (zero floats, zero subclasses)."""
    stack: list[tuple[Any, int, str]] = [(obj, 0, label)]
    visited = 0
    while stack:
        cur, depth, path = stack.pop()
        visited += 1
        if visited > MAX_JSON_NODES:
            raise TwoWayTransferError("JSON_NODE_LIMIT", f"{path}: exceeds {MAX_JSON_NODES} nodes")
        if depth > MAX_JSON_DEPTH:
            raise TwoWayTransferError("JSON_DEPTH_LIMIT", f"{path}: exceeds depth {MAX_JSON_DEPTH}")
        t = type(cur)
        if t is dict:
            for k, v in cur.items():
                ks = require_exact_str(k, f"{path}.<key>", non_empty=True)
                stack.append((v, depth + 1, f"{path}.{ks}"))
        elif t is list:
            for idx, item in enumerate(cur):
                stack.append((item, depth + 1, f"{path}[{idx}]"))
        elif t is str:
            require_exact_str(cur, path, non_empty=False)
        elif t is int:
            require_exact_int(cur, path)
        elif t is bool or cur is None:
            continue
        elif t is float:
            raise TwoWayTransferError("FLOAT_FORBIDDEN", f"{path}: IEEE-754 float forbidden")
        else:
            raise TwoWayTransferError("INVALID_JSON_TYPE", f"{path}: disallowed type {t.__name__}")


def _reject_float_token(raw: str) -> Any:
    raise TwoWayTransferError("FLOAT_FORBIDDEN", f"JSON float token forbidden: {raw[:32]}")


def _reject_const_token(raw: str) -> Any:
    raise TwoWayTransferError("JSON_CONST_FORBIDDEN", f"JSON non-standard constant forbidden: {raw[:32]}")


def _parse_int_token(raw: str) -> int:
    return parse_exact_int_ascii(raw, "json_int")


def _no_dup_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise TwoWayTransferError("DUPLICATE_JSON_KEY", f"duplicate JSON key: {k!r}")
        out[k] = v
    return out


def parse_strict_json_text(text: str, *, require_object: bool = True, label: str = "json") -> Any:
    s = require_exact_str(text, label, max_len=2_097_152, non_empty=True)
    try:
        obj = json.loads(
            s,
            parse_float=_reject_float_token,
            parse_constant=_reject_const_token,
            parse_int=_parse_int_token,
            object_pairs_hook=_no_dup_pairs,
        )
    except TwoWayTransferError:
        raise
    except RecursionError as exc:
        raise TwoWayTransferError("JSON_DEPTH_LIMIT", f"{label}: recursion depth exceeded") from exc
    except ValueError as exc:
        raise TwoWayTransferError("JSON_PARSE_ERROR", f"{label}: invalid JSON ({exc})") from exc
    validate_json_tree(obj, label)
    if require_object and type(obj) is not dict:
        raise TwoWayTransferError("JSON_OBJECT_REQUIRED", f"{label}: top-level JSON object required")
    return obj


def canonical_json_bytes(obj: Any, label: str = "json") -> bytes:
    validate_json_tree(obj, label)
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return text.encode("ascii")


def require_exact_keys(obj: Any, expected: frozenset[str], label: str) -> dict[str, Any]:
    require_ok(type(obj) is dict, "INVALID_DICT", f"{label}: exact dict required")
    require_ok(frozenset(obj.keys()) == expected, "KEYSET_MISMATCH", f"{label}: exact keyset mismatch")
    return obj


# ============================================================================
# 2. Hardened Lean 4 Static Proof-Envelope Gate (Char / Raw / Interp / Decide)
# ============================================================================

def _strip_lean4_with_report(source: str, label: str = "lean") -> str:
    """Char-literal-safe, raw-string-safe (r"..."/r#"..."#), interpolated-string-safe
    (s!"{...}"/m!"{...}"/f!"{...}"), and nested-block-comment-safe Lean 4 stripper.
    Raises TwoWayTransferError fail-closed on unterminated comments or strings."""
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
        elif ch == "r" and (i == 0 or not (s[i - 1].isalnum() or s[i - 1] in _LEAN4_IDENT_EXTRA)):
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
            and (i == 1 or not (s[i - 2].isalnum() or s[i - 2] in _LEAN4_IDENT_EXTRA))
        ):
            in_interp = True
            out.append("  ")
            i += 2
        elif ch == '"':
            in_str = True
            out.append(" ")
            i += 1
        elif ch == "'":
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
        not (in_str or in_interp or raw_hashes >= 0 or len(interp_stack) > 0),
        "LEAN4_UNTERMINATED_STRING",
        f"{label}: unterminated string literal",
    )
    return "".join(out)


def _is_lean4_native_rhs_false_span(text: str, lo: int, hi: int) -> bool:
    while True:
        while lo != hi and text[lo].isspace():
            lo += 1
        while hi != lo and text[hi - 1].isspace():
            hi -= 1
        if hi - lo >= 7 and text[lo] == "(" and text[hi - 1] == ")":
            lo += 1
            hi -= 1
            continue
        break
    rem = text[lo:hi] if hi - lo <= 10 else ""
    return rem in ("false", "Bool.false")


def _is_lean4_safe_config_span(
    text: str,
    lo: int,
    hi: int,
    match_rparen: dict[int, int],
) -> bool:
    while True:
        while lo != hi and text[lo].isspace():
            lo += 1
        while hi != lo and text[hi - 1].isspace():
            hi -= 1
        if match_rparen.get(lo) == hi - 1:
            lo += 1
            hi -= 1
            continue
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
    for m_dc in _LEAN4_DECIDE_CONFIG_BIND_RE.finditer(cleaned):
        for g_idx in (1, 2, 3):
            grp = m_dc.group(g_idx)
            if grp is not None and not _is_lean4_native_rhs_false_span(grp, 0, len(grp)):
                return True
    n = len(cleaned)
    match_rparen: dict[int, int] | None = None
    for m_dec in _LEAN4_DECIDE_KW_RE.finditer(cleaned):
        pos = m_dec.end()
        while True:
            ws = pos
            while ws != n and cleaned[ws].isspace():
                ws += 1
            if ws == n:
                break
            ch = cleaned[ws]
            if ch in "+-":
                m_flag = _LEAN4_FLAG_TOK_RE.match(cleaned, ws)
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
                m_pfx = _LEAN4_OPT_PREFIX_RE.match(cleaned, ws + 1, close_idx)
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


def static_lean4_source_check(source: str, label: str = "lean") -> None:
    """Fail-closed static proof-envelope pre-filter on pure-Init Lean 4 source."""
    cleaned = _LEAN4_GUILLEMET_IDENT_RE.sub(r"\1", _strip_lean4_with_report(source, label))
    for pat, code in _LEAN4_HARD_LINE_RULES:
        require_ok(pat.search(cleaned) is None, code, f"{label}: forbidden token matched {code}")
    require_ok(
        _LEAN4_SKIP_KERNEL_TC_RE.search(cleaned) is None,
        "LEAN4_SKIP_KERNEL_TC",
        f"{label}: debug.skipKernelTC forbidden",
    )
    require_ok(
        _LEAN4_HARD_ATTR_RE.search(cleaned) is None,
        "LEAN4_ATTR_ESCAPE",
        f"{label}: extern/implemented_by attribute escape forbidden",
    )
    require_ok(
        _LEAN4_PARTIAL_DECL_RE.search(cleaned) is None,
        "LEAN4_PARTIAL",
        f"{label}: partial declaration forbidden",
    )
    require_ok(
        not _has_lean4_decide_native(cleaned),
        "LEAN4_DECIDE_NATIVE",
        f"{label}: decide native-evaluation escape forbidden",
    )
    for m_imp in _LEAN4_IMPORT_FULL_RE.finditer(cleaned):
        mod = m_imp.group(1)
        root_pkg = mod.split(".")[0]
        require_ok(
            root_pkg in ("Init", "Std"),
            "LEAN4_NON_INIT_IMPORT",
            f"{label}: disallowed non-Init/Std import '{mod}'",
        )


# ============================================================================
# 3. Pillar 1: Exact Competing-Potential Scale-Flip Oracle (Frozen Receipts)
# ============================================================================

def analyze_competing_potential_scale_flip(
    scale_entries: Sequence[dict[str, Any]] = FROZEN_SCALE_KL_NANO,
) -> dict[str, Any]:
    """Exact pure-Q analysis of A16_H16 & A16_BlockH2 vs. A16_axis across 0.36B -> 0.5B -> 1.5B."""
    scale = 1_000_000_000
    rows: list[dict[str, Any]] = []
    wt2_h16_deltas: list[Fraction] = []
    py_h16_deltas: list[Fraction] = []
    py_05b_sub_barrier = False
    all_bh2_beats_h16 = True

    for entry in scale_entries:
        row: dict[str, Any] = {
            "model_id": entry["model_id"],
            "scale_label": entry["scale_label"],
            "block_weights": entry["block_weights"],
            "group_size": entry["group_size"],
        }
        for split in ("python", "wikitext2"):
            sp = entry[split]
            ax = Fraction(sp["A16_axis"], scale)
            bh = Fraction(sp["A16_BlockH2"], scale)
            h16 = Fraction(sp["A16_H16"], scale)
            d_h16 = h16 - ax
            d_bh = bh - ax
            rel_h16_pct = (d_h16 * 100) / ax
            rel_bh_pct = (d_bh * 100) / ax
            if bh >= h16:
                all_bh2_beats_h16 = False
            if entry["scale_label"] == "0.5B" and split == "python":
                py_05b_sub_barrier = (d_bh < 0) and (d_h16 > 0)
            if split == "wikitext2":
                wt2_h16_deltas.append(d_h16)
            else:
                py_h16_deltas.append(d_h16)
            row[split] = {
                "a16_axis_kl_q": format_exact_rational(ax),
                "a16_block_h2_kl_q": format_exact_rational(bh),
                "a16_h16_kl_q": format_exact_rational(h16),
                "h16_minus_axis_q": format_exact_rational(d_h16),
                "block_h2_minus_axis_q": format_exact_rational(d_bh),
                "block_h2_minus_h16_q": format_exact_rational(bh - h16),
                "h16_rel_pct_q": format_exact_rational(rel_h16_pct),
                "block_h2_rel_pct_q": format_exact_rational(rel_bh_pct),
            }
        rows.append(row)

    wt2_flip = (wt2_h16_deltas[0] > 0) and (wt2_h16_deltas[1] > 0) and (wt2_h16_deltas[2] < 0)
    py_flip = (py_h16_deltas[0] > 0) and (py_h16_deltas[1] > 0) and (py_h16_deltas[2] < 0)
    return {
        "frozen_receipt_provenance": dict(FROZEN_LLM_PROVENANCE),
        "scale_trajectories": rows,
        "wikitext2_h16_sign_inversion": wt2_flip,
        "python_h16_sign_inversion": py_flip,
        "python_05b_strict_sub_barrier_band": py_05b_sub_barrier,
        "block_h2_beats_h16_all_scales": all_bh2_beats_h16,
        "non_commutativity_obstruction": {
            "commuting_operator_class": NON_COMMUTATIVITY_OBSTRUCTION["commuting_operator_class"],
            "shared_exact_law": NON_COMMUTATIVITY_OBSTRUCTION["shared_exact_law"],
            "obstruction_domain": NON_COMMUTATIVITY_OBSTRUCTION["obstruction_domain"],
            "obstruction_reasons": list(NON_COMMUTATIVITY_OBSTRUCTION["obstruction_reasons"]),
        },
    }


# ============================================================================
# 4. Pillar 2: Exact Pure-Z/Q Live Silicon Hardware Probe Analyzer
# ============================================================================

def _validate_measurement(obj: Any, label: str) -> dict[str, Any]:
    m = require_exact_keys(obj, _MEAS_KEYS, label)
    return {
        "wall_us": require_exact_int(m["wall_us"], f"{label}.wall_us", lo=1),
        "pkg_uj": require_exact_int(m["pkg_uj"], f"{label}.pkg_uj", lo=1),
        "core_uj": require_exact_int(m["core_uj"], f"{label}.core_uj", lo=0),
        "uncore_uj": require_exact_int(m["uncore_uj"], f"{label}.uncore_uj", lo=0),
        "psys_uj": require_exact_int(m["psys_uj"], f"{label}.psys_uj", lo=1),
        "freq_khz_start": require_exact_int(m["freq_khz_start"], f"{label}.freq_khz_start", lo=-1),
        "freq_khz_end": require_exact_int(m["freq_khz_end"], f"{label}.freq_khz_end", lo=-1),
        "temp_mc_end": require_exact_int(m["temp_mc_end"], f"{label}.temp_mc_end", lo=-1),
        "checksum_hex": require_hex16(m["checksum_hex"], f"{label}.checksum_hex"),
    }


def _sum_trials(trials: Sequence[dict[str, Any]]) -> dict[str, int]:
    return {
        "wall_us": sum(t["wall_us"] for t in trials),
        "pkg_uj": sum(t["pkg_uj"] for t in trials),
        "core_uj": sum(t["core_uj"] for t in trials),
        "uncore_uj": sum(t["uncore_uj"] for t in trials),
        "psys_uj": sum(t["psys_uj"] for t in trials),
    }


def analyze_live_silicon_probe(probe_data: Any) -> dict[str, Any]:
    """Deterministically analyze raw integer RAPL silicon measurements purely in Z/Q."""
    validate_json_tree(probe_data, "live_probe")
    d = require_exact_keys(probe_data, _PROBE_KEYS, "live_probe")
    require_ok(
        d["schema"] == "aletheia.track_s65_live_silicon_probe.v1",
        "PROBE_SCHEMA_MISMATCH",
        "live_probe.schema mismatch",
    )
    require_ok(
        require_exact_bool(d["measured_live_silicon"], "measured_live_silicon") is True,
        "MEASURED_FLAG_FALSE",
        "measured_live_silicon must be True",
    )
    host_cpu = require_exact_str(d["host_cpu_model"], "host_cpu_model")
    rapl_max = require_exact_int(d["rapl_max_energy_range_uj"], "rapl_max_energy_range_uj", lo=1)
    tile_words = require_exact_int(d["tile_words_u64"], "tile_words_u64", lo=64)
    inner_rounds = require_exact_int(d["inner_rounds"], "inner_rounds", lo=1)
    ops_per_block = require_exact_int(d["ops_per_block"], "ops_per_block", lo=1)
    require_ok(
        ops_per_block == tile_words * inner_rounds * 4,
        "OPS_PER_BLOCK_MISMATCH",
        "ops_per_block != tile_words * inner_rounds * 4",
    )

    wa_blocks = require_exact_int(d["exp_a_total_blocks"], "exp_a_total_blocks", lo=800)
    require_ok(wa_blocks % 800 == 0, "EXP_A_DIVISIBILITY", "exp_a_total_blocks must divide by 800")
    wa_ops = require_exact_int(d["exp_a_total_ops"], "exp_a_total_ops", lo=1)
    require_ok(wa_ops == wa_blocks * ops_per_block, "EXP_A_OPS_MISMATCH", "exp_a_total_ops mismatch")
    win_a_ms = require_exact_int(d["exp_a_window_ms"], "exp_a_window_ms", lo=100)
    a_threads = require_exact_int(d["exp_a_threads"], "exp_a_threads", lo=1, hi=16)

    wb_blocks = require_exact_int(d["exp_b_total_blocks"], "exp_b_total_blocks", lo=480)
    require_ok(wb_blocks % 480 == 0, "EXP_B_DIVISIBILITY", "exp_b_total_blocks must divide by 480")
    wb_ops = require_exact_int(d["exp_b_total_ops"], "exp_b_total_ops", lo=1)
    require_ok(wb_ops == wb_blocks * ops_per_block, "EXP_B_OPS_MISMATCH", "exp_b_total_ops mismatch")

    idle_pre = _validate_measurement(d["idle_pre_1500ms"], "idle_pre_1500ms")
    idle_post = _validate_measurement(d["idle_post_1500ms"], "idle_post_1500ms")
    idle_sum = _sum_trials((idle_pre, idle_post))
    # Exact idle power in Watts = sum_uj / sum_us (since uJ / us = W!)
    idle_pkg_w_q = Fraction(idle_sum["pkg_uj"], idle_sum["wall_us"])
    idle_psys_w_q = Fraction(idle_sum["psys_uj"], idle_sum["wall_us"])

    raw_a = d["exp_a_pacing_vs_bursty"]
    require_ok(
        type(raw_a) is list and len(raw_a) == len(_EXP_A_EXPECTED_ARMS),
        "EXP_A_LEN_MISMATCH",
        "exp_a_pacing_vs_bursty must have 5 arms",
    )
    a_rows: list[dict[str, Any]] = []
    a_checksums: set[str] = set()
    a_pkg_mj_map: dict[str, Fraction] = {}
    a_psys_mj_map: dict[str, Fraction] = {}
    for idx, (entry, (exp_arm, exp_slices, exp_win)) in enumerate(zip(raw_a, _EXP_A_EXPECTED_ARMS)):
        e = require_exact_keys(entry, frozenset({"arm", "slices", "window_ms", "trials"}), f"exp_a[{idx}]")
        require_ok(e["arm"] == exp_arm, "EXP_A_ARM_NAME", f"exp_a[{idx}] arm mismatch")
        require_ok(e["slices"] == exp_slices, "EXP_A_SLICES", f"exp_a[{idx}] slices mismatch")
        require_ok(e["window_ms"] == exp_win, "EXP_A_WIN", f"exp_a[{idx}] window_ms mismatch")
        tr = e["trials"]
        require_ok(type(tr) is list and len(tr) == 2, "EXP_A_TRIALS_LEN", f"exp_a[{idx}] must have 2 trials")
        t0 = _validate_measurement(tr[0], f"exp_a[{idx}].trials[0]")
        t1 = _validate_measurement(tr[1], f"exp_a[{idx}].trials[1]")
        a_checksums.add(t0["checksum_hex"])
        a_checksums.add(t1["checksum_hex"])
        tot = _sum_trials((t0, t1))
        # Exact mean per-job energy in mJ = (sum_uj / 2) / 1000 = sum_uj / 2000
        pkg_mj = Fraction(tot["pkg_uj"], 2000)
        psys_mj = Fraction(tot["psys_uj"], 2000)
        in_pkg_res_uj = tot["pkg_uj"] - tot["core_uj"] - tot["uncore_uj"]
        mean_wall_ms = Fraction(tot["wall_us"], 2000)
        mean_pkg_w = Fraction(tot["pkg_uj"], tot["wall_us"])
        # Incremental dynamic energy above measured idle baseline over the arm's wall window:
        pkg_net_mj = (Fraction(tot["pkg_uj"], 1) - idle_pkg_w_q * tot["wall_us"]) / 2000
        a_pkg_mj_map[exp_arm] = pkg_mj
        a_psys_mj_map[exp_arm] = psys_mj
        a_rows.append(
            {
                "arm": exp_arm,
                "slices": exp_slices,
                "window_ms": exp_win,
                "sum_wall_us": tot["wall_us"],
                "sum_pkg_uj": tot["pkg_uj"],
                "sum_core_uj": tot["core_uj"],
                "sum_uncore_uj": tot["uncore_uj"],
                "sum_in_package_residual_uj": in_pkg_res_uj,
                "sum_psys_uj": tot["psys_uj"],
                "mean_wall_ms_q": format_exact_rational(mean_wall_ms),
                "mean_pkg_w_q": format_exact_rational(mean_pkg_w),
                "pkg_mj_per_job_q": format_exact_rational(pkg_mj),
                "psys_mj_per_job_q": format_exact_rational(psys_mj),
                "pkg_net_above_idle_mj_q": format_exact_rational(pkg_net_mj),
                "checksum_hex": t0["checksum_hex"],
            }
        )
    require_ok(len(a_checksums) == 1, "EXP_A_CHECKSUM_DRIFT", "Exp A checksums must be identical across all 10 trials")

    # Best fixed-deadline arm & free-deadline vs fixed-deadline regime classification
    fixed_arms = [name for name, _, win in _EXP_A_EXPECTED_ARMS if win > 0]
    best_fixed_pkg_arm = min(fixed_arms, key=lambda k: a_pkg_mj_map[k])
    best_all_a_pkg_arm = min(a_pkg_mj_map.keys(), key=lambda k: a_pkg_mj_map[k])
    burst1_pkg = a_pkg_mj_map["bursty_1_pulse_1500ms"]
    paced100_pkg = a_pkg_mj_map["paced_100_slices_1500ms"]
    race_pkg = a_pkg_mj_map["race_to_sleep_free"]

    raw_b = d["exp_b_concurrency_impedance"]
    require_ok(
        type(raw_b) is list and len(raw_b) == len(_EXP_B_EXPECTED_THREADS),
        "EXP_B_LEN_MISMATCH",
        "exp_b_concurrency_impedance must have 7 thread counts",
    )
    b_rows: list[dict[str, Any]] = []
    b_checksums: set[str] = set()
    b_pkg_mj_map: dict[int, Fraction] = {}
    b_psys_mj_map: dict[int, Fraction] = {}
    b_wall_us_map: dict[int, int] = {}
    for idx, (entry, exp_p) in enumerate(zip(raw_b, _EXP_B_EXPECTED_THREADS)):
        e = require_exact_keys(
            entry,
            frozenset({"threads", "physical_cores_used", "smt_siblings_used", "trials"}),
            f"exp_b[{idx}]",
        )
        require_ok(e["threads"] == exp_p, "EXP_B_THREADS", f"exp_b[{idx}] threads mismatch")
        exp_phys = exp_p if exp_p <= 8 else 8
        exp_smt = exp_p - 8 if exp_p > 8 else 0
        require_ok(e["physical_cores_used"] == exp_phys, "EXP_B_PHYS", f"exp_b[{idx}] physical_cores_used mismatch")
        require_ok(e["smt_siblings_used"] == exp_smt, "EXP_B_SMT", f"exp_b[{idx}] smt_siblings_used mismatch")
        tr = e["trials"]
        require_ok(type(tr) is list and len(tr) == 2, "EXP_B_TRIALS_LEN", f"exp_b[{idx}] must have 2 trials")
        t0 = _validate_measurement(tr[0], f"exp_b[{idx}].trials[0]")
        t1 = _validate_measurement(tr[1], f"exp_b[{idx}].trials[1]")
        b_checksums.add(t0["checksum_hex"])
        b_checksums.add(t1["checksum_hex"])
        tot = _sum_trials((t0, t1))
        pkg_mj = Fraction(tot["pkg_uj"], 2000)
        psys_mj = Fraction(tot["psys_uj"], 2000)
        mean_wall_ms = Fraction(tot["wall_us"], 2000)
        # Throughput in Gop/s = (2 * wb_ops) / (sum_wall_us * 1000)
        gops_q = Fraction(2 * wb_ops, tot["wall_us"] * 1000)
        b_pkg_mj_map[exp_p] = pkg_mj
        b_psys_mj_map[exp_p] = psys_mj
        b_wall_us_map[exp_p] = tot["wall_us"]
        b_rows.append(
            {
                "threads": exp_p,
                "physical_cores_used": exp_phys,
                "smt_siblings_used": exp_smt,
                "sum_wall_us": tot["wall_us"],
                "sum_pkg_uj": tot["pkg_uj"],
                "sum_core_uj": tot["core_uj"],
                "sum_uncore_uj": tot["uncore_uj"],
                "sum_psys_uj": tot["psys_uj"],
                "mean_wall_ms_q": format_exact_rational(mean_wall_ms),
                "throughput_gops_q": format_exact_rational(gops_q),
                "pkg_mj_per_job_q": format_exact_rational(pkg_mj),
                "psys_mj_per_job_q": format_exact_rational(psys_mj),
                "checksum_hex": t0["checksum_hex"],
            }
        )
    require_ok(len(b_checksums) == 1, "EXP_B_CHECKSUM_DRIFT", "Exp B checksums must be identical across all 14 trials")

    # Add exact speedup vs 1T
    wall_1t = b_wall_us_map[1]
    for row in b_rows:
        row["speedup_vs_1t_q"] = format_exact_rational(Fraction(wall_1t, row["sum_wall_us"]))

    opt_pkg_p = min(_EXP_B_EXPECTED_THREADS, key=lambda p: b_pkg_mj_map[p])
    opt_psys_p = min(_EXP_B_EXPECTED_THREADS, key=lambda p: b_psys_mj_map[p])
    best_phys_pkg_p = min((1, 2, 4, 6, 8), key=lambda p: b_pkg_mj_map[p])
    best_phys_psys_p = min((1, 2, 4, 6, 8), key=lambda p: b_psys_mj_map[p])

    return {
        "host_cpu_model": host_cpu,
        "rapl_max_energy_range_uj": rapl_max,
        "exp_a_total_blocks": wa_blocks,
        "exp_a_total_ops": wa_ops,
        "exp_a_window_ms": win_a_ms,
        "exp_a_threads": a_threads,
        "exp_b_total_blocks": wb_blocks,
        "exp_b_total_ops": wb_ops,
        "idle_baseline": {
            "sum_wall_us": idle_sum["wall_us"],
            "sum_pkg_uj": idle_sum["pkg_uj"],
            "sum_core_uj": idle_sum["core_uj"],
            "sum_uncore_uj": idle_sum["uncore_uj"],
            "sum_in_package_residual_uj": idle_sum["pkg_uj"] - idle_sum["core_uj"] - idle_sum["uncore_uj"],
            "sum_psys_uj": idle_sum["psys_uj"],
            "pkg_idle_w_q": format_exact_rational(idle_pkg_w_q),
            "psys_idle_w_q": format_exact_rational(idle_psys_w_q),
            "psys_vendor_scale_obstruction_detected": idle_psys_w_q < idle_pkg_w_q,
        },
        "exp_a_checksum_conserved": True,
        "exp_a_checksum_hex": next(iter(a_checksums)),
        "exp_a_arms": a_rows,
        "exp_a_summary": {
            "best_overall_pkg_arm": best_all_a_pkg_arm,
            "best_fixed_window_pkg_arm": best_fixed_pkg_arm,
            "race_to_sleep_beats_fixed_burst_pkg": race_pkg < burst1_pkg,
            "paced100_beats_burst1_fixed_window_pkg": paced100_pkg < burst1_pkg,
            "paced100_over_burst1_pkg_ratio_q": format_exact_rational(paced100_pkg / burst1_pkg),
            "race_over_burst1_pkg_ratio_q": format_exact_rational(race_pkg / burst1_pkg),
        },
        "exp_b_checksum_conserved": True,
        "exp_b_checksum_hex": next(iter(b_checksums)),
        "exp_b_threads": b_rows,
        "exp_b_summary": {
            "optimal_pkg_threads": opt_pkg_p,
            "optimal_psys_threads": opt_psys_p,
            "best_physical_pkg_threads": best_phys_pkg_p,
            "best_physical_psys_threads": best_phys_psys_p,
            "best_phys_beats_1t_pkg": b_pkg_mj_map[best_phys_pkg_p] < b_pkg_mj_map[1],
            "best_phys_beats_16t_pkg": b_pkg_mj_map[best_phys_pkg_p] < b_pkg_mj_map[16],
            "best_phys_beats_1t_psys": b_psys_mj_map[best_phys_psys_p] < b_psys_mj_map[1],
            "best_phys_beats_16t_psys": b_psys_mj_map[best_phys_psys_p] < b_psys_mj_map[16],
            "pkg_1t_over_best_phys_ratio_q": format_exact_rational(
                b_pkg_mj_map[1] / b_pkg_mj_map[best_phys_pkg_p]
            ),
            "pkg_16t_over_best_phys_ratio_q": format_exact_rational(
                b_pkg_mj_map[16] / b_pkg_mj_map[best_phys_pkg_p]
            ),
            "psys_1t_over_best_phys_ratio_q": format_exact_rational(
                b_psys_mj_map[1] / b_psys_mj_map[best_phys_psys_p]
            ),
            "psys_16t_over_best_phys_ratio_q": format_exact_rational(
                b_psys_mj_map[16] / b_psys_mj_map[best_phys_psys_p]
            ),
        },
    }
