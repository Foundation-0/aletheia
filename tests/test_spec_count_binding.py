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
