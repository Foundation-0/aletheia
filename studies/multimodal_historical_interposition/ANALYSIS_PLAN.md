# Frozen Analysis Plan — Passive 5-Modality Open-Room Physics x Historical Exact-Operator Interposition

- **Provenance & Timing Disclosure:** This document is a **frozen public analysis plan and hypothesis-grading specification** committed alongside the anonymized aggregate summary JSON after data acquisition completed; it is **not** a pre-data timestamped external preregistration. All statistical kill gates, null families, and negative/partial grading rules below are enforced verbatim by the offline verifier (`verify_multimodal_interposition.py`) without post-hoc threshold retargeting.
- **Acquisition Protocol & Hard Shutoff Bounds:**
  - **Window Target:** Single authorized, 100% passive pre-dawn open-room 5-modality sensor window with hard-coded stop trigger `HARD_STOP_EPOCH = 1795693500` (`2026-11-26 05:45:00 CST`) and mandatory subprocess teardown ceiling `SHUTOFF_CEILING_EPOCH = 1795693620` (`05:47:00 CST`). Realized acquisition counts, durations, and any teardown tail past the stop trigger are reported strictly in [REPORT.md](REPORT.md) and [open_room_interposition_results.json](open_room_interposition_results.json).
- **Privacy-by-Design & Zero Raw Media Storage:**
  - **100% passive capture:** zero speaker output, zero active probing, zero raw video frames, zero images, zero raw audio waveforms, zero Wi-Fi SSIDs, and zero MAC/BSSID identifiers written to disk or committed to any repository.
  - All optical and acoustic streams are reduced strictly in memory to anonymized mathematical invariants (`16x12` block means/variances/gradients, `4x4` Hermitian cross-spectral density matrices, narrowband spectral peak frequencies, autocorrelation envelopes).
- **Energy & Power Policy (`UNCONTROLLED_LAPTOP_NOT_CLAIMED`):** Zero uncontrolled laptop wattage or per-token energy claims are read, logged, or claimed anywhere. Temperatures (`deg C`) and mechanical fan tachometers (`RPM`) are used strictly as physical dynamical and acoustic state variables.

---

## 1. Synchronized Multi-Modal Sensor Suite (`M1`–`M5`)

| Modality | Anonymized On-The-Fly Mathematical Representation |
|---|---|
| **M1 — Visible RGB Optical Field** | In-memory downsampled `16x12` RGB block means, temporal variance, and `30 fps` optical flicker spectrum (`0–15 Hz`) — zero raw frames saved |
| **M2 — Near-IR Optical Field** | In-memory downsampled `16x12` monochrome Near-IR luminance field, spatial gradients, and boundary-vs-interior block covariance — zero raw frames saved |
| **M3 — 4-Channel 48 kHz Acoustic Array** | In-memory `4x4` Hermitian cross-spectral density $S(f)$ across 7 canonical bands, top-32 high-resolution PSD peak frequencies ($\Delta f = 0.25\text{ Hz}$), band-envelope autocorrelation decay — zero raw audio saved |
| **M4 — Mechanical Tachometers & Thermal State** | Exact integer dual-fan shaft RPMs ($f_1, f_2$ + rational beat $|f_1 - f_2|$) and package/chassis temperatures (`deg C`) |
| **M5 — Mechanical Hinge / Anonymized RF / Clock Drift** | Anonymized scalar RF link signal (`dBm`, stripping SSID/BSSID/MAC), hinge angle, and `CLOCK_MONOTONIC` vs. `CLOCK_REALTIME` skew (`ms`) |

---

## 2. Falsifiable Hypotheses & Strict Kill Gates (`H20-A1`–`H20-C2`)

Every stochastic hypothesis is evaluated against **matched adversarial nulls** (`B = 2,500` circular time-shift, IAAFT phase-randomized, spatially-shuffled block permutation, and log-uniform/jittered spectral surrogates) with **Holm–Bonferroni family-wise error control** (`p_Holm < 0.01`). Negative, null, and partial outcomes are reported verbatim without post-hoc retargeting.

1. **`H20-A1` (Stereographic / Rational Cayley $S^2 \to S^3$ Invariance vs. Euclidean Subtractive Cancellation on `M1`/`M2`):**
   - *Kill Gate:* `CONFIRMED` iff dimensionless temporal stability ratio `>= 2.0x` vs. Euclidean differencing, `p_Holm < 0.01` vs. spatially-shuffled block null, and `AUROC >= 0.90` separating real Near-IR room structure from dark noise. `PARTIAL` iff `p_Holm < 0.01` and `AUROC >= 0.90` with ratio `< 2.0x`; otherwise `FALSIFIED`.
2. **`H20-A2` (Exact Pure-$\mathbb{Q}$ Schur Pushforward & Haynsworth Sylvester Inertia Additivity on `M2` Near-IR `12x16` Lattice):**
   - *Kill Gate:* Verify exact pure-$\mathbb{Q}$ Haynsworth inertia additivity $\mathrm{In}(L) = \mathrm{In}(L_{II}) + \mathrm{In}(L / L_{II})$ with `n_neg == 0`. `CONFIRMED` iff held-out boundary-conditioned Schur $R^2 > 0.05$, `p_Holm < 0.01` vs. circular time-shift null, AND `p_raw_spatial_null < 0.01` vs. spatially-shuffled partition null. `PARTIAL` iff temporal null passes but spatial-shuffle null fails; `NULL_STATIC_ROOM` if interior temporal SNR `< 1.25` and lag-1 autocorrelation `< 0.25`; otherwise `FALSIFIED`.
3. **`H20-B1` (Multi-Clock Rational CRT Tachometer-Acoustic Locking on `M3` x `M4`):**
   - *Kill Gate:* Verify exact rational shaft frequencies $f_i = \mathrm{RPM}_i / 60 \in \mathbb{Q}$, exact beat $|f_1 - f_2|$, and CRT phase-synchronization periods across live `(RPM1, RPM2)` pairs. `CONFIRMED` iff passive acoustic coupling survives circular-shift/tachometer-shuffled nulls at `p_Holm < 0.01`; otherwise `FALSIFIED`.
4. **`H20-B2` (Zero-Log `cmpPower` 53-TET vs. 12-TET & Continued-Fraction Harmonicity on Mains-Excluded Persistent Peaks `M3`):**
   - *Kill Gate:* Exclude exact integer mains multiples (`60, 120, 180 Hz`) into a controlled stratum and compute exact zero-log integer power steps (`cmpPower`). `CONFIRMED` iff `53-TET` residual `< 12-TET` AND strictly beats matched log-uniform and jittered spectral nulls at `p_Holm < 0.01`; otherwise `FALSIFIED` (exposing raw `53/12` grid-density inflation).
5. **`H20-B3` (Hermitian $4\times 4$ Cross-Spectral Projected Inertia & Coulomb vs. Viscous Envelope Damping on `M3`):**
   - *Kill Gate:* Zero PSD violations across all empirical Hermitian matrices (`n_neg == 0` in exact $\mathbb{Q}$ active-channel projected inertia) and directional-vs-diffuse effective-rank gap `> 0.2` at `p_Holm < 0.01`. `CONFIRMED` if additionally `>= 5` passive transients achieve `p_raw_transient_damping_diff < 0.01`; `PARTIAL` if rank separation passes while transients are underpowered; otherwise `FALSIFIED`.
6. **`H20-C1` (5-Modality Cross-Modal Exact-$\mathbb{Q}$ Schur Partial Correlation & Descriptive Lag Holonomy on `M1`–`M5`):**
   - *Kill Gate:* `CONFIRMED` iff `>= 1` modality pair survives BOTH `B = 2,500` circular-shift AND `B = 2,500` IAAFT Holm nulls (`p < 0.01`) AND `>= 1` triple exhibits nonzero descriptive lag holonomy (explicitly labeled uncalibrated descriptive lag non-transitivity, distinct from the null-calibrated pairwise coupling tests); `PARTIAL` if pairwise coupling survives without nonzero holonomy; otherwise `FALSIFIED`.
7. **`H20-C2` (Live Replay of Pure-$\mathbb{Z}/\mathbb{Q}$ Khipu Tree-Checksums, Pāṇini C1P Registry, & Default `70/78/85 deg C` Hysteresis Thermal Governor — Deterministic Replay Gate):**
   - *Kill Gate:* Deterministic replay gate (`p_raw = null`, `p_holm = null`, outside the 6-hypothesis Holm–Bonferroni stochastic family), evaluated strictly against the **pre-configured default `70/78/85 deg C` hysteresis ladder** using exact integer switch counts (`bangbang_switches / hysteresis_switches >= 5/1`) and exact rational Pāṇini `C1P` compression (`compression_ratio_q > 1/1`). Secondary exploratory operating-band `91/93/95 deg C` (`2 deg C` and `5 deg C` deadband) sensitivity profiles were chosen around the session's observed median package temperature (`93.0 deg C`), are reported purely for post-hoc sensitivity context, and NEVER override the default kill gate. `CONFIRMED` iff Khipu tree-checksums catch `100%` of tamper trials (`0` escapes), Pāṇini C1P achieves exact lossless compression `> 1/1` on monotone thermal regimes, AND the default `70/78/85 deg C` ladder reduces switch chatter by `>= 5/1` vs. bang-bang; `PARTIAL` if Khipu and C1P pass while the default ladder falls below `5/1`; otherwise `FALSIFIED`.
