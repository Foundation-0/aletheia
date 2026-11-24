# Track S53 — Beyond-Language Raw Physical Sensor Tomography on Living Silicon (Phases 1 & 2)

> **Epistemic & Verification Contract:** Every algebraic invariant in the core extractor and independent zero-shared-code verifier (`sensor_tomography_audit.py`) is computed strictly in exact pure-$\mathbb{Z}/\mathbb{Q}$ arithmetic (`oracle_class = "exact"`, zero floating-point operations in the verifier, zero human channel labels or physical units exposed to Stage A/B). Matched IAAFT surrogate ensembles (`numpy`) and live physical sensor measurements are explicitly segregated under `oracle_class = "sampled"` / empirical `N1`. All negative/null outcomes are reported verbatim alongside positive discoveries.

---

## 1. Executive Summary & Strict Privacy Architecture

Can Aletheia's pure-$\mathbb{Z}/\mathbb{Q}$ operator calculus — specifically Schur pushforward (`⧄`), dark-mode shadow elimination (`⧅`), Bareiss–Sylvester inertia (`⦺`), blind modularity graph partitioning, time-reversal asymmetry, and SI-2019 Landauer erasure bounds — recover the real hardware topology, hidden power reservoirs, and thermodynamic arrow of time of a live computer **directly from anonymous integer sensor streams $X \in \mathbb{Z}^{T \times D}$ with zero language tokens, zero labels, and zero units**?

We executed **three live multi-channel captures** on bare-metal `UX582HS` silicon (`Intel i9-11900H` 8C/16T + `NVIDIA RTX 3080` `GA104M`), progressing across two strictly separated phases:

1. **Phase 1A — Pre-RAPL Passive Baseline (`pre_rapl_baseline_snapshot.json` $\to$ `pre_rapl_baseline_certificate.json`):** `48` raw channels (`26` dynamic, `22` zero-variance) sampled at `2 Hz` (`190` samples, `94.53 s`), reading `hwmon*`, `thermal_zone*`, `cpufreq`, `iio:device0` 3-axis hinge, and line-buffered `nvidia-smi`. **Zero microphone, zero camera, zero `sudo`.** Intel RAPL `energy_uj` counters were unreadable during this capture, creating a natural hidden-variable ("dark-mode") ablation baseline.
2. **Phase 1B — Post-RAPL Passive Tomography (`raw_sensor_snapshot.json` $\to$ `sensor_tomography_certificate.json`):** `53` raw channels (`36` dynamic, `17` zero-variance) at `2 Hz` (`190` samples, `95.04 s`), adding all `5` newly readable `intel-rapl*` per-step $\Delta E\ (\mu\text{J})$ domains (`package-0`, `mmio:package-0`, `core`, `uncore`, `psys`). **Zero microphone, zero camera, zero `sudo`.**
3. **Phase 2 — Controlled 4-Regime Acoustic + RAPL + Hysteresis Tomography (`phase2_controlled_snapshot.json` $\to$ `phase2_controlled_certificate.json`):** `60` raw channels (`48` dynamic, `12` zero-variance) at `4 Hz` (`240` frames, `60.07 s`), pairing all sysfs/RAPL/GPU telemetry with `7` coarse non-reconstructible `250 ms` acoustic power-band summaries extracted from a strictly time-bounded, explicitly authorized `48 kHz` mono audio capture (`ZERO` camera access, `ZERO` `sudo`), structured into four `15 s` controlled physical regimes:
   - **`R0` (`0–15 s`):** Ambient quiet baseline (recording room noise covariate `room_quiet_with_distant_second_laptop_fan_across_room`).
   - **`R1` (`15–30 s`):** Reversible-analog (`qfree`-like) L1-resident bijective Feistel compute loop.
   - **`R2` (`30–45 s`):** Irreversible-analog (`mfree`-like) 6-worker L3 cache overwrite / erasure workload.
   - **`R3` (`45–60 s`):** Stimulus halted at `45.0 s`; passive thermal/mechanical relaxation & EC fan-hysteresis tail.

### Privacy & Data-Handling Boundary (Enforced Fail-Closed by Verifier)
- **Zero Camera Access:** `camera_accessed = false` across every capture; `sensor_tomography_audit.py` unconditionally rejects any snapshot with `camera_accessed != False` or `sudo_used != False`.
- **Strict Local Isolation of Raw Audio:** The raw `60.01 s` `48 kHz` mono PCM file (`5,761,068` B) resides strictly inside a `0700` local-only directory (`local_raw_av/`, file mode `0600`) and is **never** committed, archived, or exported. The public snapshot (`phase2_controlled_snapshot.json`, `0600`) stores **only** `7` coarse `250 ms` integer band-energy/centroid summaries (`ac_rms_sq_0p01`, `20–100 Hz`, `100–500 Hz`, `500–2000 Hz`, `2–6 kHz`, `6–20 kHz`, `ac_spectral_centroid_hz`), from which speech or waveform reconstruction is mathematically impossible.

---

## 2. Stage A — Label Stripping & Exact Affine + Permutation Gauge Invariance (`exact`)

Before any invariant is computed, Stage A discards every channel name, sysfs path, and physical unit, retaining only $X \in \mathbb{Z}^{T \times D}$. Zero-variance channels ($\min_t X_{tj} = \max_t X_{tj}$) are dropped strictly by algebraic invariance. On the remaining dynamic matrix $X_{\mathrm{dyn}} \in \mathbb{Z}^{T \times D_{\mathrm{dyn}}}$, we apply a seeded random column permutation $\pi \in S_{D_{\mathrm{dyn}}}$ and independent positive rational affine rescalings $x'_j = a_j x_{\pi(j)} + b_j$ ($a_j \in \mathbb{Q}_{>0},\, b_j \in \mathbb{Q}$), verifying exact bit-for-bit invariance across all Stage-B operators (`R^2`, regularized precision partial correlation `P^2`, blind modularity cluster partition `ARI`, Schur dark-mode `eta`/`rho^2`/`PR`, and lagged time-reversal asymmetry `A^2`/`Gamma`):

| Capture | $T$ | $D_{\mathrm{tot}}$ | $D_{\mathrm{dyn}}$ | $\max|\Delta R^2|$ | $\max|\Delta P^2|$ | Gauge Cluster `ARI` | Schur & Asymmetry Gauge Match |
| :--- | ---: | ---: | ---: | :---: | :---: | :---: | :---: |
| **Phase 1A (Pre-RAPL)** | `190` | `48` | `26` | `0` | `0` | `1` | `True` / `True` |
| **Phase 1B (Post-RAPL)** | `190` | `53` | `36` | `0` | `0` | `1` | `True` / `True` |
| **Phase 2 (4-Regime Audio+RAPL)** | `240` | `60` | `48` | `0` | `0` | `1` | `True` / `True` |

All Stage-B reductions onto the exact $10^{-12}$ integer tick lattice `_q12_ticks(v) = (v.numerator * 10^12) // v.denominator` eliminate coprime-denominator blowup while preserving zero-float exactness and `100.0%` gauge invariance.

---

## 3. Natural Pre-RAPL $\to$ Post-RAPL $\to$ Phase 2 `⧅` Dark-Mode Schur Ablation

Conditioning all thermal channels $A$ (`cpu_die_thermal`, `chassis_acpi_thermal`, `nvme_thermal`) on measured non-thermal driver channels $B$ via the exact pure-$\mathbb{Q}$ ridge-regularized Schur complement
$$S_{A|B} = \Sigma_{AA} - \Sigma_{AB}\bigl(\Sigma_{BB} + \lambda\,\mathrm{diag}(\Sigma_{BB})\bigr)^{-1}\Sigma_{BA}, \quad \lambda = \frac{1}{20},$$
yields a direct empirical test of Aletheia's off-brane dark-mode shadow operator (`⧅` / `⦺`). When an actual physical energy reservoir (`intel-rapl` electrical watts) is unmeasured, $S_{A|B}$ must retain high unexplained variance $\bar{\eta} = \frac{1}{|A|}\sum_i (S_{A|B})_{ii}/\Sigma_{ii}$ and high off-diagonal residual correlation $\overline{\rho^2}_{ij|B}$; unveiling the hidden sensor bus must collapse both:

| Capture | Physical Partition $\|A\| \mid \|B\|$ | Bareiss Inertia $(n_+, n_0, n_-)$ | Mean Unexplained Thermal Variance $\bar{\eta}$ | Raw Off-Diag $\overline{R^2}_{AA}$ | Residual Schur $\overline{\rho^2}_{AA\|B}$ | Off-Diag Reduction | Blind $Q_{P^2}$ / Held-Out `ARI` ($P^2$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Phase 1A (Pre-RAPL)** | `14 \| 12` | `[13, 1, 0]` | **`89.67%`** (`0.896680`) | `0.072903` | `0.070557` | `-3.2%` | `0.5571` / `0.3145` |
| **Phase 1B (Post-RAPL)** | `17 \| 19` | `[16, 1, 0]` | **`65.69%`** (`0.656927`) | `0.116229` | `0.060024` | **`-48.4%`** | **`0.7071` / `0.3925`** |
| **Phase 2 (Audio+RAPL)** | `20 \| 28` | `[17, 3, 0]` | **`58.74%`** (`0.587383`) | `0.088872` | **`0.040938`** | **`-53.9%`** | `0.6452` / `0.3680` |

### Key Blind Structural Recoveries (Zero Labels Exposed to Extractor)
1. **Unveiling `intel-rapl` Explains `-23.98` pp of Hidden Thermal Variance:** Adding the `5` unlocked `intel-rapl*` $\mu\text{J}$ channels drops unexplained thermal variance from `89.67%` to `65.69%` (and to `58.74%` under Phase 2 controlled excitation + acoustic sensing) while slashing off-diagonal residual thermal covariance reduction from `-3.2%` to `-48.4%` / `-53.9%`.
2. **Exact Nullspace Unmasking of Linux Sysfs Duplicates (`⦺`):** Exact Bareiss inertia blindly flagged `[13, 1, 0]` (`n_0 = 1`) in Phase 1A, `[16, 1, 0]` (`n_0 = 1`) in Phase 1B, and `[17, 3, 0]` (`n_0 = 3`) in Phase 2 — detecting exact rank-deficient duplicate kernel sensors (`hwmon1/acpitz == thermal_zone0/acpitz`, plus additional linearly dependent ACPI/NVMe channels in Phase 2) purely from integer covariance algebra.
3. **100%-Pure Blind Hardware Sub-Bus Discovery (`clP2`):** With zero human labels, blind pure-$\mathbb{Q}$ modularity clustering on precision partial correlation $P^2$ in Phase 1B (`Q_P2 = 0.7071`, `ARI_P2 = 1108/2823 = 0.3925`) isolated:
   - **`clP2=1` (`5/5` exact):** All `5` `intel-rapl*` $\mu\text{J}$ domains (`mmio:package-0`, `package-0`, `core`, `uncore`, `psys`) with `100%` precision and `100%` recall.
   - **`clP2=5` (`2/2` exact):** `{cpu_fan, gpu_fan}` mechanical cooling loop.
   - **`clP2=2` (`3/3` exact):** `{gpu_power_cW, gpu_clock_sm_MHz, gpu_clock_mem_MHz}` GPU electromechanical bus.
   - **`clP2=3, 4, 6` (`2/2` each):** Exact duplicate/paired chassis thermal zones (`{iwlwifi_1}`, `{TCPU, x86_pkg_temp}`, `{acpitz}`).

---

## 4. Blind Thermodynamic Polarity ($\Phi_i$) & Exact SI-2019 Landauer Erasure Bridge

For lag $\tau$, let $C_{ij}(\tau) = \frac{1}{T-\tau}\sum_{t=0}^{T-\tau-1} z_{ti} z_{t+\tau, j}$ be the centered lagged cross-covariance, $\mathcal{A}^2_{ij}(\tau) = \frac{(C_{ij}(\tau) - C_{ji}(\tau))^2}{\Sigma_{ii}\Sigma_{jj}}$, $\mathrm{dir}_{ij}(\tau) = \mathrm{sgn}(C_{ij}(\tau) - C_{ji}(\tau))$, and net blind source/sink flow $\Phi_i(\tau) = \frac{1}{D-1}\sum_{j \ne i}\mathrm{dir}_{ij}(\tau)\,\mathcal{A}^2_{ij}(\tau)$.

### 4.1 Blind Second-Law Separation (Phase 1B Post-RAPL, $\tau = 2$ / `1.0 s`)
Ranked purely by anonymous $\Phi_i(\tau=2)$ without seeing a single label:
- **Top 5 Blind Sources ($\Phi_i > 0$, `5/5` Electrical Clocks / RAPL Energy):**
  1. `cpu_core5_freq_kHz` (`+0.008230`)
  2. `cpu_core7_freq_kHz` (`+0.006980`)
  3. `cpu_core0_freq_kHz` (`+0.004108`)
  4. `intel-rapl:1:psys_dE_uJ` (`+0.003169`)
  5. `intel-rapl:0:0:core_dE_uJ` (`+0.003106`)
- **Top 5 Blind Sinks ($\Phi_i < 0$, `5/5` Silicon Die / NVMe Thermal Sensors):**
  1. `Core 5` (`-0.006506`)
  2. `Core 7` (`-0.005495`)
  3. `Core 0` (`-0.004454`)
  4. `NVMe Sensor 2` (`-0.004079`)
  5. `Core 2` (`-0.003899`)

### 4.2 Exact Pure-$\mathbb{Q}$ SI-2019 Landauer Thermodynamic Erasure Bridge (`Track S38`)
Using the exact 2019 SI Boltzmann constant $k_B = 1380649 \times 10^{-29}\text{ J/K}$ and rigorous rational $\ln 2$ brackets $\frac{693147180559}{10^{12}} < \ln 2 < \frac{693147180560}{10^{12}}$, the package RAPL dissipation $E_{\mathrm{pkg}}$ at mean package die temperature $\bar{T}_{\mathrm{pkg}}$ maps to an exact integer bracket $[N_{\mathrm{lo}}, N_{\mathrm{hi}}]$ of Landauer-equivalent erased bits $N = E_{\mathrm{pkg}} / (k_B \bar{T}_{\mathrm{pkg}} \ln 2)$:

| Capture (`intel-rapl:0`) | Duration | Total Energy $E_{\mathrm{pkg}}$ | Mean Power | Mean Die Temp $\bar{T}_{\mathrm{pkg}}$ | Exact Landauer-Equivalent Erased Bits $[N_{\mathrm{lo}}, N_{\mathrm{hi}}]$ | `S38` `qfree` / `mfree` Reference |
| :--- | ---: | ---: | ---: | ---: | :--- | :--- |
| **Phase 1B (Post-RAPL)** | `95.037 s` | `5,739,791,702 uJ` (`5,739.79 J`) | `60.395 W` | `365.913 K` (`92.76°C`) | `[1639114762572878216469658, 1639114762575242959209074]` (`1.639e24` bits) | `qfree = 0`; `mfree AND in [19/16, 6/5]` bits |
| **Phase 2 (4-Regime)** | `60.066 s` | `4,199,960,562 uJ` (`4,199.96 J`) | `69.922 W` | `365.017 K` (`91.87°C`) | `[1202330249891633791804104, 1202330249893368387693137]` (`1.202e24` bits) | `qfree = 0`; `mfree AND in [19/16, 6/5]` bits |

---

## 5. Phase 2 — Controlled 4-Regime Acoustic + RAPL + Thermal Hysteresis Tomography

Under the authorized `60.07 s` controlled 4-regime protocol (`240` frames @ `4 Hz`, `48` dynamic channels), we directly separated stationary room-background noise from local electrical-mechanical-acoustic coupling:

| Channel | `R0` Quiet (`0–15 s`) | `R1` L1 Feistel (`15–30 s`) | `R2` L3 Erasure (`30–45 s`) | `R3` Relaxation (`45–60 s`) | `R3 / R0` Ratio | Physical Role |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| `intel-rapl:0` (pkg) | `62.81 W` | `69.86 W` | **`77.87 W`** | `69.45 W` | `1.11×` | Direct CPU electrical drive (`+15.06 W` peak in `R2`) |
| `intel-rapl:1` (`psys`) | `4.37 W` | `5.86 W` | `6.71 W` | **`7.45 W`** | `1.71×` | Whole-platform electrical bus |
| `TCPU` | `92.15°C` | `93.17°C` | `91.88°C` | `90.73°C` | `0.98×` | Die temperature (cools during `R3`) |
| `cpu_fan` | `3,331.7 RPM` | `3,315.0 RPM` | `3,333.3 RPM` | **`3,915.0 RPM`** | `1.18×` | Delayed EC hysteresis fan surge (`+582 RPM` in `R3`) |
| `gpu_fan` | `3,306.7 RPM` | `3,320.0 RPM` | `3,311.7 RPM` | **`3,836.7 RPM`** | `1.16×` | Coupled chassis cooling surge in `R3` |
| `ac_band_20_100hz` | `38.77 M` | `40.03 M` | `41.41 M` | `41.32 M` | **`1.07×` (flat)** | **Distant second-laptop fan + room AC floor (`44–60 Hz`)** |
| `ac_band_500_2000hz` | `13.89 M` | `14.99 M` | `13.41 M` | **`28.67 M`** | **`2.06×` (`+3.15 dB`)** | Airflow broadband band (`cpu_fan` peak `r = +0.7928` @ `-0.25 s`) |
| `ac_band_2k_6khz` | `2.32 M` | `2.88 M` | `2.64 M` | **`8.53 M`** | **`3.68×` (`+5.66 dB`)** | Blade-pass / turbulence band (`cpu_fan` peak **`r = +0.9456`** @ `-0.50 s`) |
| `ac_band_6k_20khz` | `4.95 M` | **`37.01 M` (`7.47×`)** | **`37.79 M` (`7.63×`)** | **`59.31 M`** | **`11.98×` (`+10.78 dB`)** | High-band local signature (`psys` **`r = +0.7789`** @ lag `0.00 s`!) |
| `ac_spectral_centroid_hz` | `1,362.9 Hz` | `3,812.5 Hz` | `4,816.3 Hz` | **`6,160.0 Hz`** | **`4.52×`** | Monotonic spectral shift across all four regimes |

### Three Blind Multi-Modal Findings in Phase 2
1. **Clean Spectral Rejection of Ambient Distant Fan:** The distant second laptop's fan remains anchored in the stationary `20–100 Hz` band (`44–60 Hz` peaks, `1.07×` across `R0..R3`), while local compute and cooling responses emerge cleanly at `>500 Hz` (`+3.15 dB` to `+10.78 dB`).
2. **Blind Precision Graph Locks Platform Power to `6–20 kHz` Ultrasound & Fans to `2–6 kHz`:** Without labels, `clP2=2` (`n=5`) grouped `intel-rapl:1:psys_dE_uJ` directly with `{ac_rms_sq, ac_band_20_100hz, ac_band_6k_20khz, ac_spectral_centroid_hz}` (`r = +0.7789` at lag `0.00 s`, surging `7.47×` in `R1` while fans were still flat at `3,315 RPM`), while `clP2=1` (`n=10`) locked `ac_band_2k_6khz` directly onto `{cpu_fan, gpu_fan, power1_input, gpu_power_cW, gpu_temp_C}` (`r = +0.9456`, with the microphone leading the ACPI EC tachometer update by `250–500 ms`!).
3. **Macroscopic Hysteresis & `3.0 s` Cooling Arrow:** After stimulus halted at `45.0 s`, delayed EC fan acceleration drove `ac_band_2k_6khz` (`3.68×`) and `ac_band_6k_20khz` (`11.98×`) peaks during `R3` while `TCPU` fell — appearing directly in Stage-B's `tau = 12 (3.0 s)` top time-reversal arrows: `gpu_fan -> acpitz` (`A^2 = 0.2254`), `ac_band_2k_6khz -> acpitz` (`A^2 = 0.2136`), `cpu_fan -> acpitz` (`A^2 = 0.2132`), and `ac_band_500_2000hz -> acpitz` (`A^2 = 0.1718`).

---

## 6. Adversarial Null Calibration & Law-5 Non-Commutativity Obstruction

Every capture was evaluated against two matched surrogate nulls (`N = 200` each): (1) exact pure-$\mathbb{Q}$ per-channel circular shift (`oracle_class = "exact"`), preserving exact marginals and per-channel autocorrelation; and (2) `numpy` IAAFT (`30` iterations, `oracle_class = "sampled"`), preserving exact amplitude spectra and marginals, plus out-of-sample split-half replication:

| Capture | Obs $\overline{R^2}$ | Circ-Shift $p(\overline{R^2})$ | IAAFT $p(\overline{R^2})$ & $z^2$ (`z`) | Blind Cluster `ARI` Null $p$ | Obs $\overline{\mathcal{A}^2}(1\text{ s})$ | Circ-Shift $p(\overline{\mathcal{A}^2})$ | Split-Half Top-10 Arrow Concordance |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Phase 1A (Pre-RAPL)** | `0.028367` | **`1/201`** | **`1/201`**, `1090.91` (`+33.03 sigma`) | **`1/201`** | `0.010656` | `190/201` *(null)* | `3/10` (`0.30`) |
| **Phase 1B (Post-RAPL)** | `0.089624` | **`1/201`** | **`1/201`**, `1642.44` (`+40.53 sigma`) | **`1/201`** | `0.005806` | `191/201` *(null)* | `4/10` (`0.40`) |
| **Phase 2 (4-Regime)** | `0.099362` | **`1/201`** | **`1/201`**, `892.59` (`+29.88 sigma`) | **`1/201`** | `0.006182` | `1` *(null)* | **`7/10` (`0.70`)** |

### Explicit Law-5 Obstruction — Why Global Scalar $\overline{\mathcal{A}^2}(1\text{ s})$ Fails Null Rejection While Localized Arrows Replicate
Global all-pairs coupling $\overline{R^2}$ and blind hardware-topology clustering `ARI` decisively reject both exact circular-shift and sampled IAAFT nulls (`p = 1/201`, `+29.88` to `+40.53 sigma`) across all three captures. **In honest contrast**, global mean time-reversal asymmetry $\overline{\mathcal{A}^2}(1.0\text{ s})$ **does not beat** circular-shift or IAAFT nulls in any capture (`p = 190/201`, `191/201`, and `1` — in Phase 2, observed `0.006182` is strictly *below* the circular-shift null mean `0.008456`!).

The physical mechanism behind this obstruction is concrete: tightly coupled hardware blocks (8 CPU cores, 5 RAPL domains, 7 acoustic bands) co-move largely **synchronously** ($C_{ij}(\tau) \approx C_{ji}(\tau) \gg 0$), making their global antisymmetric residual *smaller* than independent circularly wrapped non-stationary ramps (which manufacture large artificial lag offsets when `R3` wraps onto `R0`). Meanwhile, real physical irreversibility concentrates into **targeted cross-domain arrows** — evidenced by `5/5` electrical-source vs. `5/5` thermal-sink $\Phi_i$ polarity in Phase 1B, `8.15×` growth of $\overline{\mathcal{A}^2}(\tau)$ from `tau = 0.25 s` (`0.002118`) to `tau = 3.0 s` (`0.017265`, `max = 0.2254`) matching the physical fan-hysteresis timescale, and split-half top-10 arrow sign concordance jumping from `3/10` (stationary Pre-RAPL) to **`7/10`** (controlled Phase 2). Global scalar averaging does not commute with localized physical dissipation.

---

## 7. Verification Receipts & Frozen Public Manifest

### Verification Commands (3-Mode Isolated Parity)
```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -I -B sensor_tomography_audit.py --self-test
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -I -O -B sensor_tomography_audit.py --self-test
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -I -B -W error sensor_tomography_audit.py --self-test
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -I -B sensor_tomography_audit.py --raw raw_sensor_snapshot.json --check sensor_tomography_certificate.json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -I -B sensor_tomography_audit.py --raw phase2_controlled_snapshot.json --check phase2_controlled_certificate.json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -I -B test_sensor_tomography_r5.py
```

### Verification Gate Summary
- **3-Mode Isolated Parity (`-I -B`, `-I -O -B`, `-I -B -W error`):** Bit-identical across all 3 isolated modes:
  - `--self-test`: `45b643d7b564cec3d98d752ba5f673a8dfec7c15c30c97b697d70fa35d4a0159` ×3
  - `--check pre_rapl_baseline_certificate.json`: `00841415bbdcf860c9f4dffa438e2bb8ff46fc14692ed991ff5815f13883ff7b` ×3
  - `--check sensor_tomography_certificate.json`: `2daaae02d5ad48fdf5e8517c9f0adf8e698f1caec0967ebfd4dab83a61871779` ×3
  - `--check phase2_controlled_certificate.json`: `20c9cefe662426c8d9caa5ea88b45131efe90ee099605ee072ee3b895ad87d4a` ×3
  - `test_sensor_tomography_r5.py`: **`9/9 OK`** across all 3 isolated modes (`-I -B`, `-I -O -B`, `-I -B -W error`), `PYTHONHASHSEED=42 -B`, and `umask 077` (`0` bare `assert`s, `0` AST floats / `float()` calls in `sensor_tomography_audit.py` & `test_sensor_tomography_r5.py`).
- **Live Mutation, Whole-File AST `BoolOp`, & 4-Surface Zone-B Fuzzer (`sensor_tomography_audit.py`):**
  - Official live `aletheia mutate --guards require_ok --workers 4 --timeout 180 --max-mutants 0`: **`200/200` killed (`100.0%`, `KILLED=200`, `TIMEOUT=0`, `survived=0`, `truncated=False`)**.
  - Exhaustive whole-file DFS AST `BoolOp` (`OP_SWAP + SUBCOND_DEL`, `timeout=180`): **`72/72` killed (`100.0%`, `24` nodes, `69` non-timeout kills + `3` genuine infinite-loop timeouts on community-merge `L511`, `surv=[]`)**.
  - 4-Surface v2.1 `zone_b_fuzzer`: **`82/82 PASS`** (`25/25` CLI + `19/19` `VCD_CERT` + `19/19` `VCD_RAW` + `19/19` `VCD_PAYLOAD`, `bypasses=0`, `crashes=0`).
- **Public Hygiene & Safety Scan:** Isolated `0o700` public-manifest `aletheia audit-check --strict-ancestors --safety-scan --scripts sensor_tomography_audit.py test_sensor_tomography_r5.py` **`PASS`** (`11` public files, `2/2` R4 parity, `0` findings, `0` leaks, `0` bare `assert`s, `0` CRLF, `PYC=0`; private `local_raw_av/` verified `0o700` dir / `0o600` `.wav`, excluded from public manifest).

### Frozen Public File Manifest (Private `local_raw_av/` Excluded & Never Committed)
| File | Lines | Bytes | Mode | SHA-256 |
| :--- | ---: | ---: | :---: | :--- |
| `sensor_tomography_probe.py` | `1,571` | `65,224` | `0o644` | `a30f6bea7a3b27c1bf98aa1d1a4bdb21f734e869b1eb8fc506aff9300b590002` |
| `phase2_controlled_capture.py` | `534` | `21,068` | `0o644` | `b379124b7771611aedfad9f6a87258c3fcae44ab1102c0864a760e2645b0c319` |
| `sensor_tomography_audit.py` | `1,213` | `54,969` | `0o644` | `fa894bad62e4bb0a10f798dac4ed54b8fdc7cf1da314749894b16e71330341c6` |
| `test_sensor_tomography_r5.py` | `1,027` | `61,373` | `0o644` | `ff8ba6333d5ce0ca8fbe7fa87a1d40c8170c2afcb31b14b0c5c37dcc0747a7ad` |
| `pre_rapl_baseline_snapshot.json` | `1` | `56,524` | `0o600` | `510a9a76a876e7b359203514cc09190147ef21a30a774b5176cdc8a1e0cd9b71` |
| `pre_rapl_baseline_certificate.json` | `1` | `18,065` | `0o600` | `ac191f235fec87357ee7a73987483ab5d1019721245cae1c1c6b2a7a1d44a8d4` |
| `raw_sensor_snapshot.json` | `1` | `65,599` | `0o600` | `35704929e5579ea89f6a0289ac3fa044e4dcd07a7c82e022284359704ae62bf5` |
| `sensor_tomography_certificate.json` | `1` | `21,873` | `0o600` | `b127d37b3f94a64bd8afbcb39f386d42e9f2ffcc6e542d86a8203909afdbdac7` |
| `phase2_controlled_snapshot.json` | `1` | `97,968` | `0o600` | `130a7ab018ed5e3291903bf7c2f7027172caa880cf44f77c6f876ce5122422dc` |
| `phase2_controlled_certificate.json` | `1` | `28,213` | `0o600` | `6379283a41723d96637c83a7217e099da477baddc9715ef68dcbb55913c47338` |
