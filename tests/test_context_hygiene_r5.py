#!/usr/bin/env python3
"""
R1-R5 tests for `aletheia.context_hygiene` (CS-26 context lifecycle & cold-cache guard).

Covers exact Fraction dominance and crossover boundaries, CLEAN/WARNING/ALERT
detection, fail-closed file IO (symlink, ancestor symlink, FIFO, oversize,
bad UTF-8), strict exact JSON (floats, duplicate keys, oversized ints,
depth), bool-as-int traps, CLI exit codes 0/1/2, and scaffold embedding.

Zero external dependencies. No bare assert statements. R4 parity modes:
  python3 -I -B tests/test_context_hygiene_r5.py
  python3 -I -O -B tests/test_context_hygiene_r5.py
  python3 -I -B -W error tests/test_context_hygiene_r5.py
"""
from __future__ import annotations

import ast
import enum
from fractions import Fraction
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stderr, redirect_stdout

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia import cli, context_hygiene as ch
from aletheia.scaffold import init_workspace
from aletheia.strict_io import AletheiaError, parse_strict_json_text, write_lf_text


class _Color(enum.IntEnum):
    ONE = 1


class _SubInt(int):
    pass


class _SubFrac(Fraction):
    pass


def _run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.main(argv)
    return rc, out.getvalue(), err.getvalue()


def _worker(wid="w1", ctx=100, idle=0, comp=0):
    return {"id": wid, "context_tokens": ctx, "idle_seconds": idle, "compactions": comp}


def _write_workers(root, payload, name="workers.json"):
    p = root / name
    write_lf_text(p, json.dumps(payload) + "\n")
    return p


def _write_board(root, rows, name="board.jsonl"):
    p = root / name
    write_lf_text(p, "\n".join(rows) + "\n")
    return p


class TestPolicyExactQ(unittest.TestCase):
    def test_01_respawn_dominance_and_exact_costs(self):
        res = ch.evaluate_reactivation_policy(
            context_tokens=200000, idle_seconds=3600, cache_ttl_seconds=300,
            fresh_context_tokens=2000, system_tokens=2000, summary_tokens=4000,
            c_miss=Fraction(3, 1), c_hit=Fraction(1, 10), c_out=Fraction(15, 1),
        )
        self.assertEqual(res["policy"], "RETIRE_AND_RESPAWN")
        self.assertEqual(res["is_cold"], True)
        self.assertEqual(res["cold_cost"], "600000/1")
        self.assertEqual(res["warm_cost"], "20000/1")
        self.assertEqual(res["respawn_cost"], "6000/1")
        self.assertEqual(res["compact_cost"], "98000/1")
        self.assertEqual(res["compact_savings"], "502000/1")
        self.assertEqual(res["crossover_tokens"], "780000/29")
        self.assertEqual(res["respawn_savings"], "594000/1")
        self.assertEqual(res["chosen_savings"], "594000/1")
        self.assertEqual(res["schema"], "aletheia.context_hygiene.policy.v1")

    def test_02_crossover_exact_fraction(self):
        res = ch.evaluate_reactivation_policy(
            context_tokens=1000, idle_seconds=999, cache_ttl_seconds=300,
            fresh_context_tokens=2000, system_tokens=100, summary_tokens=10,
            c_miss=Fraction(3, 1), c_hit=Fraction(0, 1), c_out=Fraction(7, 1),
        )
        self.assertEqual(res["crossover_tokens"], "400/3")
        self.assertEqual(res["compact_cost"], "400/1")
        self.assertEqual(res["policy"], "PRE_IDLE_COMPACT")

    def test_03_crossover_boundary_equal_then_above(self):
        base = dict(cache_ttl_seconds=300, idle_seconds=3600, fresh_context_tokens=999999,
                    system_tokens=2900, summary_tokens=2900,
                    c_miss=Fraction(3, 1), c_hit=Fraction(1, 10), c_out=Fraction(15, 1))
        at = ch.evaluate_reactivation_policy(context_tokens=21000, **base)
        self.assertEqual(at["crossover_tokens"], "21000/1")
        self.assertEqual(at["compact_cost"], "63000/1")
        self.assertEqual(at["cold_cost"], "63000/1")
        self.assertEqual(at["compact_cost"], at["cold_cost"])
        self.assertEqual(at["policy"], "KEEP_WARM")
        below = ch.evaluate_reactivation_policy(context_tokens=20999, **base)
        self.assertEqual(below["policy"], "KEEP_WARM")
        above = ch.evaluate_reactivation_policy(context_tokens=21001, **base)
        self.assertEqual(above["policy"], "PRE_IDLE_COMPACT")
        self.assertEqual(above["chosen_savings"], "29/10")
        for miss, hit in ((Fraction(1, 1), Fraction(1, 1)), (Fraction(1, 1), Fraction(2, 1))):
            nodegen = ch.evaluate_reactivation_policy(
                context_tokens=200000, idle_seconds=3600, cache_ttl_seconds=300,
                fresh_context_tokens=999999, system_tokens=100, summary_tokens=100,
                c_miss=miss, c_hit=hit, c_out=Fraction(1, 1),
            )
            self.assertIsNone(nodegen["crossover_tokens"])
            self.assertNotEqual(nodegen["policy"], "PRE_IDLE_COMPACT")
            self.assertEqual(nodegen["policy"], "KEEP_WARM")

    def test_04_respawn_boundary_L0_equal_L(self):
        kw = dict(idle_seconds=3600, cache_ttl_seconds=300, system_tokens=1000, summary_tokens=0,
                  c_miss=Fraction(2, 1), c_hit=Fraction(1, 1), c_out=Fraction(1, 1))
        eq = ch.evaluate_reactivation_policy(context_tokens=1000, fresh_context_tokens=1000, **kw)
        self.assertEqual(eq["respawn_cost"], eq["cold_cost"])
        self.assertEqual(eq["policy"], "KEEP_WARM")
        lt = ch.evaluate_reactivation_policy(context_tokens=1000, fresh_context_tokens=999, **kw)
        self.assertEqual(lt["policy"], "RETIRE_AND_RESPAWN")
        gt = ch.evaluate_reactivation_policy(context_tokens=1000, fresh_context_tokens=1001, **kw)
        self.assertEqual(gt["policy"], "KEEP_WARM")

    def test_05_tie_respawn_compact_prefers_respawn(self):
        res = ch.evaluate_reactivation_policy(
            context_tokens=10000, idle_seconds=3600, cache_ttl_seconds=300,
            fresh_context_tokens=1000, system_tokens=400, summary_tokens=100,
            c_miss=Fraction(1, 1), c_hit=Fraction(1, 20), c_out=Fraction(0, 1),
        )
        self.assertEqual(res["respawn_cost"], "1000/1")
        self.assertEqual(res["compact_cost"], "1000/1")
        self.assertEqual(res["cold_cost"], "10000/1")
        self.assertEqual(res["policy"], "RETIRE_AND_RESPAWN")

    def test_06_compact_beats_respawn_when_strictly_cheaper(self):
        res = ch.evaluate_reactivation_policy(
            context_tokens=10000, idle_seconds=3600, fresh_context_tokens=9000,
            system_tokens=100, summary_tokens=100,
            c_miss=Fraction(1, 1), c_hit=Fraction(1, 10), c_out=Fraction(1, 1),
        )
        self.assertEqual(res["compact_cost"], "1300/1")
        self.assertEqual(res["respawn_cost"], "9000/1")
        self.assertEqual(res["cold_cost"], "10000/1")
        self.assertEqual(res["policy"], "PRE_IDLE_COMPACT")
        self.assertEqual(res["chosen_cost"], "1300/1")

    def test_07_warm_boundary_idle_vs_ttl(self):
        warm = ch.evaluate_reactivation_policy(context_tokens=999999, idle_seconds=299, cache_ttl_seconds=300)
        self.assertEqual(warm["is_cold"], False)
        self.assertEqual(warm["policy"], "KEEP_WARM")
        cold = ch.evaluate_reactivation_policy(context_tokens=999999, idle_seconds=300, cache_ttl_seconds=300)
        self.assertEqual(cold["is_cold"], True)
        self.assertEqual(cold["policy"], "RETIRE_AND_RESPAWN")
        ttl0 = ch.evaluate_reactivation_policy(context_tokens=10, idle_seconds=0, cache_ttl_seconds=0)
        self.assertEqual(ttl0["is_cold"], True)

    def test_08_int_costs_and_zero_boundaries_pass(self):
        res = ch.evaluate_reactivation_policy(
            context_tokens=0, idle_seconds=0, cache_ttl_seconds=0, fresh_context_tokens=0,
            system_tokens=0, summary_tokens=0, c_miss=2, c_hit=0, c_out=0,
        )
        self.assertEqual(res["c_miss"], "2/1")
        self.assertEqual(res["c_hit"], "0/1")
        self.assertEqual(res["cold_cost"], "0/1")
        self.assertEqual(res["policy"], "KEEP_WARM")

    def test_09_invalid_int_inputs_rejected(self):
        for bad in (True, False, "10", 1.5, None, _SubInt(3), _Color.ONE, [1]):
            with self.assertRaises(AletheiaError) as cm:
                ch.evaluate_reactivation_policy(context_tokens=bad, idle_seconds=0)
            self.assertEqual(cm.exception.code, "CONTEXT_HYGIENE_INVALID_INT")
            with self.assertRaises(AletheiaError) as cm2:
                ch.evaluate_reactivation_policy(context_tokens=10, idle_seconds=bad)
            self.assertEqual(cm2.exception.code, "CONTEXT_HYGIENE_INVALID_INT")
        for field in ("cache_ttl_seconds", "fresh_context_tokens", "system_tokens", "summary_tokens"):
            kw = {"context_tokens": 10, "idle_seconds": 0, field: True}
            with self.assertRaises(AletheiaError) as cm3:
                ch.evaluate_reactivation_policy(**kw)
            self.assertEqual(cm3.exception.code, "CONTEXT_HYGIENE_INVALID_INT")
        for bad in (-1, -100):
            with self.assertRaises(AletheiaError) as cm4:
                ch.evaluate_reactivation_policy(context_tokens=bad, idle_seconds=0)
            self.assertEqual(cm4.exception.code, "CONTEXT_HYGIENE_INVALID_INT")

    def test_10_invalid_costs_rejected(self):
        for bad in ("x", 1.5, True, None, _SubFrac(1, 2), _SubInt(2)):
            with self.assertRaises(AletheiaError) as cm:
                ch.evaluate_reactivation_policy(context_tokens=10, idle_seconds=0, c_miss=bad)
            self.assertEqual(cm.exception.code, "CONTEXT_HYGIENE_INVALID_COST")
        for zero in (0, Fraction(0, 1), Fraction(-1, 2)):
            with self.assertRaises(AletheiaError) as cm2:
                ch.evaluate_reactivation_policy(context_tokens=10, idle_seconds=0, c_miss=zero)
            self.assertEqual(cm2.exception.code, "CONTEXT_HYGIENE_INVALID_COST")
        for field in ("c_hit", "c_out"):
            with self.assertRaises(AletheiaError) as cm3:
                ch.evaluate_reactivation_policy(context_tokens=10, idle_seconds=0, **{field: Fraction(-1, 3)})
            self.assertEqual(cm3.exception.code, "CONTEXT_HYGIENE_INVALID_COST")
            ok = ch.evaluate_reactivation_policy(context_tokens=10, idle_seconds=0, **{field: Fraction(0, 1)})
            self.assertEqual(ok[field], "0/1")


class TestAuditStatuses(unittest.TestCase):
    def test_11_empty_and_clean_audit(self):
        res = ch.audit_context_hygiene()
        self.assertEqual(res["schema"], "aletheia.context_hygiene.v1")
        self.assertEqual(res["status"], "CLEAN")
        self.assertEqual(res["board"], {"messages": 0, "oversize_messages": 0, "oversize_ratio": "0/1"})
        self.assertEqual(res["workers"]["bloated_ratio"], "0/1")
        self.assertEqual(res["findings"], [])
        with tempfile.TemporaryDirectory(prefix="ctx_clean_") as td:
            root = Path(td)
            board = _write_board(root, [json.dumps({"seq": 1, "agent": "w", "text": "done: x"})])
            workers = _write_workers(root, {"workers": [_worker()]})
            clean = ch.audit_context_hygiene(board_path=board, workers_path=workers)
            self.assertEqual(clean["status"], "CLEAN")
            self.assertEqual(clean["board"]["messages"], 1)
            self.assertEqual(clean["workers"]["count"], 1)
            self.assertEqual(clean["workers"]["total_context_tokens"], 100)
            self.assertEqual(clean["workers"]["max_context_tokens"], 100)

    def test_12_board_line_and_char_boundaries(self):
        with tempfile.TemporaryDirectory(prefix="ctx_board_") as td:
            root = Path(td)
            at_limit = _write_board(root, [json.dumps({"text": "a\nb"})], "at.jsonl")
            res = ch.audit_context_hygiene(board_path=at_limit, max_board_lines=2, max_board_chars=3)
            self.assertEqual(res["status"], "CLEAN")
            over_lines = _write_board(root, [json.dumps({"text": "a\nb\nc"})], "ol.jsonl")
            res2 = ch.audit_context_hygiene(board_path=over_lines, max_board_lines=2, max_board_chars=2000)
            self.assertEqual(res2["status"], "WARNING")
            self.assertEqual([f["kind"] for f in res2["findings"]], ["BOARD_MESSAGE_TOO_MANY_LINES"])
            self.assertEqual(res2["board"]["oversize_ratio"], "1/1")
            over_chars = _write_board(root, [json.dumps({"text": "abcd"})], "oc.jsonl")
            res3 = ch.audit_context_hygiene(board_path=over_chars, max_board_lines=12, max_board_chars=3)
            self.assertEqual([f["kind"] for f in res3["findings"]], ["BOARD_MESSAGE_TOO_LONG"])
            exact_chars = _write_board(root, [json.dumps({"text": "abc"})], "ec.jsonl")
            self.assertEqual(ch.audit_context_hygiene(board_path=exact_chars, max_board_chars=3)["status"], "CLEAN")
            raw = _write_board(root, [json.dumps({"payload": "x" * 40})], "raw.jsonl")
            res4 = ch.audit_context_hygiene(board_path=raw, max_board_chars=10)
            self.assertEqual(res4["status"], "WARNING")

    def test_13_worker_cold_warm_churn_boundaries(self):
        with tempfile.TemporaryDirectory(prefix="ctx_workers_") as td:
            root = Path(td)
            at_cold = _write_workers(root, {"workers": [_worker(ctx=150000, idle=9999)]}, "a.json")
            self.assertEqual(ch.audit_context_hygiene(workers_path=at_cold)["status"], "CLEAN")
            warm = _write_workers(root, {"workers": [_worker(ctx=150001, idle=299)]}, "w.json")
            resw = ch.audit_context_hygiene(workers_path=warm)
            self.assertEqual(resw["status"], "WARNING")
            self.assertEqual([f["kind"] for f in resw["findings"]], ["CONTEXT_BLOAT"])
            cold = _write_workers(root, {"workers": [_worker(ctx=150001, idle=300)]}, "c.json")
            resc = ch.audit_context_hygiene(workers_path=cold)
            self.assertEqual(resc["status"], "ALERT")
            self.assertEqual([f["kind"] for f in resc["findings"]], ["COLD_CACHE_REACTIVATION_RISK"])
            self.assertEqual(resc["workers"]["cold_risk_ratio"], "1/1")
            churn_at = _write_workers(root, {"workers": [_worker(comp=5)]}, "ca.json")
            self.assertEqual(ch.audit_context_hygiene(workers_path=churn_at)["status"], "CLEAN")
            churn = _write_workers(root, {"workers": [_worker(comp=6)]}, "ch.json")
            resch = ch.audit_context_hygiene(workers_path=churn)
            self.assertEqual(resch["status"], "WARNING")
            self.assertEqual([f["kind"] for f in resch["findings"]], ["COMPACTION_CHURN"])

    def test_14_alert_precedence_and_exact_ratios(self):
        with tempfile.TemporaryDirectory(prefix="ctx_mix_") as td:
            root = Path(td)
            board = _write_board(root, [json.dumps({"text": "x" * 50})])
            workers = _write_workers(root, {"workers": [
                _worker("cold", ctx=200000, idle=1000), _worker("ok", ctx=10),
            ]})
            res = ch.audit_context_hygiene(board_path=board, workers_path=workers, max_board_chars=10)
            self.assertEqual(res["status"], "ALERT")
            self.assertEqual(res["workers"]["bloated_ratio"], "1/2")
            self.assertEqual(res["workers"]["total_context_tokens"], 200010)
            self.assertEqual(res["workers"]["max_context_tokens"], 200000)
            self.assertEqual(res["board"]["oversize_ratio"], "1/1")

    def test_15_threshold_validation(self):
        self.assertEqual(ch.audit_context_hygiene(max_board_lines=1, max_board_chars=1,
                                                  cold_context_tokens=0, cache_ttl_seconds=0,
                                                  max_compactions=0)["status"], "CLEAN")
        cases = [
            {"max_board_lines": 0}, {"max_board_lines": -1}, {"max_board_lines": True},
            {"max_board_chars": 0}, {"max_board_chars": "9"}, {"cold_context_tokens": -1},
            {"cold_context_tokens": 1.5}, {"cache_ttl_seconds": -1},
            {"cache_ttl_seconds": _SubInt(3)}, {"max_compactions": -1}, {"max_compactions": _Color.ONE},
        ]
        for kw in cases:
            with self.assertRaises(AletheiaError) as cm:
                ch.audit_context_hygiene(**kw)
            self.assertEqual(cm.exception.code, "CONTEXT_HYGIENE_INVALID_INT", str(kw))


class TestStrictJsonAndSchema(unittest.TestCase):
    def test_16_loads_strict_direct(self):
        self.assertEqual(ch._loads_strict_exact('{"a": 1}', "t"), {"a": 1})
        for bad, code in (("", "CONTEXT_HYGIENE_JSON_EMPTY"), ("   ", "CONTEXT_HYGIENE_JSON_EMPTY"),
                          ("{bad", "CONTEXT_HYGIENE_JSON_SYNTAX"),
                          ('{"a": 1.5}', "CONTEXT_HYGIENE_JSON_FLOAT"),
                          ('{"a": NaN}', "CONTEXT_HYGIENE_JSON_CONSTANT"),
                          ('{"a": Infinity}', "CONTEXT_HYGIENE_JSON_CONSTANT"),
                          ('{"a": -Infinity}', "CONTEXT_HYGIENE_JSON_CONSTANT"),
                          ('{"a": 1, "a": 2}', "CONTEXT_HYGIENE_JSON_DUPLICATE_KEY"),
                          ('{"a": "\\ud800"}', "CONTEXT_HYGIENE_JSON_LONE_SURROGATE")):
            with self.assertRaises(AletheiaError) as cm:
                ch._loads_strict_exact(bad, "t")
            self.assertEqual(cm.exception.code, code, bad)
        for bad_type in (b"{}", 123, None):
            with self.assertRaises(AletheiaError) as cm2:
                ch._loads_strict_exact(bad_type, "t")
            self.assertEqual(cm2.exception.code, "CONTEXT_HYGIENE_JSON_TYPE")

    def test_17_int_digit_limits(self):
        n1024 = "9" * 1024
        self.assertEqual(ch._loads_strict_exact('{"a": ' + n1024 + "}", "t")["a"], int(n1024))
        self.assertEqual(ch._loads_strict_exact('{"a": -' + n1024 + "}", "t")["a"], -int(n1024))
        for n in ("9" * 1025, "9" * 4400, "-" + "9" * 1025):
            with self.assertRaises(AletheiaError) as cm:
                ch._loads_strict_exact('{"a": ' + n + "}", "t")
            self.assertEqual(cm.exception.code, "CONTEXT_HYGIENE_JSON_INT_TOO_LONG")

    def test_18_depth_limits(self):
        ok = "[" * 64 + "1" + "]" * 64
        self.assertIsNotNone(ch._loads_strict_exact(ok, "t"))
        for deep in ("[" * 65 + "1" + "]" * 65, '{"a": ' * 65 + "1" + "}" * 65):
            with self.assertRaises(AletheiaError) as cm:
                ch._loads_strict_exact(deep, "t")
            self.assertEqual(cm.exception.code, "CONTEXT_HYGIENE_JSON_DEPTH")
        with self.assertRaises(AletheiaError) as cm2:
            ch._loads_strict_exact("[" * 5000 + "1" + "]" * 5000, "t")
        self.assertIn(cm2.exception.code, ("CONTEXT_HYGIENE_JSON_DEPTH", "CONTEXT_HYGIENE_JSON_SYNTAX"))

    def test_19_int_digit_limit_under_no_python_limit(self):
        snippet = (
            "import sys; sys.path.insert(0, " + repr(str(ROOT)) + ");"
            "from aletheia.context_hygiene import _loads_strict_exact;"
            "from aletheia.strict_io import AletheiaError;\n"
            "try:\n _loads_strict_exact('{\"a\": ' + '9'*4400 + '}', 't')\nexcept AletheiaError as e:\n print(e.code)\n"
        )
        env = dict(os.environ)
        env["PYTHONINTMAXSTRDIGITS"] = "0"
        proc = subprocess.run([sys.executable, "-B", "-c", snippet], capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "CONTEXT_HYGIENE_JSON_INT_TOO_LONG")

    def test_20_board_schema_rejections(self):
        with tempfile.TemporaryDirectory(prefix="ctx_bschema_") as td:
            root = Path(td)
            cases = [
                (["[1, 2, 3]"], "CONTEXT_HYGIENE_BOARD_NOT_OBJECT"),
                (["123"], "CONTEXT_HYGIENE_BOARD_NOT_OBJECT"),
                ([json.dumps({"text": 123})], "CONTEXT_HYGIENE_BOARD_TEXT_TYPE"),
                ([json.dumps({"text": True})], "CONTEXT_HYGIENE_BOARD_TEXT_TYPE"),
                ([json.dumps({"text": "ok"}), "", json.dumps({"text": "ok"})], "CONTEXT_HYGIENE_BOARD_BLANK_LINE"),
                (["   "], "CONTEXT_HYGIENE_BOARD_BLANK_LINE"),
                (["{bad"], "CONTEXT_HYGIENE_JSON_SYNTAX"),
                (['{"a": 1, "a": 2}'], "CONTEXT_HYGIENE_JSON_DUPLICATE_KEY"),
                (['{"a": 2.5}'], "CONTEXT_HYGIENE_JSON_FLOAT"),
            ]
            for i, (rows, code) in enumerate(cases):
                p = _write_board(root, rows, f"b{i}.jsonl")
                with self.assertRaises(AletheiaError) as cm:
                    ch.audit_context_hygiene(board_path=p)
                self.assertEqual(cm.exception.code, code, str(rows))

    def test_21_workers_schema_rejections(self):
        with tempfile.TemporaryDirectory(prefix="ctx_wschema_") as td:
            root = Path(td)
            raw_cases = [
                ("[1, 2]", "CONTEXT_HYGIENE_WORKERS_NOT_OBJECT"),
                ("123", "CONTEXT_HYGIENE_WORKERS_NOT_OBJECT"),
                ("{}", "CONTEXT_HYGIENE_MISSING_FIELD"),
                ('{"workers": {}}', "CONTEXT_HYGIENE_WORKERS_NOT_LIST"),
                ('{"workers": [1]}', "CONTEXT_HYGIENE_WORKER_NOT_OBJECT"),
                ('{"workers": [{"context_tokens": 1, "idle_seconds": 0, "compactions": 0}]}', "CONTEXT_HYGIENE_MISSING_FIELD"),
                ('{"workers": [{"id": 7, "context_tokens": 1, "idle_seconds": 0, "compactions": 0}]}', "CONTEXT_HYGIENE_WORKER_ID_TYPE"),
                ('{"workers": [{"id": "", "context_tokens": 1, "idle_seconds": 0, "compactions": 0}]}', "CONTEXT_HYGIENE_WORKER_ID_EMPTY"),
            ]
            for i, (raw, code) in enumerate(raw_cases):
                p = root / f"w{i}.json"
                write_lf_text(p, raw + "\n")
                with self.assertRaises(AletheiaError) as cm:
                    ch.audit_context_hygiene(workers_path=p)
                self.assertEqual(cm.exception.code, code, raw)
            for field in ("context_tokens", "idle_seconds", "compactions"):
                w = _worker()
                del w[field]
                p = _write_workers(root, {"workers": [w]}, f"miss_{field}.json")
                with self.assertRaises(AletheiaError) as cm2:
                    ch.audit_context_hygiene(workers_path=p)
                self.assertEqual(cm2.exception.code, "CONTEXT_HYGIENE_MISSING_FIELD")
            for field, bad in (("context_tokens", True), ("idle_seconds", -1), ("compactions", "2")):
                w = _worker()
                w[field] = bad
                p = _write_workers(root, {"workers": [w]}, f"bad_{field}.json")
                with self.assertRaises(AletheiaError) as cm3:
                    ch.audit_context_hygiene(workers_path=p)
                self.assertEqual(cm3.exception.code, "CONTEXT_HYGIENE_INVALID_INT")
            pfloat = root / "float.json"
            write_lf_text(pfloat, '{"workers": [{"id": "w", "context_tokens": 1.5, "idle_seconds": 0, "compactions": 0}]}\n')
            with self.assertRaises(AletheiaError) as cm4:
                ch.audit_context_hygiene(workers_path=pfloat)
            self.assertEqual(cm4.exception.code, "CONTEXT_HYGIENE_JSON_FLOAT")


class TestFailClosedIO(unittest.TestCase):
    def test_22_missing_and_invalid_paths(self):
        with tempfile.TemporaryDirectory(prefix="ctx_io_") as td:
            root = Path(td)
            with self.assertRaises(AletheiaError) as cm:
                ch.audit_context_hygiene(board_path=root / "nope.jsonl")
            self.assertEqual(cm.exception.code, "CONTEXT_HYGIENE_IO_ERROR")
            with self.assertRaises(AletheiaError) as cm2:
                ch.audit_context_hygiene(board_path=123)
            self.assertEqual(cm2.exception.code, "CONTEXT_HYGIENE_INVALID_PATH")
            with self.assertRaises(AletheiaError) as cm3:
                ch.audit_context_hygiene(board_path="")
            self.assertEqual(cm3.exception.code, "CONTEXT_HYGIENE_INVALID_PATH")
            with self.assertRaises(AletheiaError) as cm4:
                ch.audit_context_hygiene(board_path="/")
            self.assertEqual(cm4.exception.code, "CONTEXT_HYGIENE_INVALID_PATH")
            str_board = _write_board(root, [json.dumps({"text": "ok"})])
            self.assertEqual(ch.audit_context_hygiene(board_path=str(str_board))["status"], "CLEAN")
            self.assertEqual(ch.audit_context_hygiene(board_path=str_board)["status"], "CLEAN")

    def test_23_symlink_leaf_and_ancestor_refused(self):
        with tempfile.TemporaryDirectory(prefix="ctx_link_") as td:
            root = Path(td)
            real = _write_board(root, [json.dumps({"text": "ok"})])
            leaf = root / "leaf_link.jsonl"
            leaf.symlink_to(real)
            with self.assertRaises(AletheiaError) as cm:
                ch.audit_context_hygiene(board_path=leaf)
            self.assertEqual(cm.exception.code, "CONTEXT_HYGIENE_IO_ERROR")
            sub = root / "sub"
            sub.mkdir()
            inner = _write_board(sub, [json.dumps({"text": "ok"})], "inner.jsonl")
            dir_link = root / "dir_link"
            dir_link.symlink_to(sub, target_is_directory=True)
            with self.assertRaises(AletheiaError) as cm2:
                ch.audit_context_hygiene(board_path=dir_link / "inner.jsonl")
            self.assertEqual(cm2.exception.code, "CONTEXT_HYGIENE_IO_ERROR")
            self.assertEqual(ch.audit_context_hygiene(board_path=inner)["status"], "CLEAN")
            wreal = _write_workers(root, {"workers": []})
            wleaf = root / "w_link.json"
            wleaf.symlink_to(wreal)
            with self.assertRaises(AletheiaError) as cm3:
                ch.audit_context_hygiene(workers_path=wleaf)
            self.assertEqual(cm3.exception.code, "CONTEXT_HYGIENE_IO_ERROR")

    def test_24_fifo_and_directory_refused_without_blocking(self):
        with tempfile.TemporaryDirectory(prefix="ctx_fifo_") as td:
            root = Path(td)
            with self.assertRaises(AletheiaError) as cm:
                ch.audit_context_hygiene(board_path=root)
            self.assertEqual(cm.exception.code, "CONTEXT_HYGIENE_NOT_REGULAR_FILE")
            if hasattr(os, "mkfifo"):
                fifo = root / "board_fifo"
                os.mkfifo(fifo)
                with self.assertRaises(AletheiaError) as cm2:
                    ch.audit_context_hygiene(board_path=fifo)
                self.assertEqual(cm2.exception.code, "CONTEXT_HYGIENE_NOT_REGULAR_FILE")

    def test_25_size_cap_exact_boundary(self):
        with tempfile.TemporaryDirectory(prefix="ctx_big_") as td:
            big = Path(td) / "big.bin"
            big.write_bytes(b"x" * ch.MAX_FILE_BYTES)
            self.assertEqual(len(ch._read_file_bytes(big, "t")), ch.MAX_FILE_BYTES)
            with big.open("ab") as fh:
                fh.write(b"x")
            with self.assertRaises(AletheiaError) as cm:
                ch._read_file_bytes(big, "t")
            self.assertEqual(cm.exception.code, "CONTEXT_HYGIENE_FILE_TOO_LARGE")
            with self.assertRaises(AletheiaError) as cm2:
                ch.audit_context_hygiene(board_path=big)
            self.assertEqual(cm2.exception.code, "CONTEXT_HYGIENE_FILE_TOO_LARGE")

    def test_26_bad_utf8_and_crlf(self):
        with tempfile.TemporaryDirectory(prefix="ctx_utf8_") as td:
            root = Path(td)
            bad = root / "bad.jsonl"
            bad.write_bytes(b"\xff\xfe\n")
            with self.assertRaises(AletheiaError) as cm:
                ch.audit_context_hygiene(board_path=bad)
            self.assertEqual(cm.exception.code, "CONTEXT_HYGIENE_INVALID_UTF8")
            badw = root / "bad.json"
            badw.write_bytes(b"\xc3\x28")
            with self.assertRaises(AletheiaError) as cm2:
                ch.audit_context_hygiene(workers_path=badw)
            self.assertEqual(cm2.exception.code, "CONTEXT_HYGIENE_INVALID_UTF8")
            crlf = root / "crlf.jsonl"
            crlf.write_bytes(b'{"text": "ok"}\r\n')
            with self.assertRaises(AletheiaError) as cm3:
                ch.audit_context_hygiene(board_path=crlf)
            self.assertEqual(cm3.exception.code, "CONTEXT_HYGIENE_CRLF")


class TestDemoSelfTestCliScaffold(unittest.TestCase):
    def test_27_demo_and_self_test_deterministic(self):
        d1 = ch.run_context_hygiene_demo()
        self.assertEqual(d1, ch.run_context_hygiene_demo())
        self.assertEqual(d1["passed"], True)
        self.assertEqual(d1["examples"]["respawn"]["policy"], "RETIRE_AND_RESPAWN")
        self.assertEqual(d1["examples"]["compact"]["policy"], "PRE_IDLE_COMPACT")
        self.assertEqual(d1["examples"]["warm"]["policy"], "KEEP_WARM")
        s1 = ch.run_context_hygiene_self_test()
        self.assertEqual(s1, ch.run_context_hygiene_self_test())
        self.assertEqual(s1["passed"], True)
        self.assertEqual(s1["status"], "PASS")
        for name, val in s1["checks"].items():
            self.assertEqual(val, True, name)

    def test_28_cli_demo_selftest_and_clean(self):
        rc, out, err = _run_cli(["context-hygiene", "--self-test", "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(parse_strict_json_text(out, allow_float=False)["passed"], True)
        rc, out, err = _run_cli(["context-hygiene", "--demo", "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(parse_strict_json_text(out, allow_float=False)["passed"], True)
        rc, out, err = _run_cli(["context-hygiene", "--demo"])
        self.assertEqual(rc, 0)
        self.assertIn("status=OK", out)
        rc, out, err = _run_cli(["context-hygiene", "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(parse_strict_json_text(out, allow_float=False)["status"], "CLEAN")

    def test_29_cli_warning_alert_and_fail_on_warning(self):
        with tempfile.TemporaryDirectory(prefix="ctx_cli_") as td:
            root = Path(td)
            board = _write_board(root, [json.dumps({"text": "x" * 50})])
            rc, out, err = _run_cli(["context-hygiene", "--board", str(board), "--max-board-chars", "10", "--json"])
            self.assertEqual(rc, 0)
            self.assertEqual(parse_strict_json_text(out, allow_float=False)["status"], "WARNING")
            rc, out, err = _run_cli(["context-hygiene", "--board", str(board), "--max-board-chars", "10",
                                     "--fail-on-warning", "--json"])
            self.assertEqual(rc, 1)
            workers = _write_workers(root, {"workers": [_worker(ctx=200000, idle=1000)]})
            rc, out, err = _run_cli(["context-hygiene", "--workers", str(workers), "--json"])
            self.assertEqual(rc, 1)
            self.assertEqual(parse_strict_json_text(out, allow_float=False)["status"], "ALERT")
            rc, out, err = _run_cli(["context-hygiene", "--workers", str(workers),
                                     "--cold-context-tokens", "300000", "--json"])
            self.assertEqual(rc, 0)

    def test_30_cli_errors_rc2_no_traceback(self):
        rc, out, err = _run_cli(["context-hygiene", "--board", "/nonexistent_ctx.jsonl", "--json"])
        self.assertEqual(rc, 2)
        self.assertEqual(parse_strict_json_text(out, allow_float=False)["code"], "CONTEXT_HYGIENE_IO_ERROR")
        self.assertNotIn("Traceback", err)
        rc, out, err = _run_cli(["context-hygiene", "--board", "/nonexistent_ctx.jsonl"])
        self.assertEqual(rc, 2)
        self.assertIn("CONTEXT_HYGIENE_IO_ERROR", err)
        self.assertNotIn("Traceback", err)
        rc, out, err = _run_cli(["context-hygiene", "--max-board-lines", "0", "--json"])
        self.assertEqual(rc, 2)
        self.assertEqual(parse_strict_json_text(out, allow_float=False)["code"], "CONTEXT_HYGIENE_INVALID_INT")
        err_buf = io.StringIO()
        with redirect_stderr(err_buf):
            with self.assertRaises(SystemExit) as cm:
                cli.main(["context-hygiene", "--demo", "--self-test"])
        self.assertEqual(cm.exception.code, 2)

    def test_31_scaffold_embeds_cs26(self):
        with tempfile.TemporaryDirectory(prefix="ctx_scaffold_") as td:
            ws = Path(td) / "ws"
            init_workspace(ws, domain="math")
            protocol = (ws / "verification" / "PROTOCOL.md").read_text(encoding="utf-8")
            portals = (ws / "cartography" / "frontier_portals.md").read_text(encoding="utf-8")
            self.assertIn("CS-26", protocol)
            self.assertIn("context-hygiene", protocol)
            self.assertIn("CS-26", portals)

    def test_32_module_ast_purity(self):
        src = (ROOT / "aletheia" / "context_hygiene.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        self.assertEqual([n.lineno for n in ast.walk(tree) if isinstance(n, ast.Assert)], [])
        self.assertEqual([n.lineno for n in ast.walk(tree) if isinstance(n, ast.BoolOp)], [])
        self.assertEqual([n.lineno for n in ast.walk(tree) if isinstance(n, ast.Div)], [])
        self.assertEqual([n.value for n in ast.walk(tree)
                          if isinstance(n, ast.Constant) and type(n.value) is float], [])
        self.assertEqual([n.lineno for n in ast.walk(tree)
                          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "float"], [])

    def test_33_public_exports(self):
        import aletheia
        self.assertEqual(aletheia.evaluate_reactivation_policy, ch.evaluate_reactivation_policy)
        self.assertEqual(aletheia.audit_context_hygiene, ch.audit_context_hygiene)
        self.assertEqual(aletheia.run_context_hygiene_demo()["passed"], True)
        self.assertEqual(aletheia.run_context_hygiene_self_test()["passed"], True)

    def test_34_json_depth_recursion_surrogate_key_relative_path_and_dual_oversize(self):
        with mock.patch.object(ch.json, "loads", side_effect=RecursionError("depth")):
            with self.assertRaises(AletheiaError) as cm:
                ch._loads_strict_exact('{"a": [1, 2]}', "rec")
            self.assertEqual(cm.exception.code, "CONTEXT_HYGIENE_JSON_DEPTH")
        old_limit = sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(20)
            with self.assertRaises(AletheiaError) as cm2:
                ch._loads_strict_exact("[" * 100 + "1" + "]" * 100, "rec_lim")
            self.assertEqual(cm2.exception.code, "CONTEXT_HYGIENE_JSON_DEPTH")
        finally:
            sys.setrecursionlimit(old_limit)
        raw = '{"' + chr(0xD800) + '": 1}'
        with self.assertRaises(AletheiaError) as cm3:
            ch._loads_strict_exact(raw, "surr_key")
        self.assertEqual(cm3.exception.code, "CONTEXT_HYGIENE_JSON_LONE_SURROGATE")
        with tempfile.TemporaryDirectory(prefix="ctx_rel_") as td:
            root = Path(td)
            _write_board(root, [json.dumps({"text": "ok"})], "board_rel.jsonl")
            (root / "sym_rel.jsonl").symlink_to(root / "board_rel.jsonl")
            old_cwd = os.getcwd()
            try:
                os.chdir(root)
                self.assertEqual(ch.audit_context_hygiene(board_path="board_rel.jsonl")["status"], "CLEAN")
                with self.assertRaises(AletheiaError) as cm4:
                    ch.audit_context_hygiene(board_path="sym_rel.jsonl")
                self.assertIn(cm4.exception.code, ("CONTEXT_HYGIENE_SYMLINK_FORBIDDEN", "CONTEXT_HYGIENE_IO_ERROR"))
            finally:
                os.chdir(old_cwd)
            dual = _write_board(root, [json.dumps({"text": "a\nb\ncdefg"})], "dual.jsonl")
            res = ch.audit_context_hygiene(board_path=dual, max_board_lines=1, max_board_chars=3)
            self.assertEqual(sorted(f["kind"] for f in res["findings"]),
                             ["BOARD_MESSAGE_TOO_LONG", "BOARD_MESSAGE_TOO_MANY_LINES"])
            self.assertEqual(len(res["findings"]), 2)
            self.assertEqual(res["board"]["oversize_messages"], 1)


if __name__ == "__main__":
    unittest.main()
