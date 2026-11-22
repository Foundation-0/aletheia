"""
Pure-stdlib tests for `aletheia twin-check` (machine-checked coupling with cave-expedition).

Builds two tiny fake repos in a temp directory and covers OK, DRIFT, PENDING and SKIP.
Zero bare `assert` statements (R4 parity under -I -B, -I -O -B, -I -B -W error).
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from typing import Any
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from aletheia.cli import main as cli_main
from aletheia.strict_io import AletheiaError, write_lf_text
from aletheia.twin_check import (
    CHECK_IDS,
    _extract_cited_ids,
    format_twin_table,
    load_contract,
    resolve_roots,
    run_twin_check,
)

PKG_ROOT = Path(__file__).resolve().parent.parent
REAL_CONTRACT = PKG_ROOT / "spec" / "twin_contract.json"
LICENSE_TEXT = "fixture license text\n"
CAVE_PR = "Foundation-0/cave-expedition#1"


def _req(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        rc = cli_main(argv)
    return rc, out_buf.getvalue(), err_buf.getvalue()


def _status(report: dict[str, Any], check_id: str) -> str:
    for row in report["checks"]:
        if row["id"] == check_id:
            return str(row["status"])
    raise AssertionError(f"no row for {check_id}")


def _row(report: dict[str, Any], check_id: str) -> dict[str, Any]:
    for row in report["checks"]:
        if row["id"] == check_id:
            return row
    raise AssertionError(f"no row for {check_id}")


def _log_table(rows: list[tuple[str, str]]) -> str:
    head = (
        "# Fixture ledger\n\n## Audits\n\n"
        "| Audit ID | Date/Time | Author | Target / Claim | Gates Tested | Oracle Class | Novelty | Verdict | Script / Evidence |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
    )
    body = "".join(
        f"| **{audit_id}** | d | a | t | g | exact | N1 | **`{verdict}`** | e |\n" for audit_id, verdict in rows
    )
    return head + body


def build_repos(
    base: Path,
    *,
    scripts: int = 3,
    aletheia_cited_scripts: int = 3,
    log_rows: list[tuple[str, str]] | None = None,
    seams: int = 2,
    stated_seams: str = "2",
    entry_points: int = 2,
    portals: int = 2,
    readme_claim: str = "Every active expedition track has reached `VERIFIED` status.",
    aletheia_cites: str = "AUDIT-001 AUDIT-002/003",
    cave_license: str = LICENSE_TEXT,
    aletheia_license: str = LICENSE_TEXT,
    aletheia_ci: bool = True,
    cave_ci: bool = True,
) -> tuple[Path, Path]:
    ale = base / "aletheia"
    cave = base / "cave"
    rows = log_rows or [
        ("AUDIT-001", "VERIFIED"),
        ("AUDIT-002", "VERIFIED"),
        ("AUDIT-003", "PARTIAL/FRAGILE"),
        ("AUDIT-003R", "VERIFIED"),
    ]
    write_lf_text(cave / "verification" / "AUDIT_LOG.md", _log_table(rows))
    for i in range(scripts):
        write_lf_text(cave / "verification" / "checks" / f"check_{i + 1:03d}_fixture.py", "pass\n")
    write_lf_text(
        cave / "README.md",
        f"# Cave\n\n{readme_claim}\n\n### Confirmed `N2` Breakthroughs (Genuine New Ground)\n\n"
        "| Audit | Branch | Oracle | Summary |\n|---|---|---|---|\n"
        "| **`AUDIT-002`** | b | exact | s |\n| **`AUDIT-003R`** | b | exact | s |\n\n"
        "### Verified `N1` Concrete Advances\n\n| **`AUDIT-001`** | b | exact | s |\n",
    )
    write_lf_text(cave / "peer-web" / "frontier_seams.json", json.dumps({"frontier_seams": [{}] * seams}) + "\n")
    write_lf_text(
        cave / "peer-web" / "PEER_WEB.md",
        f"# Peer web\n\npush through the **{stated_seams} explicit seams (Section 4)** now.\n\n"
        f"## 4. Category C \u2014 {stated_seams} High-Leverage Uncharted Seams\n",
    )
    write_lf_text(cave / "cartography" / "entry_points.json", json.dumps({"entry_points": [{}] * entry_points}) + "\n")
    write_lf_text(
        cave / "cartography" / "frontier_portals.md",
        "# Portals\n\n" + "".join(f"## Portal {n} \u2014 title\n\n" for n in range(1, portals + 1)),
    )
    write_lf_text(cave / "LICENSE", cave_license)
    if cave_ci:
        write_lf_text(
            cave / ".github" / "workflows" / "verify.yml",
            "jobs:\n  v:\n    steps:\n      - run: python3 -I -B verification/checks/check_001_fixture.py\n",
        )

    write_lf_text(ale / "README.md", f"# Aletheia\n\nCites {aletheia_cites}; runs across `{aletheia_cited_scripts}` verifier scripts.\n")
    write_lf_text(ale / "THEORY.md", "# Theory\n\nNo audit ids here.\n")
    write_lf_text(
        ale / "evidence" / "cave-expedition-case-study.md",
        "| Group | Audits | Count |\n|---|---|---|\n"
        "| **Internally Labelled `N2` (`VERIFIED`)** | `AUDIT-002` *(outside note: `AUDIT-001`)* | **1** |\n"
        "| **Borderline `N1`/`N2` (`VERIFIED`)** | `AUDIT-003R` (note) | **1** |\n",
    )
    write_lf_text(ale / "LICENSE", aletheia_license)
    if aletheia_ci:
        write_lf_text(
            ale / ".github" / "workflows" / "ci.yml",
            "jobs:\n  t:\n    steps:\n      - run: python3 -I -B tests/run_all.py\n",
        )
    return ale, cave


def build_contract(
    path: Path,
    *,
    scripts: int = 3,
    pending: dict[str, list[dict[str, Any]]] | None = None,
    license_text: str = LICENSE_TEXT,
    cave_ci_if_missing: str = "DRIFT",
) -> Path:
    contract = copy.deepcopy(json.loads(REAL_CONTRACT.read_text(encoding="utf-8")))
    checks = contract["checks"]
    for spec in checks.values():
        spec.pop("pending", None)
    checks["cave.check_script_count_matches_citation"]["expected"]["aletheia_cited_check_scripts"] = scripts
    checks["cave.n2_set_matches"]["expected"] = {
        "aletheia_n2_ids": ["AUDIT-002"],
        "aletheia_borderline_n2_ids": ["AUDIT-003R"],
    }
    checks["twin.license_verbatim"]["expected"]["canonical_sha256"] = hashlib.sha256(license_text.encode("utf-8")).hexdigest()
    checks["twin.license_verbatim"]["expected"]["also_accepted_sha256"] = []
    ci_cave = checks["twin.ci_present"]["expected"]["repos"]["cave"]
    ci_cave["if_missing"] = cave_ci_if_missing
    for check_id, entries in (pending or {}).items():
        checks[check_id]["pending"] = entries
    write_lf_text(path, json.dumps(contract, indent=2) + "\n")
    return path


class TestTwinCheck(unittest.TestCase):
    def _run(self, td: str, *, contract_kwargs: dict[str, Any] | None = None, **repo_kwargs: Any) -> dict[str, Any]:
        base = Path(td)
        ale, cave = build_repos(base, **repo_kwargs)
        contract = build_contract(base / "contract.json", **(contract_kwargs or {}))
        return run_twin_check(ale, cave, contract)

    def test_01_ok_case_and_report_shape(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_ok_") as td:
            report = self._run(td)
            _req(report["status"] == "OK" and report["passed"] is True, f"expected OK: {report}")
            _req([r["id"] for r in report["checks"]] == list(CHECK_IDS), "report must hold one row per check, in order")
            _req(len(CHECK_IDS) == 9, "exactly the nine specified checks")
            for row in report["checks"]:
                _req(row["status"] == "OK", f"{row['id']} not OK: {row}")
                for key in ("id", "status", "expected", "actual", "note", "evidence", "tracking", "clears_when"):
                    _req(key in row, f"row {row['id']} missing key {key}")
            _req(report["summary"] == {"OK": 9, "DRIFT": 0, "PENDING": 0, "SKIP": 0}, f"bad summary {report['summary']}")
            cave_ev = _row(report, "cave.audit_ids_contiguous")["actual"]
            _req(cave_ev["first"] == 1 and cave_ev["last"] == 3 and cave_ev["count"] == 3, f"bad range {cave_ev}")
            _req(len(report["contract_sha256"]) == 64, "contract hash missing")

    def test_02_drift_when_contract_expects_more_scripts_than_fixture_has(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_drift_") as td:
            report = self._run(td, scripts=2, contract_kwargs={"scripts": 3})
            row = _row(report, "cave.check_script_count_matches_citation")
            _req(row["status"] == "DRIFT", f"expected DRIFT: {row}")
            _req(row["actual"]["cave_check_scripts"] == 2 and row["expected"]["cave_check_scripts"] == 3, f"bad counts: {row}")
            _req(report["status"] == "DRIFT" and report["passed"] is False, "overall must be DRIFT")
            _req("aletheia_text_says" not in row["actual"], f"drift must come from the count, not the text: {row}")

            base = Path(td)
            rc, out, _ = _run_cli(
                ["twin-check", "--aletheia-root", str(base / "aletheia"), "--cave-root", str(base / "cave"),
                 "--contract", str(base / "contract.json"), "--json"]
            )
            js = json.loads(out)
            _req(rc == 1 and js["status"] == "DRIFT", f"DRIFT must exit 1: rc={rc}")
            _req(len(js["checks"]) == 9, "json must hold one row per check")

    def test_03_pending_is_declared_tracked_and_does_not_fail(self) -> None:
        pending = {
            "cave.check_script_count_matches_citation": [
                {"tracking": [CAVE_PR], "clears_when": "the cave pull request merges", "cave_count_after_merge": 3}
            ]
        }
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_pending_") as td:
            report = self._run(td, scripts=2, contract_kwargs={"scripts": 3, "pending": pending})
            row = _row(report, "cave.check_script_count_matches_citation")
            _req(row["status"] == "PENDING", f"expected PENDING: {row}")
            _req(row["tracking"] == [CAVE_PR] and "merges" in row["clears_when"], f"PENDING must name PR and clearing: {row}")
            _req(report["status"] == "PENDING" and report["passed"] is True, "PENDING must not fail the run")
            base = Path(td)
            rc, out, _ = _run_cli(
                ["twin-check", "--aletheia-root", str(base / "aletheia"), "--cave-root", str(base / "cave"),
                 "--contract", str(base / "contract.json")]
            )
            _req(rc == 0 and "PENDING" in out and CAVE_PR in out and "clears when:" in out, f"table output wrong: rc={rc} {out!r}")

    def test_03b_aletheia_text_disagreeing_with_contract_is_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_text_") as td:
            report = self._run(td, scripts=3, aletheia_cited_scripts=5)
            row = _row(report, "cave.check_script_count_matches_citation")
            _req(row["status"] == "DRIFT" and row["actual"]["aletheia_text_says"] == 5, f"text drift missed: {row}")

    def test_04_pending_does_not_excuse_a_count_above_the_citation(self) -> None:
        pending = {
            "cave.check_script_count_matches_citation": [
                {"tracking": [CAVE_PR], "clears_when": "merge", "cave_count_after_merge": 3}
            ]
        }
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_over_") as td:
            report = self._run(td, scripts=4, contract_kwargs={"scripts": 3, "pending": pending})
            _req(_status(report, "cave.check_script_count_matches_citation") == "DRIFT", "cave above citation is drift, not pending")

    def test_05_skip_when_twin_repo_absent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_skip_") as td:
            base = Path(td)
            ale, _cave = build_repos(base)
            contract = build_contract(base / "contract.json")
            report = run_twin_check(ale, base / "no-such-cave", contract)
            _req(report["cave_root_present"] is False and report["aletheia_root_present"] is True, "presence flags wrong")
            for row in report["checks"]:
                _req(row["status"] == "SKIP", f"{row['id']} must SKIP when cave is absent: {row}")
                _req("not present" in row["note"], f"SKIP needs a clear note: {row['note']}")
            _req(report["status"] == "SKIP" and report["passed"] is True, "SKIP must not fail")
            rc, out, _ = _run_cli(
                ["twin-check", "--aletheia-root", str(ale), "--cave-root", str(base / "no-such-cave"),
                 "--contract", str(contract), "--json"]
            )
            _req(rc == 0 and json.loads(out)["summary"]["SKIP"] == 9, f"SKIP must exit 0: rc={rc}")

            only_cave = run_twin_check(base / "no-such-aletheia", base / "cave", contract)
            _req(_status(only_cave, "cave.audit_ids_contiguous") == "OK", "cave-only checks still run without aletheia")
            _req(_status(only_cave, "aletheia.cites_known_audits") == "SKIP", "twin checks skip without aletheia")
            _req(only_cave["passed"] is True, "absent aletheia must not fail")

    def test_06_audit_id_gap_and_duplicate_are_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_ids_") as td:
            report = self._run(td, log_rows=[("AUDIT-001", "VERIFIED"), ("AUDIT-003", "VERIFIED")], aletheia_cites="AUDIT-001")
            row = _row(report, "cave.audit_ids_contiguous")
            _req(row["status"] == "DRIFT" and row["actual"]["gaps"] == ["AUDIT-002"], f"gap not reported: {row}")
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_dup_") as td:
            report = self._run(
                td,
                log_rows=[("AUDIT-001", "VERIFIED"), ("AUDIT-002", "VERIFIED"), ("AUDIT-002", "VERIFIED"), ("AUDIT-003", "VERIFIED")],
            )
            row = _row(report, "cave.audit_ids_contiguous")
            _req(row["status"] == "DRIFT" and row["actual"]["duplicates"] == ["AUDIT-002"], f"duplicate not reported: {row}")

    def test_07_cited_audit_unknown_is_drift_pending_is_pending(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_cite_") as td:
            report = self._run(td, aletheia_cites="AUDIT-001 and AUDIT-009")
            row = _row(report, "aletheia.cites_known_audits")
            _req(row["status"] == "DRIFT" and "AUDIT-009" in row["evidence"]["unknown_first_seen"], f"unknown id not DRIFT: {row}")
            _req(row["evidence"]["unknown_first_seen"]["AUDIT-009"] == "README.md:3", f"needs file:line evidence: {row['evidence']}")
        pending = {
            "aletheia.cites_known_audits": [{"tracking": [CAVE_PR], "clears_when": "merge", "ids": ["AUDIT-009", "AUDIT-777"]}]
        }
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_cite2_") as td:
            report = self._run(td, aletheia_cites="AUDIT-001 and AUDIT-009", contract_kwargs={"pending": pending})
            row = _row(report, "aletheia.cites_known_audits")
            _req(row["status"] == "PENDING" and row["tracking"] == [CAVE_PR], f"declared id must be PENDING: {row}")
            _req(row["actual"]["pending"] == 1 and row["actual"]["unknown"] == 0, f"bad counts {row['actual']}")

    def test_08_n2_set_drift_pending_and_text_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_n2_") as td:
            base = Path(td)
            ale, cave = build_repos(base)
            contract = build_contract(base / "contract.json")
            # cave README gains an N2 row aletheia does not describe
            readme = cave / "README.md"
            write_lf_text(
                readme,
                readme.read_text(encoding="utf-8").replace(
                    "| **`AUDIT-003R`** | b | exact | s |\n", "| **`AUDIT-003R`** | b | exact | s |\n| **`AUDIT-001`** | b | exact | s |\n"
                ),
            )
            report = run_twin_check(ale, cave, contract)
            row = _row(report, "cave.n2_set_matches")
            _req(row["status"] == "DRIFT" and row["actual"]["cave_only"] == ["AUDIT-001"], f"cave-only N2 id must DRIFT: {row}")
            pending = {"cave.n2_set_matches": [{"tracking": [CAVE_PR], "clears_when": "merge", "ids": ["AUDIT-001"]}]}
            contract2 = build_contract(base / "contract2.json", pending=pending)
            _req(_status(run_twin_check(ale, cave, contract2), "cave.n2_set_matches") == "PENDING", "declared difference is PENDING")

        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_n2b_") as td:
            base = Path(td)
            ale, cave = build_repos(base)
            contract = build_contract(base / "contract.json")
            case = ale / "evidence" / "cave-expedition-case-study.md"
            write_lf_text(case, case.read_text(encoding="utf-8").replace("`AUDIT-002` *(outside", "`AUDIT-002`, `001` *(outside"))
            row = _row(run_twin_check(ale, cave, contract), "cave.n2_set_matches")
            _req(row["status"] == "DRIFT" and "no longer matches" in row["note"], f"aletheia text drift must be caught: {row}")

    def test_09_seam_and_portal_counts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_seam_") as td:
            report = self._run(td, seams=3, stated_seams="2", entry_points=4, portals=3)
            seam = _row(report, "cave.seam_count_consistent")
            _req(seam["status"] == "DRIFT" and seam["actual"]["json_len"] == 3, f"seam drift missed: {seam}")
            _req(len(seam["evidence"]["stated"]) == 2, f"both statements must be compared: {seam['evidence']}")
            portal = _row(report, "cave.portal_count_consistent")
            _req(portal["status"] == "DRIFT" and portal["actual"] == {"entry_points": 4, "portals": 3}, f"portal drift missed: {portal}")
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_seam2_") as td:
            report = self._run(td, seams=2, stated_seams="Two")
            _req(_status(report, "cave.seam_count_consistent") == "OK", "number words must be understood")

    def test_10_readme_verified_claim(self) -> None:
        open_rows = [("AUDIT-001", "FALSIFIED"), ("AUDIT-002", "VERIFIED"), ("AUDIT-003", "VERIFIED")]
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_claim_") as td:
            report = self._run(td, log_rows=open_rows)
            row = _row(report, "cave.readme_verified_claim_consistent")
            _req(row["status"] == "DRIFT" and row["actual"]["ledger_rows_without_closing_row"] == ["AUDIT-001"], f"claim drift missed: {row}")
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_claim2_") as td:
            caveat = "Every active expedition track has reached `VERIFIED` status, except two early rows that have no closing row."
            report = self._run(td, log_rows=open_rows, readme_claim=caveat)
            _req(_status(report, "cave.readme_verified_claim_consistent") == "OK", "caveat must clear the claim")
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_claim3_") as td:
            report = self._run(td, log_rows=open_rows, readme_claim="Most tracks reached `VERIFIED`; early audits stay on record.")
            _req(_status(report, "cave.readme_verified_claim_consistent") == "OK", "no blanket assertion means OK")

    def test_11_license_ok_drift_pending(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_lic_") as td:
            report = self._run(td, cave_license="paraphrase\n")
            row = _row(report, "twin.license_verbatim")
            _req(row["status"] == "DRIFT" and "cave" in row["note"], f"non-canonical LICENSE must DRIFT: {row}")
        pending = {
            "twin.license_verbatim": [
                {"repo": "cave", "tracking": ["Foundation-0/cave-expedition#11"], "clears_when": "the license pull request merges"}
            ]
        }
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_lic2_") as td:
            report = self._run(td, cave_license="paraphrase\n", contract_kwargs={"pending": pending})
            row = _row(report, "twin.license_verbatim")
            _req(row["status"] == "PENDING" and row["tracking"] == ["Foundation-0/cave-expedition#11"], f"declared LICENSE gap: {row}")
            _req(report["passed"] is True, "pending LICENSE must stay green")
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_lic3_") as td:
            report = self._run(td, cave_license="paraphrase\n", aletheia_license="paraphrase\n")
            _req(_status(report, "twin.license_verbatim") == "DRIFT", "identical but non-canonical files are still drift")

    def test_12_ci_present(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_ci_") as td:
            report = self._run(td, aletheia_ci=False)
            _req(_status(report, "twin.ci_present") == "DRIFT", "missing aletheia CI is DRIFT by contract")
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_ci2_") as td:
            report = self._run(
                td, cave_ci=False,
                contract_kwargs={"cave_ci_if_missing": "PENDING"},
            )
            row = _row(report, "twin.ci_present")
            _req(row["status"] == "PENDING" and row["tracking"] == ["Foundation-0/cave-expedition#12"], f"cave CI pending: {row}")
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_ci3_") as td:
            report = self._run(td, cave_ci=False)
            _req(_status(report, "twin.ci_present") == "DRIFT", "missing cave CI is DRIFT when contract says DRIFT")

    def test_13_missing_repo_file_is_drift_not_crash(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_gone_") as td:
            base = Path(td)
            ale, cave = build_repos(base)
            (cave / "peer-web" / "PEER_WEB.md").unlink()
            report = run_twin_check(ale, cave, build_contract(base / "contract.json"))
            row = _row(report, "cave.seam_count_consistent")
            _req(row["status"] == "DRIFT" and "missing file" in row["note"], f"missing file must be DRIFT: {row}")

    def test_14_contract_validation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_contract_") as td:
            base = Path(td)
            good = json.loads(REAL_CONTRACT.read_text(encoding="utf-8"))
            _req(sorted(good["checks"]) == sorted(CHECK_IDS), "shipped contract must list exactly the implemented checks")
            load_contract(REAL_CONTRACT)

            dropped = copy.deepcopy(good)
            del dropped["checks"]["twin.ci_present"]
            write_lf_text(base / "dropped.json", json.dumps(dropped))
            with self.assertRaises(AletheiaError) as ctx:
                load_contract(base / "dropped.json")
            _req(ctx.exception.code == "TWIN_CONTRACT_CHECK_SET", f"wrong code {ctx.exception.code}")

            untracked = copy.deepcopy(good)
            untracked["checks"]["cave.n2_set_matches"]["pending"] = [{"ids": ["AUDIT-020R"]}]
            write_lf_text(base / "untracked.json", json.dumps(untracked))
            with self.assertRaises(AletheiaError) as ctx2:
                load_contract(base / "untracked.json")
            _req(ctx2.exception.code == "TWIN_CONTRACT_PENDING_ENTRY", f"pending needs a tracking PR: {ctx2.exception.code}")

            bad_schema = copy.deepcopy(good)
            bad_schema["schema"] = "nope"
            write_lf_text(base / "schema.json", json.dumps(bad_schema))
            rc, out, _ = _run_cli(["twin-check", "--aletheia-root", str(base), "--cave-root", str(base), "--contract", str(base / "schema.json"), "--json"])
            _req(rc == 2 and json.loads(out)["code"] == "TWIN_CONTRACT_SCHEMA", f"bad contract must exit 2: rc={rc} {out}")

    def test_15_default_roots_env_then_sibling(self) -> None:
        a, c = resolve_roots(env={"ALETHEIA_ROOT": "/x/a", "CAVE_ROOT": "/x/c"})
        _req(a == Path("/x/a") and c == Path("/x/c"), f"env roots ignored: {a} {c}")
        a2, c2 = resolve_roots(Path("/y/a"), None, env={"CAVE_ROOT": "/x/c"})
        _req(a2 == Path("/y/a") and c2 == Path("/x/c"), "explicit argument must beat env")
        a3, c3 = resolve_roots(env={})
        _req(a3 == PKG_ROOT and c3 == PKG_ROOT.parent / "cave-expedition", f"bad defaults: {a3} {c3}")
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_env_") as td:
            base = Path(td)
            ale, cave = build_repos(base)
            contract = build_contract(base / "contract.json")
            with mock.patch.dict(os.environ, {"ALETHEIA_ROOT": str(ale), "CAVE_ROOT": str(cave)}):
                rc, out, _ = _run_cli(["twin-check", "--contract", str(contract), "--json"])
            _req(rc == 0 and json.loads(out)["summary"]["OK"] == 9, f"env-driven run failed: rc={rc} {out[:200]}")

    def test_16_extract_cited_ids(self) -> None:
        text = "see AUDIT-006/007/013 and `AUDIT-001`\u2013`021`, AUDIT-061R\u2013067R, AUDIT-063R2 AUDIT-089R2a, AUDIT_LOG, AUDIT-063-ISSUE29, AUDIT-12345\n"
        got = {i for i, _ in _extract_cited_ids(text)}
        want = {
            "AUDIT-006", "AUDIT-007", "AUDIT-013", "AUDIT-001", "AUDIT-021", "AUDIT-061R", "AUDIT-067R",
            "AUDIT-063R2", "AUDIT-089R2a", "AUDIT-063",
        }
        _req(got == want, f"extracted {sorted(got)} != {sorted(want)}")

    def test_17_table_format_and_json_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_twin_fmt_") as td:
            report = self._run(td, scripts=2, contract_kwargs={"scripts": 3})
            table = format_twin_table(report)
            _req("status=DRIFT" in table and "cave.check_script_count_matches_citation" in table, f"table incomplete: {table}")
            _req(json.loads(json.dumps(report)) == report, "report must be plain JSON data")


if __name__ == "__main__":
    unittest.main()
