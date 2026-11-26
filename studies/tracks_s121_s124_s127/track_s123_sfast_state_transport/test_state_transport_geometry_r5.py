#!/usr/bin/env python3
"""Assertion-free R5 adversarial unittest suite for verify_state_transport_geometry.py."""

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

import verify_state_transport_geometry as mod


class TestStateTransportGeometryR5(unittest.TestCase):
    def test_01_t1_bandwidth_exact_identities_and_boundaries(self) -> None:
        t1 = mod.verify_t1_kv_vs_sfast_bandwidth()
        self.assertTrue(t1["passed"])
        self.assertEqual(t1["kv_bytes_per_token"], 24576)
        self.assertEqual(t1["kv_bytes_at_T_uncompressed"], 201326592)
        self.assertEqual(t1["sfast_pure_bytes"], 786432)
        self.assertEqual(t1["aux_su2_vring_bytes"], 147456)
        self.assertEqual(t1["exact_ratio_uncompressed"], "4096/19")
        by_r = t1["by_kvzip_ratio"]
        self.assertEqual(by_r["rho_1x"]["t_star_pure_tokens"], "32/1")
        self.assertEqual(by_r["rho_1x"]["t_star_full_tokens"], "38/1")
        self.assertEqual(by_r["rho_16x"]["t_star_full_tokens"], "608/1")
        self.assertEqual(by_r["rho_64x"]["t_star_full_tokens"], "2432/1")
        self.assertEqual(by_r["rho_128x"]["t_star_pure_tokens"], "4096/1")
        self.assertEqual(by_r["rho_128x"]["t_star_full_tokens"], "4864/1")
        self.assertEqual(by_r["rho_128x"]["pure_sfast_ratio_at_T"], "2/1")
        self.assertEqual(by_r["rho_128x"]["full_holosphere_ratio_at_T"], "32/19")
        self.assertEqual(by_r["rho_128x"]["full_holosphere_ratio_10_questions"], "320/19")
        self.assertTrue(by_r["rho_128x"]["o1_beats_kv_at_T"])

        # Exact boundary hs_full_b == sfast_pure_bytes (aux == 0) and T=4 < T*=8 -> o1_beats_kv_at_T is False and passed is False!
        t1_edge = mod.verify_t1_kv_vs_sfast_bandwidth(
            batch=1, n_layers=2, n_heads=4, d_head=8, t_eval=4, holosphere_full_state_bytes=2048
        )
        self.assertFalse(t1_edge["by_kvzip_ratio"]["rho_1x"]["o1_beats_kv_at_T"])
        self.assertFalse(t1_edge["passed"])
        self.assertEqual(t1_edge["aux_su2_vring_bytes"], 0)

        # Exact crossover T == T* (ratio_full == 1 -> o1_beats_kv_at_T is False -> passed MUST be False!)
        t1_eq1 = mod.verify_t1_kv_vs_sfast_bandwidth(
            batch=1, n_layers=2, n_heads=4, d_head=8, t_eval=8, holosphere_full_state_bytes=2048
        )
        self.assertEqual(t1_eq1["exact_ratio_uncompressed"], "1/1")
        self.assertFalse(t1_eq1["by_kvzip_ratio"]["rho_1x"]["o1_beats_kv_at_T"])
        self.assertFalse(t1_eq1["passed"])

        # Exact positive-int boundaries (1 and MAX_INT_ABS accepted; 0, MAX+1, bool, float rejected)
        self.assertEqual(mod.check_pos_int(1, "min"), 1)
        self.assertEqual(mod.check_pos_int(mod.MAX_INT_ABS, "max"), mod.MAX_INT_ABS)
        with self.assertRaises(mod.StateTransportError):
            mod.verify_t1_kv_vs_sfast_bandwidth(holosphere_full_state_bytes=786431)
        for bad in (True, False, 0, -5, 1.5, mod.MAX_INT_ABS + 1, "2"):
            with self.assertRaises(mod.StateTransportError):
                mod.check_pos_int(bad, "x")

    def test_02_t2_woodbury_su2_and_w14_obs1_boundaries(self) -> None:
        t2 = mod.verify_t2_woodbury_and_su2_obstruction()
        self.assertTrue(t2["passed"])
        self.assertEqual(t2["right_woodbury_equivariance_err_sq"], "0/1")
        self.assertEqual(t2["prefix_handoff_suffix_err_sq"], "0/1")
        self.assertEqual(t2["readout_equivariance_err_sq"], "0/1")
        self.assertEqual(t2["left_woodbury_shared_gauge_err_sq"], "0/1")
        self.assertNotEqual(t2["left_woodbury_distinct_gauge_obstruction_err_sq"], "0/1")
        self.assertEqual(t2["su2_proper_det"], "1/1")
        self.assertEqual(t2["su2_proper_homomorphism_err_sq"], "0/1")
        self.assertTrue(t2["su2_proper_conjugation_exact"])
        self.assertTrue(t2["su2_cayley_group_law_exact"])
        self.assertEqual(t2["su2_improper_det"], "-1/1")
        self.assertTrue(t2["su2_improper_order_reversal_exact"])
        self.assertNotEqual(t2["su2_improper_forward_err_sq"], "0/1")
        self.assertTrue(t2["su2_kabsch_repaired_homomorphism_exact"])
        self.assertEqual(t2["w14_obs1_abelian_so2_commutator_err_sq"], "0/1")
        self.assertNotEqual(t2["w14_obs1_nonabelian_su2_commutator_err_sq"], "0/1")

        # Parameterized Woodbury verifier negative controls (non-orthogonal Q_k, non-orthogonal Q_v, handoff_idx bounds)
        eye2 = mod.mat_eye(2)
        non_orth2 = ((Fraction(2), Fraction(0)), (Fraction(0), Fraction(1)))
        tok2 = (
            ((Fraction(1), Fraction(0)), (Fraction(0), Fraction(1)), Fraction(1, 2)),
            ((Fraction(0), Fraction(1)), (Fraction(1), Fraction(0)), Fraction(1, 2)),
            ((Fraction(1), Fraction(1)), (Fraction(1), Fraction(-1)), Fraction(1, 3)),
        )
        # Boundary handoff_idx == 0 and handoff_idx == 2 succeed
        wb0 = mod.check_woodbury_gauge_transport_q(eye2, eye2, tok2, (Fraction(1), Fraction(0)), 0)
        self.assertEqual(wb0["prefix_handoff_suffix_err_sq"], "0/1")
        wb2 = mod.check_woodbury_gauge_transport_q(eye2, eye2, tok2, (Fraction(1), Fraction(0)), 2)
        self.assertEqual(wb2["prefix_handoff_suffix_err_sq"], "0/1")
        with self.assertRaises(mod.StateTransportError):
            mod.check_woodbury_gauge_transport_q(non_orth2, eye2, tok2, (Fraction(1), Fraction(0)), 0)
        with self.assertRaises(mod.StateTransportError):
            mod.check_woodbury_gauge_transport_q(eye2, non_orth2, tok2, (Fraction(1), Fraction(0)), 0)
        with self.assertRaises(mod.StateTransportError):
            mod.check_woodbury_gauge_transport_q(eye2, eye2, tok2, (Fraction(1), Fraction(0)), -1)
        with self.assertRaises(mod.StateTransportError):
            mod.check_woodbury_gauge_transport_q(eye2, eye2, tok2, (Fraction(1), Fraction(0)), 3)

        # Parameterized SU(2) + SO(2) negative controls
        u_q = mod.cayley_quat_q((Fraction(1, 2), Fraction(0), Fraction(0)))
        w1 = (Fraction(1, 3), Fraction(0), Fraction(0))
        w2 = (Fraction(0), Fraction(1, 3), Fraction(0))
        # Passing proper I_3 (det=+1) as h_refl -> BAD_REFL!
        with self.assertRaises(mod.StateTransportError):
            mod.check_su2_intertwiner_q(u_q, mod.mat_eye(3), w1, w2, (Fraction(3, 5), Fraction(4, 5)), (Fraction(5, 13), Fraction(12, 13)))
        # Passing non-orthogonal det=-1 matrix as h_refl -> BAD_REFL!
        bad_refl = ((Fraction(2), Fraction(0), Fraction(0)), (Fraction(0), Fraction(1, 2), Fraction(0)), (Fraction(0), Fraction(0), Fraction(-1)))
        with self.assertRaises(mod.StateTransportError):
            mod.check_su2_intertwiner_q(u_q, bad_refl, w1, w2, (Fraction(3, 5), Fraction(4, 5)), (Fraction(5, 13), Fraction(12, 13)))
        # Non-unit SO(2) -> NON_UNIT_SO2
        with self.assertRaises(mod.StateTransportError):
            mod.so2_rational_q(Fraction(1, 2), Fraction(1, 2))

        # Low-level linear algebra & check_frac boundaries (exact MAX_INT_ABS accepted, MAX+1 rejected!)
        self.assertEqual(mod.check_frac(mod.MAX_INT_ABS, "max_i"), Fraction(mod.MAX_INT_ABS, 1))
        self.assertEqual(mod.check_frac(-mod.MAX_INT_ABS, "min_i"), Fraction(-mod.MAX_INT_ABS, 1))
        self.assertEqual(mod.check_frac(Fraction(mod.MAX_INT_ABS, mod.MAX_INT_ABS), "max_f"), Fraction(1, 1))
        self.assertEqual(mod.check_frac(Fraction(1, mod.MAX_INT_ABS), "max_den"), Fraction(1, mod.MAX_INT_ABS))
        for bad_f in (1.25, mod.MAX_INT_ABS + 1, Fraction(mod.MAX_INT_ABS + 1, 1), Fraction(1, mod.MAX_INT_ABS + 1)):
            with self.assertRaises(mod.StateTransportError):
                mod.check_frac(bad_f, "bad")
        with self.assertRaises(mod.StateTransportError):
            mod.householder_q((Fraction(0), Fraction(0), Fraction(0)))
        with self.assertRaises(mod.StateTransportError):
            mod.det3_q(((Fraction(1), Fraction(0)), (Fraction(0), Fraction(1))))
        with self.assertRaises(mod.StateTransportError):
            mod.det3_q(((Fraction(1), Fraction(0)), (Fraction(0), Fraction(1)), (Fraction(0), Fraction(0))))
        with self.assertRaises(mod.StateTransportError):
            mod.cross3_q((Fraction(1), Fraction(0)), (Fraction(0), Fraction(1), Fraction(0)))
        with self.assertRaises(mod.StateTransportError):
            mod.cross3_q((Fraction(1), Fraction(0), Fraction(0)), (Fraction(0), Fraction(1)))
        with self.assertRaises(mod.StateTransportError):
            mod.cayley_quat_q((Fraction(1), Fraction(0)))
        with self.assertRaises(mod.StateTransportError):
            mod.quat_to_so3_q((Fraction(2), Fraction(0), Fraction(0), Fraction(0)))
        with self.assertRaises(mod.StateTransportError):
            mod.cayley_compose_vec_q((Fraction(1), Fraction(0), Fraction(0)), (Fraction(1), Fraction(0), Fraction(0)))
        with self.assertRaises(mod.StateTransportError):
            mod.mat_mul(((Fraction(1), Fraction(0)),), ((Fraction(1),),))
        with self.assertRaises(mod.StateTransportError):
            mod.mat_vec(((Fraction(1), Fraction(0)),), (Fraction(1),))
        with self.assertRaises(mod.StateTransportError):
            mod.vec_dot((Fraction(1),), (Fraction(1), Fraction(2)))

    def test_03_t3_low_rank_denoising_and_t4_ols_shrinkage(self) -> None:
        t3 = mod.verify_t3_query_aware_low_rank_denoising()
        self.assertTrue(t3["passed"])
        self.assertEqual(t3["ambient_dim"], 8)
        self.assertEqual(t3["noise_sigma_sq"], "1/4")
        self.assertEqual(t3["nullspace_penalty_ratio"], "2/1")
        sw = t3["rank_sweep"]
        self.assertEqual(sw["r2"]["err_full_sq"], "2/1")
        self.assertEqual(sw["r2"]["tail_energy_sq"], "1/4")
        self.assertEqual(sw["r2"]["noise_removed_sq"], "3/2")
        self.assertEqual(sw["r2"]["err_proj_sq"], "3/4")
        self.assertEqual(sw["r2"]["net_mse_gain"], "5/4")
        self.assertTrue(sw["r2"]["pythagorean_err_exact"])
        self.assertTrue(sw["r2"]["denoise_gain_exact"])
        self.assertTrue(sw["r2"]["query_signal_preserved"])
        self.assertTrue(sw["r2"]["beats_full"])
        self.assertEqual(sw["r4"]["tail_energy_sq"], "0/1")
        self.assertEqual(sw["r4"]["err_proj_sq"], "1/1")
        self.assertTrue(sw["r4"]["beats_full"])
        self.assertEqual(sw["r6"]["err_proj_sq"], "3/2")
        self.assertTrue(sw["r6"]["beats_full"])
        self.assertEqual(sw["r8"]["err_proj_sq"], "2/1")
        self.assertFalse(sw["r8"]["beats_full"])

        # Projector rank boundaries (1 and 8 valid; 0, 9, bool invalid)
        self.assertEqual(mod.mat_trace(mod.exact_hadamard_projector(1)), Fraction(1, 1))
        self.assertEqual(mod.mat_trace(mod.exact_hadamard_projector(8)), Fraction(8, 1))
        for bad_r in (0, 9, True, "4"):
            with self.assertRaises(mod.StateTransportError):
                mod.exact_hadamard_projector(bad_r)  # type: ignore[arg-type]

        # Negative controls for check_low_rank_pythagorean_q: non-idempotent, asymmetric, query outside col(P_r)
        eye2 = mod.mat_eye(2)
        non_idem = ((Fraction(2), Fraction(0)), (Fraction(0), Fraction(0)))
        non_sym = ((Fraction(1), Fraction(1)), (Fraction(0), Fraction(0)))
        p1 = ((Fraction(1), Fraction(0)), (Fraction(0), Fraction(0)))
        with self.assertRaises(mod.StateTransportError):
            mod.check_low_rank_pythagorean_q(eye2, eye2, non_idem, (Fraction(1), Fraction(0)))
        with self.assertRaises(mod.StateTransportError):
            mod.check_low_rank_pythagorean_q(eye2, eye2, non_sym, (Fraction(1), Fraction(0)))
        with self.assertRaises(mod.StateTransportError):
            mod.check_low_rank_pythagorean_q(eye2, eye2, p1, (Fraction(0), Fraction(1)))

        # Theorem 4 positive + exact equality boundary (s_OLS == s_Frob -> strict_shrinkage_holds == False!) + zero guards
        t4 = mod.verify_t4_ols_vs_frob_shrinkage()
        self.assertTrue(t4["passed"])
        self.assertEqual(t4["norm_a_sq"], "26/1")
        self.assertEqual(t4["norm_b_sq"], "114/1")
        self.assertEqual(t4["tr_sigma"], "52/1")
        self.assertEqual(t4["s_ols"], "2/1")
        self.assertEqual(t4["s_ols_sq"], "4/1")
        self.assertEqual(t4["s_frob_sq"], "57/13")
        self.assertEqual(t4["shrinkage_ratio_sq"], "52/57")
        self.assertTrue(t4["cauchy_schwarz_holds"])
        self.assertTrue(t4["strict_shrinkage_holds"])

        # Exact equality case Z_B = 2 * Z_A -> s_OLS^2 == s_Frob^2 == 4 -> passes <= check, strict is False!
        t4_eq = mod.check_ols_frob_shrinkage_q(eye2, mod.mat_scale(Fraction(2), eye2))
        self.assertTrue(t4_eq["cauchy_schwarz_holds"])
        self.assertFalse(t4_eq["strict_shrinkage_holds"])
        self.assertEqual(t4_eq["shrinkage_ratio_sq"], "1/1")
        zero2 = mod.mat_zero(2)
        with self.assertRaises(mod.StateTransportError):
            mod.check_ols_frob_shrinkage_q(zero2, eye2)
        with self.assertRaises(mod.StateTransportError):
            mod.check_ols_frob_shrinkage_q(eye2, zero2)

    def test_04_certificate_cli_and_tamper_refusal(self) -> None:
        cert = mod.build_certificate()
        self.assertEqual(cert["payload"]["schema"], mod.SCHEMA_ORACLE)
        self.assertTrue(cert["payload"]["all_passed"])

        # Exact depth boundary MAX_JSON_DEPTH passes; MAX_JSON_DEPTH + 1 fails!
        mod.validate_json_tree_no_floats({"a": [1, True, None, "ok"]})
        at_cap: object = "leaf"
        for _ in range(mod.MAX_JSON_DEPTH):
            at_cap = [at_cap]
        mod.validate_json_tree_no_floats(at_cap)
        over_cap: object = [at_cap]
        with self.assertRaises(mod.StateTransportError):
            mod.validate_json_tree_no_floats(over_cap)
        with self.assertRaises(mod.StateTransportError):
            mod.validate_json_tree_no_floats({"a": 1.5})
        with self.assertRaises(mod.StateTransportError):
            mod.validate_json_tree_no_floats({1: "bad_key"})
        with self.assertRaises(mod.StateTransportError):
            mod.validate_json_tree_no_floats({"a": object()})

        with tempfile.TemporaryDirectory() as td:
            cpath = Path(td) / "cert.json"
            out_buf = io.StringIO()
            with redirect_stdout(out_buf):
                rc = mod.main(["--write", str(cpath), "--json"])
            self.assertEqual(rc, 0)
            loaded = json.loads(out_buf.getvalue())
            self.assertEqual(loaded["certificate_sha256"], cert["certificate_sha256"])

            out_buf2 = io.StringIO()
            with redirect_stdout(out_buf2):
                rc2 = mod.main(["--check", str(cpath)])
            self.assertEqual(rc2, 0)
            self.assertIn("PASS", out_buf2.getvalue())

            # Tamper 1: mutate payload -> PAYLOAD_SHA_MISMATCH
            bad1 = Path(td) / "tamper_payload.json"
            tampered = json.loads(cpath.read_text(encoding="utf-8"))
            tampered["payload"]["all_passed"] = False
            bad1.write_text(json.dumps(tampered), encoding="utf-8")
            err_buf = io.StringIO()
            with redirect_stderr(err_buf):
                self.assertEqual(mod.main(["--check", str(bad1)]), 2)
            self.assertIn("PAYLOAD_SHA_MISMATCH", err_buf.getvalue())

            # Tamper 2: valid payload_sha256, stale cert_sha256 -> CERT_SHA_MISMATCH
            tampered["payload_sha256"] = hashlib.sha256(mod._canonical_json_bytes(tampered["payload"])).hexdigest()
            bad2 = Path(td) / "tamper_certsha.json"
            bad2.write_text(json.dumps(tampered), encoding="utf-8")
            err_buf2 = io.StringIO()
            with redirect_stderr(err_buf2):
                self.assertEqual(mod.main(["--check", str(bad2)]), 2)
            self.assertIn("CERT_SHA_MISMATCH", err_buf2.getvalue())

            # Tamper 3: re-signed forged payload -> REPLAY_MISMATCH
            inner = {"payload": tampered["payload"], "payload_sha256": tampered["payload_sha256"]}
            tampered["certificate_sha256"] = hashlib.sha256(mod._canonical_json_bytes(inner)).hexdigest()
            bad3 = Path(td) / "tamper_replay.json"
            bad3.write_text(json.dumps(tampered), encoding="utf-8")
            err_buf3 = io.StringIO()
            with redirect_stderr(err_buf3):
                self.assertEqual(mod.main(["--check", str(bad3)]), 2)
            self.assertIn("REPLAY_MISMATCH", err_buf3.getvalue())

            # Tamper 4: malformed / float / missing key / bad types / missing file
            for fname, txt, expect in (
                ("float.json", '{"payload": 1.5, "payload_sha256": "a", "certificate_sha256": "b"}', "FLOAT_FORBIDDEN"),
                ("keys.json", '{"payload": {}, "payload_sha256": "a"}', "CERT_KEYS"),
                ("list.json", "[1, 2, 3]", "CERT_NOT_DICT"),
                ("ht1.json", '{"payload": {}, "payload_sha256": 1, "certificate_sha256": "b"}', "CERT_HASH_TYPE"),
                ("ht2.json", '{"payload": {}, "payload_sha256": "a", "certificate_sha256": 2}', "CERT_HASH_TYPE"),
                ("badjson.json", "{not_json", "CERT_LOAD_FAIL"),
            ):
                p = Path(td) / fname
                p.write_text(txt, encoding="utf-8")
                eb = io.StringIO()
                with redirect_stderr(eb):
                    self.assertEqual(mod.main(["--check", str(p)]), 2)
                self.assertIn(expect, eb.getvalue())

            eb_miss = io.StringIO()
            with redirect_stderr(eb_miss):
                self.assertEqual(mod.main(["--check", str(Path(td) / "missing.json")]), 2)
            self.assertIn("CERT_LOAD_FAIL", eb_miss.getvalue())

            # Item 1: Missing or tampered PREREG-W12 / PREREG-W14 files must fail closed
            pr_sub = Path(td) / "prereg_sub"
            pr_sub.mkdir()
            with self.assertRaises(mod.StateTransportError) as cm_mp:
                mod.verify_prereg_locks(pr_sub)
            self.assertEqual(cm_mp.exception.code, "MISSING_PREREG")

            src_pr = HERE.parent / "preregistrations"
            (pr_sub / mod.PREREG_W12_FILENAME).write_bytes((src_pr / mod.PREREG_W12_FILENAME).read_bytes())
            with self.assertRaises(mod.StateTransportError) as cm_mp2:
                mod.verify_prereg_locks(pr_sub)
            self.assertEqual(cm_mp2.exception.code, "MISSING_PREREG")

            (pr_sub / mod.PREREG_W14_FILENAME).write_bytes((src_pr / mod.PREREG_W14_FILENAME).read_bytes())
            self.assertEqual(mod.verify_prereg_locks(pr_sub)["prereg_w12_sha256"], mod.PREREG_W12_SHA256)

            (pr_sub / mod.PREREG_W12_FILENAME).write_text("bad\n", encoding="utf-8")
            with self.assertRaises(mod.StateTransportError) as cm_bw12:
                mod.verify_prereg_locks(pr_sub)
            self.assertEqual(cm_bw12.exception.code, "PREREG_W12_MISMATCH")

            (pr_sub / mod.PREREG_W12_FILENAME).write_bytes((src_pr / mod.PREREG_W12_FILENAME).read_bytes())
            (pr_sub / mod.PREREG_W14_FILENAME).write_text("bad\n", encoding="utf-8")
            with self.assertRaises(mod.StateTransportError) as cm_bw14:
                mod.verify_prereg_locks(pr_sub)
            self.assertEqual(cm_bw14.exception.code, "PREREG_W14_MISMATCH")


if __name__ == "__main__":
    unittest.main(verbosity=2)
