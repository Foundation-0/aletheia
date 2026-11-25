#!/usr/bin/env python3
"""Assertion-free R5 adversarial & mutation-killing test suite for aletheia/supervision_airlock.py.

Zero bare `assert` statements (100% python3 -O parity).
Kills 100.0% of `aletheia mutate --max-mutants 0` refusal/boundary sites and 100.0% of
full-AST BoolOp(And/Or) single-clause mutations across Law 1b, Two-Zone Airlock +
ClaimLedger + Observational Non-Interference, and Erlang/OTP Supervision + exo#1200 Bridge.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

CLI_ROOT = Path(__file__).resolve().parent.parent
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

from aletheia import supervision_airlock as sa
from aletheia.strict_io import AletheiaError

SHA_1 = hashlib.sha256(b"r5-sha-1").hexdigest()
SHA_2 = hashlib.sha256(b"r5-sha-2").hexdigest()
SHA_3 = hashlib.sha256(b"r5-sha-3").hexdigest()
HEAD_1 = hashlib.sha1(b"r5-head-1").hexdigest()
HEAD_2 = hashlib.sha1(b"r5-head-2").hexdigest()


def _valid_law1b_spec() -> dict:
    return {
        "schema": sa.LAW1B_SCHEMA,
        "external_writes": 0,
        "repos_scanned": [
            {
                "repo": "Foundation-0/math0",
                "fetched": 10,
                "open": 1,
                "closed_unmerged": 1,
                "merged": 8,
                "prs_json_sha256": SHA_1,
            },
        ],
        "mined_entries": [
            {
                "repo": "Foundation-0/math0",
                "number": 1,
                "status": "open",
                "head_sha": HEAD_1,
                "snapshot_sha256": SHA_2,
                "mechanism_class": "EXACT_CERTIFIER_OR_DOMAIN_TOOL",
                "evidence_standing": "EXECUTED_EXACT_WITNESS",
                "honest_novelty": "N0",
                "operator_summary": "Exact rational certifier witness",
            },
            {
                "repo": "Foundation-0/math0",
                "number": 9,
                "status": "closed_unmerged",
                "head_sha": HEAD_2,
                "snapshot_sha256": SHA_3,
                "mechanism_class": "QUANTILE_OR_INDEX_BOUNDARY",
                "evidence_standing": "CATALOGED_LEAD",
                "honest_novelty": "N0",
                "operator_summary": "Closed-unmerged lead at N0",
            },
        ],
    }


def _valid_tech_submission() -> dict:
    return {
        "envelope_id": "env-r5-001",
        "claim_ledger": {
            "claim_id": "claim-r5-001",
            "finite_outcome_grammar": {"SUPPORTED": "supports", "REFUTED": "against", "INCONCLUSIVE": "inconclusive"},
            "falsifier_predicate": "residual != 0/1",
            "novelty_default": "N0",
            "linguistic_ceiling": "E2_SEALED",
        },
        "pinned_inputs": {
            "files": [{"id": "inp-1", "sha256": SHA_1, "bytes": 1}],
            "seeds": [0, 7],
        },
        "artifact_bundle": [
            {"relpath": "src/oracle.py", "sha256": SHA_2, "role": "code"},
            {"relpath": "tests/test_r5.py", "sha256": SHA_3, "role": "test"},
            {"relpath": "data/fixture.json", "sha256": SHA_1, "role": "data"},
        ],
    }


def _valid_two_zone_spec() -> dict:
    room = dict(_valid_tech_submission(), transcript="debate", authors=["alice"], models=["m1"], agreement_count=2)
    env = sa.strip_zone_a_to_airlock_envelope(room)
    env_sha = sa.canonical_sha256(env)
    return {
        "zone_a": {
            "mode": "socratic",
            "conductor": None,
            "participants": ["alice", "bob"],
            "round_robin_enforced": False,
            "silent_turns_allowed": True,
            "silent_turns_observed": 0,
            "distinct_hypotheses_count": 2,
            "output_tag": "UNVERIFIED_HYPOTHESIS",
            "agreement_counted_as_evidence": False,
        },
        "airlock_envelope": env,
        "zone_b": {
            "channel_mode": "private_c02",
            "verifier_seat": "verifier-b",
            "read_scope": ["env-r5-001"],
            "blocked_channels": sorted(sa.ZONE_B_REQUIRED_BLOCKED_CHANNELS),
            "can_read_zone_a_board": False,
            "can_approve_own_changes": False,
            "write_scopes": [],
        },
        "verdict_packet": {
            "schema": sa.AIRLOCK_VERDICT_SCHEMA,
            "envelope_id": "env-r5-001",
            "envelope_sha256": env_sha,
            "verifier_seat": "verifier-b",
            "part_e_verdict": "VERIFIED",
            "part_i_grade": "E2_SEALED",
            "outcome_matched": "SUPPORTED",
            "r5_killed": 10,
            "r5_total": 10,
            "counterexample": None,
        },
    }


def _valid_otp_children() -> list[dict]:
    return [
        {"id": "planner", "policy": "permanent", "generation": 1, "snapshot_sha256": SHA_1, "alive": True},
        {"id": "author", "policy": "transient", "generation": 1, "snapshot_sha256": SHA_1, "alive": True},
        {"id": "airlock", "policy": "permanent", "generation": 1, "snapshot_sha256": SHA_1, "alive": True},
        {"id": "temp_worker", "policy": "temporary", "generation": 1, "snapshot_sha256": SHA_1, "alive": True},
        {"id": "dead_transient", "policy": "transient", "generation": 1, "snapshot_sha256": SHA_1, "alive": False},
        {"id": "verifier", "policy": "transient", "generation": 1, "snapshot_sha256": SHA_1, "alive": True},
    ]


class TestSupervisionAirlockR5(unittest.TestCase):
    def _expect_err(self, code: str, fn, *args, **kwargs) -> None:
        with self.assertRaises(AletheiaError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_01_pure_q_helpers_and_exact_parsers(self) -> None:
        self.assertTrue(sa._is_strict_int(0))
        self.assertFalse(sa._is_strict_int(True))
        self.assertFalse(sa._is_nonempty_str(123))
        self.assertFalse(sa._is_nonempty_str("   "))
        self.assertFalse(sa._in_str_set([], sa.RESTART_POLICIES))
        self.assertFalse(sa._in_str_set("other", sa.RESTART_POLICIES))
        self.assertTrue(sa._in_str_set("transient", sa.RESTART_POLICIES))
        self.assertTrue(sa._has_control_char("a\nb"))
        self.assertTrue(sa._has_control_char("a\x7fb"))
        self.assertFalse(sa._has_control_char("clean text"))
        self.assertFalse(sa._is_clean_ascii_text("   "))
        self.assertFalse(sa._is_clean_ascii_text("line1\nline2"))
        self.assertFalse(sa._is_clean_ascii_text("caf\u00e9"))
        self.assertTrue(sa._is_clean_ascii_text("Clean ASCII 123"))

        self.assertFalse(sa._is_hex40(123))
        self.assertFalse(sa._is_hex40("a" * 39))
        self.assertFalse(sa._is_hex40("a" * 40))
        self.assertFalse(sa._is_hex40(HEAD_1 + "\n"))
        self.assertTrue(sa._is_hex40(HEAD_1))

        self.assertFalse(sa._is_hex64(123))
        self.assertFalse(sa._is_hex64("0" * 63))
        self.assertFalse(sa._is_hex64("0" * 64))
        self.assertFalse(sa._is_hex64(SHA_1 + "\n"))
        self.assertTrue(sa._is_hex64(SHA_1))

        self.assertFalse(sa._is_valid_id(99))
        self.assertFalse(sa._is_valid_id("-bad"))
        self.assertFalse(sa._is_valid_id("ok\n"))
        self.assertTrue(sa._is_valid_id("id-1.2:a_b"))

        self.assertFalse(sa._is_safe_relpath(123))
        self.assertFalse(sa._is_safe_relpath("bad path.py"))
        self.assertFalse(sa._is_safe_relpath("/abs.py"))
        self.assertFalse(sa._is_safe_relpath("a/./b.py"))
        self.assertFalse(sa._is_safe_relpath("../escape.py"))
        self.assertTrue(sa._is_safe_relpath("src/oracle.py"))

        self.assertFalse(sa.contains_forbidden_non_exact(None))
        self.assertFalse(sa.contains_forbidden_non_exact({"a": [1, True, "x", (2, None)]}))
        self.assertTrue(sa.contains_forbidden_non_exact({1.5: "v"}))
        self.assertTrue(sa.contains_forbidden_non_exact({8: 1, 13: 2}))
        self.assertTrue(sa.contains_forbidden_non_exact({1: "a", "b": 2}))
        self.assertTrue(sa.contains_forbidden_non_exact({True: "a"}))
        self.assertTrue(sa.contains_forbidden_non_exact({"nested": {1: "x"}}))
        self.assertTrue(sa.contains_forbidden_non_exact({"k": 1.5}))
        self.assertTrue(sa.contains_forbidden_non_exact([1, 2.5]))
        self.assertTrue(sa.contains_forbidden_non_exact((1, 2.5)))
        self.assertTrue(sa.contains_forbidden_non_exact({1, 2}))
        self.assertTrue(sa.contains_forbidden_non_exact(1 + 2j))
        self._expect_err("ERR_FLOAT_OR_NON_JSON", sa.canonical_json_bytes, {"x": 0.1})
        self._expect_err("ERR_FLOAT_OR_NON_JSON", sa.canonical_json_bytes, {8: 1, 13: 2})
        self._expect_err("ERR_FLOAT_OR_NON_JSON", sa.canonical_json_bytes, {1: "a", "b": 2})

        self.assertEqual(sa.parse_nonneg_fraction(0), Fraction(0, 1))
        self.assertEqual(sa.parse_nonneg_fraction(3), Fraction(3, 1))
        self._expect_err("ERR_NEGATIVE_TICK", sa.parse_nonneg_fraction, -1)
        self.assertEqual(sa.parse_nonneg_fraction(Fraction(0, 1)), Fraction(0, 1))
        self.assertEqual(sa.parse_nonneg_fraction(Fraction(2, 3)), Fraction(2, 3))
        self._expect_err("ERR_NEGATIVE_TICK", sa.parse_nonneg_fraction, Fraction(-1, 3))
        self.assertEqual(sa.parse_nonneg_fraction("0/1"), Fraction(0, 1))
        self.assertEqual(sa.parse_nonneg_fraction("1/3"), Fraction(1, 3))
        self._expect_err("ERR_INVALID_FRACTION_STR", sa.parse_nonneg_fraction, "1/0")
        self._expect_err("ERR_INVALID_FRACTION_STR", sa.parse_nonneg_fraction, "1/3\n")
        self._expect_err("ERR_UNREDUCED_FRACTION", sa.parse_nonneg_fraction, "2/4")
        self._expect_err("ERR_INVALID_TICK_TYPE", sa.parse_nonneg_fraction, 0.5)
        self._expect_err("ERR_INVALID_TICK_TYPE", sa.parse_nonneg_fraction, True)

    def test_02_law1b_serendipity_mining_accept_and_all_refusals(self) -> None:
        base = _valid_law1b_spec()
        res = sa.certify_law1b_serendipity_mining(base)
        self.assertTrue(res["certified"])
        self.assertEqual(res["unmerged_share"], "1/5")
        self.assertEqual(res["executed_witness_count"], 1)
        self.assertEqual(res["cataloged_lead_count"], 1)

        # Positive edge cases: zero closed_unmerged OR zero open repos allowed when counts match
        only_open = _valid_law1b_spec()
        only_open["repos_scanned"][0]["closed_unmerged"] = 0
        only_open["repos_scanned"][0]["merged"] = 9
        only_open["mined_entries"] = [only_open["mined_entries"][0]]
        self.assertTrue(sa.certify_law1b_serendipity_mining(only_open)["certified"])

        only_closed = _valid_law1b_spec()
        only_closed["repos_scanned"][0]["open"] = 0
        only_closed["repos_scanned"][0]["merged"] = 9
        only_closed["mined_entries"] = [dict(only_closed["mined_entries"][1], evidence_standing="EXECUTED_EXACT_WITNESS")]
        self.assertTrue(sa.certify_law1b_serendipity_mining(only_closed)["certified"])

        # Top-level rejections
        self._expect_err("L1B_INVALID_SPEC", sa.certify_law1b_serendipity_mining, [])
        bad = _valid_law1b_spec()
        bad["extra"] = 1.5
        self._expect_err("L1B_FLOAT_FORBIDDEN", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["extra"] = 1
        self._expect_err("L1B_SPEC_KEYSET_MISMATCH", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["schema"] = "wrong"
        self._expect_err("L1B_INVALID_SCHEMA", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["external_writes"] = False
        self._expect_err("L1B_NONZERO_EXTERNAL_WRITES", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["external_writes"] = 1
        self._expect_err("L1B_NONZERO_EXTERNAL_WRITES", sa.certify_law1b_serendipity_mining, bad)

        # Repo-level rejections
        bad = _valid_law1b_spec()
        bad["repos_scanned"] = "not-a-list"
        self._expect_err("L1B_REPOS_EMPTY", sa.certify_law1b_serendipity_mining, bad)
        bad["repos_scanned"] = []
        self._expect_err("L1B_REPOS_EMPTY", sa.certify_law1b_serendipity_mining, bad)
        bad["repos_scanned"] = ["not-dict"]
        self._expect_err("L1B_REPO_SCHEMA", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["repos_scanned"][0]["extra"] = 1
        self._expect_err("L1B_REPO_SCHEMA", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["repos_scanned"][0]["repo"] = 42
        self._expect_err("L1B_INVALID_REPO_NAME", sa.certify_law1b_serendipity_mining, bad)
        bad["repos_scanned"][0]["repo"] = "noslash"
        self._expect_err("L1B_INVALID_REPO_NAME", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        dup_repo = copy.deepcopy(bad["repos_scanned"][0])
        dup_repo["repo"] = "foundation-0/MATH0"
        bad["repos_scanned"].append(dup_repo)
        self._expect_err("L1B_DUPLICATE_REPO", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["repos_scanned"][0]["prs_json_sha256"] = "0" * 64
        self._expect_err("L1B_INVALID_PRS_SHA256", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["repos_scanned"][0]["open"] = True
        self._expect_err("L1B_INVALID_REPO_COUNT", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["repos_scanned"][0]["open"] = -1
        self._expect_err("L1B_INVALID_REPO_COUNT", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["repos_scanned"][0].update({"fetched": 0, "open": 0, "closed_unmerged": 0, "merged": 0})
        self._expect_err("L1B_EMPTY_REPO_FETCH", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["repos_scanned"][0]["merged"] = 99
        self._expect_err("L1B_COUNT_CONSERVATION_FAILED", sa.certify_law1b_serendipity_mining, bad)

        # Entry-level rejections
        bad = _valid_law1b_spec()
        bad["mined_entries"] = "bad"
        self._expect_err("L1B_ENTRIES_EMPTY", sa.certify_law1b_serendipity_mining, bad)
        bad["mined_entries"] = []
        self._expect_err("L1B_ENTRIES_EMPTY", sa.certify_law1b_serendipity_mining, bad)
        bad["mined_entries"] = ["bad"]
        self._expect_err("L1B_ENTRY_SCHEMA", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["mined_entries"][0]["extra"] = 1
        self._expect_err("L1B_ENTRY_SCHEMA", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["mined_entries"][0]["repo"] = 123
        self._expect_err("L1B_ENTRY_UNKNOWN_REPO", sa.certify_law1b_serendipity_mining, bad)
        bad["mined_entries"][0]["repo"] = "Other/repo"
        self._expect_err("L1B_ENTRY_UNKNOWN_REPO", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["mined_entries"][0]["number"] = True
        self._expect_err("L1B_INVALID_PR_NUMBER", sa.certify_law1b_serendipity_mining, bad)
        bad["mined_entries"][0]["number"] = 0
        self._expect_err("L1B_INVALID_PR_NUMBER", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["mined_entries"][1]["number"] = 1
        bad["mined_entries"][1]["repo"] = "foundation-0/math0"
        self._expect_err("L1B_DUPLICATE_PR_ENTRY", sa.certify_law1b_serendipity_mining, bad)

        for field, bad_non_str, bad_val, code in (
            ("status", 1, "merged", "L1B_INVALID_STATUS"),
            ("mechanism_class", 1, "UNKNOWN_CLASS", "L1B_INVALID_MECHANISM_CLASS"),
            ("evidence_standing", 1, "GUESS", "L1B_INVALID_STANDING"),
            ("honest_novelty", 1, "N9", "L1B_INVALID_NOVELTY"),
        ):
            bad = _valid_law1b_spec()
            bad["mined_entries"][0][field] = bad_non_str
            self._expect_err(code, sa.certify_law1b_serendipity_mining, bad)
            bad["mined_entries"][0][field] = bad_val
            self._expect_err(code, sa.certify_law1b_serendipity_mining, bad)

        bad = _valid_law1b_spec()
        bad["mined_entries"][0]["head_sha"] = "a" * 40
        self._expect_err("L1B_INVALID_HEAD_SHA", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["mined_entries"][0]["snapshot_sha256"] = "b" * 64
        self._expect_err("L1B_INVALID_SNAPSHOT_SHA256", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["mined_entries"][1]["honest_novelty"] = "N1"
        self._expect_err("L1B_LEAD_CANNOT_CLAIM_ABOVE_N0", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["mined_entries"][0]["operator_summary"] = "bad\nline"
        self._expect_err("L1B_INVALID_OPERATOR_SUMMARY", sa.certify_law1b_serendipity_mining, bad)

        # Per-repo count caps
        bad = _valid_law1b_spec()
        bad["mined_entries"].append(dict(bad["mined_entries"][0], number=4))
        bad["mined_entries"].append(dict(bad["mined_entries"][0], number=5))
        self._expect_err("L1B_REPO_OPEN_COUNT_EXCEEDED", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["mined_entries"].append(dict(bad["mined_entries"][1], number=10))
        self._expect_err("L1B_REPO_CLOSED_UNMERGED_COUNT_EXCEEDED", sa.certify_law1b_serendipity_mining, bad)

        # Global blind-spot and executed-witness guards
        bad = _valid_law1b_spec()
        bad["mined_entries"] = [bad["mined_entries"][0]]
        self._expect_err("L1B_CLOSED_UNMERGED_BLIND_SPOT", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["mined_entries"] = [dict(bad["mined_entries"][1], evidence_standing="EXECUTED_EXACT_WITNESS")]
        self._expect_err("L1B_OPEN_PR_BLIND_SPOT", sa.certify_law1b_serendipity_mining, bad)
        bad = _valid_law1b_spec()
        bad["mined_entries"][0]["evidence_standing"] = "CATALOGED_LEAD"
        self._expect_err("L1B_ZERO_EXECUTED_WITNESSES", sa.certify_law1b_serendipity_mining, bad)

    def test_03_airlock_stripper_envelope_and_non_interference(self) -> None:
        # Leak scanner coverage (nested list, tuple, non-str key, whitespace/case leak key)
        leaks = sa._scan_airlock_leak_keys({"ok": [{1: "x"}, ("ok", {" Transcript ": "hi"})]})
        self.assertTrue(any(v.startswith("NON_STR_KEY:") for v in leaks))
        self.assertTrue(any(v.startswith("FORBIDDEN_LEAK_KEY:") for v in leaks))

        # Stripper checks + deep-copy isolation
        self._expect_err("INVALID_ZONE_A_SUBMISSION", sa.strip_zone_a_to_airlock_envelope, [])
        self._expect_err("INVALID_ZONE_A_SUBMISSION", sa.strip_zone_a_to_airlock_envelope, {"x": 1.5})
        for req in ("envelope_id", "claim_ledger", "pinned_inputs", "artifact_bundle"):
            sub = _valid_tech_submission()
            del sub[req]
            self._expect_err("MISSING_REQUIRED_AIRLOCK_SOURCE_FIELD", sa.strip_zone_a_to_airlock_envelope, sub)

        src = _valid_tech_submission()
        env = sa.strip_zone_a_to_airlock_envelope(src)
        src["pinned_inputs"]["seeds"].append(999)
        self.assertEqual(env["pinned_inputs"]["seeds"], [0, 7])
        self.assertTrue(sa.validate_airlock_envelope(env)["passed"])

        # Envelope validation negative controls
        self.assertEqual(sa.validate_airlock_envelope([])["violations"], ["INVALID_ENVELOPE_OR_FLOAT"])
        bad = copy.deepcopy(env)
        bad["pinned_inputs"]["seeds"] = [1.5]
        self.assertEqual(sa.validate_airlock_envelope(bad)["violations"], ["INVALID_ENVELOPE_OR_FLOAT"])

        def _check_env_viol(mut_fn, expected_prefix: str) -> None:
            e = copy.deepcopy(env)
            mut_fn(e)
            r = sa.validate_airlock_envelope(e)
            self.assertFalse(r["passed"])
            self.assertTrue(any(v.startswith(expected_prefix) for v in r["violations"]), f"{expected_prefix} not in {r['violations']}")

        _check_env_viol(lambda e: e.update({"extra": 1}), "ENVELOPE_KEYSET_MISMATCH")
        _check_env_viol(lambda e: e.update({"transcript": "hi"}), "FORBIDDEN_LEAK_KEY:")
        _check_env_viol(lambda e: e.update({"schema": "bad"}), "INVALID_ENVELOPE_SCHEMA")
        _check_env_viol(lambda e: e.update({"envelope_id": "-bad"}), "INVALID_ENVELOPE_ID")
        _check_env_viol(lambda e: e.update({"claim_ledger": "bad"}), "INVALID_CLAIM_LEDGER_SCHEMA")
        _check_env_viol(lambda e: e["claim_ledger"].update({"extra": 1}), "INVALID_CLAIM_LEDGER_SCHEMA")
        _check_env_viol(lambda e: e["claim_ledger"].update({"claim_id": "-bad"}), "INVALID_CLAIM_ID")
        _check_env_viol(lambda e: e["claim_ledger"].update({"finite_outcome_grammar": "bad"}), "INVALID_FINITE_OUTCOME_GRAMMAR")
        _check_env_viol(lambda e: e["claim_ledger"].update({"finite_outcome_grammar": {"ONLY": "supports"}}), "INVALID_FINITE_OUTCOME_GRAMMAR")
        _check_env_viol(lambda e: e["claim_ledger"].update({"finite_outcome_grammar": {"OK": "supports", "": "against"}}), "INVALID_FINITE_OUTCOME_GRAMMAR")
        _check_env_viol(lambda e: e["claim_ledger"].update({"finite_outcome_grammar": {"OK": "supports", "BAD\x07": "against"}}), "INVALID_FINITE_OUTCOME_GRAMMAR")
        _check_env_viol(lambda e: e["claim_ledger"].update({"finite_outcome_grammar": {"OK": "supports", " PAD ": "against"}}), "INVALID_FINITE_OUTCOME_GRAMMAR")
        _check_env_viol(lambda e: e["claim_ledger"].update({"finite_outcome_grammar": {"OK": "supports", "BAD": "maybe"}}), "INVALID_FINITE_OUTCOME_GRAMMAR")
        _check_env_viol(lambda e: e["claim_ledger"].update({"finite_outcome_grammar": {"BROKEN": "against", "HOLDS": "supports", "P\u0410SS": "supports"}}), "INVALID_FINITE_OUTCOME_GRAMMAR")
        _check_env_viol(lambda e: e["claim_ledger"].update({"falsifier_predicate": "   "}), "EMPTY_FALSIFIER_PREDICATE")
        _check_env_viol(lambda e: e["claim_ledger"].update({"falsifier_predicate": "a\nb"}), "INVALID_FALSIFIER_PREDICATE_CONTENT")
        _check_env_viol(lambda e: e["claim_ledger"].update({"falsifier_predicate": "x" * 4097}), "INVALID_FALSIFIER_PREDICATE_CONTENT")
        _check_env_viol(lambda e: e["claim_ledger"].update({"novelty_default": "N1"}), "NOVELTY_DEFAULT_MUST_BE_N0")
        _check_env_viol(lambda e: e["claim_ledger"].update({"linguistic_ceiling": 5}), "INVALID_LINGUISTIC_CEILING")
        _check_env_viol(lambda e: e["claim_ledger"].update({"linguistic_ceiling": "E9"}), "INVALID_LINGUISTIC_CEILING")

        _check_env_viol(lambda e: e.update({"pinned_inputs": "bad"}), "INVALID_PINNED_INPUTS_SCHEMA")
        _check_env_viol(lambda e: e["pinned_inputs"].update({"extra": 1}), "INVALID_PINNED_INPUTS_SCHEMA")
        _check_env_viol(lambda e: e["pinned_inputs"].update({"files": "bad"}), "PINNED_FILES_EMPTY")
        _check_env_viol(lambda e: e["pinned_inputs"].update({"files": []}), "PINNED_FILES_EMPTY")
        _check_env_viol(lambda e: e["pinned_inputs"].update({"files": ["bad"]}), "PINNED_FILE_0_SCHEMA")
        _check_env_viol(lambda e: e["pinned_inputs"]["files"][0].update({"extra": 1}), "PINNED_FILE_0_SCHEMA")
        _check_env_viol(lambda e: e["pinned_inputs"]["files"][0].update({"id": "-bad"}), "PINNED_FILE_0_BAD_OR_DUP_ID")
        _check_env_viol(lambda e: e["pinned_inputs"]["files"].append(copy.deepcopy(e["pinned_inputs"]["files"][0])), "PINNED_FILE_1_BAD_OR_DUP_ID")
        _check_env_viol(lambda e: e["pinned_inputs"]["files"][0].update({"sha256": "0" * 64}), "PINNED_FILE_0_BAD_SHA256")
        _check_env_viol(lambda e: e["pinned_inputs"]["files"][0].update({"bytes": True}), "PINNED_FILE_0_BAD_BYTES")
        _check_env_viol(lambda e: e["pinned_inputs"]["files"][0].update({"bytes": 0}), "PINNED_FILE_0_BAD_BYTES")
        _check_env_viol(lambda e: e["pinned_inputs"].update({"seeds": "bad"}), "PINNED_SEEDS_INVALID")
        _check_env_viol(lambda e: e["pinned_inputs"].update({"seeds": []}), "PINNED_SEEDS_INVALID")
        _check_env_viol(lambda e: e["pinned_inputs"].update({"seeds": [True]}), "PINNED_SEEDS_INVALID")
        _check_env_viol(lambda e: e["pinned_inputs"].update({"seeds": [-1]}), "PINNED_SEEDS_INVALID")
        _check_env_viol(lambda e: e["pinned_inputs"].update({"seeds": [7, 7]}), "PINNED_SEEDS_INVALID")

        _check_env_viol(lambda e: e.update({"artifact_bundle": "bad"}), "ARTIFACT_BUNDLE_EMPTY")
        _check_env_viol(lambda e: e.update({"artifact_bundle": []}), "ARTIFACT_BUNDLE_EMPTY")
        _check_env_viol(lambda e: e.update({"artifact_bundle": ["bad"]}), "ARTIFACT_0_SCHEMA")
        _check_env_viol(lambda e: e["artifact_bundle"][0].update({"extra": 1}), "ARTIFACT_0_SCHEMA")
        _check_env_viol(lambda e: e["artifact_bundle"][0].update({"relpath": "../bad.py"}), "ARTIFACT_0_UNSAFE_OR_DUP_RELPATH")
        _check_env_viol(lambda e: e["artifact_bundle"].append(copy.deepcopy(e["artifact_bundle"][0])), "ARTIFACT_3_UNSAFE_OR_DUP_RELPATH")
        _check_env_viol(lambda e: e["artifact_bundle"][0].update({"sha256": "1" * 64}), "ARTIFACT_0_BAD_SHA256")
        _check_env_viol(lambda e: e["artifact_bundle"][0].update({"role": 5}), "ARTIFACT_0_BAD_ROLE")
        _check_env_viol(lambda e: e["artifact_bundle"][0].update({"role": "doc"}), "ARTIFACT_0_BAD_ROLE")
        _check_env_viol(lambda e: e.update({"artifact_bundle": [e["artifact_bundle"][1]]}), "ARTIFACT_BUNDLE_REQUIRES_CODE_AND_TEST")
        _check_env_viol(lambda e: e.update({"artifact_bundle": [e["artifact_bundle"][0]]}), "ARTIFACT_BUNDLE_REQUIRES_CODE_AND_TEST")

        # Observational non-interference positive + negative controls
        r1 = dict(_valid_tech_submission(), transcript="praise", authors=["a"], models=["m1"], agreement_count=2)
        r2 = dict(_valid_tech_submission(), transcript="skeptic", authors=["b"], models=["m2"], agreement_count=0)
        ni = sa.verify_observational_non_interference(r1, r2)
        self.assertTrue(ni["passed"])
        self.assertIsNotNone(ni["envelope_sha256"])

        self._expect_err("INVALID_NON_INTERFERENCE_INPUTS", sa.verify_observational_non_interference, [], r2)
        self._expect_err("INVALID_NON_INTERFERENCE_INPUTS", sa.verify_observational_non_interference, r1, [])
        self._expect_err("FLOAT_FORBIDDEN_IN_NON_INTERFERENCE_INPUTS", sa.verify_observational_non_interference, dict(r1, x=1.2), r2)
        self._expect_err("FLOAT_FORBIDDEN_IN_NON_INTERFERENCE_INPUTS", sa.verify_observational_non_interference, r1, dict(r2, x=1.2))
        r1_miss = copy.deepcopy(r1)
        del r1_miss["transcript"]
        self._expect_err("MISSING_SOCIAL_METADATA", sa.verify_observational_non_interference, r1_miss, r2)
        r2_miss = copy.deepcopy(r2)
        del r2_miss["models"]
        self._expect_err("MISSING_SOCIAL_METADATA", sa.verify_observational_non_interference, r1, r2_miss)
        self._expect_err("SOCIAL_METADATA_MUST_DIFFER", sa.verify_observational_non_interference, r1, dict(r2, transcript="praise"))

        # BoolOp clauses on passed = v1["passed"] and b1 == b2
        r_bad1 = copy.deepcopy(r1)
        r_bad1["envelope_id"] = "-bad"
        r_bad2 = copy.deepcopy(r2)
        r_bad2["envelope_id"] = "-bad"
        self.assertFalse(sa.verify_observational_non_interference(r_bad1, r_bad2)["passed"])
        r_diff = copy.deepcopy(r2)
        r_diff["envelope_id"] = "env-other"
        self.assertFalse(sa.verify_observational_non_interference(r1, r_diff)["passed"])

    def test_04_certify_two_zone_airlock_all_guards(self) -> None:
        base = _valid_two_zone_spec()
        self.assertTrue(sa.certify_two_zone_airlock(base)["passed"])

        # Valid adverse FALSIFIED packet (E0_LEAD + REFUTED + non-empty counterexample)
        adv = _valid_two_zone_spec()
        adv["verdict_packet"].update({
            "part_e_verdict": "FALSIFIED",
            "part_i_grade": "E0_LEAD",
            "outcome_matched": "REFUTED",
            "r5_killed": 9,
            "counterexample": "minimal witness x=0",
        })
        self.assertTrue(sa.certify_two_zone_airlock(adv)["passed"])

        # Valid EXACT_ONLY_NA adverse packet & valid PARTIAL_FRAGILE packet
        adv_na = copy.deepcopy(adv)
        adv_na["verdict_packet"]["part_i_grade"] = "EXACT_ONLY_NA"
        self.assertTrue(sa.certify_two_zone_airlock(adv_na)["passed"])
        pf_ok = _valid_two_zone_spec()
        pf_ok["verdict_packet"].update({
            "part_e_verdict": "PARTIAL_FRAGILE",
            "part_i_grade": "E0_LEAD",
            "outcome_matched": "INCONCLUSIVE",
            "r5_killed": 9,
            "counterexample": "fragile boundary seed=7",
        })
        self.assertTrue(sa.certify_two_zone_airlock(pf_ok)["passed"])

        self.assertEqual(sa.certify_two_zone_airlock([])["violations"], ["INVALID_TWO_ZONE_SPEC_OR_FLOAT"])
        bad_float = _valid_two_zone_spec()
        bad_float["extra"] = 0.5
        self.assertEqual(sa.certify_two_zone_airlock(bad_float)["violations"], ["INVALID_TWO_ZONE_SPEC_OR_FLOAT"])
        bad_keys = _valid_two_zone_spec()
        bad_keys["extra"] = 1
        self.assertEqual(sa.certify_two_zone_airlock(bad_keys)["violations"], ["UNEXPECTED_TWO_ZONE_KEYS"])

        def _check_tz(mut_fn, expected_code: str) -> None:
            sp = _valid_two_zone_spec()
            mut_fn(sp)
            r = sa.certify_two_zone_airlock(sp)
            self.assertFalse(r["passed"])
            self.assertIn(expected_code, r["violations"])

        # Zone A checks
        _check_tz(lambda s: s.update({"zone_a": "bad"}), "ZONE_A_SCHEMA_MISMATCH")
        _check_tz(lambda s: s["zone_a"].update({"extra": 1}), "ZONE_A_SCHEMA_MISMATCH")
        _check_tz(lambda s: s["zone_a"].update({"mode": "conductor"}), "ZONE_A_MUST_BE_SOCRATIC")
        _check_tz(lambda s: s["zone_a"].update({"conductor": "boss"}), "ZONE_A_SOCRATIC_MUST_HAVE_NO_CONDUCTOR")
        _check_tz(lambda s: s["zone_a"].update({"participants": "bad"}), "ZONE_A_REQUIRES_AT_LEAST_2_UNIQUE_PARTICIPANTS")
        _check_tz(lambda s: s["zone_a"].update({"participants": ["alice"]}), "ZONE_A_REQUIRES_AT_LEAST_2_UNIQUE_PARTICIPANTS")
        _check_tz(lambda s: s["zone_a"].update({"participants": ["alice", "-bad"]}), "ZONE_A_REQUIRES_AT_LEAST_2_UNIQUE_PARTICIPANTS")
        _check_tz(lambda s: s["zone_a"].update({"participants": ["alice", "ALICE"]}), "ZONE_A_REQUIRES_AT_LEAST_2_UNIQUE_PARTICIPANTS")
        _check_tz(lambda s: s["zone_a"].update({"round_robin_enforced": True}), "ZONE_A_S03_ROUND_ROBIN_FORBIDDEN")
        _check_tz(lambda s: s["zone_a"].update({"silent_turns_allowed": False}), "ZONE_A_G08_SILENCE_MUST_BE_VALID")
        _check_tz(lambda s: s["zone_a"].update({"silent_turns_observed": True}), "ZONE_A_INVALID_SILENT_TURNS")
        _check_tz(lambda s: s["zone_a"].update({"silent_turns_observed": -1}), "ZONE_A_INVALID_SILENT_TURNS")
        _check_tz(lambda s: s["zone_a"].update({"distinct_hypotheses_count": True}), "ZONE_A_HOMOGENIZED_SINGLE_HYPOTHESIS")
        _check_tz(lambda s: s["zone_a"].update({"distinct_hypotheses_count": "2"}), "ZONE_A_HOMOGENIZED_SINGLE_HYPOTHESIS")
        _check_tz(lambda s: s["zone_a"].update({"distinct_hypotheses_count": 1}), "ZONE_A_HOMOGENIZED_SINGLE_HYPOTHESIS")
        _check_tz(lambda s: s["zone_a"].update({"output_tag": "VERIFIED"}), "ZONE_A_MUST_TAG_OUTPUT_UNVERIFIED_HYPOTHESIS")
        _check_tz(lambda s: s["zone_a"].update({"agreement_counted_as_evidence": True}), "ZONE_A_AGREEMENT_CANNOT_BE_EVIDENCE")

        # Airlock error propagation + non-dict envelope/claim_ledger handling
        _check_tz(lambda s: s.update({"airlock_envelope": "bad"}), "AIRLOCK:INVALID_ENVELOPE_OR_FLOAT")
        _check_tz(lambda s: s["airlock_envelope"].update({"claim_ledger": "bad"}), "AIRLOCK:INVALID_CLAIM_LEDGER_SCHEMA")

        # Zone B checks
        _check_tz(lambda s: s.update({"zone_b": "bad"}), "ZONE_B_SCHEMA_MISMATCH")
        _check_tz(lambda s: s["zone_b"].update({"extra": 1}), "ZONE_B_SCHEMA_MISMATCH")
        _check_tz(lambda s: s["zone_b"].update({"channel_mode": "shared"}), "ZONE_B_MUST_USE_PRIVATE_C02_CHANNEL")
        _check_tz(lambda s: s["zone_b"].update({"verifier_seat": "-bad"}), "ZONE_B_INVALID_VERIFIER_SEAT")
        _check_tz(lambda s: s["zone_b"].update({"verifier_seat": "BOB"}), "ZONE_B_R3_VERIFIER_IN_ZONE_A_PARTICIPANTS")
        _check_tz(lambda s: s["zone_b"].update({"read_scope": ["env-r5-001", "zone_a_board"]}), "ZONE_B_M05_READ_SCOPE_EXCEEDS_STRIPPED_ENVELOPE")
        _check_tz(lambda s: s["zone_b"].update({"blocked_channels": "bad"}), "ZONE_B_INVALID_BLOCKED_CHANNELS")
        _check_tz(lambda s: s["zone_b"].update({"blocked_channels": ["bus", ""]}), "ZONE_B_INVALID_BLOCKED_CHANNELS")
        _check_tz(lambda s: s["zone_b"].update({"blocked_channels": ["bus"]}), "ZONE_B_M05_MISSING_REQUIRED_BLOCKED_CHANNELS")
        _check_tz(lambda s: s["zone_b"].update({"can_read_zone_a_board": True}), "ZONE_B_M05_BOARD_VISIBILITY_LEAK")
        _check_tz(lambda s: s["zone_b"].update({"can_approve_own_changes": True}), "ZONE_B_C05_SELF_APPROVAL_FORBIDDEN")
        _check_tz(lambda s: s["zone_b"].update({"write_scopes": ["src/"]}), "ZONE_B_I15_VERIFIER_MUST_BE_READ_ONLY")

        # Verdict packet checks
        _check_tz(lambda s: s.update({"verdict_packet": "bad"}), "VERDICT_PACKET_SCHEMA_MISMATCH")
        _check_tz(lambda s: s["verdict_packet"].update({"extra": 1}), "VERDICT_PACKET_SCHEMA_MISMATCH")
        _check_tz(lambda s: s["verdict_packet"].update({"schema": "bad"}), "VERDICT_INVALID_SCHEMA")
        _check_tz(lambda s: s["verdict_packet"].update({"envelope_id": "other"}), "VERDICT_ENVELOPE_ID_MISMATCH")
        _check_tz(lambda s: s["verdict_packet"].update({"envelope_sha256": SHA_3}), "VERDICT_ENVELOPE_SHA256_MISMATCH")
        _check_tz(lambda s: s["verdict_packet"].update({"verifier_seat": "other"}), "VERDICT_SEAT_MISMATCH")
        _check_tz(lambda s: s["verdict_packet"].update({"part_e_verdict": 1}), "VERDICT_INVALID_PART_E")
        _check_tz(lambda s: s["verdict_packet"].update({"part_e_verdict": "OK"}), "VERDICT_INVALID_PART_E")
        _check_tz(lambda s: s["verdict_packet"].update({"part_i_grade": 1}), "VERDICT_INVALID_PART_I_GRADE")
        _check_tz(lambda s: s["verdict_packet"].update({"part_i_grade": "E9"}), "VERDICT_INVALID_PART_I_GRADE")
        _check_tz(lambda s: s["verdict_packet"].update({"outcome_matched": "UNKNOWN"}), "VERDICT_OUTCOME_NOT_IN_DECLARED_GRAMMAR")
        _check_tz(lambda s: s["verdict_packet"].update({"outcome_matched": "REFUTED"}), "VERDICT_OUTCOME_CONTRADICTS_PART_E")
        _check_tz(lambda s: s["verdict_packet"].update({"part_e_verdict": "PARTIAL_FRAGILE", "part_i_grade": "E0_LEAD", "outcome_matched": "SUPPORTED", "counterexample": "cex"}), "VERDICT_OUTCOME_CONTRADICTS_PART_E")
        _check_tz(lambda s: s["verdict_packet"].update({"part_e_verdict": "FALSIFIED", "part_i_grade": "E0_LEAD", "outcome_matched": "SUPPORTED", "counterexample": "cex"}), "VERDICT_OUTCOME_CONTRADICTS_PART_E")
        _check_tz(lambda s: s["verdict_packet"].update({"part_e_verdict": "NOT_SHOWN", "part_i_grade": "E0_LEAD", "outcome_matched": "SUPPORTED", "counterexample": "cex"}), "VERDICT_OUTCOME_CONTRADICTS_PART_E")
        _check_tz(lambda s: s["verdict_packet"].update({"part_i_grade": "E3_REIMPLEMENTED"}), "VERDICT_PART_I_EXCEEDS_LINGUISTIC_CEILING")
        _check_tz(lambda s: s["verdict_packet"].update({"part_e_verdict": "PARTIAL_FRAGILE", "part_i_grade": "E1_PLANNED", "outcome_matched": "INCONCLUSIVE", "counterexample": "cex"}), "VERDICT_ADVERSE_CANNOT_CLAIM_ELEVATED_PART_I_GRADE")
        _check_tz(lambda s: s["verdict_packet"].update({"part_e_verdict": "FALSIFIED", "part_i_grade": "E1_PLANNED", "outcome_matched": "REFUTED", "counterexample": "cex"}), "VERDICT_ADVERSE_CANNOT_CLAIM_ELEVATED_PART_I_GRADE")
        _check_tz(lambda s: s["verdict_packet"].update({"part_e_verdict": "NOT_SHOWN", "part_i_grade": "E1_PLANNED", "outcome_matched": "INCONCLUSIVE", "counterexample": "cex"}), "VERDICT_ADVERSE_CANNOT_CLAIM_ELEVATED_PART_I_GRADE")
        _check_tz(lambda s: s["verdict_packet"].update({"r5_killed": True}), "VERDICT_INVALID_R5_COUNTS")
        _check_tz(lambda s: s["verdict_packet"].update({"r5_total": True}), "VERDICT_INVALID_R5_COUNTS")
        _check_tz(lambda s: s["verdict_packet"].update({"r5_total": 0, "r5_killed": 0}), "VERDICT_INVALID_R5_COUNTS")
        _check_tz(lambda s: s["verdict_packet"].update({"r5_killed": -1}), "VERDICT_INVALID_R5_COUNTS")
        _check_tz(lambda s: s["verdict_packet"].update({"r5_killed": 11}), "VERDICT_INVALID_R5_COUNTS")
        _check_tz(lambda s: s["verdict_packet"].update({"r5_killed": 9}), "VERDICT_VERIFIED_WITH_R5_SURVIVORS")
        _check_tz(lambda s: s["verdict_packet"].update({"counterexample": "unexpected"}), "VERDICT_VERIFIED_MUST_HAVE_NULL_COUNTEREXAMPLE")
        _check_tz(lambda s: s["verdict_packet"].update({"part_e_verdict": "FALSIFIED", "part_i_grade": "E0_LEAD", "outcome_matched": "REFUTED", "counterexample": None}), "VERDICT_ADVERSE_REQUIRES_MINIMAL_COUNTEREXAMPLE")
        _check_tz(lambda s: s["verdict_packet"].update({"part_e_verdict": "FALSIFIED", "part_i_grade": "E0_LEAD", "outcome_matched": "REFUTED", "counterexample": "\x00bad"}), "VERDICT_ADVERSE_REQUIRES_MINIMAL_COUNTEREXAMPLE")
        _check_tz(lambda s: s["verdict_packet"].update({"part_e_verdict": "PARTIAL_FRAGILE", "part_i_grade": "E0_LEAD", "outcome_matched": "INCONCLUSIVE", "counterexample": "caf\u00e9"}), "VERDICT_ADVERSE_REQUIRES_MINIMAL_COUNTEREXAMPLE")

    def test_05_erlang_otp_supervision_and_exo1200_bridge(self) -> None:
        # 1. Exact 3x3 matrix + rejections
        restarts = 0
        for p in ("permanent", "transient", "temporary"):
            for r in ("normal", "shutdown", "abnormal"):
                d = sa.otp_should_restart(p, r)
                if d["should_restart"]:
                    restarts += 1
        self.assertEqual(restarts, 4)
        self._expect_err("ERR_INVALID_POLICY", sa.otp_should_restart, 1, "normal")
        self._expect_err("ERR_INVALID_POLICY", sa.otp_should_restart, "always", "normal")
        self._expect_err("ERR_INVALID_EXIT_REASON", sa.otp_should_restart, "permanent", 1)
        self._expect_err("ERR_INVALID_EXIT_REASON", sa.otp_should_restart, "permanent", "kill")

        # 2. All 3 strategies + non-resurrection of temporary & dead transient + snapshot non-churn
        ch = _valid_otp_children()
        rfo = sa.apply_otp_strategy_crash("rest_for_one", ch, "author", "abnormal", SHA_2)
        self.assertEqual(rfo["terminated_order"], ["verifier", "temp_worker", "airlock"])
        self.assertEqual(rfo["restarted_order"], ["author", "airlock", "verifier"])
        self.assertEqual(rfo["children_after"][0]["generation"], 1)  # planner untouched
        self.assertFalse(rfo["children_after"][3]["alive"])  # temp_worker never restarted
        self.assertFalse(rfo["children_after"][4]["alive"])  # dead_transient never resurrected
        nc_ok = sa.verify_snapshot_non_churn(rfo["children_after"], "author", ["airlock", "temp_worker", "verifier"])
        self.assertTrue(nc_ok["passed"])

        ofa = sa.apply_otp_strategy_crash("one_for_all", ch, "author", "abnormal", None)
        self.assertEqual(ofa["terminated_order"], ["verifier", "temp_worker", "airlock", "planner"])
        self.assertEqual(ofa["restarted_order"], ["planner", "author", "airlock", "verifier"])

        ofo = sa.apply_otp_strategy_crash("one_for_one", ch, "author", "abnormal", SHA_2)
        self.assertEqual(ofo["terminated_order"], [])
        self.assertEqual(ofo["restarted_order"], ["author"])
        nc_bad = sa.verify_snapshot_non_churn(ofo["children_after"], "author", ["airlock", "verifier"])
        self.assertFalse(nc_bad["passed"])
        self.assertEqual(nc_bad["error_code"], "ERR_SNAPSHOT_CHURN")
        # downstream set is ALWAYS derived from child order now: [airlock, temp_worker, dead_transient, verifier]
        self.assertEqual(nc_bad["downstream_ids"], ["airlock", "temp_worker", "dead_transient", "verifier"])
        self.assertEqual(nc_bad["stale_downstream_count"], 3)

        # Clean transient exit drops child without restarting
        drop = sa.apply_otp_strategy_crash("rest_for_one", ch, "author", "normal", SHA_2)
        self.assertFalse(drop["restarted"])
        self.assertEqual(drop["restarted_order"], [])

        # Strategy validation refusals
        self._expect_err("ERR_INVALID_STRATEGY", sa.apply_otp_strategy_crash, 1, ch, "author", "abnormal")
        self._expect_err("ERR_INVALID_STRATEGY", sa.apply_otp_strategy_crash, "bad", ch, "author", "abnormal")
        self._expect_err("ERR_INVALID_CHILDREN", sa.apply_otp_strategy_crash, "rest_for_one", "bad", "author", "abnormal")
        self._expect_err("ERR_INVALID_CHILDREN", sa.apply_otp_strategy_crash, "rest_for_one", [], "author", "abnormal")
        self._expect_err("ERR_INVALID_SHA256", sa.apply_otp_strategy_crash, "rest_for_one", ch, "author", "abnormal", "0" * 64)
        self._expect_err("ERR_SCHEMA_KEYS", sa.apply_otp_strategy_crash, "rest_for_one", ["bad"], "author", "abnormal")
        c_bad = _valid_otp_children()
        c_bad[0]["extra"] = 1
        self._expect_err("ERR_SCHEMA_KEYS", sa.apply_otp_strategy_crash, "rest_for_one", c_bad, "author", "abnormal")
        c_bad = _valid_otp_children()
        c_bad[0]["id"] = "   "
        self._expect_err("ERR_INVALID_CHILD_ID", sa.apply_otp_strategy_crash, "rest_for_one", c_bad, "author", "abnormal")
        c_bad[0]["id"] = "  author\x00 "
        self._expect_err("ERR_INVALID_CHILD_ID", sa.apply_otp_strategy_crash, "rest_for_one", c_bad, "author", "abnormal")
        c_bad[0]["id"] = "-bad"
        self._expect_err("ERR_INVALID_CHILD_ID", sa.apply_otp_strategy_crash, "rest_for_one", c_bad, "author", "abnormal")
        c_bad = _valid_otp_children()
        c_bad[1]["id"] = "planner"
        self._expect_err("ERR_INVALID_CHILD_ID", sa.apply_otp_strategy_crash, "rest_for_one", c_bad, "planner", "abnormal")
        c_bad = _valid_otp_children()
        c_bad[0]["policy"] = 1
        self._expect_err("ERR_INVALID_POLICY", sa.apply_otp_strategy_crash, "rest_for_one", c_bad, "author", "abnormal")
        c_bad[0]["policy"] = "bad"
        self._expect_err("ERR_INVALID_POLICY", sa.apply_otp_strategy_crash, "rest_for_one", c_bad, "author", "abnormal")
        c_bad = _valid_otp_children()
        c_bad[0]["generation"] = True
        self._expect_err("ERR_SCHEMA_INT", sa.apply_otp_strategy_crash, "rest_for_one", c_bad, "author", "abnormal")
        c_bad[0]["generation"] = 0
        self._expect_err("ERR_SCHEMA_INT", sa.apply_otp_strategy_crash, "rest_for_one", c_bad, "author", "abnormal")
        c_bad = _valid_otp_children()
        c_bad[0]["snapshot_sha256"] = "0" * 64
        self._expect_err("ERR_INVALID_SHA256", sa.apply_otp_strategy_crash, "rest_for_one", c_bad, "author", "abnormal")
        c_bad = _valid_otp_children()
        c_bad[0]["alive"] = 1
        self._expect_err("ERR_INVALID_ALIVE", sa.apply_otp_strategy_crash, "rest_for_one", c_bad, "author", "abnormal")
        c_bad[0]["alive"] = False
        self._expect_err("ERR_DEAD_PERMANENT_CHILD", sa.apply_otp_strategy_crash, "rest_for_one", c_bad, "author", "abnormal")
        self._expect_err("ERR_UNKNOWN_CHILD", sa.apply_otp_strategy_crash, "rest_for_one", ch, 1, "abnormal")
        self._expect_err("ERR_UNKNOWN_CHILD", sa.apply_otp_strategy_crash, "rest_for_one", ch, "missing", "abnormal")
        self._expect_err("ERR_CHILD_ALREADY_DEAD", sa.apply_otp_strategy_crash, "rest_for_one", ch, "dead_transient", "abnormal")

        # Snapshot non-churn input refusals (strict schema, anti-vacuous, alive author, unique downstream)
        self._expect_err("ERR_INVALID_CHILDREN", sa.verify_snapshot_non_churn, 123, "author", ["airlock"])
        self._expect_err("ERR_INVALID_CHILDREN", sa.verify_snapshot_non_churn, [], "author", ["airlock"])
        self._expect_err("ERR_SCHEMA_KEYS", sa.verify_snapshot_non_churn, [123], "author", ["airlock"])
        self._expect_err("ERR_SCHEMA_KEYS", sa.verify_snapshot_non_churn, [{}], "author", ["airlock"])
        c_dup = _valid_otp_children()
        c_dup.append(copy.deepcopy(c_dup[0]))
        self._expect_err("ERR_INVALID_CHILD_ID", sa.verify_snapshot_non_churn, c_dup, "author", ["airlock"])
        c_zero = _valid_otp_children()
        c_zero[2]["snapshot_sha256"] = "0" * 64
        self._expect_err("ERR_INVALID_SHA256", sa.verify_snapshot_non_churn, c_zero, "author", ["airlock"])
        c_str_alive = _valid_otp_children()
        c_str_alive[2]["alive"] = "no"
        self._expect_err("ERR_INVALID_ALIVE", sa.verify_snapshot_non_churn, c_str_alive, "author", ["airlock"])
        c_dead_perm = _valid_otp_children()
        c_dead_perm[0]["alive"] = False
        self._expect_err("ERR_DEAD_PERMANENT_CHILD", sa.verify_snapshot_non_churn, c_dead_perm, "author", ["airlock"])
        # non-list/empty downstream errors are only reachable when the author is NOT
        # among the children (otherwise the set is derived from child order and the
        # caller's list is never trusted)
        self._expect_err("ERR_INVALID_DOWNSTREAM", sa.verify_snapshot_non_churn, ch, "missing2", "bad")
        solo = [{"id": "solo", "policy": "permanent", "generation": 1, "snapshot_sha256": SHA_1, "alive": True}]
        self._expect_err("ERR_INVALID_DOWNSTREAM", sa.verify_snapshot_non_churn, solo, "solo", ["x"])
        self._expect_err("ERR_UNKNOWN_AUTHOR", sa.verify_snapshot_non_churn, ch, 1, ["airlock"])
        self._expect_err("ERR_UNKNOWN_AUTHOR", sa.verify_snapshot_non_churn, ch, "missing", ["airlock"])
        self._expect_err("ERR_AUTHOR_NOT_ALIVE", sa.verify_snapshot_non_churn, ch, "dead_transient", ["airlock"])
        # with a present author the downstream set is ALWAYS derived from child order;
        # a bogus caller list is ignored entirely (never trusted)
        nc_ign = sa.verify_snapshot_non_churn(ch, "author", [1])
        self.assertTrue(nc_ign["passed"])
        self.assertEqual(nc_ign["downstream_ids"], ["airlock", "temp_worker", "dead_transient", "verifier"])
        # with an ABSENT author the caller list is used and fully validated
        self._expect_err("ERR_UNKNOWN_DOWNSTREAM", sa.verify_snapshot_non_churn, ch, "missing2", [1])
        self._expect_err("ERR_UNKNOWN_DOWNSTREAM", sa.verify_snapshot_non_churn, ch, "missing2", ["missing"])
        self._expect_err("ERR_INVALID_DOWNSTREAM", sa.verify_snapshot_non_churn, ch, "missing2", ["airlock", "airlock"])

        # 3. Pure-Z/Q sliding-window restart intensity + inclusive boundary + trailing event refusal
        t_zero = sa.certify_restart_intensity_trace(0, 5, [0])
        self.assertTrue(t_zero["escalated"])
        self.assertEqual(t_zero["escalated_at"], "0/1")
        t_eq = sa.certify_restart_intensity_trace(2, 5, [0, 0])
        self.assertFalse(t_eq["escalated"])
        t_int = sa.certify_restart_intensity_trace(2, 5, [0, 5, 6, 10])
        self.assertTrue(t_int["escalated"])
        self.assertEqual(t_int["escalated_at"], "10/1")
        self.assertEqual(t_int["steps"][1]["active_count"], 2)  # exact inclusive boundary 5-0 <= 5
        self.assertEqual(t_int["steps"][2]["evicted_count"], 1)  # 6-0 > 5 evicted
        t_ok = sa.certify_restart_intensity_trace(2, "1/3", ["0/1", "1/3"])
        self.assertFalse(t_ok["escalated"])
        self._expect_err("ERR_INVALID_MAX_RESTARTS", sa.certify_restart_intensity_trace, True, 5, [0])
        self._expect_err("ERR_INVALID_MAX_RESTARTS", sa.certify_restart_intensity_trace, -1, 5, [0])
        self._expect_err("ERR_ZERO_WINDOW", sa.certify_restart_intensity_trace, 2, 0, [0])
        self._expect_err("ERR_INVALID_CRASH_TICKS", sa.certify_restart_intensity_trace, 2, 5, "bad")
        self._expect_err("ERR_INVALID_CRASH_TICKS", sa.certify_restart_intensity_trace, 2, 5, [])
        self._expect_err("ERR_NON_MONOTONIC_TICK", sa.certify_restart_intensity_trace, 2, 5, [5, 4])
        self._expect_err("ERR_EVENT_AFTER_ESCALATION", sa.certify_restart_intensity_trace, 1, 5, [0, 1, 2])

        # 4. Monitor vs Link fault isolation
        self.assertTrue(sa.certify_monitor_vs_link_isolation("monitor", "abnormal")["isolated"])
        self.assertTrue(sa.certify_monitor_vs_link_isolation("monitor", "kill")["isolated"])
        self.assertTrue(sa.certify_monitor_vs_link_isolation("link_untrapped", "normal")["isolated"])
        l_abn = sa.certify_monitor_vs_link_isolation("link_untrapped", "abnormal")
        self.assertFalse(l_abn["isolated"])
        self.assertEqual(l_abn["collateral_kills"], ["coordinator", "verifier_2"])
        l_trap_abn = sa.certify_monitor_vs_link_isolation("link_trap_exit", "abnormal")
        self.assertTrue(l_trap_abn["isolated"])
        self.assertEqual(len(l_trap_abn["coordinator_inbox"]), 1)
        l_trap_kill = sa.certify_monitor_vs_link_isolation("link_trap_exit", "kill")
        self.assertFalse(l_trap_kill["isolated"])
        self.assertEqual(l_trap_kill["collateral_kills"], ["coordinator", "verifier_2"])
        self._expect_err("ERR_INVALID_TOPOLOGY", sa.certify_monitor_vs_link_isolation, 1, "kill")
        self._expect_err("ERR_INVALID_TOPOLOGY", sa.certify_monitor_vs_link_isolation, "bad", "kill")
        self._expect_err("ERR_INVALID_EXIT_REASON", sa.certify_monitor_vs_link_isolation, "monitor", 1)
        self._expect_err("ERR_INVALID_EXIT_REASON", sa.certify_monitor_vs_link_isolation, "monitor", "bad")

        # 5. exo#1200 x OTP hybrid supervision composition (all branches + input checks)
        kw = dict(
            task_state="failed", failure_class="transient", effect_class="not_dispatched",
            attempt_number=1, max_retries=2, stop_requested=False,
            otp_policy="transient", exit_reason="abnormal",
        )
        self.assertEqual(sa.decide_hybrid_supervision(**kw)["action"], "retry")
        self.assertEqual(sa.decide_hybrid_supervision(**dict(kw, attempt_number=2, max_retries=2))["action"], "retry")
        self.assertEqual(sa.decide_hybrid_supervision(**dict(kw, max_retries=10))["action"], "retry")
        self.assertEqual(sa.decide_hybrid_supervision(**dict(kw, max_retries=0))["reason"], "retry_budget_exhausted")
        self.assertEqual(sa.decide_hybrid_supervision(**dict(kw, stop_requested=True))["reason"], "cancelled")
        self.assertEqual(sa.decide_hybrid_supervision(**dict(kw, task_state="stopped"))["reason"], "cancelled")
        self.assertEqual(sa.decide_hybrid_supervision(**dict(kw, task_state="cancelled"))["reason"], "cancelled")
        self.assertEqual(sa.decide_hybrid_supervision(**dict(kw, failure_class="denied"))["reason"], "denied")
        self.assertEqual(sa.decide_hybrid_supervision(**dict(kw, task_state="completed"))["reason"], "completed")
        self.assertEqual(sa.decide_hybrid_supervision(**dict(kw, task_state="running"))["reason"], "not_settled_failure")
        self.assertEqual(sa.decide_hybrid_supervision(**dict(kw, task_state="pending"))["reason"], "not_settled_failure")
        self.assertEqual(sa.decide_hybrid_supervision(**dict(kw, task_state="uncertain"))["reason"], "not_settled_failure")
        self.assertEqual(sa.decide_hybrid_supervision(**dict(kw, effect_class="external"))["reason"], "effects_require_reconciliation")
        self.assertEqual(sa.decide_hybrid_supervision(**dict(kw, failure_class="unknown"))["reason"], "failure_requires_classification")
        self.assertEqual(sa.decide_hybrid_supervision(**dict(kw, attempt_number=3))["reason"], "retry_budget_exhausted")
        self.assertEqual(sa.decide_hybrid_supervision(**dict(kw, otp_policy="temporary"))["reason"], "otp_policy_drop_child")

        self._expect_err("ERR_INVALID_TASK_STATE", sa.decide_hybrid_supervision, **dict(kw, task_state=1))
        self._expect_err("ERR_INVALID_TASK_STATE", sa.decide_hybrid_supervision, **dict(kw, task_state=""))
        self._expect_err("ERR_INVALID_TASK_STATE", sa.decide_hybrid_supervision, **dict(kw, task_state="   "))
        self._expect_err("ERR_INVALID_TASK_STATE", sa.decide_hybrid_supervision, **dict(kw, task_state="COMPLETED_TYPO"))
        self._expect_err("ERR_INVALID_TASK_STATE", sa.decide_hybrid_supervision, **dict(kw, task_state="banana"))
        self._expect_err("ERR_INVALID_FAILURE_CLASS", sa.decide_hybrid_supervision, **dict(kw, failure_class=1))
        self._expect_err("ERR_INVALID_FAILURE_CLASS", sa.decide_hybrid_supervision, **dict(kw, failure_class="bad"))
        self._expect_err("ERR_INVALID_EFFECT_CLASS", sa.decide_hybrid_supervision, **dict(kw, effect_class=1))
        self._expect_err("ERR_INVALID_EFFECT_CLASS", sa.decide_hybrid_supervision, **dict(kw, effect_class="bad"))
        self._expect_err("ERR_INVALID_ATTEMPT", sa.decide_hybrid_supervision, **dict(kw, attempt_number=True))
        self._expect_err("ERR_INVALID_ATTEMPT", sa.decide_hybrid_supervision, **dict(kw, attempt_number=0))
        self._expect_err("ERR_INVALID_MAX_RETRIES", sa.decide_hybrid_supervision, **dict(kw, max_retries=True))
        self._expect_err("ERR_INVALID_MAX_RETRIES", sa.decide_hybrid_supervision, **dict(kw, max_retries=-1))
        self._expect_err("ERR_INVALID_MAX_RETRIES", sa.decide_hybrid_supervision, **dict(kw, max_retries=11))
        self._expect_err("ERR_INVALID_STOP_FLAG", sa.decide_hybrid_supervision, **dict(kw, stop_requested=1))

    def test_07_bypass_regressions_polarity_dos_nonchurn(self) -> None:
        # A1-A4: verdict/outcome polarity is declared per grammar token (ASCII only);
        # VERIFIED + adverse-polarity or adverse + supports-polarity must be rejected.
        base = _valid_two_zone_spec()
        for om, pev, pig in (("BROKEN", "VERIFIED", "E2_SEALED"), ("FAILURE", "VERIFIED", "E2_SEALED"),
                             ("P\u0410SS", "FALSIFIED", "E0_LEAD"), ("F\u0410IL", "VERIFIED", "E2_SEALED")):
            spec = copy.deepcopy(base)
            spec["airlock_envelope"]["claim_ledger"]["finite_outcome_grammar"][om] = "against" if pev == "VERIFIED" else "supports"
            spec["verdict_packet"]["outcome_matched"] = om
            spec["verdict_packet"]["part_e_verdict"] = pev
            spec["verdict_packet"]["part_i_grade"] = pig
            spec["verdict_packet"]["counterexample"] = None if pev == "VERIFIED" else "cex"
            res = sa.certify_two_zone_airlock(spec)
            self.assertFalse(res["passed"], (om, pev))
            self.assertIn("VERDICT_OUTCOME_CONTRADICTS_PART_E", res["violations"])
        # A8: VERIFIED with a 1/1 mutation run is below the floor.
        spec = copy.deepcopy(base)
        spec["verdict_packet"]["r5_killed"] = 1
        spec["verdict_packet"]["r5_total"] = 1
        res = sa.certify_two_zone_airlock(spec)
        self.assertIn("VERDICT_VERIFIED_R5_FLOOR", res["violations"])
        # A12: deep nesting is rejected as forbidden (no RecursionError).
        deep = 1
        for _ in range(5000):
            deep = {"a": deep}
        self.assertTrue(sa.contains_forbidden_non_exact(deep))
        # A13: >4300-digit fraction string is a typed error, not ValueError.
        with self.assertRaises(sa.AletheiaError) as cm:
            sa.certify_restart_intensity_trace(1, 5, ["1" * 5000 + "/1"])
        self.assertEqual(cm.exception.code, "ERR_INVALID_FRACTION_STR")
        # A14b: rest_for_one derives the downstream set from child order.
        after = [
            {"id": "author", "policy": "permanent", "generation": 1, "snapshot_sha256": SHA_1, "alive": True},
            {"id": "airlock", "policy": "permanent", "generation": 1, "snapshot_sha256": SHA_1, "alive": True},
            {"id": "verifier", "policy": "permanent", "generation": 2, "snapshot_sha256": SHA_2, "alive": True},
        ]
        nc = sa.verify_snapshot_non_churn(after, "author", ["verifier"], strategy="rest_for_one")
        self.assertFalse(nc["passed"])  # derived downstream [airlock, verifier]; verifier is stale
        self.assertEqual(nc["stale_downstream_ids"], ["verifier"])

    def test_06_selftest_dynamic_tampering_and_3mode_isolated_parity(self) -> None:
        # _run_expected_rejection returns rejected=False when no error raised
        no_rej = sa._run_expected_rejection(lambda: 42, "ANY_CODE")
        self.assertFalse(no_rej["rejected"])
        self.assertIsNone(no_rej["code"])

        res = sa.run_v21_proposals_self_test()
        self.assertTrue(res["passed"])
        self.assertEqual(res["verdict"], "ALETHEIA_V21_PROPOSALS_VERIFIED")
        self.assertFalse(sa.contains_forbidden_non_exact(res))

        # Kill every BoolOp clause in run_v21_proposals_self_test() checks dynamically
        with mock.patch.object(sa, "certify_law1b_serendipity_mining", side_effect=[{"certified": True, "unmerged_share": "0/1"}, AletheiaError("L1B_CLOSED_UNMERGED_BLIND_SPOT", "m")]):
            tampered = sa.run_v21_proposals_self_test()
            self.assertFalse(tampered["passed"])
            self.assertEqual(tampered["verdict"], "ALETHEIA_V21_PROPOSALS_FAILED")
        with mock.patch.object(sa, "certify_law1b_serendipity_mining", side_effect=[{"certified": False, "unmerged_share": "11/20"}, AletheiaError("L1B_CLOSED_UNMERGED_BLIND_SPOT", "m")]):
            self.assertFalse(sa.run_v21_proposals_self_test()["passed"])
        with mock.patch.object(sa, "certify_two_zone_airlock", side_effect=[{"passed": True, "violations": []}, {"passed": True, "violations": ["ZONE_B_R3_VERIFIER_IN_ZONE_A_PARTICIPANTS"]}]):
            self.assertFalse(sa.run_v21_proposals_self_test()["passed"])
        with mock.patch.object(sa, "certify_two_zone_airlock", side_effect=[{"passed": True, "violations": []}, {"passed": False, "violations": ["OTHER"]}]):
            self.assertFalse(sa.run_v21_proposals_self_test()["passed"])
        with mock.patch.object(sa, "verify_snapshot_non_churn", side_effect=[{"passed": False}, {"passed": False, "error_code": "ERR_SNAPSHOT_CHURN"}]):
            self.assertFalse(sa.run_v21_proposals_self_test()["passed"])
        with mock.patch.object(sa, "apply_otp_strategy_crash", side_effect=[
            {"children_after": [
                {"id": "planner", "policy": "permanent", "generation": 2, "snapshot_sha256": SHA_1, "alive": True},
                {"id": "author", "policy": "transient", "generation": 2, "snapshot_sha256": SHA_2, "alive": True},
                {"id": "airlock", "policy": "permanent", "generation": 2, "snapshot_sha256": SHA_2, "alive": True},
                {"id": "verifier", "policy": "transient", "generation": 2, "snapshot_sha256": SHA_2, "alive": True},
            ]},
            {"children_after": [
                {"id": "planner", "policy": "permanent", "generation": 1, "snapshot_sha256": SHA_1, "alive": True},
                {"id": "author", "policy": "transient", "generation": 2, "snapshot_sha256": SHA_2, "alive": True},
                {"id": "airlock", "policy": "permanent", "generation": 1, "snapshot_sha256": SHA_1, "alive": True},
                {"id": "verifier", "policy": "transient", "generation": 1, "snapshot_sha256": SHA_1, "alive": True},
            ]},
        ]):
            self.assertFalse(sa.run_v21_proposals_self_test()["passed"])
        with mock.patch.object(sa, "verify_snapshot_non_churn", side_effect=[{"passed": True}, {"passed": True, "error_code": "ERR_SNAPSHOT_CHURN"}]):
            self.assertFalse(sa.run_v21_proposals_self_test()["passed"])
        with mock.patch.object(sa, "verify_snapshot_non_churn", side_effect=[{"passed": True}, {"passed": False, "error_code": "OTHER"}]):
            self.assertFalse(sa.run_v21_proposals_self_test()["passed"])
        with mock.patch.object(sa, "certify_restart_intensity_trace", return_value={"escalated": False, "escalated_at": "1/1"}):
            self.assertFalse(sa.run_v21_proposals_self_test()["passed"])
        with mock.patch.object(sa, "certify_restart_intensity_trace", return_value={"escalated": True, "escalated_at": "2/1"}):
            self.assertFalse(sa.run_v21_proposals_self_test()["passed"])
        with mock.patch.object(sa, "certify_monitor_vs_link_isolation", side_effect=[{"isolated": True}, {"isolated": True, "error_code": "ERR_COORDINATOR_COLLATERAL_KILL"}]):
            self.assertFalse(sa.run_v21_proposals_self_test()["passed"])
        with mock.patch.object(sa, "certify_monitor_vs_link_isolation", side_effect=[{"isolated": True}, {"isolated": False, "error_code": "OTHER"}]):
            self.assertFalse(sa.run_v21_proposals_self_test()["passed"])
        with mock.patch.object(sa, "decide_hybrid_supervision", return_value={"action": "retry", "reason": "cancelled"}):
            self.assertFalse(sa.run_v21_proposals_self_test()["passed"])
        with mock.patch.object(sa, "decide_hybrid_supervision", return_value={"action": "final", "reason": "other"}):
            self.assertFalse(sa.run_v21_proposals_self_test()["passed"])

        # CLI main() text & json + failure exit code 1
        buf_txt = io.StringIO()
        with redirect_stdout(buf_txt):
            rc_txt = sa.main([])
        self.assertEqual(rc_txt, 0)
        self.assertIn("ALETHEIA_V21_PROPOSALS_VERIFIED", buf_txt.getvalue())

        buf_json = io.StringIO()
        with redirect_stdout(buf_json):
            rc_json = sa.main(["--json"])
        self.assertEqual(rc_json, 0)
        self.assertEqual(json.loads(buf_json.getvalue())["canonical_sha256"], res["canonical_sha256"])

        buf_fail = io.StringIO()
        with mock.patch.object(sa, "run_v21_proposals_self_test", return_value={"passed": False, "verdict": "FAIL", "canonical_sha256": SHA_1}):
            with redirect_stdout(buf_fail):
                rc_fail = sa.main([])
        self.assertEqual(rc_fail, 1)

        # 3-mode isolated -I R4 parity on aletheia/supervision_airlock.py --json
        script = str(CLI_ROOT / "aletheia" / "supervision_airlock.py")
        digests: list[str] = []
        for flags in (["-I", "-B"], ["-I", "-O", "-B"], ["-I", "-B", "-W", "error"]):
            proc = subprocess.run(
                [sys.executable, *flags, script, "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            digests.append(hashlib.sha256(proc.stdout.encode("utf-8")).hexdigest())
        self.assertEqual(len(set(digests)), 1)


    def test_08_grammar_polarity_casefold_type_and_strategy_guards(self) -> None:
        # --- airlock_envelope is genuinely stripped from a Zone-A submission ---
        room = dict(_valid_tech_submission(), transcript="debate", authors=["alice"], models=["m1"], agreement_count=2)
        stripped = sa.strip_zone_a_to_airlock_envelope(room)
        for social_key in ("transcript", "authors", "models", "agreement_count"):
            self.assertNotIn(social_key, stripped)
        self.assertEqual(set(stripped.keys()), {"schema", "envelope_id", "claim_ledger", "pinned_inputs", "artifact_bundle"})

        # --- Blocking: a grammar with no `against` token must be rejected ---
        env = sa.strip_zone_a_to_airlock_envelope(_valid_tech_submission())

        def _env_grammar_viol(grammar) -> None:
            e = copy.deepcopy(env)
            e["claim_ledger"]["finite_outcome_grammar"] = grammar
            r = sa.validate_airlock_envelope(e)
            self.assertFalse(r["passed"])
            self.assertIn("INVALID_FINITE_OUTCOME_GRAMMAR", r["violations"])

        _env_grammar_viol({"PASS": "supports", "FAIL": "supports"})  # no against -> reject
        _env_grammar_viol({"PASS": "against", "FAIL": "against"})  # no supports -> reject
        _env_grammar_viol({"PASS": "supports", "pass": "against"})  # case-colliding polarity -> reject
        _env_grammar_viol({"A": "supports", "a": "inconclusive"})  # case-colliding any polarity -> reject
        # valid: both polarities present, case-distinct
        e_ok = copy.deepcopy(env)
        e_ok["claim_ledger"]["finite_outcome_grammar"] = {"PASS": "supports", "FAIL": "against"}
        self.assertTrue(sa.validate_airlock_envelope(e_ok)["passed"])

        # --- Blocking: case-colliding grammar must not certify FALSIFIED + "pass" ---
        sp = _valid_two_zone_spec()
        sp["airlock_envelope"]["claim_ledger"]["finite_outcome_grammar"] = {"PASS": "supports", "pass": "against"}
        sp["verdict_packet"]["part_e_verdict"] = "FALSIFIED"
        sp["verdict_packet"]["part_i_grade"] = "E0_LEAD"
        sp["verdict_packet"]["outcome_matched"] = "pass"
        sp["verdict_packet"]["counterexample"] = "cex"
        r = sa.certify_two_zone_airlock(sp)
        self.assertFalse(r["passed"])
        self.assertTrue(any(v.endswith("INVALID_FINITE_OUTCOME_GRAMMAR") for v in r["violations"]))

        # --- Also-fix: unhashable outcome_matched -> typed violation, not TypeError ---
        sp2 = _valid_two_zone_spec()
        sp2["verdict_packet"]["outcome_matched"] = ["SUPPORTED"]
        r2 = sa.certify_two_zone_airlock(sp2)
        self.assertFalse(r2["passed"])
        self.assertIn("VERDICT_OUTCOME_NOT_IN_DECLARED_GRAMMAR", r2["violations"])

        # --- Also-fix: strategy is validated and downstream ALWAYS derived from child order ---
        after = [
            {"id": "author", "policy": "permanent", "generation": 1, "snapshot_sha256": SHA_1, "alive": True},
            {"id": "airlock", "policy": "permanent", "generation": 1, "snapshot_sha256": SHA_1, "alive": True},
            {"id": "verifier", "policy": "permanent", "generation": 1, "snapshot_sha256": SHA_1, "alive": True},
        ]
        # None no longer falls back to the caller's list: derived = [airlock, verifier]
        nc_none = sa.verify_snapshot_non_churn(after, "author", ["verifier"])
        self.assertTrue(nc_none["passed"])
        self.assertEqual(nc_none["downstream_ids"], ["airlock", "verifier"])
        # case-variant strategy is rejected
        self._expect_err("ERR_INVALID_STRATEGY", sa.verify_snapshot_non_churn, after, "author", ["verifier"], "REST_FOR_ONE")

        # --- Also-fix: 4300-char boundary is inclusive (M010 survivor) ---
        ok4300 = "1" * 4298 + "/1"  # len == 4300 exactly: accepted (boundary inclusive)
        self.assertEqual(len(ok4300), 4300)
        self.assertEqual(sa.parse_nonneg_fraction(ok4300, "t"), Fraction(int("1" * 4298), 1))
        with self.assertRaises(sa.AletheiaError) as cm_b:
            sa.parse_nonneg_fraction("1" * 4299 + "/1", "t")  # len == 4301: rejected
        self.assertEqual(cm_b.exception.code, "ERR_INVALID_FRACTION_STR")


if __name__ == "__main__":
    unittest.main()
