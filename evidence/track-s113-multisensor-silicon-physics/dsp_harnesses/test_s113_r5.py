#!/usr/bin/env python3
"""R5 positive + adversarial null/refusal verification suite for Track S113 (PREREG-S113).

Verifies:
1. S113-H1 synthetic EMI (0 us inter-mic phase slope, <0.25 ms PRBS lag) -> CONFIRMED_H1_EMI,
   synthetic Chassis Piezo (25 us linear phase slope across 6-22 kHz, <1.0 ms lag) -> CONFIRMED_H1_CHASSIS_PIEZO,
   synthetic Airborne Fan (250 us delay in <3 kHz, 1.5 s lag) -> CONFIRMED_AIRBORNE_ACOUSTIC,
   and pure broadband noise -> FALSIFIED.
2. S113-H2 microarchitectural spectral structure beyond Watts -> CONFIRMED (p < 0.005, LOBO >= 60%),
   and purely linear wattage/fan-driven confound -> FALSIFIED.
3. S113-H3 rolling-shutter 317 Hz & 1009 Hz banding with static flat-field FPN + LED alternation -> CONFIRMED,
   and pure Poisson+read noise -> FALSIFIED with accurate 4-sigma LSB/ppm upper bounds.
4. S113-H4 CMOS Photon Transfer Curve recovery (read noise + conversion gain K, R^2 > 0.999) + saturation rejection,
   and flat/noisy non-Poisson curve -> FALSIFIED.
5. S113-H5 pure-Q Fraction Sylvester-Krein inertia, Haynsworth additivity, Dark-Mode shadow on zero-variance fan
   channel, and RAPL_dark recovery -> CONFIRMED vs independent noise RAPL_dark -> FALSIFIED.
6. Certificate tamper refusal, privacy-leak refusal, and AST zero-bare-assert / LF hygiene.
"""
from __future__ import annotations

import ast
from fractions import Fraction
import math
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from scipy import signal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s113_analyze_and_certify as s113


def _ensure(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _fractional_delay_fft(x: np.ndarray, fs: int, delay_s: float) -> np.ndarray:
    """Apply exact subsample delay x(t - delay_s) in frequency domain."""
    n = len(x)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    spec = np.fft.rfft(x) * np.exp(-1j * 2.0 * np.pi * freqs * delay_s)
    return np.fft.irfft(spec, n=n)


def _build_synthetic_phase_a(
    mode: str,
    seed: int = 101,
) -> tuple[dict, np.ndarray, dict[str, np.ndarray]]:
    """Synthesize compact 4-ch 48 kHz Phase A dataset for EMI, PIEZO, AIRBORNE, or NULL."""
    rng = np.random.default_rng(seed)
    fs = 48000
    dur_blk = 3.0
    schedule = [
        ("IDLE_START", "idle", 0.0),
        ("PRIME_23HZ_A", "prime_sq", 23.0),
        ("PRIME_317HZ_A", "prime_sq", 317.0),
        ("PRIME_1009HZ_A", "prime_sq", 1009.0),
        ("PRBS7_A", "prbs7", 0.0),
        ("IDLE_END", "idle", 0.0),
    ]
    total_s = len(schedule) * dur_blk + 1.0
    n_samp = int(total_s * fs)
    t_vec = np.arange(n_samp, dtype=np.float64) / fs

    # Uncorrelated sensor floor across 4 channels
    audio = rng.normal(0.0, 0.002, size=(n_samp, 4))
    blocks = []
    prbs_bits = np.tile(s113.generate_prbs7_bits(), 2)  # 254 chips * 10ms = 2.54s
    chip_s = 0.010

    stim_env = np.zeros(n_samp, dtype=np.float64)
    for bid, (label, kind, fhz) in enumerate(schedule):
        t0 = 0.4 + bid * dur_blk
        t1 = t0 + (2.54 if kind == "prbs7" else (dur_blk - 0.2))
        blocks.append({"block_id": bid, "label": label, "kind": kind, "freq_hz": fhz, "t0_mono_s": t0, "t1_mono_s": t1})
        m = (t_vec >= t0) & (t_vec < t1)
        if kind == "prime_sq":
            sq = (np.sin(2.0 * np.pi * fhz * (t_vec[m] - t0)) >= 0.0).astype(np.float64)
            stim_env[m] = sq
        elif kind == "prbs7":
            c_idx = np.floor((t_vec[m] - t0) / chip_s).astype(np.int64)
            valid = (c_idx >= 0) & (c_idx < len(prbs_bits))
            sub = np.zeros(int(np.sum(m)), dtype=np.float64)
            sub[valid] = prbs_bits[c_idx[valid]].astype(np.float64)
            stim_env[m] = sub

    # 100 Hz RAPL telemetry
    t_tel = np.arange(0.0, total_s, 0.01)
    pkg_w = 10.0 + 40.0 * np.interp(t_tel, t_vec, stim_env) + rng.normal(0.0, 0.2, size=len(t_tel))

    if mode in ("EMI", "PIEZO"):
        sos_carrier = signal.butter(4, [7000.0, 20000.0], btype="bandpass", fs=fs, output="sos")
        carrier = signal.sosfiltfilt(sos_carrier, rng.normal(0.0, 0.04, size=n_samp))
        lag_s = 0.00005 if mode == "EMI" else 0.00035
        mod_env = _fractional_delay_fft(stim_env, fs, lag_s)
        src = carrier * (0.2 + 1.8 * np.clip(mod_env, 0.0, 1.5))
        delays_us = (0.0, 0.0, 0.0, 0.0) if mode == "EMI" else (0.0, 18.0, 36.0, 52.0)
        for ch in range(4):
            audio[:, ch] += _fractional_delay_fft(src, fs, delays_us[ch] * 1e-6)
    elif mode == "AIRBORNE":
        sos_fan = signal.butter(4, [150.0, 2200.0], btype="bandpass", fs=fs, output="sos")
        fan_src = signal.sosfiltfilt(sos_fan, rng.normal(0.0, 0.05, size=n_samp))
        # Slow 1.4 s thermal lag + 180..360 us inter-mic airborne delays
        slow_env = _fractional_delay_fft(stim_env, fs, 1.40)
        sos_lp = signal.butter(2, 2.0, btype="lowpass", fs=fs, output="sos")
        slow_env = np.clip(signal.sosfiltfilt(sos_lp, slow_env), 0.0, 2.0)
        src = fan_src * (0.2 + 2.0 * slow_env)
        for ch, d_us in enumerate((0.0, 140.0, 260.0, 380.0)):
            audio[:, ch] += _fractional_delay_fft(src, fs, d_us * 1e-6)

    audio_i32 = np.clip(audio * 2147483647.0, -2147483600, 2147483600).astype(np.int32)
    manifest = {
        "sample_rate_hz": fs,
        "audio_start_mono_s": 0.0,
        "audio_end_mono_s": total_s,
        "prbs7_chip_ms": 10.0,
        "prbs7_repeats_per_block": 2,
        "blocks": blocks,
    }
    return manifest, audio_i32, {"t_mono_s": t_tel, "pkg_w": pkg_w}


class TestTrackS113R5(unittest.TestCase):
    def test_01_ast_and_source_hygiene(self) -> None:
        track_dir = Path(s113.__file__).resolve().parent
        for name in ("s113_analyze_and_certify.py", "test_s113_r5.py"):
            p = track_dir / name
            raw = p.read_bytes()
            _ensure(b"\r\n" not in raw, f"CRLF found in {name}")
            txt = raw.decode("utf-8")
            tree = ast.parse(txt, filename=name)
            asserts = [n for n in ast.walk(tree) if isinstance(n, ast.Assert)]
            _ensure(len(asserts) == 0, f"Bare assert found in {name}: {len(asserts)}")
            leaks = s113.scan_text_for_privacy_leaks(txt)
            _ensure(not leaks, f"Privacy/path pattern found in {name}: {leaks}")
            forbid_tok = "4-" + "mode"
            _ensure(forbid_tok not in txt, f"Forbidden token in {name}")

    def test_02_h1_emi_piezo_airborne_and_null_discrimination(self) -> None:
        # 1) Direct EMI (0 us inter-mic delay, 0.05 ms impulse lag)
        # Note: at preregistered N=500 across 3 present prime carriers, the Holm floor is
        # 3/501 = 0.00598802 (>= 0.005), so confirmation under the preregistered N=500 gate
        # comes via the PRBS-7 impulse-lag leg (prbs7_p = 1/501 = 0.00199601 < 0.005), while
        # the post-hoc N=1500 exploratory Holm clears < 0.005 (3/1501 = 0.00199867).
        man_emi, aud_emi, tel_emi = _build_synthetic_phase_a("EMI", seed=11)
        res_emi = s113.analyze_h1_mechanism(man_emi, aud_emi, tel_emi, n_surrogates=1500, seed=11)
        _ensure(res_emi["verdict"] == "CONFIRMED_H1_EMI", f"Expected EMI, got {res_emi}")
        _ensure(res_emi["passes_null_gate"] is True, f"Expected passes_null_gate=True, got {res_emi}")
        _ensure(res_emi["n_surrogates"] == 500, f"Expected preregistered n_surrogates=500, got {res_emi['n_surrogates']}")
        _ensure(res_emi["hf_6_22khz_max_abs_tau_us"] < 2.0, f"EMI tau too high: {res_emi['hf_6_22khz_max_abs_tau_us']}")
        _ensure(abs(res_emi["prbs7_lag_clock_anchored_ms"]) < 0.25, f"EMI PRBS lag: {res_emi['prbs7_lag_clock_anchored_ms']}")
        _ensure(res_emi["prbs7_p"] < 0.005, f"EMI PRBS-7 p_n500 failed: {res_emi['prbs7_p']}")
        _ensure(abs(res_emi["min_holm_p"] - (3.0 / 501.0)) < 1e-6, f"Expected 3-carrier N=500 Holm floor 3/501, got {res_emi['min_holm_p']}")
        _ensure(res_emi["posthoc_n2000_exploratory"]["min_holm_p"] < 0.005, f"Posthoc N=1500 Holm failed: {res_emi['posthoc_n2000_exploratory']}")

        # 2) Chassis Piezo (18..52 us linear phase slope, 0.35 ms lag)
        man_pz, aud_pz, tel_pz = _build_synthetic_phase_a("PIEZO", seed=22)
        res_pz = s113.analyze_h1_mechanism(man_pz, aud_pz, tel_pz, n_surrogates=1500, seed=22)
        _ensure(res_pz["verdict"] == "CONFIRMED_H1_CHASSIS_PIEZO", f"Expected PIEZO, got {res_pz}")
        _ensure(res_pz["passes_null_gate"] is True, f"Expected PIEZO passes_null_gate=True")
        _ensure(res_pz["prbs7_p"] < 0.005, f"PIEZO PRBS-7 p_n500 failed: {res_pz['prbs7_p']}")
        _ensure(45.0 <= res_pz["hf_6_22khz_max_abs_tau_us"] <= 60.0, f"Piezo tau mismatch: {res_pz['hf_6_22khz_max_abs_tau_us']}")
        _ensure(abs(res_pz["prbs7_lag_clock_anchored_ms"] - 0.35) < 0.20, f"Piezo PRBS lag: {res_pz['prbs7_lag_clock_anchored_ms']}")

        # 3) Airborne Fan (slow 1.4 s lag, 140..380 us LF inter-mic delay)
        man_air, aud_air, tel_air = _build_synthetic_phase_a("AIRBORNE", seed=33)
        res_air = s113.analyze_h1_mechanism(man_air, aud_air, tel_air, n_surrogates=1500, seed=33)
        _ensure(res_air["verdict"] == "CONFIRMED_AIRBORNE_ACOUSTIC", f"Expected AIRBORNE, got {res_air}")

        # 4) Adversarial pure-noise null -> FALSIFIED
        man_null, aud_null, tel_null = _build_synthetic_phase_a("NULL", seed=44)
        res_null = s113.analyze_h1_mechanism(man_null, aud_null, tel_null, n_surrogates=1500, seed=44)
        _ensure(res_null["verdict"] == "FALSIFIED", f"Expected FALSIFIED on pure noise, got {res_null}")
        _ensure(res_null["passes_null_gate"] is False, f"Expected passes_null_gate=False on pure noise, got {res_null}")

    def test_03_h2_microarch_beyond_watts_and_wattage_confound_refusal(self) -> None:
        rng = np.random.default_rng(303)
        regimes = ["IDLE"] + list(s113.ACTIVE_REGIMES_H2)
        watts_map = {
            "IDLE": (8.0, 12.0),
            "AVX512_FMA": (55.0, 68.0),
            "INT_HAMMING_0": (34.0, 44.0),
            "INT_HAMMING_64": (36.0, 46.0),
            "DRAM_STREAM": (40.0, 56.0),
            "CSTATE_PULSE_1009HZ": (26.0, 35.0),
        }
        blocks = []
        feats_sig = []
        feats_confound = []
        w_vec = rng.normal(0.0, 1.0, size=(2, 35))
        cls_Templates = {c: rng.normal(0.0, 1.6, size=35) for c in regimes}

        for rep in range(6):
            for reg in regimes:
                pw, psw = watts_map[reg]
                pw_i = pw + rng.normal(0.0, 0.8)
                psw_i = psw + rng.normal(0.0, 1.0)
                blocks.append({
                    "block_id": rep,
                    "segment_id": len(blocks),
                    "regime": reg,
                    "t0_mono_s": 0.0,
                    "t1_mono_s": 4.0,
                    "pkg_w": pw_i,
                    "psys_w": psw_i,
                    "cpu_fan_rpm": 2200.0 + 10.0 * rep,
                    "gpu_fan_rpm": 0.0,
                })
                base_lin = 0.15 * pw_i * w_vec[0] + 0.10 * psw_i * w_vec[1]
                noise = rng.normal(0.0, 0.55, size=35)
                feats_confound.append(base_lin + noise)
                feats_sig.append(base_lin + cls_Templates[reg] + noise)

        man = {"blocks": blocks}
        res_pos = s113.analyze_h2_microarch(man, precomputed_features=np.array(feats_sig), n_permutations=800, seed=303)
        _ensure(res_pos["verdict"] == "CONFIRMED", f"Expected H2 CONFIRMED, got {res_pos}")
        _ensure(res_pos["p_perm"] < 0.005 and res_pos["lobo_balanced_accuracy"] >= 0.80, f"Weak H2: {res_pos}")

        res_conf = s113.analyze_h2_microarch(man, precomputed_features=np.array(feats_confound), n_permutations=800, seed=303)
        _ensure(res_conf["verdict"] == "FALSIFIED", f"Wattage confound leaked through H2: {res_conf}")

    def test_04_h3_rolling_shutter_positive_and_null_upper_bound(self) -> None:
        rng = np.random.default_rng(404)
        fps = 30.0
        blocks = [
            {"block_id": 0, "kind": "idle", "freq_hz": 0.0, "t0_mono_s": 0.0, "t1_mono_s": 3.0},
            {"block_id": 1, "kind": "prime_sq", "freq_hz": 317.0, "t0_mono_s": 3.0, "t1_mono_s": 6.0},
            {"block_id": 2, "kind": "prime_sq", "freq_hz": 1009.0, "t0_mono_s": 6.0, "t1_mono_s": 9.0},
            {"block_id": 3, "kind": "idle", "freq_hz": 0.0, "t0_mono_s": 9.0, "t1_mono_s": 12.0},
        ]
        n_f = int(12.0 * fps)
        # Simulate realistic +-1.2 ms ffmpeg pipe jitter on t_mono while sensor runs on crystal clock!
        t_crystal = np.arange(n_f, dtype=np.float64) / fps
        t_jittered = t_crystal + rng.normal(0.0, 0.0012, size=n_f)

        h_ir, h_rgb = 360, 480
        ir_led = (np.arange(n_f) % 2).astype(bool)
        ir_fpn_on = 110.0 + 8.0 * np.sin(np.linspace(0, 3.0, h_ir))
        ir_fpn_off = 14.0 + 1.5 * np.cos(np.linspace(0, 2.0, h_ir))
        ir_null = np.where(ir_led[:, None], ir_fpn_on[None, :], ir_fpn_off[None, :]) + rng.normal(0.0, 0.08, size=(n_f, h_ir))
        rgb_null = 128.0 + 5.0 * np.cos(np.linspace(0, 4.0, h_rgb))[None, :] + rng.normal(0.0, 0.08, size=(n_f, h_rgb))

        # Inject 0.06 DN (470 ppm) 317 Hz & 1009 Hz rolling-shutter ripple on crystal clock with 96% active duty
        ir_sig = ir_null.copy()
        rgb_sig = rgb_null.copy()
        y_rgb = np.arange(h_rgb, dtype=np.float64)[None, :] / h_rgb
        t_row_rgb = (np.arange(n_f, dtype=np.float64)[:, None] + 0.96 * y_rgb) / fps
        m_317 = (t_crystal >= 3.0) & (t_crystal < 6.0)
        m_1009 = (t_crystal >= 6.0) & (t_crystal < 9.0)
        rgb_sig[m_317] += 0.07 * np.sin(2.0 * np.pi * 317.0 * t_row_rgb[m_317])
        rgb_sig[m_1009] += 0.07 * np.sin(2.0 * np.pi * 1009.0 * t_row_rgb[m_1009])

        res_pos = s113.analyze_h3_rolling_shutter(
            {"blocks": blocks},
            {
                "ir_row_means": ir_sig,
                "ir_t_mono_s": t_jittered,
                "ir_is_unique": np.ones(n_f, dtype=bool),
                "ir_is_led_on": ir_led,
                "rgb_row_means": rgb_sig,
                "rgb_t_mono_s": t_jittered,
            },
            n_permutations=800,
            seed=404,
        )
        _ensure(res_pos["verdict"] == "CONFIRMED", f"Expected H3 CONFIRMED despite pipe jitter, got {res_pos}")
        _ensure("rgb_317Hz" in res_pos["confirmed_carriers"] and "rgb_1009Hz" in res_pos["confirmed_carriers"], f"Carriers: {res_pos['confirmed_carriers']}")

        res_null = s113.analyze_h3_rolling_shutter(
            {"blocks": blocks},
            {
                "ir_row_means": ir_null,
                "ir_t_mono_s": t_jittered,
                "ir_is_unique": np.ones(n_f, dtype=bool),
                "ir_is_led_on": ir_led,
                "rgb_row_means": rgb_null,
                "rgb_t_mono_s": t_jittered,
            },
            n_permutations=800,
            seed=404,
        )
        _ensure(res_null["verdict"] == "FALSIFIED", f"Expected H3 FALSIFIED on pure noise, got {res_null}")
        _ensure(res_null["rgb_max_4sigma_bound_lsb"] < 0.05, f"Bound too loose: {res_null['rgb_max_4sigma_bound_lsb']}")

    def test_05_h4_cmos_ptc_and_saturation_gate(self) -> None:
        # True sigma_read = 2.4 DN (var = 5.76), K = 0.25 DN/e- (4.0 e-/DN), plus saturated step at exp=1800
        steps = []
        for exp, mu in [(50, 18.0), (100, 36.0), (166, 60.0), (300, 108.0), (500, 175.0), (800, 222.0), (1800, 254.5)]:
            var_true = 5.76 + 0.25 * mu if exp < 1800 else 0.4
            steps.append({
                "exposure": exp,
                "roi_mean_dn": mu,
                "roi_pairwise_diff_var_dn2": var_true,
                "roi_spatial_fpn_var_dn2": 0.1 + 0.0004 * mu * mu,
                "clipped_high_frac": 0.85 if exp == 1800 else 0.0,
            })
        man_d = {
            "ptc_steps": steps,
            "thermal_snapshots": {
                "cool": {"pkg_temp_c": 46.0, "rgb": {"roi_mean_dn": 60.0, "roi_pairwise_diff_var_dn2": 20.76}, "ir_led_off": {"roi_mean_dn": 12.0, "roi_pairwise_diff_var_dn2": 1.20}},
                "warm": {"pkg_temp_c": 76.0, "rgb": {"roi_mean_dn": 60.3, "roi_pairwise_diff_var_dn2": 21.06}, "ir_led_off": {"roi_mean_dn": 12.6, "roi_pairwise_diff_var_dn2": 1.50}},
            },
        }
        res = s113.analyze_h4_cmos_ptc(man_d)
        _ensure(res["verdict"] == "CONFIRMED", f"Expected H4 CONFIRMED, got {res}")
        _ensure(res["ptc_r2"] > 0.9999, f"PTC R2: {res['ptc_r2']}")
        _ensure(abs(res["conversion_gain_k_dn_per_e"] - 0.25) < 1e-4, f"Gain K: {res['conversion_gain_k_dn_per_e']}")
        _ensure(abs(res["read_noise_dn"] - 2.4) < 1e-3, f"Read noise: {res['read_noise_dn']}")
        _ensure(res["n_steps_linear_fit"] == 6, f"Saturated step not excluded: {res['n_steps_linear_fit']}")

        # Adversarial flat/gamma-crushed non-Poisson variance -> FALSIFIED
        bad_steps = [{"exposure": e, "roi_mean_dn": float(m), "roi_pairwise_diff_var_dn2": 4.0 + ((-1) ** i) * 1.5, "clipped_high_frac": 0.0} for i, (e, m) in enumerate([(50, 20), (100, 50), (200, 90), (400, 150), (800, 210)])]
        res_bad = s113.analyze_h4_cmos_ptc({"ptc_steps": bad_steps})
        _ensure(res_bad["verdict"] == "FALSIFIED", f"Expected FALSIFIED on non-Poisson curve, got {res_bad}")

    def test_06_h5_pure_q_schur_dark_mode_haynsworth_and_certificate_tamper(self) -> None:
        rng = np.random.default_rng(606)
        n_w = 160
        obs_names = ["dmic0", "dmic1", "ir_m", "rgb_m", "temp_c", "fan_rpm_zero"]
        pwr_names = ["core_w", "uncore_w", "dark_w"]

        obs = rng.normal(0.0, 1.0, size=(n_w, 6))
        obs[:, 5] = 0.0  # Constant zero-RPM fan -> triggers exact Dark-Mode shadow ker(Sigma_OO) dim=1!
        core_w = 25.0 + 8.0 * obs[:, 0] + rng.normal(0.0, 1.5, size=n_w)
        uncore_w = 4.0 + 1.0 * obs[:, 1] + rng.normal(0.0, 0.5, size=n_w)
        # Hidden platform rail RAPL_dark coupled to IR/RGB/DMIC sensors
        dark_coupled = 12.0 + 2.5 * obs[:, 2] - 1.8 * obs[:, 3] + 1.2 * obs[:, 0] + rng.normal(0.0, 0.8, size=n_w)
        dark_indep = 12.0 + rng.normal(0.0, 2.5, size=n_w)

        res_pos, res_mat = s113.analyze_h5_exact_schur_q(
            obs, np.column_stack([core_w, uncore_w, dark_coupled]), obs_names, pwr_names, n_shifts=700, seed=606
        )
        _ensure(res_pos["verdict"] == "CONFIRMED", f"Expected H5 CONFIRMED, got {res_pos}")
        _ensure(res_pos["haynsworth_inertia_additivity_exact"] is True, "Haynsworth additivity must hold")
        _ensure(res_pos["dark_mode_shadow_obs"]["dim_dark"] == 1, f"Expected dim_dark=1 for zero-RPM fan, got {res_pos['dark_mode_shadow_obs']}")
        _ensure(s113.str_to_frac(res_pos["rapl_dark_r2_given_sensors_exact_q"]) > Fraction(7, 10), "Expected strong exact Q R2")
        _ensure(res_mat.shape == (n_w, 3), "Unexpected residual shape")

        res_null, _ = s113.analyze_h5_exact_schur_q(
            obs, np.column_stack([core_w, uncore_w, dark_indep]), obs_names, pwr_names, n_shifts=700, seed=606
        )
        _ensure(res_null["verdict"] == "FALSIFIED", f"Expected H5 FALSIFIED on independent dark rail, got {res_null}")

        # Certificate build, 0o600 write, --check verification, and tamper/leak refusal
        cert = s113.build_certificate({
            "track": "S113",
            "prereg_protocol": s113.PREREG_ID,
            "verdict_summary": {"H5": res_pos["verdict"]},
            "modules": {"H5": res_pos},
        })
        chk = s113.verify_certificate_dict(cert)
        _ensure(chk["ok"] is True, "Valid certificate must pass verify_certificate_dict")

        # Tamper exact Q Schur entry -> must raise S113Error
        tampered = s113.parse_strict_json_text(s113.canonical_json(cert))
        tampered["payload"]["modules"]["H5"]["rapl_dark_r2_given_sensors_exact_q"] = "1/2"
        tampered["payload_sha256"] = s113.sha256_text(s113.canonical_json(tampered["payload"]))
        tampered["certificate_sha256"] = s113.sha256_text(s113.canonical_json({
            "schema": tampered["schema"],
            "prereg_id": tampered["prereg_id"],
            "payload": tampered["payload"],
            "payload_sha256": tampered["payload_sha256"],
        }))
        raised = False
        try:
            s113.verify_certificate_dict(tampered)
        except s113.S113Error:
            raised = True
        _ensure(raised, "Tampered rational R2 must be refused by verify_certificate_dict")

        # Privacy leak refusal on write_secure_lf_file
        with tempfile.TemporaryDirectory() as td:
            out_p = Path(td) / "cert.json"
            s113.write_secure_lf_file(out_p, s113.canonical_json(cert) + "\n", mode=0o600)
            mode_bits = out_p.stat().st_mode & 0o777
            _ensure(mode_bits == 0o600, f"Expected 0o600 permissions, got {oct(mode_bits)}")

            leak_raised = False
            bad_tok = chr(47) + "ho" + "me" + chr(47) + "alice"
            try:
                s113.write_secure_lf_file(out_p, f'{{"leak": "{bad_tok}"}}\n')
            except s113.S113Error:
                leak_raised = True
            _ensure(leak_raised, "Personal path leak must be refused by write_secure_lf_file")

    def test_07_k4_hodge1_exact_q_coboundary_vs_curl(self) -> None:
        # Exact potential tau = [0, 12, 35, 80] us -> zero triangle curl (kappa_H1 == 0/1)
        exact_pairs = {
            "ch0_ch1": 12.0, "ch0_ch2": 35.0, "ch0_ch3": 80.0,
            "ch1_ch2": 23.0, "ch1_ch3": 68.0, "ch2_ch3": 45.0,
        }
        h0 = s113.q_k4_hodge1_obstruction(exact_pairs)
        _ensure(h0["kappa_h1_exact_q"] == "0/1", f"Expected 0/1 coboundary obstruction, got {h0}")

        # Pure cyclic curl on (0->1->2->0) -> strictly positive rational obstruction in (0, 1]
        curl_pairs = {
            "ch0_ch1": 50.0, "ch1_ch2": 50.0, "ch0_ch2": -50.0,
            "ch0_ch3": 0.0, "ch1_ch3": 0.0, "ch2_ch3": 0.0,
        }
        hc = s113.q_k4_hodge1_obstruction(curl_pairs)
        _ensure(s113.str_to_frac(hc["kappa_h1_exact_q"]) > Fraction(1, 2), f"Expected large curl obstruction, got {hc}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
