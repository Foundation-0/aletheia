# Track S116 Evaluation Report: `HoloSphere CellOp` Persistent Megakernel (`sm_86`), `ScopedAmpereL2Pin`, `H16e` / `H16e-v2` / `H16e-v3` Non-Abelian Group Closure, & Pure-`Init` Lean 4.36.0 Invariants (`#37–#40b`)

- **Track ID:** `track-s116-holosphere-cellop` (`N1` verified evidence bundle; `n2_claims = 0`)
- **Hardware Platform:** Live `NVIDIA GeForce RTX 3080 Laptop GPU` (`GA104M`, `sm_86`, `48` SMs, `4 MiB` L2, `2.75 MiB` hardware max persisting L2 ceiling, `nvcc 13.4 V13.4.92`), Ring-0 `mlos` Zone-B hardware telemetry (`clean_hardware_run = true`, `anomalies = []` across all `5/5` runs)
- **Companion Public Links:**
  - Formal proofs & reference library: [`Moissanite-Labs/holosphere#3`](https://github.com/Moissanite-Labs/holosphere/pull/3)
  - Silicon co-design thread (`OBS-ORDA-01..26`): [`Moissanite-Labs/silikernels#2`](https://github.com/Moissanite-Labs/silikernels/issues/2)
- **Audit Verifier:** [`s116_cellop_audit.py`](s116_cellop_audit.py) + [`s116_cellop_certificate.json`](s116_cellop_certificate.json) + [`test_s116_cellop_audit_r5.py`](test_s116_cellop_audit_r5.py) (`100.0%` Python stdlib, `0` bare `assert`s, `100.0%` mutation kill)

---

## 1. Honest Literal-Gate Scorecard (`PREREG-S116` + `AMENDMENT1..4B`)

Zero post-hoc threshold edits were made. Every verdict below is recomputed deterministically from raw shipped artifacts by pure grading functions inside `s116_cellop_audit.py`:

| Hypothesis / Run | Preregistration Lock | Literal Verdict | Primary Verified Result |
| :--- | :--- | :---: | :--- |
| **`H16a-v2`** (Phase-2B `12L` Showdown) | `PREREG_S116_AMENDMENT2` (`eb1b0e57…`) | **`CONFIRMED`** | `10/10` `0 B`-spill `sm_86` kernels (`uniform_cell_8warp_sm86`: `75` regs, `4,680 B` SMEM, `3` CTAs/SM, `IMMA.16832: 1`, `HMMA.16816: 0`); `100%` live bit-exact parity (`0` `NaN` desyncs, `0` `int32` diff, `16/16` flips caught, `0.0` `16 B` rollback drift); **`33.6866 µs/tok`** & **`0.4618 mJ/tok`** = **`106.87×` (`T2048`) / `113.33×` (`T8192`) faster** & **`195.36×` / `215.68×` lower GPU energy** vs live PyTorch eager `12L`, **`9.12×`** vs `switch(opcode)` 48-CTA, **`2.97×`** vs async C++ 48-launch, and **`7,021.71×`** state compression at `T=8192`. |
| **`H16c-v2`** (`ScopedAmpereL2Pin` + `Weight-in-A`) | `PREREG_S116_AMENDMENT2` (`eb1b0e57…`) | **`CONFIRMED`** | Exact `GA104M` hardware ceiling clamp (`2,883,584 B = 2.75 MiB`); **`+49.43%`** (`1.4943×`) at `T=2048` (`24 MiB` KV thrash), **`+36.85%`** (`1.3685×`) at `T=8192` 1-pass, and **`525.46 GB/s`** (`1.4783×` live `355.44 GB/s` GDDR6 STREAM Triad) at `T=8192` 4-pass; `Weight-in-A` `N=8` reaches **`4.0355 TOPS`** (`1.0394 µs/branch`, **`1.7140×`** vs `Weight-in-B`). |
| **`H16e`** (`800`-Step `5`-Arm Group Closure) | `PREREG_S116_AMENDMENT2` (`eb1b0e57…`) | **`PARTIAL`** | `H16e_W_S3`: `A3` & `A4` hit **`100.00%`** (`T128`, `p_Holm = 0.00026 < 0.01` vs `A0`/`A2`); `H16e_W_A5`: `A4` hit `100.00%` (`T64/128/256`) on seed `42` (`48.63%` 3-seed mean, missing `p_Holm < 0.01` at `800` steps); `A3` uniquely won `H16e_M_S3`; UTF-8 BPB `-33.85%` vs `A0`. |
| **`H16e-v2`** (`2,000`-Step `A5` Unified Fusion) | `PREREG_S116_AMENDMENT3` (`0f58e288…`) | **`PARTIAL`** | **`A5_CellOp_Unified_A3plusA4`** smashed `H16e_M_S3` (`99.35%` `T64`, **`94.40% ± 3.04%` `T128`**, **`p_Holm = 0.00149–0.00484 < 0.01`** over ALL 4 controls), hit `52.34%` `T64` / `33.01%` `T128` (seed `137`: `94.53%` / `76.76%`) on `H16e_M_A5`, and dropped UTF-8 BPB to `4.6281` (`-42.13%` vs `A0`, beating `A3`/`A4` while missing `<= 4.0` fusion bar); on `H16e_W_A5`, `A3 = 72.33%`, `A4 = 58.85%`, `A5 = 45.77%` (`df=2` grokking variance blocked `p_Holm < 0.01`). |
| **`H16e-v3`** (`2,000`-Step `A6` Relational `V_ring`) | `PREREG_S116_AMENDMENT4` (`d22ceaa5…`) + `4B` (`0194c286…`) | **`FALSIFIED`** | **`A6_RelationalCellOp`** failed all 3 kill gates (`M_S3 T128 = 31.58% < 90%`, `M_A5 T128 = 6.12% < 50%`, `M2_A5 T128 = 1.37%`), while **`A5`** set a new `8×` OOD record on `H16e_M_S3`: **`99.28%` `T64`, `96.35% ± 4.98%` `T128`, `81.18%` `T256`** (`+64.78 pp` vs `A6`, `p_Holm = 0.0378`, `t = 8.82`). Establishes **`OBS-S116-05`**. |

---

## 2. Live RTX 3080 Zone-B Silicon Measurements (`H16a-v2` & `H16c-v2`)

### 2.1 `ptxas` Zero-Spill & SASS Audit (`ptxas_s116_zero_spill_receipt.json`)
- **Compiler:** `nvcc 13.4 V13.4.92` (`-O3 -std=c++17 -arch=sm_86 --ptxas-options=-v`) on `holosphere_megakernel_sm86.cu` (`SHA-256: bb64939cec09ff2cbab74c79f056a2b7fa89bc1b6e1de6502650701a3d49a0b6`).
- **Zero-Spill Record:** **`10/10` kernels at `0 B` spill loads, `0 B` spill stores, `0 B` stack frame**.
- **Hero Kernel `uniform_cell_8warp_sm86`:** `75` registers, `4,680 B` static SMEM, `3` CTAs/SM occupancy, `IMMA.16832: 1`, **`HMMA.16816: 0`**, `FMNMX: 11`, `LDGSTS: 2`, `POPC: 10`, `SEL: 22`, `SHFL: 20`.

### 2.2 Matched `12`-Layer `d_model = 256 / 512` Showdown (`H16a-v2`)

| Configuration (`12` Layers, RTX 3080 `sm_86`, `1,245 MHz`) | Launches/tok | `µs / tok` | GPU `mJ / tok` | Speedup (`u8_d256`) |
| :--- | ---: | ---: | ---: | ---: |
| **`uniform_cell_8warp_sm86` (`d=256`, `1` CTA, `0` `grid.sync`)** | **`0`** | **`33.6866`** | **`0.4618`** | **`1.00×`** |
| `uniform_cell_8warp_sm86` (`d=512`, `2` CTA, `.gpu` L2 barriers) | `0` | `68.2160` | `0.9352` | `2.03×` |
| `switch_opcode_vm_12l_1cta` (`switch(opcode)` control, `80` regs) | `0` | `76.4934` | `1.0487` | `2.27×` |
| `async_cpp_per_op_12l_48` (async C++ `48`-launch) | `48` | `100.0494` | `1.3717` | `2.97×` |
| `switch_opcode_vm_12l_48cta` (`switch(opcode)` 48-CTA control) | `0` | `307.3492` | `4.2138` | `9.12×` |
| `async_cpp_per_op_150` (async C++ `150`-launch) | `150` | `564.9193` | — | `16.77×` |
| Live PyTorch eager `12L` (`bf16`, `d=256`, `T=2048`, `24 MiB` KV) | `184` | `3,600.1705` | `90.2264` | **`106.87×`** (`195.36×` energy) |
| Live PyTorch eager `12L` (`bf16`, `d=256`, `T=8192`, `96 MiB` KV) | `184` | `3,817.6023` | `99.6113` | **`113.33×`** (`215.68×` energy) |

- **Live Hardware Parity (`all_parity_pass = true`):** `fmnmx_onehot_nan_desyncs = 0`, `fmnmx_onehot_imma_max_int32_diff = 0`, `weight_in_a_imma_max_int32_diff = 0`, `weight_in_a_valid_syndrome_errors = 0`, `weight_in_a_injected_16_flips_caught = 16`, `cell8warp_2cta_tokens_verified = 64`, `cell8warp_2cta_syndrome_errors = 0`, `cell8warp_2cta_nan_desyncs = 0`, `cell8warp_2cta_passb_max_int32_diff = 0`, `cell8warp_2cta_16b_pi_t0_rollback_max_drift = 0.0`.
- **State Footprint (`T=8192`):** `14,336 B` fixed `O(1)` CellOp recurrent state vs `100,663,296 B` (`96 MiB`) `bf16` KV cache = **`7,021.71×`** compression (`1,755.43×` at `T=2048`).

### 2.3 `ScopedAmpereL2Pin` & `Weight-in-A` `IMMA.16832` (`H16c-v2`)
- **Live GDDR6 STREAM Triad Baseline:** `355.4441 GB/s`.
- **Hardware Ceiling Verification:** `4 MiB` pin request clamps cleanly to `2,883,584 B` (`2.75 MiB` `GA104M` hardware limit, `clamp_exact_ga104m_ceiling = true`); `1,484,800 B` core pinned under streaming `__ldcs` KV thrash:
  - `T = 2048` (`24 MiB` thrash, 1-pass): `168.77 GB/s` (unpinned `ld.global.ca`) -> **`252.19 GB/s`** (pinned) = **`+49.43%` (`1.4943×`)**.
  - `T = 8192` (`96 MiB` thrash, 1-pass): `179.50 GB/s` -> **`245.64 GB/s`** = **`+36.85%` (`1.3685×`)**.
  - `T = 8192` (`96 MiB` thrash, 4-pass): `442.01 GB/s` -> **`525.46 GB/s`** = **`1.4783×` live GDDR6 STREAM Triad**.
- **`Weight-in-A` `N=8` `IMMA.16832` (`4,096` tiles):** **`4.0355 TOPS`** (`8.3149 µs` total, `1.0394 µs/branch`) vs `Weight-in-B` (`2.3544 TOPS`, `14.2515 µs`) = **`1.7140×`**.

---

## 3. Non-Abelian Group Closure (`H16e`, `H16e-v2`, `H16e-v3`) & `OBS-S116-05`

All arms across every task satisfied strict **`CS-08 <= 0.5%`** non-embedding parameter parity (`max_delta = 0.0510%–0.1982%`) over locked seeds `[42, 137, 2026]`. Every `t_stat`, `p_raw`, and step-down Holm-Bonferroni `p_holm` is independently recomputed by `s116_cellop_audit.py`.

### 3.1 `H16e-v2` (`2,000` Steps, `A5` Unified Fusion — Honest Literal `PARTIAL`)

| Task (`CS-08 max Δ`) | `A0` (Softmax) | `A2` (SoftExp2f) | `A3` (HardFMNMX) | `A4` (CayleyOnly) | **`A5` (Unified `A3+A4`)** | Key `T128` Paired Stats (`df=2`) |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| `H16e_W_A5` (`0.1314%`, `T128`) | `1.89%` | `1.63%` | **`72.33%`** (`[100, 17, 100]`) | `58.85%` (`[99.4, 30.3, 46.9]`) | `45.77%` (`[14.8, 100, 22.5]`) | `A4 vs A0: p_Holm = 0.658`; `A5 vs A0: p_Holm = 0.982` |
| `H16e_M_S3` (`0.1494%`, `T128`) | `17.38%` | `17.06%` | `32.49%` | `17.58%` | **`94.40% ± 3.04%`** (`T64: 99.35%`) | **`A5 vs {A0,A2,A3,A4}: p_Holm = 0.00149–0.00484 < 0.01`** |
| `H16e_M_A5` (`0.1314%`, `T128`) | `1.50%` | `1.89%` | `11.39%` | `1.69%` | **`33.01%`** (`T64: 52.34%`, s137: `76.76%`) | `A5 vs A4: +31.32 pp`, `p_Holm = 1.0` |
| `512 B UTF-8` (`250` steps, BPB) | `7.9978` | `8.0018` | `5.2870` | `5.2515` | **`4.6281`** (`-42.13%` vs `A0`) | Beats `A3`/`A4`, above `<= 4.0` fusion bar |

### 3.2 `H16e-v3` (`2,000` Steps, `A6_RelationalCellOp` — Honest Literal `FALSIFIED` & `OBS-S116-05`)

| Task (`CS-08 max Δ`) | Arm (`params`, `wall/seed`) | `T = 64` (`2×`) | `T = 128` (`4×`, `± std`) | `T = 256` (`8×` OOD!) | Per-Seed `T128` (`[42, 137, 2026]`) |
| :--- | :--- | ---: | ---: | ---: | --- |
| **`H16e_M_S3`** (`0.1874%`) | `A3_HardFMNMX` (`94,977`, `35.2s`) | `71.35%` | `59.77% ± 24.89%` | `38.67%` | `[31.25, 70.90, 77.15]` |
| | `A4_CayleyOnly` (`94,977`, `27.9s`) | `17.84%` | `19.01% ± 0.41%` | `16.86%` | `[18.55, 19.14, 19.34]` |
| | **`A5_Unified`** (`94,935`, `36.9s`) | **`99.28%`** | **`96.35% ± 4.98%`** | **`81.18%`** | **`[98.83, 90.62, 99.61]`** (`T256: [90.62, 59.18, 93.75]`) |
| | `A6_Relational` (`95,155`, `69.0s`) | `34.96%` | `31.58% ± 8.12%` | `31.84%` | `[32.03, 39.45, 23.24]` (`A6 vs A5: -64.78 pp, p_Holm = 0.0378`) |
| **`H16e_M_A5`** (`0.1982%`) | `A3_HardFMNMX` (`101,937`, `35.0s`) | `27.54%` | `13.41% ± 8.22%` | `5.08%` | `[22.85, 7.81, 9.57]` |
| | `A4_CayleyOnly` (`101,937`, `28.1s`) | `1.63%` | `2.21% ± 0.41%` | `1.43%` | `[2.34, 2.54, 1.76]` |
| | **`A5_Unified`** (`101,855`, `37.5s`) | **`46.68%`** | **`26.30% ± 15.59%`** | **`13.15%`** | **`[9.96, 27.93, 41.02]`** |
| | `A6_Relational` (`102,139`, `69.6s`) | `18.03%` | `6.12% ± 2.79%` | `3.19%` | `[3.71, 9.18, 5.47]` (`A6 vs A5: -20.18 pp, p_Holm = 0.3739`) |
| **`H16e_M2_A5`** (`0.1982%`) | `A3` / `A5` / `A6` (2-step macros) | `1.63% / 1.43% / 1.89%` | `0.98% / 1.56% / 1.37%` | `2.15% / 1.50% / 1.30%` | All 3 arms at chance (`1.67%`) |

- **Scientific Diagnosis (`OBS-S116-05` — Direct-$S^3$ `V_ring` Optimization Obstruction):**
  1. Left-action relational holonomy $\Delta U_{L_k} = U_{\tau_1} U_{\tau_0}^\dagger$ is algebraically exact (`recon_err = 5.96e-8`, `transport_err = 1.25e-7`, wrong right-conjugation error `1.5749`, 4D $T_{\Delta U^*} S^3$ STE FP64 central-FD gradcheck `1.90e-11`, independently mechanized in pure-`Init` Lean 4).
  2. Storing unit quaternions directly in `V_ring` (`A6`) removes cross-head `W_mem_out` mixing, restricting each Hard-FMNMX head to `8` isolated spinors (`q_per_head = 8`) behind a `2×` deeper prefix-scan + conjugation + $S^3$-gate chain (`1.87×` slower per step: `69.0s` vs `36.9s`), collapsing SGD grokking by **`-64.78 pp`** on `H16e_M_S3` and **`-20.18 pp`** on `H16e_M_A5` relative to `A5`.
  3. On 2-step composed $A_5$ macros (`H16e_M2_A5`, `16` random prefix tokens, `80` `BIND1/BIND2` tokens), all three arms remained at chance (`1.0–1.9%`), demonstrating that multi-step macro composition requires prefix-token holonomy suppression or curriculum.
  4. **Architecture Recommendation:** Retain `A5`'s feature-space `HardFMNMXAttentionSTE` `V_ring` + `W_mem_out` cross-head mixing -> single `BoundedCayleySU2Head` for trainable models (`99.28%` `T64` / `96.35%` `T128` / `81.18%` `T256` `8×` OOD on `H16e_M_S3`).

---

## 4. Pure-`Init` `Lean 4.36.0` Co-Design Proofs (`#37–#40b`)

Shipped verbatim in [`lean/HoloSphereCellOpInvariants.lean`](lean/HoloSphereCellOpInvariants.lean) (`SHA-256: 78c8e3bae5bd16569c539ceadc4b0f8a82fc3ee762625579687f8cddc914dfc4`, zero Mathlib, zero `Classical.choice`, zero `sorryAx`, zero `native_decide`, zero warnings):

| # | Theorem | Axioms | Verified Invariant |
| :---: | :--- | :--- | :--- |
| `37` | `p1_blockh4_involutory_and_int8_bounds` | `[propext, Quot.sound]` | `H_4(H_4 u) = 4u`, `‖H_4 u‖² = 4‖u‖²`, tight signed-nibble `int8` bounds `-32 <= r_k <= 30`. |
| `38` | `p2_cayley_unit_ball_so3_involution_and_even` | `[propext, Quot.sound]` | Finite `‖w‖ = 1` covers `180°` `SO(3)` involutions (`q² = -4 d⁴`), exact `±I` evenness `so3Adj(-q) = so3Adj(q)`, and `q(0,v)q̄ = (0, so3Act q v)`. |
| `39` | `p3_cayley_exact_inverse_reversibility` | `[propext, Quot.sound]` | Exact algebraic inverse `q(-w)(q(w) U) = (d² + ‖w‖²)² U` (`κ = 1` `O(1)`-VRAM backward holonomy recovery). |
| `40` | `p4_hadamard256_byte_orthogonality` | `[propext, Quot.sound]` | `k`-bit character-sum induction proving exact `256 × 256` pairwise orthogonality of `H_256` over `Fin 256` & `UInt8`. |
| `40b` | `p4b_bent_phase_preserves_orthogonality` | `[propext, Quot.sound]` | Any `±1` diagonal sign — specifically Maiorana–McFarland `bent4(d)` (`0/2048` constant warps) — preserves `100%` exact `H_256` orthogonality. |

---

## 5. Ring-0 `mlos` Zone-B Provenance & Explicit Disclosures

| Run Tag | Receipt File | Execution Window (UTC, `clean=true`, `anomalies=[]`) | Bound `receipt_sha256` | `original_unmodified_run_receipt_sha256` |
| :--- | :--- | :--- | :--- | :--- |
| `phase2b` | `mlos_zone_b_s116_phase2b.json` | `2026-11-26T00:51:30Z .. 00:51:31Z` (`990.7 ms`) | `9dfaf1aa891ebe7288a07e16794d391a6eebbac230be57b105c64a221bbeb236` | `739f8708a22152763f3a8c8b448809bb3363dd2f592966ce1069056a03786d18` |
| `phase2b_pt12l` | `mlos_zone_b_s116_phase2b_pt12l.json` | `2026-11-26T00:35:16Z .. 00:35:22Z` (`5,889.1 ms`) | `644f4a7c7f4f9039b999090fb1df05b8191cca4628e2855c91bea252f53d6577` | `7ed1b354b5cc478d7951f7616bed8e1fb488d8d85255f512b053db07b6e77d57` |
| `h16e_v1` | `mlos_zone_b_s116_h16e.json` | `2026-11-26T00:35:22Z .. 00:51:07Z` (`944.2 s`) | `f13a522c348b340b5bd0338bb2c11904d7c0aba860fd17b00cf38a66c1e84dfb` | `ce894e0592286894fef9fce7bbba93dc5b70fa3b4c65957b34e9b9026e9ef7cc` |
| `h16e_v2` | `mlos_zone_b_s116_h16e_v2.json` | `2026-11-26T00:59:50Z .. 01:25:58Z` (`1,568.5 s`) | `77e7ad8b35ff37e2873511ecf66f3de2c6fe2fc1e0b30ec2875fbc3107fc0bf1` | `782e455bf1a9dadc236b9e6c989fb27cd1bec31c2287061b952c18e17534e9c6` |
| `h16e_v3` | `mlos_zone_b_s116_h16e_v3.json` | `2026-11-26T01:53:17Z .. 02:19:49Z` (`1,592.4 s`) | `7d3468eb60dc01a9ed8d80b826549e6be172a3a8a840037a7b23176208b5e963` | `e5169c7367469bda524440f598e590bc242f59347a9dd12f0f25a70882460948` |

### Mandatory Provenance Disclosures (`grk-proof` Standard)
1. **Pre-Staging Workspace (`"git_head": null`) & External Audit Log:** Every live RTX 3080 Zone-B run executed inside a non-git research staging workspace (`"git_head": null` in all `5/5` receipts). While the frozen `PREREG_S116*.md` documents reference `verification/AUDIT_LOG.md`, **no `verification/AUDIT_LOG.md` is shipped inside `Foundation-0/aletheia`**, and this PR's commit timestamps post-date the Zone-B execution window (`2026-11-26T00:35:16Z .. 02:19:49Z`). Pre-run lock timing is therefore **not** independently verifiable from repository git history alone.
2. **Post-Run Cryptographic Receipt Binding:** Because stock `mlos stamp-run` does not hash output JSONs or preregistration files, each shipped `mlos_zone_b_s116_*.json` adds `original_unmodified_run_receipt_sha256` (preserving the exact pre-binding `mlos` digest), `preregistration_sha256`, `result_sha256`, and `bound_result_file_sha256`, and recomputes `receipt_sha256`. All raw result JSON files (`s116_*.json`, `ptxas_s116_zero_spill_receipt.json`) and all `6` `PREREG_S116*.md` files remain 100% unmodified.
3. **Pre-Run Step-Parity Addendum (`AMENDMENT4B`):** Pre-run debugging of `A6_RelationalCellOp` ran exclusively on non-preregistered diagnostic seed `7` (zero executions on locked seeds `[42, 137, 2026]`), motivating `PREREG_S116_AMENDMENT4B_STEP_PARITY.md` (`0194c286…`) to match `H16e-v2`'s `2,000`-step budget and replace linear quaternion blending with identity-anchored multiplicative $SU(2)$ geodesic gating while preserving `PREREG_S116_AMENDMENT4` (`d22ceaa5…`) untouched and keeping all kill gates identical.

---

## 6. Complete Shipped File Manifest (`evidence/track-s116-holosphere-cellop/`)

<!-- FILE_MANIFEST_START -->
| File | Lines | Bytes | SHA-256 |
| :--- | ---: | ---: | :--- |
| `PREREG_S116_AMENDMENT1_CELLOP_IMMA_KVRING.md` | `38` | `5252` | `985e1460d186b376b0d0fe90a271e32df3579c66b2490702958daa2dfc3fea68` |
| `PREREG_S116_AMENDMENT2_8WARP_FMNMX_H16E.md` | `62` | `7949` | `eb1b0e571be990b47150c80a2ee1d75a337a6601f736084eddb95399ccb559a6` |
| `PREREG_S116_AMENDMENT3_UNIFIED_A3A4_A5.md` | `44` | `5732` | `0f58e288d2a11a0308fb7b004904c49c90eb592df3d0e00c2f155bacaf81eaf2` |
| `PREREG_S116_AMENDMENT4B_STEP_PARITY.md` | `24` | `3020` | `0194c2863b7d35af4c4f5ba5aede2eeb863461d22cb2ac97b399953f554d69d1` |
| `PREREG_S116_AMENDMENT4_RELATIONAL_MACRO_HOLONOMY.md` | `40` | `4813` | `d22ceaa5251a7c5ca9a2cd6f7fc17853119398ad87ea98ac8850774d0b3f0bfc` |
| `PREREG_S116_HOLOSPHERE_PERSISTENT_MEGAKERNEL.md` | `123` | `18540` | `9620db774af30b8b6e4ef8c241ccd5ed4cb489dd2fb3b414234633ea83c93c85` |
| `README.md` | `35` | `7350` | `0392d0a4110906c98ef8116ebf820f3ce7494c599937eb72a739ba1d726f93e9` |
| `lean/HoloSphereCellOpInvariants.lean` | `881` | `37414` | `78c8e3bae5bd16569c539ceadc4b0f8a82fc3ee762625579687f8cddc914dfc4` |
| `lean/README.md` | `22` | `2669` | `4c238f4c3c90d7d84c08759377871eb13127f90b37d0cf1c79bdad751eb335f5` |
| `lean/lakefile.toml` | `7` | `165` | `b3a290eef0e66310f8246712d86e90343b734d9f84d1ba4c3bb25897cd374c06` |
| `lean/lean-toolchain` | `1` | `25` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |
| `lean/test_cellop_lean_r5.py` | `146` | `6516` | `686b0497e5c6fc9affa5ff014347a179ecf444e8a07fd7edb18ea8f5672c4725` |
| `lean/verify_cellop_lean.py` | `473` | `21155` | `b7d5fa271386c48b8f76601a4e6e638ab0610db23f7d6d2915f0a9a294272572` |
| `mlos_zone_b_s116_h16e.json` | `93` | `2996` | `7a56c511e4a0fb3aa20ae4873db3ff3733931d351271e6f85a8b5e243bc43fc7` |
| `mlos_zone_b_s116_h16e_v2.json` | `95` | `3020` | `0e4f0a9ec39cde6fcf439c1b850db31b4c6ca415c9e9dded54d522fa3956869d` |
| `mlos_zone_b_s116_h16e_v3.json` | `95` | `3020` | `6f8fafd27ceda39e879c51e056cd24a6bdf6f752dbd1cb0a3946845be50330cc` |
| `mlos_zone_b_s116_phase2b.json` | `95` | `3030` | `398c132d3591ff101e958fb09938640c44595666689eeed0d56b8fe312d1e0ff` |
| `mlos_zone_b_s116_phase2b_pt12l.json` | `93` | `2991` | `92b973ab7436b42112417153f1e45c275e41ae492fe2edecc2eff9715292cf20` |
| `ptxas_s116_zero_spill_receipt.json` | `222` | `6026` | `d065bc75aee4f4c5f71dc4a60db864c1d1e7f78ac51039b83b2263967c72ae3f` |
| `s116_cellop_audit.py` | `959` | `41404` | `ec9e3b8b0ee27d6a86a89c08d9ed69162f87967747f16339ee144a1f85ba9d2c` |
| `s116_h16e_gpu_results.json` | `1426` | `40721` | `5b7281202a65b1fd45c543aa391dcfd52f78794fab95bcceca6ec8592f4e827e` |
| `s116_h16e_v2_gpu_results.json` | `1160` | `33245` | `6343592ebc8c2427cfee2ea55cbf09005d1fafa4cc8f6d2af23bd7769cabd252` |
| `s116_h16e_v3_gpu_results.json` | `777` | `22485` | `c733c957e3a4500f22f41cb62888084f707fecf0b1b6324b548a607c5668656c` |
| `s116_phase2b_gpu_results.json` | `133` | `4608` | `8e96e475d004f744feb94907b45bcd7dc6896412fbb8ddd94f838df3b2814090` |
| `s116_phase2b_pytorch_12l_results.json` | `35` | `962` | `bdc91eadc6dec810295505c80b183d7e77f7bc38835360cacabcfa9a41b3a30d` |
| `test_s116_cellop_audit_r5.py` | `540` | `28706` | `c99738ab62b54819668e9c7b43b1be3601b3aa49b49101fd46287d1587e701a4` |
| `REPORT_S116_CELLOP_EVAL.md` | *(self)* | *(self)* | *Pinned in `s116_cellop_certificate.json::report_sha256`* |
| `s116_cellop_certificate.json` | *(generated)* | *(generated)* | *Self-pinned via canonical inner `cert_sha256`* |
<!-- FILE_MANIFEST_END -->
