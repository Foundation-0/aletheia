# Prompt Template: Single-Agent Aletheia Resonance Loop

Use this prompt when operating **without** a multi-agent swarm (a single agent, notebook, or human-AI conversation) across any scientific, engineering, biological, or computational domain.

---

```markdown
You are executing **The Aletheia Method** (*Portal-Driven Resonance & Adversarial Tomography*) in **Single-Agent Phase-Separated Mode** on `<RESEARCH_TOPIC_OR_SOURCE>`.

To prevent confirmation bias and premature dismissal, strictly separate each research cycle into FOUR explicit phases—label every response with its active phase tag and NEVER blend `[PROBE]` and `[TOMOGRAPHY]` in the same step:

## Phase 1 — `[PORTAL]` Unconcealment
- Inspect `<RAW_SOURCES_AND_TARGET_REPOS>` read-only.
- Write 3–5 **steelmanned** hypotheses into `cartography/frontier_portals.md`.
- For each lead, explicitly separate: (a) repairable prototype bugs/friction, (b) the strongest repaired exact mathematical/physical/empirical form, and (c) the decisive falsification test & oracle class (`exact` / `sampled` / `anchor`).
- Check actual peer PRs/literature full texts before starting so you do not duplicate `N0` work.

## Phase 2 — `[PROBE]` Executable Realization
- Pick the highest-leverage steelmanned hypothesis and write ONE deterministic, LF-only, zero-bare-assert script in `probes/` testing it directly against the **real** upstream equations, code, or dataset (zero proxy substitution).
- Include explicit must-fail controls (R5) and run `python3 -I -B`, `python3 -I -O -B`, `python3 -I -B -W error` (R4).
- Immediately log every unexpected coincidence, exact cancellation, symmetry, breakdown of a textbook prior, or obstruction.

## Phase 3 — `[TOMOGRAPHY]` Independent Adversarial Audit
- Shift strictly into adversarial verifier mode ($\mathcal{G}_{\mathrm{obs}}$) — ideally in a fresh context window or isolated subagent call.
- Build a **zero-shared-code** clean-room check in `verification/checks/check_NNN_*.py`.
- Attack the Phase 2 claim from independent bases: degenerate/boundary inputs, alternative metrics, twin uncoupled/shuffled/IAAFT nulls, unseen seeds, R5 refusal-site mutations (`python3 -m aletheia mutate`), R6/R7 pinned-and-measured checks, and full-text prior-art verification.
- Append the honest verdict (`VERIFIED` / `PARTIAL/FRAGILE` / `FALSIFIED`), oracle class, novelty (`N0`/`N1`/`N2`), and explicit scope caveats permanently to `verification/AUDIT_LOG.md`.

## Phase 4 — `[RESONANCE]` Portal Re-Entry
- Do NOT stop at a `PARTIAL/FRAGILE` counterexample or a proved sharpness wall.
- Feed every Phase 2 anomaly and Phase 3 finding back into `[PORTAL]` to:
  (a) repair fixable gates and re-audit (`AUDIT-NNNR`),
  (b) elevate proven impossibilities into standalone theorems,
  (c) identify the next higher-order invariant needed to break a sharpness wall, or
  (d) package compute-limited frontiers into a portable Wave 2+ manifest (`python3 -m aletheia handoff`).

Run `python3 -m aletheia audit-check .` and `python3 -m aletheia diagnose .` at the end of every cycle.

## Context Lifecycle (`CS-26`, Single Agent)
- At each phase boundary, write state to disk (`frontier_portals.md`, `AUDIT_LOG.md`, probe outputs) so the next phase can start from a fresh context; long logs and payloads stay in external files, summarized by verdict + path + digest.
- Before a long idle gap on a bloated thread (default `>150000` tokens, TTL `300` s), compact or close the thread and reopen against the disk artifacts rather than paying a cold full-history reactivation (`python3 -m aletheia context-hygiene --self-test`).
```
