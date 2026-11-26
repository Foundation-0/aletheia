# Natural Systems × Exact-Operator Stage-B Synthesis — Portals 1 & 4

**Status:** Stage-B Exact Pure-$\mathbb{Z}/\mathbb{Q}$ Verification Complete (`11/11` Theorems, `8/8` Obstructions Proved, `9/9` Fail-Closed Negative Controls, `n2_claims = 0`, CPU-Only, `0` GPU Touch)  
**Companion Executable Oracle:** `notes/natural_systems_stage_b_2026_11_25/verify_portals_1_4_exact.py`  
- Oracle File SHA-256: `b6cf5fef3f9dad52f2fab56c9278f27c01c61146249c0019a2e70df44fdcc19d` (`1,139` lines, `53,026` bytes)  
- Canonical Payload SHA-256: `c82aa60c28fe55f62f7673b5ba146fbfd736e40d80141c6aa6d11fa837fd76e5` (bit-identical across `-I -B`, `-I -O -B`, and `-I -B -W error`)  
**Roadmap Reference:** `notes/sphere_pi_forces_2026_11_25/LOCK_IN_NATURAL_SYSTEMS_ROADMAP.md` (§3 Portals 1 & 4)  
**Active Architecture Targets:** `Weft-Geosphere` (`PREREG-S111` + `Track S110`), `Track S94`, `Track S95`, `Track S97`, `Track S102`, `Track S83`/`S85`/`S92`, and `Portal B` (`edge_reconstruction` / `vc_sample_compression`)

---

## 0. `OWN_TERMS_FIRST` & Law-2b Steelman (Discipline Guard)

### Law-5 Beyond-Language Discipline (Stage A -> Stage B)
Surface biological nouns ("synaptic homeostasis," "sleep replay," "slime-mold intelligence," "mycelial highways") carry **zero** mathematical transfer value until stripped down to coordinate-, unit-, and radix-free algebraic operators, exact conservation laws, and explicit **failure obstructions** where the biological metaphor breaks under finite-precision or continual-learning constraints. Every claim below follows a strict two-stage pipeline:
1. **Stage A (Noun Stripping):** Discard biological vocabulary; isolate the exact state space, conservation law, update rule, and symmetry group.
2. **Stage B (Exact Pure-$\mathbb{Z}/\mathbb{Q}$ Operator & Obstruction Proof):** Prove the exact rational identity/inequality over $\mathbb{Z}/\mathbb{Q}$ (`0` floats on trust paths, `0` bare `assert`s) AND construct an explicit counterexample witness pinpointing where naive biomimetic transfer **fails**.

### Law-2b Steelman (Why Portals 1 & 4 Matter — and Why Naive Transfer Fails)
- **Steelman for Portal 1 (Homeostasis / Sleep-Wake / Connectome Motifs):** A decoupled fluid-plate continual-learning architecture (`Weft-Geosphere`, `PREREG-S111`) needs an offline consolidation operator that folds accumulated outer `Weft-Smith` micro-harness plates ($d \le 128$) back into stable core weights without forgetting base capabilities, blowing up row concentration $C_{\mathrm{row}}$, or letting multi-night false updates compound (`87.15%` FWER over 20 nights in `Track S94`/`S80`). Isotropic `⧅` dark-mode projection combined with Dale-signed E/I stability clamps provides an exact zero-forgetting, scale-invariant consolidation primitive.
- **Steelman Against Naive Portal 1 Transfer:** Biology uses *anisotropic* per-neuron firing-rate scaling, *subtractive* synaptic pruning, and *global* multiplicative sleep downscaling. In exact algebra over $\mathbb{Q}$, **all three naive biological mechanisms break `Weft-Geosphere` invariants**: subtractive/Bingham pruning spikes $C_{\mathrm{row}}$ past $C_{\max} = 1/2$ (`25/52 -> 1`, `OBSTRUCTION P1-O1`), multiplicative downscaling drives `BlockH4` diffused weights below the `bf16` half-ULP annihilation floor (`1/256`, `OBSTRUCTION P1-O2`), input-side anisotropic scaling shatters the `⧅` dark-mode nullspace (`forgetting^2: 0 -> 36`, `OBSTRUCTION P1-O3`), summing two individually safe plates cancels rows and spikes $C_{\mathrm{row}}$ (`1/2 -> 1`, `OBSTRUCTION P1-O4`), and multiplicative downscaling crosses any unscaled nonzero refusal/yield margin $\tau > 0$ (`OBSTRUCTION P1-O5`).
- **Steelman for Portal 4 (Murray's Law / *Physarum* Conductance / Schur `⧄`):** Zero-backprop flow-adaptive routing over plate-plate conductance graphs ($L(D)\phi = b$) automatically solves minimum-dissipation transport (Thomson's principle = exact Schur complement `⧄` power conservation), satisfies exact Foster resistance conservation ($\sum_e D_e R_{\mathrm{eff}}(e) = |V| - 1$), obeys exact Murray cube-law capacity optimality ($r_0^3 = \sum_i r_i^3$), and converges globally to the shortest-path backbone at $\gamma = 1$ even from a $9\times$ adversarial initialization.
- **Steelman Against Naive Portal 4 Transfer:** Superlinear biological reinforcement ($\gamma = 2$) introduces an exact algebraic separatrix ($D_2/D_1 = (L_2/L_1)^2$) causing **irreversible hysteresis lock-in** onto $2\times$-worse paths (`OBSTRUCTION P4-O1`); selfish congestion routing breaks Rayleigh monotonicity via an exact **Braess `+33.33%` (`+1/3`) latency penalty** (`OBSTRUCTION P4-O2`); and un-floored $\gamma = 1$ *Physarum* prunes the graph down to a tree ($m = n - 1$), which **destroys 100% of single-edge trunk fault tolerance** AND stands at a **`1000.5×` edge-density chasm** below `Portal B` unconditional linear-density edge reconstruction ($m \ge 1000 n_0, \delta \ge 2000$, `OBSTRUCTION P4-O3`).

---

## 1. Verified Anchor Provenance (Primary Disk Receipts)

All empirical and algebraic anchors cited in the bridges below were verified directly against their on-disk certificates and primary reports:

| Anchor Track | Primary Role in This Synthesis | Verified Key Invariant(s) | Certificate File SHA-256 (16-hex) | Envelope SHA-256 (16-hex) |
| :--- | :--- | :--- | :--- | :--- |
| `Track S83` | $K_8$ Schur `⧄` compounding & Law-3 `⫩` firewall | `28/28` gain `2.6722x–10.3230x`; Foster sum `7`; ungated `2.9390x` vs gated `0` | `74d269c5c1c35665` | `f21b81d563f2c341` |
| `Track S85` | Multi-layer Schur `⧄` composition | Exact boundary elimination & compositional conductance invariance | `f9a7c7efe7d63c0b` | `cd54b65fe0c1a1bf` |
| `Track S92` | Schur `⧄` spectral routing bridge | Conductance reduction & effective resistance preservation | `294e26e91bfa8cae` | `bf86fdb60d66d2fa` |
| `Track S94` | Sleep consolidation & `[H_8, D]` non-commutation | `[H_8, D]` MSE `71/8 = 8.875x`; `20`-night FWER `87.15%` (`39/400`); `d=(3/5,4/5,0,0)` | `1ad705c23646b65d` | `b21f0fba7aef4739` |
| `Track S95` | `BlockH4` low-forgetting vs `bf16` ULP cliff | `8.74x–22.58x` lower `F/L` vs LoRA; `81.40%` (`407/500`) vs `8.73%` (`873/10000`) ULP death | `b6cee3035ea86ede` | `43ac437b64fb71c4` |
| `Track S97` | Exact `⧅` dark-mode nullspace projection (`WSE-HC`) | `154 -> 0` forgetting; Pythagorean `60 = 154/3 + 26/3`; `16.16x` less forgetting (`Hybrid`) | `506c6baa149dec6a` | `17ba806c638c5194` |
| `Track S102` | MaleCNS connectome Dale/Krein/LIF invariants | `E/I = 36739597/23661623 = 1.5527`; `M3_CX = -428,494`; `6x6` CX `7.182x` non-normal; LIF `E=4v+g` | `5238ce3f81099bd9` | `25148049f59bef77` |
| `Track S110` | `Weft-Smith` `C_row` & `Poloidal Bingham` (`PREREG-S111`) | Composed `C_row` cancellation `1/2 -> 1`; `[Bingham, +] != 0`; `40/40` clean / `10/10` rollback | `2d27a8237cb47dd9` | `7975a8040f612a3d` |

---

## 2. Portal 1 — Biological Homeostasis, Sleep-Wake Synaptic Renormalization & Connectome Motifs

### 2.1 Stage-A -> Stage-B Operator Stripping Table

| Surface Biological Term (Stripped in Stage A) | Exact Stage-B Mathematical Operator ($\mathbb{Z}/\mathbb{Q}$) | Preserved Invariants | Proven Obstruction / Failure Mode |
| :--- | :--- | :--- | :--- |
| Global Synaptic Downscaling (SHY; Tononi–Cirelli) | Isotropic scalar contraction $M_\lambda(\Delta W) = \lambda \Delta W$, $\lambda \in \mathbb{Q}_{>0}$ | $C_{\mathrm{row}}(\lambda \Delta W) = C_{\mathrm{row}}(\Delta W)$; $\operatorname{ker}(W)$ & zero-threshold sign | **`P1-O2`:** `bf16` $\le 1/256$ half-ULP annihilation; **`P1-O5`:** crosses nonzero safety margin $\tau > 0$ |
| Synaptic Pruning / Thresholded Elimination | Row-Bingham $\mathcal{S}_\tau^{\mathrm{row}}(r_i) = \max(0, 1 - \tau/\|r_i\|_2) r_i$ or coord $\mathcal{S}_\tau$ | Reduces $\|\Delta W\|_F$ & active support | **`P1-O1`:** Spikes $C_{\mathrm{row}}$ past $C_{\max}$ (`25/52 -> 1`); breaks additivity $[\mathcal{S}_\tau, +] \ne 0$ |
| Per-Neuron Homeostatic Gain (Turrigiano) | Diagonal gain $D = \operatorname{diag}(d_1, \dots, d_m)$, $d_i > 0$ non-constant | Per-row sign homogeneity (when $d_i > 0$) | **`P1-O3`:** $[U_{H_4}, D] \ne 0$ (`27/2`), spikes output $C_{\mathrm{row}}$ (`1/4 -> 16/19`), input $D$ breaks `⧅` nullspace (`0 -> 36`) |
| Offline Sleep Replay Consolidation | Convex projected fold $W'_{\mathrm{plate}} = (1-\alpha) W_{\mathrm{plate}} + \alpha (G P_\perp)$ | Exact `0` base forgetting ($\Delta W_\perp X_{\mathrm{base}} = 0$); exact `⧅` commutation | **`P1-O4`:** Summing two safe plates can cancel rows and spike $C_{\mathrm{row}}$ (`1/2 -> 1`); must re-gate post-merge |
| Dale's Law & Inhibitory Central-Complex Clamp | Sign-column-constrained non-normal $M_{\mathrm{EI}}$, $\rho(M_{\mathrm{EI}}) < 1$ + integer LIF $E(v,g) = 4v + g$ | Strict contraction despite $\|[M, M^\top]\|_F^2 > 0$; `2`-step strict LIF LaSalle convergence | Flipping I-column sign (coherent E-E loop) creates $\mu_1 = 5/4 > 1$ exponential blowup (`7,523.16x` in `20` steps) |

### 2.2 Exact Pure-$\mathbb{Q}$ Theorems & Machine-Verified Witnesses (`P1-1`..`P1-6`)

#### Theorem P1.1 & Obstruction `P1-O1`: Multiplicative `C_row` Invariance vs. Subtractive / Bingham `C_row` Spike (`p1_1`)
Define row concentration $C_{\mathrm{row}}(W) := \frac{\max_i \|W_{i,:}\|_2^2}{\sum_i \|W_{i,:}\|_2^2} \in \mathbb{Q}$ (`Track S110` / `PREREG-S111` structural gate $C_{\mathrm{row}} \le C_{\max} = 1/2$).
- **Exact Witness Matrix** (exact Pythagorean integer row norms $\|r_0\|_2 = 5$, $\|r_{1,2,3}\|_2 = 3$):
  $$\Delta W = \begin{pmatrix} 3 & 4 \\ 0 & 3 \\ 0 & 3 \\ 0 & 3 \end{pmatrix}, \quad \|r\|_2^2 = [25, 9, 9, 9], \quad C_{\mathrm{row}}(\Delta W) = \frac{25}{52} \approx 0.480769 \le \frac{1}{2}.$$
- **Multiplicative Scaling:** For EVERY tested $\lambda \in \{1/2, 1/4, 3/7, 17/5\}$, $C_{\mathrm{row}}(\lambda \Delta W) = 25/52$ identically.
- **Obstruction `P1-O1` (Subtractive / Bingham Concentration Spike):** Applying exact Euclidean row-wise Bingham soft-thresholding $\mathcal{S}_\tau^{\mathrm{row}}(r_i) = \max(0, 1 - \tau/\|r_i\|_2) r_i$ at $\tau = 3$ shrinks row `0` to $(6/5, 8/5)$ ($\|r_0'\|_2^2 = 4$) while annihilating rows `1..3` to `0`, driving:
  $$C_{\mathrm{row}}(\mathcal{S}_3^{\mathrm{row}}(\Delta W)) = \frac{4}{4} = 1 > \frac{1}{2} \quad \left(\text{exact } \frac{52}{25} = 2.08\times \text{ spike!}\right).$$
  Coordinate soft-thresholding at $\tau = 3$ yields row squared norms `[1, 0, 0, 0]` and the identical `C_row = 1` breach, while witnessing exact non-additivity $[\mathcal{S}_3, +] \ne 0$: on $u = (0, 3), v = (0, 3)$, $\mathcal{S}_3(u) + \mathcal{S}_3(v) = (0, 0) \ne (0, 3) = \mathcal{S}_3(u + v)$ (gap `= 3`, bridging `Track S110`).

#### Obstruction `P1-O2`: Multiplicative Sleep Decay & `BlockH4` Isometric Diffusion Hit the `bf16` Half-ULP Annihilation Floor (`p1_2`)
Under IEEE-754 `bf16` round-to-nearest-even at unit base weight $W_0 = 1 = 1.0000000_2 \times 2^0$ (even LSB `0`, $\mathrm{ULP}(1) = 2^{-7} = 1/128$), ANY additive update with $|\Delta W_{ij}| \le 2^{-8} = 1/256$ rounds identically back to $W_0 = 1$ (**`0` effective update**).
1. **Sleep-Decay Cliff:** Starting at $|\Delta W^{(0)}| = 1/64$ (`2` ULPs) under multiplicative contraction $\lambda = 1/2$ per sleep cycle:
   - Cycle `0`: `1/64` -> **SURVIVES**
   - Cycle `1`: `1/128` -> **SURVIVES**
   - Cycle `2`: `1/256` (exact half-ULP tie-to-even) -> **ANNIHILATED TO `0`**
   - Cycle `3`: `1/512` -> **ANNIHILATED TO `0`**
2. **Exact `BlockH4` Isometric Annihilation Theorem:** Let $U = \frac{1}{2} H_4$ ($U^\top U = I_4$ exact rational orthogonal) and localized spike $E_{00}$ with $(0,0)$ entry $1/64$ ($\|E_{00}\|_F^2 = 1/4096$). Under `bf16` merge into $W_0 = \mathbf{1}_{4\times 4}$, $E_{00}$ survives `1/1` (`100%` Frobenius mass retained). Its exact orthogonal conjugate $\tilde{\Delta} = U E_{00} U^\top$ preserves Frobenius norm identically ($\|\tilde{\Delta}\|_F^2 = 1/4096$), YET spreads mass across all `16` entries at magnitude $|\tilde{\Delta}_{ij}| = 1/256$, causing **`16/16` (`100%`) complete annihilation** upon `bf16` merge!
3. **`Track S95` Empirical Bridge:** Directly explains the measured `Track S95` cliff where `BlockH4` lost `407/500 = 81.40%` of updates to `< ½-ULP` merge annihilation vs. `LoRA` `873/10000 = 8.73%` (exact rational ratio `8140/873 = 9.324170×`).  
**Exact Algebraic Repair:** Keep fluid `Weft-Smith` plates in decoupled `FP16`/`FP32` slots during wake, and gate sleep consolidation into `bf16` cores strictly by $|\Delta W_{ij}| > 2^{e(W_0)-8}$ (or consolidate into an `FP16` core residual accumulator).

#### Theorem P1.2 & Obstructions `P1-O3` / `P1-O4`: Isotropic `⧅` Dark-Mode Commutation vs. Anisotropic Homeostasis & Plate Cancellation (`p1_3`)
Let $X_{\mathrm{base}} = \begin{pmatrix} 1 & 0 \\ 0 & 1 \\ 1 & 0 \\ 0 & 1 \end{pmatrix}$ (`rank = 2`), $P_{\mathrm{base}} = X_{\mathrm{base}}(X_{\mathrm{base}}^\top X_{\mathrm{base}})^{-1} X_{\mathrm{base}}^\top$, and dark-mode projector $P_\perp = I_4 - P_{\mathrm{base}}$ ($P_\perp^2 = P_\perp = P_\perp^\top$, $\operatorname{tr}(P_\perp) = 2$, $P_\perp X_{\mathrm{base}} = 0$). For outer plate update $\Delta W_\perp = G P_\perp$:
- **Exact Commutation & Zero Base Forgetting:** For isotropic sleep factor $\lambda = 3/4$ and convex offline replay $W' = (1-\alpha)\Delta W_\perp + \alpha \Delta W_{\perp, 2}$ ($\alpha = 1/3$):
  $$(\lambda \Delta W_\perp) P_\perp = \lambda \Delta W_\perp, \quad \|\lambda \Delta W_\perp X_{\mathrm{base}}\|_F^2 = 0, \quad \|W' X_{\mathrm{base}}\|_F^2 = 0, \quad C_{\mathrm{row}}(\lambda \Delta W_\perp) = C_{\mathrm{row}}(\Delta W_\perp) = \frac{13}{42}, \quad \frac{\|\lambda \Delta W_\perp\|_F^2}{\|\Delta W_\perp\|_F^2} = \frac{9}{16}.$$
- **Obstruction `P1-O3` (Anisotropic Per-Neuron Gain $D = \operatorname{diag}(4, 1, 1, 1)$ Breaks THREE Invariants Simultaneously):**
  1. **Breaks `BlockH4` Commutation:** $\|[U_{H_4}, D]\|_F^2 = \mathbf{27/2} > 0$ (exact algebraic counterpart of `Track S94`'s `[H_8, D]` `71/8 = 8.875×` importance MSE smearing).
  2. **Output-Side `D` Spikes `C_row`:** On uniform-row matrix $A_{\mathrm{unif}}$ (`C_row = 1/4`), $D A_{\mathrm{unif}}$ spikes to **$C_{\mathrm{row}} = 16/19 \approx 0.842105 > 1/2$**.
  3. **Input-Side `D` Shatters `⧅` Dark-Mode Nullspace:** $\|(\Delta W_\perp D) X_{\mathrm{base}}\|_F^2 = \mathbf{36} > 0$ — anisotropic presynaptic scaling rotates base inputs OUT of $\operatorname{col}(X_{\mathrm{base}})$ into $\operatorname{col}(P_\perp)$, causing immediate catastrophic base forgetting!
- **Obstruction `P1-O4` (Composed Consolidation `C_row` Cancellation, Bridging `Track S110`):** Summing two individually safe plates $W_1 = \begin{pmatrix} 1 & 1 \\ 1 & 1 \end{pmatrix}$ (`C_row = 1/2`) and $W_2 = \begin{pmatrix} 1 & 1 \\ -1 & -1 \end{pmatrix}$ (`C_row = 1/2`) cancels row `1` and yields $C_{\mathrm{row}}(W_1 + W_2) = \mathbf{1} > 1/2$. Offline replay consolidation MUST re-verify $C_{\mathrm{row}}(W_{\mathrm{merged}}) \le C_{\max}$ **after** plate summation.

#### Obstruction `P1-O5`: Rank-1 Safety Margin Crossing Under Multiplicative Downscaling (`p1_4`)
Using `Track S94`'s exact Pythagorean unit safety contrast $d = (3/5, 4/5, 0, 0)$ ($\|d\|_2^2 = 1$) and exact Householder mirror $H_d = I - 2 d d^\top$ ($H_d^2 = I$, $H_d d = -d$):
- For a safe pre-sleep refusal margin $m_{\mathrm{pre}} = d^\top W x = 5/2$ against a nonzero yield wall / refusal margin $\tau = 2$ (`m_pre > tau`), multiplicative downscaling at $\lambda = 3/4 < \lambda_{\mathrm{crit}} = \tau / m_{\mathrm{pre}} = 4/5$ shrinks the margin to **$m_{\mathrm{post}} = 15/8 < 2$** (crossing the safety wall!) **even though zero-threshold sign (`15/8 > 0`) stays preserved**.
- **Exact Algebraic Repair:** Any safety or Bingham yield wall under multiplicative sleep MUST either co-scale ($\tau' = \lambda \tau$) or be formulated as a dimensionless scale-invariant cosine score $\cos^2 \theta = \frac{(d^\top W x)^2}{\|W x\|_2^2}$ (verified identically `1 -> 1` pre- and post-sleep).

#### Theorem P1.3: MaleCNS Exact Dale Ratio, Non-Normal E/I Stability Clamp & Discrete Integer LIF LaSalle Lyapunov (`p1_5`, `Track S102` Bridge)
- **Exact MaleCNS Whole-Brain Anchors (`Track S102`):** `E = 36,739,597`, `I = 23,661,623`, `E + I = 60,401,220`, exact Dale ratio `E/I = 36739597/23661623 = 1.552708` (`60.8259% E` / `39.1741% I`), with `M3_CentralComplex` net signed synapse balance **`-428,494`** (net inhibitory clamp).
- **Exact 2-Population Dale-Structured Non-Normal E/I Clamp vs. Coherent E-E Blowup:** Under column-presynaptic convention ($x_{t+1} = M x_t$; transpose matches `S102` row-presynaptic convention), compare balanced Dale clamp $M_{\mathrm{EI}} = \begin{pmatrix} 3/4 & -1/2 \\ 1/2 & -1/4 \end{pmatrix}$ against unclamped coherent loop $M_{\mathrm{EE}} = \begin{pmatrix} 3/4 & 1/2 \\ 1/2 & 3/4 \end{pmatrix}$:
  - $M_{\mathrm{EI}}$ has exact characteristic polynomial $(\mu - 1/4)^2$ (repeated eigenvalue `1/4`), is **strictly non-normal** ($\|[M_{\mathrm{EI}}, M_{\mathrm{EI}}^\top]\|_F^2 = 2 > 0$, paralleling `S102` `6×6` CX `7.182×` non-normal commutator boost), and contracts BOTH eigenvector $x_0 = (1, 1)$ (`||x_20||^2 = 1/2^79 = 1/604462909807314587353088`) and non-eigenvector $(1, 0)$ (`||x_20||^2 = 3281/2^80 < 10^-9`, exact Jordan factor $41^2 + 40^2 = 3281$).
  - Flipping the inhibitory column sign to positive ($M_{\mathrm{EE}}$) yields $\mu_1 = 5/4 > 1$, exploding `||x_20||^2` from `2` to **`15,046.3277`** (**`7,523.1638×` amplification** in `20` steps).
- **Exact Discrete Integer LIF Lyapunov & 2-Step LaSalle Convergence (`Track S102` Refinement):** For zero-drive integer LIF dynamics $v' = \lfloor (19v + g)/20 \rfloor$, $g' = \lfloor 4g/5 \rfloor$ and $E(v, g) = 4v + g$, exhaustive verification over all `676` integer states $(v, g) \in \{0..25\}^2$ proves:
  1. **1-Step Non-Increasing (`676/676`):** $E_{t+1} \le E_t - \frac{1}{5} v_t \le E_t$.
  2. **Exact Lossless Synaptic-to-Membrane Transfer Tie (`1/675` nonzero states):** At $(v, g) = (0, 20)$ (generally $v = 0, 20 \mid g$), $E_1 = 4(1) + 16 = 20 = E_0$ holds with equality because $g$ transfers exact integer quantum `4` into $4 v_1$.
  3. **2-Step Strict LaSalle Contraction (`675/675` nonzero states):** $E_{t+2} < E_t$ holds for EVERY nonzero state $(v, g) \ne (0, 0)$, certifying unconditional finite-time convergence to rest `(0, 0)`.

#### Theorem P1.4: Multi-Night FWER Explosion vs. `⧅` Zero-Drift Pythagorean Split (`p1_6`, `Track S94`/`S97` Bridge)
- Un-gated nightly consolidation with single-night residual false-update rate $p = 39/400$ (`Track S80`/`S94`) retains only `(361/400)^20 = 0.128512` (`12.8512%`) clean trajectories after `20` nights — **`87.1488%` cumulative FWER**.
- Guarding offline consolidation with exact `⧅` nullspace projection reproduces `Track S97`'s exact rational Pythagorean energy split $60 = 154/3 + 26/3$, annihilating the `154/3` unprojected forgetting component identically to **`0`** while preserving the full `26/3` dark-mode learning residual.

---

## 3. Portal 4 — Mycelial / Vascular Flow-Adaptive Conductance (`Track S83/S85/S92` & `Portal B`)

### 3.1 Stage-A -> Stage-B Operator Stripping Table

| Surface Biological Term (Stripped in Stage A) | Exact Stage-B Mathematical Operator ($\mathbb{Z}/\mathbb{Q}$) | Preserved Invariants | Proven Obstruction / Failure Mode |
| :--- | :--- | :--- | :--- |
| Vascular Branching Law (Murray 1926) | Variational optimum of $J_e(u) = Q_e^2/u^2 + c u$ ($u = r^2$) under Kirchhoff $\sum Q_i = Q_0$ | Exact $r_0^3 = \sum r_i^3$, optimal $D_e^* \propto |Q_e|^{4/3}/L_e$, SOS excess certificate | Fixed metabolic trade-off exponent $p = 2$; fails if parameter cost scales sub-quadratically or non-additively |
| Mycelial Equilibrium Transport | Weighted graph Laplacian $L(D)\phi = b$ & Schur complement $S_B = L_{BB} - L_{BI} L_{II}^{-1} L_{IB}$ | Exact Thomson $\phi_B^\top S_B \phi_B = \sum Q_e^2/D_e$; Foster sum $\sum D_e R_{\mathrm{eff}}(e) = |V|-1$ | Linear ohmic monotonicity ONLY; **`P4-O2`:** selfish congestion routing suffers `+1/3` (`+33.33%`) Braess penalty |
| *Physarum* Tube Reinforcement (Tero et al.) | Discrete conductance map $D_e^{(t+1)} = (1-\beta) D_e^{(t)} + \alpha |Q_e^{(t)}|^\gamma$ | At $\gamma = 1$: global shortest-path attractor & $\sum D_e$ conservation | **`P4-O1`:** At $\gamma = 2$, exact separatrix $D_2/D_1 = (L_2/L_1)^2$ causes irreversible `2x`-worse hysteresis lock-in |
| Mycelial Network Pruning | Asymptotic limit $D_e \to 0$ off the shortest-path spanning tree ($m \to n - 1$) | Minimal active edge count ($m = n - 1$) | **`P4-O3`:** `100%` single-edge trunk failure AND `1000.5x` edge-density chasm below `Portal B` edge reconstruction |

### 3.2 Exact Pure-$\mathbb{Q}$ Theorems & Machine-Verified Witnesses (`P4-1`..`P4-5`)

#### Theorem P4.1: Exact Pure-$\mathbb{Q}$ Murray's Law via Plato's `3^3 + 4^3 + 5^3 = 6^3` Trifurcation & Sum-of-Squares Certificate (`p4_1`)
Minimizing viscous dissipation plus volumetric capacity cost per unit length $J(u; Q, c) = \frac{Q^2}{u^2} + c u$ ($u = r^2 > 0$) by exact 3-term AM-GM ($Q^2/u^2 + \frac{cu}{2} + \frac{cu}{2} \ge 3 (c^2 Q^2 / 4)^{1/3}$) achieves strict equality iff $c u^3 = 2 Q^2 \iff r^3 = \sqrt{2/c}\,|Q|$. By Kirchhoff conservation $Q_0 = \sum_i Q_i$, optimal radii obey **exact Murray conservation $r_0^3 = \sum_i r_i^3$** (note: Fermat's Last Theorem forbids a nonzero integer 2-way bifurcation, whereas Plato's exact integer cube identity $3^3 + 4^3 + 5^3 = 27 + 64 + 125 = 216 = 6^3$ yields an **all-integer 3-way trifurcation** at $c = 2$!).
- **Exact Algebraic Sum-of-Squares Optimality Certificate** at parent flux $Q_0 = 216, c = 2$ ($u^* = 36, r_0^* = 6, J_0^* = 108$):
  $$J(u; 216, 2) - 108 = \frac{2 (u - 36)^2 (u + 18)}{u^2} \ge 0 \quad \forall\, u > 0, \quad \text{with unique zero at } u = 36.$$
- **Exact Rational Comparison Across Competing Architectural Capacity Laws** (matched fluxes $Q = (216; 27, 64, 125)$):

| Allocation Rule | Parent $u_0 = r_0^2$ | Total Cost $J_{\mathrm{total}}$ (Exact $\mathbb{Q}$) | Exact Penalty vs. Murray | Decimal Penalty |
| :--- | :--- | :--- | :--- | :--- |
| **Murray Cube Law ($r_0^3 = \sum r_i^3$)** | **`36`** (`r_0 = 6`) | **`258`** | **`0`** (Unique Global Min) | `0.000000` |
| Area-Preserving ($r_0^2 = \sum r_i^2$) | `50` | `167914/625` | `+6664/625` | `+10.662400` |
| Uniform Radius ($r_e = 5$ all edges) | `25` | `192106/625` | `+30856/625` | `+49.369600` |
| Diameter-Preserving ($r_0 = \sum r_i$) | `144` | `1761/4` | `+729/4` | `+182.250000` |

**Weft-Geosphere Transfer:** When allocating plate rank/width capacity $u_e$ across hierarchically routing micro-harness channels carrying token flux $Q_e$, Murray's exponent $D_e \propto |Q_e|^{4/3}$ (capacity $u_e \propto |Q_e|^{2/3}$, NOT uniform and NOT linear-area $u_0 = \sum u_i$) uniquely minimizes routing resistance plus parameter volume.

#### Theorem P4.2: Exact Schur Complement `⧄` = Thomson's Minimum-Power Principle, Foster Sum & Law-3 `⫩` Firewall (`p4_2`, `Track S83` Bridge)
On a 5-node weighted plate-routing mesh ($B = \{0, 4\}$, interior plates $I = \{1, 2, 3\}$, `8` positive integer conductances `(0,1):2, (0,2):1, (1,2):1, (1,3):2, (2,3):1, (1,4):1, (2,4):2, (3,4):3`):
1. **Exact Schur Effective Conductance & Resistance:** $S_B = \begin{pmatrix} 7/4 & -7/4 \\ -7/4 & 7/4 \end{pmatrix} \implies G_{\mathrm{eff}} = 7/4$, $R_{\mathrm{eff}}(0, 4) = \mathbf{4/7} \approx 0.571429$.
2. **Exact Triple Thomson Identity:** $\phi_B^{*\top} S_B \phi_B^* = \phi^{*\top} L(D) \phi^* = \sum_e Q_e^{*2} / D_e = \mathbf{4/7}$ identically!
3. **Exact Strict Excess Certificate:** Perturbing interior potentials by $\delta = (1/3, -1/2, 2/5)$ raises dissipation by exact Schur quadratic excess $\delta^\top L_{II} \delta = \mathbf{923/300} \approx 3.076667 > 0$.
4. **Exact Foster Conservation:** $\sum_{e \in E} D_e R_{\mathrm{eff}}(e) = \mathbf{4} = |V| - 1$ (exact counterpart of `Track S83`'s $K_8$ Foster sum `7 = 8 - 1`).
5. **Exact Law-3 `⫩` Firewall Isolation:** Severing corrupted interior plate `1` yields `0` leakage to node `1` while retaining finite multi-path boundary conductance $G_{\mathrm{eff}}^{\mathrm{fw}} = 11/15$, $R_{\mathrm{eff}}^{\mathrm{fw}} = \mathbf{15/11} \approx 1.363636$.

#### Theorem P4.3 & Obstruction `P4-O1`: *Physarum* $\gamma = 1$ Global Shortest-Path Convergence vs. $\gamma = 2$ Suboptimal Hysteresis Lock-In (`p4_3`)
On a 2-parallel-path network of lengths $L_1 = 1 < L_2 = 2$ with unit flux $I = 1$, exact Kirchhoff flows $Q_1 = \frac{2 D_1}{2 D_1 + D_2}$, $Q_2 = \frac{D_2}{2 D_1 + D_2}$, and discrete *Physarum* update $D_i^{(t+1)} = \frac{1}{2} D_i^{(t)} + \frac{1}{2} Q_i^\gamma$:
- **Case A ($\gamma = 1$, Convex Linear Reinforcement — Global Convergence):**
  $$\frac{D_1^{(t+1)}}{D_2^{(t+1)}} = \frac{D_1^{(t)}}{D_2^{(t)}} \cdot \frac{2 D_1^{(t)} + D_2^{(t)} + 2}{2 D_1^{(t)} + D_2^{(t)} + 1} > \frac{D_1^{(t)}}{D_2^{(t)}} \quad \forall\, D_1, D_2 > 0, \qquad D_1^{(t)} + D_2^{(t)} = 1.$$
  Even from a **`9×` adversarial bias** toward the suboptimal longer path $(D_1^{(0)}, D_2^{(0)}) = (1/10, 9/10)$, $D_1$ strictly increases at every step, overtakes $D_2$ at **step `6`**, and reaches $(D_1^{(12)}, D_2^{(12)}) \approx (0.872340, 0.127660)$ (`D_1/D_2 = 6.833302`), converging globally to $(1, 0)$.
- **Case B ($\gamma = 2$, Superlinear Positive Feedback — `OBSTRUCTION P4-O1`):**
  Comparing $Q_1^2/D_1 - Q_2^2/D_2 = \frac{4 D_1 - D_2}{(2 D_1 + D_2)^2}$ proves an **exact algebraic separatrix at $D_2 / D_1 = (L_2/L_1)^2 = 4$** with exact unstable equilibrium **$(D_1^*, D_2^*) = (1/9, 4/9)$**:
  - From the **exact same `9×` adversarial start** $(1/10, 9/10)$ ($D_2/D_1 = 9 > 4$): $D_1/D_2$ collapses to **`0.00974172`** in just `5` steps — **irreversible lock-in onto the `2×`-longer path** (double steady-state dissipation $P = 2$ vs. optimal $P = 1$)!
  - From symmetric start $(1/2, 1/2)$ ($D_2/D_1 = 1 < 4$): $D_1/D_2$ surges to **`30.151566`** in `5` steps (converging to optimal path `1`).
  - **Architectural Rule:** Any flow-adaptive plate router MUST pin $\gamma = 1$ (strictly convex reinforcement); superlinear "winner-take-all" updates ($\gamma > 1$, e.g. high-temperature softmax / quadratic Hebbian routing) lock permanently onto stale pre-shift routes!

#### Theorem P4.4 & Obstruction `P4-O2`: Exact Braess-Type Non-Monotonicity Separation (`p4_4`)
On the 4-node Wheatstone bridge ($s=0, a=1, b=2, t=3$):
1. **Linear Ohmic / Thomson Regime (`NO` Braess Paradox):** With conductances $D_{01} = 1, D_{13} = 1/2, D_{02} = 1/2, D_{23} = 1$, exact Schur effective resistance drops strictly from $R_{\mathrm{eff}}^{\mathrm{pre}} = \mathbf{3/2}$ to $R_{\mathrm{eff}}^{\mathrm{post}} = \mathbf{43/32} = 1.343750$ upon adding bridge $D_{12} = 10$ (exact improvement **`5/32`**, bounded below by the short-circuit limit $4/3 < 43/32 < 3/2$ — Rayleigh monotonicity holds unconditionally).
2. **Selfish Congestion-Dependent Wardrop Regime (`EXACT` Braess Paradox):** With affine edge latencies $c_{01}(q) = q, c_{13}(q) = 1, c_{02}(q) = 1, c_{23}(q) = q$ and unit flow $I = 1$:
   - Pre-bridge unique Wardrop equilibrium: `(1/2, 1/2)` split, exact latency **`3/2`**.
   - Post-bridge (adding zero-cost shortcut $c_{12}(q) = 0$): `100%` of flow diverts onto `0 -> 1 -> 2 -> 3`, raising equilibrium latency to **`2`** — an exact **`+1/2` (`+1/3 = +33.3333%`) latency degradation** from adding free capacity!
- **Architectural Rule:** Adding a new micro-harness plate or shortcut edge is guaranteed non-harmful ONLY under coordinated Kirchhoff/Thomson potential routing ($\gamma = 1$ Schur), NEVER under uncoordinated greedy token routing where congestion latency grows with load.

#### Theorem P4.5 & Obstruction `P4-O3`: Sparsity vs. Tomography Identifiability Trade-Off (`p4_5`, `Portal B` Bridge)
Aggressive *Physarum* pruning ($\gamma = 1, D_{\min} = 0$) drives conductance onto a shortest-path tree ($m = n - 1$, average degree $\bar{d} < 2$, minimum degree $\delta = 1$), creating TWO exact algebraic failure modes:
1. **100% Trunk Single-Edge Fragility vs. Conductance Floor Repair:** On the 2-path witness (`L_1 = 1, L_2 = 2`), the pruned tree limit $(D_1, D_2) = (1, 0)$ achieves normal $R_{\mathrm{eff}} = 1$ but **disconnects completely (`R_eff = ∞`)** if the primary edge fails. Imposing an explicit **conductance floor $D_e \ge D_{\min} = 1/16$** simultaneously improves normal resistance to **$R_{\mathrm{eff}}^{\mathrm{norm}} = 32/33 \approx 0.969697$** AND preserves `100%` single-edge fault connectivity at finite **$R_{\mathrm{eff}}^{\mathrm{fault}} = 32$**!
2. **Exact `Portal B` `edge_reconstruction` Density Chasm:** `Portal B`'s unconditional Harary linear-density edge-reconstruction regime requires $m \ge 1000 n_0$ and $\delta(G_0) \ge 2000$. At the minimal vertex count $n_0 = 2001$:
   - *Physarum* tree edges: $m_{\mathrm{tree}} = 2,000$.
   - `Portal B` linear-density floor: $m_{\mathrm{PB}} = 2,001,000$.
   - **Exact Edge-Density Chasm:** $m_{\mathrm{PB}} / m_{\mathrm{tree}} = \mathbf{2001/2 = 1000.5\times}$ (and `Track S83`'s $K_8$ Schur mesh already requires `28/7 = 4×` tree density for its `2.6722×–10.3230×` multi-path compounding).
- **Architectural Rule:** Un-floored *Physarum* sparsity and `Portal B` edge-deck tomography / `S83` multi-path resilience occupy **provably disjoint density regimes**. Practical `Weft-Geosphere` plate routing MUST operate in a **conductance-floored regime** ($D_e \ge D_{\min} > 0$) with explicit Law-3 `⫩` per-edge circuit breakers.

---

## 4. Master Law-5 Obstruction & Repair Matrix (`8/8` Proved in Pure-$\mathbb{Q}$)

| ID | Portal | Biological Analogy That Fails | Exact Pure-$\mathbb{Q}$ Counterexample Witness | Quantitative Failure | Exact Stage-B Repair for `Weft-Geosphere` |
| :--- | :---: | :--- | :--- | :--- | :--- |
| `P1-O1` | 1 | Subtractive / Bingham synaptic pruning | Pythagorean rows `(3,4), (0,3)x3`, $\tau = 3$ | $C_{\mathrm{row}}: 25/52 \to 1$ (`2.08x` breach) + $[\mathcal{S}_3, +] \ne 0$ | Use isotropic multiplicative decay + post-merge `C_row` gate; restrict Bingham to `Poloidal` $SO(k)$ radial gates |
| `P1-O2` | 1 | Global multiplicative sleep decay into `bf16` | $U_{H_4} E_{00} U_{H_4}^\top$ (`1/256` entries) & $\lambda = 1/2$ cycle `2` | `16/16` (`100%`) entries annihilated at constant $\|\Delta W\|_F^2 = 1/4096$ | Keep `Weft-Smith` plates decoupled in `FP16`/`FP32`; merge only when $|\Delta W_{ij}| > 2^{e(W_0)-8}$ |
| `P1-O3` | 1 | Anisotropic per-neuron homeostatic gain $D$ | $D = \operatorname{diag}(4,1,1,1)$ on `BlockH4` & `P_perp` | $\|[U_{H_4}, D]\|_F^2 = 27/2$; output $C_{\mathrm{row}}: 1/4 \to 16/19$; input forgetting `0 -> 36` | Enforce strictly isotropic scalar $\lambda I$ across `BlockH4` / `⧅` subspaces |
| `P1-O4` | 1 | Independent per-plate consolidation safety | $W_1 = [(1,1),(1,1)]$, $W_2 = [(1,1),(-1,-1)]$ | Individual `C_row = 1/2`, sum `C_row = 1` (`2x` spike) | Evaluate `C_row(W_merged) <= C_max` **after** summation (matches `Track S110` commit gate) |
| `P1-O5` | 1 | Multiplicative scaling under nonzero safety wall | `S94` $d=(3/5,4/5,0,0)$, $m=5/2, \tau=2, \lambda=3/4$ | Margin drops `5/2 -> 15/8 < 2` (breaches $\tau$, sign stays `+`) | Co-scale $\tau' = \lambda \tau$ OR gate safety on scale-invariant cosine $\cos^2 \theta$ |
| `P4-O1` | 4 | Superlinear *Physarum* reinforcement ($\gamma = 2$) | $L_1=1, L_2=2$, init $(1/10, 9/10)$ above separatrix `4` | Exact unstable fixed point `(1/9, 4/9)`; locks on `2x`-worse path | Pin strictly convex reinforcement exponent $\gamma = 1$ (globally attracting shortest path) |
| `P4-O2` | 4 | Selfish congestion-weighted shortcut addition | 4-node Wheatstone bridge, affine $c(q) = q, 1, 0$ | Ohmic `R_eff: 3/2 -> 43/32` (better), Wardrop latency `3/2 -> 2` (`+33.33%` worse) | Route via coordinated Kirchhoff/Thomson potential solver, never greedy uncoordinated congestion |
| `P4-O3` | 4 | Un-floored *Physarum* tree pruning ($D_{\min} = 0$) | 2-path trunk fault & `Portal B` $n_0 = 2001$ | `100%` trunk fault disconnect; `1000.5x` deficit below `Portal B` edge deck | Impose conductance floor $D_e \ge D_{\min} > 0$ (`R_eff^fault = 32 < inf`) + Law-3 `⫩` isolation |

---

## 5. Honest Law-4 Attribution (`N0` / `N1` Accounting; `n2_claims = 0`)

- **`N0` (Classical Prior Art — Explicitly Credited, Zero Reinvention Claimed):**
  - Murray's cubic vascular optimality law (Murray 1926); Kirchhoff network equations (1845); Thomson's minimum-power principle & Rayleigh monotonicity (1870); Foster's resistance-sum theorem (1948); Schur complement (Schur 1917); Braess's paradox & Wardrop equilibrium (Wardrop 1952; Braess 1968); *Physarum polycephalum* adaptive conductance ODE/map (Tero, Kobayashi & Nakagaki 2007/2010); Synaptic Homeostasis Hypothesis (Tononi & Cirelli 2003/2014); homeostatic synaptic scaling (Turrigiano 2008); Dale's principle (Dale 1935); Harary edge-reconstruction conjecture (Harary 1964) & linear-density threshold theorem (Müller 1977 / `Portal B` bridge); FlyEM MaleCNS v1.0 connectome dataset; prior verified Aletheia tracks (`S80`, `S83`, `S85`, `S92`, `S94`, `S95`, `S97`, `S102`, `S110`).
- **`N1` (Genuinely Novel Cross-Domain Synthesis & Exact Pure-$\mathbb{Q}$ Obstruction Certificates in This Document):**
  1. Unified exact pure-$\mathbb{Z}/\mathbb{Q}$ obstruction suite (`verify_portals_1_4_exact.py`, `0` floats, `9/9` fail-closed controls) proving all `8` cross-domain failure boundaries (`P1-O1..P1-O5`, `P4-O1..P4-O3`) directly inside the `Weft-Geosphere` (`PREREG-S111` / `S110` / `S95` / `S97`) and `S83`/`Portal B` algebraic frameworks.
  2. Exact `BlockH4` isometric `16/16` (`100%`) `bf16` half-ULP tie-to-even annihilation theorem at constant Frobenius norm (`1/4096`), giving a closed-form algebraic explanation of `Track S95`'s `81.40%` vs. `8.73%` (`9.324170×`) empirical cliff.
  3. Exact 2-step integer LaSalle refinement of `Track S102`'s LIF Lyapunov function (`676/676` 1-step non-increasing, exact `1/675` lossless transfer tie at `(0, 20)`, `675/675` strict 2-step contraction).
  4. Exact Plato `3^3 + 4^3 + 5^3 = 6^3` all-integer Murray trifurcation with closed-form rational SOS optimality certificate `2(u-36)^2(u+18)/u^2` and exact quantification of the `1000.5×` *Physarum*-tree vs. `Portal B` edge-reconstruction density chasm.
- **`N2` (Unverified / Speculative Novelty Claims):** **`0`** (`n2_claims = 0`).

---

## 6. Two Falsifiable `SOP-12` Preregistration Candidates (Ready for Future GPU/CPU Execution)

### Candidate 1 — `PREREG-CAND-P1`: Sleep-Wake Isotropic `⧅`-Projected Consolidation with `bf16` ULP Guard for `Weft-Geosphere` Plates
- **Target System & Direct Bridge:** `Weft-Geosphere` (`PREREG-S111` Shell-3 `Weft-Smith` plates $d \le 128$, `Track S95` `BlockH4`, `Track S97` `⧅` nullspace projection, `Track S110` `C_row` & `Poloidal Bingham` commit gate).
- **Primary Hypothesis:** Over `20` sequential continual-learning "wake -> sleep" cycles on a frozen `bf16` base backbone (e.g., `Qwen2.5-0.5B` or `Qwen2.5-1.5B`, matched to `S95`/`S97`), consolidating wake plates via **Isotropic `⧅`-Projected Consolidation + `FP16` Residual Accumulator (or `> 1/256` ULP Merge Guard) + Post-Merge `C_row <= C_max` Re-Gate + Scale-Invariant Cosine Refusal Guard** will:
  1. Match or beat un-consolidated multi-plate retention on new tasks,
  2. Maintain near-zero base forgetting (strictly $< 10\%$ of unprojected wake drift, matching `S97` `15.66×–16.16×` reduction),
  3. Eliminate `bf16` `< ½-ULP` update death (reducing dead-weight fraction from `> 80%` to `< 5%`), AND
  4. Keep `20`-cycle cumulative anchor regression FWER `< 10%` (vs. `S94`/`S80`'s `87.15%` un-gated multi-night drift).
- **Matched-Budget Arms (`P_total`, optimizer steps, batch tokens, and `3` fixed seeds matched identically across all 5 arms):**
  1. `Arm A (Treatment)`: Isotropic `⧅`-projected offline replay + `FP16` decoupled plate accumulator + post-merge `C_row <= 1/2` re-gate + cosine refusal margin.
  2. `Arm B (Naive SHY Multiplicative in bf16)`: Global multiplicative decay $\lambda = 0.9$ merged directly into `bf16` (tests `P1-O2` ULP annihilation & `P1-O5` unscaled margin drift).
  3. `Arm C (Naive Subtractive Bingham Pruning)`: Row-wise subtractive soft-thresholding during sleep (tests `P1-O1` `C_row` concentration spike).
  4. `Arm D (Naive Anisotropic Per-Row Homeostasis)`: Firing-rate-normalized per-row scaling $D$ (tests `P1-O3` `BlockH4` commutator smearing & `⧅` nullspace leakage).
  5. `Arm E (Un-Consolidated Control)`: Direct additive plate accumulation without sleep consolidation or `⧅` projection (tests `P1-O4` composed `C_row` spike & `20`-cycle FWER blowup).
- **Concrete Falsification / Kill Gates:**
  - **PASS:** `Arm A` beats ALL of `Arms B–E` simultaneously across `3/3` seeds on Pareto dominance: `base_NLL_drift(A) <= 0.005 nats`, `ULP_dead_frac(A) < 0.05`, `post_merge_C_row(A) <= 0.50`, `refusal_cosine_drop(A) <= 0.02`, AND `task_retention(A) >= task_retention(E) - 0.01`.
  - **KILL:** Kill immediately if `Arm A` fails to reduce `ULP_dead_frac` below `0.20`, OR shows `base_NLL_drift(A) > 0.02 nats`, OR fails to outperform `Arm B` on task retention at matched base drift (`< 2×` improvement).

### Candidate 2 — `PREREG-CAND-P4`: Conductance-Floored $\gamma = 1$ *Physarum*-Schur Inter-Plate Routing vs. Superlinear $\gamma = 2$ & Un-Floored Pruning
- **Target System & Direct Bridge:** `Weft-Geosphere` multi-plate routing graph (`PREREG-S111` Shell-2/Shell-3 plate switching + `Track S83`/`S85`/`S92` Schur `⧄` conductance & Law-3 `⫩` firewall + `Portal B` degree/identifiability budget).
- **Primary Hypothesis:** On a non-stationary multi-domain plate-routing benchmark with `N = 8` (and `N = 16`) specialist plates undergoing an abrupt mid-run domain/latency regime shift (inverting optimal path costs by `2×`, matching `P4-3`) followed by single-plate fault injection (Law-3 `⫩` quarantine of the highest-flux plate, matching `P4-2`/`P4-5`), **Conductance-Floored $\gamma = 1$ *Physarum*-Schur Routing** ($D_e^{(t+1)} = \max(D_{\min}, (1-\beta) D_e^{(t)} + \alpha |Q_e^{(t)}|)$ with $D_{\min} = 1/16$ and Murray-scaled edge capacity) will:
  1. Recover optimal routing after regime shift in $\le 15$ adaptation steps (whereas $\gamma = 2$ locks permanently onto the stale suboptimal route as predicted by `P4-O1`),
  2. Maintain `100%` fault survival with bounded latency overhead (`< 2.5×` normal) under forced `⫩` isolation of the primary trunk plate (whereas un-floored $\gamma = 1$ disconnects or suffers `> 10×` stall as predicted by `P4-O3`), AND
  3. Avoid Braess latency regression when a shortcut plate is added online (whereas greedy congestion-sensitive routing degrades latency as predicted by `P4-O2`).
- **Matched-Budget Arms (identical `N` plates, identical total parameter/capacity budget $\sum u_e$, identical shift schedule, `3` fixed seeds):**
  1. `Arm A (Treatment)`: Conductance-floored $\gamma = 1$ *Physarum*-Schur potential router ($D_{\min} = 1/16$, Law-3 `⫩` firewall, Murray capacity allocation).
  2. `Arm B (Superlinear Winner-Take-All)`: Identical router with $\gamma = 2$ (direct empirical test of `P4-O1` hysteresis lock-in).
  3. `Arm C (Un-Floored Tree Pruning)`: Identical $\gamma = 1$ router with $D_{\min} = 0$ (direct empirical test of `P4-O3` single-plate trunk fragility).
  4. `Arm D (Greedy Selfish Router)`: Uncoordinated per-token greedy least-latency router with congestion cost (direct test of `P4-O2` Braess regression upon adding shortcut plate).
  5. `Arm E (Static Dense Uniform Baseline)`: Fixed uniform $K_N$ mesh (tests adaptation gain vs. static Schur redundancy).
- **Concrete Falsification / Kill Gates:**
  - **PASS:** Across `3/3` seeds: (i) post-shift routing dissipation of `Arm A` converges within `<= 1.05×` of oracle optimal in `<= 15` steps while `Arm B` remains locked `>= 1.50×` worse; (ii) under `⫩` primary-plate fault, `Arm A` maintains `100%` task completion with `<= 2.5×` resistance/latency overhead while `Arm C` suffers disconnect or `>= 10×` degradation; (iii) shortcut-plate insertion strictly decreases or preserves `Arm A` latency (`Δ <= 0`) while `Arm D` exhibits positive Braess degradation (`Δ > 0`).
  - **KILL:** Kill immediately if `Arm A` fails to beat static `Arm E` by `>= 15%` steady-state routing dissipation after regime shift, OR fails to recover within `30` steps, OR exhibits any positive Braess regression (`Δ > 0`) under shortcut insertion.

---

## 7. Reproducibility & Verification Commands

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
python3 -I -B notes/natural_systems_stage_b_2026_11_25/verify_portals_1_4_exact.py --standalone --check-self
python3 -I -O -B notes/natural_systems_stage_b_2026_11_25/verify_portals_1_4_exact.py --standalone --check-self --json
python3 -I -B -W error notes/natural_systems_stage_b_2026_11_25/verify_portals_1_4_exact.py --standalone --check-self --json
```
