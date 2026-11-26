#!/usr/bin/env python3
"""Synthetic positive-injection & anti-mirage null unit tests for s113_blind_anomaly_hunter.

Verifies:
  1. Pure colored/Gaussian noise across A1..A7 yields 0 false-positive surviving anomalies.
  2. Genuine non-textbook physical injections (quadratic phase locking A1, chiral 90-deg wave A2,
     sawtooth time-reversal asymmetry A3, 2D diagonal blank-wall wave A4, negative-lag precursor
     coincidence A5, uninvited high-Q spectral line A6, and linear-orthogonal quadratic residual A7)
     are each detected and out-of-sample split-half replicated (p_holm < 0.005).
"""
from __future__ import annotations

import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from s113_blind_anomaly_hunter import (
    _analyze_2d_stack_blind,
    apply_pooled_lens_family_holm,
    extract_phase_tested_candidates,
    lens_a1_bicoherence_and_pac,
    lens_a2_chiral_cross_spectrum,
    lens_a3_time_reversal_and_afterglow,
    lens_a5_rare_event_coincidence,
    lens_a6_uninvited_spectral_lines,
    lens_a7_nonlinear_residual_structure,
)


class BlindAnomalyHunterTests(unittest.TestCase):
    def test_pure_noise_null_produces_zero_false_positives(self) -> None:
        rng = np.random.default_rng(101)
        fs = 16000.0
        n = 16384
        # AR(1) colored linear Gaussian noise
        e = rng.standard_normal(n)
        x = np.empty(n, dtype=np.float64)
        x[0] = e[0]
        for i in range(1, n):
            x[i] = 0.6 * x[i - 1] + e[i]

        r1 = lens_a1_bicoherence_and_pac({"null": (x, fs, [])}, rng, n_screen=200, n_confirm=799)
        if len(r1["surviving_anomalies"]) != 0:
            raise AssertionError(f"Unexpected A1 FP: {r1['surviving_anomalies']}")

        # Rank-1 real common-mode EMI (including narrowband EMI line!) + independent mic noise -> 0 chiral anomalies
        t_null = np.arange(n) / fs
        cm = (rng.standard_normal(n) + 1.5 * np.cos(2.0 * math.pi * 2400.0 * t_null))[:, None]
        dmic_null = cm @ np.array([[1.0, 0.9, 1.1, 0.95]]) + 0.5 * rng.standard_normal((n, 4))
        r2 = lens_a2_chiral_cross_spectrum(dmic_null, fs, rng, n_confirm=799)
        if len(r2["surviving_anomalies"]) != 0:
            raise AssertionError(f"Unexpected A2 FP: {r2['surviving_anomalies']}")

        r3 = lens_a3_time_reversal_and_afterglow({"null": (x, fs)}, [], rng, n_screen=200, n_confirm=799)
        if len(r3["surviving_anomalies"]) != 0:
            raise AssertionError(f"Unexpected A3 FP: {r3['surviving_anomalies']}")

        # 2D white Poisson-like blank wall + static FPN + row banding -> 0 A4 anomalies after flat-field & row sub!
        t_f, h, w = 80, 48, 64
        fpn = rng.integers(90, 140, size=(1, h, w))
        row_band = rng.integers(-8, 9, size=(t_f, h, 1))
        shot = rng.integers(-4, 5, size=(t_f, h, w))
        stack_null = np.clip(fpn + row_band + shot, 0, 255).astype(np.uint8)
        _, s4 = _analyze_2d_stack_blind(stack_null, "null_cam", rng, n_confirm=799)
        if len(s4) != 0:
            raise AssertionError(f"Unexpected A4 FP: {s4}")

    def test_all_seven_lenses_detect_and_replicate_true_non_textbook_physics(self) -> None:
        rng = np.random.default_rng(2026)

        # A1: Quadratic phase-locked triad f3 = f1 + f2 with jittered phases across segments
        fs = 16000.0
        n = 32768
        t = np.arange(n) / fs
        f1, f2 = 1250.0, 2187.5
        phi1 = 0.8 * np.sin(2.0 * math.pi * 7.0 * t)
        phi2 = 0.8 * np.cos(2.0 * math.pi * 11.0 * t)
        sig_a1 = (
            np.cos(2.0 * math.pi * f1 * t + phi1)
            + np.cos(2.0 * math.pi * f2 * t + phi2)
            + 0.9 * np.cos(2.0 * math.pi * (f1 + f2) * t + phi1 + phi2)
            + 0.4 * rng.standard_normal(n)
        )
        r1 = lens_a1_bicoherence_and_pac({"triad": (sig_a1, fs, [])}, rng, n_screen=200, n_confirm=799)
        if len(r1["surviving_anomalies"]) < 1:
            raise AssertionError("A1 failed to detect quadratic phase-locked triad")

        # A2: Chiral 90-degree circulating wave across 4-ch DMIC
        f_chiral = 3750.0
        wt = 2.0 * math.pi * f_chiral * t
        dmic_chiral = np.column_stack([
            np.cos(wt),
            np.cos(wt - 0.5 * math.pi),
            np.cos(wt - math.pi),
            np.cos(wt - 1.5 * math.pi),
        ]) + 0.35 * rng.standard_normal((n, 4))
        r2 = lens_a2_chiral_cross_spectrum(dmic_chiral, fs, rng, n_confirm=799)
        if len(r2["surviving_anomalies"]) < 1:
            raise AssertionError(f"A2 failed to detect chiral wave: {r2}")

        # A3: Asymmetric relaxation oscillator (fast rise, slow exponential decay -> A(tau) != 0)
        saw = np.zeros(16384, dtype=np.float64)
        val = 0.0
        for i in range(len(saw)):
            val = 0.82 * val + (6.0 if rng.random() < 0.06 else 0.0)
            saw[i] = val + 0.1 * rng.standard_normal()
        r3 = lens_a3_time_reversal_and_afterglow({"relax": (saw, 1000.0)}, [], rng, n_screen=200, n_confirm=799)
        if len(r3["surviving_anomalies"]) < 1:
            raise AssertionError("A3 failed to detect time-reversal asymmetry")

        # A4: Subtle 2D diagonal standing/traveling wave on blank wall surviving row subtraction
        t_f, h, w = 80, 48, 64
        yy, xx = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
        wave_stack = np.empty((t_f, h, w), dtype=np.uint8)
        for ti in range(t_f):
            w2d = 5.0 * np.cos(2.0 * math.pi * (3.0 * yy / h + 5.0 * xx / w) + 0.7 * ti)
            wave_stack[ti] = np.clip(128.0 + w2d + 1.5 * rng.standard_normal((h, w)), 0, 255).astype(np.uint8)
        _, s4 = _analyze_2d_stack_blind(wave_stack, "diag_wave", rng, n_confirm=799)
        if len(s4) < 1:
            raise AssertionError("A4 failed to detect 2D diagonal blank-wall wave")

        # A5: Aperiodic Poisson rare precursor spikes (dmic spikes 160 ms BEFORE pkg_w spikes!)
        n_100 = 2400
        dmic_s = 0.2 * rng.standard_normal(n_100)
        pkg_s = 0.2 * rng.standard_normal(n_100)
        pos = 60
        while pos < n_100 - 40:
            dmic_s[pos] += 9.0
            pkg_s[pos + 16] += 9.0
            pos += int(rng.integers(45, 130))
        r5 = lens_a5_rare_event_coincidence({"dmic_hf": dmic_s, "pkg_w": pkg_s}, rng, dt_s=0.01, n_confirm=799)
        if len(r5["surviving_anomalies"]) < 1:
            raise AssertionError(f"A5 failed to detect precursor spikes: {r5}")

        # A6: Uninvited high-Q spectral line at 5443 Hz (13 Hz away from 30/60 Hz combs)
        sig_a6 = 0.45 * np.sin(2.0 * math.pi * 5443.0 * t) + rng.standard_normal(n)
        r6 = lens_a6_uninvited_spectral_lines({"idle": (sig_a6, fs, [], True)}, None, 0.0, rng, n_confirm=799)
        if len(r6["surviving_anomalies"]) < 1:
            raise AssertionError(f"A6 failed to detect uninvited high-Q line: {r6}")

        # A7: Purely non-linear zero-covariance coupling y(t) = x(t)^2 - 1
        n7 = 1000
        xa = rng.standard_normal(n7)
        xb = (xa * xa - 1.0) + 0.25 * rng.standard_normal(n7)
        r7 = lens_a7_nonlinear_residual_structure({"dmic_a": xa, "dark_w": xb}, rng, n_screen=200, n_confirm=799)
        if len(r7["surviving_anomalies"]) < 1:
            raise AssertionError("A7 failed to detect zero-covariance nonlinear residual coupling")

    def test_pooled_lens_family_holm_and_raw_p_lookup(self) -> None:
        # 2-member IAAFT family (A3) at p=1/800 survives (< 0.005: 2/800 = 0.0025),
        # while 4-member family (A1/A4) at p=1/800 is rejected (4/800 = 0.005 >= 0.005).
        phase_rows = {
            "A": [
                {"lens": "A3_TIME_REVERSAL_ASYMMETRY", "half2_p_iaaft": 0.00125, "replicated_anomaly": True},
                {"lens": "A1_BICOHERENCE", "half2_p_iaaft": 0.00125, "replicated_anomaly": True},
                {"lens": "A1_BICOHERENCE", "half2_p_iaaft": 0.00125, "replicated_anomaly": True},
            ],
            "E2": [
                {"lens": "A3_TIME_REVERSAL_ASYMMETRY", "half2_p_iaaft": 0.00125, "replicated_anomaly": True},
                {"lens": "A1_BICOHERENCE", "half2_p_iaaft": 0.00125, "replicated_anomaly": True},
                {"lens": "A1_BICOHERENCE", "half2_p_iaaft": 0.00125, "replicated_anomaly": True},
            ],
        }
        surv_by_ph, rej, counts, summary, diag = apply_pooled_lens_family_holm(["A", "E2"], phase_rows)
        if counts != {"A3_TIME_REVERSAL_ASYMMETRY": 2}:
            raise AssertionError(f"Unexpected pooled counts: {counts}")
        if len(rej) != 4 or any(r["replicated_anomaly"] is not False for r in rej):
            raise AssertionError(f"Expected 4 rejected A1 rows, got {rej}")
        if abs(surv_by_ph["A"][0]["half2_p_holm"] - 0.0025) > 1e-9:
            raise AssertionError(f"Bad pooled Holm p for A3: {surv_by_ph['A'][0]}")
        if abs(rej[0]["half2_p_holm"] - 0.005) > 1e-9:
            raise AssertionError(f"Bad pooled Holm p for A1: {rej[0]}")
        if summary["A1_BICOHERENCE"]["family_size"] != 4 or diag["total_surviving_all_lenses"] != 6:
            raise AssertionError(f"Unexpected summary/diag: {summary} / {diag}")

        # Verify extract_phase_tested_candidates includes non-surviving tested_candidates,
        # nested subphases, afterglow rep2_p_iaaft, cocycle_probes, and intermod_probes.
        phase_a_mock = {
            "phase": "A",
            "lenses": {
                "A3": {
                    "tested_candidates": [
                        {"lens": "A3_TIME_REVERSAL_ASYMMETRY", "half2_p_iaaft": 0.00125, "same_sign_replicated": True, "half2_z_iaaft": 4.2, "replicated_anomaly": True},
                        {"lens": "A3_TIME_REVERSAL_ASYMMETRY", "half2_p_iaaft": 0.60, "same_sign_replicated": True, "half2_z_iaaft": -0.2, "replicated_anomaly": False},
                        {"lens": "A3_TIME_REVERSAL_ASYMMETRY", "half2_p_iaaft": 0.70, "same_sign_replicated": False, "half2_z_iaaft": -0.5, "replicated_anomaly": False},
                        {"lens": "A3_POST_LOAD_AFTERGLOW", "rep2_p_iaaft": 0.42625, "rep2_p_holm": 0.42625, "rep2_z_iaaft": 0.27, "replicated_anomaly": False},
                    ],
                    "surviving_anomalies": [],
                }
            },
        }
        phase_e2_mock = {
            "phase": "E2",
            "subphases": {
                "E2B": {
                    "lenses": {
                        "A3": {
                            "tested_candidates": [
                                {"lens": "A3_TIME_REVERSAL_ASYMMETRY", "half2_p_iaaft": 0.00125, "same_sign_replicated": True, "half2_z_iaaft": 8.1, "replicated_anomaly": True},
                            ]
                        },
                        "A1_A2_STRUCTURED_PROBES": {
                            "cocycle_probes": [{"lens": "A2_TDOA_COCYCLE_AND_HOLONOMY", "half2_p_surr": 0.965, "half1_phase_holonomy_rad": 0.1, "half2_phase_holonomy_rad": 0.1, "half2_cocycle_defect_us": 25.0, "half2_z_surr": -1.2}],
                            "intermod_probes": [{"lens": "A1_CPU_GPU_INTERMODULATION", "half2_p_surr": 0.45875, "half1_prominence_x_median": 1.1, "half2_z_surr": 0.03}],
                        },
                    }
                }
            },
        }
        rows_full = {
            "A": extract_phase_tested_candidates(phase_a_mock),
            "E2": extract_phase_tested_candidates(phase_e2_mock),
        }
        surv2, rej2, counts2, summary2, _ = apply_pooled_lens_family_holm(["A", "E2"], rows_full)
        # Because A3_TIME_REVERSAL_ASYMMETRY has 4 Half-2-tested candidates (not 2 pre-filtered survivors),
        # min p_Holm = 4 * 0.00125 = 0.005 >= 0.005 -> 0 pooled survivors!
        if counts2 != {} or sum(len(v) for v in surv2.values()) != 0 or len(rej2) != 7:
            raise AssertionError(f"Unfiltered m=4 A3 family must yield 0 survivors: {counts2} / {surv2}")
        if summary2["A3_TIME_REVERSAL_ASYMMETRY"]["min_p_holm"] != 0.005:
            raise AssertionError(f"Expected min_p_holm=0.005 for m=4 A3, got {summary2['A3_TIME_REVERSAL_ASYMMETRY']}")


if __name__ == "__main__":
    unittest.main()
