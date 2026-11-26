#!/usr/bin/env python3
"""Pure-Stdlib R5 Unit & 100% Mutation-Kill Suite for `verify_xpi_gegenbauer_attention.py`.

Zero floats in exact-proof assertions, zero bare asserts, zero skips, zero third-party imports.
Exercises every `require_ok` guard and exact rational boundary across Chebyshev/Gegenbauer
recurrences, convex Chebyshev decompositions, denominator projections, Mellin-Sphere-Zador
identities, Joukowski vs BRIDGE_12 non-commutativity, certificate tamper refusals, and AST zero-float checks.
"""

from __future__ import annotations

import ast
import contextlib
import copy
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
from typing import Any, Callable

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import verify_xpi_gegenbauer_attention as xpi  # noqa: E402


def _resign(cert: dict[str, Any]) -> dict[str, Any]:
    body = {k: v for k, v in cert.items() if k != "certificate_sha256"}
    out = copy.deepcopy(body)
    out["certificate_sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return out


class TestXPiGegenbauerAttentionR5(unittest.TestCase):
    def _expect_code(self, fn: Callable[[], Any], code: str) -> None:
        with self.assertRaises(xpi.XPiGegenbauerError) as ctx:
            fn()
        self.assertEqual(ctx.exception.code, code)

    def test_01_ast_zero_floats_master_certificate_and_tamper_refusals(self) -> None:
        src = (_HERE / "verify_xpi_gegenbauer_attention.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        float_literals = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, float)
        ]
        float_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float"
        ]
        self.assertEqual(len(float_literals), 0)
        self.assertEqual(len(float_calls), 0)

        cert = xpi.build_xpi_gegenbauer_certificate()
        xpi.validate_xpi_certificate(cert)
        self.assertEqual(cert["float_ops_used"], 0)
        self.assertEqual(len(cert["certificate_sha256"]), 64)

        # Certificate root, SHA, Theorem 1, and Theorem 2 tamper refusals (every conjunction branch!)
        self._expect_code(lambda: xpi.validate_xpi_certificate("not_dict"), "BAD_CERT_ROOT")  # type: ignore[arg-type]
        c_flt = copy.deepcopy(cert)
        c_flt["float_ops_used"] = 1
        self._expect_code(lambda: xpi.validate_xpi_certificate(_resign(c_flt)), "BAD_CERT_ROOT")

        c_short_sha = copy.deepcopy(cert)
        c_short_sha["certificate_sha256"] = "short"
        self._expect_code(lambda: xpi.validate_xpi_certificate(c_short_sha), "MISSING_CERT_SHA")
        c_none_sha = copy.deepcopy(cert)
        c_none_sha["certificate_sha256"] = None
        self._expect_code(lambda: xpi.validate_xpi_certificate(c_none_sha), "MISSING_CERT_SHA")

        c_bad_sha = copy.deepcopy(cert)
        c_bad_sha["certificate_sha256"] = "0" * 64
        self._expect_code(lambda: xpi.validate_xpi_certificate(c_bad_sha), "CERT_SHA_MISMATCH")

        t1_tamper_fields = (
            ("stereographic_chebyshev_checks", 53),
            ("chebyshev_minus_one_matches", 8),
            ("norm_at_one_matches", 44),
            ("linear_init_l1_matches", 4),
            ("convex_chebyshev_decompositions_verified", 44),
            ("grid_supremum_matches", 764),
            ("legendre_l2_diag_verified", 7),
            ("legendre_l2_off_diag_zeros", 55),
            ("monomial_u6_u8_l2_cos_sq_q", "1/2"),
            ("g_invariance_and_linear_init_checks", 29),
            ("t7_chebyshev_unshrunk", False),
            ("t7_monomial_l1_inflation_factor_g1_q", "1/1"),
            ("t7_monomial_proj_shrink_ratio_g1_q", "1/1"),
            ("p8_const_term_q", "1/1"),
            ("p8_zero_const_monomial_l1_inflation_factor_g1_q", "1/1"),
            ("monomial_b8_max_at_rho_half_g2_q", "1/2"),
            ("monomial_b8_max_at_rho_half_g4_q", "1/2"),
            ("mobius_spherical_boost_checks", 101),
            ("mobius_north_pole_symbolic_slope_checks", 5),
            ("mobius_bijection_inverse_checks", 101),
        )
        for k, bad_v in t1_tamper_fields:
            mut = copy.deepcopy(cert)
            mut["theorem_1_spherical_denominator_projection"][k] = bad_v
            self._expect_code(lambda m=mut: xpi.validate_xpi_certificate(_resign(m)), "THEOREM_1_CERT_INVALID")

        t2_tamper_fns: list[Callable[[dict[str, Any]], None]] = [
            lambda m: m["theorem_2_xpi_mellin_sphere_zador_bridge12"].update({"mellin_even_s_verified_count": 11}),
            lambda m: m["theorem_2_xpi_mellin_sphere_zador_bridge12"].update({"null_cone_s2_omega2": {"coeff_q": "2/1", "pi_power": 1}}),
            lambda m: m["theorem_2_xpi_mellin_sphere_zador_bridge12"].update({"unit_radius_ball_norm_second_moment_q": {"2": "1/5"}}),
            lambda m: m["theorem_2_xpi_mellin_sphere_zador_bridge12"].update({"unit_volume_zador_d2_G_B2_xpi": {"coeff_q": "1/4", "pi_power": 0}}),
            lambda m: m["theorem_2_xpi_mellin_sphere_zador_bridge12"].update({"unit_volume_zador_pow_d_verified_count": 4}),
            lambda m: m["theorem_2_xpi_mellin_sphere_zador_bridge12"].update({"unit_volume_zador_pow_d_samples": {"2": {"coeff_q": "1/16", "pi_power": 0}}}),
            lambda m: m["theorem_2_xpi_mellin_sphere_zador_bridge12"].update({"ball_unit_Vd_rescaled_pi_cancel_verified_count": 4}),
            lambda m: m["theorem_2_xpi_mellin_sphere_zador_bridge12"]["joukowski_vs_bridge12"].update({"joukowski_potential_polar_match": False}),
            lambda m: m["theorem_2_xpi_mellin_sphere_zador_bridge12"]["joukowski_vs_bridge12"].update({"joukowski_pure_pi_inv_monomial": False}),
            lambda m: m["theorem_2_xpi_mellin_sphere_zador_bridge12"]["joukowski_vs_bridge12"].update({"joukowski_speed_sq_diff_pi_inv_poly_q": ["0/1", "2/1", "0/1"]}),
            lambda m: m["theorem_2_xpi_mellin_sphere_zador_bridge12"]["joukowski_vs_bridge12"].update({"joukowski_upper_faster_than_lower": False}),
            lambda m: m["theorem_2_xpi_mellin_sphere_zador_bridge12"]["joukowski_vs_bridge12"].update({"so2_abelian_commutes": False}),
            lambda m: m["theorem_2_xpi_mellin_sphere_zador_bridge12"]["joukowski_vs_bridge12"].update({"so3_2i_non_abelian": False}),
            lambda m: m["theorem_2_xpi_mellin_sphere_zador_bridge12"]["joukowski_vs_bridge12"].update({"bridge12_scalar_I3_inertia_UL": [1, 2, 0]}),
            lambda m: m["theorem_2_xpi_mellin_sphere_zador_bridge12"]["joukowski_vs_bridge12"].update({"bridge12_scalar_I3_inertia_LU": [1, 2, 0]}),
            lambda m: m["theorem_2_xpi_mellin_sphere_zador_bridge12"]["joukowski_vs_bridge12"].update({"bridge12_G311_inertia_UL": [1, 2, 0]}),
            lambda m: m["theorem_2_xpi_mellin_sphere_zador_bridge12"]["joukowski_vs_bridge12"].update({"bridge12_G311_inertia_LU": [2, 1, 0]}),
            lambda m: m["theorem_2_xpi_mellin_sphere_zador_bridge12"]["joukowski_vs_bridge12"].update({"bridge12_n_minus_split": False}),
        ]
        for fn in t2_tamper_fns:
            mut = copy.deepcopy(cert)
            fn(mut)
            self._expect_code(lambda m=mut: xpi.validate_xpi_certificate(_resign(m)), "THEOREM_2_CERT_INVALID")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(xpi.main([]), 0)
            self.assertIn('"status": "PASS"', buf.getvalue())
        buf_json = io.StringIO()
        with contextlib.redirect_stdout(buf_json):
            self.assertEqual(xpi.main(["--json"]), 0)
            parsed = json.loads(buf_json.getvalue())
            self.assertEqual(parsed["certificate_sha256"], cert["certificate_sha256"])

    def test_02_polynomial_chebyshev_and_gegenbauer_boundaries_and_refusals(self) -> None:
        self._expect_code(lambda: xpi._to_frac(True), "TYPE_ERROR")
        self._expect_code(lambda: xpi._to_frac("1/2"), "TYPE_ERROR")  # type: ignore[arg-type]
        self.assertEqual(xpi._to_frac(0), Fraction(0))
        self.assertEqual(xpi._to_frac(Fraction(3, 7)), Fraction(3, 7))

        self._expect_code(lambda: xpi.eval_poly_q((), Fraction(0)), "EMPTY_POLY")
        self._expect_code(lambda: xpi.eval_poly_q([Fraction(1)], Fraction(0)), "EMPTY_POLY")  # type: ignore[arg-type]
        self._expect_code(lambda: xpi.integrate_poly_minus1_to_1_q(()), "EMPTY_POLY")
        self._expect_code(lambda: xpi.integrate_poly_minus1_to_1_q([Fraction(1)]), "EMPTY_POLY")  # type: ignore[arg-type]
        self.assertEqual(xpi.eval_poly_q((Fraction(5),), Fraction(3)), Fraction(5))
        self.assertEqual(xpi.integrate_poly_minus1_to_1_q((Fraction(5),)), Fraction(10))

        for fn in (
            xpi.chebyshev_t_poly_q,
            lambda d: xpi.gegenbauer_norm_poly_q(d, Fraction(1)),
            lambda d: xpi.gegenbauer_chebyshev_convex_weights_q(d, Fraction(1)),
            lambda d: xpi.stereographic_chebyshev_slack_q(d, Fraction(1)),
        ):
            self._expect_code(lambda f=fn: f(True), "BAD_DEGREE")
            self._expect_code(lambda f=fn: f("2"), "BAD_DEGREE")  # type: ignore[arg-type]
            self._expect_code(lambda f=fn: f(-1), "BAD_DEGREE")

        self.assertEqual(xpi.chebyshev_t_poly_q(0), (Fraction(1),))
        self.assertEqual(xpi.gegenbauer_norm_poly_q(0, Fraction(0)), (Fraction(1),))
        self.assertEqual(xpi.gegenbauer_norm_poly_q(3, Fraction(0)), xpi.chebyshev_t_poly_q(3))
        self.assertEqual(xpi.gegenbauer_chebyshev_convex_weights_q(0, Fraction(0)), {0: Fraction(1)})
        self.assertEqual(xpi.gegenbauer_chebyshev_convex_weights_q(4, Fraction(0)), {4: Fraction(1)})
        self.assertEqual(xpi.stereographic_chebyshev_slack_q(0, Fraction(0)), (Fraction(1), Fraction(1), Fraction(0), True))

        self._expect_code(lambda: xpi.gegenbauer_norm_poly_q(2, Fraction(-1, 10)), "NEG_ALPHA")
        self._expect_code(lambda: xpi.gegenbauer_chebyshev_convex_weights_q(2, Fraction(-1, 10)), "NEG_ALPHA")

        self._expect_code(lambda: xpi._poly_div_by_var_exact_q([Fraction(0), Fraction(1)]), "SHORT_POLY_DIV")  # type: ignore[arg-type]
        self._expect_code(lambda: xpi._poly_div_by_var_exact_q((Fraction(0),)), "SHORT_POLY_DIV")
        self._expect_code(lambda: xpi._poly_div_by_var_exact_q((Fraction(1, 5), Fraction(2))), "NONZERO_H0_REMAINDER")
        self.assertEqual(xpi._poly_div_by_var_exact_q((Fraction(0), Fraction(7, 3))), (Fraction(7, 3),))

        self._expect_code(lambda: xpi.mobius_spherical_boost_q(Fraction(-11, 10), Fraction(1)), "SCORE_OUT_OF_SPHERE")
        self._expect_code(lambda: xpi.mobius_spherical_boost_q(Fraction(11, 10), Fraction(1)), "SCORE_OUT_OF_SPHERE")
        self._expect_code(lambda: xpi.mobius_spherical_boost_q(Fraction(0), Fraction(0)), "NONPOS_GAIN")
        self._expect_code(lambda: xpi.verify_mobius_north_pole_slope_q(Fraction(0)), "NONPOS_GAIN")
        self._expect_code(lambda: xpi.verify_mobius_north_pole_slope_q(Fraction(-1, 2)), "NONPOS_GAIN")
        self.assertEqual(xpi.mobius_spherical_boost_q(Fraction(-1), Fraction(3))["psi"], Fraction(-1))
        self.assertEqual(xpi.mobius_spherical_boost_q(Fraction(1), Fraction(3))["psi"], Fraction(1))

    def test_03_projection_and_attention_bounds_and_refusals(self) -> None:
        self._expect_code(lambda: xpi.project_spherical_denominator_q([], Fraction(1, 2)), "BAD_B_COEFFS")
        self._expect_code(lambda: xpi.project_spherical_denominator_q(123, Fraction(1, 2)), "BAD_B_COEFFS")
        self._expect_code(lambda: xpi.project_spherical_denominator_q([Fraction(1, 4)], Fraction(0)), "BAD_RHO")
        self._expect_code(lambda: xpi.project_spherical_denominator_q([Fraction(1, 4)], Fraction(1)), "BAD_RHO")
        self.assertEqual(xpi.project_spherical_denominator_q([Fraction(1, 4)], Fraction(1, 2)), (Fraction(1, 4),))
        self.assertEqual(xpi.project_spherical_denominator_q([Fraction(1)], Fraction(1, 2)), (Fraction(1, 2),))

        self._expect_code(lambda: xpi.project_monomial_denominator_q([], Fraction(1), Fraction(1, 2)), "BAD_B_COEFFS")
        self._expect_code(lambda: xpi.project_monomial_denominator_q(123, Fraction(1), Fraction(1, 2)), "BAD_B_COEFFS")
        self._expect_code(lambda: xpi.project_monomial_denominator_q([Fraction(1)], Fraction(0), Fraction(1, 2)), "NONPOS_GAIN")
        self._expect_code(lambda: xpi.project_monomial_denominator_q([Fraction(1)], Fraction(-1), Fraction(1, 2)), "NONPOS_GAIN")
        self._expect_code(lambda: xpi.project_monomial_denominator_q([Fraction(1)], Fraction(2), Fraction(0)), "BAD_RHO")
        self._expect_code(lambda: xpi.project_monomial_denominator_q([Fraction(1)], Fraction(2), Fraction(1)), "BAD_RHO")
        self.assertEqual(xpi.project_monomial_denominator_q([Fraction(1, 8)], Fraction(2), Fraction(1, 2)), (Fraction(1, 4) * Fraction(1, 2),))

        self._expect_code(lambda: xpi.eval_xpi_attention_1d_q([], [], [0, 1], [0], 1, 0, Fraction(1, 2)), "EMPTY_KEYS")
        self._expect_code(lambda: xpi.eval_xpi_attention_1d_q(123, 123, [0, 1], [0], 1, 0, Fraction(1, 2)), "EMPTY_KEYS")
        self._expect_code(lambda: xpi.eval_xpi_attention_1d_q([0], [1, 2], [0, 1], [0], 1, 0, Fraction(1, 2)), "KEY_VAL_LEN")
        self._expect_code(lambda: xpi.eval_xpi_attention_1d_q([0], 123, [0, 1], [0], 1, 0, Fraction(1, 2)), "KEY_VAL_LEN")
        self._expect_code(lambda: xpi.eval_xpi_attention_1d_q([0], [1], [1], [], 1, 0, Fraction(1, 2)), "BAD_A_COEFFS")
        self._expect_code(lambda: xpi.eval_xpi_attention_1d_q([0], [1], 123, [0], 1, 0, Fraction(1, 2)), "BAD_A_COEFFS")
        self._expect_code(lambda: xpi.eval_xpi_attention_1d_q([0], [1], [0, 1], [0, 0], 1, 0, Fraction(1, 2)), "BAD_B_LEN")
        self._expect_code(lambda: xpi.eval_xpi_attention_1d_q([0], [1], [0, 1], 123, 1, 0, Fraction(1, 2)), "BAD_B_LEN")
        self._expect_code(lambda: xpi.eval_xpi_attention_1d_q([0], [1], [0, 1], [0], 0, 0, Fraction(1, 2)), "NONPOS_GAIN")
        self._expect_code(lambda: xpi.eval_xpi_attention_1d_q([Fraction(-11, 10)], [1], [0, 1], [0], 1, 0, Fraction(1, 2)), "SCORE_OUT_OF_SPHERE")
        self._expect_code(lambda: xpi.eval_xpi_attention_1d_q([Fraction(11, 10)], [1], [0, 1], [0], 1, 0, Fraction(1, 2)), "SCORE_OUT_OF_SPHERE")

        res_m1 = xpi.eval_xpi_attention_1d_q([Fraction(-1)], [Fraction(3)], [Fraction(0), Fraction(1)], [Fraction(1, 2)], Fraction(2), Fraction(1), Fraction(1, 2))
        self.assertEqual(res_m1["min_h"], Fraction(1, 2))
        self.assertEqual(res_m1["output"], Fraction(-6) / Fraction(1, 2))
        res_p1 = xpi.eval_xpi_attention_1d_q([Fraction(1)], [Fraction(3)], [Fraction(0), Fraction(1)], [Fraction(1, 2)], Fraction(2), Fraction(1), Fraction(1, 2))
        self.assertEqual(res_p1["max_h"], Fraction(3, 2))
        self.assertEqual(res_p1["output"], Fraction(6) / Fraction(3, 2))

    def test_04_mellin_zador_sylvester_and_joukowski_bridge12_guards(self) -> None:
        self._expect_code(lambda: xpi.mellin_sphere_even_dim_q(True), "BAD_HALF_DIM")
        self._expect_code(lambda: xpi.mellin_sphere_even_dim_q("1"), "BAD_HALF_DIM")  # type: ignore[arg-type]
        self._expect_code(lambda: xpi.mellin_sphere_even_dim_q(0), "BAD_HALF_DIM")
        m1 = xpi.mellin_sphere_even_dim_q(1)
        self.assertEqual(m1["omega_coeff_q"], "2/1")
        self.assertEqual(m1["two_over_omega_coeff_q"], "1/1")

        self._expect_code(lambda: xpi.unit_radius_ball_norm_moment_q(True), "BAD_DIM")
        self._expect_code(lambda: xpi.unit_radius_ball_norm_moment_q("2"), "BAD_DIM")  # type: ignore[arg-type]
        self._expect_code(lambda: xpi.unit_radius_ball_norm_moment_q(0), "BAD_DIM")
        self.assertEqual(xpi.unit_radius_ball_norm_moment_q(1), Fraction(1, 3))
        self.assertEqual(xpi.unit_radius_ball_norm_moment_q(8), Fraction(1, 10))

        self._expect_code(lambda: xpi.zador_unit_volume_even_dim_xpi_q(True), "BAD_HALF_DIM")
        self._expect_code(lambda: xpi.zador_unit_volume_even_dim_xpi_q("1"), "BAD_HALF_DIM")  # type: ignore[arg-type]
        self._expect_code(lambda: xpi.zador_unit_volume_even_dim_xpi_q(0), "BAD_HALF_DIM")
        z1 = xpi.zador_unit_volume_even_dim_xpi_q(1)
        self.assertEqual(z1["unit_vol_zador_pow_d_coeff_q"], "1/16")
        self.assertEqual(z1["unit_vol_zador_pow_d_pi_power"], -2)
        self.assertTrue(z1["unit_vol_zador_pow_d_exact_match"])
        self.assertTrue(z1["ball_unit_Vd_rescaled_pi_cancels"])

        non_sym = (
            (Fraction(1), Fraction(2), Fraction(0)),
            (Fraction(0), Fraction(1), Fraction(0)),
            (Fraction(0), Fraction(0), Fraction(1)),
        )
        self._expect_code(lambda: xpi.sylvester_inertia_3x3_q(non_sym), "NON_SYMMETRIC_3X3")
        off_diag_sym = (
            (Fraction(0), Fraction(1), Fraction(0)),
            (Fraction(1), Fraction(0), Fraction(0)),
            (Fraction(0), Fraction(0), Fraction(0)),
        )
        self.assertEqual(xpi.sylvester_inertia_3x3_q(off_diag_sym), (1, 1, 1))

        self._expect_code(lambda: xpi.verify_joukowski_vs_bridge12_q(Fraction(0), Fraction(1), Fraction(1)), "NONPOS_FLOW_PARAMS")
        self._expect_code(lambda: xpi.verify_joukowski_vs_bridge12_q(Fraction(1), Fraction(0), Fraction(1)), "NONPOS_FLOW_PARAMS")
        self._expect_code(lambda: xpi.verify_joukowski_vs_bridge12_q(Fraction(1), Fraction(1), Fraction(0)), "NONPOS_FLOW_PARAMS")
        jb = xpi.verify_joukowski_vs_bridge12_q(Fraction(3, 2), Fraction(5, 7), Fraction(1))
        self.assertEqual(jb["joukowski_speed_sq_gap_pi_inv_coeff_q"], "30/7")
        self.assertEqual(jb["joukowski_speed_sq_diff_pi_inv_poly_q"], ["0/1", "30/7", "0/1"])
        self.assertTrue(jb["joukowski_potential_polar_match"])
        self.assertTrue(jb["joukowski_pure_pi_inv_monomial"])
        self.assertTrue(jb["bridge12_n_minus_split"])

    def test_05_m1_unit_vol_zador_vs_unit_radius_and_m2_constructive_proofs(self) -> None:
        # M1-S122: Euclidean unit-volume Vol(B^{2k}) = 1 gives G(B^{2k})^{2k} = (k!)^2 / ((2k+2)^{2k} * pi^{2k})
        # with strictly negative pi_power = -2k != 0, whereas V_{2k}^2 * G(B^{2k})^{2k} cancels pi!
        expected_pow_d = {
            1: ("1/16", -2),
            2: ("1/324", -4),
            4: ("9/1562500", -8),
        }
        for k_val in (1, 2, 4, 8, 12):
            row = xpi.zador_unit_volume_even_dim_xpi_q(k_val)
            self.assertEqual(row["unit_radius_norm_moment_q"], f"1/{2 * k_val + 2}")
            self.assertEqual(row["unit_radius_pi_power"], 0)
            self.assertEqual(row["unit_vol_zador_pow_d_pi_power"], -2 * k_val)
            self.assertNotEqual(row["unit_vol_zador_pow_d_pi_power"], 0)
            self.assertTrue(row["unit_vol_zador_pow_d_exact_match"])
            self.assertTrue(row["ball_unit_Vd_rescaled_pi_cancels"])
            if k_val in expected_pow_d:
                exp_coeff, exp_pow = expected_pow_d[k_val]
                self.assertEqual(row["unit_vol_zador_pow_d_coeff_q"], exp_coeff)
                self.assertEqual(row["unit_vol_zador_pow_d_pi_power"], exp_pow)

        # M2-S122 (a): Constructive Joukowski speed-squared difference 4 * V_inf * Gamma / (pi * a)
        jb_a2 = xpi.verify_joukowski_vs_bridge12_q(Fraction(3, 2), Fraction(5, 7), Fraction(2))
        self.assertEqual(jb_a2["joukowski_speed_sq_diff_pi_inv_poly_q"], ["0/1", "15/7", "0/1"])
        self.assertTrue(jb_a2["joukowski_potential_polar_match"])
        self.assertTrue(jb_a2["joukowski_pure_pi_inv_monomial"])

        # M2-S122 (b): Symbolic north-pole derivative d/du|_{u=1} == g and bijective inverse psi_{1/g}
        for g_val in (Fraction(1, 5), Fraction(1), Fraction(3), Fraction(11, 3)):
            sl = xpi.verify_mobius_north_pole_slope_q(g_val)
            self.assertEqual(sl["delta_north_h0_q"], "0/1")
            self.assertEqual(sl["north_pole_slope_q"], xpi._frac_str(g_val))
            self.assertEqual(sl["south_pole_slope_q"], xpi._frac_str(Fraction(1) / g_val))
            self.assertTrue(sl["exact_slope_match"])
            for u_val in (Fraction(-1), Fraction(-3, 7), Fraction(0), Fraction(5, 9), Fraction(1)):
                fwd = xpi.mobius_spherical_boost_q(u_val, g_val)["psi"]
                inv = xpi.mobius_spherical_boost_q(fwd, Fraction(1) / g_val)["psi"]
                self.assertEqual(inv, u_val)


if __name__ == "__main__":
    unittest.main()
