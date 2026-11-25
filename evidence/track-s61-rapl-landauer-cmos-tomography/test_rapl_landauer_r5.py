#!/usr/bin/env python3
"""Adversarial R5 Test Suite for Track S61 (intel-rapl Landauer-CMOS Tomography).

100% pure Python 3 stdlib, zero bare asserts, zero AST floats, zero .isdigit(),
zero device-path writes (scratch os.mkfifo only), Linux-guarded renameat2, Darwin alias tests.
"""
from __future__ import annotations

import ast
from contextlib import redirect_stderr, redirect_stdout
import copy
import ctypes
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
from types import SimpleNamespace
from typing import Any
import unittest
from unittest import mock

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import rapl_landauer_audit as aud  # noqa: E402
import rapl_landauer_oracle as orc  # noqa: E402


class _EvilInt(int):
    pass


class _EvilStr(str):
    pass


class _EvilDict(dict):
    pass


class _EvilList(list):
    pass


class _EvilPath(type(Path())):
    pass


def _make_mini_snapshot(n_per_regime: int = 3) -> dict[str, Any]:
    """Deterministic 21-row synthetic pure-integer snapshot for rapid unit & mutation tests."""
    channels = []
    rapl_names = list(orc.EXPECTED_RAPL_CHANNELS)
    for i in range(5):
        channels.append({"idx": i, "name": rapl_names[i], "unit": "uJ_per_tick", "modality": "intel_rapl_energy", "max_energy_range_uj": 262143328850})
    for i in range(9):
        channels.append({"idx": 5 + i, "name": f"temp_{i}", "unit": "mC", "modality": "cpu_die_thermal", "max_energy_range_uj": 0})
    for i in range(4):
        channels.append({"idx": 14 + i, "name": f"freq_{i}", "unit": "kHz", "modality": "cpu_clock_freq", "max_energy_range_uj": 0})
    for i in range(2):
        channels.append({"idx": 18 + i, "name": f"fan_{i}", "unit": "RPM", "modality": "chassis_cooling_fan", "max_energy_range_uj": 0})

    regimes = []
    regime_labels: list[int] = []
    t_rel_us: list[int] = []
    dt_us: list[int] = []
    x_rows: list[list[int]] = []
    t_acc = 0
    for r_idx, rid in enumerate(orc.EXPECTED_REGIME_IDS):
        ops = 0 if r_idx == 0 else (1_000_000_000 * (r_idx + 1))
        erased = 2_000_000_000 if r_idx == 2 else 0
        toggles = 3_000_000_000 if r_idx in (1, 2) else (127_000_000_000 if r_idx == 3 else 0)
        regimes.append({
            "idx": r_idx,
            "id": rid,
            "category": f"cat_{r_idx}",
            "n_samples": n_per_regime,
            "wall_ns": 1_000_000_000,
            "total_ops": ops,
            "total_erased_bits": erased,
            "total_toggle_bits": toggles,
            "sink_xor_hex": "0000000000000001",
        })
        for s in range(n_per_regime):
            dt = 50_000
            t_acc += dt
            regime_labels.append(r_idx)
            t_rel_us.append(t_acc)
            dt_us.append(dt)
            core_e = 2_500_000 + r_idx * 250_000 + s * 20_000
            unc_e = 40_000 + (80_000 if r_idx == 6 else r_idx * 5_000) + s * 1_000
            dark_e = 180_000 + (60_000 if r_idx == 6 else r_idx * 2_000)
            pkg_e = core_e + unc_e + dark_e
            psys_e = pkg_e // 15 + s * 500
            mmio_e = pkg_e
            row_id = r_idx * n_per_regime + s
            temps = [80_000 + r_idx * 1_200 + s * 200 + k * 300 + ((row_id + 1) ** (k % 3 + 1) * (k + 3) * 17) % 997 for k in range(9)]
            freqs = [3_400_000 - (300_000 if r_idx == 4 else r_idx * 10_000) + s * 5_000 + k * 1_000 + ((row_id + 2) * (k * 13 + 7) * 53) % 4093 for k in range(4)]
            fans = [3300, 3200 + r_idx * 20 + s * 5 + ((row_id * 29 + 11) % 37)]
            x_rows.append([pkg_e, core_e, unc_e, psys_e, mmio_e] + temps + freqs + fans)

    return {
        "schema_version": "aletheia.track_s61.rapl_landauer_snapshot.v1",
        "capture_utc_start": "2026-11-24T14:26:00Z",
        "capture_utc_end": "2026-11-24T14:26:42Z",
        "privacy_locks": {
            "audio_capture_accessed": False,
            "camera_accessed": False,
            "display_modified": False,
        },
        "host_spec": {
            "os": "linux",
            "machine": "x86_64",
            "cpu_model": "test-cpu",
            "l1d_kib_per_core": 48,
            "l2_kib_per_core": 1280,
            "l3_mib_shared": 24,
        },
        "gpu_quiescence_gate": {
            "pre_capture": {"gpu_util_pct": 0, "mem_util_pct": 100, "mem_used_mib": 2, "gpu_temp_c": 55},
            "post_capture": {"gpu_util_pct": 0, "mem_util_pct": 100, "mem_used_mib": 2, "gpu_temp_c": 55},
            "max_allowed_gpu_util_pct": 5,
            "gpu_idle_verified": True,
        },
        "microkernels_c_sha256": "a" * 64,
        "harness_version": "rapl_landauer_microkernels/v1",
        "num_workers": 4,
        "worker_cpus": [0, 1, 2, 3],
        "sampler_cpu": 7,
        "tick_ms": 50,
        "settle_ms": 500,
        "samples_per_regime": n_per_regime,
        "dram_bytes_per_worker": 67108864,
        "dram_total_bytes": 268435456,
        "step_algebra_self_checked": True,
        "channels": channels,
        "regimes": regimes,
        "regime_labels": regime_labels,
        "t_rel_us": t_rel_us,
        "dt_us": dt_us,
        "X_anonymous": x_rows,
    }


def _resign_cert(cert: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(cert)
    p_sha = orc.sha256_hex(orc.canonical_json_bytes(out["payload"]))
    out["payload_sha256"] = p_sha
    env_body = {
        "schema_version": out["schema_version"],
        "track_id": out["track_id"],
        "payload_sha256": p_sha,
        "payload": out["payload"],
    }
    out["certificate_sha256"] = orc.sha256_hex(orc.canonical_json_bytes(env_body))
    return out


class TestStaticHygieneAndOraclePrimitives(unittest.TestCase):
    def test_zero_asserts_floats_isdigit_random_devnull_and_leaks(self) -> None:
        for fname in ("rapl_landauer_oracle.py", "rapl_landauer_audit.py", "test_rapl_landauer_r5.py"):
            src = (_HERE / fname).read_text(encoding="utf-8")
            self.assertNotIn("\r", src)
            self.assertNotIn("/dev/" + "null", src)
            tree = ast.parse(src, filename=fname)
            for node in ast.walk(tree):
                self.assertNotIsInstance(node, ast.Assert, f"bare assert in {fname}")
                if isinstance(node, ast.Constant):
                    self.assertNotIsInstance(node.value, float, f"AST float in {fname}")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotEqual(node.func.id, "float", f"float() call in {fname}")
                if isinstance(node, ast.Attribute):
                    self.assertNotEqual(node.attr, "isdigit", f".isdigit() in {fname}")
                    self.assertNotIn(node.attr, ("islink", "is_symlink"), f"islink in {fname}")
                if isinstance(node, ast.Import):
                    for al in node.names:
                        self.assertNotEqual(al.name, "random", f"random import in {fname}")
                if isinstance(node, ast.ImportFrom):
                    self.assertNotEqual(node.module, "random", f"from random import in {fname}")

    def test_oracle_primitives_algebra_schur_inertia_and_ari(self) -> None:
        # require_ok / require_bool / require_exact_int / require_str / is_valid_hex64 / formatters
        with self.assertRaises(orc.RaplLandauerError) as cm:
            orc.require_ok(1, "C", "m")
        self.assertEqual(cm.exception.code, "INVALID_CONDITION")
        with self.assertRaises(orc.RaplLandauerError) as cm:
            orc.require_ok(False, "FAIL_CODE", "m")
        self.assertEqual(cm.exception.code, "FAIL_CODE")
        self.assertTrue(orc.require_bool(True))
        with self.assertRaises(orc.RaplLandauerError) as cm:
            orc.require_bool(1)
        self.assertEqual(cm.exception.code, "INVALID_BOOL")

        max_i = (1 << orc.MAX_INT_BITS) - 1
        over_i = 1 << orc.MAX_INT_BITS
        self.assertEqual(orc.require_exact_int(max_i, lo=-max_i, hi=max_i), max_i)
        for bad_val, kw, code in (
            (True, {}, "INVALID_INT"),
            (_EvilInt(1), {}, "INVALID_INT"),
            (over_i, {}, "INT_BIT_LIMIT"),
            (5, {"lo": True}, "INVALID_BOUND"),
            (5, {"lo": 6}, "INT_OUT_OF_RANGE"),
            (5, {"hi": False}, "INVALID_BOUND"),
            (5, {"hi": 4}, "INT_OUT_OF_RANGE"),
        ):
            with self.assertRaises(orc.RaplLandauerError) as cm:
                orc.require_exact_int(bad_val, **kw)
            self.assertEqual(cm.exception.code, code)

        self.assertEqual(orc.require_str("ok", non_empty=True), "ok")
        self.assertEqual(len(orc.require_str("x" * orc.MAX_STR_LEN)), orc.MAX_STR_LEN)
        for bad_s, code in (
            (123, "INVALID_STR"),
            (_EvilStr("x"), "INVALID_STR"),
            ("bad\ud800", "INVALID_UTF8_SURROGATE"),
            ("a\x00b", "NUL_BYTE_FORBIDDEN"),
            ("x" * (orc.MAX_STR_LEN + 1), "STR_TOO_LONG"),
            ("   ", "EMPTY_STR"),
        ):
            with self.assertRaises(orc.RaplLandauerError) as cm:
                orc.require_str(bad_s, non_empty=True)
            self.assertEqual(cm.exception.code, code)

        self.assertTrue(orc.is_valid_hex64("0123456789abcdef" * 4))
        self.assertFalse(orc.is_valid_hex64(123))
        self.assertFalse(orc.is_valid_hex64("a" * 63))
        self.assertFalse(orc.is_valid_hex64("A" * 64))
        self.assertFalse(orc.is_valid_hex64("z" * 64))
        with self.assertRaises(orc.RaplLandauerError) as cm:
            orc.require_hex64("bad")
        self.assertEqual(cm.exception.code, "INVALID_HEX64")

        self.assertEqual(orc.format_rational(Fraction(4, 2)), "2")
        self.assertEqual(orc.format_rational(Fraction(3, 2)), "3/2")
        with self.assertRaises(orc.RaplLandauerError) as cm:
            orc.format_rational(1)  # type: ignore[arg-type]
        self.assertEqual(cm.exception.code, "INVALID_RATIONAL")
        with self.assertRaises(orc.RaplLandauerError) as cm:
            orc.q_quantize_floor(1)  # type: ignore[arg-type]
        self.assertEqual(cm.exception.code, "INVALID_RATIONAL")
        with self.assertRaises(orc.RaplLandauerError) as cm:
            orc.format_decimal(1)  # type: ignore[arg-type]
        self.assertEqual(cm.exception.code, "INVALID_RATIONAL")
        self.assertEqual(orc.format_decimal(Fraction(-1, 10**9), 4), "0.0000")
        self.assertEqual(orc.format_decimal(Fraction(-5, 2), 0), "-3")
        self.assertEqual(orc.format_decimal(Fraction(1, 2), 0), "1")
        self.assertEqual(orc.format_decimal(Fraction(1, 4), 2), "0.25")
        self.assertEqual(orc.format_decimal(Fraction(-3, 8), 2), "-0.38")

        # Pillar 1 algebra proof + mocked failure guards (kills all R1/R2/R3 algebra BoolOps)
        p1 = orc.prove_step_algebra()
        self.assertTrue(p1["r1_bijection_verified"])
        self.assertTrue(p1["r3_bijection_verified"])
        self.assertTrue(p1["r2_irreversible_collision_verified"])
        self.assertEqual(p1["r3_over_r1_switching_ratio_q"], "509/12")

        for fn_name, bad_ret, code in (
            ("inv_r1_bijective_low", lambda a, b: (a ^ 1, b), "ALGEBRA_R1_NOT_BIJECTIVE"),
            ("inv_r1_bijective_low", lambda a, b: (a, b ^ 1), "ALGEBRA_R1_NOT_BIJECTIVE"),
            ("inv_r3_bijective_high", lambda a, b: (a ^ 1, b), "ALGEBRA_R3_NOT_BIJECTIVE"),
            ("inv_r3_bijective_high", lambda a, b: (a, b ^ 1), "ALGEBRA_R3_NOT_BIJECTIVE"),
        ):
            real_fn = getattr(orc, fn_name)
            with mock.patch.object(orc, fn_name, side_effect=lambda a, b, _r=real_fn, _m=bad_ret: _m(*_r(a, b))):
                with self.assertRaises(orc.RaplLandauerError) as cm_alg:
                    orc.prove_step_algebra()
                self.assertEqual(cm_alg.exception.code, code)
        with mock.patch.object(orc, "step_r2_erase_low", side_effect=[(1, 1), (2, 2)]):
            with self.assertRaises(orc.RaplLandauerError) as cm_c:
                orc.prove_step_algebra()
            self.assertEqual(cm_c.exception.code, "ALGEBRA_R2_COLLISION_FAIL")

        # Direct Schur non-pos diag guard, gauge helper & _pair_r2_or_zero
        deg_gram = [
            [Fraction(1, 1), Fraction(0, 1), Fraction(0, 1)],
            [Fraction(0, 1), Fraction(0, 1), Fraction(0, 1)],
            [Fraction(0, 1), Fraction(0, 1), Fraction(1, 1)],
        ]
        with self.assertRaises(orc.RaplLandauerError) as cm_sd:
            orc._exact_schur_diagnostics_q(deg_gram, [0, 1], [2], Fraction(1, 20))
        self.assertEqual(cm_sd.exception.code, "SCHUR_NON_POS_DIAG")
        with self.assertRaises(orc.RaplLandauerError) as cm_sp2:
            orc._exact_schur_diagnostics_q(deg_gram, [0, 1], [], Fraction(1, 20))
        self.assertEqual(cm_sp2.exception.code, "INVALID_SCHUR_PARTITION")

        z = Fraction(0, 1)
        one = Fraction(1, 1)
        self.assertTrue(orc._check_gauge_zero_exact(z, z, z, [2, 0, 0], [2, 0, 0], one, z, z, z, z))
        for args_bad in (
            (one, z, z, [2, 0, 0], [2, 0, 0], one, z, z, z, z),
            (z, one, z, [2, 0, 0], [2, 0, 0], one, z, z, z, z),
            (z, z, one, [2, 0, 0], [2, 0, 0], one, z, z, z, z),
            (z, z, z, [1, 1, 0], [2, 0, 0], one, z, z, z, z),
            (z, z, z, [2, 0, 0], [2, 0, 0], z, z, z, z, z),
            (z, z, z, [2, 0, 0], [2, 0, 0], one, one, z, z, z),
            (z, z, z, [2, 0, 0], [2, 0, 0], one, z, z, one, z),
        ):
            self.assertFalse(orc._check_gauge_zero_exact(*args_bad))
        r2_tiny = [[one, Fraction(1, 2)], [Fraction(1, 2), one]]
        self.assertEqual(orc._pair_r2_or_zero(r2_tiny, {0: 0, 3: 1}, 0, 3), Fraction(1, 2))
        self.assertEqual(orc._pair_r2_or_zero(r2_tiny, {3: 1}, 0, 3), z)
        self.assertEqual(orc._pair_r2_or_zero(r2_tiny, {0: 0}, 0, 3), z)

        # Direct linear algebra edge cases: singular matrix, 2x2 hyperbolic pivot, zero block, ARI edge cases
        with self.assertRaises(orc.RaplLandauerError) as cm:
            orc._invert_spd_q([[Fraction(0, 1), Fraction(0, 1)], [Fraction(0, 1), Fraction(1, 1)]])
        self.assertEqual(cm.exception.code, "SINGULAR_MATRIX")
        # Row swap branch inside Gauss-Jordan
        inv_sw = orc._invert_spd_q([[Fraction(0, 1), Fraction(1, 1)], [Fraction(1, 1), Fraction(0, 1)]])
        self.assertEqual(inv_sw, [[Fraction(0, 1), Fraction(1, 1)], [Fraction(1, 1), Fraction(0, 1)]])
        # Inertia: positive, negative, 2x2 hyperbolic off-diag with trailing entry, and zero block
        self.assertEqual(orc._symmetric_inertia_q([[Fraction(2, 1), Fraction(0, 1)], [Fraction(0, 1), Fraction(-3, 1)]]), [1, 0, 1])
        self.assertEqual(orc._symmetric_inertia_q([[Fraction(0, 1), Fraction(0, 1)], [Fraction(0, 1), Fraction(0, 1)]]), [0, 2, 0])
        hyp = [
            [Fraction(0, 1), Fraction(0, 1), Fraction(2, 1), Fraction(1, 1)],
            [Fraction(0, 1), Fraction(0, 1), Fraction(0, 1), Fraction(0, 1)],
            [Fraction(2, 1), Fraction(0, 1), Fraction(0, 1), Fraction(1, 1)],
            [Fraction(1, 1), Fraction(0, 1), Fraction(1, 1), Fraction(0, 1)],
        ]
        self.assertEqual(orc._symmetric_inertia_q(hyp), [1, 1, 2])
        # Schur partition guards & ARI edge cases
        with self.assertRaises(orc.RaplLandauerError) as cm:
            orc._exact_schur_diagnostics_q([[Fraction(1, 1)]], [0], [], Fraction(1, 20))
        self.assertEqual(cm.exception.code, "INVALID_SCHUR_PARTITION")
        with self.assertRaises(orc.RaplLandauerError) as cm:
            orc._exact_schur_diagnostics_q([[Fraction(1, 1)]], [0], [0], Fraction(1, 20))
        self.assertEqual(cm.exception.code, "INVALID_SCHUR_PARTITION")
        with self.assertRaises(orc.RaplLandauerError) as cm:
            orc._two_sample_perm_pvalue_q([], [Fraction(1, 1)], seed=1, reps=5)
        self.assertEqual(cm.exception.code, "EMPTY_PERM_SAMPLE")
        with self.assertRaises(orc.RaplLandauerError) as cm:
            orc._two_sample_perm_pvalue_q([Fraction(1, 1)], [], seed=1, reps=5)
        self.assertEqual(cm.exception.code, "EMPTY_PERM_SAMPLE")
        self.assertEqual(orc._ari_exact_q([0, 0, 0], [1, 1, 1]), Fraction(1, 1))
        self.assertEqual(orc._ari_exact_q([0, 0, 0], [0, 1, 2]), Fraction(0, 1))
        with self.assertRaises(orc.RaplLandauerError) as cm:
            orc._ari_exact_q([0], [0])
        self.assertEqual(cm.exception.code, "INVALID_ARI_INPUT")
        with self.assertRaises(orc.RaplLandauerError) as cm:
            orc._ari_exact_q([0, 1], [0])
        self.assertEqual(cm.exception.code, "INVALID_ARI_INPUT")

        # Zero-degree blind modularity branch
        lbls, modq = orc._blind_connected_components([[Fraction(1, 1), Fraction(0, 1)], [Fraction(0, 1), Fraction(1, 1)]], Fraction(1, 4))
        self.assertEqual((lbls, modq), ([0, 1], Fraction(0, 1)))

    def test_snapshot_validation_error_branches(self) -> None:
        base = _make_mini_snapshot(3)
        self.assertEqual(orc.validate_snapshot_structure(base)["schema_version"], "aletheia.track_s61.rapl_landauer_snapshot.v1")

        def _expect(mutator: Any, code: str) -> None:
            s = copy.deepcopy(base)
            s2 = mutator(s)
            with self.assertRaises(orc.RaplLandauerError) as cm:
                orc.validate_snapshot_structure(s2)
            self.assertEqual(cm.exception.code, code)

        _expect(lambda s: [], "INVALID_SNAPSHOT_TYPE")
        _expect(lambda s: {**s, "schema_version": "wrong"}, "INVALID_SNAPSHOT_SCHEMA")
        _expect(lambda s: {**s, "privacy_locks": []}, "INVALID_PRIVACY_LOCKS")
        _expect(lambda s: {**s, "privacy_locks": {**s["privacy_locks"], "audio_capture_accessed": True}}, "PRIVACY_LOCK_VIOLATION")
        _expect(lambda s: {**s, "privacy_locks": {**s["privacy_locks"], "camera_accessed": True}}, "PRIVACY_LOCK_VIOLATION")
        _expect(lambda s: {**s, "privacy_locks": {**s["privacy_locks"], "display_modified": True}}, "PRIVACY_LOCK_VIOLATION")
        _expect(lambda s: {**s, "step_algebra_self_checked": False}, "STEP_ALGEBRA_UNCHECKED")
        _expect(lambda s: {**s, "channels": []}, "INVALID_CHANNELS")
        _expect(lambda s: {**s, "channels": "x" * 20}, "INVALID_CHANNELS")
        _expect(lambda s: {**s, "channels": ["bad"] + s["channels"][1:]}, "INVALID_CHANNEL_ITEM")
        def _bad_rapl(s: dict[str, Any]) -> dict[str, Any]:
            s["channels"][0]["name"] = "wrong"
            return s
        _expect(_bad_rapl, "INVALID_RAPL_ORDER")
        _expect(lambda s: {**s, "regimes": []}, "INVALID_REGIMES")
        _expect(lambda s: {**s, "regimes": "x" * 7}, "INVALID_REGIMES")
        _expect(lambda s: {**s, "regimes": ["bad"] + s["regimes"][1:]}, "INVALID_REGIME_ITEM")
        def _bad_rid(s: dict[str, Any]) -> dict[str, Any]:
            s["regimes"][0]["id"] = "WRONG"
            return s
        _expect(_bad_rid, "INVALID_REGIME_ID")
        _expect(lambda s: {**s, "X_anonymous": s["X_anonymous"][:5]}, "INVALID_X_MATRIX")
        _expect(lambda s: {**s, "X_anonymous": "x" * 21}, "INVALID_X_MATRIX")
        _expect(lambda s: {**s, "regime_labels": s["regime_labels"][:-1]}, "INVALID_ROW_LENGTHS")
        _expect(lambda s: {**s, "regime_labels": tuple(s["regime_labels"])}, "INVALID_ROW_LENGTHS")
        _expect(lambda s: {**s, "dt_us": s["dt_us"][:-1]}, "INVALID_ROW_LENGTHS")
        _expect(lambda s: {**s, "dt_us": tuple(s["dt_us"])}, "INVALID_ROW_LENGTHS")
        def _bad_xrow(s: dict[str, Any]) -> dict[str, Any]:
            s["X_anonymous"][0] = [1, 2]
            return s
        _expect(_bad_xrow, "INVALID_X_ROW")
        def _bad_xrow_type(s: dict[str, Any]) -> dict[str, Any]:
            s["X_anonymous"][0] = "x" * 20
            return s
        _expect(_bad_xrow_type, "INVALID_X_ROW")

        # Gauge perm, active drift, and gauge broken guards inside evaluate_blind_schur_tomography
        with self.assertRaises(orc.RaplLandauerError) as cm:
            orc.evaluate_blind_schur_tomography(base, gauge_perm=[0] * 20)
        self.assertEqual(cm.exception.code, "GAUGE_PERM_INVALID")
        real_cg = orc._centered_gram_q
        cg_calls = {"n": 0}
        def _drift_cg(cols: Any) -> Any:
            cg_calls["n"] += 1
            act, zv, gr = real_cg(cols)
            if cg_calls["n"] == 2:
                return act[:-1], zv + [act[-1]], [row[:-1] for row in gr[:-1]]
            return act, zv, gr
        with mock.patch.object(orc, "_centered_gram_q", side_effect=_drift_cg):
            with self.assertRaises(orc.RaplLandauerError) as cm:
                orc.evaluate_blind_schur_tomography(base)
            self.assertEqual(cm.exception.code, "GAUGE_ACTIVE_DRIFT")
        with mock.patch.object(orc, "_ari_exact_q", return_value=Fraction(0, 1)):
            with self.assertRaises(orc.RaplLandauerError) as cm:
                orc.evaluate_blind_schur_tomography(base)
            self.assertEqual(cm.exception.code, "GAUGE_INVARIANCE_BROKEN")

        # Regime sample count mismatch & zero erased bits in R2
        s_cnt = copy.deepcopy(base)
        s_cnt["regimes"][0]["n_samples"] = 4
        with self.assertRaises(orc.RaplLandauerError) as cm:
            orc.evaluate_regime_physics_and_landauer(s_cnt)
        self.assertEqual(cm.exception.code, "REGIME_SAMPLE_COUNT_MISMATCH")

        s_er = copy.deepcopy(base)
        s_er["regimes"][2]["total_erased_bits"] = 0
        with self.assertRaises(orc.RaplLandauerError) as cm:
            orc.evaluate_regime_physics_and_landauer(s_er)
        self.assertEqual(cm.exception.code, "ZERO_ERASED_BITS_R2")


class TestParsersAuditAndBijectiveTamperKills(unittest.TestCase):
    def test_strict_parsers_rational_and_json_tree_guards(self) -> None:
        max_b = (1 << aud.MAX_JSON_INT_BITS) - 1
        over_b = 1 << aud.MAX_JSON_INT_BITS
        self.assertEqual(aud._parse_bounded_int("0"), 0)
        self.assertEqual(aud._parse_bounded_int("-42"), -42)
        self.assertEqual(aud._parse_bounded_int(str(max_b)), max_b)
        for bad_tok, code in (
            ("", "INVALID_JSON_INT"),
            ("-0", "INVALID_JSON_INT"),
            ("01", "INVALID_JSON_INT"),
            ("12a", "INVALID_JSON_INT"),
            ("9" * (aud.MAX_JSON_INT_DIGITS + 1), "INT_DIGIT_LIMIT"),
            (str(over_b), "INT_BIT_LIMIT"),
        ):
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud._parse_bounded_int(bad_tok)
            self.assertEqual(cm.exception.code, code)

        self.assertEqual(aud.parse_canonical_rational_str("0"), Fraction(0, 1))
        self.assertEqual(aud.parse_canonical_rational_str("-3/4"), Fraction(-3, 4))
        for bad_r, code in (
            ("1/2/3", "INVALID_RATIONAL_STR"),
            ("1/0", "INVALID_RATIONAL_STR"),
            ("1/02", "INVALID_RATIONAL_STR"),
            ("1/2a", "INVALID_RATIONAL_STR"),
            ("2/1", "NON_CANONICAL_RATIONAL"),
            ("2/4", "NON_CANONICAL_RATIONAL"),
        ):
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.parse_canonical_rational_str(bad_r)
            self.assertEqual(cm.exception.code, code)

        for raw_b, code in (
            (b"", "EMPTY_FILE"),
            ("not_bytes", "EMPTY_FILE"),
            (b'{"a":1}\r\n', "CRLF_FORBIDDEN"),
            (b'{"a":1}', "MISSING_TRAILING_LF"),
            (b"\xff\xfe\n", "INVALID_UTF8"),
            (b'{"a":1.5}\n', "FORBIDDEN_JSON_FLOAT"),
            (b'{"a":NaN}\n', "FORBIDDEN_JSON_CONSTANT"),
            (b'{"a":1,"a":2}\n', "DUPLICATE_JSON_KEY"),
            (b"{bad}\n", "JSON_PARSE_ERROR"),
            (b"[1,2]\n", "INVALID_JSON_ROOT"),
            (b'{ "a": 1 }\n', "NON_CANONICAL_BYTES"),
            (b'{"a\\u0000":1}\n', "NUL_BYTE_FORBIDDEN"),
        ):
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.parse_strict_json_bytes(raw_b)
            self.assertEqual(cm.exception.code, code)

        # Iterative tree depth, exact types, subclasses, surrogates, NUL
        deep: Any = 1
        for _ in range(aud.MAX_JSON_DEPTH + 2):
            deep = [deep]
        for bad_tree, code in (
            (deep, "JSON_DEPTH_EXCEEDED"),
            ({1: "a"}, "INVALID_JSON_KEY_TYPE"),
            ({"a\ud800": 1}, "INVALID_UTF8_SURROGATE"),
            ({"a\x00": 1}, "NUL_BYTE_FORBIDDEN"),
            ({"a": "b\ud800"}, "INVALID_UTF8_SURROGATE"),
            ({"a": "b\x00"}, "NUL_BYTE_FORBIDDEN"),
            ({"a": over_b}, "INT_BIT_LIMIT"),
            ({"a": json.loads("1.5")}, "FORBIDDEN_JSON_TYPE"),
            ({"a": _EvilInt(1)}, "FORBIDDEN_JSON_TYPE"),
            ({"a": _EvilStr("x")}, "FORBIDDEN_JSON_TYPE"),
            (_EvilDict({"a": 1}), "FORBIDDEN_JSON_TYPE"),
            ({"a": _EvilList([1])}, "FORBIDDEN_JSON_TYPE"),
        ):
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud._validate_json_tree(bad_tree)
            self.assertEqual(cm.exception.code, code)
        aud._validate_json_tree({"a": None, "b": True, "c": [1, "ok", max_b]})
        exact_deep: Any = 1
        for _ in range(aud.MAX_JSON_DEPTH):
            exact_deep = [exact_deep]
        aud._validate_json_tree(exact_deep)

    def test_secondary_audit_and_full_replay_tamper_matrix(self) -> None:
        snap = _make_mini_snapshot(3)
        cert = orc.build_certificate_from_snapshot(snap, mlos_receipt_sha256="b" * 64)
        res_full = aud.verify_certificate_dict(cert, full_replay=True, snapshot=snap)
        self.assertTrue(res_full["valid"])
        self.assertTrue(res_full["full_replay"])
        res_fr0 = aud.verify_certificate_dict(cert, full_replay=False)
        self.assertTrue(res_fr0["valid"])
        self.assertFalse(res_fr0["full_replay"])

        # Top-level cert envelope & full_replay type tampers
        with self.assertRaises(orc.RaplLandauerError) as cm_fr:
            aud.verify_certificate_dict(cert, full_replay=1)  # type: ignore[arg-type]
        self.assertEqual(cm_fr.exception.code, "INVALID_BOOL")
        for mut_fn, code in (
            (lambda c: [], "INVALID_CERT_TYPE"),
            (lambda c: {**c, "extra": 1}, "INVALID_CERT_KEYS"),
            (lambda c: {**c, "schema_version": "bad"}, "SCHEMA_VALUE_MISMATCH"),
            (lambda c: {**c, "track_id": "bad"}, "SCHEMA_VALUE_MISMATCH"),
            (lambda c: {**c, "payload_sha256": "0" * 64}, "PAYLOAD_SHA_MISMATCH"),
            (lambda c: {**c, "certificate_sha256": "0" * 64}, "CERT_SHA_MISMATCH"),
        ):
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.verify_certificate_dict(mut_fn(copy.deepcopy(cert)), full_replay=False)
            self.assertEqual(cm.exception.code, code)

        # Full replay mismatch on re-signed forged payload leaf
        forged_r = copy.deepcopy(cert)
        forged_r["payload"]["pillar2_regime_physics_and_landauer"]["per_regime"][0]["mean_fan_cpu_rpm_dec1"] = "9999.9"
        forged_r = _resign_cert(forged_r)
        with self.assertRaises(orc.RaplLandauerError) as cm:
            aud.verify_certificate_dict(forged_r, full_replay=True, snapshot=snap)
        self.assertEqual(cm.exception.code, "FULL_REPLAY_MISMATCH")

        # Direct secondary_audit_payload tampers across all 3 pillars
        p0 = cert["payload"]
        def _sec_fail(mutator: Any, code: str) -> None:
            p = copy.deepcopy(p0)
            p2 = mutator(p)
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.secondary_audit_payload(p2)
            self.assertEqual(cm.exception.code, code)

        _sec_fail(lambda p: [], "INVALID_PAYLOAD_TYPE")
        _sec_fail(lambda p: {**p, "extra": 1}, "INVALID_SCHEMA_KEYS")
        _sec_fail(lambda p: {**p, "schema_version": "bad"}, "SCHEMA_VALUE_MISMATCH")
        _sec_fail(lambda p: {**p, "track_id": "bad"}, "SCHEMA_VALUE_MISMATCH")
        _sec_fail(lambda p: {**p, "measured_live_silicon": False}, "SCHEMA_VALUE_MISMATCH")
        _sec_fail(lambda p: {**p, "privacy_locks": []}, "INVALID_SCHEMA_DICT")
        _sec_fail(lambda p: {**p, "privacy_locks": {}}, "INVALID_SCHEMA_KEYS")
        _sec_fail(lambda p: {**p, "privacy_locks": {**p["privacy_locks"], "audio_capture_accessed": True}}, "PRIVACY_LOCK_VIOLATION")
        _sec_fail(lambda p: {**p, "privacy_locks": {**p["privacy_locks"], "camera_accessed": True}}, "PRIVACY_LOCK_VIOLATION")
        _sec_fail(lambda p: {**p, "privacy_locks": {**p["privacy_locks"], "display_modified": True}}, "PRIVACY_LOCK_VIOLATION")
        _sec_fail(lambda p: {**p, "pillar1_step_algebra": []}, "INVALID_SCHEMA_DICT")
        _sec_fail(lambda p: {**p, "pillar1_step_algebra": {**p["pillar1_step_algebra"], "witness_pair_count": 9}}, "PILLAR1_MISMATCH")
        _sec_fail(lambda p: {**p, "pillar2_regime_physics_and_landauer": {}}, "INVALID_SCHEMA_KEYS")
        _sec_fail(lambda p: {**p, "pillar2_regime_physics_and_landauer": {**p["pillar2_regime_physics_and_landauer"], "per_regime": []}}, "INVALID_SCHEMA_LIST")
        _sec_fail(lambda p: {**p, "pillar2_regime_physics_and_landauer": {**p["pillar2_regime_physics_and_landauer"], "per_regime": "x" * 7}}, "INVALID_SCHEMA_LIST")

        # Exact legal boundary passes (conservation == 3e-6, pv == 1, rv == 0, sv == 0 & 1)
        p_bnd = copy.deepcopy(p0)
        r0 = p_bnd["pillar2_regime_physics_and_landauer"]["per_regime"][0]
        tol = Fraction(3, 10**6)
        pkg0 = aud.parse_canonical_rational_str(r0["pkg_w_q"])
        cor0 = aud.parse_canonical_rational_str(r0["core_w_q"])
        unc0 = aud.parse_canonical_rational_str(r0["uncore_w_q"])
        psy0 = aud.parse_canonical_rational_str(r0["psys_w_q"])
        mmi0 = aud.parse_canonical_rational_str(r0["mmio_w_q"])
        d0 = pkg0 - cor0 - unc0 + tol
        pd0 = psy0 - pkg0 + tol
        md0 = pkg0 - mmi0 + tol
        r0["pkg_in_package_dark_w_q"] = orc.format_rational(d0)
        r0["pkg_in_package_dark_w_dec3"] = orc.format_decimal(d0, 3)
        r0["psys_minus_pkg_w_q"] = orc.format_rational(pd0)
        r0["psys_minus_pkg_w_dec3"] = orc.format_decimal(pd0, 3)
        r0["pkg_minus_mmio_w_q"] = orc.format_rational(md0)
        r0["pkg_minus_mmio_w_dec3"] = orc.format_decimal(md0, 3)
        r0["mean_fan_cpu_rpm_dec1"] = "0.0"
        r0["mean_fan_gpu_rpm_dec1"] = "15000.0"
        r1_b = p_bnd["pillar2_regime_physics_and_landauer"]["per_regime"][1]
        r2_b = p_bnd["pillar2_regime_physics_and_landauer"]["per_regime"][2]
        c21_bnd = aud.parse_canonical_rational_str(r2_b["core_w_q"]) - aud.parse_canonical_rational_str(r1_b["core_w_q"]) + tol
        p_bnd["pillar2_regime_physics_and_landauer"]["pairwise_contrasts"]["r2_minus_r1_core_w_q"] = orc.format_rational(c21_bnd)
        p_bnd["pillar2_regime_physics_and_landauer"]["pairwise_contrasts"]["r2_minus_r1_core_w_dec3"] = orc.format_decimal(c21_bnd, 3)
        p_bnd["pillar2_regime_physics_and_landauer"]["pairwise_contrasts"]["p_r2_vs_r1_core_q"] = "1"
        p_bnd["pillar3_blind_schur_tomography"]["uncore_vs_pkg_r2_q"] = "0"
        p_bnd["pillar3_blind_schur_tomography"]["uncore_vs_pkg_r2_dec4"] = "0.0000"
        p_bnd["pillar3_blind_schur_tomography"]["blind_modularity_q"] = "-1/2"
        p_bnd["pillar3_blind_schur_tomography"]["blind_modularity_dec4"] = "-0.5000"
        p_bnd["pillar3_blind_schur_tomography"]["physical_partition_schur"]["mean_residual_rho2_q"] = "0"
        p_bnd["pillar3_blind_schur_tomography"]["physical_partition_schur"]["mean_residual_rho2_dec4"] = "0.0000"
        p_bnd["pillar3_blind_schur_tomography"]["physical_partition_schur"]["mean_unexplained_variance_eta_q"] = "1"
        p_bnd["pillar3_blind_schur_tomography"]["physical_partition_schur"]["mean_unexplained_variance_eta_dec4"] = "1.0000"
        self.assertTrue(aud.secondary_audit_payload(p_bnd)["secondary_audit_passed"])
        p_bnd["pillar3_blind_schur_tomography"]["blind_modularity_q"] = "1"
        p_bnd["pillar3_blind_schur_tomography"]["blind_modularity_dec4"] = "1.0000"
        self.assertTrue(aud.secondary_audit_payload(p_bnd)["secondary_audit_passed"])

        def _mut_p2_reg(field: str, val: Any, idx: int = 0) -> Any:
            def _f(p: dict[str, Any]) -> dict[str, Any]:
                p["pillar2_regime_physics_and_landauer"]["per_regime"][idx][field] = val
                return p
            return _f

        _sec_fail(_mut_p2_reg("id", "WRONG"), "SCHEMA_VALUE_MISMATCH")
        _sec_fail(_mut_p2_reg("pkg_w_q", "-1"), "NEGATIVE_POWER")
        _sec_fail(_mut_p2_reg("core_w_q", "-1"), "NEGATIVE_POWER")
        _sec_fail(_mut_p2_reg("uncore_w_q", "-1"), "NEGATIVE_POWER")
        _sec_fail(_mut_p2_reg("psys_w_q", "-1"), "NEGATIVE_POWER")
        _sec_fail(_mut_p2_reg("mmio_w_q", "-1"), "NEGATIVE_POWER")
        _sec_fail(_mut_p2_reg("mean_temp_pkg_k_q", "200"), "INVALID_TEMP_RANGE")
        _sec_fail(_mut_p2_reg("mean_temp_pkg_k_q", "500"), "INVALID_TEMP_RANGE")
        _sec_fail(_mut_p2_reg("mean_freq_mhz_q", "0"), "INVALID_FREQ")
        _sec_fail(_mut_p2_reg("pkg_in_package_dark_w_q", "999"), "CONSERVATION_MISMATCH")
        _sec_fail(_mut_p2_reg("psys_minus_pkg_w_q", "999"), "CONSERVATION_MISMATCH")
        _sec_fail(_mut_p2_reg("pkg_minus_mmio_w_q", "999"), "CONSERVATION_MISMATCH")
        _sec_fail(lambda p: {**p, "pillar2_regime_physics_and_landauer": {**p["pillar2_regime_physics_and_landauer"], "per_regime": [{}] + p["pillar2_regime_physics_and_landauer"]["per_regime"][1:]}}, "INVALID_SCHEMA_KEYS")

        def _mut_lb(field: str, val: Any) -> Any:
            def _f(p: dict[str, Any]) -> dict[str, Any]:
                p["pillar2_regime_physics_and_landauer"]["landauer_r2_bridge"][field] = val
                return p
            return _f

        _sec_fail(lambda p: {**p, "pillar2_regime_physics_and_landauer": {**p["pillar2_regime_physics_and_landauer"], "landauer_r2_bridge": {}}}, "INVALID_SCHEMA_KEYS")
        _sec_fail(_mut_lb("r2_erased_bits", 1), "LANDAUER_ERASED_MISMATCH")
        _sec_fail(_mut_lb("eta_gross_core_ceil_int", 1), "LANDAUER_BRACKET_INVALID")
        _sec_fail(_mut_lb("eta_gross_pkg_ceil_int", 1), "LANDAUER_BRACKET_INVALID")
        _sec_fail(_mut_lb("eta_net_core_ceil_int", 1), "LANDAUER_BRACKET_INVALID")
        _sec_fail(_mut_lb("r2_pkg_landauer_bits_hi", 1), "LANDAUER_BRACKET_INVALID")
        _sec_fail(_mut_lb("h1_cmos_landauer_obstruction_confirmed", False), "LANDAUER_H1_FLAG_MISMATCH")

        def _mut_pc(field: str, val: Any) -> Any:
            def _f(p: dict[str, Any]) -> dict[str, Any]:
                p["pillar2_regime_physics_and_landauer"]["pairwise_contrasts"][field] = val
                return p
            return _f

        _sec_fail(lambda p: {**p, "pillar2_regime_physics_and_landauer": {**p["pillar2_regime_physics_and_landauer"], "pairwise_contrasts": {}}}, "INVALID_SCHEMA_KEYS")
        _sec_fail(_mut_pc("p_r2_vs_r1_core_q", "0"), "INVALID_PVALUE")
        _sec_fail(_mut_pc("p_r2_vs_r1_core_q", "2"), "INVALID_PVALUE")
        _sec_fail(_mut_pc("psys_vendor_scale_obstruction_detected", False), "PSYS_FLAG_MISMATCH")

        # Pillar 3 tampers
        def _mut_p3(field: str, val: Any) -> Any:
            def _f(p: dict[str, Any]) -> dict[str, Any]:
                p["pillar3_blind_schur_tomography"][field] = val
                return p
            return _f

        _sec_fail(lambda p: {**p, "pillar3_blind_schur_tomography": {}}, "INVALID_SCHEMA_KEYS")
        _sec_fail(_mut_p3("active_indices", "bad"), "INVALID_SCHEMA_LIST")
        _sec_fail(_mut_p3("zero_var_indices", "bad"), "INVALID_SCHEMA_LIST")
        _sec_fail(_mut_p3("active_indices", list(range(18))), "PARTITION_MISMATCH")
        def _dup_act_union_ok(p: dict[str, Any]) -> dict[str, Any]:
            p["pillar3_blind_schur_tomography"]["active_indices"] = [0, 0] + list(range(1, 18)) + [19]
            p["pillar3_blind_schur_tomography"]["zero_var_indices"] = [18]
            return p
        _sec_fail(_dup_act_union_ok, "PARTITION_MISMATCH")
        def _dup_zv_union_ok(p: dict[str, Any]) -> dict[str, Any]:
            p["pillar3_blind_schur_tomography"]["active_indices"] = list(range(18)) + [19]
            p["pillar3_blind_schur_tomography"]["zero_var_indices"] = [18, 18]
            return p
        _sec_fail(_dup_zv_union_ok, "PARTITION_MISMATCH")
        def _overlap_union_ok(p: dict[str, Any]) -> dict[str, Any]:
            p["pillar3_blind_schur_tomography"]["active_indices"] = list(range(18)) + [19]
            p["pillar3_blind_schur_tomography"]["zero_var_indices"] = [0, 18]
            return p
        _sec_fail(_overlap_union_ok, "PARTITION_MISMATCH")
        _sec_fail(_mut_p3("mean_offdiag_r2_q", "2"), "R2_OUT_OF_RANGE")
        _sec_fail(_mut_p3("blind_r2_threshold_q", "1/2"), "SCHEMA_VALUE_MISMATCH")
        _sec_fail(_mut_p3("blind_cluster_labels", [0]), "INVALID_SCHEMA_LIST")
        _sec_fail(_mut_p3("blind_cluster_labels", "x" * len(p0["pillar3_blind_schur_tomography"]["active_indices"])), "INVALID_SCHEMA_LIST")

        def _mut_sp(field: str, val: Any) -> Any:
            def _f(p: dict[str, Any]) -> dict[str, Any]:
                p["pillar3_blind_schur_tomography"]["physical_partition_schur"][field] = val
                return p
            return _f

        _sec_fail(_mut_p3("physical_partition_schur", {}), "INVALID_SCHEMA_KEYS")
        _sec_fail(_mut_sp("ridge_lambda_q", "1/10"), "SCHEMA_VALUE_MISMATCH")
        _sec_fail(_mut_sp("a_active_positions", [0]), "INVALID_SCHEMA_LIST")
        _sec_fail(_mut_sp("a_active_positions", "x" * 14), "INVALID_SCHEMA_LIST")
        _sec_fail(_mut_sp("b_active_positions", []), "INVALID_SCHEMA_LIST")
        _sec_fail(_mut_sp("b_active_positions", "x" * 5), "INVALID_SCHEMA_LIST")
        _sec_fail(_mut_sp("a_active_positions", [5, 6]), "PARTITION_MISMATCH")
        def _schur_overlap(p: dict[str, Any]) -> dict[str, Any]:
            sp = p["pillar3_blind_schur_tomography"]["physical_partition_schur"]
            sp["a_active_positions"] = [0] + list(sp["a_active_positions"])
            return p
        _sec_fail(_schur_overlap, "PARTITION_MISMATCH")
        _sec_fail(_mut_sp("inertia", [1, 2]), "INVALID_SCHEMA_LIST")
        _sec_fail(_mut_sp("inertia", "xyz"), "INVALID_SCHEMA_LIST")
        _sec_fail(_mut_sp("inertia", [1, 0, 0]), "INERTIA_SUM_MISMATCH")
        _sec_fail(_mut_sp("mean_unexplained_variance_eta_q", "2"), "SCHUR_OUT_OF_RANGE")

        def _mut_gi(field: str, val: Any) -> Any:
            def _f(p: dict[str, Any]) -> dict[str, Any]:
                p["pillar3_blind_schur_tomography"]["stage_a_gauge_invariance"][field] = val
                return p
            return _f

        _sec_fail(_mut_p3("stage_a_gauge_invariance", {}), "INVALID_SCHEMA_KEYS")
        for gk, gv in (
            ("exact_zero_deviation", False),
            ("inertia_exact_match", False),
            ("max_r2_diff_q", "1/100"),
            ("eta_diff_q", "1/100"),
            ("res_rho2_diff_q", "1/100"),
            ("blind_cluster_gauge_ari_q", "0"),
        ):
            _sec_fail(_mut_gi(gk, gv), "GAUGE_INVARIANCE_BROKEN")

        def _mut_cn(field: str, val: Any) -> Any:
            def _f(p: dict[str, Any]) -> dict[str, Any]:
                p["pillar3_blind_schur_tomography"]["circular_shift_null"][field] = val
                return p
            return _f

        _sec_fail(_mut_p3("circular_shift_null", {}), "INVALID_SCHEMA_KEYS")
        _sec_fail(_mut_cn("p_mean_offdiag_r2_q", "1/2"), "CIRC_PVALUE_MISMATCH")
        _sec_fail(_mut_cn("p_mean_offdiag_r2_dec4", "0.9999"), "DECIMAL_MISMATCH")

        # S61-VER-01..03 R2 hardening tests: decimal parser, Landauer/contrast/regime/Schur pins,
        # 0K temperature guard, canonical_json_bytes float/NaN guard, short-write guard, and CLI NUL.
        self.assertEqual(aud._parse_canonical_decimal_str("42", 0, "d"), Fraction(42, 1))
        self.assertEqual(aud._parse_canonical_decimal_str("-1.250", 3, "d"), Fraction(-5, 4))
        for bad_dec, pl in (
            ("123", 3), ("1.2.3", 3), ("a.000", 3), ("1.abc", 3),
            ("1.00", 3), ("01.000", 3), ("-0.000", 3),
        ):
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud._parse_canonical_decimal_str(bad_dec, pl, "d")
            self.assertEqual(cm.exception.code, "INVALID_DECIMAL_STR")

        # Regime invariant, fan RPM, ops/s, and pJ/op pins
        _sec_fail(_mut_p2_reg("total_ops", 1, idx=0), "REGIME_INVARIANT_MISMATCH")
        _sec_fail(_mut_p2_reg("total_erased_bits", 1, idx=0), "REGIME_INVARIANT_MISMATCH")
        _sec_fail(_mut_p2_reg("total_toggle_bits", 1, idx=0), "REGIME_INVARIANT_MISMATCH")
        _sec_fail(_mut_p2_reg("total_ops", 0, idx=1), "REGIME_INVARIANT_MISMATCH")
        _sec_fail(_mut_p2_reg("total_erased_bits", 1, idx=1), "REGIME_INVARIANT_MISMATCH")
        _sec_fail(_mut_p2_reg("total_toggle_bits", 0, idx=1), "REGIME_INVARIANT_MISMATCH")
        _sec_fail(_mut_p2_reg("total_erased_bits", 0, idx=2), "REGIME_INVARIANT_MISMATCH")
        _sec_fail(_mut_p2_reg("total_toggle_bits", 0, idx=2), "REGIME_INVARIANT_MISMATCH")
        _sec_fail(_mut_p2_reg("total_toggle_bits", 0, idx=3), "REGIME_INVARIANT_MISMATCH")
        _sec_fail(_mut_p2_reg("total_toggle_bits", 1, idx=4), "REGIME_INVARIANT_MISMATCH")
        _sec_fail(_mut_p2_reg("mean_fan_cpu_rpm_dec1", "-0.1", idx=0), "INVALID_FAN_RPM")
        _sec_fail(_mut_p2_reg("mean_fan_gpu_rpm_dec1", "15000.1", idx=0), "INVALID_FAN_RPM")
        _sec_fail(_mut_p2_reg("ops_per_sec_dec0", "1", idx=0), "ENERGY_PER_OP_MISMATCH")
        _sec_fail(_mut_p2_reg("pkg_pj_per_op_q", "1", idx=0), "ENERGY_PER_OP_MISMATCH")
        _sec_fail(_mut_p2_reg("core_pj_per_op_q", "1", idx=0), "ENERGY_PER_OP_MISMATCH")
        _sec_fail(_mut_p2_reg("pkg_pj_per_op_dec4", "1.0000", idx=0), "ENERGY_PER_OP_MISMATCH")
        _sec_fail(_mut_p2_reg("core_pj_per_op_dec4", "1.0000", idx=0), "ENERGY_PER_OP_MISMATCH")
        _sec_fail(_mut_p2_reg("ops_per_sec_dec0", "1", idx=1), "DECIMAL_MISMATCH")
        _sec_fail(_mut_p2_reg("pkg_pj_per_op_q", "0", idx=1), "ENERGY_PER_OP_MISMATCH")
        _sec_fail(_mut_p2_reg("core_pj_per_op_q", "999999999", idx=1), "ENERGY_PER_OP_MISMATCH")
        _sec_fail(_mut_p2_reg("core_pj_per_op_dec4", "0.0000", idx=1), "DECIMAL_MISMATCH")
        _sec_fail(_mut_p2_reg("pkg_w_dec3", "0.000", idx=0), "DECIMAL_MISMATCH")
        _sec_fail(_mut_p2_reg("pkg_w_dec3", "999.000", idx=0), "DECIMAL_MISMATCH")

        # Landauer temp/bracket/Joule pins & _require_landauer_bracket boundary kills
        _sec_fail(_mut_lb("r2_temp_pkg_k_q", "350"), "LANDAUER_TEMP_MISMATCH")
        _sec_fail(_mut_lb("r2_temp_pkg_k_dec3", "350.000"), "LANDAUER_TEMP_MISMATCH")
        _sec_fail(_mut_lb("r2_core_j_dec6", "0.000001"), "DECIMAL_MISMATCH")
        _sec_fail(_mut_lb("r2_pkg_j_dec6", "999999.000000"), "DECIMAL_MISMATCH")
        for lo_v, hi_v in ((11, 11), (9, 11), (13, 14), (10, 10), (10, 14)):
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud._require_landauer_bracket(lo_v, hi_v, Fraction(10, 1), Fraction(12, 1), Fraction(1, 1), Fraction(1, 1), "lb")
            self.assertEqual(cm.exception.code, "LANDAUER_BRACKET_INVALID")
        aud._require_landauer_bracket(10, 13, Fraction(10, 1), Fraction(12, 1), Fraction(1, 1), Fraction(1, 1), "lb")

        # Contrast, permutation grid, and R5 core_pj == 0 pins
        _sec_fail(_mut_pc("p_r3_vs_r1_core_q", "1/99"), "INVALID_PVALUE")
        _sec_fail(_mut_pc("r3_minus_r1_core_w_q", "-999"), "CONTRAST_MISMATCH")
        _sec_fail(_mut_pc("r4_fp64_over_r5_vnni_pj_per_op_q", "-1"), "CONTRAST_MISMATCH")
        _sec_fail(_mut_pc("r4_fp64_over_r5_vnni_pj_per_op_q", "999999"), "CONTRAST_MISMATCH")
        _sec_fail(_mut_pc("r4_fp64_over_r5_vnni_pj_per_op_dec3", "0.000"), "DECIMAL_MISMATCH")
        def _zero_r5_core_pj(p: dict[str, Any]) -> dict[str, Any]:
            r4 = p["pillar2_regime_physics_and_landauer"]["per_regime"][4]
            r5 = p["pillar2_regime_physics_and_landauer"]["per_regime"][5]
            pkg5 = aud.parse_canonical_rational_str(r5["pkg_w_q"])
            unc5 = aud.parse_canonical_rational_str(r5["uncore_w_q"])
            c4 = aud.parse_canonical_rational_str(r4["core_w_q"])
            r5["core_w_q"] = "0"
            r5["core_w_dec3"] = "0.000"
            d5 = pkg5 - unc5
            r5["pkg_in_package_dark_w_q"] = orc.format_rational(d5)
            r5["pkg_in_package_dark_w_dec3"] = orc.format_decimal(d5, 3)
            r5["core_pj_per_op_q"] = "0"
            r5["core_pj_per_op_dec4"] = "0.0000"
            pc5 = p["pillar2_regime_physics_and_landauer"]["pairwise_contrasts"]
            pc5["r5_minus_r4_core_w_q"] = orc.format_rational(-c4)
            pc5["r5_minus_r4_core_w_dec3"] = orc.format_decimal(-c4, 3)
            return p
        _sec_fail(_zero_r5_core_pj, "CONTRAST_MISMATCH")

        # Pillar 3 cluster IDs, modularity, Schur dup a/b, precision/recall consistency, and SPD inertia
        _sec_fail(_mut_p3("blind_cluster_labels", [1] * len(p0["pillar3_blind_schur_tomography"]["active_indices"])), "INVALID_CLUSTER_IDS")
        _sec_fail(_mut_p3("blind_modularity_q", "-1"), "R2_OUT_OF_RANGE")
        _sec_fail(_mut_p3("blind_modularity_q", "2"), "R2_OUT_OF_RANGE")
        _sec_fail(_mut_p3("blind_modularity_dec4", "0.9999"), "DECIMAL_MISMATCH")
        def _dup_apos(p: dict[str, Any]) -> dict[str, Any]:
            sp = p["pillar3_blind_schur_tomography"]["physical_partition_schur"]
            sp["a_active_positions"] = list(sp["a_active_positions"]) + [sp["a_active_positions"][0]]
            return p
        def _dup_bpos(p: dict[str, Any]) -> dict[str, Any]:
            sp = p["pillar3_blind_schur_tomography"]["physical_partition_schur"]
            sp["b_active_positions"] = list(sp["b_active_positions"]) + [sp["b_active_positions"][0]]
            return p
        _sec_fail(_dup_apos, "PARTITION_MISMATCH")
        _sec_fail(_dup_bpos, "PARTITION_MISMATCH")
        _sec_fail(_mut_sp("inertia", [0, 0, len(p0["pillar3_blind_schur_tomography"]["physical_partition_schur"]["a_active_positions"])]), "INERTIA_SUM_MISMATCH")
        _sec_fail(_mut_p3("blind_rapl_recall_q", "0"), "BLIND_CLUSTER_CONSISTENCY")
        def _nonint_inter(p: dict[str, Any]) -> dict[str, Any]:
            p3 = p["pillar3_blind_schur_tomography"]
            cid = p3["blind_rapl_best_cluster_id"]
            bsz = sum(1 for c in p3["blind_cluster_labels"] if c == cid)
            nb = len(p3["physical_partition_schur"]["b_active_positions"])
            p3["blind_rapl_precision_q"] = orc.format_rational(Fraction(1, 2 * bsz))
            p3["blind_rapl_recall_q"] = orc.format_rational(Fraction(1, 2 * nb))
            return p
        _sec_fail(_nonint_inter, "BLIND_CLUSTER_CONSISTENCY")

        # All 6 re-signed AUDIT-161 semantic forgeries rejected under full_replay=False
        for mut_f in (
            lambda c: (
                c["payload"]["pillar2_regime_physics_and_landauer"]["landauer_r2_bridge"].__setitem__("eta_gross_core_floor_int", 0),
                c["payload"]["pillar2_regime_physics_and_landauer"]["landauer_r2_bridge"].__setitem__("eta_gross_core_ceil_int", 1),
                c["payload"]["pillar2_regime_physics_and_landauer"]["landauer_r2_bridge"].__setitem__("h1_cmos_landauer_obstruction_confirmed", False),
            ),
            lambda c: (
                c["payload"]["pillar2_regime_physics_and_landauer"]["pairwise_contrasts"].__setitem__("r3_minus_r1_core_w_q", "-999"),
                c["payload"]["pillar2_regime_physics_and_landauer"]["pairwise_contrasts"].__setitem__("p_r3_vs_r1_core_q", "1/99"),
            ),
            lambda c: c["payload"]["pillar3_blind_schur_tomography"]["physical_partition_schur"].__setitem__("inertia", [0, 0, 14]),
            lambda c: (
                c["payload"]["pillar3_blind_schur_tomography"]["physical_partition_schur"]["a_active_positions"].append(5),
                c["payload"]["pillar3_blind_schur_tomography"]["physical_partition_schur"].__setitem__("inertia", [15, 0, 0]),
            ),
            lambda c: c["payload"]["pillar2_regime_physics_and_landauer"]["per_regime"][0].__setitem__("total_ops", 999999),
            lambda c: c["payload"]["pillar2_regime_physics_and_landauer"]["per_regime"][0].__setitem__("core_w_dec3", None),
        ):
            cf = copy.deepcopy(cert)
            mut_f(cf)
            with self.assertRaises(orc.RaplLandauerError):
                aud.verify_certificate_dict(_resign_cert(cf), full_replay=False)

        # S61-VER-02: physical silicon temperature bounds & direct 0K ZeroDivisionError prevention
        for bad_t in (-1, 150_001):
            s_bt = _make_mini_snapshot(3)
            s_bt["X_anonymous"][0][5] = bad_t
            with self.assertRaises(orc.RaplLandauerError) as cm:
                orc.validate_snapshot_structure(s_bt)
            self.assertEqual(cm.exception.code, "INT_OUT_OF_RANGE")
        s_neg_other = _make_mini_snapshot(3)
        s_neg_other["X_anonymous"][0][6] = -5
        self.assertIs(orc.validate_snapshot_structure(s_neg_other), s_neg_other)
        s_0k = _make_mini_snapshot(3)
        for row_x in s_0k["X_anonymous"]:
            row_x[5] = -273150
        with self.assertRaises(orc.RaplLandauerError) as cm:
            orc.evaluate_regime_physics_and_landauer(s_0k)
        self.assertEqual(cm.exception.code, "INVALID_TEMP_RANGE")

        # S61-VER-03(b): direct oracle.canonical_json_bytes rejects floats & NaN with typed error
        for bad_json_txt in ('{"x":1.5}', '{"x":NaN}'):
            bad_obj = json.loads(bad_json_txt)
            with self.assertRaises(orc.RaplLandauerError) as cm:
                orc.canonical_json_bytes(bad_obj)
            self.assertEqual(cm.exception.code, "FORBIDDEN_JSON_TYPE")


class TestZoneBIODarwinConcurrencyAndLiveCert(unittest.TestCase):
    def test_zone_b_io_paths_symlinks_fifo_hardlinks_pwd_and_oserror_faults(self) -> None:
        snap = _make_mini_snapshot(3)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            nested = root / "sub1" / "sub2" / "cert.json"
            w_res = aud.write_certificate_file(nested, snapshot=snap, mlos_receipt_sha256="b" * 64)
            self.assertTrue(w_res["written"])
            self.assertEqual(stat.S_IMODE(os.lstat(nested).st_mode), 0o600)
            snap_p = root / "snap.json"
            aud.write_regular_bytes_safe(snap_p, orc.canonical_json_bytes(snap), "snap")
            rec_p = root / "rec.json"
            aud.write_regular_bytes_safe(rec_p, b'{"ok":true}\n', "rec")
            rec_sha = orc.sha256_hex(b'{"ok":true}\n')
            aud.write_certificate_file(nested, snapshot=snap, mlos_receipt_sha256=rec_sha)
            c_res = aud.check_certificate_file(nested, snapshot_path=snap_p, mlos_receipt_path=rec_p)
            self.assertTrue(c_res["valid"])

            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.read_regular_bytes_capped(_EvilPath(str(nested)))
            self.assertEqual(cm.exception.code, "INVALID_PATH_TYPE")
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.read_regular_bytes_capped(Path("a\x00b"))
            self.assertEqual(cm.exception.code, "NUL_BYTE_FORBIDDEN")
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.read_regular_bytes_capped(Path("bad\ud800.json"))
            self.assertEqual(cm.exception.code, "INVALID_UTF8_SURROGATE")
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.read_regular_bytes_capped(nested, "c", max_bytes=1 << 100)
            self.assertEqual(cm.exception.code, "INT_OUT_OF_RANGE")

            for bad_dir in (Path("/"), Path("."), Path(".."), Path("sub1/..")):
                with self.assertRaises(orc.RaplLandauerError) as cm:
                    aud.read_regular_bytes_capped(bad_dir)
                self.assertEqual(cm.exception.code, "NOT_A_REGULAR_FILE")

            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.read_regular_bytes_capped(root / "missing" / "x.json")
            self.assertEqual(cm.exception.code, "FILE_READ_ERROR")
            self.assertFalse((root / "missing").exists())

            sym_leaf = root / "sym_leaf.json"
            sym_leaf.symlink_to(nested)
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.read_regular_bytes_capped(sym_leaf)
            self.assertEqual(cm.exception.code, "SYMLINK_FORBIDDEN")
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.write_regular_bytes_safe(sym_leaf, b"x")
            self.assertEqual(cm.exception.code, "SYMLINK_FORBIDDEN")

            sym_dir = root / "sym_dir"
            sym_dir.symlink_to(nested.parent)
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.read_regular_bytes_capped(Path(f"{sym_dir}/../sub2/cert.json"))
            self.assertEqual(cm.exception.code, "SYMLINK_FORBIDDEN")
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.write_regular_bytes_safe(sym_dir / "x.json", b"a")
            self.assertEqual(cm.exception.code, "SYMLINK_FORBIDDEN")

            # Scratch FIFO (zero device-path writes)
            fifo = root / "p.fifo"
            os.mkfifo(fifo)
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.read_regular_bytes_capped(fifo)
            self.assertEqual(cm.exception.code, "NOT_A_REGULAR_FILE")
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.write_regular_bytes_safe(fifo, b"x")
            self.assertEqual(cm.exception.code, "NOT_A_REGULAR_FILE")

            # Hardlink rejected on BOTH read (--check) AND write (--write)!
            hl_a = root / "hl_a.json"
            hl_a.write_bytes(b"KEEP\n")
            hl_b = root / "hl_b.json"
            os.link(hl_a, hl_b)
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.read_regular_bytes_capped(hl_b)
            self.assertEqual(cm.exception.code, "HARDLINK_FORBIDDEN")
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.write_regular_bytes_safe(hl_b, b"CLOBBER\n")
            self.assertEqual(cm.exception.code, "HARDLINK_FORBIDDEN")
            self.assertEqual(hl_a.read_bytes(), b"KEEP\n")

            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.write_regular_bytes_safe(root / "nb.json", "not_bytes")  # type: ignore[arg-type]
            self.assertEqual(cm.exception.code, "INVALID_PAYLOAD_BYTES")

            fake_st = mock.Mock(st_nlink=2)
            with mock.patch("os.fstat", return_value=fake_st):
                with self.assertRaises(orc.RaplLandauerError) as cm:
                    aud.write_regular_bytes_safe(root / "tmp_hl.json", b"abc")
                self.assertEqual(cm.exception.code, "HARDLINK_FORBIDDEN")

            # Size fast-reject AND streaming read cap (st_size == 0 virtual-file simulation!)
            exact_f = root / "exact.bin"
            exact_f.write_bytes(b"x" * 70000)
            self.assertEqual(len(aud.read_regular_bytes_capped(exact_f, "ex", max_bytes=70000)), 70000)
            with self.assertRaises(orc.RaplLandauerError) as cm:
                aud.read_regular_bytes_capped(exact_f, "ex", max_bytes=69999)
            self.assertEqual(cm.exception.code, "FILE_TOO_LARGE")
            real_fstat = os.fstat
            def _zero_size_fstat(fd_arg: int) -> Any:
                st = real_fstat(fd_arg)
                return SimpleNamespace(st_mode=st.st_mode, st_nlink=1, st_size=0)
            with mock.patch.object(aud.os, "fstat", side_effect=_zero_size_fstat):
                with self.assertRaises(orc.RaplLandauerError) as cm:
                    aud.read_regular_bytes_capped(exact_f, "ex", max_bytes=69999)
                self.assertEqual(cm.exception.code, "FILE_TOO_LARGE")
            # Verify st_size fast-reject triggers BEFORE calling os.read
            def _huge_size_fstat(fd_arg: int) -> Any:
                st = real_fstat(fd_arg)
                return SimpleNamespace(st_mode=st.st_mode, st_nlink=1, st_size=99999)
            with (
                mock.patch.object(aud.os, "fstat", side_effect=_huge_size_fstat),
                mock.patch.object(aud.os, "read", side_effect=RuntimeError("should not read")),
            ):
                with self.assertRaises(orc.RaplLandauerError) as cm:
                    aud.read_regular_bytes_capped(exact_f, "ex", max_bytes=69999)
                self.assertEqual(cm.exception.code, "FILE_TOO_LARGE")

            # Relative CWD, stale/matching PWD, deleted CWD, and all 9 OSError fault handlers
            orig_cwd = os.getcwd()
            try:
                os.chdir(nested.parent)
                with mock.patch.dict(os.environ, {"PWD": str(nested.parent)}, clear=False):
                    self.assertEqual(aud.read_regular_bytes_capped(Path("./cert.json")), nested.read_bytes())
                with mock.patch.dict(os.environ, {"PWD": ""}, clear=False):
                    self.assertEqual(aud.read_regular_bytes_capped(Path("cert.json")), nested.read_bytes())
                with mock.patch.dict(os.environ, {"PWD": str(sym_dir)}, clear=False):
                    with self.assertRaises(orc.RaplLandauerError) as cm:
                        aud.read_regular_bytes_capped(Path("cert.json"))
                    self.assertEqual(cm.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")
                for stale_pwd in (str(root / "no_such_pwd"), str(root)):
                    with mock.patch.dict(os.environ, {"PWD": stale_pwd}, clear=False):
                        self.assertEqual(aud.read_regular_bytes_capped(Path("cert.json")), nested.read_bytes())
                with mock.patch.object(aud.os, "environ", {"PWD": "/tmp\x00stale"}):
                    self.assertEqual(aud.read_regular_bytes_capped(Path("cert.json")), nested.read_bytes())

                real_open = os.open
                def _deny_leaf_dir(path_arg: Any, flags: int, *a: Any, **kw: Any) -> int:
                    if path_arg == nested.parent.name and "dir_fd" in kw:
                        raise OSError(aud.errno.EACCES, "denied")
                    return real_open(path_arg, flags, *a, **kw)
                with (
                    mock.patch.dict(os.environ, {"PWD": str(nested.parent)}, clear=False),
                    mock.patch.object(aud.os, "open", side_effect=_deny_leaf_dir),
                ):
                    with self.assertRaises(orc.RaplLandauerError) as cm:
                        aud.read_regular_bytes_capped(Path("cert.json"))
                    self.assertEqual(cm.exception.code, "CWD_UNAVAILABLE")

                def _deny_root_open(path_arg: Any, flags: int, *a: Any, **kw: Any) -> int:
                    if path_arg == "/":
                        raise OSError(aud.errno.EACCES, "root")
                    return real_open(path_arg, flags, *a, **kw)
                with (
                    mock.patch.dict(os.environ, {"PWD": str(nested.parent)}, clear=False),
                    mock.patch.object(aud.os, "open", side_effect=_deny_root_open),
                ):
                    with self.assertRaises(orc.RaplLandauerError) as cm:
                        aud.read_regular_bytes_capped(Path("cert.json"))
                    self.assertEqual(cm.exception.code, "CWD_UNAVAILABLE")
                with mock.patch.object(aud.os, "open", side_effect=_deny_root_open):
                    with self.assertRaises(orc.RaplLandauerError) as cm:
                        aud.read_regular_bytes_capped(nested)
                    self.assertEqual(cm.exception.code, "FILE_READ_ERROR")

                with mock.patch.object(aud.os, "mkdir", side_effect=OSError(aud.errno.ENOSPC, "nospc")):
                    with self.assertRaises(orc.RaplLandauerError) as cm:
                        aud.write_regular_bytes_safe(root / "mk_fail" / "x.json", b"a")
                    self.assertEqual(cm.exception.code, "FILE_WRITE_ERROR")
                    self.assertIn("mkdir failed", cm.exception.message)
                reopen_calls = {"n": 0}
                def _fail_reopen(path_arg: Any, flags: int, *a: Any, **kw: Any) -> int:
                    if path_arg == "reopen_fail" and "dir_fd" in kw:
                        reopen_calls["n"] += 1
                        if reopen_calls["n"] == 1:
                            raise FileNotFoundError(aud.errno.ENOENT, "missing")
                        raise OSError(aud.errno.EACCES, "reopen")
                    return real_open(path_arg, flags, *a, **kw)
                with mock.patch.object(aud.os, "open", side_effect=_fail_reopen):
                    with self.assertRaises(orc.RaplLandauerError) as cm:
                        aud.write_regular_bytes_safe(root / "reopen_fail" / "x.json", b"a")
                    self.assertEqual(cm.exception.code, "FILE_WRITE_ERROR")
                with mock.patch.object(aud.os, "read", side_effect=OSError(aud.errno.EIO, "read")):
                    with self.assertRaises(orc.RaplLandauerError) as cm:
                        aud.read_regular_bytes_capped(nested)
                    self.assertEqual(cm.exception.code, "FILE_READ_ERROR")
                with mock.patch.object(aud.os, "lstat", side_effect=OSError(aud.errno.EACCES, "lstat")):
                    with self.assertRaises(orc.RaplLandauerError) as cm:
                        aud.write_regular_bytes_safe(root / "lstat_fail.json", b"a")
                    self.assertEqual(cm.exception.code, "FILE_WRITE_ERROR")
                def _fail_tmp_open(path_arg: Any, flags: int, *a: Any, **kw: Any) -> int:
                    if type(path_arg) is str and path_arg.startswith(".s61."):
                        raise OSError(aud.errno.ENOSPC, "nospc")
                    return real_open(path_arg, flags, *a, **kw)
                with mock.patch.object(aud.os, "open", side_effect=_fail_tmp_open):
                    with self.assertRaises(orc.RaplLandauerError) as cm:
                        aud.write_regular_bytes_safe(root / "tmp_fail.json", b"a")
                    self.assertEqual(cm.exception.code, "FILE_WRITE_ERROR")
                    self.assertIn("create temp failed", cm.exception.message)
                def _exhaust_tmp_open(path_arg: Any, flags: int, *a: Any, **kw: Any) -> int:
                    if type(path_arg) is str and path_arg.startswith(".s61."):
                        raise FileExistsError("exists")
                    return real_open(path_arg, flags, *a, **kw)
                with mock.patch.object(aud.os, "open", side_effect=_exhaust_tmp_open):
                    with self.assertRaises(orc.RaplLandauerError) as cm:
                        aud.write_regular_bytes_safe(root / "tmp_exh.json", b"a")
                    self.assertEqual(cm.exception.code, "FILE_WRITE_ERROR")
                    self.assertIn("exhausted", cm.exception.message)
                with mock.patch.object(aud.os, "write", side_effect=OSError(aud.errno.EIO, "write")):
                    with self.assertRaises(orc.RaplLandauerError) as cm:
                        aud.write_regular_bytes_safe(root / "wr_fail.json", b"a")
                    self.assertEqual(cm.exception.code, "FILE_WRITE_ERROR")
                with mock.patch.object(aud.os, "write", return_value=0):
                    with self.assertRaises(orc.RaplLandauerError) as cm:
                        aud.write_regular_bytes_safe(root / "wr_zero.json", b"a")
                    self.assertEqual(cm.exception.code, "FILE_WRITE_ERROR")
                with mock.patch.object(aud.os, "replace", side_effect=OSError(aud.errno.EXDEV, "replace")):
                    with self.assertRaises(orc.RaplLandauerError) as cm:
                        aud.write_regular_bytes_safe(root / "rep_fail.json", b"a")
                    self.assertEqual(cm.exception.code, "FILE_WRITE_ERROR")

                doomed = root / "doomed_cwd"
                doomed.mkdir()
                os.chdir(doomed)
                doomed.rmdir()
                eb = io.StringIO()
                with redirect_stderr(eb):
                    rc = aud.main(["--check", "rel.json", "--json"])
                self.assertEqual(rc, 2)
                self.assertEqual(json.loads(eb.getvalue())["error_code"], "CWD_UNAVAILABLE")
            finally:
                os.chdir(orig_cwd)

    def test_darwin_prefix_and_concurrency_races(self) -> None:
        root_lnk = SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_uid=0)
        root_dir = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
        user_lnk = SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_uid=1000)

        def _fake_rl(p: str) -> str:
            return {"/var": "private/var", "/tmp": "/private/tmp", "/etc": "private/etc"}[p]

        with (
            mock.patch.object(aud.sys, "platform", "darwin"),
            mock.patch.object(aud.os, "lstat", return_value=root_lnk),
            mock.patch.object(aud.os, "readlink", side_effect=_fake_rl),
        ):
            self.assertEqual(aud._normalize_darwin_system_prefix(Path("/var/x/c.json")), Path("/private/var/x/c.json"))
            self.assertEqual(aud._normalize_darwin_system_prefix(Path("/tmp/c.json")), Path("/private/tmp/c.json"))
            self.assertEqual(aud._normalize_darwin_system_prefix(Path("/etc/hosts")), Path("/private/etc/hosts"))
            self.assertEqual(aud._normalize_darwin_system_prefix(Path("/tmp")), Path("/tmp"))
            self.assertEqual(aud._normalize_darwin_system_prefix(Path("/tmp"), allow_exact=True), Path("/private/tmp"))
            self.assertEqual(aud._normalize_darwin_system_prefix(Path("rel/tmp/c.json")), Path("rel/tmp/c.json"))
            self.assertEqual(aud._normalize_darwin_system_prefix(Path("/tmp/../etc/a")), Path("/tmp/../etc/a"))
            self.assertEqual(aud._normalize_darwin_system_prefix(Path("/usr/bin")), Path("/usr/bin"))

        with (
            mock.patch.object(aud.sys, "platform", "linux"),
            mock.patch.object(aud.os, "lstat", return_value=root_lnk),
            mock.patch.object(aud.os, "readlink", side_effect=_fake_rl),
        ):
            self.assertEqual(aud._normalize_darwin_system_prefix(Path("/tmp/c.json")), Path("/tmp/c.json"))

        for st_obj, rl_val in ((root_dir, "/private/tmp"), (user_lnk, "/private/tmp"), (root_lnk, "private/evil")):
            with (
                mock.patch.object(aud.sys, "platform", "darwin"),
                mock.patch.object(aud.os, "lstat", return_value=st_obj),
                mock.patch.object(aud.os, "readlink", return_value=rl_val),
            ):
                self.assertEqual(aud._normalize_darwin_system_prefix(Path("/tmp/c.json")), Path("/tmp/c.json"))
        with (
            mock.patch.object(aud.sys, "platform", "darwin"),
            mock.patch.object(aud.os, "lstat", side_effect=OSError("enoent")),
        ):
            self.assertEqual(aud._normalize_darwin_system_prefix(Path("/tmp/c.json")), Path("/tmp/c.json"))

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            errs: list[Exception] = []
            def _w(idx: int) -> None:
                try:
                    aud.write_regular_bytes_safe(root / f"f_{idx % 4}.json", f'{{"id":{idx}}}\n'.encode("ascii"))
                except Exception as exc:  # pragma: no cover
                    errs.append(exc)
            ts = [threading.Thread(target=_w, args=(i,)) for i in range(16)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            self.assertEqual(errs, [])
            self.assertEqual([p.name for p in root.iterdir() if p.name.endswith(".tmp")], [])

            if sys.platform == "linux":
                try:
                    libc = ctypes.CDLL("libc.so.6", use_errno=True)
                except OSError:
                    libc = None
                if libc is not None and hasattr(libc, "syscall"):
                    out_d = root / "outside"
                    out_d.mkdir()
                    canary = out_d / "t.json"
                    canary.write_bytes(b"CANARY\n")
                    slot = root / "slot"
                    slot.mkdir()
                    (slot / "t.json").write_bytes(b"LEGIT\n")
                    sym = root / "sym_sw"
                    sym.symlink_to(out_d)
                    stop = threading.Event()
                    b1, b2 = os.fsencode(slot), os.fsencode(sym)
                    def _sw() -> None:
                        while not stop.is_set():
                            libc.syscall(316, -100, b1, -100, b2, 2)
                    th = threading.Thread(target=_sw, daemon=True)
                    th.start()
                    leaks = clobbers = 0
                    try:
                        for _ in range(250):
                            try:
                                if aud.read_regular_bytes_capped(slot / "t.json") != b"LEGIT\n":
                                    leaks += 1
                            except orc.RaplLandauerError:
                                pass
                            try:
                                aud.write_regular_bytes_safe(slot / "t.json", b"LEGIT\n")
                            except orc.RaplLandauerError:
                                pass
                            if canary.read_bytes() != b"CANARY\n":
                                clobbers += 1
                    finally:
                        stop.set()
                        th.join(timeout=2)
                    self.assertEqual(leaks, 0)
                    self.assertEqual(clobbers, 0)

    def test_cli_modes_and_live_frozen_silicon_certificate(self) -> None:
        snap = _make_mini_snapshot(3)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            sp = root / "mini_snap.json"
            c1 = root / "c1.json"
            c2 = root / "c2.json"
            aud.write_regular_bytes_safe(sp, orc.canonical_json_bytes(snap), "snap")

            out_s = io.StringIO()
            with redirect_stdout(out_s):
                self.assertEqual(aud.main(["--standalone", "--snapshot", str(sp), "--json"]), 0)
            st_b = out_s.getvalue().encode("ascii")

            out_w1 = io.StringIO()
            with redirect_stdout(out_w1):
                self.assertEqual(aud.main(["--write", str(c1), "--snapshot", str(sp), "--json"]), 0)
            self.assertEqual(c1.read_bytes(), st_b)

            out_w2 = io.StringIO()
            with redirect_stdout(out_w2):
                self.assertEqual(aud.main([f"--write={c2}", f"--snapshot={sp}"]), 0)
            self.assertIn("WROTE ", out_w2.getvalue())

            out_c1 = io.StringIO()
            with redirect_stdout(out_c1):
                self.assertEqual(aud.main(["--check", str(c1), "--snapshot", str(sp), "--json"]), 0)
            self.assertTrue(json.loads(out_c1.getvalue())["valid"])

            out_c2 = io.StringIO()
            with redirect_stdout(out_c2):
                self.assertEqual(aud.main([f"--check={c2}", f"--snapshot={sp}"]), 0)
            self.assertIn("OK ", out_c2.getvalue())

            self.assertEqual(aud._parse_cli_args([])["mode"], "default")
            for bad_nul_argv in (["--write", "a\x00b"], ["--check", "a\x00b"], ["--snapshot", "a\x00b"]):
                with self.assertRaises(orc.RaplLandauerError) as cm_nul:
                    aud._parse_cli_args(bad_nul_argv)
                self.assertEqual(cm_nul.exception.code, "NUL_BYTE_FORBIDDEN")
            for bad_argv, code in (
                ("bad", "INVALID_ARGV"),
                ([123], "INVALID_STR"),
                (["\ud800"], "INVALID_UTF8_SURROGATE"),
                (["a\x00b"], "NUL_BYTE_FORBIDDEN"),
                (["--json", "--json"], "DUPLICATE_FLAG"),
                (["--standalone", "--standalone"], "CONFLICTING_MODE"),
                (["--standalone", "--check", str(c1)], "CONFLICTING_MODE"),
                (["--standalone", f"--check={c1}"], "CONFLICTING_MODE"),
                (["--check"], "MISSING_PATH_ARG"),
                (["--write"], "MISSING_PATH_ARG"),
                (["--snapshot"], "MISSING_PATH_ARG"),
                (["--check", ""], "INVALID_PATH_ARG"),
                (["--check", "a\x00b"], "NUL_BYTE_FORBIDDEN"),
                (["--write", "a\x00b"], "NUL_BYTE_FORBIDDEN"),
                (["--check", "--json"], "INVALID_PATH_ARG"),
                (["--write", "--json"], "INVALID_PATH_ARG"),
                (["--check="], "INVALID_PATH_ARG"),
                (["--check=--json"], "INVALID_PATH_ARG"),
                (["--write=--json"], "INVALID_PATH_ARG"),
                (["--snapshot", ""], "INVALID_PATH_ARG"),
                (["--snapshot", "a\x00b"], "NUL_BYTE_FORBIDDEN"),
                (["--snapshot", "--json"], "INVALID_PATH_ARG"),
                (["--snapshot="], "INVALID_PATH_ARG"),
                (["--snapshot=--json"], "INVALID_PATH_ARG"),
                (["--snapshot", str(sp), "--snapshot", str(sp)], "DUPLICATE_FLAG"),
                (["--snapshot", str(sp), f"--snapshot={sp}"], "DUPLICATE_FLAG"),
                (["--bogus"], "UNKNOWN_FLAG"),
            ):
                eb = io.StringIO()
                with redirect_stderr(eb):
                    rc = aud.main(bad_argv)  # type: ignore[arg-type]
                self.assertEqual(rc, 2)
                self.assertEqual(json.loads(eb.getvalue())["error_code"], code)
            self.assertFalse((root / "--json").exists())

        # Default-snapshot CLI modes via fast mini snapshot + real live silicon certificate full replay
        with mock.patch.object(aud, "_load_default_snapshot_and_receipt", return_value=(snap, "b" * 64)):
            out_def = io.StringIO()
            with redirect_stdout(out_def):
                self.assertEqual(aud.main([]), 0)
            self.assertIn("OK ", out_def.getvalue())
            out_dj = io.StringIO()
            with redirect_stdout(out_dj):
                self.assertEqual(aud.main(["--json"]), 0)
            self.assertTrue(json.loads(out_dj.getvalue())["valid"])
            out_ls = io.StringIO()
            with redirect_stdout(out_ls):
                self.assertEqual(aud.main(["--standalone", "--json"]), 0)
            self.assertEqual(
                out_ls.getvalue().encode("ascii"),
                orc.canonical_json_bytes(orc.build_certificate_from_snapshot(snap, mlos_receipt_sha256="b" * 64)),
            )

        live_cert = _HERE / "rapl_landauer_certificate.json"
        if live_cert.is_file():
            res_live = aud.check_certificate_file(live_cert)
            self.assertTrue(res_live["valid"])
            self.assertTrue(res_live["full_replay"])


if __name__ == "__main__":
    unittest.main()
