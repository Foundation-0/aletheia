---
name: aletheia-research
description: >-
  The Aletheia Method (Portal-Driven Resonance & Adversarial Tomography): the default
  research methodology for scientific, mathematical, physical, biological, systems,
  and cross-repository discovery. Activate when running open-ended research, designing
  a discovery swarm, mining raw notes/repos/data as live portals, steelmanning rough
  prototypes into exact theorems, or running independent multi-basis adversarial
  verification.
---

# The Aletheia Method (Portal-Driven Resonance & Adversarial Tomography)

Use this runbook to execute **The Aletheia Method** in either a **multi-agent swarm** or a **single-agent session**. It prevents the twin failure modes of AI research: *premature dismissal of new truths due to prototype bugs* and *hallucinated unity / repackaging of known parts*.

## References & Canonical Specs

- [QUICK_REFERENCE.md](references/QUICK_REFERENCE.md) — Compact oracle matrix, 11 Cave-Shadow red flags (`CS-01..CS-11`), CLI cheatsheet, and repo map
- Full treatise: [THEORY.md](../../../../../THEORY.md)
- Formal specification (5 Laws, 9 Gates, R1–R5, Novelty Bar): [spec/LAWS_AND_GATES.md](../../../../../spec/LAWS_AND_GATES.md)
- Modular prompt templates: [prompts/coordinator.md](../../../../../prompts/coordinator.md), [prompts/portal-keeper.md](../../../../../prompts/portal-keeper.md), [prompts/verifier-tomography.md](../../../../../prompts/verifier-tomography.md), [prompts/single-agent-loop.md](../../../../../prompts/single-agent-loop.md)
- Domain adaptation packs: [domains/README.md](../../../../../domains/README.md)

---

## 1. Multi-Agent Swarm Architecture

Spawn **4–5 distinct, non-colliding roles** (each with an exclusive write directory; raw sources and upstream repos strictly read-only):

1. **`portal-keeper` (Cartographer — CENTRAL & CONTINUOUS):**
   - Never parks after Round 1. Mines raw sources into structured entry points AND a steelmanned `cartography/frontier_portals.md`.
   - Re-enters raw sources whenever any probe reports an anomaly, dimensionless coincidence, obstruction, or sharpness wall, deriving the sharpest next equation/experiment and routing it to peers.
2. **`<domain>-probe` (2–3 Domain Explorers):**
   - Test steelmanned hypotheses directly against real upstream equations, code, or data (zero synthetic proxy substitution).
   - Loop every surprise, exact cancellation, or obstruction back to `@portal-keeper` immediately.
3. **`synthesizer` (Cross-Domain Operator Architect):**
   - Tests whether structures across domains share exact algebraic/operator maps, dualities, or Schur complements (Law 5 / Gate 5: zero language smuggling).
4. **`verifier` (Adversarial Tomography Oracle $\mathcal{G}_{\mathrm{obs}}$):**
   - Writes zero-shared-code independent verifiers in `verification/checks/check_NNN_*.py` and logs every verdict (`VERIFIED`, `PARTIAL/FRAGILE`, `FALSIFIED`) permanently in `verification/AUDIT_LOG.md`.
   - When finding a defect, supplies both the minimal failing witness and—where the core truth holds—the exact hypothesis/gate repair.
5. **`peer-weaver` (Ecosystem & Compute Handoff):**
   - Reads actual peer PR diffs and full-text prior art so the swarm never duplicates `N0` work, maps uncharted seams, indexes verified Draft PRs, and packages portable Wave 2+ compute manifests (`aletheia handoff`).

**Branch-Spawning Rule:** Spawn a dedicated specialist theorem/experiment branch ONLY once (a) a core foundation has cleared `VERIFIED` audit, and (b) an explicit obstruction or sharpness proof pinpoints the higher-order object needed to push past it.

---

## 2. Single-Agent Execution Loop (Strict Phase Separation)

When working without a swarm, run four explicit phases rather than blending critique and invention in a single pass:

1. **Portal Phase (Unconcealment + Beyond-Language Lens):** Strip disciplinary nouns and arbitrary base-10/coordinate numerology (*Stage A*), compress perceived relational silhouettes into coordinate-, unit-, and radix-free exact invariants or zero-residual null-equivalences (*Stage B*), and record 3–5 steelmanned exact hypotheses in `cartography/frontier_portals.md`. Do not dismiss any rough lead before writing down its strongest repaired form.
2. **Probe Phase (Realization):** Implement one concrete hypothesis deterministically against real target equations/data; log anomalies and coincidences immediately.
3. **Tomography Phase (Clean-Room Audit):** Run an independent zero-shared-code verification script enforcing exact/null oracles, coordinate/basis/unit invariance, R1–R5 gates, and full-text prior-art checks; log the honest verdict in `verification/AUDIT_LOG.md`.
4. **Resonance Phase (Portal Re-Entry):** Feed every anomaly, counterexample, or sharpness wall back into the Portal Phase before moving to a new topic.

---

## 3. Executable CLI Workflow (v1.2)

```bash
python3 -m aletheia init my-expedition --domain physics
python3 -m aletheia audit-check my-expedition --lean-audit --json  # supports --allow-project-import, --comparator-config, --pinned-manifest, --prereg-check
python3 -m aletheia mutate path/to/verifier.py --work-root . --test-cmd "python3 -I -O -B path/to/test.py"
python3 -m aletheia diagnose my-expedition        # checks CS-01..CS-11 (incl. truncation mirages, collision denominators & unit/radix fragility)
python3 -m aletheia ratchet --demo              # 5-gate anti-Goodhart, noise-immune, CS-08-capped ratchet
python3 -m aletheia mde --demo                  # Plane-1 zone-canon-v0 manifest, causal DAG & SYM-2P/2.0-rcp
python3 -m aletheia handoff manifests/wave2.json --init-template
```

Every verification script must use zero bare `assert`s on validation paths, LF-only line endings, and produce identical verdicts across `python3 -I -B`, `python3 -I -O -B`, and `python3 -I -B -W error`.
