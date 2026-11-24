# CLAUDE.md — The Aletheia Method

Follow **The Aletheia Method** (*Portal-Driven Resonance & Adversarial Tomography*) for all scientific, mathematical, physical, biological, systems, and exploratory research in this repository.

## The 5 Laws

1. **Active Portal-Keeper Loop:** Raw transcripts, notes, datasets, and rough drafts are *portals into new frontiers*, never static papers to grade once. Keep `cartography/frontier_portals.md` alive across every iteration—re-enter raw sources whenever a probe hits an anomaly, coincidence, counterexample, or sharpness wall.
2. **Steelman Before Falsifying:** Separate *prototype friction* (indexing bugs, missing guards, rough stubs, overly strong premises) from the underlying scientific or mathematical truth. Diagnose defects honestly, then formulate and test the **strongest repaired version** before closing any branch.
3. **Adversarial Verification as Multi-Basis Tomography ($\mathcal{G}_{\mathrm{obs}}$):** Never self-certify inside the authoring turn. Delegate independent verification to the `verifier-tomography` subagent (or a clean-room script sharing zero helper code):
   - `exact` claims: pure `int` / `Fraction` / $\mathbb{Q}(i)$ / $\mathbb{Z}[\sqrt{2}]$ / `isqrt` / `SymPy` / Lean 4 (never float tolerances or unverified solver flags).
   - `sampled` claims: logged seeds, held-out/disjoint splits, matched adversarial nulls (IAAFT, twin uncoupled systems, shuffled/decoy controls), unseen-seed replay.
   - `anchor` claims: live execution of the untouched upstream reference model.
   - R1–R7 gates & R4 runtime parity: zero bare `assert`s on validation paths; bit-identical results across `python3 -I -B`, `python3 -I -O -B`, and `python3 -I -B -W error`; R6: the gate owner pins the check list and thresholds before any submission; R7: every compared value is recomputed from the bytes, never taken from a submitter-declared field (`spec/LAWS_AND_GATES.md` §4).
4. **Honest Novelty & Scope Accounting:** Default every claim to `N0` until full-text prior-art verification (never titles from memory) confirms `N1` or `N2`. Log every `VERIFIED`, `PARTIAL/FRAGILE`, and `FALSIFIED` verdict permanently in `verification/AUDIT_LOG.md`. Never inflate Draft PRs to merged or `uncompiled_source` to machine-checked.
5. **Exact-Operator Cross-Pollination:** Zero language smuggling. Cross-domain bridges require explicit typed objects, executable maps/identities, quantitative closure defects, or provable obstructions—and obstructions are elevated into theorems or branch triggers.

## Subagents & Commands

- Use `/aletheia` (`.claude/commands/aletheia.md`) to kick off a structured 4-phase cycle (**Portal $\to$ Probe $\to$ Tomography $\to$ Resonance**).
- Invoke `portal-keeper` whenever a probe discovers a surprise, exact cancellation, or obstruction.
- Invoke `verifier-tomography` before accepting any claim or opening any Draft PR.
- Before pushing: run `python3 -m aletheia audit-check .` and `python3 -m aletheia diagnose .`; open Draft PRs on feature branches only (never merge to default branches).
