# Track S106 GPU Evaluation Report: `PREREG-SPHERE-PI-FORCES-V1` (Phase 1B Pilot Lock + Phase 2 Blind Held-Out RTX 3080 Gauntlet)

- **Parent Preregistration SHA-256:** `ac3e62116bc4841320d2c713787c23568beed1ae738bf9b284b7f0c2a118d72a` (`PREREG_SPHERE_PI_FORCES_V1.md` — file NOT shipped in any reachable repo, so the "locked before execution" claim is UNVERIFIABLE; verifier reports `prereg_status=UNVERIFIABLE_NOT_SHIPPED` and cross-checks the SHA constant against both shipped JSONs)
- **Epistemic Class:** `[anchor]` (live bare-metal NVIDIA GeForce RTX 3080 Laptop `8 GiB` measurements serialized via `flock` + `mlos gpu-lease --mode train` + `mlos stamp-run --zone B`, `HF_HUB_OFFLINE=1`, `WEIGHTS=0`, `0` GitHub pushes)
- **Strict Anti-Snooping Proof:** Phase 1B pilot parameters locked strictly on synthetic $N(0,1)$ + `Qwen/Qwen2.5-0.5B` at `2026-11-25T11:04:41Z` (`held_out_models_touched=[]`), strictly prior to Phase 2 blind gauntlet execution (`2026-11-25T12:23:51Z` -> `2026-11-25T13:26:25Z`, `clean_hardware_run=true`, `anomalies=[]`, `56°C -> 66°C`, `thermal_throttled=false`, `compute_vram_mib: 0 -> 0`).
- **Global Bit-Level & Algebraic Integrity (`117/117` blind full-model arms across `4.40B` block weights):** `total_syndrome_errors=0`, `total_oob_groups=0`, `total_non_block_diffs=0`, `100%` `CS-08` exact bitrate accounting (all FP16 row/col scales, global RMS, and codebook bytes included in `exact_bpw`).

---

## 1. Executive Summary & Honest Preregistered Verdicts

> [!IMPORTANT]
> **Grading correction (post-run, before any external audit):** the runner's embedded grader (`preregistered_verdicts` inside the immutable results JSON) was more lenient than the LOCKED kill-gate text for `H2a`, `H3b` and `H3c`. The authoritative column below is the **literal locked kill-gate re-grade** computed by `verify_s106_gpu_eval.py::_strict_kill_gate_verdicts`; raw results are untouched.

| Hypothesis | Runner Grader | **Strict Locked Kill-Gate Verdict** | Exact Blind Held-Out Evidence (`SmolLM2-360M` / `Qwen2.5-1.5B` / `Qwen2.5-3B`) |
| :--- | :---: | :---: | :--- |
| **`H1`** | `FALSIFIED` | **`FALSIFIED`** | Best static `SphereMap` lattice arm loses to `siliquant` per-128 `A_16` at `3.0 bpw` on `3/3` models (WikiKL `1.014`/`0.567`/`15.735` vs `0.437`/`0.311`/`0.518`) despite higher static weight SNR on `2/3` (`16.498`/`16.457` vs `16.434 dB`). `H1-P2` Spearman $\rho$ (`-0.435`/`+0.332`/`-0.164`) never reaches `0.60`. |
| **`H2a`** | `PARTIAL` | **`FALSIFIED`** | Kill gate fires: at `2.0 bpw` `EQ(S^3)` loses end-to-end KL to `Cart-LM + SphereMap` on `3/3` models. Sub-claims that DID hold (logged, not upgraded): `+2.206/+2.204/+2.195 dB` SNR over Numerator-$\pi$ grid at `2.5 bpw`; `+0.027/+0.028/+0.031 dB` over 20-iter trained k-means with `0` codebook bytes; GPU decode `1.355×` vs a **reference re-implementation** of `A_16` hampack bit-unpacking, not siliquant's kernel (`2.529` vs `1.866 Gw/s`). |
| **`H3a`** | `PARTIAL` | **`PARTIAL`** | `Power-0.7` + 0-bit shell LUT: typical-layer SNR `+0.247/+0.248/+0.247 dB` (`3/3` ≥ `+0.15`), KL ≥ `3%` @ ≥ `2 SE` on `2/3` (`SmolLM2` `E_8`: `-19.4%` Wiki / `-31.9%` Py; `Qwen1.5B` `E_8`: `-8.2%`/`-13.5%`, `A_16`: `-14.8%`/`-10.8%`); heavy-layer gate missed (`+0.27/+0.37/+0.35 dB` < `+0.40`). Best of the SphereMap **lattice** arms on `3/3`, BUT plain `SphereMap + Cart-LM 3b` (`3.0141 bpw`, `+0.014 bpw` over) beats it on `2/3` models (avg KL `0.673`/`0.379` vs `1.164`/`0.464`; Qwen3B `18.78` vs `16.18`). |
| **`H3b`** | `PARTIAL` | **`FALSIFIED`** | Kill gate fires: no significant KL improvement on `Qwen1.5B` (`-4.5%`/`-2.9%` degradations) or `Qwen3B` (`A_16` `+0.07%`, `E_8` degraded). Only `SmolLM2` `A_16` improves (`-11.96%` Wiki / `-13.03%` Py per `s106_blind_gauntlet_results.json`). |
| **`H3c`** | `PARTIAL` | **`FALSIFIED`** | Kill gate fires: Yukawa trails k-means in KL on `SmolLM2` and `Qwen1.5B`. Sub-claim that held: SNR `≥ +0.075 dB` over BOTH gravity-only and Coulomb on `3/3`; KL win on `Qwen3B` only (`-17.0%`/`-22.4%`). |
| **`H4`** | `FALSIFIED` | **`FALSIFIED`** | Conjunction `h4_sp_A16_128_hodge_3b` is beaten by `sp_E8_pow07_3b` and by per-128 `A_16` on `3/3` models. |

**Net scientific reading:** on blind held-out models, weight-space hypersphere/force operators did not beat the existing `siliquant` per-128 block-scaled `A_16` baseline at matched `3.0 bpw` on any model. The durable positive findings are narrow: a zero-bit `Power-0.7` radial warp that helps lattice quantizers on `2/3` models, and a LUT-free `EQ(S^3)` codebook that matches trained k-means in SNR and decodes faster than hampack. The dominant failure mechanism (§2) is extreme per-column scale spread, which is exactly what `H5a` targets.

---

## 2. Root-Cause Physical Diagnosis of `Qwen/Qwen2.5-3B` Static `SphereMap` Catastrophe

*Numbers in this section are console observations not serialized in the shipped JSONs (only the aggregate `kurtosis_summary` is); the per-matrix `rt_err`/`dc`/`dr` values below require the Qwen2.5-3B weights and the GPU evaluator (not shipped), so they are report-only.*

On `Qwen/Qwen2.5-3B`, every static `SphereMap` arm exploded to `WikiKL = 15.6..21.4` (`PPL > 5×10^7`) even at `4.5 bpw`, whereas `p128_A16_3b` remained clean (`WikiKL = 0.518`, `PPL = 16.27`) and **Adversarial Null Shuffle (`null_shuffle_sp_A16_3b`) cut KL nearly `4×` (`19.08 -> 4.94`)**! Exact layerwise round-trip inspection (`rt_err = 3.57e-13`, confirming zero FP16 bug!) isolated the exact culprit to a single layer:
- **`model.layers.1.mlp.gate_proj.weight`:** raw kurtosis `25.9 -> 3.06`, `dr ∈ [8.57e-5, 9.94e-2]` (`1,160×` row spread), and **`dc ∈ [1.19e-2, 4.43e+1]` (`3,722×` column spread, `dc_max = 44.3`!)**.
- Static Sinkhorn divides column $j^*$ by `44.3`, mixes all 64 columns with `H_64`, injects uniform whitened quantization error, and multiplies that cross-column error back by **`44.3` (`1,962×` squared error amplification at Layer 1)**!
- This establishes a sharp Law-5 obstruction for un-weighted static `SphereMap` on extreme-col-norm layers and directly motivates Amendment 1 (`H5a`: zero-extra-bit data-flow proper-time `Flow-SphereMap` $W D_{\text{flow}}^{\text{noise}}$) and Amendment 2 (`H6`).

---

## 3. Blind Held-Out Results Across All 3 Models (`117` Arms, `0` Syndrome / `0` OOB / `0` Non-Block Errors)

### HuggingFaceTB/SmolLM2-360M (BF16 Base: Wiki PPL `16.3948`, Py PPL `5.0450`, GPU `6.26 mJ/tok`; `32L`, `224` mats, `314,572,800` wts)

| Arm | Exact `bpw` | SNR (dB) | Heavy $\kappa>10$ SNR | Wiki KL ± SE | Wiki PPL | Python KL ± SE |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `p128_A16_2b` | `1.9999` | `10.118` | `10.23` | `4.33387 ± 0.03794` | `1422.259` | `5.84479 ± 0.04877` |
| `p128_A16_3b` | `2.9990` | `16.434` | `16.46` | `0.43727 ± 0.00927` | `25.075` | `0.37812 ± 0.00836` |
| `p128_A16_45b` | `4.4997` | `25.553` | `25.55` | `0.06962 ± 0.00525` | `17.596` | `0.05807 ± 0.00475` |
| `p128_E8_3b` | `2.9971` | `16.451` | `16.46` | `0.61125 ± 0.01403` | `29.636` | `0.58843 ± 0.01442` |
| `p32_A16_3b` | `2.9995` | `15.904` | `15.93` | `0.54467 ± 0.01028` | `28.265` | `0.45527 ± 0.00923` |
| `sp_CartLM_2b` | `2.0276` | `9.271` | `9.27` | `5.80233 ± 0.04676` | `5873.875` | `7.99546 ± 0.05355` |
| `sp_CartLM_3b` | `3.0276` | `14.569` | `14.54` | `0.67512 ± 0.01249` | `32.918` | `0.67139 ± 0.01323` |
| `sp_E8_lin_2b` | `2.0021` | `10.033` | `9.99` | `5.70187 ± 0.04323` | `4883.681` | `8.02059 ± 0.05358` |
| `sp_E8_lin_3b` | `2.9927` | `15.385` | `15.29` | `1.25032 ± 0.01860` | `58.907` | `1.94008 ± 0.02771` |
| `sp_E8_pow07_3b` | `2.9927` | `15.632` | `15.56` | `1.00760 ± 0.01616` | `46.060` | `1.32103 ± 0.01993` |
| `sp_E8_hodge_3b` | `2.9927` | `15.314` | `15.22` | `1.25659 ± 0.01761` | `58.511` | `3.08353 ± 0.03384` |
| `sp_A16_lin_3b` | `2.9955` | `15.728` | `15.60` | `1.46433 ± 0.02058` | `72.321` | `2.36876 ± 0.03185` |
| `sp_A16_pow07_3b` | `2.9955` | `15.965` | `15.86` | `1.32027 ± 0.01899` | `64.408` | `2.01535 ± 0.02839` |
| `sp_A16_hodge_3b` | `2.9955` | `15.754` | `15.63` | `1.28918 ± 0.01884` | `61.203` | `2.06013 ± 0.02857` |
| `h4_sp_A16_pow07_hodge_3b` | `2.9955` | `16.008` | `15.91` | `1.16679 ± 0.01815` | `56.179` | `1.78574 ± 0.02744` |
| `sp_A16_128_2b` | `1.9939` | `10.778` | `10.74` | `6.83810 ± 0.04759` | `16729.732` | `6.88794 ± 0.05162` |
| `sp_A16_128_3b` | `2.9970` | `16.498` | `16.37` | `1.01412 ± 0.01568` | `47.021` | `1.46620 ± 0.02443` |
| `sp_A16_128_B368_290b` | `2.9017` | `15.948` | `15.84` | `1.14099 ± 0.01754` | `52.563` | `1.34234 ± 0.02186` |
| `h4_sp_A16_128_hodge_3b` | `2.9970` | `16.486` | `16.36` | `1.06129 ± 0.01619` | `48.641` | `1.49746 ± 0.02500` |
| `sp_A16_128_45b` | `4.4974` | `24.819` | `24.29` | `0.32990 ± 0.00756` | `23.019` | `0.32743 ± 0.00836` |
| `null_shuffle_sp_A16_3b` | `2.9955` | `15.700` | `14.70` | `2.96842 ± 0.03227` | `325.486` | `4.59366 ± 0.04722` |
| `sp_s3_numpi_2b` | `2.0276` | `7.176` | `7.14` | `11.20535 ± 0.04744` | `1439965.598` | `11.58012 ± 0.05656` |
| `sp_s3_eq_leo_2b` | `2.0276` | `8.030` | `7.97` | `8.66126 ± 0.05297` | `96516.900` | `11.26617 ± 0.05796` |
| `sp_s3_kmeans_2b` | `2.0277` | `8.021` | `7.96` | `9.46627 ± 0.04947` | `209991.615` | `11.38166 ± 0.05871` |
| `sp_s7_eq4096_2b` | `2.0276` | `6.648` | `6.66` | `9.77034 ± 0.05956` | `356741.104` | `11.29298 ± 0.06904` |
| `sp_s3_numpi_25b` | `2.5276` | `10.235` | `10.23` | `4.03902 ± 0.03374` | `958.676` | `4.98179 ± 0.03911` |
| `sp_s3_eq_leo_25b` | `2.5276` | `12.441` | `12.42` | `2.19734 ± 0.02675` | `152.167` | `2.57954 ± 0.03286` |
| `sp_s3_kmeans_25b` | `2.5277` | `12.414` | `12.39` | `2.03269 ± 0.02324` | `130.330` | `3.38884 ± 0.03680` |
| `sp_s3_coulomb_25b` | `2.5277` | `12.439` | `12.42` | `1.83740 ± 0.02239` | `106.017` | `2.63357 ± 0.03559` |
| `sp_s3_yukawa_25b` | `2.5277` | `12.515` | `12.50` | `1.81886 ± 0.02279` | `102.179` | `3.93543 ± 0.04253` |

- **Kurtosis Collapse:** median `4.23 -> 3.000`, max `129.79 -> 3.78` (`6` mats with $\kappa > 10$).
- **`H1-P2` Per-Layer Spearman (`32` layers):** $\rho(\overline{\kappa}_{\text{post}}-3, \mathrm{KL}) = -0.4350$ (`p=1.284e-02`), $\rho(\max\kappa_{\text{post}}-3, \mathrm{KL}) = -0.5341$ (`p=1.641e-03`).

### Qwen/Qwen2.5-1.5B (BF16 Base: Wiki PPL `12.6180`, Py PPL `3.7395`, GPU `17.28 mJ/tok`; `28L`, `196` mats, `1,310,195,712` wts)

| Arm | Exact `bpw` | SNR (dB) | Heavy $\kappa>10$ SNR | Wiki KL ± SE | Wiki PPL | Python KL ± SE |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `p128_A16_2b` | `1.9999` | `10.117` | `10.12` | `2.30490 ± 0.02499` | `109.963` | `2.27274 ± 0.02866` |
| `p128_A16_3b` | `2.9990` | `16.434` | `16.43` | `0.31135 ± 0.00744` | `16.859` | `0.21872 ± 0.00760` |
| `p128_A16_45b` | `4.4997` | `25.553` | `25.56` | `0.04986 ± 0.00406` | `13.017` | `0.03132 ± 0.00317` |
| `p128_E8_3b` | `2.9971` | `16.451` | `16.45` | `0.32463 ± 0.00984` | `16.195` | `0.22860 ± 0.00912` |
| `p32_A16_3b` | `2.9995` | `15.904` | `15.91` | `0.35646 ± 0.00961` | `16.816` | `0.22570 ± 0.00747` |
| `sp_CartLM_2b` | `2.0141` | `9.271` | `8.96` | `3.41743 ± 0.03155` | `328.516` | `3.38017 ± 0.03694` |
| `sp_CartLM_3b` | `3.0141` | `14.569` | `14.03` | `0.43629 ± 0.01055` | `18.654` | `0.32161 ± 0.00924` |
| `sp_E8_lin_2b` | `1.9886` | `10.030` | `9.60` | `3.73039 ± 0.03566` | `479.985` | `3.32811 ± 0.03713` |
| `sp_E8_lin_3b` | `2.9792` | `15.378` | `14.44` | `0.58884 ± 0.01244` | `20.983` | `0.44879 ± 0.01175` |
| `sp_E8_pow07_3b` | `2.9792` | `15.627` | `14.81` | `0.54041 ± 0.01164` | `20.242` | `0.38805 ± 0.01057` |
| `sp_E8_hodge_3b` | `2.9792` | `15.308` | `14.38` | `0.60583 ± 0.01272` | `21.279` | `0.45946 ± 0.01200` |
| `sp_A16_lin_3b` | `2.9820` | `15.721` | `14.71` | `0.74824 ± 0.01459` | `24.266` | `0.58349 ± 0.01379` |
| `sp_A16_pow07_3b` | `2.9820` | `15.959` | `14.93` | `0.63717 ± 0.01349` | `21.924` | `0.52020 ± 0.01369` |
| `sp_A16_hodge_3b` | `2.9820` | `15.747` | `14.73` | `0.78193 ± 0.01587` | `24.624` | `0.55670 ± 0.01386` |
| `h4_sp_A16_pow07_hodge_3b` | `2.9820` | `16.002` | `14.98` | `0.66321 ± 0.01442` | `22.464` | `0.54361 ± 0.01398` |
| `sp_A16_128_2b` | `1.9804` | `10.761` | `10.16` | `2.18601 ± 0.02647` | `97.114` | `2.04898 ± 0.02956` |
| `sp_A16_128_3b` | `2.9835` | `16.457` | `15.11` | `0.56729 ± 0.01355` | `20.877` | `0.44499 ± 0.01329` |
| `sp_A16_128_B368_290b` | `2.8881` | `15.910` | `14.67` | `0.57778 ± 0.01259` | `21.393` | `0.44305 ± 0.01205` |
| `h4_sp_A16_128_hodge_3b` | `2.9835` | `16.445` | `15.10` | `0.57537 ± 0.01364` | `21.416` | `0.43516 ± 0.01299` |
| `sp_A16_128_45b` | `4.4839` | `24.711` | `21.71` | `0.22333 ± 0.00716` | `15.054` | `0.15088 ± 0.00637` |
| `null_shuffle_sp_A16_3b` | `2.9820` | `15.690` | `14.37` | `0.59500 ± 0.01233` | `20.766` | `0.41665 ± 0.01151` |
| `sp_s3_numpi_2b` | `2.0141` | `7.171` | `6.77` | `9.10569 ± 0.05398` | `103810.410` | `9.64618 ± 0.06511` |
| `sp_s3_eq_leo_2b` | `2.0141` | `8.023` | `7.52` | `6.39351 ± 0.04286` | `7034.912` | `7.25071 ± 0.05002` |
| `sp_s3_kmeans_2b` | `2.0141` | `8.014` | `7.52` | `6.64270 ± 0.04561` | `8821.785` | `8.25799 ± 0.05674` |
| `sp_s7_eq4096_2b` | `2.0141` | `6.649` | `6.56` | `8.03695 ± 0.05223` | `34860.570` | `8.79135 ± 0.06372` |
| `sp_s3_numpi_25b` | `2.5141` | `10.236` | `10.00` | `1.72125 ± 0.02294` | `62.467` | `1.45683 ± 0.02341` |
| `sp_s3_eq_leo_25b` | `2.5141` | `12.440` | `12.06` | `0.79917 ± 0.01548` | `25.726` | `0.70059 ± 0.01515` |
| `sp_s3_kmeans_25b` | `2.5141` | `12.412` | `12.03` | `0.82371 ± 0.01512` | `26.664` | `0.73621 ± 0.01666` |
| `sp_s3_coulomb_25b` | `2.5141` | `12.438` | `12.06` | `0.83227 ± 0.01552` | `26.151` | `0.69740 ± 0.01537` |
| `sp_s3_yukawa_25b` | `2.5141` | `12.513` | `12.13` | `0.88103 ± 0.01548` | `28.182` | `0.73983 ± 0.01692` |

- **Kurtosis Collapse:** median `4.35 -> 3.003`, max `158.68 -> 4.33` (`3` mats with $\kappa > 10$).
- **`H1-P2` Per-Layer Spearman (`28` layers):** $\rho(\overline{\kappa}_{\text{post}}-3, \mathrm{KL}) = +0.3317$ (`p=8.465e-02`), $\rho(\max\kappa_{\text{post}}-3, \mathrm{KL}) = +0.3290$ (`p=8.741e-02`).

### Qwen/Qwen2.5-3B (BF16 Base: Wiki PPL `10.9702`, Py PPL `3.1119`, GPU `21.39 mJ/tok`; `36L`, `252` mats, `2,774,532,096` wts)

| Arm | Exact `bpw` | SNR (dB) | Heavy $\kappa>10$ SNR | Wiki KL ± SE | Wiki PPL | Python KL ± SE |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `p128_A16_2b` | `1.9999` | `10.130` | `10.44` | `6.85713 ± 0.04987` | `8187.614` | `8.63340 ± 0.05871` |
| `p128_A16_3b` | `2.9990` | `16.437` | `16.50` | `0.51768 ± 0.01359` | `16.298` | `0.71552 ± 0.02141` |
| `p128_A16_45b` | `4.4997` | `25.553` | `25.55` | `0.04652 ± 0.00251` | `11.249` | `0.03856 ± 0.00243` |
| `p128_E8_3b` | `2.9971` | `16.456` | `16.59` | `2.55715 ± 0.03363` | `123.100` | `1.69185 ± 0.03169` |
| `p32_A16_3b` | `2.9995` | `15.907` | `15.98` | `0.80709 ± 0.01807` | `20.413` | `0.63352 ± 0.02121` |
| `sp_CartLM_2b` | `2.0108` | `8.891` | `3.55` | `14.53873 ± 0.04058` | `20980560.914` | `15.90023 ± 0.04460` |
| `sp_CartLM_3b` | `3.0108` | `14.162` | `8.64` | `18.13324 ± 0.04364` | `699652785.850` | `19.42991 ± 0.04090` |
| `sp_E8_lin_2b` | `1.9852` | `9.669` | `4.52` | `19.64778 ± 0.04644` | `3042218376.075` | `20.61591 ± 0.04374` |
| `sp_E8_lin_3b` | `2.9759` | `14.985` | `9.47` | `15.73533 ± 0.03756` | `62626976.781` | `17.41704 ± 0.03491` |
| `sp_E8_pow07_3b` | `2.9759` | `15.236` | `9.82` | `15.56357 ± 0.03906` | `52594727.095` | `16.78826 ± 0.03723` |
| `sp_E8_hodge_3b` | `2.9759` | `14.917` | `9.46` | `16.69662 ± 0.04083` | `176341910.950` | `18.18058 ± 0.03808` |
| `sp_A16_lin_3b` | `2.9787` | `15.330` | `9.83` | `19.08496 ± 0.04938` | `1871657522.365` | `20.07373 ± 0.04590` |
| `sp_A16_pow07_3b` | `2.9787` | `15.566` | `10.04` | `20.65363 ± 0.05707` | `8941614170.727` | `22.17529 ± 0.06004` |
| `sp_A16_hodge_3b` | `2.9787` | `15.361` | `9.90` | `19.07183 ± 0.04195` | `1805535688.231` | `20.02589 ± 0.04082` |
| `h4_sp_A16_pow07_hodge_3b` | `2.9787` | `15.613` | `10.14` | `19.73518 ± 0.05271` | `3569811714.625` | `21.02612 ± 0.05379` |
| `sp_A16_128_2b` | `1.9770` | `10.370` | `4.99` | `16.80520 ± 0.03933` | `176971602.397` | `18.23186 ± 0.03962` |
| `sp_A16_128_3b` | `2.9802` | `16.059` | `10.56` | `19.82913 ± 0.04924` | `3974004186.403` | `21.38017 ± 0.05362` |
| `sp_A16_128_B368_290b` | `2.8848` | `15.515` | `10.08` | `17.83550 ± 0.04404` | `514805529.692` | `18.95226 ± 0.04415` |
| `h4_sp_A16_128_hodge_3b` | `2.9802` | `16.052` | `10.57` | `19.46274 ± 0.04854` | `2771926222.854` | `20.67632 ± 0.05094` |
| `sp_A16_128_45b` | `4.4806` | `24.344` | `19.06` | `18.02597 ± 0.04599` | `639113051.182` | `19.42454 ± 0.04310` |
| `null_shuffle_sp_A16_3b` | `2.9787` | `15.679` | `14.11` | `4.94172 ± 0.04318` | `1231.227` | `5.47080 ± 0.05080` |
| `sp_s3_numpi_2b` | `2.0108` | `6.831` | `1.89` | `16.22595 ± 0.03832` | `106579918.152` | `16.80714 ± 0.04621` |
| `sp_s3_eq_leo_2b` | `2.0108` | `7.674` | `2.62` | `19.40027 ± 0.06154` | `2654859370.132` | `20.93992 ± 0.07060` |
| `sp_s3_kmeans_2b` | `2.0108` | `7.665` | `2.61` | `19.73297 ± 0.05738` | `3420704731.615` | `21.74568 ± 0.06563` |
| `sp_s7_eq4096_2b` | `2.0108` | `6.303` | `1.31` | `22.02646 ± 0.06706` | `36324156966.827` | `22.88347 ± 0.06345` |
| `sp_s3_numpi_25b` | `2.5108` | `9.846` | `4.53` | `17.41785 ± 0.04371` | `333795211.853` | `17.64044 ± 0.04797` |
| `sp_s3_eq_leo_25b` | `2.5108` | `12.041` | `6.55` | `16.31060 ± 0.04034` | `121900905.491` | `18.12073 ± 0.04228` |
| `sp_s3_kmeans_25b` | `2.5108` | `12.009` | `6.52` | `19.63364 ± 0.04834` | `2977842435.284` | `21.28405 ± 0.05347` |
| `sp_s3_coulomb_25b` | `2.5108` | `12.034` | `6.50` | `20.99021 ± 0.05831` | `12209236006.643` | `21.95875 ± 0.05623` |
| `sp_s3_yukawa_25b` | `2.5108` | `12.113` | `6.70` | `16.28893 ± 0.04624` | `117672653.193` | `17.03039 ± 0.04524` |

- **Kurtosis Collapse:** median `4.15 -> 3.005`, max `49.07 -> 4.07` (`6` mats with $\kappa > 10$).
- **`H1-P2` Per-Layer Spearman (`36` layers):** $\rho(\overline{\kappa}_{\text{post}}-3, \mathrm{KL}) = -0.1640$ (`p=3.392e-01`), $\rho(\max\kappa_{\text{post}}-3, \mathrm{KL}) = -0.0988$ (`p=5.663e-01`).

---

## 4. `H2a` Pack/Decode Throughput & Hardware Energy Telemetry

- **GPU (`16,777,216` weights on RTX 3080):** Closed-form LUT-free Hopf-Hex `EQ(S^3)` = **`2.5292 Gw/s`** vs. `A_16` `hampack`-style syndrome decode = **`1.8661 Gw/s`** (**`1.355×` faster**); L1-resident `1 KiB` `EQ(S^3)` table = **`36.7443 Gw/s`** (**`19.7×`**).
- **CPU (`4,194,304` weights on `i9-11900H`):** Closed-form `EQ(S^3)` = **`0.0452 Gw/s`** vs. `A_16` `hampack` = **`0.0407 Gw/s`** (**`1.111×`**); L1 table = **`0.4531 Gw/s`**.
- **Energy & Thermal Zone-B Envelope:** Full 62.5-min blind gauntlet (`3,754.8 s`, `152,632.3 J` CPU RAPL) stayed `56°C -> 66°C` with `0` thermal throttling; BF16 inference GPU energy = `6.26` (`SmolLM2-360M`), `17.28` (`Qwen2.5-1.5B`), `21.39 mJ/tok` (`Qwen2.5-3B`).

---

## 5. Frozen Artifact Manifest (`gpu_eval/` — `9` Sibling Files + `REPORT_GPU_EVAL.md` = `10` Files)

*Note: the Phase-2 numbers in §1–§4 were produced by the pre-edit `s106_phase2_blind_gauntlet.py` (`f066f28b…`, `54,421` B); the head version differs by a comment-only hampack-baseline label.*

| File | Lines | Bytes | Mode | SHA-256 (Full 64-Hex) | Role |
| :--- | ---: | ---: | :---: | :--- | :--- |
| `mlos_zone_b_gauntlet_receipt.json` | `92` | `2,718` | `0o644` (git 100644) | `e23145d05c4228932f50ac90a6211659db8f98dbbe0bf2eeeb8f31b2eba05c1c` | mlos Zone B gauntlet receipt (`clean_hardware_run=true`, re-signed with `bound_file_sha256`, `receipt=e8b001de...`)
| `mlos_zone_b_pilot_receipt.json` | `92` | `2,721` | `0o644` (git 100644) | `3403698ea134f04ff3bed51affd5ae98f3c493a9da5227a60df11d8156d8d53e` | mlos Zone B pilot receipt (`clean_hardware_run=true`, re-signed with `bound_file_sha256`, `receipt=f815393f...`)
| `s106_blind_gauntlet_results.json` | `1` | `85,198` | `0o644` (git 100644) | `ec49d4a76008e1ab968d68d7923e6e9ec7ddd2e18ae8b29917f43adc310a742b` | Canonical Phase 2 results receipt (`117/117` arms, `result_sha256=dab0b4fd...`)
| `s106_frozen_pilot_params.json` | `1` | `44,105` | `0o644` (git 100644) | `b075337a70367408f23f4be5188b1f0c2c73e2ce61dd11b6d94637857bb836ef` | Immutable Phase 1B locked constants (inner `pilot_params_sha256=26a40bee...`)
| `s106_phase1b_pilot_lock.py` | `523` | `22,329` | `0o644` (git 100644) | `137c6a72be373df3348d95d2c7b46746246ba2a377ff1278196cfcd03198065e` | Phase 1B parameter-lock runner (strictly synthetic Gaussian + Qwen/Qwen2.5-0.5B)
| `s106_phase2_blind_gauntlet.py` | `1,202` | `54,479` | `0o644` (git 100644) | `8c459a3cb95705f79024502417b19eceae256f005f685364d837d4605e3b78a8` | `8c459a3cb95705f79024502417b19eceae256f005f685364d837d4605e3b78a8` |
| `s106_quant_ops.py` | `816` | `33,725` | `0o644` (git 100644) | `9eebf4843f294f7dd279d45668ab58cb4759807362f1c726e5af9a1e74848144` | Exact-bpw GPU/CPU operator library (SphereMap, E8, A16, A16^8, Power-0.7, Hodge, EQ(S^3), EQ(S^7), Yukawa/Coulomb)
| `test_s106_gpu_eval_r5.py` | `232` | `12,032` | `0o644` (git 100644) | `9bf14438a53c652bb0c3a122e6ccc033f86516e8639cb4be665a1a52aebf7020` | `9bf14438a53c652bb0c3a122e6ccc033f86516e8639cb4be665a1a52aebf7020` |
| `verify_s106_gpu_eval.py` | `491` | `23,881` | `0o644` (git 100644) | `e52babd09766386305213f3e53d5bc5c24913d3ef0f055938dd6e8ec66979655` | `e52babd09766386305213f3e53d5bc5c24913d3ef0f055938dd6e8ec66979655` |
