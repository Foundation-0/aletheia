#!/usr/bin/env python3
"""Aletheia R5 Adversarial, Zone-B, R10+ Lean-Gate & Mutation-Killer Test Suite for Track S86.

100% pure Python 3 stdlib, zero bare asserts, zero AST floats, zero .isdigit(),
zero random imports, scratch os.mkfifo non-regular probes, CI chmod-644 compatible,
and 0-skip Lean-less CI compatible.
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

import s86_sovereign_stack_oracle as oracle  # noqa: E402
import verify_s86_sovereign_stack as verifier  # noqa: E402


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
    p_sha = oracle.sha256_hex(oracle.canonical_json_bytes(c["payload"]))
    c["payload_sha256"] = p_sha
    env = {
        "schema_version": c["schema_version"],
        "track_id": c["track_id"],
        "payload_sha256": p_sha,
        "payload": c["payload"],
    }
    c["certificate_sha256"] = oracle.sha256_hex(oracle.canonical_json_bytes(env))
    return c


def _find_lean_optional() -> str | None:
    try:
        return verifier.resolve_lean_binary()
    except oracle.S86Error:
        return None


class Test01StaticHygieneAndExactOracle(unittest.TestCase):
    def _assert_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S86Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_ast_and_text_hygiene(self) -> None:
        for fname in (
            "s86_sovereign_stack_oracle.py",
            "verify_s86_sovereign_stack.py",
            "test_s86_sovereign_stack_r5.py",
        ):
            raw = (_THIS_DIR / fname).read_bytes()
            self.assertNotIn(b"\r", raw, fname)
            src = raw.decode("utf-8", "strict")
            self.assertNotIn("/" + "home/", src, fname)
            self.assertNotIn("/dev/" + "null", src, fname)
            self.assertNotIn("4-" + "mode", src.lower(), fname)
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

    def test_oracle_primitives_and_bounds(self) -> None:
        self.assertIs(oracle.require_bool(True, "b"), True)
        self.assertIs(oracle.require_bool(False, "b"), False)
        for bad in (0, 1, "true", None):
            self._assert_err("INVALID_BOOL", oracle.require_bool, bad, "b")

        self.assertEqual(oracle.require_exact_int(5, "x", lo=5, hi=5), 5)
        self._assert_err("INVALID_INT", oracle.require_exact_int, True, "x")
        self._assert_err("INVALID_INT", oracle.require_exact_int, _IntSub(5), "x")
        self._assert_err("INT_OUT_OF_RANGE", oracle.require_exact_int, 4, "x", lo=5)
        self._assert_err("INT_OUT_OF_RANGE", oracle.require_exact_int, 6, "x", hi=5)
        big_ok = (1 << oracle.MAX_INT_BITS) - 1
        self.assertEqual(oracle.require_exact_int(big_ok, "x"), big_ok)
        self._assert_err("INT_TOO_LARGE", oracle.require_exact_int, 1 << oracle.MAX_INT_BITS, "x")

        self.assertEqual(oracle.require_exact_str("abc", "s"), "abc")
        self._assert_err("INVALID_STR", oracle.require_exact_str, _StrSub("a"), "s")
        self._assert_err("INVALID_UTF8_SURROGATE", oracle.require_exact_str, "\ud800", "s")

        h64 = "0123456789abcdef" * 4
        self.assertEqual(oracle.require_hex64(h64, "h"), h64)
        self._assert_err("INVALID_HEX64", oracle.require_hex64, h64[:-1], "h")
        self._assert_err("INVALID_HEX64", oracle.require_hex64, "A" + h64[1:], "h")

        self.assertTrue(oracle.is_ascii_digits("0123456789"))
        self.assertFalse(oracle.is_ascii_digits(""))
        self.assertFalse(oracle.is_ascii_digits(123))  # type: ignore[arg-type]
        self.assertFalse(oracle.is_ascii_digits("12a"))
        self.assertFalse(oracle.is_ascii_digits("\u00b2"))

        self.assertEqual(oracle.q_str(Fraction(4, 1)), "4")
        self.assertEqual(oracle.q_str(Fraction(3, 4)), "3/4")
        self.assertEqual(oracle.dec_from_q(Fraction(1, 8), 2), "0.13")
        self.assertEqual(oracle.dec_from_q(Fraction(1, 4), 2), "0.25")
        self.assertEqual(oracle.dec_from_q(Fraction(-1, 8), 2), "-0.13")

        # Strict JSON tree edge cases (shared DAG ok, cycle/depth/subclass rejected)
        shared = [1, 2]
        oracle.validate_strict_json_tree({"a": shared, "b": shared, "n": None, "t": True, "s": "ok"})
        cyc_l: list = []
        cyc_l.append(cyc_l)
        self._assert_err("JSON_CYCLE", oracle.validate_strict_json_tree, cyc_l)
        cyc_d: dict = {}
        cyc_d["self"] = cyc_d
        self._assert_err("JSON_CYCLE", oracle.validate_strict_json_tree, cyc_d)
        deep: Any = 1
        for _ in range(oracle.MAX_JSON_DEPTH):
            deep = [deep]
        oracle.validate_strict_json_tree(deep)
        self._assert_err("JSON_DEPTH_EXCEEDED", oracle.validate_strict_json_tree, [deep])
        self._assert_err("INVALID_JSON_TYPE", oracle.validate_strict_json_tree, _ListSub([1]))
        self._assert_err("INVALID_JSON_TYPE", oracle.validate_strict_json_tree, _DictSub({"a": 1}))
        self._assert_err("INVALID_STR", oracle.validate_strict_json_tree, {1: "a"})

    def test_exact_certificate_and_empirical_cross_parity(self) -> None:
        cert = oracle.build_certificate()
        self.assertEqual(cert["schema_version"], oracle.SCHEMA_VERSION)
        self.assertEqual(cert["track_id"], oracle.TRACK_ID)
        p = cert["payload"]
        p1 = p["pillar1_t3_blowup_cce_det"]
        p2 = p["pillar2_borromean_4way_stack"]
        p3 = p["pillar3_csr_1_over_160_crossover"]
        p4 = p["pillar4_joint_mdl_and_mellin_glu"]

        self.assertEqual(p1["n1024_compression_ratio_dec4"], "5.4051")
        self.assertEqual(p1["n2048_compression_ratio_dec4"], "8.3654")
        self.assertEqual(p1["atomic_cas_divergent_pct_dec2"], "84.28")
        self.assertEqual(p1["atomic_add_divergent_pct_dec2"], "6.15")
        self.assertEqual(p1["perm_asc_vs_desc_pct_dec2"], "7.52")
        self.assertEqual(p1["perm_asc_vs_striped_pct_dec2"], "6.25")
        self.assertEqual(p2["full_r64_5step_loss_drop_pct_dec2"], "49.21")
        self.assertEqual(p2["full_r16_peak_alloc_mib_dec2"], "3632.18")
        self.assertEqual(p2["full_r64_peak_alloc_mib_dec2"], "4893.30")
        self.assertEqual(p2["full_r128_peak_alloc_mib_dec2"], "6594.55")
        self.assertEqual(p3["csr0500_mib_dec2"], "56.86")
        self.assertEqual(p3["csr0500_bpw_overhead_dec4"], "0.1719")
        self.assertEqual(p3["csr0500_sens_frac_pct_dec2"], "31.01")
        self.assertEqual(p3["csr0500_sout_over_sbulk_pct_dec2"], "44.95")
        self.assertEqual(p3["s79_m54_crossover_ratio_dec4"], "0.8624")
        self.assertEqual(p3["csr0500_wt_drop_pct_dec2"], "9.89")
        self.assertEqual(p3["csr0500_py_drop_pct_dec2"], "5.94")
        self.assertEqual(p3["hessian_vs_raw_wt_leverage_dec4"], "2.0288")
        self.assertEqual(p3["hessian_vs_raw_py_leverage_dec4"], "7.6903")
        self.assertEqual(p4["delta_rank_b16"], 1204)
        self.assertEqual(p4["delta_rank_adam64"], 301)
        self.assertEqual(p4["wt_horizon_lift_dec4"], "1.1097")
        self.assertEqual(p4["py_horizon_lift_dec4"], "1.0631")
        self.assertEqual(p4["mellin_rung_share_of_csr_budget_pct_dec2"], "0.61")

        # Cross-verify pinned empirical JSON on disk parses with 0 floats and matches anchors!
        emp_raw = verifier.read_regular_bytes_capped(_THIS_DIR / "rtx3080_s86_empirical_results.json", "emp")
        self.assertEqual(oracle.sha256_hex(emp_raw), oracle.EXPECTED_EMPIRICAL_SHA256)
        emp = verifier.parse_strict_json_bytes(emp_raw, "emp", require_canonical=False)
        self.assertEqual(emp["part1_cce_det_t3_blowup"]["triton_atomic_and_permutation_probe"]["atomic_cas_spinlock"]["max_divergent_rows"], 863)
        self.assertEqual(emp["part2_sovereign_stack"]["eval_arms"]["hessian_csr_0p500pct"]["wikitext2"]["kl_nanonats"], 152175575)
        self.assertEqual(emp["part2_sovereign_stack"]["vram_and_training_ablations"]["full_4way_3bpw_csr0p50_lora_r64_cce_det_run1"]["peak_alloc_bytes"], 5130998272)
        self.assertEqual(emp["part3_mellin_glu_carry_spotcheck"]["regimes"]["a16_blockh4_3p0bpw"]["sensitivity_csr_0p50pct_fp32"]["carry_passes"], 5)

        # Immutable module globals (MappingProxyType) and zero global aliasing across deep vandalism
        with self.assertRaises(TypeError):
            oracle.PINNED_LIVE_ANCHORS["eval_seed"] = 0  # type: ignore[index]
        with self.assertRaises(TypeError):
            oracle.UPSTREAM_CERT_PINS[0]["sha256"] = "0" * 64  # type: ignore[index]
        self.assertIs(type(oracle.PINNED_LIVE_ANCHORS["full_r64_step_losses_nano"]), tuple)
        cert_raw_before = oracle.canonical_json_bytes(cert)
        cert["payload"]["pinned_artifacts"]["lean_theorem_names"].append("evil")
        cert["payload"]["pinned_artifacts"]["upstream_cert_pins"][0]["sha256"] = "0" * 64
        cert["payload"]["pillar2_borromean_4way_stack"]["full_r64_step_losses_nano"].append(0)
        self.assertEqual(oracle.canonical_json_bytes(oracle.build_certificate()), cert_raw_before)


class Test02ZoneBFileIOAndParsers(unittest.TestCase):
    def _assert_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S86Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_parsers_and_rationals(self) -> None:
        raw = b'{"a":1,"b":-5,"c":0}\n'
        self.assertEqual(verifier.parse_strict_json_bytes(raw), {"a": 1, "b": -5, "c": 0})
        self._assert_err("INVALID_BYTES", verifier.parse_strict_json_bytes, "str")  # type: ignore[arg-type]
        self._assert_err("BOM_FORBIDDEN", verifier.parse_strict_json_bytes, b"\xef\xbb\xbf{}\n")
        self._assert_err("CRLF_FORBIDDEN", verifier.parse_strict_json_bytes, b"{}\r\n")
        self._assert_err("INVALID_UTF8", verifier.parse_strict_json_bytes, b"\xff\n")
        self._assert_err("FLOAT_FORBIDDEN", verifier.parse_strict_json_bytes, b'{"a":1.5}\n', require_canonical=False)
        self._assert_err("NONFINITE_JSON_CONSTANT", verifier.parse_strict_json_bytes, b'{"a":NaN}\n', require_canonical=False)
        self._assert_err("DUPLICATE_JSON_KEY", verifier.parse_strict_json_bytes, b'{"a":1,"a":2}\n', require_canonical=False)
        self._assert_err("INVALID_JSON", verifier.parse_strict_json_bytes, b"{bad\n", require_canonical=False)
        self._assert_err("INVALID_ROOT_TYPE", verifier.parse_strict_json_bytes, b"[1,2]\n", require_canonical=False)
        self._assert_err("NONCANONICAL_JSON", verifier.parse_strict_json_bytes, b'{"b": 1, "a": 2}\n', require_canonical=True)

        self._assert_err("INVALID_INT_TOKEN", verifier._parse_bounded_int, "12a")
        max_2048 = (1 << oracle.MAX_INT_BITS) - 1
        self.assertEqual(verifier._parse_bounded_int(str(max_2048)), max_2048)
        self._assert_err("INT_TOO_LARGE", verifier._parse_bounded_int, "9" * 4500)
        self._assert_err("INT_TOO_LARGE", verifier._parse_bounded_int, "9" * (oracle.MAX_INT_DIGITS + 1))
        self._assert_err("NONCANONICAL_INT", verifier._parse_bounded_int, "01")
        self._assert_err("NONCANONICAL_INT", verifier._parse_bounded_int, "-0")
        self._assert_err("INT_TOO_LARGE", verifier._parse_bounded_int, str(1 << oracle.MAX_INT_BITS))

        self.assertEqual(verifier.parse_canonical_rational_str("7", "q"), Fraction(7, 1))
        self.assertEqual(verifier.parse_canonical_rational_str("-3/5", "q"), Fraction(-3, 5))
        self.assertEqual(
            verifier.parse_canonical_rational_str(f"-{max_2048}/{max_2048 - 1}", "q"),
            Fraction(-max_2048, max_2048 - 1),
        )
        self._assert_err("INVALID_RATIONAL", verifier.parse_canonical_rational_str, "", "q")
        self._assert_err("INT_TOO_LARGE", verifier.parse_canonical_rational_str, "1/" + "a" * (2 * oracle.MAX_INT_DIGITS + 1), "q")
        self._assert_err("INT_TOO_LARGE", verifier.parse_canonical_rational_str, "9" * 4500 + "/2", "q")
        self._assert_err("INVALID_RATIONAL", verifier.parse_canonical_rational_str, "1/2/3", "q")
        self._assert_err("INVALID_RATIONAL", verifier.parse_canonical_rational_str, "1/-2", "q")
        self._assert_err("NONCANONICAL_RATIONAL", verifier.parse_canonical_rational_str, "3/1", "q")
        self._assert_err("NONCANONICAL_RATIONAL", verifier.parse_canonical_rational_str, "2/4", "q")

        # Pre-int() >4300-digit cap on _parse_pos_dec2 (exact boundary + 4301-digit DoS trap)
        max_dec2 = "9" * oracle.MAX_INT_DIGITS + ".00"
        self.assertEqual(verifier._parse_pos_dec2(max_dec2, "d"), Fraction(int("9" * oracle.MAX_INT_DIGITS), 1))
        self._assert_err("INT_TOO_LARGE", verifier._parse_pos_dec2, "9" * (oracle.MAX_INT_DIGITS + 1) + ".00", "d")
        self._assert_err("INT_TOO_LARGE", verifier._parse_pos_dec2, "9" * 4301 + ".00", "d")

    def test_zone_b_io_symlinks_fifo_hardlink_cap_and_pwd(self) -> None:
        self._assert_err("INVALID_PATH_TYPE", verifier.read_regular_bytes_capped, "str", "p")  # type: ignore[arg-type]
        self._assert_err("INVALID_PATH_TYPE", verifier.read_regular_bytes_capped, _PathSub("/tmp/x"), "p")
        self._assert_err("INVALID_PATH", verifier.read_regular_bytes_capped, Path("a\x00b"), "p")
        self._assert_err("INVALID_PATH", verifier.read_regular_bytes_capped, Path("/"), "p")
        dfd_root, leaf_root = verifier._open_parent_dir_fd_strict(Path("/top_leaf"), "p")
        os.close(dfd_root)
        self.assertEqual(leaf_root, "top_leaf")
        self._assert_err("PATH_TRAVERSAL_FORBIDDEN", verifier.read_regular_bytes_capped, Path("/tmp/../etc/hosts"), "p")
        self._assert_err("INVALID_BYTES", verifier.write_regular_bytes_safe, Path("/tmp/x"), "str", "w")  # type: ignore[arg-type]

        with tempfile.TemporaryDirectory(prefix="s86_io_") as tmpd:
            td = Path(tmpd)
            reg = td / "a.txt"
            verifier.write_regular_bytes_safe(reg, b"hello\n", "w")
            self.assertEqual(stat.S_IMODE(reg.stat().st_mode), 0o600)
            self.assertEqual(verifier.read_regular_bytes_capped(reg, "r", max_bytes=6), b"hello\n")
            self._assert_err("FILE_TOO_LARGE", verifier.read_regular_bytes_capped, reg, "r", max_bytes=5)
            # Overwrite existing regular file cleanly
            verifier.write_regular_bytes_safe(reg, b"world\n", "w")
            self.assertEqual(verifier.read_regular_bytes_capped(reg, "r"), b"world\n")

            # Missing file & missing dir
            self._assert_err("FILE_READ_ERROR", verifier.read_regular_bytes_capped, td / "missing.json", "r")
            self._assert_err("DIR_OPEN_ERROR", verifier.read_regular_bytes_capped, td / "no_dir" / "a.json", "r")

            # Symlink file & symlink ancestor
            sym_f = td / "sym_f"
            sym_f.symlink_to(reg)
            self._assert_err("SYMLINK_FORBIDDEN", verifier.read_regular_bytes_capped, sym_f, "r")
            self._assert_err("SYMLINK_FORBIDDEN", verifier.write_regular_bytes_safe, sym_f, b"x", "w")
            sub = td / "real_dir"
            sub.mkdir()
            (sub / "f.txt").write_bytes(b"ok\n")
            sym_d = td / "sym_dir"
            sym_d.symlink_to(sub)
            self._assert_err("SYMLINK_FORBIDDEN", verifier.read_regular_bytes_capped, sym_d / "f.txt", "r")

            # Scratch FIFO non-regular file probe
            fifo_p = td / "test.fifo"
            os.mkfifo(fifo_p)
            self._assert_err("NON_REGULAR_FILE", verifier.read_regular_bytes_capped, fifo_p, "r")
            self._assert_err("NON_REGULAR_FILE", verifier.write_regular_bytes_safe, fifo_p, b"x", "w")

            # Hardlink read & write rejection
            hl = td / "hardlink.txt"
            os.link(reg, hl)
            self._assert_err("HARDLINK_FORBIDDEN", verifier.read_regular_bytes_capped, hl, "r")
            self._assert_err("HARDLINK_FORBIDDEN", verifier.write_regular_bytes_safe, hl, b"x", "w")
            hl.unlink()

            # $PWD symlink ancestor check on relative path
            orig_cwd = os.getcwd()
            try:
                os.chdir(sub)
                with mock.patch.dict(os.environ, {"PWD": str(sym_d)}, clear=False):
                    self._assert_err("SYMLINK_FORBIDDEN", verifier.read_regular_bytes_capped, Path("f.txt"), "r")
                with mock.patch.dict(os.environ, {"PWD": "relative/pwd"}, clear=False):
                    self.assertEqual(verifier.read_regular_bytes_capped(Path("f.txt"), "r"), b"ok\n")
                with mock.patch.dict(os.environ, {"PWD": str(td / "nonexistent_pwd")}, clear=False):
                    self.assertEqual(verifier.read_regular_bytes_capped(Path("f.txt"), "r"), b"ok\n")
                with mock.patch.dict(os.environ, {"PWD": ""}, clear=False):
                    self.assertEqual(verifier.read_regular_bytes_capped(Path("f.txt"), "r"), b"ok\n")
            finally:
                os.chdir(orig_cwd)

            # Write error branches (short write 0, OSError on replace -> tmp cleanup)
            with mock.patch.object(os, "write", return_value=0):
                self._assert_err("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, td / "z.txt", b"ab", "w")
            with mock.patch.object(os, "replace", side_effect=OSError(errno.EIO, "io")):
                self._assert_err("FILE_WRITE_ERROR", verifier.write_regular_bytes_safe, td / "e.txt", b"ab", "w")
            self.assertEqual([x.name for x in td.iterdir() if x.name.startswith(".s86_tmp_")], [])
            # Temp nlink > 1 trap
            real_fstat = os.fstat
            fake_st = mock.Mock(st_nlink=2)
            with mock.patch.object(os, "fstat", return_value=fake_st):
                self._assert_err("HARDLINK_FORBIDDEN", verifier.write_regular_bytes_safe, td / "hl2.txt", b"ab", "w")
            del real_fstat


class Test03LeanR10GateAndLiveKernel(unittest.TestCase):
    def _assert_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S86Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_r10_plus_static_lean_attacks_and_nested_comments(self) -> None:
        lean_src = (_THIS_DIR / "SovereignStackFourthOrder.lean").read_text(encoding="utf-8")
        verifier.static_gate_lean4_source(lean_src)

        # Positive controls: decide (native := false) and decide (native := Bool.false) are allowed when clean!
        clean_with_native_false = lean_src.replace("decide", "decide (native := false)")
        verifier.static_gate_lean4_source(clean_with_native_false)
        clean_with_bool_false = lean_src.replace("decide", "decide (native := Bool.false)")
        verifier.static_gate_lean4_source(clean_with_bool_false)

        # Nested comments containing banned words AND EOF line-comment without trailing LF
        nested = "/- outer /- sorry axiom import -/ outer -/\n" + lean_src + "\n-- eof comment sorry"
        verifier.static_gate_lean4_source(nested)
        # Line comment MUST terminate at '\n' (kills SUBCOND_DEL[1] on `while i < n and source[i] != "\n"`)
        self._assert_err(
            "LEAN4_TRUST_ESCAPE",
            verifier.static_gate_lean4_source,
            lean_src + "\n-- harmless comment\ntheorem bad : True := by sorry\n",
        )

        # Unterminated block comment & CR/NUL fail closed
        self._assert_err("LEAN4_UNTERMINATED_COMMENT", verifier.static_gate_lean4_source, "/- unclosed\n" + lean_src)
        self._assert_err("LEAN4_BAD_CHARS", verifier.static_gate_lean4_source, lean_src + "\r")
        self._assert_err("LEAN4_BAD_CHARS", verifier.static_gate_lean4_source, lean_src + "\x00")

        # Full 15-class R10+ attacks INCLUDING all 6 single/multi-line boolean-expression `native :=` bypasses (S84-VER-01!)
        attacks = [
            "import Lean\n",
            "theorem x : True := by sorry\n",
            "theorem x : True := by admit\n",
            "axiom bad : False\n",
            "unsafe def u : Nat := 0\n",
            "@[implemented_by foo] def x : Nat := 0\n",
            "@[extern] def x : Nat := 0\n",
            "@[csimp] theorem x : 1 = 1 := rfl\n",
            "theorem x : 1 = 1 := by native_decide\n",
            "notation a => a\n",
            "macro a : term => a\n",
            "syntax a : term\n",
            "declare_syntax_cat foo\n",
            "elab a : term => a\n",
            "def x := Lean.ofReduceBool\n",
            "def x := Lean.trustCompiler\n",
            "def x := dbg_trace 1\n",
            "def x := throwError 1\n",
            "#eval 1 + 1\n",
            "#reduce 1 + 1\n",
            "set_option maxHeartbeats 1\n",
            "def x := debug.skipKernelTC\n",
            "def s := \"hello\"\n",
            "def c := 'a'\n",
            "def «debug» := 0\n",
            "theorem x : 1 = 1 := by decide +native\n",
            "theorem x : 1 = 1 := by decide -revert +native\n",
            "theorem x : 1 = 1 := by decide +revert +native\n",
            "theorem x : 1 = 1 := by decide -kernel +native\n",
            "initialize pure ()\n",
            "builtin_initialize pure ()\n",
            "partial def _p (n : Nat) : Nat := _p n\n",
            "opaque _p : Nat := 0\n",
            "run_cmd pure ()\n",
            "run_meta pure ()\n",
            "def _s := sorryAx\n",
            "def _r := Lean.ofReduceNat\n",
            "def _m := mkSorry\n",
            "#exit\n",
            "theorem x : 1 = 1 := by decide (config := { native := true })\n",
            "def native : Bool := true\ntheorem x : 1 = 1 := by decide +revert (config := { native })\n",
            "def native : Bool := true\ntheorem x : 1 = 1 := by decide (revert := false) (config := { native })\n",
            "def native : Bool := true\ntheorem x : 1 = 1 := by decide +revert (config := { ({} : _) with native })\n",
            "def c : DecideConfig := {}\n",
            "theorem x : 1 = 1 := by decide (native := true)\n",
            "theorem x : 1 = 1 := by decide (native := !false)\n",
            "theorem x : 1 = 1 := by decide (native := false || true)\n",
            "theorem x : 1 = 1 := by decide (native := false == false)\n",
            "theorem x : 1 = 1 := by decide (native := false != true)\n",
            "theorem x : 1 = 1 := by decide (native := false.not)\n",
            "theorem x : 1 = 1 := by decide (native := false\n  || true)\n",
            "theorem x : 1 = 1 := by decide (native := Bool.false || true)\n",
            "def x := dbgTrace 1 (fun _ => 0)\n",
            "def x := dbgTraceVal 1\n",
            "def x := dbgTraceIfShared 1 0\n",
            "def x := dbgSleep 10 (fun _ => 0)\n",
            "def x := dbgStackTrace (fun _ => 0)\n",
            "def x := dbg_sleep 10\n",
            "def x := dbg_stack_trace\n",
            "def x := dbg_trace_if 1\n",
            "@[export foo] def f : Nat := 3\n",
            "@[init] def f : Nat := 0\n",
            "@[builtin_init] def f : Nat := 0\n",
            "attribute [init] f\n",
            "export Nat (succ)\n",
            "def x := IO.println 0\n",
            "def x := System.FilePath\n",
            "def x := Meta.whnf\n",
            "def x := Elab.Term\n",
            "def c : Char := '\"'\ntheorem t : (1:Nat) = 2 := sorry\ndef d : Char := '\"'\n",
        ]
        for atk in attacks:
            self._assert_err("LEAN4_TRUST_ESCAPE", verifier.static_gate_lean4_source, lean_src + "\n" + atk)

        # Missing theorem & missing #print axioms
        self._assert_err(
            "LEAN4_MISSING_THEOREM",
            verifier.static_gate_lean4_source,
            lean_src.replace("theorem borromean_4way_vram_fit_universal", "theorem renamed_thm"),
        )
        self._assert_err(
            "LEAN4_MISSING_PRINT_AXIOMS",
            verifier.static_gate_lean4_source,
            lean_src.replace("#print axioms SovereignStackFourthOrder.rtx3080_sovereign_stack_live_witness", ""),
        )

    def test_live_lean_verification_and_leanless_ci_0skip_parity(self) -> None:
        lean_file = _THIS_DIR / "SovereignStackFourthOrder.lean"
        self._assert_err("INVALID_BOOL", verifier.verify_lean4_file_live, lean_file, enforce_sha256=1)  # type: ignore[arg-type]

        lean_bin = _find_lean_optional()
        if lean_bin is None:
            if os.environ.get("ALETHEIA_REQUIRE_LEAN") == "1":
                self.fail("Lean 4.36.0 binary required when ALETHEIA_REQUIRE_LEAN=1")
            # Lean-less CI path: 0 skips! Verify fail-closed LEAN_BINARY_UNAVAILABLE
            self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.verify_lean4_file_live, lean_file)
            buf_err = io.StringIO()
            with mock.patch.object(sys, "stderr", buf_err):
                self.assertEqual(verifier.main(["--verify-lean"]), 2)
            self.assertIn("LEAN_BINARY_UNAVAILABLE", buf_err.getvalue())
        else:
            res = verifier.verify_lean4_file_live(lean_file, enforce_sha256=True)
            self.assertTrue(res["lean_valid"])
            self.assertEqual(res["theorems_verified"], 17)
            self.assertEqual(res["zero_axiom_theorems"], 9)
            self.assertEqual(res["lean_source_sha256"], oracle.EXPECTED_LEAN_SHA256)

            # Live poisoned-env immunity check under SAFE_LEAN_ENV_KEYS allowlist
            poison = {
                "LEAN_PATH": "/evil/lean",
                "LEAN_OPTS": "--bad-opt",
                "LEAN_SRC_PATH": "/evil/src",
                "ELAN_TOOLCHAIN": "evil-toolchain",
                "ELAN_HOME": "/evil/elan",
                "LEAN_CC": "/bin/false",
                "LD_PRELOAD": "/nonexistent/evil.so",
                "LD_LIBRARY_PATH": "/evil/lib",
                "PYTHONPATH": "/evil/py",
            }
            with mock.patch.dict(os.environ, poison, clear=False):
                scrubbed = verifier._scrubbed_lean_env()
                for pk in poison:
                    self.assertNotIn(pk, scrubbed)
                self.assertTrue(set(scrubbed.keys()) <= verifier.SAFE_LEAN_ENV_KEYS)
                res_p = verifier.verify_lean4_file_live(lean_file, enforce_sha256=True)
                self.assertEqual(res_p["theorems_verified"], 17)

            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": lean_bin}, clear=False):
                self.assertEqual(verifier.resolve_lean_binary(), lean_bin)
                buf_out = io.StringIO()
                with mock.patch.object(sys, "stdout", buf_out):
                    self.assertEqual(verifier.main(["--verify-lean", "--json"]), 0)
                self.assertEqual(json.loads(buf_out.getvalue())["theorems_verified"], 17)
                buf_txt = io.StringIO()
                with mock.patch.object(sys, "stdout", buf_txt):
                    self.assertEqual(verifier.main(["--verify-lean", str(lean_file)]), 0)
                self.assertIn("LEAN_OK 17", buf_txt.getvalue())

        # Binary resolution fallback & missing/non-exec binary traps (always run!)
        with tempfile.TemporaryDirectory(prefix="s86_bin_") as td_bin:
            nonexec = Path(td_bin) / "lean_noexec"
            nonexec.write_bytes(b"#!/bin/sh\n")
            os.chmod(nonexec, 0o600)
            exec_dir = Path(td_bin) / "dir_exec"
            exec_dir.mkdir()
            os.chmod(exec_dir, 0o700)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": "/nonexistent/lean"}, clear=False):
                self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(nonexec)}, clear=False):
                self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
            with mock.patch.dict(os.environ, {"ALETHEIA_LEAN_BIN": str(exec_dir)}, clear=False):
                self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("ALETHEIA_LEAN_BIN", None)
                with mock.patch.object(shutil, "which", return_value=str(nonexec)):
                    with mock.patch.object(Path, "is_file", return_value=False):
                        self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
                with mock.patch.object(shutil, "which", return_value=None):
                    with mock.patch.dict(os.environ, {"HOME": td_bin}, clear=False):
                        with mock.patch.object(Path, "is_file", return_value=True):
                            with mock.patch.object(os, "access", return_value=False):
                                self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
                        with mock.patch.object(Path, "is_file", return_value=False):
                            self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)
                    with mock.patch.dict(os.environ, {"HOME": ""}, clear=False):
                        self._assert_err("LEAN_BINARY_UNAVAILABLE", verifier.resolve_lean_binary)

        # Mocked Lean subprocess traps (version, rc, stderr, warning, multiline axioms, banned axiom, dup, missing, timeout)
        with tempfile.TemporaryDirectory(prefix="s86_ln_") as tmpd:
            bad_lean = Path(tmpd) / "bad.lean"
            bad_lean.write_bytes(b"\xff")
            self._assert_err("LEAN4_SHA_MISMATCH", verifier.verify_lean4_file_live, bad_lean, enforce_sha256=True)
            self._assert_err("INVALID_UTF8", verifier.verify_lean4_file_live, bad_lean, enforce_sha256=False)

        with mock.patch.object(verifier, "resolve_lean_binary", return_value="lean"):
            with mock.patch.object(subprocess, "run", side_effect=OSError("boom")):
                self._assert_err("LEAN_EXEC_ERROR", verifier.verify_lean4_file_live, lean_file)
            ver_ok = subprocess.CompletedProcess(["lean", "--version"], 0, stdout="Lean (version 4.36.0)", stderr="")
            ver_bad = subprocess.CompletedProcess(["lean", "--version"], 0, stdout="Lean (version 4.10.0)", stderr="")
            ver_rc1 = subprocess.CompletedProcess(["lean", "--version"], 1, stdout="Lean (version 4.36.0)", stderr="")
            with mock.patch.object(subprocess, "run", return_value=ver_bad):
                self._assert_err("LEAN_VERSION_MISMATCH", verifier.verify_lean4_file_live, lean_file)
            with mock.patch.object(subprocess, "run", return_value=ver_rc1):
                self._assert_err("LEAN_VERSION_MISMATCH", verifier.verify_lean4_file_live, lean_file)
            with mock.patch.object(subprocess, "run", side_effect=[ver_ok, subprocess.TimeoutExpired(["lean"], 120)]):
                self._assert_err("LEAN_EXEC_ERROR", verifier.verify_lean4_file_live, lean_file)
            with mock.patch.object(subprocess, "run", side_effect=[ver_ok, subprocess.CompletedProcess(["lean"], 1, "", "")]):
                self._assert_err("LEAN_COMPILE_FAIL", verifier.verify_lean4_file_live, lean_file)
            with mock.patch.object(subprocess, "run", side_effect=[ver_ok, subprocess.CompletedProcess(["lean"], 0, "", "err")]):
                self._assert_err("LEAN_STDERR_NONEMPTY", verifier.verify_lean4_file_live, lean_file)
            with mock.patch.object(subprocess, "run", side_effect=[ver_ok, subprocess.CompletedProcess(["lean"], 0, "warning: x\n", "")]):
                self._assert_err("LEAN_WARNING_FORBIDDEN", verifier.verify_lean4_file_live, lean_file)
            with mock.patch.object(subprocess, "run", side_effect=[ver_ok, subprocess.CompletedProcess(["lean"], 0, "'A.b' depends on axioms: [propext\n", "")]):
                self._assert_err("LEAN_UNEXPECTED_STDOUT", verifier.verify_lean4_file_live, lean_file)
            with mock.patch.object(subprocess, "run", side_effect=[ver_ok, subprocess.CompletedProcess(["lean"], 0, "garbage\n", "")]):
                self._assert_err("LEAN_UNEXPECTED_STDOUT", verifier.verify_lean4_file_live, lean_file)
            dup_none = "\n".join([f"'{oracle.LEAN_THEOREM_NAMES[0]}' does not depend on any axioms"] * 2) + "\n"
            with mock.patch.object(subprocess, "run", side_effect=[ver_ok, subprocess.CompletedProcess(["lean"], 0, dup_none, "")]):
                self._assert_err("LEAN_DUPLICATE_THEOREM", verifier.verify_lean4_file_live, lean_file)
            dup_dep = "\n".join([f"'{oracle.LEAN_THEOREM_NAMES[0]}' depends on axioms: [propext]"] * 2) + "\n"
            with mock.patch.object(subprocess, "run", side_effect=[ver_ok, subprocess.CompletedProcess(["lean"], 0, dup_dep, "")]):
                self._assert_err("LEAN_DUPLICATE_THEOREM", verifier.verify_lean4_file_live, lean_file)
            banned_ax = f"'{oracle.LEAN_THEOREM_NAMES[0]}' depends on axioms: [sorryAx]\n"
            with mock.patch.object(subprocess, "run", side_effect=[ver_ok, subprocess.CompletedProcess(["lean"], 0, banned_ax, "")]):
                self._assert_err("LEAN_BANNED_AXIOM", verifier.verify_lean4_file_live, lean_file)
            # Multiline axiom join + missing theorem set mismatch
            multi_line = f"'{oracle.LEAN_THEOREM_NAMES[0]}' depends on axioms: [\n propext\n]\n"
            with mock.patch.object(subprocess, "run", side_effect=[ver_ok, subprocess.CompletedProcess(["lean"], 0, multi_line, "")]):
                self._assert_err("LEAN_THEOREM_SET_MISMATCH", verifier.verify_lean4_file_live, lean_file)


class Test04SecondaryAuditTampersAndCLI(unittest.TestCase):
    def _assert_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(oracle.S86Error) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_resigned_semantic_tampers_fr0_and_fr1(self) -> None:
        base = oracle.build_certificate()
        self.assertTrue(verifier.verify_certificate_dict(base, full_replay=False)["valid"])
        self.assertTrue(verifier.verify_certificate_dict(base, full_replay=True)["valid"])
        self._assert_err("INVALID_BOOL", verifier.verify_certificate_dict, base, full_replay=1)  # type: ignore[arg-type]
        self._assert_err("INVALID_CERT_TYPE", verifier.verify_certificate_dict, [], full_replay=False)

        # Digest mismatches
        bad_p = copy.deepcopy(base)
        bad_p["payload_sha256"] = "0" * 64
        self._assert_err("PAYLOAD_SHA_MISMATCH", verifier.verify_certificate_dict, bad_p, full_replay=False)
        bad_c = copy.deepcopy(base)
        bad_c["certificate_sha256"] = "0" * 64
        self._assert_err("CERT_SHA_MISMATCH", verifier.verify_certificate_dict, bad_c, full_replay=False)

        # Schema / key / field tampers (re-signed so ONLY secondary semantic audit catches them!)
        def _tamper(path_keys: tuple[str, ...], val: Any, expected_code: str) -> None:
            c = copy.deepcopy(base)
            cur = c["payload"]
            for k in path_keys[:-1]:
                cur = cur[k]
            cur[path_keys[-1]] = val
            self._assert_err(expected_code, verifier.verify_certificate_dict, _resign_cert(c), full_replay=False)

        _tamper(("schema_version",), "bad", "SCHEMA_MISMATCH")
        _tamper(("track_id",), "bad", "SCHEMA_MISMATCH")
        _tamper(("oracle_class",), "bad", "SCHEMA_MISMATCH")
        _tamper(("novelty_classification",), "N2", "SCHEMA_MISMATCH")
        _tamper(("measured_live_rtx3080",), False, "LIVE_FLAG")
        _tamper(("pinned_artifacts", "lean_universal_theorem_count"), 15, "INT_OUT_OF_RANGE")
        _tamper(("pinned_artifacts", "lean_witness_theorem_count"), 2, "INT_OUT_OF_RANGE")
        _tamper(("pinned_artifacts", "lean_source"), "Other.lean", "PIN_MISMATCH")
        _tamper(("pinned_artifacts", "lean_toolchain"), "bad", "PIN_MISMATCH")
        _tamper(("pinned_artifacts", "lean_theorem_names"), [], "PIN_MISMATCH")
        _tamper(("pinned_artifacts", "empirical_results_file"), "other.json", "PIN_MISMATCH")
        _tamper(("pinned_artifacts", "mlos_receipt_file"), "other.json", "PIN_MISMATCH")
        _tamper(("pinned_artifacts", "upstream_cert_pins"), [], "PIN_MISMATCH")

        # Exact list-subclass traps directly on secondary_audit_payload
        for fld, code in (
            (("pinned_artifacts", "lean_theorem_names"), "PIN_MISMATCH"),
            (("pinned_artifacts", "upstream_cert_pins"), "PIN_MISMATCH"),
            (("pillar2_borromean_4way_stack", "full_r64_step_losses_nano"), "PILLAR2_LOSSES"),
        ):
            p_sub = copy.deepcopy(base["payload"])
            p_sub[fld[0]][fld[1]] = _ListSub(p_sub[fld[0]][fld[1]])
            self._assert_err(code, verifier.secondary_audit_payload, p_sub)

        # S86-VER-02 F03..F06 pin regressions (upstream track/file/sha, mlos SHAs, n_univ/n_wit swap)
        c_swap_cnt = copy.deepcopy(base)
        c_swap_cnt["payload"]["pinned_artifacts"]["lean_universal_theorem_count"] = 1
        c_swap_cnt["payload"]["pinned_artifacts"]["lean_witness_theorem_count"] = 16
        self._assert_err("INT_OUT_OF_RANGE", verifier.verify_certificate_dict, _resign_cert(c_swap_cnt), full_replay=False)
        _tamper(("pinned_artifacts", "mlos_receipt_file_sha256"), "0" * 64, "PIN_MISMATCH")
        _tamper(("pinned_artifacts", "mlos_receipt_inner_sha256"), "0" * 64, "PIN_MISMATCH")
        c_unk_up = copy.deepcopy(base)
        c_unk_up["payload"]["pinned_artifacts"]["upstream_cert_pins"][0]["track"] = "S99"
        self._assert_err("PIN_MISMATCH", verifier.verify_certificate_dict, _resign_cert(c_unk_up), full_replay=False)
        c_empty_file_up = copy.deepcopy(base)
        c_empty_file_up["payload"]["pinned_artifacts"]["upstream_cert_pins"][0]["file"] = ""
        self._assert_err("PIN_MISMATCH", verifier.verify_certificate_dict, _resign_cert(c_empty_file_up), full_replay=False)
        c_bad_sha_up = copy.deepcopy(base)
        c_bad_sha_up["payload"]["pinned_artifacts"]["upstream_cert_pins"][0]["sha256"] = "0" * 64
        self._assert_err("PIN_MISMATCH", verifier.verify_certificate_dict, _resign_cert(c_bad_sha_up), full_replay=False)
        c_dup_up = copy.deepcopy(base)
        c_dup_up["payload"]["pinned_artifacts"]["upstream_cert_pins"][0] = copy.deepcopy(
            c_dup_up["payload"]["pinned_artifacts"]["upstream_cert_pins"][1]
        )
        self._assert_err("PIN_MISMATCH", verifier.verify_certificate_dict, _resign_cert(c_dup_up), full_replay=False)
        c_extra_up = copy.deepcopy(base)
        c_extra_up["payload"]["pinned_artifacts"]["upstream_cert_pins"].append(
            copy.deepcopy(c_extra_up["payload"]["pinned_artifacts"]["upstream_cert_pins"][0])
        )
        self._assert_err("PIN_MISMATCH", verifier.verify_certificate_dict, _resign_cert(c_extra_up), full_replay=False)

        # S86-VER-02 F01..F02 dec2 format, positivity, and ratio consistency regressions
        _tamper(("pillar1_t3_blowup_cce_det", "n1024_mat_fp32_mib_dec2"), "GARBAGE", "PILLAR1_DEC")
        _tamper(("pillar1_t3_blowup_cce_det", "n2048_cce_det_frozen_mib_dec2"), "NOPE", "PILLAR1_DEC")
        _tamper(("pillar1_t3_blowup_cce_det", "n1024_mat_fp32_mib_dec2"), "0.00", "PILLAR1_DEC")
        c_f02_1024 = copy.deepcopy(base)
        c_f02_1024["payload"]["pillar1_t3_blowup_cce_det"]["n1024_mat_fp32_mib_dec2"] = "1.00"
        c_f02_1024["payload"]["pillar1_t3_blowup_cce_det"]["n1024_cce_det_frozen_mib_dec2"] = "9999.00"
        self._assert_err("PILLAR1_RATIO", verifier.verify_certificate_dict, _resign_cert(c_f02_1024), full_replay=False)
        c_f02_2048 = copy.deepcopy(base)
        c_f02_2048["payload"]["pillar1_t3_blowup_cce_det"]["n2048_mat_fp32_mib_dec2"] = "1.00"
        c_f02_2048["payload"]["pillar1_t3_blowup_cce_det"]["n2048_cce_det_frozen_mib_dec2"] = "9999.00"
        self._assert_err("PILLAR1_RATIO", verifier.verify_certificate_dict, _resign_cert(c_f02_2048), full_replay=False)

        c_lo_1024 = copy.deepcopy(base)
        c_lo_1024["payload"]["pillar1_t3_blowup_cce_det"]["n1024_mat_fp32_mib_dec2"] = "200.00"
        c_lo_1024["payload"]["pillar1_t3_blowup_cce_det"]["n1024_cce_det_frozen_mib_dec2"] = "100.00"
        c_lo_1024["payload"]["pillar1_t3_blowup_cce_det"]["n1024_compression_ratio_q"] = "2"
        c_lo_1024["payload"]["pillar1_t3_blowup_cce_det"]["n1024_compression_ratio_dec4"] = "2.0000"
        self._assert_err("PILLAR1_RATIO", verifier.verify_certificate_dict, _resign_cert(c_lo_1024), full_replay=False)
        c_lo_2048 = copy.deepcopy(base)
        c_lo_2048["payload"]["pillar1_t3_blowup_cce_det"]["n2048_mat_fp32_mib_dec2"] = "200.00"
        c_lo_2048["payload"]["pillar1_t3_blowup_cce_det"]["n2048_cce_det_frozen_mib_dec2"] = "100.00"
        c_lo_2048["payload"]["pillar1_t3_blowup_cce_det"]["n2048_compression_ratio_q"] = "2"
        c_lo_2048["payload"]["pillar1_t3_blowup_cce_det"]["n2048_compression_ratio_dec4"] = "2.0000"
        self._assert_err("PILLAR1_RATIO", verifier.verify_certificate_dict, _resign_cert(c_lo_2048), full_replay=False)
        _tamper(("pillar1_t3_blowup_cce_det", "n1024_compression_ratio_dec4"), "0.0000", "PILLAR1_DEC")
        _tamper(("pillar1_t3_blowup_cce_det", "n2048_compression_ratio_dec4"), "0.0000", "PILLAR1_DEC")
        _tamper(("pillar1_t3_blowup_cce_det", "n4096_mat_fp32_oom"), False, "PILLAR1_OOM")
        _tamper(("pillar1_t3_blowup_cce_det", "n4096_cce_det_frozen_mib_dec2"), "0.00", "PILLAR1_DEC")
        _tamper(("pillar1_t3_blowup_cce_det", "atomic_cas_divergent_pct_dec2"), "0.00", "PILLAR1_DEC")

        _tamper(("pillar2_borromean_4way_stack", "no_s78_full_finetune_oom"), False, "PILLAR2_OOM")
        _tamper(("pillar2_borromean_4way_stack", "no_s79_r64_oom"), True, "PILLAR2_NO79")
        _tamper(("pillar2_borromean_4way_stack", "no_s79_r64_peak_alloc_mib_dec2"), "0.00", "PILLAR2_DEC")
        _tamper(("pillar2_borromean_4way_stack", "full_r64_peak_res_mib_dec2"), "0.00", "PILLAR2_DEC")
        _tamper(("pillar2_borromean_4way_stack", "full_r64_peak_alloc_mib_dec2"), "0.00", "PILLAR2_DEC")
        _tamper(("pillar2_borromean_4way_stack", "full_r64_headroom_mib_dec2"), "0.00", "PILLAR2_DEC")
        _tamper(("pillar2_borromean_4way_stack", "full_r128_peak_alloc_mib_dec2"), "0.00", "PILLAR2_DEC")
        _tamper(("pillar2_borromean_4way_stack", "full_r64_step_losses_nano"), [10, 20, 30, 40, 50], "PILLAR2_DESCENT")
        _tamper(("pillar2_borromean_4way_stack", "full_r64_loss_strictly_decreasing"), False, "PILLAR2_DESCENT")
        _tamper(("pillar2_borromean_4way_stack", "full_r64_bit_identical_repeatability"), False, "PILLAR2_REP")
        _tamper(("pillar2_borromean_4way_stack", "no_s79_r64_step0_loss_nano"), 2071853638, "PILLAR2_CSR_STEP0")
        _tamper(("pillar2_borromean_4way_stack", "full_r64_5step_loss_drop_pct_q"), "1", "PILLAR2_LDROP")
        _tamper(("pillar2_borromean_4way_stack", "full_r64_5step_loss_drop_pct_dec2"), "0.00", "PILLAR2_DEC")
        _tamper(("pillar2_borromean_4way_stack", "full_r64_step_losses_nano"), [1, 2], "PILLAR2_LOSSES")

        _tamper(("pillar3_csr_1_over_160_crossover", "csr0500_mib_dec2"), "0.00", "PILLAR3_DEC")
        c_bpw_both = copy.deepcopy(base)
        c_bpw_both["payload"]["pillar3_csr_1_over_160_crossover"]["csr0500_bpw_overhead_q"] = "1/2"
        c_bpw_both["payload"]["pillar3_csr_1_over_160_crossover"]["csr0500_bpw_overhead_dec4"] = "0.5000"
        self._assert_err("PILLAR3_DEC", verifier.verify_certificate_dict, _resign_cert(c_bpw_both), full_replay=False)
        _tamper(("pillar3_csr_1_over_160_crossover", "csr0500_bpw_overhead_dec4"), "0.0000", "PILLAR3_DEC")
        _tamper(("pillar3_csr_1_over_160_crossover", "csr0500_rho_q"), "1/300", "PILLAR3_CAP")
        c_hi_rho = copy.deepcopy(base)
        wtot_v = c_hi_rho["payload"]["pillar3_csr_1_over_160_crossover"]["total_block_weights"]
        hi_nnz = wtot_v // 100
        c_hi_rho["payload"]["pillar3_csr_1_over_160_crossover"]["csr0500_nnz"] = hi_nnz
        c_hi_rho["payload"]["pillar3_csr_1_over_160_crossover"]["csr0500_rho_q"] = oracle.q_str(Fraction(hi_nnz, wtot_v))
        self._assert_err("PILLAR3_CAP", verifier.verify_certificate_dict, _resign_cert(c_hi_rho), full_replay=False)
        _tamper(("pillar3_csr_1_over_160_crossover", "csr0500_strictly_below_1_over_160"), False, "PILLAR3_CAP")

        c_sfrac_both = copy.deepcopy(base)
        c_sfrac_both["payload"]["pillar3_csr_1_over_160_crossover"]["csr0500_sens_frac_q"] = "1/2"
        c_sfrac_both["payload"]["pillar3_csr_1_over_160_crossover"]["csr0500_sens_frac_pct_dec2"] = "50.00"
        self._assert_err("PILLAR3_DEC", verifier.verify_certificate_dict, _resign_cert(c_sfrac_both), full_replay=False)
        _tamper(("pillar3_csr_1_over_160_crossover", "csr0500_sens_frac_pct_dec2"), "0.00", "PILLAR3_DEC")
        _tamper(("pillar3_csr_1_over_160_crossover", "csr0500_sout_over_sbulk_pct_dec2"), "0.00", "PILLAR3_DEC")
        _tamper(("pillar3_csr_1_over_160_crossover", "s79_m54_crossover_ratio_q"), "1/2", "PILLAR3_CROSS")
        _tamper(("pillar3_csr_1_over_160_crossover", "s79_m54_crossover_ratio_dec4"), "0.0000", "PILLAR3_DEC")
        c_hi_cross = copy.deepcopy(base)
        stot_v = c_hi_cross["payload"]["pillar3_csr_1_over_160_crossover"]["csr0500_sens_total"]
        c_hi_cross["payload"]["pillar3_csr_1_over_160_crossover"]["csr0500_sens_out"] = 1
        c_hi_cross["payload"]["pillar3_csr_1_over_160_crossover"]["csr0500_sens_frac_q"] = oracle.q_str(Fraction(1, stot_v))
        c_hi_cross["payload"]["pillar3_csr_1_over_160_crossover"]["csr0500_sens_frac_pct_dec2"] = oracle.dec_from_q(Fraction(100, stot_v), 2)
        c_hi_cross["payload"]["pillar3_csr_1_over_160_crossover"]["csr0500_sout_over_sbulk_pct_dec2"] = oracle.dec_from_q(Fraction(100, stot_v - 1), 2)
        c_hi_cross["payload"]["pillar3_csr_1_over_160_crossover"]["s79_m54_crossover_ratio_q"] = oracle.q_str(Fraction(5 * (stot_v - 1), 4 * stot_v))
        self._assert_err("PILLAR3_CROSS", verifier.verify_certificate_dict, _resign_cert(c_hi_cross), full_replay=False)
        _tamper(("pillar3_csr_1_over_160_crossover", "s79_crossover_wins"), False, "PILLAR3_CROSS")

        _tamper(("pillar3_csr_1_over_160_crossover", "q45_wt_kl_nano"), 152175575, "PILLAR3_WT_ORDER")
        _tamper(("pillar3_csr_1_over_160_crossover", "csr0250_wt_kl_nano"), 152175575, "PILLAR3_WT_ORDER")
        _tamper(("pillar3_csr_1_over_160_crossover", "csr0250_wt_kl_nano"), 160377057, "PILLAR3_WT_ORDER")
        _tamper(("pillar3_csr_1_over_160_crossover", "csr0125_wt_kl_nano"), 168873980, "PILLAR3_WT_ORDER")
        _tamper(("pillar3_csr_1_over_160_crossover", "raw0500_wt_kl_nano"), 152175575, "PILLAR3_WT_ORDER")
        _tamper(("pillar3_csr_1_over_160_crossover", "raw0500_wt_kl_nano"), 168873980, "PILLAR3_WT_ORDER")
        _tamper(("pillar3_csr_1_over_160_crossover", "q45_py_kl_nano"), 142043565, "PILLAR3_PY_ORDER")
        _tamper(("pillar3_csr_1_over_160_crossover", "csr0250_py_kl_nano"), 142043565, "PILLAR3_PY_ORDER")
        _tamper(("pillar3_csr_1_over_160_crossover", "csr0250_py_kl_nano"), 146493230, "PILLAR3_PY_ORDER")
        _tamper(("pillar3_csr_1_over_160_crossover", "csr0125_py_kl_nano"), 151009951, "PILLAR3_PY_ORDER")
        _tamper(("pillar3_csr_1_over_160_crossover", "raw0500_py_kl_nano"), 142043565, "PILLAR3_PY_ORDER")
        _tamper(("pillar3_csr_1_over_160_crossover", "raw0500_py_kl_nano"), 151009951, "PILLAR3_PY_ORDER")
        _tamper(("pillar3_csr_1_over_160_crossover", "csr0500_wt_drop_pct_dec2"), "0.00", "PILLAR3_DEC")
        _tamper(("pillar3_csr_1_over_160_crossover", "hessian_vs_raw_wt_leverage_q"), "999/2", "PILLAR3_LEV")
        _tamper(("pillar3_csr_1_over_160_crossover", "hessian_vs_raw_py_leverage_q"), "999/2", "PILLAR3_LEV")
        _tamper(("pillar3_csr_1_over_160_crossover", "hessian_vs_raw_wt_leverage_dec4"), "0.0000", "PILLAR3_DEC")
        _tamper(("pillar3_csr_1_over_160_crossover", "hessian_vs_raw_py_leverage_dec4"), "0.0000", "PILLAR3_DEC")

        _tamper(("pillar4_joint_mdl_and_mellin_glu", "wt_horizon_lift_q"), "1/2", "PILLAR4_LIFT")
        _tamper(("pillar4_joint_mdl_and_mellin_glu", "py_horizon_lift_q"), "1/2", "PILLAR4_LIFT")
        _tamper(("pillar4_joint_mdl_and_mellin_glu", "wt_horizon_lift_dec4"), "0.0000", "PILLAR4_DEC")
        _tamper(("pillar4_joint_mdl_and_mellin_glu", "py_horizon_lift_dec4"), "0.0000", "PILLAR4_DEC")
        _tamper(("pillar4_joint_mdl_and_mellin_glu", "mellin_density_q"), "1/2", "PILLAR4_MELLIN")
        _tamper(("pillar4_joint_mdl_and_mellin_glu", "mellin_rung_share_of_csr_budget_q"), "1/2", "PILLAR4_MELLIN")
        _tamper(("pillar4_joint_mdl_and_mellin_glu", "mellin_rung_share_of_csr_budget_pct_dec2"), "0.00", "PILLAR4_DEC")

        # Full replay mismatch on FR1 via real on-disk Lean drift (FR0 passes on valid cert, FR1 catches on-disk drift!)
        with tempfile.TemporaryDirectory(prefix="s86_fr1_") as tmpd_fr1:
            td_fr1 = Path(tmpd_fr1)
            for fname in (
                "SovereignStackFourthOrder.lean",
                "lean-toolchain",
                "lakefile.toml",
                "rtx3080_s86_empirical_results.json",
                "mlos_zone_b_receipt.json",
            ):
                (td_fr1 / fname).write_bytes((_THIS_DIR / fname).read_bytes())
            lean_drifted = td_fr1 / "SovereignStackFourthOrder.lean"
            lean_drifted.write_bytes(lean_drifted.read_bytes() + b"\n-- harmless comment drift\n")
            self.assertTrue(verifier.verify_certificate_dict(base, full_replay=False)["valid"])
            self._assert_err("FULL_REPLAY_MISMATCH", verifier.verify_certificate_dict, base, full_replay=True, track_dir=td_fr1)

        # Exhaustive every-leaf re-signed tamper battery across SEC, FR0, and FR1 (203/203 leaves, 0 bypasses!)
        leaves: list[tuple[tuple[Any, ...], Any]] = []

        def _collect_leaves(node: Any, path: tuple[Any, ...]) -> None:
            if isinstance(node, dict):
                for k, v in node.items():
                    _collect_leaves(v, path + (k,))
            elif isinstance(node, list):
                for idx, v in enumerate(node):
                    _collect_leaves(v, path + (idx,))
            else:
                leaves.append((path, node))

        _collect_leaves(base["payload"], ())
        self.assertEqual(len(leaves), 203)
        base_bytes = oracle.canonical_json_bytes(base)
        for path, val in leaves:
            c_mut = copy.deepcopy(base)
            cur: Any = c_mut["payload"]
            for k in path[:-1]:
                cur = cur[k]
            if type(val) is bool:
                mut_v: Any = not val
            elif type(val) is int:
                mut_v = val + 1
            elif type(val) is str:
                if len(val) == 64 and all(ch in "0123456789abcdef" for ch in val):
                    mut_v = ("1" if val[0] == "0" else "0") + val[1:]
                else:
                    mut_v = val + "X"
            else:
                mut_v = 0
            cur[path[-1]] = mut_v
            resigned = _resign_cert(c_mut)
            with self.assertRaises(oracle.S86Error, msg=f"SEC bypass at {path}"):
                verifier.secondary_audit_payload(resigned["payload"])
            with self.assertRaises(oracle.S86Error, msg=f"FR0 bypass at {path}"):
                verifier.verify_certificate_dict(resigned, full_replay=False)
            with self.assertRaises(oracle.S86Error, msg=f"FR1 bypass at {path}"):
                verifier.verify_certificate_dict(resigned, full_replay=True)
        self.assertEqual(oracle.canonical_json_bytes(base), base_bytes)

        # Empirical JSON anchor cross-check traps (schema missing, non-dict intermediate, scalar & list mismatch)
        emp_good = verifier.parse_strict_json_bytes(
            (_THIS_DIR / "rtx3080_s86_empirical_results.json").read_bytes(), "emp", require_canonical=False
        )
        verifier._crosscheck_empirical_anchors(emp_good)
        emp_missing = copy.deepcopy(emp_good)
        del emp_missing["eval_seed"]
        self._assert_err("EMPIRICAL_SCHEMA_MISMATCH", verifier._crosscheck_empirical_anchors, emp_missing)
        emp_nondict = copy.deepcopy(emp_good)
        emp_nondict["model_pins"] = ["total_block_weights"]
        self._assert_err("EMPIRICAL_SCHEMA_MISMATCH", verifier._crosscheck_empirical_anchors, emp_nondict)
        emp_bad_scalar = copy.deepcopy(emp_good)
        emp_bad_scalar["eval_seed"] = 999
        self._assert_err("EMPIRICAL_ANCHOR_MISMATCH", verifier._crosscheck_empirical_anchors, emp_bad_scalar)
        emp_bad_list = copy.deepcopy(emp_good)
        emp_bad_list["part2_sovereign_stack"]["vram_and_training_ablations"]["full_4way_3bpw_csr0p50_lora_r64_cce_det_run1"]["step_losses_nanonats"] = [1, 2, 3, 4, 5]
        self._assert_err("EMPIRICAL_ANCHOR_MISMATCH", verifier._crosscheck_empirical_anchors, emp_bad_list)
        emp_nonlist = copy.deepcopy(emp_good)
        emp_nonlist["part2_sovereign_stack"]["vram_and_training_ablations"]["full_4way_3bpw_csr0p50_lora_r64_cce_det_run1"]["step_losses_nanonats"] = oracle.PINNED_LIVE_ANCHORS["full_r64_step_losses_nano"]
        self._assert_err("EMPIRICAL_ANCHOR_MISMATCH", verifier._crosscheck_empirical_anchors, emp_nonlist)

        # Invalid schema dict & keyset traps
        self._assert_err("INVALID_SCHEMA_DICT", verifier._require_exact_dict, [], frozenset(), "d")
        self._assert_err("INVALID_SCHEMA_KEYS", verifier._require_exact_dict, {"x": 1}, frozenset({"y"}), "d")
        c_bad_top = copy.deepcopy(base)
        c_bad_top["schema_version"] = "bad"
        self._assert_err("SCHEMA_MISMATCH", verifier.verify_certificate_dict, c_bad_top, full_replay=False)
        c_bad_tid = copy.deepcopy(base)
        c_bad_tid["track_id"] = "bad"
        self._assert_err("SCHEMA_MISMATCH", verifier.verify_certificate_dict, c_bad_tid, full_replay=False)

    def test_cli_modes_errors_and_artifacts_loader(self) -> None:
        # Artifact loader UTF-8 & toolchain traps
        with tempfile.TemporaryDirectory(prefix="s86_art_") as tmpd:
            td = Path(tmpd)
            (td / "SovereignStackFourthOrder.lean").write_bytes(b"\xff")
            self._assert_err("INVALID_UTF8", verifier._load_static_track_artifacts, td)
            (td / "SovereignStackFourthOrder.lean").write_bytes((_THIS_DIR / "SovereignStackFourthOrder.lean").read_bytes())
            (td / "lean-toolchain").write_bytes(b"\xff")
            self._assert_err("INVALID_UTF8", verifier._load_static_track_artifacts, td)
            (td / "lean-toolchain").write_bytes(b"leanprover/lean4:v4.0.0\n")
            self._assert_err("TOOLCHAIN_MISMATCH", verifier._load_static_track_artifacts, td)

        # CLI argument parser & end-to-end modes
        self._assert_err("INVALID_ARGV", verifier._parse_cli_args, ("--json",))
        self._assert_err("NUL_BYTE_FORBIDDEN", verifier._parse_cli_args, ["--json\x00"])
        self._assert_err("DUPLICATE_FLAG", verifier._parse_cli_args, ["--json", "--json"])
        self._assert_err("CONFLICTING_MODE", verifier._parse_cli_args, ["--standalone", "--verify-lean"])
        self._assert_err("CONFLICTING_MODE", verifier._parse_cli_args, ["--standalone", "--check", "x"])
        self._assert_err("CONFLICTING_MODE", verifier._parse_cli_args, ["--standalone", "--check=x"])
        self._assert_err("MISSING_PATH_ARG", verifier._parse_cli_args, ["--check"])
        self._assert_err("INVALID_PATH_ARG", verifier._parse_cli_args, ["--check", "-bad"])
        self._assert_err("INVALID_PATH_ARG", verifier._parse_cli_args, ["--check", ""])
        self._assert_err("INVALID_PATH_ARG", verifier._parse_cli_args, ["--check", "a\x00b"])
        self._assert_err("INVALID_PATH_ARG", verifier._parse_cli_args, ["--write="])
        self._assert_err("INVALID_PATH_ARG", verifier._parse_cli_args, ["--check=-bad"])
        self._assert_err("INVALID_PATH_ARG", verifier._parse_cli_args, ["--verify-lean", ""])
        self._assert_err("INVALID_PATH_ARG", verifier._parse_cli_args, ["--verify-lean", "a\x00b"])
        self._assert_err("UNKNOWN_FLAG", verifier._parse_cli_args, ["--standalone", "extra"])
        self.assertEqual(verifier._parse_cli_args(["--verify-lean"]), {"mode": "verify-lean", "target": None, "json": False})
        self.assertEqual(verifier._parse_cli_args(["--verify-lean", "--json"]), {"mode": "verify-lean", "target": None, "json": True})
        self._assert_err("UNKNOWN_FLAG", verifier._parse_cli_args, ["--unknown"])

        # Default, standalone, write, check (text & --json)
        cert_disk = _THIS_DIR / "s86_sovereign_stack_certificate.json"
        buf = io.StringIO()
        with mock.patch.object(sys, "stdout", buf):
            self.assertEqual(verifier.main(["--standalone"]), 0)
        self.assertEqual(buf.getvalue().encode("ascii"), cert_disk.read_bytes())

        for argv_ok in (
            [],
            ["--json"],
            ["--check", str(cert_disk)],
            [f"--check={cert_disk}", "--json"],
        ):
            b_out = io.StringIO()
            with mock.patch.object(sys, "stdout", b_out):
                self.assertEqual(verifier.main(argv_ok), 0)
            self.assertTrue(len(b_out.getvalue()) > 0)

        with tempfile.TemporaryDirectory(prefix="s86_cli_") as tmpd:
            out_p = Path(tmpd) / "cert.json"
            b1 = io.StringIO()
            with mock.patch.object(sys, "stdout", b1):
                self.assertEqual(verifier.main(["--write", str(out_p)]), 0)
            self.assertIn("WROTE ", b1.getvalue())
            b2 = io.StringIO()
            with mock.patch.object(sys, "stdout", b2):
                self.assertEqual(verifier.main([f"--write={out_p}", "--json"]), 0)
            self.assertTrue(json.loads(b2.getvalue())["written"])
            self.assertEqual(out_p.read_bytes(), cert_disk.read_bytes())

        b_err = io.StringIO()
        with mock.patch.object(sys, "stderr", b_err):
            self.assertEqual(verifier.main(["--bogus"]), 2)
        self.assertEqual(json.loads(b_err.getvalue())["code"], "UNKNOWN_FLAG")


if __name__ == "__main__":
    unittest.main()
