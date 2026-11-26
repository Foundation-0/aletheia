# Single-Agent & Human-AI Aletheia Loop (API / Web / Notebook Workflow)

You do **not** need a multi-agent swarm orchestrator to get the full benefit of **The Aletheia Method**. A single researcher working with any LLM (API, web interface, or notebook) reproduces the same resonance cavity by strictly separating **four phases** across distinct turns or fresh chat windows.

---

## Phase 1 — `[PORTAL]` Unconcealment (Open-Minded Generation)

**Goal:** Mine raw material (transcripts, papers, datasets, lab logs, open issues) and extract **3–5 steelmanned exact hypotheses**.

**Rules:**
- Do **not** dismiss a rough lead in Phase 1 just because an early script has a bug or a draft lemma missed a hypothesis.
- Record each lead in `cartography/frontier_portals.md` with four fields:
  1. **Raw anchor** (exact file/line/equation/dataset reference)
  2. **Repairable prototype friction** (what is rough or broken today)
  3. **Steelmanned strongest form** (the sharpest exact mathematical, physical, or empirical statement)
  4. **Decisive falsifiable test** (exact oracle class `exact` / `sampled` / `anchor` + what observation kills it)

---

## Phase 2 — `[PROBE]` Executable Realization

**Goal:** Test ONE steelmanned hypothesis against the **real** target equations, codebase, or dataset (zero synthetic proxy substitution).

**Rules:**
- Write a deterministic, self-contained script (`probes/<domain>/probe_NN.py`) with logged RNG seeds, zero bare `assert`s on trust paths, and explicit must-fail controls.
- Capture **every** surprise immediately: dimensionless coincidences (e.g. a ratio landing on `1`), unexpected symmetries or cancellations, sharp numerical ceilings, or exact obstructions.

---

## Phase 3 — `[TOMOGRAPHY]` Clean-Room Adversarial Audit

**Goal:** Try relentlessly to **break** Phase 2's claim from independent angles ($\mathcal{G}_{\mathrm{obs}}$).

**Best Practice:** Open a **fresh chat / fresh context window** (so you have zero anchoring bias from Phase 2) and paste ONLY the claim, the reproduction command, and [`SYSTEM_PROMPT.md`](SYSTEM_PROMPT.md).

**Checklist:**
1. **Zero shared code:** Re-derive or cross-check using an independent mathematical route or clean-room script.
2. **Adversarial controls:** Test edge cases the author skipped (zero/negative inputs, non-commuting/non-Hermitian cases, twin uncoupled systems, fresh seeds, alternative likelihood metrics).
3. **Runtime parity (R4):** Run under `python3 -I -B`, `python3 -I -O -B`, and `python3 -I -B -W error`.
4. **Full-text prior art:** Check actual full texts of nearest papers/PRs before upgrading novelty past `N0`.
5. **Constructive verdict:** Log `VERIFIED`, `PARTIAL/FRAGILE`, or `FALSIFIED` permanently in `verification/AUDIT_LOG.md`. If `PARTIAL/FRAGILE` or `FALSIFIED`, supply both the minimal counterexample and—if the core truth holds—the exact hypothesis tightening or gate repair.

---

## Phase 4 — `[RESONANCE]` Portal Re-Entry & Escalation

**Goal:** Turn every Phase 2 anomaly and every Phase 3 counterexample or sharpness wall into the **seed of the next cycle**.

**Decision Tree:**
- **`PARTIAL/FRAGILE` (repairable gate or premise):** Apply the exact repair and re-run Phase 3 cleanly (`AUDIT-NNNR`).
- **Sharpness wall proven** (e.g. "no stronger bound exists from moments 1–2"): Ask in Phase 1 what next-order invariant (moments 3–4, non-local ray, higher-order operator) breaks the wall.
- **Exact obstruction proven** (e.g. disconnected root graph, determinant-square obstruction): Elevate the obstruction into a clean theorem and pivot to the surviving non-obstructed cases.
- **Compute ceiling hit:** Package the verified baseline + exact Wave 2+ falsification gate into a portable handoff (`python3 -m aletheia handoff manifests/wave2.json --init-template`) for a stronger machine.

---

## Relapse Check (After Every 2 Cycles)

Ask yourself (or run `python3 -m aletheia diagnose .`):
- Have I produced 2+ dismissals in a row without testing a steelmanned repair? *(Premature Dismissal Bias)*
- Did I re-enter the raw portals after my last anomaly, or am I running on autopilot? *(Static-Map Trap)*
- Did I test a toy proxy instead of the real upstream equation/dataset? *(Substitution Shadow)*
- Did I claim cross-domain unity using shared words without an executable map? *(Language Smuggling)*

---

## Context Lifecycle (`CS-26`)

- End each phase by writing its state to disk; begin the next phase in a fresh window reading those files. Fresh context is both an independence device and the cheapest cache policy.
- Before a long pause in a bloated window, write a compact summary file and close the window; resuming the full stale history after the cache expires is the expensive path.
- Reference logs, diffs, and data by external file name plus digest; paste only the verdict and the next action.
