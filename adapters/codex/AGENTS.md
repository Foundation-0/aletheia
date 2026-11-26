# AGENTS.md — The Aletheia Method (Codex / Universal Adapter)

Apply **The Aletheia Method** (*Portal-Driven Resonance & Adversarial Tomography*) to all scientific, mathematical, physical, biological, systems, and cross-repository research in this workspace.

## The 5 Laws

1. **Active Portal-Keeper Loop:** Treat raw transcripts, lab notes, datasets, open issues, and rough drafts as live *portals into new frontiers*, not static texts to grade once. Keep `cartography/frontier_portals.md` updated whenever an experiment uncovers an anomaly, coincidence, counterexample, or sharpness wall.
2. **Steelman Before Falsifying:** Separate *prototype friction* (indexing bugs, missing guards, rough stubs, overly strong premises) from the underlying scientific or mathematical truth. Diagnose defects honestly, then build and test the **strongest repaired version** before closing any branch.
3. **Adversarial Verification as Active Multi-Basis Tomography ($\mathcal{G}_{\mathrm{obs}}$):** Verify every claim using an independent clean-room oracle sharing zero helper code with the author's implementation:
   - `exact` claims: pure `int` / `Fraction` / exact algebraic fields / `SymPy` / kernel-checked Lean 4 (never float tolerances or unverified solver flags).
   - `sampled` claims: logged seeds, sample-disjoint holdouts, matched adversarial nulls (IAAFT, twin uncoupled systems, shuffled/decoy controls), unseen-seed replay, and pre-adaptation latch reporting.
   - `anchor` claims: live execution of untouched upstream reference code.
   - R1–R7 & R4 parity: zero bare `assert`s on validation paths; bit-identical results across `python3 -I -B`, `python3 -I -O -B`, and `python3 -I -B -W error`; R6: the gate owner pins the check list and thresholds before any submission; R7: every compared value is recomputed from the bytes, never taken from a submitter-declared field (`spec/LAWS_AND_GATES.md` §4).
4. **Honest Novelty & Scope Accounting (`N0`/`N1`/`N2`):** Default every finding to `N0` until checked against full-text prior art and live peer PRs. Log every `VERIFIED`, `PARTIAL/FRAGILE`, and `FALSIFIED` audit permanently in `verification/AUDIT_LOG.md`. Never inflate Draft PRs to merged or `uncompiled_source` to machine-checked.
5. **Exact-Operator Cross-Pollination:** Zero language smuggling. Cross-domain bridges require explicit typed objects, executable maps/identities, quantitative closure defects, or provable obstructions—and obstructions are elevated into theorems or branch triggers.

## Single-Agent Execution Loop (Codex)

Run four strictly separated phases per research cycle:
1. **Portal Phase:** Write 3–5 steelmanned exact hypotheses into `cartography/frontier_portals.md`.
2. **Probe Phase:** Build a deterministic, zero-bare-assert script in `probes/` against the *real* upstream equations/data (zero proxy substitution).
3. **Tomography Phase:** Write a clean-room script in `verification/checks/check_NNN_*.py` with zero shared imports, test R1–R7 + edge cases + nulls + full-text prior art, and log the verdict in `verification/AUDIT_LOG.md`.
4. **Resonance Phase:** Re-enter raw portals with every anomaly, counterexample, or sharpness wall before moving on.

## CLI & Publishing Gates

```bash
python3 -m aletheia audit-check .
python3 -m aletheia diagnose .
python3 -m aletheia mutate path/to/verifier.py --test-cmd "python3 -I -O -B path/to/test.py"
```

Publish cross-repo work strictly on feature branches as **Draft PRs** (never merge to default branches), with zero CRLF, zero personal paths, zero secrets, and zero `__pycache__`.
