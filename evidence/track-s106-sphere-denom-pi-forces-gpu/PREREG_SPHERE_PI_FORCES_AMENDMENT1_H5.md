# Preregistration Amendment 1 (`PREREG-S106-AMENDMENT1-H5`: Data-Flow Proper-Time Metric Sphere)

- **Status:** `LOCKED_PREREGISTRATION_AMENDMENT_1` *(auto-captured & locked per `SOP-12` 2026-11-25; parent protocol `PREREG-S106` `ac3e62116bc4841320d2c713787c23568beed1ae738bf9b284b7f0c2a118d72a` remains 100% immutable and unmutated)*
- **Originating PI Insight:** A model has zero intrinsic clock when frozen; its 4th dimension ("proper time" $\tau$) advances strictly as data flows through its parameters (depth-time $\ell = 0 \to L$ on the `RMSNorm` activation hypersphere $S^{d-1}$, sequence-time causal light cone $t = 1 \to T$, and Fisher–Rao information arc length).
- **Exact Stage-B Operator Translation:**
  - Static quantization treats $W$ as a frozen Euclidean cloud ($\|W - \hat{W}\|_F^2$).
  - When data flows ($y = W x(\tau)$), input activation flow $D_{\text{flow}} = \operatorname{diag}(\sqrt{\mathbb{E}[x_j(\tau)^2]})$ warps the sphere's metric: $\mathbb{E}[\|(W-\hat{W})x\|_2^2] \approx \|(W-\hat{W})D_{\text{flow}}\|_F^2$.
  - **Zero-Extra-Bit `Flow-SphereMap`:** Map the **data-flow-weighted tensor** $W D_{\text{flow}}$ back to an isotropic sphere before hypersphere quantization ($W_{\text{flow-sphere}} = D_r^{-1} (W D_{\text{flow}}) D_c^{-1} H_{64}$), folding $D_{\text{flow}}^{-1}$ directly into the existing FP16 column vector $D_c$ (**`0.0000` additional bits** vs. static `SphereMap`!).
  - **Zero-Dataset Proper-Time Excitation (White-Noise Flow):** Measure $D_{\text{flow}}$ using ONLY synthetic random-token forward passes (zero external dataset!) so we isolate the model's *intrinsic* causal flow geometry vs. real-text calibration.

## Falsifiable Sub-Hypotheses & Kill Gates (`H5a`, `H5b`)

- **`H5a` (Zero-Extra-Bit White-Noise `Flow-SphereMap` vs. Static `SphereMap`):**
  - *Hypothesis:* At identical `exact_bpw` (`2.0`, `3.0 bpw` on $E_8$/$A_{16}$), replacing static `SphereMap` ($W$) with zero-dataset white-noise **`Flow-SphereMap` ($W D_{\text{flow}}^{\text{noise}}$)** cuts held-out **end-to-end KL divergence by $\ge 15\%$ ($\ge 2$ SE)** across $\ge 2/3$ blind held-out models (`SmolLM2-360M`, `Qwen2.5-1.5B`, `Qwen2.5-3B`) on both Wikipedia prose and Python source — even if plain static Euclidean weight SNR $\|W-\hat{W}\|_F$ degrades!
  - *Controls:* (1) Static `SphereMap` (frozen-time baseline, identical `exact_bpw`), (2) `Flow-SphereMap` with real Wikipedia calibration text (upper-bound anchor), (3) **Adversarial Null:** randomly permuted $D_{\text{flow}}$ vector (same distribution of scales, broken channel alignment!).
  - *Kill Gate (`FALSIFIED`):* Fails to beat static `SphereMap` by $\ge 15\%$ KL ($\ge 2$ SE) on $\ge 2/3$ held-out models, OR fails to beat the permuted-$D_{\text{flow}}$ null.

- **`H5b` (Causal Depth-Time Cone Amplification along $\ell = 0 \to L$):**
  - *Hypothesis:* Injecting an identical normalized perturbation $\|\Delta W_\ell\|_F / \|W_\ell\|_F = \varepsilon$ (and identical `Flow-SphereMap` quantization error) at depth-time $\ell$ produces monotonically larger final-logit KL amplification for early-layer `ffn_down` / attention-output projections than late layers (with causal-cone amplification factor $\ge 2\times$ in the first quartile of depth vs. last quartile across $\ge 2/3$ held-out models), enabling a **depth-time non-uniform bit schedule** (strictly matched mean `exact_bpw`!) that beats uniform depth bits by $\ge 8\%$ KL.
  - *Kill Gate (`FALSIFIED`):* Depth-time KL sensitivity shows no early-layer dominance (or is flat/reversed on $\ge 2/3$ models), OR matched-`bpw` depth-time bit allocation fails to beat uniform depth allocation by $\ge 8\%$ KL.
