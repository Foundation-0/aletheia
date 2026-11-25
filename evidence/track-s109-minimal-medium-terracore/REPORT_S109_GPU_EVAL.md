# Track S109 Live RTX 3080 Evaluation Report (`PREREG-S109` + `Amendments 1–3`: Minimal-Medium Core & Geodynamic TerraCore `H9a–H9d`)

- **Protocol Anchors (Immutable SHA-256 Pins):**
  - Parent `PREREG-S109`: `1ca8a38fa3c7fd8dda5823741c867b93be09c2342eb35bafde18e9e7e510b1c9`
  - `AMENDMENT1` (Council Hardening `§H9c-CONTRACT`, `CB-1..CB-6`, `§SWAP`, Triple `CS-08` Parity): `6f3d1e0b28d16e4290486e9adeb76c49bd8ebbf0954efb19d88621dc354bdcfd`
  - `AMENDMENT2` (Geodynamic TerraCore `H9d` Three-Shell Viscoplastic Architecture): `faf225067917b464ac25b2ae68ae1fa7bdf3179a2c461ec883490ea24ff9d7e3`
  - `AMENDMENT3` (Pre-Run Law-2 Steelman Repair: `MHPlate`, `SteelmanCore`, 2-Step `Arm A` CoT): `e441b07a97205f857a65f1b232b373cdcdc60fa6526d044d5c6fef856761e70e`
- **Date (UTC):** `2026-11-25` | **Owner:** `torus-telemetry`
- **Hardware & Provenance:** Live bare-metal NVIDIA GeForce RTX 3080 Laptop GPU (`8 GiB` VRAM), serialized via `flock` + `mlos gpu-lease --mode train` + `mlos stamp-run --zone B --require-gpu`, `HF_HUB_OFFLINE=1`, `PYTHONDONTWRITEBYTECODE=1`; zero model weights saved (`weights_saved = 0` recorded in all `6` protocol and results JSON artifacts).
- **Zone-B Hardware Receipts (`3/3` `clean_hardware_run=true`, `anomalies=[]`, `exit_code=0`, `compute_vram_mib: 0 -> 0`):**
  1. **Preserved Prototype Baseline (`H9a` v1, unmodified):** `mlos_zone_b_s109_h9a.json` (`receipt_sha256=1587a95bfb5b7459701631f71b69bf71f4ab5f2e8896739698c0b5eac01e3aa2`, `1,402.721 s`, `gpu_results_h9a/s109_gpu_full_results.json` `result_sha256=187e348d…`)
  2. **Amendment-3 Steelman (`H9a` v2):** `mlos_zone_b_s109_h9a_v2.json` (`receipt_sha256=f02e8bd8c1b0f313b4f0917a58657c47232774545bfde2e07ea034b17f32a8c2`, `1,956.129 s`, `gpu_results_h9a_v2/s109_gpu_full_results.json` `result_sha256=1f3c01d5…`)
  3. **Amendment-3 Steelman (`TerraCore` `H9b–H9d`):** `mlos_zone_b_s109_terracore.json` (`receipt_sha256=a1fff5a143216ba11e6514c9ed3e4665cdcdab97838ad07935793c3af01f9878`, `3,901.000 s`, `gpu_results_terracore/s109_gpu_full_results.json` `result_sha256=7e5fce10…`)
- **Total Bare-Metal Compute & Run Accounting:** `7,259.85 s` (`2h 01m 00s`) across **`114` full neural model trainings** over `3` locked seeds `[42, 137, 2026]` (`18` prototype `h9a` + `18` steelman `h9a_v2` + `78` `terracore` = `114` neural models, plus `18` lightweight `PlateSeamRouter` calibrations, `CB-1..CB-6` controls, `CS21_RESIDUAL_LEAK` probes, counterfactual $h^{(r)}$ interventions, and Portal-5 Darboux diagnostics). Operator-observed post-run host check confirmed `mlos gpu-lease --status` `held: false` (`58 °C`, `2 MiB / 8,192 MiB`, `0%` util).

---

## 1. Executive Scorecard (Strict 3-Valued Kill-Gate Verdicts)

| Hypothesis | Core Question (`PREREG-S109` + `Amendments 1–3`) | Strict Verdict | Primary Quantitative Evidence (`3` Seeds `[42, 137, 2026]`, Paired SE & 95% Bootstrap CI) |
| :--- | :--- | :--- | :--- |
| **`H9a`** | Shannon–Kolmogorov finite-capacity learnability obstruction on raw-deflate (`wbits=-15`) vs uncompressed English-CoT (`>= 15 pp` drop on BOTH regimes + decompressor/probe-LM controls) | **`CONFIRMED`** *(with explicit CoT vs non-CoT dissection)* | **`Arm A` (`English-CoT-15M`)** reaches **`100.00%`** (R1) / **`99.82%`** (R2) vs **`Arm B` (raw-deflate)** **`14.16%`** (R1, **`+85.84 pp, z=+51.13`**, CI `[+83.01, +88.82]`) and **`7.11%`** (R2, **`+92.71 pp, z=+160.40`**, CI `[+91.55, +93.31]`). Independently of CoT, matched `15M` **Decompressor Emulation** fails (`0.20%` R1 / **`0.00%`** R2 exact string inversion, `0/6,144`) and **Probe-LM** unpredictability jumps **`13.95×`** (`0.6088` vs `0.0436` bits/bit; redundancy $\Delta(B): 3.468 \to 0.453$ bits/byte). |
| **`H9b`** | Pure Canonical Symbolic Core (`scry` = `Arm C` / `Y = 1.00 Stagnant Lid`) beats `English-CoT-15M` by `>= 10 pp` AND `>= 2.0×` speed on Regime I while hitting Translator-DPI wall on Regime II | **`FALSIFIED`** | **Regime I Native (`CB-6` transducer + `ir_len=12`):** **`15.09% ± 7.54%`** vs `Arm A` **`100.00%`** (**`-84.91 pp, z=-11.26`** — FAIL). Native wall latency **`0.1309 ms`** vs `0.2113 ms` = **`1.614×`** speedup (`< 2.0×` gate, though **`2.46×` lower peak VRAM**: `349.8` vs `862.1 MiB`). `MHPlate` achieves **`100.00%`** English & Arabic IR accuracy; bottleneck is tied-weight looped Core grokking variance (`29.6% / 11.2% / 4.4%`), not IR translation. |
| **`H9c`** | Hybrid Looped Core + `<= 96`-bit capped $S^{31}$ residual (`Arm D`) beats `Arm A` on BOTH R2 accuracy (`>= +5 pp`) & wall speed (`>= 1.8×`), recovers `>= 50%` DPI gap, & passes `>= 85%` counterfactual audit | **`FALSIFIED`** | All security & modularity invariants **PASS** (`100%` frozen Core SHA-256, `0` skip paths, `0/18` `CS21_RESIDUAL_LEAK`, `CB-1..CB-6` clean, `§SWAP` drops `<= 0.33 pp`, `Y=0.25` recovers `100%` of `CB-5` `12.30%` mean / **`93.98%`** on Seed 42 with zero oracle modifier labels). **FAILS** primary Pareto & audit gates: best `Arm D` R2 **`12.30%`** vs `Arm A` `99.82%` (`-87.52 pp, z=-18.05`), R2 wall latency `0.2806 ms` vs `0.2129 ms` (`0.759×`), and counterfactual $h^{(r)}$ audit faithfulness **`16.6%–18.1% << 85%`**. |
| **`H9d`** | Geodynamic TerraCore (`AMENDMENT2`): Mobile-Lid $Y^* \in \{1/4, 1/2, 3/4\}$ strictly Pareto-dominates BOTH $Y=0$ (Magma Ocean) & $Y=1$ (Stagnant Lid) by `>= 2 SE`, plus Hodge split beats `NoHodge` on `§PLATE-SWAP` | **`FALSIFIED`** | Exact Bingham flux (`1.000 -> 0.117 -> 0.0625 -> 0.0625 -> 0.000`), Hodge orthogonality (`<= 4.06e-3` vs `0.939` `NoHodge`), Darboux dark-mode (`err <= 3.37e-15`, `448/480` kernel), and cocycle routing (`99.95–100.0%`, `err <= 1.79e-7`) all verify cleanly — **but three kill gates trigger:** (1) `Y=0.00` ALREADY passes `CS21_RESIDUAL_LEAK` (`+0.0015`) & `§SWAP` (`-0.02 pp`) with `12.08%` R2 matching/beating `Y=0.50` (`10.79%`, `z=-0.79`); (2) `Y_0.50` ties non-strawman `Y_0.50_NoHodge` on `§PLATE-SWAP` (`-0.16 pp, z=-0.47`); (3) audit faithfulness `16.6–18.1% << 85%`. |

---

## 2. Dataset Integrity, Triple `CS-08` Resource Parity, & Prototype-to-Steelman Provenance

### 2.1 Strictly Tuple-Disjoint Benchmark & Zero UTF-8 Truncation
- **Task:** Compositional 2-step modular arithmetic `(a op b) mod 16 = inter`, `(inter + c + modifier) mod 16 = ans`, with `a, b, c in {0..15}`, `op in {+, -, *, ^}`, `modifier = 0` on **Regime I** (formal symbolic syntax) and `modifier in {0, 1}` encoded purely via implicit natural-language pragmatic clauses (`"including/excluding the reserve unit"` / Arabic `"مع وحدة الاحتياط الإضافية"` / `"دون أي وحدة احتياط"`) plus numeric distractors on **Regime II**.
- **Strict Hold-Out (`0.0%` Tuple Overlap):** Deterministic SHA-256 partition of all `16,384` canonical `(a, b, c, op)` tuples reserves `~4,096` tuples exclusively for evaluation (`6,144` train / `2,048` eval per regime). Verified `train_eval_tuple_overlap == {"regime1": 0, "regime2": 0}` across all `3` seeds (`[42, 137, 2026]`).
- **Zero UTF-8 Truncation (`surf_len = 128`):** Maximum byte lengths across all datasets are `86 B` (`surface_en`), `117 B` (`surface_alt`, multi-byte UTF-8 Arabic), `72 B` (`surface_mixed`), and `80 B` (raw-deflate `wbits=-15`) — all strictly `<= 128 B`.

### 2.2 Exact Amendment-3 Triple `CS-08` Resource Parity (`15.00M ± 0.5%`, `F_infer ± 5%`, `F_train ± 5%`)

| System Architecture | `P_core` | `P_ext_in` | `P_ext_out` | `P_audit_head` | `P_total` (`vs 15M`) | `F_infer` (FLOPs/prob) | `F_train_total` (`2,000` steps × `B=128`) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Monolithic (`Arm A`, `Arm A'`, `Arm B`)** (`d=512, L=7, ffn=1040, surf=128`) | 15,023,648 | 0 | 0 | 0 | **15,023,648** (`+0.16%`) | 4,022,337,536 | 3.0892e15 |
| **TerraCore (`Arm C/D`, `Y=0..1`, `NoHodge`)** (`cd=512, cL=5, R=6, ir=24, ed=480, extL=1`) | 10,576,934 | 4,146,785 | 272 | 279,072 | **15,003,063** (`+0.02%`) | 4,002,016,288 | 3.0735e15 |
| **Ratio (`TerraCore / Monolithic`)** | — | — | — | charged | **`0.9986`** (`-0.14%`) | **`0.9949`** (`-0.51%`) | **`0.9949`** (`-0.51%`) |

### 2.3 Preserved Unmodified Prototype Baseline (`gpu_results_h9a/` vs `AMENDMENT3` Steelman)
Per anti-HARKing discipline, the initial unmodified 3-seed Zone-B baseline (`gpu_results_h9a/s109_gpu_full_results.json`, `mlos_zone_b_s109_h9a.json`, `receipt_sha256=1587a95b…`, `1,402.7 s`, `lr=1.2e-3`, `1,000` steps, single-pass `<PAD>` byte-127 pooling) is preserved untouched:
- Prototype `Arm A` reached only `7.57% ± 0.78%` (R1, `inter=25.5%`) and `6.84% ± 0.20%` (R2, `inter=23.7%`), vs prototype `Arm A'` `7.13% / 6.85%` and `Arm B` `7.81% / 6.43%` (`Arm A - Arm B`: `-0.24 pp` R1, `+0.41 pp` R2 — uninformative due to `Arm A` underfitting).
- Even in that initial baseline, the coding-obstruction controls already fired decisively: `Arm B` **Decompressor Emulation** achieved `84.51%` byte acc / `0.52%` exact string acc (R1) and `71.49%` byte acc / **`0.00%`** exact string acc (R2), while **Probe-LM** bits/bit jumped `11.19×` (`0.4754` deflate vs `0.0425` English).
- Single-seed pre-run diagnostics exposed that the prototype flat-pooled `ExternalSurfacePlate` achieved `0.00%` exact IR match and the prototype `RigidInnerCore` suffered `Track S107` (`W10-OBS-31`) antipodal Hopf phase reversal (`216°` at `R=5`). Locking `PREREG_S109_AMENDMENT3_STEELMAN_REPAIR.md` (`e441b07a…`) prior to the full 3-seed runs repaired `MHPlate` (`0.00% -> 100.00%` English & Arabic IR exact match) and steelmanned `Arm A` (`7.57% -> 100.00%` R1, `6.84% -> 99.82%` R2).

---

## 3. Detailed Live RTX 3080 Results & Mechanistic Dissection

### 3.1 Hypothesis `H9a`: Raw-Deflate Learnability Obstruction (`gpu_results_h9a_v2/`, `result_sha256=1f3c01d5…`)

| Arm (`15.02M`, `2,000` steps, `3` Seeds) | Regime I Exact Acc | Regime I Inter Acc | Regime II Exact Acc | Regime II Inter Acc | Wall `ms/prob` (R1 / R2) | Peak Eval VRAM (MiB) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| **`Arm A` (`English-CoT-15M`, 2-step CoT)** | **`1.0000 ± 0.0000`** | `1.0000 ± 0.0000` | **`0.9982 ± 0.0011`** | `0.9984 ± 0.0012` | `0.2113 / 0.2129` | `862.1` |
| **`Arm A'` (`Direct-Answer-15M`, non-CoT)** | `0.1517 ± 0.0275` | `0.0627 ± 0.0029` | `0.0804 ± 0.0023` | `0.0562 ± 0.0038` | `0.2088 / 0.2105` | `862.2` |
| **`Arm B` (`Compressed-Binary-15M`, raw-deflate)** | `0.1416 ± 0.0168` | `0.0723 ± 0.0081` | `0.0711 ± 0.0061` | `0.0575 ± 0.0013` | `0.2090 / 0.2101` | `862.2` |

- **Per-Seed `Arm A` (`42 / 137 / 2026`):** R1 `1.0000 / 1.0000 / 1.0000`; R2 `0.9985 / 0.9961 / 1.0000`.
- **Per-Seed `Arm A'`:** R1 `0.1597 / 0.1006 / 0.1948`; R2 `0.0776 / 0.0786 / 0.0850`.
- **Per-Seed `Arm B`:** R1 `0.1699 / 0.1431 / 0.1118`; R2 `0.0830 / 0.0630 / 0.0674`.
- **Paired-Seed `H9a` Deltas:**
  - `Arm A - Arm B` (Regime I): **`+85.84 pp` (`SE=1.68 pp`, `z=+51.13`, 95% CI `[+83.01, +88.82 pp]`)** — clears `>= 15 pp`.
  - `Arm A - Arm B` (Regime II): **`+92.71 pp` (`SE=0.58 pp`, `z=+160.40`, 95% CI `[+91.55, +93.31 pp]`)** — clears `>= 15 pp`.
  - `Arm A - Arm A'` (isolating 2-step CoT value): **`+84.83 pp` (`z=+30.85`)** on R1 and **`+91.78 pp` (`z=+540.16`)** on R2.
- **Amendment-1 §4.2 Direct Coding-Learnability Controls (100% Independent of CoT):**
  - **Empirical Entropy & Redundancy (`Delta = 8 - H_2`):** Uncompressed English $H_2 = 4.532$ bits/byte ($\Delta = 3.468$ bits/byte, mean `50.4 B`) vs raw-deflate $H_2 = 7.547$ bits/byte ($\Delta = 0.453$ bits/byte, mean `47.8 B` — `7.65×` redundancy collapse).
  - **Auxiliary Probe-LM Predictivity (`250` steps):** English **`0.0436 ± 0.0005` bits/bit** (`0.349` BPB) vs raw-deflate **`0.6088 ± 0.0044` bits/bit** (`4.871` BPB) — **`13.95×` higher finite-capacity neural unpredictability**.
  - **Decompressor-Emulation Control (`15.02M` inverting `deflate -> surface_en`, `600` steps):** Regime I `83.51%` byte acc / **`0.20%`** exact string match (`0.0020 / 0.0015 / 0.0024`); Regime II `55.82%` byte acc / **`0.00%`** exact string match (`0 / 6,144` exact strings across all 3 seeds!).
- **Honest Dissection (`H9a` = `CONFIRMED` with CoT transparency):** In the primary task comparison (`Arm A` vs `Arm B`), `Arm B` ran without 2-step CoT conditioning (matching `Arm A'`), so part of the `+85.8/+92.7 pp` accuracy gap reflects CoT decomposition (`Arm A` vs `Arm A'` = `+84.8/+91.8 pp`, while non-CoT `Arm A' - Arm B` = `+1.01/+0.93 pp`). Nevertheless, the matched `15M` Decompressor-Emulation failure (`0.00%` Regime-II exact inversion) and `13.95×` Probe-LM bits/bit jump directly confirm that finite-capacity neural models cannot invert raw-deflate coding even under dedicated decompression supervision.

### 3.2 Hypotheses `H9b`, `H9c`, & `H9d`: TerraCore Yield Sweep & Modularity Suite (`gpu_results_terracore/`, `result_sha256=7e5fce10…`)

#### 5-Point Bingham Yield Sweep + Non-Strawman `Y_0.50_NoHodge` (`3` Seeds `[42, 137, 2026]`, Frozen Stage-1 Core)

| Arm (`15.00M`) | Native R1 Acc (`ms`) | Plate R1 Acc | R2 Acc (`ms`) | Arabic `§SWAP` R2 (`Drop`) | Within `§SWAP` Drop | Active Flux | Hodge `orth` Max | `CS21` Leak (`+Ch`) | Audit Faith (`Shift`) | `§PLATE-SWAP` Stream (`Route`) | Mixed Seam Acc |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **`Y = 0.00` (Magma Ocean)** | `0.1509` (`0.1304`) | `0.1566` | `0.1208` (`0.2805`) | `0.1209` (`-0.02 pp`) | `-0.16 pp` | `1.0000` | `2.42e-3` | `+0.0015` | `0.1815` (`0.1779`) | `0.1006` (`99.95%`) | `0.0643` |
| **`Y = 0.25` (Mobile Lid)** | `0.1509` (`0.1310`) | `0.1576` | **`0.1230`** (`0.2806`) | `0.1209` (`+0.21 pp`) | `-0.05 pp` | `0.1173` | `4.06e-3` | `+0.0042` | `0.1776` (`0.1723`) | `0.0994` (`99.95%`) | `0.0630` |
| **`Y = 0.50` (Mobile Lid)** | `0.1509` (`0.1316`) | `0.1556` | `0.1079` (`0.2828`) | `0.1230` (`-1.51 pp`) | `-1.32 pp` | `0.0625` | `2.41e-3` | `-0.0011` | `0.1795` (`0.1761`) | `0.0981` (`100.0%`) | `0.0579` |
| **`Y = 0.75` (Mobile Lid)** | `0.1509` (`0.1309`) | `0.1507` | `0.1094` (`0.2809`) | `0.1105` (`-0.11 pp`) | `-0.24 pp` | `0.0625` | `3.43e-3` | `-0.0011` | `0.1663` (`0.1650`) | `0.0948` (`100.0%`) | `0.0583` |
| **`Y = 1.00` (Stagnant Lid / `Arm C`)** | `0.1509` (`0.1309`) | `0.1509` | `0.1108` (`0.2807`) | `0.1108` (`+0.00 pp`) | `+0.00 pp` | **`0.0000`** | `2.71e-3` | `-0.0011` | `0.1779` (`0.1751`) | `0.0942` (`99.99%`) | `0.0645` |
| **`Y_0.50_NoHodge` (Matched-Rank)** | `0.1509` (`0.1302`) | `0.1553` | `0.1173` (`0.2796`) | `0.1206` (`-0.33 pp`) | `-0.02 pp` | `0.1562` | `9.39e-1` | `+0.0003` | `0.1733` (`0.1693`) | `0.0997` (`99.99%`) | `0.0596` |
| **`Arm D-mono` (Unfrozen Anchor)** | — | `0.0552` | `0.0607` (`0.2073`) | — | — | — | — | `-0.0034` | `0.2668` | — | — |

*(Note on `eval_peak_vram_mib`: Native Regime I uses `349.8 MiB` — **`2.46×` lower VRAM** than `Arm A`'s `862.1 MiB`. Across the `Y` sweep, measured peak eval VRAM steps `689.7 -> 768.9 MiB` in `+15.6` to `+16.1 MiB` increments [mean `+15.8 MiB`/arm] purely due to retaining each Stage-2 `plate_en` object in `plates_en_by_y` until sweep completion — still `93–172 MiB` below `Arm A`.)*

#### Anti-Smuggling (`CB-1..CB-6`), Security, & Geometric Diagnostics (`3`-Seed Mean ± SE)
- **`CB-1` (Trivial Pass-Through Slot-1 Baseline):** `0.0640 ± 0.0050` (chance `0.0625`) — PASS *(implementation note: `s109_train_eval.py` evaluates `ir_pred[:, 1] % 16`, a constant slot-1 token `"("` predictor; `CB-2` below carries the substantive converter-only anti-smuggling control).*
- **`CB-2` (Frozen-Random Core — Substantive Converter-Only Control):** `0.0658 ± 0.0023` (chance) — PASS.
- **`CB-3` (Core Lesion / Batch Shuffle):** `0.0618 ± 0.0017` (chance) — PASS.
- **`CB-4` (Channel Ablation):** Residual-only (`ir=0`) = **`0.0623 ± 0.0004`** (exact chance; zero answer smuggling in `r`!); Symbolic-only (`r=0`) = `0.1108 ± 0.0356` (exact match to `Y = 1.00`).
- **`CB-5` (Oracle-IR Upper Bound):** R1 `0.1509 ± 0.0754`, R2 Symbolic (`r=0`) `0.1108 ± 0.0356`, R2 Hybrid (`r=±q_0`) `0.1230 ± 0.0494`.
- **`CB-6` (Regime-I Syntactic Transducer Trivial Core):** **`0.0513 ± 0.0040`** (`-1.12 pp` vs chance, strictly `<= chance + 5 pp` on all 3 seeds: `0.0522 / 0.0576 / 0.0439`) — PASS.
- **Stage-2 Isolation & Zero Skip Paths:** `all_core_sha_unchanged == True` across all `72` Stage-2 plates (`0` Core param gradients, bit-exact Core SHA-256); `all_zero_skip_verified == True` (`max_skip_grad == 0.0`); `any_cs21_leak_triggered == False` (`0/18`, max leak `+0.0068` above chance `<< 0.25`).
- **`MHPlate` Multilingual IR Translation:** **`1.0000`** (`100.00%`) exact 24-token IR recovery on ALL `3` seeds × ALL `6` `Y` configs across BOTH English (R1 & R2) AND Arabic (`alt` R2).
- **Portal-5 Darboux Dark-Mode Diagnostic:** Exact rank `32`, `dark_dim = 448` (`480 - 32`), intertwining error `<= 3.37e-15`, mean dark-mode kernel energy fraction `0.9168–0.9329` across `Y = 0..1`.
- **Track S50 Channel-2B Advection & Cocycle Conservation:** Mean advection norm `||r - v_unit||`: `0.4515 (Y=0)`, **`0.3903 (Y=0.25)`**, `0.4534 (Y=0.50)`, `0.3962 (Y=0.75)`, `0.0000 (Y=1.00)`, `0.6546 (Y_0.50_NoHodge)`. Multi-plate seam cocycle error `max |sum(alpha_i) - 1| <= 1.79e-7`.

### 3.3 Key Mechanistic Discoveries (Why `H9b`/`H9c`/`H9d` Falsified Despite `100%` Plate Modularity)
1. **Discrete Explicit CoT vs. Tied-Weight Continuous Looped Core (`W10-OBS-34`):**
   - `Arm A` (`100.00%` R1 / `99.82%` R2) decoupled Step 1 `(a op b) mod 16` and Step 2 `(inter + c + mod) mod 16` cleanly across **untied** layers `0..2 -> 3..6` (`split = n_layers // 2 = 3` in `s109_terracore_models.py`, vs Amendment-3's prose summary `0..3 -> 4..6`) via an explicit discrete intermediate step injection.
   - The **tied-weight** `5`-layer × `6`-loop hypersphere Core (`RigidInnerCore`, continuous $S^{511}$ loop states with no discrete intermediate readout) entered a high-variance stochastic grokking regime across seeds (`CB-5 R1`: Seed 42 **`29.64%`**, Seed 137 **`11.23%`**, Seed 2026 **`4.39%`** — mean `15.09%`, indistinguishable from non-CoT `Arm A'` `15.17%`), even with **`100.00%`** error-free canonical IR!
   - **Notable Positive Finding on Seed 42 (Zero-Oracle Modifier Discovery):** On grokking-active Seed 42 (`CB-5 R2_hyb = 22.0703%` vs `R2_sym = 18.0176%`, gap `+4.0527 pp`), Stage-2 plates trained **without any oracle modifier labels** discovered the missing pragmatic bit purely through frozen-Core input gradients, recovering exactly **`93.98%`** (`+3.8086 / +4.0527`) of the DPI gap at BOTH `Y = 0.00` (`21.8262%`, Arabic `21.9238%`) and `Y = 0.25` (`21.8262%`, Arabic `21.7773%`, using only `16.43%` active Bingham flux!), and outperforming unfrozen monolithic `Arm D-mono` (`5.52% / 6.07%`) across all 3 seeds!
2. **Why `H9d` Falsified (`AMENDMENT2` Clauses 1 & 3):**
   - Because the `<= 96`-bit capped $S^{31}$ residual at `Y = 0.00` (`Magma Ocean`) ALREADY achieved near-zero residual leak (`+0.0015 ± 0.0027` above chance) and zero `§SWAP` degradation (`-0.02 pp` Arabic, `-0.16 pp` within-English), Bingham soft-thresholding (`Y ∈ {0.25, 0.50, 0.75}`) did not Pareto-dominate `Y = 0.00` (`Y050 - Y000`: R2 `-1.29 pp, z = -0.79`; leak `-0.26 pp, z = -1.53`).
   - On `§PLATE-SWAP`, `Y_0.50` tied non-strawman `Y_0.50_NoHodge` on both 3-surface stream accuracy (`0.0981` vs `0.0997`, `-0.16 pp, z = -0.47`, both `99.99–100.0%` routing!) and hybrid mixed-seam accuracy (`0.0579` vs `0.0596`, `-0.16 pp, z = -0.51`). Hybrid mixed-seam collapsed to `~6.25%` chance across all `Y` arms because `plate_sym`'s learned absolute `pos_emb` (trained with symbolic tokens starting at byte `0`) shifted out-of-distribution when symbolic tokens started at byte `52` inside `"[plate:en] ... | [plate:sym] ..."`.
3. **Why Counterfactual Audit Faithfulness Failed (`16.6%–18.1% << 85%`):**
   - `AuditTraceDecoder` decodes from intermediate pass `h^(mid)` (pass 2 of 6, before loops 3–5 finish computing `ans`). Because the mid-grokking Core had not yet converged to deterministic `ans` separation at `h^(mid)`, patching `h^(mid)` produced only `16.6%–18.1%` agreement (`16.5%–17.8%` on answer-shifting interventions; `26.7%` on unfrozen `Arm D-mono`), honestly failing the strict `>= 85%` causal faithfulness gate.

---

## 4. Verification & Hygiene Receipts

- **CPU Pre-Flight Suite (`s109_cpu_preflight.py`, `CUDA_VISIBLE_DEVICES=""`):** `7/7 OK ×3` across `-I -B`, `-I -O -B`, and `-I -B -W error` (`0` volatile stdout bytes, `0` bare `assert`s, `100%` SHA-256 prereg pins verified across `PREREG-S109` + `Amendments 1–3`, causal `<EOS>` `ir_len=12` vs `ir_len=24` invariance verified `< 1e-5`, exact `15.0M` triple parity verified).
- **Dual `aletheia audit-check --strict-ancestors --safety-scan --scripts s109_cpu_preflight.py`:** Verified `PASS ×2` across both `aletheia-fix-lean-gates-v2` and `aletheia-fast-mutate` (`r4_scripts_passed=1/1`, `bare_assert=0, crlf=0, leak=0, pycache=0, safety_findings=0, ancestors=0`).
- **Artifacts (`weights_saved = 0` in all protocol/results JSONs):**
  - `s109_terracore_models.py`, `s109_train_eval.py`, `s109_cpu_preflight.py`, `REPORT_S109_GPU_EVAL.md`
  - `mlos_zone_b_s109_h9a.json`, `mlos_zone_b_s109_h9a_v2.json`, `mlos_zone_b_s109_terracore.json`
  - `gpu_results_h9a/`, `gpu_results_h9a_v2/`, `gpu_results_terracore/` (each containing `s109_locked_protocol.json` and `s109_gpu_full_results.json`, `0o600` in source track).
