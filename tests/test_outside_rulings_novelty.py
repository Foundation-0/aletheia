"""
Novelty status of VERIFIED N2 ledger rows in `aletheia audit-check`.

N2 needs Gates 1-10 (spec section 2.3). A VERIFIED N2 row that lists no G10 and that no
`outside_observer.rulings.v1` file names gets novelty status NOT_SHOWN: a warning by default, an
error under --strict-novelty. The rulings file is refused unless it has the shape of cave-expedition
`verification/outside/rulings.json`. Zero bare `assert` statements.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from aletheia.audit_check import load_outside_rulings, run_audit_check, validate_audit_log_markdown
from aletheia.cli import main as cli_main
from aletheia.strict_io import AletheiaError

HEAD = (
    "| Audit ID | Date | Author | Target | Gates | Oracle | Novelty | Verdict | Evidence |\n"
    "|---|---|---|---|---|---|---|---|---|\n"
)


def _req(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _row(audit_id: str, gates: str, novelty: str = "N2", verdict: str = "VERIFIED") -> str:
    return f"| **{audit_id}** | 2026-11-20 | a | t | {gates} | exact | {novelty} | **{verdict}** | note |\n"


def _write(path: Path, text: str) -> Path:
    path.write_bytes(text.encode("utf-8"))
    return path


def _rulings(areas: Any, schema: Any = "outside_observer.rulings.v1") -> dict[str, Any]:
    return {"schema": schema, "date": "2026-11-21", "areas": areas}


def _area(audits: Any, ruling: Any = "stands", name: Any = "spectral") -> dict[str, Any]:
    return {"area": name, "audits": audits, "findings": [{"id": "F1", "ruling": ruling}]}


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        rc = cli_main(argv)
    return rc, out_buf.getvalue(), err_buf.getvalue()


class TestOutsideRulingsNovelty(unittest.TestCase):
    def test_01_n2_without_g10_or_ruling_is_not_shown_warning(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_nov_") as td:
            log = _write(Path(td) / "LOG.md", HEAD + _row("AUDIT-001", "G1, G9"))
            res = validate_audit_log_markdown(log)
            _req(res["valid"], f"default mode must only warn: {res['errors']}")
            codes = [w["code"] for w in res["warnings"]]
            _req(codes == ["N2_NOVELTY_NOT_SHOWN"], f"expected one NOT_SHOWN warning, got {codes}")
            _req(res["warnings"][0]["audit_id"] == "AUDIT-001", f"wrong row: {res['warnings']}")
            _req(res["n2_novelty"][0]["novelty_status"] == "NOT_SHOWN", f"status: {res['n2_novelty']}")
            _req(
                (res["verified_n2_rows"], res["verified_n2_without_outside_ruling"], res["n2_novelty_not_shown"]) == (1, 1, 1),
                f"counts: {res}",
            )
            _req(res["outside_rulings_checked"] is False, "no rulings were passed")

    def test_02_strict_novelty_makes_it_an_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_nov_") as td:
            log = _write(Path(td) / "LOG.md", HEAD + _row("AUDIT-001", "G1, G9"))
            res = validate_audit_log_markdown(log, strict_novelty=True)
            _req(not res["valid"], "strict mode must reject a NOT_SHOWN N2 row")
            _req([e["code"] for e in res["errors"]] == ["N2_NOVELTY_NOT_SHOWN"], f"errors: {res['errors']}")
            _req(res["warnings"] == [], f"strict mode must not also warn: {res['warnings']}")

    def test_03_g10_listed_records_a_second_pass(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_nov_") as td:
            for gates in ("G1, G9, G10", "G1-G10"):
                log = _write(Path(td) / "LOG.md", HEAD + _row("AUDIT-001", gates))
                res = validate_audit_log_markdown(log, strict_novelty=True)
                # (A range such as G1-G10 still draws the separate G9 prior-art note; only NOT_SHOWN matters here.)
                nov_codes = [f["code"] for f in res["errors"] + res["warnings"] if f["code"] == "N2_NOVELTY_NOT_SHOWN"]
                _req(res["valid"] and nov_codes == [], f"{gates!r} lost its G10 credit: {res}")
                entry = res["n2_novelty"][0]
                _req(entry["novelty_status"] == "SECOND_PASS_RECORDED" and entry["basis"] == ["G10_LISTED"], f"{entry}")
                _req(res["verified_n2_without_outside_ruling"] == 1, "G10 is not an outside ruling")
            # G1 and G100 are not G10.
            for gates in ("G1, G9", "G1, G9, G100"):
                log = _write(Path(td) / "LOG.md", HEAD + _row("AUDIT-001", gates))
                res = validate_audit_log_markdown(log)
                _req(res["n2_novelty_not_shown"] == 1, f"{gates!r} counted as G10: {res['n2_novelty']}")

    def test_04_only_verified_n2_rows_are_classified(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_nov_") as td:
            text = HEAD + _row("AUDIT-001", "G1, G9", novelty="N1") + _row("AUDIT-002", "G1, G9", verdict="PARTIAL/FRAGILE")
            res = validate_audit_log_markdown(_write(Path(td) / "LOG.md", text), strict_novelty=True)
            _req(res["valid"] and res["n2_novelty"] == [] and res["verified_n2_rows"] == 0, f"{res}")

    def test_05_outside_ruling_names_the_row_exactly(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_nov_") as td:
            root = Path(td)
            rul = _write(
                root / "rulings.json",
                json.dumps(_rulings([_area("AUDIT-002, AUDIT-004 Part A"), _area("AUDIT-011R", "falls", "physics")])) + "\n",
            )
            cov = load_outside_rulings(rul)
            _req(sorted(cov) == ["AUDIT-002", "AUDIT-004", "AUDIT-011R"], f"coverage ids: {sorted(cov)}")
            _req(cov["AUDIT-004"] == [{"area": "spectral", "entry": "AUDIT-004 Part A"}], f"qualifier lost: {cov}")
            text = HEAD + "".join(_row(a, "G1, G9") for a in ("AUDIT-002", "AUDIT-004", "AUDIT-011", "AUDIT-011R"))
            res = validate_audit_log_markdown(_write(root / "LOG.md", text), outside_rulings=cov)
            status = {r["audit_id"]: r["novelty_status"] for r in res["n2_novelty"]}
            _req(
                status == {
                    "AUDIT-002": "SECOND_PASS_RECORDED",
                    "AUDIT-004": "SECOND_PASS_RECORDED",
                    "AUDIT-011": "NOT_SHOWN",
                    "AUDIT-011R": "SECOND_PASS_RECORDED",
                },
                f"exact-id matching broken: {status}",
            )
            _req([w["audit_id"] for w in res["warnings"]] == ["AUDIT-011"], f"warnings: {res['warnings']}")
            _req((res["verified_n2_without_outside_ruling"], res["n2_novelty_not_shown"]) == (1, 1), f"{res}")
            _req(res["outside_rulings_checked"] is True and res["outside_ruling_ids_not_in_ledger"] == [], f"{res}")
            # A ruling on an id the ledger lacks is reported, not silently dropped.
            res2 = validate_audit_log_markdown(_write(root / "LOG2.md", HEAD + _row("AUDIT-002", "G1")), outside_rulings=cov)
            _req(res2["outside_ruling_ids_not_in_ledger"] == ["AUDIT-004", "AUDIT-011R"], f"{res2}")

    def test_06_malformed_rulings_are_refused(self) -> None:
        good_area = _area("AUDIT-002")
        cases: list[tuple[Any, str]] = [
            (_rulings([good_area], schema="outside_observer.rulings.v2"), "OUTSIDE_RULINGS_BAD_SCHEMA"),
            ({"areas": [good_area]}, "OUTSIDE_RULINGS_BAD_SCHEMA"),
            (_rulings([]), "OUTSIDE_RULINGS_NO_AREAS"),
            (_rulings({"a": good_area}), "OUTSIDE_RULINGS_NO_AREAS"),
            (_rulings(["spectral"]), "OUTSIDE_RULINGS_BAD_AREA"),
            (_rulings([_area("AUDIT-002", name="")]), "OUTSIDE_RULINGS_BAD_AREA"),
            (_rulings([_area("AUDIT-002", name=7)]), "OUTSIDE_RULINGS_BAD_AREA"),
            (_rulings([_area("")]), "OUTSIDE_RULINGS_BAD_AUDITS"),
            (_rulings([_area(["AUDIT-002"])]), "OUTSIDE_RULINGS_BAD_AUDITS"),
            (_rulings([{"area": "x", "audits": "AUDIT-002", "findings": []}]), "OUTSIDE_RULINGS_NO_FINDINGS"),
            (_rulings([{"area": "x", "audits": "AUDIT-002"}]), "OUTSIDE_RULINGS_NO_FINDINGS"),
            (_rulings([_area("AUDIT-002", ruling="upheld")]), "OUTSIDE_RULINGS_BAD_RULING"),
            (_rulings([_area("AUDIT-002", ruling=["stands"])]), "OUTSIDE_RULINGS_BAD_RULING"),
            (_rulings([{"area": "x", "audits": "AUDIT-002", "findings": ["stands"]}]), "OUTSIDE_RULINGS_BAD_RULING"),
            (_rulings([_area("AUDIT-002, ")]), "OUTSIDE_RULINGS_BAD_AUDIT_ID"),
            (_rulings([_area("Part A of AUDIT-002")]), "OUTSIDE_RULINGS_BAD_AUDIT_ID"),
            (_rulings([_area("AUDIT-02")]), "OUTSIDE_RULINGS_BAD_AUDIT_ID"),
            # The entry must end after the id or a whitespace-separated qualifier (tail anchor).
            (_rulings([_area("AUDIT-002;AUDIT-003")]), "OUTSIDE_RULINGS_BAD_AUDIT_ID"),
            # A missing comma would hide AUDIT-003 inside the qualifier of AUDIT-002.
            (_rulings([_area("AUDIT-002 AUDIT-003")]), "OUTSIDE_RULINGS_BAD_AUDIT_ID"),
            (_rulings([_area("AUDIT-004 Part A, AUDIT-002 and AUDIT-003")]), "OUTSIDE_RULINGS_BAD_AUDIT_ID"),
        ]
        with tempfile.TemporaryDirectory(prefix="aletheia_t_nov_") as td:
            path = Path(td) / "rulings.json"
            for payload, code in cases:
                _write(path, json.dumps(payload) + "\n")
                with self.assertRaises(AletheiaError) as ctx:
                    load_outside_rulings(path)
                _req(ctx.exception.code == code, f"{payload!r}: expected {code}, got {ctx.exception.code}")
            # Duplicate keys are refused by the strict JSON loader.
            _write(path, '{"schema": "outside_observer.rulings.v1", "schema": "x", "areas": []}\n')
            with self.assertRaises(AletheiaError):
                load_outside_rulings(path)
            # Control: the smallest valid file loads.
            _write(path, json.dumps(_rulings([good_area])) + "\n")
            _req(load_outside_rulings(path) == {"AUDIT-002": [{"area": "spectral", "entry": "AUDIT-002"}]}, "control failed")

    def test_07_run_audit_check_and_cli_wiring(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_nov_") as td:
            root = Path(td) / "ws"
            (root / "verification").mkdir(parents=True)
            _write(root / "verification" / "AUDIT_LOG.md", HEAD + _row("AUDIT-002", "G1, G9") + _row("AUDIT-003", "G1, G9"))
            rul = _write(Path(td) / "rulings.json", json.dumps(_rulings([_area("AUDIT-002")])) + "\n")

            plain = run_audit_check(root)
            _req(plain["passed"], f"warnings must not fail the run: {plain['failures']}")
            _req(plain["summary"]["n2_novelty_not_shown"] == 2 and plain["summary"]["verified_n2_rows"] == 2, f"{plain['summary']}")
            # Without a rulings file the summary says so, so `verified_n2_without_outside_ruling` is not misread.
            _req(plain["summary"]["outside_rulings_checked"] is False, f"{plain['summary']}")

            with_rul = run_audit_check(root, outside_rulings=rul)
            s = with_rul["summary"]
            _req(
                with_rul["passed"]
                and (s["verified_n2_rows"], s["verified_n2_without_outside_ruling"], s["n2_novelty_not_shown"]) == (2, 1, 1)
                and s["outside_rulings_checked"] is True,
                f"{s}",
            )

            strict = run_audit_check(root, outside_rulings=rul, strict_novelty=True)
            _req(not strict["passed"] and strict["failures"] == ["AUDIT_LOG validation errors (1)"], f"{strict['failures']}")

            rc, out, _ = _run_cli(["audit-check", str(root), "--outside-rulings", str(rul), "--strict-novelty", "--json"])
            payload = json.loads(out)
            _req(rc == 1 and payload["summary"]["n2_novelty_not_shown"] == 1, f"cli strict: rc={rc} {payload['summary']}")
            rc_ok, out_ok, _ = _run_cli(["audit-check", str(root), "--outside-rulings", str(rul), "--json"])
            _req(rc_ok == 0 and json.loads(out_ok)["audit_log"]["outside_rulings_checked"] is True, f"cli default: rc={rc_ok}")

            # A rulings file with no ledger to check it against is refused, not ignored.
            bare = Path(td) / "bare"
            bare.mkdir()
            with self.assertRaises(AletheiaError) as ctx:
                run_audit_check(bare, outside_rulings=rul)
            _req(ctx.exception.code == "OUTSIDE_RULINGS_WITHOUT_AUDIT_LOG", f"got {ctx.exception.code}")
            # So is --strict-novelty: with no ledger it would otherwise pass without checking anything.
            with self.assertRaises(AletheiaError) as ctx_strict:
                run_audit_check(bare, strict_novelty=True)
            _req(ctx_strict.exception.code == "STRICT_NOVELTY_WITHOUT_AUDIT_LOG", f"got {ctx_strict.exception.code}")
            rc_bare, out_bare, _ = _run_cli(["audit-check", str(bare), "--strict-novelty", "--json"])
            _req(rc_bare == 2 and json.loads(out_bare)["code"] == "STRICT_NOVELTY_WITHOUT_AUDIT_LOG", f"cli: rc={rc_bare} {out_bare!r}")
            no_ledger = run_audit_check(bare)
            _req(no_ledger["summary"]["verified_n2_rows"] == 0 and no_ledger["audit_log"] is None, "no-ledger defaults")

    def test_08_combined_row_ids_are_ledger_ids_but_rows_match_on_the_leading_id(self) -> None:
        # cave-expedition's ledger writes re-audits as combined rows: `AUDIT-015R / 016R`, `AUDIT-011R / 013R`,
        # `AUDIT-006R / 007R / 008R`. Their later ids are in the ledger, so a ruling on one is not reported
        # as missing from it; the row itself is still matched on its leading id only.
        with tempfile.TemporaryDirectory(prefix="aletheia_t_nov_") as td:
            root = Path(td)
            rul = _write(
                root / "rulings.json",
                json.dumps(_rulings([
                    _area("AUDIT-016R, AUDIT-020R"),
                    _area("AUDIT-008R, AUDIT-013R, AUDIT-021", "stands_narrowed", "physics"),
                ])) + "\n",
            )
            cov = load_outside_rulings(rul)
            text = (
                HEAD
                + _row("AUDIT-015R / 016R", "G1, G9")
                + _row("AUDIT-006R / 007R / 008R", "G1, G9", novelty="N1")
                + _row("AUDIT-011R/013R", "G1, G9")
                + _row("AUDIT-021 / AUDIT-022", "G1, G9")
            )
            res = validate_audit_log_markdown(_write(root / "LOG.md", text), outside_rulings=cov)
            _req(res["outside_ruling_ids_not_in_ledger"] == ["AUDIT-020R"], f"combined-row ids lost: {res['outside_ruling_ids_not_in_ledger']}")
            got = {r["audit_id"]: (r["novelty_status"], r["row_ids"]) for r in res["n2_novelty"]}
            _req(
                got == {
                    "AUDIT-015R": ("NOT_SHOWN", ["AUDIT-015R", "AUDIT-016R"]),
                    "AUDIT-011R": ("NOT_SHOWN", ["AUDIT-011R", "AUDIT-013R"]),
                    "AUDIT-021": ("SECOND_PASS_RECORDED", ["AUDIT-021", "AUDIT-022"]),
                },
                f"row matching must stay on the leading id: {got}",
            )
            _req([w["audit_id"] for w in res["warnings"]] == ["AUDIT-015R", "AUDIT-011R"], f"{res['warnings']}")
            # Without the combined rows, their later ids are reported as missing from the ledger.
            res2 = validate_audit_log_markdown(_write(root / "LOG2.md", HEAD + _row("AUDIT-021", "G1, G9")), outside_rulings=cov)
            _req(
                res2["outside_ruling_ids_not_in_ledger"] == ["AUDIT-008R", "AUDIT-013R", "AUDIT-016R", "AUDIT-020R"],
                f"{res2['outside_ruling_ids_not_in_ledger']}",
            )


if __name__ == "__main__":
    unittest.main()
