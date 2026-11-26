#!/usr/bin/env python3
"""R5 test suite for Track S160 EXP-Q42c verifier."""
from __future__ import annotations

import ast
from fractions import Fraction
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
import verify_s160_q42c_reciprocity_gate as vmod

ERR = vmod.ReciprocityVerifyError


def good_runner(_lean):
    lines = ["'ReciprocityGate.t" + str(i) + "' depends on axioms: [propext, Quot.sound]" for i in range(7)]
    lines.append("'ReciprocityGate.a' does not depend on any axioms")
    lines.append("'ReciprocityGate.b' does not depend on any axioms")
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


class TestQ42cR5(unittest.TestCase):
    def test_correlated(self):
        res = vmod.evaluate_correlated_false_accept(Fraction(1, 10), Fraction(1, 5), Fraction(1, 2))
        self.assertEqual(res, {"eps1": "1/10", "eps2": "1/5", "rho": "1/2", "minimum": "1/10", "joint": "3/50", "independent": "1/50", "excess": "1/25", "strict": True})
        swapped = vmod.evaluate_correlated_false_accept(Fraction(1, 5), Fraction(1, 10), Fraction(1, 2))
        self.assertEqual(swapped["minimum"], "1/10")
        self.assertEqual(swapped["joint"], "3/50")
        ind = vmod.evaluate_correlated_false_accept(Fraction(1, 10), Fraction(1, 5), Fraction(0, 1))
        self.assertEqual(ind["joint"], "1/50")
        self.assertEqual(ind["excess"], "0/1")
        self.assertEqual(ind["strict"], False)
        zero = vmod.evaluate_correlated_false_accept(Fraction(0, 1), Fraction(1, 5), Fraction(1, 1))
        self.assertEqual(zero["joint"], "0/1")
        self.assertEqual(zero["strict"], False)
        zero2 = vmod.evaluate_correlated_false_accept(Fraction(1, 5), Fraction(0, 1), Fraction(1, 1))
        self.assertEqual(zero2["joint"], "0/1")
        self.assertEqual(zero2["strict"], False)
        one = vmod.evaluate_correlated_false_accept(Fraction(1, 1), Fraction(1, 1), Fraction(1, 3))
        self.assertEqual(one["joint"], "1/1")
        self.assertEqual(one["excess"], "0/1")
        self.assertEqual(one["strict"], False)
        cases = [
            ("EPS1_LO", (Fraction(-1, 10), Fraction(1, 5), Fraction(0, 1))),
            ("EPS1_HI", (Fraction(11, 10), Fraction(1, 5), Fraction(0, 1))),
            ("EPS2_LO", (Fraction(1, 10), Fraction(-1, 5), Fraction(0, 1))),
            ("EPS2_HI", (Fraction(1, 10), Fraction(6, 5), Fraction(0, 1))),
            ("RHO_LO", (Fraction(1, 10), Fraction(1, 5), Fraction(-1, 2))),
            ("RHO_HI", (Fraction(1, 10), Fraction(1, 5), Fraction(3, 2))),
        ]
        for code, args in cases:
            with self.assertRaisesRegex(ERR, "^" + code + ":"):
                vmod.evaluate_correlated_false_accept(args[0], args[1], args[2])

    def test_collation_factor(self):
        res = vmod.collation_factor(Fraction(1, 10), Fraction(1, 5))
        self.assertEqual(res, {"eps_a": "1/10", "eps_b": "1/5", "minimum": "1/10", "product": "1/50", "factor": "5/1", "strict": True})
        unit = vmod.collation_factor(Fraction(1, 1), Fraction(1, 2))
        self.assertEqual(unit["factor"], "1/1")
        self.assertEqual(unit["strict"], False)
        unit2 = vmod.collation_factor(Fraction(1, 2), Fraction(1, 1))
        self.assertEqual(unit2["factor"], "1/1")
        self.assertEqual(unit2["strict"], False)
        swapped = vmod.collation_factor(Fraction(1, 5), Fraction(1, 10))
        self.assertEqual(swapped["factor"], "5/1")
        cases = [
            ("EPSA_POS", (Fraction(0, 1), Fraction(1, 5))),
            ("EPSA_HI", (Fraction(2, 1), Fraction(1, 5))),
            ("EPSB_POS", (Fraction(1, 10), Fraction(0, 1))),
            ("EPSB_HI", (Fraction(1, 10), Fraction(3, 2))),
        ]
        for code, args in cases:
            with self.assertRaisesRegex(ERR, "^" + code + ":"):
                vmod.collation_factor(args[0], args[1])

    def test_witness(self):
        res = vmod.verify_correlated_witness_q()
        self.assertEqual(res["independent"]["joint"], "1/50")
        self.assertEqual(res["partial"]["joint"], "3/50")
        self.assertEqual(res["partial"]["excess"], "1/25")
        self.assertEqual(res["full"]["joint"], "1/10")
        self.assertEqual(res["collation"]["factor"], "5/1")

    def test_decomposition(self):
        empty = vmod.reciprocity_decomposition(set())
        self.assertEqual(empty, {"mutual_pairs": 0, "single_pairs": 0, "trace_a2": 0, "skew_pairs": 0, "total_edges": 0, "unordered_pairs": 0})
        single = vmod.reciprocity_decomposition({("a", "b")})
        self.assertEqual(single, {"mutual_pairs": 0, "single_pairs": 1, "trace_a2": 0, "skew_pairs": 1, "total_edges": 1, "unordered_pairs": 1})
        mixed = vmod.reciprocity_decomposition({("a", "b"), ("b", "a"), ("c", "d"), ("d", "c"), ("a", "c")})
        self.assertEqual(mixed, {"mutual_pairs": 2, "single_pairs": 1, "trace_a2": 4, "skew_pairs": 1, "total_edges": 5, "unordered_pairs": 3})

    def test_audit_graph(self):
        res = vmod.audit_review_graph_reciprocity(vmod.canonical_honest_edges(), vmod.canonical_assignments())
        self.assertEqual(res, {"nodes": 5, "edges": 5, "mutual_pairs": 0, "trace_a2": 0, "skew_pairs": 5, "admitted": True})
        empty = vmod.audit_review_graph_reciprocity((), vmod.canonical_assignments())
        self.assertEqual(empty, {"nodes": 0, "edges": 0, "mutual_pairs": 0, "trace_a2": 0, "skew_pairs": 0, "admitted": True})
        one = vmod.audit_review_graph_reciprocity((("sand-sail", "scarlet-nail"),), vmod.canonical_assignments())
        self.assertEqual(one["nodes"], 2)
        self.assertEqual(one["edges"], 1)
        self.assertEqual(one["skew_pairs"], 1)
        graph = vmod.verify_graph_witness_q()
        self.assertEqual(graph["colluding_decomposition"]["trace_a2"], 2)
        self.assertEqual(graph["honest"]["nodes"], 5)
        with self.assertRaisesRegex(ERR, "^ASSIGNMENTS_DICT:"):
            vmod.audit_review_graph_reciprocity((), [])
        with self.assertRaisesRegex(ERR, "^EDGE_ARITY:"):
            vmod.audit_review_graph_reciprocity((("sand-sail",),), vmod.canonical_assignments())
        with self.assertRaisesRegex(ERR, "^SELF_REVIEW_FORBIDDEN:"):
            vmod.audit_review_graph_reciprocity((("sand-sail", "sand-sail"),), vmod.canonical_assignments())
        with self.assertRaisesRegex(ERR, "^UNKNOWN_REVIEWER:"):
            vmod.audit_review_graph_reciprocity((("ghost", "scarlet-nail"),), vmod.canonical_assignments())
        with self.assertRaisesRegex(ERR, "^UNKNOWN_AUTHOR:"):
            vmod.audit_review_graph_reciprocity((("sand-sail", "ghost"),), vmod.canonical_assignments())
        with self.assertRaisesRegex(ERR, "^NON_DISJOINT_LANE:"):
            vmod.audit_review_graph_reciprocity((("sand-sail", "cedar-fern"),), vmod.canonical_assignments())
        with self.assertRaisesRegex(ERR, "^DUPLICATE_EDGE:"):
            vmod.audit_review_graph_reciprocity((("sand-sail", "scarlet-nail"), ("sand-sail", "scarlet-nail")), vmod.canonical_assignments())
        with self.assertRaisesRegex(ERR, "^RECIPROCITY_2CYCLE_DETECTED:"):
            vmod.audit_review_graph_reciprocity((("sand-sail", "scarlet-nail"), ("scarlet-nail", "sand-sail")), vmod.canonical_assignments())

    def test_auroc_and_rate(self):
        res = vmod.exact_auroc([3, 1], [1, 0])
        self.assertEqual(res, {"wins": 3, "ties": 1, "compared": 4, "auroc": "7/8"})
        self.assertEqual(vmod.exact_auroc([2], [1])["auroc"], "1/1")
        self.assertEqual(vmod.exact_auroc([0], [1])["auroc"], "0/1")
        self.assertEqual(vmod.exact_auroc([1], [1])["auroc"], "1/2")
        with self.assertRaisesRegex(ERR, "^AUROC_POS_EMPTY:"):
            vmod.exact_auroc([], [1])
        with self.assertRaisesRegex(ERR, "^AUROC_NEG_EMPTY:"):
            vmod.exact_auroc([1], [])
        rate = vmod.rate_at_threshold([0, 2, 4, 4], 4)
        self.assertEqual(rate, {"ge_count": 2, "total": 4, "rate": "1/2"})
        self.assertEqual(vmod.rate_at_threshold([0, 1], 4)["rate"], "0/1")
        self.assertEqual(vmod.rate_at_threshold([4, 5], 4)["rate"], "1/1")
        with self.assertRaisesRegex(ERR, "^RATE_EMPTY:"):
            vmod.rate_at_threshold([], 4)

    def test_benchmark(self):
        res = vmod.run_reciprocity_benchmark()
        self.assertEqual(res["auroc"], "1/1")
        self.assertEqual(res["fpr"], "0/1")
        self.assertEqual(res["tpr"], "1/1")
        self.assertEqual(res["wins"], 400)
        self.assertEqual(res["ties"], 0)
        self.assertEqual(res["compared"], 400)
        self.assertEqual(res["planted_scores"], [6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6])
        self.assertEqual(res["null_scores"], [2, 0, 2, 0, 0, 0, 1, 1, 2, 2, 0, 1, 1, 1, 1, 0, 1, 0, 1, 1])
        self.assertEqual(res["planted_edge_counts"], [29, 29, 29, 29, 29, 29, 29, 29, 29, 29, 29, 29, 29, 29, 29, 29, 29, 29, 29, 29])
        self.assertEqual(res["null_edge_counts"], [25, 28, 27, 29, 27, 23, 29, 29, 26, 27, 28, 28, 27, 28, 26, 28, 27, 27, 29, 28])
        self.assertEqual(res["seed"], 16042)
        self.assertEqual(res["threshold"], 4)
        small = vmod.run_reciprocity_benchmark(seed=7, trials=5, nodes=14, planted_pairs=4)
        self.assertEqual(small["planted_scores"], [4, 4, 4, 4, 4])
        self.assertEqual(small["null_scores"], [1, 1, 1, 0, 2])
        self.assertEqual(small["planted_edge_counts"], [17, 17, 17, 17, 17])
        self.assertEqual(small["null_edge_counts"], [15, 15, 16, 17, 17])
        self.assertEqual(small["wins"], 25)
        self.assertEqual(small["compared"], 25)
        with self.assertRaisesRegex(ERR, "^BENCH_TRIALS_POS:"):
            vmod.run_reciprocity_benchmark(trials=0)
        with self.assertRaisesRegex(ERR, "^BENCH_PAIRS_POS:"):
            vmod.run_reciprocity_benchmark(planted_pairs=0)
        with self.assertRaisesRegex(ERR, "^BENCH_NODES_FIT:"):
            vmod.run_reciprocity_benchmark(nodes=12, planted_pairs=6)
        with self.assertRaisesRegex(ERR, "^BENCH_AUROC:"):
            vmod.run_reciprocity_benchmark(seed=7, trials=5, nodes=8, planted_pairs=1)
        with self.assertRaisesRegex(ERR, "^BENCH_TPR:"):
            vmod.run_reciprocity_benchmark(seed=7, trials=5, nodes=30, planted_pairs=3)

    def test_benchmark_gate_boundaries(self):
        orig_rate = vmod.rate_at_threshold
        orig_auroc = vmod.exact_auroc
        try:
            vmod.rate_at_threshold = lambda scores, thr: {"ge_count": 1, "total": len(scores), "rate": "1/100"}
            with self.assertRaisesRegex(ERR, "^BENCH_FPR:"):
                vmod.run_reciprocity_benchmark(seed=7, trials=100, nodes=24, planted_pairs=6)
            vmod.rate_at_threshold = orig_rate
            vmod.exact_auroc = lambda pos, neg: {"wins": 19, "ties": 0, "compared": 20, "auroc": "19/20"}
            edge = vmod.run_reciprocity_benchmark(seed=7, trials=5, nodes=14, planted_pairs=4)
            self.assertEqual(edge["auroc"], "19/20")
            self.assertEqual(edge["wins"], 19)
            self.assertEqual(edge["compared"], 20)
        finally:
            vmod.rate_at_threshold = orig_rate
            vmod.exact_auroc = orig_auroc

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
            ("FLOAT_TOKEN", '{"a": 1E5}\n'),
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
        orig_loads = json.loads
        try:
            json.loads = lambda *a, **k: (_ for _ in ()).throw(RecursionError("x"))
            with self.assertRaisesRegex(ERR, "^RECURSION:"):
                vmod.parse_strict_json('{"a": 1}\n')
        finally:
            json.loads = orig_loads

    def test_lean_strip_and_axioms(self):
        self.assertNotIn("sorry", vmod.strip_lean_comments_and_strings("-- sorry\ntheorem x := 1\n"))
        self.assertNotIn("sorry", vmod.strip_lean_comments_and_strings('def s := "sorry"\n'))
        self.assertNotIn("sorry", vmod.strip_lean_comments_and_strings("/- outer /- sorry -/ tail -/\ntheorem x := 1\n"))
        with self.assertRaisesRegex(ERR, "^UNTERMINATED_BLOCK_COMMENT:"):
            vmod.strip_lean_comments_and_strings("/- abc")
        with self.assertRaisesRegex(ERR, "^UNTERMINATED_STRING_LITERAL:"):
            vmod.strip_lean_comments_and_strings('"abc')
        good = good_runner(Path("x"))["axiom_stdout"].splitlines()
        counts = vmod.validate_axiom_lines(good, 9)
        self.assertEqual(counts["zero_axiom"], 2)
        self.assertEqual(counts["listed"], 7)
        with self.assertRaisesRegex(ERR, "^AXIOM_LINE_COUNT:"):
            vmod.validate_axiom_lines([], 9)
        for code, line in [("AXIOM_LINE_FORMAT", "garbage"), ("AXIOM_LBRACKET", "x depends on axioms: propext]"), ("AXIOM_RBRACKET", "x depends on axioms: [propext"), ("FORBIDDEN_AXIOM", "x depends on axioms: [Classical.choice]")]:
            with self.assertRaisesRegex(ERR, "^" + code + ":"):
                vmod.validate_axiom_lines([line] * 9, 9)

    def test_lean_package_fake(self):
        info = vmod.verify_lean_package(BASE, lean_runner=good_runner)
        self.assertEqual(info["public_theorems"], 9)
        self.assertEqual(info["lean_files"], 3)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ERR, "^MISSING_LEAN_DIR:"):
                vmod.verify_lean_package(Path(tmp))
            link_root = Path(tmp) / "linked"
            link_root.mkdir()
            (link_root / "lean").symlink_to(BASE / "lean", target_is_directory=True)
            with self.assertRaisesRegex(ERR, "^MISSING_LEAN_DIR:"):
                vmod.verify_lean_package(link_root)
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
            p = root / "lean" / "ReciprocityGate" / "Basic.lean"
            p.write_text(p.read_text(encoding="utf-8") + "theorem bad : True := sorry\n", encoding="utf-8")
        variants.append(("LEAN_ESCAPE", escape))
        def eval_escape(root):
            p = root / "lean" / "ReciprocityGate" / "Basic.lean"
            p.write_text(p.read_text(encoding="utf-8") + "#eval 1\n", encoding="utf-8")
        variants.append(("LEAN_ESCAPE", eval_escape))
        def elab_escape(root):
            p = root / "lean" / "ReciprocityGate" / "Basic.lean"
            p.write_text(p.read_text(encoding="utf-8") + "elab_rules : term => pure ()\n", encoding="utf-8")
        variants.append(("LEAN_ESCAPE", elab_escape))
        def bad_import(root):
            p = root / "lean" / "ReciprocityGate" / "Basic.lean"
            p.write_text("import Mathlib\n" + p.read_text(encoding="utf-8"), encoding="utf-8")
        variants.append(("BAD_IMPORT", bad_import))
        def thm_count(root):
            p = root / "lean" / "ReciprocityGate" / "Basic.lean"
            p.write_text(p.read_text(encoding="utf-8").replace("theorem correlated_verifier_false_accept_bound", "theoremX correlated_verifier_false_accept_bound", 1), encoding="utf-8")
        variants.append(("THM_COUNT", thm_count))
        def audit_count(root):
            p = root / "lean" / "AxiomAudit.lean"
            lines = p.read_text(encoding="utf-8").splitlines(True)
            p.write_text("".join(lines[:-1]), encoding="utf-8")
        variants.append(("AUDIT_COUNT", audit_count))
        def audit_set(root):
            p = root / "lean" / "AxiomAudit.lean"
            p.write_text(p.read_text(encoding="utf-8").replace("correlated_verifier_false_accept_bound", "nope_name", 1), encoding="utf-8")
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
        self.assertEqual(payload["correlated"]["partial"]["joint"], "3/50")
        self.assertEqual(payload["benchmark"]["auroc"], "1/1")
        self.assertEqual(payload["graph"]["honest"]["edges"], 5)
        src = (BASE / "verify_s160_q42c_reciprocity_gate.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        self.assertEqual(sum(1 for n in ast.walk(tree) if isinstance(n, ast.BoolOp)), 0)
        self.assertEqual(sum(1 for n in ast.walk(tree) if isinstance(n, ast.Assert)), 0)
        floats = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, float)]
        self.assertEqual(floats, [])
        self.assertNotIn("/home/", src)
        self.assertNotIn("float(", src)
        self.assertIn("random.Random(seed)", src)
        self.assertNotIn("random.random", src)
        self.assertNotIn("random.shuffle", src)
        cert = vmod.read_strict_json(BASE / "s160_q42c_reciprocity_certificate.json")
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
        run = subprocess.run([sys.executable, "-I", "-B", "verify_s160_q42c_reciprocity_gate.py", "--check", "--json"], cwd=str(BASE), env=env, capture_output=True, text=True, timeout=120, check=False)
        self.assertEqual(run.returncode, 0)
        self.assertNotIn("Traceback", run.stderr)
        parsed = json.loads(run.stdout)
        self.assertEqual(parsed["queue_id"], "EXP-Q42c")
        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "cert.json"
            data = json.loads((BASE / "s160_q42c_reciprocity_certificate.json").read_text(encoding="utf-8"))
            data["benchmark"]["wins"] = 399
            tampered.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            bad = subprocess.run([sys.executable, "-I", "-B", "verify_s160_q42c_reciprocity_gate.py", "--check", str(tampered), "--json"], cwd=str(BASE), env=env, capture_output=True, text=True, timeout=120, check=False)
            self.assertEqual(bad.returncode, 2)
            self.assertIn("CERT_MISMATCH", bad.stderr)
            self.assertNotIn("Traceback", bad.stderr)
            big = Path(tmp) / "big.json"
            big.write_text('{"a": ' + "9" * 400 + "}\n", encoding="utf-8")
            env2 = dict(env)
            env2["PYTHONINTMAXSTRDIGITS"] = "0"
            bigrun = subprocess.run([sys.executable, "-I", "-B", "verify_s160_q42c_reciprocity_gate.py", "--check", str(big), "--json"], cwd=str(BASE), env=env2, capture_output=True, text=True, timeout=120, check=False)
            self.assertEqual(bigrun.returncode, 2)
            self.assertIn("INT_DIGITS", bigrun.stderr)
            self.assertNotIn("Traceback", bigrun.stderr)


if __name__ == "__main__":
    unittest.main()
