# Track S113 (`PREREG-S113-AMENDMENT1`): Model-Free Blind Residual Silicon Pattern Report (exploratory, N0 — not beyond-textbook discoveries)

- **Parent Protocol (Immutable):** `PREREG-S113` (`cebe48326461ef048c6e8ccfb51f76f661f33b44c32d7e0178777d2ad8221e67`)
- **Discovery Protocol:** `PREREG-S113-AMENDMENT1` (`notes/multisensor_silicon_2026_11_25/PREREG_S113_AMENDMENT1_BLIND_ANOMALY_DISCOVERY.md`)
- **Datasets Analyzed (`7/7` Closed Live Phases):** `IDLE`, `A`, `B`, `C`, `D`, `E1` (`E1A` + `E1B`), and `E2` (`E2A` + `E2B`)
- **Anti-`CS-09` Methodological Gate:** Every candidate pattern was discovered strictly on **Half 1** (`N_screen = 200` surrogates), locked by exact frequency/spatial/lag coordinate, and evaluated out-of-sample on **Half 2** against **`N_confirm = 799`** matched IAAFT (Iterative Amplitude Adjusted Fourier Transform, preserving exact power spectrum and exact marginal amplitude distribution), circular-shift, rank-1 common-mode EMI, or smooth-PSD surrogates (`p_min = 1/800 = 0.00125`), requiring **Holm-Bonferroni corrected `p_Holm < 0.005`** plus minimum effect-size thresholds (`z >= 3.5` or `4.0`).
- **Privacy & Execution Discipline:** Strictly CPU-only (`CUDA_VISIBLE_DEVICES=""`, single-threaded BLAS), zero raw audio/video waveforms or frames emitted outside `local_raw_av/` (`0700`/`0600`).

---

## 1. Frozen Deliverable Digests (`track-s113-multisensor-silicon-physics/`)

| File | Lines / Bytes | SHA-256 |
|---|---:|---|
| `s113_blind_anomaly_hunter.py` | `2,241` L / `107,027` B | `3f096806b619e902ed39fd1a9f2153cb7f259018f998ec0d92ceef6460a6eaf1` |
| `test_s113_blind_anomaly_hunter.py` | `154` L / `7,335` B | `1adae8853ec1d9cadd500f13682937cdcd47458aec5ab42389338da7822ec8c5` |
| `s113_blind_anomalies_receipt.json` | `3599` L / `115,130` B | `fc27014993aa3b214029972309bc1fe31a087de4f6344aa064e55d35c5785e2c` |

Across all `7` phases (`9` manifest streams), **`2` split-half-replicated instances** survive the preregistered lens-family Holm gate `p_Holm < 0.005` pooled across phases (only `A3_TIME_REVERSAL_ASYMMETRY`: `2`, in phases `A` and `E2`; recomputed `p_Holm = 0.0025`). The earlier revision of this receipt stored per-`(phase,lens)` Holm values (family sizes 2–6) and overstated the survivor count as `174`; the audit now recomputes pooled-per-lens Holm from the shipped raw p fields and requires every stored `half2_p_holm` to equal it (`BLIND_HOLM_NOT_RECOMPUTED`), so `191` candidates sit in `holm_rejected`. A per-`(phase,lens)` family definition would give `34`; the amendment states the pooled lens family. These are **split-half-stable exploratory patterns within one session on one machine (N0)** — not independent replications and not claimed as non-textbook discoveries; several are explained by standard mechanisms (CMOS RTS/FPN sensor noise, fan blade-pass harmonics, firmware reporting latency). **The raw physical captures/telemetry do not ship, so the physical runs are not reproducible from this repo**; the receipt + certificate are the anchor. σ values are parametric extrapolations (empirical p floor `1/800` at `N_confirm = 799`).

---

## 2. Seven Split-Half-Stable Exploratory Patterns (N0) Across Lenses `A1`–`A7`

### Discovery 1 (`Lens A1` — Ultrasonic Quadratic Phase-Locked Triads $f_1 + f_2 = f_3$ in Silent `IDLE` and `83 W` GPU Load; Cross-Rail Audio Linear Decoupling)
- **Textbook Prior Violated:** Linear time-invariant acoustic/EMI paths and arbitrary static monotonic nonlinearities (`IAAFT` null) have zero bispectral phase locking ($b^2(f_1, f_2) \to 0$).
- **Observed Pattern (`p_Holm = 0.0025`):**
  1. **Silent `IDLE` & `Phase A` Ultrasonic Mixing:** Even with zero user workload (`IDLE`), the 4-ch DMIC beam exhibits replicated quadratic phase locking at $9,187.5 + 12,562.5 = 21,750.0\text{ Hz}$ ($b^2_1 = 0.1789, z_1 = 25.30\sigma \to b^2_2 = \mathbf{0.2053}$ vs IAAFT $0.00765$, **$z_2 = 25.80\sigma, p_{\text{Holm}} = 0.0025$**). In `Phase A`, both `idle` and `active` blocks replicate $4,687.5 + 13,687.5 = 18,375.0\text{ Hz}$ ($z_2 = 15.63\sigma$ and $10.55\sigma$), $6,562.5 + 13,687.5 = 20,250.0\text{ Hz}$ ($z_2 = 12.92\sigma$), and $9,375.0 + 13,312.5 = 22,687.5\text{ Hz}$ ($z_2 = 7.15\sigma$). Notably, $4,687.5\text{ Hz} = 48,000 \times 5 / 51.2$ and $9,375.0\text{ Hz} = 2 \times 4,687.5\text{ Hz}$ are exact rational sub-divisions of the `48 kHz` PDM/PCM decimation clock mixing quadratically with a `~13.69 kHz` switching rail.
  2. **`83 W` Discrete GPU Bicoherence Surge (`Phase E2`):** Under `80–83.5 W` pulsed discrete GPU load (`E2A` & `E2B`), ultrasonic bicoherence surges `4×` to near-unity:
     - `E2A`: $4,125.0 + 11,812.5 = 15,937.5\text{ Hz}$ ($b^2_1 = 0.8715 \to b^2_2 = \mathbf{0.8303}$, **$z_2 = 45.53\sigma$**) and $3,750.0 + 12,000.0 = 15,750.0\text{ Hz}$ ($b^2_1 = 0.8502 \to b^2_2 = \mathbf{0.8631}$, **$z_2 = 23.07\sigma$**).
     - `E2B`: $3,937.5 + 12,187.5 = 16,125.0\text{ Hz}$ ($b^2_1 = 0.8484 \to b^2_2 = \mathbf{0.7860}$, **$z_2 = 80.41\sigma, p_{\text{Holm}} = 0.0025$**) and $3,937.5 + 14,062.5 = 18,000.0\text{ Hz}$ ($b^2_2 = \mathbf{0.7659}$, **$z_2 = 66.31\sigma$**).
  3. **IR Rolling-Shutter Nyquist-Edge Quadratic Triad (`Phase B`):** `ir_row_osc_10800hz_led_off` replicates $2,109.38 + 3,206.25 = 5,315.62\text{ Hz}$ ($b^2_1 = 0.8282 \to b^2_2 = \mathbf{0.8027}$ vs IAAFT $0.0921$, **$z_2 = 7.44\sigma, p_{\text{Holm}} = 0.0025$**).
  4. **Falsified Cross-Rail Audio Sum/Difference Sidebands (`E2A`/`E2B` Negative Control):** Direct low-frequency CPU+GPU intermodulation tones ($1009 \pm 317 = \{692, 1326\}\text{ Hz}$ in `E2A`, prominence `0.64–1.09×` median; $317 \pm 97 = \{220, 414\}\text{ Hz}$ in `E2B`, prominence `0.90–1.00×` median) show **zero** excess (`p_Holm >= 0.918`). Thus CPU and GPU VRMs are linearly decoupled at audio fundamentals while exhibiting strong quadratic nonlinearity in the `15.75–23.6 kHz` ultrasonic electro-acoustic regime.

---

### Discovery 2 (`Lens A2` — Always-On `18.5–22.5 kHz` Chiral Acoustic Wavefield $\operatorname{Im} S_{ij}(f)/|S_{ij}(f)| \approx 0.81$ & Integer-Cycle Cocycle Branch Resolution)
- **Textbook Prior Violated:** Shared-ground/power-plane EMI across a 4-microphone array is instantaneous ($c \sim 1.5\times 10^8\text{ m/s}$), yielding a real rank-1 cross-spectral matrix ($\operatorname{Im} S_{ij}(f) = 0$).
- **Observed Pattern (`45` Replicated Peaks Across `IDLE, A, B, C, E1, E2`, `p_Holm = 0.00375`):**
  - Even during untouched `dmic_4ch_pure_idle`, `18,515.6 Hz` (`offdiag_coh = 0.9823`, `im_ratio = 0.8131`, **$z_2 = 18.89\sigma$**), `19,453.1 Hz` (`offdiag_coh = 0.9748`, `im_ratio = 0.8071`, **$z_2 = 18.84\sigma$**), and `22,031.2 Hz` (`offdiag_coh = 0.9673`, `im_ratio = 0.8105`, `loop_circulation = 0.0164`, **$z_2 = 17.85\sigma$**) have **`>80%` skew-symmetric imaginary cross-spectra** vs real rank-1 EMI + smooth sensor noise surrogates (`0.099–0.121`), persisting across every active and idle phase up to **$z_2 = 20.53\sigma$** (`22,218.8 Hz` in `E2A`). At $18.5–22.2\text{ kHz}$, $\lambda_{\text{air}} = 15.5–18.5\text{ mm}$ matches the quarter-wave bezel mic spacing, proving a continuous inaudible ultrasonic wavefield inside the "silent" chassis.
  - **Exact Resolution of Pairwise TDOA Cocycle Defects (`A2_TDOA_COCYCLE_AND_HOLONOMY`):** Principal-branch pairwise phase delays $\tau_{ij} = \arg(C_{ij})/(2\pi f)$ produce large apparent triangle closure defects $\tau_{01}+\tau_{12}-\tau_{02} = +333.26\text{ µs}$ at `3,001 Hz` (`E1A` `LAMB_3001HZ`) and $-199.88\text{ µs}$ at `5,003 Hz` (`LAMB_5003HZ`). Those values equal **exact integer carrier periods** ($+1/3001\text{ s} = +333.22\text{ µs}$ and $-1/5003\text{ s} = -199.88\text{ µs}$), while the gauge-invariant complex loop holonomy $\arg(C_{01}C_{12}C_{02}^*)$ vanishes to **`0.00078 rad` (`PR = 1.0030`)** and **`-0.00008 rad` (`PR = 1.0005`)** (`p_surr = 0.965–0.993`), proving the narrowband carrier is rank-1 with topological $2\pi$ phase wrapping rather than non-reciprocal propagation.

---

### Discovery 3 (`Lens A3` — Microscopic Time-Reversal Asymmetry $\mathcal{A}(\tau) \neq 0$ in `RAPL pkg_w` and `83.5 W` GPU Acoustic Waveforms)
- **Textbook Prior Violated:** Every linear Gaussian process and static nonlinear transform thereof (`IAAFT`) satisfies $\mathcal{A}(\tau) = \langle z(t)^2 z(t+\tau) - z(t) z(t+\tau)^2 \rangle = 0$.
- **Observed Pattern (`p_Holm = 0.00125`):**
  1. **`Phase A` `telemetry_pkg_w` ($\tau = 50\text{ ms}$):** $\mathcal{A}_1 = +0.10093$ ($z_1 = 5.96\sigma$), replicating out-of-sample with identical sign $\mathcal{A}_2 = +0.06145$ vs IAAFT $-0.00031$ (**$z_2 = 4.24\sigma, p_{\text{Holm}} (pooled lens family) ≥ 0.005 — rejected$**), capturing asymmetric fast current-step surges vs slower thermal/PL1 decay.
  2. **`Phase E2B` `dmic_e2b_active_blocks` ($\tau = 3\text{ samples} = 62.5\text{ µs}$):** Under `83.5 W` pulsed GPU + CPU load, the raw `48 kHz` acoustic waveform breaks microscopic time-reversal symmetry with $\mathcal{A}_1 = -0.01762$ ($z_1 = 6.01\sigma$) and $\mathcal{A}_2 = -0.03548$ vs IAAFT $-0.00011$ (**$z_2 = 8.14\sigma, p_{\text{Holm}} (pooled lens family) ≥ 0.005 — rejected$**), exposing asymmetric steep-attack / ring-down piezo-inductor impulse shapes.

---

### Discovery 4 (`Lens A4` — Non-Poisson 2D Blank-Wall Waves, Persistent Oxide-Trap Telegrapher Pixels, and UVC Multi-Pixel Bursts)
- **Textbook Prior Violated:** After subtracting both static per-pixel flat-field $\bar{I}(y,x)$ and every frame's horizontal row mean $\bar{I}(t,y)$ (removing rolling-shutter horizontal banding $k_x = 0$), CMOS blank-wall residuals should be spatially white and Gaussian/Poisson.
- **Observed Pattern (`67` Replicated Anomalies Across `IDLE, B, D, E1B, E2B`):**
  1. **2D Diagonal & Column Spatial Modes (`p_Holm = 0.00375`):** RGB `luma_Y` replicates non-horizontal 2D spatial Fourier peaks at $(k_y=1, k_x=18)$ ($\lambda_x = 35.56\text{ px}$, **$z_2 = 478.47\sigma$** in `IDLE`, $57.72\sigma$ in `B`), $(k_y=1, k_x=15)$ ($\lambda_x = 42.67\text{ px}$, **$z_2 = 417.38\sigma$** in `IDLE`, $57.87\sigma$ in `B`, **$270.33\sigma$ in linear `gamma=100` `E2B`**), and $(k_y=4, k_x=65)$ ($\lambda_x = 9.85\text{ px}, \lambda_y = 120\text{ px}$, **$z_2 = 398.33\sigma$**), while IR `LED_ON`/`LED_OFF` replicates vertical column modes $k_x \in \{1, 4, 7\}$ (**$z_2 = 16.83–892.65\sigma$**).
  2. **Persistent Random-Telegraph-Signal (RTS) Silicon Trap Pixels (`p_Holm = 0.00125`):** Selecting the top `0.05%` (`76–153` pixels) by excess kurtosis in Half 1 and evaluating **those exact pixel coordinates** in Half 2 confirms fixed bistable blinking pixels across both CMOS dies:
     - IR `LED_OFF` (`115` px): Half-2 locked excess kurtosis **`+8.59`** (`IDLE`, **$z_2 = 62.17\sigma$**) and **`+11.25`** (`E1B`, **$z_2 = 73.64\sigma$**) vs random-pixel mean `+0.25`.
     - IR `LED_ON` (`115` px): Half-2 locked excess kurtosis `+2.27` to `+7.96` (**$z_2 = 16.26–64.12\sigma$**).
     - RGB `luma_Y` (`153` px) & `chroma_Cb` (`76` px): Half-2 locked excess kurtosis `+3.47` to `+9.12` (**$z_2 = 5.57–44.31\sigma$**) and `+17.85` to `+20.57` (**$z_2 = 10.42–13.45\sigma$**).
  3. **Synchronized Multi-Pixel UVC Bursts (`p_Holm <= 0.0025`):** RGB exhibits simultaneous frame-wide $>4\sigma$ impulse bursts across `IDLE`, `B`, and linear `E2B` (**$z_2 = 4.70–9.36\sigma$**), whereas IR shows `0` replicated bursts (`z_2 = -0.45..+0.03`).
  4. **Diagnostic Resolution of Phase-D `LED_OFF` Variance (`203 DN²`):** Steady-state median-stratified `LED_OFF` stacks (`IDLE`, `B`, `E1B`, `E2B`, `150` frames each) show `0` inverted shot-noise anomalies (`inv = []`), proving that the high raw `ir_led_off` variance seen in short `90`-frame `Phase D`/`E1D` snapshots came from initial V4L2 auto-exposure startup frames rather than steady-state reverse shot noise.

---

### Discovery 5 (`Lens A5` — `-80 ms` Ultrasonic Acoustic Precursor Before `RAPL` Platform Telemetry & `psys_w` Firmware Rail Inversion)
- **Textbook Prior Violated:** Digital power counters (`RAPL`) are assumed to lead or coincide with downstream physical side-channels, and `psys` (`platform`) energy is textbook-defined as a superset of CPU `package` energy (`psys_w >= pkg_w`).
- **Observed Pattern (`p_Holm = 0.00375`):**
  1. **Acoustic Precursor Leading Kernel Telemetry by `80 ms` (`Phase E2A`):** Top-100 declustered innovation spikes in `dmic_ultrasonic_14_23k_log` **precede** `dark_w` (`psys_w - pkg_w`) spikes by **`80 ms` ($\tau = -0.080\text{ s}$)**: `36/100` coincidences in Half 1 ($z_1 = 7.83\sigma$) and **`38/100` in Half 2** vs circular-shift null `12.48` (**$z_2 = 7.12\sigma, p_{\text{Holm}} (pooled lens family) ≥ 0.005 — rejected$**). Physical cause: airborne ultrasonic waves from the discrete GPU VRM reach the microphones in `~0.25 ms`, whereas Embedded Controller (`EC`) updates to the `psys` register lag by `~80 ms` of firmware filtering.
  2. **`psys_w` Sub-Package Firmware Anomaly (`IDLE, A, B, C, E1, E2`):** Across all active and idle phases, `psys_w` reads `6.48–7.43 W` while `pkg_w` reads `54.8–68.1 W` (`dark_w \approx -52\text{ W}`), producing `75–99%` zero-lag rare-event lock between `pkg_w`/`core_w` and `dark_w` (**$z_2 = 16.99–40.53\sigma$**) because `psys` on this hardware measures an auxiliary/EC rail rather than total system power.

---

### Discovery 6 (`Lens A6` — Uninvited High-$Q$ Optical Rolling-Shutter Lines & Mechanical Fan/Clock Harmonics)
- **Textbook Prior Violated:** Outside `60 Hz` mains, `30 fps` frame combs, and injected prime stimuli, blank-wall CMOS row means and idle audio spectra should follow smooth continuous noise floors.
- **Observed Pattern (`22` Replicated Lines, `p_Holm <= 0.00375`):**
  1. **Uninvited `~1 kHz` High-$Q$ Oscillators in `IDLE` IR Rolling-Shutter (`10.8 kHz`):** During untouched `IDLE`, `ir_row_osc_10800hz_led_on` exhibits a sharp line at **`1,048.1 -> 1,049.4 Hz`** ($Q = 198.8$, `8.20×` median, **$z_2 = 17.32\sigma, p_{\text{Holm}} = 0.0025$**), while `ir_row_osc_10800hz_led_off` exhibits **`932.1 -> 930.8 Hz`** ($Q = 235.7$, `8.49×` median, **$z_2 = 15.90\sigma, p_{\text{Holm}} = 0.0025$**, temperature correlation $r = +0.5062$), and `E1B` `LED_OFF` exhibits **`688.2 -> 689.5 Hz`** ($Q = 74.6$, **$z_2 = 11.67\sigma, p_{\text{Holm}} = 0.0025$**, $r = -0.4223$), plus the `30.32–31.64 Hz` unique-frame strobe beat (**$z_2 = 188.79–893.15\sigma$**).
  2. **DMIC Aeroacoustic Shaft & Blade-Pass Lines (`A, B, E2`):** `79.10 Hz` ($Q = 9.0$, `73.15×` median, **$z_2 = 137.80\sigma, p_{\text{Holm}} (pooled lens family) ≥ 0.005 — rejected$** — exact `4,746 RPM / 60` CPU fan shaft rate), `380.86 Hz` and `401.37 Hz` ($Q = 14.6–65.0$, **$z_2 = 13.03–40.75\sigma$** — 5th-harmonic blade-pass tones), and `143.55–146.48 Hz` (`82.9×` median, **$z_2 = 223.17\sigma$** in `E2A`). *(At borderline `p_Holm = 0.0050` with $m=4$ locked bins, `IDLE` also shows an exact `48,000 / 3 = 15,999.02 Hz` clock sub-harmonic at $Q = 1,820.3, z_2 = 48.53–53.59\sigma$ across mics and a `60 Hz`-split `1,889.65 / 1,949.41 Hz` pair at $Q = 358–369, z_2 = 31.50–53.93\sigma$ in RGB `14.4 kHz` row readout.)*

---

### Discovery 7 (`Lens A7` — Zero-Correlation Non-Linear Copula Mutual Information Beyond Multi-Lag Linear Schur Orthogonalization)
- **Textbook Prior Violated:** After projecting out all linear multi-lag (`lags = -2..+2`) cross-modal predictors (`H5` linear Schur complement), Gaussian/linear cross-sensor residuals should be mutually independent ($\mathrm{MI} = 0$).
- **Observed Pattern (`p_Holm = 0.00375`):**
  - **`E1A` (`dmic_ultrasonic_14_23k_log` $\leftrightarrow$ `uncore_w`):** Residual linear correlation is near zero ($r = -0.0945$), yet rank-copula $\mathrm{MI}_1 = 0.11758\text{ nats}$ ($z_1 = 56.24\sigma$) and $\mathrm{MI}_2 = \mathbf{0.05283\text{ nats}}$ vs IAAFT $0.00418\text{ nats}$ (**$z_2 = 24.45\sigma, p_{\text{Holm}} (pooled lens family) ≥ 0.005 — rejected$**).
  - **`E2A` (`dmic_crest_factor` $\leftrightarrow$ `uncore_w`):** Residual linear correlation is $r = -0.0550$, yet $\mathrm{MI}_1 = 0.02377\text{ nats}$ ($z_1 = 11.68\sigma$) and $\mathrm{MI}_2 = \mathbf{0.02431\text{ nats}}$ vs IAAFT $0.00385\text{ nats}$ (**$z_2 = 11.01\sigma, p_{\text{Holm}} (pooled lens family) ≥ 0.005 — rejected$**).
  - **`C, E1A, E2A` (`core_w` $\leftrightarrow$ `uncore_w`):** Strong curved power-budget allocation boundary ($\mathrm{MI}_2 = 0.0913–0.1272\text{ nats}$, **$z_2 = 22.07–50.21\sigma, p_{\text{Holm}} (pooled lens family) ≥ 0.005 — rejected$**).

---

## 3. Reproducible Verification Commands

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES="" \
  python3 -I -B track-s113-multisensor-silicon-physics/test_s113_blind_anomaly_hunter.py

OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES="" \
  python3 -B track-s113-multisensor-silicon-physics/s113_blind_anomaly_hunter.py \
  --track-dir track-s113-multisensor-silicon-physics --phases IDLE A B C D E1 E2
```
