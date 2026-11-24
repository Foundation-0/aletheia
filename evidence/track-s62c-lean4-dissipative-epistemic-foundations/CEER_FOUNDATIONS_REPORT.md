# Pure-Init Lean 4.36.0 Universal Foundations for Calculational-Experimental Epistemic Recursion (CEER)

## 1. OWN_TERMS_FIRST: Mathematical Scope & Honest Novelty Accounting

This package delivers a self-contained, zero-Mathlib **Lean 4.36.0** (`Init`-only) formalization of **24 kernel-checked theorems** (**21 universal `∀` theorems** over unbounded `Int`/`Nat`/`List Int`/`Fin` domains plus **3 non-vacuous concrete witness bundles**) across three standalone Lean modules, paired with a pure-$\mathbb{Z}/\mathbb{Q}$ Python verifier, adversarial R1–R5 test suite, and canonical `0o600` certificate.

Each mathematical foundation is formulated and proved first in its own native algebraic structure before linking to experimental falsification:

1. **Module 1 (`CEERFoundations/Module1_UniversalHysteresisAndConcavity.lean`) — Universal Zero-Area Memoryless-Loop Hysteresis, Affine Collinearity & Lipschitz Phase-Cliff Refutation:**
   - **Native formulation:** On arbitrary integer coordinate trajectories $(x_i, y_i) \in \mathbb{Z}^2$, define the exact integer discrete Green's-theorem trapezoid signed area $A = \sum_i (y_{i+1} + y_i)(x_{i+1} - x_i)$. Path reversal negates signed area identically, so for **EVERY** single-valued memoryless law $g : \mathbb{Z} \to \mathbb{Z}$ and **EVERY** symmetric up-then-down lever sweep $x_0, \dots, x_k, x_k, \dots, x_0$, the signed area vanishes identically (`memoryless_symmetric_loop_zero_area`). Consequently, ANY empirical trace on a symmetric sweep with nonzero signed area ($A \ne 0$) unconditionally disproves `∃ g : Int → Int, ...` across the entire infinite space of memoryless cooling laws (`hysteresis_disproves_all_single_valued`).
   - **Affine & Lipschitz refutation:** Every affine law $g(x) = a + b x$ has identically zero trapezoid signed area around **EVERY** closed loop even on arbitrary asymmetric grids (`affine_arbitrary_closed_loop_zero_area`), vanishing second difference on midpoint triples (`affine_vanishing_second_diff`), and exact cross-multiplied slope equality across arbitrary triples (`affine_general_collinearity`). Hence any three non-collinear integer sensor readings unconditionally refute ALL affine laws (`noncollinear_disproves_all_affine`), and any single two-point integer jump $|e_2 - e_1| > L |s_2 - s_1|$ across a working-set boundary unconditionally refutes ALL $L$-Lipschitz laws (`lipschitz_cliff_disproves_all_L`).
   - **Non-vacuous witness bundle (`ceer_cycle_hysteresis_concavity_cliff_witnesses`):** Thermal sweep `[15, 25, 35, 45]` with trace `[48, 56, 65, 75, 75, 69, 62, 53]` has exact signed area `-250 ≠ 0`; concave trace `(15, 150), (30, 270), (45, 340)` has second difference `-50` (slopes `8` vs `14/3`); L3→DRAM jump `(16, 120) -> (24, 480)` has slope `45 > 40`.

2. **Module 2 (`CEERFoundations/Module2_UniversalSchurDarkModeDrop.lean`) — Universal Exact Schur-Complement Dark-Mode Variance Reduction & Stage-A Affine Gauge Invariance:**
   - **Native formulation:** On a $(1+1)$ block Gram matrix $\begin{pmatrix} a & b \\ b & d \end{pmatrix}$ with $d > 0$, cleared-denominator Schur residual $d a - b^2 \le d a$ always, with strict drop iff $b \ne 0$ (`schur_1plus1_variance_drop_universal`). On a $(1+2)$ symmetric block Gram matrix with $2 \times 2$ SPD sensor block $D$ ($d_{11} > 0, \det D > 0$), completion of squares on $b^\top \operatorname{adj}(D) b$ proves $\det D \cdot a - \mathrm{drop}_{12} \le \det D \cdot a$ universally, with strict drop iff $b_1 \ne 0 \lor b_2 \ne 0$ (`schur_1plus2_variance_drop_universal`).
   - **Exact 2-stage nested unveiling law (`schur_monotonic_nested_sensor_unveiling`):** Proves the exact universal polynomial identity
     $$d_{11} (\det D \cdot a - \mathrm{drop}_{12}) = \det D \cdot (d_{11} a - b_1^2) - (d_{11} b_2 - d_{12} b_1)^2,$$
     showing $S_2 \le S_1 \le S_0$ universally, with strict second-stage drop iff partial cross-coupling $d_{11} b_2 - d_{12} b_1 \ne 0$. Extended to $(2+1)$ multi-output trace and universal Loewner contraction (`schur_2plus1_trace_and_loewner_drop`).
   - **Universal Stage-A coordinate/affine gauge invariance:** Exact integer centered covariance $C(x, y) = n \sum x_i y_i - (\sum x_i)(\sum y_i)$ is identically invariant under arbitrary additive shifts (`centered_cov_shift_invariant`) and bilinearly homogeneous under arbitrary integer scalings (`centered_cov_scale_homogeneous`). Therefore for **EVERY** equal-length integer dataset and **EVERY** positive affine rescaling $x \mapsto c_x x + d_x, y \mapsto c_y y + d_y$ ($c_x, c_y > 0$), the exact rational Schur residual ratio $\eta = 1 - r^2 = (V_x V_y - C_{xy}^2) / (V_x V_y)$ is **identically invariant** (`stageA_affine_gauge_invariance_eta`). Concrete witness `ceer_s53_dark_mode_drop_witness` certifies strict drop $S_0 = 100 > S_1 = 64 > S_2 = 60$ ($\eta: 1 \to 16/25 \to 3/5$) and exact gauge invariance under $(7x - 13, 5y + 29)$ with zero axioms `[]`.

3. **Module 3 (`CEERFoundations/Module3_UniversalLaplacianThermalCoupling.lean`) — Universal 8-Core Die-Chain Graph-Laplacian M-Matrix Monotonicity & Anisotropic Heat-Pipe Falsification:**
   - **Native formulation:** On the 8-core die path graph with uniform positive thermal conductance $g > 0$, convective sink $h > 0$, and positive core-0 heat injection $q > 0$, any steady state $(g L + h I) T = q e_0$ satisfies exact energy conservation $h \sum_{i=0}^7 T_i = q$ (`die8_laplacian_energy_conservation`), strict far-end positivity $T_7 > 0$ (`die8_far_end_strictly_positive`), strict monotone temperature decay $T_0 > T_1 > \dots > T_7 > 0$ (`die8_laplacian_strict_monotonicity`), strict discrete flux decay / convexity $T_0 - T_1 > T_1 - T_2 > \dots > T_6 - T_7 > 0$ (`die8_laplacian_strict_flux_decay`), and universal pairwise ordering $\forall i < j,\ T_i > T_j$ (`die8_pairwise_distance_monotonicity`).
   - **Non-vacuous constructive existence & falsification:** Explicitly constructs the exact integer Green's column `greensCol8 g h` and heat input `greensQ8 g h > 0` satisfying $(g L + h I) T = q e_0$ for **ALL** $(g, h) \in \mathbb{Z}_{>0}^2$ (`die8_greens_exact_solution_exists`). Conversely, ANY empirical temperature inversion $T_j \ge T_i$ ($i < j$) unconditionally disproves ALL isotropic 1D die-chain models (`anisotropic_coupling_refutes_isotropic_chain`). Concrete witness `die8_g2_h1_and_heatpipe_refutation` verifies the exact `g = 2, h = 1` Green's column `[10923, 5462, 2732, 1368, 688, 352, 192, 128]` (`q = 21845`, $T_1 / T_7 = 2731/64$) and refutes all isotropic $(g, h, q) > 0$ on an anisotropic heat-pipe profile with $T_7 = 64 > 58 = T_1$.

### Honest Novelty Classification (`N0` vs. `N1`)

- **`N0` Classical Foundations (Explicitly Credited):**
  - Green (1828): discrete path-integral signed area and path-reversal cancellation.
  - Lipschitz (1864): Lipschitz continuity and finite-difference slope bounds.
  - Schur (1917) & Haynsworth (1968): Schur complement inertia and nested variance reduction.
  - Pearson (1895): affine gauge invariance of squared correlation and residual variance ratio.
  - Ostrowski (1937) & Varga (1962): tridiagonal M-matrices and discrete Green's function positivity.
  - de Moura & Ullrich (2021): The Lean 4 theorem prover and core `Init` kernel.
- **`N1` Constructive Formalization & Engineering Contribution:**
  - Zero-import pure-`Init` Lean 4.36.0 kernel mechanization (21 universal `∀` theorems + 3 non-vacuous witness bundles, zero Mathlib, zero `sorry`/`admit`/`axiom`/`native_decide`, zero warnings) connecting raw integer experimental counterexamples unconditionally to kernel-checked refutations of infinite hypothesis classes, coupled to a Zone-B hardened pure-$\mathbb{Z}/\mathbb{Q}$ verifier and canonical `0o600` certificate.

---

## 2. Live Lean 4.36.0 Kernel & `#print axioms` Receipts

- **Toolchain (`lean-toolchain`):** `leanprover/lean4:v4.36.0`
- **Live Compiler Version:** `Lean (version 4.36.0, x86_64-unknown-linux-gnu, commit 611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9, Release)`
- **Standalone Kernel Compilation:** `3/3` modules exited `0`, `0` stderr bytes, `0` warnings, `0` non-`Init` imports (`5.59 s` total).
- **Clean-Copy `lake build`:** `Build completed successfully (8 jobs)`, exit code `0`, `0` warnings, zero `.lake/` artifacts retained.
- **Axiom Audit:** All `24/24` theorems depend strictly on subsets of `{propext, Classical.choice, Quot.sound}` (`0` `sorryAx`, `0` `Lean.ofReduceBool`, `0` `Lean.trustCompiler`).

| Module | Theorem | Kind | `#print axioms` |
|---|---|---|---|
| `Module1_UniversalHysteresisAndConcavity` | `memoryless_symmetric_loop_zero_area` | Universal (`∀ g xs`) | `[propext, Quot.sound]` |
| `Module1_UniversalHysteresisAndConcavity` | `hysteresis_disproves_all_single_valued` | Universal (`∀ xs ys`) | `[propext, Quot.sound]` |
| `Module1_UniversalHysteresisAndConcavity` | `affine_arbitrary_closed_loop_zero_area` | Universal (`∀ a b x0 xs`) | `[propext, Quot.sound]` |
| `Module1_UniversalHysteresisAndConcavity` | `affine_vanishing_second_diff` | Universal (`∀ a b p1 p2 p3`) | `[propext, Quot.sound]` |
| `Module1_UniversalHysteresisAndConcavity` | `affine_general_collinearity` | Universal (`∀ a b p1 p2 p3`) | `[propext, Quot.sound]` |
| `Module1_UniversalHysteresisAndConcavity` | `noncollinear_disproves_all_affine` | Universal (`∀ p1..y3`) | `[propext, Quot.sound]` |
| `Module1_UniversalHysteresisAndConcavity` | `lipschitz_cliff_disproves_all_L` | Universal (`∀ L s1 s2 e1 e2`) | `[propext, Quot.sound]` |
| `Module1_UniversalHysteresisAndConcavity` | `ceer_cycle_hysteresis_concavity_cliff_witnesses` | Non-vacuous witness bundle | `[propext, Quot.sound]` |
| `Module2_UniversalSchurDarkModeDrop` | `schur_1plus1_variance_drop_universal` | Universal (`∀ a b d`) | `[propext, Classical.choice, Quot.sound]` |
| `Module2_UniversalSchurDarkModeDrop` | `schur_1plus2_variance_drop_universal` | Universal (`∀ a b1 b2 D`) | `[propext, Quot.sound]` |
| `Module2_UniversalSchurDarkModeDrop` | `schur_monotonic_nested_sensor_unveiling` | Universal (`∀ a b1 b2 D`) | `[propext, Classical.choice, Quot.sound]` |
| `Module2_UniversalSchurDarkModeDrop` | `schur_2plus1_trace_and_loewner_drop` | Universal (`∀ A b d w`) | `[propext, Classical.choice, Quot.sound]` |
| `Module2_UniversalSchurDarkModeDrop` | `centered_cov_shift_invariant` | Universal (`∀ xs ys dx dy`) | `[propext, Classical.choice, Quot.sound]` |
| `Module2_UniversalSchurDarkModeDrop` | `centered_cov_scale_homogeneous` | Universal (`∀ xs ys cx cy`) | `[propext]` |
| `Module2_UniversalSchurDarkModeDrop` | `stageA_affine_gauge_invariance_eta` | Universal (`∀ xs ys cx dx cy dy`) | `[propext, Classical.choice, Quot.sound]` |
| `Module2_UniversalSchurDarkModeDrop` | `ceer_s53_dark_mode_drop_witness` | Non-vacuous witness bundle | `[]` *(zero axioms)* |
| `Module3_UniversalLaplacianThermalCoupling` | `die8_laplacian_energy_conservation` | Universal (`∀ g h q T`) | `[propext, Quot.sound]` |
| `Module3_UniversalLaplacianThermalCoupling` | `die8_far_end_strictly_positive` | Universal (`∀ g h q T`) | `[propext, Quot.sound]` |
| `Module3_UniversalLaplacianThermalCoupling` | `die8_laplacian_strict_monotonicity` | Universal (`∀ g h q T`) | `[propext, Classical.choice, Quot.sound]` |
| `Module3_UniversalLaplacianThermalCoupling` | `die8_laplacian_strict_flux_decay` | Universal (`∀ g h q T`) | `[propext, Classical.choice, Quot.sound]` |
| `Module3_UniversalLaplacianThermalCoupling` | `die8_pairwise_distance_monotonicity` | Universal (`∀ g h q T i j`) | `[propext, Classical.choice, Quot.sound]` |
| `Module3_UniversalLaplacianThermalCoupling` | `anisotropic_coupling_refutes_isotropic_chain` | Universal (`∀ T i j`) | `[propext, Classical.choice, Quot.sound]` |
| `Module3_UniversalLaplacianThermalCoupling` | `die8_greens_exact_solution_exists` | Universal (`∀ g h > 0`) | `[propext, Quot.sound]` |
| `Module3_UniversalLaplacianThermalCoupling` | `die8_g2_h1_and_heatpipe_refutation` | Non-vacuous witness bundle | `[propext, Classical.choice, Quot.sound]` |

---

## 3. Verifier Hardening & Reproducibility

- **Pure-$\mathbb{Z}/\mathbb{Q}$ Trust Path:** `ceer_foundations_audit.py` uses Python 3 standard library only (`int`, `fractions.Fraction`, `hashlib`, `hmac`, `os`, `subprocess`), with zero IEEE-754 floats, zero bare `assert`s, zero `.isdigit()`, zero `islink`/`is_symlink`, and zero mathematical RNG.
- **Offline Static Lean 4 Proof-Envelope Gate:** Strips nested `/- ... -/` block comments, `--` line comments, plain `"..."` strings, Lean 4 `Char` literals (`'"'`, `'\"'`, `'\''` guarded against identifier primes), raw strings (`r"..."` / `r#"..."#`), and interpolated strings (`s!"{...}"` / `m!"{...}"` / `f!"{...}"`, preserving `{...}` code spans for scanning while failing closed on unterminated comments/strings); normalizes ASCII French-guillemet identifiers (`«...»`); blocks `sorry`, `admit`, `axiom`, `unsafe`, `native_decide`, `sorryAx`, `ofReduceBool`, `trustCompiler`, `debug.skipKernelTC`, `@[extern]`/`@[implemented_by]`, `partial`, non-`Init`/`Std` imports, bound `DecideConfig` records with non-false `native`, and runs a single-pass $O(n)$ balanced-paren scanner enforcing a fail-closed plain-record-literal allowlist on `decide (config := ...)` (blocking positional `⟨...⟩`, `.mk`, `with`, indirect variables, field-punned `{ native }`, and `:+`/`,+` infix escapes).
- **Zone-B Filesystem & CLI Defense:** Atomic `dir_fd` traversal (`O_RDONLY | O_DIRECTORY | O_NOFOLLOW`), `(st_dev, st_ino)` `$PWD` inode parity check, verified root-owned macOS Darwin `/var`/`/tmp`/`/etc -> /private/*` prefix normalization, `st_nlink == 1` enforcement on both reads and durable `0o600` atomic writes rejecting symlink/non-regular/hardlink targets and races, exact-bool `verify_live_lean` enforcement, wrapped `OSError`/`UnicodeDecodeError`/`RuntimeError`/`TimeoutExpired`/surrogate handling, canonical byte-exact certificate verification via `hmac.compare_digest`, and fail-closed typed CLI rejecting leading-dash targets and non-string `argv`.
- **Reproduce Locally:**
  ```bash
  python3 -I -B ceer_foundations_audit.py --check ceer_foundations_certificate.json
  python3 -I -B test_ceer_foundations_r5.py -v
  ```

---

## 4. Frozen File Manifest

- **Certificate `payload_sha256`:** `626d22639b78b0f25dec45a8490d717c42863a619002894e9a81c5a51fdeb1a4`
- **Certificate `certificate_sha256`:** `c4e210fa2cc1b15c8fc8f8608d45d15b247e3b2fd799a2b7a4c2476db51218f6`

| File | Lines | Bytes | Mode | SHA-256 |
|---|---:|---:|---:|---|
| `lean-toolchain` | `1` | `25` | `0o644` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |
| `lakefile.toml` | `11` | `311` | `0o644` | `70b466dbc034bd7a21405d4c29a474bff75490b64759282f6b2b70d10d292daa` |
| `CEERFoundations/Module1_UniversalHysteresisAndConcavity.lean` | `280` | `12,958` | `0o644` | `11ca0ce15470ce87dcc97e54ab9582b550615da2d26d45f74f2b92323438adb9` |
| `CEERFoundations/Module2_UniversalSchurDarkModeDrop.lean` | `503` | `24,166` | `0o644` | `89d280c8b5d4e771f73a0d0da409381aa48498895a68a06646a122fb6922ecd4` |
| `CEERFoundations/Module3_UniversalLaplacianThermalCoupling.lean` | `410` | `21,160` | `0o644` | `0ea5bda245895b0b87b3dac6494c207d19f83dfd51a56f46fd112d4daeebdd6c` |
| `ceer_foundations_audit.py` | `1,734` | `71,970` | `0o644` | `3b4585e0cb6ce504f4f85810440b760838cd934ae23dab465a351faf8a92458b` |
| `test_ceer_foundations_r5.py` | `967` | `56,634` | `0o644` | `190d197157392bc934b886acc8eadd7b0a810948f605823bc862dd30d583b0d9` |
| `ceer_foundations_certificate.json` | `1` | `7,640` | `0o600` | `2596be5caf772da6bbf7ab2be2c9c60a64133f16b996db61d2c8a463d13e1e1b` |
| `CEER_FOUNDATIONS_REPORT.md` | *(this file)* | — | `0o644` | *(self-documenting report)* |
