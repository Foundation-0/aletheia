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
    audit_lean4_source,
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


if __name__ == "__main__":
    unittest.main()
