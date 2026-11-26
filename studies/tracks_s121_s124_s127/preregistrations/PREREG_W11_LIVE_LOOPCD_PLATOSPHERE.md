# PREREG-W11-LIVE: `LoopCD-Hidden` + Palindromic Strang $SU(2)$ Guidance & *Plato's Key* × `Portal x/π` `SphereMap` Procrustes Live RTX 3080 Probes

- **Protocol ID:** `PREREG-W11-LIVE-LOOPCD-PLATOSPHERE-V1`
- **Status:** `LOCKED_PRE_RUN` (SHA-256 computed and recorded strictly prior to RTX 3080 Zone-B execution)
- **Executable Harness:** `track-s121-wave11-loopcd-plato/run_w11_live_loopcd_platosphere.py`
- **Theoretical Companion (Frozen):** `track-s121-wave11-loopcd-plato/verify_loopcd_sphere_geometry.py` (`SHA-256: 64afff8c59968e2375a158b6959bb98ae605a4f813722d8f6f29e1c361bfbdb1`)
- **Hardware & Determinism:** Single NVIDIA RTX 3080 Laptop GPU (`GA104M`, `sm_86`, `8 GiB`), executed strictly under `mlos gpu-lease --mode train` + `mlos stamp-run --zone B --require-gpu`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `WEIGHTS = 0` inside `expedition/`.
- **Novelty Classification (Law 4):** `N1` (controlled live empirical tests of Wave-11 `EXP-Q25a`/`EXP-Q26b` and `EXP-Q25b`/`EXP-Q26a` geometric operators against explicit baselines & nulls on real frozen weights).

---

## 1. Probe A (`EXP-Q25a` / `EXP-Q26b`): Zero-Training `LoopCD-Hidden` & Palindromic Strang $SU(2)$ Guidance on Converged `HoloSphere-V3` (`15.23M`)

- **Frozen Model Under Test (Read-Only):** Converged flagship `Row3_HoloSphereV3_UnifiedCellOp` checkpoint (`holosphere_v3_15m_flagship.pt`, `SHA-256: 0e0c5f3df6e791b884d06ccbf9fb263f97d83703549aee8b389c35cbfa5a9ca2`, `L = 6, D = 512, H = 16`, `0` input-embedding params, held-out `T=8192 BPB = 2.5832`).
- **Held-Out Evaluation Set:** Strictly SHA-256-disjoint `eval.bin` (`2.93 MB`, `SHA-256: 31fd132d888a21ecebe9e907b6c4b82e3e68e42b5a29e2839584447dcca631a0`), evaluated on `T=2048` (tail-512, `16` chunks) and `T=8192` (tail-1024, `8` chunks).
- **Experimental Arms:**
  1. **Full-Depth `LoopCD-Hidden` (`L = 6`):** $h' = \mathrm{unit\_norm}(h_6 + \omega (h_6 - h_k))$ before `lm_head`, sweeping $k \in \{1, 2, 3\}$ and $\omega \in \{0.0, 0.1, 0.25, 0.5, 0.75, 1.0\}$.
  2. **`CS-08` Half-Depth FLOP Parity (`L_trunc in {3, 4}`):** Apply $h' = \mathrm{unit\_norm}(h_{L_{\mathrm{trunc}}} + \omega (h_{L_{\mathrm{trunc}}} - h_k))$ for $k \in \{1, 2\}$ and $\omega \in \{0.0, 0.1, 0.25, 0.5, 0.75, 1.0\}$ against unguided $L=6$ and unguided $L_{\mathrm{trunc}}$.
  3. **Palindromic Strang $SU(2)$ Cayley Guidance vs Reversed Left-Ordered Control:** On real layer-$k$ ($w_k$) and final-layer ($w_5$) `w_su2` vectors from `holosphere_v3_15m_flagship.pt`, measure:
     - **(i) Live Strang BCH Cancellation Ratio:** Ratio of squared quaternion chordal error $\|C(w_{\mathrm{lin}}) - C(w_{\mathrm{left}})\|^2 / \|C(w_{\mathrm{lin}}) - C(w_{\mathrm{right}})\|^2$ for $w_{\mathrm{lin}} = (1+\omega)w_5 - \omega w_k$ at $\omega \in \{0.25, 0.5, 1.0\}$.
     - **(ii) Held-Out BPB & Top-1 Byte Accuracy:** Applying $w_{\mathrm{lin}}$, right-ordered $w_{\mathrm{right}}$, and reversed left-ordered $w_{\mathrm{left}}$ inside layer 5 (`omega in {0.0, 0.1, 0.25, 0.5, 0.75, 1.0}`).

### Literal Pre-Registered Gates (Probe A)
- **`W11-A1` (Live Strang BCH Cancellation on Real Weights):** On real trained `HoloSphere-V3` `w_su2` vectors, `w_lin` approximates right-ordered $U_5(U_k^\dagger U_5)^\omega$ strictly closer than reversed left-ordered $(U_k^\dagger U_5)^\omega U_5$ by **`>= 5.0x`** in mean squared chordal error across all tested $(k, \omega > 0)$.
- **`W11-A2` (Zero-Training `LoopCD-Hidden` / $SU(2)$ Guidance Held-Out Gain):**
  - **`CONFIRMED`:** At least one $(k, \omega > 0)$ configuration strictly improves held-out `T=2048`/`T=8192` BPB by **`<= -0.010 BPB`** OR improves truncated-depth (`L=3` or `L=4`) BPB by **`<= -0.050 BPB`** without degrading top-1 accuracy.
  - **`PARTIAL`:** `W11-A1` passes AND positive guidance produces measurable improvement on truncated depth or top-1 accuracy, while full-depth `L=6` BPB gain is `< 0.010 BPB` (or non-looped residual networks differ from looped architectures).
  - **`FALSIFIED`:** Neither full-depth nor truncated-depth `LoopCD-Hidden` / $SU(2)$ guidance improves BPB or top-1 accuracy at any $\omega > 0$ (all $\omega > 0$ strictly worse than $\omega = 0.0$).

---

## 2. Probe B (`EXP-Q25b` / `EXP-Q26a`): *Plato's Key* × `Portal x/π` `SphereMap` Procrustes Transfer on Offline Base LLMs

- **Offline Models Under Test (Strict `HF_HUB_OFFLINE=1` Local Cache):**
  - `Qwen/Qwen2.5-0.5B` (`d = 896`, `L = 24`)
  - `Qwen/Qwen2.5-1.5B` (`d = 1536`, `L = 28`)
  - `HuggingFaceTB/SmolLM2-360M` (`d = 960`, `L = 32`)
  - Pairs tested: (1) Cross-scale within-family `Qwen2.5-1.5B -> Qwen2.5-0.5B` and `Qwen2.5-0.5B -> Qwen2.5-1.5B`; (2) Cross-family `Qwen2.5-1.5B -> SmolLM2-360M` and `SmolLM2-360M -> Qwen2.5-0.5B` (and reverse where shared facts permit).
- **Deterministic Subject-Disjoint Factual Recall Suite:** `>= 120` unique-subject facts across 4 relations (`capitals`, `elements`, `authors`, `geography/planets`), split strictly by subject (`70%` train / `15%` val / `15%` test, seeded `seed = 20261125`).
  - Only facts independently recalled by BOTH donor and recipient on direct greedy generation are used for swap training/validation/testing; facts recalled by donor ONLY are routed to the **Dark-Memory Recovery** evaluation (qualified as dark memory iff recipient recalls the fact under a 3-shot in-context prompt or paraphrase prompt).
- **Maps Compared Head-to-Head at Validation-Optimal Swap Layers $(\ell_A^*, \ell_B^*)$:**
  1. **`Frob_Procrustes` (*Plato's Key* baseline):** $\hat{z}_B = \mu_B + s_{\mathrm{Frob}} R(z_A - \mu_A)$, $s_{\mathrm{Frob}} = \|\tilde{Z}_B\|_F / \|\tilde{Z}_A\|_F$.
  2. **`OLS_Procrustes` (Radial Shell-Shrinkage Diagnostic):** $\hat{z}_B = \mu_B + s_{\mathrm{OLS}} R(z_A - \mu_A)$, $s_{\mathrm{OLS}} = \operatorname{tr}(\Sigma) / \|\tilde{Z}_A\|_F^2$.
  3. **`ShellNorm_Procrustes` (Exact Recipient Shell-Radius Restoration, No Quadrupole Equalization):** $\hat{z}_B = \mu_B + \bar{r}_B \frac{R(z_A - \mu_A)}{\|R(z_A - \mu_A)\|_2 + \epsilon}$.
  4. **`SphereMap_Quadrupole_Procrustes` (`Portal x/π` Treatment):** Per-channel std quadrupole equalization $D_A^{-1}(z_A - \mu_A) / \| \cdot \|_2 \to R_{\mathrm{sph}} \to D_B \to$ exact recipient shell-radius restoration $\bar{r}_B$.
  5. **Controls:** `Self_Swap` upper bound, `Random_Orthogonal` null, `Shuffled_Pair` null, plus **SVD Rank Curve** $r \in \{16, 64, 128, 256, \mathrm{full}\}$!

### Literal Pre-Registered Gates (Probe B)
- **`W11-B1` (*Plato's Key* Replication & Null Separation):** Across tested model pairs, `Frob_Procrustes` achieves test swap transfer accuracy strictly **`>= +15.0 pp`** above BOTH `Random_Orthogonal` and `Shuffled_Pair` nulls (nulls `<= 5.0%`), replicating *Plato's Key* on offline `0.36B–1.5B` models.
- **`W11-B2` (`Portal x/π` Radial Shell-Shrinkage Prediction):** `OLS_Procrustes` exhibits strictly lower scale ($s_{\mathrm{OLS}} < s_{\mathrm{Frob}}$) and equal-or-lower transfer accuracy than `Frob_Procrustes` / `ShellNorm_Procrustes`.
- **`W11-B3` (`Portal x/π` Quadrupole `SphereMap` Procrustes vs Plain `Frob_Procrustes`):**
  - **`CONFIRMED`:** `SphereMap_Quadrupole_Procrustes` beats `Frob_Procrustes` by **`>= +3.0 pp`** mean test transfer accuracy across pairs OR unlocks strictly **`> 18.0%`** of recipient dark memories while outperforming `Frob_Procrustes`.
  - **`PARTIAL`:** `W11-B1` & `W11-B2` pass and `SphereMap_Quadrupole_Procrustes` matches `Frob_Procrustes` within `[-2.0, +3.0] pp` (or wins on a subset of pairs/dark memories).
  - **`FALSIFIED`:** `SphereMap_Quadrupole_Procrustes` trails `Frob_Procrustes` by `> 2.0 pp` mean test transfer accuracy (showing isotropic quadrupole whitening destroys functional key geometry relative to raw Frobenius $O(d)$ rotation).
