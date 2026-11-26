#!/usr/bin/env python3
"""Adversarial R5 & full mutation-killing test suite for SO(d) geodesic retraction verifier.

Zero third-party dependencies, zero bare asserts, runs cleanly under -I -B, -I -O -B,
and -I -B -W error.
"""
from __future__ import annotations

import ast
import copy
from fractions import Fraction
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

STUDY_DIR = Path(__file__).resolve().parent
if str(STUDY_DIR) not in sys.path:
    sys.path.insert(0, str(STUDY_DIR))

import verify_so_d_geodesic_retraction as ver


def _resign_results(doc: dict) -> dict:
    body = {k: v for k, v in doc.items() if k != "result_sha256"}
    out = dict(body)
    out["result_sha256"] = ver.sha256_hex(ver.canonical_json_bytes(body))
    return out


def _resign_det(doc: dict) -> dict:
    body = {k: v for k, v in doc.items() if k != "receipt_sha256"}
    out = dict(body)
    out["receipt_sha256"] = ver.sha256_hex(ver.canonical_json_bytes(body))
    return out


def _resign_cert(doc: dict) -> dict:
    body = {k: v for k, v in doc.items() if k not in ("payload_sha256", "certificate_sha256")}
    p_sha = ver.sha256_hex(ver.canonical_json_bytes(body))
    out = dict(body)
    out["payload_sha256"] = p_sha
    out["certificate_sha256"] = ver.sha256_hex(ver.canonical_json_bytes(out))
    return out


def _copy_study(dst: Path) -> Path:
    for fn in (
        "preregistration_phase1_binary_gate.md",
        "preregistration_phase2_geodesic_retraction.md",
        "phase1_hardware_determinism.json",
        "phase2_hardware_determinism.json",
        "phase1_binary_gate_results.json",
        "phase2_geodesic_retraction_results.json",
        "so_d_geodesic_retraction_certificate.json",
    ):
        shutil.copy2(STUDY_DIR / fn, dst / fn)
    return dst


class TestSoDGeodesicRetractionR5(unittest.TestCase):
    def assertRaisesCode(self, expected_code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(ver.StudyVerifyError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, expected_code)

    def test_01_ast_no_bare_asserts_oracle_purity_and_live_cert_check(self) -> None:
        src = (STUDY_DIR / "verify_so_d_geodesic_retraction.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        self.assertEqual([n for n in ast.walk(tree) if isinstance(n, ast.Assert)], [])
        ast_audit = ver.verify_oracle_ast_purity(src)
        self.assertEqual(ast_audit["ast_div"], 0)
        self.assertEqual(ast_audit["oracle_functions_checked"], len(ver.ORACLE_FUNC_NAMES))

        # Negative pure-Q AST oracle fixtures (incl. DELTA2 SyntaxError, dunder __pow__/__float__/__truediv__, aliasing)
        stub_header = "\n".join(f"def {fn}():\n    return 0\n" for fn in ver.ORACLE_FUNC_NAMES[:-1])
        self.assertRaisesCode("AST_SYNTAX_ERROR", ver.verify_oracle_ast_purity, "def (\n")
        self.assertRaisesCode("AST_BARE_ASSERT", ver.verify_oracle_ast_purity, "assert True\n")
        self.assertRaisesCode("ORACLE_FUNC_MISSING", ver.verify_oracle_ast_purity, stub_header)
        for body_line, err_code in (
            ("    return 1 / 2\n", "ORACLE_AST_DIV"),
            ("    from math import sqrt\n    return sqrt(2)\n", "ORACLE_AST_IMPORT"),
            ("    import math\n    return 0\n", "ORACLE_AST_IMPORT"),
            ("    return 1.5\n", "ORACLE_AST_FLOAT"),
            ("    return 1j\n", "ORACLE_AST_FLOAT"),
            ("    return 2 ** -1\n", "ORACLE_AST_POW"),
            ("    return 2 ** (0 - 1)\n", "ORACLE_AST_POW"),
            ("    x = 2\n    x **= 2\n    return x\n", "ORACLE_AST_POW"),
            ("    return Fraction.from_float(1)\n", "ORACLE_AST_ATTR"),
            ("    return (2).__pow__(-1)\n", "ORACLE_AST_ATTR"),
            ("    return (-1).__rpow__(2)\n", "ORACLE_AST_ATTR"),
            ("    return (1).__truediv__(2)\n", "ORACLE_AST_ATTR"),
            ("    return (1).__float__()\n", "ORACLE_AST_ATTR"),
            ("    return (1).__getattribute__('real')\n", "ORACLE_AST_ATTR"),
            ("    return math.sqrt(2)\n", "ORACLE_AST_MATH"),
            ("    m = math\n    return m\n", "ORACLE_AST_MATH"),
            ("    return float(1)\n", "ORACLE_AST_CALL"),
            ("    f = float\n    return f(1)\n", "ORACLE_AST_CALL"),
            ("    return pow(2, -1)\n", "ORACLE_AST_CALL"),
            ("    return getattr(x, 'y')\n", "ORACLE_AST_CALL"),
            ("    return vars(x)\n", "ORACLE_AST_CALL"),
            ("    return __builtins__\n", "ORACLE_AST_CALL"),
            ("    F = Fraction\n    return F('0.5')\n", "ORACLE_AST_FRAC_ALIAS"),
            ("    F: object = Fraction\n    return F('0.5')\n", "ORACLE_AST_FRAC_ALIAS"),
            ("    return Fraction('1/2')\n", "ORACLE_AST_FRAC_STR"),
            ("    return Fraction('1' + '/2')\n", "ORACLE_AST_FRAC_STR"),
            ("    return Fraction(f'{a}/2')\n", "ORACLE_AST_FRAC_STR"),
            ("    return Fraction(numerator=1)\n", "ORACLE_AST_FRAC_KW"),
            ("    return Fraction()\n", "ORACLE_AST_FRAC_ARITY"),
            ("    return (1).__init__()\n", "ORACLE_AST_ATTR"),
            ("    return _UNDECLARED_GLOBAL\n", "ORACLE_AST_FREE_VAR"),
        ):
            bad_src = f"{stub_header}\ndef {ver.ORACLE_FUNC_NAMES[-1]}():\n{body_line}"
            self.assertRaisesCode(err_code, ver.verify_oracle_ast_purity, bad_src)

        # Exact 5 DELTA3 live-repro probes appended directly to full verifier source
        for live_snippet, err_code in (
            ("import operator\nx = operator.truediv(1, 2)\n", "ORACLE_AST_IMPORT"),
            ("(f_,) = (Fraction,)\nx = f_('0.5')\n", "ORACLE_AST_FRAC_ALIAS"),
            ("def g():\n    return (f_ := Fraction)('0.5')\n", "ORACLE_AST_FRAC_ALIAS"),
            ("x = 1 // 2\n", "ORACLE_AST_FLOORDIV"),
            ("x = f'{1:.3f}'\n", "ORACLE_AST_FORMAT_SPEC"),
        ):
            self.assertRaisesCode(err_code, ver.verify_oracle_ast_purity, src + "\n" + live_snippet)

        # Whole-file AST escape probes against compact full-oracle fixture
        full_stub = f"from fractions import Fraction\n{stub_header}\ndef {ver.ORACLE_FUNC_NAMES[-1]}():\n    return 0\n"
        for appended_snippet, err_code in (
            ("import math as m\n", "ORACLE_AST_IMPORT"),
            ("from fractions import Decimal\n", "ORACLE_AST_IMPORT"),
            ("from fractions import Fraction as F\n", "ORACLE_AST_IMPORT"),
            ("from . import helper\n", "ORACLE_AST_IMPORT"),
            ("x = a.truediv(1, 2)\n", "ORACLE_AST_ATTR"),
            ("x = a.__subclasses__()\n", "ORACLE_AST_ATTR"),
            ("x = Fraction(1, 2).__class__('1.5')\n", "ORACLE_AST_ATTR"),
            ("x = type(Fraction(1, 1))('1.5')\n", "ORACLE_AST_CALL"),
            ("x = (lambda v: v)('1.5')\n", "ORACLE_AST_CALL"),
            ("x = fractions.Fraction(1, 2)\n", "ORACLE_AST_FRAC_ALIAS"),
            ("x = [Fraction][0]('0.5')\n", "ORACLE_AST_FRAC_ALIAS"),
            ("x = isinstance(Fraction, object)\n", "ORACLE_AST_FRAC_ALIAS"),
            ("x = (1 is Fraction)\n", "ORACLE_AST_FRAC_ALIAS"),
            ("def g(Fraction):\n    return 0\n", "ORACLE_AST_FRAC_ALIAS"),
            ("class Fraction:\n    pass\n", "ORACLE_AST_FRAC_ALIAS"),
            ("x = a @ b\n", "ORACLE_AST_FLOORDIV"),
            ("x = '%f' % 1\n", "ORACLE_AST_FLOORDIV"),
            ("async def g():\n    return 0\n", "ORACLE_AST_ASYNC"),
            ("q_div = 0\n", "ORACLE_AST_REBIND"),
            ("del q_div\n", "ORACLE_AST_REBIND"),
            ("def q_div():\n    return 0\n", "ORACLE_AST_REBIND"),
        ):
            self.assertRaisesCode(err_code, ver.verify_oracle_ast_purity, full_stub + appended_snippet)

        # Nested class method for a non-duplicate oracle name (kills M066 id(node) in top_func_ids)
        self.assertRaisesCode(
            "ORACLE_AST_REBIND",
            ver.verify_oracle_ast_purity,
            f"{stub_header}\nclass C:\n    def {ver.ORACLE_FUNC_NAMES[-1]}(self):\n        return 0\n",
        )

        # Decorator on oracle function & impure require_ok helper checks
        self.assertRaisesCode(
            "ORACLE_AST_DECORATOR",
            ver.verify_oracle_ast_purity,
            f"{stub_header}\n@dec\ndef {ver.ORACLE_FUNC_NAMES[-1]}():\n    return 0\n",
        )
        self.assertRaisesCode(
            "ORACLE_AST_DIV",
            ver.verify_oracle_ast_purity,
            f"{stub_header}\ndef {ver.ORACLE_FUNC_NAMES[-1]}():\n    return 0\ndef require_ok():\n    return 1 / 2\n",
        )
        self.assertRaisesCode(
            "ORACLE_AST_FREE_VAR",
            ver.verify_oracle_ast_purity,
            f"_HALF = 1\n{stub_header}\ndef {ver.ORACLE_FUNC_NAMES[-1]}():\n    return _HALF\n",
        )

        cert = ver.verify_certificate_file(
            STUDY_DIR / "so_d_geodesic_retraction_certificate.json", STUDY_DIR, require_pinned=True
        )
        self.assertEqual(cert["status"], "PASS")
        self.assertEqual(cert["phase1_binary_gate_prerequisite"]["verdict"], "FALSIFIED")
        self.assertEqual(cert["phase2_geodesic_retraction"]["verdict"], "CONFIRMED")
        self.assertEqual(cert["phase2_geodesic_retraction"]["unseen_fresh_seeds_summary"]["fresh_seed_ids"], [3, 4])

        # q_div guards
        self.assertEqual(ver.q_div(Fraction(3, 4), Fraction(2, 5)), Fraction(15, 8))
        self.assertRaisesCode("QDIV_TYPE", ver.q_div, 1, Fraction(1, 2))
        self.assertRaisesCode("QDIV_TYPE", ver.q_div, Fraction(1, 2), 1)
        self.assertRaisesCode("QDIV_ZERO", ver.q_div, Fraction(1, 2), Fraction(0, 1))

    def test_02_energy_claim_guard_and_tree_scan(self) -> None:
        bad_vals = [
            "45.2 W", "45W", "45.2 W.", "45.2W!", "W?", "[W]", "45.2\u00d7W", "45.2-W",
            "45.2 [W]", "W: 45.2", "W=45.2", "45.2 kilowatts", "45.2\u200bW", "45.2 k\u200bW",
            "5 GW", "5 TW", "5 pW", "5 kilo watts", "5 kilo-watts", "5 m W", "15 watthours",
            "15 watt hours", "15 watt-hour", "5\u2013W", "12\u00b7W", "3.9e2 W", "1.5E-3W",
            "0.5 kWh", "1.2 J/tok", "joules per token", "MJ per token", "mJ/tok", "15 TDP",
            "TDP 15", "TDP", "70% less energy", "70 percent less power", "energy use dropped",
            "power savings", "5 \u051d", "\u0435nergy", "3 \u043a\u0412\u0442", "\uff11\uff12\uff37",
            "45 milliwatts", "1.2 megawatts", "12.5 kilojoules", "W: 45.2 drain", "45.2[W] drain",
            "J: 5", "cap_45_w", "45_watts", "limit_45_w", "draw_45w", "45 Whr", "130w_psu",
            "max_45w", "45w", "5 PW", "45.2 \u03c9", "\u051datt", "45.2\u2219W",
            "fifty watts", "5 Ws", "W 45", "wattage", "J 12", "kW 45.2",
            "measured with RAPL", "nvml power", "nvidia-smi draw", "10 tok/J", "5000 mAh",
            "J/token", "W/tok", "nvml_power", "mah_consumed", "energy_per_token",
            "nvmlDeviceGetTotalEnergyConsumption", "rapl_pkg_uj", "tok_per_mwh", "power_draw",
            "energy: 12", "energy = 12", "power = 45", "power: 45.2", "forty-five watts",
            "forty-five wh", "100 W/ token", "100 W/ s", "wattage: 45", "power 45",
            "2.25 A at 20 V", "20 V @ 2.25 A",
        ]
        good_vals = [
            "5 ms", "latency 12", "70 C", "78\u00b0C", "70/78/85 C knees", "5 C deadband",
            "5 deg C deadband", "135/2", "45.0%", "0.5 mm", "ac", "battery", "unknown", "temp_c",
            "gpu_temp_exceeded", "UNCONTROLLED_LAPTOP_NOT_CLAIMED", "grad_W_q",
            "stdlib_sha256_chain", "cpu_jiffies_total", "a" * 64, "129,279.00 tok/s",
            "469.41 us/tok", "8.113 MiB", "sm_86", "W10-OBS-61", "wmma", "window 20", "warp 32",
            "16 warps/SM", "h256", "rows 1024", "tdp_like_free_text_no", "W13-OBS-BVDECIDE",
            "J2000 epoch-like", "J2000.0", "worker W10", "2024-W05", "sprint-W12", "node-w10",
            "q4-w3", "W-2", "W12", "kW12", "bench w/ perf counters", "taskset -c 3 w/ 5 reps",
            "12 ms/tok", "sm_clock 2100 MHz", "0.9 V", "1024 MiB/s", "not_on_ac_power",
            "3 w/o pinning", "j = 3", "w = 3", "i = 0, j = 3", "w/ tokens", "empowerment_score",
        ]
        self.assertFalse(ver.is_forbidden_energy_key("empowerment_score"))
        for b in bad_vals:
            self.assertTrue(ver.is_forbidden_energy_value(b), f"Missed bad energy payload: {b!r}")
        for g in good_vals:
            self.assertFalse(ver.is_forbidden_energy_value(g), f"False positive on good value: {g!r}")

        # Linear-time ReDoS regression guard (process CPU time, immune to host wall-clock load)
        t0 = time.process_time()
        self.assertFalse(ver.is_forbidden_energy_key("1" + "." * 8000 + "x"))
        self.assertFalse(ver.is_forbidden_energy_value("1" + "." * 8000 + "x"))
        self.assertFalse(ver.is_forbidden_energy_value("1" + "," * 8000 + "x"))
        self.assertFalse(ver.is_forbidden_energy_value("1." * 4000))
        self.assertLess(time.process_time() - t0, 0.50)

        self.assertRaisesCode("BAD_POLICY_STR", ver.is_forbidden_energy_value, 123)
        self.assertRaisesCode("BAD_POLICY_KEY", ver.is_forbidden_energy_key, 123)
        self.assertFalse(ver.is_forbidden_energy_key("energy_power_status"))
        for bad_k in ("power_draw_w", "avgPower", "powerMw", "totalEnergy", "pkg_w", "po\u0301wer", "\u0435nergy_k"):
            self.assertTrue(ver.is_forbidden_energy_key(bad_k), f"Missed bad key: {bad_k!r}")

        # Depth boundary & tree scan guards
        self.assertRaisesCode("BAD_MAX_DEPTH", ver.scan_json_tree_clean, {}, max_depth=0)
        self.assertRaisesCode("BAD_MAX_DEPTH", ver.scan_json_tree_clean, {}, max_depth=None)
        nested: object = 1
        for _ in range(ver.MAX_JSON_DEPTH):
            nested = [nested]
        ver.scan_json_tree_clean(nested)
        self.assertRaisesCode("JSON_DEPTH", ver.scan_json_tree_clean, [nested])
        self.assertRaisesCode("NONFINITE_FLOAT", ver.scan_json_tree_clean, {"x": float("nan")})
        self.assertRaisesCode("NONFINITE_FLOAT", ver.scan_json_tree_clean, {"x": float("inf")})
        self.assertRaisesCode("PATH_LEAK", ver.scan_json_tree_clean, {"x": "/" + "home" + "/alice"})
        self.assertRaisesCode("PATH_LEAK", ver.scan_json_tree_clean, {"/" + "home" + "/k": 1})
        self.assertRaisesCode("ENERGY_CLAIM_VALUE", ver.scan_json_tree_clean, {"note": "45.2 W."})
        self.assertRaisesCode("ENERGY_CLAIM_KEY", ver.scan_json_tree_clean, {"avgPower": 1})
        self.assertRaisesCode("ALLOWLIST_SMUGGLE", ver.scan_json_tree_clean, {"energy_power_status": 45.2})
        self.assertRaisesCode("ALLOWLIST_SMUGGLE", ver.scan_json_tree_clean, {"energy_power_status": "other"})
        self.assertRaisesCode("ENERGY_CLAIM_VALUE", ver.scan_json_tree_clean, {"energy_power_status": "45.2 W"})
        self.assertRaisesCode("BAD_KEY", ver.scan_json_tree_clean, {1: "a"})
        self.assertRaisesCode("BAD_JSON_TYPE", ver.scan_json_tree_clean, {"a": (1, 2)})

    def test_03_exact_q_cayley_oracle_and_negative_controls(self) -> None:
        z = Fraction(0, 1)
        s2 = [[z, Fraction(1, 2)], [Fraction(-1, 2), z]]
        q2 = ver.cayley_transform_q(s2, Fraction(1, 1))
        self.assertEqual(ver._mat_det_q(q2), Fraction(1, 1))
        # Singular determinant path
        self.assertEqual(ver._mat_det_q([[z, z], [z, z]]), z)
        # Pivot swap determinant sign flip
        self.assertEqual(ver._mat_det_q([[z, Fraction(1, 1)], [Fraction(1, 1), z]]), Fraction(-1, 1))
        # Pivot swap in _mat_inv_q & singular matrix rejection
        inv_swap = ver._mat_inv_q([[z, Fraction(1, 1)], [Fraction(1, 1), z]])
        self.assertEqual(inv_swap, [[z, Fraction(1, 1)], [Fraction(1, 1), z]])
        self.assertRaisesCode("SINGULAR_MATRIX", ver._mat_inv_q, [[z, z], [z, z]])

        # Bad skew inputs
        self.assertRaisesCode("BAD_SKEW_SHAPE", ver.cayley_transform_q, None, Fraction(1, 1))
        self.assertRaisesCode("BAD_SKEW_SHAPE", ver.cayley_transform_q, [[z]], Fraction(1, 1))
        self.assertRaisesCode("BAD_SKEW_SHAPE", ver.cayley_transform_q, [[z, z], [z]], Fraction(1, 1))
        self.assertRaisesCode("BAD_GAMMA", ver.cayley_transform_q, s2, 0.5)
        self.assertRaisesCode("NOT_SKEW_DIAG", ver.cayley_transform_q, [[Fraction(1, 1), z], [z, z]], Fraction(1, 1))
        self.assertRaisesCode("NOT_SKEW_SYM", ver.cayley_transform_q, [[z, Fraction(1, 1)], [Fraction(1, 1), z]], Fraction(1, 1))

        # Oracle invariant negative controls (orth, det, norm, flow, contraction bound, monotonicity)
        px = [Fraction(1, 1), Fraction(2, 1)]
        fu = ([Fraction(3, 1), z],)
        self.assertRaisesCode("ORACLE_FLOW_DRIFT", ver.verify_cayley_geodesic_ladder, s2, px, fu, (Fraction(1, 1),))
        self.assertRaisesCode(
            "ORACLE_NOT_MONOTONE",
            ver.verify_cayley_geodesic_ladder,
            [[z, z, z], [z, z, Fraction(1, 2)], [z, Fraction(-1, 2), z]],
            [Fraction(1, 1), Fraction(2, 1), Fraction(3, 1)],
            ([Fraction(5, 1), z, z],),
            (Fraction(1, 2), Fraction(1, 1)),
        )
        with mock.patch.object(ver, "cayley_transform_q", return_value=[[Fraction(2, 1), z], [z, Fraction(1, 1)]]):
            self.assertRaisesCode("ORACLE_NOT_ORTH", ver.verify_cayley_geodesic_ladder, s2, px, fu, (Fraction(1, 1),))
        # Orthogonal reflection diag(-1, 1) -> passes orth, fails det == 1
        with mock.patch.object(ver, "cayley_transform_q", return_value=[[Fraction(-1, 1), z], [z, Fraction(1, 1)]]):
            self.assertRaisesCode("ORACLE_DET_BAD", ver.verify_cayley_geodesic_ladder, s2, px, fu, (Fraction(1, 1),))
        # Mocked _mat_mul_q returning identity + det 1 with scaled q -> fails ORACLE_NORM_DRIFT
        with mock.patch.object(ver, "cayley_transform_q", return_value=[[Fraction(2, 1), z], [z, Fraction(1, 2)]]), \
             mock.patch.object(ver, "_mat_mul_q", return_value=[[Fraction(1, 1), z], [z, Fraction(1, 1)]]):
            self.assertRaisesCode("ORACLE_NORM_DRIFT", ver.verify_cayley_geodesic_ladder, s2, [Fraction(1, 1), Fraction(1, 1)], fu, (Fraction(1, 1),))
        # Zero skew matrix: exact equality frob_sq == 0 == contraction_bound_sq passes <= and kills <
        s2_zero = [[z, z], [z, z]]
        ver.verify_cayley_geodesic_ladder(s2_zero, px, ([z, z],), (Fraction(1, 1),))
        # Zero skew matrix with 180-deg rotation -I in SO(2): passes orth/det/norm/flow(0), violates ||Q-I||_F^2 <= 4 g^2 ||S||_F^2 = 0
        with mock.patch.object(ver, "cayley_transform_q", return_value=[[Fraction(-1, 1), z], [z, Fraction(-1, 1)]]):
            self.assertRaisesCode("ORACLE_CONTRACTION_BOUND", ver.verify_cayley_geodesic_ladder, s2_zero, px, ([z, z],), (Fraction(1, 1),))

    def test_04_spinor_stats_and_json_helpers(self) -> None:
        unit_hex = struct.pack("<4f", 1.0, 0.0, 0.0, 0.0).hex()
        self.assertEqual(ver.verify_pi16_hex(unit_hex), (1.0, 0.0, 0.0, 0.0))
        self.assertRaisesCode("PI16_HEX_LEN", ver.verify_pi16_hex, "00")
        self.assertRaisesCode("PI16_HEX_LEN", ver.verify_pi16_hex, 123)
        self.assertRaisesCode("PI16_HEX_BAD", ver.verify_pi16_hex, "z" * 32)
        self.assertRaisesCode("PI16_NONFINITE", ver.verify_pi16_hex, struct.pack("<4f", float("nan"), 0.0, 0.0, 0.0).hex())
        self.assertRaisesCode("PI16_NOT_UNIT", ver.verify_pi16_hex, struct.pack("<4f", 2.0, 0.0, 0.0, 0.0).hex())

        # Exact IEEE-754 dyadic tolerance boundary (1.0^2 + 0.03125^2 == 1.0 + 1/1024 == 1.0 + UNIT_SPINOR_N2_TOL)
        ver.verify_pi16_hex(struct.pack("<4f", 1.0, 0.03125, 0.0, 0.0).hex())

        # paired_t_df2 & paired_t_df4 reject zero-variance degenerate samples & bad lengths
        self.assertRaisesCode("STATS_ZERO_VAR", ver.paired_t_df2, [1.0, 1.0, 1.0], [1.0, 1.0, 1.0])
        self.assertRaisesCode("STATS_ZERO_VAR", ver.paired_t_df2, [2.0, 2.0, 2.0], [1.0, 1.0, 1.0])
        self.assertRaisesCode("STATS_ZERO_VAR", ver.paired_t_df2, [1e200, 0.0, 0.0], [0.0, 0.0, 0.0])
        self.assertRaisesCode("STATS_DF2_LEN", ver.paired_t_df2, [1.0, 2.0], [1.0, 2.0])
        self.assertRaisesCode("STATS_DF2_LEN", ver.paired_t_df2, None, [1.0, 2.0, 3.0])

        self.assertRaisesCode("STATS_ZERO_VAR", ver.paired_t_df4, [1.0] * 5, [1.0] * 5)
        self.assertRaisesCode("STATS_ZERO_VAR", ver.paired_t_df4, [2.0] * 5, [1.0] * 5)
        self.assertRaisesCode("STATS_ZERO_VAR", ver.paired_t_df4, [1e200, 0.0, 0.0, 0.0, 0.0], [0.0] * 5)
        self.assertRaisesCode("STATS_DF4_LEN", ver.paired_t_df4, [1.0] * 4, [1.0] * 4)
        self.assertRaisesCode("STATS_DF4_LEN", ver.paired_t_df4, None, [1.0] * 5)

        # Preregistration threshold parser refusal & boundary controls (missing, ambiguous, nonfinite, range, poison)
        valid_pr = (STUDY_DIR / "preregistration_phase2_geodesic_retraction.md").read_text(encoding="utf-8")
        self.assertRaisesCode("PREREG_PARSE_FAIL", ver.parse_prereg_thresholds, valid_pr.replace("2.0x", "MISSING"))
        self.assertRaisesCode("PREREG_PARSE_AMBIGUOUS", ver.parse_prereg_thresholds, valid_pr + "\nmean_kl_A / mean_kl_D >= 3.5x\n")
        self.assertRaisesCode("PREREG_PARSE_FAIL", ver.parse_prereg_thresholds, valid_pr.replace("`30/30`", "MISSING"))
        self.assertRaisesCode("PREREG_POISON_BAD", ver.parse_prereg_thresholds, valid_pr.replace("`30/30`", "`30/29`"))
        self.assertRaisesCode("PREREG_POISON_BAD", ver.parse_prereg_thresholds, valid_pr.replace("`30/30`", "`0/0`"))
        self.assertRaisesCode("PREREG_FLOAT_BAD", ver.parse_prereg_thresholds, valid_pr.replace("1e-5", "1..2"))
        self.assertRaisesCode("PREREG_NONFINITE", ver.parse_prereg_thresholds, valid_pr.replace("1e-5", "1e309"))
        self.assertRaisesCode("PREREG_RANGE_BAD", ver.parse_prereg_thresholds, valid_pr.replace("2.0x", "1.0x"))
        self.assertRaisesCode("PREREG_RANGE_BAD", ver.parse_prereg_thresholds, valid_pr.replace("- 2.0 pp", "- 100.1 pp"))
        self.assertRaisesCode("PREREG_RANGE_BAD", ver.parse_prereg_thresholds, valid_pr.replace("< 0.01", "< 0.0"))
        self.assertRaisesCode("PREREG_RANGE_BAD", ver.parse_prereg_thresholds, valid_pr.replace("< 0.01", "< 1.5"))
        self.assertRaisesCode("PREREG_RANGE_BAD", ver.parse_prereg_thresholds, valid_pr.replace("<= 0.005 nats", "<= 0.0 nats"))
        self.assertRaisesCode("PREREG_RANGE_BAD", ver.parse_prereg_thresholds, valid_pr.replace("4/6", "0/6"))
        self.assertRaisesCode("PREREG_RANGE_BAD", ver.parse_prereg_thresholds, valid_pr.replace("4/6", "99/6"))
        self.assertRaisesCode("PREREG_RANGE_BAD", ver.parse_prereg_thresholds, valid_pr.replace("+5.0 pp", "+0.0 pp"))
        self.assertRaisesCode("PREREG_RANGE_BAD", ver.parse_prereg_thresholds, valid_pr.replace("+5.0 pp", "+100.1 pp"))
        self.assertRaisesCode("PREREG_RANGE_BAD", ver.parse_prereg_thresholds, valid_pr.replace("1e-5", "0.0"))
        self.assertRaisesCode("PREREG_RANGE_BAD", ver.parse_prereg_thresholds, valid_pr.replace("1e-5", "1.0"))
        # Inclusive range boundary controls (kill <= vs < mutants on hold_margin_pp, p_holm_alpha, min_commits, min_gain_pp)
        self.assertEqual(ver.parse_prereg_thresholds(valid_pr.replace("- 2.0 pp", "- 0.0 pp"))["hold_margin_pp"], 0.0)
        self.assertEqual(ver.parse_prereg_thresholds(valid_pr.replace("- 2.0 pp", "- 100.0 pp"))["hold_margin_pp"], 100.0)
        self.assertEqual(ver.parse_prereg_thresholds(valid_pr.replace("< 0.01", "< 1.0"))["p_holm_alpha"], 1.0)
        self.assertEqual(ver.parse_prereg_thresholds(valid_pr.replace("4/6", "1/6"))["min_commits"], 1)
        self.assertEqual(ver.parse_prereg_thresholds(valid_pr.replace("4/6", "6/6"))["min_commits"], 6)
        self.assertEqual(ver.parse_prereg_thresholds(valid_pr.replace("+5.0 pp", "+100.0 pp"))["min_gain_pp"], 100.0)

        # holm_3 monotonic enforcement & bounds
        h_out = ver.holm_3([0.1, 0.11, 1.0])
        self.assertAlmostEqual(h_out[0], 0.3, places=8)
        self.assertAlmostEqual(h_out[1], 0.3, places=8)
        self.assertEqual(h_out[2], 1.0)
        self.assertEqual(ver.holm_3([0.0, 0.5, 1.0])[0], 0.0)
        self.assertRaisesCode("HOLM_LEN", ver.holm_3, [0.1, 0.2])
        self.assertRaisesCode("HOLM_LEN", ver.holm_3, None)
        self.assertRaisesCode("HOLM_RANGE", ver.holm_3, [-0.1, 0.2, 0.3])
        self.assertRaisesCode("HOLM_RANGE", ver.holm_3, [0.1, 1.1, 0.3])

        # Primitive strict validators (incl. 401-digit int -> float OverflowError guard)
        self.assertRaisesCode("C", ver._strict_int, True, "C", "x")
        self.assertRaisesCode("C", ver._strict_float, True, "C", "x")
        self.assertRaisesCode("C", ver._strict_float, float("inf"), "C", "x")
        self.assertRaisesCode("C", ver._strict_float, 10 ** 400, "C", "x")
        self.assertRaisesCode("C", ver._strict_hex64, "a" * 63, "C", "x")
        self.assertRaisesCode("C", ver._strict_hex64, "A" * 64, "C", "x")
        self.assertRaisesCode("FILE_MISSING", ver.file_sha256, STUDY_DIR / "does_not_exist.txt")
        self.assertRaisesCode("FILE_MISSING", ver.file_sha256, None)
        self.assertRaisesCode("IO_ERROR", ver._write_utf8_nofollow, None, "x")
        self.assertRaisesCode("BAD_STUDY_DIR", ver.build_study_certificate, None)

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            p_dup = tdp / "dup.json"
            p_dup.write_text('{"a": 1, "a": 2}', encoding="utf-8")
            self.assertRaisesCode("JSON_DUP_KEY", ver.load_strict_json, p_dup)
            p_bad = tdp / "bad.json"
            p_bad.write_text("{bad", encoding="utf-8")
            self.assertRaisesCode("JSON_PARSE_FAIL", ver.load_strict_json, p_bad)
            p_list = tdp / "list.json"
            p_list.write_text("[1, 2]", encoding="utf-8")
            self.assertRaisesCode("JSON_NOT_OBJ", ver.load_strict_json, p_list)
            self.assertRaisesCode("JSON_MISSING", ver.load_strict_json, tdp / "missing.json")

            # Non-regular (directory + FIFO), UTF-8 BOM, invalid UTF-8, MAX_FILE_BYTES, MAX_JSON_INT_DIGITS, NaN/Inf, & symlink guards
            self.assertRaisesCode("NOT_REGULAR_FILE", ver.file_sha256, tdp)
            fifo_p = tdp / "pipe.json"
            os.mkfifo(fifo_p)
            self.assertRaisesCode("NOT_REGULAR_FILE", ver.load_strict_json, fifo_p)
            p_bom = tdp / "bom.json"
            p_bom.write_bytes(b"\xef\xbb\xbf{}")
            self.assertRaisesCode("UTF8_BOM_FORBIDDEN", ver.load_strict_json, p_bom)
            p_utf8 = tdp / "bad_utf8.json"
            p_utf8.write_bytes(b"\xff\xfe")
            self.assertRaisesCode("JSON_PARSE_FAIL", ver.load_strict_json, p_utf8)

            p_max_ok = tdp / "exact_1mib.bin"
            p_max_ok.write_bytes(b"x" * 1048576)
            self.assertEqual(len(ver.file_sha256(p_max_ok)), 64)
            p_max_bad = tdp / "over_1mib.bin"
            p_max_bad.write_bytes(b"x" * 1048577)
            self.assertRaisesCode("FILE_TOO_LARGE", ver.file_sha256, p_max_bad)

            p_int_ok = tdp / "int1024.json"
            p_int_ok.write_text(f'{{"p": {"9" * 1024}, "n": -{"9" * 1024}}}', encoding="utf-8")
            self.assertEqual(ver.load_strict_json(p_int_ok)["p"], int("9" * 1024))
            for bad_num in ("9" * 1025, "-" + "9" * 1025, "9" * 4400):
                p_int_bad = tdp / "int_bad.json"
                p_int_bad.write_text(f'{{"x": {bad_num}}}', encoding="utf-8")
                self.assertRaisesCode("JSON_PARSE_FAIL", ver.load_strict_json, p_int_bad)

            for bad_const in ("NaN", "Infinity", "-Infinity"):
                p_nan = tdp / "nan.json"
                p_nan.write_text(f'{{"x": {bad_const}}}', encoding="utf-8")
                self.assertRaisesCode("NONFINITE_FLOAT", ver.load_strict_json, p_nan)

            real_j = tdp / "real.json"
            real_j.write_text('{"ok": 1}', encoding="utf-8")
            sym_j = tdp / "sym.json"
            sym_j.symlink_to(real_j)
            self.assertRaisesCode("SYMLINK_FORBIDDEN", ver.load_strict_json, sym_j)
            self.assertRaisesCode("SYMLINK_FORBIDDEN", ver.file_sha256, sym_j)
            self.assertRaisesCode("SYMLINK_FORBIDDEN", ver._write_utf8_nofollow, sym_j, "{}")
            real_sub = tdp / "real_sub"
            real_sub.mkdir()
            real_nested = real_sub / "nested.json"
            real_nested.write_text('{"ok": 1}', encoding="utf-8")
            sym_dir = tdp / "sym_dir"
            sym_dir.symlink_to(tdp)
            # Ancestor / grandparent symlink checks (kills M003 ancestor symlink guard)
            self.assertRaisesCode("SYMLINK_FORBIDDEN", ver.file_sha256, sym_dir / "real_sub" / "nested.json")
            self.assertRaisesCode("SYMLINK_FORBIDDEN", ver._write_utf8_nofollow, sym_dir / "real_sub" / "out.json", "{}")
            self.assertRaisesCode("SYMLINK_FORBIDDEN", ver.build_study_certificate, sym_dir)
            self.assertRaisesCode("SYMLINK_FORBIDDEN", ver.build_study_certificate, sym_dir / "real_sub")

            # Simulated fdopen read/write OSError checks (kills M009 guard_except_reject)
            def _fail_fdopen(fd: int, *_args: object, **_kwargs: object) -> object:
                os.close(fd)
                raise OSError("simulated io failure")

            with mock.patch.object(os, "fdopen", side_effect=_fail_fdopen):
                self.assertRaisesCode("FILE_MISSING", ver.file_sha256, real_j)
                self.assertRaisesCode("IO_ERROR", ver._write_utf8_nofollow, tdp / "w_fail.json", "{}")

    def test_05_determinism_receipt_and_phase_tamper_rejections(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            sd = _copy_study(Path(td))

            # Determinism receipt tamper suite
            det_path = sd / "phase2_hardware_determinism.json"
            orig_det = json.loads(det_path.read_text(encoding="utf-8"))
            for field, bad_val, code in (
                ("schema", "bad", "DET_SCHEMA_BAD"),
                ("energy_power_status", "CLAIMED", "ALLOWLIST_SMUGGLE"),
                ("receipt_sha256", "0" * 64, "DET_SHA_MISMATCH"),
                ("clean_hardware_run", False, "DET_NOT_CLEAN"),
                ("anomalies", ["throttle"], "DET_ANOMALIES"),
                ("determinism_zone", "A", "DET_ZONE_BAD"),
            ):
                mut = copy.deepcopy(orig_det)
                mut[field] = bad_val
                if code != "DET_SHA_MISMATCH":
                    mut = _resign_det(mut)
                det_path.write_text(json.dumps(mut), encoding="utf-8")
                self.assertRaisesCode(code, ver.verify_determinism_receipt, det_path)

            mut_exit = copy.deepcopy(orig_det)
            mut_exit["execution"]["exit_code"] = 1
            det_path.write_text(json.dumps(_resign_det(mut_exit)), encoding="utf-8")
            self.assertRaisesCode("DET_EXIT_NONZERO", ver.verify_determinism_receipt, det_path)
            # Missing energy_power_status key hits DET_ENERGY_STATUS directly
            mut_no_ep = copy.deepcopy(orig_det)
            del mut_no_ep["energy_power_status"]
            det_path.write_text(json.dumps(_resign_det(mut_no_ep)), encoding="utf-8")
            self.assertRaisesCode("DET_ENERGY_STATUS", ver.verify_determinism_receipt, det_path)
            det_path.write_text(json.dumps(orig_det), encoding="utf-8")

            # Phase 2 results tamper suite (schema, sha, bindings, editor, budget, seeds, arms, poison, gates, stats)
            r2_path = sd / "phase2_geodesic_retraction_results.json"
            orig_r2 = json.loads(r2_path.read_text(encoding="utf-8"))

            def _try_r2(mut_doc: dict, code: str, resign: bool = True) -> None:
                r2_path.write_text(json.dumps(_resign_results(mut_doc) if resign else mut_doc), encoding="utf-8")
                if code == "P2_VERDICT_UNEXPECTED":
                    self.assertRaisesCode(code, ver.build_study_certificate, sd)
                else:
                    self.assertRaisesCode(
                        code,
                        ver._verify_phase_results,
                        sd,
                        phase=2,
                        results_file="phase2_geodesic_retraction_results.json",
                        det_file="phase2_hardware_determinism.json",
                        prereg_file="preregistration_phase2_geodesic_retraction.md",
                        phase1_hold_margin_pp=1.0,
                        phase1_seed_ids=[0, 1, 2],
                    )
                r2_path.write_text(json.dumps(orig_r2), encoding="utf-8")

            d = copy.deepcopy(orig_r2); d["schema"] = "bad"; _try_r2(d, "RES_SCHEMA_BAD")
            d = copy.deepcopy(orig_r2); del d["energy_power_status"]; _try_r2(d, "RES_ENERGY_STATUS")
            d = copy.deepcopy(orig_r2); d["determinism_receipt_file"] = "other.json"; _try_r2(d, "BOUND_DET_FILE_MISMATCH")
            d = copy.deepcopy(orig_r2); d["preregistration_file"] = "other.md"; _try_r2(d, "BOUND_PREREG_FILE_MISMATCH")
            d = copy.deepcopy(orig_r2); d["result_sha256"] = "0" * 64; _try_r2(d, "RES_SHA_MISMATCH", resign=False)
            d = copy.deepcopy(orig_r2); d["determinism_receipt_sha256"] = "0" * 64; _try_r2(d, "BOUND_DET_MISMATCH")
            d = copy.deepcopy(orig_r2); d["preregistration_sha256"] = "0" * 64; _try_r2(d, "BOUND_PREREG_MISMATCH")
            d = copy.deepcopy(orig_r2); d["per_seed"][0]["arms"]["Arm_D_Cayley_FlowNull_Retract_Spinor16B"]["final_pi16_hex"] = struct.pack("<4f", 2.0, 0.0, 0.0, 0.0).hex(); _try_r2(d, "PI16_NOT_UNIT")
            d = copy.deepcopy(orig_r2); d["frozen_specialist_editor"]["editor_sha256_invariant"] = False; _try_r2(d, "EDITOR_INVARIANT_FAIL")
            d = copy.deepcopy(orig_r2); d["matched_param_budget"]["max_param_delta_pct"] = 0.5; _try_r2(d, "BUDGET_FAIL")
            d = copy.deepcopy(orig_r2); d["per_seed"] = d["per_seed"][:4]; _try_r2(d, "SEEDS_LEN")
            d = copy.deepcopy(orig_r2); d["per_seed"][0] = "bad"; _try_r2(d, "SEED_ROW_BAD")
            d = copy.deepcopy(orig_r2); d["per_seed"][1]["seed"] = d["per_seed"][0]["seed"]; _try_r2(d, "SEED_ID_DUP")
            d = copy.deepcopy(orig_r2); d["per_seed"][0]["arms"] = []; _try_r2(d, "ARMS_BAD")
            # Arm-D KL > kl_ceil_nats fails G1_MISMATCH
            d = copy.deepcopy(orig_r2); d["per_seed"][0]["arms"]["Arm_D_Cayley_FlowNull_Retract_Spinor16B"]["final_prose_kl_nats"] = 0.006; _try_r2(d, "G1_MISMATCH")
            # Missing Phase 1 context / zero fresh unseen seeds guards
            self.assertRaisesCode(
                "P1_CTX_MISSING",
                ver._verify_phase_results,
                sd,
                phase=2,
                results_file="phase2_geodesic_retraction_results.json",
                det_file="phase2_hardware_determinism.json",
                prereg_file="preregistration_phase2_geodesic_retraction.md",
            )
            self.assertRaisesCode(
                "NO_FRESH_SEEDS",
                ver._verify_phase_results,
                sd,
                phase=2,
                results_file="phase2_geodesic_retraction_results.json",
                det_file="phase2_hardware_determinism.json",
                prereg_file="preregistration_phase2_geodesic_retraction.md",
                phase1_hold_margin_pp=1.0,
                phase1_seed_ids=[0, 1, 2, 3, 4],
            )
            d = copy.deepcopy(orig_r2); del d["per_seed"][0]["arms"]["Arm_C_Cayley_Tangent_Unprojected"]; _try_r2(d, "ARMS_MISSING")
            d = copy.deepcopy(orig_r2); d["per_seed"][0]["arms"]["Arm_D_Cayley_FlowNull_Retract_Spinor16B"]["poison_rollback_audit"] = None; _try_r2(d, "POISON_MISSING")
            d = copy.deepcopy(orig_r2); d["per_seed"][0]["arms"]["Arm_D_Cayley_FlowNull_Retract_Spinor16B"]["poison_rollback_audit"]["all_weights_sha_exact"] = False; _try_r2(d, "POISON_SHA")
            d = copy.deepcopy(orig_r2); d["gates"] = None; _try_r2(d, "GATES_MISSING")
            d = copy.deepcopy(orig_r2); d["gates"]["G1_prose_kl_cure"] = False; _try_r2(d, "G1_MISMATCH")
            d = copy.deepcopy(orig_r2); d["gates"]["G2_reserve_commits_and_holdout_gain"] = False; _try_r2(d, "G2_MISMATCH")
            d = copy.deepcopy(orig_r2); d["gates"]["G3_shell_norm_and_spinor16b_rollback"] = False; _try_r2(d, "G3_MISMATCH")
            # Direct G3 sub-clause failure checks (kills recomp_g3 BoolOp and -> or)
            d = copy.deepcopy(orig_r2); d["per_seed"][0]["arms"]["Arm_D_Cayley_FlowNull_Retract_Spinor16B"]["max_shell_norm_err"] = 1e-4; _try_r2(d, "G3_MISMATCH")
            d = copy.deepcopy(orig_r2); d["per_seed"][0]["arms"]["Arm_D_Cayley_FlowNull_Retract_Spinor16B"]["poison_rollback_audit"]["attacks_blocked"] = 5; _try_r2(d, "G3_MISMATCH")
            d = copy.deepcopy(orig_r2); d["per_seed"][0]["arms"]["Arm_D_Cayley_FlowNull_Retract_Spinor16B"]["poison_rollback_audit"]["max_param_rollback_drift"] = 1e-6; _try_r2(d, "G3_MISMATCH")
            d = copy.deepcopy(orig_r2); d["gates"]["verdict"] = "PARTIAL"; _try_r2(d, "VERDICT_MISMATCH")
            d = copy.deepcopy(orig_r2); d["stats_paired_t_df4"] = None; _try_r2(d, "STATS_MISSING")
            d = copy.deepcopy(orig_r2); d["stats_paired_t_df4"]["G1_logKL_A_minus_D"] = None; _try_r2(d, "STATS_ENTRY_BAD")
            d = copy.deepcopy(orig_r2); d["stats_paired_t_df4"]["G1_logKL_A_minus_D"]["p_holm"] = 0.5; _try_r2(d, "PHOLM_G1_MISMATCH")
            d = copy.deepcopy(orig_r2); d["stats_paired_t_df4"]["G2_holdout_D_minus_Base"]["p_holm"] = 0.5; _try_r2(d, "PHOLM_G2_MISMATCH")
            d = copy.deepcopy(orig_r2); d["stats_paired_t_df4"]["G2_holdout_D_minus_A"]["p_holm"] = 0.5; _try_r2(d, "PHOLM_G2A_MISMATCH")

            # Non-zero-variance STAT_TOL boundary check & Phase 2 1pp vs 2pp margin separation check
            d_edge = copy.deepcopy(orig_r2)
            for idx, row in enumerate(d_edge["per_seed"]):
                row["arms"]["Arm_A_Naive_Additive_DeltaW"]["holdout_mean_pct"] = 61.5 + 0.1 * idx
                row["arms"]["Arm_D_Cayley_FlowNull_Retract_Spinor16B"]["holdout_mean_pct"] = 60.0 + 0.05 * idx
            t_kl_e = ver.paired_t_df4(
                [math.log(r["arms"]["Arm_A_Naive_Additive_DeltaW"]["final_prose_kl_nats"]) for r in d_edge["per_seed"]],
                [math.log(r["arms"]["Arm_D_Cayley_FlowNull_Retract_Spinor16B"]["final_prose_kl_nats"]) for r in d_edge["per_seed"]],
            )
            t_hb_e = ver.paired_t_df4(
                [r["arms"]["Arm_D_Cayley_FlowNull_Retract_Spinor16B"]["holdout_mean_pct"] for r in d_edge["per_seed"]],
                [r["base_holdout_mean_pct"] for r in d_edge["per_seed"]],
            )
            t_ha_e = ver.paired_t_df4(
                [r["arms"]["Arm_D_Cayley_FlowNull_Retract_Spinor16B"]["holdout_mean_pct"] for r in d_edge["per_seed"]],
                [r["arms"]["Arm_A_Naive_Additive_DeltaW"]["holdout_mean_pct"] for r in d_edge["per_seed"]],
            )
            ph1_e, ph2_e, ph3_e = ver.holm_3([t_kl_e["p_raw"], t_hb_e["p_raw"], t_ha_e["p_raw"]])
            d_edge["stats_paired_t_df4"]["G1_logKL_A_minus_D"]["p_holm"] = ph1_e
            d_edge["stats_paired_t_df4"]["G2_holdout_D_minus_Base"]["p_holm"] = ph2_e
            d_edge["stats_paired_t_df4"]["G2_holdout_D_minus_A"]["p_holm"] = ph3_e
            r2_path.write_text(json.dumps(_resign_results(d_edge)), encoding="utf-8")
            cert_edge = ver.build_study_certificate(sd)
            self.assertEqual(cert_edge["phase2_geodesic_retraction"]["verdict"], "CONFIRMED")
            self.assertFalse(cert_edge["phase2_geodesic_retraction"]["passes_stricter_phase1_g1_margin"])
            # Also confirm --require-pinned rejects a live-consistent modified bundle across --check, --json, and --write!
            edge_cert_p = sd / "edge_cert.json"
            edge_cert_p.write_text(json.dumps(cert_edge), encoding="utf-8")
            self.assertRaisesCode("CERT_PIN_MISMATCH", ver.verify_certificate_file, edge_cert_p, sd, require_pinned=True)
            err_pin_j = io.StringIO()
            with mock.patch.object(sys, "stderr", err_pin_j):
                self.assertEqual(ver.main(["--study-dir", str(sd), "--json", "--require-pinned"]), 2)
            self.assertEqual(json.loads(err_pin_j.getvalue())["code"], "CERT_PIN_MISMATCH")
            err_pin_w = io.StringIO()
            unwritten_p = sd / "should_not_exist.json"
            with mock.patch.object(sys, "stderr", err_pin_w):
                self.assertEqual(ver.main(["--study-dir", str(sd), "--write", str(unwritten_p), "--require-pinned"]), 2)
            self.assertEqual(json.loads(err_pin_w.getvalue())["code"], "CERT_PIN_MISMATCH")
            self.assertFalse(unwritten_p.exists())
            edge_cert_p.unlink()
            # Perturbing p_holm by 2 * STAT_TOL fails closed immediately
            d_edge["stats_paired_t_df4"]["G1_logKL_A_minus_D"]["p_holm"] = ph1_e + 2.0 * ver.STAT_TOL
            _try_r2(d_edge, "PHOLM_G1_MISMATCH")

            # Exact STAT_TOL boundary check (tiny non-zero variance -> exp_ph == 0.0; got_ph == STAT_TOL passes <= and kills <)
            d_tol = copy.deepcopy(orig_r2)
            eps_v = (0.0, 1e-8, -1e-8, 2e-8, -2e-8)
            for idx, row in enumerate(d_tol["per_seed"]):
                row["arms"]["Arm_A_Naive_Additive_DeltaW"]["final_prose_kl_nats"] = 0.5 + eps_v[idx]
                row["arms"]["Arm_D_Cayley_FlowNull_Retract_Spinor16B"]["final_prose_kl_nats"] = 0.002
                row["base_holdout_mean_pct"] = 40.0
                row["arms"]["Arm_A_Naive_Additive_DeltaW"]["holdout_mean_pct"] = 55.0 + eps_v[idx]
                row["arms"]["Arm_D_Cayley_FlowNull_Retract_Spinor16B"]["holdout_mean_pct"] = 60.0 + 2.0 * eps_v[idx]
            d_tol["stats_paired_t_df4"]["G1_logKL_A_minus_D"]["p_holm"] = ver.STAT_TOL
            d_tol["stats_paired_t_df4"]["G2_holdout_D_minus_Base"]["p_holm"] = 0.0
            d_tol["stats_paired_t_df4"]["G2_holdout_D_minus_A"]["p_holm"] = 0.0
            r2_path.write_text(json.dumps(_resign_results(d_tol)), encoding="utf-8")
            self.assertEqual(ver.build_study_certificate(sd)["phase2_geodesic_retraction"]["verdict"], "CONFIRMED")
            r2_path.write_text(json.dumps(orig_r2), encoding="utf-8")

            # Phase 1 determinism receipt binding tamper check
            r1_path = sd / "phase1_binary_gate_results.json"
            orig_r1 = json.loads(r1_path.read_text(encoding="utf-8"))
            d1_det = copy.deepcopy(orig_r1)
            d1_det["determinism_receipt_sha256"] = "0" * 64
            r1_path.write_text(json.dumps(_resign_results(d1_det)), encoding="utf-8")
            self.assertRaisesCode("BOUND_DET_MISMATCH", ver.build_study_certificate, sd)
            r1_path.write_text(json.dumps(orig_r1), encoding="utf-8")

            # PARTIAL verdict branch & P2_VERDICT_UNEXPECTED
            d = copy.deepcopy(orig_r2)
            for row in d["per_seed"]:
                row["arms"]["Arm_D_Cayley_FlowNull_Retract_Spinor16B"]["commits"] = 3
            d["gates"]["G2_reserve_commits_and_holdout_gain"] = False
            d["gates"]["verdict"] = "PARTIAL"
            _try_r2(d, "P2_VERDICT_UNEXPECTED")

            # P1_VERDICT_UNEXPECTED (force Phase 1 to PARTIAL by making G1 pass)
            d1 = copy.deepcopy(orig_r1)
            for i, row in enumerate(d1["per_seed"]):
                row["arms"]["Arm_A_Naive_Additive_DeltaW"]["final_prose_kl_nats"] = 0.5 + 0.001 * i
                row["arms"]["Arm_D_Cayley_FlowNull_Spinor16B"]["final_prose_kl_nats"] = 0.002
                row["arms"]["Arm_D_Cayley_FlowNull_Spinor16B"]["holdout_mean_pct"] = 60.0 + 0.01 * i
            t_kl = ver.paired_t_df2(
                [math.log(r["arms"]["Arm_A_Naive_Additive_DeltaW"]["final_prose_kl_nats"]) for r in d1["per_seed"]],
                [math.log(r["arms"]["Arm_D_Cayley_FlowNull_Spinor16B"]["final_prose_kl_nats"]) for r in d1["per_seed"]],
            )
            t_hb = ver.paired_t_df2(
                [r["arms"]["Arm_D_Cayley_FlowNull_Spinor16B"]["holdout_mean_pct"] for r in d1["per_seed"]],
                [r["base_holdout_mean_pct"] for r in d1["per_seed"]],
            )
            t_ha = ver.paired_t_df2(
                [r["arms"]["Arm_D_Cayley_FlowNull_Spinor16B"]["holdout_mean_pct"] for r in d1["per_seed"]],
                [r["arms"]["Arm_A_Naive_Additive_DeltaW"]["holdout_mean_pct"] for r in d1["per_seed"]],
            )
            ph1, ph2, ph3 = ver.holm_3([t_kl["p_raw"], t_hb["p_raw"], t_ha["p_raw"]])
            d1["stats_paired_t_df2"]["G1_logKL_A_minus_D"]["p_holm"] = ph1
            d1["stats_paired_t_df2"]["G2_holdout_D_minus_Base"]["p_holm"] = ph2
            d1["stats_paired_t_df2"]["G2_holdout_D_minus_A"]["p_holm"] = ph3
            d1["gates"]["G1_prose_kl_cure"] = True
            d1["gates"]["G2_reserve_commits_and_holdout_gain"] = ph2 < 0.01
            d1["gates"]["verdict"] = "CONFIRMED" if ph2 < 0.01 else "PARTIAL"
            r1_path.write_text(json.dumps(_resign_results(d1)), encoding="utf-8")
            self.assertRaisesCode("P1_VERDICT_UNEXPECTED", ver.build_study_certificate, sd)
            r1_path.write_text(json.dumps(orig_r1), encoding="utf-8")

            # On-disk preregistration tamper detected immediately
            pr1_path = sd / "preregistration_phase1_binary_gate.md"
            orig_pr1 = pr1_path.read_text(encoding="utf-8")
            pr1_path.write_text(orig_pr1 + "\ntamper\n", encoding="utf-8")
            self.assertRaisesCode("BOUND_PREREG_MISMATCH", ver.build_study_certificate, sd)
            pr1_path.write_text(orig_pr1, encoding="utf-8")

            # Missing study dir
            self.assertRaisesCode("BAD_STUDY_DIR", ver.build_study_certificate, Path(td) / "nope")

            # Phase 2 missing Phase 1 context (kills BoolOp And->Or on phase1_hold_margin_pp / phase1_seed_ids)
            self.assertRaisesCode(
                "P1_CTX_MISSING",
                ver._verify_phase_results,
                sd,
                phase=2,
                results_file="phase2_geodesic_retraction_results.json",
                det_file="phase2_hardware_determinism.json",
                prereg_file="preregistration_phase2_geodesic_retraction.md",
                phase1_hold_margin_pp=None,
                phase1_seed_ids=[0, 1, 2],
            )
            self.assertRaisesCode(
                "P1_CTX_MISSING",
                ver._verify_phase_results,
                sd,
                phase=2,
                results_file="phase2_geodesic_retraction_results.json",
                det_file="phase2_hardware_determinism.json",
                prereg_file="preregistration_phase2_geodesic_retraction.md",
                phase1_hold_margin_pp=1.0,
                phase1_seed_ids=None,
            )

    def test_06_certificate_tamper_and_cli_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            sd = _copy_study(Path(td))
            cert_path = sd / "so_d_geodesic_retraction_certificate.json"
            orig_c = json.loads(cert_path.read_text(encoding="utf-8"))

            d = copy.deepcopy(orig_c); d["schema"] = "bad"; cert_path.write_text(json.dumps(d), encoding="utf-8")
            self.assertRaisesCode("CERT_SCHEMA_BAD", ver.verify_certificate_file, cert_path, sd)

            d = copy.deepcopy(orig_c); d["payload_sha256"] = "0" * 64; cert_path.write_text(json.dumps(d), encoding="utf-8")
            self.assertRaisesCode("CERT_PSHA_MISMATCH", ver.verify_certificate_file, cert_path, sd)

            d = copy.deepcopy(orig_c); d["certificate_sha256"] = "0" * 64; cert_path.write_text(json.dumps(d), encoding="utf-8")
            self.assertRaisesCode("CERT_CSHA_MISMATCH", ver.verify_certificate_file, cert_path, sd)

            d = copy.deepcopy(orig_c); d["status"] = "FORGED"; cert_path.write_text(json.dumps(_resign_cert(d)), encoding="utf-8")
            self.assertRaisesCode("CERT_LIVE_MISMATCH", ver.verify_certificate_file, cert_path, sd)
            d = copy.deepcopy(orig_c); d["bound_artifacts_sha256"]["phase1_binary_gate_results.json"] = "0" * 64; cert_path.write_text(json.dumps(_resign_cert(d)), encoding="utf-8")
            self.assertRaisesCode("CERT_LIVE_MISMATCH", ver.verify_certificate_file, cert_path, sd)
            cert_path.write_text(json.dumps(orig_c), encoding="utf-8")

            # CLI paths: default stdout (+ --require-pinned), --check pass, --write pass, --check fail (exit 2), unwritable --write (exit 2)
            out1 = io.StringIO()
            with mock.patch.object(sys, "stdout", out1):
                self.assertEqual(ver.main(["--study-dir", str(sd), "--json", "--require-pinned"]), 0)
            self.assertEqual(json.loads(out1.getvalue())["certificate_sha256"], orig_c["certificate_sha256"])

            out2 = io.StringIO()
            with mock.patch.object(sys, "stdout", out2):
                self.assertEqual(ver.main(["--study-dir", str(sd), "--check", str(cert_path)]), 0)
            self.assertEqual(json.loads(out2.getvalue())["status"], "PASS")

            out3 = io.StringIO()
            out_file = sd / "re_written.json"
            with mock.patch.object(sys, "stdout", out3):
                self.assertEqual(ver.main(["--study-dir", str(sd), "--write", str(out_file)]), 0)
            self.assertEqual(json.loads(out3.getvalue())["status"], "WRITTEN")

            err1 = io.StringIO()
            with mock.patch.object(sys, "stderr", err1):
                self.assertEqual(ver.main(["--study-dir", str(sd), "--check", str(sd / "missing.json")]), 2)
            self.assertEqual(json.loads(err1.getvalue())["code"], "JSON_MISSING")

            err2 = io.StringIO()
            with mock.patch.object(sys, "stderr", err2):
                self.assertEqual(ver.main(["--study-dir", str(sd), "--write", str(sd / "no_dir" / "out.json")]), 2)
            self.assertEqual(json.loads(err2.getvalue())["code"], "IO_ERROR")

            # CLI --check refuses symlinked certificate & symlinked study artifacts with RC=2
            real_cert_copy = sd / "real_cert_copy.json"
            shutil.copy2(cert_path, real_cert_copy)
            cert_path.unlink()
            cert_path.symlink_to(real_cert_copy)
            err_sym = io.StringIO()
            with mock.patch.object(sys, "stderr", err_sym):
                self.assertEqual(ver.main(["--study-dir", str(sd), "--check", str(cert_path), "--require-pinned"]), 2)
            self.assertEqual(json.loads(err_sym.getvalue())["code"], "SYMLINK_FORBIDDEN")
            cert_path.unlink()
            shutil.move(str(real_cert_copy), str(cert_path))

            # main() top-level OSError catch -> RC=2 & PYTHONINTMAXSTRDIGITS=0 4400-digit rejection -> RC=2
            err_os = io.StringIO()
            bad_stdout = mock.MagicMock()
            bad_stdout.write.side_effect = OSError("broken pipe")
            with mock.patch.object(sys, "stdout", bad_stdout), mock.patch.object(sys, "stderr", err_os):
                self.assertEqual(ver.main(["--study-dir", str(sd), "--check", str(cert_path)]), 2)
            self.assertEqual(json.loads(err_os.getvalue())["code"], "IO_ERROR")

            big_cert = sd / "big4400.json"
            big_cert.write_text('{"x": ' + ("9" * 4400) + "}", encoding="utf-8")
            env_big = dict(os.environ, CUDA_VISIBLE_DEVICES="", PYTHONDONTWRITEBYTECODE="1", PYTHONINTMAXSTRDIGITS="0")
            proc_big = subprocess.run(
                [sys.executable, "-I", "-B", str(STUDY_DIR / "verify_so_d_geodesic_retraction.py"), "--study-dir", str(sd), "--check", str(big_cert)],
                capture_output=True,
                text=True,
                env=env_big,
                timeout=20,
            )
            self.assertEqual(proc_big.returncode, 2)
            self.assertEqual(json.loads(proc_big.stderr)["code"], "JSON_PARSE_FAIL")


if __name__ == "__main__":
    unittest.main()
