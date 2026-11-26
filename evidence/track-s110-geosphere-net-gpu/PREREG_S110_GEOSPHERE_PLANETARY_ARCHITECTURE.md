# Preregistration Protocol (`PREREG-S110`): "Geosphere-Net" — Coupled Multi-Shell Geophysical Architecture (`H10a`, `H10b`, `H10c`)

- **Protocol ID:** `PREREG-S110-GEOSPHERE-PLANETARY-ARCHITECTURE`
- **Status:** `LOCKED_PREREGISTRATION` *(auto-captured & locked per `SOP-12`, 2026-11-25; extends `PREREG-S106..S109` & re-enters merged `Track S33`, `Track S43` [`math0#36`], `Track S50` [`aletheia#55`], `Track S96`, & `Track S106`)*
- **Originating PI Insight:** Build a holistic concentric spherical architecture modeled after Earth's coupled multi-timescale physical systems — gravity, core geodynamo magnetism, 3-shell inner core / viscoplastic mantle / tectonic plates, underground aquifers, liquid ocean currents, geothermal plumes, Earth electrical (telluric / global-circuit) flows, atmospheric thermal currents, and protective ozone/magnetosphere shielding.
- **Anti-`CS-03` / Anti-Kitchen-Sink Law-5 Discipline (Mandatory):**
  - **Zero Poetic Metaphor Allowed:** Every geophysical shell MUST map to an **exact, coordinate-free mathematical operator** with a defined conservation law or threshold dynamics.
  - **Strict Earn-Your-Keep Pruning Rule:** Every shell is first ablated **individually** at strictly matched total params (`15M ± 0.5%`) and matched training/inference FLOPs (`±5%`) (`H10a`). Any shell that fails to clear $\ge 2$ SE on its declared axis is **pruned** before full coupled composition (`H10b`). No dead-weight mechanisms survive on branding alone!
- **Mandatory Law-4 `N0` Prior-Art Anchors (Zero False `N2` Claims):**
  1. `nGPT` (Loshchilov et al. 2024) — unit-hypersphere normalized transformer.
  2. Skew-symmetric / orthogonal / Hamiltonian / unitary RNNs & neural ODEs (`Unitary RNN`, `expRNN`, `AntisymmetricRNN`, `Hamiltonian Neural Networks`, `Skew-Symmetric` Cayley layers).
  3. Doubly-stochastic / Sinkhorn / Optimal-Transport attention (`Sinkformer`, Sander et al. 2022).
  4. Multi-timescale recurrent / state-space memory (`Clockwork RNN`, `HiPPO`/`S4`/`Mamba-2`), adaptive-depth routing (`ACT`, `MoD`, `Inkling-2-Mini` looping), and spectral/Lipschitz adversarial defenses.
  - Matching any single prior-art anchor alone is graded strictly **`N0`**. Genuine **`N1`/`N2`** requires proving reproducible **coupled multi-shell synergy** across leave-one-shell-out ablations at matched total params, FLOPs, and wall latency!

---

## Stage-A $\to$ Stage-B Exact Geophysical-to-Operator Dictionary

All 9 Earth systems unify into **4 physical timescales** ($\tau_{\text{core}} \gg \tau_{\text{aquifer}} > \tau_{\text{ocean}} > \tau_{\text{atm}}$) governed by **3 exact mathematical principles** (Norm-Preserving Gyroscopic Rotation, Mass-Conserving Global Transport, and Thresholded Viscoplastic/Dielectric/Spectral Switching):

| Shell / Phenomenon | Exact Physical Law | Exact Stage-B Mathematical Operator | Target Failure Mode |
|---|---|---|---|
| **1. Gravity ($\Phi_{\text{grav}}$)** | Central radial potential & density stratification | Concentric hypersphere radii + `SphereMap` / `Power-γ` radial compression (`PREREG-S106` `H1`/`H3a`); invariant concepts sink to inner high-stiffness shells | Radial outlier blowup & unstratified parameter waste |
| **2. Core Geodynamo Magnetism ($\mathbf{B}$)** | $\nabla \cdot \mathbf{B} = 0$, workless Lorentz force $\mathbf{v} \cdot (\mathbf{v} \times \mathbf{B}) = 0$ | **Skew-symmetric Cayley/gyroscopic loop transport** $\dot{h} = \Omega_{\text{skew}}(h)\, h$ ($\Omega^\top = -\Omega \implies \langle h, \Omega h\rangle \equiv 0$ exact!) paired with dipole global alignment | Loop norm explosion & `Track S96` `G_3(\rho)` drift wall |
| **3. Inner Core / Mantle / Crust (`TerraCore`)** | Rigid core + Bingham viscoplastic mantle ($0 < Y < 1$) + tectonic plates | Frozen zero-language Core ($\mathcal{M} \to \mathcal{M}$) + `Track S43` $\operatorname{Bingham}_{\tau_Y}$ (`<=96`-bit $S^{k-1}$) + `Track S50` Poloidal/Toroidal Hodge split + swappable Stage-2 outer plates (`PREREG-S109` A1/A2) | Monolithic collapse ($Y=0$) vs. Translator-DPI starvation ($Y=1$) |
| **4. Underground Aquifers (Darcy Porous Flow)** | Slow porous percolation $\mathbf{q} = -\frac{K}{\mu}\nabla p$ (low-pass filtration & storage) | **Slow-timescale porous-diffusion state** $s_t = (1 - \alpha_{\text{slow}}) s_{t-1} + \alpha_{\text{slow}} K_{\text{porous}} x_t$ ($\alpha_{\text{slow}} \ll 1$, low-pass filtered beneath surface plates) | Catastrophic forgetting & transient-noise corruption of long memory |
| **5. Liquid Ocean Currents (Thermohaline / Gyres)** | Incompressible surface mass/heat transport ($\nabla \cdot \mathbf{u} = 0$) | **Doubly-stochastic Sinkhorn global redistribution** ($\sum_j T_{ij} = \sum_i T_{ij} = 1$, exact probability-mass conservation across sequence positions!) | Attention-sink collapse & "lost-in-the-middle" retrieval decay |
| **6. Geothermal Energy & Mantle Plumes** | Rayleigh–Bénard buoyancy onset when $Ra > Ra_c$ | **Error/surprise-driven bottom-up compute injection**: when Core residual uncertainty exceeds $Ra_c$, boost loop count $r(p) \in \{1..4\}$ at strict mean budget $\bar{r}=2.0$ (`H8c` Part 1) | Uniform FLOP waste on trivial tokens / starvation on hard steps |
| **7. Telluric & Global Electric Circuit Flows** | Crustal telluric induction, Core $\mathbf{J} = \frac{1}{\mu_0}\nabla\times\mathbf{B}$, & dielectric breakdown ($|\Delta V| > V_b$) | **Exact Kirchhoff/Hodge sparse fast-skip circuit (`Track S33`/`S50`)**: direct Core$\leftrightarrow$Surface skip triggered ONLY when potential gap $|\Delta V| > V_b$ | Sequential propagation lag across multi-pass looped stacks |
| **8. Atmospheric Thermal Currents (Hadley/Jet Streams)** | Fast low-inertia compressible surface circulation | **Fast shallow surface draft/broadcast layer** (`MTP-8` multi-byte/symbol drafting + local mixing at fastest timescale $\tau_{\text{atm}}$) | High inference wall-clock latency on easy surface syntax |
| **9. Ozone Layer & Magnetosphere Shield** | Selective UV absorption ($\lambda < 310\text{ nm}$) & charged-particle Lorentz deflection | **Outer spectral band-pass airlock + `Track S50` Channel-2B state-transport guard + `Track S31` `DPI` norm clamp** strictly outside the plates | Adversarial spikes, prompt injection, & zero-$\Delta W$ yield-wall advection |

---

## Three-Stage Falsifiable Experimental Plan (`H10a`, `H10b`, `H10c`)

### Stage 1 (`H10a` / `EXP-Q11a` — Single-Shell Isolation & Pruning Gate)
Starting from the matched `15M`-param frozen-Core `TerraCore` (`H9d`) / `Clifford-Torus` (`H7c`) baseline (3 seeds `42, 137, 2026`, triple parity `P_total`, `F_train_total`, `F_infer` `±5%`), test **4 orthogonal shell modules individually** against their direct `N0` baselines:
1. **`Shell-Dynamo` (Magnetism):** Skew-symmetric workless Cayley Lorentz loop operator vs. standard residual & `nGPT` geodesic step — *Earn-Keep Gate:* $\ge 15\%$ reduction in `M1-H1` 3-bit loop-drift OR $\ge 5\%$ better $R_{\text{test}}=6$ extrapolation accuracy ($\ge 2$ SE).
2. **`Shell-Hydrosphere` (Aquifers + Ocean Currents):** Dual-timescale porous slow-memory ($\alpha_{\text{slow}}$) + Sinkhorn doubly-stochastic global attention vs. standard softmax attention + equal-param SSM/KV — *Earn-Keep Gate:* $\ge 3\%$ lower long-context retrieval degradation (`lost-in-the-middle` needle-in-haystack at $2\times/4\times$ context) AND lower attention-sink entropy concentration ($\ge 2$ SE).
3. **`Shell-GeothermalElectric` (Plumes + Telluric Breakdown Skip):** Thresholded buoyancy loop boost ($Ra > Ra_c$, fixed mean $\bar{r}=2.0$) + breakdown-triggered fast skip ($|\Delta V| > V_b$) vs. uniform depth & standard dense residual skip — *Earn-Keep Gate:* $\ge 2\%$ lower exact-match error OR $\ge 1.3\times$ lower median wall latency at matched accuracy ($\ge 2$ SE).
4. **`Shell-OzoneMagneto` (Protective Shield):** Outer spectral band-pass + `Track S50` Channel-2B advection clamp + `DPI` norm gate vs. unshielded input boundary — *Earn-Keep Gate:* cuts adversarial/state-poisoning attack success rate (ASR) by **$\ge 60\%$** while keeping clean exact-match degradation **$\le 0.5$ pp**!
- **Strict Pruning Rule:** Any shell failing its Earn-Keep Gate is logged permanently as **`FALSIFIED` / `PRUNED`** in `verification/AUDIT_LOG.md` and EXCLUDED from Stage 2!

### Stage 2 (`H10b` / `EXP-Q11b` — Coupled "Geosphere-Net" Composition & Leave-One-Shell-Out Synergy Proof)
Compose ONLY the Stage-1 surviving shells into **`Geosphere-Net-15M`** (strictly matched `P_total = 15M ± 0.5%`, `F_train_total ± 5%`, `F_infer ± 5%`, 3 seeds, inheriting ALL `PREREG-S109-AMENDMENT1` `CB-1..CB-6`, `§SWAP`, and counterfactual state-patching audit gates!):
- **External Baselines:** `English-CoT-15M` (tied `<= 4k` vocab), `nGPT-15M`, and `Monolithic-Loop-15M`.
- **Mandatory Leave-One-Shell-Out Ablation Matrix:** Remove each surviving shell one at a time (re-allocating its params back to baseline width so `P_total` stays identical!) to test **super-additive cross-shell synergy** vs. simple additive sum of parts.
- **Pass Gate (`CONFIRMED`):** `Geosphere-Net-15M` (1) strictly Pareto-dominates all 3 baselines on the 4-axis tuple `(Regime I+II exact-match acc, wall latency, adversarial ASR, zero-retrain §SWAP drop)` ($\ge 2$ SE), AND (2) every retained shell shows strictly positive leave-one-out degradation ($\ge 1.5$ SE) on at least one primary axis.
- **Kill Gate (`FALSIFIED`):** Full coupled `Geosphere-Net-15M` underperforms its single best Stage-1 component OR loses to `nGPT-15M` / `Monolithic-Loop-15M` at matched total params, FLOPs, and wall latency!

### Stage 3 (`H10c` / `EXP-Q11c` — Exact Pure-$\mathbb{Z}/\mathbb{Q}$ & `Lean 4.36.0` Conservation Certificate — CPU-Only Pre-Gate!)
Before launching Stage 1–2 GPU training, certify the **exact finite-dimensional conservation laws** of the coupled planetary operators in pure-`Init` `Lean 4.36.0` (`0` external imports, `0` floats, `0` `Classical.choice`/`sorryAx`):
1. **Workless Geodynamo Lorentz Isometry:** $\forall \Omega \in \mathbb{Z}^{d \times d}$ skew-symmetric ($\Omega^\top = -\Omega$), $\langle h, \Omega h\rangle = 0$ identically and the exact rational Cayley map $Q = (I - \Omega)(I + \Omega)^{-1}$ satisfies $\|Q h\|^2 = \|h\|^2$.
2. **Oceanic Mass Conservation:** Doubly-stochastic transport preserves total state mass $\mathbf{1}^\top (T x) = \mathbf{1}^\top x$ identically.
3. **Porous Aquifer Contraction & Bingham Yield Partition:** $0 < \alpha < 1$ convex porous update preserves simplex/norm bounds, paired with `Track S43` Bingham $Y \in \{0, 1/4, 1/2, 3/4, 1\}$ phase partition.
4. **Ozone/Channel-2B Shield Monotonicity:** Band-pass/norm airlock strictly bounds worst-case yield-wall advection $\Delta x$ under frozen-weight ($\Delta W = 0$) input perturbations (`Track S50`).

---

## Execution Pipeline
1. **Immediate CPU Pre-Flight (`@council-router`):** Cross-family physics/PDE/systems red-team of `PREREG-S110` (`Grok 4.7` for geophysical/EM/fluid-dynamics fidelity + `Mistral Large 4` for coupled conservation algebra + `Claude` for `CS-08` & pruning rigor, strictly clean `SOP-11` prompts).
2. **Stage 3 (`H10c`) Pure-`Init` Lean `4.36.0` Conservation Cert** can run CPU-only in parallel while RTX 3080 completes `Track S106` (`H1–H6`) $\to$ `PREREG-S107..S109`!
3. **Stage 1–2 (`H10a` $\to$ `H10b`) RTX 3080 Execution** queued cleanly as **`EXP-Q11a..c`** immediately after `EXP-Q10d`!
