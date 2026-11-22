"""
Command-line interface for The Aletheia Method (`aletheia` / `python3 -m aletheia`).

Subcommands:
  - init         Scaffold a non-colliding Aletheia research workspace
  - audit-check  Run automated R1-R5 hygiene, AST, 3-mode R4 parity, Lean 4, prereg & AUDIT_LOG checks
  - mutate       Run generic AST refusal-site mutation testing (R5, incl. dict-verdict & accumulator checkers)
  - diagnose     Run quantitative 12-pattern Anti-Cave relapse diagnostics (CS-01..CS-12)
  - handoff      Generate or validate portable `aletheia.compute_handoff.v1` manifests
  - install      Deploy Aletheia rules/skills/adapters to antigravity/claude-code/codex/cursor/gemini-cli/repo
  - ratchet      Run Aletheia Ratchet 5-gate demo or verify float-free hash-chained ratchet ledgers
  - mde          Emit/verify Plane-1 `zone-canon-v0` Aletheia-MDE manifests, lineage DAGs & SYM-2P packets
  - calculus     List, evaluate, or self-test the 8-glyph Aletheia Operator Calculus
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from . import __version__
from .audit_check import run_audit_check
from .calculus import eval_calculus_expression, list_glyphs, run_calculus_self_test
from .diagnose import diagnose_expedition
from .gates_v2 import run_v2_gates_self_test
from .handoff import create_handoff_template, validate_handoff_manifest
from .installer import VALID_TARGETS, install_adapter
from .mde import build_aletheia_mde_manifest, run_mde_demo, verify_lineage_dag_file
from .mutator import run_mutation_suite
from .ratchet import run_ratchet_demo, verify_ratchet_ledger_file
from .safety import scan_directory_safety_surface
from .scaffold import init_workspace
from .strict_io import AletheiaError


def _emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=False))
        return
    # Concise human-readable summary
    status = payload.get("status") or payload.get("overall_status") or payload.get("verdict") or "OK"
    print(f"[aletheia] status={status}")
    for key, val in payload.items():
        if key in ("status", "overall_status", "verdict", "results", "patterns", "files", "r4_scripts", "glyphs"):
            continue
        if isinstance(val, (str, int, float, bool)):
            print(f"  {key}: {val}")
    if "summary" in payload and isinstance(payload["summary"], dict):
        for k, v in payload["summary"].items():
            print(f"  {k}: {v}")
    if "glyphs" in payload and isinstance(payload["glyphs"], list):
        print("  operator glyphs (reported 0 / 227,540 Lean 4 collisions, not reproduced here):")
        for g in payload["glyphs"]:
            print(f"    - {g['id']} {g['codepoint']} ({g['ascii_fallback']}): {g['name']}")
    if "failures" in payload and payload["failures"]:
        print("  failures:")
        for f in payload["failures"]:
            print(f"    - {f}")
    if "errors" in payload and payload["errors"]:
        print("  errors:")
        for e in payload["errors"]:
            print(f"    - {e}")
    if "patterns" in payload and isinstance(payload["patterns"], list):
        print("  anti-cave patterns:")
        for p in payload["patterns"]:
            print(f"    - {p['id']} {p['name']}: {p['status']} (risk={p['risk_score']})")
    if "files" in payload and isinstance(payload["files"], list):
        for f in payload["files"]:
            print(f"  [{f['action']}] {f['relative_path']} ({f['bytes']} bytes)")
    if "survivors" in payload and payload["survivors"]:
        print("  surviving mutants:")
        for s in payload["survivors"]:
            print(f"    - {s['id']} line {s['line']} ({s['kind']}): {s['original']} -> {s['mutated']}")
    if "covered_lines" in payload and isinstance(payload["covered_lines"], list):
        print(f"  covered_lines: {payload['covered_lines']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aletheia",
        description="The Aletheia Method: Portal-Driven Resonance & Adversarial Tomography CLI",
    )
    parser.add_argument("--version", action="version", version=f"aletheia {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # 1. init
    p_init = sub.add_parser("init", help="Scaffold a clean Aletheia research workspace")
    p_init.add_argument("dir", type=Path, help="Target workspace directory")
    p_init.add_argument("--domain", default="general", help="Domain slug (default: general)")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing workspace files")
    p_init.add_argument("--json", action="store_true", help="Emit JSON output")

    # 2. audit-check
    p_aud = sub.add_parser("audit-check", help="Run automated R1-R5 hygiene, AST, R4 parity, Lean 4, prereg & AUDIT_LOG checks")
    p_aud.add_argument("path", type=Path, help="Directory or file to audit")
    p_aud.add_argument("--scripts", nargs="*", default=[], type=Path, help="Verifier scripts to run across 3 R4 modes")
    p_aud.add_argument("--audit-log", type=Path, default=None, help="Explicit path to AUDIT_LOG.md")
    p_aud.add_argument("--receipt", type=Path, default=None, help="Optional aletheia.audit_receipt.v1 JSON receipt")
    p_aud.add_argument("--strict-unseeded", action="store_true", help="Treat unseeded RNG calls as errors")
    p_aud.add_argument("--strict-ancestors", action="store_true", help="Verify canonical 0o022-free permissions along all ancestor directories of target path")
    p_aud.add_argument("--no-isolated", action="store_true", help="Omit -I when running --scripts (for uninstalled cwd imports)")
    p_aud.add_argument("--lean-audit", action="store_true", help="Run hardened v1.4 static Lean 4 audit on *.lean files")
    p_aud.add_argument("--allow-project-import", action="extend", nargs="+", default=[], help="Allow specific project Lean module prefixes under --lean-audit (repeatable)")
    p_aud.add_argument("--comparator-config", type=Path, default=None, help="Validate a Lean 4 Comparator JSON config (enable_nanoda & isolation)")
    p_aud.add_argument("--allow-no-nanoda", action="store_true", help="Downgrade missing/false enable_nanoda in --comparator-config to warning")
    p_aud.add_argument("--pinned-manifest", type=Path, default=None, help="Verify a CORE_MANIFEST.json (SHA-256) or SafeVerify (commit SHA) manifest")
    p_aud.add_argument("--prereg-check", action="store_true", help="Verify Gate 8 git-DAG plan-before-data ancestor ordering")
    p_aud.add_argument("--plan-commit", default=None, help="Explicit plan commit SHA for --prereg-check")
    p_aud.add_argument("--data-commit", default=None, help="Explicit data/audit commit SHA for --prereg-check")
    p_aud.add_argument("--safety-scan", action="store_true", help="Run CYA-GAP-01..05 deterministic agent safety-surface scan")
    p_aud.add_argument("--include-host-hygiene", action="store_true", help="Include CYA-GAP-06 host-hygiene rules when using --safety-scan")
    p_aud.add_argument("--timeout", type=int, default=120, help="Per-mode script timeout in seconds")
    p_aud.add_argument("--json", action="store_true", help="Emit JSON output")

    # 3. mutate
    p_mut = sub.add_parser("mutate", help="Run generic AST refusal-site mutation tester (R5)")
    p_mut.add_argument("script", type=Path, help="Python file containing trust-path guards")
    p_mut.add_argument("--test-cmd", required=True, help="Test command (supports {target} placeholder)")
    p_mut.add_argument("--work-root", type=Path, default=None, help="Workspace root directory to copy into tempdir")
    p_mut.add_argument("--add-cwd", action="store_true", help="Keep work_root on sys.path (uses -s -O -B instead of -I) for repo-local unittest imports")
    p_mut.add_argument("--guards", action="extend", nargs="+", default=[], help="Extra guard function names (e.g. need or fail_if:reject)")
    p_mut.add_argument("--max-mutants", type=int, default=100, help="Maximum mutant sites to execute (0 = all; truncating yields NOT_SHOWN)")
    p_mut.add_argument("--timeout", type=int, default=30, help="Per-mutant test timeout in seconds")
    p_mut.add_argument("--no-boundaries", action="store_true", help="Only mutate if/require guard deletion (skip boundary flips)")
    p_mut.add_argument("--json", action="store_true", help="Emit JSON output")

    # 4. diagnose
    p_diag = sub.add_parser("diagnose", help="Run quantitative 12-pattern Anti-Cave relapse detector (CS-01..CS-12)")
    p_diag.add_argument("expedition_dir", type=Path, help="Expedition workspace directory")
    p_diag.add_argument("--board", type=Path, default=None, help="Optional swarm board JSONL file")
    p_diag.add_argument("--portals-path", type=Path, default=None, help="Explicit path to frontier_portals.md")
    p_diag.add_argument("--fail-on-warning", action="store_true", help="Return non-zero on WARNING as well as ALERT")
    p_diag.add_argument("--json", action="store_true", help="Emit JSON output")

    # 5. handoff
    p_ho = sub.add_parser("handoff", help="Validate or initialize an aletheia.compute_handoff.v1 manifest")
    p_ho.add_argument("manifest", type=Path, help="Path to manifest JSON file")
    p_ho.add_argument("--init-template", action="store_true", help="Create a valid template manifest at path")
    p_ho.add_argument("--source-repo", default="https://github.com/org/repo", help="Source repo URL for template")
    p_ho.add_argument("--domain", default="general", help="Domain slug for template")
    p_ho.add_argument("--force", action="store_true", help="Overwrite existing manifest when using --init-template")
    p_ho.add_argument("--json", action="store_true", help="Emit JSON output")

    # 6. install
    p_ins = sub.add_parser("install", help="Install Aletheia rules/skills/adapters for a target platform")
    p_ins.add_argument("--target", required=True, choices=list(VALID_TARGETS), help="Target platform")
    p_ins.add_argument("--dest", type=Path, default=None, help="Destination directory")
    p_ins.add_argument("--source", type=Path, default=None, help="Optional local Aletheia repo root")
    p_ins.add_argument("--dry-run", action="store_true", help="Preview installation without writing files")
    p_ins.add_argument("--force", action="store_true", help="Overwrite existing files")
    p_ins.add_argument("--json", action="store_true", help="Emit JSON output")

    # 7. ratchet (v1.1)
    p_rat = sub.add_parser("ratchet", help="Run Aletheia Ratchet 5-gate demo or verify a hash-chained ratchet ledger")
    rat_grp = p_rat.add_mutually_exclusive_group(required=True)
    rat_grp.add_argument("--demo", action="store_true", help="Run deterministic 4-regime Aletheia Ratchet showcase")
    rat_grp.add_argument("--verify-ledger", type=Path, default=None, help="Verify a float-free zone-canon-v0 ratchet JSONL ledger")
    p_rat.add_argument("--json", action="store_true", help="Emit JSON output")

    # 8. mde (v1.1)
    p_mde = sub.add_parser("mde", help="Emit/verify Plane-1 zone-canon-v0 Aletheia-MDE manifests, lineage DAGs & SYM-2P packets")
    mde_grp = p_mde.add_mutually_exclusive_group(required=True)
    mde_grp.add_argument("--manifest", action="store_true", help="Emit canonical zone-canon-v0 aletheia-mde-manifest/v0.1")
    mde_grp.add_argument("--verify-dag", type=Path, default=None, help="Verify a Plane-1 causal audit lineage JSONL DAG")
    mde_grp.add_argument("--demo", action="store_true", help="Run full zone-canon-v0 + lineage DAG + SYM-2P/2.0-rcp demo")
    p_mde.add_argument("--json", action="store_true", help="Emit JSON output")

    # 9. calculus (v1.3 — AUDIT-051 8-glyph operator calculus)
    p_calc = sub.add_parser("calculus", help="List, evaluate, or self-test the 8-glyph Aletheia Operator Calculus")
    calc_grp = p_calc.add_mutually_exclusive_group(required=True)
    calc_grp.add_argument("--list", action="store_true", help="List the verified 8-glyph operator registry (Unicode Sm & ASCII fallbacks)")
    calc_grp.add_argument("--eval", dest="eval_expr", default=None, metavar="EXPR", help="Evaluate a pure-Q Unicode or ASCII operator-calculus expression (exit 1 if the value is the boolean false)")
    calc_grp.add_argument("--self-test", action="store_true", help="Run 8-glyph registry verification, 13 compressed theorems & 6 commutator probes")
    p_calc.add_argument("--json", action="store_true", help="Emit zero-float JSON output")

    # 10. gate-v2 (v2.0 — R6/R7, Two-Direction R3, Gate-8 Subspace Latch, Law 2b Steelman, Own-Terms-First)
    p_gv2 = sub.add_parser("gate-v2", help="Self-test pure-Q Aletheia v2.0 gates (R6/R7, 2-dir R3, Gate-8 latch, Law 2b, Own-Terms-First)")
    p_gv2.add_argument("--self-test", action="store_true", required=True, help="Run deterministic zero-float self-test across all 7 v2.0 gates")
    p_gv2.add_argument("--json", action="store_true", help="Emit zero-float JSON output")

    # 11. safety-scan (v2.0 — CYA-GAP-01..06 deterministic agent safety-surface scanner)
    p_saf = sub.add_parser("safety-scan", help="Scan a file or directory for CYA-GAP-01..06 agent safety-surface hazards")
    p_saf.add_argument("path", type=Path, help="File or directory to scan")
    p_saf.add_argument("--include-host-hygiene", action="store_true", help="Include CYA-GAP-06 alias-rm and cloud-sync rules")
    p_saf.add_argument("--json", action="store_true", help="Emit JSON output")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    as_json = bool(getattr(args, "json", False))

    try:
        if args.command == "init":
            res = init_workspace(args.dir, domain=args.domain, force=args.force)
            _emit(res, as_json)
            return 0

        if args.command == "audit-check":
            res = run_audit_check(
                args.path,
                scripts=args.scripts,
                audit_log=args.audit_log,
                receipt=args.receipt,
                strict_unseeded=args.strict_unseeded,
                strict_ancestors=args.strict_ancestors,
                isolated=not args.no_isolated,
                timeout=args.timeout,
                lean_audit=args.lean_audit,
                allow_project_imports=args.allow_project_import,
                comparator_config=args.comparator_config,
                require_nanoda=not args.allow_no_nanoda,
                pinned_manifest=args.pinned_manifest,
                prereg_check=args.prereg_check,
                plan_commit=args.plan_commit,
                data_commit=args.data_commit,
                safety_scan=args.safety_scan,
                include_host_hygiene=args.include_host_hygiene,
            )
            _emit(res, as_json)
            return 0 if res["passed"] else 1

        if args.command == "mutate":
            res = run_mutation_suite(
                args.script,
                args.test_cmd,
                work_root=args.work_root,
                max_mutants=args.max_mutants,
                timeout=args.timeout,
                include_boundaries=not args.no_boundaries,
                add_cwd=args.add_cwd,
                extra_guards=args.guards,
            )
            _emit(res, as_json)
            return 0 if res["passed"] else 1

        if args.command == "diagnose":
            res = diagnose_expedition(args.expedition_dir, board_path=args.board, portals_file=args.portals_path)
            _emit(res, as_json)
            if res["overall_status"] == "RELAPSE_DETECTED":
                return 1
            if args.fail_on_warning and res["overall_status"] == "WATCH":
                return 1
            return 0

        if args.command == "handoff":
            if args.init_template:
                res = create_handoff_template(
                    args.manifest,
                    source_repo=args.source_repo,
                    domain=args.domain,
                    force=args.force,
                )
                _emit(res, as_json)
                return 0
            res = validate_handoff_manifest(args.manifest)
            _emit(res, as_json)
            return 0 if res["valid"] else 1

        if args.command == "install":
            res = install_adapter(
                args.target,
                dest=args.dest,
                source_dir=args.source,
                dry_run=args.dry_run,
                force=args.force,
            )
            _emit(res, as_json)
            return 0

        if args.command == "ratchet":
            if args.demo:
                res = run_ratchet_demo()
            else:
                res = verify_ratchet_ledger_file(args.verify_ledger)
            _emit(res, as_json)
            return 0

        if args.command == "mde":
            if args.manifest:
                res = build_aletheia_mde_manifest()
            elif args.demo:
                res = run_mde_demo()
            else:
                res = verify_lineage_dag_file(args.verify_dag)
            _emit(res, as_json)
            return 0

        if args.command == "calculus":
            if args.list:
                res = list_glyphs()
                _emit(res, as_json)
                return 0 if res["passed"] else 1
            if args.self_test:
                res = run_calculus_self_test()
                _emit(res, as_json)
                return 0 if res["passed"] else 1
            res = eval_calculus_expression(args.eval_expr)
            _emit(res, as_json)
            # A false boolean (a failed equivalence) exits 1 so a shell pipeline can gate on truth.
            return 1 if res["value_type"] == "bool" and res["value"] is False else 0

        if args.command == "gate-v2":
            res = run_v2_gates_self_test()
            _emit(res, as_json)
            return 0 if res["passed"] else 1

        if args.command == "safety-scan":
            try:
                res = scan_directory_safety_surface(args.path, include_host_hygiene=args.include_host_hygiene)
            except ValueError as exc:
                raise AletheiaError("SAFETY_SCAN_ERROR", str(exc)) from exc
            _emit(res, as_json)
            return 0 if res["clean"] else 1

        raise AletheiaError("UNKNOWN_COMMAND", f"unknown command: {args.command}")

    except AletheiaError as exc:
        err_payload = {"status": "ERROR", "code": exc.code, "message": exc.message}
        if as_json:
            print(json.dumps(err_payload, indent=2))
        else:
            print(f"[aletheia] ERROR {exc.code}: {exc.message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
