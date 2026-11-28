"""
`aletheia.lean_audit_hardening`: EXP-Q46b Lean 4 Trust-Boundary Hardening Suite.

Closes the concrete real-world bypasses surfaced in `arXiv:2611.32334v2`
(`scripts/check_clean.py`) and `solved-conjectures#902` (`TargetAudit.lean` +
`audit_lean_all_owned.py`), covering:
  1. `sorryAx` (source & `#print axioms` / `collectAxioms` log detection)
  2. `Lean.ofReduceBool` / `ofReduceBool` (+ `ofReduceNat`)
  3. `Lean.trustCompiler` / `trustCompiler`
  4. `partial` declarations (including `private partial def` and
     theorem-carrying files with `partial def`/`instance`/`abbrev`)
  5. `enable_nanoda: false` (and omitted/non-bool `enable_nanoda` in comparator configs)
  6. Nonexistent or empty Lean directories failing closed (never returning RC=0)
  7. `lakefile.lean` / `lakefile.toml` never omitted (catching hidden `import Lake`,
     `sorry`, `#eval`, metaprogramming, and unmanifested `require` packages)
  8. String-literal & char-literal escapes (`"/-"`, `"--"`, `'"'`) never corrupting
     nested comment state to hide subsequent `sorry` / `axiom` / kernel escapes
  9. `TargetAudit` private-declaration `constNames` completeness & `loadExts := false`
     elaborator-spoofing isolation checks.

Stdlib-only, zero floats, zero bare asserts, safe under all R4 isolated modes
(`-I -B`, `-I -O -B`, `-I -B -W error`).
"""
from __future__ import annotations

import argparse
from collections import deque
import errno
import json
import os
from pathlib import Path
import re
import stat
import sys
import tomllib
from typing import Any, Sequence

from aletheia import _strict_zone_b as _zb

__all__ = [
    "MAX_FILE_BYTES",
    "STANDARD_LEAN4_AXIOMS",
    "LeanAuditHardeningError",
    "strip_lean4_comments_and_literals",
    "audit_lean4_source_hardened",
    "audit_lean4_project_hardened",
    "validate_comparator_config_hardened",
    "audit_target_audit_log",
    "audit_target_audit_source",
    "run_exp_q46b_bypass_suite",
    "main",
]

MAX_FILE_BYTES = _zb.MAX_FILE_BYTES
MAX_JSON_DEPTH = _zb.MAX_JSON_DEPTH
MAX_JSON_INT_DIGITS = _zb.MAX_JSON_INT_DIGITS

STANDARD_LEAN4_AXIOMS: frozenset[str] = frozenset({"propext", "Classical.choice", "Quot.sound"})
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_SKIP_DIRS = frozenset({".git", ".lake", ".venv", "venv", "node_modules", "__pycache__"})
_MOD_NAME_RE = re.compile(r"\A[A-Za-z0-9_'\u0080-\uffff]+(?:\.[A-Za-z0-9_'\u0080-\uffff]+)*\Z")
_INTERP_PLAIN_PREFIXES: tuple[str, ...] = (
    "dbg_trace",
    "throwError",
)
_INTERP_ARG_MACROS: tuple[tuple[str, int, bool], ...] = (
    ("Macro.trace[", 1, True),
    ("trace_goal[", 1, True),
    ("trace[", 1, True),
    ("throwNamedErrorAt", 2, False),
    ("logNamedErrorAt", 2, False),
    ("logNamedWarningAt", 2, False),
    ("throwErrorAt", 1, False),
    ("throwNamedError", 1, False),
    ("logNamedError", 1, False),
    ("logNamedWarning", 1, False),
)

_SOURCE_ESCAPE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?<![A-Za-z0-9_'.])sorry(?![A-Za-z0-9_'])"), "LEAN4_SORRY"),
    (re.compile(r"(?<![A-Za-z0-9_'.])admit(?![A-Za-z0-9_'])"), "LEAN4_ADMIT"),
    (re.compile(r"(?<![A-Za-z0-9_'.])axiom(?![A-Za-z0-9_'])"), "LEAN4_AXIOM"),
    (re.compile(r"(?<![A-Za-z0-9_'.])unsafe(?![A-Za-z0-9_'])"), "LEAN4_UNSAFE"),
    (re.compile(r"(?<![A-Za-z0-9_'.])native_decide(?![A-Za-z0-9_'])"), "LEAN4_NATIVE_DECIDE"),
    (re.compile(r"(?:(?<![A-Za-z0-9_'.])decide(?:\s|\([^)]*\)|\+[A-Za-z_][A-Za-z0-9_]*)*\+native(?![A-Za-z0-9_'])|(?<![A-Za-z0-9_'.])decide\s*\([^)]*\bnative\s*:=\s*true\b[^)]*\)|(?:^|[\s;(])\+native(?![A-Za-z0-9_']))", re.DOTALL), "LEAN4_DECIDE_NATIVE"),
    (re.compile(r"(?<![A-Za-z0-9_'.])(?:bv_decide|bv_check)(?![A-Za-z0-9_'])"), "LEAN4_BV_DECIDE"),
    (re.compile(r"(?<![A-Za-z0-9_'])sorryAx(?![A-Za-z0-9_'])"), "LEAN4_SORRY_AX"),
    (re.compile(r"(?<![A-Za-z0-9_'])(?:Lean\s*\.\s*Meta\s*\.\s*)?mkSorry(?![A-Za-z0-9_'])", re.DOTALL), "LEAN4_MK_SORRY"),
    (re.compile(r"(?<![A-Za-z0-9_'])(?:Lean\s*\.\s*)?ofReduceBool(?![A-Za-z0-9_'])", re.DOTALL), "LEAN4_OF_REDUCE_BOOL"),
    (re.compile(r"(?<![A-Za-z0-9_'])(?:Lean\s*\.\s*)?ofReduceNat(?![A-Za-z0-9_'])", re.DOTALL), "LEAN4_OF_REDUCE_NAT"),
    (re.compile(r"(?<![A-Za-z0-9_'])(?:Lean\s*\.\s*)?trustCompiler(?![A-Za-z0-9_'])", re.DOTALL), "LEAN4_TRUST_COMPILER"),
    (re.compile(r"(?<![A-Za-z0-9_'])debug\s*\.\s*(?:skipKernelTC|byAsSorry|proofAsSorry|terminalTacticsAsSorry)(?![A-Za-z0-9_'])", re.DOTALL), "LEAN4_SKIP_KERNEL_TC"),
    (re.compile(r"(?<![A-Za-z0-9_'.])(?:run_cmd|run_meta|run_tac|initialize|builtin_initialize)(?![A-Za-z0-9_'])"), "LEAN4_META_EVAL_ESCAPE"),
    (re.compile(r"(?<![A-Za-z0-9_'.])(?:syntax|macro|macro_rules|elab|elab_rules|declare_syntax_cat|infix[lr]?|prefix|postfix|notation)(?![A-Za-z0-9_'])"), "LEAN4_SYNTAX_MACRO_ESCAPE"),
    (re.compile(r"#\s*(?:eval!?|reduce|exit|guard_msgs)(?![A-Za-z0-9_'])"), "LEAN4_HASH_SPOOF"),
    (re.compile(r"(?:@|(?<![A-Za-z0-9_'.])attribute\s*)\[[^\]]*(?<![A-Za-z0-9_'])(?:extern|implemented_by|export|init|builtin_init|macro|elab|tactic)(?![A-Za-z0-9_'])", re.DOTALL), "LEAN4_ATTR_ESCAPE"),
    (re.compile(r"(?:\.\s*)?_native\s*\.\s*[A-Za-z_][A-Za-z0-9_]*\s*\.\s*ax_[A-Za-z0-9_]*", re.DOTALL), "LEAN4_NATIVE_AXIOM"),
)
_TARGET_AUDIT_KERNEL_RULES_END = 13
_ROOT_NS_PREFIX_RE = re.compile(r"(?<![A-Za-z0-9_'.])(?:_root_\s*\.\s*)+")
_TOP_DECL_CMD_RE = re.compile(
    r"^\s*(?:(?:private|protected|noncomputable|unsafe|partial|scoped|local)\s+)*"
    r"(?:theorem|lemma|def|abbrev|opaque|axiom|example|instance|structure|inductive|class|namespace|section|end|open|variable|universe|attribute|#)"
    r"(?![A-Za-z0-9_'])"
)
_STOP_LINE_START_RE = re.compile(r"^\s*stop(?![A-Za-z0-9_'])")
_STOP_AFTER_TACTIC_TOK_RE = re.compile(
    r"(?:(?<![A-Za-z0-9_'.])(?:by|all_goals|any_goals|repeat|try|focus|first)|=>|<;>|[;|({·])\s*stop(?![A-Za-z0-9_'])"
)

_PARTIAL_DECL_RE = re.compile(
    r"(?<![A-Za-z0-9_'.])partial\s+(?:(?:private|protected|noncomputable|unsafe)\s+)*(?:def|instance|abbrev|theorem|lemma|opaque)\b",
    flags=re.DOTALL,
)
_THEOREM_DECL_RE = re.compile(r"(?<![A-Za-z0-9_'.])(?:theorem|lemma)\s+[A-Za-z_][A-Za-z0-9_.']*")
_IMPORT_RE = re.compile(
    r"(?<![A-Za-z0-9_'.])((?:(?:public|private|meta)\s+)*)import\s+(?:all\s+)?([A-Za-z0-9_«»'\u0080-\uffff]+(?:\.[A-Za-z0-9_«»'\u0080-\uffff]+)*)"
)
_AXIOM_LOG_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsorryAx\b"), "LEAN4_SORRY_AX"),
    (re.compile(r"\bLean\.ofReduceBool\b|\bofReduceBool\b"), "LEAN4_OF_REDUCE_BOOL"),
    (re.compile(r"\bLean\.ofReduceNat\b|\bofReduceNat\b"), "LEAN4_OF_REDUCE_NAT"),
    (re.compile(r"\bLean\.trustCompiler\b|\btrustCompiler\b"), "LEAN4_TRUST_COMPILER"),
    (re.compile(r"(?:\._native\.|_native\.)[A-Za-z_][A-Za-z0-9_]*\.ax_[A-Za-z0-9_]*"), "LEAN4_NATIVE_AXIOM"),
)


class LeanAuditHardeningError(ValueError):
    """Fail-closed error for EXP-Q46b Lean 4 trust-boundary hardening checks."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _require(cond: bool, code: str, message: str) -> None:
    if not cond:
        raise LeanAuditHardeningError(code, message)


def _loads_strict_json(raw_bytes: bytes, label: str, *, allow_float: bool = False) -> Any:
    return _zb.parse_strict_json_bytes(
        raw_bytes,
        label,
        err_cls=LeanAuditHardeningError,
        max_depth=MAX_JSON_DEPTH,
        max_int_digits=MAX_JSON_INT_DIGITS,
        allow_float=allow_float,
    )


def _read_regular_bytes(path: Any, label: str) -> bytes:
    return _zb.open_regular_file(
        path,
        label,
        err_cls=LeanAuditHardeningError,
        max_bytes=MAX_FILE_BYTES,
    )


def _match_char_literal_end(source: str, i: int, n: int) -> int | None:
    if i + 2 < n and source[i + 1] not in ("\\", "'") and source[i + 2] == "'":
        return i + 3
    if i + 3 < n and source[i + 1] == "\\":
        if source[i + 3] == "'" and source[i + 2] != "\n":
            return i + 4
        esc = source[i + 2]
        if esc == "x" and i + 5 < n and source[i + 5] == "'" and all(c in _HEX_DIGITS for c in source[i + 3 : i + 5]):
            return i + 6
        if esc == "u" and i + 7 < n and source[i + 7] == "'" and all(c in _HEX_DIGITS for c in source[i + 3 : i + 7]):
            return i + 8
    return None


def _is_ident_start(ch: str) -> bool:
    return ch.isalpha() or ch == "_"


def _is_ident_cont(ch: str) -> bool:
    return ch.isalnum() or ch in "_'!?"


def _skip_ws_and_comments(source: str, j: int, n: int) -> int:
    while j < n:
        if source[j].isspace():
            j += 1
        elif source.startswith("--", j):
            while j < n and source[j] != "\n":
                j += 1
        elif source.startswith("/-", j):
            cdepth = 1
            j += 3 if (j + 2 < n and source[j + 2] in ("-", "!")) else 2
            while j < n and cdepth > 0:
                if source.startswith("/-", j):
                    cdepth += 1
                    j += 2
                elif source.startswith("-/", j):
                    cdepth -= 1
                    j += 2
                else:
                    j += 1
        else:
            break
    return j


def _find_interp_open_quote(source: str, i: int, n: int, in_ident: bool) -> int | None:
    if in_ident or (i > 0 and source[i - 1] == "."):
        return None
    if _is_ident_start(source[i]):
        k = i + 1
        while k < n and _is_ident_cont(source[k]):
            k += 1
        if source[k - 1] == "!":
            j = _skip_ws_and_comments(source, k, n)
            if j < n and source[j] == '"':
                return j
    for pref in _INTERP_PLAIN_PREFIXES:
        if source.startswith(pref, i):
            k = i + len(pref)
            if k < n and _is_ident_cont(source[k]):
                continue
            j = _skip_ws_and_comments(source, k, n)
            if j < n and source[j] == '"':
                return j
    return None


def _match_interp_arg_macro(source: str, i: int, n: int, in_ident: bool) -> tuple[int, int, bool] | None:
    if in_ident or (i > 0 and source[i - 1] == "."):
        return None
    for kw, argc, is_bracket in _INTERP_ARG_MACROS:
        if source.startswith(kw, i):
            end = i + len(kw)
            if is_bracket:
                return end, argc, True
            if end == n or not _is_ident_cont(source[end]):
                return end, argc, False
    return None


def _find_stop_tactic_lines(scan_text: str) -> list[int]:
    lines_out: list[int] = []
    in_by = False
    for lineno, line in enumerate(scan_text.split("\n"), start=1):
        if _TOP_DECL_CMD_RE.match(line):
            in_by = False
        if _STOP_AFTER_TACTIC_TOK_RE.search(line) is not None or (
            in_by and _STOP_LINE_START_RE.match(line) is not None
        ):
            lines_out.append(lineno)
        if re.search(r"(?<![A-Za-z0-9_'.])by(?![A-Za-z0-9_'])", line) is not None:
            in_by = True
    return lines_out


def strip_lean4_comments_and_literals(source: Any) -> tuple[str, list[dict[str, Any]]]:
    """
    Literal-safe & nested-comment-safe Lean 4 stripper preserving exact line numbers.

    Closes the `check_clean.py` string-literal escape where `"/-"` or `"--"`
    inside a Lean string literal breaks comment nesting depth and hides later `sorry`.
    """
    _require(type(source) is str, "INVALID_SOURCE_TYPE", "Lean source must be str")
    out: list[str] = []
    lex_findings: list[dict[str, Any]] = []
    i = 0
    n = len(source)
    depth = 0
    in_str = False
    raw_hashes = -1
    opened_at = 0
    in_ident = False
    interp_stack: list[list[int]] = []
    pending_args = 0
    arg_depth = 0
    pending_tok = False
    interp_next_quote = False

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
        if raw_hashes >= 0:
            close_seq = '"' + ("#" * raw_hashes)
            if source.startswith(close_seq, i):
                out.append(" " * len(close_seq))
                i += len(close_seq)
                raw_hashes = -1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if in_str:
            if ch == "\\" and i + 1 < n:
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
        if interp_stack and interp_stack[-1][1] == 0:
            if ch == "\\" and i + 1 < n:
                out.append(" \n" if nxt == "\n" else "  ")
                i += 2
            elif ch == '"':
                interp_stack.pop()
                out.append(" ")
                i += 1
            elif ch == "{":
                interp_stack[-1][1] = 1
                in_ident = False
                out.append(" ")
                i += 1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue

        if ch == "/" and nxt == "-":
            if pending_tok:
                pending_tok = False
                pending_args -= 1
                interp_next_quote = pending_args == 0
            depth = 1
            opened_at = i
            in_ident = False
            if i + 2 < n and source[i + 2] in ("-", "!"):
                out.append("   ")
                i += 3
            else:
                out.append("  ")
                i += 2
            continue
        if ch == "-" and nxt == "-":
            if pending_tok:
                pending_tok = False
                pending_args -= 1
                interp_next_quote = pending_args == 0
            in_ident = False
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch.isspace():
            if pending_tok:
                pending_tok = False
                pending_args -= 1
                interp_next_quote = pending_args == 0
            in_ident = False
            out.append(ch)
            i += 1
            continue
        if interp_next_quote:
            interp_next_quote = False
            if ch == '"':
                interp_stack.append([i, 0])
                in_ident = False
                out.append(" ")
                i += 1
                continue
        if pending_args > 0:
            if ch in "([{":
                if pending_tok:
                    pending_tok = False
                    pending_args -= 1
                arg_depth += 1
            elif ch in ")]}" and arg_depth > 0:
                arg_depth -= 1
                if arg_depth == 0:
                    pending_args -= 1
                    interp_next_quote = pending_args == 0
            elif arg_depth == 0:
                if _is_ident_cont(ch) or ch in ".«":
                    pending_tok = True
                else:
                    pending_args = 0
                    pending_tok = False
        if ch == "r" and not in_ident and (i == 0 or source[i - 1] != "."):
            j = i + 1
            while j < n and source[j] == "#":
                j += 1
            if j < n and source[j] == '"':
                raw_hashes = j - (i + 1)
                opened_at = i
                in_ident = False
                out.append(" " * (j - i + 1))
                i = j + 1
                continue
        macro_arg = _match_interp_arg_macro(source, i, n, in_ident)
        if macro_arg is not None:
            end_kw, argc, is_bracket = macro_arg
            out.append(source[i:end_kw])
            i = end_kw
            in_ident = False
            pending_args = argc
            arg_depth = 1 if is_bracket else 0
            pending_tok = False
            continue
        interp_q = _find_interp_open_quote(source, i, n, in_ident)
        if interp_q is not None:
            interp_stack.append([i, 0])
            in_ident = False
            for k in range(i, interp_q + 1):
                out.append("\n" if source[k] == "\n" else " ")
            i = interp_q + 1
            continue
        if ch == '"':
            in_str = True
            opened_at = i
            in_ident = False
            out.append(" ")
            i += 1
            continue
        if ch == "'" and not in_ident:
            char_end = _match_char_literal_end(source, i, n)
            if char_end is not None:
                in_ident = False
                out.append(" \n " if source[i + 1] == "\n" else " " * (char_end - i))
                i = char_end
                continue
        if ch == "«":
            end_g = source.find("»", i + 1)
            if end_g == -1:
                line = source.count("\n", 0, i) + 1
                lex_findings.append({"line": line, "code": "LEAN4_UNTERMINATED_IDENT", "excerpt": "unterminated guillemet"})
                out.append("\n" * source.count("\n", i))
                break
            if out and _is_ident_cont(out[-1][-1]):
                out.append(" ")
            out.append(source[i + 1 : end_g].replace("\n", " "))
            if end_g + 1 < n and _is_ident_start(source[end_g + 1]):
                out.append(" ")
            in_ident = False
            i = end_g + 1
            continue
        if interp_stack:
            if ch == "{":
                interp_stack[-1][1] += 1
                in_ident = False
                out.append("{")
                i += 1
                continue
            if ch == "}":
                interp_stack[-1][1] -= 1
                in_ident = False
                out.append(" " if interp_stack[-1][1] == 0 else "}")
                i += 1
                continue

        in_ident = _is_ident_cont(ch) if in_ident else _is_ident_start(ch)
        out.append(ch)
        i += 1

    if depth > 0 or in_str or raw_hashes >= 0 or interp_stack:
        err_pos = opened_at if (depth > 0 or in_str or raw_hashes >= 0) else interp_stack[-1][0]
        line = source.count("\n", 0, err_pos) + 1
        code = "LEAN4_UNTERMINATED_COMMENT" if depth > 0 else "LEAN4_UNTERMINATED_STRING"
        lex_findings.append({"line": line, "code": code, "excerpt": code.lower()})

    return "".join(out), lex_findings


def audit_lean4_source_hardened(
    source: Any,
    *,
    allow_non_init_imports: bool = False,
    allow_project_imports: Sequence[str] = (),
) -> dict[str, Any]:
    """Static Lean 4.36.0 source auditor closing string-literal escapes, `partial`, and kernel axioms."""
    cleaned, lex_findings = strip_lean4_comments_and_literals(source)
    scan_text = _ROOT_NS_PREFIX_RE.sub("", cleaned)
    findings: list[dict[str, Any]] = list(lex_findings)
    imports: list[str] = []
    lines = scan_text.split("\n")

    for pat, code in _SOURCE_ESCAPE_RULES:
        for m_esc in pat.finditer(scan_text):
            lineno = scan_text.count("\n", 0, m_esc.start()) + 1
            excerpt = (lines[lineno - 1].strip() if lineno - 1 < len(lines) else m_esc.group(0))[:100]
            findings.append({"line": lineno, "code": code, "excerpt": excerpt})

    for stop_line in _find_stop_tactic_lines(scan_text):
        excerpt = (lines[stop_line - 1].strip() if stop_line - 1 < len(lines) else "stop")[:100]
        findings.append({"line": stop_line, "code": "LEAN4_STOP_TACTIC", "excerpt": excerpt})

    has_theorem = _THEOREM_DECL_RE.search(scan_text) is not None
    p_line, p_pos = 1, 0
    for m_part in _PARTIAL_DECL_RE.finditer(scan_text):
        p_line += scan_text.count("\n", p_pos, m_part.start())
        p_pos = m_part.start()
        code = "LEAN4_PARTIAL_THEOREM_CARRYING" if has_theorem else "LEAN4_PARTIAL"
        findings.append({"line": p_line, "code": code, "excerpt": " ".join(m_part.group(0).split())[:100]})

    imp_line, imp_pos = 1, 0
    for m_imp in _IMPORT_RE.finditer(scan_text):
        imp_line += scan_text.count("\n", imp_pos, m_imp.start(2))
        imp_pos = m_imp.start(2)
        mods_prefix = m_imp.group(1)
        mod = m_imp.group(2).replace("«", "").replace("»", "")
        imports.append(mod)
        if re.search(r"\bpublic\b", mods_prefix) is not None:
            findings.append({"line": imp_line, "code": "LEAN4_PUBLIC_IMPORT", "excerpt": mod})
        root_pkg = mod.split(".", 1)[0]
        allowed_proj = any(mod == p or mod.startswith(p + ".") for p in allow_project_imports)
        if mod in ("Std", "Std.Tactic", "Lean", "Lean.Elab", "Lean.Elab.Tactic") or mod.startswith("Std.Tactic.BVDecide"):
            findings.append({"line": imp_line, "code": "LEAN4_BV_DECIDE_IMPORT", "excerpt": mod})
        elif not allow_non_init_imports and root_pkg not in ("Init", "Std") and not allowed_proj:
            findings.append({"line": imp_line, "code": "LEAN4_NON_INIT_IMPORT", "excerpt": mod})

    return {"clean": len(findings) == 0, "findings": findings, "imports": imports}


def _scan_dir_tree(
    dir_path: Path,
    *,
    skip_dirs: frozenset[str],
    seen_dirs: set[Path],
    lean_files: dict[Path, Path],
    manifest_paths: dict[Path, Path],
    toml_paths: dict[Path, Path],
    root: Path,
) -> None:
    stack = [dir_path]
    while stack:
        cur = stack.pop()
        if cur in seen_dirs:
            continue
        seen_dirs.add(cur)
        try:
            entries = sorted(os.scandir(cur), key=lambda e: e.name)
            for entry in entries:
                ep = Path(entry.path)
                if entry.is_symlink():
                    raise LeanAuditHardeningError("SYMLINK_IN_LEAN_TREE", f"symlink forbidden: {entry.name}")
                if entry.is_dir(follow_symlinks=False):
                    if entry.name not in skip_dirs:
                        stack.append(ep)
                elif entry.is_file(follow_symlinks=False):
                    rel = ep.relative_to(root)
                    if entry.name == "lake-manifest.json":
                        manifest_paths[rel] = ep
                    elif entry.name == "lakefile.toml":
                        toml_paths[rel] = ep
                    elif ep.suffix == ".lean":
                        lean_files[rel] = ep
        except LeanAuditHardeningError:
            raise
        except OSError as exc:
            raise LeanAuditHardeningError("LEAN_TREE_IO_ERROR", f"failed scanning Lean directory {cur}: {exc}") from exc


_FORBIDDEN_LAKE_KEYS = frozenset({
    "leanOptions",
    "moreLeanArgs",
    "weakLeanArgs",
    "moreServerArgs",
    "moreLinkArgs",
    "moreLeancArgs",
    "precompileModules",
    "supportInterpreter",
    "lean_exe",
})
_UNSAFE_LAKE_STR_TOKENS: tuple[str, ...] = (
    "debug.byAsSorry",
    "debug.skipKernelTC",
    "debug.proofAsSorry",
    "debug.terminalTacticsAsSorry",
)
_LAKEFILE_LEAN_UNSAFE_RE = re.compile(
    r"(?<![A-Za-z0-9_'.])(?:leanOptions|moreLeanArgs|weakLeanArgs|moreServerArgs|moreLinkArgs|moreLeancArgs|precompileModules|supportInterpreter|lean_exe)(?![A-Za-z0-9_'])"
)


def _check_toml_unsafe_options(tdata: dict[str, Any], rel: str, findings: list[dict[str, Any]]) -> None:
    seen_opts: set[str] = set()
    stack: list[Any] = [tdata]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k in sorted(cur):
                v = cur[k]
                if type(k) is str:
                    bad = k if k in _FORBIDDEN_LAKE_KEYS else next((t for t in _UNSAFE_LAKE_STR_TOKENS if t in k), "")
                    if bad and bad not in seen_opts:
                        seen_opts.add(bad)
                        findings.append({"file": rel, "line": 1, "code": "LEAN4_LAKEFILE_UNSAFE_OPTION", "excerpt": bad})
                stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
        elif type(cur) is str:
            bad = next((t for t in _UNSAFE_LAKE_STR_TOKENS if t in cur), "")
            if bad and bad not in seen_opts:
                seen_opts.add(bad)
                findings.append({"file": rel, "line": 1, "code": "LEAN4_LAKEFILE_UNSAFE_OPTION", "excerpt": bad})


def _extract_toml_root_specs(tdata: dict[str, Any]) -> tuple[list[tuple[str, str]], bool]:
    """Return `(base_src_dir, module_spec)` pairs for `roots` and `globs`, plus `invalid_flag`."""
    specs: list[tuple[str, str]] = []
    invalid = False
    top_sdir = tdata.get("srcDir") if type(tdata.get("srcDir")) is str and tdata["srcDir"].strip() else "."

    def _collect_from(obj: dict[str, Any], sdir: str) -> None:
        nonlocal invalid
        if "roots" in obj:
            roots = obj["roots"]
            if type(roots) is not list:
                invalid = True
            else:
                for r in roots:
                    if type(r) is not str or not r.strip():
                        invalid = True
                    else:
                        specs.append((sdir, r.strip()))
        if "globs" in obj:
            globs = obj["globs"]
            if type(globs) is not list:
                invalid = True
            else:
                for g in globs:
                    if type(g) is str and g.strip():
                        specs.append((sdir, g.strip()))
                    elif isinstance(g, dict):
                        val = g.get("submodules") if "submodules" in g else g.get("andSubmodules")
                        if type(val) is str and val.strip():
                            specs.append((sdir, val.strip()))
                        else:
                            invalid = True
                    else:
                        invalid = True

    _collect_from(tdata, top_sdir)
    for sec_key in ("lean_lib", "lean_exe"):
        sec = tdata.get(sec_key)
        items = sec if type(sec) is list else ([sec] if type(sec) is dict else [])
        for item in items:
            if isinstance(item, dict):
                sdir = item.get("srcDir") if type(item.get("srcDir")) is str and item["srcDir"].strip() else top_sdir
                _collect_from(item, sdir)
    return specs, invalid


def _scan_lake_root_spec(
    base: Path,
    base_sdir: str,
    mod_spec: str,
    *,
    rel_lakefile: str,
    root: Path,
    seen_dirs: set[Path],
    lean_files: dict[Path, Path],
    manifest_paths: dict[Path, Path],
    toml_paths: dict[Path, Path],
    findings: list[dict[str, Any]],
) -> None:
    trimmed = mod_spec[:-2] if mod_spec.endswith((".*", ".+")) else mod_spec
    if "/" in trimmed or "\\" in trimmed or ".." in trimmed.split("."):
        findings.append({"file": rel_lakefile, "line": 1, "code": "LEAN4_LAKEFILE_SRCDIR_ESCAPE", "excerpt": mod_spec[:100]})
        return
    parts = [seg for seg in trimmed.split(".") if seg]
    if not parts:
        findings.append({"file": rel_lakefile, "line": 1, "code": "LEAN4_LAKEFILE_INVALID", "excerpt": mod_spec[:100]})
        return
    if any(seg in _SKIP_DIRS or seg.startswith(".") for seg in parts):
        findings.append({"file": rel_lakefile, "line": 1, "code": "LEAN4_LAKEFILE_SKIPPED_ROOT", "excerpt": mod_spec[:100]})
    sdir_path, escaped = _safe_subdir_no_symlink(base, base_sdir, rel_lakefile)
    if escaped or sdir_path is None:
        return
    rel_dir = "/".join(parts)
    sub_dir, _ = _safe_subdir_no_symlink(sdir_path, rel_dir, rel_lakefile)
    if sub_dir is not None:
        _scan_dir_tree(
            sub_dir,
            skip_dirs=frozenset(),
            seen_dirs=seen_dirs,
            lean_files=lean_files,
            manifest_paths=manifest_paths,
            toml_paths=toml_paths,
            root=root,
        )
    parent_rel = "/".join(parts[:-1]) if len(parts) > 1 else "."
    parent_dir, _ = _safe_subdir_no_symlink(sdir_path, parent_rel, rel_lakefile)
    if parent_dir is not None:
        mod_file = parent_dir / f"{parts[-1]}.lean"
        try:
            st = os.lstat(mod_file)
        except OSError:
            return
        if stat.S_ISLNK(st.st_mode):
            raise LeanAuditHardeningError("SYMLINK_IN_LEAN_TREE", f"symlink forbidden in root module: {mod_file.name}")
        if stat.S_ISREG(st.st_mode):
            lean_files[mod_file.relative_to(root)] = mod_file


def _process_lakefile_lean_config(
    lf: Path,
    rel: str,
    *,
    root: Path,
    seen_dirs: set[Path],
    lean_files: dict[Path, Path],
    manifest_paths: dict[Path, Path],
    toml_paths: dict[Path, Path],
    findings: list[dict[str, Any]],
) -> None:
    raw = _read_regular_bytes(lf, rel)
    src = _zb.decode_strict_utf8_bytes(
        raw,
        rel,
        err_cls=LeanAuditHardeningError,
        bom_code="LEAN4_BOM_FORBIDDEN",
        crlf_code="LEAN4_CRLF_LINE_ENDINGS",
        require_crlf_only=True,
    )
    cleaned, _ = strip_lean4_comments_and_literals(src)
    if _LAKEFILE_LEAN_UNSAFE_RE.search(cleaned) is not None:
        findings.append({"file": rel, "line": 1, "code": "LEAN4_LAKEFILE_UNSAFE_OPTION", "excerpt": "unsafe lakefile.lean option"})
    if re.search(r'\bsrcDir\s*:=\s*(?=\S)(?!")', src) is not None:
        findings.append({"file": rel, "line": 1, "code": "LEAN4_LAKEFILE_INVALID", "excerpt": "non-literal srcDir"})
    src_dirs = re.findall(r'\bsrcDir\s*:=\s*"([^"\n]*)"', src)
    for sdir in src_dirs:
        if not sdir.strip():
            findings.append({"file": rel, "line": 1, "code": "LEAN4_LAKEFILE_INVALID", "excerpt": "empty srcDir"})
            continue
        sub, escaped = _safe_subdir_no_symlink(lf.parent, sdir, rel)
        if escaped:
            findings.append({"file": rel, "line": 1, "code": "LEAN4_LAKEFILE_SRCDIR_ESCAPE", "excerpt": sdir})
            continue
        if sub is not None:
            _scan_dir_tree(
                sub,
                skip_dirs=frozenset(),
                seen_dirs=seen_dirs,
                lean_files=lean_files,
                manifest_paths=manifest_paths,
                toml_paths=toml_paths,
                root=root,
            )
    base_sdir = src_dirs[0] if len(src_dirs) == 1 and src_dirs[0].strip() else "."
    for roots_blk in re.findall(r"\broots\s*:=\s*#\[([^\]]*)\]", cleaned):
        for rmod in re.findall(r"`([A-Za-z0-9_.']+)", roots_blk):
            _scan_lake_root_spec(
                lf.parent,
                base_sdir,
                rmod,
                rel_lakefile=rel,
                root=root,
                seen_dirs=seen_dirs,
                lean_files=lean_files,
                manifest_paths=manifest_paths,
                toml_paths=toml_paths,
                findings=findings,
            )


def _extract_toml_src_dirs(tdata: dict[str, Any]) -> list[tuple[bool, str]]:
    """Return list of `(is_valid_type, srcDir_value)` declared in `lakefile.toml`."""
    out: list[tuple[bool, str]] = []
    if "srcDir" in tdata:
        val = tdata["srcDir"]
        out.append((type(val) is str and bool(val.strip()), val if type(val) is str else ""))
    for sec_key in ("lean_lib", "lean_exe", "lean_data"):
        sec = tdata.get(sec_key)
        items = sec if type(sec) is list else ([sec] if type(sec) is dict else [])
        for item in items:
            if isinstance(item, dict) and "srcDir" in item:
                val = item["srcDir"]
                out.append((type(val) is str and bool(val.strip()), val if type(val) is str else ""))
    return out


def _safe_subdir_no_symlink(base: Path, rel_str: str, label: str) -> tuple[Path | None, bool]:
    if "\x00" in rel_str:
        raise LeanAuditHardeningError("INVALID_PATH", f"{label}: NUL byte forbidden")
    sub = Path(rel_str)
    if sub.is_absolute() or ".." in sub.parts:
        return None, True
    cur = base
    for part in sub.parts:
        if part in ("", "."):
            continue
        cur = cur / part
        try:
            st = os.lstat(cur)
        except OSError:
            return None, False
        if stat.S_ISLNK(st.st_mode):
            raise LeanAuditHardeningError("SYMLINK_IN_LEAN_TREE", f"symlink forbidden in srcDir: {cur.name}")
        if not stat.S_ISDIR(st.st_mode):
            return None, False
    return cur, False


def audit_lean4_project_hardened(
    target_path: Any,
    *,
    allow_non_init_imports: bool = False,
    allow_project_imports: Sequence[str] = (),
    require_nonempty: bool = True,
) -> dict[str, Any]:
    """
    Fail-closed directory/file Lean 4 project audit (`EXP-Q46b`).

    Never returns RC=0 / `clean=True` on nonexistent paths, symlinked roots, or
    empty directories; never skips `lakefile.lean` or `lakefile` `srcDir` targets
    (even when named `venv`/`.venv`/`.lake`); cross-checks `lakefile.toml`
    `require` entries against `lake-manifest.json`.
    """
    p = Path(target_path) if type(target_path) is str else target_path
    _require(isinstance(p, Path), "INVALID_PATH", "target_path must be str or Path")
    _require("\x00" not in os.fspath(p), "INVALID_PATH", "target_path contains NUL byte")
    try:
        raw_st = os.lstat(p)
    except OSError as exc:
        raise LeanAuditHardeningError("MISSING_LEAN_TARGET", f"Lean target missing or unreadable: {exc}") from exc
    _require(not stat.S_ISLNK(raw_st.st_mode), "SYMLINK_TARGET_FORBIDDEN", "Lean target root must not be a symlink")

    lean_files: dict[Path, Path] = {}
    manifest_paths: dict[Path, Path] = {}
    toml_paths: dict[Path, Path] = {}
    seen_dirs: set[Path] = set()
    if stat.S_ISREG(raw_st.st_mode):
        _require(p.suffix == ".lean", "NOT_LEAN_FILE", f"expected .lean file, got {p.name}")
        lean_files[Path(p.name)] = p
    else:
        _require(stat.S_ISDIR(raw_st.st_mode), "INVALID_LEAN_TARGET", "target must be regular file or directory")
        _scan_dir_tree(
            p,
            skip_dirs=_SKIP_DIRS,
            seen_dirs=seen_dirs,
            lean_files=lean_files,
            manifest_paths=manifest_paths,
            toml_paths=toml_paths,
            root=p,
        )

    findings: list[dict[str, Any]] = []
    parsed_tomls: list[tuple[Path, str, dict[str, Any]]] = []
    for rel_tp in sorted(toml_paths):
        tp = toml_paths[rel_tp]
        rel = str(rel_tp)
        text = _zb.decode_strict_utf8_bytes(
            _read_regular_bytes(tp, rel),
            rel,
            err_cls=LeanAuditHardeningError,
            bom_code="LEAN4_BOM_FORBIDDEN",
            crlf_code="LEAN4_CRLF_LINE_ENDINGS",
            require_crlf_only=True,
        )
        try:
            tdata = tomllib.loads(text)
        except (tomllib.TOMLDecodeError, ValueError) as exc:
            findings.append({"file": rel, "line": 1, "code": "LEAN4_LAKEFILE_INVALID", "excerpt": str(exc)[:100]})
            continue
        parsed_tomls.append((tp, rel, tdata))
        _check_toml_unsafe_options(tdata, rel, findings)
        for valid_type, sdir in _extract_toml_src_dirs(tdata):
            if not valid_type:
                findings.append({"file": rel, "line": 1, "code": "LEAN4_LAKEFILE_INVALID", "excerpt": "invalid srcDir"})
                continue
            sub, escaped = _safe_subdir_no_symlink(tp.parent, sdir, rel)
            if escaped:
                findings.append({"file": rel, "line": 1, "code": "LEAN4_LAKEFILE_SRCDIR_ESCAPE", "excerpt": sdir})
                continue
            if sub is not None:
                _scan_dir_tree(
                    sub,
                    skip_dirs=frozenset(),
                    seen_dirs=seen_dirs,
                    lean_files=lean_files,
                    manifest_paths=manifest_paths,
                    toml_paths=toml_paths,
                    root=p,
                )
        root_specs, bad_roots = _extract_toml_root_specs(tdata)
        if bad_roots:
            findings.append({"file": rel, "line": 1, "code": "LEAN4_LAKEFILE_INVALID", "excerpt": "invalid roots/globs"})
        for base_sdir, mod_spec in root_specs:
            _scan_lake_root_spec(
                tp.parent,
                base_sdir,
                mod_spec,
                rel_lakefile=rel,
                root=p,
                seen_dirs=seen_dirs,
                lean_files=lean_files,
                manifest_paths=manifest_paths,
                toml_paths=toml_paths,
                findings=findings,
            )

    for rel_lf in sorted(list(lean_files)):
        if rel_lf.name == "lakefile.lean":
            _process_lakefile_lean_config(
                lean_files[rel_lf],
                str(rel_lf),
                root=p,
                seen_dirs=seen_dirs,
                lean_files=lean_files,
                manifest_paths=manifest_paths,
                toml_paths=toml_paths,
                findings=findings,
            )

    if require_nonempty:
        _require(len(lean_files) > 0, "EMPTY_LEAN_DIRECTORY", "no .lean files found under target")

    for rel_lf in sorted(lean_files):
        lf = lean_files[rel_lf]
        rel = str(rel_lf)
        raw = _read_regular_bytes(lf, rel)
        src = _zb.decode_strict_utf8_bytes(
            raw,
            rel,
            err_cls=LeanAuditHardeningError,
            bom_code="LEAN4_BOM_FORBIDDEN",
            crlf_code="LEAN4_CRLF_LINE_ENDINGS",
            require_crlf_only=True,
        )
        res = audit_lean4_source_hardened(
            src,
            allow_non_init_imports=allow_non_init_imports,
            allow_project_imports=allow_project_imports,
        )
        for item in res["findings"]:
            findings.append({"file": rel, **item})

    manifest_pkgs: dict[Path, set[str]] = {}
    for rel_mp in sorted(manifest_paths):
        mp = manifest_paths[rel_mp]
        rel = str(rel_mp)
        data = _loads_strict_json(_read_regular_bytes(mp, rel), rel, allow_float=False)
        _require(type(data) is dict and type(data.get("packages")) is list, "LEAN4_LAKE_MANIFEST_INVALID", f"{rel}: invalid packages list")
        pkgs = data["packages"]
        names: set[str] = set()
        for pkg in pkgs:
            if isinstance(pkg, dict) and type(pkg.get("name")) is str and pkg["name"].strip():
                names.add(pkg["name"])
        manifest_pkgs[mp.parent] = names
        if not allow_non_init_imports and len(pkgs) > 0:
            findings.append({"file": rel, "line": 1, "code": "LEAN4_LAKE_MANIFEST_NONEMPTY_PACKAGES", "excerpt": f"{len(pkgs)} packages"})

    for tp, rel, tdata in parsed_tomls:
        reqs = tdata.get("require", [])
        if type(reqs) is not list:
            findings.append({"file": rel, "line": 1, "code": "LEAN4_LAKEFILE_INVALID", "excerpt": "require must be array"})
            continue
        declared: list[str] = []
        bad_req = False
        for req_item in reqs:
            if not isinstance(req_item, dict) or type(req_item.get("name")) is not str or not req_item["name"].strip():
                bad_req = True
                break
            declared.append(req_item["name"])
        if bad_req:
            findings.append({"file": rel, "line": 1, "code": "LEAN4_LAKEFILE_INVALID", "excerpt": "require entry missing valid name"})
            continue
        if declared:
            mset = manifest_pkgs.get(tp.parent)
            if mset is None:
                findings.append({"file": rel, "line": 1, "code": "LEAN4_LAKEFILE_MISSING_MANIFEST", "excerpt": f"missing manifest for {declared[0]}"})
            else:
                for dname in declared:
                    if dname not in mset:
                        findings.append({"file": rel, "line": 1, "code": "LEAN4_LAKEFILE_UNMANIFESTED_REQUIRE", "excerpt": dname})

    return {
        "schema": "aletheia.lean_audit_hardening.v1",
        "files_checked": len(lean_files),
        "manifests_checked": len(manifest_paths),
        "lakefiles_checked": len(toml_paths) + sum(1 for lf in lean_files.values() if lf.name == "lakefile.lean"),
        "clean": len(findings) == 0,
        "findings": findings,
    }


def _read_module_source_no_resolve(root_p: Path, mod_name: str) -> tuple[str | None, str | None]:
    """Read local module `mod_name` using `O_NOFOLLOW` traversal (never `Path.resolve()`)."""
    mod_rel = Path(*mod_name.split(".")).with_suffix(".lean")
    mod_p = root_p / mod_rel
    try:
        raw = _read_regular_bytes(mod_p, mod_p.name)
    except LeanAuditHardeningError as exc:
        if exc.code == "IO_ERROR" and isinstance(exc.__cause__, (FileNotFoundError, NotADirectoryError)):
            return None, f"MISSING_MODULE:{mod_name}"
        cause = exc.__cause__
        if isinstance(cause, OSError) and cause.errno == errno.ELOOP:
            return None, f"SYMLINK_MODULE:{mod_name}"
        return None, f"UNREADABLE_MODULE:{mod_name}:{exc.code}"
    src = _zb.decode_strict_utf8_bytes(
        raw,
        mod_p.name,
        err_cls=LeanAuditHardeningError,
        bom_code="LEAN4_BOM_FORBIDDEN",
        crlf_code="LEAN4_CRLF_LINE_ENDINGS",
        require_crlf_only=True,
    )
    return src, None


def _extract_call_span(text: str, start_idx: int) -> str:
    n = len(text)
    i = start_idx
    depth = 0
    while i < n:
        ch = text[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and ch in (";", "\n"):
            if ch == ";":
                break
            rest = text[i + 1 :].lstrip(" \t")
            if not rest or rest[0] in ("#", "\n") or re.match(
                r"(?:let|def|theorem|lemma|private|protected|open|namespace|run_cmd|for|if|return|collectAxioms)\b",
                rest,
            ):
                break
        i += 1
    return text[start_idx:i]


def _validate_str_collection(val: Any, code: str, label: str) -> list[str]:
    _require(type(val) in (list, tuple, set, frozenset), code, f"{label} must be list, tuple, set, or frozenset")
    items = list(val)
    _require(all(type(x) is str and bool(x.strip()) for x in items), code, f"{label} entries must be non-empty str")
    return items


def validate_comparator_config_hardened(
    config_path: Any,
    *,
    lean_root: Any = None,
    require_nanoda: bool = True,
) -> dict[str, Any]:
    """Fail-closed Comparator `config.json` validator rejecting `enable_nanoda: false`, missing root, & transitive leaks."""
    data = _loads_strict_json(_read_regular_bytes(config_path, "comparator_config"), "comparator_config", allow_float=False)
    _require(type(data) is dict, "INVALID_COMPARATOR_CONFIG", "comparator config must be JSON object")
    if lean_root is not None:
        _require(type(lean_root) is str or isinstance(lean_root, Path), "INVALID_PATH", "lean_root must be str or Path")
        _require("\x00" not in os.fspath(lean_root), "INVALID_PATH", "lean_root contains NUL byte")
        root_p = Path(lean_root) if type(lean_root) is str else lean_root
    else:
        cfg_p = Path(config_path) if type(config_path) is str else config_path
        root_p = cfg_p.parent if str(cfg_p.parent) else Path(".")
    errors: list[str] = []

    chl = data.get("challenge_module")
    sol = data.get("solution_module")
    thms = data.get("theorem_names")
    axioms = data.get("permitted_axioms")
    nanoda = data.get("enable_nanoda")

    chl_valid = type(chl) is str and _MOD_NAME_RE.match(chl) is not None
    sol_valid = type(sol) is str and _MOD_NAME_RE.match(sol) is not None
    if not chl_valid:
        errors.append("INVALID_CHALLENGE_MODULE")
    if not sol_valid:
        errors.append("INVALID_SOLUTION_MODULE")
    if chl_valid and chl == sol:
        errors.append("CHALLENGE_EQUALS_SOLUTION")
    if type(thms) is not list or not thms or any(type(t) is not str or not t.strip() for t in thms):
        errors.append("INVALID_THEOREM_NAMES")
    if type(axioms) is not list or any(type(a) is not str for a in axioms):
        errors.append("INVALID_PERMITTED_AXIOMS")
    else:
        bad_ax = sorted(a for a in axioms if a not in STANDARD_LEAN4_AXIOMS)
        if bad_ax:
            errors.append(f"NONSTANDARD_AXIOMS:{','.join(bad_ax)}")
    if require_nanoda and nanoda is not True:
        errors.append(f"NANODA_DISABLED:{nanoda!r}")

    def _audit_module_bfs(start_mod: str, *, is_solution: bool) -> None:
        visited: set[str] = {start_mod}
        queue: deque[str] = deque([start_mod])
        role = "SOLUTION" if is_solution else "CHALLENGE"
        while queue:
            cur = queue.popleft()
            src, err = _read_module_source_no_resolve(root_p, cur)
            if err is not None:
                if cur == start_mod:
                    if err.startswith("MISSING_MODULE:"):
                        errors.append(f"MISSING_{role}_FILE")
                    else:
                        errors.append(f"UNREADABLE_{role}_FILE:{err}")
                elif err.startswith("MISSING_MODULE:"):
                    errors.append(f"MISSING_TRANSITIVE_{role}_MODULE:{cur}")
                else:
                    errors.append(f"UNREADABLE_TRANSITIVE_{role}_MODULE:{cur}:{err}")
                continue
            res = audit_lean4_source_hardened(src if src is not None else "", allow_non_init_imports=True)
            if is_solution and chl_valid and (chl in res["imports"] or any(imp.startswith(chl + ".") for imp in res["imports"])):
                if "SOLUTION_IMPORTS_CHALLENGE" not in errors:
                    errors.append("SOLUTION_IMPORTS_CHALLENGE")
            for f in res["findings"]:
                prefix = f"{role}_ESCAPE" if cur == start_mod else f"TRANSITIVE_{role}_ESCAPE:{cur}"
                errors.append(f"{prefix}:{f['code']}@L{f['line']}")
            for imp in res["imports"]:
                if imp not in visited and imp.split(".", 1)[0] not in ("Init", "Std"):
                    visited.add(imp)
                    queue.append(imp)

    if chl_valid:
        _audit_module_bfs(chl, is_solution=False)
    if sol_valid:
        _audit_module_bfs(sol, is_solution=True)

    return {"schema": "aletheia.comparator_hardened.v1", "passed": len(errors) == 0, "errors": errors}


def audit_target_audit_source(source: Any) -> dict[str, Any]:
    """
    Audit a `TargetAudit.lean`-style verification script (`solved-conjectures#902`).

    Enforces `withImportModules` + `loadExts := false` isolation against `#8271` /
    elaborator `run_cmd` / `initialize` spoofing and requires `ModuleData.constNames`
    + `collectAxioms` invocation checks.
    """
    _require(type(source) is str and len(source.strip()) > 0, "EMPTY_TARGET_AUDIT", "TargetAudit source required")
    cleaned, lex_findings = strip_lean4_comments_and_literals(source)
    scan_text = _ROOT_NS_PREFIX_RE.sub("", cleaned)
    errors: list[str] = [f"TARGET_AUDIT_LEX:{f['code']}" for f in lex_findings]

    imp_calls = list(re.finditer(r"(?<![A-Za-z0-9_'.])(?:withImportModules|importModules)(?![A-Za-z0-9_'])", scan_text))
    if not imp_calls:
        errors.append("MISSING_WITH_IMPORT_MODULES")
    unsafe_exts = (
        re.search(r"\bloadExts\s*:=\s*false(?![A-Za-z0-9_'])", scan_text) is None
        or re.search(r"\bloadExts\s*:=\s*(?=\S)(?!false(?![A-Za-z0-9_']))", scan_text) is not None
        or re.search(r"\b(?:leakEnv|enableInitializersExecution)\s*:=\s*(?=\S)(?!false(?![A-Za-z0-9_']))", scan_text) is not None
        or re.search(r"\bplugins\s*:=\s*(?=\S)(?!#\[\s*\])", scan_text) is not None
    )
    for m_call in imp_calls:
        span = _extract_call_span(scan_text, m_call.end())
        if re.search(r"\bloadExts\s*:=\s*false(?![A-Za-z0-9_'])", span) is None:
            unsafe_exts = True
            break
    if unsafe_exts:
        errors.append("TARGET_AUDIT_UNSAFE_ELAB_EXTS")

    if re.search(r"(?:\.|\bModuleData\s*\.\s*)constNames(?![A-Za-z0-9_'])", scan_text) is None:
        errors.append("MISSING_SERIALIZED_CONSTNAMES_CHECK")
    if re.search(r"(?<!\bdef\s)(?<![A-Za-z0-9_'])(?:Lean\s*\.\s*)?collectAxioms\s+(?!:=)[^\s;:=)]+", scan_text) is None:
        errors.append("MISSING_COLLECT_AXIOMS")
    for pat, code in _SOURCE_ESCAPE_RULES[:_TARGET_AUDIT_KERNEL_RULES_END]:
        if pat.search(scan_text) is not None:
            errors.append(f"TARGET_AUDIT_ESCAPE:{code}")
    if _find_stop_tactic_lines(scan_text):
        errors.append("TARGET_AUDIT_ESCAPE:LEAN4_STOP_TACTIC")
    return {"schema": "aletheia.target_audit_source.v1", "passed": len(errors) == 0, "errors": errors}


def audit_target_audit_log(
    log_text: Any,
    *,
    expected_modules: Sequence[str],
    required_decls: Sequence[str],
    expected_private_decls: Sequence[str] = (),
    allowed_axioms: frozenset[str] = STANDARD_LEAN4_AXIOMS,
) -> dict[str, Any]:
    """
    Validate `ALL-OWNED-JSON` / `#print axioms` verification output (`solved-conjectures#902`),
    checking non-vacuity, private-declaration completeness, `import_all`, `has_data`, summary
    counts, and zero forbidden axioms (`sorryAx`, `ofReduceBool`, `trustCompiler`, native LRAT).
    """
    _require(type(log_text) is str and len(log_text.strip()) > 0, "EMPTY_AUDIT_LOG", "audit log text must be non-empty")
    exp_mods = _validate_str_collection(expected_modules, "INVALID_EXPECTED_MODULES", "expected_modules")
    req_decls = _validate_str_collection(required_decls, "INVALID_REQUIRED_DECLS", "required_decls")
    exp_privs = _validate_str_collection(expected_private_decls, "INVALID_EXPECTED_PRIVATE_DECLS", "expected_private_decls")
    ok_axioms = set(_validate_str_collection(allowed_axioms, "INVALID_ALLOWED_AXIOMS", "allowed_axioms"))

    marker = "ALL-OWNED-JSON "
    errors: list[str] = []

    for f in _AXIOM_LOG_RULES:
        pat, code = f
        if pat.search(log_text) is not None:
            errors.append(f"FORBIDDEN_AXIOM_IN_LOG:{code}")

    modules: dict[str, dict[str, Any]] = {}
    decls: dict[str, dict[str, Any]] = {}
    required_seen: set[str] = set()
    passed_summaries: list[dict[str, Any]] = []

    for lineno, line in enumerate(log_text.split("\n"), start=1):
        if not line.startswith(marker):
            continue
        payload_str = line[len(marker) :]
        rec = _zb.parse_strict_json_text(
            payload_str,
            f"log:{lineno}",
            err_cls=LeanAuditHardeningError,
            max_depth=MAX_JSON_DEPTH,
            max_int_digits=MAX_JSON_INT_DIGITS,
            allow_float=False,
        )
        _require(type(rec) is dict, "INVALID_LOG_RECORD", f"log:{lineno}: must be dict")
        tag = rec.get("tag")
        if tag == "module":
            mod = rec.get("module")
            _require(type(mod) is str and mod not in modules, "INVALID_OR_DUP_MODULE", f"log:{lineno}: bad module {mod!r}")
            modules[mod] = rec
        elif tag == "declaration":
            dname = rec.get("name")
            _require(type(dname) is str and dname not in decls, "INVALID_OR_DUP_DECL", f"log:{lineno}: bad decl {dname!r}")
            decls[dname] = rec
        elif tag == "required":
            rname = rec.get("name")
            _require(type(rname) is str, "INVALID_REQUIRED_DECL", f"log:{lineno}: bad required decl")
            required_seen.add(rname)
        elif tag == "passed":
            passed_summaries.append(rec)
        else:
            errors.append(f"UNKNOWN_LOG_TAG:{tag!r}")

    if len(exp_mods) == 0:
        errors.append("EMPTY_EXPECTED_MODULES")
    if len(req_decls) == 0:
        errors.append("EMPTY_REQUIRED_DECLS")
    if set(modules) != set(exp_mods):
        errors.append("MODULE_INVENTORY_MISMATCH")
    if len(passed_summaries) != 1:
        errors.append("MISSING_OR_DUP_PASSED_SUMMARY")

    raw_serialized: set[str] = set()
    raw_name_count = 0
    for mod, mrec in modules.items():
        if mrec.get("import_all") is not True or mrec.get("has_data") is not True:
            errors.append(f"INCOMPLETE_PRIVATE_DATA:{mod}")
        names = mrec.get("names")
        if type(names) is not list or any(type(x) is not str or not x.strip() for x in names):
            errors.append(f"INVALID_CONSTNAMES:{mod}")
        else:
            if len(set(names)) != len(names):
                errors.append(f"DUPLICATE_CONSTNAME:{mod}")
            if any(
                not (x == mod or x.startswith(mod + ".") or x.startswith(f"_private.{mod}."))
                for x in names
            ):
                errors.append(f"FOREIGN_CONSTNAME:{mod}")
            raw_serialized.update(names)
            raw_name_count += len(names)

    if len(modules) == 0 or len(decls) == 0 or len(raw_serialized) == 0:
        errors.append("VACUOUS_AUDIT_LOG")

    if not set(req_decls) <= required_seen or not required_seen <= set(decls):
        errors.append("REQUIRED_DECL_MISSING")
    if not set(req_decls) <= raw_serialized:
        errors.append("REQUIRED_DECL_NOT_SERIALIZED")
    if exp_privs and not set(exp_privs) <= raw_serialized:
        errors.append("MISSING_PRIVATE_DECLARATION")

    if not raw_serialized <= set(decls):
        errors.append("ESCAPED_SERIALIZED_DECLARATION")
    if not set(decls) <= raw_serialized:
        errors.append("UNSERIALIZED_DECLARATION")

    for dname, drec in decls.items():
        axs = drec.get("axioms")
        if type(axs) is not list or any(type(a) is not str for a in axs):
            errors.append(f"INVALID_DECL_AXIOMS:{dname}")
        elif not set(axs) <= ok_axioms:
            errors.append(f"UNAPPROVED_DECL_AXIOM:{dname}")

    if len(passed_summaries) == 1:
        s = passed_summaries[0]
        expected_counts = (
            ("modules", len(modules)),
            ("declarations", len(decls)),
            ("raw_declarations", len(raw_serialized)),
        )
        if (
            any(type(s.get(k)) is not int or s.get(k) != n for k, n in expected_counts)
            or raw_name_count != len(raw_serialized)
        ):
            errors.append("SUMMARY_COUNT_MISMATCH")

    return {
        "schema": "aletheia.target_audit_log.v1",
        "passed": len(errors) == 0,
        "modules_checked": len(modules),
        "declarations_checked": len(decls),
        "raw_declarations_checked": len(raw_serialized),
        "errors": errors,
    }


def run_exp_q46b_bypass_suite(*, scratch_parent: Path | None = None) -> dict[str, Any]:
    """
    Deterministic check suite covering positive pure-`Init` controls AND all real-world
    bypass vectors from `arXiv:2611.32334v2` (`check_clean.py`) and `solved-conjectures#902`.
    """
    import tempfile

    checks: dict[str, bool] = {}

    clean_src = (
        "-- comment with \"string\" inside\n"
        "def okId (x : Nat) : Nat := x\n"
        "def okQuote : String := \"/- sorry axiom ofReduceBool -/\"\n"
        "theorem okThm (x : Nat) : okId x = x := rfl\n"
    )
    checks["positive_clean_init_passes"] = audit_lean4_source_hardened(clean_src)["clean"]

    checks["bypass_1_sorryAx"] = any(
        f["code"] == "LEAN4_SORRY_AX"
        for f in audit_lean4_source_hardened("theorem bad : False := sorryAx _\n")["findings"]
    )
    checks["bypass_2_ofReduceBool"] = any(
        f["code"] == "LEAN4_OF_REDUCE_BOOL"
        for f in audit_lean4_source_hardened("theorem bad : True := Lean.ofReduceBool _ _ rfl\n")["findings"]
    )
    checks["bypass_3_trustCompiler"] = any(
        f["code"] == "LEAN4_TRUST_COMPILER"
        for f in audit_lean4_source_hardened("def bad := Lean.trustCompiler\n")["findings"]
    )
    partial_src = "private partial def loop (n : Nat) : Nat := loop n\ntheorem thm : True := trivial\n"
    checks["bypass_4_partial_theorem_carrying"] = any(
        f["code"] == "LEAN4_PARTIAL_THEOREM_CARRYING"
        for f in audit_lean4_source_hardened(partial_src)["findings"]
    )
    str_escape_src = 'def s : String := "/-"\ntheorem hidden : False := sorry\n'
    checks["bypass_8_string_literal_escape"] = any(
        f["code"] == "LEAN4_SORRY"
        for f in audit_lean4_source_hardened(str_escape_src)["findings"]
    )
    interp_escape_src = 'def s : String := s!"{ "/-" }"\ntheorem fake : False := sorry\ndef t : String := s!"{ "-/" }"\n'
    checks["bypass_9_interpolated_string_escape"] = any(
        f["code"] == "LEAN4_SORRY"
        for f in audit_lean4_source_hardened(interp_escape_src)["findings"]
    )

    ws_interp_src = 'def s : String := s! "{ "/-" }"\ntheorem fake : False := sorry\ndef t : String := s! "{ "-/" }"\n'
    checks["bypass_9b_ws_interpolated_string_escape"] = any(
        f["code"] == "LEAN4_SORRY"
        for f in audit_lean4_source_hardened(ws_interp_src)["findings"]
    )
    syntax_interp_src = 'syntax "q!" interpolatedStr(term) : term\nmacro_rules | `(q! $s) => `(s! $s)\n'
    checks["bypass_9c_syntax_interpolated_banned"] = any(
        f["code"] == "LEAN4_SYNTAX_MACRO_ESCAPE"
        for f in audit_lean4_source_hardened(syntax_interp_src)["findings"]
    )
    ml_attr_src = '@[\nextern "c_evil"\n]\ndef f : Nat := 0\n'
    checks["bypass_10_multiline_extern_attr"] = any(
        f["code"] == "LEAN4_ATTR_ESCAPE"
        for f in audit_lean4_source_hardened(ml_attr_src)["findings"]
    )
    bang_s_src = 'def badPrefix : Bool := !s!"{ "/-" }".isEmpty\ntheorem bad_nh1 : False := sorry\ndef badPrefix2 : Bool := !s!"{ "-/" }".isEmpty\n'
    checks["bypass_12_bang_s_interpolated"] = any(
        f["code"] == "LEAN4_SORRY"
        for f in audit_lean4_source_hardened(bang_s_src)["findings"]
    )
    checks["bypass_13_stop_tactic"] = any(
        f["code"] == "LEAN4_STOP_TACTIC"
        for f in audit_lean4_source_hardened("theorem t_stop : False := by stop skip\n")["findings"]
    )
    checks["bypass_14_root_sorryAx"] = any(
        f["code"] == "LEAN4_SORRY_AX"
        for f in audit_lean4_source_hardened("theorem t_rs : False := _root_.sorryAx False true\n")["findings"]
    )
    checks["bypass_15_root_guillemet_sorryAx"] = any(
        f["code"] == "LEAN4_SORRY_AX"
        for f in audit_lean4_source_hardened("theorem t_rgs : False := _root_.«sorryAx» False true\n")["findings"]
    )
    checks["bypass_16_decide_plus_native"] = any(
        f["code"] == "LEAN4_DECIDE_NATIVE"
        for f in audit_lean4_source_hardened("theorem t_dn : 1 + 1 = 2 := by decide +native\n")["findings"]
    )
    throw_at_src = 'import Lean.Exception\ndef t (stx : Lean.Syntax) := throwErrorAt stx "{ "/-" }"\ntheorem bad_m7 : False := sorry\ndef t2 (stx : Lean.Syntax) := throwErrorAt stx "{ "-/" }"\n'
    checks["bypass_17_throwErrorAt_comparator"] = any(
        f["code"] == "LEAN4_SORRY"
        for f in audit_lean4_source_hardened(throw_at_src, allow_non_init_imports=True)["findings"]
    )

    with tempfile.TemporaryDirectory(dir=str(scratch_parent) if scratch_parent else None) as td:
        root = Path(td)
        # Bypass 5: enable_nanoda: false
        cfg = root / "config.json"
        cfg.write_text(
            json.dumps({
                "challenge_module": "Challenge",
                "solution_module": "Solution",
                "theorem_names": ["main_thm"],
                "permitted_axioms": ["propext", "Quot.sound"],
                "enable_nanoda": False,
            }) + "\n",
            encoding="utf-8",
        )
        comp_res = validate_comparator_config_hardened(cfg)
        checks["bypass_5_enable_nanoda_false"] = (not comp_res["passed"]) and ("NANODA_DISABLED:False" in comp_res["errors"])

        # Bypass 6: nonexistent dir must fail closed (never RC=0 / clean=True)
        nonexist_caught = False
        try:
            audit_lean4_project_hardened(root / "does_not_exist")
        except LeanAuditHardeningError as exc:
            nonexist_caught = exc.code == "MISSING_LEAN_TARGET"
        checks["bypass_6_nonexistent_dir_fails_closed"] = nonexist_caught

        # Empty dir must also fail closed
        empty_dir = root / "empty_proj"
        empty_dir.mkdir()
        empty_caught = False
        try:
            audit_lean4_project_hardened(empty_dir)
        except LeanAuditHardeningError as exc:
            empty_caught = exc.code == "EMPTY_LEAN_DIRECTORY"
        checks["bypass_6b_empty_dir_fails_closed"] = empty_caught

        # Bypass 7: lakefile.lean omission & srcDir="venv" bypass
        proj = root / "lake_bypass"
        proj.mkdir()
        (proj / "Main.lean").write_text("theorem ok : True := trivial\n", encoding="utf-8")
        (proj / "lakefile.lean").write_text("import Lake\nopen Lake DSL\ntheorem sneaky : False := sorry\n", encoding="utf-8")
        proj_res = audit_lean4_project_hardened(proj)
        checks["bypass_7_lakefile_lean_not_omitted"] = (not proj_res["clean"]) and any(
            f["file"] == "lakefile.lean" and f["code"] in ("LEAN4_NON_INIT_IMPORT", "LEAN4_SORRY")
            for f in proj_res["findings"]
        )

        srcdir_proj = root / "srcdir_bypass"
        srcdir_proj.mkdir()
        (srcdir_proj / "Main.lean").write_text("theorem ok : True := trivial\n", encoding="utf-8")
        (srcdir_proj / "lakefile.toml").write_text('name = "p"\n[[lean_lib]]\nname = "Evil"\nsrcDir = "venv"\n', encoding="utf-8")
        (srcdir_proj / "venv").mkdir()
        (srcdir_proj / "venv" / "Evil.lean").write_text("theorem bad : False := sorry\n", encoding="utf-8")
        srcdir_res = audit_lean4_project_hardened(srcdir_proj)
        checks["bypass_11_srcdir_venv_not_skipped"] = (not srcdir_res["clean"]) and any(
            f["code"] == "LEAN4_SORRY" for f in srcdir_res["findings"]
        )

    # TargetAudit (#902) private decl completeness + withImportModules/loadExts:=false check
    unsafe_ta = audit_target_audit_source(
        "withImportModules imports {loadExts := true}\ndef x := constNames\ndef y := collectAxioms\n"
    )
    checks["target_audit_unsafe_elab_flagged"] = (not unsafe_ta["passed"]) and (
        "TARGET_AUDIT_UNSAFE_ELAB_EXTS" in unsafe_ta["errors"]
    )

    safe_log = "\n".join([
        'ALL-OWNED-JSON {"tag":"module","module":"ModA","import_all":true,"has_data":true,"names":["ModA.thm","_private.ModA.0.helper"]}',
        'ALL-OWNED-JSON {"tag":"declaration","name":"ModA.thm","axioms":["propext"]}',
        'ALL-OWNED-JSON {"tag":"declaration","name":"_private.ModA.0.helper","axioms":[]}',
        'ALL-OWNED-JSON {"tag":"required","name":"ModA.thm"}',
        'ALL-OWNED-JSON {"tag":"passed","modules":1,"declarations":2,"raw_declarations":2}',
    ])
    checks["target_audit_log_clean_passes"] = audit_target_audit_log(
        safe_log, expected_modules=("ModA",), required_decls=("ModA.thm",)
    )["passed"]

    escaped_log = "\n".join([
        'ALL-OWNED-JSON {"tag":"module","module":"ModA","import_all":true,"has_data":true,"names":["ModA.thm","_private.ModA.0.hidden_sorry"]}',
        'ALL-OWNED-JSON {"tag":"declaration","name":"ModA.thm","axioms":["propext"]}',
        'ALL-OWNED-JSON {"tag":"required","name":"ModA.thm"}',
        'ALL-OWNED-JSON {"tag":"passed","modules":1,"declarations":1,"raw_declarations":2}',
    ])
    escaped_res = audit_target_audit_log(escaped_log, expected_modules=("ModA",), required_decls=("ModA.thm",))
    checks["target_audit_escaped_private_decl_caught"] = (not escaped_res["passed"]) and (
        "ESCAPED_SERIALIZED_DECLARATION" in escaped_res["errors"]
    )

    passed = all(checks.values())
    return {
        "schema": "aletheia.exp_q46b_suite.v1",
        "passed": passed,
        "checks_passed": sum(1 for v in checks.values() if v),
        "checks_total": len(checks),
        "checks": checks,
    }


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="EXP-Q46b Lean 4 Audit Bypass Hardening Suite")
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--self-test", action="store_true", help="Run deterministic EXP-Q46b bypass & positive check suite")
    grp.add_argument("--audit", type=Path, default=None, help="Audit a Lean 4 file or project directory fail-closed")
    ap.add_argument("--comparator-config", type=Path, default=None, help="Optional Comparator JSON config to validate")
    ap.add_argument("--json", action="store_true", help="Emit JSON output")
    args = ap.parse_args(argv)

    try:
        if args.self_test:
            res = run_exp_q46b_bypass_suite()
            print(json.dumps(res, indent=2, sort_keys=True))
            return 0 if res["passed"] else 1
        proj_res = audit_lean4_project_hardened(args.audit)
        comp_res = None
        if args.comparator_config is not None:
            comp_res = validate_comparator_config_hardened(args.comparator_config, lean_root=args.audit)
        ok = proj_res["clean"] and (comp_res is None or comp_res["passed"])
        payload = {"passed": ok, "lean_audit": proj_res, "comparator": comp_res}
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if ok else 1
    except LeanAuditHardeningError as exc:
        err = {"status": "ERROR", "code": exc.code, "message": exc.message}
        print(json.dumps(err, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
