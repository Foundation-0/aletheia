# Proposal: test a pattern on its own terms first *(Promoted to Canonical `v2.0.0` Spec)*

**Status:** **ADOPTED (`v2.0.0`, 2026-11-21).** Originally proposed by an outside checker (`Foundation-0/aletheia#9`, commit `ffa0ed42`). On **2026-11-21**, the project owner explicitly confirmed all three direction statements below and authorized promotion into the canonical specification ([`spec/LAWS_AND_GATES.md`](../LAWS_AND_GATES.md)), integrated with the five formal tightenings from `AUDIT-084R` (`OTF-TIGHT-01..05`) and paired with **Law 2b (Transformational Steelman)** (`AUDIT-088R`).

## Context

The project's working hypothesis is stated in the continuum essay ([continuum PR #1](https://github.com/Foundation-0/continuum/pull/1), `continuum.md`, lines 2 to 3). Our knowledge is limited by the habit of sorting reality into classes and fixed structures. Reality is a continuum, so a fixed structure will always miss part of it.

Direction given to the team on 2026-11-21 (**confirmed explicitly by the project owner on 2026-11-21**):

1. The existing approach to mathematics, down to its number systems and notation, is assumed to be flawed in a way that keeps us from capturing reality.
2. The team may derive its own symbols and mathematical systems where that is what it takes to represent the patterns it finds.
3. Patterns are to be looked for by observing raw sensor data from high quality sources such as NASA, without leaning on existing theorems or accepted knowledge.

## What the v1 method lacked

Law 4 and Gate 9 (`spec/LAWS_AND_GATES.md`) count a result as known until prior work has been read in full. Law 5 and Gate 5 accept a cross-field claim only with typed objects and a map that runs. Both judge a claim against existing knowledge. Apart from the null tests in Gate 3, v1 had no formal rule to score a pattern that has no existing theory to compare against.

## Adopted Rule (`v2.0.0`): Own-Terms-First + Formal Tightenings (`OTF-TIGHT-01..05`)

1. **Two phases, kept apart (`OTF-TIGHT-05`).** Phase 1 tests a pattern on its own terms: rerun from the raw source, test on held-out data the finder never saw, and test on a second instrument. Phase 2 compares it with existing mathematics, later and separately. `"Already known"` and `"does not translate"` are Phase 2 outputs; neither overrides Phase 1 reproducibility.
2. **New symbols are judged by operational utility (`OTF-TIGHT-04`).** Can another party, given only the symbol's rules and raw data, reproduce the same pattern and make accurate predictions on unseen data? Classify every proposed symbol honestly across 5 operational tiers (`GENUINE_OPERATIONAL_PRIMITIVE`, `TYPED_EXECUTION_OPERATOR`, `COMPOSITION_SHORTHAND`, `OVERLOADED_RENAMING`, `UNIMPLEMENTED_ALIAS`). A glyph that merely renames a standard construct and adds no new executable rule is recorded transparently as a renaming (as confirmed in `AUDIT-084R` for `7/8` of the v1.3 glyphs).
3. **Net-invariance with pre-pinned R6 nets & Bonferroni FWER (`OTF-TIGHT-01`).** What is real is *"the invariant that survives every change of net."* A signature counts only if it survives pre-pinned changes of sampling rate, quantization, amplitude scale, window, and instrument under dependence-free Bonferroni FWER budgeting ($\sum_j \alpha_j \le \alpha_{\mathrm{FWER}}$) — never post-hoc net shopping.
4. **Stratified Tier-4A & Tier-4B nulls (`OTF-TIGHT-03`).** Two checks stay mandatory because they require no prior theorem: scrambled data (Tier-4A IID permutation null) **and** spectrum-preserving red-noise surrogates (Tier-4B phase/IAAFT null) must not show the pattern, with magnitude-safe margin $\text{obs} - |\text{null}| \ge m_{\min}$ on data the finder never inspected.
5. **Negative controls & signal-over-control dominance (`Rule 5`).** A signature that appears everywhere is not a finding. Include controls where it must be absent, enforcing both $|\text{ctrl}| \le c_{\max}$ and $\text{obs} - |\text{ctrl}| \ge m_{\min}$ across every net.
6. **No-definition return-to-author (`Rule 6`).** Where a claim gives nothing measurable, hand it back to its authors (`RETURN_TO_AUTHOR_FOR_DEFINITION`) without inventing a proxy definition to knock down — while still rejecting malformed/float payloads fail-closed.
7. **Orthogonal model-ladder remainder test (`OTF-TIGHT-02`).** Testing whether a structured remainder exceeds a discrete model requires projecting both training and unseen series orthogonally onto $\mathcal{M}_k^\perp$ across a nested model ladder $\mathcal{M}_1 \subset \mathcal{M}_2 \subset \dots$, separating genuine structured continuum remainders from finite model misspecification.

Implemented programmatically in `aletheia.gates_v2.certify_own_terms_phase1` (`aletheia gate-v2 --self-test`).
