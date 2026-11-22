# Proposal: test a pattern on its own terms first

**Status:** **Adopted in Aletheia v2.0.0** (promoted into [`spec/LAWS_AND_GATES.md`](../LAWS_AND_GATES.md) with executable gates in `aletheia/gates_v2.py` covering `OTF-TIGHT-01..04` from `AUDIT-084R`, paired with Law 2b Transformational Steelman from `AUDIT-088R`). **Provenance timeline:** (1) the three direction points below were originally given on **2026-11-21** and explicitly confirmed by the project owner on **2026-11-22** (recorded in PR `#9` commit `d43cb1c7`, at which point the proposed rule itself was not yet adopted); (2) subsequently on **2026-11-22**, the project owner explicitly authorized full `v2.0.0` adoption of this rule into canonical Aletheia under autonomous stewardship.

## Context

The project's working hypothesis is stated in the continuum essay ([continuum PR #1](https://github.com/Foundation-0/continuum/pull/1), `continuum.md`, lines 2 to 3). Our knowledge is limited by the habit of sorting reality into classes and fixed structures. Reality is a continuum, so a fixed structure will always miss part of it.

Direction given to the team on 2026-11-21, confirmed by the project owner on 2026-11-22 (PR `#9`, `d43cb1c7`):

1. The existing approach to mathematics, down to its number systems and notation, is assumed to be flawed in a way that keeps us from capturing reality.
2. The team may derive its own symbols and mathematical systems where that is what it takes to represent the patterns it finds.
3. Patterns are to be looked for by observing raw sensor data from high quality sources such as NASA, without leaning on existing theorems or accepted knowledge.

## What the v1 method lacked

Law 4 and Gate 9 (`spec/LAWS_AND_GATES.md`) count a result as known until prior work has been read in full. Law 5 and Gate 5 accept a cross-field claim only with typed objects and a map that runs. Both judge a claim against existing knowledge. Apart from the null tests in Gate 3, v1 had no formal rule to score a pattern that has no existing theory to compare against.

## Adopted Rule (`v2.0.0`): Own-Terms-First + Formal Tightenings (`OTF-TIGHT-01..05`)

1. **Two phases, kept apart (`OTF-TIGHT-05`).** Phase 1 tests a pattern on its own terms: rerun from the raw source, test on held-out data the finder never saw, and test on a second instrument. Phase 2 compares it with existing mathematics, later and separately. `"Already known"` and `"does not translate"` are Phase 2 outputs; neither overrides Phase 1 reproducibility.
2. **New symbols are judged by operational utility (`OTF-TIGHT-04`, code: `certify_own_terms_symbol_utility`).** Can another party, given only the symbol's rules and raw data, reproduce the same pattern and make accurate predictions on unseen data? Classify every proposed symbol honestly across 5 operational tiers (`OPERATIONAL_NEW_PRIMITIVE`, `TYPED_ENGINEERING_OPERATOR`, `COMPOSITION_SHORTHAND_RENAMING`, `OVERLOADED_RENAMING`, `NON_REPRODUCIBLE_SYMBOL`). A glyph that merely renames a standard construct and adds no new executable rule is recorded transparently as a renaming (as confirmed in `AUDIT-084R` for `7/8` of the v1.3 glyphs).
3. **Net-invariance with pre-pinned R6 nets & Bonferroni FWER (`OTF-TIGHT-01`, code: `certify_own_terms_phase1`).** What is real is *"the invariant that survives every change of net."* A signature counts only if it survives `>= 2` pre-pinned nets spanning `>= 2` distinct axes (`rate`, `quantization`, `scale`, `window`, `instrument`) with `held_out_verified=True`, `second_instrument_verified=True`, non-vacuous error budgets (`per_net_alpha <= 1/10`, `max_fwer <= 1/4`, `observed_p_value <= per_net_alpha`, $\sum_j \alpha_j \le \alpha_{\mathrm{FWER}}$) — never single-net or post-hoc net shopping.
4. **Stratified Tier-4A & Tier-4B nulls (`OTF-TIGHT-03`, code: `certify_own_terms_phase1`).** Two checks stay mandatory because they require no prior theorem: scrambled data (Tier-4A IID permutation null) **and** spectrum-preserving red-noise surrogates (Tier-4B phase/IAAFT null) must not show the pattern, with magnitude-safe margin $\text{obs} - |\text{null}| \ge m_{\min}$ on data the finder never inspected.
5. **Negative controls & signal-over-control dominance (`Rule 5`, code: `certify_own_terms_phase1`).** A signature that appears everywhere is not a finding. Include controls where it must be absent, enforcing both $|\text{ctrl}| \le c_{\max}$ and $\text{obs} - |\text{ctrl}| \ge m_{\min}$ across every net.
6. **No-definition return-to-author (`Rule 6`, code: `certify_own_terms_phase1`).** Where a claim gives nothing measurable, hand it back to its authors (`RETURN_TO_AUTHOR_FOR_DEFINITION`) without inventing a proxy definition to knock down — while still rejecting malformed/float payloads fail-closed.
7. **Orthogonal model-ladder remainder test (`OTF-TIGHT-02`, code: `certify_own_terms_model_ladder`).** Testing whether a structured remainder exceeds a discrete model requires projecting both training and unseen series orthogonally onto $\mathcal{M}_k^\perp$ across a nested model ladder $\mathcal{M}_1 \subset \mathcal{M}_2 \subset \dots$, separating genuine structured continuum remainders from finite model misspecification.

Executable gates live in `aletheia.gates_v2` (`certify_own_terms_phase1`, `certify_own_terms_model_ladder`, `certify_own_terms_symbol_utility`; verified via `aletheia gate-v2 --self-test`). `OTF-TIGHT-05` (organizational Phase-1 before Phase-2 scheduling) is a workflow-discipline requirement recorded in [`spec/LAWS_AND_GATES.md`](../LAWS_AND_GATES.md).
