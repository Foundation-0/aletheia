"""
R5 adversarial & mutation-killing test suite for Aletheia R13b Lean 4.36.0 trust-boundary
hardening (`W13-OBS-BVDECIDE` + `lake-manifest.json` `packages: []` verification).

Zero external dependencies (Python 3 stdlib only). Zero bare `assert` statements.
Zero skipped tests (100% pure-Python R4 parity across `-I -B`, `-I -O -B`, `-I -B -W error`).
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia.audit_check import (
    audit_lean4_axiom_log,
    audit_lean4_directory,
    audit_lean4_lake_manifest,
    audit_lean4_lake_manifest_text,
    audit_lean4_lakefile,
    audit_lean4_source,
    parse_lakefile_lean_requires,
    parse_lakefile_toml_requires,
    run_audit_check,
    scan_lean4_axiom_log_text,
    scan_lean4_bv_decide_source,
)
from aletheia.cli import main as cli_main
from aletheia.lean_r13b import (
    extract_custom_lean4_interp_prefixes,
    is_ambiguous_lean4_hash_command,
    is_bv_decide_module,
    is_lean4_id_first,
    is_lean4_id_rest,
    is_lean4_safe_guillemet_ident,
    is_lean4_word_cont,
    match_lean4_char_literal_end,
    match_lean4_hash_command_end,
    normalize_lean4_module_name,
    scan_lean4_numeric_literal_end,
)
from aletheia.strict_io import parse_strict_json_text


def _req(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _write_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        rc = cli_main(argv)
    return rc, out_buf.getvalue(), err_buf.getvalue()


class TestLeanR13bBVDecideAndManifestR5(unittest.TestCase):
    def test_01_bv_decide_tactic_calls_and_numeric_adjacent_bypasses(self) -> None:
        """Must-fail: plain, trace `?`, parenthesized, and W10-OBS-32 numeric-adjacent `bv_decide`."""
        attacks = [
            ("plain", "theorem t (x : Bool) : (x && true) = x := by bv_decide\n"),
            ("qmark", "theorem t (x : Bool) : (x && true) = x := by bv_decide?\n"),
            ("parens", "theorem t (x : Bool) : (x && true) = x := by (bv_decide)\n"),
            ("config", "theorem t (x : Bool) : (x && true) = x := by bv_decide (config := { acNf := false })\n"),
            ("iter_dec", "theorem t (x : Bool) : (x && true) = x := by iterate 1bv_decide\n"),
            ("iter_dec_us", "theorem t (x : Bool) : (x && true) = x := by iterate 1_0bv_decide\n"),
            ("iter_bin", "theorem t (x : Bool) : (x && true) = x := by iterate 0b1bv_decide\n"),
            ("iter_bin_upper", "theorem t (x : Bool) : (x && true) = x := by iterate 0B1_0bv_decide\n"),
            ("iter_oct", "theorem t (x : Bool) : (x && true) = x := by iterate 0o7bv_decide\n"),
            ("iter_oct_upper", "theorem t (x : Bool) : (x && true) = x := by iterate 0O1_7bv_decide\n"),
            ("iter_float", "theorem t (x : Bool) : (x && true) = x := by iterate 1.0bv_decide\n"),
            ("iter_sci", "theorem t (x : Bool) : (x && true) = x := by iterate 1e0bv_decide\n"),
            ("iter_sci_sign", "theorem t (x : Bool) : (x && true) = x := by iterate 1.e+2bv_decide\n"),
            ("qualified", "theorem t : True := by Tactic.bv_decide\n"),
            ("after_char_quote", "def q : Char := '\"'\ntheorem t : True := by bv_decide\n"),
            ("after_hex_char", "def q : Char := '\\x22'\ntheorem t : True := by bv_decide\n"),
            ("after_uni_char", "def q : Char := '\\u0022'\ntheorem t : True := by bv_decide\n"),
            ("guillemet_bv", "theorem t : True := by «bv_decide»\n"),
            (
                "b1_fake_comment_guillemet",
                "def «/-» : Nat := 1\n"
                "theorem t (x y : BitVec 4) : x + y = y + x := by bv_decide\n"
                "def «-/» : Nat := 2\n",
            ),
            (
                "b1_fake_string_guillemet",
                'def «a"» : Nat := 1\n'
                "theorem t (x y : BitVec 4) : x + y = y + x := by bv_decide\n"
                'def «b"» : Nat := 2\n',
            ),
            (
                "b1_fake_line_comment_guillemet",
                "def «--» : Nat := 1; theorem t : True := by bv_decide\n",
            ),
            (
                "n1_hash_check_char_quote_bv_decide",
                "import Init\n#check'\"'\ntheorem t (x : Bool) : (x && true) = x := by bv_decide\n-- \"\n",
            ),
            (
                "p1_hash_eval_raw_string_bv_decide",
                "import Init\n#evalr\"\\\"\ntheorem t (x : Bool) : (x && true) = x := by bv_decide\n-- \"\n",
            ),
            (
                "n2_bv_check_lrat",
                'theorem t (x : BitVec 4) : x = x := by bv_check "Gen.lean-G-2-65.lrat"\n',
            ),
            (
                "n2_bv_check_qmark",
                'theorem t (x : BitVec 4) : x = x := by bv_check? "Gen.lean-G-2-65.lrat"\n',
            ),
            (
                "n2_bv_check_numeric_adj",
                'theorem t (x : BitVec 4) : x = x := by iterate 1bv_check "Gen.lean-G-2-65.lrat"\n',
            ),
            (
                "p2_interp_s_bang_bv_decide",
                'def T : String := s!"{let _ : ∀ x : Bool, x = x := by intros; bv_decide; 0}"\n',
            ),
            (
                "p2_interp_spaced_s_bang_bv_decide",
                'def T : String := s! "{let _ : ∀ x : Bool, x = x := by intros; bv_decide; 0}"\n',
            ),
            (
                "p2_interp_nested_braces_bv_decide",
                'def T : String := m!"{({ a := (by bv_decide : True) })}"\n',
            ),
        ]
        for label, src in attacks:
            res = audit_lean4_source(src)
            codes = [f["code"] for f in res["findings"]]
            _req(
                not res["clean"] and "LEAN4_BV_DECIDE" in codes,
                f"attack {label!r} missed LEAN4_BV_DECIDE: {res}",
            )

        # N1 & P1 & P2 regression controls for `sorry` (ensuring #check'"', #evalr"\", #mycmdr"\",
        # s!"{...}", Macro.trace[foo] "{...}", and custom interpolatedStr macros cannot hide sorry!)
        for label, src in (
            ("n1_hash_check_sorry", "import Init\n#check'\"'\ntheorem T : False := by sorry\n-- \"\n"),
            ("n1_hash_print_sorry", "import Init\n#print'\"'\ntheorem T : False := by sorry\n-- \"\n"),
            ("p1_hash_eval_raw_sorry", "import Init\n#evalr\"\\\"\ntheorem T : False := by sorry\n-- \"\n"),
            ("p1_hash_eval_bang_raw_sorry", "import Init\n#eval!r\"\\\"\ntheorem T : False := by sorry\n-- \"\n"),
            (
                "p1_custom_hash_raw_sorry",
                'syntax "#mycmd" term : command\n#mycmdr"\\"\ntheorem T : False := by sorry\n-- "\n',
            ),
            ("p2_interp_s_bang_sorry", 'def T : String := s!"{(by sorry : Nat)}"\n'),
            ("p2_interp_dbg_trace_sorry", 'def T : Nat := dbg_trace "{(by sorry : Nat)}"; 0\n'),
            ("p2_interp_macro_trace_sorry", 'def T : Lean.MacroM Unit := Macro.trace[foo] "{(by sorry : Nat)}"\n'),
            (
                "p2_custom_bang_macro_sorry",
                'macro "my!" s:interpolatedStr(term) : term => `(s! $s)\ndef T : String := my!"{(by sorry : Nat)}"\n',
            ),
            (
                "p2_custom_plain_macro_sorry",
                'macro "myk" s:interpolatedStr(term) : term => `(s! $s)\ndef T : String := myk "{(by sorry : Nat)}"\n',
            ),
            (
                "p2_interp_brace_in_inner_str",
                'def T : String := s!"{(let _ := "}"; (by sorry : Nat))}"\n',
            ),
            (
                "p2_unmatched_plain_lbrace_no_swallow",
                'def s1 : String := "{"\ntheorem T : False := by sorry\ndef s2 : String := "}"\n',
            ),
        ):
            res_s = audit_lean4_source(src)
            _req(
                not res_s["clean"] and "LEAN4_SORRY" in {f["code"] for f in res_s["findings"]},
                f"sorry bypass {label!r} missed: {res_s}",
            )

        # Unterminated interpolated string must fail closed
        res_uinterp = audit_lean4_source('def T : String := s!"{1 + 2\n')
        _req(
            not res_uinterp["clean"]
            and "LEAN4_UNTERMINATED_STRING" in {f["code"] for f in res_uinterp["findings"]},
            f"unterminated interpolated string missed: {res_uinterp}",
        )

        # Direct boundary tests on R13b N1/P1/P2 helpers (100% mutation kill)
        _req(is_lean4_word_cont("a") and not is_lean4_word_cont("!"), "word_cont check")
        _req(match_lean4_hash_command_end("#check'\"'", 0, 9) == 6, "hash cmd stops before char lit")
        _req(match_lean4_hash_command_end("#evalr\"\\\"", 0, 9) == 5, "hash cmd stops before raw str")
        _req(match_lean4_hash_command_end("#evalr#\"\\\"#", 0, 11) == 5, "hash cmd stops before r# raw str")
        _req(match_lean4_hash_command_end("#eval! \"{\"", 0, 10) == 6, "hash cmd consumes trailing !")
        _req(match_lean4_hash_command_end("#bar", 0, 4) == 4, "hash cmd ending in r at EOF")
        _req(match_lean4_hash_command_end("#bar \"x\"", 0, 8) == 4, "hash cmd ending in r before space quote")
        _req(match_lean4_hash_command_end("#foo' 1", 0, 7) == 5, "hash cmd keeps non-char prime")
        _req(extract_custom_lean4_interp_prefixes("def x := 1") == (frozenset(), frozenset()), "no custom interp")
        _req(
            extract_custom_lean4_interp_prefixes(
                'macro "my!" s:interpolatedStr(term) : term => `(s! $s)\n'
                'syntax "myk" interpolatedStr(term) : term\n'
            )
            == (frozenset({"my"}), frozenset({"myk"})),
            "custom interp bang + plain extraction",
        )

        # Unterminated French-quoted identifier must fail closed
        res_unterm = audit_lean4_source("def «unclosed : Nat := 1\n")
        _req(
            not res_unterm["clean"] and [f["code"] for f in res_unterm["findings"]] == ["LEAN4_UNTERMINATED_IDENT"],
            f"unterminated guillemet ident missed: {res_unterm}",
        )
        _req(is_lean4_safe_guillemet_ident("BVDecide") and not is_lean4_safe_guillemet_ident("/-"), "guillemet safe check")
        _req(normalize_lean4_module_name("Std.Tactic.«BVDecide»") == "Std.Tactic.BVDecide", "module normalize check")

        # W10-OBS-32 numeric-adjacent also unmasks existing `sorry`/`admit`/`native_decide`
        for src, want in (
            ("theorem t : True := by iterate 1sorry\n", "LEAN4_SORRY"),
            ("theorem t : True := by iterate 0b1admit\n", "LEAN4_ADMIT"),
            ("theorem t : True := by iterate 0o1admit\n", "LEAN4_ADMIT"),
            ("theorem t : True := by iterate 0x1sorry\n", "LEAN4_SORRY"),
            ("theorem t : 1 + 1 = 2 := by iterate 1native_decide\n", "LEAN4_NATIVE_DECIDE"),
        ):
            res = audit_lean4_source(src)
            codes = {f["code"] for f in res["findings"]}
            _req(not res["clean"] and want in codes, f"numeric-adjacent {want} missed: {res}")

        # Exact hex boundary check: in Lean 4, `0x1bv_decide` lexes `0x1b` + `v_decide` (not `bv_decide`).
        _req(scan_lean4_numeric_literal_end("0x1bv_decide", 0, 12) == 4, "hex must consume 0x1b")
        _req(scan_lean4_numeric_literal_end("0b1bv_decide", 0, 12) == 3, "bin must stop before 'b'")
        _req(scan_lean4_numeric_literal_end("0o7bv_decide", 0, 12) == 3, "oct must stop before 'b'")
        _req(is_lean4_id_first("a") and not is_lean4_id_first("1"), "id_first check")
        _req(is_lean4_id_rest("'") and is_lean4_id_rest("1") and not is_lean4_id_rest(" "), "id_rest check")
        _req(match_lean4_char_literal_end("'a'", 0, 3) == 3, "simple char literal")
        _req(match_lean4_char_literal_end("'\\n'", 0, 4) == 4, "escaped char literal")
        _req(match_lean4_char_literal_end("'\\x27'", 0, 6) == 6, "hex char literal")
        _req(match_lean4_char_literal_end("'\\u0027'", 0, 8) == 8, "unicode char literal")
        _req(match_lean4_char_literal_end("'bad", 0, 4) is None, "unclosed char literal")

    def test_02_bv_decide_imports_references_and_native_axioms(self) -> None:
        """Must-fail: `Std.Tactic.BVDecide` / `Lean.Elab.Tactic.BVDecide` imports & refs + `_native.bv_decide` axioms."""
        # 1. Imports must fail CLOSED even when `allow_non_init_imports=True` or `Std` is allowed.
        for mod in (
            "Std",
            "Std.Tactic",
            "Lean",
            "Lean.Elab",
            "Lean.Elab.Tactic",
            "Std.Tactic.BVDecide",
            "Std.Tactic.«BVDecide»",
            "«Std».«Tactic».«BVDecide»",
            "Std.Tactic.BVDecide.LRAT",
            "Std.Tactic.BVDecide.Reflect",
            "Lean.Elab.Tactic.BVDecide",
            "Lean.Elab.Tactic.BVDecide.Frontend",
            "Lean.Meta.Tactic.BVDecide",
            "Lean.Meta.Tactic.BVDecide.BitBlast",
        ):
            _req(is_bv_decide_module(mod), f"expected BVDecide module: {mod}")
            for prefix in ("import ", "import all ", "public import ", "private\n  import ", "meta import "):
                src = f"{prefix}{mod}\ntheorem ok : True := trivial\n"
                res = audit_lean4_source(src, allow_non_init_imports=True)
                codes = [f["code"] for f in res["findings"]]
                _req(
                    not res["clean"] and codes == ["LEAN4_BV_DECIDE_IMPORT"],
                    f"import {prefix}{mod} expected only LEAN4_BV_DECIDE_IMPORT, got {res}",
                )

        # N2 same-line multi-import (`import Init import Std.Tactic`) must fail closed in both modes!
        for multi_imp in (
            "import Init import Std.Tactic\ntheorem ok : True := trivial\n",
            "import Init; import Std.Tactic.«BVDecide»\ntheorem ok : True := trivial\n",
            "import Init public import Lean.Elab.Tactic\ntheorem ok : True := trivial\n",
        ):
            for allow_ni in (False, True):
                res_mi = audit_lean4_source(multi_imp, allow_non_init_imports=allow_ni)
                _req(
                    not res_mi["clean"]
                    and "LEAN4_BV_DECIDE_IMPORT" in {f["code"] for f in res_mi["findings"]},
                    f"same-line multi-import {multi_imp!r} (allow={allow_ni}) missed: {res_mi}",
                )

        # Default (strict pure-Init): `import Std.Tactic.«BVDecide»` and umbrella `import Std.Tactic` / `import Std` MUST fail!
        for strict_imp in (
            "import Std.Tactic.BVDecide\ntheorem ok : True := trivial\n",
            "import Std.Tactic.«BVDecide»\ntheorem ok : True := trivial\n",
            "import Std.Tactic\ntheorem ok : True := trivial\n",
            "import Std\ntheorem ok : True := trivial\n",
            "import all Std.Tactic.BVDecide\ntheorem ok : True := trivial\n",
        ):
            res_std_bv = audit_lean4_source(strict_imp)
            _req(
                not res_std_bv["clean"]
                and [f["code"] for f in res_std_bv["findings"]] == ["LEAN4_BV_DECIDE_IMPORT"],
                f"import {strict_imp!r} bypassed pure-Init default: {res_std_bv}",
            )

        # Negative control on module predicate: non-BVDecide Std modules stay clean.
        _req(not is_bv_decide_module("Std.Data.HashMap"), "Std.Data.HashMap must not match")
        _req(not is_bv_decide_module("Std.Tactic.Do"), "Std.Tactic.Do must not match umbrella Std.Tactic")
        _req(not is_bv_decide_module("Std.Tactic.BVDecideHelper"), "prefix without dot must not match")

        # 2. Non-import references (single-line, French-quoted, and multiline dot chains).
        for src in (
            "open Std.Tactic.BVDecide\n",
            "open Std.Tactic.«BVDecide»\n",
            "open Lean.Elab.Tactic.BVDecide\n",
            "open Lean.Meta.Tactic.BVDecide\n",
            "def f := Std.Tactic.BVDecide.Reflect.verifyBVExpr\n",
            "def f := Std.Tactic.«BVDecide».Reflect.verifyBVExpr\n",
            "def f := Std\n  .Tactic\n  .BVDecide.Reflect.verifyBVExpr\n",
            "def f := Lean.Elab.Tactic.BVDecide.Frontend.bvDecide\n",
            "def f := Lean.Meta.Tactic.BVDecide.BitBlast\n",
        ):
            res = audit_lean4_source(src)
            codes = [f["code"] for f in res["findings"]]
            _req(not res["clean"] and "LEAN4_BV_DECIDE_REF" in codes, f"ref missed in {src!r}: {res}")

        # 3. Native LRAT axiom artifacts inside Lean source.
        for src in (
            "def a := LeanSVM.Proofs.t._native.bv_decide.ax_1_15\n",
            "def b := _native.bv_decide\n",
            "def c := foo._native.bv_decide.ax_0\n",
            "def d := _native . bv_decide . ax_2\n",
            "def e := foo.«_native».«bv_decide».ax_3\n",
        ):
            res = audit_lean4_source(src)
            codes = [f["code"] for f in res["findings"]]
            _req(
                not res["clean"] and "LEAN4_BV_DECIDE_AXIOM" in codes,
                f"native bv_decide axiom missed in {src!r}: {res}",
            )

        # Direct call to scan_lean4_bv_decide_source confirms exact dedup between import & ref lines.
        direct = scan_lean4_bv_decide_source(
            "import Std.Tactic.BVDecide\nopen Std.Tactic.BVDecide\n",
            import_entries=[(1, "Std.Tactic.BVDecide")],
        )
        _req(
            [(f["line"], f["code"]) for f in direct]
            == [(1, "LEAN4_BV_DECIDE_IMPORT"), (2, "LEAN4_BV_DECIDE_REF")],
            f"unexpected direct findings: {direct}",
        )

    def test_03_comments_strings_and_benign_identifiers_have_zero_false_positives(self) -> None:
        """Must-pass: comments, nested comments, regular/raw strings, and benign identifiers stay clean."""
        clean_src = "\n".join([
            "import Init",
            "import Std.Data.HashMap",
            "-- by bv_decide",
            "-- import Std.Tactic.BVDecide",
            "-- foo._native.bv_decide.ax_1_15",
            "/- block comment mentioning bv_decide, Lean.Elab.Tactic.BVDecide, and _native.bv_decide -/",
            "/- outer /- nested bv_decide -/ still comment Std.Tactic.BVDecide -/",
            'def s1 : String := "by bv_decide bv_check Std.Tactic.BVDecide ._native.bv_decide.ax_1"',
            'def s2 : String := r"by bv_decide bv_check Lean.Elab.Tactic.BVDecide"',
            'def s3 : String := r#"by iterate 1bv_decide _native.bv_decide"#',
            'def s4 : String := s!"plain literal bv_decide bv_check {1 + 2} end"',
            'def bar! (s : String) : String := s',
            'def s5 : String := bar! "{"',
            "def q : Char := '\"'",
            "def my_bv_decide_note : Nat := 1",
            "def my_bv_check_note : Nat := 1",
            "def bv_decide_count : Nat := 0",
            "def bv_decide' : Nat := 2",
            "def x1bv_decide : Nat := 3",
            "def αbv_decide : Nat := 4",
            "def αbv_check : Nat := 4",
            "def bv_decide₁ : Nat := 5",
            "def bv_check₁ : Nat := 5",
            "def bv_decideα : Nat := 6",
            "def αStd.Tactic.BVDecide : Nat := 7",
            "def Std.Tactic.BVDecideα : Nat := 8",
            "def α_native.bv_decide : Nat := 9",
            "def foo._native.bv_decide₁ : Nat := 10",
            "def hex_val : Nat := 0x1bv_decide",
            "theorem ok (x : Nat) : x + 0 = x := by simp",
        ]) + "\n"
        res = audit_lean4_source(clean_src)
        _req(res["clean"] and res["findings"] == [], f"false positive on clean Lean source: {res}")

    def test_04_axiom_audit_logs_catch_native_bv_decide_and_unsound_axioms(self) -> None:
        """Must-fail & must-pass on `#print axioms` / `Lean.collectAxioms` logs."""
        clean_log = (
            "'MatMul94.ok' depends on axioms: [propext, Quot.sound]\n"
            "'MatMul94.classical' depends on axioms: [propext, Classical.choice, Quot.sound]\n"
        )
        _req(scan_lean4_axiom_log_text(clean_log) == [], "clean axiom log flagged")

        dirty_cases = [
            (
                "'LeanSVM.Compiler.Proofs.loadBytes_storeBytes_b8_same' depends on axioms: "
                "[propext, Classical.choice, Quot.sound, "
                "LeanSVM.Compiler.Proofs.loadBytes_storeBytes_b8_same._native.bv_decide.ax_1_15]\n",
                "LEAN4_BV_DECIDE_AXIOM",
            ),
            ("'t' depends on axioms: [_native.bv_decide]\n", "LEAN4_BV_DECIDE_AXIOM"),
            ("'t' depends on axioms: [propext, sorryAx]\n", "LEAN4_SORRY_AX"),
            ("'t' depends on axioms: [Lean.ofReduceBool]\n", "LEAN4_OF_REDUCE_BOOL"),
            ("'t' depends on axioms: [Lean.trustCompiler]\n", "LEAN4_TRUST_COMPILER"),
        ]
        for log_txt, want in dirty_cases:
            hits = scan_lean4_axiom_log_text(log_txt)
            _req([h["code"] for h in hits] == [want], f"axiom log {log_txt!r} expected [{want}], got {hits}")

        with tempfile.TemporaryDirectory(prefix="aletheia_r13b_ax_") as td:
            root = Path(td)
            # Clean log on disk
            good_log = root / "axioms.log"
            _write_lf(good_log, clean_log)
            r_ok = audit_lean4_axiom_log(good_log)
            _req(r_ok["clean"] and r_ok["findings"] == [], f"clean axiom log file failed: {r_ok}")

            # Missing log fails closed
            r_miss = audit_lean4_axiom_log(root / "missing_axioms.log")
            _req(
                not r_miss["clean"] and r_miss["findings"][0]["code"] == "LEAN4_AXIOM_LOG_INVALID",
                f"missing axiom log did not fail closed: {r_miss}",
            )

            # Non-regular (directory / symlink) fails closed
            dir_log = root / "dir_axioms.log"
            dir_log.mkdir()
            r_dir = audit_lean4_axiom_log(dir_log)
            _req(
                not r_dir["clean"] and r_dir["findings"][0]["code"] == "LEAN4_AXIOM_LOG_INVALID",
                f"dir axiom log did not fail closed: {r_dir}",
            )

            sym_log = root / "sym_axioms.log"
            os.symlink(good_log, sym_log)
            r_sym = audit_lean4_axiom_log(sym_log)
            _req(
                not r_sym["clean"] and r_sym["findings"][0]["code"] == "LEAN4_AXIOM_LOG_INVALID",
                f"symlink axiom log did not fail closed: {r_sym}",
            )

            # Invalid UTF-8 fails closed
            bad_utf8 = root / "bad_utf8_axioms.log"
            bad_utf8.write_bytes(b"\xff\xfeinvalid\n")
            r_utf = audit_lean4_axiom_log(bad_utf8)
            _req(
                not r_utf["clean"] and r_utf["findings"][0]["code"] == "LEAN4_AXIOM_LOG_INVALID",
                f"bad utf8 axiom log did not fail closed: {r_utf}",
            )

    def test_05_lake_manifest_empty_vs_nonempty_and_malformed(self) -> None:
        """Must-pass on `packages: []`; must-fail on non-empty, missing, wrong-type, duplicate-key, or corrupt JSON."""
        valid_manifest = json.dumps(
            {"version": "1.1.0", "packagesDir": ".lake/packages", "packages": [], "lakeDir": ".lake"},
            indent=2,
        ) + "\n"
        r_ok = audit_lean4_lake_manifest_text(valid_manifest)
        _req(r_ok["clean"] and r_ok["findings"] == [] and r_ok["package_count"] == 0, f"valid manifest failed: {r_ok}")

        # Non-empty packages (dict entries with name, and non-dict / nameless entries)
        nonempty_named = json.dumps(
            {
                "version": "1.1.0",
                "packages": [
                    {"name": "mathlib", "type": "git"},
                    {"name": "batteries", "type": "git"},
                ],
            },
            indent=2,
        ) + "\n"
        r_ne = audit_lean4_lake_manifest_text(nonempty_named)
        _req(
            not r_ne["clean"]
            and r_ne["package_count"] == 2
            and [f["code"] for f in r_ne["findings"]] == ["LEAN4_LAKE_MANIFEST_NONEMPTY_PACKAGES"]
            and "mathlib" in r_ne["findings"][0]["excerpt"]
            and "batteries" in r_ne["findings"][0]["excerpt"]
            and r_ne["findings"][0]["line"] == 3,
            f"non-empty named packages failed check: {r_ne}",
        )

        # Explicit opt-in allow_external_packages=True allows non-empty list
        r_ne_allow = audit_lean4_lake_manifest_text(nonempty_named, allow_external_packages=True)
        _req(r_ne_allow["clean"] and r_ne_allow["package_count"] == 2, f"allow_external_packages failed: {r_ne_allow}")

        # Non-dict package item fallback formatting
        r_ne_str = audit_lean4_lake_manifest_text('{"version": 7, "packages": ["std4"]}\n')
        _req(
            not r_ne_str["clean"]
            and r_ne_str["findings"][0]["code"] == "LEAN4_LAKE_MANIFEST_NONEMPTY_PACKAGES"
            and "std4" in r_ne_str["findings"][0]["excerpt"],
            f"non-dict package item check failed: {r_ne_str}",
        )

        # Malformed / missing / wrong-type / duplicate-key / NaN manifests -> LEAN4_LAKE_MANIFEST_INVALID
        invalid_payloads = [
            ("empty", ""),
            ("syntax_err", "{not json\n"),
            ("root_array", "[]\n"),
            ("missing_packages", '{"version": "1.1.0"}\n'),
            ("packages_null", '{"version": "1.1.0", "packages": null}\n'),
            ("packages_empty_dict", '{"version": "1.1.0", "packages": {}}\n'),
            ("packages_nonempty_dict", '{"version": "1.1.0", "packages": {"mathlib": 1}}\n'),
            ("packages_str", '{"version": "1.1.0", "packages": "[]"}\n'),
            ("packages_int", '{"version": "1.1.0", "packages": 0}\n'),
            ("dup_key_shadow", '{"packages": [{"name": "mathlib"}], "packages": []}\n'),
            ("nan_const", '{"packages": [], "bad": NaN}\n'),
        ]
        for label, payload in invalid_payloads:
            r_inv = audit_lean4_lake_manifest_text(payload)
            _req(
                not r_inv["clean"]
                and r_inv["package_count"] is None
                and [f["code"] for f in r_inv["findings"]] == ["LEAN4_LAKE_MANIFEST_INVALID"],
                f"invalid manifest {label!r} did not fail with LEAN4_LAKE_MANIFEST_INVALID: {r_inv}",
            )

        # Disk-level fail-closed checks: missing, directory, symlink, FIFO (if POSIX), invalid UTF-8
        with tempfile.TemporaryDirectory(prefix="aletheia_r13b_mf_") as td:
            root = Path(td)
            mf_good = root / "lake-manifest.json"
            _write_lf(mf_good, valid_manifest)
            _req(audit_lean4_lake_manifest(mf_good)["clean"], "good manifest on disk failed")

            r_miss = audit_lean4_lake_manifest(root / "missing.json")
            _req(
                not r_miss["clean"] and r_miss["findings"][0]["code"] == "LEAN4_LAKE_MANIFEST_INVALID",
                f"missing manifest failed: {r_miss}",
            )

            mf_dir = root / "dir_manifest"
            mf_dir.mkdir()
            r_dir = audit_lean4_lake_manifest(mf_dir)
            _req(
                not r_dir["clean"] and r_dir["findings"][0]["code"] == "LEAN4_LAKE_MANIFEST_INVALID",
                f"dir manifest failed: {r_dir}",
            )

            mf_sym = root / "sym_manifest.json"
            os.symlink(mf_good, mf_sym)
            r_sym = audit_lean4_lake_manifest(mf_sym)
            _req(
                not r_sym["clean"] and r_sym["findings"][0]["code"] == "LEAN4_LAKE_MANIFEST_INVALID",
                f"symlink manifest failed: {r_sym}",
            )

            mf_utf8 = root / "bad_utf8.json"
            mf_utf8.write_bytes(b"\xff\xfe{}\n")
            r_utf = audit_lean4_lake_manifest(mf_utf8)
            _req(
                not r_utf["clean"] and r_utf["findings"][0]["code"] == "LEAN4_LAKE_MANIFEST_INVALID",
                f"bad utf8 manifest failed: {r_utf}",
            )

            if hasattr(os, "mkfifo"):
                mf_fifo = root / "fifo_manifest.json"
                os.mkfifo(mf_fifo)
                r_fifo = audit_lean4_lake_manifest(mf_fifo)
                _req(
                    not r_fifo["clean"] and r_fifo["findings"][0]["code"] == "LEAN4_LAKE_MANIFEST_INVALID",
                    f"fifo manifest failed: {r_fifo}",
                )

    def test_06_end_to_end_audit_directory_and_cli_integration(self) -> None:
        """End-to-end `audit_lean4_directory`, `run_audit_check`, and `aletheia audit-check --lean-audit` CLI."""
        with tempfile.TemporaryDirectory(prefix="aletheia_r13b_e2e_") as td:
            base = Path(td)

            # 1. Clean pure-Init Lean project with `packages: []` + clean `axioms.log` + ignored `.lake/` manifest
            clean_proj = base / "clean_proj"
            _write_lf(clean_proj / "Main.lean", "import Init\ntheorem id_nat (n : Nat) : n = n := rfl\n")
            _write_lf(
                clean_proj / "lake-manifest.json",
                '{"version": "1.1.0", "packagesDir": ".lake/packages", "packages": [], "lakeDir": ".lake"}\n',
            )
            _write_lf(clean_proj / "axioms.log", "'id_nat' depends on axioms: [propext, Quot.sound]\n")
            # A non-empty manifest buried inside `.lake/` must be skipped by directory walk.
            _write_lf(
                clean_proj / ".lake" / "packages" / "dep" / "lake-manifest.json",
                '{"version": "1.1.0", "packages": [{"name": "ignored_in_dotlake"}]}\n',
            )
            rc_ok, out_ok, err_ok = _run_cli(["audit-check", str(clean_proj), "--lean-audit", "--json"])
            _req(rc_ok == 0, f"clean project CLI failed: rc={rc_ok} out={out_ok} err={err_ok}")
            obj_ok = parse_strict_json_text(out_ok)
            _req(
                obj_ok["passed"]
                and obj_ok["lean_audit"]["clean"]
                and obj_ok["lean_audit"]["files_checked"] == 1
                and obj_ok["lean_audit"]["manifests_checked"] == 1
                and obj_ok["lean_audit"]["axiom_logs_checked"] == 1,
                f"unexpected clean report: {obj_ok['lean_audit']}",
            )

            # Single-file audit on Main.lean checks sibling lake-manifest.json
            sf_ok = audit_lean4_directory(clean_proj / "Main.lean")
            _req(sf_ok["clean"] and sf_ok["manifests_checked"] == 1, f"single-file ok failed: {sf_ok}")
            # Direct single-file audit on lake-manifest.json and axioms.log
            _req(audit_lean4_directory(clean_proj / "lake-manifest.json")["manifests_checked"] == 1, "direct manifest file")
            _req(audit_lean4_directory(clean_proj / "axioms.log")["axiom_logs_checked"] == 1, "direct axiom log file")

            # 2. Project with non-empty lake-manifest.json fails closed via CLI
            bad_mf = base / "bad_manifest_proj"
            _write_lf(bad_mf / "Main.lean", "theorem ok : True := trivial\n")
            _write_lf(
                bad_mf / "lake-manifest.json",
                '{"version": "1.1.0", "packages": [{"name": "mathlib", "type": "git"}]}\n',
            )
            rc_mf, out_mf, _ = _run_cli(["audit-check", str(bad_mf), "--lean-audit", "--json"])
            obj_mf = parse_strict_json_text(out_mf)
            _req(
                rc_mf == 1
                and not obj_mf["passed"]
                and any(f["code"] == "LEAN4_LAKE_MANIFEST_NONEMPTY_PACKAGES" for f in obj_mf["lean_audit"]["findings"]),
                f"non-empty manifest CLI did not fail closed: {obj_mf}",
            )
            # Single-file audit on Main.lean also catches sibling bad lake-manifest.json
            sf_bad = audit_lean4_directory(bad_mf / "Main.lean")
            _req(
                not sf_bad["clean"]
                and sf_bad["findings"][0]["code"] == "LEAN4_LAKE_MANIFEST_NONEMPTY_PACKAGES",
                f"single-file sibling manifest check missed bad manifest: {sf_bad}",
            )

            # 3. Project with `bv_decide` (incl. numeric-adjacent) + `Std.Tactic.BVDecide` + dirty `axiom_audit.txt`
            bad_bv = base / "bad_bv_proj"
            _write_lf(
                bad_bv / "Proofs.lean",
                "import Std.Tactic.BVDecide\n"
                "theorem t1 (x : Bool) : (x && true) = x := by iterate 1bv_decide\n"
                "theorem t2 (x : Bool) : (x && true) = x := by iterate 0b1bv_decide\n",
            )
            _write_lf(
                bad_bv / "axiom_audit.txt",
                "'Proofs.t1' depends on axioms: [propext, Proofs.t1._native.bv_decide.ax_1_1]\n",
            )
            _write_lf(bad_bv / "lake-manifest.json", '{"version": "1.1.0", "packages": []}\n')
            rc_bv, out_bv, _ = _run_cli(["audit-check", str(bad_bv), "--lean-audit", "--json"])
            obj_bv = parse_strict_json_text(out_bv)
            bv_codes = {f["code"] for f in obj_bv["lean_audit"]["findings"]}
            _req(
                rc_bv == 1
                and not obj_bv["passed"]
                and {"LEAN4_BV_DECIDE_IMPORT", "LEAN4_BV_DECIDE", "LEAN4_BV_DECIDE_AXIOM"}.issubset(bv_codes),
                f"bv_decide project CLI missed expected codes: {bv_codes}",
            )

            # 4. Malformed lake-manifest.json inside subdirectory fails closed via audit_lean4_directory & run_audit_check
            bad_sub = base / "bad_sub_proj"
            _write_lf(bad_sub / "lean" / "Ok.lean", "theorem ok : True := trivial\n")
            _write_lf(bad_sub / "lean" / "lake-manifest.json", "{corrupt json\n")
            r_sub = run_audit_check(bad_sub, lean_audit=True)
            _req(
                not r_sub["passed"]
                and any(f["code"] == "LEAN4_LAKE_MANIFEST_INVALID" for f in r_sub["lean_audit"]["findings"]),
                f"corrupt nested lake-manifest.json missed: {r_sub['lean_audit']}",
            )

            # 5. Directory literally named `lake-manifest.json` fails closed (A3)
            dir_mf_proj = base / "dir_mf_proj"
            _write_lf(dir_mf_proj / "Ok.lean", "theorem ok : True := trivial\n")
            (dir_mf_proj / "lake-manifest.json").mkdir()
            r_dir_mf = audit_lean4_directory(dir_mf_proj)
            _req(
                not r_dir_mf["clean"]
                and r_dir_mf["findings"][0]["code"] == "LEAN4_LAKE_MANIFEST_INVALID",
                f"directory named lake-manifest.json missed: {r_dir_mf}",
            )

            # 6. Directory walk skips symlinked subdirs (never follows directory symlinks)
            outside = base / "outside"
            _write_lf(outside / "lake-manifest.json", '{"packages": [{"name": "escape"}]}\n')
            sym_proj = base / "sym_proj"
            _write_lf(sym_proj / "Ok.lean", "theorem ok : True := trivial\n")
            os.symlink(outside, sym_proj / "ext_link")
            r_sym_dir = audit_lean4_directory(sym_proj)
            _req(
                r_sym_dir["clean"] and r_sym_dir["manifests_checked"] == 0,
                f"directory symlink should not be followed by r13b walk: {r_sym_dir}",
            )

    def test_07_delta2_e1_b1_b2_b3_b4_and_import_guards(self) -> None:
        """Close all DELTA2 live Lean 4.36.0 escapes (E1, B1..B6, C3/E2/E3, A1'..A3', D1/D2) & M036/M037."""
        # 1. E1 combined full bv_decide exploit + C3/E2/E3 zero-whitespace guillemet imports
        e1_src = (
            "import«Std».Tactic.BVDecide\n"
            "def m! (x : String) : String := x\n"
            'def a := m! "{"\n'
            "theorem evil_bv (x y : BitVec 8) : x * y = y * x := by bv_decide\n"
            '-- "}"\n'
        )
        r_e1 = audit_lean4_source(e1_src)
        e1_codes = {f["code"] for f in r_e1["findings"]}
        _req(
            not r_e1["clean"]
            and {"LEAN4_BV_DECIDE_IMPORT", "LEAN4_BV_DECIDE"}.issubset(e1_codes)
            and "Std.Tactic.BVDecide" in r_e1["imports"],
            f"E1 exploit missed: {r_e1}",
        )
        for label, src, want_imp in (
            ("c3_std", "import«Std»\ntheorem t : True := trivial\n", "Std"),
            ("e2_lean_elab", "import«Lean».Elab\ntheorem t : True := trivial\n", "Lean.Elab"),
            ("e3_bvdecide", "import«Std».Tactic.BVDecide\ntheorem t : True := trivial\n", "Std.Tactic.BVDecide"),
            ("all_guil", "import all«Std»\ntheorem t : True := trivial\n", "Std"),
        ):
            r_g = audit_lean4_source(src)
            _req(
                not r_g["clean"]
                and "LEAN4_BV_DECIDE_IMPORT" in {f["code"] for f in r_g["findings"]}
                and want_imp in r_g["imports"],
                f"zero-ws guillemet import {label} missed: {r_g}",
            )

        # 2. B1/B2/B3 false-interpolation escapes via dual-projection (m!, logInfo, v!, throwError, reportIssue!, dbg_trace)
        for label, src in (
            ("b1_def_m_bang", 'def m! (x : String) := x\ndef a := m! "{"\ntheorem t : False := by sorry\n-- "}"\n'),
            ("b2_def_logInfo", 'def logInfo (x : String) := x\ndef a := logInfo "{"\ntheorem t : False := by sorry\n-- "}"\n'),
            ("b1_def_v_bang", 'def v! (x : String) := x\ndef a := v! "{"\ntheorem t : False := by sorry\n-- "}"\n'),
            ("b1_def_throwError", 'def throwError (x : String) := x\ndef a := throwError "{"\ntheorem t : False := by sorry\n-- "}"\n'),
            ("b1_def_reportIssue", 'def reportIssue! (x : String) := x\ndef a := reportIssue! "{"\ntheorem t : False := by sorry\n-- "}"\n'),
            ("b3_tactic_dbg_trace", 'theorem t : False := by\n  dbg_trace "{"\n  sorry\n-- "}"\n'),
        ):
            r_b1 = audit_lean4_source(src)
            _req(
                not r_b1["clean"] and "LEAN4_SORRY" in {f["code"] for f in r_b1["findings"]},
                f"false-interp escape {label} missed LEAN4_SORRY: {r_b1}",
            )

        # 3. B4/B5/B6 multiline, `?`-suffix, and multi-atom custom interpolatedStr macros
        for label, src in (
            (
                "b4_multiline_macro",
                'macro\n  "q!" s:interpolatedStr(term) : term => `(s! $s)\ndef t := q!"{(by sorry : Nat)}"\n',
            ),
            (
                "b4_3line_syntax",
                'syntax (name := q3!)\n  "q3!"\n  interpolatedStr(term) : term\ndef t := q3!"{(by sorry : Nat)}"\n',
            ),
            (
                "b5_qmark_macro",
                'macro "foo?" s:interpolatedStr(term) : term => `(s! $s)\ndef t := foo? "{(by sorry : Nat)}"\n',
            ),
            (
                "b6_multiatom_macro",
                'macro "foo" "bar" s:interpolatedStr(term) : term => `(s! $s)\ndef t := foo bar "{(by sorry : Nat)}"\n',
            ),
        ):
            r_cm = audit_lean4_source(src)
            codes_cm = {f["code"] for f in r_cm["findings"]}
            _req(
                not r_cm["clean"] and {"LEAN4_META_SYNTAX_ESCAPE", "LEAN4_SORRY"}.issubset(codes_cm),
                f"custom interp macro {label} missed findings: {r_cm}",
            )
        _req(
            extract_custom_lean4_interp_prefixes(
                'macro\n  "q!" s:interpolatedStr(term) : term => `(s! $s)\n'
                'macro "foo?" s:interpolatedStr(term) : term => `(s! $s)\n'
                'macro "foo" "bar" s:interpolatedStr(term) : term => `(s! $s)\n'
            )
            == (frozenset({"q"}), frozenset({"foo?", "bar"})),
            "multiline / qmark / multiatom custom interp extraction",
        )

        # 4. B3 ambiguous `#cmd` glued-quote / raw-string lexing (A1'/A2'/A3', standalone & with syntax)
        for label, src in (
            ("a1_kx", "#kx'\"'+\"\ntheorem evil : False := by sorry\n-- \"\n"),
            ("a2_kxr", '#kxr"\\"  "\ntheorem evil : False := by sorry\n-- "\n'),
            ("a3_kalpha", "#kα'\"'+\"\ntheorem evil : False := by sorry\n-- \"\n"),
            ("glued_dquote", '#foo"bar"\ntheorem evil : False := by sorry\n'),
        ):
            r_h = audit_lean4_source(src)
            _req(
                not r_h["clean"] and "LEAN4_AMBIGUOUS_LEXING" in {f["code"] for f in r_h["findings"]},
                f"B3 ambiguous #cmd {label} missed LEAN4_AMBIGUOUS_LEXING: {r_h}",
            )
        # Direct boundary tests on is_ambiguous_lean4_hash_command (100% mutate kill)
        _req(not is_ambiguous_lean4_hash_command("#[1]", 0, 1, 4), "bare # not ambiguous")
        _req(not is_ambiguous_lean4_hash_command("#cmd", 0, 4, 4), "#cmd at EOF not ambiguous")
        _req(not is_ambiguous_lean4_hash_command("#cmd x", 0, 4, 6), "spaced #cmd not ambiguous")
        _req(not is_ambiguous_lean4_hash_command("#eval(1)", 0, 5, 8), "#eval(1) not ambiguous")
        _req(not is_ambiguous_lean4_hash_command("#cmdr x", 0, 4, 7), "r without quote not ambiguous")
        _req(is_ambiguous_lean4_hash_command("#kx'\"'", 0, 3, 6), "glued single quote ambiguous")
        _req(is_ambiguous_lean4_hash_command('#foo"x"', 0, 4, 7), "glued double quote ambiguous")
        _req(is_ambiguous_lean4_hash_command('#kxr"x"', 0, 3, 7), "glued r\" ambiguous")
        _req(is_ambiguous_lean4_hash_command('#kxr#"x"#', 0, 3, 9), "glued r#\" ambiguous")

        # 5. B4: decide +native, decide (config := {native := true}), Grind.BVDecide, and general _native.<tactic>.ax_*
        for label, src in (
            ("d1_decide_plus_native", "theorem t : 1 + 1 = 2 := by decide +native\n"),
            ("d2_decide_config_native", "theorem t : 1 + 1 = 2 := by decide (config := {native := true})\n"),
        ):
            r_d = audit_lean4_source(src)
            _req(
                not r_d["clean"] and "LEAN4_DECIDE_NATIVE" in {f["code"] for f in r_d["findings"]},
                f"B4 {label} missed LEAN4_DECIDE_NATIVE: {r_d}",
            )

        for mod_g in ("Lean.Elab.Tactic.Grind.BVDecide", "Lean.Meta.Tactic.Grind.BVDecide"):
            _req(is_bv_decide_module(mod_g), f"Grind.BVDecide module missed: {mod_g}")
            r_gi = audit_lean4_source(f"import {mod_g}\ntheorem ok : True := trivial\n", allow_non_init_imports=True)
            _req(
                not r_gi["clean"] and [f["code"] for f in r_gi["findings"]] == ["LEAN4_BV_DECIDE_IMPORT"],
                f"Grind.BVDecide import missed: {r_gi}",
            )
            r_gr = audit_lean4_source(f"def x := {mod_g}.foo\n")
            _req(
                not r_gr["clean"] and "LEAN4_BV_DECIDE_REF" in {f["code"] for f in r_gr["findings"]},
                f"Grind.BVDecide ref missed: {r_gr}",
            )

        for ax_src in (
            "def a := t._native.decide.ax_1_1\n",
            "def b := _native.grind.ax_0\n",
            "def c := foo.«_native».«decide».ax_2\n",
        ):
            r_na = audit_lean4_source(ax_src)
            _req(
                not r_na["clean"] and "LEAN4_NATIVE_AXIOM" in {f["code"] for f in r_na["findings"]},
                f"general native axiom missed in {ax_src!r}: {r_na}",
            )
        log_native_hits = scan_lean4_axiom_log_text(
            "'t' depends on axioms: [t._native.decide.ax_1_1]\n"
            "'u' depends on axioms: [_native.grind.ax_0]\n"
            "'v' depends on axioms: [Lean.ofReduceNat]\n"
        )
        _req(
            [h["code"] for h in log_native_hits]
            == ["LEAN4_NATIVE_AXIOM", "LEAN4_NATIVE_AXIOM", "LEAN4_OF_REDUCE_NAT"],
            f"general native axiom log rules mismatch: {log_native_hits}",
        )

        # 6. Explicit import guard regression tests (kills audit_check.py M036 & M037)
        r_forb_exact = audit_lean4_source(
            "import Challenge.Spec\n", allow_non_init_imports=True, forbidden_import_prefixes=["Challenge.Spec"]
        )
        _req(
            [f["code"] for f in r_forb_exact["findings"]] == ["LEAN4_FORBIDDEN_CHALLENGE_IMPORT"],
            f"exact forbidden prefix missed: {r_forb_exact}",
        )
        r_forb_sub = audit_lean4_source(
            "import Challenge.Spec.Helper\n", allow_non_init_imports=True, forbidden_import_prefixes=["Challenge.Spec"]
        )
        _req(
            [f["code"] for f in r_forb_sub["findings"]] == ["LEAN4_FORBIDDEN_CHALLENGE_IMPORT"],
            f"child forbidden prefix missed: {r_forb_sub}",
        )
        r_forb_other = audit_lean4_source(
            "import Challenge.SpecExtra\n", allow_non_init_imports=True, forbidden_import_prefixes=["Challenge.Spec"]
        )
        _req(r_forb_other["clean"], f"sibling prefix falsely flagged as forbidden: {r_forb_other}")

        r_proj_ok = audit_lean4_source(
            "import Init\nimport Std.Data.HashMap\nimport MyProj\nimport MyProj.Sub\n",
            allow_project_imports=["MyProj"],
        )
        _req(r_proj_ok["clean"], f"allowed project imports falsely flagged: {r_proj_ok}")
        r_proj_bad = audit_lean4_source(
            "import MyProjExtra\nimport Mathlib.Data.Nat\n",
            allow_project_imports=["MyProj"],
        )
        _req(
            [(f["line"], f["code"]) for f in r_proj_bad["findings"]]
            == [(1, "LEAN4_NON_INIT_IMPORT"), (2, "LEAN4_NON_INIT_IMPORT")],
            f"non-allowed imports missed: {r_proj_bad}",
        )

    def test_08_lakefile_toml_require_parsing_decoys_and_invalid(self) -> None:
        """Issue #122: `lakefile.toml` `require` parser, comment/string decoys, and fail-closed errors."""
        # 1. Clean zero-dependency lakefile.toml + comment/string/nested-table decoys -> 0 requires
        clean_toml = (
            'name = "PureInitProj"\n'
            'defaultTargets = ["PureInitProj"]\n'
            'description = "[[require]]\\nname = \'decoy_in_str\'"\n'
            '# [[require]]\n'
            '# name = "decoy_in_comment"\n'
            '\n'
            '[[lean_lib]]\n'
            'name = "PureInitProj"\n'
            '\n'
            '[other_section]\n'
            'require = [{ name = "nested_decoy" }]\n'
        )
        r_clean = parse_lakefile_toml_requires(clean_toml)
        _req(r_clean["valid"] and r_clean["requires"] == [] and r_clean["findings"] == [], f"clean toml failed: {r_clean}")

        r_empty_req = parse_lakefile_toml_requires('name = "Proj"\nrequire = []\n')
        _req(r_empty_req["valid"] and r_empty_req["requires"] == [], f"empty require list failed: {r_empty_req}")

        # N2: UTF-8 BOM in lakefile.toml string is cleanly accepted
        r_bom_toml = parse_lakefile_toml_requires('\ufeffname = "Proj"\n[[require]]\nname = "bom_pkg"\n')
        _req(
            r_bom_toml["valid"] and [d["name"] for d in r_bom_toml["requires"]] == ["bom_pkg"],
            f"UTF-8 BOM toml require failed: {r_bom_toml}",
        )

        # 2. All valid TOML `require` forms (array-of-tables, single/multiline/unicode strings, inline array)
        multi_toml = (
            'name = "DepProj"\n'
            '\n'
            '[[require]]\n'
            'name = "batteries"\n'
            'scope = "leanprover-community"\n'
            'rev = "v4.36.0"\n'
            '\n'
            '[[require]]\n'
            "'name' = 'aesop'\n"
            '\n'
            '[[require]]\n'
            'name = """\\u006dathlib"""\n'
        )
        r_multi = parse_lakefile_toml_requires(multi_toml)
        _req(
            r_multi["valid"]
            and [d["name"] for d in r_multi["requires"]] == ["batteries", "aesop", "mathlib"]
            and r_multi["requires"][0]["line"] == 4
            and r_multi["requires"][1]["line"] == 9
            and r_multi["requires"][2]["line"] == 11,
            f"multi toml requires failed: {r_multi}",
        )

        r_inline = parse_lakefile_toml_requires('name = "Inline"\nrequire = [{ name = "qq", git = "https://example.invalid/qq" }]\n')
        _req(
            r_inline["valid"] and [d["name"] for d in r_inline["requires"]] == ["qq"] and r_inline["requires"][0]["line"] == 2,
            f"inline toml require failed: {r_inline}",
        )

        # 3. Malformed / hostile lakefile.toml payloads -> LEAN4_LAKEFILE_INVALID
        bad_tomls = [
            ("syntax_err", "[[require]\nname = 'broken'\n"),
            ("dup_key", 'name = "a"\n[[require]]\nname = "x"\nname = "y"\n'),
            ("require_str", 'name = "a"\nrequire = "mathlib"\n'),
            ("require_table", 'name = "a"\n[require]\nname = "mathlib"\n'),
            ("entry_not_table", 'name = "a"\nrequire = ["mathlib"]\n'),
            ("missing_name", 'name = "a"\n[[require]]\ngit = "https://example.invalid/repo"\n'),
            ("empty_name", 'name = "a"\n[[require]]\nname = ""\n'),
            ("blank_name", 'name = "a"\n[[require]]\nname = "   "\n'),
            ("padded_name", 'name = "a"\n[[require]]\nname = " mathlib "\n'),
            ("int_name", 'name = "a"\n[[require]]\nname = 42\n'),
            ("deep_nested_recursion_dos", "a = " + ("[" * 2000) + ("]" * 2000) + "\n"),
        ]
        for label, payload in bad_tomls:
            r_bad = parse_lakefile_toml_requires(payload)
            _req(
                not r_bad["valid"]
                and [f["code"] for f in r_bad["findings"]] == ["LEAN4_LAKEFILE_INVALID"],
                f"invalid toml {label!r} did not fail closed: {r_bad}",
            )

        # 4. Disk-level audit_lean4_lakefile fail-closed checks + UTF-8 BOM (`N2`)
        with tempfile.TemporaryDirectory(prefix="aletheia_lf_toml_") as td:
            root = Path(td)
            good_lf = root / "lakefile.toml"
            _write_lf(good_lf, clean_toml)
            _req(audit_lean4_lakefile(good_lf)["valid"], "good lakefile.toml failed")

            bom_lf = root / "bom_lakefile.toml"
            bom_lf.write_bytes(b'\xef\xbb\xbfname = "Proj"\n[[require]]\nname = "bom_dep"\n')
            r_bom_disk = audit_lean4_lakefile(bom_lf)
            _req(
                r_bom_disk["valid"] and [d["name"] for d in r_bom_disk["requires"]] == ["bom_dep"],
                f"UTF-8 BOM lakefile.toml on disk failed: {r_bom_disk}",
            )

            bom_lean = root / "bom_lakefile.lean"
            bom_lean.write_bytes(b'\xef\xbb\xbfimport Lake\nopen Lake DSL\nrequire bom_lean_dep\n')
            r_bom_lean = audit_lean4_lakefile(bom_lean)
            _req(
                r_bom_lean["valid"] and [d["name"] for d in r_bom_lean["requires"]] == ["bom_lean_dep"],
                f"UTF-8 BOM lakefile.lean on disk failed: {r_bom_lean}",
            )

            r_miss = audit_lean4_lakefile(root / "missing.toml")
            _req(not r_miss["valid"] and r_miss["findings"][0]["code"] == "LEAN4_LAKEFILE_INVALID", "missing lakefile")

            dir_lf = root / "dir_lakefile.toml"
            dir_lf.mkdir()
            r_dir = audit_lean4_lakefile(dir_lf)
            _req(not r_dir["valid"] and r_dir["findings"][0]["code"] == "LEAN4_LAKEFILE_INVALID", "dir lakefile")

            sym_lf = root / "sym_lakefile.toml"
            os.symlink(good_lf, sym_lf)
            r_sym = audit_lean4_lakefile(sym_lf)
            _req(not r_sym["valid"] and r_sym["findings"][0]["code"] == "LEAN4_LAKEFILE_INVALID", "symlink lakefile")

            bad_utf8 = root / "bad_utf8.toml"
            bad_utf8.write_bytes(b"\xff\xfename = 'x'\n")
            r_utf = audit_lean4_lakefile(bad_utf8)
            _req(not r_utf["valid"] and r_utf["findings"][0]["code"] == "LEAN4_LAKEFILE_INVALID", "bad utf8 lakefile")

            bad_ext = root / "lakefile.txt"
            _write_lf(bad_ext, 'name = "x"\n')
            r_ext = audit_lean4_lakefile(bad_ext)
            _req(not r_ext["valid"] and r_ext["findings"][0]["code"] == "LEAN4_LAKEFILE_INVALID", "bad ext lakefile")

            if hasattr(os, "mkfifo"):
                fifo_lf = root / "fifo_lakefile.toml"
                os.mkfifo(fifo_lf)
                r_fifo = audit_lean4_lakefile(fifo_lf)
                _req(not r_fifo["valid"] and r_fifo["findings"][0]["code"] == "LEAN4_LAKEFILE_INVALID", "fifo lakefile")

    def test_09_lakefile_lean_require_parsing_decoys_and_evasions(self) -> None:
        """Issue #122: `lakefile.lean` `require` parser, comment/string decoys, and adversarial evasions."""
        # 1. Clean lakefile.lean with comment, nested block comment, doc comment, string, raw string,
        #    interpolated string, char literal, dot-projection, and non-command identifier decoys -> 0 requires
        decoy_lean = "\n".join([
            "import Lake",
            "open Lake DSL",
            "-- require commented_out from git \"https://example.invalid/a\"",
            "/- require block_commented from git \"https://example.invalid/b\" -/",
            "/- outer /- nested require nested_comment -/ still require outer_comment -/",
            "/-- doc comment mentioning require doc_decoy -/",
            "/- /--/ -/",
            'def note1 : String := "require in_string from git \\"https://example.invalid\\""',
            'def note2 : String := "escapes \\n\\r\\t\\\'\\\\\\x41\\u0042\\q\\\nline2"',
            'def note3 : String := r"require in_raw_str"',
            'def note4 : String := r#"require in_hashed_raw_str"#',
            'def note5 : String := s!"require in_interp_str {1 + 2} still require"',
            'def note5b : String := s! "hi {1 + 2}"',
            'def note5c : String := s! /- c -/ "hi {1 + 2}"',
            'def note5d : String := s! "{let _ := "}"; 0}"',
            'def note6 : String := s!"nested {({ a := 1 })} and {s!"{2}"}"',
            'def ver : String := v!"0.1.0"',
            'def msg : String := logInfo "plain build notice"',
            'def nonstr_bang := foo! 123',
            'def after_nonstr_bang : String := "{"',
            'def dot_bang := obj.foo! "{"',
            "def c1 : Char := '\"'",
            "def my_require : Nat := 1",
            "def require_helper : Nat := 2",
            "def require : Nat := 3",
            "def «require» (x : Nat) : Nat := x",
            "«require» arg_decoy",
            "def «macro» : Nat := 4",
            "def proj := obj.require arg",
            "def proj_meta := obj.syntax",
            "def qname := `Foo.Bar",
            "def paren (require : Nat) : Nat := (require)",
            "def brack := [1, 2]",
            "def brace := { a := 1 }",
            "def prime_id := foo'",
            "def bang_ident := s!a",
            "def prime_bang_ident := f!'a",
            "def num_id := 0x10",
            "@[default_target]",
            "lean_lib CleanLib",
            "def tail_at := @",
        ]) + "\n"
        r_decoy = parse_lakefile_lean_requires(decoy_lean)
        _req(
            r_decoy["valid"] and r_decoy["requires"] == [] and r_decoy["findings"] == [],
            f"false positive on lakefile.lean decoys: {r_decoy}",
        )
        # Adjacent dot-projection at exact token index 2 (`obj.require arg`) -> 0 requires (kills M034)
        r_dot2 = parse_lakefile_lean_requires("obj.require arg\n")
        _req(r_dot2["valid"] and r_dot2["requires"] == [], f"dot-projection at idx 2 failed: {r_dot2}")

        # N1: deeply nested block comments (2000 levels) must not hit RecursionError
        deep_comment_lean = ("/- " * 2000) + "require hidden " + ("-/ " * 2000) + "require after_deep_comment\n"
        r_deep = parse_lakefile_lean_requires(deep_comment_lean)
        _req(
            r_deep["valid"] and [d["name"] for d in r_deep["requires"]] == ["after_deep_comment"],
            f"deeply nested block comment failed: {r_deep}",
        )

        # N2: UTF-8 BOM in lakefile.lean string is cleanly accepted
        r_bom_lean_s = parse_lakefile_lean_requires("\ufeffimport Lake\nrequire bom_str_dep\n")
        _req(
            r_bom_lean_s["valid"] and [d["name"] for d in r_bom_lean_s["requires"]] == ["bom_str_dep"],
            f"UTF-8 BOM lakefile.lean string failed: {r_bom_lean_s}",
        )

        # 2. All valid Lean 4 Lake DSL `require` forms + tricky lexing contexts
        all_forms_lean = "\n".join([
            "import Lake",
            "open Lake DSL",
            'require mathlib from git "https://example.invalid/mathlib4.git"',
            'require «batteries-4» from git "https://example.invalid/batteries" @ "v4.36.0"',
            'require«zero-ws» from "../local"',
            'require "str-pkg" from "../str_dep"',
            'require r"raw-pkg" from "../raw_dep"',
            'require r#"raw-scope"# / r#"raw-scoped-pkg"#',
            'require "\\u0065sc\\x61ped" from "../esc_dep"',
            'require "leanprover-community" / "proofwidgets" @ git "v0.0.40"',
            'require "leanprover-community" / aesop @ git "v4.36.0"',
            'require "leanprover-community" / «doc-gen4»',
            'require "scope-ns"/"tight_slash"',
            'require Foo.Bar from "../dotted"',
            "require",
            '  "multi-scope" /',
            '  "multi-pkg"',
            '  @ "v1.0.0"',
            'meta if get_config? env = some "dev" then',
            '  require cond_dep from git "https://example.invalid/cond"',
            "def x := 1; require semi_dep",
            "section",
            "require in_section_dep",
            "end",
            "require after_end_dep",
            "def q : Char := '\"'",
            "require after_char",
            "#check'\"'",
            "require after_hash_char",
            "-- \"",
            'def s_ch := s!"{\'"\'}"',
            "require after_interp_char",
            "-- \"",
            'def s_br := s!"{let _ := "}"; 0}"',
            "require after_interp_brace",
            "def «/-» : Nat := 1",
            "require after_guil_comment",
            "def «-/» : Nat := 2",
            'def «a"» : Nat := 1',
            "require after_guil_str",
            'def «b"» : Nat := 2',
            # H1: /--/ and /-!/ 3-char doc comment openers must NOT close early on -/ and swallow require!
            '/--/ " -/',
            'require after_doc_slash from git "https://example.invalid/doc"',
            '/- " -/',
            '/-!/ " -/',
            'require after_mod_doc_slash from git "https://example.invalid/mdoc"',
            '/- " -/',
            # H3: dotted keyword `Foo.fun` & trailing numeric dot `1.` must NOT exempt next-line require!
            "def Foo.fun := 1",
            "#check Foo.fun",
            'require after_dotted_kw from git "https://example.invalid/dotkw"',
            "def num_dot := 1.",
            'require after_num_dot from git "https://example.invalid/numdot"',
            # H4: guillemet and `!`/`?`-suffixed ident before char-quote `'"'` must NOT desync string scanning!
            "def c_guil := «a»'\"'",
            'require after_guil_char_quote from git "https://example.invalid/gcq"',
            '-- "',
            "def c_bang := g!'\"'",
            'require after_bang_char_quote from git "https://example.invalid/bcq"',
            '-- "',
            "def c_qmark := g?'\"'",
            'require after_qmark_char_quote from git "https://example.invalid/qcq"',
            '-- "',
            "def c_op_bang := !'\"'",
            'require after_op_bang_char_quote from git "https://example.invalid/obcq"',
            '-- "',
            # DELTA3: Lean 4 `isIdRest` keeps `!`/`?`/`'` inside a single identifier (`a!def`, `a!open`,
            # `a?def`, `f!'a'def`) and `prev_is_decl_kw` only exempts same-line non-projected binders!
            "def a!def := 1",
            "def x1 := a!def",
            "require after_a_bang_def",
            "def a!open := 1",
            "def x2 := a!open",
            "require after_a_bang_open",
            "def a?def := 1",
            "def x3 := a?def",
            "require after_a_qmark_def",
            "def f!'a'def := 1",
            "def x4 := f!'a'def",
            "require after_f_bang_prime_def",
            "def",
            "require after_cross_line_def",
            "open require after_open_kw",
            "Foo.fun require after_same_line_dot_kw",
            # H2: imported custom operator shifting delimiter depth must NOT suppress require!
            "def op1 := 1 (* 2",
            'require inside_imported_op from git "https://example.invalid/op"',
            "def op2 := 1 )* 2",
            "require bare_eof",
        ]) + "\n"
        r_forms = parse_lakefile_lean_requires(all_forms_lean)
        got_names = [d["name"] for d in r_forms["requires"]]
        want_names = [
            "mathlib",
            "batteries-4",
            "zero-ws",
            "str-pkg",
            "raw-pkg",
            "raw-scoped-pkg",
            "escaped",
            "proofwidgets",
            "aesop",
            "doc-gen4",
            "tight_slash",
            "Foo.Bar",
            "multi-pkg",
            "cond_dep",
            "semi_dep",
            "in_section_dep",
            "after_end_dep",
            "after_char",
            "after_hash_char",
            "after_interp_char",
            "after_interp_brace",
            "after_guil_comment",
            "after_guil_str",
            "after_doc_slash",
            "after_mod_doc_slash",
            "after_dotted_kw",
            "after_num_dot",
            "after_guil_char_quote",
            "after_bang_char_quote",
            "after_qmark_char_quote",
            "after_op_bang_char_quote",
            "after_a_bang_def",
            "after_a_bang_open",
            "after_a_qmark_def",
            "after_f_bang_prime_def",
            "after_cross_line_def",
            "after_open_kw",
            "after_same_line_dot_kw",
            "inside_imported_op",
            "bare_eof",
        ]
        _req(
            r_forms["valid"] and got_names == want_names,
            f"lakefile.lean require parsing mismatch:\n  got ={got_names}\n  want={want_names}\n  res ={r_forms}",
        )

        # 3. Malformed / hostile lakefile.lean payloads, B1 metaprogramming/quotations, B2 unbalanced
        #    delimiters, N4 ambiguous custom `!`/interp strings, & forbidden attributes -> LEAN4_LAKEFILE_INVALID
        bad_leans = [
            ("unclosed_block_comment", "/- unclosed comment\nrequire x\n"),
            ("unclosed_nested_comment", "/- a /- b -/\n"),
            ("unclosed_str", 'def x := "unclosed\n'),
            ("unclosed_str_bs", 'def x := "abc\\'),
            ("unclosed_guil", "def «unclosed := 1\n"),
            ("unclosed_raw_str", 'def x := r#"unclosed"\n'),
            ("unclosed_interp_str", 'def x := s!"unclosed\n'),
            ("unclosed_interp_brace", 'def x := s!"{1 + 2\n'),
            ("truncated_scoped_eof", 'require "scope" /\n'),
            ("truncated_scoped_num", 'require "scope" / 123\n'),
            ("empty_str_name", 'require "" from "../x"\n'),
            ("blank_str_name", 'require "   " from "../x"\n'),
            ("padded_str_name", 'require " mathlib " from "../x"\n'),
            ("empty_scoped_name", 'require "scope" / ""\n'),
            ("raw_package_dep_attr", "@[package_dep]\ndef evil : Dependency := {}\n"),
            ("raw_package_dep_qual", "@[Lake.package_dep]\ndef evil : Dependency := {}\n"),
            ("raw_package_dep_multi", "@[inline, package_dep]\ndef evil : Dependency := {}\n"),
            ("raw_package_dep_post", "attribute [local, package_dep] evil\n"),
            ("raw_package_dep_guil", "attribute [«package_dep»] evil\n"),
            ("attr_init", "@[init]\ndef evil : IO Unit := pure ()\n"),
            ("attr_builtin_init", "@[builtin_init]\ndef evil : IO Unit := pure ()\n"),
            ("attr_macro", "@[macro foo]\ndef evil := 1\n"),
            ("attr_command_elab", "attribute [command_elab foo] evil\n"),
            ("attr_term_elab", "@[term_elab foo]\ndef evil := 1\n"),
            ("attr_tactic", "@[tactic foo]\ndef evil := 1\n"),
            ("attr_extern", '@[extern "pwn"]\ndef evil : Nat := 1\n'),
            ("attr_implemented_by", "@[implemented_by foo]\ndef evil : Nat := 1\n"),
            ("attr_guil_kw", "«attribute» [package_dep] evil\n"),
            ("attr_unbalanced", "@[default_target\nrequire evil\n"),
            # B1 / H2 / H4: Metaprogramming, custom operators, `#eval`, `register_*`, & syntax quotations
            (
                "b1_macro_require_quotation",
                'import Lake\nopen Lake DSL\nmacro "mydep" : command => `(require mathlib from git "https://example.invalid/m")\nmydep\n',
            ),
            ("b1_macro_rules", "macro_rules | x => x\n"),
            ("b1_elab", 'elab "mydep" : command => pure ()\n'),
            ("b1_elab_rules", "elab_rules | x => pure ()\n"),
            ("b1_syntax", 'syntax "mydep" : command\n'),
            ("h2_declare_syntax_cat", "declare_syntax_cat mycat\n"),
            ("b1_notation", 'notation "mydep" => 1\n'),
            ("h2_infixl_op", 'infixl:65 "(*" => fun a b => a + b\n'),
            ("h2_prefix_op", 'prefix:65 "!!" => id\n'),
            ("h2_register_attr", "register_simp_attr my_simp\n"),
            ("h2_macro_inside_parens", '(macro "m" : command => pure ())\n'),
            ("b1_run_cmd", "run_cmd pure ()\n"),
            ("b1_run_elab", "run_elab pure ()\n"),
            ("h4_run_meta", "run_meta pure ()\n"),
            ("h4_hash_eval", '#eval IO.println "pwn"\n'),
            ("h4_hash_eval_bang", '#eval! IO.println "pwn"\n'),
            ("h4_hash_run_cmd", "#run_cmd pure ()\n"),
            ("b1_initialize", "initialize x : IO.Ref Nat ← IO.mkRef 0\n"),
            ("b1_builtin_initialize", "builtin_initialize x : IO.Ref Nat ← IO.mkRef 0\n"),
            ("b1_standalone_quotation", 'def helper := `(require evil from git "https://example.invalid/e")\n'),
            ("b1_nested_quotation", 'def helper := (`(require evil))\n'),
            # B2 / L1: Unbalanced & interleaved delimiters + bare malformed require
            ("b2_unclosed_paren", 'def helper := (1\nrequire evil from git "https://example.invalid/evil"\n'),
            ("b2_unclosed_brack", 'def helper := [1\nrequire evil from git "https://example.invalid/evil"\n'),
            ("b2_unclosed_brace", 'def helper := { a := 1\nrequire evil from git "https://example.invalid/evil"\n'),
            ("b2_extra_rparen", "def helper := 1)\n"),
            ("b2_extra_rbrack", "def helper := 1]\n"),
            ("b2_extra_rbrace", "def helper := 1}\n"),
            ("b2_reversed_parens", "def helper := )(\n"),
            ("b2_reversed_bracks", "def helper := ][\n"),
            ("b2_reversed_braces", "def helper := }{\n"),
            ("l1_interleaved_delims", "def helper := ([)]\n"),
            ("l1_bare_require_num", "require 123\n"),
            ("l1_bare_require_eof", "require\n"),
            ("b2_interp_brace_symmetry", 'def s := s!"{1}" }\n'),
            # N4: Ambiguous non-builtin `!` / interpolated string prefixes with `{` or `}`
            (
                "n4_custom_bang_desync",
                'def x := foo!"{ let s := "{"; 0 }"\n'
                'require evil from git "https://example.invalid/e"\n'
                'def y := foo!"{ let s := "}"; 0 }"\n',
            ),
            ("n4_m_bang_lbrace", 'def m_fake := m! "{"\nrequire evil\n-- "}"\n'),
            ("n4_custom_bang_rbrace", 'def y := foo!"plain } brace"\n'),
            ("n4_v_bang_brace", 'def v := v!"{0.1.0}"\n'),
            ("n4_loginfo_brace", 'def l := logInfo "{evil}"\n'),
            ("n4_dbg_trace_brace", 'def d := dbg_trace "{"\n'),
            ("delta3_a_bang_r_str", 'def x := a!r"\\"\nrequire evil\n'),
            ("delta3_s_bang_bang_brace", 'def x := s!!"{evil}"\n'),
        ]
        for label, src in bad_leans:
            r_bad = parse_lakefile_lean_requires(src)
            _req(
                not r_bad["valid"]
                and any(f["code"] == "LEAN4_LAKEFILE_INVALID" for f in r_bad["findings"]),
                f"hostile lakefile.lean {label!r} did not fail with LEAN4_LAKEFILE_INVALID: {r_bad}",
            )

        # Standalone exact DELTA2 reproducer checks (`a!def`, `a!open`, `a?def` followed by `\nrequire evil`)
        for ident_name in ("a!def", "a!open", "a?def"):
            repro = f"import Lake\nopen Lake DSL\ndef {ident_name} := 1\ndef x := {ident_name}\nrequire evil\n"
            r_repro = parse_lakefile_lean_requires(repro)
            _req(
                r_repro["valid"] and [d["name"] for d in r_repro["requires"]] == ["evil"],
                f"DELTA2 reproducer {ident_name!r} failed: {r_repro}",
            )

    def test_10_lakefile_manifest_cross_check_end_to_end(self) -> None:
        """Issue #122 end-to-end: unmanifested requires in lakefile.{toml,lean}, missing manifest, manifested PASS, and decoys."""
        with tempfile.TemporaryDirectory(prefix="aletheia_issue122_") as td:
            base = Path(td)

            # 1. Unmanifested require in lakefile.toml with NO lake-manifest.json -> FAIL (CLI + API, both allow modes)
            p_toml_nomf = base / "toml_no_manifest"
            _write_lf(p_toml_nomf / "Main.lean", "import Init\ntheorem ok : True := trivial\n")
            _write_lf(
                p_toml_nomf / "lakefile.toml",
                'name = "Proj"\n[[require]]\nname = "mathlib"\ngit = "https://example.invalid/mathlib4.git"\n',
            )
            rc1, out1, _ = _run_cli(["audit-check", str(p_toml_nomf), "--lean-audit", "--json"])
            obj1 = parse_strict_json_text(out1)
            _req(
                rc1 == 1
                and not obj1["passed"]
                and obj1["lean_audit"]["lakefiles_checked"] == 1
                and obj1["lean_audit"]["manifests_checked"] == 0
                and any(
                    f["code"] == "LEAN4_LAKEFILE_MISSING_MANIFEST" and "mathlib" in f["excerpt"]
                    for f in obj1["lean_audit"]["findings"]
                ),
                f"unmanifested toml require (no manifest) missed via CLI: {obj1['lean_audit']}",
            )
            r1_allow = audit_lean4_directory(p_toml_nomf, allow_external_packages=True)
            _req(
                not r1_allow["clean"]
                and [f["code"] for f in r1_allow["findings"]] == ["LEAN4_LAKEFILE_MISSING_MANIFEST"],
                f"missing manifest must fail even with allow_external_packages=True: {r1_allow}",
            )

            # 2. Unmanifested require in lakefile.lean with NO lake-manifest.json -> FAIL (CLI + API)
            p_lean_nomf = base / "lean_no_manifest"
            _write_lf(p_lean_nomf / "Main.lean", "import Init\ntheorem ok : True := trivial\n")
            _write_lf(
                p_lean_nomf / "lakefile.lean",
                'import Lake\nopen Lake DSL\nrequire "leanprover-community" / "mathlib" @ git "v4.36.0"\n',
            )
            rc2, out2, _ = _run_cli(["audit-check", str(p_lean_nomf), "--lean-audit", "--json"])
            obj2 = parse_strict_json_text(out2)
            _req(
                rc2 == 1
                and not obj2["passed"]
                and any(
                    f["code"] == "LEAN4_LAKEFILE_MISSING_MANIFEST" and "mathlib" in f["excerpt"]
                    for f in obj2["lean_audit"]["findings"]
                ),
                f"unmanifested lakefile.lean require (no manifest) missed via CLI: {obj2['lean_audit']}",
            )
            r2_allow = audit_lean4_directory(p_lean_nomf, allow_non_init_imports=True, allow_external_packages=True)
            _req(
                not r2_allow["clean"]
                and [f["code"] for f in r2_allow["findings"]] == ["LEAN4_LAKEFILE_MISSING_MANIFEST"],
                f"lakefile.lean missing manifest failed check: {r2_allow}",
            )

            # 3. Unmanifested require in lakefile.toml when lake-manifest.json has `packages: []` -> FAIL
            p_toml_empty_mf = base / "toml_empty_manifest"
            _write_lf(p_toml_empty_mf / "Main.lean", "theorem ok : True := trivial\n")
            _write_lf(p_toml_empty_mf / "lakefile.toml", 'name = "P"\n[[require]]\nname = "batteries"\n')
            _write_lf(p_toml_empty_mf / "lake-manifest.json", '{"version": "1.1.0", "packages": []}\n')
            rc3, out3, _ = _run_cli(["audit-check", str(p_toml_empty_mf), "--lean-audit", "--json"])
            obj3 = parse_strict_json_text(out3)
            _req(
                rc3 == 1
                and not obj3["passed"]
                and [f["code"] for f in obj3["lean_audit"]["findings"]] == ["LEAN4_LAKEFILE_UNMANIFESTED_REQUIRE"]
                and "batteries" in obj3["lean_audit"]["findings"][0]["excerpt"],
                f"empty manifest vs toml require failed: {obj3['lean_audit']}",
            )

            # 4. Partial manifest (lists `batteries` but omits `mathlib`) in lakefile.toml & lakefile.lean
            p_partial = base / "partial_manifest"
            _write_lf(p_partial / "Main.lean", "theorem ok : True := trivial\n")
            _write_lf(
                p_partial / "lakefile.toml",
                'name = "P"\n[[require]]\nname = "batteries"\n[[require]]\nname = "mathlib"\n',
            )
            _write_lf(
                p_partial / "lake-manifest.json",
                '{"version": "1.1.0", "packages": [{"name": "batteries", "type": "git"}]}\n',
            )
            r4_allow = audit_lean4_directory(p_partial, allow_external_packages=True)
            _req(
                not r4_allow["clean"]
                and [f["code"] for f in r4_allow["findings"]] == ["LEAN4_LAKEFILE_UNMANIFESTED_REQUIRE"]
                and "mathlib" in r4_allow["findings"][0]["excerpt"]
                and "batteries" not in r4_allow["findings"][0]["excerpt"],
                f"partial manifest allow_external check failed: {r4_allow}",
            )
            r4_strict = audit_lean4_directory(p_partial, allow_external_packages=False)
            _req(
                not r4_strict["clean"]
                and {f["code"] for f in r4_strict["findings"]}
                == {"LEAN4_LAKE_MANIFEST_NONEMPTY_PACKAGES", "LEAN4_LAKEFILE_UNMANIFESTED_REQUIRE"},
                f"partial manifest strict check failed: {r4_strict}",
            )

            # 5. Corrupt lake-manifest.json + declared require -> BOTH manifest invalid & require unverified
            p_corrupt = base / "corrupt_manifest"
            _write_lf(p_corrupt / "Main.lean", "theorem ok : True := trivial\n")
            _write_lf(p_corrupt / "lakefile.toml", 'name = "P"\n[[require]]\nname = "mathlib"\n')
            _write_lf(p_corrupt / "lake-manifest.json", "{corrupt\n")
            r5 = audit_lean4_directory(p_corrupt, allow_external_packages=True)
            _req(
                not r5["clean"]
                and {f["code"] for f in r5["findings"]}
                == {"LEAN4_LAKE_MANIFEST_INVALID", "LEAN4_LAKEFILE_UNMANIFESTED_REQUIRE"},
                f"corrupt manifest with declared require failed: {r5}",
            )

            # 6. Valid manifested requires (PASS under allow_external_packages=True for BOTH .toml and .lean!)
            p_valid_toml = base / "valid_manifested_toml"
            _write_lf(p_valid_toml / "Main.lean", "import Init\ntheorem ok : True := trivial\n")
            _write_lf(
                p_valid_toml / "lakefile.toml",
                'name = "P"\n[[require]]\nname = "batteries"\ngit = "https://example.invalid/batteries"\n',
            )
            _write_lf(
                p_valid_toml / "lake-manifest.json",
                '{"version": "1.1.0", "packages": [{"name": "batteries", "type": "git"}]}\n',
            )
            r6_toml_ok = audit_lean4_directory(p_valid_toml, allow_external_packages=True)
            _req(
                r6_toml_ok["clean"]
                and r6_toml_ok["findings"] == []
                and r6_toml_ok["lakefiles_checked"] == 1
                and r6_toml_ok["manifests_checked"] == 1,
                f"valid manifested lakefile.toml should PASS with allow_external_packages=True: {r6_toml_ok}",
            )
            r6_toml_strict = audit_lean4_directory(p_valid_toml, allow_external_packages=False)
            _req(
                not r6_toml_strict["clean"]
                and [f["code"] for f in r6_toml_strict["findings"]] == ["LEAN4_LAKE_MANIFEST_NONEMPTY_PACKAGES"],
                f"manifested require in strict zero-dep mode should flag only nonempty manifest: {r6_toml_strict}",
            )

            p_valid_lean = base / "valid_manifested_lean"
            _write_lf(p_valid_lean / "Main.lean", "import Init\ntheorem ok : True := trivial\n")
            _write_lf(
                p_valid_lean / "lakefile.lean",
                "import Lake\n"
                "open Lake DSL\n"
                'package myproj where\n  version := v!"0.1.0"\n'
                'require batteries from git "https://example.invalid/batteries" @ "v4.36.0"\n'
                'require "leanprover-community" / "mathlib" @ git "v4.36.0"\n',
            )
            _write_lf(
                p_valid_lean / "lake-manifest.json",
                '{"version": "1.1.0", "packages": [{"name": "batteries"}, {"name": "mathlib"}]}\n',
            )
            r6_lean_ok = audit_lean4_directory(p_valid_lean, allow_non_init_imports=True, allow_external_packages=True)
            _req(
                r6_lean_ok["clean"]
                and r6_lean_ok["findings"] == []
                and r6_lean_ok["lakefiles_checked"] == 1
                and r6_lean_ok["manifests_checked"] == 1,
                f"valid manifested lakefile.lean should PASS with allow flags: {r6_lean_ok}",
            )

            # 7. Commented-out & string-literal require decoys in BOTH .toml and .lean (PASS via CLI, 0 FP!)
            p_decoy = base / "decoy_only_proj"
            _write_lf(p_decoy / "Main.lean", "import Init\ntheorem ok : True := trivial\n")
            _write_lf(
                p_decoy / "lakefile.toml",
                'name = "Decoy"\ndescription = "[[require]]\\nname = \'fake\'"\n# [[require]]\n# name = "commented"\n',
            )
            _write_lf(
                p_decoy / "lakefile.lean",
                'import Init\n-- require commented_out\n/- require block_out -/\ndef s := "require in_str"\n',
            )
            # Also verify `.lake/` buried lakefiles with requires are skipped cleanly
            _write_lf(
                p_decoy / ".lake" / "packages" / "dep" / "lakefile.toml",
                'name = "Ignored"\n[[require]]\nname = "ignored_dep"\n',
            )
            rc7, out7, err7 = _run_cli(["audit-check", str(p_decoy), "--lean-audit", "--json"])
            obj7 = parse_strict_json_text(out7)
            _req(
                rc7 == 0 and obj7["passed"] and obj7["lean_audit"]["clean"] and obj7["lean_audit"]["lakefiles_checked"] == 2,
                f"decoy-only project failed CLI: rc={rc7} err={err7} lean={obj7['lean_audit']}",
            )

            # 8. Nested subdirectory isolation: root manifest does NOT satisfy sub/lakefile.toml
            p_nested = base / "nested_isolation"
            _write_lf(p_nested / "lake-manifest.json", '{"version": "1.1.0", "packages": [{"name": "mathlib"}]}\n')
            _write_lf(p_nested / "sub" / "lakefile.toml", 'name = "Sub"\n[[require]]\nname = "mathlib"\n')
            r8 = audit_lean4_directory(p_nested, allow_external_packages=True)
            _req(
                not r8["clean"]
                and [(f["file"], f["code"]) for f in r8["findings"]]
                == [("sub/lakefile.toml", "LEAN4_LAKEFILE_MISSING_MANIFEST")],
                f"nested lakefile should not borrow parent manifest: {r8}",
            )

            # 9. Single-file mode: Main.lean, lakefile.toml, lakefile.lean, and lake-manifest.json all cross-check siblings
            sf_main = audit_lean4_directory(p_toml_nomf / "Main.lean")
            _req(
                not sf_main["clean"]
                and sf_main["lakefiles_checked"] == 1
                and sf_main["findings"][0]["code"] == "LEAN4_LAKEFILE_MISSING_MANIFEST",
                f"single-file Main.lean missed sibling lakefile.toml: {sf_main}",
            )
            sf_toml = audit_lean4_directory(p_toml_empty_mf / "lakefile.toml")
            _req(
                not sf_toml["clean"]
                and sf_toml["lakefiles_checked"] == 1
                and sf_toml["manifests_checked"] == 1
                and sf_toml["findings"][0]["code"] == "LEAN4_LAKEFILE_UNMANIFESTED_REQUIRE",
                f"single-file lakefile.toml missed sibling manifest cross-check: {sf_toml}",
            )
            sf_mf = audit_lean4_directory(p_toml_empty_mf / "lake-manifest.json")
            _req(
                not sf_mf["clean"]
                and sf_mf["lakefiles_checked"] == 1
                and sf_mf["manifests_checked"] == 1
                and sf_mf["findings"][0]["code"] == "LEAN4_LAKEFILE_UNMANIFESTED_REQUIRE",
                f"single-file lake-manifest.json missed sibling lakefile cross-check: {sf_mf}",
            )
            sf_lean_ok = audit_lean4_directory(
                p_valid_lean / "lakefile.lean", allow_non_init_imports=True, allow_external_packages=True
            )
            _req(
                sf_lean_ok["clean"] and sf_lean_ok["lakefiles_checked"] == 1 and sf_lean_ok["manifests_checked"] == 1,
                f"single-file valid lakefile.lean failed: {sf_lean_ok}",
            )

            # 10. Directory named `lakefile.toml` fails closed with LEAN4_LAKEFILE_INVALID
            p_dir_lf = base / "dir_named_lakefile"
            _write_lf(p_dir_lf / "Ok.lean", "theorem ok : True := trivial\n")
            (p_dir_lf / "lakefile.toml").mkdir()
            r10 = audit_lean4_directory(p_dir_lf)
            _req(
                not r10["clean"] and r10["findings"][0]["code"] == "LEAN4_LAKEFILE_INVALID",
                f"directory named lakefile.toml missed: {r10}",
            )

            # 11. Unreadable subdirectory fails closed (L1: never silently skips os.scandir OSError!)
            if os.geteuid() != 0:
                p_unr = base / "unreadable_subdir_proj"
                _write_lf(p_unr / "Ok.lean", "theorem ok : True := trivial\n")
                locked = p_unr / "locked"
                locked.mkdir()
                _write_lf(locked / "lakefile.toml", 'name = "X"\n[[require]]\nname = "evil"\n')
                os.chmod(locked, 0o000)
                try:
                    r11 = audit_lean4_directory(p_unr)
                    _req(
                        not r11["clean"]
                        and any(f["code"] == "LEAN4_LAKEFILE_INVALID" and f["file"] == "locked" for f in r11["findings"]),
                        f"unreadable subdir did not fail closed: {r11}",
                    )
                finally:
                    os.chmod(locked, 0o700)


if __name__ == "__main__":
    unittest.main()
