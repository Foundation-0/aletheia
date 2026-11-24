"""
Count binding: agent-facing text must state the gate and contract counts that
`spec/LAWS_AND_GATES.md` states.

The spec defines its gates as lines `N. **Gate N — <title>:**` and its contracts
as table rows `| **Rk — <name>** |`. These tests derive both from the spec and
check that the protocol written by `aletheia init` / `aletheia install --target
repo` (`aletheia.scaffold._protocol_markdown`) names every gate by its spec title,
R6, R7, Law 2b and Own-Terms-First, and carries no v1 counts.

Modelled on `Foundation-0/project-asma` `tests/test_claim_counts.py` (header
counts must equal the row counts) and on `Foundation-0/cave-expedition`
`verification/outside/check_totals.py` (stale totals must be gone from the text).

Zero external dependencies. Zero bare assert statements (100% R4 parity across
`-I -B`, `-I -O -B`, and `-I -B -W error`).
"""
from __future__ import annotations

from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia.scaffold import _protocol_markdown

SPEC_PATH = ROOT / "spec" / "LAWS_AND_GATES.md"

_SPEC_GATE_RE = re.compile(r"^(\d+)\. \*\*Gate (\d+) — (.+?):\*\*", re.MULTILINE)
_SPEC_CONTRACT_RE = re.compile(r"^\| \*\*R(\d+) — ([^*|]+)\*\* \|", re.MULTILINE)
_ISSUE_REF_RE = re.compile(r"\s*\(`aletheia#\d+`[^)]*\)")

# v1-era count claims (the spec now has 10 gates and R1-R7).
_NINE_GATES_RE = re.compile(r"(?<![\w.])(?:nine|9)(?:[ -]+[A-Za-z-]+){0,2}[ -]+gates?\b", re.IGNORECASE)
_V1_TITLE_RE = re.compile(r"^#.*\bAletheia v1\b(?!\.)", re.MULTILINE)
_R1_R5_RE = re.compile(r"R1`?\s*(?:–|-|—|to)\s*`?R5\b")


def _req(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _norm_title(title: str) -> str:
    """Drop issue references such as (`aletheia#2`) that only make sense inside this repo."""
    return _ISSUE_REF_RE.sub("", title).strip()


def spec_gates() -> dict[int, str]:
    text = SPEC_PATH.read_text(encoding="utf-8")
    gates: dict[int, str] = {}
    for item, num, title in _SPEC_GATE_RE.findall(text):
        _req(item == num, f"spec list item {item} carries Gate {num}")
        _req(int(num) not in gates, f"spec defines Gate {num} twice")
        gates[int(num)] = _norm_title(title)
    _req(len(gates) > 0, "no `N. **Gate N — ...:**` lines found in the spec")
    _req(sorted(gates) == list(range(1, len(gates) + 1)), f"spec gate numbers are not 1..n: {sorted(gates)}")
    return gates


def spec_contracts() -> list[int]:
    text = SPEC_PATH.read_text(encoding="utf-8")
    nums = [int(n) for n, _ in _SPEC_CONTRACT_RE.findall(text)]
    _req(len(nums) > 0, "no `| **Rk — ...** |` rows found in the spec")
    _req(nums == list(range(1, len(nums) + 1)), f"spec contract numbers are not R1..Rk in order: {nums}")
    return nums


def stale_count_claims(text: str) -> list[str]:
    """Return the v1-era count phrases found in `text` (nine gates, an Aletheia v1 title, bare R1-R5)."""
    hits: list[str] = []
    hits.extend(m.group(0) for m in _NINE_GATES_RE.finditer(text))
    hits.extend(m.group(0) for m in _V1_TITLE_RE.finditer(text))
    hits.extend(m.group(0) for m in _R1_R5_RE.finditer(text))
    return hits


class TestSpecCounts(unittest.TestCase):
    def test_spec_states_ten_gates_and_r1_to_r7(self) -> None:
        # Pinned on purpose: when the spec changes its counts, this test fails and the
        # agent-facing text checked below must be updated in the same change.
        gates = spec_gates()
        _req(len(gates) == 10, f"spec gate count changed: {len(gates)}; update agent-facing text and this pin")
        _req(spec_contracts() == [1, 2, 3, 4, 5, 6, 7], f"spec contracts changed: {spec_contracts()}")

    def test_stale_pattern_controls(self) -> None:
        # Must-flag controls.
        for bad in (
            "The Nine Verification Gates",
            "5 Laws, 9 Gates, R1–R5, Novelty Bar",
            "9 anti-shadow verification gates",
            "a 9-gate verification protocol",
            "# Anti-Shadow Adversarial Verification Protocol (Aletheia v1)",
            "Enforce R1-R5 gate integrity",
            "contracts `R1`–`R5`",
        ):
            _req(stale_count_claims(bad) != [], f"stale phrase not flagged: {bad!r}")
        # Must-pass controls: legitimate phrases that mention other counts.
        for ok in (
            "the 10 Verification Gates and R1–R7",
            "5-gate autonomous ratchet",
            "docs/09-gate-contracts.md",
            "Enforce R1–R4 fail-closed parsing",
            "Aletheia v1.3 introduces the glyphs",
            "Gate 9 — Mechanism-First Prior Art",
        ):
            _req(stale_count_claims(ok) == [], f"legitimate phrase flagged: {ok!r} -> {stale_count_claims(ok)}")


# Agent-instruction and documentation files: no v1 counts at all.
DOC_FILES = ("AGENTS.md", "README.md", "THEORY.md", "CONTRIBUTING.md")
DOC_GLOBS = ("adapters/**/*", ".agents/**/*", "agents/**/*", "prompts/**/*", "domains/**/*", "docs/**/*")
DOC_SUFFIXES = (".md", ".mdc", ".json", ".html", ".txt")
# Intentional R1-R5 mentions that scope a claim instead of stating the contract count.
ALLOWED_PHRASES = (
    "R1–R5 are necessary, not sufficient",  # spec section 4, quoted
    "R1 to R5 are the floor. R6 and R7 close the gap",  # docs/method/index.html
    "contracts R1–R5 and the two measurement contracts R6–R7",  # domains/computer-science-and-systems.md
)

# Tool help strings and generated CI step names: R1-R5 may appear only in the scoped form,
# and each listed file must carry the scope note (R6/R7 exist only as library certifiers).
TOOL_SCOPE_NOTE = "R6/R7 not automated by this command"
TOOL_FILES = {"aletheia/cli.py": 2, "aletheia/audit_check.py": 2, "aletheia/installer.py": 1}

# Agent instructions: a line that names `audit-check` next to R6/R7 must say that no command runs them
# (`audit-check` runs no R6/R7 check; they exist only as `aletheia.gates_v2.evaluate_r6_r7_gate`).
AGENT_INSTRUCTION_PREFIXES = ("AGENTS.md", "adapters/", ".agents/", "agents/", "prompts/", "domains/")
_AUDIT_CHECK_RE = re.compile(r"\baudit-check\b")
_R6_R7_RE = re.compile(r"\bR[67]\b|R1`?\s*(?:–|-|—|to)\s*`?R7\b")
_R6_R7_SCOPE_RE = re.compile(r"does not run|not automated|no CLI command runs", re.IGNORECASE)


def audit_check_r6_r7_overclaims(line: str) -> bool:
    """True when `line` names `audit-check` and R6/R7 without saying that no command runs R6/R7."""
    return (
        _AUDIT_CHECK_RE.search(line) is not None
        and _R6_R7_RE.search(line) is not None
        and _R6_R7_SCOPE_RE.search(line) is None
    )


def doc_files() -> list[Path]:
    paths = {ROOT / rel for rel in DOC_FILES}
    for pattern in DOC_GLOBS:
        paths.update(p for p in ROOT.glob(pattern) if p.is_file() and p.suffix in DOC_SUFFIXES)
    return sorted(p for p in paths if p.is_file())


def doc_stale_hits() -> list[str]:
    hits: list[str] = []
    for path in doc_files():
        rel = path.relative_to(ROOT).as_posix()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for allowed in ALLOWED_PHRASES:
                line = line.replace(allowed, "")
            hits.extend(f"{rel}:{lineno}: {phrase}" for phrase in stale_count_claims(line))
    return hits


class TestAgentFacingCounts(unittest.TestCase):
    def test_doc_scope_covers_the_adapters_prompts_and_packs(self) -> None:
        rels = {p.relative_to(ROOT).as_posix() for p in doc_files()}
        for must in (
            "AGENTS.md",
            "adapters/README.md",
            "adapters/claude-code/CLAUDE.md",
            "adapters/cursor/.cursor/rules/aletheia-research.mdc",
            ".agents/plugins/aletheia-research/skills/aletheia-research/SKILL.md",
            "prompts/verifier-tomography.md",
            "domains/README.md",
        ):
            _req(must in rels, f"count-binding scan misses {must}")

    def test_agent_instruction_and_doc_files_carry_no_v1_counts(self) -> None:
        hits = doc_stale_hits()
        _req(hits == [], "v1 count claims (spec: 10 gates, R1-R7):\n" + "\n".join(hits))

    def test_tool_help_strings_scope_r1_r5_and_r6_r7(self) -> None:
        for rel, min_notes in TOOL_FILES.items():
            text = (ROOT / rel).read_text(encoding="utf-8")
            notes = text.count(TOOL_SCOPE_NOTE)
            _req(notes >= min_notes, f"{rel}: {notes} scope note(s) {TOOL_SCOPE_NOTE!r}, expected >= {min_notes}")
            for lineno, line in enumerate(text.splitlines(), start=1):
                _req(_NINE_GATES_RE.search(line) is None, f"{rel}:{lineno}: nine-gate claim")
                if _R1_R5_RE.search(line) is not None:
                    _req(TOOL_SCOPE_NOTE in line, f"{rel}:{lineno}: R1-R5 without the scope note: {line.strip()}")


    def test_audit_check_is_not_said_to_verify_r6_r7(self) -> None:
        # Must-flag control: the synthesizer wording this test was written for.
        _req(
            audit_check_r6_r7_overclaims(
                "dedicated must-fail controls (R5), checks pinned before any submission (R6), and compared values "
                "recomputed from the bytes (R7), verifying cleanly with `python3 -m aletheia mutate` and "
                "`python3 -m aletheia audit-check`."
            ),
            "overclaim control not flagged",
        )
        # Must-pass controls.
        for ok in (
            "`aletheia.gates_v2.evaluate_r6_r7_gate` implements R6 and R7 as a library certifier; `aletheia audit-check` does not run them.",
            "Verify R4 hygiene with `audit-check`. No CLI command runs R6/R7 on your instrument.",
            "Run `aletheia audit-check .` before every Draft PR.",
        ):
            _req(not audit_check_r6_r7_overclaims(ok), f"scoped line flagged: {ok!r}")
        hits: list[str] = []
        for path in doc_files():
            rel = path.relative_to(ROOT).as_posix()
            if not rel.startswith(AGENT_INSTRUCTION_PREFIXES):
                continue
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if audit_check_r6_r7_overclaims(line):
                    hits.append(f"{rel}:{lineno}: {line.strip()[:160]}")
        _req(hits == [], "audit-check named next to R6/R7 without saying no command runs them:\n" + "\n".join(hits))


class TestScaffoldProtocol(unittest.TestCase):
    def test_protocol_names_every_spec_gate_by_title(self) -> None:
        text = _protocol_markdown("x")
        found = {int(num): _norm_title(title) for _, num, title in _SPEC_GATE_RE.findall(text)}
        gates = spec_gates()
        _req(sorted(found) == sorted(gates), f"protocol gates {sorted(found)} != spec gates {sorted(gates)}")
        for num, title in gates.items():
            _req(found[num] == title, f"Gate {num} title differs: protocol {found[num]!r} vs spec {title!r}")
        count_word = {10: "Ten"}.get(len(gates), str(len(gates)))
        _req(f"## The {count_word} Verification Gates" in text, f"protocol heading does not state {len(gates)} gates")

    def test_protocol_names_contracts_laws_and_oracles(self) -> None:
        text = _protocol_markdown("x")
        for k in spec_contracts():
            _req(f"(R{k})" in text, f"protocol does not define R{k}")
        for needle in ("Law 2b", "Own-Terms-First", "`reference_replay`", "R1–R5 are necessary, not sufficient"):
            _req(needle in text, f"protocol lacks {needle!r}")
        _req(text.startswith("# Anti-Shadow Adversarial Verification Protocol (Aletheia v2)\n"), "protocol title is not v2")

    def test_protocol_has_no_stale_counts(self) -> None:
        text = _protocol_markdown("x")
        # The only R1-R5 mention allowed is the spec's own scoping sentence.
        scrubbed = text.replace("R1–R5 are necessary, not sufficient", "")
        hits = stale_count_claims(scrubbed)
        _req(hits == [], f"scaffold protocol carries v1 counts: {hits}")


if __name__ == "__main__":
    unittest.main()
