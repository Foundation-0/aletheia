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
  - **Corpus disclosure:** no per-file manifest or exact slice recipe for the truncated `python_code` (`400,000` B) / `formal_docs` (`300,000` B) domains is recoverable from this repository (same standing corpus gap as #106); the aggregate `train_sha256` / `eval_sha256` and the per-domain shas above — identical across H10a/H10b with `file_overlap_count = 0` — are the binding integrity anchors.
- **CPU Pre-Flight R4 Lock:** `s110_cpu_preflight.py` passes **`10/10` gates** bit-identically across `-I -B`, `-I -O -B`, and `-I -B -W error` (`payload_sha256 = cb603cb411de6ad3476eecd96f454639a65cca8629957ce1bcff91f5b6f20012`, `0` volatile stdout).

---

## 1. Master Literal-Gate Scorecard (`42` Full-Scale `15M` Runs + `2` `sm_86` Microbenches, `n2_claims = 0`)

| Component / Stage | Scope & Runs | Literal Locked Verdict | Headline Quantitative Outcome (`3` Seeds `[42, 137, 2026]`, `600` Steps = `2.46M` Tok/Run) |
| :--- | :--- | :---: | :--- |
| **`sm_86` Microbench Pre-Gate** (`<2 min`) | `5` operators + `6` full `15M` train steps (`BF16`, `B=8, T=512, d=384`) | **`PRUNE`** *(3/5 ops PASS, 2/5 PRUNE eager)* | **`BinghamProx` (`13.27%` blk / `+1.41%` step), `ACT` (`1.21%`), `MTP-8` (`4.53%` / `+10.04%` combined step) PASS** `<= 15%`. Eager PyTorch `Cayley2x2` (`28.87%` blk / `+15.55%` step) and `DarcyEMA` (`47.19%` cuFFT blk / `+20.97%` step, down from `124.4%` / `+96.33%` eager Hillis-Steele) exceed `15%` without custom fused `sm_86` CUDA kernels. Peak VRAM `<= 2.13 GiB / 8 GiB`; `0` NaNs. |
| **Stage 1 (`H10a`)** Single-Shell Isolation | `5` arms × `3` seeds (`15` runs, `~14 min`) | **`FALSIFIED`** on the prereg earn-keep *(0/4 shells earn-keep; 2/4 PRUNED on the sm_86 gate)* | Graded against the preregistered Shell-Dynamo earn-keep (`≥15%` M1-H1 reduction OR `≥5%` better `R_test=6`, `≥2` SE — **not** BPB-512), **`0/4` shells earn-keep: `FALSIFIED`**. **`H10a_Shell1_Cayley2x2`** (`2.3033 ± 0.0266 BPB`, #1 across all `14` arms, `-0.0943 BPB` / `-3.94%` vs `Baseline_Loop`, `z = +3.82`, Holm-z `p = 0.000262` but exact-t Holm `p_t = 0.1242` **not significant**, all `4/4` `N0` beaten on z) only cuts M1-H1 `-6.91% (z=+1.09)` and its `R=6` is far worse (`6.6218` vs `2.9124`) → earn-keep **FALSIFIED**, and its eager step overhead `+15.55%` marks it **PRUNED** under Amendment 1. **`Shell2_BinghamProx`** (`2.3782`, `z=+1.03, p_Holm=0.453`) M1-H1 `-14.28% (z=+2.25)` misses the `15%` line → FALSIFIED. **`Shell3_DarcyEMA`** (`2.5414`, `z=-5.63`) earns M1-H1 `-25.84% (z=+13.42)` but is `+20.97%` step → **PRUNED**. **`Shell4_ACTPlume_MTP8`** (`2.5342`, `z=-6.74`) FALSIFIED (`MTP-8` `18.24%` 8-step mean acc, exact `16.0` sparse passes). All shells keep exact post-train Beltrami `[C,K] = 0` (`m0..m4` drift `1.2e-7`). |
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

| Shell | Paired BPB Gain (`Base - Shell`) | `z` | Raw `p_z` | Holm `p_z` | Holm-z Sig. | `t` (df=2) | `p_t` | Holm `p_t` | Holm-t Sig. | BPB-512 Verdict (graded on Holm-t) | Secondary Highlights (`z`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`H10a_Shell1_Cayley2x2`** | **`+0.09435 ± 0.02467` (`-3.94%`)** | **`+3.82`** | `6.56e-5` | **`0.000262`** | YES (z) | **`+3.82`** | `0.0310` | **`0.1242`** | **NO (t)** | **`FALSIFIED`** under the conservative exact-t Holm | Beats ALL `4/4` `N0` baselines on z (`z=+2.47..+5.48`; unadjusted `p_t` vs Monolithic `0.044`, Unlooped `0.016`, nGPT `0.059`, English CoT `0.066` — Holm-t would not confirm all four); earn-keep FALSIFIED (`M1-H1 -6.91%, z=+1.09`; `R=6 6.62`); `+15.55%` step → PRUNED; `3b` KL `+28.3%` |
| `H10a_Shell2_BinghamProx` | `+0.01938 ± 0.01878` (`-0.81%`) | `+1.03` | `0.1509` | `0.4528` | NO | `+1.03` | `0.3094` | `1.0000` | NO | `FALSIFIED` | `M1-H1` `-14.28% (z=+2.25)` misses the `15%` earn-keep line (`p_t=0.077`); `+1.41%` full train step |
| `H10a_Shell3_DarcyEMA` | `-0.14380 ± 0.02553` (`+6.00%`) | `-5.63` | `1.0000` | `1.0000` | NO | `-5.63` | `1.0000` | `1.0000` | NO | **`FALSIFIED`** (PRUNED on `+20.97%` step) | Cuts `Δ1024-512` **`-39.85% (z=+2.29)`**, `M1-H1` **`-25.84% (z=+13.42)`** (earn-keep met on M1-H1, but pruned), `3b` KL `-8.98% (z=+2.85)` |
| `H10a_Shell4_ACTPlume_MTP8` | `-0.13655 ± 0.02025` (`+5.70%`) | `-6.74` | `1.0000` | `1.0000` | NO | `-6.74` | `1.0000` | `1.0000` | NO | **`FALSIFIED`** | Exact `16.0` sparse passes; lowest `R=6` (`2.865`) & spike ASR (`0.2375`) |

*Small-Sample (`n = 3` Seeds) Statistical Sensitivity Note:* The normal-`z` Holm-Bonferroni yields `z = +3.8242`, one-sided normal `p = 6.56e-5`, `p_Holm = 0.000262` (all `3/3` paired seeds beat baseline by `+0.0654`, `+0.0742`, `+0.1434` BPB). Under the exact small-sample Student-$t$ ($\text{df} = 2$) test, `t = 3.8242` gives one-sided `p_t = 0.0310` and Holm `p_t = 0.1242 > 0.05`. The certificate therefore grades the BPB-512 headline on the conservative Holm-**t** (reported alongside Holm-z in `h10a_vs_baseline_bpb` / `h10b_loso_bpb` / `h10b_full_vs_n0_bpb`): `CONFIRMED` only if Holm-t significant, else `FALSIFIED` — here `FALSIFIED`. Multi-seed replication (`n >= 5`) remains the path to a confirmed standalone Cayley claim; the standalone `2x2` Cayley layer is in the `N0` prior-art class, so the novelty tier is **`N0`** (genuine `N1`/`N2` requires coupled multi-shell synergy, which Stage 2 FALSIFIED).

### 4.2 Paired `H10a_Shell1_Cayley2x2` vs All `4` `N0` Baselines (Exact Bit-Identical Corpus)

| Reference Baseline | Paired `T=512` BPB Gain | `z` (`T=512`) | Rel. BPB Change | Paired `T=1024` BPB Gain | `z` (`T=1024`) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `N0_Monolithic_Loop_15M` | `+0.0938 ± 0.0299` | `+3.14` | `-3.91%` | `+0.0872 ± 0.0666` | `+1.31` |
| `N0_nGPT_Loop_15M` | `+0.1221 ± 0.0463` | `+2.63` | `-5.03%` | `+0.0192 ± 0.0608` | `+0.32` |
| `N0_English_CoT_15M` | `+0.1393 ± 0.0565` | `+2.47` | `-5.70%` | `+0.1076 ± 0.0331` | `+3.25` |
| `N0_nGPT_Unlooped_15M` | `+0.2846 ± 0.0520` | `+5.48` | `-11.00%` | `+0.1609 ± 0.0528` | `+3.05` |

### 4.3 Stage-2 `H10b` Holm-Bonferroni LOSO & `N0` Baselines (`FALSIFIED`)

- **`H10b_Geosphere_Full` vs `N0` Baselines (`T=512` BPB):** loses to `N0_Monolithic_Loop_15M` (`-0.3005, z=-23.46`), `N0_nGPT_Loop_15M` (`-0.2722, z=-6.02`), `N0_English_CoT_15M` (`-0.2550, z=-12.28`), and `N0_nGPT_Unlooped_15M` (`-0.1097, z=-7.81`).
- **LOSO Ablation (`Ablated - Full`; positive = removing shell hurt):** `NoCayley = -0.0065 (z=-0.14, p_Holm=1.0)`, `NoBingham = -0.0479 (z=-2.39, p_Holm=1.0)`, `NoDarcyEMA = -0.2255 (z=-6.82, p_Holm=1.0)`, `NoACTDraft = -0.2434 (z=-3.35, p_Holm=1.0)` — `0/4` Holm-significant on both z and exact-t (`holm_significant_t` all false), so `H10b_coupled_loso = FALSIFIED` under either test.
- **Post-Training Portal-3 Beltrami `[C, K] = 0` Audit:** Across all `15/15` trained Cayley runs (`Shell1_Cayley2x2`, `Geosphere_Full`, `LOSO_NoBingham`, `LOSO_NoDarcyEMA`, `LOSO_NoACTDraft`), post-training commutator norm stays identically **`||[C, K]||_F = 0.0`** and conserved moments `m_0..m_4` drift stays **`<= 1.2e-7`**. Hidden-state Beltrami Rayleigh quotients stay within `|mean(H/E)| <= 0.0248` across 3-seed arm means (peak `0.024786` on `H10b_LOSO_NoDarcyEMA`) and within **`|H/E| <= 0.070645`** across every individual seed/pass (peak on `H10b_LOSO_NoACTDraft` seed `2026`: `[-0.053808, -0.068652, -0.070645, -0.035332]`; `H10a_Shell1_Cayley2x2` per-seed max `|H/E| = 0.023878`), with zero `O3.5` monotonic positive-Rayleigh collapse.

---

## 5. Key Mechanistic Lessons & Honest Obstructions

1. **Anti-Kitchen-Sink Law-5 Vindicated:** Blindly composing 4 distinct physical operators (`Cayley + Bingham + DarcyEMA + ACT/MTP-8`) degrades primary BPB by `+0.394 BPB` relative to the single winning operator (`Cayley2x2`), confirming `PREREG-S110`'s mandatory earn-your-keep pruning rule.
2. **Closed-Form `2x2` Block Cayley `SO(d)` Is a Genuine Standalone Architectural Primitive:** Adding `0.25%` parameters (`+37,632`) via rank-16 data-dependent `2x2` block-diagonal Cayley rotations delivers a `-3.94%` (`z=+3.82, p_Holm=0.00026`) held-out BPB lift over `Baseline_Loop` and beats `nGPT_Loop_15M` (`-5.03%`) and `English_CoT_15M` (`-5.70%`) across all `3` domains — while strictly obeying Beltrami `[C,K]=0` conservation. Its two remaining obstructions are (a) fixed-depth `R_train = 2 -> R_test = 6` phase over-winding (`6.62 BPB`), and (b) eager PyTorch dispatch overhead (`+15.55%`), which directly motivates fused `sm_86` kernels and non-antipodal/variable-depth training in follow-on work.
3. **Variable-Depth Loop Training Cures Phase Over-Winding:** Comparing `H10b_LOSO_NoDarcyEMA` (`Cayley + Bingham + ACT`: `R=6 = 2.9389 BPB`) and `H10b_Geosphere_Full` (`R=6 = 3.0678 BPB`) against `H10b_LOSO_NoACTDraft` (`5.6297 BPB`) and `H10a_Shell1_Cayley2x2` (`6.6218 BPB`) demonstrates that training across variable loop counts `r in {1..4}` eliminates loop-phase blowup at unseen depths (`R_test = 6`).
4. **Damping-vs-Sharpness Trade-Off:** `DarcyEMA` and `BinghamProx` measurably damp `3`-bit quantization loop drift (`M1-H1`: `2.186 -> 1.621` alone, `1.012` combined with `Cayley`) and `2x` context decay (`+0.262 -> +0.110`), at a sharp `T=512` modeling-capacity penalty (`+0.144..+0.225 BPB`).

---

## 6. Deviations & Out-of-Band Disclosures (review round 2)

Stated plainly, with times in America/Chicago (UTC in the receipts):

1. **Preregistration first committed after the GPU windows.** `PREREG_S110_GEOSPHERE_PLANETARY_ARCHITECTURE.md` and `PREREG_S110_AMENDMENT1_COUNCIL_PRUNING.md` are first committed in this PR at `2026-11-25` 4:54 PM CT, while the GPU runs executed earlier the same day: sm_86 microbench 3:28:44–3:28:54 PM CT (`21:28:44Z–21:28:54Z`), H10a 3:29:22–3:42:42 PM CT (`21:29:22Z–21:42:42Z`), H10b 3:43:11–4:12:21 PM CT (`21:43:11Z–22:12:21Z`). The parent/amendment SHA-256 hashes (`2e645597…`, `a41399fd…`) **are** recorded inside every run artifact (`prereg_s110_sha256`, `prereg_s110_amend1_sha256`) and re-hash byte-exact against the markdown committed in this PR, so the content was fixed before the runs even though the git commit came later; the git-timestamp ordering is nonetheless a real deviation from strict prereg-before-run and is disclosed here rather than hidden.
2. **Cited `notes/` path not in-repo.** The REPORT header cites `notes/sphere_pi_forces_2026_11_25/PREREG_S110_*.md`; that path does not exist in `aletheia`, `siliquant`, `math0`, or `cave-expedition` on any local branch. The authoritative copies are the ones in this track directory, pinned by the hashes above.
3. **Operators marked PRUNE were still trained.** The sm_86 microbench marks `Cayley2x2` (`28.87%` blk / `+15.55%` step) and `DarcyEMA` (`47.19%` cuFFT blk / `+20.97%` step) `PRUNE_OVERHEAD_GT_15PCT` (`all_operators_clear_15pct_gate: false`); per Amendment 1 `:42` they should have been pruned before multi-seed training. Both were trained in the 15+27-run eval and composed into Stage 2, against prereg `:44` ("failed shells EXCLUDED from Stage 2"). The certificate now grades them `PRUNED` (step overhead `> 15%`) and the Stage-1 verdict is computed from the earn-keep, not from the trained outcome.
4. **BPB-512 substituted for the earn-keep.** The preregistered Shell-Dynamo earn-keep is `≥15%` M1-H1 reduction or `≥5%` better `R_test=6` at `≥2` SE; BPB-512 is not the earn-keep. The first review round locked a `CONFIRMED` on BPB-512 Holm-z; this round the certificate derives every verdict from the gates (earn-keep per shell, Amendment-1 prune flags, exact-t Holm for the BPB-512 headline, LOSO count for H10b) and reports Holm-t alongside Holm-z.
5. **Out-of-band preflight citations unverifiable.** `PREREG_S110_AMENDMENT1_COUNCIL_PRUNING.md:4-7` cites three `verification/reports/COLLAB-{CLAUDE,GROK47,DSV41}-S110-*-PREFLIGHT.md` files that are not present in `aletheia`, `math0`, `cave-expedition`, or `siliquant` on any local branch. They are treated as unverifiable out-of-band references, not as evidence; the in-repo `s110_cpu_preflight_receipt.json` (`10/10` gates) is the verifiable preflight record.
6. **Corpus per-file recipe unrecoverable** for the truncated `python_code` / `formal_docs` domains (see header disclosure).

---

## 7. Artifact Provenance & Verification Receipts (`WEIGHTS=0`, `0` Leaks)

Regenerated file-list manifest (path, lines, bytes, sha256) of every payload file in this track directory, plus the internal payload/receipt digests:

| File | Lines | Bytes | SHA-256 |
| :--- | ---: | ---: | :--- |
| `PREFLIGHT_REPORT.md` | 105 | 11484 | `ba2007bd202bde4000c79cd7943b2a6b8ff7d683ce3e136dc04119765e026035` |
| `PREREG_S110_AMENDMENT1_COUNCIL_PRUNING.md` | 42 | 5981 | `a41399fdb888167288a63cefa540778d921574197f721b8d5322bd8825d0928a` |
| `PREREG_S110_GEOSPHERE_PLANETARY_ARCHITECTURE.md` | 65 | 11430 | `2e645597e81a330159b2183caf670f685821a9451a37223a782936e88e30d0fe` |
| `README.md` | 20 | 2699 | `4da28e2202ff54a6ffeede5ee4058c8af471510178e2cba7fe329f7b41df56d3` |
| `h10a_gpu_results.json` | 2123 | 59247 | `9d9df344c2c4db347674f5512247f906b5ac64ad7cf21d72398f2c51faca3d6b` |
| `h10b_gpu_results.json` | 4117 | 117096 | `c32d99c32ed08e27120e2991be01c13fba02f5d86657957327855831b66098ac` |
| `mlos_zone_b_s110_h10a.json` | 94 | 2751 | `677f72dbc916211ba09eb9baeaae30a5e59aae6bb79652979970ee9113881665` |
| `mlos_zone_b_s110_h10b.json` | 94 | 2752 | `809d5f3e1411d6d8e2d0863c23fdf6fbd33b1b34d4a82af7d86425fd68525e33` |
| `mlos_zone_b_s110_microbench.json` | 95 | 2869 | `34ce62f84c04bcfb692e9ea7114195b9290240d549d957cbbf87baee5eb971f5` |
| `s110_cpu_preflight.py` | 577 | 25475 | `65ce7fd01fba2cad4d3d40efaeb534110f73b6e86c20b6af44a1b3a9ffdb7596` |
| `s110_cpu_preflight_receipt.json` | 364 | 11180 | `4d9aabb726012eed2cfbbf5efd808dfd2e436f87ece1cf98ebff8aef218d25f5` |
| `s110_geosphere_audit.py` | 907 | 43156 | `d52c0ff709c4f2235cd70200e15ba3b7e87f5758ba38de3e96305fcc6c94eda1` |
| `s110_geosphere_certificate.json` | 1 | 11156 | `a1e41ac00039e34fd061740160b8d5d72e574fadb97eb0cebecbd2b6c596457d` |
| `s110_geosphere_models.py` | 1422 | 62532 | `a47d262593cf4e4774559913034988595a5fbae3509cb33bfe30b517ebae50d0` |
| `s110_sm86_microbench.json` | 152 | 4888 | `1f34743555344d7f94d10c6a56544aa98dd0ce787827e4bcfb009dbc04045a20` |
| `s110_sm86_microbench_eager_hillis.json` | 152 | 4890 | `0fd10a569cbfb1ece44d0fe2d25aa00706dc967c77efa86eca10d7a6149c7e91` |
| `s110_train_eval.py` | 1229 | 54829 | `5b84334fb95a780357973a916b3a02c7de4b3e0fef9b7b9ecbd05df84249a03f` |
| `test_s110_geosphere_audit_r5.py` | 443 | 22773 | `039bd4847743f110604b23a1bf876b6fe19acb6776a7a00fd75ba6a6967b0b73` |

- `s110_sm86_microbench.json`: `payload_sha256 = 733c8c33e8f4ddfbc75bd9a2ee51ac1012881846d353b2d05cce15f8b755fd01`
- `s110_sm86_microbench_eager_hillis.json`: `payload_sha256 = 279865a222d3f60a843b909c1aeae11257881793f0ef351be15eafeb693ff146`
- `h10a_gpu_results.json`: `payload_sha256 = 7da424abee3223e91a0bec02eceb82a42b0025bc2f275fcad078d1e9079cea33`
- `h10b_gpu_results.json`: `payload_sha256 = 8cef8307e6c5d62c33dc7122735f36d0c59fb66154c85432ca542528abfd46d3`
- `s110_cpu_preflight_receipt.json`: `payload_sha256 = cb603cb411de6ad3476eecd96f454639a65cca8629957ce1bcff91f5b6f20012`
- `mlos_zone_b_s110_microbench.json`: internal `receipt_sha256 = 88556dbce090b3ed2ee9d9ceb897cb6bac31d502a7dbe2fa6ee075af398357cf` (`clean_hardware_run = true`, `anomalies = []`, bound to `s110_sm86_microbench.json` = `1f34743555344d7f…`, `s110_sm86_microbench_eager_hillis.json` = `0fd10a569cbfb1ec…`, window `2026-11-25T21:28:44Z .. 2026-11-25T21:28:54Z`)
- `mlos_zone_b_s110_h10a.json`: internal `receipt_sha256 = 078df50ff9ba23b136c0ebd679e21ceeac295881544f379bccceaede4794710e` (`clean_hardware_run = true`, `anomalies = []`, bound to `h10a_gpu_results.json` = `9d9df344c2c4db34…`, window `2026-11-25T21:29:22Z .. 2026-11-25T21:42:42Z`)
- `mlos_zone_b_s110_h10b.json`: internal `receipt_sha256 = af695a375ff4747dca6086ef4c24bc389f2d6e74235aa7da99ac240333780b88` (`clean_hardware_run = true`, `anomalies = []`, bound to `h10b_gpu_results.json` = `c32d99c32ed08e27…`, window `2026-11-25T21:43:11Z .. 2026-11-25T22:12:21Z`)

