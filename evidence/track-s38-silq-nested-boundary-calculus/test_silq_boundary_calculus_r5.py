#!/usr/bin/env python3
"""Track S38: Comprehensive R5 Adversarial, Concurrency, Mutation & Algebra Test Suite.

Zero AST float literals, zero float() calls, zero bare asserts, zero .isdigit(),
zero RNG, zero external dependencies.
"""
from __future__ import annotations

import copy
import ctypes
from fractions import Fraction
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any
import unittest
from unittest import mock

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import silq_boundary_calculus_audit as audit
import silq_boundary_calculus_oracle as oracle

# Runtime float constructed without AST float literal or float() call
_RUNTIME_FLOAT: Any = json.loads("1.5")


def _require_real_tmpdir_or_skip(case: unittest.TestCase) -> None:
    """Skip tempdir-based symlink-guard tests cleanly when TMPDIR traverses a symlink (e.g. macOS /var -> /private/var)."""
    tmp_root = Path(tempfile.gettempdir())
    for anc in (tmp_root, *tmp_root.parents):
        if anc.is_symlink():
            case.skipTest(f"TMPDIR traverses symlink ancestor {anc}; set TMPDIR to a symlink-free path")


class _EvilInt(int):
    pass


class _EvilStr(str):
    pass


class _EvilDict(dict):
    pass


class _EvilList(list):
    pass


class _EvilTuple(tuple):
    pass


class _EvilFrac(Fraction):
    pass


class _EvilPath(type(Path("."))):
    pass


class Test01ZoneBPrimitivesAndParsers(unittest.TestCase):
    """Exact type guards, bounded int/rational/decimal parsers, iterative JSON tree validator."""

    def _expect_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.SilqBoundaryError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_strict_type_and_hex64_boundaries(self) -> None:
        self.assertIs(oracle.require_bool(True, "b"), True)
        self.assertIs(oracle.require_bool(False, "b"), False)
        self._expect_err("INVALID_BOOL", oracle.require_bool, 1, "b")
        self._expect_err("INVALID_BOOL", oracle.require_bool, "true", "b")

        self.assertEqual(oracle.require_int(0, "n", lo=0, hi=5), 0)
        self.assertEqual(oracle.require_int(5, "n", lo=0, hi=5), 5)
        self._expect_err("INVALID_INT", oracle.require_int, True, "n")
        self._expect_err("INVALID_INT", oracle.require_int, _EvilInt(3), "n")
        self._expect_err("INT_OUT_OF_RANGE", oracle.require_int, -1, "n", lo=0)
        self._expect_err("INT_OUT_OF_RANGE", oracle.require_int, 6, "n", hi=5)

        self.assertEqual(oracle.require_str("abc", "s", max_len=3), "abc")
        self._expect_err("INVALID_STR", oracle.require_str, _EvilStr("abc"), "s")
        self._expect_err("STR_TOO_LONG", oracle.require_str, "abcd", "s", max_len=3)
        self._expect_err("INT_OUT_OF_RANGE", oracle.require_str, "a", "s", max_len=oracle.HARD_MAX_BYTES_CAP + 1)
        self._expect_err("INVALID_UTF8_SURROGATE", oracle.require_str, "\ud800", "s")

        self.assertEqual(len(oracle.sha256_hex(b"ok")), 64)
        self._expect_err("INVALID_BYTES", oracle.sha256_hex, "not_bytes")

        h_ok = "0123456789abcdef" * 4
        self.assertEqual(oracle.require_hex64(h_ok, "h"), h_ok)
        self.assertTrue(oracle.constant_time_hex64_equal(h_ok, h_ok, "eq"))
        self.assertFalse(oracle.constant_time_hex64_equal(h_ok, "f" + h_ok[1:], "neq"))
        self._expect_err("INVALID_HEX64", oracle.require_hex64, "a" * 63, "h")
        self._expect_err("STR_TOO_LONG", oracle.require_hex64, "a" * 65, "h")
        self._expect_err("INVALID_HEX64", oracle.require_hex64, "A" * 64, "h")
        self._expect_err("INVALID_HEX64", oracle.require_hex64, "\u00e9" * 64, "h")
        self._expect_err("INVALID_UTF8_SURROGATE", oracle.require_hex64, "\ud800" * 64, "h")

    def test_bounded_int_rational_and_decimal_trunc(self) -> None:
        # parse_bounded_int (default MAX_INT_DIGITS=617 / MAX_INT_BITS=2048 without monkeypatching)
        max_2048 = (1 << oracle.MAX_INT_BITS) - 1
        self.assertEqual(oracle.parse_bounded_int(0), 0)
        self.assertEqual(oracle.parse_bounded_int("0"), 0)
        self.assertEqual(oracle.parse_bounded_int("-42", lo=-50, hi=50), -42)
        self.assertEqual(oracle.parse_bounded_int(str(max_2048)), max_2048)
        self.assertEqual(oracle.parse_bounded_int(str(-max_2048)), -max_2048)
        self.assertEqual(oracle.parse_bounded_int(max_2048), max_2048)
        self._expect_err("INT_TOO_LARGE", oracle.parse_bounded_int, 1 << oracle.MAX_INT_BITS)
        self._expect_err("INT_TOO_LARGE", oracle.parse_bounded_int, "9" * oracle.MAX_INT_DIGITS)
        self._expect_err("INVALID_INT", oracle.parse_bounded_int, True)
        self._expect_err("INVALID_INT", oracle.parse_bounded_int, _RUNTIME_FLOAT)
        self._expect_err("INVALID_INT_STR", oracle.parse_bounded_int, "1" * (oracle.MAX_INT_DIGITS + 2))
        self._expect_err("INVALID_INT_STR", oracle.parse_bounded_int, "")
        self._expect_err("INVALID_INT_STR", oracle.parse_bounded_int, "00")
        self._expect_err("INVALID_INT_STR", oracle.parse_bounded_int, "-0")
        self._expect_err("INVALID_INT_STR", oracle.parse_bounded_int, "\u0661\u0662")
        self._expect_err("INT_OUT_OF_RANGE", oracle.parse_bounded_int, "10", hi=5)

        # parse_exact_rational & format_rational (default MAX_RATIONAL_CHARS = 2*617 + 2 = 1236)
        self.assertEqual(oracle.parse_exact_rational(0), Fraction(0, 1))
        self.assertEqual(oracle.parse_exact_rational(-7), Fraction(-7, 1))
        self.assertEqual(oracle.parse_exact_rational(Fraction(3, 5)), Fraction(3, 5))
        self.assertEqual(oracle.parse_exact_rational("0"), Fraction(0, 1))
        self.assertEqual(oracle.parse_exact_rational("-13/7"), Fraction(-13, 7))
        max_rat_str = f"-{max_2048}/{max_2048 - 1}"
        self.assertEqual(len(max_rat_str), oracle.MAX_RATIONAL_CHARS)
        self.assertEqual(oracle.parse_exact_rational(max_rat_str), Fraction(-max_2048, max_2048 - 1))
        self.assertEqual(oracle.parse_exact_rational(max_2048), Fraction(max_2048, 1))
        self._expect_err("RATIONAL_TOO_LARGE", oracle.parse_exact_rational, 1 << oracle.MAX_INT_BITS)
        self._expect_err("RATIONAL_TOO_LARGE", oracle.parse_exact_rational, "9" * oracle.MAX_INT_DIGITS)
        self._expect_err("RATIONAL_TOO_LARGE", oracle.parse_exact_rational, "1/" + "9" * oracle.MAX_INT_DIGITS)
        self._expect_err("RATIONAL_TOO_LARGE", oracle.parse_exact_rational, Fraction(1 << oracle.MAX_INT_BITS, 1))
        self._expect_err("RATIONAL_TOO_LARGE", oracle.parse_exact_rational, Fraction(1, 1 << oracle.MAX_INT_BITS))
        self._expect_err("INVALID_RATIONAL_TYPE", oracle.parse_exact_rational, True)
        self._expect_err("INVALID_RATIONAL_TYPE", oracle.parse_exact_rational, _RUNTIME_FLOAT)
        self._expect_err("INVALID_RATIONAL_TYPE", oracle.parse_exact_rational, _EvilFrac(1, 2))
        self._expect_err("INVALID_RATIONAL_TYPE", oracle.parse_exact_rational, _EvilStr("1/2"))
        self._expect_err("INVALID_RATIONAL_STR", oracle.parse_exact_rational, "")
        self._expect_err("INVALID_RATIONAL_STR", oracle.parse_exact_rational, "1" * (oracle.MAX_RATIONAL_CHARS + 1))
        self._expect_err("INVALID_RATIONAL_STR", oracle.parse_exact_rational, "1/2/3")
        self._expect_err("INVALID_RATIONAL_STR", oracle.parse_exact_rational, "-")
        self._expect_err("INVALID_RATIONAL_STR", oracle.parse_exact_rational, "\u00b2")
        self._expect_err("INVALID_RATIONAL_STR", oracle.parse_exact_rational, "\u0661\u0662")
        self._expect_err("INVALID_RATIONAL_STR", oracle.parse_exact_rational, "\u2460")
        self._expect_err("INVALID_RATIONAL_STR", oracle.parse_exact_rational, "a")
        self._expect_err("INVALID_RATIONAL_STR", oracle.parse_exact_rational, "007")
        self._expect_err("INVALID_RATIONAL_STR", oracle.parse_exact_rational, "-0")
        self._expect_err("INVALID_RATIONAL_STR", oracle.parse_exact_rational, "1/02")
        self._expect_err("INVALID_RATIONAL_STR", oracle.parse_exact_rational, "1/0")
        self._expect_err("INVALID_RATIONAL_STR", oracle.parse_exact_rational, "3/1")
        self._expect_err("INVALID_RATIONAL_STR", oracle.parse_exact_rational, "1/a")
        self._expect_err("NON_CANONICAL_RATIONAL", oracle.parse_exact_rational, "2/4")

        self.assertEqual(oracle.format_rational(Fraction(5, 1)), "5")
        self.assertEqual(oracle.format_rational(Fraction(-0, 1)), "0")
        self.assertEqual(oracle.format_rational(Fraction(-5, 3)), "-5/3")
        self.assertEqual(oracle.format_rational(Fraction((1 << oracle.MAX_FORMAT_BITS) - 1, 1)), str((1 << oracle.MAX_FORMAT_BITS) - 1))
        self._expect_err("INVALID_RATIONAL_TYPE", oracle.format_rational, 5)
        self._expect_err("RATIONAL_TOO_LARGE", oracle.format_rational, Fraction(1 << oracle.MAX_FORMAT_BITS, 1))
        self._expect_err("RATIONAL_TOO_LARGE", oracle.format_rational, Fraction(1, 1 << oracle.MAX_FORMAT_BITS))

        # format_decimal_trunc including '-0.00' / '-0' normalization
        self.assertEqual(oracle.format_decimal_trunc(Fraction(-1, 1000), places=2), "0.00")
        self.assertEqual(oracle.format_decimal_trunc(Fraction(-1, 1000), places=0), "0")
        self.assertEqual(oracle.format_decimal_trunc(Fraction(-15, 4), places=2), "-3.75")
        self.assertEqual(oracle.format_decimal_trunc(Fraction(15, 4), places=0), "3")
        self.assertEqual(oracle.format_decimal_trunc(Fraction((1 << oracle.MAX_FORMAT_BITS) - 1, 1), places=0), str((1 << oracle.MAX_FORMAT_BITS) - 1))
        self._expect_err("INVALID_RATIONAL_TYPE", oracle.format_decimal_trunc, 1)
        self._expect_err("RATIONAL_TOO_LARGE", oracle.format_decimal_trunc, Fraction(1 << oracle.MAX_FORMAT_BITS, 1))
        self._expect_err("RATIONAL_TOO_LARGE", oracle.format_decimal_trunc, Fraction(1, 1 << oracle.MAX_FORMAT_BITS))
        self._expect_err("INT_OUT_OF_RANGE", oracle.format_decimal_trunc, Fraction(1, 2), places=25)

    def test_iterative_json_and_strict_parser(self) -> None:
        ok_nested: list = []
        cur = ok_nested
        for _ in range(oracle.MAX_JSON_DEPTH):
            nxt: list = []
            cur.append(nxt)
            cur = nxt
        oracle.validate_json_tree_iterative(ok_nested)
        cur.append(0)
        self._expect_err("JSON_DEPTH_EXCEEDED", oracle.validate_json_tree_iterative, ok_nested)

        cyc_d: dict = {}
        cyc_d["self"] = cyc_d
        self._expect_err("JSON_CYCLE", oracle.validate_json_tree_iterative, cyc_d)
        cyc_l: list = []
        cyc_l.append(cyc_l)
        self._expect_err("JSON_CYCLE", oracle.validate_json_tree_iterative, cyc_l)

        shared = {"x": 1}
        oracle.validate_json_tree_iterative({"a": shared, "b": shared})
        max_2048 = (1 << oracle.MAX_INT_BITS) - 1
        self.assertEqual(len(str(max_2048)), oracle.MAX_INT_DIGITS)
        for boundary_int in (10 ** 616, max_2048, -max_2048):
            self.assertEqual(oracle.parse_bounded_int(boundary_int), boundary_int)
            raw_b = oracle.canonical_json_bytes({"ok_int": boundary_int, "none": None, "flag": True})
            self.assertEqual(oracle.parse_strict_json_text(raw_b.decode("ascii"))["ok_int"], boundary_int)
        self._expect_err("INT_TOO_LARGE", oracle.validate_json_tree_iterative, {"huge_bits": 1 << 2048})
        self._expect_err("INT_TOO_LARGE", oracle.validate_json_tree_iterative, {"huge_digits": 10 ** 617})
        self._expect_err("INT_TOO_LARGE", oracle.canonical_json_bytes, {"x": 10 ** 4300})
        self._expect_err("FORBIDDEN_JSON_TYPE", oracle.validate_json_tree_iterative, _EvilDict({"a": 1}))
        self._expect_err("FORBIDDEN_JSON_TYPE", oracle.validate_json_tree_iterative, _EvilList([1]))
        self._expect_err("FORBIDDEN_JSON_TYPE", oracle.validate_json_tree_iterative, {"x": _RUNTIME_FLOAT})
        self._expect_err("INVALID_STR", oracle.validate_json_tree_iterative, {1: "bad_key"})

        self.assertEqual(oracle.parse_strict_json_text("[1,2]", require_object=False), [1, 2])
        mb_txt = '{"a":"' + ("\u00e9" * 6) + '"}'  # 14 chars, 20 UTF-8 bytes
        self.assertEqual(oracle.parse_strict_json_text(mb_txt, max_bytes=20)["a"], "\u00e9" * 6)
        self._expect_err("JSON_TOO_LARGE", oracle.parse_strict_json_text, mb_txt, max_bytes=19)
        self._expect_err("INVALID_BOOL", oracle.parse_strict_json_text, "{}", require_object=1)  # type: ignore[arg-type]
        self._expect_err("INT_OUT_OF_RANGE", oracle.parse_strict_json_text, "{}", max_bytes=oracle.HARD_MAX_BYTES_CAP + 1)
        self._expect_err("JSON_NOT_OBJECT", oracle.parse_strict_json_text, "[1,2]", require_object=True)
        self._expect_err("DUPLICATE_JSON_KEY", oracle.parse_strict_json_text, '{"a":1,"\\u0061":2}')
        self._expect_err("FLOAT_FORBIDDEN", oracle.parse_strict_json_text, '{"x":1.5}')
        self._expect_err("NONFINITE_CONSTANT", oracle.parse_strict_json_text, '{"x":NaN}')
        self._expect_err("INVALID_JSON", oracle.parse_strict_json_text, '{"x":' + ("9" * 5000) + "}")
        self._expect_err("JSON_DEPTH_EXCEEDED", oracle.parse_strict_json_text, ("[" * 1500) + "0" + ("]" * 1500), require_object=False)
        with mock.patch.object(oracle.json, "loads", side_effect=RecursionError("deep")):
            self._expect_err("JSON_DEPTH_EXCEEDED", oracle.parse_strict_json_text, "{}")
        self._expect_err("INVALID_JSON", oracle.parse_strict_json_text, '{"a":')


class Test02PublicMathAndSilqAPIGuards(unittest.TestCase):
    """Exact guards and edge cases across Pillars 1-4 exported APIs."""

    def _expect_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.SilqBoundaryError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_pillar1_cyclotomic_ring_and_matrices(self) -> None:
        z1 = oracle.cyc_make(1, Fraction(1, 2), -1, 0)
        z2 = oracle.cyc_make(0, 1, 1, Fraction(1, 2))
        self.assertEqual(oracle.cyc_sub(oracle.cyc_add(z1, z2), z2), z1)
        self.assertEqual(oracle.cyc_format(oracle.CYC_OMEGA8), ["0", "1/2", "0", "1/2"])
        self.assertTrue(oracle.cyc_is_dyadic(oracle.CYC_OMEGA8))
        self.assertFalse(oracle.cyc_is_dyadic(oracle.cyc_make(Fraction(1, 3))))
        self._expect_err("INVALID_CYCLOTOMIC", oracle.cyc_conj, [1, 0, 0, 0])
        self._expect_err("INVALID_CYCLOTOMIC", oracle.cyc_conj, _EvilTuple((1, 0, 0, 0)))
        self._expect_err("INVALID_CYCLOTOMIC", oracle.cyc_conj, (1, 0, 0))

        # Exact algebraic sign test _qsqrt2_nonneg across all 4 sign quadrants + boundary + type guards
        self._expect_err("INVALID_RATIONAL_TYPE", oracle._qsqrt2_nonneg, _RUNTIME_FLOAT, Fraction(0))
        self._expect_err("INVALID_RATIONAL_TYPE", oracle._qsqrt2_nonneg, Fraction(0), 1)
        self._expect_err("INVALID_RATIONAL_TYPE", oracle._qsqrt2_nonneg, _EvilFrac(1), Fraction(0))
        self.assertTrue(oracle._qsqrt2_nonneg(Fraction(0), Fraction(0)))
        self.assertTrue(oracle._qsqrt2_nonneg(Fraction(1), Fraction(1)))
        self.assertFalse(oracle._qsqrt2_nonneg(Fraction(-1), Fraction(0)))
        self.assertFalse(oracle._qsqrt2_nonneg(Fraction(-1), Fraction(-1)))
        self.assertTrue(oracle._qsqrt2_nonneg(Fraction(2), Fraction(-1)))    # 4 >= 2
        self.assertFalse(oracle._qsqrt2_nonneg(Fraction(1), Fraction(-1)))   # 1 < 2
        self.assertTrue(oracle._qsqrt2_nonneg(Fraction(-1), Fraction(1)))    # 2 >= 1
        self.assertFalse(oracle._qsqrt2_nonneg(Fraction(-2), Fraction(1)))   # 2 < 4

        # Matrix, Kronecker, apply_gate_state, state_born_summary guards
        self._expect_err("INVALID_MATRIX", oracle.is_unitary_cyc, [])
        self._expect_err("INVALID_MATRIX", oracle.is_unitary_cyc, _EvilList([[oracle.CYC_ONE]]))
        self._expect_err("INVALID_MATRIX", oracle.is_unitary_cyc, [[oracle.CYC_ONE], [oracle.CYC_ONE, oracle.CYC_ZERO]])
        self._expect_err("INVALID_MATRIX", oracle.is_unitary_cyc, [_EvilList([oracle.CYC_ONE])])
        self._expect_err("MATRIX_DIM_MISMATCH", oracle.mat_mul_cyc, oracle.mat_identity_cyc(2), oracle.mat_identity_cyc(4))
        self.assertEqual(len(oracle.mat_kron_cyc(oracle.mat_identity_cyc(4), oracle.mat_identity_cyc(4))), 16)
        self._expect_err("MATRIX_TOO_LARGE", oracle.mat_kron_cyc, oracle.mat_identity_cyc(8), oracle.mat_identity_cyc(4))

        g_h = oracle._canonical_gates()["H"]
        self._expect_err("INVALID_STATE", oracle.apply_gate_state, _EvilList([oracle.CYC_ONE, oracle.CYC_ZERO]), 1, g_h, [0])
        self._expect_err("INVALID_STATE", oracle.apply_gate_state, [oracle.CYC_ONE], 1, g_h, [0])
        self._expect_err("INVALID_TARGETS", oracle.apply_gate_state, [oracle.CYC_ONE, oracle.CYC_ZERO], 1, g_h, [])
        self._expect_err("INVALID_TARGETS", oracle.apply_gate_state, [oracle.CYC_ONE, oracle.CYC_ZERO], 1, g_h, _EvilList([0]))
        self._expect_err("DUPLICATE_TARGET_QUBIT", oracle.apply_gate_state, [oracle.CYC_ONE] + [oracle.CYC_ZERO] * 3, 2, oracle._canonical_gates()["CNOT"], [0, 0])
        self._expect_err("GATE_TARGET_MISMATCH", oracle.apply_gate_state, [oracle.CYC_ONE] + [oracle.CYC_ZERO] * 3, 2, g_h, [0, 1])

        self._expect_err("INVALID_STATE", oracle.state_born_summary, [])
        self._expect_err("INVALID_STATE", oracle.state_born_summary, _EvilList([oracle.CYC_ONE]))
        # Born sum with sum_u == 1 but sum_v != 0 -> born_sum_is_one False; sum_u == 0, sum_v == 0 -> False
        z_skew = oracle.cyc_make(Fraction(1, 2), Fraction(1, 2))  # |z|^2 = 3/4 + (1/2)sqrt(2)
        z_pad = oracle.cyc_make(Fraction(1, 2), 0)                 # |z|^2 = 1/4
        s_skew = oracle.state_born_summary([z_skew, z_pad])
        self.assertFalse(s_skew["born_sum_is_one"])
        self.assertFalse(oracle.state_born_summary([oracle.CYC_ZERO, oracle.CYC_ZERO])["born_sum_is_one"])

    def test_pillar2_silq_typechecker_exhaustive_guards(self) -> None:
        # Malformed IR structure -> SilqBoundaryError
        self._expect_err("INVALID_PROGRAM", oracle.typecheck_silq_program, [])
        self._expect_err("INVALID_IDENT", oracle.typecheck_silq_program, {"name": "", "annotation": "mfree", "params": [], "body": [], "returns": []})
        self._expect_err("INVALID_ANNOTATION", oracle.typecheck_silq_program, {"name": "p", "annotation": "bad", "params": [], "body": [], "returns": []})
        self._expect_err("INVALID_PROGRAM_STRUCTURE", oracle.typecheck_silq_program, {"name": "p", "annotation": "mfree", "params": {}, "body": [], "returns": []})
        self._expect_err("INVALID_PROGRAM_STRUCTURE", oracle.typecheck_silq_program, {"name": "p", "annotation": "mfree", "params": [], "body": {}, "returns": []})
        self._expect_err("INVALID_PROGRAM_STRUCTURE", oracle.typecheck_silq_program, {"name": "p", "annotation": "mfree", "params": [], "body": [], "returns": {}})
        self._expect_err("INVALID_PARAM", oracle.typecheck_silq_program, {"name": "p", "annotation": "mfree", "params": ["bad"], "body": [], "returns": []})
        self._expect_err("INVALID_PARAM_TYPE", oracle.typecheck_silq_program, {"name": "p", "annotation": "mfree", "params": [{"name": "x", "type": "int", "const": False}], "body": [], "returns": []})
        self._expect_err("DUPLICATE_PARAM", oracle.typecheck_silq_program, {"name": "p", "annotation": "mfree", "params": [{"name": "x", "type": "B", "const": False}, {"name": "x", "type": "B", "const": False}], "body": [], "returns": []})
        self._expect_err("INVALID_STMT", oracle.typecheck_silq_program, {"name": "p", "annotation": "mfree", "params": [], "body": ["bad"], "returns": []})
        self._expect_err("UNKNOWN_OP", oracle.typecheck_silq_program, {"name": "p", "annotation": "mfree", "params": [], "body": [{"op": "bogus"}], "returns": []})

        def _tc(ann: str, params: list, body: list, returns: list) -> dict:
            return oracle.typecheck_silq_program({"name": "t", "annotation": ann, "params": params, "body": body, "returns": returns})

        # Duplicate variable bindings across alloc_q, lifted_and, dup, measure
        self._expect_err("DUPLICATE_VAR", _tc, "mfree", [{"name": "a", "type": "B", "const": False}], [{"op": "alloc_q", "dst": "a"}], ["a"])
        self._expect_err("DUPLICATE_VAR", _tc, "mfree", [{"name": "a", "type": "B", "const": True}, {"name": "b", "type": "B", "const": True}], [{"op": "lifted_and", "dst": "a", "ctrl1": "a", "ctrl2": "b"}], [])
        self._expect_err("DUPLICATE_VAR", _tc, "mfree", [{"name": "c", "type": "!B", "const": False}], [{"op": "dup", "src": "c", "dst": "c"}], [])
        self._expect_err("DUPLICATE_VAR", _tc, "general", [{"name": "q", "type": "B", "const": False}], [{"op": "measure", "src": "q", "dst": "q"}], [])

        # Invalid gates / controls
        self._expect_err("INVALID_GATE", _tc, "qfree", [], [{"op": "qfree_gate", "gate": "H", "controls": [], "target": "a"}], [])
        self._expect_err("INVALID_CONTROLS", _tc, "qfree", [], [{"op": "qfree_gate", "gate": "X", "controls": "a", "target": "a"}], [])
        self._expect_err("INVALID_GATE", _tc, "mfree", [], [{"op": "unitary_gate", "gate": "X", "controls": [], "target": "a"}], [])
        self._expect_err("INVALID_CONTROLS", _tc, "mfree", [], [{"op": "unitary_gate", "gate": "H", "controls": "a", "target": "a"}], [])

        # Semantic rejections (every error branch!)
        p_b = [{"name": "a", "type": "B", "const": False}, {"name": "b", "type": "B", "const": True}]
        p_cb = [{"name": "c", "type": "!B", "const": False}, {"name": "q", "type": "B", "const": True}]
        # lifted_and unbound / aliased
        self.assertEqual(_tc("mfree", p_b, [{"op": "lifted_and", "dst": "t", "ctrl1": "missing", "ctrl2": "b"}], ["a"])["type_error_code"], "UNBOUND_OR_DEAD_VAR")
        self.assertEqual(_tc("mfree", p_b, [{"op": "lifted_and", "dst": "t", "ctrl1": "a", "ctrl2": "a"}], ["a"])["type_error_code"], "QUANTUM_CLONING_FORBIDDEN")
        # qfree_gate aliased / unbound / type mismatch / non-const tainting unrelated vs related
        self.assertEqual(_tc("qfree", p_b, [{"op": "qfree_gate", "gate": "CNOT", "controls": ["a"], "target": "a"}], ["a"])["type_error_code"], "QUANTUM_CLONING_FORBIDDEN")
        self.assertEqual(_tc("qfree", p_b, [{"op": "qfree_gate", "gate": "X", "controls": [], "target": "missing"}], ["a"])["type_error_code"], "UNBOUND_OR_DEAD_VAR")
        self.assertEqual(_tc("qfree", p_cb, [{"op": "qfree_gate", "gate": "X", "controls": [], "target": "c"}], [])["type_error_code"], "TYPE_MISMATCH")
        # unitary_gate aliased / unbound / type mismatch / const non-diag / non-diag taints lifted_and
        self.assertEqual(_tc("mfree", p_b, [{"op": "unitary_gate", "gate": "CZ", "controls": ["a"], "target": "a"}], ["a"])["type_error_code"], "QUANTUM_CLONING_FORBIDDEN")
        self.assertEqual(_tc("mfree", p_b, [{"op": "unitary_gate", "gate": "H", "controls": [], "target": "missing"}], ["a"])["type_error_code"], "UNBOUND_OR_DEAD_VAR")
        self.assertEqual(_tc("mfree", p_cb, [{"op": "unitary_gate", "gate": "H", "controls": [], "target": "c"}], [])["type_error_code"], "TYPE_MISMATCH")
        self.assertEqual(_tc("mfree", p_cb, [{"op": "unitary_gate", "gate": "H", "controls": [], "target": "q"}], [])["type_error_code"], "CONST_MODIFICATION_FORBIDDEN")
        # dup unbound
        self.assertEqual(_tc("mfree", p_cb, [{"op": "dup", "src": "missing", "dst": "c2"}], [])["type_error_code"], "UNBOUND_OR_DEAD_VAR")
        # measure unbound / dead / type mismatch / const / consuming dep breaks forget
        self.assertEqual(_tc("general", p_cb, [{"op": "measure", "src": "missing", "dst": "m"}], [])["type_error_code"], "UNBOUND_OR_DEAD_VAR")
        self.assertEqual(_tc("general", p_cb, [{"op": "measure", "src": "c", "dst": "m"}], [])["type_error_code"], "TYPE_MISMATCH")
        self.assertEqual(_tc("general", p_cb, [{"op": "measure", "src": "q", "dst": "m"}], [])["type_error_code"], "CONST_CONSUMPTION_FORBIDDEN")
        # Use-after-measure rejects dead variable
        self.assertEqual(
            _tc("general", p_b, [{"op": "measure", "src": "a", "dst": "m"}, {"op": "qfree_gate", "gate": "X", "controls": [], "target": "a"}], ["m"])["type_error_code"],
            "UNBOUND_OR_DEAD_VAR",
        )
        # forget unbound / non-lifted / valid explicit forget
        self.assertEqual(_tc("mfree", p_b, [{"op": "forget", "var": "missing"}], ["a"])["type_error_code"], "UNBOUND_OR_DEAD_VAR")
        self.assertEqual(_tc("mfree", p_b, [{"op": "forget", "var": "a"}], [])["type_error_code"], "UNCOMPUTATION_FAILED")
        ok_forget = _tc(
            "mfree",
            [{"name": "a", "type": "B", "const": True}, {"name": "b", "type": "B", "const": True}, {"name": "z", "type": "B", "const": False}],
            [
                {"op": "lifted_and", "dst": "tmp", "ctrl1": "a", "ctrl2": "b"},
                {"op": "qfree_gate", "gate": "X", "controls": [], "target": "z"},  # mutates unrelated wire -> tmp stays untainted!
                {"op": "forget", "var": "tmp"},
            ],
            ["z"],
        )
        self.assertTrue(ok_forget["well_typed"])
        self.assertEqual(ok_forget["synthesized_uncomputations"], ["CCX(a,b,tmp)"])
        # Duplicate return / dead return / const B return (S38-VER-01) vs const !B return
        self.assertEqual(_tc("mfree", p_b, [], ["a", "a"])["type_error_code"], "QUANTUM_CLONING_FORBIDDEN")
        self.assertEqual(_tc("general", p_b, [{"op": "measure", "src": "a", "dst": "m"}], ["a"])["type_error_code"], "UNBOUND_OR_DEAD_VAR")
        self.assertEqual(_tc("mfree", [{"name": "a", "type": "B", "const": True}], [], ["a"])["type_error_code"], "CONST_CONSUMPTION_FORBIDDEN")
        self.assertTrue(_tc("mfree", [{"name": "c", "type": "!B", "const": True}], [], ["c"])["well_typed"])

        # S38-VER-01: Self-mutation of lifted_and temporary blocks BOTH explicit forget and LIFO auto-uncompute
        p_ab = [{"name": "a", "type": "B", "const": True}, {"name": "b", "type": "B", "const": True}]
        for bad_mut in (
            {"op": "unitary_gate", "gate": "H", "controls": [], "target": "tmp"},
            {"op": "unitary_gate", "gate": "Y", "controls": [], "target": "tmp"},
            {"op": "qfree_gate", "gate": "X", "controls": [], "target": "tmp"},
        ):
            self.assertEqual(
                _tc("mfree", p_ab, [{"op": "lifted_and", "dst": "tmp", "ctrl1": "a", "ctrl2": "b"}, bad_mut, {"op": "forget", "var": "tmp"}], [])["type_error_code"],
                "UNCOMPUTATION_FAILED",
            )
            self.assertEqual(
                _tc("mfree", p_ab, [{"op": "lifted_and", "dst": "tmp", "ctrl1": "a", "ctrl2": "b"}, bad_mut], [])["type_error_code"],
                "UNCONSUMED_QUANTUM_DROP",
            )

        # S38-VER-01: Exact control arity enforcement across qfree_gate & unitary_gate
        p_3b = [
            {"name": "a", "type": "B", "const": False},
            {"name": "b", "type": "B", "const": False},
            {"name": "d", "type": "B", "const": False},
        ]
        for bad_arity_stmt in (
            {"op": "qfree_gate", "gate": "X", "controls": ["a"], "target": "b"},
            {"op": "qfree_gate", "gate": "CNOT", "controls": [], "target": "a"},
            {"op": "qfree_gate", "gate": "CNOT", "controls": ["a", "b"], "target": "d"},
            {"op": "qfree_gate", "gate": "CCX", "controls": [], "target": "a"},
            {"op": "qfree_gate", "gate": "CCX", "controls": ["a"], "target": "b"},
            {"op": "unitary_gate", "gate": "H", "controls": ["a"], "target": "b"},
            {"op": "unitary_gate", "gate": "Z", "controls": ["a"], "target": "b"},
            {"op": "unitary_gate", "gate": "phase", "controls": ["a"], "target": "b"},
            {"op": "unitary_gate", "gate": "CZ", "controls": [], "target": "a"},
            {"op": "unitary_gate", "gate": "CZ", "controls": ["a", "b"], "target": "d"},
        ):
            self.assertEqual(_tc("mfree", p_3b, [bad_arity_stmt], ["a", "b", "d"])["type_error_code"], "GATE_ARITY_MISMATCH")

        # Strict !B/B operand separation (no !tau <: tau subtyping in this toy IR),
        # consistent const-control handling for CNOT & CZ, and const-target rejection across unitary gates
        p_mix = [
            {"name": "c", "type": "!B", "const": False},
            {"name": "a", "type": "B", "const": False},
            {"name": "q", "type": "B", "const": True},
        ]
        self.assertEqual(_tc("mfree", p_mix, [{"op": "lifted_and", "dst": "t", "ctrl1": "c", "ctrl2": "a"}], ["a"])["type_error_code"], "TYPE_MISMATCH")
        self.assertEqual(_tc("mfree", p_mix, [{"op": "lifted_and", "dst": "t", "ctrl1": "a", "ctrl2": "c"}], ["a"])["type_error_code"], "TYPE_MISMATCH")
        self.assertEqual(_tc("qfree", p_mix, [{"op": "qfree_gate", "gate": "CNOT", "controls": ["c"], "target": "a"}], ["a"])["type_error_code"], "TYPE_MISMATCH")
        self.assertEqual(_tc("mfree", p_mix, [{"op": "unitary_gate", "gate": "CZ", "controls": ["c"], "target": "a"}], ["a"])["type_error_code"], "TYPE_MISMATCH")
        # Both CNOT and CZ consistently accept a const control with a non-const target
        self.assertTrue(_tc("mfree", p_mix, [{"op": "qfree_gate", "gate": "CNOT", "controls": ["q"], "target": "a"}], ["a"])["well_typed"])
        self.assertTrue(_tc("mfree", p_mix, [{"op": "unitary_gate", "gate": "CZ", "controls": ["q"], "target": "a"}], ["a"])["well_typed"])
        for const_u in (
            {"op": "unitary_gate", "gate": "phase", "controls": [], "target": "q"},
            {"op": "unitary_gate", "gate": "Z", "controls": [], "target": "q"},
            {"op": "unitary_gate", "gate": "S", "controls": [], "target": "q"},
            {"op": "unitary_gate", "gate": "T", "controls": [], "target": "q"},
            {"op": "unitary_gate", "gate": "CZ", "controls": ["a"], "target": "q"},
        ):
            self.assertEqual(_tc("mfree", p_mix, [const_u], ["a"])["type_error_code"], "CONST_MODIFICATION_FORBIDDEN")

        # Documented toy-IR scope boundary: DJ CNOT-allocated ancilla is outside lifted_and-only forget(),
        # whereas Toffoli lifted_and + diagonal Z + explicit forget() type-checks and synthesizes CCX
        dj_forget_attempt = _tc(
            "mfree",
            [{"name": "O", "type": "B", "const": False}],
            [
                {"op": "alloc_q", "dst": "H"},
                {"op": "unitary_gate", "gate": "H", "controls": [], "target": "O"},
                {"op": "qfree_gate", "gate": "CNOT", "controls": ["O"], "target": "H"},
                {"op": "unitary_gate", "gate": "Z", "controls": [], "target": "H"},
                {"op": "forget", "var": "H"},
                {"op": "unitary_gate", "gate": "H", "controls": [], "target": "O"},
            ],
            ["O"],
        )
        self.assertFalse(dj_forget_attempt["well_typed"])
        self.assertEqual(dj_forget_attempt["type_error_code"], "UNCOMPUTATION_FAILED")

        toff_forget_ok = _tc(
            "mfree",
            [{"name": "a", "type": "B", "const": True}, {"name": "b", "type": "B", "const": True}],
            [
                {"op": "lifted_and", "dst": "tmp", "ctrl1": "a", "ctrl2": "b"},
                {"op": "unitary_gate", "gate": "Z", "controls": [], "target": "tmp"},
                {"op": "forget", "var": "tmp"},
            ],
            [],
        )
        self.assertTrue(toff_forget_ok["well_typed"])
        self.assertEqual(toff_forget_ok["synthesized_uncomputations"], ["CCX(a,b,tmp)"])

    def test_pillar3_and_pillar4_public_api_guards(self) -> None:
        st2 = [oracle.CYC_ONE, oracle.CYC_ZERO, oracle.CYC_ZERO, oracle.CYC_ZERO]
        st3 = [oracle.CYC_ONE] + [oracle.CYC_ZERO] * 7
        self._expect_err("INVALID_STATE", oracle.partial_trace_state, _EvilList(st2), 2, [0])
        self._expect_err("INVALID_STATE", oracle.partial_trace_state, [oracle.CYC_ONE], 2, [0])
        self._expect_err("INVALID_KEEP_QUBITS", oracle.partial_trace_state, st2, 2, [])
        self._expect_err("INVALID_KEEP_QUBITS", oracle.partial_trace_state, st2, 2, _EvilList([0]))
        self._expect_err("INVALID_KEEP_QUBITS", oracle.partial_trace_state, st3, 3, [0, 0])
        self._expect_err("INVALID_KEEP_QUBITS", oracle.partial_trace_state, st2, 2, [0, 1])

        # Pillar 4 analyze_classical_gate_erasure edge cases for bijection and involution checks
        self._expect_err("INVALID_TRUTH_TABLE", oracle.analyze_classical_gate_erasure, 1, 1, [0])
        self._expect_err("INVALID_TRUTH_TABLE", oracle.analyze_classical_gate_erasure, 1, 1, _EvilList([0, 1]))
        # Non-bijection because ni != no (1 -> 2, injective [0, 1] has outputs[outputs[x]] == x!)
        inj_1_to_2 = oracle.analyze_classical_gate_erasure(1, 2, [0, 1])
        self.assertFalse(inj_1_to_2["is_bijection"])
        self.assertFalse(inj_1_to_2["involution_verified"])
        # Bijection that is NOT an involution (3-cycle on 2 bits: 0->1->2->0, 3->3)
        cyc3 = oracle.analyze_classical_gate_erasure(2, 2, [1, 2, 0, 3])
        self.assertTrue(cyc3["is_bijection"])
        self.assertFalse(cyc3["involution_verified"])
        # Table boundary check (max_qubits=24 ok, 25 rejected)
        self.assertEqual(len(oracle.build_dense_statevector_size_table(24)), 24)
        self._expect_err("INT_OUT_OF_RANGE", oracle.build_dense_statevector_size_table, 25)


class Test03ZoneBFileIOConcurrencyRacesAndCLI(unittest.TestCase):
    """Hardened Zone-B file I/O: 0o600, 16T+80T concurrency, renameat2, hardlink race, CWD, CLI."""

    def _expect_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.SilqBoundaryError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_safe_path_io_and_pwd_guards(self) -> None:
        self._expect_err("INVALID_PATH_TYPE", audit.require_safe_path, "not_a_path")
        self._expect_err("INVALID_PATH_TYPE", audit.require_safe_path, _EvilPath("ok.json"))
        self._expect_err("INVALID_PATH", audit.require_safe_path, Path("bad\x00name"))
        self._expect_err("INVALID_UTF8_SURROGATE", audit.require_safe_path, Path("\ud800"))
        self._expect_err("NON_REGULAR_FILE", audit.require_safe_path, Path("/"))
        self._expect_err("NON_REGULAR_FILE", audit.require_safe_path, Path("."))
        self._expect_err("NON_REGULAR_FILE", audit.require_safe_path, Path("a/.."))
        self._expect_err("INVALID_WRITE_DATA", audit.write_regular_file_bytes, Path("/tmp/unused_s38"), "str")  # type: ignore[arg-type]
        self._expect_err("INT_OUT_OF_RANGE", audit.read_regular_bytes_capped, Path("/tmp/unused_s38"), max_bytes=oracle.HARD_MAX_BYTES_CAP + 1)
        self._expect_err("INT_OUT_OF_RANGE", audit.read_regular_bytes_capped, Path("/tmp/unused_s38"), max_bytes=1 << 100)

        _require_real_tmpdir_or_skip(self)
        with tempfile.TemporaryDirectory(prefix="s38_io_") as tmp:
            td = Path(tmp)
            real_dir = td / "real"
            real_dir.mkdir(mode=0o700)
            ok_file = real_dir / "ok.json"
            ok_file.write_bytes(b"{}\n")

            sym_file = td / "sym.json"
            sym_file.symlink_to(ok_file)
            sym_dir = td / "sym_dir"
            sym_dir.symlink_to(real_dir)
            self._expect_err("SYMLINK_FORBIDDEN", audit.require_safe_path, sym_file)
            self._expect_err("SYMLINK_FORBIDDEN", audit.require_safe_path, sym_dir / "ok.json")
            self._expect_err("SYMLINK_FORBIDDEN", audit.read_regular_bytes_capped, sym_file)
            self._expect_err("SYMLINK_FORBIDDEN", audit.write_regular_file_bytes, sym_file, b"x")
            self._expect_err("FILE_IO_ERROR", audit.require_safe_path, td / "missing_dir" / "ok.json")
            self._expect_err("PATH_STAT_ERROR", audit.require_safe_path, ok_file / "child")
            self.assertEqual(audit.require_safe_path(real_dir / "brand_new.json"), real_dir / "brand_new.json")
            self.assertEqual(audit.require_safe_path(ok_file), ok_file)

            old_cwd = os.getcwd()
            old_pwd = os.environ.get("PWD")
            try:
                os.chdir(real_dir)
                os.environ["PWD"] = str(sym_dir)
                self._expect_err("SYMLINK_FORBIDDEN", audit.require_safe_path, Path("ok.json"))
                os.environ["PWD"] = str(real_dir)
                self.assertEqual(audit.read_regular_bytes_capped(Path("./ok.json")), b"{}\n")
                os.environ.pop("PWD", None)
                self.assertEqual(audit.read_regular_bytes_capped(Path("ok.json")), b"{}\n")
                os.environ["PWD"] = "relative/pwd"
                self.assertEqual(audit.read_regular_bytes_capped(Path("ok.json")), b"{}\n")
            finally:
                os.chdir(old_cwd)
                if old_pwd is None:
                    os.environ.pop("PWD", None)
                else:
                    os.environ["PWD"] = old_pwd

            self._expect_err("FILE_READ_ERROR", audit.read_regular_bytes_capped, real_dir / "missing.json")
            self._expect_err("NON_REGULAR_FILE", audit.read_regular_bytes_capped, real_dir)
            fifo_path = real_dir / "pipe.fifo"
            os.mkfifo(fifo_path)
            self._expect_err("NON_REGULAR_FILE", audit.read_regular_bytes_capped, fifo_path)
            self._expect_err("NON_REGULAR_FILE", audit.write_regular_file_bytes, fifo_path, b"x")

            exact_f = real_dir / "exact.bin"
            audit.write_regular_file_bytes(exact_f, b"12345")
            self.assertEqual(stat.S_IMODE(os.lstat(exact_f).st_mode), 0o600)
            self.assertEqual(audit.read_regular_bytes_capped(exact_f, max_bytes=5), b"12345")
            self._expect_err("FILE_TOO_LARGE", audit.read_regular_bytes_capped, exact_f, max_bytes=4)

            hl_a = real_dir / "hl_a.json"
            hl_b = real_dir / "hl_b.json"
            hl_a.write_bytes(b"ORIGINAL\n")
            os.link(hl_a, hl_b)
            self._expect_err("HARDLINK_FORBIDDEN", audit.write_regular_file_bytes, hl_a, b"CLOBBER\n")
            self.assertEqual(hl_b.read_bytes(), b"ORIGINAL\n")

            # Direct OSError fail-closed handler coverage across _check_pwd_no_symlinks,
            # _open_parent_dir_fd, require_safe_path, read_regular_bytes_capped, write_regular_file_bytes
            with mock.patch.dict(os.environ, {"PWD": str(real_dir)}):
                with mock.patch.object(audit.os, "open", side_effect=PermissionError("root denied")):
                    self._expect_err("CWD_UNAVAILABLE", audit._check_pwd_no_symlinks)
                    self._expect_err("FILE_IO_ERROR", audit.require_safe_path, Path("/tmp/x.json"))
            with mock.patch.object(audit.os, "lstat", side_effect=PermissionError("lstat denied")):
                self._expect_err("PATH_STAT_ERROR", audit.require_safe_path, ok_file)
                self._expect_err("FILE_WRITE_ERROR", audit.write_regular_file_bytes, real_dir / "w_lstat.json", b"x")
            with mock.patch.object(audit.os, "read", side_effect=OSError("read io error")):
                self._expect_err("FILE_READ_ERROR", audit.read_regular_bytes_capped, ok_file)
            with mock.patch.object(audit.os, "fsync", side_effect=OSError("fsync io error")):
                self._expect_err("FILE_WRITE_ERROR", audit.write_regular_file_bytes, real_dir / "w_fsync.json", b"x")
            self.assertEqual([p.name for p in real_dir.glob(".s38_silq_tmp_*")], [])

    def test_cli_argv_guards(self) -> None:
        bad_argvs: list[tuple[Any, str]] = [
            ("not_a_list", "INVALID_ARGV"),
            ([123], "INVALID_ARGV"),
            ([_EvilStr("--standalone")], "INVALID_ARGV"),
            (["\ud800"], "INVALID_UTF8_SURROGATE"),
            (["--check", "\ud800"], "INVALID_UTF8_SURROGATE"),
            (["--write=\ud800"], "INVALID_UTF8_SURROGATE"),
            (["--json", "--json"], "DUPLICATE_FLAG"),
            (["--standalone", "--standalone"], "CONFLICTING_MODE"),
            (["--standalone", "--check", "a.json"], "CONFLICTING_MODE"),
            (["--standalone", "--check=a.json"], "CONFLICTING_MODE"),
            (["--check", "a.json", "--write", "b.json"], "CONFLICTING_MODE"),
            (["--check"], "MISSING_PATH_ARG"),
            (["--write"], "MISSING_PATH_ARG"),
            (["--check", ""], "INVALID_PATH_ARG"),
            (["--write", ""], "INVALID_PATH_ARG"),
            (["--check", "--json"], "INVALID_PATH_ARG"),
            (["--write", "--json"], "INVALID_PATH_ARG"),
            (["--check=--json"], "INVALID_PATH_ARG"),
            (["--write=--json"], "INVALID_PATH_ARG"),
            (["--check="], "INVALID_PATH_ARG"),
            (["--write="], "INVALID_PATH_ARG"),
            (["--write", "-foo"], "INVALID_PATH_ARG"),
            (["--wr=--json"], "UNKNOWN_FLAG"),
            (["--unknown"], "UNKNOWN_FLAG"),
        ]
        _require_real_tmpdir_or_skip(self)
        with tempfile.TemporaryDirectory(prefix="s38_cli_bad_") as tmp:
            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                for argv, exp_code in bad_argvs:
                    buf_err = io.StringIO()
                    old_err = sys.stderr
                    try:
                        sys.stderr = buf_err
                        rc = audit.main(argv)
                    finally:
                        sys.stderr = old_err
                    self.assertEqual(rc, 2)
                    err_obj = json.loads(buf_err.getvalue())
                    self.assertFalse(err_obj["valid"])
                    self.assertEqual(err_obj["error_code"], exp_code)
                self.assertEqual(list(Path(tmp).iterdir()), [])
            finally:
                os.chdir(old_cwd)


class Test04PayloadAndSecondaryAuditTamperMatrix(unittest.TestCase):
    """Exhaustive tamper matrix killing every guard in validate_certificate_payload & secondary_audit_payload."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.valid_cert = oracle.build_standalone_certificate()

    def _expect_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.SilqBoundaryError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def _resign(self, cert: dict) -> dict:
        c = copy.deepcopy(cert)
        p_sha = oracle.sha256_hex(oracle.canonical_json_bytes(c["payload"]))
        c["payload_sha256"] = p_sha
        body = {
            "schema": c["schema"],
            "track_id": c["track_id"],
            "payload_sha256": p_sha,
            "payload": c["payload"],
        }
        c["certificate_sha256"] = oracle.sha256_hex(oracle.canonical_json_bytes(body))
        return c

    def test_validate_certificate_payload_tampers(self) -> None:
        res_ok = oracle.validate_certificate_payload(self.valid_cert, full_replay=False)
        self.assertTrue(res_ok["valid"])
        self.assertFalse(res_ok["full_replay"])

        self._expect_err("CERT_NOT_DICT", oracle.validate_certificate_payload, [], full_replay=False)

        missing_k = copy.deepcopy(self.valid_cert)
        del missing_k["track_id"]
        self._expect_err("INVALID_CERT_KEYS", oracle.validate_certificate_payload, missing_k, full_replay=False)

        for key, bad_v, code in [
            ("schema", "wrong", "INVALID_SCHEMA"),
            ("track_id", "wrong", "INVALID_TRACK_ID"),
            ("payload", [], "PAYLOAD_NOT_DICT"),
        ]:
            t_c = copy.deepcopy(self.valid_cert)
            t_c[key] = bad_v
            self._expect_err(code, oracle.validate_certificate_payload, t_c, full_replay=False)

        bad_psha = copy.deepcopy(self.valid_cert)
        bad_psha["payload_sha256"] = ("0" if bad_psha["payload_sha256"][0] != "0" else "1") + bad_psha["payload_sha256"][1:]
        self._expect_err("PAYLOAD_SHA_MISMATCH", oracle.validate_certificate_payload, bad_psha, full_replay=False)

        bad_csha = copy.deepcopy(self.valid_cert)
        bad_csha["certificate_sha256"] = ("0" if bad_csha["certificate_sha256"][0] != "0" else "1") + bad_csha["certificate_sha256"][1:]
        self._expect_err("CERT_SHA_MISMATCH", oracle.validate_certificate_payload, bad_csha, full_replay=False)

        hollow = copy.deepcopy(self.valid_cert)
        hollow["payload"] = {}
        self._expect_err("INVALID_PAYLOAD_KEYS", oracle.validate_certificate_payload, self._resign(hollow), full_replay=False)

        # Validator accepts any valid Aletheia novelty tier (N0/N1/N2) without hard-coding a self-assigned tier
        for valid_tier in ("N0", "N1", "N2"):
            t_ok = copy.deepcopy(self.valid_cert)
            t_ok["payload"]["novelty_classification"] = valid_tier
            self.assertTrue(oracle.validate_certificate_payload(self._resign(t_ok), full_replay=False)["valid"])

        for field, bad_v, code in [
            ("oracle_class", "approx", "INVALID_PAYLOAD_META"),
            ("novelty_classification", "N9", "INVALID_PAYLOAD_META"),
            ("novelty_classification", [], "INVALID_PAYLOAD_META"),
            ("zero_floats_exact_arithmetic", False, "INVALID_PAYLOAD_META"),
            ("all_verified", False, "INVALID_PAYLOAD_META"),
            ("literature_anchors_n0", "ab", "INVALID_PAYLOAD_META"),
            ("literature_anchors_n0", ["only_one"], "INVALID_PAYLOAD_META"),
            ("pillar1_cyclotomic_clifford_t", [], "INVALID_PILLAR_TYPE"),
        ]:
            t_m = copy.deepcopy(self.valid_cert)
            t_m["payload"][field] = bad_v
            self._expect_err(code, oracle.validate_certificate_payload, self._resign(t_m), full_replay=False)

        unver = copy.deepcopy(self.valid_cert)
        unver["payload"]["pillar1_cyclotomic_clifford_t"]["pillar_verified"] = False
        self._expect_err("PILLAR_NOT_VERIFIED", oracle.validate_certificate_payload, self._resign(unver), full_replay=False)

        extra_pk = copy.deepcopy(self.valid_cert)
        extra_pk["payload"]["pillar1_cyclotomic_clifford_t"]["rogue_extra"] = 1
        self._expect_err("INVALID_PILLAR_KEYS", oracle.validate_certificate_payload, self._resign(extra_pk), full_replay=False)

        bool_int = copy.deepcopy(self.valid_cert)
        bool_int["payload"]["pillar2_toy_silq_ir_checker"]["valid_program_count"] = True
        self._expect_err("BOOL_IN_NON_BOOL_FIELD", oracle.validate_certificate_payload, self._resign(bool_int), full_replay=False)

        bool_list = copy.deepcopy(self.valid_cert)
        bool_list["payload"]["literature_anchors_n0"][0] = True
        self._expect_err("BOOL_IN_LIST", oracle.validate_certificate_payload, self._resign(bool_list), full_replay=False)

        bool_nested = copy.deepcopy(self.valid_cert)
        bool_nested["payload"]["pillar4_landauer_and_dense_sizes"]["dense_statevector_size_table_n1_to_n20"][0]["n_qubits"] = True
        self._expect_err("BOOL_IN_NON_BOOL_FIELD", oracle.validate_certificate_payload, self._resign(bool_nested), full_replay=False)

        int_in_bool = copy.deepcopy(self.valid_cert)
        int_in_bool["payload"]["pillar1_cyclotomic_clifford_t"]["gate_certifications"][0]["is_unitary"] = 1
        self._expect_err("NON_BOOL_IN_BOOL_FIELD", oracle.validate_certificate_payload, self._resign(int_in_bool), full_replay=False)

        altered = copy.deepcopy(self.valid_cert)
        altered["payload"]["pillar3_uncomputation_partial_trace"]["deutsch_jozsa_uncomputed_clean"]["purity_Tr_rho_sq"] = "1/2"
        altered_r = self._resign(altered)
        self.assertTrue(oracle.validate_certificate_payload(altered_r, full_replay=False)["valid"])
        self._expect_err("RECOMPUTATION_MISMATCH", oracle.validate_certificate_payload, altered_r, full_replay=True)

    def test_secondary_audit_payload_tamper_matrix(self) -> None:
        base_p = self.valid_cert["payload"]
        sec = audit.secondary_audit_payload(base_p)
        self.assertTrue(sec["secondary_audit_passed"])
        self.assertEqual(sec["pillars_checked"], 4)

        self._expect_err("AUDIT_PAYLOAD_TYPE", audit.secondary_audit_payload, [])
        self._expect_err("AUDIT_SCHEMA_ERROR", audit.secondary_audit_payload, {"all_verified": True})
        self._expect_err("AUDIT_SCHEMA_TYPE", audit.secondary_audit_payload, {"all_verified": True, "literature_anchors_n0": base_p["literature_anchors_n0"], "pillar1_cyclotomic_clifford_t": None})

        def _tamper(code: str, mutator) -> None:
            p = copy.deepcopy(base_p)
            mutator(p)
            self._expect_err(code, audit.secondary_audit_payload, p)

        _tamper("AUDIT_ALL_VERIFIED_FALSE", lambda p: p.__setitem__("all_verified", False))
        _tamper("INVALID_BOOL", lambda p: p.__setitem__("all_verified", 1))
        _tamper("AUDIT_META_ANCHORS", lambda p: p.__setitem__("literature_anchors_n0", ["forged", "forged"]))

        # Pillar 1 tampers (incl. strict keysets, ring_representation, dyadic denominator, & exact Born vectors)
        _tamper("AUDIT_SCHEMA_ERROR", lambda p: p["pillar1_cyclotomic_clifford_t"].__setitem__("extra_p1", 1))
        _tamper("AUDIT_P1_RING", lambda p: p["pillar1_cyclotomic_clifford_t"].__setitem__("ring_representation", "fake"))
        _tamper("AUDIT_P1_UNITARY", lambda p: p["pillar1_cyclotomic_clifford_t"]["gate_certifications"][0].__setitem__("extra_g", 1))
        _tamper("AUDIT_P1_BORN", lambda p: p["pillar1_cyclotomic_clifford_t"]["born_witnesses"]["bell_pair"].__setitem__("extra_w", 1))
        _tamper("AUDIT_SCHEMA_TYPE", lambda p: p["pillar1_cyclotomic_clifford_t"]["born_witnesses"].__setitem__("bell_pair", []))
        _tamper("AUDIT_P1_NON_DYADIC", lambda p: p["pillar1_cyclotomic_clifford_t"]["born_witnesses"]["bell_pair"].__setitem__("born_probs_qsqrt2", [["1/3", "0"], ["2/3", "0"], ["0", "0"], ["0", "0"]]))
        _tamper("AUDIT_P1_NON_DYADIC", lambda p: p["pillar1_cyclotomic_clifford_t"]["born_witnesses"]["magic_HTH_ket0"].__setitem__("born_probs_qsqrt2", [["1/2", "1/3"], ["1/2", "-1/3"]]))
        _tamper("AUDIT_P1_BORN", lambda p: p["pillar1_cyclotomic_clifford_t"]["born_witnesses"]["bell_pair"].__setitem__("born_probs_qsqrt2", [["1/4", "0"], ["1/4", "0"], ["1/4", "0"], ["1/4", "0"]]))
        _tamper("AUDIT_P1_BORN", lambda p: p["pillar1_cyclotomic_clifford_t"]["born_witnesses"]["ghz_3q"].__setitem__("born_probs_qsqrt2", [["1", "0"]] + [["0", "0"]] * 7))
        _tamper("AUDIT_P1_BORN", lambda p: p["pillar1_cyclotomic_clifford_t"]["born_witnesses"]["toffoli_superposed"].__setitem__("born_probs_qsqrt2", [["1", "0"]] + [["0", "0"]] * 7))
        _tamper("AUDIT_P1_GATES", lambda p: p["pillar1_cyclotomic_clifford_t"]["gate_certifications"].pop())
        _tamper("AUDIT_P1_GATE_DIMS", lambda p: p["pillar1_cyclotomic_clifford_t"]["gate_certifications"][0].__setitem__("dim", 4))
        _tamper("INVALID_INT", lambda p: p["pillar1_cyclotomic_clifford_t"]["gate_certifications"][0].__setitem__("dim", True))
        _tamper("AUDIT_P1_UNITARY", lambda p: p["pillar1_cyclotomic_clifford_t"]["gate_certifications"][0].__setitem__("is_unitary", False))
        _tamper("INVALID_BOOL", lambda p: p["pillar1_cyclotomic_clifford_t"]["gate_certifications"][0].__setitem__("is_unitary", 1))
        _tamper("AUDIT_P1_UNITARY", lambda p: p["pillar1_cyclotomic_clifford_t"].__setitem__("all_gates_unitary_and_dyadic", False))
        _tamper("AUDIT_P1_RELATIONS", lambda p: p["pillar1_cyclotomic_clifford_t"].__setitem__("group_relations_verified", []))
        _tamper("AUDIT_P1_RELATIONS", lambda p: p["pillar1_cyclotomic_clifford_t"]["group_relations_verified"].pop("H2_eq_I"))
        def _swap_rel_key(p: dict) -> None:
            r = p["pillar1_cyclotomic_clifford_t"]["group_relations_verified"]
            r.pop("H2_eq_I")
            r["well_typed"] = True
        _tamper("AUDIT_P1_RELATIONS", _swap_rel_key)
        _tamper("AUDIT_P1_RELATIONS", lambda p: p["pillar1_cyclotomic_clifford_t"]["group_relations_verified"].__setitem__("H2_eq_I", False))
        _tamper("AUDIT_P1_RELATIONS", lambda p: p["pillar1_cyclotomic_clifford_t"].__setitem__("all_group_relations_verified", False))
        _tamper("AUDIT_P1_BORN", lambda p: p["pillar1_cyclotomic_clifford_t"].__setitem__("born_witnesses", []))
        _tamper("AUDIT_P1_BORN", lambda p: p["pillar1_cyclotomic_clifford_t"]["born_witnesses"].pop("bell_pair"))
        _tamper("AUDIT_P1_BORN", lambda p: p["pillar1_cyclotomic_clifford_t"].__setitem__("all_witnesses_unit_norm", False))
        _tamper("AUDIT_P1_BORN_SHAPE", lambda p: p["pillar1_cyclotomic_clifford_t"]["born_witnesses"]["magic_HTH_ket0"].__setitem__("born_probs_qsqrt2", []))
        _tamper("AUDIT_P1_BORN_SHAPE", lambda p: p["pillar1_cyclotomic_clifford_t"]["born_witnesses"]["bell_pair"].__setitem__("born_probs_qsqrt2", (["1/2", "0"], ["0", "0"], ["0", "0"], ["1/2", "0"])))
        _tamper("AUDIT_P1_BORN_SHAPE", lambda p: p["pillar1_cyclotomic_clifford_t"]["born_witnesses"]["bell_pair"].__setitem__("born_probs_qsqrt2", [["1/2", "0"], ["1/2", "0"]]))
        _tamper("AUDIT_P1_BORN_PAIR", lambda p: p["pillar1_cyclotomic_clifford_t"]["born_witnesses"]["bell_pair"]["born_probs_qsqrt2"].__setitem__(0, ("1/2", "0")))
        _tamper("AUDIT_P1_BORN_PAIR", lambda p: p["pillar1_cyclotomic_clifford_t"]["born_witnesses"]["bell_pair"]["born_probs_qsqrt2"].__setitem__(0, ["1/2"]))
        _tamper("AUDIT_P1_BORN_NEGATIVE", lambda p: p["pillar1_cyclotomic_clifford_t"]["born_witnesses"]["bell_pair"].__setitem__("born_probs_qsqrt2", [["-1/2", "0"], ["3/2", "0"], ["0", "0"], ["0", "0"]]))
        _tamper("AUDIT_P1_BORN", lambda p: p["pillar1_cyclotomic_clifford_t"]["born_witnesses"]["bell_pair"].__setitem__("born_probs_qsqrt2", [["1/4", "0"], ["0", "0"], ["0", "0"], ["1/4", "0"]]))
        _tamper("AUDIT_P1_BORN", lambda p: p["pillar1_cyclotomic_clifford_t"]["born_witnesses"]["magic_HTH_ket0"].__setitem__("born_probs_qsqrt2", [["1/2", "0"], ["1/2", "0"]]))
        _tamper("AUDIT_P1_BORN", lambda p: p["pillar1_cyclotomic_clifford_t"]["born_witnesses"]["bell_pair"].__setitem__("sum_q", "2"))
        _tamper("AUDIT_P1_NONUNITARY", lambda p: p["pillar1_cyclotomic_clifford_t"].__setitem__("must_fail_non_unitary_rejected", False))
        _tamper("AUDIT_P1_NONUNITARY", lambda p: p["pillar1_cyclotomic_clifford_t"].__setitem__("pillar_verified", False))

        # Pillar 2 tampers (incl. strict keysets, annotation, synthesis list, must-fail exact codes/details/names)
        _tamper("AUDIT_SCHEMA_ERROR", lambda p: p["pillar2_toy_silq_ir_checker"].__setitem__("extra_p2", 1))
        _tamper("AUDIT_SCHEMA_TYPE", lambda p: p.__setitem__("pillar2_toy_silq_ir_checker", []))
        _tamper("AUDIT_P2_VALID_COUNT", lambda p: p["pillar2_toy_silq_ir_checker"].__setitem__("valid_program_count", 5))
        _tamper("INVALID_INT", lambda p: p["pillar2_toy_silq_ir_checker"].__setitem__("valid_program_count", True))
        _tamper("AUDIT_P2_VALID_TYPED", lambda p: p["pillar2_toy_silq_ir_checker"]["valid_programs"][0].__setitem__("well_typed", False))
        _tamper("AUDIT_P2_VALID_TYPED", lambda p: p["pillar2_toy_silq_ir_checker"]["valid_programs"][0].__setitem__("extra_vp", 1))
        _tamper("AUDIT_P2_VALID_TYPED", lambda p: p["pillar2_toy_silq_ir_checker"]["valid_programs"][0].__setitem__("annotation", "general"))
        _tamper("AUDIT_P2_VALID_TYPED", lambda p: p["pillar2_toy_silq_ir_checker"]["valid_programs"][0].__setitem__("return_types", ["!B", "!B"]))
        _tamper("AUDIT_P2_VALID_TYPED", lambda p: p["pillar2_toy_silq_ir_checker"]["valid_programs"][1].__setitem__("name", p["pillar2_toy_silq_ir_checker"]["valid_programs"][0]["name"]))
        _tamper("AUDIT_P2_VALID_TYPED", lambda p: p["pillar2_toy_silq_ir_checker"]["valid_programs"][2].__setitem__("synthesized_uncomputations", []))
        _tamper("AUDIT_P2_FAIL_COUNT", lambda p: p["pillar2_toy_silq_ir_checker"].__setitem__("must_fail_program_count", 6))
        _tamper("AUDIT_P2_FAIL_REJECTED", lambda p: p["pillar2_toy_silq_ir_checker"]["must_fail_programs"][0].__setitem__("well_typed", True))
        _tamper("AUDIT_P2_FAIL_REJECTED", lambda p: p["pillar2_toy_silq_ir_checker"]["must_fail_programs"][0].__setitem__("extra_fp", 1))
        _tamper("AUDIT_P2_FAIL_REJECTED", lambda p: p["pillar2_toy_silq_ir_checker"]["must_fail_programs"][0].__setitem__("annotation", "mfree"))
        _tamper("AUDIT_P2_FAIL_REJECTED", lambda p: p["pillar2_toy_silq_ir_checker"]["must_fail_programs"][0].__setitem__("synthesized_uncomputations", ["X"]))
        _tamper("INVALID_BOOL", lambda p: p["pillar2_toy_silq_ir_checker"]["must_fail_programs"][0].__setitem__("well_typed", 0))
        def _rename_err_codes(p: dict) -> None:
            r0 = p["pillar2_toy_silq_ir_checker"]["must_fail_programs"][0]
            r0["type_error_code"] = "FORGED_CODE"
            r0["expected_error_code"] = "FORGED_CODE"
        _tamper("AUDIT_P2_FAIL_REJECTED", _rename_err_codes)
        _tamper("AUDIT_P2_FAIL_REJECTED", lambda p: p["pillar2_toy_silq_ir_checker"]["must_fail_programs"][0].__setitem__("type_error_detail", "forged detail"))
        _tamper("AUDIT_P2_FAIL_REJECTED", lambda p: p["pillar2_toy_silq_ir_checker"]["must_fail_programs"][1].__setitem__("name", "renamed_fail"))

        # Pillar 3 tampers (incl. strict keysets, hermitian, trace_is_one, interference_*, purity_strictly_dropped)
        _tamper("AUDIT_SCHEMA_ERROR", lambda p: p["pillar3_uncomputation_partial_trace"].__setitem__("extra_p3", 1))
        _tamper("AUDIT_SCHEMA_TYPE", lambda p: p.__setitem__("pillar3_uncomputation_partial_trace", []))
        _tamper("AUDIT_P3_DJ_CLEAN", lambda p: p["pillar3_uncomputation_partial_trace"]["deutsch_jozsa_uncomputed_clean"].__setitem__("extra_w3", 1))
        _tamper("AUDIT_P3_DJ_CLEAN", lambda p: p["pillar3_uncomputation_partial_trace"]["deutsch_jozsa_uncomputed_clean"].__setitem__("purity_Tr_rho_sq", "1/2"))
        _tamper("AUDIT_P3_DJ_CLEAN", lambda p: p["pillar3_uncomputation_partial_trace"]["deutsch_jozsa_uncomputed_clean"].__setitem__("hermitian", False))
        _tamper("AUDIT_P3_DJ_CLEAN", lambda p: p["pillar3_uncomputation_partial_trace"]["deutsch_jozsa_uncomputed_clean"].__setitem__("trace_is_one", False))
        _tamper("AUDIT_P3_DJ_CLEAN", lambda p: p["pillar3_uncomputation_partial_trace"]["deutsch_jozsa_uncomputed_clean"].__setitem__("interference_preserved", False))
        _tamper("INVALID_INT", lambda p: p["pillar3_uncomputation_partial_trace"]["deutsch_jozsa_uncomputed_clean"].__setitem__("dim", True))
        _tamper("AUDIT_P3_DJ_GARBAGE", lambda p: p["pillar3_uncomputation_partial_trace"]["deutsch_jozsa_dropped_garbage"].__setitem__("purity_Tr_rho_sq", "1"))
        _tamper("AUDIT_P3_DJ_GARBAGE", lambda p: p["pillar3_uncomputation_partial_trace"]["deutsch_jozsa_dropped_garbage"].__setitem__("interference_destroyed", False))
        _tamper("AUDIT_P3_GROVER_CLEAN", lambda p: p["pillar3_uncomputation_partial_trace"]["toffoli_grover_uncomputed_clean"].__setitem__("purity_Tr_rho_sq", "5/8"))
        _tamper("AUDIT_P3_GROVER_GARBAGE", lambda p: p["pillar3_uncomputation_partial_trace"]["toffoli_grover_dropped_garbage"].__setitem__("purity_Tr_rho_sq", "1/2"))
        _tamper("AUDIT_P3_FLAGS", lambda p: p["pillar3_uncomputation_partial_trace"].__setitem__("purity_strictly_dropped", False))

        # Pillar 4 tampers (incl. strict keysets, n_in_bits/input_state_count/distinct_output_count/max_fiber_size metadata)
        _tamper("AUDIT_SCHEMA_ERROR", lambda p: p["pillar4_landauer_and_dense_sizes"].__setitem__("extra_p4", 1))
        _tamper("AUDIT_SCHEMA_TYPE", lambda p: p.__setitem__("pillar4_landauer_and_dense_sizes", []))
        _tamper("AUDIT_P4_LANDAUER_AND", lambda p: p["pillar4_landauer_and_dense_sizes"]["irreversible_and_2_to_1"].__setitem__("extra_and", 1))
        _tamper("AUDIT_P4_LANDAUER_AND", lambda p: p["pillar4_landauer_and_dense_sizes"]["irreversible_and_2_to_1"].__setitem__("n_in_bits", 9))
        _tamper("AUDIT_P4_LANDAUER_AND", lambda p: p["pillar4_landauer_and_dense_sizes"]["irreversible_and_2_to_1"].__setitem__("input_state_count", 8))
        _tamper("AUDIT_P4_LANDAUER_AND", lambda p: p["pillar4_landauer_and_dense_sizes"]["irreversible_and_2_to_1"].__setitem__("distinct_output_count", 3))
        _tamper("AUDIT_P4_LANDAUER_AND", lambda p: p["pillar4_landauer_and_dense_sizes"]["irreversible_and_2_to_1"].__setitem__("max_fiber_size", 4))
        _tamper("AUDIT_P4_LANDAUER_AND", lambda p: p["pillar4_landauer_and_dense_sizes"]["irreversible_and_2_to_1"].__setitem__("two_pow_N_H_X_given_Y", 26))
        _tamper("AUDIT_P4_LANDAUER_AND", lambda p: p["pillar4_landauer_and_dense_sizes"]["irreversible_and_2_to_1"].__setitem__("landauer_erasure_lower_bound_bits", "999"))
        _tamper("INVALID_INT", lambda p: p["pillar4_landauer_and_dense_sizes"]["irreversible_and_2_to_1"].__setitem__("two_pow_N_H_X_given_Y", True))
        _tamper("AUDIT_P4_LANDAUER_ERASE", lambda p: p["pillar4_landauer_and_dense_sizes"]["irreversible_reset_1_to_1"].__setitem__("extra_er", 1))
        _tamper("AUDIT_P4_LANDAUER_ERASE", lambda p: p["pillar4_landauer_and_dense_sizes"]["irreversible_reset_1_to_1"].__setitem__("n_in_bits", 2))
        _tamper("AUDIT_P4_LANDAUER_ERASE", lambda p: p["pillar4_landauer_and_dense_sizes"]["irreversible_reset_1_to_1"].__setitem__("max_fiber_size", 1))
        _tamper("AUDIT_P4_LANDAUER_ERASE", lambda p: p["pillar4_landauer_and_dense_sizes"]["irreversible_reset_1_to_1"].__setitem__("two_pow_N_H_X_given_Y", 999))
        _tamper("AUDIT_P4_LANDAUER_ERASE", lambda p: p["pillar4_landauer_and_dense_sizes"]["irreversible_reset_1_to_1"].__setitem__("is_bijection", True))
        _tamper("AUDIT_P4_TOFFOLI", lambda p: p["pillar4_landauer_and_dense_sizes"]["reversible_toffoli_3_to_3"].__setitem__("extra_ccx", 1))
        _tamper("AUDIT_P4_TOFFOLI", lambda p: p["pillar4_landauer_and_dense_sizes"]["reversible_toffoli_3_to_3"].__setitem__("n_in_bits", 2))
        _tamper("AUDIT_P4_TOFFOLI", lambda p: p["pillar4_landauer_and_dense_sizes"]["reversible_toffoli_3_to_3"].__setitem__("max_fiber_size", 2))
        _tamper("AUDIT_P4_TOFFOLI", lambda p: p["pillar4_landauer_and_dense_sizes"]["reversible_toffoli_3_to_3"].__setitem__("involution_verified", False))
        _tamper("AUDIT_P4_SIM_N", lambda p: p["pillar4_landauer_and_dense_sizes"]["dense_statevector_size_table_n1_to_n20"].pop())
        _tamper("AUDIT_P4_SIM_SCALING", lambda p: p["pillar4_landauer_and_dense_sizes"]["dense_statevector_size_table_n1_to_n20"][0].__setitem__("extra_row", 1))
        _tamper("AUDIT_P4_SIM_SCALING", lambda p: p["pillar4_landauer_and_dense_sizes"]["dense_statevector_size_table_n1_to_n20"][0].__setitem__("hilbert_dim_2n", 3))
        _tamper("AUDIT_P4_SIM_SCALING", lambda p: p["pillar4_landauer_and_dense_sizes"]["dense_statevector_size_table_n1_to_n20"][19].__setitem__("overhead_2n_over_n", "999"))
        _tamper("AUDIT_P4_SIM_SCALING", lambda p: p["pillar4_landauer_and_dense_sizes"]["dense_statevector_size_table_n1_to_n20"][19].__setitem__("overhead_decimal_trunc2", "999.00"))
        _tamper("AUDIT_P4_ISO", lambda p: p["pillar4_landauer_and_dense_sizes"].__setitem__("generators_unitary", False))
        _tamper("AUDIT_P4_ISO", lambda p: p["pillar4_landauer_and_dense_sizes"].__setitem__("overhead_strictly_increasing_from_n2", False))

    def test_file_level_canonical_byte_guards(self) -> None:
        _require_real_tmpdir_or_skip(self)
        raw = oracle.canonical_json_bytes(self.valid_cert) + b"\n"
        with tempfile.TemporaryDirectory(prefix="s38_cert_") as tmp:
            td = Path(tmp)
            for fname, content, exp_code in [
                ("crlf.json", raw.replace(b"\n", b"\r\n"), "CRLF_FORBIDDEN"),
                ("nolf.json", raw[:-1], "MISSING_TRAILING_LF"),
                ("badutf8.json", b"\xff\xfe\n", "INVALID_UTF8"),
                ("pretty.json", (json.dumps(self.valid_cert, indent=2) + "\n").encode("ascii"), "NON_CANONICAL_BYTES"),
            ]:
                p = td / fname
                p.write_bytes(content)
                self._expect_err(exp_code, audit.check_certificate_file, p)


class Test98KernelRacesAndConcurrencyStress(unittest.TestCase):
    """Deleted-CWD, renameat2 TOCTOU, hardlink race, 16T/80T concurrent writers, EEXIST/fstat."""

    def _expect_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.SilqBoundaryError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_live_renameat2_toctou_race(self) -> None:
        # Linux/glibc-only renameat2(RENAME_EXCHANGE) TOCTOU race witness; explicitly skips elsewhere
        if sys.platform != "linux":
            self.skipTest("renameat2(RENAME_EXCHANGE) TOCTOU race requires Linux glibc; skipped on " + sys.platform)
        _require_real_tmpdir_or_skip(self)
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is None:
            self.skipTest("libc renameat2 symbol unavailable on this platform")
        if hasattr(renameat2, "argtypes"):
            renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            renameat2.restype = ctypes.c_int

        AT_FDCWD = -100
        RENAME_EXCHANGE = 2
        with tempfile.TemporaryDirectory(prefix="s38_toctou_") as tmp:
            td = Path(tmp)
            canary_dir = td / "canary"
            canary_dir.mkdir(mode=0o700)
            canary_file = canary_dir / "data.json"
            canary_file.write_bytes(b"CANARY_DO_NOT_LEAK_OR_CLOBBER\n")
            safe_dir = td / "slot_a"
            safe_dir.mkdir(mode=0o700)
            (safe_dir / "data.json").write_bytes(b"SAFE_PAYLOAD\n")
            sym_slot = td / "slot_b"
            sym_slot.symlink_to(canary_dir)

            p_a = os.fsencode(str(safe_dir))
            p_b = os.fsencode(str(sym_slot))
            # Synchronous first-call probe: skip cleanly if filesystem/kernel rejects RENAME_EXCHANGE
            probe_rc = renameat2(AT_FDCWD, p_a, AT_FDCWD, p_b, RENAME_EXCHANGE)
            if probe_rc != 0:
                self.skipTest(f"renameat2(RENAME_EXCHANGE) unsupported on tmp filesystem (errno={ctypes.get_errno()})")
            restore_rc = renameat2(AT_FDCWD, p_a, AT_FDCWD, p_b, RENAME_EXCHANGE)
            self.assertEqual(restore_rc, 0)

            stop_ev = threading.Event()
            swaps = [0]
            deadline_ns = time.monotonic_ns() + 15_000_000_000

            def _swapper() -> None:
                consecutive_failures = 0
                while (not stop_ev.is_set() or swaps[0] < 600) and time.monotonic_ns() < deadline_ns:
                    if renameat2(AT_FDCWD, p_a, AT_FDCWD, p_b, RENAME_EXCHANGE) == 0:
                        swaps[0] += 1
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                        if consecutive_failures >= 100:
                            break
                    if stop_ev.is_set() and swaps[0] >= 600:
                        break

            t = threading.Thread(target=_swapper, daemon=True)
            t.start()
            try:
                target = safe_dir / "data.json"
                for i in range(550):
                    try:
                        got = audit.read_regular_bytes_capped(target)
                        self.assertNotIn(b"CANARY", got)
                    except oracle.SilqBoundaryError as exc:
                        self.assertIn(exc.code, ("SYMLINK_FORBIDDEN", "PATH_STAT_ERROR", "FILE_READ_ERROR", "FILE_IO_ERROR"))
                    try:
                        audit.write_regular_file_bytes(target, f"SAFE_WRITE_{i}\n".encode("ascii"))
                    except oracle.SilqBoundaryError as exc:
                        self.assertIn(exc.code, ("SYMLINK_FORBIDDEN", "PATH_STAT_ERROR", "FILE_WRITE_ERROR", "FILE_IO_ERROR"))
            finally:
                stop_ev.set()
                t.join(timeout=5)
            self.assertFalse(t.is_alive())
            self.assertGreaterEqual(swaps[0], 500)
            self.assertEqual(canary_file.read_bytes(), b"CANARY_DO_NOT_LEAK_OR_CLOBBER\n")
            self.assertEqual([p.name for p in safe_dir.glob(".s38_silq_tmp_*")], [])

    def test_renameat2_missing_or_failing_skips_without_hanging(self) -> None:
        # Issue #52 item 5 regression: failing or missing renameat2 must skip cleanly without hanging
        _require_real_tmpdir_or_skip(self)

        class _FailingLibc:
            @staticmethod
            def renameat2(_dfd1: int, _p1: bytes, _dfd2: int, _p2: bytes, _flags: int) -> int:
                return -1

        class _MissingLibc:
            pass

        with mock.patch.object(sys, "platform", "linux"), mock.patch.object(ctypes, "CDLL", return_value=_FailingLibc()):
            with self.assertRaises(unittest.SkipTest):
                self.test_live_renameat2_toctou_race()

        with mock.patch.object(sys, "platform", "linux"), mock.patch.object(ctypes, "CDLL", return_value=_MissingLibc()):
            with self.assertRaises(unittest.SkipTest):
                self.test_live_renameat2_toctou_race()

        with mock.patch.object(sys, "platform", "darwin"):
            with self.assertRaises(unittest.SkipTest):
                self.test_live_renameat2_toctou_race()

    def test_deleted_cwd_hardlink_and_concurrency_stress(self) -> None:
        _require_real_tmpdir_or_skip(self)
        # 1. Deleted CWD fail-closed
        with tempfile.TemporaryDirectory(prefix="s38_cwd_") as tmp:
            doomed = Path(tmp) / "doomed"
            doomed.mkdir(mode=0o700)
            old_cwd = os.getcwd()
            try:
                os.chdir(doomed)
                os.rmdir(doomed)
                self._expect_err("CWD_UNAVAILABLE", audit.require_safe_path, Path("rel.json"))
                proc = subprocess.run(
                    [sys.executable, "-I", "-B", str(Path(_THIS_DIR) / "silq_boundary_calculus_audit.py"), "--check", "rel.json"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(json.loads(proc.stderr)["error_code"], "CWD_UNAVAILABLE")
            finally:
                os.chdir(old_cwd)

        # 2. Live >= 420 concurrent os.link / os.unlink hardlink race + 16T/80T writer burst + EEXIST/fstat guards
        with tempfile.TemporaryDirectory(prefix="s38_conc_") as tmp:
            td = Path(tmp)
            victim = td / "victim.json"
            victim.write_bytes(b"VICTIM_INODE_IMMUTABLE\n")
            target = td / "target.json"
            stop_hl = threading.Event()

            def _hl_racer() -> None:
                while not stop_hl.is_set():
                    try:
                        os.unlink(target)
                    except OSError:
                        pass
                    try:
                        os.link(victim, target)
                    except OSError:
                        pass

            th = threading.Thread(target=_hl_racer, daemon=True)
            th.start()
            try:
                for i in range(420):
                    try:
                        audit.write_regular_file_bytes(target, f"NEW_INODE_{i}\n".encode("ascii"))
                    except oracle.SilqBoundaryError as exc:
                        self.assertIn(exc.code, ("HARDLINK_FORBIDDEN", "FILE_WRITE_ERROR"))
            finally:
                stop_hl.set()
                th.join(timeout=5)
            self.assertEqual(victim.read_bytes(), b"VICTIM_INODE_IMMUTABLE\n")
            self.assertEqual([p.name for p in td.glob(".s38_silq_tmp_*")], [])

            # 16T distinct-target + 16T same-target + 80T barrier burst
            mt_errors: list[str] = []
            mt_lock = threading.Lock()
            d_dir = td / "mt_distinct"
            d_dir.mkdir(mode=0o700)

            def _dw(tid: int) -> None:
                p = d_dir / f"w_{tid}.json"
                for k in range(40):
                    try:
                        audit.write_regular_file_bytes(p, f"D{tid}_{k}\n".encode("ascii"))
                    except Exception as exc:
                        with mt_lock:
                            mt_errors.append(f"d_{tid}_{k}:{exc}")

            ts = [threading.Thread(target=_dw, args=(t,)) for t in range(16)]
            for x in ts:
                x.start()
            for x in ts:
                x.join(timeout=15)
            self.assertEqual(mt_errors, [])
            for tid in range(16):
                p = d_dir / f"w_{tid}.json"
                self.assertEqual(p.read_bytes(), f"D{tid}_39\n".encode("ascii"))
                self.assertEqual(stat.S_IMODE(os.lstat(p).st_mode), 0o600)
            self.assertEqual([p.name for p in d_dir.glob(".s38_silq_tmp_*")], [])

            s_dir = td / "mt_same"
            s_dir.mkdir(mode=0o700)
            shared = s_dir / "shared.json"
            valid_same = {f"S{tid}_{k}\n".encode("ascii") for tid in range(16) for k in range(40)}

            def _sw(tid: int) -> None:
                for k in range(40):
                    try:
                        audit.write_regular_file_bytes(shared, f"S{tid}_{k}\n".encode("ascii"))
                    except Exception as exc:
                        with mt_lock:
                            mt_errors.append(f"s_{tid}_{k}:{exc}")

            ts = [threading.Thread(target=_sw, args=(t,)) for t in range(16)]
            for x in ts:
                x.start()
            for x in ts:
                x.join(timeout=15)
            self.assertEqual(mt_errors, [])
            self.assertIn(shared.read_bytes(), valid_same)
            self.assertEqual([p.name for p in s_dir.glob(".s38_silq_tmp_*")], [])

            b_dir = td / "mt_burst80"
            b_dir.mkdir(mode=0o700)
            barrier = threading.Barrier(80)

            def _bw(tid: int) -> None:
                barrier.wait(timeout=10)
                try:
                    audit.write_regular_file_bytes(b_dir / f"b_{tid}.json", f"B{tid}\n".encode("ascii"))
                except Exception as exc:
                    with mt_lock:
                        mt_errors.append(f"b_{tid}:{exc}")

            ts = [threading.Thread(target=_bw, args=(t,)) for t in range(80)]
            for x in ts:
                x.start()
            for x in ts:
                x.join(timeout=15)
            self.assertEqual(mt_errors, [])
            self.assertEqual(len(list(b_dir.glob("b_*.json"))), 80)
            self.assertEqual([p.name for p in b_dir.glob(".s38_silq_tmp_*")], [])

            # EEXIST retry, exhaustion (TEMP_RETRY_EXHAUSTED), and pre-replace st_nlink != 1 guard
            orig_open = audit.os.open
            orig_fstat = audit.os.fstat
            try:
                calls = {"n": 0}
                def _collide_once(p_arg, flags, *a, **kw):
                    if isinstance(p_arg, str) and p_arg.startswith(".s38_silq_tmp_") and calls["n"] == 0:
                        calls["n"] += 1
                        raise FileExistsError("simulated")
                    return orig_open(p_arg, flags, *a, **kw)
                audit.os.open = _collide_once  # type: ignore[assignment]
                audit.write_regular_file_bytes(s_dir / "retry_ok.json", b"OK\n")
                self.assertEqual((s_dir / "retry_ok.json").read_bytes(), b"OK\n")

                def _always_collide(p_arg, flags, *a, **kw):
                    if isinstance(p_arg, str) and p_arg.startswith(".s38_silq_tmp_"):
                        raise FileExistsError("always")
                    return orig_open(p_arg, flags, *a, **kw)
                audit.os.open = _always_collide  # type: ignore[assignment]
                self._expect_err("TEMP_RETRY_EXHAUSTED", audit.write_regular_file_bytes, s_dir / "retry_fail.json", b"NO\n")

                audit.os.open = orig_open  # type: ignore[assignment]
                class _FakeStat:
                    st_nlink = 2
                audit.os.fstat = lambda _fd: _FakeStat()  # type: ignore[assignment]
                self._expect_err("HARDLINK_FORBIDDEN", audit.write_regular_file_bytes, s_dir / "tmp_hl.json", b"NO\n")
            finally:
                audit.os.open = orig_open
                audit.os.fstat = orig_fstat
            self.assertEqual([p.name for p in s_dir.glob(".s38_silq_tmp_*")], [])


class Test99EndToEndPillarsAndCLI(unittest.TestCase):
    """End-to-end verification of all 4 Track S38 exact pillars and CLI roundtrip."""

    def test_end_to_end_and_cli_roundtrip(self) -> None:
        cert = oracle.build_standalone_certificate()
        p = cert["payload"]
        self.assertTrue(p["all_verified"])
        self.assertEqual(p["oracle_class"], "exact")
        self.assertEqual(p["novelty_classification"], "N0")
        self.assertEqual(len(p["literature_anchors_n0"]), 5)

        # Pillar 1 (exact 9 gates: X, Y, Z, H, S, T, CNOT, CZ, CCX)
        p1 = p["pillar1_cyclotomic_clifford_t"]
        self.assertTrue(p1["pillar_verified"])
        self.assertEqual([g["gate"] for g in p1["gate_certifications"]], ["X", "Y", "Z", "H", "S", "T", "CNOT", "CZ", "CCX"])
        self.assertEqual(len(p1["group_relations_verified"]), 14)

        # Pillar 2
        p2 = p["pillar2_toy_silq_ir_checker"]
        self.assertTrue(p2["pillar_verified"])
        self.assertEqual(p2["valid_program_count"], 6)
        self.assertEqual(p2["must_fail_program_count"], 7)
        self.assertEqual(p2["valid_programs"][2]["synthesized_uncomputations"], ["CCX(a,b,tmp)"])
        self.assertEqual(p2["must_fail_programs"][0]["type_error_code"], "UNCONSUMED_QUANTUM_DROP")

        # Pillar 3
        p3 = p["pillar3_uncomputation_partial_trace"]
        self.assertTrue(p3["pillar_verified"])
        self.assertEqual(p3["deutsch_jozsa_uncomputed_clean"]["purity_Tr_rho_sq"], "1")
        self.assertEqual(p3["deutsch_jozsa_dropped_garbage"]["purity_Tr_rho_sq"], "1/2")
        self.assertEqual(p3["toffoli_grover_uncomputed_clean"]["purity_Tr_rho_sq"], "1")
        self.assertEqual(p3["toffoli_grover_dropped_garbage"]["purity_Tr_rho_sq"], "5/8")

        # Pillar 4
        p4 = p["pillar4_landauer_and_dense_sizes"]
        self.assertTrue(p4["pillar_verified"])
        self.assertTrue(p4["generators_unitary"])
        self.assertEqual(p4["irreversible_and_2_to_1"]["two_pow_N_H_X_given_Y"], 27)
        self.assertEqual(p4["reversible_toffoli_3_to_3"]["two_pow_N_H_X_given_Y"], 1)
        self.assertEqual(p4["dense_statevector_size_table_n1_to_n20"][19]["hilbert_dim_2n"], 1048576)
        self.assertEqual(p4["dense_statevector_size_table_n1_to_n20"][19]["cyclotomic_q_components_4x2n"], 4194304)

        # CLI roundtrip (default, --standalone, --write, --check, '=' syntax)
        _require_real_tmpdir_or_skip(self)
        with tempfile.TemporaryDirectory(prefix="s38_cli_") as tmp:
            cp1 = Path(tmp) / "c1.json"
            cp2 = Path(tmp) / "c2.json"
            for argv, check_fn in [
                ([], lambda out: self.assertIn("OK " + oracle.SCHEMA_VERSION, out)),
                (["--standalone", "--json"], lambda out: self.assertEqual(json.loads(out)["payload_sha256"], cert["payload_sha256"])),
                (["--write", str(cp1), "--json"], lambda out: self.assertTrue(json.loads(out)["written"])),
                (["--check", str(cp1), "--json"], lambda out: self.assertTrue(json.loads(out)["valid"])),
                ([f"--write={cp2}", "--json"], lambda out: self.assertTrue(json.loads(out)["written"])),
                ([f"--check={cp2}", "--json"], lambda out: self.assertTrue(json.loads(out)["valid"])),
            ]:
                buf_out = io.StringIO()
                old_out = sys.stdout
                try:
                    sys.stdout = buf_out
                    rc = audit.main(argv)
                finally:
                    sys.stdout = old_out
                self.assertEqual(rc, 0)
                check_fn(buf_out.getvalue())


if __name__ == "__main__":
    unittest.main()
