#!/usr/bin/env python3
"""Aletheia R5 Adversarial, Zone-B, R10+ Lean-Gate & Mutation-Killer Suite for Track S88.

Pure Python 3 stdlib only, zero bare asserts, zero AST floats, zero .isdigit(),
zero random imports, zero host-home tilde strings, CI chmod-644 and Lean-less CI compatible
(zero skipped tests in both live-Lean and Lean-less environments).
"""
from __future__ import annotations

import ast
import copy
import errno
from fractions import Fraction
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import aletheia_mesh_engine as engine  # noqa: E402
import verify_aletheia_mesh as verifier  # noqa: E402


class _IntSub(int):
    pass


class _StrSub(str):
    pass


class _ListSub(list):
    pass


class _DictSub(dict):
    pass


class _PathSub(type(Path())):
    pass


def _resign_cert(cert: dict) -> dict:
    c = copy.deepcopy(cert)
    an_wrap = c["payload"]["s83_k8_live_analysis"]
    if type(an_wrap) is dict and "analysis" in an_wrap and type(an_wrap["analysis"]) is dict:
        an_wrap["analysis_sha256"] = engine.sha256_hex(engine.canonical_json_bytes(an_wrap["analysis"]))
    p_sha = engine.sha256_hex(engine.canonical_json_bytes(c["payload"]))
    c["payload_sha256"] = p_sha
    env = {
        "schema_version": c["schema_version"],
        "track_id": c["track_id"],
        "payload_sha256": p_sha,
        "payload": c["payload"],
    }
    c["certificate_sha256"] = engine.sha256_hex(engine.canonical_json_bytes(env))
    return c


class Test01StaticHygieneAndTest28Safety(unittest.TestCase):
    def test_ast_and_text_hygiene(self) -> None:
        bad_r4_re = re.compile(
            r"(?i)" + "4" + "-mode|all " + "four (?:isolated|python|execution)|" + "four " + "isolated"
        )
        for fname in (
            "aletheia_mesh_engine.py",
            "verify_aletheia_mesh.py",
            "test_s88_aletheia_mesh_r5.py",
        ):
            raw = (_THIS_DIR / fname).read_bytes()
            self.assertNotIn(b"\r", raw, fname)
            src = raw.decode("utf-8", "strict")
            self.assertNotIn("/" + "home/", src, fname)
            self.assertNotIn("/dev/" + "null", src, fname)
            self.assertNotIn("~" + "/", src, fname)
            self.assertIsNone(bad_r4_re.search(src), fname)
            tree = ast.parse(src, filename=fname)
            for node in ast.walk(tree):
                self.assertNotIsInstance(node, ast.Assert, fname)
                if isinstance(node, ast.Constant):
                    self.assertNotIsInstance(node.value, float, fname)
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        self.assertNotIn(node.func.id, ("float", "eval", "exec"), fname)
                    if isinstance(node.func, ast.Attribute):
                        self.assertNotEqual(node.func.attr, "isdigit", fname)
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotEqual(alias.name, "random", fname)
                if isinstance(node, ast.ImportFrom):
                    self.assertNotEqual(node.module, "random", fname)

    def test_disk_certificate_strict_zero_float_canonical(self) -> None:
        raw = verifier.read_regular_bytes_capped(_THIS_DIR / "s88_aletheia_mesh_certificate.json", "cert")
        obj = verifier.parse_strict_json_bytes(raw, "cert", require_canonical=True)
        self.assertIs(type(obj), dict)


class Test02EnginePrimitivesAndMeshMath(unittest.TestCase):
    def _assert_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(engine.MeshError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_type_guards_and_json_tree(self) -> None:
        self.assertIs(engine.require_bool(True, "b"), True)
        self.assertIs(engine.require_bool(False, "b"), False)
        for bad in (0, 1, "true", None):
            self._assert_err("INVALID_BOOL", engine.require_bool, bad, "b")

        self.assertEqual(engine.require_exact_int(5, "x", lo=5, hi=5), 5)
        self._assert_err("INVALID_INT", engine.require_exact_int, True, "x")
        self._assert_err("INVALID_INT", engine.require_exact_int, _IntSub(5), "x")
        self._assert_err("INT_OUT_OF_RANGE", engine.require_exact_int, 4, "x", lo=5)
        self._assert_err("INT_OUT_OF_RANGE", engine.require_exact_int, 6, "x", hi=5)
        big_ok = (1 << engine.MAX_INT_BITS) - 1
        self.assertEqual(engine.require_exact_int(big_ok, "x"), big_ok)
        self._assert_err("INT_TOO_LARGE", engine.require_exact_int, 1 << engine.MAX_INT_BITS, "x")

        self.assertEqual(engine.require_exact_str("abc", "s"), "abc")
        self._assert_err("INVALID_STR", engine.require_exact_str, _StrSub("a"), "s")
        self._assert_err("INVALID_UTF8_SURROGATE", engine.require_exact_str, "\ud800", "s")

        h64 = "0123456789abcdef" * 4
        self.assertEqual(engine.require_hex64(h64, "h"), h64)
        self._assert_err("INVALID_HEX64", engine.require_hex64, h64[:-1], "h")
        self._assert_err("INVALID_HEX64", engine.require_hex64, "A" + h64[1:], "h")

        self.assertTrue(engine.is_ascii_digits("0123456789"))
        self.assertFalse(engine.is_ascii_digits(""))
        self.assertFalse(engine.is_ascii_digits("12a"))
        self.assertFalse(engine.is_ascii_digits("\u00b2"))

        shared = [1, 2]
        engine.validate_strict_json_tree({"a": shared, "b": shared, "n": None, "t": True, "s": "ok"})
        nested: list = []
        cur = nested
        for _ in range(engine.MAX_JSON_DEPTH):
            nxt: list = []
            cur.append(nxt)
            cur = nxt
        engine.validate_strict_json_tree(nested)
        cur.append(0)
        self._assert_err("JSON_DEPTH_EXCEEDED", engine.validate_strict_json_tree, nested)
        engine.validate_strict_json_tree((1 << engine.MAX_INT_BITS) - 1)
        self._assert_err("INT_TOO_LARGE", engine.validate_strict_json_tree, 1 << engine.MAX_INT_BITS)
        cyc_l: list = []
        cyc_l.append(cyc_l)
        self._assert_err("JSON_CYCLE", engine.validate_strict_json_tree, cyc_l)
        cyc_d: dict = {}
        cyc_d["self"] = cyc_d
        self._assert_err("JSON_CYCLE", engine.validate_strict_json_tree, cyc_d)
        self._assert_err("INVALID_UTF8_SURROGATE", engine.validate_strict_json_tree, {"k": "\ud800"})
        self._assert_err("INVALID_STR", engine.validate_strict_json_tree, {1: "a"})
        for bad in ((1, 2), b"abc", _IntSub(1), _StrSub("a"), _ListSub([1]), _DictSub({"a": 1})):
            self._assert_err("INVALID_JSON_TYPE", engine.validate_strict_json_tree, bad)

    def test_linear_algebra_formatting_and_combinatorics(self) -> None:
        self.assertEqual(engine.q_str(Fraction(4, 1)), "4")
        self.assertEqual(engine.q_str(Fraction(-3, 2)), "-3/2")
        self.assertEqual(engine.dec_from_q(Fraction(1, 200), 2), "0.01")
        self.assertEqual(engine.dec_from_q(Fraction(1, 300), 2), "0.00")
        self.assertEqual(engine.dec_from_q(Fraction(-1, 1000), 2), "0.00")
        self.assertEqual(engine.dec_from_q(Fraction(-3, 200), 2), "-0.02")
        self.assertEqual(engine.dec_from_q(Fraction(5, 2), 0), "3")
        self.assertEqual(engine.dec_from_q(Fraction(-5, 2), 0), "-3")
        self.assertEqual(engine.comb_k(8, -1), 0)
        self.assertEqual(engine.comb_k(4, 5), 0)
        self.assertEqual(engine.comb_k(8, 0), 1)
        self.assertEqual(engine.comb_k(16, 5), 4368)

        swap_m = [[Fraction(0), Fraction(2)], [Fraction(3), Fraction(1)]]
        self.assertEqual(engine.q_solve(swap_m, [[Fraction(4)], [Fraction(5)]]), [[Fraction(1)], [Fraction(2)]])
        self.assertEqual(engine.q_det(swap_m), Fraction(-6))
        sing_m = [[Fraction(1), Fraction(2)], [Fraction(2), Fraction(4)]]
        self._assert_err("SINGULAR_MATRIX", engine.q_solve, sing_m, [[Fraction(1)], [Fraction(2)]])
        self.assertEqual(engine.q_det(sing_m), Fraction(0))

        diag_swap = [
            [Fraction(0), Fraction(0), Fraction(0)],
            [Fraction(0), Fraction(3), Fraction(0)],
            [Fraction(0), Fraction(0), Fraction(-2)],
        ]
        self.assertEqual(engine.q_sylvester_inertia(diag_swap), [1, 1, 1])
        off_4 = [
            [Fraction(0), Fraction(0), Fraction(0), Fraction(0)],
            [Fraction(0), Fraction(0), Fraction(0), Fraction(2)],
            [Fraction(0), Fraction(0), Fraction(0), Fraction(1)],
            [Fraction(0), Fraction(2), Fraction(1), Fraction(0)],
        ]
        self.assertEqual(engine.q_sylvester_inertia(off_4), [1, 1, 2])
        off_full = [
            [Fraction(0), Fraction(0), Fraction(1), Fraction(2)],
            [Fraction(0), Fraction(0), Fraction(2), Fraction(1)],
            [Fraction(1), Fraction(2), Fraction(0), Fraction(0)],
            [Fraction(2), Fraction(1), Fraction(0), Fraction(0)],
        ]
        self.assertEqual(engine.q_sylvester_inertia(off_full), [2, 2, 0])
        self.assertEqual(engine.q_sylvester_inertia(engine.q_zeros(3, 3)), [0, 0, 3])

    def test_mesh_parser_s83_generic_balanced_and_rejections(self) -> None:
        # Generic balanced K_4 (0 obstructions -> exercises non-frustrated T_2 and empty T_3!)
        bal_spec = engine.build_parametric_kn_spec(4)
        for e in bal_spec["edges"]:
            e["pathway_class"] = "EXACT_COMMUTE"
            e["weight_q"] = "4"
        bal_res = engine.analyze_mesh_full(bal_spec, spectral_steps=6)["analysis"]
        self.assertFalse(bal_res["t2_signed_frustration_double_cover"]["is_frustrated"])
        self.assertEqual(bal_res["t2_signed_frustration_double_cover"]["signed_laplacian_det_q"], "0")
        self.assertFalse(bal_res["t2_signed_frustration_double_cover"]["double_cover_connected"])
        self.assertEqual(bal_res["t2_signed_frustration_double_cover"]["double_cover_inertia"], [6, 0, 2])
        self.assertEqual(bal_res["t3_auto_blowup_ranker"]["n_obstruction_candidates"], 0)
        self.assertFalse(bal_res["t3_auto_blowup_ranker"]["pareto_multi_wall_obstruction_detected"])
        self.assertEqual(bal_res["higher_order_convergence"]["order3_tetrahedra"]["all_commute_k4_count"], 1)

        # Single-wall K_4 (blowing up the 1 wall makes signed Laplacian balanced/singular -> exercises T_3 else branch!)
        k4_spec = engine.build_parametric_kn_spec(4)
        k4_spec["edges"][0]["weight_q"] = "3/2"  # exercises fractional canonical weight parser!
        k4_res = engine.analyze_mesh_full(k4_spec, spectral_steps=6)["analysis"]
        self.assertEqual(k4_res["t3_auto_blowup_ranker"]["ranked_unlocks"][0]["signed_det_after_q"], "0")
        self.assertEqual(k4_res["t3_auto_blowup_ranker"]["ranked_unlocks"][0]["signed_lambda1_after_bracket_dec4"], ["0.0000", "0.0000"])

        # Reversed edge ordering (u > v) in generic & S83 specs
        rev_spec = engine.build_parametric_kn_spec(4)
        rev_spec["edges"][0]["u"], rev_spec["edges"][0]["v"] = rev_spec["edges"][0]["v"], rev_spec["edges"][0]["u"]
        self.assertEqual(engine.parse_mesh_spec(rev_spec)["n"], 4)

        # S83 format parser (synthetic valid S83 cert)
        s83_like = {
            "schema_version": engine.S83_CERT_SCHEMA,
            "payload": {
                "mesh_nodes": [{"id": f"v{i}"} for i in range(4)],
                "pillar1_schur_compounding": {
                    "pair_rows": [
                        {
                            "pair": f"{e['v']}-{e['u']}" if idx == 0 else f"{e['u']}-{e['v']}",
                            "pathway_class": e["pathway_class"],
                            "operator_tag": e["operator_tag"],
                            "direct_w_q": e["weight_q"],
                        }
                        for idx, e in enumerate(engine.build_parametric_kn_spec(4)["edges"])
                    ]
                },
            },
        }
        self.assertEqual(engine.parse_mesh_spec(s83_like)["n"], 4)

        # S83 format at exact upper bound n == MAX_MESH_NODES (16)
        k16_spec = engine.build_parametric_kn_spec(engine.MAX_MESH_NODES)
        s83_k16 = {
            "schema_version": engine.S83_CERT_SCHEMA,
            "payload": {
                "mesh_nodes": [{"id": f"v{i}"} for i in range(engine.MAX_MESH_NODES)],
                "pillar1_schur_compounding": {
                    "pair_rows": [
                        {
                            "pair": f"{e['u']}-{e['v']}",
                            "pathway_class": e["pathway_class"],
                            "operator_tag": e["operator_tag"],
                            "direct_w_q": e["weight_q"],
                        }
                        for e in k16_spec["edges"]
                    ]
                },
            },
        }
        self.assertEqual(engine.parse_mesh_spec(s83_k16)["n"], engine.MAX_MESH_NODES)

        # Parser fail-closed rejections (covering every single BoolOp sub-clause!)
        self._assert_err("INVALID_MESH_SPEC", engine.parse_mesh_spec, [])
        self._assert_err("UNSUPPORTED_MESH_SCHEMA", engine.parse_mesh_spec, {"schema_version": "bad"})
        self._assert_err("INVALID_S83_CERT", engine.parse_mesh_spec, {"schema_version": engine.S83_CERT_SCHEMA, "payload": []})
        self._assert_err("INVALID_S83_CERT", engine.parse_mesh_spec, {"schema_version": engine.S83_CERT_SCHEMA, "payload": {"mesh_nodes": [], "pillar1_schur_compounding": []}})
        self._assert_err("INVALID_S83_CERT", engine.parse_mesh_spec, {"schema_version": engine.S83_CERT_SCHEMA, "payload": {"mesh_nodes": "bad", "pillar1_schur_compounding": {"pair_rows": []}}})
        self._assert_err("INVALID_S83_CERT", engine.parse_mesh_spec, {"schema_version": engine.S83_CERT_SCHEMA, "payload": {"mesh_nodes": [], "pillar1_schur_compounding": {"pair_rows": "no"}}})

        bad_s83 = copy.deepcopy(s83_like)
        bad_s83["payload"]["mesh_nodes"][0] = "bad"
        self._assert_err("INVALID_NODE", engine.parse_mesh_spec, bad_s83)
        bad_s83 = copy.deepcopy(s83_like)
        bad_s83["payload"]["mesh_nodes"][1]["id"] = "v0"
        self._assert_err("DUPLICATE_NODE", engine.parse_mesh_spec, bad_s83)
        bad_s83 = copy.deepcopy(s83_like)
        bad_s83["payload"]["mesh_nodes"] = [{"id": "v0"}, {"id": "v1"}, {"id": "v2"}]
        self._assert_err("INVALID_NODE_COUNT", engine.parse_mesh_spec, bad_s83)
        bad_s83 = copy.deepcopy(s83_like)
        bad_s83["payload"]["pillar1_schur_compounding"]["pair_rows"][0] = "bad"
        self._assert_err("INVALID_EDGE", engine.parse_mesh_spec, bad_s83)
        for bad_pair in ("v0-v9", "v9-v0", "v0-v1-v2"):
            bad_s83 = copy.deepcopy(s83_like)
            bad_s83["payload"]["pillar1_schur_compounding"]["pair_rows"][0]["pair"] = bad_pair
            self._assert_err("INVALID_EDGE_PAIR", engine.parse_mesh_spec, bad_s83)
        bad_s83 = copy.deepcopy(s83_like)
        bad_s83["payload"]["pillar1_schur_compounding"]["pair_rows"][0]["pair"] = "v0-v0"
        self._assert_err("SELF_LOOP_FORBIDDEN", engine.parse_mesh_spec, bad_s83)
        bad_s83 = copy.deepcopy(s83_like)
        bad_s83["payload"]["pillar1_schur_compounding"]["pair_rows"][1]["pair"] = "v0-v1"
        self._assert_err("DUPLICATE_EDGE", engine.parse_mesh_spec, bad_s83)
        bad_s83 = copy.deepcopy(s83_like)
        bad_s83["payload"]["pillar1_schur_compounding"]["pair_rows"][0]["pathway_class"] = "BAD"
        self._assert_err("INVALID_PATHWAY_CLASS", engine.parse_mesh_spec, bad_s83)
        bad_s83 = copy.deepcopy(s83_like)
        bad_s83["payload"]["pillar1_schur_compounding"]["pair_rows"].pop()
        self._assert_err("INCOMPLETE_MESH", engine.parse_mesh_spec, bad_s83)

        # Generic spec rejections + weight parser edges
        self._assert_err("INVALID_MESH_SPEC", engine.parse_mesh_spec, {"schema_version": engine.MESH_SPEC_SCHEMA, "mesh_id": "m", "nodes": "no", "edges": []})
        self._assert_err("INVALID_MESH_SPEC", engine.parse_mesh_spec, {"schema_version": engine.MESH_SPEC_SCHEMA, "mesh_id": "m", "nodes": [], "edges": "no"})
        bad_g = engine.build_parametric_kn_spec(4)
        bad_g["nodes"][0] = "x"
        self._assert_err("INVALID_NODE", engine.parse_mesh_spec, bad_g)
        bad_g = engine.build_parametric_kn_spec(4)
        bad_g["nodes"][1]["id"] = "v0"
        self._assert_err("DUPLICATE_NODE", engine.parse_mesh_spec, bad_g)
        bad_g = engine.build_parametric_kn_spec(4)
        bad_g["nodes"].pop()
        self._assert_err("INVALID_NODE_COUNT", engine.parse_mesh_spec, bad_g)
        bad_g = engine.build_parametric_kn_spec(4)
        bad_g["edges"][0] = "x"
        self._assert_err("INVALID_EDGE", engine.parse_mesh_spec, bad_g)
        for bu, bv in (("v0", "v0"), ("v9", "v0"), ("v0", "v9")):
            bad_g = engine.build_parametric_kn_spec(4)
            bad_g["edges"][0]["u"], bad_g["edges"][0]["v"] = bu, bv
            self._assert_err("INVALID_EDGE_PAIR", engine.parse_mesh_spec, bad_g)
        bad_g = engine.build_parametric_kn_spec(4)
        bad_g["edges"][1]["u"], bad_g["edges"][1]["v"] = "v0", "v1"
        self._assert_err("DUPLICATE_EDGE", engine.parse_mesh_spec, bad_g)
        bad_g = engine.build_parametric_kn_spec(4)
        bad_g["edges"][0]["pathway_class"] = "NOPE"
        self._assert_err("INVALID_PATHWAY_CLASS", engine.parse_mesh_spec, bad_g)
        bad_g = engine.build_parametric_kn_spec(4)
        bad_g["edges"].pop()
        self._assert_err("INCOMPLETE_MESH", engine.parse_mesh_spec, bad_g)

        for bad_w, code in (
            ("", "INVALID_WEIGHT"),
            ("0", "INVALID_WEIGHT"),
            ("abc", "INVALID_WEIGHT"),
            ("1/2/3", "INVALID_WEIGHT"),
            ("a/2", "INVALID_WEIGHT"),
            ("1/b", "INVALID_WEIGHT"),
            ("0/2", "INVALID_WEIGHT"),
            ("2/1", "INVALID_WEIGHT"),
            ("2/4", "NONCANONICAL_WEIGHT"),
        ):
            self._assert_err(code, engine._parse_pos_q_str, bad_w, "w")

        # Direct single-clause BoolOp tests for all exported engine invariant checkers
        self.assertTrue(engine.check_triangle_strict_ineq(Fraction(2), Fraction(2), Fraction(3)))
        self.assertFalse(engine.check_triangle_strict_ineq(Fraction(2), Fraction(2), Fraction(4)))
        self.assertFalse(engine.check_triangle_strict_ineq(Fraction(4), Fraction(2), Fraction(2)))
        self.assertFalse(engine.check_triangle_strict_ineq(Fraction(2), Fraction(4), Fraction(2)))
        self.assertTrue(engine.check_hodge_reconstruction(True, Fraction(1), Fraction(2), Fraction(3)))
        self.assertFalse(engine.check_hodge_reconstruction(False, Fraction(1), Fraction(2), Fraction(3)))
        self.assertFalse(engine.check_hodge_reconstruction(True, Fraction(1), Fraction(2), Fraction(4)))
        self.assertTrue(engine.check_borromean_3body([0, 0, 3], [2, 0, 1]))
        self.assertFalse(engine.check_borromean_3body([1, 0, 2], [2, 0, 1]))
        self.assertFalse(engine.check_borromean_3body([0, 0, 3], [1, 0, 2]))
        self.assertTrue(engine.check_borromean_4way(14, True, [0, 0, 4], [3, 0, 1]))
        self.assertFalse(engine.check_borromean_4way(13, True, [0, 0, 4], [3, 0, 1]))
        self.assertFalse(engine.check_borromean_4way(14, False, [0, 0, 4], [3, 0, 1]))
        self.assertFalse(engine.check_borromean_4way(14, True, [1, 0, 3], [3, 0, 1]))
        self.assertFalse(engine.check_borromean_4way(14, True, [0, 0, 4], [2, 0, 2]))
        self.assertTrue(engine.check_three_regime_curvature(Fraction(-1, 4), Fraction(0), Fraction(1, 2)))
        self.assertFalse(engine.check_three_regime_curvature(Fraction(0), Fraction(0), Fraction(1, 2)))
        self.assertFalse(engine.check_three_regime_curvature(Fraction(-1, 4), Fraction(1), Fraction(1, 2)))
        self.assertFalse(engine.check_three_regime_curvature(Fraction(-1, 4), Fraction(0), Fraction(0)))
        self.assertTrue(engine.check_firewall_zero_flux("0", True))
        self.assertFalse(engine.check_firewall_zero_flux("1", True))
        self.assertFalse(engine.check_firewall_zero_flux("0", False))

        # Firewall compromised == anchor rejection
        norm4 = engine.parse_mesh_spec(engine.build_parametric_kn_spec(4))
        self._assert_err("INVALID_FIREWALL_NODES", engine.simulate_law3_contagion_firewall, norm4, compromised=0, anchor=0)
        # Firewall with anchor > compromised (tests pair ordering branch)
        fw_rev = engine.simulate_law3_contagion_firewall(norm4, compromised=0, anchor=2)
        self.assertTrue(fw_rev["flux_equals_schur_g_eff"])

        # Parametric bounds
        self._assert_err("INT_OUT_OF_RANGE", engine.build_parametric_kn_spec, 3)
        self._assert_err("INT_OUT_OF_RANGE", engine.build_parametric_kn_spec, 17)
        self.assertEqual(engine.build_parametric_kn_spec(8)["mesh_id"], "parametric_k8_mesh")
        self.assertEqual(engine.build_parametric_kn_spec(12)["mesh_id"], "parametric_k12_mesh")

        # Non-exact-compounded edge case (extreme weight imbalance where gain <= 1 impossible in connected positive graph,
        # so exercise _classify_triangle directly across all 4 classes)
        self.assertEqual(engine._classify_triangle(3, 0), ("EXACT_TRANSITIVE_CLOSURE", 0))
        self.assertEqual(engine._classify_triangle(2, 0), ("CONDITIONAL_COMPOUNDING_CLOSURE", 0))
        self.assertEqual(engine._classify_triangle(2, 1), ("FRUSTRATED_CURVATURE_LOOP", 1))
        self.assertEqual(engine._classify_triangle(0, 2), ("MULTI_WALL_BOUNDARY_SECTOR", 0))

    def test_s83_k8_live_numbers_and_parametric_k16(self) -> None:
        cert = engine.build_s88_certificate()
        an = cert["payload"]["s83_k8_live_analysis"]["analysis"]
        o1 = an["higher_order_convergence"]["order1_schur"]
        self.assertEqual(o1["foster_sum_q"], "7")
        self.assertEqual(o1["laplacian_inertia"], [7, 0, 1])
        self.assertEqual(o1["resistance_triangle_inequalities_verified"], 168)
        self.assertTrue(o1["all_pairs_strictly_compounded"])
        o2 = an["higher_order_convergence"]["order2_triangles"]
        self.assertEqual(o2["odd_z2_holonomy_triangles"], 22)
        self.assertEqual(o2["even_z2_holonomy_triangles"], 34)
        o3 = an["higher_order_convergence"]["order3_tetrahedra"]
        self.assertEqual(o3["frustrated_face_distribution"], {"0": 20, "1": 0, "2": 45, "3": 0, "4": 5})
        self.assertTrue(o3["bianchi_coboundary_zero_all"])
        o4 = an["higher_order_convergence"]["order4_five_cells_and_silo_cuts"]
        self.assertEqual(o4["zero_obstruction_five_cells"], 4)
        self.assertEqual(o4["silo_cut_curves"]["4|4"]["k5"]["destroyed"], 56)
        t1 = an["t1_line_graph_hodge"]
        self.assertEqual(t1["obstruction_grad_energy_q"], "13/4")
        self.assertEqual(t1["obstruction_curl_energy_q"], "11/4")
        self.assertEqual(t1["same_tag_disjoint_functor_bridges"], 18)
        t2 = an["t2_signed_frustration_double_cover"]
        self.assertEqual(t2["signed_laplacian_det_q"], "1841101056")
        self.assertEqual(t2["lifted_closed_triangles"], 68)
        self.assertEqual(t2["lifted_open_6cycles"], 22)
        t3 = an["t3_auto_blowup_ranker"]
        self.assertEqual(t3["top_frustration_unlock_pair"], "v6-v7")
        self.assertEqual(t3["top_conductance_unlock_pair"], "v2-v4")
        self.assertEqual(t3["top_lambda2_unlock_pair"], "v1-v4")
        self.assertTrue(t3["pareto_multi_wall_obstruction_detected"])
        self.assertEqual(t3["ranked_unlocks"][0]["net_frustrated_delta"], -6)
        self.assertEqual(t3["ranked_unlocks"][5]["net_frustrated_delta"], 2)
        t6 = an["t6_kron_coarsening_and_curvature"]
        self.assertEqual(t6["r_eff_gram_det_q"], "3218/7036691")
        self.assertTrue(t6["all_kept_pairs_r_eff_exact_invariant"])
        self.assertTrue(t6["three_regime_curvature_separated"])
        # Parametric K_16 8|8 split
        k16_row = cert["payload"]["parametric_scaling_summary"][2]
        self.assertEqual(k16_row["balanced_silo_cut"]["k2"]["destroyed"], 64)
        self.assertEqual(k16_row["balanced_silo_cut"]["k3"]["destroyed"], 448)
        self.assertEqual(k16_row["balanced_silo_cut"]["k4"]["destroyed"], 1680)
        self.assertEqual(k16_row["balanced_silo_cut"]["k5"]["destroyed"], 4256)


class Test03ZoneBIOAndParsers(unittest.TestCase):
    def _assert_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(engine.MeshError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_path_and_darwin_normalization(self) -> None:
        self._assert_err("INVALID_PATH_TYPE", verifier._require_concrete_path, "/tmp/a", "p")
        self._assert_err("INVALID_PATH_TYPE", verifier._require_concrete_path, _PathSub("/tmp/a"), "p")
        self._assert_err("INVALID_UTF8_SURROGATE", verifier._require_concrete_path, Path("/tmp/\ud800"), "p")
        self._assert_err("NUL_BYTE_FORBIDDEN", verifier._require_concrete_path, Path("/tmp/a\x00b"), "p")

        fake_lnk = os.stat_result((stat.S_IFLNK | 0o777, 1, 1, 1, 0, 0, 0, 0, 0, 0))
        fake_nonroot = os.stat_result((stat.S_IFLNK | 0o777, 1, 1, 1, 1000, 0, 0, 0, 0, 0))
        fake_dir = os.stat_result((stat.S_IFDIR | 0o755, 1, 1, 1, 0, 0, 0, 0, 0, 0))

        with mock.patch.object(verifier.sys, "platform", "linux"), mock.patch.object(
            verifier.os, "lstat", return_value=fake_lnk
        ), mock.patch.object(verifier.os, "readlink", return_value="private/tmp"):
            self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/tmp/a")), Path("/tmp/a"))

        with mock.patch.object(verifier.sys, "platform", "darwin"):
            self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/opt/a")), Path("/opt/a"))
            with mock.patch.object(verifier.os, "lstat", return_value=fake_lnk), mock.patch.object(
                verifier.os, "readlink", return_value="private/tmp"
            ):
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("x/tmp/a")), Path("x/tmp/a"))
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/tmp")), Path("/tmp"))
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/tmp/../a")), Path("/tmp/../a"))
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/tmp/a")), Path("/private/tmp/a"))
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/tmp"), allow_exact=True), Path("/private/tmp"))
            with mock.patch.object(verifier.os, "lstat", return_value=fake_dir), mock.patch.object(
                verifier.os, "readlink", return_value="private/tmp"
            ):
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/tmp/a")), Path("/tmp/a"))
            with mock.patch.object(verifier.os, "lstat", return_value=fake_nonroot), mock.patch.object(
                verifier.os, "readlink", return_value="private/tmp"
            ):
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/tmp/a")), Path("/tmp/a"))
            with mock.patch.object(verifier.os, "lstat", return_value=fake_lnk), mock.patch.object(
                verifier.os, "readlink", return_value="/other"
            ):
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/tmp/a")), Path("/tmp/a"))
            with mock.patch.object(verifier.os, "lstat", side_effect=OSError("no")):
                self.assertEqual(verifier._normalize_darwin_system_prefix(Path("/tmp/a")), Path("/tmp/a"))

    def test_pwd_symlink_and_safe_cwd_guards(self) -> None:
        with mock.patch.object(verifier.Path, "cwd", side_effect=OSError("gone")):
            self._assert_err("CWD_UNAVAILABLE", verifier._safe_cwd, "c")

        with mock.patch.dict(os.environ, {"PWD": "relative"}):
            verifier._check_pwd_no_symlinks("c")
        with mock.patch.object(verifier.os, "environ", {"PWD": "/tmp/a\x00b"}):
            self._assert_err("NUL_BYTE_FORBIDDEN", verifier._check_pwd_no_symlinks, "c")

        with tempfile.TemporaryDirectory() as td:
            real_d = Path(td) / "real"
            real_d.mkdir(mode=0o700)
            sym_d = Path(td) / "sym"
            os.symlink(real_d, sym_d)
            old_cwd = Path.cwd()
            try:
                os.chdir(real_d)
                with mock.patch.dict(os.environ, {"PWD": str(sym_d)}):
                    self._assert_err("SYMLINK_ANCESTOR_FORBIDDEN", verifier._check_pwd_no_symlinks, "c")
                with mock.patch.dict(os.environ, {"PWD": str(Path(td) / "nonexistent")}):
                    verifier._check_pwd_no_symlinks("c")
                other_d = Path(td) / "other"
                other_d.mkdir(mode=0o700)
                with mock.patch.dict(os.environ, {"PWD": str(other_d)}):
                    verifier._check_pwd_no_symlinks("c")
                with mock.patch.dict(os.environ, {"PWD": str(real_d)}), mock.patch.object(
                    verifier.os, "open", side_effect=OSError(errno.EACCES, "denied")
                ):
                    self._assert_err("CWD_UNAVAILABLE", verifier._check_pwd_no_symlinks, "c")
                orig_open = os.open

                def fail_second(path, flags, *a, **kw):
                    if path != "/":
                        raise OSError(errno.EACCES, "denied")
                    return orig_open(path, flags, *a, **kw)

                with mock.patch.dict(os.environ, {"PWD": str(real_d)}), mock.patch.object(
                    verifier.os, "open", side_effect=fail_second
                ):
                    self._assert_err("CWD_UNAVAILABLE", verifier._check_pwd_no_symlinks, "c")
            finally:
                os.chdir(old_cwd)

    def test_read_and_write_safe_io_traps(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            reg = base / "data.bin"
            verifier.write_regular_bytes_safe(reg, b"hello", "reg")
            self.assertEqual(stat.S_IMODE(os.lstat(reg).st_mode), 0o600)
            self.assertEqual(verifier.read_regular_bytes_capped(reg, "reg", max_bytes=5), b"hello")
            with self.assertRaises(engine.MeshError) as ctx_sz:
                verifier.read_regular_bytes_capped(reg, "reg", max_bytes=4)
            self.assertEqual(ctx_sz.exception.code, "FILE_TOO_LARGE")
            self.assertIn("size exceeds cap", ctx_sz.exception.detail)

            # Relative path read/write + nested parent creation
            old_cwd = Path.cwd()
            try:
                os.chdir(base)
                with mock.patch.dict(os.environ, {"PWD": str(base)}):
                    verifier.write_regular_bytes_safe(Path("sub/nested/out.bin"), b"xy", "nest")
                    self.assertEqual(verifier.read_regular_bytes_capped(Path("sub/nested/out.bin"), "nest"), b"xy")
            finally:
                os.chdir(old_cwd)

            # Symlink leaf, symlink ancestor, FIFO, hardlink, directory leaf, root, ..
            sym_leaf = base / "sym.bin"
            os.symlink(reg, sym_leaf)
            self._assert_err("SYMLINK_FORBIDDEN", verifier.read_regular_bytes_capped, sym_leaf, "sl")
            self._assert_err("SYMLINK_FORBIDDEN", verifier.write_regular_bytes_safe, sym_leaf, b"x", "sl")

            real_sub = base / "rsub"
            real_sub.mkdir(mode=0o700)
            sym_sub = base / "ssub"
            os.symlink(real_sub, sym_sub)
            self._assert_err("SYMLINK_FORBIDDEN", verifier.read_regular_bytes_capped, sym_sub / "a", "sa")
            self._assert_err("SYMLINK_FORBIDDEN", verifier.write_regular_bytes_safe, sym_sub / "a", b"x", "sa")

            fifo = base / "pipe.fifo"
            os.mkfifo(fifo)
            self._assert_err("NOT_A_REGULAR_FILE", verifier.read_regular_bytes_capped, fifo, "fi")
            self._assert_err("NOT_A_REGULAR_FILE", verifier.write_regular_bytes_safe, fifo, b"x", "fi")

            hl = base / "hl.bin"
            os.link(reg, hl)
            self._assert_err("HARDLINK_FORBIDDEN", verifier.read_regular_bytes_capped, reg, "hl")
            with self.assertRaises(engine.MeshError) as ctx_hl:
                verifier.write_regular_bytes_safe(reg, b"x", "hl")
            self.assertEqual(ctx_hl.exception.code, "HARDLINK_FORBIDDEN")
            self.assertNotIn("pre-replace", ctx_hl.exception.detail)
            os.unlink(hl)

            self._assert_err("NOT_A_REGULAR_FILE", verifier.read_regular_bytes_capped, real_sub, "dir")
            self._assert_err("NOT_A_REGULAR_FILE", verifier.write_regular_bytes_safe, real_sub, b"x", "dir")
            self._assert_err("NOT_A_REGULAR_FILE", verifier.read_regular_bytes_capped, Path("/"), "root")
            with self.assertRaises(engine.MeshError) as ctx_dd:
                verifier.read_regular_bytes_capped(base / "..", "dotdot")
            self.assertEqual(ctx_dd.exception.code, "NOT_A_REGULAR_FILE")
            self.assertIn("regular file leaf", ctx_dd.exception.detail)
            self._assert_err("FILE_READ_ERROR", verifier.read_regular_bytes_capped, base / "missing.bin", "miss")
            self._assert_err("FILE_READ_ERROR", verifier.read_regular_bytes_capped, base / "nope" / "a.bin", "missd")
            self.assertFalse((base / "nope").exists())
            self._assert_err("INVALID_PAYLOAD_BYTES", verifier.write_regular_bytes_safe, reg, "notbytes", "p")

            # Mocked OSError / TOCTOU / stream growth / temp slot exhaustion branches
            with mock.patch.object(verifier.os, "open", side_effect=OSError(errno.EACCES, "root")):
                self._assert_err("FILE_READ_ERROR", verifier.read_regular_bytes_capped, reg, "r")
                self._assert_err("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, reg, b"a", "w")
            with mock.patch.object(verifier.os, "read", return_value=b"abcdef"):
                self._assert_err("FILE_TOO_LARGE", verifier.read_regular_bytes_capped, reg, "grow", max_bytes=5)
            with mock.patch.object(verifier.os, "read", side_effect=OSError("io")):
                self._assert_err("FILE_READ_ERROR", verifier.read_regular_bytes_capped, reg, "io")
            with mock.patch.object(verifier.os, "mkdir", side_effect=FileExistsError("race")):
                # mkdir FileExistsError race re-open path (fail on reopen -> FILE_WRITE_ERROR)
                self._assert_err("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, base / "raced" / "x", b"1", "rc")
            with mock.patch.object(verifier.os, "mkdir", side_effect=OSError("mk")):
                with self.assertRaises(engine.MeshError) as ctx_mk:
                    verifier.write_regular_bytes_safe(base / "mkfail" / "x", b"1", "mk")
                self.assertEqual(ctx_mk.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("mkdir failed", ctx_mk.exception.detail)
            with mock.patch.object(verifier.os, "lstat", side_effect=OSError("ls")):
                self._assert_err("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, reg, b"a", "ls")
            orig_open = os.open

            def fail_tmp(path, flags, *a, **kw):
                if isinstance(path, str) and path.startswith(".s88."):
                    raise FileExistsError("busy")
                return orig_open(path, flags, *a, **kw)

            with mock.patch.object(verifier.os, "open", side_effect=fail_tmp):
                with self.assertRaises(engine.MeshError) as ctx_sl:
                    verifier.write_regular_bytes_safe(reg, b"a", "slots")
                self.assertEqual(ctx_sl.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("temp slots exhausted", ctx_sl.exception.detail)

            def fail_tmp_os(path, flags, *a, **kw):
                if isinstance(path, str) and path.startswith(".s88."):
                    raise OSError("open_tmp")
                return orig_open(path, flags, *a, **kw)

            with mock.patch.object(verifier.os, "open", side_effect=fail_tmp_os):
                with self.assertRaises(engine.MeshError) as ctx_to:
                    verifier.write_regular_bytes_safe(reg, b"a", "to")
                self.assertEqual(ctx_to.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("temp open failed", ctx_to.exception.detail)
            with mock.patch.object(verifier.os, "write", return_value=0):
                self._assert_err("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, reg, b"a", "sw")
            with mock.patch.object(verifier.os, "write", side_effect=OSError("wr")):
                self._assert_err("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, reg, b"a", "wr")
            fake_hl_st = os.stat_result((stat.S_IFREG | 0o600, 1, 1, 2, 0, 0, 1, 0, 0, 0))
            with mock.patch.object(verifier.os, "fstat", return_value=fake_hl_st):
                self._assert_err("HARDLINK_FORBIDDEN", verifier.write_regular_bytes_safe, reg, b"a", "fhl")

            # Pre-replace lstat TOCTOU checks (second lstat returns symlink/dir/hardlink/OSError)
            orig_lstat = os.lstat
            for bad_st, exp_code in (
                (os.stat_result((stat.S_IFLNK | 0o777, 1, 1, 1, 0, 0, 0, 0, 0, 0)), "SYMLINK_FORBIDDEN"),
                (os.stat_result((stat.S_IFDIR | 0o700, 1, 1, 1, 0, 0, 0, 0, 0, 0)), "NOT_A_REGULAR_FILE"),
                (fake_hl_st, "HARDLINK_FORBIDDEN"),
                (OSError("pre"), "FILE_WRITE_ERROR"),
            ):
                calls = {"n": 0}

                def lstat_toctou(*a, **kw):
                    calls["n"] += 1
                    if calls["n"] == 2:
                        if isinstance(bad_st, BaseException):
                            raise bad_st
                        return bad_st
                    return orig_lstat(*a, **kw)

                with mock.patch.object(verifier.os, "lstat", side_effect=lstat_toctou):
                    self._assert_err(exp_code, verifier.write_regular_bytes_safe, reg, b"a", "toc")

            with mock.patch.object(verifier.os, "replace", side_effect=OSError("rep")):
                self._assert_err("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, reg, b"a", "rep")
            with mock.patch.object(verifier.os, "replace", side_effect=OSError("rep")), mock.patch.object(
                verifier.os, "unlink", side_effect=OSError("ul")
            ):
                self._assert_err("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, reg, b"a", "rep2")

    def test_strict_json_and_rational_parsers(self) -> None:
        self._assert_err("INVALID_BYTES", verifier.parse_strict_json_bytes, "str", "j")
        self._assert_err("BOM_FORBIDDEN", verifier.parse_strict_json_bytes, b"\xef\xbb\xbf{}\n", "j")
        self._assert_err("CRLF_FORBIDDEN", verifier.parse_strict_json_bytes, b"{}\r\n", "j")
        self._assert_err("INVALID_UTF8", verifier.parse_strict_json_bytes, b"\xff\n", "j")
        self._assert_err("FLOAT_FORBIDDEN", verifier.parse_strict_json_bytes, b'{"x":1.5}\n', "j")
        self._assert_err("NONFINITE_JSON_CONSTANT", verifier.parse_strict_json_bytes, b'{"x":NaN}\n', "j")
        self._assert_err("DUPLICATE_JSON_KEY", verifier.parse_strict_json_bytes, b'{"a":1,"a":2}\n', "j")
        self._assert_err("INVALID_JSON", verifier.parse_strict_json_bytes, b"{bad", "j")
        self._assert_err("INVALID_ROOT_TYPE", verifier.parse_strict_json_bytes, b"[1]\n", "j")
        self._assert_err("NONCANONICAL_JSON", verifier.parse_strict_json_bytes, b'{"b":1,"a":2}\n', "j", require_canonical=True)
        self.assertEqual(verifier.parse_strict_json_bytes(b'{"b":1,"a":2}\n', "j", require_canonical=False), {"a": 2, "b": 1})

        self._assert_err("INVALID_INT_TOKEN", verifier._parse_bounded_int, "12a")
        with self.assertRaises(engine.MeshError) as ctx_dig:
            verifier._parse_bounded_int("9" * (engine.MAX_INT_DIGITS + 1))
        self.assertEqual(ctx_dig.exception.code, "INT_TOO_LARGE")
        self.assertIn("int digits cap", ctx_dig.exception.detail)
        self._assert_err("NONCANONICAL_INT", verifier._parse_bounded_int, "01")
        self._assert_err("NONCANONICAL_INT", verifier._parse_bounded_int, "-0")
        # Exact MAX_INT_DIGITS (2467) AND exact MAX_INT_BITS (8192): 10**2466 passes; 2*10**2466 (8193 bits) fails bits!
        exact_boundary_s = "1" + "0" * (engine.MAX_INT_DIGITS - 1)
        self.assertEqual(verifier._parse_bounded_int(exact_boundary_s), 10 ** (engine.MAX_INT_DIGITS - 1))
        self.assertEqual(verifier._parse_bounded_int(str((1 << engine.MAX_INT_BITS) - 1)), (1 << engine.MAX_INT_BITS) - 1)
        with self.assertRaises(engine.MeshError) as ctx_bits:
            verifier._parse_bounded_int("2" + "0" * (engine.MAX_INT_DIGITS - 1))
        self.assertEqual(ctx_bits.exception.code, "INT_TOO_LARGE")
        self.assertIn("int bits cap", ctx_bits.exception.detail)
        self.assertEqual(verifier._parse_bounded_int("0"), 0)
        self.assertEqual(verifier._parse_bounded_int("-42"), -42)
        self._assert_err("INVALID_SCHEMA_DICT", verifier._require_exact_dict, [], frozenset({"a"}), "d")
        self._assert_err("INVALID_SCHEMA_KEYS", verifier._require_exact_dict, {"b": 1}, frozenset({"a"}), "d")

        self.assertEqual(verifier.parse_canonical_rational_str("5", "q"), Fraction(5))
        self.assertEqual(verifier.parse_canonical_rational_str("-3/4", "q"), Fraction(-3, 4))
        self._assert_err("INVALID_RATIONAL", verifier.parse_canonical_rational_str, "", "q")
        self._assert_err("INVALID_RATIONAL", verifier.parse_canonical_rational_str, "1/2/3", "q")
        self._assert_err("INVALID_RATIONAL", verifier.parse_canonical_rational_str, "1/-2", "q")
        self._assert_err("NONCANONICAL_RATIONAL", verifier.parse_canonical_rational_str, "2/1", "q")
        self._assert_err("NONCANONICAL_RATIONAL", verifier.parse_canonical_rational_str, "2/4", "q")


class Test04SecondaryAuditFullReplayAndCLI(unittest.TestCase):
    def _assert_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(engine.MeshError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def _load_cert(self) -> dict:
        raw = verifier.read_regular_bytes_capped(_THIS_DIR / "s88_aletheia_mesh_certificate.json", "cert")
        return verifier.parse_strict_json_bytes(raw, "cert", require_canonical=True)

    def test_verify_certificate_dict_and_semantic_tamper_sweep(self) -> None:
        cert = self._load_cert()
        res_fr1 = verifier.verify_certificate_dict(cert, full_replay=True)
        self.assertTrue(res_fr1["valid"] and res_fr1["full_replay"])
        res_fr0 = verifier.verify_certificate_dict(cert, full_replay=False)
        self.assertTrue(res_fr0["valid"] and not res_fr0["full_replay"])

        for bad_fr in (0, 1, "true", None):
            self._assert_err("INVALID_BOOL", verifier.verify_certificate_dict, cert, full_replay=bad_fr)
        self._assert_err("INVALID_CERT_TYPE", verifier.verify_certificate_dict, [], full_replay=False)
        self._assert_err("INVALID_PAYLOAD_TYPE", verifier.secondary_audit_payload, [])

        # Top-level schema / hash tampers
        c = copy.deepcopy(cert)
        c["schema_version"] = "bad"
        self._assert_err("SCHEMA_MISMATCH", verifier.verify_certificate_dict, c, full_replay=False)
        c = copy.deepcopy(cert)
        c["track_id"] = "bad"
        self._assert_err("SCHEMA_MISMATCH", verifier.verify_certificate_dict, c, full_replay=False)
        c = copy.deepcopy(cert)
        c["payload_sha256"] = "0" * 64
        self._assert_err("PAYLOAD_SHA_MISMATCH", verifier.verify_certificate_dict, c, full_replay=False)
        c = copy.deepcopy(cert)
        c["certificate_sha256"] = "0" * 64
        self._assert_err("CERT_SHA_MISMATCH", verifier.verify_certificate_dict, c, full_replay=False)

        # Re-signed semantic tamper sweep across EVERY section (verified under BOTH full_replay=False & secondary_audit_payload)
        def mut_check(mutator, exp_code: str) -> None:
            m = copy.deepcopy(cert)
            mutator(m["payload"])
            rs = _resign_cert(m)
            self._assert_err(exp_code, verifier.secondary_audit_payload, rs["payload"])
            self._assert_err(exp_code, verifier.verify_certificate_dict, rs, full_replay=False)

        mut_check(lambda p: p.__setitem__("schema_version", "x"), "SCHEMA_MISMATCH")
        mut_check(lambda p: p.__setitem__("track_id", "x"), "SCHEMA_MISMATCH")
        mut_check(lambda p: p.__setitem__("oracle_class", "x"), "SCHEMA_MISMATCH")
        mut_check(lambda p: p.__setitem__("novelty_classification", "N2"), "SCHEMA_MISMATCH")
        mut_check(lambda p: p["pinned_artifacts"].__setitem__("lean_source", "x.lean"), "SCHEMA_MISMATCH")
        mut_check(lambda p: p["pinned_artifacts"].__setitem__("lean_source_sha256", "0" * 64), "PINNED_SHA_MISMATCH")
        mut_check(lambda p: p["pinned_artifacts"].__setitem__("lean_toolchain_sha256", "0" * 64), "PINNED_SHA_MISMATCH")
        mut_check(lambda p: p["pinned_artifacts"].__setitem__("lakefile_sha256", "0" * 64), "PINNED_SHA_MISMATCH")
        mut_check(lambda p: p["pinned_artifacts"].__setitem__("s83_certificate_sha256", "0" * 64), "PINNED_SHA_MISMATCH")
        mut_check(lambda p: p["pinned_artifacts"].__setitem__("s83_payload_sha256", "0" * 64), "PINNED_SHA_MISMATCH")
        mut_check(lambda p: p["pinned_artifacts"].__setitem__("lean_toolchain", "bad"), "SCHEMA_MISMATCH")
        mut_check(lambda p: p["pinned_artifacts"].__setitem__("lean_theorem_names", dict.fromkeys(engine.LEAN_THEOREM_NAMES, 1)), "THEOREM_LIST_MISMATCH")
        mut_check(lambda p: p["pinned_artifacts"]["lean_theorem_names"].__setitem__(0, "bad"), "THEOREM_LIST_MISMATCH")

        # Inner analysis_sha256 mismatch (must not be re-hashed by _resign_cert)
        bad_asha = copy.deepcopy(cert)
        bad_asha["payload"]["s83_k8_live_analysis"]["analysis_sha256"] = "0" * 64
        self._assert_err("ANALYSIS_SHA_MISMATCH", verifier.secondary_audit_payload, bad_asha["payload"])

        def an(p):
            return p["s83_k8_live_analysis"]["analysis"]

        mut_check(lambda p: an(p).__setitem__("mesh_id", "wrong"), "MESH_ID_MISMATCH")
        mut_check(lambda p: an(p).__setitem__("node_ids", "v0v1v2v3"), "NODE_IDS_MISMATCH")
        mut_check(lambda p: an(p)["node_ids"].__setitem__(0, "x0"), "NODE_IDS_MISMATCH")
        # Order 1 (each sub-clause isolated so every single BoolOp clause & S88-VER-02 G1/G7 is killed!)
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("total_conductance_q", "71"), "O1_CONDUCTANCE_MISMATCH")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"]["pathway_class_counts"].__setitem__("EXACT_COMMUTE", 9), "INT_OUT_OF_RANGE")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"]["pathway_class_counts"].__setitem__("EXACT_COMMUTE", 11), "INT_OUT_OF_RANGE")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"]["pathway_class_counts"].__setitem__("CONDITIONAL_BRIDGE", 11), "INT_OUT_OF_RANGE")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"]["pathway_class_counts"].__setitem__("CONDITIONAL_BRIDGE", 13), "INT_OUT_OF_RANGE")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"]["pathway_class_counts"].__setitem__("EXACT_OBSTRUCTION", 5), "INT_OUT_OF_RANGE")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"]["pathway_class_counts"].__setitem__("EXACT_OBSTRUCTION", 7), "INT_OUT_OF_RANGE")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("min_compounding_gain_pair", 123), "INVALID_STR")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("max_compounding_gain_pair", None), "INVALID_STR")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("min_compounding_gain_pair", "BOGUS"), "O1_PAIR_INVALID")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("max_compounding_gain_pair", "BOGUS"), "O1_PAIR_INVALID")
        mut_check(
            lambda p: (
                an(p)["higher_order_convergence"]["order1_schur"].__setitem__("min_compounding_gain_pair", "v1-v2"),
                an(p)["higher_order_convergence"]["order1_schur"].__setitem__("max_compounding_gain_pair", "v1-v2"),
            ),
            "O1_PAIR_INVALID",
        )
        mut_check(
            lambda p: (
                an(p)["higher_order_convergence"]["order1_schur"].__setitem__("min_compounding_gain_pair", "BOGUS"),
                an(p)["higher_order_convergence"]["order1_schur"].__setitem__("max_compounding_gain_pair", "BOGUS"),
            ),
            "O1_PAIR_INVALID",
        )
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("laplacian_inertia", [6, 1, 1]), "INERTIA_MISMATCH")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("laplacian_inertia", [7, 0]), "INVALID_INERTIA")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("laplacian_inertia", "abc"), "INVALID_INERTIA")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("foster_sum_q", "6"), "O1_ALGEBRA_FAIL")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("foster_identity_exact", False), "O1_ALGEBRA_FAIL")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("all_pairs_strictly_compounded", False), "O1_ALGEBRA_FAIL")
        mut_check(
            lambda p: (
                an(p)["higher_order_convergence"]["order1_schur"].__setitem__("min_compounding_gain_q", "1"),
                an(p)["higher_order_convergence"]["order1_schur"].__setitem__("min_compounding_gain_dec4", "1.0000"),
            ),
            "O1_ALGEBRA_FAIL",
        )
        mut_check(
            lambda p: (
                an(p)["higher_order_convergence"]["order1_schur"].__setitem__("max_compounding_gain_q", "20"),
                an(p)["higher_order_convergence"]["order1_schur"].__setitem__("max_compounding_gain_dec4", "20.0000"),
            ),
            "O1_ALGEBRA_FAIL",
        )
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("min_compounding_gain_dec4", "9.9999"), "O1_ALGEBRA_FAIL")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("max_compounding_gain_dec4", "9.9999"), "O1_ALGEBRA_FAIL")
        mut_check(
            lambda p: (
                an(p)["higher_order_convergence"]["order1_schur"].__setitem__("total_effective_conductance_q", "0"),
                an(p)["higher_order_convergence"]["order1_schur"].__setitem__("total_effective_conductance_dec4", "0.0000"),
            ),
            "O1_ALGEBRA_FAIL",
        )
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("total_effective_conductance_dec4", "0.0000"), "O1_ALGEBRA_FAIL")
        mut_check(
            lambda p: (
                an(p)["higher_order_convergence"]["order1_schur"].__setitem__("kirchhoff_index_q", "999"),
                an(p)["higher_order_convergence"]["order1_schur"].__setitem__("kirchhoff_index_dec4", "999.0000"),
            ),
            "O1_ALGEBRA_FAIL",
        )
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("kirchhoff_index_dec4", "0.0000"), "O1_ALGEBRA_FAIL")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("lambda2_bracket_q", ["1"]), "INVALID_BRACKET")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("lambda2_bracket_q", "12"), "INVALID_BRACKET")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("lambda2_bracket_dec4", ["1.0000"]), "INVALID_BRACKET")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("lambda2_bracket_dec4", "12"), "INVALID_BRACKET")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("lambda2_bracket_q", ["0", "1"]), "INVALID_BRACKET_RANGE")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("lambda2_bracket_q", ["5", "4"]), "INVALID_BRACKET_RANGE")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"]["lambda2_bracket_dec4"].__setitem__(0, "0.0000"), "BRACKET_DEC_MISMATCH")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"]["lambda2_bracket_dec4"].__setitem__(1, "0.0000"), "BRACKET_DEC_MISMATCH")
        mut_check(
            lambda p: (
                an(p)["higher_order_convergence"]["order1_schur"].__setitem__("lambda2_bracket_q", ["11", "12"]),
                an(p)["higher_order_convergence"]["order1_schur"].__setitem__("lambda2_bracket_dec4", ["11.0000", "12.0000"]),
                an(p)["t3_auto_blowup_ranker"].__setitem__("baseline_lambda2_bracket_q", ["11", "12"]),
            ),
            "O1_LAM2_MISMATCH",
        )
        # Order 2, 3, 4 (isolated sub-clause kills)
        mut_check(lambda p: an(p)["higher_order_convergence"]["order2_triangles"]["classification_counts"].__setitem__("CONDITIONAL_COMPOUNDING_CLOSURE", 23), "O2_ALGEBRA_FAIL")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order2_triangles"].__setitem__("even_z2_holonomy_triangles", 33), "O2_ALGEBRA_FAIL")
        mut_check(
            lambda p: (
                an(p)["higher_order_convergence"]["order2_triangles"].__setitem__("odd_z2_holonomy_triangles", 21),
                an(p)["higher_order_convergence"]["order2_triangles"].__setitem__("even_z2_holonomy_triangles", 35),
            ),
            "O2_ALGEBRA_FAIL",
        )
        mut_check(lambda p: an(p)["higher_order_convergence"]["order2_triangles"].__setitem__("exact_transitive_closures", "abc"), "O2_ALGEBRA_FAIL")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order2_triangles"].__setitem__("exact_transitive_closures", []), "O2_ALGEBRA_FAIL")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order2_triangles"].__setitem__("exact_transitive_closures", [123, None, []]), "INVALID_STR")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order2_triangles"].__setitem__("exact_transitive_closures", ["BOGUS", "v0-v5-v6", "v1-v2-v7"]), "O2_CLOSURE_INVALID")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order2_triangles"].__setitem__("exact_transitive_closures", ["v0-v3-v7", "v0-v3-v7", "v1-v2-v7"]), "O2_CLOSURE_INVALID")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order3_tetrahedra"].__setitem__("bianchi_coboundary_zero_all", False), "O3_BIANCHI_FAIL")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order3_tetrahedra"]["frustrated_face_distribution"].__setitem__("0", 19), "O3_FDIST_FAIL")
        mut_check(
            lambda p: (
                an(p)["higher_order_convergence"]["order3_tetrahedra"].__setitem__("zero_obstruction_k4_count", 0),
                an(p)["higher_order_convergence"]["order3_tetrahedra"].__setitem__("all_commute_k4_count", 70),
            ),
            "INT_OUT_OF_RANGE",
        )
        mut_check(lambda p: an(p)["higher_order_convergence"]["order3_tetrahedra"].__setitem__("zero_obstruction_k4_count", 15), "INT_OUT_OF_RANGE")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order3_tetrahedra"].__setitem__("zero_obstruction_k4_count", 17), "INT_OUT_OF_RANGE")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order3_tetrahedra"].__setitem__("all_commute_k4_count", 1), "INT_OUT_OF_RANGE")
        mut_check(
            lambda p: (
                an(p)["higher_order_convergence"]["order4_five_cells_and_silo_cuts"].__setitem__("zero_obstruction_five_cells", 0),
                an(p)["higher_order_convergence"]["order4_five_cells_and_silo_cuts"].__setitem__("all_commute_five_cells", 56),
            ),
            "INT_OUT_OF_RANGE",
        )
        mut_check(lambda p: an(p)["higher_order_convergence"]["order4_five_cells_and_silo_cuts"].__setitem__("zero_obstruction_five_cells", 3), "INT_OUT_OF_RANGE")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order4_five_cells_and_silo_cuts"].__setitem__("zero_obstruction_five_cells", 5), "INT_OUT_OF_RANGE")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order4_five_cells_and_silo_cuts"].__setitem__("all_commute_five_cells", 1), "INT_OUT_OF_RANGE")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order4_five_cells_and_silo_cuts"]["silo_cut_curves"]["4|4"]["k5"].__setitem__("destroyed_pct_dec2", "99.00"), "O4_SILO_PCT_MISMATCH")
        # T_1, T_2, T_3 (isolated sub-clause kills + S88-VER-02 G2/F2b/G3/G7/G8)
        mut_check(lambda p: an(p)["t1_line_graph_hodge"].__setitem__("same_tag_disjoint_functor_bridges", 17), "INT_OUT_OF_RANGE")
        mut_check(lambda p: an(p)["t1_line_graph_hodge"].__setitem__("same_tag_disjoint_functor_bridges", 19), "INT_OUT_OF_RANGE")
        mut_check(lambda p: an(p)["t1_line_graph_hodge"].__setitem__("b1_b2_zero_exact", False), "T1_HODGE_FAIL")
        mut_check(lambda p: an(p)["t1_line_graph_hodge"].__setitem__("hodge1_equals_n_identity", False), "T1_HODGE_FAIL")
        mut_check(lambda p: an(p)["t1_line_graph_hodge"].__setitem__("obstruction_hodge_orthogonal_exact", False), "T1_HODGE_FAIL")
        mut_check(lambda p: an(p)["t1_line_graph_hodge"].__setitem__("obstruction_hodge_reconstruction_exact", False), "T1_HODGE_FAIL")
        mut_check(
            lambda p: (
                an(p)["t1_line_graph_hodge"].__setitem__("obstruction_flow_norm_sq_q", "7"),
                an(p)["t1_line_graph_hodge"].__setitem__("obstruction_grad_energy_q", "17/4"),
            ),
            "T1_HODGE_FAIL",
        )
        mut_check(
            lambda p: (
                an(p)["t1_line_graph_hodge"].__setitem__("obstruction_flow_norm_sq_q", "5"),
                an(p)["t1_line_graph_hodge"].__setitem__("obstruction_curl_energy_q", "7/4"),
            ),
            "T1_HODGE_FAIL",
        )
        mut_check(lambda p: an(p)["t1_line_graph_hodge"].__setitem__("obstruction_flow_norm_sq_q", "7"), "T1_HODGE_FAIL")
        mut_check(lambda p: an(p)["t1_line_graph_hodge"].__setitem__("obstruction_curl_energy_q", "1"), "T1_HODGE_FAIL")
        mut_check(lambda p: an(p)["t2_signed_frustration_double_cover"].__setitem__("signed_laplacian_det_q", "0"), "T2_DET_FAIL")
        mut_check(lambda p: an(p)["t2_signed_frustration_double_cover"].__setitem__("signed_laplacian_det_q", "1"), "T2_DET_FAIL")
        mut_check(lambda p: an(p)["t2_signed_frustration_double_cover"].__setitem__("is_frustrated", False), "T2_FRUST_FAIL")
        mut_check(
            lambda p: (
                an(p)["t2_signed_frustration_double_cover"].__setitem__("frustration_lambda1_bracket_q", ["2", "3"]),
                an(p)["t2_signed_frustration_double_cover"].__setitem__("frustration_lambda1_bracket_dec4", ["2.0000", "3.0000"]),
            ),
            "T2_L1_MISMATCH",
        )
        mut_check(lambda p: an(p)["t2_signed_frustration_double_cover"].__setitem__("double_cover_connected", False), "T2_DC_FAIL")
        mut_check(lambda p: an(p)["t2_signed_frustration_double_cover"].__setitem__("law5_gauge_sheet_obstruction_active", False), "T2_DC_FAIL")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"].__setitem__("target_class", "CONDITIONAL_BRIDGE"), "T3_TARGET")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"].__setitem__("baseline_lambda2_bracket_q", ["1", "2"]), "T3_BASE_L2")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"].__setitem__("ranked_unlocks", "abcdef"), "T3_LEN")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"].pop(), "T3_LEN")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("pair", ""), "T3_PAIR_TAG_INVALID")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("pair", "BOGUS"), "T3_PAIR_TAG_INVALID")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("operator_tag", ""), "T3_PAIR_TAG_INVALID")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("operator_tag", "BOGUS_TAG"), "T3_PAIR_TAG_INVALID")
        mut_check(
            lambda p: (
                an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("pair", "BOGUS"),
                an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("operator_tag", "BOGUS_TAG"),
            ),
            "T3_PAIR_TAG_INVALID",
        )
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][1].__setitem__("pair", "v6-v7"), "T3_PAIR_TAG_INVALID")
        mut_check(
            lambda p: [r.__setitem__("pair", "v6-v7") for r in an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"]],
            "T3_PAIR_TAG_INVALID",
        )
        mut_check(
            lambda p: (
                an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][2].__setitem__("frustrated_resolved", 6),
                an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][2].__setitem__("multi_wall_exposed", 6),
                an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][2].__setitem__("net_frustrated_delta", 0),
            ),
            "INT_OUT_OF_RANGE",
        )
        mut_check(
            lambda p: (
                an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][2].__setitem__("frustrated_resolved", 3),
                an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][2].__setitem__("multi_wall_exposed", 4),
                an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][2].__setitem__("net_frustrated_delta", 1),
            ),
            "INT_OUT_OF_RANGE",
        )
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("net_frustrated_delta", -5), "T3_ORDER_FAIL")

        def _swap_t3_first_two(p):
            rows = an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"]
            rows[0], rows[1] = rows[1], rows[0]
            rows[0]["rank"], rows[1]["rank"] = 1, 2

        mut_check(_swap_t3_first_two, "T3_ORDER_FAIL")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("signed_lambda1_after_bracket_dec4", "ab"), "T3_SL1_DEC")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("signed_lambda1_after_bracket_dec4", ["1.0000"]), "T3_SL1_DEC")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("signed_lambda1_after_bracket_dec4", [1, "1.8896"]), "INVALID_STR")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("signed_lambda1_after_bracket_dec4", ["GARBAGE", "NOPE"]), "T3_SL1_DEC")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("signed_lambda1_after_bracket_dec4", ["01.0000", "2.0000"]), "T3_SL1_DEC")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("signed_lambda1_after_bracket_dec4", ["1.0000", "02.0000"]), "T3_SL1_DEC")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("signed_lambda1_after_bracket_dec4", ["2.0000", "1.0000"]), "T3_SL1_DEC")
        self._assert_err("T3_SL1_DEC", verifier._audit_dec4_nonneg_bracket, ("1.8872", "1.8896"), "t3.sl1")
        mut_check(
            lambda p: (
                an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("global_schur_conductance_gain_q", "0"),
                an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("global_schur_conductance_gain_dec4", "0.0000"),
            ),
            "T3_ROW_ALGEBRA",
        )
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("pair_direct_gain_q", "0"), "T3_ROW_ALGEBRA")
        mut_check(
            lambda p: (
                an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("kirchhoff_reduction_q", "0"),
                an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("kirchhoff_reduction_dec4", "0.0000"),
            ),
            "T3_ROW_ALGEBRA",
        )
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("global_schur_conductance_gain_dec4", "0.0000"), "T3_ROW_ALGEBRA")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("kirchhoff_reduction_dec4", "0.0000"), "T3_ROW_ALGEBRA")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("lambda2_strict_lift_certified", True), "T3_ROW_ALGEBRA")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"]["ranked_unlocks"][0].__setitem__("signed_det_after_q", "0"), "T3_ROW_ALGEBRA")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"].__setitem__("top_frustration_unlock_pair", "v1-v5"), "T3_PARETO_FAIL")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"].__setitem__("top_conductance_unlock_pair", "v1-v5"), "T3_PARETO_FAIL")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"].__setitem__("top_lambda2_unlock_pair", "v6-v7"), "T3_PARETO_FAIL")
        mut_check(lambda p: an(p)["t3_auto_blowup_ranker"].__setitem__("pareto_multi_wall_obstruction_detected", False), "T3_PARETO_FAIL")
        # T_4, T_5, T_6, Firewall, Parametric, Plugin (isolated sub-clause kills + S88-VER-02 G4/G5/G6/G10/G11/G13/G14)
        mut_check(lambda p: an(p)["t4_directed_loop_schur_gate"].__setitem__("unstable_lyapunov_inertia", "abc"), "T4_UNSTABLE_FAIL")
        mut_check(lambda p: an(p)["t4_directed_loop_schur_gate"].__setitem__("unstable_lyapunov_inertia", [1, 2]), "T4_UNSTABLE_FAIL")
        mut_check(lambda p: an(p)["t4_directed_loop_schur_gate"].__setitem__("unstable_lyapunov_inertia", ["GARBAGE", None, []]), "INVALID_INT")
        mut_check(lambda p: an(p)["t4_directed_loop_schur_gate"].__setitem__("unstable_lyapunov_inertia", [99, 99, 99]), "INT_OUT_OF_RANGE")
        mut_check(lambda p: an(p)["t4_directed_loop_schur_gate"].__setitem__("unstable_lyapunov_inertia", [4, 0, 0]), "INT_OUT_OF_RANGE")
        mut_check(lambda p: an(p)["t4_directed_loop_schur_gate"].__setitem__("unstable_lyapunov_inertia", [-1, 2, 2]), "INT_OUT_OF_RANGE")
        mut_check(lambda p: an(p)["t4_directed_loop_schur_gate"].__setitem__("unstable_lyapunov_inertia", [2, 2, 0]), "T4_UNSTABLE_FAIL")
        mut_check(lambda p: an(p)["t4_directed_loop_schur_gate"].__setitem__("unstable_lyapunov_inertia", [3, 0, 0]), "T4_UNSTABLE_FAIL")
        # Valid non-SPD boundary [0, 3, 0] passes SEC/FR0 (kills hi=3->2 boundary mutant) and fails FR1
        c_u3 = copy.deepcopy(cert)
        an(c_u3["payload"])["t4_directed_loop_schur_gate"]["unstable_lyapunov_inertia"] = [0, 3, 0]
        rs_u3 = _resign_cert(c_u3)
        self.assertTrue(verifier.secondary_audit_payload(rs_u3["payload"])["secondary_audit_passed"])
        self._assert_err("FULL_REPLAY_MISMATCH", verifier.verify_certificate_dict, rs_u3, full_replay=True)
        mut_check(lambda p: an(p)["t4_directed_loop_schur_gate"].__setitem__("curl_frobenius_sq_q", "1/999"), "T4_GATE_FAIL")
        mut_check(lambda p: an(p)["t4_directed_loop_schur_gate"].__setitem__("non_normal_commutator_sq_q", "1/999"), "T4_GATE_FAIL")
        mut_check(lambda p: an(p)["t4_directed_loop_schur_gate"].__setitem__("is_non_normal", False), "T4_GATE_FAIL")
        mut_check(lambda p: an(p)["t4_directed_loop_schur_gate"].__setitem__("directed_col0_response_q", "999"), "T4_GATE_FAIL")
        mut_check(lambda p: an(p)["t4_directed_loop_schur_gate"].__setitem__("symmetrized_col0_response_q", "1"), "T4_GATE_FAIL")
        mut_check(lambda p: an(p)["t4_directed_loop_schur_gate"].__setitem__("directional_asymmetry_certified", False), "T4_GATE_FAIL")
        mut_check(lambda p: an(p)["t4_directed_loop_schur_gate"].__setitem__("stable_gate_passed", False), "T4_GATE_FAIL")
        mut_check(lambda p: an(p)["t4_directed_loop_schur_gate"].__setitem__("unstable_gate_rejected", False), "T4_GATE_FAIL")
        mut_check(lambda p: an(p)["t4_directed_loop_schur_gate"].__setitem__("law3_damping_factor_q", "1/2"), "T4_GATE_FAIL")
        mut_check(lambda p: an(p)["t4_directed_loop_schur_gate"].__setitem__("damped_gate_restored", False), "T4_GATE_FAIL")
        mut_check(lambda p: an(p)["t5_borromean_hyperedge_detector"]["borromean_3body_helicity"].__setitem__("pairwise_blind_hypergraph_unlocked", False), "T5_H3_FAIL")
        mut_check(lambda p: an(p)["t5_borromean_hyperedge_detector"]["borromean_4way_sovereign_stack"].__setitem__("components", "abcd"), "T5_H4_COMP")
        mut_check(lambda p: an(p)["t5_borromean_hyperedge_detector"]["borromean_4way_sovereign_stack"].__setitem__("components", ["a"]), "T5_H4_COMP")
        mut_check(lambda p: an(p)["t5_borromean_hyperedge_detector"]["borromean_4way_sovereign_stack"].__setitem__("components", [1, 2, 3, 4]), "INVALID_STR")
        mut_check(lambda p: an(p)["t5_borromean_hyperedge_detector"]["borromean_4way_sovereign_stack"].__setitem__("components", ["", "b", "c", "d"]), "T5_H4_COMP")
        mut_check(lambda p: an(p)["t5_borromean_hyperedge_detector"]["borromean_4way_sovereign_stack"].__setitem__("components", ["a", "a", "c", "d"]), "T5_H4_COMP")
        mut_check(
            lambda p: (
                an(p)["t5_borromean_hyperedge_detector"]["borromean_4way_sovereign_stack"].__setitem__("full_4way_vram_mib", 300),
                an(p)["t5_borromean_hyperedge_detector"]["borromean_4way_sovereign_stack"].__setitem__("headroom_mib", 7892),
            ),
            "INT_OUT_OF_RANGE",
        )
        mut_check(lambda p: an(p)["t5_borromean_hyperedge_detector"]["borromean_4way_sovereign_stack"].__setitem__("full_4way_vram_mib", 4822), "INT_OUT_OF_RANGE")
        mut_check(lambda p: an(p)["t5_borromean_hyperedge_detector"]["borromean_4way_sovereign_stack"].__setitem__("headroom_mib", 3370), "T5_H4_FAIL")
        mut_check(lambda p: an(p)["t5_borromean_hyperedge_detector"]["borromean_4way_sovereign_stack"].__setitem__("full_4way_feasible", False), "T5_H4_FAIL")
        mut_check(lambda p: an(p)["t5_borromean_hyperedge_detector"]["borromean_4way_sovereign_stack"].__setitem__("borromean_irreducible_certified", False), "T5_H4_FAIL")
        mut_check(lambda p: an(p)["t6_kron_coarsening_and_curvature"].__setitem__("kept_nodes", ["v0", "v1", "v2", "v4"]), "T6_KEEP")
        mut_check(lambda p: an(p)["t6_kron_coarsening_and_curvature"].__setitem__("all_kept_edges_strictly_boosted", False), "T6_KRON_FAIL")
        mut_check(lambda p: an(p)["t6_kron_coarsening_and_curvature"].__setitem__("all_kept_pairs_r_eff_exact_invariant", False), "T6_KRON_FAIL")
        mut_check(lambda p: an(p)["t6_kron_coarsening_and_curvature"].__setitem__("r_eff_gram_det_q", "0"), "T6_KRON_FAIL")
        mut_check(lambda p: an(p)["t6_kron_coarsening_and_curvature"].__setitem__("r_eff_gram_det_q", "999"), "T6_KRON_FAIL")
        mut_check(lambda p: an(p)["t6_kron_coarsening_and_curvature"].__setitem__("cat0_rank_metric_det_q", "-1/2"), "T6_KRON_FAIL")
        mut_check(lambda p: an(p)["t6_kron_coarsening_and_curvature"].__setitem__("se3_r3_gram_det_q", "1"), "T6_KRON_FAIL")
        mut_check(lambda p: an(p)["t6_kron_coarsening_and_curvature"].__setitem__("three_regime_curvature_separated", False), "T6_KRON_FAIL")
        mut_check(lambda p: an(p)["law3_contagion_firewall"].__setitem__("compromised_node", 999), "INVALID_STR")
        mut_check(lambda p: an(p)["law3_contagion_firewall"].__setitem__("clean_anchor_node", None), "INVALID_STR")
        mut_check(lambda p: an(p)["law3_contagion_firewall"].__setitem__("compromised_node", "v9"), "FW_NODE_INVALID")
        mut_check(lambda p: an(p)["law3_contagion_firewall"].__setitem__("clean_anchor_node", "v9"), "FW_NODE_INVALID")
        mut_check(
            lambda p: (
                an(p)["law3_contagion_firewall"].__setitem__("compromised_node", "v0"),
                an(p)["law3_contagion_firewall"].__setitem__("clean_anchor_node", "v0"),
            ),
            "FW_NODE_INVALID",
        )
        mut_check(
            lambda p: (
                an(p)["law3_contagion_firewall"].__setitem__("compromised_node", "v9"),
                an(p)["law3_contagion_firewall"].__setitem__("clean_anchor_node", "v9"),
            ),
            "FW_NODE_INVALID",
        )
        mut_check(
            lambda p: (
                an(p)["law3_contagion_firewall"].__setitem__("direct_edge_flux_q", "2"),
                an(p)["law3_contagion_firewall"].__setitem__("ungated_flux_amplification_q", "63330219/10774199"),
                an(p)["law3_contagion_firewall"].__setitem__(
                    "ungated_flux_amplification_dec4",
                    engine.dec_from_q(Fraction(63330219, 10774199), 4),
                ),
            ),
            "FW_ALGEBRA_FAIL",
        )
        mut_check(
            lambda p: (
                an(p)["law3_contagion_firewall"].__setitem__("ungated_total_flux_q", "8"),
                an(p)["law3_contagion_firewall"].__setitem__("ungated_flux_amplification_q", "2"),
                an(p)["law3_contagion_firewall"].__setitem__("ungated_flux_amplification_dec4", "2.0000"),
            ),
            "FW_ALGEBRA_FAIL",
        )
        mut_check(
            lambda p: (
                an(p)["law3_contagion_firewall"].__setitem__("direct_edge_flux_q", "1"),
                an(p)["law3_contagion_firewall"].__setitem__("ungated_total_flux_q", "2"),
                an(p)["law3_contagion_firewall"].__setitem__("ungated_flux_amplification_q", "2"),
                an(p)["law3_contagion_firewall"].__setitem__("ungated_flux_amplification_dec4", "2.0000"),
                an(p)["law3_contagion_firewall"].__setitem__("retained_min_compounding_gain_q", "2"),
                an(p)["law3_contagion_firewall"].__setitem__("retained_min_compounding_gain_dec4", "2.0000"),
            ),
            "FW_ALGEBRA_FAIL",
        )
        mut_check(
            lambda p: (
                an(p)["law3_contagion_firewall"].__setitem__("ungated_flux_amplification_q", "2"),
                an(p)["law3_contagion_firewall"].__setitem__("ungated_flux_amplification_dec4", "2.0000"),
            ),
            "FW_ALGEBRA_FAIL",
        )
        mut_check(lambda p: an(p)["law3_contagion_firewall"].__setitem__("ungated_flux_amplification_dec4", "2.0000"), "FW_ALGEBRA_FAIL")
        mut_check(lambda p: an(p)["law3_contagion_firewall"].__setitem__("flux_equals_schur_g_eff", False), "FW_ALGEBRA_FAIL")
        mut_check(lambda p: an(p)["law3_contagion_firewall"].__setitem__("all_interior_nodes_corrupted", False), "FW_ALGEBRA_FAIL")
        mut_check(lambda p: an(p)["law3_contagion_firewall"].__setitem__("gated_firewall_flux_q", "1"), "FW_ALGEBRA_FAIL")
        mut_check(lambda p: an(p)["law3_contagion_firewall"].__setitem__("gated_firewall_interior_max_error_q", "1"), "FW_ALGEBRA_FAIL")
        mut_check(lambda p: an(p)["law3_contagion_firewall"].__setitem__("retained_all_pairs_compounded", False), "FW_ALGEBRA_FAIL")
        mut_check(
            lambda p: (
                an(p)["law3_contagion_firewall"].__setitem__("retained_min_compounding_gain_q", "2"),
                an(p)["law3_contagion_firewall"].__setitem__("retained_min_compounding_gain_dec4", "2.0000"),
            ),
            "FW_ALGEBRA_FAIL",
        )
        mut_check(lambda p: an(p)["law3_contagion_firewall"].__setitem__("retained_min_compounding_gain_dec4", "1.0000"), "FW_ALGEBRA_FAIL")
        # >4300-digit rational string DoS protection (zero raw ValueError on SEC/FR0/FR1)
        huge_q = "9" * 5000
        self._assert_err("INT_TOO_LARGE", verifier.parse_canonical_rational_str, huge_q, "huge")
        self._assert_err("INT_TOO_LARGE", verifier.parse_canonical_rational_str, "1/" + huge_q, "huge_den")
        mut_check(lambda p: an(p)["higher_order_convergence"]["order1_schur"].__setitem__("total_conductance_q", huge_q), "INT_TOO_LARGE")
        mut_check(lambda p: p.__setitem__("parametric_scaling_summary", "abc"), "PARAM_LEN_FAIL")
        mut_check(lambda p: p["parametric_scaling_summary"].pop(), "PARAM_LEN_FAIL")
        mut_check(lambda p: p["parametric_scaling_summary"][0].__setitem__("foster_identity_exact", False), "PARAM_ROW_FAIL")
        mut_check(lambda p: p["parametric_scaling_summary"][0].__setitem__("all_pairs_strictly_compounded", False), "PARAM_ROW_FAIL")
        mut_check(lambda p: p["parametric_scaling_summary"][0].__setitem__("bianchi_coboundary_zero_all", False), "PARAM_ROW_FAIL")
        mut_check(lambda p: p["parametric_scaling_summary"][0].__setitem__("hodge_b1_b2_zero_exact", False), "PARAM_ROW_FAIL")
        mut_check(lambda p: p["parametric_scaling_summary"][0].__setitem__("hodge1_equals_n_identity", False), "PARAM_ROW_FAIL")
        mut_check(lambda p: p["parametric_scaling_summary"][0].__setitem__("signed_is_frustrated", False), "PARAM_ROW_FAIL")
        mut_check(lambda p: p["parametric_scaling_summary"][0].__setitem__("kron_r_eff_exact_invariant", False), "PARAM_ROW_FAIL")
        mut_check(lambda p: p["parametric_scaling_summary"][0].__setitem__("firewall_zero_flux", False), "PARAM_ROW_FAIL")
        mut_check(lambda p: p["parametric_scaling_summary"][0].__setitem__("balanced_split", "1|3"), "PARAM_ROW_FAIL")
        mut_check(lambda p: p["parametric_scaling_summary"][0]["balanced_silo_cut"]["k2"].__setitem__("destroyed_pct_dec2", "1.00"), "PARAM_SILO_PCT")
        mut_check(lambda p: p["aletheia_cli_plugin_spec"].__setitem__("subcommand", "bad"), "PLUGIN_SPEC_FAIL")
        mut_check(lambda p: p["aletheia_cli_plugin_spec"].__setitem__("entrypoint", "bad"), "PLUGIN_SPEC_FAIL")
        mut_check(lambda p: p["aletheia_cli_plugin_spec"].__setitem__("input_schemas", []), "PLUGIN_SPEC_FAIL")
        mut_check(lambda p: p["aletheia_cli_plugin_spec"].__setitem__("modes", []), "PLUGIN_SPEC_FAIL")
        mut_check(lambda p: p["aletheia_cli_plugin_spec"].__setitem__("zero_float_strict", False), "PLUGIN_SPEC_FAIL")
        mut_check(lambda p: p["aletheia_cli_plugin_spec"].__setitem__("r4_three_mode_deterministic", False), "PLUGIN_SPEC_FAIL")
        mut_check(lambda p: p["aletheia_cli_plugin_spec"].__setitem__("node_bounds", [4, 8]), "PLUGIN_SPEC_FAIL")

        # Full replay mismatch (subtle value swap that passes secondary audit: e.g. swap order of exact_transitive_closures)
        c_rep = copy.deepcopy(cert)
        an(c_rep["payload"])["higher_order_convergence"]["order2_triangles"]["exact_transitive_closures"].reverse()
        rs_rep = _resign_cert(c_rep)
        verifier.verify_certificate_dict(rs_rep, full_replay=False)
        self._assert_err("FULL_REPLAY_MISMATCH", verifier.verify_certificate_dict, rs_rep, full_replay=True)

        # Static bundle verification error paths
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            (tdir / "lean-toolchain").write_bytes(b"\xff\xfe")
            self._assert_err("INVALID_UTF8", verifier._verify_static_lean_bundle, tdir)
            (tdir / "lean-toolchain").write_text("leanprover/lean4:v4.10.0\n", encoding="utf-8")
            self._assert_err("TOOLCHAIN_MISMATCH", verifier._verify_static_lean_bundle, tdir)
            (tdir / "lean-toolchain").write_bytes((_THIS_DIR / "lean-toolchain").read_bytes())
            (tdir / "lakefile.toml").write_bytes((_THIS_DIR / "lakefile.toml").read_bytes())
            (tdir / "AletheiaMeshEngine.lean").write_bytes(b"\xff\xfe")
            self._assert_err("INVALID_UTF8", verifier._verify_static_lean_bundle, tdir)
            # Bracket helper non-strict-pos check
            self.assertEqual(verifier._audit_bracket_pair(["0", "1"], ["0.0000", "1.0000"], "z", strict_pos=False), (Fraction(0), Fraction(1)))

    def test_cli_modes_and_rejections(self) -> None:
        def run_cli(argv):
            so = io.StringIO()
            se = io.StringIO()
            with mock.patch.object(sys, "stdout", so), mock.patch.object(sys, "stderr", se):
                rc = verifier.main(argv)
            return rc, so.getvalue(), se.getvalue()

        with tempfile.TemporaryDirectory() as td:
            out_p = Path(td) / "s88.json"
            rc, out, err = run_cli(["--write", str(out_p), "--json"])
            self.assertEqual((rc, err), (0, ""))
            self.assertEqual(stat.S_IMODE(os.lstat(out_p).st_mode), 0o600)
            self.assertTrue(json.loads(out)["written"])

            rc, out, err = run_cli(["--write=" + str(out_p)])
            self.assertEqual((rc, err), (0, ""))
            self.assertTrue(out.startswith("WROTE "))

            rc, out, err = run_cli(["--check=" + str(out_p)])
            self.assertEqual((rc, err), (0, ""))
            self.assertTrue(out.startswith("OK "))

            rc, out, err = run_cli(["--check", str(out_p), "--json"])
            self.assertEqual((rc, err), (0, ""))
            self.assertTrue(json.loads(out)["valid"])

            rc, out, err = run_cli(["--standalone"])
            self.assertEqual((rc, err), (0, ""))
            self.assertEqual(out.encode("ascii"), (_THIS_DIR / "s88_aletheia_mesh_certificate.json").read_bytes())

            rc, out, err = run_cli([])
            self.assertEqual((rc, err), (0, ""))
            self.assertTrue(out.startswith("OK "))

            rc, out, err = run_cli(["--json"])
            self.assertEqual((rc, err), (0, ""))
            self.assertTrue(json.loads(out)["valid"])

            with mock.patch.object(verifier.sys, "argv", ["verify_aletheia_mesh.py", "--json"]):
                rc, out, err = run_cli(None)
                self.assertEqual((rc, err), (0, ""))
                self.assertTrue(json.loads(out)["valid"])

            # --analyze on external generic mesh JSON (both text & --json)
            mesh_p = Path(td) / "k4_spec.json"
            mesh_p.write_bytes(engine.canonical_json_bytes(engine.build_parametric_kn_spec(4)))
            rc, out, err = run_cli(["--analyze", str(mesh_p)])
            self.assertEqual((rc, err), (0, ""))
            self.assertIn("TOP_FRUSTRATION_UNLOCK=v0-v1", out)
            rc, out, err = run_cli(["--analyze", str(mesh_p), "--json"])
            self.assertEqual((rc, err), (0, ""))
            self.assertEqual(json.loads(out)["mode"], "analyze")

            # --parametric 5 (both text & --json)
            rc, out, err = run_cli(["--parametric", "5"])
            self.assertEqual((rc, err), (0, ""))
            self.assertIn("MESH parametric_k5_mesh (N=5)", out)
            rc, out, err = run_cli(["--parametric=5", "--json"])
            self.assertEqual((rc, err), (0, ""))
            self.assertEqual(json.loads(out)["mode"], "parametric")

            # --verify-lean (live when lean present; fail-closed LEAN_BINARY_UNAVAILABLE when absent -> 0 skips!)
            lean_p = _THIS_DIR / "AletheiaMeshEngine.lean"
            try:
                verifier.resolve_lean_binary()
                has_lean = True
            except engine.MeshError:
                has_lean = False
            if has_lean or os.environ.get("ALETHEIA_REQUIRE_LEAN") == "1":
                rc, out, err = run_cli(["--verify-lean=" + str(lean_p), "--json"])
                self.assertEqual((rc, err), (0, ""))
                self.assertEqual(json.loads(out)["theorems_verified"], 16)
                with mock.patch.object(
                    verifier,
                    "verify_lean4_file_live",
                    return_value={"theorems_verified": 16, "lean_sha256": engine.EXPECTED_LEAN_SHA256},
                ):
                    rc, out, err = run_cli(["--verify-lean", str(lean_p)])
                    self.assertEqual((rc, err), (0, ""))
                    self.assertTrue(out.startswith("LEAN_OK 16 "))
            else:
                rc, out, err = run_cli(["--verify-lean", str(lean_p), "--json"])
                self.assertEqual(rc, 2)
                self.assertEqual(json.loads(err)["code"], "LEAN_BINARY_UNAVAILABLE")

            bad_cases = [
                (123, "INVALID_ARGV"),
                (["--json", "--json"], "DUPLICATE_FLAG"),
                (["--standalone", "--check", str(out_p)], "CONFLICTING_MODE"),
                (["--check", str(out_p), "--standalone"], "CONFLICTING_MODE"),
                (["--check", str(out_p), "--write=" + str(out_p)], "CONFLICTING_MODE"),
                (["--check"], "MISSING_VALUE_ARG"),
                (["--check", ""], "INVALID_VALUE_ARG"),
                (["--check", "-bad"], "INVALID_VALUE_ARG"),
                (["--check="], "INVALID_VALUE_ARG"),
                (["--write=-bad"], "INVALID_VALUE_ARG"),
                (["--bad=val"], "UNKNOWN_FLAG"),
                (["--unknown"], "UNKNOWN_FLAG"),
                (["--check\x00"], "NUL_BYTE_FORBIDDEN"),
                (["--check", "a\x00b"], "NUL_BYTE_FORBIDDEN"),
                (["--check", "\ud800"], "INVALID_UTF8_SURROGATE"),
            ]
            for bad_argv, code in bad_cases:
                rc, out, err = run_cli(bad_argv)
                self.assertEqual(rc, 2, f"argv={bad_argv!r}")
                self.assertEqual(out, "")
                self.assertEqual(json.loads(err)["code"], code)
            self._assert_err("NUL_BYTE_FORBIDDEN", verifier._parse_cli_args, ["--check", "a\x00b"])
            self.assertEqual(verifier._parse_cli_args([])["mode"], "default")


class Test05LeanGatesR10Plus(unittest.TestCase):
    def _assert_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(engine.MeshError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_strip_and_r10_plus_static_gate(self) -> None:
        lean_src = (_THIS_DIR / "AletheiaMeshEngine.lean").read_text(encoding="utf-8")
        verifier.static_gate_lean4_source(lean_src)
        # Positive controls (0 FP on explicit native := false, Bool.false, @[simp]/@[inline]/@[macro_inline], export, my_panic)
        verifier.static_gate_lean4_source(lean_src + "\nprivate theorem _pos_ctrl1 : 1 + 1 = 2 := by decide (native := false)\n")
        verifier.static_gate_lean4_source(lean_src + "\nprivate theorem _pos_ctrl2 : 1 + 1 = 2 := by decide (native := Bool.false)\n")
        verifier.static_gate_lean4_source(lean_src + "\n@[simp] private def _pos_ctrl3 : Nat := 0\n@[inline] private def _pos_ctrl4 : Nat := 1\n@[macro_inline] private def _pos_ctrl5 : Nat := 2\n")
        verifier.static_gate_lean4_source(lean_src + "\nexport Nat (succ)\nprivate def init : Nat := 0\nprivate def my_panic : Nat := 0\n")

        stripped = verifier._strip_lean4_for_static_gate(
            "/- outer / - /- sorry -/ -/ -- axiom\n"
            "def x := a / b - c\n"
            "-- eof comment"
        )
        self.assertNotIn("sorry", stripped)
        self.assertNotIn("axiom", stripped)
        self.assertIn("a / b - c", stripped)
        self.assertEqual(verifier._strip_lean4_for_static_gate("/- a - sorry -/\n").strip(), "")
        self.assertEqual(verifier._strip_lean4_for_static_gate("/- a / sorry -/\n").strip(), "")
        self._assert_err("LEAN4_UNTERMINATED_LEX", verifier._strip_lean4_for_static_gate, "/- unclosed")
        self._assert_err("LEAN4_BAD_CHARS", verifier.static_gate_lean4_source, lean_src + "\r")
        self._assert_err("LEAN4_BAD_CHARS", verifier.static_gate_lean4_source, lean_src + "\x00")

        for escape in (
            "\nsorry\n",
            "\nadmit\n",
            "\naxiom bad : Prop\n",
            "\nunsafe def u := 0\n",
            "\ntheorem t : True := by native_decide\n",
            "\ntheorem t : True := by bv_decide\n",
            "\ndef s := sorryAx\n",
            "\nprivate theorem _d01 : False := _root_.sorryAx False false\n",
            "\ndef _d02 := Lean.ofReduceBool\n",
            "\ndef _d03 := Lean.ofReduceNat\n",
            "\ndef _d04 := Lean.trustCompiler\n",
            "\ndef _d05 := Lean.Meta.mkSorry\n",
            "\nset_option debug.skipKernelTC true\n",
            "\nset_option warn.sorry false in private theorem _f04 : False := _root_.sorryAx False false\n",
            "\nset_option «debug».«skipKernelTC» true\n",
            '\n@[extern "c_fn"] def f : Nat := 0\n',
            "\nattribute [implemented_by f] g\n",
            "\n@[export c_sym] def f : Nat := 0\n",
            "\n@[init f] def g : Nat := 0\n",
            "\n@[builtin_init f] def g : Nat := 0\n",
            "\n@[term_elab f] def g : Nat := 0\n",
            "\n@[command_elab f] def g : Nat := 0\n",
            "\n@[tactic f] def g : Nat := 0\n",
            "\n@[macro f] def g : Nat := 0\n",
            "\n@[macro_rules f] def g : Nat := 0\n",
            "\n@[builtin_tactic f] def g : Nat := 0\n",
            "\nattribute [tactic f] g\n",
            "\n@[csimp] theorem c : True := trivial\n",
            "\nopaque hidden : Nat := 0\n",
            "\npartial def loop : Nat := loop\n",
            "\nnoncomputable def nc : Nat := 0\n",
            "\ntheorem t : True := by decide +native\n",
            "\nprivate theorem _e1 : 1 = 1 := by decide -revert +native\n",
            "\ntheorem t : 1 = 1 := by decide (config := myCfg)\n",
            "\nprivate def native : Bool := true\nprivate theorem _atk10 : 1 + 1 = 2 := by decide +revert (config := { native })\n",
            "\nprivate def native : Bool := true\nprivate theorem _atk11 : 1 + 1 = 2 := by decide (revert := false) (config := { native })\n",
            "\nprivate theorem _atk11b : 1 + 1 = 2 := by decide { default with native := true }\n",
            "\ndef cfg : DecideConfig := {}\n",
            "\ntheorem t : True := by decide (native := !false)\n",
            "\ntheorem t : 1 + 1 = 2 := by decide (native := false || true)\n",
            "\ntheorem t : 1 + 1 = 2 := by decide (native := false == false)\n",
            "\ntheorem t : 1 + 1 = 2 := by decide (native := false != true)\n",
            "\ntheorem t : 1 + 1 = 2 := by decide (native := false.not)\n",
            "\ntheorem t : 1 + 1 = 2 := by decide (native := false\n  || true)\n",
            "\ntheorem t : 1 + 1 = 2 := by decide (native := Bool.false || true)\n",
            "\n#eval 1 + 1\n",
            "\n#reduce 1\n",
            "\n#check 1\n",
            "\n#synth Inhabited Nat\n",
            "\n#guard true\n",
            "\n#guard_msgs\n",
            "\n#exit\n",
            "\n#print Nat\n",
            "\n#print axioms Evil.thm\n",
            "\nimport Mathlib\n",
            "\nimport Init\n",
            '\nmacro "bad" : term => `(sorry)\n',
            "\nmacro_rules | x => x\n",
            "\nelab_rules | x => x\n",
            "\ndeclare_syntax_cat evil\n",
            '\nnotation "openq\\"" => 0\n',
            "\ninfixl:65 a => b\n",
            '\ndef x := s!"{(by sorry : String)}"\n',
            '\ndef _a := r#"""#\naxiom evil : False\ndef _b := r#"""#\n',
            "\ndef q1 : Char := '\"'\n#eval 1\ndef q2 : Char := '\"'\n",
            '\ndbg_trace "x"\n',
            "\nprivate def _f02 : Nat := dbgTrace (String.ofList []) (fun _ => 0)\n",
            "\nprivate def _f03 : Nat := _root_.dbgTrace (String.ofList []) (fun _ => 0)\n",
            "\nprivate def _dtv : Nat := dbgTraceVal 0\n",
            "\nprivate def _dtvi : Nat := dbgTraceValId 0\n",
            "\nprivate def _dts : Nat := dbgTraceIfShared 0 0\n",
            "\nprivate def _dsl : Nat := dbgSleep 0 (fun _ => 0)\n",
            "\nprivate def _dst : Nat := dbgStackTrace (fun _ => 0)\n",
            "\nprivate def _ds1 : Nat := dbg_sleep 0\n",
            "\nprivate def _ds2 : Nat := dbg_stack_trace 0\n",
            "\nprivate def _p1 : Nat := panic! 0\n",
            "\nprivate def _p2 : Nat := unreachable!\n",
            "\nprivate def _p3 : Nat := panicCore 0\n",
            "\nprivate def _p4 : Nat := panicWithPosWithDecl 0\n",
            "\nprivate def _p5 : Nat := assert! true\n",
            "\nprivate def _p6 : Nat := debug_assert! true\n",
            "\ntheorem t : False := by «sorry»\n",
        ):
            self._assert_err("LEAN4_TRUST_ESCAPE", verifier.static_gate_lean4_source, lean_src + escape)

        self._assert_err(
            "LEAN4_MISSING_THEOREM",
            verifier.static_gate_lean4_source,
            lean_src.replace("theorem k_simplex_silo_cut_edge_identity", "theorem renamed_thm"),
        )
        self._assert_err(
            "LEAN4_MISSING_THEOREM",
            verifier.static_gate_lean4_source,
            lean_src.replace("theorem k_simplex_silo_cut_edge_identity", "private theorem k_simplex_silo_cut_edge_identity"),
        )
        self._assert_err(
            "LEAN4_MISSING_THEOREM",
            verifier.static_gate_lean4_source,
            lean_src.replace("theorem k_simplex_silo_cut_edge_identity", "theorem k_simplex_silo_cut_edge_identity_fake"),
        )
        self._assert_err(
            "LEAN4_MISSING_PRINT_AXIOMS",
            verifier.static_gate_lean4_source,
            lean_src.replace("#print axioms AletheiaMeshEngine.k_simplex_silo_cut_edge_identity", ""),
        )
        self._assert_err(
            "LEAN4_MISSING_PRINT_AXIOMS",
            verifier.static_gate_lean4_source,
            lean_src.replace(
                "#print axioms AletheiaMeshEngine.k_simplex_silo_cut_edge_identity",
                "#print axioms AletheiaMeshEngine.k_simplex_silo_cut_edge_identity_fake",
            ),
        )

    def test_resolve_and_verify_lean_live_and_mocked(self) -> None:
        lean_path = _THIS_DIR / "AletheiaMeshEngine.lean"
        self._assert_err("INVALID_BOOL", verifier.verify_lean4_file_live, lean_path, enforce_sha256=1)
        try:
            verifier.resolve_lean_binary()
            has_lean = True
        except engine.MeshError:
            has_lean = False
        with tempfile.TemporaryDirectory() as td:
            # Live & unit LEAN_PATH / LEAN_OPTS / ELAN_* / LEAN_CC env-scrub immunity
            evil_dir = Path(td) / "evil_lean_path"
            evil_dir.mkdir(mode=0o700)
            (evil_dir / "Init.olean").write_bytes(b"CORRUPT_OLEAN_HIJACK")
            poison = {
                "LEAN_PATH": str(evil_dir),
                "LEAN_OPTS": "--nonexistent-lean-flag-999",
                "ELAN_TOOLCHAIN": "nonexistent-toolchain-99.99",
                "ELAN_HOME": str(evil_dir),
                "LEAN_CC": str(evil_dir / "no_cc"),
            }
            with mock.patch.dict(os.environ, poison):
                cleaned_env = verifier._clean_lean_env()
                for bad_k in poison:
                    self.assertNotIn(bad_k, cleaned_env)
                self.assertIn("PATH", cleaned_env)
                if has_lean or os.environ.get("ALETHEIA_REQUIRE_LEAN") == "1":
                    live = verifier.verify_lean4_file_live(lean_path, enforce_sha256=True)
                    self.assertEqual(live["theorems_verified"], len(engine.LEAN_THEOREM_NAMES))
                    self.assertIn("4.36.0", live["lean_version"])
                else:
                    self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.verify_lean4_file_live, lean_path, enforce_sha256=True)

            fake_bin = Path(td) / "lean"
            fake_bin.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(fake_bin, 0o700)
            noexec_bin = Path(td) / "lean_noexec"
            noexec_bin.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(noexec_bin, 0o600)
            dir_bin = Path(td) / "lean_dir"
            dir_bin.mkdir(mode=0o700)

            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(fake_bin)}):
                self.assertEqual(verifier.resolve_lean_binary(), str(fake_bin))
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(Path(td) / "missing")}):
                self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(noexec_bin)}):
                self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(dir_bin)}):
                self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)

            env_no = {k: v for k, v in os.environ.items() if k not in ("ALETHEIA_LEAN_BIN", "HOME")}
            with mock.patch.dict(os.environ, env_no, clear=True):
                with mock.patch.object(verifier.shutil, "which", return_value=str(fake_bin)):
                    self.assertEqual(verifier.resolve_lean_binary(), str(fake_bin))
                with mock.patch.object(verifier.shutil, "which", return_value=None):
                    self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
                home_d = Path(td) / "h"
                (home_d / ".local" / "bin" / "lean").mkdir(parents=True)
                (home_d / ".elan" / "bin").mkdir(parents=True)
                elan_lean = home_d / ".elan" / "bin" / "lean"
                elan_lean.write_text("#!/bin/sh\n", encoding="utf-8")
                os.chmod(elan_lean, 0o600)
                with mock.patch.dict(os.environ, {"HOME": str(home_d)}), mock.patch.object(
                    verifier.shutil, "which", return_value=str(noexec_bin)
                ):
                    self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
                os.chmod(elan_lean, 0o700)
                with mock.patch.dict(os.environ, {"HOME": str(home_d)}), mock.patch.object(
                    verifier.shutil, "which", return_value=None
                ):
                    self.assertEqual(verifier.resolve_lean_binary(), str(elan_lean))
                os.unlink(elan_lean)
                with mock.patch.dict(os.environ, {"HOME": str(home_d)}), mock.patch.object(
                    verifier.shutil, "which", return_value=None
                ):
                    self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)

            # SHA-256 pinning rejection & UTF-8 rejection & unpinned exploit rejection
            tampered = Path(td) / "tampered.lean"
            tampered.write_bytes(lean_path.read_bytes() + b"\n-- extra\n")
            self._assert_err("LEAN_SHA256_MISMATCH", verifier.verify_lean4_file_live, tampered, enforce_sha256=True)

            bad_utf8 = Path(td) / "bad.lean"
            bad_utf8.write_bytes(b"\xff\xfe")
            self._assert_err("INVALID_UTF8", verifier.verify_lean4_file_live, bad_utf8, enforce_sha256=False)

            base_lean = lean_path.read_text(encoding="utf-8")
            for idx_e, exploit_tail in enumerate((
                "\nprivate theorem _e1 : 1 = 1 := by decide -revert +native\n",
                "\nset_option «debug».«skipKernelTC» true\n",
                "\ndef q1 : Char := '\"'\n#eval 1\ndef q2 : Char := '\"'\n",
                "\nset_option warn.sorry false in private theorem _f04 : False := _root_.sorryAx False false\n",
                "\nprivate def _f02 : Nat := dbgTrace (String.ofList []) (fun _ => 0)\n",
                "\nprivate def _f03 : Nat := _root_.dbgTrace (String.ofList []) (fun _ => 0)\n",
                "\nprivate def native : Bool := true\nprivate theorem _atk10 : 1 + 1 = 2 := by decide +revert (config := { native })\n",
                "\nprivate def native : Bool := true\nprivate theorem _atk11 : 1 + 1 = 2 := by decide (revert := false) (config := { native })\n",
                "\n#guard true\n",
            )):
                exp_p = Path(td) / f"exp_{idx_e}.lean"
                exp_p.write_text(base_lean + exploit_tail, encoding="utf-8")
                self._assert_err("LEAN4_TRUST_ESCAPE", verifier.verify_lean4_file_live, exp_p, enforce_sha256=False)

        ok_ver = subprocess.CompletedProcess(["lean", "--version"], 0, "Lean (version 4.36.0, x86_64)\n", "")

        def run_mock(ver_res, comp_res, seen_envs=None):
            seq = [ver_res, comp_res]

            def side_eff(*a, **kw):
                if seen_envs is not None:
                    seen_envs.append(kw.get("env"))
                item = seq.pop(0)
                if isinstance(item, BaseException):
                    raise item
                return item

            return mock.patch.object(verifier.subprocess, "run", side_effect=side_eff)

        with mock.patch.object(verifier, "resolve_lean_binary", return_value="lean"):
            with run_mock(OSError("no"), ok_ver):
                self._assert_err("LEAN_EXEC_ERROR", verifier.verify_lean4_file_live, lean_path)
            with run_mock(subprocess.CompletedProcess(["lean"], 0, "Lean (version 4.10.0)\n", ""), ok_ver):
                self._assert_err("LEAN_VERSION_MISMATCH", verifier.verify_lean4_file_live, lean_path)
            with run_mock(subprocess.CompletedProcess(["lean"], 1, "Lean (version 4.36.0)\n", ""), ok_ver):
                self._assert_err("LEAN_VERSION_MISMATCH", verifier.verify_lean4_file_live, lean_path)
            with run_mock(ok_ver, subprocess.TimeoutExpired(["lean"], 120)):
                self._assert_err("LEAN_EXEC_ERROR", verifier.verify_lean4_file_live, lean_path)
            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 1, "", "")):
                self._assert_err("LEAN_COMPILE_FAIL", verifier.verify_lean4_file_live, lean_path)
            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 0, "", "err")):
                self._assert_err("LEAN_STDERR_NONEMPTY", verifier.verify_lean4_file_live, lean_path)
            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 0, "warning: unused\n", "")):
                self._assert_err("LEAN_WARNING_FORBIDDEN", verifier.verify_lean4_file_live, lean_path)
            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 0, "weird line\n", "")):
                self._assert_err("LEAN_UNEXPECTED_STDOUT", verifier.verify_lean4_file_live, lean_path)

            lines_ok = [f"'{engine.LEAN_THEOREM_NAMES[0]}' does not depend on any axioms", ""]
            lines_ok.append(f"'{engine.LEAN_THEOREM_NAMES[1]}' depends on axioms: []")
            lines_ok.append(f"'{engine.LEAN_THEOREM_NAMES[2]}' depends on axioms: [propext,")
            lines_ok.append("  ,")
            lines_ok.append("  Quot.sound]")
            for t in engine.LEAN_THEOREM_NAMES[3:]:
                lines_ok.append(f"'{t}' depends on axioms: [propext, Quot.sound]")
            seen_envs: list = []
            with mock.patch.dict(
                os.environ,
                {
                    "LEAN_PATH": "/tmp/evil_lp",
                    "LEAN_OPTS": "--evil",
                    "ELAN_TOOLCHAIN": "evil",
                    "ELAN_HOME": "/tmp/evil_eh",
                    "LEAN_CC": "/tmp/evil_cc",
                },
            ), run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 0, "\n".join(lines_ok) + "\n", ""), seen_envs):
                res = verifier.verify_lean4_file_live(lean_path)
                self.assertEqual(res["theorems_verified"], len(engine.LEAN_THEOREM_NAMES))
            self.assertEqual(len(seen_envs), 2)
            for c_env in seen_envs:
                self.assertIsInstance(c_env, dict)
                for bad_k in ("LEAN_PATH", "LEAN_OPTS", "ELAN_TOOLCHAIN", "ELAN_HOME", "LEAN_CC"):
                    self.assertNotIn(bad_k, c_env)

            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 0, f"'{engine.LEAN_THEOREM_NAMES[0]}' depends on axioms: [propext,\n", "")):
                self._assert_err("LEAN_UNEXPECTED_STDOUT", verifier.verify_lean4_file_live, lean_path)
            dup_none = f"'{engine.LEAN_THEOREM_NAMES[0]}' does not depend on any axioms\n" * 2
            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 0, dup_none, "")):
                self._assert_err("LEAN_DUPLICATE_THEOREM", verifier.verify_lean4_file_live, lean_path)
            dup_dep = f"'{engine.LEAN_THEOREM_NAMES[0]}' depends on axioms: [propext]\n" * 2
            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 0, dup_dep, "")):
                self._assert_err("LEAN_DUPLICATE_THEOREM", verifier.verify_lean4_file_live, lean_path)
            bad_ax = f"'{engine.LEAN_THEOREM_NAMES[0]}' depends on axioms: [Classical.choice]\n"
            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 0, bad_ax, "")):
                self._assert_err("LEAN_FORBIDDEN_AXIOM", verifier.verify_lean4_file_live, lean_path)
            with run_mock(ok_ver, subprocess.CompletedProcess(["lean"], 0, "\n".join(lines_ok[:-1]) + "\n", "")):
                self._assert_err("LEAN_THEOREM_SET_MISMATCH", verifier.verify_lean4_file_live, lean_path)


if __name__ == "__main__":
    unittest.main()
