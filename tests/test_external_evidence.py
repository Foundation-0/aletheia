"""
Every cave-expedition check script this repository cites must have a row in
`evidence/EXTERNAL_EVIDENCE.md`, and no line may call a script that the index
lists as `not on main at 9729839` archived.

The idea comes from cave-expedition's revision table
(`verification/outside/README.md:18-28`) and its stale-text guard
(`verification/outside/check_totals.py`). This test reads only this
repository: it guards aletheia's own text against its own index and cannot
detect a change in a sibling repository. `aletheia twin-check` covers the
audit ids and the check-script count; it does not look at individual
`check_NNN` citations.

Zero external dependencies. Zero bare assert statements (same result under
`-I -B`, `-I -O -B` and `-I -B -W error`).
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "evidence" / "EXTERNAL_EVIDENCE.md"
NOT_ON_MAIN = "not on main at 9729839"

TOKEN = re.compile(r"\bcheck_(\d{3})(?!\d)")
RANGE = re.compile(r"\bcheck_(\d{3})`?\s*(?:–|-|to)\s*`?check_(\d{3})(?!\d)")
ARCHIVED = re.compile(r"(?<!reported as )\barchived\b", re.IGNORECASE)


def _req(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _citing_documents() -> dict[str, str]:
    paths = [ROOT / "README.md", ROOT / "THEORY.md", ROOT / "CHANGELOG.md"]
    for sub, pattern in (("spec", "*.md"), ("domains", "*.md"), ("evidence", "*.md"), ("docs", "*.html")):
        paths.extend(sorted((ROOT / sub).rglob(pattern)))
    return {p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8") for p in paths if p.is_file()}


def parse_index(text: str) -> tuple[dict[int, str], list[str]]:
    """Map each check number in the index's first column to its status cell."""
    status: dict[int, str] = {}
    problems: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 6:
            continue
        first, row_status = cells[0], cells[2]
        nums: set[int] = set()
        for lo_s, hi_s in RANGE.findall(first):
            lo, hi = int(lo_s), int(hi_s)
            if lo > hi:
                problems.append(f"index line {lineno}: range check_{lo:03d} to check_{hi:03d} runs backwards")
                continue
            nums.update(range(lo, hi + 1))
        nums.update(int(n) for n in TOKEN.findall(first))
        for n in sorted(nums):
            if n in status and status[n] != row_status:
                problems.append(f"index line {lineno}: check_{n:03d} listed twice with different status")
            status[n] = row_status
    if not status:
        problems.append("index lists no check scripts")
    return status, problems


def citation_problems(index_text: str, documents: dict[str, str]) -> list[str]:
    status, problems = parse_index(index_text)
    for name in sorted(documents):
        for lineno, line in enumerate(documents[name].splitlines(), 1):
            for n in sorted({int(m) for m in TOKEN.findall(line)}):
                if n not in status:
                    problems.append(
                        f"{name}:{lineno} cites check_{n:03d}, which evidence/EXTERNAL_EVIDENCE.md does not list"
                    )
                elif status[n] == NOT_ON_MAIN and ARCHIVED.search(line):
                    problems.append(
                        f"{name}:{lineno} calls check_{n:03d} archived, but the index lists it as {NOT_ON_MAIN}"
                    )
    return problems


SYNTHETIC_INDEX = "\n".join([
    "| Cited as | Repo | Status | Revision read | Path | sha256 |",
    "|---|---|---|---|---|---|",
    "| `check_001`–`check_003` | r | main | x | p | none |",
    "| `check_016`–`check_025` | r | not on main at 9729839 | x | none on main | none |",
])


class ExternalEvidenceIndex(unittest.TestCase):
    def test_repository_citations_match_index(self) -> None:
        problems = citation_problems(INDEX.read_text(encoding="utf-8"), _citing_documents())
        _req(problems == [], "external-evidence problems:\n" + "\n".join(problems))

    def test_index_parses_known_rows(self) -> None:
        status, problems = parse_index(INDEX.read_text(encoding="utf-8"))
        _req(problems == [], "index parse problems: " + "; ".join(problems))
        _req(status.get(1) == "main" and status.get(14) == "main", "check_001 and check_014 must read as main")
        _req(status.get(15) is None, "check_015 must not be indexed: no such script is cited")
        for n in (16, 20, 25, 26, 30, 40, 42, 45):
            _req(status.get(n) == NOT_ON_MAIN, f"check_{n:03d} must read as {NOT_ON_MAIN}")

    def test_must_fail_unindexed_citation(self) -> None:
        problems = citation_problems(SYNTHETIC_INDEX, {"a.md": "verified by `check_099`"})
        _req(len(problems) == 1 and "check_099" in problems[0], f"unindexed citation not caught: {problems}")

    def test_must_fail_archived_claim(self) -> None:
        docs = {"a.md": "Scripts (`check_016`–`check_025`) are archived in the sibling repo."}
        problems = citation_problems(SYNTHETIC_INDEX, docs)
        _req(len(problems) == 2 and all("archived" in p for p in problems), f"archived claim not caught: {problems}")
        docs = {"a.md": "Scripts in the middle of the range, `check_020`, are Archived there."}
        problems = citation_problems(SYNTHETIC_INDEX, docs)
        _req(len(problems) == 1 and "check_020" in problems[0], f"range member or case not caught: {problems}")

    def test_allowed_wording_passes(self) -> None:
        docs = {
            "a.md": "Scripts (`check_016`–`check_025`) were reported as archived; they are not on its main branch.",
            "b.md": "`check_002` is archived on main.",
            "c.md": "`check_totals.py` and `check_NNN` are not numbered citations.",
        }
        problems = citation_problems(SYNTHETIC_INDEX, docs)
        _req(problems == [], f"allowed wording rejected: {problems}")

    def test_must_fail_empty_or_backwards_index(self) -> None:
        _status, problems = parse_index("no table here")
        _req(problems == ["index lists no check scripts"], f"empty index not caught: {problems}")
        backwards = SYNTHETIC_INDEX + "\n| `check_009`–`check_007` | r | main | x | p | none |"
        _status, problems = parse_index(backwards)
        _req(any("runs backwards" in p for p in problems), f"backwards range not caught: {problems}")
        conflicting = SYNTHETIC_INDEX + "\n| `check_002` | r | not on main at 9729839 | x | p | none |"
        _status, problems = parse_index(conflicting)
        _req(any("listed twice" in p for p in problems), f"conflicting status not caught: {problems}")


if __name__ == "__main__":
    unittest.main()
