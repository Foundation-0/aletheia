"""
Aletheia R13b Lean 4.36.0 Trust-Boundary Hardening (`W13-OBS-BVDECIDE` + `lake-manifest.json`).

Pure Python 3 standard library. Zero floats on exact checks. Zero bare `assert`s.

Closes two live Lean 4.36.0 audit gaps surfaced in Wave-12/Wave-13 cold kernel replays:
  1. `W13-OBS-BVDECIDE`: In Lean 4.36.0, `by bv_decide` does not emit `Lean.ofReduceBool`
     or `native_decide`; instead, on LRAT-fallback goals it injects native-C LRAT axioms
     (`<decl>._native.bv_decide.ax_* : Std.Tactic.BVDecide.Reflect.verifyBVExpr ... = true`),
     and `import Std.Tactic.BVDecide` / umbrella `import Std.Tactic` / `import Std` previously
     bypassed `LEAN4_NON_INIT_IMPORT` because `Std` is in the standard root allowlist.
     This module detects:
       - `bv_decide` tactic calls (including `bv_decide?`, `«bv_decide»`, and numeric-adjacent
         `by iterate 1bv_decide` / `0b1bv_decide` / `0o1bv_decide` via `W10-OBS-32` numeric
         literal blanking), with full Unicode Lean 4 identifier boundaries (`isIdFirst`/`isIdRest`)
         so valid pure-`Init` Unicode identifiers (`αbv_decide`, `bv_decide₁`, `bv_decideα`)
         produce zero false positives while comments, strings, raw strings, and French-quoted
         `«...»` identifiers (`«/-»`, `«a"»`) cannot hide or spoof code;
       - `Std.Tactic.BVDecide*`, `Lean.Elab.Tactic.BVDecide*`, `Lean.Meta.Tactic.BVDecide*`,
         and umbrella re-exports `Std` / `Std.Tactic` (including French-quoted segments like
         `Std.Tactic.«BVDecide»` and `import all`) as `LEAN4_BV_DECIDE_IMPORT`, plus non-import
         code references as `LEAN4_BV_DECIDE_REF`;
       - `._native.bv_decide.ax_*` and `_native.bv_decide` axiom artifacts in `.lean` files
         and axiom-audit logs (`*axiom*.{log,txt,out}` auto-discovered by directory walk, or
         explicitly audited via `audit_lean4_axiom_log(path)`).
  2. `lake-manifest.json` zero-dependency verification: When a `lake-manifest.json` is
     present in an audited Lean project, fails closed on malformed/non-regular/symlinked/
     directory manifests (`LEAN4_LAKE_MANIFEST_INVALID`) or non-empty `"packages"` lists
     (`LEAN4_LAKE_MANIFEST_NONEMPTY_PACKAGES`), blocking hidden external Lean dependencies.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat
from typing import Any, Sequence

from .strict_io import AletheiaError, parse_strict_json_text

# ---------------------------------------------------------------------------
# W10-OBS-32 Lean 4.36.0 identifier & numeric/char/guillemet lexing helpers
# ---------------------------------------------------------------------------

_LEAN4_HEX_DIGITS: frozenset[str] = frozenset("0123456789abcdefABCDEF")
_LEAN4_DEC_NUM_CHARS: frozenset[str] = frozenset("0123456789_")
_LEAN4_BIN_NUM_CHARS: frozenset[str] = frozenset("01_")
_LEAN4_OCT_NUM_CHARS: frozenset[str] = frozenset("01234567_")
_LEAN4_HEX_NUM_CHARS: frozenset[str] = _LEAN4_HEX_DIGITS | frozenset("_")

# Exact Lean 4.36.0 `Lean.isIdFirst` / `Lean.isIdRest` character classes (excludes non-ident
# alphanumerics like λ, Π, Σ and separates digit-led numeric literals from identifiers).
_LEAN4_ID_FIRST_CHARS: frozenset[str] = frozenset(
    chr(cp)
    for lo, hi in (
        (65, 90), (95, 95), (97, 122),
        (192, 214), (216, 246), (248, 383),
        (913, 927), (929, 930), (932, 937),
        (945, 954), (956, 969),
        (970, 1019), (7936, 8190),
        (8448, 8527), (119964, 120223),
    )
    for cp in range(lo, hi + 1)
)
_LEAN4_ID_SUBSCRIPT_AND_DIGITS: frozenset[str] = frozenset(
    chr(cp)
    for lo, hi in ((48, 57), (7522, 7530), (8320, 8329), (8336, 8348), (11388, 11388))
    for cp in range(lo, hi + 1)
)
# Identifier continuation characters excluding `?` and `!` (so `bv_decide?` remains a call boundary
# while `bv_decide₁`, `bv_decideα`, `bv_decide'`, and `bv_decide_count` stay whole identifiers).
_LEAN4_WORD_CONT_CHARS: frozenset[str] = (
    _LEAN4_ID_FIRST_CHARS | _LEAN4_ID_SUBSCRIPT_AND_DIGITS | frozenset("'")
)
_LEAN4_ID_REST_CHARS: frozenset[str] = _LEAN4_WORD_CONT_CHARS | frozenset("!?")

# Lean 4 interpolated-string prefixes whose `{...}` expressions must remain visible (`P2`).
# `s!`, `f!`, and `println!` are built-in `Init` parser syntax keywords (verified live on Lean 4.36.0:
# `def s!`, `def f!`, `def println!` all fail parsing). All other prefixes (`m!`, `v!`, `logInfo`,
# `throwError`, `dbg_trace`, custom macros) can take plain strings in `Init` or tactic mode, so the
# auditor runs dual-projection (`interp` + `plain`) whenever any non-reserved prefix appears (`B1`).
LEAN4_INIT_RESERVED_INTERP_BANG_WORDS: frozenset[str] = frozenset({"s", "f", "println"})
LEAN4_INTERP_BANG_WORDS: frozenset[str] = frozenset(
    {"s", "f", "m", "v", "println", "reportIssue", "reportDbgIssue", "reportEMatchIssue"}
)
LEAN4_INTERP_KEYWORDS: frozenset[str] = frozenset(
    {"dbg_trace", "throwError", "logInfo", "logError", "logWarning"}
)
LEAN4_INTERP_BRACKET_WORDS: frozenset[str] = frozenset({"trace", "trace_goal"})

# Matches single-line, multiline (up to 4 lines), `?`-suffixed (`"foo?"`), and multi-atom
# (`"foo" "bar" s:interpolatedStr`) custom `interpolatedStr` macro/syntax definitions (`B1`/`B4-B6`).
_CUSTOM_INTERP_MACRO_RE = re.compile(
    r'\b(?:macro|syntax)\b(?:[^\n]*\n){0,4}?[^\n]*"([A-Za-z_][A-Za-z0-9_]*)([!?]?)\s*"'
    r'(?:\s*(?:[A-Za-z_][A-Za-z0-9_]*\s*:\s*)?|\s*\n\s*)interpolatedStr\b'
)


def is_lean4_id_first(ch: str) -> bool:
    """Return True iff `ch` can start a Lean 4 identifier."""
    return ch in _LEAN4_ID_FIRST_CHARS


def is_lean4_id_rest(ch: str) -> bool:
    """Return True iff `ch` can continue a Lean 4 identifier."""
    return ch in _LEAN4_ID_REST_CHARS


def is_lean4_word_cont(ch: str) -> bool:
    """Return True iff `ch` continues a Lean 4 identifier word (excluding `!` and `?`)."""
    return ch in _LEAN4_WORD_CONT_CHARS


def extract_custom_lean4_interp_prefixes(source: str) -> tuple[frozenset[str], frozenset[str]]:
    """Return `(extra_bang_words, extra_plain_words)` for file-local `interpolatedStr` macros (`P2`/`B1`)."""
    if "interpolatedStr" not in source:
        return frozenset(), frozenset()
    bang: set[str] = set()
    plain: set[str] = set()
    for m in _CUSTOM_INTERP_MACRO_RE.finditer(source):
        if m.group(2) == "!":
            bang.add(m.group(1))
        else:
            plain.add(m.group(1) + m.group(2))
    return frozenset(bang), frozenset(plain)


def match_lean4_hash_command_end(source: str, i: int, n: int) -> int:
    """
    Advance past a Lean 4 `#command` token starting at `source[i] == '#'` (`N1` / `P1`).

    Stops immediately before an adjacent Char literal (`#check'"'`, `#mycmd'"'`) or
    raw string (`#evalr"\\"`, `#evalr#"\\"#`, `#mycmdr"\\"`) and consumes a single
    trailing `!` (`#eval!`), without relying on a fixed command allowlist.
    """
    j = i + 1
    while j < n and source[j] in _LEAN4_WORD_CONT_CHARS:
        if source[j] == "r":
            k = j + 1
            while k < n and source[k] == "#":
                k += 1
            if k < n and source[k] == '"':
                break
        if source[j] == "'" and match_lean4_char_literal_end(source, j, n) is not None:
            break
        j += 1
    if j < n and source[j] == "!":
        j += 1
    return j


def is_ambiguous_lean4_hash_command(source: str, i: int, cmd_end: int, n: int) -> bool:
    """
    Return True when a `#<ident>` prefix is glued without whitespace to `'`, `"`, or `r#*"` (`B3`).

    Without Lean's runtime syntax table, `#kx'"'+"`, `#kxr"\\"  "`, and `#kα'"'+"` have ambiguous
    token splits (`#k` + `x'` + `"+"` vs `#kx` + `'"'` + `+` + `"`), so fail closed with
    `LEAN4_AMBIGUOUS_LEXING`.
    """
    if cmd_end <= i + 1 or cmd_end >= n:
        return False
    ch = source[cmd_end]
    if ch in ("'", '"'):
        return True
    if ch == "r":
        k = cmd_end + 1
        while k < n and source[k] == "#":
            k += 1
        if k < n and source[k] == '"':
            return True
    return False


def is_lean4_safe_guillemet_ident(inner: str) -> bool:
    """Return True iff French-quoted `«inner»` contains only safe identifier characters (no delimiters)."""
    return bool(inner) and all(ch in _LEAN4_WORD_CONT_CHARS for ch in inner)


def normalize_lean4_module_name(module_name: str) -> str:
    """Strip French guillemets from Lean 4 module segments (`Std.Tactic.«BVDecide»` -> `Std.Tactic.BVDecide`)."""
    return module_name.replace("«", "").replace("»", "")


def _has_lean4_ident_boundaries(text: str, start: int, end: int) -> bool:
    """Full Unicode Lean 4 identifier boundary check matching `Lean.isIdFirst`/`isIdRest` (`B2`)."""
    before_ok = start == 0 or text[start - 1] not in _LEAN4_ID_REST_CHARS
    after_ok = end == len(text) or text[end] not in _LEAN4_WORD_CONT_CHARS
    return before_ok and after_ok


def match_lean4_char_literal_end(source: str, i: int, n: int) -> int | None:
    """Return end index of a Lean 4 Char literal starting at `source[i] == \"'\"`, or None."""
    if i + 2 < n and source[i + 1] not in ("\\", "'") and source[i + 2] == "'":
        return i + 3
    if i + 3 < n and source[i + 1] == "\\":
        if source[i + 3] == "'" and source[i + 2] != "\n":
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


def scan_lean4_numeric_literal_end(source: str, i: int, n: int) -> int:
    """
    Advance past a Lean 4 numeric/scientific literal starting at digit `source[i]` (`W10-OBS-32`).

    Enforces exact per-base digit charsets (`0b`/`0B` -> `[01_]`, `0o`/`0O` -> `[0-7_]`,
    `0x`/`0X` -> `[0-9a-fA-F_]`) and decimal/scientific exponents so immediately adjacent
    identifiers like `by iterate 1bv_decide`, `0b1bv_decide`, or `0o1bv_decide` retain a
    clean token boundary once the numeric literal is blanked to spaces.
    """
    nxt = source[i + 1] if i + 1 < n else ""
    num_end = i + 1
    if source[i] == "0" and nxt in "xXbBoO":
        num_end += 1
        if nxt in "xX":
            base_chars = _LEAN4_HEX_NUM_CHARS
        elif nxt in "bB":
            base_chars = _LEAN4_BIN_NUM_CHARS
        else:
            base_chars = _LEAN4_OCT_NUM_CHARS
        while num_end < n and source[num_end] in base_chars:
            num_end += 1
        return num_end

    while num_end < n and source[num_end] in _LEAN4_DEC_NUM_CHARS:
        num_end += 1
    has_dot = False
    if num_end < n and source[num_end] == "." and num_end + 1 < n and "0" <= source[num_end + 1] <= "9":
        has_dot = True
        num_end += 2
        while num_end < n and source[num_end] in _LEAN4_DEC_NUM_CHARS:
            num_end += 1
    exp_start = num_end + 1 if (not has_dot and num_end < n and source[num_end] == ".") else num_end
    if exp_start < n and source[exp_start] in "eE":
        exp_pos = exp_start + 1
        if exp_pos < n and source[exp_pos] in "+-":
            exp_pos += 1
        if exp_pos < n and "0" <= source[exp_pos] <= "9":
            while exp_pos < n and source[exp_pos] in _LEAN4_DEC_NUM_CHARS:
                exp_pos += 1
            num_end = exp_pos
    return num_end


# ---------------------------------------------------------------------------
# W13-OBS-BVDECIDE static Lean 4 & axiom-audit log detection
# ---------------------------------------------------------------------------

BV_DECIDE_MODULE_PREFIXES: tuple[str, ...] = (
    "Std.Tactic.BVDecide",
    "Lean.Elab.Tactic.BVDecide",
    "Lean.Meta.Tactic.BVDecide",
    "Lean.Elab.Tactic.Grind.BVDecide",
    "Lean.Meta.Tactic.Grind.BVDecide",
)

# Umbrella stdlib/compiler roots that transitively re-export `Std.Tactic.BVDecide` / `bv_decide`
# (`Std/Tactic.lean:9`, `Std.lean:14`, `Lean.lean`, `Lean/Elab.lean`, `Lean/Elab/Tactic.lean`).
# Exact match only so unrelated submodules like `Std.Data.HashMap` or `Std.Tactic.Do` stay allowed.
BV_DECIDE_UMBRELLA_MODULES: frozenset[str] = frozenset(
    {"Std", "Std.Tactic", "Lean", "Lean.Elab", "Lean.Elab.Tactic"}
)

# Raw token matchers (`bv_decide` & LRAT-replay `bv_check`); exact Unicode identifier boundaries
# are enforced via `_has_lean4_ident_boundaries` (`N2` / `B2`).
_LEAN4_BV_DECIDE_CALL_RE = re.compile(r"bv_(?:decide|check)")

# Matches `Std.Tactic.BVDecide`, `Lean.{Elab,Meta}.Tactic.(Grind.)?BVDecide` references
# (including French-quoted segments like `Std.Tactic.«BVDecide»` and multiline dot chains).
_LEAN4_BV_DECIDE_REF_RE = re.compile(
    r"(?:«?Std»?\s*\.\s*«?Tactic»?|«?Lean»?\s*\.\s*(?:«?Elab»?|«?Meta»?)\s*\.\s*«?Tactic»?(?:\s*\.\s*«?Grind»?)?)\s*\.\s*«?BVDecide»?",
    flags=re.DOTALL,
)

# Matches native LRAT axiom artifacts emitted by Lean 4.36.0 `bv_decide`:
# `<decl>._native.bv_decide.ax_1_15` or bare `_native.bv_decide` (incl. French-quoted segments).
_LEAN4_BV_DECIDE_AXIOM_RE = re.compile(
    r"(?:\.\s*)?(«?_native»?\s*\.\s*«?bv_decide»?(?:\s*\.\s*«?ax_[A-Za-z0-9_]*»?)?)",
    flags=re.DOTALL,
)

# General Lean 4.36.0 native-tactic axiom artifacts (`B4`): `<decl>._native.<tactic>.ax_*`
# (e.g. `t._native.decide.ax_1_1`, `t._native.grind.ax_1`). `bv_decide` is handled above.
_LEAN4_GENERAL_NATIVE_AXIOM_RE = re.compile(
    r"(?:\.\s*)?(«?_native»?\s*\.\s*«?(?!bv_decide(?:»|\b))([A-Za-z_][A-Za-z0-9_]*)»?\s*\.\s*«?ax_[A-Za-z0-9_]*»?)",
    flags=re.DOTALL,
)

# Axiom-audit log line rules (e.g. `#print axioms` / `Lean.collectAxioms` output files).
_LEAN4_AXIOM_LOG_BV_RE = re.compile(
    r"(?:\._native\.bv_decide(?:\.ax_[A-Za-z0-9_]*)?|(?<![A-Za-z0-9_'])_native\.bv_decide(?:\.ax_[A-Za-z0-9_]*)?)"
)
_LEAN4_AXIOM_LOG_GENERAL_NATIVE_RE = re.compile(
    r"(?:\._native\.(?!bv_decide\b)[A-Za-z_][A-Za-z0-9_]*\.ax_[A-Za-z0-9_]*|(?<![A-Za-z0-9_'])_native\.(?!bv_decide\b)[A-Za-z_][A-Za-z0-9_]*\.ax_[A-Za-z0-9_]*)"
)
_LEAN4_AXIOM_LOG_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (_LEAN4_AXIOM_LOG_BV_RE, "LEAN4_BV_DECIDE_AXIOM"),
    (_LEAN4_AXIOM_LOG_GENERAL_NATIVE_RE, "LEAN4_NATIVE_AXIOM"),
    (re.compile(r"\bsorryAx\b"), "LEAN4_SORRY_AX"),
    (re.compile(r"\bLean\.ofReduceBool\b|\bofReduceBool\b"), "LEAN4_OF_REDUCE_BOOL"),
    (re.compile(r"\bLean\.ofReduceNat\b|\bofReduceNat\b"), "LEAN4_OF_REDUCE_NAT"),
    (re.compile(r"\bLean\.trustCompiler\b|\btrustCompiler\b"), "LEAN4_TRUST_COMPILER"),
)

_AXIOM_LOG_SUFFIXES: frozenset[str] = frozenset({".log", ".txt", ".out"})
_PACKAGES_KEY_RE = re.compile(r'"packages"\s*:')


def is_bv_decide_module(module_name: str) -> bool:
    """
    Return True when `module_name` (after normalizing French guillemets) is a BVDecide module
    (`Std.Tactic.BVDecide*`, `Lean.Elab.Tactic.BVDecide*`, `Lean.Meta.Tactic.BVDecide*`) or an
    umbrella root (`Std`, `Std.Tactic`) that publicly re-exports `Std.Tactic.BVDecide`.
    """
    norm = normalize_lean4_module_name(module_name)
    if norm in BV_DECIDE_UMBRELLA_MODULES:
        return True
    return any(
        norm == pref or norm.startswith(pref + ".")
        for pref in BV_DECIDE_MODULE_PREFIXES
    )


def _line_has_bv_decide_call(line: str) -> bool:
    for m in _LEAN4_BV_DECIDE_CALL_RE.finditer(line):
        start, end = m.start(), m.end()
        if not _has_lean4_ident_boundaries(line, start, end):
            continue
        # Exclude `_native.bv_decide` (classified separately as `LEAN4_BV_DECIDE_AXIOM`)
        prefix = line[:start].rstrip()
        if prefix.endswith("_native.") or prefix.endswith("_native»."):
            continue
        return True
    return False


def scan_lean4_bv_decide_source(
    cleaned: str,
    *,
    import_entries: Sequence[tuple[int, str]] = (),
) -> list[dict[str, Any]]:
    """
    Scan comment/literal-stripped Lean 4 source (`cleaned`) for `W13-OBS-BVDECIDE` trust escapes:
      - `LEAN4_BV_DECIDE_IMPORT`: `import Std.Tactic.BVDecide*`, `Lean.{Elab,Meta}.Tactic.BVDecide*`,
        and umbrella `Std` / `Std.Tactic` (including French-quoted segments & `import all`)
      - `LEAN4_BV_DECIDE`: `bv_decide` tactic calls (with full Unicode Lean 4 identifier boundaries)
      - `LEAN4_BV_DECIDE_REF`: non-import references to `{Std,Lean.Elab,Lean.Meta}.Tactic.BVDecide`
      - `LEAN4_BV_DECIDE_AXIOM`: `._native.bv_decide.ax_*` / `_native.bv_decide` axiom artifacts
    """
    findings: list[dict[str, Any]] = []
    bv_import_lines: set[int] = set()

    for lineno, mod in import_entries:
        if is_bv_decide_module(mod):
            bv_import_lines.add(lineno)
            findings.append(
                {"line": lineno, "code": "LEAN4_BV_DECIDE_IMPORT", "excerpt": normalize_lean4_module_name(mod)[:100]}
            )

    for lineno, line in enumerate(cleaned.splitlines(), start=1):
        if _line_has_bv_decide_call(line):
            findings.append({"line": lineno, "code": "LEAN4_BV_DECIDE", "excerpt": line.strip()[:100]})

    ref_line, ref_pos = 1, 0
    for m_ref in _LEAN4_BV_DECIDE_REF_RE.finditer(cleaned):
        start, end = m_ref.start(), m_ref.end()
        ref_line += cleaned.count("\n", ref_pos, start)
        ref_pos = start
        if ref_line not in bv_import_lines and _has_lean4_ident_boundaries(cleaned, start, end):
            findings.append(
                {
                    "line": ref_line,
                    "code": "LEAN4_BV_DECIDE_REF",
                    "excerpt": " ".join(m_ref.group(0).split())[:100],
                }
            )

    ax_line, ax_pos = 1, 0
    for m_ax in _LEAN4_BV_DECIDE_AXIOM_RE.finditer(cleaned):
        inner_start, inner_end = m_ax.start(1), m_ax.end(1)
        ax_line += cleaned.count("\n", ax_pos, inner_start)
        ax_pos = inner_start
        if _has_lean4_ident_boundaries(cleaned, inner_start, inner_end):
            findings.append(
                {
                    "line": ax_line,
                    "code": "LEAN4_BV_DECIDE_AXIOM",
                    "excerpt": " ".join(m_ax.group(0).split())[:100],
                }
            )

    gn_line, gn_pos = 1, 0
    for m_gn in _LEAN4_GENERAL_NATIVE_AXIOM_RE.finditer(cleaned):
        inner_start, inner_end = m_gn.start(1), m_gn.end(1)
        gn_line += cleaned.count("\n", gn_pos, inner_start)
        gn_pos = inner_start
        if _has_lean4_ident_boundaries(cleaned, inner_start, inner_end):
            findings.append(
                {
                    "line": gn_line,
                    "code": "LEAN4_NATIVE_AXIOM",
                    "excerpt": " ".join(m_gn.group(0).split())[:100],
                }
            )

    return findings


def scan_lean4_axiom_log_text(text: str) -> list[dict[str, Any]]:
    """
    Scan Lean 4 `#print axioms` / `Lean.collectAxioms` output text for non-pure-kernel axioms,
    specifically catching `._native.bv_decide.ax_*` / `_native.bv_decide` (`LEAN4_BV_DECIDE_AXIOM`),
    `sorryAx`, `Lean.ofReduceBool`, and `Lean.trustCompiler`.
    """
    findings: list[dict[str, Any]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pat, code in _LEAN4_AXIOM_LOG_RULES:
            if pat.search(line) is not None:
                findings.append({"line": lineno, "code": code, "excerpt": line.strip()[:100]})
    return findings


def audit_lean4_axiom_log(path: Path) -> dict[str, Any]:
    """Fail-closed scanner for a Lean 4 axiom-audit log file on disk."""
    findings: list[dict[str, Any]] = []
    try:
        st = os.lstat(path)
    except OSError as exc:
        findings.append({"line": 1, "code": "LEAN4_AXIOM_LOG_INVALID", "excerpt": f"unreadable axiom log: {exc}"[:100]})
        return {"clean": False, "findings": findings}
    if not stat.S_ISREG(st.st_mode):
        findings.append({"line": 1, "code": "LEAN4_AXIOM_LOG_INVALID", "excerpt": "non-regular or symlinked axiom log"})
        return {"clean": False, "findings": findings}
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        findings.append({"line": 1, "code": "LEAN4_AXIOM_LOG_INVALID", "excerpt": f"invalid UTF-8/IO in axiom log: {exc}"[:100]})
        return {"clean": False, "findings": findings}
    findings.extend(scan_lean4_axiom_log_text(text))
    return {"clean": len(findings) == 0, "findings": findings}


# ---------------------------------------------------------------------------
# lake-manifest.json zero-dependency verification (`packages: []`)
# ---------------------------------------------------------------------------

def _packages_line_number(text: str) -> int:
    m = _PACKAGES_KEY_RE.search(text)
    if m is None:
        return 1
    return text.count("\n", 0, m.start()) + 1


def _format_package_names(packages: list[Any]) -> str:
    names: list[str] = []
    for item in packages:
        if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip():
            names.append(item["name"].strip())
        else:
            names.append(repr(item))
    return ", ".join(names)


def audit_lean4_lake_manifest_text(
    text: str,
    *,
    allow_external_packages: bool = False,
) -> dict[str, Any]:
    """
    Strictly validate a `lake-manifest.json` payload for zero-dependency pure-`Init` Lean projects.

    Fail-closed rules:
      - Must parse as a strict RFC-8259 JSON object (no syntax errors, duplicate keys, NaN/Inf,
        or lone surrogates) -> else `LEAN4_LAKE_MANIFEST_INVALID`.
      - Must contain key `"packages"` whose value is a JSON list -> else `LEAN4_LAKE_MANIFEST_INVALID`.
      - Unless `allow_external_packages=True`, `"packages"` must be empty (`[]`) -> else
        `LEAN4_LAKE_MANIFEST_NONEMPTY_PACKAGES`.
    """
    findings: list[dict[str, Any]] = []
    try:
        data = parse_strict_json_text(text, allow_float=True, require_object=True)
    except AletheiaError as exc:
        findings.append(
            {
                "line": 1,
                "code": "LEAN4_LAKE_MANIFEST_INVALID",
                "excerpt": f"{exc.code}: {exc.message}"[:100],
            }
        )
        return {"clean": False, "findings": findings, "package_count": None}

    if "packages" not in data:
        findings.append(
            {
                "line": 1,
                "code": "LEAN4_LAKE_MANIFEST_INVALID",
                "excerpt": "lake-manifest.json missing required 'packages' field",
            }
        )
        return {"clean": False, "findings": findings, "package_count": None}

    packages = data["packages"]
    if not isinstance(packages, list):
        findings.append(
            {
                "line": _packages_line_number(text),
                "code": "LEAN4_LAKE_MANIFEST_INVALID",
                "excerpt": f"lake-manifest.json 'packages' must be a list, got {type(packages).__name__}",
            }
        )
        return {"clean": False, "findings": findings, "package_count": None}

    if not allow_external_packages:
        if len(packages) > 0:
            pkg_summary = _format_package_names(packages)
            findings.append(
                {
                    "line": _packages_line_number(text),
                    "code": "LEAN4_LAKE_MANIFEST_NONEMPTY_PACKAGES",
                    "excerpt": f"packages ({len(packages)}): {pkg_summary}"[:100],
                }
            )
            return {"clean": False, "findings": findings, "package_count": len(packages)}

    return {"clean": True, "findings": findings, "package_count": len(packages)}


def audit_lean4_lake_manifest(
    path: Path,
    *,
    allow_external_packages: bool = False,
) -> dict[str, Any]:
    """Fail-closed validation of a `lake-manifest.json` file on disk."""
    try:
        st = os.lstat(path)
    except OSError as exc:
        return {
            "clean": False,
            "findings": [
                {"line": 1, "code": "LEAN4_LAKE_MANIFEST_INVALID", "excerpt": f"unreadable manifest: {exc}"[:100]}
            ],
            "package_count": None,
        }
    if not stat.S_ISREG(st.st_mode):
        return {
            "clean": False,
            "findings": [
                {"line": 1, "code": "LEAN4_LAKE_MANIFEST_INVALID", "excerpt": "non-regular or symlinked lake-manifest.json"}
            ],
            "package_count": None,
        }
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {
            "clean": False,
            "findings": [
                {"line": 1, "code": "LEAN4_LAKE_MANIFEST_INVALID", "excerpt": f"invalid UTF-8/IO in manifest: {exc}"[:100]}
            ],
            "package_count": None,
        }
    return audit_lean4_lake_manifest_text(text, allow_external_packages=allow_external_packages)


def _is_axiom_log_filename(name: str) -> bool:
    lower = name.lower()
    return "axiom" in lower and Path(lower).suffix in _AXIOM_LOG_SUFFIXES


def audit_lean4_directory_r13b_artifacts(
    root: Path,
    *,
    skip_dirs: frozenset[str] = frozenset(),
    allow_external_packages: bool = False,
) -> dict[str, Any]:
    """
    Discover and validate `lake-manifest.json` files and `*axiom*.{log,txt,out}` axiom-audit
    logs under `root` (skipping `skip_dirs` and `.lake`, never following directory symlinks).
    """
    skip = set(skip_dirs) | {".lake"}
    manifest_paths: list[Path] = []
    axiom_log_paths: list[Path] = []

    if root.is_file():
        if root.name == "lake-manifest.json":
            manifest_paths.append(root)
        elif _is_axiom_log_filename(root.name):
            axiom_log_paths.append(root)
        elif root.suffix == ".lean":
            sib_manifest = root.parent / "lake-manifest.json"
            if os.path.lexists(sib_manifest):
                manifest_paths.append(sib_manifest)
    else:
        stack: list[Path] = [root]
        while stack:
            cur = stack.pop()
            try:
                entries = sorted(os.scandir(cur), key=lambda e: e.name)
            except OSError:
                continue
            for entry in entries:
                name = entry.name
                p = Path(entry.path)
                if name == "lake-manifest.json":
                    manifest_paths.append(p)
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if name not in skip:
                        stack.append(p)
                    continue
                if _is_axiom_log_filename(name):
                    axiom_log_paths.append(p)

    manifest_paths.sort()
    axiom_log_paths.sort()

    findings: list[dict[str, Any]] = []
    for mp in manifest_paths:
        rel = mp.name if root.is_file() else str(mp.relative_to(root))
        res = audit_lean4_lake_manifest(mp, allow_external_packages=allow_external_packages)
        for f in res["findings"]:
            findings.append({"file": rel, **f})

    for ap in axiom_log_paths:
        rel = ap.name if root.is_file() else str(ap.relative_to(root))
        res = audit_lean4_axiom_log(ap)
        for f in res["findings"]:
            findings.append({"file": rel, **f})

    return {
        "manifests_checked": len(manifest_paths),
        "axiom_logs_checked": len(axiom_log_paths),
        "findings": findings,
    }
