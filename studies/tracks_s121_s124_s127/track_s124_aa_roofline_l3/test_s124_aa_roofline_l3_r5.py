#!/usr/bin/env python3
"""Pure-Stdlib R5 Unit & 100%-Mutation-Kill Suite for `verify_s124_aa_roofline_l3.py`.

Zero floats / zero float literals in AST, zero bare asserts, zero skips, zero external imports.
Exercises every `require_ok` guard and exact rational boundary across G1 (S_3 A/A illusion,
PR #9 863k tok/s coalesced-chunk mirage, `64 * '!'` degenerate alphabet), G2 (PR #22, #12, #13),
G3 (HoloSphere-V3 8.80 MiB L3 & sm_86 ceilings), PREREG-W14 SHA binding, and certificate tamper.
"""

from __future__ import annotations

import ast
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

import verify_s124_aa_roofline_l3 as s124  # noqa: E402


def _resign(cert: dict[str, Any]) -> dict[str, Any]:
    body = {k: v for k, v in cert.items() if k != "certificate_sha256"}
    out = copy.deepcopy(body)
    out["certificate_sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return out


class TestS124AARooflineL3R5(unittest.TestCase):
    def _expect_code(self, fn: Callable[[], Any], code: str) -> None:
        with self.assertRaises(s124.S124RooflineError) as ctx:
            fn()
        self.assertEqual(ctx.exception.code, code)

    def test_01_ast_zero_floats_and_prereg_binding(self) -> None:
        for fname in ("verify_s124_aa_roofline_l3.py", "test_s124_aa_roofline_l3_r5.py"):
            tree = ast.parse((_HERE / fname).read_text(encoding="utf-8"))
            flt_lits = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, float)]
            flt_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "float"]
            self.assertEqual(len(flt_lits), 0, f"float literal in {fname}")
            self.assertEqual(len(flt_calls), 0, f"float() call in {fname}")

        with tempfile.TemporaryDirectory() as td:
            miss_p = Path(td) / "missing.md"
            self._expect_code(lambda: s124.verify_prereg_w14_file(miss_p), "MISSING_PREREG_W14")
            bad_p = Path(td) / "bad.md"
            bad_p.write_text("tampered", encoding="utf-8")
            self._expect_code(lambda: s124.verify_prereg_w14_file(bad_p), "PREREG_W14_SHA_MISMATCH")

    def test_02_g1_aa_illusion_and_pr9_863k_mirage_must_fail_controls(self) -> None:
        self._expect_code(lambda: s124._to_frac(True), "TYPE_ERROR")
        self._expect_code(lambda: s124._to_frac("1/3"), "TYPE_ERROR")  # type: ignore[arg-type]
        self._expect_code(lambda: s124._to_int(True), "INT_ERROR")
        self._expect_code(lambda: s124._to_int(Fraction(1, 2)), "INT_ERROR")  # type: ignore[arg-type]

        self._expect_code(lambda: s124.prove_aa_triple_false_win_q(Fraction(0)), "BAD_ALPHA_TARGET")
        self._expect_code(lambda: s124.prove_aa_triple_false_win_q(Fraction(1)), "BAD_ALPHA_TARGET")
        # Exact alpha == 1/3 boundary -> m_triples == 1 (kills while prob_m > alp -> >=!)
        p_third = s124.prove_aa_triple_false_win_q(Fraction(1, 3))
        self.assertEqual(p_third["min_independent_triples_for_alpha"], 1)

        aa_10 = [Fraction(20)] * 10
        self._expect_code(lambda: s124.compute_aa_noise_floor_margin_q([Fraction(20)] * 9), "INSUFFICIENT_AA_RUNS")
        self._expect_code(lambda: s124.compute_aa_noise_floor_margin_q("1234567890"), "INSUFFICIENT_AA_RUNS")  # type: ignore[arg-type]
        self._expect_code(lambda: s124.compute_aa_noise_floor_margin_q([Fraction(20)] * 9 + [Fraction(0)]), "NONPOS_AA_RATE")
        self.assertEqual(s124.compute_aa_noise_floor_margin_q(aa_10)["false_wins"], 0)

        good_text = "valid distinct tokens!"
        # Control rate guards
        self._expect_code(
            lambda: s124.evaluate_decode_benchmark_gate_q(
                aa_control_rates=aa_10, ctl_left_rate=0, cand_completion_tokens=64,
                cand_decode_window_sec=Fraction(3), cand_text=good_text, ctl_right_rate=20,
            ),
            "NONPOS_CTL_RATE",
        )
        self._expect_code(
            lambda: s124.evaluate_decode_benchmark_gate_q(
                aa_control_rates=aa_10, ctl_left_rate=20, cand_completion_tokens=64,
                cand_decode_window_sec=Fraction(3), cand_text=good_text, ctl_right_rate=0,
            ),
            "NONPOS_CTL_RATE",
        )
        # Completion tokens >= 2 boundary
        self._expect_code(
            lambda: s124.evaluate_decode_benchmark_gate_q(
                aa_control_rates=aa_10, ctl_left_rate=20, cand_completion_tokens=1,
                cand_decode_window_sec=Fraction(1, 20), cand_text=good_text, ctl_right_rate=20,
            ),
            "TOO_FEW_DECODE_TOKENS",
        )
        # PR #9 Must-Fail Control 1: 64 tokens delivered in 7e-5 s (~900k / 863k tok/s single-chunk mirage!)
        self._expect_code(
            lambda: s124.evaluate_decode_benchmark_gate_q(
                aa_control_rates=aa_10, ctl_left_rate=Fraction(2039, 100), cand_completion_tokens=64,
                cand_decode_window_sec=Fraction(7, 100_000), cand_text=good_text, ctl_right_rate=Fraction(2040, 100),
            ),
            "COALESCED_CHUNK_MIRAGE",
        )
        self._expect_code(
            lambda: s124.evaluate_decode_benchmark_gate_q(
                aa_control_rates=aa_10, ctl_left_rate=20, cand_completion_tokens=64,
                cand_decode_window_sec=Fraction(1), cand_text=good_text, ctl_right_rate=20,
                min_decode_window_sec=Fraction(0),
            ),
            "NONPOS_MIN_WINDOW",
        )
        # PR #9 Must-Fail Control 2: whitespace-free `64 * '!'` degenerate collapse!
        self._expect_code(
            lambda: s124.evaluate_decode_benchmark_gate_q(
                aa_control_rates=aa_10, ctl_left_rate=20, cand_completion_tokens=64,
                cand_decode_window_sec=Fraction(3), cand_text="!" * 64, ctl_right_rate=20,
            ),
            "DEGENERATE_OUTPUT_ALPHABET",
        )
        self._expect_code(
            lambda: s124.evaluate_decode_benchmark_gate_q(
                aa_control_rates=aa_10, ctl_left_rate=20, cand_completion_tokens=64,
                cand_decode_window_sec=Fraction(3), cand_text=12345, ctl_right_rate=20,  # type: ignore[arg-type]
            ),
            "DEGENERATE_OUTPUT_ALPHABET",
        )
        self._expect_code(
            lambda: s124.evaluate_decode_benchmark_gate_q(
                aa_control_rates=aa_10, ctl_left_rate=20, cand_completion_tokens=64,
                cand_decode_window_sec=Fraction(3), cand_text=good_text, ctl_right_rate=20,
                min_unique_chars=1,
            ),
            "BAD_MIN_UNIQUE_CHARS",
        )
        self._expect_code(
            lambda: s124.evaluate_decode_benchmark_gate_q(
                aa_control_rates=aa_10, ctl_left_rate=20, cand_completion_tokens=64,
                cand_decode_window_sec=Fraction(3), cand_text=good_text, ctl_right_rate=20,
                safety_factor=Fraction(9, 10),
            ),
            "BAD_SAFETY_FACTOR",
        )
        # B-S124-2 Must-Fail Control 3: m < 3 independent triples (e.g., m = 2 gives 1/9 > 1/20)!
        self._expect_code(
            lambda: s124.evaluate_decode_benchmark_gate_q(
                aa_control_rates=aa_10, ctl_left_rate=20, cand_completion_tokens=64,
                cand_decode_window_sec=Fraction(2), cand_text=good_text, ctl_right_rate=20,
                n_independent_triples=2,
            ),
            "INSUFFICIENT_INDEPENDENT_TRIPLES",
        )
        # B-S124-2 Must-Fail Control 4: zero or negative min_rel_floor_q is refused!
        self._expect_code(
            lambda: s124.evaluate_decode_benchmark_gate_q(
                aa_control_rates=aa_10, ctl_left_rate=20, cand_completion_tokens=64,
                cand_decode_window_sec=Fraction(2), cand_text=good_text, ctl_right_rate=20,
                min_rel_floor_q=Fraction(0),
            ),
            "NONPOS_MIN_REL_FLOOR",
        )
        # B-S124-2 Must-Fail Control 5: zero-false-win constant & monotone ledgers NEVER set required_margin = 0!
        jitter_const = s124.evaluate_decode_benchmark_gate_q(
            aa_control_rates=aa_10, ctl_left_rate=20, cand_completion_tokens=129,
            cand_decode_window_sec=Fraction(128, 20) / Fraction(1001, 1000),
            cand_text=good_text, ctl_right_rate=20,
        )
        self.assertFalse(jitter_const["accepted"])
        self.assertGreater(Fraction(jitter_const["required_rel_margin_q"]), Fraction(0))

        monotone_aa = [Fraction(2000 - k, 100) for k in range(10)]
        self.assertEqual(s124.compute_aa_noise_floor_margin_q(monotone_aa)["false_wins"], 0)
        jitter_mono = s124.evaluate_decode_benchmark_gate_q(
            aa_control_rates=monotone_aa, ctl_left_rate=20, cand_completion_tokens=129,
            cand_decode_window_sec=Fraction(128, 20) / Fraction(1001, 1000),
            cand_text=good_text, ctl_right_rate=20,
        )
        self.assertFalse(jitter_mono["accepted"])
        self.assertGreater(Fraction(jitter_mono["required_rel_margin_q"]), Fraction(0))

        # Monotone ledger with 1/21 (~4.76%) adjacent spread rejects a +3% sub-spread candidate!
        steep_mono_aa = [Fraction(30 - k) for k in range(10)]
        self.assertEqual(s124.compute_aa_noise_floor_margin_q(steep_mono_aa)["false_wins"], 0)
        sub_spread = s124.evaluate_decode_benchmark_gate_q(
            aa_control_rates=steep_mono_aa, ctl_left_rate=20, cand_completion_tokens=129,
            cand_decode_window_sec=Fraction(128, 20) / Fraction(103, 100),
            cand_text=good_text, ctl_right_rate=20,
        )
        self.assertFalse(sub_spread["accepted"])

        # Exact boundary acceptance: n_independent_triples == 3, ct == 2, win_s == min_decode_window_sec == 1/20, min_unique_chars == 2, safety_factor == 1
        exact_ok = s124.evaluate_decode_benchmark_gate_q(
            aa_control_rates=aa_10, ctl_left_rate=10, cand_completion_tokens=2,
            cand_decode_window_sec=Fraction(1, 20), cand_text="ab", ctl_right_rate=10,
            n_independent_triples=3, safety_factor=Fraction(1), min_decode_window_sec=Fraction(1, 20), min_unique_chars=2,
        )
        self.assertTrue(exact_ok["accepted"])

    def test_03_g2_rooflines_and_must_fail_guards(self) -> None:
        base_loop = dict(
            prelude_layers=0, core_layers=1, core_loops=1, postlude_layers=0,
            bytes_per_visit_gb=Fraction(1), bandwidth_gbps=Fraction(100),
            flops_per_visit_gflops=Fraction(100), spec_2to4_sparse_tflops=Fraction(100),
        )
        self.assertEqual(s124.looped_model_roofline_q(**base_loop)["visit_to_physical_ratio_q"], "1/1")
        for bad_k, bad_v in (("prelude_layers", -1), ("core_layers", 0), ("core_loops", 0), ("postlude_layers", -1)):
            self._expect_code(lambda k=bad_k, v=bad_v: s124.looped_model_roofline_q(**{**base_loop, k: v}), "BAD_LOOP_TOPOLOGY")
        for bad_k in ("bytes_per_visit_gb", "bandwidth_gbps", "flops_per_visit_gflops", "spec_2to4_sparse_tflops"):
            self._expect_code(lambda k=bad_k: s124.looped_model_roofline_q(**{**base_loop, k: 0}), "NONPOS_ROOFLINE_INPUT")

        base_moe = dict(prelude_gb=1, core_gb=1, postlude_gb=1, top_k=1, n_experts=1, core_loops=1)
        self.assertEqual(s124.loop_aware_moe_vram_roi_q(**base_moe)["core_vs_boundary_roi_ratio_q"], "1/1")
        for bad_k in ("prelude_gb", "core_gb", "postlude_gb"):
            self._expect_code(lambda k=bad_k: s124.loop_aware_moe_vram_roi_q(**{**base_moe, k: 0}), "NONPOS_MOE_GB")
        for bad_k, bad_v in (("top_k", 0), ("top_k", 2), ("core_loops", 0)):
            self._expect_code(lambda k=bad_k, v=bad_v: s124.loop_aware_moe_vram_roi_q(**{**base_moe, k: v}), "BAD_MOE_ROUTING")

        base_spec = dict(
            bandwidth_gbps=100, n_requests=1, draft_steps_k=1,
            accepted_tokens_per_req=2, verify_bytes_gb=1, draft_weight_bytes_gb=Fraction(1, 4),
        )
        self.assertEqual(s124.batched_speculative_decode_ceiling_q(**base_spec)["relative_underestimate_q"], "0/1")
        for bad_k in ("n_requests", "draft_steps_k"):
            self._expect_code(lambda k=bad_k: s124.batched_speculative_decode_ceiling_q(**{**base_spec, k: 0}), "BAD_BATCH_SPEC")
        for bad_k in ("bandwidth_gbps", "accepted_tokens_per_req", "verify_bytes_gb", "draft_weight_bytes_gb"):
            self._expect_code(lambda k=bad_k: s124.batched_speculative_decode_ceiling_q(**{**base_spec, k: 0}), "NONPOS_SPEC_BYTES")

    def test_04_certificate_validator_tamper_and_cli_roundtrip(self) -> None:
        cert = s124.build_s124_certificate()
        s124.validate_s124_certificate(cert)

        self._expect_code(lambda: s124.validate_s124_certificate("bad"), "BAD_CERT_HEADER")  # type: ignore[arg-type]
        for hdr_k, hdr_v in (("schema", "bad"), ("float_ops_used", 1), ("preregistration_sha256", "0" * 64)):
            m = copy.deepcopy(cert)
            m[hdr_k] = hdr_v
            self._expect_code(lambda x=m: s124.validate_s124_certificate(_resign(x)), "BAD_CERT_HEADER")

        m_short = copy.deepcopy(cert)
        m_short["certificate_sha256"] = "short"
        self._expect_code(lambda: s124.validate_s124_certificate(m_short), "MISSING_CERT_SHA")
        m_none = copy.deepcopy(cert)
        m_none["certificate_sha256"] = None
        self._expect_code(lambda: s124.validate_s124_certificate(m_none), "MISSING_CERT_SHA")
        m_bad_sha = copy.deepcopy(cert)
        m_bad_sha["certificate_sha256"] = "0" * 64
        self._expect_code(lambda: s124.validate_s124_certificate(m_bad_sha), "CERT_SHA_MISMATCH")

        g1_tampers: list[Callable[[dict[str, Any]], None]] = [
            lambda c: c["g1_aa_illusion_and_mirage_gate"]["combinatorial_proof"].update({"single_triple_false_win_prob_q": "1/2"}),
            lambda c: c["g1_aa_illusion_and_mirage_gate"]["combinatorial_proof"].update({"min_independent_triples_for_alpha": 2}),
            lambda c: c["g1_aa_illusion_and_mirage_gate"]["combinatorial_proof"].update({"m_triple_false_win_prob_q": "1/9"}),
            lambda c: c["g1_aa_illusion_and_mirage_gate"]["pr11_calibrated_floor"].update({"max_false_win_rel_margin_q": "0/1"}),
            lambda c: c["g1_aa_illusion_and_mirage_gate"].update({"sub_floor_1pct_candidate_rejected": False}),
            lambda c: c["g1_aa_illusion_and_mirage_gate"].update({"zero_false_win_jitter_candidate_rejected": False}),
            lambda c: c["g1_aa_illusion_and_mirage_gate"].update({"genuine_25pct_candidate_accepted": False}),
        ]
        for fn in g1_tampers:
            m = copy.deepcopy(cert)
            fn(m)
            self._expect_code(lambda x=m: s124.validate_s124_certificate(_resign(x)), "G1_CERT_INVALID")

        g2_tampers: list[Callable[[dict[str, Any]], None]] = [
            lambda c: c["g2_looped_and_batched_draft_rooflines"]["pr22_inkling2_mini_visits"].update({"physical_layers": 12}),
            lambda c: c["g2_looped_and_batched_draft_rooflines"]["pr22_inkling2_mini_visits"].update({"logical_layer_visits": 24}),
            lambda c: c["g2_looped_and_batched_draft_rooflines"]["pr22_inkling2_mini_visits"].update({"decode_overstatement_ratio_q": "1/1"}),
            lambda c: c["g2_looped_and_batched_draft_rooflines"]["pr22_inkling2_mini_visits"].update({"prefill_sparse_phys_vs_dense_visit_ratio_q": "1/1"}),
            lambda c: c["g2_looped_and_batched_draft_rooflines"]["pr12_loop_aware_moe_vram_roi"].update({"boundary_mb_per_tok_per_gb_q": "1/1"}),
            lambda c: c["g2_looped_and_batched_draft_rooflines"]["pr12_loop_aware_moe_vram_roi"].update({"core_mb_per_tok_per_gb_q": "1/1"}),
            lambda c: c["g2_looped_and_batched_draft_rooflines"]["pr12_loop_aware_moe_vram_roi"].update({"core_vs_boundary_roi_ratio_q": "1/1"}),
            lambda c: c["g2_looped_and_batched_draft_rooflines"]["pr12_loop_aware_moe_vram_roi"].update({"core_share_of_active_traffic_q": "1/2"}),
            lambda c: c["g2_looped_and_batched_draft_rooflines"]["pr13_batched_single_read_draft"].update({"true_aggregate_ceiling_tok_s_q": "400/1"}),
            lambda c: c["g2_looped_and_batched_draft_rooflines"]["pr13_batched_single_read_draft"].update({"buggy_aggregate_ceiling_tok_s_q": "640/1"}),
            lambda c: c["g2_looped_and_batched_draft_rooflines"]["pr13_batched_single_read_draft"].update({"relative_underestimate_q": "0/1"}),
        ]
        for fn in g2_tampers:
            m = copy.deepcopy(cert)
            fn(m)
            self._expect_code(lambda x=m: s124.validate_s124_certificate(_resign(x)), "G2_CERT_INVALID")

        g3_tampers: list[Callable[[dict[str, Any]], None]] = [
            lambda c: c["g3_holosphere_v3_15m_l3_roofline"].update({"safetensors_file_bytes": 1}),
            lambda c: c["g3_holosphere_v3_15m_l3_roofline"].update({"tensor_payload_bytes": 1}),
            lambda c: c["g3_holosphere_v3_15m_l3_roofline"].update({"input_embedding_bytes": 1}),
            lambda c: c["g3_holosphere_v3_15m_l3_roofline"].update({"persistent_o1_state_bytes": 1}),
            lambda c: c["g3_holosphere_v3_15m_l3_roofline"].update({"kv_bytes_per_token": 1}),
            lambda c: c["g3_holosphere_v3_15m_l3_roofline"].update({"resident_total_bytes": 1}),
            lambda c: c["g3_holosphere_v3_15m_l3_roofline"].update({"fits_in_24mib_l3": False}),
            lambda c: c["g3_holosphere_v3_15m_l3_roofline"].update({"hugepages_2mib_needed_holosphere_v3": 99}),
            lambda c: c["g3_holosphere_v3_15m_l3_roofline"].update({"i9_l3_vs_ddr4_bandwidth_lift_q": "1/1"}),
            lambda c: c["g3_holosphere_v3_15m_l3_roofline"].update({"live_v3_46468_over_gddr6_tied_q": "1/1"}),
            lambda c: c["g3_holosphere_v3_15m_l3_roofline"].update({"live_v3_46468_over_l2_tied_q": "1/1"}),
            lambda c: c["g3_holosphere_v3_15m_l3_roofline"].update({"i9_1c_practical_fma_compute_ceiling_tok_s_q": "1/1"}),
            lambda c: c["g3_holosphere_v3_15m_l3_roofline"].update({"i9_1c_l3_is_compute_bound": False}),
        ]
        for fn in g3_tampers:
            m = copy.deepcopy(cert)
            fn(m)
            self._expect_code(lambda x=m: s124.validate_s124_certificate(_resign(x)), "G3_CERT_INVALID")

        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(s124.main(["--write", "--check"]), 2)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(s124.main([]), 0)
            self.assertEqual(s124.main(["--json"]), 0)

        # CLI --write, --check, missing cert, and CERT_DRIFT check in temporary isolated copy
        with tempfile.TemporaryDirectory() as td:
            orig_file = s124.__file__
            try:
                s124.__file__ = str(Path(td) / "verify_s124_aa_roofline_l3.py")
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(s124.main(["--check"]), 2)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(s124.main(["--write"]), 0)
                    self.assertEqual(s124.main(["--check"]), 0)
                cp = Path(td) / s124.CERT_FILENAME
                drifted = copy.deepcopy(json.loads(cp.read_text(encoding="utf-8")))
                drifted["track"] = "S999"
                cp.write_text(json.dumps(_resign(drifted)), encoding="utf-8")
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(s124.main(["--check"]), 2)
            finally:
                s124.__file__ = orig_file


if __name__ == "__main__":
    unittest.main()
