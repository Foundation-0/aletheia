#!/usr/bin/env python3
"""Assertion-free R5 adversarial unittest suite for verify_ratncap_cone_gait.py (Track S127)."""

from __future__ import annotations

from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import verify_ratncap_cone_gait as mod


class TestRatNCAPConeGaitR5(unittest.TestCase):
    def test_01_g1_cone_bijection_hessian_elasticity_and_boundaries(self) -> None:
        g1 = mod.verify_g1_antagonistic_cone_linearization()
        self.assertTrue(g1["passed"])
        self.assertEqual(g1["cone_samples_tested"], 8)
        self.assertEqual(g1["bijection_exact_matches"], 8)
        self.assertEqual(g1["positive_stiffness_matches"], 8)
        self.assertEqual(g1["convex_hull_matches"], 8)
        self.assertEqual(g1["torque_identity_matches"], 32)
        self.assertEqual(g1["antagonistic_midpoint_defect"], "0/1")
        self.assertEqual(g1["position_stiffness_midpoint_defect"], "-1/1")
        self.assertTrue(g1["position_stiffness_defect_formula_exact"])
        self.assertEqual(g1["position_stiffness_hessian_det"], "-1/1")
        self.assertEqual(g1["position_stiffness_hessian_inertia"], [1, 1, 0])
        self.assertEqual(g1["elastic_dw_store"], "-3/4")
        self.assertEqual(g1["elastic_dw_return"], "3/4")
        self.assertEqual(g1["elastic_dw_cycle"], "0/1")
        self.assertTrue(g1["elastic_braking_negative"])
        self.assertTrue(g1["elastic_return_positive"])
        self.assertTrue(g1["elastic_cycle_zero"])

        # Exact boundary checks for forward/inverse cone maps & check_frac
        self.assertEqual(mod.check_frac(mod.MAX_INT_ABS, "mi"), Fraction(mod.MAX_INT_ABS, 1))
        self.assertEqual(mod.check_frac(-mod.MAX_INT_ABS, "ni"), Fraction(-mod.MAX_INT_ABS, 1))
        self.assertEqual(mod.check_frac(Fraction(mod.MAX_INT_ABS, mod.MAX_INT_ABS), "mf"), Fraction(1, 1))
        self.assertEqual(mod.check_frac(Fraction(1, mod.MAX_INT_ABS), "md"), Fraction(1, mod.MAX_INT_ABS))
        for bad_f in (1.5, True, "1", mod.MAX_INT_ABS + 1, Fraction(mod.MAX_INT_ABS + 1, 1), Fraction(1, mod.MAX_INT_ABS + 1)):
            with self.assertRaises(mod.RatNCAPError):
                mod.check_frac(bad_f, "bad")

        # Boundary poles q_eq == q_flx and q_eq == q_ext accepted; strictly outside rejected!
        ae_lo, af_lo = mod.antagonistic_inverse_q(2, -1, 1, 1, 1, -1)
        self.assertEqual((ae_lo, af_lo), (Fraction(0), Fraction(2)))
        ae_hi, af_hi = mod.antagonistic_inverse_q(2, 1, 1, 1, 1, -1)
        self.assertEqual((ae_hi, af_hi), (Fraction(2), Fraction(0)))

        # Must-fail negative controls for forward/inverse/spring_work
        for fn in (
            lambda: mod.antagonistic_forward_q(1, 1, 0, 1, 1, -1),
            lambda: mod.antagonistic_forward_q(1, 1, 1, 0, 1, -1),
            lambda: mod.antagonistic_forward_q(1, 1, 1, 1, -1, -1),
            lambda: mod.antagonistic_forward_q(-1, 2, 1, 1, 1, -1),
            lambda: mod.antagonistic_forward_q(2, -1, 1, 1, 1, -1),
            lambda: mod.antagonistic_forward_q(0, 0, 1, 1, 1, -1),
            lambda: mod.antagonistic_inverse_q(1, 0, 0, 1, 1, -1),
            lambda: mod.antagonistic_inverse_q(1, 0, 1, 0, 1, -1),
            lambda: mod.antagonistic_inverse_q(1, -1, 1, 1, -1, -1),
            lambda: mod.antagonistic_inverse_q(0, 0, 1, 1, 1, -1),
            lambda: mod.antagonistic_inverse_q(1, -2, 1, 1, 1, -1),
            lambda: mod.antagonistic_inverse_q(1, 2, 1, 1, 1, -1),
            lambda: mod.spring_work_q(0, 0, 0, 1),
        ):
            with self.assertRaises(mod.RatNCAPError):
                fn()

    def test_02_g2_commissural_bifurcation_krein_inertia_and_edges(self) -> None:
        g2 = mod.verify_g2_commissural_gait_bifurcation()
        self.assertTrue(g2["passed"])
        self.assertEqual(g2["k_crit_1d"], "1/4")
        self.assertEqual(g2["k_crit_4d_with_diag"], "3/16")
        self.assertTrue(g2["gait_1d_intact"]["trot_stable"])
        self.assertFalse(g2["gait_1d_intact"]["bound_stable"])
        self.assertEqual(g2["gait_1d_intact"]["trot_krein_neg"], 0)
        self.assertEqual(g2["gait_1d_intact"]["bound_krein_neg"], 1)
        self.assertEqual(g2["gait_1d_critical"]["curv_trot"], "0/1")
        self.assertEqual(g2["gait_1d_critical"]["curv_bound"], "0/1")
        self.assertFalse(g2["gait_1d_v0_knockout"]["trot_stable"])
        self.assertTrue(g2["gait_1d_v0_knockout"]["bound_stable"])
        self.assertEqual(g2["gait_1d_v0_knockout"]["trot_krein_neg"], 1)
        self.assertEqual(g2["gait_1d_v0_knockout"]["bound_krein_neg"], 0)
        self.assertEqual(g2["v3_ablation_curv_gain_1d"], "1/1")

        # 4-limb T^4/S^1 exact Krein inertia swap (3,0,0) <-> (1,2,0) & degenerate (2,0,1)/(1,1,1) at crit!
        self.assertEqual(g2["t4_inertia_trot_intact"], [3, 0, 0])
        self.assertEqual(g2["t4_inertia_bound_intact"], [1, 2, 0])
        self.assertEqual(g2["t4_inertia_trot_at_crit"], [2, 0, 1])
        self.assertEqual(g2["t4_inertia_bound_at_crit"], [2, 0, 1])
        self.assertEqual(g2["t4_inertia_trot_v0_ko"], [1, 2, 0])
        self.assertEqual(g2["t4_inertia_bound_v0_ko"], [3, 0, 0])
        self.assertEqual(g2["t4_inertia_trot_v3_ko"], [3, 0, 0])
        self.assertEqual(g2["t4_v3_ablation_trace_gain"], "3/1")

        # Exercise all branches of symmetric_inertia_3x3_q (hyperbolic off-diag zero-diag block, zero matrix, pivot swap!)
        z = Fraction(0)
        one = Fraction(1)
        self.assertEqual(mod.symmetric_inertia_3x3_q(((z, z, z), (z, z, z), (z, z, z))), (0, 0, 3))
        self.assertEqual(mod.symmetric_inertia_3x3_q(((z, one, z), (one, z, z), (z, z, z))), (1, 1, 1))
        self.assertEqual(mod.symmetric_inertia_3x3_q(((z, z, z), (z, z, one), (z, one, z))), (1, 1, 1))
        self.assertEqual(mod.symmetric_inertia_3x3_q(((z, z, z), (z, one, z), (z, z, -one))), (1, 1, 1))

        # Must-fail controls for symmetric_inertia_3x3_q, gait_1d_curvatures_q, quadruped_t4_reduced_hessian_q
        for fn in (
            lambda: mod.symmetric_inertia_3x3_q(((one, z), (z, one))),
            lambda: mod.symmetric_inertia_3x3_q(((one, z), (z, one), (z, z))),
            lambda: mod.symmetric_inertia_3x3_q(((one, one, z), (z, one, z), (z, z, one))),
            lambda: mod.gait_1d_curvatures_q(1, 0, 1),
            lambda: mod.gait_1d_curvatures_q(1, 1, -1),
            lambda: mod.gait_1d_curvatures_q(-1, 1, 1),
            lambda: mod.quadruped_t4_reduced_hessian_q(one, one, one, "gallop"),
        ):
            with self.assertRaises(mod.RatNCAPError):
                fn()

    def test_03_g3_holosphere_antagonistic_gate_and_refusal_controls(self) -> None:
        g3 = mod.verify_g3_holosphere_antagonistic_gate()
        self.assertTrue(g3["passed"])
        self.assertEqual(g3["gate_pairs_tested"], 5)
        self.assertEqual(g3["contraction_exact_matches"], 5)
        self.assertEqual(g3["non_expansive_matches"], 5)
        self.assertEqual(g3["coord_convex_hull_matches"], 5)
        self.assertEqual(g3["unit_ball_invariant_matches"], 5)
        self.assertEqual(g3["cone_equivalence_matches"], 5)
        self.assertEqual(g3["unconstrained_lam_eff"], "-3/2")
        self.assertEqual(g3["unconstrained_expansion_ratio_sq"], "9/4")
        self.assertTrue(g3["unconstrained_escapes_unit_ball"])

        # Exact boundary g_pos + g_neg == 1 & len == 1 accepted; violations rejected!
        xn, lam = mod.antagonistic_dual_pole_step_q([0], [1], [-1], Fraction(1, 2), Fraction(1, 2))
        self.assertEqual((xn, lam), ((Fraction(0),), Fraction(0)))
        for fn in (
            lambda: mod.antagonistic_dual_pole_step_q([], [], [], 0, 0),
            lambda: mod.antagonistic_dual_pole_step_q([0], [1, 2], [-1], 0, 0),
            lambda: mod.antagonistic_dual_pole_step_q([0], [1], [-1, 0], 0, 0),
            lambda: mod.antagonistic_dual_pole_step_q([0], [1], [-1], Fraction(-1, 10), 0),
            lambda: mod.antagonistic_dual_pole_step_q([0], [1], [-1], 0, Fraction(-1, 10)),
            lambda: mod.antagonistic_dual_pole_step_q([0], [1], [-1], Fraction(3, 5), Fraction(3, 5)),
        ):
            with self.assertRaises(mod.RatNCAPError):
                fn()

    def test_04_certificate_cli_and_tamper_refusal(self) -> None:
        cert = mod.build_certificate()
        self.assertEqual(cert["payload"]["schema"], mod.SCHEMA_S127)
        self.assertEqual(cert["payload"]["prereg_w15_sha256"], mod.PREREG_W15_SHA256)
        self.assertTrue(cert["payload"]["all_passed"])

        # Depth boundary MAX_JSON_DEPTH accepted, MAX_JSON_DEPTH + 1 rejected
        mod.validate_json_tree_no_floats({"k": [1, True, None, "s"]})
        at_cap: object = "leaf"
        for _ in range(mod.MAX_JSON_DEPTH):
            at_cap = [at_cap]
        mod.validate_json_tree_no_floats(at_cap)
        with self.assertRaises(mod.RatNCAPError):
            mod.validate_json_tree_no_floats([at_cap])
        with self.assertRaises(mod.RatNCAPError):
            mod.validate_json_tree_no_floats({"k": 1.25})
        with self.assertRaises(mod.RatNCAPError):
            mod.validate_json_tree_no_floats({1: "bad_key"})
        with self.assertRaises(mod.RatNCAPError):
            mod.validate_json_tree_no_floats({"k": object()})

        with tempfile.TemporaryDirectory() as td:
            cpath = Path(td) / "cert.json"
            out1 = io.StringIO()
            with redirect_stdout(out1):
                self.assertEqual(mod.main(["--write", str(cpath), "--json"]), 0)
            self.assertEqual(json.loads(out1.getvalue())["certificate_sha256"], cert["certificate_sha256"])

            out2 = io.StringIO()
            with redirect_stdout(out2):
                self.assertEqual(mod.main(["--check", str(cpath)]), 0)
            self.assertIn("PASS", out2.getvalue())

            # Tamper 1: mutate payload -> PAYLOAD_SHA_MISMATCH
            tampered = json.loads(cpath.read_text(encoding="utf-8"))
            tampered["payload"]["all_passed"] = False
            p1 = Path(td) / "t1.json"
            p1.write_text(json.dumps(tampered), encoding="utf-8")
            eb1 = io.StringIO()
            with redirect_stderr(eb1):
                self.assertEqual(mod.main(["--check", str(p1)]), 2)
            self.assertIn("PAYLOAD_SHA_MISMATCH", eb1.getvalue())

            # Tamper 2: valid payload_sha256, stale cert_sha256 -> CERT_SHA_MISMATCH
            tampered["payload_sha256"] = hashlib.sha256(mod._canonical_json_bytes(tampered["payload"])).hexdigest()
            p2 = Path(td) / "t2.json"
            p2.write_text(json.dumps(tampered), encoding="utf-8")
            eb2 = io.StringIO()
            with redirect_stderr(eb2):
                self.assertEqual(mod.main(["--check", str(p2)]), 2)
            self.assertIn("CERT_SHA_MISMATCH", eb2.getvalue())

            # Tamper 3a: re-signed forged all_passed=False -> ALL_PASSED_INVALID inside check_certificate_file!
            inner = {"payload": tampered["payload"], "payload_sha256": tampered["payload_sha256"]}
            tampered["certificate_sha256"] = hashlib.sha256(mod._canonical_json_bytes(inner)).hexdigest()
            p3 = Path(td) / "t3.json"
            p3.write_text(json.dumps(tampered), encoding="utf-8")
            eb3 = io.StringIO()
            with redirect_stderr(eb3):
                self.assertEqual(mod.main(["--check", str(p3)]), 2)
            self.assertIn("ALL_PASSED_INVALID", eb3.getvalue())

            # Tamper 3b: re-signed forged schema (passes gate invariants, caught by REPLAY_MISMATCH!)
            forged_meta = json.loads(cpath.read_text(encoding="utf-8"))
            forged_meta["payload"]["schema"] = "forged.schema"
            forged_meta["payload_sha256"] = hashlib.sha256(mod._canonical_json_bytes(forged_meta["payload"])).hexdigest()
            forged_meta["certificate_sha256"] = hashlib.sha256(
                mod._canonical_json_bytes({"payload": forged_meta["payload"], "payload_sha256": forged_meta["payload_sha256"]})
            ).hexdigest()
            p3b = Path(td) / "t3b.json"
            p3b.write_text(json.dumps(forged_meta), encoding="utf-8")
            eb3b = io.StringIO()
            with redirect_stderr(eb3b):
                self.assertEqual(mod.main(["--check", str(p3b)]), 2)
            self.assertIn("REPLAY_MISMATCH", eb3b.getvalue())

            # B1 Regression Tests: direct validate_certificate_payload tamper + in-memory monkeypatch attacks!
            for gate_key, field, bad_val, expect_code in (
                ("g1_antagonistic_cone_linearization", "bijection_exact_matches", 0, "G1_CERT_INVALID"),
                ("g2_commissural_gait_bifurcation", "t4_inertia_trot_v0_ko", [3, 0, 0], "G2_CERT_INVALID"),
                ("g3_holosphere_antagonistic_gate", "contraction_exact_matches", 4, "G3_CERT_INVALID"),
            ):
                bad_p = json.loads(json.dumps(cert["payload"]))
                bad_p[gate_key][field] = bad_val
                with self.assertRaises(mod.RatNCAPError) as cm_v:
                    mod.validate_certificate_payload(bad_p)
                self.assertEqual(cm_v.exception.code, expect_code)

            # In-memory monkeypatch 1: shift antagonistic_inverse_q by 1/7 -> build_certificate MUST raise G1_CERT_INVALID!
            orig_inv = mod.antagonistic_inverse_q
            def _bad_inv(*a: object, **kw: object) -> tuple[Fraction, Fraction]:
                ae, af = orig_inv(*a, **kw)  # type: ignore[arg-type]
                return ae + Fraction(1, 7), af
            mod.antagonistic_inverse_q = _bad_inv  # type: ignore[assignment]
            try:
                with self.assertRaises(mod.RatNCAPError) as cm_m1:
                    mod.build_certificate()
                self.assertEqual(cm_m1.exception.code, "G1_CERT_INVALID")
            finally:
                mod.antagonistic_inverse_q = orig_inv  # type: ignore[assignment]

            # In-memory monkeypatch 2: force symmetric_inertia_3x3_q to (3, 0, 0) -> MUST raise G1/G2_CERT_INVALID!
            orig_in = mod.symmetric_inertia_3x3_q
            mod.symmetric_inertia_3x3_q = lambda _m: (3, 0, 0)  # type: ignore[assignment]
            try:
                g2_bad = mod.verify_g2_commissural_gait_bifurcation()
                self.assertFalse(g2_bad["passed"])
                bad_p2 = json.loads(json.dumps(cert["payload"]))
                bad_p2["g2_commissural_gait_bifurcation"] = g2_bad
                with self.assertRaises(mod.RatNCAPError) as cm_m2:
                    mod.validate_certificate_payload(bad_p2)
                self.assertEqual(cm_m2.exception.code, "G2_CERT_INVALID")
            finally:
                mod.symmetric_inertia_3x3_q = orig_in  # type: ignore[assignment]

            # In-memory monkeypatch 3: corrupt antagonistic_dual_pole_step_q -> MUST raise G3_CERT_INVALID!
            orig_step = mod.antagonistic_dual_pole_step_q
            def _bad_step(x: object, up: object, un: object, gp: object, gn: object) -> tuple[tuple[Fraction, ...], Fraction]:
                xn, lam = orig_step(x, up, un, gp, gn)  # type: ignore[arg-type]
                return tuple(v * 3 for v in xn), lam
            mod.antagonistic_dual_pole_step_q = _bad_step  # type: ignore[assignment]
            try:
                with self.assertRaises(mod.RatNCAPError) as cm_m3:
                    mod.build_certificate()
                self.assertEqual(cm_m3.exception.code, "G3_CERT_INVALID")
            finally:
                mod.antagonistic_dual_pole_step_q = orig_step  # type: ignore[assignment]

            for fname, txt, expect in (
                ("float.json", '{"payload": 1.5, "payload_sha256": "a", "certificate_sha256": "b"}', "FLOAT_FORBIDDEN"),
                ("keys.json", '{"payload": {}, "payload_sha256": "a"}', "CERT_KEYS"),
                ("list.json", "[1, 2]", "CERT_NOT_DICT"),
                ("ht1.json", '{"payload": {}, "payload_sha256": 1, "certificate_sha256": "b"}', "CERT_HASH_TYPE"),
                ("ht2.json", '{"payload": {}, "payload_sha256": "a", "certificate_sha256": 2}', "CERT_HASH_TYPE"),
                ("badjson.json", "{oops", "CERT_LOAD_FAIL"),
            ):
                fp = Path(td) / fname
                fp.write_text(txt, encoding="utf-8")
                eb = io.StringIO()
                with redirect_stderr(eb):
                    self.assertEqual(mod.main(["--check", str(fp)]), 2)
                self.assertIn(expect, eb.getvalue())

            ebm = io.StringIO()
            with redirect_stderr(ebm):
                self.assertEqual(mod.main(["--check", str(Path(td) / "missing.json")]), 2)
            self.assertIn("CERT_LOAD_FAIL", ebm.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
