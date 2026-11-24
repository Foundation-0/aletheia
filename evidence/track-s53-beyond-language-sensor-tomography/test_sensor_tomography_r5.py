#!/usr/bin/env python3
"""Track S53 Phases 1 & 2 R1-R5 Fail-Closed Verification Suite (Zero Bare Asserts, Zero Floats).

Covers:
  1. Synthetic mathematical positive/negative controls (time-symmetric diffusive
     system -> A^2 == 0, one-way causal lag chain -> A^2 > 0 & dir == +1, hidden
     common-driver dark-mode Schur residual -> SPD & low PR, decoupled channels
     -> zero residual coupling, singular matrix rejection).
  2. Exact Stage-A affine + permutation gauge invariance across R^2, partial
     correlation P^2, Schur dark-mode invariants, blind clustering ARI == 1, and
     time-reversal asymmetry.
  3. Exhaustive planted tamper kills covering EVERY trust-boundary guard in
     `sensor_tomography_audit.py`: schema, payload/raw/X SHA-256, Phase 1 &
     Phase 2 privacy policies (sudo, camera, mic, consent window, covariate),
     matrix dimensions, active/zero-var indices, ridge bounds, coupling &
     modularity & ARI, gauge diff & flags, blind & physical Schur, asymmetry
     & lag bounds, SI-2019 Landauer erasure bridge, exact circular-shift null,
     and sampled IAAFT bounds.
  4. Zone-B filesystem, parser, exact-rational, integer-bit/digit boundary,
     and argv boundary defenses (symlink leaf/ancestor, missing ancestor,
     parent traversal, root path, scratch FIFO via `os.mkfifo` — zero system
     device-node writes, unreadable `chmod 000`, exact byte cap, CRLF, BOM,
     NUL, surrogates, float/NaN, duplicate keys, exact depth 64 vs 65, exact
     bit limit 3321 vs 3322, exact digit limit 1000 vs 1001, structured exit
     code 2 with zero raw tracebacks).
  5. Live frozen snapshot & certificate verification across ALL THREE captured
     artifacts (`pre_rapl_baseline_certificate.json`, Phase 1 Post-RAPL
     `sensor_tomography_certificate.json`, and Phase 2 Controlled Audio+RAPL
     `phase2_controlled_certificate.json`).

Verification modes (standard 3-mode isolated parity):
  python3 -I -B test_sensor_tomography_r5.py
  python3 -I -O -B test_sensor_tomography_r5.py
  python3 -I -B -W error test_sensor_tomography_r5.py
"""

from __future__ import annotations

import copy
import errno
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import sensor_tomography_audit as audit


def _build_synthetic_snapshot(*, with_rapl: bool = True, phase2_audio: bool = False) -> tuple[dict, bytes, str]:
    """Build a compact deterministic synthetic multi-module integer sensor snapshot."""
    t_len = 24
    h_driver = [10, 14, 18, 22, 19, 15, 11, 13, 17, 23, 25, 20, 16, 12, 14, 19, 24, 21, 17, 13, 15, 20, 22, 18]
    g_driver = [50, 52, 49, 55, 60, 58, 53, 51, 56, 62, 59, 54, 50, 53, 57, 61, 58, 52, 49, 54, 59, 63, 57, 51]
    noise_a = [1, -1, 0, 1, -1, 0, 1, -1, 0, 1, -1, 0, 1, -1, 0, 1, -1, 0, 1, -1, 0, 1, -1, 0]
    noise_b = [0, 1, -1, 0, 1, -1, 0, 1, -1, 0, 1, -1, 0, 1, -1, 0, 1, -1, 0, 1, -1, 0, 1, -1]

    rows = []
    for t in range(t_len):
        c0 = 40000 + 200 * h_driver[t] + 15 * noise_a[t]
        c1 = 41000 + 190 * h_driver[t] + 15 * noise_b[t]
        c2 = 3000 + 40 * (h_driver[t - 2] if t >= 2 else h_driver[0])
        c3 = 800 + 30 * g_driver[t] + 5 * noise_a[t]
        c4 = 50 + 2 * (g_driver[t - 1] if t >= 1 else g_driver[0]) + noise_b[t]
        c5 = 35000 + 100 * h_driver[t] + 10 * g_driver[t]
        c6 = 0  # stationary zero-variance channel
        row = [c0, c1, c2, c3, c4, c5, c6]
        if with_rapl:
            row.append(12_000_000 + 500_000 * h_driver[t] + 50_000 * noise_a[t])
        rows.append(row)

    channels = [
        {"channel_id": 0, "source": "synthetic", "device": "coretemp", "field": "temp1_input", "label": "Package id 0", "unit_scale": "temp_mC", "module": "cpu_die_thermal"},
        {"channel_id": 1, "source": "synthetic", "device": "coretemp", "field": "temp2_input", "label": "Core 0", "unit_scale": "temp_mC", "module": "cpu_die_thermal"},
        {"channel_id": 2, "source": "synthetic", "device": "asus", "field": "fan1_input", "label": "cpu_fan", "unit_scale": "fan_rpm", "module": "mechanical_cooling"},
        {"channel_id": 3, "source": "synthetic", "device": "gpu0", "field": "gpu_power_cW", "label": "gpu_power_cW", "unit_scale": "power_cW", "module": "gpu_electromechanical"},
        {"channel_id": 4, "source": "synthetic", "device": "gpu0", "field": "gpu_temp_C", "label": "gpu_temp_C", "unit_scale": "temp_C", "module": "gpu_electromechanical"},
        {"channel_id": 5, "source": "synthetic", "device": "thermal_zone0", "field": "temp", "label": "acpitz", "unit_scale": "temp_mC", "module": "chassis_acpi_thermal"},
        {"channel_id": 6, "source": "synthetic", "device": "iio0", "field": "in_z_raw", "label": "z0", "unit_scale": "raw_int", "module": "chassis_hinge_iio"},
    ]
    if with_rapl:
        channels.append(
            {
                "channel_id": 7,
                "source": "sysfs_rapl_delta",
                "device": "intel-rapl:0",
                "field": "delta_energy_uj",
                "label": "intel-rapl:0:package-0_dE_uJ",
                "unit_scale": "energy_uJ_per_step",
                "module": "cpu_rapl_energy_uj",
            }
        )
    snap = {
        "schema_version": audit.SCHEMA_RAW,
        "capture_utc_epoch_s": 1795470000,
        "cadence_hz": 2,
        "nominal_interval_ms": 500,
        "elapsed_ms": 11500,
        "sample_count": t_len,
        "channel_count": len(channels),
        "sudo_used": False,
        "timestamps_ms": [500 * t for t in range(t_len)],
        "X_anonymous": rows,
        "held_out_ground_truth_channels": channels,
        "x_anonymous_sha256": hashlib.sha256(audit.canonical_json_bytes(rows)).hexdigest(),
    }
    if phase2_audio:
        snap["audio_authorized_only"] = True
        snap["mic_accessed"] = True
        snap["camera_accessed"] = False
        snap["audio_consent_window"] = "2026-11-24 06:48-07:48 CST"
        snap["room_noise_covariate"] = "room_quiet_synthetic"
    else:
        snap["mic_cam_accessed"] = False
        snap["camera_accessed"] = False
    raw_bytes = audit.canonical_json_bytes(snap)
    return snap, raw_bytes, hashlib.sha256(raw_bytes).hexdigest()


def _resign(cert: dict) -> dict:
    c2 = copy.deepcopy(cert)
    c2["payload_sha256"] = hashlib.sha256(audit.canonical_json_bytes(c2["payload"])).hexdigest()
    return c2


def _make_valid_synthetic_pair(*, with_rapl: bool = True, phase2_audio: bool = False) -> tuple[dict, str, dict]:
    import sensor_tomography_probe as probe

    snap, _raw_bytes, raw_sha = _build_synthetic_snapshot(with_rapl=with_rapl, phase2_audio=phase2_audio)
    cert = probe.analyze_snapshot(snap, raw_sha)
    # Inject deterministic synthetic sampled IAAFT block so stdlib `-I` mode also exercises IAAFT bounds
    cert["payload"]["adversarial_nulls_and_replication"]["iaaft_null_sampled"] = {
        "oracle_class": "sampled",
        "method": "synthetic_iaaft_check",
        "available": True,
        "n_surrogates": 200,
        "p_mean_r2_q": "1",
        "p_mean_a2_q": "1",
        "z_squared_mean_r2_q": "0",
        "z_squared_mean_a2_q": "0",
    }
    cert = _resign(cert)
    return snap, raw_sha, cert


class TestTrackS53BeyondLanguageR5(unittest.TestCase):
    def test_01_builtin_self_test_and_math_controls(self) -> None:
        res = audit.run_self_test()
        self.assertTrue(res["self_test_passed"])
        self.assertEqual(res["symmetric_control_a2_q"], "0")
        self.assertEqual(res["causal_control_dir"], 1)
        self.assertGreater(audit.parse_exact_q(res["causal_control_a2_q"], "c"), Fraction(0))
        self.assertLess(audit.parse_exact_q(res["dark_mode_control_pr_q"], "pr"), Fraction(3, 2))
        self.assertEqual(res["tamper_controls_killed"], 5)

        # Exact matrix inversion boundaries: identity (piv_r == 0) succeeds, singular fails closed
        inv_id = audit._indep_invert_q([[Fraction(1), Fraction(0)], [Fraction(0), Fraction(1)]])
        self.assertEqual(inv_id, [[Fraction(1), Fraction(0)], [Fraction(0), Fraction(1)]])
        with self.assertRaises(audit.SensorAuditError) as ctx_sg:
            audit._indep_invert_q([[Fraction(0), Fraction(0)], [Fraction(0), Fraction(0)]])
        self.assertEqual(ctx_sg.exception.code, "SINGULAR_MATRIX")

    def test_02_decoupled_schur_control_has_near_full_pr(self) -> None:
        rows = [
            [Fraction(1), Fraction(1), Fraction(1)],
            [Fraction(1), Fraction(-1), Fraction(-1)],
            [Fraction(-1), Fraction(1), Fraction(-1)],
            [Fraction(-1), Fraction(-1), Fraction(1)],
            [Fraction(1), Fraction(1), Fraction(1)],
            [Fraction(1), Fraction(-1), Fraction(-1)],
            [Fraction(-1), Fraction(1), Fraction(-1)],
            [Fraction(-1), Fraction(-1), Fraction(1)],
        ]
        _, cov = audit._indep_cov_and_centered(rows)
        sch = audit._indep_schur(cov, [0, 1], [2], Fraction(1, 20))
        self.assertEqual(sch["inertia"], [2, 0, 0])
        self.assertEqual(sch["off_rho2_mean"], Fraction(0))
        self.assertEqual(sch["pr"], Fraction(2))
        self.assertEqual(sch["compression"], Fraction(1))

    def test_03_exact_rational_and_int_boundary_guards(self) -> None:
        # Exact boundary values must PASS (kills <= -> < and >= -> > mutants)
        max_bit_val = (1 << audit.MAX_INT_BITS) - 1
        self.assertEqual(audit.parse_exact_q(str(max_bit_val), "max_bits"), Fraction(max_bit_val, 1))
        self.assertEqual(audit._require_exact_int(max_bit_val, "max_bits", lo=0, hi=max_bit_val), max_bit_val)
        self.assertEqual(audit._require_exact_int(0, "lo_eq", lo=0, hi=10), 0)
        self.assertEqual(audit._require_exact_int(10, "hi_eq", lo=0, hi=10), 10)
        self.assertEqual(audit.parse_exact_q("-3/5", "neg_num"), Fraction(-3, 5))

        # Exact digit cap = 1000 vs 1001 in JSON int parser & bit cap 3321 vs 3322
        max_bit_json = f'{{"v":{max_bit_val}}}\n'.encode("utf-8")
        self.assertEqual(audit.parse_strict_json_bytes(max_bit_json, "max_bit_json")["v"], max_bit_val)
        over_bit_json = f'{{"v":{1 << audit.MAX_INT_BITS}}}\n'.encode("utf-8")
        with self.assertRaises(audit.SensorAuditError) as ctx_ob:
            audit.parse_strict_json_bytes(over_bit_json, "over_bit")
        self.assertEqual(ctx_ob.exception.code, "INT_BIT_LIMIT")

        exact_1000_digits = "1" + ("0" * 999)
        self.assertEqual(len(exact_1000_digits), audit.MAX_INT_DIGITS)
        # 10^999 has 3319 bits <= 3321 and 1000 digits == MAX_INT_DIGITS (kills <= -> < on MAX_INT_DIGITS)
        self.assertEqual(
            audit.parse_strict_json_bytes(f'{{"v":{exact_1000_digits}}}\n'.encode("utf-8"), "d1000")["v"],
            int(exact_1000_digits),
        )
        self.assertEqual(audit.parse_exact_q(exact_1000_digits, "q1000"), Fraction(int(exact_1000_digits), 1))

        over_digits = "1" + ("0" * 1000)
        with self.assertRaises(audit.SensorAuditError) as ctx_odj:
            audit.parse_strict_json_bytes(f'{{"v":{over_digits}}}\n'.encode("utf-8"), "d1001")
        self.assertEqual(ctx_odj.exception.code, "INT_DIGIT_LIMIT")
        with self.assertRaises(audit.SensorAuditError) as ctx_odq:
            audit.parse_exact_q(over_digits, "q1001")
        self.assertEqual(ctx_odq.exception.code, "INT_DIGIT_LIMIT")

        # All parse_exact_q malformed / non-canonical / negative-denom / bit-limit rejections (exact typed codes)
        for bad_q, expected_code in (
            (123, "INVALID_Q_TYPE"),
            ("", "EMPTY_Q"),
            (" 1/2", "INVALID_Q_SPACING"),
            ("1/2 ", "INVALID_Q_SPACING"),
            ("1/2/3", "INVALID_Q_FORMAT"),
            ("1/", "INVALID_Q_FORMAT"),
            ("/2", "INVALID_Q_FORMAT"),
            ("-", "INT_DIGIT_LIMIT"),
            ("1/-2", "INVALID_Q_SIGN"),
            ("1a/2", "INVALID_Q_DIGIT"),
            ("01/2", "LEADING_ZERO_Q"),
            ("2/4", "NONCANONICAL_Q"),
            ("1/0", "ZERO_DENOMINATOR"),
            (str(1 << audit.MAX_INT_BITS), "INT_BIT_LIMIT"),
        ):
            with self.subTest(bad_q=bad_q):
                with self.assertRaises(audit.SensorAuditError) as ctx_bq:
                    audit.parse_exact_q(bad_q, "bad_q")
                self.assertEqual(ctx_bq.exception.code, expected_code)

        # _require_exact_int rejections (bool subclass, bit limit, bounds)
        with self.assertRaises(audit.SensorAuditError):
            audit._require_exact_int(True, "bool_int")
        with self.assertRaises(audit.SensorAuditError):
            audit._require_exact_int(1 << audit.MAX_INT_BITS, "big_int")
        with self.assertRaises(audit.SensorAuditError):
            audit._require_exact_int(-1, "below_lo", lo=0)
        with self.assertRaises(audit.SensorAuditError):
            audit._require_exact_int(11, "above_hi", hi=10)

    def test_04_exhaustive_certificate_and_privacy_tamper_matrix(self) -> None:
        snap, raw_sha, cert = _make_valid_synthetic_pair(with_rapl=True, phase2_audio=False)
        verdict = audit.verify_certificate_dict(snap, raw_sha, cert)
        self.assertTrue(verdict["valid"])
        self.assertTrue(verdict["gauge_invariance_exact"])
        self.assertEqual(verdict["dynamic_channel_count"], 7)

        # Also validate Phase 2 authorized audio mode succeeds
        snap2, raw_sha2, cert2 = _make_valid_synthetic_pair(with_rapl=True, phase2_audio=True)
        verdict2 = audit.verify_certificate_dict(snap2, raw_sha2, cert2)
        self.assertTrue(verdict2["valid"])

        def _mut_cert(fn) -> tuple[dict, str, dict]:
            c = copy.deepcopy(cert)
            fn(c)
            return snap, raw_sha, _resign(c)

        def _mut_raw(fn) -> tuple[dict, str, dict]:
            s = copy.deepcopy(snap)
            fn(s)
            return s, raw_sha, cert

        def _mut_raw2(fn) -> tuple[dict, str, dict]:
            s = copy.deepcopy(snap2)
            fn(s)
            return s, raw_sha2, cert2

        p0 = cert["payload"]
        tamper_cases: list[tuple[str, tuple[dict, str, dict]]] = [
            # Top-level schema, payload type, SHA bindings
            ("bad_cert_schema", (snap, raw_sha, {**cert, "schema_version": "bad"})),
            ("bad_raw_schema", _mut_raw(lambda s: s.__setitem__("schema_version", "bad"))),
            ("bad_payload_type", (snap, raw_sha, {**cert, "payload": []})),
            ("unsigned_payload_edit", (snap, raw_sha, {**cert, "payload_sha256": "0" * 64})),
            ("raw_sha_mismatch", (snap, "0" * 64, cert)),
            ("bad_x_rows_short", _mut_raw(lambda s: s.__setitem__("X_anonymous", [[1]] * 3))),
            ("bad_gt_ch_short", _mut_raw(lambda s: s.__setitem__("held_out_ground_truth_channels", []))),
            ("raw_x_sha_mismatch", _mut_raw(lambda s: s.__setitem__("x_anonymous_sha256", "0" * 64))),
            ("cert_x_sha_mismatch", _mut_cert(lambda c: c["payload"].__setitem__("x_anonymous_sha256", "0" * 64))),
            # Phase 1 & Phase 2 privacy policy guards
            ("sudo_true", _mut_raw(lambda s: s.__setitem__("sudo_used", True))),
            ("p1_mic_cam_true", _mut_raw(lambda s: s.__setitem__("mic_cam_accessed", True))),
            ("p1_cam_true", _mut_raw(lambda s: s.__setitem__("camera_accessed", True))),
            ("p2_cam_true", _mut_raw2(lambda s: s.__setitem__("camera_accessed", True))),
            ("p2_mic_false", _mut_raw2(lambda s: s.__setitem__("mic_accessed", False))),
            ("p2_empty_consent", _mut_raw2(lambda s: s.__setitem__("audio_consent_window", ""))),
            ("p2_empty_cov", _mut_raw2(lambda s: s.__setitem__("room_noise_covariate", ""))),
            # Matrix width & dynamic indices & ridge
            ("row_width_mismatch", _mut_raw(lambda s: s["X_anonymous"][0].append(1))),
            ("active_idx_lie", _mut_cert(lambda c: c["payload"].__setitem__("active_orig_indices", [0, 1]))),
            ("zvar_idx_lie", _mut_cert(lambda c: c["payload"].__setitem__("zero_variance_orig_indices", []))),
            ("dyn_count_lie", _mut_cert(lambda c: c["payload"].__setitem__("dynamic_channel_count", 6))),
            ("ridge_zero", _mut_cert(lambda c: c["payload"].__setitem__("ridge_lambda_q", "0"))),
            ("ridge_neg", _mut_cert(lambda c: c["payload"].__setitem__("ridge_lambda_q", "-1/20"))),
            ("ridge_zero_denom", _mut_cert(lambda c: c["payload"].__setitem__("ridge_lambda_q", "1/0"))),
            # Stage B coupling & blind clustering
            ("missing_coupling_sec", _mut_cert(lambda c: c["payload"].__setitem__("stage_b_coupling_and_blind_clustering", []))),
            ("sigma_reg_inertia_lie", _mut_cert(lambda c: c["payload"]["stage_b_coupling_and_blind_clustering"].__setitem__("sigma_reg_inertia", [1, 0, 0]))),
            ("sigma_reg_spd_lie", _mut_cert(lambda c: c["payload"]["stage_b_coupling_and_blind_clustering"].__setitem__("sigma_reg_is_spd", False))),
            ("mean_r2_lie", _mut_cert(lambda c: c["payload"]["stage_b_coupling_and_blind_clustering"].__setitem__("mean_pair_r2_q", "0"))),
            ("blind_r2_labels_lie", _mut_cert(lambda c: c["payload"]["stage_b_coupling_and_blind_clustering"].__setitem__("blind_r2_labels", [0] * 7))),
            ("mod_r2_lie", _mut_cert(lambda c: c["payload"]["stage_b_coupling_and_blind_clustering"].__setitem__("blind_r2_modularity_q", "0"))),
            ("blind_p2_labels_lie", _mut_cert(lambda c: c["payload"]["stage_b_coupling_and_blind_clustering"].__setitem__("blind_p2_labels", [0] * 7))),
            ("mod_p2_lie", _mut_cert(lambda c: c["payload"]["stage_b_coupling_and_blind_clustering"].__setitem__("blind_p2_modularity_q", "0"))),
            ("ari_r2_lie", _mut_cert(lambda c: c["payload"]["stage_b_coupling_and_blind_clustering"].__setitem__("held_out_ari_r2_q", "0"))),
            ("ari_p2_lie", _mut_cert(lambda c: c["payload"]["stage_b_coupling_and_blind_clustering"].__setitem__("held_out_ari_p2_q", "0"))),
            # Stage A gauge section
            ("missing_gauge_sec", _mut_cert(lambda c: c["payload"].__setitem__("stage_a_gauge_invariance", None))),
            ("max_r2_diff_lie", _mut_cert(lambda c: c["payload"]["stage_a_gauge_invariance"].__setitem__("max_r2_diff_q", "1/1000"))),
            ("max_p2_diff_lie", _mut_cert(lambda c: c["payload"]["stage_a_gauge_invariance"].__setitem__("max_partial_p2_diff_q", "1/1000"))),
            ("gauge_ari_lie", _mut_cert(lambda c: c["payload"]["stage_a_gauge_invariance"].__setitem__("blind_cluster_gauge_ari_q", "0"))),
            ("gauge_schur_false", _mut_cert(lambda c: c["payload"]["stage_a_gauge_invariance"].__setitem__("schur_gauge_exact_match", False))),
            ("gauge_flag_false", _mut_cert(lambda c: c["payload"]["stage_a_gauge_invariance"].__setitem__("all_gauge_invariants_exact", False))),
            ("gauge_asym_flag_false", _mut_cert(lambda c: c["payload"]["stage_a_gauge_invariance"].__setitem__("asymmetry_gauge_exact_match", False))),
            # Stage B Schur dark modes (blind + physical)
            ("missing_schur_sec", _mut_cert(lambda c: c["payload"].__setitem__("stage_b_schur_dark_modes", None))),
            ("bad_schur_idx", _mut_cert(lambda c: c["payload"]["stage_b_schur_dark_modes"].__setitem__("blind_largest_cluster_a_indices", "bad"))),
            ("missing_blind_schur", _mut_cert(lambda c: c["payload"]["stage_b_schur_dark_modes"].__setitem__("blind_partition_schur", None))),
            ("blind_schur_inertia", _mut_cert(lambda c: c["payload"]["stage_b_schur_dark_modes"]["blind_partition_schur"].__setitem__("schur_inertia", [0, 0, 0]))),
            ("blind_schur_eta", _mut_cert(lambda c: c["payload"]["stage_b_schur_dark_modes"]["blind_partition_schur"].__setitem__("mean_unexplained_variance_eta_q", "0"))),
            ("blind_schur_raw_r2", _mut_cert(lambda c: c["payload"]["stage_b_schur_dark_modes"]["blind_partition_schur"].__setitem__("mean_raw_offdiag_r2_q", "1"))),
            ("blind_schur_rho2", _mut_cert(lambda c: c["payload"]["stage_b_schur_dark_modes"]["blind_partition_schur"].__setitem__("mean_residual_offdiag_rho2_q", "0"))),
            ("blind_schur_pr", _mut_cert(lambda c: c["payload"]["stage_b_schur_dark_modes"]["blind_partition_schur"].__setitem__("residual_participation_ratio_q", "1"))),
            ("phys_schur_dropped", _mut_cert(lambda c: c["payload"]["stage_b_schur_dark_modes"].__setitem__("physical_partition_schur", None))),
            ("phys_schur_is_list", _mut_cert(lambda c: c["payload"]["stage_b_schur_dark_modes"].__setitem__("physical_partition_schur", []))),
            ("phys_schur_idx_a", _mut_cert(lambda c: c["payload"]["stage_b_schur_dark_modes"].__setitem__("physical_thermal_a_indices", [0, 1]))),
            ("phys_schur_idx_b", _mut_cert(lambda c: c["payload"]["stage_b_schur_dark_modes"].__setitem__("physical_driver_b_indices", [2, 3]))),
            ("phys_schur_inertia", _mut_cert(lambda c: c["payload"]["stage_b_schur_dark_modes"]["physical_partition_schur"].__setitem__("schur_inertia", [0, 0, 0]))),
            ("phys_schur_eta", _mut_cert(lambda c: c["payload"]["stage_b_schur_dark_modes"]["physical_partition_schur"].__setitem__("mean_unexplained_variance_eta_q", "0"))),
            ("phys_schur_raw_r2", _mut_cert(lambda c: c["payload"]["stage_b_schur_dark_modes"]["physical_partition_schur"].__setitem__("mean_raw_offdiag_r2_q", "1"))),
            ("phys_schur_rho2", _mut_cert(lambda c: c["payload"]["stage_b_schur_dark_modes"]["physical_partition_schur"].__setitem__("mean_residual_offdiag_rho2_q", "0"))),
            ("phys_schur_pr", _mut_cert(lambda c: c["payload"]["stage_b_schur_dark_modes"]["physical_partition_schur"].__setitem__("residual_participation_ratio_q", "1"))),
            # Stage B time-reversal asymmetry (all lags incl. non-primary)
            ("missing_asym_sec", _mut_cert(lambda c: c["payload"].__setitem__("stage_b_time_reversal_dissipation", None))),
            ("primary_tau_lie", _mut_cert(lambda c: c["payload"]["stage_b_time_reversal_dissipation"].__setitem__("primary_tau", 1))),
            ("missing_by_lag", _mut_cert(lambda c: c["payload"]["stage_b_time_reversal_dissipation"].__setitem__("by_lag", {}))),
            ("lag_rec_list", _mut_cert(lambda c: c["payload"]["stage_b_time_reversal_dissipation"]["by_lag"].__setitem__("2", []))),
            ("lag_tau_lie", _mut_cert(lambda c: c["payload"]["stage_b_time_reversal_dissipation"]["by_lag"]["5"].__setitem__("tau", 99))),
            ("non_primary_lag_a2_lie", _mut_cert(lambda c: c["payload"]["stage_b_time_reversal_dissipation"]["by_lag"]["5"].__setitem__("mean_asymmetry_a2_q", "0"))),
            ("mean_a2_lie", _mut_cert(lambda c: c["payload"]["stage_b_time_reversal_dissipation"]["by_lag"]["2"].__setitem__("mean_asymmetry_a2_q", "0"))),
            ("max_a2_lie", _mut_cert(lambda c: c["payload"]["stage_b_time_reversal_dissipation"]["by_lag"]["2"].__setitem__("max_asymmetry_a2_q", "0"))),
            ("mean_gamma_lie", _mut_cert(lambda c: c["payload"]["stage_b_time_reversal_dissipation"]["by_lag"]["2"].__setitem__("mean_dissipation_gamma_q", "0"))),
            # Stage B Landauer thermodynamic bridge
            ("landauer_dropped", _mut_cert(lambda c: c["payload"]["stage_b_time_reversal_dissipation"].__setitem__("landauer_thermodynamic_bridge", None))),
            ("bad_landauer_class", _mut_cert(lambda c: c["payload"]["stage_b_time_reversal_dissipation"]["landauer_thermodynamic_bridge"].__setitem__("oracle_class", "sampled"))),
            ("missing_rapl_in_gt", _mut_raw(lambda s: s["held_out_ground_truth_channels"][7].__setitem__("module", "other"))),
            ("landauer_energy_lie", _mut_cert(lambda c: c["payload"]["stage_b_time_reversal_dissipation"]["landauer_thermodynamic_bridge"].__setitem__("total_energy_uj", 1))),
            ("landauer_temp_lie", _mut_cert(lambda c: c["payload"]["stage_b_time_reversal_dissipation"]["landauer_thermodynamic_bridge"].__setitem__("mean_package_temp_kelvin_q", "300"))),
            ("landauer_lo_lie", _mut_cert(lambda c: c["payload"]["stage_b_time_reversal_dissipation"]["landauer_thermodynamic_bridge"].__setitem__("landauer_bits_lower_bound", 1))),
            ("landauer_hi_lie", _mut_cert(lambda c: c["payload"]["stage_b_time_reversal_dissipation"]["landauer_thermodynamic_bridge"].__setitem__("landauer_bits_upper_bound", 1))),
            ("landauer_qfree_lie", _mut_cert(lambda c: c["payload"]["stage_b_time_reversal_dissipation"]["landauer_thermodynamic_bridge"].__setitem__("s38_qfree_reversible_bits", 1))),
            ("landauer_qfree_bool", _mut_cert(lambda c: c["payload"]["stage_b_time_reversal_dissipation"]["landauer_thermodynamic_bridge"].__setitem__("s38_qfree_reversible_bits", False))),
            ("landauer_mfree_lie", _mut_cert(lambda c: c["payload"]["stage_b_time_reversal_dissipation"]["landauer_thermodynamic_bridge"].__setitem__("s38_mfree_single_and_bracket_bits_q", ["1", "2"]))),
            ("landauer_power_lie", _mut_cert(lambda c: c["payload"]["stage_b_time_reversal_dissipation"]["landauer_thermodynamic_bridge"].__setitem__("mean_package_power_w_q", "1"))),
            # Adversarial nulls & split-half replication
            ("missing_nulls_sec", _mut_cert(lambda c: c["payload"].__setitem__("adversarial_nulls_and_replication", None))),
            ("bad_circ_class", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["circular_shift_null_exact"].__setitem__("oracle_class", "sampled"))),
            ("circ_obs_r2_lie", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["circular_shift_null_exact"].__setitem__("obs_mean_r2_q", "0"))),
            ("circ_obs_a2_lie", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["circular_shift_null_exact"].__setitem__("obs_mean_a2_q", "0"))),
            (
                "circ_p_r2_lie",
                _mut_cert(
                    lambda c: c["payload"]["adversarial_nulls_and_replication"]["circular_shift_null_exact"].__setitem__(
                        "p_mean_r2_q",
                        "2/201"
                        if p0["adversarial_nulls_and_replication"]["circular_shift_null_exact"]["p_mean_r2_q"] == "1/201"
                        else "1/201",
                    )
                ),
            ),
            (
                "circ_p_a2_lie",
                _mut_cert(
                    lambda c: c["payload"]["adversarial_nulls_and_replication"]["circular_shift_null_exact"].__setitem__(
                        "p_mean_a2_q",
                        "2/201"
                        if p0["adversarial_nulls_and_replication"]["circular_shift_null_exact"]["p_mean_a2_q"] == "1/201"
                        else "1/201",
                    )
                ),
            ),
            ("bad_iaaft_class", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["iaaft_null_sampled"].__setitem__("oracle_class", "exact"))),
            ("iaaft_p_r2_zero", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["iaaft_null_sampled"].__setitem__("p_mean_r2_q", "0"))),
            ("iaaft_p_r2_gt1", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["iaaft_null_sampled"].__setitem__("p_mean_r2_q", "2"))),
            ("iaaft_p_r2_offgrid", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["iaaft_null_sampled"].__setitem__("p_mean_r2_q", "1/1000000"))),
            ("iaaft_p_a2_zero", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["iaaft_null_sampled"].__setitem__("p_mean_a2_q", "0"))),
            ("iaaft_p_a2_gt1", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["iaaft_null_sampled"].__setitem__("p_mean_a2_q", "2"))),
            ("iaaft_p_a2_offgrid", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["iaaft_null_sampled"].__setitem__("p_mean_a2_q", "1/1000000"))),
            ("iaaft_z2_r2_neg", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["iaaft_null_sampled"].__setitem__("z_squared_mean_r2_q", "-1"))),
            ("iaaft_z2_a2_neg", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["iaaft_null_sampled"].__setitem__("z_squared_mean_a2_q", "-1"))),
            ("split_half_missing", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"].__setitem__("split_half_replication_exact", None))),
            ("split_half_dyn_lie", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["split_half_replication_exact"].__setitem__("both_halves_dynamic_count", 1))),
            ("split_half_len_lie", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["split_half_replication_exact"].__setitem__("half_len", 1))),
            ("split_half_ari_lie", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["split_half_replication_exact"].__setitem__("split_half_cluster_ari_q", "-1"))),
            ("split_half_matches_lie", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["split_half_replication_exact"].__setitem__("top10_arrow_sign_matches", 99))),
            ("split_half_count_lie", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["split_half_replication_exact"].__setitem__("top10_arrow_count", 99))),
            ("split_half_conc_lie", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["split_half_replication_exact"].__setitem__("top10_arrow_sign_concordance_q", "0" if p0["adversarial_nulls_and_replication"]["split_half_replication_exact"]["top10_arrow_sign_concordance_q"] != "0" else "1"))),
            ("split_half_h1_lie", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["split_half_replication_exact"].__setitem__("half1_mean_a2_q", "0"))),
            ("split_half_h2_lie", _mut_cert(lambda c: c["payload"]["adversarial_nulls_and_replication"]["split_half_replication_exact"].__setitem__("half2_mean_a2_q", "0"))),
        ]

        for name, (s_obj, r_sha, c_obj) in tamper_cases:
            with self.subTest(tamper=name):
                with self.assertRaises(audit.SensorAuditError):
                    audit.verify_certificate_dict(s_obj, r_sha, c_obj)

        # Explicit error-code pins so upstream guards cannot be masked by downstream hash/recompute checks
        with self.assertRaises(audit.SensorAuditError) as ctx_pl:
            audit.verify_certificate_dict(snap, raw_sha, {**cert, "payload": []})
        self.assertEqual(ctx_pl.exception.code, "INVALID_PAYLOAD")

        s_short = copy.deepcopy(snap)
        s_short["X_anonymous"] = [[1] * len(snap["held_out_ground_truth_channels"])] * 3
        with self.assertRaises(audit.SensorAuditError) as ctx_xm:
            audit.verify_certificate_dict(s_short, raw_sha, cert)
        self.assertEqual(ctx_xm.exception.code, "INVALID_MATRIX")

        s_ch = copy.deepcopy(snap)
        s_ch["held_out_ground_truth_channels"] = []
        with self.assertRaises(audit.SensorAuditError) as ctx_ch:
            audit.verify_certificate_dict(s_ch, raw_sha, cert)
        self.assertEqual(ctx_ch.exception.code, "INVALID_CHANNELS_LIST")

        s_ch_bad = copy.deepcopy(snap)
        s_ch_bad["held_out_ground_truth_channels"][0] = 123
        with self.assertRaises(audit.SensorAuditError) as ctx_cb:
            audit.verify_certificate_dict(s_ch_bad, raw_sha, cert)
        self.assertEqual(ctx_cb.exception.code, "INVALID_CHANNELS")

        s_ch_mod = copy.deepcopy(snap)
        s_ch_mod["held_out_ground_truth_channels"][0]["module"] = 123
        with self.assertRaises(audit.SensorAuditError) as ctx_cm:
            audit.verify_certificate_dict(s_ch_mod, raw_sha, cert)
        self.assertEqual(ctx_cm.exception.code, "INVALID_CHANNELS")

        s_rw = copy.deepcopy(snap)
        s_rw["X_anonymous"][0].append(1)
        rw_xsha = hashlib.sha256(audit.canonical_json_bytes(s_rw["X_anonymous"])).hexdigest()
        s_rw["x_anonymous_sha256"] = rw_xsha
        c_rw = copy.deepcopy(cert)
        c_rw["payload"]["x_anonymous_sha256"] = rw_xsha
        c_rw = _resign(c_rw)
        with self.assertRaises(audit.SensorAuditError) as ctx_rw:
            audit.verify_certificate_dict(s_rw, raw_sha, c_rw)
        self.assertEqual(ctx_rw.exception.code, "INVALID_ROW")

        for bad_ridge in ("0", "-1/20"):
            c_rg = copy.deepcopy(cert)
            c_rg["payload"]["ridge_lambda_q"] = bad_ridge
            c_rg = _resign(c_rg)
            with self.assertRaises(audit.SensorAuditError) as ctx_rg:
                audit.verify_certificate_dict(snap, raw_sha, c_rg)
            self.assertEqual(ctx_rg.exception.code, "INVALID_RIDGE")

        # Type-confusion tamper cases (kills every `type(x) is ... and ...` BoolOp sub-condition!)
        s_xstr = copy.deepcopy(snap)
        s_xstr["X_anonymous"] = "0123456789"
        with self.assertRaises(audit.SensorAuditError) as ctx_xs:
            audit.verify_certificate_dict(s_xstr, raw_sha, cert)
        self.assertEqual(ctx_xs.exception.code, "INVALID_MATRIX")

        s_gstr = copy.deepcopy(snap)
        s_gstr["held_out_ground_truth_channels"] = "01234567"
        with self.assertRaises(audit.SensorAuditError) as ctx_gs:
            audit.verify_certificate_dict(s_gstr, raw_sha, cert)
        self.assertEqual(ctx_gs.exception.code, "INVALID_CHANNELS_LIST")

        s_rstr = copy.deepcopy(snap)
        s_rstr["X_anonymous"][0] = "12345678"
        rs_xsha = hashlib.sha256(audit.canonical_json_bytes(s_rstr["X_anonymous"])).hexdigest()
        s_rstr["x_anonymous_sha256"] = rs_xsha
        c_rstr = copy.deepcopy(cert)
        c_rstr["payload"]["x_anonymous_sha256"] = rs_xsha
        with self.assertRaises(audit.SensorAuditError) as ctx_rs:
            audit.verify_certificate_dict(s_rstr, raw_sha, _resign(c_rstr))
        self.assertEqual(ctx_rs.exception.code, "INVALID_ROW")

        for field_name in ("audio_consent_window", "room_noise_covariate"):
            s_p2t = copy.deepcopy(snap2)
            s_p2t[field_name] = ["nonempty_list"]
            with self.assertRaises(audit.SensorAuditError) as ctx_p2t:
                audit.verify_certificate_dict(s_p2t, raw_sha2, cert2)
            self.assertEqual(ctx_p2t.exception.code, "PRIVACY_POLICY")

        c_bb = copy.deepcopy(cert)
        c_bb["payload"]["stage_b_schur_dark_modes"]["blind_complement_b_indices"] = "bad"
        with self.assertRaises(audit.SensorAuditError) as ctx_bb:
            audit.verify_certificate_dict(snap, raw_sha, _resign(c_bb))
        self.assertEqual(ctx_bb.exception.code, "INVALID_SCHUR_IDX")

        c_bl = copy.deepcopy(cert)
        c_bl["payload"]["stage_b_time_reversal_dissipation"]["by_lag"] = ["1", "2", "3", "5"]
        with self.assertRaises(audit.SensorAuditError) as ctx_bl:
            audit.verify_certificate_dict(snap, raw_sha, _resign(c_bl))
        self.assertEqual(ctx_bl.exception.code, "MISSING_LAG")

        c_lb = copy.deepcopy(cert)
        c_lb["payload"]["stage_b_time_reversal_dissipation"]["landauer_thermodynamic_bridge"] = []
        with self.assertRaises(audit.SensorAuditError) as ctx_lb:
            audit.verify_certificate_dict(snap, raw_sha, _resign(c_lb))
        self.assertEqual(ctx_lb.exception.code, "INVALID_LANDAUER")

        s_notmp = copy.deepcopy(snap)
        s_notmp["held_out_ground_truth_channels"][0]["label"] = "Other"
        with self.assertRaises(audit.SensorAuditError) as ctx_nt:
            audit.verify_certificate_dict(s_notmp, raw_sha, cert)
        self.assertEqual(ctx_nt.exception.code, "UNEXPECTED_LANDAUER")

        c_cn = copy.deepcopy(cert)
        c_cn["payload"]["adversarial_nulls_and_replication"]["circular_shift_null_exact"] = []
        with self.assertRaises(audit.SensorAuditError) as ctx_cn:
            audit.verify_certificate_dict(snap, raw_sha, _resign(c_cn))
        self.assertEqual(ctx_cn.exception.code, "INVALID_CIRC_NULL")

        c_ia = copy.deepcopy(cert)
        c_ia["payload"]["adversarial_nulls_and_replication"]["iaaft_null_sampled"] = []
        with self.assertRaises(audit.SensorAuditError) as ctx_ia:
            audit.verify_certificate_dict(snap, raw_sha, _resign(c_ia))
        self.assertEqual(ctx_ia.exception.code, "INVALID_IAAFT")

        # Tie-breaking modularity cluster control (kills tie-break BoolOp cleanly)
        sym_aff = [
            [Fraction(1), Fraction(1, 2), Fraction(0), Fraction(0)],
            [Fraction(1, 2), Fraction(1), Fraction(0), Fraction(0)],
            [Fraction(0), Fraction(0), Fraction(1), Fraction(1, 2)],
            [Fraction(0), Fraction(0), Fraction(1, 2), Fraction(1)],
        ]
        cl_sym, q_sym = audit._indep_modularity_cluster(sym_aff)
        self.assertEqual(len(set(cl_sym)), 2)
        self.assertEqual(q_sym, Fraction(1, 2))

    def test_05_zone_b_filesystem_parser_and_argv_defenses(self) -> None:
        # Path type, NUL, surrogate, root, parent traversal, argv guards
        with self.assertRaises(audit.SensorAuditError) as ctx_pt:
            audit.read_regular_bytes_safe("not_a_path_str", "bad_type")  # type: ignore[arg-type]
        self.assertEqual(ctx_pt.exception.code, "INVALID_PATH_TYPE")

        with self.assertRaises(audit.SensorAuditError) as ctx_nl:
            audit.read_regular_bytes_safe(Path("bad\x00path"), "nul_path")
        self.assertEqual(ctx_nl.exception.code, "NUL_BYTE_FORBIDDEN")

        with self.assertRaises(audit.SensorAuditError) as ctx_sr:
            audit.read_regular_bytes_safe(Path("bad\ud800path"), "surr_path")
        self.assertEqual(ctx_sr.exception.code, "INVALID_UTF8_SURROGATE")

        with self.assertRaises(audit.SensorAuditError) as ctx_rt:
            audit.read_regular_bytes_safe(Path("/"), "root_path")
        self.assertEqual(ctx_rt.exception.code, "NOT_A_REGULAR_FILE")

        with self.assertRaises(audit.SensorAuditError) as ctx_up:
            audit.read_regular_bytes_safe(Path("foo/../bar.json"), "up_path")
        self.assertEqual(ctx_up.exception.code, "PARENT_TRAVERSAL_FORBIDDEN")

        # _validate_argv coverage
        self.assertIsNone(audit._validate_argv(None))
        self.assertEqual(audit._validate_argv(["--self-test"]), ["--self-test"])
        with self.assertRaises(audit.SensorAuditError):
            audit._validate_argv("bad")  # type: ignore[arg-type]
        with self.assertRaises(audit.SensorAuditError):
            audit._validate_argv([123])  # type: ignore[list-item]
        with self.assertRaises(audit.SensorAuditError):
            audit._validate_argv(["a\x00b"])
        with self.assertRaises(audit.SensorAuditError):
            audit._validate_argv(["a\ud800b"])

        with tempfile.TemporaryDirectory(prefix="s53_zoneb_") as td:
            root = Path(td)
            canary = root / "canary.json"
            canary.write_bytes(b'{"ok":1}\n')

            # Exact max_bytes equality must PASS (kills st_size <= max_bytes & total <= max_bytes -> <)
            exact64 = root / "exact64.json"
            exact64.write_bytes(b"a" * 64)
            self.assertEqual(len(audit.read_regular_bytes_safe(exact64, "eq64", max_bytes=64)), 64)

            # S53-VER-03: Hardlinked file rejected (st_nlink > 1) on both API & live CLI
            hl_src = root / "hl_src.json"
            hl_src.write_bytes(b'{"ok":1}\n')
            hl_dst = root / "hl_dst.json"
            os.link(str(hl_src), str(hl_dst))
            with self.assertRaises(audit.SensorAuditError) as ctx_hl:
                audit.read_regular_bytes_safe(hl_dst, "hardlink")
            self.assertEqual(ctx_hl.exception.code, "HARDLINK_FORBIDDEN")
            proc_hl = subprocess.run(
                [sys.executable, "-I", "-B", str(HERE / "sensor_tomography_audit.py"), "--raw", str(canary), "--check", str(hl_dst)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_hl.returncode, 2)
            self.assertEqual(json.loads(proc_hl.stderr)["code"], "HARDLINK_FORBIDDEN")

            # Symlink leaf rejected
            sym_leaf = root / "sym_leaf.json"
            os.symlink(str(canary), str(sym_leaf))
            with self.assertRaises(audit.SensorAuditError) as ctx_sl:
                audit.read_regular_bytes_safe(sym_leaf, "sym_leaf")
            self.assertEqual(ctx_sl.exception.code, "SYMLINK_FORBIDDEN")

            # Symlink ancestor rejected
            real_dir = root / "real_dir"
            real_dir.mkdir()
            (real_dir / "inner.json").write_bytes(b'{"ok":1}\n')
            sym_dir = root / "sym_dir"
            os.symlink(str(real_dir), str(sym_dir))
            with self.assertRaises(audit.SensorAuditError) as ctx_sd:
                audit.read_regular_bytes_safe(sym_dir / "inner.json", "sym_dir")
            self.assertEqual(ctx_sd.exception.code, "SYMLINK_FORBIDDEN")

            # Missing ancestor directory -> FILE_NOT_FOUND
            with self.assertRaises(audit.SensorAuditError) as ctx_ma:
                audit.read_regular_bytes_safe(root / "no_such_dir" / "file.json", "missing_anc")
            self.assertEqual(ctx_ma.exception.code, "FILE_NOT_FOUND")

            # Non-directory ancestor (regular file as dir component) -> SYMLINK_FORBIDDEN
            with self.assertRaises(audit.SensorAuditError) as ctx_nd:
                audit.read_regular_bytes_safe(canary / "child.json", "nondir_anc")
            self.assertEqual(ctx_nd.exception.code, "SYMLINK_FORBIDDEN")

            # Scratch FIFO (zero system device-node writes)
            if hasattr(os, "mkfifo"):
                fifo_p = root / "pipe.fifo"
                os.mkfifo(str(fifo_p))
                with self.assertRaises(audit.SensorAuditError) as ctx_ff:
                    audit.read_regular_bytes_safe(fifo_p, "fifo")
                self.assertEqual(ctx_ff.exception.code, "NOT_A_REGULAR_FILE")

            # Unreadable file (chmod 000) -> FILE_READ_ERROR
            locked = root / "locked.json"
            locked.write_bytes(b'{"ok":1}\n')
            os.chmod(str(locked), 0o000)
            try:
                if os.geteuid() != 0:
                    with self.assertRaises(audit.SensorAuditError) as ctx_lk:
                        audit.read_regular_bytes_safe(locked, "locked")
                    self.assertEqual(ctx_lk.exception.code, "FILE_READ_ERROR")
            finally:
                os.chmod(str(locked), 0o600)

            # Fast st_size cap (65 > 64 must reject BEFORE os.read) + exact 64-byte pass + streaming read cap
            exact64 = root / "exact64.json"
            exact64.write_bytes(b"a" * 64)
            self.assertEqual(audit.read_regular_bytes_safe(exact64, "exact64", max_bytes=64), b"a" * 64)

            big = root / "big.json"
            big.write_bytes(b"a" * 65)
            with mock.patch("os.read", side_effect=RuntimeError("os.read must not run before st_size cap")):
                with self.assertRaises(audit.SensorAuditError) as ctx_bg:
                    audit.read_regular_bytes_safe(big, "big", max_bytes=64)
                self.assertEqual(ctx_bg.exception.code, "FILE_TOO_LARGE")

            orig_fstat = os.fstat

            def _shrunk_fstat(fd: int):
                st_real = orig_fstat(fd)
                return os.stat_result((st_real.st_mode, st_real.st_ino, st_real.st_dev, 1, st_real.st_uid, st_real.st_gid, 0, st_real.st_atime, st_real.st_mtime, st_real.st_ctime))

            with mock.patch("os.fstat", side_effect=_shrunk_fstat):
                with self.assertRaises(audit.SensorAuditError) as ctx_bgs:
                    audit.read_regular_bytes_safe(big, "big_stream", max_bytes=64)
                self.assertEqual(ctx_bgs.exception.code, "FILE_TOO_LARGE")

            # Base-dir os.open failure -> FILE_READ_ERROR
            with mock.patch("os.open", side_effect=OSError(errno.EACCES, "root denied")):
                with self.assertRaises(audit.SensorAuditError) as ctx_bd:
                    audit.read_regular_bytes_safe(canary, "base_dir_err")
                self.assertEqual(ctx_bd.exception.code, "FILE_READ_ERROR")

            # Relative path read + symlinked $PWD rejection + os.getcwd failure -> CWD_UNAVAILABLE
            (real_dir / "inner.json").write_bytes(b'{"ok":2}\n')
            orig_cwd = os.getcwd()
            try:
                os.chdir(str(root))
                with mock.patch.dict(os.environ, {"PWD": str(root)}):
                    self.assertEqual(audit.read_regular_bytes_safe(Path("canary.json"), "rel_canary"), b'{"ok":1}\n')
                os.chdir(str(real_dir))
                with mock.patch.dict(os.environ, {"PWD": str(sym_dir)}):
                    with self.assertRaises(audit.SensorAuditError) as ctx_spwd:
                        audit.read_regular_bytes_safe(Path("inner.json"), "rel_sym_pwd")
                    self.assertEqual(ctx_spwd.exception.code, "SYMLINK_FORBIDDEN")
            finally:
                os.chdir(orig_cwd)

            with mock.patch("os.getcwd", side_effect=OSError(errno.ENOENT, "cwd unlinked")):
                with self.assertRaises(audit.SensorAuditError) as ctx_cwd:
                    audit.read_regular_bytes_safe(Path("rel_no_cwd.json"), "cwd_err")
                self.assertEqual(ctx_cwd.exception.code, "CWD_UNAVAILABLE")

            # Missing leaf file -> FILE_NOT_FOUND
            with self.assertRaises(audit.SensorAuditError) as ctx_ms:
                audit.read_regular_bytes_safe(root / "missing.json", "missing")
            self.assertEqual(ctx_ms.exception.code, "FILE_NOT_FOUND")

            # Exact depth 64 PASSES (kills depth <= MAX_JSON_DEPTH -> <), depth 65 FAILS
            depth64 = b'{"a":' + (b"[" * 63) + b"1" + (b"]" * 63) + b"}\n"
            self.assertIsInstance(audit.parse_strict_json_bytes(depth64, "d64"), dict)
            depth65 = b'{"a":' + (b"[" * 64) + b"1" + (b"]" * 64) + b"}\n"
            with self.assertRaises(audit.SensorAuditError) as ctx_d65:
                audit.parse_strict_json_bytes(depth65, "d65")
            self.assertEqual(ctx_d65.exception.code, "JSON_DEPTH_LIMIT")

            # Strict parser rejections: UTF-8, syntax, float, dup key, CRLF, BOM, NUL, NaN, non-dict root
            for label, payload_b, expected_code in (
                ("bad_utf8", b"\xff\xfe", "INVALID_UTF8"),
                ("bad_json", b'{"x": }\n', "INVALID_JSON"),
                ("float", b'{"x": 1.25}\n', "FLOAT_JSON_FORBIDDEN"),
                ("dup", b'{"x": 1, "x": 2}\n', "DUPLICATE_JSON_KEY"),
                ("crlf", b'{"x": 1}\r\n', "CRLF_FORBIDDEN"),
                ("bom", b'\xef\xbb\xbf{"x": 1}\n', "BOM_FORBIDDEN"),
                ("nul", b'{"x": "a\x00b"}\n', "NUL_BYTE_FORBIDDEN"),
                ("nan", b'{"x": NaN}\n', "NONFINITE_JSON_FORBIDDEN"),
                ("list_root", b"[1, 2, 3]\n", "JSON_ROOT_NOT_OBJECT"),
            ):
                with self.subTest(bad_json=label):
                    with self.assertRaises(audit.SensorAuditError) as ctx_pj:
                        audit.parse_strict_json_bytes(payload_b, label)
                    self.assertEqual(ctx_pj.exception.code, expected_code)

    def test_06_cli_exit_codes_zero_tracebacks(self) -> None:
        proc_ok = subprocess.run(
            [sys.executable, "-I", "-B", str(HERE / "sensor_tomography_audit.py"), "--self-test"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc_ok.returncode, 0)
        self.assertEqual(proc_ok.stderr, "")
        parsed = json.loads(proc_ok.stdout)
        self.assertTrue(parsed["self_test_passed"])

        # Zero-arg default runs self-test too, and --self-test overrides --check
        proc_def = subprocess.run(
            [sys.executable, "-I", "-B", str(HERE / "sensor_tomography_audit.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc_def.returncode, 0)
        self.assertTrue(json.loads(proc_def.stdout)["self_test_passed"])

        proc_override = subprocess.run(
            [sys.executable, "-I", "-B", str(HERE / "sensor_tomography_audit.py"), "--self-test", "--check", str(HERE / "nonexistent_cert.json")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc_override.returncode, 0)
        self.assertTrue(json.loads(proc_override.stdout)["self_test_passed"])

        proc_bad = subprocess.run(
            [sys.executable, "-I", "-B", str(HERE / "sensor_tomography_audit.py"), "--check", str(HERE / "nonexistent_cert.json")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc_bad.returncode, 2)
        self.assertNotIn("Traceback", proc_bad.stderr)
        err_obj = json.loads(proc_bad.stderr)
        self.assertEqual(err_obj["code"], "FILE_NOT_FOUND")

        # Auto-pairing --check <cert> without --raw across all 3 canonical filenames + explicit --raw override
        import sensor_tomography_probe as probe

        s_pre, rb_pre, rs_pre = _build_synthetic_snapshot(with_rapl=False, phase2_audio=False)
        c_pre = probe.analyze_snapshot(s_pre, rs_pre)
        s_p2, rb_p2, rs_p2 = _build_synthetic_snapshot(with_rapl=True, phase2_audio=True)
        c_p2 = probe.analyze_snapshot(s_p2, rs_p2)
        with tempfile.TemporaryDirectory(prefix="s53_autopair_") as td:
            td_p = Path(td)
            (td_p / "pre_rapl_baseline_snapshot.json").write_bytes(rb_pre)
            (td_p / "pre_rapl_baseline_certificate.json").write_bytes(audit.canonical_json_bytes(c_pre))
            (td_p / "phase2_controlled_snapshot.json").write_bytes(rb_p2)
            (td_p / "phase2_controlled_certificate.json").write_bytes(audit.canonical_json_bytes(c_p2))
            for cert_name in ("pre_rapl_baseline_certificate.json", "phase2_controlled_certificate.json"):
                proc_ap = subprocess.run(
                    [sys.executable, "-I", "-B", str(HERE / "sensor_tomography_audit.py"), "--check", cert_name],
                    cwd=str(td_p),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc_ap.returncode, 0, proc_ap.stderr)
                self.assertTrue(json.loads(proc_ap.stdout)["valid"])
            proc_ovr = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    str(HERE / "sensor_tomography_audit.py"),
                    "--raw",
                    "pre_rapl_baseline_snapshot.json",
                    "--check",
                    "phase2_controlled_certificate.json",
                ],
                cwd=str(td_p),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_ovr.returncode, 2)
            self.assertEqual(json.loads(proc_ovr.stderr)["code"], "RAW_SHA_MISMATCH")

    def test_09_live_frozen_snapshots_all_three_phases(self) -> None:
        pairs = (
            ("pre_rapl_baseline_snapshot.json", "pre_rapl_baseline_certificate.json", 26),
            ("raw_sensor_snapshot.json", "sensor_tomography_certificate.json", 36),
            ("phase2_controlled_snapshot.json", "phase2_controlled_certificate.json", 48),
        )
        for raw_name, cert_name, min_dyn in pairs:
            raw_p = HERE / raw_name
            cert_p = HERE / cert_name
            if not (raw_p.is_file() and cert_p.is_file()):
                continue
            with self.subTest(cert=cert_name):
                raw_bytes = audit.read_regular_bytes_safe(raw_p, raw_name)
                cert_bytes = audit.read_regular_bytes_safe(cert_p, cert_name)
                raw_obj = audit.parse_strict_json_bytes(raw_bytes, raw_name)
                cert_obj = audit.parse_strict_json_bytes(cert_bytes, cert_name)
                res = audit.verify_certificate_dict(raw_obj, hashlib.sha256(raw_bytes).hexdigest(), cert_obj)
                self.assertTrue(res["valid"])
                self.assertTrue(res["gauge_invariance_exact"])
                self.assertGreaterEqual(res["dynamic_channel_count"], min_dyn)

    def test_07_r2_json_tree_subclasses_bool_in_int_and_branch_controls(self) -> None:
        import sensor_tomography_probe as probe

        snap, raw_sha, cert = _make_valid_synthetic_pair(with_rapl=True, phase2_audio=False)

        class _FakeDict(dict):
            pass

        class _FakeList(list):
            pass

        class _FakeInt(int):
            pass

        class _FakeStr(str):
            pass

        # Non-dict roots & invalid raw_sha
        for args, code in (
            (([], raw_sha, cert), "JSON_ROOT_NOT_OBJECT"),
            ((snap, raw_sha, []), "JSON_ROOT_NOT_OBJECT"),
            ((snap, raw_sha, None), "JSON_ROOT_NOT_OBJECT"),
            ((snap, 123, cert), "INVALID_RAW_SHA"),
        ):
            with self.assertRaises(audit.SensorAuditError) as ctx_r:
                audit.verify_certificate_dict(*args)  # type: ignore[arg-type]
            self.assertEqual(ctx_r.exception.code, code)

        # Subclasses, runtime floats/NaN, non-str dict key, huge int, NUL, surrogate, depth 64 vs 65
        nan_val = json.loads("NaN")
        flt_val = json.loads("1.5")
        with self.assertRaises(audit.SensorAuditError) as ctx_nan:
            audit.canonical_json_bytes({"x": nan_val})
        self.assertEqual(ctx_nan.exception.code, "FORBIDDEN_JSON_TYPE")

        for bad_obj, exp_code in (
            (_FakeDict({"a": 1}), "FORBIDDEN_JSON_TYPE"),
            ({"a": _FakeList([1])}, "FORBIDDEN_JSON_TYPE"),
            ({"a": _FakeInt(1)}, "FORBIDDEN_JSON_TYPE"),
            ({"a": _FakeStr("x")}, "FORBIDDEN_JSON_TYPE"),
            ({"a": flt_val}, "FORBIDDEN_JSON_TYPE"),
            ({1: "x"}, "INVALID_JSON_KEY"),
            ({_FakeStr("k"): "x"}, "INVALID_JSON_KEY"),
            ({"a": 1 << audit.MAX_INT_BITS}, "INT_BIT_LIMIT"),
            ({"a": (10 ** 5000) - 1}, "INT_BIT_LIMIT"),
            ({"a": "x\x00y"}, "NUL_BYTE_FORBIDDEN"),
            ({"a": "x\ud800y"}, "INVALID_UTF8_SURROGATE"),
        ):
            with self.subTest(bad_tree=exp_code):
                with self.assertRaises(audit.SensorAuditError) as ctx_t:
                    audit._validate_json_tree_iter(bad_obj, "t")
                self.assertEqual(ctx_t.exception.code, exp_code)

        # Exact bit-cap and depth-64 boundary pass vs depth-65 fail in _validate_json_tree_iter
        audit._validate_json_tree_iter({"a": (1 << audit.MAX_INT_BITS) - 1, "b": None, "c": True}, "ok_max")
        d64: object = 1
        for _ in range(63):
            d64 = [d64]
        audit._validate_json_tree_iter({"a": d64}, "tree_d64")
        with self.assertRaises(audit.SensorAuditError) as ctx_td65:
            audit._validate_json_tree_iter({"a": [d64]}, "tree_d65")
        self.assertEqual(ctx_td65.exception.code, "JSON_DEPTH_LIMIT")

        # Subclass roots & bool-in-int smuggling on verify_certificate_dict
        with self.assertRaises(audit.SensorAuditError) as ctx_fd:
            audit.verify_certificate_dict(snap, raw_sha, _FakeDict(cert))
        self.assertEqual(ctx_fd.exception.code, "JSON_ROOT_NOT_OBJECT")

        c_bi = copy.deepcopy(cert)
        c_bi["payload"]["stage_b_schur_dark_modes"]["physical_partition_schur"]["schur_inertia"] = [
            c_bi["payload"]["stage_b_schur_dark_modes"]["physical_partition_schur"]["schur_inertia"][0],
            False,
            False,
        ]
        with self.assertRaises(audit.SensorAuditError) as ctx_bi:
            audit.verify_certificate_dict(snap, raw_sha, _resign(c_bi))
        self.assertEqual(ctx_bi.exception.code, "PHYS_SCHUR_INERTIA")

        c_blb = copy.deepcopy(cert)
        c_blb["payload"]["stage_b_coupling_and_blind_clustering"]["blind_r2_labels"] = [
            (False if v == 0 else (True if v == 1 else v))
            for v in c_blb["payload"]["stage_b_coupling_and_blind_clustering"]["blind_r2_labels"]
        ]
        with self.assertRaises(audit.SensorAuditError) as ctx_blb:
            audit.verify_certificate_dict(snap, raw_sha, _resign(c_blb))
        self.assertEqual(ctx_blb.exception.code, "BLIND_R2_MISMATCH")

        # Non-thermal capture (len(exp_pa) < 2) AND all-thermal capture (len(exp_pb) == 0) AND short 4Hz capture
        s_noth, _, _ = _build_synthetic_snapshot(with_rapl=False, phase2_audio=False)
        for ch in s_noth["held_out_ground_truth_channels"]:
            ch["module"] = "mechanical_cooling"
        s_noth["cadence_hz"] = 4  # t_len=24 < 40 -> keeps 2Hz LAGS=(1,2,3,5) (kills cadence==4 and t_len>=40 BoolOp!)
        rb_nt = audit.canonical_json_bytes(s_noth)
        rs_nt = hashlib.sha256(rb_nt).hexdigest()
        c_nt = probe.analyze_snapshot(s_noth, rs_nt)
        self.assertTrue(audit.verify_certificate_dict(s_noth, rs_nt, c_nt)["valid"])

        c_nt_bad = copy.deepcopy(c_nt)
        c_nt_bad["payload"]["stage_b_schur_dark_modes"]["physical_partition_schur"] = {}
        with self.assertRaises(audit.SensorAuditError) as ctx_up:
            audit.verify_certificate_dict(s_noth, rs_nt, _resign(c_nt_bad))
        self.assertEqual(ctx_up.exception.code, "UNEXPECTED_PHYS_SCHUR")

        s_allth, _, _ = _build_synthetic_snapshot(with_rapl=False, phase2_audio=False)
        for ch in s_allth["held_out_ground_truth_channels"]:
            ch["module"] = "cpu_die_thermal"
        rb_at = audit.canonical_json_bytes(s_allth)
        rs_at = hashlib.sha256(rb_at).hexdigest()
        c_at = probe.analyze_snapshot(s_allth, rs_at)
        self.assertTrue(audit.verify_certificate_dict(s_allth, rs_at, c_at)["valid"])

    def test_08_r3_mutation_and_boolop_closure(self) -> None:
        import sensor_tomography_probe as probe

        # 1. _require_exact_int_list BoolOp: exact-length tuple AND prefix-matching longer list rejected
        with self.assertRaises(audit.SensorAuditError) as ctx_tup:
            audit._require_exact_int_list((1, 2), "TUP_CODE", "tup_lbl", [1, 2])
        self.assertEqual(ctx_tup.exception.code, "TUP_CODE")

        with self.assertRaises(audit.SensorAuditError) as ctx_len:
            audit._require_exact_int_list([1, 2, 3], "LEN_CODE", "len_lbl", [1, 2])
        self.assertEqual(ctx_len.exception.code, "LEN_CODE")

        audit._require_exact_int_list([1, 2], "OK_CODE", "ok_lbl", [1, 2])

        # 2. Direct gauge_ari == 1 guard (unmasked by setting cert gauge_ari_q="1/2" & all_gauge_invariants_exact=False)
        snap, raw_sha, cert = _make_valid_synthetic_pair(with_rapl=True, phase2_audio=False)
        c_gfail = copy.deepcopy(cert)
        c_gfail["payload"]["stage_a_gauge_invariance"]["blind_cluster_gauge_ari_q"] = "1/2"
        c_gfail["payload"]["stage_a_gauge_invariance"]["all_gauge_invariants_exact"] = False
        c_gfail = _resign(c_gfail)
        orig_ari = audit._indep_ari_q
        call_n = [0]

        def _rigged_ari(la, lb):
            call_n[0] += 1
            if call_n[0] == 3:
                return Fraction(1, 2)
            return orig_ari(la, lb)

        with mock.patch.object(audit, "_indep_ari_q", side_effect=_rigged_ari):
            with self.assertRaises(audit.SensorAuditError) as ctx_ga:
                audit.verify_certificate_dict(snap, raw_sha, c_gfail)
            self.assertEqual(ctx_ga.exception.code, "GAUGE_ARI_MISMATCH")

        # 3. Split-half palindromic symmetric snapshot: dm_1 == dm_2 == 0 -> r[1] != 0 must force agree == 0
        s_sym, _, _ = _build_synthetic_snapshot(with_rapl=False, phase2_audio=False)
        h1_half = [
            (10, 50, 1, 0),
            (14, 56, -1, 2),
            (19, 48, 2, -1),
            (25, 62, -2, 1),
            (16, 54, 0, -2),
            (12, 59, 1, 0),
        ]
        h2_half = [
            (12, 52, -1, 2),
            (18, 49, 1, 0),
            (11, 60, 0, -2),
            (24, 55, 2, 1),
            (20, 63, -1, -1),
            (15, 51, -2, 1),
        ]
        seq = h1_half + list(reversed(h1_half)) + h2_half + list(reversed(h2_half))
        sym_rows = [
            [
                40000 + 200 * ht + 15 * a,
                41000 + 190 * ht + 15 * b,
                3000 + 40 * ht + 25 * b,
                800 + 30 * gt + 5 * a,
                50 + 2 * gt + b,
                35000 + 100 * ht + 10 * gt,
                0,
            ]
            for ht, gt, a, b in seq
        ]
        s_sym["X_anonymous"] = sym_rows
        s_sym["x_anonymous_sha256"] = hashlib.sha256(audit.canonical_json_bytes(sym_rows)).hexdigest()
        rb_sym = audit.canonical_json_bytes(s_sym)
        rs_sym = hashlib.sha256(rb_sym).hexdigest()
        c_sym = probe.analyze_snapshot(s_sym, rs_sym)
        sh_sym = c_sym["payload"]["adversarial_nulls_and_replication"]["split_half_replication_exact"]
        self.assertEqual(sh_sym["top10_arrow_count"], 10)
        self.assertEqual(sh_sym["top10_arrow_sign_matches"], 0)
        self.assertTrue(audit.verify_certificate_dict(s_sym, rs_sym, c_sym)["valid"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
