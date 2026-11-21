"""
Comprehensive pure-stdlib test suite for the `aletheia` CLI & package.

Zero bare `assert` statements (100% R4 parity under -I -B, -I -O -B, -I -B -W error).
Covers all 6 subcommands (init, audit-check, mutate, diagnose, handoff, install),
adversarial R1-R5 must-fail controls, Cave-Shadow relapse detection, and live 100% mutant kill!
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

from aletheia.audit_check import run_audit_check, validate_audit_receipt_json
from aletheia.cli import main as cli_main
from aletheia.diagnose import diagnose_expedition
from aletheia.handoff import create_handoff_template, validate_handoff_manifest
from aletheia.installer import VALID_TARGETS, install_adapter
from aletheia.mutator import run_mutation_suite
from aletheia.scaffold import init_workspace
from aletheia.strict_io import AletheiaError, parse_strict_json_text, write_lf_text

CLI_ROOT = Path(__file__).resolve().parent.parent


def _req(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        rc = cli_main(argv)
    return rc, out_buf.getvalue(), err_buf.getvalue()


class TestAletheiaCLI(unittest.TestCase):
    def test_01_init_scaffold_and_self_audit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_init_") as td:
            ws = Path(td) / "exp"
            rc, out, _ = _run_cli(["init", str(ws), "--domain", "spectral", "--json"])
            _req(rc == 0, f"init failed: rc={rc} out={out}")
            data = json.loads(out)
            _req(data["status"] == "INITIALIZED" and data["domain"] == "spectral", f"bad init payload: {data}")
            for rel in (
                "aletheia.json",
                "cartography/frontier_portals.md",
                "verification/PROTOCOL.md",
                "verification/AUDIT_LOG.md",
                "manifests/compute_handoff.v1.json",
            ):
                _req((ws / rel).is_file(), f"missing scaffolded file {rel}")

            # Refuses overwrite without --force (R1 safe)
            with self.assertRaises(AletheiaError):
                init_workspace(ws, domain="spectral", force=False)

            # Invalid domain name rejected
            with self.assertRaises(AletheiaError):
                init_workspace(Path(td) / "bad", domain="BAD DOMAIN!")

            # Fresh workspace passes audit-check, handoff validation, AND diagnose cleanly (no self-triggered CS-06)!
            aud = run_audit_check(ws)
            _req(aud["passed"], f"fresh workspace failed audit-check: {aud}")
            ho = validate_handoff_manifest(ws / "manifests" / "compute_handoff.v1.json")
            _req(ho["valid"], f"scaffolded handoff manifest invalid: {ho}")
            diag = diagnose_expedition(ws)
            _req(
                diag["overall_status"] == "HEALTHY" and diag["alert_count"] == 0,
                f"fresh workspace self-triggered diagnose: {diag}",
            )
            rc_diag, out_diag, _ = _run_cli(["diagnose", str(ws), "--json"])
            _req(rc_diag == 0 and json.loads(out_diag)["overall_status"] == "HEALTHY", f"CLI diagnose failed: {rc_diag} {out_diag}")

    def test_02_audit_check_r1_to_r4_must_fail_controls(self) -> None:
        # 1. Clean self-audit of the aletheia CLI staging tree itself!
        self_aud = run_audit_check(CLI_ROOT)
        _req(self_aud["passed"], f"aletheia CLI self-audit failed: {self_aud}")

        # 2. Adversarial temp fixtures that MUST fail audit-check:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_aud_") as td:
            root = Path(td)

            # Control A: bare `assert` on trust path
            d_assert = root / "bad_assert"
            d_assert.mkdir()
            write_lf_text(d_assert / "checker.py", "def ok(x):\n    assert x > 0\n    return True\n")
            r_assert = run_audit_check(d_assert)
            _req(not r_assert["passed"] and r_assert["summary"]["bare_assert_count"] == 1,
                 f"failed to catch bare assert: {r_assert}")

            # Control B: CRLF line ending
            d_crlf = root / "bad_crlf"
            d_crlf.mkdir()
            (d_crlf / "note.md").write_bytes(b"hello\r\nworld\r\n")
            r_crlf = run_audit_check(d_crlf)
            _req(not r_crlf["passed"] and r_crlf["summary"]["crlf_count"] == 1,
                 f"failed to catch CRLF: {r_crlf}")

            # Control C: __pycache__ artifact
            d_pyc = root / "bad_pyc"
            (d_pyc / "__pycache__").mkdir(parents=True)
            (d_pyc / "__pycache__" / "x.pyc").write_bytes(b"0000")
            r_pyc = run_audit_check(d_pyc)
            _req(not r_pyc["passed"] and r_pyc["summary"]["pycache_count"] >= 1,
                 f"failed to catch pycache: {r_pyc}")

            # Control D: dynamically synthesized personal path leak (zero literal path in source!)
            d_leak = root / "bad_leak"
            d_leak.mkdir()
            fake_path = chr(47) + "ho" + "me" + chr(47) + "alice" + chr(47) + "work"
            write_lf_text(d_leak / "README.md", f"Run from {fake_path}\n")
            r_leak = run_audit_check(d_leak)
            _req(not r_leak["passed"] and r_leak["summary"]["leak_count"] == 1,
                 f"failed to catch personal path leak: {r_leak}")

            # Control E: duplicate JSON key
            d_dup = root / "bad_json"
            d_dup.mkdir()
            write_lf_text(d_dup / "dup.json", '{"k": 1, "k": 2}\n')
            r_dup = run_audit_check(d_dup)
            _req(not r_dup["passed"] and r_dup["summary"]["json_error_count"] == 1,
                 f"failed to catch duplicate JSON key: {r_dup}")

            # Control F: R4 script parity catches script whose output changes under -O (assert stripped!)
            d_r4 = root / "bad_r4"
            d_r4.mkdir()
            write_lf_text(
                d_r4 / "sneaky.py",
                "import sys\nif __debug__:\n    print('DEBUG_MODE')\nelse:\n    print('OPT_MODE')\n",
            )
            r_r4 = run_audit_check(d_r4, scripts=[d_r4 / "sneaky.py"])
            _req(not r_r4["passed"] and not r_r4["r4_scripts"][0]["stdout_bit_identical"],
                 f"failed to catch -O stdout divergence: {r_r4}")

            # Control G: R4 script parity PASSES on clean deterministic script
            d_ok = root / "good_r4"
            d_ok.mkdir()
            write_lf_text(d_ok / "clean.py", "print('EXACT_DETERMINISTIC_42')\n")
            r_ok = run_audit_check(d_ok, scripts=[d_ok / "clean.py"])
            _req(r_ok["passed"] and r_ok["r4_scripts"][0]["stdout_bit_identical"],
                 f"clean R4 script unexpectedly failed: {r_ok}")

            # Control H: unseeded random warning + strict failure
            d_rng = root / "bad_rng"
            d_rng.mkdir()
            write_lf_text(d_rng / "sim.py", "import random\nx = random.random()\n")
            r_rng_warn = run_audit_check(d_rng, strict_unseeded=False)
            r_rng_strict = run_audit_check(d_rng, strict_unseeded=True)
            _req(r_rng_warn["passed"] and r_rng_warn["summary"]["unseeded_rng_warning_count"] == 1,
                 f"expected unseeded warning: {r_rng_warn}")
            _req(not r_rng_strict["passed"], "strict_unseeded should fail")

            # Control I: AUDIT_LOG.md invalid verdict + audit receipt R2/R3 validation
            d_log = root / "bad_log"
            write_lf_text(
                d_log / "verification" / "AUDIT_LOG.md",
                "| Audit ID | Date | Author | Target | Gates | Oracle | Novelty | Verdict | Evidence |\n"
                "|---|---|---|---|---|---|---|---|---|\n"
                "| **AUDIT-001** | 2026-11-20 | a | t | G1 | exact | N2 | **BOGUS_STATUS** | none |\n",
            )
            r_log = run_audit_check(d_log)
            _req(not r_log["passed"] and not r_log["audit_log"]["valid"], f"bad verdict not caught: {r_log}")

            # Audit receipt valid vs N2-without-prior-art rejected
            rec_ok = root / "receipt_ok.json"
            write_lf_text(
                rec_ok,
                json.dumps({
                    "schema": "aletheia.audit_receipt.v1",
                    "audit_id": "AUDIT-001",
                    "target": "theorem_a",
                    "verdict": "VERIFIED",
                    "oracle_class": "exact",
                    "novelty": "N2",
                    "repro_command": "python3 -I -O -B -W error check.py",
                    "r4_parity": True,
                    "prior_art_checked": True,
                    "evidence": "Verified against arXiv:2610.08965",
                }, indent=2) + "\n",
            )
            _req(validate_audit_receipt_json(rec_ok)["valid"], "valid receipt rejected")

            rec_bad = root / "receipt_bad.json"
            write_lf_text(
                rec_bad,
                json.dumps({
                    "schema": "aletheia.audit_receipt.v1",
                    "audit_id": "AUDIT-002",
                    "target": "theorem_b",
                    "verdict": "VERIFIED",
                    "oracle_class": "exact",
                    "novelty": "N2",
                    "repro_command": "python3 check.py",
                    "r4_parity": True,
                    "prior_art_checked": False,
                    "evidence": "missing prior art",
                }, indent=2) + "\n",
            )
            _req(not validate_audit_receipt_json(rec_bad)["valid"], "N2 without prior_art_checked was not rejected")

    def test_03_mutate_r5_100_percent_kill_on_fixture_verifier(self) -> None:
        """
        Live R5 end-to-end test: run `aletheia mutate` against `tests/fixture_verifier.py`
        and confirm 100% mutant kill rate (0 survivors) across ALL discovered AST refusal
        and boundary guards!
        """
        fixture = CLI_ROOT / "tests" / "fixture_verifier.py"
        res = run_mutation_suite(
            fixture,
            "python3 fixture_verifier_test.py",
            work_root=fixture.parent,
            include_boundaries=True,
        )
        _req(res["total_mutants"] >= 12, f"expected >= 12 AST mutants, got {res['total_mutants']}")
        _req(res["passed"] and res["survived"] == 0 and res["kill_rate_pct"] == 100.0,
             f"fixture mutation suite had survivors: {res['survivors']}")

        # Also test CLI entrypoint directly
        rc, out, _ = _run_cli([
            "mutate", str(fixture),
            "--test-cmd", "python3 fixture_verifier_test.py",
            "--work-root", str(fixture.parent),
            "--json",
        ])
        _req(rc == 0, f"CLI mutate returned rc={rc}: {out}")
        parsed = json.loads(out)
        _req(parsed["killed"] == parsed["total_mutants"] and parsed["survived"] == 0, f"CLI mutate mismatch: {parsed}")

    def test_04_diagnose_healthy_vs_cave_shadow_relapse(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_diag_") as td:
            root = Path(td)

            # 1. Healthy expedition passes with HEALTHY status
            good = root / "healthy"
            init_workspace(good, domain="math")
            write_lf_text(
                good / "cartography" / "frontier_portals.md",
                "# Frontier Portals\n\n"
                "## Portal 1 — Spectral Rank Envelope\n"
                "Exact theorem: `n_+(H_perp) >= R_opt(u, t, S, b)` proved in `probes/math/check.py`.\n"
                "Elevated sharpness wall into higher-moment Theorem A2 branch.\n\n"
                "## Portal 2 — Higher-Moment Stieltjes-Hankel\n"
                "Exact Schur complement `R_H4 = S_1^2/S_2 + (S_1 S_3 - S_2^2)^2/(S_2(S_2 S_4 - S_3^2)) - b`.\n",
            )
            write_lf_text(
                good / "verification" / "AUDIT_LOG.md",
                "| Audit ID | Date | Author | Target | Gates | Oracle | Novelty | Verdict | Evidence |\n"
                "|---|---|---|---|---|---|---|---|---|\n"
                "| **AUDIT-001** | 2026-11-20 | probe | proto | G1 | exact | N1 | **FALSIFIED** | missing PSD check |\n"
                "| **AUDIT-002** | 2026-11-20 | probe | R_opt | G1-G9 | exact | **N2** | **VERIFIED** | confirmed beyond arXiv:2610.08965 |\n",
            )
            good_board = root / "good_board.jsonl"
            write_lf_text(
                good_board,
                "\n".join([
                    json.dumps({"seq": 1, "agent": "portal-keeper", "text": "Opened Portal 1"}),
                    json.dumps({"seq": 2, "agent": "verifier", "text": "FALSIFIED proto bug"}),
                    json.dumps({"seq": 3, "agent": "portal-keeper", "text": "Steelmanned Portal 1 -> repaired R_opt"}),
                    json.dumps({"seq": 4, "agent": "verifier", "text": "VERIFIED N2 + proved sharpness wall"}),
                    json.dumps({"seq": 5, "agent": "portal-keeper", "text": "Spawning higher-moment theorem branch"}),
                ]) + "\n",
            )
            d_good = diagnose_expedition(good, board_path=good_board)
            _req(d_good["overall_status"] == "HEALTHY" and d_good["alert_count"] == 0,
                 f"healthy expedition flagged: {d_good}")

            # 2. Simulated Cave-Shadow relapse triggers RELAPSE_DETECTED across multiple patterns!
            bad = root / "relapse"
            (bad / "cartography").mkdir(parents=True)
            (bad / "verification" / "checks").mkdir(parents=True)
            write_lf_text(
                bad / "cartography" / "frontier_portals.md",
                "# Map\n\n## Portal 1\n"
                "Both domains share a deep sheaf duality curvature emergence holonomy isomorphism.\n"
                "We hit a sharpness wall and stopped.\n"
                "Used a synthetic proxy for quick validation. Draft PR merged into main.\n",
            )
            write_lf_text(
                bad / "verification" / "AUDIT_LOG.md",
                "| Audit ID | Date | Author | Target | Gates | Oracle | Novelty | Verdict | Evidence |\n"
                "|---|---|---|---|---|---|---|---|---|\n"
                "| **AUDIT-001** | 2026-11-20 | a | p1 | G1 | exact | N0 | **FALSIFIED** | bug |\n"
                "| **AUDIT-002** | 2026-11-20 | a | p2 | G1 | exact | N0 | **FALSIFIED** | bug |\n",
            )
            write_lf_text(
                bad / "verification" / "checks" / "glass.py",
                "from fractions import Fraction\n# zero-float exact check\ndef check(x):\n    assert abs(x) < 1e-12\n",
            )
            bad_board = root / "bad_board.jsonl"
            write_lf_text(
                bad_board,
                "\n".join([
                    json.dumps({"seq": 1, "agent": "portal-keeper", "text": "[done] initial summary"}),
                    json.dumps({"seq": 2, "agent": "verifier", "text": "FALSIFIED dead end"}),
                    json.dumps({"seq": 3, "agent": "verifier", "text": "FALSIFIED repackaging no new ground"}),
                    json.dumps({"seq": 4, "agent": "verifier", "text": "FALSIFIED dead end"}),
                    json.dumps({"seq": 5, "agent": "probe", "text": "stopping here"}),
                ]) + "\n",
            )
            rc, out, _ = _run_cli(["diagnose", str(bad), "--board", str(bad_board), "--json"])
            _req(rc == 1, f"expected rc=1 on relapse, got {rc}")
            d_bad = json.loads(out)
            _req(d_bad["overall_status"] == "RELAPSE_DETECTED" and d_bad["alert_count"] >= 4,
                 f"expected >= 4 alerts on relapse fixture, got {d_bad}")

    def test_05_handoff_template_and_strict_validation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_ho_") as td:
            root = Path(td)
            mf = root / "handoff.json"
            rc, out, _ = _run_cli(["handoff", str(mf), "--init-template", "--domain", "physics", "--json"])
            _req(rc == 0 and mf.is_file(), f"handoff --init-template failed: {out}")

            rc2, out2, _ = _run_cli(["handoff", str(mf), "--json"])
            _req(rc2 == 0 and json.loads(out2)["valid"], f"template manifest failed validation: {out2}")

            # Corrupt manifest: unknown compute_tier + invalid oracle_class + missing falsification_gate
            bad_mf = root / "bad_handoff.json"
            obj = json.loads(mf.read_text(encoding="utf-8"))
            obj["waves"][0]["tasks"][0]["compute_tier"] = "nonexistent_tier"
            obj["waves"][0]["tasks"][0]["oracle_class"] = "vibes"
            obj["waves"][0]["tasks"][0]["falsification_gate"] = ""
            write_lf_text(bad_mf, json.dumps(obj, indent=2) + "\n")

            rc3, out3, _ = _run_cli(["handoff", str(bad_mf), "--json"])
            _req(rc3 == 1, f"expected rc=1 on corrupt handoff manifest, got {rc3}")
            parsed = json.loads(out3)
            codes = {e["code"] for e in parsed["errors"]}
            _req({"UNKNOWN_COMPUTE_TIER", "INVALID_ORACLE_CLASS", "MISSING_TASK_FIELD"}.issubset(codes),
                 f"expected all 3 error codes, got {codes}")

            # Legacy expedition.next_waves.v1 allows parenthetical qualifiers on valid oracle tokens
            leg_mf = root / "legacy_handoff.json"
            leg_obj = json.loads(mf.read_text(encoding="utf-8"))
            leg_obj["schema"] = "expedition.next_waves.v1"
            leg_obj["waves"][0]["tasks"][0]["oracle_class"] = "sampled (PDE) + exact (laws)"
            write_lf_text(leg_mf, json.dumps(leg_obj, indent=2) + "\n")
            _req(validate_handoff_manifest(leg_mf)["valid"], "legacy parenthetical oracle_class rejected")

    def test_06_install_all_targets_dry_run_and_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_ins_") as td:
            root = Path(td)
            for target in VALID_TARGETS:
                dest = root / f"dest_{target}"
                # Dry-run writes ZERO files
                rc_dr, out_dr, _ = _run_cli(["install", "--target", target, "--dest", str(dest), "--dry-run", "--json"])
                _req(rc_dr == 0, f"dry-run failed for {target}: {out_dr}")
                dr = json.loads(out_dr)
                _req(dr["status"] == "DRY_RUN" and dr["file_count"] >= 1 and not dest.exists(),
                     f"dry-run violated zero-write for {target}: {dr}")

                # Real install creates all planned LF-clean files
                rc_in, out_in, _ = _run_cli(["install", "--target", target, "--dest", str(dest), "--json"])
                _req(rc_in == 0, f"install failed for {target}: {out_in}")
                ins = json.loads(out_in)
                _req(ins["status"] == "INSTALLED" and ins["file_count"] == dr["file_count"], f"install mismatch: {ins}")
                # Installed tree must itself pass audit-check!
                aud = run_audit_check(dest)
                _req(aud["passed"], f"installed target {target} failed audit-check: {aud}")

                # Re-installing without --force fails closed (R1 safe)
                with self.assertRaises(AletheiaError):
                    install_adapter(target, dest=dest, dry_run=False, force=False)

            # Verify repo-adapter layout mapping for claude-code (README skipped; commands/agents -> .claude/*)
            fake_repo = root / "repo_src"
            write_lf_text(fake_repo / "adapters" / "claude-code" / "README.md", "# Do not overwrite repo README\n")
            write_lf_text(fake_repo / "adapters" / "claude-code" / "CLAUDE.md", "# Claude rules\n")
            write_lf_text(fake_repo / "adapters" / "claude-code" / "commands" / "aletheia.md", "# /aletheia\n")
            write_lf_text(fake_repo / "adapters" / "claude-code" / "agents" / "portal-keeper.md", "# portal-keeper\n")
            cc_dest = root / "cc_repo"
            cc_res = install_adapter("claude-code", dest=cc_dest, source_dir=fake_repo)
            _req(cc_res["source_mode"] == "repo_adapters", f"expected repo_adapters mode: {cc_res}")
            _req(not (cc_dest / "README.md").exists(), "claude-code install must not copy README.md")
            _req((cc_dest / "CLAUDE.md").is_file()
                 and (cc_dest / ".claude" / "commands" / "aletheia.md").is_file()
                 and (cc_dest / ".claude" / "agents" / "portal-keeper.md").is_file(),
                 f"claude-code layout mismatch: {cc_res}")

    def test_07_strict_json_r1_r3_edge_cases(self) -> None:
        for bad in ("", "  ", "[]", '{"a": 1, "a": 2}', '{"a": NaN}', '{"a": Infinity}'):
            with self.assertRaises(AletheiaError):
                parse_strict_json_text(bad, allow_float=True, require_object=True)
        with self.assertRaises(AletheiaError):
            parse_strict_json_text('{"a": 0.5}', allow_float=False, require_object=True)


if __name__ == "__main__":
    unittest.main()
