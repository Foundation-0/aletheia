# `PREREG-S110` + `AMENDMENT1` — CPU-Only Pre-Flight & RTX 3080 Harness Report ("Geosphere-Net")

- **Track Directory:** `track-s110-geosphere-net-gpu/` (`EXP-Q11a..b`: Pruned 4-Operator "Geosphere-Net"; separate from frozen Lean 4.36.0 `track-s110-geosphere-weft-conservation/`)
- **Locked Preregistration Sources:**
  - `notes/sphere_pi_forces_2026_11_25/PREREG_S110_GEOSPHERE_PLANETARY_ARCHITECTURE.md` (`2e645597e81a330159b2183caf670f685821a9451a37223a782936e88e30d0fe`)
  - `notes/sphere_pi_forces_2026_11_25/PREREG_S110_AMENDMENT1_COUNCIL_PRUNING.md` (`a41399fdb888167288a63cefa540778d921574197f721b8d5322bd8825d0928a`, mandatory overrides applied)
- **Execution Posture:** Strictly CPU-only (`CUDA_VISIBLE_DEVICES=""`, `nice -n 15`, `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`, `torch.set_num_threads(1)`, `0` GPU touch, `WEIGHTS=0`, `0` GitHub writes)
- **Pre-Flight Verdict:** **`10/10` MANDATORY CPU GATES PASS** (`3`-mode `-I` bit-identical `payload_sha256 = cb603cb411de6ad3476eecd96f454639a65cca8629957ce1bcff91f5b6f20012`; dual `aletheia audit-check --strict-ancestors --safety-scan --strict-unseeded PASS x2`)

---

## 1. Pruned 4-Operator Architecture & Amendment-1 Compliance

All 4 pruned mechanisms from `PREREG-S110-AMENDMENT1` (`causal_sinkhorn`, `dense_cayley_lu`, `telluric_direct_skip`, `bingham_post_renorm`) are permanently excluded and **fail-closed rejected** by `S110ModelConfig.validate()` with `S110ConfigError`.

1. **`s110_geosphere_models.py`** — Modular PyTorch implementation of the 4 `sm_86`-viable surviving operators + baseline safety harness + Portal-3 Beltrami diagnostic:
   - **Operator 1 (`CayleyBlock2x2SO`):** Closed-form `2x2` block-diagonal Cayley `SO(d)` feature rotation (`4` FMAs/pair, zero matrix inversion / zero LU, rank-16 data-dependent skew bottleneck, exact `Q^T Q = I_d`, `det = +1`, `<h, Omega h> = 0`).
   - **Operator 2 (`VectorProximalPoloidalBingham`):** Repaired $SO(k)$-equivariant vector-proximal Poloidal Bingham operator $\mathcal{S}_Y^H(u) = \max(0, 1 - \tau_Y / \|u_{\mathrm{pol}}\|_2) u_{\mathrm{pol}} \oplus u_{\mathrm{tor}}$ (NO post-renorm, exact Hodge orthogonality, exact Stagnant-Lid zeroing when $\|u_{\mathrm{pol}}\|_2 \le \tau_Y$, safe zero-NaN gradient branch at $u_{\mathrm{pol}} = 0$ in FP32 & BF16, frozen Stage-1 quantile grid $Y \in \{0, 0.25, 0.50, 0.75, 1.0\}$).
   - **Operator 3 (`DiagonalDarcyEMA`):** Pure diagonal multi-timescale porous EMA $s_t = (1 - \alpha) \odot s_{t-1} + \alpha \odot x_t$ ($0 < \alpha < 1$, log-spaced $\tau \in [2, 128]$) executed via exact zero-wraparound cuFFT causal linear convolution (replacing the initial eager Hillis-Steele scan; `< 1e-6` exact parity vs sequential recurrence).
   - **Operator 4 (`GeothermalACTController` + `FastSurfaceMTPDraft`):** Exact rank-quota integer ACT loop plumes ($r \in \{1..4\}$, exact mean $\bar{r} = 2.000$ via `{1: 37.5%, 2: 37.5%, 3: 12.5%, 4: 12.5%}` with STE differentiable training & quadratic ponder regularizer) + tied-embedding `MTP-8` low-rank surface draft head (`d_draft = 48`).
   - **Portal-3 Beltrami Diagnostic (`run_beltrami_helicity_diagnostic` + `measure_trace_beltrami_rayleigh`):** Verifies the exact `[C, K] = 0` helicity/moment conservation iff law ($m_0..m_4$), non-commuting instantaneous drift law $\dot{H} = v^\top [C, K] v$, and `O3.5` symmetric-residual Rayleigh collapse control.
   - **Baseline Safety Harness (`Channel2BAirlockClamp`):** Outer `DPI` norm clamp + `Track S50` Channel-2B airlock folded into the baseline harness rather than counted as a generative accuracy shell.
2. **`s110_train_eval.py`** — Offline-ready (`HF_HUB_OFFLINE=1`, `WEIGHTS=0`) RTX 3080 + CPU runner implementing:
   - `--microbench`: `<2 min` `sm_86` wall-clock latency kill gate (`> 15%` overhead over matched baseline block => `PRUNE_OVERHEAD_GT_15PCT`),
   - `--stage H10a | H10b | all`: Stage-1 single-shell isolation & Stage-2 coupled `Geosphere-Net-15M` + LOSO matrix + `N0` baselines,
   - Holm-Bonferroni step-down multiple-comparison control + paired bootstrap 95% CIs + 3-valued verdicts (`CONFIRMED` / `FALSIFIED` / `INCONCLUSIVE`),
   - Pre-normalization (`pre-N`) counterfactual $h^{(r)}$ state-patching faithfulness audit.
3. **`s110_cpu_preflight.py`** + **`s110_cpu_preflight_receipt.json`** — Self-contained 10-gate CPU-only pre-flight certifier (`0` bare asserts, `3`-mode `-I` bit-identical).

---

## 2. Full-Scale `15M` Parameter & FLOP Parity Matrix (`seq_len = 512`, `V = 260`)

All `14` Stage-1 (`H10a`), Stage-2 (`H10b` coupled + 4 LOSO), and `N0` external baseline arms satisfy strict `<= 0.50%` parameter parity (`max = 0.2701%`) and `<= 5.0%` FLOP parity (`max_loop_tok = 0.5359%`, `max_problem_equiv = 2.6535%`):

| Arm | Stage | `d_model` / `d_ff` | `L_phys` / `L_eff` | Total Params | Param Dev | Fwd FLOPs/Tok | Equiv FLOP Dev |
| :--- | :--- | :---: | :---: | ---: | ---: | ---: | ---: |
| `H10a_Baseline_Loop` | Stage 1 | `384 / 1104` | `8 / 12` | `14,999,424` | `0.0038%` | `54,316,032` | `0.0000%` |
| `H10a_Shell1_Cayley2x2` | Stage 1 | `384 / 1104` | `8 / 12` | `15,037,056` | `0.2470%` | `54,475,776` | `0.2941%` |
| `H10a_Shell2_BinghamProx` | Stage 1 | `384 / 1104` | `8 / 12` | `14,999,424` | `0.0038%` | `54,320,640` | `0.0085%` |
| `H10a_Shell3_DarcyEMA` | Stage 1 | `384 / 1104` | `8 / 12` | `15,002,496` | `0.0166%` | `54,398,976` | `0.1527%` |
| `H10a_Shell4_ACTPlume_MTP8` | Stage 1 | `384 / 1072` | `8 / 12` | `14,999,810` | `0.0013%` | `54,024,960` | `0.5359%` |
| **`H10b_Geosphere_Full`** | **Stage 2** | **`384 / 1072`** | **`8 / 12`** | **`15,040,514`** | **`0.2701%`** | **`54,272,256`** | **`0.0806%`** |
| `H10b_LOSO_NoCayley` | LOSO | `384 / 1072` | `8 / 12` | `15,002,882` | `0.0192%` | `54,112,512` | `0.3747%` |
| `H10b_LOSO_NoBingham` | LOSO | `384 / 1072` | `8 / 12` | `15,040,514` | `0.2701%` | `54,267,648` | `0.0891%` |
| `H10b_LOSO_NoDarcyEMA` | LOSO | `384 / 1072` | `8 / 12` | `15,037,442` | `0.2496%` | `54,189,312` | `0.2333%` |
| `H10b_LOSO_NoACTDraft` | LOSO | `384 / 1104` | `8 / 12` | `15,040,128` | `0.2675%` | `54,563,328` | `0.4553%` |
| `N0_nGPT_Loop_15M` | `N0` Anchor | `384 / 1104` | `8 / 12` | `15,005,616` | `0.0374%` | `54,316,032` | `0.0000%` |
| `N0_Monolithic_Loop_15M` | `N0` Anchor | `384 / 1104` | `8 / 12` | `14,999,424` | `0.0038%` | `54,316,032` | `0.0000%` |
| `N0_English_CoT_15M` | `N0` Anchor (`1.4x` CoT) | `320 / 864` | `12 / 12` | `14,959,680` | `0.2688%` | `37,767,680` | `2.6535%` |
| `N0_nGPT_Unlooped_15M` | `N0` Anchor (`1.4x` CoT) | `320 / 864` | `12 / 12` | `14,967,456` | `0.2170%` | `37,767,680` | `2.6535%` |

---

## 3. All `10/10` Machine-Verified CPU Pre-Flight Gates (`s110_cpu_preflight_receipt.json`)

| Gate | Locked Contract (`PREREG-S110` + `AMENDMENT1`) | Verified CPU Measurements | Verdict |
| :--- | :--- | :--- | :---: |
| **`G1`** | `2x2` Block Cayley `SO(k)` orth `< 1e-6`, workless, `R=8` norm, grads | `orth = 2.38e-7`, `det = 2.38e-7`, `workless = 2.38e-7`, `R=8 drift = 9.54e-7`, FP32/BF16 grads finite | **PASS** |
| **`G2`** | $\mathcal{S}_Y^H(u)$ $SO(k)$-equiv, Hodge orth, Stagnant Lid, quantile grid | `SO(k) err = 9.54e-7` (vs broken coord control `0.3495`), `Hodge = 0.0`, `Stagnant Lid = 0.0` exact, `Y` plugs `[0, 0.25, 0.5, 0.75, 1.0]`, zero-NaN grads | **PASS** |
| **`G3`** | Diagonal Darcy EMA `0 < alpha < 1`, parallel vs seq parity, contraction | `alpha in [0.007812, 0.5]`, `ratio = 64.0`, `par-vs-seq = 2.68e-7` (`2.682209e-7`), convex `L_inf` contraction, FP32/BF16 grads finite | **PASS** |
| **`G4`** | Integer ACT exact $\bar{r} = 2.000$ + `MTP-8` tied surface draft | `mean_int_r = 2.0` (`r1=0.375, r2=0.375, r3=0.125, r4=0.125`), sparse `B=8` `core_seq_passes = 16.0`, `ponder = 8e-5`, STE & `MTP-8` finite | **PASS** |
| **`G5`** | Portal-3 Beltrami `[C,K]=0` moments `m_0..m_4`, non-comm drift, `O3.5` | `||[C,K]||_F = 0.0`, `m_0..m_4 drift = 1.19e-7` (`motion = 1.597`); non-comm `E_drift = 0.0`, `H_drift = 0.0404`, `dH err = 1.27e-5`; `O3.5` `0.0866 -> 0.7184` monotone | **PASS** |
| **`G6`** | Channel-2B airlock norm bound & fail-closed rejection of `4` pruned traps | Clamped `max_norm = 4.0`; `causal_sinkhorn`, `dense_cayley_lu`, `telluric_direct_skip`, `bingham_post_renorm` all raise `S110ConfigError` | **PASS** |
| **`G7`** | Full `15M` param (`<= 0.50%`) & FLOP (`<= 5.0%`) parity (`14` arms) | `max_param_dev = 0.2701%`, `max_loop_flop_dev = 0.5359%`, `max_equiv_flop_dev = 2.6535%` | **PASS** |
| **`G8`** | Holm-Bonferroni correction & `pre-N` counterfactual patching | `adj_p = [0.016, 0.09, 0.09, 0.45]` (`[T, F, F, F]`); `pre-N` faithfulness `1.0` (`54/54` distinct pos, `self_err = 0.0`, `patch_to_b_err = 0.0`) | **PASS** |
| **`G9`** | CPU micro-train (`6` arms), zero-NaN grads, determinism, `--microbench` | All `6/6` arms drop loss & run `R=6` extrap; `det_diff = 0.0`; `5/5` `--microbench` operators verified | **PASS** |
| **`G10`** | `WEIGHTS=0`, UTF-8 round-trip, `CUDA_VISIBLE_DEVICES=""`, SHA locks | `weight_files = 0`, `utf8_roundtrip = True`, exact parent & Amendment-1 SHAs verified | **PASS** |

---

## 4. Executed RTX 3080 Commands (Serialized Under `flock` + `mlos gpu-lease` + Zone B)

Executed strictly in order under `flock` + `mlos gpu-lease --mode train` + `mlos stamp-run --zone B --require-gpu` + `HF_HUB_OFFLINE=1` + `WEIGHTS=0` (`--multidomain` uses the disjoint offline WikiText-2 + frozen code/docs bundle; `--corpus-path` remains available as a single-file override):

```bash
# 1. MANDATORY <2 min sm_86 wall-clock microbenchmark pre-gate (prunes any op > 15% overhead BEFORE training)
flock /tmp/aletheion_rapl_experiment.lock mlos gpu-lease --mode train -- \
  mlos stamp-run --profile "$MLOS_PROFILE" --zone B --require-gpu \
  --output track-s110-geosphere-net-gpu/mlos_zone_b_s110_microbench.json -- \
  env HF_HUB_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 "$VENV_PY" -I -B \
  track-s110-geosphere-net-gpu/s110_train_eval.py \
  --microbench --device cuda --amp-bf16 --scale full15m --seq-len 512 --batch-size 8 \
  --out-json track-s110-geosphere-net-gpu/s110_sm86_microbench.json

# 2. Stage 1 (H10a: single-shell isolation & earn-your-keep pruning across 3 seeds, 600 steps = 2.46M tok/run)
flock /tmp/aletheion_rapl_experiment.lock mlos gpu-lease --mode train -- \
  mlos stamp-run --profile "$MLOS_PROFILE" --zone B --require-gpu \
  --output track-s110-geosphere-net-gpu/mlos_zone_b_s110_h10a.json -- \
  env HF_HUB_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 "$VENV_PY" -I -B \
  track-s110-geosphere-net-gpu/s110_train_eval.py \
  --stage H10a --multidomain --device cuda --amp-bf16 --scale full15m --seq-len 512 --batch-size 8 --steps 600 \
  --seeds 42 137 2026 \
  --out-json track-s110-geosphere-net-gpu/h10a_gpu_results.json

# 3. Stage 2 (H10b: coupled Geosphere-Net-15M + Holm-Bonferroni LOSO + N0 baselines across 3 seeds)
flock /tmp/aletheion_rapl_experiment.lock mlos gpu-lease --mode train -- \
  mlos stamp-run --profile "$MLOS_PROFILE" --zone B --require-gpu \
  --output track-s110-geosphere-net-gpu/mlos_zone_b_s110_h10b.json -- \
  env HF_HUB_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 "$VENV_PY" -I -B \
  track-s110-geosphere-net-gpu/s110_train_eval.py \
  --stage H10b --multidomain --device cuda --amp-bf16 --scale full15m --seq-len 512 --batch-size 8 --steps 600 \
  --seeds 42 137 2026 \
  --out-json track-s110-geosphere-net-gpu/h10b_gpu_results.json
```
