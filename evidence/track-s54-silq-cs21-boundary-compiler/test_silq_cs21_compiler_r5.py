#!/usr/bin/env python3
"""Assertion-free verification, mutation-killing, Lean 4 kernel check & adversarial
test suite for Silq !T/qfree/mfree x DeepMind CS-21 Boundary Compiler.

100% pure Python 3 stdlib unittest, zero bare asserts, zero AST floats, zero float(),
zero .isdigit(), zero islink, scratch os.mkfifo only, zero mathematical RNG.
"""
from __future__ import annotations

import ast
import copy
import ctypes
import errno
from fractions import Fraction
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import silq_cs21_compiler_audit as audit  # noqa: E402
import silq_cs21_compiler_oracle as oracle  # noqa: E402


def _resign_payload(payload: dict[str, object]) -> dict[str, object]:
    p_sha = audit._sha256_canonical(payload)
    outer = {
        "schema_version": oracle.SCHEMA_VERSION,
        "track_id": oracle.TRACK_ID,
        "payload_sha256": p_sha,
        "payload": payload,
    }
    c_sha = audit._sha256_canonical(outer)
    return {
        "schema_version": oracle.SCHEMA_VERSION,
        "track_id": oracle.TRACK_ID,
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "payload": payload,
    }


def _call_main(argv: list[str]) -> tuple[int, str, str]:
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with mock.patch.object(sys, "stdout", out_buf), mock.patch.object(sys, "stderr", err_buf):
        rc = audit.main(argv)
    return rc, out_buf.getvalue(), err_buf.getvalue()


class TestSilqCS21CompilerR5(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cert = audit.build_standalone_certificate()
        cls.payload = cls.cert["payload"]

    def _expect_err(self, code: str, fn, *args, **kwargs) -> oracle.SilqCS21Error:
        with self.assertRaises(oracle.SilqCS21Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)
        return ctx.exception

    # ------------------------------------------------------------------
    # 1. Static AST & Hygiene + Lean 4 Source Integrity
    # ------------------------------------------------------------------
    def test_01_static_ast_hygiene_and_lean_file(self) -> None:
        files = (
            _THIS_DIR / "silq_cs21_compiler_oracle.py",
            _THIS_DIR / "silq_cs21_compiler_audit.py",
            _THIS_DIR / "test_silq_cs21_compiler_r5.py",
        )
        for fp in files:
            src = fp.read_text(encoding="utf-8")
            self.assertNotIn("\r", src)
            tree = ast.parse(src, filename=str(fp))
            for node in ast.walk(tree):
                self.assertNotIsInstance(node, ast.Assert, f"bare assert in {fp.name}")
                if isinstance(node, ast.Constant):
                    self.assertIsNot(type(node.value), float, f"float literal in {fp.name}")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotEqual(node.func.id, "float", f"float() call in {fp.name}")
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, ("isdigit", "islink", "is_symlink"), f"forbidden attr in {fp.name}")
                if isinstance(node, ast.Name) and node.id != "secrets":
                    self.assertFalse(node.id.lower().startswith("secret"), f"forbidden var {node.id} in {fp.name}")
                if isinstance(node, ast.arg):
                    self.assertFalse(node.arg.lower().startswith("secret"), f"forbidden arg {node.arg} in {fp.name}")

        lean_path = _THIS_DIR / oracle.LEAN_SOURCE_FILENAME
        self.assertTrue(lean_path.is_file())
        lean_src = lean_path.read_text(encoding="utf-8")
        self.assertNotIn("\r", lean_src)
        for thm in oracle.LEAN_THEOREM_NAMES:
            short = thm.split(".")[-1]
            self.assertIn(f"theorem {short}", lean_src)
            self.assertIn(f"#print axioms {short}", lean_src)

    # ------------------------------------------------------------------
    # 2. Strict Primitives, Formatters & Cost Billing Boundaries
    # ------------------------------------------------------------------
    def test_02_strict_primitives_and_formatters(self) -> None:
        oracle.require_ok(True, "OK", "ok")
        self._expect_err("BOOM", oracle.require_ok, False, "BOOM", "fail")
        self._expect_err("INVALID_CONDITION_TYPE", oracle.require_ok, 1, "X", "bad")
        self.assertIs(oracle.require_exact_bool(True), True)
        self.assertIs(oracle.require_exact_bool(False), False)
        self._expect_err("INVALID_BOOL_TYPE", oracle.require_exact_bool, 1)

        max_ok = (1 << oracle.MAX_INT_BITS) - 1
        self.assertEqual(oracle.require_exact_int(max_ok, "m", lo=0, hi=max_ok), max_ok)
        self.assertEqual(oracle.require_exact_int(0, "z", lo=0, hi=0), 0)
        self._expect_err("INVALID_INT_TYPE", oracle.require_exact_int, True)
        self._expect_err("INT_BIT_LIMIT", oracle.require_exact_int, 1 << oracle.MAX_INT_BITS)
        self._expect_err("INVALID_BOUND_TYPE", oracle.require_exact_int, 5, lo="0")
        self._expect_err("INVALID_BOUND_TYPE", oracle.require_exact_int, 5, hi="9")
        self._expect_err("INT_OUT_OF_RANGE", oracle.require_exact_int, -1, lo=0)
        self._expect_err("INT_OUT_OF_RANGE", oracle.require_exact_int, 10, hi=9)

        self.assertEqual(oracle.require_exact_fraction(Fraction(max_ok, 1)), Fraction(max_ok, 1))
        self.assertEqual(oracle.require_exact_fraction(Fraction(1, max_ok)), Fraction(1, max_ok))
        self._expect_err("INVALID_FRACTION_TYPE", oracle.require_exact_fraction, 3)
        self._expect_err("RATIONAL_BIT_LIMIT", oracle.require_exact_fraction, Fraction(1 << oracle.MAX_RATIONAL_BITS, 1))
        self._expect_err("RATIONAL_BIT_LIMIT", oracle.require_exact_fraction, Fraction(1, 1 << oracle.MAX_RATIONAL_BITS))

        self.assertEqual(oracle.format_rational(Fraction(5, 1)), "5")
        self.assertEqual(oracle.format_rational(Fraction(-3, 4)), "-3/4")
        self.assertEqual(oracle.format_decimal(Fraction(1, 200), 2), "0.01")
        self.assertEqual(oracle.format_decimal(Fraction(1, 201), 2), "0.00")
        self.assertEqual(oracle.format_decimal(Fraction(-1, 10000), 2), "0.00")
        self.assertEqual(oracle.format_decimal(Fraction(-7, 2), 0), "-4")
        self.assertEqual(oracle.format_decimal(Fraction(7, 2), 0), "4")
        self.assertEqual(oracle.format_decimal(Fraction(0), 0), "0")
        self.assertEqual(oracle.format_decimal(Fraction(1, 8), 12), "0.125000000000")
        self._expect_err("INT_OUT_OF_RANGE", oracle.format_decimal, Fraction(1), -1)
        self._expect_err("INT_OUT_OF_RANGE", oracle.format_decimal, Fraction(1), 13)

        self._expect_err("INT_OUT_OF_RANGE", oracle.compute_boundary_cost, -1, 0, 0, 0)
        self._expect_err("INT_OUT_OF_RANGE", oracle.compute_boundary_cost, 0, -1, 0, 0)
        self._expect_err("INT_OUT_OF_RANGE", oracle.compute_boundary_cost, 0, 0, -1, 0)
        self._expect_err("INT_OUT_OF_RANGE", oracle.compute_boundary_cost, 0, 0, 0, -1)
        z_cost = oracle.compute_boundary_cost(0, 0, 0, 0)
        self.assertEqual(z_cost["scaled_cost_hi_10"], 0)
        self.assertEqual(z_cost["scaled_cost_lo_160"], 0)

    # ------------------------------------------------------------------
    # 3. Exhaustive Compiler & Cut Evaluator Edge/Error Coverage
    # ------------------------------------------------------------------
    def test_03_compiler_and_cut_edge_guards(self) -> None:
        self._expect_err("INVALID_PROGRAM", oracle.compile_silq_cs21_program, [])
        base = {"name": "p", "annotation": "general", "params": [], "ops": [], "returns": []}
        self._expect_err("INVALID_PROGRAM", oracle.compile_silq_cs21_program, dict(base, name=""))
        self._expect_err("INVALID_PROGRAM", oracle.compile_silq_cs21_program, dict(base, name=123))
        self._expect_err("INVALID_ANNOTATION", oracle.compile_silq_cs21_program, dict(base, annotation="bad"))
        self._expect_err("INVALID_ANNOTATION", oracle.compile_silq_cs21_program, dict(base, annotation=1))
        self._expect_err("INVALID_PROGRAM", oracle.compile_silq_cs21_program, dict(base, params="x"))
        self._expect_err("INVALID_PROGRAM", oracle.compile_silq_cs21_program, dict(base, ops="x"))
        self._expect_err("INVALID_PROGRAM", oracle.compile_silq_cs21_program, dict(base, returns="x"))
        self._expect_err("INVALID_PARAM", oracle.compile_silq_cs21_program, dict(base, params=["bad"]))
        self._expect_err("INVALID_PARAM", oracle.compile_silq_cs21_program, dict(base, params=[{"name": "", "type": "B"}]))
        self._expect_err("INVALID_PARAM", oracle.compile_silq_cs21_program, dict(base, params=[{"name": 1, "type": "B"}]))
        self._expect_err("INVALID_PARAM", oracle.compile_silq_cs21_program, dict(base, params=[{"name": "a", "type": "B"}, {"name": "a", "type": "B"}]))
        self._expect_err("INVALID_TYPE", oracle.compile_silq_cs21_program, dict(base, params=[{"name": "a", "type": "Q"}]))
        self._expect_err("INVALID_TYPE", oracle.compile_silq_cs21_program, dict(base, params=[{"name": "a", "type": 1}]))
        self._expect_err("INVALID_OP", oracle.compile_silq_cs21_program, dict(base, ops=["bad"]))
        self._expect_err("UNKNOWN_OP", oracle.compile_silq_cs21_program, dict(base, ops=[{"op": "magic"}]))

        # qfree_gate & unitary_gate structural + semantic rejections
        p_q = {"name": "q", "annotation": "general", "params": [{"name": "a", "type": "B"}, {"name": "c", "type": "!B"}], "ops": [], "returns": ["a"]}
        self._expect_err("UNKNOWN_GATE", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "qfree_gate", "gate": "H", "target": "a"}]))
        self._expect_err("GATE_ARITY_MISMATCH", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "qfree_gate", "gate": "CNOT", "target": "a", "controls": []}]))
        self._expect_err("GATE_ARITY_MISMATCH", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "qfree_gate", "gate": "CNOT", "target": "a", "controls": "a"}]))
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_q, ops=[{"op": "qfree_gate", "gate": "X", "target": "missing"}]))["type_error_code"], "UNBOUND_VARIABLE")
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_q, ops=[{"op": "qfree_gate", "gate": "X", "target": "c"}]))["type_error_code"], "TYPE_MISMATCH")
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_q, ops=[{"op": "qfree_gate", "gate": "CNOT", "target": "a", "controls": ["c"]}]))["type_error_code"], "TYPE_MISMATCH")
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_q, ops=[{"op": "qfree_gate", "gate": "CNOT", "target": "a", "controls": ["missing"]}]))["type_error_code"], "TYPE_MISMATCH")

        # CCX qfree_gate + T unitary_gate cost billing
        p_ccx = {
            "name": "ccx_t",
            "annotation": "mfree",
            "params": [{"name": "a", "type": "B"}, {"name": "b", "type": "B"}, {"name": "t", "type": "B"}],
            "ops": [
                {"op": "qfree_gate", "gate": "CCX", "target": "t", "controls": ["a", "b"]},
                {"op": "unitary_gate", "gate": "T", "target": "t"},
                {"op": "unitary_gate", "gate": "CZ", "target": "t", "controls": ["a"]},
            ],
            "returns": ["a", "b", "t"],
        }
        r_ccx = oracle.compile_silq_cs21_program(p_ccx)
        self.assertTrue(r_ccx["well_typed"])
        self.assertEqual(r_ccx["cost"]["t_gates"], 8)
        self.assertEqual(r_ccx["clifford_ops"], 9)

        self._expect_err("UNKNOWN_GATE", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "unitary_gate", "gate": "X", "target": "a"}]))
        self._expect_err("GATE_ARITY_MISMATCH", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "unitary_gate", "gate": "CZ", "target": "a", "controls": []}]))
        self._expect_err("GATE_ARITY_MISMATCH", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "unitary_gate", "gate": "CZ", "target": "a", "controls": "a"}]))
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_q, ops=[{"op": "unitary_gate", "gate": "H", "target": "missing"}]))["type_error_code"], "TYPE_MISMATCH")
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_q, ops=[{"op": "unitary_gate", "gate": "H", "target": "c"}]))["type_error_code"], "TYPE_MISMATCH")
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_q, ops=[{"op": "unitary_gate", "gate": "CZ", "target": "a", "controls": ["c"]}]))["type_error_code"], "TYPE_MISMATCH")
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_q, ops=[{"op": "unitary_gate", "gate": "CZ", "target": "a", "controls": ["missing"]}]))["type_error_code"], "TYPE_MISMATCH")
        p_const = {"name": "pc", "annotation": "general", "params": [{"name": "a", "type": "B", "const": True}], "ops": [], "returns": []}
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_const, ops=[{"op": "unitary_gate", "gate": "H", "target": "a"}]))["type_error_code"], "CONST_MODIFICATION_FORBIDDEN")
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_const, ops=[{"op": "measure", "dst": "m", "src": "a", "ctrl_ops": 1}]))["type_error_code"], "CONST_MODIFICATION_FORBIDDEN")
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_const, ops=[{"op": "offload_classical", "dst": "m", "srcs": ["a"], "ctrl_ops": 1}]))["type_error_code"], "CONST_MODIFICATION_FORBIDDEN")
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_const, returns=["a"]))["type_error_code"], "CONST_CONSUMPTION_FORBIDDEN")

        # lifted_and, forget, dup, measure, offload, return edge cases
        self._expect_err("INVALID_OP", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "lifted_and", "dst": "", "a": "a", "b": "a"}]))
        self._expect_err("INVALID_OP", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "lifted_and", "dst": 1, "a": "a", "b": "a"}]))
        self._expect_err("INVALID_OP", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "lifted_and", "dst": "a", "a": "a", "b": "a"}]))
        for bad_la in (
            {"op": "lifted_and", "dst": "t", "a": "missing", "b": "a"},
            {"op": "lifted_and", "dst": "t", "a": "a", "b": "missing"},
            {"op": "lifted_and", "dst": "t", "a": "c", "b": "a"},
            {"op": "lifted_and", "dst": "t", "a": "a", "b": "c"},
        ):
            self.assertEqual(oracle.compile_silq_cs21_program(dict(p_q, ops=[bad_la]))["type_error_code"], "TYPE_MISMATCH")

        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_q, ops=[{"op": "forget", "var": "missing"}]))["type_error_code"], "UNCOMPUTATION_FAILED")
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_q, ops=[{"op": "forget", "var": "c"}]))["type_error_code"], "UNCOMPUTATION_FAILED")
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_q, ops=[{"op": "forget", "var": "a"}]))["type_error_code"], "UNCOMPUTATION_FAILED")

        self._expect_err("INVALID_OP", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "dup", "dst": "", "src": "c"}]))
        self._expect_err("INVALID_OP", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "dup", "dst": 1, "src": "c"}]))
        self._expect_err("INVALID_OP", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "dup", "dst": "c", "src": "c"}]))
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_q, ops=[{"op": "dup", "dst": "d", "src": "missing"}]))["type_error_code"], "UNBOUND_VARIABLE")

        self._expect_err("INVALID_OP", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "measure", "dst": "", "src": "a", "ctrl_ops": 1}]))
        self._expect_err("INVALID_OP", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "measure", "dst": 1, "src": "a", "ctrl_ops": 1}]))
        self._expect_err("INVALID_OP", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "measure", "dst": "c", "src": "a", "ctrl_ops": 1}]))
        self._expect_err("INT_OUT_OF_RANGE", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "measure", "dst": "m", "src": "a", "ctrl_ops": 0}]))
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_q, ops=[{"op": "measure", "dst": "m", "src": "missing", "ctrl_ops": 1}]))["type_error_code"], "TYPE_MISMATCH")
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_q, ops=[{"op": "measure", "dst": "m", "src": "c", "ctrl_ops": 1}]))["type_error_code"], "TYPE_MISMATCH")

        self._expect_err("INVALID_OP", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "offload_classical", "dst": "o", "srcs": [], "ctrl_ops": 1}]))
        self._expect_err("INVALID_OP", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "offload_classical", "dst": "o", "srcs": "a", "ctrl_ops": 1}]))
        self._expect_err("INVALID_OP", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "offload_classical", "dst": "", "srcs": ["a"], "ctrl_ops": 1}]))
        self._expect_err("INVALID_OP", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "offload_classical", "dst": 1, "srcs": ["a"], "ctrl_ops": 1}]))
        self._expect_err("INVALID_OP", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "offload_classical", "dst": "a", "srcs": ["a"], "ctrl_ops": 1}]))
        self._expect_err("INT_OUT_OF_RANGE", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "offload_classical", "dst": "o", "srcs": ["a"], "ctrl_ops": 0}]))
        self._expect_err("INT_OUT_OF_RANGE", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "offload_classical", "dst": "o", "srcs": ["a"], "ctrl_ops": 1, "and_count": -1}]))
        self._expect_err("INT_OUT_OF_RANGE", oracle.compile_silq_cs21_program, dict(p_q, ops=[{"op": "offload_classical", "dst": "o", "srcs": ["a"], "ctrl_ops": 1, "reset_count": -1}]))
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_q, ops=[{"op": "offload_classical", "dst": "o", "srcs": ["missing"], "ctrl_ops": 1}]))["type_error_code"], "UNBOUND_VARIABLE")

        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_q, returns=["missing"]))["type_error_code"], "UNBOUND_VARIABLE")
        self.assertEqual(oracle.compile_silq_cs21_program(dict(p_q, returns=["a", "a"]))["type_error_code"], "UNBOUND_VARIABLE")

        # Classical !B param in lifted is allowed (kills lifted+B+const BoolOp)
        p_lifted_cls = {"name": "lc", "annotation": "lifted", "params": [{"name": "c", "type": "!B", "const": False}], "ops": [], "returns": ["c"]}
        self.assertTrue(oracle.compile_silq_cs21_program(p_lifted_cls)["well_typed"])
        # Non-const classical !B dropped silently is allowed (kills block-exit !B vs const BoolOp)
        p_cls_drop = {"name": "cd", "annotation": "general", "params": [{"name": "c", "type": "!B"}], "ops": [], "returns": []}
        self.assertTrue(oracle.compile_silq_cs21_program(p_cls_drop)["well_typed"])
        # Const classical !B returned is allowed (kills return type==B and const BoolOp)
        p_cls_const_ret = {"name": "ccr", "annotation": "general", "params": [{"name": "c", "type": "!B", "const": True}], "ops": [], "returns": ["c"]}
        self.assertTrue(oracle.compile_silq_cs21_program(p_cls_const_ret)["well_typed"])
        # Offload const classical !B is allowed (kills offload type==B and const BoolOp)
        p_off_const_cls = {
            "name": "occ",
            "annotation": "general",
            "params": [{"name": "c", "type": "!B", "const": True}],
            "ops": [{"op": "offload_classical", "dst": "o", "srcs": ["c"], "ctrl_ops": 2}],
            "returns": ["o"],
        }
        self.assertTrue(oracle.compile_silq_cs21_program(p_off_const_cls)["well_typed"])
        # Measure invalidating dependent lifted_and -> block-exit drop rejected
        p_meas_inv = {
            "name": "mi",
            "annotation": "general",
            "params": [{"name": "a", "type": "B"}, {"name": "b", "type": "B", "const": True}],
            "ops": [
                {"op": "lifted_and", "dst": "tmp", "a": "a", "b": "b"},
                {"op": "measure", "dst": "ca", "src": "a", "ctrl_ops": 5},
            ],
            "returns": ["ca"],
        }
        self.assertEqual(oracle.compile_silq_cs21_program(p_meas_inv)["type_error_code"], "UNCONSUMED_QUANTUM_DROP")

        class _SubStr(str):
            pass

        self._expect_err("INVALID_ANNOTATION", oracle.compile_silq_cs21_program, dict(base, annotation=_SubStr("general")))
        self._expect_err("INVALID_TYPE", oracle.compile_silq_cs21_program, dict(base, params=[{"name": "a", "type": _SubStr("B")}]))

        # Mutating an unrelated variable must NOT invalidate an independent lifted_and temporary
        p_indep = {
            "name": "indep_uncomp",
            "annotation": "mfree",
            "params": [{"name": "a", "type": "B"}, {"name": "b", "type": "B", "const": True}, {"name": "c", "type": "B", "const": True}],
            "ops": [
                {"op": "lifted_and", "dst": "tmp", "a": "b", "b": "c"},
                {"op": "qfree_gate", "gate": "X", "target": "a"},
                {"op": "forget", "var": "tmp"},
            ],
            "returns": ["a"],
        }
        self.assertTrue(oracle.compile_silq_cs21_program(p_indep)["well_typed"])

        # Cut evaluator bounds
        self.assertIsNone(oracle.evaluate_boundary_cut(0))
        self.assertIsNone(oracle.evaluate_boundary_cut(63))
        self.assertIsNotNone(oracle.evaluate_boundary_cut(52))
        self._expect_err("INT_OUT_OF_RANGE", oracle.evaluate_boundary_cut, -1)
        self._expect_err("INT_OUT_OF_RANGE", oracle.evaluate_boundary_cut, 64)

    # ------------------------------------------------------------------
    # 4. Exact Four-Pillar Mathematical Payload Checks
    # ------------------------------------------------------------------
    def test_04_four_pillars_exact_values(self) -> None:
        pl = self.payload
        self.assertEqual(pl["track_id"], oracle.TRACK_ID)
        self.assertEqual(pl["portal_ref"], "Portal 54")
        self.assertEqual(pl["novelty_class"], "N1")

        p1 = pl["pillar1_typed_boundary_compiler"]
        self.assertTrue(p1["all_verified"])
        self.assertEqual((p1["valid_program_count"], p1["must_fail_program_count"]), (5, 8))
        self.assertEqual(p1["valid_programs"][0]["cost"]["t_gates"], 14)
        self.assertEqual(p1["valid_programs"][4]["cost"]["landauer_bits_lo_q"], "35")
        self.assertEqual(p1["valid_programs"][4]["cost"]["landauer_bits_hi_q"], "176/5")

        p2 = pl["pillar2_noncommutativity_and_cs21"]
        self.assertTrue(p2["all_verified"])
        self.assertEqual(p2["cs21_s44_mirage"]["apparent_t_speedup_b_vs_a_q"], "4")
        self.assertEqual(p2["cs21_s44_mirage"]["hidden_cost_share_b_q"], "5/6")
        self.assertEqual(p2["cs21_s44_mirage"]["full_cost_ratio_b_over_a_q"], "600/401")
        self.assertEqual(p2["s38_landauer_erasure_proof"]["and_power_product_2pow4H"], 27)
        self.assertEqual(p2["s38_landauer_erasure_proof"]["bracket_q"], ["19/16", "6/5"])
        self.assertEqual(p2["noncommutativity_16and_witness"]["order1_qfree_uncompute_then_measure"]["full_cost_lo_q"], "225")
        self.assertEqual(p2["noncommutativity_16and_witness"]["order2_measure_offload_before_uncompute"]["full_cost_lo_q"], "547/2")
        self.assertEqual(p2["noncommutativity_16and_witness"]["order2_measure_offload_before_uncompute"]["full_cost_hi_q"], "1368/5")

        p3 = pl["pillar3_pareto_boundary_optimizer"]
        self.assertTrue(p3["all_verified"])
        self.assertEqual(p3["optimal_boundary_cut"]["mask"], 52)
        self.assertEqual(p3["optimal_boundary_cut"]["placement"], "QQCQCC")
        self.assertEqual(p3["optimal_boundary_cut"]["cost"]["full_cost_lo_q"], "1729/4")
        self.assertEqual(p3["optimal_boundary_cut"]["cost"]["full_cost_hi_q"], "2162/5")
        self.assertEqual(p3["naive_min_t_cut"]["mask"], 62)
        self.assertEqual(p3["naive_min_t_penalty_ratio_q"], "1408/1081")
        self.assertEqual(p3["optimal_savings_vs_all_quantum_q"], "567/10")
        self.assertEqual(p3["optimal_savings_vs_naive_min_t_q"], "654/5")
        self.assertTrue(p3["branch_and_bound"]["matches_exhaustive_exact"])
        self.assertGreater(p3["branch_and_bound"]["nodes_pruned"], 0)
        self.assertEqual(len(p3["pareto_frontier"]), 4)

        p4 = pl["pillar4_lean4_kernel_contract"]
        self.assertTrue(p4["all_verified"])
        self.assertEqual(p4["lean_theorem_count"], 7)

    # ------------------------------------------------------------------
    # 5. Strict Parsers, Binding 3,321-Bit Cap & Canonical JSON
    # ------------------------------------------------------------------
    def test_05_parsers_binding_bit_cap_and_canonical_json(self) -> None:
        self.assertEqual(audit.require_hex64_lower_ascii("a" * 64), "a" * 64)
        self._expect_err("INVALID_HEX64", audit.require_hex64_lower_ascii, "a" * 63)
        self._expect_err("INVALID_HEX64", audit.require_hex64_lower_ascii, "A" * 64)
        self._expect_err("INVALID_HEX64", audit.require_hex64_lower_ascii, "g" * 64)
        self._expect_err("INVALID_STR", audit.require_hex64_lower_ascii, 123)

        self.assertEqual(audit.parse_exact_rational("0"), Fraction(0))
        self.assertEqual(audit.parse_exact_rational("-5"), Fraction(-5))
        self.assertEqual(audit.parse_exact_rational("-7/11"), Fraction(-7, 11))
        for bad in ("-0", "01", "", "-", "1/0", "1/1", "2/4", "1/2/3", "\u0661", "1/02", "9" * 1001):
            with self.assertRaises(oracle.SilqCS21Error):
                audit.parse_exact_rational(bad)

        max_ok = (1 << oracle.MAX_INT_BITS) - 1
        self.assertEqual(len(str(max_ok)), oracle.MAX_INT_DIGITS)
        rt = audit.parse_strict_json_text(f'{{"x":{max_ok}}}')
        self.assertEqual(rt["x"], max_ok)
        self.assertEqual(audit.canonical_json_bytes(rt), f'{{"x":{max_ok}}}'.encode("ascii"))

        self._expect_err("INT_BIT_LIMIT", audit._parse_bounded_int, "9" * 1000)
        self._expect_err("INT_BIT_LIMIT", audit.canonical_json_bytes, {"x": 1 << oracle.MAX_INT_BITS})
        self._expect_err("INT_BIT_LIMIT", audit.parse_strict_json_text, f'{{"x":{1 << oracle.MAX_INT_BITS}}}')
        self._expect_err("INT_DIGIT_LIMIT", audit.parse_strict_json_text, '{"x":1' + "0" * 4300 + "}")
        self._expect_err("FLOAT_LITERAL_FORBIDDEN", audit.parse_strict_json_text, '{"x":1.5}')
        self._expect_err("FLOAT_LITERAL_FORBIDDEN", audit.parse_strict_json_text, '{"x":1e2}')
        self._expect_err("NONFINITE_LITERAL_FORBIDDEN", audit.parse_strict_json_text, '{"x":NaN}')
        self._expect_err("DUPLICATE_JSON_KEY", audit.parse_strict_json_text, '{"a":1,"a":2}')
        self._expect_err("JSON_PARSE_ERROR", audit.parse_strict_json_text, '{"a":')
        self._expect_err("JSON_ROOT_NOT_OBJECT", audit.parse_strict_json_text, "[1,2]")
        self.assertEqual(audit.parse_strict_json_text("[1,null,true,false]", require_object=False), [1, None, True, False])
        self.assertEqual(audit.parse_strict_json_text('{"a":1}', max_bytes=7), {"a": 1})
        self._expect_err("JSON_TOO_LARGE", audit.parse_strict_json_text, '{"a":"0123456789"}', max_bytes=10)
        self._expect_err("INT_OUT_OF_RANGE", audit.parse_strict_json_text, "{}", max_bytes=1 << 100)
        self._expect_err("NUL_BYTE_FORBIDDEN", audit.parse_strict_json_text, '{"a":"\x00"}')
        self._expect_err("INVALID_UTF8_SURROGATE", audit.parse_strict_json_text, '{"a":"\ud800"}')
        self._expect_err("FORBIDDEN_JSON_TYPE", audit.canonical_json_bytes, {"a": {1, 2}})

        d64 = "[" * 64 + "0" + "]" * 64
        d65 = "[" * 65 + "0" + "]" * 65
        self.assertIsInstance(audit.parse_strict_json_text(d64, require_object=False), list)
        self._expect_err("JSON_DEPTH_LIMIT", audit.parse_strict_json_text, d65, require_object=False)
        self.assertEqual(audit.canonical_json_bytes({"b": "\u00e9", "a": 1}), b'{"a":1,"b":"\\u00e9"}')

    # ------------------------------------------------------------------
    # 6. Deep Secondary Auditor & 48 Re-Signed full_replay=False Tampers
    # ------------------------------------------------------------------
    def test_06_secondary_audit_and_resigned_tamper_matrix(self) -> None:
        self.assertTrue(audit.verify_certificate_dict(self.cert, full_replay=True)["valid"])
        self.assertTrue(audit.verify_certificate_dict(self.cert, full_replay=False)["valid"])
        self._expect_err("INVALID_BOOL_TYPE", audit.verify_certificate_dict, self.cert, full_replay=1)

        self._expect_err("INVALID_CERT_TYPE", audit.verify_certificate_dict, [])
        c_extra = copy.deepcopy(self.cert)
        c_extra["rogue"] = 1
        self._expect_err("INVALID_CERT_KEYS", audit.verify_certificate_dict, c_extra, full_replay=False)
        c_sch = copy.deepcopy(self.cert)
        c_sch["schema_version"] = "bad"
        self._expect_err("INVALID_SCHEMA", audit.verify_certificate_dict, c_sch, full_replay=False)
        c_tid = copy.deepcopy(self.cert)
        c_tid["track_id"] = "bad"
        self._expect_err("INVALID_TRACK_ID", audit.verify_certificate_dict, c_tid, full_replay=False)
        c_pt = copy.deepcopy(self.cert)
        c_pt["payload"] = []
        self._expect_err("INVALID_PAYLOAD_TYPE", audit.verify_certificate_dict, c_pt, full_replay=False)
        c_psha = copy.deepcopy(self.cert)
        c_psha["payload_sha256"] = "0" * 64
        self._expect_err("PAYLOAD_SHA256_MISMATCH", audit.verify_certificate_dict, c_psha, full_replay=False)
        c_csha = copy.deepcopy(self.cert)
        c_csha["certificate_sha256"] = "0" * 64
        self._expect_err("CERT_SHA256_MISMATCH", audit.verify_certificate_dict, c_csha, full_replay=False)
        self._expect_err("INVALID_SCHEMA_DICT", audit._req_dict, [], "row", frozenset())

        def mutate_and_expect(mutator, exp_code: str) -> None:
            pl = copy.deepcopy(self.payload)
            mutator(pl)
            resigned = _resign_payload(pl)
            self._expect_err(exp_code, audit.verify_certificate_dict, resigned, full_replay=False)

        tampers = [
            (lambda p: p.__setitem__("track_id", "WRONG"), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p.__setitem__("portal_ref", "Portal 99"), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p.__setitem__("novelty_class", "N0"), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p.__setitem__("prior_literature_n0", ["forged"]), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p.__setitem__("extra_top", 1), "INVALID_SCHEMA_KEYS"),
            (lambda p: p["cost_model_weights"].__setitem__("extra_w", 1), "INVALID_SCHEMA_KEYS"),
            (lambda p: p["cost_model_weights"].__setitem__("w_ctrl_q", "1/5"), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p["cost_model_weights"].__setitem__("landauer_and_bracket_q", {"forged": 1}), "INVALID_SCHEMA_LIST"),
            (lambda p: p["cost_model_weights"].__setitem__("landauer_and_bracket_q", ["19/16"]), "INVALID_SCHEMA_LIST"),
            (lambda p: p["cost_model_weights"].__setitem__("landauer_and_bracket_q", ["1/2", "6/5"]), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p["cost_model_weights"].__setitem__("landauer_and_bracket_q", ["19/16", "2/3"]), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p["cost_model_weights"].__setitem__("landauer_and_bracket_q", ["1/0", "6/5"]), "INVALID_RATIONAL"),
            (lambda p: p["pillar1_typed_boundary_compiler"].__setitem__("extra_p1", 1), "INVALID_SCHEMA_KEYS"),
            (lambda p: p["pillar1_typed_boundary_compiler"].__setitem__("valid_programs", {str(i): i for i in range(5)}), "INVALID_SCHEMA_LIST"),
            (lambda p: p["pillar1_typed_boundary_compiler"].__setitem__("valid_programs", []), "INVALID_SCHEMA_LIST"),
            (lambda p: p["pillar1_typed_boundary_compiler"]["valid_programs"][0].__setitem__("extra_v", 1), "INVALID_SCHEMA_KEYS"),
            (lambda p: p["pillar1_typed_boundary_compiler"]["valid_programs"][0].__setitem__("well_typed", 1), "INVALID_BOOL_TYPE"),
            (lambda p: p["pillar1_typed_boundary_compiler"]["valid_programs"][0]["cost"].__setitem__("extra_c", 1), "INVALID_SCHEMA_KEYS"),
            (lambda p: p["pillar1_typed_boundary_compiler"]["valid_programs"][0]["cost"].__setitem__("scaled_cost_hi_10", 999), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p["pillar1_typed_boundary_compiler"]["valid_programs"][0]["cost"].__setitem__("t_gates", True), "INVALID_INT_TYPE"),
            (lambda p: p["pillar1_typed_boundary_compiler"]["must_fail_programs"][0].__setitem__("extra_f", 1), "INVALID_SCHEMA_KEYS"),
            (lambda p: p["pillar1_typed_boundary_compiler"]["must_fail_programs"][0].__setitem__("well_typed", True), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p["pillar1_typed_boundary_compiler"].__setitem__("valid_program_count", True), "INVALID_INT_TYPE"),
            (lambda p: p["pillar2_noncommutativity_and_cs21"].__setitem__("extra_p2", 1), "INVALID_SCHEMA_KEYS"),
            (lambda p: p["pillar2_noncommutativity_and_cs21"]["cs21_s44_mirage"].__setitem__("extra_m", 1), "INVALID_SCHEMA_KEYS"),
            (lambda p: p["pillar2_noncommutativity_and_cs21"]["cs21_s44_mirage"].__setitem__("full_cost_ratio_b_over_a_q", "1/2"), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p["pillar2_noncommutativity_and_cs21"]["cs21_s44_mirage"]["circuit_a_qfree_clean"].__setitem__("scaled_cost_hi_10", 0), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p["pillar2_noncommutativity_and_cs21"]["cs21_s44_mirage"].__setitem__("ordering_reversed_by_full_cost", 1), "INVALID_BOOL_TYPE"),
            (lambda p: p["pillar2_noncommutativity_and_cs21"]["s38_landauer_erasure_proof"].__setitem__("extra_l", 1), "INVALID_SCHEMA_KEYS"),
            (lambda p: p["pillar2_noncommutativity_and_cs21"]["s38_landauer_erasure_proof"].__setitem__("and_power_product_2pow4H", 28), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p["pillar2_noncommutativity_and_cs21"]["s38_landauer_erasure_proof"].__setitem__("toffoli_3bit_power_product", True), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p["pillar2_noncommutativity_and_cs21"]["s38_landauer_erasure_proof"].__setitem__("p_and_pow_4", True), "INVALID_INT_TYPE"),
            (lambda p: p["pillar2_noncommutativity_and_cs21"]["noncommutativity_16and_witness"].__setitem__("extra_n", 1), "INVALID_SCHEMA_KEYS"),
            (lambda p: p["pillar2_noncommutativity_and_cs21"]["noncommutativity_16and_witness"].__setitem__("noncommutativity_strict_regression_even_at_lo", 1), "INVALID_BOOL_TYPE"),
            (lambda p: p["pillar3_pareto_boundary_optimizer"].__setitem__("extra_p3", 1), "INVALID_SCHEMA_KEYS"),
            (lambda p: p["pillar3_pareto_boundary_optimizer"]["branch_and_bound"].__setitem__("extra_bb", 1), "INVALID_SCHEMA_KEYS"),
            (lambda p: p["pillar3_pareto_boundary_optimizer"]["branch_and_bound"].__setitem__("optimal_mask", 32), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p["pillar3_pareto_boundary_optimizer"]["branch_and_bound"].__setitem__("nodes_pruned", 0), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p["pillar3_pareto_boundary_optimizer"]["branch_and_bound"].__setitem__("matches_exhaustive_exact", 1), "INVALID_BOOL_TYPE"),
            (lambda p: p["pillar3_pareto_boundary_optimizer"]["optimal_boundary_cut"].__setitem__("extra_oc", 1), "INVALID_SCHEMA_KEYS"),
            (lambda p: p["pillar3_pareto_boundary_optimizer"]["optimal_boundary_cut"].__setitem__("mask", True), "INVALID_INT_TYPE"),
            (lambda p: p["pillar3_pareto_boundary_optimizer"]["pareto_frontier"][0].__setitem__("extra_pf", 1), "INVALID_SCHEMA_KEYS"),
            (lambda p: p["pillar3_pareto_boundary_optimizer"]["pareto_frontier"][0].__setitem__("full_cost_hi_q", "1"), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p["pillar3_pareto_boundary_optimizer"].__setitem__("pareto_frontier", []), "INVALID_SCHEMA_LIST"),
            (lambda p: p["pillar4_lean4_kernel_contract"].__setitem__("extra_p4", 1), "INVALID_SCHEMA_KEYS"),
            (lambda p: p["pillar4_lean4_kernel_contract"]["pinned_integer_identities"].__setitem__("extra_id", 1), "INVALID_SCHEMA_KEYS"),
            (lambda p: p["pillar4_lean4_kernel_contract"]["pinned_integer_identities"].__setitem__("pareto_opt_mask52_hi10", 9999), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p["pillar4_lean4_kernel_contract"].__setitem__("lean_theorem_count", 6), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p["pillar4_lean4_kernel_contract"].__setitem__("zero_sorry_zero_native_decide_contract", 1), "INVALID_BOOL_TYPE"),
            (lambda p: p["summary"].__setitem__("extra_s", 1), "INVALID_SCHEMA_KEYS"),
            (lambda p: p["summary"].__setitem__("pillar_count", True), "INVALID_INT_TYPE"),
            (lambda p: p["summary"].__setitem__("all_four_pillars_verified", 1), "INVALID_BOOL_TYPE"),
            (lambda p: p["summary"].__setitem__("float_count_on_trust_path", 1), "SECONDARY_AUDIT_FAILED"),
            (lambda p: p["summary"].__setitem__("rng_calls", 1), "SECONDARY_AUDIT_FAILED"),
        ]
        self.assertGreaterEqual(len(tampers), 48)
        for mutator, exp_code in tampers:
            mutate_and_expect(mutator, exp_code)

        with mock.patch.object(audit, "build_standalone_certificate", return_value={"payload_sha256": "0" * 64}):
            self._expect_err("REPLAY_MISMATCH", audit.verify_certificate_dict, self.cert, full_replay=True)

        # Direct secondary_audit_payload rejects runtime floats and builtin subclasses
        class _SubInt(int):
            pass

        class _SubStr(str):
            pass

        class _SubList(list):
            pass

        pl_flt = copy.deepcopy(self.payload)
        pl_flt["pillar4_lean4_kernel_contract"]["pinned_integer_identities"]["cs21_circuit_a_hi10"] = 4010 / 1
        self._expect_err("FORBIDDEN_JSON_TYPE", audit.secondary_audit_payload, pl_flt)

        pl_si = copy.deepcopy(self.payload)
        pl_si["pillar4_lean4_kernel_contract"]["pinned_integer_identities"]["cs21_circuit_a_hi10"] = _SubInt(4010)
        self._expect_err("FORBIDDEN_JSON_TYPE", audit.secondary_audit_payload, pl_si)

        pl_ss = copy.deepcopy(self.payload)
        pl_ss["track_id"] = _SubStr(oracle.TRACK_ID)
        self._expect_err("FORBIDDEN_JSON_TYPE", audit.secondary_audit_payload, pl_ss)

        pl_sl = copy.deepcopy(self.payload)
        pl_sl["prior_literature_n0"] = _SubList(pl_sl["prior_literature_n0"])
        self._expect_err("FORBIDDEN_JSON_TYPE", audit.secondary_audit_payload, pl_sl)

    # ------------------------------------------------------------------
    # 7. Zone-B File I/O (Scratch mkfifo ONLY), Symlink/PWD/Hardlink & CLI
    # ------------------------------------------------------------------
    def test_07_zone_b_io_and_cli(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            cert_path = root / "sub" / "cert.json"
            wres = audit.write_certificate_file(cert_path)
            self.assertTrue(wres["written"])
            self.assertEqual(stat.S_IMODE(os.lstat(cert_path).st_mode), 0o600)
            active_umask = os.umask(0o022)
            os.umask(active_umask)
            self.assertEqual(stat.S_IMODE(os.lstat(root / "sub").st_mode), 0o755 & ~active_umask)
            cres = audit.check_certificate_file(cert_path, full_replay=True)
            self.assertTrue(cres["valid"])
            self.assertEqual(cres["file_sha256"], wres["file_sha256"])

            missing_dir = root / "never_created"
            self._expect_err("FILE_READ_ERROR", audit.read_regular_bytes_capped, missing_dir / "x.json")
            self.assertFalse(missing_dir.exists())

            crlf_p = root / "crlf.json"
            crlf_p.write_bytes(cert_path.read_bytes().replace(b"\n", b"\r\n"))
            self._expect_err("CRLF_FORBIDDEN", audit.check_certificate_file, crlf_p)

            nolf_p = root / "nolf.json"
            nolf_p.write_bytes(cert_path.read_bytes()[:-1])
            self._expect_err("MISSING_TRAILING_LF", audit.check_certificate_file, nolf_p)

            badu_p = root / "badu.json"
            badu_p.write_bytes(b"\xff\xfe\n")
            self._expect_err("INVALID_UTF8", audit.check_certificate_file, badu_p)

            pretty_p = root / "pretty.json"
            pretty_p.write_bytes((json.dumps(self.cert, indent=2) + "\n").encode("utf-8"))
            self._expect_err("NON_CANONICAL_BYTES", audit.check_certificate_file, pretty_p)

            sym_leaf = root / "sym_leaf.json"
            os.symlink(cert_path, sym_leaf)
            self._expect_err("SYMLINK_FORBIDDEN", audit.read_regular_bytes_capped, sym_leaf)
            self._expect_err("SYMLINK_FORBIDDEN", audit.write_regular_bytes_safe, sym_leaf, b"x")

            sym_dir = root / "sym_dir"
            os.symlink(root / "sub", sym_dir)
            self._expect_err("SYMLINK_FORBIDDEN", audit.read_regular_bytes_capped, sym_dir / "cert.json")
            self._expect_err("SYMLINK_FORBIDDEN", audit.write_regular_bytes_safe, sym_dir / "new.json", b"x")

            self._expect_err("NOT_A_REGULAR_FILE", audit.read_regular_bytes_capped, root / "sub")
            self._expect_err("NOT_A_REGULAR_FILE", audit.write_regular_bytes_safe, root / "sub", b"x")
            self._expect_err("NOT_A_REGULAR_FILE", audit.read_regular_bytes_capped, Path("/"))
            self._expect_err("NOT_A_REGULAR_FILE", audit.read_regular_bytes_capped, missing_dir / "..")

            fifo_p = root / "pipe.fifo"
            os.mkfifo(fifo_p)
            self._expect_err("NOT_A_REGULAR_FILE", audit.read_regular_bytes_capped, fifo_p)
            self._expect_err("NOT_A_REGULAR_FILE", audit.write_regular_bytes_safe, fifo_p, b"x")

            hl_p = root / "hardlink.json"
            os.link(cert_path, hl_p)
            self._expect_err("HARDLINK_FORBIDDEN", audit.write_regular_bytes_safe, hl_p, b"x")
            os.unlink(hl_p)

            big_p = root / "big70k.bin"
            big_p.write_bytes(b"A" * 70_000)
            self.assertEqual(len(audit.read_regular_bytes_capped(big_p, "exact", 70_000)), 70_000)
            self._expect_err("FILE_TOO_LARGE", audit.read_regular_bytes_capped, big_p, "big", 65_536)
            if Path("/proc/kallsyms").exists():
                self._expect_err("FILE_TOO_LARGE", audit.read_regular_bytes_capped, Path("/proc/kallsyms"), "ks", 1024)

            fake_st = os.stat_result((stat.S_IFREG | 0o600, 1, 1, 2, 0, 0, 1, 0, 0, 0))
            with mock.patch.object(os, "fstat", return_value=fake_st):
                self._expect_err("HARDLINK_FORBIDDEN", audit.write_regular_bytes_safe, root / "race_nlink.bin", b"x")

            self._expect_err("INVALID_PATH_TYPE", audit.read_regular_bytes_capped, str(cert_path))  # type: ignore[arg-type]
            self._expect_err("INVALID_PAYLOAD_BYTES", audit.write_regular_bytes_safe, root / "t.bin", "str")  # type: ignore[arg-type]

            orig_cwd = os.getcwd()
            orig_pwd = os.environ.get("PWD")
            try:
                os.chdir(root)
                os.environ["PWD"] = str(root)
                rel_p = Path("rel_out.json")
                audit.write_regular_bytes_safe(rel_p, b"{}\n")
                self.assertEqual(audit.read_regular_bytes_capped(rel_p), b"{}\n")

                # Stale/non-existent or mismatched-inode PWD must not fail valid relative reads
                os.environ["PWD"] = str(root / "stale_nonexistent_pwd")
                self.assertEqual(audit.read_regular_bytes_capped(rel_p), b"{}\n")
                os.environ["PWD"] = str(root / "sub")
                self.assertEqual(audit.read_regular_bytes_capped(rel_p), b"{}\n")

                # Symlinked PWD matching current directory inode MUST be rejected
                os.chdir(root / "sub")
                os.environ["PWD"] = str(sym_dir)
                self._expect_err("SYMLINK_ANCESTOR_FORBIDDEN", audit.read_regular_bytes_capped, Path("cert.json"))

                ghost = root / "ghost_dir"
                ghost.mkdir()
                os.chdir(ghost)
                os.environ["PWD"] = str(ghost)
                ghost.rmdir()
                self._expect_err("CWD_UNAVAILABLE", audit.read_regular_bytes_capped, Path("rel.json"))
            finally:
                os.chdir(orig_cwd)
                if orig_pwd is None:
                    os.environ.pop("PWD", None)
                else:
                    os.environ["PWD"] = orig_pwd

            # macOS Darwin root-owned system-prefix normalization (all branches + BoolOp kills)
            root_lnk = SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_uid=0)
            root_dir = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
            user_lnk = SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_uid=1000)

            def _fake_readlink(p: str) -> str:
                if p == "/var":
                    return "private/var"
                if p == "/tmp":
                    return "/private/tmp"
                if p == "/etc":
                    return "private/etc"
                raise OSError("unexpected readlink")

            with (
                mock.patch.object(audit.sys, "platform", "darwin"),
                mock.patch.object(audit.os, "lstat", return_value=root_lnk),
                mock.patch.object(audit.os, "readlink", side_effect=_fake_readlink),
            ):
                self.assertEqual(
                    audit._normalize_darwin_system_prefix(Path("/var/folders/xx/cert.json")),
                    Path("/private/var/folders/xx/cert.json"),
                )
                self.assertEqual(
                    audit._normalize_darwin_system_prefix(Path("/tmp/cert.json")),
                    Path("/private/tmp/cert.json"),
                )
                self.assertEqual(
                    audit._normalize_darwin_system_prefix(Path("/etc/cert.json")),
                    Path("/private/etc/cert.json"),
                )
                self.assertEqual(
                    audit._normalize_darwin_system_prefix(Path("/opt/cert.json")),
                    Path("/opt/cert.json"),
                )
                self.assertEqual(
                    audit._normalize_darwin_system_prefix(Path("a/var/folders/xx/cert.json")),
                    Path("a/var/folders/xx/cert.json"),
                )
                self.assertEqual(
                    audit._normalize_darwin_system_prefix(Path("/tmp"), allow_exact=True),
                    Path("/private/tmp"),
                )
                self.assertEqual(
                    audit._normalize_darwin_system_prefix(Path("/"), allow_exact=True),
                    Path("/"),
                )
                self.assertEqual(audit._normalize_darwin_system_prefix(Path("/tmp")), Path("/tmp"))
                self.assertEqual(
                    audit._normalize_darwin_system_prefix(Path("/tmp/../etc/passwd")),
                    Path("/tmp/../etc/passwd"),
                )
            for bad_stat in (root_dir, user_lnk):
                with (
                    mock.patch.object(audit.sys, "platform", "darwin"),
                    mock.patch.object(audit.os, "lstat", return_value=bad_stat),
                    mock.patch.object(audit.os, "readlink", side_effect=_fake_readlink),
                ):
                    self.assertEqual(
                        audit._normalize_darwin_system_prefix(Path("/var/folders/xx/cert.json")),
                        Path("/var/folders/xx/cert.json"),
                    )
            with (
                mock.patch.object(audit.sys, "platform", "darwin"),
                mock.patch.object(audit.os, "lstat", return_value=root_lnk),
                mock.patch.object(audit.os, "readlink", return_value="private/evil"),
            ):
                self.assertEqual(
                    audit._normalize_darwin_system_prefix(Path("/var/folders/xx/cert.json")),
                    Path("/var/folders/xx/cert.json"),
                )
            with (
                mock.patch.object(audit.sys, "platform", "darwin"),
                mock.patch.object(audit.os, "lstat", side_effect=OSError("no access")),
            ):
                self.assertEqual(
                    audit._normalize_darwin_system_prefix(Path("/var/folders/xx/cert.json")),
                    Path("/var/folders/xx/cert.json"),
                )
            with (
                mock.patch.object(audit.sys, "platform", "linux"),
                mock.patch.object(audit.os, "lstat", return_value=root_lnk),
                mock.patch.object(audit.os, "readlink", side_effect=_fake_readlink),
            ):
                self.assertEqual(
                    audit._normalize_darwin_system_prefix(Path("/var/folders/xx/cert.json")),
                    Path("/var/folders/xx/cert.json"),
                )

            rc, out, err = _call_main([])
            self.assertEqual((rc, err), (0, ""))
            self.assertIn("OK ", out)

            rc, out, err = _call_main(["--standalone", "--json"])
            self.assertEqual((rc, err), (0, ""))
            self.assertEqual(json.loads(out)["certificate_sha256"], self.cert["certificate_sha256"])

            cli_w = root / "cli_w.json"
            rc, out, err = _call_main(["--write", str(cli_w), "--json"])
            self.assertEqual((rc, err), (0, ""))
            self.assertTrue(json.loads(out)["written"])

            rc, out, err = _call_main(["--check", str(cli_w), "--json"])
            self.assertEqual((rc, err), (0, ""))
            self.assertTrue(json.loads(out)["valid"])

            cli_w2 = root / "cli_w2.json"
            rc, out, err = _call_main([f"--write={cli_w2}"])
            self.assertEqual((rc, err), (0, ""))
            rc, out, err = _call_main([f"--check={cli_w2}", "--json"])
            self.assertEqual((rc, err), (0, ""))
            self.assertTrue(json.loads(out)["valid"])

            for bad_argv, exp_code in (
                (["--unknown"], "UNKNOWN_FLAG"),
                (["--json", "--json"], "DUPLICATE_FLAG"),
                (["--standalone", "--check", str(cli_w)], "CONFLICTING_MODE"),
                (["--check", str(cli_w), "--standalone"], "CONFLICTING_MODE"),
                (["--standalone", f"--check={cli_w}"], "CONFLICTING_MODE"),
                (["--check"], "MISSING_PATH_ARG"),
                (["--check", ""], "INVALID_PATH_ARG"),
                (["--check", "-bad"], "INVALID_PATH_ARG"),
                (["--check="], "INVALID_PATH_ARG"),
                (["--write=-bad"], "INVALID_PATH_ARG"),
                (["--check", "a\x00b"], "NUL_BYTE_FORBIDDEN"),
            ):
                rc, _o, e = _call_main(bad_argv)
                self.assertEqual(rc, 2)
                self.assertEqual(json.loads(e)["error_code"], exp_code)

            rc, _o, e = _call_main("not-a-list")  # type: ignore[arg-type]
            self.assertEqual(rc, 2)
            self.assertEqual(json.loads(e)["error_code"], "INVALID_ARGV")

    # ------------------------------------------------------------------
    # 8. Concurrency & Kernel Races (16T/80T + 550 renameat2 + 550 hardlink)
    # ------------------------------------------------------------------
    def test_08_concurrency_and_kernel_races(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()

            errs: list[Exception] = []
            def w_distinct(idx: int) -> None:
                try:
                    p = root / f"d_{idx}.bin"
                    audit.write_regular_bytes_safe(p, f"payload-{idx}\n".encode("ascii"))
                    if stat.S_IMODE(os.lstat(p).st_mode) != 0o600:
                        raise RuntimeError("bad mode")
                except Exception as exc:
                    errs.append(exc)

            ts = [threading.Thread(target=w_distinct, args=(i,)) for i in range(16)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            self.assertEqual(errs, [])

            shared = root / "shared.bin"
            def w_same(idx: int) -> None:
                try:
                    audit.write_regular_bytes_safe(shared, f"v-{idx}\n".encode("ascii"))
                except Exception as exc:
                    errs.append(exc)

            for count in (16, 80):
                ts = [threading.Thread(target=w_same, args=(i,)) for i in range(count)]
                for t in ts:
                    t.start()
                for t in ts:
                    t.join()
            self.assertEqual(errs, [])
            self.assertEqual([p.name for p in root.iterdir() if p.name.endswith(".tmp")], [])

            if sys.platform == "linux":
                libc = ctypes.CDLL(None, use_errno=True)
                renameat2 = getattr(libc, "renameat2", None)
            else:
                renameat2 = None
            if renameat2 is not None:
                rename_exchange = 2
                at_fdcwd = -100
                victim_dir = root / "victim_outside"
                victim_dir.mkdir()
                real_sub = root / "race_slot_a"
                real_sub.mkdir()
                sym_sub = root / "race_slot_b"
                os.symlink(victim_dir, sym_sub)

                stop_flag = threading.Event()
                b_a = os.fsencode(str(real_sub))
                b_b = os.fsencode(str(sym_sub))

                def flipper() -> None:
                    while not stop_flag.is_set():
                        renameat2(at_fdcwd, b_a, at_fdcwd, b_b, rename_exchange)

                fl = threading.Thread(target=flipper)
                fl.start()
                try:
                    for i in range(550):
                        try:
                            audit.write_regular_bytes_safe(real_sub / "x.bin", f"{i}\n".encode("ascii"))
                        except oracle.SilqCS21Error:
                            pass
                finally:
                    stop_flag.set()
                    fl.join()
                self.assertEqual(list(victim_dir.iterdir()), [])

            hl_dir = root / "hl_race"
            hl_dir.mkdir()
            hl_target = hl_dir / "target.bin"
            hl_victim = hl_dir / "victim.bin"
            hl_victim.write_bytes(b"ORIGINAL_VICTIM\n")

            stop_hl = threading.Event()
            def hl_attacker() -> None:
                while not stop_hl.is_set():
                    try:
                        os.unlink(hl_target)
                    except OSError:
                        pass
                    try:
                        os.link(hl_victim, hl_target)
                    except OSError:
                        pass

            ha = threading.Thread(target=hl_attacker)
            ha.start()
            try:
                for i in range(550):
                    try:
                        audit.write_regular_bytes_safe(hl_target, f"safe-{i}\n".encode("ascii"))
                    except oracle.SilqCS21Error:
                        pass
            finally:
                stop_hl.set()
                ha.join()
            self.assertEqual(hl_victim.read_bytes(), b"ORIGINAL_VICTIM\n")

    # ------------------------------------------------------------------
    # 9. Live Lean 4.36.0 Kernel Elaboration & Axiom Audit
    # ------------------------------------------------------------------
    def test_09_live_lean4_kernel_check(self) -> None:
        lean_path = _THIS_DIR / oracle.LEAN_SOURCE_FILENAME
        lean_bin = shutil.which("lean")
        if lean_bin is None:
            for cand in (Path.home() / ".local" / "bin" / "lean", Path.home() / ".elan" / "bin" / "lean"):
                if cand.is_file():
                    lean_bin = str(cand)
                    break
        # The kernel check must never be vacuously skipped: a missing lean binary is a failure.
        self.assertIsNotNone(lean_bin, "lean binary not found on PATH, ~/.local/bin or ~/.elan/bin; kernel check must not be skipped")
        ver = subprocess.run([lean_bin, "--version"], capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(ver.returncode, 0, ver.stderr)
        self.assertTrue(
            ver.stdout.startswith("Lean (version 4.36.0"),
            f"expected Lean 4.36.0 toolchain, got: {ver.stdout!r}",
        )
        proc = subprocess.run([lean_bin, str(lean_path)], capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for forbidden in ("sorryAx", "ofReduceBool", "trustCompiler"):
            self.assertNotIn(forbidden, proc.stdout)
        for thm in oracle.LEAN_THEOREM_NAMES:
            self.assertIn(thm, proc.stdout)

    # ------------------------------------------------------------------
    # 10. Fail-Closed OSError Handlers (mutation coverage of the hardened
    #     I/O error paths: mocked EACCES/EIO on open/read/write/replace)
    # ------------------------------------------------------------------
    def test_10_fail_closed_oserror_handlers(self) -> None:
        eacces = OSError(errno.EACCES, "mocked EACCES")
        eio = OSError(errno.EIO, "mocked EIO")
        real_open = os.open

        # (a) root open inside _check_pwd_no_symlinks (audit line ~260): with an
        # absolute PWD matching ".", the first os.open("/") must fail closed.
        with mock.patch.dict(os.environ, {"PWD": os.getcwd()}):
            def open_root_only(path, flags, *a, **kw):
                if path == "/" and not kw.get("dir_fd"):
                    raise eacces
                return real_open(path, flags, *a, **kw)

            with mock.patch("os.open", side_effect=open_root_only):
                self._expect_err(
                    "CWD_UNAVAILABLE",
                    audit.write_regular_bytes_safe,
                    Path("s54_rel_probe.tmp"),
                    b"x",
                    "probe",
                )

        # (b) root open inside _open_dir_chain (audit line ~300): non-absolute PWD
        # short-circuits _check_pwd_no_symlinks, so the ancestor walk's os.open("/")
        # is the first root open and must fail closed.
        with mock.patch.dict(os.environ, {"PWD": "relative"}):
            with mock.patch("os.open", side_effect=lambda p, f, *a, **kw: (_ for _ in ()).throw(eacces) if p == "/" and not kw.get("dir_fd") else real_open(p, f, *a, **kw)):
                self._expect_err(
                    "FILE_WRITE_ERROR",
                    audit.write_regular_bytes_safe,
                    Path("s54_rel_probe.tmp"),
                    b"x",
                    "probe",
                )

        with tempfile.TemporaryDirectory() as td:
            tgt = Path(td) / "out.bin"

            # (c) read failure inside read_regular_bytes_capped (audit line ~370).
            src = Path(td) / "in.bin"
            src.write_bytes(b"hello\n")
            with mock.patch("os.read", side_effect=eio):
                self._expect_err("FILE_READ_ERROR", audit.read_regular_bytes_capped, src, "probe", 1024)

            # (d) lstat failure on the leaf (audit line ~389).
            with mock.patch("os.lstat", side_effect=eacces):
                self._expect_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, tgt, b"x", "probe")

            # (e) temp-file creation failure (audit line ~415): every O_CREAT|O_EXCL
            # probe fails with EACCES, so the first attempt must fail closed with
            # "create temp failed" (not "exhausted temp file slots").
            def open_no_create(path, flags, *a, **kw):
                if flags & os.O_CREAT:
                    raise eacces
                return real_open(path, flags, *a, **kw)

            with mock.patch("os.open", side_effect=open_no_create):
                with self.assertRaises(oracle.SilqCS21Error) as ctx:
                    audit.write_regular_bytes_safe(tgt, b"x", "probe")
                self.assertEqual(ctx.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("create temp failed", str(ctx.exception))

            # (f) write/fsync failure (audit line ~432).
            with mock.patch("os.write", side_effect=eio):
                self._expect_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, tgt, b"x", "probe")

            # (g) atomic replace failure (audit line ~443).
            with mock.patch("os.replace", side_effect=eacces):
                self._expect_err("FILE_WRITE_ERROR", audit.write_regular_bytes_safe, tgt, b"x", "probe")
            self.assertFalse(tgt.exists())

            # (h) mkdir failure on a missing parent (audit line ~314).
            nested = Path(td) / "newdir" / "out.bin"
            with mock.patch("os.mkdir", side_effect=eacces):
                with self.assertRaises(oracle.SilqCS21Error) as ctx:
                    audit.write_regular_bytes_safe(nested, b"x", "probe")
                self.assertEqual(ctx.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("mkdir failed", str(ctx.exception))

            # (i) reopen failure after successful mkdir (audit line ~320).
            state = {"n": 0}

            def open_flaky_dir(path, flags, *a, **kw):
                if path == "newdir" and not (flags & os.O_CREAT):
                    state["n"] += 1
                    if state["n"] == 1:
                        raise FileNotFoundError(errno.ENOENT, "mocked ENOENT")
                    raise eacces
                return real_open(path, flags, *a, **kw)

            with mock.patch("os.open", side_effect=open_flaky_dir):
                with self.assertRaises(oracle.SilqCS21Error) as ctx:
                    audit.write_regular_bytes_safe(nested, b"x", "probe")
                self.assertEqual(ctx.exception.code, "FILE_WRITE_ERROR")
                self.assertIn("cannot open created dir", str(ctx.exception))
            self.assertFalse(nested.exists())


if __name__ == "__main__":
    unittest.main()
