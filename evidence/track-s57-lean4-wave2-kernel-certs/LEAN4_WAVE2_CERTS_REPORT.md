# Pure-Init Lean 4.36.0 Kernel-Checked Certificates for Wave 2 Exact-Arithmetic Theorems

## 1. OWN_TERMS_FIRST: Mathematical Scope & Honest Novelty Accounting

This package delivers a self-contained, zero-Mathlib **Lean 4.36.0** (`Init`-only) formalization of **24 kernel-checked theorems** (11 universal parametric theorems over unbounded `Int`/`Nat`/`List Int`/`Fin` domains plus 13 exact integer/rational witness theorems) across three standalone Lean modules, paired with a pure-$\mathbb{Z}/\mathbb{Q}$ Python verifier, adversarial test suite, and canonical `0o600` certificate.

Each mathematical domain is stated and proved first in its own native algebraic terms:

1. **Module 1 (`Wave2KernelCerts/Theorem1_BallF64CauchySchwarz.lean`) — Discrete $L_2$-Ball Accumulation Envelope & Construction-A Even-Norm Parity:**
   - **Native formulation:** On arbitrary-length integer lists $v \in \mathbb{Z}^n$, Cauchy–Schwarz gives $(\sum_i |v_i|)^2 \le n \sum_i v_i^2$ (`int_list_cauchy_schwarz`). On any Construction-A lattice $v = c + 2z$ over an even-weight binary code $C$, $(c_i + 2z_i)^2 \equiv c_i \pmod{2}$, so $\sum_i v_i^2 \equiv \sum_i c_i \equiv 0 \pmod{2}$ (`constructionA_even_parity_norm_sq`), tightening every odd squared-norm cap $2b+1$ identically to $2b$ (`odd_bound_tightens_to_even`).
   - **Application to quantized dot-product accumulation:** For $n = 128$, even $\|v\|_2^2 \le 5213 \implies \|v\|_2^2 \le 5212 \implies \|v\|_1 \le 816$ (`ball_72B_sumAbs_le_816`), yielding an exact `> 10×` IEEE-754 `binary64` consecutive-integer margin ($2^{53} / (816 \cdot 65504 \cdot 2^{24}) = 1048576 / 104397 > 10$, `ball_72B_f64_margin_gt_10x`) even though individual coordinates reach $\max |v_i| = 72 > 64$ (`ball_72B_max_coord_72_gt_64_witness`, where a naive $L_\infty \le 64$ box breaks). For $n = 32$, even $\|v\|_2^2 \le 1207 \implies \|v\|_2^2 \le 1206 \implies \|v\|_1 \le 196$ (`ball_18B_sumAbs_le_196`), giving `> 41×` headroom ($4194304 / 100303 > 41$, $\max |v_i| = 34$, `ball_18B_f64_margin_gt_41x`).

2. **Module 2 (`Wave2KernelCerts/Theorem2_ZeroDWStateTransport.lean`) — Rank-1 Delta-Rule State Transport, Iso-Frobenius Separation & Discrete $S^2$ Cohomological Obstruction:**
   - **Native formulation:** Every $4 \times 4$ rank-1 integer matrix $M = a b^\top$ satisfies $\operatorname{tr}((M^\top M)^2) = (\operatorname{tr}(M^\top M))^2$ identically (`rank1_schatten_s4_exact_one`, i.e., basis-invariant Schatten-4 dominance $S_4 = 1$). Under the cleared-denominator delta update $S' = d^2 S + (d v - S k) k^\top$ for any rational unit key $k/d$ ($\|k\|_2^2 = d^2$), $S' k = d^3 v$ identically with zero parameter-weight mutation ($\Delta W = 0$, `gdn2_unit_key_exact_overwrite`).
   - **Concrete witnesses & $S^2$ Gauss–Stokes vs. ReLU:** On the Hadamard memory state $S_4 = H_4$ with Pythagorean key $k_5 = (3/5, 4/5, 0, 0)$ and value $v_5 = (0, 6, 0, 0)$, the readout margin flips from $+2$ to $-83/25$ ($\Delta m = -133/25$, $\operatorname{ReLU}: 2 \to 0$) at $\|\Delta S\|_F^2 = 212/5$ and $S_4 = 1$ (`gdn2_poison_margin_flip_zero_dw`). A matched-Frobenius rank-2 nullspace perturbation carries identical $\|\Delta S\|_F^2 = 212/5$ yet $S_4 = 35657/70225 < 1$ and zero margin shift (`iso_frobenius_blindness_212_5`). In 2D, the same delta rule ($\alpha = 1/2, \beta = 1, k = (1,0), v = (1/4,0)$) advects the ReLU yield wall from $x = 1$ to $x = 4$ (displacement $3$) and flips margin $+1/2 \to -5/8$ ($\Delta m = -9/8$, `yield_wall_advection_zero_dw`). On the closed $S^2$ cube cell complex ($V = 8, E = 12, F = 6, \chi = 2$), $d_1 d_0 = 0$, $\sum_f d_1(f, e) = 0$, and Hodge poloidal/toroidal fields are orthogonal (`s2_cube_chain_complex_and_euler`); universally over EVERY integer edge flux $u : \operatorname{Fin}\,12 \to \mathbb{Z}$, total outward divergence vanishes identically $\sum_v (\delta_1 u)_v = 0$ (`s2_cube_universal_gauss_stokes`), whereas piecewise-linear ReLU carries global divergence residual $-4 \ne 0$ and commutator sum $\sum_v [\operatorname{ReLU}, \delta_1](u_{\mathrm{asym}})_v = 13 \ne 0$ (`s2_cube_relu_obstruction_and_commutator`).

3. **Module 3 (`Wave2KernelCerts/Theorem3_SchurMetrologyObstruction.lean`) — Universal Symmetric $4 \times 4$ Sylvester Positive-Definiteness, Coupled Schur-Complement Obstruction & Dual-Sensor Power Closure:**
   - **Native formulation:** By exact integer completion of squares on symmetric $2 \times 2$, $3 \times 3$, and $4 \times 4$ matrices, positive Schur-reduction pivots imply strict positive-definiteness universally over $\mathbb{Z}^2 \setminus \{0\}$ (`sym2_sylvester_spd`) and $\mathbb{Z}^4 \setminus \{0\}$ (`sym4_sylvester_spd`).
   - **Application to coupled plant-metrology admissibility:** The diagonal plant gate admits $u_c = (901053, 879564, 696000, 379589)$ inside $\|u_c - u_0\|_2^2 = 37{,}525{,}000{,}000 \le 198{,}947^2 = 39{,}579{,}908{,}809$ with every coordinate below $1{,}000{,}000$ (`optifab_diagonal_plant_gate_admits_uc`), and the $2 \times 2$ sensor precision block $D$ is universally SPD (`optifab_sensor_block_D_spd`, $\det D_{\mathrm{num}} = 147{,}295{,}492{,}035{,}060 > 0$). Computing the exact cleared-integer Schur complement $S_{\mathrm{uncal}} = A(u_c) - \tfrac{1}{2} B D^{-1} B^\top$ directly inside the Lean 4 kernel yields Sylvester pivot signs $(+, +, +, -)$, i.e., inertia $(3, 0, 1)$ (`optifab_uncalibrated_schur_minors_3_0_1`), witnessed by the low-integer vector $w = (0, 3, 0, 1)$ satisfying $w^\top A w = 340867/200000 > 0$, $w^\top S_{\mathrm{uncal}} w = -36136568696489/758863946600000 < 0$, and $w^\top S_{\mathrm{cal}} w = 628610907866011/758863946600000 > 0$ (`optifab_uncalibrated_negative_witness`). Calibration ($\eta = 1$, coupling $\tfrac{1}{4} B D^{-1} B^\top$) yields strictly positive pivots $(+, +, +, +)$ and universal strict positive-definiteness $\forall x \in \mathbb{Z}^4 \setminus \{0\},\ x^\top S_{\mathrm{cal}} x > 0$ (`optifab_calibrated_schur_universal_spd`). Finally, single-sensor Venturi utilisation $(2311/28875)/(13/125) = 2311/3003 < 1$ implies dual-sensor closure $k \cdot 3003 \ge 4622 \iff k \ge 2$ (`venturi_collars_min_two_universal`).

### Honest Novelty Classification (`N0` vs. `N1`)

- **`N0` Classical Foundations (Explicitly Credited):**
  - Cauchy (1821) / Schwarz (1885): discrete $L_1$–$L_2$ Cauchy–Schwarz inequality.
  - IEEE Std 754-2008: `binary16` and `binary64` exact consecutive-integer significand ceiling ($2^{53}$).
  - Conway & Sloane (1999): Construction-A lattices over even-weight binary codes.
  - Yang et al. (2024): Gated Delta Networks (rank-1 state-transport delta rule).
  - Desbrun et al. (2005): Discrete Exterior Calculus and discrete Gauss–Stokes on closed surfaces.
  - Schur (1917) & Sylvester (1852): Schur complements, leading principal minors, and quadratic-form inertia.
  - de Moura & Ullrich (2021): The Lean 4 theorem prover and core `Init` kernel.
- **`N1` Constructive Formalization & Engineering Contribution:**
  - Zero-import pure-`Init` Lean 4.36.0 kernel mechanization (zero Mathlib, zero `sorry`/`admit`/`axiom`/`native_decide`, zero compiler warnings) unifying 11 universal parametric theorems and 13 exact concrete witnesses across quantized $L_2$-ball accumulation, zero-$\Delta W$ state transport / discrete $S^2$ cohomology, and coupled Schur-complement metrology with full universal Sylvester SPD proofs in pure integer arithmetic, coupled to a Zone-B hardened pure-$\mathbb{Z}/\mathbb{Q}$ verifier and canonical `0o600` certificate.

---

## 2. Live Lean 4.36.0 Kernel & `#print axioms` Receipts

- **Toolchain (`lean-toolchain`):** `leanprover/lean4:v4.36.0`
- **Live Compiler Version:** `Lean (version 4.36.0, x86_64-unknown-linux-gnu, commit 611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9, Release)`
- **Standalone Kernel Compilation:** `3/3` modules exited `0`, `0` stderr bytes, `0` compiler warnings, `0` non-`Init` imports (`4.37 s` total wall clock).
- **Clean-Copy `lake build`:** `Build completed successfully (8 jobs)`, exit code `0`, `0` warnings, zero `.lake/` artifacts retained in the deliverable directory.
- **Axiom Audit:** All `24/24` theorems depend strictly on subsets of `{propext, Classical.choice, Quot.sound}` (`2/24` depend on zero axioms `[]`; `0` `sorryAx`, `0` `Lean.ofReduceBool`, `0` `Lean.trustCompiler`).

| Module | Theorem | Kind | `#print axioms` |
|---|---|---|---|
| `Theorem1_BallF64CauchySchwarz` | `int_list_cauchy_schwarz` | Universal (`∀ l : List Int`) | `[propext, Classical.choice, Quot.sound]` |
| `Theorem1_BallF64CauchySchwarz` | `constructionA_even_parity_norm_sq` | Universal (`∀ c z : List Int`) | `[propext, Classical.choice, Quot.sound]` |
| `Theorem1_BallF64CauchySchwarz` | `odd_bound_tightens_to_even` | Universal (`∀ n b : Int`) | `[propext, Quot.sound]` |
| `Theorem1_BallF64CauchySchwarz` | `ball_72B_sumAbs_le_816` | Universal (`∀ v : List Int`) | `[propext, Classical.choice, Quot.sound]` |
| `Theorem1_BallF64CauchySchwarz` | `ball_72B_f64_margin_gt_10x` | Universal (`∀ v a`) | `[propext, Classical.choice, Quot.sound]` |
| `Theorem1_BallF64CauchySchwarz` | `ball_72B_max_coord_72_gt_64_witness` | Concrete sharp witness | `[]` *(zero axioms)* |
| `Theorem1_BallF64CauchySchwarz` | `ball_18B_sumAbs_le_196` | Universal (`∀ v : List Int`) | `[propext, Classical.choice, Quot.sound]` |
| `Theorem1_BallF64CauchySchwarz` | `ball_18B_f64_margin_gt_41x` | Universal (`∀ v a`) | `[propext, Classical.choice, Quot.sound]` |
| `Theorem2_ZeroDWStateTransport` | `rank1_schatten_s4_exact_one` | Universal (`∀ a b : Fin 4 → Int`) | `[propext, Quot.sound]` |
| `Theorem2_ZeroDWStateTransport` | `gdn2_unit_key_exact_overwrite` | Universal (`∀ S k v d`) | `[propext, Quot.sound]` |
| `Theorem2_ZeroDWStateTransport` | `gdn2_poison_margin_flip_zero_dw` | Concrete exact witness | `[propext]` |
| `Theorem2_ZeroDWStateTransport` | `iso_frobenius_blindness_212_5` | Concrete exact witness | `[propext]` |
| `Theorem2_ZeroDWStateTransport` | `yield_wall_advection_zero_dw` | Concrete exact witness | `[]` *(zero axioms)* |
| `Theorem2_ZeroDWStateTransport` | `s2_cube_chain_complex_and_euler` | Concrete exact complex | `[propext]` |
| `Theorem2_ZeroDWStateTransport` | `s2_cube_universal_gauss_stokes` | Universal (`∀ u : Fin 12 → Int`) | `[propext, Quot.sound]` |
| `Theorem2_ZeroDWStateTransport` | `s2_cube_relu_obstruction_and_commutator` | Concrete exact obstruction | `[propext]` |
| `Theorem3_SchurMetrologyObstruction` | `sym2_sylvester_spd` | Universal (`∀ M x0 x1`) | `[propext, Quot.sound]` |
| `Theorem3_SchurMetrologyObstruction` | `sym4_sylvester_spd` | Universal (`∀ M x0 x1 x2 x3`) | `[propext, Quot.sound]` |
| `Theorem3_SchurMetrologyObstruction` | `optifab_diagonal_plant_gate_admits_uc` | Concrete exact gate | `[propext]` |
| `Theorem3_SchurMetrologyObstruction` | `optifab_sensor_block_D_spd` | Universal (`∀ y0 y1`) | `[propext, Quot.sound]` |
| `Theorem3_SchurMetrologyObstruction` | `optifab_uncalibrated_schur_minors_3_0_1` | Concrete exact minors | `[propext]` |
| `Theorem3_SchurMetrologyObstruction` | `optifab_uncalibrated_negative_witness` | Concrete exact witness | `[propext]` |
| `Theorem3_SchurMetrologyObstruction` | `optifab_calibrated_schur_universal_spd` | Universal (`∀ x0 x1 x2 x3`) | `[propext, Quot.sound]` |
| `Theorem3_SchurMetrologyObstruction` | `venturi_collars_min_two_universal` | Universal (`∀ k : Nat`) | `[propext, Classical.choice, Quot.sound]` |

---

## 3. Verifier Hardening & Reproducibility

- **Pure-$\mathbb{Z}/\mathbb{Q}$ Trust Path:** `lean4_wave2_certs_audit.py` uses Python 3 standard library only (`int`, `fractions.Fraction`, `math.isqrt`, `hashlib`, `hmac`, `os`, `subprocess`), with zero IEEE-754 floats, zero bare `assert`s, zero `.isdigit()`, zero `islink`/`is_symlink`, and zero mathematical RNG.
- **Offline Static Lean 4 Proof-Envelope Gate:** Strips nested `/- ... -/` block comments, `--` line comments, plain `"..."` strings, Lean 4 `Char` literals (`'"'`, `'\"'`, `'\''` guarded against identifier primes), raw strings (`r"..."` / `r#"..."#`), and interpolated strings (`s!"{...}"` / `m!"{...}"` / `f!"{...}"`, preserving `{...}` code spans for scanning while failing closed on unterminated comments/strings); normalizes French-guillemet identifiers (`«...»`); blocks `sorry`, `admit`, `axiom`, `unsafe`, `native_decide`, `sorryAx`, `ofReduceBool`, `trustCompiler`, `debug.skipKernelTC`, `@[extern]`/`@[implemented_by]`, `partial`, non-`Init`/`Std` imports, bound `DecideConfig` records with non-false `native`, and runs a single-pass $O(n)$ balanced-paren scanner enforcing a fail-closed plain-record-literal allowlist on `decide (config := ...)`.
- **Zone-B Filesystem & CLI Defense:** Atomic `dir_fd` traversal (`O_RDONLY | O_DIRECTORY | O_NOFOLLOW`), `(st_dev, st_ino)` `$PWD` inode parity check, verified root-owned macOS Darwin `/var`/`/tmp`/`/etc -> /private/*` prefix normalization, `st_nlink == 1` enforcement on both reads and durable `0o600` atomic writes rejecting symlink/non-regular/hardlink targets and races, exact-bool `verify_live_lean` enforcement, wrapped `OSError`/`UnicodeDecodeError`/`RuntimeError`/`TimeoutExpired`/surrogate handling, canonical byte-exact certificate enforcement via `hmac.compare_digest`, and fail-closed typed CLI rejecting leading-dash targets and non-string `argv`.
- **Reproduce Locally:**
  ```bash
  python3 -I -B lean4_wave2_certs_audit.py --check lean4_wave2_certs_certificate.json
  python3 -I -B test_lean4_wave2_certs_r5.py -v
  ```

---

## 4. Frozen File Manifest

- **Certificate `payload_sha256`:** `f29ce24bb9accef51aecf8037680968ebe3801eb83dcde1fccefe51687716cfd`
- **Certificate `certificate_sha256`:** `9934344838c22cb9c2d3621f04845ff5ab501b85f104f12af5f597fda636e612`

| File | Lines | Bytes | Mode | SHA-256 |
|---|---:|---:|---:|---|
| `lean-toolchain` | `1` | `25` | `0o644` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |
| `lakefile.toml` | `11` | `295` | `0o644` | `3a85facf098e98b55006864aed7881cda559552987c364d776975df9ffa256bf` |
| `Wave2KernelCerts/Theorem1_BallF64CauchySchwarz.lean` | `269` | `11,568` | `0o644` | `12fef5dbbc90e53ac38885cb04ada7428bdf59715473137c591ce000885e67cb` |
| `Wave2KernelCerts/Theorem2_ZeroDWStateTransport.lean` | `357` | `16,161` | `0o644` | `d575a529ff6102d6669bb3c4cf6fedbb54a3e6eed11ba8a608218e7c7c8adaeb` |
| `Wave2KernelCerts/Theorem3_SchurMetrologyObstruction.lean` | `633` | `29,363` | `0o644` | `b9d714a414f9d1b9bfacf1fdcf2655fb30671a124ba687558cc05d0fca6af196` |
| `lean4_wave2_certs_audit.py` | `1,943` | `79,538` | `0o644` | `fc3052d5ff490f84dcaa6567b3aa8b7ad46768b0af02f655ab7179de6ad12969` |
| `test_lean4_wave2_certs_r5.py` | `971` | `57,010` | `0o644` | `2bcbea67cf3fe5f79e7ecdf8317c5dee1254d94ca205af9c18ffc9baeb399698` |
| `lean4_wave2_certs_certificate.json` | `1` | `8,282` | `0o600` | `0e0f088df04400632034eeebb0626d8f95dadd5970df31462f03137c455443d5` |
| `LEAN4_WAVE2_CERTS_REPORT.md` | *(this file)* | — | `0o644` | *(self-documenting report)* |
