#!/usr/bin/env python3
"""
Track S84: Comprehensive R5 Adversarial, Zone-B, Live-Lean R10+ Exploit,
No-Lean 0-Skip CI, Mutation & BoolOp Test Suite.

Strict hygiene:
  * Zero bare `assert`s (unittest assertions only).
  * Zero AST floats / float().
  * Zero hardcoded host-user paths.
  * Zero host device-node paths (uses scratch `os.mkfifo`).
  * Short-write mock uses one-shot `_zero_once` (guarantees timeout=0 under mutation testing).
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from fractions import Fraction
from pathlib import Path
from typing import Any
from unittest import mock

TRACK_DIR = Path(__file__).resolve().parent
if str(TRACK_DIR) not in sys.path:
    sys.path.insert(0, str(TRACK_DIR))

import s84_higher_order_k16_oracle as oracle
import verify_s84_higher_order_k16 as verifier


def _resign(env: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(env)
    p_sha = hashlib.sha256(oracle.canonical_json_bytes(out["payload"])).hexdigest()
    out["payload_sha256"] = p_sha
    eb = {
        "schema_version": out["schema_version"],
        "track_id": out["track_id"],
        "payload_sha256": p_sha,
        "payload": out["payload"],
    }
    out["certificate_sha256"] = hashlib.sha256(oracle.canonical_json_bytes(eb)).hexdigest()
    return out


def _lean_available() -> bool:
    try:
        verifier.resolve_lean_binary()
        return True
    except ValueError:
        return False


class TestOracleK16HigherOrderMath(unittest.TestCase):
    def test_01_rational_formatting_linalg_and_inertia(self) -> None:
        self.assertEqual(oracle.q_str(Fraction(15, 1)), "15")
        self.assertEqual(oracle.q_str(Fraction(8, 15)), "8/15")
        self.assertEqual(oracle.dec_from_q(Fraction(0, 1), 2), "0.00")
        self.assertEqual(oracle.dec_from_q(Fraction(1, 200), 2), "0.01")
        self.assertEqual(oracle.dec_from_q(Fraction(-3, 2), 2), "-1.50")
        self.assertEqual(oracle.dec_from_q(Fraction(-1, 10000), 2), "0.00")
        self.assertEqual(oracle.dec_from_q(Fraction(7, 2), 0), "4")

        # Singular matrix guard
        with self.assertRaisesRegex(ValueError, "SINGULAR_MATRIX"):
            oracle.q_solve([[Fraction(0), Fraction(0)], [Fraction(0), Fraction(0)]], [[Fraction(1)], [Fraction(1)]])

        # Non-trivial row pivot swap in q_solve
        sol = oracle.q_solve(
            [[Fraction(0), Fraction(2)], [Fraction(3), Fraction(1)]],
            [[Fraction(4)], [Fraction(5)]],
        )
        self.assertEqual(sol, [[Fraction(1)], [Fraction(2)]])

        # Sylvester inertia covering positive, negative, zero, and 2x2 off-diagonal pivot branches
        self.assertEqual(oracle.q_sylvester_inertia([[Fraction(0), Fraction(1)], [Fraction(1), Fraction(0)]]), [1, 1, 0])
        self.assertEqual(oracle.q_sylvester_inertia([[Fraction(0), Fraction(0), Fraction(1)], [Fraction(0), Fraction(0), Fraction(0)], [Fraction(1), Fraction(0), Fraction(0)]]), [1, 1, 1])
        self.assertEqual(oracle.q_sylvester_inertia([[Fraction(-2), Fraction(0)], [Fraction(0), Fraction(0)]]), [0, 1, 1])

        # 2x2 Schur match guard & edge lookup guards
        oracle.verify_schur_2x2_match([[Fraction(3), Fraction(-3)], [Fraction(-3), Fraction(3)]], Fraction(3))
        with self.assertRaisesRegex(ValueError, "SCHUR_2X2_MISMATCH"):
            oracle.verify_schur_2x2_match([[Fraction(3), Fraction(-2)], [Fraction(-3), Fraction(3)]], Fraction(3))
        with self.assertRaisesRegex(ValueError, "EDGE_INDEX_OUT_OF_RANGE"):
            oracle.build_edge_lookup(((5, 5, "EXACT_COMMUTE", "REFUSAL_GATE", "bad"),))
        with self.assertRaisesRegex(ValueError, "EDGE_INDEX_OUT_OF_RANGE"):
            oracle.build_edge_lookup(((0, 16, "EXACT_COMMUTE", "REFUSAL_GATE", "oob"),))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_EDGE"):
            oracle.build_edge_lookup(
                (
                    (0, 1, "EXACT_COMMUTE", "REFUSAL_GATE", "a"),
                    (0, 1, "EXACT_COMMUTE", "REFUSAL_GATE", "b"),
                )
            )
        with self.assertRaisesRegex(ValueError, "EXPECTED_120_EDGES"):
            oracle.build_edge_lookup(((0, 1, "EXACT_COMMUTE", "REFUSAL_GATE", "a"),))

    def test_02_all_four_orders_and_oracle_main(self) -> None:
        env = oracle.build_certificate_envelope()
        p = env["payload"]
        self.assertTrue(p["all_pillars_verified"])
        self.assertEqual(len(p["pinned_nodes"]), 16)

        p1 = p["pillar_1_order1_k16_and_k8_lift"]
        self.assertTrue(p1["all_verified"])
        self.assertEqual(p1["edge_count"], 120)
        self.assertEqual(p1["total_edge_weight"], 333)
        self.assertEqual(p1["laplacian_inertia"], [15, 0, 1])
        self.assertEqual(p1["foster_sum_q"], "15")
        self.assertTrue(p1["all_120_pairs_strictly_compounded"])
        self.assertEqual(p1["min_compounding_ratio_dec4"], "4.4697")
        self.assertEqual(p1["max_compounding_ratio_dec4"], "21.9371")
        self.assertTrue(p1["wave4_k8_submesh_comparison"]["all_28_wave4_pairs_strictly_amplified_by_k16"])
        self.assertEqual(p1["wave4_k8_submesh_comparison"]["min_k16_over_k8_lift_dec4"], "1.9346")
        self.assertEqual(p1["wave4_k8_submesh_comparison"]["max_k16_over_k8_lift_dec4"], "2.3624")

        p2 = p["pillar_2_order2_triangles_hodge_disjoint"]
        self.assertTrue(p2["all_verified"])
        self.assertEqual(sum(p2["triangle_counts"].values()), 560)
        self.assertEqual(p2["hodge_1_simplicial"]["b1_b2_nonzero_entries"], 0)
        self.assertEqual(p2["hodge_1_simplicial"]["gradient_dim"], 15)
        self.assertEqual(p2["hodge_1_simplicial"]["curl_dim"], 105)
        self.assertEqual(p2["disjoint_edge_second_order_convergences"]["curated_count"], 8)

        # Direct mutation killers for Pillar 1/2/4 oracle BoolOps & require_ok guards
        emap = oracle.build_edge_lookup()
        bad_nt = copy.deepcopy(list(oracle.DISJOINT_NATURAL_TRANSFORMS))
        bad_nt[0]["edge_b"] = [0, 9]  # overlaps n00
        with mock.patch.object(oracle, "DISJOINT_NATURAL_TRANSFORMS", tuple(bad_nt)):
            with self.assertRaisesRegex(ValueError, "DISJOINT_NT_OVERLAP"):
                oracle.certify_pillar2_order2_triangles_hodge_and_disjoint(emap)
        bad_nt2 = copy.deepcopy(list(oracle.DISJOINT_NATURAL_TRANSFORMS))
        bad_nt2[0]["operator_tag"] = "REFUSAL_GATE"
        with mock.patch.object(oracle, "DISJOINT_NATURAL_TRANSFORMS", tuple(bad_nt2)):
            with self.assertRaisesRegex(ValueError, "DISJOINT_NT_OP_MISMATCH"):
                oracle.certify_pillar2_order2_triangles_hodge_and_disjoint(emap)

        # Kill Pillar 1 all_verified BoolOp branches via surgical return-value patches
        with mock.patch.object(oracle, "q_sylvester_inertia", side_effect=[[14, 0, 2], [7, 0, 1]]):
            p1_bad_in, _, _ = oracle.certify_pillar1_order1_k16_and_k8_lift(emap)
            self.assertFalse(p1_bad_in["all_verified"])
        with mock.patch.object(oracle, "q_sylvester_inertia", side_effect=[[15, 0, 1], [6, 0, 2]]):
            p1_bad_k8, _, _ = oracle.certify_pillar1_order1_k16_and_k8_lift(emap)
            self.assertFalse(p1_bad_k8["all_verified"])
        # Kill min_ratio > 1 independently (foster_sum == 15 & min_lift > 1 hold!)
        orig_green = oracle.grounded_green_matrix
        lap16_for_p1 = oracle.build_weighted_laplacian(16, [(u, v, info[3]) for (u, v), info in sorted(emap.items())])
        lap8_for_p1 = oracle.build_weighted_laplacian(8, [(u, v, info[3]) for (u, v), info in sorted(emap.items()) if v < 8])
        z16_bad_ratio = oracle.q_zeros(16, 16)
        for idx_d in range(1, 14):
            z16_bad_ratio[idx_d][idx_d] = Fraction(1, 10000)
        z16_bad_ratio[14][14] = Fraction(1, 4)
        used_foster = sum(lap16_for_p1[i][i] * z16_bad_ratio[i][i] for i in range(1, 15))
        z16_bad_ratio[15][15] = (Fraction(15, 1) - used_foster) / lap16_for_p1[15][15]
        with mock.patch.object(oracle, "grounded_green_matrix", side_effect=[z16_bad_ratio, orig_green(lap8_for_p1)]):
            with mock.patch.object(oracle, "verify_schur_2x2_match"):
                p1_bad_r, _, _ = oracle.certify_pillar1_order1_k16_and_k8_lift(emap)
                self.assertEqual(p1_bad_r["foster_sum_q"], "15")
                self.assertTrue(p1_bad_r["wave4_k8_submesh_comparison"]["all_28_wave4_pairs_strictly_amplified_by_k16"])
                self.assertFalse(p1_bad_r["all_verified"])
        with mock.patch.object(oracle, "grounded_green_matrix", side_effect=[orig_green(lap16_for_p1), [[c / 10 for c in r] for r in orig_green(lap8_for_p1)]]):
            p1_bad_l, _, _ = oracle.certify_pillar1_order1_k16_and_k8_lift(emap)
            self.assertFalse(p1_bad_l["all_verified"])

        # Kill P4 all_verified BoolOp branches cleanly
        p3 = p["pillar_3_order3_tetrahedra_bianchi"]
        self.assertTrue(p3["all_verified"])
        self.assertEqual(p3["z2_bianchi_nonzero_count"], 0)
        self.assertEqual(p3["k4_exact_lock_count"], 40)
        self.assertEqual(p3["tetrahedron_counts"]["PAIRED_FRUSTRATION_REPAIR_TET"], 545)

        p4 = p["pillar_4_order4_5cells_metamesh_silocut_firewall"]
        self.assertTrue(p4["all_verified"])
        self.assertEqual(p4["k5_exact_lock_count"], 11)
        self.assertEqual(p4["fourth_order_meta_mesh_m4"]["foster_sum_q"], "3")
        self.assertEqual(p4["fourth_order_meta_mesh_m4"]["min_meta_compounding_ratio_dec4"], "1.8523")
        self.assertEqual([r["destroyed_8_8"] for r in p4["k_simplex_silo_cut_law_k16"]["orders"]], [64, 448, 1680, 4256])
        self.assertEqual(p4["law3_contagion_firewall_k16_to_k15"]["gated_corrupting_flux"], 0)
        self.assertEqual(p4["law3_contagion_firewall_k16_to_k15"]["k15_min_compounding_ratio_dec4"], "4.1344")

        _, lap16, g_eff_map = oracle.certify_pillar1_order1_k16_and_k8_lift(emap)
        _, tri_hol = oracle.certify_pillar2_order2_triangles_hodge_and_disjoint(emap)
        # Mutate g_eff_map[(0,6)] to kill j_ungated == g_eff_map[(0,6)]
        bad_g = dict(g_eff_map)
        bad_g[(0, 6)] = Fraction(1, 1)
        self.assertFalse(oracle.certify_pillar4_order4_5cells_metamesh_silocut_firewall(emap, tri_hol, lap16, bad_g)["all_verified"])
        # Mutate q_sylvester_inertia to kill m4_inertia == [3,0,1]
        with mock.patch.object(oracle, "q_sylvester_inertia", return_value=[2, 0, 2]):
            self.assertFalse(oracle.certify_pillar4_order4_5cells_metamesh_silocut_firewall(emap, tri_hol, lap16, g_eff_map)["all_verified"])
        # Mutate q_mul to kill quot_exact
        with mock.patch.object(oracle, "q_mul", return_value=oracle.q_zeros(4, 4)):
            self.assertFalse(oracle.certify_pillar4_order4_5cells_metamesh_silocut_firewall(emap, tri_hol, lap16, g_eff_map)["all_verified"])
        # Mutate q_solve ONLY on the 14x1 firewall interior solve while keeping j_ungated == g_eff_map[(0,6)]
        orig_solve = oracle.q_solve

        def _zero_fw_solve(a: Any, b: Any) -> Any:
            if len(a) == 14 and len(b[0]) == 1:
                return [[Fraction(0)] for _ in range(14)]
            return orig_solve(a, b)

        bad_g_zero = dict(g_eff_map)
        bad_g_zero[(0, 6)] = Fraction(4, 1)
        with mock.patch.object(oracle, "q_solve", side_effect=_zero_fw_solve):
            self.assertFalse(oracle.certify_pillar4_order4_5cells_metamesh_silocut_firewall(emap, tri_hol, lap16, bad_g_zero)["all_verified"])
        # Mutate grounded_green_matrix for M_4 & K_15 independently
        real_z_m4 = orig_green(oracle.build_weighted_laplacian(4, [(0, 1, Fraction(43)), (0, 2, Fraction(47)), (0, 3, Fraction(39)), (1, 2, Fraction(34)), (1, 3, Fraction(41)), (2, 3, Fraction(45))]))
        k15_nodes = [i for i in range(16) if i != 6]
        k15_map = {orig: idx for idx, orig in enumerate(k15_nodes)}
        k15_edges = [(k15_map[u], k15_map[v], info[3]) for (u, v), info in sorted(emap.items()) if 6 not in (u, v)]
        real_z_15 = orig_green(oracle.build_weighted_laplacian(15, k15_edges))
        with mock.patch.object(oracle, "grounded_green_matrix", side_effect=[real_z_m4, [[c * 100 for c in r] for r in real_z_15]]):
            self.assertFalse(oracle.certify_pillar4_order4_5cells_metamesh_silocut_firewall(emap, tri_hol, lap16, g_eff_map)["all_verified"])
        # Mutate m4_min_ratio <= 1 while keeping m4_foster == 3 EXACTLY!
        skew_m4 = oracle.q_zeros(4, 4)
        skew_m4[1][1] = Fraction(1, 42)
        skew_m4[2][2] = Fraction(1, 1000)
        skew_m4[3][3] = (Fraction(3, 1) - Fraction(118, 42) - Fraction(126, 1000)) / Fraction(125, 1)
        with mock.patch.object(oracle, "grounded_green_matrix", side_effect=[skew_m4, real_z_15]):
            res_sk = oracle.certify_pillar4_order4_5cells_metamesh_silocut_firewall(emap, tri_hol, lap16, g_eff_map)
            self.assertEqual(res_sk["fourth_order_meta_mesh_m4"]["foster_sum_q"], "3")
            self.assertFalse(res_sk["all_verified"])
        # Mutate only foster_sum (scale real_z_m4 by 1/2 so all ratios DOUBLE (>1) while foster = 3/2 != 3!)
        half_m4 = [[c / 2 for c in r] for r in real_z_m4]
        with mock.patch.object(oracle, "grounded_green_matrix", side_effect=[half_m4, real_z_15]):
            self.assertFalse(oracle.certify_pillar4_order4_5cells_metamesh_silocut_firewall(emap, tri_hol, lap16, g_eff_map)["all_verified"])
        # Kill P1 foster_sum == 15 independently (scale z16 by 1/2 -> ratios double > 1, lifts double > 1, foster = 15/2 != 15!)
        z16_real = orig_green(lap16)
        z8_real = orig_green(oracle.build_weighted_laplacian(8, [(u, v, info[3]) for (u, v), info in sorted(emap.items()) if v < 8]))
        with mock.patch.object(oracle, "grounded_green_matrix", side_effect=[[[c / 2 for c in r] for r in z16_real], z8_real]):
            with mock.patch.object(oracle, "verify_schur_2x2_match"):
                self.assertFalse(oracle.certify_pillar1_order1_k16_and_k8_lift(emap)[0]["all_verified"])
        # Kill P4 sum(cell_counts.values()) == 4368 via comb/range not needed if we keep cell_counts check clean — test via dict subclass? No, test P4_ok when sum != 4368 via mock
        # Also test oracle.main() pass & fail paths
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = oracle.main()
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(buf.getvalue())["certificate_sha256"], env["certificate_sha256"])

        bad_env = copy.deepcopy(env)
        bad_env["payload"]["all_pillars_verified"] = False
        with mock.patch.object(oracle, "build_certificate_envelope", return_value=bad_env):
            self.assertEqual(oracle.main(), 1)


class TestVerifierZoneBAndLeanS84(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.valid_env = oracle.build_certificate_envelope()

    def test_03_require_ok_sha_parse_int_cycles_and_depth(self) -> None:
        verifier.require_ok(True, "NOOP")
        with self.assertRaisesRegex(ValueError, "BOOM"):
            verifier.require_ok(False, "BOOM")

        self.assertTrue(verifier._is_sha256_hex("a" * 64))
        self.assertFalse(verifier._is_sha256_hex("A" * 64))
        self.assertFalse(verifier._is_sha256_hex("a" * 63))
        self.assertFalse(verifier._is_sha256_hex(12345))

        self.assertEqual(verifier._parse_strict_int("0" * verifier.MAX_INT_DIGITS), 0)
        self.assertEqual(verifier._parse_strict_int("-" + ("0" * verifier.MAX_INT_DIGITS)), 0)
        with self.assertRaisesRegex(ValueError, "JSON_INVALID_INT_TOKEN"):
            verifier._parse_strict_int("12_3")
        with self.assertRaisesRegex(ValueError, "JSON_INVALID_INT_TOKEN"):
            verifier._parse_strict_int("\u0661\u0662")
        with self.assertRaisesRegex(ValueError, "JSON_INT_TOO_LARGE"):
            verifier._parse_strict_int("9" * (verifier.MAX_INT_DIGITS + 1))
        with self.assertRaisesRegex(ValueError, "JSON_INT_TOO_LARGE"):
            verifier._parse_strict_int("9" * 5000)

        at_limit: Any = 1
        for _ in range(verifier.MAX_JSON_DEPTH):
            at_limit = [at_limit]
        verifier._check_json_depth_and_types(at_limit)
        with self.assertRaisesRegex(ValueError, "JSON_MAX_DEPTH_EXCEEDED"):
            verifier._check_json_depth_and_types([at_limit])

        verifier._check_json_depth_and_types({"v": (1 << verifier.MAX_INT_BITS) - 1, "b": True, "n": None})
        with self.assertRaisesRegex(ValueError, "JSON_INT_TOO_LARGE"):
            verifier._check_json_depth_and_types({"v": 1 << verifier.MAX_INT_BITS})

        # Cyclic list & cyclic dict rejection
        cyc_l: list[Any] = []
        cyc_l.append(cyc_l)
        with self.assertRaisesRegex(ValueError, "JSON_CYCLE"):
            verifier._check_json_depth_and_types(cyc_l)
        cyc_d: dict[str, Any] = {}
        cyc_d["self"] = cyc_d
        with self.assertRaisesRegex(ValueError, "JSON_CYCLE"):
            verifier._check_json_depth_and_types(cyc_d)

        class EvilDict(dict):
            pass

        with self.assertRaisesRegex(ValueError, "JSON_DISALLOWED_TYPE"):
            verifier._check_json_depth_and_types(EvilDict({"a": 1}))
        verifier._check_json_depth_and_types({"ok": "\ud7ff\ue000"})
        with self.assertRaisesRegex(ValueError, "JSON_LONE_SURROGATE"):
            verifier._check_json_depth_and_types({"bad": "\ud800"})
        with self.assertRaisesRegex(ValueError, "JSON_LONE_SURROGATE"):
            verifier._check_json_depth_and_types({"bad": "\udfff"})
        with self.assertRaisesRegex(ValueError, "JSON_NUL_IN_STRING"):
            verifier._check_json_depth_and_types({"bad": "a\x00b"})
        with self.assertRaisesRegex(ValueError, "JSON_NON_STRING_KEY"):
            verifier._check_json_depth_and_types({1: "x"})

    def test_04_hardened_io_fifo_hardlink_pwd_and_strict_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            good = d / "good.json"
            raw_good = oracle.canonical_json_bytes(self.valid_env)
            good.write_bytes(raw_good)
            loaded = verifier.load_strict_json_file(good)
            self.assertEqual(loaded["certificate_sha256"], self.valid_env["certificate_sha256"])

            with mock.patch.object(verifier, "MAX_JSON_BYTES", len(raw_good)):
                self.assertEqual(verifier.load_strict_json_file(good)["certificate_sha256"], self.valid_env["certificate_sha256"])

            with self.assertRaisesRegex(ValueError, "EMPTY_PATH"):
                verifier._validate_path_str("")
            with self.assertRaisesRegex(ValueError, "EMPTY_PATH"):
                verifier._validate_path_str(123)  # type: ignore[arg-type]
            with self.assertRaisesRegex(ValueError, "NUL_IN_PATH"):
                verifier._validate_path_str("a\x00b")
            with self.assertRaisesRegex(ValueError, "INVALID_PATH"):
                verifier.load_strict_json_file(Path("a\x00b"))
            with self.assertRaisesRegex(ValueError, "INVALID_PATH"):
                verifier.load_strict_json_file(Path("/"))
            with self.assertRaisesRegex(ValueError, "INVALID_PATH"):
                verifier.load_strict_json_file(d / "..")

            d_fd = os.open(str(d), os.O_RDONLY | os.O_DIRECTORY)
            try:
                self.assertIs(verifier._is_symlink_at(d_fd, "missing.json"), False)
            finally:
                os.close(d_fd)

            with self.assertRaisesRegex(ValueError, "OPEN_FAILED"):
                verifier.load_strict_json_file(d / "missing.json")
            with self.assertRaisesRegex(ValueError, "INVALID_PARENT_DIR"):
                verifier.load_strict_json_file(d / "no_dir" / "missing.json")
            with self.assertRaisesRegex(ValueError, "NOT_REGULAR_FILE"):
                verifier.load_strict_json_file(d)

            sym = d / "sym.json"
            sym.symlink_to(good)
            with self.assertRaisesRegex(ValueError, "SYMLINK_IN_PATH"):
                verifier.load_strict_json_file(sym)
            real_sub = d / "real_sub"
            real_sub.mkdir()
            (real_sub / "g.json").write_bytes(raw_good)
            sym_anc = d / "sym_anc"
            sym_anc.symlink_to(real_sub)
            with self.assertRaisesRegex(ValueError, "SYMLINK_IN_PATH"):
                verifier.load_strict_json_file(sym_anc / "g.json")

            # Non-blocking FIFO rejection via scratch mkfifo
            fifo_path = d / "pipe.fifo"
            os.mkfifo(fifo_path)
            t0 = time.monotonic_ns()
            with self.assertRaisesRegex(ValueError, "NOT_REGULAR_FILE"):
                verifier.load_strict_json_file(fifo_path)
            self.assertLess(time.monotonic_ns() - t0, 1_000_000_000)

            # Hardlink read rejection
            hl_read = d / "hl_read.json"
            os.link(good, hl_read)
            try:
                with self.assertRaisesRegex(ValueError, "HARDLINK_FORBIDDEN"):
                    verifier.load_strict_json_file(hl_read)
            finally:
                hl_read.unlink()

            # Logical $PWD symlink ancestor defense
            proc_pwd = subprocess.run(
                [sys.executable, "-I", "-B", str(TRACK_DIR / "verify_s84_higher_order_k16.py"), "--check", "g.json"],
                cwd=str(sym_anc),
                env={"PATH": os.environ.get("PATH", ""), "PWD": str(sym_anc)},
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(proc_pwd.returncode, 1)
            self.assertIn("SYMLINK_IN_PATH", proc_pwd.stderr)

            orig_cwd = os.getcwd()
            try:
                os.chdir(real_sub)
                with mock.patch.dict(os.environ, {"PWD": str(real_sub)}, clear=False):
                    self.assertEqual(verifier.load_strict_json_file(Path("g.json"))["certificate_sha256"], self.valid_env["certificate_sha256"])
                with mock.patch.dict(os.environ, {"PWD": "relative/pwd"}, clear=False):
                    self.assertEqual(verifier.load_strict_json_file(Path("g.json"))["certificate_sha256"], self.valid_env["certificate_sha256"])
                with mock.patch.dict(os.environ, {"PWD": str(d / "stale_dir")}, clear=False):
                    self.assertEqual(verifier.load_strict_json_file(Path("g.json"))["certificate_sha256"], self.valid_env["certificate_sha256"])
                with mock.patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(verifier.load_strict_json_file(Path("g.json"))["certificate_sha256"], self.valid_env["certificate_sha256"])
            finally:
                os.chdir(orig_cwd)

            for fname, raw, err_pat in (
                ("dup.json", b'{"a":1,"a":2}\n', "JSON_DUPLICATE_KEY"),
                ("flt.json", b'{"a":1.5}\n', "JSON_FLOAT_FORBIDDEN"),
                ("nan.json", b'{"a":NaN}\n', "JSON_CONSTANT_FORBIDDEN"),
                ("huge.json", (b'{"a":' + (b"9" * 5000) + b"}\n"), "JSON_INT_TOO_LARGE"),
                ("syn.json", b"{bad\n", "JSON_SYNTAX_ERROR"),
                ("arr.json", b"[1,2,3]\n", "JSON_ROOT_NOT_OBJECT"),
                ("nul.json", b'{"a":"x\x00y"}\n', "NUL_BYTE_IN_JSON"),
                ("crlf.json", b'{"a":1}\r\n', "CRLF_FORBIDDEN"),
                ("pretty.json", b'{\n  "a": 1\n}\n', "NON_CANONICAL_JSON_BYTES"),
                ("utf.json", b"\xff\xfe", "INVALID_UTF8"),
            ):
                fp = d / fname
                fp.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, err_pat):
                    verifier.load_strict_json_file(fp)

            with mock.patch("json.loads", side_effect=RecursionError("deep")):
                with self.assertRaisesRegex(ValueError, "JSON_MAX_DEPTH_EXCEEDED"):
                    verifier.load_strict_json_file(good)

            fake_st = os.stat_result((stat.S_IFREG | 0o600, 0, 0, 1, 0, 0, verifier.MAX_JSON_BYTES + 1, 0, 0, 0))
            with mock.patch("os.fstat", return_value=fake_st):
                with self.assertRaisesRegex(ValueError, "FILE_TOO_LARGE"):
                    verifier.load_strict_json_file(good)

            orig_read = os.read
            calls = [0]

            def _big_read(fd: int, n: int) -> bytes:
                calls[0] += 1
                if calls[0] <= 2:
                    return b" " * (verifier.MAX_JSON_BYTES // 2 + 10)
                return orig_read(fd, n)

            with mock.patch("os.read", side_effect=_big_read):
                with self.assertRaisesRegex(ValueError, "FILE_TOO_LARGE"):
                    verifier.load_strict_json_file(good)

    def test_05_atomic_write_0600_toctou_and_short_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            out = d / "cert.json"
            payload = oracle.canonical_json_bytes(self.valid_env)
            verifier.atomic_write_0600(out, payload)
            self.assertEqual(stat.S_IMODE(os.lstat(out).st_mode), 0o600)
            self.assertEqual(out.read_bytes(), payload)

            verifier.atomic_write_0600(out, payload)
            self.assertEqual(stat.S_IMODE(os.lstat(out).st_mode), 0o600)

            with self.assertRaisesRegex(ValueError, "INVALID_PATH"):
                verifier.atomic_write_0600(Path("a\x00b"), payload)
            with self.assertRaisesRegex(ValueError, "INVALID_PARENT_DIR"):
                verifier.atomic_write_0600(d / "nope" / "c.json", payload)
            sub_real = d / "real_dir"
            sub_real.mkdir()
            sub_sym = d / "sym_dir"
            sub_sym.symlink_to(sub_real)
            with self.assertRaisesRegex(ValueError, "SYMLINK_IN_PATH"):
                verifier.atomic_write_0600(sub_sym / "c.json", payload)
            tgt_sym = d / "tgt_sym.json"
            tgt_sym.symlink_to(out)
            with self.assertRaisesRegex(ValueError, "SYMLINK_IN_PATH"):
                verifier.atomic_write_0600(tgt_sym, payload)
            with self.assertRaisesRegex(ValueError, "TARGET_NOT_REGULAR"):
                verifier.atomic_write_0600(sub_real, payload)

            hl_src = d / "hl_src.json"
            hl_src.write_bytes(payload)
            hl_dst = d / "hl_dst.json"
            os.link(hl_src, hl_dst)
            with self.assertRaisesRegex(ValueError, "HARDLINK_FORBIDDEN"):
                verifier.atomic_write_0600(hl_dst, payload)

            fake_hl_st = os.stat_result((stat.S_IFREG | 0o600, 0, 0, 2, 0, 0, len(payload), 0, 0, 0))
            with mock.patch("os.fstat", return_value=fake_hl_st):
                with self.assertRaisesRegex(ValueError, "TMP_HARDLINK_DETECTED"):
                    verifier.atomic_write_0600(d / "tmp_hl.json", payload)
            self.assertEqual([p.name for p in d.iterdir() if p.name.endswith(".tmp")], [])

            toctou_tgt = d / "toctou.json"
            real_fsync = os.fsync
            swapped = [False]

            def _swap_on_fsync(fd: int) -> None:
                real_fsync(fd)
                if not swapped[0]:
                    swapped[0] = True
                    toctou_tgt.symlink_to(out)

            with mock.patch("os.fsync", side_effect=_swap_on_fsync):
                with self.assertRaisesRegex(ValueError, "SYMLINK_IN_PATH"):
                    verifier.atomic_write_0600(toctou_tgt, payload)
            self.assertEqual([p.name for p in d.iterdir() if p.name.endswith(".tmp")], [])

            fired = [False]
            real_write = os.write

            def _zero_once(fd: int, data: bytes) -> int:
                if not fired[0]:
                    fired[0] = True
                    return 0
                return real_write(fd, data)

            out2 = d / "short.json"
            with mock.patch("os.write", side_effect=_zero_once):
                with self.assertRaisesRegex(OSError, "SHORT_WRITE"):
                    verifier.atomic_write_0600(out2, payload)
            self.assertFalse(out2.exists())
            self.assertEqual([p.name for p in d.iterdir() if p.name.endswith(".tmp")], [])

    def test_06_lean_r10_static_live_and_no_lean_0_skip(self) -> None:
        clean_src = (
            "-- sorry in line comment\n"
            "/- /- admit \"quoted\" 'x' \u00abbad\u00bb nested -/ -/\n"
            "theorem ok : 1 = 1 := by decide\n"
            "theorem ok_f : 1 = 1 := by decide (native := false)\n"
            "theorem ok_bf : 1 = 1 := by decide (native := Bool.false)\n"
            "#print axioms ok\n"
        )
        self.assertTrue(verifier.audit_lean_source_static(clean_src)["clean"])

        for snippet, code in (
            ('def _a : String := s!"x"\n#eval 1\ndef _b : Char := \'"\'\n', "LEAN_QUOTE_OR_GUILLEMET_FORBIDDEN"),
            ('def _a : String := s!"x"\naxiom fake : False\ndef _b : Char := \'"\'\n', "LEAN_FORBIDDEN_KEYWORD"),
            ('def _s := s! "x"\ntheorem t : 1 = 1 := by native_decide\n', "LEAN_FORBIDDEN_KEYWORD"),
            ('def _open := "/-"\naxiom fake : False\ndef _close := "-/"\n', "LEAN_QUOTE_OR_GUILLEMET_FORBIDDEN"),
            ('def _r := r#"""#\n', "LEAN_QUOTE_OR_GUILLEMET_FORBIDDEN"),
            ("set_option \u00abdebug\u00bb.\u00abskipKernelTC\u00bb true\n", "LEAN_SKIP_KERNEL_TC"),
            ("theorem t : False := by sorry", "LEAN_FORBIDDEN_KEYWORD"),
            ("theorem t : False := by admit", "LEAN_FORBIDDEN_KEYWORD"),
            ("axiom bogus : False", "LEAN_FORBIDDEN_KEYWORD"),
            ("unsafe def u := 1", "LEAN_FORBIDDEN_KEYWORD"),
            ("def x := Lean.ofReduceNat", "LEAN_FORBIDDEN_KEYWORD"),
            ("def x := Lean.Meta.mkSorry", "LEAN_FORBIDDEN_KEYWORD"),
            ("declare_syntax_cat mycat", "LEAN_FORBIDDEN_KEYWORD"),
            ("notation myop => 0", "LEAN_FORBIDDEN_KEYWORD"),
            ("def f : Nat := dbg_trace 1; 0", "LEAN_FORBIDDEN_KEYWORD"),
            ("def f : Nat := throwError 0", "LEAN_FORBIDDEN_KEYWORD"),
            ("run_cmd pure ()", "LEAN_FORBIDDEN_KEYWORD"),
            ("partial def p (n : Nat) : Nat := p n", "LEAN_PARTIAL_DECL"),
            ("theorem t : True := by decide +native", "LEAN_DECIDE_NATIVE"),
            ("theorem t : True := by decide (revert := true) +native", "LEAN_DECIDE_NATIVE"),
            ("theorem t : True := by decide -revert +native", "LEAN_DECIDE_NATIVE"),
            ("theorem t : True := by decide +revert +native", "LEAN_DECIDE_NATIVE"),
            ("theorem t : True := by decide (config := { native := !false })", "LEAN_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (native := false || true)", "LEAN_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (native := false == false)", "LEAN_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (native := false != true)", "LEAN_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (native := false.not)", "LEAN_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (native := false\n  || true)", "LEAN_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (native := Bool.false || true)", "LEAN_DECIDE_NATIVE"),
            ("def cfg : DecideConfig := {}", "LEAN_DECIDE_NATIVE"),
            ("set_option debug.skipKernelTC true", "LEAN_SKIP_KERNEL_TC"),
            ("#eval 1 + 1", "LEAN_EVAL_OR_PRINT_SPOOF"),
            ("#print Nat.add", "LEAN_EVAL_OR_PRINT_SPOOF"),
            ("#print axioms example", "LEAN_EVAL_OR_PRINT_SPOOF"),
            ("#exit", "LEAN_EVAL_OR_PRINT_SPOOF"),
            ("@[csimp] theorem bad : 1 = 1 := rfl", "LEAN_ATTR_TRUST_ESCAPE"),
            ("attribute [implemented_by g] f", "LEAN_ATTR_TRUST_ESCAPE"),
            ("import Lean", "LEAN_NON_ZERO_IMPORTS"),
            ("/- unterminated comment", "LEAN_UNTERMINATED_BLOCK_COMMENT"),
        ):
            r = verifier.audit_lean_source_static(snippet)
            self.assertFalse(r["clean"], msg=f"Expected failure on: {snippet}")
            self.assertTrue(any(f.startswith(code) for f in r["findings"]), msg=f"{snippet} -> {r}")

        lean_file = TRACK_DIR / "HigherOrderEpistemicMesh.lean"

        # 0-skip live-or-no-Lean parity
        if _lean_available():
            live = verifier.verify_lean_proof(lean_file)
            self.assertTrue(live["static_clean"])
            self.assertTrue(live["sha256_pinned"])
            self.assertEqual(live["theorems_verified"], len(oracle.EXPECTED_LEAN_THEOREMS))
            self.assertEqual(live["zero_axiom_theorems"], 4)
            self.assertEqual(live["axioms_used"], ["Quot.sound", "propext"])
            self.assertEqual(live["imports"], [])
        else:
            with self.assertRaisesRegex(ValueError, "LEAN_BINARY_UNAVAILABLE"):
                verifier.verify_lean_proof(lean_file)

        # ALETHEIA_LEAN_BIN override tests (executable file, non-exec file, directory)
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            fake_bin = d / "lean"
            fake_bin.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(fake_bin, 0o700)
            noexec = d / "lean_noexec"
            noexec.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(noexec, 0o600)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(fake_bin)}):
                self.assertEqual(verifier.resolve_lean_binary(), str(fake_bin))
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(noexec)}):
                with self.assertRaisesRegex(ValueError, "LEAN_BINARY_UNAVAILABLE"):
                    verifier.resolve_lean_binary()
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(d)}):
                with self.assertRaisesRegex(ValueError, "LEAN_BINARY_UNAVAILABLE"):
                    verifier.resolve_lean_binary()

            # E2E exploit regressions (even with enforce_sha256=False!) & SHA-256 trivialization block
            forged = d / "forged.lean"
            forged.write_text(
                'def _a : String := s!"x"\n#eval 1\ndef _b : Char := \'"\'\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "LEAN_STATIC_AUDIT_FAILED"):
                verifier.verify_lean_proof(forged, enforce_sha256=False)

            triv = d / "trivial.lean"
            triv.write_text("theorem x : True := trivial\n#print axioms x\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "LEAN_SHA256_MISMATCH"):
                verifier.verify_lean_proof(triv)
            with self.assertRaisesRegex(ValueError, "INVALID_ENFORCE_SHA256_FLAG"):
                verifier.verify_lean_proof(lean_file, enforce_sha256=0)  # type: ignore[arg-type]

            with self.assertRaisesRegex(ValueError, "NOT_REGULAR_FILE"):
                verifier.verify_lean_proof(d)
            sym = d / "sym.lean"
            sym.symlink_to(lean_file)
            with self.assertRaisesRegex(ValueError, "SYMLINK_IN_PATH"):
                verifier.verify_lean_proof(sym)
            bad_utf = d / "bad_utf.lean"
            bad_utf.write_bytes(b"\xff\xfe")
            with self.assertRaisesRegex(ValueError, "LEAN_INVALID_UTF8"):
                verifier.verify_lean_proof(bad_utf)

        # Mocked Lean subprocess edge cases (work identically with OR without real lean binary!)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ALETHEIA_LEAN_BIN", None)
            with mock.patch("shutil.which", return_value=None):
                with self.assertRaisesRegex(ValueError, "LEAN_BINARY_UNAVAILABLE"):
                    verifier.verify_lean_proof(lean_file)

        with mock.patch.object(verifier, "resolve_lean_binary", return_value="lean"):
            with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess(["lean"], 1, stdout="", stderr="err")):
                with self.assertRaisesRegex(ValueError, "LEAN_COMPILE_FAILED"):
                    verifier.verify_lean_proof(lean_file)
            with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess(["lean"], 0, stdout="", stderr="warn")):
                with self.assertRaisesRegex(ValueError, "LEAN_NONEMPTY_STDERR"):
                    verifier.verify_lean_proof(lean_file)
            with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess(["lean"], 0, stdout="warning: x\n", stderr="")):
                with self.assertRaisesRegex(ValueError, "LEAN_UNEXPECTED_STDOUT_LINE"):
                    verifier.verify_lean_proof(lean_file)
            with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess(["lean"], 0, stdout="  indented\n", stderr="")):
                with self.assertRaisesRegex(ValueError, "LEAN_UNEXPECTED_STDOUT_LINE"):
                    verifier.verify_lean_proof(lean_file)
            dup0 = f"'{oracle.EXPECTED_LEAN_THEOREMS[0]}' does not depend on any axioms\n" * 2
            with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess(["lean"], 0, stdout=dup0, stderr="")):
                with self.assertRaisesRegex(ValueError, "LEAN_DUPLICATE_THEOREM"):
                    verifier.verify_lean_proof(lean_file)
            dup1 = f"'{oracle.EXPECTED_LEAN_THEOREMS[0]}' depends on axioms: [propext]\n" * 2
            with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess(["lean"], 0, stdout=dup1, stderr="")):
                with self.assertRaisesRegex(ValueError, "LEAN_DUPLICATE_THEOREM"):
                    verifier.verify_lean_proof(lean_file)
            bad_ax = f"'{oracle.EXPECTED_LEAN_THEOREMS[0]}' depends on axioms: [Classical.choice]\n"
            with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess(["lean"], 0, stdout=bad_ax, stderr="")):
                with self.assertRaisesRegex(ValueError, "LEAN_FORBIDDEN_AXIOM"):
                    verifier.verify_lean_proof(lean_file)
            short_out = f"'{oracle.EXPECTED_LEAN_THEOREMS[0]}' does not depend on any axioms\n"
            with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess(["lean"], 0, stdout=short_out, stderr="")):
                with self.assertRaisesRegex(ValueError, "LEAN_THEOREM_LIST_MISMATCH"):
                    verifier.verify_lean_proof(lean_file)

            wrapped = []
            for idx, thm in enumerate(oracle.EXPECTED_LEAN_THEOREMS):
                if idx == 0:
                    wrapped.append(f"'{thm}' depends on axioms:\n  [propext, Quot.sound]")
                elif idx == 1:
                    wrapped.append(f"'{thm}'\n  does not depend on any axioms")
                else:
                    wrapped.append(f"'{thm}' does not depend on any axioms")
            with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess(["lean"], 0, stdout="\n".join(wrapped) + "\n", stderr="")):
                res_w = verifier.verify_lean_proof(lean_file)
                self.assertEqual(res_w["theorems_verified"], len(oracle.EXPECTED_LEAN_THEOREMS))

    def test_07_verify_cert_fr1_fr0_and_secondary_audit_matrix(self) -> None:
        ok_fr1 = verifier.verify_certificate_dict(self.valid_env, full_replay=True)
        self.assertTrue(ok_fr1["all_pillars_verified"])
        self.assertTrue(ok_fr1["full_replay"])

        with mock.patch.object(verifier, "build_certificate_envelope", side_effect=RuntimeError("NO_REPLAY_IN_FR0")):
            ok_fr0 = verifier.verify_certificate_dict(self.valid_env, full_replay=False)
            self.assertFalse(ok_fr0["full_replay"])
            self.assertTrue(ok_fr0["secondary_audit_passed"])

        with self.assertRaisesRegex(ValueError, "INVALID_FULL_REPLAY_FLAG"):
            verifier.verify_certificate_dict(self.valid_env, full_replay=1)  # type: ignore[arg-type]

        # Envelope rejections
        with self.assertRaisesRegex(ValueError, "CERT_NOT_DICT"):
            verifier.secondary_audit_payload([])
        extra = copy.deepcopy(self.valid_env)
        extra["extra"] = 1
        with self.assertRaisesRegex(ValueError, "CERT_TOP_KEYS_MISMATCH"):
            verifier.secondary_audit_payload(extra)
        for field, val, err in (
            ("schema_version", "wrong", "SCHEMA_VERSION_MISMATCH"),
            ("track_id", "wrong", "TRACK_ID_MISMATCH"),
            ("payload_sha256", "not-hex", "INVALID_PAYLOAD_SHA256"),
            ("certificate_sha256", "not-hex", "INVALID_CERT_SHA256"),
            ("payload", [], "PAYLOAD_NOT_DICT"),
            ("certificate_sha256", "0" * 64, "CERTIFICATE_SHA256_TAMPERED"),
        ):
            e = copy.deepcopy(self.valid_env)
            e[field] = val
            with self.assertRaisesRegex(ValueError, err):
                verifier.secondary_audit_payload(e)
        tp = copy.deepcopy(self.valid_env)
        tp["payload"]["novelty_tier"] = "N9"
        with self.assertRaisesRegex(ValueError, "PAYLOAD_SHA256_TAMPERED"):
            verifier.secondary_audit_payload(tp)

        # FR1-only oracle drift
        drift = copy.deepcopy(self.valid_env)
        drift["payload"]["pinned_nodes"][0]["anchor"] = "DRIFTED"
        drift = _resign(drift)
        verifier.secondary_audit_payload(drift)
        with self.assertRaisesRegex(ValueError, "ORACLE_PAYLOAD_DRIFT"):
            verifier.verify_certificate_dict(drift, full_replay=True)

        fake_rec = copy.deepcopy(self.valid_env)
        fake_rec["certificate_sha256"] = "f" * 64
        with mock.patch.object(verifier, "build_certificate_envelope", return_value=fake_rec):
            with self.assertRaisesRegex(ValueError, "ORACLE_CERT_DRIFT"):
                verifier.verify_certificate_dict(self.valid_env, full_replay=True)

        # Exhaustive re-signed semantic tamper matrix covering EVERY guard in _audit_payload_pillars
        def _tamper(mut: Any, code: str) -> None:
            e = copy.deepcopy(self.valid_env)
            mut(e["payload"])
            with self.assertRaisesRegex(ValueError, code):
                verifier.secondary_audit_payload(_resign(e))

        _tamper(lambda p: p.pop("novelty_tier"), "PAYLOAD_KEYS_MISMATCH")
        _tamper(lambda p: p.__setitem__("track_id", "X"), "PAYLOAD_TRACK_MISMATCH")
        _tamper(lambda p: p.__setitem__("oracle_class", "X"), "ORACLE_CLASS_MISMATCH")
        _tamper(lambda p: p.__setitem__("novelty_tier", "N0"), "NOVELTY_TIER_MISMATCH")
        _tamper(lambda p: p.__setitem__("lean_toolchain", "X"), "LEAN_TOOLCHAIN_MISMATCH")
        _tamper(lambda p: p.__setitem__("lean_source_sha256", "0" * 64), "PAYLOAD_LEAN_SHA_MISMATCH")
        _tamper(lambda p: p.__setitem__("lean_theorem_count", 17), "LEAN_COUNT_MISMATCH")
        _tamper(lambda p: p.__setitem__("all_pillars_verified", False), "PILLARS_NOT_VERIFIED")
        _tamper(lambda p: p.__setitem__("pinned_nodes", "0" * 16), "NODES_NOT_LIST")
        _tamper(lambda p: p.__setitem__("pinned_nodes", []), "NODES_LEN_MISMATCH")
        _tamper(lambda p: p["pinned_nodes"].__setitem__(0, []), "NODE_NOT_DICT")
        _tamper(lambda p: p["pinned_nodes"][0].__setitem__("id", "bad"), "NODE_ID_MISMATCH")
        _tamper(lambda p: p["pinned_nodes"][0].__setitem__("sha256", "bad"), "NODE_SHA_INVALID")
        _tamper(lambda p: p["pinned_nodes"][0].__setitem__("bytes", 0), "NODE_BYTES_NONPOS")

        # Pillar 1 guards
        _tamper(lambda p: p.__setitem__("pillar_1_order1_k16_and_k8_lift", []), "P1_NOT_DICT")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"].__setitem__("all_verified", False), "P1_NOT_VERIFIED")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"].__setitem__("node_count", 8), "P1_NODE_COUNT_MISMATCH")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"].__setitem__("edge_count", 28), "P1_EDGE_COUNT_MISMATCH")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"].__setitem__("foster_sum_q", "7"), "P1_FOSTER_MISMATCH")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"].__setitem__("all_120_pairs_strictly_compounded", False), "P1_COMPOUNDING_FAILED")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"].__setitem__("laplacian_inertia", "123"), "P1_INERTIA_INVALID")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"].__setitem__("laplacian_inertia", [15, 0]), "P1_INERTIA_INVALID")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"].__setitem__("laplacian_inertia", [14, 0, 2]), "P1_INERTIA_MISMATCH")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"].__setitem__("laplacian_inertia", [15, False, True]), "P1_INT_INVALID")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"].__setitem__("canonical_edges", "x" * 120), "P1_EDGES_NOT_LIST")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"].__setitem__("canonical_edges", []), "P1_EDGES_LEN_MISMATCH")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"]["canonical_edges"].__setitem__(0, []), "P1_EDGE_NOT_DICT")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"]["canonical_edges"][0].__setitem__("pathway_class", "BAD"), "P1_EDGE_CLASS_INVALID")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"]["canonical_edges"][0].__setitem__("weight", 99), "P1_EDGE_WEIGHT_MISMATCH")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"]["canonical_edges"][0].__setitem__("operator_tag", "BAD"), "P1_EDGE_OP_INVALID")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"].__setitem__("total_edge_weight", 999), "P1_TOTAL_WEIGHT_MISMATCH")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"].__setitem__("max_compounding_direct_w", 0), "P1_INT_INVALID")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"].__setitem__("wave4_k8_submesh_comparison", []), "P1_K8_NOT_DICT")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"]["wave4_k8_submesh_comparison"].__setitem__("k8_edge_count", 27), "P1_K8_EDGES_MISMATCH")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"]["wave4_k8_submesh_comparison"].__setitem__("all_28_wave4_pairs_strictly_amplified_by_k16", False), "P1_K8_LIFT_FAILED")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"]["wave4_k8_submesh_comparison"].__setitem__("k8_schur_pushforward_inertia", "123"), "P1_K8_INERTIA_INVALID")
        _tamper(lambda p: p["pillar_1_order1_k16_and_k8_lift"]["wave4_k8_submesh_comparison"].__setitem__("k8_schur_pushforward_inertia", [6, 0, 2]), "P1_K8_INERTIA_MISMATCH")

        # Pillar 2 guards
        _tamper(lambda p: p.__setitem__("pillar_2_order2_triangles_hodge_disjoint", []), "P2_NOT_DICT")
        _tamper(lambda p: p["pillar_2_order2_triangles_hodge_disjoint"].__setitem__("all_verified", False), "P2_NOT_VERIFIED")
        _tamper(lambda p: p["pillar_2_order2_triangles_hodge_disjoint"].__setitem__("triangle_counts", []), "P2_TC_NOT_DICT")
        _tamper(lambda p: p["pillar_2_order2_triangles_hodge_disjoint"]["triangle_counts"].__setitem__("EXACT_TRANSITIVE_CLOSURE", 0), "P2_TRIANGLE_SUM_MISMATCH")
        _tamper(lambda p: p["pillar_2_order2_triangles_hodge_disjoint"].__setitem__("hodge_1_simplicial", []), "P2_HODGE_NOT_DICT")
        _tamper(lambda p: p["pillar_2_order2_triangles_hodge_disjoint"]["hodge_1_simplicial"].__setitem__("b1_b2_nonzero_entries", 1), "P2_B1B2_NONZERO")
        _tamper(lambda p: p["pillar_2_order2_triangles_hodge_disjoint"]["hodge_1_simplicial"].__setitem__("b1_b2_identically_zero", False), "P2_B1B2_FLAG_FAILED")
        _tamper(lambda p: p["pillar_2_order2_triangles_hodge_disjoint"]["hodge_1_simplicial"].__setitem__("gradient_dim", 14), "P2_HODGE_DIM_MISMATCH")

        def _mut_harm(p: dict[str, Any]) -> None:
            h = p["pillar_2_order2_triangles_hodge_disjoint"]["hodge_1_simplicial"]
            h["curl_dim"] = 104
            h["harmonic_dim"] = 1

        _tamper(_mut_harm, "P2_HARM_DIM_NONZERO")
        _tamper(lambda p: p["pillar_2_order2_triangles_hodge_disjoint"]["hodge_1_simplicial"].__setitem__("b1_b1t_inertia", "123"), "P2_B1_INERTIA_INVALID")
        _tamper(lambda p: p["pillar_2_order2_triangles_hodge_disjoint"]["hodge_1_simplicial"].__setitem__("b1_b1t_inertia", [14, 0, 2]), "P2_B1_INERTIA_MISMATCH")
        _tamper(lambda p: p["pillar_2_order2_triangles_hodge_disjoint"].__setitem__("disjoint_edge_second_order_convergences", []), "P2_DISJOINT_NOT_DICT")
        _tamper(lambda p: p["pillar_2_order2_triangles_hodge_disjoint"]["disjoint_edge_second_order_convergences"].__setitem__("curated_transforms", "12345678"), "P2_CURATED_NOT_LIST")
        _tamper(lambda p: p["pillar_2_order2_triangles_hodge_disjoint"]["disjoint_edge_second_order_convergences"].__setitem__("curated_transforms", []), "P2_CURATED_LEN_MISMATCH")

        # Pillar 3 guards
        _tamper(lambda p: p.__setitem__("pillar_3_order3_tetrahedra_bianchi", []), "P3_NOT_DICT")
        _tamper(lambda p: p["pillar_3_order3_tetrahedra_bianchi"].__setitem__("all_verified", False), "P3_NOT_VERIFIED")
        _tamper(lambda p: p["pillar_3_order3_tetrahedra_bianchi"].__setitem__("z2_bianchi_nonzero_count", 1), "P3_BIANCHI_NONZERO")
        _tamper(lambda p: p["pillar_3_order3_tetrahedra_bianchi"].__setitem__("z2_bianchi_all_zero", False), "P3_BIANCHI_FLAG_FAILED")
        _tamper(lambda p: p["pillar_3_order3_tetrahedra_bianchi"].__setitem__("tetrahedron_counts", []), "P3_TET_NOT_DICT")
        _tamper(lambda p: p["pillar_3_order3_tetrahedra_bianchi"]["tetrahedron_counts"].__setitem__("K4_EXACT_LOCK", 0), "P3_TET_SUM_MISMATCH")
        _tamper(lambda p: p["pillar_3_order3_tetrahedra_bianchi"].__setitem__("k4_exact_lock_count", 0), "P3_K4_LOCK_MISMATCH")

        # Pillar 4 guards
        _tamper(lambda p: p.__setitem__("pillar_4_order4_5cells_metamesh_silocut_firewall", []), "P4_NOT_DICT")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"].__setitem__("all_verified", False), "P4_NOT_VERIFIED")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"].__setitem__("five_cell_counts", []), "P4_CC_NOT_DICT")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["five_cell_counts"].__setitem__("K5_EXACT_LOCK", 0), "P4_5CELL_SUM_MISMATCH")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"].__setitem__("five_cell_frustrated_face_histogram", []), "P4_HIST_NOT_DICT")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["five_cell_frustrated_face_histogram"].__setitem__("0", 0), "P4_HIST_SUM_MISMATCH")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"].__setitem__("fourth_order_meta_mesh_m4", []), "P4_M4_NOT_DICT")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["fourth_order_meta_mesh_m4"].__setitem__("quotient_identity_pt_l0_p_exact", False), "P4_M4_QUOT_FAILED")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["fourth_order_meta_mesh_m4"].__setitem__("foster_sum_q", "2"), "P4_M4_FOSTER_MISMATCH")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["fourth_order_meta_mesh_m4"].__setitem__("all_6_meta_pairs_strictly_compounded", False), "P4_M4_COMP_FAILED")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["fourth_order_meta_mesh_m4"].__setitem__("laplacian_inertia", "123"), "P4_M4_INERTIA_INVALID")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["fourth_order_meta_mesh_m4"].__setitem__("laplacian_inertia", [2, 0, 2]), "P4_M4_INERTIA_MISMATCH")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["fourth_order_meta_mesh_m4"].__setitem__("clusters", "1234"), "P4_M4_CLUSTERS_NOT_LIST")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["fourth_order_meta_mesh_m4"].__setitem__("clusters", []), "P4_M4_CLUSTERS_LEN_MISMATCH")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["fourth_order_meta_mesh_m4"]["clusters"].__setitem__(0, []), "P4_M4_CLUSTER_NOT_DICT")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["fourth_order_meta_mesh_m4"]["clusters"][0].__setitem__("internal_obstruction_edges", False), "P4_INT_INVALID")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"].__setitem__("k_simplex_silo_cut_law_k16", []), "P4_SILO_NOT_DICT")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["k_simplex_silo_cut_law_k16"].__setitem__("orders", "1234"), "P4_SILO_ORDERS_NOT_LIST")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["k_simplex_silo_cut_law_k16"].__setitem__("orders", []), "P4_SILO_LEN_MISMATCH")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["k_simplex_silo_cut_law_k16"]["orders"].__setitem__(0, []), "P4_SILO_ROW_NOT_DICT")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["k_simplex_silo_cut_law_k16"]["orders"][0].__setitem__("order", 9), "P4_SILO_ORDER_MISMATCH")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["k_simplex_silo_cut_law_k16"]["orders"][0].__setitem__("destroyed_8_8", 63), "P4_SILO_DESTROYED_MISMATCH")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["k_simplex_silo_cut_law_k16"]["orders"][0].__setitem__("strictly_below_exponential_ceiling", False), "P4_SILO_CEIL_FAILED")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"].__setitem__("law3_contagion_firewall_k16_to_k15", []), "P4_FW_NOT_DICT")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["law3_contagion_firewall_k16_to_k15"].__setitem__("gated_corrupting_flux", 1), "P4_FW_GATED_FLUX_NONZERO")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["law3_contagion_firewall_k16_to_k15"].__setitem__("gated_interior_nodes_corrupted", 1), "P4_FW_GATED_INT_NONZERO")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["law3_contagion_firewall_k16_to_k15"].__setitem__("ungated_all_14_interior_corrupted", False), "P4_FW_UNGATED_FAILED")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["law3_contagion_firewall_k16_to_k15"].__setitem__("k15_surviving_five_cells", 3000), "P4_FW_K15_MISMATCH")
        _tamper(lambda p: p["pillar_4_order4_5cells_metamesh_silocut_firewall"]["law3_contagion_firewall_k16_to_k15"].__setitem__("k15_all_105_pairs_compounded", False), "P4_FW_K15_COMP_FAILED")

        # Lean report checks in secondary_audit_payload
        n_thms = len(oracle.EXPECTED_LEAN_THEOREMS)
        self.assertFalse(verifier.secondary_audit_payload(self.valid_env)["lean_verified"])
        self.assertTrue(verifier.secondary_audit_payload(self.valid_env, {"static_clean": True, "theorems_verified": n_thms})["lean_verified"])
        with self.assertRaisesRegex(ValueError, "LEAN_REPORT_NOT_DICT"):
            verifier.secondary_audit_payload(self.valid_env, "bad")
        for bad_lr in (
            {"static_clean": False, "theorems_verified": n_thms},
            {"static_clean": True, "theorems_verified": True},
            {"static_clean": True, "theorems_verified": n_thms - 1},
        ):
            with self.assertRaisesRegex(ValueError, "LEAN_REPORT_INCOMPLETE"):
                verifier.secondary_audit_payload(self.valid_env, bad_lr)

    def test_08_pinned_nodes_and_cli_modes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            f1 = root / "sub" / "a.json"
            f1.parent.mkdir()
            raw = b'{"ok":true}\n'
            f1.write_bytes(raw)
            sha = hashlib.sha256(raw).hexdigest()
            fake_nodes = ({"id": "n00", "relative_ref": "sub/a.json", "sha256": sha, "bytes": len(raw)},)

            with mock.patch.object(verifier, "MESH_NODES", fake_nodes):
                res = verifier.verify_pinned_nodes_on_disk(root)
                self.assertEqual(res["nodes_checked"], 1)
                self.assertTrue(res["all_matched"])

                with mock.patch.object(verifier, "MESH_NODES", ({"id": "n00", "relative_ref": "sub/a.json", "sha256": sha, "bytes": len(raw) + 1},)):
                    with self.assertRaisesRegex(ValueError, "PINNED_NODE_BYTES_MISMATCH"):
                        verifier.verify_pinned_nodes_on_disk(root)

                with mock.patch.object(verifier, "MESH_NODES", ({"id": "n00", "relative_ref": "sub/a.json", "sha256": "0" * 64, "bytes": len(raw)},)):
                    with self.assertRaisesRegex(ValueError, "PINNED_NODE_SHA_MISMATCH"):
                        verifier.verify_pinned_nodes_on_disk(root)

                with self.assertRaisesRegex(ValueError, "EXPEDITION_ROOT_INVALID"):
                    verifier.verify_pinned_nodes_on_disk(root / "missing")

            cert_path = root / "out_cert.json"

            out_buf = io.StringIO()
            with redirect_stdout(out_buf):
                rc = verifier.main(["--standalone", "--json"])
            self.assertEqual(rc, 0)
            self.assertNotIn("lean", json.loads(out_buf.getvalue()))

            out_buf = io.StringIO()
            with redirect_stdout(out_buf):
                rc = verifier.main(["--write", str(cert_path), "--json"])
            self.assertEqual(rc, 0)
            self.assertNotIn("lean", json.loads(out_buf.getvalue()))
            self.assertEqual(stat.S_IMODE(os.lstat(cert_path).st_mode), 0o600)

            out_buf = io.StringIO()
            with redirect_stdout(out_buf):
                rc = verifier.main(["--check", str(cert_path), "--json"])
            self.assertEqual(rc, 0)
            self.assertNotIn("lean", json.loads(out_buf.getvalue()))

            out_buf = io.StringIO()
            with redirect_stdout(out_buf):
                rc = verifier.main(["--check", str(cert_path)])
            self.assertEqual(rc, 0)
            self.assertIn("PASS", out_buf.getvalue())

            # Default --json & explicit --lean (live when lean present; mocked cleanly under no-Lean CI!)
            lean_stub = {
                "lean_file": "HigherOrderEpistemicMesh.lean",
                "lean_sha256": oracle.EXPECTED_LEAN_SHA256,
                "sha256_pinned": True,
                "static_clean": True,
                "theorems_verified": len(oracle.EXPECTED_LEAN_THEOREMS),
                "zero_axiom_theorems": 4,
                "axioms_used": ["Quot.sound", "propext"],
                "imports": [],
            }
            if _lean_available():
                out_buf = io.StringIO()
                with redirect_stdout(out_buf):
                    rc = verifier.main(["--json"])
                self.assertEqual(rc, 0)
                self.assertIn("lean", json.loads(out_buf.getvalue()))

                out_buf = io.StringIO()
                with mock.patch.object(verifier, "MESH_NODES", fake_nodes):
                    with redirect_stdout(out_buf):
                        rc = verifier.main(
                            ["--standalone", "--lean", str(TRACK_DIR / "HigherOrderEpistemicMesh.lean"), "--expedition-root", str(root), "--json"]
                        )
                self.assertEqual(rc, 0)
                j = json.loads(out_buf.getvalue())
                self.assertEqual(j["lean"]["theorems_verified"], len(oracle.EXPECTED_LEAN_THEOREMS))
                self.assertTrue(j["pinned_nodes"]["all_matched"])
            else:
                out_buf, err_buf = io.StringIO(), io.StringIO()
                with redirect_stdout(out_buf), redirect_stderr(err_buf):
                    rc = verifier.main(["--json"])
                self.assertEqual(rc, 1)
                self.assertIn("LEAN_BINARY_UNAVAILABLE", out_buf.getvalue())
                with mock.patch.object(verifier, "verify_lean_proof", return_value=lean_stub):
                    with mock.patch.object(verifier, "MESH_NODES", fake_nodes):
                        out_buf = io.StringIO()
                        with redirect_stdout(out_buf):
                            rc = verifier.main(
                                ["--standalone", "--lean", str(TRACK_DIR / "HigherOrderEpistemicMesh.lean"), "--expedition-root", str(root), "--json"]
                            )
                        self.assertEqual(rc, 0)
                        j = json.loads(out_buf.getvalue())
                        self.assertTrue(j["pinned_nodes"]["all_matched"])

            for argv in (
                ["--unknown"],
                ["--write"],
                ["--write", str(cert_path), "--write", str(cert_path)],
                ["--standalone", "--standalone"],
                ["--json", "--json"],
                ["--write", str(cert_path), "--check", str(cert_path)],
                ["--check", str(root / "missing.json"), "--json"],
                ["--check", str(root / "missing.json")],
            ):
                ob, eb = io.StringIO(), io.StringIO()
                with redirect_stdout(ob), redirect_stderr(eb):
                    self.assertEqual(verifier.main(argv), 1, msg=f"Expected rc=1 for {argv}")


if __name__ == "__main__":
    unittest.main()
