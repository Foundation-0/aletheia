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
from aletheia.installer import _build_install_plan
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
# The rights words match as whole words only: these lines contain them inside other words and stay scored.
NOT_DISCLOSED_SUBSTRINGS = (
    "Used an unauthorized synthetic proxy for the headline table.",
    "Synthetic proxy for the copyrights table.",
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

    def test_rights_words_inside_other_words_do_not_exempt(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_cs04_sub_") as td:
            ws = Path(td) / "ws"
            init_workspace(ws, domain="biology")
            body = "".join(f"{line}\n" for line in NOT_DISCLOSED_SUBSTRINGS)
            write_lf_text(ws / "probes" / "biology" / "notes.md", f"# Notes\n\n{body}")
            cs04 = _cs04(ws)
            _req(cs04["risk_score"] == 80, f"both substring-only lines must score 40 each: {cs04}")
            _req(
                cs04["evidence"] == [
                    "probes/biology/notes.md:3: possible unaddressed toy/proxy substitution",
                    "probes/biology/notes.md:4: possible unaddressed toy/proxy substitution",
                ],
                f"evidence must name both substring-only lines: {cs04['evidence']}",
            )

    def test_remediation_allows_for_rights_and_authorization(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_cs04_rem_") as td:
            ws = Path(td) / "ws"
            init_workspace(ws, domain="biology")
            remediation = _cs04(ws)["remediation"]
            _req("where rights and authorization allow" in remediation, f"remediation lacks rights clause: {remediation}")
            _req("label the synthetic input" in remediation, f"remediation lacks labelling instruction: {remediation}")
            _req("zero synthetic proxy substitution" not in remediation, f"remediation still unconditional: {remediation}")


class TestInstallerEmbeddedTemplates(unittest.TestCase):
    """The standalone `aletheia install` templates qualify live-data probing by rights."""

    def test_probe_wording_is_conditional_on_rights_and_authorization(self) -> None:
        skill = dict(_build_install_plan("antigravity", None))["skills/aletheia-research/SKILL.md"]
        command = dict(_build_install_plan("claude-code", None))[".claude/commands/aletheia.md"]
        for name, text in (("SKILL.md", skill), ("commands/aletheia.md", command)):
            _req("where rights and authorization allow" in text, f"{name} lacks the rights qualifier")
            _req("label any synthetic input as synthetic" in text, f"{name} lacks the labelling instruction")
            _req("zero synthetic proxy substitution" not in text, f"{name} still demands live data unconditionally")


class TestPostingSignOff(unittest.TestCase):
    """Role prompts route sign-off for posting outside the workspace to a named human, not an agent."""

    def test_no_prompt_lets_the_coordinator_authorize_posting(self) -> None:
        for path in sorted((ROOT / "prompts").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            _req("coordinator sign-off" not in text.lower(), f"{path.name} still lets the coordinator agent sign off")

    def test_posting_roles_name_the_accountable_human(self) -> None:
        for name in ("coordinator.md", "peer-weaver.md", "domain-probe.md", "synthesizer.md"):
            text = (ROOT / "prompts" / name).read_text(encoding="utf-8")
            _req("`<ACCOUNTABLE_HUMAN>`" in text, f"prompts/{name} does not name the accountable human")
            _req("not enforce" in text, f"prompts/{name} does not say the rule is unenforced by the tools")


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
