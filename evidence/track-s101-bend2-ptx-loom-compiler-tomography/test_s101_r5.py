#!/usr/bin/env python3
"""
Track S101 Assertion-Free R5 Hardened Unit Test Suite.

Covers all 4 Pillars (Bend 2 BendTT adversarial tomography, live CPU sm_86 ptxas/nvdisasm
SASS audit, siliconcordat/loom main+PRs #5/#7/#9 x Zero-PyTorch libcuda.so roofline,
provenance & Lean 4.36.0 companion), exact-Q oracle boundaries, Zone-B fail-closed I/O & JSON
attacks, 4-surface API (CLI/FR1/FR0/SEC), (0o600, 0o644) committed disk-cert parity + strict
0o600 --write, scratch os.mkfifo probes, hardlinks, symlinks, read-only directories,
--verify-ptx / --verify-upstream / --verify-bend / --verify-loom checks, scrubbed subprocess
environments (stripping LEAN_PATH/LEAN_OPTS/LEAN_SYSROOT/ELAN_*/LD_PRELOAD/LD_LIBRARY_PATH),
all upgraded R12 static Lean 4 bypasses (incl. decide +revert +native, multiline decide,
config := { native }, debug.terminalTacticsAsSorry, warn.sorry, dbg_trace/dbg_sleep/dbg_stack_trace,
dbgTrace*, panic!/panicWithPosWithDecl/unreachable!, initialize, partial, opaque,
@[export]/@[init]/@[builtin_init]/@[term_elab]/@[command_elab]/@[tactic]/@[macro]/@[macro_rules],
Std import, #exit, #guard, #guard_msgs, bv_decide), AND 0-skip Lean-less CI dual-mode compatibility!
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

import s101_compiler_loom_oracle as s101
import verify_s101_compiler_loom as ver


def _resign(cert: dict) -> dict:
    p_sha = hashlib.sha256(s101.canonical_json_bytes(cert["payload"])).hexdigest()
    env = {
        "schema": cert["schema"],
        "track_id": cert["track_id"],
        "payload_sha256": p_sha,
        "payload": cert["payload"],
    }
    c_sha = hashlib.sha256(s101.canonical_json_bytes(env)).hexdigest()
    return {
        "schema": cert["schema"],
        "track_id": cert["track_id"],
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "payload": cert["payload"],
    }


class TestS101OraclePrimitives(unittest.TestCase):
    def test_error_guards_formatters_and_det(self) -> None:
        err = s101.S101Error("E_CODE", "e msg")
        self.assertEqual(err.code, "E_CODE")
        self.assertEqual(err.message, "e msg")
        self.assertEqual(str(err), "[E_CODE] e msg")

        s101.require_ok(True, "OK", "ok")
        for bad in (False, 1, "yes", None):
            with self.assertRaises(s101.S101Error) as ctx:
                s101.require_ok(bad, "BAD_COND", "bad")  # type: ignore[arg-type]
            self.assertEqual(ctx.exception.code, "BAD_COND")

        self.assertEqual(s101.q_obj(Fraction(-6, 4)), {"num": -3, "den": 2})
        with self.assertRaises(s101.S101Error) as cq:
            s101.q_obj(3)  # type: ignore[arg-type]
        self.assertEqual(cq.exception.code, "INVALID_FRACTION")

        self.assertEqual(s101.frac_to_dec_str(Fraction(1, 4), 1), "0.2")
        self.assertEqual(s101.frac_to_dec_str(Fraction(1, 8), 3), "0.125")
        self.assertEqual(s101.frac_to_dec_str(Fraction(1, 2), 12), "0.500000000000")
        with self.assertRaises(s101.S101Error):
            s101.frac_to_dec_str(1, 2)  # type: ignore[arg-type]
        for bad_pl in (0, 13, True):
            with self.assertRaises(s101.S101Error) as cpl:
                s101.frac_to_dec_str(Fraction(1, 2), bad_pl)  # type: ignore[arg-type]
            self.assertEqual(cpl.exception.code, "INVALID_PLACES")

        self.assertEqual(s101._check_exact_int(7, "x"), 7)
        with self.assertRaises(s101.S101Error):
            s101._check_exact_int(True, "x")
        self.assertEqual(s101._check_exact_frac(Fraction(2, 3), "f"), Fraction(2, 3))
        with self.assertRaises(s101.S101Error):
            s101._check_exact_frac(2, "f")  # type: ignore[arg-type]

        # exact_det_q positive, negative swap, singular, 3x3, invalid inputs
        self.assertEqual(s101.exact_det_q([[Fraction(5)]]), Fraction(5))
        self.assertEqual(
            s101.exact_det_q([[Fraction(0), Fraction(1)], [Fraction(1), Fraction(0)]]),
            Fraction(-1),
        )
        self.assertEqual(
            s101.exact_det_q([[Fraction(1), Fraction(2)], [Fraction(2), Fraction(4)]]),
            Fraction(0),
        )
        for bad_m in ([], "notlist", ([Fraction(1)],), [(Fraction(1),)], [[Fraction(1), Fraction(2)]], [[1]]):
            with self.assertRaises(s101.S101Error):
                s101.exact_det_q(bad_m)  # type: ignore[arg-type]

    def test_domain_evaluators_and_boundaries(self) -> None:
        # eval_sm86_occupancy boundaries (kills >= 1 and >= 256 BoolOps!)
        o1 = s101.eval_sm86_occupancy(1, 1, 1, 256)
        self.assertEqual(o1["active_warps_per_sm"], 1)
        self.assertTrue(o1["full_occupancy_achieved"])
        for bad_occ in ((0, 32, 48, 65536), (16, 0, 48, 65536), (16, 32, 0, 65536), (16, 32, 48, 255)):
            with self.assertRaises(s101.S101Error) as c_o:
                s101.eval_sm86_occupancy(*bad_occ)
            self.assertEqual(c_o.exception.code, "NONPOS_OCC_PARAM")

        # eval_dispatch_crossover boundaries
        d1 = s101.eval_dispatch_crossover(
            bw_gb_s_q=Fraction(100),
            eager_us_q=Fraction(10),
            uvm_fault_us_q=Fraction(5),
            graph_us_q=Fraction(10),
            num_launches=1,
        )
        self.assertFalse(d1["uvm_strictly_worse_than_eager"])
        self.assertFalse(d1["graph_strictly_beats_eager"])
        with self.assertRaises(s101.S101Error) as c_nr:
            s101.eval_dispatch_crossover(
                bw_gb_s_q=Fraction(0),
                eager_us_q=Fraction(10),
                uvm_fault_us_q=Fraction(20),
                graph_us_q=Fraction(1),
                num_launches=1,
            )
        self.assertEqual(c_nr.exception.code, "NONPOS_ROOFLINE")
        with self.assertRaises(s101.S101Error) as c_nl:
            s101.eval_dispatch_crossover(
                bw_gb_s_q=Fraction(100),
                eager_us_q=Fraction(10),
                uvm_fault_us_q=Fraction(20),
                graph_us_q=Fraction(1),
                num_launches=0,
            )
        self.assertEqual(c_nl.exception.code, "NONPOS_LAUNCHES")

        # eval_pcie_double_buffer boundaries (both sides of BoolOp + equality)
        p_eq = s101.eval_pcie_double_buffer(Fraction(12), Fraction(12))
        self.assertFalse(p_eq["decode_b1_transfer_bound"])
        self.assertTrue(p_eq["double_buffer_hides_dense_b1"])
        for bad_bw in ((Fraction(0), Fraction(12)), (Fraction(12), Fraction(0))):
            with self.assertRaises(s101.S101Error) as c_bw:
                s101.eval_pcie_double_buffer(*bad_bw)
            self.assertEqual(c_bw.exception.code, "NONPOS_BW")

    def test_four_pillars_certificate_values(self) -> None:
        cert = s101.build_certificate()
        ver.audit_certificate_object(cert)
        self.assertEqual(cert["schema"], s101.CERT_SCHEMA)
        self.assertEqual(cert["track_id"], s101.CERT_TRACK_ID)
        p = cert["payload"]

        p1 = p["pillar1_bend2_adversarial_tomography"]
        self.assertTrue(p1["pillar_verified"])
        self.assertEqual(p1["tcb_loc_audit"]["untrusted_ts_loc"], 13395)
        self.assertEqual(p1["tcb_loc_audit"]["bendtt_lean_kernel_loc"], 3861)
        self.assertEqual(p1["tcb_loc_audit"]["untrusted_to_kernel_ratio_q"], {"num": 4465, "den": 1287})
        self.assertEqual(p1["tcb_loc_audit"]["untrusted_to_kernel_ratio_dec"], "3.4693")
        self.assertEqual(p1["bendtt_lean436_live_audit"]["theorems_count"], 228)
        self.assertEqual(p1["bendtt_lean436_live_audit"]["stdout_bytes"], 8307)
        self.assertEqual(p1["bendtt_lean436_live_audit"]["stderr_bytes"], 0)
        self.assertEqual(p1["bendtt_lean436_live_audit"]["partial_parser_defs"], 17)
        self.assertEqual(p1["law4_latency_honesty"]["bend_cli_status"], "unexecuted_bun_missing")

        p2 = p["pillar2_sm86_ptx_sass_audit"]
        self.assertTrue(p2["pillar_verified"])
        self.assertFalse(p2["gpu_runtime_touched"])
        self.assertEqual(p2["kernels"]["atomic_cas_hazard"]["sass_atomg_cas_count"], 1)
        self.assertEqual(p2["kernels"]["atomic_cas_hazard"]["sass_red_add_f32_ftz_count"], 1)
        self.assertEqual(p2["kernels"]["atomic_cas_hazard"]["sass_bssy_count"], 1)
        self.assertEqual(p2["kernels"]["atomic_cas_hazard"]["sass_bsync_count"], 1)
        self.assertEqual(p2["kernels"]["atomic_cas_hazard"]["sass_yield_count"], 1)
        self.assertEqual(p2["kernels"]["det_warp_shfl_cce"]["sass_shfl_bfly_count"], 5)
        self.assertEqual(p2["kernels"]["fused_blockh4_dp4a"]["sass_idp4a_count"], 1)
        self.assertEqual(p2["sm86_occupancy_comparison"]["s101_16reg_kernels"]["occupancy_q"], {"num": 1, "den": 1})
        self.assertEqual(p2["sm86_occupancy_comparison"]["s52_52reg_live_repair"]["occupancy_q"], {"num": 3, "den": 4})

        p3 = p["pillar3_loom_libcuda_roofline"]
        self.assertTrue(p3["pillar_verified"])
        self.assertEqual(p3["dispatch_crossover_4b_n3_216ops"]["crossover_bytes_eager_q"], {"num": 4279200, "den": 1})
        self.assertEqual(p3["dispatch_crossover_4b_n3_216ops"]["crossover_bytes_uvm_q"], {"num": 12481000, "den": 1})
        self.assertEqual(p3["dispatch_crossover_4b_n3_216ops"]["crossover_bytes_graph_q"], {"num": 356600, "den": 1})
        self.assertEqual(p3["dispatch_crossover_4b_n3_216ops"]["graph_collapse_vs_eager_q"], {"num": 2592, "den": 1})
        self.assertEqual(p3["dispatch_crossover_27b_n8_3584ops"]["graph_collapse_vs_eager_q"], {"num": 43008, "den": 1})
        self.assertEqual(p3["law5_pcie_gen4x8_double_buffer"]["gpu_over_pcie_bw_ratio_q"], {"num": 1783, "den": 60})
        self.assertEqual(p3["law5_pcie_gen4x8_double_buffer"]["gpu_over_pcie_bw_ratio_dec"], "29.7167")
        self.assertEqual(p3["s94_residency_cliff_bridge"]["b_crit_bpw_q"], {"num": 325, "den": 171})
        self.assertEqual(p3["loom_main_doc04_exact"]["ive_4b_total_macs"], 1509949440)
        self.assertEqual(p3["loom_pr7_exact_inertia"]["tridiag_3x3_det_q"], {"num": -1, "den": 1})
        self.assertEqual(p3["loom_pr9_gate_contracts"]["escape_reduction_factor_q"], {"num": 35, "den": 1})

        p4 = p["pillar4_provenance_and_lean4"]
        self.assertEqual(p4["upstream_receipt_count"], 5)
        self.assertEqual(p4["bend2_file_count"], 7)
        self.assertEqual(p4["loom_branch_count"], 4)
        self.assertEqual(p4["loom_doc_count"], 5)
        self.assertEqual(p4["lean4_certificate"]["theorem_count"], 18)
        self.assertEqual(p4["novelty_honesty_law4"]["n2_claims"], 0)


class TestS101VerifierZoneBAndIO(unittest.TestCase):
    def test_json_tree_and_parser_hardening(self) -> None:
        ver.validate_json_tree_iterative({"a": [1, True, None, "ok", (1 << 2048) - 1]}, max_depth=256)
        ver.validate_json_tree_iterative(1, max_depth=1)
        ver.validate_json_tree_iterative([[1]], max_depth=2)
        for bad_depth in (0, 257, True):
            with self.assertRaises(s101.S101Error) as cd:
                ver.validate_json_tree_iterative({}, max_depth=bad_depth)  # type: ignore[arg-type]
            self.assertEqual(cd.exception.code, "INVALID_MAX_DEPTH")
        with self.assertRaises(s101.S101Error) as cdep:
            ver.validate_json_tree_iterative([[[1]]], max_depth=2)
        self.assertEqual(cdep.exception.code, "JSON_DEPTH_EXCEEDED")
        with self.assertRaises(s101.S101Error) as cnk:
            ver.validate_json_tree_iterative({1: "a"})
        self.assertEqual(cnk.exception.code, "NON_STR_KEY")
        with self.assertRaises(s101.S101Error) as csk:
            ver.validate_json_tree_iterative({"\ud800": "a"})
        self.assertEqual(csk.exception.code, "INVALID_UNICODE_STR")
        with self.assertRaises(s101.S101Error) as csv:
            ver.validate_json_tree_iterative({"a": "\ud800"})
        self.assertEqual(csv.exception.code, "INVALID_UNICODE_STR")
        with self.assertRaises(s101.S101Error) as cbi:
            ver.validate_json_tree_iterative(1 << 2048)
        self.assertEqual(cbi.exception.code, "INT_BIT_LIMIT")
        with self.assertRaises(s101.S101Error) as cft:
            ver.validate_json_tree_iterative((1, 2))
        self.assertEqual(cft.exception.code, "FORBIDDEN_JSON_TYPE")

        class IntSub(int):
            pass

        with self.assertRaises(s101.S101Error) as cis:
            ver.validate_json_tree_iterative(IntSub(5))
        self.assertEqual(cis.exception.code, "FORBIDDEN_JSON_TYPE")

        max_2048 = (1 << 2048) - 1
        self.assertEqual(ver._parse_capped_int_token(str(max_2048)), max_2048)
        with self.assertRaises(s101.S101Error) as tok_bit:
            ver._parse_capped_int_token(str(1 << 2048))
        self.assertEqual(tok_bit.exception.code, "INT_BIT_LIMIT")
        with self.assertRaises(s101.S101Error) as tok_dig:
            ver._parse_capped_int_token("9" * (ver.MAX_INT_DIGITS + 1))
        self.assertEqual(tok_dig.exception.code, "INT_DIGIT_LIMIT")

        self.assertEqual(ver.parse_strict_json('{"x":-42,"y":[true,null,"z"]}'), {"x": -42, "y": [True, None, "z"]})
        exact_max_json = '"' + ("a" * (ver.MAX_JSON_BYTES - 2)) + '"'
        self.assertEqual(len(ver.parse_strict_json(exact_max_json)), ver.MAX_JSON_BYTES - 2)
        with self.assertRaises(s101.S101Error) as cp1:
            ver.parse_strict_json(b"{}")  # type: ignore[arg-type]
        self.assertEqual(cp1.exception.code, "INVALID_JSON_TEXT")
        with self.assertRaises(s101.S101Error) as cp2:
            ver.parse_strict_json('"\ud800"')
        self.assertEqual(cp2.exception.code, "INVALID_UNICODE_STR")
        with self.assertRaises(s101.S101Error) as cp3:
            ver.parse_strict_json('"' + ("a" * (ver.MAX_JSON_BYTES + 1)) + '"')
        self.assertEqual(cp3.exception.code, "JSON_TOO_LARGE")
        with self.assertRaises(s101.S101Error) as cp4:
            ver.parse_strict_json('{"a":1,"\\u0061":2}')
        self.assertEqual(cp4.exception.code, "DUPLICATE_JSON_KEY")
        with self.assertRaises(s101.S101Error) as cp5:
            ver.parse_strict_json('{"a":1.0}')
        self.assertEqual(cp5.exception.code, "FLOAT_FORBIDDEN")
        with self.assertRaises(s101.S101Error) as cp6:
            ver.parse_strict_json('{"a":NaN}')
        self.assertEqual(cp6.exception.code, "NONFINITE_CONSTANT")
        with self.assertRaises(s101.S101Error) as cp7:
            ver.parse_strict_json('{"a":' + ("9" * 5001) + "}")
        self.assertEqual(cp7.exception.code, "INT_DIGIT_LIMIT")
        with self.assertRaises(s101.S101Error) as cp7b:
            ver.parse_strict_json('{"a":-' + ("9" * (ver.MAX_INT_DIGITS + 1)) + "}")
        self.assertEqual(cp7b.exception.code, "INT_DIGIT_LIMIT")
        with self.assertRaises(s101.S101Error) as cp8:
            ver.parse_strict_json('{"a":' + str(1 << 2048) + "}")
        self.assertEqual(cp8.exception.code, "INT_BIT_LIMIT")
        with self.assertRaises(s101.S101Error) as cp9:
            ver.parse_strict_json("{broken")
        self.assertEqual(cp9.exception.code, "JSON_DECODE_ERROR")
        with self.assertRaises(s101.S101Error) as cp10:
            ver.parse_strict_json("[" * 500 + "]" * 500)
        self.assertIn(cp10.exception.code, ("JSON_DEPTH_EXCEEDED", "JSON_DECODE_ERROR"))

    def test_digest_exact_equal_and_four_surfaces(self) -> None:
        good_h = "0123456789abcdef" * 4
        self.assertEqual(ver.require_sha256_hex(good_h, "h"), good_h)
        with self.assertRaises(s101.S101Error) as d1:
            ver.require_sha256_hex(123, "h")
        self.assertEqual(d1.exception.code, "INVALID_DIGEST_TYPE")
        with self.assertRaises(s101.S101Error) as d2:
            ver.require_sha256_hex("a" * 63, "h")
        self.assertEqual(d2.exception.code, "INVALID_DIGEST_LEN")
        with self.assertRaises(s101.S101Error) as d3:
            ver.require_sha256_hex("A" * 64, "h")
        self.assertEqual(d3.exception.code, "INVALID_DIGEST_HEX")

        self.assertTrue(ver.exact_typed_equal({"a": [1, True, None]}, {"a": [1, True, None]}))
        self.assertFalse(ver.exact_typed_equal(1, True))
        self.assertFalse(ver.exact_typed_equal({"a": 1}, {"a": 1, "b": 2}))
        self.assertFalse(ver.exact_typed_equal({"a": 1}, {"b": 1}))
        self.assertFalse(ver.exact_typed_equal([1, 2], [1]))
        self.assertFalse(ver.exact_typed_equal([1, 2], [1, 3]))
        self.assertFalse(ver.exact_typed_equal("x", "y"))

        cert = s101.build_certificate()
        self.assertEqual(ver.audit_certificate_object(cert)["certificate_sha256"], cert["certificate_sha256"])

        with self.assertRaises(s101.S101Error) as a0:
            ver.audit_certificate_object([1, 2])
        self.assertEqual(a0.exception.code, "NON_OBJECT_ROOT")
        c_keys = copy.deepcopy(cert)
        c_keys["extra"] = 1
        with self.assertRaises(s101.S101Error) as a1:
            ver.audit_certificate_object(c_keys)
        self.assertEqual(a1.exception.code, "BAD_CERT_KEYS")
        c_sch = copy.deepcopy(cert)
        c_sch["schema"] = "wrong"
        with self.assertRaises(s101.S101Error) as a2:
            ver.audit_certificate_object(c_sch)
        self.assertEqual(a2.exception.code, "BAD_SCHEMA")
        c_tid = copy.deepcopy(cert)
        c_tid["track_id"] = "wrong"
        with self.assertRaises(s101.S101Error) as a3:
            ver.audit_certificate_object(c_tid)
        self.assertEqual(a3.exception.code, "BAD_TRACK_ID")
        c_pt = copy.deepcopy(cert)
        c_pt["payload"] = []
        with self.assertRaises(s101.S101Error) as a4:
            ver.audit_certificate_object(c_pt)
        self.assertEqual(a4.exception.code, "BAD_PAYLOAD_TYPE")
        c_psha = copy.deepcopy(cert)
        c_psha["payload_sha256"] = "0" * 64
        with self.assertRaises(s101.S101Error) as a5:
            ver.audit_certificate_object(c_psha)
        self.assertEqual(a5.exception.code, "PAYLOAD_SHA_MISMATCH")
        c_csha = copy.deepcopy(cert)
        c_csha["certificate_sha256"] = "0" * 64
        with self.assertRaises(s101.S101Error) as a6:
            ver.audit_certificate_object(c_csha)
        self.assertEqual(a6.exception.code, "CERT_SHA_MISMATCH")

        self.assertEqual(
            ver.verify_certificate_dict(cert, full_replay=False)["certificate_sha256"],
            cert["certificate_sha256"],
        )
        with self.assertRaises(s101.S101Error) as fr_bad:
            ver.verify_certificate_dict(cert, full_replay=1)  # type: ignore[arg-type]
        self.assertEqual(fr_bad.exception.code, "INVALID_FULL_REPLAY")
        self.assertIs(ver.secondary_audit_payload(cert["payload"]), cert["payload"])
        with self.assertRaises(s101.S101Error) as sec_nd:
            ver.secondary_audit_payload([1, 2])
        self.assertEqual(sec_nd.exception.code, "BAD_PAYLOAD_TYPE")

        # Strict rational dict rejections + non-_q half-rat tree-walk BoolOp killers
        self.assertEqual(ver._parse_rat_dict({"num": -3, "den": 2}), Fraction(-3, 2))
        for bad_rat in (
            123,
            {"num": 0, "den": 0, "extra": 1},
            {"num": 0, "other": 1},
            {"other": 0, "den": 1},
            {"num": True, "den": 1},
            {"num": 1, "den": True},
            {"num": 1, "den": 0},
            {"num": 1, "den": -1},
            {"num": 4, "den": 2},
        ):
            with self.assertRaises(s101.S101Error) as e_rat:
                ver._parse_rat_dict(bad_rat)
            self.assertEqual(e_rat.exception.code, "BAD_RATIONAL_DICT")
            c_rat = copy.deepcopy(cert)
            c_rat["payload"]["pillar1_bend2_adversarial_tomography"]["tcb_loc_audit"]["untrusted_to_kernel_ratio_q"] = bad_rat
            for surface_fn in (
                lambda c: ver.secondary_audit_payload(c["payload"]),
                lambda c: ver.verify_certificate_dict(_resign(c), full_replay=False),
                lambda c: ver.verify_certificate_dict(_resign(c), full_replay=True),
            ):
                with self.assertRaises(s101.S101Error) as e_r2:
                    surface_fn(c_rat)
                self.assertIn(e_r2.exception.code, ("BAD_RATIONAL_DICT", "UNEXPECTED_BOOL_FIELD"))
        for bad_half_rat in ({"num": 0, "other": 1}, {"other": 0, "den": 1}):
            c_hr = copy.deepcopy(cert)
            c_hr["payload"]["pillar1_bend2_adversarial_tomography"]["law4_latency_honesty"]["proven_commons_catalog_repos"] = bad_half_rat
            with self.assertRaises(s101.S101Error) as e_hr:
                ver.secondary_audit_payload(c_hr["payload"])
            self.assertEqual(e_hr.exception.code, "BAD_RATIONAL_DICT")

        c_bool_fld = copy.deepcopy(cert)
        c_bool_fld["payload"]["pillar1_bend2_adversarial_tomography"]["law4_latency_honesty"]["proven_commons_catalog_repos"] = True
        with self.assertRaises(s101.S101Error) as a7f:
            ver.secondary_audit_payload(c_bool_fld["payload"])
        self.assertEqual(a7f.exception.code, "UNEXPECTED_BOOL_FIELD")
        c_bool_lst = copy.deepcopy(cert)
        c_bool_lst["payload"]["pillar3_loom_libcuda_roofline"]["loom_pr7_exact_inertia"]["true_inertia_pos_neg_zero"][0] = True
        with self.assertRaises(s101.S101Error) as a7l:
            ver.secondary_audit_payload(c_bool_lst["payload"])
        self.assertEqual(a7l.exception.code, "UNEXPECTED_BOOL_ITEM")
        c_bad_pin = copy.deepcopy(cert)
        c_bad_pin["payload"]["pillar4_provenance_and_lean4"]["upstream_receipt_manifest"][0]["sha256"] = "Z" * 64
        with self.assertRaises(s101.S101Error) as a7s:
            ver.secondary_audit_payload(c_bad_pin["payload"])
        self.assertEqual(a7s.exception.code, "INVALID_DIGEST_HEX")

        with self.assertRaises(s101.S101Error):
            ver._req_int("not_int", "BAD_INT")
        with self.assertRaises(s101.S101Error):
            ver._req_dict([], frozenset({"a"}), "BAD_D")
        with self.assertRaises(s101.S101Error):
            ver._req_dict({"b": 1}, frozenset({"a"}), "BAD_D")

        # Direct consistent-state boundary probes on _audit_* helpers (kills EVERY denominator/boundary guard!)
        occ_mw1 = s101.eval_sm86_occupancy(16, 32, 1, 65536)
        ver._audit_occupancy(occ_mw1, True)
        occ_arw0 = copy.deepcopy(occ_mw1)
        occ_arw0.update({"regs_per_thread": 0, "alloc_regs_per_warp": 0})
        with self.assertRaises(s101.S101Error) as e_arw0:
            ver._audit_occupancy(occ_arw0, True)
        self.assertEqual(e_arw0.exception.code, "BAD_OCC_INV")
        occ_mw0 = copy.deepcopy(occ_mw1)
        occ_mw0["max_warps_per_sm"] = 0
        with self.assertRaises(s101.S101Error) as e_mw0:
            ver._audit_occupancy(occ_mw0, True)
        self.assertEqual(e_mw0.exception.code, "BAD_OCC_INV")

        d_nl2 = s101.eval_dispatch_crossover(
            bw_gb_s_q=Fraction(100), eager_us_q=Fraction(12), uvm_fault_us_q=Fraction(35), graph_us_q=Fraction(1), num_launches=2
        )
        ver._audit_dispatch(d_nl2, Fraction(100))
        d_nl1 = s101.eval_dispatch_crossover(
            bw_gb_s_q=Fraction(100), eager_us_q=Fraction(12), uvm_fault_us_q=Fraction(35), graph_us_q=Fraction(1), num_launches=1
        )
        with self.assertRaises(s101.S101Error) as e_nl1:
            ver._audit_dispatch(d_nl1, Fraction(100))
        self.assertEqual(e_nl1.exception.code, "BAD_DISP_INV")
        d_tg0 = copy.deepcopy(d_nl2)
        d_tg0["graph_launch_us_q"] = {"num": 0, "den": 1}
        with self.assertRaises(s101.S101Error) as e_tg0:
            ver._audit_dispatch(d_tg0, Fraction(100))
        self.assertEqual(e_tg0.exception.code, "BAD_DISP_INV")

        p1_k0 = copy.deepcopy(cert["payload"]["pillar1_bend2_adversarial_tomography"])
        p1_k0["tcb_loc_audit"]["bendtt_lean_kernel_loc"] = 0
        with self.assertRaises(s101.S101Error) as e_k0:
            ver._audit_pillar1(p1_k0)
        self.assertEqual(e_k0.exception.code, "BAD_P1_INV")
        p1_t0 = copy.deepcopy(cert["payload"]["pillar1_bend2_adversarial_tomography"])
        p1_t0["tcb_loc_audit"]["total_compiler_loc"] = 0
        with self.assertRaises(s101.S101Error) as e_t0:
            ver._audit_pillar1(p1_t0)
        self.assertEqual(e_t0.exception.code, "BAD_P1_INV")

        p2_tr0 = copy.deepcopy(cert["payload"]["pillar2_sm86_ptx_sass_audit"])
        p2_tr0["s86_empirical_hazard_anchor"]["total_rows"] = 0
        with self.assertRaises(s101.S101Error) as e_tr0:
            ver._audit_pillar2(p2_tr0)
        self.assertEqual(e_tr0.exception.code, "BAD_P2_INV")

        p3_b0 = copy.deepcopy(cert["payload"]["pillar3_loom_libcuda_roofline"])
        p3_b0["law5_pcie_gen4x8_double_buffer"]["bw_pcie_gb_s_q"] = {"num": 0, "den": 1}
        with self.assertRaises(s101.S101Error) as e_b0:
            ver._audit_pillar3(p3_b0)
        self.assertEqual(e_b0.exception.code, "BAD_P3_INV")
        p3_es0 = copy.deepcopy(cert["payload"]["pillar3_loom_libcuda_roofline"])
        p3_es0["loom_pr9_gate_contracts"]["strong_escape_rate_q"] = {"num": 0, "den": 1}
        with self.assertRaises(s101.S101Error) as e_es0:
            ver._audit_pillar3(p3_es0)
        self.assertEqual(e_es0.exception.code, "BAD_P3_INV")

        # Comprehensive live re-signed semantic tampers: ALL MUST FAIL across SEC, FR0, AND FR1!
        semantic_tampers: list[tuple[str, Any, str]] = [
            ("empty_p1_to_p3", lambda d: d.update({"pillar1_bend2_adversarial_tomography": {}, "pillar2_sm86_ptx_sass_audit": {}, "pillar3_loom_libcuda_roofline": {}}), "BAD_P1_SCHEMA"),
            ("p1_verified_false", lambda d: d["pillar1_bend2_adversarial_tomography"].__setitem__("pillar_verified", False), "BAD_P1_INV"),
            ("p1_commit_bad", lambda d: d["pillar1_bend2_adversarial_tomography"].__setitem__("bend2_commit", "0" * 40), "BAD_P1_INV"),
            ("p1_tcb_sum_bad", lambda d: d["pillar1_bend2_adversarial_tomography"]["tcb_loc_audit"].__setitem__("untrusted_ts_loc", 10), "BAD_P1_INV"),
            ("p1_tcb_dec_bad", lambda d: d["pillar1_bend2_adversarial_tomography"]["tcb_loc_audit"].__setitem__("untrusted_to_kernel_ratio_dec", "GARBAGE"), "BAD_P1_INV"),
            ("p1_ksh_dec_bad", lambda d: d["pillar1_bend2_adversarial_tomography"]["tcb_loc_audit"].__setitem__("kernel_loc_share_pct_dec", "GARBAGE"), "BAD_P1_INV"),
            ("p1_btt_sorry", lambda d: d["pillar1_bend2_adversarial_tomography"]["bendtt_lean436_live_audit"].__setitem__("sorry_count", 1), "BAD_P1_INV"),
            ("p1_btt_thms_drift", lambda d: d["pillar1_bend2_adversarial_tomography"]["bendtt_lean436_live_audit"].__setitem__("theorems_count", 227), "BAD_P1_INV"),
            ("p1_btt_stdout_drift", lambda d: d["pillar1_bend2_adversarial_tomography"]["bendtt_lean436_live_audit"].__setitem__("stdout_bytes", 0), "BAD_P1_INV"),
            ("p1_btt_warn_drift", lambda d: d["pillar1_bend2_adversarial_tomography"]["bendtt_lean436_live_audit"].__setitem__("tactic_warnings_on_lean436", 71), "BAD_P1_INV"),
            ("p1_btt_axioms", lambda d: d["pillar1_bend2_adversarial_tomography"]["bendtt_lean436_live_audit"].__setitem__("top_theorem_axioms", ["sorryAx"]), "BAD_P1_INV"),
            ("p1_lat_status", lambda d: d["pillar1_bend2_adversarial_tomography"]["law4_latency_honesty"].__setitem__("bend_cli_status", "fabricated"), "BAD_P1_INV"),
            ("p1_catalog_41_drift", lambda d: d["pillar1_bend2_adversarial_tomography"]["law4_latency_honesty"].__setitem__("proven_commons_catalog_repos", 41), "BAD_P1_INV"),
            ("p2_verified_false", lambda d: d["pillar2_sm86_ptx_sass_audit"].__setitem__("pillar_verified", False), "BAD_P2_INV"),
            ("p2_gpu_touched", lambda d: d["pillar2_sm86_ptx_sass_audit"].__setitem__("gpu_runtime_touched", True), "BAD_P2_INV"),
            ("p2_ka_spill", lambda d: d["pillar2_sm86_ptx_sass_audit"]["kernels"]["atomic_cas_hazard"].__setitem__("spill_stores_bytes", 4), "BAD_P2_INV"),
            ("p2_ka_bssy", lambda d: d["pillar2_sm86_ptx_sass_audit"]["kernels"]["atomic_cas_hazard"].__setitem__("sass_bssy_count", 0), "BAD_P2_INV"),
            ("p2_ka_sha", lambda d: d["pillar2_sm86_ptx_sass_audit"]["kernels"]["atomic_cas_hazard"].__setitem__("ptx_sha256", "0" * 64), "BAD_P2_INV"),
            ("p2_kb_shfl", lambda d: d["pillar2_sm86_ptx_sass_audit"]["kernels"]["det_warp_shfl_cce"].__setitem__("sass_shfl_bfly_count", 4), "BAD_P2_INV"),
            ("p2_kc_fadd", lambda d: d["pillar2_sm86_ptx_sass_audit"]["kernels"]["fused_blockh4_dp4a"].__setitem__("sass_fadd_count", 1), "BAD_P2_INV"),
            ("p2_s86_pct", lambda d: d["pillar2_sm86_ptx_sass_audit"]["s86_empirical_hazard_anchor"].__setitem__("atomic_cas_divergent_pct_dec", "0.00"), "BAD_P2_INV"),
            ("p2_s86_ulp_drift", lambda d: d["pillar2_sm86_ptx_sass_audit"]["s86_empirical_hazard_anchor"].__setitem__("atomic_cas_max_ulp", 14), "BAD_P2_INV"),
            ("p2_s68_maxabs_drift", lambda d: d["pillar2_sm86_ptx_sass_audit"]["s68_blockh4_dp4a_anchor"].__setitem__("max_butterfly_abs", 29), "BAD_P2_INV"),
            ("p2_s68_bpw", lambda d: d["pillar2_sm86_ptx_sass_audit"]["s68_blockh4_dp4a_anchor"].__setitem__("bpw_q", {"num": 4, "den": 1}), "BAD_P2_INV"),
            ("p2_occ_pct", lambda d: d["pillar2_sm86_ptx_sass_audit"]["sm86_occupancy_comparison"]["s101_16reg_kernels"].__setitem__("occupancy_pct_dec", "50.00"), "BAD_OCC_INV"),
            ("p3_verified_false", lambda d: d["pillar3_loom_libcuda_roofline"].__setitem__("pillar_verified", False), "BAD_P3_INV"),
            ("p3_disp_me", lambda d: d["pillar3_loom_libcuda_roofline"]["dispatch_crossover_4b_n3_216ops"].__setitem__("crossover_bytes_eager_q", {"num": 1, "den": 1}), "BAD_DISP_INV"),
            ("p3_pcie_dec", lambda d: d["pillar3_loom_libcuda_roofline"]["law5_pcie_gen4x8_double_buffer"].__setitem__("gpu_over_pcie_bw_ratio_dec", "1.0000"), "BAD_P3_INV"),
            ("p3_s94_dec", lambda d: d["pillar3_loom_libcuda_roofline"]["s94_residency_cliff_bridge"].__setitem__("b_crit_bpw_dec", "GARBAGE"), "BAD_P3_INV"),
            ("p3_s94_bcrit_drift", lambda d: d["pillar3_loom_libcuda_roofline"]["s94_residency_cliff_bridge"].update({"b_crit_bpw_q": {"num": 2, "den": 1}, "b_crit_bpw_dec": "2.0000"}), "BAD_P3_INV"),
            ("p3_s94_bssd0", lambda d: d["pillar3_loom_libcuda_roofline"]["s94_residency_cliff_bridge"].__setitem__("b_ssd_gb_s_q", {"num": 0, "den": 1}), "BAD_P3_INV"),
            ("p3_s94_bram_drift", lambda d: d["pillar3_loom_libcuda_roofline"]["s94_residency_cliff_bridge"].__setitem__("b_ram_gb_s_q", {"num": 60, "den": 1}), "BAD_P3_INV"),
            ("p3_kulisch", lambda d: d["pillar3_loom_libcuda_roofline"]["loom_main_doc04_exact"].__setitem__("bf16_kulisch_container_bits", 500), "BAD_P3_INV"),
            ("p3_kulisch_span0", lambda d: d["pillar3_loom_libcuda_roofline"]["loom_main_doc04_exact"].__setitem__("bf16_kulisch_product_span_bits", 0), "BAD_P3_INV"),
            ("p3_kulisch_guard0", lambda d: d["pillar3_loom_libcuda_roofline"]["loom_main_doc04_exact"].__setitem__("bf16_kulisch_guard_bits", 0), "BAD_P3_INV"),
            ("p3_blk_bits0", lambda d: d["pillar3_loom_libcuda_roofline"]["loom_main_doc04_exact"].__setitem__("int8_2pow20_blocks_max_bits", 0), "BAD_P3_INV"),
            ("p3_ive_4b_drift", lambda d: d["pillar3_loom_libcuda_roofline"]["loom_main_doc04_exact"].__setitem__("ive_4b_total_macs", 1), "BAD_P3_INV"),
            ("p3_l5_cost", lambda d: d["pillar3_loom_libcuda_roofline"]["loom_pr5_contextual_compute"].__setitem__("closed_pathway_eval_cost", 1), "BAD_P3_INV"),
            ("p3_l5_moe0", lambda d: d["pillar3_loom_libcuda_roofline"]["loom_pr5_contextual_compute"].__setitem__("s94_sparse_moe_active_frac_q", {"num": 0, "den": 1}), "BAD_P3_INV"),
            ("p3_l5_csr0", lambda d: d["pillar3_loom_libcuda_roofline"]["loom_pr5_contextual_compute"].__setitem__("s86_csr_budget_ceiling_q", {"num": 0, "den": 1}), "BAD_P3_INV"),
            ("p3_l7_det", lambda d: d["pillar3_loom_libcuda_roofline"]["loom_pr7_exact_inertia"].__setitem__("tridiag_3x3_det_q", {"num": -2, "den": 1}), "BAD_P3_INV"),
            ("p3_l9_esc", lambda d: d["pillar3_loom_libcuda_roofline"]["loom_pr9_gate_contracts"].__setitem__("escape_reduction_factor_q", {"num": 2, "den": 1}), "BAD_P3_INV"),
            ("p3_l9_weak_drift", lambda d: d["pillar3_loom_libcuda_roofline"]["loom_pr9_gate_contracts"].update({"weak_escape_rate_q": {"num": 1, "den": 2}, "strong_escape_rate_q": {"num": 1, "den": 4}, "escape_reduction_factor_q": {"num": 2, "den": 1}}), "BAD_P3_INV"),
            ("p4_up_cnt", lambda d: d["pillar4_provenance_and_lean4"].__setitem__("upstream_receipt_count", 4), "BAD_UP_COUNT"),
            ("p4_up_nonlist", lambda d: d["pillar4_provenance_and_lean4"].__setitem__("upstream_receipt_manifest", "12345"), "BAD_UP_LIST"),
            ("p4_up_len", lambda d: d["pillar4_provenance_and_lean4"]["upstream_receipt_manifest"].pop(), "BAD_UP_LIST"),
            ("p4_up_sha", lambda d: d["pillar4_provenance_and_lean4"]["upstream_receipt_manifest"][0].__setitem__("sha256", "0" * 64), "BAD_UP_PIN"),
            ("p4_bend_cnt", lambda d: d["pillar4_provenance_and_lean4"].__setitem__("bend2_file_count", 6), "BAD_BEND_COUNT"),
            ("p4_bend_nonlist", lambda d: d["pillar4_provenance_and_lean4"].__setitem__("bend2_file_manifest", "1234567"), "BAD_BEND_LIST"),
            ("p4_bend_len", lambda d: d["pillar4_provenance_and_lean4"]["bend2_file_manifest"].pop(), "BAD_BEND_LIST"),
            ("p4_bend_sha", lambda d: d["pillar4_provenance_and_lean4"]["bend2_file_manifest"][0].__setitem__("sha256", "0" * 64), "BAD_BEND_PIN"),
            ("p4_lref_cnt", lambda d: d["pillar4_provenance_and_lean4"].__setitem__("loom_branch_count", 3), "BAD_LOOM_REF_COUNT"),
            ("p4_lref_nonlist", lambda d: d["pillar4_provenance_and_lean4"].__setitem__("loom_branch_refs", "1234"), "BAD_LOOM_REF_LIST"),
            ("p4_lref_len", lambda d: d["pillar4_provenance_and_lean4"]["loom_branch_refs"].pop(), "BAD_LOOM_REF_LIST"),
            ("p4_lref_sha", lambda d: d["pillar4_provenance_and_lean4"]["loom_branch_refs"][0].__setitem__("commit_sha", "0" * 40), "BAD_LOOM_REF_PIN"),
            ("p4_ldoc_cnt", lambda d: d["pillar4_provenance_and_lean4"].__setitem__("loom_doc_count", 4), "BAD_LOOM_DOC_COUNT"),
            ("p4_ldoc_nonlist", lambda d: d["pillar4_provenance_and_lean4"].__setitem__("loom_doc_manifest", "12345"), "BAD_LOOM_DOC_LIST"),
            ("p4_ldoc_len", lambda d: d["pillar4_provenance_and_lean4"]["loom_doc_manifest"].pop(), "BAD_LOOM_DOC_LIST"),
            ("p4_ldoc_sha", lambda d: d["pillar4_provenance_and_lean4"]["loom_doc_manifest"][0].__setitem__("sha256", "0" * 64), "BAD_LOOM_DOC_PIN"),
            ("p4_lean_sha", lambda d: d["pillar4_provenance_and_lean4"]["lean4_certificate"].__setitem__("sha256", "0" * 64), "BAD_LEAN_PIN"),
            ("p4_lean_cnt", lambda d: d["pillar4_provenance_and_lean4"]["lean4_certificate"].__setitem__("theorem_count", 17), "BAD_THEOREM_COUNT"),
            ("p4_lean_thms", lambda d: d["pillar4_provenance_and_lean4"]["lean4_certificate"].__setitem__("theorems", []), "BAD_THEOREM_LIST"),
            ("p4_lean_ax", lambda d: d["pillar4_provenance_and_lean4"]["lean4_certificate"].__setitem__("allowed_axioms", ["sorryAx"]), "BAD_ALLOWED_AXIOMS"),
            ("p4_nov_n2", lambda d: d["pillar4_provenance_and_lean4"]["novelty_honesty_law4"].__setitem__("n2_claims", 1), "BAD_NOVELTY_CLAIMS"),
        ]
        for label, mut_fn, exp_code in semantic_tampers:
            cand_c = copy.deepcopy(cert)
            mut_fn(cand_c["payload"])
            with self.assertRaises(s101.S101Error, msg=f"SEC must reject {label}") as e_s:
                ver.secondary_audit_payload(cand_c["payload"])
            self.assertEqual(e_s.exception.code, exp_code, f"SEC code for {label}")
            resigned = _resign(cand_c)
            with self.assertRaises(s101.S101Error, msg=f"FR0 must reject {label}") as e_f0:
                ver.verify_certificate_dict(resigned, full_replay=False)
            self.assertEqual(e_f0.exception.code, exp_code, f"FR0 code for {label}")
            with self.assertRaises(s101.S101Error, msg=f"FR1 must reject {label}") as e_f1:
                ver.verify_certificate_dict(resigned, full_replay=True)
            self.assertEqual(e_f1.exception.code, exp_code, f"FR1 code for {label}")

        c_hollow = copy.deepcopy(cert)
        c_hollow["payload"] = {}
        with self.assertRaises(s101.S101Error) as a8:
            ver.audit_certificate_object(_resign(c_hollow))
        self.assertEqual(a8.exception.code, "BAD_PAYLOAD_KEYS")

        # Mocked FR1 oracle divergence tests (kills both FR1 exact_typed_equal and cert_sha guards)
        fake_exp_p = copy.deepcopy(cert)
        fake_exp_p["payload"]["pillar1_bend2_adversarial_tomography"]["law4_latency_honesty"]["proven_commons_catalog_repos"] = 41
        with mock.patch.object(ver, "build_certificate", return_value=fake_exp_p):
            with self.assertRaises(s101.S101Error) as a8r:
                ver.verify_certificate_dict(cert, full_replay=True)
            self.assertEqual(a8r.exception.code, "PAYLOAD_ORACLE_MISMATCH")

        fake_exp = copy.deepcopy(cert)
        fake_exp["certificate_sha256"] = "f" * 64
        with mock.patch.object(ver, "build_certificate", return_value=fake_exp):
            with self.assertRaises(s101.S101Error) as a9:
                ver.audit_certificate_object(cert)
            self.assertEqual(a9.exception.code, "ORACLE_CERT_SHA_MISMATCH")

    def test_committed_disk_cert_manifests_ptx_and_hardened_io(self) -> None:
        disk_cert = _SCRIPT_DIR / "s101_compiler_loom_certificate.json"
        mode = stat.S_IMODE(disk_cert.stat().st_mode)
        self.assertIn(mode, (0o600, 0o644))
        checked = ver.check_certificate_file(disk_cert)

        out_buf = io.BytesIO()
        with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": out_buf})()):
            rc = ver.main(["--standalone", "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(out_buf.getvalue(), disk_cert.read_bytes())
        out_buf2 = io.BytesIO()
        with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": out_buf2})()):
            rc2 = ver.main([])
        self.assertEqual(rc2, 0)
        self.assertEqual(out_buf2.getvalue(), disk_cert.read_bytes())

        chk_buf = io.BytesIO()
        with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": chk_buf})()):
            rc = ver.main(["--check", str(disk_cert), "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(chk_buf.getvalue().decode("utf-8"))["status"], "PASS")
        self.assertEqual(ver.main(["--check", str(disk_cert)]), 0)

        # Scrubbed subprocess environment check (strips LEAN_PATH/LEAN_OPTS/ELAN_*/LD_PRELOAD/LD_LIBRARY_PATH)
        hostile_env = {
            "PATH": "/evil/bin",
            "HOME": "/tmp/fakehome",
            "LEAN_PATH": "/evil/olean",
            "LEAN_OPTS": "--evil",
            "LEAN_SYSROOT": "/evil/sysroot",
            "ELAN_TOOLCHAIN": "evil",
            "ELAN_HOME": "/evil/elan",
            "LEAN_CC": "/evil/cc",
            "LD_PRELOAD": "/evil/lib.so",
            "LD_LIBRARY_PATH": "/evil/lib",
            "GIT_CONFIG_GLOBAL": "/evil/gitconfig",
        }
        with mock.patch.object(ver.os, "environ", hostile_env):
            scrub = ver._scrubbed_tool_env()
            self.assertEqual(scrub["PATH"], "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/bin")
            self.assertEqual(scrub["HOME"], "/tmp/fakehome")
            for forbidden_k in (
                "LEAN_PATH", "LEAN_OPTS", "LEAN_SYSROOT", "ELAN_TOOLCHAIN", "ELAN_HOME",
                "LEAN_CC", "LD_PRELOAD", "LD_LIBRARY_PATH", "GIT_CONFIG_GLOBAL",
            ):
                self.assertNotIn(forbidden_k, scrub)
        with mock.patch.object(ver.os, "environ", {}):
            self.assertNotIn("HOME", ver._scrubbed_tool_env())

        # Live or dual-mode CPU ptxas/nvdisasm checks (0 skips in tool-less CI!)
        has_ptx = True
        try:
            ver._find_cuda_cpu_tool("ptxas", "PTXAS_BIN")
            ver._find_cuda_cpu_tool("nvdisasm", "NVDISASM_BIN")
        except s101.S101Error:
            has_ptx = False
        if has_ptx:
            ptx_buf = io.BytesIO()
            with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": ptx_buf})()):
                rc_ptx = ver.main(["--verify-ptx", "--json"])
            self.assertEqual(rc_ptx, 0)
            self.assertEqual(json.loads(ptx_buf.getvalue().decode("utf-8"))["kernels_verified"], 3)
            self.assertEqual(ver.main(["--verify-ptx"]), 0)

        # Mocked ptxas/nvdisasm error & discovery paths (runs in ALL CI envs!)
        with tempfile.TemporaryDirectory(prefix="s101_io_") as td:
            tdir = Path(td).resolve()
            fake_tool = tdir / "fake_tool"
            fake_tool.write_text("#!/bin/sh\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"PTXAS_BIN": str(fake_tool)}):
                self.assertEqual(ver._find_cuda_cpu_tool("ptxas", "PTXAS_BIN"), str(fake_tool))
            with mock.patch.dict(os.environ, {"PTXAS_BIN": str(tdir / "missing_tool")}):
                with self.assertRaises(s101.S101Error) as e_ct:
                    ver._find_cuda_cpu_tool("ptxas", "PTXAS_BIN")
                self.assertEqual(e_ct.exception.code, "CUDA_TOOL_NOT_FOUND")
            with mock.patch.dict(os.environ, {"PTXAS_BIN": ""}):
                with mock.patch.object(ver.shutil, "which", return_value="/mock/ptxas"):
                    self.assertEqual(ver._find_cuda_cpu_tool("ptxas", "PTXAS_BIN"), "/mock/ptxas")
                with mock.patch.object(ver.shutil, "which", return_value=None):
                    with mock.patch.object(Path, "is_file", return_value=False):
                        with self.assertRaises(s101.S101Error) as e_ct2:
                            ver._find_cuda_cpu_tool("ptxas", "PTXAS_BIN")
                        self.assertEqual(e_ct2.exception.code, "CUDA_TOOL_NOT_FOUND")
                    with mock.patch.object(Path, "is_file", return_value=True):
                        self.assertTrue(ver._find_cuda_cpu_tool("ptxas", "PTXAS_BIN").endswith("ptxas"))

            with mock.patch.object(ver, "_find_cuda_cpu_tool", return_value="/mock/tool"):
                with mock.patch.object(subprocess, "run", return_value=subprocess.CompletedProcess(["ptxas"], 1, "", "err")):
                    with self.assertRaises(s101.S101Error) as e_pf:
                        ver.verify_ptx_kernels_live()
                    self.assertEqual(e_pf.exception.code, "PTXAS_COMPILE_FAILED")
                # Missing regs OR missing spills (kills BoolOp on m_sp is not None and m_rg is not None!)
                for bad_stderr in (
                    "0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads\n",
                    "Used 10 registers, used 0 barriers, 372 bytes cmem[0]\n",
                ):
                    with mock.patch.object(subprocess, "run", return_value=subprocess.CompletedProcess(["ptxas"], 0, "", bad_stderr)):
                        with self.assertRaises(s101.S101Error) as e_pp:
                            ver.verify_ptx_kernels_live()
                        self.assertEqual(e_pp.exception.code, "PTXAS_PARSE_FAILED")
                ok_ptx = subprocess.CompletedProcess(
                    ["ptxas"], 0, "", "0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads\nUsed 10 registers, 372 bytes cmem[0]\n"
                )
                bad_dis = subprocess.CompletedProcess(["nvdisasm"], 1, "", "dis err")
                with mock.patch.object(subprocess, "run", side_effect=[ok_ptx, bad_dis]):
                    with self.assertRaises(s101.S101Error) as e_nd:
                        ver.verify_ptx_kernels_live()
                    self.assertEqual(e_nd.exception.code, "NVDISASM_FAILED")

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

            # Synthetic --verify-upstream, --verify-bend, --verify-loom checks (isolated CI-safe!)
            fake_root = tdir / "exp_root"
            fake_root.mkdir()
            fb = b'{"ok":true}\n'
            fsha = hashlib.sha256(fb).hexdigest()
            (fake_root / "t1").mkdir()
            (fake_root / "t1" / "c1.json").write_bytes(fb)
            with mock.patch.object(ver, "UPSTREAM_RECEIPT_MANIFEST", (("S52", "t1/c1.json", fsha),)):
                up_buf = io.BytesIO()
                with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": up_buf})()):
                    self.assertEqual(ver.main(["--verify-upstream", str(fake_root), "--json"]), 0)
                self.assertEqual(json.loads(up_buf.getvalue().decode("utf-8"))["receipts_verified"], 1)
                self.assertEqual(ver.main(["--verify-upstream", str(fake_root)]), 0)
                (fake_root / "t1" / "c1.json").write_bytes(b"bad\n")
                with self.assertRaises(s101.S101Error) as e_up:
                    ver.verify_upstream_manifest(fake_root)
                self.assertEqual(e_up.exception.code, "UPSTREAM_SHA_MISMATCH")

            fake_bend = tdir / "bend_dir"
            fake_bend.mkdir()
            (fake_bend / "README.md").write_bytes(fb)
            with mock.patch.object(ver, "BEND2_FILE_MANIFEST", (("README.md", fsha),)):
                b_buf = io.BytesIO()
                with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": b_buf})()):
                    self.assertEqual(ver.main(["--verify-bend", str(fake_bend), "--json"]), 0)
                self.assertEqual(json.loads(b_buf.getvalue().decode("utf-8"))["files_verified"], 1)
                self.assertEqual(ver.main(["--verify-bend", str(fake_bend)]), 0)
                (fake_bend / "README.md").write_bytes(b"bad\n")
                with self.assertRaises(s101.S101Error) as e_bd:
                    ver.verify_bend_clone(fake_bend)
                self.assertEqual(e_bd.exception.code, "BEND_SHA_MISMATCH")

            with mock.patch.object(ver, "LOOM_DOC_MANIFEST", (("main:doc.md", fsha),)):
                with mock.patch.object(ver.shutil, "which", return_value="/usr/bin/git"):
                    ok_git = subprocess.CompletedProcess(["git"], 0, stdout=fb, stderr=b"")
                    with mock.patch.object(subprocess, "run", return_value=ok_git):
                        l_buf = io.BytesIO()
                        with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": l_buf})()):
                            self.assertEqual(ver.main(["--verify-loom", str(tdir), "--json"]), 0)
                        self.assertEqual(json.loads(l_buf.getvalue().decode("utf-8"))["docs_verified"], 1)
                        self.assertEqual(ver.main(["--verify-loom", str(tdir)]), 0)
                    bad_git_rc = subprocess.CompletedProcess(["git"], 128, stdout=b"", stderr=b"fatal")
                    with mock.patch.object(subprocess, "run", return_value=bad_git_rc):
                        with self.assertRaises(s101.S101Error) as e_lg:
                            ver.verify_loom_clone(tdir)
                        self.assertEqual(e_lg.exception.code, "LOOM_GIT_SHOW_FAILED")
                    bad_git_sha = subprocess.CompletedProcess(["git"], 0, stdout=b"drift", stderr=b"")
                    with mock.patch.object(subprocess, "run", return_value=bad_git_sha):
                        with self.assertRaises(s101.S101Error) as e_ls:
                            ver.verify_loom_clone(tdir)
                        self.assertEqual(e_ls.exception.code, "LOOM_SHA_MISMATCH")
                with mock.patch.object(ver.shutil, "which", return_value=None):
                    with self.assertRaises(s101.S101Error) as e_ng:
                        ver.verify_loom_clone(tdir)
                    self.assertEqual(e_ng.exception.code, "GIT_NOT_FOUND")

            # Hardened dir_fd / symlink / FIFO / hardlink / RO-dir / UTF-8 / CRLF / non-canonical checks
            with self.assertRaises(s101.S101Error) as p0:
                ver.read_regular_file_bytes("not_a_path")  # type: ignore[arg-type]
            self.assertEqual(p0.exception.code, "INVALID_PATH_TYPE")
            with self.assertRaises(s101.S101Error) as p1:
                ver.read_regular_file_bytes(Path(str(tdir) + "/\ud800"))
            self.assertEqual(p1.exception.code, "INVALID_UNICODE_STR")
            with self.assertRaises(s101.S101Error) as p2:
                ver.read_regular_file_bytes(Path(str(tdir) + "/a\x00b"))
            self.assertEqual(p2.exception.code, "INVALID_PATH_NUL")
            with self.assertRaises(s101.S101Error) as p3:
                ver.read_regular_file_bytes(Path("/"))
            self.assertEqual(p3.exception.code, "INVALID_PATH")
            with self.assertRaises(s101.S101Error) as p4:
                ver.read_regular_file_bytes(tdir / "..")
            self.assertEqual(p4.exception.code, "INVALID_PATH")
            with self.assertRaises(s101.S101Error) as p5:
                ver.check_certificate_file(tdir / "no_dir" / "x.json")
            self.assertEqual(p5.exception.code, "PARENT_DIR_ERROR")
            with self.assertRaises(s101.S101Error) as p6:
                ver.check_certificate_file(tdir / "missing.json")
            self.assertEqual(p6.exception.code, "FILE_READ_ERROR")
            with self.assertRaises(s101.S101Error) as p7:
                ver.check_certificate_file(tdir)
            self.assertEqual(p7.exception.code, "NOT_REGULAR_FILE")

            sym_f = tdir / "sym.json"
            sym_f.symlink_to(out_p)
            with self.assertRaises(s101.S101Error) as p8:
                ver.check_certificate_file(sym_f)
            self.assertEqual(p8.exception.code, "SYMLINK_FORBIDDEN")
            with self.assertRaises(s101.S101Error) as p8w:
                ver.write_atomic_0600_bytes(sym_f, b"{}\n")
            self.assertEqual(p8w.exception.code, "SYMLINK_FORBIDDEN")

            sub_d = tdir / "real_sub"
            sub_d.mkdir()
            (sub_d / "c.json").write_bytes(disk_cert.read_bytes())
            sym_d = tdir / "sym_sub"
            sym_d.symlink_to(sub_d)
            with self.assertRaises(s101.S101Error) as p9:
                ver.check_certificate_file(sym_d / "c.json")
            self.assertEqual(p9.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")

            with mock.patch.object(ver.os, "environ", {}):
                ver._check_pwd_no_symlinks()
            with mock.patch.object(ver.os, "environ", {"PWD": "x" + str(sym_d)}):
                ver._check_pwd_no_symlinks()
            with mock.patch.object(ver.os, "environ", {"PWD": str(sym_d)}):
                with self.assertRaises(s101.S101Error) as p9p:
                    ver._check_pwd_no_symlinks()
                self.assertEqual(p9p.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")
            with mock.patch.object(ver.os, "environ", {"PWD": "/tmp/\ud800"}):
                with self.assertRaises(s101.S101Error) as p9s:
                    ver.read_regular_file_bytes(Path("c.json"))
                self.assertEqual(p9s.exception.code, "INVALID_UNICODE_STR")
            with mock.patch.dict(os.environ, {"PWD": "/nonexistent_s101_pwd_xyz"}):
                with self.assertRaises(s101.S101Error):
                    ver.read_regular_file_bytes(Path("definitely_missing_s101_rel.json"))

            fifo_p = tdir / "pipe.fifo"
            os.mkfifo(fifo_p)
            with self.assertRaises(s101.S101Error) as pf:
                ver.check_certificate_file(fifo_p)
            self.assertEqual(pf.exception.code, "NOT_REGULAR_FILE")
            with self.assertRaises(s101.S101Error) as pfw:
                ver.write_atomic_0600_bytes(fifo_p, b"{}\n")
            self.assertEqual(pfw.exception.code, "NOT_REGULAR_FILE")

            hl_p = tdir / "hardlink.json"
            os.link(out_p, hl_p)
            with self.assertRaises(s101.S101Error) as ph1:
                ver.check_certificate_file(hl_p)
            self.assertEqual(ph1.exception.code, "HARDLINK_FORBIDDEN")
            with self.assertRaises(s101.S101Error) as ph2:
                ver.write_atomic_0600_bytes(hl_p, b"{}\n")
            self.assertEqual(ph2.exception.code, "HARDLINK_FORBIDDEN")
            hl_p.unlink()

            ro_dir = tdir / "ro_dir"
            ro_dir.mkdir()
            ro_dir.chmod(0o500)
            try:
                with self.assertRaises(s101.S101Error) as pro:
                    ver.write_atomic_0600_bytes(ro_dir / "x.json", b"{}\n")
                self.assertEqual(pro.exception.code, "FILE_WRITE_ERROR")
            finally:
                ro_dir.chmod(0o700)

            crlf_p = tdir / "crlf.json"
            crlf_p.write_bytes(disk_cert.read_bytes().replace(b"\n", b"\r\n"))
            with self.assertRaises(s101.S101Error) as pcrlf:
                ver.check_certificate_file(crlf_p)
            self.assertEqual(pcrlf.exception.code, "CRLF_FORBIDDEN")

            badu_p = tdir / "badutf8.json"
            badu_p.write_bytes(b"\xff\xfe")
            with self.assertRaises(s101.S101Error) as pbu:
                ver.check_certificate_file(badu_p)
            self.assertEqual(pbu.exception.code, "INVALID_UTF8")

            pretty_p = tdir / "pretty.json"
            pretty_p.write_text(json.dumps(checked, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(s101.S101Error) as ppr:
                ver.check_certificate_file(pretty_p)
            self.assertEqual(ppr.exception.code, "NONCANONICAL_BYTES")

            dfd_chk = os.open(tdir, os.O_RDONLY | os.O_DIRECTORY)
            try:
                self.assertIs(ver._is_symlink_at(dfd_chk, "no_such_entry"), False)
                self.assertIs(ver._is_symlink_at(dfd_chk, "sym.json"), True)
            finally:
                os.close(dfd_chk)

            big_p = tdir / "big.json"
            big_p.write_bytes(b"a" * 32)
            self.assertEqual(ver.read_regular_file_bytes(big_p, max_bytes=32), b"a" * 32)
            big_p.write_bytes(b"a" * 64)
            with mock.patch.object(os, "read", return_value=b""):
                with self.assertRaises(s101.S101Error) as pbig:
                    ver.read_regular_file_bytes(big_p, max_bytes=32)
                self.assertEqual(pbig.exception.code, "FILE_TOO_LARGE")

            empty_p = tdir / "empty.json"
            empty_p.write_bytes(b"")
            with mock.patch.object(os, "read", side_effect=[b"x" * 20, b"y" * 20, b""]):
                with self.assertRaises(s101.S101Error) as pstr:
                    ver.read_regular_file_bytes(empty_p, max_bytes=32)
                self.assertEqual(pstr.exception.code, "FILE_TOO_LARGE")
            with mock.patch.object(os, "read", side_effect=OSError(5, "EIO")):
                with self.assertRaises(s101.S101Error) as peio:
                    ver.read_regular_file_bytes(out_p)
                self.assertEqual(peio.exception.code, "FILE_READ_ERROR")
            with mock.patch.object(os, "write", side_effect=OSError(5, "EIO")):
                with self.assertRaises(s101.S101Error) as pwe:
                    ver.write_atomic_0600_bytes(tdir / "eio.json", b"hello")
                self.assertEqual(pwe.exception.code, "FILE_WRITE_ERROR")
            with mock.patch.object(os, "write", return_value=0):
                with self.assertRaises(s101.S101Error) as pw0:
                    ver.write_atomic_0600_bytes(tdir / "zwrite.json", b"hello")
                self.assertEqual(pw0.exception.code, "FILE_WRITE_ERROR")
            fake_st = type("St", (), {"st_nlink": 2})()
            with mock.patch.object(os, "fstat", return_value=fake_st):
                with self.assertRaises(s101.S101Error) as ptn:
                    ver.write_atomic_0600_bytes(tdir / "hl_tmp.json", b"hello")
                self.assertEqual(ptn.exception.code, "HARDLINK_FORBIDDEN")
            with mock.patch.object(os, "replace", side_effect=OSError(13, "EACCES")):
                with self.assertRaises(s101.S101Error) as prep:
                    ver.write_atomic_0600_bytes(tdir / "rep_err.json", b"hello")
                self.assertEqual(prep.exception.code, "FILE_WRITE_ERROR")

            err_buf = io.StringIO()
            with mock.patch.object(sys, "stderr", err_buf):
                rc_err = ver.main(["--check", str(crlf_p)])
            self.assertEqual(rc_err, 2)
            self.assertIn("CRLF_FORBIDDEN", err_buf.getvalue())


class TestS101LeanR10AndLiveOrCiVerification(unittest.TestCase):
    def test_r10_static_all_classes_and_clean_cases(self) -> None:
        with self.assertRaises(s101.S101Error):
            ver.audit_lean4_source_r10(123)  # type: ignore[arg-type]

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

        clean_src = "\n".join(
            [
                "-- sorry admit axiom native_decide opaque export dbg_trace",
                "/- outer /x a/ sorry -x /- nested -/ still comment -/",
                'def s1 := "sorry \\" native_decide opaque export dbg_trace"',
                'def s2 := r#"a " sorry " b"#',
                'def s3 := s! "hello {1 + 1} sorry"',
                'def s4 := !r#"sorry"#',
                'def s6 := s!x ++ "sorry"',
                'def s7 := obj.dbg_trace ++ obj.opaque ++ obj.export',
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
                "export Nat (succ)",
                "import Init.Data.Nat.Basic",
                "#print axioms t1",
                "theorem t_eof : 1 = 1 := by decide",
            ]
        )
        self.assertEqual(ver.audit_lean4_source_r10(clean_src), [])
        self.assertEqual(ver.audit_lean4_source_r10("-- eof no newline"), [])
        self.assertEqual(ver.audit_lean4_source_r10("r#"), [])
        self.assertEqual(ver.audit_lean4_source_r10("rx"), [])
        self.assertEqual(ver.audit_lean4_source_r10('r"sorry"a'), [])
        self.assertEqual(ver.audit_lean4_source_r10('!"a {sorry}"s'), [])
        self.assertEqual(ver.audit_lean4_source_r10('"ok"a!'), [])
        self.assertEqual(ver.audit_lean4_source_r10(' !"sorry"'), [])
        self.assertEqual(ver.audit_lean4_source_r10("'a'"), [])
        self.assertEqual(ver.audit_lean4_source_r10('def f := a\'"\' sorry "'), [])
        self.assertEqual(ver.audit_lean4_source_r10('def f := _\'"\' sorry "'), [])
        self.assertEqual(ver.audit_lean4_source_r10('def f := foo.s! "a {sorry}"'), [])
        self.assertEqual(ver.audit_lean4_source_r10("s!"), [])
        self.assertEqual(ver.audit_lean4_source_r10('panic!"sorry"'), ["LEAN4_PANIC_ESCAPE"])
        self.assertEqual(ver.audit_lean4_source_r10('!panic!"sorry"'), ["LEAN4_PANIC_ESCAPE"])
        self.assertEqual(ver.audit_lean4_source_r10("def y := a!\"\""), ["LEAN4_UNKNOWN_BANG_STRING"])
        self.assertEqual(ver.audit_lean4_source_r10("'\x22'\nsorry\ndef q : Char := '\x22'"), ["LEAN4_SORRY"])
        self.assertEqual(ver.audit_lean4_source_r10('def x := foo.r#"ok"; sorry; def z := "#"'), ["LEAN4_SORRY"])
        self.assertEqual(
            ver.audit_lean4_source_r10('def _a : String := s!"x"\naxiom evil : False\ndef _b : Char := \'"\''),
            ["LEAN4_AXIOM"],
        )

        cases: list[tuple[str, str]] = [
            ("theorem t : True := by sorry", "LEAN4_SORRY"),
            ("-- comment\ntheorem t : True := by sorry", "LEAN4_SORRY"),
            ("def x := 1 - 2\ndef y := a - sorry", "LEAN4_SORRY"),
            ("def x := 1-2; sorry", "LEAN4_SORRY"),
            ("theorem t : True := by «sorry»", "LEAN4_SORRY"),
            ("theorem t : True := by admit", "LEAN4_ADMIT"),
            ("axiom bogus : False", "LEAN4_AXIOM"),
            ("unsafe def f : Nat := 0", "LEAN4_UNSAFE"),
            ("opaque hidden : Nat := 0", "LEAN4_OPAQUE"),
            ("@[export my_sym] def f : Nat := 0", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("attribute [export my_sym] f", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("@[init] def f : IO Unit := pure ()", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("@[builtin_init] def f : IO Unit := pure ()", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("attribute [init] f", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("attribute [builtin_init] f", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("@[term_elab foo] def f : Nat := 0", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("@[command_elab foo] def f : Nat := 0", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("@[tactic foo] def f : Nat := 0", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("@[macro foo] def f : Nat := 0", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("@[macro_rules] def f : Nat := 0", "LEAN4_ATTR_TRUST_ESCAPE"),
            ('def f (n : Nat) : Nat := dbg_trace "hi"; n', "LEAN4_DBG_TRACE"),
            ("def f (n : Nat) : Nat := dbg_sleep 1; n", "LEAN4_DBG_TRACE"),
            ("def f (n : Nat) : Nat := dbg_stack_trace; n", "LEAN4_DBG_TRACE"),
            ('def f (n : Nat) : Nat := dbgTrace "hi" fun _ => n', "LEAN4_DBG_TRACE"),
            ('def f (n : Nat) : Nat := _root_.dbgTrace "hi" fun _ => n', "LEAN4_DBG_TRACE"),
            ("def f (n : Nat) : Nat := dbgTraceVal n", "LEAN4_DBG_TRACE"),
            ('def f (n : Nat) : Nat := dbgTraceIfShared "hi" n', "LEAN4_DBG_TRACE"),
            ("def f (n : Nat) : Nat := dbgSleep 1 fun _ => n", "LEAN4_DBG_TRACE"),
            ('def f (n : Nat) : Nat := dbgStackTrace "hi" fun _ => n', "LEAN4_DBG_TRACE"),
            ("def f : Nat := panic! (String.ofList [])", "LEAN4_PANIC_ESCAPE"),
            ("def f : Nat := panicWithPosWithDecl \"a\" \"b\" 1 1 \"c\"", "LEAN4_PANIC_ESCAPE"),
            ("def f : Nat := unreachable!", "LEAN4_PANIC_ESCAPE"),
            ("theorem t : 1 = 1 := by native_decide", "LEAN4_NATIVE_DECIDE"),
            ("theorem t : 1 = 1 := by bv_decide", "LEAN4_BV_DECIDE"),
            ("def x := sorryAx", "LEAN4_SORRY_AX"),
            ("def x := Lean.Meta.mkSorry", "LEAN4_MK_SORRY"),
            ("def x := Lean.ofReduceBool", "LEAN4_OF_REDUCE_BOOL"),
            ("def x := Lean.ofReduceNat", "LEAN4_OF_REDUCE_NAT"),
            ("def x := Lean.trustCompiler", "LEAN4_TRUST_COMPILER"),
            ("public\n  import Mathlib.Tactic", "LEAN4_NON_INIT_IMPORT"),
            ("import Std.Data.HashMap", "LEAN4_NON_INIT_IMPORT"),
            ("partial\n def loop (n : Nat) : Nat := loop n", "LEAN4_PARTIAL"),
            ("theorem t : 1 = 1 := by decide +native", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide +revert +native", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide -kernel +native", "LEAN4_DECIDE_NATIVE"),
            (") theorem t : 1 = 1 := by decide (native := true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := false\n|| true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := false == false)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := false != true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := false.not)", "LEAN4_DECIDE_NATIVE"),
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
            ("set_option warn.sorry false", "LEAN4_SKIP_KERNEL_TC"),
            ("#eval 1 + 1", "LEAN4_EVAL_SPOOF"),
            ("#eval! 1 + 1", "LEAN4_EVAL_SPOOF"),
            ("#reduce 1 + 1", "LEAN4_EVAL_SPOOF"),
            ("#exit", "LEAN4_EVAL_SPOOF"),
            ("#guard_msgs in #check 1", "LEAN4_EVAL_SPOOF"),
            ("#guard 1 == 1", "LEAN4_EVAL_SPOOF"),
            ("#print Nat.add", "LEAN4_EVAL_SPOOF"),
            ("#print axioms theorem", "LEAN4_EVAL_SPOOF"),
            ("run_cmd pure ()", "LEAN4_EVAL_SPOOF"),
            ("run_meta pure ()", "LEAN4_EVAL_SPOOF"),
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
            got = ver.audit_lean4_source_r10(snippet)
            self.assertIn(expected_code, got, f"expected {expected_code} for {snippet!r}, got {got}")

    def test_lean_verification_dual_mode_zero_skips(self) -> None:
        lean_file = _SCRIPT_DIR / s101.LEAN_FILE_NAME
        self.assertEqual(ver.audit_lean4_source_r10(lean_file.read_text(encoding="utf-8")), [])
        self.assertEqual(hashlib.sha256(lean_file.read_bytes()).hexdigest(), s101.LEAN_FILE_SHA256)

        has_lean = True
        try:
            ver._find_lean_binary()
        except s101.S101Error:
            has_lean = False

        if os.environ.get("ALETHEIA_REQUIRE_LEAN") == "1":
            self.assertTrue(has_lean, "ALETHEIA_REQUIRE_LEAN=1 requires live lean binary")

        if has_lean:
            out_buf = io.BytesIO()
            with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": out_buf})()):
                rc = ver.main(["--verify-lean", str(lean_file), "--json"])
            self.assertEqual(rc, 0)
            res = json.loads(out_buf.getvalue().decode("utf-8"))
            self.assertEqual(res["theorems_verified"], 18)
            self.assertEqual(res["r10_findings"], 0)
            self.assertEqual(res["allowed_axioms"], ["propext"])
            self.assertEqual(res["sha256"], s101.LEAN_FILE_SHA256)
            self.assertEqual(ver.main(["--verify-lean", str(lean_file)]), 0)
        else:
            err_buf = io.StringIO()
            with mock.patch.object(sys, "stderr", err_buf):
                rc_nl = ver.main(["--verify-lean", str(lean_file)])
            self.assertEqual(rc_nl, 2)
            self.assertIn("LEAN_BINARY_NOT_FOUND", err_buf.getvalue())

        with tempfile.TemporaryDirectory(prefix="s101_lean_") as td:
            tdir = Path(td).resolve()
            for bad_flag in (0, 1, "false", None):
                with self.assertRaises(s101.S101Error) as e_flag:
                    ver.verify_lean_file(lean_file, check_pinned_sha=bad_flag)  # type: ignore[arg-type]
                self.assertEqual(e_flag.exception.code, "INVALID_CHECK_PINNED_SHA")

            crlf_l = tdir / "c.lean"
            crlf_l.write_bytes(b"theorem t : True := trivial\r\n")
            with self.assertRaises(s101.S101Error) as e1:
                ver.verify_lean_file(crlf_l, check_pinned_sha=False)
            self.assertEqual(e1.exception.code, "CRLF_FORBIDDEN")

            badu_l = tdir / "u.lean"
            badu_l.write_bytes(b"\xff\xfe")
            with self.assertRaises(s101.S101Error) as e2:
                ver.verify_lean_file(badu_l, check_pinned_sha=False)
            self.assertEqual(e2.exception.code, "INVALID_UTF8")

            other_l = tdir / "o.lean"
            other_l.write_text("theorem ok1 : 1 = 1 := rfl\n#print axioms ok1\n", encoding="utf-8")
            with self.assertRaises(s101.S101Error) as e3:
                ver.verify_lean_file(other_l, check_pinned_sha=True)
            self.assertEqual(e3.exception.code, "LEAN_SHA_MISMATCH")

            r10_l = tdir / "r10_bad.lean"
            r10_l.write_text("#eval 1 + 1\n", encoding="utf-8")
            with self.assertRaises(s101.S101Error) as e_r10:
                ver.verify_lean_file(r10_l, check_pinned_sha=False)
            self.assertEqual(e_r10.exception.code, "LEAN_R10_STATIC_FINDING")

            with mock.patch.object(ver, "_find_lean_binary", return_value="/usr/bin/lean"):
                wrap_ok = subprocess.CompletedProcess(
                    ["lean"],
                    0,
                    stdout="'ok1' depends on axioms: [\n  propext\n]\n'ok2' does not depend on any axioms\n",
                    stderr="",
                )
                with mock.patch.dict(os.environ, {"LEAN_PATH": "/evil/olean", "LD_PRELOAD": "/evil.so"}):
                    with mock.patch.object(subprocess, "run", return_value=wrap_ok) as m_run:
                        self.assertEqual(ver.verify_lean_file(other_l, check_pinned_sha=False)["theorems_verified"], 2)
                        self.assertEqual(m_run.call_args[0][0], ["/usr/bin/lean", "--stdin"])
                        self.assertEqual(m_run.call_args[1]["input"], other_l.read_text(encoding="utf-8"))
                        self.assertNotIn("LEAN_PATH", m_run.call_args[1]["env"])
                        self.assertNotIn("LD_PRELOAD", m_run.call_args[1]["env"])

                wrap_bad = subprocess.CompletedProcess(
                    ["lean"], 0, stdout="'ok1' depends on axioms: [\n  propext,\n  Classical.choice\n]\n", stderr=""
                )
                with mock.patch.object(subprocess, "run", return_value=wrap_bad):
                    with self.assertRaises(s101.S101Error) as e_wb:
                        ver.verify_lean_file(other_l, check_pinned_sha=False)
                    self.assertEqual(e_wb.exception.code, "LEAN_FORBIDDEN_AXIOM")

                dup_out = subprocess.CompletedProcess(
                    ["lean"], 0, stdout="'ok1' does not depend on any axioms\n'ok1' does not depend on any axioms\n", stderr=""
                )
                with mock.patch.object(subprocess, "run", return_value=dup_out):
                    with self.assertRaises(s101.S101Error) as e_dup:
                        ver.verify_lean_file(other_l, check_pinned_sha=False)
                    self.assertEqual(e_dup.exception.code, "LEAN_DUPLICATE_THEOREM")

                fail_rc = subprocess.CompletedProcess(["lean"], 1, stdout="", stderr="type mismatch")
                with mock.patch.object(subprocess, "run", return_value=fail_rc):
                    with self.assertRaises(s101.S101Error) as e_rc:
                        ver.verify_lean_file(other_l, check_pinned_sha=False)
                    self.assertEqual(e_rc.exception.code, "LEAN_COMPILE_FAILED")

                fake_proc_err = subprocess.CompletedProcess(["lean"], 0, stdout="", stderr="warn")
                with mock.patch.object(subprocess, "run", return_value=fake_proc_err):
                    with self.assertRaises(s101.S101Error) as e6:
                        ver.verify_lean_file(other_l, check_pinned_sha=False)
                    self.assertEqual(e6.exception.code, "LEAN_STDERR_NONEMPTY")

                fake_proc_out = subprocess.CompletedProcess(["lean"], 0, stdout="weird line\n", stderr="")
                with mock.patch.object(subprocess, "run", return_value=fake_proc_out):
                    with self.assertRaises(s101.S101Error) as e7:
                        ver.verify_lean_file(other_l, check_pinned_sha=False)
                    self.assertEqual(e7.exception.code, "LEAN_UNEXPECTED_OUTPUT")

                fake_proc_thm = subprocess.CompletedProcess(
                    ["lean"], 0, stdout="'Wrong.thm' does not depend on any axioms\n", stderr=""
                )
                with mock.patch.object(subprocess, "run", return_value=fake_proc_thm):
                    with self.assertRaises(s101.S101Error) as e8:
                        ver.verify_lean_file(lean_file, check_pinned_sha=True)
                    self.assertEqual(e8.exception.code, "LEAN_THEOREM_SET_MISMATCH")

                empty_out = subprocess.CompletedProcess(["lean"], 0, stdout="", stderr="")
                with mock.patch.object(subprocess, "run", return_value=empty_out):
                    with self.assertRaises(s101.S101Error) as e_zero:
                        ver.verify_lean_file(other_l, check_pinned_sha=False)
                    self.assertEqual(e_zero.exception.code, "LEAN_NO_THEOREMS_VERIFIED")

            if has_lean:
                self.assertEqual(ver.verify_lean_file(other_l, check_pinned_sha=False)["theorems_verified"], 1)
                cl_l = tdir / "classical.lean"
                cl_l.write_text("theorem use_em (p : Prop) : p ∨ ¬ p := Classical.em p\n#print axioms use_em\n", encoding="utf-8")
                with self.assertRaises(s101.S101Error) as e4:
                    ver.verify_lean_file(cl_l, check_pinned_sha=False)
                self.assertEqual(e4.exception.code, "LEAN_FORBIDDEN_AXIOM")
                bad_l = tdir / "bad.lean"
                bad_l.write_text("theorem bad : 1 = 2 := rfl\n", encoding="utf-8")
                with self.assertRaises(s101.S101Error) as e5:
                    ver.verify_lean_file(bad_l, check_pinned_sha=False)
                self.assertEqual(e5.exception.code, "LEAN_COMPILE_FAILED")

            dummy_lean = tdir / "fake_lean"
            dummy_lean.write_text("#!/bin/sh\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"LEAN_BIN": str(dummy_lean)}):
                self.assertEqual(ver._find_lean_binary(), str(dummy_lean))
            with mock.patch.dict(os.environ, {"LEAN_BIN": str(tdir / "no_such_lean")}):
                with self.assertRaises(s101.S101Error) as e_eb:
                    ver._find_lean_binary()
                self.assertEqual(e_eb.exception.code, "LEAN_BINARY_NOT_FOUND")
            with mock.patch.dict(os.environ, {"LEAN_BIN": "", "HOME": str(tdir)}):
                with mock.patch.object(ver.shutil, "which", return_value="/mock/lean"):
                    self.assertEqual(ver._find_lean_binary(), "/mock/lean")
                with mock.patch.object(ver.shutil, "which", return_value=None):
                    with self.assertRaises(s101.S101Error) as e9:
                        ver._find_lean_binary()
                    self.assertEqual(e9.exception.code, "LEAN_BINARY_NOT_FOUND")
                    elan_bin = tdir / ".elan" / "bin"
                    elan_bin.mkdir(parents=True)
                    (elan_bin / "lean").write_text("#!/bin/sh\n", encoding="utf-8")
                    self.assertEqual(ver._find_lean_binary(), str(elan_bin / "lean"))
            with mock.patch.object(ver.os, "environ", {}):
                with mock.patch.object(ver.shutil, "which", return_value=None):
                    with self.assertRaises(s101.S101Error) as e10:
                        ver._find_lean_binary()
                    self.assertEqual(e10.exception.code, "LEAN_BINARY_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
