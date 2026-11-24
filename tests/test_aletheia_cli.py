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
                diag["overall_status"] == "HEALTHY"
                and diag["health_score"] == 100.0
                and diag["alert_count"] == 0
                and len(diag["patterns"]) == 12,
                f"fresh workspace self-triggered diagnose: {diag}",
            )
            rc_diag, out_diag, _ = _run_cli(["diagnose", str(ws), "--json"])
            _req(
                rc_diag == 0
                and json.loads(out_diag)["overall_status"] == "HEALTHY"
                and json.loads(out_diag)["health_score"] == 100.0,
                f"CLI diagnose failed: {rc_diag} {out_diag}",
            )

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

    def test_08_mutator_v11_dict_verdict_accumulator_and_add_cwd(self) -> None:
        """v1.1 R5 upgrade (AUDIT-029): detect & kill dict-verdict and accumulator refusal sites + --add-cwd."""
        with tempfile.TemporaryDirectory(prefix="aletheia_t_m11_") as td:
            root = Path(td)
            # Checker combining dict-verdict return AND finding-accumulator append (v1.0 found 0 sites!)
            write_lf_text(
                root / "checker_pkg.py",
                "def audit_val(x: int) -> dict:\n"
                "    findings = []\n"
                "    if x < 0:\n"
                "        findings.append('NEGATIVE_VALUE')\n"
                "    if x > 10:\n"
                "        return {'admissible': False, 'status': 'REJECTED_OVERFLOW'}\n"
                "    return {'admissible': len(findings) == 0, 'findings': findings}\n",
            )
            write_lf_text(
                root / "test_checker_pkg.py",
                "import unittest\n"
                "from checker_pkg import audit_val\n"
                "class T(unittest.TestCase):\n"
                "    def test_bounds(self):\n"
                "        if not audit_val(0)['admissible']:\n"
                "            raise RuntimeError('0 must pass')\n"
                "        if not audit_val(10)['admissible']:\n"
                "            raise RuntimeError('10 must pass')\n"
                "        if audit_val(-1)['admissible']:\n"
                "            raise RuntimeError('-1 must fail')\n"
                "        if audit_val(11)['admissible']:\n"
                "            raise RuntimeError('11 must fail')\n",
            )
            # Without --add-cwd, `-I` strips cwd so `python3 -m unittest test_checker_pkg` would fail;
            # WITH --add-cwd, repo-local unittest runs cleanly and kills 4/4 mutants (2 guards + 2 boundaries)!
            rc, out, _ = _run_cli([
                "mutate", str(root / "checker_pkg.py"),
                "--test-cmd", "python3 -m unittest test_checker_pkg",
                "--work-root", str(root),
                "--add-cwd",
                "--json",
            ])
            _req(rc == 0, f"mutator v1.1 --add-cwd failed: rc={rc} out={out}")
            parsed = json.loads(out)
            _req(parsed["total_mutants"] == 4 and parsed["killed"] == 4 and parsed["survived"] == 0,
                 f"expected 4/4 mutants killed on dict+accumulator checker, got {parsed}")

    def test_09_diagnose_cs08_compute_leakage_simpson(self) -> None:
        """v1.1 CS-08 (AUDIT-023): detect unbounded-compute / format-breaking CoT Simpson's Paradox."""
        with tempfile.TemporaryDirectory(prefix="aletheia_t_cs08_") as td:
            root = Path(td)
            ws = root / "simpson_ws"
            init_workspace(ws, domain="dynamics")
            # Inject an unmitigated Simpson reversal JSON under probes/dynamics/
            write_lf_text(
                ws / "probes" / "dynamics" / "repair_eval.json",
                json.dumps({
                    "fixed_compute_winner": "Arm_C_true_sign",
                    "unbounded_winner": "Arm_D_sign_flipped",
                    "fixed_compute_cap_enforced": False,
                }, indent=2) + "\n",
            )
            rc, out, _ = _run_cli(["diagnose", str(ws), "--json"])
            _req(rc == 1, f"CS-08 Simpson poison should return rc=1, got {rc}")
            diag = json.loads(out)
            cs08 = [p for p in diag["patterns"] if p["id"] == "CS-08"][0]
            _req(cs08["status"] == "ALERT" and cs08["risk_score"] >= 50, f"CS-08 did not ALERT: {cs08}")

    def test_10_ratchet_demo_and_ledger_verification(self) -> None:
        """v1.1 `aletheia ratchet`: 4-regime demo + strict float-free hash-chained ledger verification."""
        rc, out, _ = _run_cli(["ratchet", "--demo", "--json"])
        _req(rc == 0, f"ratchet --demo failed: rc={rc} out={out}")
        data = json.loads(out)
        _req(
            data["status"] == "PASS"
            and data["regime_1_goodhart_latch"]["latch_step"]["decision"] == "LATCH_HALT"
            and data["regime_2_noise_and_ast_identity"]["ratchet_false_keeps"] == 0
            and data["regime_3_cs08_compute_cap"]["capped_valid_arm"]["admitted"] is True
            and data["regime_3_cs08_compute_cap"]["unbounded_cot_escape_arm"]["admitted"] is False
            and data["regime_4_ring0_and_ledger"]["ring0_tamper_blocked"] is True,
            f"ratchet demo invariant mismatch: {data}",
        )
        # Verify valid ledger file and reject tampered ledger file
        from aletheia.ratchet import build_ratchet_record, ast_canonical_digest
        with tempfile.TemporaryDirectory(prefix="aletheia_t_rl_") as td:
            root = Path(td)
            r0 = build_ratchet_record(
                step=0, prev_hash="sha256:" + "0" * 64, decision="KEEP",
                ast_sha256=ast_canonical_digest("x = 1\n"), wall_ms=500,
                proxy_num=0, proxy_den=1, outside_num=0, outside_den=1, note="ok",
            )
            good_f = root / "good.jsonl"
            write_lf_text(good_f, json.dumps(r0, separators=(",", ":")) + "\n")
            rc_v, out_v, _ = _run_cli(["ratchet", "--verify-ledger", str(good_f), "--json"])
            _req(rc_v == 0 and json.loads(out_v)["valid"] is True, f"valid ledger failed: {out_v}")

            bad_r0 = dict(r0)
            bad_r0["wall_ms"] = 99999
            bad_f = root / "tampered.jsonl"
            write_lf_text(bad_f, json.dumps(bad_r0, separators=(",", ":")) + "\n")
            rc_b, _, _ = _run_cli(["ratchet", "--verify-ledger", str(bad_f), "--json"])
            _req(rc_b == 2, f"tampered ledger should fail with rc=2, got {rc_b}")

    def test_11_mde_cli_and_lean4_prereg_audit(self) -> None:
        """v1.1 `aletheia mde` + `audit-check --lean-audit` (T-10..T-12) + `--prereg-check`."""
        rc_m, out_m, _ = _run_cli(["mde", "--manifest", "--json"])
        _req(rc_m == 0 and json.loads(out_m)["plane2_oracle_compilation_forbidden"] is True, f"mde --manifest failed: {out_m}")
        rc_d, out_d, _ = _run_cli(["mde", "--demo", "--json"])
        _req(rc_d == 0, f"mde --demo failed: {out_d}")
        d_mde = json.loads(out_d)
        _req(
            d_mde["zone_canon_vectors"]["accept_passed"] == 7
            and d_mde["zone_canon_vectors"]["reject_blocked"] == 10
            and d_mde["self_audit_blocked"] is True
            and d_mde["sym2p_tamper_blocked"] is True,
            f"mde --demo check failed: {d_mde}",
        )

        # Static Lean 4 auditor: clean stock-Init with char literal `'"'` passes; T-10..T-12 escapes fail!
        with tempfile.TemporaryDirectory(prefix="aletheia_t_lean_") as td:
            root = Path(td)
            clean_dir = root / "lean_ok"
            write_lf_text(
                clean_dir / "Ok.lean",
                "import Init\n/- block comment mentioning sorry and unsafe -/\n"
                "def quoteChar : Char := '\"'\ntheorem id_ok (x' : Nat) : x' = x' := rfl\n",
            )
            r_ok = run_audit_check(clean_dir, lean_audit=True)
            _req(r_ok["passed"] and r_ok["lean_audit"]["files_checked"] == 1, f"clean Lean 4 failed: {r_ok}")

            bad_dir = root / "lean_bad"
            write_lf_text(
                bad_dir / "Bad.lean",
                "import Mathlib.Data.Rat.Basic\nunsafe def u : Nat := 0\n"
                "partial def p : Nat := p\n@[\n  implemented_by u\n]\ndef q : Nat := 1\n",
            )
            r_bad = run_audit_check(bad_dir, lean_audit=True)
            codes = {f["code"] for f in r_bad["lean_audit"]["findings"]}
            _req(
                not r_bad["passed"]
                and {"LEAN4_NON_INIT_IMPORT", "LEAN4_UNSAFE", "LEAN4_PARTIAL", "LEAN4_ATTR_TRUST_ESCAPE"}.issubset(codes),
                f"Lean 4 bypasses missed: {codes}",
            )

            # Mechanical git-DAG --prereg-check (plan commit ancestor of data commit)
            import subprocess
            gdir = root / "git_prereg"
            gdir.mkdir()
            def _g(*args: str) -> str:
                p = subprocess.run(["git", "-C", str(gdir), *args], capture_output=True, text=True, check=True)
                return p.stdout.strip()
            _g("init")
            _g("config", "user.email", "test@example.invalid")
            _g("config", "user.name", "Test")
            write_lf_text(gdir / "cartography" / "frontier_portals.md", "# Plan\n")
            _g("add", ".")
            _g("commit", "-m", "plan")
            c_plan = _g("rev-parse", "HEAD")
            write_lf_text(
                gdir / "verification" / "AUDIT_LOG.md",
                "| Audit ID | Date | Author | Target | Gates | Oracle | Novelty | Verdict | Evidence |\n"
                "|---|---|---|---|---|---|---|---|---|\n"
                "| **AUDIT-001** | 2026-11-20 | a | t | G1 | exact | N1 | **VERIFIED** | ok |\n",
            )
            _g("add", ".")
            _g("commit", "-m", "audit")
            c_data = _g("rev-parse", "HEAD")
            r_pre_ok = run_audit_check(gdir, prereg_check=True)
            r_pre_inv = run_audit_check(gdir, prereg_check=True, plan_commit=c_data, data_commit=c_plan)
            r_pre_same = run_audit_check(gdir, prereg_check=True, plan_commit=c_plan, data_commit=c_plan)
            _req(r_pre_ok["passed"] and r_pre_ok["prereg_check"]["passed"] is True, f"valid prereg failed: {r_pre_ok}")
            _req(not r_pre_inv["passed"] and r_pre_inv["prereg_check"]["passed"] is False, f"inverted prereg not caught: {r_pre_inv}")
            _req(not r_pre_same["passed"] and r_pre_same["prereg_check"]["passed"] is False, f"same-commit prereg bypass not caught: {r_pre_same}")

            # Bypass B regression: rewriting plan AFTER data commit MUST fail default --prereg-check!
            write_lf_text(gdir / "cartography" / "frontier_portals.md", "# Rewritten Plan After Seeing Data\n")
            _g("add", ".")
            _g("commit", "-m", "post-hoc plan rewrite")
            r_pre_bypass_b = run_audit_check(gdir, prereg_check=True)
            _req(not r_pre_bypass_b["passed"] and r_pre_bypass_b["prereg_check"]["passed"] is False,
                 f"post-hoc plan rewrite bypass B not caught: {r_pre_bypass_b}")

            # Bypass A & C regression: separate repo with data first -> plan second -> data typo edit third
            gdir2 = root / "git_prereg_hark"
            gdir2.mkdir()
            def _g2(*args: str) -> str:
                p = subprocess.run(["git", "-C", str(gdir2), *args], capture_output=True, text=True, check=True)
                return p.stdout.strip()
            _g2("init")
            _g2("config", "user.email", "test@example.invalid")
            _g2("config", "user.name", "Test")
            write_lf_text(
                gdir2 / "verification" / "AUDIT_LOG.md",
                "| Audit ID | Date | Author | Target | Gates | Oracle | Novelty | Verdict | Evidence |\n"
                "|---|---|---|---|---|---|---|---|---|\n"
                "| **AUDIT-001** | 2026-11-20 | a | t | G1 | exact | N1 | **VERIFIED** | ok |\n",
            )
            _g2("add", ".")
            _g2("commit", "-m", "data first")
            write_lf_text(gdir2 / "cartography" / "frontier_portals.md", "# HARKed Plan\n")
            _g2("add", ".")
            _g2("commit", "-m", "harked plan second")
            write_lf_text(
                gdir2 / "verification" / "AUDIT_LOG.md",
                "| Audit ID | Date | Author | Target | Gates | Oracle | Novelty | Verdict | Evidence |\n"
                "|---|---|---|---|---|---|---|---|---|\n"
                "| **AUDIT-001** | 2026-11-20 | a | t | G1 | exact | N1 | **VERIFIED** | ok typo fix |\n",
            )
            _g2("add", ".")
            _g2("commit", "-m", "data typo edit third")
            r_pre_bypass_a = run_audit_check(gdir2, prereg_check=True)
            _req(not r_pre_bypass_a["passed"] and r_pre_bypass_a["prereg_check"]["passed"] is False,
                 f"data->plan->typo HARKing bypass A not caught: {r_pre_bypass_a}")

            # Bypass C regression: plan + data bundled in single commit MUST fail!
            gdir3 = root / "git_prereg_bulk"
            gdir3.mkdir()
            def _g3(*args: str) -> str:
                p = subprocess.run(["git", "-C", str(gdir3), *args], capture_output=True, text=True, check=True)
                return p.stdout.strip()
            _g3("init")
            _g3("config", "user.email", "test@example.invalid")
            _g3("config", "user.name", "Test")
            write_lf_text(gdir3 / "cartography" / "frontier_portals.md", "# Plan\n")
            write_lf_text(
                gdir3 / "verification" / "AUDIT_LOG.md",
                "| Audit ID | Date | Author | Target | Gates | Oracle | Novelty | Verdict | Evidence |\n"
                "|---|---|---|---|---|---|---|---|---|\n"
                "| **AUDIT-001** | 2026-11-20 | a | t | G1 | exact | N1 | **VERIFIED** | ok |\n",
            )
            _g3("add", ".")
            _g3("commit", "-m", "bulk commit")
            r_pre_bypass_c = run_audit_check(gdir3, prereg_check=True)
            _req(not r_pre_bypass_c["passed"] and r_pre_bypass_c["prereg_check"]["passed"] is False,
                 f"bulk single-commit bypass C not caught: {r_pre_bypass_c}")

    def test_12_v12_lean4_hardening_manifests_and_cs09_to_cs11(self) -> None:
        """v1.2: T-12 + multiline skipKernelTC + Lean 4.22 public import + .partial non-FP + Comparator/Manifest + CS-09..11."""
        from aletheia.audit_check import audit_lean4_source, validate_comparator_config, validate_pinned_manifest
        from aletheia.strict_io import canonical_sha256_bytes

        # 1. T-12 char quote '"' before multiline debug.skipKernelTC + multiline partial\n def + axiom + sorryAx/ofReduceBool/trustCompiler
        evasive = (
            "def q : Char := '\"'\n"
            "set_option\n  debug.skipKernelTC\n  true in\n"
            "partial\n  def inf_loop (n : Nat) : Nat := inf_loop n\n"
            "axiom bogus : False\n"
            "def a := sorryAx\n"
            "def b := Lean.ofReduceBool\n"
            "def c := Lean.trustCompiler\n"
            "public\n  import Mathlib.Data.Rat.Basic\n"
        )
        res_ev = audit_lean4_source(evasive, allow_non_init_imports=False)
        codes_ev = {f["code"] for f in res_ev["findings"]}
        _req(
            not res_ev["clean"]
            and {
                "LEAN4_SKIP_KERNEL_TC",
                "LEAN4_PARTIAL",
                "LEAN4_AXIOM",
                "LEAN4_SORRY_AX",
                "LEAN4_OF_REDUCE_BOOL",
                "LEAN4_TRUST_COMPILER",
                "LEAN4_NON_INIT_IMPORT",
            }.issubset(codes_ev),
            f"v1.2 Lean 4 escapes missed: {codes_ev}",
        )

        # 2. Zero false positives on dot-projection `.partial` + `@[csimp]` notice + project imports + ExistsImplication
        clean_v12 = (
            "public import Init.Core\n"
            "private import MyProj.Spec\n"
            "theorem SmoothShell.partial (hv : Nat) : hv = hv := rfl\n"
            "def step := hv.partial (1, 0)\n"
            "@[csimp] theorem exec_eq : True := trivial\n"
            "theorem vac : ∃ x : Nat, x = 0 → x = 1 := ⟨1, by omega⟩\n"
        )
        res_ok = audit_lean4_source(clean_v12, allow_non_init_imports=False, allow_project_imports=("MyProj",))
        notice_codes = {n["code"] for n in res_ok["notices"]}
        _req(
            res_ok["clean"]
            and "LEAN4_CSIMP_REWRITE_NOTICE" in notice_codes
            and "LEAN4_EXISTS_IMPLICATION_NOTICE" in notice_codes,
            f"v1.2 clean Lean 4 failed or missed notices: {res_ok}",
        )

        # 3. Lean 4.22 `public import` forbidden challenge module caught + Comparator enable_nanoda + Pinned Manifest
        with tempfile.TemporaryDirectory(prefix="aletheia_t_v12_") as td:
            root = Path(td)
            write_lf_text(root / "Chl.lean", "theorem main : True := by sorry\n")
            write_lf_text(root / "SolGood.lean", "theorem main : True := trivial\n")
            write_lf_text(root / "SolCheat.lean", "public import Chl\ntheorem main : True := Chl.main\n")

            cfg_good = root / "comp_good.json"
            write_lf_text(
                cfg_good,
                json.dumps({
                    "challenge_module": "Chl",
                    "solution_module": "SolGood",
                    "theorem_names": ["main"],
                    "permitted_axioms": ["propext", "Classical.choice", "Quot.sound"],
                    "enable_nanoda": True,
                }) + "\n",
            )
            _req(validate_comparator_config(cfg_good, lean_root=root, require_nanoda=True)["passed"], "good comparator failed")

            cfg_no_nanoda = root / "comp_nonanoda.json"
            write_lf_text(
                cfg_no_nanoda,
                json.dumps({
                    "challenge_module": "Chl",
                    "solution_module": "SolGood",
                    "theorem_names": ["main"],
                    "permitted_axioms": ["propext", "Classical.choice", "Quot.sound"],
                    "enable_nanoda": False,
                }) + "\n",
            )
            r_nn = validate_comparator_config(cfg_no_nanoda, lean_root=root, require_nanoda=True)
            _req(not r_nn["passed"], f"enable_nanoda=false must fail strict comparator check: {r_nn}")

            cfg_cheat = root / "comp_cheat.json"
            write_lf_text(
                cfg_cheat,
                json.dumps({
                    "challenge_module": "Chl",
                    "solution_module": "SolCheat",
                    "theorem_names": ["main"],
                    "permitted_axioms": ["propext", "Classical.choice", "Quot.sound"],
                    "enable_nanoda": True,
                }) + "\n",
            )
            r_ch = validate_comparator_config(cfg_cheat, lean_root=root, require_nanoda=True)
            _req(not r_ch["passed"] and any("LEAN4_FORBIDDEN_CHALLENGE_IMPORT" in e for e in r_ch["errors"]),
                 f"public import of challenge module not caught: {r_ch}")

            # AUDIT-040 regression #2: absolute-path escape in solution_module MUST fail!
            outside_clean = root.parent / "outside_clean_aletheia_test.lean"
            write_lf_text(outside_clean, "theorem main : True := trivial\n")
            try:
                cfg_abs = root / "comp_abs.json"
                write_lf_text(
                    cfg_abs,
                    json.dumps({
                        "challenge_module": "Chl",
                        "solution_module": str(outside_clean.with_suffix("")),
                        "theorem_names": ["main"],
                        "permitted_axioms": ["propext", "Classical.choice", "Quot.sound"],
                        "enable_nanoda": True,
                    }) + "\n",
                )
                r_abs = validate_comparator_config(cfg_abs, lean_root=root, require_nanoda=True)
                _req(not r_abs["passed"] and "INVALID_OR_MISSING_SOLUTION_MODULE" in r_abs["errors"],
                     f"absolute-path solution_module escape not caught: {r_abs}")
            finally:
                outside_clean.unlink(missing_ok=True)

            # Pinned manifest: CORE_MANIFEST.json (SHA-256) + SafeVerify (40-hex commit SHA) + path traversal block
            sol_sha = canonical_sha256_bytes((root / "SolGood.lean").read_bytes())
            mf_good = root / "CORE_MANIFEST.json"
            write_lf_text(
                mf_good,
                json.dumps({"files": {"SolGood.lean": sol_sha}, "pins": {"SafeVerify": {"commit": "a" * 40}}}) + "\n",
            )
            r_mf_ok = validate_pinned_manifest(mf_good, root=root)
            _req(r_mf_ok["passed"] and r_mf_ok["files_verified"] == 1 and r_mf_ok["commits_verified"] == 1, f"good manifest failed: {r_mf_ok}")

            mf_bad = root / "BAD_MANIFEST.json"
            write_lf_text(
                mf_bad,
                json.dumps({"files": {"SolGood.lean": "0" * 64, "../escape.txt": sol_sha}, "pins": {"SafeVerify": {"commit": "short"}}}) + "\n",
            )
            r_mf_bad = validate_pinned_manifest(mf_bad, root=root)
            _req(not r_mf_bad["passed"] and len(r_mf_bad["errors"]) == 3, f"tampered manifest not fully caught: {r_mf_bad}")

            # AUDIT-040 regression #3: valid commit + wrong-typed files/entries/pins MUST fail closed!
            mf_corrupt = root / "CORRUPT_TYPES_MANIFEST.json"
            write_lf_text(
                mf_corrupt,
                json.dumps({"commit": "a" * 40, "files": "corrupted", "entries": "corrupted", "pins": "corrupted"}) + "\n",
            )
            r_mf_corrupt = validate_pinned_manifest(mf_corrupt, root=root)
            _req(
                not r_mf_corrupt["passed"]
                and {"INVALID_FILES_SECTION_TYPE", "INVALID_ENTRIES_SECTION_TYPE", "INVALID_PINS_SECTION_TYPE"}.issubset(
                    set(r_mf_corrupt["errors"])
                ),
                f"corrupt section types not caught: {r_mf_corrupt}",
            )

            # 4. Diagnose CS-09, CS-10 (both Python scatter_reduce_ mean & JSON), CS-11
            ws = root / "cs_v12_ws"
            init_workspace(ws, domain="dynamics")
            write_lf_text(
                ws / "probes" / "dynamics" / "demo_bug.py",
                "def agg(t, idx, src):\n    return t.scatter_reduce_('mean', idx, src, include_self=False)\n",
            )
            write_lf_text(
                ws / "probes" / "dynamics" / "eval_flags.json",
                json.dumps({
                    "asymptotic_claim": True,
                    "finite_sample_checked": False,
                    "unit_gauge_invariant": False,
                }) + "\n",
            )
            rc_d, out_d, _ = _run_cli(["diagnose", str(ws), "--json"])
            _req(rc_d == 1, f"CS-09..11 poison should return rc=1, got {rc_d}")
            d_obj = json.loads(out_d)
            by_id = {p["id"]: p for p in d_obj["patterns"]}
            for cid in ("CS-09", "CS-10", "CS-11"):
                _req(by_id[cid]["status"] == "ALERT", f"{cid} did not ALERT: {by_id[cid]}")

    def test_13_v13_cli_extend_and_operator_calculus(self) -> None:
        """v1.3: ALETHEIA-CLI-01 repeatable --allow-project-import + 8-glyph `aletheia calculus` CLI."""
        with tempfile.TemporaryDirectory(prefix="aletheia_v13_") as td:
            root = Path(td)

            # 1. ALETHEIA-CLI-01 regression: repeated --allow-project-import A --allow-project-import B accumulates BOTH
            lean_dir = root / "lean_multi"
            write_lf_text(
                lean_dir / "Multi.lean",
                "\n".join([
                    "import Init.Data.Nat.Basic",
                    "import AlphaPkg.Core",
                    "import BetaPkg.Aux",
                    "theorem ok : 1 + 1 = 2 := rfl",
                ]) + "\n",
            )
            rc_rep, out_rep, err_rep = _run_cli([
                "audit-check", str(lean_dir), "--lean-audit",
                "--allow-project-import", "AlphaPkg",
                "--allow-project-import", "BetaPkg",
                "--json",
            ])
            _req(rc_rep == 0, f"repeated --allow-project-import should accumulate both prefixes: rc={rc_rep} out={out_rep} err={err_rep}")
            rep_obj = parse_strict_json_text(out_rep)
            _req(
                rep_obj["passed"]
                and rep_obj["lean_audit"]["clean"]
                and len(rep_obj["lean_audit"]["findings"]) == 0,
                f"expected clean lean audit: {rep_obj}",
            )

            # Single flag with multiple prefixes must also continue to work
            rc_multi, out_multi, _ = _run_cli([
                "audit-check", str(lean_dir), "--lean-audit",
                "--allow-project-import", "AlphaPkg", "BetaPkg",
                "--json",
            ])
            _req(rc_multi == 0 and parse_strict_json_text(out_multi)["passed"], "multi-arg --allow-project-import failed")

            # Negative control: omitting BetaPkg must fail closed on BetaPkg.Aux
            rc_one, out_one, _ = _run_cli([
                "audit-check", str(lean_dir), "--lean-audit",
                "--allow-project-import", "AlphaPkg",
                "--json",
            ])
            one_obj = parse_strict_json_text(out_one)
            _req(
                rc_one == 1
                and not one_obj["passed"]
                and any(
                    f["code"] == "LEAN4_NON_INIT_IMPORT" and "BetaPkg.Aux" in f["excerpt"]
                    for f in one_obj["lean_audit"]["findings"]
                ),
                f"omitted BetaPkg must fail closed on BetaPkg.Aux: {one_obj}",
            )

            # 2. `aletheia calculus --list --json` (strict zero-float JSON)
            rc_ls, out_ls, err_ls = _run_cli(["calculus", "--list", "--json"])
            _req(rc_ls == 0, f"calculus --list failed: rc={rc_ls} err={err_ls}")
            ls_obj = parse_strict_json_text(out_ls, allow_float=False)
            _req(ls_obj["passed"] is True and ls_obj["glyph_count"] == 8, f"unexpected list payload: {ls_obj}")
            _req(
                ls_obj["collision_audit"]["lean4_corpus_files_scanned"] == 227540
                and ls_obj["collision_audit"]["lean4_hits_across_selected_glyphs"] == 0,
                f"unexpected collision audit: {ls_obj['collision_audit']}",
            )
            glyph_chars = [g["glyph"] for g in ls_obj["glyphs"]]
            _req(glyph_chars == ["⧄", "⧅", "⦷", "⟠", "⧇", "⦺", "⩩", "⫩"], f"glyph order mismatch: {glyph_chars}")

            # 3. `aletheia calculus --eval EXPR --json` (Unicode & ASCII parity + exact arithmetic)
            eval_pairs = [
                ("⦺(L_odd ⦷ chi1) ⩩ (1, 2, 1)", "(+-0)(L_odd (||) chi1) =#= (1, 2, 1)", "bool", True),
                ("N1 ⟠ G_mult ⩩ -1/12", "N1 <=> G_mult =#= -1/12", "bool", True),
                ("(M ⧄ D) ⧄ C_after_D ⩩ M ⧄ (D | C)", "(M |/| D) |/| C_after_D =#= M |/| (D | C)", "bool", True),
                ("1/2 + 1/3", "1/2 + 1/3", "rational", "5/6"),
                ("1/2 ⩩ 1/3", "1/2 =#= 1/3", "bool", False),
            ]
            for u_expr, a_expr, exp_type, exp_val in eval_pairs:
                rc_u, out_u, err_u = _run_cli(["calculus", "--eval", u_expr, "--json"])
                rc_a, out_a, err_a = _run_cli(["calculus", "--eval", a_expr, "--json"])
                want_rc = 1 if exp_val is False else 0
                _req(rc_u == want_rc and rc_a == want_rc, f"eval rc for {u_expr!r}/{a_expr!r}: {rc_u}/{rc_a}, want {want_rc}: {err_u} {err_a}")
                obj_u = parse_strict_json_text(out_u, allow_float=False)
                obj_a = parse_strict_json_text(out_a, allow_float=False)
                _req(
                    obj_u["value_type"] == exp_type and obj_u["value"] == exp_val
                    and obj_a["value_type"] == exp_type and obj_a["value"] == exp_val,
                    f"eval mismatch for {u_expr!r}: u={obj_u}, a={obj_a}",
                )

            # Negative controls on `--eval`: float literal, empty string, unbound identifier must fail with rc=2
            for bad_expr, exp_code in [("0.5 + 0.5", "LEX_ERR"), ("   ", "EMPTY_EXPRESSION"), ("no_such_var ⩩ 0", "UNBOUND_VAR")]:
                rc_b, out_b, _ = _run_cli(["calculus", "--eval", bad_expr, "--json"])
                _req(rc_b == 2, f"bad expr {bad_expr!r} should exit rc=2, got {rc_b}")
                err_obj = parse_strict_json_text(out_b, allow_float=False)
                _req(err_obj["status"] == "ERROR" and err_obj["code"] == exp_code, f"bad error payload: {err_obj}")

            # 4. `aletheia calculus --self-test --json` (strict zero-float JSON, 13 theorems, 6/6 commutator probes)
            rc_st, out_st, err_st = _run_cli(["calculus", "--self-test", "--json"])
            _req(rc_st == 0, f"calculus --self-test failed: rc={rc_st} err={err_st}")
            st_obj = parse_strict_json_text(out_st, allow_float=False)
            _req(
                st_obj["passed"] is True
                and st_obj["verdict"] == "ALETHEIA_OPERATOR_CALCULUS_ALL_LAWS_VERIFIED"
                and st_obj["compressed_expedition_theorems"]["theorems_verified"] == 13
                and len(st_obj["commutator_discovery_probes"]) == 6,
                f"self-test payload incomplete: {st_obj}",
            )

    def test_14_v14_local_wrappers_strict_json_ancestors_and_cs12(self) -> None:
        """v1.4: AST local refusal-wrapper detection, loads_strict_json/JSONL, --strict-ancestors, and CS-12."""
        import os
        import stat
        from aletheia import (
            __version__,
            audit_ancestor_dir_permissions,
            discover_local_refusal_wrappers,
            load_strict_jsonl_file,
            loads_strict_json,
            verify_ancestor_dir_modes,
        )
        from aletheia.mutator import discover_mutant_sites, run_mutation_suite

        _req(tuple(int(p) for p in __version__.split(".")) >= (1, 4, 0), f"expected version >= 1.4.0, got {__version__}")

        # 1. AST local refusal-wrapper auto-detection (`PR1-B4`: `_req`, `_fail_if`, `_guard_ret`)
        with tempfile.TemporaryDirectory(prefix="aletheia_v14_") as td:
            root = Path(td)
            wrap_mod = root / "wrapped_gate.py"
            wrap_src = (
                "def _req(cond, code, msg):\n"
                "    '''Local require wrapper.'''\n"
                "    if not cond:\n"
                "        raise ValueError(f'{code}: {msg}')\n\n"
                "def _fail_if(bad, msg):\n"
                "    if bad:\n"
                "        raise ValueError(msg)\n\n"
                "def _guard_ret(cond):\n"
                "    if not bool(cond):\n"
                "        raise ValueError('bad')\n"
                "    return True\n\n"
                "def normalize_opt(s):\n"
                "    if not s:\n"
                "        return None\n"
                "    return s.strip()\n\n"
                "def verify_x(x):\n"
                "    _ = normalize_opt(' ok ')\n"
                "    _req(type(x) is int, 'T', 'not int')\n"
                "    _req(x >= 1, 'B', 'must be >= 1')\n"
                "    _fail_if(x > 10, 'must be <= 10')\n"
                "    _guard_ret(x != 5)\n"
                "    return x\n"
            )
            write_lf_text(wrap_mod, wrap_src)
            tree, sites = discover_mutant_sites(wrap_src, include_boundaries=True)
            local_w = discover_local_refusal_wrappers(tree)
            _req(
                local_w == {"_req": "require", "_fail_if": "reject", "_guard_ret": "require"}
                and "normalize_opt" not in local_w,
                f"unexpected local wrappers detected (normalize_opt must be ignored): {local_w}",
            )
            _req(
                not any("normalize_opt(" in s.original_src for s in sites),
                f"ordinary early-return utility normalize_opt was falsely mutated: {sites}",
            )
            kinds = {s.kind for s in sites}
            _req(
                {"guard_require_call", "guard_reject_call", "boundary_cmp_require", "guard_if_reject"}.issubset(kinds),
                f"missing expected mutant kinds: {kinds}",
            )

            # Test suite killing EVERY local-wrapper mutant & boundary (100%)
            wrap_test_good = root / "test_wrapped_good.py"
            write_lf_text(
                wrap_test_good,
                "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parent))\n"
                "from wrapped_gate import normalize_opt, verify_x\n"
                "if normalize_opt('') is not None or normalize_opt(' a ') != 'a':\n    raise SystemExit(1)\n"
                "if verify_x(1) != 1 or verify_x(10) != 10:\n    raise SystemExit(1)\n"
                "for bad in (True, 0, 11, 5):\n"
                "    try:\n        verify_x(bad)\n        raise SystemExit(2)\n"
                "    except ValueError:\n        pass\n",
            )
            m_ok = run_mutation_suite(
                wrap_mod,
                "python3 -I -O -B test_wrapped_good.py",
                work_root=root,
                add_cwd=True,
                include_boundaries=True,
            )
            _req(
                m_ok["passed"]
                and m_ok["survived"] == 0
                and m_ok["total_mutants"] >= 10
                and m_ok["local_wrappers_detected"] == ["_fail_if", "_guard_ret", "_req"],
                f"local-wrapper 100% kill failed: {m_ok}",
            )

            # Weak test omitting `11` & `5` MUST leave surviving mutants on `_fail_if` and `_guard_ret`!
            wrap_test_weak = root / "test_wrapped_weak.py"
            write_lf_text(
                wrap_test_weak,
                "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parent))\n"
                "from wrapped_gate import verify_x\n"
                "if verify_x(1) != 1:\n    raise SystemExit(1)\n",
            )
            m_weak = run_mutation_suite(
                wrap_mod,
                "python3 -I -O -B test_wrapped_weak.py",
                work_root=root,
                add_cwd=True,
                include_boundaries=True,
            )
            _req(not m_weak["passed"] and m_weak["survived"] >= 4, f"weak test should leave local-wrapper survivors: {m_weak}")

            # 2. Strict duplicate-key + no-NaN JSON/JSONL loaders (`loads_strict_json`, `load_strict_jsonl_file`)
            _req(loads_strict_json('{"a": [1, 2], "b": "ok"}') == {"a": [1, 2], "b": "ok"}, "valid strict json failed")
            _req(loads_strict_json("[1, 2, 3]") == [1, 2, 3], "strict json list root failed")
            for bad_json, exp_code in (
                ('{"a": 1, "a": 2}', "JSON_DUPLICATE_KEY"),
                ('{"outer": {"x": 1, "x": 2}}', "JSON_DUPLICATE_KEY"),
                ('{"v": NaN}', "JSON_CONSTANT_FORBIDDEN"),
                ('{"v": Infinity}', "JSON_CONSTANT_FORBIDDEN"),
                ('{"v": -Infinity}', "JSON_CONSTANT_FORBIDDEN"),
            ):
                try:
                    loads_strict_json(bad_json)
                    raise AssertionError(f"bad JSON accepted: {bad_json}")
                except AletheiaError as exc:
                    _req(exc.code == exp_code, f"wrong error code for {bad_json}: {exc.code} != {exp_code}")

            try:
                loads_strict_json('{"x": 1.5}', allow_float=False)
                raise AssertionError("float accepted when allow_float=False")
            except AletheiaError as exc:
                _req(exc.code == "JSON_FLOAT_FORBIDDEN", f"wrong float code: {exc.code}")

            # Strict JSONL: clean, empty 0-byte, whitespace-only tamper, duplicate-key line, NaN line
            jl_ok = root / "clean.jsonl"
            write_lf_text(jl_ok, '{"seq": 1, "ok": true}\n{"seq": 2, "ok": true}\n')
            _req(len(load_strict_jsonl_file(jl_ok)) == 2, "clean jsonl failed")

            jl_empty = root / "empty.jsonl"
            jl_empty.write_bytes(b"")
            _req(load_strict_jsonl_file(jl_empty) == [], "0-byte jsonl should return []")

            jl_ws = root / "ws_tamper.jsonl"
            write_lf_text(jl_ws, "   \n\t\n")
            try:
                load_strict_jsonl_file(jl_ws)
                raise AssertionError("whitespace-only jsonl accepted")
            except AletheiaError as exc:
                _req(exc.code == "JSONL_WHITESPACE_ONLY", f"wrong ws jsonl code: {exc.code}")

            jl_dup_dir = root / "jl_dup_dir"
            write_lf_text(jl_dup_dir / "ledger.jsonl", '{"seq": 1, "reason": "evil", "reason": "ok"}\n')
            r_jldup = run_audit_check(jl_dup_dir)
            _req(
                not r_jldup["passed"]
                and any(e["code"] == "JSON_DUPLICATE_KEY" for e in r_jldup["json_errors"]),
                f"audit-check missed duplicate key in .jsonl: {r_jldup}",
            )

            # 3. Canonical ancestor-directory permission gate (`verify_ancestor_dir_modes`, `--strict-ancestors`)
            good_chain = [("/", 0o755), ("/etc", 0o755), ("/etc/warp", 0o750), ("/etc/warp/keys", 0o700)]
            r_anc_ok = verify_ancestor_dir_modes(good_chain)
            _req(r_anc_ok["passed"] and r_anc_ok["checked_dirs"] == 4, f"good ancestor chain failed: {r_anc_ok}")

            bad_chains: list[tuple[Any, str]] = [
                ([], "EMPTY_DIR_MODES"),
                ([("/", 0o755), ("//etc", 0o755)], "NON_CANONICAL_PATH"),
                ([("/", 0o755), ("/etc/../etc", 0o755)], "NON_CANONICAL_PATH"),
                ([("/", 0o755), ("/etc/./warp", 0o755)], "NON_CANONICAL_PATH"),
                ([("/", 0o755), ("/etc/warp/", 0o755)], "NON_CANONICAL_PATH"),
                ([("/", 0o755), ("/etc\x00/warp", 0o755)], "NON_CANONICAL_PATH"),
                ([("/", 0o755), ("/etc", False)], "INVALID_MODE"),
                ([("/", 0o755), ("/etc", -1)], "INVALID_MODE"),
                ([("/", 0o755), ("/etc", 0o10000)], "INVALID_MODE"),
                ([("/", 0o755), ("/etc", 0o755), ("/etc", 0o750)], "DUPLICATE_PATH"),
                ([("/", 0o755), ("/etc", 0o775)], "WRITABLE_ANCESTOR_MODE"),
                ([("/", 0o755), ("/tmp", 0o1777)], "WRITABLE_ANCESTOR_MODE"),
                ([("/", 0o755), ("/etc/warp/keys", 0o700)], "MISSING_ANCESTOR"),
                ([("/etc", 0o755)], "MISSING_ANCESTOR"),
            ]
            for ch, exp_err in bad_chains:
                r_bad_anc = verify_ancestor_dir_modes(ch)
                _req(
                    not r_bad_anc["passed"] and exp_err in r_bad_anc["errors"],
                    f"ancestor gate missed {exp_err} on {ch!r}: {r_bad_anc}",
                )

            # Live CLI `--strict-ancestors`: world-writable 0o777 subdir MUST fail closed (rc=1)
            writable_dir = root / "world_writable"
            writable_dir.mkdir(mode=0o777)
            os.chmod(writable_dir, 0o777)
            write_lf_text(writable_dir / "note.txt", "ok\n")
            rc_sa, out_sa, _ = _run_cli(["audit-check", str(writable_dir), "--strict-ancestors", "--json"])
            sa_obj = loads_strict_json(out_sa, require_object=True)
            _req(
                rc_sa == 1
                and not sa_obj["passed"]
                and "WRITABLE_ANCESTOR_MODE" in sa_obj["ancestor_permissions"]["errors"],
                f"--strict-ancestors failed to reject 0o777 dir: {sa_obj}",
            )

            # Real filesystem audit on CLI_ROOT matches actual stat bits
            repo_anc = audit_ancestor_dir_permissions(CLI_ROOT)
            all_anc_clean = all(
                (stat.S_IMODE(os.stat(d).st_mode) & 0o022) == 0
                for d in [CLI_ROOT.resolve(), *CLI_ROOT.resolve().parents]
            )
            _req(repo_anc["passed"] == all_anc_clean, f"live ancestor audit disagreed with os.stat: {repo_anc}")

            # 4. CS-12 (`Trust-Boundary Shadow`) in `aletheia diagnose` (isolated .py regex vs .json flag workspaces!)
            ws12_py = root / "cs12_py_only"
            init_workspace(ws12_py, domain="systems")
            write_lf_text(
                ws12_py / "probes" / "systems" / "cert_re.py",
                "import re\nSHA256_RE = re.compile(r'^[0-9a-f]{64}$')\n",
            )
            rc_d12p, out_d12p, _ = _run_cli(["diagnose", str(ws12_py), "--json"])
            d12p = loads_strict_json(out_d12p, require_object=True)
            by_id12p = {p["id"]: p for p in d12p["patterns"]}
            _req(
                rc_d12p == 1 and len(d12p["patterns"]) == 12 and by_id12p["CS-12"]["status"] == "ALERT",
                f"CS-12 .py-only `$` regex did not ALERT: {by_id12p.get('CS-12')}",
            )

            # Positive control: `\A...\Z` regex in .py MUST remain CS-12 CLEAR!
            ws12_ok = root / "cs12_py_clean"
            init_workspace(ws12_ok, domain="systems")
            write_lf_text(
                ws12_ok / "probes" / "systems" / "cert_re_ok.py",
                "import re\nSHA256_RE = re.compile(r'\\A[0-9a-f]{64}\\Z')\n",
            )
            rc_d12ok, out_d12ok, _ = _run_cli(["diagnose", str(ws12_ok), "--json"])
            d12ok = loads_strict_json(out_d12ok, require_object=True)
            by_id12ok = {p["id"]: p for p in d12ok["patterns"]}
            _req(
                rc_d12ok == 0 and by_id12ok["CS-12"]["status"] == "CLEAR",
                f"clean \\A...\\Z regex falsely tripped CS-12: {by_id12ok.get('CS-12')}",
            )

            # Isolated .json-only CS-12 workspace
            ws12_json = root / "cs12_json_only"
            init_workspace(ws12_json, domain="systems")
            write_lf_text(
                ws12_json / "probes" / "systems" / "gate_flags.json",
                json.dumps({"escape_hatch_bound": False}) + "\n",
            )
            rc_d12j, out_d12j, _ = _run_cli(["diagnose", str(ws12_json), "--json"])
            d12j = loads_strict_json(out_d12j, require_object=True)
            by_id12j = {p["id"]: p for p in d12j["patterns"]}
            _req(
                rc_d12j == 1 and by_id12j["CS-12"]["status"] == "ALERT",
                f"CS-12 .json-only poison did not ALERT: {by_id12j.get('CS-12')}",
            )

    def test_15_ci_install_step_needs_no_preinstalled_setuptools(self) -> None:
        wf = (CLI_ROOT / ".github" / "workflows" / "aletheia-ci.yml").read_text(encoding="utf-8")
        install_lines = [ln.strip() for ln in wf.splitlines() if "pip install" in ln]
        _req(len(install_lines) >= 1, f"expected an install line in CI, got {install_lines}")
        # `--no-build-isolation` needs setuptools in the runner's own environment, which
        # setup-python does not provide (ModuleNotFoundError: No module named 'setuptools').
        for line in install_lines:
            _req("--no-build-isolation" not in line, f"CI install needs preinstalled setuptools: {line}")
            _req("--no-deps" in line, f"CI install must stay dependency-free: {line}")

        # An in-tree install leaves build/ and *.egg-info in the repo root; the self-audit must not trip on them.
        with tempfile.TemporaryDirectory(prefix="aletheia_t_ci_") as td:
            root = Path(td)
            write_lf_text(root / "README.md", "# demo\n")
            egg = root / "aletheia_method.egg-info"
            write_lf_text(egg / "PKG-INFO", "Metadata-Version: 2.1\nName: aletheia-method\n")
            write_lf_text(egg / "SOURCES.txt", "README.md\naletheia/__init__.py\n")
            write_lf_text(egg / "top_level.txt", "aletheia\n")
            write_lf_text(egg / "entry_points.txt", "[console_scripts]\naletheia = aletheia.cli:main\n")
            write_lf_text(root / "build" / "lib" / "aletheia" / "x.py", "x = 1\n")
            res = run_audit_check(root)
            _req(res["passed"], f"in-tree install artifacts tripped the self-audit: {res['failures']}")

    def test_16_self_audit_ignores_only_its_own_bytecode(self) -> None:
        import importlib.util
        import shutil
        import subprocess

        driver = (
            "import sys\n"
            "root = sys.argv[1]\n"
            "sys.path.insert(0, root)\n"
            "from aletheia.cli import main\n"
            "raise SystemExit(main(['audit-check', root, '--json']))\n"
        )

        def fresh_copy(parent: Path, name: str) -> Path:
            dst = parent / name
            shutil.copytree(CLI_ROOT / "aletheia", dst / "aletheia", ignore=shutil.ignore_patterns("__pycache__"))
            return dst

        def audit(root: Path, *, bytecode: bool) -> dict:
            flags = ["-I"] if bytecode else ["-I", "-B"]
            proc = subprocess.run(
                [sys.executable, *flags, "-c", driver, str(root)],
                capture_output=True, check=False, timeout=120, cwd=str(root),
            )
            _req(proc.stdout.strip() != b"", f"audit printed nothing: {proc.stderr.decode()[-400:]}")
            return json.loads(proc.stdout.decode("utf-8"))

        with tempfile.TemporaryDirectory(prefix="aletheia_t_pyc_") as td:
            parent = Path(td)

            # Bytecode writing ON: the run writes aletheia/__pycache__ while importing, then audits the tree.
            on = fresh_copy(parent, "on")
            r_on = audit(on, bytecode=True)
            written = sorted((on / "aletheia" / "__pycache__").glob("*.pyc"))
            _req(len(written) >= 10, f"control failed: the bytecode-on run wrote only {len(written)} .pyc files")
            _req(r_on["passed"] and r_on["summary"]["pycache_count"] == 0,
                 f"audit failed on bytecode it produced itself: {r_on['failures']} {r_on['pycache_items'][:3]}")

            # Bytecode writing OFF: same verdict.
            off = fresh_copy(parent, "off")
            r_off = audit(off, bytecode=False)
            _req(not (off / "aletheia" / "__pycache__").exists(), "control failed: -B run wrote bytecode")
            _req(r_off["passed"] and r_off["status"] == r_on["status"], f"verdicts differ: {r_off['failures']}")

            # Stale bytecode planted before the run is still reported (loose file, other interpreter tag).
            ghost = fresh_copy(parent, "ghost")
            (ghost / "aletheia" / "__pycache__").mkdir()
            (ghost / "aletheia" / "__pycache__" / "ghost.cpython-39.pyc").write_bytes(b"0000")
            for use_bytecode in (False, True):
                r_ghost = audit(ghost, bytecode=use_bytecode)
                _req(not r_ghost["passed"] and any("ghost.cpython-39.pyc" in it for it in r_ghost["pycache_items"]),
                     f"planted stale pyc not reported (bytecode={use_bytecode}): {r_ghost['pycache_items']}")

            # Bytecode left by an earlier run whose source has since changed is stale: reported.
            stale = fresh_copy(parent, "stale")
            audit(stale, bytecode=True)
            target = stale / "aletheia" / "scaffold.py"
            target.write_bytes(target.read_bytes() + b"\n# edited after the bytecode was written\n")
            stale_cache = Path(importlib.util.cache_from_source(str(target), optimization=""))
            _req(stale_cache.is_file(), "control failed: no cache file for the edited module")
            r_stale = audit(stale, bytecode=False)
            stale_rel = str(stale_cache.relative_to(stale))
            _req(not r_stale["passed"] and r_stale["pycache_items"] == ["aletheia/__pycache__", stale_rel],
                 f"stale cache of an edited module not isolated: {r_stale['pycache_items']}")

    def test_17_init_refuses_to_overwrite_any_existing_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_force_") as td:
            root = Path(td)
            for rel in ("verification/AUDIT_LOG.md", "verification/PROTOCOL.md", "synthesis/.gitkeep"):
                ws = root / rel.replace("/", "_")
                precious = "| **AUDIT-007** | keep me |\n"
                write_lf_text(ws / rel, precious)
                before = sorted(p.relative_to(ws).as_posix() for p in ws.rglob("*"))

                # No aletheia.json here, so only a guard on every target file protects the ledger.
                rc, out, _ = _run_cli(["init", str(ws), "--domain", "spectral", "--json"])
                _req(rc != 0, f"init over existing {rel} returned rc={rc}: {out}")
                _req(rel in out and "WORKSPACE_EXISTS" in out, f"refusal did not name {rel}: {out!r}")
                _req((ws / rel).read_text(encoding="utf-8") == precious, f"{rel} was overwritten without --force")
                after = sorted(p.relative_to(ws).as_posix() for p in ws.rglob("*"))
                _req(after == before, f"refused init still wrote files: {sorted(set(after) - set(before))}")

                with self.assertRaises(AletheiaError) as ctx:
                    init_workspace(ws, domain="spectral")
                _req(ctx.exception.code == "WORKSPACE_EXISTS", f"wrong error code {ctx.exception.code}")

                # --force is the only way through.
                rc_f, out_f, _ = _run_cli(["init", str(ws), "--domain", "spectral", "--force", "--json"])
                _req(rc_f == 0 and json.loads(out_f)["status"] == "INITIALIZED", f"--force init failed: {out_f}")
                _req((ws / rel).read_text(encoding="utf-8") != precious or rel.endswith(".gitkeep"),
                     f"--force did not rewrite {rel}")
                _req((ws / "aletheia.json").is_file(), "--force init did not write aletheia.json")

    def test_18_seeding_is_not_an_unseeded_rng_call(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_seed_") as td:
            root = Path(td)
            seeded = root / "seeded"
            write_lf_text(seeded / "sim.py", "import random\nimport random as rnd\nrandom.seed(42)\nrnd.seed(7)\n")
            r_seeded = run_audit_check(seeded, strict_unseeded=True)
            _req(r_seeded["passed"] and r_seeded["summary"]["unseeded_rng_warning_count"] == 0,
                 f"random.seed(...) was reported as unseeded: {r_seeded['unseeded_rng_warnings']}")

            # Control: a module-level draw is still reported, with or without a seed call before it.
            drawn = root / "drawn"
            write_lf_text(drawn / "sim.py", "import random\nrandom.seed(42)\nx = random.random()\n")
            r_drawn = run_audit_check(drawn, strict_unseeded=True)
            _req(not r_drawn["passed"] and r_drawn["summary"]["unseeded_rng_warning_count"] == 1
                 and r_drawn["unseeded_rng_warnings"][0]["call"] == "random.random()",
                 f"module-level draw no longer flagged: {r_drawn['unseeded_rng_warnings']}")

    def test_19_lean4_unterminated_comment_or_string_fails_closed(self) -> None:
        from aletheia.audit_check import audit_lean4_source

        def codes(src: str) -> list[str]:
            return [f["code"] for f in audit_lean4_source(src)["findings"]]

        open_comment = "/- never closed\ntheorem t : True := by sorry\n"
        res = audit_lean4_source(open_comment)
        _req(not res["clean"], f"unterminated block comment before sorry passed: {res}")
        _req(res["findings"][0] == {"line": 1, "code": "LEAN4_UNTERMINATED_COMMENT", "excerpt": "/- never closed"},
             f"wrong unterminated-comment finding: {res['findings']}")
        _req("LEAN4_UNTERMINATED_COMMENT" in codes("def a := 1\n/- outer /- inner -/ still open\n"),
             "nested comment left open was not reported")
        _req(codes('def s := "never closed\ntheorem t : True := by sorry\n') == ["LEAN4_UNTERMINATED_STRING"],
             "unterminated string was not reported")

        # Controls: terminated comments and strings, openers inside strings and line comments, a char literal.
        for ok_src in (
            "/- closed -/\ndef a := 1\n",
            "/- outer /- inner -/ outer -/\ndef a := 1\n",
            'def s := "text /- not a comment"\ndef a := 1\n',
            "-- /- only a line comment\ndef a := 1\n",
            "def q : Char := '\"'\ndef a := 1\n",
        ):
            _req(audit_lean4_source(ok_src)["clean"], f"false positive on well-formed source: {ok_src!r}")
        _req(codes("/- closed -/ theorem t : True := by sorry\n") == ["LEAN4_SORRY"], "closed comment must not hide code after it")

        # End to end through audit-check --lean-audit.
        with tempfile.TemporaryDirectory(prefix="aletheia_t_lean_open_") as td:
            root = Path(td)
            write_lf_text(root / "Open.lean", open_comment)
            rc, out, _ = _run_cli(["audit-check", str(root), "--lean-audit", "--json"])
            obj = json.loads(out)
            _req(rc == 1 and not obj["passed"] and obj["lean_audit"]["findings"][0]["code"] == "LEAN4_UNTERMINATED_COMMENT",
                 f"audit-check passed an unterminated Lean comment: rc={rc} {obj['failures']}")

    def test_20_audit_log_matches_whole_verdict_tokens_and_needs_rows(self) -> None:
        from aletheia.audit_check import validate_audit_log_markdown

        head = (
            "| Audit ID | Date | Author | Target | Gates | Oracle | Novelty | Verdict | Evidence |\n"
            "|---|---|---|---|---|---|---|---|---|\n"
        )

        def row(verdict: str) -> str:
            return f"| **AUDIT-001** | 2026-11-20 | a | t | G1 | exact | N1 | {verdict} | note |\n"

        with tempfile.TemporaryDirectory(prefix="aletheia_t_log_") as td:
            root = Path(td)

            def check(body: str, **kw) -> dict:
                path = root / "LOG.md"
                write_lf_text(path, body)
                return validate_audit_log_markdown(path, **kw)

            # A negated or embedded verdict is not VERIFIED.
            for bad in ("**NOT VERIFIED**", "NOT VERIFIED", "NOT_VERIFIED", "UNVERIFIED", "not verified", "VERIFIED_PARTIAL"):
                res = check(head + row(bad))
                _req(not res["valid"] and res["verdict_counts"] == {}
                     and [e["code"] for e in res["errors"]] == ["INVALID_VERDICT"],
                     f"{bad!r} was accepted: {res}")

            # Controls: whole tokens, with or without markdown emphasis or a trailing note, are still read.
            for good, token in (
                ("**VERIFIED**", "VERIFIED"),
                ("`FALSIFIED`", "FALSIFIED"),
                ("PARTIAL/FRAGILE", "PARTIAL/FRAGILE"),
                ("**PARTIAL/FRAGILE** (scope: local)", "PARTIAL/FRAGILE"),
                ("NOT_SHOWN", "NOT_SHOWN"),
                ("EXPOSED", "EXPOSED"),
            ):
                res = check(head + row(good))
                _req(res["valid"] and res["verdict_counts"] == {token: 1}, f"{good!r} was not read as {token}: {res}")

            # A ledger with no rows is not valid; one row makes it valid.
            for empty in ("", head, "# Log\n\nNo audits yet.\n"):
                res = check(empty)
                _req(not res["valid"] and res["rows_checked"] == 0
                     and [e["code"] for e in res["errors"]] == ["NO_AUDIT_ROWS"],
                     f"empty ledger accepted: {res}")
            _req(check(head + row("VERIFIED"))["valid"], "one-row ledger rejected")
            _req(check(head, require_rows=False)["valid"], "require_rows=False must still allow an empty ledger")

            # Through audit-check: an explicit empty log fails, a freshly scaffolded workspace still passes.
            ws = root / "ws"
            init_workspace(ws, domain="spectral")
            ledger = ws / "verification" / "AUDIT_LOG.md"
            _req(run_audit_check(ws)["passed"], "fresh workspace with an empty auto-discovered ledger must pass")
            rc, out, _ = _run_cli(["audit-check", str(ws), "--audit-log", str(ledger), "--json"])
            obj = json.loads(out)
            _req(rc == 1 and not obj["passed"] and obj["audit_log"]["errors"][0]["code"] == "NO_AUDIT_ROWS",
                 f"explicit empty --audit-log passed: rc={rc} {obj['failures']}")

    def test_21_calculus_registry_lists_every_commutator_probe_the_self_test_runs(self) -> None:
        from aletheia.calculus import GLYPH_REGISTRY_DATA, run_calculus_self_test

        listed = [p["id"] for p in GLYPH_REGISTRY_DATA["commutator_probes"]]
        ran = list(run_calculus_self_test()["commutator_discovery_probes"].keys())
        _req(listed == ran == ["C1", "C2", "C3", "C4", "C5", "C6"], f"registry {listed} vs self-test {ran}")
        c6 = GLYPH_REGISTRY_DATA["commutator_probes"][-1]
        _req(c6["expression"] and c6["hypothesis"], f"C6 entry is incomplete: {c6}")

    def test_22_collision_figure_is_labelled_as_reported_not_reproduced(self) -> None:
        from aletheia.calculus import GLYPH_REGISTRY_DATA

        prov = GLYPH_REGISTRY_DATA["collision_audit"].get("provenance", "")
        _req("reported" in prov and "not reproduced" in prov, f"registry carries no provenance note: {prov!r}")
        _, out, _ = _run_cli(["calculus", "--list"])
        _req("reported 0 / 227,540" in out and "not reproduced" in out, f"--list does not label the figure: {out[:300]}")

        # The scan script and corpus manifest are not in the repo, so every prose line that states the figure must say so.
        unlabelled = []
        for path in sorted(CLI_ROOT.rglob("*")):
            rel = path.relative_to(CLI_ROOT)
            if not path.is_file() or ".git" in rel.parts or rel.parts[0] == "tests" or path.suffix not in (".py", ".md"):
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "227,540" in line and "reported" not in line.lower():
                    unlabelled.append(f"{rel}:{n}")
        _req(not unlabelled, f"227,540 stated without a 'reported' label at: {unlabelled}")

    def test_23_calculus_eval_exit_code_gates_on_a_false_boolean(self) -> None:
        for expr, rc_want, value in (
            ("1/2 ⩩ 1/2", 0, True),
            ("1/2 =#= 1/3", 1, False),
            ("1/2 + 1/3", 0, "5/6"),
        ):
            for extra in (["--json"], []):
                rc, out, _ = _run_cli(["calculus", "--eval", expr, *extra])
                _req(rc == rc_want, f"{expr!r} {extra}: rc={rc}, want {rc_want}")
                if extra:
                    _req(parse_strict_json_text(out, allow_float=False)["value"] == value, f"{expr!r}: wrong value {out}")
        # A usage or evaluation error is still rc=2, distinct from a false result.
        rc, _, _ = _run_cli(["calculus", "--eval", "no_such_var ⩩ 0", "--json"])
        _req(rc == 2, f"error must stay rc=2, got {rc}")

    def test_24_calculus_self_test_reports_a_raising_probe_as_failed(self) -> None:
        from unittest import mock

        import aletheia.calculus as calc

        def boom() -> dict:
            raise calc.CalculusError("SINGULAR_SOLVE", "precondition miss")

        clean = calc.run_calculus_self_test()
        _req(clean["passed"] is True and clean["errors"] == [], f"clean self-test must pass with no errors: {clean['errors']}")

        for target, section in (
            ("run_probe_c2_nested_shadow_and_associator", "C2"),
            ("run_compressed_theorems", "compressed_theorems"),
            ("verify_glyph_registry", "glyph_registry"),
        ):
            with mock.patch.object(calc, target, boom):
                res = calc.run_calculus_self_test()
                _req(
                    res["passed"] is False and res["verdict"] == "FAILED"
                    and [(e["section"], e["code"]) for e in res["errors"]] == [(section, "SINGULAR_SOLVE")],
                    f"{target}: raised error not reported as FAILED: {res['verdict']} {res['errors']}",
                )
                _req(
                    res["commutator_discovery_probes"]["C6"]["all_verified"] is True or section == "glyph_registry",
                    f"{target}: the other probes must still run",
                )
                rc, out, _ = _run_cli(["calculus", "--self-test", "--json"])
                _req(rc == 1, f"{target}: CLI must exit 1 for a failed section, got {rc}")
                _req(parse_strict_json_text(out, allow_float=False)["verdict"] == "FAILED", f"{target}: CLI verdict")

    def test_25_latch_result_carries_no_tautological_gate_field(self) -> None:
        from fractions import Fraction

        from aletheia.ratchet import exact_pythagorean_latch_check

        res = exact_pythagorean_latch_check(
            proxy_before=Fraction(36), proxy_after=Fraction(0),
            outside_before=Fraction(0), outside_after=Fraction(144),
        )
        # `pythagorean_exact` compared proxy_after + outside_after with itself and was true for every input.
        _req("pythagorean_exact" not in res, f"always-true field is back: {res}")
        _req(res["decision"] == "LATCH_HALT" and res["total_after"] == "144" and res["outside_inflated"] is True, f"latch changed: {res}")
        _, out, _ = _run_cli(["ratchet", "--demo", "--json"])
        _req("pythagorean_exact" not in out, "the demo output still carries pythagorean_exact")

    def test_26_mutator_reports_when_max_mutants_truncates(self) -> None:
        fixture = CLI_ROOT / "tests" / "fixture_verifier.py"
        cmd = "python3 fixture_verifier_test.py"
        full = run_mutation_suite(fixture, cmd, work_root=fixture.parent, include_boundaries=True)
        n = full["total_mutants"]
        _req(n > 3 and full["truncated"] is False and "warning" not in full and full["mutants_discovered"] == n,
             f"untruncated run must say so: {n} {full['truncated']} {full.get('warning')}")

        cut = run_mutation_suite(fixture, cmd, work_root=fixture.parent, include_boundaries=True, max_mutants=3)
        _req(
            cut["truncated"] is True and cut["total_mutants"] == 3 and cut["mutants_discovered"] == n
            and cut["verdict"] == "NOT_SHOWN" and cut["passed"] is False
            and f"{n - 3} of {n}" in cut["warning"],
            f"truncation not reported as NOT_SHOWN: {cut.get('verdict')} {cut.get('passed')} {cut.get('warning')}",
        )

        # The command line shows it too, in JSON and in the text summary, and exits 1 (NOT_SHOWN).
        args = ["mutate", str(fixture), "--test-cmd", cmd, "--max-mutants", "3"]
        rc, out, _ = _run_cli(args + ["--json"])
        obj = json.loads(out)
        _req(rc == 1 and obj["truncated"] is True and obj["verdict"] == "NOT_SHOWN" and "warning" in obj,
             f"JSON output hides NOT_SHOWN truncation: rc={rc} {list(obj)}")
        rc, out, _ = _run_cli(args)
        _req(rc == 1 and "warning: max_mutants=3" in out and "NOT_SHOWN" in out, f"text output hides NOT_SHOWN truncation: {out[:400]}")

    def test_27_init_reports_a_regular_file_in_the_way_of_a_directory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_initfile_") as td:
            root = Path(td)
            for blocker in ("verification", "probes", "cartography"):
                ws = root / f"ws_{blocker}"
                ws.mkdir()
                (ws / blocker).write_text("not a directory\n", encoding="utf-8")
                for extra in ([], ["--force"]):
                    rc, out, err = _run_cli(["init", str(ws), "--domain", "spectral", "--json", *extra])
                    obj = json.loads(out) if out.strip() else {}
                    _req(
                        rc == 2 and obj.get("code") == "WORKSPACE_EXISTS" and blocker in obj.get("message", ""),
                        f"{blocker} {extra}: rc={rc} out={out!r} err={err!r}",
                    )
                    _req((ws / blocker).read_text(encoding="utf-8") == "not a directory\n", f"{blocker} file was touched")
                    _req(sorted(p.name for p in ws.iterdir()) == [blocker], f"{blocker} {extra}: partial scaffold left behind")
            # The target itself being a regular file takes the same path.
            target = root / "afile"
            target.write_text("x", encoding="utf-8")
            rc, out, _ = _run_cli(["init", str(target), "--json"])
            _req(rc == 2 and json.loads(out)["code"] == "WORKSPACE_EXISTS", f"file target: rc={rc} out={out!r}")
            # Control: a clean directory still initializes.
            rc, out, _ = _run_cli(["init", str(root / "clean"), "--json"])
            _req(rc == 0 and json.loads(out)["status"] == "INITIALIZED", f"clean init failed: rc={rc} out={out!r}")

    def test_28_r4_is_three_modes_everywhere_it_is_stated(self) -> None:
        import re

        from aletheia.audit_check import run_r4_script_check

        # The code is the reference: the check runs three modes and the scaffold writes three.
        with tempfile.TemporaryDirectory(prefix="aletheia_t_r4_") as td:
            script = Path(td) / "ok.py"
            write_lf_text(script, 'print("ok")\n')
            res = run_r4_script_check(script)
            _req(sorted(res["modes"]) == ["B", "B_Werror", "O_B"] and res["passed"], f"R4 check modes: {sorted(res['modes'])}")
            ws = Path(td) / "ws"
            init_workspace(ws, domain="spectral")
            cfg = json.loads((ws / "aletheia.json").read_text(encoding="utf-8"))
            _req(cfg["r4_modes"] == ["-I -B", "-I -O -B", "-I -B -W error"], f"scaffold r4_modes: {cfg['r4_modes']}")

        # No document, docstring or example may call it four modes or list a fourth combination as an R4 mode.
        fourth = [
            re.compile(r"(?i)4-mode|all four (isolated|python|execution)|four isolated"),
            re.compile(r"-I -B -W error.{0,12}-I -O -B -W error"),
            re.compile(r"-I -B -W error[^\n]*\n[^\n]*-I -O -B -W error"),
        ]
        stray = []
        for path in sorted(CLI_ROOT.rglob("*")):
            rel = path.relative_to(CLI_ROOT)
            if not path.is_file() or ".git" in rel.parts or rel.parts[0] == "tests" and rel.name != "run_all.py" or path.suffix not in (".py", ".md"):
                continue
            text = path.read_text(encoding="utf-8")
            for pat in fourth:
                if pat.search(text):
                    stray.append(f"{rel}: {pat.pattern}")
        _req(not stray, f"a fourth R4 mode is still stated: {stray}")

    def test_29_demo_stage5_is_labelled_simulated(self) -> None:
        import importlib.util

        demo = CLI_ROOT / "examples" / "worked_resonance_cycle" / "run_demo.py"
        spec = importlib.util.spec_from_file_location("aletheia_worked_demo", demo)
        _req(spec is not None and spec.loader is not None, "cannot load the demo")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.modules.pop(spec.name, None)
        stage5 = mod.run_all()["stages"][4]
        _req("simulated" in stage5["name"].lower(), f"stage 5 name does not say simulated: {stage5['name']}")
        _req(stage5["mutants_total"] == 3 and stage5["mutants_killed"] == 3, "stage 5 counts changed")

        # The demo uses skip flags in the certifier, not the AST mutator, so no text may call these mutations live.
        for path in (demo, demo.with_name("README.md")):
            text = path.read_text(encoding="utf-8").lower()
            _req("live refusal-site" not in text and "3 live" not in text and "live mutation" not in text,
                 f"{path.name} still calls the simulated mutations live")
            _req("simulated" in text and "ast mutator" in text, f"{path.name} does not say the mutations are simulated")

    def test_30_n2_prior_art_hint_ignores_bare_confirmed_and_beyond(self) -> None:
        from aletheia.audit_check import validate_audit_log_markdown

        head = (
            "| Audit ID | Date | Author | Target | Gates | Oracle | Novelty | Verdict | Evidence |\n"
            "|---|---|---|---|---|---|---|---|---|\n"
        )

        def warn_codes(gates: str, evidence: str) -> list[str]:
            with tempfile.TemporaryDirectory(prefix="aletheia_t_n2_") as td:
                path = Path(td) / "LOG.md"
                write_lf_text(path, head + f"| AUDIT-001 | 2026-11-20 | a | t | {gates} | exact | N2 | VERIFIED | {evidence} |\n")
                res = validate_audit_log_markdown(path)
                _req(res["valid"], f"row rejected: {res['errors']}")
                return [w["code"] for w in res["warnings"]]

        # Ordinary words are not a prior-art note.
        for text in ("confirmed by the verifier", "goes beyond the sketch", "Confirmed beyond doubt"):
            _req(warn_codes("G1", text) == ["N2_MISSING_PRIOR_ART_NOTE"], f"{text!r} counted as a prior-art note")
        # Controls: a real prior-art cue or a G9 entry still satisfies the check.
        for gates, text in (("G1", "prior-art checked against arXiv"), ("G1", "no upstream result found"), ("G1, G9", "note")):
            _req(warn_codes(gates, text) == [], f"{gates!r}/{text!r} lost its prior-art credit")

    def test_31_comparator_rejects_one_module_as_challenge_and_solution(self) -> None:
        from aletheia.audit_check import validate_comparator_config

        base = {
            "theorem_names": ["main"],
            "permitted_axioms": ["propext", "Classical.choice", "Quot.sound"],
            "enable_nanoda": True,
        }
        with tempfile.TemporaryDirectory(prefix="aletheia_t_cmp_") as td:
            root = Path(td)
            write_lf_text(root / "Same.lean", "theorem main : True := trivial\n")
            write_lf_text(root / "Other.lean", "theorem main : True := trivial\n")

            def check(chl: str, sol: str) -> dict:
                cfg = root / "cfg.json"
                write_lf_text(cfg, json.dumps({**base, "challenge_module": chl, "solution_module": sol}) + "\n")
                return validate_comparator_config(cfg, lean_root=root, require_nanoda=True)

            same = check("Same", "Same")
            _req(
                not same["passed"] and "CHALLENGE_EQUALS_SOLUTION_MODULE:Same" in same["errors"],
                f"challenge == solution accepted: {same}",
            )
            _req(check("Same", "Other")["passed"], "two different modules must still pass")

    def test_32_v20_issue5_imported_wrappers_guards_and_refusal_shapes(self) -> None:
        """v2.0 closes aletheia#5 #1 (imported wrappers + --guards + covered_lines) & #11 (shapes.py + rule.py)."""
        with tempfile.TemporaryDirectory(prefix="aletheia_t_v2_mut_") as td:
            root = Path(td)
            write_lf_text(root / "helpers.py", "def need(ok, msg):\n    if not ok:\n        raise ValueError(msg)\n")
            write_lf_text(
                root / "checker_ext.py",
                'from helpers import need\n'
                'def accept(d):\n'
                '    need(isinstance(d, dict), "not dict")\n'
                '    need(d.get("ok") == 1, "bad")\n'
                '    return True\n',
            )
            write_lf_text(
                root / "test_ext.py",
                'import unittest, checker_ext\n'
                'class T(unittest.TestCase):\n'
                '    def test_all(self):\n'
                '        self.assertTrue(checker_ext.accept({"ok": 1}))\n'
                '        with self.assertRaises(ValueError):\n'
                '            checker_ext.accept([])\n'
                '        with self.assertRaises(ValueError):\n'
                '            checker_ext.accept({"ok": 2})\n'
                'if __name__ == "__main__":\n'
                '    unittest.main()\n',
            )
            rc, out, err = _run_cli([
                "mutate", str(root / "checker_ext.py"),
                "--work-root", str(root),
                "--test-cmd", "python3 test_ext.py",
                "--add-cwd", "--json",
            ])
            obj = json.loads(out)
            _req(rc == 0 and obj["passed"] and obj["imported_wrappers_detected"] == ["need"] and obj["covered_lines"] == [3, 4],
                 f"imported wrapper failed: rc={rc} out={out} err={err}")

            # Explicit --guards flag
            write_lf_text(root / "custom_g.py", "def f(x, gate):\n    gate(x > 0, 'neg')\n    return x\n")
            write_lf_text(
                root / "test_cg.py",
                'import unittest, custom_g\n'
                'def g(ok, m):\n    if not ok:\n        raise ValueError(m)\n'
                'class T(unittest.TestCase):\n'
                '    def test_g(self):\n'
                '        self.assertEqual(custom_g.f(1, g), 1)\n'
                '        with self.assertRaises(ValueError):\n            custom_g.f(0, g)\n'
                'if __name__ == "__main__":\n    unittest.main()\n',
            )
            rc_g, out_g, _ = _run_cli([
                "mutate", str(root / "custom_g.py"),
                "--work-root", str(root),
                "--test-cmd", "python3 test_cg.py",
                "--add-cwd", "--guards", "gate", "--json",
            ])
            og = json.loads(out_g)
            _req(rc_g == 0 and og["passed"] and og["explicit_guards"] == ["gate"] and og["total_mutants"] == 2,
                 f"--guards failed: rc={rc_g} out={out_g}")

            # aletheia#5 #11: shapes.py (all 5 refusal shapes) & rule.py
            write_lf_text(
                root / "shapes.py",
                'def a(x):\n    if x < 0:\n        return "REJECTED"\n    return "ok"\n\n'
                'def b(x):\n    if x < 0:\n        return False, "negative"\n    return True, ""\n\n'
                'def c(x):\n    if x < 0:\n        print("bad")\n        raise ValueError(x)\n    return x\n\n'
                'def d(x):\n    if x < 0:\n        return {"admissible": False}\n    return {"admissible": True}\n\n'
                'def e(x):\n    findings = []\n    if x < 0:\n        findings.append("neg")\n    return findings\n',
            )
            _, out_s, _ = _run_cli(["mutate", str(root / "shapes.py"), "--test-cmd", "python3 -c pass", "--json"])
            os_j = json.loads(out_s)
            _req(len(os_j["covered_lines"]) == 5 and os_j["total_mutants"] == 10,
                 f"shapes.py missed refusal shapes: {os_j['covered_lines']} total={os_j['total_mutants']}")

            write_lf_text(
                root / "rule.py",
                'def decide(x):\n    if x == 1:\n        return "against"\n    if x == 2:\n        return "inconclusive"\n    raise ValueError(x)\n',
            )
            _, out_r, _ = _run_cli(["mutate", str(root / "rule.py"), "--test-cmd", "python3 -c pass", "--json"])
            or_j = json.loads(out_r)
            _req(or_j["total_mutants"] == 4 and or_j["covered_lines"] == [2, 4],
                 f"rule.py missed string decisions: {or_j}")

    def test_33_v20_issue5_selfcheck_timeout_and_add_cwd_hint(self) -> None:
        """v2.0 closes aletheia#5 #6 (-I/--add-cwd hint), #7 (BASELINE_TEST_TIMEOUT), and #12 (selfcheck.py 100%)."""
        with tempfile.TemporaryDirectory(prefix="aletheia_t_v2_sc_") as td:
            root = Path(td)
            # #12 selfcheck.py -> 100.0% kill!
            write_lf_text(
                root / "selfcheck.py",
                'import sys\nFAILS = []\n'
                'def check(cond, msg):\n    if not cond:\n        FAILS.append(msg)\n'
                'check(sum(range(5)) == 10, "sum")\n'
                'check(len("abc") == 3, "len")\n'
                'if FAILS:\n    print("FAIL", FAILS)\n    sys.exit(1)\n'
                'print("PASS 2 of 2")\n',
            )
            rc_sc, out_sc, err_sc = _run_cli([
                "mutate", str(root / "selfcheck.py"),
                "--test-cmd", "python3 selfcheck.py", "--json",
            ])
            jsc = json.loads(out_sc)
            _req(rc_sc == 0 and jsc["passed"] and jsc["self_check_mode"] is True and jsc["kill_rate_pct"] == 100.0 and jsc["total_mutants"] == 6,
                 f"selfcheck.py did not reach 100%: rc={rc_sc} out={out_sc} err={err_sc}")

            # #6 -I hint on ModuleNotFoundError
            write_lf_text(root / "m.py", "def f(x):\n    if x < 0:\n        raise ValueError(x)\n    return x\n")
            write_lf_text(root / "tm.py", "import m\nm.f(1)\n")
            rc_6, out_6, _ = _run_cli(["mutate", str(root / "m.py"), "--test-cmd", "python3 tm.py", "--json"])
            j6 = json.loads(out_6)
            _req(rc_6 == 2 and j6["code"] == "BASELINE_TEST_FAILED" and "--add-cwd" in j6["message"] and "-I" in j6["message"],
                 f"missing -I/--add-cwd hint: {j6}")

            # #7 structured BASELINE_TEST_TIMEOUT (no traceback!)
            write_lf_text(root / "slow.py", "import time\ntime.sleep(3)\n")
            rc_7, out_7, err_7 = _run_cli([
                "mutate", str(root / "m.py"), "--test-cmd", "python3 slow.py", "--timeout", "1", "--json",
            ])
            j7 = json.loads(out_7)
            _req(rc_7 == 2 and j7["code"] == "BASELINE_TEST_TIMEOUT" and "Traceback" not in err_7,
                 f"baseline timeout not structured: rc={rc_7} out={out_7} err={err_7}")

    def test_34_v20_issue5_r4_skip_from_random_diagnose_claude_and_lean_raw(self) -> None:
        """v2.0 closes aletheia#5 #2 (-O skip), #5 (\\Z schemas), #8 (root portals), #10 (claude-code), #13 (from random) & B4 raw strings."""
        with tempfile.TemporaryDirectory(prefix="aletheia_t_v2_aud_") as td:
            root = Path(td)
            # #2 R4 unittest skip under -O MUST FAIL!
            write_lf_text(
                root / "skip_o.py",
                'import unittest\nclass T(unittest.TestCase):\n'
                '    @unittest.skipIf(not __debug__, "needs asserts")\n'
                '    def test_g(self):\n        self.assertTrue(True)\n'
                'if __name__ == "__main__":\n    unittest.main()\n',
            )
            rc2, out2, _ = _run_cli(["audit-check", str(root), "--scripts", "skip_o.py", "--json"])
            j2 = json.loads(out2)
            _req(rc2 == 1 and j2["r4_scripts"][0]["skip_parity"] is False and j2["r4_scripts"][0]["passed"] is False,
                 f"-O unittest skip passed R4: rc={rc2} {j2['r4_scripts']}")

            # #13 from random import randint caught by --strict-unseeded
            d13 = root / "rng13"
            d13.mkdir()
            write_lf_text(d13 / "fromimp.py", "from random import randint as r_int\nprint(r_int(1, 6))\n")
            rc13, out13, _ = _run_cli(["audit-check", str(d13), "--strict-unseeded", "--json"])
            j13 = json.loads(out13)
            _req(rc13 == 1 and j13["summary"]["unseeded_rng_warning_count"] == 1,
                 f"from random import randint missed: rc={rc13} {j13['unseeded_rng_warnings']}")

            # #8 diagnose accepts root frontier_portals.md
            d8 = root / "diag8"
            d8.mkdir()
            write_lf_text(d8 / "frontier_portals.md", "# Portal 1: Alpha\n" + ("x" * 1300) + "\n# Portal 2: Beta\n")
            rc8, out8, _ = _run_cli(["diagnose", str(d8), "--json"])
            j8 = json.loads(out8)
            _req(rc8 == 0 and j8["overall_status"] == "HEALTHY", f"root frontier_portals.md failed diagnose: {j8}")

            # #10 claude-code install plugin.json paths all exist in dest
            d10 = root / "cc10"
            d10.mkdir()
            rc10, _, _ = _run_cli(["install", "--target", "claude-code", "--dest", str(d10)])
            pj = json.loads((d10 / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
            listed = list(pj.get("commands", [])) + list(pj.get("agents", []))
            missing = [p for p in listed if not (d10 / p).is_file()]
            _req(rc10 == 0 and len(listed) == 3 and not missing, f"claude-code plugin.json broken paths: listed={listed} missing={missing}")

            # #5 schemas use (?!\n)$ everywhere (rejecting trailing \n in Python re)
            import re
            for sf in sorted((CLI_ROOT / "schemas").glob("*.json")):
                sobj = json.loads(sf.read_text(encoding="utf-8"))
                def _check_pats(x: object) -> None:
                    if isinstance(x, dict):
                        p = x.get("pattern")
                        if isinstance(p, str):
                            _req(p.endswith("(?!\\n)$"), f"{sf.name} pattern lacks (?!\\n)$: {p!r}")
                            _req(re.search(p, "AUDIT-001\n") is None and re.search(p, "2026-11-21\n") is None,
                                 f"{sf.name} pattern matched trailing newline: {p!r}")
                        for v in x.values():
                            _check_pats(v)
                    elif isinstance(x, list):
                        for v in x:
                            _check_pats(v)
                _check_pats(sobj)

            # PR #7 B4 Lean 4 raw string r#"has " quote"# clean + sorry still caught
            from aletheia.audit_check import audit_lean4_source
            lean_raw_ok = audit_lean4_source('def s := r#"has " quote"#\ntheorem ok : True := trivial\n')
            lean_raw_sorry = audit_lean4_source('def s := r#"has " quote"#\ntheorem bad : True := by sorry\n')
            lean_raw_unclosed = audit_lean4_source('def s := r#"unclosed\ntheorem ok : True := trivial\n')
            _req(lean_raw_ok["clean"] is True, f"raw string false positive: {lean_raw_ok}")
            _req(not lean_raw_sorry["clean"] and lean_raw_sorry["findings"][0]["code"] == "LEAN4_SORRY",
                 f"sorry after raw string missed: {lean_raw_sorry}")
            _req(not lean_raw_unclosed["clean"] and lean_raw_unclosed["findings"][0]["code"] == "LEAN4_UNTERMINATED_STRING",
                 f"unclosed raw string missed: {lean_raw_unclosed}")

    def test_35_v20_cli_gate_v2_and_safety_scan(self) -> None:
        """v2.x CLI subcommands: gate-v2 --self-test, safety-scan, audit-check --safety-scan, version 2.1.0."""
        from aletheia import __version__
        _req(__version__ == "2.1.0", f"expected version 2.1.0, got {__version__}")

        rc_g, out_g, _ = _run_cli(["gate-v2", "--self-test", "--json"])
        jg = parse_strict_json_text(out_g, allow_float=False)
        _req(
            rc_g == 0
            and jg["passed"] is True
            and jg["verdict"] == "ALETHEIA_V2_GATES_VERIFIED"
            and isinstance(jg.get("checks"), dict)
            and len(jg["checks"]) >= 19
            and all(v is True for v in jg["checks"].values()),
            f"gate-v2 --self-test failed: rc={rc_g} {jg}",
        )

        with tempfile.TemporaryDirectory(prefix="aletheia_t_v2_saf_") as td:
            root = Path(td)
            write_lf_text(root / "bad.sh", 'rm -rf "$TARGET"\n')
            rc_s, out_s, _ = _run_cli(["safety-scan", str(root), "--json"])
            js = json.loads(out_s)
            _req(rc_s == 1 and js["clean"] is False and js["gap_ids_present"] == ["CYA-GAP-03"],
                 f"safety-scan failed: rc={rc_s} {js}")

            rc_a, out_a, _ = _run_cli(["audit-check", str(root), "--safety-scan", "--json"])
            ja = json.loads(out_a)
            _req(rc_a == 1 and ja["summary"]["safety_findings_count"] == 1,
                 f"audit-check --safety-scan failed: rc={rc_a} {ja['summary']}")

            # Missing target yields structured AletheiaError (exit 2), never raw traceback
            rc_m, out_m, _ = _run_cli(["safety-scan", str(root / "missing"), "--json"])
            jm = json.loads(out_m)
            _req(rc_m == 2 and jm.get("code") == "SAFETY_SCAN_ERROR", f"expected SAFETY_SCAN_ERROR: rc={rc_m} {jm}")

            # Binary/undecodable file forces clean=False (exit 1) even with 0 regex findings
            bin_dir = root / "bin_only"
            bin_dir.mkdir()
            (bin_dir / "opaque.bin").write_bytes(b"\x00\x01\x02\xff")
            rc_b, out_b, _ = _run_cli(["safety-scan", str(bin_dir), "--json"])
            jb = json.loads(out_b)
            _req(rc_b == 1 and jb["clean"] is False and len(jb["undecodable_files"]) == 1,
                 f"undecodable file must fail closed: rc={rc_b} {jb}")

            # Plain-text safety-scan prints FAIL status + skipped/undecodable/unreadable counts
            rc_pt, out_pt, _ = _run_cli(["safety-scan", str(bin_dir)])
            _req(
                rc_pt == 1
                and "[aletheia] status=FAIL" in out_pt
                and "skipped_files_count: 0" in out_pt
                and "undecodable_files_count: 1" in out_pt
                and "unreadable_files_count: 0" in out_pt
                and "opaque.bin: undecodable_or_binary" in out_pt,
                f"plain-text safety-scan missing counts/status: rc={rc_pt} out={out_pt!r}",
            )

    def test_36_audit_log_splits_on_delimiter_pipes_and_whole_tokens_only(self) -> None:
        from aletheia.audit_check import validate_audit_log_markdown

        head = (
            "| Audit ID | Date | Author | Target | Gates | Oracle | Novelty | Verdict | Evidence |\n"
            "|---|---|---|---|---|---|---|---|---|\n"
        )

        def row(target: str, oracle: str, novelty: str, verdict: str) -> str:
            return f"| **AUDIT-005** | 2026-11-20 | a | {target} | G1, G9 | {oracle} | {novelty} | {verdict} | note |\n"

        with tempfile.TemporaryDirectory(prefix="aletheia_t_pipes_") as td:
            root = Path(td)

            def check(body: str) -> dict:
                path = root / "LOG.md"
                write_lf_text(path, body)
                return validate_audit_log_markdown(path)

            # Cave AUDIT-005 shape: norm bars inside math must not shift columns.
            res = check(head + row(r"inflation $\|r\|^2=\|r^*\|^2+e_1^2/\|p_1\|^2$", "`exact`", "**`N1`** *(text)*", "**`VERIFIED`**"))
            _req(res["valid"] and res["verdict_counts"] == {"VERIFIED": 1} and res["novelty_counts"] == {"N1": 1},
                 f"escaped-pipe row rejected: {res}")
            # Unescaped pipes inside math or code spans are cell content, not delimiters.
            for target in (r"norm $a|b$ end", "`x|y` helper"):
                res = check(head + row(target, "`exact` (notes)", "**`N1`** *(text)*", "**`VERIFIED`**"))
                _req(res["valid"], f"pipe in span split the row for {target!r}: {res}")
            # Whole tokens only: near spellings of each column must fail.
            for body, code in (
                (head + row("t", "exactitude", "N1", "VERIFIED"), "INVALID_ORACLE_CLASS"),
                (head + row("t", "exact", "N20", "VERIFIED"), "INVALID_NOVELTY_TAG"),
                (head + row("t", "exact", "N1", "VERIFIED-ish"), "INVALID_VERDICT"),
            ):
                res = check(body)
                _req(not res["valid"] and [e["code"] for e in res["errors"]] == [code],
                     f"near token accepted, want {code}: {res}")

    def test_37_strict_json_rejects_nonfinite_floats_and_lone_surrogates(self) -> None:
        from aletheia.strict_io import loads_strict_json

        for bad, code in (
            ('{"x": 1e999}', "JSON_FLOAT_NOT_FINITE"),
            ('{"x": -1e999}', "JSON_FLOAT_NOT_FINITE"),
            ('[1e999]', "JSON_FLOAT_NOT_FINITE"),
            (r'"\ud800"', "JSON_LONE_SURROGATE"),
            (r'{"\ud800": 1}', "JSON_LONE_SURROGATE"),
            (r'{"a": ["\udfff"]}', "JSON_LONE_SURROGATE"),
        ):
            try:
                loads_strict_json(bad)
                raise AssertionError(f"bad JSON accepted: {bad}")
            except AletheiaError as exc:
                _req(exc.code == code, f"wrong code for {bad}: {exc.code} != {code}")
        _req(loads_strict_json('{"x": 1.5}') == {"x": 1.5}, "finite float rejected")
        _req(loads_strict_json(r'"\ud83d\ude00"') == "\U0001f600", "valid surrogate pair rejected")
        # The exact path keeps its float refusal and code.
        for bad in ('{"x": 1.5}', '{"x": 1e999}'):
            try:
                loads_strict_json(bad, allow_float=False)
                raise AssertionError(f"float accepted with allow_float=False: {bad}")
            except AletheiaError as exc:
                _req(exc.code == "JSON_FLOAT_FORBIDDEN", f"wrong exact-path code for {bad}: {exc.code}")

    def test_37b_strict_json_rejects_float_literal_that_underflows_to_zero(self) -> None:
        from aletheia.strict_io import loads_strict_json

        for bad in ('{"x": 1e-999}', '{"x": -1e-999}', '{"x": 1.0e-999}', '{"a": 1e-999, "b": 2}'):
            try:
                loads_strict_json(bad)
                raise AssertionError(f"underflowing float accepted: {bad}")
            except AletheiaError as exc:
                _req(exc.code == "JSON_FLOAT_UNDERFLOW", f"wrong code for {bad}: {exc.code}")
        # Literals that denote exactly zero stay legal.
        for good, want in (('{"x": 0}', 0.0), ('{"x": 0.0}', 0.0), ('{"x": -0.0}', -0.0), ('{"x": 0e-999}', 0.0)):
            _req(loads_strict_json(good)["x"] == want, f"exact zero rejected: {good}")
        # A subnormal that still carries magnitude is accepted; that scope choice is recorded in the PR.
        _req(loads_strict_json('{"x": 1e-320}')["x"] == 1e-320, "subnormal float rejected")
        # The exact path keeps its own float refusal code.
        try:
            loads_strict_json('{"x": 1e-999}', allow_float=False)
            raise AssertionError("float accepted with allow_float=False")
        except AletheiaError as exc:
            _req(exc.code == "JSON_FLOAT_FORBIDDEN", f"wrong exact-path code: {exc.code}")

    def test_38_ring0_lock_compares_with_strict_types(self) -> None:
        from aletheia.ratchet import check_ring0_lock

        for base, cand in (
            ({"oracle": 1}, {"oracle": True}),
            ({"oracle": 1}, {"oracle": 1.0}),
            ({"oracle": True}, {"oracle": 1.0}),
            ({"gates": {"k": [1]}}, {"gates": {"k": [True]}}),
        ):
            try:
                check_ring0_lock(base, cand)
                raise AssertionError(f"Ring-0 type change accepted: {base} -> {cand}")
            except AletheiaError as exc:
                _req(exc.code == "RING0_TAMPER", f"wrong Ring-0 code: {exc.code}")
        _req(check_ring0_lock({"oracle": "exact", "gates": {"k": [1, True, 1.0]}},
                              {"oracle": "exact", "gates": {"k": [1, True, 1.0]}}),
             "identical typed Ring-0 sections rejected")
        _req(check_ring0_lock({"oracle": "exact", "lr": 1}, {"oracle": "exact", "lr": True}),
             "non Ring-0 section must stay mutable")


if __name__ == "__main__":
    unittest.main()
