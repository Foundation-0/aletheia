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
        valid = json.loads((_HERE / bench.RESULTS_FILENAME).read_text(encoding="utf-8"))
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

        # Item 3 R5 Plants: re-hashed oracle cert mismatch, missing sections, seed/mean tamper, and verdict flip!
        bad_orc = copy.deepcopy(valid)
        bad_orc["exact_q_oracle_certificate_sha256"] = "0" * 64
        self._expect_code(lambda: bench.validate_results_payload(_resign(bad_orc)), "ORACLE_CERT_MISMATCH")

        for sec_key in (
            "regression_2d",
            "simplicity_bias_init_rho1p8",
            "high_gain_g3_stress_test",
            "lookup_4x4_saddle_escaped",
            "lookup_8x8_single_thread_saddle_diagnostic",
        ):
            bad_sec = copy.deepcopy(valid)
            bad_sec[sec_key] = None
            self._expect_code(lambda x=bad_sec: bench.validate_results_payload(_resign(x)), "MISSING_BENCH_SECTIONS")

        bad_reg_arm = copy.deepcopy(valid)
        bad_reg_arm["regression_2d"]["linear"]["seeds"] = []
        self._expect_code(lambda: bench.validate_results_payload(_resign(bad_reg_arm)), "BAD_REG_ARM")

        bad_sc = copy.deepcopy(valid)
        bad_sc["regression_2d"]["softmax"]["seeds"] = bad_sc["regression_2d"]["softmax"]["seeds"][:2]
        self._expect_code(lambda: bench.validate_results_payload(_resign(bad_sc)), "SEED_COUNT_MISMATCH")

        bad_sb = copy.deepcopy(valid)
        bad_sb["simplicity_bias_init_rho1p8"]["linear_init_runs"] = []
        self._expect_code(lambda: bench.validate_results_payload(_resign(bad_sb)), "BAD_SB_RUNS")
        bad_sb2 = copy.deepcopy(valid)
        bad_sb2["simplicity_bias_init_rho1p8"]["t8_softmax_init_runs"] = []
        self._expect_code(lambda: bench.validate_results_payload(_resign(bad_sb2)), "BAD_SB_RUNS")

        bad_hg = copy.deepcopy(valid)
        bad_hg["high_gain_g3_stress_test"]["mono_runs"] = []
        self._expect_code(lambda: bench.validate_results_payload(_resign(bad_hg)), "BAD_HG_RUNS")
        bad_hg2 = copy.deepcopy(valid)
        bad_hg2["high_gain_g3_stress_test"]["xpi_gegen_runs"] = []
        self._expect_code(lambda: bench.validate_results_payload(_resign(bad_hg2)), "BAD_HG_RUNS")

        bad_l4 = copy.deepcopy(valid)
        bad_l4["lookup_4x4_saddle_escaped"]["linear"]["seeds"] = []
        self._expect_code(lambda: bench.validate_results_payload(_resign(bad_l4)), "BAD_LKP4_ARM")

        bad_l8 = copy.deepcopy(valid)
        bad_l8["lookup_8x8_single_thread_saddle_diagnostic"]["linear"]["seed0"] = None
        self._expect_code(lambda: bench.validate_results_payload(_resign(bad_l8)), "BAD_LKP8_ARM")

        # Plant A: overwrite a seed val_mse and rehash -> SUMMARY_METRIC_MISMATCH
        plant_mse = copy.deepcopy(valid)
        plant_mse["regression_2d"]["poly_xpi_mobius"]["seeds"][0]["val_mse"] = 0.999999
        self._expect_code(lambda: bench.validate_results_payload(_resign(plant_mse)), "SUMMARY_METRIC_MISMATCH")

        for mut_fn in (
            lambda d: d["simplicity_bias_init_rho1p8"].update({"linear_init_mean_mse": 0.999}),
            lambda d: d["simplicity_bias_init_rho1p8"].update({"t8_softmax_init_mean_mse": 0.999}),
            lambda d: d["high_gain_g3_stress_test"].update({"mono_mean_mse": 0.999}),
            lambda d: d["high_gain_g3_stress_test"].update({"xpi_gegen_mean_mse": 0.999}),
            lambda d: d["lookup_4x4_saddle_escaped"]["poly_xpi_mobius"].update({"mean_val_acc_pct": 12.3456}),
            lambda d: d["lookup_8x8_single_thread_saddle_diagnostic"]["poly_xpi_mobius"].update({"mean_val_acc_pct": 99.0}),
        ):
            m = copy.deepcopy(valid)
            mut_fn(m)
            self._expect_code(lambda x=m: bench.validate_results_payload(_resign(x)), "SUMMARY_METRIC_MISMATCH")

        # Plant B: flip graded.verdict PARTIAL -> CONFIRMED and rehash -> GRADED_VERDICT_MISMATCH (and --check rc=2!)
        plant_verdict = copy.deepcopy(valid)
        plant_verdict["graded"]["verdict"] = "CONFIRMED"
        resigned_verdict = _resign(plant_verdict)
        self._expect_code(lambda: bench.validate_results_payload(resigned_verdict), "GRADED_VERDICT_MISMATCH")

        # Plant C: overwrite lookup_8x8 seed0 + mean_val_acc_pct to 99% while leaving verdict PARTIAL -> GRADED_VERDICT_MISMATCH
        plant_g4 = copy.deepcopy(valid)
        for arm in ("softmax", "poly_xpi_mobius"):
            plant_g4["lookup_8x8_single_thread_saddle_diagnostic"][arm]["seed0"]["val_acc_pct"] = 99.0
            plant_g4["lookup_8x8_single_thread_saddle_diagnostic"][arm]["mean_val_acc_pct"] = 99.0
        self._expect_code(lambda: bench.validate_results_payload(_resign(plant_g4)), "GRADED_VERDICT_MISMATCH")

        buf_err = io.StringIO()
        with contextlib.redirect_stderr(buf_err):
            self.assertEqual(bench.main(["--write", "--check"]), 2)

        # Missing results file + CLI --check failure on rehashed verdict/MSE plants via temporary _HERE override
        with tempfile.TemporaryDirectory() as td:
            orig_here = bench._HERE
            try:
                bench._HERE = Path(td)
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(bench.main(["--check"]), 2)
                for bad_doc in (resigned_verdict, _resign(plant_mse)):
                    (Path(td) / bench.RESULTS_FILENAME).write_text(json.dumps(bad_doc), encoding="utf-8")
                    with contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(bench.main(["--check"]), 2)
            finally:
                bench._HERE = orig_here

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
