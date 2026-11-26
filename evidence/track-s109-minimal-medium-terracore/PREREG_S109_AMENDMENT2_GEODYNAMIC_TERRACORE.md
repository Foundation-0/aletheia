# Preregistration Amendment 2 (`PREREG-S109-AMENDMENT2-GEODYNAMIC-TERRACORE`: Three-Shell Viscoplastic Architecture `H9d`)

- **Status:** `LOCKED_PREREGISTRATION_AMENDMENT_2` *(auto-captured & locked per `SOP-12`, 2026-11-25; parent `PREREG-S109` `1ca8a38f...` and `AMENDMENT1` `6f3d1e0b...` remain 100% immutable; strictly inherits ALL 5 consensus safety contracts from `AMENDMENT1`: `§H9c-CONTRACT`, `CB-1..CB-6`, `§SWAP`, triple FLOP/param parity, and counterfactual audit faithfulness)*
- **Originating PI Insight:** Model the three semi-distinct channels of the zero-language hybrid architecture (`#3` / `H9c`) after Earth's layered spherical structure — rigid inner core, fluid/convective intermediate coupling layer, and semi-rigid surface tectonic plates that influence one another yet rearrange modularly at their boundaries.
- **Exact Prior-Art & Expedition Portal Anchor (Zero Language Smuggling — Law 5 / Anti-`CS-03`):**
  - Directly re-enters our already-verified, merged exact pure-$\mathbb{Q}$ portals:
    1. **`Track S43`** (`Foundation-0/math0#36` `MERGED`, `track-s43-viscoplastic-tectonics-relu-regions/TECTONICS_RELU_REGIONS_REPORT.md`): proved that Duvaut–Lions variational **Bingham viscoplasticity** equals **two-sided ReLU proximal soft-thresholding** identically, governed by the dimensionless **Yield Number $Y = \tau_Y / (G H)$** separating **Magma Ocean ($Y = 0$)**, **Mobile-Lid Plate Tectonics ($0 < Y < 1$)**, and **Stagnant Lid ($Y \ge 1, Q = 0$)**, plus exact R-T-F triple-junction 1-cocycle balancing ($\omega_{AB}+\omega_{BC}+\omega_{CA}=0$).
    2. **`Track S50`** (`Foundation-0/aletheia#55` `MERGED`, `track-s50-zero-dw-state-transport-tomography/ZERO_DW_STATE_TRANSPORT_REPORT.md`): proved exact discrete $S^2$ **Poloidal / Toroidal Hodge orthogonality** ($\langle u_{\text{pol}}, u_{\text{tor}}\rangle = 0$) AND exposed the exact Law-5 obstruction that ReLU/Bingham yield walls break smooth divergence conservation (`[ReLU, \delta_1] \neq 0`) and permit zero-$\Delta W$ yield-wall advection (`x = 1 -> 4`), necessitating the **Channel-2B state-transport airlock**.
  - **Direct Resolution of the `#2787` 3-Family Council Dilemma:** `AMENDMENT1` (`#2787`) exposed that an unconstrained fluid residual collapses modularity into a monolithic LM (**Magma Ocean, $Y = 0$**), while zero residual hits `Track S92`'s Translator-DPI bottleneck (**Stagnant Lid, $Y = 1$**). `Track S43`'s Bingham viscoplastic yield operator provides the exact mathematical phase-control parameter $Y \in (0, 1)$ between those two extremes!

---

## Stage-B Exact Three-Shell Operator Specification ("TerraCore")

1. **Shell 1 — Rigid Crystalline Inner Core (Zero-Language Reasoner $\mathcal{M} \to \mathcal{M}$):**
   - Frozen SHA-256-pinned `Clifford-Torus S^3` looped Core (`H7c`), strictly zero human-language tokens inside, norm-preserving $S^{d-1}$ transitions with denominator-$\pi$ Hopf fiber loop clock $\phi_r = 2\pi r / R$.
2. **Shell 2 — Viscoplastic Convective Asthenosphere (Bingham-Thresholded Capped $S^{k-1}$ Coupling Layer):**
   - Strictly obeys `§H9c-CONTRACT` ($k \le 32$, `3 bpw`, $B_{\text{res}} \le 96$ bits/problem, zero encoder$\to$decoder skip paths, Stage-2 `stop_gradient` into frozen Core).
   - Applies exact **`Track S43` Bingham Viscoplastic Soft-Thresholding** governed by dimensionless Yield Number $Y \in [0, 1]$:
     $$v = \operatorname{Bingham}_{\tau_Y}(u) := \operatorname{ReLU}(u - \tau_Y) - \operatorname{ReLU}(-u - \tau_Y), \qquad \tau_Y = Y \cdot \sigma_u, \qquad r = \operatorname{Norm}_{S^{k-1}}(v)$$
     (with $r = 0$ identically whenever $\|v\|_2 = 0$, i.e. sub-yield rigid plug flow!).
   - **Orthogonal Poloidal / Toroidal Hodge Split (`Track S50` Pillar 2):** Decomposes convective coupling into orthogonal radial-exchange (**Poloidal** $u_{\text{pol}}$: plate $\leftrightarrow$ Core coupling) and lateral-routing (**Toroidal** $u_{\text{tor}}$: cross-plate boundary rearrangement without perturbing Core depth), $\langle u_{\text{pol}}, u_{\text{tor}} \rangle = 0$.
   - **Mandatory Security Guard (`Track S50` Channel-2B Airlock):** Logs yield-wall advection norm & residual-leak probe (`<= 50k` MLP, fail-closed `CS21_RESIDUAL_LEAK` if $\ge 25\%$ above chance) to guard against `Track S50`'s zero-$\Delta W$ advection obstruction.
3. **Shell 3 — Semi-Rigid Swappable Lithospheric Plates (Modular External Converters):**
   - Independent external surface converters trained in Stage 2 (`stop_gradient` into frozen Core): e.g., **English Plate**, **Arabic/Paraphrase Plate**, **Code/Symbolic Plate**, and **Audit-Trace Plate**.
   - **Plate-Boundary Composition (`Track S43` Pillar 3):** For mixed-domain inputs (e.g., English word problem + inline symbolic/Python equations), a lightweight boundary router blends outputs at the plate seam with explicit cocycle conservation ($\sum_i \alpha_i = 1$, zero Core retraining) — testing true modular plate rearrangement!

---

## Falsifiable Hypothesis & Kill Gates (`H9d` / `EXP-Q10d`)

### Primary Experiment: Exact Dimensionless Yield-Number Phase Sweep ($Y \in \{0,\; 1/4,\; 1/2,\; 3/4,\; 1\}$)
Hold the Stage-1 frozen Core (SHA-pinned) and total system budget (`P_total = 15M`, `F_train_total`, `F_infer` `±5%`) strictly fixed across all 5 arms (3 seeds `42, 137, 2026`):
- **`Y = 0` (Magma Ocean Control):** Unthresholded capped `<= 96`-bit $S^{k-1}$ residual (`AMENDMENT1` baseline).
- **`Y = 1` (Stagnant Lid Control):** Zero residual flux ($Q = 0$, pure discrete symbolic Arm C).
- **`Y ∈ {1/4, 1/2, 3/4}` (Mobile-Lid Viscoplastic Arms):** Bingham-thresholded capped residual + orthogonal Poloidal/Toroidal split.
- **Ablation (`Y_best-NoHodge`):** Best mobile-lid $Y^*$ with an unstructured matched-rank linear coupling (isolating whether the Poloidal/Toroidal Hodge split adds real value over Bingham thresholding alone!).
- **Multi-Plate Rearrangement Test (`§PLATE-SWAP`):** Zero-retrain hot-swap and mixed-input seam composition of `{English Plate, Paraphrase/Arabic Plate, Symbolic/Code Plate}` atop the identical frozen SHA-pinned Core!

### Explicit 3-Valued Pass / Kill Gates (`H9d`)
- **`CONFIRMED`:** At least one Mobile-Lid regime $Y^* \in \{1/4, 1/2, 3/4\}$ **strictly Pareto-dominates BOTH $Y=0$ (Magma Ocean) AND $Y=1$ (Stagnant Lid)** across 3 seeds ($\ge 2$ SE), achieving:
  1. **$\ge 50\%$ of the Regime-II DPI recovery** over $Y=1$ (`Stagnant Lid`),
  2. **Strictly lower `CS21_RESIDUAL_LEAK` probe score ($\le 15\%$ above chance) AND strictly smaller `§SWAP` / `§PLATE-SWAP` drop ($\le 3$ pp)** than $Y=0$ (`Magma Ocean`), AND
  3. **$\ge 85\%$ counterfactual $h^{(r)}$ state-patching audit faithfulness**.
  *(Separate secondary check: `Y_best` vs `Y_best-NoHodge` grades whether the orthogonal Poloidal/Toroidal split independently clears $\ge 2$ SE on mixed-plate seam composition!)*
- **`FALSIFIED`:** Either $Y=0$ (capped `<= 96`-bit linear residual) ALREADY passes `CS21_RESIDUAL_LEAK` + `§SWAP` with equal or better Regime-II accuracy (proving simple bit-capping suffices without Bingham thresholding), OR $Y=1$ (pure symbolic) matches all $Y < 1$ arms, OR no $Y \in (0, 1)$ beats the controls on multi-plate seam composition.
- **`INCONCLUSIVE`:** Paired bootstrap 95% confidence intervals overlap across regimes under `3`-seed budget.
