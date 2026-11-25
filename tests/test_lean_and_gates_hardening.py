#!/usr/bin/env python3
"""Regression and mutation-killing tests for Lean 4 scanner hardening,
audit-check target-root validation, and pure-Q canonical gates_v2 parsing.

Zero bare asserts. Pure Python 3 standard library.
"""
from __future__ import annotations

import enum
from fractions import Fraction
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

CLI_ROOT = Path(__file__).resolve().parent.parent
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

from aletheia.audit_check import (
    _is_lean4_native_rhs_false,
    _is_lean4_safe_config_span,
    _strip_lean4_comments_and_literals,
    audit_lean4_source,
    run_audit_check,
)
from aletheia import gates_v2 as g2
from aletheia.strict_io import AletheiaError

HAS_MKFIFO = hasattr(os, "mkfifo")


class _Color(enum.IntEnum):
    ONE = 1


class _SubInt(int):
    pass


class _SubFrac(Fraction):
    pass


class _SubStr(str):
    pass


class _LyingStr(str):
    def split(self, *args: object, **kwargs: object) -> list[str]:
        return ["1", "2"]


def _req(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


class TestLean4AndAuditRootHardening(unittest.TestCase):
    def test_01_lean4_raw_strings_zero_and_multi_hash(self) -> None:
        # Exact zero-hash raw string r"\" must NOT escape the closing quote and swallow `sorry`
        src_repro = 'def a := r"\\"\ntheorem t : False := by sorry\ndef b := "x"\n'
        res = audit_lean4_source(src_repro)
        _req(not res["clean"], f"expected finding on raw-string sorry: {res}")
        _req(
            [(f["code"], f["line"]) for f in res["findings"]] == [("LEAN4_SORRY", 2)],
            f"unexpected findings: {res['findings']}",
        )

        # Paired zero-hash raw strings around sorry must also report sorry on line 2
        src_pair = 'def a := r"\\"\ntheorem t : False := by sorry\ndef b := r"\\"\n'
        res_pair = audit_lean4_source(src_pair)
        _req(
            [(f["code"], f["line"]) for f in res_pair["findings"]] == [("LEAN4_SORRY", 2)],
            f"paired raw strings hid sorry: {res_pair['findings']}",
        )

        # Raw string opening at index 0 (col 0, line 1) with alnum EOF so source[-1].isalnum() is True
        src_col0 = 'r"\\"\ntheorem t : False := by sorry'
        res_col0 = audit_lean4_source(src_col0)
        _req(
            [(f["code"], f["line"]) for f in res_col0["findings"]] == [("LEAN4_SORRY", 2)],
            f"col-0 raw string misparsed: {res_col0['findings']}",
        )

        # Non-'r' char immediately before '"' must remain a normal string (escaped quote keeps `sorry` inside string)
        r_non_r = audit_lean4_source('def s := ("\\" sorry")\ntheorem ok : True := trivial\n')
        _req(r_non_r["clean"], f"non-r quote misparsed as raw string: {r_non_r['findings']}")

        # Multiline zero-hash raw string preserves line numbers
        src_ml = 'def a := r"line1\nline2\\"\ntheorem bad : False := by sorry\n'
        res_ml = audit_lean4_source(src_ml)
        _req(
            [(f["code"], f["line"]) for f in res_ml["findings"]] == [("LEAN4_SORRY", 3)],
            f"multiline raw string line count drifted: {res_ml['findings']}",
        )

        # Well-formed raw strings (0, 1, 2 hashes) containing quotes/backslashes/sorry are clean
        for clean_src in (
            'def a := r"sorry \\ "\ntheorem ok : True := trivial\n',
            'def a := r#"sorry " \\ "#\ntheorem ok : True := trivial\n',
            'def a := r##"sorry "# \\ "##\ntheorem ok : True := trivial\n',
            'def r := 1\ntheorem ok : True := trivial\n',
            'def x := r#a\n',
            'def x := r#',
        ):
            r_ok = audit_lean4_source(clean_src)
            _req(r_ok["clean"], f"false positive on clean Lean source {clean_src!r}: {r_ok}")

        # Preceding Lean identifier characters (alnum, _, ., ', !, ?) mean `r` is NOT a raw string
        for id_src in (
            'def bar"\\" := 1\n',
            'def foo_r"\\" := 1\n',
            'def Foo.r"\\" := 1\n',
            'def foo\'r"\\" := 1\n',
            'def foo!r"\\" := 1\n',
            'def foo?r"\\" := 1\n',
        ):
            r_id = audit_lean4_source(id_src)
            _req(
                [f["code"] for f in r_id["findings"]] == ["LEAN4_UNTERMINATED_STRING"],
                f"identifier-prefixed r\" must not open raw string: {id_src!r} -> {r_id}",
            )
        # Exact Foo.r"\"" regression: must NOT swallow theorem t : False := sorry on line 3
        foo_dot_r = (
            "def Foo.r (s : String) : String := s\n"
            'def a := Foo.r"\\""\n'
            "theorem t : False := sorry\n"
            'def b := "\\""\n'
        )
        r_fdr = audit_lean4_source(foo_dot_r)
        _req(
            [(f["code"], f["line"]) for f in r_fdr["findings"]] == [("LEAN4_SORRY", 3)],
            f"Foo.r plain string hid sorry: {r_fdr['findings']}",
        )

        # Unterminated zero-hash raw string (raw_hashes == 0) and 1-hash raw string must fail closed
        for unterm in ('def a := r"unterminated\n', 'def a := r#"unterminated\n', 'def a := "unterminated\n'):
            r_u = audit_lean4_source(unterm)
            _req(
                [(f["code"], f["line"]) for f in r_u["findings"]] == [("LEAN4_UNTERMINATED_STRING", 1)],
                f"unterminated string not reported on line 1: {unterm!r} -> {r_u}",
            )
        r_uc = audit_lean4_source("/- unterminated comment\n")
        _req(
            [(f["code"], f["line"]) for f in r_uc["findings"]] == [("LEAN4_UNTERMINATED_COMMENT", 1)],
            f"unterminated comment not reported: {r_uc}",
        )

    def test_02_lean4_decide_plus_native_detection(self) -> None:
        for bad_src, exp_line in (
            ("theorem t : 1 + 1 = 2 := by decide +native\n", 1),
            ("theorem t : 1 + 1 = 2 := by\n  decide\n    +native\n", 2),
            ("theorem t : 1 + 1 = 2 := by decide +revert +native\n", 1),
            ("theorem t : 1 + 1 = 2 := by decide -revert +native\n", 1),
            ("theorem t : 1 + 1 = 2 := by decide +kernel -revert +native\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide (native := true)\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide (kernel := false) +native\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide (kernel := false)+native\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide +revert+native\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide+native\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide-revert+native\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide (native := Bool.true)\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide (native := (true))\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide (native := ((true)))\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide (native := (false || (true)))\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide (native := !false)\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide (native := false || true)\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide (native := false) +native\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide (config := { native := Bool.true })\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide (config := (({ native := true })))\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide (kernel := (by decide+native))\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide +revert (native := true)\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide (revert := true) (native := true)\n", 1),
            ("theorem t : 1 + 1 = 2 := by decide (config := { native := true })\n", 1),
            ("theorem t : 2 + 2 = 4 := by decide (config := ({ native := true } : DecideConfig))\n", 1),
            ("def cfg : DecideConfig := { native := true }\n", 1),
            ("def cfg : DecideConfig := { native := Bool.true }\n", 1),
            ("def cfg := ({ native := true } : Lean.Elab.Tactic.DecideConfig)\n", 1),
            ("def cfg := { native := true : DecideConfig }\n", 1),
            ("def cfg := { native := !false : DecideConfig }\n", 1),
            ("theorem t : 1 + 1 = 2 := by\n  decide (config := {\n    revert := true,\n    native := true\n  })\n", 2),
            ("theorem t : 1 + 1 = 2 := by decide (config := { native := true, revert := false })\n", 1),
            # Guillemet-escaped identifiers (Lean 4 lexer strips French guillemets before elaboration)
            ("theorem t : 1 + 1 = 2 := by decide +«native»\n", 1),
            ("theorem t : 1 + 1 = 2 := by decide («native» := true)\n", 1),
            ("theorem t : 1 + 1 = 2 := by decide (config := { «native» := true })\n", 1),
            ("theorem t : 1 + 1 = 2 := by decide («config» := { native := true })\n", 1),
            ("theorem t : 1 + 1 = 2 := by «decide» +«native»\n", 1),
            # Positional, constructor, indirect, with-update, field-punned, and non-record config forms
            ("theorem t : 1 + 1 = 2 := by decide (config := ⟨false, true, false, false⟩)\n", 1),
            ("theorem t : 1 + 1 = 2 := by decide (config := .mk false true false false)\n", 1),
            ("theorem t : 1 + 1 = 2 := by decide (config := Lean.Parser.Tactic.DecideConfig.mk false true false false)\n", 1),
            ("def c : Lean.Parser.Tactic.DecideConfig := ⟨false, true, false, false⟩\ntheorem t : 1 + 1 = 2 := by decide (config := c)\n", 2),
            ("def c0 : Lean.Parser.Tactic.DecideConfig := {}\ndef c1 := { c0 with native := true }\ntheorem t : 1 + 1 = 2 := by decide (config := c1)\n", 3),
            ("def native : Bool := true\ntheorem t : 1 + 1 = 2 := by decide (config := { native })\n", 2),
            ("theorem t : 1 + 1 = 2 := by decide (config := { c0 with kernel := true })\n", 1),
            ("theorem t : 1 + 1 = 2 := by decide (config := { ({} : Lean.Parser.Tactic.DecideConfig) with native := true })\n", 1),
            # Custom infix operators starting with `:` or `,` and type-ascribed bound DecideConfig
            ('infixr:65 " :+ " => fun (_ _ : Bool) => true\ntheorem t : 1 + 1 = 2 := by decide (config := { native := false :+ false })\n', 2),
            ('infixr:65 " ,+ " => fun (_ _ : Bool) => true\ntheorem t : 1 + 1 = 2 := by decide (config := { native := false ,+ false })\n', 2),
            ("def c : DecideConfig := { native := (true : Bool) }\n", 1),
            # Malformed / asymmetric brace & empty config forms fail closed cleanly
            ("theorem t : 1 + 1 = 2 := by decide (config := )\n", 1),
            ("theorem t : 1 + 1 = 2 := by decide (config := { kernel := true)\n", 1),
            ("theorem t : 1 + 1 = 2 := by decide (config := kernel := true })\n", 1),
            ("theorem t : 1 + 1 = 2 := by decide (config := { { })\n", 1),
            ("theorem t : 1 + 1 = 2 := by decide (config := { } })\n", 1),
        ):
            res = audit_lean4_source(bad_src)
            _req(not res["clean"], f"decide +native was missed: {bad_src!r}")
            _req(
                [(f["code"], f["line"]) for f in res["findings"]] == [("LEAN4_DECIDE_NATIVE", exp_line)],
                f"unexpected findings for {bad_src!r}: {res['findings']}",
            )

        # Bound DecideConfig before or after a separate `decide +native` reports both lines
        both_before = audit_lean4_source(
            "def cfg : DecideConfig := { native := true }\ntheorem t : 2 + 2 = 4 := by decide +native\n"
        )
        _req(
            sorted((f["code"], f["line"]) for f in both_before["findings"])
            == [("LEAN4_DECIDE_NATIVE", 1), ("LEAN4_DECIDE_NATIVE", 2)],
            f"expected both findings: {both_before['findings']}",
        )
        both_after = audit_lean4_source(
            "theorem t : 2 + 2 = 4 := by decide +native\ndef cfg : DecideConfig := { native := true }\n"
        )
        _req(
            sorted((f["code"], f["line"]) for f in both_after["findings"])
            == [("LEAN4_DECIDE_NATIVE", 1), ("LEAN4_DECIDE_NATIVE", 2)],
            f"expected both findings: {both_after['findings']}",
        )

        # Non-native decide and commented/stringified forms must not false-positive
        for ok_src in (
            "theorem t : 1 + 1 = 2 := by decide\n",
            "theorem t : 1 + 1 = 2 := by decide +kernel\n",
            "theorem t : 1 + 1 = 2 := by decide +revert\n",
            "theorem t : 1 + 1 = 2 := by decide -revert\n",
            "theorem t : 1 + 1 = 2 := by decide +revert -native\n",
            "theorem t : 2 + 2 = 4 := by decide (native := false)\n",
            "theorem t : 2 + 2 = 4 := by decide (native := Bool.false)\n",
            "theorem t : 2 + 2 = 4 := by decide (native := (false))\n",
            "theorem t : 2 + 2 = 4 := by decide (native := ((Bool.false)))\n",
            "theorem t : 2 + 2 = 4 := by decide (kernel := true) -native\n",
            "theorem t : 1 + 1 = 2 := by decide (config := { native := false })\n",
            "theorem t : 1 + 1 = 2 := by decide (config := {})\n",
            "theorem t : 1 + 1 = 2 := by decide (config := { kernel := true })\n",
            "theorem t : 1 + 1 = 2 := by decide (config :=   ( ( { native := ((Bool.false)) } ) )  )\n",
            "theorem t : 1 + 1 = 2 := by decide (config := (({ native := ((Bool.false)) })))\n",
            "theorem t : 1 + 1 = 2 := by decide (config := { native := Bool.false, revert := true })\n",
            "theorem t : 1 + 1 = 2 := by decide (config := { native := false, })\n",
            "theorem t : 1 + 1 = 2 := by decide (config := { my_native := true, with_extra := false })\n",
            "theorem t : 1 + 1 = 2 := by decide (config := { «native» := «false» })\n",
            "theorem t : 1 + 1 = 2 := by decide (config := { «native» := «Bool».«false» })\n",
            "def f (decide : Nat) : Nat := decide+1\n",
            "def x := decide ",
            "def x := decide + (1)\n",
            "def x := decide (a + b)\n",
            "def x := decide (\n",
            ") theorem t : 1 = 1 := by decide\n",
            "def cfg : DecideConfig := { native := false }\n",
            "def cfg := { native := false : DecideConfig }\n",
            "def cfg : OtherConfig := { native := true }\n",
            "def my_decide_x := 1\n-- decide +native\n",
            'def s1 := "decide +native"\ndef s2 := r"decide +native"\ndef s3 := r#"decide (config := { native := true })"#\n',
        ):
            res_ok = audit_lean4_source(ok_src)
            _req(res_ok["clean"], f"false positive on {ok_src!r}: {res_ok['findings']}")

        # Direct _is_lean4_native_rhs_false boundary checks
        _req(_is_lean4_native_rhs_false("false") is True, "false must be false")
        _req(_is_lean4_native_rhs_false("  false  ") is True, "padded false must be false")
        _req(_is_lean4_native_rhs_false("(false)") is True, "exact 7-char (false) must be false")
        _req(_is_lean4_native_rhs_false("(( Bool.false ))") is True, "parenthesized Bool.false must be false")
        for non_false in ("", "   ", "(", "()", "true", "(false!", "!false)", "(false) || true"):
            _req(_is_lean4_native_rhs_false(non_false) is False, f"{non_false!r} must not be treated as false")

        # Direct _is_lean4_safe_config_span boundary checks (empty/whitespace-only/paren-matched)
        _req(_is_lean4_safe_config_span("", 0, 0, {}) is False, "empty config span must fail closed")
        _req(_is_lean4_safe_config_span("   ", 0, 3, {}) is False, "whitespace-only config span must fail closed")
        _req(_is_lean4_safe_config_span("{}", 0, 2, {}) is True, "empty record literal must pass")
        _req(_is_lean4_safe_config_span(" ( {} ) ", 0, 8, {1: 6}) is True, "padded matched-paren record must pass")

        # Linear-time ReDoS guard: unclosed braces, repeated DecideConfig, and deep parens finish in < 200 ms
        for redos_src, expect_clean in (
            ("{ " * 5000 + "\n", True),
            ("{ native := false " * 2000 + "\n", True),
            ("DecideConfig " * 2000 + "\n", True),
            ("decide " + "(" * 5000 + ")" * 5000 + "\n", True),
            ("decide (" * 5000 + "\n", True),
            ("decide (config := " + "(" * 1500 + "{ native := false }" + ")" * 1500 + ")\n", True),
            ("decide (config := " * 1500 + "{ native := false }" + ")" * 1500 + "\n", False),
        ):
            t0 = time.monotonic()
            res_r = audit_lean4_source(redos_src)
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            _req(res_r["clean"] is expect_clean, f"unexpected clean={res_r['clean']} on ReDoS probe: {res_r['findings']}")
            _req(elapsed_ms < 200.0, f"quadratic backtracking regression: {elapsed_ms:.1f} ms")

        # End-to-end through run_audit_check(..., lean_audit=True)
        with tempfile.TemporaryDirectory(prefix="aletheia_lean_hard_") as td:
            root = Path(td).resolve()
            (root / "Bad.lean").write_text(
                'def a := r"\\"\ntheorem t : False := by decide -revert +native\n',
                encoding="utf-8",
            )
            rep = run_audit_check(root, lean_audit=True)
            _req(not rep["passed"], "audit-check --lean-audit must fail on decide -revert +native")
            codes = [f["code"] for f in rep["lean_audit"]["findings"]]
            _req(codes == ["LEAN4_DECIDE_NATIVE"], f"wrong end-to-end lean codes: {codes}")

    def test_02b_lean4_interpolated_strings_char_desync_and_kernel_escapes(self) -> None:
        # Interpolated strings s!"{...}" / m!"{...}" must expose embedded Lean code while blanking literal text
        for bad_src, exp_findings in (
            ('def x := s!"{sorry}"\n', [("LEAN4_SORRY", 1)]),
            ('s!"{sorry}" ++ x', [("LEAN4_SORRY", 1)]),
            ('def x := m!"{admit}"\n', [("LEAN4_ADMIT", 1)]),
            ('def x := f!"{sorry}"\n', [("LEAN4_SORRY", 1)]),
            ('def x := s!"prefix {sorry} suffix"\n', [("LEAN4_SORRY", 1)]),
            ('def x := s!"a {let _ := { y := 1 }; sorry} b"\n', [("LEAN4_SORRY", 1)]),
            ('def x := s!"a {if true then "ok" else sorry} b"\n', [("LEAN4_SORRY", 1)]),
            ('def x := s!"a {s!"{sorry}"} b"\n', [("LEAN4_SORRY", 1)]),
            ('def x := s!"line1\nline2"\ntheorem t : False := by sorry\n', [("LEAN4_SORRY", 3)]),
            ('def x := s!"\\\n"\ntheorem t : False := by sorry\n', [("LEAN4_SORRY", 3)]),
            ('def x := "\\\n"\ntheorem t : False := by sorry\n', [("LEAN4_SORRY", 3)]),
            (
                'def foo! (s : String) : Nat := s.length\ndef a := foo!"{"\ntheorem t : False := sorry\ndef b := "}"\n',
                [("LEAN4_UNKNOWN_BANG_STRING", 2), ("LEAN4_SORRY", 3)],
            ),
            (
                'def a : Nat := panic!"{"\ntheorem t : False := sorry\ndef b := "}"\n',
                [("LEAN4_SORRY", 2)],
            ),
            (
                'def a := foos!"{"\ntheorem t : False := sorry\ndef b := "}"\n',
                [("LEAN4_UNKNOWN_BANG_STRING", 1), ("LEAN4_SORRY", 2)],
            ),
            (
                'def a := Foo.s!"{"\ntheorem t : False := sorry\ndef b := "}"\n',
                [("LEAN4_UNKNOWN_BANG_STRING", 1), ("LEAN4_SORRY", 2)],
            ),
            (
                '!"{"\ntheorem t : False := sorry\ndef b := "}" ++ s',
                [("LEAN4_SORRY", 2)],
            ),
            ('def x := s!"unclosed\n', [("LEAN4_UNTERMINATED_STRING", 1)]),
            ('def x := s!"line1\n{ "ok"\n', [("LEAN4_UNTERMINATED_STRING", 1)]),
            ('def x := s!"line1\n{ /- unclosed\n', [("LEAN4_UNTERMINATED_COMMENT", 2)]),
            ('let _c := \'"\'\ntheorem t : False := by sorry\n-- "\n', [("LEAN4_SORRY", 2)]),
            ("theorem t : False := exact sorryAx False false\n", [("LEAN4_SORRY_AX", 1)]),
            ("meta def f := Lean.Meta.mkSorry\n", [("LEAN4_MK_SORRY", 1)]),
            ("meta def f := mkSorry\n", [("LEAN4_MK_SORRY", 1)]),
            ("def x := Lean.ofReduceNat\n", [("LEAN4_OF_REDUCE_NAT", 1)]),
        ):
            res = audit_lean4_source(bad_src)
            _req(not res["clean"], f"expected finding for {bad_src!r}: {res}")
            _req(
                [(f["code"], f["line"]) for f in res["findings"]] == exp_findings,
                f"wrong findings for {bad_src!r}: got {res['findings']}, want {exp_findings}",
            )

        # Clean interpolated strings, escaped braces, normal strings with {sorry}, and boolean negation !true
        for clean_src in (
            'def greet (n : String) := s!"hello {n} sorry"\n',
            'def esc := s!"hello \\{sorry} \\" world"\n',
            'def plain := "hello {sorry}"\n',
            'def neg := !true\n',
            'def nested := s!"a {if true then "sorry" else "ok"} b"\n',
            'def raw_interp := r#"s!"{sorry}""#\n',
            'def brace_in_comment := s!"a { -- }\n  1 } b"\n',
            'def a : Nat := panic!"bad {sorry} state"\n',
            'def a : Nat := panic!"abc\ntheorem t : True := by sorry\n"\n',
            'panic!"ok"\n',
            'def a := s "hello {sorry}"\n',
            'def a := s!x\n',
            'def x! (s : String) := s\ndef a := x! "bad {sorry} state"\n',
            'def foo! (s : String) := s\ndef f := foo! "abc\ntheorem t : True := by sorry\n"\n',
        ):
            r_ok = audit_lean4_source(clean_src)
            _req(r_ok["clean"], f"false positive on clean interpolated/negation source {clean_src!r}: {r_ok}")

    def test_02c_lean4_post_decl_attributes_eval_spoof_and_char_desync(self) -> None:
        # 1. Identifier-prime + Char literal desync and \xHH / \uHHHH Char-escape desyncs
        for label, bad_src, exp_findings in (
            (
                "xprime_skipKernelTC",
                "def f (x' : Char -> Nat) : Nat := x' '\"'\nset_option debug.skipKernelTC true\ntheorem evil : 1 = 1 := rfl\ndef g : String := \"\\\"\"\n",
                [("LEAN4_SKIP_KERNEL_TC", 2)],
            ),
            (
                "xprime_sorry",
                "def f (x' : Char -> Nat) : Nat := x' '\"'\ntheorem evil : False := by sorry\ndef g : String := \"\\\"\"\n",
                [("LEAN4_SORRY", 2)],
            ),
            (
                "double_prime_sorry",
                "def f (x'' : Char -> Nat) : Nat := x'' '\"'\ntheorem evil : False := by sorry\ndef g : String := \"\\\"\"\n",
                [("LEAN4_SORRY", 2)],
            ),
            (
                "underscore_prime_sorry",
                "def f (x_' : Char -> Nat) : Nat := x_' '\"'\ntheorem evil : False := by sorry\ndef g : String := \"\\\"\"\n",
                [("LEAN4_SORRY", 2)],
            ),
            (
                "guillemet_prime_sorry",
                "def f («x»' : Char -> Nat) : Nat := «x»' '\"'\ntheorem evil : False := by sorry\ndef g : String := \"\\\"\"\n",
                [("LEAN4_SORRY", 2)],
            ),
            (
                "escaped_quote_char_desync",
                "def f (a b : Char) : Nat := 0\ndef x := f '\\'' '\"'\ntheorem evil : False := by sorry\ndef g : String := \"\\\"\"\n",
                [("LEAN4_SORRY", 3)],
            ),
            (
                "hex_char_desync",
                "def f (a b : Char) : Nat := 0\ndef x := f '\\x27' '\"'\ntheorem evil : False := by sorry\ndef g : String := \"\\\"\"\n",
                [("LEAN4_SORRY", 3)],
            ),
            (
                "unicode_char_desync",
                "def f (a b : Char) : Nat := 0\ndef x := f '\\u0027' '\"'\ntheorem evil : False := by sorry\ndef g : String := \"\\\"\"\n",
                [("LEAN4_SORRY", 3)],
            ),
            (
                "col0_char_with_alnum_eof",
                "'\"'\ntheorem t : False := by sorry",
                [("LEAN4_SORRY", 2)],
            ),
            (
                "literal_nl_char_preserves_lines",
                "'\n'\ntheorem t : False := by sorry\n",
                [("LEAN4_SORRY", 3)],
            ),
            (
                "escaped_nl_char_preserves_lines",
                "'\\\n'\ntheorem t : False := by sorry\n",
                [("LEAN4_SORRY", 3)],
            ),
            (
                "non_backslash_4char_not_char_literal",
                "def a := '\"x'\n",
                [("LEAN4_UNTERMINATED_STRING", 1)],
            ),
            (
                "backslash_missing_close_quote",
                "def a := '\\a\"x\n",
                [("LEAN4_UNTERMINATED_STRING", 1)],
            ),
        ):
            res = audit_lean4_source(bad_src)
            _req(not res["clean"], f"{label} bypassed audit_lean4_source: {res}")
            _req(
                [(f["code"], f["line"]) for f in res["findings"]] == exp_findings,
                f"wrong findings for {label}: got {res['findings']}, want {exp_findings}",
            )

        # Direct Char-literal boundary & hex/unicode escape checks on _strip_lean4_comments_and_literals
        _req(_strip_lean4_comments_and_literals("def c := '\\''") == "def c :=     ", "escaped quote '\\'' must blank all 4 chars")
        _req(_strip_lean4_comments_and_literals("'a") == "'a", "short len-2 quote must not read past EOF")
        _req(_strip_lean4_comments_and_literals("'\\a") == "'\\a", "short len-3 escape must not read past EOF")
        _req(_strip_lean4_comments_and_literals("'\\x27") == "'\\x27", "short len-5 hex must not read past EOF")
        _req(_strip_lean4_comments_and_literals("'\\u0027") == "'\\u0027", "short len-7 unicode must not read past EOF")
        _req(_strip_lean4_comments_and_literals("def a := '\\a27'") == "def a := '\\a27'", "non-x 6-char escape must stay intact")
        _req(_strip_lean4_comments_and_literals("def a := '\\x27a") == "def a := '\\x27a", "unclosed hex char must stay intact")
        _req(_strip_lean4_comments_and_literals("def a := '\\xZZ'") == "def a := '\\xZZ'", "non-hex \\x escape must stay intact")
        _req(_strip_lean4_comments_and_literals("def a := '\\a0027'") == "def a := '\\a0027'", "non-u 8-char escape must stay intact")
        _req(_strip_lean4_comments_and_literals("def a := '\\u0027a") == "def a := '\\u0027a", "unclosed unicode char must stay intact")
        _req(_strip_lean4_comments_and_literals("def a := '\\uZZZZ'") == "def a := '\\uZZZZ'", "non-hex \\u escape must stay intact")
        _req(_strip_lean4_comments_and_literals("def a := '\\x2A'") == "def a :=       ", "valid \\x2A must blank to 6 spaces")
        _req(_strip_lean4_comments_and_literals("def a := '\\u002F'") == "def a :=         ", "valid \\u002F must blank to 8 spaces")

        for ok_char in (
            "def x : Char := ('\"')\n",
            "def x:Char:='\"'\n",
            "def c : Char := '\\x22'\n",
            "def c : Char := '\\u0022'\n",
            "def c : Char := '\\''\n",
            "def c : Char := '\\\\'\n",
        ):
            _req(audit_lean4_source(ok_char)["clean"], f"false positive on clean char literal {ok_char!r}")

        # 2. Post-declaration `attribute [...]` trust escapes & csimp notices + O(n) balanced-bracket scanning
        for label, bad_attr, exp_line, exp_excerpt in (
            ("post_attr_extern", 'opaque foo : Nat\nattribute [extern "c_foo"] foo\n', 2, "extern"),
            ("post_attr_impl", "def f_impl : Nat := 1\ndef f_spec : Nat := 0\nattribute [implemented_by f_impl] f_spec\n", 3, "implemented_by"),
            ("post_attr_multiline", 'opaque foo : Nat\nattribute\n  [extern "c_foo"]\n  foo\n', 2, "extern"),
            ("post_attr_inline_extern", 'opaque foo : Nat\nattribute [inline, extern "c_foo[0]"] foo\n', 2, "extern"),
            ("local_attr_extern", 'local attribute [extern "c_foo"] foo\n', 1, "extern"),
            ("scoped_attr_impl", "scoped attribute [implemented_by f_impl] f_spec\n", 1, "implemented_by"),
            ("guillemet_attr_extern", 'attribute [«extern» "c_foo"] foo\n', 1, "extern"),
            ("nested_brack_attr_extern", 'attribute [my_attr [0], extern "c_foo"] foo\n', 1, "extern"),
            ("stray_rbrack_then_at_extern", '] @[extern "c_foo"] opaque f : Nat\n', 1, "extern"),
        ):
            res_a = audit_lean4_source(bad_attr)
            _req(
                [(f["code"], f["line"], f["excerpt"]) for f in res_a["findings"]]
                == [("LEAN4_ATTR_TRUST_ESCAPE", exp_line, exp_excerpt)],
                f"wrong attr findings for {label}: {res_a['findings']}",
            )

        for label, csimp_src, exp_line in (
            ("post_attr_csimp", "def a : Nat := 0\ndef b : Nat := 0\ntheorem ab : a = b := rfl\nattribute [csimp] ab\n", 4),
            ("post_attr_local_csimp", "def a : Nat := 0\ndef b : Nat := 0\ntheorem ab : a = b := rfl\nattribute [local csimp] ab\n", 4),
        ):
            res_cs = audit_lean4_source(csimp_src)
            _req(res_cs["clean"], f"csimp should be notice not hard finding for {label}: {res_cs}")
            _req(
                [(n["code"], n["line"], n["excerpt"]) for n in res_cs["notices"]]
                == [("LEAN4_CSIMP_REWRITE_NOTICE", exp_line, "csimp")],
                f"missing csimp notice for {label}: {res_cs['notices']}",
            )

        for ok_attr in (
            "attribute [simp] foo\n",
            'Foo.attribute [extern "c_foo"]\n',
            "def x := [extern]\n",
            'attribute [extern "unclosed\n',
            '-- attribute [extern "c_foo"] foo\n',
            'def s := "attribute [extern \\"c_foo\\"] foo"\n',
        ):
            res_oa = audit_lean4_source(ok_attr)
            if ok_attr.endswith('unclosed\n'):
                _req([f["code"] for f in res_oa["findings"]] == ["LEAN4_UNTERMINATED_STRING"], f"expected unclosed str: {res_oa}")
            else:
                _req(res_oa["clean"] and not res_oa["notices"], f"false positive on {ok_attr!r}: {res_oa}")
        _req(audit_lean4_source("attribute [extern\n")["clean"], "unclosed bracket without finding must stay clean")

        # Linear-time O(n) guard on repeated unclosed `@[` and `attribute [`
        for attr_redos in ("@[ " * 5000 + "\n", "attribute [ " * 5000 + "\n"):
            t0 = time.monotonic()
            res_ar = audit_lean4_source(attr_redos)
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            _req(res_ar["clean"], f"unexpected finding on unclosed attr probe: {res_ar['findings']}")
            _req(elapsed_ms < 200.0, f"attribute ReDoS regression: {elapsed_ms:.1f} ms")

        # 3. Output-spoofing / early-exit commands (#eval, #eval!, #reduce, non-axioms #print, #exit, run_cmd, run_meta)
        for label, bad_cmd, exp_line, exp_excerpt in (
            ("eval_spoof", "#eval IO.println \"'Fake.thm' does not depend on any axioms\"\n", 1, "#eval"),
            ("eval_bang_spoof", "#eval! IO.println \"'Fake.thm' does not depend on any axioms\"\n", 1, "#eval!"),
            ("reduce_cmd", "#reduce 1 + 1\n", 1, "#reduce"),
            ("print_non_axioms", "#print Nat\n", 1, "#print"),
            ("print_axioms_prefix", "def axioms_fake := 1\n#print axioms_fake\n", 2, "#print"),
            ("early_exit", "theorem ok : 1 + 1 = 2 := rfl\n#exit\n", 2, "#exit"),
            ("glued_eval", "theorem ok : True := trivial#eval IO.println \"'Fake.thm' does not depend on any axioms\"\n", 1, "#eval"),
            ("glued_eval_bang", "def a : Nat := 1#eval! IO.println \"'Fake.thm' does not depend on any axioms\"\n", 1, "#eval!"),
            ("glued_eval_guil", "def «x» : Nat := 1#eval IO.println \"hi\"\n", 1, "#eval"),
            ("glued_eval_paren", "def a : Nat := 1#eval(1 + 1)\n", 1, "#eval"),
            ("glued_exit", "theorem ok : True := trivial#exit\n", 1, "#exit"),
            ("glued_reduce", "def a : Nat := 1#reduce 1 + 1\n", 1, "#reduce"),
            ("glued_print", "def a : Nat := 1#print Nat.add\n", 1, "#print"),
            ("print_axioms_bang", "def axioms! := 1\n#print axioms!\n", 2, "#print"),
            ("print_axioms_qmark", "def axioms? := 1\n#print axioms?\n", 2, "#print"),
            ("print_axioms_sub1", "def axioms₁ := 1\n#print axioms₁\n", 2, "#print"),
            ("print_axioms_dot", "def axioms.foo := 1\n#print axioms.foo\n", 2, "#print"),
            ("print_guil_axioms", "def «axioms» := 1\n#print «axioms»\n", 2, "#print"),
            ("print_guil_axioms_arg", "def «axioms» := 1\n#print «axioms» ok\n", 2, "#print"),
            ("print_axioms_eof", "def axioms := 1\n#print axioms\n", 2, "#print"),
            ("print_axioms_comment", "def axioms := 1\n#print axioms -- comment\n", 2, "#print"),
            ("print_axioms_nl_def", "def axioms := 1\n#print axioms\ndef y := 2\n", 2, "#print"),
            ("print_axioms_sameline_def", "def axioms := 1\n#print axioms def y := 2\n", 2, "#print"),
            ("run_cmd_meta", "run_cmd pure ()\n", 1, "run_cmd"),
            ("run_meta_cmd", "run_meta pure ()\n", 1, "run_meta"),
        ):
            res_c = audit_lean4_source(bad_cmd)
            _req(
                [(f["code"], f["line"], f["excerpt"]) for f in res_c["findings"]]
                == [("LEAN4_EVAL_SPOOF", exp_line, exp_excerpt)],
                f"wrong eval-spoof findings for {label}: {res_c['findings']}",
            )
        # run_cmd must still fail even under allow_non_init_imports=True
        res_rc = audit_lean4_source(
            'import Lean\nrun_cmd Lean.logInfo "\'Fake.thm\' does not depend on any axioms"\n',
            allow_non_init_imports=True,
        )
        _req(
            [(f["code"], f["line"], f["excerpt"]) for f in res_rc["findings"]]
            == [("LEAN4_EVAL_SPOOF", 2, "run_cmd")],
            f"run_cmd bypassed allow_non_init_imports=True: {res_rc}",
        )

        # Clean #print axioms (single-line, multiline, keyword-prefix ident), guillemet `#eval`, dot-projection, and array `#`
        for ok_cmd in (
            "theorem ok : 1 + 1 = 2 := rfl\n#print axioms ok\n",
            "theorem ok : 1 + 1 = 2 := rfl\n#print\n  axioms ok\n",
            "theorem def_foo : 1 + 1 = 2 := rfl\n#print axioms def_foo\n",
            'def s := "#eval 1"\n-- #reduce 1\n/- #print Nat -/\ndef r := r#"#exit"#\ndef a := #[1, 2]\n',
            "def «#eval» : Nat := 1\n",
            "def x := Foo.run_cmd\n",
        ):
            res_oc = audit_lean4_source(ok_cmd)
            _req(res_oc["clean"], f"false positive on clean #print/array source {ok_cmd!r}: {res_oc['findings']}")

        # 4. Guillemet-escaped identifiers («...») and `!`/`?` identifier-prime Char desyncs
        for label, bad_src, exp_findings in (
            ("guil_line_comment_sorry", "theorem «--» : False := by sorry\n", [("LEAN4_SORRY", 1)]),
            ("guil_dquote_sorry", 'def «"» : Nat := 1\ntheorem fake : False := by sorry\ndef «" » : Nat := 2\n', [("LEAN4_SORRY", 2)]),
            (
                "guil_block_comment_hijack",
                "def «/-» : Nat := 1\nset_option debug.skipKernelTC true\ntheorem fake : False := by sorry\ndef «-/» : Nat := 2\n",
                [("LEAN4_SORRY", 3), ("LEAN4_SKIP_KERNEL_TC", 2)],
            ),
            ("guil_interp_hijack", 'def «s!"» : Nat := 1\ntheorem fake : False := by sorry\ndef «"» : Nat := 2\n', [("LEAN4_SORRY", 2)]),
            ("guil_raw_hijack", 'def «r#"» : Nat := 1\ntheorem fake : False := by sorry\ndef «"#» : Nat := 2\n', [("LEAN4_SORRY", 2)]),
            ("guil_multiline_preserves_lines", "def «a\nb» : Nat := 1\ntheorem fake : False := by sorry\n", [("LEAN4_SORRY", 3)]),
            ("guil_rbrace_in_interp", 'def x := s!"{ let «}» := 1; sorry }"\n', [("LEAN4_SORRY", 1)]),
            ("guil_unterminated", "def «unclosed\nline2 := 1\n", [("LEAN4_UNTERMINATED_IDENT", 1)]),
            (
                "xprime_bang_char_desync",
                "def f (x!' : Char -> Nat) : Nat := x!' '\"'\ntheorem fake : False := by sorry\ndef g (y!' : Char -> Nat) : Nat := y!' '\"'\n",
                [("LEAN4_SORRY", 2)],
            ),
            (
                "xprime_qmark_char_desync",
                "def f (x?' : Char -> Nat) : Nat := x?' '\"'\nset_option debug.skipKernelTC true\ntheorem fake : False := by sorry\ndef g (y?' : Char -> Nat) : Nat := y?' '\"'\n",
                [("LEAN4_SORRY", 3), ("LEAN4_SKIP_KERNEL_TC", 2)],
            ),
        ):
            res_g = audit_lean4_source(bad_src)
            _req(not res_g["clean"], f"{label} bypassed audit_lean4_source: {res_g}")
            _req(
                [(f["code"], f["line"]) for f in res_g["findings"]] == exp_findings,
                f"wrong findings for {label}: got {res_g['findings']}, want {exp_findings}",
            )
        _req(
            _strip_lean4_comments_and_literals("def «unclosed\nline2").count("\n") == 1,
            "unterminated guillemet must preserve newline count",
        )
        _req(
            _strip_lean4_comments_and_literals("def «a\nb» := 1").count("\n") == 1,
            "multiline guillemet must preserve newline count",
        )
        for guil_redos, exp_clean in (("«" * 5000 + "\n", False), ("«»" * 5000 + "\n", True)):
            t0 = time.monotonic()
            res_gr = audit_lean4_source(guil_redos)
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            _req(res_gr["clean"] is exp_clean, f"unexpected guillemet ReDoS result: {res_gr['findings']}")
            _req(elapsed_ms < 100.0, f"guillemet ReDoS regression: {elapsed_ms:.1f} ms")

        # 5. R9 closures: !r"..." / !s!"..." entry, spaced/commented s!/f!/m! "...", debug.*AsSorry, initialize, #print axioms example
        for label, bad_src, exp_findings in (
            ("bang_raw_sorry", 'def a : Bool := !r"\\".isEmpty\ntheorem fake : False := by sorry\n-- "\n', [("LEAN4_SORRY", 2)]),
            ("bang_raw_col0_sorry", '!r"\\"\ntheorem fake : False := by sorry\n-- "\n', [("LEAN4_SORRY", 2)]),
            ("double_bang_raw_sorry", 'def a : Bool := !!r"\\".isEmpty\ntheorem fake : False := by sorry\n-- "\n', [("LEAN4_SORRY", 2)]),
            ("bang_raw_hash_sorry", 'def a : Bool := !r#"\\"#.isEmpty\ntheorem fake : False := by sorry\n-- "\n', [("LEAN4_SORRY", 2)]),
            ("bang_s_interp_sorry", 'def a : Bool := !s!"{let _ := "x"; (by sorry : String)}".isEmpty\n', [("LEAN4_SORRY", 1)]),
            ("bang_f_interp_sorry", 'def a : Bool := !f!"{let _ := "x"; (by sorry : String)}".pretty.isEmpty\n', [("LEAN4_SORRY", 1)]),
            ("bang_spaced_s_interp", 'def a : Bool := !s! "{let _ := "x"; (by sorry : String)}".isEmpty\n', [("LEAN4_SORRY", 1)]),
            ("col0_ident_r_plain", 'xr"\\" := 1\n', [("LEAN4_UNTERMINATED_STRING", 1)]),
            ("double_bang_ident_r_plain", 'def foo!!r"\\" := 1\n', [("LEAN4_UNTERMINATED_STRING", 1)]),
            ("underscore_bang_ident_r_plain", 'def foo_!r"\\" := 1\n', [("LEAN4_UNTERMINATED_STRING", 1)]),
            ("s_bang_space_interp", 'def a : String := s! "{(by sorry : String)}"\n', [("LEAN4_SORRY", 1)]),
            ("s_bang_nl_interp", 'def a : String := s!\n"{(by sorry : String)}"\n', [("LEAN4_SORRY", 2)]),
            ("s_bang_block_comment_interp", 'def a : String := s! /- c -/ "{(by sorry : String)}"\n', [("LEAN4_SORRY", 1)]),
            ("s_bang_line_comment_interp", 'def a : String := s! -- c\n"{(by sorry : String)}"\n', [("LEAN4_SORRY", 2)]),
            ("f_bang_space_interp", 'def a : Std.Format := f! "{(by sorry : String)}"\n', [("LEAN4_SORRY", 1)]),
            ("m_bang_space_interp", 'def a := m! "{sorry}"\n', [("LEAN4_SORRY", 1)]),
            (
                "s_bang_space_skipKernelTC",
                'def a : String := s! "{let _ := (by set_option debug.skipKernelTC true in trivial : True); "ok"}"\n',
                [("LEAN4_SKIP_KERNEL_TC", 1)],
            ),
            (
                "s_bang_nested_space_interp",
                'def a : String := s! "{ s! "}" ++ (by sorry : String) }"\n',
                [("LEAN4_SORRY", 1)],
            ),
            ("foo_underscore_s_bang_plain", 'def a := foo_s!"{"\ntheorem t : False := sorry\ndef b := "}"\n', [("LEAN4_UNKNOWN_BANG_STRING", 1), ("LEAN4_SORRY", 2)]),
            ("foo_prime_s_bang_plain", "def a := foo's!\"{\"\ntheorem t : False := sorry\ndef b := \"}\"\n", [("LEAN4_UNKNOWN_BANG_STRING", 1), ("LEAN4_SORRY", 2)]),
            ("debug_byAsSorry", "set_option debug.byAsSorry true\ntheorem fake : False := by trivial\n", [("LEAN4_SKIP_KERNEL_TC", 1)]),
            ("debug_proofAsSorry", "set_option debug.proofAsSorry true\ntheorem fake : False := by trivial\n", [("LEAN4_SKIP_KERNEL_TC", 1)]),
            (
                "debug_terminalTacticsAsSorry",
                "set_option debug.terminalTacticsAsSorry true\ntheorem fake : False := by omega\n",
                [("LEAN4_SKIP_KERNEL_TC", 1)],
            ),
            (
                "guil_debug_byAsSorry",
                "set_option «debug».«byAsSorry» true\ntheorem fake : False := by trivial\n",
                [("LEAN4_SKIP_KERNEL_TC", 1)],
            ),
            (
                "guil_debug_proofAsSorry",
                "set_option «debug».«proofAsSorry» true\ntheorem fake : False := by trivial\n",
                [("LEAN4_SKIP_KERNEL_TC", 1)],
            ),
            ("multiline_debug_byAsSorry", "set_option debug\n  . byAsSorry true\n", [("LEAN4_SKIP_KERNEL_TC", 1)]),
            ("initialize_io_spoof", 'initialize IO.println "\'Fake.thm\' does not depend on any axioms"\n', [("LEAN4_EVAL_SPOOF", 1)]),
            ("builtin_initialize_io_spoof", 'builtin_initialize IO.println "\'Fake.thm\' does not depend on any axioms"\n', [("LEAN4_EVAL_SPOOF", 1)]),
            ("named_initialize_io", 'initialize myInit : Nat ← do IO.println "hi"; pure 0\n', [("LEAN4_EVAL_SPOOF", 1)]),
            ("print_axioms_example", "def axioms := 1\n#print axioms example : True := trivial\n", [("LEAN4_EVAL_SPOOF", 2)]),
        ):
            res_r9 = audit_lean4_source(bad_src)
            _req(not res_r9["clean"], f"{label} bypassed audit_lean4_source: {res_r9}")
            _req(
                [(f["code"], f["line"]) for f in res_r9["findings"]] == exp_findings,
                f"wrong R9 findings for {label}: got {res_r9['findings']}, want {exp_findings}",
            )

        # Clean R9 non-FP controls (pending_interp clearing across tokens, dotted .initialize, raw/escaped strings, example_thm)
        for ok_r9 in (
            'def foo (x : String) : String := x\ndef y := foo.initialize\n',
            'def y := Foo.builtin_initialize\n',
            'def r := r##"hello "# sorry"##\n',
            'def e := s!"\\{sorry}"\n',
            'def e2 := s! "\\{sorry}"\n',
            'def s!a (x : String) : String := x\ndef y := s!a "{sorry}"\n',
            'def y := s! r"ok" "{sorry}"\n',
            'def y := s! «tok» "{sorry}"\n',
            "def y := s! 'a' \"{sorry}\"\n",
            'def y := s! "{ let _ := s! { a := 1 }; def b := "{sorry}" }"\n',
            'def y := s! "{ s! }" ++ "{sorry}"\n',
            'theorem example_thm : 1 + 1 = 2 := rfl\n#print axioms example_thm\n',
        ):
            res_ok9 = audit_lean4_source(ok_r9)
            _req(res_ok9["clean"], f"false positive on clean R9 control {ok_r9!r}: {res_ok9['findings']}")

        # Anti-ReDoS linear-time guard on repeated `s! ` / `debug.` / `initialize` patterns
        for r9_redos in ("s! " * 5000 + "\n", "s! /- c -/ " * 2500 + "\n", "debug " * 5000 + "\n"):
            t0 = time.monotonic()
            res_rr9 = audit_lean4_source(r9_redos)
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            _req(res_rr9["clean"], f"unexpected finding on R9 ReDoS probe: {res_rr9['findings']}")
            _req(elapsed_ms < 200.0, f"R9 ReDoS regression: {elapsed_ms:.1f} ms")

        # 6. R10 closures: unrecognized `<ident>!"`, built-in `dbg_trace`/`println!`/`Macro.trace[...]`/`trace[...]`/`throwError`,
        # custom `macro`/`syntax`/`elab`/`interpolatedStr`, and quote-bearing `notation`/`prefix`/`infix*`/`postfix` tokens
        for label, bad_src, exp_findings in (
            ("ahrazzle_foo_bang_multiline", 'def f := foo!"abc\ntheorem t : True := by sorry\n"\n', [("LEAN4_UNKNOWN_BANG_STRING", 1)]),
            ("unknown_x_bang_glued", 'def a := x!"bad {sorry} state"\n', [("LEAN4_UNKNOWN_BANG_STRING", 1)]),
            ("col0_short_ident_bang", 'a!"x"\n', [("LEAN4_UNKNOWN_BANG_STRING", 1)]),
            ("my_panic_spoof", 'def f := my_panic!"abc"\n', [("LEAN4_UNKNOWN_BANG_STRING", 1)]),
            ("foo_dot_panic_spoof", 'def f := Foo.panic!"abc"\n', [("LEAN4_UNKNOWN_BANG_STRING", 1)]),
            ("unicode_ident_bang_glued", 'def f := α!"abc\ntheorem t : True := by sorry\n"\n', [("LEAN4_UNKNOWN_BANG_STRING", 1)]),
            ("double_bang_ident_glued", 'def f := foo!!"abc\ntheorem t : True := by sorry\n"\n', [("LEAN4_UNKNOWN_BANG_STRING", 1)]),
            ("double_bang_s_glued", 'def f := s!!"{sorry}"\n', [("LEAN4_UNKNOWN_BANG_STRING", 1)]),
            ("dbg_trace_interp_sorry", 'def f : Nat := dbg_trace "hi {(by sorry : String)}"; 0\n', [("LEAN4_SORRY", 1)]),
            ("dbg_trace_nospace_sorry", 'def f : Nat := dbg_trace"hi {(by sorry : String)}"; 0\n', [("LEAN4_SORRY", 1)]),
            ("dbg_trace_multiline_sorry", 'def f : Nat := dbg_trace\n  "hi {(by sorry : String)}"; 0\n', [("LEAN4_SORRY", 2)]),
            ("dbg_trace_comment_sorry", 'def f : Nat := dbg_trace /- c -/ "hi {(by sorry : String)}"; 0\n', [("LEAN4_SORRY", 1)]),
            ("throwError_interp_sorry", 'def f := throwError "hi {(by sorry : String)}"\n', [("LEAN4_SORRY", 1)]),
            ("println_interp_sorry", 'def f : IO Unit := println! "hi {(by sorry : String)}"\n', [("LEAN4_SORRY", 1)]),
            ("println_nospace_sorry", 'def f : IO Unit := println!"hi {(by sorry : String)}"\n', [("LEAN4_SORRY", 1)]),
            ("println_nl_sorry", 'def f : IO Unit := println!\n  "hi {(by sorry : String)}"\n', [("LEAN4_SORRY", 2)]),
            ("v_bang_lake_interp_sorry", 'def f := v!"{(by sorry : String)}"\n', [("LEAN4_SORRY", 1)]),
            ("reportIssue_interp_sorry", 'def f := reportIssue! "hi {(by sorry : String)}"\n', [("LEAN4_SORRY", 1)]),
            ("reportDbgIssue_interp_sorry", 'def f := reportDbgIssue! "hi {(by sorry : String)}"\n', [("LEAN4_SORRY", 1)]),
            ("reportEMatchIssue_interp_sorry", 'def f := reportEMatchIssue! "hi {(by sorry : String)}"\n', [("LEAN4_SORRY", 1)]),
            ("macro_trace_interp_sorry", 'def f : Lean.MacroM Unit := Macro.trace[foo] "hi {(by sorry : String)}"\n', [("LEAN4_SORRY", 1)]),
            ("macro_trace_nospace_sorry", 'def f : Lean.MacroM Unit := Macro.trace[foo]"hi {(by sorry : String)}"\n', [("LEAN4_SORRY", 1)]),
            ("macro_trace_nl_sorry", 'def f : Lean.MacroM Unit := Macro.trace[foo]\n  "hi {(by sorry : String)}"\n', [("LEAN4_SORRY", 2)]),
            ("trace_brack_sorry", 'def f := trace[Elab.step] "hi {(by sorry : String)}"\n', [("LEAN4_SORRY", 1)]),
            ("trace_goal_brack_sorry", 'def f := trace_goal[grind] "hi {(by sorry : String)}"\n', [("LEAN4_SORRY", 1)]),
            ("trace_nested_brack_sorry", 'def f := trace[a[0]] "hi {(by sorry : String)}"\n', [("LEAN4_SORRY", 1)]),
            ("trace_inner_macro_trace_sorry", 'def f := trace[Macro.trace] "hi {(by sorry : String)}"\n', [("LEAN4_SORRY", 1)]),
            ("trace_inner_trace_sorry", 'def f := trace[trace] "hi {(by sorry : String)}"\n', [("LEAN4_SORRY", 1)]),
            ("custom_syntax_interp", 'syntax "foo!" interpolatedStr(term) : term\n', [("LEAN4_META_SYNTAX_ESCAPE", 1)]),
            ("custom_macro_mkIdent_sorryAx", 'macro "ok" : term => pure (Lean.mkIdent (Lean.Name.mkSimple ("sor" ++ "ryAx")))\ntheorem fake : False := ok False false\n', [("LEAN4_META_SYNTAX_ESCAPE", 1)]),
            ("custom_macro_rules", 'macro_rules | `(ok) => `(0)\n', [("LEAN4_META_SYNTAX_ESCAPE", 1)]),
            ("custom_elab", 'elab "ok" : term => pure ()\n', [("LEAN4_META_SYNTAX_ESCAPE", 1)]),
            ("custom_elab_rules", 'elab_rules : term | `(ok) => pure ()\n', [("LEAN4_META_SYNTAX_ESCAPE", 1)]),
            ("qualified_interpolatedStr", 'def f := Lean.Parser.Term.interpolatedStr\n', [("LEAN4_META_SYNTAX_ESCAPE", 1)]),
            ("notation_quote_token_sorry", 'notation "foo!\\"" => 0\ndef f := foo!"\ntheorem fake : False := by sorry\ndef g := foo!"\n', [("LEAN4_SYNTAX_QUOTE_TOKEN", 1), ("LEAN4_UNKNOWN_BANG_STRING", 2)]),
            ("notation_bar_quote_token", 'notation "bar\\"" => 1\ndef f := bar"\ntheorem fake : False := by sorry\ndef g := bar"\n', [("LEAN4_SYNTAX_QUOTE_TOKEN", 1)]),
            ("notation_double_escaped_quote_once", 'notation "a\\"b\\"" => 0\n', [("LEAN4_SYNTAX_QUOTE_TOKEN", 1)]),
            ("prefix_quote_token", 'prefix:max "foo!\\"" => id\n', [("LEAN4_SYNTAX_QUOTE_TOKEN", 1)]),
            ("infix_quote_token", 'infix:65 " +\\" " => Nat.add\n', [("LEAN4_SYNTAX_QUOTE_TOKEN", 1)]),
            ("infixl_quote_token", 'infixl:65 " +\\" " => Nat.add\n', [("LEAN4_SYNTAX_QUOTE_TOKEN", 1)]),
            ("infixr_quote_token", 'infixr:65 " +\\" " => Nat.add\n', [("LEAN4_SYNTAX_QUOTE_TOKEN", 1)]),
            ("postfix_quote_token", 'postfix:max "foo!\\"" => id\n', [("LEAN4_SYNTAX_QUOTE_TOKEN", 1)]),
        ):
            res_r10 = audit_lean4_source(bad_src)
            _req(not res_r10["clean"], f"{label} bypassed audit_lean4_source: {res_r10}")
            _req(
                [(f["code"], f["line"]) for f in res_r10["findings"]] == exp_findings,
                f"wrong R10 findings for {label}: got {res_r10['findings']}, want {exp_findings}",
            )

        # Clean R10 non-FP controls (exact boundaries for panic!, dbg_trace, println!, Macro.trace, trace, notation =>, meta identifiers)
        for ok_r10 in (
            'def f : Nat := dbg_trace ("hi {sorry}"); 0\n',
            'def f : Nat := dbg_trace "hi sorry"; 0\n',
            'def f := dbg_trace.foo "{sorry}"\n',
            "def f := dbg_trace' \"{sorry}\"\n",
            'def my_dbg_trace (s : String) := s\ndef f := my_dbg_trace "hi {sorry}"\n',
            'def f : IO Unit := println! ("hi {sorry}")\n',
            'def f : IO Unit := println! "hi sorry"\n',
            'def f := s!! "{sorry}"\n',
            'def f := s!',
            'def f := Macro.trace',
            'def f := Macro.trace[foo] "hi sorry"\n',
            'def f := Macro.trace1[0] "{sorry}"\n',
            'def f := Macro.trace_[0] "{sorry}"\n',
            'def trace (s : String) := s\ndef f := trace "hi {sorry}"\n',
            'def f := trace "{sorry}" [0] "{sorry}"\n',
            'def f := trace[a[0] "{sorry}"]\n',
            'def f (x : S) := x.trace[0] "hi {sorry}"\n',
            'def f := s! => "{sorry}"\n',
            'def f := trace => [0] "{sorry}"\n',
            'def f := trace «tok» [0] "{sorry}"\n',
            "def f := trace 'a' [0] \"{sorry}\"\n",
            'def f := trace r"ok" [0] "{sorry}"\n',
            'def f := s!"{ trace { a := 1 }; [1] "{sorry}" }"\n',
            'def f := !!"abc\ntheorem t : True := by sorry\n"\n',
            'notation "a\\n" => 0\n',
            'notation "my_q" => "\\""\ndef s := my_q\n',
            'infixl:65 " ⊕ " => Nat.add\ndef s := "a \\" b"\n',
            'def f := prefix.x "\\""\n',
            'def f := notation\' "\\""\n',
            'def x := 1 -- eof_comment_no_nl',
            '@[macro_inline] def f : Nat := 1\n',
            'def x := Foo.macro + Foo.syntax + my_macro + syntax_tree + elaborate\n',
            '-- macro syntax elab\ndef s := "macro syntax elab interpolatedStr"\n',
        ):
            res_ok10 = audit_lean4_source(ok_r10)
            _req(res_ok10["clean"], f"false positive on clean R10 control {ok_r10!r}: {res_ok10['findings']}")

        # Anti-ReDoS linear-time guard for R10 (including thousands of findings via monotonic line cursor)
        for r10_redos, exp_clean in (
            ('foo!"a" ' * 5000 + "\n", False),
            ('notation ' + '"\\"" ' * 3000 + '=> 0\n', False),
            ('Macro.trace ' * 5000 + "\n", True),
            ('dbg_trace ' * 5000 + "\n", True),
        ):
            t0 = time.monotonic()
            res_rr10 = audit_lean4_source(r10_redos)
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            _req(res_rr10["clean"] is exp_clean, f"unexpected R10 ReDoS result: clean={res_rr10['clean']}")
            _req(elapsed_ms < 200.0, f"R10 ReDoS regression: {elapsed_ms:.1f} ms")

        # 7. R11 closures: Init.Util impure C-FFI debug primitives (`dbgTrace*`/`dbgSleep`/`dbgStackTrace`),
        # `@[export]`/`@[init]`/`@[builtin_init]` (+ `attribute [...]` equivalents), and R11 regressions
        for label, bad_src, exp_findings in (
            ("r11_dbgTrace", "def f : Nat := dbgTrace (String.ofList []) (fun _ => 0)\n", [("LEAN4_DBG_FFI_ESCAPE", 1)]),
            ("r11_dbgTraceVal", "def f : Nat := dbgTraceVal 0\n", [("LEAN4_DBG_FFI_ESCAPE", 1)]),
            ("r11_dbgTraceIfShared", "def f : Nat := dbgTraceIfShared (String.ofList []) 0\n", [("LEAN4_DBG_FFI_ESCAPE", 1)]),
            ("r11_root_dbgTrace", "def f : Nat := _root_.dbgTrace (String.ofList []) (fun _ => 0)\n", [("LEAN4_DBG_FFI_ESCAPE", 1)]),
            ("r11_root_dbgTraceVal", "def f : Nat := _root_.dbgTraceVal 0\n", [("LEAN4_DBG_FFI_ESCAPE", 1)]),
            ("r11_root_dbgTraceIfShared", "def f : Nat := _root_.dbgTraceIfShared (String.ofList []) 0\n", [("LEAN4_DBG_FFI_ESCAPE", 1)]),
            ("r11_guil_dbgTrace", "def f : Nat := «dbgTrace» (String.ofList []) (fun _ => 0)\n", [("LEAN4_DBG_FFI_ESCAPE", 1)]),
            ("r11_dbgSleep", "def f : Nat := dbgSleep 0 (fun _ => 0)\n", [("LEAN4_DBG_FFI_ESCAPE", 1)]),
            ("r11_dbgStackTrace", "def f : Nat := dbgStackTrace (fun _ => 0)\n", [("LEAN4_DBG_FFI_ESCAPE", 1)]),
            ("r11_at_export", "@[export my_c_sym] def f (n : Nat) : Nat := n\n", [("LEAN4_ATTR_TRUST_ESCAPE", 1)]),
            ("r11_attr_export", "def f (n : Nat) : Nat := n\nattribute [export my_c_sym] f\n", [("LEAN4_ATTR_TRUST_ESCAPE", 2)]),
            ("r11_guil_attr_export", "def f (n : Nat) : Nat := n\nattribute [«export» my_c_sym] f\n", [("LEAN4_ATTR_TRUST_ESCAPE", 2)]),
            ("r11_at_init", '@[init] def myInit : IO Unit := IO.println "SPOOF"\n', [("LEAN4_ATTR_TRUST_ESCAPE", 1)]),
            ("r11_at_init_of", "def myInit : IO Nat := pure 0\n@[init myInit] opaque x : Nat\n", [("LEAN4_ATTR_TRUST_ESCAPE", 2)]),
            ("r11_attr_init", 'def myInit : IO Unit := IO.println "SPOOF"\nattribute [init] myInit\n', [("LEAN4_ATTR_TRUST_ESCAPE", 2)]),
            ("r11_at_builtin_init", '@[builtin_init] def myInit : IO Unit := IO.println "SPOOF"\n', [("LEAN4_ATTR_TRUST_ESCAPE", 1)]),
            ("r11_attr_builtin_init", 'def myInit : IO Unit := IO.println "SPOOF"\nattribute [builtin_init] myInit\n', [("LEAN4_ATTR_TRUST_ESCAPE", 2)]),
            ("r11_warn_sorry_false", "set_option warn.sorry false\n", [("LEAN4_SORRY", 1)]),
            ("r11_warn_sorry_guil", "set_option «warn».«sorry» false\n", [("LEAN4_SORRY", 1)]),
            ("r11_warn_sorry_root_sorryAx", "set_option warn.sorry false in theorem t : False := _root_.sorryAx False false\n", [("LEAN4_SORRY", 1), ("LEAN4_SORRY_AX", 1)]),
            ("r11_decide_plus_revert_config_native", "def native : Bool := true\ntheorem t : 1 + 1 = 2 := by decide +revert (config := { native })\n", [("LEAN4_DECIDE_NATIVE", 2)]),
            ("r11_decide_revert_false_config_native", "def native : Bool := true\ntheorem t : 1 + 1 = 2 := by decide (revert := false) (config := { native })\n", [("LEAN4_DECIDE_NATIVE", 2)]),
            ("r11_decide_struct_update_native", "def native : Bool := true\ntheorem t : 1 + 1 = 2 := by decide +revert (config := { ({} : _) with native })\n", [("LEAN4_DECIDE_NATIVE", 2)]),
        ):
            res_r11 = audit_lean4_source(bad_src)
            _req(not res_r11["clean"], f"{label} bypassed audit_lean4_source: {res_r11}")
            _req(
                [(f["code"], f["line"]) for f in res_r11["findings"]] == exp_findings,
                f"wrong R11 findings for {label}: got {res_r11['findings']}, want {exp_findings}",
            )

        # Clean R11 non-FP controls (namespace export, init target outside [...], identifier substrings, comments/strings)
        for ok_r11 in (
            "export Nat (succ)\ntheorem t : succ 0 = 1 := rfl\n",
            "def init : Nat := 0\nattribute [simp] init\n",
            "@[simp] def init : Nat := 0\n",
            "def my_dbgTrace : Nat := 0\ndef dbgTrace2 : Nat := 1\n",
            '-- dbgTrace dbgTraceVal dbgTraceIfShared @[export foo] @[init]\ndef s := "dbgTrace @[export foo] @[init]"\n',
            "theorem t : 1 + 1 = 2 := by decide (native := false)\n",
            "theorem t : 1 + 1 = 2 := by decide (native := Bool.false)\n",
        ):
            res_ok11 = audit_lean4_source(ok_r11)
            _req(res_ok11["clean"], f"false positive on clean R11 control {ok_r11!r}: {res_ok11['findings']}")

        # Anti-ReDoS linear-time guard for R11
        for r11_redos, exp_clean in (
            ("dbgTrace " * 5000 + "\n", False),
            ("@[export x] " * 3000 + "\n", False),
            ("export Nat (succ)\n" * 3000, True),
        ):
            t0 = time.monotonic()
            res_rr11 = audit_lean4_source(r11_redos)
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            _req(res_rr11["clean"] is exp_clean, f"unexpected R11 ReDoS result: clean={res_rr11['clean']}")
            _req(elapsed_ms < 200.0, f"R11 ReDoS regression: {elapsed_ms:.1f} ms")

    def test_02d_live_lean4_compiler_witnesses(self) -> None:
        """When a live `lean` binary is on PATH, verify each new escape & clean control actually compiles (rc == 0)."""
        lean_exe = shutil.which("lean")
        if lean_exe is None:
            return
        probes = (
                    (
                        "xprime_skipKernelTC",
                        "def f (x' : Char -> Nat) : Nat := x' '\"'\nset_option debug.skipKernelTC true\ntheorem evil : 1 = 1 := rfl\ndef g : String := \"\\\"\"\n",
                        False,
                        False,
                    ),
                    (
                        "xprime_bang_sorry",
                        "def f (x!' : Char -> Nat) : Nat := x!' '\"'\ntheorem fake : False := by sorry\ndef g (y!' : Char -> Nat) : Nat := y!' '\"'\n",
                        False,
                        False,
                    ),
                    (
                        "xprime_qmark_skipKernelTC",
                        "def f (x?' : Char -> Nat) : Nat := x?' '\"'\nset_option debug.skipKernelTC true\ntheorem fake : False := by sorry\ndef g (y?' : Char -> Nat) : Nat := y?' '\"'\n",
                        False,
                        False,
                    ),
                    (
                        "hex_char_desync",
                        "def f (a b : Char) : Nat := 0\ndef x := f '\\x27' '\"'\ntheorem evil : False := by sorry\ndef g : String := \"\\\"\"\n",
                        False,
                        False,
                    ),
                    (
                        "unicode_char_desync",
                        "def f (a b : Char) : Nat := 0\ndef x := f '\\u0027' '\"'\ntheorem evil : False := by sorry\ndef g : String := \"\\\"\"\n",
                        False,
                        False,
                    ),
                    ("guil_line_comment", "theorem «--» : False := by sorry\n", False, False),
                    ("guil_dquote", 'def «"» : Nat := 1\ntheorem fake : False := by sorry\ndef «" » : Nat := 2\n', False, False),
                    ("guil_block_comment", "def «/-» : Nat := 1\nset_option debug.skipKernelTC true\ntheorem fake : False := by sorry\ndef «-/» : Nat := 2\n", False, False),
                    ("guil_interp", 'def «s!"» : Nat := 1\ntheorem fake : False := by sorry\ndef «"» : Nat := 2\n', False, False),
                    ("guil_raw", 'def «r#"» : Nat := 1\ntheorem fake : False := by sorry\ndef «"#» : Nat := 2\n', False, False),
                    ("guil_eval_clean", "def «#eval» : Nat := 1\n", True, False),
                    ("post_attr_extern", 'opaque foo : Nat\nattribute [extern "c_foo"] foo\n', False, False),
                    ("post_attr_impl", "def f_impl : Nat := 1\ndef f_spec : Nat := 0\nattribute [implemented_by f_impl] f_spec\n", False, False),
                    ("post_attr_csimp", "def a : Nat := 0\ndef b : Nat := 0\ntheorem ab : a = b := rfl\nattribute [csimp] ab\n", True, False),
                    ("eval_spoof", "#eval IO.println \"'Fake.thm' does not depend on any axioms\"\n", False, False),
                    ("eval_bang_spoof", "#eval! IO.println \"'Fake.thm' does not depend on any axioms\"\n", False, False),
                    ("glued_eval", "theorem ok : True := trivial#eval IO.println \"'Fake.thm' does not depend on any axioms\"\n", False, False),
                    ("glued_exit", "theorem ok : True := trivial#exit\n", False, False),
                    ("reduce_cmd", "#reduce 1 + 1\n", False, False),
                    ("print_non_axioms", "#print Nat\n", False, False),
                    ("print_axioms_bang", "def axioms! := 1\n#print axioms!\n", False, False),
                    ("print_axioms_sub1", "def axioms₁ := 1\n#print axioms₁\n", False, False),
                    ("print_axioms_dot", "def axioms.foo := 1\n#print axioms.foo\n", False, False),
                    ("print_axioms_eof", "def axioms := 1\n#print axioms\n", False, False),
                    ("print_axioms_sameline_def", "def axioms := 1\n#print axioms def y := 2\n", False, False),
                    ("print_guil_axioms", "def «axioms» := 1\n#print «axioms»\n", False, False),
                    ("run_cmd_lean", 'import Lean\nrun_cmd Lean.logInfo "\'Fake.thm\' does not depend on any axioms"\n', False, True),
                    ("early_exit", "theorem ok : 1 + 1 = 2 := rfl\n#exit\n", False, False),
                    ("bang_raw_sorry", 'def a : Bool := !r"\\".isEmpty\ntheorem fake : False := by sorry\n-- "\n', False, False),
                    ("bang_raw_hash_sorry", 'def a : Bool := !r#"\\"#.isEmpty\ntheorem fake : False := by sorry\n-- "\n', False, False),
                    ("bang_s_interp_sorry", 'def a : Bool := !s!"{let _ := "x"; (by sorry : String)}".isEmpty\n', False, False),
                    ("bang_f_interp_sorry", 'def a : Bool := !f!"{let _ := "x"; (by sorry : String)}".pretty.isEmpty\n', False, False),
                    ("s_bang_space_interp", 'def a : String := s! "{(by sorry : String)}"\n', False, False),
                    ("s_bang_nl_interp", 'def a : String := s!\n"{(by sorry : String)}"\n', False, False),
                    ("s_bang_block_comment_interp", 'def a : String := s! /- c -/ "{(by sorry : String)}"\n', False, False),
                    ("s_bang_line_comment_interp", 'def a : String := s! -- c\n"{(by sorry : String)}"\n', False, False),
                    ("f_bang_space_interp", 'def a : Std.Format := f! "{(by sorry : String)}"\n', False, False),
                    ("s_bang_nested_space_interp", 'def a : String := s! "{ s! "}" ++ (by sorry : String) }"\n', False, False),
                    ("s_bang_space_skipKernelTC", 'def a : String := s! "{let _ := (by set_option debug.skipKernelTC true in trivial : True); "ok"}"\n', False, False),
                    ("debug_byAsSorry", "set_option debug.byAsSorry true\ntheorem fake : False := by trivial\n", False, False),
                    ("debug_proofAsSorry", "set_option debug.proofAsSorry true\ntheorem fake : False := by trivial\n", False, False),
                    ("debug_terminalTacticsAsSorry", "set_option debug.terminalTacticsAsSorry true\ntheorem fake : False := by omega\n", False, False),
                    ("guil_debug_byAsSorry", "set_option «debug».«byAsSorry» true\ntheorem fake : False := by trivial\n", False, False),
                    ("guil_debug_proofAsSorry", "set_option «debug».«proofAsSorry» true\ntheorem fake : False := by trivial\n", False, False),
                    ("initialize_io_spoof", 'initialize IO.println "\'Fake.thm\' does not depend on any axioms"\n', False, False),
                    ("builtin_initialize_io_spoof", 'builtin_initialize IO.println "\'Fake.thm\' does not depend on any axioms"\n', False, False),
                    ("named_initialize_io", 'initialize myInit : Nat ← do IO.println "hi"; pure 0\n', False, False),
                    ("print_axioms_example", "def axioms := 1\n#print axioms example : True := trivial\n", False, False),
                    ("clean_print_axioms", "theorem ok : 1 + 1 = 2 := rfl\n#print axioms ok\n#print\n  axioms ok\n", True, False),
                    ("clean_r9_controls", 'def r := r##"hello "# sorry"##\ndef e := s!"\\{sorry}"\ndef e2 := s! "\\{sorry}"\ntheorem example_thm : 1 + 1 = 2 := rfl\n#print axioms example_thm\n', True, False),
                    # R10 live Lean 4.36.0 compiler witnesses
                    ("r10_dbg_trace_interp_sorry", 'def f : Nat := dbg_trace "hi {(by sorry : String)}"; 0\n', False, False),
                    ("r10_dbg_trace_nospace_sorry", 'def f : Nat := dbg_trace"hi {(by sorry : String)}"; 0\n', False, False),
                    ("r10_dbg_trace_comment_sorry", 'def f : Nat := dbg_trace /- c -/ "hi {(by sorry : String)}"; 0\n', False, False),
                    ("r10_println_interp_sorry", 'def f : IO Unit := println! "hi {(by sorry : String)}"\n', False, False),
                    ("r10_println_nospace_sorry", 'def f : IO Unit := println!"hi {(by sorry : String)}"\n', False, False),
                    ("r10_macro_trace_interp_sorry", 'def f : Lean.MacroM Unit := Macro.trace[foo] "hi {(by sorry : String)}"\n', False, False),
                    ("r10_macro_trace_nospace_sorry", 'def f : Lean.MacroM Unit := Macro.trace[foo]"hi {(by sorry : String)}"\n', False, False),
                    ("r10_custom_syntax_interp_sorry", 'syntax "foo!" interpolatedStr(term) : term\nmacro_rules | `(foo!$s) => `(s!$s)\ndef f := foo!"{(by sorry : String)}"\n', False, False),
                    ("r10_custom_macro_interp_sorry", 'macro "my!" s:interpolatedStr(term) : term => `(s!$s)\ndef f := my!"{(by sorry : String)}"\n', False, False),
                    ("r10_custom_syntax_no_bang_interp", 'syntax "foo" interpolatedStr(term) : term\nmacro_rules | `(foo$s) => `(s!$s)\ndef f := foo"{(by sorry : String)}"\n', False, False),
                    ("r10_macro_mkIdent_sorryAx", 'macro "ok" : term => pure (Lean.mkIdent (Lean.Name.mkSimple ("sor" ++ "ryAx")))\ntheorem fake : False := ok False false\n', False, False),
                    ("r10_macro_decide_native_mkIdent", 'macro "ok" : tactic => `(tactic| decide +$(Lean.mkIdent (Lean.Name.mkSimple ("nat" ++ "ive"))))\ntheorem t : 1 + 1 = 2 := by ok\n', False, False),
                    ("r10_macro_attr_extern", 'macro "ok" : attr => `(attr| extern "c_foo")\n@[ok] opaque f : Nat\n', False, False),
                    ("r10_notation_foo_bang_quote", 'notation "foo!\\"" => 0\ndef f := foo!"\ntheorem fake : False := by sorry\ndef g := foo!"\n', False, False),
                    ("r10_notation_bar_quote", 'notation "bar\\"" => 1\ndef f := bar"\ntheorem fake : False := by sorry\ndef g := bar"\n', False, False),
                    ("r10_prefix_quote_token", 'prefix:max "foo!\\"" => id\ndef f := foo!" 0\ntheorem fake : False := by sorry\ndef g := foo!" 0\n', False, False),
                    ("r10_infixl_quote_token", 'infixl:65 " +\\" " => Nat.add\ndef f := 1 +" 2\ntheorem fake : False := by sorry\ndef g := 1 +" 2\n', False, False),
                    ("r10_postfix_quote_token", 'postfix:max "foo!\\"" => id\ndef f := 0foo!"\ntheorem fake : False := by sorry\ndef g := 0foo!"\n', False, False),
                    ("r10_clean_spaced_foo_bang_multiline", 'def foo! (s : String) : String := s\ndef f := foo! "abc\ntheorem t : True := by sorry\n"\n', True, False),
                    ("r10_clean_panic_multiline", 'def f : Nat := panic!"abc\ntheorem t : True := by sorry\n"\n', True, False),
                    ("r10_clean_dbg_trace_and_println_parens", 'def f1 : Nat := dbg_trace ("hi {sorry}"); 0\ndef f2 : IO Unit := println! ("hi {sorry}")\n', True, False),
                    ("r10_clean_notation_rhs_quote_and_macro_inline", 'notation "my_q" => "\\""\n@[macro_inline] def s : String := my_q\n', True, False),
                    # R11 live Lean 4.36.0 compiler witnesses
                    ("r11_dbgTrace", "def f : Nat := dbgTrace (String.ofList []) (fun _ => 0)\n", False, False),
                    ("r11_dbgTraceVal", "def f : Nat := dbgTraceVal 0\n", False, False),
                    ("r11_dbgTraceIfShared", "def f : Nat := dbgTraceIfShared (String.ofList []) 0\n", False, False),
                    ("r11_root_dbgTrace", "def f : Nat := _root_.dbgTrace (String.ofList []) (fun _ => 0)\n", False, False),
                    ("r11_dbgSleep", "def f : Nat := dbgSleep 0 (fun _ => 0)\n", False, False),
                    ("r11_dbgStackTrace", "def f : Nat := dbgStackTrace (fun _ => 0)\n", False, False),
                    ("r11_at_export", "@[export r11_c_sym_1] def f (n : Nat) : Nat := n\n", False, False),
                    ("r11_attr_export", "def f (n : Nat) : Nat := n\nattribute [export r11_c_sym_2] f\n", False, False),
                    ("r11_at_init", '@[init] def myInit : IO Unit := IO.println "SPOOF"\n', False, False),
                    ("r11_at_init_of", "def myInit : IO Nat := pure 0\n@[init myInit] opaque x : Nat\n", False, False),
                    ("r11_attr_init", 'def myInit : IO Unit := IO.println "SPOOF"\nattribute [init] myInit\n', False, False),
                    ("r11_at_builtin_init", '@[builtin_init] def myInit : IO Unit := IO.println "SPOOF"\n', False, False),
                    ("r11_attr_builtin_init", 'def myInit : IO Unit := IO.println "SPOOF"\nattribute [builtin_init] myInit\n', False, False),
                    ("r11_warn_sorry_root_sorryAx", "set_option warn.sorry false in theorem t : False := _root_.sorryAx False false\n", False, False),
                    ("r11_decide_plus_revert_config_native", "def native : Bool := true\ntheorem t : 1 + 1 = 2 := by decide +revert (config := { native })\n", False, False),
                    ("r11_decide_revert_false_config_native", "def native : Bool := true\ntheorem t : 1 + 1 = 2 := by decide (revert := false) (config := { native })\n", False, False),
                    ("r11_clean_namespace_export", "export Nat (succ)\ntheorem t : succ 0 = 1 := rfl\n", True, False),
                    ("r11_clean_attr_simp_init", "def init : Nat := 0\nattribute [simp] init\n", True, False),
                )
        for label, src, expect_clean, allow_non_init in probes:
            res = audit_lean4_source(src, allow_non_init_imports=allow_non_init)
            _req(res["clean"] is expect_clean, f"audit mismatch on live {label}: {res}")
        solo_tokens = ("#exit", "import ", "syntax ", "macro ", "notation ", "prefix:", "infix", "postfix:")
        batched: list[tuple[int, str, str]] = []
        solo: list[tuple[int, str, str]] = []
        for idx, (label, src, _, allow_non_init) in enumerate(probes):
            if allow_non_init or any(tok in src for tok in solo_tokens):
                solo.append((idx, label, src))
            else:
                batched.append((idx, label, src))
        with tempfile.TemporaryDirectory(prefix="aletheia_lean_live_") as td:
            if batched:
                bp = Path(td) / "BatchProbes.lean"
                bp.write_text(
                    "\n".join(f"namespace Probe_{idx}\n{src}\nend Probe_{idx}\n" for idx, _, src in batched),
                    encoding="utf-8",
                )
                proc_b = subprocess.run([lean_exe, str(bp)], capture_output=True, text=True, timeout=60, check=False)
                _req(
                    proc_b.returncode == 0,
                    f"live Lean failed on batched probes: rc={proc_b.returncode} out={proc_b.stdout!r} err={proc_b.stderr!r}",
                )
            for idx, label, src in solo:
                p = Path(td) / f"Probe{idx}.lean"
                p.write_text(src, encoding="utf-8")
                proc = subprocess.run([lean_exe, str(p)], capture_output=True, text=True, timeout=60, check=False)
                _req(proc.returncode == 0, f"live Lean failed on {label}: rc={proc.returncode} out={proc.stdout!r} err={proc.stderr!r}")

    def test_03_audit_check_target_root_symlink_fifo_and_unreadable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_root_hard_") as td:
            base = Path(td).resolve()
            real_dir = base / "real_dir"
            real_dir.mkdir()
            real_file = real_dir / "ok.txt"
            real_file.write_text("clean\n", encoding="utf-8")

            # Missing target -> TARGET_NOT_FOUND
            with self.assertRaises(AletheiaError) as cm_nf:
                run_audit_check(base / "does_not_exist")
            _req(cm_nf.exception.code == "TARGET_NOT_FOUND", f"wrong code: {cm_nf.exception.code}")

            # Non-ENOENT OSError on lstat (file used as directory parent -> ENOTDIR) -> TARGET_UNREADABLE
            with self.assertRaises(AletheiaError) as cm_ur:
                run_audit_check(real_file / "child")
            _req(cm_ur.exception.code == "TARGET_UNREADABLE", f"wrong code: {cm_ur.exception.code}")

            # Mode-000 unreadable root directory -> TARGET_UNREADABLE (never raw PermissionError)
            locked_root = base / "locked_root"
            locked_root.mkdir()
            (locked_root / "x.py").write_text("x = 1\n", encoding="utf-8")
            os.chmod(locked_root, 0o000)
            try:
                if not os.access(locked_root, os.R_OK):
                    with self.assertRaises(AletheiaError) as cm_lr:
                        run_audit_check(locked_root)
                    _req(cm_lr.exception.code == "TARGET_UNREADABLE", f"wrong code: {cm_lr.exception.code}")
            finally:
                os.chmod(locked_root, 0o700)

            # Symlink directory/file root refused by default, allowed with allow_symlinks=True
            sym_dir = base / "sym_dir"
            os.symlink(real_dir, sym_dir)
            with self.assertRaises(AletheiaError) as cm_sd:
                run_audit_check(sym_dir)
            _req(cm_sd.exception.code == "TARGET_IS_SYMLINK", f"wrong code: {cm_sd.exception.code}")
            rep_allow = run_audit_check(sym_dir, allow_symlinks=True)
            _req(rep_allow["passed"], f"allow_symlinks=True should follow clean symlink root: {rep_allow}")

            sym_file = base / "sym_file.txt"
            os.symlink(real_file, sym_file)
            with self.assertRaises(AletheiaError) as cm_sf:
                run_audit_check(sym_file)
            _req(cm_sf.exception.code == "TARGET_IS_SYMLINK", f"wrong code: {cm_sf.exception.code}")

            # Broken symlink root: TARGET_IS_SYMLINK by default, TARGET_NOT_FOUND with allow_symlinks=True
            broken = base / "broken_root"
            os.symlink(base / "missing_target", broken)
            with self.assertRaises(AletheiaError) as cm_b1:
                run_audit_check(broken)
            _req(cm_b1.exception.code == "TARGET_IS_SYMLINK", f"wrong code: {cm_b1.exception.code}")
            with self.assertRaises(AletheiaError) as cm_b2:
                run_audit_check(broken, allow_symlinks=True)
            _req(cm_b2.exception.code == "TARGET_NOT_FOUND", f"wrong code: {cm_b2.exception.code}")

            if HAS_MKFIFO:
                fifo = base / "pipe_root"
                os.mkfifo(fifo)
                with self.assertRaises(AletheiaError) as cm_f1:
                    run_audit_check(fifo)
                _req(cm_f1.exception.code == "TARGET_NOT_REGULAR", f"wrong code: {cm_f1.exception.code}")
                sym_fifo = base / "sym_fifo"
                os.symlink(fifo, sym_fifo)
                with self.assertRaises(AletheiaError) as cm_f2:
                    run_audit_check(sym_fifo, allow_symlinks=True)
                _req(cm_f2.exception.code == "TARGET_NOT_REGULAR", f"wrong code: {cm_f2.exception.code}")


class TestGatesV2CanonicalAndDepthHardening(unittest.TestCase):
    def test_04_strict_int_rejects_intenum_and_subclasses(self) -> None:
        _req(g2._is_strict_int(0) is True, "exact int 0 must pass")
        _req(g2._is_strict_int(42) is True, "exact int 42 must pass")
        for bad in (True, False, _Color.ONE, _SubInt(1), "1", Fraction(1, 1)):
            _req(g2._is_strict_int(bad) is False, f"_is_strict_int must reject {type(bad).__name__}")
        with self.assertRaisesRegex(ValueError, "SAMPLED_INVALID_TOTAL"):
            g2.evaluate_sampled_integrity(0, _Color.ONE, 0)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "SAMPLED_INVALID_TESTED"):
            g2.evaluate_sampled_integrity(_SubInt(1), 2, 0)

        # Strict str checks in _is_clean_ascii and _is_lower_hex (exact ASCII 32..126 and hex64 boundaries)
        _req(g2._is_clean_ascii("a b") is True, "internal ASCII space (32) must pass")
        _req(g2._is_clean_ascii("~") is True, "ASCII tilde (126) must pass")
        for bad_ascii in ("", " a", "a ", "\x1f", "\x7f", _SubStr("1/2"), _LyingStr("bogus"), 123, None):
            _req(g2._is_clean_ascii(bad_ascii) is False, f"_is_clean_ascii must reject {bad_ascii!r}")

        good_hex = "0123456789abcdef" * 4
        _req(g2._is_lower_hex(good_hex, 64) is True, "valid 64-char lower hex must pass")
        for bad_hex in (_SubStr(good_hex), 123, None, "a" * 63, "a" * 65, "A" * 64, "g" * 64):
            _req(g2._is_lower_hex(bad_hex, 64) is False, f"_is_lower_hex must reject {bad_hex!r}")

    def test_05_parse_exact_rational_canonical_and_digit_bounds(self) -> None:
        # Exact valid canonical forms (bijective with _fmt_q, plus 1000-digit boundary)
        _req(g2._parse_exact_rational(Fraction(3, 7)) == Fraction(3, 7), "exact Fraction failed")
        _req(g2._parse_exact_rational(0) == Fraction(0, 1), "exact int 0 failed")
        _req(g2._parse_exact_rational("0") == Fraction(0, 1), "'0' failed")
        _req(g2._parse_exact_rational("-5") == Fraction(-5, 1), "'-5' failed")
        _req(g2._parse_exact_rational("1/2") == Fraction(1, 2), "'1/2' failed")
        max_num = "9" * g2.MAX_RATIONAL_DIGITS
        _req(g2._parse_exact_rational(max_num) == Fraction(int(max_num), 1), "exact 1000-digit num failed")
        _req(g2._parse_exact_rational("1/" + max_num) == Fraction(1, int(max_num)), "exact 1000-digit den failed")

        for bad, code in (
            (_SubFrac(1, 2), "RATIONAL_TYPE_OR_SYNTAX"),
            (_SubInt(1), "RATIONAL_TYPE_OR_SYNTAX"),
            (_Color.ONE, "RATIONAL_TYPE_OR_SYNTAX"),
            (_SubStr("1/2"), "RATIONAL_TYPE_OR_SYNTAX"),
            (_LyingStr("bogus"), "RATIONAL_TYPE_OR_SYNTAX"),
            ("", "RATIONAL_TYPE_OR_SYNTAX"),
            (" 1", "RATIONAL_TYPE_OR_SYNTAX"),
            ("1 ", "RATIONAL_TYPE_OR_SYNTAX"),
            ("1\u0662", "RATIONAL_TYPE_OR_SYNTAX"),
            ("1/2/3", "RATIONAL_TOO_MANY_SLASHES"),
            ("-", "RATIONAL_INVALID_NUMERATOR"),
            ("+5", "RATIONAL_INVALID_NUMERATOR"),
            ("9" * (g2.MAX_RATIONAL_DIGITS + 1), "RATIONAL_INVALID_NUMERATOR"),
            ("1/", "RATIONAL_INVALID_DENOMINATOR"),
            ("1/+5", "RATIONAL_INVALID_DENOMINATOR"),
            ("1/" + "9" * (g2.MAX_RATIONAL_DIGITS + 1), "RATIONAL_INVALID_DENOMINATOR"),
            ("01", "RATIONAL_LEADING_ZERO"),
            ("-01", "RATIONAL_LEADING_ZERO"),
            ("00", "RATIONAL_LEADING_ZERO"),
            ("1/02", "RATIONAL_LEADING_ZERO"),
            ("1/01", "RATIONAL_LEADING_ZERO"),
            ("-0", "RATIONAL_NEGATIVE_ZERO"),
            ("-0/1", "RATIONAL_NEGATIVE_ZERO"),
            ("-0/5", "RATIONAL_NEGATIVE_ZERO"),
            ("1/0", "RATIONAL_NONPOSITIVE_DENOMINATOR"),
            ("0/0", "RATIONAL_NONPOSITIVE_DENOMINATOR"),
            ("3/1", "RATIONAL_UNIT_DENOMINATOR"),
            ("0/1", "RATIONAL_UNIT_DENOMINATOR"),
            ("-5/1", "RATIONAL_UNIT_DENOMINATOR"),
            ("2/4", "RATIONAL_NOT_REDUCED"),
            ("-2/4", "RATIONAL_NOT_REDUCED"),
            ("0/2", "RATIONAL_NOT_REDUCED"),
            ("6/3", "RATIONAL_NOT_REDUCED"),
        ):
            with self.assertRaisesRegex(ValueError, code, msg=f"expected {code} for {bad!r}"):
                g2._parse_exact_rational(bad)

    def test_06_iterative_depth_bounded_no_floats_and_deep_json(self) -> None:
        # Exact MAX_CONTAINER_DEPTH (64) passes; 65 and 2000 raise typed AletheiaError (never RecursionError)
        ok_nest: object = 1
        for _ in range(g2.MAX_CONTAINER_DEPTH):
            ok_nest = [ok_nest]
        g2._verify_no_floats(ok_nest)

        with self.assertRaises(AletheiaError) as cm_65:
            g2._verify_no_floats([ok_nest])
        _req(cm_65.exception.code == "MAX_DEPTH_EXCEEDED", f"wrong code at depth 65: {cm_65.exception.code}")

        deep_2000: object = 1
        for _ in range(2000):
            deep_2000 = [deep_2000]
        with self.assertRaises(AletheiaError) as cm_2k:
            g2._verify_no_floats(deep_2000)
        _req(cm_2k.exception.code == "MAX_DEPTH_EXCEEDED", f"wrong code at depth 2000: {cm_2k.exception.code}")

        # Float detection across dict keys, dict values, lists, and tuples
        for bad_float in ({0.5: 1}, {"k": 0.5}, [0.5], (0.5,)):
            with self.assertRaisesRegex(ValueError, "FLOAT_FORBIDDEN"):
                g2._verify_no_floats(bad_float)

        # End-to-end through certify_transformational_steelman
        with self.assertRaises(AletheiaError) as cm_ts:
            g2.certify_transformational_steelman({"deep": deep_2000})  # type: ignore[arg-type]
        _req(cm_ts.exception.code == "MAX_DEPTH_EXCEEDED", f"wrong code: {cm_ts.exception.code}")

        # Deeply nested JSON object bytes in _parse_strict_json_bytes must raise AletheiaError (never raw RecursionError)
        for depth in (g2.MAX_CONTAINER_DEPTH + 10, 2500):
            deep_json = b'{"a":' * depth + b"1" + b"}" * depth
            with self.assertRaises(AletheiaError) as cm_dj:
                g2._parse_strict_json_bytes(deep_json)
            _req(cm_dj.exception.code == "MAX_DEPTH_EXCEEDED", f"wrong deep JSON code at {depth}: {cm_dj.exception.code}")
        with mock.patch.object(g2.json, "loads", side_effect=RecursionError("depth")):
            with self.assertRaises(AletheiaError) as cm_rec:
                g2._parse_strict_json_bytes(b"{}")
        _req(cm_rec.exception.code == "MAX_DEPTH_EXCEEDED", f"wrong RecursionError code: {cm_rec.exception.code}")


if __name__ == "__main__":
    unittest.main()
