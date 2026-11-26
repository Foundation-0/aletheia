#!/usr/bin/env python3
"""R5 test suite for Track S160 EXP-Q42b verifier."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

BASE = Path(os.path.abspath(str(Path(__file__).parent)))
sys.path.insert(0, str(BASE))
import verify_s160_q42b_prior_tilt as vmod

ERR = vmod.PriorTiltVerifyError


def wit(**kw):
    w = vmod.canonical_witness()
    w.update(kw)
    return w


def good_runner(_lean):
    lines = ["'PriorTilt.t" + str(i) + "' depends on axioms: [propext, Quot.sound]" for i in range(7)]
    lines.append("'PriorTilt.a' does not depend on any axioms")
    lines.append("'PriorTilt.b' does not depend on any axioms")
    return {"version_rc": 0, "version_output": "Lean (version 4.36.0)", "build_rc": 0, "build_output": "ok", "axiom_rc": 0, "axiom_stdout": "\n".join(lines) + "\n"}


def runner_with(**kw):
    def run(lean):
        out = good_runner(lean)
        out.update(kw)
        return out
    return run


def copy_lean(tmp):
    dest = Path(tmp) / "lean"
    shutil.copytree(BASE / "lean", dest, ignore=shutil.ignore_patterns(".lake"))
    return Path(tmp)


class TestQ42bR5(unittest.TestCase):
    def test_witness(self):
        res = vmod.verify_witness_q()
        self.assertEqual(res["real_net"], 77)
        self.assertEqual(res["flipped_net"], 52)
        self.assertEqual(res["real_rate"], "11/58")
        self.assertEqual(res["flipped_rate"], "26/203")
        cases = [
            ("W_IMBALANCE", wit(imbalance=1)),
            ("W_IMBALANCE_POS", wit(pos_errors=10, neg_errors=10, imbalance=0)),
            ("W_FEEDBACK_DIFF", wit(feedback_diff=1)),
            ("W_FEEDBACK_POS", wit(feedback_pos=7, feedback_neg=7, feedback_diff=0)),
            ("W_REAL_NET", wit(real_net=1)),
            ("W_FLIP_NET", wit(flipped_net=1)),
            ("W_REAL_POS", wit(real_majority=0, real_minority=0, real_net=0)),
            ("W_FLIP_POS", wit(flipped_majority=0, flipped_minority=0, flipped_net=0)),
            ("W_COMPARABLE_POS", wit(comparable_pairs=0)),
            ("W_REAL_RATE", wit(real_majority=76, real_net=78)),
            ("W_FLIP_RATE", wit(flipped_minority=53, flipped_net=53)),
            ("W_REAL_GCD", wit(real_majority=75, real_minority=2, real_net=77, comparable_pairs=406)),
        ]
        for code, bad in cases[:-1]:
            with self.assertRaisesRegex(ERR, "^" + code + ":"):
                vmod.verify_witness_q(bad)
        # W_REAL_GCD: keep rate 11/58 via 22/116 - sums must hold
        with self.assertRaisesRegex(ERR, "^W_REAL_GCD:"):
            vmod.verify_witness_q(wit(real_majority=2231, real_minority=2, real_net=2233, flipped_majority=0, flipped_minority=1508, flipped_net=1508, comparable_pairs=11774))

    def test_balanced(self):
        res = vmod.verify_balanced_q()
        self.assertEqual(res["balanced_numerator"], 0)
        self.assertEqual(res["imbalanced_numerator"], 1158)
        with self.assertRaisesRegex(ERR, "^B_BALANCED_NONZERO:"):
            vmod.verify_balanced_q(f_pos=6)
        with self.assertRaisesRegex(ERR, "^B_COUNTS_UNEQUAL:"):
            vmod.verify_balanced_q(f_pos=0, r_neg=0, n_pos=1, n_neg=2)
        with self.assertRaisesRegex(ERR, "^B_IMBALANCED_NONPOS:"):
            vmod.verify_balanced_q(imb_f=1)
        with self.assertRaisesRegex(ERR, "^B_IMBALANCED_NONPOS:"):
            vmod.verify_balanced_q(imb_npos=18, imb_nneg=7)
        with self.assertRaisesRegex(ERR, "^B_IMBALANCED_VALUE:"):
            vmod.verify_balanced_q(imb_f=19)

    def test_contraction(self):
        res = vmod.verify_contraction_q()
        self.assertEqual(res["factor"], "1/625")
        self.assertEqual(res["p"], "3/4")
        self.assertEqual(res["p_input"], "45/60")
        with self.assertRaisesRegex(ERR, "^C_P_REDUCED:"):
            vmod.verify_contraction_q(p_num=1, p_den=2)
        with self.assertRaisesRegex(ERR, "^C_B_DEN_POS:"):
            vmod.verify_contraction_q(b_den=0)
        with self.assertRaisesRegex(ERR, "^C_GATE:"):
            vmod.verify_contraction_q(b_num=40, b_den=50)
        with self.assertRaisesRegex(ERR, "^C_GATE:"):
            vmod.verify_contraction_q(b_num=1, b_den=2, p_num=3, p_den=4)
        with self.assertRaisesRegex(ERR, "^C_FACTOR:"):
            vmod.verify_contraction_q(b_num=1, b_den=25)
        with self.assertRaisesRegex(ERR, "^C_NEXT_NEG:"):
            vmod.verify_contraction_q(remainders=(10, -1))
        with self.assertRaisesRegex(ERR, "^C_STEP:"):
            vmod.verify_contraction_q(remainders=(10, 1))
        with self.assertRaisesRegex(ERR, "^C_SCALE_POS:"):
            vmod.verify_contraction_q(grid_cases=((0, 0, 0),))
        with self.assertRaisesRegex(ERR, "^C_GRID_LO:"):
            vmod.verify_contraction_q(grid_cases=((0, 10, 3),))
        with self.assertRaisesRegex(ERR, "^C_GRID_HI:"):
            vmod.verify_contraction_q(grid_cases=((100, 0, 3),))
        lo_edge = vmod.verify_contraction_q(grid_cases=((1, 1, 2),))
        hi_edge = vmod.verify_contraction_q(grid_cases=((3, 1, 2),))
        self.assertEqual((lo_edge["grid_checks"], hi_edge["grid_checks"]), (1, 1))

    def test_strict_io(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = root / "good.json"
            good.write_bytes(b'{"a": 1}\n')
            self.assertEqual(vmod.read_strict_json(good), {"a": 1})
            with self.assertRaisesRegex(ERR, "^READ_OPEN:"):
                vmod.read_strict_bytes(root / "missing.json")
            fifo = root / "pipe"
            os.mkfifo(fifo)
            with self.assertRaisesRegex(ERR, "^NOT_REGULAR:"):
                vmod.read_strict_bytes(fifo)
            link = root / "link.json"
            link.symlink_to(good)
            with self.assertRaisesRegex(ERR, "^SYMLINK_ANCESTOR:"):
                vmod.read_strict_bytes(link)
            exact_big = root / "exact_big.json"
            exact_big.write_bytes(b"{}" + b" " * (vmod.MAX_BYTES - 3) + b"\n")
            self.assertEqual(len(exact_big.read_bytes()), vmod.MAX_BYTES)
            self.assertEqual(vmod.read_strict_json(exact_big), {})
            big = root / "big.bin"
            big.write_bytes(b"a" * 1048577)
            with self.assertRaisesRegex(ERR, "^TOO_LARGE:"):
                vmod.read_strict_bytes(big)
            for code, raw in [("BAD_UTF8", b"\xff\n"), ("BAD_BOM", '{"a": 1}\n'.encode("utf-8-sig")), ("BAD_LF", b'{"a": 1}\r\n'), ("BAD_FINAL_LF", b'{"a": 1}')]:
                p = root / (code + ".json")
                p.write_bytes(raw)
                with self.assertRaisesRegex(ERR, "^" + code + ":"):
                    vmod.read_strict_text(p)

    def test_strict_json_parse(self):
        cases = [
            ("DEPTH", "{" + '"a": {' * 33 + "1" + "}" * 34 + "\n"),
            ("UNBALANCED", "]\n"),
            ("UNBALANCED_FINAL", "{\n"),
            ("INT_DIGITS", '{"a": ' + "1" * 257 + "}\n"),
            ("FLOAT_TOKEN", '{"a": 12' + "." + "5}\n"),
            ("FLOAT_TOKEN", '{"a": 1e5}\n'),
            ("UNTERMINATED_JSON_STRING", '"abc\n'),
            ("DUP_KEY", '{"a": 1, "a": 2}\n'),
            ("BAD_CONSTANT", '{"a": NaN}\n'),
            ("BAD_JSON", '{"a": }\n'),
            ("NOT_OBJECT", "[1, 2]\n"),
        ]
        for code, text in cases:
            with self.assertRaisesRegex(ERR, "^" + code + ":"):
                vmod.parse_strict_json(text)
        deep400 = '{"a": ' + "9" * 400 + "}\n"
        with self.assertRaisesRegex(ERR, "^INT_DIGITS:"):
            vmod.parse_strict_json(deep400)
        self.assertEqual(vmod.parse_strict_json('{"a": {"b": [1, 2]}}\n'), {"a": {"b": [1, 2]}})
        d32 = '{"a": ' + "[" * 31 + "0" + "]" * 31 + "}\n"
        self.assertIsInstance(vmod.parse_strict_json(d32), dict)
        n256 = '{"a": ' + "9" * 256 + "}\n"
        self.assertEqual(vmod.parse_strict_json(n256)["a"], int("9" * 256))

    def test_lean_strip_and_axioms(self):
        self.assertNotIn("sorry", vmod.strip_lean_comments_and_strings("-- sorry\ntheorem x := 1\n"))
        self.assertNotIn("sorry", vmod.strip_lean_comments_and_strings('def s := "sorry"\n'))
        with self.assertRaisesRegex(ERR, "^UNTERMINATED_BLOCK_COMMENT:"):
            vmod.strip_lean_comments_and_strings("/- abc")
        with self.assertRaisesRegex(ERR, "^UNTERMINATED_STRING_LITERAL:"):
            vmod.strip_lean_comments_and_strings('"abc')
        good = good_runner(Path("x"))["axiom_stdout"].splitlines()
        counts = vmod.validate_axiom_lines(good, 9)
        self.assertEqual(counts["zero_axiom"], 2)
        with self.assertRaisesRegex(ERR, "^AXIOM_LINE_COUNT:"):
            vmod.validate_axiom_lines([], 9)
        for code, line in [("AXIOM_LINE_FORMAT", "garbage"), ("AXIOM_LBRACKET", "x depends on axioms: propext]"), ("AXIOM_RBRACKET", "x depends on axioms: [propext"), ("FORBIDDEN_AXIOM", "x depends on axioms: [Classical.choice]")]:
            with self.assertRaisesRegex(ERR, "^" + code + ":"):
                vmod.validate_axiom_lines([line] * 9, 9)

    def test_lean_package_fake(self):
        info = vmod.verify_lean_package(BASE, lean_runner=good_runner)
        self.assertEqual(info["public_theorems"], 9)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ERR, "^MISSING_LEAN_DIR:"):
                vmod.verify_lean_package(Path(tmp))
        variants = []
        def bad_toolchain(root):
            (root / "lean" / "lean-toolchain").write_text("leanprover/lean4:v0\n", encoding="utf-8")
        variants.append(("BAD_TOOLCHAIN", bad_toolchain))
        def bad_manifest(root):
            (root / "lean" / "lake-manifest.json").write_text('{"packages": [{"x": 1}]}\n', encoding="utf-8")
        variants.append(("NONEMPTY_PACKAGES", bad_manifest))
        def extra_file(root):
            (root / "lean" / "Extra.lean").write_text("theorem extra : True := trivial\n", encoding="utf-8")
        variants.append(("LEAN_FILE_COUNT", extra_file))
        def escape(root):
            p = root / "lean" / "PriorTilt" / "Basic.lean"
            p.write_text(p.read_text(encoding="utf-8") + "theorem bad : True := sorry\n", encoding="utf-8")
        variants.append(("LEAN_ESCAPE", escape))
        def eval_escape(root):
            p = root / "lean" / "PriorTilt" / "Basic.lean"
            p.write_text(p.read_text(encoding="utf-8") + "#eval 1\n", encoding="utf-8")
        variants.append(("LEAN_ESCAPE", eval_escape))
        def bad_import(root):
            p = root / "lean" / "PriorTilt" / "Basic.lean"
            p.write_text("import Mathlib\n" + p.read_text(encoding="utf-8"), encoding="utf-8")
        variants.append(("BAD_IMPORT", bad_import))
        def thm_count(root):
            p = root / "lean" / "PriorTilt" / "Basic.lean"
            p.write_text(p.read_text(encoding="utf-8").replace("theorem netGain_pos_of_gt", "theoremX netGain_pos_of_gt", 1), encoding="utf-8")
        variants.append(("THM_COUNT", thm_count))
        def audit_count(root):
            p = root / "lean" / "AxiomAudit.lean"
            lines = p.read_text(encoding="utf-8").splitlines(True)
            p.write_text("".join(lines[:-1]), encoding="utf-8")
        variants.append(("AUDIT_COUNT", audit_count))
        def audit_set(root):
            p = root / "lean" / "AxiomAudit.lean"
            p.write_text(p.read_text(encoding="utf-8").replace("netGain_pos_of_gt", "nope_name", 1), encoding="utf-8")
        variants.append(("AUDIT_SET", audit_set))
        for code, mutate in variants:
            with tempfile.TemporaryDirectory() as tmp:
                root = copy_lean(tmp)
                mutate(root)
                with self.assertRaisesRegex(ERR, "^" + code + ":"):
                    vmod.verify_lean_package(root)
        for code, kw in [("LEAN_VERSION_RC", {"version_rc": 1}), ("BAD_LEAN_VERSION", {"version_output": "Lean (version 0)"}), ("LAKE_BUILD_FAIL", {"build_rc": 1}), ("LAKE_BUILD_WARNING", {"build_output": "warning: x"}), ("AXIOM_RC", {"axiom_rc": 1}), ("AXIOM_LINE_COUNT", {"axiom_stdout": ""})]:
            with self.assertRaisesRegex(ERR, "^" + code + ":"):
                vmod.verify_lean_package(BASE, lean_runner=runner_with(**kw))

    def test_payload_and_ast(self):
        payload = vmod.build_payload(base=BASE)
        self.assertEqual(payload["witness"]["real_net"], 77)
        self.assertEqual(payload["contraction"]["factor"], "1/625")
        src = (BASE / "verify_s160_q42b_prior_tilt.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        self.assertEqual(sum(1 for n in ast.walk(tree) if isinstance(n, ast.BoolOp)), 0)
        self.assertEqual(sum(1 for n in ast.walk(tree) if isinstance(n, ast.Assert)), 0)
        floats = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, float)]
        self.assertEqual(floats, [])
        self.assertNotIn("/home/", src)
        self.assertNotIn("float(", src)
        cert = vmod.read_strict_json(BASE / "s160_q42b_prior_tilt_certificate.json")
        self.assertEqual(cert, payload)

    def test_main_recursion_and_os(self):
        orig = vmod.build_payload
        try:
            vmod.build_payload = lambda **kw: (_ for _ in ()).throw(RecursionError("x"))
            self.assertEqual(vmod.main(["--standalone"]), 2)
            vmod.build_payload = lambda **kw: (_ for _ in ()).throw(OSError("x"))
            self.assertEqual(vmod.main(["--standalone"]), 2)
            vmod.build_payload = lambda **kw: (_ for _ in ()).throw(ERR("X_CODE", "y"))
            self.assertEqual(vmod.main(["--standalone"]), 2)
        finally:
            vmod.build_payload = orig
        self.assertEqual(vmod.main([]), 0)
        self.assertEqual(vmod.main(["--check", "--standalone"]), 2)

    def test_cli_subprocess(self):
        env = dict(os.environ)
        env["CUDA_VISIBLE_DEVICES"] = ""
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        run = subprocess.run([sys.executable, "-I", "-B", "verify_s160_q42b_prior_tilt.py", "--check", "--json"], cwd=str(BASE), env=env, capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(run.returncode, 0)
        self.assertNotIn("Traceback", run.stderr)
        parsed = json.loads(run.stdout)
        self.assertEqual(parsed["queue_id"], "EXP-Q42b")
        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "cert.json"
            data = json.loads((BASE / "s160_q42b_prior_tilt_certificate.json").read_text(encoding="utf-8"))
            data["witness"]["real_net"] = 78
            tampered.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            bad = subprocess.run([sys.executable, "-I", "-B", "verify_s160_q42b_prior_tilt.py", "--check", str(tampered), "--json"], cwd=str(BASE), env=env, capture_output=True, text=True, timeout=60, check=False)
            self.assertEqual(bad.returncode, 2)
            self.assertIn("CERT_MISMATCH", bad.stderr)
            self.assertNotIn("Traceback", bad.stderr)
            big = Path(tmp) / "big.json"
            big.write_text('{"a": ' + "9" * 400 + "}\n", encoding="utf-8")
            env2 = dict(env)
            env2["PYTHONINTMAXSTRDIGITS"] = "0"
            bigrun = subprocess.run([sys.executable, "-I", "-B", "verify_s160_q42b_prior_tilt.py", "--check", str(big), "--json"], cwd=str(BASE), env=env2, capture_output=True, text=True, timeout=60, check=False)
            self.assertEqual(bigrun.returncode, 2)
            self.assertIn("INT_DIGITS", bigrun.stderr)
            self.assertNotIn("Traceback", bigrun.stderr)
            orig_loads = vmod.json.loads
            try:
                vmod.json.loads = lambda *a, **kw: (_ for _ in ()).throw(ValueError("limit"))
                with self.assertRaisesRegex(ERR, "^BAD_JSON:"):
                    vmod.parse_strict_json('{"a": 1}\n')
            finally:
                vmod.json.loads = orig_loads
            real_sub = Path(tmp) / "real" / "sub"
            real_sub.mkdir(parents=True)
            link_anc = Path(tmp) / "real" / "sym"
            link_anc.symlink_to(real_sub)
            dotdot = str(link_anc) + "/../sub/target.json"
            (real_sub / "target.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ERR, "^SYMLINK_ANCESTOR:"):
                vmod.read_strict_bytes(dotdot)
            cwd_orig = os.getcwd()
            try:
                os.chdir(str(BASE))
                rel_cert = vmod.read_strict_json("s160_q42b_prior_tilt_certificate.json")
                self.assertEqual(rel_cert["queue_id"], "EXP-Q42b")
            finally:
                os.chdir(cwd_orig)
            with self.assertRaisesRegex(ERR, "^READ_OPEN:"):
                vmod.read_strict_bytes("/")
            dfd, leaf = vmod._open_parent_nofollow("/tmp")
            os.close(dfd)
            self.assertEqual(leaf, "tmp")
            with self.assertRaisesRegex(ERR, "^READ_OPEN:"):
                vmod.read_strict_bytes("/nonexistent_q42b_top_entry")
            with self.assertRaisesRegex(ERR, "^READ_OPEN:"):
                vmod.read_strict_bytes(str(BASE / "missing_subdir" / "s160_q42b_prior_tilt_certificate.json"))


if __name__ == "__main__":
    unittest.main()
