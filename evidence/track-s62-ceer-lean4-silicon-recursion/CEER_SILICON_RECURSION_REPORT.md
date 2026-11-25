# Calculational-Experimental Epistemic Recursion (`CEER`): Live Closed-Loop `Lean 4.36.0` $\leftrightarrow$ Silicon Verification Report

## 1. Executive Summary & Live Hardware Provenance

This package implements and certifies a live, three-cycle **Calculational-Experimental Epistemic Recursion (`CEER`)** closing an unbroken loop between formal pure-`Init` **`Lean 4.36.0`** theories/proofs and live physical silicon telemetry on an 8-core / 16-thread Intel Core i9-11900H (`UX582HS`, `24 MiB` shared L3, `70 W` PL1 thermal envelope) with discrete RTX 3080 verified idle (`P8`, `0%` GPU utilization, `2 MiB` KMD baseline VRAM, `0` compute/graphics processes) before and after every cycle.

- **Hard Safety & Privacy Locks:** Zero microphone access, zero camera access, zero display/brightness modifications; C11 actuator (`ceer_actuator.c`) compiled strictly into ephemeral `0o700` scratch directories (`ELF = 0` in frozen package).
- **Anti-Goodhart Cryptographic Pre-Registration:** Before every live silicon execution $k \in \{0, 1, 2\}$, `cycle_<k>_prereg.json` (written `0o600` by `--write`; `0644` in git) cryptographically commits to `CEER_Cycle<k>_Theory.lean` (`theory_lean_sha256`), the prior cycle's Lean 4 kernel verdict (`parent_cycle_verdict_sha256`), exact pure-$\mathbb{Z}/\mathbb{Q}$ falsifiable predictions, and strictly **pairwise-disjoint held-out micro-levers**. Zero thresholds or pre-registrations were modified after observing telemetry; every live falsification and hardware obstruction is proved constructively in `Lean 4.36.0` and lifted into the subsequent cycle's theory.
- **Ring-0 `mlos` Execution Receipts (all written `0o600` by `--write`, `0644` in git; `clean_hardware_run: true`, `determinism_zone: "B"`, `anomalies: []`, `exit_code: 0`, zero personal path leaks):**
  - Cycle 0 (`mlos_cycle0_receipt.json`, `receipt_sha256 = 32a10a25314c05dc2d809b6833ff26377b2b3ed1abd38cc3ad028780369d0a73`): `30,496 ms`, `14` segments, GPU `0% -> 0%`.
  - Cycle 1 (`mlos_cycle1_receipt.json`, `receipt_sha256 = 75fdec1e93abfe24016aaa8f7d4fcec00d2bb1d82e7dfbac7470a78cfefab9a2`): `29,500 ms`, `10` segments, GPU `0% -> 0%`.
  - Cycle 2 (`mlos_cycle2_receipt.json`, `receipt_sha256 = a740558f75fbe701df75702f57b4e5453f7f765b7e631b9ad2533ea26dab9d51`): `27,612 ms`, `11` segments, GPU `0% -> 0%`.

---

## 2. Pairwise-Disjoint Held-Out Micro-Levers Across Cycles `0 -> 1 -> 2`

Every cycle evaluates strictly unseen micro-levers across all four controllable hardware families (`ceer_actuator.c` compiled with `-O3 -std=c11 -D_GNU_SOURCE -Wall -Wextra -Werror -pthread`, zero warnings; 20 Hz / 50 ms pure-integer sampling of all 5 unlocked `intel-rapl` domains, all 9 `coretemp` sensors, `cpu_fan`/`gpu_fan`, and per-core `cpufreq`):

| Lever Family | Cycle 0 (`T_0` Classical Idealized) | Cycle 1 (`T_1` Obstruction-Lifted) | Cycle 2 (`T_2` Coupled Electro-Thermal + Schur) | Pairwise Disjoint |
|---|---|---|---|---|
| `u1` Active Physical Cores | `{1, 2, 4, 8}` | `{3, 6}` | `{5, 7}` | **Yes** (`8` distinct counts) |
| `u2` Spatial Thermal Core Pairs | `{(0,1), (0,7)}` | `{(2,3), (2,7)}` | `{(4,5), (1,6)}` | **Yes** (`6` distinct pairs) |
| `u3` Sattolo Pointer-Chase Footprints | `{16 KiB, 256 KiB, 4 MiB, 64 MiB}` | `{8 MiB, 32 MiB}` | `{512 KiB, 12 MiB, 48 MiB}` | **Yes** (`9` distinct sizes) |
| `u4` Symmetric Load Ramp Schedule | `1,2,4,8,8,4,2,1 @ 1200 ms` | `0,2,4,8,8,4,2,0 @ 1800 ms` | `1,3,6,8,6,3,1 @ 1500 ms` | **Yes** (`3` distinct schedules) |

---

## 3. Three-Cycle Live Silicon Empirical & Epistemic Trajectory

Cleanly corroborated composite hypotheses rose strictly monotonically across the three live silicon recursion cycles: **`0/4 (Cycle 0) -> 2/4 (Cycle 1) -> 3/4 (Cycle 2; 11/12 atomic sub-clauses)`**, with every live falsification exposing a genuine physical mechanism verified in `Lean 4.36.0`:

### Cycle 0 (`T_0`: Idealized Linear / Flat / Isotropic / Non-Hysteretic Baseline) — `0/4` Cleanly Corroborated

| Hypothesis | Pre-Registered Prediction | Live Measured Silicon Evidence (Exact $\mathbb{Z}/\mathbb{Q}$) | Lean 4 Kernel Verdict | Discovered Physical Obstruction Lifting Cycle 1 |
|---|---|---|---|---|
| `H0a` | Linear non-concave core power scaling (`p in {1,2,4,8}`) | `P_pkg = [69984, 69857, 69802, 69884] mW` (`|P8 - P1| = 100 <= 200 mW`); `ops` scaled `8.01x` (`2.84B -> 22.73B`) | **DEGENERATE** (`cycle0_H0a_degenerate_pl1_saturation`) | `70 W` PL1 hard power wall clamps package power flat -> lift `H1a` to PL1-saturated computational efficiency `ops / uJ`. |
| `H0b` | Flat memory hierarchy (`<= 2x` energy/op `16 KiB -> 64 MiB`) & `P_dark(64M) <= P_dark(16K)` | Exact cliff **`81.23x`** (`402490869786 / 4955019133`, `> 80x`); `UX582HS` `psys` reads `~4.6 W < P_pkg` (`darkMw = -65202 mW`), while calibrated on-package `P_pkg - P_core - P_uncore = +4313 / +4051 mW` | **FALSIFIED** (`cycle0_disproof_H0b`, `cycle0_H0b_cliff_gt_80x`, `cycle0_on_package_dark_power_positive`) | Massive L1-to-DRAM energy cliff + `UX582HS` ACPI `psys` uncalibrated vendor-scale obstruction -> lift `H1b` to unseen L3 boundary `{8 MiB, 32 MiB}` and calibrated on-package `P_pkg - P_core - P_uncore > 0`. |
| `H0c` | Spatial thermal invariance (`|adj - dist| <= 500 mC`) | `adjInactRiseMc = -343 mC`, `distInactRiseMc = +985 mC`, gap **`1,328 mC > 500 mC`**; static interior hotspot (`Core 5 ~86.5 C` vs `Core 6 ~76.0 C`) | **FALSIFIED** (`cycle0_disproof_H0c`) | Ambient temporal drift + static die-interior thermal gradient -> lift `H1c` to within-window common-mode-cancelled contrast on unseen pairs `(2,3)` vs `(2,7)`. |
| `H0d` | Single-valued non-hysteretic fan cooling (`2*Area == 0`, `|dRPM| <= 50`) | `cpu_fan` locked at `3300 RPM` across all 193 samples (`twiceFanHystArea = 0`), yet `T_pkg` lagged warmer on descent by **`+1,101 mC`** (`86270 -> 87371 mC`) with signed `(T_pkg, load_p)` area **`-8,000 != 0`** | **OBSTRUCTED** (`cycle0_H0d_fan_plateau_and_thermal_lag`) | EC fan quantization deadband hides die-temperature thermal-capacitance hysteresis -> lift `H1d` to `(T_pkg, load_p)` thermal hysteresis on unseen ramp `0,2,4,8,8,4,2,0 @ 1800 ms`. |

### Cycle 1 (`T_1`: First Obstruction-Lifted Theory) — `2/4` Corroborated, `2/4` Honestly Falsified

| Hypothesis | Pre-Registered Prediction | Live Measured Silicon Evidence (Exact $\mathbb{Z}/\mathbb{Q}$) | Lean 4 Kernel Verdict | Residual Discovery Lifting Cycle 2 |
|---|---|---|---|---|
| `H1a` | PL1-flat (`|P6-P3| <= 5%`) & `ops/uJ` gain `>= 1.60x` (`p in {3,6}`) | `P_pkg: 69989 -> 69832 mW` (`0.22%` delta); `ops/uJ` scaled **`1.874x`** (`187/100 >= 160/100`) | **CORROBORATED** (`cycle1_corroborates_H1a`) | Refine `H2a` to test frequency-normalized efficiency `ops / (uJ * freq)` on unseen `p in {5,7}`. |
| `H1b` | `8 MiB -> 32 MiB` cliff `>= 1.50x` & `P_pkg_dark > 0` | Cliff **`1.326x < 1.50x`** (`132/100`, still `>= 1.30x`); calibrated on-package dark power **`+4420 / +4212 mW > 4000 mW`** | **FALSIFIED** (`cycle1_disproof_H1b`, `cycle1_H1b_residual_cliff_and_dark_power`) | Under live 8-core concurrency, `8 MiB` already spills 4-KiB L2 STLB + contends for shared L3 -> lift `H2b` to two-regime private-L2/STLB vs shared-L3/DRAM `{512 KiB, 12 MiB, 48 MiB}`. |
| `H1c` | `contrast(2,3) > contrast(2,7)` & `interior - edge > 1500 mC` | `contrast23 = -793 mC > contrast27 = -1325 mC` (`+532 mC`); `interiorMinusEdge = +3,390 mC > 1500 mC` | **CORROBORATED** (`cycle1_corroborates_H1c`, `cycle1_H1c_static_dominance_obstruction`) | Both contrasts stayed `< 0` -> static die-interior resistance (`Cores 4,5`) dominates dynamic 2-core heating -> test extreme sign-reversal `(4,5)` vs `(1,6)` in `H2c`. |
| `H1d` | `twiceThermalLoadArea != 0` & `T_down > T_up` (`0,2,4,8,8,4,2,0`) | `T_down = 86110 mC < T_up = 88173 mC` (**`-2,063 mC`**); EC fan surged `3300 -> 3355 RPM` mid-ramp, reversing signed loop area to **`+30,444`** | **FALSIFIED** (`cycle1_disproof_H1d`, `cycle1_H1d_reversed_loop_obstruction`) | Open-loop `load_p` explains `< 3%` of `T_pkg` variance; coupled hidden modes (thermal soak + internal die gradient) drive `T_pkg` -> lift `H2d` to coordinate-free `3x3` Schur-complement variance closure. |

### Cycle 2 (`T_2`: Coupled Electro-Thermal & Coordinate-Free `3x3` Schur Closure) — `3/4` Full Corroborated (`11/12` Atomic Clauses)

| Hypothesis | Pre-Registered Prediction | Live Measured Silicon Evidence (Exact $\mathbb{Z}/\mathbb{Q}$) | Lean 4 Kernel Verdict | Physical Discovery |
|---|---|---|---|---|
| `H2a` | `|P7-P5| <= 5%`, raw `ops/uJ >= 1.25x`, freq-norm `ops/(uJ*freq) >= 1.20x` (`p in {5,7}`) | `P_pkg: 69791 -> 69946 mW` (`0.22%`); raw **`1.371x`**, freq-normalized **`1.361x`** (`3618.9 -> 3647.2 MHz`) | **CORROBORATED** (`cycle2_corroborates_H2a`) | PL1-clamped frequency-normalized computational efficiency scaling holds cleanly out of sample. |
| `H2b` | `{512K, 12M, 48M}`: `512K->48M >= 8x`, `512K->12M >= 4x`, `12M->48M >= 1.10x`, `P_pkg_dark > 0` | `512K->48M =` **`24.15x`**, `512K->12M =` **`25.52x`**, `P_pkg_dark =` **`+5082 / +4741 / +4411 mW`**; `12M->48M =` **`0.946x < 1.10x`** | **PRIMARY CLIFF & DARK POWER CORROBORATED; TAIL FALSIFIED** (`cycle2_disproof_H2b_dram_asymptote`, `cycle2_H2b_primary_cliff_and_dark_power`) | `512 KiB -> 12 MiB` captures the full `25.5x` STLB+L3 cliff; by `12 MiB`, live shared-L3 contention already reaches the flat DRAM saturation asymptote (`~25x`), so `12M -> 48M` stays flat within noise. |
| `H2c` | Extreme sign reversal on `(4,5)` vs `(1,6)`: `c45 > 0`, `c16 < 0`, swing `> 3000 mC` | `contrast45 =` **`+5,285 mC`**, `contrast16 =` **`-5,325 mC`**, total swing **`+10,610 mC` (`10.61 C`)** | **CORROBORATED** (`cycle2_corroborates_H2c`) | Symmetrical `+5.29 C / -5.33 C` sign reversal confirms static die-interior thermal resistance topology. |
| `H2d` | `twiceArea != 0`, `>= 5%` Schur variance drop (`v_soak`), strict drop (`delta != 0`, `v_spread`) | `twiceArea = -12,700`; exact `3x3` Schur identity residual `= 0` on both modes; `v_soak` drops residual variance by **`23.09%`** (`2309 bps >= 500`); `v_spread` (`max_c T_c - min_c T_c`) drops residual variance by **`62.02%`** (`6202 bps`, strict `det(G)*Suu < R1_num*det(A)`) | **CORROBORATED** (`cycle2_corroborates_H2d`, `cycle2_H2d_sharp_schur_reductions`, `cycle2_epistemic_chain_disjoint_and_monotone`) | Coordinate-free exact integer Schur complement closes Cycle 1's thermal obstruction with `> 62%` hidden-mode variance reduction proved inside `Lean 4.36.0` with **zero axioms `[]`**. |

---

## 4. Pure-`Init` `Lean 4.36.0` Kernel Inventory (`6` Modules, `37/37` Theorems, `0` Warnings, `0` Mathlib)

- **Toolchain:** `leanprover/lean4:v4.36.0` (`0` external imports, `0` `sorry`/`admit`/`axiom`/`unsafe`/`native_decide`/`partial`/`debug.skipKernelTC`/`extern`/`implemented_by`).
- **Clean-Copy `lake build`:** `Build completed successfully (14 jobs)`, `RC = 0`, `0` warnings (scratch build directory deleted post-run; `.lake = 0` in frozen package).
- **Exact `#print axioms` Allowlist Verification:** All `37/37` theorems strictly $\subseteq \{\text{propext}, \text{Classical.choice}, \text{Quot.sound}\}$, including **`5/37` zero-axiom `[]` kernel theorems**:
  1. `CEERSiliconCerts/CEER_Cycle0_Theory.lean` (`8` theorems): `falsify_H0a`, `falsify_H0b_energy`, `falsify_H0b_dark`, `falsify_H0c`, `falsify_H0d_area` (`[]`), `falsify_H0d_rpm`, `constant_fan_zero_hyst_area`, `closedConstTrapArea_eq`.
  2. `CEERSiliconCerts/CEER_Cycle0_Verdict.lean` (`6` theorems): `cycle0_disproof_H0b`, `cycle0_H0b_cliff_gt_80x`, `cycle0_disproof_H0c`, `cycle0_H0a_degenerate_pl1_saturation`, `cycle0_H0d_fan_plateau_and_thermal_lag`, `cycle0_on_package_dark_power_positive`.
  3. `CEERSiliconCerts/CEER_Cycle1_Theory.lean` (`4` theorems): `pl1_flat_power_implies_eff_gain`, `falsify_H1d_temp_lag`, `falsify_H1c_contrast`, `falsify_H1b_cliff`.
  4. `CEERSiliconCerts/CEER_Cycle1_Verdict.lean` (`7` theorems): `cycle1_corroborates_H1a`, `cycle1_disproof_H1b`, `cycle1_H1b_residual_cliff_and_dark_power`, `cycle1_corroborates_H1c`, `cycle1_H1c_static_dominance_obstruction`, `cycle1_disproof_H1d`, `cycle1_H1d_reversed_loop_obstruction`.
  5. `CEERSiliconCerts/CEER_Cycle2_Theory.lean` (`5` theorems): universal degree-4 `schur_3x3_variance_identity`, `schur_strict_variance_reduction`, `falsify_H2d_zero_delta` (`[]`), `falsify_H2c_sign`, `falsify_H2b_cliff`.
  6. `CEERSiliconCerts/CEER_Cycle2_Verdict.lean` (`7` theorems): `cycle2_corroborates_H2a`, `cycle2_disproof_H2b_dram_asymptote`, `cycle2_H2b_primary_cliff_and_dark_power`, `cycle2_corroborates_H2c`, `cycle2_corroborates_H2d` (`[]`), `cycle2_H2d_sharp_schur_reductions` (`[]`), `cycle2_epistemic_chain_disjoint_and_monotone` (`[]`).

---

## 5. Independent Verification Gates & Hardening Summary (Post-Last-Edit `100.0%` PASS)

- **Certificate Digest (`ceer_silicon_certificate.json`, written `0o600` by `--write`, `0644` in git):** `certificate_sha256 = 4c0cb09860f0a1dd4e505059b7ef43795ea40f61fe66895422df0d781ecc9b5a`, raw file SHA-256 `2a46bb17e6b108258a67acef7eebd9d2c2dc49f029e5b764d70647dbc0923dae` (`11,201` B; zero floats; binds all `19` frozen core source/data/receipt/proof SHAs + exact anchored unique telemetry-to-Lean witness parity across all `69/69` witness fields).
- **R4 3-Mode Isolated Python Parity (`-I -B`, `-I -O -B`, `-I -B -W error`) + `PYTHONHASHSEED=42 -I -B` + `umask 077`:**
  - `ceer_silicon_audit.py` (zero-arg) & `--standalone --json`: `2a46bb17e6b108258a67acef7eebd9d2c2dc49f029e5b764d70647dbc0923dae` (bit-identical across all 3 R4 modes + `PYTHONHASHSEED=42`).
  - `ceer_silicon_audit.py --check ceer_silicon_certificate.json`: `306d697238acafcc938519ce0c0264fadc059219b0e2632dedacb9e1cc659555` (bit-identical across all 3 R4 modes + `PYTHONHASHSEED=42`).
  - `test_ceer_silicon_r5.py`: `23/23 OK` across all 3 R4 modes + `PYTHONHASHSEED=42` under `umask 077`.
- **4-Surface Adversarial Fuzzer:** **`82 / 82 PASS`** (`25/25 CLI + 19/19 FR1 + 19/19 FR0 + 19/19 SEC`, `bypasses = 0, crashes = 0`).
- **Exhaustive Hardening Controls:** Strict `read_regular_file_strict` pre-load of all `19` artifacts before oracle JSON parsing (`O_NOFOLLOW`, `O_NONBLOCK`, `st_nlink == 1`, `MAX_FILE_BYTES`), iterative JSON tree guard (`MAX_JSON_DEPTH = 64`, `MAX_JSON_NODES = 100,000`, `MAX_INT_BITS = 2048`), strict `parse_constant`/`parse_float`/`object_pairs_hook` + exact `int` `cycle_id`/`exit_code`, constant-time `hmac.compare_digest` certificate check, bounded `FileExistsError` retry + temp `st_nlink == 1` + wrapped `os.unlink` in `write_atomic_0600`, root-owned symlink verification on Darwin `/tmp`/`/var`/`/etc`, surrogate/NUL rejection across CLI paths & `$PWD`, anchored unique `def obs{0,1,2}` witness extraction rejecting duplicate fields and decoys, strict `#print axioms` full-stdout audit rejecting compiler warnings & unexpected stdout lines, and pinned per-module `37/37` theorem names + `5/5` zero-axiom `[]` invariants across `FR0`, `FR1 (run_live_lean=False)`, and direct `SEC`.
- **Lean 4 Static Trust-Escape Hardening:** Full identifier-prime-safe `Char` (`'"'`, blocking `x' '"'` desync), raw-string (`r"..."`/`r#"..."#`), interpolated-string (`s!"{...}"`/`m!"{...}"`/`f!"{...}"`), nested-comment, French-guillemet (`«native»`/`«config»`), `decide` `+native`/`(native := ...)`/`(config := ...)`/`DecideConfig`, `attribute [extern/implemented_by]`, `#eval`/`#reduce`/`#print <non-axioms>`, and 64-digit witness-integer scanner + exact strict `STANDARD_LEAN4_AXIOMS` allowlist.
- **Live Guard Mutation Sweep (`aletheia mutate --guards require_ok --timeout 180 --max-mutants 0`; the `--workers` flag does not exist at this CLI):** **`41/41` oracle + `126/126` audit = `167 / 167` (`100.0%`, `survived = 0`, `timeout = 0`, `null_mutant = passed`, `truncated = False`)** (one-off local run, not shipped).
- **Whole-File DFS AST `BoolOp` Mutation Sweep (`OP_SWAP` + `SUBCOND_DEL`):** **`64/64` oracle (`19` nodes) + `194/194` audit (`53` nodes) = `258 / 258` (`100.0%`, `survived = 0`)**.
- **Static & Hygiene Audit (`aletheia audit-check . --lean-audit --strict-ancestors --safety-scan --scripts ceer_silicon_audit.py test_ceer_silicon_r5.py`):** **`PASS`** (`0` findings, `0` notices, `6/6` Lean clean, `2/2` R4 parity, `0` leaks, `0` CRLF, `0` bare asserts, `0` AST floats, `0` `.isdigit()`, `0` null-device refs, `ELF = 0`, `PYC = 0`, `.lake = 0`).

---

## 6. Frozen Artifact Manifest (`23` Core Files + This Report)

Mode column: `0o600` was the on-disk mode written by `--write` on the capture host; git records all files as `100644` (git cannot store `0600`). The certificate's `artifact_sha256` pins the `19` core artifacts (Lean modules, runner, actuator, preregs, telemetries, receipts, toolchain, lakefile); the audit/oracle/test/report files themselves are not hash-pinned by the certificate, so their trust boundary is git review.

| File | Lines | Bytes | Mode | SHA-256 |
|---|---:|---:|:---:|---|
| `CEERSiliconCerts/CEER_Cycle0_Theory.lean` | `147` | `6,720` | `0o644` | `8058c7fd24980e5c37abce7c2a4c71f2e682bec9189dc82970dadce7d078a1ab` |
| `CEERSiliconCerts/CEER_Cycle0_Verdict.lean` | `125` | `4,629` | `0o644` | `354b305ccc6ad64ef2ddb9dedce72345cff702e7a8328813878ccc45d1165eb6` |
| `CEERSiliconCerts/CEER_Cycle1_Theory.lean` | `114` | `5,345` | `0o644` | `4cbdd29f991d29a4d4088ed41f9f5044d0289102c6963e4be9bdb4827ed55457` |
| `CEERSiliconCerts/CEER_Cycle1_Verdict.lean` | `137` | `5,833` | `0o644` | `75324d91a25c2c4b9299ef1e5654451158d64206763dea8af7b61b4cc3266422` |
| `CEERSiliconCerts/CEER_Cycle2_Theory.lean` | `222` | `11,086` | `0o644` | `11d622de1106c537cf31095163b8cbb140f0a0273049c590970f8bf166de519f` |
| `CEERSiliconCerts/CEER_Cycle2_Verdict.lean` | `221` | `9,461` | `0o644` | `2942e35865f8ae3d995ecadb8f03ed5727ed533e5a60602f7892bedeccfc4812` |
| `ceer_actuator.c` | `377` | `12,287` | `0o644` | `a513986df0b65aa9bbac40c3b5ac893d11570c08d9c6f766da1b5c1e57ed46b3` |
| `ceer_silicon_audit.py` | `1,317` | `54,851` | `0o644` | `164e74825e50299e486c46cea2bda561695787ef8f59f997f86f1c65f03291c6` |
| `ceer_silicon_certificate.json` | `1` | `11,201` | `0o600 (git: 100644)` | `2a46bb17e6b108258a67acef7eebd9d2c2dc49f029e5b764d70647dbc0923dae` |
| `ceer_silicon_oracle.py` | `615` | `26,991` | `0o644` | `a73c82d474de5fcef9c30bc262f570266623dbe53e6ee625ee516c493c9eee2e` |
| `ceer_silicon_runner.py` | `449` | `16,193` | `0o644` | `9734852393a2dbe217dcc4404f6d2367ebb42579163fbcb60f2ebe350b5dcf0e` |
| `cycle_0_prereg.json` | `1` | `1,879` | `0o600 (git: 100644)` | `8eed5486024c2fc7fd14a00fdd5fe34dd3baa1d34025c045a4e7d0edeabf5e80` |
| `cycle_0_telemetry.json` | `1` | `201,869` | `0o600 (git: 100644)` | `56de8798a6f0bea39f5261fbad3b1c6d3a04dd2cce33c135a4afc0e3d5b0eaa9` |
| `cycle_1_prereg.json` | `1` | `1,777` | `0o600 (git: 100644)` | `6a75abdc1ab0efa2662704b11e10ddced86bc507d8582e58a902cc8c50b04d8a` |
| `cycle_1_telemetry.json` | `1` | `190,864` | `0o600 (git: 100644)` | `df2993b47a8bd7c88be2cfc4c127adf485431dcd12558438ae3a3205089bf8b6` |
| `cycle_2_prereg.json` | `1` | `2,004` | `0o600 (git: 100644)` | `40389e5a4cdd359963edd940ce31c801bf31e2c694e4d146631fd9fcc8268659` |
| `cycle_2_telemetry.json` | `1` | `179,216` | `0o600 (git: 100644)` | `ea8939df68e0c8e6883940f8b290817a7def46d99e820dc0b47e43daf6d76278` |
| `lakefile.toml` | `14` | `383` | `0o644` | `74f8839f29f0947848b2dc17172bed56f17d0ce362600fe350955fcc6c0b12f8` |
| `lean-toolchain` | `1` | `25` | `0o644` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |
| `mlos_cycle0_receipt.json` | `93` | `2,645` | `0o600 (git: 100644)` | `61db8181febd2845cb9c0f01b72068409ca17b997927e3f18d9269e25eba1d4b` |
| `mlos_cycle1_receipt.json` | `93` | `2,645` | `0o600 (git: 100644)` | `006b598328031366b1ef6ac12ce4f5816c04f48c8d18644fabbbea165ee2c3da` |
| `mlos_cycle2_receipt.json` | `93` | `2,645` | `0o600 (git: 100644)` | `37ee49c768fd96a737e323e7844def6dcc640711cfeafbfe33d2b3ddc0a5fa9b` |
| `test_ceer_silicon_r5.py` | `1,569` | `86,751` | `0o644` | `7c40c48b5d9d0836506cdc92cae0d03aed2d50c25c2ff3a18b96f10db66b3bf7` |
