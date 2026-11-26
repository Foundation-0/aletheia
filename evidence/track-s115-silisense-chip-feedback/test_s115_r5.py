#!/usr/bin/env python3
"""R5 Verification & Refusal Suite for Track S115 (`PREREG-S115` SiliSense).

Verifies:
  1. Hard fail-closed Two-Mode Sensor & Privacy Airlock:
     - Default Mode 1 ('telemetry-only') refuses all DMIC audio endpoints/traces.
     - Mode 2 ('dmic-authorized') refuses missing/non-positive/>300s audio
       windows, invalid tokens, and expired monotonic windows.
     - Camera endpoints (/dev/video*, V4L2, PipeWire video) are UNCONDITIONALLY
       refused across ALL modes (ERR_CAMERA_FORBIDDEN).
     - Zero /dev/snd or /dev/video opens occur anywhere during test execution.
  2. Strict Anti-Illusion Null Calibration:
     - Colored AR(1) + multi-lag linear uncore->GPU coupled noise yields ZERO
       false positives across A3, A5, A7, A1, and A2, with multi-lag Schur
       residual linear correlation <= 1e-9.
  3. Positive Synthetic Recovery Across All 5 Non-Textbook Lenses:
     - A3 sawtooth steepening shockwaves, A5 -80 ms precursor spikes, A7
       zero-correlation nonlinear copula contention, A1 quadratic phase-coupled
       ultrasonic bicoherence (vs random-phase control), and A2 chiral wave +
       signed CPU-vs-GPU VRM lateral TDOA triangulation.
  4. H15a, H15b, and H15c Positive & Refusal/Goalpost-Tamper Gates:
     - H15a equal-wattage non-confound refusal when separation is purely wattage.
     - H15b PrecursorThrottleGovernor beating NoGovernor, Reactive-1Hz-SMI, AND
       duty-cycle-matched Shuffled-Trigger-Control (plus refusal when shuffled
       control matches).
     - H15c SiliSenseKernelAutotuner sustained EDP win + refusal on CS-08
       effective-batch mismatch or tampered objective weights.
  5. Immutable PREREG-S115 SHA-256 Pin & AST Hygiene Gate (0 bare asserts,
     0 shell=True, 0 home-path leaks).
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest

import builtins

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

EXPECTED_PREREG_ID = "PREREG-S115-SILICON-PHYSICS-FEEDBACK-OPTIMIZER-V1"
EXPECTED_PREREG_SHA256 = "4787a4f407bb09b440c19190a24e89fead862ba9cec96edd68e5d222e0f0dc75"

try:
    import numpy as np  # noqa: E402
    from scipy import signal  # noqa: E402
    from s115_feedback_autotuner import (  # noqa: E402
        HoloSphereKernelConfig,
        HoloSphereStepTelemetry,
        HoloSphereTuningProfile,
        PairedABABABEvaluator,
        PreAdaptationResidualLatch,
        PrecursorThrottleGovernor,
        SiliSenseHoloSphereBridge,
        SiliSenseKernelAutotuner,
        check_delay_bandwidth_lock,
        floor_to_exact_f32,
        grade_h15b_results,
        simulate_sustained_governor_benchmark,
    )
    from s115_silisense_profiler import (  # noqa: E402
        AudioAuthorizationGate,
        PREREG_S115_ID,
        PREREG_S115_RELPATH,
        PREREG_S115_SHA256,
        SiliSensePermissionError,
        SiliSenseProfiler,
        SiliSenseValueError,
        compute_a1_ultrasonic_bicoherence,
        compute_a2_chiral_vrm_balance,
        compute_a3_time_reversal_asymmetry,
        compute_a5_precursor_lead_lag,
        compute_a7_nonlinear_uncore_copula_mi,
        extract_ultrasonic_envelope,
        make_synthetic_workload_trace,
        validate_endpoint_path,
    )

    _HAS_NUMPY_SCIPY = True
except ImportError:
    np = None  # type: ignore[assignment]
    signal = None  # type: ignore[assignment]
    _HAS_NUMPY_SCIPY = False


class TestS115SiliSenseR5(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_open = builtins.open
        test_case = self

        def _guarded_open(file, *args, **kwargs):
            f_str = str(file)
            if "/dev/snd" in f_str or "/dev/video" in f_str or "/dev/v4l" in f_str:
                test_case.fail(f"FORBIDDEN_LIVE_SENSOR_OPEN during unit test: {f_str}")
            return test_case._orig_open(file, *args, **kwargs)

        builtins.open = _guarded_open

    def tearDown(self) -> None:
        builtins.open = self._orig_open

    @unittest.skipUnless(_HAS_NUMPY_SCIPY, "requires numpy and scipy")
    def test_01_sensor_airlock_fail_closed_and_unconditional_camera_ban(self) -> None:
        clock = [1000.0]
        valid_gate = AudioAuthorizationGate.create(
            enable_dmic_authorized=True,
            authorize_audio_window_sec=30.0,
            pi_authorization_token="PI-WINDOW-20261125",
            clock_fn=lambda: clock[0],
        )
        valid_gate.verify_active()
        self.assertAlmostEqual(valid_gate.remaining_sec(), 30.0, places=6)

        # Camera AND IR/media endpoints (incl. traversal & V4L2 char 81:*) MUST fail closed even when DMIC audio IS authorized
        self.assertNotIn("PI-WINDOW-20261125", repr(valid_gate))
        for cam_ep in (
            "/dev/video0",
            "/dev/./video0",
            "/dev//video0",
            "/dev/char/81:0",
            "/dev/snd/../video0",
            "/dev/video2",
            "/dev/media0",
            "/dev/v4l/by-id/usb-cam",
            "pipewire://camera/0",
            "sys/class/leds/ir_led",
        ):
            with self.assertRaises(SiliSensePermissionError) as ctx:
                validate_endpoint_path(cam_ep, auth_gate=valid_gate)
            self.assertEqual(ctx.exception.code, "ERR_CAMERA_FORBIDDEN")

        # Audio endpoints MUST fail closed in default Mode 1 (auth_gate=None)
        for aud_ep in ("/dev/snd/pcmC0D0c", "alsa:hw:0,0", "arecord"):
            with self.assertRaises(SiliSensePermissionError) as ctx:
                validate_endpoint_path(aud_ep, auth_gate=None)
            self.assertEqual(ctx.exception.code, "ERR_DMIC_DISABLED_DEFAULT")
            # Allowed while valid_gate is unexpired
            validate_endpoint_path(aud_ep, auth_gate=valid_gate)

        # Missing/invalid/out-of-bounds authorization parameters MUST fail closed
        bad_cases = [
            {"enable_dmic_authorized": False, "authorize_audio_window_sec": 10.0, "pi_authorization_token": "VALIDTOKEN1"},
            {"enable_dmic_authorized": True, "authorize_audio_window_sec": None, "pi_authorization_token": "VALIDTOKEN1"},
            {"enable_dmic_authorized": True, "authorize_audio_window_sec": 0.0, "pi_authorization_token": "VALIDTOKEN1"},
            {"enable_dmic_authorized": True, "authorize_audio_window_sec": -5.0, "pi_authorization_token": "VALIDTOKEN1"},
            {"enable_dmic_authorized": True, "authorize_audio_window_sec": 301.0, "pi_authorization_token": "VALIDTOKEN1"},
            {"enable_dmic_authorized": True, "authorize_audio_window_sec": float("nan"), "pi_authorization_token": "VALIDTOKEN1"},
            {"enable_dmic_authorized": True, "authorize_audio_window_sec": 15.0, "pi_authorization_token": "short"},
        ]
        for kwargs in bad_cases:
            with self.assertRaises(SiliSensePermissionError):
                AudioAuthorizationGate.create(**kwargs)  # type: ignore[arg-type]

        # Monotonic window expiry MUST fail closed
        clock[0] = 1030.5
        with self.assertRaises(SiliSensePermissionError) as ctx_exp:
            valid_gate.verify_active()
        self.assertEqual(ctx_exp.exception.code, "ERR_AUDIO_WINDOW_EXPIRED")

        # Default Mode-1 profiler MUST refuse DMIC arrays and camera keys
        prof_m1 = SiliSenseProfiler(mode="telemetry-only", n_iaaft=39, n_shifts=60, seed=7)
        base_tr = make_synthetic_workload_trace("fused_holosphere", n_samples=160, seed=7)
        with self.assertRaises(SiliSensePermissionError) as ctx_dmic:
            prof_m1.profile_trace({**base_tr, "dmic_mono_48k": np.zeros(2048)}, allow_offline_dmic=False)
        self.assertEqual(ctx_dmic.exception.code, "ERR_DMIC_DISABLED_DEFAULT")

        with self.assertRaises(SiliSensePermissionError) as ctx_cam:
            prof_m1.profile_trace({**base_tr, "/dev/video0_luma": [1.0, 2.0]}, allow_offline_dmic=False)
        self.assertEqual(ctx_cam.exception.code, "ERR_CAMERA_FORBIDDEN")

    @unittest.skipUnless(_HAS_NUMPY_SCIPY, "requires numpy and scipy")
    def test_02_null_calibration_zero_false_positives_on_colored_ar1_and_linear_lags(self) -> None:
        null_tr = make_synthetic_workload_trace("colored_null", n_samples=420, seed=12345)
        prof = SiliSenseProfiler(mode="telemetry-only", n_iaaft=149, n_shifts=300, seed=12345)
        res = prof.profile_trace(null_tr)

        self.assertFalse(res["any_non_textbook_significant_0p005"])
        obs = res["observables"]
        self.assertFalse(obs["A3_telemetry"]["significant_0p005"])
        self.assertFalse(obs["A5_precursor"]["significant_0p005"])
        self.assertFalse(obs["A7_uncore_copula_mi"]["significant_0p005"])
        self.assertLessEqual(obs["A7_uncore_copula_mi"]["max_abs_residual_linear_corr"], 1e-9)

        # Colored ultrasonic Gaussian noise on offline A1 & A2 must ALSO produce zero false positives
        rng = np.random.default_rng(54321)
        dmic_null = rng.standard_normal((8192, 4))
        for ch in range(4):
            for t in range(1, dmic_null.shape[0]):
                dmic_null[t, ch] += 0.55 * dmic_null[t - 1, ch]

        a1_null = compute_a1_ultrasonic_bicoherence(dmic_null[:, 0], n_iaaft=79, seed=54321, allow_offline_array=True)
        a2_null = compute_a2_chiral_vrm_balance(dmic_null, n_surr=79, seed=54321, allow_offline_array=True)
        self.assertFalse(a1_null["significant_0p005"])
        self.assertFalse(a2_null["significant_0p005"])

    @unittest.skipUnless(_HAS_NUMPY_SCIPY, "requires numpy and scipy")
    def test_03_positive_recovery_all_five_non_textbook_lenses(self) -> None:
        # A3, A5, A7 via eager micro-kernel burst trace
        eager_tr = make_synthetic_workload_trace("eager_microkernel", n_samples=450, dt_ms=5.0, seed=99)
        a3 = compute_a3_time_reversal_asymmetry(eager_tr["gpu_power_w"], dt_ms=5.0, n_iaaft=699, seed=99)
        a5 = compute_a5_precursor_lead_lag(
            eager_tr["fast_power_w"], eager_tr["slow_throttle_or_psys"], dt_ms=5.0, max_lag_ms=150.0, n_shifts=500, seed=99
        )
        a7 = compute_a7_nonlinear_uncore_copula_mi(
            eager_tr["uncore_w"], eager_tr["gpu_power_w"], max_linear_lag=5, n_iaaft=699, seed=99
        )

        self.assertTrue(a3["significant_0p005"])
        self.assertGreaterEqual(abs(a3["z_iaaft"]), 4.0)
        self.assertTrue(a5["significant_0p005"])
        self.assertAlmostEqual(a5["peak_precursor_lag_ms"], -80.0, delta=10.0)
        self.assertTrue(a7["significant_0p005"])
        self.assertGreaterEqual(a7["z_iaaft"], 4.0)
        self.assertLessEqual(a7["max_abs_residual_linear_corr"], 1e-9)

        # A1: Quadratic phase-coupled 7.5 kHz + 11.25 kHz -> 18.75 kHz vs uncoupled random-phase third tone
        fs = 48000
        n_fft = 256
        n_seg = 64
        rng = np.random.default_rng(2026)
        coupled_segs: list[np.ndarray] = []
        uncoupled_segs: list[np.ndarray] = []
        t_seg = np.arange(n_fft, dtype=np.float64) / float(fs)
        f1, f2 = 7500.0, 11250.0
        f3 = f1 + f2
        for _ in range(n_seg):
            p1 = float(rng.uniform(0.0, 2.0 * math.pi))
            p2 = float(rng.uniform(0.0, 2.0 * math.pi))
            p3_rand = float(rng.uniform(0.0, 2.0 * math.pi))
            coupled_segs.append(
                np.cos(2.0 * math.pi * f1 * t_seg + p1)
                + np.cos(2.0 * math.pi * f2 * t_seg + p2)
                + 0.95 * np.cos(2.0 * math.pi * f3 * t_seg + (p1 + p2))
                + 0.20 * rng.standard_normal(n_fft)
            )
            uncoupled_segs.append(
                np.cos(2.0 * math.pi * f1 * t_seg + p1)
                + np.cos(2.0 * math.pi * f2 * t_seg + p2)
                + 0.95 * np.cos(2.0 * math.pi * f3 * t_seg + p3_rand)
                + 0.20 * rng.standard_normal(n_fft)
            )
        coupled = np.concatenate(coupled_segs)
        uncoupled = np.concatenate(uncoupled_segs)

        a1_c = compute_a1_ultrasonic_bicoherence(coupled, fs=fs, n_fft=n_fft, n_iaaft=99, seed=2026, allow_offline_array=True)
        a1_u = compute_a1_ultrasonic_bicoherence(uncoupled, fs=fs, n_fft=n_fft, n_iaaft=99, seed=2026, allow_offline_array=True)
        self.assertGreater(a1_c["max_b2"], 0.60)
        self.assertTrue(a1_c["significant_0p005"])
        self.assertLess(a1_u["max_b2"], 0.25)

        # A2: Chiral quadrature 20 kHz tone + opposite-sign CPU-vs-GPU VRM broadband TDOA (+/- 160 us)
        n_a2 = 12288
        t_full = np.arange(n_a2, dtype=np.float64) / float(fs)
        src_vrm = signal.sosfiltfilt(
            signal.butter(4, [13000.0 / 24000.0, 17500.0 / 24000.0], btype="bandpass", output="sos"),
            rng.standard_normal(n_a2),
        )
        delay_samples = 8  # 8 / 48000 = 166.67 us -> ~2.86 cm lateral offset
        chiral_l = 0.8 * np.cos(2.0 * math.pi * 20100.0 * t_full)
        chiral_r = 0.8 * np.sin(2.0 * math.pi * 20100.0 * t_full)

        # Case 1: Left (CPU VRM) leads Right by +8 samples => CPU_VRM_LEFT
        arr_cpu = 0.12 * rng.standard_normal((n_a2, 4))
        arr_cpu[:, 0] += src_vrm + chiral_l
        arr_cpu[delay_samples:, 3] += src_vrm[:-delay_samples] + chiral_r[delay_samples:]
        res_cpu = compute_a2_chiral_vrm_balance(arr_cpu, fs=fs, n_surr=99, seed=11, allow_offline_array=True)

        # Case 2: Right (GPU VRM) leads Left by +8 samples => GPU_VRM_RIGHT
        arr_gpu = 0.12 * rng.standard_normal((n_a2, 4))
        arr_gpu[delay_samples:, 0] += src_vrm[:-delay_samples] + chiral_l[delay_samples:]
        arr_gpu[:, 3] += src_vrm + chiral_r
        res_gpu = compute_a2_chiral_vrm_balance(arr_gpu, fs=fs, n_surr=99, seed=12, allow_offline_array=True)

        self.assertTrue(res_cpu["significant_0p005"])
        self.assertEqual(res_cpu["dominant_vrm_rail"], "CPU_VRM_LEFT")
        self.assertGreater(res_cpu["tdoa_left_leads_right_us"], 140.0)
        self.assertLess(res_cpu["lateral_vrm_offset_cm"], -2.0)

        self.assertTrue(res_gpu["significant_0p005"])
        self.assertEqual(res_gpu["dominant_vrm_rail"], "GPU_VRM_RIGHT")
        self.assertLess(res_gpu["tdoa_left_leads_right_us"], -140.0)
        self.assertGreater(res_gpu["lateral_vrm_offset_cm"], 2.0)

        # Ultrasonic envelope extraction check
        env = extract_ultrasonic_envelope(arr_gpu[:, 0], fs=fs, bin_ms=1.0, allow_offline_array=True)
        self.assertEqual(env.shape[0], n_a2 // 48)

    @unittest.skipUnless(_HAS_NUMPY_SCIPY, "requires numpy and scipy")
    def test_04_h15a_paired_ababab_confirm_and_confound_refusal(self) -> None:
        ev = PairedABABABEvaluator(mode="telemetry-only", n_iaaft=699, n_shifts=500)
        std_pairs = [
            (
                {**make_synthetic_workload_trace("eager_microkernel", seed=100 + k, target_mean_gpu_w=99.0), "tokens_processed": 16384},
                {**make_synthetic_workload_trace("fused_holosphere", seed=200 + k, target_mean_gpu_w=91.0), "tokens_processed": 16384},
            )
            for k in range(4)
        ]
        eqw_pairs = [
            (
                {**make_synthetic_workload_trace("eager_microkernel", seed=300 + k, target_mean_gpu_w=93.0), "tokens_processed": 16384},
                {**make_synthetic_workload_trace("fused_holosphere", seed=400 + k, target_mean_gpu_w=93.0), "tokens_processed": 16384},
            )
            for k in range(4)
        ]
        res_ok = ev.evaluate_h15a(standard_pairs=std_pairs, equal_watt_pairs=eqw_pairs)
        self.assertEqual(res_ok["verdict"], "CONFIRMED")

        # Tamper 1: Equal-wattage pairs violate <=5% wattage bound -> must NOT return CONFIRMED
        bad_eqw = [
            (
                {**make_synthetic_workload_trace("eager_microkernel", seed=300 + k, target_mean_gpu_w=105.0), "tokens_processed": 16384},
                {**make_synthetic_workload_trace("fused_holosphere", seed=400 + k, target_mean_gpu_w=90.0), "tokens_processed": 16384},
            )
            for k in range(4)
        ]
        res_bad_eqw = ev.evaluate_h15a(standard_pairs=std_pairs, equal_watt_pairs=bad_eqw)
        self.assertEqual(res_bad_eqw["verdict"], "PARTIAL")
        self.assertFalse(res_bad_eqw["criterion_3_equal_watt_non_confound"])

        # Tamper 2: CS-08 token count mismatch -> must raise typed SiliSenseValueError
        mismatch_pairs = list(std_pairs)
        mismatch_pairs[0] = (
            {**std_pairs[0][0], "tokens_processed": 16384},
            {**std_pairs[0][1], "tokens_processed": 8192},
        )
        with self.assertRaises(SiliSenseValueError) as ctx:
            ev.evaluate_h15a(standard_pairs=mismatch_pairs, equal_watt_pairs=eqw_pairs)
        self.assertEqual(ctx.exception.code, "ERR_CS08_TOKEN_MISMATCH")

    @unittest.skipUnless(_HAS_NUMPY_SCIPY, "requires numpy and scipy")
    def test_05_h15b_precursor_governor_beats_controls_and_refuses_non_specific_damping(self) -> None:
        res = simulate_sustained_governor_benchmark(seeds=(42, 137, 2026, 909), n_steps=1200, dt_ms=5.0)
        self.assertEqual(res["verdict"], "CONFIRMED")
        self.assertTrue(res["criterion_1_precursor_lead"])
        self.assertTrue(res["criterion_2_closed_loop_stability"])
        self.assertGreaterEqual(res["throughput_vs_NoGovernor"]["rel_change_pct"], -2.0)

        # If Shuffled-Trigger-Control ties SiliSense-Precursor-Gov, Criterion 2 MUST fail (PARTIAL, not CONFIRMED)
        spoof = grade_h15b_results(
            lead_receipts=[{"p_circ": 0.002, "peak_precursor_lag_ms": -80.0} for _ in range(4)],
            per_arm_stall={
                "NoGovernor": [0.22, 0.24, 0.23, 0.25],
                "Reactive-1Hz-SMI": [0.21, 0.22, 0.21, 0.23],
                "Shuffled-Trigger-Control": [0.06, 0.06, 0.06, 0.06],
                "SiliSense-Precursor-Gov": [0.06, 0.06, 0.06, 0.06],
            },
            per_arm_cv={
                "NoGovernor": [0.20, 0.21, 0.20, 0.22],
                "Reactive-1Hz-SMI": [0.19, 0.20, 0.19, 0.21],
                "Shuffled-Trigger-Control": [0.09, 0.09, 0.09, 0.09],
                "SiliSense-Precursor-Gov": [0.09, 0.09, 0.09, 0.09],
            },
            per_arm_tps={
                "NoGovernor": [910.0, 908.0, 912.0, 909.0],
                "Reactive-1Hz-SMI": [905.0, 904.0, 906.0, 905.0],
                "Shuffled-Trigger-Control": [925.0, 924.0, 926.0, 925.0],
                "SiliSense-Precursor-Gov": [925.0, 924.0, 926.0, 925.0],
            },
        )
        self.assertFalse(spoof["criterion_2_closed_loop_stability"])
        self.assertNotEqual(spoof["verdict"], "CONFIRMED")

    @unittest.skipUnless(_HAS_NUMPY_SCIPY, "requires numpy and scipy")
    def test_06_h15c_composite_autotuner_and_tamper_refusals(self) -> None:
        tuner = SiliSenseKernelAutotuner()

        # Tampering with locked weights MUST fail closed
        with self.assertRaises(SiliSenseValueError) as ctx_w:
            SiliSenseKernelAutotuner(lambda_a3=0.50)
        self.assertEqual(ctx_w.exception.code, "ERR_LOCKED_WEIGHT_TAMPER")

        # CS-08 effective tokens/step mismatch MUST fail closed
        c_bad1 = HoloSphereKernelConfig("c1", 32, 4, micro_batch=8, grad_accum=2, seq_len=512, grad_ckpt=0)
        c_bad2 = HoloSphereKernelConfig("c2", 32, 4, micro_batch=8, grad_accum=1, seq_len=512, grad_ckpt=0)
        with self.assertRaises(SiliSenseValueError) as ctx_cs08:
            tuner.select_winners(
                [
                    {"config": c_bad1, "cal_tok_per_s": 10000.0, "cal_edp": 0.5, "z_a3": 0.5, "z_a7": 0.5, "a5_precursor_rate": 0.0},
                    {"config": c_bad2, "cal_tok_per_s": 11000.0, "cal_edp": 0.5, "z_a3": 0.5, "z_a7": 0.5, "a5_precursor_rate": 0.0},
                ]
            )
        self.assertEqual(ctx_cs08.exception.code, "ERR_CS08_EFFECTIVE_BATCH_MISMATCH")

        # Valid 3-config selection & sustained confirmation grading
        c1 = HoloSphereKernelConfig("tps_hot", 32, 8, micro_batch=16, grad_accum=1, seq_len=512, grad_ckpt=0)
        c2 = HoloSphereKernelConfig("edp_cal", 64, 8, micro_batch=8, grad_accum=2, seq_len=512, grad_ckpt=0)
        c3 = HoloSphereKernelConfig("sili_opt", 32, 4, micro_batch=8, grad_accum=2, seq_len=512, grad_ckpt=0)
        sel = tuner.select_winners(
            [
                {"config": c1, "cal_tok_per_s": 15000.0, "cal_edp": 0.51, "z_a3": -6.5, "z_a7": 7.1, "a5_precursor_rate": 0.60},
                {"config": c2, "cal_tok_per_s": 14300.0, "cal_edp": 0.47, "z_a3": -4.8, "z_a7": 5.5, "a5_precursor_rate": 0.42},
                {"config": c3, "cal_tok_per_s": 14150.0, "cal_edp": 0.48, "z_a3": -1.1, "z_a7": 0.9, "a5_precursor_rate": 0.03},
            ]
        )
        self.assertEqual(sel["Scalar-TokPerSec-Tuner"], "tps_hot")
        self.assertEqual(sel["Scalar-MeanWatt-EDP-Tuner"], "edp_cal")
        self.assertEqual(sel["SiliSense-Composite-Tuner"], "sili_opt")

        graded_ok = tuner.grade_h15c(
            tps_sustained_edp=[0.62, 0.61, 0.63, 0.62],
            edp0_sustained_edp=[0.55, 0.54, 0.56, 0.55],
            sili_sustained_edp=[0.49, 0.48, 0.50, 0.49],
            edp0_tail_drift=[0.16, 0.17, 0.15, 0.16],
            sili_tail_drift=[0.03, 0.03, 0.02, 0.03],
            selection_summary=sel,
        )
        self.assertEqual(graded_ok["verdict"], "CONFIRMED")

        graded_fail = tuner.grade_h15c(
            tps_sustained_edp=[0.50, 0.50, 0.51, 0.50],
            edp0_sustained_edp=[0.50, 0.50, 0.51, 0.50],
            sili_sustained_edp=[0.495, 0.496, 0.505, 0.495],
            edp0_tail_drift=[0.05, 0.05, 0.05, 0.05],
            sili_tail_drift=[0.05, 0.05, 0.05, 0.05],
            selection_summary=sel,
        )
        self.assertEqual(graded_fail["verdict"], "FALSIFIED")

        # Verify one-way HoloSphereStepTelemetry -> HoloSphereTuningProfile bridge contract & refusals
        bridge = SiliSenseHoloSphereBridge(base_profile=HoloSphereTuningProfile(backend="cuda_sm86", block_t=128, microbatch_size=8))
        for step_i in range(15):
            tel = HoloSphereStepTelemetry(
                step_idx=step_i,
                seq_len=512,
                batch_size=8,
                r_loops=3,
                backend="cuda_sm86",
                block_t=128,
                step_ms=22.0,
                tok_per_sec=186000.0,
                norm_drift_max=1e-6,
            )
            pw = 94.0 if step_i < 14 else 125.0
            prof_out = bridge.on_step_boundary(tel, fast_power_w=pw)
            if step_i == 14:
                self.assertGreater(prof_out.inter_step_cooldown_ms, 0.0)

        with self.assertRaises(SiliSenseValueError) as ctx_drift:
            bridge.on_step_boundary(
                HoloSphereStepTelemetry(15, 512, 8, 3, "cuda_sm86", 128, 22.0, 186000.0, norm_drift_max=0.05),
                fast_power_w=94.0,
            )
        self.assertEqual(ctx_drift.exception.code, "ERR_NORM_DRIFT_EXCEEDED")

    def test_07_prereg_sha256_pin_cli_parity_and_ast_hygiene(self) -> None:
        # Verify bundled PREREG-S115 file exists and matches pinned SHA-256 unconditionally in pure stdlib
        prereg_local = THIS_DIR / "PREREG_S115_SILICON_PHYSICS_FEEDBACK_OPTIMIZER.md"
        if not prereg_local.is_file() and _HAS_NUMPY_SCIPY:
            prereg_local = THIS_DIR.parent / PREREG_S115_RELPATH
        self.assertTrue(prereg_local.is_file(), f"Missing PREREG_S115 file at {prereg_local}")
        digest = hashlib.sha256(prereg_local.read_bytes()).hexdigest()
        self.assertEqual(len(EXPECTED_PREREG_SHA256), 64)
        self.assertEqual(digest, EXPECTED_PREREG_SHA256)
        self.assertIn(EXPECTED_PREREG_ID, prereg_local.read_text(encoding="utf-8"))

        # AST scan all .py files in track directory: 0 bare asserts, 0 shell=True, 0 home-path leaks
        home_prefix = "/" + "home/"
        py_files = sorted(THIS_DIR.glob("*.py"))
        self.assertGreaterEqual(len(py_files), 3)
        for py_path in py_files:
            src = py_path.read_text(encoding="utf-8")
            self.assertNotIn(home_prefix, src, f"Home path leak in {py_path.name}")
            tree = ast.parse(src, filename=str(py_path))
            for node in ast.walk(tree):
                self.assertNotIsInstance(node, ast.Assert, f"Bare assert in {py_path.name}")
                if isinstance(node, ast.keyword) and node.arg == "shell":
                    self.assertFalse(
                        isinstance(node.value, ast.Constant) and node.value.value is True,
                        f"shell=True forbidden in {py_path.name}",
                    )

        # CLI deterministic self-checks exit 0 when optional numpy/scipy stack is installed
        if _HAS_NUMPY_SCIPY:
            for script_name in ("s115_silisense_profiler.py", "s115_feedback_autotuner.py"):
                proc = subprocess.run(
                    [sys.executable, "-I", "-B", str(THIS_DIR / script_name), "--demo-synthetic"],
                    capture_output=True,
                    text=True,
                    timeout=30.0,
                    check=False,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn(EXPECTED_PREREG_ID, proc.stdout)

    @unittest.skipUnless(_HAS_NUMPY_SCIPY, "requires numpy and scipy")
    def test_08_dyadic_f32_floor_delay_bandwidth_lock_and_holosphere_wire_parity(self) -> None:
        # 1. Exact downward binary32 dyadic rounding (0-ULP overshoot across 200 non-dyadic decimals)
        for idx in range(1, 201):
            alpha = 0.5 + 0.0023 * float(idx)
            f32 = floor_to_exact_f32(alpha)
            self.assertLessEqual(f32, alpha)
            self.assertGreater(alpha - f32, -1e-9)
            self.assertLess(alpha - f32, 1e-6)

        # 2. Delay-Bandwidth Lock f * tau < 1/6: 80 ms EC psys fails at 5 Hz (> 2.0833 Hz), 5 ms RAPL passes up to 33.33 Hz
        ec_psys_5hz = check_delay_bandwidth_lock(f_control_hz=5.0, tau_sensor_sec=0.080)
        rapl_20hz = check_delay_bandwidth_lock(f_control_hz=20.0, tau_sensor_sec=0.005)
        self.assertFalse(ec_psys_5hz["stable"])
        self.assertTrue(rapl_20hz["stable"])

        # 3. Smooth L^{5/3} multi-rail shared-heatpipe norm & Lyapunov conductance monotonicity
        env0 = PrecursorThrottleGovernor.smooth_l53_multi_rail_envelope([0.0, -3.0])
        env1 = PrecursorThrottleGovernor.smooth_l53_multi_rail_envelope([8.0, 12.0])
        self.assertEqual(env0, 0.0)
        self.assertGreater(env1, 12.0)
        g1 = PrecursorThrottleGovernor.lyapunov_conductance_damping(1.0, 2.0, alpha=0.1, g_floor=0.70)
        g2 = PrecursorThrottleGovernor.lyapunov_conductance_damping(g1, 3.0, alpha=0.1, g_floor=0.70)
        self.assertLess(g1, 1.0)
        self.assertLessEqual(g2, g1)
        self.assertGreaterEqual(g2, floor_to_exact_f32(0.70))

        # 4. Gate Contract 4 Pre-Adaptation Residual Latch freezes raw open pathology prior to tuning
        prof = SiliSenseProfiler(mode="telemetry-only", n_iaaft=249, n_shifts=200, seed=77).profile_trace(
            make_synthetic_workload_trace("eager_microkernel", n_samples=320, seed=77)
        )
        latch = PreAdaptationResidualLatch.capture_from_profile(prof)
        self.assertTrue(latch.open_pathology)

        # 5. Canonical JSON & profile_sha256 parity (incl. 0 == 0.0 == -0.0 & f32 overflow/bool guards)
        for bad_alpha in (True, False, 1e39, 1e-46, -1.0, float("nan")):
            with self.assertRaises(SiliSenseValueError):
                floor_to_exact_f32(bad_alpha)  # type: ignore[arg-type]
        p_z_int = HoloSphereTuningProfile(inter_step_cooldown_ms=0)
        p_z_flt = HoloSphereTuningProfile(inter_step_cooldown_ms=0.0)
        p_z_neg = HoloSphereTuningProfile(inter_step_cooldown_ms=-0.0)
        self.assertEqual(p_z_int.profile_sha256(), p_z_flt.profile_sha256())
        self.assertEqual(p_z_flt.profile_sha256(), p_z_neg.profile_sha256())
        p_sili = HoloSphereTuningProfile(backend="cuda_sm86", block_t=128, microbatch_size=8, inter_step_cooldown_ms=1.5)
        roundtrip = HoloSphereTuningProfile.from_dict(json.loads(p_sili.to_json()))
        self.assertEqual(p_sili.profile_sha256(), roundtrip.profile_sha256())
        holo_root = THIS_DIR.parent.parent / "holosphere"
        if (holo_root / "holosphere" / "telemetry.py").is_file():
            proc = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    "-c",
                    f"import sys; sys.path.insert(0, {str(holo_root)!r}); "
                    f"from holosphere.telemetry import HoloSphereTuningProfile as P; "
                    f"p = P.from_dict({p_sili.to_dict()!r}); print(p.profile_sha256())",
                ],
                capture_output=True,
                text=True,
                timeout=10.0,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.strip(), p_sili.profile_sha256())


if __name__ == "__main__":
    unittest.main()
