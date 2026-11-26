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
  2. `lake-manifest.json` & `lakefile.{toml,lean}` dependency verification: When a
     `lake-manifest.json` is present in an audited Lean project, fails closed on
     malformed/non-regular/symlinked/directory manifests (`LEAN4_LAKE_MANIFEST_INVALID`) or
     non-empty `"packages"` lists (`LEAN4_LAKE_MANIFEST_NONEMPTY_PACKAGES`). When a
     `lakefile.toml` or `lakefile.lean` is present, parses declared `require` packages
     (respecting comments, strings, raw strings, char literals, and French guillemets; rejecting
     malformed lakefiles and raw `@[package_dep]` attributes with `LEAN4_LAKEFILE_INVALID`) and
     cross-checks every declared package against the sibling `lake-manifest.json` — failing closed
     if the manifest is absent (`LEAN4_LAKEFILE_MISSING_MANIFEST`), invalid, or omits any declared
     package (`LEAN4_LAKEFILE_UNMANIFESTED_REQUIRE`).
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat
import tomllib
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


def _extract_manifest_package_names(packages: list[Any]) -> list[str]:
    names: list[str] = []
    for item in packages:
        if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip():
            names.append(item["name"])
    return names


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
        return {"clean": False, "findings": findings, "package_count": None, "package_names": None}

    if "packages" not in data:
        findings.append(
            {
                "line": 1,
                "code": "LEAN4_LAKE_MANIFEST_INVALID",
                "excerpt": "lake-manifest.json missing required 'packages' field",
            }
        )
        return {"clean": False, "findings": findings, "package_count": None, "package_names": None}

    packages = data["packages"]
    if not isinstance(packages, list):
        findings.append(
            {
                "line": _packages_line_number(text),
                "code": "LEAN4_LAKE_MANIFEST_INVALID",
                "excerpt": f"lake-manifest.json 'packages' must be a list, got {type(packages).__name__}",
            }
        )
        return {"clean": False, "findings": findings, "package_count": None, "package_names": None}

    pkg_names = _extract_manifest_package_names(packages)
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
            return {
                "clean": False,
                "findings": findings,
                "package_count": len(packages),
                "package_names": pkg_names,
            }

    return {
        "clean": True,
        "findings": findings,
        "package_count": len(packages),
        "package_names": pkg_names,
    }


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
            "package_names": None,
        }
    if not stat.S_ISREG(st.st_mode):
        return {
            "clean": False,
            "findings": [
                {"line": 1, "code": "LEAN4_LAKE_MANIFEST_INVALID", "excerpt": "non-regular or symlinked lake-manifest.json"}
            ],
            "package_count": None,
            "package_names": None,
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
            "package_names": None,
        }
    return audit_lean4_lake_manifest_text(text, allow_external_packages=allow_external_packages)


# ---------------------------------------------------------------------------
# lakefile.toml & lakefile.lean `require` parsing and manifest cross-checking
# ---------------------------------------------------------------------------

_LAKEFILE_NAMES: frozenset[str] = frozenset({"lakefile.toml", "lakefile.lean"})
_TOML_REQUIRE_KEY_RE = re.compile(r"(?:^|\n)[ \t]*(?:\[\[\s*require\s*\]\]|require\s*=|\[[ \t]*require[ \t]*\])")
_LEAN_DECL_BEFORE_REQUIRE: frozenset[str] = frozenset(
    {
        "def",
        "theorem",
        "lemma",
        "abbrev",
        "let",
        "fun",
        "structure",
        "inductive",
        "class",
    }
)
_LEAN_LAKEFILE_METAPROG_COMMANDS: frozenset[str] = frozenset(
    {
        "macro",
        "macro_rules",
        "elab",
        "elab_rules",
        "syntax",
        "declare_syntax_cat",
        "notation",
        "prefix",
        "infix",
        "infixl",
        "infixr",
        "postfix",
        "run_cmd",
        "run_elab",
        "run_meta",
        "initialize",
        "builtin_initialize",
    }
)
_LEAN_LAKEFILE_FORBIDDEN_HASH_CMDS: frozenset[str] = frozenset(
    {"#eval", "#eval!", "#run_cmd", "#run_elab", "#run_meta"}
)
_LEAN_LAKEFILE_FORBIDDEN_ATTRS: frozenset[str] = frozenset(
    {
        "package_dep",
        "init",
        "builtin_init",
        "macro",
        "builtin_macro",
        "command_elab",
        "builtin_command_elab",
        "term_elab",
        "builtin_term_elab",
        "tactic",
        "builtin_tactic",
        "command_parser",
        "builtin_command_parser",
        "extern",
        "implemented_by",
        "export",
        "csimp",
    }
)
_DELIM_CLOSE: dict[str, str] = {"(": ")", "[": "]", "{": "}"}
_LEAN_STR_SIMPLE_ESCAPES: dict[str, str] = {
    "\\": "\\",
    '"': '"',
    "'": "'",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}


def _find_toml_require_line(text: str, pkg_name: str | None = None, search_from: int = 0) -> tuple[int, int]:
    """Locate approximate 1-based line number and next cursor for a `lakefile.toml` require entry."""
    if pkg_name is not None:
        pat = re.compile(
            r"""(?:^|[\s,{])((?:"name"|'name'|name)\s*=\s*(?:"|'|"{3}|'{3})""" + re.escape(pkg_name) + r")"
        )
        m = pat.search(text, search_from)
        if m is not None:
            return text.count("\n", 0, m.start(1)) + 1, m.end()
    m_req = _TOML_REQUIRE_KEY_RE.search(text, search_from)
    if m_req is not None:
        hit_pos = m_req.start() + (1 if text[m_req.start()] == "\n" else 0)
        return text.count("\n", 0, hit_pos) + 1, m_req.end()
    return 1, search_from


def parse_lakefile_toml_requires(text: str) -> dict[str, Any]:
    """
    Strictly parse `require` dependency declarations from a `lakefile.toml` payload.

    Uses Python's stdlib `tomllib` so `#` comments, string literals, single/multiline strings,
    inline arrays (`require = [{ name = "..." }]`), and duplicate keys obey TOML 1.0 semantics.
    Fails closed (`LEAN4_LAKEFILE_INVALID`) on syntax errors, non-list `require`, non-table entries,
    or missing/empty/padded/non-string `name`.
    """
    findings: list[dict[str, Any]] = []
    text = text.removeprefix("\ufeff")
    try:
        data = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, RecursionError, ValueError) as exc:
        findings.append(
            {
                "line": 1,
                "code": "LEAN4_LAKEFILE_INVALID",
                "excerpt": f"invalid lakefile.toml: {exc}"[:100],
            }
        )
        return {"valid": False, "requires": [], "findings": findings}

    if "require" not in data:
        return {"valid": True, "requires": [], "findings": findings}

    reqs_raw = data["require"]
    if not isinstance(reqs_raw, list):
        line, _ = _find_toml_require_line(text)
        findings.append(
            {
                "line": line,
                "code": "LEAN4_LAKEFILE_INVALID",
                "excerpt": f"lakefile.toml 'require' must be an array of tables, got {type(reqs_raw).__name__}",
            }
        )
        return {"valid": False, "requires": [], "findings": findings}

    requires: list[dict[str, Any]] = []
    cursor = 0
    for idx, entry in enumerate(reqs_raw):
        if not isinstance(entry, dict):
            line, cursor = _find_toml_require_line(text, None, cursor)
            findings.append(
                {
                    "line": line,
                    "code": "LEAN4_LAKEFILE_INVALID",
                    "excerpt": f"lakefile.toml require[{idx}] must be a table, got {type(entry).__name__}",
                }
            )
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip() or name != name.strip():
            line, cursor = _find_toml_require_line(text, None, cursor)
            findings.append(
                {
                    "line": line,
                    "code": "LEAN4_LAKEFILE_INVALID",
                    "excerpt": f"lakefile.toml require[{idx}] missing valid non-empty string 'name'",
                }
            )
            continue
        line, cursor = _find_toml_require_line(text, name, cursor)
        requires.append({"name": name, "line": line})

    return {"valid": len(findings) == 0, "requires": requires, "findings": findings}


def _decode_lean_string_literal(text: str, start: int, n: int) -> tuple[str | None, int, int]:
    """
    Parse a Lean 4 double-quoted string literal starting at `text[start] == '"'`.
    Returns `(decoded_or_None_if_unterminated, next_index, newlines_crossed)`.
    """
    chars: list[str] = []
    i = start + 1
    nl = 0
    while i < n:
        ch = text[i]
        if ch == '"':
            return "".join(chars), i + 1, nl
        if ch == "\\":
            if i + 1 >= n:
                return None, n, nl
            esc = text[i + 1]
            if esc in _LEAN_STR_SIMPLE_ESCAPES:
                chars.append(_LEAN_STR_SIMPLE_ESCAPES[esc])
                i += 2
            elif esc == "x" and i + 3 < n and all(c in _LEAN4_HEX_DIGITS for c in text[i + 2 : i + 4]):
                chars.append(chr(int(text[i + 2 : i + 4], 16)))
                i += 4
            elif esc == "u" and i + 5 < n and all(c in _LEAN4_HEX_DIGITS for c in text[i + 2 : i + 6]):
                chars.append(chr(int(text[i + 2 : i + 6], 16)))
                i += 6
            else:
                if esc == "\n":
                    nl += 1
                chars.append(esc)
                i += 2
        else:
            if ch == "\n":
                nl += 1
            chars.append(ch)
            i += 1
    return None, n, nl


def _tokenize_lakefile_lean(text: str) -> tuple[list[tuple[str, str, int, int, int]], list[dict[str, Any]]]:
    """
    Tokenize a Lean 4 `lakefile.lean` respecting `--` line comments, nested `/- ... -/` (and
    3-character `/--` / `/-!` doc-comment openers), regular/raw/interpolated strings, char
    literals, numeric literals, `#commands`, and French-quoted `«...»` identifiers.
    Emits `(kind, value, line, start_offset, end_offset)` tokens and fails closed
    (`LEAN4_LAKEFILE_INVALID`) on unclosed comments, strings, raw strings, or guillemets.
    """
    tokens: list[tuple[str, str, int, int, int]] = []
    findings: list[dict[str, Any]] = []
    i = 0
    n = len(text)
    line = 1
    pending_interp = False
    pending_ambig_interp = False
    in_interp_str = False
    interp_line = 1
    interp_stack: list[int] = []

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if in_interp_str:
            if ch == "\\" and i + 1 < n:
                if nxt == "\n":
                    line += 1
                i += 2
            elif ch == "{":
                interp_stack.append(1)
                tokens.append(("SYM", "{", line, i, i + 1))
                in_interp_str = False
                i += 1
            elif ch == '"':
                in_interp_str = False
                i += 1
            else:
                if ch == "\n":
                    line += 1
                i += 1
            continue

        if ch == "/" and nxt == "-":
            start_line = line
            depth = 1
            if i + 2 < n and text[i + 2] in ("-", "!"):
                i += 3
            else:
                i += 2
            while i < n and depth > 0:
                if text[i] == "/" and i + 1 < n and text[i + 1] == "-":
                    depth += 1
                    i += 2
                elif text[i] == "-" and i + 1 < n and text[i + 1] == "/":
                    depth -= 1
                    i += 2
                else:
                    if text[i] == "\n":
                        line += 1
                    i += 1
            if depth > 0:
                findings.append(
                    {
                        "line": start_line,
                        "code": "LEAN4_LAKEFILE_INVALID",
                        "excerpt": "unterminated block comment in lakefile.lean",
                    }
                )
            continue

        if ch == "-" and nxt == "-":
            while i < n and text[i] != "\n":
                i += 1
            continue

        if ch.isspace():
            if ch == "\n":
                line += 1
            i += 1
            continue

        if ch != '"':
            pending_interp = False
            pending_ambig_interp = False

        if interp_stack and ch in "{}":
            if ch == "{":
                interp_stack[-1] += 1
                tokens.append(("SYM", "{", line, i, i + 1))
            else:
                interp_stack[-1] -= 1
                tokens.append(("SYM", "}", line, i, i + 1))
                if interp_stack[-1] == 0:
                    interp_stack.pop()
                    in_interp_str = True
                    interp_line = line
            i += 1
            continue

        if ch == '"':
            if pending_interp:
                pending_interp = False
                in_interp_str = True
                interp_line = line
                i += 1
                continue
            was_ambig_interp = pending_ambig_interp
            pending_ambig_interp = False
            start_line = line
            start_pos = i
            decoded, next_i, nl = _decode_lean_string_literal(text, i, n)
            line += nl
            i = next_i
            if decoded is None:
                findings.append(
                    {
                        "line": start_line,
                        "code": "LEAN4_LAKEFILE_INVALID",
                        "excerpt": "unterminated string literal in lakefile.lean",
                    }
                )
                break
            if was_ambig_interp and ("{" in decoded or "}" in decoded):
                findings.append(
                    {
                        "line": start_line,
                        "code": "LEAN4_LAKEFILE_INVALID",
                        "excerpt": "ambiguous non-builtin interpolated string prefix in lakefile.lean",
                    }
                )
            tokens.append(("STR", decoded, start_line, start_pos, next_i))
            continue

        if ch == "«":
            start_line = line
            start_pos = i
            end_g = text.find("»", i + 1)
            if end_g == -1:
                findings.append(
                    {
                        "line": start_line,
                        "code": "LEAN4_LAKEFILE_INVALID",
                        "excerpt": "unterminated guillemet identifier in lakefile.lean",
                    }
                )
                break
            inner = text[i + 1 : end_g]
            line += inner.count("\n")
            tokens.append(("GUIL", inner, start_line, start_pos, end_g + 1))
            i = end_g + 1
            continue

        if ch == "'":
            start_line = line
            char_end = match_lean4_char_literal_end(text, i, n)
            if char_end is not None:
                line += text.count("\n", i, char_end)
                tokens.append(("CHAR", text[i:char_end], start_line, i, char_end))
                i = char_end
                continue
            tokens.append(("SYM", "'", line, i, i + 1))
            i += 1
            continue

        if ch == "#" and i + 1 < n and is_lean4_id_first(text[i + 1]):
            cmd_end = match_lean4_hash_command_end(text, i, n)
            tokens.append(("SYM", text[i:cmd_end], line, i, cmd_end))
            i = cmd_end
            continue

        if "0" <= ch <= "9":
            num_end = scan_lean4_numeric_literal_end(text, i, n)
            tokens.append(("NUM", text[i:num_end], line, i, num_end))
            i = num_end
            continue

        dot_prev = i > 0 and text[i - 1] == "."
        if ch == "r" and not dot_prev:
            j = i + 1
            while j < n and text[j] == "#":
                j += 1
            if j < n and text[j] == '"':
                start_line = line
                start_pos = i
                close_seq = '"' + ("#" * (j - (i + 1)))
                close_pos = text.find(close_seq, j + 1)
                if close_pos == -1:
                    findings.append(
                        {
                            "line": start_line,
                            "code": "LEAN4_LAKEFILE_INVALID",
                            "excerpt": "unterminated raw string literal in lakefile.lean",
                        }
                    )
                    break
                line += text.count("\n", j + 1, close_pos)
                end_pos = close_pos + len(close_seq)
                tokens.append(("STR", text[j + 1 : close_pos], start_line, start_pos, end_pos))
                i = end_pos
                continue

        if is_lean4_id_first(ch):
            w_end = i + 1
            while w_end < n and is_lean4_id_rest(text[w_end]):
                if text[w_end : w_end + 3] == "'\"'" and text[w_end - 1] in "!?":
                    break
                w_end += 1
            word = text[i:w_end]
            if not dot_prev:
                if word.endswith("!"):
                    if word[:-1] in LEAN4_INIT_RESERVED_INTERP_BANG_WORDS:
                        pending_interp = True
                    else:
                        pending_ambig_interp = True
                elif word in LEAN4_INTERP_KEYWORDS:
                    pending_ambig_interp = True
            tokens.append(("IDENT", word, line, i, w_end))
            i = w_end
            continue

        tokens.append(("SYM", ch, line, i, i + 1))
        i += 1

    if in_interp_str or interp_stack:
        findings.append(
            {
                "line": interp_line,
                "code": "LEAN4_LAKEFILE_INVALID",
                "excerpt": "unterminated interpolated string in lakefile.lean",
            }
        )

    return tokens, findings


def _is_adjacent_dot_projection(tokens: list[tuple[str, str, int, int, int]], idx: int) -> bool:
    """Return True iff `tokens[idx]` is directly adjacent to `<ident|guil|')'>.<tok>` with zero whitespace."""
    if idx < 2:
        return False
    dot = tokens[idx - 1]
    lhs = tokens[idx - 2]
    tok = tokens[idx]
    return (
        dot[0] == "SYM"
        and dot[1] == "."
        and dot[4] == tok[3]
        and lhs[4] == dot[3]
        and (lhs[0] in ("IDENT", "GUIL") or lhs[:2] == ("SYM", ")"))
    )


def parse_lakefile_lean_requires(text: str) -> dict[str, Any]:
    """
    Parse Lake DSL `require` declarations from a `lakefile.lean` payload.

    Supports all Lean 4 Lake `depName` forms:
      - `require foo ...`
      - `require «foo-bar» ...` / zero-whitespace `require«foo-bar»`
      - `require "foo-bar" ...`
      - `require "scope" / "pkg" ...`, `require "scope" / pkg ...`, `require "scope" / «pkg» ...`
      - multiline and conditional (`meta if ... then require ...`) declarations

    Ignores `--` line comments, nested `/- ... -/` (and `/--`/`/-!`) comments, regular/raw/
    interpolated strings, adjacent dot-projections (`obj.require`), and non-command declarations
    (`def require := ...`). Fails closed (`LEAN4_LAKEFILE_INVALID`) on unclosed lexemes,
    mismatched/unbalanced delimiters (`([)]`, EOF), malformed scoped/empty/bare `require`,
    build-time metaprogramming/operator/evaluation commands (`macro`, `elab`, `syntax`, `infix*`,
    `#eval`, `run_cmd`, `initialize`, `register_*`, syntax quotations `` `( ``), ambiguous
    non-builtin interpolated string prefixes, and forbidden attributes (`@[package_dep]`, `@[init]`,
    `@[term_elab]`, `@[extern]`, etc.).
    """
    text = text.removeprefix("\ufeff")
    tokens, findings = _tokenize_lakefile_lean(text)
    requires: list[dict[str, Any]] = []
    n = len(tokens)
    delim_stack: list[str] = []
    idx = 0

    while idx < n:
        kind, val, line, _spos, _epos = tokens[idx]

        # Reject raw `@[... package_dep/init/macro/term_elab/extern ...]` and `attribute [...]`.
        if (
            (kind == "SYM" and val == "@" or kind in ("IDENT", "GUIL") and val == "attribute")
            and idx + 1 < n
            and tokens[idx + 1][:2] == ("SYM", "[")
        ):
            j = idx + 2
            depth_b = 1
            while j < n and depth_b > 0:
                tk_k, tk_v, tk_ln, _ts, _te = tokens[j]
                if tk_k == "SYM" and tk_v == "[":
                    depth_b += 1
                elif tk_k == "SYM" and tk_v == "]":
                    depth_b -= 1
                elif tk_k in ("IDENT", "GUIL") and tk_v in _LEAN_LAKEFILE_FORBIDDEN_ATTRS:
                    findings.append(
                        {
                            "line": tk_ln,
                            "code": "LEAN4_LAKEFILE_INVALID",
                            "excerpt": f"disallowed {tk_v!r} attribute bypasses static lakefile require scanning",
                        }
                    )
                j += 1
            if depth_b != 0:
                findings.append(
                    {
                        "line": line,
                        "code": "LEAN4_LAKEFILE_INVALID",
                        "excerpt": "unbalanced attribute brackets in lakefile.lean",
                    }
                )
            idx = j
            continue

        # Reject syntax quotations `` `( ... ) `` at any delimiter depth (`B1`).
        if kind == "SYM" and val == "`" and idx + 1 < n and tokens[idx + 1][:2] == ("SYM", "("):
            findings.append(
                {
                    "line": line,
                    "code": "LEAN4_LAKEFILE_INVALID",
                    "excerpt": "syntax quotation '`(' is disallowed in lakefile.lean",
                }
            )
            idx += 1
            continue

        # Reject build-time evaluation hash commands (`#eval`, `#eval!`, `#run_cmd`, etc.).
        if kind == "SYM" and val in _LEAN_LAKEFILE_FORBIDDEN_HASH_CMDS:
            findings.append(
                {
                    "line": line,
                    "code": "LEAN4_LAKEFILE_INVALID",
                    "excerpt": f"disallowed build-time command {val!r} in lakefile.lean",
                }
            )
            idx += 1
            continue

        if kind == "SYM":
            if val in _DELIM_CLOSE:
                delim_stack.append(_DELIM_CLOSE[val])
            elif val in (")", "]", "}"):
                if not delim_stack or delim_stack[-1] != val:
                    findings.append(
                        {
                            "line": line,
                            "code": "LEAN4_LAKEFILE_INVALID",
                            "excerpt": f"unbalanced {val!r} delimiter in lakefile.lean",
                        }
                    )
                else:
                    delim_stack.pop()
            idx += 1
            continue

        # Reject build-time metaprogramming & custom operator commands at ANY delimiter depth (`B1`/`H2`).
        if kind == "IDENT" and (val in _LEAN_LAKEFILE_METAPROG_COMMANDS or val.startswith("register_")):
            if not _is_adjacent_dot_projection(tokens, idx):
                findings.append(
                    {
                        "line": line,
                        "code": "LEAN4_LAKEFILE_INVALID",
                        "excerpt": f"disallowed metaprogramming command {val!r} in lakefile.lean",
                    }
                )
                idx += 1
                continue

        if kind == "IDENT" and val == "require":
            is_dot_proj = _is_adjacent_dot_projection(tokens, idx)
            prev_is_decl_kw = (
                idx > 0
                and tokens[idx - 1][2] == line
                and tokens[idx - 1][0] == "IDENT"
                and tokens[idx - 1][1] in _LEAN_DECL_BEFORE_REQUIRE
                and not _is_adjacent_dot_projection(tokens, idx - 1)
            )
            is_non_cmd = is_dot_proj or prev_is_decl_kw
            nxt = tokens[idx + 1] if idx + 1 < n else None
            if not is_non_cmd and nxt is not None and nxt[0] in ("IDENT", "GUIL", "STR"):
                if nxt[0] == "STR" and idx + 2 < n and tokens[idx + 2][:2] == ("SYM", "/"):
                    if idx + 3 >= n or tokens[idx + 3][0] not in ("IDENT", "GUIL", "STR"):
                        findings.append(
                            {
                                "line": line,
                                "code": "LEAN4_LAKEFILE_INVALID",
                                "excerpt": "malformed scoped require declaration missing package name",
                            }
                        )
                        idx += 3
                        continue
                    pkg_tok = tokens[idx + 3]
                    end_idx = idx + 4
                else:
                    pkg_tok = nxt
                    end_idx = idx + 2

                pkg_name = pkg_tok[1]
                if pkg_tok[0] in ("IDENT", "GUIL"):
                    while (
                        end_idx + 1 < n
                        and tokens[end_idx][:2] == ("SYM", ".")
                        and tokens[end_idx + 1][0] in ("IDENT", "GUIL")
                    ):
                        pkg_name = f"{pkg_name}.{tokens[end_idx + 1][1]}"
                        end_idx += 2

                if not pkg_name.strip() or pkg_name != pkg_name.strip():
                    findings.append(
                        {
                            "line": line,
                            "code": "LEAN4_LAKEFILE_INVALID",
                            "excerpt": "lakefile.lean require declaration has empty or padded package name",
                        }
                    )
                else:
                    requires.append({"name": pkg_name, "line": line})
                idx = end_idx
                continue
            if not is_non_cmd and not delim_stack:
                findings.append(
                    {
                        "line": line,
                        "code": "LEAN4_LAKEFILE_INVALID",
                        "excerpt": "malformed require declaration missing package name",
                    }
                )

        idx += 1

    if delim_stack:
        findings.append(
            {
                "line": tokens[-1][2],
                "code": "LEAN4_LAKEFILE_INVALID",
                "excerpt": "unbalanced delimiters at EOF in lakefile.lean",
            }
        )

    return {"valid": len(findings) == 0, "requires": requires, "findings": findings}


def audit_lean4_lakefile(path: Path) -> dict[str, Any]:
    """Fail-closed validation and `require` extraction for a `lakefile.toml` or `lakefile.lean`."""
    try:
        st = os.lstat(path)
    except OSError as exc:
        return {
            "valid": False,
            "requires": [],
            "findings": [
                {"line": 1, "code": "LEAN4_LAKEFILE_INVALID", "excerpt": f"unreadable lakefile: {exc}"[:100]}
            ],
        }
    if not stat.S_ISREG(st.st_mode):
        return {
            "valid": False,
            "requires": [],
            "findings": [
                {"line": 1, "code": "LEAN4_LAKEFILE_INVALID", "excerpt": f"non-regular or symlinked {path.name}"[:100]}
            ],
        }
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        return {
            "valid": False,
            "requires": [],
            "findings": [
                {"line": 1, "code": "LEAN4_LAKEFILE_INVALID", "excerpt": f"invalid UTF-8/IO in {path.name}: {exc}"[:100]}
            ],
        }
    if path.suffix == ".toml":
        return parse_lakefile_toml_requires(text)
    if path.suffix == ".lean":
        return parse_lakefile_lean_requires(text)
    return {
        "valid": False,
        "requires": [],
        "findings": [
            {"line": 1, "code": "LEAN4_LAKEFILE_INVALID", "excerpt": f"unsupported lakefile extension: {path.name}"[:100]}
        ],
    }


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
    Discover and validate `lake-manifest.json`, `lakefile.{toml,lean}` (cross-checking every
    declared `require` package against sibling `lake-manifest.json`), and `*axiom*.{log,txt,out}`
    axiom-audit logs under `root` (skipping `skip_dirs` and `.lake`, never following dir symlinks).
    """
    skip = set(skip_dirs) | {".lake"}
    manifest_paths: list[Path] = []
    lakefile_paths: list[Path] = []
    axiom_log_paths: list[Path] = []
    findings: list[dict[str, Any]] = []

    if root.is_file():
        if root.name == "lake-manifest.json":
            manifest_paths.append(root)
            for lf_name in sorted(_LAKEFILE_NAMES):
                sib_lf = root.parent / lf_name
                if os.path.lexists(sib_lf):
                    lakefile_paths.append(sib_lf)
        elif root.name in _LAKEFILE_NAMES:
            lakefile_paths.append(root)
            sib_manifest = root.parent / "lake-manifest.json"
            if os.path.lexists(sib_manifest):
                manifest_paths.append(sib_manifest)
        elif _is_axiom_log_filename(root.name):
            axiom_log_paths.append(root)
        elif root.suffix == ".lean":
            sib_manifest = root.parent / "lake-manifest.json"
            if os.path.lexists(sib_manifest):
                manifest_paths.append(sib_manifest)
            for lf_name in sorted(_LAKEFILE_NAMES):
                sib_lf = root.parent / lf_name
                if os.path.lexists(sib_lf):
                    lakefile_paths.append(sib_lf)
    else:
        stack: list[Path] = [root]
        while stack:
            cur = stack.pop()
            try:
                entries = sorted(os.scandir(cur), key=lambda e: e.name)
            except OSError as exc:
                rel_dir = "." if cur == root else str(cur.relative_to(root))
                findings.append(
                    {
                        "file": rel_dir,
                        "line": 1,
                        "code": "LEAN4_LAKEFILE_INVALID",
                        "excerpt": f"unreadable directory during Lean audit: {exc}"[:100],
                    }
                )
                continue
            for entry in entries:
                name = entry.name
                p = Path(entry.path)
                if name == "lake-manifest.json":
                    manifest_paths.append(p)
                    continue
                if name in _LAKEFILE_NAMES:
                    lakefile_paths.append(p)
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if name not in skip:
                        stack.append(p)
                    continue
                if _is_axiom_log_filename(name):
                    axiom_log_paths.append(p)

    manifest_paths.sort()
    lakefile_paths.sort()
    axiom_log_paths.sort()

    manifest_by_dir: dict[Path, dict[str, Any]] = {}
    for mp in manifest_paths:
        rel = mp.name if root.is_file() else str(mp.relative_to(root))
        res = audit_lean4_lake_manifest(mp, allow_external_packages=allow_external_packages)
        manifest_by_dir[mp.parent] = res
        for f in res["findings"]:
            findings.append({"file": rel, **f})

    for lp in lakefile_paths:
        rel = lp.name if root.is_file() else str(lp.relative_to(root))
        lf_res = audit_lean4_lakefile(lp)
        for f in lf_res["findings"]:
            findings.append({"file": rel, **f})
        if lf_res["requires"]:
            mf_res = manifest_by_dir.get(lp.parent)
            if mf_res is None:
                for req in lf_res["requires"]:
                    findings.append(
                        {
                            "file": rel,
                            "line": req["line"],
                            "code": "LEAN4_LAKEFILE_MISSING_MANIFEST",
                            "excerpt": f"required package {req['name']!r} has no sibling lake-manifest.json"[:100],
                        }
                    )
            elif mf_res["package_names"] is None:
                for req in lf_res["requires"]:
                    findings.append(
                        {
                            "file": rel,
                            "line": req["line"],
                            "code": "LEAN4_LAKEFILE_UNMANIFESTED_REQUIRE",
                            "excerpt": f"required package {req['name']!r} unverified: lake-manifest.json is invalid"[:100],
                        }
                    )
            else:
                manifested = set(mf_res["package_names"])
                for req in lf_res["requires"]:
                    if req["name"] not in manifested:
                        findings.append(
                            {
                                "file": rel,
                                "line": req["line"],
                                "code": "LEAN4_LAKEFILE_UNMANIFESTED_REQUIRE",
                                "excerpt": f"required package {req['name']!r} not listed in lake-manifest.json"[:100],
                            }
                        )

    for ap in axiom_log_paths:
        rel = ap.name if root.is_file() else str(ap.relative_to(root))
        res = audit_lean4_axiom_log(ap)
        for f in res["findings"]:
            findings.append({"file": rel, **f})

    return {
        "manifests_checked": len(manifest_paths),
        "lakefiles_checked": len(lakefile_paths),
        "axiom_logs_checked": len(axiom_log_paths),
        "findings": findings,
    }
