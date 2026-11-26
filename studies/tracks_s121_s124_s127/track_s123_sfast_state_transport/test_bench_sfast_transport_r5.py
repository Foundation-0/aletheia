#!/usr/bin/env python3
"""Assertion-free R5 adversarial unittest suite for bench_sfast_cross_seed_transport.py (100% mutate, stdlib safe)."""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import bench_sfast_cross_seed_transport as mod


class TestBenchSfastTransportR5(unittest.TestCase):
    def test_01_stdlib_selftest_a5_order_and_rev_fixed_count(self) -> None:
        res = mod.run_stdlib_selftest()
        self.assertTrue(res["passed"])
        self.assertEqual(res["schema"], mod.SCHEMA_SELFTEST)
        self.assertEqual(res["a5_group_order"], 60)
        self.assertTrue(res["a5_non_abelian_verified"])
        self.assertEqual(res["a5_seed5005_rev_fixed_prefixes"], 64)
        self.assertEqual(res["seeds"], [42, 137, 2026])
        self.assertEqual(res["rank_sweep"], [4, 8, 16, 32])

        # CLI --selftest-stdlib --json AND default no-arg CLI
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(mod.main(["--selftest-stdlib", "--json"]), 0)
        parsed = json.loads(buf.getvalue())
        self.assertEqual(parsed["payload_sha256"], res["payload_sha256"])

        buf2 = io.StringIO()
        with redirect_stdout(buf2):
            self.assertEqual(mod.main([]), 0)
        self.assertIn("SELFTEST_PASS", buf2.getvalue())

    def test_02_exact_boundaries_and_must_fail_controls(self) -> None:
        # Exact minimum valid boundaries accepted
        d_edge = mod.build_assoc_recall_dataset(1, seed=42, n_keys=4, n_vals=4, t_doc=4)
        self.assertEqual(len(d_edge), 1)
        self.assertEqual(len(d_edge[0][0]), 4)
        # Exact t_doc - 2 == n_keys boundary accepted
        d_cap = mod.build_assoc_recall_dataset(1, seed=42, n_keys=4, n_vals=4, t_doc=6)
        self.assertEqual(len(d_cap[0][0]), 6)

        d1 = mod.build_assoc_recall_dataset(10, seed=42)
        d2 = mod.build_assoc_recall_dataset(10, seed=42)
        self.assertEqual(d1, d2)
        for seq, q_k, target_v in d1:
            seen_vals: dict[int, list[int]] = {}
            for k, v in seq:
                seen_vals.setdefault(k, []).append(v)
            self.assertEqual(seen_vals[q_k][-1], target_v)
            self.assertTrue(any(len(vs) >= 2 and vs[-1] != vs[0] for vs in seen_vals.values()))

        # Exact A_5 word & reversal-prefix boundaries accepted
        w_edge, y_edge = mod.build_a5_word_dataset(1, seed=99, word_len=4)
        self.assertEqual(len(w_edge), 1)
        self.assertEqual(len(y_edge), 1)
        self.assertEqual(mod.count_a5_reversal_fixed_prefixes([[0]], 1), 1)
        self.assertEqual(mod.count_a5_reversal_fixed_prefixes([[0, 1]], 2), 0)

        # Every single guard must-fail control!
        for code, fn in (
            ("BAD_N_SAMPLES", lambda: mod.build_assoc_recall_dataset(0, seed=1)),
            ("BAD_N_KEYS", lambda: mod.build_assoc_recall_dataset(1, seed=1, n_keys=3, n_vals=4, t_doc=4)),
            ("BAD_N_VALS", lambda: mod.build_assoc_recall_dataset(1, seed=1, n_keys=4, n_vals=3, t_doc=4)),
            ("BAD_T_DOC", lambda: mod.build_assoc_recall_dataset(1, seed=1, n_keys=4, n_vals=4, t_doc=3)),
            ("BAD_KEY_CAP", lambda: mod.build_assoc_recall_dataset(1, seed=1, n_keys=4, n_vals=4, t_doc=7)),
            ("BAD_A5_N", lambda: mod.build_a5_word_dataset(0, seed=1, word_len=4)),
            ("BAD_A5_LEN", lambda: mod.build_a5_word_dataset(1, seed=1, word_len=3)),
            ("BAD_HALF", lambda: mod.count_a5_reversal_fixed_prefixes([[0, 1]], 0)),
            ("WORD_TOO_SHORT", lambda: mod.count_a5_reversal_fixed_prefixes([[0]], 2)),
        ):
            with self.assertRaises(mod.BenchTransportError) as cm:
                fn()
            self.assertEqual(cm.exception.code, code)

        # Also exercise main() exception handler (exit 2) cleanly via monkeypatch!
        orig = mod.run_stdlib_selftest
        def _boom() -> dict[str, object]:
            raise mod.BenchTransportError("FORCED_ERR", "test")
        mod.run_stdlib_selftest = _boom  # type: ignore[assignment]
        try:
            eb = io.StringIO()
            with redirect_stderr(eb):
                self.assertEqual(mod.main([]), 2)
            self.assertIn("FORCED_ERR", eb.getvalue())
        finally:
            mod.run_stdlib_selftest = orig  # type: ignore[assignment]


if __name__ == "__main__":
    unittest.main(verbosity=2)
