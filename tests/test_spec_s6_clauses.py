"""
Regression tests for `Foundation-0/aletheia#11`:
Verify that `spec/LAWS_AND_GATES.md` Section 6 explicitly states both the
Plane-2 oracle-compilation ban (`plane2_oracle_compilation_forbidden: true`)
and all five autonomous ratchet clauses as standalone visible sentences:
text hidden behind comments or fenced code blocks, mid-sentence hedges, and
post-sentence tails do not satisfy them. The spec's enforcement notes must
also match what `aletheia/mde.py` and `aletheia/ratchet.py` actually check.

Follow-up `Foundation-0/aletheia#29` / PR #31: the whole of Section 6 is pinned
verbatim (`_SECTION6_CANONICAL_LINES`), so editing any line of Section 6 needs a
paired edit here; and every refusal site in `aletheia/ratchet.py` has a named
control (`aletheia mutate aletheia/ratchet.py --max-mutants 0` with this file).

Zero external dependencies. Zero bare assert statements (100% R4 parity
across `-I -B`, `-I -O -B`, and `-I -B -W error`).
"""
from __future__ import annotations

import copy
from fractions import Fraction
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia.mde import (
    build_aletheia_mde_manifest,
    compute_zone_canon_id,
    verify_aletheia_mde_manifest,
)
import aletheia.ratchet as ratchet_mod
from aletheia.ratchet import (
    RATCHET_LEDGER_SCHEMA,
    ast_canonical_digest,
    build_ratchet_record,
    check_fixed_compute_survival,
    check_ring0_lock,
    exact_pythagorean_latch_check,
    verify_ratchet_ledger_records,
)
from aletheia.strict_io import AletheiaError

SPEC_PATH = ROOT / "spec" / "LAWS_AND_GATES.md"


def _req(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _extract_section_6(spec_text: str) -> str:
    match = re.search(
        r"(?ms)^## 6\..*?(?=^## 7\.)",
        spec_text,
    )
    _req(match is not None, "Section 6 heading bounded by Section 7 not found in spec/LAWS_AND_GATES.md")
    return match.group(0) if match is not None else ""


def _raw_section_6() -> str:
    """Raw Section 6 text directly from spec/LAWS_AND_GATES.md without stripping fences or comments."""
    return _extract_section_6(SPEC_PATH.read_text(encoding="utf-8"))


def _visible_section_6(raw_section: str | None = None) -> str:
    """Section 6 text with HTML comments and fenced code blocks removed.

    Clauses hidden behind comments or fences, or stated only inside code
    samples, do not count as spec text.
    """
    section = _raw_section_6() if raw_section is None else raw_section
    without_comments = re.sub(r"<!--.*?-->", "", section, flags=re.DOTALL)
    without_backtick_fences = re.sub(
        r"(?ms)^[ \t]*```.*?^[ \t]*```[ \t]*$",
        "",
        without_comments,
    )
    without_tilde_fences = re.sub(
        r"(?ms)^[ \t]*~~~.*?^[ \t]*~~~[ \t]*$",
        "",
        without_backtick_fences,
    )
    return without_tilde_fences


_SECTION6_HEADING = "## 6. v1.1\u2013v2.0 Executable Modules & Epistemic Accounting"
_PLANE2_HEADING = (
    "4. **Plane-1 MDE Contract (`aletheia mde`, `AUDIT-027`, restored from `v1.3.0` `58207b4`, `aletheia#11`):**"
)
_RATCHET_HEADING = (
    "5. **5-Gate Autonomous Ratchet Contract (`aletheia ratchet`, `AUDIT-026R` + `AUDIT-023`, "
    "restored from `v1.3.0` `58207b4`, `aletheia#11`):**"
)

_PLANE2_LEAD_IN = "**Plane-2 Mechanical Obstruction (`plane2_oracle_compilation_forbidden: true`):**"
_PLANE2_SENTENCE = (
    "Verification oracles MUST NEVER be compiled into neural weights; "
    "Plane-2 weight adapters are strictly disposable caches subordinate to "
    "Plane-1 deterministic verification."
)
_PLANE2_CONTEXT_BULLET = (
    "An Aletheia expedition may be packaged unconditionally as a "
    "**Plane-1 Model Domain Expansion (MDE)** using deterministic `zone-canon-v0` "
    "manifest IDs, dyadic integer zone scales, content-addressed causal `AUDIT-XXX` "
    "lineage DAGs enforcing **`author != verifier`** (`SELF_AUDIT_FORBIDDEN`) and "
    "Hard Veto #2 contested-head halts (`ADJUDICATION_OMITS_HEADS`), and compact "
    "`abios`-compatible `SYM-2P/2.0-rcp` wire packets."
)
_PLANE2_ENFORCEMENT_BULLET = (
    "**Code vs. Workflow Enforcement (`aletheia/mde.py`):** "
    "`aletheia/mde.py` refuses a manifest with the flag false (`ORACLE_IN_WEIGHTS_FORBIDDEN`) "
    "or a zone with `allow_weight_oracle_compilation` true (`ORACLE_COMPILATION_ENABLED`) "
    "when a manifest is checked; there is no `mde` subcommand that checks a manifest an "
    "author supplies, so this is a stated obligation on the manifest author, backed by "
    "library functions for the author to call."
)

_RATCHET_SENTENCE = (
    "Any automated hill-climbing or autoresearch loop running under Aletheia "
    "MUST enforce: (i) immutable Ring-0 evaluation harness lock, (ii) float-free "
    "canonical hash-chained receipts, (iii) AST-identity unchanged-baseline null "
    "rejection, (iv) Pre-Adaptation Goodhart Latch halt + blind portal re-entry "
    "preserving informative failed branches, and (v) a fixed-compute `CS-08` "
    "survival cap."
)
_RATCHET_ENFORCEMENT_BULLET = (
    "**Code vs. Workflow Enforcement (`aletheia/ratchet.py`):** "
    "Clauses (i), (ii), (iii), the Pre-Adaptation Goodhart Latch halt of (iv), and (v) "
    "are stated obligations on the loop author, backed by fail-closed library functions "
    "for an enforcing loop to call: `check_ring0_lock` / `RING0_TAMPER`, "
    "`build_ratchet_record` (validating `decision` and canonical `ast_sha256` at build "
    "time) & `verify_ratchet_ledger_records` (`aletheia ratchet --verify-ledger` checks "
    "the hash chain, strict decision enum, canonical `sha256` AST digest format, and "
    "Gate-1 adjacent-baseline AST progression over declared digest strings in the "
    "submitted ledger: `BROKEN_HASH_CHAIN`, `RECORD_HASH_MISMATCH`, `INVALID_DECISION`, "
    "`INVALID_AST_DIGEST`, `AST_UNCHANGED_KEEP`, `REVERT_TO_UNKNOWN_BASELINE`, where "
    "`KEEP` updates the active baseline digest, `REVERT`'s `ast_sha256` must match a "
    "previously kept baseline and restores it as the active baseline, and `DISCARD` and "
    "`LATCH_HALT` leave the active baseline unchanged, so `KEEP A -> KEEP B -> KEEP A` "
    "is valid under adjacent-baseline progression whereas "
    "`KEEP A -> KEEP B -> REVERT A -> KEEP A` fails closed with `AST_UNCHANGED_KEEP` "
    "and `KEEP A -> REVERT B` with unkept `B` fails closed with "
    "`REVERT_TO_UNKNOWN_BASELINE`), "
    "`ast_canonical_digest` (canonical AST hash whose unchanged-baseline `KEEP` invariant "
    "is enforced on submitted ledger digests by `verify_ratchet_ledger_records` via "
    "`AST_UNCHANGED_KEEP`), `exact_pythagorean_latch_check` / `LATCH_HALT`, and "
    "`check_fixed_compute_survival` / `EXCEEDED_FIXED_COMPUTE_CAP` & "
    "`FORMAT_BREAKING_COT_ESCAPE`. No runtime supervisor forces an external loop to call "
    "clauses (i)–(v); clauses (ii) and (iii) are enforced when running `--verify-ledger` "
    "on a submitted ledger (verifying declared digest strings rather than re-parsing "
    "external source files), where any submitted ledger violating hash-chain integrity, "
    "decision/digest validity, or keeping an unchanged `ast_sha256` relative to the "
    "active baseline fails closed under `verify_ratchet_ledger_records`. Blind portal "
    "re-entry preserving informative failed branches in clause (iv) is a normative "
    "loop-orchestration discipline (`AUDIT-026R`), paired with the `LATCH_HALT` trigger "
    "rather than a standalone function in `aletheia/ratchet.py`."
)

# Items 1, 2, 3 and 6 of Section 6, copied verbatim from spec/LAWS_AND_GATES.md (non-ASCII
# characters written as escapes). Together with the item 4/5 constants above they pin the
# whole of Section 6: see `_assert_section6_exact_text`.
_SECTION6_ITEM1 = (
    '1. **Pure-$\\mathbb{Q}$ v2.0 Gate-Contract Engine (`aletheia gate-v2 --self-test`, '
    '`aletheia/gates_v2.py`):** Executable pure-$\\mathbb{Q}$ certifiers for `R6`/`R7` '
    '(registered check IDs verified against executed checks), Two-Direction `R3`, \xa74 '
    '`NOT_SHOWN`, \xa7\xa75–7 oracle/feedback rules, \xa78 Gate-8 subspace latch '
    '(`BLIND_AUDIT_IN_COL_PHI`), Law 2b Transformational Steelman (schema/inequality gate '
    'aligned with `AUDIT-088R` `T1`–`T7` IDs & `G0`–`G4` guards), and Own-Terms-First '
    '(`certify_own_terms_phase1`, `certify_own_terms_model_ladder`, '
    '`certify_own_terms_symbol_utility` — schema/inequality gates over caller-supplied '
    'records; execution provenance requires separate replay). `gate-v2 --self-test` '
    'dynamically verifies one accept and one rejection control per gate.'
)
_SECTION6_ITEM2 = (
    '2. **Deterministic Agent Safety-Surface Scanner (`aletheia safety-scan` & `aletheia '
    'audit-check --safety-scan`, `aletheia/safety.py`):** Implements `CYA-GAP-01..06` '
    '(`AUDIT-078R`): hidden Trojan-Source Unicode (`U+00AD`, `U+200B..200F`, `U+2060..2064`, '
    '`U+FEFF`, BiDi controls, variation selectors `U+FE00..FE0F`/`U+E0100..E01EF`, Tags), '
    # Split literals (as in aletheia/safety.py) keep `aletheia safety-scan` from flagging this
    # quotation of the spec as a live auto-yes / yolo / session-hook configuration.
    'unpinned MCP/`n' 'px -y` (shell + JSON/YAML)/`-' '-yolo`/`Session' 'Start`, unguarded recursive '
    'force-delete of shell/Makefile variables (YAML `run:`, `$(...)`, continuations, '
    '`xargs`, `sh -c`, Makefile `$(VAR)`; top-level non-conditional/non-heredoc `set -u` '
    'guards unset only, `${VAR:?}` guards unset and empty), `pull_request_target` + '
    'secrets/`secrets: inherit`/write/untrusted PR head checkout (dot/bracket exprs, step '
    'outputs, `pull/N/head`, `gh pr checkout`), prose-only rules & `~/` host paths (incl. '
    '`.cursorrules`), UTF-16 decoding, dotfiles/extensionless/vendor-dir scanning, '
    'fail-closed reporting of `skipped_files` (incl. non-regular files such as '
    'FIFOs/sockets/devices without blocking), `undecodable_files` (incl. '
    'binary/NUL-containing text such as UTF-32 with BOM), and `unreadable_files`, plus '
    'optional `--include-host-hygiene`.'
)
_SECTION6_ITEM3_HEADING = (
    '3. **8-Glyph Exact Operator Calculus (`aletheia calculus`, v1.3, Honest Rule-2 '
    'Accounting per `AUDIT-084R`):**'
)
_SECTION6_ITEM3_NOTATION_BULLET = (
    'Executable pure-$\\mathbb{Q}/\\mathbb{Z}$ notation (reported `0 / 227,540` Lean 4 corpus '
    'hits; the scan script and corpus are not in this repository): `⧄` (`|/|`), `⧅` (`|\\|`), '
    '`⦷` (`(||)`), `⟠` (`<=>`), `⧇` (`[o]`), `⦺` (`(+-0)`), `⩩` (`=#=`), `⫩` (`_|T`).'
)
_SECTION6_ITEM3_UTILITY_BULLET = (
    '**Honest Operational-Utility Classification (`AUDIT-084R`):** Under Own-Terms-First '
    'Rule 2, `7/8` glyphs are documented transparently as composition shorthands / renamings '
    '(`6` shorthands + overloaded `⟠`) operating on constructed exact-$\\mathbb{Q}$ objects '
    '(`0` file I/O in `calculus.py`), while `1/8` (`⫩`, mutation-tested refusal gate) is a '
    'typed execution operator (`N0` mutation-testing origin); all `6` algebraic composition '
    'probes (`C1`–`C6`) execute cleanly with zero floats.'
)
_SECTION6_ITEM6 = (
    '6. **Hardened `audit-check` & `mutate` (`aletheia/audit_check.py`, '
    '`aletheia/mutator.py`):** Includes Lean 4 raw-string `r#"..."#` safe lexing, R4 '
    '`unittest` `-O` skip detection, `from random import` AST tracking, cross-module '
    'imported wrapper discovery + `--guards` + `covered_lines`, `shapes.py`/`rule.py` '
    'refusal shapes, `selfcheck.py` constant-shift mutation, `NOT_SHOWN` truncation, and '
    '`(?!\\n)$` schema alignment.'
)

_SECTION6_BULLET = "   - "

# Every non-blank line of Section 6, in order, from the `## 6.` heading to the closing `---`.
# A change to Section 6 of the spec must update this tuple (and the constants it is built
# from) in the same pull request, so that every wording change to this binding section is
# reviewed as a paired spec + test edit.
_SECTION6_CANONICAL_LINES: tuple[str, ...] = (
    _SECTION6_HEADING,
    _SECTION6_ITEM1,
    _SECTION6_ITEM2,
    _SECTION6_ITEM3_HEADING,
    _SECTION6_BULLET + _SECTION6_ITEM3_NOTATION_BULLET,
    _SECTION6_BULLET + _SECTION6_ITEM3_UTILITY_BULLET,
    _PLANE2_HEADING,
    _SECTION6_BULLET + _PLANE2_CONTEXT_BULLET,
    f"{_SECTION6_BULLET}{_PLANE2_LEAD_IN} {_PLANE2_SENTENCE}",
    _SECTION6_BULLET + _PLANE2_ENFORCEMENT_BULLET,
    _RATCHET_HEADING,
    _SECTION6_BULLET + _RATCHET_SENTENCE,
    _SECTION6_BULLET + _RATCHET_ENFORCEMENT_BULLET,
    _SECTION6_ITEM6,
    "---",
)


def _assert_section6_exact_text(raw_section: str) -> None:
    """Whole-Section-6 exact allow-list (the binding check for every item, not only 4 and 5).

    Every non-blank line of Section 6, with its leading indentation, must equal the matching
    line of `_SECTION6_CANONICAL_LINES` after NFKC normalization; trailing whitespace is
    ignored and blank lines are skipped. Invisible format characters (Unicode category `Cf`)
    are refused before normalization. Any added, removed, reordered, or reworded heading,
    bullet, or line anywhere in Section 6 fails whatever its wording, so waiver text cannot
    be added to any item without also editing this test.
    """
    for ch in raw_section:
        if unicodedata.category(ch) == "Cf":
            raise AssertionError(f"Invisible format character U+{ord(ch):04X} forbidden in Section 6")
    got = [ln.rstrip() for ln in unicodedata.normalize("NFKC", raw_section).splitlines() if ln.strip()]
    expected = [unicodedata.normalize("NFKC", ln) for ln in _SECTION6_CANONICAL_LINES]
    for idx in range(max(len(got), len(expected))):
        got_ln = got[idx] if idx < len(got) else None
        exp_ln = expected[idx] if idx < len(expected) else None
        if got_ln != exp_ln:
            raise AssertionError(
                f"Section 6 differs from its canonical text at non-blank line {idx}: "
                f"expected {exp_ln!r}, got {got_ln!r}. Section 6 is pinned verbatim; a spec "
                "edit to it must update _SECTION6_CANONICAL_LINES in "
                "tests/test_spec_s6_clauses.py in the same change."
            )


def _enclosing_clause_block(section: str, start: int) -> str:
    """Return the enclosing numbered Section 6 item bounded only by column-0 items, headings, or `---`."""
    item_starts = [m.start() for m in re.finditer(r"(?m)^\d+\.\s", section)]
    lo = 0
    for pos in item_starts:
        if pos <= start:
            lo = pos
        else:
            break
    boundary_re = re.compile(r"(?m)^(?:\d+\.\s|#{1,6}(?:\s|$)|---[ \t]*$)")
    hi = len(section)
    for m in boundary_re.finditer(section, pos=lo + 1):
        if m.start() > start:
            hi = m.start()
            break
    return section[lo:hi]


def _extract_block_heading_and_bullets(block: str) -> tuple[str | None, list[str]]:
    """Parse numbered item heading and sub-bullets, rejecting Cf chars, headings, and non-bullet lines."""
    for ch in block:
        if unicodedata.category(ch) == "Cf":
            raise AssertionError(f"Invisible format character U+{ord(ch):04X} forbidden in Section 6 clause block")
    normalized = unicodedata.normalize("NFKC", block)
    lines = normalized.splitlines()
    heading: str | None = None
    bullets: list[str] = []
    idx = 0
    if lines and re.match(r"^\d+\.\s", lines[0]):
        heading = lines[0].strip()
        idx = 1
    while idx < len(lines):
        raw = lines[idx]
        stripped = raw.strip()
        if not stripped:
            idx += 1
            continue
        if stripped.startswith(("- ", "* ")):
            bullets.append(stripped[2:].strip())
        else:
            raise AssertionError(f"Unexpected non-bullet line inside clause block: {raw!r}")
        idx += 1
    return heading, bullets


_SECTION6_OUTSIDE_WAIVER_PATTERNS = (
    re.compile(
        r"(?i)\b(?:nothing|none)\b[^\n.;!?]*\b(?:is|are)\s+binding\b"
    ),
    re.compile(
        r"(?i)\bno\b[^\n.;!?]*\b(?:clauses?|items?|requirements?|obligations?|rules?|parts?)\b"
        r"[^\n.;!?]*\b(?:is|are)\s+binding\b"
    ),
    re.compile(
        r"(?i)\ball\s+of\s+these\s+are\s+(?:optional|guidance|recommendations?|advisory|non[-\s]?binding)\b"
    ),
    re.compile(
        r"(?i)\b(?:nothing|none|clauses?|items?|requirements?|obligations?|rules?|section)\b"
        r"[^\n.;!?]*\b(?:not\s+binding|non[-\s]?binding|optional|advisory(?:\s+only)?|"
        r"guidance(?:\s+only)?|recommendations?|not\s+requirements?|"
        r"waiv(?:e|ed|er|ing)|opt[\s-]?out|do(?:es)?\s+not\s+apply|exempt(?:ed|ion)?|"
        r"discretionary|superseded)\b"
    ),
    re.compile(
        r"(?i)\b(?:not\s+binding|non[-\s]?binding|waiv(?:e|ed|er|ing)|opt[\s-]?out|advisory(?:\s+only)?|"
        r"guidance(?:\s+only)?|recommendations?|not\s+requirements?)\b"
        r"[^\n.;!?]*\b(?:section|clauses?|items?|requirements?|obligations?|plane[-\s]?2|ratchet)\b"
    ),
    re.compile(
        r"(?i)\b(?:plane[-\s]?2|oracle\s+compilation|ratchet|items?\s*\d|clauses?\s*\(?i\)?|"
        r"this\s+section|section\s*6)\b[^\n.;!?]*\b(?:optional|waiv(?:e|ed|er|ing)|"
        r"non[-\s]?binding|not\s+binding|advisory|guidance|recommendations?|not\s+requirements?|"
        r"opt[\s-]?out|do(?:es)?\s+not\s+apply|"
        r"exempt(?:ed|ion)?|discretionary|may\s+skip|need\s+not|supersed(?:e|ed|ing))\b"
    ),
)


def _assert_no_section6_waiver_outside_clauses(raw_section: str) -> None:
    """Enforce exact Section 6 top-level item structure (1..6, no extra headings/intro prose)
    plus best-effort waiver deny-checks across the prose inside non-clause items (1-3, 6).

    The keyword deny-list misses plain rephrasings; it is kept as a second layer with
    targeted error messages. The binding check for the whole section is
    `_assert_section6_exact_text`."""
    for ch in raw_section:
        if unicodedata.category(ch) == "Cf":
            raise AssertionError(f"Invisible format character U+{ord(ch):04X} forbidden in Section 6")
    norm_section = unicodedata.normalize("NFKC", raw_section)

    # Structural lock on Section 6 outside items 4 & 5:
    # exactly heading `## 6. ...`, zero intro prose before item 1, zero extra `#` subheadings,
    # and exact numbered item sequence [1, 2, 3, 4, 5, 6] (rejects appended `7. **Scope:** ...`
    # or column-0 `#### Scope` subsections regardless of phrasing).
    sec_lines = norm_section.splitlines()
    _req(
        bool(sec_lines) and sec_lines[0].strip() == unicodedata.normalize("NFKC", _SECTION6_HEADING),
        f"Unexpected Section 6 heading: {sec_lines[0] if sec_lines else ''!r}",
    )
    seen_item_nums: list[int] = []
    for raw_ln in sec_lines[1:]:
        stripped = raw_ln.strip()
        if not stripped or stripped == "---":
            continue
        if raw_ln.startswith("#") or stripped.startswith("#"):
            raise AssertionError(f"Unexpected heading line inside Section 6: {raw_ln!r}")
        m_num = re.match(r"^(\d+)\.\s", raw_ln)
        if m_num is not None:
            seen_item_nums.append(int(m_num.group(1)))
            continue
        if not seen_item_nums:
            raise AssertionError(f"Unexpected prose before Section 6 item 1: {raw_ln!r}")
    _req(
        seen_item_nums == [1, 2, 3, 4, 5, 6],
        f"Unexpected Section 6 numbered item structure: got {seen_item_nums!r}, expected [1, 2, 3, 4, 5, 6]",
    )

    remainder = norm_section
    for sentence in (_PLANE2_SENTENCE, _RATCHET_SENTENCE):
        norm_s = unicodedata.normalize("NFKC", sentence)
        pos = remainder.find(norm_s)
        if pos != -1:
            block = _enclosing_clause_block(remainder, pos)
            remainder = remainder.replace(block, "\n", 1)
    for line in remainder.splitlines():
        for rx in _SECTION6_OUTSIDE_WAIVER_PATTERNS:
            if rx.search(line) is not None:
                raise AssertionError(
                    f"Waiver or non-binding override forbidden in Section 6 outside clause blocks: {line!r}"
                )


def _assert_exact_obligation_clause(
    raw_section: str,
    sentence: str,
    *,
    expected_heading: str | None = None,
    lead_in: str = "",
    allowed_block_bullets: tuple[str, ...] | None = None,
) -> None:
    """Raw-block fence/comment/Cf/heading rejection + NFKC whole-heading & whole-block allow-list check."""
    for ch in raw_section:
        if unicodedata.category(ch) == "Cf":
            raise AssertionError(f"Invisible format character U+{ord(ch):04X} forbidden in Section 6")
    norm_section = unicodedata.normalize("NFKC", raw_section)
    norm_sentence = unicodedata.normalize("NFKC", sentence)
    expected_bullet = f"{unicodedata.normalize('NFKC', lead_in)} {norm_sentence}" if lead_in else norm_sentence

    start = norm_section.find(norm_sentence)
    _req(start != -1, f"Required sentence missing from Section 6 text: {sentence!r}")
    clause_block = _enclosing_clause_block(norm_section, start)
    if "```" in clause_block or "~~~" in clause_block:
        raise AssertionError(f"Markdown code fence forbidden inside Section 6 clause block: {clause_block!r}")
    if "<!--" in clause_block or "-->" in clause_block:
        raise AssertionError(f"HTML comment forbidden inside Section 6 clause block: {clause_block!r}")

    heading, bullets = _extract_block_heading_and_bullets(clause_block)
    if expected_heading is not None:
        _req(
            heading == unicodedata.normalize("NFKC", expected_heading),
            f"Clause item heading does not match exact canonical text: got {heading!r}",
        )
    _req(
        expected_bullet in bullets,
        f"Obligation bullet does not match exact canonical text (pre-sentence, trailing, or altered text): {bullets!r}",
    )
    if allowed_block_bullets is not None:
        expected_all = [unicodedata.normalize("NFKC", b) for b in allowed_block_bullets]
        _req(
            bullets == expected_all,
            f"Clause block contains unexpected, missing, or added bullets: got {bullets!r}",
        )


def _forge_ratchet_record(
    *,
    step: int,
    prev_hash: str,
    decision: object,
    ast_sha256: object,
    wall_ms: int,
    proxy_num: int,
    proxy_den: int,
    outside_num: int,
    outside_den: int,
    note: str,
) -> dict[str, object]:
    """Construct a validly hash-signed ratchet record bypassing build_ratchet_record validation."""
    body: dict[str, object] = {
        "schema": RATCHET_LEDGER_SCHEMA,
        "step": step,
        "prev_hash": prev_hash,
        "decision": decision,
        "ast_sha256": ast_sha256,
        "wall_ms": wall_ms,
        "proxy_num": proxy_num,
        "proxy_den": proxy_den,
        "outside_num": outside_num,
        "outside_den": outside_den,
        "note": note,
    }
    body["record_hash"] = compute_zone_canon_id(body, exclude_key="record_hash")
    return body


class TestSpecSection6Clauses(unittest.TestCase):
    def test_spec_section6_restores_plane2_ban_and_ratchet_clauses(self) -> None:
        raw_section_6 = _raw_section_6()
        section_6 = _visible_section_6(raw_section_6)

        # Restored obligations must match exact canonical heading, whole-bullet, and whole-block allow-lists
        # on the RAW enclosing item (before any fence or comment stripping).
        _assert_exact_obligation_clause(
            raw_section_6,
            _PLANE2_SENTENCE,
            expected_heading=_PLANE2_HEADING,
            lead_in=_PLANE2_LEAD_IN,
            allowed_block_bullets=(
                _PLANE2_CONTEXT_BULLET,
                f"{_PLANE2_LEAD_IN} {_PLANE2_SENTENCE}",
                _PLANE2_ENFORCEMENT_BULLET,
            ),
        )
        _assert_exact_obligation_clause(
            raw_section_6,
            _RATCHET_SENTENCE,
            expected_heading=_RATCHET_HEADING,
            allowed_block_bullets=(
                _RATCHET_SENTENCE,
                _RATCHET_ENFORCEMENT_BULLET,
            ),
        )
        _assert_no_section6_waiver_outside_clauses(raw_section_6)
        # Binding check: the whole of Section 6 (every item, heading and bullet) is pinned verbatim.
        _assert_section6_exact_text(raw_section_6)

        required_visible_phrases = (
            # Plane-2 ban key (restored verbatim from v1.3.0 58207b4)
            "plane2_oracle_compilation_forbidden: true",
            # Enforcement notes must state what the code actually checks
            "when a manifest is checked",
            "for an enforcing loop to call",
            "INVALID_DECISION",
            "INVALID_AST_DIGEST",
            "AST_UNCHANGED_KEEP",
            "REVERT_TO_UNKNOWN_BASELINE",
            "declared digest strings",
            "clauses (i)\u2013(v)",
            # Existing v2.0.0 Section 6 items preserved intact
            "aletheia/gates_v2.py",
            "aletheia/safety.py",
            "aletheia calculus",
            "aletheia/audit_check.py",
        )
        for phrase in required_visible_phrases:
            _req(phrase in section_6, f"Missing required Section 6 clause in visible spec/LAWS_AND_GATES.md text: {phrase!r}")

    def test_spec_clause_boundary_rejects_contradicting_tails_and_waivers(self) -> None:
        """Regression tests for exact clause-block heading/bullet allow-list, raw fence/comment/heading rejection, and Section 6 waiver checks."""
        raw_section_6 = _raw_section_6()
        plane2_allowed = (
            _PLANE2_CONTEXT_BULLET,
            f"{_PLANE2_LEAD_IN} {_PLANE2_SENTENCE}",
            _PLANE2_ENFORCEMENT_BULLET,
        )
        ratchet_allowed = (_RATCHET_SENTENCE, _RATCHET_ENFORCEMENT_BULLET)

        # All #29 same-line tails, heading-line tails, pre-sentence hedges, continuation lines,
        # `#` headings inside clause blocks, fenced code blocks, HTML comments, zero-width Cf chars,
        # and arbitrary rephrased waiver bullets MUST fail closed.
        bad_mutations = (
            # Exact #29 trailing sentences
            (_PLANE2_SENTENCE, _PLANE2_SENTENCE + " Unless the owner waives this.", _PLANE2_HEADING, _PLANE2_LEAD_IN, plane2_allowed),
            (_RATCHET_SENTENCE, _RATCHET_SENTENCE + " All of these are optional.", _RATCHET_HEADING, "", ratchet_allowed),
            (_PLANE2_SENTENCE, _PLANE2_SENTENCE + " This does not apply to adapters.", _PLANE2_HEADING, _PLANE2_LEAD_IN, plane2_allowed),
            # Arbitrary pre-sentence contradiction
            (_PLANE2_SENTENCE, "Adapters are excluded. " + _PLANE2_SENTENCE, _PLANE2_HEADING, _PLANE2_LEAD_IN, plane2_allowed),
            (_RATCHET_SENTENCE, "In advisory mode only. " + _RATCHET_SENTENCE, _RATCHET_HEADING, "", ratchet_allowed),
            # Neutral same-line trailing prose
            (_PLANE2_SENTENCE, _PLANE2_SENTENCE + " Additional prose on the same line.", _PLANE2_HEADING, _PLANE2_LEAD_IN, plane2_allowed),
            (_RATCHET_SENTENCE, _RATCHET_SENTENCE + " Additional prose on the same line.", _RATCHET_HEADING, "", ratchet_allowed),
            # Same-paragraph continuation line
            (_RATCHET_SENTENCE, _RATCHET_SENTENCE + "\n   Continuing the same paragraph without a bullet.", _RATCHET_HEADING, "", ratchet_allowed),
            # Indented `#` / `#### Scope` headings inside clause block (must NOT break early!)
            (_RATCHET_ENFORCEMENT_BULLET, _RATCHET_ENFORCEMENT_BULLET + "\n   #### Scope\n   All of these are optional.", _RATCHET_HEADING, "", ratchet_allowed),
            (_RATCHET_ENFORCEMENT_BULLET, _RATCHET_ENFORCEMENT_BULLET + "\n   #\n   Clauses (i)-(v) of this item are optional and not binding.", _RATCHET_HEADING, "", ratchet_allowed),
            (_PLANE2_ENFORCEMENT_BULLET, _PLANE2_ENFORCEMENT_BULLET + "\n   ### Note\n   Unless the owner waives this.", _PLANE2_HEADING, _PLANE2_LEAD_IN, plane2_allowed),
            # Numbered heading-line tail waivers
            (_RATCHET_HEADING, _RATCHET_HEADING + " All clauses below are optional and not binding.", _RATCHET_HEADING, "", ratchet_allowed),
            (_PLANE2_HEADING, _PLANE2_HEADING + " The Plane-2 ban below is waived for adapters.", _PLANE2_HEADING, _PLANE2_LEAD_IN, plane2_allowed),
            # Fenced code blocks inside clause block (backtick & tilde fences)
            (_RATCHET_SENTENCE, _RATCHET_SENTENCE + "\n   ```\n   All of these are optional.\n   ```", _RATCHET_HEADING, "", ratchet_allowed),
            (_PLANE2_SENTENCE, _PLANE2_SENTENCE + "\n   ```\n   Unless the owner waives this.\n   ```", _PLANE2_HEADING, _PLANE2_LEAD_IN, plane2_allowed),
            (_RATCHET_SENTENCE, _RATCHET_SENTENCE + "\n   ~~~\n   All of these are optional.\n   ~~~", _RATCHET_HEADING, "", ratchet_allowed),
            # HTML comments inside clause block (block & inline)
            (_PLANE2_SENTENCE, _PLANE2_SENTENCE + "\n   <!-- Unless the owner waives this. -->", _PLANE2_HEADING, _PLANE2_LEAD_IN, plane2_allowed),
            (_RATCHET_SENTENCE, _RATCHET_SENTENCE + " <!-- optional -->", _RATCHET_HEADING, "", ratchet_allowed),
            # Rephrased added waiver bullets with ZERO classic deny-list words
            (_PLANE2_SENTENCE, _PLANE2_SENTENCE + "\n   - Non-binding guidance only.", _PLANE2_HEADING, _PLANE2_LEAD_IN, plane2_allowed),
            (_RATCHET_SENTENCE, _RATCHET_SENTENCE + "\n   - Waiving these requirements is permitted.", _RATCHET_HEADING, "", ratchet_allowed),
            (_RATCHET_SENTENCE, _RATCHET_SENTENCE + "\n   - Teams may opt out.", _RATCHET_HEADING, "", ratchet_allowed),
            # Invisible zero-width format character (Cf) smuggling
            (_PLANE2_SENTENCE, _PLANE2_SENTENCE + "\u200b", _PLANE2_HEADING, _PLANE2_LEAD_IN, plane2_allowed),
        )
        for target_text, replacement, exp_heading, lead_in, allowed in bad_mutations:
            mutated = raw_section_6.replace(target_text, replacement, 1)
            _req(mutated != raw_section_6, f"Test setup failed to mutate target: {target_text!r}")
            check_sentence = _PLANE2_SENTENCE if exp_heading == _PLANE2_HEADING else _RATCHET_SENTENCE
            try:
                _assert_exact_obligation_clause(
                    mutated,
                    check_sentence,
                    expected_heading=exp_heading,
                    lead_in=lead_in,
                    allowed_block_bullets=allowed,
                )
            except AssertionError:
                pass
            else:
                raise AssertionError(f"Tampered clause was not rejected: {replacement!r}")

        # Section-wide waiver overrides, extra numbered items, and column-0 subheadings outside items 4 & 5 MUST fail closed
        outside_waiver_mutations = (
            raw_section_6.replace(
                "## 6. v1.1\u2013v2.0 Executable Modules & Epistemic Accounting\n",
                "## 6. v1.1\u2013v2.0 Executable Modules & Epistemic Accounting\n\nNothing in this section is binding.\n",
                1,
            ),
            raw_section_6.replace(
                "schema alignment.\n",
                "schema alignment.\n   - Clauses (i)-(v) of item 5 and the Plane-2 ban are optional.\n",
                1,
            ),
            raw_section_6.replace(
                "schema alignment.\n",
                "schema alignment.\n7. **Scope:** Items 4 and 5 above are recommendations, not requirements.\n",
                1,
            ),
            raw_section_6.replace(
                "schema alignment.\n",
                "schema alignment.\n7. **Scope:** The ratchet and Plane-2 text above is guidance only.\n",
                1,
            ),
            raw_section_6.replace(
                "schema alignment.\n",
                "schema alignment.\n   - Items 4 and 5 above are recommendations, not requirements.\n",
                1,
            ),
            raw_section_6.replace(
                "schema alignment.\n",
                "schema alignment.\n   - The ratchet and Plane-2 text above is guidance only.\n",
                1,
            ),
            raw_section_6.replace(
                "schema alignment.\n",
                "schema alignment.\n#### Scope\nAll of these are optional.\n",
                1,
            ),
            raw_section_6.replace(
                "schema alignment.\n",
                "schema alignment.\n   ```\n   Clauses (i)-(v) of item 5 are optional.\n   ```\n",
                1,
            ),
        )
        for mutated_s6 in outside_waiver_mutations:
            _req(mutated_s6 != raw_section_6, "Test setup failed to mutate Section 6 outside clause blocks")
            try:
                _assert_no_section6_waiver_outside_clauses(mutated_s6)
            except AssertionError:
                pass
            else:
                raise AssertionError(f"Section-6 outside waiver was not rejected: {mutated_s6[-160:]!r}")

        # Whole-Section-6 exact allow-list: keyword-free rephrasings outside items 4 & 5
        # (the four PR #31 review shapes that passed the deny-list at 86373326), plus
        # reordered/removed lines, MUST fail closed.
        item3_utility_line = _SECTION6_BULLET + _SECTION6_ITEM3_UTILITY_BULLET + "\n"
        item3_notation_line = _SECTION6_BULLET + _SECTION6_ITEM3_NOTATION_BULLET + "\n"
        item6_line = _SECTION6_ITEM6 + "\n"
        exact_text_mutations = (
            # Bullet in item 3
            raw_section_6.replace(
                item3_utility_line,
                item3_utility_line + "   - Compliance with the MDE and ratchet contracts is voluntary.\n",
                1,
            ),
            # Bullets in item 6
            raw_section_6.replace(item6_line, item6_line + "   - Loops may skip the ratchet clauses above.\n", 1),
            raw_section_6.replace(item6_line, item6_line + "   - The Plane-2 obstruction is suspended for adapters.\n", 1),
            # Text appended to item 2's heading line
            raw_section_6.replace(_SECTION6_ITEM2, _SECTION6_ITEM2 + " Loops need not honour item 5.", 1),
            # Text appended to item 1 and item 3's heading lines
            raw_section_6.replace(_SECTION6_ITEM1, _SECTION6_ITEM1 + " Items 4 and 5 bind no one.", 1),
            raw_section_6.replace(_SECTION6_ITEM3_HEADING, _SECTION6_ITEM3_HEADING + " Item 5 is aspirational.", 1),
            # Indented continuation line under item 6, and a line between `---` and `## 7.`
            raw_section_6.replace(item6_line, item6_line + "   Adapters can ignore item 4.\n", 1),
            raw_section_6.replace("\n---\n", "\n---\n\nLoops may treat items 4 and 5 as background reading.\n", 1),
            # Reordered and removed bullets in item 3
            raw_section_6.replace(item3_notation_line + item3_utility_line, item3_utility_line + item3_notation_line, 1),
            raw_section_6.replace(item3_notation_line, "", 1),
            # Removed closing `---`
            raw_section_6.replace("\n---\n", "\n", 1),
        )
        for mutated_s6 in exact_text_mutations:
            _req(mutated_s6 != raw_section_6, "Test setup failed to mutate Section 6 for the exact allow-list")
            try:
                _assert_section6_exact_text(mutated_s6)
            except AssertionError:
                pass
            else:
                raise AssertionError(f"Section-6 exact allow-list accepted altered text: {mutated_s6[-200:]!r}")

        # The exact allow-list also subsumes every earlier clause-block and outside-waiver mutation
        for target_text, replacement, _exp_heading, _lead_in, _allowed in bad_mutations:
            mutated = raw_section_6.replace(target_text, replacement, 1)
            try:
                _assert_section6_exact_text(mutated)
            except AssertionError:
                pass
            else:
                raise AssertionError(f"Section-6 exact allow-list accepted clause-block mutation: {replacement!r}")
        for mutated_s6 in outside_waiver_mutations:
            try:
                _assert_section6_exact_text(mutated_s6)
            except AssertionError:
                pass
            else:
                raise AssertionError(f"Section-6 exact allow-list accepted outside mutation: {mutated_s6[-160:]!r}")

        # Positive controls: the canonical lines pass with different blank-line layout and trailing spaces
        _assert_section6_exact_text("\n\n".join(_SECTION6_CANONICAL_LINES) + "\n")
        _assert_section6_exact_text("\n".join(ln + "  " for ln in _SECTION6_CANONICAL_LINES))

        # Positive controls: clean standalone clause block (bounded by column-0 `### Next`) passes
        _assert_exact_obligation_clause(
            f"4. **Clause:**\n   - {_PLANE2_LEAD_IN} {_PLANE2_SENTENCE}\n\n### Next",
            _PLANE2_SENTENCE,
            expected_heading="4. **Clause:**",
            lead_in=_PLANE2_LEAD_IN,
            allowed_block_bullets=(f"{_PLANE2_LEAD_IN} {_PLANE2_SENTENCE}",),
        )

    def test_mde_code_enforces_plane2_ban_fail_closed(self) -> None:
        manifest = build_aletheia_mde_manifest()
        _req(
            manifest.get("plane2_oracle_compilation_forbidden") is True,
            "Canonical MDE manifest must pin plane2_oracle_compilation_forbidden=True",
        )
        for zone in manifest["zones"]:
            _req(
                zone["protection_flags"].get("allow_weight_oracle_compilation") is False,
                f"Zone {zone['zone']!r} must forbid allow_weight_oracle_compilation",
            )
        verified_id = verify_aletheia_mde_manifest(manifest)
        _req(verified_id == manifest["manifest_id"], "Canonical MDE manifest failed verification")

        # Negative control 1: top-level Plane-2 flag tampered (with re-signed manifest_id)
        tampered_top = copy.deepcopy(manifest)
        tampered_top["plane2_oracle_compilation_forbidden"] = False
        tampered_top["manifest_id"] = compute_zone_canon_id(tampered_top)
        try:
            verify_aletheia_mde_manifest(tampered_top)
        except AletheiaError as exc:
            _req(exc.code == "ORACLE_IN_WEIGHTS_FORBIDDEN", f"Unexpected error code: {exc.code}")
        else:
            raise AssertionError("Manifest with plane2_oracle_compilation_forbidden=False was not rejected")

        # Negative control 2: per-zone oracle compilation enabled (with re-signed manifest_id)
        tampered_zone = copy.deepcopy(manifest)
        tampered_zone["zones"][0]["protection_flags"]["allow_weight_oracle_compilation"] = True
        tampered_zone["manifest_id"] = compute_zone_canon_id(tampered_zone)
        try:
            verify_aletheia_mde_manifest(tampered_zone)
        except AletheiaError as exc:
            _req(exc.code == "ORACLE_COMPILATION_ENABLED", f"Unexpected error code: {exc.code}")
        else:
            raise AssertionError("Manifest with zone allow_weight_oracle_compilation=True was not rejected")

    def test_ratchet_code_enforces_clauses_fail_closed(self) -> None:
        # (i) Immutable Ring-0 harness lock
        base_cfg = {"oracle": "exact_v1", "gates": "r1_r7", "lr": 1}
        _req(
            check_ring0_lock(base_cfg, {"oracle": "exact_v1", "gates": "r1_r7", "lr": 2}) is True,
            "Ring-0 lock rejected valid non-Ring-0 update",
        )
        try:
            check_ring0_lock(base_cfg, {"oracle": "approx", "gates": "r1_r7", "lr": 1})
        except AletheiaError as exc:
            _req(exc.code == "RING0_TAMPER", f"Unexpected Ring-0 error code: {exc.code}")
        else:
            raise AssertionError("Ring-0 tamper was not rejected")

        # (iii) AST-identity unchanged-baseline null rejection
        d_base = ast_canonical_digest("def f(x):\n    return x + 1\n")
        d_comment = ast_canonical_digest("def f(x):\n    # no-op comment\n    return x + 1\n")
        d_changed = ast_canonical_digest("def f(x):\n    return x + 2\n")
        _req(d_base == d_comment, "AST-identical comment edit must produce identical digest")
        _req(d_base != d_changed, "Semantic edit must produce distinct AST digest")

        # (ii) Float-free canonical hash-chained receipts
        genesis = "sha256:" + ("0" * 64)
        rec0 = build_ratchet_record(
            step=0,
            prev_hash=genesis,
            decision="LATCH_HALT",
            ast_sha256=d_base,
            wall_ms=100,
            proxy_num=0,
            proxy_den=1,
            outside_num=144,
            outside_den=1,
            note="halt",
        )
        rec1 = build_ratchet_record(
            step=1,
            prev_hash=rec0["record_hash"],
            decision="KEEP",
            ast_sha256=d_changed,
            wall_ms=200,
            proxy_num=0,
            proxy_den=1,
            outside_num=0,
            outside_den=1,
            note="keep",
        )
        ver = verify_ratchet_ledger_records([rec0, rec1])
        _req(ver["valid"] is True and ver["record_count"] == 2, f"Valid ledger failed: {ver}")

        bad_hash = dict(rec1, note="tampered")
        try:
            verify_ratchet_ledger_records([rec0, bad_hash])
        except AletheiaError as exc:
            _req(exc.code == "RECORD_HASH_MISMATCH", f"Unexpected tamper error code: {exc.code}")
        else:
            raise AssertionError("Tampered ratchet record was not rejected")

        broken_chain = build_ratchet_record(
            step=1,
            prev_hash=genesis,
            decision="KEEP",
            ast_sha256=d_changed,
            wall_ms=200,
            proxy_num=0,
            proxy_den=1,
            outside_num=0,
            outside_den=1,
            note="broken",
        )
        try:
            verify_ratchet_ledger_records([rec0, broken_chain])
        except AletheiaError as exc:
            _req(exc.code == "BROKEN_HASH_CHAIN", f"Unexpected chain error code: {exc.code}")
        else:
            raise AssertionError("Broken ratchet hash chain was not rejected")

        # (iv) Exact Fraction Pre-Adaptation Goodhart Latch
        halt = exact_pythagorean_latch_check(
            proxy_before=Fraction(36, 1),
            proxy_after=Fraction(0, 1),
            outside_before=Fraction(0, 1),
            outside_after=Fraction(144, 1),
        )
        _req(halt["decision"] == "LATCH_HALT", f"Expected LATCH_HALT, got {halt}")
        keep = exact_pythagorean_latch_check(
            proxy_before=Fraction(36, 1),
            proxy_after=Fraction(0, 1),
            outside_before=Fraction(0, 1),
            outside_after=Fraction(0, 1),
        )
        _req(keep["decision"] == "KEEP", f"Expected KEEP, got {keep}")

        # (v) Fixed-compute CS-08 survival cap
        ok_cap = check_fixed_compute_survival(wall_ms=1000, max_wall_ms=30000, format_valid=True)
        _req(ok_cap["admitted"] is True and ok_cap["reason"] == "ADMITTED", f"Valid arm rejected: {ok_cap}")
        over_cap = check_fixed_compute_survival(wall_ms=30001, max_wall_ms=30000, format_valid=True)
        _req(
            over_cap["admitted"] is False and over_cap["reason"] == "EXCEEDED_FIXED_COMPUTE_CAP",
            f"Over-cap arm not rejected: {over_cap}",
        )
        bad_fmt = check_fixed_compute_survival(wall_ms=1000, max_wall_ms=30000, format_valid=False)
        _req(
            bad_fmt["admitted"] is False and bad_fmt["reason"] == "FORMAT_BREAKING_COT_ESCAPE",
            f"Format-breaking arm not rejected: {bad_fmt}",
        )

    def test_ratchet_ledger_rejects_unchanged_ast_across_keep_steps(self) -> None:
        """Regression tests for `Foundation-0/aletheia#29` Gap 2 (`AST_UNCHANGED_KEEP`)."""
        genesis = "sha256:" + ("0" * 64)
        d1 = ast_canonical_digest("def f(x):\n    return x + 1\n")
        d2 = ast_canonical_digest("def f(x):\n    return x + 2\n")
        d3 = ast_canonical_digest("def f(x):\n    return x + 3\n")
        kw = dict(wall_ms=10 ** 9, proxy_num=0, proxy_den=1, outside_num=999, outside_den=1)

        # Baseline step=0 KEEP is valid on its own
        r0 = build_ratchet_record(step=0, prev_hash=genesis, decision="KEEP", note="k0", ast_sha256=d1, **kw)
        ver0 = verify_ratchet_ledger_records([r0])
        _req(ver0["valid"] is True and ver0["status"] == "VALID", f"Baseline KEEP rejected: {ver0}")

        # Exact `@orda-aska` repro: r0(KEEP, d1) + same(KEEP, d1) MUST fail with AST_UNCHANGED_KEEP
        same = build_ratchet_record(step=1, prev_hash=r0["record_hash"], decision="KEEP", note="k2", ast_sha256=d1, **kw)
        try:
            verify_ratchet_ledger_records([r0, same])
        except AletheiaError as exc:
            _req(exc.code == "AST_UNCHANGED_KEEP", f"Expected AST_UNCHANGED_KEEP, got {exc.code}")
        else:
            raise AssertionError("KEEP->KEEP with unchanged ast_sha256 was not rejected")

        # Exact `@orda-aska` positive control: r0(KEEP, d1) + diff(KEEP, d2) MUST pass
        diff = build_ratchet_record(step=1, prev_hash=r0["record_hash"], decision="KEEP", note="k2", ast_sha256=d2, **kw)
        ver_diff = verify_ratchet_ledger_records([r0, diff])
        _req(ver_diff["valid"] is True and ver_diff["status"] == "VALID", f"Valid KEEP->KEEP diff rejected: {ver_diff}")

        # Tracking updates last_kept_ast: KEEP(d1) -> KEEP(d2) -> KEEP(d2) MUST fail with AST_UNCHANGED_KEEP
        same_after_diff = build_ratchet_record(
            step=2, prev_hash=diff["record_hash"], decision="KEEP", note="k3", ast_sha256=d2, **kw,
        )
        try:
            verify_ratchet_ledger_records([r0, diff, same_after_diff])
        except AletheiaError as exc:
            _req(exc.code == "AST_UNCHANGED_KEEP", f"Expected AST_UNCHANGED_KEEP on step 2, got {exc.code}")
        else:
            raise AssertionError("KEEP(d1)->KEEP(d2)->KEEP(d2) was not rejected")

        # KEEP(d1) -> DISCARD(d1) -> KEEP(d1) MUST fail with AST_UNCHANGED_KEEP
        disc_same = build_ratchet_record(
            step=1, prev_hash=r0["record_hash"], decision="DISCARD", note="d1", ast_sha256=d1, **kw,
        )
        keep_after_disc_same = build_ratchet_record(
            step=2, prev_hash=disc_same["record_hash"], decision="KEEP", note="k2", ast_sha256=d1, **kw,
        )
        try:
            verify_ratchet_ledger_records([r0, disc_same, keep_after_disc_same])
        except AletheiaError as exc:
            _req(exc.code == "AST_UNCHANGED_KEEP", f"Expected AST_UNCHANGED_KEEP across DISCARD, got {exc.code}")
        else:
            raise AssertionError("KEEP(d1)->DISCARD(d1)->KEEP(d1) was not rejected")

        # KEEP(d1) -> DISCARD(d2) -> KEEP(d2) MUST pass (DISCARD does not block a changed KEEP)
        disc_diff = build_ratchet_record(
            step=1, prev_hash=r0["record_hash"], decision="DISCARD", note="d2", ast_sha256=d2, **kw,
        )
        keep_after_disc_diff = build_ratchet_record(
            step=2, prev_hash=disc_diff["record_hash"], decision="KEEP", note="k2", ast_sha256=d2, **kw,
        )
        ver_dk = verify_ratchet_ledger_records([r0, disc_diff, keep_after_disc_diff])
        _req(ver_dk["valid"] is True and ver_dk["status"] == "VALID", f"Valid KEEP->DISCARD(diff)->KEEP(diff) rejected: {ver_dk}")

        # KEEP(d1) -> DISCARD(d2) -> KEEP(d1) MUST fail (DISCARD does not change active baseline)
        keep_d1_after_disc_d2 = build_ratchet_record(
            step=2, prev_hash=disc_diff["record_hash"], decision="KEEP", note="k1_again", ast_sha256=d1, **kw,
        )
        try:
            verify_ratchet_ledger_records([r0, disc_diff, keep_d1_after_disc_d2])
        except AletheiaError as exc:
            _req(exc.code == "AST_UNCHANGED_KEEP", f"Expected AST_UNCHANGED_KEEP after DISCARD(d2), got {exc.code}")
        else:
            raise AssertionError("KEEP(d1)->DISCARD(d2)->KEEP(d1) was not rejected")

        # KEEP(d1) -> LATCH_HALT(d2) -> KEEP(d1) MUST fail (LATCH_HALT does not change active baseline)
        halt_diff = build_ratchet_record(
            step=1, prev_hash=r0["record_hash"], decision="LATCH_HALT", note="h2", ast_sha256=d2, **kw,
        )
        keep_d1_after_halt_d2 = build_ratchet_record(
            step=2, prev_hash=halt_diff["record_hash"], decision="KEEP", note="k1_after_halt", ast_sha256=d1, **kw,
        )
        try:
            verify_ratchet_ledger_records([r0, halt_diff, keep_d1_after_halt_d2])
        except AletheiaError as exc:
            _req(exc.code == "AST_UNCHANGED_KEEP", f"Expected AST_UNCHANGED_KEEP after LATCH_HALT(d2), got {exc.code}")
        else:
            raise AssertionError("KEEP(d1)->LATCH_HALT(d2)->KEEP(d1) was not rejected")

        # Adjacent-baseline A -> B -> A progression: KEEP(d1) -> KEEP(d2) -> KEEP(d1) MUST pass
        keep_back_to_d1 = build_ratchet_record(
            step=2, prev_hash=diff["record_hash"], decision="KEEP", note="k_aba", ast_sha256=d1, **kw,
        )
        ver_aba = verify_ratchet_ledger_records([r0, diff, keep_back_to_d1])
        _req(ver_aba["valid"] is True and ver_aba["status"] == "VALID", f"Valid A->B->A progression rejected: {ver_aba}")

        # REVERT updates active baseline to a previously kept digest:
        # KEEP(d1) -> KEEP(d2) -> REVERT(d1) -> KEEP(d1) MUST fail with AST_UNCHANGED_KEEP
        rev_to_d1 = build_ratchet_record(
            step=2, prev_hash=diff["record_hash"], decision="REVERT", note="rev_d1", ast_sha256=d1, **kw,
        )
        keep_same_after_rev = build_ratchet_record(
            step=3, prev_hash=rev_to_d1["record_hash"], decision="KEEP", note="k_same_rev", ast_sha256=d1, **kw,
        )
        try:
            verify_ratchet_ledger_records([r0, diff, rev_to_d1, keep_same_after_rev])
        except AletheiaError as exc:
            _req(exc.code == "AST_UNCHANGED_KEEP", f"Expected AST_UNCHANGED_KEEP after REVERT(d1), got {exc.code}")
        else:
            raise AssertionError("KEEP(d1)->KEEP(d2)->REVERT(d1)->KEEP(d1) was not rejected")

        # KEEP(d1) -> KEEP(d2) -> REVERT(d1) -> KEEP(d2) MUST pass (changes away from reverted baseline d1)
        keep_diff_after_rev = build_ratchet_record(
            step=3, prev_hash=rev_to_d1["record_hash"], decision="KEEP", note="k_diff_rev", ast_sha256=d2, **kw,
        )
        ver_rev_ok = verify_ratchet_ledger_records([r0, diff, rev_to_d1, keep_diff_after_rev])
        _req(ver_rev_ok["valid"] is True and ver_rev_ok["status"] == "VALID", f"Valid post-REVERT KEEP rejected: {ver_rev_ok}")

        # REVERT to an unkept digest MUST fail closed with REVERT_TO_UNKNOWN_BASELINE
        # (blocks `KEEP(d1) -> REVERT(d2) -> KEEP(d1)` masquerading an unchanged KEEP)
        rev_unkept_d2 = build_ratchet_record(
            step=1, prev_hash=r0["record_hash"], decision="REVERT", note="rev_unkept", ast_sha256=d2, **kw,
        )
        keep_d1_after_unkept_rev = build_ratchet_record(
            step=2, prev_hash=rev_unkept_d2["record_hash"], decision="KEEP", note="k1_smuggle", ast_sha256=d1, **kw,
        )
        try:
            verify_ratchet_ledger_records([r0, rev_unkept_d2, keep_d1_after_unkept_rev])
        except AletheiaError as exc:
            _req(exc.code == "REVERT_TO_UNKNOWN_BASELINE", f"Expected REVERT_TO_UNKNOWN_BASELINE for unkept REVERT(d2), got {exc.code}")
        else:
            raise AssertionError("KEEP(d1)->REVERT(d2)->KEEP(d1) with unkept d2 was not rejected")

        # Consecutive DISCARD/LATCH_HALT with identical ast_sha256 remain valid, while REVERT before any KEEP fails
        disc0 = build_ratchet_record(step=0, prev_hash=genesis, decision="DISCARD", note="d0", ast_sha256=d1, **kw)
        halt1 = build_ratchet_record(step=1, prev_hash=disc0["record_hash"], decision="LATCH_HALT", note="h1", ast_sha256=d1, **kw)
        keep_after_nonkeep = build_ratchet_record(
            step=2, prev_hash=halt1["record_hash"], decision="KEEP", note="k3", ast_sha256=d3, **kw,
        )
        ver_nk = verify_ratchet_ledger_records([disc0, halt1, keep_after_nonkeep])
        _req(ver_nk["valid"] is True and ver_nk["status"] == "VALID", f"Valid non-KEEP sequence rejected: {ver_nk}")

        rev_before_keep = build_ratchet_record(step=1, prev_hash=disc0["record_hash"], decision="REVERT", note="rev0", ast_sha256=d1, **kw)
        try:
            verify_ratchet_ledger_records([disc0, rev_before_keep])
        except AletheiaError as exc:
            _req(exc.code == "REVERT_TO_UNKNOWN_BASELINE", f"Expected REVERT_TO_UNKNOWN_BASELINE before any KEEP, got {exc.code}")
        else:
            raise AssertionError("DISCARD(d1)->REVERT(d1) with no prior KEEP was not rejected")

        # Invalid/non-canonical ast_sha256 MUST fail closed at BOTH build_ratchet_record AND verify_ratchet_ledger_records
        class _EvilStr(str):
            pass

        for bad_ast in (
            "",
            "   ",
            "not-a-sha256",
            "sha256:" + ("a" * 63),
            "sha256:" + ("a" * 65),
            "a" * 71,
            "sha256:" + ("A" * 64),
            "sha256:" + ("g" * 64),
            d1 + " ",
            " " + d1,
            "\u00e9" * 64,
            "sha256:" + ("\u00e9" * 64),
            "sha256:e\u0301" + ("0" * 62),
            _EvilStr(d1),
            123,
            None,
        ):
            for dec in ("KEEP", "DISCARD"):
                try:
                    build_ratchet_record(
                        step=0, prev_hash=genesis, decision=dec, note="bad_ast", ast_sha256=bad_ast, **kw,  # type: ignore[arg-type]
                    )
                except AletheiaError as exc:
                    _req(exc.code == "INVALID_AST_DIGEST", f"build_ratchet_record expected INVALID_AST_DIGEST for {bad_ast!r}/{dec}, got {exc.code}")
                else:
                    raise AssertionError(f"build_ratchet_record accepted invalid ast_sha256={bad_ast!r}/{dec}")

                bad_rec = _forge_ratchet_record(
                    step=0, prev_hash=genesis, decision=dec, note="bad_ast", ast_sha256=bad_ast, **kw,
                )
                try:
                    verify_ratchet_ledger_records([bad_rec])
                except AletheiaError as exc:
                    _req(exc.code == "INVALID_AST_DIGEST", f"Expected INVALID_AST_DIGEST for {bad_ast!r}/{dec}, got {exc.code}")
                else:
                    raise AssertionError(f"{dec} with invalid ast_sha256={bad_ast!r} was not rejected")

        # Invalid/case-variant/whitespace/str-subclass/unhashable decisions MUST fail closed at BOTH build and verify
        for bad_dec in ("keep", "Keep", "KEEP ", " KEEP", "kept", "", "discard", "UNKNOWN", _EvilStr("KEEP"), 123, None, []):
            try:
                build_ratchet_record(
                    step=0, prev_hash=genesis, decision=bad_dec, note="bad_dec", ast_sha256=d1, **kw,  # type: ignore[arg-type]
                )
            except AletheiaError as exc:
                _req(exc.code == "INVALID_DECISION", f"build_ratchet_record expected INVALID_DECISION for {bad_dec!r}, got {exc.code}")
            else:
                raise AssertionError(f"build_ratchet_record accepted invalid decision={bad_dec!r}")

            bad_dec_rec = _forge_ratchet_record(
                step=0, prev_hash=genesis, decision=bad_dec, note="bad_dec", ast_sha256=d1, **kw,
            )
            try:
                verify_ratchet_ledger_records([bad_dec_rec])
            except AletheiaError as exc:
                _req(exc.code == "INVALID_DECISION", f"Expected INVALID_DECISION for {bad_dec!r}, got {exc.code}")
            else:
                raise AssertionError(f"Invalid decision={bad_dec!r} was not rejected")

        # Complete verify_ratchet_ledger_records structural & type guards (100% function-wide mutate/BoolOp)
        for bad_ledger, want_code in (
            ([], "EMPTY_LEDGER"),
            (["not_a_mapping"], "INVALID_RECORD"),
            ([dict(r0, schema="wrong/v0")], "INVALID_SCHEMA"),
            ([dict(r0, step=1)], "INVALID_STEP_SEQ"),
            ([dict(r0, step=False)], "INVALID_STEP_SEQ"),
            ([dict(r0, prev_hash=123)], "BROKEN_HASH_CHAIN"),
            ([dict(r0, record_hash=123)], "RECORD_HASH_MISMATCH"),
        ):
            try:
                verify_ratchet_ledger_records(bad_ledger)  # type: ignore[arg-type]
            except AletheiaError as exc:
                _req(exc.code == want_code, f"Expected {want_code}, got {exc.code}")
            else:
                raise AssertionError(f"Expected {want_code} for malformed ledger")

        # End-to-end CLI `--verify-ledger` checks: AST_UNCHANGED_KEEP, INVALID_DECISION, INVALID_AST_DIGEST,
        # LEDGER_READ_ERROR (non-UTF-8 & chmod 000), and valid changed KEEP
        with tempfile.TemporaryDirectory(prefix="aletheia_issue29_") as td:
            tdp = Path(td)
            env_cli = {"PATH": "", "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}

            def _run_verify_cli(path: Path) -> tuple[int, dict]:
                proc = subprocess.run(
                    [sys.executable, "-B", "-m", "aletheia", "ratchet", "--verify-ledger", str(path), "--json"],
                    capture_output=True,
                    text=True,
                    env=env_cli,
                    check=False,
                )
                return proc.returncode, json.loads(proc.stdout)

            bad_jsonl = tdp / "unchanged_keep.jsonl"
            bad_jsonl.write_text(
                json.dumps(r0, separators=(",", ":")) + "\n" + json.dumps(same, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            rc_b, pay_b = _run_verify_cli(bad_jsonl)
            _req(rc_b == 2 and pay_b.get("status") == "ERROR" and pay_b.get("code") == "AST_UNCHANGED_KEEP", f"Unexpected CLI bad: {rc_b} {pay_b}")

            bad_dec_f = tdp / "bad_dec.jsonl"
            bad_dec_r = _forge_ratchet_record(step=0, prev_hash=genesis, decision="keep", note="lc", ast_sha256=d1, **kw)
            bad_dec_f.write_text(json.dumps(bad_dec_r, separators=(",", ":")) + "\n", encoding="utf-8")
            rc_d, pay_d = _run_verify_cli(bad_dec_f)
            _req(rc_d == 2 and pay_d.get("code") == "INVALID_DECISION", f"Unexpected CLI bad dec: {rc_d} {pay_d}")

            bad_ast_f = tdp / "bad_ast.jsonl"
            bad_ast_r = _forge_ratchet_record(step=0, prev_hash=genesis, decision="KEEP", note="ws", ast_sha256="   ", **kw)
            bad_ast_f.write_text(json.dumps(bad_ast_r, separators=(",", ":")) + "\n", encoding="utf-8")
            rc_a, pay_a = _run_verify_cli(bad_ast_f)
            _req(rc_a == 2 and pay_a.get("code") == "INVALID_AST_DIGEST", f"Unexpected CLI bad ast: {rc_a} {pay_a}")

            # Missing, non-UTF-8 & chmod 000 ledger files fail closed with rc=2
            rc_m, pay_m = _run_verify_cli(tdp / "missing.jsonl")
            _req(rc_m == 2 and pay_m.get("code") == "LEDGER_NOT_FOUND", f"Unexpected CLI missing: {rc_m} {pay_m}")

            non_utf8_f = tdp / "non_utf8.jsonl"
            non_utf8_f.write_bytes(b"\xff\xfe\n")
            rc_u, pay_u = _run_verify_cli(non_utf8_f)
            _req(rc_u == 2 and pay_u.get("code") == "LEDGER_READ_ERROR", f"Unexpected CLI non-UTF8: {rc_u} {pay_u}")

            if os.geteuid() != 0:
                unr_f = tdp / "chmod000.jsonl"
                unr_f.write_text(json.dumps(r0, separators=(",", ":")) + "\n", encoding="utf-8")
                os.chmod(unr_f, 0o000)
                try:
                    rc_p, pay_p = _run_verify_cli(unr_f)
                    _req(rc_p == 2 and pay_p.get("code") == "LEDGER_READ_ERROR", f"Unexpected CLI chmod 000: {rc_p} {pay_p}")
                finally:
                    os.chmod(unr_f, 0o600)

            good_jsonl = tdp / "changed_keep.jsonl"
            good_jsonl.write_text(
                json.dumps(r0, separators=(",", ":")) + "\n" + json.dumps(diff, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            rc_g, pay_g = _run_verify_cli(good_jsonl)
            _req(rc_g == 0 and pay_g.get("valid") is True and pay_g.get("status") == "VALID", f"Unexpected CLI good: {rc_g} {pay_g}")

    def test_ratchet_input_guards_and_demo_self_checks_fail_closed(self) -> None:
        """Named controls for the remaining `aletheia/ratchet.py` refusal sites (R5)."""

        def _expect_code(want: str, fn: object, *args: object, **kwargs: object) -> None:
            try:
                fn(*args, **kwargs)  # type: ignore[operator]
            except AletheiaError as exc:
                _req(exc.code == want, f"Expected {want}, got {exc.code}")
            else:
                raise AssertionError(f"Expected {want} for args={args!r} kwargs={kwargs!r}")

        # check_ring0_lock: both configs must be mappings
        _expect_code("INVALID_CONFIG", check_ring0_lock, ["oracle"], {"oracle": "exact"})
        _expect_code("INVALID_CONFIG", check_ring0_lock, {"oracle": "exact"}, "oracle")

        # ast_canonical_digest: empty/non-str source and syntax errors are typed refusals
        for bad_src in ("", "   \n", 123, None):
            _expect_code("EMPTY_SOURCE", ast_canonical_digest, bad_src)
        _expect_code("AST_SYNTAX_ERROR", ast_canonical_digest, "def f(:\n    return 1\n")

        # exact_pythagorean_latch_check: every metric must be a non-negative Fraction
        good_metrics = dict(
            proxy_before=Fraction(1), proxy_after=Fraction(1), outside_before=Fraction(1), outside_after=Fraction(1),
        )
        for name in good_metrics:
            for bad_val in (1, 0.5, Fraction(-1, 2), None):
                _expect_code("INVALID_EXACT_METRIC", exact_pythagorean_latch_check, **dict(good_metrics, **{name: bad_val}))

        # check_fixed_compute_survival: typed budget and format flag
        for bad_wall in (-1, True, 1.0, None):
            _expect_code("INVALID_WALL_MS", check_fixed_compute_survival, wall_ms=bad_wall, max_wall_ms=10, format_valid=True)
        for bad_max in (0, -5, True, 10.0, None):
            _expect_code("INVALID_MAX_WALL_MS", check_fixed_compute_survival, wall_ms=1, max_wall_ms=bad_max, format_valid=True)
        for bad_flag in (1, 0, "true", None):
            _expect_code("INVALID_FORMAT_FLAG", check_fixed_compute_survival, wall_ms=1, max_wall_ms=10, format_valid=bad_flag)

        # build_ratchet_record: step and denominators
        genesis = "sha256:" + ("0" * 64)
        d1 = ast_canonical_digest("def f(x):\n    return x + 1\n")
        rec_kw = dict(
            step=0, prev_hash=genesis, decision="KEEP", ast_sha256=d1, wall_ms=1,
            proxy_num=0, proxy_den=1, outside_num=0, outside_den=1, note="n",
        )
        for bad_step in (-1, True, 1.0, None):
            _expect_code("INVALID_STEP", build_ratchet_record, **dict(rec_kw, step=bad_step))
        for field in ("proxy_den", "outside_den"):
            for bad_den in (0, -1, True, 1.0, None):
                _expect_code("INVALID_DENOM", build_ratchet_record, **dict(rec_kw, **{field: bad_den}))

        # run_ratchet_demo: passes as shipped, and each self-check refuses when its gate is broken
        demo = ratchet_mod.run_ratchet_demo()
        _req(demo["status"] == "PASS", f"Demo did not pass: {demo}")
        _req(demo["regime_4_ring0_and_ledger"]["ledger_verified"]["valid"] is True, f"Demo ledger invalid: {demo}")

        def _latch_always(decision: str):
            return lambda **_kw: {"decision": decision}

        digest_counter = iter(range(10 ** 6))
        broken_gates = (
            ("exact_pythagorean_latch_check", _latch_always("KEEP"), "DEMO_LATCH_FAIL"),
            ("exact_pythagorean_latch_check", _latch_always("LATCH_HALT"), "DEMO_REPAIR_FAIL"),
            ("ast_canonical_digest", lambda _src: f"sha256:{next(digest_counter):064x}", "DEMO_AST_FAIL"),
            (
                "check_fixed_compute_survival",
                lambda **_kw: {"admitted": True, "within_budget": True, "format_valid": True, "reason": "ADMITTED"},
                "DEMO_CS08_FAIL",
            ),
            ("check_ring0_lock", lambda _base, _cand: True, "DEMO_RING0_FAIL"),
        )
        for attr, fake, want in broken_gates:
            with mock.patch.object(ratchet_mod, attr, fake):
                _expect_code(want, ratchet_mod.run_ratchet_demo)


if __name__ == "__main__":
    unittest.main()
