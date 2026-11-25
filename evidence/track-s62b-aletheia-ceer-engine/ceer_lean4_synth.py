#!/usr/bin/env python3
"""
Deterministic Pure-Init Lean 4.36.0 Certificate Synthesizer & Hardened Anti-Bypass Gate.

Generates self-contained pure-Init Lean 4.36.0 proof/disproof files (`0` Mathlib, `0` imports,
`0` sorry, `0` native_decide, `0` axioms) from CEER cycle records, enforces the hardened
12/12 `decide` / French-guillemet / plain-record-config static gate, and executes live
`lean` kernel compilation + `#print axioms` auditing.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any

LEAN_SYNTH_SCHEMA = "aletheia.ceer_lean4_synth.v1"
_ALLOWED_STANDARD_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})

# ---------------------------------------------------------------------------
# Hardened Static Anti-Bypass Scanner (AL-LG-R5-01..02 + Field Punning + :+/ ,+ Infix)
# ---------------------------------------------------------------------------

_LEAN4_IDENT_EXTRA = "_.'!?"
_LEAN4_CHAR_PREV_EXTRA = "_'»!?"
_LEAN4_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_LEAN4_PLAIN_GUILLEMET_RE = re.compile(r"\A[A-Za-z_][A-Za-z0-9_']*\Z")
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
_LEAN4_HARD_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?<!\.)\bsorry\b"), "LEAN4_SORRY"),
    (re.compile(r"(?<!\.)\bsorryAx\b"), "LEAN4_SORRY_AX"),
    (re.compile(r"(?<!\.)\badmit\b"), "LEAN4_ADMIT"),
    (re.compile(r"(?<!\.)\baxiom\b"), "LEAN4_AXIOM"),
    (re.compile(r"(?<!\.)\bnative_decide\b"), "LEAN4_NATIVE_DECIDE"),
    (re.compile(r"(?<!\.)\bunsafe\b"), "LEAN4_UNSAFE"),
    (re.compile(r"(?<!\.)\bpartial\s+(?:def|instance|abbrev)\b"), "LEAN4_PARTIAL"),
    (re.compile(r"\b(?:implemented_by|extern)\b"), "LEAN4_ATTR_TRUST_ESCAPE"),
    (re.compile(r"\bdebug\s*\.\s*skipKernelTC\b"), "LEAN4_SKIP_KERNEL_TC"),
    (re.compile(r"\bLean\.Meta\.mkSorry\b|\bmkSorry\b"), "LEAN4_MK_SORRY"),
    (re.compile(r"\bLean\.ofReduceBool\b|\bofReduceBool\b"), "LEAN4_OF_REDUCE_BOOL"),
    (re.compile(r"\bLean\.ofReduceNat\b|\bofReduceNat\b"), "LEAN4_OF_REDUCE_NAT"),
    (re.compile(r"\bLean\.trustCompiler\b|\btrustCompiler\b"), "LEAN4_TRUST_COMPILER"),
    (re.compile(r"(?m)^\s*(?:(?:public|private|meta)\s+)*import\s+(?!Init\b)"), "LEAN4_EXTERNAL_IMPORT"),
    (re.compile(r"#\s*(?:eval!?(?![A-Za-z0-9_])|reduce(?![A-Za-z0-9_])|exit(?![A-Za-z0-9_])|print(?![A-Za-z0-9_])(?!\s+axioms[ \t]+[A-Za-z_]))"), "LEAN4_META_CMD"),
    (re.compile(r"(?<!\.)\brun_cmd\b"), "LEAN4_META_CMD"),
)


def _match_lean4_char_literal_end(source: str, i: int, n: int) -> int | None:
    """Return end index of a Lean 4 Char literal starting at `source[i] == "'"`, or None."""
    if i + 2 < n and source[i + 1] != "\\" and source[i + 1] != "\n" and source[i + 2] == "'":
        return i + 3
    if i + 3 < n and source[i + 1] == "\\":
        if source[i + 2] != "\n" and source[i + 3] == "'":
            return i + 4
        esc = source[i + 2]
        if (
            esc == "x"
            and i + 5 < n
            and source[i + 5] == "'"
            and all(c in _LEAN4_HEX_DIGITS for c in source[i + 3 : i + 5])
        ):
            return i + 6
        if (
            esc == "u"
            and i + 7 < n
            and source[i + 7] == "'"
            and all(c in _LEAN4_HEX_DIGITS for c in source[i + 3 : i + 7])
        ):
            return i + 8
    return None


class CEERLeanError(ValueError):
    """Typed fail-closed error for Lean 4 synthesis, static scanning, and live verification."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _strip_lean4_comments_and_strings(source: str) -> tuple[str, list[dict[str, Any]]]:
    """Strip Lean 4 line/block comments and string literals while preserving newlines and `{...}` interpolations."""
    out: list[str] = []
    unterminated: list[dict[str, Any]] = []
    n = len(source)
    i = 0
    line = 1
    block_depth = 0
    block_start_line = 0
    # Interpolation stack: stores brace depth inside active interpolated string s!"...{...}..."
    interp_braces: list[int] = []
    in_str = False
    str_is_interp = False
    str_start_line = 0

    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""

        if block_depth > 0:
            if ch == "/" and nxt == "-":
                block_depth += 1
                out.append("  ")
                i += 2
                continue
            if ch == "-" and nxt == "/":
                block_depth -= 1
                out.append("  ")
                i += 2
                continue
            if ch == "\n":
                line += 1
                out.append("\n")
            else:
                out.append(" ")
            i += 1
            continue

        if in_str:
            if ch == "\\":
                if nxt == "\n":
                    line += 1
                    out.append(" \n")
                else:
                    out.append("  ")
                i += 2
                continue
            if str_is_interp and ch == "{":
                interp_braces.append(1)
                in_str = False
                out.append(" ")
                i += 1
                continue
            if ch == '"':
                in_str = False
                str_is_interp = False
                out.append(" ")
                i += 1
                continue
            if ch == "\n":
                line += 1
                out.append("\n")
            else:
                out.append(" ")
            i += 1
            continue

        # Code mode
        if ch == "«":
            end_g = source.find("»", i + 1)
            if end_g == -1:
                unterminated.append({"line": line, "code": "LEAN4_UNTERMINATED_IDENT"})
                out.append(" " * (n - i))
                break
            inner = source[i + 1 : end_g]
            if _LEAN4_PLAIN_GUILLEMET_RE.match(inner) is not None:
                out.append(source[i : end_g + 1])
            else:
                out.append("".join("\n" if c == "\n" else " " for c in source[i : end_g + 1]))
                line += inner.count("\n")
            i = end_g + 1
            continue
        if ch == "-" and nxt == "-":
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch == "/" and nxt == "-":
            block_depth = 1
            block_start_line = line
            out.append("  ")
            i += 2
            continue
        if interp_braces:
            if ch == "{":
                interp_braces[-1] += 1
                out.append(ch)
                i += 1
                continue
            if ch == "}":
                interp_braces[-1] -= 1
                if interp_braces[-1] == 0:
                    interp_braces.pop()
                    in_str = True
                    str_is_interp = True
                    out.append(" ")
                else:
                    out.append(ch)
                i += 1
                continue
        # Raw strings r"..." / r#"..."#
        if ch == "r" and (i == 0 or not (source[i - 1].isalnum() or source[i - 1] in _LEAN4_IDENT_EXTRA)):
            j = i + 1
            while j < n and source[j] == "#":
                j += 1
            if j < n and source[j] == '"':
                hashes = j - (i + 1)
                start_ln = line
                out.append(" " * (j - i + 1))
                i = j + 1
                closed = False
                while i < n:
                    if source[i] == '"' and source[i + 1 : i + 1 + hashes] == "#" * hashes:
                        out.append(" " * (1 + hashes))
                        i += 1 + hashes
                        closed = True
                        break
                    if source[i] == "\n":
                        line += 1
                        out.append("\n")
                    else:
                        out.append(" ")
                    i += 1
                if not closed:
                    unterminated.append({"line": start_ln, "code": "LEAN4_UNTERMINATED_STRING"})
                continue
        # Interpolated string s!"..." / m!"..." / f!"..."
        if ch == "!" and nxt == '"':
            is_smf = (
                i >= 1
                and source[i - 1] in "smf"
                and (i == 1 or not (source[i - 2].isalnum() or source[i - 2] in _LEAN4_IDENT_EXTRA))
            )
            if is_smf:
                in_str = True
                str_is_interp = True
                str_start_line = line
                out.append("  ")
                i += 2
                continue
        if ch == '"':
            in_str = True
            str_is_interp = False
            str_start_line = line
            out.append(" ")
            i += 1
            continue
        if ch == "'" and (i == 0 or not (source[i - 1].isalnum() or source[i - 1] in _LEAN4_CHAR_PREV_EXTRA)):
            # Lean 4 char literals ('"', '\n', '\x27', '\u0027') without disturbing identifier primes x'
            char_end = _match_lean4_char_literal_end(source, i, n)
            if char_end is not None:
                out.append(" " * (char_end - i))
                i = char_end
                continue
        if ch == "\n":
            line += 1
        out.append(ch)
        i += 1

    if block_depth > 0:
        unterminated.append({"line": block_start_line, "code": "LEAN4_UNTERMINATED_COMMENT"})
    if in_str or interp_braces:
        unterminated.append({"line": str_start_line, "code": "LEAN4_UNTERMINATED_STRING"})
    return "".join(out), unterminated


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


def _scan_lean4_decide_native(cleaned: str) -> list[tuple[int, int]]:
    if "decide" not in cleaned:
        return []
    n = len(cleaned)
    match_rparen: dict[int, int] = {}
    stack: list[int] = []
    for idx, ch in enumerate(cleaned):
        if ch == "(":
            stack.append(idx)
        elif ch == ")" and stack:
            match_rparen[stack.pop()] = idx

    spans: list[tuple[int, int]] = []
    for m_dec in _LEAN4_DECIDE_KW_RE.finditer(cleaned):
        start = m_dec.start()
        pos = m_dec.end()
        hit = False
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
                    hit = True
                pos = m_flag.end()
                continue
            if ch == "(":
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
                        hit = True
                elif opt_key == "config":
                    if not _is_lean4_safe_config_span(cleaned, rhs_lo, close_idx, match_rparen):
                        hit = True
                pos = close_idx + 1
                continue
            break
        if hit:
            spans.append((start, pos))
    return spans


def scan_lean4_trust_escapes(source: str) -> dict[str, Any]:
    """Run hardened O(n) static Lean 4 trust-escape scan (incl. 12/12 guillemet/config/infix escapes)."""
    if type(source) is not str:
        raise CEERLeanError("LEAN_INVALID_SOURCE", "Lean source must be strict str")
    cleaned, unterminated = _strip_lean4_comments_and_strings(source)
    cleaned = _LEAN4_GUILLEMET_IDENT_RE.sub(r"\1", cleaned)
    findings: list[dict[str, Any]] = list(unterminated)

    for pat, code in _LEAN4_HARD_RULES:
        ln = 1
        pos = 0
        for m in pat.finditer(cleaned):
            ln += cleaned.count("\n", pos, m.start())
            pos = m.start()
            findings.append({"line": ln, "code": code})

    decide_spans = _scan_lean4_decide_native(cleaned)
    dec_ln = 1
    dec_pos = 0
    for ds, _de in decide_spans:
        dec_ln += cleaned.count("\n", dec_pos, ds)
        dec_pos = ds
        findings.append({"line": dec_ln, "code": "LEAN4_DECIDE_NATIVE"})

    for m_dc in _LEAN4_DECIDE_CONFIG_BIND_RE.finditer(cleaned):
        if any(ds <= m_dc.start() < de for ds, de in decide_spans):
            continue
        if any(grp is not None and not _is_lean4_native_rhs_false_span(grp, 0, len(grp)) for grp in m_dc.groups()):
            findings.append({"line": cleaned.count("\n", 0, m_dc.start()) + 1, "code": "LEAN4_DECIDE_NATIVE"})

    return {
        "clean": not findings,
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# Deterministic Pure-Init Lean 4.36.0 Certificate Synthesizer
# ---------------------------------------------------------------------------


def _lean_int(n: int) -> str:
    return f"({n} : Int)"


def synthesize_cycle_lean4(cycle: dict[str, Any]) -> dict[str, Any]:
    """Deterministically synthesize a self-contained pure-Init Lean 4.36.0 theorem file for a CEER cycle."""
    if type(cycle) is not dict or "cycle_index" not in cycle or "predicate_results" not in cycle:
        raise CEERLeanError("LEAN_INVALID_CYCLE", "cycle must be an evaluated CEER cycle dict")
    cyc = cycle["cycle_index"]
    if type(cyc) is not int or cyc < 0:
        raise CEERLeanError("LEAN_INVALID_CYCLE", "cycle_index must be non-negative int")
    theory_id = cycle["theory_id"]
    verdict = cycle["verdict"]
    preds = cycle["predicate_results"]

    lines: list[str] = [
        f"/- Auto-synthesized pure-Init Lean 4.36.0 CEER Cycle {cyc} Certificate ({theory_id}) -/",
        f"namespace CEERCycle{cyc}",
        "",
        "def twiceLoopAreaAux : List (Int × Int) -> Int × Int -> Int",
        "  | [], _ => 0",
        "  | [(x, y)], (x0, y0) => (y0 + y) * (x0 - x)",
        "  | (x1, y1) :: (x2, y2) :: rest, first =>",
        "    (y2 + y1) * (x2 - x1) + twiceLoopAreaAux ((x2, y2) :: rest) first",
        "",
        "def twiceLoopArea : List (Int × Int) -> Int",
        "  | [] => 0",
        "  | first :: rest => twiceLoopAreaAux (first :: rest) first",
        "",
        "def secondDiff (u0 u1 u2 y0 y1 y2 : Int) : Int :=",
        "  (y2 - y1) * (u1 - u0) - (y1 - y0) * (u2 - u1)",
        "",
    ]

    theorem_names: list[str] = []
    for rec in preds:
        pid = rec["id"]
        kind = rec["kind"]
        passed = rec["passed"]
        thm_base = f"cycle_{cyc}_{pid.lower()}"
        full_name = f"CEERCycle{cyc}.{thm_base}"

        if kind == "LINEAR_SCALING":
            lhs = rec["lhs_scaled_int"]
            rhs = rec["rhs_scaled_int"]
            if passed:
                stmt = f"{_lean_int(lhs)} <= {_lean_int(rhs)}"
            else:
                stmt = f"Not ({_lean_int(lhs)} <= {_lean_int(rhs)})"
            lines.append(f"theorem {thm_base} : {stmt} := by decide")
            theorem_names.append(full_name)

        elif kind == "CONCAVE_SECOND_DIFF":
            ctrls = rec["controls"]
            vals = rec["values"]
            conj_terms = [
                f"secondDiff {_lean_int(ctrls[i])} {_lean_int(ctrls[i + 1])} {_lean_int(ctrls[i + 2])} "
                f"{_lean_int(vals[i])} {_lean_int(vals[i + 1])} {_lean_int(vals[i + 2])} < 0"
                for i in range(len(ctrls) - 2)
            ]
            body_prop = " ∧ ".join(conj_terms)
            stmt = body_prop if passed else f"Not ({body_prop})"
            lines.append(f"theorem {thm_base} : {stmt} := by decide")
            theorem_names.append(full_name)

        elif kind == "SCHUR_DARK_DROP":
            # Encode exact rational comparison dark_drop >= threshold_q (or <=) via cross-multiplied Int
            dd_parts = rec["dark_drop_q"].split("/")
            dd_n = int(dd_parts[0])
            dd_d = int(dd_parts[1]) if len(dd_parts) == 2 else 1
            th_parts = rec["threshold_q"].split("/")
            th_n = int(th_parts[0])
            th_d = int(th_parts[1]) if len(th_parts) == 2 else 1
            if rec["expect_at_least"]:
                prop = f"{_lean_int(dd_n * th_d)} >= {_lean_int(th_n * dd_d)}"
            else:
                prop = f"{_lean_int(dd_n * th_d)} <= {_lean_int(th_n * dd_d)}"
            stmt = prop if passed else f"Not ({prop})"
            lines.append(f"theorem {thm_base} : {stmt} := by decide")
            theorem_names.append(full_name)

        elif kind in ("HYSTERESIS_ZERO_AREA", "HYSTERESIS_NONZERO_AREA"):
            pairs = ", ".join(f"({x}, {y})" for x, y in zip(rec["xs"], rec["ys"]))
            if kind == "HYSTERESIS_ZERO_AREA":
                prop = f"twiceLoopArea [{pairs}] = 0"
            else:
                min_a = rec["min_abs_twice_area"]
                prop = f"Int.natAbs (twiceLoopArea [{pairs}]) >= {min_a}"
            stmt = prop if passed else f"Not ({prop})"
            lines.append(f"theorem {thm_base} : {stmt} := by decide")
            theorem_names.append(full_name)

        elif kind == "RATIONAL_ENCLOSURE":
            conj_terms = []
            for pt in rec["points"]:
                num, den = pt["num"], pt["den"]
                lo_p = pt["lo_q"].split("/")
                lo_n, lo_d = int(lo_p[0]), (int(lo_p[1]) if len(lo_p) == 2 else 1)
                hi_p = pt["hi_q"].split("/")
                hi_n, hi_d = int(hi_p[0]), (int(hi_p[1]) if len(hi_p) == 2 else 1)
                conj_terms.append(
                    f"({_lean_int(lo_n * den)} <= {_lean_int(num * lo_d)} ∧ "
                    f"{_lean_int(num * hi_d)} <= {_lean_int(hi_n * den)})"
                )
            body_prop = " ∧ ".join(conj_terms)
            stmt = body_prop if passed else f"Not ({body_prop})"
            lines.append(f"theorem {thm_base} : {stmt} := by decide")
            theorem_names.append(full_name)

    lines.append("")
    lines.append(f"end CEERCycle{cyc}")
    lines.append("")
    for full_name in theorem_names:
        lines.append(f"#print axioms {full_name}")
    lines.append("")

    source = "\n".join(lines)
    scan = scan_lean4_trust_escapes(source)
    if not scan["clean"]:
        raise CEERLeanError("LEAN_SYNTH_UNSAFE", f"synthesized Lean failed static gate: {scan['findings']}")
    return {
        "schema": LEAN_SYNTH_SCHEMA,
        "cycle_index": cyc,
        "filename": f"CEER_Cycle{cyc}_Verdict.lean",
        "verdict": verdict,
        "theorem_names": theorem_names,
        "source": source,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
    }


def resolve_lean_binary(lean_bin: str | None = None) -> str:
    if lean_bin is not None:
        if type(lean_bin) is not str or not lean_bin or "\x00" in lean_bin:
            raise CEERLeanError("LEAN_INVALID_BIN", "lean_bin must be non-empty clean str")
        return lean_bin
    found = shutil.which("lean")
    if found:
        return found
    candidate = Path.home() / ".local" / "bin" / "lean"
    if candidate.is_file():
        return str(candidate)
    raise CEERLeanError("LEAN_NOT_FOUND", "lean binary not found in PATH or ~/.local/bin/lean")


def verify_lean4_source_live(
    source: str,
    theorem_names: list[str],
    lean_bin: str | None = None,
    timeout_s: int = 30,
) -> dict[str, Any]:
    """Static-gate, compile live with Lean 4.36.0, and verify zero forbidden axioms for every theorem."""
    if type(source) is not str or not source or "\x00" in source:
        raise CEERLeanError("LEAN_INVALID_SOURCE", "source must be non-empty clean str")
    if type(theorem_names) is not list or not theorem_names:
        raise CEERLeanError("LEAN_EMPTY_THEOREMS", "theorem_names must be non-empty list")
    for tn in theorem_names:
        if type(tn) is not str or not tn:
            raise CEERLeanError("LEAN_INVALID_THEOREM", "theorem name must be non-empty str")
    if type(timeout_s) is not int or timeout_s < 1:
        raise CEERLeanError("LEAN_INVALID_TIMEOUT", "timeout_s must be positive int")

    static_res = scan_lean4_trust_escapes(source)
    if not static_res["clean"]:
        raise CEERLeanError("LEAN_STATIC_REJECT", f"static anti-bypass gate rejected source: {static_res['findings']}")

    binary = resolve_lean_binary(lean_bin)
    try:
        ver_proc = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=timeout_s)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CEERLeanError("LEAN_EXEC_ERROR", f"failed to invoke lean --version: {exc}") from exc
    if ver_proc.returncode != 0:
        raise CEERLeanError("LEAN_VERSION_FAIL", f"lean --version exited {ver_proc.returncode}")
    lean_version = ver_proc.stdout.strip().splitlines()[0] if ver_proc.stdout.strip() else "unknown"
    if not lean_version.startswith("Lean (version 4.36.0"):
        raise CEERLeanError("LEAN_VERSION_UNSUPPORTED", f"require 'Lean (version 4.36.0' prefix, got: {lean_version}")

    with tempfile.TemporaryDirectory(prefix="aletheia_ceer_lean_") as td:
        os.chmod(td, 0o700)
        src_path = Path(td) / "CEERVerify.lean"
        src_path.write_text(source, encoding="utf-8")
        try:
            proc = subprocess.run([binary, str(src_path)], capture_output=True, text=True, timeout=timeout_s)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CEERLeanError("LEAN_EXEC_ERROR", f"lean compilation failed to execute: {exc}") from exc

    if proc.returncode != 0:
        combined = (proc.stdout + "\n" + proc.stderr).strip()
        raise CEERLeanError("LEAN_COMPILE_FAIL", f"lean rc={proc.returncode}: {combined[:240]}")
    if proc.stderr.strip():
        raise CEERLeanError("LEAN_STDERR_NONEMPTY", f"lean emitted stderr: {proc.stderr.strip()[:240]}")

    stdout_text = proc.stdout
    if "warning:" in stdout_text.lower():
        raise CEERLeanError("LEAN_WARNING_FORBIDDEN", f"lean emitted compiler warning: {stdout_text.strip()[:240]}")

    axioms_by_thm: dict[str, list[str]] = {}
    for m_none in re.finditer(r"(?m)^'([^']+)' does not depend on any axioms$", stdout_text):
        axioms_by_thm[m_none.group(1)] = []
    residual = re.sub(r"(?m)^'([^']+)' does not depend on any axioms$", "", stdout_text)
    for m_dep in re.finditer(r"(?ms)^'([^']+)' depends on axioms:\s*\[([^\]]*)\]", stdout_text):
        axs = [a.strip() for a in m_dep.group(2).split(",") if a.strip()]
        axioms_by_thm[m_dep.group(1)] = axs
    residual = re.sub(r"(?ms)^'([^']+)' depends on axioms:\s*\[([^\]]*)\]", "", residual)
    if residual.strip():
        raise CEERLeanError("LEAN_UNEXPECTED_STDOUT", f"unexpected lean stdout: {residual.strip()[:240]}")

    for tn in theorem_names:
        if tn not in axioms_by_thm:
            raise CEERLeanError("LEAN_MISSING_AXIOM_REPORT", f"no #print axioms output for {tn}")
        for ax in axioms_by_thm[tn]:
            if ax not in _ALLOWED_STANDARD_AXIOMS:
                raise CEERLeanError("LEAN_FORBIDDEN_AXIOM", f"theorem {tn} depends on non-standard axiom {ax}")

    return {
        "lean_version": lean_version,
        "returncode": 0,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "theorem_axioms": axioms_by_thm,
        "all_zero_axioms": all(len(axioms_by_thm[tn]) == 0 for tn in theorem_names),
    }
