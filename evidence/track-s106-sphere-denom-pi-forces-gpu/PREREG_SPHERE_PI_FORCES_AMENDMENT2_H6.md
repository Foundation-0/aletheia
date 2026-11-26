# Preregistration Amendment 2 (`PREREG-S106-AMENDMENT2-H6`: 4D Hypersphere Foliation & Hopf-Fiber Weight Arrangement)

- **Status:** `LOCKED_PREREGISTRATION_AMENDMENT_2` *(auto-captured & locked per `SOP-12` 2026-11-25; `PREREG-S106` `ac3e6211...` and `AMENDMENT1-H5` `c83910a0...` remain 100% immutable)*
- **Originating PI Insight:** If 4th dimension = proper time = data flow, map out how the 4th dimension is geometrically arranged inside a 4D hypersphere ($S^3 \subset \mathbb{R}^4$) and arrange model weights & compute flow to follow that 4D hypersphere structure directly.
- **Exact Stage-B Mathematical Foliations of $S^3$:**
  1. **Polar Slicing Foliation ($x_4 = \cos\psi$, slices $S^2(\sin\psi)$ for $\psi \in (0,\pi)$):** Cross-sectional volume peaks at the equator ($\propto \sin^2\psi$), while **intrinsic slice curvature blows up at BOTH poles** ($\kappa(\psi) \propto 1/\sin^2\psi$ as $\psi \to 0$ input and $\psi \to \pi$ output) — contrasting sharply with standard flat cylindrical transformers ($S^2 \times [0,L]$).
  2. **Hopf Fibration ($S^1 \hookrightarrow S^3 \xrightarrow{\pi} S^2$):** Every 4D vector $x = (z_1, z_2) \in \mathbb{C}^2 \setminus \{0\}$ factors into a base direction $\pi(z_1, z_2) = (2\operatorname{Re}(z_1\bar{z}_2), 2\operatorname{Im}(z_1\bar{z}_2), |z_1|^2 - |z_2|^2)/\|x\|^2 \in S^2$ and a 4th-dimensional periodic phase fiber $e^{i\tau} \in S^1$ ($\pi(e^{i\tau}z) = \pi(z)$ identically, every pair of fibers linked with $\operatorname{Lk}=1$).
  3. **Clifford Torus Foliation ($S^3 = \bigcup_\alpha S^1(\cos\alpha) \times S^1(\sin\alpha)$):** Dual coupled clocks (depth-time poloidal pass × sequence-time toroidal token advance).

## Falsifiable Sub-Hypotheses, Controls & Kill Gates (`H6a`, `H6b`, `H6c`)

- **`H6a` ($S^3$ Depth-Time Foliation Bit Arrangement — Polar Curvature vs. Equatorial vs. Flat Cylinder):**
  - *Hypothesis:* At **strictly identical model-wide mean `exact_bpw`** (`3.00 bpw`), arranging layer bit-budgets along depth-time $\psi_\ell = \frac{\ell + 1/2}{L}\pi$ according to **$S^3$ polar sectional curvature** (higher bits at high-curvature entry/exit poles $\ell \approx 0, L-1$, fewer bits at the flat equator $\ell \approx L/2$, smooth clamped $1/\sin^2\psi_\ell$ or $a + b\cos^2\psi_\ell$ schedule locked on `Qwen2.5-0.5B` ONLY) achieves **$\ge 10\%$ lower held-out mean KL divergence ($\ge 2$ SE)** than BOTH (1) Flat Cylinder (uniform `3.00 bpw`) AND (2) Equatorial Volume ($\propto \sin^2\psi_\ell$) across $\ge 2/3$ blind held-out models (`SmolLM2-360M`, `Qwen2.5-1.5B`, `Qwen2.5-3B`) on Wikipedia + Python texts.
  - *Kill Gate (`FALSIFIED`):* Fails to beat Flat Cylinder by $\ge 10\%$ KL ($\ge 2$ SE) on $\ge 2/3$ held-out models, OR Equatorial $\sin^2\psi_\ell$ beats Polar Curvature.

- **`H6b` (Hopf-Fiber $S^1 \hookrightarrow S^3 \to S^2$ Quantization & Zero-Cost Data-Flow Weight Arrangement):**
  - *Hypothesis (Part 1 — Hopf Quantizer):* Factoring 4D weight blocks via the Hopf fibration (`EQ(S^2)` base patch + denominator-$\pi$ $S^1$ fiber phase $e^{i\tau}$ + radial gain) achieves exact power-of-2 LUT-free indexing within `0.15 dB` of direct `EQ(S^3)` while enabling $O(1)$ phase-equivariant block rotation (`e^{i\Delta\tau}` shifts only the fiber index!).
  - *Hypothesis (Part 2 — Zero-Cost Weight Arrangement):* Re-ordering MLP intermediate channels (`down_proj` columns paired with `gate_proj`/`up_proj` rows — **`0` extra bits and `0` runtime FLOPs!**) along a **Hopf-base / data-flow-covariance space-filling order** before grouping into 4D/8D/16D hypersphere blocks cuts held-out quantization KL by **$\ge 5\%$ ($\ge 2$ SE)** vs. both native weight order and random column permutation across $\ge 2/3$ held-out models at `2.0` & `3.0 bpw`.
  - *Kill Gate (`FALSIFIED`):* Hopf/data-flow channel arrangement fails to beat native order and random-permutation null by $\ge 5\%$ KL ($\ge 2$ SE) on $\ge 2/3$ held-out models.

- **`H6c` (Native Hopf-Fiber $S^3$ Forward-Flow Architecture — Matched-Param Micro-Model Pilot):**
  - *Hypothesis:* Training a matched-parameter (`~10M` params, identical token budget & optimizer, `WEIGHTS=0` post-eval) micro-language-model whose hidden blocks evolve via **Hopf-fiber / quaternionic $SU(2)$-coupled $S^3$ transitions** (preserving hypersphere norm with explicit base-$S^2$ + fiber-$S^1$ phase coupling) achieves either (a) lower held-out validation NLL OR (b) $\ge 15\%$ lower post-training 3-bit quantization KL degradation than an identically sized standard flat-residual transformer baseline.
  - *Controls:* Matched-param standard RoPE+RMSNorm transformer trained on identical seeds/tokens/compute (`CS-08` strict parity).
  - *Kill Gate (`FALSIFIED`):* Worse validation NLL AND fails to cut 3-bit quantization KL degradation by $\ge 15\%$.
