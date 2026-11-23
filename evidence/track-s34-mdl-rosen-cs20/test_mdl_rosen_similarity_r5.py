#!/usr/bin/env python3
"""Track S34 (Portal 31) R2 Verification & Adversarial Zone-B Test Suite.

Pure Python 3 stdlib, zero bare asserts, zero AST float literals and zero float()
calls (runtime negative fixtures use json.loads("1.5") / json.loads("NaN") /
json.loads("1.0") solely to test fail-closed float rejection in Zone-B parsers).
Covers:
  - Test 1: Full 5-pillar exact Z/Q mathematical verification & certificate parity
  - Test 2: Exact domain, type, boundary, arithmetic, Sturm, DPI & CS-20 guards
  - Test 3: Uniform Zone-B Gold Standard (atomic dir_fd PWD/openat, 0o600 CSPRNG
            temp + pre-replace st_nlink == 1 + fsync + os.replace, 64 KiB streaming
            capped read, canonical_json_bytes tree validation, ASCII-only parsers
            rejecting -0/leading zeros, exact-int secondary_audit_payload &
            full_replay=False verification, /proc/kallsyms, /dev/null, FIFO,
            chmod 000, hardlink, deep/dotdot/PWD symlinks, deleted-CWD, lone
            surrogates, space & equals CLI, subprocess parity)
  - Test 4: Live >= 520-iter concurrent renameat2(RENAME_EXCHANGE) + >= 420-iter
            concurrent os.link()/os.unlink() hardlink inode-immutability race +
            16T distinct / 16T same-target / 80T barrier burst concurrent writers
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import copy
import ctypes
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
import threading
import unittest
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mdl_rosen_similarity_audit as audit  # noqa: E402
import mdl_rosen_similarity_oracle as oracle  # noqa: E402

CERT_PATH = ROOT / audit.DEFAULT_CERT_NAME
_AT_FDCWD = -100
_RENAME_EXCHANGE = 2


class _EvilPath(type(Path())):
    """Path subclass rejected by strict concrete pathlib.Path check."""


class _StrSub(str):
    """str subclass rejected by strict type(x) is str check."""


class _IntSub(int):
    """int subclass rejected by strict type(x) is int check."""


class _BoolLike:
    def __bool__(self) -> bool:
        return True


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _expect_err(fn: Any, expected_code: str, label: str) -> None:
    try:
        fn()
    except oracle.MdlRosenError as exc:
        if exc.code != expected_code:
            raise AssertionError(f"{label}: expected {expected_code}, got {exc.code} ({exc})") from exc
        return
    raise AssertionError(f"{label}: expected MdlRosenError({expected_code}), but succeeded")


def _sample_cs20_spec(
    *,
    name: str = "spec",
    regime: str = "R0",
    disc: Fraction = Fraction(1, 1),
    bottleneck: str = "HBM_BOUND",
    dpi: Fraction = Fraction(1, 1),
    thr: Fraction = Fraction(16, 1),
) -> dict[str, Any]:
    return {
        "name": name,
        "discrete_regime_sig": regime,
        "jacobian_discriminant": disc,
        "active_bottleneck_phase": bottleneck,
        "dpi_concentration": dpi,
        "dpi_threshold": thr,
    }


class TrackS34Tests(unittest.TestCase):
    def test_01_five_pillars_exact_math_and_certificate(self) -> None:
        cert = audit.build_certificate()
        disk_bytes = CERT_PATH.read_bytes()
        _check(audit.canonical_json_bytes(cert) == disk_bytes, "on-disk certificate drift")
        res = audit.verify_certificate_dict(cert, expected=cert)
        _check(res["valid"] is True, "verify_certificate_dict failed")
        res_nr = audit.verify_certificate_dict(cert, full_replay=False)
        _check(res_nr == res, "verify_certificate_dict(full_replay=False) mismatch")
        res_file = audit.verify_certificate_file(CERT_PATH)
        _check(res_file == res, "verify_certificate_file mismatch")

        pl = cert["payload"]
        _check(
            pl["track_id"] == "TRACK-S34-MDL-ROSEN"
            and pl["novelty_class"] == "N1"
            and pl["all_pillars_verified"] is True,
            "top-level metadata mismatch",
        )

        # Pillar 1: Two-Part MDL vs Prequential vs Requential (2607.11883)
        p1 = pl["pillar1_mdl_prequential_requential"]
        _check(p1["all_verified"] is True, "P1 all_verified")
        _check(
            p1["L_uniform_bits"] == 64
            and p1["L_theta_T_bits"] == 56
            and p1["L_online_raw_bits"] == 60
            and p1["cumulative_regret_R_bits"] == 4,
            "P1 codelengths",
        )
        _check(
            [r["L_diff_bits"] for r in p1["offline_vs_online_regimes"]] == [8, 0, -2]
            and [r["online_beats_offline"] for r in p1["offline_vs_online_regimes"]] == [True, False, False],
            "P1 crossover regimes",
        )
        tw = p1["three_way_separation"]
        _check(
            tw["mdl_two_part_delta_bits"] == "16"
            and tw["prequential_delta_bits"] == "16"
            and tw["requential_kl_base_bits"] == "1"
            and tw["requential_kl_noisy_bits"] == "1"
            and tw["requential_kl_delta_bits"] == "0"
            and tw["requential_invariant_under_noise"] is True,
            "P1 three-way separation",
        )

        # Pillar 2: siliquant Gemma 3 4B IT Pareto & log-convex bitrate law
        p2 = pl["pillar2_siliquant_mdl_pareto"]
        _check(p2["all_verified"] is True and p2["ln2_within_reference_bracket"] is True, "P2 verified")
        _check(
            p2["kl_mean_units"] == "nats"
            and p2["first_order_ln2_cancellation_exact"] is True
            and p2["source_provenance"]["dataset"] == oracle.SILIQUANT_SOURCE_DATASET
            and p2["source_provenance"]["source_file_sha256"] == oracle.SILIQUANT_SOURCE_FILE_SHA256,
            "P2 units & provenance",
        )
        _check(p2["active_weights_N"] == 3_208_642_560 and p2["active_matrices"] == 238, "P2 Gemma 4B N_act")
        zbg_res = p2["zbg128_log_convex_fit_residuals"]
        _check(
            len(zbg_res) == 3
            and all(r["within_0_25_pct"] is True for r in zbg_res)
            and [r["rel_err_upper_pct_dec4"] for r in zbg_res] == ["0.1913", "0.0057", "0.1926"],
            "P2 ZBG fit residuals",
        )
        par = p2["pareto_EBG128_vs_Q4_K_M"]
        _check(
            par["strict_pareto_dominance_all_T_ge_0"] is True
            and par["delta_bpw_dec6"] == "-0.315202"
            and par["model_Gbits_saved_dec3"] == "1.011",
            "P2 Pareto dominance",
        )
        be = p2["breakeven_vs_bf16"]
        _check(be["EBG128:b560s16"]["wiki_tokens_lo_billions_dec3"] == "271.275", "P2 EBG wiki tok")
        _check(be["EBG128:b560s16"]["py_tokens_lo_billions_dec3"] == "640.207", "P2 EBG py tok")
        _check(be["file:Q4_K_M"]["wiki_tokens_lo_billions_dec3"] == "164.420", "P2 Q4KM wiki tok")
        _check(be["file:Q4_K_M"]["py_tokens_lo_billions_dec3"] == "382.218", "P2 Q4KM py tok")
        law = p2["log_convex_bitrate_law"]
        _check(
            law["strictly_convex"] is True
            and law["strictly_monotone_T_over_N"] is True
            and law["first_order_optimality_all_certified"] is True,
            "P2 convex law",
        )
        _check(
            len(law["schedule"]) == 5
            and law["schedule"][1]["bitrate_b_q"] == "9/2"
            and all(
                row["first_order_zero_certified"] is True
                and row["dL_db_lo_dec12"] == "0.000000000000"
                and row["dL_db_hi_dec12"] == "0.000000000000"
                for row in law["schedule"]
            ),
            "P2 schedule first-order certification",
        )

        # Pillar 3: Rosen similarity & bifurcation obstruction
        p3 = pl["pillar3_rosen_similarity_bifurcation"]
        _check(
            p3["all_verified"] is True
            and p3["power_law_buckingham_pi_commutation_exact"] is True
            and p3["vdw_corresponding_states_commutation_exact"] is True
            and p3["vdw_critical_point_1_1_1"]["exact_triple_root"] is True,
            "P3 Rosen commutation & critical point",
        )
        _check(
            p3["vdw_phase_discriminants"]["supercritical_Pr1_Tr2"] == "-21696"
            and p3["vdw_phase_discriminants"]["subcritical_Pr_half_Tr_7_8"] == "81/2",
            "P3 vdW discriminants",
        )
        cusp = p3["cusp_normal_form_obstruction"]
        _check(
            cusp["supercritical_a1_b0"]["sturm_real_roots"] == 1
            and cusp["multi_phase_a_neg4_b0"]["sturm_real_roots"] == 3
            and cusp["fold_a_neg3_b_pos2"]["jacobian_dx"] == "0"
            and cusp["topological_cardinality_obstruction_1_ne_3"] is True,
            "P3 cusp obstruction",
        )

        # Pillar 4: Global MDL blindness to surgical weight-space misfolding
        p4 = pl["pillar4_mdl_blindness_misfolding"]
        _check(
            p4["all_verified"] is True
            and p4["model_scope"] == "synthetic_64x16_weight_matrix_witness"
            and p4["iso_frobenius_exact"] is True
            and p4["control_queries_identical"] == 12
            and p4["control_delta_L_theta_bits"] == 0
            and p4["control_requential_kl_bits"] == "0"
            and p4["trigger_argmax_W0"] == 0
            and p4["trigger_argmax_W1"] == 1
            and p4["dpi_benign_quant"] == "1"
            and p4["dpi_misfolding_patch"] == "64"
            and p4["dpi_separation_ratio"] == "64",
            "P4 misfolding vs DPI separation",
        )

        # Pillar 5: Executable Aletheia v2.2 CS-20 gate
        p5 = pl["pillar5_cs20_extrapolation_gate"]
        _check(
            p5["all_verified"] is True
            and p5["clean_within_phase_pairs_checked"] == 3
            and p5["cross_boundary_witnesses_checked"] == 5
            and p5["tpu_v5e_bf16_ridge_B_star_q"] == "19700/273"
            and p5["siliquant_kl_advantage_nats_q"] == {
                "270m": "6333/250000",
                "1b": "3221/200000",
                "4b": "-57011/1000000",
            },
            "P5 CS-20 summary",
        )

    def test_02_oracle_guards_boundaries_sturm_dpi_and_cs20(self) -> None:
        # Strict primitive guards (int, bool, str, Fraction, bounds, formatting)
        _expect_err(lambda: oracle.require_ok(1, "X", "m"), "INVALID_CONDITION_TYPE", "int cond")
        _expect_err(lambda: oracle.require_ok(_BoolLike(), "X", "m"), "INVALID_CONDITION_TYPE", "boollike cond")
        _expect_err(lambda: oracle.require_ok(False, "MY_CODE", "boom"), "MY_CODE", "false cond")
        oracle.require_ok(True, "OK", "ok")

        _expect_err(lambda: oracle.require_exact_int(True, "n"), "INVALID_INT_TYPE", "bool as int")
        _expect_err(lambda: oracle.require_exact_int(_IntSub(3), "n"), "INVALID_INT_TYPE", "int subclass")
        _expect_err(lambda: oracle.require_exact_int(1 << oracle.MAX_RATIONAL_BITS, "n"), "INT_BIT_LIMIT", "int bit cap")
        _check(oracle.require_exact_int((1 << oracle.MAX_RATIONAL_BITS) - 1, "n") > 0, "exact max bits int")
        _expect_err(lambda: oracle.require_exact_int(1, "n", lo="0"), "INVALID_BOUND_TYPE", "bad lo type")  # type: ignore[arg-type]
        _expect_err(lambda: oracle.require_exact_int(1, "n", hi="5"), "INVALID_BOUND_TYPE", "bad hi type")  # type: ignore[arg-type]
        _expect_err(lambda: oracle.require_exact_int(0, "n", lo=1), "INT_OUT_OF_RANGE", "below lo")
        _check(oracle.require_exact_int(1, "n", lo=1, hi=5) == 1, "exact lo int")
        _expect_err(lambda: oracle.require_exact_int(6, "n", lo=1, hi=5), "INT_OUT_OF_RANGE", "above hi")
        _check(oracle.require_exact_int(5, "n", lo=1, hi=5) == 5, "exact hi int")

        _expect_err(lambda: oracle.require_exact_bool(1, "b"), "INVALID_BOOL_TYPE", "int as bool")
        _check(oracle.require_exact_bool(False, "b") is False, "bool false")

        _expect_err(lambda: oracle.require_exact_str(123, "s"), "INVALID_STR_TYPE", "non-str")
        _expect_err(lambda: oracle.require_exact_str(_StrSub("a"), "s"), "INVALID_STR_TYPE", "str subclass")
        _expect_err(lambda: oracle.require_exact_str("a\x00b", "s"), "NUL_BYTE_FORBIDDEN", "NUL str")
        _expect_err(lambda: oracle.require_exact_str("\ud800", "s"), "INVALID_UTF8_SURROGATE", "surrogate str")
        _expect_err(lambda: oracle.require_exact_str("", "s", min_len=1), "STR_TOO_SHORT", "empty str")
        _check(oracle.require_exact_str("a", "s", min_len=1, max_len=3) == "a", "exact min_len str")
        _check(oracle.require_exact_str("abc", "s", min_len=1, max_len=3) == "abc", "exact max_len str")
        _expect_err(lambda: oracle.require_exact_str("abcd", "s", min_len=1, max_len=3), "STR_TOO_LONG", "too long str")

        _expect_err(lambda: oracle.require_exact_fraction(1, "q"), "INVALID_FRACTION_TYPE", "int as Fraction")
        _expect_err(
            lambda: oracle.require_exact_fraction(Fraction(1 << oracle.MAX_RATIONAL_BITS, 1), "q"),
            "RATIONAL_BIT_LIMIT",
            "num bit cap",
        )
        _check(oracle.require_exact_fraction(Fraction((1 << oracle.MAX_RATIONAL_BITS) - 1, 1), "q") > 0, "exact num bits")
        _expect_err(
            lambda: oracle.require_exact_fraction(Fraction(1, 1 << oracle.MAX_RATIONAL_BITS), "q"),
            "RATIONAL_BIT_LIMIT",
            "den bit cap",
        )
        _check(oracle.require_exact_fraction(Fraction(1, (1 << oracle.MAX_RATIONAL_BITS) - 1), "q") > 0, "exact den bits")
        _expect_err(lambda: oracle.require_exact_fraction(Fraction(1, 2), "q", lo=0), "INVALID_BOUND_TYPE", "bad frac lo")  # type: ignore[arg-type]
        _expect_err(lambda: oracle.require_exact_fraction(Fraction(1, 2), "q", hi=1), "INVALID_BOUND_TYPE", "bad frac hi")  # type: ignore[arg-type]
        _expect_err(
            lambda: oracle.require_exact_fraction(Fraction(0, 1), "q", lo=Fraction(1, 2)),
            "FRACTION_OUT_OF_RANGE",
            "frac below lo",
        )
        _expect_err(
            lambda: oracle.require_exact_fraction(Fraction(2, 1), "q", hi=Fraction(1, 1)),
            "FRACTION_OUT_OF_RANGE",
            "frac above hi",
        )
        _check(oracle.require_exact_fraction(Fraction(1, 2), "q", lo=Fraction(1, 2), hi=Fraction(1, 2)) == Fraction(1, 2), "exact frac bounds")

        _check(oracle.format_fraction(Fraction(6, 2)) == "3", "int frac format")
        _check(oracle.format_fraction(Fraction(5, 3)) == "5/3", "non-int frac format")
        _check(oracle.format_decimal_rounded(Fraction(-5, 4), 4) == "-1.2500", "neg dec format")
        _check(oracle.format_decimal_rounded(Fraction(2, 3), 6) == "0.666667", "pos dec rounding")
        _check(oracle.format_decimal_rounded(Fraction(-1, 10**9), 6) == "0.000000", "no negative zero dec")
        _check(oracle.format_decimal_rounded(Fraction(0, 1), 6) == "0.000000", "zero dec format")
        _expect_err(lambda: oracle.format_decimal_rounded(Fraction(1, 2), 0), "INT_OUT_OF_RANGE", "digits 0")

        # Pure-Q enclosures (ln2, exp, pow2)
        ln2_lo, ln2_hi = oracle.certify_ln2_enclosure(14)
        _check(ln2_lo < ln2_hi, "ln2 bracket")
        _expect_err(lambda: oracle.certify_ln2_enclosure(3), "INT_OUT_OF_RANGE", "ln2 terms < 4")
        _expect_err(lambda: oracle.certify_exp_enclosure(Fraction(1, 2), Fraction(1, 4)), "FRACTION_OUT_OF_RANGE", "exp inverted")
        p0_lo, p0_hi = oracle.certify_pow2_rational_enclosure(Fraction(0, 1), ln2_lo, ln2_hi)
        _check(p0_lo == 1 and p0_hi == 1, "2^0 exact")
        p3_lo, p3_hi = oracle.certify_pow2_rational_enclosure(Fraction(3, 1), ln2_lo, ln2_hi)
        _check(p3_lo == 8 and p3_hi == 8, "2^3 exact")
        p_hi_lo, p_hi_hi = oracle.certify_pow2_rational_enclosure(Fraction(1, 2), Fraction(9, 10), Fraction(9, 10))
        _check(p_hi_lo < p_hi_hi, "exact ln2_hi == 9/10 allowed")
        _expect_err(
            lambda: oracle.certify_pow2_rational_enclosure(Fraction(1, 2), Fraction(91, 100), Fraction(91, 100)),
            "FRACTION_OUT_OF_RANGE",
            "ln2_lo > 9/10",
        )
        _expect_err(
            lambda: oracle.certify_pow2_rational_enclosure(Fraction(1, 2), Fraction(7, 10), Fraction(91, 100)),
            "FRACTION_OUT_OF_RANGE",
            "ln2_hi > 9/10",
        )

        # Dyadic information-theory guards
        _check(oracle.exact_dyadic_codelength(Fraction(1, 1)) == 0, "log2(1)")
        _check(oracle.exact_dyadic_codelength(Fraction(1, 8)) == 3, "log2(1/8)")
        _expect_err(lambda: oracle.exact_dyadic_codelength(Fraction(3, 4)), "NON_DYADIC_PROB", "num != 1")
        _expect_err(lambda: oracle.exact_dyadic_codelength(Fraction(1, 3)), "NON_DYADIC_PROB", "non-pow2 den")
        _expect_err(lambda: oracle.exact_dyadic_entropy_bits((Fraction(1, 2), Fraction(1, 2))), "INVALID_DIST_TYPE", "tuple dist")  # type: ignore[arg-type]
        _expect_err(lambda: oracle.exact_dyadic_entropy_bits([Fraction(1, 1)]), "INVALID_DIST_LEN", "len 1 dist")
        _expect_err(lambda: oracle.exact_dyadic_entropy_bits([Fraction(1, 2), Fraction(1, 4)]), "DIST_NOT_NORMALIZED", "unnorm dist")
        _check(oracle.exact_dyadic_entropy_bits([Fraction(1, 1), Fraction(0, 1)]) == 0, "degenerate entropy")
        _check(oracle.exact_dyadic_kl_bits([Fraction(1, 1), Fraction(0, 1)], [Fraction(1, 2), Fraction(1, 2)]) == 1, "zero-prob KL")
        _check(oracle.exact_dyadic_cross_entropy_bits([Fraction(1, 1), Fraction(0, 1)], [Fraction(1, 2), Fraction(1, 2)]) == 1, "zero-prob CE")
        _expect_err(
            lambda: oracle.exact_dyadic_kl_bits([Fraction(1, 2), Fraction(1, 2)], [Fraction(1, 4)] * 4),
            "DIST_LEN_MISMATCH",
            "KL len mismatch",
        )
        _expect_err(
            lambda: oracle.exact_dyadic_kl_bits([Fraction(1, 2), Fraction(1, 2)], [Fraction(1, 1), Fraction(0, 1)]),
            "KL_SUPPORT_MISMATCH",
            "KL support mismatch",
        )
        _expect_err(
            lambda: oracle.exact_dyadic_cross_entropy_bits([Fraction(1, 2), Fraction(1, 2)], [Fraction(1, 4)] * 4),
            "DIST_LEN_MISMATCH",
            "CE len mismatch",
        )
        _expect_err(
            lambda: oracle.exact_dyadic_cross_entropy_bits([Fraction(1, 2), Fraction(1, 2)], [Fraction(1, 1), Fraction(0, 1)]),
            "KL_SUPPORT_MISMATCH",
            "CE support mismatch",
        )

        # Cubic discriminant, polynomial trim/rem, & Sturm root counter guards (kills L667 BoolOp!)
        _expect_err(
            lambda: oracle.cubic_discriminant_exact(Fraction(0, 1), Fraction(1, 1), Fraction(1, 1), Fraction(1, 1)),
            "DEGENERATE_CUBIC",
            "a3=0",
        )
        _check(oracle._poly_trim([Fraction(0, 1), Fraction(0, 1)]) == [Fraction(0, 1)], "poly trim all-zero")
        _check(
            oracle._poly_rem([Fraction(-1, 1), Fraction(0, 1), Fraction(1, 1)], [Fraction(-1, 1), Fraction(1, 1)])
            == [Fraction(0, 1)],
            "exact zero remainder",
        )
        _expect_err(lambda: oracle.sturm_real_root_count_depressed_cubic(Fraction(-3, 1), Fraction(2, 1)), "NON_SQUAREFREE_CUBIC", "fold")
        _check(oracle.sturm_real_root_count_depressed_cubic(Fraction(0, 1), Fraction(1, 1)) == 1, "x^3 + 1")
        _check(oracle.sturm_real_root_count_depressed_cubic(Fraction(0, 1), Fraction(-1, 1)) == 1, "x^3 - 1")

        # DPI matrix guards
        _expect_err(lambda: oracle.compute_row_energy_dpi("bad"), "INVALID_MATRIX_TYPE", "non-list matrix")  # type: ignore[arg-type]
        _expect_err(lambda: oracle.compute_row_energy_dpi([[Fraction(1, 1)]]), "INVALID_MATRIX_DIM", "1-row matrix")
        _expect_err(lambda: oracle.compute_row_energy_dpi([1, [Fraction(1, 1)]]), "INVALID_MATRIX_ROW", "non-list row")  # type: ignore[list-item]
        _expect_err(lambda: oracle.compute_row_energy_dpi([[], []]), "INVALID_MATRIX_DIM", "empty rows")
        _expect_err(
            lambda: oracle.compute_row_energy_dpi([[Fraction(1, 1)], [Fraction(1, 1), Fraction(1, 1)]]),
            "INVALID_MATRIX_ROW",
            "ragged matrix",
        )
        _expect_err(
            lambda: oracle.compute_row_energy_dpi([[Fraction(0, 1)], [Fraction(0, 1)]]),
            "ZERO_PERTURBATION",
            "zero matrix",
        )

        # CS-20 gate schema, singular manifold, DPI both-sides & boundary checks (kills SWAP+SUBCOND_DEL!)
        _expect_err(lambda: oracle.evaluate_cs20_extrapolation_gate("bad", _sample_cs20_spec()), "INVALID_CS20_SPEC", "bad spec")  # type: ignore[arg-type]
        _expect_err(lambda: oracle.evaluate_cs20_extrapolation_gate({}, _sample_cs20_spec()), "INVALID_CS20_SPEC_KEYS", "empty spec")
        res_sing_p = oracle.evaluate_cs20_extrapolation_gate(
            _sample_cs20_spec(disc=Fraction(0, 1)), _sample_cs20_spec(disc=Fraction(1, 1))
        )
        _check(res_sing_p["reason_codes"] == ["SINGULAR_BIFURCATION_MANIFOLD"], "proto singular")
        res_sing_t = oracle.evaluate_cs20_extrapolation_gate(
            _sample_cs20_spec(disc=Fraction(1, 1)), _sample_cs20_spec(disc=Fraction(0, 1))
        )
        _check(res_sing_t["reason_codes"] == ["SINGULAR_BIFURCATION_MANIFOLD"], "target singular")
        res_dpi_p = oracle.evaluate_cs20_extrapolation_gate(
            _sample_cs20_spec(dpi=Fraction(17, 1)), _sample_cs20_spec(dpi=Fraction(1, 1))
        )
        _check(res_dpi_p["reason_codes"] == ["DPI_STRUCTURAL_CONCENTRATION_SPIKE"], "proto DPI spike")
        res_dpi_t = oracle.evaluate_cs20_extrapolation_gate(
            _sample_cs20_spec(dpi=Fraction(1, 1)), _sample_cs20_spec(dpi=Fraction(17, 1))
        )
        _check(res_dpi_t["reason_codes"] == ["DPI_STRUCTURAL_CONCENTRATION_SPIKE"], "target DPI spike")
        res_dpi_eq = oracle.evaluate_cs20_extrapolation_gate(
            _sample_cs20_spec(dpi=Fraction(16, 1), thr=Fraction(16, 1)),
            _sample_cs20_spec(dpi=Fraction(16, 1), thr=Fraction(16, 1)),
        )
        _check(res_dpi_eq["verdict"] == "ALLOW_EXTRAPOLATION", "exact DPI == threshold must allow")
        # Live witness spec helper boundary guards
        _expect_err(
            lambda: oracle._make_siliquant_q4km_spec("x", 8, 7, Fraction(1, 10), Fraction(1, 10)),
            "INVALID_PROMOTED_COUNT",
            "promoted > total",
        )
        sq_eq = oracle._make_siliquant_q4km_spec("x", 7, 7, Fraction(1, 10), Fraction(1, 10))
        _check(sq_eq["discrete_regime_sig"] == "Q4_K_M:promoted_7_of_7", "exact promoted == total")
        lora_eq = oracle._make_cs16_lora_spec("x", "P", Fraction(1, 1), Fraction(1, 1))
        _check(lora_eq["active_bottleneck_phase"] == "GAIN_MATCHED_FORGETTING_REVERSAL", "exact rel_delta == 0")

    def test_03_zone_b_hardening_parsers_secondary_audit_and_cli(self) -> None:
        cert = json.loads(CERT_PATH.read_text(encoding="utf-8"))
        cert_bytes = CERT_PATH.read_bytes()

        # Hex64 + verify_certificate_dict + schema-safe secondary_audit_payload guards
        _expect_err(lambda: audit.require_hex64_lower_ascii("a" * 63, "h"), "INVALID_HEX64", "len 63")
        _expect_err(lambda: audit.require_hex64_lower_ascii("A" * 64, "h"), "INVALID_HEX64", "uppercase hex")
        _expect_err(lambda: audit.require_hex64_lower_ascii(123, "h"), "INVALID_HEX64", "int hex")
        _expect_err(lambda: audit.require_hex64_lower_ascii(["a"] * 64, "h"), "INVALID_HEX64", "list len 64")

        _expect_err(lambda: audit.verify_certificate_dict([]), "INVALID_CERT_TYPE", "list cert")
        _expect_err(lambda: audit.verify_certificate_dict(cert, full_replay=1), "INVALID_BOOL_TYPE", "non-bool full_replay")  # type: ignore[arg-type]
        bad_k = copy.deepcopy(cert)
        bad_k["extra"] = 1
        _expect_err(lambda: audit.verify_certificate_dict(bad_k, expected=cert), "INVALID_CERT_KEYS", "extra key")
        bad_sv = copy.deepcopy(cert)
        bad_sv["schema_version"] = "9.9.9"
        _expect_err(lambda: audit.verify_certificate_dict(bad_sv, full_replay=False), "INVALID_SCHEMA_VERSION", "bad schema")
        bad_tid = copy.deepcopy(cert)
        bad_tid["track_id"] = "OTHER"
        _expect_err(lambda: audit.verify_certificate_dict(bad_tid, full_replay=False), "INVALID_TRACK_ID", "bad track_id")
        bad_psha = copy.deepcopy(cert)
        bad_psha["payload_sha256"] = "0" * 64
        _expect_err(lambda: audit.verify_certificate_dict(bad_psha, full_replay=False), "PAYLOAD_SHA_MISMATCH", "bad psha")
        bad_csha = copy.deepcopy(cert)
        bad_csha["certificate_sha256"] = "0" * 64
        _expect_err(lambda: audit.verify_certificate_dict(bad_csha, full_replay=False), "CERTIFICATE_SHA_MISMATCH", "bad csha")
        bad_pl = copy.deepcopy(cert)
        bad_pl["payload"]["novelty_class"] = "N9"
        _expect_err(lambda: audit.verify_certificate_dict(bad_pl, expected=cert), "PAYLOAD_SHA_MISMATCH", "unsigned bad payload")
        # Re-signed payload with altered metadata: passes self-consistent full_replay=False, fails full_replay=True
        resigned_pl = copy.deepcopy(cert)
        resigned_pl["payload"]["novelty_class"] = "N9"
        resigned_pl["payload_sha256"] = hashlib.sha256(audit.canonical_json_bytes(resigned_pl["payload"])).hexdigest()
        resigned_env = {
            "schema_version": resigned_pl["schema_version"],
            "track_id": resigned_pl["track_id"],
            "payload_sha256": resigned_pl["payload_sha256"],
            "payload": resigned_pl["payload"],
        }
        resigned_pl["certificate_sha256"] = hashlib.sha256(audit.canonical_json_bytes(resigned_env)).hexdigest()
        _check(audit.verify_certificate_dict(resigned_pl, full_replay=False)["valid"] is True, "re-signed full_replay=False")
        _expect_err(lambda: audit.verify_certificate_dict(resigned_pl, expected=cert, full_replay=True), "CERTIFICATE_MISMATCH", "re-signed full_replay=True")
        # Re-signed bool-for-int forgery MUST fail EVEN with full_replay=False!
        bool_forge = copy.deepcopy(cert)
        bool_forge["payload"]["pillar1_mdl_prequential_requential"]["offline_vs_online_regimes"][0]["cancellation_residual"] = False
        bool_forge["payload_sha256"] = hashlib.sha256(audit.canonical_json_bytes(bool_forge["payload"])).hexdigest()
        bf_env = {
            "schema_version": bool_forge["schema_version"],
            "track_id": bool_forge["track_id"],
            "payload_sha256": bool_forge["payload_sha256"],
            "payload": bool_forge["payload"],
        }
        bool_forge["certificate_sha256"] = hashlib.sha256(audit.canonical_json_bytes(bf_env)).hexdigest()
        _expect_err(lambda: audit.verify_certificate_dict(bool_forge, full_replay=False), "INVALID_INT_TYPE", "re-signed bool-for-int")

        # Schema-safe fail-closed exact-int secondary_audit_payload across crafted malformed inputs (0 uncaught errors!)
        _expect_err(lambda: audit.secondary_audit_payload(123), "SECONDARY_AUDIT_SCHEMA_ERROR", "int payload")
        _expect_err(lambda: audit.secondary_audit_payload([]), "SECONDARY_AUDIT_SCHEMA_ERROR", "list payload")
        _expect_err(lambda: audit.secondary_audit_payload({}), "SECONDARY_AUDIT_SCHEMA_ERROR", "empty payload")
        bad_list_pl = copy.deepcopy(cert["payload"])
        bad_list_pl["pillar1_mdl_prequential_requential"]["offline_vs_online_regimes"] = tuple(
            bad_list_pl["pillar1_mdl_prequential_requential"]["offline_vs_online_regimes"]
        )
        _expect_err(lambda: audit.secondary_audit_payload(bad_list_pl), "SECONDARY_AUDIT_SCHEMA_ERROR", "tuple regimes list")

        bad_res_pl = copy.deepcopy(cert["payload"])
        bad_res_pl["pillar1_mdl_prequential_requential"]["offline_vs_online_regimes"][0]["cancellation_residual"] = 1
        _expect_err(lambda: audit.secondary_audit_payload(bad_res_pl), "SECONDARY_AUDIT_FAILED", "nonzero residual")

        # Exact-int (bool-for-int & float-for-int) secondary_audit_payload rejections
        for mut_fn, lbl in (
            (lambda p: p["pillar1_mdl_prequential_requential"]["offline_vs_online_regimes"][0].__setitem__("cancellation_residual", False), "bool residual"),
            (lambda p: p["pillar1_mdl_prequential_requential"]["hardcode_no_profit_checks"][0].__setitem__("T", True), "bool hardcode T"),
            (lambda p: p["pillar3_rosen_similarity_bifurcation"]["cusp_normal_form_obstruction"]["supercritical_a1_b0"].__setitem__("sturm_real_roots", True), "bool sturm roots"),
            (lambda p: p["pillar3_rosen_similarity_bifurcation"]["cusp_normal_form_obstruction"]["supercritical_a1_b0"].__setitem__("sturm_real_roots", json.loads("1.0")), "float sturm roots"),
            (lambda p: p["pillar3_rosen_similarity_bifurcation"]["cusp_normal_form_obstruction"]["multi_phase_a_neg4_b0"].__setitem__("explicit_roots", [-2, False, 2]), "bool explicit root"),
            (lambda p: p["pillar4_mdl_blindness_misfolding"].__setitem__("control_delta_L_theta_bits", False), "bool p4 delta"),
        ):
            mp = copy.deepcopy(cert["payload"])
            mut_fn(mp)
            _expect_err(lambda x=mp: audit.secondary_audit_payload(x), "INVALID_INT_TYPE", lbl)

        bad_rat_pl = copy.deepcopy(cert["payload"])
        bad_rat_pl["pillar2_siliquant_mdl_pareto"]["pareto_EBG128_vs_Q4_K_M"]["delta_kl_wiki_q"] = "\u00b2"
        _expect_err(lambda: audit.secondary_audit_payload(bad_rat_pl), "INVALID_RATIONAL", "superscript in payload")

        bad_p5_clean = copy.deepcopy(cert["payload"])
        bad_p5_clean["pillar5_cs20_extrapolation_gate"]["clean_within_phase_results"][0]["verdict"] = "DENY_PHASE_BIFURCATION"
        _expect_err(lambda: audit.secondary_audit_payload(bad_p5_clean), "SECONDARY_AUDIT_FAILED", "tampered p5 clean")

        bad_p5_deny = copy.deepcopy(cert["payload"])
        bad_p5_deny["pillar5_cs20_extrapolation_gate"]["cross_boundary_witness_results"][0]["verdict"] = "ALLOW_EXTRAPOLATION"
        _expect_err(lambda: audit.secondary_audit_payload(bad_p5_deny), "SECONDARY_AUDIT_FAILED", "tampered p5 deny")

        # Strict ASCII-only _parse_bounded_int & parse_exact_rational guards
        _check(
            audit._parse_bounded_int("0") == 0
            and audit._parse_bounded_int("-5") == -5
            and audit._parse_bounded_int("10") == 10,
            "valid bounded ints",
        )
        for bad_int_tok, lbl in (
            (12, "non-str int"),
            ("", "empty int"),
            ("-", "bare minus"),
            ("-0", "negative zero"),
            ("007", "leading zero pos"),
            ("-01", "leading zero neg"),
            ("\u0661\u0662", "Arabic-Indic"),
            ("-\u0661\u0662", "neg Arabic-Indic"),
            ("\u00b2", "superscript"),
            ("+12", "leading plus"),
            ("1_2", "underscore"),
        ):
            _expect_err(lambda bt=bad_int_tok: audit._parse_bounded_int(bt), "INVALID_JSON_INT", lbl)

        _check(audit.parse_exact_rational("0") == 0 and audit.parse_exact_rational("-5") == -5, "int rational")
        _check(audit.parse_exact_rational("3/2") == Fraction(3, 2), "den=2 rational")
        _check(audit.parse_exact_rational("3/7") == Fraction(3, 7) and audit.parse_exact_rational("-11/4") == Fraction(-11, 4), "frac rational")
        _check(audit.parse_exact_rational("9" * audit.MAX_JSON_INT_DIGITS) > 0, "exact max-digit rational num")
        _check(audit.parse_exact_rational("1/" + "9" * audit.MAX_JSON_INT_DIGITS) > 0, "exact max-digit rational den")
        for bad_rat_tok, lbl in (
            (12, "non-str rat"),
            ("", "empty rat"),
            ("-", "dash rat"),
            ("-0", "neg zero rat"),
            ("01", "leading zero num"),
            ("1/02", "leading zero den"),
            ("3/1", "non-canonical den=1"),
            ("2/4", "non-reduced rational"),
            ("1/2/3", "two slashes"),
            ("/2", "empty num"),
            ("-/2", "dash-only num"),
            ("1/", "empty den"),
            ("1/0", "zero den"),
            ("1/-2", "neg den"),
            ("\u00b2", "superscript rat"),
            ("1/\u00b2", "superscript den"),
            ("\u0661\u0662/\u0663", "Arabic-Indic rat"),
            ("+1/2", "plus rat"),
            ("9" * (audit.MAX_JSON_INT_DIGITS + 1), "num too long"),
            ("1/" + "9" * (audit.MAX_JSON_INT_DIGITS + 1), "den too long"),
        ):
            _expect_err(lambda bt=bad_rat_tok: audit.parse_exact_rational(bt), "INVALID_RATIONAL", lbl)

        # Strict JSON tree & parser guards (zero AST floats: use json.loads("1.5") for runtime float!)
        _check(audit.parse_strict_json_text("[1,true,null]", "arr", require_object=False) == [1, True, None], "arr parse")
        _check(
            audit.parse_strict_json_text('{"n":' + str((1 << oracle.MAX_JSON_INT_BITS) - 1) + "}", "maxb")["n"] > 0,
            "exact 4096-bit int",
        )
        _check(
            audit.parse_strict_json_text('{"n":-' + str((1 << oracle.MAX_JSON_INT_BITS) - 1) + "}", "negd")["n"] < 0,
            "exact neg 4096-bit int",
        )
        _expect_err(lambda: audit.parse_strict_json_text(123, "x"), "INVALID_JSON_TEXT", "non-str")
        _expect_err(lambda: audit.parse_strict_json_text("{}", "x", require_object=1), "INVALID_BOOL_TYPE", "non-bool")  # type: ignore[arg-type]
        _expect_err(lambda: audit.parse_strict_json_text("\ufeff{}", "x"), "BOM_FORBIDDEN", "BOM")
        _expect_err(lambda: audit.parse_strict_json_text("{\x00}", "x"), "NUL_BYTE_FORBIDDEN", "NUL")
        _expect_err(lambda: audit.parse_strict_json_text('{"a":"\ud800"}', "x"), "INVALID_UTF8_SURROGATE", "raw surr")
        _expect_err(lambda: audit.parse_strict_json_text('{"a":"\\ud800"}', "x"), "INVALID_UTF8_SURROGATE", "esc surr")
        _expect_err(lambda: audit.parse_strict_json_text('{"a":"x\\u0000y"}', "x"), "NUL_BYTE_FORBIDDEN", "esc NUL")
        _expect_err(lambda: audit.parse_strict_json_text('{"a":1,"a":2}', "x"), "DUPLICATE_JSON_KEY", "dup key")
        _expect_err(lambda: audit.parse_strict_json_text('{"a":NaN}', "x"), "NONFINITE_JSON", "NaN")
        _expect_err(lambda: audit.parse_strict_json_text('{"a":1.5}', "x"), "FLOAT_FORBIDDEN", "float")
        _expect_err(lambda: audit.parse_strict_json_text('{"n":' + "9" * (audit.MAX_JSON_INT_DIGITS + 1) + "}", "x"), "INT_DIGIT_LIMIT", "digit cap")
        _expect_err(lambda: audit.parse_strict_json_text('{"n":' + "9" * audit.MAX_JSON_INT_DIGITS + "}", "x"), "INT_BIT_LIMIT", "bit cap")
        _expect_err(lambda: audit.parse_strict_json_text("[1]", "x", require_object=True), "JSON_ROOT_NOT_OBJECT", "list root")
        _expect_err(lambda: audit.parse_strict_json_text("{bad", "x"), "INVALID_JSON", "syntax error")
        _expect_err(lambda: audit._validate_json_tree({1: "x"}, "k"), "INVALID_JSON_KEY", "int key")
        _expect_err(lambda: audit._validate_json_tree({"n": 1 << oracle.MAX_JSON_INT_BITS}, "b"), "INT_BIT_LIMIT", "4097-bit")
        runtime_float = json.loads("1.5")
        runtime_nan = json.loads("NaN")
        _expect_err(lambda: audit._validate_json_tree({"f": runtime_float}, "f"), "INVALID_JSON_VALUE", "float in tree")
        # canonical_json_bytes tree validation (int bit cap, floats, NaN, cyclic dict)
        _expect_err(lambda: audit.canonical_json_bytes({"n": 10**4300}), "INT_BIT_LIMIT", "canonical 10**4300")
        _expect_err(lambda: audit.canonical_json_bytes({"f": runtime_float}), "INVALID_JSON_VALUE", "canonical float")
        _expect_err(lambda: audit.canonical_json_bytes({"f": runtime_nan}), "INVALID_JSON_VALUE", "canonical NaN")
        cyc: dict[str, Any] = {}
        cyc["self"] = cyc
        _expect_err(lambda: audit.canonical_json_bytes(cyc), "MAX_DEPTH_EXCEEDED", "canonical cyclic dict")

        ok_d: Any = 1
        for _ in range(audit.MAX_JSON_DEPTH - 1):
            ok_d = [ok_d]
        _check(type(audit.parse_strict_json_text(json.dumps({"x": ok_d}), "d64")) is dict, "depth 64")
        _expect_err(lambda: audit.parse_strict_json_text(json.dumps({"x": [ok_d]}), "d65"), "MAX_DEPTH_EXCEEDED", "depth 65")

        # /proc/kallsyms st_size==0 capped read + /dev/null write guard + max_bytes 64 MiB cap
        proc_kallsyms = Path("/proc/kallsyms")
        if proc_kallsyms.exists():
            _expect_err(lambda: audit.read_regular_bytes_capped(proc_kallsyms, "kallsyms", max_bytes=16), "FILE_TOO_LARGE", "kallsyms cap")
        dev_null = Path("/dev/null")
        if dev_null.exists():
            _expect_err(lambda: audit.write_regular_bytes_safe(dev_null, b"{}\n", "devnull"), "NOT_A_REGULAR_FILE", "devnull write")

        with tempfile.TemporaryDirectory(prefix="s34_zb_") as td:
            root = Path(td)
            cfile = root / "c.json"
            # Payload bytes check MUST fire BEFORE creating parent dirs or opening temp files
            _expect_err(
                lambda: audit.write_regular_bytes_safe(root / "never_created" / "x.json", "not-bytes", "bad_payload"),  # type: ignore[arg-type]
                "INVALID_PAYLOAD_BYTES",
                "non-bytes payload",
            )
            _check(not (root / "never_created").exists(), "bad payload created parent dir")

            audit.write_regular_bytes_safe(cfile, cert_bytes, "c")
            _check(stat.S_IMODE(os.stat(cfile).st_mode) == 0o600, "temp/final file mode must be 0o600")
            audit.write_regular_bytes_safe(cfile, b"{}\n", "c_short")
            _check(cfile.read_bytes() == b"{}\n", "atomic replace shorter failed")
            audit.write_regular_bytes_safe(cfile, cert_bytes, "c_restore")
            # Streaming >64 KiB read/write round-trip
            big_payload = b"A" * 70_000
            big_file = root / "big.bin"
            audit.write_regular_bytes_safe(big_file, big_payload, "big")
            _check(audit.read_regular_bytes_capped(big_file, "big") == big_payload, "streaming >64KiB read failed")
            # Deterministic CSPRNG temp collision retry (EEXIST)
            fixed_tok_a = "deadbeef00000001"
            fixed_tok_b = "deadbeef00000002"
            pre_tmp = root / f".s34.{os.getpid()}.{fixed_tok_a}.tmp"
            pre_tmp.write_bytes(b"pre")
            tok_iter = iter((fixed_tok_a, fixed_tok_b))
            orig_token_hex = audit.secrets.token_hex
            try:
                audit.secrets.token_hex = lambda _n=8: next(tok_iter)  # type: ignore[assignment]
                audit.write_regular_bytes_safe(cfile, cert_bytes, "c_retry")
            finally:
                audit.secrets.token_hex = orig_token_hex
            _check(pre_tmp.read_bytes() == b"pre", "preexisting tmp altered")
            pre_tmp.unlink()
            _check([p.name for p in root.glob(".s34.*.tmp")] == [], "leftover retry tmp")
            # Live pre-replace temp st_nlink != 1 detection (hardlink injected during fsync)
            orig_fsync = audit.os.fsync
            linked_alias = root / "injected_tmp_link"
            hook_armed = [True]

            def _inject_tmp_link(fd_arg: int) -> None:
                if hook_armed[0]:
                    tmps = list(root.glob(".s34.*.tmp"))
                    if tmps:
                        hook_armed[0] = False
                        _check(stat.S_IMODE(os.lstat(tmps[0]).st_mode) == 0o600, "live temp mode not 0o600")
                        os.link(tmps[0], linked_alias)
                orig_fsync(fd_arg)

            try:
                audit.os.fsync = _inject_tmp_link  # type: ignore[assignment]
                _expect_err(
                    lambda: audit.write_regular_bytes_safe(cfile, b'{"tamper":1}\n', "tmp_hl"),
                    "HARDLINK_FORBIDDEN",
                    "pre-replace temp hardlink",
                )
            finally:
                audit.os.fsync = orig_fsync
                if linked_alias.exists():
                    linked_alias.unlink()
            _check(cfile.read_bytes() == cert_bytes, "pre-replace hardlink altered target")
            _check([p.name for p in root.glob(".s34.*.tmp")] == [], "leftover temp after pre-replace hardlink")

            nested = root / "nested_a" / "sub_b" / "w.json"
            audit.write_regular_bytes_safe(nested, cert_bytes, "nested")
            _check(nested.read_bytes() == cert_bytes, "nested dir_fd create failed")
            _check(audit.read_regular_bytes_capped(cfile, "c", max_bytes=len(cert_bytes)) == cert_bytes, "exact max_bytes")
            _check(audit.read_regular_bytes_capped(cfile, "c", max_bytes=audit.MAX_ALLOWED_CAP_BYTES) == cert_bytes, "exact 64MiB cap")
            _expect_err(
                lambda: audit.read_regular_bytes_capped(cfile, "c", max_bytes=audit.MAX_ALLOWED_CAP_BYTES + 1),
                "INT_OUT_OF_RANGE",
                "over 64MiB cap",
            )
            _expect_err(lambda: audit.read_regular_bytes_capped(cfile, "c", max_bytes=len(cert_bytes) - 1), "FILE_TOO_LARGE", "max_bytes-1")

            # Hardlink target protection (zero clobber)
            hlink = root / "hlink.json"
            os.link(cfile, hlink)
            try:
                _expect_err(lambda: audit.write_regular_bytes_safe(hlink, b"tamper", "hlink"), "HARDLINK_FORBIDDEN", "hardlink write")
                _check(cfile.read_bytes() == cert_bytes, "hardlink refusal altered target")
            finally:
                hlink.unlink()

            # Path type, NUL, surrogate, root, dotdot, non-dir ancestor, dir, FIFO, chmod 000, ro parent
            _expect_err(lambda: audit.read_regular_bytes_capped(_EvilPath(cfile), "evil"), "INVALID_PATH_TYPE", "EvilPath")
            _expect_err(lambda: audit.read_regular_bytes_capped(str(cfile), "str"), "INVALID_PATH_TYPE", "str path")  # type: ignore[arg-type]
            _expect_err(lambda: audit.read_regular_bytes_capped(Path("a\x00b.json"), "nul"), "NUL_BYTE_FORBIDDEN", "NUL path")
            _expect_err(lambda: audit.read_regular_bytes_capped(Path("bad_\ud800.json"), "surr"), "INVALID_UTF8_SURROGATE", "surrogate read")
            _expect_err(lambda: audit.write_regular_bytes_safe(Path("bad_\ud800.json"), cert_bytes, "surr"), "INVALID_UTF8_SURROGATE", "surrogate write")
            _expect_err(lambda: audit.read_regular_bytes_capped(Path("/"), "root"), "NOT_A_REGULAR_FILE", "root path")
            _expect_err(lambda: audit.read_regular_bytes_capped(root / "sub" / "..", "dotdot"), "NOT_A_REGULAR_FILE", "dotdot leaf")
            _expect_err(lambda: audit.read_regular_bytes_capped(root / "no_dir" / "x.json", "nodir"), "FILE_READ_ERROR", "missing dir")
            _check(not (root / "no_dir").exists(), "read must not create dir")
            _expect_err(lambda: audit.read_regular_bytes_capped(cfile / "child.json", "nondir"), "FILE_READ_ERROR", "non-dir ancestor")
            _expect_err(lambda: audit.read_regular_bytes_capped(root / "missing.json", "missing"), "FILE_READ_ERROR", "missing file")

            adir = root / "adir"
            adir.mkdir()
            _expect_err(lambda: audit.read_regular_bytes_capped(adir, "adir"), "NOT_A_REGULAR_FILE", "dir read")
            _expect_err(lambda: audit.write_regular_bytes_safe(adir, cert_bytes, "adir"), "NOT_A_REGULAR_FILE", "dir write")
            if hasattr(os, "mkfifo"):
                fifo = root / "pipe.json"
                os.mkfifo(fifo)
                _expect_err(lambda: audit.read_regular_bytes_capped(fifo, "fifo"), "NOT_A_REGULAR_FILE", "FIFO read")
                _expect_err(lambda: audit.write_regular_bytes_safe(fifo, cert_bytes, "fifo"), "NOT_A_REGULAR_FILE", "FIFO write")

            no_perm = root / "noperm.json"
            no_perm.write_bytes(cert_bytes)
            os.chmod(no_perm, 0o000)
            try:
                if os.geteuid() != 0:
                    _expect_err(lambda: audit.read_regular_bytes_capped(no_perm, "noperm"), "FILE_READ_ERROR", "chmod 000")
            finally:
                os.chmod(no_perm, 0o600)

            ro_dir = root / "ro_dir"
            ro_dir.mkdir()
            os.chmod(ro_dir, 0o500)
            try:
                if os.geteuid() != 0:
                    _expect_err(lambda: audit.write_regular_bytes_safe(ro_dir / "x.json", cert_bytes, "ro"), "FILE_WRITE_ERROR", "ro write")
                    _expect_err(lambda: audit.write_regular_bytes_safe(ro_dir / "nd" / "x.json", cert_bytes, "ro_mk"), "FILE_WRITE_ERROR", "ro mkdir")
            finally:
                os.chmod(ro_dir, 0o700)

            # Symlinks (leaf, deep ancestor, dotdot-collapsed, PWD) + deleted CWD
            sym = root / "sym.json"
            os.symlink(cfile, sym)
            _expect_err(lambda: audit.verify_certificate_file(sym), "SYMLINK_FORBIDDEN", "symlink read")
            _expect_err(lambda: audit.write_regular_bytes_safe(sym, cert_bytes, "sym_w"), "SYMLINK_FORBIDDEN", "symlink write")
            real_sub = root / "real_sub" / "nested"
            real_sub.mkdir(parents=True)
            (real_sub / "c.json").write_bytes(cert_bytes)
            sym_dir = root / "sym_dir"
            os.symlink(root / "real_sub", sym_dir)
            _expect_err(lambda: audit.verify_certificate_file(sym_dir / "nested" / "c.json"), "SYMLINK_FORBIDDEN", "deep symlink")
            _expect_err(lambda: audit.write_regular_bytes_safe(sym_dir / "nested" / "w.json", cert_bytes, "sym_dir_w"), "SYMLINK_FORBIDDEN", "write under symlink dir")
            _expect_err(lambda: audit.verify_certificate_file(sym_dir / ".." / "real_sub" / "nested" / "c.json"), "SYMLINK_FORBIDDEN", "dotdot symlink")

            # BOM, invalid UTF-8, CRLF, pretty-printed non-canonical bytes
            bom_f = root / "bom.json"
            bom_f.write_bytes(b"\xef\xbb\xbf" + cert_bytes)
            _expect_err(lambda: audit.verify_certificate_file(bom_f), "BOM_FORBIDDEN", "BOM file")
            bad_u8 = root / "bad_u8.json"
            bad_u8.write_bytes(b"\xff\xfe")
            _expect_err(lambda: audit.verify_certificate_file(bad_u8), "INVALID_UTF8", "bad utf8")
            crlf_f = root / "crlf.json"
            crlf_f.write_bytes(cert_bytes.replace(b"\n", b"\r\n"))
            _expect_err(lambda: audit.verify_certificate_file(crlf_f), "CRLF_FORBIDDEN", "CRLF")
            pretty_f = root / "pretty.json"
            pretty_f.write_text(json.dumps(cert, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            _expect_err(lambda: audit.verify_certificate_file(pretty_f), "CERTIFICATE_BYTE_MISMATCH", "pretty JSON")

            # Relative PWD symlink, surrogate PWD, relative PWD, unset PWD, deleted CWD, & CLI tests
            orig_cwd = os.getcwd()
            orig_pwd = os.environ.get("PWD")
            try:
                os.chdir(real_sub)
                local_sym = real_sub / "local_sym"
                os.symlink(real_sub, local_sym)
                os.environ["PWD"] = str(sym_dir / "nested")
                _expect_err(lambda: audit.verify_certificate_file(Path("c.json")), "SYMLINK_ANCESTOR_FORBIDDEN", "symlink PWD")
                os.environ["PWD"] = "/nonexistent_s34_pwd_dir"
                _expect_err(lambda: audit.read_regular_bytes_capped(Path("c.json"), "missing_pwd"), "CWD_UNAVAILABLE", "missing PWD")
                os.environ["PWD"] = "/tmp/bad_\udcff_pwd"
                _expect_err(lambda: audit.read_regular_bytes_capped(Path("c.json"), "spwd"), "INVALID_UTF8_SURROGATE", "surrogate PWD")
                os.environ["PWD"] = "rel/local_sym"
                _check(audit.read_regular_bytes_capped(Path(".") / "c.json", "relpwd") == cert_bytes, "relative PWD")
                os.environ["PWD"] = str(real_sub)
                _check(audit.read_regular_bytes_capped(Path("c.json"), "realpwd") == cert_bytes, "real PWD")
                os.environ.pop("PWD", None)
                _check(audit.read_regular_bytes_capped(Path("c.json"), "nopwd") == cert_bytes, "unset PWD")

                # CLI main() positive + strict negative + flag-like & equals-syntax guards
                out_path = root / "written.json"
                obuf = io.StringIO()
                with redirect_stdout(obuf):
                    rc_w = audit.main(["--write", str(out_path)])
                _check(rc_w == 0 and out_path.read_bytes() == cert_bytes, "CLI --write")

                cbuf = io.StringIO()
                with redirect_stdout(cbuf):
                    rc_c = audit.main(["--check", str(out_path)])
                _check(rc_c == 0 and json.loads(cbuf.getvalue())["valid"] is True, "CLI --check")

                _tuple_argv = ("--standalone", "--json")
                for bad_argv, exp_code in (
                    (_tuple_argv, "INVALID_ARGV"),
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
                ):
                    ebuf = io.StringIO()
                    with redirect_stderr(ebuf):
                        rc_b = audit.main(bad_argv)  # type: ignore[arg-type]
                    err_txt = ebuf.getvalue()
                    _check(rc_b == 2 and exp_code in err_txt, f"bad argv {bad_argv!r}: rc={rc_b} err={err_txt!r}")
                _check(not (real_sub / "--json").exists(), "--write --json / --write=--json created ./--json")

                # Deleted CWD refusal (CWD_UNAVAILABLE, rc=2)
                gone = root / "gone_cwd"
                gone.mkdir()
                os.chdir(gone)
                os.rmdir(gone)
                _expect_err(lambda: audit.read_regular_bytes_capped(Path("r.json"), "r"), "CWD_UNAVAILABLE", "deleted CWD read")
                _expect_err(lambda: audit.write_regular_bytes_safe(Path("w.json"), cert_bytes, "w"), "CWD_UNAVAILABLE", "deleted CWD write")
                for g_argv in (["--check", "r.json"], ["--write", "w.json"]):
                    gbuf = io.StringIO()
                    with redirect_stderr(gbuf):
                        rc_g = audit.main(g_argv)
                    _check(rc_g == 2 and "CWD_UNAVAILABLE" in gbuf.getvalue(), f"deleted CWD CLI {g_argv}")
            finally:
                os.chdir(orig_cwd)
                if orig_pwd is None:
                    os.environ.pop("PWD", None)
                else:
                    os.environ["PWD"] = orig_pwd

            # Subprocess zero-arg, --standalone --json parity, & symlinked PWD CLI refusal
            p_def = subprocess.run([sys.executable, "-I", "-O", "-B", str(ROOT / "mdl_rosen_similarity_audit.py")], capture_output=True, timeout=60)
            _check(p_def.returncode == 0 and p_def.stdout == cert_bytes, "subprocess zero-arg mismatch")
            p_std = subprocess.run([sys.executable, "-I", "-O", "-B", str(ROOT / "mdl_rosen_similarity_audit.py"), "--standalone", "--json"], capture_output=True, timeout=60)
            _check(p_std.returncode == 0 and p_std.stdout == cert_bytes, "subprocess --standalone mismatch")
            p_pwd = subprocess.run(
                [sys.executable, "-I", "-O", "-B", str(ROOT / "mdl_rosen_similarity_audit.py"), "--check", "c.json"],
                cwd=str(real_sub),
                env={**os.environ, "PWD": str(sym_dir / "nested")},
                capture_output=True,
                text=True,
                timeout=60,
            )
            _check(p_pwd.returncode == 2 and "SYMLINK_ANCESTOR_FORBIDDEN" in p_pwd.stderr, f"subprocess symlink PWD: {p_pwd.stderr!r}")

    def test_04_live_renameat2_and_hardlink_race_stress(self) -> None:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
        renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameat2.restype = ctypes.c_int

        with tempfile.TemporaryDirectory(prefix="s34_race_") as td:
            root = Path(td)
            secret = root / "secret.txt"
            secret_bytes = b"DO_NOT_LEAK_OR_CLOBBER\n"
            secret.write_bytes(secret_bytes)

            # Part A: >= 520-iter concurrent renameat2(RENAME_EXCHANGE) leaf + intermediate dir race
            real_dir = root / "real_dir"
            real_dir.mkdir()
            target_a = real_dir / "target.json"
            target_a.write_bytes(b'{"ok":1}\n')
            sym_leaf = root / "sym_leaf.json"
            os.symlink(secret, sym_leaf)
            swap_dir = root / "swap_dir"
            os.symlink(root, swap_dir)

            stop_ev = threading.Event()
            p1_b = os.fsencode(target_a)
            p2_b = os.fsencode(sym_leaf)
            d1_b = os.fsencode(real_dir)
            d2_b = os.fsencode(swap_dir)

            def _flipper() -> None:
                while not stop_ev.is_set():
                    renameat2(_AT_FDCWD, p1_b, _AT_FDCWD, p2_b, _RENAME_EXCHANGE)
                    renameat2(_AT_FDCWD, d1_b, _AT_FDCWD, d2_b, _RENAME_EXCHANGE)

            t = threading.Thread(target=_flipper, daemon=True)
            t.start()
            leaks = 0
            clobbers = 0
            try:
                for _ in range(520):
                    try:
                        got = audit.read_regular_bytes_capped(real_dir / "target.json", "race_r")
                        if b"DO_NOT_LEAK" in got:
                            leaks += 1
                    except oracle.MdlRosenError:
                        pass
                    try:
                        audit.write_regular_bytes_safe(real_dir / "target.json", b'{"ok":2}\n', "race_w")
                    except oracle.MdlRosenError:
                        pass
                    if secret.read_bytes() != secret_bytes:
                        clobbers += 1
            finally:
                stop_ev.set()
                t.join(timeout=5)

            _check(leaks == 0 and clobbers == 0, f"renameat2 race failed: leaks={leaks}, clobbers={clobbers}")
            _check(secret.read_bytes() == secret_bytes, "secret clobbered in renameat2 race")

            # Part B: >= 420-iter concurrent os.link()/os.unlink() hardlink inode-immutability race
            hl_dir = root / "hl_dir"
            hl_dir.mkdir()
            hl_target = hl_dir / "cert.json"
            hl_alias = hl_dir / "alias.json"
            hl_target.write_bytes(b'{"iter":-1}\n')

            stop_hl = threading.Event()
            links_created = [0]
            hl_clobbers = [0]

            def _linker() -> None:
                while not stop_hl.is_set():
                    try:
                        os.link(hl_target, hl_alias)
                        links_created[0] += 1
                    except OSError:
                        continue
                    try:
                        snap = hl_alias.read_bytes()
                        for _ in range(8):
                            if hl_alias.read_bytes() != snap:
                                hl_clobbers[0] += 1
                    except OSError:
                        pass
                    finally:
                        try:
                            os.unlink(hl_alias)
                        except OSError:
                            pass

            t_hl = threading.Thread(target=_linker, daemon=True)
            t_hl.start()
            try:
                for i in range(420):
                    payload = f'{{"iter":{i}}}\n'.encode("ascii")
                    try:
                        audit.write_regular_bytes_safe(hl_target, payload, "hl_w")
                    except oracle.MdlRosenError as exc:
                        _check(exc.code == "HARDLINK_FORBIDDEN", f"unexpected hardlink error {exc.code}")
            finally:
                stop_hl.set()
                t_hl.join(timeout=5)
            _check(hl_clobbers[0] == 0 and links_created[0] > 0, f"hardlink race failed: clobbers={hl_clobbers[0]}")
            leftovers = [p.name for p in hl_dir.iterdir() if p.name.startswith(".s34.")]
            _check(len(leftovers) == 0, f"leftover temp files: {leftovers}")

            # Part C: Concurrent writer stress (16T distinct + 16T same-target + 80T barrier burst)
            cw_dir = root / "cw_dir"
            cw_dir.mkdir()
            cw_errs: list[str] = []

            def _distinct_worker(idx: int) -> None:
                p = cw_dir / f"t_{idx}.json"
                data = f'{{"worker":{idx}}}\n'.encode("ascii")
                try:
                    for _ in range(4):
                        audit.write_regular_bytes_safe(p, data, f"dw_{idx}")
                    if p.read_bytes() != data or stat.S_IMODE(os.stat(p).st_mode) != 0o600:
                        cw_errs.append(f"distinct_mismatch_{idx}")
                except BaseException as exc:
                    cw_errs.append(f"distinct_{idx}:{exc}")

            t_dist = [threading.Thread(target=_distinct_worker, args=(i,)) for i in range(16)]
            for th in t_dist:
                th.start()
            for th in t_dist:
                th.join(timeout=15)
            _check(cw_errs == [], f"16T distinct write errors: {cw_errs}")

            same_target = cw_dir / "shared.json"
            valid_16 = {f'{{"same":{i}}}\n'.encode("ascii") for i in range(16)}

            def _same_worker(idx: int) -> None:
                data = f'{{"same":{idx}}}\n'.encode("ascii")
                try:
                    for _ in range(4):
                        audit.write_regular_bytes_safe(same_target, data, f"sw_{idx}")
                except BaseException as exc:
                    cw_errs.append(f"same_{idx}:{exc}")

            t_same = [threading.Thread(target=_same_worker, args=(i,)) for i in range(16)]
            for th in t_same:
                th.start()
            for th in t_same:
                th.join(timeout=15)
            _check(cw_errs == [] and same_target.read_bytes() in valid_16, f"16T same-target errors: {cw_errs}")

            burst_target = cw_dir / "burst80.json"
            valid_80 = {f'{{"burst":{i}}}\n'.encode("ascii") for i in range(80)}
            bar80 = threading.Barrier(80)

            def _burst_worker(idx: int) -> None:
                data = f'{{"burst":{idx}}}\n'.encode("ascii")
                try:
                    bar80.wait(timeout=10)
                    audit.write_regular_bytes_safe(burst_target, data, f"bw_{idx}")
                except BaseException as exc:
                    cw_errs.append(f"burst_{idx}:{exc}")

            t_burst = [threading.Thread(target=_burst_worker, args=(i,)) for i in range(80)]
            for th in t_burst:
                th.start()
            for th in t_burst:
                th.join(timeout=20)
            cw_leftovers = [p.name for p in cw_dir.iterdir() if p.name.startswith(".s34.")]
            _check(
                cw_errs == [] and burst_target.read_bytes() in valid_80 and cw_leftovers == [],
                f"80T burst errors={cw_errs} leftovers={cw_leftovers}",
            )


if __name__ == "__main__":
    unittest.main()
