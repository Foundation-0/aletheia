#!/usr/bin/env python3
"""
Track S77 Assertion-Free R5 Hardened Unit Test Suite.

Covers all 4 Wave-4 pillars, exact-Q oracle boundaries, Zone-B fail-closed I/O & JSON attacks,
(0o600, 0o644) committed disk-cert parity + strict 0o600 --write, scratch os.mkfifo probes,
hardlinks, read-only directories, all R9 11-class static Lean 4 bypasses + live Lean 4.36.0 checks,
and 100% mutation/BoolOp kill coverage.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import s77_mellin_wsp_tomography as s77
import verify_s77_mellin_wsp as ver


def _resign(cert: dict) -> dict:
    p_sha = hashlib.sha256(s77.canonical_json_bytes(cert["payload"])).hexdigest()
    env = {
        "schema": cert["schema"],
        "track_id": cert["track_id"],
        "payload_sha256": p_sha,
        "payload": cert["payload"],
    }
    c_sha = hashlib.sha256(s77.canonical_json_bytes(env)).hexdigest()
    return {
        "schema": cert["schema"],
        "track_id": cert["track_id"],
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "payload": cert["payload"],
    }


class TestS77OraclePrimitives(unittest.TestCase):
    def test_error_and_guards(self) -> None:
        err = s77.S77Error("E_CODE", "e msg")
        self.assertEqual(err.code, "E_CODE")
        self.assertEqual(err.message, "e msg")
        self.assertEqual(str(err), "E_CODE: e msg")

        s77.require_ok(True, "OK", "ok")
        for bad in (False, 1, "yes", None):
            with self.assertRaises(s77.S77Error) as ctx:
                s77.require_ok(bad, "BAD_COND", "bad")  # type: ignore[arg-type]
            self.assertEqual(ctx.exception.code, "BAD_COND")

        max_ok = (1 << s77.MAX_INT_BITS) - 1
        self.assertEqual(s77.require_exact_int(max_ok, "m"), max_ok)
        self.assertEqual(s77.require_exact_int(5, "x", min_val=5, max_val=5), 5)
        with self.assertRaises(s77.S77Error) as c1:
            s77.require_exact_int(True, "b")
        self.assertEqual(c1.exception.code, "INVALID_INT")
        with self.assertRaises(s77.S77Error) as c2:
            s77.require_exact_int(1 << s77.MAX_INT_BITS, "big")
        self.assertEqual(c2.exception.code, "INT_BIT_LIMIT")
        with self.assertRaises(s77.S77Error) as c3:
            s77.require_exact_int(4, "lo", min_val=5)
        self.assertEqual(c3.exception.code, "INT_TOO_SMALL")
        with self.assertRaises(s77.S77Error) as c4:
            s77.require_exact_int(6, "hi", max_val=5)
        self.assertEqual(c4.exception.code, "INT_TOO_LARGE")

        self.assertEqual(s77.require_exact_fraction(Fraction(3, 7), "f"), Fraction(3, 7))
        with self.assertRaises(s77.S77Error) as cf:
            s77.require_exact_fraction(3, "f")  # type: ignore[arg-type]
        self.assertEqual(cf.exception.code, "INVALID_FRACTION")
        self.assertEqual(s77.frac_to_dict(Fraction(-6, 4)), {"num": -3, "den": 2})

    def test_quantizers_and_mcnemar(self) -> None:
        self.assertEqual(s77.round_half_even_int(Fraction(5, 2)), 2)
        self.assertEqual(s77.round_half_even_int(Fraction(7, 2)), 4)
        self.assertEqual(s77.round_half_even_int(Fraction(-5, 2)), -2)

        self.assertEqual(s77.sym_quant_int(0, 7, 1024), 0)
        self.assertEqual(s77.sym_quant_int(64, 7, 1024), 0)
        self.assertEqual(s77.sym_quant_int(1, 127, 8), 16)
        self.assertEqual(s77.sym_quant_int(1, 1, 2), 1)
        self.assertEqual(s77.sym_quant_int(1, 1, 3), 0)
        with self.assertRaises(s77.S77Error):
            s77.sym_quant_int(-1, 7, 8)
        with self.assertRaises(s77.S77Error):
            s77.sym_quant_int(1, 0, 8)
        with self.assertRaises(s77.S77Error):
            s77.sym_quant_int(1, 7, 0)

        self.assertEqual(s77.sym_quant_signed_frac(Fraction(3, 1), 7, Fraction(2, 1)), Fraction(2, 1))
        self.assertEqual(s77.sym_quant_signed_frac(Fraction(-3, 1), 7, Fraction(2, 1)), Fraction(-2, 1))
        self.assertEqual(s77.sym_quant_signed_frac(Fraction(1, 1), 4, Fraction(2, 1)), Fraction(1, 1))
        self.assertEqual(s77.sym_quant_signed_frac(Fraction(-1, 1), 4, Fraction(2, 1)), Fraction(-1, 1))
        with self.assertRaises(s77.S77Error) as cp:
            s77.sym_quant_signed_frac(Fraction(1, 1), 7, Fraction(0, 1))
        self.assertEqual(cp.exception.code, "NONPOSITIVE_PEAK")

        self.assertEqual(s77.exact_two_sided_mcnemar_p(0, 0), Fraction(1, 1))
        self.assertEqual(s77.exact_two_sided_mcnemar_p(5, 5), Fraction(1, 1))
        self.assertEqual(s77.exact_two_sided_mcnemar_p(1, 3), Fraction(5, 8))
        self.assertEqual(s77.exact_two_sided_mcnemar_p(3, 1), Fraction(5, 8))
        p_fin = s77.exact_two_sided_mcnemar_p(3, 46)
        self.assertLess(p_fin, Fraction(1, 10**10))
        with self.assertRaises(s77.S77Error):
            s77.exact_two_sided_mcnemar_p(-1, 2)
        with self.assertRaises(s77.S77Error):
            s77.exact_two_sided_mcnemar_p(0, 2001)

    def test_mellin_h4_and_dpi(self) -> None:
        self.assertEqual(s77.mellin_rat_phi(Fraction(0, 1), r=2), Fraction(0, 1))
        self.assertEqual(s77.mellin_rat_phi(Fraction(1, 1), r=2), Fraction(3, 10))
        self.assertEqual(s77.mellin_rat_phi(Fraction(-1, 1), r=2), Fraction(-3, 10))
        self.assertEqual(s77.mellin_rat_phi(Fraction(1, 1), r=3), Fraction(2, 5))
        with self.assertRaises(s77.S77Error):
            s77.mellin_rat_phi(Fraction(1, 1), r=1)
        with self.assertRaises(s77.S77Error):
            s77.mellin_rat_phi(Fraction(1, 1), r=17)

        rungs_r3 = tuple(Fraction(3, 1) ** k for k in range(-2, 3))
        v_sum = s77.eval_mellin_grid(rungs_r3, Fraction(5, 7), Fraction(3, 2), Fraction(11, 4), r=3)
        v_cls = s77.eval_mellin_closed_form(-2, 2, Fraction(5, 7), Fraction(3, 2), Fraction(11, 4), r=3)
        self.assertEqual(v_sum, v_cls)
        with self.assertRaises(s77.S77Error):
            s77.eval_mellin_grid(rungs_r3, Fraction(1, 1), Fraction(0, 1), Fraction(1, 1))
        with self.assertRaises(s77.S77Error):
            s77.eval_mellin_closed_form(2, 1, Fraction(1, 1), Fraction(1, 1), Fraction(1, 1))
        with self.assertRaises(s77.S77Error):
            s77.eval_mellin_closed_form(-33, 0, Fraction(1, 1), Fraction(1, 1), Fraction(1, 1))
        with self.assertRaises(s77.S77Error):
            s77.eval_mellin_closed_form(0, 33, Fraction(1, 1), Fraction(1, 1), Fraction(1, 1))
        with self.assertRaises(s77.S77Error):
            s77.eval_mellin_closed_form(0, 1, Fraction(1, 1), Fraction(0, 1), Fraction(1, 1))

        vec = (Fraction(1, 1), Fraction(3, 1), Fraction(-5, 1), Fraction(11, 1))
        rot = s77._h4_apply_exact(vec)
        self.assertEqual(rot, (Fraction(5, 1), Fraction(-9, 1), Fraction(-1, 1), Fraction(7, 1)))
        self.assertEqual(s77._h4_apply_exact(rot), vec)

        dpi = s77.compute_matrix_dpi_bwi(((2, 0), (-1, 3)))
        self.assertEqual(dpi["rows"], 2)
        self.assertEqual(dpi["cols"], 2)
        self.assertEqual(dpi["c_row"], {"num": 10, "den": 7})
        self.assertEqual(dpi["bwi_span"], {"num": 3, "den": 1})
        self.assertEqual(dpi["bwi_sq_overload"], {"num": 27, "den": 14})
        self.assertEqual(dpi["l0_density"], {"num": 3, "den": 4})
        self.assertEqual(dpi["nonzero_count"], 3)
        for bad_m in (((1, 2),), ((1,), (2,)), ((1, 2), (3,)), ((0, 0), (0, 0))):
            with self.assertRaises(s77.S77Error):
                s77.compute_matrix_dpi_bwi(bad_m)

        self.assertEqual(s77.count_offblock_nnz(((1, 0), (0, 1)), 1), 0)
        self.assertEqual(s77.count_offblock_nnz(((1, 2), (0, 1)), 1), 1)
        self.assertEqual(s77.count_offblock_nnz(((1, 0), (3, 1)), 1), 1)
        with self.assertRaises(s77.S77Error):
            s77.count_offblock_nnz(((1, 0), (0, 1)), 0)
        with self.assertRaises(s77.S77Error):
            s77.count_offblock_nnz(((1, 0), (0, 1)), 2)

        self.assertTrue(s77.is_sign_flip(Fraction(1, 10), Fraction(-1, 10)))
        self.assertFalse(s77.is_sign_flip(Fraction(0, 1), Fraction(-1, 10)))
        self.assertFalse(s77.is_sign_flip(Fraction(1, 10), Fraction(0, 1)))
        self.assertFalse(s77.is_sign_flip(Fraction(-1, 10), Fraction(-1, 10)))
        self.assertFalse(s77.is_sign_flip(Fraction(1, 10), Fraction(1, 10)))

    def test_four_pillars_certificate_values(self) -> None:
        cert = s77.build_certificate()
        ver.audit_certificate_object(cert)
        self.assertEqual(cert["schema"], s77.CERT_SCHEMA)
        self.assertEqual(cert["track_id"], s77.CERT_TRACK_ID)
        p = cert["payload"]

        # Pillar 1
        p1 = p["pillar1_mellin_glu_primitives"]
        self.assertEqual(p1["single_layer_collapse"]["f1_zero"], {"num": 0, "den": 1})
        self.assertEqual(p1["single_layer_collapse"]["weight_norm_lb_at_lam_1_256_eps_1_10"], {"num": 98304, "den": 5})
        self.assertEqual(len(p1["single_layer_collapse"]["evaluations"]), 4)
        self.assertEqual(p1["mellin_21rung_telescoping"]["rung_count"], 21)
        self.assertEqual(p1["mellin_21rung_telescoping"]["weight_dynamic_span"], 1048576)
        self.assertEqual(p1["mellin_21rung_telescoping"]["exact_carry_passes"], 5)
        self.assertEqual(p1["mellin_21rung_telescoping"]["max_abs_error"], {"num": 347892434082, "den": 4402341479425})
        self.assertEqual(p1["two_layer_boolean_gate"]["exact_passes"], 24)
        self.assertEqual(p1["two_layer_boolean_gate"]["total_evaluations"], 24)
        we = p1["width_extension_and_tied_readout"]
        self.assertEqual(we["granite_gamma_nl_sq"], {"num": 128, "den": 185})
        self.assertEqual(we["qwen_gamma_nl_sq"], {"num": 512, "den": 1023})
        self.assertEqual(we["granite_sparse_nnz_fraction"], {"num": 133, "den": 366000})
        self.assertEqual(we["qwen_sparse_nnz_fraction"], {"num": 239, "den": 420600})
        self.assertEqual(we["norm_pair"], [254, -256])
        self.assertEqual(we["off_trigger_residual"], 0)
        self.assertEqual(we["active_push_exact"], 10710)
        self.assertEqual(we["active_push_formula"], 10710)
        self.assertEqual(p1["s70_swiglu_perm_invariance"]["permutations_checked"], 24)
        self.assertEqual(p1["s70_swiglu_perm_invariance"]["max_abs_diff"], {"num": 0, "den": 1})

        # Pillar 2
        p2 = p["pillar2_quantization_margin_collision"]
        regs = {r["regime"]: r for r in p2["regimes"]}
        self.assertEqual(len(regs), 6)
        self.assertEqual((regs["exact_fp32_sparse_sidecar"]["zeroed_rungs"], regs["exact_fp32_sparse_sidecar"]["carry_passes"]), (0, 5))
        self.assertEqual((regs["uniform_group_int4"]["zeroed_rungs"], regs["uniform_group_int4"]["carry_passes"]), (12, 0))
        self.assertEqual((regs["uniform_group_int8"]["zeroed_rungs"], regs["uniform_group_int8"]["carry_passes"]), (8, 0))
        self.assertEqual((regs["unsorted_blockh4_int8"]["zeroed_rungs"], regs["unsorted_blockh4_int8"]["carry_passes"]), (4, 1))
        self.assertEqual((regs["stratified_s72_quad_int8"]["zeroed_rungs"], regs["stratified_s72_quad_int8"]["carry_passes"]), (0, 5))
        self.assertEqual((regs["stratified_s72_quad_int4"]["zeroed_rungs"], regs["stratified_s72_quad_int4"]["carry_passes"]), (0, 0))
        self.assertTrue(regs["stratified_s72_quad_int8"]["all_carry_pass"])
        self.assertFalse(regs["unsorted_blockh4_int8"]["all_carry_pass"])

        # Pillar 3
        p3 = p["pillar3_wsp_dpi_security_collision"]
        self.assertEqual(len(p3["wsp_gym_upstream"]["pinned_files"]), 7)
        dpi = p3["dpi_bwi_three_regime_model"]
        self.assertEqual(dpi["clean_dense"]["c_row"], {"num": 1, "den": 1})
        self.assertEqual(dpi["symmetry_hidden_sign_flip"]["c_row"], {"num": 1, "den": 1})
        self.assertEqual(dpi["whitebox_diff_dw"]["c_row"], {"num": 4, "den": 1})
        self.assertEqual(dpi["mellin_glu_graft_single_snapshot"]["bwi_span"], {"num": 1024, "den": 1})
        self.assertEqual(dpi["graft_offblock_nnz"], 0)
        self.assertEqual(dpi["graft_norm_pair_antisym_sum"], 0)
        self.assertEqual(dpi["graft_norm_sq_overload"], 65025)

        cs08 = p3["cs08_compute_budget_wall"]
        self.assertEqual(cs08["token_compression_ratio"], {"num": 5298074, "den": 19035})
        self.assertEqual(cs08["all_faulty_diff_rl_minus_think"], {"num": 31, "den": 422})
        self.assertEqual(cs08["all_faulty_mcnemar_p_rounded_1e6"], 6591)
        self.assertEqual(cs08["finished_faulty_n"], 327)
        self.assertEqual(cs08["finished_scale_rl_correct"], 276)
        self.assertEqual(cs08["finished_thinking_correct"], 319)
        self.assertEqual(cs08["finished_diff_rl_minus_think"], {"num": -43, "den": 327})
        self.assertEqual(cs08["cutoff_exclusive_rl_wins"], 74)
        self.assertTrue(cs08["sign_flip_verified"])

        m500 = {r["method"]: r for r in p3["cs15_cs18_random_edit_wall"]["comparisons_vs_random_L23"]}
        self.assertTrue(m500["unedited"]["mcnemar_two_sided_p_lt_1e_30"])
        self.assertEqual(m500["untrained_reason_L23"]["mcnemar_two_sided_p_rounded_1e6"], 854630)
        self.assertEqual(m500["real_rl_L23"]["mcnemar_two_sided_p_rounded_1e6"], 923401)
        self.assertEqual(m500["formula_rl_L23"]["mcnemar_two_sided_p_rounded_1e6"], 1000000)
        self.assertEqual(m500["n573_x2_published_edit"]["mcnemar_two_sided_p_rounded_1e6"], 854630)
        self.assertEqual(m500["wait_ban_zero_weight_edit"]["mcnemar_two_sided_p_rounded_1e6"], 645497)
        self.assertFalse(m500["wait_ban_zero_weight_edit"]["edits_weights"])

        # Pillar 4
        p4 = p["pillar4_lean4_and_scope"]
        self.assertEqual(p4["lean4_certificate"]["theorem_count"], 18)
        self.assertEqual(p4["lean4_certificate"]["sha256"], s77.LEAN_FILE_SHA256)
        self.assertEqual(p4["novelty_honesty_law4"]["highest_novelty_class"], "N1")
        self.assertEqual(p4["novelty_honesty_law4"]["n2_claims"], 0)


class TestS77VerifierZoneBAndIO(unittest.TestCase):
    def test_json_tree_and_parser_hardening(self) -> None:
        ver.validate_json_tree_iterative({"a": [1, True, None, "ok", (1 << 2048) - 1]}, max_depth=256)
        ver.validate_json_tree_iterative(1, max_depth=1)
        ver.validate_json_tree_iterative([[1]], max_depth=2)
        for bad_depth in (0, 257, True):
            with self.assertRaises(s77.S77Error) as cd:
                ver.validate_json_tree_iterative({}, max_depth=bad_depth)  # type: ignore[arg-type]
            self.assertEqual(cd.exception.code, "INVALID_MAX_DEPTH")
        with self.assertRaises(s77.S77Error) as cdep:
            ver.validate_json_tree_iterative([[[1]]], max_depth=2)
        self.assertEqual(cdep.exception.code, "JSON_DEPTH_EXCEEDED")
        with self.assertRaises(s77.S77Error) as cnk:
            ver.validate_json_tree_iterative({1: "a"})
        self.assertEqual(cnk.exception.code, "NON_STR_KEY")
        with self.assertRaises(s77.S77Error) as csk:
            ver.validate_json_tree_iterative({"\ud800": "a"})
        self.assertEqual(csk.exception.code, "INVALID_UNICODE_STR")
        with self.assertRaises(s77.S77Error) as csv:
            ver.validate_json_tree_iterative({"a": "\ud800"})
        self.assertEqual(csv.exception.code, "INVALID_UNICODE_STR")
        with self.assertRaises(s77.S77Error) as cbi:
            ver.validate_json_tree_iterative(1 << 2048)
        self.assertEqual(cbi.exception.code, "INT_BIT_LIMIT")
        with self.assertRaises(s77.S77Error) as cft:
            ver.validate_json_tree_iterative((1, 2))
        self.assertEqual(cft.exception.code, "FORBIDDEN_JSON_TYPE")

        class IntSub(int):
            pass

        with self.assertRaises(s77.S77Error) as cis:
            ver.validate_json_tree_iterative(IntSub(5))
        self.assertEqual(cis.exception.code, "FORBIDDEN_JSON_TYPE")

        # Direct _parse_capped_int_token boundary probes (617 digits & 2048 bits)
        max_2048 = (1 << 2048) - 1
        self.assertEqual(len(str(max_2048)), ver.MAX_INT_DIGITS)
        self.assertEqual(ver._parse_capped_int_token(str(max_2048)), max_2048)
        with self.assertRaises(s77.S77Error) as tok_bit:
            ver._parse_capped_int_token(str(1 << 2048))
        self.assertEqual(tok_bit.exception.code, "INT_BIT_LIMIT")
        with self.assertRaises(s77.S77Error) as tok_dig:
            ver._parse_capped_int_token("9" * (ver.MAX_INT_DIGITS + 1))
        self.assertEqual(tok_dig.exception.code, "INT_DIGIT_LIMIT")

        self.assertEqual(ver.parse_strict_json('{"x":-42,"y":[true,null,"z"]}'), {"x": -42, "y": [True, None, "z"]})
        exact_max_json = '"' + ("a" * (ver.MAX_JSON_BYTES - 2)) + '"'
        self.assertEqual(len(ver.parse_strict_json(exact_max_json)), ver.MAX_JSON_BYTES - 2)
        with self.assertRaises(s77.S77Error) as cp1:
            ver.parse_strict_json(b"{}")  # type: ignore[arg-type]
        self.assertEqual(cp1.exception.code, "INVALID_JSON_TEXT")
        with self.assertRaises(s77.S77Error) as cp2:
            ver.parse_strict_json('"\ud800"')
        self.assertEqual(cp2.exception.code, "INVALID_UNICODE_STR")
        with self.assertRaises(s77.S77Error) as cp3:
            ver.parse_strict_json('"' + ("a" * (ver.MAX_JSON_BYTES + 1)) + '"')
        self.assertEqual(cp3.exception.code, "JSON_TOO_LARGE")
        with self.assertRaises(s77.S77Error) as cp4:
            ver.parse_strict_json('{"a":1,"\\u0061":2}')
        self.assertEqual(cp4.exception.code, "DUPLICATE_JSON_KEY")
        with self.assertRaises(s77.S77Error) as cp5:
            ver.parse_strict_json('{"a":1.0}')
        self.assertEqual(cp5.exception.code, "FLOAT_FORBIDDEN")
        with self.assertRaises(s77.S77Error) as cp6:
            ver.parse_strict_json('{"a":NaN}')
        self.assertEqual(cp6.exception.code, "NONFINITE_CONSTANT")
        with self.assertRaises(s77.S77Error) as cp7:
            ver.parse_strict_json('{"a":' + ("9" * 5001) + "}")
        self.assertEqual(cp7.exception.code, "INT_DIGIT_LIMIT")
        with self.assertRaises(s77.S77Error) as cp7b:
            ver.parse_strict_json('{"a":-' + ("9" * (ver.MAX_INT_DIGITS + 1)) + "}")
        self.assertEqual(cp7b.exception.code, "INT_DIGIT_LIMIT")
        with self.assertRaises(s77.S77Error) as cp8:
            ver.parse_strict_json('{"a":' + str(1 << 2048) + "}")
        self.assertEqual(cp8.exception.code, "INT_BIT_LIMIT")
        with self.assertRaises(s77.S77Error) as cp9:
            ver.parse_strict_json("{broken")
        self.assertEqual(cp9.exception.code, "JSON_DECODE_ERROR")
        with self.assertRaises(s77.S77Error) as cp10:
            ver.parse_strict_json("[" * 500 + "]" * 500)
        self.assertIn(cp10.exception.code, ("JSON_DEPTH_EXCEEDED", "JSON_DECODE_ERROR"))

    def test_digest_and_exact_typed_equal_and_auditor(self) -> None:
        good_h = "0123456789abcdef" * 4
        self.assertEqual(ver.require_sha256_hex(good_h, "h"), good_h)
        with self.assertRaises(s77.S77Error) as d1:
            ver.require_sha256_hex(123, "h")
        self.assertEqual(d1.exception.code, "INVALID_DIGEST_TYPE")
        with self.assertRaises(s77.S77Error) as d2:
            ver.require_sha256_hex("a" * 63, "h")
        self.assertEqual(d2.exception.code, "INVALID_DIGEST_LEN")
        with self.assertRaises(s77.S77Error) as d3:
            ver.require_sha256_hex("A" * 64, "h")
        self.assertEqual(d3.exception.code, "INVALID_DIGEST_HEX")
        with self.assertRaises(s77.S77Error) as d4:
            ver.require_sha256_hex("\u00e9" * 64, "h")
        self.assertEqual(d4.exception.code, "INVALID_DIGEST_HEX")

        self.assertTrue(ver.exact_typed_equal({"a": [1, True, None]}, {"a": [1, True, None]}))
        self.assertFalse(ver.exact_typed_equal(1, True))
        self.assertFalse(ver.exact_typed_equal({"a": 1}, {"a": 1, "b": 2}))
        self.assertFalse(ver.exact_typed_equal({"a": 1}, {"b": 1}))
        self.assertFalse(ver.exact_typed_equal([1, 2], [1]))
        self.assertFalse(ver.exact_typed_equal([1, 2], [1, 3]))
        self.assertFalse(ver.exact_typed_equal("x", "y"))

        cert = s77.build_certificate()
        self.assertEqual(ver.audit_certificate_object(cert)["certificate_sha256"], cert["certificate_sha256"])

        with self.assertRaises(s77.S77Error) as a0:
            ver.audit_certificate_object([1, 2])
        self.assertEqual(a0.exception.code, "NON_OBJECT_ROOT")
        c_keys = copy.deepcopy(cert)
        c_keys["extra"] = 1
        with self.assertRaises(s77.S77Error) as a1:
            ver.audit_certificate_object(c_keys)
        self.assertEqual(a1.exception.code, "BAD_CERT_KEYS")
        c_sch = copy.deepcopy(cert)
        c_sch["schema"] = "wrong"
        with self.assertRaises(s77.S77Error) as a2:
            ver.audit_certificate_object(c_sch)
        self.assertEqual(a2.exception.code, "BAD_SCHEMA")
        c_tid = copy.deepcopy(cert)
        c_tid["track_id"] = "wrong"
        with self.assertRaises(s77.S77Error) as a3:
            ver.audit_certificate_object(c_tid)
        self.assertEqual(a3.exception.code, "BAD_TRACK_ID")
        c_pt = copy.deepcopy(cert)
        c_pt["payload"] = []
        with self.assertRaises(s77.S77Error) as a4:
            ver.audit_certificate_object(c_pt)
        self.assertEqual(a4.exception.code, "BAD_PAYLOAD_TYPE")
        c_psha = copy.deepcopy(cert)
        c_psha["payload_sha256"] = "0" * 64
        with self.assertRaises(s77.S77Error) as a5:
            ver.audit_certificate_object(c_psha)
        self.assertEqual(a5.exception.code, "PAYLOAD_SHA_MISMATCH")
        c_csha = copy.deepcopy(cert)
        c_csha["certificate_sha256"] = "0" * 64
        with self.assertRaises(s77.S77Error) as a6:
            ver.audit_certificate_object(c_csha)
        self.assertEqual(a6.exception.code, "CERT_SHA_MISMATCH")

        # Direct verify_certificate_dict FR1/FR0 and secondary_audit_payload tests
        self.assertEqual(ver.verify_certificate_dict(cert, full_replay=False)["certificate_sha256"], cert["certificate_sha256"])
        with self.assertRaises(s77.S77Error) as fr_bad:
            ver.verify_certificate_dict(cert, full_replay=1)  # type: ignore[arg-type]
        self.assertEqual(fr_bad.exception.code, "INVALID_FULL_REPLAY")
        self.assertIs(ver.secondary_audit_payload(cert["payload"]), cert["payload"])
        with self.assertRaises(s77.S77Error) as sec_nd:
            ver.secondary_audit_payload([1, 2])
        self.assertEqual(sec_nd.exception.code, "BAD_PAYLOAD_TYPE")

        # Re-signed bool-as-int swap (ZB05) caught by secondary_audit_payload in FR0 and FR1
        c_bool = copy.deepcopy(cert)
        c_bool["payload"]["pillar1_mellin_glu_primitives"]["single_layer_collapse"]["f1_zero"]["den"] = True
        with self.assertRaises(s77.S77Error) as a7:
            ver.verify_certificate_dict(_resign(c_bool), full_replay=False)
        self.assertEqual(a7.exception.code, "BAD_RATIONAL_DICT")
        c_bool_num = copy.deepcopy(cert)
        c_bool_num["payload"]["pillar1_mellin_glu_primitives"]["single_layer_collapse"]["f1_zero"]["num"] = True
        with self.assertRaises(s77.S77Error) as a7n:
            ver.secondary_audit_payload(c_bool_num["payload"])
        self.assertEqual(a7n.exception.code, "BAD_RATIONAL_DICT")
        c_zero_den = copy.deepcopy(cert)
        c_zero_den["payload"]["pillar1_mellin_glu_primitives"]["single_layer_collapse"]["f1_zero"]["den"] = 0
        with self.assertRaises(s77.S77Error) as a7z:
            ver.secondary_audit_payload(c_zero_den["payload"])
        self.assertEqual(a7z.exception.code, "BAD_RATIONAL_DICT")
        c_extra_rat = copy.deepcopy(cert)
        c_extra_rat["payload"]["pillar1_mellin_glu_primitives"]["single_layer_collapse"]["f1_zero"] = {
            "num": 0,
            "den": 0,
            "extra": 1,
        }
        self.assertIs(ver.secondary_audit_payload(c_extra_rat["payload"]), c_extra_rat["payload"])
        c_num_only = copy.deepcopy(cert)
        c_num_only["payload"]["pillar1_mellin_glu_primitives"]["single_layer_collapse"]["f1_zero"] = {"num": 0, "other": 1}
        self.assertIs(ver.secondary_audit_payload(c_num_only["payload"]), c_num_only["payload"])
        c_den_only = copy.deepcopy(cert)
        c_den_only["payload"]["pillar1_mellin_glu_primitives"]["single_layer_collapse"]["f1_zero"] = {"other": 0, "den": 1}
        self.assertIs(ver.secondary_audit_payload(c_den_only["payload"]), c_den_only["payload"])
        c_bool_fld = copy.deepcopy(cert)
        c_bool_fld["payload"]["pillar1_mellin_glu_primitives"]["mellin_21rung_telescoping"]["rung_count"] = True
        with self.assertRaises(s77.S77Error) as a7f:
            ver.secondary_audit_payload(c_bool_fld["payload"])
        self.assertEqual(a7f.exception.code, "UNEXPECTED_BOOL_FIELD")
        c_bool_lst = copy.deepcopy(cert)
        c_bool_lst["payload"]["pillar1_mellin_glu_primitives"]["width_extension_and_tied_readout"]["norm_pair"][0] = True
        with self.assertRaises(s77.S77Error) as a7l:
            ver.secondary_audit_payload(c_bool_lst["payload"])
        self.assertEqual(a7l.exception.code, "UNEXPECTED_BOOL_ITEM")
        c_bad_pin = copy.deepcopy(cert)
        c_bad_pin["payload"]["pillar3_wsp_dpi_security_collision"]["wsp_gym_upstream"]["pinned_files"][0]["sha256"] = "Z" * 64
        with self.assertRaises(s77.S77Error) as a7s:
            ver.secondary_audit_payload(c_bad_pin["payload"])
        self.assertEqual(a7s.exception.code, "INVALID_DIGEST_HEX")

        # Pillar 1..4 secondary_audit_payload guards
        p1_bad = copy.deepcopy(cert["payload"])
        p1_bad["pillar1_mellin_glu_primitives"] = "HOLLOWED"
        with self.assertRaises(s77.S77Error) as e_p1:
            ver.secondary_audit_payload(p1_bad)
        self.assertEqual(e_p1.exception.code, "BAD_PILLAR_TYPE")
        p4_bad = copy.deepcopy(cert["payload"])
        p4_bad["pillar4_lean4_and_scope"] = []
        with self.assertRaises(s77.S77Error) as e_p4:
            ver.secondary_audit_payload(p4_bad)
        self.assertEqual(e_p4.exception.code, "BAD_PILLAR_TYPE")
        for mut_fn, exp_code in (
            (lambda d: d["pillar4_lean4_and_scope"].__setitem__("lean4_certificate", []), "BAD_LEAN_CERT_TYPE"),
            (lambda d: d["pillar4_lean4_and_scope"]["lean4_certificate"].__setitem__("theorem_count", 17), "BAD_THEOREM_COUNT"),
            (lambda d: d["pillar4_lean4_and_scope"]["lean4_certificate"].__setitem__("theorem_count", True), "UNEXPECTED_BOOL_FIELD"),
            (lambda d: d["pillar4_lean4_and_scope"]["lean4_certificate"].__setitem__("theorem_count", "18"), "BAD_THEOREM_COUNT"),
            (lambda d: d["pillar4_lean4_and_scope"]["lean4_certificate"].__setitem__("sha256", "0" * 64), "BAD_LEAN_PIN"),
            (lambda d: d["pillar4_lean4_and_scope"].__setitem__("novelty_honesty_law4", []), "BAD_NOVELTY_TYPE"),
            (lambda d: d["pillar4_lean4_and_scope"]["novelty_honesty_law4"].__setitem__("n2_claims", 1), "BAD_NOVELTY_CLAIMS"),
            (lambda d: d["pillar4_lean4_and_scope"]["novelty_honesty_law4"].__setitem__("n2_claims", "0"), "BAD_NOVELTY_CLAIMS"),
        ):
            cand = copy.deepcopy(cert["payload"])
            mut_fn(cand)
            with self.assertRaises(s77.S77Error) as e_sec:
                ver.secondary_audit_payload(cand)
            self.assertEqual(e_sec.exception.code, exp_code)

        # Re-signed hollow payload (ZB13) caught in FR0 & FR1
        c_hollow = copy.deepcopy(cert)
        c_hollow["payload"] = {}
        with self.assertRaises(s77.S77Error) as a8:
            ver.audit_certificate_object(_resign(c_hollow))
        self.assertEqual(a8.exception.code, "BAD_PAYLOAD_KEYS")

        # Re-signed valid-schema tampered value passes FR0 but fails FR1 oracle replay
        c_tamp = copy.deepcopy(cert)
        c_tamp["payload"]["pillar1_mellin_glu_primitives"]["width_extension_and_tied_readout"]["active_push_exact"] = 10711
        c_tamp_signed = _resign(c_tamp)
        self.assertEqual(
            ver.verify_certificate_dict(c_tamp_signed, full_replay=False)["certificate_sha256"],
            c_tamp_signed["certificate_sha256"],
        )
        with self.assertRaises(s77.S77Error) as a8r:
            ver.verify_certificate_dict(c_tamp_signed, full_replay=True)
        self.assertEqual(a8r.exception.code, "PAYLOAD_ORACLE_MISMATCH")

        # Simulate oracle cert_sha mismatch after payload equality passes
        fake_exp = copy.deepcopy(cert)
        fake_exp["certificate_sha256"] = "f" * 64
        with mock.patch.object(ver, "build_certificate", return_value=fake_exp):
            with self.assertRaises(s77.S77Error) as a9:
                ver.audit_certificate_object(cert)
            self.assertEqual(a9.exception.code, "ORACLE_CERT_SHA_MISMATCH")

    def test_committed_disk_cert_and_hardened_io_and_cli(self) -> None:
        disk_cert = _SCRIPT_DIR / "s77_mellin_wsp_certificate.json"
        mode = stat.S_IMODE(disk_cert.stat().st_mode)
        self.assertIn(mode, (0o600, 0o644))
        checked = ver.check_certificate_file(disk_cert)

        # CLI --standalone --json and no-arg default byte-identical to committed disk cert
        out_buf = io.BytesIO()
        fake_stdout = type("FakeOut", (), {"buffer": out_buf})()
        with mock.patch.object(sys, "stdout", fake_stdout):
            rc = ver.main(["--standalone", "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(out_buf.getvalue(), disk_cert.read_bytes())
        out_buf2 = io.BytesIO()
        with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": out_buf2})()):
            rc2 = ver.main([])
        self.assertEqual(rc2, 0)
        self.assertEqual(out_buf2.getvalue(), disk_cert.read_bytes())

        # CLI --check --json
        chk_buf = io.BytesIO()
        with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": chk_buf})()):
            rc = ver.main(["--check", str(disk_cert), "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(chk_buf.getvalue().decode("utf-8"))["status"], "PASS")
        self.assertEqual(ver.main(["--check", str(disk_cert)]), 0)

        with tempfile.TemporaryDirectory(prefix="s77_io_") as td:
            tdir = Path(td).resolve()
            out_p = tdir / "cert_out.json"
            old_umask = os.umask(0o022)
            try:
                w_buf = io.BytesIO()
                with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": w_buf})()):
                    rc_w = ver.main(["--write", str(out_p), "--json"])
                self.assertEqual(rc_w, 0)
                self.assertEqual(json.loads(w_buf.getvalue().decode("utf-8"))["status"], "WRITTEN")
                self.assertEqual(stat.S_IMODE(out_p.stat().st_mode), 0o600)
                self.assertEqual(ver.main(["--write", str(out_p)]), 0)
                self.assertEqual(out_p.read_bytes(), disk_cert.read_bytes())
            finally:
                os.umask(old_umask)

            # Reject bad path types, surrogate, NUL, root/.. paths
            with self.assertRaises(s77.S77Error) as p0:
                ver.read_regular_file_bytes("not_a_path")  # type: ignore[arg-type]
            self.assertEqual(p0.exception.code, "INVALID_PATH_TYPE")
            with self.assertRaises(s77.S77Error) as p1:
                ver.read_regular_file_bytes(Path(str(tdir) + "/\ud800"))
            self.assertEqual(p1.exception.code, "INVALID_UNICODE_STR")
            with self.assertRaises(s77.S77Error) as p2:
                ver.read_regular_file_bytes(Path(str(tdir) + "/a\x00b"))
            self.assertEqual(p2.exception.code, "INVALID_PATH_NUL")
            with self.assertRaises(s77.S77Error) as p3:
                ver.read_regular_file_bytes(Path("/"))
            self.assertEqual(p3.exception.code, "INVALID_PATH")
            with self.assertRaises(s77.S77Error) as p4:
                ver.read_regular_file_bytes(tdir / "..")
            self.assertEqual(p4.exception.code, "INVALID_PATH")

            # Missing ancestor / missing file / directory
            with self.assertRaises(s77.S77Error) as p5:
                ver.check_certificate_file(tdir / "no_dir" / "x.json")
            self.assertEqual(p5.exception.code, "PARENT_DIR_ERROR")
            with self.assertRaises(s77.S77Error) as p6:
                ver.check_certificate_file(tdir / "missing.json")
            self.assertEqual(p6.exception.code, "FILE_READ_ERROR")
            with self.assertRaises(s77.S77Error) as p7:
                ver.check_certificate_file(tdir)
            self.assertEqual(p7.exception.code, "NOT_REGULAR_FILE")

            # Symlink target & symlink ancestor & relative PWD symlink
            sym_f = tdir / "sym.json"
            sym_f.symlink_to(out_p)
            with self.assertRaises(s77.S77Error) as p8:
                ver.check_certificate_file(sym_f)
            self.assertEqual(p8.exception.code, "SYMLINK_FORBIDDEN")
            with self.assertRaises(s77.S77Error) as p8w:
                ver.write_atomic_0600_bytes(sym_f, b"{}\n")
            self.assertEqual(p8w.exception.code, "SYMLINK_FORBIDDEN")

            sub_d = tdir / "real_sub"
            sub_d.mkdir()
            (sub_d / "c.json").write_bytes(disk_cert.read_bytes())
            sym_d = tdir / "sym_sub"
            sym_d.symlink_to(sub_d)
            with self.assertRaises(s77.S77Error) as p9:
                ver.check_certificate_file(sym_d / "c.json")
            self.assertEqual(p9.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")

            with mock.patch.object(ver.os, "environ", {}):
                ver._check_pwd_no_symlinks()
            with mock.patch.object(ver.os, "environ", {"PWD": "x" + str(sym_d)}):
                ver._check_pwd_no_symlinks()
            with mock.patch.object(ver.os, "environ", {"PWD": str(sym_d)}):
                with self.assertRaises(s77.S77Error) as p9p:
                    ver._check_pwd_no_symlinks()
                self.assertEqual(p9p.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")
            with mock.patch.object(ver.os, "environ", {"PWD": "/tmp/\ud800"}):
                with self.assertRaises(s77.S77Error) as p9s:
                    ver.read_regular_file_bytes(Path("c.json"))
                self.assertEqual(p9s.exception.code, "INVALID_UNICODE_STR")
            with mock.patch.dict(os.environ, {"PWD": "/nonexistent_s77_pwd_xyz"}):
                with self.assertRaises(s77.S77Error):
                    ver.read_regular_file_bytes(Path("definitely_missing_s77_rel.json"))

            # FIFO (non-regular scratch pipe probe)
            fifo_p = tdir / "pipe.fifo"
            os.mkfifo(fifo_p)
            with self.assertRaises(s77.S77Error) as pf:
                ver.check_certificate_file(fifo_p)
            self.assertEqual(pf.exception.code, "NOT_REGULAR_FILE")
            with self.assertRaises(s77.S77Error) as pfw:
                ver.write_atomic_0600_bytes(fifo_p, b"{}\n")
            self.assertEqual(pfw.exception.code, "NOT_REGULAR_FILE")

            # Hardlink rejection on read & write
            hl_p = tdir / "hardlink.json"
            os.link(out_p, hl_p)
            with self.assertRaises(s77.S77Error) as ph1:
                ver.check_certificate_file(hl_p)
            self.assertEqual(ph1.exception.code, "HARDLINK_FORBIDDEN")
            with self.assertRaises(s77.S77Error) as ph2:
                ver.write_atomic_0600_bytes(hl_p, b"{}\n")
            self.assertEqual(ph2.exception.code, "HARDLINK_FORBIDDEN")
            hl_p.unlink()

            # Read-only directory write failure (chmod 0o500)
            ro_dir = tdir / "ro_dir"
            ro_dir.mkdir()
            ro_dir.chmod(0o500)
            try:
                with self.assertRaises(s77.S77Error) as pro:
                    ver.write_atomic_0600_bytes(ro_dir / "x.json", b"{}\n")
                self.assertEqual(pro.exception.code, "FILE_WRITE_ERROR")
            finally:
                ro_dir.chmod(0o700)

            # CRLF, invalid UTF-8, non-canonical bytes, oversized file, read/write OSError
            crlf_p = tdir / "crlf.json"
            crlf_p.write_bytes(disk_cert.read_bytes().replace(b"\n", b"\r\n"))
            with self.assertRaises(s77.S77Error) as pcrlf:
                ver.check_certificate_file(crlf_p)
            self.assertEqual(pcrlf.exception.code, "CRLF_FORBIDDEN")

            badu_p = tdir / "badutf8.json"
            badu_p.write_bytes(b"\xff\xfe")
            with self.assertRaises(s77.S77Error) as pbu:
                ver.check_certificate_file(badu_p)
            self.assertEqual(pbu.exception.code, "INVALID_UTF8")

            pretty_p = tdir / "pretty.json"
            pretty_p.write_text(json.dumps(checked, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(s77.S77Error) as ppr:
                ver.check_certificate_file(pretty_p)
            self.assertEqual(ppr.exception.code, "NONCANONICAL_BYTES")

            # Direct _is_symlink_at False check on missing file (kills except OSError: pass)
            dfd_chk = os.open(tdir, os.O_RDONLY | os.O_DIRECTORY)
            try:
                self.assertIs(ver._is_symlink_at(dfd_chk, "no_such_entry"), False)
                self.assertIs(ver._is_symlink_at(dfd_chk, "sym.json"), True)
            finally:
                os.close(dfd_chk)

            big_p = tdir / "big.json"
            big_p.write_bytes(b"a" * 32)
            # Exact max_bytes boundary passes (kills st_size >= max_bytes & total >= max_bytes)
            self.assertEqual(ver.read_regular_file_bytes(big_p, max_bytes=32), b"a" * 32)
            # Oversized st_size rejected BEFORE read even if os.read returns b"" (kills L312 if False)
            big_p.write_bytes(b"a" * 64)
            with mock.patch.object(os, "read", return_value=b""):
                with self.assertRaises(s77.S77Error) as pbig:
                    ver.read_regular_file_bytes(big_p, max_bytes=32)
                self.assertEqual(pbig.exception.code, "FILE_TOO_LARGE")

            # Streaming size cap on 0-byte st_size file (kills L324 if False) & read/write EIO
            empty_p = tdir / "empty.json"
            empty_p.write_bytes(b"")
            with mock.patch.object(os, "read", side_effect=[b"x" * 20, b"y" * 20, b""]):
                with self.assertRaises(s77.S77Error) as pstr:
                    ver.read_regular_file_bytes(empty_p, max_bytes=32)
                self.assertEqual(pstr.exception.code, "FILE_TOO_LARGE")
            with mock.patch.object(os, "read", side_effect=OSError(5, "EIO")):
                with self.assertRaises(s77.S77Error) as peio:
                    ver.read_regular_file_bytes(out_p)
                self.assertEqual(peio.exception.code, "FILE_READ_ERROR")
            with mock.patch.object(os, "write", side_effect=OSError(5, "EIO")):
                with self.assertRaises(s77.S77Error) as pwe:
                    ver.write_atomic_0600_bytes(tdir / "eio.json", b"hello")
                self.assertEqual(pwe.exception.code, "FILE_WRITE_ERROR")
            with mock.patch.object(os, "write", return_value=0):
                with self.assertRaises(s77.S77Error) as pw0:
                    ver.write_atomic_0600_bytes(tdir / "zwrite.json", b"hello")
                self.assertEqual(pw0.exception.code, "FILE_WRITE_ERROR")
            fake_st = type("St", (), {"st_nlink": 2})()
            with mock.patch.object(os, "fstat", return_value=fake_st):
                with self.assertRaises(s77.S77Error) as ptn:
                    ver.write_atomic_0600_bytes(tdir / "hl_tmp.json", b"hello")
                self.assertEqual(ptn.exception.code, "HARDLINK_FORBIDDEN")
            with mock.patch.object(os, "replace", side_effect=OSError(13, "EACCES")):
                with self.assertRaises(s77.S77Error) as prep:
                    ver.write_atomic_0600_bytes(tdir / "rep_err.json", b"hello")
                self.assertEqual(prep.exception.code, "FILE_WRITE_ERROR")

            # CLI fail-closed exit code 2
            err_buf = io.StringIO()
            with mock.patch.object(sys, "stderr", err_buf):
                rc_err = ver.main(["--check", str(crlf_p)])
            self.assertEqual(rc_err, 2)
            self.assertIn("CRLF_FORBIDDEN", err_buf.getvalue())


class TestS77LeanR9AndLiveVerification(unittest.TestCase):
    def test_r9_static_all_11_classes_and_clean_cases(self) -> None:
        with self.assertRaises(s77.S77Error):
            ver.audit_lean4_source_r9(123)  # type: ignore[arg-type]

        # Direct _is_lean4_ident_prev & _strip_outer_parens boundary probes
        self.assertIs(ver._is_lean4_ident_prev("a", -1), False)
        self.assertIs(ver._is_lean4_ident_prev("a", 0), True)
        self.assertIs(ver._is_lean4_ident_prev("_", 0), True)
        self.assertIs(ver._is_lean4_ident_prev(" ", 0), False)
        self.assertIs(ver._is_lean4_ident_prev("a!", 1), True)
        self.assertIs(ver._is_lean4_ident_prev("_!", 1), True)
        self.assertIs(ver._is_lean4_ident_prev(" !", 1), False)
        self.assertIs(ver._is_lean4_ident_prev("!", 0), False)
        self.assertEqual(ver._strip_outer_parens(""), "")
        self.assertEqual(ver._strip_outer_parens("("), "(")
        self.assertEqual(ver._strip_outer_parens("(false)"), "false")
        self.assertEqual(ver._strip_outer_parens("(false"), "(false")
        self.assertEqual(ver._strip_outer_parens("false)"), "false)")

        # Direct _match_lean4_char_literal_end boundary probes
        self.assertEqual(ver._match_lean4_char_literal_end("'a'", 0, 3), 3)
        self.assertIsNone(ver._match_lean4_char_literal_end("'a", 0, 2))
        self.assertIsNone(ver._match_lean4_char_literal_end("'ab", 0, 3))
        self.assertIsNone(ver._match_lean4_char_literal_end("'ab'", 0, 4))
        self.assertIsNone(ver._match_lean4_char_literal_end("'\n'", 0, 3))
        self.assertEqual(ver._match_lean4_char_literal_end("'\\''", 0, 4), 4)
        self.assertEqual(ver._match_lean4_char_literal_end("'\\n'", 0, 4), 4)
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\n", 0, 3))
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\\n'", 0, 4))
        self.assertEqual(ver._match_lean4_char_literal_end("'\\x2a'", 0, 6), 6)
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\x2g'", 0, 6))
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\x2a!", 0, 6))
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\x2a", 0, 5))
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\y2a'", 0, 6))
        self.assertEqual(ver._match_lean4_char_literal_end("'\\u002A'", 0, 8), 8)
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\u002g'", 0, 8))
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\u002A!", 0, 8))
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\u002A", 0, 7))
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\v002A'", 0, 8))

        # Clean samples including comments, char literals, strings, raw strings, safe decide, dot-partial, #print axioms
        clean_src = "\n".join(
            [
                "-- sorry admit axiom native_decide",
                "/- outer /x -x /- sorry -/ still comment -/",
                'def s1 := "sorry \\" native_decide"',
                'def s2 := r#"a " sorry " b"#',
                'def s3 := s! "hello {1 + 1} sorry"',
                'def s4 := !r#"sorry"#',
                'def s5 := panic!"sorry"',
                'def s6 := s!x ++ "sorry"',
                'def s7 := dbg_trace.ok "sorry"',
                'def s8 := _ok_1 "sorry"',
                'def s "a {sorry}"',
                'def bar#"ok"',
                "def foo!r := 1 / 2 - 1",
                "def c1 : Char := '\"'",
                "def c2 : Char := '\\''",
                "def c3 : Char := '\\x22'",
                "def c4 : Char := '\\u0022'",
                "def x' := 1",
                "def x_p := x' + 'a'.toNat",
                "def badCharStart := 'a + 1",
                "def x := rec.partial",
                "theorem t1 : 1 = 1 := by decide (native := false)",
                "theorem t2 : 1 = 1 := by decide (config := ({ native := Bool.false }))",
                "def cfg : DecideConfig := { native := false }",
                "def okGuillemet := «hello» ++ «bad sorry»",
                "@[simp] def attrOk := 1",
                "@[extern",
                "import Init.Data.Nat.Basic",
                "#print axioms t1",
                "theorem t_eof : 1 = 1 := by decide",
            ]
        )
        self.assertEqual(ver.audit_lean4_source_r9(clean_src), [])
        # Exact EOF boundary snippets for line comment, raw-string prefix, char literal at index 0, and index-0 ! / r
        self.assertEqual(ver.audit_lean4_source_r9("-- eof no newline"), [])
        self.assertEqual(ver.audit_lean4_source_r9("r#"), [])
        self.assertEqual(ver.audit_lean4_source_r9("rx"), [])
        self.assertEqual(ver.audit_lean4_source_r9('r"sorry"a'), [])
        self.assertEqual(ver.audit_lean4_source_r9('!"a {sorry}"s'), [])
        self.assertEqual(ver.audit_lean4_source_r9('"ok"a!'), [])
        self.assertEqual(ver.audit_lean4_source_r9(' !"sorry"'), [])
        self.assertEqual(ver.audit_lean4_source_r9("'a'"), [])
        self.assertEqual(ver.audit_lean4_source_r9('def f := a\'"\' sorry "'), [])
        self.assertEqual(ver.audit_lean4_source_r9('def f := _\'"\' sorry "'), [])
        self.assertEqual(ver.audit_lean4_source_r9('def f := foo.s! "a {sorry}"'), [])
        self.assertEqual(ver.audit_lean4_source_r9("s!"), [])
        self.assertEqual(ver.audit_lean4_source_r9('panic!"sorry"'), [])
        self.assertEqual(ver.audit_lean4_source_r9('!panic!"sorry"'), [])
        self.assertEqual(ver.audit_lean4_source_r9("def y := a!\"\""), ["LEAN4_UNKNOWN_BANG_STRING"])
        self.assertEqual(ver.audit_lean4_source_r9("'\x22'\nsorry\ndef q : Char := '\x22'"), ["LEAN4_SORRY"])
        self.assertEqual(ver.audit_lean4_source_r9('def x := foo.r#"ok"; sorry; def z := "#"'), ["LEAN4_SORRY"])
        self.assertEqual(ver.audit_lean4_source_r9('def _a : String := s!"x"\naxiom evil : False\ndef _b : Char := \'"\''), ["LEAN4_AXIOM"])

        # All R10 bypass classes (including S77-VER-01 char-literal quote flips, custom bang/meta, dbg_trace/throwError, csimp) MUST be flagged!
        cases: list[tuple[str, str]] = [
            ("theorem t : True := by sorry", "LEAN4_SORRY"),
            ("-- comment\ntheorem t : True := by sorry", "LEAN4_SORRY"),
            ("def x := 1 - 2\ndef y := a - sorry", "LEAN4_SORRY"),
            ("def x := 1-2; sorry", "LEAN4_SORRY"),
            ("theorem t : True := by «sorry»", "LEAN4_SORRY"),
            ("theorem t : True := by admit", "LEAN4_ADMIT"),
            ("axiom bogus : False", "LEAN4_AXIOM"),
            ("unsafe def f : Nat := 0", "LEAN4_UNSAFE"),
            ("theorem t : 1 = 1 := by native_decide", "LEAN4_NATIVE_DECIDE"),
            ("def x := sorryAx", "LEAN4_SORRY_AX"),
            ("def x := Lean.Meta.mkSorry", "LEAN4_MK_SORRY"),
            ("def x := Lean.ofReduceBool", "LEAN4_OF_REDUCE_BOOL"),
            ("def x := Lean.ofReduceNat", "LEAN4_OF_REDUCE_NAT"),
            ("def x := Lean.trustCompiler", "LEAN4_TRUST_COMPILER"),
            ("public\n  import Mathlib.Tactic", "LEAN4_NON_INIT_IMPORT"),
            ("partial\n def loop (n : Nat) : Nat := loop n", "LEAN4_PARTIAL"),
            ("theorem t : 1 = 1 := by decide +native", "LEAN4_DECIDE_NATIVE"),
            (") theorem t : 1 = 1 := by decide (native := true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native := true })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := myCfg)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := {foo)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := foo})", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { { })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { } })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { c with native := false })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide («native» := true)", "LEAN4_DECIDE_NATIVE"),
            ("def c : DecideConfig := { native := true }", "LEAN4_DECIDE_NATIVE"),
            ("set_option debug.skipKernelTC true", "LEAN4_SKIP_KERNEL_TC"),
            ("set_option debug.byAsSorry true", "LEAN4_SKIP_KERNEL_TC"),
            ("set_option debug.proofAsSorry true", "LEAN4_SKIP_KERNEL_TC"),
            ("set_option debug.terminalTacticsAsSorry true", "LEAN4_SKIP_KERNEL_TC"),
            ("#eval 1 + 1", "LEAN4_EVAL_SPOOF"),
            ("#eval! 1 + 1", "LEAN4_EVAL_SPOOF"),
            ("#reduce 1 + 1", "LEAN4_EVAL_SPOOF"),
            ("#exit", "LEAN4_EVAL_SPOOF"),
            ("#print Nat.add", "LEAN4_EVAL_SPOOF"),
            ("#print axioms theorem", "LEAN4_EVAL_SPOOF"),
            ("run_cmd pure ()", "LEAN4_EVAL_SPOOF"),
            ("initialize x : Nat := pure 0", "LEAN4_EVAL_SPOOF"),
            ("builtin_initialize x : Nat := pure 0", "LEAN4_EVAL_SPOOF"),
            ('] @[extern "c_fn"] def f : Nat := 0', "LEAN4_ATTR_TRUST_ESCAPE"),
            ("attribute [implemented_by g] f", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("@[csimp] theorem csimp_bad : 1 = 1 := rfl", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("attribute [csimp] csimp_bad", "LEAN4_ATTR_TRUST_ESCAPE"),
            ('def x := s! "a {sorry} b"', "LEAN4_SORRY"),
            ('def x := !s!"a {sorry}"', "LEAN4_SORRY"),
            ('def x := dbg_trace "{(fun (_ : 1 = 1) => 0) (by native_decide)}" 0', "LEAN4_NATIVE_DECIDE"),
            ('def x := throwError "{sorry}"', "LEAN4_SORRY"),
            ('def x := foo!"a {sorry}"', "LEAN4_UNKNOWN_BANG_STRING"),
            ('def x := xpanic!"ok"', "LEAN4_UNKNOWN_BANG_STRING"),
            ('syntax "foo!" interpolatedStr(term) : term', "LEAN4_META_SYNTAX_ESCAPE"),
            ("macro_rules | `(1) => `(1)", "LEAN4_META_SYNTAX_ESCAPE"),
            ('elab "e" : term => sorry', "LEAN4_META_SYNTAX_ESCAPE"),
            ('notation "openq\\"" => 0', "LEAN4_META_SYNTAX_ESCAPE"),
            ('def x := s! /- c -/ "{sorry}"', "LEAN4_SORRY"),
            ('def x := s! -- c\n"{sorry}"', "LEAN4_SORRY"),
            ("theorem t : 1 = 1 := by decide -revert +native", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (revert := true) +native", "LEAN4_DECIDE_NATIVE"),
            ("set_option «debug».«skipKernelTC» true", "LEAN4_SKIP_KERNEL_TC"),
            ('def q1 : Char := \'"\'\ntheorem bad : False := by sorry\ndef q2 : Char := \'"\'', "LEAN4_SORRY"),
            ('def q1 : Char := \'"\'\naxiom bad : False\ndef q2 : Char := \'"\'', "LEAN4_AXIOM"),
            ('def q1 : Char := \'"\'\ntheorem bad : 1 = 1 := by native_decide\ndef q2 : Char := \'"\'', "LEAN4_NATIVE_DECIDE"),
            ('def q1 : Char := \'"\'\n#eval IO.println "\'MellinGluQuantMargin.bad\' does not depend on any axioms"\ndef q2 : Char := \'"\'', "LEAN4_EVAL_SPOOF"),
            ("def q1 : Char := '\\''\ndef q2 : Char := '\"'\ntheorem bad : False := by sorry\ndef q3 : Char := '\"'", "LEAN4_SORRY"),
            ("def x := «unterminated", "LEAN4_UNTERMINATED_IDENT"),
            ("/- unterminated comment", "LEAN4_UNTERMINATED_COMMENT"),
            ('def x := "unterminated', "LEAN4_UNTERMINATED_STRING"),
            ('def x := s!"unterminated', "LEAN4_UNTERMINATED_STRING"),
            ('def x := r#"unterminated', "LEAN4_UNTERMINATED_STRING"),
            ('def x := s!"{1', "LEAN4_UNTERMINATED_STRING"),
            ("def x := «axioms»\n#print «axioms» foo", "LEAN4_EVAL_SPOOF"),
            ('def x := s!"{\"{}\"}" ++ s!"{sorry}"', "LEAN4_SORRY"),
        ]
        for snippet, expected_code in cases:
            got = ver.audit_lean4_source_r9(snippet)
            self.assertIn(expected_code, got, f"expected {expected_code} for {snippet!r}, got {got}")

    def test_live_lean_verification_and_rejections(self) -> None:
        lean_file = _SCRIPT_DIR / "MellinGluQuantMargin.lean"
        try:
            ver._find_lean_binary()
            has_lean = True
        except s77.S77Error:
            has_lean = False
        if os.environ.get("ALETHEIA_REQUIRE_LEAN") == "1":
            self.assertTrue(has_lean, "ALETHEIA_REQUIRE_LEAN=1 set but lean binary not found")

        out_buf = io.BytesIO()
        err_buf = io.StringIO()
        if has_lean:
            with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": out_buf})()):
                rc = ver.main(["--verify-lean", str(lean_file), "--json"])
            self.assertEqual(rc, 0)
            res = json.loads(out_buf.getvalue().decode("utf-8"))
            self.assertEqual(res["theorems_verified"], 18)
            self.assertEqual(res["r9_findings"], 0)
            self.assertEqual(res["allowed_axioms"], ["propext"])
            self.assertEqual(res["sha256"], s77.LEAN_FILE_SHA256)
            self.assertEqual(ver.main(["--verify-lean", str(lean_file)]), 0)
        else:
            with mock.patch.object(sys, "stderr", err_buf):
                rc = ver.main(["--verify-lean", str(lean_file), "--json"])
            self.assertEqual(rc, 2)
            self.assertIn("LEAN_BINARY_NOT_FOUND", err_buf.getvalue())
            with self.assertRaises(s77.S77Error) as e_nobin:
                ver.verify_lean_file(lean_file, check_pinned_sha=True)
            self.assertEqual(e_nobin.exception.code, "LEAN_BINARY_NOT_FOUND")

        with tempfile.TemporaryDirectory(prefix="s77_lean_") as td:
            tdir = Path(td).resolve()

            # CRLF and invalid UTF-8
            crlf_l = tdir / "c.lean"
            crlf_l.write_bytes(b"theorem t : True := trivial\r\n")
            with self.assertRaises(s77.S77Error) as e1:
                ver.verify_lean_file(crlf_l, check_pinned_sha=False)
            self.assertEqual(e1.exception.code, "CRLF_FORBIDDEN")

            badu_l = tdir / "u.lean"
            badu_l.write_bytes(b"\xff\xfe")
            with self.assertRaises(s77.S77Error) as e2:
                ver.verify_lean_file(badu_l, check_pinned_sha=False)
            self.assertEqual(e2.exception.code, "INVALID_UTF8")

            # Pinned SHA mismatch
            other_l = tdir / "o.lean"
            other_l.write_text("theorem ok1 : 1 = 1 := rfl\n#print axioms ok1\n", encoding="utf-8")
            with self.assertRaises(s77.S77Error) as e3:
                ver.verify_lean_file(other_l, check_pinned_sha=True)
            self.assertEqual(e3.exception.code, "LEAN_SHA_MISMATCH")
            # Unpinned clean passes live lean (or mocked lean on pre-Lean CI runners)
            if has_lean:
                ok_res = ver.verify_lean_file(other_l, check_pinned_sha=False)
                self.assertEqual(ok_res["theorems_verified"], 1)
            else:
                ok_mock = subprocess.CompletedProcess(
                    ["lean"], 0, stdout="'ok1' does not depend on any axioms\n", stderr=""
                )
                with mock.patch.object(ver, "_find_lean_binary", return_value="lean"):
                    with mock.patch.object(subprocess, "run", return_value=ok_mock):
                        ok_res = ver.verify_lean_file(other_l, check_pinned_sha=False)
                        self.assertEqual(ok_res["theorems_verified"], 1)

            # Live Lean R9 static finding rejected BEFORE invoking lean (kills M102)
            r9_l = tdir / "r9_bad.lean"
            r9_l.write_text("#eval 1 + 1\n", encoding="utf-8")
            with self.assertRaises(s77.S77Error) as e_r9:
                ver.verify_lean_file(r9_l, check_pinned_sha=False)
            self.assertEqual(e_r9.exception.code, "LEAN_R9_STATIC_FINDING")

            # Live Lean R10 char-literal quote-flip spoof & custom interpolatedStr macro rejected BEFORE lean!
            for idx_sp, spoof_src in enumerate(
                (
                    'def q1 : Char := \'"\'\n#eval IO.println "\'MellinGluQuantMargin.bad\' does not depend on any axioms"\ndef q2 : Char := \'"\'\n',
                    'def q1 : Char := \'"\'\ntheorem bad : False := by sorry\ndef q2 : Char := \'"\'\n#print axioms bad\n',
                    'def q1 : Char := \'"\'\naxiom bad : False\ndef q2 : Char := \'"\'\n#print axioms bad\n',
                    'def q1 : Char := \'"\'\ntheorem bad : 1 = 1 := by native_decide\ndef q2 : Char := \'"\'\n#print axioms bad\n',
                    "def q1 : Char := '\\''\ndef q2 : Char := '\"'\ntheorem bad : False := by sorry\ndef q3 : Char := '\"'\n",
                    'syntax "foo!" interpolatedStr(term) : term\nmacro_rules | `(foo! $s:interpolatedStr) => `(s! $s)\ndef x := foo!"a {((by sorry : Nat))}"\n',
                )
            ):
                sp_l = tdir / f"spoof_{idx_sp}.lean"
                sp_l.write_text(spoof_src, encoding="utf-8")
                with self.assertRaises(s77.S77Error) as e_sp:
                    ver.verify_lean_file(sp_l, check_pinned_sha=False)
                self.assertEqual(e_sp.exception.code, "LEAN_R9_STATIC_FINDING")

            # Multi-line wrapped #print axioms accepted when allowed, rejected on forbidden axiom or duplicate theorem
            wrap_ok = subprocess.CompletedProcess(
                ["lean"], 0, stdout="'ok1' depends on axioms: [\n  propext\n]\n'ok2' does not depend on any axioms\n", stderr=""
            )
            with mock.patch.object(ver, "_find_lean_binary", return_value="lean"):
                with mock.patch.object(subprocess, "run", return_value=wrap_ok):
                    w_res = ver.verify_lean_file(other_l, check_pinned_sha=False)
                    self.assertEqual(w_res["theorems_verified"], 2)

                wrap_bad = subprocess.CompletedProcess(
                    ["lean"], 0, stdout="'ok1' depends on axioms: [\n  propext,\n  Classical.choice\n]\n", stderr=""
                )
                with mock.patch.object(subprocess, "run", return_value=wrap_bad):
                    with self.assertRaises(s77.S77Error) as e_wb:
                        ver.verify_lean_file(other_l, check_pinned_sha=False)
                    self.assertEqual(e_wb.exception.code, "LEAN_FORBIDDEN_AXIOM")

                dup_out = subprocess.CompletedProcess(
                    ["lean"], 0, stdout="'ok1' does not depend on any axioms\n'ok1' does not depend on any axioms\n", stderr=""
                )
                with mock.patch.object(subprocess, "run", return_value=dup_out):
                    with self.assertRaises(s77.S77Error) as e_dup:
                        ver.verify_lean_file(other_l, check_pinned_sha=False)
                    self.assertEqual(e_dup.exception.code, "LEAN_DUPLICATE_THEOREM")

            # Live Lean forbidden axiom Classical.choice & compile failure rejected!
            cl_l = tdir / "classical.lean"
            cl_l.write_text(
                "theorem use_em (p : Prop) : p ∨ ¬ p := Classical.em p\n#print axioms use_em\n",
                encoding="utf-8",
            )
            bad_l = tdir / "bad.lean"
            bad_l.write_text("theorem bad : 1 = 2 := rfl\n", encoding="utf-8")
            if has_lean:
                with self.assertRaises(s77.S77Error) as e4:
                    ver.verify_lean_file(cl_l, check_pinned_sha=False)
                self.assertEqual(e4.exception.code, "LEAN_FORBIDDEN_AXIOM")

                with self.assertRaises(s77.S77Error) as e5:
                    ver.verify_lean_file(bad_l, check_pinned_sha=False)
                self.assertEqual(e5.exception.code, "LEAN_COMPILE_FAILED")
            else:
                fake_fail = subprocess.CompletedProcess(["lean"], 1, stdout="", stderr="type mismatch")
                with mock.patch.object(ver, "_find_lean_binary", return_value="lean"):
                    with mock.patch.object(subprocess, "run", return_value=fake_fail):
                        with self.assertRaises(s77.S77Error) as e5:
                            ver.verify_lean_file(bad_l, check_pinned_sha=False)
                        self.assertEqual(e5.exception.code, "LEAN_COMPILE_FAILED")

            # Unexpected stdout / stderr / missing binary / theorem set mismatch via mock
            with mock.patch.object(ver, "_find_lean_binary", return_value="lean"):
                fake_proc_err = subprocess.CompletedProcess(["lean"], 0, stdout="", stderr="warn")
                with mock.patch.object(subprocess, "run", return_value=fake_proc_err):
                    with self.assertRaises(s77.S77Error) as e6:
                        ver.verify_lean_file(other_l, check_pinned_sha=False)
                    self.assertEqual(e6.exception.code, "LEAN_STDERR_NONEMPTY")

                fake_proc_out = subprocess.CompletedProcess(["lean"], 0, stdout="weird line\n", stderr="")
                with mock.patch.object(subprocess, "run", return_value=fake_proc_out):
                    with self.assertRaises(s77.S77Error) as e7:
                        ver.verify_lean_file(other_l, check_pinned_sha=False)
                    self.assertEqual(e7.exception.code, "LEAN_UNEXPECTED_OUTPUT")

                fake_proc_thm = subprocess.CompletedProcess(
                    ["lean"], 0, stdout="'Wrong.thm' does not depend on any axioms\n", stderr=""
                )
                with mock.patch.object(subprocess, "run", return_value=fake_proc_thm):
                    with self.assertRaises(s77.S77Error) as e8:
                        ver.verify_lean_file(lean_file, check_pinned_sha=True)
                    self.assertEqual(e8.exception.code, "LEAN_THEOREM_SET_MISMATCH")

            with mock.patch.object(ver.shutil, "which", return_value=None):
                with mock.patch.object(Path, "is_file", return_value=False):
                    with self.assertRaises(s77.S77Error) as e9:
                        ver._find_lean_binary()
                    self.assertEqual(e9.exception.code, "LEAN_BINARY_NOT_FOUND")
                with mock.patch.object(Path, "is_file", return_value=True):
                    self.assertTrue(ver._find_lean_binary().endswith("lean"))


if __name__ == "__main__":
    unittest.main()
