#!/usr/bin/env python3
"""R5 adversarial & mutation-killing test suite for aletheia/gates_v2.py.

Zero bare asserts. Covers every fail-closed guard, boundary, and red-team bypass
across all 7 Aletheia v2.0 pure-Q gates (R6/R7, Two-Direction R3, Sampled NOT_SHOWN,
Oracle Contract, Gate-8 Subspace Latch, Law 2b Transformational Steelman, Own-Terms-First).
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
import unittest

CLI_ROOT = Path(__file__).resolve().parent.parent
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

from aletheia import gates_v2 as g2


def _assert_no_floats(tc: unittest.TestCase, obj: object) -> None:
    if isinstance(obj, float):
        tc.fail(f"Forbidden float encountered: {obj!r}")
    if isinstance(obj, dict):
        for k, v in obj.items():
            _assert_no_floats(tc, k)
            _assert_no_floats(tc, v)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _assert_no_floats(tc, item)


def _valid_rules(**kw):
    d = {
        "rule_id": "rule.v2.test",
        "expected_check_ids": ["c1", "c2"],
        "min_sq_norm": "0",
        "max_sq_norm": "20",
        "expected_header_alpha": "4",
        "max_vector_dim": 4,
    }
    d.update(kw)
    return d


def _valid_payload(alpha: str = "4", vec: list[str] | None = None, **sub_kw):
    v = ["3", "2", "1"] if vec is None else vec
    raw = (json.dumps({"header_alpha": alpha, "vector_entries": v}, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    sq = sum((g2._parse_exact_rational(x) ** 2 for x in v), Fraction(0, 1))
    sub = {
        "declared_sha256": hashlib.sha256(raw).hexdigest(),
        "declared_sq_norm": g2._fmt_q(sq),
        "declared_header_alpha": alpha,
        "declared_status": "PASS",
        "submitter_rule_overrides": {},
    }
    sub.update(sub_kw)
    return raw, sub


def _valid_steelman_rescue(**kw):
    d = {
        "proposed_verdict": "TRANSFORMED_EXACT",
        "families_searched": ["T1_GAUGE_SIMILARITY"],
        "literal_failure_witness": "row sums [3/2, 3/4] != [1, 1]",
        "transform_family": "T1_GAUGE_SIMILARITY",
        "preserved_invariant_core": "tr=1, det=0 similarity spectrum",
        "modified_hypotheses": "non-stochastic diagonal gauge similarity",
        "transform_rank": 1,
        "transform_dof": 0,
        "held_out_constraints": 1,
        "fixed_globally": True,
        "null_false_passes": 0,
        "null_total": 10,
        "max_null_rate": "1/10",
        "max_residual_gap": "0",
        "surviving_obstruction": None,
    }
    d.update(kw)
    return d


def _valid_steelman_falsified(**kw):
    d = {
        "proposed_verdict": "INVARIANT_FALSIFIED",
        "families_searched": sorted(g2.MORPHISM_FAMILIES),
        "literal_failure_witness": "zero models vs 8 models under identical spectrum",
        "transform_family": None,
        "preserved_invariant_core": None,
        "modified_hypotheses": None,
        "transform_rank": 0,
        "transform_dof": 0,
        "held_out_constraints": 1,
        "fixed_globally": True,
        "null_false_passes": 0,
        "null_total": 10,
        "max_null_rate": "1/10",
        "max_residual_gap": "1",
        "surviving_obstruction": "parity_model_count_invariant",
    }
    d.update(kw)
    return d


def _valid_otf_spec(**kw):
    d = {
        "measurable_definition_present": True,
        "pinned_net_ids": ["net_a", "net_b"],
        "per_net_alpha": "1/50",
        "max_fwer": "1/20",
        "min_signal_margin": "1/10",
        "max_control_score": "1/20",
    }
    d.update(kw)
    return d


def _valid_otf_rows():
    return [
        {"net_id": "net_a", "observed_score": "3/10", "iid_null_score": "1/20", "spectrum_null_score": "1/10", "control_score": "1/20"},
        {"net_id": "net_b", "observed_score": "3/10", "iid_null_score": "-1/5", "spectrum_null_score": "-1/5", "control_score": "-1/20"},
    ]


class TestGatesV2R5(unittest.TestCase):
    def test_01_helpers_rational_json_and_typed_equal(self) -> None:
        self.assertEqual(g2._parse_exact_rational(Fraction(2, 3)), Fraction(2, 3))
        self.assertEqual(g2._parse_exact_rational(0), Fraction(0, 1))
        self.assertEqual(g2._parse_exact_rational("-5/1"), Fraction(-5, 1))
        self.assertEqual(g2._fmt_q(Fraction(4, 1)), "4")
        self.assertEqual(g2._fmt_q(Fraction(3, 5)), "3/5")
        self.assertTrue(g2._strict_typed_equal({"a": [1, (True, "x")]}, {"a": [1, (True, "x")]}))
        self.assertFalse(g2._strict_typed_equal(1, True))
        self.assertFalse(g2._strict_typed_equal({"a": 1}, {"b": 1}))
        self.assertFalse(g2._strict_typed_equal([1], [True]))
        self.assertFalse(g2._strict_typed_equal([1], [1, 2]))

        for bad, code in (
            (True, "RATIONAL_TYPE_OR_SYNTAX"),
            (1.5, "RATIONAL_TYPE_OR_SYNTAX"),
            ("1/2\n", "RATIONAL_TYPE_OR_SYNTAX"),
            ("1/2/3", "RATIONAL_TOO_MANY_SLASHES"),
            ("-", "RATIONAL_INVALID_NUMERATOR"),
            ("1/", "RATIONAL_INVALID_DENOMINATOR"),
            ("1/0", "RATIONAL_NONPOSITIVE_DENOMINATOR"),
        ):
            with self.assertRaisesRegex(ValueError, code):
                g2._parse_exact_rational(bad)

        with self.assertRaisesRegex(ValueError, "FLOAT_FORBIDDEN"):
            g2._verify_no_floats({"a": [1, 0.5]})
        with self.assertRaisesRegex(ValueError, "PAYLOAD_INVALID_UTF8"):
            g2._parse_strict_json_bytes(b"\xff\xfe")
        with self.assertRaisesRegex(ValueError, "PAYLOAD_INVALID_JSON"):
            g2._parse_strict_json_bytes(b"{bad")
        with self.assertRaisesRegex(ValueError, "JSON_FLOAT_FORBIDDEN"):
            g2._parse_strict_json_bytes(b'{"a": 1.25}')
        with self.assertRaisesRegex(ValueError, "JSON_CONSTANT_FORBIDDEN"):
            g2._parse_strict_json_bytes(b'{"a": NaN}')
        with self.assertRaisesRegex(ValueError, "JSON_DUPLICATE_KEY"):
            g2._parse_strict_json_bytes(b'{"a": 1, "a": 2}')
        with self.assertRaisesRegex(ValueError, "PAYLOAD_ROOT_NOT_OBJECT"):
            g2._parse_strict_json_bytes(b"[1]")

    def test_02_r6_r7_gate_boundaries_and_rejections(self) -> None:
        raw0, sub0 = _valid_payload("4", ["0"], declared_status="CANDIDATE")
        res0 = g2.evaluate_r6_r7_gate(_valid_rules(min_sq_norm="0", max_sq_norm="0", max_vector_dim=1), sub0, raw0)
        self.assertEqual(res0["status"], "ACCEPTED")
        raw20, sub20 = _valid_payload("4", ["4", "2", "0", "0"])
        res20 = g2.evaluate_r6_r7_gate(_valid_rules(min_sq_norm="20", max_sq_norm="20", max_vector_dim=4), sub20, raw20)
        self.assertEqual(res20["measured_sq_norm"], "20")

        raw, sub = _valid_payload()
        for rules, code in (
            ([], "R6_PINNED_RULES_SCHEMA_MISMATCH"),
            (_valid_rules(rule_id="bad\n"), "R6_INVALID_RULE_ID"),
            (_valid_rules(expected_check_ids=[]), "R6_EMPTY_CHECK_IDS"),
            (_valid_rules(expected_check_ids=["c1", " "]), "R6_INVALID_CHECK_ID"),
            (_valid_rules(expected_check_ids=["c1", "C1"]), "R6_DUPLICATE_CHECK_ID"),
            (_valid_rules(min_sq_norm="-1"), "R6_NEGATIVE_MIN_SQ_NORM"),
            (_valid_rules(min_sq_norm="5", max_sq_norm="4"), "R6_INVERTED_SQ_NORM_RANGE"),
            (_valid_rules(expected_header_alpha="0"), "R6_NONPOSITIVE_EXPECTED_ALPHA"),
            (_valid_rules(max_vector_dim=0), "R6_INVALID_MAX_VECTOR_DIM"),
            (_valid_rules(max_vector_dim=True), "R6_INVALID_MAX_VECTOR_DIM"),
        ):
            with self.assertRaisesRegex(ValueError, code):
                g2.evaluate_r6_r7_gate(rules, sub, raw)  # type: ignore[arg-type]

        rules = _valid_rules()
        for bad_sub, bad_raw, code in (
            ([], raw, "R6_SUBMISSION_SCHEMA_MISMATCH"),
            ({**sub, "submitter_rule_overrides": []}, raw, "R6_OVERRIDES_NOT_OBJECT"),
            ({**sub, "submitter_rule_overrides": {"max_sq_norm": "999"}}, raw, "R6_SUBMITTER_RULE_OVERRIDE"),
            ({**sub, "declared_status": "PASS\n"}, raw, "R6_INVALID_DECLARED_STATUS"),
            (sub, "not-bytes", "R7_ARTIFACT_NOT_BYTES"),
            (sub, b"", "R7_NULL_ARTIFACT_BYTES"),
            ({**sub, "declared_sha256": sub["declared_sha256"] + "\n"}, raw, "R7_INVALID_DECLARED_SHA256"),
            ({**sub, "declared_sha256": "0" * 64}, raw, "R7_DECLARED_SHA256_MISMATCH"),
            ({**sub, "declared_sq_norm": "13"}, raw, "R7_DECLARED_NORM_MISMATCH"),
            ({**sub, "declared_header_alpha": "5"}, raw, "R7_DECLARED_ALPHA_MISMATCH"),
        ):
            with self.assertRaisesRegex(ValueError, code):
                g2.evaluate_r6_r7_gate(rules, bad_sub, bad_raw)  # type: ignore[arg-type]

        bad_p = b'{"header_alpha":"4","vector_entries":["1"],"extra":1}\n'
        with self.assertRaisesRegex(ValueError, "R7_PAYLOAD_SCHEMA_MISMATCH"):
            g2.evaluate_r6_r7_gate(rules, {**sub, "declared_sha256": hashlib.sha256(bad_p).hexdigest()}, bad_p)
        empty_v = b'{"header_alpha":"4","vector_entries":[]}\n'
        with self.assertRaisesRegex(ValueError, "R7_EMPTY_VECTOR_ENTRIES"):
            g2.evaluate_r6_r7_gate(rules, {**sub, "declared_sha256": hashlib.sha256(empty_v).hexdigest()}, empty_v)
        big_v, sub_bv = _valid_payload("4", ["1", "1", "1", "1", "1"])
        with self.assertRaisesRegex(ValueError, "R6_VECTOR_DIM_EXCEEDS_MAX"):
            g2.evaluate_r6_r7_gate(rules, sub_bv, big_v)
        raw_a8, sub_a8 = _valid_payload("8", ["1"])
        with self.assertRaisesRegex(ValueError, "R6_HEADER_ALPHA_OUT_OF_SPEC"):
            g2.evaluate_r6_r7_gate(rules, sub_a8, raw_a8)
        raw_lo, sub_lo = _valid_payload("4", ["1"])
        with self.assertRaisesRegex(ValueError, "R6_MEASURED_NORM_BELOW_MIN"):
            g2.evaluate_r6_r7_gate(_valid_rules(min_sq_norm="2"), sub_lo, raw_lo)
        raw_hi, sub_hi = _valid_payload("4", ["5"])
        with self.assertRaisesRegex(ValueError, "R6_MEASURED_NORM_ABOVE_MAX"):
            g2.evaluate_r6_r7_gate(rules, sub_hi, raw_hi)

    def test_03_two_direction_r3_sampled_and_oracle_contracts(self) -> None:
        ok = {"flag": True, "v": "VERIFIED"}
        bad = {"flag": True, "v": "FAILED"}
        ok_m = {"flag": 1, "v": "VERIFIED"}
        bad_m = {"flag": 1, "v": "FAILED"}

        def strict_fn(r):
            return isinstance(r, dict) and isinstance(r.get("flag"), bool) and r["flag"] and r.get("v") == "VERIFIED"

        def note_d_fn(r):
            if r.get("flag") is False:
                return False
            if r.get("flag") is True and r.get("v") != "VERIFIED":
                return False
            return True

        with self.assertRaisesRegex(ValueError, "R3_EMPTY_DIR1_CASES"):
            g2.certify_two_direction_r3(strict_fn, ok, bad, [], [("d2", bad_m)])
        with self.assertRaisesRegex(ValueError, "R3_EMPTY_DIR2_CASES"):
            g2.certify_two_direction_r3(strict_fn, ok, bad, [("d1", ok_m)], [])
        with self.assertRaisesRegex(ValueError, "R3_BASELINE_ACCEPT_FAILED"):
            g2.certify_two_direction_r3(strict_fn, bad, bad, [("d1", ok_m)], [("d2", bad_m)])
        with self.assertRaisesRegex(ValueError, "R3_BASELINE_REJECT_FAILED"):
            g2.certify_two_direction_r3(strict_fn, ok, ok, [("d1", ok_m)], [("d2", bad_m)])
        with self.assertRaisesRegex(ValueError, "R3_INVALID_DIR1_LABEL"):
            g2.certify_two_direction_r3(strict_fn, ok, bad, [(" ", ok_m)], [("d2", bad_m)])
        with self.assertRaisesRegex(ValueError, "R3_INVALID_DIR2_LABEL"):
            g2.certify_two_direction_r3(strict_fn, ok, bad, [("d1", ok_m)], [("", bad_m)])
        with self.assertRaisesRegex(ValueError, "R3_DUPLICATE_LABEL"):
            g2.certify_two_direction_r3(strict_fn, ok, bad, [("a", ok_m), ("A", {"flag": "true", "v": "VERIFIED"})], [("d2", bad_m)])
        with self.assertRaisesRegex(ValueError, "R3_DUPLICATE_LABEL"):
            g2.certify_two_direction_r3(strict_fn, ok, bad, [("a", ok_m)], [("A", bad_m)])
        with self.assertRaisesRegex(ValueError, "R3_NOOP_DIR1_CASE"):
            g2.certify_two_direction_r3(strict_fn, ok, bad, [("n1", dict(ok))], [("d2", bad_m)])
        with self.assertRaisesRegex(ValueError, "R3_NOOP_DIR2_CASE"):
            g2.certify_two_direction_r3(strict_fn, ok, bad, [("d1", ok_m)], [("n2", dict(bad))])

        res_vuln = g2.certify_two_direction_r3(note_d_fn, ok, bad, [("d1_int1", ok_m)], [("d2_int1", bad_m)])
        self.assertFalse(res_vuln["passed"])
        self.assertEqual(res_vuln["dir1_failures"], ["d1_int1"])
        self.assertEqual(res_vuln["dir2_failures"], ["d2_int1"])

        # Sampled integrity
        self.assertEqual(g2.evaluate_sampled_integrity(0, 1, 0)["verdict"], "NOT_SHOWN")
        self.assertEqual(g2.evaluate_sampled_integrity(4, 4, 0)["verdict"], "PASS")
        self.assertEqual(g2.evaluate_sampled_integrity(4, 4, 4)["verdict"], "FAIL")
        for args, code in (
            ((0, 0, 0), "SAMPLED_INVALID_TOTAL"),
            ((0, True, 0), "SAMPLED_INVALID_TOTAL"),
            ((-1, 2, 0), "SAMPLED_INVALID_TESTED"),
            ((3, 2, 0), "SAMPLED_INVALID_TESTED"),
            ((2, 2, -1), "SAMPLED_INVALID_HITS"),
            ((2, 2, 3), "SAMPLED_INVALID_HITS"),
        ):
            with self.assertRaisesRegex(ValueError, code):
                g2.evaluate_sampled_integrity(*args)  # type: ignore[arg-type]

        # Oracle contracts
        self.assertTrue(g2.certify_oracle_contract({"oracle_class": "exact", "evidence_basis": "formal_proof", "feedback_channel": "full_counterexample_and_repair"})["valid"])
        self.assertTrue(g2.certify_oracle_contract({"oracle_class": "sampled", "evidence_basis": "random_finite_sample_exact_arithmetic", "feedback_channel": "family_only_with_fresh_post_repair_seed"})["valid"])
        self.assertTrue(g2.certify_oracle_contract({"oracle_class": "reference_replay", "evidence_basis": "untouched_upstream_replay", "feedback_channel": "diff_against_upstream_reference"})["valid"])
        for spec, code in (
            ({}, "ORACLE_CONTRACT_SCHEMA_MISMATCH"),
            ({"oracle_class": "bad", "evidence_basis": "x", "feedback_channel": "y"}, "ORACLE_UNKNOWN_CLASS"),
            ({"oracle_class": "exact", "evidence_basis": "", "feedback_channel": "y"}, "ORACLE_INVALID_BASIS"),
            ({"oracle_class": "exact", "evidence_basis": "formal_proof", "feedback_channel": " "}, "ORACLE_INVALID_FEEDBACK"),
            ({"oracle_class": "exact", "evidence_basis": "random_finite_sample_exact_arithmetic", "feedback_channel": "full_counterexample_and_repair"}, "ORACLE_EXACT_REQUIRES_NON_SAMPLED_BASIS"),
            ({"oracle_class": "sampled", "evidence_basis": "formal_proof", "feedback_channel": "family_only_with_fresh_post_repair_seed"}, "ORACLE_SAMPLED_INVALID_BASIS"),
            ({"oracle_class": "anchor", "evidence_basis": "untouched_upstream_replay", "feedback_channel": "none_to_proposer_spec_owner_only"}, "ORACLE_ANCHOR_REQUIRES_EXTERNAL_DATA"),
            ({"oracle_class": "reference_replay", "evidence_basis": "external_domain_data", "feedback_channel": "diff_against_upstream_reference"}, "ORACLE_REPLAY_REQUIRES_UPSTREAM"),
            ({"oracle_class": "anchor", "evidence_basis": "external_domain_data", "feedback_channel": "full_counterexample_and_repair"}, "ORACLE_FEEDBACK_CHANNEL_MISMATCH"),
        ):
            with self.assertRaisesRegex(ValueError, code):
                g2.certify_oracle_contract(spec)

    def test_04_gate8_subspace_latch(self) -> None:
        r0 = g2.certify_gate8_subspace_latch([["0", "0"]], ["3", "4"], "0", "1")
        self.assertEqual(r0["phi_rank"], 0)
        self.assertEqual(r0["decision"], "WITHIN_POSTFIT_BUDGET")
        r_bnd = g2.certify_gate8_subspace_latch([["0", "1", "0"], ["1", "0", "0"], ["0", "0", "0"]], ["1", "2", "2"], "3", "3")
        self.assertEqual(r_bnd["sin2_theta_attenuation"], "4/9")
        self.assertEqual(r_bnd["decision"], "WITHIN_POSTFIT_BUDGET")
        r_sat = g2.certify_gate8_subspace_latch([["1", "0"], ["0", "1"]], ["1", "1"], "0", "1")
        self.assertEqual(r_sat["decision"], "SATURATED_NO_SURVIVING_AUDITS")
        r_blind = g2.certify_gate8_subspace_latch([["1", "0", "0"]], ["2", "0", "0"], "0", "1")
        self.assertEqual(r_blind["decision"], "BLIND_AUDIT_IN_COL_PHI")
        self.assertTrue(r_blind["halt"])
        r_halt = g2.certify_gate8_subspace_latch([["1", "0", "0"]], ["0", "1", "0"], "3", "1")
        self.assertEqual(r_halt["decision"], "LATCH_HALT")
        self.assertEqual(g2._solve_linear_q([[Fraction(0), Fraction(2)], [Fraction(3), Fraction(1)]], [Fraction(4), Fraction(5)]), [Fraction(1), Fraction(2)])

        with self.assertRaisesRegex(ValueError, "LATCH_SINGULAR_GRAM"):
            g2._solve_linear_q([[Fraction(1), Fraction(1)], [Fraction(1), Fraction(1)]], [Fraction(1), Fraction(1)])
        for args, code in (
            (([], ["1"], "0", "1"), "LATCH_EMPTY_PHI"),
            (([[]], ["1"], "0", "1"), "LATCH_EMPTY_PHI_COLUMN"),
            (([["1", "0"], ["1"]], ["1", "0"], "0", "1"), "LATCH_RAGGED_PHI"),
            (([["1", "0"]], ["1"], "0", "1"), "LATCH_AUDIT_VECTOR_DIM_MISMATCH"),
            (([["1", "0"]], ["0", "0"], "0", "1"), "LATCH_ZERO_AUDIT_VECTOR"),
            (([["1", "0"]], ["0", "1"], "-1", "1"), "LATCH_NEGATIVE_RESIDUAL"),
            (([["1", "0"]], ["0", "1"], "0", "0"), "LATCH_NONPOSITIVE_NOISE_VAR"),
        ):
            with self.assertRaisesRegex(ValueError, code):
                g2.certify_gate8_subspace_latch(*args)  # type: ignore[arg-type]

    def test_05_law2b_transformational_steelman_guards(self) -> None:
        # Exact rescue, bounded core, zero max_null_rate, and exhaustive invariant falsified
        self.assertEqual(g2.certify_transformational_steelman(_valid_steelman_rescue())["status"], "CERTIFIED_TRANSFORMED_EXACT")
        self.assertEqual(
            g2.certify_transformational_steelman(_valid_steelman_rescue(proposed_verdict="BOUNDED_TRANSFORM_CORE", max_residual_gap="1/4", max_null_rate="0", null_total=1))["status"],
            "CERTIFIED_BOUNDED_TRANSFORM_CORE",
        )
        self.assertEqual(
            g2.certify_transformational_steelman(_valid_steelman_rescue(null_false_passes=1, null_total=10, max_null_rate="1/10"))["null_false_pass_rate"],
            "1/10",
        )
        self.assertEqual(g2.certify_transformational_steelman(_valid_steelman_falsified())["status"], "CERTIFIED_INVARIANT_FALSIFIED")

        for spec, code in (
            ({}, "TS_SCHEMA_MISMATCH"),
            (_valid_steelman_rescue(max_residual_gap=0.0), "FLOAT_FORBIDDEN"),
            (_valid_steelman_rescue(proposed_verdict="FALSIFIED_RAW"), "G4_RAW_FALSIFIED_FORBIDDEN"),
            (_valid_steelman_rescue(proposed_verdict="MAYBE"), "TS_INVALID_VERDICT"),
            (_valid_steelman_rescue(families_searched=[]), "TS_EMPTY_FAMILIES_SEARCHED"),
            (_valid_steelman_rescue(families_searched=["T99"]), "TS_UNKNOWN_MORPHISM_FAMILY"),
            (_valid_steelman_rescue(families_searched=["T1_GAUGE_SIMILARITY", "T1_GAUGE_SIMILARITY"]), "TS_DUPLICATE_MORPHISM_FAMILY"),
            (_valid_steelman_rescue(literal_failure_witness=""), "G3_MISSING_LITERAL_FAILURE_WITNESS"),
            (_valid_steelman_rescue(fixed_globally=1), "G2_INVALID_FIXED_GLOBALLY_TYPE"),
            (_valid_steelman_rescue(fixed_globally=False), "G2_NOT_FIXED_GLOBALLY"),
            (_valid_steelman_rescue(transform_rank=-1), "G1_INVALID_TRANSFORM_RANK"),
            (_valid_steelman_rescue(transform_dof=-1), "G2_INVALID_TRANSFORM_DOF"),
            (_valid_steelman_rescue(held_out_constraints=0), "G2_INVALID_CONSTRAINTS"),
            (_valid_steelman_rescue(null_total=0), "G1_EMPTY_NULL_SUITE"),
            (_valid_steelman_rescue(null_false_passes=-1), "G1_INVALID_NULL_FALSE_PASSES"),
            (_valid_steelman_rescue(null_false_passes=11), "G1_INVALID_NULL_FALSE_PASSES"),
            (_valid_steelman_rescue(max_null_rate="-1/100"), "G1_MAX_NULL_RATE_OUT_OF_RANGE"),
            (_valid_steelman_rescue(max_null_rate="11/100"), "G1_MAX_NULL_RATE_OUT_OF_RANGE"),
            (_valid_steelman_rescue(null_false_passes=2, null_total=10, max_null_rate="1/10"), "G1_NULL_FALSE_PASS_EXCEEDED"),
            (_valid_steelman_rescue(max_residual_gap="-1"), "G3_NEGATIVE_RESIDUAL_GAP"),
            # INVARIANT_FALSIFIED dual guards
            (_valid_steelman_falsified(families_searched=["T1_GAUGE_SIMILARITY"]), "G4_INCOMPLETE_MORPHISM_SEARCH"),
            (_valid_steelman_falsified(surviving_obstruction=None), "G4_MISSING_SURVIVING_OBSTRUCTION"),
            (_valid_steelman_falsified(preserved_invariant_core="core"), "G4_CONTRADICTORY_RESCUE_FIELDS_ON_FALSIFIED"),
            (_valid_steelman_falsified(transform_rank=1), "G4_CONTRADICTORY_RESCUE_FIELDS_ON_FALSIFIED"),
            (_valid_steelman_falsified(max_residual_gap="0"), "G4_FALSIFIED_HAS_ZERO_GAP"),
            # Rescue anti-epicycle guards
            (_valid_steelman_rescue(surviving_obstruction="obs"), "G0_CONTRADICTORY_OBSTRUCTION_ON_RESCUE"),
            (_valid_steelman_rescue(transform_family="T2_AFFINE_BREGMAN_SHIFT"), "G3_TRANSFORM_FAMILY_NOT_SEARCHED"),
            (_valid_steelman_rescue(preserved_invariant_core=""), "G3_MISSING_SCOPE_DELTA"),
            (_valid_steelman_rescue(modified_hypotheses=""), "G3_MISSING_SCOPE_DELTA"),
            (_valid_steelman_rescue(transform_rank=0), "G1_DEGENERATE_ZERO_RANK_TRANSFORM"),
            (_valid_steelman_rescue(transform_dof=1, held_out_constraints=1), "G2_DOF_EXCEEDS_CONSTRAINTS"),
            (_valid_steelman_rescue(null_total=9, max_null_rate="1/10"), "G1_INSUFFICIENT_NULL_RESOLUTION"),
            (_valid_steelman_rescue(max_residual_gap="1/100"), "G3_EXACT_RESCUE_HAS_NONZERO_GAP"),
        ):
            with self.assertRaisesRegex(ValueError, code):
                g2.certify_transformational_steelman(spec)

    def test_06_own_terms_first_phase1_and_selftest(self) -> None:
        # Exact boundary pass (Bonferroni 2 * 1/40 = 1/20, obs - abs(null) = 1/10 == min_margin, ctrl = 1/20 == max_ctrl)
        ok_res = g2.certify_own_terms_phase1(_valid_otf_spec(per_net_alpha="1/40", max_fwer="1/20"), _valid_otf_rows())
        self.assertTrue(ok_res["certified"])
        self.assertEqual(ok_res["min_iid_margin"], "1/10")

        # Rule 6 return-to-author (no floats and list/sequence types validated BEFORE early return -> OTF-BUG-01, ALETHEIA-V2-BUG-03)
        r6 = g2.certify_own_terms_phase1(_valid_otf_spec(measurable_definition_present=False, pinned_net_ids=[]), [])
        self.assertEqual(r6["decision"], "RETURN_TO_AUTHOR_FOR_DEFINITION")
        with self.assertRaisesRegex(ValueError, "FLOAT_FORBIDDEN"):
            g2.certify_own_terms_phase1(_valid_otf_spec(measurable_definition_present=False), [0.5])  # type: ignore[list-item]
        with self.assertRaisesRegex(ValueError, "OTF_MEASUREMENTS_NOT_LIST"):
            g2.certify_own_terms_phase1(_valid_otf_spec(measurable_definition_present=False), "NOT_A_LIST")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "OTF_PINNED_NETS_NOT_SEQUENCE"):
            g2.certify_own_terms_phase1(_valid_otf_spec(measurable_definition_present=False, pinned_net_ids="NOT_A_LIST"), [])  # type: ignore[arg-type]

        # Boundary alpha=1, max_fwer=1, max_control_score=0
        b_res = g2.certify_own_terms_phase1(
            _valid_otf_spec(pinned_net_ids=["only"], per_net_alpha="1", max_fwer="1", max_control_score="0"),
            [{"net_id": "ONLY", "observed_score": "1/10", "iid_null_score": "0", "spectrum_null_score": "0", "control_score": "0"}],
        )
        self.assertTrue(b_res["certified"])

        rows = _valid_otf_rows()
        for spec, meas, code in (
            ({}, rows, "OTF_SPEC_SCHEMA_MISMATCH"),
            (_valid_otf_spec(measurable_definition_present=1), rows, "OTF_INVALID_MEASURABLE_FLAG"),
            (_valid_otf_spec(pinned_net_ids=[]), rows, "OTF_EMPTY_PINNED_NETS"),
            (_valid_otf_spec(pinned_net_ids=["ok", " "]), rows, "OTF_INVALID_NET_ID"),
            (_valid_otf_spec(pinned_net_ids=["net_a", "NET_A"]), rows, "OTF_DUPLICATE_PINNED_NET_ID"),
            (_valid_otf_spec(per_net_alpha="0"), rows, "OTF_INVALID_ALPHA"),
            (_valid_otf_spec(per_net_alpha="11/10"), rows, "OTF_INVALID_ALPHA"),
            (_valid_otf_spec(max_fwer="0"), rows, "OTF_INVALID_MAX_FWER"),
            (_valid_otf_spec(max_fwer="11/10"), rows, "OTF_INVALID_MAX_FWER"),
            (_valid_otf_spec(min_signal_margin="0"), rows, "OTF_NONPOSITIVE_SIGNAL_MARGIN"),
            (_valid_otf_spec(max_control_score="-1/100"), rows, "OTF_NEGATIVE_MAX_CONTROL"),
            (_valid_otf_spec(per_net_alpha="1/20", max_fwer="1/20"), rows, "OTF_BONFERRONI_FWER_EXCEEDED"),
            (_valid_otf_spec(), rows[:1], "OTF_MEASUREMENT_COUNT_MISMATCH"),
            (_valid_otf_spec(), [rows[0], {}], "OTF_MEASUREMENT_SCHEMA_MISMATCH"),
            (_valid_otf_spec(), [rows[0], {**rows[1], "net_id": ""}], "OTF_INVALID_MEASUREMENT_NET_ID"),
            (_valid_otf_spec(), [rows[0], {**rows[1], "net_id": "unpinned"}], "OTF_UNPINNED_NET_ID"),
            (_valid_otf_spec(), [rows[0], {**rows[1], "net_id": "NET_A"}], "OTF_DUPLICATE_MEASUREMENT_NET_ID"),
            (_valid_otf_spec(), [rows[0], {**rows[1], "iid_null_score": "-1/4"}], "OTF_TIER4A_IID_NULL_FAILED"),
            (_valid_otf_spec(), [rows[0], {**rows[1], "spectrum_null_score": "1/4"}], "OTF_TIER4B_SPECTRUM_NULL_FAILED"),
            (_valid_otf_spec(), [rows[0], {**rows[1], "control_score": "1/10"}], "OTF_RULE5_CONTROL_CONTAMINATED"),
            (_valid_otf_spec(max_control_score="1"), [rows[0], {**rows[1], "observed_score": "1/5", "iid_null_score": "0", "spectrum_null_score": "0", "control_score": "1/5"}], "OTF_RULE5_CONTROL_CONTAMINATED"),
        ):
            with self.assertRaisesRegex(ValueError, code):
                g2.certify_own_terms_phase1(spec, meas)  # type: ignore[arg-type]

        st = g2.run_v2_gates_self_test()
        _assert_no_floats(self, st)
        self.assertTrue(st["passed"])
        self.assertEqual(st["gate8_blind_audit"]["decision"], "BLIND_AUDIT_IN_COL_PHI")


if __name__ == "__main__":
    unittest.main()
