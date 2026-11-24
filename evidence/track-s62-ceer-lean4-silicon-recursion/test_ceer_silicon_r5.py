#!/usr/bin/env python3
"""
test_ceer_silicon_r5.py — Comprehensive R5, filesystem/JSON hardening, Lean 4 trust-escape,
and 100% mutation-killing test suite for 3-cycle CEER (Lean 4.36.0 <-> silicon).

Fast in-memory and scratch-directory tests run first (so fail-fast mutation sweeps kill
mutants in <0.15s); live Lean 4.36.0 end-to-end verification runs last.
Zero bare asserts, zero float literals, zero null-device references, umask-077 safe.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

_TRACK_DIR = Path(__file__).resolve().parent
if str(_TRACK_DIR) not in sys.path:
    sys.path.insert(0, str(_TRACK_DIR))

import ceer_silicon_audit as A  # noqa: E402
import ceer_silicon_oracle as O  # noqa: E402


class _SubDict(dict):
    pass


class _SubList(list):
    pass


class _SubInt(int):
    pass


class _SubStr(str):
    pass


def _load_track_json(name: str) -> dict:
    return json.loads((_TRACK_DIR / name).read_text(encoding="utf-8"))


def _reseal(cert: dict) -> dict:
    c = copy.deepcopy(cert)
    c["certificate_sha256"] = A._compute_certificate_digest(c)
    return c


class Test01OracleCore(unittest.TestCase):
    def test_req_helpers(self) -> None:
        self.assertEqual(O._req_int(0, "x"), 0)
        self.assertEqual(O._req_int(-7, "x"), -7)
        self.assertEqual(O._req_pos(1, "x"), 1)
        for bad_pos in (0, -3):
            with self.assertRaises(O.OracleError) as cm:
                O._req_pos(bad_pos, "x")
            self.assertEqual(cm.exception.code, "NON_POSITIVE_VALUE")
        for bad in (True, False, _SubInt(5), "5", None, []):
            with self.assertRaises(O.OracleError) as cm:
                O._req_int(bad, "x")
            self.assertEqual(cm.exception.code, "NON_INTEGER_VALUE")
        self.assertEqual(O._req_dict({"a": 1}, "d"), {"a": 1})
        for bad_d in ([], _SubDict(a=1)):
            with self.assertRaises(O.OracleError) as cm:
                O._req_dict(bad_d, "d")
            self.assertEqual(cm.exception.code, "BAD_OBJECT")
        self.assertEqual(O._req_list([1], "l"), [1])
        for bad_l in ({}, _SubList([1])):
            with self.assertRaises(O.OracleError) as cm:
                O._req_list(bad_l, "l")
            self.assertEqual(cm.exception.code, "BAD_LIST")
        # Strict oracle JSON byte parser & artifact reader
        self.assertEqual(O._parse_json_bytes(b'{"k":1}', "t"), {"k": 1})
        for raw, code in (
            (b"\xff\xfe", "INVALID_UTF8"),
            (b"{bad", "INVALID_JSON"),
            (b'{"a":NaN}', "NON_FINITE_JSON"),
            (b'{"a":1.5}', "FLOAT_FORBIDDEN"),
            (b'{"a":1,"a":2}', "DUPLICATE_KEY"),
            (b"[1,2]", "BAD_OBJECT"),
        ):
            with self.assertRaises(O.OracleError) as cm:
                O._parse_json_bytes(raw, "t")
            self.assertEqual(cm.exception.code, code)
        with self.assertRaises(O.OracleError) as cm:
            O._read_artifact_bytes(_TRACK_DIR, "missing.json", {})
        self.assertEqual(cm.exception.code, "MISSING_ARTIFACT")
        with self.assertRaises(O.OracleError) as cm:
            O._read_artifact_bytes(_TRACK_DIR, "does_not_exist_r2.json", None)
        self.assertEqual(cm.exception.code, "READ_FAILED")

    def test_seg_map_and_get_seg(self) -> None:
        m = O._seg_map({"segments": [{"segment_id": "s1"}, {"segment_id": "s2"}]})
        self.assertEqual(O._get_seg(m, "s1")["segment_id"], "s1")
        with self.assertRaises(O.OracleError) as cm:
            O._get_seg(m, "missing")
        self.assertEqual(cm.exception.code, "MISSING_SEGMENT")
        for bad_seg in ({"segment_id": ""}, {"segment_id": 123}, {"segment_id": _SubStr("s1")}, {}):
            with self.assertRaises(O.OracleError) as cm:
                O._seg_map({"segments": [bad_seg]})
            self.assertEqual(cm.exception.code, "BAD_SEGMENT_ID")
        with self.assertRaises(O.OracleError) as cm:
            O._seg_map({"segments": [{"segment_id": "dup"}, {"segment_id": "dup"}]})
        self.assertEqual(cm.exception.code, "DUPLICATE_SEGMENT_ID")

    def test_polygon_area(self) -> None:
        self.assertEqual(O.compute_twice_polygon_area([0, 3, 0], [0, 0, 4]), 12)
        self.assertEqual(O.compute_twice_polygon_area([0, 0, 3], [0, 4, 0]), -12)
        self.assertEqual(O.compute_twice_polygon_area([1, 2], [3, 4]), 0)
        for xs, ys in (([1], [1]), ([1, 2], [1]), ([], [])):
            with self.assertRaises(O.OracleError) as cm:
                O.compute_twice_polygon_area(xs, ys)
            self.assertEqual(cm.exception.code, "BAD_POLYGON")

    def test_ramp_step_means(self) -> None:
        ts = [
            {"t_ms": 0, "v": 100},
            {"t_ms": 99, "v": 200},
            {"t_ms": 100, "v": 300},
            {"t_ms": 199, "v": 500},
        ]
        self.assertEqual(O.compute_ramp_step_means(ts, 2, 100, "v"), [150, 400])
        for n_steps, step_ms in ((1, 100), (2, 0), (2, -5)):
            with self.assertRaises(O.OracleError) as cm:
                O.compute_ramp_step_means(ts, n_steps, step_ms, "v")
            self.assertEqual(cm.exception.code, "BAD_RAMP_SPEC")
        with self.assertRaises(O.OracleError) as cm:
            O.compute_ramp_step_means([{"t_ms": 0, "v": 10}], 2, 100, "v")
        self.assertEqual(cm.exception.code, "EMPTY_RAMP_BIN")

    def test_centered_dot_and_exact_schur(self) -> None:
        self.assertEqual(O.centered_int_dot([1, 3, 5], [2, 4, 10]), 144)
        for a, b in (([1], [1]), ([1, 2], [1])):
            with self.assertRaises(O.OracleError) as cm:
                O.centered_int_dot(a, b)
            self.assertEqual(cm.exception.code, "BAD_SERIES")
        # Construct exact 3x3 Gram matrix from integer vectors y=[1,4,2,9], u=[0,1,2,3], v=[0,1,0,2]
        y, u, v = [1, 4, 2, 9], [0, 1, 2, 3], [0, 1, 0, 2]
        syy = O.centered_int_dot(y, y)
        suu = O.centered_int_dot(u, u)
        svv = O.centered_int_dot(v, v)
        syu = O.centered_int_dot(y, u)
        syv = O.centered_int_dot(y, v)
        suv = O.centered_int_dot(u, v)
        res = O.exact_schur_3x3(syy, suu, svv, syu, syv, suv)
        self.assertEqual(res["identity_residual"], 0)
        self.assertGreater(res["det_a"], 0)
        self.assertGreater(res["r1_num"], 0)
        self.assertGreater(res["variance_reduction_bps"], 0)
        self.assertEqual(len(res["variance_reduction_fraction"]), 2)
        # Degenerate r1_num <= 0 (y == u) and det_a <= 0 (v == u)
        with self.assertRaises(O.OracleError) as cm:
            O.exact_schur_3x3(suu, suu, svv, suu, syv, suv)
        self.assertEqual(cm.exception.code, "SCHUR_DEGENERATE")
        with self.assertRaises(O.OracleError) as cm:
            O.exact_schur_3x3(syy, suu, suu, syu, syu, suu)
        self.assertEqual(cm.exception.code, "SCHUR_DEGENERATE")


class Test02OracleExtractionAndChain(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = _load_track_json("cycle_0_telemetry.json")
        self.t1 = _load_track_json("cycle_1_telemetry.json")
        self.t2 = _load_track_json("cycle_2_telemetry.json")
        self.p0 = _load_track_json("cycle_0_prereg.json")
        self.p1 = _load_track_json("cycle_1_prereg.json")
        self.p2 = _load_track_json("cycle_2_prereg.json")

    def _seg(self, tel: dict, sid: str) -> dict:
        return next(s for s in tel["segments"] if s["segment_id"] == sid)

    def test_cycle0_extraction_and_boundary_flips(self) -> None:
        r = O.extract_cycle0_obs(self.t0)
        self.assertEqual(r["verdicts"]["corroborated_clean"], 0)
        self.assertEqual(r["verdicts"]["falsified_or_obstructed"], 4)
        self.assertTrue(r["verdicts"]["H0a_raw"])
        self.assertTrue(r["verdicts"]["H0a_degenerate_pl1"])
        self.assertFalse(r["verdicts"]["H0b"])
        self.assertFalse(r["verdicts"]["H0c"])
        self.assertTrue(r["verdicts"]["H0d_fan_plateau"])
        self.assertTrue(r["verdicts"]["H0d_thermal_lag_obstructed"])
        self.assertEqual(r["verdicts"]["cliff_16k_to_64m_100x"], 8122)

        # Exact boundary len(ts) == 8 allowed; len(ts) == 7 rejected
        t_len8 = copy.deepcopy(self.t0)
        self._seg(t_len8, "c0_u4_ramp")["time_series"] = self._seg(t_len8, "c0_u4_ramp")["time_series"][:8]
        self.assertIn("obs", O.extract_cycle0_obs(t_len8))
        t_short = copy.deepcopy(self.t0)
        self._seg(t_short, "c0_u4_ramp")["time_series"] = self._seg(t_short, "c0_u4_ramp")["time_series"][:7]
        with self.assertRaises(O.OracleError) as cm:
            O.extract_cycle0_obs(t_short)
        self.assertEqual(cm.exception.code, "BAD_SERIES")

        # Flip each clause of H0a_degenerate_pl1
        t_a = copy.deepcopy(self.t0)
        self._seg(t_a, "c0_u1_p8")["power_mw"]["package_0"] = self._seg(t_a, "c0_u1_p1")["power_mw"]["package_0"] + 201
        self.assertFalse(O.extract_cycle0_obs(t_a)["verdicts"]["H0a_degenerate_pl1"])
        t_a2 = copy.deepcopy(self.t0)
        self._seg(t_a2, "c0_u1_p8")["actuator_output"]["retired_ops"] = 6 * self._seg(t_a2, "c0_u1_p1")["actuator_output"]["retired_ops"]
        self.assertFalse(O.extract_cycle0_obs(t_a2)["verdicts"]["H0a_degenerate_pl1"])

        # Flip H0b clauses independently (make energy <= 2x while dark <= stays true, then dark >)
        t_b = copy.deepcopy(self.t0)
        self._seg(t_b, "c0_u3_64m")["actuator_output"]["chases"] = self._seg(t_b, "c0_u3_16k")["actuator_output"]["chases"]
        self.assertTrue(O.extract_cycle0_obs(t_b)["verdicts"]["H0b"])
        self._seg(t_b, "c0_u3_64m")["power_mw"]["psys"] = self._seg(t_b, "c0_u3_16k")["power_mw"]["psys"] + 5000
        self.assertFalse(O.extract_cycle0_obs(t_b)["verdicts"]["H0b"])

        # Flip H0d_fan_plateau and H0d_thermal_lag_obstructed clauses independently
        t_d = copy.deepcopy(self.t0)
        ts = self._seg(t_d, "c0_u4_ramp")["time_series"]
        ts[0]["cpu_fan_rpm"] = 3500
        ts[1]["pkg_temp_mc"] = ts[0]["pkg_temp_mc"] + 5000
        self.assertFalse(O.extract_cycle0_obs(t_d)["verdicts"]["H0d_fan_plateau"])
        t_d2 = copy.deepcopy(self.t0)
        for pt in self._seg(t_d2, "c0_u4_ramp")["time_series"]:
            pt["pkg_temp_mc"] = 85000
        v_d2 = O.extract_cycle0_obs(t_d2)["verdicts"]
        self.assertFalse(v_d2["H0d_thermal_lag_obstructed"])
        # Fan diff > 50 with zero area (constant T)
        ts2 = self._seg(t_d2, "c0_u4_ramp")["time_series"]
        for pt in ts2[len(ts2) // 2 :]:
            pt["cpu_fan_rpm"] = 3400
        self.assertFalse(O.extract_cycle0_obs(t_d2)["verdicts"]["H0d_fan_plateau"])
        # tempDown - tempUp > 1000 but twiceThermalLoadArea == 0: bump only interior constant-p samples on descent
        t_d3 = copy.deepcopy(self.t0)
        ts3 = self._seg(t_d3, "c0_u4_ramp")["time_series"]
        n3 = len(ts3)
        half = n3 // 2
        steps0 = [1, 2, 4, 8, 8, 4, 2, 1]
        p3 = [steps0[(i * 8) // n3] for i in range(n3)]
        for i, pt in enumerate(ts3):
            if i >= half and p3[(i - 1) % n3] == p3[(i + 1) % n3]:
                pt["pkg_temp_mc"] = 83000
            else:
                pt["pkg_temp_mc"] = 80000
        o_d3 = O.extract_cycle0_obs(t_d3)
        self.assertEqual(o_d3["obs"]["twiceThermalLoadArea"], 0)
        self.assertGreater(o_d3["obs"]["tempDownMeanMc"] - o_d3["obs"]["tempUpMeanMc"], 1000)
        self.assertFalse(o_d3["verdicts"]["H0d_thermal_lag_obstructed"])
        # tempDown - tempUp <= 1000 WITH twiceThermalLoadArea != 0
        t_d4 = copy.deepcopy(self.t0)
        ts4 = self._seg(t_d4, "c0_u4_ramp")["time_series"]
        for i, pt in enumerate(ts4):
            pt["pkg_temp_mc"] = 88000 if (i * 8) // len(ts4) == 2 else 85000
        o_d4 = O.extract_cycle0_obs(t_d4)
        self.assertNotEqual(o_d4["obs"]["twiceThermalLoadArea"], 0)
        self.assertLessEqual(o_d4["obs"]["tempDownMeanMc"] - o_d4["obs"]["tempUpMeanMc"], 1000)
        self.assertFalse(o_d4["verdicts"]["H0d_thermal_lag_obstructed"])

    def test_cycle1_extraction_and_boundary_flips(self) -> None:
        r = O.extract_cycle1_obs(self.t1)
        self.assertEqual(r["verdicts"]["corroborated_clean"], 2)
        self.assertEqual(r["verdicts"]["falsified_or_obstructed"], 2)
        self.assertTrue(r["verdicts"]["H1a"])
        self.assertFalse(r["verdicts"]["H1b"])
        self.assertTrue(r["verdicts"]["H1c"])
        self.assertFalse(r["verdicts"]["H1d"])

        # H1a flips: power delta > 5%, efficiency < 1.60x
        t = copy.deepcopy(self.t1)
        self._seg(t, "c1_u1_p6")["power_mw"]["package_0"] = 80000
        self.assertFalse(O.extract_cycle1_obs(t)["verdicts"]["H1a"])
        t = copy.deepcopy(self.t1)
        self._seg(t, "c1_u1_p6")["actuator_output"]["retired_ops"] = self._seg(t, "c1_u1_p3")["actuator_output"]["retired_ops"]
        self.assertFalse(O.extract_cycle1_obs(t)["verdicts"]["H1a"])

        # H1b flips: make cliff >= 1.50x, then zero each dark power independently
        t = copy.deepcopy(self.t1)
        self._seg(t, "c1_u3_32m")["actuator_output"]["chases"] = self._seg(t, "c1_u3_8m")["actuator_output"]["chases"] // 2
        self.assertTrue(O.extract_cycle1_obs(t)["verdicts"]["H1b"])
        t1 = copy.deepcopy(t)
        self._seg(t1, "c1_u3_8m")["power_mw"]["core"] = self._seg(t1, "c1_u3_8m")["power_mw"]["package_0"]
        self.assertFalse(O.extract_cycle1_obs(t1)["verdicts"]["H1b"])
        t2 = copy.deepcopy(t)
        self._seg(t2, "c1_u3_32m")["power_mw"]["core"] = self._seg(t2, "c1_u3_32m")["power_mw"]["package_0"]
        self.assertFalse(O.extract_cycle1_obs(t2)["verdicts"]["H1b"])

        # H1c flips: contrast23 <= contrast27, interiorMinusEdge <= 1500
        t = copy.deepcopy(self.t1)
        self._seg(t, "c1_u2_adj_23")["mean_temp_mc"]["core_2"] -= 5000
        self.assertFalse(O.extract_cycle1_obs(t)["verdicts"]["H1c"])
        t = copy.deepcopy(self.t1)
        for seg_id in ("c1_u2_adj_23", "c1_u2_dist_27"):
            for c in range(8):
                self._seg(t, seg_id)["mean_temp_mc"][f"core_{c}"] = 80000
            self._seg(t, seg_id)["mean_temp_mc"]["core_3"] = 81000
        self.assertFalse(O.extract_cycle1_obs(t)["verdicts"]["H1c"])

        # H1d flips: tempDown > tempUp with nonzero area vs zero area
        t = copy.deepcopy(self.t1)
        for pt in self._seg(t, "c1_u4_ramp")["time_series"]:
            pt["pkg_temp_mc"] = 80000 + pt["t_ms"]
        self.assertTrue(O.extract_cycle1_obs(t)["verdicts"]["H1d"])
        # Zero area with tempDown > tempUp: steps=[0,2,4,8,8,4,2,0], delta weights [-4,-6,-4,-2] on steps 4..7
        # d4=+6000, d5=-4000 -> -4*6000 - 6*(-4000) = 0 area AND tempDown - tempUp = +500 > 0!
        t = copy.deepcopy(self.t1)
        step_deltas = [0, 0, 0, 0, 6000, -4000, 0, 0]
        for pt in self._seg(t, "c1_u4_ramp")["time_series"]:
            s_idx = min(7, pt["t_ms"] // 1800)
            pt["pkg_temp_mc"] = 80000 + step_deltas[s_idx]
        r_z1 = O.extract_cycle1_obs(t)
        self.assertEqual(r_z1["obs"]["twiceThermalLoadArea"], 0)
        self.assertGreater(r_z1["obs"]["tempDownMeanMc"], r_z1["obs"]["tempUpMeanMc"])
        self.assertFalse(r_z1["verdicts"]["H1d"])

    def test_cycle2_extraction_and_boundary_flips(self) -> None:
        r = O.extract_cycle2_obs(self.t2)
        self.assertEqual(r["verdicts"]["corroborated_clean"], 3)
        self.assertEqual(r["verdicts"]["falsified_or_obstructed"], 1)
        self.assertTrue(r["verdicts"]["H2a"])
        self.assertFalse(r["verdicts"]["H2b_full"])
        self.assertTrue(r["verdicts"]["H2b_primary_cliff_and_dark"])
        self.assertFalse(r["verdicts"]["H2b_tail_12m_to_48m"])
        self.assertTrue(r["verdicts"]["H2c"])
        self.assertTrue(r["verdicts"]["H2d"])

        # Bad core_temps_mc length
        t = copy.deepcopy(self.t2)
        self._seg(t, "c2_u4_ramp")["time_series"][0]["core_temps_mc"] = [80000] * 7
        with self.assertRaises(O.OracleError) as cm:
            O.extract_cycle2_obs(t)
        self.assertEqual(cm.exception.code, "BAD_CORE_TEMPS")

        # H2a flips: power delta > 5%, raw eff < 1.25x (while freq eff >= 1.20x!), freq eff < 1.20x
        t = copy.deepcopy(self.t2)
        self._seg(t, "c2_u1_p7")["power_mw"]["package_0"] = 80000
        self.assertFalse(O.extract_cycle2_obs(t)["verdicts"]["H2a"])
        t = copy.deepcopy(self.t2)
        p5_seg, p7_seg = self._seg(t, "c2_u1_p5"), self._seg(t, "c2_u1_p7")
        p7_seg["delta_rapl_uj"]["package_0"] = p5_seg["delta_rapl_uj"]["package_0"]
        p7_seg["actuator_output"]["retired_ops"] = (122 * p5_seg["actuator_output"]["retired_ops"]) // 100
        for c in range(7):
            p7_seg["mean_freq_khz"][f"core_{c}"] = p5_seg["mean_freq_khz"]["core_0"]
        for c in range(5):
            p5_seg["mean_freq_khz"][f"core_{c}"] = p5_seg["mean_freq_khz"]["core_0"]
        self.assertFalse(O.extract_cycle2_obs(t)["verdicts"]["H2a"])
        t = copy.deepcopy(self.t2)
        for c in range(7):
            self._seg(t, "c2_u1_p7")["mean_freq_khz"][f"core_{c}"] = 5000000
        self.assertFalse(O.extract_cycle2_obs(t)["verdicts"]["H2a"])

        # H2b flips: make tail pass (full H2b True), then break each of the 5 primary clauses
        t_pass = copy.deepcopy(self.t2)
        self._seg(t_pass, "c2_u3_48m")["actuator_output"]["chases"] = self._seg(t_pass, "c2_u3_12m")["actuator_output"]["chases"] // 2
        self.assertTrue(O.extract_cycle2_obs(t_pass)["verdicts"]["H2b_full"])
        for seg_id in ("c2_u3_512k", "c2_u3_12m", "c2_u3_48m"):
            tb = copy.deepcopy(t_pass)
            self._seg(tb, seg_id)["power_mw"]["core"] = self._seg(tb, seg_id)["power_mw"]["package_0"]
            self.assertFalse(O.extract_cycle2_obs(tb)["verdicts"]["H2b_primary_cliff_and_dark"])
            self.assertFalse(O.extract_cycle2_obs(tb)["verdicts"]["H2b_full"])
        tb1 = copy.deepcopy(t_pass)
        self._seg(tb1, "c2_u3_48m")["actuator_output"]["chases"] = self._seg(tb1, "c2_u3_512k")["actuator_output"]["chases"]
        self.assertFalse(O.extract_cycle2_obs(tb1)["verdicts"]["H2b_primary_cliff_and_dark"])
        tb2 = copy.deepcopy(t_pass)
        self._seg(tb2, "c2_u3_12m")["actuator_output"]["chases"] = self._seg(tb2, "c2_u3_512k")["actuator_output"]["chases"]
        self.assertFalse(O.extract_cycle2_obs(tb2)["verdicts"]["H2b_primary_cliff_and_dark"])

        # H2c flips: isolated contrast45 <= 0 (with c16 < 0 & swing > 3000), isolated c16 >= 0 (with c45 > 0 & swing > 3000), swing <= 3000
        t = copy.deepcopy(self.t2)
        for c in range(8):
            self._seg(t, "c2_u2_hot_45")["mean_temp_mc"][f"core_{c}"] = 80000
            self._seg(t, "c2_u2_cool_16")["mean_temp_mc"][f"core_{c}"] = 80000
        self._seg(t, "c2_u2_hot_45")["mean_temp_mc"]["core_4"] = 79500
        self._seg(t, "c2_u2_hot_45")["mean_temp_mc"]["core_5"] = 79500
        self._seg(t, "c2_u2_cool_16")["mean_temp_mc"]["core_1"] = 75000
        self._seg(t, "c2_u2_cool_16")["mean_temp_mc"]["core_6"] = 75000
        self.assertFalse(O.extract_cycle2_obs(t)["verdicts"]["H2c"])
        t = copy.deepcopy(self.t2)
        for c in range(8):
            self._seg(t, "c2_u2_hot_45")["mean_temp_mc"][f"core_{c}"] = 80000
            self._seg(t, "c2_u2_cool_16")["mean_temp_mc"][f"core_{c}"] = 80000
        self._seg(t, "c2_u2_hot_45")["mean_temp_mc"]["core_4"] = 85000
        self._seg(t, "c2_u2_hot_45")["mean_temp_mc"]["core_5"] = 85000
        self._seg(t, "c2_u2_cool_16")["mean_temp_mc"]["core_1"] = 80500
        self._seg(t, "c2_u2_cool_16")["mean_temp_mc"]["core_6"] = 80500
        self.assertFalse(O.extract_cycle2_obs(t)["verdicts"]["H2c"])
        t = copy.deepcopy(self.t2)
        for c in range(8):
            self._seg(t, "c2_u2_hot_45")["mean_temp_mc"][f"core_{c}"] = 80000
            self._seg(t, "c2_u2_cool_16")["mean_temp_mc"][f"core_{c}"] = 80000
        self._seg(t, "c2_u2_hot_45")["mean_temp_mc"]["core_4"] = 80500
        self._seg(t, "c2_u2_hot_45")["mean_temp_mc"]["core_5"] = 80500
        self._seg(t, "c2_u2_cool_16")["mean_temp_mc"]["core_1"] = 79500
        self._seg(t, "c2_u2_cool_16")["mean_temp_mc"]["core_6"] = 79500
        self.assertFalse(O.extract_cycle2_obs(t)["verdicts"]["H2c"])

        # H2d flips: isolated zero area WITH soak >= 5% AND spread delta != 0!
        # weights [2, 5, 5, 0, -5, -5, -2]: deltas [-5000, +2000, 0, 0, 0, -2000, +5000] -> exact 0 area, high soak!
        t = copy.deepcopy(self.t2)
        zero_area_d = [-5000, 2000, 0, 0, 0, -2000, 5000]
        synth_za = []
        for s_idx in range(7):
            for k in (0, 1):
                temp_v = 80000 + zero_area_d[s_idx]
                synth_za.append({
                    "t_ms": s_idx * 1500 + k * 500,
                    "pkg_temp_mc": temp_v,
                    "core_temps_mc": [temp_v + 1000, 74000, 74000, 74000, 74000, 74000, 74000, 74000],
                })
        self._seg(t, "c2_u4_ramp")["time_series"] = synth_za
        r_za = O.extract_cycle2_obs(t)
        self.assertEqual(r_za["obs"]["twiceThermalLoadArea"], 0)
        self.assertGreaterEqual(r_za["schur_soak"]["variance_reduction_bps"], 500)
        self.assertNotEqual(r_za["schur_spread"]["delta"], 0)
        self.assertFalse(r_za["verdicts"]["H2d"])
        # Nonzero area, low soak (<5%), nonzero spread
        t2 = copy.deepcopy(self.t2)
        ts2 = self._seg(t2, "c2_u4_ramp")["time_series"]
        for i, pt in enumerate(ts2):
            step_idx = min(6, pt["t_ms"] // 1500)
            pt["pkg_temp_mc"] = 80000 + (500 if step_idx == 2 else 0) + (i % 7) * 500
            pt["core_temps_mc"] = [80000 + (i % 5) * 1000, 80000, 80000, 80000, 80000, 80000, 80000, 80000]
        r_low = O.extract_cycle2_obs(t2)
        self.assertNotEqual(r_low["obs"]["twiceThermalLoadArea"], 0)
        self.assertFalse(r_low["verdicts"]["H2d"])
        # Nonzero area, strong soak (>=5%), zero spread delta (v_spread orthogonal to y after u)
        t3 = copy.deepcopy(self.t2)
        ts3 = self._seg(t3, "c2_u4_ramp")["time_series"]
        for i, pt in enumerate(ts3):
            pt["pkg_temp_mc"] = 80000 + pt["t_ms"]
            # Make spread purely alternating even/odd around a balanced pair so delta_spr == 0
            pt["core_temps_mc"] = [81000 if (i % 2 == 0) else 80000, 80000, 80000, 80000, 80000, 80000, 80000, 80000]
        # Force exact delta_spr == 0 by using 14 synthetic points (2 per step, exact symmetric)
        synth_ts = []
        for s_idx in range(7):
            for k in (0, 1):
                t_ms = s_idx * 1500 + k * 750
                # y depends ONLY on step index linearly (not k); spread depends ONLY on k (-1/+1)
                # u is symmetric in step_idx, so u is orthogonal to k too -> suv_spr = 0, syv_spr = 0 -> delta_spr = 0!
                synth_ts.append({
                    "t_ms": t_ms,
                    "pkg_temp_mc": 80000 + s_idx * 1000,
                    "core_temps_mc": [81000 if k == 0 else 80000, 80000, 80000, 80000, 80000, 80000, 80000, 80000],
                })
        self._seg(t3, "c2_u4_ramp")["time_series"] = synth_ts
        r_zspr = O.extract_cycle2_obs(t3)
        self.assertEqual(r_zspr["schur_spread"]["delta"], 0)
        self.assertNotEqual(r_zspr["obs"]["twiceThermalLoadArea"], 0)
        self.assertFalse(r_zspr["verdicts"]["H2d"])

    def test_disjoint_levers_and_prereg_chain_errors(self) -> None:
        self.assertEqual(O.verify_disjoint_held_out_levers([self.p0, self.p1, self.p2])["total_distinct_core_counts"], 8)
        with self.assertRaises(O.OracleError) as cm:
            O.verify_disjoint_held_out_levers([self.p0, self.p1])
        self.assertEqual(cm.exception.code, "BAD_CYCLE_COUNT")

        p_bad_pair = copy.deepcopy(self.p1)
        p_bad_pair["held_out_levers"]["u2_pairs"] = [[2, 3, 4]]
        with self.assertRaises(O.OracleError) as cm:
            O.verify_disjoint_held_out_levers([self.p0, p_bad_pair, self.p2])
        self.assertEqual(cm.exception.code, "BAD_PAIR")

        p_ov_c = copy.deepcopy(self.p1)
        p_ov_c["held_out_levers"]["u1_cores"] = [1, 6]
        with self.assertRaises(O.OracleError) as cm:
            O.verify_disjoint_held_out_levers([self.p0, p_ov_c, self.p2])
        self.assertEqual(cm.exception.code, "OVERLAPPING_CORES")

        p_ov_p = copy.deepcopy(self.p2)
        p_ov_p["held_out_levers"]["u2_pairs"] = [[7, 2], [1, 6]]  # reversed (2,7)
        with self.assertRaises(O.OracleError) as cm:
            O.verify_disjoint_held_out_levers([self.p0, self.p1, p_ov_p])
        self.assertEqual(cm.exception.code, "OVERLAPPING_PAIRS")

        p_ov_b = copy.deepcopy(self.p2)
        p_ov_b["held_out_levers"]["u3_bytes"] = [16384, 12582912, 50331648]
        with self.assertRaises(O.OracleError) as cm:
            O.verify_disjoint_held_out_levers([self.p0, self.p1, p_ov_b])
        self.assertEqual(cm.exception.code, "OVERLAPPING_BYTES")

        p_dup_r = copy.deepcopy(self.p2)
        p_dup_r["held_out_levers"]["u4_ramp_step_ms"] = self.p0["held_out_levers"]["u4_ramp_step_ms"]
        p_dup_r["held_out_levers"]["u4_ramp_steps"] = list(self.p0["held_out_levers"]["u4_ramp_steps"])
        with self.assertRaises(O.OracleError) as cm:
            O.verify_disjoint_held_out_levers([self.p0, self.p1, p_dup_r])
        self.assertEqual(cm.exception.code, "DUPLICATE_RAMP")

        # Scratch copy of track dir to exercise every compute_ceer_summary error path
        with tempfile.TemporaryDirectory(prefix="ceer_chain_") as td:
            root = Path(td)
            shutil.copytree(_TRACK_DIR / "CEERSiliconCerts", root / "CEERSiliconCerts")
            for cid in (0, 1, 2):
                for kind in ("prereg", "telemetry"):
                    shutil.copy2(_TRACK_DIR / f"cycle_{cid}_{kind}.json", root / f"cycle_{cid}_{kind}.json")
            self.assertTrue(O.compute_ceer_summary(root)["epistemic_trajectory"]["strictly_monotone"])

            def _rewrite_and_expect(fname: str, mut_fn, code: str) -> None:
                orig = (root / fname).read_bytes()
                try:
                    obj = json.loads(orig.decode("utf-8"))
                    mut_fn(obj)
                    (root / fname).write_bytes(A.canonical_json_bytes(obj) + b"\n")
                    with self.assertRaises(O.OracleError) as cm:
                        O.compute_ceer_summary(root)
                    self.assertEqual(cm.exception.code, code)
                finally:
                    (root / fname).write_bytes(orig)

            _rewrite_and_expect("cycle_0_prereg.json", lambda o: o.update({"cycle_id": 9}), "CYCLE_ID_MISMATCH")
            _rewrite_and_expect("cycle_0_telemetry.json", lambda o: o.update({"cycle_id": 9}), "CYCLE_ID_MISMATCH")
            _rewrite_and_expect("cycle_0_prereg.json", lambda o: o.update({"cycle_id": False}), "NON_INTEGER_VALUE")
            _rewrite_and_expect("cycle_0_telemetry.json", lambda o: o.update({"cycle_id": False}), "NON_INTEGER_VALUE")
            _rewrite_and_expect("cycle_0_prereg.json", lambda o: o.update({"theory_lean_sha256": "0" * 64}), "THEORY_SHA_MISMATCH")
            _rewrite_and_expect("cycle_0_telemetry.json", lambda o: o.update({"prereg_sha256": "0" * 64}), "PREREG_TEL_MISMATCH")

            # For root parent / chain break we must also re-link telemetry prereg_sha256
            orig_p0 = (root / "cycle_0_prereg.json").read_bytes()
            orig_t0 = (root / "cycle_0_telemetry.json").read_bytes()
            try:
                p0_obj = json.loads(orig_p0.decode("utf-8"))
                p0_obj["parent_cycle_verdict_sha256"] = "a" * 64
                raw_p0 = A.canonical_json_bytes(p0_obj) + b"\n"
                (root / "cycle_0_prereg.json").write_bytes(raw_p0)
                t0_obj = json.loads(orig_t0.decode("utf-8"))
                t0_obj["prereg_sha256"] = hashlib.sha256(raw_p0).hexdigest()
                (root / "cycle_0_telemetry.json").write_bytes(A.canonical_json_bytes(t0_obj) + b"\n")
                with self.assertRaises(O.OracleError) as cm:
                    O.compute_ceer_summary(root)
                self.assertEqual(cm.exception.code, "BAD_ROOT_PARENT")
            finally:
                (root / "cycle_0_prereg.json").write_bytes(orig_p0)
                (root / "cycle_0_telemetry.json").write_bytes(orig_t0)

            orig_p1 = (root / "cycle_1_prereg.json").read_bytes()
            orig_t1 = (root / "cycle_1_telemetry.json").read_bytes()
            try:
                p1_obj = json.loads(orig_p1.decode("utf-8"))
                p1_obj["parent_cycle_verdict_sha256"] = "b" * 64
                raw_p1 = A.canonical_json_bytes(p1_obj) + b"\n"
                (root / "cycle_1_prereg.json").write_bytes(raw_p1)
                t1_obj = json.loads(orig_t1.decode("utf-8"))
                t1_obj["prereg_sha256"] = hashlib.sha256(raw_p1).hexdigest()
                (root / "cycle_1_telemetry.json").write_bytes(A.canonical_json_bytes(t1_obj) + b"\n")
                with self.assertRaises(O.OracleError) as cm:
                    O.compute_ceer_summary(root)
                self.assertEqual(cm.exception.code, "CHAIN_BREAK")
            finally:
                (root / "cycle_1_prereg.json").write_bytes(orig_p1)
                (root / "cycle_1_telemetry.json").write_bytes(orig_t1)

            # Non-monotone convergence (break C2 H2a and H2c so C2 corroborated == 1 <= C1 == 2)
            orig_t2 = (root / "cycle_2_telemetry.json").read_bytes()
            try:
                t2_obj = json.loads(orig_t2.decode("utf-8"))
                self._seg(t2_obj, "c2_u1_p7")["power_mw"]["package_0"] = 99999
                self._seg(t2_obj, "c2_u2_hot_45")["mean_temp_mc"]["core_4"] = 50000
                self._seg(t2_obj, "c2_u2_hot_45")["mean_temp_mc"]["core_5"] = 50000
                (root / "cycle_2_telemetry.json").write_bytes(A.canonical_json_bytes(t2_obj) + b"\n")
                with self.assertRaises(O.OracleError) as cm:
                    O.compute_ceer_summary(root)
                self.assertEqual(cm.exception.code, "NON_MONOTONE_CONVERGENCE")
            finally:
                (root / "cycle_2_telemetry.json").write_bytes(orig_t2)


class Test03JsonTreeAndStrictParse(unittest.TestCase):
    def test_validate_json_tree_bounds_types_subclasses_chars(self) -> None:
        # Depth 64 allowed, 65 rejected
        d64: object = 1
        for _ in range(A.MAX_JSON_DEPTH):
            d64 = [d64]
        A._validate_json_tree(d64)
        with self.assertRaises(A.AuditError) as cm:
            A._validate_json_tree([d64])
        self.assertEqual(cm.exception.code, "DEPTH_LIMIT")

        A._validate_json_tree({"a": [None, True, False, 42, (1 << A.MAX_INT_BITS) - 1, "ok"]})
        for big_i in (1 << A.MAX_INT_BITS, 10**2000):
            with self.assertRaises(A.AuditError) as cm:
                A._validate_json_tree({"x": big_i})
            self.assertEqual(cm.exception.code, "INT_BIT_LIMIT")
        with mock.patch.object(A, "MAX_JSON_NODES", 3):
            A._validate_json_tree([1, 2])
            with self.assertRaises(A.AuditError) as cm:
                A._validate_json_tree([1, 2, 3])
            self.assertEqual(cm.exception.code, "NODE_LIMIT")
        for bad in (json.loads("1.5"), _SubDict(a=1), _SubList([1]), _SubInt(1), _SubStr("x"), (1, 2)):
            with self.assertRaises(A.AuditError) as cm:
                A._validate_json_tree(bad)
            self.assertEqual(cm.exception.code, "FORBIDDEN_TYPE")
        with self.assertRaises(A.AuditError) as cm:
            A._validate_json_tree({1: "a"})
        self.assertEqual(cm.exception.code, "NON_STR_KEY")
        with self.assertRaises(A.AuditError) as cm:
            A._validate_json_tree({_SubStr("k"): 1})
        self.assertEqual(cm.exception.code, "NON_STR_KEY")
        for bad_obj, code in (
            ({"a\x00b": 1}, "NUL_IN_STRING"),
            ({"a": "x\x00y"}, "NUL_IN_STRING"),
            ({"a\ud800": 1}, "SURROGATE_CHAR"),
            ({"a": "\udfff"}, "SURROGATE_CHAR"),
        ):
            with self.assertRaises(A.AuditError) as cm:
                A._validate_json_tree(bad_obj)
            self.assertEqual(cm.exception.code, code)

    def test_parse_strict_json_bytes(self) -> None:
        self.assertEqual(A.parse_strict_json_bytes(b'{"k":1}\n'), {"k": 1})
        huge_int = b'{"k":' + (b"9" * 5000) + b"}\n"
        for raw, code in (
            (b"\xff\xfe", "INVALID_UTF8"),
            (b"{bad", "INVALID_JSON"),
            (huge_int, "INVALID_JSON"),
            (b'{"a":NaN}\n', "NON_FINITE_JSON"),
            (b'{"a":Infinity}\n', "NON_FINITE_JSON"),
            (b'{"a":-Infinity}\n', "NON_FINITE_JSON"),
            (b'{"a":1.5}\n', "FLOAT_FORBIDDEN"),
            (b'{"a":1,"a":2}\n', "DUPLICATE_KEY"),
            (b"[1,2,3]\n", "ROOT_NOT_OBJECT"),
            (b'{"k":1}\r\n', "NON_CANONICAL_JSON"),
            (b'{"k": 1}\n', "NON_CANONICAL_JSON"),
            (b'{"k":1}', "NON_CANONICAL_JSON"),
        ):
            with self.assertRaises(A.AuditError) as cm:
                A.parse_strict_json_bytes(raw)
            self.assertEqual(cm.exception.code, code)


class Test04HardenedFilesystemAndCLI(unittest.TestCase):
    def test_verified_cwd_darwin_and_cli_path_arg(self) -> None:
        cwd = os.getcwd()
        with mock.patch.dict(os.environ, {"PWD": cwd}):
            self.assertEqual(A._verified_cwd(), Path(cwd))
        with mock.patch.dict(os.environ, {"PWD": ""}):
            self.assertEqual(A._verified_cwd(), Path(cwd))
        with mock.patch.dict(os.environ, {"PWD": "."}):
            # Relative "." matches (st_dev, st_ino) of "." yet MUST be rejected by isabs!
            self.assertEqual(A._verified_cwd(), Path(cwd))
        with mock.patch.dict(os.environ, {"PWD": "/"}):
            self.assertEqual(A._verified_cwd(), Path(cwd))
        with mock.patch.dict(os.environ, {"PWD": "/nonexistent_ceer_pwd_dir"}):
            self.assertEqual(A._verified_cwd(), Path(cwd))
        with mock.patch.object(A.os, "environ", {"PWD": "/tmp/\ud800"}):
            self.assertEqual(A._verified_cwd(), Path(cwd))
        st_root_lnk = os.stat_result((stat.S_IFLNK | 0o777, 1, 1, 1, 0, 0, 0, 0, 0, 0))
        st_root_dir = os.stat_result((stat.S_IFDIR | 0o755, 1, 1, 1, 0, 0, 0, 0, 0, 0))
        st_user_lnk = os.stat_result((stat.S_IFLNK | 0o777, 1, 1, 1, 1000, 1000, 0, 0, 0, 0))
        with mock.patch.object(sys, "platform", "darwin"):
            with mock.patch.object(os, "lstat", return_value=st_root_lnk):
                with mock.patch.object(os, "readlink", side_effect=lambda p: "private" + p):
                    self.assertEqual(A._normalize_darwin_prefix(Path("/tmp")), Path("/private/tmp"))
                    self.assertEqual(A._normalize_darwin_prefix(Path("/tmp/a.json")), Path("/private/tmp/a.json"))
                    self.assertEqual(A._normalize_darwin_prefix(Path("/var/b")), Path("/private/var/b"))
                    self.assertEqual(A._normalize_darwin_prefix(Path("/etc/c")), Path("/private/etc/c"))
                    self.assertEqual(A._normalize_darwin_prefix(Path("/tmp2/d")), Path("/tmp2/d"))
                with mock.patch.object(os, "readlink", return_value="other/tmp"):
                    self.assertEqual(A._normalize_darwin_prefix(Path("/tmp/a.json")), Path("/tmp/a.json"))
            with mock.patch.object(os, "lstat", return_value=st_root_dir), mock.patch.object(os, "readlink", return_value="private/tmp"):
                self.assertEqual(A._normalize_darwin_prefix(Path("/tmp/a.json")), Path("/tmp/a.json"))
            with mock.patch.object(os, "lstat", return_value=st_user_lnk):
                with mock.patch.object(os, "readlink", return_value="private/tmp"):
                    self.assertEqual(A._normalize_darwin_prefix(Path("/tmp/a.json")), Path("/tmp/a.json"))
            with mock.patch.object(os, "lstat", side_effect=OSError("no")):
                self.assertEqual(A._normalize_darwin_prefix(Path("/tmp/a.json")), Path("/tmp/a.json"))
        with mock.patch.object(sys, "platform", "linux"):
            self.assertEqual(A._normalize_darwin_prefix(Path("/tmp/a.json")), Path("/tmp/a.json"))

        for bad, code in (
            ("", "BAD_PATH"),
            (123, "BAD_PATH"),
            ("a\x00b", "NUL_IN_STRING"),
            ("/tmp/\ud800.json", "SURROGATE_CHAR"),
            ("-x", "FLAG_LIKE_PATH"),
            ("--check", "FLAG_LIKE_PATH"),
        ):
            with self.assertRaises(A.AuditError) as cm:
                A._check_cli_path_arg(bad)
            self.assertEqual(cm.exception.code, code)
        self.assertTrue(A._check_cli_path_arg("rel.json").is_absolute())

    def test_read_and_write_filesystem_hardening(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ceer_zb_") as td:
            root = Path(td)
            f1 = root / "ok.json"
            A.write_atomic_0600(f1, b'{"ok":1}\n')
            self.assertEqual(stat.S_IMODE(f1.stat().st_mode), 0o600)
            self.assertEqual(A.read_regular_file_strict(f1), b'{"ok":1}\n')
            # Overwrite existing regular file atomically
            A.write_atomic_0600(f1, b'{"ok":2}\n')
            self.assertEqual(A.read_regular_file_strict(f1), b'{"ok":2}\n')

            # Missing leaf & missing parent
            with self.assertRaises(A.AuditError) as cm:
                A.read_regular_file_strict(root / "no_such.json")
            self.assertEqual(cm.exception.code, "PATH_NOT_FOUND")
            with self.assertRaises(A.AuditError) as cm:
                A.write_atomic_0600(root / "no_parent" / "x.json", b"{}")
            self.assertEqual(cm.exception.code, "PARENT_NOT_FOUND")

            # Symlink leaf and symlink parent
            sym = root / "sym.json"
            sym.symlink_to(f1)
            with self.assertRaises(A.AuditError) as cm:
                A.read_regular_file_strict(sym)
            self.assertEqual(cm.exception.code, "SYMLINK_REJECTED")
            with self.assertRaises(A.AuditError) as cm:
                A.write_atomic_0600(sym, b"{}")
            self.assertEqual(cm.exception.code, "SYMLINK_REJECTED")

            sub = root / "realdir"
            sub.mkdir()
            symdir = root / "symdir"
            symdir.symlink_to(sub)
            with self.assertRaises(A.AuditError) as cm:
                A.write_atomic_0600(symdir / "x.json", b"{}")
            self.assertEqual(cm.exception.code, "SYMLINK_REJECTED")

            # Hardlink rejection on read & write
            hl = root / "hl.json"
            os.link(f1, hl)
            with self.assertRaises(A.AuditError) as cm:
                A.read_regular_file_strict(hl)
            self.assertEqual(cm.exception.code, "HARDLINK_REJECTED")
            with self.assertRaises(A.AuditError) as cm:
                A.write_atomic_0600(hl, b"{}")
            self.assertEqual(cm.exception.code, "HARDLINK_REJECTED")
            hl.unlink()

            # Scratch FIFO rejection & directory rejection
            fifo = root / "pipe.fifo"
            os.mkfifo(fifo)
            with self.assertRaises(A.AuditError) as cm:
                A.read_regular_file_strict(fifo)
            self.assertEqual(cm.exception.code, "NOT_REGULAR_FILE")
            with self.assertRaises(A.AuditError) as cm:
                A.write_atomic_0600(fifo, b"{}")
            self.assertEqual(cm.exception.code, "NOT_REGULAR_FILE")
            with self.assertRaises(A.AuditError) as cm:
                A.read_regular_file_strict(sub)
            self.assertEqual(cm.exception.code, "NOT_REGULAR_FILE")
            with self.assertRaises(A.AuditError) as cm:
                A.write_atomic_0600(sub, b"{}")
            self.assertEqual(cm.exception.code, "NOT_REGULAR_FILE")

            # Size cap checks: exact boundary allowed, st_size cap fails before os.read, AND streaming cap
            exact_len = len(f1.read_bytes())
            self.assertEqual(len(A.read_regular_file_strict(f1, max_bytes=exact_len)), exact_len)
            with mock.patch.object(os, "read", side_effect=RuntimeError("must not read oversized")):
                with self.assertRaises(A.AuditError) as cm:
                    A.read_regular_file_strict(f1, max_bytes=exact_len - 1)
                self.assertEqual(cm.exception.code, "FILE_TOO_LARGE")
            real_fstat = os.fstat

            def _zero_size_fstat(fd_arg: int):
                st = real_fstat(fd_arg)
                return os.stat_result((st.st_mode, st.st_ino, st.st_dev, st.st_nlink, st.st_uid, st.st_gid, 0, st.st_atime, st.st_mtime, st.st_ctime))

            with mock.patch.object(os, "fstat", side_effect=_zero_size_fstat):
                with self.assertRaises(A.AuditError) as cm:
                    A.read_regular_file_strict(f1, max_bytes=4)
                self.assertEqual(cm.exception.code, "FILE_TOO_LARGE")

            # Mocked os.open OSError on file open
            real_open = os.open

            def _fail_second_open(*args, **kwargs):
                if "dir_fd" in kwargs:
                    raise PermissionError(13, "denied")
                return real_open(*args, **kwargs)

            with mock.patch.object(os, "open", side_effect=_fail_second_open):
                with self.assertRaises(A.AuditError) as cm:
                    A.read_regular_file_strict(f1)
                self.assertEqual(cm.exception.code, "OPEN_FAILED")

            # Mocked partial writes + zero-byte short write cleanup
            real_write = os.write
            calls = {"n": 0}

            def _chunked_write(fd_arg: int, buf):
                calls["n"] += 1
                return real_write(fd_arg, bytes(buf[:3]))

            f2 = root / "chunked.json"
            with mock.patch.object(os, "write", side_effect=_chunked_write):
                A.write_atomic_0600(f2, b"12345678")
            self.assertEqual(f2.read_bytes(), b"12345678")
            self.assertGreater(calls["n"], 1)

            f3 = root / "short.json"
            sw_calls = {"n": 0}

            def _zero_once(*_a, **_kw):
                sw_calls["n"] += 1
                if sw_calls["n"] > 1:
                    raise RuntimeError("write loop did not abort on 0-byte write")
                return 0

            with mock.patch.object(os, "write", side_effect=_zero_once):
                with self.assertRaises(A.AuditError) as cm:
                    A.write_atomic_0600(f3, b"abc")
                self.assertEqual(cm.exception.code, "SHORT_WRITE")
            self.assertFalse(f3.exists())
            self.assertEqual([p.name for p in root.glob(".short.json.*")], [])

            # Wrapped OSErrors: chmod 500 dir on write, mocked lstat/open/read/replace errors
            ro_dir = root / "ro_dir"
            ro_dir.mkdir(mode=0o700)
            os.chmod(ro_dir, 0o500)
            try:
                with self.assertRaises(A.AuditError) as cm:
                    A.write_atomic_0600(ro_dir / "blocked.json", b"{}")
                self.assertEqual(cm.exception.code, "WRITE_FAILED")
            finally:
                os.chmod(ro_dir, 0o700)

            with mock.patch.object(os, "replace", side_effect=OSError(5, "replace fail")):
                with self.assertRaises(A.AuditError) as cm:
                    A.write_atomic_0600(root / "rep_fail.json", b"{}")
                self.assertEqual(cm.exception.code, "WRITE_FAILED")

            with mock.patch.object(os, "lstat", side_effect=PermissionError(13, "no stat")):
                with self.assertRaises(A.AuditError) as cm:
                    A.read_regular_file_strict(f1)
                self.assertEqual(cm.exception.code, "STAT_FAILED")
            with mock.patch.object(os, "open", side_effect=PermissionError(13, "no dir")):
                with self.assertRaises(A.AuditError) as cm:
                    A.read_regular_file_strict(f1)
                self.assertEqual(cm.exception.code, "OPEN_FAILED")
                with self.assertRaises(A.AuditError) as cm:
                    A.write_atomic_0600(f1, b"{}")
                self.assertEqual(cm.exception.code, "WRITE_FAILED")
            with mock.patch.object(os, "read", side_effect=OSError(5, "io err")):
                with self.assertRaises(A.AuditError) as cm:
                    A.read_regular_file_strict(f1)
                self.assertEqual(cm.exception.code, "READ_FAILED")
            real_lstat = os.lstat

            def _fail_dirfd_lstat(*args, **kwargs):
                if "dir_fd" in kwargs:
                    raise PermissionError(13, "no target stat")
                return real_lstat(*args, **kwargs)

            with mock.patch.object(os, "lstat", side_effect=_fail_dirfd_lstat):
                with self.assertRaises(A.AuditError) as cm:
                    A.write_atomic_0600(f1, b"{}")
                self.assertEqual(cm.exception.code, "STAT_FAILED")

            # Bounded FileExistsError retries (once -> succeeds; exhausted -> TEMP_EXHAUSTED),
            # hardlinked temp file rejection, and wrapped os.unlink cleanup error
            eexist_cnt = {"n": 0}

            def _eexist_once(p_arg, fl_arg, *a, **kw):
                if (fl_arg & os.O_EXCL) and eexist_cnt["n"] == 0:
                    eexist_cnt["n"] += 1
                    raise FileExistsError("dup once")
                return real_open(p_arg, fl_arg, *a, **kw)

            f_retry = root / "retry_ok.json"
            with mock.patch.object(os, "open", side_effect=_eexist_once):
                A.write_atomic_0600(f_retry, b'{"r":1}\n')
            self.assertEqual(eexist_cnt["n"], 1)
            self.assertEqual(f_retry.read_bytes(), b'{"r":1}\n')

            eexist_all = {"n": 0}

            def _eexist_always(p_arg, fl_arg, *a, **kw):
                if fl_arg & os.O_EXCL:
                    eexist_all["n"] += 1
                    raise FileExistsError("dup always")
                return real_open(p_arg, fl_arg, *a, **kw)

            with mock.patch.object(os, "open", side_effect=_eexist_always):
                with self.assertRaises(A.AuditError) as cm:
                    A.write_atomic_0600(root / "retry_fail.json", b"{}")
                self.assertEqual(cm.exception.code, "TEMP_EXHAUSTED")
            self.assertEqual(eexist_all["n"], A._MAX_TMP_RETRIES)

            def _nlink2_fstat(fd_arg: int):
                st = real_fstat(fd_arg)
                return os.stat_result((st.st_mode, st.st_ino, st.st_dev, 2, st.st_uid, st.st_gid, st.st_size, st.st_atime, st.st_mtime, st.st_ctime))

            with mock.patch.object(os, "fstat", side_effect=_nlink2_fstat):
                with self.assertRaises(A.AuditError) as cm:
                    A.write_atomic_0600(root / "tmp_hl.json", b"{}")
                self.assertEqual(cm.exception.code, "HARDLINK_REJECTED")

            sw_calls["n"] = 0
            with mock.patch.object(os, "write", side_effect=_zero_once), mock.patch.object(os, "unlink", side_effect=OSError(13, "unlink fail")):
                with self.assertRaises(A.AuditError) as cm:
                    A.write_atomic_0600(root / "unlink_err.json", b"abc")
                self.assertEqual(cm.exception.code, "SHORT_WRITE")
            for p_left in root.glob(".unlink_err.json.*"):
                p_left.unlink()


class Test05Lean4StaticScanner12Controls(unittest.TestCase):
    def test_comments_strings_and_clean_forms(self) -> None:
        clean = (
            "/- nested /- sorry native_decide -/ comment -/\n"
            "-- line comment sorry axiom\n"
            'def s := "escaped \\" \\\n sorry native_decide"\n'
            'def raw1 := r#"contains " sorry " inside\nline"#\n'
            'def raw0 := r"plain sorry"\n'
            "def r_ident := r + r1\n"
            'def c1 := \'"\' ; def c2 := \'\\n\' ; def c3 := \'a\'\n'
            "def x' := 1\n"
            'def interp1 := s!"hello \\" \\\n { { a := 1 } } world"\n'
            'def interp2 := m!"ok"\n'
            'def non_interp := foo!"bar"\n'
            "def x := Foo.axiom + Foo.unsafe + SmoothShell.partial\n"
            "theorem t1 : 1 = 1 := by decide\n"
            "theorem t2 : 1 = 1 := by decide -native\n"
            "theorem t3 : 1 = 1 := by decide (native := false)\n"
            "theorem t4 : 1 = 1 := by decide (native := (Bool.false))\n"
            "theorem t5 : 1 = 1 := by decide (config := { native := false })\n"
            "theorem t6 : 1 = 1 := by decide (config := ({ native := Bool.false, zeta := true }))\n"
            "theorem t7 : 1 = 1 := by decide (config := { native := false, })\n"
            "theorem t8 : 1 = 1 := by decide (maxHeartbeats := 100)\n"
            "theorem t9 : 1 = 1 := by decide (foo)\n"
            "theorem t10 : 1 = 1 := by decide +\n"
            "theorem t11 : 1 = 1 := by decide (\n"
            "def safeCfg : DecideConfig := { native := false }\n"
            "theorem t12 : 1 = 1 := by decide"
        )
        self.assertEqual(A.scan_lean4_source(clean), [])
        # Lexer edge-case defenses: Char, raw, interp, comments, EOF boundaries
        for clean_edge in (
            'r"start_of_file_raw"',
            's!"start_of_file_interp"',
            "def a := 1 -- sorry",
            "def eof_r := r#",
            '!"{by sorry}" + s',
            "def bang_expr := s!a",
            'def not_interp_ss := ss"{by sorry}"',
            'def not_interp_a := a!"{by sorry}"',
            'def not_interp_x := xs!"{by sorry}"',
            'def not_interp_u := _s!"{by sorry}"',
            "def trailing_quote := 'a",
            "def trailing_esc := '\\",
        ):
            with self.subTest(clean_edge=clean_edge):
                self.assertEqual(A.scan_lean4_source(clean_edge), [])
        for bypass in (
            '\'"\'; theorem bad : True := by sorry',
            'def q := \'"\'; theorem bad : True := by sorry',
            'def q := \'\\"\'; theorem bad : True := by sorry',
            'def q := \'\\\'\',\'"\'; theorem bad : True := by sorry',
            'def f (x\' : Char -> Nat) := x\' \'"\'; theorem bad : True := by sorry',
            'def f (_\' : Char -> Nat) := _\' \'"\'; theorem bad : True := by sorry',
            'def f («x»\' : Char -> Nat) := «x»\' \'"\'; theorem bad : True := by sorry',
            'def q := \'\\\'"\'; theorem bad : True := by sorry',
            'def a := \' "ok"; theorem bad : True := by sorry',
            'def a := \'a \'"\'; theorem bad : True := by sorry',
            'def a := \'\\x"ok"; theorem bad : True := by sorry',
            'def x\'="ok"; theorem bad : True := by sorry',
            'def f := x\'="\'" + "a"; theorem bad : True := by sorry',
            'def f := x\'\\a"ok"; theorem bad : True := by sorry',
            'def a := \'x + \'y\'; theorem bad : True := by sorry',
            'def a := \'\\x + y\'; theorem bad : True := by sorry',
            'def d := 10 / 2; theorem bad : True := by sorry',
            '-- comment line\ntheorem bad : True := by sorry',
            'r"\\"; theorem bad : True := by sorry',
            'def s := r"\\"; theorem bad : True := by sorry',
            'def x := ar"\\""; theorem bad : True := by sorry',
            'def x := _r"\\""; theorem bad : True := by sorry',
            's!"{by sorry}" + a',
            'def s := s!"{by sorry}"',
            'def s := f!"prefix { (by sorry) } suffix"',
        ):
            with self.subTest(bypass=bypass):
                self.assertIn("LEAN4_SORRY", A.scan_lean4_source(bypass))

        with self.assertRaises(A.AuditError) as cm:
            A.scan_lean4_source("/- unterminated")
        self.assertEqual(cm.exception.code, "LEAN4_UNTERMINATED_COMMENT")
        for unterm in ('def s := "unterminated', 'def s := r#"unterm', 'def s := s!"unterm', 'def s := s!"{1'):
            with self.assertRaises(A.AuditError) as cm:
                A.scan_lean4_source(unterm)
            self.assertEqual(cm.exception.code, "LEAN4_UNTERMINATED_STRING")

    def test_hard_rules_and_decide_native_escapes(self) -> None:
        cases = [
            ("theorem t : True := by sorry", "LEAN4_SORRY"),
            ("theorem t : True := by admit", "LEAN4_ADMIT"),
            ("axiom bad : False", "LEAN4_AXIOM"),
            ("unsafe def f := 1", "LEAN4_UNSAFE"),
            ("theorem t : 1=1 := by native_decide", "LEAN4_NATIVE_DECIDE"),
            ("def x := sorryAx", "LEAN4_SORRY_AX"),
            ("def x := mkSorry", "LEAN4_MK_SORRY"),
            ("def x := ofReduceBool", "LEAN4_OF_REDUCE_BOOL"),
            ("def x := ofReduceNat", "LEAN4_OF_REDUCE_NAT"),
            ("def x := trustCompiler", "LEAN4_TRUST_COMPILER"),
            ("partial\n def loop : Nat := loop", "LEAN4_PARTIAL"),
            ("set_option debug.skipKernelTC true", "LEAN4_SKIP_KERNEL_TC"),
            ('@[extern "c_fn"] def f : Nat := 0', "LEAN4_UNSOUND_ATTR"),
            ("@[implemented_by g] def f : Nat := 0", "LEAN4_UNSOUND_ATTR"),
            ('attribute [extern "c_fn"] f', "LEAN4_UNSOUND_ATTR"),
            ("attribute [implemented_by g] f", "LEAN4_UNSOUND_ATTR"),
            ('#eval IO.println "\'Fake.thm\' does not depend on any axioms"', "LEAN4_META_EXEC"),
            ("#reduce 1 + 1", "LEAN4_META_EXEC"),
            ("#print Nat", "LEAN4_PRINT_NON_AXIOMS"),
            ("#print", "LEAN4_PRINT_NON_AXIOMS"),
            ("public\n import Mathlib.Data.Int.Basic", "LEAN4_EXTERNAL_IMPORT"),
            ("theorem t : 1=1 := by decide +native", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1=1 := by decide (native := true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1=1 := by decide (native :=   )", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1=1 := by decide (native := (true))", "LEAN4_DECIDE_NATIVE"),
            ("def stray ) := 1\ntheorem t : 1=1 := by decide (native := true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1=1 := by decide (native := !false)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1=1 := by decide («native» := true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1=1 := by decide («config» := { «native» := true })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1=1 := by decide (config :=   )", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1=1 := by decide (config := a })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1=1 := by decide (config := { a )", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1=1 := by decide (config := myCfg)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1=1 := by decide (config := { myCfg with native := false })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1=1 := by decide (config := { native := false, a := { b := 1 } })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1=1 := by decide (config := { native := false } } )", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1=1 := by decide (config := { native })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1=1 := by decide (config := { native := false, true })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1=1 := by decide (config := { native := false ; zeta := true })", "LEAN4_DECIDE_NATIVE"),
            ("def c : DecideConfig := { native := true }", "LEAN4_DECIDE_CONFIG_BIND"),
            ("def c := ({ native := true } : Lean.Elab.Tactic.DecideConfig)", "LEAN4_DECIDE_CONFIG_BIND"),
            ("def c := { native := true : DecideConfig }", "LEAN4_DECIDE_CONFIG_BIND"),
        ]
        for snippet, expected_code in cases:
            with self.subTest(expected_code=expected_code, snippet=snippet):
                self.assertIn(expected_code, A.scan_lean4_source(snippet))
        # Direct edge tests on _is_lean4_safe_config_span & _is_lean4_native_rhs_false_span
        self.assertFalse(A._is_lean4_safe_config_span("{ a } b }", 0, 9, {}))
        self.assertFalse(A._is_lean4_safe_config_span("{ a { b }", 0, 9, {}))
        self.assertFalse(A._is_lean4_safe_config_span("{ a", 0, 3, {}))
        self.assertFalse(A._is_lean4_safe_config_span("a }", 0, 3, {}))
        self.assertFalse(A._is_lean4_safe_config_span("   ", 0, 3, {}))
        self.assertFalse(A._is_lean4_native_rhs_false_span("   ", 0, 3))
        self.assertFalse(A._is_lean4_native_rhs_false_span("(a)", 0, 3))
        self.assertFalse(A._is_lean4_native_rhs_false_span("(falsex", 0, 7))
        self.assertFalse(A._is_lean4_native_rhs_false_span("xfalse)", 0, 7))
        self.assertTrue(A._is_lean4_native_rhs_false_span("(false)", 0, 7))
        self.assertFalse(A._is_lean4_native_rhs_false_span("very_long_expression", 0, 20))

    def test_verdict_witness_parser(self) -> None:
        A._parse_verdict_witness_fields("def obs := { a := 10, b := -5 }", {"a": 10, "b": -5})
        A._parse_verdict_witness_fields(
            "def obs0 : Cycle0Obs := { a := 10, b := -5 }", {"a": 10, "b": -5}, obs_name="obs0"
        )
        max64 = "9" * 64
        A._parse_verdict_witness_fields(f"def obs := {{ a := {max64} }}", {"a": int(max64)})
        for too_big in ("9" * 65, "9" * 5001):
            with self.assertRaises(A.AuditError) as cm:
                A._parse_verdict_witness_fields(f"def obs := {{ a := {too_big} }}", {"a": 1})
            self.assertEqual(cm.exception.code, "WITNESS_INT_TOO_LONG")
        with self.assertRaises(A.AuditError) as cm:
            A._parse_verdict_witness_fields("def obs := { a := 11, b := -5 }", {"a": 10, "b": -5})
        self.assertEqual(cm.exception.code, "WITNESS_PARITY_MISMATCH")
        # Decoy overwrite outside def obs0 must NOT mask tampered field inside def obs0
        decoy_src = "def obs0 : Cycle0Obs := { a := 999, b := -5 }\ndef decoy : Int := let a := 10; 0\n"
        with self.assertRaises(A.AuditError) as cm:
            A._parse_verdict_witness_fields(decoy_src, {"a": 10, "b": -5}, obs_name="obs0")
        self.assertEqual(cm.exception.code, "WITNESS_PARITY_MISMATCH")
        # Duplicate field inside record rejected
        with self.assertRaises(A.AuditError) as cm:
            A._parse_verdict_witness_fields(
                "def obs0 : Cycle0Obs := { a := 999, a := 10, b := -5 }",
                {"a": 10, "b": -5},
                obs_name="obs0",
            )
        self.assertEqual(cm.exception.code, "WITNESS_DUPLICATE_FIELD")
        # Missing anchor, non-record def obs0, and duplicate def obs0 rejected
        for bad_anchor in (
            "def other := { a := 10, b := -5 }",
            "def obs0 := 1",
            "def obs0 := 1\ndef obs0 : Cycle0Obs := { a := 10, b := -5 }",
            "def obs0 : Cycle0Obs := { a := 10, b := -5 }\ndef obs0 : Cycle0Obs := { a := 10, b := -5 }",
        ):
            with self.assertRaises(A.AuditError) as cm:
                A._parse_verdict_witness_fields(bad_anchor, {"a": 10, "b": -5}, obs_name="obs0")
            self.assertEqual(cm.exception.code, "WITNESS_ANCHOR_INVALID")


class Test06CertificateAndSecondaryAuditTamper(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cert = json.loads((_TRACK_DIR / "ceer_silicon_certificate.json").read_text(encoding="utf-8"))

    def test_valid_secondary_and_fr0_and_fr1_fast(self) -> None:
        res = A.secondary_audit_payload(self.cert)
        self.assertTrue(res["secondary_audit_ok"])
        self.assertEqual(res["corroborated_clean_by_cycle"], [0, 2, 3])
        self.assertEqual(res["schur_soak_bps"], 2309)
        self.assertEqual(res["schur_spread_bps"], 6202)
        self.assertEqual(A.validate_certificate_payload(self.cert, track_dir=None), res)
        self.assertEqual(A.validate_certificate_payload(self.cert, track_dir=_TRACK_DIR, run_live_lean=False), res)

    def test_secondary_audit_rejects_every_tamper_vector(self) -> None:
        # Direct non-dict, subclass, float injection at entry of secondary_audit_payload
        with self.assertRaises(A.AuditError) as cm:
            A.secondary_audit_payload([1, 2])
        self.assertEqual(cm.exception.code, "ROOT_NOT_OBJECT")
        with self.assertRaises(A.AuditError) as cm:
            A.secondary_audit_payload(_SubDict(self.cert))
        self.assertEqual(cm.exception.code, "FORBIDDEN_TYPE")

        # Missing / extra key
        c = copy.deepcopy(self.cert)
        c["extra"] = 1
        with self.assertRaises(A.AuditError) as cm:
            A.secondary_audit_payload(c)
        self.assertEqual(cm.exception.code, "KEY_SET_MISMATCH")

        # Bad digest format (str and non-str) & tampered digest
        for bad_sha in ("not-a-sha", 123):
            c = copy.deepcopy(self.cert)
            c["certificate_sha256"] = bad_sha
            with self.assertRaises(A.AuditError) as cm:
                A.secondary_audit_payload(c)
            self.assertEqual(cm.exception.code, "BAD_CERT_SHA")
        c = copy.deepcopy(self.cert)
        c["certificate_sha256"] = "0" * 64
        with self.assertRaises(A.AuditError) as cm:
            A.secondary_audit_payload(c)
        self.assertEqual(cm.exception.code, "CERT_SHA_MISMATCH")

        def _expect_resealed(mut_fn, code: str) -> None:
            cand = copy.deepcopy(self.cert)
            mut_fn(cand)
            cand = _reseal(cand)
            with self.assertRaises(A.AuditError) as cm:
                A.secondary_audit_payload(cand)
            self.assertEqual(cm.exception.code, code)

        _expect_resealed(lambda o: o.update({"schema_version": "bad"}), "SCHEMA_MISMATCH")
        _expect_resealed(lambda o: o.update({"track_id": "bad"}), "TRACK_ID_MISMATCH")
        _expect_resealed(lambda o: o.update({"toolchain": "leanprover/lean4:v4.0.0"}), "TOOLCHAIN_MISMATCH")
        _expect_resealed(lambda o: o.update({"artifact_sha256": {}}), "ARTIFACT_MAP_MISMATCH")
        _expect_resealed(lambda o: o["artifact_sha256"].update({"lean-toolchain": "bad"}), "BAD_ARTIFACT_SHA")
        _expect_resealed(lambda o: o["artifact_sha256"].update({"lean-toolchain": 123}), "BAD_ARTIFACT_SHA")

        # MLOS receipt list (wrong len AND len-3 non-list str) & entry checks
        _expect_resealed(lambda o: o.update({"mlos_receipts": []}), "BAD_MLOS_LIST")
        _expect_resealed(lambda o: o.update({"mlos_receipts": "abc"}), "BAD_MLOS_LIST")
        _expect_resealed(lambda o: o["mlos_receipts"].__setitem__(0, "bad"), "MLOS_RECEIPT_INVALID")
        for field, bad_val in (
            ("file", "wrong.json"),
            ("file_sha256", "0" * 64),
            ("receipt_sha256", "not-hex"),
            ("receipt_sha256", 123),
            ("clean_hardware_run", False),
            ("determinism_zone", "A"),
            ("profile_id", "wrong"),
            ("exit_code", 1),
            ("exit_code", False),
            ("anomalies_count", 1),
            ("anomalies_count", False),
        ):
            _expect_resealed(lambda o, f=field, v=bad_val: o["mlos_receipts"][0].update({f: v}), "MLOS_RECEIPT_INVALID")

        # Lean4 verification block & modules checks (including non-list int/str)
        _expect_resealed(lambda o: o.update({"lean4_verification": []}), "LEAN4_BLOCK_INVALID")
        for field, bad_val in (
            ("pure_init_zero_mathlib", False),
            ("static_findings", 1),
            ("static_findings", False),
            ("witness_telemetry_parity", False),
            ("axioms_subset_standard", False),
            ("total_modules", 5),
            ("total_theorems", 35),
            ("modules", []),
            ("modules", "123456"),
            ("modules", 123),
        ):
            _expect_resealed(lambda o, f=field, v=bad_val: o["lean4_verification"].update({f: v}), "LEAN4_BLOCK_INVALID")
        for m_field, m_val in (
            ("module", "Wrong.lean"),
            ("theorem_count", 99),
            ("warnings", 1),
            ("warnings", False),
            ("theorems", []),
            ("theorems", "1234567"),
            ("theorems", {}),
        ):
            _expect_resealed(lambda o, f=m_field, v=m_val: o["lean4_verification"]["modules"][0].update({f: v}), "LEAN4_BLOCK_INVALID")
        _expect_resealed(
            lambda o: o["lean4_verification"]["modules"][0]["theorems"].update(
                {next(iter(o["lean4_verification"]["modules"][0]["theorems"])): ["Lean.ofReduceBool"]}
            ),
            "LEAN4_BLOCK_INVALID",
        )
        _expect_resealed(
            lambda o: o["lean4_verification"]["modules"][0]["theorems"].update(
                {next(iter(o["lean4_verification"]["modules"][0]["theorems"])): [123]}
            ),
            "LEAN4_BLOCK_INVALID",
        )
        _expect_resealed(
            lambda o: o["lean4_verification"]["modules"][0]["theorems"].update(
                {next(iter(o["lean4_verification"]["modules"][0]["theorems"])): "not-a-list"}
            ),
            "LEAN4_BLOCK_INVALID",
        )
        _expect_resealed(
            lambda o: o["lean4_verification"]["modules"][0]["theorems"].update(
                {next(iter(o["lean4_verification"]["modules"][0]["theorems"])): ""}
            ),
            "LEAN4_BLOCK_INVALID",
        )
        _expect_resealed(
            lambda o: o["lean4_verification"]["modules"][0]["theorems"].update(
                {next(iter(o["lean4_verification"]["modules"][0]["theorems"])): 123}
            ),
            "LEAN4_BLOCK_INVALID",
        )
        # Forged theorem names, duplicate axioms, unsorted axioms, and non-empty axioms on zero-axiom theorem
        # MUST fail across direct SEC, FR0 (track_dir=None), AND FR1 (run_live_lean=False)
        forged = copy.deepcopy(self.cert)
        for mod in forged["lean4_verification"]["modules"]:
            mod["theorems"] = {f"FAKE_{i}": ["propext", "propext"] for i in range(mod["theorem_count"])}
        forged = _reseal(forged)
        for fn in (
            lambda: A.secondary_audit_payload(forged),
            lambda: A.validate_certificate_payload(forged, track_dir=None),
            lambda: A.validate_certificate_payload(forged, track_dir=_TRACK_DIR, run_live_lean=False),
        ):
            with self.assertRaises(A.AuditError) as cm:
                fn()
            self.assertEqual(cm.exception.code, "LEAN4_BLOCK_INVALID")
        _expect_resealed(
            lambda o: o["lean4_verification"]["modules"][0]["theorems"].update(
                {"CEERSiliconCerts.Cycle0Theory.falsify_H0a": ["propext", "propext"]}
            ),
            "LEAN4_BLOCK_INVALID",
        )
        _expect_resealed(
            lambda o: o["lean4_verification"]["modules"][0]["theorems"].update(
                {"CEERSiliconCerts.Cycle0Theory.falsify_H0a": ["propext", "Quot.sound"]}
            ),
            "LEAN4_BLOCK_INVALID",
        )
        _expect_resealed(
            lambda o: o["lean4_verification"]["modules"][0]["theorems"].update(
                {"CEERSiliconCerts.Cycle0Theory.falsify_H0d_area": ["propext"]}
            ),
            "LEAN4_BLOCK_INVALID",
        )

        # CEER summary, disjoint levers, & chain binding
        _expect_resealed(lambda o: o.update({"ceer_summary": []}), "BAD_CEER_SUMMARY")
        _expect_resealed(lambda o: o["ceer_summary"].update({"disjoint_held_out_levers": []}), "LEVERS_NOT_DISJOINT")
        for field, bad_val in (
            ("pairwise_disjoint_cores", False),
            ("pairwise_disjoint_pairs", False),
            ("pairwise_disjoint_bytes", False),
            ("pairwise_distinct_ramps", False),
            ("total_distinct_core_counts", 7),
            ("total_distinct_spatial_pairs", 5),
            ("total_distinct_memory_footprints", 8),
        ):
            _expect_resealed(lambda o, f=field, v=bad_val: o["ceer_summary"]["disjoint_held_out_levers"].update({f: v}), "LEVERS_NOT_DISJOINT")
        _expect_resealed(
            lambda o: o["ceer_summary"]["cryptographic_chain"].update({"cycle_0_prereg_sha256": "0" * 64}),
            "CHAIN_BINDING_MISMATCH",
        )
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_0"]["obs"].update({"pkgMwP1": "bad"}), "C0_MATH_MISMATCH")
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_0"]["obs"].update({"pkgMwP2": 0}), "C0_MATH_MISMATCH")
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_0"]["verdicts"].update({"H0b": True}), "C0_MATH_MISMATCH")

        # Cycle 0 math clauses
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_0"]["obs"].update({"ops64m": 10**12}), "C0_MATH_MISMATCH")
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_0"]["obs"].update({"adjInactRiseMc": 985}), "C0_MATH_MISMATCH")
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_0"]["obs"].update({"tempDownMeanMc": 86000}), "C0_MATH_MISMATCH")
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_0"]["obs"].update({"pkgDarkMw16k": 4000}), "C0_MATH_MISMATCH")
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_0"]["obs"].update({"pkgDarkMw64m": 4000}), "C0_MATH_MISMATCH")

        # Cycle 1 math clauses
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_1"]["obs"].update({"opsP6": 1}), "C1_MATH_MISMATCH")
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_1"]["obs"].update({"ops32m": 1}), "C1_MATH_MISMATCH")
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_1"]["obs"].update({"contrast23Mc": -5000}), "C1_MATH_MISMATCH")
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_1"]["obs"].update({"tempDownMeanMc": 99000}), "C1_MATH_MISMATCH")
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_1"]["verdicts"].update({"H1a": False}), "C1_MATH_MISMATCH")

        # Cycle 2 Schur recomputation checks
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_2"]["schur_soak"].update({"variance_reduction_bps": 1}), "C2_SCHUR_MISMATCH")
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_2"]["schur_spread"].update({"variance_reduction_bps": 1}), "C2_SCHUR_MISMATCH")
        # Mock nonzero identity_residual to kill identity_residual != 0 mutants
        with mock.patch.object(A, "exact_schur_3x3", return_value={**self.cert["ceer_summary"]["cycle_2"]["schur_soak"], "identity_residual": 1}):
            with self.assertRaises(A.AuditError) as cm:
                A.secondary_audit_payload(self.cert)
            self.assertEqual(cm.exception.code, "C2_SCHUR_MISMATCH")
        orig_schur = A.exact_schur_3x3
        call_idx = {"i": 0}

        def _fail_second_schur(*args):
            call_idx["i"] += 1
            res = orig_schur(*args)
            if call_idx["i"] == 2:
                res = dict(res)
                res["identity_residual"] = 1
            return res

        with mock.patch.object(A, "exact_schur_3x3", side_effect=_fail_second_schur):
            with self.assertRaises(A.AuditError) as cm:
                A.secondary_audit_payload(self.cert)
            self.assertEqual(cm.exception.code, "C2_SCHUR_MISMATCH")

        # Cycle 2 math clauses (all 8 clauses)
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_2"]["obs"].update({"opsP7": 1}), "C2_MATH_MISMATCH")
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_2"]["obs"].update({"ops48m": 10**12}), "C2_MATH_MISMATCH")
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_2"]["obs"].update({"ops12m": 10**12}), "C2_MATH_MISMATCH")
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_2"]["obs"].update({"contrast45Mc": 0}), "C2_MATH_MISMATCH")
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_2"]["obs"].update({"contrast16Mc": 0}), "C2_MATH_MISMATCH")
        _expect_resealed(lambda o: o["ceer_summary"]["cycle_2"]["obs"].update({"contrast45Mc": 100, "contrast16Mc": -100}), "C2_MATH_MISMATCH")

        def _weak_soak(o: dict) -> None:
            o["ceer_summary"]["cycle_2"]["obs"]["syvSoak"] = 0
            o["ceer_summary"]["cycle_2"]["obs"]["suvSoak"] = 0
            ob = o["ceer_summary"]["cycle_2"]["obs"]
            o["ceer_summary"]["cycle_2"]["schur_soak"] = O.exact_schur_3x3(
                ob["syy"], ob["suu"], ob["svvSoak"], ob["syu"], ob["syvSoak"], ob["suvSoak"]
            )

        def _weak_spread(o: dict) -> None:
            o["ceer_summary"]["cycle_2"]["obs"]["syvSpread"] = 0
            o["ceer_summary"]["cycle_2"]["obs"]["suvSpread"] = 0
            ob = o["ceer_summary"]["cycle_2"]["obs"]
            o["ceer_summary"]["cycle_2"]["schur_spread"] = O.exact_schur_3x3(
                ob["syy"], ob["suu"], ob["svvSpread"], ob["syu"], ob["syvSpread"], ob["suvSpread"]
            )

        _expect_resealed(_weak_soak, "C2_MATH_MISMATCH")
        _expect_resealed(_weak_spread, "C2_MATH_MISMATCH")

        # Epistemic trajectory checks
        _expect_resealed(lambda o: o["ceer_summary"].update({"epistemic_trajectory": []}), "TRAJECTORY_MISMATCH")
        _expect_resealed(lambda o: o["ceer_summary"]["epistemic_trajectory"].update({"corroborated_clean_by_cycle": [0, 1, 3]}), "TRAJECTORY_MISMATCH")
        _expect_resealed(lambda o: o["ceer_summary"]["epistemic_trajectory"].update({"strictly_monotone": False}), "TRAJECTORY_MISMATCH")

    def test_validate_recompute_mismatch_paths(self) -> None:
        for bad_bool in (0, 1, "true", None):
            with self.assertRaises(A.AuditError) as cm:
                A.validate_certificate_payload(self.cert, track_dir=None, run_live_lean=bad_bool)  # type: ignore[arg-type]
            self.assertEqual(cm.exception.code, "BAD_BOOL")
            with self.assertRaises(A.AuditError) as cm:
                A.build_certificate(_TRACK_DIR, run_live_lean=bad_bool)  # type: ignore[arg-type]
            self.assertEqual(cm.exception.code, "BAD_BOOL")
        fake_fresh = copy.deepcopy(self.cert)
        fake_fresh["artifact_sha256"]["lean-toolchain"] = "f" * 64
        with mock.patch.object(A, "build_certificate", return_value=fake_fresh):
            with self.assertRaises(A.AuditError) as cm:
                A.validate_certificate_payload(self.cert, track_dir=_TRACK_DIR, run_live_lean=False)
            self.assertEqual(cm.exception.code, "FRESH_RECOMPUTE_MISMATCH")
            with self.assertRaises(A.AuditError) as cm:
                A.validate_certificate_payload(self.cert, track_dir=_TRACK_DIR, run_live_lean=True)
            self.assertEqual(cm.exception.code, "FRESH_CERT_MISMATCH")


class Test07MockedLiveLeanMlosAndCLI(unittest.TestCase):
    def test_resolve_lean_and_verify_module_live_mocked(self) -> None:
        with mock.patch.object(shutil, "which", return_value="/usr/bin/lean"):
            self.assertEqual(A._resolve_lean_bin(), "/usr/bin/lean")
        with mock.patch.object(shutil, "which", return_value=None), mock.patch.object(Path, "is_file", return_value=True):
            self.assertTrue(A._resolve_lean_bin().endswith("/.local/bin/lean"))
        with mock.patch.object(shutil, "which", return_value=None), mock.patch.object(Path, "is_file", return_value=False):
            with self.assertRaises(A.AuditError) as cm:
                A._resolve_lean_bin()
            self.assertEqual(cm.exception.code, "LEAN_NOT_FOUND")

        good_out = (
            "'M.t1' depends on axioms: [propext,\n Quot.sound]\n"
            "'M.t2' does not depend on any axioms\n"
        )
        p = Path("Fake.lean")
        with mock.patch.object(A, "_resolve_lean_bin", return_value="lean"):
            with mock.patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0, good_out, "")):
                r = A.verify_lean4_module_live(p, 2)
                self.assertEqual(r["theorem_count"], 2)
                self.assertEqual(r["theorems"]["M.t1"], ["Quot.sound", "propext"])
                self.assertEqual(r["theorems"]["M.t2"], [])
            with mock.patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired(["lean"], 60)):
                with self.assertRaises(A.AuditError) as cm:
                    A.verify_lean4_module_live(p, 2)
                self.assertEqual(cm.exception.code, "LEAN4_EXEC_ERROR")
            with mock.patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "")):
                with self.assertRaises(A.AuditError) as cm:
                    A.verify_lean4_module_live(p, 2)
                self.assertEqual(cm.exception.code, "LEAN4_VERIFY_FAILED")
            with mock.patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0, good_out, "warning")):
                with self.assertRaises(A.AuditError) as cm:
                    A.verify_lean4_module_live(p, 2)
                self.assertEqual(cm.exception.code, "LEAN4_VERIFY_FAILED")
            for bad_out, exp_code in (
                ("Fake.lean:1:1: warning: unused variable\n" + good_out, "LEAN4_UNEXPECTED_OUTPUT"),
                (good_out + "Fake.lean:9:1: warning: trailing\n", "LEAN4_UNEXPECTED_OUTPUT"),
                ("'M.t1' depends on axioms: [propext, propext]\n", "LEAN4_DUPLICATE_AXIOM"),
                ("'M.t1' does not depend on any axioms\n'M.t1' does not depend on any axioms\n", "LEAN4_DUPLICATE_THEOREM"),
                ("'M.t1' depends on axioms: [Lean.ofReduceBool]\n", "LEAN4_NONSTANDARD_AXIOM"),
            ):
                with mock.patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0, bad_out, "")):
                    with self.assertRaises(A.AuditError) as cm:
                        A.verify_lean4_module_live(p, 1)
                    self.assertEqual(cm.exception.code, exp_code)
            with mock.patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0, good_out, "")):
                with self.assertRaises(A.AuditError) as cm:
                    A.verify_lean4_module_live(p, 3)
                self.assertEqual(cm.exception.code, "LEAN4_THEOREM_COUNT_MISMATCH")
            fake7 = "".join(f"'FAKE_{i}' does not depend on any axioms\n" for i in range(7))
            with mock.patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0, fake7, "")):
                with self.assertRaises(A.AuditError) as cm:
                    A.verify_lean4_module_live(Path("CEER_Cycle0_Theory.lean"), 7)
                self.assertEqual(cm.exception.code, "LEAN4_THEOREM_NAME_MISMATCH")

    def test_mlos_receipt_and_build_certificate_error_paths(self) -> None:
        base = json.loads((_TRACK_DIR / "mlos_cycle0_receipt.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix="ceer_mlos_") as td:
            p = Path(td) / "mlos_cycle0_receipt.json"
            p.write_text(json.dumps(base), encoding="utf-8")
            self.assertTrue(A._check_mlos_receipt(p)["clean_hardware_run"])

            leak_str = "/" + "home/leak"
            cases = [
                (lambda o: o.update({"note": leak_str}), "HOME_PATH_LEAK"),
                (lambda o: o.update({"schema": "bad"}), "MLOS_SCHEMA_BAD"),
                (lambda o: o.update({"clean_hardware_run": False}), "MLOS_NOT_CLEAN"),
                (lambda o: o.update({"determinism_zone": "A"}), "MLOS_BAD_ZONE"),
                (lambda o: o.update({"anomalies": ["drift"]}), "MLOS_ANOMALIES"),
                (lambda o: o.update({"profile_id": "other"}), "MLOS_BAD_PROFILE"),
                (lambda o: o.update({"execution": "bad"}), "MLOS_NONZERO_EXIT"),
                (lambda o: o["execution"].update({"exit_code": 1}), "MLOS_NONZERO_EXIT"),
                (lambda o: o["execution"].update({"exit_code": False}), "MLOS_NONZERO_EXIT"),
                (lambda o: o.update({"receipt_sha256": "xyz"}), "MLOS_BAD_SHA"),
                (lambda o: o.update({"receipt_sha256": 123}), "MLOS_BAD_SHA"),
            ]
            for mut, code in cases:
                cand = copy.deepcopy(base)
                mut(cand)
                p.write_text(json.dumps(cand), encoding="utf-8")
                with self.assertRaises(A.AuditError) as cm:
                    A._check_mlos_receipt(p)
                self.assertEqual(cm.exception.code, code)
            p.write_bytes(b"\xff\xfe")
            with self.assertRaises(A.AuditError) as cm:
                A._check_mlos_receipt(p)
            self.assertEqual(cm.exception.code, "INVALID_UTF8")
            p.write_text("{bad", encoding="utf-8")
            with self.assertRaises(A.AuditError) as cm:
                A._check_mlos_receipt(p)
            self.assertEqual(cm.exception.code, "INVALID_JSON")
            p.write_text('{"schema":"mlos-run-receipt/v0.1","x":NaN}', encoding="utf-8")
            with self.assertRaises(A.AuditError) as cm:
                A._check_mlos_receipt(p)
            self.assertEqual(cm.exception.code, "NON_FINITE_JSON")
            p.write_text('{"anomalies":["bad"],"anomalies":[]}', encoding="utf-8")
            with self.assertRaises(A.AuditError) as cm:
                A._check_mlos_receipt(p)
            self.assertEqual(cm.exception.code, "DUPLICATE_KEY")
            p.write_text("[1,2]", encoding="utf-8")
            with self.assertRaises(A.AuditError) as cm:
                A._check_mlos_receipt(p)
            self.assertEqual(cm.exception.code, "MLOS_SCHEMA_BAD")

        # build_certificate bad toolchain, bad UTF-8 toolchain, symlink-before-oracle,
        # non-UTF-8 prereg, & static lean finding
        with tempfile.TemporaryDirectory(prefix="ceer_bld_") as td:
            root = Path(td)
            (root / "lean-toolchain").write_bytes(b"\xff\xfe")
            with self.assertRaises(A.AuditError) as cm:
                A.build_certificate(root, run_live_lean=False)
            self.assertEqual(cm.exception.code, "INVALID_UTF8")
            (root / "lean-toolchain").write_text("leanprover/lean4:v4.0.0\n", encoding="utf-8")
            with self.assertRaises(A.AuditError) as cm:
                A.build_certificate(root, run_live_lean=False)
            self.assertEqual(cm.exception.code, "TOOLCHAIN_MISMATCH")

            # Copy all 19 artifacts then symlink cycle_0_prereg.json to malformed JSON:
            # MUST raise SYMLINK_REJECTED before compute_ceer_summary ever parses it!
            shutil.copytree(_TRACK_DIR / "CEERSiliconCerts", root / "CEERSiliconCerts")
            for rel in A.ARTIFACT_FILES:
                if "/" not in rel:
                    shutil.copy2(_TRACK_DIR / rel, root / rel)
            ext_bad = root / "ext_bad.json"
            ext_bad.write_text("{bad json", encoding="utf-8")
            (root / "cycle_0_prereg.json").unlink()
            (root / "cycle_0_prereg.json").symlink_to(ext_bad)
            with self.assertRaises(A.AuditError) as cm:
                A.build_certificate(root, run_live_lean=False)
            self.assertEqual(cm.exception.code, "SYMLINK_REJECTED")
            (root / "cycle_0_prereg.json").unlink()
            (root / "cycle_0_prereg.json").write_bytes(b"\xff\xfe")
            with self.assertRaises(O.OracleError) as cm:
                A.build_certificate(root, run_live_lean=False)
            self.assertEqual(cm.exception.code, "INVALID_UTF8")

        with mock.patch.object(A, "scan_lean4_source", return_value=["LEAN4_SORRY"]):
            with self.assertRaises(A.AuditError) as cm:
                A.build_certificate(_TRACK_DIR, run_live_lean=False)
            self.assertEqual(cm.exception.code, "LEAN4_STATIC_FINDING")

    def test_cli_main_mocked_and_error_modes(self) -> None:
        cert = json.loads((_TRACK_DIR / "ceer_silicon_certificate.json").read_text(encoding="utf-8"))
        with mock.patch.object(A, "build_certificate", return_value=cert):
            for ok_args in ([], ["--standalone", "--json"]):
                out = io.StringIO()
                with mock.patch.object(sys, "stdout", out):
                    self.assertEqual(A.main(ok_args), 0)
                self.assertEqual(json.loads(out.getvalue())["certificate_sha256"], cert["certificate_sha256"])

            with tempfile.TemporaryDirectory(prefix="ceer_cli_") as td:
                dest = Path(td) / "out.json"
                out_w = io.StringIO()
                with mock.patch.object(sys, "stdout", out_w):
                    self.assertEqual(A.main(["--write", str(dest)]), 0)
                self.assertEqual(stat.S_IMODE(dest.stat().st_mode), 0o600)
                out_c = io.StringIO()
                with mock.patch.object(sys, "stdout", out_c):
                    self.assertEqual(A.main(["--check", str(dest)]), 0)
                self.assertTrue(json.loads(out_c.getvalue())["secondary_audit_ok"])
                # Reject non---check flag with valid cert file, and extra arg after --check
                for bad_with_dest in (["--bad", str(dest)], ["--check", str(dest), "extra"], ["--check"]):
                    err_d = io.StringIO()
                    with mock.patch.object(sys, "stderr", err_d):
                        self.assertEqual(A.main(bad_with_dest), 2)
                    self.assertIn("BAD_CLI_ARGS", err_d.getvalue())

        for bad_args in (
            123,
            ["--check", 123],
            ["--check", "/tmp/\ud800.json"],
            ["--write", "\ud800.json"],
            ["--bad"],
            ["--bad", "x"],
            ["--standalone"],
            ["--write"],
            ["--write", "--check"],
            ["--check", "-x"],
        ):
            err = io.StringIO()
            with mock.patch.object(sys, "stderr", err):
                self.assertEqual(A.main(bad_args), 2)  # type: ignore[arg-type]
            self.assertIn("AUDIT_FAIL", err.getvalue())


class Test08EndToEndLiveLean4(unittest.TestCase):
    def test_live_lean4_build_and_check_certificate(self) -> None:
        cert = A.build_certificate(_TRACK_DIR, run_live_lean=True)
        self.assertEqual(cert["lean4_verification"]["total_modules"], 6)
        self.assertEqual(cert["lean4_verification"]["total_theorems"], 36)
        self.assertEqual(cert["lean4_verification"]["static_findings"], 0)
        self.assertTrue(cert["lean4_verification"]["witness_telemetry_parity"])
        disk_cert = json.loads((_TRACK_DIR / "ceer_silicon_certificate.json").read_text(encoding="utf-8"))
        self.assertEqual(cert, disk_cert)
        res = A.validate_certificate_payload(disk_cert, track_dir=_TRACK_DIR, run_live_lean=True)
        self.assertTrue(res["secondary_audit_ok"])

        # Live Lean 4.36.0 compiler warning on stdout MUST fail closed
        with tempfile.TemporaryDirectory(prefix="ceer_warn_") as td:
            warn_lean = Path(td) / "warn_repro.lean"
            warn_lean.write_text(
                "theorem w (unused_x : Nat) : 1 + 1 = 2 := rfl\n#print axioms w\n",
                encoding="utf-8",
            )
            with self.assertRaises(A.AuditError) as cm:
                A.verify_lean4_module_live(warn_lean, 1)
            self.assertEqual(cm.exception.code, "LEAN4_UNEXPECTED_OUTPUT")


if __name__ == "__main__":
    unittest.main()
