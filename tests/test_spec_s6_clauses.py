"""
Regression tests for `Foundation-0/aletheia#11`:
Verify that `spec/LAWS_AND_GATES.md` Section 6 explicitly states both the
Plane-2 oracle-compilation ban (`plane2_oracle_compilation_forbidden: true`)
and all five autonomous ratchet clauses, aligned with live fail-closed
enforcement in `aletheia/mde.py` and `aletheia/ratchet.py`.

Zero external dependencies. Zero bare assert statements (100% R4 parity
across `-I -B`, `-I -O -B`, and `-I -B -W error`).
"""
from __future__ import annotations

import copy
from fractions import Fraction
from pathlib import Path
import re
import unittest

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

ROOT = Path(__file__).resolve().parent.parent
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


class TestSpecSection6Clauses(unittest.TestCase):
    def test_spec_section6_restores_plane2_ban_and_ratchet_clauses(self) -> None:
        spec_text = SPEC_PATH.read_text(encoding="utf-8")
        section_6 = _extract_section_6(spec_text)

        required_phrases = (
            # Plane-2 ban (restored verbatim from v1.3.0 58207b4)
            "plane2_oracle_compilation_forbidden: true",
            "Verification oracles MUST NEVER be compiled into neural weights",
            "Plane-2 weight adapters are strictly disposable caches subordinate to Plane-1 deterministic verification",
            # Five autonomous ratchet clauses (restored verbatim from v1.3.0 58207b4)
            "Any automated hill-climbing or autoresearch loop running under Aletheia MUST enforce:",
            "(i) immutable Ring-0 evaluation harness lock",
            "(ii) float-free canonical hash-chained receipts",
            "(iii) AST-identity unchanged-baseline null rejection",
            "(iv) Pre-Adaptation Goodhart Latch halt + blind portal re-entry preserving informative failed branches",
            "(v) a fixed-compute `CS-08` survival cap",
            # Existing v2.0.0 Section 6 items preserved intact
            "aletheia/gates_v2.py",
            "aletheia/safety.py",
            "aletheia calculus",
            "aletheia/audit_check.py",
        )
        for phrase in required_phrases:
            _req(phrase in section_6, f"Missing required Section 6 clause in spec/LAWS_AND_GATES.md: {phrase!r}")

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


if __name__ == "__main__":
    unittest.main()
