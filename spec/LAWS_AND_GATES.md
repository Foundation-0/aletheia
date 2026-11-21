# Aletheia Canonical Specification: Laws, Gates, Contracts, Oracles & Anti-Patterns

**Specification Version:** `aletheia.spec.v1.4`  
**Lineage:** Formalizes the Cave Expedition anti-shadow protocol (`verification/PROTOCOL.md`, v2), gate-contract architecture (`siliconcordat/loom#8` / `#9`), Wave 2 Symbiosis Rounds 1–3 (`AUDIT-023`–`AUDIT-039`), Wave 2 Round 4 Ramanujan/Hawking & 8-Glyph Operator Calculus (`AUDIT-041`–`AUDIT-054`), and Wave 2 Round 6 `Moissanite-Labs/warp-drive` Trust-Boundary & Spectral Tomography (`AUDIT-061R`–`AUDIT-065`) into a domain-general open specification enforced programmatically by the `aletheia` v1.4 CLI (`audit-check`, `mutate`, `diagnose`, `ratchet`, `mde`, `calculus`).

---

## 1. The Five Operational Laws

| Law | Name | Mandatory Operational Requirement |
|---|---|---|
| **Law 1** | **Active Portal-Keeper Loop** | Never park the cartographer / literature navigator after an initial index. Keep a dedicated Portal Keeper active throughout the run to re-enter raw sources whenever any probe uncovers an anomaly, coincidence, divergence, or sharpness wall. |
| **Law 2** | **Steelman-Before-Falsify** | Separate prototype/implementation defects from the underlying scientific or mathematical truth. Diagnose and log every bug explicitly, then construct and test the strongest mathematically intact formulation sitting beside the flawed draft before declaring a frontier closed. |
| **Law 3** | **Active Multi-Basis Observer Tomography ($\mathcal{G}_{\mathrm{obs}}$)** | Subject every candidate result to independent, zero-shared-code verification across distinct mathematical bases, precisions, null models, and R1–R5 gate-integrity checks. When catching a defect, supply a minimal reproducible counterexample and (where core structure holds) the exact boundary condition or hypothesis tightening required to upgrade cleanly. |
| **Law 4** | **Honest `N0`/`N1`/`N2` & Full-Text Prior-Art Accounting** | Default every result to `N0` until full-text comparison against literature and peer repositories establishes the exact delta. State oracle class (`exact`/`sampled`/`anchor`) and scope boundaries (local vs. global, `uncompiled_source`, Draft PR vs. merged, SNR/ensemble limits) explicitly. |
| **Law 5** | **Exact-Operator Cross-Pollination (Zero Language Smuggling)** | Reject cross-domain claims based on shared vocabulary alone. Require typed objects in both domains, an explicit map/intertwiner/reduction, an exact identity or quantitative closure defect beating matched nulls, and non-trivial predictive transfer. |

---

## 2. Verdict, Oracle-Class, Provenance & Novelty Taxonomies

### 2.1 Verdicts
- **`VERIFIED`**: Passed all applicable Gates 1–9 with clean-room replay, appropriate exact/certified or null-calibrated checks, passing R1–R5 gate integrity, and no counterexample under adversarial search. Valid strictly within stated hypotheses and scope.
- **`PARTIAL/FRAGILE`**: Core structure reproduces, but fails one or more robustness, invariance, precision, R1–R5, latch, or scope gates. Must be patched and re-audited (logged as `AUDIT-XXXR`) before relying on it.
- **`FALSIFIED`**: Concrete counterexample found, exact arithmetic refutes claim, detector fires on negative controls, gate fatally fails R1–R5, alleged bridge fails intertwining/non-triviality, or fails clean-room replay. Retract or steelman into a distinct repaired claim.
- **`NOT_SHOWN`** *(modifier for `sampled` oracles)*: Tested inputs passed without counterexample; universal truth outside tested regimes is explicitly unestablished.
- **`EXPOSED`** *(modifier for R4 failures)*: Bare `assert` statements guard an accepting trust path and disappear under `python3 -O`.

### 2.2 Oracle Classes
- **`exact`**: Acceptance mathematically implies the stated claim universally (algebraic proof kernel, pure integer/`Fraction`/$\mathbb{Q}(i)$/$\mathbb{Z}[\sqrt{2}]$ certificate checker, exact `SymPy` identity, or exhaustive finite enumeration).
- **`sampled`**: Finite statistical, randomized, multi-seed, or numerical-grid check. Provides calibrated evidence strictly on tested regimes; never misrepresent as universal proof.
- **`anchor`**: Independent replay against a held-out external specification, untouched upstream simulator, or out-of-family physical check. Never tune or fit proposers against an anchor.

### 2.3 Provenance Tags
- **`verified`**: Independently re-executed from clean state with exact command, script, digest, and verdict recorded in `AUDIT_LOG.md`.
- **`source_claim`**: Reported in external literature, peer repo, or raw portal; not yet independently re-executed.
- **`hypothesis`**: Proposed law or conjecture with explicit falsification criterion and/or pre-registered test.
- **`uncompiled_source`**: Formal proof source (e.g., Lean 4 / Coq) inspected by hand but not yet verified by the target proof-assistant compiler on the current host.

### 2.4 Novelty Bar (`N0` Default)
- **`N0` (Known / Repackaging):** Standard textbook result, existing literature construction, or already landed in peer repositories. Default score until proven otherwise.
- **`N1` (Concrete Local Advance):** New certified counterexample, hardened TCB repair, sharpened boundary on an open instance, newly certified case of an existing framework, or rigorous empirical falsification of an active claim.
- **`N2` (Genuine New Ground):** New theorem, sharp new invariant, exact obstruction theorem, or non-trivial cross-domain operator transfer surviving full-text prior-art verification and Gates 1–8.

---

## 3. The Nine Verification Gates

1. **Gate 1 — Exact Reproducibility & Clean-Room Replay:** Explicit logged RNG seeds; clean execution from scratch without pre-baked caches producing bit-identical outputs (exact/discrete) or outputs within pre-declared tolerance (continuous/iterative); recorded script paths, commit SHAs, and dependency versions.
2. **Gate 2 — Coordinate, Gauge, Basis, Metric & Discretization Invariance:** Invariants must remain fixed (and covariant objects transform covariantly) under orthogonal/unitary/invertible similarity transforms, index permutations, sign/phase flips, unit rescaling, likelihood-metric swaps, and mesh/step-size refinement ($h \to h/2$).
3. **Gate 3 — Negative Controls, Null Models & Adversarial Edge Cases:** Every detector or empirical score must clear pre-declared margins against matched adversarial nulls (permuted controls, IAAFT surrogates, twin uncoupled oscillators, glitches, random matrices, degenerate $n=1,2,3$ and singular boundary cases) and state an explicit falsification criterion.
4. **Gate 4 — Exact Arithmetic, Symbolic & Interval-Certified Checks:** Algebraic, combinatorial, bound, LP/SDP, and cohomology claims MUST be certified in exact integer/rational/algebraic-field arithmetic (`int`, `Fraction`, $\mathbb{Q}(i)$, $\mathbb{Z}[\sqrt{2}]$, `math.isqrt`, exact `SymPy`) or rigorously directed interval arithmetic—never `1e-12` float cutoffs or unchecked solver `"optimal"` flags. Dynamical/PDE claims must audit conserved quantities and precision convergence.
5. **Gate 5 — Anti-Language-Smuggling & Cross-Domain Bridge Audit:** Every bridge between domains $A$ and $B$ requires (i) explicit typed objects, (ii) an explicit runnable/exact map $\Phi$, (iii) an exact commuting identity or quantitative closure defect beating random nulls, and (iv) non-trivial predictive transfer.
6. **Gate 6 — Anti-Circularity, Non-Vacuity & Fresh-Seed Out-of-Sample Check:** Confirm conclusions are not hard-coded into generators/priors; verify bounds strictly beat trivial baselines (Cauchy–Schwarz, trace/Weyl/Gershgorin, dimension counts); re-test parameter/seed-discovered phenomena on unseen out-of-sample draws without re-tuning.
7. **Gate 7 — Gate Integrity, Optimizer Parity & Check-Deletion Mutation (R1–R5):** Every verifier, certificate checker, or automated gate must satisfy Contracts **R1–R5** (§4 below).
8. **Gate 8 — Pre-Adaptation Latch & Permanent Miss Logging:** For adaptive fits $r(\theta)\approx r_0 - \Phi\theta$, record misspecification diagnostics *before* adaptation (post-fit linear audits vanish on $\operatorname{col}(\Phi)$ and retain only $\sin^2\angle(w,\operatorname{col}(\Phi))$ sensitivity); pre-register predictions where applicable; log all `FALSIFIED` and `PARTIAL/FRAGILE` audits permanently in `AUDIT_LOG.md` (never delete or rewrite misses).
9. **Gate 9 — Strict Novelty & Full-Text Prior-Art Bar:** Explicitly distinguish prior literature / peer repo baselines from the exact novel delta before assigning `N1` or `N2`.

---

## 4. The Five Gate-Integrity Contracts (R1–R5)

Principle: *"A gate's verdict must never be movable by how the submission is written."*

| Contract | Requirement | Concrete Enforcement |
|---|---|---|
| **R1 — Default Reject** | Empty, blank, null, missing-field, or unknown-status inputs MUST fail closed. | Explicit schema/key validation returning rejection or raising a dedicated exception. |
| **R2 — Omission Monotonicity** | Deleting required evidence or witness fields MUST NEVER turn `reject` into `accept`. | Test suites explicitly drop every required witness field and confirm rejection. |
| **R3 — Canonical Encoding & Type Strictness** | Type-check before value-check (`bool` vs `int`, `int` vs `float`, `str` vs number); reject non-canonical strings (`"007"`, `"-0"`, `"2/4"`, `"0/5"`, trailing `\n` via `\Z` not `$`, non-ASCII digits, duplicate JSON keys, raw floats in hashed payloads). | Strict canonical parsers (`parse_strict_fraction`) + explicit negative test vectors. |
| **R4 — Optimizer & Warning Parity** | Every verifier and test suite MUST produce identical exit status and canonical outputs across all three isolated Python modes: `python3 -I -B`, `python3 -I -O -B`, and `python3 -I -B -W error`. | **Zero bare `assert` statements on trust/validation paths** (use explicit `if not cond: raise ValueError(...)`); enforced by `aletheia audit-check`. |
| **R5 — Refusal-Site Mutation Isolation** | Every named guard/check MUST have a minimal must-fail control that trips that specific check. Deleting or inverting any single refusal branch MUST turn the test suite RED. | Enforced programmatically via AST mutation (`aletheia mutate`) targeting 100% mutant kill rate (`0` survivors). |

---

## 5. The Twelve Cave-Shadow Anti-Patterns (`CS-01` – `CS-12`)

Automated heuristics for these twelve failure modes are implemented in `aletheia diagnose`:

| # | Anti-Pattern | Observable Symptom | Structural Remedy |
|---|---|---|---|
| **1** | **Static-Map Trap (`CS-01`)** | Portal Keeper / literature agent posts `[done]` in Round 1 and never re-enters raw sources. | Keep Portal Keeper active; trigger source re-entry on every probe anomaly or wall. |
| **2** | **Premature Dismissal Bias (`CS-02`)** | Multiple `FALSIFIED` / `N0` verdicts with zero repaired/steelmanned formulations tested. | Invoke Law 2: require an explicit steelman statement & exact test before closing a thread. |
| **3** | **Language Smuggling (`CS-03`)** | Cross-domain prose claims (*"both are sheaves/dualities"*) with no typed intertwining map or defect metric. | Enforce Gate 5: require explicit typed objects, operator identity, and quantitative transfer. |
| **4** | **Substitution Shadow (`CS-04`)** | Verifier certifies a simplified synthetic proxy matrix/dataset instead of the real upstream target. | Import and execute against the actual target equations, datasets, or live upstream code. |
| **5** | **Glass Gate (`CS-05`)** | Bare `assert`s on trust paths, `1e-12` float cutoffs for exact claims, unseeded RNGs, or `0` must-fail controls. | Enforce R1–R5 (`aletheia audit-check` + `aletheia mutate` covering dict-verdicts & accumulators). |
| **6** | **Local-Optimum Closure (`CS-06`)** | Stopping when hitting a sharpness wall or impossibility boundary instead of turning it into a theorem or next branch. | Elevate exact obstructions to theorems or spawn a branch supplying the proven missing invariant. |
| **7** | **Provenance Inflation (`CS-07`)** | Claiming "merged", "machine-checked", or `N2` without merge, compiler execution, or full-text prior-art verification. | Enforce strict standing tags (`Draft PR`, `uncompiled_source`, local-vs-global scope, default `N0`). |
| **8** | **Compute-Leakage Simpson's Paradox (`CS-08`)** | Comparing arms by round count without a fixed compute/token survival cap, allowing slow format-breaking CoT escapes to invert the true fixed-budget winner (`AUDIT-023` `N2`). | Enforce fixed wall-clock/token survival caps alongside round counts; report paired fast-channel and escape-channel outcomes separately. |
| **9** | **Finite-Sample / Support-Truncation Mirage (`CS-09`)** | Claiming an infinite-horizon equilibrium or phase-transition law from finite-sample / top-$p$ / truncated trajectories without checking tail-mass extinction (`AUDIT-032` `N2`). | Test exact finite-$M$ / projective support-truncation cutoffs and verify tail survival before asserting asymptotic laws. |
| **10** | **Sparse-Collision Denominator Collapse (`CS-10`)** | Aggregating sparse updates or filtered eval scores by local collision count $c_j$ (e.g. `scatter_reduce_("mean", include_self=False)`) or dropping invalid rows instead of dividing by fixed global $W$ (`AUDIT-039` `N2`, `AUDIT-037`). | Always normalize sparse/filtered aggregates over the fixed global denominator $W$ (`sum/W`) and penalize dropped/invalid rows explicitly. |
| **11** | **Unit-Gauge / Radix Fragility (`CS-11`)** | Regularizing unscaled heterogeneous-unit features (e.g. raw `Ridge(alpha)` breaking under $10^9\times$ unit rescaling) or grading exact math via base-10/IEEE-754 heuristics (`100 == 1`, `10^17+1 == 10^17`, `AUDIT-039` `N2`, `AUDIT-036`). | Enforce Stage-B coordinate-free null-equivalence: gauge-normalize features before regularization and grade exact equivalence over $\mathbb{Q}$, never float64/radix heuristics. |
| **12** | **Trust-Boundary Shadow (`CS-12`)** | Local refusal wrappers (`def _req`) hiding R5 survivors, hex-digest regexes ending in `$` instead of `\Z`, raw `json.loads` accepting duplicate keys / `NaN`, unbound escape hatches, or writable ancestor directories (`AUDIT-061R`–`065`, `v1.4`). | Auto-detect local refusal wrappers in `aletheia mutate`, enforce `\A...\Z` digest regexes, parse JSON/JSONL via `loads_strict_json`/`load_strict_jsonl_file`, bind escape hatches cryptographically to policy bounds, and verify `--strict-ancestors`. |

---

## 6. v1.1–v1.4 Governance Extensions: Beyond-Language Perception, 8-Glyph Calculus, Plane-1 MDE, Ratchet & Trust-Boundary Gates

1. **Beyond-Language, Beyond-Numerology Structural Perception (v1.2, `THEORY.md` §3.5):**
   - **Stage A (Label-Stripping):** Strip disciplinary nouns and base-10/coordinate numerology across candidate domains to perceive raw relational geometry, fiber eliminations, dualities, and obstructions.
   - **Stage B (Coordinate-Free Null-Equivalence):** Compress silhouettes into basis-, unit-, and radix-invariant exact invariants (`residual == 0`, exact integer inertia, projective invariants, R5 refusal witnesses) verified by independent clean-room oracles.
2. **8-Glyph Exact Operator Calculus (`aletheia calculus`, v1.3, `AUDIT-051`):**
   - Standardized zero-collision Unicode `Sm` notation (`0 / 227,540` Lean 4 corpus hits) with 1-to-1 pure-$\mathbb{Q}/\mathbb{Z}$ executable semantics and ASCII fallbacks: `⧄` (`|/|`, Schur pushforward), `⧅` (`|\|`, dark-mode shadow), `⦷` (`(||)`, holonomy unmasking), `⟠` (`<=>`, observer-net equalizer), `⧇` (`[o]`, cohomological obstruction), `⦺` (`(+-0)`, Krein inertia), `⩩` (`=#=`, exact null-equivalence forbidding floats), and `⫩` (`_|T`, R5 refusal-verified gate).
   - Executable via `aletheia calculus [--list | --eval EXPR | --self-test] [--json]`, certifying 13 compressed theorems and 6 commutator probes (`C1`–`C6`) with zero floats.
3. **Plane-1 MDE Contract (`aletheia mde`, `AUDIT-027`):**
   - An Aletheia expedition may be packaged unconditionally as a **Plane-1 Model Domain Expansion (MDE)** using deterministic `zone-canon-v0` manifest IDs, dyadic integer zone scales, content-addressed causal `AUDIT-XXX` lineage DAGs enforcing **`author != verifier`** and Hard Veto #2 contested-head halts, and compact `abios`-compatible `SYM-2P/2.0-rcp` wire packets.
   - **Plane-2 Mechanical Obstruction (`plane2_oracle_compilation_forbidden: true`):** Verification oracles MUST NEVER be compiled into neural weights; Plane-2 weight adapters are strictly disposable caches subordinate to Plane-1 deterministic verification.
4. **5-Gate Autonomous Ratchet Contract (`aletheia ratchet`, `AUDIT-026R` + `AUDIT-023`):**
   - Any automated hill-climbing or autoresearch loop running under Aletheia MUST enforce: (i) immutable Ring-0 evaluation harness lock, (ii) float-free canonical hash-chained receipts, (iii) AST-identity unchanged-baseline null rejection, (iv) Pre-Adaptation Goodhart Latch halt + blind portal re-entry preserving informative failed branches, and (v) a fixed-compute `CS-08` survival cap.
5. **Hardened v1.4 Static Lean 4, Strict JSON/JSONL, Ancestor-Permission & R5 Wrapper Gates (`aletheia audit-check` & `aletheia mutate`, `AUDIT-028`–`065`):**
   - `--prereg-check` verifies strict topological plan-before-data ordering via git DAG ancestry (`LATEST(plan) < EARLIEST(data)`, rejecting same-commit bulk, post-hoc plan rewrites, typo masking, and dash-prefixed refs).
   - `--lean-audit` enforces char-literal `'"'` (`T-12`) & nested-comment-safe lexing, multiline `debug.skipKernelTC`, `sorryAx`, `Lean.ofReduceBool`, `Lean.trustCompiler`, declaration-scoped `partial` (zero `.partial` FPs), Lean 4.22 `(public|private|meta)? import` with repeatable accumulating `--allow-project-import` (`ALETHEIA-CLI-01` fixed in v1.3), `@[extern]`/`@[implemented_by]` hard escapes vs. `@[csimp]`/`ExistsImplication` review notices.
   - `--comparator-config` validates dual-kernel Comparator JSONs (`enable_nanoda: true`, permitted axioms, Spec $\not\to$ Proof isolation); `--pinned-manifest` verifies `CORE_MANIFEST.json` SHA-256 digests and `SafeVerify` 40-hex commit-SHA pins with path-traversal protection.
   - `loads_strict_json` / `load_strict_jsonl_file` reject duplicate keys at every depth, non-RFC-8259 `NaN`/`Infinity`, and whitespace-only tampered JSONL ledgers (`WD-LEDGER-01`); `--strict-ancestors` (`verify_ancestor_dir_modes`) enforces canonical `0o022`-free permissions along the entire `/` through parent ancestor chain (`BYPASS-04`); `aletheia mutate` AST-detects local single-refusal helper wrappers (`_req`, `_fail_if`, `PR1-B4`).

---

## 7. Machine-Readable Schemas

Formal JSON Schemas (`draft/2020-12`) corresponding to this specification reside in [`../schemas/`](../schemas/):
- [`schemas/audit_receipt.v1.schema.json`](../schemas/audit_receipt.v1.schema.json)
- [`schemas/frontier_portal.v1.schema.json`](../schemas/frontier_portal.v1.schema.json)
- [`schemas/compute_handoff.v1.schema.json`](../schemas/compute_handoff.v1.schema.json)
