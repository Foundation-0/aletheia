#!/usr/bin/env python3
"""R5 Adversarial & Mutation-Killing Test Suite for EXP-Q25a LoopCD S^{d-1} & SU(2) Geometry."""

from __future__ import annotations

from fractions import Fraction
import io
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_loopcd_sphere_geometry as mod


class TestLoopCDSphereGeometryR5(unittest.TestCase):
    def test_01_sphere_rmsnorm_angular_law_saturation_and_slerp_contrast(self) -> None:
        cert = mod.build_certificate()
        mod.validate_certificate(cert)
        sp = cert["sphere_rmsnorm_theorems"]
        self.assertEqual(sp["angular_law_matches"], 36)
        self.assertEqual(sp["saturation_bound_matches"], 36)
        self.assertEqual(sp["householder_8d_equivariance_matches"], 36)
        self.assertEqual(sp["strict_omega_monotonicity_steps"], 30)
        self.assertEqual(sp["witness_90deg_w1_tan_alpha"], "1/2")
        self.assertEqual(sp["witness_obtuse_s2_slerp_sin2theta"], "-24/25")
        self.assertEqual(sp["witness_obtuse_s2_loopcd_tan_alpha"], "4/13")
        self.assertEqual(sp["witness_small_s1_20_w1_2_rel_diff"], "1/201")

        self.assertEqual(mod.stereo_cos_sin_q(0), (Fraction(1), Fraction(0)))
        h1 = (Fraction(3, 5), Fraction(-4, 5))
        hr = (Fraction(1), Fraction(0))
        self.assertEqual(mod.loopcd_hidden_raw_q(h1, hr, -1), h1)
        self.assertEqual(mod.loopcd_tan_alpha_q(Fraction(3, 2), 0), Fraction(0))
        self.assertEqual(mod.loopcd_chord_normal_margin_q(Fraction(3, 2), 0), Fraction(2, 3))

    def test_02_su2_cayley_strang_cancellation_and_exact_bch_identities(self) -> None:
        cert = mod.build_certificate()
        su = cert["su2_holonomy_theorems"]
        self.assertEqual(su["min_acute_ball_cayley_denom"], "81/625")
        self.assertEqual(su["delta_cayley_identity_matches"], 4)
        self.assertEqual(su["exact_bch_product_matches"], 20)
        self.assertEqual(su["endpoint_omega_0_matches"], 4)
        self.assertEqual(su["endpoint_omega_minus1_matches"], 4)
        self.assertEqual(su["exact_geodesic_omega_1_matches"], 4)
        self.assertEqual(su["dyadic_lam1_8_err_sq_exact_cayley_bch"], "0/1")

        # Boundary ||w|| == 4/5 exact norm acceptance and exact C(w_Delta) == U_1^dag * U_R
        w_edge = (Fraction(4, 5), Fraction(0), Fraction(0))
        w_opp = (Fraction(-4, 5), Fraction(0), Fraction(0))
        delta_edge = mod.su2_relative_cayley_delta_q(w_edge, w_opp, enforce_acute_ball=True)
        self.assertEqual(delta_edge, (Fraction(-40, 9), Fraction(0), Fraction(0)))

        # Adaptive top-2 rule intermediate value, zero-omega_max boundary, & p1 + p2 == 1
        self.assertEqual(mod.adaptive_omega_top2_q(0, Fraction(3, 5), Fraction(1, 5)), Fraction(0))
        self.assertEqual(
            mod.adaptive_omega_top2_q(Fraction(4, 5), Fraction(3, 5), Fraction(2, 5)),
            Fraction(16, 25),
        )

    def test_03_must_fail_type_domain_and_singularity_guards(self) -> None:
        cases = [
            ("TYPE_ERROR", lambda: mod.stereo_cos_sin_q(True)),  # type: ignore[arg-type]
            ("TYPE_ERROR", lambda: mod.stereo_cos_sin_q(0.5)),  # type: ignore[arg-type]
            ("NEG_HALF_TAN", lambda: mod.stereo_cos_sin_q(Fraction(-1, 10))),
            ("NONPOS_HALF_TAN", lambda: mod.loopcd_tan_alpha_q(0, 1)),
            ("NEG_OMEGA", lambda: mod.loopcd_tan_alpha_q(1, Fraction(-1, 10))),
            ("NONPOS_HALF_TAN", lambda: mod.loopcd_chord_normal_margin_q(0, 1)),
            ("NEG_OMEGA", lambda: mod.loopcd_chord_normal_margin_q(1, Fraction(-1, 10))),
            ("BAD_VEC_DIM", lambda: mod.loopcd_hidden_raw_q([1], [1], 0)),
            ("BAD_VEC_DIM", lambda: mod.loopcd_hidden_raw_q("ab", "cd", 0)),
            ("HIDDEN_DIM_MISMATCH", lambda: mod.loopcd_hidden_raw_q([1, 0], [1, 0, 0], 0)),
            ("OMEGA_BELOW_MINUS_ONE", lambda: mod.loopcd_hidden_raw_q([1, 0], [0, 1], Fraction(-11, 10))),
            ("NEG_OMEGA_MAX", lambda: mod.adaptive_omega_top2_q(Fraction(-1, 2), Fraction(1, 2), Fraction(1, 4))),
            ("BAD_TOP2_PROBS", lambda: mod.adaptive_omega_top2_q(1, Fraction(1, 4), Fraction(1, 2))),
            ("BAD_TOP2_PROBS", lambda: mod.adaptive_omega_top2_q(1, Fraction(1, 2), Fraction(-1, 10))),
            ("BAD_TOP2_PROBS", lambda: mod.adaptive_omega_top2_q(1, Fraction(6, 5), Fraction(0))),
            ("PROB_SUM_GT_ONE", lambda: mod.adaptive_omega_top2_q(1, Fraction(3, 5), Fraction(1, 2))),
            ("BAD_VEC3", lambda: mod.cayley_su2_q([1, 2])),
            ("BAD_QUAT", lambda: mod.inv_cayley_su2_q((Fraction(1), Fraction(0), Fraction(0)))),  # type: ignore[arg-type]
            ("NON_UNIT_QUAT", lambda: mod.inv_cayley_su2_q((Fraction(1), Fraction(1), Fraction(0), Fraction(0)))),
            ("ANTIPODAL_MINUS_I", lambda: mod.inv_cayley_su2_q((Fraction(-1), Fraction(0), Fraction(0), Fraction(0)))),
            ("OUTSIDE_ACUTE_BALL", lambda: mod.su2_relative_cayley_delta_q((Fraction(5, 6), 0, 0), (0, 0, 0), True)),
            ("OUTSIDE_ACUTE_BALL", lambda: mod.su2_relative_cayley_delta_q((0, 0, 0), (0, Fraction(5, 6), 0), True)),
            ("CAYLEY_ANTIPODAL_PRODUCT", lambda: mod.cayley_compose_vec_q((Fraction(1), 0, 0), (Fraction(1), 0, 0))),
            ("OMEGA_BELOW_MINUS_ONE", lambda: mod.su2_cayley_exact_bch_guide_q((0, 0, 0), (0, 0, 0), Fraction(-2))),
            ("DIM_MISMATCH", lambda: mod._dot_nq((Fraction(1),), (Fraction(1), Fraction(2)))),
            ("ZERO_HOUSEHOLDER_VEC", lambda: mod._householder_apply_q((Fraction(0), Fraction(0)), (Fraction(1), Fraction(0)))),
        ]
        for expected_code, fn in cases:
            with self.assertRaises(mod.LoopCDGeometryError) as cm:
                fn()
            self.assertEqual(cm.exception.code, expected_code)

    def test_04_certificate_tamper_refusal_and_cli_modes(self) -> None:
        cert = mod.build_certificate()
        bad_sp = json.loads(json.dumps(cert))
        bad_sp["sphere_rmsnorm_theorems"]["saturation_bound_matches"] = 35
        with self.assertRaises(mod.LoopCDGeometryError) as cm1:
            mod.validate_certificate(bad_sp)
        self.assertEqual(cm1.exception.code, "SPHERE_CERT_INVALID")

        bad_su = json.loads(json.dumps(cert))
        bad_su["su2_holonomy_theorems"]["exact_geodesic_omega_1_matches"] = 3
        with self.assertRaises(mod.LoopCDGeometryError) as cm2:
            mod.validate_certificate(bad_su)
        self.assertEqual(cm2.exception.code, "SU2_CERT_INVALID")

        for ratio_val in ("15/1", "17/1"):
            bad_lr = json.loads(json.dumps(cert))
            bad_lr["su2_holonomy_theorems"]["dyadic_halving_ratio_left_order"] = ratio_val
            with self.assertRaises(mod.LoopCDGeometryError):
                mod.validate_certificate(bad_lr)

        bad_rr = json.loads(json.dumps(cert))
        bad_rr["su2_holonomy_theorems"]["dyadic_halving_ratio_right_strang_linear"] = "60/1"
        with self.assertRaises(mod.LoopCDGeometryError):
            mod.validate_certificate(bad_rr)

        bad_miss_sha = json.loads(json.dumps(cert))
        del bad_miss_sha["payload_sha256"]
        with self.assertRaises(mod.LoopCDGeometryError) as cm_ms:
            mod.validate_certificate(bad_miss_sha)
        self.assertEqual(cm_ms.exception.code, "CERT_SHA_MISSING")

        bad_sha = json.loads(json.dumps(cert))
        bad_sha["payload_sha256"] = "0" * 64
        with self.assertRaises(mod.LoopCDGeometryError) as cm_bs:
            mod.validate_certificate(bad_sha)
        self.assertEqual(cm_bs.exception.code, "CERT_SHA_MISMATCH")

        for flag_list, token in (([], "S121_LOOPCD_GEOMETRY_OK"), (["--check"], "PASS S121_LOOPCD_GEOMETRY"), (["--json"], '"schema_version"')):
            buf = io.StringIO()
            old = sys.stdout
            try:
                sys.stdout = buf
                rc = mod.main(flag_list)
            finally:
                sys.stdout = old
            self.assertEqual(rc, 0)
            self.assertIn(token, buf.getvalue())

        orig_build = mod.build_certificate
        try:
            def _bad_build() -> dict[str, object]:
                c = json.loads(json.dumps(orig_build()))
                c["payload_sha256"] = "0" * 64
                return c

            mod.build_certificate = _bad_build  # type: ignore[assignment]
            err_buf = io.StringIO()
            old_err = sys.stderr
            try:
                sys.stderr = err_buf
                rc_fail = mod.main(["--check"])
            finally:
                sys.stderr = old_err
            self.assertEqual(rc_fail, 2)
            self.assertIn("FAIL S121_LOOPCD_GEOMETRY [CERT_SHA_MISMATCH]", err_buf.getvalue())
        finally:
            mod.build_certificate = orig_build  # type: ignore[assignment]


if __name__ == "__main__":
    unittest.main()
