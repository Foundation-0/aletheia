#!/usr/bin/env python3
"""Pure-stdlib fail-closed verifier & exact-Q SO(d) Cayley geodesic geometry oracle.

Verifies the two-phase SO(d) Cayley geodesic step-retraction weight-editing study:
  1. Pure-Q exact SO(d) Cayley transform oracle Q(gamma * S) = (I - gamma*S)(I + gamma*S)^(-1)
     certifying exact orthogonality (Q^T Q == I), exact orientation (det Q == 1/1),
     exact shell-norm preservation (||Q x||^2 == ||x||^2), exact flow-subspace invariance
     (Q u == u for u in span(U_flow)), and exact geodesic retraction monotonicity over
     gamma in {1, 1/2, 1/4} using fractions.Fraction with zero IEEE-754 floats.
  2. Strict energy-claim policy guard (NFKC -> NFKD -> drop Cf/Mn -> non-ASCII homoglyph
     rejection -> full SI/separator/per-token/relative-prose scan) plus host-path leak
     rejection across every key and string value in every on-disk JSON artifact.
  3. 100% on-disk self-bound cryptographic verification of Phase 1 (3-seed binary-gate
     honest FALSIFIED prerequisite) and Phase 2 (5-seed geodesic retraction CONFIRMED),
     independently recomputing 16-byte <4f unit-spinor norms, df=2 and df=4 paired
     Student-t statistics, Holm-Bonferroni p_Holm, poison-rollback totals, and G1/G2/G3
     verdicts with zero unbound external hashes.
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
import struct
import sys
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import unicodedata

SCHEMA_CERT = "so_d_geodesic_retraction_certificate_v1"
SCHEMA_PHASE1 = "so_d_phase1_binary_gate_results_v1"
SCHEMA_PHASE2 = "so_d_phase2_geodesic_retraction_results_v1"
SCHEMA_DET_RECEIPT = "hardware_determinism_receipt_v1"
ENERGY_POLICY_EXPECTED = "UNCONTROLLED_LAPTOP_NOT_CLAIMED"
PINNED_CERTIFICATE_SHA256 = "ef1cda74445458021f148cafc1a9f618eac909122da876143d73a9316ed56146"

WEFT_PI_T0_BYTES = 16
UNIT_SPINOR_N2_TOL = 0.0009765625  # Exact dyadic 1/1024
STAT_TOL = 1e-8  # Strictly bounds 8-decimal JSON rounding (<= 5e-9); >1700x tighter than p_holm=1.739e-5
MAX_JSON_DEPTH = 32
MAX_FILE_BYTES = 1048576
MAX_JSON_INT_DIGITS = 1024
FORBIDDEN_PATH_SUBSTR = "/" + "home" + "/"

ORACLE_FUNC_NAMES = (
    "q_div",
    "_mat_mul_q",
    "_mat_inv_q",
    "_mat_det_q",
    "cayley_transform_q",
    "verify_cayley_geodesic_ladder",
    "certify_exact_so_d_cayley_oracle",
)
_PROTECTED_FUNC_NAMES = frozenset(ORACLE_FUNC_NAMES) | frozenset({"require_ok"})
_ALLOWED_TOP_IMPORTS = frozenset(
    {
        "argparse",
        "ast",
        "errno",
        "hashlib",
        "hmac",
        "json",
        "math",
        "os",
        "re",
        "stat",
        "struct",
        "sys",
        "unicodedata",
    }
)
_ALLOWED_TOP_FROM_MODULES = frozenset({"__future__", "fractions", "pathlib", "typing"})
_ORACLE_ALLOWED_GLOBALS = frozenset(ORACLE_FUNC_NAMES) | frozenset(
    {
        "Fraction",
        "StudyVerifyError",
        "all",
        "isinstance",
        "len",
        "list",
        "range",
        "require_ok",
        "sum",
        "tuple",
        "type",
    }
)
_ORACLE_FORBIDDEN_NAMES = frozenset(
    {
        "float",
        "complex",
        "pow",
        "divmod",
        "getattr",
        "setattr",
        "delattr",
        "eval",
        "exec",
        "compile",
        "__import__",
        "vars",
        "globals",
        "locals",
        "dir",
        "builtins",
        "__builtins__",
        "sys",
        "struct",
        "operator",
        "fractions",
    }
)
_ORACLE_FORBIDDEN_ATTRS = frozenset(
    {
        "from_float",
        "from_decimal",
        "as_integer_ratio",
        "truediv",
        "itruediv",
        "floordiv",
        "ifloordiv",
        "real",
        "imag",
        "conjugate",
        "modules",
    }
)

# Linear-time O(N) energy-claim guard (NFKC -> NFKD -> drop Cf/Mn -> casefold; bounded quantifiers).
_PFX = r"(?:p|n|u|\u03bc|m|k|g|t|pico|nano|micro|milli|kilo|mega|giga|tera)"
_UNIT = r"(?:watt[^a-z0-9]{0,2}hours?|watthours?|wattages?|watts?|joules?|whrs?|wh|ws|w|j|tdp|mah)"
_UNIT_MULTI = r"(?:watt[^a-z0-9]{0,2}hours?|watthours?|wattages?|watts?|joules?|whrs?|wh|ws|tdp|mah)"
_LONG_UNIT = r"(?:watt[^a-z0-9]{0,2}hours?|watthours?|wattages?|watts?|joules?)"
_SEP = r"[^a-z0-9,;=]{0,4}"
_NUM = r"(?<!\d)\d{1,18}(?:[.,]\d{1,18}){0,4}(?:e[+-]?\d{1,4})?"
_WORD_NUM = (
    r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
    r"fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|"
    r"sixty|seventy|eighty|ninety|hundred|thousand)"
    r"(?:[\s-]{1,2}(?:one|two|three|four|five|six|seven|eight|nine|hundred|thousand)){0,2}"
)
_ENERGY_VALUE_RE = re.compile(
    "(?:"
    rf"{_NUM}{_SEP}(?:{_PFX}{_SEP})?{_UNIT}(?![a-z0-9])(?!/)"
    rf"|(?<![a-z0-9])(?:(?:{_PFX}{_SEP})?{_UNIT_MULTI}|{_PFX}{_SEP}[wj]|energy|power)(?:\s{{0,4}}[:=]\s{{0,4}}|\s{{1,4}}){_NUM}(?![a-z0-9_-])"
    rf"|(?<![a-z0-9])[wj](?:\s{{0,4}}:\s{{0,4}}|=|\s{{1,4}}){_NUM}(?![a-z0-9_-])"
    rf"|(?<![a-z0-9]){_WORD_NUM}[\s-]{{1,4}}(?:{_PFX}[\s-]{{0,2}})?(?:watts?|joules?|watt[\s-]{{0,2}}hours?|watthours?|whrs?|wh|ws|tdp|mah)(?![a-z0-9])"
    rf"|(?<![a-z0-9])(?:{_PFX}{_SEP})?{_LONG_UNIT}(?![a-z0-9])"
    rf"|(?<![a-z0-9])tdp[^a-z0-9]{{0,4}}{_NUM}"
    rf"|^[^a-z0-9]{{0,4}}(?:{_PFX}{_SEP})?{_UNIT}[^a-z0-9]{{0,4}}$"
    r"|(?<![a-z0-9])(?:energy|power|joules?|watts?|watthours?|mwh|kwh|wh|mj|uj|nj|pj|mw|kw|uw|j)(?:[\s_]{1,4}per[\s_]{1,4}|\s{0,4}/\s{0,4})(?:tok(?:en)?s?|s|sec(?:ond)?s?|ms|us|ns|min(?:ute)?s?|hr?s?)(?![a-z0-9])"
    r"|(?<![a-z0-9])w(?:[\s_]{1,4}per[\s_]{1,4}|/(?!\s))(?:tok(?:en)?s?|s|sec(?:ond)?s?)(?![a-z0-9])"
    rf"|{_NUM}{_SEP}w\s{{0,4}}/\s{{0,4}}(?:tok(?:en)?s?|s|sec(?:ond)?s?)(?![a-z0-9])"
    rf"|{_NUM}\s{{1,4}}(?:v|volts?)\s{{1,4}}(?:@|at)\s{{1,4}}{_NUM}\s{{1,4}}(?:m?a|amps?|amperes?)(?![a-z0-9])"
    rf"|{_NUM}\s{{1,4}}(?:m?a|amps?|amperes?)\s{{1,4}}(?:@|at)\s{{1,4}}{_NUM}\s{{1,4}}(?:v|volts?)(?![a-z0-9])"
    r"|(?<![a-z0-9])tok(?:en)?s?(?:[\s_]{1,4}per[\s_]{1,4}|\s{0,4}/\s{0,4})(?:energy|power|joules?|watts?|watthours?|mwh|kwh|wh|mj|uj|nj|pj|mw|kw|uw|j|w)(?![a-z0-9])"
    r"|(?<![a-z0-9])(?:rapl|nvml|nvidia[^a-z0-9]{0,2}smi)"
    r"|(?<![a-z0-9])mah(?![a-z0-9])"
    r"|(?<![a-z0-9])(?:less|lower|reduced|fewer)[\s_]{1,4}(?:in[\s_]{1,4})?(?:energy|power)(?![a-z0-9])"
    r"|(?<![a-z0-9])(?:energy|power)[\s_]{1,4}(?:use|usage|reduction|savings?|dropped|consumption|draw|consumed|limit|budget|cap|metric|telemetry)(?![a-z0-9])"
    ")"
)
_ENERGY_KEY_RE = re.compile(
    r"(?:(?:^|[^a-z0-9])(?:power|watt|watts|wattage|wattages|joule|joules|energy|kwh|mwh|whr|wh|ws|tdp|mj|uj|mw|kw|gw|tw|rapl|nvml|mah)(?:[^a-z0-9]|$)"
    r"|(?:^|[^a-z0-9])(?:pkg|gpu|cpu|sys|avg|peak|max|min|total|board)[^a-z0-9]{1,4}(?:w|j)(?:[^a-z0-9]|$))"
)
_CAMEL_SPLIT_RE = re.compile(r"([a-z0-9])([A-Z])")
_ALLOWLISTED_POLICY_KEYS = frozenset({"energy_power_status"})


class StudyVerifyError(ValueError):
    """Typed fail-closed error for SO(d) geodesic retraction study verification."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


def require_ok(cond: bool, code: str, message: str) -> None:
    if cond is not True:
        raise StudyVerifyError(code, message)


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=True
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_regular_bytes_nofollow(path: Path, missing_code: str = "FILE_MISSING") -> bytes:
    require_ok(isinstance(path, Path), missing_code, "Invalid path object")
    require_ok(
        not any(parent.is_symlink() for parent in path.absolute().parents),
        "SYMLINK_FORBIDDEN",
        f"Ancestor symlink forbidden: {path.name}",
    )
    try:
        fd = os.open(path, os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise StudyVerifyError("SYMLINK_FORBIDDEN", f"Symlink forbidden: {path.name}") from exc
        raise StudyVerifyError(missing_code, f"Missing or unreadable file: {path.name}") from exc
    try:
        st = os.fstat(fd)
        require_ok(stat.S_ISREG(st.st_mode), "NOT_REGULAR_FILE", f"Not a regular file: {path.name}")
    except BaseException:
        os.close(fd)
        raise
    try:
        with os.fdopen(fd, "rb") as handle:
            raw = handle.read(MAX_FILE_BYTES + 1)
    except OSError as exc:
        raise StudyVerifyError(missing_code, f"Failed reading file: {path.name}") from exc
    require_ok(len(raw) <= MAX_FILE_BYTES, "FILE_TOO_LARGE", f"File exceeds byte limit: {path.name}")
    return raw


def _read_utf8_nofollow(path: Path, missing_code: str = "FILE_MISSING") -> str:
    raw = _read_regular_bytes_nofollow(path, missing_code=missing_code)
    require_ok(not raw.startswith(b"\xef\xbb\xbf"), "UTF8_BOM_FORBIDDEN", f"UTF-8 BOM forbidden: {path.name}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StudyVerifyError("JSON_PARSE_FAIL", f"Invalid UTF-8 in {path.name}") from exc


def _write_utf8_nofollow(path: Path, text: str) -> None:
    require_ok(isinstance(path, Path), "IO_ERROR", "Invalid output path")
    require_ok(
        not any(parent.is_symlink() for parent in path.absolute().parents),
        "SYMLINK_FORBIDDEN",
        f"Symlink forbidden on write path: {path.name}",
    )
    data = text.encode("utf-8")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise StudyVerifyError("SYMLINK_FORBIDDEN", f"Symlink forbidden: {path.name}") from exc
        raise StudyVerifyError("IO_ERROR", f"Cannot open output file: {path.name}") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
    except OSError as exc:
        raise StudyVerifyError("IO_ERROR", f"Failed writing output file: {path.name}") from exc


def file_sha256(path: Path) -> str:
    return sha256_hex(_read_regular_bytes_nofollow(path, missing_code="FILE_MISSING"))


def _normalize_policy_text(text: str) -> str:
    norm = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", text))
    return "".join(
        ch for ch in norm if unicodedata.category(ch) not in ("Cf", "Mn")
    ).casefold()


def _has_non_ascii_letter(text: str) -> bool:
    return any(
        ord(ch) > 127 and ch.isalpha() and ch not in ("\u03bc", "\u00b5")
        for ch in text
    )


def is_forbidden_energy_value(text: str) -> bool:
    require_ok(type(text) is str, "BAD_POLICY_STR", "Policy text must be str")
    norm = _normalize_policy_text(text)
    if _has_non_ascii_letter(norm):
        return True
    return bool(_ENERGY_VALUE_RE.search(norm))


def is_forbidden_energy_key(key: str) -> bool:
    require_ok(type(key) is str, "BAD_POLICY_KEY", "Policy key must be str")
    if key in _ALLOWLISTED_POLICY_KEYS:
        return False
    split_key = _CAMEL_SPLIT_RE.sub(r"\1 \2", key).replace("_", " ")
    norm = _normalize_policy_text(split_key)
    if _has_non_ascii_letter(norm):
        return True
    return bool(_ENERGY_KEY_RE.search(norm)) or bool(_ENERGY_VALUE_RE.search(norm))


def scan_json_tree_clean(root: Any, max_depth: int = MAX_JSON_DEPTH) -> None:
    """Iterative depth-capped tree scan enforcing energy policy, finite floats, and zero host leaks."""
    require_ok(type(max_depth) is int and max_depth >= 1, "BAD_MAX_DEPTH", "max_depth must be int >= 1")
    stack: List[Tuple[Any, int, Optional[str]]] = [(root, 0, None)]
    while stack:
        node, depth, parent_key = stack.pop()
        require_ok(depth <= max_depth, "JSON_DEPTH", "JSON nesting depth exceeded")
        t = type(node)
        if t is float:
            require_ok(math.isfinite(node), "NONFINITE_FLOAT", "NaN/Inf forbidden")
        elif t is str:
            require_ok(FORBIDDEN_PATH_SUBSTR not in node.lower(), "PATH_LEAK", "Host path leak detected")
            require_ok(
                not is_forbidden_energy_value(node),
                "ENERGY_CLAIM_VALUE",
                f"Forbidden energy/power claim value: {node!r}",
            )
            if parent_key in _ALLOWLISTED_POLICY_KEYS:
                require_ok(
                    node == ENERGY_POLICY_EXPECTED,
                    "ALLOWLIST_SMUGGLE",
                    "energy_power_status must equal UNCONTROLLED_LAPTOP_NOT_CLAIMED",
                )
        elif t is dict:
            for k, v in node.items():
                require_ok(type(k) is str, "BAD_KEY", "Dict key must be str")
                require_ok(FORBIDDEN_PATH_SUBSTR not in k.lower(), "PATH_LEAK", "Host path leak in key")
                require_ok(
                    not is_forbidden_energy_key(k),
                    "ENERGY_CLAIM_KEY",
                    f"Forbidden energy/power key: {k!r}",
                )
                if k in _ALLOWLISTED_POLICY_KEYS:
                    require_ok(type(v) is str, "ALLOWLIST_SMUGGLE", "energy_power_status must be str")
                stack.append((v, depth + 1, k))
        elif t is list:
            for item in node:
                stack.append((item, depth + 1, parent_key))
        elif t in (int, bool) or node is None:
            continue
        else:
            raise StudyVerifyError("BAD_JSON_TYPE", f"Unsupported JSON type: {t.__name__}")


def _no_dup_pairs(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in pairs:
        require_ok(k not in out, "JSON_DUP_KEY", f"Duplicate JSON key: {k!r}")
        out[k] = v
    return out


def _strict_parse_int(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    require_ok(len(digits) <= MAX_JSON_INT_DIGITS, "JSON_PARSE_FAIL", "Integer exceeds digit limit")
    return int(token)


def _reject_json_constant(token: str) -> Any:
    raise StudyVerifyError("NONFINITE_FLOAT", f"Non-finite JSON constant forbidden: {token}")


def load_strict_json(path: Path) -> Dict[str, Any]:
    raw = _read_utf8_nofollow(path, missing_code="JSON_MISSING")
    try:
        obj = json.loads(
            raw,
            object_pairs_hook=_no_dup_pairs,
            parse_int=_strict_parse_int,
            parse_constant=_reject_json_constant,
        )
    except StudyVerifyError:
        raise
    except (ValueError, RecursionError) as exc:
        raise StudyVerifyError("JSON_PARSE_FAIL", f"Failed to parse {path.name}: {exc}") from exc
    require_ok(type(obj) is dict, "JSON_NOT_OBJ", "Root JSON must be object")
    scan_json_tree_clean(obj)
    return obj


def _strict_int(val: Any, code: str, name: str) -> int:
    require_ok(type(val) is int, code, f"{name} must be strict int")
    return val


def _strict_float(val: Any, code: str, name: str) -> float:
    require_ok(type(val) in (int, float), code, f"{name} must be finite number")
    try:
        fval = float(val)
    except OverflowError as exc:
        raise StudyVerifyError(code, f"{name} overflow in float conversion") from exc
    require_ok(math.isfinite(fval), code, f"{name} must be finite number")
    return fval


def _strict_hex64(val: Any, code: str, name: str) -> str:
    require_ok(type(val) is str and len(val) == 64, code, f"{name} must be 64-char hex")
    for ch in val:
        require_ok(ch in "0123456789abcdef", code, f"{name} must be lowercase hex")
    return val


def _digest_eq(got: str, expected: str) -> bool:
    return hmac.compare_digest(got.encode("ascii"), expected.encode("ascii"))


# ---------------------------------------------------------------------------
# Module A: Exact Pure-Q SO(d) Cayley Geodesic Step-Retraction Oracle
# ---------------------------------------------------------------------------


def _collect_annotation_node_ids(tree: ast.AST) -> Set[int]:
    ann_ids: Set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and node.annotation is not None:
            ann_ids.update(id(sub) for sub in ast.walk(node.annotation))
        elif isinstance(node, ast.FunctionDef) and node.returns is not None:
            ann_ids.update(id(sub) for sub in ast.walk(node.returns))
        elif isinstance(node, ast.AnnAssign) and node.annotation is not None:
            ann_ids.update(id(sub) for sub in ast.walk(node.annotation))
    return ann_ids


def verify_oracle_ast_purity(source_text: str) -> Dict[str, int]:
    """Fail-closed pure-Q AST guard across whole-file escapes and all Module A oracle functions."""
    try:
        tree = ast.parse(source_text)
    except SyntaxError as exc:
        raise StudyVerifyError("AST_SYNTAX_ERROR", f"Invalid Python syntax: {exc}") from exc

    all_nodes = list(ast.walk(tree))
    bare_asserts = sum(1 for n in all_nodes if isinstance(n, ast.Assert))
    require_ok(bare_asserts == 0, "AST_BARE_ASSERT", "Bare assert forbidden")

    async_defs = sum(1 for n in all_nodes if isinstance(n, ast.AsyncFunctionDef))
    require_ok(async_defs == 0, "ORACLE_AST_ASYNC", "async def forbidden")

    floordiv_ops = sum(1 for n in all_nodes if isinstance(n, (ast.FloorDiv, ast.MatMult, ast.Mod)))
    require_ok(floordiv_ops == 0, "ORACLE_AST_FLOORDIV", "FloorDiv, MatMult, and Mod forbidden")

    format_specs = sum(1 for n in all_nodes if isinstance(n, ast.FormattedValue) and n.format_spec is not None)
    require_ok(format_specs == 0, "ORACLE_AST_FORMAT_SPEC", "FormattedValue format_spec forbidden")

    # Whole-file import allowlist: imports permitted only at module top-level with no aliases.
    top_import_ids = {id(n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))}
    forbidden_import = 0
    for node in all_nodes:
        if isinstance(node, ast.Import):
            if id(node) not in top_import_ids:
                forbidden_import += 1
            for alias in node.names:
                if alias.name not in _ALLOWED_TOP_IMPORTS or alias.asname is not None:
                    forbidden_import += 1
        elif isinstance(node, ast.ImportFrom):
            if id(node) not in top_import_ids or node.level != 0 or node.module not in _ALLOWED_TOP_FROM_MODULES:
                forbidden_import += 1
            for alias in node.names:
                if alias.asname is not None or (node.module == "fractions" and alias.name != "Fraction"):
                    forbidden_import += 1
    require_ok(forbidden_import == 0, "ORACLE_AST_IMPORT", "Disallowed or aliased import")

    # Whole-file attribute guard (blocks dunder escapes & float/truediv/from_float bridges everywhere).
    for node in all_nodes:
        if isinstance(node, ast.Attribute):
            is_bad_dunder = (
                node.attr.startswith("__")
                and node.attr.endswith("__")
                and node.attr not in ("__init__", "__name__")
            )
            require_ok(
                not is_bad_dunder and node.attr not in _ORACLE_FORBIDDEN_ATTRS,
                "ORACLE_AST_ATTR",
                f"Forbidden attribute {node.attr}",
            )
            require_ok(node.attr != "Fraction", "ORACLE_AST_FRAC_ALIAS", "Attribute Fraction access forbidden")

    # Whole-file first-class Fraction guard: Fraction may only appear as direct Call.func, static annotation, or isinstance/type guard.
    ann_ids = _collect_annotation_node_ids(tree)
    valid_frac_ids: Set[int] = set()
    fraction_str_or_from_float = 0
    for node in all_nodes:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Fraction":
            require_ok(len(node.keywords) == 0, "ORACLE_AST_FRAC_KW", "Fraction kwargs forbidden")
            require_ok(len(node.args) in (1, 2), "ORACLE_AST_FRAC_ARITY", "Fraction arity must be 1 or 2")
            for arg in node.args:
                for sub in ast.walk(arg):
                    if isinstance(sub, ast.JoinedStr) or (
                        isinstance(sub, ast.Constant)
                        and type(sub.value).__name__ in ("str", "bytes", "float", "complex")
                    ):
                        fraction_str_or_from_float += 1
            require_ok(fraction_str_or_from_float == 0, "ORACLE_AST_FRAC_STR", "Fraction(str/float) forbidden")
            valid_frac_ids.add(id(node.func))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "isinstance"
            and len(node.args) == 2
            and len(node.keywords) == 0
            and isinstance(node.args[1], ast.Name)
            and node.args[1].id == "Fraction"
        ):
            valid_frac_ids.add(id(node.args[1]))
        elif (
            isinstance(node, ast.Compare)
            and isinstance(node.left, ast.Call)
            and isinstance(node.left.func, ast.Name)
            and node.left.func.id == "type"
            and len(node.left.args) == 1
            and len(node.left.keywords) == 0
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.Is)
            and len(node.comparators) == 1
            and isinstance(node.comparators[0], ast.Name)
            and node.comparators[0].id == "Fraction"
        ):
            valid_frac_ids.add(id(node.comparators[0]))

    for node in all_nodes:
        if isinstance(node, ast.Name) and node.id == "Fraction":
            require_ok(
                id(node) in valid_frac_ids or id(node) in ann_ids,
                "ORACLE_AST_FRAC_ALIAS",
                "First-class aliasing or rebinding of Fraction forbidden",
            )
        if isinstance(node, ast.arg):
            require_ok(node.arg != "Fraction", "ORACLE_AST_FRAC_ALIAS", "Parameter shadowing Fraction forbidden")
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.ExceptHandler)):
            require_ok(node.name != "Fraction", "ORACLE_AST_FRAC_ALIAS", "Definition shadowing Fraction forbidden")
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            require_ok(
                node.id not in _PROTECTED_FUNC_NAMES,
                "ORACLE_AST_REBIND",
                f"Rebinding or deleting protected symbol {node.id} forbidden",
            )

    dynamic_calls = sum(
        1 for n in all_nodes if isinstance(n, ast.Call) and not isinstance(n.func, (ast.Name, ast.Attribute))
    )
    require_ok(dynamic_calls == 0, "ORACLE_AST_CALL", "Dynamic or computed callable forbidden")

    # Top-level function table & anti-shadowing / anti-decorator checks.
    top_func_ids = {id(n) for n in tree.body if isinstance(n, ast.FunctionDef)}
    funcs: Dict[str, ast.FunctionDef] = {}
    for node in all_nodes:
        if isinstance(node, ast.FunctionDef) and node.name in _PROTECTED_FUNC_NAMES:
            require_ok(id(node) in top_func_ids, "ORACLE_AST_REBIND", f"Nested protected def {node.name} forbidden")
            require_ok(node.name not in funcs, "ORACLE_AST_REBIND", f"Duplicate def {node.name} forbidden")
            require_ok(len(node.decorator_list) == 0, "ORACLE_AST_DECORATOR", f"Decorator on {node.name} forbidden")
            funcs[node.name] = node

    oracle_funcs = [funcs[fname] for fname in ORACLE_FUNC_NAMES if fname in funcs]
    require_ok(
        len(oracle_funcs) == len(ORACLE_FUNC_NAMES),
        "ORACLE_FUNC_MISSING",
        "Missing required oracle function",
    )

    check_funcs = list(oracle_funcs)
    if "require_ok" in funcs:
        check_funcs.append(funcs["require_ok"])

    ast_div = 0
    float_or_complex = 0
    forbidden_pow_or_call = 0
    free_vars = 0
    for fn in check_funcs:
        local_names = {a.arg for a in fn.args.args} | {
            n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
        }
        for node in ast.walk(fn):
            if isinstance(node, ast.Div):
                ast_div += 1
            elif isinstance(node, ast.Constant) and type(node.value).__name__ in ("float", "complex"):
                float_or_complex += 1
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
                is_nonneg = isinstance(node.right, ast.Constant) and type(node.right.value) is int and node.right.value >= 0
                require_ok(is_nonneg, "ORACLE_AST_POW", f"Negative/non-const Pow forbidden in {fn.name}")
            elif isinstance(node, ast.AugAssign):
                require_ok(not isinstance(node.op, ast.Pow), "ORACLE_AST_POW", f"Augmented Pow forbidden in {fn.name}")
            elif isinstance(node, ast.Attribute):
                require_ok(
                    not node.attr.startswith("__"),
                    "ORACLE_AST_ATTR",
                    f"Dunder attribute {node.attr} forbidden in {fn.name}",
                )
            elif isinstance(node, ast.Name):
                require_ok(node.id != "math", "ORACLE_AST_MATH", f"math forbidden in {fn.name}")
                if node.id in _ORACLE_FORBIDDEN_NAMES:
                    forbidden_pow_or_call += 1
                elif (
                    isinstance(node.ctx, ast.Load)
                    and id(node) not in ann_ids
                    and node.id not in local_names
                    and node.id not in _ORACLE_ALLOWED_GLOBALS
                ):
                    free_vars += 1
        require_ok(ast_div == 0, "ORACLE_AST_DIV", f"ast.Div forbidden in {fn.name}")
        require_ok(float_or_complex == 0, "ORACLE_AST_FLOAT", f"Float/complex literal forbidden in {fn.name}")
        require_ok(forbidden_pow_or_call == 0, "ORACLE_AST_CALL", f"Forbidden name in {fn.name}")
        require_ok(free_vars == 0, "ORACLE_AST_FREE_VAR", f"Unallowlisted free symbol in {fn.name}")

    return {
        "oracle_functions_checked": len(oracle_funcs),
        "ast_div": ast_div,
        "float_or_complex": float_or_complex,
        "forbidden_pow_or_call": forbidden_pow_or_call,
        "forbidden_import": forbidden_import,
        "fraction_str_or_from_float": fraction_str_or_from_float,
        "bare_asserts": bare_asserts,
    }


def q_div(a: Fraction, b: Fraction) -> Fraction:
    """Exact rational division via integer cross-multiplication (zero ast.Div)."""
    require_ok(isinstance(a, Fraction) and isinstance(b, Fraction), "QDIV_TYPE", "Expected Fraction operands")
    require_ok(b.numerator != 0, "QDIV_ZERO", "Division by zero")
    return Fraction(a.numerator * b.denominator, a.denominator * b.numerator)


def _mat_mul_q(a: List[List[Fraction]], b: List[List[Fraction]]) -> List[List[Fraction]]:
    rows = len(a)
    inner = len(b)
    cols = len(b[0])
    return [
        [
            sum((a[i][k] * b[k][j] for k in range(inner)), Fraction(0, 1))
            for j in range(cols)
        ]
        for i in range(rows)
    ]


def _mat_inv_q(mat: List[List[Fraction]]) -> List[List[Fraction]]:
    n = len(mat)
    aug = [
        [mat[i][j] for j in range(n)]
        + [Fraction(1, 1) if i == j else Fraction(0, 1) for j in range(n)]
        for i in range(n)
    ]
    for col in range(n):
        piv = -1
        for r in range(col, n):
            if aug[r][col] != 0:
                piv = r
                break
        require_ok(piv != -1, "SINGULAR_MATRIX", f"Singular matrix at col {col}")
        if piv != col:
            aug[col], aug[piv] = aug[piv], aug[col]
        pv = aug[col][col]
        aug[col] = [q_div(x, pv) for x in aug[col]]
        for r in range(n):
            if r != col and aug[r][col] != 0:
                fac = aug[r][col]
                aug[r] = [aug[r][c] - fac * aug[col][c] for c in range(2 * n)]
    return [row[n:] for row in aug]


def _mat_det_q(mat: List[List[Fraction]]) -> Fraction:
    n = len(mat)
    a = [[mat[i][j] for j in range(n)] for i in range(n)]
    det = Fraction(1, 1)
    for col in range(n):
        piv = -1
        for r in range(col, n):
            if a[r][col] != 0:
                piv = r
                break
        if piv == -1:
            return Fraction(0, 1)
        if piv != col:
            a[col], a[piv] = a[piv], a[col]
            det = -det
        pv = a[col][col]
        det *= pv
        for r in range(col + 1, n):
            if a[r][col] != 0:
                fac = q_div(a[r][col], pv)
                for c in range(col + 1, n):
                    a[r][c] = a[r][c] - fac * a[col][c]
    return det


def cayley_transform_q(skew: List[List[Fraction]], gamma: Fraction) -> List[List[Fraction]]:
    """Exact rational Cayley transform Q(gamma * S) = (I - gamma*S)(I + gamma*S)^(-1) in SO(d)."""
    require_ok(isinstance(skew, (list, tuple)) and len(skew) >= 2, "BAD_SKEW_SHAPE", "Skew matrix must be square >= 2")
    require_ok(type(gamma) is Fraction, "BAD_GAMMA", "gamma must be Fraction")
    n = len(skew)
    require_ok(all(isinstance(row, (list, tuple)) and len(row) == n for row in skew), "BAD_SKEW_SHAPE", "Skew matrix must be square")
    for i in range(n):
        require_ok(skew[i][i] == 0, "NOT_SKEW_DIAG", "Skew matrix diagonal must be 0")
        for j in range(i + 1, n):
            require_ok(skew[i][j] == -skew[j][i], "NOT_SKEW_SYM", "Matrix must satisfy S^T == -S")
    eye = [[Fraction(1, 1) if i == j else Fraction(0, 1) for j in range(n)] for i in range(n)]
    m_plus = [[eye[i][j] + gamma * skew[i][j] for j in range(n)] for i in range(n)]
    m_minus = [[eye[i][j] - gamma * skew[i][j] for j in range(n)] for i in range(n)]
    return _mat_mul_q(m_minus, _mat_inv_q(m_plus))


def verify_cayley_geodesic_ladder(
    skew: List[List[Fraction]],
    probe_x: Sequence[Fraction],
    flow_basis: Sequence[Sequence[Fraction]],
    gammas: Sequence[Fraction],
) -> Dict[str, Any]:
    """Certify exact SO(d) Cayley identities, subspace invariance, & contraction bound over Q."""
    z = Fraction(0, 1)
    n = len(skew)
    norm2_x = sum((v * v for v in probe_x), z)
    skew_frob_sq = sum((skew[i][j] * skew[i][j] for i in range(n) for j in range(n)), z)
    frob_list: List[Fraction] = []
    records: List[Dict[str, Any]] = []
    for g in gammas:
        q = cayley_transform_q(skew, g)
        qt = [[q[j][i] for j in range(n)] for i in range(n)]
        qtq = _mat_mul_q(qt, q)
        orth_ok = all(
            qtq[i][j] == (Fraction(1, 1) if i == j else z)
            for i in range(n)
            for j in range(n)
        )
        det_q = _mat_det_q(q)
        qx = [sum((q[i][j] * probe_x[j] for j in range(n)), z) for i in range(n)]
        norm2_qx = sum((v * v for v in qx), z)
        flow_drift_sq = z
        for flow_u in flow_basis:
            qu = [sum((q[i][j] * flow_u[j] for j in range(n)), z) for i in range(n)]
            flow_drift_sq += sum(((qu[i] - flow_u[i]) ** 2 for i in range(n)), z)
        frob_sq = sum(
            ((q[i][j] - (Fraction(1, 1) if i == j else z)) ** 2 for i in range(n) for j in range(n)),
            z,
        )
        contraction_bound_sq = Fraction(4, 1) * g * g * skew_frob_sq
        require_ok(orth_ok, "ORACLE_NOT_ORTH", "Q^T Q != I")
        require_ok(det_q == Fraction(1, 1), "ORACLE_DET_BAD", "det(Q) != 1")
        require_ok(norm2_qx == norm2_x, "ORACLE_NORM_DRIFT", "||Qx||^2 != ||x||^2")
        require_ok(flow_drift_sq == z, "ORACLE_FLOW_DRIFT", "Flow subspace not invariant")
        require_ok(frob_sq <= contraction_bound_sq, "ORACLE_CONTRACTION_BOUND", "||Q(gS)-I||_F^2 > 4 g^2 ||S||_F^2")
        frob_list.append(frob_sq)
        records.append(
            {
                "gamma_q": f"{g.numerator}/{g.denominator}",
                "orthogonality_exact": orth_ok,
                "det_q": f"{det_q.numerator}/{det_q.denominator}",
                "shell_norm_sq_residual_q": f"{(norm2_qx - norm2_x).numerator}/{(norm2_qx - norm2_x).denominator}",
                "flow_subspace_drift_sq_q": f"{flow_drift_sq.numerator}/{flow_drift_sq.denominator}",
                "step_displacement_frob_sq_q": f"{frob_sq.numerator}/{frob_sq.denominator}",
                "cayley_contraction_upper_bound_q": f"{contraction_bound_sq.numerator}/{contraction_bound_sq.denominator}",
            }
        )

    retraction_monotone = all(frob_list[i] > frob_list[i + 1] for i in range(len(frob_list) - 1))
    require_ok(retraction_monotone, "ORACLE_NOT_MONOTONE", "Geodesic step norm not strictly monotone")
    return {
        "dim": n,
        "flow_dim": len(flow_basis),
        "nullspace_dim": n - len(flow_basis),
        "non_axis_aligned_subspace": True,
        "retraction_monotone_strict": retraction_monotone,
        "gamma_ladder": records,
    }


def certify_exact_so_d_cayley_oracle() -> Dict[str, Any]:
    """Certify exact SO(6) non-axis-aligned flow-nullspace Cayley geodesic identities over Q."""
    z = Fraction(0, 1)
    # Non-axis-aligned orthogonal 2D protected flow basis (each ||u||^2 == 4, u1 . u2 == 0)
    u1 = [Fraction(1, 1), Fraction(1, 1), Fraction(1, 1), Fraction(1, 1), z, z]
    u2 = [Fraction(1, 1), Fraction(-1, 1), z, z, Fraction(1, 1), Fraction(-1, 1)]
    p_perp = [
        [
            (Fraction(1, 1) if i == j else z)
            - q_div(u1[i] * u1[j] + u2[i] * u2[j], Fraction(4, 1))
            for j in range(6)
        ]
        for i in range(6)
    ]
    # Dense skew-symmetric generator projected into orthogonal complement: S = P_perp A P_perp
    raw_a = [[z for _ in range(6)] for _ in range(6)]
    raw_entries = (
        (0, 1, Fraction(1, 2)),
        (0, 4, Fraction(-1, 3)),
        (1, 5, Fraction(2, 5)),
        (2, 3, Fraction(1, 2)),
        (2, 4, Fraction(-1, 3)),
        (3, 5, Fraction(1, 4)),
    )
    for i, j, val in raw_entries:
        raw_a[i][j] = val
        raw_a[j][i] = -val
    s_proj = _mat_mul_q(_mat_mul_q(p_perp, raw_a), p_perp)
    probe_x = [Fraction(3, 1), Fraction(-2, 1), Fraction(5, 1), Fraction(1, 2), Fraction(-7, 3), Fraction(4, 1)]
    return verify_cayley_geodesic_ladder(s_proj, probe_x, (u1, u2), (Fraction(1, 1), Fraction(1, 2), Fraction(1, 4)))


# ---------------------------------------------------------------------------
# Module B: Spinor Checkpoints, Paired-t (df=2, df=4), Holm-Bonferroni
# ---------------------------------------------------------------------------


def verify_pi16_hex(hex_str: Any) -> Tuple[float, float, float, float]:
    require_ok(type(hex_str) is str and len(hex_str) == 32, "PI16_HEX_LEN", "pi16 hex must be 32 chars")
    try:
        raw = bytes.fromhex(hex_str)
    except ValueError as exc:
        raise StudyVerifyError("PI16_HEX_BAD", f"invalid hex: {exc}") from exc
    qw, qx, qy, qz = struct.unpack("<4f", raw)
    require_ok(
        math.isfinite(qw) and math.isfinite(qx) and math.isfinite(qy) and math.isfinite(qz),
        "PI16_NONFINITE",
        "pi16 contains non-finite float",
    )
    n2 = qw * qw + qx * qx + qy * qy + qz * qz
    require_ok(abs(n2 - 1.0) <= UNIT_SPINOR_N2_TOL, "PI16_NOT_UNIT", f"spinor n2={n2}")
    return (qw, qx, qy, qz)


def paired_t_df2(xs: Sequence[float], ys: Sequence[float]) -> Dict[str, float]:
    require_ok(isinstance(xs, (list, tuple)) and isinstance(ys, (list, tuple)) and len(xs) == 3 and len(ys) == 3, "STATS_DF2_LEN", "Expected 3 seeds")
    diffs = [_strict_float(a, "STATS_VAL", "x") - _strict_float(b, "STATS_VAL", "y") for a, b in zip(xs, ys)]
    mean_d = sum(diffs) / 3.0
    var_d = sum((d - mean_d) * (d - mean_d) for d in diffs) / 2.0
    require_ok(var_d > 0.0 and math.isfinite(var_d), "STATS_ZERO_VAR", "Degenerate or non-finite paired sample (df=2)")
    se_d = math.sqrt(var_d / 3.0)
    t_stat = mean_d / se_d
    p_raw = 1.0 - abs(t_stat) / math.sqrt(2.0 + t_stat * t_stat)
    return {"mean_diff": mean_d, "p_raw": max(0.0, min(1.0, p_raw))}


def paired_t_df4(xs: Sequence[float], ys: Sequence[float]) -> Dict[str, float]:
    require_ok(isinstance(xs, (list, tuple)) and isinstance(ys, (list, tuple)) and len(xs) == 5 and len(ys) == 5, "STATS_DF4_LEN", "Expected 5 seeds")
    diffs = [_strict_float(a, "STATS_VAL", "x") - _strict_float(b, "STATS_VAL", "y") for a, b in zip(xs, ys)]
    mean_d = sum(diffs) / 5.0
    var_d = sum((d - mean_d) * (d - mean_d) for d in diffs) / 4.0
    require_ok(var_d > 0.0 and math.isfinite(var_d), "STATS_ZERO_VAR", "Degenerate or non-finite paired sample (df=4)")
    se_d = math.sqrt(var_d / 5.0)
    t_stat = mean_d / se_d
    u = abs(t_stat) / math.sqrt(4.0 + t_stat * t_stat)
    p_raw = 1.0 - 0.5 * u * (3.0 - u * u)
    return {"mean_diff": mean_d, "p_raw": max(0.0, min(1.0, p_raw))}


def holm_3(p_vals: Sequence[float]) -> List[float]:
    require_ok(isinstance(p_vals, (list, tuple)) and len(p_vals) == 3, "HOLM_LEN", "Expected 3 p-values")
    vals = [_strict_float(v, "HOLM_VAL", "p_val") for v in p_vals]
    for v in vals:
        require_ok(0.0 <= v <= 1.0, "HOLM_RANGE", "p-value out of [0, 1]")
    indexed = sorted(enumerate(vals), key=lambda kv: kv[1])
    out = [0.0, 0.0, 0.0]
    run_max = 0.0
    for rank, (idx, pv) in enumerate(indexed):
        adj = min(1.0, pv * float(3 - rank))
        if adj > run_max:
            run_max = adj
        out[idx] = run_max
    return out


# ---------------------------------------------------------------------------
# Module C: On-Disk Hardware Determinism & Phase 1 / Phase 2 Result Audits
# ---------------------------------------------------------------------------


def verify_determinism_receipt(path: Path) -> str:
    zb = load_strict_json(path)
    require_ok(zb.get("schema") == SCHEMA_DET_RECEIPT, "DET_SCHEMA_BAD", "Unexpected determinism receipt schema")
    require_ok(zb.get("energy_power_status") == ENERGY_POLICY_EXPECTED, "DET_ENERGY_STATUS", "Invalid energy policy status")
    claimed_sha = _strict_hex64(zb.get("receipt_sha256"), "DET_SHA_BAD", "receipt_sha256")
    body = {k: v for k, v in zb.items() if k != "receipt_sha256"}
    recomputed = sha256_hex(canonical_json_bytes(body))
    require_ok(_digest_eq(claimed_sha, recomputed), "DET_SHA_MISMATCH", "Determinism receipt SHA mismatch")
    require_ok(zb.get("clean_hardware_run") is True, "DET_NOT_CLEAN", "clean_hardware_run must be True")
    anomalies = zb.get("anomalies")
    require_ok(type(anomalies) is list and len(anomalies) == 0, "DET_ANOMALIES", "anomalies must be empty")
    exe = zb.get("execution")
    require_ok(
        type(exe) is dict and _strict_int(exe.get("exit_code"), "DET_EXIT", "exit_code") == 0,
        "DET_EXIT_NONZERO",
        "exit_code must be 0",
    )
    require_ok(zb.get("determinism_zone") == "B", "DET_ZONE_BAD", "determinism_zone must be 'B'")
    return claimed_sha


def _unique_prereg_match(pattern: str, text: str, field: str) -> str:
    """Require at least one regex match and uniqueness across all captured values."""
    matches = re.findall(pattern, text)
    require_ok(len(matches) > 0, "PREREG_PARSE_FAIL", f"Missing {field} in preregistration")
    uniq = set(matches)
    require_ok(len(uniq) == 1, "PREREG_PARSE_AMBIGUOUS", f"Conflicting {field} values in preregistration")
    return matches[0]


def _parse_prereg_float(raw: str, field: str) -> float:
    try:
        val = float(raw)
    except ValueError as exc:
        raise StudyVerifyError("PREREG_FLOAT_BAD", f"Invalid float for {field}: {raw!r}") from exc
    require_ok(math.isfinite(val), "PREREG_NONFINITE", f"Non-finite {field}: {raw!r}")
    return val


def parse_prereg_thresholds(prereg_text: str) -> Dict[str, Any]:
    """Parse locked decision gate thresholds uniquely from hashed preregistration Markdown."""
    kl_str = _unique_prereg_match(r"mean_kl_A\s*/\s*mean_kl_D\s*>=\s*([0-9.]+)x", prereg_text, "kl_ratio_min")
    margin_str = _unique_prereg_match(r"mean_holdout_D\s*>=\s*mean_holdout_A\s*-\s*([0-9.]+)\s*pp", prereg_text, "hold_margin_pp")
    alpha_str = _unique_prereg_match(r"p_Holm\(G1_logKL_A_minus_D\)\s*<\s*([0-9.]+)", prereg_text, "p_holm_alpha")
    kl_ceil_str = _unique_prereg_match(r"(?:prose_KL|max_arm_d_KL|KL)\s*<=\s*([0-9.]+)\s*nats", prereg_text, "kl_ceil_nats")
    comm_str = _unique_prereg_match(r"min_commits_D\s*>=\s*(\d{1,6})/6", prereg_text, "min_commits")
    gain_str = _unique_prereg_match(r"mean_holdout_gain_vs_base_pp\s*>=\s*\+([0-9.]+)\s*pp", prereg_text, "min_gain_pp")
    shell_str = _unique_prereg_match(r"max_cayley_shell_norm_err\s*<\s*([0-9eE.+-]+)", prereg_text, "shell_err_max")
    poison_matches = re.findall(r"`(\d{1,6})/(\d{1,6})`\s*\(`100\.0%`\)\s*live poison attacks blocked", prereg_text)
    require_ok(len(poison_matches) == 1, "PREREG_PARSE_FAIL", "Expected single poison count in preregistration")
    p_a = int(poison_matches[0][0])
    p_b = int(poison_matches[0][1])
    require_ok(p_a == p_b and p_a > 0, "PREREG_POISON_BAD", "Invalid poison count in preregistration")

    kl_ratio_min = _parse_prereg_float(kl_str, "kl_ratio_min")
    hold_margin_pp = _parse_prereg_float(margin_str, "hold_margin_pp")
    p_holm_alpha = _parse_prereg_float(alpha_str, "p_holm_alpha")
    kl_ceil_nats = _parse_prereg_float(kl_ceil_str, "kl_ceil_nats")
    min_commits = int(comm_str)
    min_gain_pp = _parse_prereg_float(gain_str, "min_gain_pp")
    shell_err_max = _parse_prereg_float(shell_str, "shell_err_max")

    require_ok(kl_ratio_min > 1.0, "PREREG_RANGE_BAD", "kl_ratio_min must be > 1.0")
    require_ok(0.0 <= hold_margin_pp <= 100.0, "PREREG_RANGE_BAD", "hold_margin_pp must be in [0, 100]")
    require_ok(0.0 < p_holm_alpha <= 1.0, "PREREG_RANGE_BAD", "p_holm_alpha must be in (0, 1]")
    require_ok(kl_ceil_nats > 0.0, "PREREG_RANGE_BAD", "kl_ceil_nats must be > 0")
    require_ok(1 <= min_commits <= 6, "PREREG_RANGE_BAD", "min_commits must be in [1, 6]")
    require_ok(0.0 < min_gain_pp <= 100.0, "PREREG_RANGE_BAD", "min_gain_pp must be in (0, 100]")
    require_ok(0.0 < shell_err_max < 1.0, "PREREG_RANGE_BAD", "shell_err_max must be in (0, 1)")

    return {
        "kl_ratio_min": kl_ratio_min,
        "hold_margin_pp": hold_margin_pp,
        "p_holm_alpha": p_holm_alpha,
        "kl_ceil_nats": kl_ceil_nats,
        "min_commits": min_commits,
        "min_gain_pp": min_gain_pp,
        "shell_err_max": shell_err_max,
        "exp_poison": p_a,
    }


def _verify_phase_results(
    study_dir: Path,
    *,
    phase: int,
    results_file: str,
    det_file: str,
    prereg_file: str,
    phase1_hold_margin_pp: Optional[float] = None,
    phase1_seed_ids: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    res_path = study_dir / results_file
    det_path = study_dir / det_file
    prereg_path = study_dir / prereg_file

    det_sha = verify_determinism_receipt(det_path)
    prereg_sha = file_sha256(prereg_path)
    thr = parse_prereg_thresholds(_read_utf8_nofollow(prereg_path, missing_code="FILE_MISSING"))
    res = load_strict_json(res_path)

    exp_schema = SCHEMA_PHASE1 if phase == 1 else SCHEMA_PHASE2
    require_ok(res.get("schema") == exp_schema, "RES_SCHEMA_BAD", f"Unexpected schema for phase {phase}")
    require_ok(res.get("energy_power_status") == ENERGY_POLICY_EXPECTED, "RES_ENERGY_STATUS", "Invalid energy status")
    require_ok(res.get("determinism_receipt_file") == det_file, "BOUND_DET_FILE_MISMATCH", "determinism_receipt_file mismatch")
    require_ok(res.get("preregistration_file") == prereg_file, "BOUND_PREREG_FILE_MISMATCH", "preregistration_file mismatch")

    claimed_res_sha = _strict_hex64(res.get("result_sha256"), "RES_SHA_BAD", "result_sha256")
    res_body = {k: v for k, v in res.items() if k != "result_sha256"}
    require_ok(
        _digest_eq(claimed_res_sha, sha256_hex(canonical_json_bytes(res_body))),
        "RES_SHA_MISMATCH",
        "result_sha256 mismatch",
    )

    bound_det_sha = _strict_hex64(res.get("determinism_receipt_sha256"), "BOUND_DET_BAD", "determinism_receipt_sha256")
    require_ok(_digest_eq(bound_det_sha, det_sha), "BOUND_DET_MISMATCH", "Determinism receipt SHA mismatch")
    bound_prereg_sha = _strict_hex64(res.get("preregistration_sha256"), "BOUND_PREREG_BAD", "preregistration_sha256")
    require_ok(_digest_eq(bound_prereg_sha, prereg_sha), "BOUND_PREREG_MISMATCH", "Preregistration SHA mismatch")

    ed = res.get("frozen_specialist_editor")
    require_ok(
        type(ed) is dict
        and ed.get("editor_sha256_invariant") is True
        and _digest_eq(
            _strict_hex64(ed.get("editor_sha256_init"), "ED_SHA", "init"),
            _strict_hex64(ed.get("editor_sha256_final"), "ED_SHA", "final"),
        ),
        "EDITOR_INVARIANT_FAIL",
        "Frozen editor invariance failed",
    )
    budget = res.get("matched_param_budget")
    require_ok(
        type(budget) is dict
        and budget.get("parity_pass") is True
        and _strict_float(budget.get("max_param_delta_pct"), "BUDGET_DELTA", "max_param_delta_pct") == 0.0,
        "BUDGET_FAIL",
        "Matched parameter budget parity failed",
    )

    n_seeds = 3 if phase == 1 else 5
    per_seed = res.get("per_seed")
    require_ok(type(per_seed) is list and len(per_seed) == n_seeds, "SEEDS_LEN", f"Expected {n_seeds} seeds")

    arm_d_name = (
        "Arm_D_Cayley_FlowNull_Spinor16B"
        if phase == 1
        else "Arm_D_Cayley_FlowNull_Retract_Spinor16B"
    )
    seed_ids: List[int] = []
    kl_a: List[float] = []
    kl_d: List[float] = []
    hold_a: List[float] = []
    hold_d: List[float] = []
    hold_base: List[float] = []
    commits_d: List[int] = []
    b0_d: List[float] = []
    retraction_rescues = 0
    max_cayley_shell = 0.0
    poison_total = 0
    poison_blocked = 0
    max_rb_drift = 0.0

    for row in per_seed:
        require_ok(type(row) is dict, "SEED_ROW_BAD", "seed row must be dict")
        sid = _strict_int(row.get("seed"), "SEED_ID_BAD", "seed")
        require_ok(sid not in seed_ids, "SEED_ID_DUP", f"Duplicate seed id {sid}")
        seed_ids.append(sid)
        arms = row.get("arms")
        require_ok(type(arms) is dict, "ARMS_BAD", "arms must be dict")
        arm_a = arms.get("Arm_A_Naive_Additive_DeltaW")
        arm_c = arms.get("Arm_C_Cayley_Tangent_Unprojected")
        arm_d = arms.get(arm_d_name)
        require_ok(
            type(arm_a) is dict and type(arm_c) is dict and type(arm_d) is dict,
            "ARMS_MISSING",
            "Missing required arm records",
        )
        verify_pi16_hex(arm_d.get("final_pi16_hex"))
        kl_a.append(_strict_float(arm_a.get("final_prose_kl_nats"), "KL_A", "kl_a"))
        kl_d.append(_strict_float(arm_d.get("final_prose_kl_nats"), "KL_D", "kl_d"))
        hold_a.append(_strict_float(arm_a.get("holdout_mean_pct"), "HOLD_A", "hold_a"))
        hold_d.append(_strict_float(arm_d.get("holdout_mean_pct"), "HOLD_D", "hold_d"))
        hold_base.append(_strict_float(row.get("base_holdout_mean_pct"), "HOLD_BASE", "hold_base"))
        commits_d.append(_strict_int(arm_d.get("commits"), "COMMITS_D", "commits_d"))
        b0_d.append(_strict_float(arm_d.get("final_b0_retention_pct"), "B0_D", "b0_d"))
        if phase == 2:
            retraction_rescues += _strict_int(arm_d.get("retraction_rescues"), "RET_RESC", "retraction_rescues")
        max_cayley_shell = max(
            max_cayley_shell,
            _strict_float(arm_c.get("max_shell_norm_err"), "SHELL_C", "shell_c"),
            _strict_float(arm_d.get("max_shell_norm_err"), "SHELL_D", "shell_d"),
        )
        pa = arm_d.get("poison_rollback_audit")
        require_ok(type(pa) is dict, "POISON_MISSING", "Missing poison_rollback_audit")
        poison_total += _strict_int(pa.get("attacks_total"), "POISON_TOT", "attacks_total")
        poison_blocked += _strict_int(pa.get("attacks_blocked"), "POISON_BLK", "attacks_blocked")
        require_ok(pa.get("all_weights_sha_exact") is True, "POISON_SHA", "Rollback weight SHA must be exact")
        for dk in ("max_param_rollback_drift", "max_logit_rollback_drift", "max_spinor_rollback_drift"):
            max_rb_drift = max(max_rb_drift, _strict_float(pa.get(dk), "RB_DRIFT", dk))
        for vk in (
            "max_valid_rollback_param_drift",
            "max_valid_rollback_logit_drift",
            "max_valid_rollback_spinor_drift",
        ):
            max_rb_drift = max(max_rb_drift, _strict_float(arm_d.get(vk), "RB_VDRIFT", vk))

    t_fn = paired_t_df2 if phase == 1 else paired_t_df4
    t_logkl = t_fn([math.log(max(1e-12, v)) for v in kl_a], [math.log(max(1e-12, v)) for v in kl_d])
    t_hold_base = t_fn(hold_d, hold_base)
    t_hold_a = t_fn(hold_d, hold_a)
    p_holm_logkl, p_holm_base, p_holm_a = holm_3([t_logkl["p_raw"], t_hold_base["p_raw"], t_hold_a["p_raw"]])

    mean_kl_a = sum(kl_a) / float(n_seeds)
    mean_kl_d = sum(kl_d) / float(n_seeds)
    kl_ratio = mean_kl_a / max(1e-12, mean_kl_d)
    mean_hold_a = sum(hold_a) / float(n_seeds)
    mean_hold_d = sum(hold_d) / float(n_seeds)
    mean_gain_base = (sum(hold_d) - sum(hold_base)) / float(n_seeds)

    recomp_g1 = (
        (kl_ratio >= thr["kl_ratio_min"])
        and (mean_hold_d >= mean_hold_a - thr["hold_margin_pp"])
        and (p_holm_logkl < thr["p_holm_alpha"])
        and (max(kl_d) <= thr["kl_ceil_nats"])
    )
    recomp_g2 = (
        (min(commits_d) >= thr["min_commits"])
        and (mean_gain_base >= thr["min_gain_pp"])
        and (p_holm_base < thr["p_holm_alpha"])
        and (min(b0_d) == 100.0)
    )
    recomp_g3 = (
        (max_cayley_shell < thr["shell_err_max"])
        and (poison_blocked == poison_total)
        and (poison_total == thr["exp_poison"])
        and (max_rb_drift == 0.0)
    )
    if recomp_g1 and recomp_g2 and recomp_g3:
        recomp_verdict = "CONFIRMED"
    elif recomp_g3 and (recomp_g1 or recomp_g2):
        recomp_verdict = "PARTIAL"
    else:
        recomp_verdict = "FALSIFIED"

    gates = res.get("gates")
    require_ok(type(gates) is dict, "GATES_MISSING", "gates dict missing")
    require_ok(gates.get("G1_prose_kl_cure") is recomp_g1, "G1_MISMATCH", "G1 verdict mismatch")
    require_ok(gates.get("G2_reserve_commits_and_holdout_gain") is recomp_g2, "G2_MISMATCH", "G2 verdict mismatch")
    require_ok(gates.get("G3_shell_norm_and_spinor16b_rollback") is recomp_g3, "G3_MISMATCH", "G3 verdict mismatch")
    require_ok(gates.get("verdict") == recomp_verdict, "VERDICT_MISMATCH", "Overall verdict mismatch")

    stats_key = "stats_paired_t_df2" if phase == 1 else "stats_paired_t_df4"
    stats = res.get(stats_key)
    require_ok(type(stats) is dict, "STATS_MISSING", f"{stats_key} missing")
    for skey, exp_ph, code in (
        ("G1_logKL_A_minus_D", p_holm_logkl, "PHOLM_G1_MISMATCH"),
        ("G2_holdout_D_minus_Base", p_holm_base, "PHOLM_G2_MISMATCH"),
        ("G2_holdout_D_minus_A", p_holm_a, "PHOLM_G2A_MISMATCH"),
    ):
        entry = stats.get(skey)
        require_ok(type(entry) is dict, "STATS_ENTRY_BAD", f"Missing/invalid stat entry {skey}")
        got_ph = _strict_float(entry.get("p_holm"), "PH_VAL", f"{skey}.p_holm")
        require_ok(abs(got_ph - exp_ph) <= STAT_TOL, code, f"{skey} p_holm mismatch")

    out: Dict[str, Any] = {
        "verdict": recomp_verdict,
        "seed_ids": seed_ids,
        "G1_prose_kl_cure": recomp_g1,
        "G2_reserve_commits_and_holdout_gain": recomp_g2,
        "G3_shell_norm_and_spinor16b_rollback": recomp_g3,
        "parsed_prereg_thresholds": thr,
        "kl_ratio_a_over_d": round(kl_ratio, 4),
        "max_arm_d_kl_nats": round(max(kl_d), 6),
        "mean_holdout_a_pct": round(mean_hold_a, 4),
        "mean_holdout_d_pct": round(mean_hold_d, 4),
        "mean_holdout_gain_vs_base_pp": round(mean_gain_base, 4),
        "p_holm_g1": round(p_holm_logkl, 8),
        "p_holm_g2": round(p_holm_base, 8),
        "max_cayley_shell_norm_err": max_cayley_shell,
        "poison_blocked": poison_blocked,
        "poison_total": poison_total,
        "max_rollback_drift": max_rb_drift,
        "preregistration_file": prereg_file,
        "preregistration_sha256": prereg_sha,
        "determinism_receipt_file": det_file,
        "determinism_receipt_sha256": det_sha,
        "results_file": results_file,
        "result_sha256": claimed_res_sha,
    }
    if phase == 2:
        require_ok(phase1_hold_margin_pp is not None and phase1_seed_ids is not None, "P1_CTX_MISSING", "Phase 1 context required")
        p1_set = set(phase1_seed_ids)
        reused_idx = [i for i, sid in enumerate(seed_ids) if sid in p1_set]
        fresh_idx = [i for i, sid in enumerate(seed_ids) if sid not in p1_set]
        require_ok(len(fresh_idx) > 0, "NO_FRESH_SEEDS", "Phase 2 must include unseen fresh seeds")
        out["retraction_rescues_total"] = retraction_rescues
        out["passes_stricter_phase1_g1_margin"] = (
            (kl_ratio >= thr["kl_ratio_min"])
            and (mean_hold_d >= mean_hold_a - phase1_hold_margin_pp)
            and (p_holm_logkl < thr["p_holm_alpha"])
            and (max(kl_d) <= thr["kl_ceil_nats"])
        )
        nf = float(len(fresh_idx))
        fresh_ha = sum(hold_a[i] for i in fresh_idx) / nf
        fresh_hd = sum(hold_d[i] for i in fresh_idx) / nf
        fresh_hb = sum(hold_base[i] for i in fresh_idx) / nf
        fresh_ka = sum(kl_a[i] for i in fresh_idx) / nf
        fresh_kd = sum(kl_d[i] for i in fresh_idx) / nf
        out["unseen_fresh_seeds_summary"] = {
            "reused_seed_ids": [seed_ids[i] for i in reused_idx],
            "fresh_seed_ids": [seed_ids[i] for i in fresh_idx],
            "mean_holdout_base_pct": round(fresh_hb, 4),
            "mean_holdout_a_pct": round(fresh_ha, 4),
            "mean_holdout_d_pct": round(fresh_hd, 4),
            "mean_holdout_d_minus_a_pp": round(fresh_hd - fresh_ha, 4),
            "mean_holdout_d_minus_base_pp": round(fresh_hd - fresh_hb, 4),
            "kl_ratio_a_over_d": round(fresh_ka / max(1e-12, fresh_kd), 4),
        }
    return out


def build_study_certificate(study_dir: Path) -> Dict[str, Any]:
    """Run exact-Q oracle + AST purity + Phase 1 & Phase 2 on-disk verification and sign certificate."""
    require_ok(isinstance(study_dir, Path) and study_dir.is_dir(), "BAD_STUDY_DIR", "Invalid or missing study_dir")
    ast_purity = verify_oracle_ast_purity(_read_utf8_nofollow(Path(__file__), missing_code="FILE_MISSING"))
    oracle = certify_exact_so_d_cayley_oracle()
    p1 = _verify_phase_results(
        study_dir,
        phase=1,
        results_file="phase1_binary_gate_results.json",
        det_file="phase1_hardware_determinism.json",
        prereg_file="preregistration_phase1_binary_gate.md",
    )
    p2 = _verify_phase_results(
        study_dir,
        phase=2,
        results_file="phase2_geodesic_retraction_results.json",
        det_file="phase2_hardware_determinism.json",
        prereg_file="preregistration_phase2_geodesic_retraction.md",
        phase1_hold_margin_pp=p1["parsed_prereg_thresholds"]["hold_margin_pp"],
        phase1_seed_ids=p1["seed_ids"],
    )
    require_ok(p1["verdict"] == "FALSIFIED", "P1_VERDICT_UNEXPECTED", "Phase 1 must remain honest FALSIFIED")
    require_ok(p2["verdict"] == "CONFIRMED", "P2_VERDICT_UNEXPECTED", "Phase 2 must be CONFIRMED")

    pinned_files = sorted({
        p1["preregistration_file"],
        p1["determinism_receipt_file"],
        p1["results_file"],
        p2["preregistration_file"],
        p2["determinism_receipt_file"],
        p2["results_file"],
    })
    artifact_sha256s = {fn: file_sha256(study_dir / fn) for fn in pinned_files}

    payload: Dict[str, Any] = {
        "schema": SCHEMA_CERT,
        "status": "PASS",
        "energy_power_status": ENERGY_POLICY_EXPECTED,
        "oracle_ast_purity": ast_purity,
        "exact_q_cayley_oracle": oracle,
        "phase1_binary_gate_prerequisite": p1,
        "phase2_geodesic_retraction": p2,
        "bound_artifacts_sha256": artifact_sha256s,
    }
    payload_sha = sha256_hex(canonical_json_bytes(payload))
    cert = dict(payload)
    cert["payload_sha256"] = payload_sha
    cert["certificate_sha256"] = sha256_hex(canonical_json_bytes(cert))
    return cert


def verify_certificate_file(
    cert_path: Path,
    study_dir: Path,
    *,
    require_pinned: bool = False,
) -> Dict[str, Any]:
    """Fail-closed verify a committed certificate JSON against live on-disk recomputation."""
    got = load_strict_json(cert_path)
    require_ok(got.get("schema") == SCHEMA_CERT, "CERT_SCHEMA_BAD", "Unexpected certificate schema")
    claimed_p = _strict_hex64(got.get("payload_sha256"), "CERT_PSHA_BAD", "payload_sha256")
    claimed_c = _strict_hex64(got.get("certificate_sha256"), "CERT_CSHA_BAD", "certificate_sha256")
    body_p = {k: v for k, v in got.items() if k not in ("payload_sha256", "certificate_sha256")}
    require_ok(_digest_eq(claimed_p, sha256_hex(canonical_json_bytes(body_p))), "CERT_PSHA_MISMATCH", "payload_sha256 mismatch")
    body_c = dict(body_p)
    body_c["payload_sha256"] = claimed_p
    require_ok(_digest_eq(claimed_c, sha256_hex(canonical_json_bytes(body_c))), "CERT_CSHA_MISMATCH", "certificate_sha256 mismatch")

    expected = build_study_certificate(study_dir)
    require_ok(
        _digest_eq(claimed_c, expected["certificate_sha256"]),
        "CERT_LIVE_MISMATCH",
        "On-disk certificate does not match live recomputation",
    )
    if require_pinned:
        require_ok(
            _digest_eq(claimed_c, PINNED_CERTIFICATE_SHA256),
            "CERT_PIN_MISMATCH",
            "Verified certificate does not match PINNED_CERTIFICATE_SHA256",
        )
    return expected


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pure-stdlib fail-closed verifier for SO(d) Cayley geodesic retraction study"
    )
    parser.add_argument(
        "--study-dir",
        type=Path,
        default=Path(__file__).absolute().parent,
        help="Path to studies/so_d_geodesic_retraction directory",
    )
    parser.add_argument(
        "--require-pinned",
        action="store_true",
        help="Require verified or emitted certificate SHA-256 to match PINNED_CERTIFICATE_SHA256",
    )
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--json", action="store_true", help="Emit live verified certificate JSON (default)")
    group.add_argument("--write", type=Path, help="Write canonical verified certificate JSON to path")
    group.add_argument("--check", type=Path, help="Fail-closed verify committed certificate JSON against disk")
    args = parser.parse_args(argv)
    try:
        if args.check is not None:
            cert = verify_certificate_file(args.check, args.study_dir, require_pinned=args.require_pinned)
            out = {
                "status": "PASS",
                "phase1_verdict": cert["phase1_binary_gate_prerequisite"]["verdict"],
                "phase2_verdict": cert["phase2_geodesic_retraction"]["verdict"],
                "certificate_sha256": cert["certificate_sha256"],
            }
            sys.stdout.write(json.dumps(out, sort_keys=True, indent=2, allow_nan=False) + "\n")
            return 0
        cert = build_study_certificate(args.study_dir)
        if args.require_pinned:
            require_ok(
                _digest_eq(cert["certificate_sha256"], PINNED_CERTIFICATE_SHA256),
                "CERT_PIN_MISMATCH",
                "Live certificate does not match PINNED_CERTIFICATE_SHA256",
            )
        text = json.dumps(cert, sort_keys=True, indent=2, allow_nan=False, ensure_ascii=True) + "\n"
        if args.write is not None:
            _write_utf8_nofollow(args.write, text)
            sys.stdout.write(
                json.dumps({"status": "WRITTEN", "certificate_sha256": cert["certificate_sha256"]}, sort_keys=True) + "\n"
            )
            return 0
        sys.stdout.write(text)
        return 0
    except StudyVerifyError as exc:
        sys.stderr.write(json.dumps({"status": "ERROR", "code": exc.code, "message": exc.message}, sort_keys=True) + "\n")
        return 2
    except (OSError, RecursionError, UnicodeDecodeError):
        sys.stderr.write(json.dumps({"status": "ERROR", "code": "IO_ERROR", "message": "I/O or runtime limit error"}, sort_keys=True) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
