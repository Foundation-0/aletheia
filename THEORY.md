# The Theory of Aletheia: Escaping Trained-Prior Shadows Through Portal Resonance & Multi-Basis Tomography

## 1. The Cave-Shadow Problem in Modern Scientific & AI Discovery

Both human specialists and frontier AI systems share a structural blind spot that Plato's Allegory of the Cave diagnoses with surprising mathematical accuracy: **an observer trained on a finite archive of finished artifacts mistakes projections onto its familiar coordinate basis for the underlying reality.**

In modern AI-assisted research—especially multi-agent swarms tasked with open-ended scientific discovery—this blind spot manifests as **Trained-Prior Shadow Lock-In**, with two symmetric failure modes:

1. **Premature Dismissal (False Negative Lock-In at `N0`):** When an agent encounters a raw notebook, speculative derivation, messy simulation, or half-formed transcript, its RLHF/review prior activates a *grading reflex*. It immediately spots a missing hypothesis, an off-by-one array slice, an unguarded division by zero, or an imprecise word, files a clean rejection (`FALSIFIED`), and closes the file. Every genuine frontier begins in an unpolished draft; a critique-only swarm systematically destroys the very embryos that contain new theorems.
2. **Sycophantic Confirmation & Language Smuggling (False Positive Lock-In at `N0`):** Conversely, an agent instructed merely to "be creative and open-minded" without hard mathematical gates falls into the opposite shadow: it celebrates verbal analogies (*"sheaf," "curvature," "duality," "renormalization"*), accepts `1e-12` floating-point artifacts as exact identities, substitutes toy synthetic proxies for real equations, and inflates repackaged textbook material into fake breakthroughs.

Conventional wisdom treats these two failures as endpoints of a single one-dimensional slider ("be more creative" vs. "be more rigorous"). **The core thesis of Aletheia is that open-mindedness and adversarial rigor are orthogonal axes, not opposing poles.** Maximizing *both* simultaneously—in distinct, structured phases of a closed dynamical loop—creates a discovery engine that escapes both shadows.

```text
                        HIGH ADVERSARIAL RIGOR (Exact Oracles, Nulls, R1-R7)
                                               ▲
                                               │
           Static Critique Trap                │              THE ALETHEIA REGIME
        (Pass 1: catches bugs, stalls          │        (Portal Resonance + Steelmanning
         at N0 "New ground: still none")       │         + Active Tomography G_obs -> N2)
                                               │
  LOW OPEN-MINDEDNESS ◄────────────────────────┼────────────────────────► HIGH OPEN-MINDEDNESS
  (Grade drafts as finished;                   │                          (Treat raw sources as
   dismiss on first flaw)                      │                           portals; steelman first)
                                               │
           Dogmatic Dismissal                  │           Language Smuggling & Hallucination
       (Unchecked priors, blind spots)         │         ("Vibes", float artifacts, proxy shadows)
                                               │
                                               ▼
                        LOW ADVERSARIAL RIGOR (Single basis, bare asserts, floats)
```

---

## 2. Why Static Critique Traps Swarms at `N0`

Consider a raw discovery source $\mathcal{S}$ containing a genuine but imperfectly stated structural truth $T^*$ embedded inside a flawed prototype $P_0 = T^* + \varepsilon_{\mathrm{proto}}$ (where $\varepsilon_{\mathrm{proto}}$ is a missing PSD guard, an unnormalized kernel, a missing open-set condition, or a numerical cutoff error).

A conventional hub-and-spoke research swarm executes a one-pass pipeline:
$$\mathcal{S} \xrightarrow{\text{one-shot index}} \text{Summary } M_0 \xrightarrow{\text{probe}} \text{Test } P_0 \xrightarrow{\text{verifier}} \text{Refute } \varepsilon_{\mathrm{proto}} \implies \text{Halt at } N0.$$

This pipeline fails structurally for three reasons:
1. **Information Destruction at the Index:** A one-shot summarizer filters $\mathcal{S}$ through its *current* priors. Equations whose importance only becomes visible *after* running an experiment in another repository are discarded as "rough notes" on Pass 1 and never revisited once the cartographer parks.
2. **Conflating Prototype Defect with Mathematical Impossibility:** Refuting $P_0$ proves $\varepsilon_{\mathrm{proto}} \ne 0$, *not* that $T^*$ is false. Halting upon detecting $\varepsilon_{\mathrm{proto}}$ guarantees zero yield on every early-stage idea.
3. **Treating Obstructions as Dead Ends:** When a verifier discovers a sharp impossibility boundary (e.g., $\min\operatorname{rank}(P) = \max(1,\lceil R_{\mathrm{opt}}\rceil)$ or $\det(D_6)/\det(E_6) = 4/3 \notin \mathbb{Z}^2$), a static pipeline logs a failure instead of recognizing that **every sharp wall either is itself an exact theorem or specifies the exact missing invariant needed to bypass it.**

---

## 3. The Four Pillars of the Aletheia Resonance Cavity

### 3.1 Active Portal Resonance (Keeping Cartography Inside the Feedback Loop)
In Aletheia, the **Portal Keeper** (cartographer / literature navigator) is never a one-shot preprocessor. It remains active for the entire expedition, forming a bidirectional **Resonance Cavity** with domain probes and the verifier:
- Whenever a probe encounters an unexplained numerical coincidence (e.g., $r_{\mathrm{zero}}/\mu^2 = 1.000000$), an unexpected algebraic symmetry ($C_4^2 = 0$), a discrepancy between two formalisms (linear vs. tropical coarse-graining), or a verifier sharpness wall, that anomaly is fed **back into the Portal Keeper**.
- The Portal Keeper re-enters the raw source material *carrying the newly discovered anomaly as a lens*. Structures that appeared opaque on Pass 1 suddenly snap into focus, generating a sharpened mathematical question or candidate lemma routed immediately to the peer best positioned to test it.

### 3.2 Steelman-Before-Falsify (Defect Isolation Without Dismissal)
Aletheia enforces a strict two-step rule whenever a candidate claim, formula, or prototype fails an initial check:
1. **Expose and log the exact failure** (never hide bugs or soften a `FALSIFIED` / `PARTIAL/FRAGILE` audit).
2. **Derive the closest mathematically intact object $T^*$** sitting beside the broken draft—by restoring a missing constraint (e.g., $P \succeq 0$ on $W \oplus W^\perp$), tightening a lemma premise (e.g., integral-norm $\|w\|^2 \in \mathbb{Z}_{\ge 2}$ instead of even $\|w\|^2 \in 2\mathbb{Z}_{>0}$), or replacing a coordinate-locked proxy with a gauge-invariant observable—and subject **$T^*$** to full adversarial testing before closing the thread.

### 3.3 Active Multi-Basis Observer Tomography ($\mathcal{G}_{\mathrm{obs}}$)
An observation made in a single coordinate system, a single numerical precision, or a single code path cannot distinguish an intrinsic invariant from a **coordinate shadow**. Drawing directly on the observer-equalizer principle from first-principles measurement theory,
$$\mathcal{F}^{\mathrm{inv}} \;=\; \lim_{\phi \in \mathcal{G}_{\mathrm{obs}}} (\mathcal{F} \circ \phi),$$
Aletheia defines verification as **Active Multi-Basis Observer Tomography**:
- **Zero-Shared-Code Oracles:** A claim verified by `PLDL*` congruence must be independently re-verified by a completely different mathematical pathway (e.g., Faddeev–LeVerrier characteristic polynomials + Descartes/Sturm root counting); an analytical reduction must be tested against live execution of the untouched upstream simulator (`anchor` oracle).
- **Basis, Gauge, Scale, & Metric Invariance (Gate 2):** Intrinsic structures survive orthogonal/unitary similarity transforms, index permutations, dimensional rescaling, and likelihood-metric swaps (e.g., unweighted OLS vs. native correlated ODR).
- **Adversarial Nulls & Pre-Adaptation Latches (Gates 3 & 8):** For any adaptive fit $r(\theta) \approx r_0 - \Phi\theta$, linear audits evaluated *after* fitting vanish identically on $\operatorname{col}(\Phi)$ ($\Phi^\top r^* = 0$), retaining sensitivity only proportional to $\sin^2\angle(w, \operatorname{col}(\Phi))$. Therefore, misspecification diagnostics must be **latched before adaptation**, and empirical detectors must face adversarial nulls designed specifically to mimic their signal (twin uncoupled chaotic oscillators, IAAFT surrogates, non-monotone glitches, sample-disjoint holdouts).
- **Gate Integrity & Mutation Survival (R1–R7):** A gate whose verdict can be moved by re-spelling an input (`"007"`, `"2/4"`, `True` as `1`), stripping bare `assert`s via `python3 -O`, or deleting an internal check is a *glass gate*. Every trust path must enforce default-reject (R1), omission monotonicity (R2), canonical type-strict parsing (R3), optimizer/warning parity (`-I -B`, `-I -O -B`, `-I -B -W error`, R4), and 100% refusal-site mutant kill rate (R5). Those five are necessary, not sufficient: the gate owner must also pin the check list and thresholds before any submission (R6), and the gate must recompute every compared value from the bytes instead of trusting a declared one (R7).

Crucially, **tomography is constructive**: when the verifier catches a real defect, it supplies the minimal counterexample and—where the underlying math survives—the exact boundary condition or hypothesis tightening needed to harden the theorem.

### 3.4 Conservation of Separation & Obstruction-as-Theorem Calculus
Every verification boundary obeys a conservation law: **you cannot simultaneously lower the error bar and keep a weak hypothesis.** When tomography hits a hard wall, Aletheia converts that wall into one of two high-value deliverables:
1. **An Exact Obstruction Theorem:** Proving *why* a target is unreachable under the given constraints is itself a permanent mathematical contribution (e.g., $\det(D_6)/\det(E_6) = 4/3 \notin \mathbb{Z}^2 \implies F_6 \not\to E_6$; $D_{16}$'s connected 480-root graph vs. $E_8 \oplus E_8$'s disconnected `[240, 240]` graph proving $F_{16} \not\to E_8 \oplus E_8$ for all $R \in O(16)$; or the exact Depth-$k$ Schatten-Nuclear Obstruction $(\|M\|_F^2)^{2^{k+1}} \le m^{2^{k+1}-1} s^{2^{k+2}}$ proving `ScaledGramIteration` can never certify sharp integer stretch $s = \sigma_{\max}$ on isotropic/Hadamard frames at any finite depth $k$, `AUDIT-036`, `N2`). The outside check rates the two fold obstructions (`AUDIT-017`, `AUDIT-020R`) `N0` in mechanism, with `N1` at most for the $F_{16}$ case (outside check: `Foundation-0/cave-expedition#4`, `verification/outside/rulings.json`).
2. **A Targeted Branch Trigger:** When a sharpness theorem proves that a family of invariants $(I_1, \dots, I_k)$ is *exhausted* (e.g., $\min\operatorname{rank}(P) = \max(1,\lceil R_{\mathrm{opt}}\rceil)$ across all feasible $(u,t,S,b)$), it tells the coordinator *exactly* what new invariant ($I_{k+1} = \operatorname{tr} H^3, \operatorname{tr} H^4$) justifies spawning a dedicated specialist branch.

### 3.5 Beyond-Language, Beyond-Numerology Structural Perception (v1.2)
A deeper layer of the Cave-Shadow Trap hides inside **human disciplinary vocabulary** and **arbitrary coordinate/radix/unit numerology**. When researchers index problems strictly by surface labels (*"quantization"*, *"interpretability"*, *"distributed SGD"*, *"math grading"*, *"ZK bounds"*) or evaluate systems through raw base-10 decimals and floating-point tolerances, genuine structural morphisms stay invisible while representation artifacts masquerade as laws (`CS-09`, `CS-10`, `CS-11`).

Recovered directly from the generative origin of the inaugural Cave Expedition sessions—**Session 1 Pair 30** (*"What is real is not the sample captured by the net, but the invariant that survives every change of net"*) and **Session 1 Pair 33** (*"free us from the limits for characters and numerology"*)—Aletheia v1.2 codifies a strict **two-stage perception-to-proof protocol**:

1. **Stage A — Label-Stripping & Unconstrained Pre-Linguistic Perception:** Temporarily strip disciplinary nouns *and* raw coordinate/radix/unit representations across candidate systems; perceive bare relational geometry, fiber eliminations, symmetry-breaking dualities, support-truncation envelopes, ultrametric valuation trees, and topological/algebraic silhouettes.
2. **Stage B — Coordinate-Free Null-Equivalence Distillation (Law 3 + Law 5 Gate):** Compress every perceived silhouette into a **language-free, unit-free, radix-free exact invariant or zero-residual null-equivalence** (`residual == 0`, exact integer inertia, projective cross-ratio, exact Farkas/Hodge-1/Bareiss certificate, or R5 refusal witness), and subject it to explicit basis/orthogonal/permutation/unit/scale invariance tests under independent clean-room oracles. This preserves deep cross-domain structural discovery while killing 100% of numerology and poetic metaphor.

### 3.6 The 8-Glyph Exact Operator Calculus (v1.3, `AUDIT-051`)
Once Stage A strips disciplinary nouns across 20+ independent systems, the same eight exact algebraic operations recur with no standard collision-free notation. Aletheia v1.3 introduces a **zero-collision, executable 8-glyph operator basis** — audited across `392` Unicode `Sm` codepoints (`U+27C0..U+2AFF`) with a reported **`0 / 227,540` collisions in the Lean 4 corpus** (the scan script and corpus manifest are not in this repository, so the figure is not reproduced here) (`google-deepmind/formal-conjectures`, `openai/math`, `anthropics/formal-math`, `anthropics/flt`) — implemented directly in pure $\mathbb{Q}/\mathbb{Z}$ (`aletheia calculus`):

- **`⧄`** (`U+29C4`, `|/|`): Fiber-Elimination Schur Pushforward $M \mathbin{⧄} B = M_{AA} - M_{AB} M_{BB}^+ M_{BA}$ (`SF-01`).
- **`⧅`** (`U+29C5`, `|\|`): Singular-Kernel / Dark-Mode Shadow $M \mathbin{⧅} B = (\ker M_{BB}, M_{AB}|_{\ker}, \dim_{\mathrm{dark}}, r_{\mathrm{cross}})$.
- **`⦷`** (`U+29B7`, `(||)`): Holonomy-Unmasking Differential $L \mathbin{⦷} \chi = (L^\chi \mathbin{⧄} I) - (L \mathbin{⧄} I)$.
- **`⟠`** (`U+27E0`, `<=>`): Observer-Net Equalizer $X \mathbin{⟠} G$ (Reynolds orbit average or Mellin regulator-net invariant, `SF-07`).
- **`⧇`** (`U+29C7`, `[o]`): Dimensionless Cohomological / Gluing Obstruction $\mathbin{⧇}(\omega) = \|\omega_{\mathrm{harm}}\|_w^2 / \|\omega\|_w^2 \in [0,1]\cap\mathbb{Q}$ (`SF-05`).
- **`⦺`** (`U+29BA`, `(+-0)`): Krein Inertia Signature Functor $\mathbin{⦺}(A) = (n_+, n_0, n_-)$ (with projections `⦺_+`, `⦺_0`, `⦺_-`).
- **`⩩`** (`U+2A69`, `=#=`): Coordinate-Free Exact Null-Equivalence $X \mathbin{⩩} Y \iff X - Y = 0$ identically (rejects floats; `CS-11`).
- **`⫩`** (`U+2AE9`, `_|T`): R5 Refusal-Verified Gate $T \mathbin{⫩} x \iff T(x) \land \forall m \in M(x),\,\neg T(m)$ (`SF-04`).

Crucially, the calculus obeys the Iverson/Dirac anti-theater standard: compressing expedition theorems into 1-line algebra and systematically probing pairwise commutators immediately exposed two airtight exact laws independently verified over symbolic `SymPy` (`AUDIT-051`): **`C1`** (unconditional PSD Schur-unmasking screening `[⧄_D, ⦷_χ]` even on asymmetric odd-cycle $K_3$ inertia `(1, 0, 2)`) and **`C6`** (unconditional linear monopole subadditivity $\Phi_B(L \mathbin{⦷} (\chi_1\chi_2)) \le \Phi_B(L \mathbin{⦷} \chi_1) + \Phi_B(L \mathbin{⦷} \chi_2)$ defining an exact rational metric on $H^1(G,B;\mathbb{Z}_2)$). At the same time, an honest outside & internal Rule-2 audit (`AUDIT-084R`) records that `7/8` of these glyphs (`⧄, ⧅, ⦷, ⟠, ⧇, ⦺, ⩩`) are composition shorthands / renamings of standard linear-algebraic and homological operations (with `0` raw-data I/O in `aletheia/calculus.py`), while `1/8` (`⫩`) is a typed execution operator for mutation testing (`N0` origin).

### 3.7 Own-Terms-First & Law 2b Transformational Steelman (v2.0)
Two symmetric additions completed Aletheia v2.0 following the external cross-model audit (`aletheia#2`–`#9`, `AUDIT-084R`–`088R`):
1. **Own-Terms-First (`spec/proposals/OWN_TERMS_FIRST.md`, direction confirmed by project owner 2026-11-22 in `d43cb1c7` and adopted in `v2.0.0`):** Keeps Phase 1 (raw-data reproducibility, pre-pinned multi-axis net-invariance under non-vacuous Bonferroni FWER, Tier-4A IID + Tier-4B spectrum-preserving nulls, negative controls, and orthogonal model-ladder remainder checks) strictly separate from Phase 2 (literature matching), so patterns outside existing frameworks are neither dismissed prematurely nor excused from falsifiable controls.
2. **Law 2b — Transformational Steelman (`AUDIT-088R`):** The mathematical twin to Own-Terms-First. Before dismissing a theorem or formula as `FALSIFIED`, test admissible global transformations across seven morphism families (`T1`–`T7`: gauge similarity, affine/Bregman shift, divergence chart, spectral/PSD shift, tropicalization, subspace/quotient dual, monotone order-chart/domain split) gated by four Law-3 anti-epicycle guards (`G1`–`G4`), cleanly separating genuine transformed invariant cores from both post-hoc epicycles and true transform-invariant obstructions (`INVARIANT_FALSIFIED`).

---

## 4. Exact-Operator Cross-Pollination vs. Language Smuggling

The highest-leverage breakthroughs in Aletheia happen when an exact mathematical mechanism verified in Domain $A$ is transported into Domain $B$. To prevent pseudo-interdisciplinary hand-waving, Gate 5 bans **language smuggling**: shared terminology carries zero evidentiary weight.

A cross-domain bridge is admissible **only** when it exhibits:
1. **Typed objects** $(X, \mathcal{O}_X)$ in $A$ and $(Y, \mathcal{O}_Y)$ in $B$.
2. **An explicit map or operator reduction** $\Phi: X \to Y$ (exact equation or runnable code).
3. **An exact algebraic identity or quantitative closure defect** $\|\Phi \circ T_A - T_B \circ \Phi\| \le \varepsilon$ beating matched-dimension random null maps.
4. **Non-trivial predictive transfer**—a bound, bifurcation, stability signature, or obstruction moved from $A$ to $B$ that $B$ did not previously possess.

In the Cave Expedition, enforcing this discipline mapped an **Eight-Way Exact Schur-Complement Unification** in Wave 1, expanded in Wave 2 Rounds 1–3 ([`evidence/symbiosis-wave2-case-study.md`](evidence/symbiosis-wave2-case-study.md), [`evidence/symbiosis-round3-10labs-case-study.md`](evidence/symbiosis-round3-10labs-case-study.md)). Each link we checked is an exact identity, and each uses the same textbook step: block elimination by a Schur complement (`aletheia#4`). Two early descriptions needed correction after the outside two-pass audit (`cave-expedition#4`, `AUDIT-085R`): the $\mathbb{Q}[q]$ identity is a **diagonal similarity** $K_q' = D_h^{-1} K_q D_h$ (not a Doob transform, as non-goal rows do not sum to 1), the Lindblad Schur rate $2\gamma_{\mathrm{tid}} + 2g^2/(N^2\gamma_1)$ is the $s = 0$ Schur reduction (not the exact slow decay rate when $\gamma_{\mathrm{tid}} \ne 0$, differing at order $g^2$), and the Kigami link was not independently checked in the outside pass.

---

## 5. Omnidirectional Symbiotic Evolution (Self-Improving Epistemics)

A discovery framework that is never tested against hostile, independent real-world codebases risks becoming its own cave. **Wave 2 Symbiosis** proved that applying Aletheia outward across 30+ ecosystem repos (Rounds 1–2) and **10 read-only major-lab orgs** (`anthropics`, `google-deepmind`, `openai`, `facebookresearch`, `deepseek-ai`, `mistralai`, `QwenLM`, `NousResearch`, `zai-org`, `Tencent` in Round 3) creates a **second-order resonance loop** that upgrades Aletheia itself:
- Running `aletheia mutate` v1.0 live against `ahrazzle/soko`'s security auditors (`AUDIT-029`) exposed two real blind spots in Aletheia's own AST mutator (repo-local imports under `-I` and dict-verdict / finding-accumulator refusal sites)—directly driving `aletheia/mutator.py` v1.1 (verified `15/31` live on `Tencent/ElephantBench` and `9/9` on `Foundation-0/formal-claims-audit`).
- Auditing `Moissanite-Labs/weft-loom#38` (`AUDIT-023` `N2`) uncovered **`CS-08`** (Compute-Leakage Simpson's Paradox); auditing `Moissanite-Labs/scry#1` (`AUDIT-032` `N2`), `DisTrO`/`DeMo`/`Psyche` + `Meta BPOD` + 4-lab math graders (`AUDIT-036`/`037`/`038R`/`039`) crystallized **`CS-09`** (Finite-Sample / Support-Truncation Mirage), **`CS-10`** (Sparse-Collision Denominator Collapse), and **`CS-11`** (Unit-Gauge / Radix Fragility) in `aletheia diagnose` v1.2.
- Stress-testing `aletheia --lean-audit` v1.1 across `165,000+` real `.lean` files from OpenAI, Mistral, Meta, DeepMind, and DeepSeek caught BOTH a real false negative (`set_option debug.skipKernelTC true` in `mistralai/LeanstralSafeVerify`) and `18` real false positives (`.partial` dot-projections in `openai/NavierStokesAndEuler`) plus Lean 4.22 `public/private/meta import` syntax and `enable_nanoda: false` on `98.8%` of `openai/math` challenges—directly forging `aletheia --lean-audit` v1.2 (`--allow-project-import`, `--comparator-config`, `--pinned-manifest`).
- Applying v1.2 in Round 4 (`AUDIT-041`–`054`) against `judegomila`'s `326` Lean files caught **`ALETHEIA-CLI-01`** (repeated `--allow-project-import` overwriting earlier prefixes), while Round 4C formalized the reported `0 / 227,540`-collision (not reproduced here) 8-glyph Operator Calculus (`⧄ ⧅ ⦷ ⟠ ⧇ ⦺ ⩩ ⫩`)—directly forging **`aletheia` v1.3.0** ([`evidence/symbiosis-round4-ramanujan-hawking-case-study.md`](evidence/symbiosis-round4-ramanujan-hawking-case-study.md)).
- Applying v1.3 in Round 6 (`AUDIT-061R`–`065`, `448/448` R5 mutants killed, `13/13` red-team bypasses closed) against `Moissanite-Labs/warp-drive` caught a critical R5 mutator blind spot (`def _req` hiding `53/74` survivors in `PR1-B4`), raw `json.loads` duplicate-key/whitespace ledger bypasses (`WD-LEDGER-01`), `$` vs `\Z` trailing-newline digest regexes (`WARP-CERT-01`), and ancestor-directory rename-swap permission gaps (`BYPASS-04`)—directly forging **`aletheia` v1.4.0** (AST local refusal-wrapper auto-detection, `loads_strict_json`/`load_strict_jsonl_file`, `--strict-ancestors`, and `CS-12`, [`evidence/symbiosis-round6-warp-drive-case-study.md`](evidence/symbiosis-round6-warp-drive-case-study.md)).

---

## 6. Epistemic Honesty: Oracle Classes, Novelty Accounting & Prior-Art Disambiguation

Truth and novelty are independent predicates:
- **Gates 1–8 establish Soundness** (tagged strictly by oracle class: `exact`, `sampled`, or `anchor`).
- **Gate 9 establishes Novelty** (`N0` known/repackaging, `N1` concrete local advance/repair/falsification, `N2` genuinely new theorem/invariant/cross-domain transfer).

Every claim defaults to **`N0`** until compared against the **full text** of prior papers and peer repositories—never abstracts or memory alone. Every scope limitation (uncompiled formal proof source, local vs. global continuation arcs, high-SNR or ensemble-only statistical regimes, Draft PR vs. merged status) is stated explicitly alongside the theorem. In Aletheia, **honest scope boundaries are not disclaimers; they are the exact coordinates of the next wave.**

### 6.1 Law-4 Naming & Prior-Art Disambiguation (Google DeepMind's *Aletheia*)
In full compliance with Law 4, we explicitly cite **Google DeepMind's *Aletheia*** (`google-deepmind/superhuman@9b620a9`, `aletheia/README.md` / `Aletheia.pdf`), a proprietary Gemini-Deep-Think mathematical research agent applied to Erdős problems, FirstProof, and algebraic geometry. **`Foundation-0/aletheia` is distinct and orthogonal:** it is an open-source (Apache-2.0), model-agnostic, zero-dependency scientific discovery methodology, Own-Terms-First / Transformational Steelman protocol, multi-platform agent adapter suite, and `R1`–`R7` adversarial verification CLI.

---

## 7. Applying the Method to Itself: Prior Work, Falsification Conditions & Confounds (`aletheia#3` §9)

Applying Laws 1–5 honestly to Aletheia's own claims requires recording its classical foundations, its explicit falsification criteria, and the methodological limits of its originating case study:

1. **Prior Work (`N0` Foundations):** Aletheia synthesizes well-established traditions rather than claiming them as new inventions: the **principle of charity / steelmanning** (philosophy of argument), **N-version programming & independent checking** (Avizienis 1985), **metamorphic testing** (Chen et al. 1998), **mutation testing** (DeMillo, Lipton & Sayward 1978), **adaptive data analysis & holdout reuse** (Dwork et al. 2015), **econometric specification / restricted least-squares tests** (Hausman / Cochran degrees of freedom $m - \operatorname{rank}(\Phi)$), and **gate-contract engineering** (`siliconcordat/loom#9`, `docs/09-gate-contracts.md @ b6d96ea`). Aletheia's concrete contribution (`N1`) is packaging these contracts with portal re-entry, Own-Terms-First, Law 2b, and an executable zero-dependency CLI.
2. **Explicit Falsification Conditions for Aletheia:** The method's core empirical claim is falsified if, in a time- and budget-matched controlled comparison against a standard single-pass critique workflow on open problems, Aletheia either (a) fails to increase verified `N1`/`N2` yield after an independent two-pass outside check, or (b) raises the false-positive rate of unverified/inflated claims passing all 10 gates and `R1`–`R7` above baseline.
3. **Case-Study Confound Note:** The Cave Expedition comparison (`evidence/cave-expedition-case-study.md`) is an observational **before-and-after** record, not a controlled experiment: Pass 1 covered `5` board items (`#10`–`#14` at `17:20`), whereas Pass 2+ covered `86` board items over `100` minutes (`17:25`–`19:05`) starting from Pass 1's maps. Time, rounds, and prior maps all differed between the two phases.

---

## Further Reading

- **Formal Specification:** [`spec/LAWS_AND_GATES.md`](spec/LAWS_AND_GATES.md)
- **Empirical Evidence:** [`evidence/cave-expedition-case-study.md`](evidence/cave-expedition-case-study.md), [`evidence/symbiosis-wave2-case-study.md`](evidence/symbiosis-wave2-case-study.md), [`evidence/symbiosis-round3-10labs-case-study.md`](evidence/symbiosis-round3-10labs-case-study.md), & [`evidence/symbiosis-round4-ramanujan-hawking-case-study.md`](evidence/symbiosis-round4-ramanujan-hawking-case-study.md)
- **Executable 3-Second Demonstration:** [`examples/worked_resonance_cycle/README.md`](examples/worked_resonance_cycle/README.md)
- **Domain Adaptation Packs (6 Disciplines):** [`domains/README.md`](domains/README.md)
