"""
Regression tests for `Foundation-0/aletheia#11`:
Verify that `spec/LAWS_AND_GATES.md` Section 6 explicitly states both the
Plane-2 oracle-compilation ban (`plane2_oracle_compilation_forbidden: true`)
and all five autonomous ratchet clauses as standalone visible sentences:
text hidden behind comments or fenced code blocks, mid-sentence hedges, and
post-sentence tails do not satisfy them. The spec's enforcement notes must
also match what `aletheia/mde.py` and `aletheia/ratchet.py` actually check.

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

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia.mde import (
    build_aletheia_mde_manifest,
    compute_zone_canon_id,
    verify_aletheia_mde_manifest,
)
from aletheia.ratchet import (
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


def _visible_section_6() -> str:
    """Section 6 text with HTML comments and fenced code blocks removed.

    Clauses hidden behind comments or fences, or stated only inside code
    samples, do not count as spec text.
    """
    section = _extract_section_6(SPEC_PATH.read_text(encoding="utf-8"))
    without_comments = re.sub(r"<!--.*?-->", "", section, flags=re.DOTALL)
    without_fences = re.sub(
        r"(?ms)^[ \t]*```.*?^[ \t]*```[ \t]*$",
        "",
        without_comments,
    )
    return without_fences


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
    "`build_ratchet_record` & `verify_ratchet_ledger_records` "
    "(`aletheia ratchet --verify-ledger` checks the hash chain, strict decision enum, "
    "canonical `sha256` AST digest format, and Gate-1 AST progression across `KEEP` steps "
    "over declared digest strings in the submitted ledger: `BROKEN_HASH_CHAIN`, "
    "`RECORD_HASH_MISMATCH`, `INVALID_DECISION`, `INVALID_AST_DIGEST`, "
    "`AST_UNCHANGED_KEEP`), `ast_canonical_digest` (canonical AST hash whose "
    "unchanged-baseline `KEEP` invariant is enforced on submitted ledger digests by "
    "`verify_ratchet_ledger_records` via `AST_UNCHANGED_KEEP`), "
    "`exact_pythagorean_latch_check` / `LATCH_HALT`, and "
    "`check_fixed_compute_survival` / `EXCEEDED_FIXED_COMPUTE_CAP` & "
    "`FORMAT_BREAKING_COT_ESCAPE`. No runtime supervisor forces an external loop to call "
    "clauses (i), (iv), or (v), and `--verify-ledger` verifies declared digest strings in "
    "the submitted ledger rather than re-parsing external source files, whereas any "
    "submitted ledger violating hash-chain integrity, decision/digest validity, or keeping "
    "an unchanged `ast_sha256` across `KEEP` steps fails closed under "
    "`verify_ratchet_ledger_records`. Blind portal re-entry preserving informative failed "
    "branches in clause (iv) is a normative loop-orchestration discipline (`AUDIT-026R`), "
    "paired with the `LATCH_HALT` trigger rather than a standalone function in "
    "`aletheia/ratchet.py`."
)


def _enclosing_clause_block(section: str, start: int) -> str:
    """Return the enclosing numbered Section 6 item (or full section if unnumbered)."""
    item_starts = [m.start() for m in re.finditer(r"(?m)^\d+\.\s", section)]
    lo = 0
    hi = len(section)
    for pos in item_starts:
        if pos <= start:
            lo = pos
        else:
            hi = pos
            break
    return section[lo:hi]


def _extract_block_bullets(block: str) -> list[str]:
    """Parse sub-bullets inside a numbered clause block, rejecting invisible `Cf` format chars."""
    for ch in block:
        if unicodedata.category(ch) == "Cf":
            raise AssertionError(f"Invisible format character U+{ord(ch):04X} forbidden in Section 6 clause block")
    normalized = unicodedata.normalize("NFKC", block)
    lines = normalized.splitlines()
    bullets: list[str] = []
    idx = 0
    if lines and re.match(r"^\d+\.\s", lines[0]):
        idx = 1
    while idx < len(lines):
        raw = lines[idx]
        stripped = raw.strip()
        if not stripped:
            idx += 1
            continue
        if stripped.startswith(("#",)):
            break
        if stripped.startswith(("- ", "* ")):
            bullets.append(stripped[2:].strip())
        else:
            raise AssertionError(f"Unexpected non-bullet continuation line inside clause block: {raw!r}")
        idx += 1
    return bullets


def _assert_exact_obligation_clause(
    section: str,
    sentence: str,
    *,
    lead_in: str = "",
    allowed_block_bullets: tuple[str, ...] | None = None,
) -> None:
    """Whole-bullet and whole-block allow-list check (NFKC + Cf-free, zero leaky deny-list)."""
    for ch in section:
        if unicodedata.category(ch) == "Cf":
            raise AssertionError(f"Invisible format character U+{ord(ch):04X} forbidden in Section 6")
    norm_section = unicodedata.normalize("NFKC", section)
    norm_sentence = unicodedata.normalize("NFKC", sentence)
    expected_bullet = f"{unicodedata.normalize('NFKC', lead_in)} {norm_sentence}" if lead_in else norm_sentence

    start = norm_section.find(norm_sentence)
    _req(start != -1, f"Required sentence missing from visible Section 6 text: {sentence!r}")
    clause_block = _enclosing_clause_block(norm_section, start)
    bullets = _extract_block_bullets(clause_block)
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


class TestSpecSection6Clauses(unittest.TestCase):
    def test_spec_section6_restores_plane2_ban_and_ratchet_clauses(self) -> None:
        section_6 = _visible_section_6()

        # Restored obligations must match exact canonical whole-bullet and whole-block allow-lists.
        _assert_exact_obligation_clause(
            section_6,
            _PLANE2_SENTENCE,
            lead_in=_PLANE2_LEAD_IN,
            allowed_block_bullets=(
                _PLANE2_CONTEXT_BULLET,
                f"{_PLANE2_LEAD_IN} {_PLANE2_SENTENCE}",
                _PLANE2_ENFORCEMENT_BULLET,
            ),
        )
        _assert_exact_obligation_clause(
            section_6,
            _RATCHET_SENTENCE,
            allowed_block_bullets=(
                _RATCHET_SENTENCE,
                _RATCHET_ENFORCEMENT_BULLET,
            ),
        )

        required_visible_phrases = (
            # Plane-2 ban key (restored verbatim from v1.3.0 58207b4)
            "plane2_oracle_compilation_forbidden: true",
            # Enforcement notes must state what the code actually checks
            "when a manifest is checked",
            "for an enforcing loop to call",
            "INVALID_DECISION",
            "INVALID_AST_DIGEST",
            "AST_UNCHANGED_KEEP",
            "declared digest strings in the submitted ledger",
            # Existing v2.0.0 Section 6 items preserved intact
            "aletheia/gates_v2.py",
            "aletheia/safety.py",
            "aletheia calculus",
            "aletheia/audit_check.py",
        )
        for phrase in required_visible_phrases:
            _req(phrase in section_6, f"Missing required Section 6 clause in visible spec/LAWS_AND_GATES.md text: {phrase!r}")

    def test_spec_clause_boundary_rejects_contradicting_tails_and_waivers(self) -> None:
        """Regression tests for `Foundation-0/aletheia#29` Gap 1 whole-bullet allow-list."""
        section_6 = _visible_section_6()
        plane2_allowed = (
            _PLANE2_CONTEXT_BULLET,
            f"{_PLANE2_LEAD_IN} {_PLANE2_SENTENCE}",
            _PLANE2_ENFORCEMENT_BULLET,
        )
        ratchet_allowed = (_RATCHET_SENTENCE, _RATCHET_ENFORCEMENT_BULLET)

        # All #29 same-line tails, pre-sentence hedges, continuation lines, zero-width Cf chars,
        # and arbitrary rephrased waiver bullets (even with zero deny-list words!) MUST fail closed.
        bad_mutations = (
            # Exact `@orda-aska` #29 trailing sentences
            (_PLANE2_SENTENCE, _PLANE2_SENTENCE + " Unless the owner waives this.", _PLANE2_LEAD_IN, plane2_allowed),
            (_RATCHET_SENTENCE, _RATCHET_SENTENCE + " All of these are optional.", "", ratchet_allowed),
            (_PLANE2_SENTENCE, _PLANE2_SENTENCE + " This does not apply to adapters.", _PLANE2_LEAD_IN, plane2_allowed),
            # Arbitrary pre-sentence contradiction
            (_PLANE2_SENTENCE, "Adapters are excluded. " + _PLANE2_SENTENCE, _PLANE2_LEAD_IN, plane2_allowed),
            (_RATCHET_SENTENCE, "In advisory mode only. " + _RATCHET_SENTENCE, "", ratchet_allowed),
            # Neutral same-line trailing prose
            (_PLANE2_SENTENCE, _PLANE2_SENTENCE + " Additional prose on the same line.", _PLANE2_LEAD_IN, plane2_allowed),
            (_RATCHET_SENTENCE, _RATCHET_SENTENCE + " Additional prose on the same line.", "", ratchet_allowed),
            # Same-paragraph continuation line
            (_RATCHET_SENTENCE, _RATCHET_SENTENCE + "\n   Continuing the same paragraph without a bullet.", "", ratchet_allowed),
            # Rephrased added waiver bullets with ZERO classic deny-list words
            (_PLANE2_SENTENCE, _PLANE2_SENTENCE + "\n   - Non-binding guidance only.", _PLANE2_LEAD_IN, plane2_allowed),
            (_RATCHET_SENTENCE, _RATCHET_SENTENCE + "\n   - Waiving these requirements is permitted.", "", ratchet_allowed),
            (_RATCHET_SENTENCE, _RATCHET_SENTENCE + "\n   - Teams may opt out.", "", ratchet_allowed),
            # Invisible zero-width format character (Cf) smuggling
            (_PLANE2_SENTENCE, _PLANE2_SENTENCE + "\u200b", _PLANE2_LEAD_IN, plane2_allowed),
        )
        for sentence, replacement, lead_in, allowed in bad_mutations:
            mutated = section_6.replace(sentence, replacement, 1)
            _req(mutated != section_6, f"Test setup failed to mutate sentence: {sentence!r}")
            try:
                _assert_exact_obligation_clause(mutated, sentence, lead_in=lead_in, allowed_block_bullets=allowed)
            except AssertionError:
                pass
            else:
                raise AssertionError(f"Tampered clause was not rejected: {replacement!r}")

        # Positive controls: clean standalone clause block passes
        _assert_exact_obligation_clause(
            f"4. **Clause:**\n   - {_PLANE2_LEAD_IN} {_PLANE2_SENTENCE}\n\n### Next",
            _PLANE2_SENTENCE,
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

        # KEEP(d1) -> DISCARD(d2) -> KEEP(d2) MUST pass
        disc_diff = build_ratchet_record(
            step=1, prev_hash=r0["record_hash"], decision="DISCARD", note="d2", ast_sha256=d2, **kw,
        )
        keep_after_disc_diff = build_ratchet_record(
            step=2, prev_hash=disc_diff["record_hash"], decision="KEEP", note="k2", ast_sha256=d2, **kw,
        )
        ver_dk = verify_ratchet_ledger_records([r0, disc_diff, keep_after_disc_diff])
        _req(ver_dk["valid"] is True and ver_dk["status"] == "VALID", f"Valid KEEP->DISCARD(diff)->KEEP(diff) rejected: {ver_dk}")

        # Consecutive non-KEEP records with identical ast_sha256 MUST remain valid
        disc0 = build_ratchet_record(step=0, prev_hash=genesis, decision="DISCARD", note="d0", ast_sha256=d1, **kw)
        disc1 = build_ratchet_record(step=1, prev_hash=disc0["record_hash"], decision="REVERT", note="rev", ast_sha256=d1, **kw)
        keep_after_nonkeep = build_ratchet_record(
            step=2, prev_hash=disc1["record_hash"], decision="KEEP", note="k3", ast_sha256=d3, **kw,
        )
        ver_nk = verify_ratchet_ledger_records([disc0, disc1, keep_after_nonkeep])
        _req(ver_nk["valid"] is True and ver_nk["status"] == "VALID", f"Valid non-KEEP sequence rejected: {ver_nk}")

        # Invalid/non-canonical ast_sha256 MUST fail closed with INVALID_AST_DIGEST on ANY decision
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
            123,
            None,
        ):
            for dec in ("KEEP", "DISCARD"):
                bad_rec = build_ratchet_record(
                    step=0, prev_hash=genesis, decision=dec, note="bad_ast", ast_sha256=bad_ast, **kw,  # type: ignore[arg-type]
                )
                try:
                    verify_ratchet_ledger_records([bad_rec])
                except AletheiaError as exc:
                    _req(exc.code == "INVALID_AST_DIGEST", f"Expected INVALID_AST_DIGEST for {bad_ast!r}/{dec}, got {exc.code}")
                else:
                    raise AssertionError(f"{dec} with invalid ast_sha256={bad_ast!r} was not rejected")

        # Invalid/case-variant/whitespace/unhashable decisions MUST fail closed with INVALID_DECISION
        for bad_dec in ("keep", "Keep", "KEEP ", " KEEP", "kept", "", "discard", "UNKNOWN", 123, None, []):
            bad_dec_rec = build_ratchet_record(
                step=0, prev_hash=genesis, decision=bad_dec, note="bad_dec", ast_sha256=d1, **kw,  # type: ignore[arg-type]
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
            bad_dec_r = build_ratchet_record(step=0, prev_hash=genesis, decision="keep", note="lc", ast_sha256=d1, **kw)
            bad_dec_f.write_text(json.dumps(bad_dec_r, separators=(",", ":")) + "\n", encoding="utf-8")
            rc_d, pay_d = _run_verify_cli(bad_dec_f)
            _req(rc_d == 2 and pay_d.get("code") == "INVALID_DECISION", f"Unexpected CLI bad dec: {rc_d} {pay_d}")

            bad_ast_f = tdp / "bad_ast.jsonl"
            bad_ast_r = build_ratchet_record(step=0, prev_hash=genesis, decision="KEEP", note="ws", ast_sha256="   ", **kw)
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


if __name__ == "__main__":
    unittest.main()
