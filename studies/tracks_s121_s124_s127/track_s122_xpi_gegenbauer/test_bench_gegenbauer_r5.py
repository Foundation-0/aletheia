#!/usr/bin/env python3
"""R5 Unit & 100%-Mutation-Kill Suite for `bench_gegenbauer_vs_monomial_attn.py`.

Runs pure-stdlib grading, basis-matrix, CLI, and tamper-refusal tests unconditionally under
`/usr/bin/python3 -I -B`, plus end-to-end `--smoke` PyTorch verification when `torch` is installed.
"""

from __future__ import annotations

import contextlib
import copy
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from typing import Any, Callable

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import bench_gegenbauer_vs_monomial_attn as bench  # noqa: E402


def _resign(payload: dict[str, Any]) -> dict[str, Any]:
    body = {k: v for k, v in payload.items() if k not in ("result_sha256", "elapsed_seconds")}
    out = copy.deepcopy(payload)
    out["result_sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return out


class TestBenchGegenbauerR5(unittest.TestCase):
    def _expect_code(self, fn: Callable[[], Any], code: str) -> None:
        with self.assertRaises(bench.S122BenchError) as ctx:
            fn()
        self.assertEqual(ctx.exception.code, code)

    def test_01_basis_matrix_and_pure_law4_grading_boundaries(self) -> None:
        self._expect_code(lambda: bench.build_gegenbauer_basis_matrix_float(Fraction(-1, 2)), "BAD_ALPHA")
        self._expect_code(lambda: bench.build_gegenbauer_basis_matrix_float(0.5), "BAD_ALPHA")  # type: ignore[arg-type]
        m0 = bench.build_gegenbauer_basis_matrix_float(Fraction(0))
        self.assertEqual(len(m0), 9)
        self.assertEqual(m0[1][1], 1.0)
        self.assertEqual(m0[8][8], 128.0)

        base_kw = dict(
            nan_runs_xpi=0,
            reg_xpi_wins_vs_softmax=3,
            reg_xpi_wins_vs_t8_init=3,
            reg_xpi_mean_mse=0.011,
            reg_linear_mean_mse=0.014,
            high_g_xpi_mean_mse=0.075,
            high_g_mono_mean_mse=0.150,
            high_g_xpi_max_b8=0.100,
            high_g_mono_max_b8=0.001,
            lkp4_xpi_mean_acc=98.5,
            lkp4_mono_mean_acc=99.0,
            lkp4_linear_mean_acc=62.0,
            lkp4_softmax_mean_acc=100.0,
            lkp8_xpi_mean_acc=98.5,
            lkp8_softmax_mean_acc=100.0,
            n_seeds=3,
        )
        self._expect_code(lambda: bench.grade_s122_empirical(**{**base_kw, "n_seeds": 0}), "BAD_N_SEEDS")
        self._expect_code(lambda: bench.grade_s122_empirical(**{**base_kw, "n_seeds": True}), "BAD_N_SEEDS")
        self._expect_code(lambda: bench.grade_s122_empirical(**{**base_kw, "n_seeds": "3"}), "BAD_N_SEEDS")  # type: ignore[arg-type]
        self._expect_code(lambda: bench.grade_s122_empirical(**{**base_kw, "nan_runs_xpi": -1}), "BAD_NAN_COUNT")
        self._expect_code(lambda: bench.grade_s122_empirical(**{**base_kw, "nan_runs_xpi": True}), "BAD_NAN_COUNT")
        self._expect_code(lambda: bench.grade_s122_empirical(**{**base_kw, "nan_runs_xpi": "0"}), "BAD_NAN_COUNT")  # type: ignore[arg-type]

        # Exact n_seeds == 1 and nan_runs_xpi == 0 boundary
        g_seed1 = bench.grade_s122_empirical(**{**base_kw, "n_seeds": 1, "reg_xpi_wins_vs_softmax": 1, "reg_xpi_wins_vs_t8_init": 1})
        self.assertEqual(g_seed1["verdict"], "CONFIRMED")

        # CONFIRMED outcome
        self.assertEqual(bench.grade_s122_empirical(**base_kw)["verdict"], "CONFIRMED")

        # PARTIAL outcome (8x8 CPU sequence budget stays in <75% saddle while G1, G2a, G2b, G3 pass)
        self.assertEqual(
            bench.grade_s122_empirical(**{**base_kw, "lkp8_xpi_mean_acc": 51.0, "lkp8_softmax_mean_acc": 50.0})["verdict"],
            "PARTIAL",
        )

        # FALSIFIED outcomes
        self.assertEqual(bench.grade_s122_empirical(**{**base_kw, "nan_runs_xpi": 1})["verdict"], "FALSIFIED")
        self.assertEqual(bench.grade_s122_empirical(**{**base_kw, "high_g_xpi_mean_mse": 0.20})["verdict"], "FALSIFIED")
        self.assertEqual(bench.grade_s122_empirical(**{**base_kw, "lkp4_xpi_mean_acc": 70.0})["verdict"], "FALSIFIED")

    def test_02_payload_validator_and_cli_guards(self) -> None:
        valid = _resign(
            {
                "track": "S122",
                "cs08_param_counts": {"fixed_linear_and_softmax": 27079, "polynomial_p8_all_arms": 27198},
                "graded": {"verdict": "PARTIAL"},
            }
        )
        bench.validate_results_payload(valid)

        self._expect_code(lambda: bench.validate_results_payload("bad"), "BAD_PAYLOAD_ROOT")  # type: ignore[arg-type]
        bad_tr = copy.deepcopy(valid)
        bad_tr["track"] = "S999"
        self._expect_code(lambda: bench.validate_results_payload(_resign(bad_tr)), "BAD_PAYLOAD_ROOT")

        bad_miss = copy.deepcopy(valid)
        bad_miss["result_sha256"] = "short"
        self._expect_code(lambda: bench.validate_results_payload(bad_miss), "MISSING_RESULT_SHA")
        bad_none = copy.deepcopy(valid)
        bad_none["result_sha256"] = None
        self._expect_code(lambda: bench.validate_results_payload(bad_none), "MISSING_RESULT_SHA")

        bad_sha = copy.deepcopy(valid)
        bad_sha["result_sha256"] = "0" * 64
        self._expect_code(lambda: bench.validate_results_payload(bad_sha), "RESULT_SHA_MISMATCH")

        bad_pc_none = copy.deepcopy(valid)
        bad_pc_none["cs08_param_counts"] = None
        self._expect_code(lambda: bench.validate_results_payload(_resign(bad_pc_none)), "CS08_PARAM_MISMATCH")

        bad_p1 = copy.deepcopy(valid)
        bad_p1["cs08_param_counts"]["fixed_linear_and_softmax"] = 100
        self._expect_code(lambda: bench.validate_results_payload(_resign(bad_p1)), "CS08_PARAM_MISMATCH")

        bad_p2 = copy.deepcopy(valid)
        bad_p2["cs08_param_counts"]["polynomial_p8_all_arms"] = 100
        self._expect_code(lambda: bench.validate_results_payload(_resign(bad_p2)), "CS08_PARAM_MISMATCH")

        buf_err = io.StringIO()
        with contextlib.redirect_stderr(buf_err):
            self.assertEqual(bench.main(["--write", "--check"]), 2)

        # Missing results file check via temporary _HERE override
        with tempfile.TemporaryDirectory() as td:
            orig_here = bench._HERE
            try:
                bench._HERE = Path(td)
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(bench.main(["--check"]), 2)
            finally:
                bench._HERE = orig_here

        if (_HERE / bench.RESULTS_FILENAME).is_file():
            buf_out = io.StringIO()
            with contextlib.redirect_stdout(buf_out):
                self.assertEqual(bench.main(["--check"]), 0)
                self.assertIn('"status": "PASS"', buf_out.getvalue())

        orig_has_torch = bench._HAS_TORCH
        try:
            bench._HAS_TORCH = False
            self._expect_code(lambda: bench.run_benchmark(smoke=True), "TORCH_MISSING")
        finally:
            bench._HAS_TORCH = orig_has_torch

    @unittest.skipUnless(bench._HAS_TORCH, "PyTorch optional for CPU benchmark execution test")
    def test_03_smoke_benchmark_end_to_end(self) -> None:
        res = bench.run_benchmark(smoke=True)
        bench.validate_results_payload(res)
        self.assertEqual(res["cs08_param_counts"]["fixed_linear_and_softmax"], 27079)
        self.assertEqual(res["cs08_param_counts"]["polynomial_p8_all_arms"], 27198)
        self.assertIsInstance(res["regression_2d"]["linear"]["mean_val_mse"], float)
        self.assertIsInstance(res["lookup_4x4_saddle_escaped"]["linear"]["mean_val_acc_pct"], float)

        # Exercise NaN train-loss and non-finite validation prediction guards cleanly
        import torch

        bmat = torch.tensor(bench.build_gegenbauer_basis_matrix_float(Fraction(1, 2)), dtype=torch.float32)
        tx = torch.full((2, 4, 9, 5), float("nan"))
        ty = torch.zeros(2, 4, 2)
        vx = torch.zeros(4, 9, 5)
        vy = torch.zeros(4, 2)
        r_nan_tr = bench._train_single_run(
            task="regression", attn_type="linear", seed=0, peak_lr=0.01,
            train_x_stream=tx, train_y_stream=ty, val_x=vx, val_y=vy, basis_mat=bmat,
        )
        self.assertTrue(r_nan_tr["nan"])

        tx_ok = torch.zeros(1, 4, 9, 5)
        vx_nan = torch.full((4, 9, 5), float("nan"))
        r_nan_val = bench._train_single_run(
            task="regression", attn_type="linear", seed=0, peak_lr=0.01,
            train_x_stream=tx_ok, train_y_stream=ty[:1], val_x=vx_nan, val_y=vy, basis_mat=bmat,
        )
        self.assertTrue(r_nan_val["nan"])


if __name__ == "__main__":
    unittest.main()
