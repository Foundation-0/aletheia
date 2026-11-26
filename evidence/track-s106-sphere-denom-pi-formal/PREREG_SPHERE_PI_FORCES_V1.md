# Preregistered Scientific Protocol (`PREREG-SPHERE-PI-FORCES-V1`)

- **Status:** `LOCKED_PREREGISTRATION_V1` *(PI-approved 2026-11-25; immutable SHA-256 logged into `verification/AUDIT_LOG.md` BEFORE any Phase-1/2 execution)*
- **Core Scientific Thesis:** LLM computing gains do not by themselves prove new physical laws — rather, if a **$\pi$-denominated / hypersphere / physical-force mathematical representation** simultaneously (a) simplifies exact symbolic & physical formulations cleanly AND (b) transfers directly into measurable, matched-bitrate silicon computing gains on blind held-out systems, that demonstrates the **representation structure itself carries genuine cross-domain operational value** (Aletheia Law 5).
- **Date:** 2026-11-25
- **Hardware Envelope:** `ahraz` (`i9-11900H` AVX-512, `31 GiB` RAM, RTX 3080 Laptop `8 GiB` CC `8.6` serialized via `mlos gpu-lease --mode train` + `mlos stamp-run --zone B`, `HF_HUB_OFFLINE=1`)
- **Offline Verified Model Suite (`5.36B` total params across 2 independent architectures):**
  - **Development / Parameter-Lock Model ONLY:** Synthetic Gaussian $N(0,1)$ + `Qwen/Qwen2.5-0.5B`
  - **Blind Held-Out Evaluation Suite (ZERO hyperparameter tuning allowed):** `HuggingFaceTB/SmolLM2-360M` (cross-family Llama architecture), `Qwen/Qwen2.5-1.5B`, `Qwen/Qwen2.5-3B`
- **Held-Out Evaluation Corpora (2 domains matching `Moissanite-Labs/siliquant`):** Wikipedia prose + Python source code (evaluated with exact mean KL divergence in nats ± SE against full-precision BF16 logits, plus perplexity and exact weight SNR).

---

## 0. Epistemic Boundary (Law 4 & Law 5 Discipline)

To keep the scientific claims airtight and immune to language smuggling (`CS-03`) or compute/bit leakage (`CS-08`):
- **Tier A (Directly Proven/Falsified in Silicon Computing):** Whether hypersphere measure concentration (`H1`), denominator-$\pi$ equal-sphere-fraction coding (`H2a`), and physical-force variational operators (`H3a–H3c`) deliver statistically significant, matched-exact-`bpw` improvements in **end-to-end LLM KL divergence, weight SNR, throughput (`Gw/s`), and energy (`mJ/tok`)** across unseen models and scales.
- **Tier B (Paired Physics Verification — Direct Test of Representation Generality):** Because an LLM speedup alone does not prove new physical laws, we pair `H2` directly with exact analytical physical testbeds (**3D Gauss/multipole flux on $S^2$** and **Fock–Moser regularized Kepler/Hydrogen $S^3$ wavefunctions**) comparing denominator-$\pi$ `EQ(S^{d-1})` and sphere-unit coordinates ($\operatorname{Vol}(B^d) \equiv 1$) against numerator-$\pi$ angle grids, Cartesian boxes, and standard Lebedev/Gauss–Legendre controls.
- **Strict Bit Accounting (Zero `CS-08` Cheating):** Every reported `exact_bpw` includes **100% of stored bits** — index bits, per-block or row/col FP16 scales (`16(m+n)/(mn)`), shell LUT entries, and codebook storage (amortized honestly over tensor size).

---

## 1. Falsifiable Hypotheses, Controls & Kill Gates

### `H1` — Hypersphere Dimension & Measure Concentration ($S^3 \to S^7 \to S^{15} \to S^{127}$)
- **Hypothesis:** After quadrupole inversion (`SphereMap = Sinkhorn dual_scale + orthogonal block rotation`), real LLM weight blocks concentrate onto thin hyperspherical shells $S^{d-1}$ ($\sigma_R/\mu_R \approx 1/\sqrt{2d}$), so higher-dimensional hypersphere balls ($A_{16}$ on $S^{15}$ and product-ball $A_{16}^8$ on $S^{127}$) strictly dominate lower-dimensional spheres ($S^1, S^3, S^7$) and scalar quantizers in **end-to-end KL divergence** at matched exact `bpw` (`2.0`, `3.0`, `4.5 bpw`) across all 3 held-out models — with per-layer failure sharply predicted by residual post-`SphereMap` excess kurtosis $\kappa_{\text{post}} - 3 > 0.30$.
- **Controls:** (1) Cartesian Lloyd-Max + `SphereMap`, (2) `siliquant`'s current per-32 and per-128 block-scaled $E_8$/$A_{16}$ baselines (counting every scale bit), (3) **Adversarial Null:** randomly permuting weight entries across rows/cols before `SphereMap` (destroying real quadrupole structure).
- **Pass Criteria:**
  - `H1-P1`: On $\ge 2/3$ held-out models (`SmolLM2-360M`, `Qwen2.5-1.5B`, `Qwen2.5-3B`) across both texts at `3.0 bpw`, `SphereMap + A_16/E_8` beats matched-`bpw` per-128 block-scaled `siliquant` by $\ge 10\%$ lower mean KL (at $\ge 2$ SE) OR matches KL at $\ge 0.10\text{ bpw}$ lower bitrate.
  - `H1-P2`: Across layers of each model, $\kappa_{\text{post}} - 3$ correlates with per-layer KL degradation at Spearman $\rho \ge 0.60$.
- **Kill Gate (`FALSIFIED`):** Fails `H1-P1` on $\ge 2/3$ held-out models (testing explicitly whether activation outliers override weight-space `SphereMap` gains in end-to-end KL!).

### `H2` — Denominator-$\pi$ Equal-Sphere-Fraction Representation (`Sphere = 1`, $\pi^{d/2}$ in Denominator)
- **Hypothesis `H2a` (Computing / `siliquant`):** Partitioning $S^{d-1}$ into $K = 2^B$ equal-measure cells of exact fraction $1/2^B$ of $\omega_{d-1} \propto \pi^{d/2}$ (`EQ(S^3)`, `EQ(S^7)` — zero training, zero stored LUT, exact `0..2^B-1` bijection) at ultra-low rates (`1.5–2.5 bpw`) beats numerator-$\pi$ angle grids by $\ge +1.5\text{ dB}$, matches or beats 20-iter trained spherical k-means within `0.10 dB` (with zero codebook storage and zero unused slots), and delivers faster pack/decode than `hampack.py` indexing.
- **Hypothesis `H2b` (Paired Physics Testbed):** On exact analytical physics integrals — (i) 3D Gauss flux & multipole moments ($\ell \le 6$) on $S^2$ and (ii) Fock–Moser regularized 3D Hydrogen/Kepler $S^3$ momentum-space overlaps — denominator-$\pi$ `EQ(S^2)`/`EQ(S^3)` reduces integration & conservation error by **$\ge 3\times$** vs. matched-node numerator-$\pi$ angle grids and Cartesian grids (benchmarked honestly alongside Lebedev / Gauss–Legendre / quasi-Monte-Carlo controls to isolate exact novelty class `N0`/`N1`).
- **Kill Gates (`FALSIFIED`):**
  - `H2a` falsified if closed-form `EQ(S^3)`/`EQ(S^7)` trails trained spherical k-means by $> 0.15\text{ dB}$ OR loses in held-out end-to-end KL to matched-`bpw` Cartesian Lloyd-Max + `SphereMap` at `2.0 bpw`.
  - `H2b` falsified if `EQ(S^2)`/`EQ(S^3)` achieves $< 3\times$ error reduction over matched-node numerator-$\pi$ angle grids on either physical benchmark.

### `H3` — Fundamental-Force Operators Mapped to Model Weights (3 Independent Sub-Hypotheses)
Each sub-hypothesis uses parameters frozen strictly on Synthetic Gaussian / `Qwen2.5-0.5B` and tested blind on the 3 held-out models:
- **`H3a` (Radial Sphere Warp $r \mapsto r^\gamma$ + Zero-Bit Integer Shell-LUT $\rho[m]$):**
  - *Mechanism:* Directly attacks the empirically discovered `28%–54%` longitudinal radial error bottleneck on $E_8$/$A_{16}$ balls with `0.0000` extra bits and `0` runtime transcendentals.
  - *Pass Gate:* At `3.0 bpw` on $\ge 2/3$ held-out models, improves weight SNR by $\ge +0.15\text{ dB}$ on typical layers and $\ge +0.40\text{ dB}$ on $\kappa > 10$ layers **AND** lowers end-to-end mean KL by $\ge 3\%$ (and $\ge 2$ SE) relative to linear `SphereMap + E_8/A_16`.
  - *Kill Gate:* If SNR rises but held-out KL fails to improve (or degrades), log honestly as `PARTIAL (SNR only) / FALSIFIED (KL)`.
- **`H3b` (EM / Hodge Transverse-Weighted Quantization):**
  - *Mechanism:* Weighting tangential angular error $\lambda_\perp \|\delta_\perp\|^2 + \|\delta_\parallel\|^2$ ($\lambda_\perp \in \{2, 4\}$ frozen on `0.5B`) preserves feature direction on $S^{d-1}$ for RMSNorm-adjacent projections.
  - *Pass Gate:* Reduces held-out mean KL by $\ge 3\%$ ($\ge 2$ SE) vs. plain Euclidean MSE selection at identical `exact_bpw` (even if plain weight MSE is slightly worse!).
  - *Kill Gate:* Zero KL improvement or degradation across $\ge 2/3$ held-out models.
- **`H3c` (Gravity + Short-Range Nuclear Yukawa Repulsion $e^{-\mu r}/r$ Spherical Codebooks):**
  - *Mechanism:* Short-range screened repulsion prevents local k-means centroid collapse on $S^3$/$S^7$ at exact power-of-2 sizes ($K = 256, 4096$).
  - *Pass Gate:* Strictly beats both pure spherical k-means ("gravity-only") AND unscreened Coulomb ($1/r$) in held-out weight SNR ($\ge +0.05\text{ dB}$) and mean KL across $\ge 2/3$ held-out models at `2.0–2.5 bpw`.
  - *Kill Gate:* Trails or statistically ties pure spherical k-means (`|ΔKL| < 2 SE`) on $\ge 2/3$ held-out models.

### `H4` — Conjunction & Scale-Transfer Synergy (`H1 + H2 + H3` Combined)
- **Hypothesis:** Combining the winning components of `H1` (`SphereMap` + $S^{15}/S^{127}$), `H2` (Denominator-$\pi$ exact-$2^B$ indexing / sphere-unit scaling), and `H3` (`Power-0.7` radial shell LUT + Hodge transverse weighting) establishes a **strictly Pareto-dominant KL-vs-exact-`bpw` frontier** on all 3 held-out models (`SmolLM2-360M`, `Qwen2.5-1.5B`, `Qwen2.5-3B`) across both texts compared to every individual ablation AND `siliquant`'s current baselines (`A_16` per-128 and `Q4_K_M@16`).
- **Kill Gate (`FALSIFIED`):** Any single component equals or beats the conjunction across $\ge 2/3$ held-out models (anti-bloat rule: keep ONLY what survives ablation!).

---

## 2. Four-Phase Execution Plan

| Phase | Scope & Artifacts | Compute & Guardrails | Exit Gate |
|---|---|---|---|
| **Phase 0: Preregistration Lock** | Finalize hypotheses & kill gates with PI -> freeze SHA-256 of this protocol & log into `verification/AUDIT_LOG.md` | `0` GPU | Signed SHA-256 lock before any held-out eval |
| **Phase 1: Pilot + Physics + Exact Formal Core** | (a) Lock frozen universal constants on Gaussian + `Qwen2.5-0.5B`; (b) Run `H2b` physics $S^2$ Gauss-flux & $S^3$ Fock–Moser Kepler/Hydrogen benchmarks; (c) Build pure-$\mathbb{Q}$ oracle + `Lean 4.36.0` proofs for sphere-unit $G(B^d) = \frac{1}{d+2}$, Hodge split $\|\delta\|^2 = \|\delta_\parallel\|^2 + \|\delta_\perp\|^2$, and exact `EQ(S^2)`/`EQ(S^3)` equal-measure invariants | CPU + ~10 min RTX 3080 (`mlos gpu-lease`) | All constants frozen; physics benchmark & Lean proofs compiled `rc=0` |
| **Phase 2: Blind Held-Out RTX 3080 Gauntlet** | Run frozen arms on `SmolLM2-360M`, `Qwen2.5-1.5B`, `Qwen2.5-3B` across Wikipedia + Python texts: exact `bpw`, weight SNR, mean KL ± SE, PPL, pack/decode `Gw/s`, `mJ/tok` (RAPL+NVML), `mlos` Zone-B hardware receipt | ~25 min RTX 3080 (`mlos gpu-lease --mode train` + `stamp-run --zone B`, `WEIGHTS=0`) | Raw JSON results + receipts written with zero post-hoc tuning |
| **Phase 3: Cross-Family Audit & Release** | Independent multi-family council audit (e.g. Grok 4.7 + Claude Code + GLM 5.3) verifying `0` `CS-08` bit leakage, `0` snooping, honest `CONFIRMED`/`PARTIAL`/`FALSIFIED` verdicts -> ship verified winners to `Moissanite-Labs/siliquant` & `Foundation-0/aletheia` + Rule-8 `aletheia-corpus` sync | CPU + `@council-router` | `VERIFIED` audit + Ready PR(s) |
