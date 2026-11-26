# Preregistration Amendment `PREREG-S113-AMENDMENT1`: Model-Free Blind Residual & Non-Textbook Pattern Discovery (`SOP-12`)

- **Parent Protocol (Immutable):** `PREREG-S113` (`cebe48326461ef048c6e8ccfb51f76f661f33b44c32d7e0178777d2ad8221e67`)
- **PI Motivation (`2026-11-25T13:55:13Z`):** *"look for patterns in the data that dont make sense to what you have been trained to know - that is where discovery lies"*
- **Methodological Safeguard (Law 1 + Law 3 + anti-`CS-09`):** Exploratory anomaly hunting MUST NOT degenerate into cherry-picking noise. Every blind discovery lens below runs **split-half / out-of-sample replication** (discover on odd blocks / first half -> verify on held-out even blocks / second half!) AND compares against **matched IAAFT surrogates (`N >= 200`, preserving exact power spectrum and marginal amplitude distribution)** and **interleaved `IDLE` controls** (`p < 0.005` Holm-corrected). Any surviving anomaly MUST trigger **Law-1 Adaptive Phase-E Re-Entry** before the hard `2026-11-25T14:44:00Z` sensor shutoff to confirm physical reproducibility on fresh data!

---

## Seven Model-Free "Beyond-Textbook" Discovery Lenses (`A1`–`A7`)

1. **`A1` — Higher-Order Non-Linear Coupling (Bicoherence $b^2(f_1, f_2)$ & Cross-Frequency Phase-Amplitude Coupling):**
   - Textbook linear systems have zero bicoherence and zero phase-amplitude coupling. Scan all `4-ch` DMIC (`0–24 kHz`), `IR` row-oscilloscope (`0–5.4 kHz`), and `RGB` row-oscilloscope (`0–7.2 kHz`) for quadratic phase locking ($f_3 = f_1 + f_2$), parametric sub-harmonics ($f_0/2, f_0/3$), and slow-to-ultrasonic modulation exceeding `N = 200` IAAFT surrogates.
2. **`A2` — Chiral / Non-Reciprocal `4×4` Cross-Spectral Circulation ($\operatorname{Im} S_{ij}(f)$ & Effective Rank $> 1$):**
   - Common-mode EMI is strictly real rank-1 ($\operatorname{Im} S_{ij} \equiv 0$). Measure the skew-symmetric imaginary cross-spectrum $\operatorname{Im} S_{ij}(f)$, rotational circulation $\sum \operatorname{Im} S_{ij}$, and effective participation ratio $\mathrm{PR}(f) = (\operatorname{tr} S)^2 / \operatorname{tr}(S^2)$ across `0–24 kHz` to detect unexpected helical/circulating or multi-source spatial eigenmodes.
3. **`A3` — Time-Reversal Asymmetry $\mathcal{A}(\tau)$ & ON-vs-OFF Step Hysteresis / Afterglow Memory:**
   - Compute exact time-reversal asymmetry $\mathcal{A}(\tau) = \langle x(t)^2 x(t+\tau) - x(t) x(t+\tau)^2 \rangle / \sigma^3$ and asymmetric step-response difference (`ON-edge` minus time-reversed `OFF-edge`) plus post-load memory persistence (`0.1 s` to `15 s` after stimulus shuts off) across DMIC, IR, RGB, and `PSys - Pkg`.
4. **`A4` — 2D Blank-Wall Non-Poisson & Spatio-Temporal Wave Violations (`IR` `640×360` & `RGB` `640×480`):**
   - After subtracting static per-pixel flat-field $\bar{I}(y,x)$ and per-frame horizontal row mean $\bar{I}(t, y)$, textbook CMOS noise must be spatially & temporally white. Scan raw 2D residuals in `local_raw_av/` for: (i) non-horizontal 2D spatial Fourier peaks $P(k_x, k_y)$ (diagonal/column/checkerboard/traveling waves), (ii) anomalous spatial Fano-factor ($\mathrm{Var}/\mathrm{Mean}$) & excess-kurtosis clusters, and (iii) correlated multi-pixel impulse bursts across IR and RGB.
5. **`A5` — Zero-Filter Cross-Modal Rare-Event Coincidence (Including Negative Precursor Lags $\tau < 0$):**
   - Independently extract the top-100 highest-$|z|$ unexpected outlier timestamps in EACH modality (`4-ch DMIC`, `IR`, `RGB`, `RAPL_pkg`, `PSys-Pkg`, `BAT0`, `IIO`) with zero frequency assumptions; compute cross-event coincidence curves across $\tau \in [-2.0\text{ s}, +2.0\text{ s}]$ against circular-shift surrogates to expose unexpected coupling OR precursor events where one sensor reacts BEFORE `RAPL` reports power change.
6. **`A6` — Blind Uninvited Spectral Lines, Drifting Chirps & Non-Harmonic Ratios:**
   - Full-resolution spectral peak finder across `0–24 kHz` (DMIC), `0–5.4 kHz` (IR), and `0–7.2 kHz` (RGB) during BOTH pure `IDLE` and active runs, flagging every high-$Q$ line NOT attributable to `60 Hz` mains, `30 fps` video frame rate, or injected prime stimuli, and tracking whether its frequency drifts with temperature, voltage, or load.
7. **`A7` — Non-Linear Predictability / Recurrence & Cross-Modal Transfer Entropy Beyond Linear Covariance:**
   - After OLS-removing all linear cross-modal predictions (including `H5` Schur complement), test post-textbook residuals for remaining rank-copula mutual information, nearest-neighbor delay-embedding predictability, and recurrence determinism exceeding `N = 200` IAAFT surrogates.

---

## Adaptive Phase-E Re-Entry Rule (`<= 2026-11-25T14:44:00Z`)
Any anomaly surviving BOTH split-half replication AND `N >= 200` IAAFT/circular-shift null (`p < 0.005`) immediately triggers a targeted **Phase-E Confirmatory Probe** inside the live 1-hour sensor window (varying the suspected physical parameter — e.g. display brightness, Wi-Fi/USB load, core-ID pinning, exposure time, or pure silent dark/idle control — to distinguish real physical phenomena from instrument/driver quirks) BEFORE hard sensor shutoff at `14:44:00Z`!
