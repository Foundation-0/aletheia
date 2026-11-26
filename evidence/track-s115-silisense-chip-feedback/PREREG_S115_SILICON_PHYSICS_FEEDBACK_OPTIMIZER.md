# `PREREG-S115`: Non-Textbook Silicon Physics Observables (`S113` Amendment-1) as Closed-Loop Dependent Variables for `HoloSphere` Chip-Level Optimization (`EXP-Q21a..c`)

- **Document ID:** `PREREG-S115-SILICON-PHYSICS-FEEDBACK-OPTIMIZER-V1`
- **Status:** **IMMUTABLE PRE-RUN LOCK** (written & SHA-256-logged in `verification/AUDIT_LOG.md` strictly BEFORE any live GPU/RAPL benchmark or audio-window experiment)
- **Date (UTC):** `2026-11-25`
- **Owner:** `gravity-probe` (`Track S115` / candidate standalone `Moissanite-Labs/silisense`, plug-compatible with `Moissanite-Labs/holosphere` telemetry)
- **Target Hardware (When Live-Dispatched):** ASUS ZenBook Pro Duo `UX582HS` (`Intel Core i9-11980HK` `intel-rapl` `pkg_w`/`core_w`/`uncore_w`/`psys_w` + `NVIDIA GeForce RTX 3080 Laptop GPU` `GA104M` `sm_86`), serialized under `flock` + `mlos gpu-lease` + `mlos stamp-run --zone B`, `WEIGHTS=0`, `AV=0`, `ELF=0`.
- **Anchored Empirical Baselines (Immutable Prior Receipts):**
  - `Track S113` (`s113_multisensor_certificate.json` `831ab960...` & `s113_blind_anomalies_receipt.json` `cb0c9548...`, `W10-OBS-29`): Dual-verified (`0` blockers) discovery of `193` split-half + `N=799` IAAFT (`p_Holm < 0.005`) non-textbook silicon/firmware invariants, including:
    - **`A1`:** `80.4σ` (`b^2 = 0.86`) `83 W` GPU VRM ultrasonic quadratic phase bicoherence (`25.8σ` idle).
    - **`A2`:** `0.81` chiral `18.5–22.2 kHz` acoustic cross-spectrum + `13.4 cm` lateral `ch0–ch3` TDOA sign-reversal triangulation between CPU VRM and GPU VRM rails.
    - **`A3`:** `-8.14σ` (`62.5 µs`) third-order time-reversal asymmetry $\mathcal{A}(\tau)$ from nonlinear sawtooth transient steepening.
    - **`A5`:** `-80 ms` precursor lead (`320×` faster than EC `psys` firmware telemetry).
    - **`A7`:** `24.45σ` zero-linear-correlation rank-copula mutual information with `uncore_w` ring-bus / memory-controller power.
    - **`H3`/`H4` Negative Result:** Confirmed `0` CPU/GPU workload leakage into optical RGB/IR sensors (`<= 2.36 ppm` at `141 W`), justifying permanent exclusion of camera devices from chip-performance profiling.
  - `Track S107` (`H7b`, `h7b_gpu_results.json` `0775dd1c...`) & `Track S114` (`PREREG-S114` `5fa927a0...`): Unfused eager PyTorch `SU(2)` holonomy scan pays a `3.913×` wall-clock slowdown from `~60` micro-kernel launches/layer and HBM round-trips, whereas `S114` (`su2_holonomy_scan_sm86.cu`) fuses forward/backward holonomy and covariant $(Q, K, V)$ transport into `0 B`-spill warp-shuffle `float4` registers.

---

## 1. Strict Two-Mode Privacy & Sensor Airlock (Hard Fail-Closed Invariant)

1. **Unconditional Camera Ban (`ERR_CAMERA_FORBIDDEN`):** `/dev/video*` and V4L2/PipeWire camera endpoints are **permanently banned** across all modes. `Track S113` (`H3`/`H4`) proved optical sensors carry zero chip-telemetry signal while carrying maximal privacy risk.
2. **Mode 1 (`telemetry-only`, Default):**
   - Reads **only** non-acoustic power/clock counters: `intel-rapl` (`50–200 Hz` `pkg_w`, `core_w`, `uncore_w`, `psys_w`) and `nvidia-smi` / NVML (`gpu_power_w`, `sm_clock_mhz`, `gpu_temp_c`, `SwPowerCap` / `HwThermalSlowdown` flags).
   - Computes `A3` (power-increment time-reversal asymmetry $\mathcal{A}(\tau)$), `A5` (`200 Hz` fast-rail precursor lead over `psys_w` / `SwPowerCap` / `1 Hz` polling), and `A7` (multi-lag Schur linear-residualized rank-copula MI `uncore_w <-> gpu_power_w`).
   - **Zero `/dev/snd/*` or audio tools may be opened in Mode 1.**
3. **Mode 2 (`--enable-dmic-authorized`, Fail-Closed Opt-In):**
   - Requires **all three** explicit capabilities: `--enable-dmic-authorized`, finite `--authorize-audio-window-sec` in `(0.0, 300.0]`, and explicit `--pi-authorization-token` (monotonic deadline enforced on every read; expired windows fail closed with `ERR_AUDIO_WINDOW_EXPIRED`).
   - Adds `48 kHz` 4-channel DMIC observables `A1` (`[6, 23] kHz` bicoherence $b^2$), `A2` (`[18.5, 22.2] kHz` chirality $\chi_{03}$ + `ch0–ch3` CPU-vs-GPU VRM lateral TDOA), `A3-62us` (`20.8–62.5 µs` acoustic shockwave asymmetry), and `A5-80ms` (`15–22 kHz` ultrasonic envelope precursor).
   - Raw audio waveforms are **never** persisted to disk (`AV=0`); only scalar/spectral summary statistics are emitted.

---

## 2. Novelty Classification (`N1`, `n2_claims = 0`) & Null-Model Controls

- **Classification (`N1`):** Kim–Powers bicoherence (`1979`), Knapp–Carter GCC-PHAT (`1976`), Pomeau third-order time-reversal asymmetry (`1982`), Schreiber/rank-copula mutual information, Schreiber–Schmitz IAAFT surrogates (`1996`), and interleaved `ABABAB` autotuning are established `N0` primitives. Co-designing them into a fail-closed silicon-observable profiler, precursor throttle governor, and multi-objective `HoloSphere` kernel autotuner is classified strictly as `N1` (`n2_claims = 0`).
- **Mandatory Anti-Illusion Nulls:**
  - Every `A1`, `A3`, and `A7` test statistic is scored against **IAAFT surrogates** (`N_iaaft = 199` online / `799` offline audit) preserving both exact marginal amplitude distribution and exact power spectrum $|X(f)|^2$ (preventing colored `1/f` or `AR(1)` spectra from triggering false positives).
  - `A2` chirality is scored against **locally median-smoothed PSD surrogates** (`width = 9` bins) so narrowband tones cannot inflate constant-phase surrogates.
  - `A5` precursor lead-lag is scored against **circular-shift surrogates** (`N_circ = 500`, minimum guard shift `max(2 * L_max, N // 10)`) preserving exact autocorrelation of both series.
  - `A7` projects out **all linear lag correlations** `k in [-L, +L]` (`L = 5`) via least-squares Schur orthogonalization (`max_k |Corr(r_y, u_{t+k})| <= 1e-9`) strictly prior to rank-copula MI estimation.

---

## 3. Locked Falsifiable Hypotheses & Literal Kill Gates

All multi-seed evaluations lock seeds `[42, 137, 2026]`, Holm–Bonferroni family-wise significance `alpha = 0.005`, `CS-08` equal-token-work accounting, and interleaved `ABABAB` block ordering (`>= 3` A/B pairs per seed) to cancel monotonic chassis warm-up drift.

### `H15a` (`EXP-Q21a`) — Fused `HoloSphere` (`S114`) vs. Eager PyTorch (`H7b`) Non-Textbook Silicon Signature
- **Claim:** Replacing unfused eager `H7b` (`~60` micro-kernel launches/layer + HBM norm/scan round-trips) with `S114`'s `0 B`-spill warp-fused `SU(2)` holonomy kernel measurably suppresses microscopic power/acoustic shockwave steepening (`|A3|`) and nonlinear PCIe/ring-bus uncore contention (`A7`), even when paced to matched average GPU wattage.
- **Protocol:** Interleaved `ABABAB` blocks (`>= 3` pairs × `3` seeds) under (i) unthrottled `CS-08` equal-tokens-per-block execution AND (ii) throughput-paced equal-wattage execution (`|mean_gpu_w_eager - mean_gpu_w_fused| / mean_gpu_w_fused <= 5.0%`).
- **Locked Pass Criteria:**
  1. **Non-Gaussian Silicon Activity Gate:** At least one arm exhibits non-textbook silicon dynamics surviving `N >= 199` (`799` final audit) surrogates at `p_Holm < 0.005` (`|z_surr| >= 3.5`).
  2. **Shockwave & Contention Reduction Gate:** Fused `HoloSphere` reduces **BOTH** `|A3|` time-reversal shockwave magnitude AND `A7` uncore-to-GPU residual copula MI by **`>= 20.0%` relative (`z <= -2.0` across paired `AB` blocks)** vs. Eager `H7b` (and under Mode-2 audio authorization, reduces `A1` ultrasonic bicoherence $b^2$ by `>= 15.0%`, `z <= -2.0`).
  3. **Equal-Wattage Non-Confound Gate:** Under `<= 5.0%` matched mean GPU wattage pacing, `>= 1` non-textbook observable (`|A3|`, `A7`, or `A1`) still separates Fused `HoloSphere` from Eager `H7b` at `z <= -2.0` (ruling out trivial mean-wattage scaling).
- **Literal Grading Rule:**
  - `CONFIRMED`: Criteria 1, 2, and 3 ALL pass.
  - `PARTIAL`: Criterion 1 passes AND `>= 1` observable in Criterion 2 drops by `>= 20.0%` (`z <= -2.0`), but either the second observable or Criterion 3 misses.
  - `FALSIFIED`: Criterion 1 fails, or neither `|A3|` nor `A7` achieves `>= 20.0%` (`z <= -2.0`) reduction.

### `H15b` (`EXP-Q21b`) — `A5` Sub-Millisecond / High-Rate Precursor Closed-Loop Governor
- **Claim:** Causal `A5` fast-rail innovation spikes (`200 Hz` `RAPL+NVML` in Mode 1; `-80 ms` `48 kHz` DMIC ultrasonic envelope in Mode 2) predict `SwPowerCap` / thermal throttling earlier than standard `1 Hz` `nvidia-smi` polling and cut throttle stalls or `mJ/tok` jitter without net throughput loss.
- **Four Locked Arms (`3` seeds, paired sustained runs):**
  1. `NoGovernor` (uncontrolled sustained training baseline)
  2. `Reactive-1Hz-SMI` (standard `1 Hz` reactive power/thermal polling control)
  3. `Shuffled-Trigger-Control` (exact same number/duration of damping actions as `SiliSense-Precursor-Gov`, applied at circularly shifted timestamps — strict duty-cycle non-specificity control)
  4. `SiliSense-Precursor-Gov` (causal `A5` innovation trigger `z_innov >= 2.5` applying bounded micro-pacing before `SwPowerCap` clamp)
- **Locked Pass Criteria:**
  1. **Genuine Precursor Lead Gate:** `A5` fast innovations precede `SwPowerCap` / `HwThermalSlowdown` / `psys_w` excursion onsets with peak causal precursor lag `<= -20.0 ms` (Mode 1) or `<= -60.0 ms` (Mode 2) and circular-shift `p_circ < 0.005`.
  2. **Closed-Loop Stability Gate:** `SiliSense-Precursor-Gov` reduces `SwPowerCap`/thermal stall fraction by **`>= 25.0%` (`z <= -2.0`)** OR step `mJ/tok` coefficient of variation (`CV`) by **`>= 20.0%` (`z <= -2.0`)** relative to **BOTH** `NoGovernor` and `Reactive-1Hz-SMI`, **AND** beats `Shuffled-Trigger-Control` (`z <= -2.0`), with net throughput delta **`>= -2.0%`** (at most `2.0%` `tok/s` cost, or net speedup).
- **Literal Grading Rule:**
  - `CONFIRMED`: Criteria 1 and 2 BOTH pass (including beating `Shuffled-Trigger-Control`).
  - `PARTIAL`: Criterion 1 passes (`p_circ < 0.005`), OR Criterion 2 beats `NoGovernor`/`Reactive-1Hz-SMI` but misses `Shuffled-Trigger-Control` or incurs `2.0%–5.0%` throughput cost.
  - `FALSIFIED`: Fails Criterion 1 (`p_circ >= 0.005`) AND fails Criterion 2.

### `H15c` (`EXP-Q21c`) — Silicon-Observable Multi-Objective Kernel Autotuner vs. Scalar `tok/s` Tuning
- **Claim:** Selecting `HoloSphere` kernel/execution knobs $\theta = (\text{warp\_tile\_t}, \text{num\_warps}, \text{micro\_batch}, \text{grad\_ckpt})$ at constant `CS-08` effective tokens/step (`micro_batch * grad_accum * seq_len = const`) using non-textbook silicon observables avoids contention-heavy / shockwave-heavy configurations that win short `tok/s` warmups but degrade sustained energy-delay product (`EDP = mJ/tok * ms/tok`).
- **Locked Composite Objective (Zero Post-Hoc Weight Tuning):**
  $$\mathcal{J}(\theta) = \frac{\text{EDP}_{\text{cal}}(\theta)}{\min_{\theta'} \text{EDP}_{\text{cal}}(\theta')} + 0.15\,\max\!\left(0,\, |z_{A3}(\theta)| - 2.0\right) + 0.15\,\max\!\left(0,\, z_{A7}(\theta) - 2.0\right) + 0.10\,\text{PrecursorRate}_{A5}(\theta)$$
  where $(\lambda_{A3}, \lambda_{A7}, \lambda_{A5}) = (0.15, 0.15, 0.10)$ are frozen here and the `2.0σ` hinge ensures sub-significance noise fluctuations contribute zero penalty.
- **Three Locked Arms (Evaluated on Held-Out Sustained `ABABAB` Confirmation Runs, `3` Seeds):**
  1. `Scalar-TokPerSec-Tuner`: $\theta^*_{\text{tps}} = \arg\max_\theta \text{tok/s}_{\text{cal}}(\theta)$
  2. `Scalar-MeanWatt-EDP-Tuner`: $\theta^*_{\text{edp0}} = \arg\min_\theta \text{EDP}_{\text{cal}}(\theta)$ (textbook scalar power-aware baseline)
  3. `SiliSense-Composite-Tuner`: $\theta^*_{\text{sili}} = \arg\min_\theta \mathcal{J}(\theta)$
- **Locked Pass Criteria:**
  1. **Sustained `EDP` Win Over Scalar `tok/s` Tuner:** `SiliSense-Composite-Tuner` achieves **`>= 5.0%` lower held-out sustained `EDP` (`z <= -2.0`)** than `Scalar-TokPerSec-Tuner`.
  2. **Sustained `EDP` or Thermal-Drift Win Over Textbook Mean-Wattage Tuner:** Beats `Scalar-MeanWatt-EDP-Tuner` by **`>= 2.0%` lower sustained `EDP` (`z <= -2.0`)** OR **`>= 15.0%` lower late-run `EDP` drift (`EDP_tail / EDP_head - 1`, `z <= -2.0`)**.
- **Literal Grading Rule:**
  - `CONFIRMED`: Criteria 1 and 2 BOTH pass.
  - `PARTIAL`: Criterion 1 passes (`>= 5.0%` `EDP` win vs `Scalar-TokPerSec-Tuner`, `z <= -2.0`), while tying `Scalar-MeanWatt-EDP-Tuner` within `±2.0%`.
  - `FALSIFIED`: `< 5.0%` sustained `EDP` improvement over `Scalar-TokPerSec-Tuner` or `z > -2.0`.

---

## 4. Architectural Boundary: Clean Standalone (`Moissanite-Labs/silisense`) vs. `HoloSphere` Fusion

- **Standalone Readiness (`Moissanite-Labs/silisense`):** `s115_silisense_profiler.py` and `s115_feedback_autotuner.py` have **zero dependency** on `torch` or `holosphere` internals — they consume generic `TelemetryTrace` dicts/arrays and `KernelConfig` tables, so `silisense` works out-of-the-box on any GPU/CPU workload or repository.
- **Drop-In `HoloSphere` Hook:** When `H15a–c` confirm live on RTX 3080, `PrecursorThrottleGovernor` and `SiliSenseKernelAutotuner` expose a 10-line callback protocol (`on_step_telemetry`, `select_optimal_config`) that plugs into `holosphere/telemetry/` without coupling `holosphere/kernels/` to OS sysfs readers.
