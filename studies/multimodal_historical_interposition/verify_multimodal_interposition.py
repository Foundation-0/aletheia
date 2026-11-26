#!/usr/bin/env python3
"""Pure-Stdlib Fail-Closed Verifier for Passive 5-Modality Open-Room Interposition.

Independently verifies the anonymized open-room multi-modal sensor x historical
exact-operator interposition study bundle with zero external dependencies
(runs identically under `python3 -I -B`, `-I -O -B`, and `-I -B -W error`):
  1. Cryptographic SHA-256 self-binding of BOTH committed `ANALYSIS_PLAN.md`
     (raw bytes) AND committed `open_room_interposition_results.json` (BOTH
     raw file bytes AND canonical `payload_sha256` / `results_sha256`), using
     `is_hex64` before `hmac.compare_digest` plus strict duplicate-key and
     non-finite JSON parse rejection.
  2. Privacy, zero-raw-media, hard-stop trigger (`<= 1795693500` / `05:45:00 CST`),
     teardown ceiling (`<= 1795693620` / `05:47:00 CST`, transparently checking
     `stopped_before_hard_stop == (stop_epoch_s <= hard_stop_epoch_s)` for the
     realized `+5.1 s` shutdown drain tail), zero-SSID/MAC/email/host-path, and
     strict uncontrolled-laptop energy-claim rejection (NFKC/NFKD/casefold
     normalization + non-ASCII homoglyph rejection + unit/metric value guard).
  3. Exact pure-Z/Q recomputation of embedded historical operators + in-module
     AST self-audit (`audit_exact_operators_ast`, banning float/complex literals,
     `ast.Div`, `ast.Pow`, unsafe `Fraction(...)`, `from_float`, and transcendentals):
     - Zero-log `cmp_power` 53-TET & 12-TET peak-ratio steps (`H20-B2`),
     - Exact Haynsworth Sylvester inertia additivity (`H20-A2`) & Hermitian PSD (`H20-B3`),
     - Exact rational tachometer shaft frequencies & CRT phase-sync exemplar witnesses
       with `unique_rpm_pairs_count >= len(witnesses)` and distinct pairs (`H20-B1`),
     - Exact Panini C1P bitset compression ratio & Khipu summary-attestation checks
       (tamper arithmetic, non-zero 64-hex `root_merkle_sha256`, positive `root_value`) (`H20-C2`).
  4. Exact Holm-Bonferroni step-down p-value recomputation & honest Law-4
     verdict re-derivation across all 7 hypotheses (`H20-A1..C2`), including:
     - Full `H20-B1` four-null-test binding (`p_raw_* < 0.01`),
     - Full `H20-C1` live recomputation of all `C(k,2)` pair Holm p-values,
       survivor flags/counts, `p_raw`, and all `C(k,3)` Cech H^1 lag holonomies
       directly from `pair_couplings` (plus sample-triple cross-checks),
     - Deterministic replay `H20-C2` graded strictly on exact rational default
       `70/78/85 C` ladder switch counts (`bangbang / hysteresis >= 5/1`) and
       exact rational Panini compression (`compression_ratio_q > 1/1`).
"""

from __future__ import annotations

import argparse
import ast
import errno
from fractions import Fraction
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unicodedata

SCHEMA_RESULTS = "aletheia.multimodal_historical_interposition.v1"
PINNED_ANALYSIS_PLAN_SHA256 = "b42768b8ddb0fdb3835e35c7eb739e2474a7e3b7d715fabda23b7140b8bd6f81"
PINNED_RESULTS_SHA256 = "2e56087c3fdf061ea05b61bdacd9cd242aebdddf28e20f616f07b79b0360fdf3"
PINNED_RESULTS_FILE_SHA256 = "d6da84ff911d063c4559b449dea31c58fd75a6c5cd30fd7032124de88de0b4f0"

ABSOLUTE_HARD_STOP_EPOCH = 1795693500
SHUTOFF_CEILING_EPOCH = 1795693620
MAX_JSON_DEPTH = 24
MAX_POWER_EXP = 1024
MAX_TET_DIVISIONS = 512
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_ENERGY_TEXT_LEN = 16384
MAX_JSON_INT_DIGITS = 1024
HOLM_TOL = 1e-6

STOCHASTIC_KEYS = ("H20-A1", "H20-A2", "H20-B1", "H20-B2", "H20-B3", "H20-C1")
ALL_HYP_KEYS = ("H20-A1", "H20-A2", "H20-B1", "H20-B2", "H20-B3", "H20-C1", "H20-C2")
B1_SUB_PVAL_KEYS = (
    "p_raw_dynamic_circular_null",
    "p_raw_peak_freq_tracking_null",
    "p_raw_4pole_lock_null",
    "p_raw_harmonic_lock_null",
)
REQUIRED_TOP_KEYS = (
    "schema",
    "analysis_plan_sha256",
    "dataset_prefix",
    "seed",
    "n_nulls",
    "energy_power_status",
    "privacy_and_shutoff_receipt",
    "summary",
    "hypotheses",
    "payload_sha256",
    "results_sha256",
)
EXACT_OPERATOR_FUNCS = (
    "_int_gcd",
    "_int_pow",
    "_parse_frac_str",
    "cmp_power",
    "exact_nearest_tet_step_z",
    "verify_exact_operators",
)

_HEX_LOWER = frozenset("0123456789abcdef")
_CAMEL_BOUNDARY_RE = re.compile(r"([a-z0-9])([A-Z])")
_KEY_TOKEN_RE = re.compile(r"[a-z0-9]+")

_FORBIDDEN_EXACT_CALLS = frozenset((
    "float",
    "complex",
    "round",
    "eval",
    "exec",
    "pow",
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
    "vars",
    "__import__",
    "__builtins__",
    "__loader__",
    "__spec__",
    "__annotations__",
    "from_float",
    "from_decimal",
    "truediv",
    "itruediv",
    "divmod",
    "format",
    "format_map",
    "memoryview",
    "literal_eval",
    "compile",
    "open",
    "log",
    "log2",
    "log10",
    "exp",
    "sqrt",
    "sin",
    "cos",
))

# Reference Energy-Claim Value Guard (NFKC -> NFKD -> strip Cf/Mn -> casefold)
# Strictly linear-time O(N) bounded quantifiers; covers hex magnitudes, hp, V*A, per-token, spelled words, & telemetry.
_PFX = r"(?:p|n|u|\u03bc|m|k|g|t|pico|nano|micro|milli|kilo|mega|giga|tera)"
_UNIT = r"(?:watt[^a-z0-9.,/]{0,2}hours?|watthours?|watts?|wattage|joules?|whrs?|wh|w|j|tdp|hp)"
_COLON_UNIT = r"(?:watt[^a-z0-9.,/]{0,2}hours?|watthours?|watts?|wattage|joules?|whrs?|wh|w|tdp|hp|energy|power)"
_SEP = r"[^a-z0-9.,/]{0,4}"
_NUM = r"(?:0x[0-9a-f]+|\d+(?:[.,]\d+){0,4}(?:e[+-]?\d+)?)"
_WORD_NUM = (
    r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
    r"fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|"
    r"sixty|seventy|eighty|ninety|hundred|thousand)"
)
_VOLT = rf"{_NUM}{_SEP}(?:m|k)?(?:volts?|v)(?![a-z0-9])"
_AMP = rf"{_NUM}{_SEP}(?:m|u|\u03bc)?(?:amps?|amperes?|a)(?![a-z0-9])"
ENERGY_VALUE_RE = re.compile(
    "(?:"
    rf"(?<![a-z0-9]){_NUM}{_SEP}(?:{_PFX}{_SEP})?{_UNIT}(?![a-z0-9])(?!/[a-z0-9\s])"
    rf"|(?<![a-z0-9])(?:{_PFX}{_SEP})?{_COLON_UNIT}\s*[:=]\s*{_NUM}"
    rf"|(?<![a-z0-9]){_PFX}{_SEP}j\s*[:=]\s*{_NUM}"
    rf"|(?<![a-z0-9])j\s*:\s*{_NUM}"
    rf"|(?<![a-z0-9])(?:tdp|energy|power|wattage)[^a-z0-9]{{0,4}}{_NUM}"
    rf"|^[^a-z0-9]{{0,4}}(?:{_PFX}{_SEP})?{_UNIT}[^a-z0-9]{{0,4}}$"
    r"|(?<![a-z0-9])(?:joules?|watts?|(?:p|n|u|\u03bc|m|k|g|t)(?:wh|w|j)|wh|j)\s*(?:per|/)\s*tok(?:en)?s?(?![a-z0-9])"
    r"|(?<![a-z0-9])w(?:\s+per\s+|/)tok(?:en)?s?(?![a-z0-9])"
    rf"|(?<![a-z0-9]){_WORD_NUM}(?:[\s-]{{0,2}}{_WORD_NUM}){{0,3}}\s+(?:(?:pico|nano|micro|milli|kilo|mega|giga|tera)[\s-]*)?(?:watts?|watt[\s-]*hours?|joules?|horsepower)(?![a-z0-9])"
    rf"|(?<![a-z0-9])(?:{_AMP}(?:[\s,@x*\u00d7/-]{{1,6}}(?:at\s+)?)?{_VOLT}|{_VOLT}(?:[\s,@x*\u00d7/-]{{1,6}}(?:at\s+)?)?{_AMP})"
    r"|(?<![a-z0-9])(?:less|lower|reduced|fewer)\s+(?:in\s+)?(?:energy|power)(?![a-z0-9])"
    r"|(?<![a-z0-9])(?:energy|power)[\s_-]+(?:use|usage|reduction|savings?|dropped|consumption|draw|limit|cap)(?![a-z0-9])"
    r"|(?<![a-z0-9])(?:nvml|rapl)[\s_-]*(?:power|energy|watt|joule|uj|mw|limit|cap)(?![a-z0-9])"
    ")"
)

LEAK_VALUE_RE = re.compile(
    r"(?:"
    r"/" + r"home/"
    r"|/" + r"users/"
    r"|/" + r"root/"
    r"|c:[/\\]users[/\\]"
    r"|(?:bssid|mac_addr|ssid|rapl|nvml)"
    r"|(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}"
    r"|[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}"
    r")"
)

ALLOWED_POLICY_KEYS = frozenset((
    "energy_power_status",
    "zero_power_energy_reads",
    "zero_ssid_mac_reads",
))
FORBIDDEN_KEY_TOKENS = frozenset((
    "bssid",
    "ssid",
    "rapl",
    "nvml",
    "watt",
    "watts",
    "wattage",
    "joule",
    "joules",
    "tdp",
    "kwh",
    "whr",
    "mw",
    "kw",
    "hp",
))


class StudyVerifyError(ValueError):
    """Fail-closed verification error for the multimodal interposition study."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"[{code}] {detail}")


def require_ok(cond: bool, code: str, detail: str) -> None:
    if not cond:
        raise StudyVerifyError(code, detail)


def is_hex64(val: Any) -> bool:
    """Return True iff val is a lowercase 64-char ASCII hex SHA-256 digest."""
    return (
        type(val) is str
        and len(val) == 64
        and all(ch in _HEX_LOWER for ch in val)
    )


def _int_gcd(a: int, b: int) -> int:
    """Pure-integer binary GCD (zero ast.Div / ast.FloorDiv / ast.Mod)."""
    x = abs(a)
    y = abs(b)
    if x == 0:
        return y
    if y == 0:
        return x
    shift = 0
    while ((x | y) & 1) == 0:
        x >>= 1
        y >>= 1
        shift += 1
    while (x & 1) == 0:
        x >>= 1
    while y != 0:
        while (y & 1) == 0:
            y >>= 1
        if x > y:
            x, y = y, x
        y -= x
    return x << shift


def _int_pow(base: int, power: int) -> int:
    """Pure-integer binary exponentiation (zero ast.Pow / ast.FloorDiv / floats)."""
    acc = 1
    b = base
    e = power
    while e > 0:
        if e & 1:
            acc *= b
        b *= b
        e >>= 1
    return acc


def _is_real_num(val: Any) -> bool:
    """Return True iff val is an exact int or finite float (never bool)."""
    t = type(val)
    return t is int or (t is float and math.isfinite(val))


def _require_dict(val: Any, code: str, detail: str) -> Dict[str, Any]:
    require_ok(type(val) is dict, code, detail)
    return val


def _require_real(val: Any, code: str, detail: str) -> float:
    require_ok(_is_real_num(val), code, detail)
    try:
        return float(val)
    except OverflowError as exc:
        raise StudyVerifyError(code, detail) from exc


def _require_int(val: Any, code: str, detail: str) -> int:
    require_ok(type(val) is int, code, detail)
    return val


def _require_bool(val: Any, code: str, detail: str) -> bool:
    require_ok(type(val) is bool, code, detail)
    return val


def normalize_text(text: str) -> str:
    """Normalize text via NFKC -> NFKD -> strip Cf/Mn -> casefold."""
    require_ok(type(text) is str, "BAD_TEXT", "Expected str for normalization")
    s = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", text))
    return "".join(
        ch for ch in s if unicodedata.category(ch) not in ("Cf", "Mn")
    ).casefold()


def has_non_ascii_letter(text: str) -> bool:
    """Reject non-ASCII alphabetic characters (homoglyph risk) except micro sign."""
    require_ok(type(text) is str, "BAD_TEXT", "Expected str for non-ASCII scan")
    return any(
        not ch.isascii() and ch.isalpha() and ch not in ("\u03bc", "\u00b5")
        for ch in text
    )


def is_forbidden_energy_value(text: str) -> bool:
    """Return True iff text contains a forbidden uncontrolled energy/power claim."""
    n = normalize_text(text)
    require_ok(len(n) <= MAX_ENERGY_TEXT_LEN, "STRING_TOO_LARGE", "Text length exceeds guard limit")
    return has_non_ascii_letter(text) or bool(ENERGY_VALUE_RE.search(n))


def is_forbidden_energy_key(key: str) -> bool:
    """Return True iff key encodes a forbidden energy/power or identifier token."""
    require_ok(type(key) is str, "BAD_KEY", "JSON key must be str")
    spaced = _CAMEL_BOUNDARY_RE.sub(r"\1 \2", key).replace("_", " ")
    if is_forbidden_energy_value(spaced):
        return True
    if key in ALLOWED_POLICY_KEYS:
        return False
    norm = normalize_text(spaced)
    if "mac addr" in norm:
        return True
    tokens = set(_KEY_TOKEN_RE.findall(norm))
    return bool(tokens & FORBIDDEN_KEY_TOKENS)


def _contains_fraction_name(expr: ast.AST) -> bool:
    for sub in ast.walk(expr):
        if isinstance(sub, ast.Name) and sub.id == "Fraction":
            return True
    return False


def audit_exact_operators_ast(
    source_text: str,
    func_names: Optional[Sequence[str]] = EXACT_OPERATOR_FUNCS,
) -> Dict[str, bool]:
    """Fail-closed allowlist AST purity check for exact pure-Z/Q operator functions."""
    require_ok(type(source_text) is str, "BAD_SOURCE", "source_text must be str")
    try:
        tree = ast.parse(source_text)
    except SyntaxError as exc:
        raise StudyVerifyError("AST_SYNTAX_ERR", str(exc)) from exc

    roots: List[ast.AST] = []
    if func_names is None:
        roots.append(tree)
    else:
        defs = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        for name in func_names:
            require_ok(name in defs, "MISSING_EXACT_FUNC", f"Required exact function missing: {name}")
            roots.append(defs[name])

    for root in roots:
        allowed_type_call_ids = set()
        for n in ast.walk(root):
            if isinstance(n, ast.Compare) and isinstance(n.ops[0], ast.Is):
                allowed_type_call_ids.add(id(n.left))
        for node in ast.walk(root):
            if isinstance(node, ast.Constant):
                require_ok(
                    type(node.value) not in (float, complex),
                    "AST_FLOAT_LITERAL",
                    "Float/complex literal forbidden in exact operators",
                )
            elif isinstance(node, ast.Div):
                raise StudyVerifyError("AST_DIV_FORBIDDEN", "True-division `/` forbidden in exact operators")
            elif isinstance(node, ast.FloorDiv):
                raise StudyVerifyError("AST_FLOORDIV_FORBIDDEN", "Floor-division `//` forbidden in exact operators")
            elif isinstance(node, ast.Mod):
                raise StudyVerifyError("AST_MOD_FORBIDDEN", "Modulo / %-formatting `%` forbidden in exact operators")
            elif isinstance(node, ast.Pow):
                raise StudyVerifyError("AST_POW_FORBIDDEN", "Operator `**` forbidden in exact operators")
            elif isinstance(node, ast.FormattedValue):
                require_ok(
                    node.format_spec is None,
                    "AST_FORMAT_SPEC_FORBIDDEN",
                    "Format specifiers forbidden in exact operators",
                )
            elif isinstance(node, ast.Import):
                raise StudyVerifyError("AST_FLOAT_IMPORT", "Bare `import` statements forbidden in exact operators")
            elif isinstance(node, ast.ImportFrom):
                require_ok(
                    node.level == 0 and node.module == "fractions",
                    "AST_FLOAT_IMPORT",
                    f"Only `from fractions import Fraction` is allowed (got {node.module})",
                )
                for alias in node.names:
                    require_ok(
                        alias.name == "Fraction" and alias.asname is None,
                        "AST_FRACTION_ALIAS",
                        "Only bare `from fractions import Fraction` is allowed",
                    )
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                val_expr = node.value
                if val_expr is not None:
                    if isinstance(val_expr, ast.Name) and val_expr.id in ("Fraction", "type"):
                        raise StudyVerifyError("AST_FRACTION_ALIAS", "Aliasing Fraction or type is forbidden")
                    if isinstance(val_expr, ast.Attribute) and val_expr.attr == "Fraction":
                        raise StudyVerifyError("AST_FRACTION_ALIAS", "Aliasing Fraction attribute is forbidden")
            elif isinstance(node, (ast.Subscript, ast.List, ast.Tuple, ast.Set, ast.Dict)):
                require_ok(
                    not _contains_fraction_name(node),
                    "AST_FRACTION_ALIAS",
                    "Wrapping or indexing Fraction is forbidden",
                )
            elif isinstance(node, ast.Name):
                require_ok(
                    node.id not in _FORBIDDEN_EXACT_CALLS,
                    "AST_FLOAT_CALL",
                    f"Forbidden name in exact operators: {node.id}",
                )
            elif isinstance(node, ast.Attribute):
                require_ok(
                    not node.attr.startswith("__") and node.attr not in _FORBIDDEN_EXACT_CALLS and node.attr != "modules",
                    "AST_FLOAT_CALL",
                    f"Forbidden attribute in exact operators: .{node.attr}",
                )
            elif isinstance(node, ast.Call):
                fn = node.func
                require_ok(
                    isinstance(fn, (ast.Name, ast.Attribute)),
                    "AST_INDIRECT_CALL",
                    "Indirect call expression forbidden in exact operators",
                )
                call_name = fn.id if isinstance(fn, ast.Name) else fn.attr
                if call_name == "type":
                    require_ok(
                        isinstance(fn, ast.Name)
                        and id(node) in allowed_type_call_ids
                        and len(node.args) == 1
                        and len(node.keywords) == 0,
                        "AST_UNSAFE_TYPE",
                        "type() only allowed as 1-arg identity check `type(x) is T`",
                    )
                if call_name == "Fraction":
                    require_ok(
                        isinstance(fn, ast.Name) and len(node.args) == 2 and len(node.keywords) == 0,
                        "AST_UNSAFE_FRACTION",
                        "Fraction() must use strict bare 2-arg form Fraction(num, den)",
                    )
                    for arg in node.args:
                        if isinstance(arg, ast.Constant):
                            require_ok(
                                type(arg.value) is int,
                                "AST_UNSAFE_FRACTION",
                                "Fraction() constant args must be exact int",
                            )

    return {
        "zero_float_literals": True,
        "zero_ast_div": True,
        "zero_ast_pow": True,
        "zero_unsafe_fraction_calls": True,
        "zero_transcendental_calls": True,
    }


def _canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _no_duplicate_keys(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in pairs:
        require_ok(k not in out, "JSON_DUP_KEY", f"Duplicate JSON key: {k}")
        out[k] = v
    return out


def _reject_nonfinite_constant(tok: str) -> Any:
    raise StudyVerifyError("NONFINITE_FLOAT", f"Non-finite JSON constant forbidden: {tok}")


def _parse_bounded_int(tok: str) -> int:
    require_ok(
        len(tok.lstrip("+-")) <= MAX_JSON_INT_DIGITS,
        "JSON_INT_TOO_LARGE",
        "JSON integer literal exceeds digit cap",
    )
    return int(tok)


def _parse_frac_str(text: Any, name: str) -> Fraction:
    require_ok(type(text) is str and "/" in text, "BAD_FRAC_STR", f"{name} must be 'p/q'")
    parts = text.split("/")
    require_ok(len(parts) == 2, "BAD_FRAC_STR", f"{name} must have single '/'")
    try:
        num = int(parts[0])
        den = int(parts[1])
    except ValueError as exc:
        raise StudyVerifyError("BAD_FRAC_STR", f"{name} non-int parts") from exc
    require_ok(den > 0, "BAD_FRAC_DEN", f"{name} denominator must be > 0")
    return Fraction(num, den)


def validate_json_tree_clean(root: Any, max_depth: int = MAX_JSON_DEPTH) -> None:
    """Reject NaN/Inf floats, excessive nesting, non-str keys, leaks, and energy claims."""
    require_ok(
        type(max_depth) is int and 0 <= max_depth <= MAX_JSON_DEPTH,
        "BAD_MAX_DEPTH",
        "max_depth must be int in [0, MAX_JSON_DEPTH]",
    )
    stack: List[Tuple[Any, int]] = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        require_ok(depth <= max_depth, "JSON_DEPTH", "JSON nesting depth exceeded")
        t = type(node)
        if t is float:
            require_ok(math.isfinite(node), "NONFINITE_FLOAT", "NaN/Inf forbidden")
        elif t is str:
            require_ok(
                not is_forbidden_energy_value(node),
                "FORBIDDEN_ENERGY_VALUE",
                "Forbidden energy/power or homoglyph text in value",
            )
            norm = normalize_text(node)
            require_ok(
                not LEAK_VALUE_RE.search(norm),
                "FORBIDDEN_LEAK",
                "Forbidden path, MAC, email, or hardware identifier token in value",
            )
        elif t is dict:
            for k, v in node.items():
                require_ok(
                    not is_forbidden_energy_key(k),
                    "FORBIDDEN_ENERGY_KEY",
                    f"Forbidden key {k}",
                )
                k_norm = normalize_text(k)
                require_ok(
                    k in ALLOWED_POLICY_KEYS or not LEAK_VALUE_RE.search(k_norm),
                    "FORBIDDEN_LEAK",
                    "Forbidden host path or identifier in key",
                )
                stack.append((v, depth + 1))
        elif t is list:
            for item in node:
                stack.append((item, depth + 1))
        elif t in (int, bool) or node is None:
            continue
        else:
            raise StudyVerifyError("BAD_JSON_TYPE", f"Unsupported type {t.__name__}")


def cmp_power(y_num: int, y_den: int, x_num: int, x_den: int, p: int, q: int) -> int:
    """Zero-log exact BigInt sign of (y_num/y_den)^q - (x_num/x_den)^p."""
    require_ok(
        type(y_num) is int
        and type(y_den) is int
        and type(x_num) is int
        and type(x_den) is int
        and type(p) is int
        and type(q) is int,
        "BAD_CMP_POWER_TYPE",
        "cmp_power arguments must be exact int",
    )
    require_ok(
        y_num > 0 and y_den > 0 and x_num > 0 and x_den > 0 and q > 0,
        "BAD_CMP_POWER",
        "cmp_power requires positive rationals and q > 0",
    )
    require_ok(
        abs(p) <= MAX_POWER_EXP and q <= MAX_POWER_EXP,
        "CMP_POWER_EXP_BOUND",
        "cmp_power exponent exceeds bound",
    )
    if p >= 0:
        lhs = _int_pow(y_num, q) * _int_pow(x_den, p)
        rhs = _int_pow(x_num, p) * _int_pow(y_den, q)
    else:
        ap = -p
        lhs = _int_pow(y_num, q) * _int_pow(x_num, ap)
        rhs = _int_pow(x_den, ap) * _int_pow(y_den, q)
    if lhs > rhs:
        return 1
    if lhs < rhs:
        return -1
    return 0


def exact_nearest_tet_step_z(r: Fraction, n_tet: int) -> int:
    """Zero-log exact nearest N-TET step in 0..n_tet via pure-Z cmp_power."""
    require_ok(
        type(r) is Fraction and type(n_tet) is int and r > Fraction(0, 1) and 0 < n_tet <= MAX_TET_DIVISIONS,
        "BAD_TET_ARG",
        "r must be positive Fraction and n_tet int in [1, MAX_TET_DIVISIONS]",
    )
    rr = r
    while rr >= Fraction(2, 1):
        rr = rr * Fraction(1, 2)
    while rr < Fraction(1, 1):
        rr = rr * Fraction(2, 1)
    lo, hi = 0, n_tet
    while lo < hi:
        mid = (lo + hi + 1) >> 1
        if cmp_power(rr.numerator, rr.denominator, 2, 1, mid, n_tet) >= 0:
            lo = mid
        else:
            hi = mid - 1
    k_lo = lo
    k_hi = k_lo + 1
    r2 = rr * rr
    if cmp_power(r2.numerator, r2.denominator, 2, 1, k_lo + k_hi, n_tet) >= 0:
        return k_hi
    return k_lo


def holm_bonferroni(pvals: Dict[str, float]) -> Dict[str, float]:
    """Exact Holm-Bonferroni step-down adjusted p-values."""
    require_ok(type(pvals) is dict and len(pvals) > 0, "BAD_PVALS", "pvals must be non-empty dict")
    cleaned: List[Tuple[str, float]] = []
    for key, pv in pvals.items():
        require_ok(type(key) is str, "BAD_PVAL_KEY", "pvals keys must be str")
        f_pv = _require_real(pv, "BAD_PVAL_TYPE", f"p-value must be finite real for {key}")
        require_ok(0.0 <= f_pv <= 1.0, "BAD_PVAL", f"p-value out of [0,1] for {key}")
        cleaned.append((key, f_pv))
    cleaned.sort(key=lambda kv: (kv[1], kv[0]))
    m = len(cleaned)
    adj: Dict[str, float] = {}
    running_max = 0.0
    for rank, (key, pv) in enumerate(cleaned):
        val = min(1.0, pv * float(m - rank))
        if val < running_max:
            val = running_max
        running_max = val
        adj[key] = round(val, 8)
    return adj


def verify_privacy_and_shutoff(rec: Any) -> None:
    """Enforce hard-stop trigger, teardown ceiling, consistent stop flag, and zero leaks."""
    rec_d = _require_dict(rec, "BAD_RECEIPT", "privacy_and_shutoff_receipt must be dict")
    hard_stop = _require_int(rec_d.get("hard_stop_epoch_s"), "HARD_STOP_TYPE", "hard_stop_epoch_s must be int")
    require_ok(
        0 <= hard_stop <= ABSOLUTE_HARD_STOP_EPOCH,
        "HARD_STOP_EXCEEDED",
        "hard_stop_epoch_s must be in [0, 05:45:00 CST trigger ceiling]",
    )
    start_ep = _require_real(rec_d.get("start_epoch_s"), "BAD_EPOCHS", "start_epoch_s must be finite real")
    stop_ep = _require_real(rec_d.get("stop_epoch_s"), "BAD_EPOCHS", "stop_epoch_s must be finite real")
    require_ok(stop_ep >= start_ep, "BAD_EPOCHS", "stop_epoch_s must be >= start_epoch_s")
    require_ok(
        stop_ep <= float(SHUTOFF_CEILING_EPOCH),
        "PAST_HARD_STOP",
        "Collector teardown exceeded 05:47:00 CST shutoff ceiling",
    )
    stopped_before = _require_bool(
        rec_d.get("stopped_before_hard_stop"),
        "STOP_FLAG_TYPE",
        "stopped_before_hard_stop must be bool",
    )
    require_ok(
        stopped_before == (stop_ep <= float(hard_stop)),
        "STOP_FLAG_INCONSISTENT",
        "stopped_before_hard_stop contradicts stop_epoch_s vs hard_stop_epoch_s",
    )
    v_handles = _require_int(
        rec_d.get("video_handles_after_close"),
        "LEAKED_VIDEO_HANDLE",
        "video_handles_after_close must be int",
    )
    require_ok(v_handles == 0, "LEAKED_VIDEO_HANDLE", "video_handles_after_close != 0")
    raw_files = _require_int(
        rec_d.get("raw_media_files_count"),
        "RAW_MEDIA_LEAK",
        "raw_media_files_count must be int",
    )
    require_ok(raw_files == 0, "RAW_MEDIA_LEAK", "raw_media_files_count != 0")
    require_ok(rec_d.get("passive_zero_output_enforced") is True, "NOT_PASSIVE", "Must enforce passive capture")
    require_ok(rec_d.get("zero_power_energy_reads") is True, "POWER_READ_LEAK", "Must enforce zero power reads")
    require_ok(rec_d.get("zero_ssid_mac_reads") is True, "SSID_MAC_LEAK", "Must enforce zero SSID/MAC reads")


def _require_inertia_triple(val: Any, code: str, detail: str) -> List[int]:
    require_ok(
        type(val) is list and len(val) == 3 and all(type(x) is int and x >= 0 for x in val),
        code,
        detail,
    )
    return val


def verify_exact_operators(hyps: Dict[str, Any]) -> None:
    """Re-verify pure-Z/Q operator witnesses embedded across H20-A2, B1, B2, B3, C2."""
    # H20-A2: Haynsworth Sylvester inertia additivity + exact dimensions (12 = 4 + 8) + SPD
    a2 = hyps["H20-A2"]
    in_f = _require_inertia_triple(a2.get("inertia_full_12x12"), "BAD_INERTIA_FMT", "H20-A2 full inertia")
    in_i = _require_inertia_triple(a2.get("inertia_interior_4x4"), "BAD_INERTIA_FMT", "H20-A2 interior inertia")
    in_s = _require_inertia_triple(a2.get("inertia_schur_boundary_8x8"), "BAD_INERTIA_FMT", "H20-A2 schur inertia")
    require_ok(
        sum(in_f) == 12
        and sum(in_i) == 4
        and sum(in_s) == 8
        and all(in_f[k] == in_i[k] + in_s[k] for k in range(3))
        and in_f[2] == 0,
        "HAYNSWORTH_MISMATCH",
        "H20-A2 Haynsworth inertia dimension, additivity, or SPD failed",
    )
    require_ok(a2.get("exact_q_haynsworth_inertia_additivity") is True, "HAYNSWORTH_FLAG", "Haynsworth flag False")

    # H20-B1: Exact rational tachometer shaft & CRT phase-sync exemplar witnesses
    b1 = hyps["H20-B1"]
    witnesses = b1.get("qin_maya_crt_beat_witnesses")
    require_ok(type(witnesses) is list and len(witnesses) > 0, "BAD_CRT_LIST", "CRT witness list must be non-empty")
    unique_rpm_cnt = _require_int(b1.get("unique_rpm_pairs_count"), "BAD_CRT_COUNT", "unique_rpm_pairs_count must be int")
    require_ok(
        unique_rpm_cnt >= len(witnesses),
        "BAD_CRT_COUNT",
        "unique_rpm_pairs_count must be >= len(qin_maya_crt_beat_witnesses)",
    )
    seen_rpm_pairs = set()
    for w_raw in witnesses:
        w = _require_dict(w_raw, "BAD_CRT_ITEM", "CRT witness must be dict")
        r1 = _require_int(w.get("rpm1"), "BAD_RPM", "rpm1 must be int")
        r2 = _require_int(w.get("rpm2"), "BAD_RPM", "rpm2 must be int")
        require_ok(r1 > 0 and r2 > 0, "BAD_RPM", "RPM must be positive int")
        require_ok((r1, r2) not in seen_rpm_pairs, "BAD_CRT_DUP", "Duplicate CRT witness pair")
        seen_rpm_pairs.add((r1, r2))
        q1 = Fraction(r1, 60)
        q2 = Fraction(r2, 60)
        diff_q = abs(q1 - q2)
        g_num = _int_gcd(q1.numerator, q2.numerator)
        l_den = Fraction(q1.denominator * q2.denominator, _int_gcd(q1.denominator, q2.denominator)).numerator
        sync_q = Fraction(l_den, g_num)
        require_ok(_parse_frac_str(w.get("f1_hz_q"), "f1_hz_q") == q1, "CRT_F1_MISMATCH", "f1_hz_q mismatch")
        require_ok(_parse_frac_str(w.get("f2_hz_q"), "f2_hz_q") == q2, "CRT_F2_MISMATCH", "f2_hz_q mismatch")
        require_ok(_parse_frac_str(w.get("beat_hz_q"), "beat_hz_q") == diff_q, "CRT_BEAT_MISMATCH", "beat_hz_q mismatch")
        require_ok(_parse_frac_str(w.get("crt_phase_sync_s_q"), "crt_sync") == sync_q, "CRT_SYNC_MISMATCH", "CRT sync mismatch")

    # H20-B2: Zero-log cmpPower exact 53-TET & 12-TET step check on embedded peak pairs
    b2 = hyps["H20-B2"]
    for stratum_key in ("stratum_all_peaks", "stratum_mains_excluded"):
        st = _require_dict(b2.get(stratum_key), "BAD_STRATUM", f"Missing stratum {stratum_key}")
        pairs = st.get("sample_pairs_exact_cmpPower")
        require_ok(type(pairs) is list and len(pairs) > 0, "BAD_CMPPOWER_LIST", f"Empty pairs in {stratum_key}")
        for pr_raw in pairs:
            pr = _require_dict(pr_raw, "BAD_CMPPOWER_ITEM", "Pair witness must be dict")
            rq = _parse_frac_str(pr.get("ratio_q"), "ratio_q")
            exp_k53 = exact_nearest_tet_step_z(rq, 53)
            exp_k12 = exact_nearest_tet_step_z(rq, 12)
            k53 = _require_int(pr.get("k53"), "CMPPOWER_K53_MISMATCH", "k53 must be int")
            k12 = _require_int(pr.get("k12"), "CMPPOWER_K12_MISMATCH", "k12 must be int")
            require_ok(k53 == exp_k53, "CMPPOWER_K53_MISMATCH", "k53 mismatch vs pure-Z cmpPower")
            require_ok(k12 == exp_k12, "CMPPOWER_K12_MISMATCH", "k12 mismatch vs pure-Z cmpPower")

    # H20-B3: Hermitian PSD projected inertia check (active 3x3: sum == 3, n_pos > 0, n_neg == 0)
    b3 = hyps["H20-B3"]
    ih = _require_inertia_triple(
        b3.get("exact_q_session_mean_fan_hermitian_inertia"),
        "BAD_HERMITIAN_INERTIA",
        "Hermitian inertia must be length-3 non-negative int list",
    )
    require_ok(sum(ih) == 3 and ih[0] > 0 and ih[2] == 0, "HERMITIAN_NEG_EIG", "Active 3x3 Hermitian CSD must be non-trivial PSD")
    psd_v = _require_int(b3.get("psd_violations"), "PSD_VIOLATION", "psd_violations must be int")
    require_ok(psd_v == 0, "PSD_VIOLATION", "psd_violations must be 0")

    # H20-C2: Deterministic replay p-value check, Khipu attestation, & exact Panini C1P interval check
    c2 = hyps["H20-C2"]
    require_ok(
        c2.get("p_raw") is None and c2.get("p_holm") is None,
        "BAD_C2_PVAL",
        "Deterministic replay gate H20-C2 must set p_raw and p_holm to null",
    )
    kh = _require_dict(c2.get("khipu_tree_checksum"), "BAD_KHIPU", "khipu_tree_checksum must be dict")
    t_trials = _require_int(kh.get("tamper_trials"), "KHIPU_COUNT_MISMATCH", "tamper_trials must be int")
    t_det = _require_int(kh.get("tamper_detected"), "KHIPU_COUNT_MISMATCH", "tamper_detected must be int")
    t_esc = _require_int(kh.get("tamper_escapes"), "KHIPU_COUNT_MISMATCH", "tamper_escapes must be int")
    require_ok(
        t_trials > 0 and t_det >= 0 and t_esc >= 0 and t_trials - t_det == t_esc,
        "KHIPU_COUNT_MISMATCH",
        "Khipu tamper arithmetic mismatch",
    )
    kh_merkle = kh.get("root_merkle_sha256")
    require_ok(
        is_hex64(kh_merkle) and kh_merkle != "0" * 64,
        "BAD_KHIPU_ROOT",
        "khipu root_merkle_sha256 must be non-zero 64-hex",
    )
    kh_root_val = _require_int(kh.get("root_value"), "BAD_KHIPU_ROOT", "khipu root_value must be int")
    require_ok(kh_root_val > 0, "BAD_KHIPU_ROOT", "khipu root_value must be positive")
    pc = _require_dict(c2.get("panini_c1p_live_replay"), "BAD_PANINI", "panini_c1p_live_replay must be dict")
    pm = _require_dict(pc.get("monotone_thermal_regimes"), "BAD_PANINI", "monotone_thermal_regimes must be dict")
    n_sp = _require_int(pm.get("spine_len"), "BAD_PANINI", "spine_len must be int")
    n_tg = _require_int(pm.get("tag_count"), "BAD_PANINI", "tag_count must be int")
    require_ok(n_sp > 0 and n_tg > 0, "BAD_PANINI", "spine_len and tag_count must be positive")
    idx_bits = max(1, (n_sp - 1).bit_length())
    exp_naive = n_tg * n_sp
    exp_c1p = n_tg * 2 * idx_bits
    exp_ratio = Fraction(exp_naive, exp_c1p)
    got_naive = _require_int(pm.get("naive_bitset_bits"), "PANINI_NAIVE_MISMATCH", "naive_bitset_bits must be int")
    got_c1p = _require_int(pm.get("c1p_descriptor_bits"), "PANINI_C1P_MISMATCH", "c1p_descriptor_bits must be int")
    require_ok(got_naive == exp_naive, "PANINI_NAIVE_MISMATCH", "naive_bitset_bits mismatch")
    require_ok(got_c1p == exp_c1p, "PANINI_C1P_MISMATCH", "c1p_descriptor_bits mismatch")
    require_ok(
        _parse_frac_str(pm.get("compression_ratio_q"), "compression_ratio_q") == exp_ratio,
        "PANINI_RATIO_MISMATCH",
        "Panini compression_ratio_q mismatch",
    )
    pm_intervals = _require_dict(pm.get("intervals"), "BAD_PANINI_INTERVALS", "monotone intervals must be dict")
    require_ok(
        len(pm_intervals) == n_tg
        and pm.get("obstructed_count") == 0
        and pm.get("obstructed_tags") == {},
        "BAD_PANINI_INTERVALS",
        "monotone C1P intervals count or obstructed fields mismatch",
    )
    for iv in pm_intervals.values():
        require_ok(
            type(iv) is list
            and len(iv) == 2
            and type(iv[0]) is int
            and type(iv[1]) is int
            and 0 <= iv[0] <= iv[1] < n_sp,
            "BAD_PANINI_INTERVALS",
            "Panini interval must be [lo, hi] within [0, spine_len)",
        )
    cross_pm = _require_dict(
        pc.get("cross_modal_regimes_on_thermal_spine"),
        "BAD_PANINI_OBSTRUCTED",
        "cross_modal_regimes_on_thermal_spine must be dict",
    )
    obs_tags = cross_pm.get("obstructed_tags")
    require_ok(
        cross_pm.get("c1p_admissible") is False
        and cross_pm.get("compression_ratio_q") is None
        and cross_pm.get("compression_ratio_float") is None
        and cross_pm.get("intervals") == {}
        and type(obs_tags) is dict
        and len(obs_tags) > 0
        and all(type(v) is int and v > 0 for v in obs_tags.values())
        and cross_pm.get("obstructed_count") == len(obs_tags),
        "BAD_PANINI_OBSTRUCTED",
        "Non-admissible C1P cross-modal block must report empty intervals, positive obstructed_tags, and null ratios",
    )


def _verify_c1_evidence(c1: Dict[str, Any]) -> Tuple[int, int]:
    """Recompute H20-C1 pair Holm survivors and all C(k,3) Cech H^1 lag holonomies from pair_couplings."""
    active = c1.get("active_channels")
    require_ok(
        type(active) is list
        and len(active) >= 3
        and all(type(x) is str and len(x) > 0 for x in active)
        and len(set(active)) == len(active),
        "BAD_C1_CHANNELS",
        "active_channels must be >= 3 distinct non-empty strings",
    )
    n_ch = len(active)
    expected_pairs = {
        f"{active[i]}__x__{active[j]}": (active[i], active[j])
        for i in range(n_ch)
        for j in range(i + 1, n_ch)
    }
    n_expected_pairs = len(expected_pairs)
    n_tested = _require_int(c1.get("n_pairs_tested"), "BAD_C1_PAIRS", "n_pairs_tested must be int")
    pairs = c1.get("pair_couplings")
    require_ok(
        type(pairs) is list and len(pairs) == n_expected_pairs and n_tested == n_expected_pairs,
        "BAD_C1_PAIRS",
        "pair_couplings and n_pairs_tested must match C(len(active_channels), 2)",
    )

    circ_raws: Dict[str, float] = {}
    iaaft_raws: Dict[str, float] = {}
    stored_pair_rows: Dict[str, Tuple[float, float, bool]] = {}
    lag_map: Dict[Tuple[str, str], int] = {}

    for row_raw in pairs:
        row = _require_dict(row_raw, "BAD_C1_PAIR_ITEM", "pair_couplings item must be dict")
        pk = row.get("pair")
        require_ok(type(pk) is str and pk in expected_pairs and pk not in stored_pair_rows, "BAD_C1_PAIR_KEY", f"Invalid or duplicate pair key: {pk!r}")
        a_ch, b_ch = expected_pairs[pk]
        lag_val = _require_int(row.get("opt_lag_s"), "BAD_C1_LAG", f"opt_lag_s must be int for {pk}")
        lag_map[(a_ch, b_ch)] = lag_val
        lag_map[(b_ch, a_ch)] = -lag_val

        p_cr = _require_real(row.get("p_circ_raw"), "BAD_C1_PVAL", f"p_circ_raw invalid for {pk}")
        p_ir = _require_real(row.get("p_iaaft_raw"), "BAD_C1_PVAL", f"p_iaaft_raw invalid for {pk}")
        p_ch = _require_real(row.get("p_circ_holm"), "BAD_C1_PVAL", f"p_circ_holm invalid for {pk}")
        p_ih = _require_real(row.get("p_iaaft_holm"), "BAD_C1_PVAL", f"p_iaaft_holm invalid for {pk}")
        require_ok(
            all(0.0 <= v <= 1.0 for v in (p_cr, p_ir, p_ch, p_ih)),
            "BAD_C1_PVAL",
            f"pair p-values out of [0,1] for {pk}",
        )
        surv_flag = _require_bool(row.get("survives_both_nulls_001"), "BAD_C1_SURV_FLAG", f"survives_both_nulls_001 must be bool for {pk}")
        circ_raws[pk] = p_cr
        iaaft_raws[pk] = p_ir
        stored_pair_rows[pk] = (p_ch, p_ih, surv_flag)

    exp_circ_holm = holm_bonferroni(circ_raws)
    exp_iaaft_holm = holm_bonferroni(iaaft_raws)
    recomp_surv = 0
    for pk, (p_ch, p_ih, surv_flag) in stored_pair_rows.items():
        require_ok(
            abs(p_ch - exp_circ_holm[pk]) <= HOLM_TOL and abs(p_ih - exp_iaaft_holm[pk]) <= HOLM_TOL,
            "C1_PAIR_HOLM_MISMATCH",
            f"pair Holm p-value mismatch for {pk}",
        )
        exp_surv = exp_circ_holm[pk] < 0.01 and exp_iaaft_holm[pk] < 0.01
        require_ok(surv_flag == exp_surv, "C1_SURVIVOR_FLAG_MISMATCH", f"survives_both_nulls_001 mismatch for {pk}")
        if exp_surv:
            recomp_surv += 1

    stored_surv = _require_int(c1.get("n_pairs_surviving_both_nulls_holm_001"), "BAD_C1", "n_pairs_surviving must be int")
    require_ok(
        stored_surv == recomp_surv,
        "C1_SURVIVOR_COUNT_MISMATCH",
        f"n_pairs_surviving_both_nulls_holm_001 ({stored_surv}) != recomputed ({recomp_surv})",
    )
    c1_p_raw = _require_real(c1.get("p_raw"), "BAD_C1_PVAL", "H20-C1 p_raw must be finite real")
    exp_c1_p_raw = min(max(circ_raws[pk], iaaft_raws[pk]) for pk in expected_pairs)
    require_ok(
        abs(c1_p_raw - exp_c1_p_raw) <= HOLM_TOL,
        "C1_PRAW_MISMATCH",
        f"H20-C1 p_raw ({c1_p_raw}) != min_pair max(p_circ_raw, p_iaaft_raw) ({exp_c1_p_raw})",
    )

    triple_hol: Dict[Tuple[str, str, str], int] = {}
    for i in range(n_ch):
        for j in range(i + 1, n_ch):
            for k in range(j + 1, n_ch):
                a_ch, b_ch, c_ch = active[i], active[j], active[k]
                triple_hol[(a_ch, b_ch, c_ch)] = lag_map[(a_ch, b_ch)] + lag_map[(b_ch, c_ch)] + lag_map[(c_ch, a_ch)]

    n_triples_exp = len(triple_hol)
    recomp_nonzero = sum(1 for h_val in triple_hol.values() if h_val != 0)
    try:
        recomp_mean_abs = sum(abs(h_val) for h_val in triple_hol.values()) / float(n_triples_exp)
    except OverflowError as exc:
        raise StudyVerifyError("C1_HOLONOMY_MEAN_MISMATCH", "Recomputed lag holonomy overflows finite float") from exc

    stored_triples_cnt = _require_int(c1.get("cech_h1_triples_count"), "BAD_C1", "cech_h1_triples_count must be int")
    stored_nonzero = _require_int(c1.get("cech_h1_nonzero_holonomy_count"), "BAD_C1", "cech_h1_nonzero_holonomy_count must be int")
    stored_mean_abs = _require_real(c1.get("cech_h1_mean_abs_lag_holonomy_s"), "BAD_C1", "cech_h1_mean_abs_lag_holonomy_s must be real")
    require_ok(stored_triples_cnt == n_triples_exp, "C1_HOLONOMY_COUNT_MISMATCH", "cech_h1_triples_count mismatch")
    require_ok(stored_nonzero == recomp_nonzero, "C1_HOLONOMY_COUNT_MISMATCH", "cech_h1_nonzero_holonomy_count mismatch")
    require_ok(
        abs(stored_mean_abs - recomp_mean_abs) <= 1e-4,
        "C1_HOLONOMY_MEAN_MISMATCH",
        "cech_h1_mean_abs_lag_holonomy_s mismatch vs recomputed lag holonomies",
    )

    sample_triples = c1.get("cech_h1_sample_triples")
    require_ok(type(sample_triples) is list and len(sample_triples) <= n_triples_exp, "C1_SAMPLE_TRIPLE_MISMATCH", "cech_h1_sample_triples must be list")
    for st_raw in sample_triples:
        st = _require_dict(st_raw, "C1_SAMPLE_TRIPLE_MISMATCH", "sample triple must be dict")
        tr = st.get("triple")
        require_ok(
            type(tr) is list and all(type(x) is str for x in tr) and tuple(tr) in triple_hol,
            "C1_SAMPLE_TRIPLE_MISMATCH",
            "sample triple channels invalid",
        )
        h_got = _require_int(st.get("lag_holonomy_s"), "C1_SAMPLE_TRIPLE_MISMATCH", "sample lag_holonomy_s must be int")
        require_ok(h_got == triple_hol[tuple(tr)], "C1_SAMPLE_TRIPLE_MISMATCH", "sample lag_holonomy_s mismatch")

    return recomp_surv, recomp_nonzero


def _expected_verdicts(hyps: Dict[str, Any], p_holm: Dict[str, float]) -> Dict[str, str]:
    """Re-derive honest Law-4 verdicts strictly from ANALYSIS_PLAN.md kill gates."""
    out: Dict[str, str] = {}

    a1 = hyps["H20-A1"]
    a1_ratio = _require_real(a1.get("primary_stability_ratio"), "BAD_A1", "primary_stability_ratio")
    a1_auroc = _require_real(a1.get("auroc_ir_real_vs_noise"), "BAD_A1", "auroc_ir_real_vs_noise")
    if a1_ratio >= 2.0 and p_holm["H20-A1"] < 0.01 and a1_auroc >= 0.90:
        out["H20-A1"] = "CONFIRMED"
    elif p_holm["H20-A1"] < 0.01 and a1_auroc >= 0.90:
        out["H20-A1"] = "PARTIAL"
    else:
        out["H20-A1"] = "FALSIFIED"

    a2 = hyps["H20-A2"]
    a2_r2 = _require_real(a2.get("heldout_schur_r2"), "BAD_A2", "heldout_schur_r2")
    a2_ps = _require_real(a2.get("p_raw_spatial_null"), "BAD_A2", "p_raw_spatial_null")
    a2_snr = _require_real(a2.get("interior_temporal_snr_ratio"), "BAD_A2", "interior_temporal_snr_ratio")
    a2_ac = _require_real(a2.get("interior_mean_lag1_acorr"), "BAD_A2", "interior_mean_lag1_acorr")
    if a2_r2 > 0.05 and p_holm["H20-A2"] < 0.01 and a2_ps < 0.01:
        out["H20-A2"] = "CONFIRMED"
    elif a2_r2 > 0.05 and p_holm["H20-A2"] < 0.01:
        out["H20-A2"] = "PARTIAL"
    elif a2_snr < 1.25 and a2_ac < 0.25:
        out["H20-A2"] = "NULL_STATIC_ROOM"
    else:
        out["H20-A2"] = "FALSIFIED"

    b1 = hyps["H20-B1"]
    b1_sub_pvals: List[float] = []
    for k in B1_SUB_PVAL_KEYS:
        pv = _require_real(b1.get(k), "BAD_B1_PVAL", f"Missing/invalid {k}")
        require_ok(0.0 <= pv <= 1.0, "BAD_B1_PVAL", f"{k} out of [0,1]")
        b1_sub_pvals.append(pv)
    if p_holm["H20-B1"] < 0.01 and all(pv < 0.01 for pv in b1_sub_pvals):
        out["H20-B1"] = "CONFIRMED"
    else:
        out["H20-B1"] = "FALSIFIED"

    st2 = hyps["H20-B2"]["stratum_mains_excluded"]
    m53 = st2.get("mean_53tet_cents_cmpPower")
    m12 = st2.get("mean_12tet_cents_cmpPower")
    if m53 is not None:
        m53 = _require_real(m53, "BAD_B2", "mean_53tet_cents_cmpPower")
    if m12 is not None:
        m12 = _require_real(m12, "BAD_B2", "mean_12tet_cents_cmpPower")
    if p_holm["H20-B2"] < 0.01 and m53 is not None and m12 is not None and m53 < m12:
        out["H20-B2"] = "CONFIRMED"
    else:
        out["H20-B2"] = "FALSIFIED"

    b3 = hyps["H20-B3"]
    b3_gap = _require_real(b3.get("directional_vs_diffuse_reff_gap"), "BAD_B3", "directional_vs_diffuse_reff_gap")
    b3_nt = _require_int(b3.get("n_transients_fitted"), "BAD_B3", "n_transients_fitted")
    b3_pt = _require_real(b3.get("p_raw_transient_damping_diff"), "BAD_B3", "p_raw_transient_damping_diff")
    if p_holm["H20-B3"] < 0.01 and b3_gap > 0.2:
        if b3_nt >= 5 and b3_pt < 0.01:
            out["H20-B3"] = "CONFIRMED"
        else:
            out["H20-B3"] = "PARTIAL"
    else:
        out["H20-B3"] = "FALSIFIED"

    c1 = hyps["H20-C1"]
    c1_pairs, c1_hol = _verify_c1_evidence(c1)
    if c1_pairs >= 1 and c1_hol >= 1:
        out["H20-C1"] = "CONFIRMED"
    elif c1_pairs >= 1:
        out["H20-C1"] = "PARTIAL"
    else:
        out["H20-C1"] = "FALSIFIED"

    # H20-C2: Strictly graded on exact pure-Q Panini compression_ratio_q > 1/1 and
    # exact pure-Q default 70/78/85 C ladder switch counts (bangbang / hysteresis >= 5/1).
    c2 = hyps["H20-C2"]
    khipu_ok = c2["khipu_tree_checksum"]["tamper_escapes"] == 0
    pm = c2["panini_c1p_live_replay"]["monotone_thermal_regimes"]
    c1p_adm = _require_bool(pm.get("c1p_admissible"), "BAD_C2", "c1p_admissible")
    panini_ratio_q = _parse_frac_str(pm.get("compression_ratio_q"), "compression_ratio_q")
    panini_ok = c1p_adm and panini_ratio_q > Fraction(1, 1)

    tg = _require_dict(c2.get("thermal_governor_live_replay"), "BAD_C2", "thermal_governor_live_replay")
    default_prof = _require_dict(tg.get("default_70_78_85_ladder"), "BAD_C2", "Missing default_70_78_85_ladder")
    bb_sw = _require_int(default_prof.get("bangbang_switches"), "BAD_C2", "bangbang_switches must be int")
    hy_sw = _require_int(default_prof.get("hysteresis_switches"), "BAD_C2", "hysteresis_switches must be int")
    require_ok(bb_sw >= 0 and hy_sw > 0, "BAD_C2", "Switch counts require bangbang >= 0 and hysteresis > 0")
    default_red_q = Fraction(bb_sw, hy_sw)
    default_rr = _require_real(default_prof.get("reduction_ratio"), "BAD_C2", "default reduction_ratio must be finite real")
    try:
        default_red_f = float(default_red_q)
    except OverflowError as exc:
        raise StudyVerifyError("BAD_C2_RATIO", "default switch ratio overflows finite float") from exc
    require_ok(
        abs(default_rr - default_red_f) <= 1e-3,
        "BAD_C2_RATIO",
        "default reduction_ratio disagrees with bangbang_switches / hysteresis_switches",
    )
    if khipu_ok and panini_ok and default_red_q >= Fraction(5, 1):
        out["H20-C2"] = "CONFIRMED"
    elif khipu_ok and panini_ok:
        out["H20-C2"] = "PARTIAL"
    else:
        out["H20-C2"] = "FALSIFIED"

    return out


def validate_results_document(doc: Any) -> Dict[str, Any]:
    """Fail-closed semantic, statistical, exact-operator, and cryptographic verification."""
    validate_json_tree_clean(doc)
    doc_d = _require_dict(doc, "BAD_ROOT", "Document root must be dict")
    req_set = set(REQUIRED_TOP_KEYS)
    doc_set = set(doc_d.keys())
    for k in REQUIRED_TOP_KEYS:
        require_ok(k in doc_set, "MISSING_KEY", f"Missing required key {k}")
    require_ok(doc_set == req_set, "EXTRA_KEY", "Unexpected top-level keys present")

    require_ok(doc_d["schema"] == SCHEMA_RESULTS, "BAD_SCHEMA", "Schema mismatch")
    plan_sha = doc_d["analysis_plan_sha256"]
    require_ok(
        is_hex64(plan_sha) and hmac.compare_digest(plan_sha, PINNED_ANALYSIS_PLAN_SHA256),
        "BAD_ANALYSIS_PLAN",
        "Analysis plan SHA-256 mismatch",
    )
    require_ok(
        type(doc_d["dataset_prefix"]) is str and len(doc_d["dataset_prefix"]) > 0,
        "BAD_PREFIX",
        "dataset_prefix must be non-empty str",
    )
    _require_int(doc_d["seed"], "BAD_SEED", "seed must be int")
    n_nulls = _require_int(doc_d["n_nulls"], "TOO_FEW_NULLS", "n_nulls must be int")
    require_ok(n_nulls >= 100, "TOO_FEW_NULLS", "n_nulls must be >= 100")
    require_ok(
        doc_d["energy_power_status"] == "UNCONTROLLED_LAPTOP_NOT_CLAIMED",
        "BAD_ENERGY_STATUS",
        "Energy policy status mismatch",
    )

    verify_privacy_and_shutoff(doc_d["privacy_and_shutoff_receipt"])

    hyps = _require_dict(doc_d["hypotheses"], "BAD_HYPS", "hypotheses must be dict")
    require_ok(set(hyps.keys()) == set(ALL_HYP_KEYS), "BAD_HYP_KEYS", "Unexpected or missing hypothesis keys")
    for hk in ALL_HYP_KEYS:
        _require_dict(hyps[hk], "MISSING_HYP", f"Hypothesis {hk} must be dict")

    verify_exact_operators(hyps)

    p_raws = {
        hk: _require_real(hyps[hk].get("p_raw"), "BAD_PVAL_TYPE", f"Missing/invalid p_raw for {hk}")
        for hk in STOCHASTIC_KEYS
    }
    exp_holm = holm_bonferroni(p_raws)
    summary = _require_dict(doc_d["summary"], "BAD_SUMMARY", "summary must be dict")
    got_holm = _require_dict(summary.get("holm_bonferroni_pvals"), "BAD_HOLM", "holm_bonferroni_pvals must be dict")
    require_ok(set(got_holm.keys()) == set(STOCHASTIC_KEYS), "BAD_HOLM", "Unexpected holm_bonferroni_pvals keys")
    for hk in STOCHASTIC_KEYS:
        gh = _require_real(got_holm[hk], "HOLM_MISMATCH", f"Invalid summary Holm p-value for {hk}")
        hh = _require_real(hyps[hk].get("p_holm"), "HOLM_MISMATCH", f"Invalid hypothesis Holm p-value for {hk}")
        require_ok(
            abs(gh - exp_holm[hk]) <= HOLM_TOL and abs(hh - exp_holm[hk]) <= HOLM_TOL,
            "HOLM_MISMATCH",
            f"Holm p-value mismatch for {hk}",
        )

    exp_verdicts = _expected_verdicts(hyps, exp_holm)
    got_verdicts = _require_dict(summary.get("verdicts"), "BAD_VERDICTS", "verdicts must be dict")
    require_ok(set(got_verdicts.keys()) == set(ALL_HYP_KEYS), "BAD_VERDICTS", "Unexpected summary verdicts keys")
    for hk in ALL_HYP_KEYS:
        require_ok(
            got_verdicts[hk] == exp_verdicts[hk] and hyps[hk].get("verdict") == exp_verdicts[hk],
            "VERDICT_MISMATCH",
            f"Law-4 verdict mismatch for {hk}: got {got_verdicts[hk]}, expected {exp_verdicts[hk]}",
        )

    payload = {k: doc_d[k] for k in doc_d if k not in ("payload_sha256", "results_sha256")}
    exp_p_sha = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    got_p_sha = doc_d["payload_sha256"]
    require_ok(
        is_hex64(got_p_sha) and hmac.compare_digest(got_p_sha, exp_p_sha),
        "PAYLOAD_SHA_MISMATCH",
        "payload_sha256 mismatch",
    )
    body = dict(payload)
    body["payload_sha256"] = exp_p_sha
    exp_r_sha = hashlib.sha256(_canonical_json_bytes(body)).hexdigest()
    got_r_sha = doc_d["results_sha256"]
    require_ok(
        is_hex64(got_r_sha) and hmac.compare_digest(got_r_sha, exp_r_sha),
        "RESULTS_SHA_MISMATCH",
        "results_sha256 mismatch",
    )

    return {
        "status": "PASS",
        "analysis_plan_sha256": plan_sha,
        "verdicts": exp_verdicts,
        "results_sha256": exp_r_sha,
    }


def _read_regular_file_bytes(
    path: Path,
    err_code: str,
    max_bytes: int = MAX_FILE_BYTES,
) -> bytes:
    """Refuse symlinks along target and ancestors, open with O_NOFOLLOW|O_NONBLOCK, verify S_ISREG & cap."""
    abs_path = path if path.is_absolute() else Path.cwd().joinpath(path)
    cur = Path(abs_path.anchor)
    for idx, part in enumerate(abs_path.parts[1:]):
        cur = cur.joinpath(part)
        if idx >= 1 or idx == len(abs_path.parts) - 2:
            require_ok(
                not cur.is_symlink(),
                "SYMLINK_FORBIDDEN",
                f"Symlink path or ancestor directory forbidden: {path.name}",
            )
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise StudyVerifyError("SYMLINK_FORBIDDEN", f"Symlink forbidden: {path.name}") from exc
        raise StudyVerifyError(err_code, f"Failed to open file ({path.name}): {exc.strerror}") from exc
    try:
        try:
            st = os.fstat(fd)
            require_ok(stat.S_ISREG(st.st_mode), "NOT_REGULAR_FILE", f"Non-regular file forbidden: {path.name}")
            require_ok(st.st_size <= max_bytes, "FILE_TOO_LARGE", f"File exceeds {max_bytes} byte cap: {path.name}")
            chunks: List[bytes] = []
            total = 0
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                total += len(chunk)
                require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"Read exceeded {max_bytes} byte cap: {path.name}")
                chunks.append(chunk)
            return b"".join(chunks)
        except OSError as exc:
            raise StudyVerifyError(err_code, f"Failed to read file ({path.name}): {exc.strerror}") from exc
    finally:
        os.close(fd)


def check_results_file(
    path: Path,
    *,
    expected_results_sha256: Optional[str] = None,
    expected_file_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    """Load and fail-closed verify a results JSON file (no symlinks/FIFOs, dup-key & raw-bytes pin checks)."""
    require_ok(isinstance(path, Path), "BAD_PATH", "path must be pathlib.Path")
    raw_bytes = _read_regular_file_bytes(path, "READ_OR_JSON_ERR")
    raw_sha = hashlib.sha256(raw_bytes).hexdigest()
    if expected_file_sha256 is not None:
        require_ok(
            is_hex64(expected_file_sha256) and hmac.compare_digest(raw_sha, expected_file_sha256),
            "RESULTS_FILE_BYTES_MISMATCH",
            "On-disk results JSON raw-bytes SHA-256 mismatch",
        )
    try:
        data = json.loads(
            raw_bytes.decode("utf-8"),
            object_pairs_hook=_no_duplicate_keys,
            parse_constant=_reject_nonfinite_constant,
            parse_int=_parse_bounded_int,
        )
    except StudyVerifyError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise StudyVerifyError("READ_OR_JSON_ERR", f"Failed to parse JSON: {exc}") from exc
    res = validate_results_document(data)
    if expected_results_sha256 is not None:
        require_ok(
            is_hex64(expected_results_sha256)
            and hmac.compare_digest(res["results_sha256"], expected_results_sha256),
            "PINNED_RESULTS_MISMATCH",
            "results_sha256 does not match pinned study digest",
        )
    res["results_file_sha256"] = raw_sha
    return res


def check_study_bundle(study_dir: Path) -> Dict[str, Any]:
    """Fail-closed verify AST exact-operator purity, ANALYSIS_PLAN.md, and results JSON raw bytes."""
    require_ok(isinstance(study_dir, Path), "BAD_PATH", "study_dir must be pathlib.Path")
    self_bytes = _read_regular_file_bytes(Path(__file__), "READ_PLAN_ERR")
    try:
        self_text = self_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StudyVerifyError("READ_PLAN_ERR", f"Verifier source invalid UTF-8: {exc}") from exc
    audit_exact_operators_ast(self_text)
    plan_path = study_dir.joinpath("ANALYSIS_PLAN.md")
    plan_bytes = _read_regular_file_bytes(plan_path, "READ_PLAN_ERR")
    plan_sha = hashlib.sha256(plan_bytes).hexdigest()
    require_ok(
        hmac.compare_digest(plan_sha, PINNED_ANALYSIS_PLAN_SHA256),
        "ANALYSIS_PLAN_FILE_MISMATCH",
        "Committed ANALYSIS_PLAN.md SHA-256 mismatch",
    )
    results_path = study_dir.joinpath("open_room_interposition_results.json")
    return check_results_file(
        results_path,
        expected_results_sha256=PINNED_RESULTS_SHA256,
        expected_file_sha256=PINNED_RESULTS_FILE_SHA256,
    )


def build_selftest_fixture() -> Dict[str, Any]:
    """Deterministic pure-stdlib contract fixture verifying all verifier pathways."""
    p_raws = {
        "H20-A1": 0.000999,
        "H20-A2": 0.000999,
        "H20-B1": 0.000999,
        "H20-B2": 0.45,
        "H20-B3": 0.000999,
        "H20-C1": 0.000999,
    }
    p_h = holm_bonferroni(p_raws)
    hyps: Dict[str, Any] = {
        "H20-A1": {
            "primary_stability_ratio": 3.2,
            "auroc_ir_real_vs_noise": 0.99,
            "p_raw": p_raws["H20-A1"],
            "p_holm": p_h["H20-A1"],
            "verdict": "CONFIRMED",
        },
        "H20-A2": {
            "heldout_schur_r2": 0.65,
            "interior_temporal_snr_ratio": 2.0,
            "interior_mean_lag1_acorr": 0.7,
            "p_raw_spatial_null": 0.5,
            "exact_q_haynsworth_inertia_additivity": True,
            "inertia_full_12x12": [12, 0, 0],
            "inertia_interior_4x4": [4, 0, 0],
            "inertia_schur_boundary_8x8": [8, 0, 0],
            "p_raw": p_raws["H20-A2"],
            "p_holm": p_h["H20-A2"],
            "verdict": "PARTIAL",
        },
        "H20-B1": {
            "unique_rpm_pairs_count": 1,
            "qin_maya_crt_beat_witnesses": [
                {
                    "rpm1": 3400,
                    "rpm2": 3300,
                    "f1_hz_q": "170/3",
                    "f2_hz_q": "55/1",
                    "beat_hz_q": "5/3",
                    "crt_phase_sync_s_q": "3/5",
                }
            ],
            "p_raw_dynamic_circular_null": p_raws["H20-B1"],
            "p_raw_peak_freq_tracking_null": p_raws["H20-B1"],
            "p_raw_4pole_lock_null": p_raws["H20-B1"],
            "p_raw_harmonic_lock_null": p_raws["H20-B1"],
            "p_raw": p_raws["H20-B1"],
            "p_holm": p_h["H20-B1"],
            "verdict": "CONFIRMED",
        },
        "H20-B2": {
            "stratum_all_peaks": {
                "mean_53tet_cents_cmpPower": 5.5,
                "mean_12tet_cents_cmpPower": 24.0,
                "sample_pairs_exact_cmpPower": [{"ratio_q": "3/2", "k53": 31, "k12": 7}],
            },
            "stratum_mains_excluded": {
                "mean_53tet_cents_cmpPower": 5.6,
                "mean_12tet_cents_cmpPower": 24.5,
                "sample_pairs_exact_cmpPower": [{"ratio_q": "4/3", "k53": 22, "k12": 5}],
            },
            "p_raw": p_raws["H20-B2"],
            "p_holm": p_h["H20-B2"],
            "verdict": "FALSIFIED",
        },
        "H20-B3": {
            "psd_violations": 0,
            "exact_q_session_mean_fan_hermitian_inertia": [3, 0, 0],
            "directional_vs_diffuse_reff_gap": 1.1,
            "n_transients_fitted": 2,
            "p_raw_transient_damping_diff": 1.0,
            "p_raw": p_raws["H20-B3"],
            "p_holm": p_h["H20-B3"],
            "verdict": "PARTIAL",
        },
        "H20-C1": {
            "active_channels": ["M1_vis_luma", "M3_mic_rms", "M4_fan_rpm"],
            "n_pairs_tested": 3,
            "n_pairs_surviving_both_nulls_holm_001": 2,
            "pair_couplings": [
                {
                    "pair": "M1_vis_luma__x__M3_mic_rms",
                    "opt_lag_s": 0,
                    "p_circ_raw": 0.5,
                    "p_circ_holm": 0.5,
                    "p_iaaft_raw": 0.5,
                    "p_iaaft_holm": 0.5,
                    "survives_both_nulls_001": False,
                },
                {
                    "pair": "M1_vis_luma__x__M4_fan_rpm",
                    "opt_lag_s": 2,
                    "p_circ_raw": 0.000999,
                    "p_circ_holm": 0.002997,
                    "p_iaaft_raw": 0.000999,
                    "p_iaaft_holm": 0.002997,
                    "survives_both_nulls_001": True,
                },
                {
                    "pair": "M3_mic_rms__x__M4_fan_rpm",
                    "opt_lag_s": 1,
                    "p_circ_raw": 0.000999,
                    "p_circ_holm": 0.002997,
                    "p_iaaft_raw": 0.000999,
                    "p_iaaft_holm": 0.002997,
                    "survives_both_nulls_001": True,
                },
            ],
            "cech_h1_triples_count": 1,
            "cech_h1_nonzero_holonomy_count": 1,
            "cech_h1_mean_abs_lag_holonomy_s": 1.0,
            "cech_h1_sample_triples": [
                {
                    "triple": ["M1_vis_luma", "M3_mic_rms", "M4_fan_rpm"],
                    "lag_holonomy_s": -1,
                    "transitivity_obstruction": 0.1,
                }
            ],
            "p_raw": p_raws["H20-C1"],
            "p_holm": p_h["H20-C1"],
            "verdict": "CONFIRMED",
        },
        "H20-C2": {
            "khipu_tree_checksum": {
                "root_merkle_sha256": "a" * 64,
                "root_value": 123456,
                "tamper_trials": 200,
                "tamper_detected": 200,
                "tamper_escapes": 0,
            },
            "thermal_governor_live_replay": {
                "default_70_78_85_ladder": {
                    "bangbang_switches": 100,
                    "hysteresis_switches": 10,
                    "reduction_ratio": 10.0,
                },
                "operating_band_2c_deadband": {"reduction_ratio": 8.0},
                "operating_band_5c_deadband": {"reduction_ratio": 12.0},
            },
            "panini_c1p_live_replay": {
                "cross_modal_regimes_on_thermal_spine": {
                    "c1p_admissible": False,
                    "compression_ratio_q": None,
                    "compression_ratio_float": None,
                    "intervals": {},
                    "obstructed_count": 1,
                    "obstructed_tags": {"acoustic_above_med": 12},
                },
                "monotone_thermal_regimes": {
                    "spine_len": 32,
                    "tag_count": 4,
                    "c1p_admissible": True,
                    "naive_bitset_bits": 128,
                    "c1p_descriptor_bits": 40,
                    "compression_ratio_q": "16/5",
                    "compression_ratio_float": 3.2,
                    "intervals": {"t0": [0, 7], "t1": [8, 15], "t2": [16, 23], "t3": [24, 31]},
                    "obstructed_count": 0,
                    "obstructed_tags": {},
                },
            },
            "p_raw": None,
            "p_holm": None,
            "verdict": "CONFIRMED",
        },
    }
    payload: Dict[str, Any] = {
        "schema": SCHEMA_RESULTS,
        "analysis_plan_sha256": PINNED_ANALYSIS_PLAN_SHA256,
        "dataset_prefix": "selftest_",
        "seed": 20261126,
        "n_nulls": 1000,
        "energy_power_status": "UNCONTROLLED_LAPTOP_NOT_CLAIMED",
        "privacy_and_shutoff_receipt": {
            "start_epoch_s": 1795689600.0,
            "stop_epoch_s": 1795693499.0,
            "hard_stop_epoch_s": ABSOLUTE_HARD_STOP_EPOCH,
            "stopped_before_hard_stop": True,
            "video_handles_after_close": 0,
            "raw_media_files_count": 0,
            "passive_zero_output_enforced": True,
            "zero_power_energy_reads": True,
            "zero_ssid_mac_reads": True,
        },
        "summary": {
            "holm_bonferroni_pvals": p_h,
            "verdicts": {k: hyps[k]["verdict"] for k in ALL_HYP_KEYS},
        },
        "hypotheses": hyps,
    }
    p_sha = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    doc = dict(payload)
    doc["payload_sha256"] = p_sha
    doc["results_sha256"] = hashlib.sha256(_canonical_json_bytes(doc)).hexdigest()
    return doc


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pure-stdlib fail-closed verifier for the multimodal historical interposition study"
    )
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        "--check-bundle",
        nargs="?",
        const=Path(__file__).resolve().parent,
        type=Path,
        help="Verify committed ANALYSIS_PLAN.md and results JSON raw bytes & schema (default)",
    )
    group.add_argument("--selftest", action="store_true", help="Run standalone pure-stdlib contract selftest")
    group.add_argument("--check", type=Path, help="Fail-closed verify a standalone results JSON file")
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            res = validate_results_document(build_selftest_fixture())
        elif args.check is not None:
            res = check_results_file(args.check)
        else:
            bundle_dir = args.check_bundle if args.check_bundle is not None else Path(__file__).resolve().parent
            res = check_study_bundle(bundle_dir)
        sys.stdout.write(json.dumps(res, indent=2, sort_keys=True) + "\n")
        return 0
    except StudyVerifyError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
