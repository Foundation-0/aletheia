#!/usr/bin/env python3
"""Track S106 Phase 1A R5 test suite: assertion-free (unittest methods only), zero floats, zero skips.

Covers pure-Decimal physics benchmark guards, exact pure-Q sphere/Hodge/Hopf/Coxeter oracle,
hardened Zone-B I/O, strict JSON parser, 18-rule R12 static Lean 4 pre-filter + 0-FP controls +
Char/raw/interp/guillemet/X1..X3 quote-desync PoCs, allowlist env scrubbing + live Init.olean
LEAN_PATH hijack immunity, re-signed SEC/FR0/FR1 every-leaf + type-confusion + >4300-digit DoS
forgery battery, and the CLI surface.
"""
from __future__ import annotations

import ast
import copy
from decimal import Decimal
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
from unittest import mock

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import s106_physics_denom_pi_bench as bench  # noqa: E402
import s106_sphere_denom_pi_oracle as oracle  # noqa: E402
import verify_s106_sphere_denom_pi as verifier  # noqa: E402

E = oracle.S106Error
BE = bench.S106BenchError
CERT = json.loads((_THIS_DIR / oracle.CERT_FILE_NAME).read_text(encoding="utf-8"))
PAYLOAD = CERT["payload"]
LEAN_PATH = _THIS_DIR / oracle.LEAN_SOURCE_NAME
LEAN_SRC = LEAN_PATH.read_text(encoding="utf-8")
SOURCES = (
    "s106_physics_denom_pi_bench.py",
    "s106_sphere_denom_pi_oracle.py",
    "verify_s106_sphere_denom_pi.py",
    "test_s106_sphere_denom_pi_r5.py",
)
FAKE_LIVE = {
    "lean_version": "Lean (version 4.36.0, mock)",
    "theorems_verified": 34,
    "lean_source_sha256": oracle.PINNED_LEAN_SOURCE_SHA256,
}


def code_of(fn, *args, **kwargs) -> str:
    try:
        fn(*args, **kwargs)
    except (E, BE) as exc:
        return exc.code
    return "NO_ERROR"


def resign(payload: dict) -> dict:
    p_sha = oracle.sha256_hex(oracle.canonical_json_bytes(payload))
    core = {"schema_version": oracle.SCHEMA_VERSION, "track_id": oracle.TRACK_ID, "payload_sha256": p_sha, "payload": payload}
    return {**core, "certificate_sha256": oracle.sha256_hex(oracle.canonical_json_bytes(core))}


def set_path(obj, path, value):
    cur = obj
    for k in path[:-1]:
        cur = cur[k]
    cur[path[-1]] = value


def leaf_paths(obj, prefix=()):
    if type(obj) is dict:
        for k, v in obj.items():
            yield from leaf_paths(v, prefix + (k,))
    elif type(obj) is list:
        for i, v in enumerate(obj):
            yield from leaf_paths(v, prefix + (i,))
    else:
        yield prefix, obj


def tamper_value(v):
    if type(v) is bool:
        return not v
    if type(v) is int:
        return v + 1
    if type(v) is str:
        return v + "x"
    return "x"


def axiom_stdout(names, dep_for=()) -> str:
    lines = []
    for n in names:
        if n in dep_for:
            lines.append(f"'{n}' depends on axioms: [propext, Quot.sound]")
        else:
            lines.append(f"'{n}' does not depend on any axioms")
    return "\n".join(lines) + "\n"


def completed(rc=0, out="", err=""):
    return subprocess.CompletedProcess(args=["lean"], returncode=rc, stdout=out, stderr=err)


GOOD_VERSION = "Lean (version 4.36.0, x86_64-unknown-linux-gnu, Release)\n"


class Test01Hygiene(unittest.TestCase):
    def test_python_sources_zero_floats_asserts_and_literals(self):
        banned_sub = ("/dev/" + "null", "4-" + "mode", "/" + "home/", "\r")
        for name in SOURCES:
            text = (_THIS_DIR / name).read_text(encoding="utf-8")
            for b in banned_sub:
                self.assertNotIn(b, text, f"{name} contains banned literal")
            tree = ast.parse(text)
            for node in ast.walk(tree):
                self.assertNotIsInstance(node, ast.Assert, f"{name}: bare assert")
                if isinstance(node, ast.Constant):
                    self.assertNotIsInstance(node.value, float, f"{name}: float literal")
                    self.assertNotIsInstance(node.value, complex, f"{name}: complex literal")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotEqual(node.func.id, "float", f"{name}: float() call")
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    mods = [a.name for a in node.names] + ([node.module] if isinstance(node, ast.ImportFrom) else [])
                    self.assertNotIn("random", mods)

    def test_lean_source_clean_and_counts(self):
        verifier.static_gate_lean4_source(LEAN_SRC)
        self.assertEqual(verifier.lean4_rule_hits(LEAN_SRC), [])
        self.assertEqual(len(oracle.LEAN_THEOREM_NAMES), 34)
        self.assertEqual(len(set(oracle.LEAN_THEOREM_NAMES)), 34)
        self.assertEqual(len(verifier.LEAN4_RULES), 18)
        self.assertEqual(len({rid for rid, _ in verifier.LEAN4_RULES}), 18)


class Test02BenchAndOraclePrimitives(unittest.TestCase):
    def test_physics_bench_guards_and_math(self):
        self.assertEqual(code_of(bench.require_ok, 1, "C", "d"), "C")
        self.assertEqual(code_of(bench.d_sin_cos, 1), "INVALID_DECIMAL")
        s0, c0 = bench.d_sin_cos(Decimal(0))
        self.assertEqual((s0, c0), (Decimal(0), Decimal(1)))
        self.assertEqual(code_of(bench.d_sqrt, 1), "INVALID_DECIMAL")
        self.assertEqual(code_of(bench.d_sqrt, Decimal(-1)), "NEG_SQRT")
        self.assertEqual(bench.d_sqrt(Decimal(0)), Decimal(0))
        self.assertEqual(bench.d_sqrt(Decimal(4)), Decimal(2))
        self.assertEqual(bench.d_fmt_sci(Decimal("1e-26")), "0")
        self.assertEqual(bench.d_fmt_sci(Decimal("0.00125")), "1.250000e-3")
        self.assertEqual(bench.d_ratio_dec4(Decimal(0), Decimal(0)), "1.0000")
        self.assertEqual(bench.d_ratio_dec4(Decimal(1), Decimal(0)), "EXACT_INF")
        self.assertEqual(bench.d_ratio_dec4(Decimal(7), Decimal(2)), "3.5000")
        self.assertIs(bench.all_ge_threshold((Decimal(3), Decimal(4)), Decimal(3)), True)
        self.assertIs(bench.all_ge_threshold((Decimal(2), Decimal(4)), Decimal(3)), False)
        self.assertEqual(code_of(bench.leggauss_dec, "2"), "INVALID_GL_N")
        self.assertEqual(code_of(bench.leggauss_dec, 0), "INVALID_GL_N")
        self.assertEqual(code_of(bench.leggauss_dec, 65), "INVALID_GL_N")
        xs1, ws1 = bench.leggauss_dec(1)
        self.assertEqual((len(xs1), ws1[0]), (1, Decimal(2)))
        xs64, ws64 = bench.leggauss_dec(64)
        self.assertEqual(len(xs64), 64)
        self.assertEqual(len(ws64), 64)
        self.assertEqual(code_of(bench.halton_dec, "2", 2), "INVALID_HALTON_N")
        self.assertEqual(code_of(bench.halton_dec, 0, 2), "INVALID_HALTON_N")
        self.assertEqual(code_of(bench.halton_dec, 2, "2"), "INVALID_HALTON_BASE")
        self.assertEqual(code_of(bench.halton_dec, 2, 0), "INVALID_HALTON_BASE")
        self.assertEqual(bench.halton_dec(1, 2), [Decimal("0.5")])

    def test_oracle_require_json_and_hodge_guards(self):
        self.assertEqual(code_of(oracle.require_bool, 1, "x"), "INVALID_BOOL")
        self.assertIs(oracle.require_bool(True, "x"), True)
        self.assertEqual(code_of(oracle.require_exact_int, False, "x"), "INVALID_INT")
        self.assertEqual(oracle.require_exact_int(5, "x", lo=5, hi=5), 5)
        self.assertEqual(code_of(oracle.require_exact_int, 4, "x", lo=5), "INT_OUT_OF_RANGE")
        self.assertEqual(code_of(oracle.require_exact_int, 6, "x", hi=5), "INT_OUT_OF_RANGE")
        self.assertEqual(code_of(oracle.require_exact_str, 1, "x"), "INVALID_STR")
        self.assertEqual(code_of(oracle.require_hex64, "a" * 63, "x"), "INVALID_HEX64")
        self.assertEqual(code_of(oracle.require_hex64, "A" * 64, "x"), "INVALID_HEX64")
        self.assertEqual(oracle.require_hex64("a" * 64, "x"), "a" * 64)
        self.assertEqual(code_of(oracle.require_ok, 1, "C", "d"), "C")
        deep = []
        cur = deep
        for _ in range(31):
            nxt = []
            cur.append(nxt)
            cur = nxt
        oracle.validate_strict_json_tree([deep])
        self.assertEqual(code_of(oracle.validate_strict_json_tree, [[deep]]), "JSON_DEPTH_EXCEEDED")
        oracle.validate_strict_json_tree((1 << 2048) - 1)
        self.assertEqual(code_of(oracle.validate_strict_json_tree, 1 << 2048), "INT_BIT_LIMIT")
        self.assertEqual(code_of(oracle.validate_strict_json_tree, {1: 2}), "INVALID_JSON_KEY")
        self.assertEqual(code_of(oracle.validate_strict_json_tree, {"a": Fraction(1, 2)}), "FORBIDDEN_JSON_TYPE")
        oracle.validate_strict_json_tree({"a": None, "b": False, "c": "s", "d": [1]})
        self.assertEqual(code_of(oracle.fmt_q, 1), "INVALID_FRACTION")
        self.assertEqual(oracle.fmt_q(Fraction(4)), "4")
        self.assertEqual(oracle.fmt_q(Fraction(-3, 5)), "-3/5")
        self.assertEqual(code_of(oracle.fmt_dec_q, 1, 2), "INVALID_FRACTION")
        self.assertEqual(code_of(oracle.fmt_dec_q, Fraction(1), 19), "INT_OUT_OF_RANGE")
        self.assertEqual(oracle.fmt_dec_q(Fraction(-1, 3), 3), "-0.333")
        self.assertEqual(oracle.fmt_dec_q(Fraction(5, 2), 0), "3")
        self.assertEqual(oracle.fmt_dec_q(Fraction(1, 8), 2), "0.13")
        self.assertEqual(code_of(oracle.exact_hodge_split, (), ()), "EMPTY_VEC")
        self.assertEqual(code_of(oracle.exact_hodge_split, (Fraction(1),), (Fraction(1), Fraction(2))), "DIM_MISMATCH")
        self.assertEqual(code_of(oracle.exact_hodge_split, (Fraction(0),), (Fraction(1),)), "ZERO_REF_VEC")
        sp1 = oracle.exact_hodge_split((Fraction(1),), (Fraction(2),))
        self.assertEqual(sp1["norm_sq_perp"], Fraction(0))


class Test03ExactScienceChecks(unittest.TestCase):
    def test_pillars_and_honest_h2b_grading(self):
        p1 = PAYLOAD["pillar1_sphere_unit_and_qpi"]
        self.assertIs(p1["g_sphere_unit_strictly_decreasing"], True)
        self.assertIs(p1["all_even_dims_ball_beats_cube"], True)
        self.assertIs(p1["all_area_over_vol_equals_dim"], True)
        p2 = PAYLOAD["pillar2_em_hodge_splitting"]
        self.assertIs(p2["all_pythagorean"], True)
        self.assertIs(p2["all_orthogonal"], True)
        self.assertIs(p2["all_radial_rescaling_invariant"], True)
        self.assertIs(p2["all_radial_warp_zero_transverse"], True)
        p3 = PAYLOAD["pillar3_denom_pi_eq_and_slots"]
        self.assertIs(p3["all_hopf_mean_u_half"], True)
        self.assertIs(p3["all_hopf_mean_1_minus_u_half"], True)
        self.assertIs(p3["all_hopf_3s_quadratic_exact"], True)
        self.assertEqual(p3["hopf_3s_error_ratio_a4_to_a8_q"], "4")
        p4 = PAYLOAD["pillar4_thin_shell_and_coxeter"]
        self.assertIs(p4["thin_shell_cv_sq_strictly_decreasing"], True)
        cw = p4["coxeter_weyl_orders"]
        self.assertEqual((cw["W_B8"], cw["W_E8"], cw["index_W_E8_over_W_D8"]), (10321920, 696729600, 135))
        p5 = PAYLOAD["pillar5_h2b_physics_benchmarks"]
        gr = p5["grading"]
        self.assertEqual(gr["verdict"], "PARTIAL")
        self.assertIs(gr["eq_beats_unweighted_numpi_ge_3x"], True)
        self.assertIs(gr["eq_beats_unweighted_cartesian_ge_3x"], True)
        self.assertIs(gr["tensor_eq_beats_jacobian_weighted_numpi_ge_3x"], False)
        self.assertIs(gr["fibonacci_equal_area_beats_sinweight_flux_ge_3x"], True)
        self.assertIs(gr["hopf_eq_s3_1s2s2p_exact_zero_all_n"], True)
        self.assertEqual(gr["hopf_eq_s3_n123_256_to_1024_scaling_factor"], "4.0000")
        c600 = p5["s3_600cell_11design_control"]
        self.assertEqual((c600["n_nodes"], c600["h_1s2s2p_rms"], c600["h_n123_rms"]), (120, "0", "0"))


class Test04ZoneBIO(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = Path(self._td.name)
        self._cwd = os.getcwd()
        self._pwd = os.environ.get("PWD")

    def tearDown(self):
        os.chdir(self._cwd)
        if self._pwd is None:
            os.environ.pop("PWD", None)
        else:
            os.environ["PWD"] = self._pwd
        for p in self.td.rglob("*"):
            if p.is_dir() and not p.is_symlink():
                os.chmod(p, 0o700)
        self._td.cleanup()

    def mk(self, name, data=b"abc"):
        p = self.td / name
        p.write_bytes(data)
        return p

    def test_read_write_and_path_guards(self):
        R = verifier.read_regular_bytes_capped
        W = verifier.write_regular_bytes_atomic_0600
        self.assertEqual(code_of(R, "", "x"), "EMPTY_PATH")
        self.assertEqual(code_of(R, "a\x00b", "x"), "NUL_BYTE_FORBIDDEN")
        self.assertEqual(code_of(R, "a\udcff", "x"), "INVALID_UTF8_SURROGATE")
        self.assertEqual(code_of(R, 5, "x"), "INVALID_STR")
        self.assertEqual(code_of(R, self.mk("f"), "x", max_bytes=0), "INT_OUT_OF_RANGE")
        self.assertEqual(R(self.mk("g"), "x"), b"abc")
        os.symlink(self.mk("t"), self.td / "lnk")
        self.assertEqual(code_of(R, self.td / "lnk", "x"), "SYMLINK_IN_PATH")
        (self.td / "real").mkdir()
        self.mk("real/f")
        os.symlink(self.td / "real", self.td / "dlink")
        self.assertEqual(code_of(R, self.td / "dlink" / "f", "x"), "SYMLINK_IN_PATH")
        self.assertEqual(code_of(R, self.td / "missing" / "f", "x"), "IO_OPEN_ERROR")
        self.assertEqual(R(os.path.relpath(self.mk("relf"), os.getcwd()), "x"), b"abc")
        with mock.patch.object(verifier.os, "lstat", side_effect=PermissionError("no")):
            self.assertEqual(code_of(R, self.mk("h"), "x"), "IO_STAT_ERROR")
        with mock.patch.object(verifier.os, "getcwd", side_effect=FileNotFoundError("gone")):
            self.assertEqual(code_of(R, self.mk("f2"), "x"), "CWD_ERROR")
        os.chdir(self.td / "real")
        os.environ["PWD"] = str(self.td / "dlink")
        self.assertEqual(code_of(R, self.mk("f3"), "x"), "SYMLINK_IN_PATH")
        os.environ["PWD"] = str(self.td / "real")
        self.assertEqual(R(self.td / "f3", "x"), b"abc")
        os.environ["PWD"] = str(self.td / "nonexistent-dir")
        self.assertEqual(R(self.td / "f3", "x"), b"abc")
        os.environ["PWD"] = "relative"
        self.assertEqual(R(self.td / "f3", "x"), b"abc")
        os.environ["PWD"] = str(self.td)
        self.assertEqual(R(self.td / "f3", "x"), b"abc")
        self.assertEqual(code_of(R, self.td, "x"), "NOT_REGULAR_FILE")
        os.mkfifo(self.td / "fifo")
        self.assertEqual(code_of(R, self.td / "fifo", "x"), "NOT_REGULAR_FILE")
        os.link(self.mk("a"), self.td / "b")
        self.assertEqual(code_of(R, self.td / "a", "x"), "HARDLINK_FORBIDDEN")
        self.assertEqual(R(self.mk("ten", b"0123456789"), "x", max_bytes=10), b"0123456789")
        self.assertEqual(code_of(R, self.mk("eleven", b"0123456789A"), "x", max_bytes=10), "FILE_TOO_LARGE")
        self.assertEqual(code_of(R, f"/proc/{os.getpid()}/status", "x", max_bytes=8), "FILE_STREAM_TOO_LARGE")
        with mock.patch.object(verifier.os, "read", side_effect=OSError("eio")):
            self.assertEqual(code_of(R, self.mk("r"), "x"), "IO_READ_ERROR")
        self.assertEqual(code_of(W, self.td / "o", "s", "x"), "INVALID_BYTES")
        self.assertEqual(code_of(W, self.td / "nodir" / "o", b"d", "x"), "PARENT_MISSING")
        self.mk("file")
        self.assertEqual(code_of(W, self.td / "file" / "o", b"d", "x"), "PARENT_NOT_DIR")
        (self.td / "adir").mkdir()
        self.assertEqual(code_of(W, self.td / "adir", b"d", "x"), "TARGET_NOT_REGULAR")
        os.link(self.mk("h1"), self.td / "h2")
        self.assertEqual(code_of(W, self.td / "h1", b"d", "x"), "HARDLINK_FORBIDDEN")
        out = W(self.td / "new.json", b"payload", "x")
        self.assertEqual(stat.S_IMODE(os.stat(out).st_mode), 0o600)
        W(self.td / "new.json", b"second", "x")
        self.assertEqual((self.td / "new.json").read_bytes(), b"second")
        with mock.patch.object(verifier.os, "fsync", side_effect=OSError("eio")):
            self.assertEqual(code_of(W, self.td / "fail.json", b"d", "x"), "IO_WRITE_ERROR")
        (self.td / "ro").mkdir()
        os.chmod(self.td / "ro", 0o500)
        self.assertEqual(code_of(W, self.td / "ro" / "o", b"d", "x"), "IO_OPEN_ERROR")

    def test_strict_json_parser(self):
        P = verifier.parse_strict_json_bytes
        self.assertEqual(code_of(P, "{}", "x"), "INVALID_BYTES")
        big = b'"' + b"a" * (verifier.MAX_JSON_BYTES - 3) + b'"\n'
        self.assertEqual(P(big, "x"), "a" * (verifier.MAX_JSON_BYTES - 3))
        self.assertEqual(code_of(P, big + b" ", "x"), "JSON_TOO_LARGE")
        self.assertEqual(code_of(P, '{"a":"\u00e9"}\n'.encode("utf-8"), "x"), "NON_ASCII_JSON")
        self.assertEqual(code_of(P, b'{"a":' + b"1" * 81 + b"}\n", "x"), "JSON_INT_TOO_LARGE")
        self.assertEqual(P(b'{"a":' + b"1" * 80 + b"}\n", "x"), {"a": int("1" * 80)})
        self.assertEqual(code_of(P, b'{"a":1,"a":2}\n', "x"), "DUPLICATE_JSON_KEY")
        self.assertEqual(code_of(P, b'{"a":1.5}\n', "x"), "FORBIDDEN_JSON_FLOAT")
        self.assertEqual(code_of(P, b'{"a":NaN}\n', "x"), "FORBIDDEN_JSON_CONST")
        self.assertEqual(code_of(P, b'{"a":', "x"), "INVALID_JSON")
        self.assertEqual(code_of(P, b"[" * 100000, "x"), "INVALID_JSON")
        self.assertEqual(code_of(P, b'{"a": 1}\n', "x"), "NON_CANONICAL_JSON")


POCS: tuple[tuple[str, str], ...] = (
    ("R01_STRING_OR_GUILLEMET", 'def s := "x"'),
    ("R01_STRING_OR_GUILLEMET", "def c : Char := '\"'\ntheorem t : (1:Nat) = 2 := sorry\ndef d : Char := '\"'"),
    ("R01_STRING_OR_GUILLEMET", "def b : Bool := !'\"'.isDigit\ntheorem t : False := sorry\ndef z : Char := '\"'"),
    ("R01_STRING_OR_GUILLEMET", 'def r := r#"\\"#\ntheorem t : False := sorry'),
    ("R01_STRING_OR_GUILLEMET", 'def s := s!"x"'),
    ("R01_STRING_OR_GUILLEMET", 'def «"» := 1'),
    ("R01_STRING_OR_GUILLEMET", "def «weird» := 1"),
    ("R02_SORRY_ADMIT_AXIOM", "theorem t : False := sorry"),
    ("R02_SORRY_ADMIT_AXIOM", "theorem t : False := _root_.sorryAx False"),
    ("R02_SORRY_ADMIT_AXIOM", "axiom bad : False"),
    ("R02_SORRY_ADMIT_AXIOM", "theorem t : False := by admit"),
    ("R03_UNSAFE_PARTIAL_OPAQUE_VIS", "partial def f : Nat → Nat := f"),
    ("R03_UNSAFE_PARTIAL_OPAQUE_VIS", "opaque c : Nat"),
    ("R03_UNSAFE_PARTIAL_OPAQUE_VIS", "unsafe def g : Nat := 0"),
    ("R03_UNSAFE_PARTIAL_OPAQUE_VIS", "private theorem p : True := trivial"),
    ("R03_UNSAFE_PARTIAL_OPAQUE_VIS", "protected theorem p : True := trivial"),
    ("R03_UNSAFE_PARTIAL_OPAQUE_VIS", "noncomputable def c : Nat := 0"),
    ("R04_KERNEL_BYPASS_PANIC", "theorem t : 1 = 1 := by native_decide"),
    ("R04_KERNEL_BYPASS_PANIC", "def f : Nat := panic! (String.ofList [])"),
    ("R04_KERNEL_BYPASS_PANIC", "def f : Nat := panicCore (String.ofList [])"),
    ("R04_KERNEL_BYPASS_PANIC", "def f : Nat := panicWithPosWithDecl m d 1 2 (String.ofList [])"),
    ("R04_KERNEL_BYPASS_PANIC", "def f : Nat := unreachable!"),
    ("R04_KERNEL_BYPASS_PANIC", "theorem t := Lean.ofReduceBool a b h"),
    ("R05_FFI_IMPLEMENTED_BY", "@[implemented_by g] def f : Nat := 0"),
    ("R05_FFI_IMPLEMENTED_BY", "@[csimp] theorem c : f = g := rfl"),
    ("R06_INITIALIZE", "initialize r : IO.Ref Nat ← IO.mkRef 0"),
    ("R06_INITIALIZE", "builtin_initialize foo"),
    ("R07_INIT_ATTRIBUTE", "@[init g] def f : IO Unit := pure ()"),
    ("R07_INIT_ATTRIBUTE", "@[simp, builtin_init g] def f : Nat := 0"),
    ("R07_INIT_ATTRIBUTE", "attribute [init g] f"),
    ("R08_EXPORT", "@[export lean_f] def f : Nat := 0"),
    ("R08_EXPORT", "export Nat (succ)"),
    ("R09_METAPROGRAMMING", "macro_rules | `(x) => `(y)"),
    ("R09_METAPROGRAMMING", "declare_syntax_cat foo"),
    ("R09_METAPROGRAMMING", "elab_rules : tactic | _ => pure ()"),
    ("R09_METAPROGRAMMING", "@[term_elab foo] def f : Nat := 0"),
    ("R09_METAPROGRAMMING", "@[command_elab foo] def f : Nat := 0"),
    ("R09_METAPROGRAMMING", "@[tactic foo] def f : Nat := 0"),
    ("R09_METAPROGRAMMING", "@[builtin_macro foo] def f : Nat := 0"),
    ("R10_NOTATION", "notation a \u2295 b => a + b"),
    ("R11_IMPORT", "import Lean"),
    ("R12_SET_OPTION", "set_option maxHeartbeats 0 in"),
    ("R13_DEBUG_WARN_OPTIONS", "x debug.terminalTacticsAsSorry y"),
    ("R13_DEBUG_WARN_OPTIONS", "x warn.sorry y"),
    ("R14_DBG_BUILTINS", "def f := dbg_trace 1"),
    ("R14_DBG_BUILTINS", "def f := dbg_sleep 1"),
    ("R14_DBG_BUILTINS", "def f := dbg_stack_trace 1"),
    ("R14_DBG_BUILTINS", "def f := dbgTraceIfShared 1 2"),
    ("R14_DBG_BUILTINS", "def f := dbgSleep 1 fun _ => 0"),
    ("R14_DBG_BUILTINS", "def f := dbgStackTrace fun _ => 0"),
    ("R15_HASH_COMMANDS", "#eval 1"),
    ("R15_HASH_COMMANDS", "#guard_msgs in"),
    ("R15_HASH_COMMANDS", "#guard true"),
    ("R15_HASH_COMMANDS", "#exit"),
    ("R16_PLUS_NATIVE_FLAG", "theorem t : 1 = 1 := by decide +revert +native"),
    ("R17_NATIVE_CONFIG", "theorem t : 1 = 1 := by decide (config := { native := true })"),
    ("R17_NATIVE_CONFIG", "theorem t : 1 = 1 := by decide (native := true)"),
    ("R18_MULTILINE_DECIDE", "theorem t : 1 = 1 := by decide\n  (kernel := true)"),
)

CLEAN_CONTROLS: tuple[str, ...] = (
    "theorem partially_ordered_ok : True := trivial",
    "theorem native_ok : True := trivial",
    "theorem t : 1 = 1 := by decide\n\ntheorem u : True := trivial",
    "-- sorry, axiom, partial, panic!, #eval in a line comment\ntheorem t : True := trivial",
    "/- block: import Lean, set_option, dbg_trace -/ theorem t : True := trivial",
    "theorem exported_value : True := trivial",
    "def initializer_count : Nat := 0",
    "@[simp] theorem tactic_free_simp_lemma : True := trivial",
    "theorem my_panic_free : True := trivial",
)


class Test05LeanR12AndMockedLive(unittest.TestCase):
    def setUp(self):
        self._env = mock.patch.dict(os.environ, {}, clear=False)
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def test_static_18_rules_and_clean_controls(self):
        covered = set()
        for rid, src in POCS:
            hits = verifier.lean4_rule_hits(src)
            self.assertIn(rid, hits, f"{rid} missed {src!r}")
            covered.add(rid)
            self.assertEqual(code_of(verifier.static_gate_lean4_source, LEAN_SRC + "\n" + src + "\n"), "LEAN4_TRUST_ESCAPE")
        self.assertEqual(covered, {rid for rid, _ in verifier.LEAN4_RULES})
        for src in CLEAN_CONTROLS:
            self.assertEqual(verifier.lean4_rule_hits(src), [], src)
        G = verifier.static_gate_lean4_source
        self.assertEqual(code_of(G, LEAN_SRC + "\r"), "LEAN4_BAD_CHARS")
        self.assertEqual(code_of(G, LEAN_SRC + "\x00"), "LEAN4_BAD_CHARS")
        self.assertEqual(code_of(G, LEAN_SRC + "\n/- open"), "LEAN4_UNTERMINATED_COMMENT")
        self.assertEqual(code_of(G, LEAN_SRC + "\n#print Nat\n"), "LEAN4_BAD_PRINT")
        last = f"#print axioms {oracle.LEAN_THEOREM_NAMES[-1]}\n"
        self.assertEqual(code_of(G, LEAN_SRC.replace(last, "")), "LEAN4_PRINT_SET_MISMATCH")
        self.assertEqual(code_of(G, LEAN_SRC.replace("theorem fact_pos ", "theorem fact_pos_x ")), "LEAN4_MISSING_THEOREM")
        S = verifier.strip_lean4_comments
        self.assertEqual(S("a -- b\nc"), "a \nc")
        self.assertEqual(S("a -- b"), "a ")
        self.assertEqual(S("x -/ y"), "x -/ y")
        self.assertEqual(S("/- a /- b -/ c -/d"), "d")
        self.assertEqual(S("/- a\nb -/c"), "\nc")
        self.assertEqual(S("/- -- -/ok"), "ok")

    def test_resolve_scrub_and_mocked_live(self):
        os.environ["ALETHEIA_LEAN_BIN"] = "/nonexistent/lean-bin"
        self.assertEqual(code_of(verifier.resolve_lean_binary), "LEAN_BINARY_NOT_FILE")
        with tempfile.TemporaryDirectory() as td:
            os.environ["ALETHEIA_LEAN_BIN"] = td
            self.assertEqual(code_of(verifier.resolve_lean_binary), "LEAN_BINARY_NOT_FILE")
            f = Path(td) / "lean"
            f.write_bytes(b"x")
            os.chmod(f, 0o600)
            os.environ["ALETHEIA_LEAN_BIN"] = str(f)
            self.assertEqual(code_of(verifier.resolve_lean_binary), "LEAN_BINARY_NOT_EXECUTABLE")
            os.chmod(f, 0o700)
            self.assertEqual(verifier.resolve_lean_binary(), str(f))
        os.environ["ALETHEIA_LEAN_BIN"] = ""
        with mock.patch.object(verifier.shutil, "which", return_value=None):
            self.assertEqual(code_of(verifier.resolve_lean_binary), "LEAN_BINARY_UNAVAILABLE")
        with mock.patch.object(verifier.shutil, "which", return_value="/opt/lean"):
            self.assertEqual(verifier.resolve_lean_binary(), "/opt/lean")
        for k in ("LEAN_PATH", "LEAN_OPTS", "LEAN_SRC_PATH", "LEAN_CC", "LEAN_SYSROOT", "ELAN_TOOLCHAIN", "ELAN_HOME", "LAKE_HOME", "LD_PRELOAD"):
            os.environ[k] = "/evil"
        env = verifier.scrubbed_lean_env()
        for k in ("LEAN_PATH", "LEAN_OPTS", "LEAN_SRC_PATH", "LEAN_CC", "LEAN_SYSROOT", "ELAN_TOOLCHAIN", "ELAN_HOME", "LAKE_HOME", "LD_PRELOAD"):
            self.assertNotIn(k, env)

        good = axiom_stdout(oracle.LEAN_THEOREM_NAMES)

        def run_m(outs):
            with mock.patch.object(verifier, "resolve_lean_binary", return_value="lean"), \
                    mock.patch.object(verifier.subprocess, "run", side_effect=outs):
                return code_of(verifier.verify_lean4_file_live, LEAN_PATH)

        self.assertEqual(run_m([completed(0, GOOD_VERSION), completed(0, good)]), "NO_ERROR")
        self.assertEqual(run_m([completed(1, GOOD_VERSION), completed(0, good)]), "LEAN_VERSION_MISMATCH")
        self.assertEqual(run_m([completed(0, "Lean (version 4.35.0, x)\n"), completed(0, good)]), "LEAN_VERSION_MISMATCH")
        self.assertEqual(run_m([completed(0, GOOD_VERSION), completed(1, good)]), "LEAN_COMPILE_FAIL")
        self.assertEqual(run_m([completed(0, GOOD_VERSION), completed(0, good, "err")]), "LEAN_STDERR_NONEMPTY")
        self.assertEqual(run_m([completed(0, GOOD_VERSION), completed(0, good + "<stdin>:1:1: warning: x\n")]), "LEAN_WARNING_FORBIDDEN")
        self.assertEqual(run_m(OSError("noexec")), "LEAN_EXEC_ERROR")
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "Bad.lean"
            bad.write_bytes(b"\xff\xfe")
            self.assertEqual(code_of(verifier.verify_lean4_file_live, bad), "INVALID_UTF8")
        names = oracle.LEAN_THEOREM_NAMES
        P = verifier.parse_lean_axiom_output
        wrapped = axiom_stdout(names[1:]) + f"'{names[0]}' depends on axioms: [propext,\n Quot.sound]\n"
        self.assertEqual(P(wrapped)[names[0]], ["propext", "Quot.sound"])
        self.assertEqual(code_of(P, axiom_stdout(names) + "junk\n"), "LEAN_UNEXPECTED_STDOUT")
        self.assertEqual(code_of(P, axiom_stdout(names) + axiom_stdout(names[:1])), "LEAN_DUPLICATE_THEOREM")
        bad_ax = axiom_stdout(names[1:]) + f"'{names[0]}' depends on axioms: [propext, Classical.choice]\n"
        self.assertEqual(code_of(P, bad_ax), "LEAN_FORBIDDEN_AXIOM")
        self.assertEqual(code_of(P, axiom_stdout(names[1:])), "LEAN_THEOREM_SET_MISMATCH")
        trunc = axiom_stdout(names[1:]) + f"'{names[0]}' depends on axioms: [propext,"
        self.assertEqual(code_of(P, trunc), "LEAN_UNEXPECTED_STDOUT")


SEMANTIC_TAMPERS: tuple[tuple[tuple, object, str], ...] = (
    (("pillar1_sphere_unit_and_qpi", "pi_rational_bracket", "lo_q"), "3", "SEC_PI_LO"),
    (("pillar1_sphere_unit_and_qpi", "pi_rational_bracket", "lo_q"), "9" * 4500 + "/1", "INVALID_RATIONAL_STR"),
    (("pillar1_sphere_unit_and_qpi", "pi_rational_bracket", "hi_q"), "3", "SEC_PI_HI"),
    (("pillar1_sphere_unit_and_qpi", "all_even_dims_ball_beats_cube"), False, "SEC_ZADOR_ALL"),
    (("pillar1_sphere_unit_and_qpi", "even_dimensions", 3, "g_sphere_unit_q"), "1/8", "SEC_G8"),
    (("pillar2_em_hodge_splitting", "all_pythagorean"), False, "SEC_HODGE_PYTH"),
    (("pillar2_em_hodge_splitting", "all_orthogonal"), False, "SEC_HODGE_ORTH"),
    (("pillar2_em_hodge_splitting", "all_radial_rescaling_invariant"), False, "SEC_HODGE_RESCALE"),
    (("pillar3_denom_pi_eq_and_slots", "all_hopf_mean_u_half"), False, "SEC_HOPF_U"),
    (("pillar3_denom_pi_eq_and_slots", "all_hopf_3s_quadratic_exact"), False, "SEC_HOPF_3S"),
    (("pillar3_denom_pi_eq_and_slots", "hopf_3s_error_ratio_a4_to_a8_q"), "2", "SEC_HOPF_4X"),
    (("pillar4_thin_shell_and_coxeter", "thin_shell_cv_sq_strictly_decreasing"), False, "SEC_THIN_SHELL"),
    (("pillar4_thin_shell_and_coxeter", "coxeter_weyl_orders", "W_B8"), 10321921, "SEC_WB8"),
    (("pillar4_thin_shell_and_coxeter", "coxeter_weyl_orders", "W_E8"), 696729601, "SEC_WE8"),
    (("pillar4_thin_shell_and_coxeter", "coxeter_weyl_orders", "index_W_E8_over_W_D8"), 134, "SEC_WE8_INDEX"),
    (("pillar5_h2b_physics_benchmarks", "grading", "verdict"), "CONFIRMED", "SEC_H2B_VERDICT"),
    (("pillar5_h2b_physics_benchmarks", "grading", "eq_beats_unweighted_numpi_ge_3x"), False, "SEC_H2B_UNW"),
    (("pillar5_h2b_physics_benchmarks", "grading", "tensor_eq_beats_jacobian_weighted_numpi_ge_3x"), True, "SEC_H2B_VERDICT"),
    (("pillar5_h2b_physics_benchmarks", "grading", "hopf_eq_s3_1s2s2p_exact_zero_all_n"), False, "SEC_H2B_HOPF0"),
    (("pillar5_h2b_physics_benchmarks", "grading", "hopf_eq_s3_n123_256_to_1024_scaling_factor"), "9" * 4500 + ".0000", "INVALID_DEC_STR"),
    (("pillar5_h2b_physics_benchmarks", "s3_600cell_11design_control", "poisson_rms"), "bad", "INVALID_SCI_STR"),
    (("prior_art", 0), "forged narrative", "SEC_PAYLOAD_PIN_MISMATCH"),
    (("scope", "gpu_touch"), 1, "SEC_PAYLOAD_PIN_MISMATCH"),
)


class Test06SecFr0Fr1AndCLI(unittest.TestCase):
    def test_envelope_type_confusion_and_semantic_forgeries(self):
        V = verifier.verify_certificate_dict
        self.assertIs(V(copy.deepcopy(CERT), full_replay=False)["valid"], True)
        with mock.patch.object(verifier, "verify_lean4_file_live", return_value=dict(FAKE_LIVE)):
            self.assertEqual(V(copy.deepcopy(CERT), full_replay=True)["lean_live"]["theorems_verified"], 34)
        self.assertEqual(code_of(V, copy.deepcopy(CERT), full_replay=1), "INVALID_BOOL")
        self.assertEqual(code_of(V, [], full_replay=False), "INVALID_CERT_TYPE")
        c = copy.deepcopy(CERT)
        c["extra"] = 1
        self.assertEqual(code_of(V, c, full_replay=False), "KEYSET_MISMATCH")
        for key in ("schema_version", "track_id"):
            c = copy.deepcopy(CERT)
            c[key] = "forged"
            self.assertEqual(code_of(V, c, full_replay=False), "SCHEMA_MISMATCH")
        c = copy.deepcopy(CERT)
        c["payload_sha256"] = "0" * 64
        self.assertEqual(code_of(V, c, full_replay=False), "PAYLOAD_SHA_MISMATCH")
        c = copy.deepcopy(CERT)
        c["certificate_sha256"] = "0" * 64
        self.assertEqual(code_of(V, c, full_replay=False), "CERT_SHA_MISMATCH")
        self.assertEqual(code_of(verifier.secondary_audit_payload, []), "INVALID_PAYLOAD_TYPE")
        p = copy.deepcopy(PAYLOAD)
        del p["scope"]
        self.assertEqual(code_of(verifier.secondary_audit_payload, p), "KEYSET_MISMATCH")

        for bad_mut in (
            lambda d: d.__setitem__("pillar1_sphere_unit_and_qpi", None),
            lambda d: d["pillar1_sphere_unit_and_qpi"].__setitem__("even_dimensions", []),
            lambda d: d["pillar4_thin_shell_and_coxeter"]["coxeter_weyl_orders"].pop("W_E8"),
            lambda d: d["scope"].__setitem__("gpu_touch", False),
        ):
            p = copy.deepcopy(PAYLOAD)
            bad_mut(p)
            self.assertEqual(code_of(verifier.secondary_audit_payload, p), "SEC_SHAPE_MISMATCH")
            self.assertEqual(code_of(V, resign(p), full_replay=False), "SEC_SHAPE_MISMATCH")

        for path, val, code in SEMANTIC_TAMPERS:
            p = copy.deepcopy(PAYLOAD)
            set_path(p, path, val)
            self.assertEqual(code_of(verifier.secondary_audit_payload, p), code, path)
            self.assertEqual(code_of(V, resign(p), full_replay=False), code, path)
            with mock.patch.object(verifier, "verify_lean4_file_live", return_value=dict(FAKE_LIVE)):
                self.assertEqual(code_of(V, resign(p), full_replay=True), code, path)

        self.assertEqual(verifier.strict_deep_equal({"a": [1]}, {"a": [True]}), "payload.a[0]")
        self.assertEqual(verifier.strict_deep_equal({"a": 1}, {"b": 1}), "payload")
        self.assertEqual(verifier.strict_deep_equal([1, 2], [1]), "payload")
        self.assertEqual(verifier.strict_shape_match({"a": 1}, {"b": 1}), "payload")
        self.assertEqual(verifier.strict_shape_match([1, 2], [1]), "payload")
        self.assertIsNot(verifier.expected_payload(), verifier.expected_payload())

    def test_every_leaf_resigned_tamper_rejected(self):
        paths = list(leaf_paths(PAYLOAD))
        self.assertEqual(len(paths), 690)
        p = copy.deepcopy(PAYLOAD)
        bypasses = []
        for path, v in paths:
            set_path(p, path, tamper_value(v))
            if code_of(verifier.secondary_audit_payload, p) == "NO_ERROR":
                bypasses.append(("SEC", path))
            if code_of(verifier.verify_certificate_dict, resign(p), full_replay=False) == "NO_ERROR":
                bypasses.append(("FR0", path))
            set_path(p, path, v)
        self.assertEqual(bypasses, [])
        self.assertEqual(p, PAYLOAD)

    def test_track_artifacts_external_pins_and_cli(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            for name in (oracle.LEAN_SOURCE_NAME, "lean-toolchain", "lakefile.toml"):
                shutil.copyfile(_THIS_DIR / name, t / name)
            with mock.patch.object(verifier, "verify_lean4_file_live", return_value=dict(FAKE_LIVE)):
                self.assertIs(verifier.verify_certificate_dict(copy.deepcopy(CERT), full_replay=True, track_dir=t)["valid"], True)
                (t / "lean-toolchain").write_bytes(b"leanprover/lean4:v4.35.0\n")
                self.assertEqual(code_of(verifier._load_track_artifacts, t), "TOOLCHAIN_MISMATCH")
                shutil.copyfile(_THIS_DIR / "lean-toolchain", t / "lean-toolchain")
                (t / "lakefile.toml").write_bytes(b'name = "x"\n')
                self.assertEqual(code_of(verifier._load_track_artifacts, t), "LAKEFILE_SHA_MISMATCH")
                shutil.copyfile(_THIS_DIR / "lakefile.toml", t / "lakefile.toml")
            with mock.patch.object(verifier, "verify_lean4_file_live", return_value=dict(FAKE_LIVE, lean_source_sha256="0" * 64)):
                self.assertEqual(code_of(verifier._load_track_artifacts, t), "LEAN_SHA_MISMATCH")
            (t / "f.md").write_bytes(b"hello")
            row = ("P1", "f.md", 5, oracle.sha256_hex(b"hello"))
            with mock.patch.object(oracle, "EXTERNAL_PINS", (row,)):
                self.assertEqual(verifier.verify_external_pins(str(t))["external_pins_verified"], 1)
                (t / "f.md").write_bytes(b"hello!")
                self.assertEqual(code_of(verifier.verify_external_pins, str(t)), "EXT_PIN_BYTES")
                (t / "f.md").write_bytes(b"jello")
                self.assertEqual(code_of(verifier.verify_external_pins, str(t)), "EXT_PIN_SHA")
        A = verifier._parse_cli_args
        self.assertEqual(A([]), {"mode": "default", "target": None, "as_json": False})
        self.assertEqual(code_of(A, ["--json", "--json"]), "DUPLICATE_FLAG")
        self.assertEqual(code_of(A, ["--standalone", "--standalone"]), "CONFLICTING_MODE")
        self.assertEqual(code_of(A, ["--check", "a", "--standalone"]), "CONFLICTING_MODE")
        self.assertEqual(code_of(A, ["--check", "a", "--write", "b"]), "CONFLICTING_MODE")
        self.assertEqual(code_of(A, ["--bogus"]), "UNKNOWN_FLAG")
        self.assertEqual(code_of(A, ["--check"]), "MISSING_PATH_ARG")
        self.assertEqual(code_of(A, ["--check", "-x"]), "INVALID_PATH_ARG")

        def run_main(argv):
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(verifier.sys, "stdout", out), mock.patch.object(verifier.sys, "stderr", err):
                rc = verifier.main(argv)
            return rc, out.getvalue(), err.getvalue()

        with mock.patch.object(oracle, "build_certificate", side_effect=lambda: copy.deepcopy(CERT)):
            rc, out, _ = run_main(["--standalone"])
            self.assertEqual((rc, out), (0, oracle.canonical_json_bytes(CERT).decode("ascii")))
            rc, _, err = run_main(["--bogus"])
            self.assertEqual((rc, json.loads(err)["code"]), (2, "UNKNOWN_FLAG"))
            with tempfile.TemporaryDirectory() as td:
                t = Path(td)
                (t / "f.md").write_bytes(b"x")
                row = ("P1", "f.md", 1, oracle.sha256_hex(b"x"))
                with mock.patch.object(oracle, "EXTERNAL_PINS", (row,)):
                    self.assertEqual(run_main(["--verify-pins", str(t)])[:2], (0, "PINS_OK external=1\n"))
                    self.assertEqual(json.loads(run_main(["--json", "--verify-pins", str(t)])[1])["status"], "PINS_VERIFIED")
                with mock.patch.object(verifier, "verify_lean4_file_live", return_value=dict(FAKE_LIVE)):
                    rc, out, _ = run_main(["--write", str(t / "cert.json")])
                    self.assertEqual(rc, 0)
                    self.assertIn(CERT["certificate_sha256"], out)
                    rc, out, _ = run_main(["--json", "--write", str(t / "cert2.json")])
                    self.assertIs(json.loads(out)["written"], True)
                    rc, out, _ = run_main(["--check", str(t / "cert.json")])
                    self.assertEqual((rc, out), (0, f"OK {oracle.TRACK_ID} cert_sha256={CERT['certificate_sha256']}\n"))
                    rc, out, _ = run_main(["--json"])
                    self.assertIs(json.loads(out)["valid"], True)
                    rc, out, _ = run_main([])
                    self.assertTrue(out.startswith("OK "))


class Test07LiveLeanAndSubprocess(unittest.TestCase):
    def setUp(self):
        self._env = mock.patch.dict(os.environ, {}, clear=False)
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def test_live_lean_kernel_and_init_olean_hijack_immunity(self):
        lean_bin = verifier.resolve_lean_binary()
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            evil_src = t / "Init.lean"
            evil_src.write_text("prelude\ninductive False : Prop\n", encoding="utf-8")
            b_proc = subprocess.run([lean_bin, "-R", str(t), "-o", str(t / "Init.olean"), str(evil_src)],
                                    cwd=str(t), capture_output=True, text=True, timeout=60, check=False,
                                    env=verifier.scrubbed_lean_env())
            self.assertEqual(b_proc.returncode, 0, b_proc.stderr)
            poisoned_env = dict(os.environ, LEAN_PATH=str(t))
            raw_proc = subprocess.run([lean_bin, "--stdin"], input=LEAN_SRC, capture_output=True,
                                      text=True, timeout=60, check=False, env=poisoned_env)
            self.assertNotEqual(raw_proc.returncode, 0)
            os.environ["LEAN_PATH"] = str(t)
            os.environ["LEAN_OPTS"] = "-DwarningAsError=false"
            os.environ["ELAN_TOOLCHAIN"] = "nonexistent-toolchain"
            live = verifier.verify_lean4_file_live(LEAN_PATH)
            self.assertEqual(live["theorems_verified"], 34)
            self.assertEqual(live["lean_source_sha256"], oracle.PINNED_LEAN_SOURCE_SHA256)

    def test_live_oracle_build_and_no_shared_mutable_aliases(self):
        built = oracle.build_certificate()
        self.assertEqual(built, CERT)
        p1 = built["payload"]
        p1["prior_art"].append("mut")
        p1["external_pins"][0]["bytes"] = 0
        p1["pinned_artifacts"]["lean_theorem_names"].append("x")
        p1["pillar1_sphere_unit_and_qpi"]["even_dimensions"][0]["dim"] = 99
        self.assertEqual(oracle.build_payload(), PAYLOAD)

    def test_frozen_certificate_and_subprocess(self):
        cert_p = _THIS_DIR / oracle.CERT_FILE_NAME
        self.assertEqual(cert_p.read_bytes(), oracle.canonical_json_bytes(CERT))
        script = str(_THIS_DIR / "verify_s106_sphere_denom_pi.py")
        proc = subprocess.run([sys.executable, "-I", "-B", script, "--check", str(cert_p)],
                              capture_output=True, text=True, timeout=300, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(CERT["certificate_sha256"], proc.stdout)
        proc = subprocess.run([sys.executable, "-I", "-B", script, "--check", str(_THIS_DIR / "missing.json")],
                              capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(json.loads(proc.stderr)["code"], "IO_OPEN_ERROR")


if __name__ == "__main__":
    unittest.main()
