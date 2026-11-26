#!/usr/bin/env python3
"""Comprehensive Verification & Strict Filesystem Security Test Suite for Zero-Delta-W State-Transport Tomography.

Zero bare asserts, zero floats, zero third-party dependencies; non-regular file
tests use scratch os.mkfifo inside TemporaryDirectory exclusively.
"""

from __future__ import annotations

import copy
import ctypes
from fractions import Fraction
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.append(_SCRIPT_DIR)

import zero_dw_state_transport_audit as audit
import zero_dw_state_transport_oracle as oracle


class _IntSub(int):
    pass


class _StrSub(str):
    pass


class _DictSub(dict):
    pass


class _ListSub(list):
    pass


class _FracSub(Fraction):
    pass


def _resign_cert(cert: dict) -> dict:
    out = copy.deepcopy(cert)
    p_sha = hashlib.sha256(oracle.canonical_json_bytes(out["payload"])).hexdigest()
    out["payload_sha256"] = p_sha
    core = {
        "schema_version": out["schema_version"],
        "track_id": out["track_id"],
        "oracle_class": out["oracle_class"],
        "novelty_tier": out["novelty_tier"],
        "payload_sha256": p_sha,
        "payload": out["payload"],
    }
    out["certificate_sha256"] = hashlib.sha256(oracle.canonical_json_bytes(core)).hexdigest()
    return out


def _base_airlock_record(**overrides: object) -> dict:
    rec: dict = {
        "weight_hash_match": True,
        "weight_block_dpi_ratio": "1",
        "max_weight_block_dpi_ratio": "4",
        "kv_cross_model_reuse": False,
        "kv_residual_evicted_mentions": 0,
        "state_session_authorized": True,
        "state_cross_session_carryover": False,
        "state_delta_frob_sq": "0",
        "max_state_delta_frob_sq": "1",
        "state_delta_rank": 0,
        "state_schatten_s4": "0",
        "margin_before": "2",
        "margin_after": "2",
        "min_safe_margin": "1/2",
        "yield_wall_displacement": "0",
        "max_yield_wall_displacement": "1/2",
        "cohomological_relu_residual": 0,
        "require_conserved_flow": True,
        "corpus_provenance_verified": True,
        "mode_transfer_gap": "3/125",
        "max_mode_transfer_gap": "1/20",
    }
    rec.update(overrides)
    return rec


class TestPrimitivesAndParsers(unittest.TestCase):
    def _assert_err(self, expected_code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.ZeroDwStateTransportError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, expected_code)

    def test_require_exact_int_boundaries(self) -> None:
        max_ok = (1 << oracle.MAX_INT_BITS) - 1
        self.assertEqual(oracle.require_exact_int(max_ok, "x"), max_ok)
        self.assertEqual(oracle.require_exact_int(-max_ok, "x"), -max_ok)
        self.assertEqual(oracle.require_exact_int(0, "x", min_val=0, max_val=0), 0)
        self._assert_err("INVALID_INT_TYPE", oracle.require_exact_int, True, "x")
        self._assert_err("INVALID_INT_TYPE", oracle.require_exact_int, _IntSub(1), "x")
        self._assert_err("INT_BIT_LIMIT", oracle.require_exact_int, 1 << oracle.MAX_INT_BITS, "x")
        self._assert_err("INT_BELOW_MIN", oracle.require_exact_int, -1, "x", min_val=0)
        self._assert_err("INT_ABOVE_MAX", oracle.require_exact_int, 5, "x", max_val=4)

    def test_require_bool_str_sha256_fraction(self) -> None:
        self.assertIs(oracle.require_exact_bool(True, "b"), True)
        self._assert_err("INVALID_BOOL_TYPE", oracle.require_exact_bool, 1, "b")

        self.assertEqual(oracle.require_exact_str("ok", "s"), "ok")
        self.assertEqual(oracle.require_exact_str("", "s", non_empty=False), "")
        self._assert_err("INVALID_STR_TYPE", oracle.require_exact_str, _StrSub("ok"), "s")
        self._assert_err("EMPTY_STR", oracle.require_exact_str, "", "s")
        self._assert_err("INVALID_UTF8_SURROGATE", oracle.require_exact_str, "\ud800", "s")

        good_sha = "a" * 64
        self.assertEqual(oracle.require_sha256_hex(good_sha, "h"), good_sha)
        self._assert_err("INVALID_SHA256_LEN", oracle.require_sha256_hex, "a" * 63, "h")
        self._assert_err("INVALID_SHA256_HEX", oracle.require_sha256_hex, "A" * 64, "h")

        big_ok = (1 << oracle.MAX_RATIONAL_BITS) - 1
        self.assertEqual(oracle.require_exact_fraction(Fraction(big_ok, big_ok - 1), "q", positive=True), Fraction(big_ok, big_ok - 1))
        self._assert_err("INVALID_FRACTION_TYPE", oracle.require_exact_fraction, _FracSub(1, 2), "q")
        self._assert_err("INVALID_FRACTION_TYPE", oracle.require_exact_fraction, 1, "q")
        self._assert_err("RATIONAL_BIT_LIMIT", oracle.require_exact_fraction, Fraction(1 << oracle.MAX_RATIONAL_BITS, 1), "q")
        self._assert_err("RATIONAL_BIT_LIMIT", oracle.require_exact_fraction, Fraction(1, 1 << oracle.MAX_RATIONAL_BITS), "q")
        self._assert_err("RATIONAL_NON_POSITIVE", oracle.require_exact_fraction, Fraction(0, 1), "q", positive=True)

    def test_parse_int_and_rational_strict(self) -> None:
        max_ok = (1 << oracle.MAX_INT_BITS) - 1
        self.assertEqual(oracle.parse_exact_int_ascii(str(max_ok), "n"), max_ok)
        self.assertEqual(oracle.parse_exact_int_ascii("0", "n"), 0)
        self.assertEqual(oracle.parse_exact_int_ascii("-7", "n"), -7)
        self._assert_err("INT_WHITESPACE", oracle.parse_exact_int_ascii, " 1", "n")
        self._assert_err("INVALID_INT_ASCII", oracle.parse_exact_int_ascii, "-", "n")
        self._assert_err("INVALID_INT_ASCII", oracle.parse_exact_int_ascii, "12a", "n")
        self._assert_err("INVALID_INT_ASCII", oracle.parse_exact_int_ascii, "\u0661", "n")
        self._assert_err("LEADING_ZERO_INT", oracle.parse_exact_int_ascii, "01", "n")
        self._assert_err("NEGATIVE_ZERO_INT", oracle.parse_exact_int_ascii, "-0", "n")
        self._assert_err("INT_DIGIT_LIMIT", oracle.parse_exact_int_ascii, "9" * (oracle.MAX_INT_DIGITS + 1), "n")
        self._assert_err("INT_BIT_LIMIT", oracle.parse_exact_int_ascii, str(1 << oracle.MAX_INT_BITS), "n")

        self.assertEqual(oracle.parse_exact_rational(5, "q"), Fraction(5, 1))
        self.assertEqual(oracle.parse_exact_rational("-83/25", "q"), Fraction(-83, 25))
        self.assertEqual(oracle.format_exact_rational(Fraction(4, 1)), "4")
        self.assertEqual(oracle.format_exact_rational(Fraction(-83, 25)), "-83/25")
        self._assert_err("RATIONAL_WHITESPACE", oracle.parse_exact_rational, " 1/2", "q")
        self._assert_err("MALFORMED_RATIONAL", oracle.parse_exact_rational, "1/2/3", "q")
        self._assert_err("ZERO_OR_NEG_DENOM", oracle.parse_exact_rational, "1/0", "q")
        self._assert_err("ZERO_OR_NEG_DENOM", oracle.parse_exact_rational, "1/-2", "q")
        self._assert_err("NON_CANONICAL_RATIONAL", oracle.parse_exact_rational, "2/4", "q")
        self._assert_err("NON_CANONICAL_DENOM_ONE", oracle.parse_exact_rational, "3/1", "q")

    def test_validate_json_tree_and_strict_parser(self) -> None:
        max_ok = (1 << oracle.MAX_INT_BITS) - 1
        oracle.validate_json_tree({"a": None, "b": True, "c": [1, max_ok, "x"]}, "t")
        deep: object = 0
        for _ in range(oracle.MAX_JSON_DEPTH):
            deep = [deep]
        oracle.validate_json_tree(deep, "ok_depth")
        self._assert_err("MAX_DEPTH_EXCEEDED", oracle.validate_json_tree, [deep], "too_deep")
        self._assert_err("INT_BIT_LIMIT", oracle.validate_json_tree, {"x": 1 << oracle.MAX_INT_BITS}, "big")
        self._assert_err("INVALID_UTF8_SURROGATE", oracle.validate_json_tree, {"x": "\ud800"}, "sur")
        self._assert_err("INVALID_JSON_KEY", oracle.validate_json_tree, {_StrSub("k"): 1}, "subk")
        self._assert_err("INVALID_JSON_VALUE", oracle.validate_json_tree, _DictSub({"k": 1}), "subd")
        self._assert_err("INVALID_JSON_VALUE", oracle.validate_json_tree, _ListSub([1]), "subl")
        self._assert_err("INVALID_JSON_VALUE", oracle.validate_json_tree, {"x": _IntSub(1)}, "subi")
        self._assert_err("INVALID_JSON_VALUE", oracle.validate_json_tree, {"x": Fraction(1, 2)}, "frac")
        # Construct runtime float without float literal or float() call
        runtime_f = json.loads("1.5")
        self._assert_err("INVALID_JSON_VALUE", oracle.validate_json_tree, {"x": runtime_f}, "flt")

        self.assertEqual(oracle.parse_strict_json_text("[1,2]", require_object=False), [1, 2])
        self._assert_err("JSON_TOO_LARGE", oracle.parse_strict_json_text, '{"a":1}', max_bytes=6)
        self.assertEqual(oracle.parse_strict_json_text('{"a":1}', max_bytes=7), {"a": 1})
        self._assert_err("JSON_BOM_FORBIDDEN", oracle.parse_strict_json_text, '\ufeff{"a":1}')
        self._assert_err("JSON_CRLF_FORBIDDEN", oracle.parse_strict_json_text, '{"a":1}\r\n')
        self._assert_err("JSON_NUL_FORBIDDEN", oracle.parse_strict_json_text, '{"a":"x\x00"}')
        self._assert_err("JSON_FLOAT_FORBIDDEN", oracle.parse_strict_json_text, '{"a":1.5}')
        self._assert_err("JSON_CONST_FORBIDDEN", oracle.parse_strict_json_text, '{"a":NaN}')
        self._assert_err("DUPLICATE_JSON_KEY", oracle.parse_strict_json_text, '{"a":1,"a":2}')
        self._assert_err("INVALID_JSON_SYNTAX", oracle.parse_strict_json_text, "{bad")
        self._assert_err("JSON_ROOT_NOT_OBJECT", oracle.parse_strict_json_text, "[1]")


class TestLinearAlgebraAndOperators(unittest.TestCase):
    def _assert_err(self, expected_code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.ZeroDwStateTransportError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, expected_code)

    def test_matrix_and_vector_guards(self) -> None:
        q0, q1 = Fraction(0, 1), Fraction(1, 1)
        self._assert_err("INVALID_VECTOR", oracle.dot_exact, "bad", [q1])
        self._assert_err("EMPTY_VECTOR", oracle.dot_exact, [], [])
        self._assert_err("VECTOR_DIM_MISMATCH", oracle.dot_exact, [q1], [q1, q0])

        self._assert_err("INVALID_MATRIX", oracle.mat_vec_exact, "bad", [q1])
        self._assert_err("EMPTY_MATRIX", oracle.mat_vec_exact, [], [q1])
        self._assert_err("RAGGED_MATRIX", oracle.mat_vec_exact, [[q1], [q1, q0]], [q1])
        self._assert_err("MATVEC_DIM_MISMATCH", oracle.mat_vec_exact, [[q1, q0]], [q1])
        self._assert_err("MATMUL_DIM_MISMATCH", oracle.mat_mul_exact, [[q1, q0]], [[q1]])
        self._assert_err("SHAPE_MISMATCH", oracle.matrix_sub_exact, [[q1]], [[q1], [q0]])
        self._assert_err("SHAPE_MISMATCH", oracle.matrix_sub_exact, [[q1]], [[q1, q0]])
        self._assert_err("NON_SQUARE_MATRIX", oracle.gdn2_delta_step_exact, [[q1, q0]], [q1], [q1])
        self._assert_err("ZERO_MATRIX", oracle.schatten_s4_ratio_exact, [[q0, q0], [q0, q0]])
        self._assert_err("ZERO_PATCH", oracle.dpi_concentration_exact, [[q0, q0]])

        # gdn2_delta_step_exact boundary checks
        eye2 = [[q1, q0], [q0, q1]]
        self._assert_err("KEY_DIM_MISMATCH", oracle.gdn2_delta_step_exact, eye2, [q1], [q1, q0])
        self._assert_err("VALUE_DIM_MISMATCH", oracle.gdn2_delta_step_exact, eye2, [q1, q0], [q1])
        self._assert_err("ALPHA_ABOVE_ONE", oracle.gdn2_delta_step_exact, eye2, [q1, q0], [q1, q0], alpha=Fraction(2, 1))
        self.assertEqual(oracle.gdn2_delta_step_exact(eye2, [q1, q0], [q1, q0], alpha=q1, beta=q1), eye2)

        # state_transport_tomography_exact dimension checks
        sha = "0" * 64
        self._assert_err(
            "STATE_DIM_MISMATCH",
            oracle.state_transport_tomography_exact,
            eye2, [[q1]], [q1, q0], q0, [q1, q0],
            weight_sha256_before=sha, weight_sha256_after=sha,
        )
        self._assert_err(
            "WEIGHT_DIM_MISMATCH",
            oracle.state_transport_tomography_exact,
            eye2, eye2, [q1], q0, [q1, q0],
            weight_sha256_before=sha, weight_sha256_after=sha,
        )
        self._assert_err(
            "QUERY_DIM_MISMATCH",
            oracle.state_transport_tomography_exact,
            eye2, eye2, [q1, q0], q0, [q1],
            weight_sha256_before=sha, weight_sha256_after=sha,
        )

        # Non-orthogonal matrix rejection
        self._assert_err(
            "NOT_ORTHOGONAL",
            oracle.verify_orthogonal_conjugation_invariance_exact,
            eye2, eye2, [q1, q0], q0, [q1, q0],
            [[Fraction(2, 1), q0], [q0, q1]],
            weight_sha256=sha,
        )

        # discrete_s2_outward_div_exact guards
        d0, _ = oracle._build_s2_cube_operators()
        self._assert_err("INVALID_D0_MATRIX", oracle.discrete_s2_outward_div_exact, tuple(d0), [0] * 12)
        self._assert_err("INVALID_D0_MATRIX", oracle.discrete_s2_outward_div_exact, d0[:-1], [0] * 12)
        self._assert_err("INVALID_D0_MATRIX", oracle.discrete_s2_outward_div_exact, [tuple(d0[0])] + d0[1:], [0] * 12)
        self._assert_err("INVALID_D0_MATRIX", oracle.discrete_s2_outward_div_exact, [[0] * 7] + d0[1:], [0] * 12)
        self._assert_err("INVALID_FLUX_VEC", oracle.discrete_s2_outward_div_exact, d0, tuple([0] * 12))
        self._assert_err("INVALID_FLUX_VEC", oracle.discrete_s2_outward_div_exact, d0, [0] * 11)

    def test_four_channel_airlock_exhaustive_boundaries(self) -> None:
        self._assert_err("INVALID_AIRLOCK_RECORD", oracle.evaluate_state_transport_airlock, "not_dict")
        self._assert_err("INVALID_AIRLOCK_KEYS", oracle.evaluate_state_transport_airlock, {"only": 1})

        # Exact numeric boundaries & refusal checks
        self._assert_err("NEGATIVE_DPI_RATIO", oracle.evaluate_state_transport_airlock, _base_airlock_record(weight_block_dpi_ratio="-1"))
        self._assert_err("NON_POSITIVE_MAX_DPI", oracle.evaluate_state_transport_airlock, _base_airlock_record(max_weight_block_dpi_ratio="0"))
        self._assert_err("NEGATIVE_STATE_FROB", oracle.evaluate_state_transport_airlock, _base_airlock_record(state_delta_frob_sq="-1"))
        self._assert_err("NEGATIVE_MAX_STATE_FROB", oracle.evaluate_state_transport_airlock, _base_airlock_record(max_state_delta_frob_sq="-1"))
        self._assert_err("NEGATIVE_SCHATTEN_S4", oracle.evaluate_state_transport_airlock, _base_airlock_record(state_schatten_s4="-1/2"))
        self._assert_err("SCHATTEN_S4_ABOVE_ONE", oracle.evaluate_state_transport_airlock, _base_airlock_record(state_delta_frob_sq="1", state_delta_rank=1, state_schatten_s4="3/2"))
        self._assert_err("INCONSISTENT_ZERO_RANK", oracle.evaluate_state_transport_airlock, _base_airlock_record(state_delta_rank=1))
        self._assert_err("INCONSISTENT_ZERO_S4", oracle.evaluate_state_transport_airlock, _base_airlock_record(state_schatten_s4="1"))
        self._assert_err("INCONSISTENT_NONZERO_RANK", oracle.evaluate_state_transport_airlock, _base_airlock_record(state_delta_frob_sq="1", state_delta_rank=0, state_schatten_s4="1"))
        self._assert_err("INCONSISTENT_S4_RANK_BOUND", oracle.evaluate_state_transport_airlock, _base_airlock_record(state_delta_frob_sq="1", state_delta_rank=2, state_schatten_s4="1/3"))
        self._assert_err("NEGATIVE_MIN_SAFE_MARGIN", oracle.evaluate_state_transport_airlock, _base_airlock_record(min_safe_margin="-1"))
        self._assert_err("NEGATIVE_MAX_WALL_DISP", oracle.evaluate_state_transport_airlock, _base_airlock_record(max_yield_wall_displacement="-1"))
        self._assert_err("NEGATIVE_MODE_GAP", oracle.evaluate_state_transport_airlock, _base_airlock_record(mode_transfer_gap="-1"))
        self._assert_err("NEGATIVE_MAX_MODE_GAP", oracle.evaluate_state_transport_airlock, _base_airlock_record(max_mode_transfer_gap="-1"))

        # Exact equality boundaries (all PASS -> ALLOW)
        eq_ok = oracle.evaluate_state_transport_airlock(_base_airlock_record(
            weight_block_dpi_ratio="0",
            state_delta_frob_sq="0",
            max_state_delta_frob_sq="0",
            min_safe_margin="0",
            margin_after="0",
            yield_wall_displacement="0",
            max_yield_wall_displacement="0",
            mode_transfer_gap="0",
            max_mode_transfer_gap="0",
        ))
        self.assertEqual(eq_ok["airlock_4ch_decision"], "ALLOW")
        self.assertFalse(eq_ok["weight_hash_blind_to_attack"])

        # Tight S4 = 1/rank equality boundary & negative wall displacement within bound
        eq_s4 = oracle.evaluate_state_transport_airlock(_base_airlock_record(
            state_delta_frob_sq="1",
            max_state_delta_frob_sq="1",
            state_delta_rank=2,
            state_schatten_s4="1/2",
            yield_wall_displacement="-1/2",
            max_yield_wall_displacement="1/2",
            weight_block_dpi_ratio="4",
            max_weight_block_dpi_ratio="4",
            mode_transfer_gap="1/20",
            max_mode_transfer_gap="1/20",
            margin_after="1/2",
            min_safe_margin="1/2",
        ))
        self.assertEqual(eq_s4["airlock_4ch_decision"], "ALLOW")
        self.assertFalse(eq_s4["rank1_concentrated"])

        # Each BoolOp operand isolated for 100% BoolOp kill rate
        # 1. weight_hash_match=False alone -> param_only DENY, frob_only DENY, weight_hash_blind False
        r_wh = oracle.evaluate_state_transport_airlock(_base_airlock_record(weight_hash_match=False))
        self.assertEqual(r_wh["param_only_hash_decision"], "DENY")
        self.assertEqual(r_wh["frob_only_decision"], "DENY")
        self.assertIn("CH1_WEIGHT_INTEGRITY_OR_DPI", r_wh["violations_3ch"])
        self.assertFalse(r_wh["weight_hash_blind_to_attack"])

        # 2. w_dpi > max_w_dpi with weight_hash_match=True -> param_only ALLOW, 4ch DENY
        r_dpi = oracle.evaluate_state_transport_airlock(_base_airlock_record(weight_block_dpi_ratio="5"))
        self.assertIn("CH1_WEIGHT_INTEGRITY_OR_DPI", r_dpi["violations_3ch"])
        self.assertTrue(r_dpi["weight_hash_blind_to_attack"])

        # 3. kv_res > 0 with kv_reuse=False
        r_kv_res = oracle.evaluate_state_transport_airlock(_base_airlock_record(kv_residual_evicted_mentions=1))
        self.assertIn("CH2A_KV_BOUNDARY_VIOLATION", r_kv_res["violations_3ch"])

        # 4. corpus_provenance_verified=False with mode_transfer_gap <= max
        r_corp = oracle.evaluate_state_transport_airlock(_base_airlock_record(corpus_provenance_verified=False))
        self.assertIn("CH3_DATA_PROVENANCE_OR_MODE_TRANSFER", r_corp["violations_3ch"])

        # 5. state_session_authorized=False with carryover=False vs authorized=True with carryover=True
        r_unauth = oracle.evaluate_state_transport_airlock(_base_airlock_record(state_session_authorized=False))
        self.assertIn("CH2B_UNAUTHORIZED_STATE_CARRYOVER", r_unauth["violations_4ch"])
        r_carry = oracle.evaluate_state_transport_airlock(_base_airlock_record(state_cross_session_carryover=True))
        self.assertIn("CH2B_UNAUTHORIZED_STATE_CARRYOVER", r_carry["violations_4ch"])

        # 6. state_delta_frob_sq > max_state_delta_frob_sq (frob_only DENY, param_only ALLOW)
        r_frob = oracle.evaluate_state_transport_airlock(_base_airlock_record(
            state_delta_frob_sq="2", max_state_delta_frob_sq="1", state_delta_rank=1, state_schatten_s4="1",
        ))
        self.assertEqual(r_frob["frob_only_decision"], "DENY")
        self.assertIn("CH2B_STATE_FROB_BUDGET_EXCEEDED", r_frob["violations_4ch"])

        # 7. margin_sign_flipped=True while margin_below_floor=False (-2 -> +2, min_safe=1/2)
        r_flip_only = oracle.evaluate_state_transport_airlock(_base_airlock_record(
            margin_before="-2", margin_after="2", min_safe_margin="1/2",
        ))
        self.assertTrue(r_flip_only["margin_sign_flipped"])
        self.assertFalse(r_flip_only["margin_below_floor"])
        self.assertIn("CH2B_STATE_MARGIN_PHASE_CROSSING", r_flip_only["violations_4ch"])

        # 8. margin_sign_flipped=False while margin_below_floor=True (+2 -> +1/4, min_safe=1/2)
        r_floor_only = oracle.evaluate_state_transport_airlock(_base_airlock_record(
            margin_before="2", margin_after="1/4", min_safe_margin="1/2",
        ))
        self.assertFalse(r_floor_only["margin_sign_flipped"])
        self.assertTrue(r_floor_only["margin_below_floor"])
        self.assertIn("CH2B_STATE_MARGIN_PHASE_CROSSING", r_floor_only["violations_4ch"])

        # 9. require_conserved_flow=False vs True with cohomological_relu_residual=-4
        r_noncons = oracle.evaluate_state_transport_airlock(_base_airlock_record(
            require_conserved_flow=False, cohomological_relu_residual=-4,
        ))
        self.assertFalse(r_noncons["cohomology_violated"])
        self.assertEqual(r_noncons["airlock_4ch_decision"], "ALLOW")

        r_coh = oracle.evaluate_state_transport_airlock(_base_airlock_record(
            require_conserved_flow=True, cohomological_relu_residual=-4,
        ))
        self.assertTrue(r_coh["cohomology_violated"])
        self.assertEqual(r_coh["airlock_4ch_decision"], "DENY")
        self.assertEqual(r_coh["violations_4ch"], ["CH2B_COHOMOLOGICAL_RELU_OBSTRUCTION"])

        # 10. Negative yield_wall_displacement exceeding bound (-1 < -1/2) -> DENY
        r_neg_wall = oracle.evaluate_state_transport_airlock(_base_airlock_record(yield_wall_displacement="-1"))
        self.assertTrue(r_neg_wall["yield_wall_exceeded"])
        self.assertIn("CH2B_YIELD_WALL_ADVECTION", r_neg_wall["violations_4ch"])


class TestCertificateAndSecondaryAudit(unittest.TestCase):
    def _assert_err(self, expected_code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.ZeroDwStateTransportError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, expected_code)

    def test_three_pillars_exact_witnesses(self) -> None:
        cert = oracle.build_standalone_certificate()
        res = audit.verify_certificate_dict(cert, full_replay=True)
        self.assertTrue(res["valid"])
        self.assertTrue(res["secondary_audit_passed"])

        p = cert["payload"]
        p1 = p["pillar1_gdn2_zero_dw_state_transport"]
        self.assertTrue(p1["hadamard_keys_orthonormal"])
        self.assertTrue(p1["l4_zero_error_exact"])
        self.assertTrue(p1["k5_unit_norm_exact"])
        self.assertEqual(p1["universal_capacity_lb"], "106/5")
        self.assertEqual(p1["l5_parseval_error_sq"], "212/5")
        self.assertTrue(p1["parseval_identity_exact"])
        self.assertTrue(p1["state_hashes_distinct"])
        self.assertTrue(p1["intervening_orth_turn_persists"])
        self.assertEqual(p1["margin_after_orth_turn"], "-83/25")
        self.assertTrue(p1["channel2b_tomography"]["zero_delta_w"])
        self.assertEqual(p1["channel2b_tomography"]["margin_before"], "2")
        self.assertEqual(p1["channel2b_tomography"]["margin_after"], "-83/25")
        self.assertEqual(p1["channel2b_tomography"]["margin_delta"], "-133/25")
        self.assertEqual(p1["channel2b_tomography"]["delta_s_rank"], 1)
        self.assertEqual(p1["channel2b_tomography"]["delta_s_schatten_s4"], "1")
        self.assertTrue(p1["orthogonal_conjugation_invariance"]["all_invariants_identical"])
        self.assertFalse(p1["benign_nullspace_control"]["phase_crossed"])
        self.assertEqual(p1["benign_nullspace_control"]["margin_delta"], "0")
        self.assertEqual(len(p1["general_rank_r_nuclear_frob_bounds"]), 4)
        for row in p1["general_rank_r_nuclear_frob_bounds"]:
            self.assertTrue(row["nuclear_bracket_exact"])
            self.assertTrue(row["s4_lower_bound_exact"])

        p2 = p["pillar2_yield_wall_and_s2_cohomology"]
        wall = p2["yield_wall_advection_zero_dw"]
        self.assertEqual(wall["wall_x_t0"], "1")
        self.assertEqual(wall["wall_x_t1"], "4")
        self.assertEqual(wall["wall_displacement"], "3")
        self.assertEqual(wall["gdn2_injection_rank"], 1)
        self.assertEqual(wall["gdn2_injection_schatten_s4"], "1")
        self.assertTrue(wall["gdn2_key_overwrite_exact"])
        self.assertEqual(wall["gdn2_wall_tomography"]["margin_before"], "1/2")
        self.assertEqual(wall["gdn2_wall_tomography"]["margin_after"], "-5/8")
        self.assertEqual(wall["pure_rank1_lift_tomography"]["delta_s_rank"], 1)
        self.assertEqual(wall["pure_rank1_lift_tomography"]["delta_s_schatten_s4"], "1")
        self.assertFalse(wall["static_feedforward_control"]["phase_crossed"])
        self.assertTrue(wall["so2_conjugation_invariance"]["all_invariants_identical"])

        coh = p2["s2_cohomological_obstruction"]
        self.assertEqual(coh["euler_characteristic"], 2)
        self.assertTrue(coh["d1_d0_identically_zero"])
        self.assertTrue(coh["closed_s2_boundary_zero"])
        self.assertEqual(coh["betti_numbers"], [1, 0, 1])
        self.assertEqual(coh["hodge_inner_product"], 0)
        self.assertTrue(coh["hodge_pythagorean_exact"])
        self.assertEqual(coh["s2_basis_fluxes_zero_sum_count"], 12)
        self.assertEqual(coh["gauss_stokes_positive_sum"], 13)
        self.assertEqual(coh["gauss_stokes_negative_sum"], -13)
        self.assertEqual(coh["gauss_stokes_net_sum"], 0)
        self.assertEqual(coh["relu_global_div_residual"], -4)
        self.assertTrue(coh["relu_violates_gauss_stokes"])
        self.assertEqual(coh["commutator_relu_delta1_sum"], 13)
        self.assertTrue(coh["relu_delta1_non_commutative"])

        p3 = p["pillar3_iso_frobenius_and_4ch_airlock"]
        self.assertTrue(p3["iso_frobenius_state_separation"]["iso_frobenius_matched_exact"])
        self.assertTrue(p3["iso_frobenius_state_separation"]["opposite_phase_outcome_at_equal_frobenius"])
        self.assertEqual(p3["dpi_iso_frobenius_weight_anchor"]["toy_64x16_frob_gap"], "0")
        self.assertEqual(p3["dpi_iso_frobenius_weight_anchor"]["toy_64x16_concentration_ratio_factor"], "32")
        self.assertEqual(p3["dpi_iso_frobenius_weight_anchor"]["analytical_two_row_min_concentration"], "75968")
        self.assertTrue(p3["four_channel_state_transport_airlock"]["airlock_certified"])

    def test_envelope_and_replay_tampers(self) -> None:
        cert = oracle.build_standalone_certificate()
        self._assert_err("CERT_NOT_OBJECT", oracle.verify_certificate_payload, "bad")
        self._assert_err("INVALID_CERT_KEYS", oracle.verify_certificate_payload, {"only": 1})

        for field, bad_val, code in (
            ("schema_version", "wrong", "INVALID_SCHEMA"),
            ("track_id", "wrong", "INVALID_TRACK_ID"),
            ("oracle_class", "empirical", "INVALID_ORACLE_CLASS"),
            ("novelty_tier", "N0", "INVALID_NOVELTY_TIER"),
        ):
            c = copy.deepcopy(cert)
            c[field] = bad_val
            self._assert_err(code, oracle.verify_certificate_payload, c, full_replay=False)

        c_pobj = copy.deepcopy(cert)
        c_pobj["payload"] = []
        self._assert_err("PAYLOAD_NOT_OBJECT", oracle.verify_certificate_payload, c_pobj, full_replay=False)

        c_pkeys = copy.deepcopy(cert)
        c_pkeys["payload"]["extra"] = 1
        self._assert_err("INVALID_PAYLOAD_KEYS", oracle.verify_certificate_payload, c_pkeys, full_replay=False)

        for field, bad_val, code in (
            ("oracle_class", "approx", "INVALID_ORACLE_CLASS"),
            ("novelty_tier", "N2", "INVALID_NOVELTY_TIER"),
            ("prior_art_cs13_anchors", "abcdef", "INVALID_CS13_ANCHORS"),
            ("prior_art_cs13_anchors", ["a"], "INVALID_CS13_ANCHORS"),
            ("measured_live_model_weights", True, "INVALID_LAW4_FLAG"),
            ("zero_trust_path_floats", False, "INVALID_HYGIENE_FLAG"),
        ):
            c = copy.deepcopy(cert)
            c["payload"][field] = bad_val
            self._assert_err(code, oracle.verify_certificate_payload, c, full_replay=False)

        c_psha = copy.deepcopy(cert)
        c_psha["payload_sha256"] = "0" * 64
        self._assert_err("PAYLOAD_SHA_MISMATCH", oracle.verify_certificate_payload, c_psha, full_replay=False)

        c_csha = copy.deepcopy(cert)
        c_csha["certificate_sha256"] = "0" * 64
        self._assert_err("CERT_SHA_MISMATCH", oracle.verify_certificate_payload, c_csha, full_replay=False)

        # Re-signed payload tamper passes full_replay=False in oracle, fails full_replay=True in oracle,
        # AND fails secondary_audit_payload / verify_certificate_dict(full_replay=False) in audit!
        c_resigned = copy.deepcopy(cert)
        c_resigned["payload"]["prior_art_cs13_anchors"][0] = "tampered"
        c_resigned = _resign_cert(c_resigned)
        self.assertTrue(oracle.verify_certificate_payload(c_resigned, full_replay=False)["valid"])
        self._assert_err("REPLAY_MISMATCH", oracle.verify_certificate_payload, c_resigned, full_replay=True)
        self._assert_err("PAYLOAD_VALUE_MISMATCH", audit.verify_certificate_dict, c_resigned, full_replay=False)

    def test_verify_algebraic_invariants_all_codes(self) -> None:
        base_p = oracle.build_standalone_certificate()["payload"]
        self.assertTrue(audit.verify_algebraic_invariants(base_p)["algebraic_checks_passed"])
        self._assert_err("PAYLOAD_NOT_OBJECT", audit.verify_algebraic_invariants, "bad")

        # Direct missing field / wrong container checks
        p_miss = copy.deepcopy(base_p)
        del p_miss["pillar1_gdn2_zero_dw_state_transport"]
        self._assert_err("MISSING_FIELD", audit.verify_algebraic_invariants, p_miss)
        p_notdict = copy.deepcopy(base_p)
        p_notdict["pillar1_gdn2_zero_dw_state_transport"] = 1
        self._assert_err("FIELD_NOT_OBJECT", audit.verify_algebraic_invariants, p_notdict)
        p_miss_r = copy.deepcopy(base_p)
        del p_miss_r["pillar1_gdn2_zero_dw_state_transport"]["channel2b_tomography"]["margin_before"]
        self._assert_err("MISSING_FIELD", audit.verify_algebraic_invariants, p_miss_r)
        p_miss_l = copy.deepcopy(base_p)
        del p_miss_l["pillar3_iso_frobenius_and_4ch_airlock"]["four_channel_state_transport_airlock"]["benign_controls"]
        self._assert_err("MISSING_FIELD", audit.verify_algebraic_invariants, p_miss_l)
        p_notlist = copy.deepcopy(base_p)
        p_notlist["pillar3_iso_frobenius_and_4ch_airlock"]["four_channel_state_transport_airlock"]["benign_controls"] = {}
        self._assert_err("FIELD_NOT_LIST", audit.verify_algebraic_invariants, p_notlist)

        # Boundary: cs_lhs == cs_rhs PASSES verify_algebraic_invariants (kills <= -> <)
        p_cs_eq = copy.deepcopy(base_p)
        p_cs_eq["pillar1_gdn2_zero_dw_state_transport"]["channel2b_tomography"]["cauchy_schwarz_upper_bound"] = "17689/625"
        self.assertTrue(audit.verify_algebraic_invariants(p_cs_eq)["algebraic_checks_passed"])
        # Still rejected by secondary_audit_payload exact equality!
        self._assert_err("PAYLOAD_VALUE_MISMATCH", audit.secondary_audit_payload, p_cs_eq)

        # Exact individual algebraic violations
        mutations: list[tuple[list, object, str]] = [
            (["pillar1_gdn2_zero_dw_state_transport", "channel2b_tomography", "margin_before"], "1", "ALGEBRAIC_P1_MARGIN"),
            (["pillar1_gdn2_zero_dw_state_transport", "channel2b_tomography", "margin_after"], "-1", "ALGEBRAIC_P1_MARGIN"),
            (["pillar1_gdn2_zero_dw_state_transport", "channel2b_tomography", "margin_delta"], "-1", "ALGEBRAIC_P1_MARGIN"),
            (["pillar1_gdn2_zero_dw_state_transport", "channel2b_tomography", "delta_s_frob_norm_sq"], "10", "ALGEBRAIC_P1_FROB"),
            (["pillar1_gdn2_zero_dw_state_transport", "universal_capacity_lb"], "10", "ALGEBRAIC_P1_CAPACITY"),
            (["pillar1_gdn2_zero_dw_state_transport", "l5_parseval_error_sq"], "10", "ALGEBRAIC_P1_PARSEVAL"),
            (["pillar1_gdn2_zero_dw_state_transport", "channel2b_tomography", "delta_s_schatten_s4"], "1/2", "ALGEBRAIC_P1_RANK1"),
            (["pillar1_gdn2_zero_dw_state_transport", "channel2b_tomography", "cauchy_schwarz_margin_sq"], "1", "ALGEBRAIC_P1_CS"),
            (["pillar1_gdn2_zero_dw_state_transport", "channel2b_tomography", "cauchy_schwarz_upper_bound"], "1", "ALGEBRAIC_P1_CS"),
            (["pillar2_yield_wall_and_s2_cohomology", "yield_wall_advection_zero_dw", "wall_x_t0"], "2", "ALGEBRAIC_P2_WALL"),
            (["pillar2_yield_wall_and_s2_cohomology", "yield_wall_advection_zero_dw", "wall_x_t1"], "5", "ALGEBRAIC_P2_WALL"),
            (["pillar2_yield_wall_and_s2_cohomology", "yield_wall_advection_zero_dw", "wall_displacement"], "2", "ALGEBRAIC_P2_WALL"),
            (["pillar2_yield_wall_and_s2_cohomology", "s2_cohomological_obstruction", "gauss_stokes_positive_sum"], 12, "ALGEBRAIC_P2_GS"),
            (["pillar2_yield_wall_and_s2_cohomology", "s2_cohomological_obstruction", "gauss_stokes_negative_sum"], -12, "ALGEBRAIC_P2_GS"),
            (["pillar2_yield_wall_and_s2_cohomology", "s2_cohomological_obstruction", "gauss_stokes_net_sum"], 1, "ALGEBRAIC_P2_GS"),
            (["pillar2_yield_wall_and_s2_cohomology", "s2_cohomological_obstruction", "relu_global_div_residual"], 0, "ALGEBRAIC_P2_RELU"),
            (["pillar2_yield_wall_and_s2_cohomology", "s2_cohomological_obstruction", "commutator_relu_delta1_sum"], 0, "ALGEBRAIC_P2_COMM"),
            (["pillar3_iso_frobenius_and_4ch_airlock", "iso_frobenius_state_separation", "frobenius_energy_gap"], "1", "ALGEBRAIC_P3_ISO"),
            (["pillar3_iso_frobenius_and_4ch_airlock", "dpi_iso_frobenius_weight_anchor", "analytical_vocab_rows"], 100, "ALGEBRAIC_P3_DPI"),
            (["pillar3_iso_frobenius_and_4ch_airlock", "dpi_iso_frobenius_weight_anchor", "analytical_vocab_rows"], 2, "ALGEBRAIC_P3_DPI"),
            (["pillar3_iso_frobenius_and_4ch_airlock", "dpi_iso_frobenius_weight_anchor", "toy_64x16_concentration_ratio_factor"], "16", "ALGEBRAIC_P3_DPI"),
        ]
        for path, val, code in mutations:
            p_mut = copy.deepcopy(base_p)
            cur = p_mut
            for k in path[:-1]:
                cur = cur[k]
            cur[path[-1]] = val
            self._assert_err(code, audit.verify_algebraic_invariants, p_mut)

        # Special coupled cases to kill each pinned anchor independently of sum/diff checks
        coupled_cases = [
            # m0 != 2 while m1==-83/25, m1-m0==dm, dm^2==cs_lhs
            (
                {
                    ("pillar1_gdn2_zero_dw_state_transport", "channel2b_tomography", "margin_before"): "1",
                    ("pillar1_gdn2_zero_dw_state_transport", "channel2b_tomography", "margin_delta"): "-108/25",
                    ("pillar1_gdn2_zero_dw_state_transport", "channel2b_tomography", "cauchy_schwarz_margin_sq"): "11664/625",
                },
                "ALGEBRAIC_P1_MARGIN",
            ),
            # m1 != -83/25 while m0==2, m1-m0==dm, dm^2==cs_lhs
            (
                {
                    ("pillar1_gdn2_zero_dw_state_transport", "channel2b_tomography", "margin_after"): "-1",
                    ("pillar1_gdn2_zero_dw_state_transport", "channel2b_tomography", "margin_delta"): "-3",
                    ("pillar1_gdn2_zero_dw_state_transport", "channel2b_tomography", "cauchy_schwarz_margin_sq"): "9",
                },
                "ALGEBRAIC_P1_MARGIN",
            ),
            # x0 != 1 while x1==4, x1-x0==dx
            (
                {
                    ("pillar2_yield_wall_and_s2_cohomology", "yield_wall_advection_zero_dw", "wall_x_t0"): "2",
                    ("pillar2_yield_wall_and_s2_cohomology", "yield_wall_advection_zero_dw", "wall_displacement"): "2",
                },
                "ALGEBRAIC_P2_WALL",
            ),
            # x1 != 4 while x0==1, x1-x0==dx
            (
                {
                    ("pillar2_yield_wall_and_s2_cohomology", "yield_wall_advection_zero_dw", "wall_x_t1"): "5",
                    ("pillar2_yield_wall_and_s2_cohomology", "yield_wall_advection_zero_dw", "wall_displacement"): "4",
                },
                "ALGEBRAIC_P2_WALL",
            ),
            # gs_pos != 13 while gs_neg==-13, gs_pos+gs_neg==gs_net
            (
                {
                    ("pillar2_yield_wall_and_s2_cohomology", "s2_cohomological_obstruction", "gauss_stokes_positive_sum"): 12,
                    ("pillar2_yield_wall_and_s2_cohomology", "s2_cohomological_obstruction", "gauss_stokes_net_sum"): -1,
                },
                "ALGEBRAIC_P2_GS",
            ),
            # gs_neg != -13 while gs_pos==13, gs_pos+gs_neg==gs_net
            (
                {
                    ("pillar2_yield_wall_and_s2_cohomology", "s2_cohomological_obstruction", "gauss_stokes_negative_sum"): -12,
                    ("pillar2_yield_wall_and_s2_cohomology", "s2_cohomological_obstruction", "gauss_stokes_net_sum"): 1,
                },
                "ALGEBRAIC_P2_GS",
            ),
            # vocab_rows=2 AND min_conc=1 kills two_row_conc == 75968 independently
            (
                {
                    ("pillar3_iso_frobenius_and_4ch_airlock", "dpi_iso_frobenius_weight_anchor", "analytical_vocab_rows"): 2,
                    ("pillar3_iso_frobenius_and_4ch_airlock", "dpi_iso_frobenius_weight_anchor", "analytical_two_row_min_concentration"): "1",
                },
                "ALGEBRAIC_P3_DPI",
            ),
        ]
        for edits, code in coupled_cases:
            p_mut = copy.deepcopy(base_p)
            for path, val in edits.items():
                cur = p_mut
                for k in path[:-1]:
                    cur = cur[k]
                cur[path[-1]] = val
            self._assert_err(code, audit.verify_algebraic_invariants, p_mut)

        # Airlock list count, item type, and decision checks
        for lst_key in ("benign_controls", "negative_controls"):
            p_short = copy.deepcopy(base_p)
            p_short["pillar3_iso_frobenius_and_4ch_airlock"]["four_channel_state_transport_airlock"][lst_key].pop()
            self._assert_err("ALGEBRAIC_P3_AIRLOCK", audit.verify_algebraic_invariants, p_short)

            p_baditem = copy.deepcopy(base_p)
            p_baditem["pillar3_iso_frobenius_and_4ch_airlock"]["four_channel_state_transport_airlock"][lst_key][0] = "bad"
            self._assert_err("ALGEBRAIC_P3_AIRLOCK", audit.verify_algebraic_invariants, p_baditem)

            p_flip = copy.deepcopy(base_p)
            p_flip["pillar3_iso_frobenius_and_4ch_airlock"]["four_channel_state_transport_airlock"][lst_key][0]["airlock_4ch_decision"] = "WRONG"
            self._assert_err("ALGEBRAIC_P3_AIRLOCK", audit.verify_algebraic_invariants, p_flip)

        # _exact_json_tree_equal direct branch kills (type, keys, list len, value)
        self._assert_err("SCHEMA_TYPE_MISMATCH", audit._exact_json_tree_equal, 1, True)
        self._assert_err("SCHEMA_KEYS_MISMATCH", audit._exact_json_tree_equal, {"a": 1, "b": 2}, {"a": 1})
        self._assert_err("SCHEMA_LIST_LEN_MISMATCH", audit._exact_json_tree_equal, [1], [1, 2])
        self._assert_err("PAYLOAD_VALUE_MISMATCH", audit._exact_json_tree_equal, "a", "b")

        # Direct secondary_audit_payload float & subclass defenses
        p_sub = copy.deepcopy(base_p)
        p_sub["novelty_tier"] = _StrSub("N1")
        self._assert_err("INVALID_JSON_VALUE", audit.secondary_audit_payload, p_sub)
        p_flt = copy.deepcopy(base_p)
        p_flt["extra_float"] = json.loads("0.25")
        self._assert_err("INVALID_JSON_VALUE", audit.secondary_audit_payload, p_flt)


class TestFilesystemSecurityAndCLI(unittest.TestCase):
    def _assert_err(self, expected_code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.ZeroDwStateTransportError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, expected_code)

    def test_strict_read_write_and_filesystem_defenses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # 1. Invalid path inputs
            self._assert_err("INVALID_PATH_NUL", audit.read_regular_file_bytes_strict, tmp + "/a\x00b")
            self._assert_err("PATH_IS_DIRECTORY", audit.read_regular_file_bytes_strict, tmp + "/")
            self._assert_err("INVALID_PATH", audit.read_regular_file_bytes_strict, ".")
            self._assert_err("INVALID_LEAF", audit.read_regular_file_bytes_strict, tmp + "/..")
            self._assert_err("INVALID_WRITE_DATA", audit.atomic_write_regular_file_0600, tmp + "/x", "not_bytes")

            # 2. Atomic 0o600 write + read + exact max_bytes boundary
            target = os.path.join(tmp, "cert.json")
            summary = audit.write_certificate_file(target)
            self.assertTrue(summary["written"])
            st = os.lstat(target)
            self.assertEqual(stat.S_IMODE(st.st_mode), 0o600)
            raw = audit.read_regular_file_bytes_strict(target, max_bytes=len(oracle.canonical_json_bytes(oracle.build_standalone_certificate())))
            self.assertEqual(len(raw), summary["bytes"])
            self._assert_err("FILE_TOO_LARGE", audit.read_regular_file_bytes_strict, target, max_bytes=summary["bytes"] - 1)
            self.assertTrue(audit.check_certificate_file(target)["valid"])

            # 3. Invalid UTF-8 & non-canonical pretty-printed JSON rejected cleanly
            bad_utf8 = os.path.join(tmp, "bad.bin")
            audit.atomic_write_regular_file_0600(bad_utf8, b"\xff\xfe")
            self._assert_err("INVALID_UTF8", audit.check_certificate_file, bad_utf8)
            pretty_path = os.path.join(tmp, "pretty.json")
            pretty_bytes = (json.dumps(oracle.build_standalone_certificate(), indent=2, sort_keys=True) + "\n").encode("ascii")
            audit.atomic_write_regular_file_0600(pretty_path, pretty_bytes)
            self._assert_err("NON_CANONICAL_JSON_BYTES", audit.check_certificate_file, pretty_path)

            # 4. Symlink ancestor & symlink leaf on read and write
            real_sub = os.path.join(tmp, "real_sub")
            os.mkdir(real_sub)
            sym_sub = os.path.join(tmp, "sym_sub")
            os.symlink(real_sub, sym_sub)
            self._assert_err("SYMLINK_FORBIDDEN", audit.read_regular_file_bytes_strict, os.path.join(sym_sub, "f"))
            self._assert_err("SYMLINK_FORBIDDEN", audit.atomic_write_regular_file_0600, os.path.join(sym_sub, "f"), b"x")

            sym_leaf = os.path.join(tmp, "sym_leaf")
            os.symlink(target, sym_leaf)
            self._assert_err("SYMLINK_FORBIDDEN", audit.read_regular_file_bytes_strict, sym_leaf)
            self._assert_err("SYMLINK_FORBIDDEN", audit.atomic_write_regular_file_0600, sym_leaf, b"x")

            # 5. Missing ancestor & missing leaf
            self._assert_err("DIR_OPEN_ERROR", audit.read_regular_file_bytes_strict, os.path.join(tmp, "no_such_dir", "f"))
            self._assert_err("FILE_READ_ERROR", audit.read_regular_file_bytes_strict, os.path.join(tmp, "missing.json"))

            # 6. Scratch os.mkfifo non-regular file inside TemporaryDirectory
            fifo_path = os.path.join(tmp, "scratch.fifo")
            os.mkfifo(fifo_path, 0o600)
            self._assert_err("NON_REGULAR_FILE", audit.read_regular_file_bytes_strict, fifo_path)
            self._assert_err("NON_REGULAR_FILE", audit.atomic_write_regular_file_0600, fifo_path, b"x")

            # 7. Directory target rejected as NON_REGULAR_FILE
            self._assert_err("NON_REGULAR_FILE", audit.read_regular_file_bytes_strict, real_sub)
            self._assert_err("NON_REGULAR_FILE", audit.atomic_write_regular_file_0600, real_sub, b"x")

            # 8. Hardlink defense (st_nlink > 1)
            victim = os.path.join(tmp, "victim.json")
            alias = os.path.join(tmp, "alias.json")
            audit.atomic_write_regular_file_0600(victim, b"canary_payload")
            os.link(victim, alias)
            self._assert_err("HARDLINK_FORBIDDEN", audit.atomic_write_regular_file_0600, victim, b"overwrite")
            with open(alias, "rb") as alias_fh:
                self.assertEqual(alias_fh.read(), b"canary_payload")

            # 9. chmod 000 unreadable regular file -> structured FILE_READ_ERROR
            unreadable = os.path.join(tmp, "no_read.json")
            audit.atomic_write_regular_file_0600(unreadable, b"{}")
            os.chmod(unreadable, 0o000)
            try:
                if os.geteuid() != 0:
                    self._assert_err("FILE_READ_ERROR", audit.read_regular_file_bytes_strict, unreadable)
            finally:
                os.chmod(unreadable, 0o600)

            # 10. /proc/kallsyms streaming cap check (0-byte st_size pseudo-file)
            if os.path.exists("/proc/kallsyms"):
                self._assert_err("FILE_TOO_LARGE", audit.read_regular_file_bytes_strict, "/proc/kallsyms", max_bytes=1024)

    def test_relative_paths_symlinked_pwd_and_deleted_cwd(self) -> None:
        orig_cwd = os.getcwd()
        orig_pwd = os.environ.get("PWD")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                real_dir = os.path.join(tmp, "real_dir")
                os.mkdir(real_dir)
                sym_dir = os.path.join(tmp, "sym_dir")
                os.symlink(real_dir, sym_dir)
                sym_other = os.path.join(tmp, "sym_other")
                os.symlink(tmp, sym_other)

                os.chdir(real_dir)
                # Empty PWD, relative PWD, nonexistent PWD, different-dir symlink PWD -> relative write/read succeeds
                for pwd_val in ("", "rel/pwd", "/nonexistent_s50_pwd_dir", sym_other):
                    os.environ["PWD"] = pwd_val
                    audit.atomic_write_regular_file_0600("./rel_ok.json", b"ok")
                    self.assertEqual(audit.read_regular_file_bytes_strict("./rel_ok.json"), b"ok")

                # Symlinked logical $PWD (including '/./' component) -> SYMLINK_FORBIDDEN
                os.environ["PWD"] = os.path.join(tmp, ".", "sym_dir")
                self._assert_err("SYMLINK_FORBIDDEN", audit.read_regular_file_bytes_strict, "rel_ok.json")

                # Deleted CWD -> CWD_UNAVAILABLE
                gone_dir = os.path.join(tmp, "gone_dir")
                os.mkdir(gone_dir)
                os.chdir(gone_dir)
                os.environ["PWD"] = gone_dir
                os.rmdir(gone_dir)
                self._assert_err("CWD_UNAVAILABLE", audit.read_regular_file_bytes_strict, "any.json")
        finally:
            os.chdir(orig_cwd)
            if orig_pwd is None:
                os.environ.pop("PWD", None)
            else:
                os.environ["PWD"] = orig_pwd

    def test_mocked_io_error_defenses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "mock.json")
            audit.atomic_write_regular_file_0600(target, b"init")

            # Short write (os.write returns 0)
            with mock.patch("os.write", return_value=0):
                self._assert_err("SHORT_WRITE", audit.atomic_write_regular_file_0600, target, b"abc")

            # Temp creation EEXIST exhaustion -> TMP_CREATE_EXHAUSTED
            real_open = os.open

            def _eexist_on_excl(path, flags, *args, **kwargs):
                if flags & os.O_EXCL:
                    raise FileExistsError(17, "File exists")
                return real_open(path, flags, *args, **kwargs)

            with mock.patch("os.open", side_effect=_eexist_on_excl):
                self._assert_err("TMP_CREATE_EXHAUSTED", audit.atomic_write_regular_file_0600, target, b"abc")

            # Pre-replace temp hardlink probe (fstat reports st_nlink == 2)
            real_fstat = os.fstat

            class _FakeStat:
                def __init__(self, st_obj):
                    self.st_mode = st_obj.st_mode
                    self.st_nlink = 2

            with mock.patch("os.fstat", side_effect=lambda fd: _FakeStat(real_fstat(fd))):
                self._assert_err("HARDLINK_FORBIDDEN", audit.atomic_write_regular_file_0600, target, b"abc")

            # os.read raises OSError -> FILE_READ_ERROR
            with mock.patch("os.read", side_effect=OSError(5, "EIO")):
                self._assert_err("FILE_READ_ERROR", audit.read_regular_file_bytes_strict, target)

            # os.lstat raises OSError -> FILE_STAT_ERROR
            with mock.patch("os.lstat", side_effect=OSError(13, "EACCES")):
                self._assert_err("FILE_STAT_ERROR", audit.atomic_write_regular_file_0600, target, b"abc")

            # os.open raises OSError on tmp creation -> TMP_CREATE_ERROR
            def _eacces_on_excl(path, flags, *args, **kwargs):
                if flags & os.O_EXCL:
                    raise OSError(13, "EACCES")
                return real_open(path, flags, *args, **kwargs)

            with mock.patch("os.open", side_effect=_eacces_on_excl):
                self._assert_err("TMP_CREATE_ERROR", audit.atomic_write_regular_file_0600, target, b"abc")

            # os.replace raises OSError -> ATOMIC_WRITE_ERROR
            with mock.patch("os.replace", side_effect=OSError(18, "EXDEV")):
                self._assert_err("ATOMIC_WRITE_ERROR", audit.atomic_write_regular_file_0600, target, b"abc")

    def test_concurrency_and_kernel_races(self) -> None:
        cert_bytes = oracle.canonical_json_bytes(oracle.build_standalone_certificate())
        with tempfile.TemporaryDirectory() as tmp:
            # 1. 16T distinct files + 16T same-target atomic 0o600 writes
            errors: list[BaseException] = []

            def _distinct_worker(idx: int) -> None:
                try:
                    p = os.path.join(tmp, f"d_{idx}.json")
                    audit.atomic_write_regular_file_0600(p, cert_bytes)
                    self.assertEqual(stat.S_IMODE(os.lstat(p).st_mode), 0o600)
                except BaseException as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=_distinct_worker, args=(i,)) for i in range(16)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])

            shared = os.path.join(tmp, "shared.json")
            bar16 = threading.Barrier(16)

            def _same_worker() -> None:
                try:
                    bar16.wait()
                    audit.atomic_write_regular_file_0600(shared, cert_bytes)
                except BaseException as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=_same_worker) for _ in range(16)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            self.assertEqual(audit.read_regular_file_bytes_strict(shared), cert_bytes)
            self.assertEqual(stat.S_IMODE(os.lstat(shared).st_mode), 0o600)

            # 2. 80T barrier burst
            burst_target = os.path.join(tmp, "burst80.json")
            bar80 = threading.Barrier(80)

            def _burst_worker() -> None:
                try:
                    bar80.wait()
                    audit.atomic_write_regular_file_0600(burst_target, cert_bytes)
                except BaseException as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=_burst_worker) for _ in range(80)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            self.assertEqual(audit.read_regular_file_bytes_strict(burst_target), cert_bytes)

            # 3. 420-iter concurrent hardlink race
            hl_target = os.path.join(tmp, "hl_target.json")
            hl_alias = os.path.join(tmp, "hl_alias.json")
            audit.atomic_write_regular_file_0600(hl_target, b"initial")
            stop_hl = threading.Event()

            def _linker() -> None:
                while not stop_hl.is_set():
                    try:
                        os.link(hl_target, hl_alias)
                    except OSError:
                        pass
                    try:
                        os.unlink(hl_alias)
                    except OSError:
                        pass

            hl_thread = threading.Thread(target=_linker)
            hl_thread.start()
            try:
                for _ in range(420):
                    try:
                        audit.atomic_write_regular_file_0600(hl_target, b"updated")
                    except oracle.ZeroDwStateTransportError as exc:
                        self.assertEqual(exc.code, "HARDLINK_FORBIDDEN")
            finally:
                stop_hl.set()
                hl_thread.join()

    def test_linux_renameat2_toctou_race(self) -> None:
        if sys.platform != "linux":
            self.skipTest("renameat2(RENAME_EXCHANGE) requires Linux")
        try:
            libc = ctypes.CDLL("libc.so.6", use_errno=True)
            renameat2_fn = libc.renameat2
        except (OSError, AttributeError):
            self.skipTest("libc.renameat2 unavailable on this host")
        renameat2_fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameat2_fn.restype = ctypes.c_int

        with tempfile.TemporaryDirectory() as tmp:
            decoy_dir = os.path.join(tmp, "decoy_outside")
            os.mkdir(decoy_dir)
            decoy_file = os.path.join(decoy_dir, "race_leaf.json")
            race_sub = os.path.join(tmp, "race_sub")
            os.mkdir(race_sub)
            race_link = os.path.join(tmp, "race_link")
            os.symlink(decoy_dir, race_link)
            rename_exchange = 2
            at_fdcwd = -100
            b_sub = os.fsencode(race_sub)
            b_lnk = os.fsencode(race_link)

            if renameat2_fn(at_fdcwd, b_sub, at_fdcwd, b_lnk, rename_exchange) != 0:
                self.skipTest("renameat2(RENAME_EXCHANGE) unsupported on this filesystem")
            renameat2_fn(at_fdcwd, b_sub, at_fdcwd, b_lnk, rename_exchange)

            stop_ev = threading.Event()

            def _swapper() -> None:
                while not stop_ev.is_set():
                    renameat2_fn(at_fdcwd, b_sub, at_fdcwd, b_lnk, rename_exchange)

            sw_thread = threading.Thread(target=_swapper)
            sw_thread.start()
            try:
                race_target = os.path.join(race_sub, "race_leaf.json")
                for _ in range(520):
                    try:
                        audit.atomic_write_regular_file_0600(race_target, b"ok")
                    except oracle.ZeroDwStateTransportError:
                        pass
            finally:
                stop_ev.set()
                sw_thread.join()
            self.assertFalse(os.path.exists(decoy_file))

    def test_linux_renameat2_non_linux_and_unavailable_skip(self) -> None:
        class _FailingLibc:
            @staticmethod
            def renameat2(_dfd1: int, _p1: bytes, _dfd2: int, _p2: bytes, _flags: int) -> int:
                return -1

        class _MissingLibc:
            pass

        with mock.patch.object(sys, "platform", "darwin"):
            with self.assertRaises(unittest.SkipTest):
                self.test_linux_renameat2_toctou_race()
        with mock.patch.object(sys, "platform", "linux"), mock.patch.object(ctypes, "CDLL", side_effect=OSError("no libc")):
            with self.assertRaises(unittest.SkipTest):
                self.test_linux_renameat2_toctou_race()
        with mock.patch.object(sys, "platform", "linux"), mock.patch.object(ctypes, "CDLL", return_value=_MissingLibc()):
            with self.assertRaises(unittest.SkipTest):
                self.test_linux_renameat2_toctou_race()
        with mock.patch.object(sys, "platform", "linux"), mock.patch.object(ctypes, "CDLL", return_value=_FailingLibc()):
            with self.assertRaises(unittest.SkipTest):
                self.test_linux_renameat2_toctou_race()

    def test_darwin_system_prefix_normalization(self) -> None:
        class _FakeSt:
            def __init__(self, st_mode: int, st_uid: int) -> None:
                self.st_mode = st_mode
                self.st_uid = st_uid

        root_lnk = _FakeSt(stat.S_IFLNK | 0o777, 0)
        user_lnk = _FakeSt(stat.S_IFLNK | 0o777, 501)
        root_dir = _FakeSt(stat.S_IFDIR | 0o755, 0)

        def _fake_readlink(p: str) -> str:
            if p == "/var":
                return "private/var"
            if p == "/tmp":
                return "/private/tmp"
            if p == "/etc":
                return "private/etc"
            raise OSError("unexpected readlink")

        # 1. Non-Darwin never normalizes
        with mock.patch.object(audit.sys, "platform", "linux"):
            self.assertEqual(audit._normalize_darwin_system_prefix(["var", "folders", "x"]), ["var", "folders", "x"])

        # 2. Valid root-owned Darwin aliases normalize (/var, /tmp, /etc); empty, '..', & non-alias unchanged
        with (
            mock.patch.object(audit.sys, "platform", "darwin"),
            mock.patch.object(audit.os, "lstat", return_value=root_lnk),
            mock.patch.object(audit.os, "readlink", side_effect=_fake_readlink),
        ):
            self.assertEqual(
                audit._normalize_darwin_system_prefix(["var", "folders", "xx"]),
                ["private", "var", "folders", "xx"],
            )
            self.assertEqual(audit._normalize_darwin_system_prefix(["tmp"]), ["private", "tmp"])
            self.assertEqual(audit._normalize_darwin_system_prefix(["etc", "hosts"]), ["private", "etc", "hosts"])
            self.assertEqual(audit._normalize_darwin_system_prefix([]), [])
            self.assertEqual(audit._normalize_darwin_system_prefix(["tmp", "..", "etc"]), ["tmp", "..", "etc"])
            self.assertEqual(audit._normalize_darwin_system_prefix(["usr", "local"]), ["usr", "local"])

            # End-to-end _open_parent_dir_fd_nofollow routes normalized ancestors without normalizing leaf '/tmp'
            seen_chains: list[list[str]] = []

            def _rec_chain(comps: list[str], start_fd: int) -> int:
                seen_chains.append(list(comps))
                return start_fd

            with mock.patch.object(audit, "_open_dir_chain_nofollow", side_effect=_rec_chain):
                fd1, leaf1 = audit._open_parent_dir_fd_nofollow("/var/folders/xx/cert.json")
                os.close(fd1)
                self.assertEqual(leaf1, "cert.json")
                fd2, leaf2 = audit._open_parent_dir_fd_nofollow("/tmp")
                os.close(fd2)
                self.assertEqual(leaf2, "tmp")
            self.assertEqual(seen_chains, [["private", "var", "folders", "xx"], []])

        # 3. Non-root symlink, non-symlink dir, OSError, and unexpected readlink target all refuse normalization
        with (
            mock.patch.object(audit.sys, "platform", "darwin"),
            mock.patch.object(audit.os, "lstat", return_value=user_lnk),
            mock.patch.object(audit.os, "readlink", side_effect=_fake_readlink),
        ):
            self.assertEqual(audit._normalize_darwin_system_prefix(["var", "x"]), ["var", "x"])

        with (
            mock.patch.object(audit.sys, "platform", "darwin"),
            mock.patch.object(audit.os, "lstat", return_value=root_dir),
            mock.patch.object(audit.os, "readlink", side_effect=_fake_readlink),
        ):
            self.assertEqual(audit._normalize_darwin_system_prefix(["var", "x"]), ["var", "x"])

        with (
            mock.patch.object(audit.sys, "platform", "darwin"),
            mock.patch.object(audit.os, "lstat", side_effect=OSError("no alias")),
        ):
            self.assertEqual(audit._normalize_darwin_system_prefix(["var", "x"]), ["var", "x"])

        with (
            mock.patch.object(audit.sys, "platform", "darwin"),
            mock.patch.object(audit.os, "lstat", return_value=root_lnk),
            mock.patch.object(audit.os, "readlink", return_value="private/evil"),
        ):
            self.assertEqual(audit._normalize_darwin_system_prefix(["var", "x"]), ["var", "x"])

    def test_cli_modes_and_strict_rejections(self) -> None:
        cert_bytes = oracle.canonical_json_bytes(oracle.build_standalone_certificate()).decode("ascii")
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "cli_cert.json")

            # In-process CLI modes
            for argv in ([], ["--standalone", "--json"]):
                buf_out = io.StringIO()
                with mock.patch.object(sys, "stdout", buf_out):
                    rc = audit.main(argv)
                self.assertEqual(rc, 0)
                self.assertEqual(buf_out.getvalue(), cert_bytes)

            buf_w = io.StringIO()
            with mock.patch.object(sys, "stdout", buf_w):
                rc = audit.main(["--write", out_path])
            self.assertEqual(rc, 0)
            self.assertTrue(json.loads(buf_w.getvalue())["written"])

            buf_c = io.StringIO()
            with mock.patch.object(sys, "stdout", buf_c):
                rc = audit.main(["--check", out_path])
            self.assertEqual(rc, 0)
            self.assertTrue(json.loads(buf_c.getvalue())["valid"])

            # Bad CLI argv inputs -> rc=2, structured JSON on stderr, 0 files created
            for bad_argv, exp_code in (
                ("not_list", "INVALID_ARGV"),
                (_ListSub([]), "INVALID_ARGV"),
                ([_StrSub("--write"), out_path], "INVALID_STR_TYPE"),
                (["--unknown"], "INVALID_CLI_ARGS"),
                (["--write"], "INVALID_CLI_ARGS"),
                (["--check"], "INVALID_CLI_ARGS"),
                (["--other", "foo"], "INVALID_CLI_ARGS"),
                (["--write", "--json"], "FLAG_LIKE_PATH"),
                (["--check", "--json"], "FLAG_LIKE_PATH"),
                (["--write=--json"], "INVALID_CLI_ARGS"),
                (["--check", os.path.join(tmp, "nope.json")], "FILE_READ_ERROR"),
            ):
                buf_err = io.StringIO()
                with mock.patch.object(sys, "stderr", buf_err):
                    rc = audit.main(bad_argv)
                self.assertEqual(rc, 2)
                err_json = json.loads(buf_err.getvalue())
                self.assertFalse(err_json["valid"])
                self.assertEqual(err_json["error_code"], exp_code)

            # Live subprocess non-UTF-8 raw CLI argument bytes -> rc=2, structured JSON, no traceback
            audit_script = os.path.join(_SCRIPT_DIR, "zero_dw_state_transport_audit.py")
            proc_bad = subprocess.run(
                [sys.executable, "-I", "-B", audit_script, b"--check", b"\xff\xfe"],
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc_bad.returncode, 2)
            self.assertNotIn(b"Traceback", proc_bad.stderr)
            self.assertEqual(json.loads(proc_bad.stderr.decode("ascii"))["error_code"], "INVALID_UTF8_SURROGATE")

            # Live subprocess isolated parity against saved file
            proc_emit = subprocess.run(
                [sys.executable, "-I", "-B", audit_script, "--standalone", "--json"],
                capture_output=True,
                check=True,
            )
            self.assertEqual(proc_emit.stdout.decode("ascii"), cert_bytes)


if __name__ == "__main__":
    unittest.main()
