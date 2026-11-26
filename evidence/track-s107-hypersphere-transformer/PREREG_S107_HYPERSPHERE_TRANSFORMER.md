# Preregistration Protocol (`PREREG-S107`): Native 4D Hypersphere-Transformer Architecture Tracks (`H7a`, `H7b`, `H7c`)

- **Protocol ID:** `PREREG-S107-NATIVE-HYPERSPHERE-TRANSFORMER`
- **Status:** `LOCKED_PREREGISTRATION` *(auto-captured & locked per `SOP-12`, 2026-11-25; independent of immutable `PREREG-S106` `ac3e6211...`, `AMENDMENT1-H5` `c83910a0...`, and `AMENDMENT2-H6` `b676cc55...`)*
- **Hardware Envelope & Compute Discipline (`CS-08` Strict Parity):** Single NVIDIA RTX 3080 (`8 GiB` VRAM, `mlos gpu-lease --mode train`, `mlos stamp-run --zone B`, `HF_HUB_OFFLINE=1`, `WEIGHTS=0` inside `expedition/`). Every arm within a track is matched to **$\le 0.5\%$ total parameter count AND $\le 1.0\%$ training FLOPs per token**, identical tokenizer/byte stream, identical data order, identical wall-clock/token budget, and **$\ge 3$ fixed seeds (`42, 137, 2026`)** evaluated on strictly held-out multi-domain corpora (Wikipedia prose, Python source code, classical Arabic `S92` treatises, and structured `ABIOS`/JSON agent traces).
- **Mandatory Law-4 `N0` Prior-Art Anchors (Zero False `N2` Claims):**
  1. **Standard Pre-Norm + RoPE + SwiGLU Transformer** (Touvron et al. / Qwen2.5 baseline).
  2. **`nGPT` (Normalized Transformer on the Unit Hypersphere)** — Loshchilov et al., Oct 2024 (unit-norm embeddings, hidden states, and weight rows with learnable spherical interpolation eigen-learning rates $\alpha_A, \alpha_M$). Any hypersphere claim MUST beat or clearly separate from `nGPT` on its declared axis to claim `N1`/`N2`; matching `nGPT` alone is graded `N0`.
  3. **Standard Flat-Residual Looped Transformer** (Dehghani et al. Universal Transformer / Thinking Machines `Inkling-2-Mini` `inkling2_loop` baseline: pre-layers + shared looped core × $R$ passes + suffix layers).

---

## Track `H7a` (`EXP-Q08a`): Non-Cylindrical $S^3$-Foliated Capacity Allocation During Training

### Stage-B Geometric Formulation
A standard transformer is a **flat cylinder** $S^{d-1} \times [0, L]$ with uniform MLP width $d_{\text{ff}}(\ell) = d_{\text{ff}}$ and uniform head allocation across every layer $\ell \in \{0, \dots, L-1\}$. Foliating a 4D hypersphere $S^3 \subset \mathbb{R}^4$ by polar angle $\psi_\ell = \frac{\ell + 1/2}{L}\pi \in (0, \pi)$ produces two sharply opposite geometric density profiles:
- **Equatorial Volume Profile:** cross-sectional 2-sphere area scales as $w_{\text{eq}}(\psi_\ell) \propto \sin^2\psi_\ell$ (widest middle layers, narrow entry/exit poles).
- **Polar Sectional-Curvature Profile:** intrinsic slice curvature scales as $\kappa(\psi_\ell) \propto 1/\sin^2\psi_\ell$ (clamped smoothly to $w_{\text{pol}}(\psi_\ell) = a + b \cos^2\psi_\ell$ with $a, b > 0$ fixed a priori at contrast ratio $w_{\max}/w_{\min} = 2.0$, highest capacity at input/output poles $\ell \approx 0, L-1$, leanest at the middle equator $\ell \approx L/2$).

### Arms (Matched Total Params `~15M` $\pm 0.5\%$ & Matched Training FLOPs $\pm 1.0\%$, $L = 12$ Layers)
1. **Control A (`Cyl-Std`):** Standard Pre-Norm + RoPE, uniform width across all 12 layers.
2. **Control B (`Cyl-nGPT`):** `nGPT` unit-hypersphere normalized transformer, uniform width across all 12 layers.
3. **Arm 1 (`S3-Polar-Std` / `S3-Polar-nGPT`):** Polar-curvature $w_{\text{pol}}(\psi_\ell) \propto a + b \cos^2\psi_\ell$ width profile ($2:1$ pole-to-equator MLP/attention capacity ratio, exact param & FLOP budget conserved).
4. **Arm 2 (`S3-Equatorial-Std` / `S3-Equatorial-nGPT`):** Equatorial volume $w_{\text{eq}}(\psi_\ell) \propto a + b \sin^2\psi_\ell$ width profile ($2:1$ equator-to-pole ratio, exact param & FLOP budget conserved).
5. **Adversarial Null (`S3-Permuted`):** Exact same multiset of 12 layer widths as `S3-Polar`, randomly permuted across depth $\ell$ (separates *geometry along depth-time* from mere *width heterogeneity*!).

### Pass & Kill Gates (`H7a`)
- **Primary Metrics:** Held-out validation Bits-Per-Byte (`BPB`, mean $\pm$ SE across 3 seeds) AND post-training 3-bit PTQ KL degradation ($\Delta\text{KL}_{3\text{b}}$).
- **`CONFIRMED`:** Either `S3-Polar` OR `S3-Equatorial` beats BOTH its uniform cylinder control (`Cyl-Std`/`Cyl-nGPT`) AND the permuted-width adversarial null (`S3-Permuted`) by **$\ge 1.5\%$ relative BPB reduction ($\ge 2$ SE)** OR **$\ge 15\%$ lower 3-bit PTQ KL degradation ($\ge 2$ SE)** at no worse unquantized BPB.
- **`FALSIFIED`:** Neither polar nor equatorial foliation beats both flat cylinder and permuted-width null across seeds (proving flat cylinder or arbitrary heterogeneity suffices).

---

## Track `H7b` (`EXP-Q08b`): Non-Abelian $SU(2) \cong S^3$ / Hopf-Coupled Positional Attention vs. 2D Abelian $S^1$ RoPE

### Stage-B Geometric Formulation
Standard RoPE pairs adjacent coordinates $(x_{2k}, x_{2k+1}) \in \mathbb{R}^2 \cong \mathbb{C}$ and rotates each 2D plane independently by an **Abelian** $U(1) \cong S^1$ phase $e^{i t \theta_k}$: commuting rotations with zero inter-plane coupling.
Grouping every 4 head coordinates into a unit quaternion / $\mathbb{C}^2$ spinor $q_k = (z_1, z_2) \in \mathbb{H} \cong \mathbb{R}^4$ lifts positional coupling to the **non-Abelian** Lie group $SU(2) \cong S^3$ via the **Hopf Fibration** $S^1 \hookrightarrow S^3 \xrightarrow{\pi} S^2$:
$$q_k(t) = L\big(u_{\text{seq}}(t)\big)\; q_k\; R\big(v_{\text{depth}}(\ell)\big), \qquad u_{\text{seq}}(t) = \exp\!\big(t\, \theta_k\, \hat{n}_k\big) \in SU(2),$$
where right multiplication by $e^{i\tau_\ell} \in S^1$ rotates strictly along the **Hopf fiber** (preserving the $S^2$ base projection $\pi(q_k e^{i\tau}) = \pi(q_k)$ identically), while left multiplication by $u_{\text{seq}}(t) \in SU(2)$ advances along a **non-Abelian 3-axis sequence trajectory** coupling the 4D block!
- **Explicit Law-5 Check (Relative-Position Property):** Left multiplication $Q'(t) = U(t) Q$, $K'(s) = U(s) K$ satisfies $\langle Q'(t), K'(s) \rangle_{\mathbb{R}^4} = \langle Q, U(t)^{-1} U(s) K \rangle$. When $U(t) = \exp(t \Omega_k)$ for a single skew generator $\Omega_k$ per 4D block, $U(t)^{-1} U(s) = \exp((s-t)\Omega_k)$ is **exact relative position**, while coupling two non-commuting generators (sequence-time $\Omega_k$ × depth/content axis $\Xi_k$) breaks commutativity intentionally via Baker–Campbell–Hausdorff curvature $[\Omega_k, \Xi_k] \neq 0$! We test BOTH the pure relative-position $SU(2)$ quaternion rotation AND the non-commuting content/depth-coupled Hopf rotation explicitly!

### Arms (Matched Params `~15M`, Matched FLOPs, Context $T_{\text{train}} = 512$, Evaluated at $T \in \{512, 1024, 2048\}$)
1. **Control A (`RoPE-Std`):** Standard 2D Abelian $S^1$ RoPE (Pre-Norm).
2. **Control B (`RoPE-nGPT`):** `nGPT` hypersphere transformer with standard 2D RoPE.
3. **Arm 1 (`Quat-SU2-Rel`):** Exact relative-position 4D $SU(2)$ quaternion rotation (`u_seq(t)` fixed axis per 4D block, zero extra parameters).
4. **Arm 2 (`Hopf-SU2-Coupled`):** Full Hopf-fiber $S^1_{\text{depth}} \times SU(2)_{\text{seq}}$ coupling (left sequence $SU(2)$ rotation + right Hopf $S^1$ phase rotation $\tau_\ell$ + optional gated content-dependent axis tilt $\hat{n}_k(h)$).
5. **Adversarial Null (`Block4-RandOrtho`):** Fixed random static $SO(4)$ mixing matrix per 4D block + standard 2D RoPE (controls for pure 4D linear mixing without non-Abelian positional structure!).

### Pass & Kill Gates (`H7b`)
- **Primary Metrics:** (i) In-distribution val BPB ($T=512$), (ii) zero-shot $2\times / 4\times$ length-extrapolation BPB ($T = 1024, 2048$), and (iii) synthetic **non-Abelian state-tracking / $S_3$ & $A_5$ group-word composition probe** (where Abelian 2D phase rotations have a known algebraic expressivity ceiling!).
- **`CONFIRMED`:** `Hopf-SU2-Coupled` (or `Quat-SU2-Rel`) beats BOTH `RoPE-nGPT` AND `Block4-RandOrtho` by **$\ge 1.5\%$ BPB at $T=512$** OR **$\ge 5\%$ BPB at $2\times/4\times$ length extrapolation** OR **$\ge 15$ percentage points accuracy on non-Abelian group-state tracking** ($\ge 2$ SE across 3 seeds) with no regression on standard BPB.
- **`FALSIFIED`:** No statistically significant gain over `RoPE-nGPT` + `Block4-RandOrtho` across BPB, length extrapolation, and non-Abelian state tracking.

---

## Track `H7c` (`EXP-Q08c`): Clifford-Torus Dual-Clock Looped Core ($S^1_{\text{depth}} \times S^1_{\text{seq}}$) — Direct `Inkling-2-Mini` Loop Bridge

### Stage-B Geometric Formulation & Direct Link to `Track S96` (`Thm 18` `G_3(\rho)` Wall)
In `thinkingmachines/Inkling-2-Mini` (`Track S96`: `24` physical layers = `6` pre + `12` core × **`3` loops** + `6` suffix = `48` effective layers), repeating a flat residual core $h^{(r+1)} = h^{(r)} + F(h^{(r)}; W_{\text{core}})$ faces two concrete mathematical walls proved in `Track S96`:
1. **Loop-Pass Ambiguity & Radial Drift:** Without loop-step coordinates, repeated additive updates drift radially or collapse onto a fixed point when test-time loops scale ($R_{\text{train}} = 3 \to R_{\text{test}} \in \{4, 6, 8\}$).
2. **Per-Pass Quantization Noise Amplification (`Track S96 Thm 18`):** Under quantized core weights (`NVFP4` / `3-bit` / `4-bit`), fresh quantization error accumulates as $G_R(\rho) = 1 + \rho + \dots + \rho^{R-1}$, breaching the `M1-H1` kill gate ($\Delta_3/\Delta_{1,\text{ctrl}} \le 2$) once $\rho > (\sqrt{5}-1)/2 \approx 0.618$ even when the loop is strictly contractive ($\rho < 1$).

**Clifford-Torus $S^3$ Looped Core Construction:**
Place the looped core natively on the hypersphere $S^{d-1}$ with a **Clifford-Torus dual clock** $(e^{i\phi_r}, e^{i\theta_t}) \in S^1_{\text{depth}} \times S^1_{\text{seq}} \subset S^3$:
- **Geodesic Spherical Loop Step (`SLERP` / Cayley-normalized update):**
  $$h^{(r+1)} = \operatorname{Norm}\!\Big(\cos(\alpha_r)\, h^{(r)} + \sin(\alpha_r)\, \operatorname{Norm}\!\big(\mathcal{R}_{\text{Hopf}}(\phi_r)\, F(h^{(r)}; W_{\text{core}})\big)\Big),$$
  where $\phi_r = \frac{2\pi r}{R}$ (denominator-$\pi$ exact turn fraction $r/R \in \mathbb{Q}/\mathbb{Z}$!) rotates the core output along the **Hopf $S^1$ fiber** on loop pass $r$ — giving the shared core an exact, parameter-free **proper-time loop clock** with **strictly bounded unit norm ($\|h^{(r)}\|_2 \equiv 1$ for ALL $r = 1 \dots \infty$)**!

### Arms (Matched Active FLOPs AND Matched Physical Params: `2` pre + `4` core × `R=3` loops + `2` suffix = `16` effective layers vs. `16`-layer unlooped control!)
1. **Control A (`Unlooped-16L`):** Standard non-looped `16`-layer transformer (same effective depth & FLOPs, $2\times$ physical core params — upper-bound anchor!).
2. **Control B (`FlatLoop-Std`):** Standard `Inkling`-style flat-residual looped transformer (`2 + 4×3 + 2`), learned per-pass scalar gate (no hypersphere constraint, no Hopf loop clock).
3. **Control C (`SphereLoop-NoClock`):** `nGPT`-style geodesic spherical looped core WITHOUT the Hopf fiber loop-clock $\mathcal{R}_{\text{Hopf}}(\phi_r)$ (isolates the exact contribution of the Clifford-Torus dual clock!).
4. **Arm 1 (`CliffordTorus-HopfLoop`):** Full geodesic hypersphere looped core WITH denominator-$\pi$ Hopf fiber loop clock $\phi_r = 2\pi r / R$ AND optional adaptive halting gate.

### Pass & Kill Gates (`H7c`)
- **Primary Metrics:**
  1. **Equal-param val BPB** at $R = 3$ vs. `FlatLoop-Std` and `SphereLoop-NoClock` (plus gap closed toward `Unlooped-16L`!).
  2. **Zero-shot Test-Time Loop Extrapolation ($R_{\text{test}} \in \{4, 6, 8\}$):** Val BPB stability and algorithmic reasoning (multi-hop arithmetic / parity / bracket depth) without catastrophic divergence.
  3. **`Track S96` `M1-H1` Quantized Loop-Drift Gate (`3-bit` & `4-bit` core quantization):** Measure $\Delta_3 / \Delta_{1,\text{ctrl}}$ and held-out KL degradation on `CliffordTorus-HopfLoop` vs. `FlatLoop-Std`!
- **`CONFIRMED`:** `CliffordTorus-HopfLoop` beats BOTH `FlatLoop-Std` AND `SphereLoop-NoClock` by **$\ge 2\%$ lower val BPB at $R=3$** OR **eliminates test-time divergence at $R_{\text{test}}=6$ ($\ge 10\%$ better BPB/accuracy)** OR **cuts 3-bit/4-bit loop-drift ratio $\Delta_3/\Delta_{1,\text{ctrl}}$ by $\ge 20\%$ ($\ge 2$ SE across 3 seeds)** without hurting unquantized BPB.
- **`FALSIFIED`:** Fails to beat `FlatLoop-Std` and `SphereLoop-NoClock` across all three axes (in-dist BPB, $R_{\text{test}}$ extrapolation, and `M1-H1` quantized loop drift).

---

## Law-4 Honest Novelty Boundary
- Matching `nGPT` alone or standard looped transformers alone is strictly **`N0`**.
- Demonstrating reproducible, seed-replicated, FLOP-and-parameter-matched separation beyond `nGPT` + adversarial nulls (`S3-Permuted`, `Block4-RandOrtho`, `SphereLoop-NoClock`) on `H7a`, `H7b`, or `H7c` qualifies as **`N1`** (or **`N2`** only after full-text prior-art clearance against contemporary 2025–2026 hypersphere/quaternionic/looped transformer literature).
