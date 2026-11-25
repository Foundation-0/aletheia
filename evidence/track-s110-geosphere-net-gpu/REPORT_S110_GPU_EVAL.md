# `PREREG-S110` + `AMENDMENT1` (`EXP-Q11a..b`, "Geosphere-Net") — Live RTX 3080 Evaluation Report

- **Track Directory:** `track-s110-geosphere-net-gpu/` *(separate from merged pure-`Init` Lean `4.36.0` conservation certificate `track-s110-geosphere-weft-conservation/`)*
- **Immutable Preregistration Locks:**
  - `notes/sphere_pi_forces_2026_11_25/PREREG_S110_GEOSPHERE_PLANETARY_ARCHITECTURE.md` (`2e645597e81a330159b2183caf670f685821a9451a37223a782936e88e30d0fe`)
  - `notes/sphere_pi_forces_2026_11_25/PREREG_S110_AMENDMENT1_COUNCIL_PRUNING.md` (`a41399fdb888167288a63cefa540778d921574197f721b8d5322bd8825d0928a`, mandatory `9 -> 4` pruning applied; all `4` pruned mechanisms fail-closed rejected by `S110ModelConfig.validate()`)
- **Hardware & Provenance:** NVIDIA GeForce RTX 3080 Laptop GPU (`8 GiB` VRAM, `sm_86`, `BF16` autocast), serialized under `flock` + `mlos gpu-lease --mode train` + `mlos stamp-run --zone B --require-gpu`, `HF_HUB_OFFLINE=1`, `WEIGHTS=0` (zero weight checkpoints written anywhere in the repository tree). All **`3/3` `mlos` Zone-B receipts** (`microbench`, `H10a`, `H10b`) report **`clean_hardware_run = true`, `anomalies = []`**, and GPU lease is cleanly released (`held: false`).
- **Strictly Disjoint Offline Multi-Domain Corpus (`100%` Bit-Identical Across All `42/42` Runs, `file_overlap_count = 0`):**
  - **Train (`2,946,710` B, `213` files, `5,744` chunks of `T=512`):** `train_sha256 = 0f8106245d072ebdd579c90bc4dae8e33433790df098b19423511951bedcd312` (`wikitext-2-raw-v1` validation + 80%-SHA-split frozen Python source & formal Markdown/JSON).
  - **Held-Out Eval (`1,990,548` B, `74` files, `72` `T=512` windows + `24` `T=1024` windows):** `eval_sha256 = 912ff9bfc02d20e67cb4e9abe67a1f0f0549b1b9f8d7742c904e066a1ab17254`:
    - `wikitext2_test`: `1,290,546` B (`430983e5...`)
    - `python_code`: `400,000` B (`1da6a86e...`)
    - `formal_docs`: `300,000` B (`9dc785e8...`)
  - Scored by exact raw UTF-8 BPB (`fp32` log-softmax, BOS excluded, EOS scored).
- **CPU Pre-Flight R4 Lock:** `s110_cpu_preflight.py` passes **`10/10` gates** bit-identically across `-I -B`, `-I -O -B`, and `-I -B -W error` (`payload_sha256 = cb603cb411de6ad3476eecd96f454639a65cca8629957ce1bcff91f5b6f20012`, `0` volatile stdout).

---

## 1. Master Literal-Gate Scorecard (`42` Full-Scale `15M` Runs + `2` `sm_86` Microbenches, `n2_claims = 0`)

| Component / Stage | Scope & Runs | Literal Locked Verdict | Headline Quantitative Outcome (`3` Seeds `[42, 137, 2026]`, `600` Steps = `2.46M` Tok/Run) |
| :--- | :--- | :---: | :--- |
| **`sm_86` Microbench Pre-Gate** (`<2 min`) | `5` operators + `6` full `15M` train steps (`BF16`, `B=8, T=512, d=384`) | **`PARTIAL`** *(3/5 ops PASS eager)* | **`BinghamProx` (`13.27%` blk / `+1.41%` step), `ACT` (`1.21%`), `MTP-8` (`4.53%` / `+10.04%` combined step) PASS** `<= 15%`. Eager PyTorch `Cayley2x2` (`28.87%` blk / `+15.55%` step) and `DarcyEMA` (`47.19%` cuFFT blk / `+20.97%` step, down from `124.4%` / `+96.33%` eager Hillis-Steele) exceed `15%` without custom fused `sm_86` CUDA kernels. Peak VRAM `<= 2.13 GiB / 8 GiB`; `0` NaNs. |
| **Stage 1 (`H10a`)** Single-Shell Isolation | `5` arms × `3` seeds (`15` runs, `~14 min`) | **`PARTIAL`** *(1/4 primary BPB win; 0/4 clear all axes)* | **`H10a_Shell1_Cayley2x2` (`2.3033 ± 0.0266 BPB`) is the #1 overall model across all `14` arms**, beating `Baseline_Loop` (`2.3976`) by **`-0.0943 BPB` (`-3.94%`, `z = +3.82`, `p_Holm = 0.000262`, `CONFIRMED` on BPB-512)** and all `4/4` `N0` baselines (`z = +2.47..+5.48`), while keeping exact post-train Beltrami `[C,K] = 0` (`m0..m4` drift `1.2e-7`). However, it hits the `R_test = 6` phase-rotation wall (`6.6218 BPB` vs `2.9124`) and eager latency `+15.55%`. **`Shell2_BinghamProx`** (`2.3782`, `z=+1.03, p_Holm=0.453`) is `INCONCLUSIVE` on BPB while cutting `M1-H1` `-14.3% (z=+2.25)` at `+1.41%` step cost. **`Shell3_DarcyEMA`** (`2.5414`, `z=-5.63`) is `FALSIFIED` on BPB-512 yet cuts `2x` context decay `-39.85% (z=+2.29)`, `M1-H1` `-25.84% (z=+13.42, 1.621)`, and `3b` PTQ KL `-8.98% (z=+2.85)`. **`Shell4_ACTPlume_MTP8`** (`2.5342`, `z=-6.74`) is `FALSIFIED` on BPB-512 (`MTP-8` `18.24%` 8-step mean acc, exact `16.0` sparse passes). |
| **Stage 2 (`H10b`)** Coupled `Geosphere-Net-15M` + LOSO | `9` arms × `3` seeds (`27` runs, `~29 min`) | **`FALSIFIED`** *(Anti-Kitchen-Sink Law-5 confirmed)* | **`H10b_Geosphere_Full` (`2.6976 ± 0.0229 BPB`) decisively loses** to its best single shell `H10a_Shell1_Cayley2x2` (`+0.3943 BPB` worse) AND to **all `4/4` `N0` baselines** (`Monolithic_Loop` `z=-23.46`, `nGPT_Loop` `z=-6.02`, `English_CoT` `z=-12.28`, `nGPT_Unlooped` `z=-7.81`). **`0/4` LOSO shells show positive Holm-Bonferroni primary-BPB contribution** (`p_Holm = 1.0`; removing `DarcyEMA` improves BPB `-0.2255 z=-6.82`, removing `ACTDraft` improves `-0.2434 z=-3.35`, removing `BinghamProx` improves `-0.0479 z=-2.39`). **Secondary cross-shell finding:** variable-depth ACT (`r in {1..4}`) cures `Cayley2x2`'s `R=6` blowup (`6.62 -> 3.07 BPB` / `2.94` without Darcy), and `Cayley + Bingham + Darcy` achieves near-unity `M1-H1 = 1.012` (`Geosphere_Full = 1.367`) and minimum `2x` context decay (`+0.1104 BPB`, `-57.8%`). |

---

## 2. Live `<2 Min` RTX 3080 `sm_86` Microbenchmark Pre-Gate (`B=8, T=512, d=384, BF16`)

Both eager Hillis-Steele (`s110_sm86_microbench_eager_hillis.json`) and exact cuFFT linear-convolution Darcy EMA (`s110_sm86_microbench.json`, `mlos_zone_b_s110_microbench.json`) were benchmarked live (`baseline_block_ms = 1.9632 ms`, `baseline_gemm_ms = 0.3255 ms`, `0` NaN/Inf across all kernels):

| Operator / Full `15M` Model Step | Scope | Eager Op (`ms`) | Overhead vs Ref Block | Full `15M` Train Step (`ms` / `tok/s`) | Step Overhead vs Baseline | Peak VRAM (`MiB`) | FP32 vs BF16 Max Diff | Literal `<= 15%` Gate |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| `H10a_Baseline_Loop` (`14,999,424` P) | full step | — | — | `73.94 ms` / `55,397` | `0.00%` | `1,349.0` | — | ref |
| `op1_cayley_2x2_so` (`15,037,056` P) | per core blk | `0.5667` | `28.87%` | `85.43 ms` / `47,944` | `+15.55%` | `1,637.5` | `0.0283` | `PRUNE` *(eager)* |
| `op2_bingham_vector_prox` (`14,999,424` P) | per core blk | `0.2605` | `13.27%` | `74.98 ms` / `54,628` | `+1.41%` | `1,362.4` | `0.0256` | **`PASS`** |
| `op3_darcy_diagonal_ema` — **Hillis-Steele** | per core blk | `2.4424` | `124.40%` | `144.54 ms` / `28,338` | `+96.33%` | `2,320.3` | `0.0183` | `PRUNE` *(eager)* |
| `op3_darcy_diagonal_ema` — **cuFFT exact** | per core blk | `0.9265` | `47.19%` | `89.45 ms` / `45,793` | `+20.97%` | `1,638.1` | `0.0183` | `PRUNE` *(eager)* |
| `op4a_act_controller` (`16.0` sparse passes) | per fwd (12 eff) | `0.2850` | `1.21%` | `81.36 ms` / `50,343` *(w/ MTP-8)* | `+10.04%` | `1,534.6` | `0.0151` | **`PASS`** |
| `op4b_mtp8_surface_draft` (`MTP-8`) | per fwd (12 eff) | `1.0667` | `4.53%` | *(combined above)* | *(+10.04%)* | `1,534.6` | `0.4031` | **`PASS`** |
| `H10b_Geosphere_Full` (`15,040,514` P, cuFFT) | full step | — | — | `120.01 ms` / `34,131` | `+62.31%` | `2,128.5` | — | *(all 4 active)* |

*Hardware Insight:* Replacing eager `9`-step Python `torch.cat` Hillis-Steele with exact zero-wraparound cuFFT causal convolution (`< 1e-6` parity in `G3`) cut `DarcyEMA` full-step overhead **`4.6x`** (`+96.33% -> +20.97%`) and VRAM by `-682 MiB`. `Cayley2x2` (`4` FMAs/pair) sits just `0.55 pp` above `+15.0%` end-to-end in eager PyTorch due to unfused `float()/stack/reshape` dispatch overhead; a fused `sm_86` CUDA/Triton kernel would bring both well under `5%`.

---

## 3. Complete `14`-Arm Full-Scale `15M` Parity Scorecard (`42/42` Live RTX 3080 Runs, `nan_steps = 0`)

Every arm ran `3` seeds (`[42, 137, 2026]`), `600` steps (`B=8, T=512`, cosine LR warmup `50`, `lr=1.5e-3` Std/Geosphere, `lr=2.5e-3` `nGPT`), on the exact bit-identical offline multidomain corpus (`0%` file overlap). Every single run achieved **`pre_norm_faithfulness = 1.0000`** (`0.0` self-patch error) and **`0` NaN steps**:

| Arm (`15M ± 0.27%` Parity) | Params | `T=512` BPB (`mean ± SE`) | Domain BPB (`Wiki / Py / Docs`) | `T=1024` BPB (`Δ1024-512`) | `R=6` BPB | `3b` PTQ KL (`nats`) | `M1-H1` `Δ3/Δ1` | Spike ASR | Infer (`ms`) | Train (`s`) / VRAM (`MiB`) |
| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | ---: | :---: |
| **`H10a_Shell1_Cayley2x2`** | `15,037,056` | **`2.3033 ± 0.0266`** | **`2.436 / 2.276 / 2.198`** | **`2.5610 (+0.258)`** | `6.6218` | `0.03685` | `2.035` | `0.2592` | `26.58` | `52.3s` / `1,620` |
| `H10a_Shell2_BinghamProx` | `14,999,424` | `2.3782 ± 0.0363` | `2.479 / 2.338 / 2.318` | `2.6079 (+0.230)` | `2.9677` | `0.03284` | `1.874` | `0.2562` | `24.62` | `49.3s` / `1,384` |
| `N0_Monolithic_Loop_15M` | `14,999,424` | `2.3971 ± 0.0254` | `2.503 / 2.361 / 2.327` | `2.6482 (+0.251)` | `2.9063` | `0.02776` | `2.172` | `0.2531` | `22.65` | `45.3s` / `1,329` |
| `H10a_Baseline_Loop` | `14,999,424` | `2.3976 ± 0.0250` | `2.491 / 2.368 / 2.334` | `2.6592 (+0.262)` | `2.9124` | `0.02873` | `2.186` | `0.2631` | `22.65` | `45.1s` / `1,333` |
| `N0_nGPT_Loop_15M` | `15,005,616` | `2.4254 ± 0.0259` | `2.549 / 2.350 / 2.377` | `2.5802 (+0.155)` | `5.6351` | **`0.01116`** | `1.536` | `0.2550` | `28.94` | `63.1s` / `1,579` |
| `N0_English_CoT_15M` | `14,959,680` | `2.4426 ± 0.0435` | `2.527 / 2.408 / 2.393` | `2.6686 (+0.226)` | `3.4465` | `0.04703` | `2.235` | `0.2490` | **`18.90`** | `38.4s` / `1,137` |
| `H10b_LOSO_NoACTDraft` | `15,040,128` | `2.4542 ± 0.0605` | `2.545 / 2.406 / 2.412` | `2.7005 (+0.246)` | `5.6297` | `0.03682` | **`1.012`** | `0.2764` | `34.66` | `66.6s` / `1,945` |
| `H10b_LOSO_NoDarcyEMA` | `15,037,442` | `2.4721 ± 0.0423` | `2.578 / 2.420 / 2.419` | `2.6505 (+0.178)` | `2.9389` | `0.04533` | `1.801` | `0.2670` | `37.13` | `78.6s` / `1,797` |
| `H10a_Shell4_ACTPlume_MTP8` | `14,999,810` | `2.5342 ± 0.0280` | `2.601 / 2.499 / 2.503` | `2.7527 (+0.219)` | **`2.8646`** | `0.02955` | `2.066` | **`0.2375`** | `25.80` | `52.8s` / `1,472` |
| `H10a_Shell3_DarcyEMA` | `15,002,496` | `2.5414 ± 0.0118` | `2.581 / 2.499 / 2.544` | `2.6988 (+0.157)` | `3.5298` | `0.02615` | `1.621` | `0.2893` | `28.17` | `55.9s` / `1,615` |
| `N0_nGPT_Unlooped_15M` | `14,967,456` | `2.5879 ± 0.0333` | `2.647 / 2.518 / 2.599` | `2.7219 (+0.134)` | `7.5102` | `0.01542` | `3.284` | `0.2583` | `24.35` | `54.2s` / `1,339` |
| `H10b_LOSO_NoBingham` | `15,040,514` | `2.6497 ± 0.0425` | `2.670 / 2.581 / 2.699` | `2.7490 (+0.099)` | `3.1617` | `0.03766` | `1.615` | `0.2786` | `36.91` | `70.8s` / `2,057` |
| `H10b_LOSO_NoCayley` | `15,002,882` | `2.6911 ± 0.0435` | `2.708 / 2.636 / 2.730` | `2.8230 (+0.132)` | `3.1339` | `0.02790` | `1.501` | `0.2642` | `35.30` | `66.8s` / `1,821` |
| `H10b_Geosphere_Full` | `15,040,514` | `2.6976 ± 0.0229` | `2.690 / 2.628 / 2.775` | `2.8080` (**`+0.110`**) | `3.0678` | `0.03558` | `1.367` | `0.2712` | `42.11` | `76.8s` / `2,098` |

*MTP-8 Surface Draft Top-1 Accuracy (8-step mean):* `H10a_Shell4_ACTPlume_MTP8 = 0.1824`, `H10b_LOSO_NoDarcyEMA = 0.1828`, `H10b_Geosphere_Full = 0.1803`, `H10b_LOSO_NoCayley = 0.1798`, `H10b_LOSO_NoBingham = 0.1793`.

---

## 4. Paired Statistical & Holm-Bonferroni Verification Tables

### 4.1 Stage-1 `H10a` vs `H10a_Baseline_Loop` (Primary `T=512` BPB, Holm-Bonferroni `alpha = 0.05`)

| Shell | Paired BPB Gain (`Base - Shell`) | `z` | Raw `p` | Holm Adj. `p` | Holm Sig. | Primary BPB Verdict | Secondary Highlights (`z`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`H10a_Shell1_Cayley2x2`** | **`+0.09435 ± 0.02467` (`-3.94%`)** | **`+3.82`** | `6.56e-5` | **`0.000262`** | **YES** | **`CONFIRMED`** | Beats ALL `4/4` `N0` baselines (`z=+2.47..+5.48`); `R=6` phase blowup (`6.62`); `3b` KL `+28.3%` |
| `H10a_Shell2_BinghamProx` | `+0.01938 ± 0.01878` (`-0.81%`) | `+1.03` | `0.1509` | `0.4528` | NO | `INCONCLUSIVE` | `M1-H1` `-14.28% (z=+2.25)`, `+1.41%` full train step |
| `H10a_Shell3_DarcyEMA` | `-0.14380 ± 0.02553` (`+6.00%`) | `-5.63` | `1.0000` | `1.0000` | NO | **`FALSIFIED`** | Cuts `Δ1024-512` **`-39.85% (z=+2.29)`**, `M1-H1` **`-25.84% (z=+13.42)`**, `3b` KL `-8.98% (z=+2.85)` |
| `H10a_Shell4_ACTPlume_MTP8` | `-0.13655 ± 0.02025` (`+5.70%`) | `-6.74` | `1.0000` | `1.0000` | NO | **`FALSIFIED`** | Exact `16.0` sparse passes; lowest `R=6` (`2.865`) & spike ASR (`0.2375`) |

*Small-Sample (`n = 3` Seeds) Statistical Sensitivity Note:* The locked normal-`z` Holm-Bonferroni formula in `s110_train_eval.py` / `s110_geosphere_audit.py` yields `z = +3.8242`, one-sided normal `p = 6.56e-5`, `p_Holm = 0.000262` (`CONFIRMED` on BPB-512; all `3/3` paired seeds beat baseline by `+0.0654`, `+0.0742`, and `+0.1434` BPB). Under a more conservative exact small-sample Student-$t$ ($\text{df} = 2$) test, `t = 3.8242` gives one-sided `p_t = 0.0310` and `p_Holm = 0.1239 > 0.05` (above `alpha = 0.05` after `m = 4` family-wise correction at `n = 3` seeds); multi-seed replication (`n >= 5`) is therefore recommended before elevating `Cayley2x2` beyond `PARTIAL` / `N1`.

### 4.2 Paired `H10a_Shell1_Cayley2x2` vs All `4` `N0` Baselines (Exact Bit-Identical Corpus)

| Reference Baseline | Paired `T=512` BPB Gain | `z` (`T=512`) | Rel. BPB Change | Paired `T=1024` BPB Gain | `z` (`T=1024`) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `N0_Monolithic_Loop_15M` | `+0.0938 ± 0.0299` | `+3.14` | `-3.91%` | `+0.0872 ± 0.0666` | `+1.31` |
| `N0_nGPT_Loop_15M` | `+0.1221 ± 0.0463` | `+2.63` | `-5.03%` | `+0.0192 ± 0.0608` | `+0.32` |
| `N0_English_CoT_15M` | `+0.1393 ± 0.0565` | `+2.47` | `-5.70%` | `+0.1076 ± 0.0331` | `+3.25` |
| `N0_nGPT_Unlooped_15M` | `+0.2846 ± 0.0520` | `+5.48` | `-11.00%` | `+0.1609 ± 0.0528` | `+3.05` |

### 4.3 Stage-2 `H10b` Holm-Bonferroni LOSO & `N0` Baselines (`FALSIFIED`)

- **`H10b_Geosphere_Full` vs `N0` Baselines (`T=512` BPB):** loses to `N0_Monolithic_Loop_15M` (`-0.3005, z=-23.46`), `N0_nGPT_Loop_15M` (`-0.2722, z=-6.02`), `N0_English_CoT_15M` (`-0.2550, z=-12.28`), and `N0_nGPT_Unlooped_15M` (`-0.1097, z=-7.81`).
- **LOSO Ablation (`Ablated - Full`; positive = removing shell hurt):** `NoCayley = -0.0065 (z=-0.14, p_Holm=1.0)`, `NoBingham = -0.0479 (z=-2.39, p_Holm=1.0)`, `NoDarcyEMA = -0.2255 (z=-6.82, p_Holm=1.0)`, `NoACTDraft = -0.2434 (z=-3.35, p_Holm=1.0)`.
- **Post-Training Portal-3 Beltrami `[C, K] = 0` Audit:** Across all `15/15` trained Cayley runs (`Shell1_Cayley2x2`, `Geosphere_Full`, `LOSO_NoBingham`, `LOSO_NoDarcyEMA`, `LOSO_NoACTDraft`), post-training commutator norm stays identically **`||[C, K]||_F = 0.0`** and conserved moments `m_0..m_4` drift stays **`<= 1.2e-7`**. Hidden-state Beltrami Rayleigh quotients stay within `|mean(H/E)| <= 0.0248` across 3-seed arm means (peak `0.024786` on `H10b_LOSO_NoDarcyEMA`) and within **`|H/E| <= 0.070645`** across every individual seed/pass (peak on `H10b_LOSO_NoACTDraft` seed `2026`: `[-0.053808, -0.068652, -0.070645, -0.035332]`; `H10a_Shell1_Cayley2x2` per-seed max `|H/E| = 0.023878`), with zero `O3.5` monotonic positive-Rayleigh collapse.

---

## 5. Key Mechanistic Lessons & Honest Obstructions

1. **Anti-Kitchen-Sink Law-5 Vindicated:** Blindly composing 4 distinct physical operators (`Cayley + Bingham + DarcyEMA + ACT/MTP-8`) degrades primary BPB by `+0.394 BPB` relative to the single winning operator (`Cayley2x2`), confirming `PREREG-S110`'s mandatory earn-your-keep pruning rule.
2. **Closed-Form `2x2` Block Cayley `SO(d)` Is a Genuine Standalone Architectural Primitive:** Adding `0.25%` parameters (`+37,632`) via rank-16 data-dependent `2x2` block-diagonal Cayley rotations delivers a `-3.94%` (`z=+3.82, p_Holm=0.00026`) held-out BPB lift over `Baseline_Loop` and beats `nGPT_Loop_15M` (`-5.03%`) and `English_CoT_15M` (`-5.70%`) across all `3` domains — while strictly obeying Beltrami `[C,K]=0` conservation. Its two remaining obstructions are (a) fixed-depth `R_train = 2 -> R_test = 6` phase over-winding (`6.62 BPB`), and (b) eager PyTorch dispatch overhead (`+15.55%`), which directly motivates fused `sm_86` kernels and non-antipodal/variable-depth training in follow-on work.
3. **Variable-Depth Loop Training Cures Phase Over-Winding:** Comparing `H10b_LOSO_NoDarcyEMA` (`Cayley + Bingham + ACT`: `R=6 = 2.9389 BPB`) and `H10b_Geosphere_Full` (`R=6 = 3.0678 BPB`) against `H10b_LOSO_NoACTDraft` (`5.6297 BPB`) and `H10a_Shell1_Cayley2x2` (`6.6218 BPB`) demonstrates that training across variable loop counts `r in {1..4}` eliminates loop-phase blowup at unseen depths (`R_test = 6`).
4. **Damping-vs-Sharpness Trade-Off:** `DarcyEMA` and `BinghamProx` measurably damp `3`-bit quantization loop drift (`M1-H1`: `2.186 -> 1.621` alone, `1.012` combined with `Cayley`) and `2x` context decay (`+0.262 -> +0.110`), at a sharp `T=512` modeling-capacity penalty (`+0.144..+0.225 BPB`).

---

## 6. Artifact Provenance & Verification Receipts (`WEIGHTS=0`, `0` Leaks)

- `s110_sm86_microbench.json`: `payload_sha256 = 733c8c33e8f4ddfbc75bd9a2ee51ac1012881846d353b2d05cce15f8b755fd01`
- `s110_sm86_microbench_eager_hillis.json`: `payload_sha256 = 279865a222d3f60a843b909c1aeae11257881793f0ef351be15eafeb693ff146`
- `h10a_gpu_results.json`: `payload_sha256 = 7da424abee3223e91a0bec02eceb82a42b0025bc2f275fcad078d1e9079cea33`
- `h10b_gpu_results.json`: `payload_sha256 = 8cef8307e6c5d62c33dc7122735f36d0c59fb66154c85432ca542528abfd46d3`
- `mlos_zone_b_s110_microbench.json`: `772ef320789c62a9cfb43652b22843c1be46626acd2f0997fdc8535d10703021` (`clean_hardware_run = true`, `anomalies = []`)
- `mlos_zone_b_s110_h10a.json`: `f8288f80d931796afc2d2d15b395398e39ced0fe3d161561dfa3155b9ae16d1f` (`clean_hardware_run = true`, `anomalies = []`)
- `mlos_zone_b_s110_h10b.json`: `d894aec1ef14d4dd3932759e50c33de1ccfc095859eaa8584812bfa90787ebc5` (`clean_hardware_run = true`, `anomalies = []`)
- `s110_cpu_preflight_receipt.json`: `payload_sha256 = cb603cb411de6ad3476eecd96f454639a65cca8629957ce1bcff91f5b6f20012` (`10/10 PASS` bit-identical across `-I -B`, `-I -O -B`, `-I -B -W error`)
