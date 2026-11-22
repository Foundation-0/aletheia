#!/usr/bin/env python3
"""
Clean-Room Master Test Runner for The Aletheia Method CLI (`aletheia`).

Zero external dependencies (Python 3 stdlib only). Zero bare asserts.
Safe and bit-identical across ALL isolated R4 modes:
  python3 -I -B tests/run_all.py
  python3 -I -O -B tests/run_all.py
  python3 -I -B -W error tests/run_all.py
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia import __version__
from aletheia.audit_check import run_audit_check
from aletheia.mutator import run_mutation_suite


def main() -> None:
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stderr)
    result = runner.run(suite)
    if not result.wasSuccessful():
        raise SystemExit(f"UNITTEST FAILED: failures={len(result.failures)}, errors={len(result.errors)}")

    # Live R5 mutation self-check on built-in trust-path verifier fixture
    fixture = ROOT / "tests" / "fixture_verifier.py"
    mut_report = run_mutation_suite(
        fixture,
        "python3 fixture_verifier_test.py",
        work_root=fixture.parent,
        include_boundaries=True,
    )
    if not mut_report["passed"]:
        raise SystemExit(f"MUTATION SELF-CHECK FAILED: {mut_report['survived']} survivors")

    # Live R1-R4 hygiene & AST self-audit of the CLI package & tests
    aud_pkg = run_audit_check(ROOT / "aletheia")
    aud_tests = run_audit_check(ROOT / "tests")
    if not (aud_pkg["passed"] and aud_tests["passed"]):
        raise SystemExit("SELF AUDIT-CHECK FAILED")

    summary = {
        "aletheia_version": __version__,
        "unittest": {
            "tests_run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "ok": True,
        },
        "mutation_self_check_r5": {
            "total_mutants": mut_report["total_mutants"],
            "killed": mut_report["killed"],
            "survived": mut_report["survived"],
            "kill_rate_pct": mut_report["kill_rate_pct"],
        },
        "self_audit_r1_r4": {
            "aletheia_pkg_passed": aud_pkg["passed"],
            "aletheia_pkg_bare_asserts": aud_pkg["summary"]["bare_assert_count"],
            "tests_passed": aud_tests["passed"],
            "tests_bare_asserts": aud_tests["summary"]["bare_assert_count"],
        },
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
