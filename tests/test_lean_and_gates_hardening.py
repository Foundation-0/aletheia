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
                [("LEAN4_SORRY", 3)],
            ),
            (
                'def a : Nat := panic!"{"\ntheorem t : False := sorry\ndef b := "}"\n',
                [("LEAN4_SORRY", 2)],
            ),
            (
                'def a := foos!"{"\ntheorem t : False := sorry\ndef b := "}"\n',
                [("LEAN4_SORRY", 2)],
            ),
            (
                'def a := Foo.s!"{"\ntheorem t : False := sorry\ndef b := "}"\n',
                [("LEAN4_SORRY", 2)],
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
            'def a := s "hello {sorry}"\n',
            'def a := s!x\n',
            'def a := x!"bad {sorry} state"\n',
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

    def test_02d_live_lean4_compiler_witnesses(self) -> None:
        """When a live `lean` binary is on PATH, verify each new escape & clean control actually compiles (rc == 0)."""
        lean_exe = shutil.which("lean")
        if lean_exe is None:
            return
        with tempfile.TemporaryDirectory(prefix="aletheia_lean_live_") as td:
            for idx, (label, src, expect_clean, allow_non_init) in enumerate(
                (
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
                    ("clean_print_axioms", "theorem ok : 1 + 1 = 2 := rfl\n#print axioms ok\n#print\n  axioms ok\n", True, False),
                )
            ):
                p = Path(td) / f"Probe{idx}.lean"
                p.write_text(src, encoding="utf-8")
                proc = subprocess.run([lean_exe, str(p)], capture_output=True, text=True, timeout=60, check=False)
                _req(proc.returncode == 0, f"live Lean failed on {label}: rc={proc.returncode} out={proc.stdout!r} err={proc.stderr!r}")
                res = audit_lean4_source(src, allow_non_init_imports=allow_non_init)
                _req(res["clean"] is expect_clean, f"audit mismatch on live {label}: {res}")

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
