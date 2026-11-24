"""
Regression tests for the data-rights reconciliation of `CS-04` (Substitution Shadow).

`domains/biology-and-life-sciences.md` ("Data Rights, Consent & Disclosure") says a clearly
labelled synthetic input, used because rights or authorization for the real data are not in
place, is not a Substitution Shadow: `CS-04` is passing a proxy off as the real target.
`aletheia diagnose` must not score such a line, must still score an undisclosed proxy, and its
remediation must not demand real data where rights and authorization do not allow it.

Zero external dependencies. Zero bare assert statements (100% R4 parity across
`-I -B`, `-I -O -B`, and `-I -B -W error`).
"""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia.diagnose import diagnose_expedition
from aletheia.scaffold import init_workspace
from aletheia.strict_io import AletheiaError, write_lf_text

UNDISCLOSED = "Used a synthetic proxy for quick validation."
DISCLOSED = (
    "Synthetic proxy matrix used because data-access rights for the real cohort are not in place; "
    "every result below is labelled synthetic.",
    "Placeholder model until the dated authorization for live acquisition is recorded.",
    "Mock matrix stands in for the cohort: participant consent does not cover this use.",
    "Toy stub in place of the real files; authorisation for the real data is pending.",
)


def _req(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _cs04(ws: Path) -> dict:
    report = diagnose_expedition(ws)
    by_id = {p["id"]: p for p in report["patterns"]}
    _req("CS-04" in by_id, f"CS-04 missing from diagnose report: {sorted(by_id)}")
    return by_id["CS-04"]


class TestCS04DataRights(unittest.TestCase):
    def test_disclosed_rights_proxy_lines_are_not_scored(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_cs04_ok_") as td:
            ws = Path(td) / "ws"
            init_workspace(ws, domain="biology")
            for idx, line in enumerate(DISCLOSED):
                write_lf_text(ws / "probes" / "biology" / f"note_{idx}.md", f"# Note {idx}\n\n{line}\n")
            cs04 = _cs04(ws)
            _req(cs04["risk_score"] == 0, f"disclosed rights/authorization proxy lines were scored: {cs04}")
            _req(cs04["evidence"] == [], f"disclosed lines produced evidence: {cs04['evidence']}")

    def test_undisclosed_proxy_is_still_scored_next_to_disclosed_one(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_cs04_bad_") as td:
            ws = Path(td) / "ws"
            init_workspace(ws, domain="biology")
            write_lf_text(
                ws / "probes" / "biology" / "notes.md",
                f"# Notes\n\n{DISCLOSED[0]}\n{UNDISCLOSED}\n",
            )
            cs04 = _cs04(ws)
            _req(cs04["risk_score"] == 40, f"undisclosed proxy must score exactly 40: {cs04}")
            _req(
                cs04["evidence"] == ["probes/biology/notes.md:4: possible unaddressed toy/proxy substitution"],
                f"evidence must name only the undisclosed line: {cs04['evidence']}",
            )

    def test_remediation_allows_for_rights_and_authorization(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_cs04_rem_") as td:
            ws = Path(td) / "ws"
            init_workspace(ws, domain="biology")
            remediation = _cs04(ws)["remediation"]
            _req("where rights and authorization allow" in remediation, f"remediation lacks rights clause: {remediation}")
            _req("label the synthetic input" in remediation, f"remediation lacks labelling instruction: {remediation}")
            _req("zero synthetic proxy substitution" not in remediation, f"remediation still unconditional: {remediation}")


class TestDiagnoseMustFailControls(unittest.TestCase):
    """Must-fail controls for the two refusal sites in aletheia/diagnose.py (R5)."""

    def test_missing_expedition_dir_is_refused(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_diag_missing_") as td:
            missing = Path(td) / "does-not-exist"
            with self.assertRaises(AletheiaError) as ctx:
                diagnose_expedition(missing)
            _req(ctx.exception.code == "EXPEDITION_DIR_NOT_FOUND", f"wrong code: {ctx.exception.code}")

    def test_missing_board_file_is_refused(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_diag_board_") as td:
            ws = Path(td) / "ws"
            init_workspace(ws, domain="biology")
            with self.assertRaises(AletheiaError) as ctx:
                diagnose_expedition(ws, board_path=Path(td) / "no-board.jsonl")
            _req(ctx.exception.code == "BOARD_NOT_FOUND", f"wrong code: {ctx.exception.code}")


if __name__ == "__main__":
    unittest.main()
