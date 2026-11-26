#!/usr/bin/env python3
"""Track S110 Stage 3 (H10c) R5 Adversarial, Mutation-Hardening & Live-Lean Test Suite.

Zero bare asserts (uses unittest assertions only), zero IEEE-754 floats,
zero external dependencies, zero skipped tests across all Python -I / -O / -W error / RO-dir envs.
"""

from __future__ import annotations

import copy
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
import unittest

TRACK_DIR = Path(__file__).resolve().parent
if str(TRACK_DIR) not in sys.path:
    sys.path.insert(0, str(TRACK_DIR))

import s110_geosphere_weft_oracle as oracle
import verify_s110_geosphere_weft_conservation as ver

CERT_PATH = TRACK_DIR / "s110_geosphere_weft_certificate.json"
LEAN_PATH = TRACK_DIR / oracle.LEAN_FILE_NAME
FROZEN_CERT = json.loads(CERT_PATH.read_text(encoding="utf-8"))


def _resign(cert: dict) -> dict:
    p_sha = oracle.sha256_hex(oracle.canonical_json_bytes(cert["payload"]))
    cert["payload_sha256"] = p_sha
    env = {
        "schema_version": cert["schema_version"],
        "track_id": cert["track_id"],
        "payload_sha256": p_sha,
    }
    cert["certificate_sha256"] = oracle.sha256_hex(oracle.canonical_json_bytes(env))
    return cert


def _walk_leaves(obj, path: list, out: list) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            _walk_leaves(v, path + [k], out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _walk_leaves(v, path + [i], out)
    else:
        out.append((path, obj))


def _set_path(obj, path: list, val) -> None:
    cur = obj
    for p in path[:-1]:
        cur = cur[p]
    cur[path[-1]] = val


def _tamper_scalar(val):
    if isinstance(val, bool):
        return not val
    if isinstance(val, int):
        return val + 1
    if isinstance(val, str):
        return val + "_X" if val else "X"
    return "TAMPER"


class Test01OraclePrimitivesAndCLI(unittest.TestCase):
    def test_01_oracle_guards_and_math_primitives(self) -> None:
        oracle.require_ok(True, "OK", "ok")
        with self.assertRaises(oracle.S110OracleError) as cm:
            oracle.require_ok(False, "FAIL_CODE", "fail")
        self.assertEqual(cm.exception.code, "FAIL_CODE")
        self.assertEqual(oracle.require_exact_int(7, "x"), 7)
        with self.assertRaises(oracle.S110OracleError):
            oracle.require_exact_int(True, "bool")
        with self.assertRaises(oracle.S110OracleError):
            oracle.require_exact_int("7", "str")
        self.assertEqual(oracle.require_exact_str("abc", "s"), "abc")
        with self.assertRaises(oracle.S110OracleError):
            oracle.require_exact_str(123, "int")
        self.assertEqual(oracle.q_str(Fraction(5, 1)), "5")
        self.assertEqual(oracle.q_str(Fraction(5, 3)), "5/3")

        with self.assertRaises(oracle.S110OracleError) as cm2:
            oracle.dot_q([Fraction(1)], [Fraction(1), Fraction(2)])
        self.assertEqual(cm2.exception.code, "DIM_MISMATCH")

        self.assertTrue(oracle.is_skew_q([[Fraction(0), Fraction(-2)], [Fraction(2), Fraction(0)]]))
        self.assertFalse(oracle.is_skew_q([[Fraction(0), Fraction(2)], [Fraction(2), Fraction(0)]]))
        self.assertFalse(oracle.is_skew_q([[Fraction(1), Fraction(0)], [Fraction(0), Fraction(0)]]))

        # Exact determinant: singular, row-swap sign flip, and 2x2 non-trivial
        self.assertEqual(oracle.det_exact_q([[Fraction(1), Fraction(2)], [Fraction(2), Fraction(4)]]), 0)
        self.assertEqual(oracle.det_exact_q([[Fraction(0), Fraction(1)], [Fraction(1), Fraction(0)]]), -1)
        self.assertEqual(oracle.det_exact_q([[Fraction(3), Fraction(1)], [Fraction(2), Fraction(5)]]), 13)

        # ReLU, Bingham, and Clip boundaries
        self.assertEqual(oracle.relu_q(Fraction(3)), 3)
        self.assertEqual(oracle.relu_q(Fraction(0)), 0)
        self.assertEqual(oracle.relu_q(Fraction(-3)), 0)
        self.assertEqual(oracle.bingham_q(Fraction(2), Fraction(5)), 3)
        self.assertEqual(oracle.bingham_q(Fraction(2), Fraction(-5)), -3)
        self.assertEqual(oracle.bingham_q(Fraction(2), Fraction(2)), 0)
        self.assertEqual(oracle.bingham_q(Fraction(2), Fraction(-2)), 0)
        self.assertEqual(oracle.clip_q(Fraction(2), Fraction(5)), 2)
        self.assertEqual(oracle.clip_q(Fraction(2), Fraction(2)), 2)
        self.assertEqual(oracle.clip_q(Fraction(2), Fraction(-5)), -2)
        self.assertEqual(oracle.clip_q(Fraction(2), Fraction(-2)), -2)
        self.assertEqual(oracle.clip_q(Fraction(2), Fraction(1)), 1)

        # weft_step_sim boundary: equal anchor_err commits; higher rejects
        st = {
            "core_sha256": "a" * 64,
            "rewriter_sha256": "b" * 64,
            "plate_rev": 0,
            "anchor_err": 10,
            "rewriter_can_emit_text": False,
            "rewriter_can_invoke_tool": False,
        }
        nxt_eq, ok_eq = oracle.weft_step_sim(
            st,
            {"target": "plate", "proposed_plate_rev": 1, "post_anchor_err": 10, "static_ok": True, "receipt_ok": True},
        )
        self.assertTrue(ok_eq)
        self.assertEqual(nxt_eq["plate_rev"], 1)
        nxt_hi, ok_hi = oracle.weft_step_sim(
            st,
            {"target": "plate", "proposed_plate_rev": 2, "post_anchor_err": 11, "static_ok": True, "receipt_ok": True},
        )
        self.assertFalse(ok_hi)
        self.assertEqual(nxt_hi, st)

    def test_02_oracle_main_and_live_cert_parity(self) -> None:
        live = oracle.build_certificate()
        self.assertEqual(live, FROZEN_CERT)
        buf_sum = io.StringIO()
        buf_std = io.StringIO()
        old_out = sys.stdout
        try:
            sys.stdout = buf_sum
            self.assertEqual(oracle.main([]), 0)
            sys.stdout = buf_std
            self.assertEqual(oracle.main(["--standalone", "--json"]), 0)
        finally:
            sys.stdout = old_out
        summary = json.loads(buf_sum.getvalue())
        self.assertEqual(summary["lean_theorems"], 38)
        self.assertEqual(summary["certificate_sha256"], FROZEN_CERT["certificate_sha256"])
        self.assertEqual(buf_std.getvalue().encode("utf-8"), CERT_PATH.read_bytes())


class Test02ZoneBIOAndStrictJSON(unittest.TestCase):
    def test_03_regular_file_io_and_atomic_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="s110_io_") as td:
            d = Path(td)
            f = d / "sample.bin"
            ver.write_atomic_0600(f, b"hello-s110")
            self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600)
            self.assertEqual(ver.read_regular_bytes_capped(f, "s", max_bytes=10), b"hello-s110")
            with self.assertRaises(ver.S110Error) as cm_big:
                ver.read_regular_bytes_capped(f, "s", max_bytes=9)
            self.assertEqual(cm_big.exception.code, "FILE_TOO_LARGE")

            # Multi-chunk read (> 65536 bytes) and mid-stream size cap
            big_data = b"x" * 70000
            big_f = d / "big.bin"
            ver.write_atomic_0600(big_f, big_data)
            self.assertEqual(len(ver.read_regular_bytes_capped(big_f, "big")), 70000)

            # Symlink target and symlink ancestor rejection
            sym = d / "link.bin"
            sym.symlink_to(f)
            with self.assertRaises(ver.S110Error) as cm_sym:
                ver.read_regular_bytes_capped(sym, "sym")
            self.assertEqual(cm_sym.exception.code, "SYMLINK_FORBIDDEN")

            sub = d / "real_sub"
            sub.mkdir()
            (sub / "inside.bin").write_bytes(b"abc")
            sym_dir = d / "sym_sub"
            sym_dir.symlink_to(sub)
            with self.assertRaises(ver.S110Error) as cm_anc:
                ver.read_regular_bytes_capped(sym_dir / "inside.bin", "anc")
            self.assertEqual(cm_anc.exception.code, "SYMLINK_FORBIDDEN")

            # Directory (non-regular) rejection
            with self.assertRaises(ver.S110Error) as cm_dir:
                ver.read_regular_bytes_capped(d, "dir")
            self.assertEqual(cm_dir.exception.code, "NON_REGULAR_FILE")

            # Missing file & missing parent on write
            with self.assertRaises(ver.S110Error) as cm_miss:
                ver.read_regular_bytes_capped(d / "nope", "nope")
            self.assertEqual(cm_miss.exception.code, "IO_OPEN_FAIL")
            with self.assertRaises(ver.S110Error) as cm_wp:
                ver.write_atomic_0600(d / "missing_dir" / "out.json", b"{}")
            self.assertEqual(cm_wp.exception.code, "IO_WRITE_FAIL")

            # Atomic write error cleanup on directory target
            target_dir = d / "isdir"
            target_dir.mkdir()
            with self.assertRaises(ver.S110Error) as cm_wd:
                ver.write_atomic_0600(target_dir, b"{}")
            self.assertEqual(cm_wd.exception.code, "IO_WRITE_FAIL")
            self.assertEqual(list(d.glob(".s110_tmp_*")), [])

    def test_04_strict_json_dos_and_type_guards(self) -> None:
        self.assertEqual(ver.loads_json_strict(b'{"a": 1, "b": -2}', "ok"), {"a": 1, "b": -2})
        # Exact 80-digit int boundary passes; 81-digit and 4500-digit fail with INT_DIGIT_LIMIT
        d80 = "9" * 80
        d81 = "9" * 81
        d4500 = "9" * 4500
        self.assertEqual(ver.loads_json_strict(f'{{"n": {d80}}}'.encode(), "ok80")["n"], int(d80))
        self.assertEqual(ver.loads_json_strict(f'{{"n": -{d80}}}'.encode(), "ok80n")["n"], -int(d80))
        for raw, expected_code in (
            (b"\xff\xfe", "INVALID_UTF8"),
            (b'{"a": "\x00"}', "INVALID_JSON"),
            (b'{"a": 1, "a": 2}', "DUPLICATE_JSON_KEY"),
            (b'{"a": 1.5}', "FLOAT_FORBIDDEN"),
            (b'{"a": NaN}', "NON_FINITE_FORBIDDEN"),
            (b'{"a": Infinity}', "NON_FINITE_FORBIDDEN"),
            (f'{{"n": {d81}}}'.encode(), "INT_DIGIT_LIMIT"),
            (f'{{"n": -{d81}}}'.encode(), "INT_DIGIT_LIMIT"),
            (f'{{"n": {d4500}}}'.encode(), "INT_DIGIT_LIMIT"),
            (b"{bad json", "INVALID_JSON"),
        ):
            with self.assertRaises(ver.S110Error) as cm:
                ver.loads_json_strict(raw, "bad")
            self.assertEqual(cm.exception.code, expected_code, f"for {raw[:30]!r}")
        # Direct _parse_int_capped boundary test (kills regex-only skip mutants)
        self.assertEqual(ver._parse_int_capped(d80), int(d80))
        self.assertEqual(ver._parse_int_capped("-" + d80), -int(d80))
        with self.assertRaises(ver.S110Error) as cm_cap:
            ver._parse_int_capped(d81)
        self.assertEqual(cm_cap.exception.code, "INT_DIGIT_LIMIT")


class Test03R13bLeanLexerAndStaticGate(unittest.TestCase):
    def test_05_r13b_o1_in_ident_lexer_and_char_literals(self) -> None:
        # Nested block comments, line comments, and clean identifier primes (0 FP!)
        clean_src = (
            "/- outer /- inner -/ still comment -/\n"
            "-- line comment with sorry \"bad\"\n"
            "def f (x' x1' foo.bar' x'' : Int) := x' + x1' - 1 / 2"
        )
        stripped = ver.strip_lean4_source(clean_src)
        self.assertIn("x' + x1'", stripped)
        self.assertNotIn("sorry", stripped)
        self.assertEqual(ver.lean4_rule_hits(clean_src), [])

        # Line comment at EOF without trailing newline, lone '-' inside block comment, lone '-' before sorry,
        # and identifier prime followed by quote-like span (kills BoolOp SUBCOND_DEL mutants)
        self.assertEqual(ver.lean4_rule_hits("def a := 1 -- sorry"), [])
        self.assertEqual(ver.lean4_rule_hits("/- a - sorry -/"), [])
        self.assertEqual(ver.lean4_rule_hits("def f := a - sorry"), ["R03_SORRY_ADMIT"])
        self.assertIn("x'", ver.strip_lean4_source("def f := x' '"))

        # Unclosed block comment fails closed
        with self.assertRaises(ver.S110Error) as cm_un:
            ver.strip_lean4_source("/- outer /- inner -/ unclosed")
        self.assertEqual(cm_un.exception.code, "LEAN4_UNTERMINATED_COMMENT")

        # X1 (!'"'.isDigit), X2 (1'"'), X3 («x»'"'), literal-LF Char, escapes (\n, \x27, \u0027)
        for atk_name, src, expect_rule in (
            ("X1_bang_char_quote", "def x := !'\"'.isDigit\nsorry", "R03_SORRY_ADMIT"),
            ("X2_digit_char_quote", "def x := 1'\"'\nsorry", "R03_SORRY_ADMIT"),
            ("X3_guil_char_quote", "def x := «x»'\"'\nsorry", "R01_LITERAL_OR_GUILLEMET"),
            ("literal_lf_char", "def c := '\n'\nsorry", "R03_SORRY_ADMIT"),
            ("esc_nl_char", "def c := '\\n'\nsorry", "R03_SORRY_ADMIT"),
            ("esc_hex_char", "def c := '\\x27'\nsorry", "R03_SORRY_ADMIT"),
            ("esc_uni_char", "def c := '\\u0027'\nsorry", "R03_SORRY_ADMIT"),
        ):
            hits = ver.lean4_rule_hits(src)
            self.assertIn(expect_rule, hits, f"{atk_name} missed: {hits}")
        # Verify literal-LF Char preserves line count
        lf_stripped = ver.strip_lean4_source("def c := '\n'\ndef y := 1")
        self.assertEqual(lf_stripped.count("\n"), 2)
        # Verify malformed Char escapes are NOT stripped as valid Char literals
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\", 0, 2))
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\\n'", 0, 4))
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\xGG'", 0, 6))
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\uZZZZ'", 0, 8))
        self.assertIsNone(ver._match_lean4_char_literal_end("''a'", 0, 4))
        self.assertEqual(ver._match_lean4_char_literal_end("'\\x27'", 0, 6), 6)
        self.assertEqual(ver._match_lean4_char_literal_end("'\\u0027'", 0, 8), 8)

    def test_06_all_18_static_lean_rules_and_structural_checks(self) -> None:
        samples = [
            ("R01_LITERAL_OR_GUILLEMET", 'def s := "sorry"'),
            ("R01_LITERAL_OR_GUILLEMET", 'def s := s!"{sorry}"'),
            ("R01_LITERAL_OR_GUILLEMET", 'def s := r#"sorry"#'),
            ("R01_LITERAL_OR_GUILLEMET", "def «bad» := 1"),
            ("R02_IMPORT", "import Init"),
            ("R03_SORRY_ADMIT", "theorem t : True := sorry"),
            ("R04_AXIOM_DECL", "axiom bad : False"),
            ("R05_UNSAFE_EXTERN", "unsafe def f := 1"),
            ("R05_UNSAFE_EXTERN", "@[implemented_by foo] def f := 1"),
            ("R06_OPAQUE_PARTIAL", "partial def f : Nat := f"),
            ("R06_OPAQUE_PARTIAL", "opaque g : Nat"),
            ("R07_NATIVE_DECIDE", "theorem t : True := by native_decide"),
            ("R07_NATIVE_DECIDE", "theorem t : True := by decide +native"),
            ("R08_DBG_TRACE", "def f := dbg_trace 1"),
            ("R08_DBG_TRACE", "def f := dbgSleep 1"),
            ("R09_INIT_EXPORT_ATTR", "@[export foo] def f := 1"),
            ("R09_INIT_EXPORT_ATTR", "initialize x : Nat := pure 1"),
            ("R10_GUARD_MSGS", "#guard_msgs in #check 1"),
            ("R11_WARN_SORRY_OPT", "warn.sorry"),
            ("R12_META_EVAL_CMD", "#eval 1"),
            ("R13_SET_OPTION", "set_option maxRecDepth 1000"),
            ("R14_ELAB_TACTIC_MACRO", "macro_rules | `(x) => `(1)"),
            ("R15_IO_SYSTEM", "def f := IO.println"),
            ("R16_PANIC_UNREACHABLE", "def f := panic!"),
            ("R17_DECIDE_CONFIG", "by decide (config := { native := true })"),
            ("R18_ROOT_SORRYAX", "_root_.sorryAx"),
        ]
        for rule_id, snippet in samples:
            self.assertIn(rule_id, ver.lean4_rule_hits(snippet), f"missed {rule_id}")

        real_src = LEAN_PATH.read_text(encoding="utf-8")
        ver.static_gate_lean4_source(real_src)
        with self.assertRaises(ver.S110Error) as cm_esc:
            ver.static_gate_lean4_source(real_src + "\n-- ok\nsorry\n")
        self.assertEqual(cm_esc.exception.code, "LEAN4_TRUST_ESCAPE")
        with self.assertRaises(ver.S110Error) as cm_cr:
            ver.static_gate_lean4_source(real_src + "\r")
        self.assertEqual(cm_cr.exception.code, "LEAN4_BAD_CHARS")
        with self.assertRaises(ver.S110Error) as cm_nul:
            ver.static_gate_lean4_source(real_src + "\x00")
        self.assertEqual(cm_nul.exception.code, "LEAN4_BAD_CHARS")
        with self.assertRaises(ver.S110Error) as cm_pr:
            ver.static_gate_lean4_source(real_src + "\n#print Nat\n")
        self.assertEqual(cm_pr.exception.code, "LEAN4_BAD_PRINT")
        with self.assertRaises(ver.S110Error) as cm_ps:
            ver.static_gate_lean4_source(real_src.rsplit("\n#print axioms", 1)[0])
        self.assertEqual(cm_ps.exception.code, "LEAN4_PRINT_SET_MISMATCH")
        with self.assertRaises(ver.S110Error) as cm_mt:
            ver.static_gate_lean4_source(real_src.replace("theorem skew_diag_zero", "def skew_diag_zero", 1))
        self.assertEqual(cm_mt.exception.code, "LEAN4_MISSING_THEOREM")

    def test_07_axiom_parser_and_env_scrub(self) -> None:
        # Multiline wrapped axiom output + zero-axiom theorem + allowed axioms
        lines = []
        for idx, name in enumerate(oracle.LEAN_THEOREM_NAMES):
            if idx == 0:
                lines.append(f"'{name}' does not depend on any axioms")
            elif idx == 1:
                lines.append(f"'{name}' depends on axioms: [\n  propext,\n  Quot.sound\n]")
            else:
                lines.append(f"'{name}' depends on axioms: [propext, Quot.sound]")
        parsed = ver.parse_lean_axiom_output("\n".join(lines))
        self.assertEqual(len(parsed), 38)
        self.assertEqual(parsed[oracle.LEAN_THEOREM_NAMES[0]], [])
        self.assertEqual(parsed[oracle.LEAN_THEOREM_NAMES[1]], ["propext", "Quot.sound"])

        with self.assertRaises(ver.S110Error) as cm_unexp:
            ver.parse_lean_axiom_output("unexpected noise line")
        self.assertEqual(cm_unexp.exception.code, "LEAN_UNEXPECTED_STDOUT")
        with self.assertRaises(ver.S110Error) as cm_eof:
            ver.parse_lean_axiom_output("'GeosphereWeftConservation.skew_diag_zero' depends on axioms: [propext")
        self.assertEqual(cm_eof.exception.code, "LEAN_UNEXPECTED_STDOUT")
        with self.assertRaises(ver.S110Error) as cm_dup:
            ver.parse_lean_axiom_output("\n".join(lines + [lines[0]]))
        self.assertEqual(cm_dup.exception.code, "LEAN_DUPLICATE_THEOREM")
        bad_ax = list(lines)
        bad_ax[2] = f"'{oracle.LEAN_THEOREM_NAMES[2]}' depends on axioms: [propext, Classical.choice]"
        with self.assertRaises(ver.S110Error) as cm_ax:
            ver.parse_lean_axiom_output("\n".join(bad_ax))
        self.assertEqual(cm_ax.exception.code, "LEAN_FORBIDDEN_AXIOM")
        with self.assertRaises(ver.S110Error) as cm_set:
            ver.parse_lean_axiom_output("\n".join(lines[:-1]))
        self.assertEqual(cm_set.exception.code, "LEAN_THEOREM_SET_MISMATCH")

        # Allowlist env scrub + resolve_lean_binary error paths
        old_env = dict(os.environ)
        try:
            os.environ["LEAN_PATH"] = "/tmp/poison"
            os.environ["ELAN_TOOLCHAIN"] = "poison"
            os.environ["LD_PRELOAD"] = "/tmp/evil.so"
            clean = ver.scrubbed_lean_env()
            for bad_k in ("LEAN_PATH", "ELAN_TOOLCHAIN", "LD_PRELOAD"):
                self.assertNotIn(bad_k, clean)
            os.environ["ALETHEIA_LEAN_BIN"] = "/nonexistent/lean_bin_s110"
            with self.assertRaises(ver.S110Error) as cm_nf:
                ver.resolve_lean_binary()
            self.assertEqual(cm_nf.exception.code, "LEAN_BINARY_NOT_FILE")
            with tempfile.NamedTemporaryFile(prefix="s110_noexec_", delete=False) as tf:
                noexec = Path(tf.name)
            try:
                os.chmod(noexec, 0o600)
                os.environ["ALETHEIA_LEAN_BIN"] = str(noexec)
                with self.assertRaises(ver.S110Error) as cm_nx:
                    ver.resolve_lean_binary()
                self.assertEqual(cm_nx.exception.code, "LEAN_BINARY_NOT_EXECUTABLE")
                os.chmod(noexec, 0o700)
                self.assertEqual(ver.resolve_lean_binary(), str(noexec))
            finally:
                noexec.unlink()
            os.environ.pop("ALETHEIA_LEAN_BIN", None)
            os.environ["PATH"] = ""
            with self.assertRaises(ver.S110Error) as cm_na:
                ver.resolve_lean_binary()
            self.assertEqual(cm_na.exception.code, "LEAN_BINARY_UNAVAILABLE")
        finally:
            os.environ.clear()
            os.environ.update(old_env)


class Test04SemanticAndShapeAudits(unittest.TestCase):
    def test_08_shape_deep_equal_rational_and_aliasing(self) -> None:
        a = ver.expected_payload()
        b = ver.expected_payload()
        a["novelty_grade"] = "MUTATED"
        self.assertEqual(b["novelty_grade"], "N1")
        self.assertEqual(ver.strict_shape_match({"a": [1, True]}, {"a": [2, False]}), "")
        self.assertEqual(ver.strict_shape_match({"a": True}, {"a": 1}), "payload.a")
        self.assertEqual(ver.strict_shape_match({"a": 1}, {"b": 1}), "payload")
        self.assertEqual(ver.strict_shape_match({"a": [1]}, {"a": [1, 2]}), "payload.a")
        self.assertEqual(ver.strict_deep_equal({"a": [1, {"b": 2}]}, {"a": [1, {"b": 2}]}), "")
        self.assertEqual(ver.strict_deep_equal({"a": True}, {"a": 1}), "payload.a")
        self.assertEqual(ver.strict_deep_equal({"a": 1}, {"b": 1}), "payload")
        self.assertEqual(ver.strict_deep_equal({"a": [1]}, {"a": [1, 2]}), "payload.a")
        self.assertEqual(ver.strict_deep_equal({"a": [1, 2]}, {"a": [1, 3]}), "payload.a[1]")

        self.assertEqual(ver.parse_capped_rational("-3/4", "r"), Fraction(-3, 4))
        self.assertEqual(ver.parse_capped_rational("0", "r"), Fraction(0))
        for bad_r in (123, "", "1/0", "1.5", "1/" + "9" * 81, "9" * 81, "NaN"):
            with self.assertRaises(ver.S110Error) as cm:
                ver.parse_capped_rational(bad_r, "r")
            self.assertEqual(cm.exception.code, "INVALID_RATIONAL_STR")

    def test_09_all_independent_semantic_codes(self) -> None:
        # Directly target every SEC_* code in _independent_semantics
        cases = [
            (["novelty_grade"], "N2", "SEC_NOVELTY"),
            (["n2_claims"], 1, "SEC_N2_ZERO"),
            (["lean_companion", "named_theorem_count"], 37, "SEC_LEAN_CNT"),
            (["lean_companion", "total_theorem_declarations"], 99, "SEC_LEAN_TOTAL"),
            (["pillar1_geodynamo_cayley", "rank2_skew_d8", "lorentz_radial_work_q"], "1", "SEC_P1_WORK"),
            (["pillar1_geodynamo_cayley", "block2x2_cayley_d8", "norm_sq_out_q"], "999", "SEC_P1_CAY2"),
            (["pillar1_geodynamo_cayley", "hopf_quat_cayley_d4", "norm_sq_out_q"], "999", "SEC_P1_CAY4"),
            (["pillar1_geodynamo_cayley", "pfaffian_4d_invertibility", "det_I_plus_skew_q"], "38", "SEC_P1_DET4"),
            (["pillar2_oceanic_and_darcy", "bidirectional_birkhoff_d4", "mass_out_q"], "17", "SEC_P2_MASS"),
            (["pillar2_oceanic_and_darcy", "b1_causal_sinkhorn_obstruction", "forced_identity"], False, "SEC_P2_B1"),
            (["pillar2_oceanic_and_darcy", "discovery2_so2_birkhoff_non_commutation", "commutator_frob_sq_q"], "0", "SEC_P2_COMM"),
            (["pillar2_oceanic_and_darcy", "darcy_aquifer_contraction", "parallelogram_residual_q"], "0", "SEC_P2_PARA"),
            (["pillar2_oceanic_and_darcy", "m1_unbounded_K_obstruction", "post_state_q"], "1", "SEC_P2_M1"),
            (["pillar3_bingham_poloidal_and_ozone", "bingham_y_phase_sweep", 4, "is_stagnant_lid_zero"], False, "SEC_P3_STAG"),
            (["pillar3_bingham_poloidal_and_ozone", "b5_sigma_obstruction", "leaked_output_q"], "0", "SEC_P3_B5"),
            (["pillar3_bingham_poloidal_and_ozone", "s50_commutator_obstruction", "sum_of_bingham_q"], "0", "SEC_P3_S50"),
            (["pillar3_bingham_poloidal_and_ozone", "discovery3_poloidal_bingham_S_YH", "pol_tor_dot_q"], "1", "SEC_P3_ORTH"),
            (["pillar3_bingham_poloidal_and_ozone", "discovery3_poloidal_bingham_S_YH", "so4_equivariant_exact"], False, "SEC_P3_EQUIV"),
            (["pillar3_bingham_poloidal_and_ozone", "ozone_channel2b_airlock", "advection_sq_q"], "241", "SEC_P3_OZ1"),
            (["pillar3_bingham_poloidal_and_ozone", "ozone_channel2b_airlock", "bound_b2_q"], "239", "SEC_P3_OZ2"),
            (["pillar4_weft_smith_triple_gate", "householder_crow_invariance", "c_row_after_q"], "1/3", "SEC_P4_CROW"),
            (["pillar4_weft_smith_triple_gate", "householder_crow_invariance", "c_max_q"], "1/3", "SEC_P4_DPI"),
            (["pillar4_weft_smith_triple_gate", "crow_cancellation_obstruction", "c_row_composed_q"], "1/2", "SEC_P4_CANCEL"),
            (["pillar4_weft_smith_triple_gate", "h11c_50cycle_simulation", "cycles_total"], 51, "SEC_P4_CYCLES"),
            (["pillar4_weft_smith_triple_gate", "h11c_50cycle_simulation", "poisoned_rejected_and_rolled_back"], 8, "SEC_P4_CATCH"),
            (["pillar4_weft_smith_triple_gate", "h11c_50cycle_simulation", "anchor_err_final"], 101, "SEC_P4_MONO"),
            (["pillar4_weft_smith_triple_gate", "h11c_50cycle_simulation", "cum_norm_sq_final"], 51, "SEC_P4_CUM"),
        ]
        for path, bad_val, expected_code in cases:
            p = ver.expected_payload()
            _set_path(p, path, bad_val)
            with self.assertRaises(ver.S110Error) as cm:
                ver.secondary_audit_payload(p)
            self.assertEqual(cm.exception.code, expected_code, f"path={path}")

        # Exact-equality boundary check on _independent_semantics (kills <= -> < and >= -> > mutants)
        p_eq = ver.expected_payload()
        p_eq["pillar3_bingham_poloidal_and_ozone"]["ozone_channel2b_airlock"]["advection_sq_q"] = "240"
        p_eq["pillar3_bingham_poloidal_and_ozone"]["ozone_channel2b_airlock"]["bound_b2_q"] = "240"
        p_eq["pillar4_weft_smith_triple_gate"]["householder_crow_invariance"]["c_max_q"] = "1/2"
        p_eq["pillar4_weft_smith_triple_gate"]["h11c_50cycle_simulation"]["poisoned_rejected_and_rolled_back"] = 9
        p_eq["pillar4_weft_smith_triple_gate"]["h11c_50cycle_simulation"]["anchor_err_final"] = 100
        p_eq["pillar4_weft_smith_triple_gate"]["h11c_50cycle_simulation"]["cum_norm_sq_final"] = 50
        ver._independent_semantics(p_eq)

        # Direct SCHEMA_SHAPE_MISMATCH check on secondary_audit_payload
        with self.assertRaises(ver.S110Error) as cm_sh:
            ver.secondary_audit_payload({"wrong_key": 1})
        self.assertEqual(cm_sh.exception.code, "SCHEMA_SHAPE_MISMATCH")


class Test05ExhaustiveLeafSweepAndEnvelope(unittest.TestCase):
    def test_10_envelope_and_replay_rejection(self) -> None:
        res_fr1 = ver.verify_certificate_dict(FROZEN_CERT, full_replay=True)
        res_fr0 = ver.verify_certificate_dict(FROZEN_CERT, full_replay=False)
        self.assertEqual(res_fr1["status"], "OK")
        self.assertTrue(res_fr1["full_replay"])
        self.assertFalse(res_fr0["full_replay"])

        with self.assertRaises(ver.S110Error) as cm_t:
            ver.verify_certificate_dict([])
        self.assertEqual(cm_t.exception.code, "INVALID_ENVELOPE_TYPE")
        with self.assertRaises(ver.S110Error) as cm_pt:
            ver.secondary_audit_payload([])
        self.assertEqual(cm_pt.exception.code, "INVALID_PAYLOAD_TYPE")

        for mut_fn, exp_code in (
            (lambda c: c.pop("track_id"), "INVALID_ENVELOPE_KEYS"),
            (lambda c: c.__setitem__("schema_version", "wrong"), "SCHEMA_VERSION_MISMATCH"),
            (lambda c: c.__setitem__("track_id", "wrong"), "TRACK_ID_MISMATCH"),
            (lambda c: c.__setitem__("payload_sha256", 123), "INVALID_HASH"),
            (lambda c: c.__setitem__("payload_sha256", "Z" * 64), "INVALID_HASH"),
            (lambda c: c.__setitem__("certificate_sha256", 123), "INVALID_HASH"),
            (lambda c: c.__setitem__("certificate_sha256", "Z" * 64), "INVALID_HASH"),
            (lambda c: c.__setitem__("payload", []), "INVALID_PAYLOAD_TYPE"),
            (lambda c: c.__setitem__("payload_sha256", "0" * 64), "PAYLOAD_HASH_MISMATCH"),
            (lambda c: c.__setitem__("certificate_sha256", "0" * 64), "CERT_HASH_MISMATCH"),
        ):
            c = copy.deepcopy(FROZEN_CERT)
            mut_fn(c)
            with self.assertRaises(ver.S110Error) as cm:
                ver.verify_certificate_dict(c, full_replay=True)
            self.assertEqual(cm.exception.code, exp_code)

        # Pre-hash tree safety (non-str key, >266-bit int, forbidden types) & non-canonical file bytes
        ver._validate_exact_json_tree({"s": "ok", "b": True, "i": (1 << ver.MAX_INT_BITS) - 1, "l": [1, False]})
        with self.assertRaises(ver.S110Error) as cm_k:
            ver._validate_exact_json_tree({1: "bad"})
        self.assertEqual(cm_k.exception.code, "INVALID_JSON_KEY")
        with self.assertRaises(ver.S110Error) as cm_bi:
            ver._validate_exact_json_tree({"n": 1 << ver.MAX_INT_BITS})
        self.assertEqual(cm_bi.exception.code, "INT_DIGIT_LIMIT")
        with self.assertRaises(ver.S110Error) as cm_tp:
            ver._validate_exact_json_tree({"bad": (1, 2)})
        self.assertEqual(cm_tp.exception.code, "INVALID_JSON_TYPE")

        c_big = copy.deepcopy(FROZEN_CERT)
        c_big["payload"]["n2_claims"] = 10 ** 5000
        with self.assertRaises(ver.S110Error) as cm_5k:
            ver.verify_certificate_dict(c_big, full_replay=True)
        self.assertEqual(cm_5k.exception.code, "INT_DIGIT_LIMIT")

        with tempfile.TemporaryDirectory(prefix="s110_canon_") as td:
            d = Path(td)
            crlf_p = d / "crlf.json"
            crlf_p.write_bytes(CERT_PATH.read_bytes().replace(b"\n", b"\r\n"))
            with self.assertRaises(ver.S110Error) as cm_cr:
                ver.verify_certificate_file(crlf_p)
            self.assertEqual(cm_cr.exception.code, "NON_CANONICAL_BYTES")
            pretty_p = d / "pretty.json"
            pretty_p.write_text(json.dumps(FROZEN_CERT, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(ver.S110Error) as cm_pr:
                ver.verify_certificate_file(pretty_p)
            self.assertEqual(cm_pr.exception.code, "NON_CANONICAL_BYTES")

        # Pin REPLAY_MISMATCH ahead of secondary_audit_payload when full_replay=True
        orig_build = oracle.build_payload
        try:
            def _mutated_payload():
                p = orig_build()
                p["scope_note"] = "DIFF"
                return p
            oracle.build_payload = _mutated_payload
            with self.assertRaises(ver.S110Error) as cm_rep:
                ver.verify_certificate_dict(FROZEN_CERT, full_replay=True)
            self.assertEqual(cm_rep.exception.code, "REPLAY_MISMATCH")
        finally:
            oracle.build_payload = orig_build

    def test_11_exhaustive_235_leaf_resigned_sweep_all_3_surfaces(self) -> None:
        leaves: list = []
        _walk_leaves(FROZEN_CERT["payload"], [], leaves)
        self.assertEqual(len(leaves), 241)
        for path, orig in leaves:
            c = copy.deepcopy(FROZEN_CERT)
            _set_path(c["payload"], path, _tamper_scalar(orig))
            c = _resign(c)
            snap = copy.deepcopy(c)
            with self.assertRaises(ver.S110Error):
                ver.secondary_audit_payload(c["payload"])
            self.assertEqual(c, snap)
            with self.assertRaises(ver.S110Error):
                ver.verify_certificate_dict(c, full_replay=False)
            self.assertEqual(c, snap)
            with self.assertRaises(ver.S110Error):
                ver.verify_certificate_dict(c, full_replay=True)
            self.assertEqual(c, snap)


class Test06CLIAndPins(unittest.TestCase):
    def test_12_external_pins_and_tamper(self) -> None:
        # No silent skip: pins are either re-hashed (files shipped) or reported unverifiable.
        pins = ver.verify_external_pins()
        if (TRACK_DIR.parent / oracle.EXTERNAL_PROTOCOL_PINS[0][1]).is_file():
            self.assertEqual(pins["status"], "PINS_OK")
            self.assertEqual(pins["external"], 4)
        else:
            self.assertEqual(pins["status"], "PINS_PARTIAL_UNVERIFIABLE")
            self.assertEqual(len(pins["unverifiable"]), 4)
            self.assertEqual(pins["external"], 0)
        with tempfile.TemporaryDirectory(prefix="s110_pins_") as td:
            root = Path(td)
            sample = root / "pin.md"
            sample.write_bytes(b"pinned-content")
            good_sha = oracle.sha256_hex(b"pinned-content")
            orig_pins = oracle.EXTERNAL_PROTOCOL_PINS
            try:
                oracle.EXTERNAL_PROTOCOL_PINS = (("TEST_PIN", "pin.md", good_sha),)
                ok_res = ver.verify_external_pins(root)
                self.assertEqual(ok_res["status"], "PINS_OK")
                self.assertEqual(ok_res["external"], 1)
                self.assertEqual(ok_res["pins"][0]["sha256"], good_sha)
                sample.write_bytes(b"TAMPERED")
                with self.assertRaises(ver.S110Error) as cm:
                    ver.verify_external_pins(root)
                self.assertEqual(cm.exception.code, "PIN_SHA_MISMATCH")
            finally:
                oracle.EXTERNAL_PROTOCOL_PINS = orig_pins

    def test_13_cli_modes_and_fail_closed_flags(self) -> None:
        def _run_cli(argv: list[str]) -> tuple[int, str, str]:
            out_buf, err_buf = io.StringIO(), io.StringIO()
            old_out, old_err = sys.stdout, sys.stderr
            try:
                sys.stdout, sys.stderr = out_buf, err_buf
                rc = ver.main(argv)
            finally:
                sys.stdout, sys.stderr = old_out, old_err
            return rc, out_buf.getvalue(), err_buf.getvalue()

        rc, out, _ = _run_cli([])
        self.assertEqual(rc, 0)
        self.assertIn(FROZEN_CERT["certificate_sha256"], out)

        rc, out, _ = _run_cli(["--check"])
        self.assertEqual(rc, 0)
        self.assertIn(FROZEN_CERT["certificate_sha256"], out)

        rc, out, _ = _run_cli(["--check", str(CERT_PATH), "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["status"], "OK")

        rc, out, _ = _run_cli(["--verify-pins"])
        self.assertEqual(rc, 0)
        rc, out, _ = _run_cli(["--verify-pins", "--json"])
        self.assertEqual(rc, 0)
        pj = json.loads(out)
        if (TRACK_DIR.parent / oracle.EXTERNAL_PROTOCOL_PINS[0][1]).is_file():
            self.assertEqual(pj["status"], "PINS_OK")
            self.assertEqual(pj["external"], 4)
        else:
            self.assertEqual(pj["status"], "PINS_PARTIAL_UNVERIFIABLE")
            self.assertEqual(len(pj["unverifiable"]), 4)

        with tempfile.TemporaryDirectory(prefix="s110_cli_") as td:
            d = Path(td)
            out_cert = d / "out.json"
            rc, out, _ = _run_cli(["--write", str(out_cert), "--json"])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(out)["status"], "WRITTEN")
            self.assertEqual(out_cert.read_bytes(), CERT_PATH.read_bytes())
            self.assertEqual(stat.S_IMODE(out_cert.stat().st_mode), 0o600)

            pin_f = d / "p.md"
            pin_f.write_bytes(b"ok-pin")
            orig_pins = oracle.EXTERNAL_PROTOCOL_PINS
            try:
                oracle.EXTERNAL_PROTOCOL_PINS = (("P1", "p.md", oracle.sha256_hex(b"ok-pin")),)
                rc, out, _ = _run_cli(["--verify-pins", str(d)])
                self.assertEqual(rc, 0)
                self.assertIn("PINS_OK external=1", out)
                rc, out, _ = _run_cli(["--verify-pins", str(d), "--json"])
                self.assertEqual(rc, 0)
                self.assertEqual(json.loads(out)["external"], 1)
            finally:
                oracle.EXTERNAL_PROTOCOL_PINS = orig_pins

        for bad_argv, code in (
            (["--unknown"], "UNKNOWN_FLAG"),
            (["--check", "--verify-pins"], "CONFLICTING_FLAGS"),
            (["--check", "/nonexistent/s110_cert.json"], "IO_OPEN_FAIL"),
        ):
            rc, _, err = _run_cli(bad_argv)
            self.assertEqual(rc, 2)
            self.assertIn(code, err)


class Test07LiveLeanAndPoisonedEnvHijack(unittest.TestCase):
    def test_14_live_lean_and_cli_verify_lean(self) -> None:
        res = ver.verify_lean4_file_live(LEAN_PATH, check_sha=True)
        self.assertEqual(res["theorems_verified"], 38)
        self.assertEqual(res["lean_source_sha256"], oracle.LEAN_SOURCE_SHA256)
        self.assertIn("4.36.0", res["lean_version"])

        # Non-UTF8 and SHA mismatch checks on verify_lean4_file_live
        with tempfile.TemporaryDirectory(prefix="s110_lean_") as td:
            d = Path(td)
            bad_utf8 = d / "bad.lean"
            bad_utf8.write_bytes(b"\xff\xfe")
            with self.assertRaises(ver.S110Error) as cm_u:
                ver.verify_lean4_file_live(bad_utf8, check_sha=False)
            self.assertEqual(cm_u.exception.code, "INVALID_UTF8")

            mod_lean = d / "mod.lean"
            mod_lean.write_text(LEAN_PATH.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaises(ver.S110Error) as cm_sha:
                ver.verify_lean4_file_live(mod_lean, check_sha=True)
            self.assertEqual(cm_sha.exception.code, "LEAN_SHA_MISMATCH")

            # Live fake-lean error paths (version, compile fail, stderr, warning)
            def _make_fake(name: str, body: str) -> Path:
                p = d / name
                p.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
                os.chmod(p, 0o700)
                return p

            old_bin = os.environ.get("ALETHEIA_LEAN_BIN")
            try:
                os.environ["ALETHEIA_LEAN_BIN"] = str(_make_fake("badver.sh", "echo 'Lean (version 4.1.0, x)'"))
                with self.assertRaises(ver.S110Error) as cm_v:
                    ver.verify_lean4_file_live(LEAN_PATH, check_sha=True)
                self.assertEqual(cm_v.exception.code, "LEAN_VERSION_MISMATCH")

                os.environ["ALETHEIA_LEAN_BIN"] = str(_make_fake("badverrc.sh", "echo 'Lean (version 4.36.0, x)'; exit 1"))
                with self.assertRaises(ver.S110Error) as cm_vrc:
                    ver.verify_lean4_file_live(LEAN_PATH, check_sha=True)
                self.assertEqual(cm_vrc.exception.code, "LEAN_VERSION_MISMATCH")

                orig_run = ver.subprocess.run
                try:
                    def _boom(*_a, **_kw):
                        raise OSError("exec_boom")
                    ver.subprocess.run = _boom
                    with self.assertRaises(ver.S110Error) as cm_ex:
                        ver.verify_lean4_file_live(LEAN_PATH, check_sha=True)
                    self.assertEqual(cm_ex.exception.code, "LEAN_EXEC_ERROR")
                finally:
                    ver.subprocess.run = orig_run

                os.environ["ALETHEIA_LEAN_BIN"] = str(
                    _make_fake("badrc.sh", "if [ \"$1\" = --version ]; then echo 'Lean (version 4.36.0, x)'; exit 0; fi; exit 1")
                )
                with self.assertRaises(ver.S110Error) as cm_c:
                    ver.verify_lean4_file_live(LEAN_PATH, check_sha=True)
                self.assertEqual(cm_c.exception.code, "LEAN_COMPILE_FAIL")

                os.environ["ALETHEIA_LEAN_BIN"] = str(
                    _make_fake("baderr.sh", "if [ \"$1\" = --version ]; then echo 'Lean (version 4.36.0, x)'; exit 0; fi; echo err >&2; exit 0")
                )
                with self.assertRaises(ver.S110Error) as cm_e:
                    ver.verify_lean4_file_live(LEAN_PATH, check_sha=True)
                self.assertEqual(cm_e.exception.code, "LEAN_STDERR_NONEMPTY")

                os.environ["ALETHEIA_LEAN_BIN"] = str(
                    _make_fake("badwarn.sh", "if [ \"$1\" = --version ]; then echo 'Lean (version 4.36.0, x)'; exit 0; fi; echo 'warning: bad'; exit 0")
                )
                with self.assertRaises(ver.S110Error) as cm_w:
                    ver.verify_lean4_file_live(LEAN_PATH, check_sha=True)
                self.assertEqual(cm_w.exception.code, "LEAN_WARNING_FORBIDDEN")
            finally:
                if old_bin is None:
                    os.environ.pop("ALETHEIA_LEAN_BIN", None)
                else:
                    os.environ["ALETHEIA_LEAN_BIN"] = old_bin

        # CLI --verify-lean subprocess
        proc = subprocess.run(
            [sys.executable, "-I", "-B", str(TRACK_DIR / "verify_s110_geosphere_weft_conservation.py"), "--verify-lean", "--json"],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["theorems_verified"], 38)

    def test_15_live_init_olean_hijack_blocked(self) -> None:
        lean_bin = ver.resolve_lean_binary()
        lean_src = LEAN_PATH.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory(prefix="s110_hijack_") as td:
            fake_dir = Path(td)
            (fake_dir / "Init.olean").write_bytes(b"CORRUPT_FAKE_INIT_OLEAN")
            poison_env = dict(os.environ)
            poison_env["LEAN_PATH"] = str(fake_dir)
            raw_proc = subprocess.run(
                [lean_bin, "--stdin"],
                input=lean_src,
                capture_output=True,
                text=True,
                env=poison_env,
                timeout=120,
                check=False,
            )
            self.assertNotEqual(raw_proc.returncode, 0)
            old_lp = os.environ.get("LEAN_PATH")
            try:
                os.environ["LEAN_PATH"] = str(fake_dir)
                clean_res = ver.verify_lean4_file_live(LEAN_PATH, check_sha=True)
                self.assertEqual(clean_res["theorems_verified"], 38)
            finally:
                if old_lp is None:
                    os.environ.pop("LEAN_PATH", None)
                else:
                    os.environ["LEAN_PATH"] = old_lp


if __name__ == "__main__":
    unittest.main()
