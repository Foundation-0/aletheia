# Track S113: Multi-Sensor Live Silicon Physics & Cross-Modal Coupling (`PREREG-S113` + `AMENDMENT1`)

This evidence bundle archives the preregistrations, cryptographic pure-$\mathbb{Q}$ certificate, model-free blind residual discovery receipt, reports, and reproducible verification suites for **Track S113**: a 1-hour live physical experiment across seven multi-sensor phases (`IDLE`, `A`, `B`, `C`, `D`, `E1`, `E2`) on `ASUS ZenBook Pro Duo UX582HS` (`Intel Core i9-11900H` + `NVIDIA RTX 3080 Laptop GPU`), with verified hard sensor shutoff at `2026-11-25T14:41:58Z` (`raw_av_staged_count = 0`; zero raw audio waveforms, camera frames, or binary captures staged).

---

## 1. Summary of Preregistered Verdicts (`PREREG-S113`) & Blind Discoveries (`AMENDMENT1`)

- **`S113-H1` + `E1a` + `E2a` — `FALSIFIED` (as preregistered):** at the preregistered gate (`N = 500` surrogates, Holm across the 6 frequencies) the certificate's own `p_raw_n500 = 0.001996` values give Holm `p = 6 × 0.001996 = 0.011976 ≥ 0.005`, so **H1 is FALSIFIED under the preregistered gate**. The `N = 2000` run (`min p_Holm = 0.0030`) yields `CONFIRMED_H1_VRM_AIRBORNE_PIEZO` only **post-hoc** (N raised 500→2000 after data; mechanism category not among the preregistered outcomes; stimulus-to-audio lag not measured, `prbs7_p = 0.9545`) and is recorded as N0 exploratory (`posthoc_n2000_exploratory`), not as a preregistered confirmation. The measured `6–22 kHz` inter-mic delays up to `250.42 µs` (`γ90² = 0.9901`) fall in the airborne `100–500 µs` band; no `< 1 ms` transduction claim is made. Confirmatory `E2a` (`82 W` pulsed GPU load) reverses lateral bezel TDOAs (`+175.7 -> -200.5 µs`).
- **`S113-H2` (`Phase C`) — `FALSIFIED`:** Power- and fan-residualized LOBO balanced accuracy across active microarchitectural regimes drops from `64.0%` to `48.0%` (`< 60%` gate; FWL $p_{\text{perm}} = 0.0150 \ge 0.01$).
- **`S113-H3` + `E1b` (`FALSIFIED_NOISE_FLUCTUATION`) + `E2b` (`FALSIFIED`):** Crystal-indexed `14.4 kHz` RGB and `10.8 kHz` stratified IR rolling-shutter analyses confirm `0` carriers `>= 4.0σ` up to `141 W` (`83.5 W` GPU + `58.7 W` CPU), establishing tight `4σ` isolation bounds (`<= 0.000202 DN` / `1.39 ppm` RGB and `<= 20.16 ppm` `1009 Hz` stratified IR in `Phase B`, `1,267.01 ppm` all-carrier IR max; `<= 19.93 ppm` in `E1b`; `<= 2.36 ppm` linear RGB in `E2b`).
- **`S113-H4` + `E1c` + `E1d` — `FALSIFIED`:** Default `gamma=300, gain=0` (`Phase D`) compresses shot noise (`H4.ptc_r2 = 0.017642` on `9` unsaturated steps; `0.4866` across all `12` steps). Confirmatory linear `gamma=100, gain=64` (`E1c`) restores a `6.7×` monotonic shot-noise slope ($K = 0.002585\text{ DN}/e^-$, `ptc_r2 = 0.972693`, `0.0073` shy of the strict `0.98` gate). `E1d` (`+31.0 °C` ramp) measures `+0.329027 DN²/°C` dark IR variance drift.
- **`S113-H5` — `FALSIFIED`:** Exact `fractions.Fraction` covariance quantization (`0` floats in calculus kernel) verifies Sylvester-Krein PSD inertia `(13,0,0) = (10,0,0) + (3,0,0)` (Haynsworth exact) and exposes that `intel-rapl:1` (`psys` `~7.1 W`) on `UX582HS` is `99.0333%` collinear with `-pkg_w` ($\Delta R_{\mathbb{Q}}^2 = 0.005922$, `p_shift = 63/2001 = 0.031484 >= 0.005`).
- **`PREREG-S113-AMENDMENT1` Blind Discovery (`Lenses A1–A7`, **`2` split-half-replicated survivors** (lens `A3` time-reversal asymmetry, phases `A` and `E2`) at `N_confirm = 799` under the preregistered lens-family Holm gate `p_Holm < 0.005` **pooled across all phases**; `191` candidates are in `holm_rejected`. An earlier receipt revision stored per-`(phase,lens)` Holm values and overstated the count as `174`; the audit now recomputes Holm from the shipped raw p fields (`BLIND_HOLM_NOT_RECOMPUTED` otherwise). A per-`(phase,lens)` family definition would give `34`; the amendment states the pooled lens family, so `2` is reported): split-half-stable exploratory patterns (N0). σ values are parametric extrapolations from surrogate mean/sd (empirical p floor `1/800` at `N_confirm = 799`), not tail probabilities. **The raw physical captures/telemetry do not ship in this repo, so the physical results are not reproducible from the repo alone**; the shipped receipt + certificate are the verifiable anchor.

---

## 2. Bundle Layout

- `PREREG_S113_MULTISENSOR_SILICON_PHYSICS.md` (`cebe4832...`) & `PREREG_S113_AMENDMENT1_BLIND_ANOMALY_DISCOVERY.md`: protocol documents. **Provenance caveat:** both first appear in this PR's single commit, ~1.5 h after the sensor shutoff (`2026-11-25T14:41:58Z`), and their hashes resolve only to this branch — treat them as written during/after the session, NOT as pre-data anchors.
- `REPORT_S113_PHYSICS.md` & `REPORT_S113_BLIND_ANOMALIES.md`: Full technical reports.
- `s113_multisensor_certificate.json` & `s113_blind_anomalies_receipt.json`: Cryptographic pure-$\mathbb{Q}$ certificate and split-half blind-discovery receipt (`0` raw A/V paths or frame bytes).
- `s113_multisensor_audit.py` & `test_s113_multisensor_audit_r5.py`: Zero-dependency pure-stdlib CI verifier and 8-test R5 suite across all three isolated Python modes (`-I -B`, `-I -O -B`, `-I -B -W error`).
- `dsp_harnesses/`: Full-waveform `numpy`/`scipy` analyzers and synthetic injection/null suites (`s113_analyze_and_certify.py`, `test_s113_r5.py`, `s113_blind_anomaly_hunter.py`, `test_s113_blind_anomaly_hunter.py`).

---

## 3. Quickstart Verification (3 Isolated Modes)

```bash
cd evidence/track-s113-multisensor-silicon-physics
python3 -I -B s113_multisensor_audit.py --check s113_multisensor_certificate.json
python3 -I -B test_s113_multisensor_audit_r5.py
python3 -I -O -B test_s113_multisensor_audit_r5.py
python3 -I -B -W error test_s113_multisensor_audit_r5.py
```
