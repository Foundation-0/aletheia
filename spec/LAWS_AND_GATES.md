# Aletheia Canonical Specification: Laws, Gates, Contracts, Oracles & Anti-Patterns

**Specification Version:** `aletheia.spec.v2.0`  
**Lineage:** Adapts the five gate relations and parts of the oracle-class and latch contracts of `siliconcordat/loom` (`docs/09-gate-contracts.md @ b6d96ea`, `aletheia#3`), formalizes the Cave Expedition anti-shadow protocol (`verification/PROTOCOL.md`, v2), Wave 2 Symbiosis Rounds 1–10 (`AUDIT-023`–`AUDIT-088R`), the outside two-pass review & CLI audit (`aletheia#1`–`#9`), `OWN_TERMS_FIRST` (direction confirmed 2026-11-22 in `d43cb1c7`, `AUDIT-084R`), **Law 2b Transformational Steelman** (`AUDIT-088R`), and deterministic safety-surface scanning (`CYA-GAP-01..06`, `AUDIT-078R`), enforced programmatically by the `aletheia` v2.0.0 CLI (`audit-check`, `mutate`, `diagnose`, `gate-v2`, `safety-scan`, `ratchet`, `mde`, `calculus`).

---

## 1. The Operational Laws (Laws 1–5 + Law 2b + Own-Terms-First)

| Law | Name | Mandatory Operational Requirement |
|---|---|---|
| **Law 1** | **Active Portal-Keeper Loop** | Never park the cartographer / literature navigator after an initial index. Keep a dedicated Portal Keeper active throughout the run to re-enter raw sources whenever any probe uncovers an anomaly, coincidence, divergence, or sharpness wall. |
| **Law 2** | **Steelman-Before-Falsify** | Separate prototype/implementation defects from the underlying scientific or mathematical truth. Diagnose and log every bug explicitly, then construct and test the strongest mathematically intact formulation sitting beside the flawed draft before declaring a frontier closed. |
| **Law 2b** | **Transformational Steelman (`AUDIT-088R`)** | Before closing a theorem or formula as `FALSIFIED`, search across seven admissible global morphism families harmonized with `AUDIT-088R` (`T1_GAUGE_SIMILARITY`, `T2_AFFINE_BREGMAN`, `T3_METRIC_CHART`, `T4_SPECTRAL_PSD_SHIFT`, `T5_SEMIRING_TROPICAL`, `T6_SUBSPACE_PROJECTION`, `T7_ORDER_DOMAIN_RESIDUAL`), gated by four Law-3 anti-epicycle guards (`G0` literal claim must actually fail, `G1` non-vacuity, full target pass on rescues, & uniform null resolution `null_total * max_null_rate >= 1` for `max_null_rate > 0` and explicit minimum `null_total >= 10` when `max_null_rate == 0` enforced on BOTH rescues and `INVARIANT_FALSIFIED`, `G2` global pre-holdout scope with `transform_dof < held_out_constraints`, `G3` explicit scope-delta ledger forbidding silent relabelling, `residual_gap == 0` & `max_residual_gap == 0` on `TRANSFORMED_EXACT`, and `0 < residual_gap <= max_residual_gap` on `BOUNDED_TRANSFORM_CORE`, `G4` exhaustive `7/7` search + transform-invariant surviving obstruction across all searched families + failing target + dual anti-contradiction checks for `INVARIANT_FALSIFIED`; unsearched `FALSIFIED_RAW` is unconditionally rejected). Implemented in `aletheia.gates_v2.certify_transformational_steelman` (which certifies caller-supplied record well-formedness and inequalities; underlying execution provenance requires separate clean-room replay / R6–R7 byte verification). |
| **Law 3** | **Active Multi-Basis Observer Tomography ($\mathcal{G}_{\mathrm{obs}}$)** | Subject every candidate result to independent, zero-shared-code verification across distinct mathematical bases, precisions, null models, and `R1`–`R7` gate-integrity checks. When catching a defect, supply a minimal reproducible counterexample and (where core structure holds) the exact boundary condition or hypothesis tightening required to upgrade cleanly. |
| **Law 4** | **Honest `N0`/`N1`/`N2` & Mechanism-First Prior Art** | Default every result to `N0` until full-text comparison—including mechanism-first searches across at least two neighbouring fields (`aletheia#2`)—establishes the exact delta. State oracle class (`exact`/`sampled`/`anchor`/`reference_replay`) and scope boundaries explicitly. |
| **Law 5** | **Exact-Operator Cross-Pollination (Zero Language Smuggling)** | Reject cross-domain claims based on shared vocabulary alone. Require typed objects in both domains, an explicit map/intertwiner/reduction, an exact identity or quantitative closure defect beating matched nulls, and non-trivial predictive transfer. |

### 1.1 Own-Terms-First Rule (`aletheia#9`, Direction Confirmed 2026-11-22 in `d43cb1c7`, Adopted in `v2.0.0`, `AUDIT-084R`)
When probing raw sensor or primary data without leaning on existing theorems (`spec/proposals/OWN_TERMS_FIRST.md`):
1. **Separate Phase 1 and Phase 2 (`OTF-TIGHT-05` — workflow/process discipline, prose):** Phase 1 tests a pattern on its own terms (raw rerun, held-out unseen data, second instrument); Phase 2 compares with existing mathematics separately afterward.
2. **Pre-Pinned Multi-Axis Net-Invariance & Non-Vacuous Bonferroni FWER (`OTF-TIGHT-01` — code: `aletheia.gates_v2.certify_own_terms_phase1`):** Require `>= 2` pre-pinned nets spanning `>= 2` distinct axes (`rate`, `quantization`, `scale`, `window`, `instrument`), explicit `held_out_verified=True` and `second_instrument_verified=True`, non-vacuous ceilings (`per_net_alpha <= 1/10`, `max_fwer <= 1/4`, $\sum_j \alpha_j \le \alpha_{\mathrm{FWER}}$), and per-net `observed_p_value <= per_net_alpha`.
3. **Stratified Nulls & Signal-over-Control Dominance (`OTF-TIGHT-03` & Rule 5 — code: `aletheia.gates_v2.certify_own_terms_phase1`):** Clear both Tier-4A (IID permutation) and Tier-4B (spectrum-preserving) nulls with magnitude-safe margins ($\text{obs} - |\text{null}| \ge m_{\min}$) and dominate negative controls ($|\text{ctrl}| \le c_{\max}$ and $\text{obs} - |\text{ctrl}| \ge m_{\min}$).
4. **Operational Utility of New Symbols (`OTF-TIGHT-04` & Rule 2 — code: `aletheia.gates_v2.certify_own_terms_symbol_utility`):** Judge coined symbols strictly by independent reproducibility and unseen predictive power across 5 explicit operational tiers; classify renamings honestly.
5. **No-Definition Return-to-Author (Rule 6 — code: `certify_own_terms_phase1`) & Orthogonal Model Ladder (`OTF-TIGHT-02` — code: `aletheia.gates_v2.certify_own_terms_model_ladder`):** Return unmeasurable claims to their author (`RETURN_TO_AUTHOR_FOR_DEFINITION`) while validating float-free & container types fail-closed; separate structured continuum remainders from finite model misspecification via exact pure-$\mathbb{Q}$ orthogonal projection onto $\mathcal{M}_k^\perp$ across nested model ladders.

> **Declared-Record Scope Boundary (Law 2b & Own-Terms-First Pure-$\mathbb{Q}$ Gates):** `certify_transformational_steelman`, `certify_own_terms_phase1`, `certify_own_terms_model_ladder`, and `certify_own_terms_symbol_utility` certify that a caller-supplied record is well-formed and satisfies the stated mathematical inequalities. They do **not** establish from the caller-supplied dicts/arguments alone that the underlying measurements, null suites, held-out splits, or second-instrument runs were actually executed, nor that distinct labels denote physically distinct nets or series. Execution provenance must be established separately through clean-room replay, R6/R7 byte-recomputed artifacts, and empirical claim-ledger verification.

---

## 2. Verdict, Oracle-Class, Feedback, Provenance & Novelty Taxonomies

### 2.1 Verdicts
- **`VERIFIED`**: Passed all applicable Gates 1–10 with clean-room replay, appropriate exact/certified or null-calibrated checks, passing `R1`–`R7` gate integrity, and no counterexample under adversarial search. Valid strictly within stated hypotheses and scope.
- **`PARTIAL/FRAGILE`**: Core structure reproduces, but fails one or more robustness, invariance, precision, `R1`–`R7`, latch, or scope gates. Must be patched and re-audited (logged as `AUDIT-XXXR`) before relying on it.
- **`FALSIFIED`** (`INVARIANT_FALSIFIED` under Law 2b): Concrete transform-invariant counterexample or obstruction proved across admissible morphism families, detector fires on negative controls, gate fatally fails `R1`–`R7`, or fails clean-room replay.
- **`NOT_SHOWN`**: Tested inputs passed without counterexample, **or** a gate-integrity check sampled only $k < n$ sites with `0` hits (`aletheia#3` §4: report `"k of n run"`, never `PASS`).
- **`EXPOSED`** *(modifier for R4 failures)*: Bare `assert` statements guard an accepting trust path and disappear under `python3 -O`.

### 2.2 Oracle Classes & Feedback Channels (`aletheia#3` §§5–7)

| Oracle Class | Required Evidence Basis | Disallowed Confusion | Permitted Feedback Channel |
|---|---|---|---|
| **`exact`** | Formal proof, symbolic identity, per-input certificate, or exhaustive finite enumeration. | **Exact arithmetic $\ne$ exact oracle:** finite random samples decided in exact $\mathbb{Q}$ are still `sampled`, NEVER `exact`. | Full counterexample + structural repair guidance (`full_counterexample_and_repair`). |
| **`sampled`** | Finite statistical, randomized, multi-seed, or numerical-grid check (including random exact-$\mathbb{Q}$ draws). | Never claim universal truth or `PASS` on truncated gate-integrity coverage. | Budgeted family-only verdict + fresh post-repair nulls/seeds (`family_only_with_fresh_post_repair_seed`). |
| **`anchor`** | External domain data testing the specification itself; failure indicts the specification. | Never conflate with `reference_replay`; never tune or feed back to proposers. | **None to proposer**; routed strictly to specification owner (`none_to_proposer_spec_owner_only`). |
| **`reference_replay`** | Live agreement with an untouched upstream implementation/simulator. | Never treat upstream code bugs as ground truth about external nature (`anchor`). | Diff against untouched upstream implementation (`diff_against_upstream_reference`). |

### 2.3 Provenance Tags & Novelty Bar (`N0` Default)
- **Provenance:** `verified` | `source_claim` | `hypothesis` | `uncompiled_source`.
- **Novelty:** `N0` (Known / Repackaging — default until full-text & mechanism-first prior-art audit proves otherwise) | `N1` (Concrete local advance, repair, counterexample, or rigorous empirical falsification) | `N2` (Genuine new theorem, sharp new invariant, exact obstruction theorem, or non-trivial cross-domain operator transfer surviving full-text mechanism-first prior-art audit and Gates 1–10).

---

## 3. The Ten Verification Gates

1. **Gate 1 — Exact Reproducibility & Clean-Room Replay:** Explicit logged RNG seeds; clean execution from scratch against pinned commit SHAs (never trusting stored pass results after upstream edits).
2. **Gate 2 — Coordinate, Gauge, Basis, Metric & Discretization Invariance:** Invariants remain fixed under similarity transforms, permutations, sign/phase flips, unit rescaling, likelihood-metric swaps, and mesh refinement.
3. **Gate 3 — Negative Controls, Null Models & Adversarial Edge Cases:** Clear pre-declared margins against matched adversarial nulls (permuted, spectrum-preserving/IAAFT, twin uncoupled oscillators, degenerate boundaries) with explicit falsification criteria.
4. **Gate 4 — Exact Arithmetic, Symbolic & Interval-Certified Checks:** Decide algebraic, combinatorial, bound, LP/SDP, and cohomology claims in exact integer/rational/algebraic-field arithmetic (`int`, `Fraction`, $\mathbb{Q}(i)$, $\mathbb{Z}[\sqrt{2}]$, `isqrt`, exact `SymPy`) or directed intervals—never float epsilon cutoffs.
5. **Gate 5 — Anti-Language-Smuggling & Cross-Domain Bridge Audit:** Require typed objects, explicit runnable/exact map $\Phi$, exact commuting identity or quantitative closure defect beating nulls, and non-trivial predictive transfer.
6. **Gate 6 — Anti-Circularity, Non-Vacuity & Fresh-Seed Out-of-Sample Check:** Confirm conclusions are not hard-coded; verify bounds strictly beat trivial baselines; re-test on unseen draws without re-tuning.
7. **Gate 7 — Gate Integrity, Optimizer Parity & Mutation Isolation (`R1`–`R7`):** Every verifier, certificate checker, or automated gate must satisfy Contracts **R1–R7** (§4 below).
8. **Gate 8 — Pre-Adaptation Subspace Latch & Hashed Preregistration (`aletheia#3` §8):** For adaptive fits $r(\theta)\approx r_0 - \Phi\theta$, record misspecification diagnostics *before* adaptation. A post-fit audit reads only its orthogonal component outside $\operatorname{col}(\Phi)$ ($\sin^2\theta$ attenuation); an audit wholly inside $\operatorname{col}(\Phi)$ ($\sin^2\theta = 0$) halts with **`BLIND_AUDIT_IN_COL_PHI`** (`aletheia.gates_v2.certify_gate8_subspace_latch`). At most $m - \operatorname{rank}(\Phi)$ independent audits survive adaptation; compare total post-fit residual against $(m - \operatorname{rank}(\Phi)) s^2$. Commit/hash preregistrations *before* reading code or data, score hit/partial/miss via a second reader, retain all misses permanently, and report unexpected non-preregistered effects separately as new leads.
9. **Gate 9 — Mechanism-First Prior Art (`aletheia#2`):** Before assigning `N1` or `N2`, restate the result's central object and mechanism in plain mathematical terms and in the vocabulary of at least **two neighbouring fields** that use the same mechanism. Search full texts under each restatement and record restatements tried, fields searched, and texts read. A match on mechanism sets the label regardless of terminology.
10. **Gate 10 — Second-Pass Advocate for Narrowing Findings (`aletheia#2`):** Every `FALSIFIED` or `PARTIAL/FRAGILE` verdict, and every finding that lowers a novelty label or narrows a claim, receives a second independent verifier (`prompts/advocate.md`) briefed to rebuild evidence from scratch, read cited prior work in full, test Law 2b transformations, and record a ruling (`stands`, `stands_narrowed`, or `falls`) alongside the strongest surviving claim. Before publishing any label above `N0`, solicit an independent outside observer (`prompts/outside-observer.md`) where feasible.

---

## 4. The Seven Gate-Integrity Contracts (`R1`–`R7`, `aletheia#3`)

Principle: *"A gate's verdict must never be movable by how the submission is written, nor by submitter-declared values standing in for byte-recomputed measurements."*

**R1–R5 are necessary, not sufficient.** A gate can keep all five and still accept a false claim when submitter-written fields choose the check rules or stand in for measurements (`Record B`, `aletheia#3` §1). **R6 and R7** close that gap.

| Contract | Requirement | Concrete Enforcement |
|---|---|---|
| **R1 — Default Reject** | Empty, blank, null, missing-field, or unknown-status inputs MUST fail closed. | Explicit schema/key validation returning rejection or raising a dedicated exception. |
| **R2 — Omission Monotonicity** | Deleting required evidence or witness fields MUST NEVER turn `reject` into `accept`. | Test suites explicitly drop every required witness field and confirm rejection. |
| **R3 — Two-Direction Canonical Encoding & Type Strictness** | **(i)** Accepted input with a checked value re-spelled $\to$ rejected. **(ii) Costly direction:** Rejected input MUST stay rejected when any correctly typed value is re-spelled (`0`, `"false"`, `1` for `true`, trailing `\n` via `\Z`/`(?!\n)$`, duplicate JSON keys, floats). | Enforced via `aletheia.gates_v2.certify_two_direction_r3` (strict typed non-noop equality & unique case-insensitive labels). |
| **R4 — Optimizer, Skip & Cross-Language Mode Parity** | Covers every deployment mode: all three isolated Python modes (`python3 -I -B`, `python3 -I -O -B`, `python3 -I -B -W error`, zero bare `assert`s, zero `-O` test skips) and compiled release profiles (e.g. Rust release dropping `debug_assert!`/overflow checks). **Write-path check:** `python3 -O verify.py --write` must never emit a certificate that a plain run rejects. | Enforced by `aletheia audit-check` (exit code, stdout SHA-256, and `unittest` skip-count parity across all 3 modes). |
| **R5 — Refusal-Site Mutation Isolation** | Every named guard/check has a must-fail control killing single-site deletion/boundary mutations. Sampling $k < n$ sites with `0` survivors yields **`NOT_SHOWN`**, NEVER `PASS`. | Enforced by `aletheia mutate` (local + cross-module imported wrappers, `--guards`, string/tuple/multi-stmt shapes, self-check mode, `NOT_SHOWN` on truncation). |
| **R6 — Pinned Checks (`aletheia#3` §1)** | Check list, ranges, and thresholds are fixed by the gate owner before submission exists; no submitter-written field may select or override them. | Enforced by `aletheia.gates_v2.evaluate_r6_r7_gate` (`R6_SUBMITTER_RULE_OVERRIDE` fail-closed). |
| **R7 — Measured, Not Declared (`aletheia#3` §1)** | Every value compared against a pinned rule is recomputed by the gate from the bytes about to be promoted. Declared digests/statuses/counts/flags may be checked *against* measurements but never stand in for them. | Enforced by `aletheia.gates_v2.evaluate_r6_r7_gate` (raw-byte SHA-256, alpha, and exact rational norm recomputation). |

---

## 5. The Fourteen Cave-Shadow Anti-Patterns (`CS-01` – `CS-14`)

Automated heuristics for `CS-01`–`CS-12` run in `aletheia diagnose`; `CS-13` and `CS-14` are enforced by Gates 9–10 and `prompts/advocate.md`:

| # | Anti-Pattern | Observable Symptom | Structural Remedy |
|---|---|---|---|
| **1** | **Static-Map Trap (`CS-01`)** | Portal Keeper parks `[done]` in Round 1 and never re-enters raw sources. | Keep Portal Keeper active; re-enter sources on every anomaly or wall. |
| **2** | **Premature Dismissal Bias (`CS-02`)** | `FALSIFIED`/`N0` verdicts without steelmanned repairs or Law 2b morphism search. | Invoke Laws 2 & 2b before closing any thread. |
| **3** | **Language Smuggling (`CS-03`)** | Cross-domain prose claims with no typed intertwining map or defect metric. | Enforce Gate 5: typed objects, operator identity, quantitative transfer. |
| **4** | **Substitution Shadow (`CS-04`)** | Certifying a synthetic proxy matrix/dataset instead of the real upstream target. | Execute directly against actual target equations, data, or live upstream code. |
| **5** | **Glass Gate (`CS-05`)** | Bare `assert`s, float cutoffs in exact checks, unseeded RNGs, or `0` must-fail controls. | Enforce `R1`–`R7` (`aletheia audit-check`, `aletheia mutate`, `aletheia gate-v2`). |
| **6** | **Local-Optimum Closure (`CS-06`)** | Stopping at a sharpness wall instead of elevating it to a theorem or branch. | Convert obstructions to theorems or spawn a branch adding the missing invariant. |
| **7** | **Provenance Inflation (`CS-07`)** | Claiming merged, machine-checked, or `N2` without merge, compiler log, or prior art. | Enforce standing tags (`Draft PR`, `uncompiled_source`, default `N0`). |
| **8** | **Compute Leakage (`CS-08`)** | Comparing arms by round count without a fixed compute cap, so an arm triggering long open reasoning gains solves the cap would not allow (`aletheia#4`, `AUDIT-023` lead). | Compare arms under one fixed compute cap and report format-preserving solves separately from long open-reasoning escapes. |
| **9** | **Finite-Sample / Support-Truncation Mirage (`CS-09`)** | Claiming an asymptotic equilibrium from truncated trajectories without checking tail-mass extinction (`AUDIT-032`). | Test exact finite-$M$ / support-truncation cutoffs before asserting asymptotic laws. |
| **10** | **Sparse-Collision Denominator Collapse (`CS-10`)** | Aggregating sparse updates or filtered evals by collision count $c_j$ instead of fixed global $W$ (`AUDIT-039`, `037`). | Normalize sparse/filtered aggregates over fixed global denominator $W$ (`sum/W`). |
| **11** | **Unit-Gauge / Radix Fragility (`CS-11`)** | Unscaled raw-unit regularization or base-10/float64 math grading (`AUDIT-039`, `036`). | Gauge-normalize features before regularization and grade exact math over $\mathbb{Q}$. |
| **12** | **Trust-Boundary Shadow (`CS-12`)** | Unseen refusal wrappers, `$` digest regexes matching `\n`, loose `json.loads`, unbound escape hatches, writable ancestors, or unpinned MCP/CI/shell hazards (`AUDIT-061R`–`065`, `AUDIT-078R`). | Use `\A...\Z`/`(?!\n)$`, `loads_strict_json`, `--strict-ancestors`, `--safety-scan` (`CYA-GAP-01..06`), and full R5 mutation isolation. |
| **13** | **Citation-Trail Search (`CS-13`, `aletheia#2`)** | Prior-art search checks only papers the source cites or only the source's own words. | Restate the mechanism in at least two neighbouring fields' terms before any label above `N0`. |
| **14** | **One-Sided Verifier (`CS-14`, `aletheia#2`)** | Negative findings and novelty downgrades are accepted on a single verifier pass. | Assign an Advocate (`prompts/advocate.md`) to rebuild and rule (`stands`/`stands_narrowed`/`falls`) before acting. |

---

## 6. v1.1–v2.0 Executable Modules & Epistemic Accounting

1. **Pure-$\mathbb{Q}$ v2.0 Gate-Contract Engine (`aletheia gate-v2 --self-test`, `aletheia/gates_v2.py`):** Executable pure-$\mathbb{Q}$ certifiers for `R6`/`R7` (registered check IDs verified against executed checks), Two-Direction `R3`, §4 `NOT_SHOWN`, §§5–7 oracle/feedback rules, §8 Gate-8 subspace latch (`BLIND_AUDIT_IN_COL_PHI`), Law 2b Transformational Steelman (schema/inequality gate aligned with `AUDIT-088R` `T1`–`T7` IDs & `G0`–`G4` guards), and Own-Terms-First (`certify_own_terms_phase1`, `certify_own_terms_model_ladder`, `certify_own_terms_symbol_utility` — schema/inequality gates over caller-supplied records; execution provenance requires separate replay). `gate-v2 --self-test` dynamically verifies one accept and one rejection control per gate.
2. **Deterministic Agent Safety-Surface Scanner (`aletheia safety-scan` & `aletheia audit-check --safety-scan`, `aletheia/safety.py`):** Implements `CYA-GAP-01..06` (`AUDIT-078R`): hidden Trojan-Source Unicode (`U+00AD`, `U+200B..200F`, `U+2060..2064`, `U+FEFF`, BiDi controls, variation selectors `U+FE00..FE0F`/`U+E0100..E01EF`, Tags), unpinned MCP/`npx -y` (shell + JSON/YAML)/`--yolo`/`SessionStart`, unguarded recursive force-delete of shell/Makefile variables (YAML `run:`, `$(...)`, continuations, `xargs`, `sh -c`, Makefile `$(VAR)`; top-level non-conditional/non-heredoc `set -u` guards unset only, `${VAR:?}` guards unset and empty), `pull_request_target` + secrets/`secrets: inherit`/write/untrusted PR head checkout (dot/bracket exprs, step outputs, `pull/N/head`, `gh pr checkout`), prose-only rules & `~/` host paths (incl. `.cursorrules`), UTF-16 decoding, dotfiles/extensionless/vendor-dir scanning, fail-closed reporting of `skipped_files` (incl. non-regular files such as FIFOs/sockets/devices without blocking), `undecodable_files` (incl. binary/NUL-containing text such as UTF-32 with BOM), and `unreadable_files`, plus optional `--include-host-hygiene`.
3. **8-Glyph Exact Operator Calculus (`aletheia calculus`, v1.3, Honest Rule-2 Accounting per `AUDIT-084R`):**
   - Executable pure-$\mathbb{Q}/\mathbb{Z}$ notation (reported `0 / 227,540` Lean 4 corpus hits; the scan script and corpus are not in this repository): `⧄` (`|/|`), `⧅` (`|\|`), `⦷` (`(||)`), `⟠` (`<=>`), `⧇` (`[o]`), `⦺` (`(+-0)`), `⩩` (`=#=`), `⫩` (`_|T`).
   - **Honest Operational-Utility Classification (`AUDIT-084R`):** Under Own-Terms-First Rule 2, `7/8` glyphs are documented transparently as composition shorthands / renamings (`6` shorthands + overloaded `⟠`) operating on constructed exact-$\mathbb{Q}$ objects (`0` file I/O in `calculus.py`), while `1/8` (`⫩`, mutation-tested refusal gate) is a typed execution operator (`N0` mutation-testing origin); all `6` algebraic composition probes (`C1`–`C6`) execute cleanly with zero floats.
4. **Plane-1 MDE (`aletheia mde`), 5-Gate Ratchet (`aletheia ratchet`), & Hardened `audit-check` / `mutate`:** Includes Lean 4 raw-string `r#"..."#` safe lexing, R4 `unittest` `-O` skip detection, `from random import` AST tracking, cross-module imported wrapper discovery + `--guards` + `covered_lines`, `shapes.py`/`rule.py` refusal shapes, `selfcheck.py` constant-shift mutation, `NOT_SHOWN` truncation, and `(?!\n)$` schema alignment.

---

## 7. Machine-Readable Schemas

Formal JSON Schemas (`draft/2020-12`, aligned with CLI validators and `(?!\n)$` newline-safe anchors) reside in [`../schemas/`](../schemas/):
- [`schemas/audit_receipt.v1.schema.json`](../schemas/audit_receipt.v1.schema.json)
- [`schemas/frontier_portal.v1.schema.json`](../schemas/frontier_portal.v1.schema.json)
- [`schemas/compute_handoff.v1.schema.json`](../schemas/compute_handoff.v1.schema.json)
