# Aletheia Domain Pack: Biology & Life Sciences

> **Scope:** Computational biology, proteomics & mass-spectrometry deconvolution, multi-omics, compartment kinetics, systems biology, and translational/clinical bioinformatics.  
> **Core Challenge:** High-dimensional biological assays mix genuine mechanistic signal with unmeasured nuisance factors (batch effects, donor/site stratification, ionization efficiencies, co-eluting chimeras, and assay saturation), while narrative metaphors ("pathway network", "manifold", "emergence") easily mask cohort-specific overfitting (**Latches**).

---

## 1. Raw Portals in the Life Sciences (Law 1)

In biology and medicine, the highest-leverage discoveries hide inside **assay degeneracies, discordant replicates, and residual structure** that routine pipelines filter away as noise. Treat the following as live portals rather than nuisances to discard:

| Raw Signal / Friction | Cave-Shadow Default (Avoid) | Aletheia Portal Question |
|---|---|---|
| Multiple mechanistic worlds fit a single-point assay identically | Pick the biologically familiar world via priors or post-hoc regularization | What **group symmetry** maps nuisance parameters $(r, c)$ to each other, and what multi-point invariant cancels them *identically*? |
| Secondary peaks / chimeric spectra buried under a dominant backbone | Threshold out minor components or trust heuristic clustering counts | What exact spectral-moment or congruence certificate lower-bounds the true component rank under an explicit noise ceiling $\tau$? |
| A model tuned to fix one failing validation cohort degrades another | Re-weight samples or add ad-hoc batch covariates until aggregate loss drops | Does fitting anchor $a_1$ strictly inflate out-of-distribution Bregman/KL divergence—signaling an **omitted biological variable** $\Psi$ rather than parameter error? |
| Two assays or modalities show high correlation on a shared cohort | Claim "convergent biological mechanism" from correlation alone | Does the lock survive **cohort-disjoint splits**, **non-overlapping lags**, and **decoy/phase-randomized controls**? |

---

## 2. Steelmanning Biological Models via Parameter-Free Invariants (Law 2 & Law 5)

### Worked Pattern A: Eliminating Nuisance Parameters with Exact Group Invariants (`project-asma` / Portal 11, `AUDIT-006R`)

In `Foundation-0/project-asma`, a toy two-state model with invented values (`docs/compartment-identifiability.md`, labelled there "synthetic arithmetic only", ledger row `V19`) maps the high-state fraction $p \in (0, 1)$ of a blood clonotype to its CSF high-state fraction $q$:

$$q(p; r, c) = \frac{r p + c(1 - p)}{r p + (1 - p)}, \qquad r > 0,\; c < 1,$$

where $r$ weights high-state cells relative to low-state cells at entry or retention, and $c$ is the fraction of low-state cells that later convert to high state. At the invented snapshot $p = 1/5$, four settings—`S = (16, 0)`, `C25 = (11, 1/4)`, `C50 = (6, 1/2)`, and `C75 = (1, 3/4)`—produce the **same observation $q = 4/5$** (formal restatement: Lean theorem `snapshot_four_worlds_indistinguishable`, `formal/AsmaIdentifiabilityProofs.lean:32-37`; project-asma's ledger lists no formal proofs, `CLAIMS.md:24`).

- **Pass-1 Trap:** Fit $(r, c)$ from one snapshot, or pick a world by prior. Concluding that a single snapshot does not identify $(r, c)$ is correct (project-asma `V19`); the trap is stopping there instead of asking which further observation would.
- **Aletheia Portal Move:** Recognize $q(p; r, c)$ as a non-degenerate **$PGL(2)$ Möbius transformation** ($\det = r(1-c) \neq 0$) possessing a **universal fixed point $q(1; r, c) \equiv 1$**. Because $PGL(2)$ preserves cross-ratios identically, **both** the 4-point cross-ratio and—exploiting $q(1) = 1$—the **3-point fixed-point cross-ratio** cancel **both** unknown nuisance parameters $(r, c)$ with zero parameter fitting:

$$\mathrm{CR}_4(q_1, q_2; q_3, q_4) \equiv \mathrm{CR}_4(p_1, p_2; p_3, p_4), \qquad \mathrm{CR}_3(q_1, q_2; q_3, 1) \equiv \mathrm{CR}_3(p_1, p_2; p_3, 1).$$

- **Exact Zero-Float Verification (`AUDIT-006R`; Check 10 of project-asma `studies/expedition-mobius-ropt/optimal_inertia_rank.py`, Python `Fraction`, not a Lean theorem; project-asma labels the study author self-checked, with no in-repo second checker or ledger row, novelty `N0`, `studies/expedition-mobius-ropt/README.md:3`):** On rational seed schedule $(1/20, 1/10, 1/5, 2/5)$, $\mathrm{CR}_4 = 9/7$ and $\mathrm{CR}_3(\cdot, 1) = 27/19$ hold **identically** across the four settings (`S`, `C25`, `C50`, `C75`) and one further rational world $(37/5, 2/11)$; the general statement is textbook $PGL(2)$ invariance (`N0`), not a separate verification.
- **What the invariants can and cannot test (negative controls):** A non-Möbius readout $r(p) = 6 + 10p$ with $c = 1/2$ breaks both invariants ($\mathrm{CR}_4 = 1431/1133 \neq 9/7$, $\mathrm{CR}_3 = 567/418 \neq 27/19$), so they can reject readouts outside the fractional-linear family. They cannot separate members of the family: $\mathrm{CR}_4$ and $\mathrm{CR}_3$ take the same values for `S`, `C25`, `C50` and `C75` by construction. $\mathrm{CR}_4$ stays `9/7` under any affine readout bleed $y = (1-\alpha-\beta)q + \alpha$, because an affine map is itself fractional-linear. $\mathrm{CR}_3$ with the literal fixed point `1` moves when $\beta \neq 0$ (`291/187` for `S` at $\alpha = \beta = 1/10$), so a $\mathrm{CR}_3$ failure can come from readout loss rather than a third compartment. Separating selection from conversion needs a changed starting mixture. In project-asma's declared synthetic model (`V48`, `docs/research/compartment-measurement-design.md`), the pair of inputs $(1/10, 2/5)$ separates zero conversion from the `C50` and `C75` settings, with exact boundary $\varepsilon < 13/700$, under a shared offset $|b| \le 1/20$. It separates all four settings only for $\varepsilon < 3/448$, not at project-asma's illustrative $\varepsilon = 1/60$. Under unanchored readout bleed $\alpha = c$ with $\beta = 0$, pure selection $(r, 0)$ reproduces the conversion world $(r, c)$ at every $p$, since $(1-c)\,q(p; r, 0) + c = q(p; r, c)$; a readout standard of known composition $p = 0$ that fixes $\alpha$ is then needed. All inputs are invented; nothing here is an assay precision. The paired-design ceilings are restated in Lean as `pr78_sharp_separation_hierarchy` (`formal/AsmaIdentifiabilityProofs.lean:39-52`), a formal restatement outside project-asma's ledger.

### Worked Pattern B: Exact Chimeric Spectral-Rank Certification Under Unknown Noise (`AUDIT-002`, `AUDIT-006R`, `AUDIT-014`)

In tandem mass spectrometry (MS/MS) and mixed-population deconvolution, an observed $T \times T$ scan Gram matrix $G = P + Q + N$ mixes:
- a known dominant backbone $Q$ with certified positive inertia $n_+(Q) \le b$ ($W = \operatorname{range}(Q_+)$),
- unknown chimeric/co-eluting species $P \succeq 0$, and
- unknown PSD measurement noise bounded by $0 \preceq N \preceq \tau I_T$.

1. **Exact Quadratic Envelope & Trace-Slack Sensitivity Law (`AUDIT-002` `N1`, `AUDIT-006R`) (outside check: `Foundation-0/cave-expedition#4`, `verification/outside/rulings.json`):**
   Subtracting the conservative noise envelope $M = G - \tau I_T$ and certifying $n_+(Q) \le b$ via exact zero-float block-$LDL^\top$ congruence over $\mathbb{Q}$, the scale-invariant bound (on its strong-interference branch $b > 0, t_- > 0, b t_M > t_-, b S > t_-^2$)
   $$R_{\mathrm{opt}} = \frac{(t_M - t_-)^2}{S - t_-^2 / b} \le n_+(\Pi_{W^\perp} H \Pi_{W^\perp}) \le \operatorname{rank}(\Pi_{W^\perp} P \Pi_{W^\perp}) \le \operatorname{rank}(P)$$
   exposes a **certified first-order sufficient noise-slack threshold** $\Delta t^* = \|P\|_F^2 / (2 t)$, a conservative sufficient condition rather than an exact law: the exact worst-case crossing is $\approx 4.8\%$ above $1/360$ on this benchmark, and the crossing for the noise actually present lies higher still (outside check `twoloop-stack` `F5`, `verification/outside/rulings.json`). On a synthetic 3-component, 5-scan Gram matrix with invented weights and no project-asma data ($w_1 = 9/10$ backbone, $w_2 = w_3 = 1/20$ chimeras; called a "CDR2L backbone" in project-asma `studies/expedition-mobius-ropt/optimal_inertia_rank.py:639-649`), $\Delta t^* = 1/360$:
   - Below threshold ($\tau = 1/5000$): $R_{\mathrm{opt}} = 1.5306 > 1$ **certifies $\operatorname{rank}(P_{\mathrm{chim}}) \ge 2$**, whereas naive Mode A (`0.226`), fixed-$c$ (`0.424`), and `loom` $R_G$ (`0.184`) all fail; a single-chimera negative control is cleanly rejected.
   - Above threshold ($\tau = 1/1000$): unknown-$Q$ $R_{\mathrm{opt}}$ drops below `1` (`0.8097`) exactly as predicted by $\Delta t^*$, signaling that either noise must be reduced or $Q$ must be explicitly subtracted (`1.9396 > 1`).
2. **Breaking Past the Quadratic Sharpness Wall via Higher Moments (`AUDIT-014`, Theorem A2 `N0` as a theorem and `N1` for its closed form) (outside check: `Foundation-0/cave-expedition#4`, `verification/outside/rulings.json`):**
   `AUDIT-002` proved an exact pointwise sharpness wall for quadratic moments: $\min \operatorname{rank}(P) = \max(1, \lceil R_{\mathrm{opt}} \rceil)$. Under Aletheia Law 1 & Law 5, that obstruction triggered **higher-moment Stieltjes–Hankel ($R_{H4}$) and Noise-Annihilating Quartic SOS ($\Phi_{x_0, \tau}$) bounds**:
   - **Provenance of the `Scan 23848` regimes below:** they are not computed from project-asma's spectrum. They come from a two-weight model whose weights are the squares of a single-scan ion-current share and its complement, $w_1 = 0.6404^2$ and $w_2 = 0.3596^2$, which cave-expedition labels the "Claimed Scan 23848 Calibration" in its Session 2 verification map (`cartography/session2_verification_map.md:112`; built in `verification/checks/check_001_lemma32_and_tcb.py:265-267` and `verification/checks/check_003_seam01_ropt.py:460-462`; this repository's worked example uses the same weights, `examples/worked_resonance_cycle/run_demo.py:798-800`). `0.3596` is the `35.96%` share of total ion current that project-asma gives to a 19-peak chimeric ladder at m/z `615.02568` on scan 23848 (project-asma `results/formal-synthesis-2026-11-13/PROOF.md:15` and `report.json:43` at `de88b12`; labelled `VERIFIED` in `PROOF.md`, with no row in `CLAIMS.md`), and `0.6404` is its complement ($0.6404 + 0.3596 = 1$). cave labels that complement `64.04%` "CDR2L" (`session2_verification_map.md:43-44`), whereas project-asma's partition of the same spectrum gives `16.80%` to the CDR2L primary b/y ladder (same `PROOF.md` line), `12.39%` to CDR2L auxiliary and immonium ions and `34.86%` to unassigned background (`report.json:34-47`). The backbone-chimera overlap $\rho$ is a free synthetic parameter (`check_003_seam01_ropt.py:464` sweeps $\rho = 0, 1/2, 3/4, 9/10$). Squared shares from one scan are not a multi-scan Gram matrix: cave's own map notes that one MS2 scan gives a rank-1 outer product, so $G$ needs several elution or repeated scans (`session2_verification_map.md:109`). With these weights, `check_003`'s guarded Mode B formula (`R_opt_guarded`, `:239-249`) gives $R_{\mathrm{opt}} = 0.036849\ldots$ at $\rho = 19/20$ (exact rational, recomputed for this note); the `0.0369` below is quoted from the `AUDIT-014` record. That benchmark lives in `Foundation-0/spectral-inertia` (`scan23848_benchmark`, whose `W1` and `W2` cave's `AUDIT-014` check imports at `verification/checks/check_008_spectral_inertia.py:60`) and was not read for this note. project-asma's ledger row `V38` covers only the source linkage and metadata of scan 23848 (`CLAIMS.md:218`).
   - $R_{H4}$ lifts `Scan 23848` Mode B ($\tau = 0, b = 1$) from $R_{\mathrm{opt}} = 0.0369$ to **exact `1`** across all backbone-chimera overlaps $\rho \in [0, 0.95]$.
   - $\Phi_{x_0, \tau}$ (built with a double zero at $-\tau$ to annihilate noise eigenvalues) certifies chimeric rank $\ge 2$ on **6 high-interference noisy `Scan 23848` Mode A regimes** ($\rho \in [0.75, 0.95], \tau \in [0.005, 0.020]$) where quadratic bounds collapse, while strictly refusing whenever $\lambda_2 - \tau < 0$.

### Worked Pattern C: Diagnosing Omitted Biology vs. Parameter Misfit (`AUDIT-005`, `AUDIT-008R`)

When an exponential-family or linear biological predictor $q^* \in \mathcal{E}_\Phi$ (fixed assay feature set $\Phi$) fails an external clinical/experimental anchor $a_1$, forcing $q_{\mathrm{adapt}} \in \mathcal{E}_\Phi$ to silence $a_1$ without expanding $\Phi$ obeys **exact global Bregman / KL Pythagoras**:

$$D_F(p \,\|\, q_{\mathrm{adapt}}) \;=\; D_F(p \,\|\, q^*) \;+\; D_F(q^* \,\|\, q_{\mathrm{adapt}}) \;>\; D_F(p \,\|\, q^*).$$

On a fresh unseen cohort anchor $a_2$, adaptation helps **if and only if** the Fisher-metric overlap lies inside the sharp phase window $0 < \rho_{\Phi, G}(a_1, a_2) / \kappa_\perp < 2$; outside that window it strictly worsens error, whereas expanding the specification ($\Phi \to [\Phi, \Psi_{\mathrm{rev}}]$) to include the omitted biological state strictly contracts divergence by $-D_F(q_{\mathrm{rev}} \| q^*)$.

---

## 3. Mandatory Negative-Control & Oracle Architecture (Law 3)

Every biological claim must explicitly declare its **Oracle Class** and pass domain-matched negative controls:

| Claim Layer | Required Oracle Class | Mandatory Negative Controls |
|---|---|---|
| Mathematical identifiability, cross-ratio invariance, Gram rank/inertia bounds | **`exact`** (`int`, `Fraction`, `math.isqrt`, exact `SymPy`) | Single-component rank-1 null (must fail $\ge 2$ certification); non-Möbius / density-dependent departure $r(p) = r_0 + \alpha p$ (must break $\mathrm{CR}_3/\mathrm{CR}_4$); R3/R4 malformed input & `-O` parity checks. |
| Biomarker discovery, differential expression, multi-omics coupling, deconvolution on noisy replicates | **`sampled`** (logged RNG seeds + out-of-sample replication) | **Cohort-, donor-, site-, and instrument-disjoint splits** (never leak technical replicates across train/test!); target-decoy FDR / label permutations; batch-matched null controls; unseen-seed replication; empirical rank $p$-values (`n_surrogates >= 200`) for single-sample decisions. |
| Assay physics calibration, MS raw-file deconvolution, clinical benchmark parity | **`anchor`** (pinned untouched raw datasets or reference standards) | Spike-in blank & known-mixture calibration standards; held-out laboratory / clinical center external validation; pre-adaptation Latch reporting (report metrics *before* any post-hoc threshold tuning!). |

### Strict Separation of In-Silico Proof vs. Wet-Lab / Clinical Validation (Law 4)

Aletheia enforces an iron boundary between mathematical possibility and biological reality:

- **What an `exact` proof establishes:** Under model assumptions $M$ (e.g., two-compartment Möbius kinetics, PSD noise $\preceq \tau I_T$), identifiability or rank lower bounds hold with zero floating-point error.
- **What remains explicitly `not_shown`:** Wet-lab assay linearity, biological absence of unmodeled third compartments, robustness to non-PSD/systematic ionization artifacts, and clinical efficacy across untested patient populations.
- **Rule:** Never upgrade an in-silico `exact` theorem (`AUDIT-006R`, `AUDIT-014`) into a clinical or wet-lab claim without passing `sampled` + `anchor` verification on independent biological cohorts. Every scope boundary must be written verbatim in the report and `AUDIT_LOG.md`.

---

## 4. Biology-Specific Cave-Shadow Anti-Patterns

1. **Cohort/Batch Latch Disguised as Biology:** High cross-validated AUROC from random sample splits that share donors, plates, or acquisition dates. *Remediation:* Split strictly by donor/site/instrument and test against acquisition-shift nulls. `CR4` is unchanged by any affine acquisition shift, so it cannot detect a batch latch.
2. **Threshold & Cutoff Shopping:** Picking peak-height, $p$-value, or singular-value cutoffs after inspecting the target cohort. *Remediation:* Replace arbitrary numeric cutoffs (`sigma_2 > 1e-3`) with noise-envelope exact certificates (`R_opt`, `Phi_{x0, tau}`) or pre-registered holdouts.
3. **Metaphorical Multi-Omics Unification:** Claiming transcriptomics, proteomics, and metabolomics "form a unified sheaf/manifold" without an explicit restriction map and gluing residual. *Remediation:* Compute an explicit cross-modal gluing/intertwining operator (`audit_continuum_probes.py` / `AUDIT-007R`) and test against shuffled-donor and uncoupled-dynamics nulls.
4. **Conflating In-Silico Identifiability with Clinical Proof:** Citing a verified algebraic proof on idealized inputs as wet-lab validation. *Remediation:* Tag every table row with `exact` / `sampled` / `anchor` and an explicit `not_shown` column.
5. **Silent Failure Under Optimization or Malformed Assay Inputs:** Using bare `assert`s to guard spectra normalization or accepting `NaN`/`bool`/unreduced fractions in assay pipelines. *Remediation:* Enforce R1–R4 fail-closed parsing (`aletheia audit-check`).

---

## 5. Quickstart Workflow

```bash
# 1. Scaffold a biology expedition workspace
aletheia init ./my-bio-expedition --domain biology

# 2. Enforce R1-R4 hygiene, zero bare asserts, and exact/sampled provenance gates
aletheia audit-check ./my-bio-expedition

# 3. Scan logs/drafts for Latch overfitting, missing negative controls, or scope creep
aletheia diagnose ./my-bio-expedition

# 4. Generate & validate a portable Wave 2+ compute manifest for cohort/proteomics sweeps
aletheia handoff ./my-bio-expedition/manifests/next_waves.json --init-template
```

See also: [Domains Rosetta Stone](./README.md) · [Laws & Gates Specification](../spec/LAWS_AND_GATES.md) · [Aletheia Theory](../THEORY.md) · [Cave Expedition Case Study](../evidence/cave-expedition-case-study.md)

---

## 6. Reference Evidence from the Cave Expedition

- **`AUDIT-002` (`VERIFIED`, `exact`, `N1` (outside check: `Foundation-0/cave-expedition#4`, `verification/outside/rulings.json`)):** Scale-invariant `R_opt`, novel-subspace chain $\operatorname{rank}(\Pi_{W^\perp}P\Pi_{W^\perp}) \ge R_{\mathrm{opt}}$, and integer-exact pointwise sharpness wall.
- **`AUDIT-006R` (`VERIFIED`, `N0`, oracle class `certified sufficient condition` for the trace-slack law (outside check: `Foundation-0/cave-expedition#4`, `verification/outside/rulings.json`); the Portal 11 $PGL(2)$ invariants were outside that check):** `project-asma` 3-component trace-slack sensitivity law ($\Delta t^* = 1/360$) + Portal 11 parameter-free $PGL(2)$ Möbius 3-point (`27/19`) & 4-point (`9/7`) cross-ratio invariants (`Foundation-0/project-asma#101`, merged into project-asma `main` as `f2f92ee` on 2026-11-22; project-asma's own label for the study: author self-checked, no in-repo second checker or ledger row, novelty `N0`, `studies/expedition-mobius-ropt/README.md:3`).
- **`AUDIT-014` (`VERIFIED`, `exact` (outside check: `Foundation-0/cave-expedition#4`, `verification/outside/rulings.json`)):** Higher-moment Stieltjes–Hankel `R_H4` and Noise-Annihilating Quartic SOS `Phi_{x0, tau}` lifting `Scan 23848` Mode B & noisy Mode A (`Foundation-0/spectral-inertia`).
- **`AUDIT-005` & `AUDIT-008R` (`VERIFIED`, `exact`): `AUDIT-005` is `N0` for the identity, `N1` for the application; `AUDIT-008R` is `N1`:** Exact Euclidean & nonlinear Bregman/KL two-loop Pythagoras + Fisher–Rao omitted-variable phase boundary (`Foundation-0/continuum#3`).
