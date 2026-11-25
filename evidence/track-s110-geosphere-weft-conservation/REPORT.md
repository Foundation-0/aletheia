# Track S110 Stage 3 (`H10c`) — Pure-`Init` `Lean 4.36.0` Exact Conservation Laws, Law-5 Obstructions & `Weft-Smith` Safety Certificate

**Author:** `@claude-architect` · **Protocols Pinned:** `PREREG-S110` (`2e645597...`), `PREREG-S110-AMENDMENT1` (`a41399fd...`), `PREREG-S111` (`6174c5fb...`), `PREREG-S109-AMENDMENT2` (`faf22506...`) · **Scope:** CPU-only formal & exact-rational pre-GPU gate (`0` GPU touch, `0` external downloads, `0` GitHub pushes, `0` IEEE-754 floats, `0` bare asserts, `PYTHONDONTWRITEBYTECODE=1`).

**Honest Scope & Novelty (`N1`, `n2_claims = 0`):**
- Skew-symmetric Cayley rotations, Birkhoff doubly-stochastic matrices, Darcy convex averaging, Bingham soft-thresholding, Householder reflections, and gated rollback state machines are classical prior art (`N0` individually).
- **Exact Scope Boundary (Zero Overclaim):** Every theorem in `GeosphereWeftConservation.lean` and every witness in `s110_geosphere_weft_oracle.py` certifies **per-factor exact finite-dimensional algebraic invariants and explicit Law-5 obstructions over $\mathbb{Z}$ / $\mathbb{Q}$ and pure-`Init` `Lean 4.36.0`**. This track does **NOT** claim unconstrained coupled multi-shell conservation in FP16/BF16 or 3-bpw quantized neural training; on the contrary, it formally proves the exact mathematical obstructions (`B1`, $O(n)\cap B_n \subseteq \mathrm{Perm}(n)$, `M1`, `B5`, `S50`, and `S111` `C_row` cancellation) that force the amended `sm_86` operator designs before any GPU training runs.

---

## 1. Pillar 1 — Workless Core Geodynamo Lorentz Isometry & Exact Rational Cayley Transport

- **Universal Worklessness & Arbitrary-Dimension Cayley Isometry (Theorems 1–4):** Over arbitrary dimension $n \in \mathbb{N}$ and any skew-symmetric $\Omega \in \mathbb{Z}^{n \times n}$ ($\Omega_{ij} = -\Omega_{ji}$), every diagonal entry vanishes ($\Omega_{ii} = 0$), radial work vanishes identically ($\langle h, \Omega h \rangle = 0$), and every solution to the cleared-denominator Cayley transport equation $(s I + \Omega) y = (s I - \Omega) x$ with $s \ne 0$ preserves squared Euclidean norm identically ($\|y\|^2 = \|x\|^2$).
- **Low-Cost Skew Generators & Closed-Form `sm_86` Repairs (Theorems 5–8):**
  - Rank-2 skew generators $\Omega = u v^\top - v u^\top$ are universally skew-symmetric in every dimension $n$ ($O(d)$ Woodbury-friendly; oracle witness at $d = 8$ gives $\langle h, \Omega h\rangle = 0$).
  - Closed-form **`2×2` block-diagonal Cayley** (`PREREG-S110-AMENDMENT1` Discovery 2: `4` FMAs per pair, zero matrix inversion) preserves $\|y^{\text{cl}}\|^2 = (1+w^2)^2\|x\|^2$ with $1 + w^2 \ge 1$ identically (oracle $d = 8$ witness: `norm_sq_in = norm_sq_out = 69`).
  - Universal Pfaffian invertibility of $I_4 + \Omega$ over $\mathbb{Z}^{4 \times 4}$: $\det(I_4 + \Omega) = 1 + (a^2+b^2+c^2+d^2+e^2+f^2) + (af - be + cd)^2 \ge 1$ (oracle witness: $\mathrm{Pf} = -3$, exact rational Gaussian elimination $\det = 45$).
  - Explicit dense $SO(4)$/Hopf quaternion Cayley isometry with `(b, c, d) = (1, 2, -1)` ($D = 7$, exact $(I_4 + \Omega) y = (I_4 - \Omega) x$, `norm_sq_in = norm_sq_out = 39`, `y_out = [3/7, -2/7, -43/7, -1]`).

## 2. Pillar 2 — Oceanic Mass Conservation, `B1` Causal Collapse, $O(n)\cap B_n$ & Darcy Contraction

- **Bidirectional Mass Conservation (Theorem 9):** Every column-stochastic (and doubly-stochastic) matrix $T$ with column sum $D$ satisfies $\sum_i (T x)_i = D \sum_j x_j$ identically for all $n \in \mathbb{N}$ (oracle $d = 4$ symmetric Birkhoff witness: `mass_in = mass_out = 16`).
- **Exact Law-5 Obstruction `B1` — Causal Doubly-Stochastic Collapse (`PREREG-S110-AMENDMENT1` Discovery 1, Theorem 10):** Proved universally for **all $n \in \mathbb{N}$**: any non-negative lower-triangular (causal) matrix whose rows AND columns sum to $D$ MUST satisfy $T_{ij} = D \cdot \delta_{ij}$ identically ($T = D \cdot I_n$ — zero cross-token attention!). Causal doubly-stochastic Sinkhorn is therefore permanently pruned.
- **Exact Law-5 Obstruction — $O(n) \cap B_n \subseteq \mathrm{Perm}(n)$ & Non-Commutation (`PREREG-S110-AMENDMENT1` Discovery 2, Theorems 11–12):**
  - Universally for all $n \in \mathbb{N}$, any non-negative matrix whose rows have $L^1$ sum $D$ and $L^2$ norm-squared $D^2$ satisfies $Q_{ij} \in \{0, D\}$ for every entry (permutation entries only — zero continuous doubly-stochastic orthogonal mixing on the same axis!).
  - Explicit $d = 2$ Cayley quarter-turn $Q$ and Birkhoff matrix $T = \frac{1}{4}\begin{pmatrix}1&3\\3&1\end{pmatrix}$ fail to commute (`QT[0,0] = -3/4`, `TQ[0,0] = 3/4`, $\|QT - TQ\|_F^2 = 9/2 > 0`), mandating feature-axis $SO(k)$ vs. position-axis separation.
- **Darcy Porous Aquifer / Diagonal EMA Contraction & `M1` Hypothesis Obstruction (Theorems 13–17):**
  - Under explicit non-expansive input hypothesis ($|K(x)| \le B$ or $\|K(x)\|^2 \le R$) and $0 \le \alpha \le D$, the cleared update $s' = (D - \alpha) s + \alpha y$ obeys both coordinate contraction $|s'| \le D B$ and the exact arbitrary-dimension parallelogram identity $\|s'\|^2 + \alpha(D-\alpha)\|s - y\|^2 = D((D-\alpha)\|s\|^2 + \alpha\|y\|^2) \le D^2 R$ (oracle $d = 4$, $\alpha = 1/8$: $\|s\|^2 = 30$, $\|y\|^2 = 18$, $\|s'\|^2 = 723/32$, residual $= 189/32$, strict error decay for $0 < \alpha$).
  - **Law-5 `M1` Obstruction (Theorem 16):** Without $\|K_{\text{porous}}\| \le 1$, Darcy escapes the prior bound (`D = 4, a = 1, s = 1, y = 2, B = 1 => s' = 5/4 > 1`).

## 3. Pillar 3 — Bingham Viscoplasticity, Repaired Vector-Proximal $\mathcal{S}_Y^H(u)$ & Ozone/Channel-2B Airlock

- **Scalar Bingham Proximal Regularity & `B5`/`S50` Obstructions (Theorems 18–24):**
  - Proves exact odd symmetry, sub-yield plug-flow zero-leakage ($|u| \le \tau \implies \operatorname{Bingham}_\tau(u) = 0$), $L^2$ non-expansion, strict shrinkage ($\tau > 0, u \ne 0$), and monotone 1-Lipschitz regularity.
  - Per-example max threshold $\tau_{\max} \ge \max_i |u_i|$ yields an exact Stagnant Lid ($Q = 0$ at $Y = 1$; oracle sweep over $Y \in \{0, 1/4, 1/2, 3/4, 1\}$ gives $\|v\|^2 = 30, 14, 5, 1, 0$), whereas $\tau = \sigma < \max_i|u_i|$ leaks (`bingham 1 2 = 1 != 0`, closing `B5`), and `bingham 1 (2 + (-1)) = 0 != 1 = bingham 1 2 + bingham 1 (-1)` proves `Track S50`'s `[Bingham, +] != 0` obstruction.
- **Council-Repaired Vector-Proximal Poloidal Bingham $\mathcal{S}_Y^H(u)$ (`PREREG-S110-AMENDMENT1` Discovery 3, Theorems 25–26):**
  - Cleared-denominator $\operatorname{polBingham}(D, g, u_{\text{pol}}, u_{\text{tor}}) = g\, u_{\text{pol}} + D\, u_{\text{tor}}$ (NO post-renorm!) preserves Poloidal/Toroidal Hodge orthogonality identically, satisfies exact Pythagorean energy $\|S_Y^H(u)\|^2 = g^2\|u_{\text{pol}}\|^2 + D^2\|u_{\text{tor}}\|^2 \le D^2\|u_{\text{pol}} + u_{\text{tor}}\|^2$ for $0 \le g \le D$, shuts poloidal flux cleanly to `0` at sub-yield plug flow ($g = 0$), AND commutes identically with every linear / $SO(k)$ map $Q$ in arbitrary dimension $n$ (contrasted with coordinate-wise Bingham breaking $SO(2)$ equivariance on $(2,0) \mapsto (1,1)$). Oracle $d = 4$ witness confirms exact $SO(4)$ equivariance under quaternion Cayley $Q_q$ (`total = 30`, mobile gate `3/5 -> 14`, plug `0 -> 5`).
- **Constructive Arbitrary-Dimension Cauchy–Schwarz & Ozone/Channel-2B Airlock (Theorems 27–28):**
  - Proves $(\langle w, d\rangle)^2 \le \|w\|^2 \|d\|^2$ constructively over arbitrary $\mathbb{Z}^n$ via incremental Lagrange sums of squares, yielding the exact frozen-weight ($\Delta W = 0$) airlock bound $(\langle w, \operatorname{Bingham}_\tau(\operatorname{clip}_{B_1}(\delta))\rangle)^2 \le \|w\|^2 \cdot n B_1^2 \le \|w\|^2 \cdot n B_2^2$ for $0 \le B_1 \le B_2$ (oracle $d = 4$, $\|w\|^2 = 15$: `25 <= 240 <= 960`).

## 4. Pillar 4 — `Weft-Smith` (`PREREG-S111`) Composed Triple Gate, Cumulative `C_row` & `O(1)` Rollback

- **Householder Reflection Invariance of `C_row` & Composed Cancellation Obstruction (Theorems 29–30, 37):**
  - Arbitrary-dimension Householder reflections satisfy $\|H_u^{\text{cl}} v\|^2 = \|u\|^4 \|v\|^2$, preserving `Track S31` `DPI` row-concentration $C_{\text{row}}(\Delta W) \le C_{\max}$ identically (oracle $3 \times 4$ witness: `row_norm_sq = [5, 10, 5]`, `C_row = 1/2 <= 3/5` before & after reflection).
  - **Law-5 `C_row` Cancellation Obstruction (`PREREG-S111` Convergence #1, Theorem 37):** Universally for every $a \ne 0$, two patches $(a, a)$ and $(a, -a)$ each obey $C_{\text{row}} = 1/2 \le 1/2$, yet their composed sum $(2a, 0)$ yields $C_{\text{row}} = 1 > 1/2$, proving $C_{\text{row}}$ and Frobenius drift MUST be gated on composed $\sum_k \Delta W_k$.
- **Capability Isolation, Non-Generative Mask, Triple-Gate Non-Redundancy & Multi-Cycle Cumulative Ledger (Theorems 31–36, 38):**
  - Every `weftStep` leaves Shell-1 Core `coreW`, Shell-2 `rewriterPsi`, and the non-generative capability mask (`canEmitText = false`, `canInvokeTool = false`) identically unchanged.
  - Failing Static, Receipt, `Shell_3` domain isolation, or held-out anchor non-regression restores the entire pre-state bit-for-bit (`post = pre`); dropping any single gate triggers exact rollback (non-redundancy).
  - Across arbitrary $T$-cycle sequences (`weftRun` & `weftLedgerRun`), Core, Rewriter, cumulative drift cap (`cumNormSq <= cumCapSq`), composed `cumCrowOk`, and monotonic `anchorErr` are preserved inductively, and every rejected patch preserves `kvEpoch` and full state equality (`post = pre`). Oracle `H11c` 50-cycle simulation commits `40/40` clean updates (`anchor_err: 100 -> 20`, `cum_norm_sq: 40 <= 50`) and rejects/rolls back `10/10` poisoned episodes (`100% >= 90%`).

---

## 5. Pure-`Init` `Lean 4.36.0` Theorem Table — `GeosphereWeftConservation.lean`

Zero imports, zero Mathlib, zero `sorry`, zero warnings, `rc = 0`, `0 B` stderr under allowlist-scrubbed `lean --stdin`, all **`38/38`** named `#print axioms` theorems $\subseteq \{\text{propext}, \text{Quot.sound}\}$ (`4 [] + 2 [propext] + 32 [propext, Quot.sound]`, `0` `Classical.choice`, `0` `sorryAx`; `23` `private theorem` helpers not counted, `61` total `theorem` declarations).

| # | Theorem | Exact Formal Statement Summary |
|---|---|---|
| 1 | `skew_diag_zero` | `∀ n Ω i, IsSkew n Ω → i < n → Ω i i = 0` |
| 2 | `geodynamo_lorentz_workless` | `∀ n Ω h, IsSkew n Ω → dotN n h (matVec n Ω h) = 0` |
| 3–4 | `geodynamo_cayley_isometry{_scaled,}` | `IsSkew n Ω → (s I + Ω) y = (s I - Ω) x → s * normSqN n y = s * normSqN n x` (`s ≠ 0 → normSqN n y = normSqN n x`) |
| 5 | `rank2_skew_is_skew` | `∀ n u v, IsSkew n (rank2Skew u v)` |
| 6 | `cayley2_exact_isometry` | `∀ w x0 x1, 1 ≤ 1 + w^2 ∧ cayley2Num0^2 + cayley2Num1^2 = (1 + w^2)^2 * (x0^2 + x1^2)` |
| 7 | `det4_I_plus_skew_pos` | `∀ a b c d e f, 1 ≤ 1 + (a^2+b^2+c^2+d^2+e^2+f^2) + (a*f - b*e + c*d)^2` |
| 8 | `cayley4_hopf_quat_isometry` | `∀ b c d x0..x3, 1 ≤ cayley4QDen ∧ ‖cayley4Q‖^2 = cayley4QDen^2 * ‖x‖^2` |
| 9 | `oceanic_column_stochastic_mass_conservation` | `(∀ j < n, colSum T j = D) → sumN n (matVec n T x) = D * sumN n x` |
| 10 | `causal_doubly_stochastic_is_identity` | `NonNeg ∧ LowerTriangular ∧ RowSum D ∧ ColSum D → ∀ i j < n, T i j = if i = j then D else 0` |
| 11 | `orthogonal_birkhoff_is_permutation_entries` | `NonNeg ∧ RowSum D ∧ RowNormSq D^2 → ∀ i j < n, Q i j = 0 ∨ Q i j = D` |
| 12 | `so2_birkhoff_non_commutation` | Explicit `d = 2` Cayley rotation `Q` and Birkhoff `T`: `(QT)_00 ≠ (TQ)_00 ∧ (QT)_11 ≠ (TQ)_11` |
| 13–15 | `darcy_{convex_coord_bound,euclidean_parallelogram_identity,l2_ball_invariance}` | Coordinate bound `|s'| ≤ D B`, exact arbitrary-dim parallelogram identity, and `L2` ball invariance `≤ D^2 R` |
| 16–17 | `darcy_{unbounded_K_obstruction,step_error_strict_contraction}` | `∃ D a s y B` escaping bound when `K` unbounded (`M1`); strict contraction for `0 < a` |
| 18–22 | `bingham_{odd,sub_yield_plug_zero,sq_nonexpansive,strict_shrinkage,one_lipschitz}` | Odd symmetry, sub-yield `|u| ≤ τ → 0`, `L2` contraction, strict shrinkage, monotone 1-Lipschitz |
| 23–24 | `bingham_{stagnant_lid_and_b5_obstruction,non_commuting_obstruction}` | `tauMax` Stagnant Lid `Q = 0` vs `bingham 1 2 ≠ 0` (`B5`); `bingham 1 (2 + -1) ≠ bingham 1 2 + bingham 1 (-1)` (`S50`) |
| 25–26 | `poloidal_bingham_{orthogonality_and_energy,so_equivariance}` | Repaired `S_Y^H`: orthogonality, Pythagorean energy `≤ D^2‖u‖^2`, plug `g=0`, exact `SO(k)` equivariance vs coord-ReLU failure |
| 27–28 | `cauchy_schwarz_int_n`, `ozone_channel2b_advection_airlock_bound` | Arbitrary-dim constructive Cauchy–Schwarz & frozen-weight Channel-2B airlock bound monotone in `B1 ≤ B2` |
| 29–30 | `householder_reflection_norm_sq`, `weft_crow_preserved_under_reflection` | Arbitrary-dim `‖H_u^{cl} v‖^2 = ‖u‖^4‖v‖^2` and exact `C_row(ΔW) ≤ C_max` invariance under reflection |
| 31–35 | `weft_step_{capability_isolation,non_generative_mask,rollback_soundness,commit_soundness}`, `weft_triple_gate_non_redundancy` | `ΔW_core = 0 ∧ Δψ = 0`, non-generative mask, `O(1)` rollback `post = pre`, commit iff all 3 gates + `Shell_3`, non-redundancy |
| 36–38 | `weft_multicycle_safety_invariant`, `weft_crow_cancellation_obstruction`, `weft_cumulative_budget_multicycle` | `T`-cycle invariance, universal `a ≠ 0` composed `C_row` cancellation attack, and cumulative ledger drift + `kvEpoch` rollback |

---

## 6. Post-Last-Edit Verification Receipts

All gates ran post-last-edit (CPU-only, `0` GPU touch, `PYTHONDONTWRITEBYTECODE=1`) with **`100.0% PASS`**:

- **Live Lean `4.36.0` (`--verify-lean`):** **`38/38`** theorems verified under allowlist-scrubbed `lean --stdin` (`4 [] + 2 [propext] + 32 [propext, Quot.sound]`, `0` `Classical.choice`, `0` `sorryAx`, `0` warnings, `0 B` stderr, `18/18` R13b `O(1)` `in_ident` static Lean rules `0` findings, `X1..X3` + literal-LF `Char` caught with `0` FP on identifier primes, live fake `Init.olean` hijack blocked).
- **Canonical Certificate (`0o600`, `7,794` B):** `payload_sha256 = 58e53e131b28a97d2a0e432f77870afc9f2ef2e65aaa14d2a31a8a839741151c`, `certificate_sha256 = 7975a8040f612a3dc95d8e83e20748aba8087c159ef3624a32343d28982a1f63`, `--standalone --json | cmp` **`EXACT`**, `--verify-pins` **`PINS_OK external=4`**.
- **Exhaustive `235`-Leaf Re-Signed Tamper Sweep (`SEC`/`FR0`/`FR1`):** **`705/705 = 100.0%`** (`235/235` × 3 surfaces, `0` bypasses, `0` crashes, `caller_immutable = True`, plus `4,500`-digit JSON & `10^5000` in-memory DoS rejected with typed `INT_DIGIT_LIMIT`).
- **Direct 4-Surface v2.1 `zone_b_fuzzer` (zero wrappers):** **`82/82 PASS`** (`CLI 25/25`, `FR1 19/19`, `FR0 19/19`, `SEC 19/19`; `bypasses = 0`, `crashes = 0`).
- **Official `aletheia-fast-mutate` (`--guards require_ok --workers 2 --timeout 180 --max-mutants 0`):** **`140/140 KILLED = 100.0%`** (`s110_geosphere_weft_oracle.py` `9/9`, `verify_s110_geosphere_weft_conservation.py` `131/131`; `survived = 0`, `truncated = False ×2`, `null_mutant = passed ×2`).
- **Whole-File AST `BoolOp` (`OP_SWAP + SUBCOND_DEL` across both `.py` targets):** **`28/28 KILLED = 100.0%`** (`0` survivors; `0` `BoolOp` nodes in oracle, `28/28` killed in verifier).
- **Multi-Env `-I` & Read-Only Directory Parity (`0` Skips):** **`15/15 OK ×7`** across isolated flags (`-I -B`, `-I -O -B`, `-I -B -W error`, `PYTHONHASHSEED=42`, `env -i HOME=/nonexistent`, and read-only directory), `--check ×6`, `--verify-lean`, `--standalone | cmp EXACT`, `--verify-pins PINS_OK external=4`, `PYC_OR_LAKE = 0`.
- **Dual `aletheia audit-check` (`aletheia-fix-lean-gates-v2` & `aletheia-fast-mutate`, `--strict-ancestors --safety-scan --lean-audit --scripts verify_s110_geosphere_weft_conservation.py test_s110_geosphere_weft_r5.py`):** **`PASS ×2`** (`files_scanned = 8`, `r4 = 2/2`, `lean_findings = 0`, `safety_findings = 0`, `bare_assert = 0`, `leaks = 0`, `crlf = 0`, `pycache = 0`).

---

## 7. Frozen Companion Manifest

| File | Lines | Bytes | Mode | SHA-256 |
|---|---:|---:|---:|---|
| `GeosphereWeftConservation.lean` | 1,651 | 79,093 | `0o644` | `1c0ed76de3eb6fe55e5f3e618a2ea12433ce4ffe4efe158af0a769bac5733fa8` |
| `lakefile.toml` | 5 | 131 | `0o644` | `ef07fba51abddc218a7e345d7032744615ff0e21af4bcabb9d0de01013dd02d4` |
| `lean-toolchain` | 1 | 25 | `0o644` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |
| `s110_geosphere_weft_oracle.py` | 833 | 33,181 | `0o644` | `82abfd3af2f6b99d7d0b2795bad6a324ed6aad02d4ff2776772fb32645982bd4` |
| `verify_s110_geosphere_weft_conservation.py` | 672 | 29,114 | `0o644` | `72bd6d0796defa705d6aa5e0f505a77438e381c80762e87cef3f4b3f80aefd62` |
| `test_s110_geosphere_weft_r5.py` | 800 | 41,589 | `0o644` | `78c82f9c2be0ffd40ea57c9980d88cb2fd6d415113131577d3b6288194b5debb` |
| `s110_geosphere_weft_certificate.json` | 1 | 7,794 | `0o600` | `2d27a8237cb47dd95f6aad09324d9487dbafe1f4363194a800239ea4e3b5eeba` |
