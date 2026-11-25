# Track S113: Multi-Sensor Live Silicon Physics & Cross-Modal Coupling (`PREREG-S113`)

## 1. Executive Scorecard & Cryptographic Receipts

All seven live capture datasets (`IDLE`, `A`, `B`, `C`, `D`, `E1`, `E2`) were acquired inside the authorized 1-hour blank-wall window on `ASUS ZenBook Pro Duo UX582HS` (`i9-11900H` + `RTX 3080 Laptop GPU`) with verified hard sensor shutoff at `2026-11-25T14:41:58Z` (`2m 02s` prior to the `14:44:00Z` UTC cutoff, `raw_av_staged_count = 0`).

- **Pure-Stdlib Pure-$\mathbb{Q}$ CI Verifier:** `s113_multisensor_audit.py` (`0` external dependencies)
- **Full-Waveform Analyzer & Pure-$\mathbb{Q}$ Certifier:** `s113_analyze_and_certify.py`
- **Adversarial & Positive R5 Suites:** `test_s113_multisensor_audit_r5.py` (pure stdlib) & `test_s113_r5.py` (`7/7 OK` across `-I -B`, `-I -O -B`, `-I -B -W error`)
- **Certificate (`0o600`):** `s113_multisensor_certificate.json`
  - `payload_sha256`: `0ea122458a73ef1a97b3b7471d252a9679e7fb885d14178ae4f2c30754fa0845`
  - `certificate_sha256`: `b18744a69571acf501a25fd2340082804bf0d390d2012495d4a2b571fe39d3d5`

| Hypothesis / Confirmatory Probe | Preregistered Gate (`N = 2000 >= 500` Surrogates) | Measured Quantitative Result | Literal Verdict |
|---|---|---|---|
| **`S113-H1`** (`Phase A`: `4-ch` `48 kHz` Load-Sound Mechanism) | Prime lock-in $p_{\text{Holm}} < 0.005$; inter-mic $\Delta\tau_{ij}$ & coherence $\gamma_{ij}^2$ in `6–22 kHz` | `3001 Hz` (`135.7×`, $R^2=0.652$), `1009 Hz` (`42.6×`, $R^2=0.341$), `97 Hz` (`18.6×`, $R^2=0.192$), all **$p_{\text{Holm}} = 0.0030 < 0.005$**; `6–22 kHz` $\gamma_{90}^2 = 0.9901$, $|\Delta\tau_{ij}|$ up to **`250.42 µs`** (`8.59 cm` @ `343 m/s`, airborne `100–500 µs` band) | **`CONFIRMED_H1_VRM_AIRBORNE_PIEZO`** (MLCC/VRM piezo transducer $\to$ `343 m/s` airborne path; `< 2 µs` EMI, `[5, 80] µs` solid plate & `> 1 s` fan falsified) |
| **`S113-H2`** (`Phase C`: Microarch Switching Beyond Watts/Fans) | FWL partial-$F$ $p_{\text{perm}} < 0.005$ AND zero-leakage LOBO balanced acc `>= 60%` (`5` active regimes) | Unresidualized LOBO = `64.0%`, power+fan-residualized LOBO = **`48.0%`** (chance `20.0%`), FWL $F = 3.158$ vs null `1.052`, **$p_{\text{perm}} = 0.0150 \ge 0.01$** (host background load pinned `IDLE` at `58.7 W` & fans at `4,714 RPM`) | **`FALSIFIED`** |
| **`S113-H3`** (`Phase B`: `10.8 kHz` IR + `14.4 kHz` RGB Rolling-Shutter) | Carrier SNR `>= 4.0σ` above sidebands AND `>= 4.0σ` above `IDLE`, $p_{\text{Holm}} < 0.005$ | `0` carriers `>= 4.0σ` (`p_Holm >= 0.248`); Manual-RGB max `4σ` bound **`<= 0.000202 DN` (`1.39 ppm` @ `97 Hz`; `0.84 ppm` @ `1009 Hz`)**; IR stratified `1009 Hz` bound **`<= 20.16 ppm` (`0.002268 DN`)** and all-carrier certificate max `ir_max_4sigma_bound_ppm = 1,267.01 ppm` (`0.142552 DN` @ `23 Hz`) | **`FALSIFIED`** (sub-`2 ppm` RGB & `20.16 ppm` `1009 Hz` IR isolation bounds) |
| **`S113-H4`** (`Phase D` + `E1c/E1d`: CMOS PTC & Thermal Drift) | Unsaturated linear-regime Poisson shot-noise fit $R^2 > 0.98$, $K > 0$ | Default `gamma=300, gain=0` (`Phase D`): `9`-step unsaturated fit **`H4.ptc_r2 = 0.017642`** ($K = -0.000144\text{ DN}/e^-$; all-`12`-step Anscombe-compressed + `116 DN`-clipped fit $R^2 = 0.4866, K = -0.00131$); Linear `gamma=100, gain=64` (`Phase E1c`): restores positive shot-noise slope $K = 0.002585\text{ DN}/e^-$, **`ptc_r2 = 0.972693`** (`0.007307` below strict `0.98` gate; `215 DN` BT.601 clip) | **`FALSIFIED`** (strict `0.98` gate catches ISP gamma & residual filtering) |
| **`S113-H5`** (`Phases IDLE+B`: Pure-$\mathbb{Q}$ Schur `⧄`, Dark-Mode `⧅`, Krein `⦺`) | Exact rational $R_{\text{dark}|O, \mathbb{Q}}^2 > 0$ with circular-shift $p < 0.005$ (`569` windows) | Exact `⦺(Σ) = (13,0,0) = (10,0,0) + (3,0,0)` (Haynsworth exact); $R_{\text{dark}|\text{sensors}, \mathbb{Q}}^2 = 0.475116$, **but** $R_{\text{dark}|\text{CPU}, \mathbb{Q}}^2 = 0.990333$ (`ΔR² = 0.005922`, circular-shift **`p_shift = 63/2001 = 0.031484 >= 0.005`**) | **`FALSIFIED`** (`UX582HS` `psys` scaling artifact exposed) |
| **Confirmatory `E1a`** (Cocycle `⧇`, Core-0/4/7 Pinning & `1–15 kHz` Sweep) | Narrowband Pancharatnam loop holonomy vs broadband $K_4$ Hodge-1 `⧇` & dispersion slope $\beta$ | Pure ultrasonic carriers (`5003–15013 Hz`) reach **`17,708×` SNR** (`15,013 Hz`) with exact rank-1 `PR = 1.00006` & **`<= 0.011°` narrowband holonomy**, while broadband `6–22 kHz` shows `PR = 2.40–2.94` & `⧇ = κ_{H^1} ∈ [0.284, 0.969]`, $\beta = +0.0937$ (non-dispersive multipath + multi-source); Core 0 radiates **`16.5×`** stronger `3001 Hz` than Core 7 | **Mechanism Resolved** |
| **Confirmatory `E1b`** (`H3_E1b_IR_1009HZ_OOS`: OOS `1009 Hz` IR) | Out-of-sample replication (`4.0σ`, $p < 0.005$) on `3×` counterbalanced `1009 Hz` IR blocks | `E1b` stratified IR `1009 Hz`: **`-1.35σ` vs `IDLE` (`+0.82σ` vs sidebands, $p_{\text{raw}} = 0.885557$)**, stratified `4σ` bound **`<= 19.93 ppm` (`0.002335 DN`)** (`LED_ON <= 12.82 ppm`, `LED_OFF <= 64.31 ppm`) | **`FALSIFIED_NOISE_FLUCTUATION`** |
| **Confirmatory `E2b`** (`e2b_high_wattage_rolling_shutter`: `141 W` CPU+GPU Camera) | Carrier SNR `>= 4.0σ` & $p_{\text{Holm}} < 0.005$ under `83.5 W` GPU + `58.7 W` CPU (`97, 220, 317, 414 Hz`) | `0` carriers confirmed across `{97, 220, 317, 414} Hz`; linear `gamma=100` RGB `4σ` bound **`<= 0.000499 DN` (`2.36 ppm`)**, IR max `4σ` bound **`<= 77.98 ppm` (`0.009144 DN`)** | **`FALSIFIED`** (confirms `<= 2.36 ppm` RGB isolation at `141 W`) |
| **Confirmatory `E2a`** (CPU-VRM vs `82 W` RTX 3080 GPU-VRM Triangulation) | `4-ch` phased-array TDOA $\Delta\tau_{ij}$ sign/azimuth & `1009 ± 317 = {692, 1326} Hz` intermodulation | **Exact lateral TDOA sign reversal:** `CPU_ONLY` (`ch0_ch2 = +175.7 µs`, `ch1_ch3 = +218.1 µs`) vs `GPU_ONLY_317HZ` (`ch0_ch2 = -200.5 µs`, `ch1_ch3 = -184.7 µs` — **`376–403 µs` = `12.9–13.8 cm` acoustic shift**); GPU VRM `6–22 kHz` envelope SNR = **`24,855×`** (`1009 Hz`) & **`18,900×`** (`317 Hz`); IMD `< 1.6×` GPU floor | **Opposite-Side Motherboard VRMs Triangulated** |

---

## 2. Key Physical Findings & Non-Textbook Surprises

### 2.1 Resolution of the "0 ms Electrical Load Sound" & the $K_4$ TDOA Cocycle Paradox (`S113-H1` + `E1a` + `E2a`)
1. **Why the Certificate Token Reads `CONFIRMED_H1_VRM_AIRBORNE_PIEZO` (`< 2 µs` Direct EMI, `[5, 80] µs` Solid-Plate Waveguide, and `> 1 s` Slow Fan All Falsified):**
   - CPU square-wave current modulation locks into the `4-ch` `48 kHz` DMIC array at **`3,001 Hz` (`135.7×` over idle, $p_{\text{Holm}} = 0.0029985 < 0.005$)**, **`1,009 Hz` (`42.6×`, $p_{\text{Holm}} = 0.0029985$)**, and up to **`15,013 Hz` (`17,708×` over idle in `E1a`)** — frequencies three to four orders of magnitude faster than mechanical fan rotor inertia (`> 1 s`).
   - Simultaneously, inter-channel `6–22 kHz` time-delays across the `4` synchronous TDM microphones reach **`250.42 µs`** ($R_\phi^2 = 0.978$, $\gamma_{90}^2 = 0.9901$), falsifying common-mode electrical PDM/rail crosstalk (`|\Delta\tau_{ij}| < 2 µs`) by **`125×`** and lying cleanly inside the airborne acoustic propagation band (`100–500 µs`) rather than the solid-chassis plate-wave band (`[5, 80] µs`).
   - Thus `"PIEZO"` in `CONFIRMED_H1_VRM_AIRBORNE_PIEZO` denotes the **source transduction mechanism** — motherboard VRM inductors and piezoelectric MLCC decoupling capacitors converting `< 1 ms` `di/dt` load edges into ultrasonic pressure waves (`SNR` rising from `9.5×` at `1,009 Hz` to `17,708×` at `15,013 Hz`) — while `"AIRBORNE"` denotes the **waveguide medium**, propagating **through air (`343 m/s`)** from the keyboard/ScreenPad deck across the **`~8.59 cm` (`250.42 µs`)** top-bezel 4-mic aperture.
2. **Why Broadband Group Delays Violate Triangle Closure (`⧇ ≠ 0`) While Pure Ultrasonic Tones Are Exact Rank-1 (`PR = 1.00006`):**
   - At pure high-SNR ultrasonic fundamentals (`5,003`, `7,919`, `11,003`, `15,013 Hz`), the `4×4` Cross-Spectral Density matrix is strictly rank-1 ($\mathrm{PR}(f_0) = 1.00006\text{–}1.00079$) and the narrowband Pancharatnam 3-mic phase holonomy $\operatorname{angle}(S_{ij} S_{jk} S_{ki})$ vanishes to **`0.001°–0.031°`**.
   - Across the full `6–22 kHz` band, however, `PR` rises to **`2.40–2.94`** (superposition of CPU VRM, GPU VRM, and dual-fan broadband turbulence) and multipath reflections off the tilted secondary `ScreenPad Plus` corner reflector create frequency-dependent interference notches, producing large pure-$\mathbb{Q}$ Hodge-1 cohomological obstructions ($\kappa_{H^1} \in [0.284, 0.969]$ on $K_4$, triangle curl `200–857 µs`) with flat frequency scaling ($\beta = +0.0937$, ruling out $\tau \propto f^{-1/2}$ flexural Lamb plate dispersion).
3. **Passive Acoustic Triangulation of CPU VRM vs. RTX 3080 GPU VRM (`E2a`) & Core Asymmetry (`E1a`):**
   - Pulsing the RTX 3080 Laptop GPU (`43.6–81.6 W`) modulates the `6–22 kHz` acoustic envelope by **`24,855×` (`+44.0 dB`)** at `1,009 Hz` and **`18,900×` (`+42.8 dB`)** at `317 Hz`, while **reversing the sign** of the lateral bezel TDOAs (`ch0_ch2: +175.7 µs -> -200.5 µs`; `ch1_ch3: +218.1 µs -> -184.7 µs`), passively localizing the CPU VRM and GPU VRM to opposite sides of the motherboard (`~13 cm` effective path reversal).
   - Pinning a single `3,001 Hz` thread to **Core 0** produces **`16.5×`** higher narrowband acoustic power than **Core 7** (`1.81×` vs `0.11×` over idle), exposing spatial VRM-phase / power-delivery asymmetry across cores.

### 2.2 Sub-`2.4 ppm` Optical/IR Rolling-Shutter Isolation & ISP Gamma Physics (`S113-H3`, `S113-H4`, `E1b–E1d`, `E2b`)
- **Crystal-Locked Rolling-Shutter Upper Bounds (`H3`, `E1b`, `E2b`):** Eliminating pipe-buffering timestamp jitter via unmasked crystal frame-index regression (`29.9983 fps`, `14,399.1 Hz` RGB row clock, `10,799.4 Hz` IR row clock) and stratifying the IR camera's alternating `15 Hz` LED-ON (`~157 DN`) vs. LED-OFF (`~68 DN`) frames establishes tight `4σ` coupling bounds: in `Phase B` (`H3`), Manual-RGB achieves **`<= 0.000202 DN` (`1.39 ppm` max at `97 Hz`; `0.84 ppm` at `1009 Hz`)**, while stratified IR achieves **`<= 20.16 ppm` (`0.002268 DN`) at `1009 Hz`** (`72.43 ppm` at `317 Hz`, `301.32 ppm` at `97 Hz`, and all-carrier certificate max `ir_max_4sigma_bound_ppm = 1,267.01 ppm` / `0.142552 DN` at low-frequency `23 Hz`). Out-of-sample `E1b` (`FALSIFIED_NOISE_FLUCTUATION`) confirms **`<= 19.93 ppm`** on stratified `1009 Hz` IR (`-1.35σ`, $p_{\text{raw}} = 0.885557$), and `141 W` (`83.5 W` GPU + `58.7 W` CPU) `E2b` (`FALSIFIED`) confirms **`<= 0.000499 DN` (`2.36 ppm`)** in linear `gamma=100` RGB and **`<= 77.98 ppm`** max in IR across `{97, 220, 317, 414} Hz`.
- **CMOS PTC & ISP Non-Linearity (`S113-H4` / `E1c`):** Under default UVC `gamma=300` (`γ ≈ 2.2`, `gain=0`) in `Phase D`, the certificate's `9`-step unsaturated linear-regime OLS fit (`exp <= 500`, before the `116.00 DN` digital ceiling) yields **`H4.ptc_r2 = 0.017642, K = -0.000144 DN/e^-`** (`read_noise_dn = 0.35908`), while fitting across all `12` Anscombe-compressed + `116.00 DN`-clipped steps gives $R^2 = 0.4866, K = -0.00131$. Switching to linear `gamma=100, gain=64` (`E1c`) restores a `6.7×` monotonic shot-noise ramp (`0.0899 -> 0.6012 DN²` across `17.8 -> 210.7 DN`, $K = 0.002585\text{ DN}/e^-$, **`ptc_r2 = 0.972693`** across `8` unsaturated steps up to the `215.00 DN` ITU-R BT.601 studio-swing clip, honestly `FALSIFIED` against the strict `R^2 > 0.98` gate).
- **Thermal Dark Sensitivity (`E1d` `+31.0 °C` Ramp, `57 -> 88 °C`):** Dark `ir_led_off` temporal variance rises by **`+10.20 DN²` (`+0.329027 DN²/°C`)** under chassis heating while RGB variance remains thermally invariant (`-0.000342 DN²/°C`).

### 2.3 Pure-$\mathbb{Q}$ Schur Pushforward `⧄` & `UX582HS` `intel-rapl:1` (`PSys`) Telemetry Discovery (`S113-H5`)
- Over exact `fractions.Fraction` arithmetic (`0` floats inside the calculus kernel), `Σ_full` (`13×13` across `569` synchronized `0.5 s` windows) satisfies exact Sylvester-Krein PSD inertia `⦺(Σ_full) = (13, 0, 0)` and exact Haynsworth additivity `(13, 0, 0) = (10, 0, 0) + (3, 0, 0)`.
- Computing exact $R_{\text{dark}|\text{CPU}, \mathbb{Q}}^2 = \frac{11341092347173644541029269983561}{11451792812642246596158410050832} \approx 0.990333$ and $R_{\text{dark}|\text{all}, \mathbb{Q}}^2 \approx 0.996255$ revealed that on `ASUS UX582HS` AC telemetry, `intel-rapl:1` (`psys` `~7.1 W`) reports a scaled/sub-rail current rather than unscaled total system power (`> 65 W`), making `psys - pkg` (`~ -56 W`) `99.0333%` collinear with `-pkg_w`. Incremental multi-sensor variance explained beyond CPU RAPL is exact $\Delta R_{\mathbb{Q}}^2 = R_{\text{dark}|\text{all}, \mathbb{Q}}^2 - R_{\text{dark}|\text{CPU}, \mathbb{Q}}^2 \approx 0.005922$ with circular-shift **`p_shift = 63/2001 = 0.031484 >= 0.005`** (`p_n500 = 18/501 = 0.035928`), cleanly falsifying `H5`.

---

## 3. Reproducible Verification Commands

```bash
# Pure-stdlib CI audit check (zero external dependencies)
python3 -I -B s113_multisensor_audit.py --check s113_multisensor_certificate.json

# Pure-stdlib R5 suite across all three isolated Python modes
python3 -I -B test_s113_multisensor_audit_r5.py
python3 -I -O -B test_s113_multisensor_audit_r5.py
python3 -I -B -W error test_s113_multisensor_audit_r5.py

# Full DSP + pure-Q analyzer & synthetic waveform R5 suites (when numpy & scipy are installed)
python3 -I -B dsp_harnesses/s113_analyze_and_certify.py --check s113_multisensor_certificate.json
python3 -I -B dsp_harnesses/test_s113_r5.py
python3 -I -B dsp_harnesses/test_s113_blind_anomaly_hunter.py
```
