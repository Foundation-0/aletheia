# Track S114 (`HoloSphere` / `SiliSphere`) — Bare-Metal `sm_86` Fused `SU(2)` Holonomy-Scan & Kernel-Isomorphic Transformer Evaluation Report

- **Track:** `track-s114-silisphere-fused-kernel-transformer` (`EXP-Q18a..c`)
- **Preregistration Document:** `PREREG-S114-SILISPHERE-FUSED-ENTITY-V1` (`PREREG_S114_SILISPHERE_FUSED_ENTITY.md`, archived verbatim inside this track)
- **Immutable Preregistration SHA-256:** `5fa927a06933c3cff057b65f75c1d2f190e10f1e420303d582dfb7c802ee69a4`
- **Amendment 1 Document:** `PREREG-S114-AMENDMENT1-S107-S108-CONVERGENCE-V1` (`PREREG_S114_AMENDMENT1_S107_S108_CONVERGENCE.md`, SHA-256 `b661b54359dacd455813f4d83e6547e0a89036afb6d527566c2a97f905e89a12`) — **Status: locked & queued (`H14d`/`H14e` not yet executed in this report)**
- **Novelty Classification:** **`N1` (`n2_claims = 0`)** — zero-spill Ampere `sm_86` PTX/Triton co-fusion of established Lie-group/spherical primitives (`N0`), exact $\mathfrak{su}(2)$ additive-suffix-sum reverse-mode adjoint, zero-permute BHTD register-transposed layout, trig-free pure-rational `cayley_su2` + Beltrami `Cayley2x2` kernels, and preregistered Zone-B empirical evaluation.
- **Target Silicon:** NVIDIA GeForce RTX 3080 Laptop GPU (`GA104M`, CC `8.6`, `48` SMs, `100 KiB` shmem/SM, `4 MiB` L2, `8 GiB` GDDR6, `356.6 GB/s` empirical host STREAM Triad calibration outside this track, driver `615.78.08`, VBIOS `94.04.49.00.51`, PyTorch `2.15.0+cu132`, Triton `3.9.0`, `nvcc 13.4`), serialized under Ring-0 `mlos gpu-lease --mode train` + `mlos stamp-run --zone B --require-gpu`.
- **Execution Date (UTC):** `2026-11-25`

---

## Executive Summary & Locked Verdicts (`PREREG-S114`)

All three preregistered hypotheses (`H14a`, `H14b`, `H14c`) were executed end-to-end on bare-metal RTX 3080 (`sm_86`) under Zone-B hardware telemetry (`3/3` clean runs, `0` thermal throttles, `0` anomalies) and graded literally against the frozen kill gates in `PREREG-S114`:

| Hypothesis | Campaign | Runs / Kernels | Locked Verdict | Primary Empirical Outcome |
| :--- | :--- | :---: | :---: | :--- |
| **`H14a` (`EXP-Q18a`)** | `sm_86` CUDA/PTX + Triton Fused `SU(2)` Holonomy-Scan Parity, `0 B` Spill, & Speedup | **Locked V1:** `9/9` `0 B`-spill kernels (`cu=8c9c40ff...`); **Post-V1 V2:** `27/27` (`cu=15f9b3a2...`) | **`CONFIRMED`** (`4/4` locked V1 gates PASS) | **Locked V1:** `9/9` `0 B` spills; FP32 `max_abs <= 7.82e-6`, BF16 `max_abs <= 1.953e-3` (`max_rel <= 2.129e-3`), norm drift `1.8e-7`; `12L` step **`0.6765×`** `RoPE-2D-nGPT` (**`5.83×`** vs eager `H7b`); gated `C4` BHTD-with-permute speedup **`37.86×`** (`T=512`) & **`46.05×`** (`T=2048`) (ungated fiber-major diagnostic `146.99×`, `348.37 GB/s`). **Post-V1 V2 upgrade:** `27/27` `0 B` spills, **`0.6313×`** `RoPE-2D-nGPT` (**`6.35×`** vs eager), `124.41×` zero-permute direct-BF16. |
| **`H14b` (`EXP-Q18b`)** | Equal-Wall-Clock (`CS-08`) + Equal-Step `15M` LM Showdown & NVML `mJ/tok` | `21/21` (`7` arms × `3` seeds; `2` preregistered + `2` exploratory HoloSphere arms) | **`CONFIRMED`** (rests independently on preregistered **`HoloSphere-V2-SU2-Unlooped`** passing `C1/C2/C3`) | **Preregistered primary arm `HoloSphere-V2-SU2-Unlooped`:** `T=2048` **`2.6484 BPB`** (`-10.00%` vs `RoPE-2D-nGPT`, `p_t=0.00076`; `-18.98%` vs `RoPE-2D-Std`, `p_t=0.00090`), `T=512` `2.6545` (`-3.56%` vs `RoPE-2D-nGPT`, `p_t=0.00823`), inference `0.7632×`/`0.8318×` gross `mJ/tok` vs `RoPE-2D-nGPT`. **Exploratory `#1` at `T=2048` (`HoloSphere-V2-CayleySU2-Unlooped`, trig-free):** `T=2048` **`2.6098 BPB`** (`-11.31%` vs `RoPE-2D-nGPT`, `-20.16%` vs `RoPE-2D-Std`), `0.7986×`/`0.8427×` vs `RoPE-2D-nGPT`. **Baseline advantage:** `RoPE-2D-Std` leads in-distribution at `T=512` (`2.5846` mean across all `3` seeds) and inference energy (`0.4755 / 0.6102 mJ/tok`), but suffers `4×` blowup (`3.2687 BPB`). |
| **`H14c` (`EXP-Q18c`)** | Full Covariant $(Q,K,V)$ + $\overline{U_t} O_t$ on Non-Abelian $S_3$ / $A_5$ Word Tracking | `30/30` (`5` arms × `2` groups × `3` seeds) | **`FALSIFIED`** (`0/2` group gates PASS) | `Full-Covariant-QKV-Untransport` ranks `#1` on $S_3$ OOD at **`35.30%`** vs `RoPE-2D-nGPT` `19.48%` (`+15.81 pp, p_t=0.00943`) and `H7b-QK-Only` `31.06%` (`+4.24 pp, p_t=0.291`), missing the locked `>= 50.0%` floor and `>= +15.0 pp` margin vs `QK-Only`; $A_5$ OOD stays near `1.67%` chance (`2.42%–2.58%`), consistent with (though not directly ablated here) the softmax convex-hull closure obstruction. |

---

## Hardware Provenance & Ring-0 Zone-B Telemetry (`3/3` Clean Runs)

Every GPU campaign ran under `mlos gpu-lease --mode train` and `mlos stamp-run --zone B --require-gpu` with `HF_HUB_OFFLINE=1`, `PYTHONHASHSEED=0`, `TORCH_USE_DETERMINISTIC_ALGORITHMS=1`, and `CUBLAS_WORKSPACE_CONFIG=:4096:8`. All `3` Zone-B receipts verify `clean_hardware_run=true`, `anomalies=[]`, `exit_code=0`, `compute_vram_mib=0` before/after execution, `thermal_throttled=false`, and `slowdown_active=false`. Note that `mlos` `receipt_sha256` is an unkeyed SHA-256 self-hash (detecting accidental edits/truncation rather than adversarial forgery); receipts are cross-linked to result files via distinct `receipt_sha256` digests and verified UTC windows (`started_utc <= completed_utc <= ended_utc`).

| Campaign | Zone-B Receipt File | `receipt_sha256` (Prefix) | Result File (`inner result_sha256` Prefix) | Kernel `cu_sha256` (Bound `ptxas`) | UTC Window (`started` .. `ended`) | `duration_ms` | GPU Temp (`start -> end`) |
| :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| **`H14a` (V1 Locked)** | `mlos_zone_b_s114_h14a.json` | `27028a128811...` | `s114_h14a_gpu_results.json` (`5dcd7cf57405...`) | `8c9c40ff...` (`v1`, `9/9`) | `22:29:07Z .. 22:30:14Z` | `66,656.0` | `58°C -> 71°C` |
| **`V2` Foundry (Post-V1)** | `mlos_zone_b_s114_v2.json` | `c1c4361460d9...` | `s114_v2_gpu_results.json` (`bef753422238...`) | `15f9b3a2...` (`v2`, `27/27`) | `22:47:40Z .. 22:48:24Z` | `43,276.8` | `58°C -> 73°C` |
| **`H14b + H14c`** | `mlos_zone_b_s114_h14bc.json` | `0dec97fbdac8...` | `s114_h14bc_gpu_results.json` (`cf67c129fee1...`) | `15f9b3a2...` (`v2`, `27/27`) | `22:59:04Z .. 23:37:06Z` | `2,281,912.0` | `54°C -> 69°C` |

---

## 1. `H14a` (`EXP-Q18a`) Locked V1 & Post-V1 V2 Kernel Foundry Results — `CONFIRMED`

### 1.1 Compiler Zero-Spill & SASS Profiles (`ptxas` V1 `9/9` & V2 `27/27`)

Both the locked V1 compilation receipt and the post-V1 V2 compilation receipt are archived verbatim and verified independently:

- **Locked V1 Receipt (`ptxas_sm86_zero_spill_receipt_v1.json`, SHA-256 `5312211af68c402bb124e4badf8fcca7d0d2121820fe0537380e37cef239b695`, `cu_sha256 = 8c9c40ff9ef7afd6de3bea7ff30364723102555b2577032b6dba59785808aeb2`):** **`9/9` zero-spill kernels** (`0 B` stack frame, `0 B` spill stores, `0 B` spill loads across all `9` instantiations; SASS mix: `1,137` `FFMA`, `60` `LDG.E.128`, `20` `STG.E.128`, `37` `SHFL.UP`, `28` `SHFL.DOWN`, `45` `SHFL.BFLY`, `29` `MUFU.RSQ`, `6` `POPC`). This receipt backs `H14a` Gate `C1` directly.
- **Post-V1 V2 Receipt (`ptxas_sm86_zero_spill_receipt.json`, SHA-256 `749f9b4b959a1dd2a27d05931ed8e051df898b406e89e1a504c8206b59cd9c23`, `cu_sha256 = 15f9b3a2cd55752edc24e33664f8c6a3d60a8ade24036345ef7ebdc9def1f79f` matching archived `su2_holonomy_scan_sm86.cu`):** **`27/27` zero-spill kernels** (`20–61` regs/thread, `0 B` stack/spills; `su2_holonomy_scan_qkv_bhtd_fwd_sm86`: `38–40` regs + `2,176 B` shmem; `bwd`: `48–61` regs + `1,920 B` shmem; `holosphere_cayley2x2_fwd/bwd`: `22–31` regs; `holosphere_hopf_s3_cayley2x2_fwd/bwd`: `23–46` regs).
- **V2 Ampere `sm_86` SASS Mix:** `3,324` `FFMA`, `103` `LDG.E.128`, `63` `LDG.E.64`, `41` `STG.E.128`, `22` `STG.E.64`, `117` `SHFL.UP`, `88` `SHFL.DOWN`, `90` `SHFL.BFLY`, `28` `SHFL.IDX`, `81` `MUFU.RSQ`, `179` `MUFU.RCP`, and `6` `POPC`. Note: rational division (`1/(1 + ||w||^2)`) and reciprocal square root lower to Ampere SFU `MUFU.RCP`/`MUFU.RSQ` instructions; `cayley_su2` is therefore **trig-free** (zero `MUFU.SIN`/`MUFU.COS` transcendental calls), not SFU-free.

### 1.2 Numerical Parity & Algebraic Invariants (`Gate C2`: PASS)

| Suite | Coverage | Worst FP32 `max_abs` (`<= 1e-4`) | Worst BF16 `max_abs` (`<= 5e-3`) | Worst Unit-Norm Drift (`<= 1e-5`) | Extra Invariant |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **`H14a` V1 Locked (`CUDA` + `Triton`)** | `10` lengths `T ∈ {32,33,64,100,128,256,512,513,1024,2048}`, `untransport`, `4` spherical steps | `7.82e-6` | `1.953e-3`\* | `1.8e-7` | `A_16` `0/4,096` valid errors; `17/17` injected 1-bit errors caught (`max_abs=2.4e-7`); `0` NaN/Inf |
| **`V2` Post-V1 (Zero-Permute + Cayley)** | `20` `(T, d_head, layout, map_mode, dtype)` rows + `cayley2x2` + `hopf_s3_cayley2x2` + `slerp_hopf` | `5.87e-6` | `1.953e-3` | `1.8e-7` | Live GPU Beltrami `[C, K] = 0` moments `m0..m4` max drift **`1.192e-7`** (`<= 1e-6`); `0` NaN/Inf |

*\*Note on V1 BF16 summary field:* The producer summary `s114_h14a_gpu_results.json::parity.summary.worst_bf16_err = 2.129e-3` (`0.00212936`) pooled a `max_rel` entry (`slerp.d_alpha.max_rel`); pure recomputed `max_abs` across all V1 BF16 tensors is **`1.95324e-3`**. Both sit well below the locked `5.0e-3` ceiling.

### 1.3 Kernel Microbenchmarks (`B=8, H=8, d_head=64`, `Gate C4`: PASS)

Locked `H14a` Gate `C4` (`>= 5.0×` at `T=512` and `T=2048`) is graded on the end-to-end **`BHTD` with permute** wrapper (`37.86×` at `T=512`, `46.05×` at `T=2048`). Comparing against the ungated native fiber-major diagnostic exposed a **`68.7%–69.8%`** `.permute().contiguous()` layout tax, motivating the post-V1 V2 zero-permute `32×32` register-transposed kernels (`su2_holonomy_scan_qkv_bhtd_{fwd,bwd}_sm86`), direct-BF16 I/O, and trig-free rational `cayley_su2`:

| Seq Len `T` | Eager `H7b` Fwd+Bwd | V1 CUDA `BHTD` (Gated `C4`) | V1 CUDA Fiber-Major (Diagnostic, `% Triad` Fwd) | V2 Zero-Permute FP32 (`% Triad` Fwd) | V2 Zero-Permute Direct-BF16 | V2 `cayley_su2` Direct-BF16 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`512`** | `46.486 ms` | `1.228 ms` (**`37.86×`**) | `0.371 ms` (`125.40×`, `90.47%`) | `0.771 ms` (`60.04×`, `77.33%`) | `0.473 ms` (`97.86×`) | `0.478 ms` (`96.81×`) |
| **`1024`** | `99.214 ms` | `2.441 ms` (`40.64×`) | `0.744 ms` (`133.27×`, `91.73%`) | `1.541 ms` (`64.12×`, `80.54%`) | `0.892 ms` (`110.80×`) | `0.925 ms` (`106.87×`) |
| **`2048`** | `210.727 ms` | `4.576 ms` (**`46.05×`**) | `1.434 ms` (`146.99×`, `97.69%` = `348.37 GB/s`) | `2.891 ms` (`72.85×`, `92.37%` = `329.40 GB/s`) | `1.693 ms` (`124.41×`) | `1.790 ms` (`117.65×`) |

- **Post-V1 V2 `Cayley2x2` & `Hopf-S^3 + Cayley2x2` Microbenchmark (`B=8, T=512, d=384, BF16`):**
  - `Cayley2x2`: `1.7613 ms` eager -> **`0.1802 ms`** fused `sm_86` (**`9.77×`** speedup).
  - `Hopf-S^3 + Cayley2x2`: `6.4676 ms` eager -> **`0.2263 ms`** fused `sm_86` (**`28.58×`** speedup).

### 1.4 End-to-End `12L` (`d=320, H=8, B=8, T=512, BF16`) Training Step (`Gate C3`: PASS)

Both locked V1 and post-V1 V2 pass the locked `<= 1.15×` `RoPE-2D-nGPT` ceiling and `>= 3.40×` eager-`H7b` speedup floor:

| Run | Model Arm | Params | Median Step (ms) | `tok/s` | vs `RoPE-2D-nGPT` | vs Eager `H7b` | Peak VRAM (MiB) | Train `mJ/tok` |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **V1 Locked** | `RoPE-2D-nGPT` | `14,983,937` | `115.396` | `35,495` | `1.0000×` | `3.9446×` | `2,094.46` | `1.9984` |
| **V1 Locked** | `Eager H7b` (`s107_models.py`) | `14,982,017` | `455.195` | `8,998` | `3.9446×` | `1.0000×` | `3,816.49` | `10.3420` |
| **V1 Locked** | **`HoloSphere-CUDA-sm86`** | `14,982,017` | **`78.068`** | `52,467` | **`0.6765×`** | **`5.8308×`** | `1,904.03` | `1.6461` |
| **V1 Locked** | `HoloSphere-Triton-3.9` | `14,982,017` | `107.844` | `37,981` | `0.9346×` | `4.2209×` | `1,930.80` | `2.2968` |
| **V2 Post-V1** | `RoPE-2D-nGPT` | `14,983,937` | `113.364` | `36,131` | `1.0000×` | `4.0088×` | `2,094.46` | `2.3879` |
| **V2 Post-V1** | `Eager H7b` | `14,982,017` | `454.454` | `9,013` | `4.0088×` | `1.0000×` | `3,816.49` | `10.3324` |
| **V2 Post-V1** | **`HoloSphere-V2-sm86`** | `14,979,137` | **`71.568`** | **`57,232`** | **`0.6313×`** | **`6.3500×`** | **`1,814.32`** | **`1.4308`** |
| **V2 Post-V1** | **`HoloSphere-V2-CayleySU2`** | `14,979,137` | `72.192` | `56,738` | `0.6368×` | `6.2951×` | `1,814.32` | `1.5159` |
| **V2 Post-V1** | `HoloSphere-V2 + Cayley2x2 (Fused)` | `15,073,217` | `75.133` | `54,517` | `0.6628×` (`+4.98%` vs V2) | `6.0487×` | `1,887.84` | `1.5791` |
| **V2 Post-V1** | `HoloSphere-V2 + Cayley2x2 (Eager)` | `15,073,217` | `90.424` | `45,298` | `0.7976×` (`+26.35%` vs V2) | `5.0258×` | `2,168.40` | `1.9766` |

V1 single-block scaling (`B=8, H=8, d_head=64`, `T ∈ {512, 1024, 2048}`) remains constant at **`0.6812× / 0.6960× / 0.6819×`** of `RoPE-2D-nGPT` (**`5.95× / 6.27× / 6.63×`** vs eager `H7b`).

---

## 2. `H14b` (`EXP-Q18b`) Equal-Wall-Clock (`CS-08`) & Equal-Step Showdown — `CONFIRMED`

### 2.1 Protocol & Offline SHA-Disjoint Corpus

- **Runs:** `21/21` (`7` arms × `3` seeds `{42, 137, 2026}`), rotated arm execution order per seed to cancel thermal drift, matched non-embedding parameters across every seed (`14,876,480–14,924,549`, max delta `0.18% <= 0.5%`).
- **Offline Multi-Domain Byte-Level UTF-8 Corpus:** `train_sha256 = 505a4b675c297306d315a984a7b86913fa56c3e897940c62f5a71b1b879d9931` (`2,570,357` bytes); disjoint `eval_sha256 = 522a66e9d61918401c10aef0f8619038a75b5cdb4802a391e3d71be03e28132c` (`wikitext2_test`: `1,290,546 B`, `python_code`: `250,282 B`, `json_traces`: `121,766 B`). Exact FP32 log-softmax BPB at `T=512` (`32,768` scored tokens) and `4×` extrapolation `T=2048` (`8,192` tail-512 scored tokens).
- **Equal-Wall-Clock (`CS-08`) Budget:** Anchored per seed to `600` steps of `RoPE-2D-nGPT` (`67.092 s` / `67.213 s` / `66.070 s`; max single-step boundary overshoot `+0.115 s`). Synchronized NVML inference power measured with idle baseline `P_idle = 20.01 W` (both gross and idle-subtracted `mJ/tok` logged).

### 2.2 Seven-Arm Mean Performance & Energy Table (`3`-Seed Mean)

| Arm (Lock Status) | Non-Emb Params | Eq-Step (`600`) `T512` | Eq-Step (`600`) `T2048` | Eq-WC Steps | Eq-WC `T512` BPB | Eq-WC `T2048` BPB | Inf `T512` Gross/Net `mJ/tok` | Inf `T2048` Gross/Net `mJ/tok` | Peak VRAM (MiB) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`HoloSphere-V2-SU2-Unlooped`** *(Preregistered)* | `14,895,937` | `2.7794` | `2.7560` | `886.3` | `2.6545` | `2.6484` | `0.5478 / 0.4322` | `0.6701 / 0.5273` | `1,991.4` |
| `HoloSphere-V2-Full-Entity` *(Preregistered, `r=3`+MTP8)* | `14,924,549` | **`2.6629`** | **`2.6321`** | `519.3` | `2.7282` | `2.6963` | `0.9384 / 0.7582` | `1.0936 / 0.8770` | `3,284.4` |
| **`HoloSphere-V2-CayleySU2-Unlooped`** *(Exploratory)* | `14,895,937` | `2.7544` | `2.7328` | `887.0` | `2.6203` | **`2.6098`** | `0.5733 / 0.4562` | `0.6789 / 0.5361` | `1,994.2` |
| `HoloSphere-V2-Stage1a-Cayley2x2` *(Exploratory)* | `14,897,665` | `2.7607` | `2.7250` | `848.3` | `2.6495` | `2.6245` | `0.5714 / 0.4512` | `0.6897 / 0.5396` | `2,056.4` |
| `RoPE-2D-nGPT` *(Preregistered Anchor Baseline)* | `14,897,857` | `2.7525` | `2.9428` | `600.0` | `2.7525` | `2.9428` | `0.7178 / 0.5596` | `0.8056 / 0.6235` | `1,867.6` |
| `RoPE-2D-nGPT+MarkovMTP8` *(Exploratory MTP Control)* | `14,889,061` | `2.7289` | `2.9656` | `572.0` | `2.7388` | `2.9623` | `0.7413 / 0.5824` | `0.8448 / 0.6618` | `1,921.3` |
| `RoPE-2D-Std` *(Preregistered Pre-Norm Baseline)* | `14,876,480` | `2.8102` | `3.2210` | `1,173.0` | **`2.5846`** | `3.2687` | **`0.4755 / 0.3831`** | **`0.6102 / 0.4867`** | `1,250.3` |

### 2.3 Paired Statistical Tests & Literal `PREREG-S114` Gate Grading

| `HoloSphere-V2` Arm (Status) | Eq-WC `T2048` vs `RoPE-2D-nGPT` (`t`, `p_t(df=2)`) | Eq-WC `T2048` vs `RoPE-2D-Std` (`t`, `p_t(df=2)`) | Eq-WC `T512` vs `RoPE-2D-nGPT` (`t`, `p_t(df=2)`) | Eq-Step `T2048` vs `RoPE-2D-nGPT` (`t`, `p_t(df=2)`) | Inf `mJ/tok` Ratio vs `RoPE-2D-nGPT` (`T512` / `T2048`) | `C1 / C2 / C3` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`SU2-Unlooped`** *(Preregistered)* | **`-10.00%`** (`-36.22`, `0.00076`) | **`-18.98%`** (`-33.25`, `0.00090`) | **`-3.56%`** (`-10.96`, `0.00823`) | `-6.35%` (`-60.28`, `0.00028`) | **`0.7632×` / `0.8318×`** | **`PASS / PASS / PASS`** |
| `Full-Entity` *(Preregistered)* | `-8.38%` (`-16.42`, `0.00369`) | `-17.51%` (`-27.67`, `0.00130`) | `-0.88%` (`-5.54`, `0.03102`) | **`-10.56%`** (`-23.43`, `0.00182`) | `1.3073×` / `1.3576×` | `PASS / PASS / FAIL` |
| **`CayleySU2-Unlooped`** *(Exploratory)* | **`-11.31%`** (`-15.43`, `0.00418`) | **`-20.16%`** (`-15.55`, `0.00411`) | **`-4.80%`** (`-20.92`, `0.00228`) | `-7.14%` (`-21.59`, `0.00214`) | **`0.7986×` / `0.8427×`** | **`PASS / PASS / PASS`** |
| **`Stage1a-Cayley2x2`** *(Exploratory)* | **`-10.81%`** (`-25.38`, `0.00155`) | **`-19.71%`** (`-18.36`, `0.00295`) | **`-3.74%`** (`-10.24`, `0.00940`) | `-7.40%` (`-112.23`, `0.00008`) | **`0.7960×` / `0.8561×`** | **`PASS / PASS / PASS`** |

### 2.4 Key Empirical Findings from `H14b`

1. **Preregistered Verdict Independence & Attribution:** **`H14b = CONFIRMED` rests cleanly on the preregistered arm `HoloSphere-V2-SU2-Unlooped` alone** (`C1/C2/C3 = PASS/PASS/PASS`), independent of the exploratory arms. The `RoPE-2D-nGPT+MarkovMTP8` control (`572` eq-WC steps, `T=2048 = 2.9623` vs `2.9428`, `+0.66%`) rules out MTP-8 attribution. The equal-wall-clock gains are **consistent with combined architectural `SU(2)` holonomy gains** (`-6.35%` to `-7.14%` at equal `600` steps) **and higher step throughput enabled by fused kernel execution** (`848–887` vs `600` equal-wall-clock steps).
2. **Exploratory Trig-Free `CayleySU2` Leads at `T=2048`, While `RoPE-2D-Std` Leads at `T=512` & Energy:** Replacing transcendental `exp(omega)` (`sincosf`) with the trig-free rational Cayley map $\delta u = (1 - \|\omega\|^2, 2\omega)/(1 + \|\omega\|^2)$ achieves the **lowest equal-wall-clock BPB at `T=2048` (`2.6098` mean across all `3` seeds; `-11.31%` vs `RoPE-2D-nGPT`, `-20.16%` vs `RoPE-2D-Std`)**, while beating `RoPE-2D-nGPT` at `T=512` (`2.6203` vs `2.7525`, `-4.80%`; `Stage1a` edges `CayleySU2` on seed `42` at `2.6279` vs `2.6295`) and cutting `T=512` inference energy by `20.1%` relative to `RoPE-2D-nGPT`. Crucially, however, **`RoPE-2D-Std`** (`1,173` equal-wall-clock steps) achieves the **lowest in-distribution `T=512` BPB across all `7` arms (`2.5846` mean, beating every HoloSphere arm on all `3` seeds)** and the **lowest absolute inference energy (`0.4755 mJ/tok` at `T=512`, `0.6102 mJ/tok` at `T=2048` — `CayleySU2` uses `1.21×` / `1.11×` of `RoPE-2D-Std`)**, at the expense of severe `4×` length-extrapolation collapse (`3.2687 BPB`).
3. **Looped Fixed-Depth `R_test` Behavior (`Full-Entity`):** `HoloSphere-V2-Full-Entity` ranks `#1` at **equal step** (`2.6321` vs `2.9428`, `-10.56%`, `p_t=0.00182`), passes `C1` & `C2` at equal wall-clock (`-8.38%`), and fails `C3` (`1.3073×/1.3576×` `mJ/tok`) due to its `3×` loop + MTP-8 head. Training strictly at fixed `r_train=3` causes cumulative drift when extrapolated (`R3=3.156, R4=3.491, R6=6.719, R8=13.914` mean BPB), motivating variable-depth training (`r ∈ {1..4}`) + decaying angles in follow-up work.
4. **External Candidate Checkpoint Provenance (`WEIGHTS=0` in Repo):** The single best equal-wall-clock `T=2048` checkpoint (`HoloSphere-V2-CayleySU2-Unlooped`, seed `42`, Eq-WC `T=2048 = 2.569676 BPB`) was exported strictly outside the repository (`holosphere_v2_15m_best.pt`, `59,967,263 B`, SHA-256 `3194cea40c305b47fcf539f58822b3a669c27965f287c1d45429fd960e29adb8`).

---

## 3. `H14c` (`EXP-Q18c`) Non-Abelian $S_3$ / $A_5$ State Tracking — `FALSIFIED`

### 3.1 Five-Arm × Two-Group Results (`30/30` Runs, `6L, d=256, H=8`, `1200` Steps, `3` Seeds)

All `5` arms share matched non-embedding parameters across every seed (`4,753,380–4,765,956`, max delta `0.26% <= 0.5%`), the `3`-stage curriculum (`L ∈ [4..24] -> [4..48] -> [4..64]` train, `L ∈ [65..192]` OOD), unit `sqk=1.0`, `angle_scale=pi`, and a shared phase-insensitive quadratic quaternion readout invariant to the $\pm q$ double cover of $2D_3$ and $2I$:

| Arm (Lock Status) | $S_3$ ID (`L=4..64`) | $S_3$ OOD (`L=65..192`) | $S_3$ OOD Final | $A_5$ ID (`L=4..64`) | $A_5$ OOD (`L=65..192`) | $A_5$ OOD Final |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`HoloSphere-V2-Full-Covariant-QKV-Untransport`** *(Preregistered)* | **`47.88%`** | **`35.30%`** | **`26.69%`** | `4.64%` | **`2.58%`** | **`2.21%`** |
| `HoloSphere-V2-QKV-NoUntransport` *(Exploratory Ablation)* | `46.09%` | `33.49%` | `19.01%` | `4.73%` | `2.48%` | `1.82%` |
| `Abelian-SO2-Phase` *(Exploratory Control)* | `44.79%` | `31.91%` | `22.14%` | `4.61%` | `2.52%` | `2.08%` |
| `H7b-QK-Only` *(Preregistered Ablation)* | `39.82%` | `31.06%` | `23.05%` | `4.79%` | `2.55%` | `1.43%` |
| `RoPE-2D-nGPT` *(Preregistered Control)* | `27.52%` | `19.48%` | `16.41%` | `4.85%` | `2.42%` | `1.56%` |

### 3.2 Literal Kill-Gate Grading & Mechanistic Interpretation

- **$S_3$ Gate (FAIL):** `Full-Covariant-QKV-Untransport` beats `RoPE-2D-nGPT` by **`+15.81 pp`** (`t=+10.22, p_t=0.00943`), and ranks `#1` across all `5` arms, but misses the locked `>= 50.0%` OOD accuracy floor (`35.30%`) and the `>= +15.0 pp` margin over `H7b-QK-Only` (`+4.24 pp, t=+1.42, p_t=0.291`). Furthermore, `Abelian-SO2-Phase` (`31.91%`) is statistically indistinguishable from `Full-Covariant-QKV-Untransport` (`+3.38 pp, t=+0.88, p_t=0.474`).
- **$A_5$ Gate (FAIL):** All `5` arms remain near `1/60 = 1.67%` chance (`2.42%–2.58%` OOD), missing the `>= 15.0%` floor and `+8.0 pp` margin (`+0.17 pp` vs `RoPE`, `+0.04 pp` vs `H7b-QK-Only`).
- **Locked Verdict:** **`FALSIFIED`** (`0/2` group criteria pass).
- **Mechanistic Interpretation (Untested Hypothesis):** These failures are **consistent with (though not directly ablated here)** a softmax convex-hull closure obstruction: parallel transport $\overline{U_t} U_s V_s$ acts orthogonally on each fiber, but non-negative softmax averaging $\sum_s \alpha_{ts} (\overline{U_t} U_s V_s)$ projects into the convex hull of $S^3$ rather than closing under group multiplication, suggesting a hard/top-1 or dedicated multiplicative group-state recurrence outside softmax attention may be required.

---

## 4. Explicit Deviations, PREREG Arm Mapping, & Post-V1 Upgrades

No locked threshold, seed set (`{42, 137, 2026}`), or kill gate in `PREREG-S114` was relaxed or altered. Every post-preregistration addition and file-provenance detail is disclosed transparently:

1. **PREREG-to-Run Arm Mapping & Unlocked Exploratory Expansion:**
   - `PREREG-S114` locked **two** `H14b` candidate arms (`SiliSphere-Fused-Unlooped` -> executed as **`HoloSphere-V2-SU2-Unlooped`**; `SiliSphere-Fused-Entity` -> executed as **`HoloSphere-V2-Full-Entity`**) and **three** `H14c` arms (`RoPE-2D-nGPT`, `SU2-QK-Only-nGPT` -> **`H7b-QK-Only`**, `SU2-Covariant-QKV-nGPT` -> **`HoloSphere-V2-Full-Covariant-QKV-Untransport`**).
   - The additional `H14b` arms (**`HoloSphere-V2-CayleySU2-Unlooped`**, **`HoloSphere-V2-Stage1a-Cayley2x2`**, **`RoPE-2D-nGPT+MarkovMTP8`**) and `H14c` ablations (**`Abelian-SO2-Phase`**, **`HoloSphere-V2-QKV-NoUntransport`**), plus the shared quadratic quaternion readout and `sqk=1.0`, `angle_scale=pi` settings in `H14c`, were **added post-V1/V2 and were NOT locked in `PREREG-S114` or Amendment 1**; they are explicitly labeled **exploratory**.
   - **Verdict Integrity:** Because `H14b` requires `>= 1` passing arm, adding exploratory arms could otherwise inflate pass probability. Here, **`H14b = CONFIRMED` holds strictly on the preregistered arm `HoloSphere-V2-SU2-Unlooped` alone** (`C1/C2/C3 = PASS/PASS/PASS`), which `s114_holosphere_audit.py` verifies independently (`preregistered_arms_verdict == "CONFIRMED"`).
2. **Post-V1 V2 Kernel Expansion (`9 -> 27` `0 B`-Spill Kernels) & Script Provenance:**
   - `H14a` ran on V1 (`cu_sha256 = 8c9c40ff...`, `ptxas_sm86_zero_spill_receipt_v1.json`, `9/9` zero-spill kernels). After V1 exposed the `68.7%–69.8%` `.permute().contiguous()` layout bottleneck, `su2_holonomy_scan_sm86.cu` (`cu_sha256 = 15f9b3a2...`, `ptxas_sm86_zero_spill_receipt.json`, `27/27` zero-spill kernels) and supporting scripts (`s114_fused_ops.py`, `su2_holonomy_triton.py`, `s114_h14a_gpu_bench.py`) were expanded post-V1 (`22:45–22:47Z`, after the `22:30Z` V1 `H14a` run) to add zero-permute `BHTD` scans, direct-BF16 I/O, trig-free `cayley_su2`, and fused `Cayley2x2` / `Hopf-S^3+Cayley2x2`.
   - `su2_holonomy_scan_sm86.cu` (`15f9b3a2...`) is archived verbatim as compiled and executed (retaining internal track comments and the imprecise `"SFU-free"` comment on line 961) so its `cu_sha256` matches `ptxas_sm86_zero_spill_receipt.json`, `s114_v2_gpu_results.json`, and `s114_h14bc_gpu_results.json` bit-for-bit.
3. **Statistical & Thermal Additions:** Added rotated per-seed arm ordering, exact two-sided Student-`t(df=2)` p-values alongside paired `z/t`, both gross and idle-subtracted (`P_idle=20.01 W`) NVML `mJ/tok`, and fixed-depth `R_test ∈ {3, 4, 6, 8}` probing on `HoloSphere-V2-Full-Entity`.

---

## 5. Scope, Limitations, & Amendment 1 Status

- **Hardware & Scale Scope:** All results were measured on a single consumer laptop GPU (`GA104M` RTX 3080 Laptop `8 GiB`), at `15M` parameters (`H14b`) and `4.8M` parameters (`H14c`), on a `2.57 MB` byte-level UTF-8 corpus over `n=3` seeds (`df=2` paired Student-`t` tests). Extrapolation to multi-GPU server silicon, larger model scales, or subword tokenizers is not claimed.
- **Host STREAM Triad Reference:** The `356.6 GB/s` empirical `GA104M` GDDR6 STREAM Triad denominator cited in `s114_h14a_gpu_results.json` and `s114_v2_gpu_results.json` comes from an external host calibration outside this track directory; raw kernel `GB/s` values (`348.37 GB/s` V1 fiber-major, `329.40 GB/s` V2 zero-permute) are computed directly from tensor byte traffic and CUDA event elapsed milliseconds.
- **Amendment 1 (`PREREG_S114_AMENDMENT1_S107_S108_CONVERGENCE.md`, `b661b543...`):** Locks follow-up probes `H14d` (antipodal safe-Hopf loop clocks + equatorial foliation) and `H14e` (holonomy-smoothed chunking + coupled `Markov-MTP8`); **status = queued / not yet executed in this report**.

---

## 6. Reproducibility, Pure-Stdlib Audit, & Artifact Hygiene

- **Pure-Stdlib Fail-Closed Audit & Certificate:** `s114_holosphere_audit.py` (zero `torch`/`numpy` imports, zero bare asserts, zero hardcoded verdicts, `allow_nan=False`, strict `int`/not-`bool` checks, symlink & JSON-size guards) fails closed if `PREREG_S114_SILISPHERE_FUSED_ENTITY.md` (`5fa927a0...`) or `PREREG_S114_AMENDMENT1_S107_S108_CONVERGENCE.md` (`b661b543...`) is absent or altered; verifies both V1 (`9/9`, `8c9c40ff...`) and V2 (`27/27`, `15f9b3a2...`) `ptxas` receipts bound to `h14a` and `v2`/`h14bc` respectively; recomputes all `H14a`/`V2`/`H14b`/`H14c` paired statistics, per-seed parameter parity, equal-wall-clock budget adherence, preregistered-only vs all-arm `H14b` verdicts, and `H14c` verdicts from raw JSON arrays; verifies inner `result_sha256` digests and all `3` Zone-B `receipt_sha256` unkeyed integrity hashes + UTC windows; enforces `WEIGHTS=0`/`ELF=0`; and emits canonical `s114_holosphere_certificate.json` (`prereg_verified=true`).
- **Verification Gates:** Stock Python `3`-mode isolated `-I` parity (`-I -B`, `-I -O -B`, `-I -B -W error`), pure-stdlib R5 test suite (`test_s114_holosphere_audit_r5.py`) + `aletheia mutate --guards require_ok --max-mutants 0 --add-cwd`, and dual `aletheia audit-check --strict-ancestors --safety-scan --strict-unseeded` (run via `publish/aletheia-fix-lean-gates-v2` and `publish/aletheia-fast-mutate`; `bare_assert=0, leak=0, WEIGHTS=0, ELF=0, PYC=0`).
