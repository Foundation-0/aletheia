#!/usr/bin/env python3
"""
Track S96 Assertion-Free R5 Hardened Unit Test Suite.

Covers all 4 Pillars (LoRA's 3 exact bottlenecks, 3 Beyond-LoRA epistemic-native adapters
+ Law-5 obstructions, Inkling-2-Mini inkling2_loop architecture & 8 GiB vs 32 GiB roofline,
provenance & Lean 4.36.0 anchor), exact-Q oracle boundaries, Zone-B fail-closed I/O & JSON
attacks, 4-surface API (CLI/FR1/FR0/SEC), (0o600, 0o644) committed disk-cert parity + strict
0o600 --write, scratch os.mkfifo probes, hardlinks, symlinks, read-only directories,
--verify-upstream & --verify-inkling manifest checks, all R10+ static Lean 4 bypasses,
AND 0-skip Lean-less CI dual-mode compatibility (ALETHEIA_REQUIRE_LEAN=1).
"""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import s96_beyond_lora_inkling_oracle as s96
import verify_s96_beyond_lora_inkling as ver


def _resign(cert: dict) -> dict:
    p_sha = hashlib.sha256(s96.canonical_json_bytes(cert["payload"])).hexdigest()
    env = {
        "schema": cert["schema"],
        "track_id": cert["track_id"],
        "payload_sha256": p_sha,
        "payload": cert["payload"],
    }
    c_sha = hashlib.sha256(s96.canonical_json_bytes(env)).hexdigest()
    return {
        "schema": cert["schema"],
        "track_id": cert["track_id"],
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "payload": cert["payload"],
    }


class TestS96OraclePrimitives(unittest.TestCase):
    def test_error_guards_and_formatters(self) -> None:
        err = s96.S96Error("E_CODE", "e msg")
        self.assertEqual(err.code, "E_CODE")
        self.assertEqual(err.message, "e msg")
        self.assertEqual(str(err), "[E_CODE] e msg")

        s96.require_ok(True, "OK", "ok")
        for bad in (False, 1, "yes", None):
            with self.assertRaises(s96.S96Error) as ctx:
                s96.require_ok(bad, "BAD_COND", "bad")  # type: ignore[arg-type]
            self.assertEqual(ctx.exception.code, "BAD_COND")

        self.assertEqual(s96.q_obj(Fraction(-6, 4)), {"num": -3, "den": 2})
        with self.assertRaises(s96.S96Error) as cq:
            s96.q_obj(3)  # type: ignore[arg-type]
        self.assertEqual(cq.exception.code, "INVALID_FRACTION")

        self.assertEqual(s96.frac_to_dec_str(Fraction(1, 4), 1), "0.2")
        self.assertEqual(s96.frac_to_dec_str(Fraction(1, 8), 3), "0.125")
        self.assertEqual(s96.frac_to_dec_str(Fraction(1, 2), 12), "0.500000000000")
        with self.assertRaises(s96.S96Error):
            s96.frac_to_dec_str(1, 2)  # type: ignore[arg-type]
        for bad_pl in (0, 13, True):
            with self.assertRaises(s96.S96Error) as cpl:
                s96.frac_to_dec_str(Fraction(1, 2), bad_pl)  # type: ignore[arg-type]
            self.assertEqual(cpl.exception.code, "INVALID_PLACES")

        self.assertEqual(s96._check_exact_int(7, "x"), 7)
        with self.assertRaises(s96.S96Error):
            s96._check_exact_int(True, "x")
        self.assertEqual(s96._check_exact_frac(Fraction(2, 3), "f"), Fraction(2, 3))
        with self.assertRaises(s96.S96Error):
            s96._check_exact_frac(2, "f")  # type: ignore[arg-type]

    def test_exact_linear_algebra_primitives(self) -> None:
        # Matrix validation failures (list, non-empty, row list, non-empty row, ragged, entry Fraction)
        for bad_m in (
            [],
            "notlist",
            ([Fraction(1)],),
            [[]],
            ["bad"],
            [[Fraction(1)], "bad"],
            [[Fraction(1)], (Fraction(2),)],
            [[Fraction(1), Fraction(2)], [Fraction(3)]],
            [[1]],
        ):
            with self.assertRaises(s96.S96Error):
                s96.exact_transpose_q(bad_m)  # type: ignore[arg-type]
        with self.assertRaises(s96.S96Error) as c_mr0:
            s96.exact_transpose_q([(Fraction(1),)])  # type: ignore[list-item]
        self.assertEqual(c_mr0.exception.code, "INVALID_MATRIX_ROW")

        # matmul, transpose, frob_norm_sq
        a = [[Fraction(1), Fraction(2)], [Fraction(3), Fraction(4)]]
        b = [[Fraction(2)], [Fraction(-1)]]
        self.assertEqual(s96.exact_matmul_q(a, b), [[Fraction(0)], [Fraction(2)]])
        self.assertEqual(
            s96.exact_transpose_q(a),
            [[Fraction(1), Fraction(3)], [Fraction(2), Fraction(4)]],
        )
        self.assertEqual(s96.exact_frob_norm_sq_q(a), Fraction(30))
        with self.assertRaises(s96.S96Error) as c_mm:
            s96.exact_matmul_q(b, a)
        self.assertEqual(c_mm.exception.code, "MATMUL_DIM_MISMATCH")

        # exact_rank_q: full, zero col, swap, wide, tall, rank-deficient
        self.assertEqual(s96.exact_rank_q([[Fraction(0), Fraction(1)], [Fraction(1), Fraction(0)]]), 2)
        self.assertEqual(s96.exact_rank_q([[Fraction(0), Fraction(0)], [Fraction(0), Fraction(2)]]), 1)
        self.assertEqual(s96.exact_rank_q([[Fraction(1), Fraction(2), Fraction(3)], [Fraction(2), Fraction(4), Fraction(6)]]), 1)
        self.assertEqual(s96.exact_rank_q([[Fraction(1), Fraction(0), Fraction(2)], [Fraction(0), Fraction(1), Fraction(3)]]), 2)
        self.assertEqual(s96.exact_rank_q([[Fraction(1)], [Fraction(2)], [Fraction(3)]]), 1)

        # exact_det_q: 1x1, swap sign flip, singular, 3x3, non-square
        self.assertEqual(s96.exact_det_q([[Fraction(5)]]), Fraction(5))
        self.assertEqual(
            s96.exact_det_q([[Fraction(0), Fraction(1)], [Fraction(1), Fraction(0)]]),
            Fraction(-1),
        )
        self.assertEqual(
            s96.exact_det_q([[Fraction(1), Fraction(2)], [Fraction(2), Fraction(4)]]),
            Fraction(0),
        )
        self.assertEqual(
            s96.exact_det_q(
                [
                    [Fraction(2), Fraction(1), Fraction(0)],
                    [Fraction(1), Fraction(3), Fraction(1)],
                    [Fraction(0), Fraction(1), Fraction(2)],
                ]
            ),
            Fraction(8),
        )
        with self.assertRaises(s96.S96Error) as c_nsq_det:
            s96.exact_det_q([[Fraction(1), Fraction(2)]])
        self.assertEqual(c_nsq_det.exception.code, "NON_SQUARE_MATRIX")

        # exact_inv_q: pivot swap, identity verification, non-square, singular
        inv_swap = s96.exact_inv_q([[Fraction(0), Fraction(2)], [Fraction(1), Fraction(1)]])
        self.assertEqual(
            inv_swap,
            [[Fraction(-1, 2), Fraction(1)], [Fraction(1, 2), Fraction(0)]],
        )
        with self.assertRaises(s96.S96Error) as c_nsq_inv:
            s96.exact_inv_q([[Fraction(1), Fraction(2)]])
        self.assertEqual(c_nsq_inv.exception.code, "NON_SQUARE_MATRIX")
        with self.assertRaises(s96.S96Error) as c_sing_inv:
            s96.exact_inv_q([[Fraction(1), Fraction(2)], [Fraction(2), Fraction(4)]])
        self.assertEqual(c_sing_inv.exception.code, "SINGULAR_MATRIX")

    def test_domain_operators_and_boundary_guards(self) -> None:
        # LoRA metrics boundaries
        full_sq = s96.lora_rank_and_gauge_metrics(4, 4, 4)
        self.assertFalse(full_sq["rank_starved"])
        self.assertEqual(full_sq["unreachable_dim"], 0)
        self.assertEqual(full_sq["eta_alg_q"], {"num": 1, "den": 2})
        starved = s96.lora_rank_and_gauge_metrics(8, 4, 2)
        self.assertTrue(starved["rank_starved"])
        self.assertEqual(starved["unreachable_dim"], 2)
        self.assertEqual(starved["unreachable_frac_q"], {"num": 1, "den": 2})
        for bad_args in ((0, 4, 1), (4, 0, 1), (4, 4, 0)):
            with self.assertRaises(s96.S96Error) as c_np:
                s96.lora_rank_and_gauge_metrics(*bad_args)
            self.assertEqual(c_np.exception.code, "NONPOS_DIM")
        with self.assertRaises(s96.S96Error) as c_rk:
            s96.lora_rank_and_gauge_metrics(4, 8, 5)
        self.assertEqual(c_rk.exception.code, "RANK_EXCEEDS_DIM")

        # Householder boundaries
        q2 = s96.build_householder_q([Fraction(1), Fraction(1)])
        self.assertEqual(q2, [[Fraction(0), Fraction(-1)], [Fraction(-1), Fraction(0)]])
        for bad_u in ("bad", (Fraction(1), Fraction(2)), [Fraction(1)]):
            with self.assertRaises(s96.S96Error) as c_uv:
                s96.build_householder_q(bad_u)  # type: ignore[arg-type]
            self.assertEqual(c_uv.exception.code, "INVALID_VEC")
        with self.assertRaises(s96.S96Error) as c_zv:
            s96.build_householder_q([Fraction(0), Fraction(0)])
        self.assertEqual(c_zv.exception.code, "ZERO_VEC")

        # Nullspace projection boundaries (non-square delta_w AND dim mismatch with x_base)
        with self.assertRaises(s96.S96Error) as c_p1:
            s96.build_nullspace_projected_update(
                [[Fraction(1), Fraction(0), Fraction(0)], [Fraction(0), Fraction(1), Fraction(0)]],
                [[Fraction(1)], [Fraction(0)], [Fraction(0)]],
            )
        self.assertEqual(c_p1.exception.code, "PROJ_DIM_MISMATCH")
        with self.assertRaises(s96.S96Error) as c_p2:
            s96.build_nullspace_projected_update(
                [[Fraction(1), Fraction(0)], [Fraction(0), Fraction(1)]],
                [[Fraction(1)], [Fraction(0)], [Fraction(0)]],
            )
        self.assertEqual(c_p2.exception.code, "PROJ_DIM_MISMATCH")

        # Per-pass quantization noise & M1-H1 drift obstruction boundaries (all 4 boolean corners!)
        self.assertEqual(s96.eval_per_pass_quant_noise(Fraction(1, 4), 1), Fraction(1, 1))
        self.assertEqual(s96.eval_per_pass_quant_noise(Fraction(1, 4), 3), Fraction(21, 16))
        self.assertEqual(s96.eval_per_pass_quant_noise(Fraction(1, 2), 16), Fraction(65535, 32768))
        for bad_rho in (Fraction(0), Fraction(-1, 4), 1):
            with self.assertRaises(s96.S96Error):
                s96.eval_per_pass_quant_noise(bad_rho, 3)  # type: ignore[arg-type]
        for bad_np in (0, 17, True):
            with self.assertRaises(s96.S96Error):
                s96.eval_per_pass_quant_noise(Fraction(1, 4), bad_np)  # type: ignore[arg-type]

        # All 4 (contracts_init, breaches_cap) corners + exact equality boundaries
        obs_tt = s96.eval_m1h1_drift_obstruction(Fraction(3, 4), 3, Fraction(2, 1))
        self.assertEqual(obs_tt["rho_k"], Fraction(27, 64))
        self.assertEqual(obs_tt["g_k"], Fraction(37, 16))
        self.assertTrue(obs_tt["contracts_init_but_kills_m1h1"])
        obs_tf = s96.eval_m1h1_drift_obstruction(Fraction(1, 4), 3, Fraction(2, 1))
        self.assertFalse(obs_tf["contracts_init_but_kills_m1h1"])
        obs_tf_eq = s96.eval_m1h1_drift_obstruction(Fraction(3, 4), 3, Fraction(37, 16))
        self.assertFalse(obs_tf_eq["contracts_init_but_kills_m1h1"])
        obs_ft = s96.eval_m1h1_drift_obstruction(Fraction(1, 1), 3, Fraction(2, 1))
        self.assertFalse(obs_ft["contracts_init_but_kills_m1h1"])
        obs_ff = s96.eval_m1h1_drift_obstruction(Fraction(5, 4), 3, Fraction(10, 1))
        self.assertFalse(obs_ff["contracts_init_but_kills_m1h1"])
        for bad_cap in (Fraction(0), Fraction(-1, 2), 2):
            with self.assertRaises(s96.S96Error):
                s96.eval_m1h1_drift_obstruction(Fraction(3, 4), 3, bad_cap)  # type: ignore[arg-type]

        # Hardware roofline evaluator: all 4 (stream_fits_vram, cold_fits_ram) combinations + exact boundary + nonpos
        r_tt = s96.eval_hardware_roofline(
            model_gb_q=Fraction(8),
            gpu_vram_gb_q=Fraction(8),
            host_ram_gb_q=Fraction(16),
            shared_gb_q=Fraction(2),
            hot_experts_gb_q=Fraction(4),
            cold_experts_gb_q=Fraction(16),
            kv_headroom_gb_q=Fraction(2),
        )
        self.assertTrue(r_tt["full_resident_fits"])
        self.assertEqual(r_tt["full_resident_overflow_gb_q"], {"num": 0, "den": 1})
        self.assertTrue(r_tt["streamed_fits_gpu"])
        self.assertTrue(r_tt["cold_fits_host_ram"])
        self.assertTrue(r_tt["streaming_tier_feasible"])

        r_tf = s96.eval_hardware_roofline(
            model_gb_q=Fraction(20),
            gpu_vram_gb_q=Fraction(8),
            host_ram_gb_q=Fraction(10),
            shared_gb_q=Fraction(2),
            hot_experts_gb_q=Fraction(4),
            cold_experts_gb_q=Fraction(14),
            kv_headroom_gb_q=Fraction(2),
        )
        self.assertTrue(r_tf["streamed_fits_gpu"])
        self.assertFalse(r_tf["cold_fits_host_ram"])
        self.assertFalse(r_tf["streaming_tier_feasible"])

        r_ft = s96.eval_hardware_roofline(
            model_gb_q=Fraction(20),
            gpu_vram_gb_q=Fraction(8),
            host_ram_gb_q=Fraction(31),
            shared_gb_q=Fraction(3),
            hot_experts_gb_q=Fraction(5),
            cold_experts_gb_q=Fraction(12),
            kv_headroom_gb_q=Fraction(2),
        )
        self.assertFalse(r_ft["streamed_fits_gpu"])
        self.assertTrue(r_ft["cold_fits_host_ram"])
        self.assertFalse(r_ft["streaming_tier_feasible"])

        r_ff = s96.eval_hardware_roofline(
            model_gb_q=Fraction(20),
            gpu_vram_gb_q=Fraction(8),
            host_ram_gb_q=Fraction(8),
            shared_gb_q=Fraction(3),
            hot_experts_gb_q=Fraction(5),
            cold_experts_gb_q=Fraction(12),
            kv_headroom_gb_q=Fraction(2),
        )
        self.assertFalse(r_ff["streamed_fits_gpu"])
        self.assertFalse(r_ff["cold_fits_host_ram"])
        self.assertFalse(r_ff["streaming_tier_feasible"])

        with self.assertRaises(s96.S96Error) as c_nm:
            s96.eval_hardware_roofline(
                model_gb_q=Fraction(0),
                gpu_vram_gb_q=Fraction(8),
                host_ram_gb_q=Fraction(31),
                shared_gb_q=Fraction(2),
                hot_experts_gb_q=Fraction(4),
                cold_experts_gb_q=Fraction(10),
                kv_headroom_gb_q=Fraction(2),
            )
        self.assertEqual(c_nm.exception.code, "NONPOS_MEM")

    def test_four_pillars_certificate_values(self) -> None:
        # Deep-copy isolation check: mutating returned cert must never alias a fresh build_certificate()
        cert = s96.build_certificate()
        cert_alias = s96.build_certificate()
        cert_alias["payload"]["pillar1_lora_three_bottlenecks"]["pillar_verified"] = False
        cert_alias["payload"]["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"]["mtp_target_layer_ids"].append(99)
        cert_fresh = s96.build_certificate()
        self.assertTrue(ver.exact_typed_equal(cert, cert_fresh))
        ver.audit_certificate_object(cert)
        self.assertEqual(cert["schema"], s96.CERT_SCHEMA)
        self.assertEqual(cert["track_id"], s96.CERT_TRACK_ID)
        p = cert["payload"]

        # Pillar 1: LoRA's 3 exact mathematical bottlenecks
        p1 = p["pillar1_lora_three_bottlenecks"]
        self.assertTrue(p1["pillar_verified"])
        self.assertEqual(p1["qwen25_05b_r16_starvation"]["unreachable_dim"], 880)
        self.assertEqual(p1["qwen25_05b_r16_starvation"]["unreachable_frac_q"], {"num": 55, "den": 56})
        self.assertEqual(p1["qwen25_05b_r16_starvation"]["unreachable_pct_dec"], "98.21")
        self.assertEqual(p1["s78_fig3_vproj_r128"]["d_eff"], 180224)
        self.assertEqual(p1["s78_fig3_vproj_r128"]["eta_alg_q"], {"num": 11, "den": 12})
        self.assertEqual(p1["s78_full_rank_r512"]["eta_alg_q"], {"num": 2, "den": 3})
        self.assertEqual(p1["privileged_basis_commutator"]["anisotropic_comm_frob_sq_q"], {"num": 54, "den": 1})
        self.assertEqual(p1["privileged_basis_commutator"]["isotropic_comm_frob_sq_q"], {"num": 0, "den": 1})
        self.assertEqual(p1["s78_fig7_unit_conservation"]["forgetting_kb_q"], {"num": 229, "den": 5})
        self.assertEqual(p1["s78_fig7_unit_conservation"]["forgetting_over_learning_q"], {"num": 1, "den": 1})

        # Pillar 2: Three Beyond-LoRA epistemic-native adapters + Law-5 obstructions
        p2 = p["pillar2_beyond_lora_architectures"]
        self.assertTrue(p2["pillar_verified"])
        bf = p2["matched_budget_blockh4_butterfly"]
        self.assertEqual(bf["matched_param_budget"], 32)
        self.assertEqual(bf["standard_lora_rank"], 2)
        self.assertEqual(bf["butterfly_rank"], 8)
        self.assertEqual(bf["butterfly_interleaved_rank"], 8)
        self.assertEqual(bf["full_rank_advantage_q"], {"num": 4, "den": 1})
        self.assertEqual(bf["law5_unpermuted_cross_block_sq_q"], {"num": 0, "den": 1})
        self.assertEqual(bf["interleaved_cross_block_sq_q"], {"num": 660, "den": 1})
        hh = p2["privsparse_householder_isometry"]
        self.assertEqual(hh["s42_fisher_waterfilling_gain_q"], {"num": 263, "den": 16})
        self.assertEqual(hh["householder_det_q"], {"num": -1, "den": 1})
        self.assertEqual(hh["probe_norm_sq_before_q"], {"num": 30, "den": 1})
        self.assertEqual(hh["probe_norm_sq_after_q"], {"num": 30, "den": 1})
        self.assertEqual(hh["householder_kappa2_q"], {"num": 1, "den": 1})
        self.assertEqual(hh["s82_shear_kappa2_lower_q"], {"num": 1309, "den": 500})
        ns = p2["nullspace_projected_antiforgetting"]
        self.assertEqual(ns["rank2_calibration_projection"]["raw_forgetting_sq_q"], {"num": 46, "den": 1})
        self.assertEqual(ns["rank2_calibration_projection"]["projected_forgetting_sq_q"], {"num": 0, "den": 1})
        self.assertEqual(ns["rank2_calibration_projection"]["projected_update_energy_sq_q"], {"num": 11, "den": 1})
        self.assertEqual(ns["law5_full_rank_saturation_control"]["nullspace_dim"], 0)
        self.assertEqual(ns["law5_full_rank_saturation_control"]["projected_update_energy_sq_q"], {"num": 0, "den": 1})
        hyb = p2["s95_bf16_ulp_diagnosis_and_hybrid_prereg"]
        self.assertEqual(hyb["bf16_half_ulp_threshold_q"], {"num": 1, "den": 256})
        self.assertEqual(hyb["bf16_half_ulp_zero_frac_butterfly_q"], {"num": 407, "den": 500})
        self.assertEqual(hyb["bf16_half_ulp_zero_frac_lora_q"], {"num": 873, "den": 10000})
        self.assertEqual(hyb["bf16_annihilation_ratio_q"], {"num": 8140, "den": 873})
        self.assertEqual(hyb["bf16_annihilation_ratio_dec"], "9.3242")
        self.assertEqual(hyb["butterflyhead_bfly_params"], 14336)
        self.assertEqual(hyb["butterflyhead_head_params"], 14336)
        self.assertEqual(hyb["butterflyhead_total_params_per_proj"], 28672)
        self.assertEqual(hyb["butterflyhead_lr_ratio_q"], {"num": 10, "den": 1})
        self.assertEqual(hyb["s104_kronecker_rank2_head_params"], 3616)
        self.assertEqual(hyb["s104_kronecker_compression_ratio_q"], {"num": 448, "den": 113})
        self.assertTrue(hyb["exact_budget_parity_verified"])

        # Pillar 3: Inkling-2-Mini (inkling2_loop) architecture, 3x leverage & hardware roofline
        p3 = p["pillar3_inkling2_loop_and_roofline"]
        self.assertTrue(p3["pillar_verified"])
        cfg = p3["inkling2_config_exact"]
        self.assertEqual(cfg["hidden_size"], 2304)
        self.assertEqual(cfg["sqrt_hidden_size"], 48)
        self.assertEqual(cfg["effective_layers"], 48)
        self.assertEqual(cfg["depth_reuse_ratio_q"], {"num": 2, "den": 1})
        self.assertEqual(cfg["gate_rank_over_sqrt_hidden_q"], {"num": 4, "den": 3})
        self.assertEqual(cfg["active_expert_frac_q"], {"num": 1, "den": 16})
        self.assertEqual(cfg["intermediate_over_hidden_q"], {"num": 1, "den": 2})
        self.assertEqual(cfg["mtp_target_layer_ids"], [5, 23, 41, 48])
        self.assertEqual(cfg["readme_effective_over_physical_active_q"], {"num": 27, "den": 17})
        amp = p3["loop_core_adapter_amplification"]
        self.assertEqual(amp["gate_adapter_params_per_core_layer"], 294912)
        self.assertEqual(amp["core_adapter_total_params"], 3538944)
        self.assertEqual(amp["nonloop_equivalent_params"], 10616832)
        self.assertEqual(amp["effective_layer_leverage_q"], {"num": 3, "den": 1})
        self.assertEqual(amp["s76_3pass_error_bound_q"], {"num": 1, "den": 64})
        self.assertEqual(amp["divergent_3pass_error_q"], {"num": 125, "den": 64})
        m1h1 = p3["per_pass_quant_noise_and_m1h1_gate"]
        self.assertEqual(m1h1["s76_g3_quant_amp_q"], {"num": 21, "den": 16})
        self.assertEqual(m1h1["s76_g3_quant_amp_dec"], "1.3125")
        self.assertEqual(m1h1["s76_g3_over_rho3_ratio_q"], {"num": 84, "den": 1})
        self.assertTrue(m1h1["s76_passes_m1h1_drift_gate"])
        self.assertEqual(m1h1["high_rho_3pass_init_q"], {"num": 27, "den": 64})
        self.assertEqual(m1h1["high_rho_g3_quant_amp_q"], {"num": 37, "den": 16})
        self.assertEqual(m1h1["high_rho_g3_quant_amp_dec"], "2.3125")
        self.assertTrue(m1h1["high_rho_contracts_init_but_kills_m1h1"])
        self.assertEqual(m1h1["threshold_lo_g3_q"], {"num": 49, "den": 25})
        self.assertEqual(m1h1["threshold_hi_g3_q"], {"num": 129, "den": 64})
        self.assertEqual(m1h1["m1h1_max_drift_ratio_delta3_over_delta1_ctrl_q"], {"num": 2, "den": 1})
        self.assertEqual(m1h1["m1h1_max_rel_l2_drift_delta3_q"], {"num": 1, "den": 20})
        roof = p3["hardware_roofline_comparison"]
        self.assertFalse(roof["rtx3080_8gib"]["full_resident_fits"])
        self.assertEqual(roof["rtx3080_8gib"]["full_resident_overflow_gb_q"], {"num": 12, "den": 1})
        self.assertTrue(roof["rtx3080_8gib"]["streaming_tier_feasible"])
        self.assertTrue(roof["workstation_32gib"]["full_resident_fits"])
        self.assertEqual(roof["qwen25_05b_bf16_vram_frac_of_8gib_q"], {"num": 247, "den": 2048})
        self.assertEqual(roof["qwen25_05b_bf16_vram_pct_dec"], "12.06")

        # Pillar 4: Provenance, Lean 4.36.0 & Law-4 novelty honesty
        p4 = p["pillar4_provenance_and_lean4"]
        self.assertEqual(p4["inkling_spec_count"], 2)
        self.assertEqual(p4["upstream_corpus_count"], 10)
        self.assertEqual(p4["lean4_certificate"]["theorem_count"], 20)
        self.assertEqual(p4["lean4_certificate"]["sha256"], s96.LEAN_FILE_SHA256)
        self.assertEqual(p4["novelty_honesty_law4"]["novelty_tier"], "N1")
        self.assertEqual(p4["novelty_honesty_law4"]["n2_claims"], 0)


class TestS96VerifierZoneBAndIO(unittest.TestCase):
    def test_json_tree_and_parser_hardening(self) -> None:
        ver.validate_json_tree_iterative({"a": [1, True, None, "ok", (1 << 2048) - 1]}, max_depth=256)
        ver.validate_json_tree_iterative(1, max_depth=1)
        ver.validate_json_tree_iterative([[1]], max_depth=2)
        for bad_depth in (0, 257, True):
            with self.assertRaises(s96.S96Error) as cd:
                ver.validate_json_tree_iterative({}, max_depth=bad_depth)  # type: ignore[arg-type]
            self.assertEqual(cd.exception.code, "INVALID_MAX_DEPTH")
        with self.assertRaises(s96.S96Error) as cdep:
            ver.validate_json_tree_iterative([[[1]]], max_depth=2)
        self.assertEqual(cdep.exception.code, "JSON_DEPTH_EXCEEDED")
        with self.assertRaises(s96.S96Error) as cnk:
            ver.validate_json_tree_iterative({1: "a"})
        self.assertEqual(cnk.exception.code, "NON_STR_KEY")
        with self.assertRaises(s96.S96Error) as csk:
            ver.validate_json_tree_iterative({"\ud800": "a"})
        self.assertEqual(csk.exception.code, "INVALID_UNICODE_STR")
        with self.assertRaises(s96.S96Error) as csv:
            ver.validate_json_tree_iterative({"a": "\ud800"})
        self.assertEqual(csv.exception.code, "INVALID_UNICODE_STR")
        with self.assertRaises(s96.S96Error) as cbi:
            ver.validate_json_tree_iterative(1 << 2048)
        self.assertEqual(cbi.exception.code, "INT_BIT_LIMIT")
        with self.assertRaises(s96.S96Error) as cft:
            ver.validate_json_tree_iterative((1, 2))
        self.assertEqual(cft.exception.code, "FORBIDDEN_JSON_TYPE")

        class IntSub(int):
            pass

        with self.assertRaises(s96.S96Error) as cis:
            ver.validate_json_tree_iterative(IntSub(5))
        self.assertEqual(cis.exception.code, "FORBIDDEN_JSON_TYPE")

        max_2048 = (1 << 2048) - 1
        self.assertEqual(len(str(max_2048)), ver.MAX_INT_DIGITS)
        self.assertEqual(ver._parse_capped_int_token(str(max_2048)), max_2048)
        with self.assertRaises(s96.S96Error) as tok_bit:
            ver._parse_capped_int_token(str(1 << 2048))
        self.assertEqual(tok_bit.exception.code, "INT_BIT_LIMIT")
        with self.assertRaises(s96.S96Error) as tok_dig:
            ver._parse_capped_int_token("9" * (ver.MAX_INT_DIGITS + 1))
        self.assertEqual(tok_dig.exception.code, "INT_DIGIT_LIMIT")

        self.assertEqual(ver.parse_strict_json('{"x":-42,"y":[true,null,"z"]}'), {"x": -42, "y": [True, None, "z"]})
        exact_max_json = '"' + ("a" * (ver.MAX_JSON_BYTES - 2)) + '"'
        self.assertEqual(len(ver.parse_strict_json(exact_max_json)), ver.MAX_JSON_BYTES - 2)
        with self.assertRaises(s96.S96Error) as cp1:
            ver.parse_strict_json(b"{}")  # type: ignore[arg-type]
        self.assertEqual(cp1.exception.code, "INVALID_JSON_TEXT")
        with self.assertRaises(s96.S96Error) as cp2:
            ver.parse_strict_json('"\ud800"')
        self.assertEqual(cp2.exception.code, "INVALID_UNICODE_STR")
        with self.assertRaises(s96.S96Error) as cp3:
            ver.parse_strict_json('"' + ("a" * (ver.MAX_JSON_BYTES + 1)) + '"')
        self.assertEqual(cp3.exception.code, "JSON_TOO_LARGE")
        with self.assertRaises(s96.S96Error) as cp4:
            ver.parse_strict_json('{"a":1,"\\u0061":2}')
        self.assertEqual(cp4.exception.code, "DUPLICATE_JSON_KEY")
        with self.assertRaises(s96.S96Error) as cp5:
            ver.parse_strict_json('{"a":1.0}')
        self.assertEqual(cp5.exception.code, "FLOAT_FORBIDDEN")
        with self.assertRaises(s96.S96Error) as cp6:
            ver.parse_strict_json('{"a":NaN}')
        self.assertEqual(cp6.exception.code, "NONFINITE_CONSTANT")
        with self.assertRaises(s96.S96Error) as cp7:
            ver.parse_strict_json('{"a":' + ("9" * 5001) + "}")
        self.assertEqual(cp7.exception.code, "INT_DIGIT_LIMIT")
        with self.assertRaises(s96.S96Error) as cp7b:
            ver.parse_strict_json('{"a":-' + ("9" * (ver.MAX_INT_DIGITS + 1)) + "}")
        self.assertEqual(cp7b.exception.code, "INT_DIGIT_LIMIT")
        with self.assertRaises(s96.S96Error) as cp8:
            ver.parse_strict_json('{"a":' + str(1 << 2048) + "}")
        self.assertEqual(cp8.exception.code, "INT_BIT_LIMIT")
        with self.assertRaises(s96.S96Error) as cp9:
            ver.parse_strict_json("{broken")
        self.assertEqual(cp9.exception.code, "JSON_DECODE_ERROR")
        with self.assertRaises(s96.S96Error) as cp10:
            ver.parse_strict_json("[" * 500 + "]" * 500)
        self.assertIn(cp10.exception.code, ("JSON_DEPTH_EXCEEDED", "JSON_DECODE_ERROR"))

    def test_digest_exact_equal_and_four_surfaces(self) -> None:
        good_h = "0123456789abcdef" * 4
        self.assertEqual(ver.require_sha256_hex(good_h, "h"), good_h)
        with self.assertRaises(s96.S96Error) as d1:
            ver.require_sha256_hex(123, "h")
        self.assertEqual(d1.exception.code, "INVALID_DIGEST_TYPE")
        with self.assertRaises(s96.S96Error) as d2:
            ver.require_sha256_hex("a" * 63, "h")
        self.assertEqual(d2.exception.code, "INVALID_DIGEST_LEN")
        with self.assertRaises(s96.S96Error) as d3:
            ver.require_sha256_hex("A" * 64, "h")
        self.assertEqual(d3.exception.code, "INVALID_DIGEST_HEX")
        with self.assertRaises(s96.S96Error) as d4:
            ver.require_sha256_hex("\u00e9" * 64, "h")
        self.assertEqual(d4.exception.code, "INVALID_DIGEST_HEX")

        self.assertTrue(ver.exact_typed_equal({"a": [1, True, None]}, {"a": [1, True, None]}))
        self.assertFalse(ver.exact_typed_equal(1, True))
        self.assertFalse(ver.exact_typed_equal({"a": 1}, {"a": 1, "b": 2}))
        self.assertFalse(ver.exact_typed_equal({"a": 1}, {"b": 1}))
        self.assertFalse(ver.exact_typed_equal([1, 2], [1]))
        self.assertFalse(ver.exact_typed_equal([1, 2], [1, 3]))
        self.assertFalse(ver.exact_typed_equal("x", "y"))

        cert = s96.build_certificate()
        self.assertEqual(ver.audit_certificate_object(cert)["certificate_sha256"], cert["certificate_sha256"])

        with self.assertRaises(s96.S96Error) as a0:
            ver.audit_certificate_object([1, 2])
        self.assertEqual(a0.exception.code, "NON_OBJECT_ROOT")
        c_keys = copy.deepcopy(cert)
        c_keys["extra"] = 1
        with self.assertRaises(s96.S96Error) as a1:
            ver.audit_certificate_object(c_keys)
        self.assertEqual(a1.exception.code, "BAD_CERT_KEYS")
        c_sch = copy.deepcopy(cert)
        c_sch["schema"] = "wrong"
        with self.assertRaises(s96.S96Error) as a2:
            ver.audit_certificate_object(c_sch)
        self.assertEqual(a2.exception.code, "BAD_SCHEMA")
        c_tid = copy.deepcopy(cert)
        c_tid["track_id"] = "wrong"
        with self.assertRaises(s96.S96Error) as a3:
            ver.audit_certificate_object(c_tid)
        self.assertEqual(a3.exception.code, "BAD_TRACK_ID")
        c_pt = copy.deepcopy(cert)
        c_pt["payload"] = []
        with self.assertRaises(s96.S96Error) as a4:
            ver.audit_certificate_object(c_pt)
        self.assertEqual(a4.exception.code, "BAD_PAYLOAD_TYPE")
        c_psha = copy.deepcopy(cert)
        c_psha["payload_sha256"] = "0" * 64
        with self.assertRaises(s96.S96Error) as a5:
            ver.audit_certificate_object(c_psha)
        self.assertEqual(a5.exception.code, "PAYLOAD_SHA_MISMATCH")
        c_csha = copy.deepcopy(cert)
        c_csha["certificate_sha256"] = "0" * 64
        with self.assertRaises(s96.S96Error) as a6:
            ver.audit_certificate_object(c_csha)
        self.assertEqual(a6.exception.code, "CERT_SHA_MISMATCH")

        # Direct verify_certificate_dict FR1/FR0 and secondary_audit_payload tests
        self.assertEqual(
            ver.verify_certificate_dict(cert, full_replay=False)["certificate_sha256"],
            cert["certificate_sha256"],
        )
        with self.assertRaises(s96.S96Error) as fr_bad:
            ver.verify_certificate_dict(cert, full_replay=1)  # type: ignore[arg-type]
        self.assertEqual(fr_bad.exception.code, "INVALID_FULL_REPLAY")
        self.assertIs(ver.secondary_audit_payload(cert["payload"]), cert["payload"])
        with self.assertRaises(s96.S96Error) as sec_nd:
            ver.secondary_audit_payload([1, 2])
        self.assertEqual(sec_nd.exception.code, "BAD_PAYLOAD_TYPE")

        # Strict rational dict rejections across audited _q fields + non-_q field (kills tree-walk BoolOp!)
        self.assertEqual(ver._parse_rat_dict({"num": -3, "den": 2}), Fraction(-3, 2))
        for bad_rat in (
            123,
            {"num": 0, "den": 0, "extra": 1},
            {"num": 0, "other": 1},
            {"other": 0, "den": 1},
            {"num": True, "den": 1},
            {"num": 1, "den": True},
            {"num": 1, "den": 0},
            {"num": 1, "den": -1},
            {"num": 4, "den": 2},
        ):
            with self.assertRaises(s96.S96Error) as e_rat:
                ver._parse_rat_dict(bad_rat)
            self.assertEqual(e_rat.exception.code, "BAD_RATIONAL_DICT")
            c_rat = copy.deepcopy(cert)
            c_rat["payload"]["pillar1_lora_three_bottlenecks"]["privileged_basis_commutator"]["anisotropic_comm_frob_sq_q"] = bad_rat
            for surface_fn in (
                lambda c: ver.secondary_audit_payload(c["payload"]),
                lambda c: ver.verify_certificate_dict(_resign(c), full_replay=False),
                lambda c: ver.verify_certificate_dict(_resign(c), full_replay=True),
            ):
                with self.assertRaises(s96.S96Error) as e_r2:
                    surface_fn(c_rat)
                self.assertIn(e_r2.exception.code, ("BAD_RATIONAL_DICT", "UNEXPECTED_BOOL_FIELD"))
        for bad_half_rat in ({"num": 0, "other": 1}, {"other": 0, "den": 1}):
            c_hr = copy.deepcopy(cert)
            c_hr["payload"]["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"]["vocab_size"] = bad_half_rat
            with self.assertRaises(s96.S96Error) as e_hr:
                ver.secondary_audit_payload(c_hr["payload"])
            self.assertEqual(e_hr.exception.code, "BAD_RATIONAL_DICT")

        c_bool_fld = copy.deepcopy(cert)
        c_bool_fld["payload"]["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"]["vocab_size"] = True
        with self.assertRaises(s96.S96Error) as a7f:
            ver.secondary_audit_payload(c_bool_fld["payload"])
        self.assertEqual(a7f.exception.code, "UNEXPECTED_BOOL_FIELD")
        c_bool_lst = copy.deepcopy(cert)
        c_bool_lst["payload"]["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"]["mtp_target_layer_ids"][0] = True
        with self.assertRaises(s96.S96Error) as a7l:
            ver.secondary_audit_payload(c_bool_lst["payload"])
        self.assertEqual(a7l.exception.code, "UNEXPECTED_BOOL_ITEM")
        c_bad_pin = copy.deepcopy(cert)
        c_bad_pin["payload"]["pillar4_provenance_and_lean4"]["upstream_cert_manifest"][0]["sha256"] = "Z" * 64
        with self.assertRaises(s96.S96Error) as a7s:
            ver.secondary_audit_payload(c_bad_pin["payload"])
        self.assertEqual(a7s.exception.code, "INVALID_DIGEST_HEX")

        with self.assertRaises(s96.S96Error):
            ver._req_int("not_int", "BAD_INT")
        with self.assertRaises(s96.S96Error):
            ver._req_dict([], frozenset({"a"}), "BAD_D")
        with self.assertRaises(s96.S96Error):
            ver._req_dict({"b": 1}, frozenset({"a"}), "BAD_D")

        # Direct boundary unit probes on _audit_* helpers (consistent states kill every guard uniquely!)
        ver._audit_lora_metric(s96.lora_rank_and_gauge_metrics(1, 1, 1), False)
        bad_r0 = {
            "m": 1,
            "n": 1,
            "rank": 0,
            "p_raw": 0,
            "d_eff": 0,
            "eta_alg_q": {"num": 0, "den": 1},
            "unreachable_dim": 1,
            "unreachable_frac_q": {"num": 1, "den": 1},
            "unreachable_pct_dec": "100.00",
            "rank_starved": True,
        }
        with self.assertRaises(s96.S96Error) as e_r0:
            ver._audit_lora_metric(bad_r0, True)
        self.assertEqual(e_r0.exception.code, "BAD_LORA_INV")
        bad_rhi = {
            "m": 1,
            "n": 1,
            "rank": 2,
            "p_raw": 4,
            "d_eff": 0,
            "eta_alg_q": {"num": 0, "den": 1},
            "unreachable_dim": -1,
            "unreachable_frac_q": {"num": -1, "den": 1},
            "unreachable_pct_dec": "-100.00",
            "rank_starved": False,
        }
        with self.assertRaises(s96.S96Error) as e_rhi:
            ver._audit_lora_metric(bad_rhi, False)
        self.assertEqual(e_rhi.exception.code, "BAD_LORA_INV")
        bad_praw = copy.deepcopy(cert["payload"]["pillar1_lora_three_bottlenecks"]["qwen25_05b_r16_starvation"])
        bad_praw.update({"p_raw": 1000, "d_eff": 744, "eta_alg_q": {"num": 93, "den": 125}})
        with self.assertRaises(s96.S96Error) as e_praw:
            ver._audit_lora_metric(bad_praw, True)
        self.assertEqual(e_praw.exception.code, "BAD_LORA_INV")

        ns_unit = copy.deepcopy(cert["payload"]["pillar2_beyond_lora_architectures"]["nullspace_projected_antiforgetting"]["law5_full_rank_saturation_control"])
        ns_unit["dim"] = 1
        ns_unit["base_rank"] = 1
        ns_unit["nullspace_dim"] = 0
        ver._audit_nullspace_entry(ns_unit, True)
        ns_zero = copy.deepcopy(ns_unit)
        ns_zero["dim"] = 0
        ns_zero["base_rank"] = 0
        with self.assertRaises(s96.S96Error) as e_ns0:
            ver._audit_nullspace_entry(ns_zero, True)
        self.assertEqual(e_ns0.exception.code, "BAD_NS_INV")
        # AUDIT-196 F04: negative base_rank with inflated nullspace_dim
        ns_neg = copy.deepcopy(cert["payload"]["pillar2_beyond_lora_architectures"]["nullspace_projected_antiforgetting"]["rank2_calibration_projection"])
        ns_neg["base_rank"] = -10
        ns_neg["nullspace_dim"] = 14
        with self.assertRaises(s96.S96Error) as e_nsneg:
            ver._audit_nullspace_entry(ns_neg, False)
        self.assertEqual(e_nsneg.exception.code, "BAD_NS_INV")
        ns_over = copy.deepcopy(ns_unit)
        ns_over["dim"] = 4
        ns_over["base_rank"] = 5
        ns_over["nullspace_dim"] = -1
        with self.assertRaises(s96.S96Error) as e_nsover:
            ver._audit_nullspace_entry(ns_over, False)
        self.assertEqual(e_nsover.exception.code, "BAD_NS_INV")

        rf_eq = s96.eval_hardware_roofline(
            model_gb_q=Fraction(8),
            gpu_vram_gb_q=Fraction(8),
            host_ram_gb_q=Fraction(31),
            shared_gb_q=Fraction(2),
            hot_experts_gb_q=Fraction(4),
            cold_experts_gb_q=Fraction(4),
            kv_headroom_gb_q=Fraction(2),
        )
        ver._audit_roofline_entry(rf_eq, True)
        rf_min = s96.eval_hardware_roofline(
            model_gb_q=Fraction(1),
            gpu_vram_gb_q=Fraction(1),
            host_ram_gb_q=Fraction(1),
            shared_gb_q=Fraction(1, 4),
            hot_experts_gb_q=Fraction(1, 2),
            cold_experts_gb_q=Fraction(1, 2),
            kv_headroom_gb_q=Fraction(1, 4),
        )
        ver._audit_roofline_entry(rf_min, True)
        rf_mod0 = copy.deepcopy(rf_eq)
        rf_mod0.update(
            {
                "model_gb_q": {"num": 0, "den": 1},
                "model_over_vram_ratio_q": {"num": 0, "den": 1},
                "full_resident_overflow_gb_q": {"num": 0, "den": 1},
            }
        )
        with self.assertRaises(s96.S96Error) as e_rm0:
            ver._audit_roofline_entry(rf_mod0, True)
        self.assertEqual(e_rm0.exception.code, "BAD_ROOF_INV")
        rf_vram0 = copy.deepcopy(rf_eq)
        rf_vram0["gpu_vram_gb_q"] = {"num": 0, "den": 1}
        with self.assertRaises(s96.S96Error) as e_rv0:
            ver._audit_roofline_entry(rf_vram0, True)
        self.assertEqual(e_rv0.exception.code, "BAD_ROOF_INV")
        for bad_sv in ({"num": -999, "den": 1}, {"num": 0, "den": 1}, {"num": 9, "den": 1}):
            rf_sv = copy.deepcopy(rf_eq)
            rf_sv["streamed_vram_gb_q"] = bad_sv
            with self.assertRaises(s96.S96Error) as e_sv:
                ver._audit_roofline_entry(rf_sv, True)
            self.assertEqual(e_sv.exception.code, "BAD_ROOF_INV")
        for bad_cold in ({"num": 0, "den": 1}, {"num": 8, "den": 1}, {"num": 1000, "den": 1}):
            rf_c0 = copy.deepcopy(rf_eq)
            rf_c0["cold_experts_gb_q"] = bad_cold
            with self.assertRaises(s96.S96Error) as e_c0:
                ver._audit_roofline_entry(rf_c0, True)
            self.assertEqual(e_c0.exception.code, "BAD_ROOF_INV")

        # Direct zero-denominator & strict-type boundary probes on _audit_pillar1..3
        p1_l0 = copy.deepcopy(cert["payload"]["pillar1_lora_three_bottlenecks"])
        p1_l0["s78_fig7_unit_conservation"]["learning_kb_q"] = {"num": 0, "den": 1}
        with self.assertRaises(s96.S96Error) as e_p1l0:
            ver._audit_pillar1(p1_l0)
        self.assertEqual(e_p1l0.exception.code, "BAD_P1_INV")

        for p2_patch in (
            lambda p2: p2["matched_budget_blockh4_butterfly"].__setitem__("matched_lora_rank", 0),
            lambda p2: p2["matched_budget_blockh4_butterfly"].__setitem__("standard_lora_rank", 0),
            lambda p2: p2["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("bf16_half_ulp_zero_frac_lora_q", {"num": 0, "den": 1}),
            lambda p2: p2["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("butterflyhead_head_lr_q", {"num": 0, "den": 1}),
            lambda p2: p2["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("s104_kronecker_rank2_head_params", 0),
        ):
            p2_z = copy.deepcopy(cert["payload"]["pillar2_beyond_lora_architectures"])
            p2_patch(p2_z)
            with self.assertRaises(s96.S96Error) as e_p2z:
                ver._audit_pillar2(p2_z)
            self.assertEqual(e_p2z.exception.code, "BAD_P2_INV")

        class ListSub(list):
            pass

        class IntSub2(int):
            pass

        for bad_cfg_patch in (
            {"hidden_size": 0},
            {"sqrt_hidden_size": 0},
            {"num_hidden_layers": 0},
            {"n_routed_experts": 0},
            {"num_passes": 0},
            {"num_passes": 4},
            {"readme_physical_active_b_q": {"num": 0, "den": 1}},
            {"mtp_target_layer_ids": (5, 23, 41, 48)},
            {"mtp_target_layer_ids": ListSub([5, 23, 41, 48])},
            {"mtp_target_layer_ids": [IntSub2(5), 23, 41, 48]},
            {"mtp_target_layer_ids": [5, 23, 41]},
        ):
            p3_bad = copy.deepcopy(cert["payload"]["pillar3_inkling2_loop_and_roofline"])
            p3_bad["inkling2_config_exact"].update(bad_cfg_patch)
            with self.assertRaises(s96.S96Error) as e_p3b:
                ver._audit_pillar3(p3_bad)
            self.assertEqual(e_p3b.exception.code, "BAD_P3_INV")
        for bad_amp_patch in (
            {"s76_contractive_rho_q": {"num": 0, "den": 1}},
            {"s76_3pass_error_bound_q": {"num": 0, "den": 1}},
        ):
            p3_ba = copy.deepcopy(cert["payload"]["pillar3_inkling2_loop_and_roofline"])
            p3_ba["loop_core_adapter_amplification"].update(bad_amp_patch)
            with self.assertRaises(s96.S96Error) as e_p3a:
                ver._audit_pillar3(p3_ba)
            self.assertEqual(e_p3a.exception.code, "BAD_P3_INV")

        # Comprehensive live re-signed semantic tampers: ALL MUST FAIL across SEC, FR0, AND FR1!
        semantic_tampers: list[tuple[str, Any, str]] = [
            (
                "empty_pillars_1_to_3",
                lambda d: d.update(
                    {
                        "pillar1_lora_three_bottlenecks": {},
                        "pillar2_beyond_lora_architectures": {},
                        "pillar3_inkling2_loop_and_roofline": {},
                    }
                ),
                "BAD_P1_SCHEMA",
            ),
            ("p1_verified_false", lambda d: d["pillar1_lora_three_bottlenecks"].__setitem__("pillar_verified", False), "BAD_P1_INV"),
            ("p1_qwen_m_drift", lambda d: d["pillar1_lora_three_bottlenecks"].__setitem__("qwen25_05b_r16_starvation", s96.lora_rank_and_gauge_metrics(900, 896, 16)), "BAD_P1_INV"),
            ("p1_qwen_n_drift", lambda d: d["pillar1_lora_three_bottlenecks"].__setitem__("qwen25_05b_r16_starvation", s96.lora_rank_and_gauge_metrics(896, 900, 16)), "BAD_P1_INV"),
            ("p1_qwen_r_drift", lambda d: d["pillar1_lora_three_bottlenecks"].__setitem__("qwen25_05b_r16_starvation", s96.lora_rank_and_gauge_metrics(896, 896, 32)), "BAD_P1_INV"),
            ("p1_f3_m_drift", lambda d: d["pillar1_lora_three_bottlenecks"].__setitem__("s78_fig3_vproj_r128", s96.lora_rank_and_gauge_metrics(516, 1024, 128)), "BAD_P1_INV"),
            ("p1_f3_n_drift", lambda d: d["pillar1_lora_three_bottlenecks"].__setitem__("s78_fig3_vproj_r128", s96.lora_rank_and_gauge_metrics(512, 1028, 128)), "BAD_P1_INV"),
            ("p1_f3_r_drift", lambda d: d["pillar1_lora_three_bottlenecks"].__setitem__("s78_fig3_vproj_r128", s96.lora_rank_and_gauge_metrics(512, 1024, 64)), "BAD_P1_INV"),
            ("p1_full_m_drift", lambda d: d["pillar1_lora_three_bottlenecks"].__setitem__("s78_full_rank_r512", s96.lora_rank_and_gauge_metrics(256, 1024, 256)), "BAD_P1_INV"),
            ("p1_full_n_drift", lambda d: d["pillar1_lora_three_bottlenecks"].__setitem__("s78_full_rank_r512", s96.lora_rank_and_gauge_metrics(512, 512, 512)), "BAD_P1_INV"),
            ("p1_full_r_drift", lambda d: d["pillar1_lora_three_bottlenecks"].__setitem__("s78_full_rank_r512", s96.lora_rank_and_gauge_metrics(512, 1024, 256)), "BAD_LORA_INV"),
            ("p1_p_raw_bad", lambda d: d["pillar1_lora_three_bottlenecks"]["qwen25_05b_r16_starvation"].__setitem__("p_raw", 1), "BAD_LORA_INV"),
            ("p1_d_eff_bad", lambda d: d["pillar1_lora_three_bottlenecks"]["qwen25_05b_r16_starvation"].__setitem__("d_eff", 1), "BAD_LORA_INV"),
            ("p1_eta_bad", lambda d: d["pillar1_lora_three_bottlenecks"]["qwen25_05b_r16_starvation"].__setitem__("eta_alg_q", {"num": 1, "den": 2}), "BAD_LORA_INV"),
            ("p1_unr_bad", lambda d: d["pillar1_lora_three_bottlenecks"]["qwen25_05b_r16_starvation"].__setitem__("unreachable_dim", 1), "BAD_LORA_INV"),
            ("p1_ufrac_bad", lambda d: d["pillar1_lora_three_bottlenecks"]["qwen25_05b_r16_starvation"].__setitem__("unreachable_frac_q", {"num": 1, "den": 2}), "BAD_LORA_INV"),
            ("p1_upct_bad", lambda d: d["pillar1_lora_three_bottlenecks"]["qwen25_05b_r16_starvation"].__setitem__("unreachable_pct_dec", "GARBAGE"), "BAD_LORA_INV"),
            ("p1_starved_bad", lambda d: d["pillar1_lora_three_bottlenecks"]["qwen25_05b_r16_starvation"].__setitem__("rank_starved", False), "BAD_LORA_INV"),
            ("p1_comm_aniso_f09", lambda d: d["pillar1_lora_three_bottlenecks"]["privileged_basis_commutator"].__setitem__("anisotropic_comm_frob_sq_q", {"num": 1, "den": 1}), "BAD_P1_INV"),
            ("p1_comm_iso_nonzero", lambda d: d["pillar1_lora_three_bottlenecks"]["privileged_basis_commutator"].__setitem__("isotropic_comm_frob_sq_q", {"num": 1, "den": 1}), "BAD_P1_INV"),
            ("p1_comm_flag1", lambda d: d["pillar1_lora_three_bottlenecks"]["privileged_basis_commutator"].__setitem__("commutator_nonzero_under_anisotropy", False), "BAD_P1_INV"),
            ("p1_comm_flag2", lambda d: d["pillar1_lora_three_bottlenecks"]["privileged_basis_commutator"].__setitem__("commutator_zero_under_isotropy", False), "BAD_P1_INV"),
            ("p1_cons_f10", lambda d: d["pillar1_lora_three_bottlenecks"]["s78_fig7_unit_conservation"].update({"forgetting_kb_q": {"num": 1, "den": 1}, "learning_kb_q": {"num": 1, "den": 1}}), "BAD_P1_INV"),
            ("p1_cons_f_neq_l", lambda d: d["pillar1_lora_three_bottlenecks"]["s78_fig7_unit_conservation"].update({"forgetting_kb_q": {"num": 458, "den": 5}, "forgetting_over_learning_q": {"num": 2, "den": 1}}), "BAD_P1_INV"),
            ("p1_cons_ratio_bad", lambda d: d["pillar1_lora_three_bottlenecks"]["s78_fig7_unit_conservation"].__setitem__("forgetting_over_learning_q", {"num": 2, "den": 1}), "BAD_P1_INV"),
            ("p1_cons_flag", lambda d: d["pillar1_lora_three_bottlenecks"]["s78_fig7_unit_conservation"].__setitem__("unit_conservation_exact", False), "BAD_P1_INV"),
            ("p2_verified_false", lambda d: d["pillar2_beyond_lora_architectures"].__setitem__("pillar_verified", False), "BAD_P2_INV"),
            ("p2_bf_dim_drift", lambda d: d["pillar2_beyond_lora_architectures"]["matched_budget_blockh4_butterfly"].update({"dim": 4, "matched_param_budget": 16, "butterfly_rank": 4, "butterfly_interleaved_rank": 4, "full_rank_advantage_q": {"num": 2, "den": 1}}), "BAD_P2_INV"),
            ("p2_bf_budget", lambda d: d["pillar2_beyond_lora_architectures"]["matched_budget_blockh4_butterfly"].__setitem__("matched_param_budget", 99), "BAD_P2_INV"),
            ("p2_bf_rlora", lambda d: d["pillar2_beyond_lora_architectures"]["matched_budget_blockh4_butterfly"].__setitem__("standard_lora_rank", 1), "BAD_P2_INV"),
            ("p2_bf_rbf", lambda d: d["pillar2_beyond_lora_architectures"]["matched_budget_blockh4_butterfly"].__setitem__("butterfly_rank", 4), "BAD_P2_INV"),
            ("p2_bf_rmix", lambda d: d["pillar2_beyond_lora_architectures"]["matched_budget_blockh4_butterfly"].__setitem__("butterfly_interleaved_rank", 4), "BAD_P2_INV"),
            ("p2_bf_eq_rank", lambda d: d["pillar2_beyond_lora_architectures"]["matched_budget_blockh4_butterfly"].update({"matched_lora_rank": 8, "standard_lora_rank": 8, "matched_param_budget": 128, "full_rank_advantage_q": {"num": 1, "den": 1}}), "BAD_P2_INV"),
            ("p2_bf_adv", lambda d: d["pillar2_beyond_lora_architectures"]["matched_budget_blockh4_butterfly"].__setitem__("full_rank_advantage_q", {"num": 2, "den": 1}), "BAD_P2_INV"),
            ("p2_bf_orth", lambda d: d["pillar2_beyond_lora_architectures"]["matched_budget_blockh4_butterfly"].__setitem__("blockh4_exact_orthogonal", False), "BAD_P2_INV"),
            ("p2_bf_unp", lambda d: d["pillar2_beyond_lora_architectures"]["matched_budget_blockh4_butterfly"].__setitem__("law5_unpermuted_cross_block_sq_q", {"num": 1, "den": 1}), "BAD_P2_INV"),
            ("p2_bf_mix_f11", lambda d: d["pillar2_beyond_lora_architectures"]["matched_budget_blockh4_butterfly"].__setitem__("interleaved_cross_block_sq_q", {"num": 1, "den": 1}), "BAD_P2_INV"),
            ("p2_bf_f1", lambda d: d["pillar2_beyond_lora_architectures"]["matched_budget_blockh4_butterfly"].__setitem__("law5_locality_obstruction_verified", False), "BAD_P2_INV"),
            ("p2_bf_f2", lambda d: d["pillar2_beyond_lora_architectures"]["matched_budget_blockh4_butterfly"].__setitem__("interleave_restores_mixing", False), "BAD_P2_INV"),
            ("p2_hh_s42", lambda d: d["pillar2_beyond_lora_architectures"]["privsparse_householder_isometry"].__setitem__("s42_fisher_waterfilling_gain_q", {"num": 1, "den": 1}), "BAD_P2_INV"),
            ("p2_hh_dim", lambda d: d["pillar2_beyond_lora_architectures"]["privsparse_householder_isometry"].__setitem__("householder_dim", 2), "BAD_P2_INV"),
            ("p2_hh_det", lambda d: d["pillar2_beyond_lora_architectures"]["privsparse_householder_isometry"].__setitem__("householder_det_q", {"num": 1, "den": 1}), "BAD_P2_INV"),
            ("p2_hh_orth", lambda d: d["pillar2_beyond_lora_architectures"]["privsparse_householder_isometry"].__setitem__("householder_exact_orthogonal", False), "BAD_P2_INV"),
            ("p2_hh_inv", lambda d: d["pillar2_beyond_lora_architectures"]["privsparse_householder_isometry"].__setitem__("householder_exact_involutive", False), "BAD_P2_INV"),
            ("p2_hh_norm_f12", lambda d: d["pillar2_beyond_lora_architectures"]["privsparse_householder_isometry"].update({"probe_norm_sq_before_q": {"num": 1, "den": 1}, "probe_norm_sq_after_q": {"num": 1, "den": 1}}), "BAD_P2_INV"),
            ("p2_hh_norm", lambda d: d["pillar2_beyond_lora_architectures"]["privsparse_householder_isometry"].__setitem__("probe_norm_sq_after_q", {"num": 31, "den": 1}), "BAD_P2_INV"),
            ("p2_hh_k2", lambda d: d["pillar2_beyond_lora_architectures"]["privsparse_householder_isometry"].__setitem__("householder_kappa2_q", {"num": 2, "den": 1}), "BAD_P2_INV"),
            ("p2_hh_sh", lambda d: d["pillar2_beyond_lora_architectures"]["privsparse_householder_isometry"].__setitem__("s82_shear_kappa2_lower_q", {"num": 2, "den": 1}), "BAD_P2_INV"),
            ("p2_hh_cure", lambda d: d["pillar2_beyond_lora_architectures"]["privsparse_householder_isometry"].__setitem__("cures_s82_shear_blowup", False), "BAD_P2_INV"),
            ("p2_ns_dim_f14", lambda d: d["pillar2_beyond_lora_architectures"]["nullspace_projected_antiforgetting"]["rank2_calibration_projection"].update({"dim": 6, "nullspace_dim": 4}), "BAD_NS_INV"),
            ("p2_ns_br_f14", lambda d: d["pillar2_beyond_lora_architectures"]["nullspace_projected_antiforgetting"]["rank2_calibration_projection"].update({"base_rank": 1, "nullspace_dim": 3}), "BAD_NS_INV"),
            ("p2_ns_dim", lambda d: d["pillar2_beyond_lora_architectures"]["nullspace_projected_antiforgetting"]["rank2_calibration_projection"].__setitem__("nullspace_dim", 1), "BAD_NS_INV"),
            ("p2_ns_rawf_f13", lambda d: d["pillar2_beyond_lora_architectures"]["nullspace_projected_antiforgetting"]["rank2_calibration_projection"].__setitem__("raw_forgetting_sq_q", {"num": 1, "den": 1}), "BAD_NS_INV"),
            ("p2_ns_projf", lambda d: d["pillar2_beyond_lora_architectures"]["nullspace_projected_antiforgetting"]["rank2_calibration_projection"].__setitem__("projected_forgetting_sq_q", {"num": 1, "den": 1}), "BAD_NS_INV"),
            ("p2_ns_zf", lambda d: d["pillar2_beyond_lora_architectures"]["nullspace_projected_antiforgetting"]["rank2_calibration_projection"].__setitem__("exact_zero_forgetting", False), "BAD_NS_INV"),
            ("p2_ns_satf", lambda d: d["pillar2_beyond_lora_architectures"]["nullspace_projected_antiforgetting"]["rank2_calibration_projection"].__setitem__("nullspace_saturated", True), "BAD_NS_INV"),
            ("p2_ns_pe_f13", lambda d: d["pillar2_beyond_lora_architectures"]["nullspace_projected_antiforgetting"]["rank2_calibration_projection"].__setitem__("projected_update_energy_sq_q", {"num": 999999, "den": 1}), "BAD_NS_INV"),
            ("p2_ns_sat_dim", lambda d: d["pillar2_beyond_lora_architectures"]["nullspace_projected_antiforgetting"]["law5_full_rank_saturation_control"].update({"dim": 2, "base_rank": 2}), "BAD_NS_INV"),
            ("p2_ns_sat_br", lambda d: d["pillar2_beyond_lora_architectures"]["nullspace_projected_antiforgetting"]["law5_full_rank_saturation_control"].update({"base_rank": 3, "nullspace_dim": 1}), "BAD_NS_INV"),
            ("p2_ns_sat_rawf", lambda d: d["pillar2_beyond_lora_architectures"]["nullspace_projected_antiforgetting"]["law5_full_rank_saturation_control"].__setitem__("raw_forgetting_sq_q", {"num": 1, "den": 1}), "BAD_NS_INV"),
            ("p2_ns_sat_pe1", lambda d: d["pillar2_beyond_lora_architectures"]["nullspace_projected_antiforgetting"]["law5_full_rank_saturation_control"].__setitem__("projected_update_energy_sq_q", {"num": 1, "den": 1}), "BAD_NS_INV"),
            ("p2_hyb_ulp", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("bf16_half_ulp_threshold_q", {"num": 1, "den": 128}), "BAD_P2_INV"),
            ("p2_hyb_bfz", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("bf16_half_ulp_zero_frac_butterfly_q", {"num": 1, "den": 2}), "BAD_P2_INV"),
            ("p2_hyb_lrz", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("bf16_half_ulp_zero_frac_lora_q", {"num": 1, "den": 10}), "BAD_P2_INV"),
            ("p2_hyb_ann", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("bf16_annihilation_ratio_q", {"num": 9, "den": 1}), "BAD_P2_INV"),
            ("p2_hyb_anndec", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("bf16_annihilation_ratio_dec", "9.0000"), "BAD_P2_INV"),
            ("p2_hyb_d", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("butterflyhead_proj_dim", 512), "BAD_P2_INV"),
            ("p2_hyb_s", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("butterflyhead_stages_s", 4), "BAD_P2_INV"),
            ("p2_hyb_r", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("butterflyhead_rank_r", 4), "BAD_P2_INV"),
            ("p2_hyb_bp", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("butterflyhead_bfly_params", 1), "BAD_P2_INV"),
            ("p2_hyb_hp", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("butterflyhead_head_params", 1), "BAD_P2_INV"),
            ("p2_hyb_tp", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("butterflyhead_total_params_per_proj", 1), "BAD_P2_INV"),
            ("p2_hyb_nk", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("butterflyhead_nullspace_top_k", 16), "BAD_P2_INV"),
            ("p2_hyb_fc", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("butterflyhead_frob_cap_frac_q", {"num": 1, "den": 25}), "BAD_P2_INV"),
            ("p2_hyb_hlr", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("butterflyhead_head_lr_q", {"num": 1, "den": 1000}), "BAD_P2_INV"),
            ("p2_hyb_blr", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("butterflyhead_bfly_lr_q", {"num": 1, "den": 100}), "BAD_P2_INV"),
            ("p2_hyb_lrr", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("butterflyhead_lr_ratio_q", {"num": 5, "den": 1}), "BAD_P2_INV"),
            ("p2_hyb_kp", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("s104_kronecker_rank2_head_params", 3600), "BAD_P2_INV"),
            ("p2_hyb_kcr", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("s104_kronecker_compression_ratio_q", {"num": 4, "den": 1}), "BAD_P2_INV"),
            ("p2_hyb_pmin", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("pass_exact_all5_min_q", {"num": 1, "den": 2}), "BAD_P2_INV"),
            ("p2_hyb_kmax", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("kill_exact_all5_max_q", {"num": 1, "den": 2}), "BAD_P2_INV"),
            ("p2_hyb_nll", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("pass_nll_retention_ratio_cap_q", {"num": 3, "den": 1}), "BAD_P2_INV"),
            ("p2_hyb_zf", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("pass_bf16_zero_frac_cap_q", {"num": 1, "den": 2}), "BAD_P2_INV"),
            ("p2_hyb_t16", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("pass_top16_energy_cap_q", {"num": 4, "den": 5}), "BAD_P2_INV"),
            ("p2_hyb_sig", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("pass_sigma_max_cap_q", {"num": 1, "den": 2}), "BAD_P2_INV"),
            ("p2_hyb_rf", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("pass_rel_frob_cap_q", {"num": 1, "den": 20}), "BAD_P2_INV"),
            ("p2_hyb_vram", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("pass_peak_vram_cap_mib", 8192), "BAD_P2_INV"),
            ("p2_hyb_par", lambda d: d["pillar2_beyond_lora_architectures"]["s95_bf16_ulp_diagnosis_and_hybrid_prereg"].__setitem__("exact_budget_parity_verified", False), "BAD_P2_INV"),
            ("p3_verified_false", lambda d: d["pillar3_inkling2_loop_and_roofline"].__setitem__("pillar_verified", False), "BAD_P3_INV"),
            ("p3_r3080_mod", lambda d: d["pillar3_inkling2_loop_and_roofline"]["hardware_roofline_comparison"]["rtx3080_8gib"].update({"model_gb_q": {"num": 24, "den": 1}, "full_resident_overflow_gb_q": {"num": 16, "den": 1}, "model_over_vram_ratio_q": {"num": 3, "den": 1}}), "BAD_ROOF_INV"),
            ("p3_r3080_vram", lambda d: d["pillar3_inkling2_loop_and_roofline"]["hardware_roofline_comparison"]["rtx3080_8gib"].update({"gpu_vram_gb_q": {"num": 10, "den": 1}, "full_resident_overflow_gb_q": {"num": 10, "den": 1}, "model_over_vram_ratio_q": {"num": 2, "den": 1}}), "BAD_ROOF_INV"),
            ("p3_r3080_svram_f01", lambda d: d["pillar3_inkling2_loop_and_roofline"]["hardware_roofline_comparison"]["rtx3080_8gib"].__setitem__("streamed_vram_gb_q", {"num": 7, "den": 1}), "BAD_ROOF_INV"),
            ("p3_r3080_cold_f03", lambda d: d["pillar3_inkling2_loop_and_roofline"]["hardware_roofline_comparison"]["rtx3080_8gib"].__setitem__("cold_experts_gb_q", {"num": 12, "den": 1}), "BAD_ROOF_INV"),
            ("p3_w32_mod", lambda d: d["pillar3_inkling2_loop_and_roofline"]["hardware_roofline_comparison"]["workstation_32gib"].update({"model_gb_q": {"num": 16, "den": 1}, "model_over_vram_ratio_q": {"num": 1, "den": 2}}), "BAD_ROOF_INV"),
            ("p3_w32_vram", lambda d: d["pillar3_inkling2_loop_and_roofline"]["hardware_roofline_comparison"]["workstation_32gib"].update({"gpu_vram_gb_q": {"num": 40, "den": 1}, "model_over_vram_ratio_q": {"num": 1, "den": 2}}), "BAD_ROOF_INV"),
            ("p3_w32_svram", lambda d: d["pillar3_inkling2_loop_and_roofline"]["hardware_roofline_comparison"]["workstation_32gib"].__setitem__("streamed_vram_gb_q", {"num": 7, "den": 1}), "BAD_ROOF_INV"),
            ("p3_w32_cold", lambda d: d["pillar3_inkling2_loop_and_roofline"]["hardware_roofline_comparison"]["workstation_32gib"].__setitem__("cold_experts_gb_q", {"num": 12, "den": 1}), "BAD_ROOF_INV"),
            ("p3_roof_rat", lambda d: d["pillar3_inkling2_loop_and_roofline"]["hardware_roofline_comparison"]["rtx3080_8gib"].__setitem__("model_over_vram_ratio_q", {"num": 1, "den": 1}), "BAD_ROOF_INV"),
            ("p3_roof_fit", lambda d: d["pillar3_inkling2_loop_and_roofline"]["hardware_roofline_comparison"]["rtx3080_8gib"].__setitem__("full_resident_fits", True), "BAD_ROOF_INV"),
            ("p3_roof_ovf", lambda d: d["pillar3_inkling2_loop_and_roofline"]["hardware_roofline_comparison"]["rtx3080_8gib"].__setitem__("full_resident_overflow_gb_q", {"num": 0, "den": 1}), "BAD_ROOF_INV"),
            ("p3_roof_sfg", lambda d: d["pillar3_inkling2_loop_and_roofline"]["hardware_roofline_comparison"]["rtx3080_8gib"].__setitem__("streamed_fits_gpu", False), "BAD_ROOF_INV"),
            ("p3_roof_cfr", lambda d: d["pillar3_inkling2_loop_and_roofline"]["hardware_roofline_comparison"]["rtx3080_8gib"].__setitem__("cold_fits_host_ram", False), "BAD_ROOF_INV"),
            ("p3_roof_stf", lambda d: d["pillar3_inkling2_loop_and_roofline"]["hardware_roofline_comparison"]["rtx3080_8gib"].__setitem__("streaming_tier_feasible", False), "BAD_ROOF_INV"),
            ("p3_sh_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("sqrt_hidden_size", 47), "BAD_P3_INV"),
            ("p3_vs_f17", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("vocab_size", 201025), "BAD_P3_INV"),
            ("p3_uvs_f17", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("unpadded_vocab_size", 200059), "BAD_P3_INV"),
            ("p3_nah_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("num_attention_heads", 16), "BAD_P3_INV"),
            ("p3_nkv_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("num_key_value_heads", 4), "BAD_P3_INV"),
            ("p3_hd_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("head_dim", 64), "BAD_P3_INV"),
            ("p3_glc_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("global_layer_count", 5), "BAD_P3_INV"),
            ("p3_llc_sum", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].update({"local_layer_count": 19, "global_layer_count": 5}), "BAD_P3_INV"),
            ("p3_sws_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("sliding_window_size", 512), "BAD_P3_INV"),
            ("p3_ea_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].update({"num_experts_per_tok": 4, "active_expert_frac_q": {"num": 1, "den": 32}}), "BAD_P3_INV"),
            ("p3_inter_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].update({"intermediate_size": 576, "intermediate_over_hidden_q": {"num": 1, "den": 4}}), "BAD_P3_INV"),
            ("p3_mgs_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("mlp_gate_softcap", 5), "BAD_P3_INV"),
            ("p3_mus_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("mlp_up_softcap", 26), "BAD_P3_INV"),
            ("p3_rs_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("route_scale", 9), "BAD_P3_INV"),
            ("p3_cs_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].update({"core_start": 5, "core_layers": 13}), "BAD_P3_INV"),
            ("p3_ce_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].update({"core_end": 19, "core_layers": 13}), "BAD_P3_INV"),
            ("p3_gr_bad_pin", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].update({"gate_rank": 32, "gate_rank_over_sqrt_hidden_q": {"num": 2, "den": 3}}), "BAD_P3_INV"),
            ("p3_mtp_bs", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("mtp_block_size", 4), "BAD_P3_INV"),
            ("p3_mtp_mr", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("mtp_markov_rank", 128), "BAD_P3_INV"),
            ("p3_mtp_ids", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("mtp_target_layer_ids", [5, 23, 41, 47]), "BAD_P3_INV"),
            ("p3_rm_tot", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("readme_total_params_b_q", {"num": 27, "den": 5}), "BAD_P3_INV"),
            ("p3_rm_eff", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].update({"readme_effective_active_b_q": {"num": 28, "den": 5}, "readme_effective_over_physical_active_q": {"num": 28, "den": 17}}), "BAD_P3_INV"),
            ("p3_rm_rat_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("readme_effective_over_physical_active_q", {"num": 2, "den": 1}), "BAD_P3_INV"),
            ("p3_qwen_vf_f05", lambda d: d["pillar3_inkling2_loop_and_roofline"]["hardware_roofline_comparison"].update({"qwen25_05b_bf16_vram_frac_of_8gib_q": {"num": 1, "den": 2}, "qwen25_05b_bf16_vram_pct_dec": "50.00"}), "BAD_P3_INV"),
            ("p3_qwen_pct_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["hardware_roofline_comparison"].__setitem__("qwen25_05b_bf16_vram_pct_dec", "GARBAGE"), "BAD_P3_INV"),
            ("p3_cl_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("core_layers", 11), "BAD_P3_INV"),
            ("p3_eff_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("effective_layers", 47), "BAD_P3_INV"),
            ("p3_dr_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("depth_reuse_ratio_q", {"num": 3, "den": 1}), "BAD_P3_INV"),
            ("p3_gr_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("gate_rank_over_sqrt_hidden_q", {"num": 1, "den": 1}), "BAD_P3_INV"),
            ("p3_ae_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("active_expert_frac_q", {"num": 1, "den": 8}), "BAD_P3_INV"),
            ("p3_ih_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].__setitem__("intermediate_over_hidden_q", {"num": 1, "den": 1}), "BAD_P3_INV"),
            ("p3_cper_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["loop_core_adapter_amplification"].__setitem__("gate_adapter_params_per_core_layer", 1), "BAD_P3_INV"),
            ("p3_ctot_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["loop_core_adapter_amplification"].__setitem__("core_adapter_total_params", 1), "BAD_P3_INV"),
            ("p3_nleq_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["loop_core_adapter_amplification"].__setitem__("nonloop_equivalent_params", 1), "BAD_P3_INV"),
            ("p3_lev_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["loop_core_adapter_amplification"].__setitem__("effective_layer_leverage_q", {"num": 2, "den": 1}), "BAD_P3_INV"),
            ("p3_rho_f07", lambda d: (
                d["pillar3_inkling2_loop_and_roofline"]["loop_core_adapter_amplification"].update({"s76_contractive_rho_q": {"num": 1, "den": 2}, "s76_3pass_error_bound_q": {"num": 1, "den": 8}}),
                d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].update({"s76_g3_quant_amp_q": {"num": 7, "den": 4}, "s76_g3_quant_amp_dec": "1.7500", "s76_g3_over_rho3_ratio_q": {"num": 14, "den": 1}}),
            ), "BAD_P3_INV"),
            ("p3_np2_consistent", lambda d: (
                d["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"].update({"num_passes": 2, "effective_layers": 36, "depth_reuse_ratio_q": {"num": 3, "den": 2}}),
                d["pillar3_inkling2_loop_and_roofline"]["loop_core_adapter_amplification"].update({"nonloop_equivalent_params": 7077888, "effective_layer_leverage_q": {"num": 2, "den": 1}, "s76_3pass_error_bound_q": {"num": 1, "den": 16}, "divergent_3pass_error_q": {"num": 25, "den": 16}}),
                d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].update({"s76_g3_quant_amp_q": {"num": 5, "den": 4}, "s76_g3_quant_amp_dec": "1.2500", "s76_g3_over_rho3_ratio_q": {"num": 20, "den": 1}, "high_rho_3pass_init_q": {"num": 9, "den": 16}, "high_rho_g3_quant_amp_q": {"num": 7, "den": 4}, "high_rho_g3_quant_amp_dec": "1.7500", "threshold_lo_g3_q": {"num": 8, "den": 5}, "threshold_hi_g3_q": {"num": 13, "den": 8}}),
            ), "BAD_P3_INV"),
            ("p3_err3_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["loop_core_adapter_amplification"].__setitem__("s76_3pass_error_bound_q", {"num": 1, "den": 2}), "BAD_P3_INV"),
            ("p3_div3_f06", lambda d: d["pillar3_inkling2_loop_and_roofline"]["loop_core_adapter_amplification"].__setitem__("divergent_3pass_error_q", {"num": 999, "den": 1}), "BAD_P3_INV"),
            ("p3_stab_bad", lambda d: d["pillar3_inkling2_loop_and_roofline"]["loop_core_adapter_amplification"].__setitem__("contractive_3pass_stable", False), "BAD_P3_INV"),
            ("p3_m1h1_g3", lambda d: d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].__setitem__("s76_g3_quant_amp_q", {"num": 1, "den": 1}), "BAD_P3_INV"),
            ("p3_m1h1_g3d", lambda d: d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].__setitem__("s76_g3_quant_amp_dec", "1.0000"), "BAD_P3_INV"),
            ("p3_m1h1_rat", lambda d: d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].__setitem__("s76_g3_over_rho3_ratio_q", {"num": 1, "den": 1}), "BAD_P3_INV"),
            ("p3_m1h1_pg", lambda d: d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].__setitem__("s76_passes_m1h1_drift_gate", False), "BAD_P3_INV"),
            ("p3_m1h1_hr", lambda d: d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].__setitem__("high_rho_q", {"num": 4, "den": 5}), "BAD_P3_INV"),
            ("p3_m1h1_hr3", lambda d: d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].__setitem__("high_rho_3pass_init_q", {"num": 1, "den": 2}), "BAD_P3_INV"),
            ("p3_m1h1_hg3", lambda d: d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].__setitem__("high_rho_g3_quant_amp_q", {"num": 2, "den": 1}), "BAD_P3_INV"),
            ("p3_m1h1_hg3d", lambda d: d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].__setitem__("high_rho_g3_quant_amp_dec", "2.0000"), "BAD_P3_INV"),
            ("p3_m1h1_ck", lambda d: d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].__setitem__("high_rho_contracts_init_but_kills_m1h1", False), "BAD_P3_INV"),
            ("p3_m1h1_tlr", lambda d: d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].__setitem__("threshold_lo_rho_q", {"num": 1, "den": 2}), "BAD_P3_INV"),
            ("p3_m1h1_tlg", lambda d: d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].__setitem__("threshold_lo_g3_q", {"num": 2, "den": 1}), "BAD_P3_INV"),
            ("p3_m1h1_thr", lambda d: d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].__setitem__("threshold_hi_rho_q", {"num": 2, "den": 3}), "BAD_P3_INV"),
            ("p3_m1h1_thg", lambda d: d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].__setitem__("threshold_hi_g3_q", {"num": 2, "den": 1}), "BAD_P3_INV"),
            ("p3_m1h1_cap", lambda d: d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].__setitem__("m1h1_max_drift_ratio_delta3_over_delta1_ctrl_q", {"num": 3, "den": 1}), "BAD_P3_INV"),
            ("p3_m1h1_l2", lambda d: d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].__setitem__("m1h1_max_rel_l2_drift_delta3_q", {"num": 1, "den": 10}), "BAD_P3_INV"),
            ("p3_m1h1_fp", lambda d: d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].__setitem__("requires_unique_layer_fp_baseline", False), "BAD_P3_INV"),
            ("p3_m1h1_ctrl", lambda d: d["pillar3_inkling2_loop_and_roofline"]["per_pass_quant_noise_and_m1h1_gate"].__setitem__("requires_single_pass_nvfp4_control", False), "BAD_P3_INV"),
            ("p4_spec_cnt", lambda d: d["pillar4_provenance_and_lean4"].__setitem__("inkling_spec_count", 1), "BAD_SPEC_COUNT"),
            ("p4_spec_nonlist", lambda d: d["pillar4_provenance_and_lean4"].__setitem__("inkling_spec_manifest", "ab"), "BAD_SPEC_LIST"),
            ("p4_spec_len", lambda d: d["pillar4_provenance_and_lean4"]["inkling_spec_manifest"].pop(), "BAD_SPEC_LIST"),
            ("p4_spec_fn", lambda d: d["pillar4_provenance_and_lean4"]["inkling_spec_manifest"][0].__setitem__("filename", "wrong.json"), "BAD_SPEC_PIN"),
            ("p4_spec_sha", lambda d: d["pillar4_provenance_and_lean4"]["inkling_spec_manifest"][0].__setitem__("sha256", "0" * 64), "BAD_SPEC_PIN"),
            ("p4_up_cnt", lambda d: d["pillar4_provenance_and_lean4"].__setitem__("upstream_corpus_count", 9), "BAD_CORPUS_COUNT"),
            ("p4_up_nonlist", lambda d: d["pillar4_provenance_and_lean4"].__setitem__("upstream_cert_manifest", "x" * 10), "BAD_MANIFEST_LIST"),
            ("p4_up_len", lambda d: d["pillar4_provenance_and_lean4"]["upstream_cert_manifest"].pop(), "BAD_MANIFEST_LIST"),
            ("p4_up_tid", lambda d: d["pillar4_provenance_and_lean4"]["upstream_cert_manifest"][0].__setitem__("track_id", "S99"), "BAD_MANIFEST_PIN"),
            ("p4_up_rel", lambda d: d["pillar4_provenance_and_lean4"]["upstream_cert_manifest"][0].__setitem__("rel_path", "wrong.json"), "BAD_MANIFEST_PIN"),
            ("p4_up_sha", lambda d: d["pillar4_provenance_and_lean4"]["upstream_cert_manifest"][0].__setitem__("sha256", "0" * 64), "BAD_MANIFEST_PIN"),
            ("p4_lean_file", lambda d: d["pillar4_provenance_and_lean4"]["lean4_certificate"].__setitem__("file", "Wrong.lean"), "BAD_LEAN_PIN"),
            ("p4_lean_sha", lambda d: d["pillar4_provenance_and_lean4"]["lean4_certificate"].__setitem__("sha256", "0" * 64), "BAD_LEAN_PIN"),
            ("p4_lean_cnt", lambda d: d["pillar4_provenance_and_lean4"]["lean4_certificate"].__setitem__("theorem_count", 17), "BAD_THEOREM_COUNT"),
            ("p4_lean_thms", lambda d: d["pillar4_provenance_and_lean4"]["lean4_certificate"].__setitem__("theorems", []), "BAD_THEOREM_LIST"),
            ("p4_lean_ax", lambda d: d["pillar4_provenance_and_lean4"]["lean4_certificate"].__setitem__("allowed_axioms", ["sorryAx"]), "BAD_ALLOWED_AXIOMS"),
            ("p4_nov_tier", lambda d: d["pillar4_provenance_and_lean4"]["novelty_honesty_law4"].__setitem__("novelty_tier", "N2"), "BAD_NOVELTY_CLAIMS"),
            ("p4_nov_n0", lambda d: d["pillar4_provenance_and_lean4"]["novelty_honesty_law4"].__setitem__("n0_prior_art_anchored", False), "BAD_NOVELTY_CLAIMS"),
            ("p4_nov_n1", lambda d: d["pillar4_provenance_and_lean4"]["novelty_honesty_law4"].__setitem__("n1_exact_synthesis_verified", False), "BAD_NOVELTY_CLAIMS"),
            ("p4_nov_n2", lambda d: d["pillar4_provenance_and_lean4"]["novelty_honesty_law4"].__setitem__("n2_claims", 1), "BAD_NOVELTY_CLAIMS"),
        ]
        for label, mut_fn, exp_code in semantic_tampers:
            cand_c = copy.deepcopy(cert)
            mut_fn(cand_c["payload"])
            with self.assertRaises(s96.S96Error, msg=f"SEC must reject {label}") as e_s:
                ver.secondary_audit_payload(cand_c["payload"])
            self.assertEqual(e_s.exception.code, exp_code, f"SEC code for {label}")
            resigned = _resign(cand_c)
            with self.assertRaises(s96.S96Error, msg=f"FR0 must reject {label}") as e_f0:
                ver.verify_certificate_dict(resigned, full_replay=False)
            self.assertEqual(e_f0.exception.code, exp_code, f"FR0 code for {label}")
            with self.assertRaises(s96.S96Error, msg=f"FR1 must reject {label}") as e_f1:
                ver.verify_certificate_dict(resigned, full_replay=True)
            self.assertEqual(e_f1.exception.code, exp_code, f"FR1 code for {label}")

        c_hollow = copy.deepcopy(cert)
        c_hollow["payload"] = {}
        with self.assertRaises(s96.S96Error) as a8:
            ver.audit_certificate_object(_resign(c_hollow))
        self.assertEqual(a8.exception.code, "BAD_PAYLOAD_KEYS")

        # Mocked FR1 oracle-divergence guards (since SEC/FR0 reject 100% of field-level drifts!)
        fake_payload_exp = copy.deepcopy(cert)
        fake_payload_exp["payload"]["pillar3_inkling2_loop_and_roofline"]["inkling2_config_exact"]["vocab_size"] = 201025
        with mock.patch.object(ver, "build_certificate", return_value=fake_payload_exp):
            with self.assertRaises(s96.S96Error) as a8r:
                ver.verify_certificate_dict(cert, full_replay=True)
            self.assertEqual(a8r.exception.code, "PAYLOAD_ORACLE_MISMATCH")

        fake_exp = copy.deepcopy(cert)
        fake_exp["certificate_sha256"] = "f" * 64
        with mock.patch.object(ver, "build_certificate", return_value=fake_exp):
            with self.assertRaises(s96.S96Error) as a9:
                ver.audit_certificate_object(cert)
            self.assertEqual(a9.exception.code, "ORACLE_CERT_SHA_MISMATCH")

    def test_committed_disk_cert_manifests_and_hardened_io(self) -> None:
        disk_cert = _SCRIPT_DIR / "s96_beyond_lora_inkling_certificate.json"
        mode = stat.S_IMODE(disk_cert.stat().st_mode)
        self.assertIn(mode, (0o600, 0o644))
        checked = ver.check_certificate_file(disk_cert)

        out_buf = io.BytesIO()
        with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": out_buf})()):
            rc = ver.main(["--standalone", "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(out_buf.getvalue(), disk_cert.read_bytes())
        out_buf2 = io.BytesIO()
        with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": out_buf2})()):
            rc2 = ver.main([])
        self.assertEqual(rc2, 0)
        self.assertEqual(out_buf2.getvalue(), disk_cert.read_bytes())

        chk_buf = io.BytesIO()
        with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": chk_buf})()):
            rc = ver.main(["--check", str(disk_cert), "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(chk_buf.getvalue().decode("utf-8"))["status"], "PASS")
        self.assertEqual(ver.main(["--check", str(disk_cert)]), 0)

        with tempfile.TemporaryDirectory(prefix="s96_io_") as td:
            tdir = Path(td).resolve()
            out_p = tdir / "cert_out.json"
            old_umask = os.umask(0o022)
            try:
                w_buf = io.BytesIO()
                with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": w_buf})()):
                    rc_w = ver.main(["--write", str(out_p), "--json"])
                self.assertEqual(rc_w, 0)
                self.assertEqual(json.loads(w_buf.getvalue().decode("utf-8"))["status"], "WRITTEN")
                self.assertEqual(stat.S_IMODE(out_p.stat().st_mode), 0o600)
                self.assertEqual(ver.main(["--write", str(out_p)]), 0)
                self.assertEqual(out_p.read_bytes(), disk_cert.read_bytes())
            finally:
                os.umask(old_umask)

            # Verify --verify-upstream with synthetic matching & tampered roots (works in isolated CI!)
            fake_root = tdir / "exp_root"
            fake_root.mkdir()
            fake_bytes = b'{"ok":true}\n'
            fake_sha = hashlib.sha256(fake_bytes).hexdigest()
            fake_manifest = (("S1", "t1/c1.json", fake_sha),)
            (fake_root / "t1").mkdir()
            (fake_root / "t1" / "c1.json").write_bytes(fake_bytes)
            with mock.patch.object(ver, "UPSTREAM_CERT_MANIFEST", fake_manifest):
                up_buf = io.BytesIO()
                with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": up_buf})()):
                    rc_u = ver.main(["--verify-upstream", str(fake_root), "--json"])
                self.assertEqual(rc_u, 0)
                self.assertEqual(json.loads(up_buf.getvalue().decode("utf-8"))["tracks_verified"], 1)
                self.assertEqual(ver.main(["--verify-upstream", str(fake_root)]), 0)
                (fake_root / "t1" / "c1.json").write_bytes(b'{"ok":false}\n')
                with self.assertRaises(s96.S96Error) as e_up:
                    ver.verify_upstream_manifest(fake_root)
                self.assertEqual(e_up.exception.code, "UPSTREAM_SHA_MISMATCH")

            # Verify --verify-inkling with synthetic matching & tampered spec dirs
            fake_spec_dir = tdir / "spec_dir"
            fake_spec_dir.mkdir()
            sp_bytes = b'{"loop_config":{"num_passes":3}}\n'
            sp_sha = hashlib.sha256(sp_bytes).hexdigest()
            (fake_spec_dir / "cfg.json").write_bytes(sp_bytes)
            with mock.patch.object(ver, "INKLING_SPEC_MANIFEST", (("cfg.json", sp_sha),)):
                sp_buf = io.BytesIO()
                with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": sp_buf})()):
                    rc_sp = ver.main(["--verify-inkling", str(fake_spec_dir), "--json"])
                self.assertEqual(rc_sp, 0)
                self.assertEqual(json.loads(sp_buf.getvalue().decode("utf-8"))["specs_verified"], 1)
                self.assertEqual(ver.main(["--verify-inkling", str(fake_spec_dir)]), 0)
                (fake_spec_dir / "cfg.json").write_bytes(b'{"tampered":true}\n')
                with self.assertRaises(s96.S96Error) as e_sp_m:
                    ver.verify_inkling_specs(fake_spec_dir)
                self.assertEqual(e_sp_m.exception.code, "INKLING_SPEC_SHA_MISMATCH")

            # Reject bad path types, surrogate, NUL, root/.. paths
            with self.assertRaises(s96.S96Error) as p0:
                ver.read_regular_file_bytes("not_a_path")  # type: ignore[arg-type]
            self.assertEqual(p0.exception.code, "INVALID_PATH_TYPE")
            with self.assertRaises(s96.S96Error) as p1:
                ver.read_regular_file_bytes(Path(str(tdir) + "/\ud800"))
            self.assertEqual(p1.exception.code, "INVALID_UNICODE_STR")
            with self.assertRaises(s96.S96Error) as p2:
                ver.read_regular_file_bytes(Path(str(tdir) + "/a\x00b"))
            self.assertEqual(p2.exception.code, "INVALID_PATH_NUL")
            with self.assertRaises(s96.S96Error) as p3:
                ver.read_regular_file_bytes(Path("/"))
            self.assertEqual(p3.exception.code, "INVALID_PATH")
            with self.assertRaises(s96.S96Error) as p4:
                ver.read_regular_file_bytes(tdir / "..")
            self.assertEqual(p4.exception.code, "INVALID_PATH")

            with self.assertRaises(s96.S96Error) as p5:
                ver.check_certificate_file(tdir / "no_dir" / "x.json")
            self.assertEqual(p5.exception.code, "PARENT_DIR_ERROR")
            with self.assertRaises(s96.S96Error) as p6:
                ver.check_certificate_file(tdir / "missing.json")
            self.assertEqual(p6.exception.code, "FILE_READ_ERROR")
            with self.assertRaises(s96.S96Error) as p7:
                ver.check_certificate_file(tdir)
            self.assertEqual(p7.exception.code, "NOT_REGULAR_FILE")

            sym_f = tdir / "sym.json"
            sym_f.symlink_to(out_p)
            with self.assertRaises(s96.S96Error) as p8:
                ver.check_certificate_file(sym_f)
            self.assertEqual(p8.exception.code, "SYMLINK_FORBIDDEN")
            with self.assertRaises(s96.S96Error) as p8w:
                ver.write_atomic_0600_bytes(sym_f, b"{}\n")
            self.assertEqual(p8w.exception.code, "SYMLINK_FORBIDDEN")

            sub_d = tdir / "real_sub"
            sub_d.mkdir()
            (sub_d / "c.json").write_bytes(disk_cert.read_bytes())
            sym_d = tdir / "sym_sub"
            sym_d.symlink_to(sub_d)
            with self.assertRaises(s96.S96Error) as p9:
                ver.check_certificate_file(sym_d / "c.json")
            self.assertEqual(p9.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")

            with mock.patch.object(ver.os, "environ", {}):
                ver._check_pwd_no_symlinks()
            with mock.patch.object(ver.os, "environ", {"PWD": "x" + str(sym_d)}):
                ver._check_pwd_no_symlinks()
            with mock.patch.object(ver.os, "environ", {"PWD": str(sym_d)}):
                with self.assertRaises(s96.S96Error) as p9p:
                    ver._check_pwd_no_symlinks()
                self.assertEqual(p9p.exception.code, "SYMLINK_ANCESTOR_FORBIDDEN")
            with mock.patch.object(ver.os, "environ", {"PWD": "/tmp/\ud800"}):
                with self.assertRaises(s96.S96Error) as p9s:
                    ver.read_regular_file_bytes(Path("c.json"))
                self.assertEqual(p9s.exception.code, "INVALID_UNICODE_STR")
            with mock.patch.dict(os.environ, {"PWD": "/nonexistent_s96_pwd_xyz"}):
                with self.assertRaises(s96.S96Error):
                    ver.read_regular_file_bytes(Path("definitely_missing_s96_rel.json"))

            fifo_p = tdir / "pipe.fifo"
            os.mkfifo(fifo_p)
            with self.assertRaises(s96.S96Error) as pf:
                ver.check_certificate_file(fifo_p)
            self.assertEqual(pf.exception.code, "NOT_REGULAR_FILE")
            with self.assertRaises(s96.S96Error) as pfw:
                ver.write_atomic_0600_bytes(fifo_p, b"{}\n")
            self.assertEqual(pfw.exception.code, "NOT_REGULAR_FILE")

            hl_p = tdir / "hardlink.json"
            os.link(out_p, hl_p)
            with self.assertRaises(s96.S96Error) as ph1:
                ver.check_certificate_file(hl_p)
            self.assertEqual(ph1.exception.code, "HARDLINK_FORBIDDEN")
            with self.assertRaises(s96.S96Error) as ph2:
                ver.write_atomic_0600_bytes(hl_p, b"{}\n")
            self.assertEqual(ph2.exception.code, "HARDLINK_FORBIDDEN")
            hl_p.unlink()

            ro_dir = tdir / "ro_dir"
            ro_dir.mkdir()
            ro_dir.chmod(0o500)
            try:
                with self.assertRaises(s96.S96Error) as pro:
                    ver.write_atomic_0600_bytes(ro_dir / "x.json", b"{}\n")
                self.assertEqual(pro.exception.code, "FILE_WRITE_ERROR")
            finally:
                ro_dir.chmod(0o700)

            crlf_p = tdir / "crlf.json"
            crlf_p.write_bytes(disk_cert.read_bytes().replace(b"\n", b"\r\n"))
            with self.assertRaises(s96.S96Error) as pcrlf:
                ver.check_certificate_file(crlf_p)
            self.assertEqual(pcrlf.exception.code, "CRLF_FORBIDDEN")

            badu_p = tdir / "badutf8.json"
            badu_p.write_bytes(b"\xff\xfe")
            with self.assertRaises(s96.S96Error) as pbu:
                ver.check_certificate_file(badu_p)
            self.assertEqual(pbu.exception.code, "INVALID_UTF8")

            pretty_p = tdir / "pretty.json"
            pretty_p.write_text(json.dumps(checked, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(s96.S96Error) as ppr:
                ver.check_certificate_file(pretty_p)
            self.assertEqual(ppr.exception.code, "NONCANONICAL_BYTES")

            dfd_chk = os.open(tdir, os.O_RDONLY | os.O_DIRECTORY)
            try:
                self.assertIs(ver._is_symlink_at(dfd_chk, "no_such_entry"), False)
                self.assertIs(ver._is_symlink_at(dfd_chk, "sym.json"), True)
            finally:
                os.close(dfd_chk)

            big_p = tdir / "big.json"
            big_p.write_bytes(b"a" * 32)
            self.assertEqual(ver.read_regular_file_bytes(big_p, max_bytes=32), b"a" * 32)
            big_p.write_bytes(b"a" * 64)
            with mock.patch.object(os, "read", return_value=b""):
                with self.assertRaises(s96.S96Error) as pbig:
                    ver.read_regular_file_bytes(big_p, max_bytes=32)
                self.assertEqual(pbig.exception.code, "FILE_TOO_LARGE")

            empty_p = tdir / "empty.json"
            empty_p.write_bytes(b"")
            with mock.patch.object(os, "read", side_effect=[b"x" * 20, b"y" * 20, b""]):
                with self.assertRaises(s96.S96Error) as pstr:
                    ver.read_regular_file_bytes(empty_p, max_bytes=32)
                self.assertEqual(pstr.exception.code, "FILE_TOO_LARGE")
            with mock.patch.object(os, "read", side_effect=OSError(5, "EIO")):
                with self.assertRaises(s96.S96Error) as peio:
                    ver.read_regular_file_bytes(out_p)
                self.assertEqual(peio.exception.code, "FILE_READ_ERROR")
            with mock.patch.object(os, "write", side_effect=OSError(5, "EIO")):
                with self.assertRaises(s96.S96Error) as pwe:
                    ver.write_atomic_0600_bytes(tdir / "eio.json", b"hello")
                self.assertEqual(pwe.exception.code, "FILE_WRITE_ERROR")
            with mock.patch.object(os, "write", return_value=0):
                with self.assertRaises(s96.S96Error) as pw0:
                    ver.write_atomic_0600_bytes(tdir / "zwrite.json", b"hello")
                self.assertEqual(pw0.exception.code, "FILE_WRITE_ERROR")
            fake_st = type("St", (), {"st_nlink": 2})()
            with mock.patch.object(os, "fstat", return_value=fake_st):
                with self.assertRaises(s96.S96Error) as ptn:
                    ver.write_atomic_0600_bytes(tdir / "hl_tmp.json", b"hello")
                self.assertEqual(ptn.exception.code, "HARDLINK_FORBIDDEN")
            with mock.patch.object(os, "replace", side_effect=OSError(13, "EACCES")):
                with self.assertRaises(s96.S96Error) as prep:
                    ver.write_atomic_0600_bytes(tdir / "rep_err.json", b"hello")
                self.assertEqual(prep.exception.code, "FILE_WRITE_ERROR")

            err_buf = io.StringIO()
            with mock.patch.object(sys, "stderr", err_buf):
                rc_err = ver.main(["--check", str(crlf_p)])
            self.assertEqual(rc_err, 2)
            self.assertIn("CRLF_FORBIDDEN", err_buf.getvalue())


class TestS96LeanR10AndLiveOrCiVerification(unittest.TestCase):
    def test_r10_static_all_classes_and_clean_cases(self) -> None:
        with self.assertRaises(s96.S96Error):
            ver.audit_lean4_source_r10(123)  # type: ignore[arg-type]

        self.assertIs(ver._is_lean4_ident_prev("a", -1), False)
        self.assertIs(ver._is_lean4_ident_prev("a", 0), True)
        self.assertIs(ver._is_lean4_ident_prev("_", 0), True)
        self.assertIs(ver._is_lean4_ident_prev(" ", 0), False)
        self.assertIs(ver._is_lean4_ident_prev("a!", 1), True)
        self.assertIs(ver._is_lean4_ident_prev("_!", 1), True)
        self.assertIs(ver._is_lean4_ident_prev(" !", 1), False)
        self.assertIs(ver._is_lean4_ident_prev("!", 0), False)
        self.assertEqual(ver._strip_outer_parens(""), "")
        self.assertEqual(ver._strip_outer_parens("("), "(")
        self.assertEqual(ver._strip_outer_parens("(false)"), "false")
        self.assertEqual(ver._strip_outer_parens("(false"), "(false")
        self.assertEqual(ver._strip_outer_parens("false)"), "false)")

        self.assertEqual(ver._match_lean4_char_literal_end("'a'", 0, 3), 3)
        self.assertIsNone(ver._match_lean4_char_literal_end("'a", 0, 2))
        self.assertIsNone(ver._match_lean4_char_literal_end("'ab", 0, 3))
        self.assertIsNone(ver._match_lean4_char_literal_end("'ab'", 0, 4))
        self.assertEqual(ver._match_lean4_char_literal_end("'\n'", 0, 3), 3)
        self.assertIsNone(ver._match_lean4_char_literal_end("'''", 0, 3))
        self.assertEqual(ver._match_lean4_char_literal_end("'\\''", 0, 4), 4)
        self.assertEqual(ver._match_lean4_char_literal_end("'\\n'", 0, 4), 4)
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\n", 0, 3))
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\\n'", 0, 4))
        self.assertEqual(ver._match_lean4_char_literal_end("'\\x2a'", 0, 6), 6)
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\x2g'", 0, 6))
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\x2a!", 0, 6))
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\x2a", 0, 5))
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\y2a'", 0, 6))
        self.assertEqual(ver._match_lean4_char_literal_end("'\\u002A'", 0, 8), 8)
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\u002g'", 0, 8))
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\u002A!", 0, 8))
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\u002A", 0, 7))
        self.assertIsNone(ver._match_lean4_char_literal_end("'\\v002A'", 0, 8))

        clean_src = "\n".join(
            [
                "-- sorry admit axiom native_decide",
                "/- outer /x a/ sorry -x /- nested -/ still comment -/",
                'def s1 := "sorry \\" native_decide"',
                'def s2 := r#"a " sorry " b"#',
                'def s3 := s! "hello {1 + 1} sorry"',
                'def s4 := !r#"sorry"#',
                'def s5 := obj.opaque ++ obj.dbg_trace',
                'def s6 := s!x ++ "sorry"',
                'def s7 := obj.panic ++ "sorry"',
                "export Nat (succ)",
                'def s8 := _ok_1 "sorry"',
                'def s "a {sorry}"',
                'def bar#"ok"',
                "def foo!r := 1 / 2 - 1",
                "def c1 : Char := '\"'",
                "def c2 : Char := '\\''",
                "def c3 : Char := '\\x22'",
                "def c4 : Char := '\\u0022'",
                "def x' := 1",
                "def x_p := x' + 'a'.toNat",
                "def badCharStart := 'a + 1",
                "def x := rec.partial",
                "theorem t1 : 1 = 1 := by decide (native := false)",
                "theorem t2 : 1 = 1 := by decide (config := ({ native := Bool.false }))",
                "def cfg : DecideConfig := { native := false }",
                "def okGuillemet := «hello» ++ «bad sorry»",
                "@[simp] def attrOk := 1",
                "@[extern",
                "import Init.Data.Nat.Basic",
                "#print axioms t1",
                "theorem t_eof : 1 = 1 := by decide",
            ]
        )
        self.assertEqual(ver.audit_lean4_source_r10(clean_src), [])
        self.assertEqual(ver.audit_lean4_source_r10("-- eof no newline"), [])
        self.assertEqual(ver.audit_lean4_source_r10("r#"), [])
        self.assertEqual(ver.audit_lean4_source_r10("rx"), [])
        self.assertEqual(ver.audit_lean4_source_r10('r"sorry"a'), [])
        self.assertEqual(ver.audit_lean4_source_r10('!"a {sorry}"s'), [])
        self.assertEqual(ver.audit_lean4_source_r10('"ok"a!'), [])
        self.assertEqual(ver.audit_lean4_source_r10(' !"sorry"'), [])
        self.assertEqual(ver.audit_lean4_source_r10("'a'"), [])
        self.assertEqual(ver.audit_lean4_source_r10('def f := a\'"\' sorry "'), [])
        self.assertEqual(ver.audit_lean4_source_r10('def f := _\'"\' sorry "'), [])
        self.assertEqual(ver.audit_lean4_source_r10('def f := foo.bar\'"\' sorry "'), [])
        self.assertEqual(ver.audit_lean4_source_r10('def f := «f».x\'"\' sorry "'), [])
        self.assertEqual(ver.audit_lean4_source_r10('def f := foo.b1\'"\' sorry "'), [])
        self.assertEqual(ver.audit_lean4_source_r10('def f := x!\'"\' sorry "'), [])
        self.assertEqual(ver.audit_lean4_source_r10('def f := x\'\'"\' sorry "'), [])
        self.assertEqual(ver.audit_lean4_source_r10('def f := foo.s! "a {sorry}"'), [])
        self.assertEqual(ver.audit_lean4_source_r10("s!"), [])
        self.assertEqual(ver.audit_lean4_source_r10('panic!"sorry"'), ["LEAN4_PANIC_ESCAPE"])
        self.assertEqual(ver.audit_lean4_source_r10('!panic!"sorry"'), ["LEAN4_PANIC_ESCAPE"])
        self.assertEqual(ver.audit_lean4_source_r10("def y := a!\"\""), ["LEAN4_UNKNOWN_BANG_STRING"])
        self.assertEqual(ver.audit_lean4_source_r10("'\x22'\nsorry\ndef q : Char := '\x22'"), ["LEAN4_SORRY"])
        self.assertEqual(ver.audit_lean4_source_r10('def x := foo.r#"ok"; sorry; def z := "#"'), ["LEAN4_SORRY"])
        self.assertEqual(
            ver.audit_lean4_source_r10('def _a : String := s!"x"\naxiom evil : False\ndef _b : Char := \'"\''),
            ["LEAN4_AXIOM"],
        )

        cases: list[tuple[str, str]] = [
            ("theorem t : True := by sorry", "LEAN4_SORRY"),
            ("-- comment\ntheorem t : True := by sorry", "LEAN4_SORRY"),
            ("def x := 1 - 2\ndef y := a - sorry", "LEAN4_SORRY"),
            ("def x := 1-2; sorry", "LEAN4_SORRY"),
            ("theorem t : True := by «sorry»", "LEAN4_SORRY"),
            ("theorem t : True := by admit", "LEAN4_ADMIT"),
            ("axiom bogus : False", "LEAN4_AXIOM"),
            ("unsafe def f : Nat := 0", "LEAN4_UNSAFE"),
            ("opaque badOp : Nat := 0", "LEAN4_OPAQUE"),
            ("noncomputable opaque badOp2 : Nat", "LEAN4_OPAQUE"),
            ("def x := dbg_trace \"hi\"; 0", "LEAN4_DBG_TRACE"),
            ("def x := dbg_sleep 1 fun _ => 0", "LEAN4_DBG_TRACE"),
            ("def x := dbg_stack_trace fun _ => 0", "LEAN4_DBG_TRACE"),
            ("def x := dbgTrace \"hi\" fun _ => 0", "LEAN4_DBG_TRACE"),
            ("def x := dbgTraceVal 0", "LEAN4_DBG_TRACE"),
            ("def x := dbgTraceIfShared \"hi\" 0", "LEAN4_DBG_TRACE"),
            ("def x := dbgSleep 1 fun _ => 0", "LEAN4_DBG_TRACE"),
            ("def x := dbgStackTrace fun _ => 0", "LEAN4_DBG_TRACE"),
            ("def x : Nat := unreachable!", "LEAN4_PANIC_ESCAPE"),
            ("def x := panicWithPosWithDecl \"f\" \"d\" 1 1 \"m\"", "LEAN4_PANIC_ESCAPE"),
            ("theorem t : 1 = 1 := by native_decide", "LEAN4_NATIVE_DECIDE"),
            ("theorem t : 1 = 1 := by bv_decide", "LEAN4_BV_DECIDE"),
            ("def x := sorryAx", "LEAN4_SORRY_AX"),
            ("def x := Lean.Meta.mkSorry", "LEAN4_MK_SORRY"),
            ("def x := Lean.ofReduceBool", "LEAN4_OF_REDUCE_BOOL"),
            ("def x := Lean.ofReduceNat", "LEAN4_OF_REDUCE_NAT"),
            ("def x := Lean.trustCompiler", "LEAN4_TRUST_COMPILER"),
            ("def x := Lean.Elab.Command.elabCommand", "LEAN4_LEAN_META_API"),
            ("def x := Lean.Core.CoreM", "LEAN4_LEAN_META_API"),
            ("def x := Lean.Environment.addDecl", "LEAN4_LEAN_META_API"),
            ("def x := Lean.Kernel.check", "LEAN4_LEAN_META_API"),
            ("public\n  import Mathlib.Tactic", "LEAN4_NON_INIT_IMPORT"),
            ("import Std.Data.HashMap", "LEAN4_NON_INIT_IMPORT"),
            ("partial\n def loop (n : Nat) : Nat := loop n", "LEAN4_PARTIAL"),
            ("theorem t : 1 = 1 := by decide +native", "LEAN4_DECIDE_NATIVE"),
            (") theorem t : 1 = 1 := by decide (native := true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := false || true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := false == false)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := false != true)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (native := false.not)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native := true })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { native })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := myCfg)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := {foo)", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := foo})", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { { })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { } })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (config := { c with native := false })", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide («native» := true)", "LEAN4_DECIDE_NATIVE"),
            ("def c : DecideConfig := { native := true }", "LEAN4_DECIDE_NATIVE"),
            ("set_option debug.skipKernelTC true", "LEAN4_SKIP_KERNEL_TC"),
            ("set_option debug.byAsSorry true", "LEAN4_SKIP_KERNEL_TC"),
            ("set_option debug.proofAsSorry true", "LEAN4_SKIP_KERNEL_TC"),
            ("set_option debug.terminalTacticsAsSorry true", "LEAN4_SKIP_KERNEL_TC"),
            ("set_option warn.sorry false", "LEAN4_SKIP_KERNEL_TC"),
            ("#eval 1 + 1", "LEAN4_EVAL_SPOOF"),
            ("#eval! 1 + 1", "LEAN4_EVAL_SPOOF"),
            ("#reduce 1 + 1", "LEAN4_EVAL_SPOOF"),
            ("#exit", "LEAN4_EVAL_SPOOF"),
            ("#guard_msgs in #check Nat", "LEAN4_EVAL_SPOOF"),
            ("#guard true", "LEAN4_EVAL_SPOOF"),
            ("#print Nat.add", "LEAN4_EVAL_SPOOF"),
            ("#print axioms theorem", "LEAN4_EVAL_SPOOF"),
            ("run_cmd pure ()", "LEAN4_EVAL_SPOOF"),
            ("initialize x : Nat := pure 0", "LEAN4_EVAL_SPOOF"),
            ("builtin_initialize x : Nat := pure 0", "LEAN4_EVAL_SPOOF"),
            ('] @[extern "c_fn"] def f : Nat := 0', "LEAN4_ATTR_TRUST_ESCAPE"),
            ("attribute [implemented_by g] f", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("@[csimp] theorem csimp_bad : 1 = 1 := rfl", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("attribute [csimp] csimp_bad", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("@[export c_sym] def exp_fn : Nat := 0", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("attribute [export c_sym] exp_fn", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("@[init] def init_fn : IO Unit := pure ()", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("@[builtin_init] def binit_fn : IO Unit := pure ()", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("@[term_elab foo] def te := 0", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("@[command_elab foo] def ce := 0", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("@[tactic foo] def ta := 0", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("@[macro foo] def ma := 0", "LEAN4_ATTR_TRUST_ESCAPE"),
            ("attribute [macro_rules] ma", "LEAN4_ATTR_TRUST_ESCAPE"),
            ('def x := s! "a {sorry} b"', "LEAN4_SORRY"),
            ('def x := !s!"a {sorry}"', "LEAN4_SORRY"),
            ('def x := dbg_trace "{(fun (_ : 1 = 1) => 0) (by native_decide)}" 0', "LEAN4_NATIVE_DECIDE"),
            ('def x := throwError "{sorry}"', "LEAN4_SORRY"),
            ('def x := foo!"a {sorry}"', "LEAN4_UNKNOWN_BANG_STRING"),
            ('def x := xpanic!"ok"', "LEAN4_UNKNOWN_BANG_STRING"),
            ('syntax "foo!" interpolatedStr(term) : term', "LEAN4_META_SYNTAX_ESCAPE"),
            ("macro_rules | `(1) => `(1)", "LEAN4_META_SYNTAX_ESCAPE"),
            ('elab "e" : term => sorry', "LEAN4_META_SYNTAX_ESCAPE"),
            ('notation "openq\\"" => 0', "LEAN4_META_SYNTAX_ESCAPE"),
            ('def x := s! /- c -/ "{sorry}"', "LEAN4_SORRY"),
            ('def x := s! -- c\n"{sorry}"', "LEAN4_SORRY"),
            ("theorem t : 1 = 1 := by decide -revert +native", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 = 1 := by decide (revert := true) +native", "LEAN4_DECIDE_NATIVE"),
            ("set_option «debug».«skipKernelTC» true", "LEAN4_SKIP_KERNEL_TC"),
            ('def q1 : Char := \'"\'\ntheorem bad : False := by sorry\ndef q2 : Char := \'"\'', "LEAN4_SORRY"),
            ('def q1 : Char := \'"\'\naxiom bad : False\ndef q2 : Char := \'"\'', "LEAN4_AXIOM"),
            ('def q1 : Char := \'"\'\ntheorem bad : 1 = 1 := by native_decide\ndef q2 : Char := \'"\'', "LEAN4_NATIVE_DECIDE"),
            ('def q1 : Char := \'"\'\n#eval IO.println "\'S96.bad\' does not depend on any axioms"\ndef q2 : Char := \'"\'', "LEAN4_EVAL_SPOOF"),
            ("def q1 : Char := '\\''\ndef q2 : Char := '\"'\ntheorem bad : False := by sorry\ndef q3 : Char := '\"'", "LEAN4_SORRY"),
            ("def b : Bool := !'\"'.isDigit\ntheorem t : (1 : Nat) = 2 := by sorry\ndef z : Char := '\"'", "LEAN4_SORRY"),
            ("def b := 1'\"'\ntheorem t : (1 : Nat) = 2 := by sorry\ndef z : Char := '\"'", "LEAN4_SORRY"),
            ("def b := «x»'\"'\ntheorem t : (1 : Nat) = 2 := by sorry\ndef z : Char := '\"'", "LEAN4_SORRY"),
            ("def b := f '\n' '\"'\ntheorem t : (1 : Nat) = 2 := by sorry\ndef z : Char := '\"'", "LEAN4_SORRY"),
            ("def b := foo+'\"'\ntheorem t : (1 : Nat) = 2 := by sorry\ndef z : Char := '\"'", "LEAN4_SORRY"),
            ("def g := «a\"b»\ntheorem t : (1 : Nat) = 2 := by sorry\ndef z := «a\"b»", "LEAN4_SORRY"),
            ("def g := «/-»\ntheorem t : (1 : Nat) = 2 := by sorry\ndef z := «-/»", "LEAN4_SORRY"),
            ("def s := s!\"hello\"\ntheorem t : (1 : Nat) = 2 := by sorry\ndef z := s!\"\\\"x\"", "LEAN4_SORRY"),
            ("def s := r#\" \" \"#\ntheorem t : (1 : Nat) = 2 := by sorry\ndef z := r#\" \" \"#", "LEAN4_SORRY"),
            ("def b := !\"{\" == \"a\"\ntheorem t : (1 : Nat) = 2 := by sorry\ndef c := \"}\"", "LEAN4_SORRY"),
            ("def x := «unterminated", "LEAN4_UNTERMINATED_IDENT"),
            ("/- unterminated comment", "LEAN4_UNTERMINATED_COMMENT"),
            ('def x := "unterminated', "LEAN4_UNTERMINATED_STRING"),
            ('def x := s!"unterminated', "LEAN4_UNTERMINATED_STRING"),
            ('def x := r#"unterminated', "LEAN4_UNTERMINATED_STRING"),
            ('def x := s!"{1', "LEAN4_UNTERMINATED_STRING"),
            ("def x := «axioms»\n#print «axioms» foo", "LEAN4_EVAL_SPOOF"),
            ('def x := s!"{\"{}\"}" ++ s!"{sorry}"', "LEAN4_SORRY"),
        ]
        for snippet, expected_code in cases:
            got = ver.audit_lean4_source_r10(snippet)
            self.assertIn(expected_code, got, f"expected {expected_code} for {snippet!r}, got {got}")

    def test_lean_verification_dual_mode_zero_skips(self) -> None:
        """Runs live Lean 4.36.0 when installed, or 0-skip mocked + fail-closed checks in Lean-less CI."""
        lean_file = _SCRIPT_DIR / s96.LEAN_FILE_NAME
        self.assertEqual(ver.audit_lean4_source_r10(lean_file.read_text(encoding="utf-8")), [])
        self.assertEqual(hashlib.sha256(lean_file.read_bytes()).hexdigest(), s96.LEAN_FILE_SHA256)

        has_lean = True
        try:
            ver._find_lean_binary()
        except s96.S96Error:
            has_lean = False

        if os.environ.get("ALETHEIA_REQUIRE_LEAN") == "1":
            self.assertTrue(has_lean, "ALETHEIA_REQUIRE_LEAN=1 requires live lean binary")

        if has_lean:
            out_buf = io.BytesIO()
            with mock.patch.object(sys, "stdout", type("FakeOut", (), {"buffer": out_buf})()):
                rc = ver.main(["--verify-lean", str(lean_file), "--json"])
            self.assertEqual(rc, 0)
            res = json.loads(out_buf.getvalue().decode("utf-8"))
            self.assertEqual(res["theorems_verified"], 20)
            self.assertEqual(res["r10_findings"], 0)
            self.assertEqual(res["allowed_axioms"], ["propext"])
            self.assertEqual(res["sha256"], s96.LEAN_FILE_SHA256)
            self.assertEqual(ver.main(["--verify-lean", str(lean_file)]), 0)
        else:
            err_buf = io.StringIO()
            with mock.patch.object(sys, "stderr", err_buf):
                rc_nl = ver.main(["--verify-lean", str(lean_file)])
            self.assertEqual(rc_nl, 2)
            self.assertIn("LEAN_BINARY_NOT_FOUND", err_buf.getvalue())

        # _scrubbed_tool_env() unit coverage (hostile vars stripped, HOME optional)
        hostile = {
            "HOME": "/tmp/s96_home_test",
            "LEAN_PATH": "/evil",
            "LEAN_OPTS": "-DwarningAsError=false",
            "LEAN_SYSROOT": "/evil_sys",
            "ELAN_TOOLCHAIN": "evil",
            "ELAN_HOME": "/evil_elan",
            "LEAN_CC": "/evil_cc",
            "LD_PRELOAD": "/evil.so",
            "LD_LIBRARY_PATH": "/evil_lib",
            "LAKE_HOME": "/evil_lake",
        }
        with mock.patch.object(ver.os, "environ", hostile):
            sc = ver._scrubbed_tool_env()
        self.assertEqual(sc["HOME"], "/tmp/s96_home_test")
        self.assertEqual(sc["LANG"], "C.UTF-8")
        self.assertEqual(sc["LC_ALL"], "C.UTF-8")
        for banned_k in ("LEAN_PATH", "LEAN_OPTS", "LEAN_SYSROOT", "ELAN_TOOLCHAIN", "ELAN_HOME", "LEAN_CC", "LD_PRELOAD", "LD_LIBRARY_PATH", "LAKE_HOME"):
            self.assertNotIn(banned_k, sc)
        with mock.patch.object(ver.os, "environ", {}):
            sc_no_home = ver._scrubbed_tool_env()
        self.assertNotIn("HOME", sc_no_home)

        with tempfile.TemporaryDirectory(prefix="s96_lean_") as td:
            tdir = Path(td).resolve()

            for bad_flag in (0, 1, "false", None):
                with self.assertRaises(s96.S96Error) as e_flag:
                    ver.verify_lean_file(lean_file, check_pinned_sha=bad_flag)  # type: ignore[arg-type]
                self.assertEqual(e_flag.exception.code, "INVALID_CHECK_PINNED_SHA")

            crlf_l = tdir / "c.lean"
            crlf_l.write_bytes(b"theorem t : True := trivial\r\n")
            with self.assertRaises(s96.S96Error) as e1:
                ver.verify_lean_file(crlf_l, check_pinned_sha=False)
            self.assertEqual(e1.exception.code, "CRLF_FORBIDDEN")

            badu_l = tdir / "u.lean"
            badu_l.write_bytes(b"\xff\xfe")
            with self.assertRaises(s96.S96Error) as e2:
                ver.verify_lean_file(badu_l, check_pinned_sha=False)
            self.assertEqual(e2.exception.code, "INVALID_UTF8")

            other_l = tdir / "o.lean"
            other_l.write_text("theorem ok1 : 1 = 1 := rfl\n#print axioms ok1\n", encoding="utf-8")
            with self.assertRaises(s96.S96Error) as e3:
                ver.verify_lean_file(other_l, check_pinned_sha=True)
            self.assertEqual(e3.exception.code, "LEAN_SHA_MISMATCH")

            r10_l = tdir / "r10_bad.lean"
            r10_l.write_text("#eval 1 + 1\n", encoding="utf-8")
            with self.assertRaises(s96.S96Error) as e_r10:
                ver.verify_lean_file(r10_l, check_pinned_sha=False)
            self.assertEqual(e_r10.exception.code, "LEAN_R10_STATIC_FINDING")

            for lex_idx, lex_src in enumerate(
                (
                    "def b : Bool := !'\"'.isDigit\ntheorem t : (1 : Nat) = 2 := by sorry\ndef z : Char := '\"'\n",
                    "def b := 1'\"'\ntheorem t : (1 : Nat) = 2 := by sorry\ndef z : Char := '\"'\n",
                    "def b := «x»'\"'\ntheorem t : (1 : Nat) = 2 := by sorry\ndef z : Char := '\"'\n",
                    "def b := f '\n' '\"'\ntheorem t : (1 : Nat) = 2 := by sorry\ndef z : Char := '\"'\n",
                )
            ):
                lex_p = tdir / f"lex_bypass_{lex_idx}.lean"
                lex_p.write_text(lex_src, encoding="utf-8")
                with self.assertRaises(s96.S96Error) as e_lex:
                    ver.verify_lean_file(lex_p, check_pinned_sha=False)
                self.assertEqual(e_lex.exception.code, "LEAN_R10_STATIC_FINDING")

            with mock.patch.object(ver, "_find_lean_binary", return_value="/usr/bin/lean"):
                wrap_ok = subprocess.CompletedProcess(
                    ["lean"],
                    0,
                    stdout="'ok1' depends on axioms: [\n  propext\n]\n'ok2' does not depend on any axioms\n",
                    stderr="",
                )
                with mock.patch.object(ver.os, "environ", hostile):
                    with mock.patch.object(subprocess, "run", return_value=wrap_ok) as m_run:
                        w_res = ver.verify_lean_file(other_l, check_pinned_sha=False)
                        self.assertEqual(w_res["theorems_verified"], 2)
                        call_args, call_kwargs = m_run.call_args
                        self.assertEqual(call_args[0], ["/usr/bin/lean", "--stdin"])
                        self.assertEqual(call_kwargs["input"], "theorem ok1 : 1 = 1 := rfl\n#print axioms ok1\n")
                        for banned_k in ("LEAN_PATH", "LEAN_OPTS", "LEAN_SYSROOT", "ELAN_TOOLCHAIN", "LD_PRELOAD", "LD_LIBRARY_PATH"):
                            self.assertNotIn(banned_k, call_kwargs["env"])

                wrap_bad = subprocess.CompletedProcess(
                    ["lean"],
                    0,
                    stdout="'ok1' depends on axioms: [\n  propext,\n  Classical.choice\n]\n",
                    stderr="",
                )
                with mock.patch.object(subprocess, "run", return_value=wrap_bad):
                    with self.assertRaises(s96.S96Error) as e_wb:
                        ver.verify_lean_file(other_l, check_pinned_sha=False)
                    self.assertEqual(e_wb.exception.code, "LEAN_FORBIDDEN_AXIOM")

                dup_out = subprocess.CompletedProcess(
                    ["lean"],
                    0,
                    stdout="'ok1' does not depend on any axioms\n'ok1' does not depend on any axioms\n",
                    stderr="",
                )
                with mock.patch.object(subprocess, "run", return_value=dup_out):
                    with self.assertRaises(s96.S96Error) as e_dup:
                        ver.verify_lean_file(other_l, check_pinned_sha=False)
                    self.assertEqual(e_dup.exception.code, "LEAN_DUPLICATE_THEOREM")

                fail_rc = subprocess.CompletedProcess(["lean"], 1, stdout="", stderr="type mismatch")
                with mock.patch.object(subprocess, "run", return_value=fail_rc):
                    with self.assertRaises(s96.S96Error) as e_rc:
                        ver.verify_lean_file(other_l, check_pinned_sha=False)
                    self.assertEqual(e_rc.exception.code, "LEAN_COMPILE_FAILED")

                fake_proc_err = subprocess.CompletedProcess(["lean"], 0, stdout="", stderr="warn")
                with mock.patch.object(subprocess, "run", return_value=fake_proc_err):
                    with self.assertRaises(s96.S96Error) as e6:
                        ver.verify_lean_file(other_l, check_pinned_sha=False)
                    self.assertEqual(e6.exception.code, "LEAN_STDERR_NONEMPTY")

                fake_proc_out = subprocess.CompletedProcess(["lean"], 0, stdout="weird line\n", stderr="")
                with mock.patch.object(subprocess, "run", return_value=fake_proc_out):
                    with self.assertRaises(s96.S96Error) as e7:
                        ver.verify_lean_file(other_l, check_pinned_sha=False)
                    self.assertEqual(e7.exception.code, "LEAN_UNEXPECTED_OUTPUT")

                fake_proc_thm = subprocess.CompletedProcess(
                    ["lean"], 0, stdout="'Wrong.thm' does not depend on any axioms\n", stderr=""
                )
                with mock.patch.object(subprocess, "run", return_value=fake_proc_thm):
                    with self.assertRaises(s96.S96Error) as e8:
                        ver.verify_lean_file(lean_file, check_pinned_sha=True)
                    self.assertEqual(e8.exception.code, "LEAN_THEOREM_SET_MISMATCH")

                empty_out = subprocess.CompletedProcess(["lean"], 0, stdout="", stderr="")
                with mock.patch.object(subprocess, "run", return_value=empty_out):
                    with self.assertRaises(s96.S96Error) as e_zero:
                        ver.verify_lean_file(other_l, check_pinned_sha=False)
                    self.assertEqual(e_zero.exception.code, "LEAN_NO_THEOREMS_VERIFIED")

            if has_lean:
                ok_res = ver.verify_lean_file(other_l, check_pinned_sha=False)
                self.assertEqual(ok_res["theorems_verified"], 1)
                cl_l = tdir / "classical.lean"
                cl_l.write_text(
                    "theorem use_em (p : Prop) : p ∨ ¬ p := Classical.em p\n#print axioms use_em\n",
                    encoding="utf-8",
                )
                with self.assertRaises(s96.S96Error) as e4:
                    ver.verify_lean_file(cl_l, check_pinned_sha=False)
                self.assertEqual(e4.exception.code, "LEAN_FORBIDDEN_AXIOM")

                bad_l = tdir / "bad.lean"
                bad_l.write_text("theorem bad : 1 = 2 := rfl\n", encoding="utf-8")
                with self.assertRaises(s96.S96Error) as e5:
                    ver.verify_lean_file(bad_l, check_pinned_sha=False)
                self.assertEqual(e5.exception.code, "LEAN_COMPILE_FAILED")

            # _find_lean_binary discovery branches (LEAN_BIN valid/invalid, PATH, $HOME/.elan/bin, empty HOME, missing)
            dummy_lean = tdir / "fake_lean"
            dummy_lean.write_text("#!/bin/sh\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"LEAN_BIN": str(dummy_lean)}):
                self.assertEqual(ver._find_lean_binary(), str(dummy_lean))
            with mock.patch.dict(os.environ, {"LEAN_BIN": str(tdir / "no_such_lean")}):
                with self.assertRaises(s96.S96Error) as e_eb:
                    ver._find_lean_binary()
                self.assertEqual(e_eb.exception.code, "LEAN_BINARY_NOT_FOUND")
            with mock.patch.dict(os.environ, {"LEAN_BIN": "", "HOME": str(tdir)}):
                with mock.patch.object(ver.shutil, "which", return_value="/mock/lean"):
                    self.assertEqual(ver._find_lean_binary(), "/mock/lean")
                with mock.patch.object(ver.shutil, "which", return_value=None):
                    with self.assertRaises(s96.S96Error) as e9:
                        ver._find_lean_binary()
                    self.assertEqual(e9.exception.code, "LEAN_BINARY_NOT_FOUND")
                    elan_bin = tdir / ".elan" / "bin"
                    elan_bin.mkdir(parents=True)
                    (elan_bin / "lean").write_text("#!/bin/sh\n", encoding="utf-8")
                    self.assertEqual(ver._find_lean_binary(), str(elan_bin / "lean"))
            with mock.patch.object(ver.os, "environ", {}):
                with mock.patch.object(ver.shutil, "which", return_value=None):
                    with self.assertRaises(s96.S96Error) as e10:
                        ver._find_lean_binary()
                    self.assertEqual(e10.exception.code, "LEAN_BINARY_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
