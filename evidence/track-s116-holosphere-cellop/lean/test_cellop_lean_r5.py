#!/usr/bin/env python3
"""R5 Adversarial & Live-Lean Test Suite for HoloSphereCellOpInvariants.lean (#37-#40 + #40b).

Zero bare asserts; 0 skips when Lean 4.36.0 is available (skips live-Lean kernel checks
cleanly when no ``lean`` binary is installed); runs cleanly across -I -B, -I -O -B, and -I -B -W error.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

LEAN_DIR = Path(__file__).resolve().parent
if str(LEAN_DIR) not in sys.path:
    sys.path.insert(0, str(LEAN_DIR))

import verify_cellop_lean as ver


class TestCellOpLeanInvariants(unittest.TestCase):
    def test_01_algebraic_witnesses_exact(self) -> None:
        res = ver.verify_algebraic_witnesses()
        self.assertEqual(res["blockh4_exhaustive_vectors"], 65536)
        self.assertEqual(res["blockh4_tight_range"], [-32, 30])
        self.assertEqual(res["h256_pairs_checked"], 32896)
        self.assertEqual(res["bent4_const_warps_of_2048"], 0)

    def test_02_r13b_lexer_and_all_18_static_rules(self) -> None:
        clean_src = ver.DEFAULT_LEAN_PATH.read_text(encoding="utf-8")
        info = ver.audit_lean4_static(clean_src)
        self.assertEqual(info["static_rules_checked"], 18)
        self.assertEqual(info["public_theorem_count"], 5)
        self.assertEqual(info["private_theorem_count"], 30)

        # Prime identifiers must NOT be misparsed as Char literals
        primed = clean_src.replace("def popc8", "-- comment with sorry and \"quote\"\ndef x' : Int := 1\ndef popc8", 1)
        self.assertEqual(ver.audit_lean4_static(primed)["public_theorem_count"], 5)

        snippets = (
            ("R01_LITERAL_OR_GUILLEMET", 'def s := "bad"\n'),
            ("R02_IMPORT", "import Init\n"),
            ("R03_SORRY_ADMIT", "def x := sorry\n"),
            ("R04_AXIOM_DECL", "axiom bad : False\n"),
            ("R05_UNSAFE_EXTERN", "unsafe def u : Nat := 0\n"),
            ("R06_OPAQUE_PARTIAL", "noncomputable def nc : Nat := 0\n"),
            ("R07_NATIVE_DECIDE", "theorem t : True := by native_decide\n"),
            ("R08_DBG_TRACE", "def d := dbg_trace 1\n"),
            ("R09_INIT_EXPORT_ATTR", "@[export c_fn] def f : Nat := 0\n"),
            ("R10_GUARD_MSGS", "#guard_msgs in\n"),
            ("R11_WARN_SORRY_OPT", "def w := terminalTacticsAsSorry\n"),
            ("R12_META_EVAL_CMD", "#eval 1 + 1\n"),
            ("R13_SET_OPTION", "set_option maxHeartbeats 0\n"),
            ("R14_ELAB_TACTIC_MACRO", "macro_rules | `(t) => `(t)\n"),
            ("R15_IO_SYSTEM", "def io := IO.println\n"),
            ("R16_PANIC_UNREACHABLE", "def p := panic! 0\n"),
            ("R17_DECIDE_CONFIG", "def c := decide (config := { native := true })\n"),
            ("R18_ROOT_ESCAPE", "def r := _root_.Nat\n"),
        )
        for expected_code, poison in snippets:
            with self.assertRaises(ver.CellOpLeanError) as cm:
                ver.audit_lean4_static(poison + clean_src)
            self.assertEqual(cm.exception.code, expected_code)

    def test_03_axiom_allowlist_blocks_choice_and_ofreducebool(self) -> None:
        good_lines = [
            f"'{thm}' depends on axioms: [propext, Quot.sound]"
            for thm in ver.PUBLIC_THEOREMS
        ]
        parsed = ver.parse_and_audit_lean_axioms("\n".join(good_lines) + "\n")
        self.assertEqual(len(parsed), 5)

        for forbidden in ("Classical.choice", "Lean.ofReduceBool", "sorryAx"):
            bad = list(good_lines)
            bad[3] = f"'{ver.PUBLIC_THEOREMS[3]}' depends on axioms: [propext, {forbidden}]"
            with self.assertRaises(ver.CellOpLeanError) as cm:
                ver.parse_and_audit_lean_axioms("\n".join(bad) + "\n")
            self.assertEqual(cm.exception.code, "FORBIDDEN_AXIOM")

    def _require_lean_or_skip(self) -> str:
        try:
            return ver.resolve_lean_binary()
        except ver.CellOpLeanError as exc:
            if exc.code == "LEAN_BINARY_UNAVAILABLE":
                self.skipTest("lean binary unavailable in PATH")
            raise

    def test_04_live_lean_and_init_olean_hijack_blocked(self) -> None:
        lean_bin = self._require_lean_or_skip()
        res = ver.verify_lean4_file_live(ver.DEFAULT_LEAN_PATH, check_sha=True)
        self.assertEqual(res["theorems_verified"], 5)
        self.assertEqual(res["lean_source_sha256"], ver.LEAN_SOURCE_SHA256)

        src = ver.DEFAULT_LEAN_PATH.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory(prefix="cellop_hijack_") as td:
            fake_dir = Path(td)
            (fake_dir / "Init.olean").write_bytes(b"CORRUPT_FAKE_INIT_OLEAN")
            poison_env = dict(os.environ)
            poison_env["LEAN_PATH"] = str(fake_dir)
            raw_proc = subprocess.run([lean_bin, "--stdin"], input=src, capture_output=True, text=True, env=poison_env, timeout=60, check=False)
            self.assertNotEqual(raw_proc.returncode, 0)

            old_lp = os.environ.get("LEAN_PATH")
            try:
                os.environ["LEAN_PATH"] = str(fake_dir)
                clean_res = ver.verify_lean4_file_live(ver.DEFAULT_LEAN_PATH, check_sha=True)
                self.assertEqual(clean_res["theorems_verified"], 5)
            finally:
                if old_lp is None:
                    os.environ.pop("LEAN_PATH", None)
                else:
                    os.environ["LEAN_PATH"] = old_lp

    def test_05_cli_unknown_flag_refusal(self) -> None:
        out_buf2, err_buf2 = io.StringIO(), io.StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = out_buf2, err_buf2
            rc_bad = ver.main(["--unknown"])
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        self.assertEqual(rc_bad, 2)
        self.assertIn("UNKNOWN_FLAG", err_buf2.getvalue())

    def test_06_cli_verify_lean_json_mode(self) -> None:
        self._require_lean_or_skip()
        out_buf, err_buf = io.StringIO(), io.StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = out_buf, err_buf
            rc = ver.main(["--verify-lean", "--json"])
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        self.assertEqual(rc, 0)
        payload = json.loads(out_buf.getvalue())
        self.assertEqual(payload["status"], "OK")
        self.assertEqual(payload["theorems_verified"], 5)


if __name__ == "__main__":
    unittest.main()
