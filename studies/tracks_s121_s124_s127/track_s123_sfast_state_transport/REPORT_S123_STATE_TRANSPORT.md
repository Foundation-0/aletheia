# Track S123 (`EXP-Q28a` + `EXP-Q30c` / `W14-OBS-1`): Cross-Model $O(1)$ `HoloSphere` `S_fast` Woodbury & Non-Abelian `CayleySU2` State Transport vs. $O(T)$ KV-Cache Translators

- **Track:** `track-s123-speculative-state-transport` (`EXP-Q28a` Wave-12 Portal 138 + `EXP-Q30c` Wave-14 Portal 148 Addendum)
- **Locked Preregistrations:** `PREREG-W12` (`notes/portals_wave12_2026_11_26/PREREG_WAVE12_FRONTIER_SYNTHESIS.md`) & `PREREG-W14` (`SHA-256 = 871900e5d6c860ac159f43ca6b4767e7c128d0b4f7748edf788d56e9cb535d3e`)
- **Novelty Classification (Law 4):** `N1` (exact pure-$\mathbb{Q}$ algebraic certification + matched 3-seed CPU cross-seed state-transport micro-benchmark contrasting $O(1)$ Woodbury/`CayleySU2` states against $O(T)$ KV translators; prior art explicitly credited below).
- **Execution Envelope:** Strictly CPU-only (`CUDA_VISIBLE_DEVICES=""`, `OPENBLAS_NUM_THREADS=1`), `0` floats in pure-$\mathbb{Q}$ oracle AST, `51/51 = 100.0%` `aletheia mutate`, `10/10 = 100.0%` AST `BoolOp` sweep, `3`-mode `-I` parity, dual `aletheia audit-check PASS`, `PYC=0, ELF=0, WEIGHTS=0`.

---

## 1. Own-Terms Steelman of Prior Art (Law 2b — `OWN_TERMS_FIRST`)

1. **`b10-tv/speculative-encoding @ 5b74ad4d14` (Wave-12 Portal 138, `Apache-2.0`, HF `RampPublic/speculative-encoding`):**
   - *Strengths on its own terms:* A single `9.79 GB` shared bottleneck translator (`5–7×` smaller `EncodedMemory` than raw per-layer hidden states) translates document states across **7 production LLMs in all 42 directed pairs** (`Qwen3-14B`, `Qwen3.5-9B`, `Llama-3.1-8B`, `Gemma-3/4-12B`, `Ministral-3-8B/14B`), serves directly into vLLM/HF, supports prefix concatenation (`prefix_ops`), and adds query-aware `KVzip` (`16×/64×/128×`) compression.
   - *Exact Structural Obstructions (`W12-OBS-1`):* Even at `128×` `KVzip`, transported cache size still scales linearly $O(T)$, requires storing a separate compressed cache **per question** ($O(M \cdot T / \rho)$ for $M$ queries over one document), requires RoPE key re-rotation on prefix concatenation, and is uncalibrated on non-prefill autoregressive decode states.
2. **`alesha-pro/vllm-cross-model-kv` (`Apache-2.0`, Wave-14 Portal 148, independent vLLM implementation of NVIDIA `arXiv:2608.03893`):**
   - *Strengths on its own terms:* Zero gradient training — fits closed-form ridge regression ($\lambda = 0.01$) across same-family models (`Qwen3-0.6B -> Qwen3-1.7B`) by stripping RoPE per token (`inv_RoPE(K) -> ridge(K, V) -> target_RoPE(K)`), reaching `K R² = 0.760`, `V R² = 0.625`, `0.940` HellaSwag retention, and **`2.22×` warm TTFT speedup at `32K`** (`1645 ms` vs `3657 ms`).
   - *Exact Structural Obstructions (`W14-OBS-1`):* Requires matched tokenizer and matched KV head geometry, still incurs $O(T)$ transport bytes and $O(T)$ per-token inverse/forward RoPE rotations, and relies critically on **Abelian $SO(2)^{d/2}$ scalar-phase commutativity** ($R(\tau \theta)^{-1}$ factors position cleanly out of every token independently).
3. **Hazy Research *Plato's Key* (Wave-11 Portal 129) & Wave-11 `Track S121` Live Probe (`W11-B`):**
   - Orthogonal Procrustes ($O(d) \times \mathbb{R}_+$) aligns entity-key subspaces across models; in our live Wave-11 `0.36B–1.5B` probe (`w11_live_loopcd_platosphere_results.json`), PCA rank-truncation (`r = 64/128`) jumped swap transfer `+28.57 pp` (`28.57% -> 57.14%`) on `Qwen2.5-1.5B -> Qwen2.5-0.5B` and `+7.14 pp` (`21.43% -> 28.57%` vs `0.0%` nulls) on `Qwen2.5-1.5B -> SmolLM2-360M` by excising the uncalibrated $N_{\mathrm{cal}} < d$ nullspace.

---

## 2. Part 1 — Pure-$\mathbb{Q}$ Certified Theorems (`verify_state_transport_geometry.py`, `0` Floats)

- **Certificate SHA-256 (`s123_state_transport_certificate.json`):** `00022833acb4cdee03074af058860ff02bdd133b8a7bb493eff1ac46707abdbf`
- **Mutation Hardening:** `51 / 51 = 100.0%` `aletheia mutate --max-mutants 0` + `10 / 10 = 100.0%` exhaustive AST `BoolOp` sweep (`0` float literals in AST).

| Theorem | Exact Pure-$\mathbb{Q}$ Statement & Certified Witness | Key Exact Rational Quantities |
| :--- | :--- | :--- |
| **`T1` ($O(T)$ KV vs. $O(1)$ `S_fast` Bandwidth)** | Compares BF16 KV cache $4 B L H d_h T / \rho$ against pure FP32 `S_fast` ($4 B L H d_h^2$) and full `HoloSphere-V3` `15M` `O(1)` state (`933,888 B = 57/64 MiB`, `B=2, L=6, H=16, d_h=32`). | At $T=8192$: KV = `201,326,592 B` (`192 MiB`), exact ratio = **`4096/19` (`215.58×`)**. Exact crossovers: $T^*_{\mathrm{pure}}(\rho) = \rho d_h$ (`32, 512, 2048, 4096`), $T^*_{\mathrm{full}}(\rho) = 38 \rho$ (`38, 608, 2432, 4864`). Even vs **`128× KVzip`**, `HoloSphere` is **`32/19` (`1.684×`)** smaller for 1 question and **`320/19` (`16.84×`)** smaller across `10` questions! |
| **`T2a` (Gauge-Invariant Woodbury Transport)** | Over independent rational orthogonal gauges $(Q_k, Q_v) \in O(4,\mathbb{Q})^2$ ($Q_k \neq Q_v$), right-acting associative Woodbury $S' = S(I - \beta k k^\top) + \beta v k^\top$ satisfies exact intertwining $S_B = Q_v S_A Q_k^\top$, exact readout equivariance $S_B(Q_k q) = Q_v(S_A q)$, and **bit-exact prefix handoff + native suffix continuation** (`0/1` error, zero RoPE re-rotation, zero $O(T^2)$ cross-token cost). | `right_woodbury_equivariance_err_sq = 0/1`, `prefix_handoff_suffix_err_sq = 0/1`, `readout_equivariance_err_sq = 0/1`. Contrast: left-acting $(I-\beta kk^\top)S + \beta v k^\top$ intertwines for shared $Q_v=Q_k$ (`0/1`) but **breaks** for distinct $Q_v \neq Q_k$ (`err_sq > 0`). |
| **`T2b` (`SU(2)` Intertwiner & `W14-OBS-1`)** | Proper rotation $R \in SO(3,\mathbb{Q})$ ($\det R = +1$) satisfies exact Cayley homomorphism $R(w_1 \oplus w_2) = (R w_1)\oplus(R w_2)$ & quaternion conjugation $u C(w) u^{-1} = C(R_u w)$. Improper reflection ($\det R = -1$) acts as a **group anti-homomorphism** reversing every word: $R(w_1 \oplus w_2) = (R w_2)\oplus(R w_1) \neq (R w_1)\oplus(R w_2)$! Kabsch $\det=+1$ column flip restores exact homomorphism. Simultaneously proves `W14-OBS-1`: Pythagorean $SO(2,\mathbb{Q})$ rotations $(3/5,4/5)$ & $(5/13,12/13)$ commute (`0/1`), whereas $SU(2)$ Cayley steps do not (`> 0`). | `su2_proper_det = 1/1` (`err_sq = 0/1`), `su2_improper_det = -1/1` (`order_reversal_exact = true`, `forward_err_sq > 0`), `su2_kabsch_repaired_homomorphism_exact = true`, `w14_obs1_abelian_so2_commutator_err_sq = 0/1`, `w14_obs1_nonabelian_su2_commutator_err_sq > 0`. |
| **`T3` (Query-Aware Low-Rank Projection & `2×` Nullspace Penalty)** | Using exact rational Hadamard projectors $P_r = \frac{1}{8} H_{8,:r}^\top H_{8,:r}$ ($r \in \{2,4,6,8\}$, $d=8$, $\sigma=1/2$), certifies exact Pythagorean decomposition $\|\hat{S} P_r - S^*\|_F^2 = \varepsilon_{\mathrm{tail}}^2 + \sigma^2 r$, net gain $\sigma^2(d-r) - \varepsilon_{\mathrm{tail}}^2$ (`r=2`: `2/1 -> 3/4`, net gain `5/4`), exact `0` query distortion on $\operatorname{col}(P_r)$, AND proves **exact `2/1` (`2×`) squared-error penalty** of uncalibrated orthogonal nullspace rotation $J$ ($\langle J z, z\rangle = 0 \implies \|Jz - z\|^2 = 2\|z\|^2$) vs zero/mean projection ($1\|z\|^2$). | `nullspace_penalty_ratio = 2/1`; `r2`: `err_full = 2/1`, `err_proj = 3/4`, `gain = 5/4`; `r4`: `err_proj = 1/1`; `r6`: `err_proj = 3/2`; `r8`: `err_proj = 2/1` (`beats_full = false`). |
| **`T4` (OLS Thin-Shell Shrinkage)** | Exact Cauchy–Schwarz certification over $\mathbb{Q}$ of $s_{\mathrm{OLS}}^2 \le s_{\mathrm{Frob}}^2$ with strict inequality under noisy alignment. | `s_ols = 2/1`, `s_ols_sq = 4/1 < 57/13 = s_frob_sq`, `shrinkage_ratio_sq = 52/57`. |

---

## 3. Part 2 — Deterministic 3-Seed CPU Cross-Seed State-Transport Micro-Benchmark (`bench_sfast_cross_seed_transport.py`)

- **Execution:** CPU-only (`CUDA_VISIBLE_DEVICES=""`, `OPENBLAS_NUM_THREADS=1`), `3` independent seeds `{42, 137, 2026}` (`6` ordered cross-seed pairs per experiment), canonical deterministic `payload_sha256 = ee7dedd07ac35265239495a1a0ba8d8f29012bb244178e1412217fc02f19183a` (`wall_seconds` excluded from digest -> `100%` bit-identical across repeated CPU runs!), `19/19 = 100.0%` `aletheia mutate`.
- **Pre-Declared Gate Verdict:** **`CONFIRMED`** (`3 / 3` independent empirical gates `PASS`: `S123-G1`, `S123-G2`, `S123-G3`; plus algebraic Cauchy-Schwarz sanity invariant `sanity_S123_cauchy_schwarz_ols_le_frob = true`).

### 3.1 Experiment 1 — Cross-Seed $O(1)$ `S_fast` Woodbury Associative Recall (`d_h = 32`, `N_keys = 12`, `T_doc = 8` w/ Overwrites)

| Transport Arm (Mean Across `6` Ordered Cross-Seed Pairs, `128` Test Docs/Pair) | Held-Out Test Acc | Notes |
| :--- | ---: | :--- |
| `Native_UpperBound` (Model B reads doc natively) | **`100.00%`** | `3/3` seeds converged (`1.000`) |
| `Raw_Unaligned_Control` (plug $S_A$ directly into Model B) | `8.47%` | Pure chance (`1/12 = 8.33%`), confirms distinct seed gauges |
| **`Bilinear_Frob_Procrustes`** ($\hat{S}_B = s_{\mathrm{Frob}} Q_v S_A Q_k^\top$) | **`100.00%`** | **`+91.53 pp`** vs unaligned; **`+92.58 pp`** vs Random-$O(d)$ (`G1 PASS`) |
| **`Bilinear_OLS_Procrustes`** ($\hat{S}_B = s_{\mathrm{OLS}} Q_v S_A Q_k^\top$) | **`100.00%`** | `s_ols < s_frob` on `6/6` pairs (`0.899–0.951` vs `0.973–1.028`, Cauchy-Schwarz sanity invariant) |
| **`Prefix_Handoff_Suffix_Continue`** (A reads `t=0..3` -> transport -> B continues `t=4..7`) | **`100.00%`** | Zero RoPE re-rotation, zero $O(T^2)$ cross-token recomputation |
| `Adversarial_Null_Random_Od` | `7.42%` | Chance |
| `Adversarial_Null_Shuffled_Doc` | `9.89%` | Chance |

- **Query-Aware SVD Rank Sweep (`r in {4, 8, 16, 32}`, Effective Trained Key/Val Rank = `12 < 16 < 32`):**
  - Clean `64`-doc calibration transport: `r=4` `78.13%` (`0.00234` MSE), `r=8` `94.14%` (`0.00142` MSE), **`r=16` `100.00%` (`0.00064` MSE, `2×` state compression with `0.0 pp` accuracy loss!)**, `r=32` `100.00%` (`0.00048` MSE).
  - Isotropic orthogonal perturbation ($\sigma = 0.35$): `r=32` (`0.122659` MSE, `59.25%`) -> **`r=16` (`0.061624` MSE = `-49.76%` / `1.9904×` state-MSE reduction, `0.0 pp` accuracy change at `59.25% == 59.25%` across `6/6` pairs because effective key rank `12 < 16 < 32` implies readout $S q$ already lies inside $\operatorname{col}(P_{16})$, `G2 PASS` on state-MSE denoising!)**, `r=8` (`0.031928` MSE, `48.96%`), `r=4` (`0.017553` MSE, `33.33%`).

### 3.2 Experiment 2 — Non-Abelian $A_5$ (`L = 16`, `60` Classes) `CayleySU2` Mid-Word Prefix Handoff (`t = 8`)

| Transport Arm (Mean Across `6` Ordered Cross-Seed Pairs, `200` Test Words/Pair) | Held-Out Test Acc | Drop vs `det=+1` |
| :--- | ---: | ---: |
| `Native_UpperBound` (Model B reads all `16` tokens) | **`100.00%`** | — |
| **`Kabsch_SO3_DetPlus1`** ($\det R = +1$, conjugation $\hat{U}_B = u_R U_A u_R^{-1}$) | **`100.00%`** | `0.00 pp` (`G3 PASS`) |
| **`Improper_O3_DetMinus1_Obstruction`** ($\det R = -1$, reflection) | **`32.00%`** (`64/200`) | **`-68.00 pp`** (exact `rev(P) == P` count in $A_5$!) |
| **`Abelian_Commutative_Sum_W14_OBS_1`** (RoPE-style path-free generator sum) | **`11.75%`** | **`-88.25 pp`** (proves Abelian strip fails on $SU(2)$!) |
| `Random_SO3_Null` | `6.50%` | `-93.50 pp` |
| `Shuffled_Word_Null` | `4.00%` | `-96.00 pp` |

---

## 4. Scope & Honest Limitations (Aletheia Law 4)

1. **Micro-Scale Cross-Seed vs. Heterogeneous Pretrained LLMs:** Part 2 validates cross-seed transport on controlled micro-cells (`d_h = 32` associative recall and 60-class $A_5$ `CayleySU2` cells where independent seeds are related by exact/near-exact orthogonal gauges). Translating states across heterogeneous multi-billion-parameter pretrained LLMs with different tokenizers and nonlinearly misaligned feature manifolds remains substantially harder (as observed in our Wave-11 `W11-B` live probe where `0.36B–1.5B` `Frob_Procrustes` reached `21.4%–37.5%`, `r=64` reached `28.6%–57.1%`, and dark-memory recovery remained `0%–0.85%` at $N_{\mathrm{train}} \le 61$).
2. **Optimizer Sensitivity on `L=16` $A_5$ BPTT:** During initial testing, a uniform `lr=0.05` caused `seed=2026`'s `gen_w` to diverge out of the `2I` acute basin (`1.5%` native accuracy); lowering the generator LR to `0.003` while keeping readout `lr=0.05` achieved `100.0%` native convergence on all `3/3` seeds (echoing a prior acute-basin finding).
3. **Exact Group-Theoretic Explanation of `Improper_O3_DetMinus1` (`64 / 200 = 32.00%` Across `6/6` Pairs):** The 4 generator axes $(\pm w_{g_0}, \pm w_{g_1})$ span a rank-2 mirror plane in $\mathbb{R}^3$ on which $R_{\mathrm{improp}}$ agrees with $R_{\mathrm{prop}}$ on every individual letter while flipping the orthogonal axis ($\det R_{\mathrm{improp}} = -1$). By Theorem `T2b`'s exact anti-homomorphism $R_{\mathrm{improp}}(a \oplus b) = (R_{\mathrm{improp}} b) \oplus (R_{\mathrm{improp}} a)$, improper transport conjugates the **reversed prefix** $\mathrm{rev}(P)$ rather than $P$. Direct enumeration (`count_a5_reversal_fixed_prefixes`) verifies that **exactly `64 / 200 = 32.00%`** of `seed=5005` test prefixes satisfy $\mathrm{rev}(P) = P$ in $A_5$, matching `Improper_O3_DetMinus1` survival (`64/200`) identically on all `6/6` pairs (`improper_survival_matches_rev_fixed_exact = true`)!

---

## 5. Artifact SHA-256 Manifest (`0644`, `PYC=0, ELF=0, WEIGHTS=0`)

| File | SHA-256 |
| :--- | :--- |
| `verify_state_transport_geometry.py` | `c551d3adee779c0d3fe9a91a8b2574291f10b4162f6a73f7b750469f46cfb7b7` |
| `test_state_transport_geometry_r5.py` | `30beb44ebcae42abd94c684c93b38ecb8ad5cd096e059f92d5b5545c7ae00a54` |
| `s123_state_transport_certificate.json` | `518a2e12f8a3a3092aaa07980dda4da76ac45a654e6ac273c2baff54aa86a7bd` |
| `bench_sfast_cross_seed_transport.py` | `6857c7c71db372638baebd95c9720b1c1c1e6fd787bd3b7c6caae7043af24088` |
| `test_bench_sfast_transport_r5.py` | `bf0d5da814d2a5e6addc50a31c922ca827ac9040535307344db5db2ecd4c13ab` |
| `s123_cross_seed_bench_results.json` | `4ffdc57453b262d5131cc8f99157f2cc6dc4c09000375f86de08be02e579e37f` |
