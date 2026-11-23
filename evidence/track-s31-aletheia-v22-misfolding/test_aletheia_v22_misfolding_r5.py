"""R5 verification, adversarial Zone-B, mutation-killing, and TOCTOU test suite for Track S31.

Zero external dependencies, zero IEEE-754 floats, zero bare asserts, zero RNG.
"""
from __future__ import annotations

import ast
from contextlib import redirect_stderr, redirect_stdout
import copy
import ctypes
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import aletheia_v22_misfolding_audit as audit
import aletheia_v22_misfolding_oracle as oracle

CERT_PATH = ROOT / audit.DEFAULT_CERT_NAME


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(f"S31_R5_FAILED: {msg}")


def _expect_err(fn, code: str | None = None, label: str = "") -> None:
    try:
        fn()
    except oracle.AletheiaV22Error as exc:
        if code is not None:
            _check(exc.code == code, f"{label}: expected {code}, got {exc.code} ({exc})")
        return
    raise RuntimeError(f"Expected AletheiaV22Error({code}) for {label}")


class _EvilPath(type(Path())):
    pass


class _StrSub(str):
    pass


class _IntSub(int):
    pass


class TestTrackS31AletheiaV22Misfolding(unittest.TestCase):
    def test_01_ast_purity_zero_floats_zero_asserts_and_cert_pillars(self) -> None:
        for name in (
            "aletheia_v22_misfolding_oracle.py",
            "aletheia_v22_misfolding_audit.py",
            "test_aletheia_v22_misfolding_r5.py",
        ):
            src = (ROOT / name).read_text(encoding="utf-8")
            tree = ast.parse(src, filename=name)
            asserts = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Assert)]
            floats = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Constant) and type(n.value) is float]
            float_calls = [
                n.lineno for n in ast.walk(tree)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "float"
            ]
            _check(len(asserts) == 0, f"bare asserts in {name}: {asserts}")
            _check(len(floats) == 0, f"float literals in {name}: {floats}")
            _check(len(float_calls) == 0, f"float() calls in {name}: {float_calls}")

        res = audit.verify_certificate_file(CERT_PATH)
        _check(res["valid"] is True, "committed certificate invalid")
        cert = json.loads(CERT_PATH.read_text(encoding="utf-8"))
        p = cert["payload"]

        # Pillar 1 checks
        p1 = p["pillar_1_dpi_misfolding_separation"]
        toy = p1["toy_64x16_iso_frobenius_separation"]
        _check(toy["frobenius_energy_residual"] == "0", "iso-Frobenius residual nonzero")
        _check(toy["benign_diffuse_quantization"]["row_concentration_ratio"] == "1", "benign C_row != 1")
        _check(toy["localized_2row_misfolding"]["row_concentration_ratio"] == "32", "misfolding C_row != 32")
        _check(toy["localized_2row_misfolding"]["support_sparsity_density"] == "1/32", "misfolding rho_nnz != 1/32")
        _check(toy["single_row_saturation_bound"]["row_concentration_ratio"] == "64", "1-row C_row != 64")
        _check(toy["row_concentration_separation_factor"] == "32", "sep factor != 32")
        qwen = p1["qwen25_1p5b_token_embd_analytical_scaling"]
        _check(qwen["two_row_min_concentration_ratio"] == "75968", "Qwen 2-row C_row != 75968")
        r1 = p1["rank1_spectral_and_reversal_detector"]
        _check(r1["abliteration_spectral"]["is_exact_rank_1"] is True, "abliteration not rank-1")
        _check(r1["reversal_5x_spectral"]["is_exact_rank_1"] is True, "reversal not rank-1")
        _check(r1["isotropic_rank4_control_spectral"]["schatten_s4_ratio"] == "1/4", "iso rank-4 S4 != 1/4")
        _check(r1["abliteration_projection"]["gamma_u"] == "0" and r1["abliteration_projection"]["regime"] == "orthogonal_abliteration", "abliteration gamma wrong")
        _check(r1["reversal_5x_projection"]["gamma_u"] == "-5" and r1["reversal_5x_projection"]["regime"] == "mechanism_reversal", "reversal gamma wrong")

        # Pillar 2 checks
        p2 = p["pillar_2_risk_asymmetry_and_bellwethers"]
        w22 = p2["brindle_1_over_22_exact_threshold_witness"]
        _check(w22["k_star"] == 15 and w22["k_14_below_half"] is True and w22["k_15_attacker_gt_half_gt_defender"] is True, "k*(1/22) witness wrong")
        _check(w22["k_100_attacker_gt_99pct"] is True, "k=100 > 99% failed")
        bw_c = p2["bellwether_completeness_brindle_supply"]
        _check(bw_c["omission_witness"]["naive_positive_existence_pass"] is True and bw_c["omission_witness"]["omission_detected"] is True, "Brindle omission wrong")
        _check(bw_c["omission_witness"]["missing_items"] == ["Brindle Supply"], "missing item wrong")
        _check(bw_c["duplicate_substitution_witness"]["cardinality_conserved"] is True and bw_c["duplicate_substitution_witness"]["bijection_exact"] is False, "dup subst wrong")
        _check(bw_c["clean_control"]["bijection_exact"] is True, "clean set wrong")
        bw_r = p2["bellwether_relational_closure_buenos_aires"]
        _check(bw_r["misfolded_witness"]["consistent"] is False and bw_r["clean_control"]["consistent"] is True, "relational closure wrong")

        # Pillar 3 checks
        p3 = p["pillar_3_siliquant_hadamard_bypass_bridge"]
        _check(p3["hadamard_h8_exact_identities"]["symmetric"] is True and p3["hadamard_h8_exact_identities"]["h8_squared_eq_8I"] is True, "H8 id wrong")
        _check(p3["pure_spike_h8_spreading_law"]["coherence_ratio_drop"] == "1/8", "H8 drop != 1/8")
        _check(p3["group128_mlp_spike_bwi_detection"]["group_scale_sq_inflation_factor"] == "256", "scale inflation != 256")
        _check(p3["group128_mlp_spike_bwi_detection"]["spiked_group128"]["exceeds_5sigma_sq_threshold_25"] is True, "5sigma threshold wrong")
        _check(p3["group128_mlp_spike_bwi_detection"]["h8_energy_conservation_exact"] is True, "H8 energy conservation wrong")
        bypass = p3["unquantized_token_embd_bypass_theorem"]
        _check(bypass["post_quant_embd_patch_exact_invariant"] is True, "embd bypass wrong")
        _check(bypass["survival_fraction"] == "1" and bypass["dw_embd_energy_sq"] == bypass["post_quant_embd_energy_sq"], "live survival_fraction wrong")
        _check(bypass["changed_rows_detected"] == [2] and bypass["unchanged_rows_count"] == 3, "per-row SHA-256 changed rows wrong")
        _check(len(bypass["per_row_sha256_base"]) == 4 and bypass["per_row_sha256_base"]["0"] == bypass["per_row_sha256_patched"]["0"], "unchanged row hash mismatch")
        _check(bypass["per_row_sha256_base"]["2"] != bypass["per_row_sha256_patched"]["2"] and bypass["immutable_row_hash_lock_detected_edit"] is True, "per-row hash lock wrong")

        # Pillar 4 checks
        p4 = p["pillar_4_aletheia_v22_governance_cs15_cs19"]
        _check(p4["cs15_constructive_scope_gate"]["pass_control"]["passed"] is True, "CS15 pass wrong")
        _check(p4["cs15_constructive_scope_gate"]["diagnosis_only_unscoped_failure"]["passed"] is False, "CS15 fail wrong")
        _check(p4["cs16_matched_gain_pareto"]["korean_vocab_freeze_confound_overstatement"] == "7/40", "CS16 vocab confound wrong")
        _check(p4["cs16_matched_gain_pareto"]["lora_vs_full_ft_2p64x_flip"]["matched_ratio_fa_over_fb"] == "66/25", "CS16 2.64x wrong")
        _check(p4["cs16_matched_gain_pareto"]["lora_vs_full_ft_2p64x_flip"]["unmatched_vs_matched_sign_flipped"] is True, "CS16 flip wrong")
        _check(p4["cs17_herding_and_sunk_cost"]["score_visible_herding_88pct"]["herding_flagged"] is True, "CS17 herding wrong")
        _check(p4["cs17_herding_and_sunk_cost"]["coordinate_only_control_30pct"]["herding_flagged"] is False, "CS17 coord wrong")
        _check(p4["cs17_herding_and_sunk_cost"]["sunk_cost_escalation_16p2pp"]["escalation_rejected"] is True, "CS17 sunk wrong")
        _check(p4["cs17_herding_and_sunk_cost"]["zero_sunk_cost_control"]["escalation_rejected"] is False, "CS17 clean sunk wrong")
        _check(p4["cs18_abstention_and_tost"]["distinct_synthetic_mismatched_records"] == 300 and p4["cs18_abstention_and_tost"]["mismatched_300_abstained_count"] == 300, "CS18 300/300 distinct wrong")
        _check(p4["cs18_abstention_and_tost"]["tost_true_equivalence"]["verdict"] == "EQUIVALENT_NULL", "CS18 TOST equiv wrong")
        _check(p4["cs18_abstention_and_tost"]["tost_null_overstatement_blocked"]["null_overstatement_blocked"] is True, "CS18 overstate wrong")
        _check(p4["cs19_ast_leak_and_sha256_gate"]["ast_leaked_fixture"]["passed"] is False, "CS19 AST leak missed")
        _check(p4["cs19_ast_leak_and_sha256_gate"]["ast_clean_control"]["passed"] is True, "CS19 AST false positive")
        _check(p4["cs19_ast_leak_and_sha256_gate"]["sha256_prefix8_hallucination_fixture"]["prefix8_hallucination_caught"] is True, "CS19 SHA hallucination missed")
        _check(p4["cs19_ast_leak_and_sha256_gate"]["sha256_exact_control"]["full_match"] is True, "CS19 SHA exact wrong")

        # Pillar 5 checks
        p5 = p["pillar_5_three_channel_provenance_airlock"]
        _check(p5["clean_compliant_record"]["verdict"] == "ALLOW", "P5 clean not ALLOW")
        _check(len(p5["negative_controls"]) == 5 and all(v["verdict"] == "DENY" for v in p5["negative_controls"].values()), "P5 neg controls wrong")

    def test_02_oracle_primitives_boundaries_boolops_and_refusal_guards(self) -> None:
        # Basic validators
        _check(oracle.require_exact_int(5, "x", lo=5, hi=5) == 5, "exact int lo==hi")
        _expect_err(lambda: oracle.require_exact_int(True, "x"), "INVALID_INT", "bool int")
        _expect_err(lambda: oracle.require_exact_int(_IntSub(5), "x"), "INVALID_INT", "int subclass")
        _expect_err(lambda: oracle.require_exact_int(5, "x", lo=True), "INVALID_BOUND", "bool lo")
        _expect_err(lambda: oracle.require_exact_int(5, "x", hi=True), "INVALID_BOUND", "bool hi")
        _expect_err(lambda: oracle.require_exact_int(4, "x", lo=5), "INT_OUT_OF_RANGE", "val < lo")
        _expect_err(lambda: oracle.require_exact_int(6, "x", hi=5), "INT_OUT_OF_RANGE", "val > hi")
        _check(oracle.require_exact_bool(False, "b") is False, "valid bool")
        _expect_err(lambda: oracle.require_exact_bool(0, "b"), "INVALID_BOOL", "int bool")
        _check(oracle.require_exact_str("", "s") == "", "empty str ok when non_empty=False")
        _expect_err(lambda: oracle.require_exact_str(123, "s"), "INVALID_STR", "int str")
        _expect_err(lambda: oracle.require_exact_str("", "s", non_empty=True), "EMPTY_STR", "empty str")
        _expect_err(lambda: oracle.require_exact_fraction(1, "f"), "INVALID_RATIONAL", "int frac")

        # Strict ASCII-only rational & int parsers (reject Unicode digits/superscripts/zero den/too long)
        _check(oracle.is_ascii_digits("0123456789") is True, "ascii digits ok")
        _check(oracle.is_ascii_digits("") is False, "empty ascii digits")
        _check(oracle.is_ascii_digits("12a") is False, "alpha in digits")
        _check(oracle.is_ascii_digits("²") is False and oracle.is_ascii_digits("١٢") is False and oracle.is_ascii_digits("①") is False, "unicode digits rejected")
        _check(oracle.parse_exact_int_str("-42") == -42 and oracle.parse_exact_int_str("0") == 0, "int str")
        _check(oracle.parse_exact_int_str("9" * 1200) > 0, "1200-digit boundary ok")
        _expect_err(lambda: oracle.parse_exact_int_str("9" * 1201), "INT_STR_TOO_LONG", "1201 digits")
        _expect_err(lambda: oracle.parse_exact_int_str("²"), "INVALID_INT_STR", "superscript int")
        _expect_err(lambda: oracle.parse_exact_int_str("١٢"), "INVALID_INT_STR", "arabic int")
        _expect_err(lambda: oracle.parse_exact_int_str("-"), "INVALID_INT_STR", "bare minus")
        _check(oracle.parse_exact_rational("-7/3") == Fraction(-7, 3), "neg rational")
        _check(oracle.parse_exact_rational("1/" + "9" * 1200) > 0, "1200-digit den ok")
        _expect_err(lambda: oracle.parse_exact_rational("1/2/3"), "INVALID_RATIONAL_STR", "two slashes")
        _expect_err(lambda: oracle.parse_exact_rational("1/-2"), "INVALID_RATIONAL_DEN", "neg den")
        _expect_err(lambda: oracle.parse_exact_rational("1/²"), "INVALID_RATIONAL_DEN", "unicode den")
        _expect_err(lambda: oracle.parse_exact_rational("1/" + "9" * 1201), "INT_STR_TOO_LONG", "1201-digit den")
        _expect_err(lambda: oracle.parse_exact_rational("1/0"), "ZERO_DENOMINATOR", "zero den")
        _expect_err(lambda: oracle.parse_exact_rational("1.5"), "INVALID_INT_STR", "float str")

        # format_rational 4000-bit boundary on both num & den
        ok_big = (1 << oracle.MAX_RATIONAL_BITS) - 1
        too_big = 1 << oracle.MAX_RATIONAL_BITS
        _check(len(oracle.format_rational(Fraction(ok_big, 1))) > 0, "4000-bit num ok")
        _check("/" in oracle.format_rational(Fraction(1, ok_big)), "4000-bit den ok")
        _expect_err(lambda: oracle.format_rational(Fraction(too_big, 1)), "RATIONAL_TOO_LARGE", "4001-bit num")
        _expect_err(lambda: oracle.format_rational(Fraction(1, too_big)), "RATIONAL_TOO_LARGE", "4001-bit den")

        # Matrix, DPI, spectral, directional guards
        m1 = [[Fraction(1, 1), Fraction(2, 1)]]
        m2_same_col = [[Fraction(1, 1), Fraction(2, 1)], [Fraction(3, 1), Fraction(4, 1)]]
        _expect_err(lambda: oracle.matrix_diff_exact("bad", m1), "INVALID_MATRIX", "non-list mat")
        _expect_err(lambda: oracle.matrix_diff_exact([], m1), "EMPTY_MATRIX", "empty mat")
        _expect_err(lambda: oracle.matrix_diff_exact(["bad"], m1), "INVALID_VECTOR", "non-list row")
        _expect_err(lambda: oracle.matrix_diff_exact([[]], m1), "EMPTY_VECTOR", "empty row")
        _expect_err(lambda: oracle.matrix_diff_exact([[Fraction(1, 1)], [Fraction(1, 1), Fraction(2, 1)]], m1), "RAGGED_MATRIX", "ragged")
        _expect_err(lambda: oracle.matrix_diff_exact(m1, m2_same_col), "SHAPE_MISMATCH", "row mismatch same col")
        _expect_err(lambda: oracle.matrix_diff_exact(m1, [[Fraction(1, 1)]]), "SHAPE_MISMATCH", "col mismatch")
        _expect_err(lambda: oracle.dpi_metrics_exact([[Fraction(0, 1)]]), "ZERO_PATCH", "zero dpi")
        _expect_err(lambda: oracle.spectral_rank1_dominance_exact([[Fraction(0, 1)]]), "ZERO_PATCH", "zero spectral")

        u1 = [Fraction(1, 1)]
        _expect_err(lambda: oracle.directional_projection_ratio_exact(m1, m2_same_col, u1, [Fraction(1, 1), Fraction(1, 1)]), "SHAPE_MISMATCH", "dir row mismatch same col")
        _expect_err(lambda: oracle.directional_projection_ratio_exact(m1, [[Fraction(1, 1)]], u1, u1), "SHAPE_MISMATCH", "dir col mismatch")
        _expect_err(lambda: oracle.directional_projection_ratio_exact(m1, m1, [Fraction(1, 1), Fraction(1, 1)], [Fraction(1, 1), Fraction(1, 1)]), "DIM_MISMATCH", "u mismatch")
        _expect_err(lambda: oracle.directional_projection_ratio_exact(m1, m1, u1, u1), "DIM_MISMATCH", "v mismatch")
        _expect_err(lambda: oracle.directional_projection_ratio_exact([[Fraction(0, 1)]], [[Fraction(1, 1)]], u1, u1), "ZERO_BASELINE_PROJECTION", "zero base proj")
        _check(oracle.directional_projection_ratio_exact([[Fraction(2, 1)]], [[Fraction(2, 1)]], u1, u1)["regime"] == "preserved", "preserved")
        _check(oracle.directional_projection_ratio_exact([[Fraction(2, 1)]], [[Fraction(1, 1)]], u1, u1)["regime"] == "attenuated", "attenuated")
        _check(oracle.directional_projection_ratio_exact([[Fraction(2, 1)]], [[Fraction(4, 1)]], u1, u1)["regime"] == "amplified", "amplified")

        # Pillar 2 guards (pass@k, threshold, set conservation, relational closure)
        _expect_err(lambda: oracle.pass_pow_k_exact(Fraction(0, 1), 1), "INVALID_RATE", "p==0")
        _expect_err(lambda: oracle.pass_pow_k_exact(Fraction(1, 1), 1), "INVALID_RATE", "p==1")
        _expect_err(lambda: oracle.pass_pow_k_exact(Fraction(1, 2), 0), "INT_OUT_OF_RANGE", "k==0")
        _expect_err(lambda: oracle.asymmetry_threshold_exact(Fraction(0, 1)), "INVALID_RATE", "thresh p==0")
        _expect_err(lambda: oracle.asymmetry_threshold_exact(Fraction(1, 1)), "INVALID_RATE", "thresh p==1")
        _expect_err(lambda: oracle.asymmetry_threshold_exact(Fraction(1, 2), Fraction(0, 1)), "INVALID_TARGET_RISK", "risk==0")
        _expect_err(lambda: oracle.asymmetry_threshold_exact(Fraction(1, 2), Fraction(1, 1)), "INVALID_TARGET_RISK", "risk==1")
        _expect_err(lambda: oracle.asymmetry_threshold_exact(Fraction(1, 22), Fraction(1, 2), max_k=14), "THRESHOLD_LIMIT_EXCEEDED", "k*>max_k")
        _check(oracle.asymmetry_threshold_exact(Fraction(1, 22), Fraction(1, 2), max_k=15)["k_star"] == 15, "exact k*==max_k")
        _expect_err(lambda: oracle.asymmetry_threshold_exact(Fraction(1, 2), Fraction(1, 2), max_k=0), "INT_OUT_OF_RANGE", "max_k==0")
        _check(oracle.asymmetry_threshold_exact(Fraction(3, 4), Fraction(1, 2))["k_star"] == 1, "k*==1")

        _expect_err(lambda: oracle.certify_set_cardinality_conservation("bad", ["a"]), "INVALID_SET_LIST", "bad supplied")
        _expect_err(lambda: oracle.certify_set_cardinality_conservation(["a"], "bad"), "INVALID_SET_LIST", "bad extracted")
        _expect_err(lambda: oracle.certify_set_cardinality_conservation([], []), "EMPTY_SUPPLIED", "empty supplied")
        extra_only = oracle.certify_set_cardinality_conservation(["a"], ["a", "b"])
        _check(extra_only["bijection_exact"] is False and extra_only["missing_items"] == [] and extra_only["extra_items"] == ["b"], "extra-only bijection BoolOp")

        _expect_err(lambda: oracle.certify_relational_closure([], [("a", "b")]), "INVALID_KB", "bad kb")
        _expect_err(lambda: oracle.certify_relational_closure({}, [("a", "b")]), "EMPTY_KB", "empty kb")
        _expect_err(lambda: oracle.certify_relational_closure({"a": "b"}, "bad"), "INVALID_CLAIMS", "bad claims")
        _expect_err(lambda: oracle.certify_relational_closure({"a": "b"}, []), "EMPTY_CLAIMS", "empty claims")
        _expect_err(lambda: oracle.certify_relational_closure({"a": "b"}, [["a", "b"]]), "INVALID_CLAIM_PAIR", "list pair")
        _expect_err(lambda: oracle.certify_relational_closure({"a": "b"}, [("a",)]), "INVALID_CLAIM_PAIR", "len1 pair")
        unk_rel = oracle.certify_relational_closure({"a": "b"}, [("z", "b")])
        _check(unk_rel["consistent"] is False and unk_rel["violations"][0]["reason"] == "unknown_city", "unknown city")

        # Pillar 3 guards (Hadamard, matvec, coherence, block quantizer)
        _check(oracle.build_hadamard_exact(1) == [[1]], "H1")
        _expect_err(lambda: oracle.build_hadamard_exact(3), "INVALID_HADAMARD_ORDER", "H3 non-pow2")
        _expect_err(lambda: oracle.matvec_int_frac("bad", [Fraction(1, 1)]), "INVALID_MATRIX", "matvec bad")
        _expect_err(lambda: oracle.matvec_int_frac([[1], [1]], [Fraction(1, 1)]), "DIM_MISMATCH", "matvec row dim")
        _expect_err(lambda: oracle.matvec_int_frac(["bad"], [Fraction(1, 1)]), "INVALID_MATRIX", "matvec bad row")
        _expect_err(lambda: oracle.matvec_int_frac([[1, 2]], [Fraction(1, 1)]), "DIM_MISMATCH", "matvec col dim")
        _expect_err(lambda: oracle.peak_coherence_ratio_exact([Fraction(0, 1)]), "ZERO_VECTOR", "zero vec")
        _expect_err(lambda: oracle.apply_block_quantizer_only([[Fraction(1, 1)]], [[Fraction(1, 1)]], 0, 1), "INT_OUT_OF_RANGE", "step_num=0")
        _expect_err(lambda: oracle.apply_block_quantizer_only([[Fraction(1, 1)]], [[Fraction(1, 1)]], 1, 0), "INT_OUT_OF_RANGE", "step_den=0")

        # Pillar 4 guards (CS-15..CS-19 + exact BoolOp operand isolation)
        cs15_scoped_1 = oracle.certify_cs15_scope_gate(
            has_constructive_fix=True, beats_strongest_baseline=True, model_families_tested=1, scoped_single_family_honestly=True
        )
        _check(cs15_scoped_1["passed"] is True, "CS15 scoped single family must pass")
        cs15_unscoped_1 = oracle.certify_cs15_scope_gate(
            has_constructive_fix=True, beats_strongest_baseline=True, model_families_tested=1, scoped_single_family_honestly=False
        )
        _check(cs15_unscoped_1["flags"] == ["UNSCOPED_SINGLE_FAMILY_OVERCLAIM"], "CS15 unscoped 1 family")

        # CS-16 curve & sign-flip BoolOp isolation
        c_ok = [(Fraction(0, 1), Fraction(0, 1)), (Fraction(1, 1), Fraction(1, 2))]
        _expect_err(lambda: oracle.matched_gain_pareto_compare_exact("bad", c_ok, Fraction(1, 2)), "INVALID_CURVE", "bad curve")
        _expect_err(lambda: oracle.matched_gain_pareto_compare_exact([(Fraction(0, 1), Fraction(0, 1))], c_ok, Fraction(0, 1)), "SHORT_CURVE", "short curve")
        _expect_err(lambda: oracle.matched_gain_pareto_compare_exact([[Fraction(0, 1), Fraction(0, 1)], (Fraction(1, 1), Fraction(1, 1))], c_ok, Fraction(1, 2)), "INVALID_POINT", "list pt")
        _expect_err(lambda: oracle.matched_gain_pareto_compare_exact([(Fraction(0, 1),), (Fraction(1, 1), Fraction(1, 1))], c_ok, Fraction(1, 2)), "INVALID_POINT", "len1 pt")
        _expect_err(lambda: oracle.matched_gain_pareto_compare_exact([(Fraction(1, 1), Fraction(0, 1)), (Fraction(1, 1), Fraction(1, 1))], c_ok, Fraction(1, 1)), "NON_MONOTONE_GAIN", "eq gain")
        _expect_err(lambda: oracle.matched_gain_pareto_compare_exact(c_ok, c_ok, Fraction(-1, 10)), "OUT_OF_OVERLAP", "g* < min")
        _expect_err(lambda: oracle.matched_gain_pareto_compare_exact(c_ok, c_ok, Fraction(11, 10)), "OUT_OF_OVERLAP", "g* > max")
        _expect_err(lambda: oracle.matched_gain_pareto_compare_exact(c_ok, c_ok, Fraction(0, 1)), "NONPOSITIVE_BASELINE_FORGETTING", "fb==0")
        # Test exact endpoint boundaries g_star == min & g_star == max + all sign-flip BoolOp combinations
        c_same_pos = oracle.matched_gain_pareto_compare_exact(
            [(Fraction(0, 1), Fraction(1, 4)), (Fraction(1, 1), Fraction(3, 4))],
            [(Fraction(0, 1), Fraction(1, 8)), (Fraction(1, 1), Fraction(1, 2))],
            Fraction(1, 1),
        )
        _check(c_same_pos["unmatched_vs_matched_sign_flipped"] is False, "same pos sign")
        c_same_neg = oracle.matched_gain_pareto_compare_exact(
            [(Fraction(0, 1), Fraction(1, 8)), (Fraction(1, 1), Fraction(1, 4))],
            [(Fraction(0, 1), Fraction(1, 4)), (Fraction(1, 1), Fraction(1, 2))],
            Fraction(0, 1),
        )
        _check(c_same_neg["unmatched_vs_matched_sign_flipped"] is False, "same neg sign")
        c_rev_flip = oracle.matched_gain_pareto_compare_exact(
            [(Fraction(0, 1), Fraction(0, 1)), (Fraction(3, 10), Fraction(5, 88)), (Fraction(8, 10), Fraction(25, 100))],
            [(Fraction(0, 1), Fraction(0, 1)), (Fraction(3, 10), Fraction(15, 100))],
            Fraction(3, 10),
        )
        _check(c_rev_flip["unmatched_vs_matched_sign_flipped"] is True, "reversed sign flip")
        c_eq_unmatched = oracle.matched_gain_pareto_compare_exact(
            [(Fraction(0, 1), Fraction(0, 1)), (Fraction(1, 2), Fraction(1, 4)), (Fraction(1, 1), Fraction(1, 2))],
            [(Fraction(0, 1), Fraction(0, 1)), (Fraction(1, 2), Fraction(1, 8)), (Fraction(1, 1), Fraction(1, 2))],
            Fraction(1, 2),
        )
        _check(c_eq_unmatched["unmatched_vs_matched_sign_flipped"] is False, "zero unmatched diff")
        c_eq_matched = oracle.matched_gain_pareto_compare_exact(
            [(Fraction(0, 1), Fraction(0, 1)), (Fraction(1, 2), Fraction(1, 4)), (Fraction(1, 1), Fraction(3, 4))],
            [(Fraction(0, 1), Fraction(0, 1)), (Fraction(1, 2), Fraction(1, 4)), (Fraction(1, 1), Fraction(1, 2))],
            Fraction(1, 2),
        )
        _check(c_eq_matched["unmatched_vs_matched_sign_flipped"] is False, "zero matched diff")

        # CS-17 herding & sunk-cost guards
        _expect_err(lambda: oracle.detect_herding_hhi_exact("bad"), "INVALID_COUNTS", "bad counts")
        _expect_err(lambda: oracle.detect_herding_hhi_exact([5]), "TOO_FEW_BUCKETS", "1 bucket")
        _expect_err(lambda: oracle.detect_herding_hhi_exact([1, 1], Fraction(0, 1)), "INVALID_THRESHOLD", "thresh 0")
        _expect_err(lambda: oracle.detect_herding_hhi_exact([1, 1], Fraction(1, 1)), "INVALID_THRESHOLD", "thresh 1")
        _expect_err(lambda: oracle.detect_herding_hhi_exact([0, 0]), "ZERO_TOTAL_COUNTS", "zero sum")
        _check(oracle.detect_herding_hhi_exact([1, 1], Fraction(1, 2))["herding_flagged"] is False, "exact 1/2 not flagged")

        _check(oracle.detect_sunk_cost_escalation_exact(Fraction(0, 1), Fraction(1, 1), Fraction(0, 1))["escalation_rejected"] is True, "sunk boundaries 0/1")
        _check(oracle.detect_sunk_cost_escalation_exact(Fraction(1, 1), Fraction(0, 1), Fraction(0, 1))["escalation_rejected"] is False, "sunk boundaries 1/0")
        _expect_err(lambda: oracle.detect_sunk_cost_escalation_exact(Fraction(-1, 10), Fraction(1, 2)), "INVALID_ALLOC", "base < 0")
        _expect_err(lambda: oracle.detect_sunk_cost_escalation_exact(Fraction(11, 10), Fraction(1, 2)), "INVALID_ALLOC", "base > 1")
        _expect_err(lambda: oracle.detect_sunk_cost_escalation_exact(Fraction(1, 2), Fraction(-1, 10)), "INVALID_ALLOC", "sunk < 0")
        _expect_err(lambda: oracle.detect_sunk_cost_escalation_exact(Fraction(1, 2), Fraction(11, 10)), "INVALID_ALLOC", "sunk > 1")
        _expect_err(lambda: oracle.detect_sunk_cost_escalation_exact(Fraction(1, 2), Fraction(1, 2), Fraction(-1, 10)), "INVALID_SHIFT", "max_shift < 0")

        # CS-18 TOST exact boundaries (kills SWAP & SUBCOND_DEL on ci_lo > -delta and ci_hi < delta)
        _expect_err(lambda: oracle.evaluate_four_state_tost_exact(evidence_matched=True, ci_lo=Fraction(1, 2), ci_hi=Fraction(1, 4), equiv_delta=Fraction(1, 10)), "INVALID_CI", "lo > hi")
        _expect_err(lambda: oracle.evaluate_four_state_tost_exact(evidence_matched=True, ci_lo=Fraction(0, 1), ci_hi=Fraction(0, 1), equiv_delta=Fraction(0, 1)), "INVALID_DELTA", "delta == 0")
        _check(oracle.evaluate_four_state_tost_exact(evidence_matched=False, ci_lo=Fraction(1, 2), ci_hi=Fraction(3, 4), equiv_delta=Fraction(1, 10))["verdict"] == "UNDETERMINABLE", "unmatched positive CI must abstain")
        _check(oracle.evaluate_four_state_tost_exact(evidence_matched=True, ci_lo=Fraction(-1, 10), ci_hi=Fraction(9, 100), equiv_delta=Fraction(1, 10))["verdict"] == "UNDETERMINABLE", "lo == -delta rejected")
        _check(oracle.evaluate_four_state_tost_exact(evidence_matched=True, ci_lo=Fraction(-9, 100), ci_hi=Fraction(1, 10), equiv_delta=Fraction(1, 10))["verdict"] == "UNDETERMINABLE", "hi == +delta rejected")
        _check(oracle.evaluate_four_state_tost_exact(evidence_matched=True, ci_lo=Fraction(0, 1), ci_hi=Fraction(0, 1), equiv_delta=Fraction(1, 10))["verdict"] == "EQUIVALENT_NULL", "lo==hi==0 ok")

        # CS-19 AST (all 5 store forms + subscript-index FP immunity) & SHA-256 guards + per-row SHA-256 helper
        row_h = oracle.token_embd_row_hashes_exact([[Fraction(1, 2)], [Fraction(3, 4)]])
        _check(row_h["rows"] == 2 and len(row_h["row_hashes"]) == 2 and len(row_h["manifest_sha256"]) == 64, "token_embd_row_hashes_exact")
        _expect_err(lambda: oracle.token_embd_row_hashes_exact([]), "EMPTY_MATRIX", "empty row hash mat")

        _expect_err(lambda: oracle.scan_ast_answer_key_leaks("def bad(:\n"), "INVALID_PYTHON_SOURCE", "bad syntax")
        ann_none = oracle.scan_ast_answer_key_leaks("s_curr: int\nother = 1\n")
        _check(ann_none["passed"] is True, "AnnAssign value=None")
        ann_leak = oracle.scan_ast_answer_key_leaks("s_curr: int = s_exact\n")
        _check(ann_leak["passed"] is False and ann_leak["leak_count"] == 1 and ann_leak["findings"][0]["store_kind"] == "AnnAssign", "AnnAssign leak")
        aug_leak = oracle.scan_ast_answer_key_leaks("s_curr += s_exact\n")
        _check(aug_leak["passed"] is False and aug_leak["findings"][0]["store_kind"] == "AugAssign", "AugAssign leak")
        walrus_leak = oracle.scan_ast_answer_key_leaks("if (s_curr := s_exact):\n    pass\n")
        _check(walrus_leak["passed"] is False and walrus_leak["findings"][0]["store_kind"] == "NamedExpr", "NamedExpr leak")
        attr_leak = oracle.scan_ast_answer_key_leaks("obj.s_curr = obj.s_exact\n")
        _check(attr_leak["passed"] is False and attr_leak["findings"][0]["candidate_vars"] == ["s_curr"] and attr_leak["findings"][0]["oracle_vars"] == ["s_exact"], "Attribute leak")
        sub_leak = oracle.scan_ast_answer_key_leaks("arr[0] = s_exact\n")
        _check(sub_leak["passed"] is False and sub_leak["findings"][0]["candidate_vars"] == ["arr"], "Subscript store leak")
        tup_leak = oracle.scan_ast_answer_key_leaks("a, s_curr = 0, s_exact\n")
        _check(tup_leak["passed"] is False and tup_leak["leak_count"] == 1, "Tuple unpack leak")
        star_leak = oracle.scan_ast_answer_key_leaks("*s_curr, = [s_exact]\n")
        _check(star_leak["passed"] is False and star_leak["leak_count"] == 1, "Starred target leak")
        # S31-BUG-03 zero false positive on subscript index read!
        sub_idx_clean = oracle.scan_ast_answer_key_leaks("buf[s_curr] = s_exact\n")
        _check(sub_idx_clean["passed"] is True and sub_idx_clean["leak_count"] == 0, "subscript index FP must not trigger")
        lhs_only = oracle.scan_ast_answer_key_leaks("s_curr = other_var\n")
        _check(lhs_only["passed"] is True, "lhs-only clean")
        rhs_only = oracle.scan_ast_answer_key_leaks("err = s_exact\n")
        _check(rhs_only["passed"] is True, "rhs-only clean")

        _expect_err(lambda: oracle.verify_sha256_digest_exact("a" * 63, b"x"), "INVALID_SHA256_FORMAT", "len 63")
        _expect_err(lambda: oracle.verify_sha256_digest_exact("A" * 64, b"x"), "INVALID_SHA256_FORMAT", "uppercase hex")
        _expect_err(lambda: oracle.verify_sha256_digest_exact("a" * 64, "notbytes"), "INVALID_BYTES", "str bytes")
        wrong_prefix = oracle.verify_sha256_digest_exact("0" * 64, b"aletheia")
        _check(wrong_prefix["prefix8_match"] is False and wrong_prefix["prefix8_hallucination_caught"] is False, "wrong prefix BoolOp")

        # Pillar 5 airlock guards
        good_rec = {
            "token_embd_immutable_lock": True,
            "token_embd_digest_match": True,
            "max_block_dpi_ratio": Fraction(1, 1),
            "dpi_threshold": Fraction(1, 1),
            "cross_model_kv_reuse": False,
            "evicted_entity_mentions_remaining": 0,
            "corpus_provenance_tagged": True,
            "pii_binding_leak_tested": True,
            "recall_cot_off": Fraction(0, 1),
            "recall_cot_on": Fraction(1, 1),
            "max_mode_transfer_gap": Fraction(1, 1),
        }
        _check(oracle.evaluate_three_channel_airlock(good_rec)["verdict"] == "ALLOW", "airlock exact boundaries 0/1")
        good_rec_b = dict(good_rec); good_rec_b["recall_cot_off"] = Fraction(1, 1); good_rec_b["recall_cot_on"] = Fraction(0, 1)
        _check(oracle.evaluate_three_channel_airlock(good_rec_b)["verdict"] == "ALLOW", "airlock exact boundaries 1/0")
        good_rec_g0 = dict(good_rec); good_rec_g0["recall_cot_off"] = Fraction(1, 1); good_rec_g0["recall_cot_on"] = Fraction(1, 1); good_rec_g0["max_mode_transfer_gap"] = Fraction(0, 1)
        _check(oracle.evaluate_three_channel_airlock(good_rec_g0)["verdict"] == "ALLOW", "airlock exact boundary gap==0")
        _expect_err(lambda: oracle.evaluate_three_channel_airlock([]), "INVALID_AIRLOCK_RECORD", "list rec")
        bad_keys = dict(good_rec); del bad_keys["dpi_threshold"]
        _expect_err(lambda: oracle.evaluate_three_channel_airlock(bad_keys), "INVALID_AIRLOCK_KEYS", "missing key")
        for field, bad_val, code in (
            ("max_block_dpi_ratio", Fraction(1, 2), "INVALID_DPI"),
            ("dpi_threshold", Fraction(1, 2), "INVALID_DPI"),
            ("recall_cot_off", Fraction(-1, 10), "INVALID_RECALL"),
            ("recall_cot_off", Fraction(11, 10), "INVALID_RECALL"),
            ("recall_cot_on", Fraction(-1, 10), "INVALID_RECALL"),
            ("recall_cot_on", Fraction(11, 10), "INVALID_RECALL"),
            ("max_mode_transfer_gap", Fraction(-1, 10), "INVALID_GAP"),
        ):
            r_bad = dict(good_rec); r_bad[field] = bad_val
            _expect_err(lambda r=r_bad: oracle.evaluate_three_channel_airlock(r), code, f"airlock {field}")
        # Exercise remaining DENY flags (embd lock disabled, provenance untagged, pii untested)
        for field, val, vtag in (
            ("token_embd_immutable_lock", False, "CH1_TOKEN_EMBD_LOCK_DISABLED"),
            ("corpus_provenance_tagged", False, "CH3_MISSING_CORPUS_PROVENANCE"),
            ("pii_binding_leak_tested", False, "CH3_MISSING_PII_BINDING_AUDIT"),
        ):
            r_f = dict(good_rec); r_f[field] = val
            out_f = oracle.evaluate_three_channel_airlock(r_f)
            _check(out_f["verdict"] == "DENY" and vtag in out_f["violations"], f"airlock flag {vtag}")

    def test_03_zone_b_audit_io_secondary_checks_races_and_cli(self) -> None:
        cert = json.loads(CERT_PATH.read_text(encoding="utf-8"))
        cert_bytes = CERT_PATH.read_bytes()

        # In-memory verify_certificate_dict + secondary_audit_payload tamper checks
        _check(audit.verify_certificate_dict(cert)["valid"] is True, "valid dict")
        _expect_err(lambda: audit.verify_certificate_dict([]), "INVALID_CERT_TYPE", "list cert")
        bad_k = copy.deepcopy(cert); bad_k["extra"] = 1
        _expect_err(lambda: audit.verify_certificate_dict(bad_k), "INVALID_CERT_KEYS", "extra key")
        bad_k2 = copy.deepcopy(cert); del bad_k2["payload"]
        _expect_err(lambda: audit.verify_certificate_dict(bad_k2), "INVALID_CERT_KEYS", "missing key")
        bad_v = copy.deepcopy(cert); bad_v["payload_sha256"] = "0" * 64
        _expect_err(lambda: audit.verify_certificate_dict(bad_v), "CERTIFICATE_MISMATCH", "tampered sha")
        bad_s = copy.deepcopy(cert); bad_s["payload_sha256"] = "\ud800"
        _expect_err(lambda: audit.verify_certificate_dict(bad_s), "INVALID_UTF8_SURROGATE", "surrogate in dict")
        bad_ser = copy.deepcopy(cert); bad_ser["payload"] = {"bad": object()}
        _expect_err(lambda: audit.verify_certificate_dict(bad_ser), "INVALID_JSON_VALUE", "object in dict")
        bad_flt = copy.deepcopy(cert); bad_flt["payload"] = {"bad": 3 / 2}
        _expect_err(lambda: audit.verify_certificate_dict(bad_flt), "INVALID_JSON_VALUE", "float in dict")
        bad_key = copy.deepcopy(cert); bad_key["payload"] = {1: "x"}
        _expect_err(lambda: audit.verify_certificate_dict(bad_key), "INVALID_JSON_KEY", "int key")
        bad_big = copy.deepcopy(cert); bad_big["payload"] = {"n": 1 << oracle.MAX_RATIONAL_BITS}
        _expect_err(lambda: audit.verify_certificate_dict(bad_big), "INT_TOO_LARGE", "4001-bit int")
        _check(audit.parse_strict_json_text('{"n":' + str((1 << oracle.MAX_RATIONAL_BITS) - 1) + ',"z":null,"b":true}', "ok")["z"] is None, "null/bool/4000-bit")

        # Secondary algebraic audit tamper guards (every require_ok in secondary_audit_payload!)
        _expect_err(lambda: audit.secondary_audit_payload([]), "AUDIT_PAYLOAD_TYPE", "list payload")
        p_miss = copy.deepcopy(cert["payload"]); del p_miss["pillar_5_three_channel_provenance_airlock"]
        _expect_err(lambda: audit.secondary_audit_payload(p_miss), "AUDIT_MISSING_PILLAR", "missing pillar")
        tamper_specs = (
            (("pillar_1_dpi_misfolding_separation", "toy_64x16_iso_frobenius_separation", "frobenius_energy_residual"), "1", "AUDIT_P1_ISO_FROB"),
            (("pillar_1_dpi_misfolding_separation", "toy_64x16_iso_frobenius_separation", "row_concentration_separation_factor"), "31", "AUDIT_P1_SEP"),
            (("pillar_1_dpi_misfolding_separation", "rank1_spectral_and_reversal_detector", "reversal_5x_projection", "gamma_u"), "-4", "AUDIT_P1_REV5"),
            (("pillar_1_dpi_misfolding_separation", "rank1_spectral_and_reversal_detector", "abliteration_projection", "gamma_u"), "1", "AUDIT_P1_ABLIT"),
            (("pillar_2_risk_asymmetry_and_bellwethers", "brindle_1_over_22_exact_threshold_witness", "k_star"), 14, "AUDIT_P2_KSTAR"),
            (("pillar_2_risk_asymmetry_and_bellwethers", "brindle_1_over_22_exact_threshold_witness", "k_15_pass_at_k"), "1/2", "AUDIT_P2_SUM"),
            (("pillar_3_siliquant_hadamard_bypass_bridge", "pure_spike_h8_spreading_law", "coherence_ratio_drop"), "1/4", "AUDIT_P3_H8"),
            (("pillar_3_siliquant_hadamard_bypass_bridge", "unquantized_token_embd_bypass_theorem", "post_quant_embd_patch_exact_invariant"), False, "AUDIT_P3_BYPASS"),
            (("pillar_3_siliquant_hadamard_bypass_bridge", "unquantized_token_embd_bypass_theorem", "survival_fraction"), "1/2", "AUDIT_P3_SURV"),
            (("pillar_4_aletheia_v22_governance_cs15_cs19", "cs16_matched_gain_pareto", "lora_vs_full_ft_2p64x_flip", "matched_ratio_fa_over_fb"), "2", "AUDIT_P4_LORA"),
            (("pillar_4_aletheia_v22_governance_cs15_cs19", "cs18_abstention_and_tost", "mismatched_300_abstained_count"), 299, "AUDIT_P4_CS18"),
            (("pillar_4_aletheia_v22_governance_cs15_cs19", "cs18_abstention_and_tost", "distinct_synthetic_mismatched_records"), 299, "AUDIT_P4_CS18"),
            (("pillar_5_three_channel_provenance_airlock", "clean_compliant_record", "verdict"), "DENY", "AUDIT_P5_CLEAN"),
            (("pillar_5_three_channel_provenance_airlock", "negative_controls", "ch1_token_embd_tamper", "verdict"), "ALLOW", "AUDIT_P5_NEG"),
        )
        for path_keys, bad_val, exp_code in tamper_specs:
            p_bad = copy.deepcopy(cert["payload"])
            cur = p_bad
            for k in path_keys[:-1]:
                cur = cur[k]
            cur[path_keys[-1]] = bad_val
            _expect_err(lambda pb=p_bad: audit.secondary_audit_payload(pb), exp_code, f"tamper {exp_code}")

        # S31-BUG-01 fail-closed schema-safe checks on crafted nested missing/wrong-type keys (zero KeyError/TypeError/AttributeError!)
        empty_pillars = {
            "pillar_1_dpi_misfolding_separation": {},
            "pillar_2_risk_asymmetry_and_bellwethers": {},
            "pillar_3_siliquant_hadamard_bypass_bridge": {},
            "pillar_4_aletheia_v22_governance_cs15_cs19": {},
            "pillar_5_three_channel_provenance_airlock": {},
        }
        _expect_err(lambda: audit.secondary_audit_payload(empty_pillars), "AUDIT_P1_SCHEMA", "5 empty pillar dicts")
        c_empty = copy.deepcopy(cert); c_empty["payload"] = empty_pillars
        _expect_err(lambda: audit.verify_certificate_dict(c_empty), "AUDIT_P1_SCHEMA", "dict 5 empty pillar dicts")
        p_null_toy = copy.deepcopy(cert["payload"]); p_null_toy["pillar_1_dpi_misfolding_separation"]["toy_64x16_iso_frobenius_separation"] = None
        _expect_err(lambda: audit.secondary_audit_payload(p_null_toy), "AUDIT_P1_SCHEMA", "null toy")
        p_miss_leaf = copy.deepcopy(cert["payload"]); del p_miss_leaf["pillar_1_dpi_misfolding_separation"]["toy_64x16_iso_frobenius_separation"]["frobenius_energy_residual"]
        _expect_err(lambda: audit.secondary_audit_payload(p_miss_leaf), "AUDIT_P1_ISO_FROB", "missing leaf field")
        p_list_lora = copy.deepcopy(cert["payload"]); p_list_lora["pillar_4_aletheia_v22_governance_cs15_cs19"]["cs16_matched_gain_pareto"]["lora_vs_full_ft_2p64x_flip"] = []
        _expect_err(lambda: audit.secondary_audit_payload(p_list_lora), "AUDIT_P4_SCHEMA", "list lora")
        p_list_neg = copy.deepcopy(cert["payload"]); p_list_neg["pillar_5_three_channel_provenance_airlock"]["negative_controls"] = []
        _expect_err(lambda: audit.secondary_audit_payload(p_list_neg), "AUDIT_P5_SCHEMA", "list neg controls")
        p_empty_neg = copy.deepcopy(cert["payload"]); p_empty_neg["pillar_5_three_channel_provenance_airlock"]["negative_controls"] = {}
        _expect_err(lambda: audit.secondary_audit_payload(p_empty_neg), "AUDIT_P5_NEG_COUNT", "empty neg controls")
        p_bad_neg_entry = copy.deepcopy(cert["payload"])
        p_bad_neg_entry["pillar_5_three_channel_provenance_airlock"]["negative_controls"]["ch1_token_embd_tamper"] = []
        _expect_err(lambda: audit.secondary_audit_payload(p_bad_neg_entry), "AUDIT_P5_NEG", "non-dict neg entry")

        # Strict JSON text parser guards
        _check(audit.parse_strict_json_text("[1,2]", "arr", require_object=False) == [1, 2], "arr")
        _expect_err(lambda: audit.parse_strict_json_text(123, "x"), "INVALID_JSON_TEXT", "non-str")
        _expect_err(lambda: audit.parse_strict_json_text("{}", "x", require_object=1), "INVALID_BOOL", "non-bool")
        _expect_err(lambda: audit.parse_strict_json_text("{\x00}", "x"), "NUL_BYTE_FORBIDDEN", "NUL")
        _expect_err(lambda: audit.parse_strict_json_text('{"a":1,"a":2}', "x"), "DUPLICATE_JSON_KEY", "dup key")
        _expect_err(lambda: audit.parse_strict_json_text('{"a":NaN}', "x"), "NONFINITE_JSON", "NaN")
        _expect_err(lambda: audit.parse_strict_json_text('{"a":1.5}', "x"), "FLOAT_FORBIDDEN", "float")
        _expect_err(lambda: audit.parse_strict_json_text("[1]", "x", require_object=True), "JSON_ROOT_NOT_OBJECT", "list root")
        _expect_err(lambda: audit.parse_strict_json_text("{bad", "x"), "INVALID_JSON", "bad syntax")
        _expect_err(lambda: audit.parse_strict_json_text('{"n":' + "9" * 5000 + "}", "x"), "INVALID_JSON", "5000-digit int")
        _expect_err(lambda: audit.parse_strict_json_text('{"a":"\\ud800"}', "x"), "INVALID_UTF8_SURROGATE", "surrogate val")
        _expect_err(lambda: audit.parse_strict_json_text('{"\\ud800":1}', "x"), "INVALID_UTF8_SURROGATE", "surrogate key")
        ok_d: Any = 1
        for _ in range(audit.MAX_JSON_DEPTH - 1):
            ok_d = [ok_d]
        _check(type(audit.parse_strict_json_text(json.dumps({"x": ok_d}), "d64")) is dict, "depth 64")
        _expect_err(lambda: audit.parse_strict_json_text(json.dumps({"x": [ok_d]}), "d65"), "MAX_DEPTH_EXCEEDED", "depth 65")

        # /proc/kallsyms & /dev/null
        if Path("/proc/kallsyms").exists():
            _expect_err(lambda: audit.read_regular_bytes_capped(Path("/proc/kallsyms"), "k", max_bytes=16), "FILE_TOO_LARGE", "/proc/kallsyms")
        if Path("/dev/null").exists():
            _expect_err(lambda: audit.write_regular_bytes_safe(Path("/dev/null"), b"{}\n", "dn"), "NOT_A_REGULAR_FILE", "/dev/null")

        with tempfile.TemporaryDirectory(prefix="s31_zb_") as td:
            root = Path(td)
            cfile = root / "c.json"
            audit.write_regular_bytes_safe(cfile, cert_bytes, "c")
            audit.write_regular_bytes_safe(cfile, b"{}\n", "c_shorter")
            _check(cfile.read_bytes() == b"{}\n", "atomic shorter overwrite failed")
            audit.write_regular_bytes_safe(cfile, cert_bytes, "c_restore")
            nested_out = root / "new_nested" / "sub" / "w.json"
            audit.write_regular_bytes_safe(nested_out, cert_bytes, "nested_create")
            _check(nested_out.read_bytes() == cert_bytes, "nested dir_fd create")
            _check(audit.read_regular_bytes_capped(cfile, "c", max_bytes=len(cert_bytes)) == cert_bytes, "exact max_bytes")
            _check(audit.read_regular_bytes_capped(cfile, "c64m", max_bytes=audit.MAX_ALLOWED_READ_BYTES) == cert_bytes, "exact 64MiB cap")
            _expect_err(lambda: audit.read_regular_bytes_capped(cfile, "over64m", max_bytes=audit.MAX_ALLOWED_READ_BYTES + 1), "INT_OUT_OF_RANGE", "max_bytes > 64MiB")
            _expect_err(lambda: audit.read_regular_bytes_capped(cfile, "huge", max_bytes=1 << 100), "INT_OUT_OF_RANGE", "S31-BUG-02 1<<100 no OverflowError")
            _expect_err(lambda: audit.read_regular_bytes_capped(cfile, "c", max_bytes=len(cert_bytes) - 1), "FILE_TOO_LARGE", "max_bytes - 1")
            # S31-BUG-02 write_regular_bytes_safe strict exact bytes check BEFORE opening dir/temp
            for bad_pl, lbl in (("not_bytes", "str"), (None, "none"), (bytearray(b"x"), "bytearray")):
                nb_path = root / f"nb_{lbl}.json"
                _expect_err(lambda p=nb_path, pl=bad_pl, l=lbl: audit.write_regular_bytes_safe(p, pl, l), "INVALID_PAYLOAD_BYTES", f"bad payload {lbl}")
                _check(not nb_path.exists(), f"bad payload {lbl} created target")
            _check(not any(".s31_tmp_" in x.name for x in root.iterdir()), "bad payload left temp file")

            # Hardlink protection
            hlink = root / "hlink.json"
            os.link(cfile, hlink)
            try:
                _expect_err(lambda: audit.write_regular_bytes_safe(hlink, b"tamper", "hlink"), "HARDLINK_FORBIDDEN", "hardlink write")
                _check(cfile.read_bytes() == cert_bytes, "hardlink refusal modified target")
            finally:
                hlink.unlink()

            # Path type, NUL, surrogate, root/leaf & dir_fd ancestor guards
            _expect_err(lambda: audit.read_regular_bytes_capped(_EvilPath(cfile), "evil"), "INVALID_PATH_TYPE", "EvilPath r")
            _expect_err(lambda: audit.read_regular_bytes_capped(str(cfile), "str"), "INVALID_PATH_TYPE", "str r")
            _expect_err(lambda: audit.read_regular_bytes_capped(Path("a\x00b.json"), "nul"), "NUL_BYTE_FORBIDDEN", "NUL r")
            _expect_err(lambda: audit.read_regular_bytes_capped(Path("bad_\ud800.json"), "sr"), "INVALID_UTF8_SURROGATE", "surr r")
            _expect_err(lambda: audit.write_regular_bytes_safe(_EvilPath(cfile), cert_bytes, "evil"), "INVALID_PATH_TYPE", "EvilPath w")
            _expect_err(lambda: audit.write_regular_bytes_safe(Path("bad_\ud800.json"), cert_bytes, "sw"), "INVALID_UTF8_SURROGATE", "surr w")
            _expect_err(lambda: audit.read_regular_bytes_capped(Path("/"), "root"), "NOT_A_REGULAR_FILE", "root path")
            _expect_err(lambda: audit.read_regular_bytes_capped(Path("/nonexistent_s31_top"), "top"), "FILE_READ_ERROR", "single-part missing")
            _expect_err(lambda: audit.read_regular_bytes_capped(root / "real_sub" / "..", "dd"), "NOT_A_REGULAR_FILE", "dotdot leaf")
            _expect_err(lambda: audit.read_regular_bytes_capped(root / "no_such_dir" / "missing.json", "nodir"), "FILE_READ_ERROR", "missing anc")
            _check(not (root / "no_such_dir").exists(), "read mode must never mkdir")
            _expect_err(lambda: audit.read_regular_bytes_capped(cfile / "under.json", "ndir"), "FILE_READ_ERROR", "non-dir anc")

            # Missing, dir, FIFO, chmod 000, ro parent
            _expect_err(lambda: audit.read_regular_bytes_capped(root / "missing.json", "miss"), "FILE_READ_ERROR", "missing")
            adir = root / "adir"; adir.mkdir()
            _expect_err(lambda: audit.read_regular_bytes_capped(adir, "adir"), "NOT_A_REGULAR_FILE", "dir r")
            _expect_err(lambda: audit.write_regular_bytes_safe(adir, cert_bytes, "adir"), "NOT_A_REGULAR_FILE", "dir w")
            if hasattr(os, "mkfifo"):
                fifo = root / "pipe.json"; os.mkfifo(fifo)
                _expect_err(lambda: audit.read_regular_bytes_capped(fifo, "fifo"), "NOT_A_REGULAR_FILE", "FIFO r")
                _expect_err(lambda: audit.write_regular_bytes_safe(fifo, cert_bytes, "fifo"), "NOT_A_REGULAR_FILE", "FIFO w")

            no_perm = root / "noperm.json"; no_perm.write_bytes(cert_bytes)
            os.chmod(no_perm, 0o000)
            try:
                if os.geteuid() != 0:
                    _expect_err(lambda: audit.read_regular_bytes_capped(no_perm, "np"), "FILE_READ_ERROR", "chmod 000")
            finally:
                os.chmod(no_perm, 0o600)

            ro_dir = root / "ro_dir"; ro_dir.mkdir()
            os.chmod(ro_dir, 0o500)
            try:
                if os.geteuid() != 0:
                    _expect_err(lambda: audit.write_regular_bytes_safe(ro_dir / "x.json", cert_bytes, "ro"), "FILE_WRITE_ERROR", "ro w")
                    _expect_err(lambda: audit.write_regular_bytes_safe(ro_dir / "newd" / "x.json", cert_bytes, "romk"), "FILE_WRITE_ERROR", "ro mk")
            finally:
                os.chmod(ro_dir, 0o700)

            # Symlinks (read & write, deep ancestor, ..-collapsed), relative-PWD (with symlink decoy for SUBCOND_DEL!), & deleted CWD
            sym = root / "sym.json"; os.symlink(cfile, sym)
            _expect_err(lambda: audit.verify_certificate_file(sym), "SYMLINK_FORBIDDEN", "sym r")
            _expect_err(lambda: audit.write_regular_bytes_safe(sym, cert_bytes, "symw"), "SYMLINK_FORBIDDEN", "sym w")
            real_sub = root / "real_sub" / "nested"; real_sub.mkdir(parents=True)
            (real_sub / "c.json").write_bytes(cert_bytes)
            os.symlink(cfile, real_sub / "pwd_decoy")
            sym_dir = root / "sym_dir"; os.symlink(root / "real_sub", sym_dir)
            _expect_err(lambda: audit.verify_certificate_file(sym_dir / "nested" / "c.json"), "SYMLINK_FORBIDDEN", "deep sym r")
            _expect_err(lambda: audit.write_regular_bytes_safe(sym_dir / "nested" / "w.json", cert_bytes, "deep_sym_w"), "SYMLINK_FORBIDDEN", "deep sym w")
            _expect_err(lambda: audit.verify_certificate_file(sym_dir / ".." / "real_sub" / "nested" / "c.json"), "SYMLINK_FORBIDDEN", "dotdot sym")

            orig_cwd = os.getcwd()
            orig_pwd = os.environ.get("PWD")
            try:
                os.chdir(real_sub)
                os.environ["PWD"] = str(sym_dir / "nested")
                _expect_err(lambda: audit.verify_certificate_file(Path("c.json")), "SYMLINK_ANCESTOR_FORBIDDEN", "sym PWD")
                os.environ["PWD"] = "rel/pwd_decoy"
                _check(audit.read_regular_bytes_capped(Path(".") / "c.json", "c") == cert_bytes, "rel PWD decoy")
                os.environ["PWD"] = str(real_sub)
                _check(audit.read_regular_bytes_capped(Path("c.json"), "c") == cert_bytes, "real PWD")
                os.environ.pop("PWD", None)
                _check(audit.read_regular_bytes_capped(Path("c.json"), "c") == cert_bytes, "unset PWD")

                gone_dir = root / "gone_cwd"; gone_dir.mkdir()
                os.chdir(gone_dir)
                os.rmdir(gone_dir)
                _expect_err(lambda: audit.read_regular_bytes_capped(Path("rel.json"), "r"), "CWD_UNAVAILABLE", "deleted CWD r")
                _expect_err(lambda: audit.write_regular_bytes_safe(Path("rel.json"), cert_bytes, "w"), "CWD_UNAVAILABLE", "deleted CWD w")
                for gone_argv in (["--check", "rel.json"], ["--write", "rel.json"]):
                    gbuf = io.StringIO()
                    with redirect_stderr(gbuf):
                        rc_g = audit.main(gone_argv)
                    _check(rc_g == 2 and "CWD_UNAVAILABLE" in gbuf.getvalue(), f"deleted CWD CLI {gone_argv}")
            finally:
                os.chdir(orig_cwd)
                if orig_pwd is None:
                    os.environ.pop("PWD", None)
                else:
                    os.environ["PWD"] = orig_pwd

            # File format tamper checks
            bad_utf8 = root / "bad_utf8.json"; bad_utf8.write_bytes(b"\xff\xfe")
            _expect_err(lambda: audit.verify_certificate_file(bad_utf8), "INVALID_UTF8", "bad utf8")
            crlf = root / "crlf.json"; crlf.write_bytes(cert_bytes.replace(b"\n", b"\r\n"))
            _expect_err(lambda: audit.verify_certificate_file(crlf), "CRLF_FORBIDDEN", "CRLF")
            bad_keys_f = root / "bad_keys.json"; bad_keys_f.write_text('{"a":1}\n', encoding="utf-8")
            _expect_err(lambda: audit.verify_certificate_file(bad_keys_f), "INVALID_CERT_KEYS", "bad keys file")
            pretty = root / "pretty.json"; pretty.write_text(json.dumps(cert, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            _expect_err(lambda: audit.verify_certificate_file(pretty), "CERTIFICATE_BYTE_MISMATCH", "pretty JSON")
            # S31-BUG-01 CLI --check on crafted nested bad JSON must return rc=2 (never rc=1 traceback!)
            crafted_f = root / "crafted_empty.json"
            crafted_f.write_text(json.dumps(c_empty, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            p_craft = subprocess.run(
                [sys.executable, "-I", "-O", "-B", str(ROOT / "aletheia_v22_misfolding_audit.py"), "--check", str(crafted_f)],
                capture_output=True, text=True, timeout=30,
            )
            _check(p_craft.returncode == 2 and "AUDIT_P1_SCHEMA" in p_craft.stderr and "Traceback" not in p_craft.stderr,
                   f"crafted CLI rc={p_craft.returncode} err={p_craft.stderr!r}")

            # CLI main() positive + negative + strict flag-path & equals-syntax guards
            out_path = root / "written.json"
            _check(audit.main(["--write", str(out_path)]) == 0 and out_path.read_bytes() == cert_bytes, "CLI --write")
            for chk_argv in (["--check", str(out_path)], ["--check", str(out_path), "--json"]):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc_chk = audit.main(chk_argv)
                _check(rc_chk == 0 and json.loads(buf.getvalue())["valid"] is True, f"CLI {chk_argv}")

            for bad_argv, exp_code in (
                (("--standalone", "--json"), "INVALID_ARGV"),
                ("--check", "INVALID_ARGV"),
                ([123], "INVALID_ARGV"),
                ([_StrSub("--check"), str(out_path)], "INVALID_ARGV"),
                (["--standalone\x00", "--json"], "NUL_BYTE_FORBIDDEN"),
                (["--check", "\ud800"], "INVALID_UTF8_SURROGATE"),
                (["--write", ""], "INVALID_PATH_ARG"),
                (["--check", ""], "INVALID_PATH_ARG"),
                (["--write", "--json"], "INVALID_PATH_ARG"),
                (["--check", "--json"], "INVALID_PATH_ARG"),
                (["--check", "--help"], "INVALID_PATH_ARG"),
                (["--write", "-"], "INVALID_PATH_ARG"),
                (["--write=--json"], "INVALID_CLI_ARGS"),
                (["--check=--json"], "INVALID_CLI_ARGS"),
                (["--write="], "INVALID_CLI_ARGS"),
                (["--check="], "INVALID_CLI_ARGS"),
                (["--wr=--json"], "INVALID_CLI_ARGS"),
                (["--write"], "INVALID_CLI_ARGS"),
                (["--check"], "INVALID_CLI_ARGS"),
                (["--unknown", "x"], "INVALID_CLI_ARGS"),
                (["--check", str(out_path), "--bad"], "INVALID_CLI_ARGS"),
                (["--write", str(out_path), "--json"], "INVALID_CLI_ARGS"),
                (["--check", str(out_path), "--json", "--extra"], "INVALID_CLI_ARGS"),
            ):
                ebuf = io.StringIO()
                with redirect_stderr(ebuf):
                    rc_b = audit.main(bad_argv)
                _check(rc_b == 2 and exp_code in ebuf.getvalue(), f"bad argv {bad_argv!r}: rc={rc_b} err={ebuf.getvalue()!r}")
            _check(not (Path(orig_cwd) / "--json").exists(), "flag-like --write created ./--json!")

            # Live subprocess zero-arg, --standalone --json, & symlinked PWD CLI refusal
            p_def = subprocess.run([sys.executable, "-I", "-O", "-B", str(ROOT / "aletheia_v22_misfolding_audit.py")], capture_output=True, timeout=30)
            _check(p_def.returncode == 0 and p_def.stdout == cert_bytes, "subprocess zero-arg mismatch")
            p_std = subprocess.run([sys.executable, "-I", "-O", "-B", str(ROOT / "aletheia_v22_misfolding_audit.py"), "--standalone", "--json"], capture_output=True, timeout=30)
            _check(p_std.returncode == 0 and p_std.stdout == cert_bytes, "subprocess --standalone mismatch")
            p_pwd = subprocess.run(
                [sys.executable, "-I", "-O", "-B", str(ROOT / "aletheia_v22_misfolding_audit.py"), "--check", "c.json"],
                cwd=str(real_sub),
                env={**os.environ, "PWD": str(sym_dir / "nested")},
                capture_output=True,
                text=True,
                timeout=30,
            )
            _check(p_pwd.returncode == 2 and "SYMLINK_ANCESTOR_FORBIDDEN" in p_pwd.stderr, f"subprocess sym PWD rc={p_pwd.returncode}")

    def test_04_live_renameat2_toctou_and_concurrent_hardlink_races(self) -> None:
        if sys.platform != "linux":
            return
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        AT_FDCWD = -100
        RENAME_EXCHANGE = 2

        with tempfile.TemporaryDirectory(prefix="s31_race_") as td:
            root = Path(td)
            secret = root / "secret.txt"; secret.write_bytes(b"S31_SECRET_SENTINEL")
            legit_dir = root / "legit_dir"; legit_dir.mkdir()
            sym_dir = root / "sym_dir"; os.symlink(root, sym_dir)
            leaf_a = root / "slot_a.json"; leaf_a.write_bytes(b"SAFE_OK")
            leaf_b = root / "slot_b.json"; os.symlink(secret, leaf_b)
            hl_orig = root / "hl_orig.json"; hl_orig.write_bytes(b"HL_SENTINEL")
            hl_target = root / "hl_target.json"

            stop = threading.Event()
            def flipper() -> None:
                ba, bb = os.fsencode(leaf_a), os.fsencode(leaf_b)
                da, db = os.fsencode(legit_dir), os.fsencode(sym_dir)
                while not stop.is_set():
                    libc.renameat2(AT_FDCWD, ba, AT_FDCWD, bb, RENAME_EXCHANGE)
                    libc.renameat2(AT_FDCWD, da, AT_FDCWD, db, RENAME_EXCHANGE)
                    try:
                        os.link(hl_orig, hl_target)
                    except OSError:
                        pass
                    try:
                        os.unlink(hl_target)
                    except OSError:
                        pass

            t = threading.Thread(target=flipper, daemon=True)
            t.start()
            leaks = 0
            clobbers = 0
            hl_clobbers = 0
            try:
                for _ in range(500):
                    try:
                        d1 = audit.read_regular_bytes_capped(leaf_a, "rr")
                        if b"S31_SECRET" in d1:
                            leaks += 1
                    except oracle.AletheiaV22Error:
                        pass
                    try:
                        audit.write_regular_bytes_safe(leaf_a, b"SAFE_WR", "rw")
                    except oracle.AletheiaV22Error:
                        pass
                    try:
                        d2 = audit.read_regular_bytes_capped(legit_dir / "secret.txt", "dr")
                        if b"S31_SECRET" in d2:
                            leaks += 1
                    except oracle.AletheiaV22Error:
                        pass
                    try:
                        audit.write_regular_bytes_safe(hl_target, b"NEW_HL", "hlw")
                    except oracle.AletheiaV22Error:
                        pass
                    if secret.read_bytes() != b"S31_SECRET_SENTINEL":
                        clobbers += 1
                    if hl_orig.read_bytes() != b"HL_SENTINEL":
                        hl_clobbers += 1
            finally:
                stop.set()
                t.join(timeout=5)
            leftover_tmps = [p.name for p in root.iterdir() if ".s31_tmp_" in p.name]
            _check(leaks == 0 and clobbers == 0 and hl_clobbers == 0 and len(leftover_tmps) == 0,
                   f"race failed: leaks={leaks} clobbers={clobbers} hl={hl_clobbers} tmps={leftover_tmps}")


if __name__ == "__main__":
    unittest.main()
