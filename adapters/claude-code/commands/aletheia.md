---
description: Launch an Aletheia Method (Portal-Driven Resonance & Adversarial Tomography) research cycle on a topic, raw source, or repository frontier.
argument-hint: "<research-topic-or-raw-source-path>"
---

Execute **The Aletheia Method** on `$ARGUMENTS` using strict phase separation (or subagents `portal-keeper` and `verifier-tomography`):

1. **Initialize Workspace (if absent):**
   Ensure exclusive directories exist (`cartography/`, `probes/`, `synthesis/`, `verification/checks/`, `peer-web/`) and `verification/AUDIT_LOG.md` is initialized (or run `python3 -m aletheia init .`).

2. **Phase 1 — Portal Phase (delegate to `portal-keeper` if available):**
   - Mine the raw material / target repos read-only.
   - Write or update `cartography/frontier_portals.md` with 3–5 **steelmanned** exact hypotheses, explicitly separating repairable prototype bugs from the strongest scientific/mathematical truth being reached for.
   - Check live peer PRs and full-text prior art so we do not duplicate `N0` work.

3. **Phase 2 — Probe Phase:**
   - Select the highest-leverage steelmanned hypothesis and build a deterministic, LF-only, zero-bare-assert script in `probes/` testing it directly against the **real** upstream equations, code, or data (zero synthetic proxy substitution).
   - Record every anomaly, exact cancellation, coincidence, or obstruction immediately.

4. **Phase 3 — Tomography Phase (delegate to `verifier-tomography`):**
   - Run an independent, zero-shared-code clean-room check in `verification/checks/check_NNN_*.py`.
   - Enforce the appropriate oracle class (`exact` / `sampled` / `anchor`), R1–R7 gates, R4 3-mode parity (`-I -B`, `-I -O -B`, `-I -B -W error`), and full-text prior-art novelty check (`N0`/`N1`/`N2`).
   - Log the permanent verdict (`VERIFIED` / `PARTIAL/FRAGILE` / `FALSIFIED`) in `verification/AUDIT_LOG.md`.

5. **Phase 4 — Resonance Phase (Portal Re-Entry):**
   - Do **not** terminate on a `PARTIAL/FRAGILE` verdict, counterexample, or sharpness wall. Feed the exact defect, tightness proof, or surprise back into Phase 1 (`portal-keeper`) to repair the gate, elevate an obstruction into a theorem, or unlock the next higher-order invariant.

6. **Automated Hygiene Check:**
   Run `python3 -m aletheia audit-check .` and `python3 -m aletheia diagnose .` before reporting results or opening a Draft PR.

7. **Context Hygiene (`CS-26`):**
   Between phases, persist state to disk and prefer fresh `portal-keeper` / `verifier-tomography` subagents over reusing bloated threads. Compact before long idle gaps instead of waking a large thread cold past cache TTL, keep payloads in external files (concise pointers in chat), and run `python3 -m aletheia context-hygiene --self-test` with the hygiene check.
