# Track S113 (`PREREG-S113-AMENDMENT1`): Model-Free Blind Residual Split-Half Exploratory Pattern Report (`N0`)

- **Parent Protocol (Immutable):** `PREREG-S113` (`cebe48326461ef048c6e8ccfb51f76f661f33b44c32d7e0178777d2ad8221e67`)
- **Exploratory Protocol:** `PREREG-S113-AMENDMENT1` (`PREREG_S113_AMENDMENT1_BLIND_ANOMALY_DISCOVERY.md`)
- **Datasets Analyzed (`7/7` Closed Live Phases):** `IDLE`, `A`, `B`, `C`, `D`, `E1` (`E1A` + `E1B`), and `E2` (`E2A` + `E2B`)
- **Anti-`CS-09` Methodological Gate:** Every candidate pattern was screened strictly on **Half 1** (`N_screen = 200` surrogates), locked by exact frequency/spatial/lag coordinate, and evaluated out-of-sample on **Half 2** against **`N_confirm = 799`** matched IAAFT (Iterative Amplitude Adjusted Fourier Transform, preserving exact power spectrum and exact marginal amplitude distribution), circular-shift, rank-1 common-mode EMI, or smooth-PSD surrogates (exact empirical p-value floor `p_min = 1/800 = 0.00125`), followed by **step-down Holm-Bonferroni correction pooled per lens across all 7 analyzed phases (`p_Holm < 0.005`)**.
- **Reproducibility Scope (`AV=0` Privacy-Preserving Policy):** Strictly CPU-only (`CUDA_VISIBLE_DEVICES=""`, single-threaded BLAS), zero raw audio/video waveforms, frames, or binary telemetry arrays staged in this repository (`raw_av_staged_count = 0`). Raw per-phase physical anomaly numbers are therefore **not independently reproducible from this repository alone**; pooled lens-family Holm-Bonferroni recomputation, receipt-to-certificate cryptographic binding, and synthetic positive/null lens tests (`dsp_harnesses/test_s113_blind_anomaly_hunter.py`) **are** independently reproducible.
- **Phase-E Re-Entry Caveat:** Amendment 1 called for surviving blind anomalies to immediately trigger targeted Phase-E confirmatory probes prior to the `2026-11-25T14:44:00Z` sensor shutoff. In practice, per-phase blind-hunter execution completed after shutoff (`14:50:09Z–15:17:54Z`), and confirmatory Phases `E1`/`E2` targeted `H1`/`H3`/`H4` physics probes rather than blind-hunter triggers; the Phase-E re-entry rule was therefore not executed from blind-hunter survivors.
- **$\sigma$ Framing Caveat:** All `z` (`σ`) figures below are parametric extrapolations `(obs - mean_surr) / sd_surr` from the surrogate distribution, **not** empirical tail probabilities; at `N_confirm = 799`, the empirical p-value floor is strictly `1/800 = 0.00125`.

---

## 1. Frozen Deliverable Digests (`evidence/track-s113-multisensor-silicon-physics/`)

| File | Lines / Bytes | SHA-256 |
|---|---:|---|
| `dsp_harnesses/s113_blind_anomaly_hunter.py` | `2,426` L / `116,165` B | `25bf190376d175e9322bfdfe85add83ce3378f0d21ef5b17467dbd22e4054714` |
| `dsp_harnesses/test_s113_blind_anomaly_hunter.py` | `182` L / `9,180` B | `df8fd1ec6cac8c4e4fcad7ddc87c0016c1a97ee193b7f6f4dc35f9ac697b992f` |
| `s113_blind_anomalies_receipt.json` | `3,898` L / `124,324` B | `2bb69fff3145c4714ca1ab207615270dc904eb56d637335a5d88f24c718e6123` |

- **Receipt Cryptographic Binding:** `receipt_payload_sha256 = ffdf68f9baae840f5e7e9d69fd70ad1498b9240f4006a765e63644b5d60f8a1e`, bound to `certificate_payload_sha256 = e8e3da5f45cb3331e0b29ac51d08496d6c3ef1b17e9bf27c9e5ad213908ac574` and all `7/7` source phase manifest digests (`source_phase_manifests_sha256`) and per-phase hunter run JSON digests (`source_phase_json_sha256s`).

### Honest Pooled Lens-Family Holm-Bonferroni Scorecard (`193` Split-Half Candidates -> `2` Pooled Survivors, `191` `holm_rejected`)

Regenerated 100% programmatically by `dsp_harnesses/s113_blind_anomaly_hunter.py --from-phase-jsons`. Because `N_confirm = 799` fixes the empirical p-value floor at `1/800 = 0.00125`, any pooled lens family of size $m \ge 4$ has minimum possible step-down Holm p-value $m / 800 \ge 4/800 = 0.005$ and therefore **cannot** pass `< 0.005` under pooled-across-all-phases Holm:

| Lens Family (`holm_family`) | Pooled Size $m$ | Min Raw $p$ (`N=799`) | Min Pooled $p_{\text{Holm}}$ | Pooled Survivors (`< 0.005`) | `holm_rejected` (`>= 0.005`) | Per-`(Phase, Lens)` Diagnostic Survivors |
|---|---:|---:|---:|---:|---:|---:|
| **`A3_TIME_REVERSAL_ASYMMETRY`** | `2` | `0.00125` | **`0.00250`** | **`2`** | `0` | `2` |
| `A4_SYNCHRONIZED_MULTIPIXEL_BURSTS` | `6` | `0.00125` | `0.00750` | `0` | `6` | `6` |
| `A4_PERSISTENT_TELEGRAPHER_PIXELS` | `13` | `0.00125` | `0.01625` | `0` | `13` | `9` |
| `A1_BICOHERENCE` | `17` | `0.00125` | `0.02125` | `0` | `17` | `3` |
| `A5_RARE_EVENT_COINCIDENCE` | `18` | `0.00125` | `0.02250` | `0` | `18` | `8` |
| `A6_UNINVITED_SPECTRAL_LINE` | `22` | `0.00125` | `0.02750` | `0` | `22` | `6` |
| `A7_NONLINEAR_RESIDUAL_COPULA_MI` | `22` | `0.00125` | `0.02750` | `0` | `22` | `12` |
| `A2_CHIRAL_4X4_CSD` | `45` | `0.00125` | `0.05625` | `0` | `45` | `3` |
| `A4_2D_SPATIAL_WAVE_PEAK` | `48` | `0.00125` | `0.06000` | `0` | `48` | `0` |
| **Total** | **`193`** | `0.00125` | — | **`2`** | **`191`** | **`49`** (`34` excl. A4 RTS/burst) |

All patterns below are **split-half-stable exploratory patterns within one session on one machine (`N0`)** — not independent replications; several are explained by standard mechanisms (CMOS RTS/FPN sensor noise, fan blade-pass harmonics, EC firmware reporting latency). No cross-lens multiplicity correction is applied beyond the per-lens pooled Holm family.

---

## 2. Seven Split-Half-Stable Exploratory Patterns (`N0`) Across Lenses `A1`–`A7`

### Pattern 3 (`Lens A3` — **Survives Pooled Lens-Family Holm (`2/2`, `p_Holm = 0.0025 < 0.005`)**: Microscopic Time-Reversal Asymmetry $\mathcal{A}(\tau) \neq 0$ in `RAPL pkg_w` and `83.5 W` GPU Acoustic Waveforms)
- **Null Baseline Tested:** Stationary linear Gaussian processes and static monotonic nonlinear transforms thereof (`IAAFT`) satisfy $\mathcal{A}(\tau) = \langle z(t)^2 z(t+\tau) - z(t) z(t+\tau)^2 \rangle = 0$.
- **Observed Pattern (`2/2` pooled survivors, `p_raw = 0.00125`, pooled `p_Holm = 0.0025 < 0.005`):**
  1. **`Phase A` `telemetry_pkg_w` ($\tau = 50\text{ ms}$):** $\mathcal{A}_1 = +0.10093$ ($z_1 = 5.96\sigma$), replicating out-of-sample with identical sign $\mathcal{A}_2 = +0.06145$ vs IAAFT $-0.00031$ (parametric $z_2 = 4.24\sigma$, `p_raw = 0.00125`, pooled **`p_Holm = 0.0025`**), consistent with asymmetric fast current-step surges vs slower thermal/PL1 decay.
  2. **`Phase E2B` `dmic_e2b_active_blocks` ($\tau = 3\text{ samples} = 62.5\text{ µs}$):** Under `83.5 W` pulsed GPU + CPU load, the raw `48 kHz` acoustic waveform breaks microscopic time-reversal symmetry with $\mathcal{A}_1 = -0.01762$ ($z_1 = 6.01\sigma$) and $\mathcal{A}_2 = -0.03548$ vs IAAFT $-0.00011$ (parametric $z_2 = 8.14\sigma$, `p_raw = 0.00125`, pooled **`p_Holm = 0.0025`**), consistent with asymmetric steep-attack / ring-down piezo-inductor impulse shapes.

---

### Pattern 1 (`Lens A1` — `holm_rejected` Under Pooled Holm [`m=17`, `p_Holm = 0.02125 >= 0.005`]; `3` Per-Phase Diagnostic): Ultrasonic Quadratic Phase-Locked Triads $f_1 + f_2 = f_3$
- **Null Baseline Tested:** Linear time-invariant acoustic/EMI paths and static monotonic nonlinearities (`IAAFT` null) have zero bispectral phase locking ($b^2(f_1, f_2) \to 0$).
- **Observed Pattern (`17` split-half candidates hitting `p_raw = 0.00125`; pooled `p_Holm = 0.02125` -> `holm_rejected`):**
  1. **Silent `IDLE` & `Phase A` Ultrasonic Mixing:** During `IDLE`, the 4-ch DMIC beam shows split-half quadratic phase locking at $9,187.5 + 12,562.5 = 21,750.0\text{ Hz}$ ($b^2_1 = 0.1789 \to b^2_2 = 0.2053$ vs IAAFT $0.00765$, parametric $z_2 = 25.80\sigma$, `p_raw = 0.00125`). In `Phase A`, both `idle` and `active` blocks repeat $4,687.5 + 13,687.5 = 18,375.0\text{ Hz}$ ($z_2 = 15.63\sigma$ and $10.55\sigma$), $6,562.5 + 13,687.5 = 20,250.0\text{ Hz}$ ($z_2 = 12.92\sigma$), and $9,375.0 + 13,312.5 = 22,687.5\text{ Hz}$ ($z_2 = 7.15\sigma$).
  2. **`83 W` Discrete GPU Bicoherence Surge (`Phase E2`):** Under `80–83.5 W` pulsed discrete GPU load (`E2A` & `E2B`), ultrasonic bicoherence reaches $b^2_2 = 0.8303$ ($z_2 = 45.53\sigma$ at $4,125 + 11,812.5 = 15,937.5\text{ Hz}$), $0.8631$ ($z_2 = 23.07\sigma$ at $3,750 + 12,000 = 15,750\text{ Hz}$), and $0.7860$ ($z_2 = 80.41\sigma$ at $3,937.5 + 12,187.5 = 16,125\text{ Hz}$).
  3. **IR Rolling-Shutter Triad (`Phase B`):** `ir_row_osc_10800hz_led_off` shows $2,109.38 + 3,206.25 = 5,315.62\text{ Hz}$ ($b^2_2 = 0.8027$, $z_2 = 7.44\sigma$).
  4. **Falsified Cross-Rail Audio Sum/Difference Sidebands (`E2A`/`E2B` Negative Control):** Direct low-frequency CPU+GPU intermodulation tones ($1009 \pm 317 = \{692, 1326\}\text{ Hz}$ in `E2A`; $317 \pm 97 = \{220, 414\}\text{ Hz}$ in `E2B`) show zero excess (`p_Holm >= 0.918`).

---

### Pattern 2 (`Lens A2` — `holm_rejected` Under Pooled Holm [`m=45`, `p_Holm = 0.05625 >= 0.005`]; `3` Per-Phase Diagnostic): Always-On `18.5–22.5 kHz` Chiral Acoustic Wavefield & Integer-Cycle Cocycle Wrapping
- **Null Baseline Tested:** Instantaneous common-mode EMI across a 4-microphone array yields a real rank-1 cross-spectral matrix ($\operatorname{Im} S_{ij}(f) = 0$).
- **Observed Pattern (`45` split-half candidates hitting `p_raw = 0.00125`; pooled `p_Holm = 0.05625` -> `holm_rejected`):**
  - Across `IDLE, A, B, C, E1, E2`, `18.5–22.2 kHz` bins (`18,515.6`, `19,453.1`, `22,031.2`, `22,218.8 Hz`) show `offdiag_coh = 0.967–0.982` and `im_ratio = 0.807–0.813` (parametric $z_2 = 17.85–20.53\sigma$ vs real rank-1 EMI surrogates), matching quarter-wave bezel mic spacing ($\lambda_{\text{air}} = 15.5–18.5\text{ mm}$).
  - **Exact Integer-Cycle Resolution of Pairwise TDOA Cocycle Defects (`A2_TDOA_COCYCLE_AND_HOLONOMY`):** Principal-branch pairwise phase delays $\tau_{ij} = \arg(C_{ij})/(2\pi f)$ produce apparent triangle closure defects $+333.26\text{ µs}$ at `3,001 Hz` and $-199.88\text{ µs}$ at `5,003 Hz`, equal to exact integer carrier periods ($+1/3001\text{ s}$ and $-1/5003\text{ s}$), while gauge-invariant loop holonomy vanishes (`0.00078 rad`, `PR = 1.0030`; `-0.00008 rad`, `PR = 1.0005`; `p_surr = 0.965–0.993`).

---

### Pattern 4 (`Lens A4` — `holm_rejected` Under Pooled Holm [`m=48/13/6`, `p_Holm = 0.0600/0.01625/0.0075 >= 0.005`]): 2D Blank-Wall Spatial Modes, Persistent CMOS RTS Pixels, and UVC Multi-Pixel Bursts
- **Null Baseline Tested:** After subtracting static per-pixel flat-field $\bar{I}(y,x)$ and per-frame horizontal row mean $\bar{I}(t,y)$, idealized blank-wall CMOS residuals are spatially white and Gaussian/Poisson.
- **Observed Pattern (`67` split-half candidates across 3 sub-lenses, all `holm_rejected` under pooled Holm; standard CMOS/UVC sensor artifacts):**
  1. **2D Diagonal & Column Spatial Modes (`m=48`, pooled `p_Holm = 0.0600`):** RGB `luma_Y` shows non-horizontal 2D spatial Fourier peaks at $(k_y=1, k_x=18)$, $(k_y=1, k_x=15)$, and $(k_y=4, k_x=65)$ (parametric $z_2 = 57.7–478.5\sigma$), and IR `LED_ON`/`LED_OFF` shows column modes $k_x \in \{1, 4, 7\}$ ($z_2 = 16.8–892.7\sigma$).
  2. **Persistent Random-Telegraph-Signal (RTS) Pixels (`m=13`, pooled `p_Holm = 0.01625`):** Standard CMOS oxide-trap bistable blinking pixels locked in Half 1 show elevated Half-2 excess kurtosis (`+8.59` to `+11.25` in IR `LED_OFF`, `+3.47` to `+9.12` in RGB `luma_Y`, `+17.85` to `+20.57` in `chroma_Cb`; parametric $z_2 = 5.57–73.64\sigma$).
  3. **Synchronized Multi-Pixel UVC Bursts (`m=6`, pooled `p_Holm = 0.0075`):** RGB shows simultaneous frame-wide $>4\sigma$ bursts across `IDLE`, `B`, `E2B` (parametric $z_2 = 4.70–9.36\sigma$; IR shows `0`).
  4. **Diagnostic Resolution of Phase-D `LED_OFF` Variance:** Steady-state median-stratified `LED_OFF` stacks show `0` inverted shot-noise rows, confirming Phase-D/E1D high variance came from initial V4L2 auto-exposure startup frames.

---

### Pattern 5 (`Lens A5` — `holm_rejected` Under Pooled Holm [`m=18`, `p_Holm = 0.0225 >= 0.005`]; `8` Per-Phase Diagnostic): `-80 ms` Acoustic Lead Before EC `RAPL` Telemetry & `psys_w` Firmware Rail Scaling
- **Null Baseline Tested:** Uncoupled circular-shift surrogates between top-100 innovation timestamps across sensor modalities.
- **Observed Pattern (`18` split-half candidates hitting `p_raw = 0.00125`; pooled `p_Holm = 0.0225` -> `holm_rejected`; standard firmware reporting latency):**
  1. **`-80 ms` Telemetry Lag (`Phase E2A`):** Top-100 innovation spikes in `dmic_ultrasonic_14_23k_log` precede `dark_w` (`psys_w - pkg_w`) spikes by `80 ms` ($\tau = -0.080\text{ s}$, `38/100` Half-2 coincidences vs null `12.48`, parametric $z_2 = 7.12\sigma$), explained by `~80 ms` Embedded Controller (`EC`) firmware filtering latency on the `psys` register versus `~0.25 ms` airborne acoustic propagation.
  2. **`psys_w` Sub-Package Firmware Scaling:** Across all phases, `psys_w` reads `6.48–7.43 W` while `pkg_w` reads `54.8–68.1 W` (`dark_w ≈ -52 W`), creating `75–99%` zero-lag coincidence because `psys` on this hardware reports a different/scaled rail.

---

### Pattern 6 (`Lens A6` — `holm_rejected` Under Pooled Holm [`m=22`, `p_Holm = 0.0275 >= 0.005`]; `6` Per-Phase Diagnostic): Uninvited High-$Q$ Rolling-Shutter Lines & Fan/Clock Harmonics
- **Null Baseline Tested:** Smooth continuous noise floors outside `60 Hz` mains, `30 fps` frame combs, and injected prime stimuli.
- **Observed Pattern (`22` split-half candidates hitting `p_raw = 0.00125`; pooled `p_Holm = 0.0275` -> `holm_rejected`; standard fan/clock/oscillator lines):**
  1. **IR Rolling-Shutter Lines (`10.8 kHz`):** `1,048.1 -> 1,049.4 Hz` (`IDLE` `LED_ON`, $Q = 198.8$, $z_2 = 17.32\sigma$), `932.1 -> 930.8 Hz` (`IDLE` `LED_OFF`, $Q = 235.7$, $z_2 = 15.90\sigma$), `688.2 -> 689.5 Hz` (`E1B` `LED_OFF`, $Q = 74.6$, $z_2 = 11.67\sigma$), plus the `30.32–31.64 Hz` frame strobe beat ($z_2 = 188.8–893.2\sigma$).
  2. **DMIC Fan Shaft & Blade-Pass Lines (`A, B, E2`):** Standard mechanical aeroacoustic tones at `79.10 Hz` (`4,746 RPM / 60` fan shaft rate, $z_2 = 137.8\sigma$), `380.86 / 401.37 Hz` (5th-harmonic blade-pass), and `143.55–146.48 Hz` (`E2A`).

---

### Pattern 7 (`Lens A7` — `holm_rejected` Under Pooled Holm [`m=22`, `p_Holm = 0.0275 >= 0.005`]; `12` Per-Phase Diagnostic): Non-Linear Copula Mutual Information Beyond Multi-Lag Linear Projection
- **Null Baseline Tested:** Mutual independence ($\mathrm{MI} = 0$) of cross-modal residuals after linear multi-lag (`lags = -2..+2`) OLS orthogonalization, compared against `IAAFT` surrogates.
- **Observed Pattern (`22` split-half candidates hitting `p_raw = 0.00125`; pooled `p_Holm = 0.0275` -> `holm_rejected`):**
  - `E1A` (`dmic_ultrasonic_14_23k_log` $\leftrightarrow$ `uncore_w`): linear $r = -0.0945$, Half-2 rank-copula $\mathrm{MI}_2 = 0.05283\text{ nats}$ vs IAAFT $0.00418\text{ nats}$ (parametric $z_2 = 24.45\sigma$).
  - `E2A` (`dmic_crest_factor` $\leftrightarrow$ `uncore_w`): $r = -0.0550$, $\mathrm{MI}_2 = 0.02431\text{ nats}$ vs IAAFT $0.00385\text{ nats}$ ($z_2 = 11.01\sigma$).
  - `C, E1A, E2A` (`core_w` $\leftrightarrow$ `uncore_w`): curved power-budget allocation boundary ($\mathrm{MI}_2 = 0.0913–0.1272\text{ nats}$, $z_2 = 22.07–50.21\sigma$).

---

## 3. Reproducible Verification Commands

```bash
# Pure-stdlib audit & pooled Holm recomputation (zero external dependencies)
python3 -I -B s113_multisensor_audit.py --check s113_multisensor_certificate.json --json
python3 -I -B test_s113_multisensor_audit_r5.py

# Synthetic positive/null DSP blind-hunter tests (when numpy & scipy are installed)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES="" \
  python3 -I -B dsp_harnesses/test_s113_blind_anomaly_hunter.py
```
