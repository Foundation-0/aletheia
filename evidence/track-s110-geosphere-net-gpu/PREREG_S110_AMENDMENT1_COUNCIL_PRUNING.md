# Preregistration Amendment 1 (`PREREG-S110-AMENDMENT1-COUNCIL-PRUNING`: Pre-GPU Mathematical Obstructions, `sm_86` Pruning & Exact Operator Repairs)

- **Status:** `LOCKED_PREREGISTRATION_AMENDMENT_1` *(2026-11-25; parent `PREREG-S110` SHA `2e645597e81a330159b2183caf670f685821a9451a37223a782936e88e30d0fe` and `PREREG-S109-AMENDMENT2` SHA `faf22506...` remain 100% immutable and unmutated)*
- **Source Pre-Flight Audits (Unanimous 3-Family Consensus, `#2814`):**
  1. `verification/reports/COLLAB-CLAUDE-S110-ABLATION-PREFLIGHT.md` (`BLOCK_KITCHEN_SINK` / `AMEND_BEFORE_GPU`)
  2. `verification/reports/COLLAB-GROK47-S110-GEOPHYSICS-PREFLIGHT.md` (`PRUNE_SHELLS_BEFORE_GPU`)
  3. `verification/reports/COLLAB-DSV41-S110-CONSERVATION-PREFLIGHT.md` (`NEEDS_OPERATOR_AMENDMENT`)

All 4 unanimous pre-GPU discoveries below are **mandatory overrides** before ANY GPU training runs under `EXP-Q10d` or `EXP-Q11a..b` (saving weeks of wasted GPU compute by catching exact algebraic impossibilities and `sm_86` bottlenecks BEFORE execution!):

---

## Discovery 1 — Exact Algebraic Obstruction: Causal Doubly-Stochastic Sinkhorn Collapses Identically to $I_n$ (PRUNED!)
- **Proof (Independently Derived by All 3 Families):** Any non-negative lower-triangular (causal) matrix $T \in \mathbb{R}_{\ge 0}^{n \times n}$ whose rows AND columns sum to `1` forces $T_{11} = 1 \implies T_{i1} = 0\ (\forall i > 1) \implies$ by induction **$T = I_n$ identically** (zero cross-token attention!). Moreover, iterative Sinkhorn on $L = 4096$ explodes autograd tape memory (`~5 GiB` VRAM on `8 GiB` RTX 3080).
- **Mandatory Action:** **PRUNE** causal Sinkhorn attention permanently from `H10a`/`H10b` (logged as exact pre-GPU algebraic obstruction; formalize `LowerTriangular ∧ DoublyStochastic → T = I_n` directly inside `Track S110` Stage 3 `H10c` `Lean 4.36.0`!). If Sinkhorn mass conservation is ever tested, it is strictly restricted to **non-causal / bidirectional fixed-width feature mixing or encoder prefix blocks**, never causal autoregressive attention.

## Discovery 2 — Exact Invariant Obstruction: $SO(d) \cap B_d = A_d$ & Dense Cayley `sm_86` Wall $\to$ **`2×2` Block-Diagonal Cayley**
- **Obstruction:** Orthogonal norm preservation ($SO(d)$) and Birkhoff doubly-stochastic mass conservation ($B_d$) intersect ONLY on even permutation matrices ($A_d$); furthermore, dense $d \times d$ Cayley inversion via cuSOLVER LU runs `10–40×` slower than `sm_86` Tensor-Core GEMMs and overflows `15M` parameter parity.
- **Mandatory Repair:** Replace dense $d \times d$ Cayley with **closed-form `2×2` block-diagonal Cayley / Givens rotations** on the **feature axis ONLY** (`4` FMAs per pair, zero matrix inversion, exact $\|Q h\|_2^2 = \|h\|_2^2$, `O(d)` params & FLOPs!).

## Discovery 3 — Exact `TerraCore` (`H9d`) Bingham Repair: Vector-Proximal Poloidal Operator $\mathcal{S}_Y^H(u)$
- **Obstruction Caught Independently by Grok 4.7 & DeepSeek V4.1 Flash:** Coordinate-wise Bingham ReLU followed by unit-sphere renormalization (`r = Norm(Bingham(u))`) breaks $SO(k)$ equivariance (up to `36.6%` / `14.8°`), erases the yield magnitude, and leaves Stagnant-Lid `Y=1` unreachable (`Φ(1)^32 = 4.96e-6` plug probability at `k=32`).
- **Exact Repaired Operator (Drop-In Override for `H9d` & `H10a`):**
  $$\mathcal{S}_Y^H(u) = \max\!\left(0,\; 1 - \frac{\tau_Y}{\|u_{\mathrm{pol}}\|_2}\right) u_{\mathrm{pol}} + u_{\mathrm{tor}}, \qquad \langle u_{\mathrm{pol}}, u_{\mathrm{tor}}\rangle = 0 \quad (\text{NO post-renorm!})$$
  - Strictly commutes with $SO(k)$, preserves Poloidal/Toroidal Hodge orthogonality identically, satisfies $[\mathcal{S}_Y^H, \delta_1] = 0$, and achieves an exact, clean Stagnant-Lid transition ($u_{\mathrm{pol}} \mapsto 0$) whenever $\|u_{\mathrm{pol}}\|_2 \le \tau_Y$!
  - Define $\tau_Y$ explicitly via frozen Stage-1 calibration quantiles of $\|u_{\mathrm{pol}}\|_2$ (`Y ∈ {0, 0.25, 0.50, 0.75, 1.0}` quantile grid — zero undefined $\sigma_u$!).

## Discovery 4 — Ruthless `sm_86` Shell Pruning (`9 -> 4` Surviving Silicon-Viable Mechanisms) & Statistical Gate Hardening
- **PRUNED Pre-GPU (`CS-03` / `S109` Conflict / `sm_86` Wall):**
  - Causal Sinkhorn Ocean Attention (`T = I_n` obstruction),
  - Dense $d \times d$ Cayley LU (`10–40×` Tensor-Core penalty),
  - Telluric Breakdown Direct Skip (`Core <-> Surface` skip violates `PREREG-S109-AMENDMENT1` zero-skip graph rule!),
  - Unpruned 9-shell bundle & unverified Ozone stand-alone shell (fold `Track S50` Channel-2B airlock + norm clamp cleanly into the baseline safety harness rather than counting it as a generative accuracy shell!).
- **4 Surviving `sm_86`-Viable Mechanisms (Tested Individually in `H10a`, Strictly Gated by `<2 min` CUDA Wall-Clock Microbenchmarks):**
  1. **`2×2` Block-Diagonal Cayley Feature Rotation** (closed-form `4` FMAs, norm-preserving loop routing),
  2. **Vector-Proximal Poloidal Bingham $\mathcal{S}_Y^H(u)$** (Hodge-orthogonal, $SO(k)$-equivariant, no post-renorm),
  3. **Diagonal Multi-Timescale Darcy EMA** (drop dense `K_porous`; pure diagonal exponential moving average `s_t = (1-α) s_{t-1} + α x_t` with explicit contractive `0 < α < 1`),
  4. **Integer ACT Geothermal Loop Plumes** ($r \in \{1..4\}$ at strict mean $\bar{r} = 2.0$) + **Fast Surface Draft (`MTP-8`)**.
- **Statistical & Audit Gate Hardening (`§PRUNE-1..6`, `§CS-08`):**
  - Enforce **Holm–Bonferroni multiple-comparison correction** across all Stage-1 & leave-one-shell-out tests (fixing the `44%` unadjusted family-wise FP rate at `1.5 SE` across 9 shells!).
  - Measure counterfactual $h^{(r)}$ state-patching faithfulness **pre-normalization (`pre-𝒩`)** so `𝒩` + $\sigma_2(P)$ contraction across `r=4` loops does not bias the audit gate toward NULL.
  - Enforce hard **`sm_86` wall-clock microbenchmark pre-gate**: any candidate operator adding `> 15%` kernel wall-clock overhead over fused `BF16` GEMM at identical FLOPs is pruned before multi-seed training!
