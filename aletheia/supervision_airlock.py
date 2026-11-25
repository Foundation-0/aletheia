"""
`aletheia.supervision_airlock`: Pure-Z/Q Executable Reference Certifier for Aletheia v2.1 Proposals.

Pure Python 3 standard library (`int`, `fractions.Fraction`, zero floats on trust paths or JSON,
zero bare `assert`s). Safe and bit-identical across all three isolated R4 modes:
  python3 -I -B aletheia/supervision_airlock.py --json
  python3 -I -O -B aletheia/supervision_airlock.py --json
  python3 -I -B -W error aletheia/supervision_airlock.py --json

Unifies three dual-family verified architectural primitives:
  1. Law 1b Unmerged-PR Serendipity Mining (`certify_law1b_serendipity_mining`, `AUDIT-111R`)
  2. Two-Zone Blinded Airlock, `ClaimLedger` Outcome Binding & Observational Non-Interference
     (`strip_zone_a_to_airlock_envelope`, `validate_airlock_envelope`, `certify_two_zone_airlock`,
     `verify_observational_non_interference`, `AUDIT-105R`, harmonized with `EMPIRICAL_CLAIMS.md`
     except the deliberate verdict-packet adverse-grade cap at `E0_LEAD` (see spec :52 divergence note))
  3. Erlang/OTP Supervision Tree Semantics, Frozen-Snapshot `rest_for_one` Non-Churn,
     Pure-Q Sliding-Window Intensity, `monitor` vs. `link` Fault Isolation & `exo#1200` Bridge
     (`otp_should_restart`, `apply_otp_strategy_crash`, `verify_snapshot_non_churn`,
     `certify_restart_intensity_trace`, `certify_monitor_vs_link_isolation`,
     `decide_hybrid_supervision`, `AUDIT-110R`).

AUDIT-111R / AUDIT-105R / AUDIT-110R are pending on open cave-expedition PRs #1 and #27
(not yet on cave main); cited here as pending, not as verified.

Declared-Record / Formal-Model Scope Boundary:
  Certifies well-formedness, invariants, and exact discrete transitions over caller-supplied
  records and traces; byte-level disk re-hashing of external snapshots and OS-level process
  sandboxing remain outside this pure-stdlib module.
"""
from __future__ import annotations

import argparse
from collections import deque
import copy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Callable

if not __package__:
    _PKG_ROOT = str(Path(__file__).resolve().parent.parent)
    if _PKG_ROOT not in sys.path:
        sys.path.insert(0, _PKG_ROOT)

from aletheia.strict_io import AletheiaError

# ---------------------------------------------------------------------------
# Closed Schemas, Taxonomies & Regex Patterns
# ---------------------------------------------------------------------------

LAW1B_SCHEMA = "aletheia.law1b.v1"
AIRLOCK_ENVELOPE_SCHEMA = "aletheia.airlock_envelope.v1"
AIRLOCK_VERDICT_SCHEMA = "aletheia.airlock_verdict.v1"
SELFTEST_SCHEMA = "aletheia.v21_proposals.selftest.v1"

HEX40_RE = re.compile(r"\A[0-9a-f]{40}\Z")
HEX64_RE = re.compile(r"\A[0-9a-f]{64}\Z")
ID_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}\Z")
REPO_RE = re.compile(r"\A[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
SAFE_RELPATH_RE = re.compile(r"\A[A-Za-z0-9_./-]+\Z")
FRAC_RE = re.compile(r"\A(0|[1-9][0-9]*)/([1-9][0-9]*)\Z")

LAW1B_MECHANISM_CLASSES: frozenset[str] = frozenset({
    "DENOMINATOR_OR_WEIGHT_BIAS",
    "QUANTILE_OR_INDEX_BOUNDARY",
    "AFFINE_OR_RANGE_PROJECTION",
    "ALGEBRAIC_KERNEL_EQUIVALENCE",
    "LEXER_OR_PARSER_SECURITY_BYPASS",
    "CRYPTO_PIN_OR_STATE_MACHINE",
    "EMPIRICAL_REFUTATION_OR_FREEZE",
    "INTERNAL_STEERING_OR_ARCHITECTURE",
    "EXACT_CERTIFIER_OR_DOMAIN_TOOL",
})
LAW1B_UNMERGED_STATUSES: frozenset[str] = frozenset({"open", "closed_unmerged"})
LAW1B_EVIDENCE_STANDINGS: frozenset[str] = frozenset({"EXECUTED_EXACT_WITNESS", "CATALOGED_LEAD"})
LAW1B_NOVELTY_LEVELS: frozenset[str] = frozenset({"N0", "N1", "N2"})
LAW1B_SPEC_KEYS: frozenset[str] = frozenset({"schema", "external_writes", "repos_scanned", "mined_entries"})
LAW1B_REPO_KEYS: frozenset[str] = frozenset({"repo", "fetched", "open", "closed_unmerged", "merged", "prs_json_sha256"})
LAW1B_ENTRY_KEYS: frozenset[str] = frozenset({
    "repo", "number", "status", "head_sha", "snapshot_sha256",
    "mechanism_class", "evidence_standing", "honest_novelty", "operator_summary",
})

FORBIDDEN_AIRLOCK_LEAK_KEYS: frozenset[str] = frozenset({
    "transcript", "board_messages", "author", "authors", "model", "models",
    "agreement_count", "votes", "consensus", "persuasion", "socratic_log",
    "seat_name", "deliberation", "chat_history", "zone_a_messages",
})
ZONE_B_REQUIRED_BLOCKED_CHANNELS: frozenset[str] = frozenset({
    "bus", "memory", "peers", "peer_send", "bus_post", "send_message", "zone_a_board",
})
ALLOWED_ENVELOPE_KEYS: frozenset[str] = frozenset({
    "schema", "envelope_id", "claim_ledger", "pinned_inputs", "artifact_bundle",
})
ALLOWED_CLAIM_LEDGER_KEYS: frozenset[str] = frozenset({
    "claim_id", "finite_outcome_grammar", "falsifier_predicate",
    "novelty_default", "linguistic_ceiling",
})
ALLOWED_PINNED_SECTION_KEYS: frozenset[str] = frozenset({"files", "seeds"})
ALLOWED_PINNED_INPUT_KEYS: frozenset[str] = frozenset({"id", "sha256", "bytes"})
ALLOWED_ARTIFACT_KEYS: frozenset[str] = frozenset({"relpath", "sha256", "role"})
ALLOWED_ARTIFACT_ROLES: frozenset[str] = frozenset({"code", "test", "data"})
ALLOWED_ZONE_A_KEYS: frozenset[str] = frozenset({
    "mode", "conductor", "participants", "round_robin_enforced",
    "silent_turns_allowed", "silent_turns_observed", "distinct_hypotheses_count",
    "output_tag", "agreement_counted_as_evidence",
})
ALLOWED_ZONE_B_KEYS: frozenset[str] = frozenset({
    "channel_mode", "verifier_seat", "read_scope", "blocked_channels",
    "can_read_zone_a_board", "can_approve_own_changes", "write_scopes",
})
ALLOWED_VERDICT_KEYS: frozenset[str] = frozenset({
    "schema", "envelope_id", "envelope_sha256", "verifier_seat",
    "part_e_verdict", "part_i_grade", "outcome_matched",
    "r5_killed", "r5_total", "counterexample",
})
OUTCOME_POLARITIES: frozenset[str] = frozenset({"supports", "against", "inconclusive"})
MIN_R5_TOTAL_FOR_VERIFIED = 10

ALLOWED_PART_E_VERDICTS: frozenset[str] = frozenset({
    "VERIFIED", "PARTIAL_FRAGILE", "FALSIFIED", "NOT_SHOWN",
})
# Harmonized directly with Foundation-0/aletheia#10 (EMPIRICAL_CLAIMS.md @ bf37ea73)
EVIDENCE_GRADE_RANK: dict[str, int] = {
    "E0_LEAD": 0,
    "E1_PLANNED": 1,
    "E2_SEALED": 2,
    "E3_REIMPLEMENTED": 3,
    "E4_REPLICATED": 4,
    "E5_OUTSIDE_REPLICATED": 5,
}
ALLOWED_PART_I_GRADES: frozenset[str] = frozenset(EVIDENCE_GRADE_RANK.keys()) | {"EXACT_ONLY_NA"}

RESTART_POLICIES: frozenset[str] = frozenset({"permanent", "transient", "temporary"})
EXIT_REASONS: frozenset[str] = frozenset({"normal", "shutdown", "abnormal"})
SIGNAL_EXIT_REASONS: frozenset[str] = frozenset({"normal", "shutdown", "abnormal", "kill"})
RESTART_STRATEGIES: frozenset[str] = frozenset({"one_for_one", "one_for_all", "rest_for_one"})
SIGNAL_TOPOLOGIES: frozenset[str] = frozenset({"monitor", "link_untrapped", "link_trap_exit"})
OTP_CHILD_KEYS: frozenset[str] = frozenset({"id", "policy", "generation", "snapshot_sha256", "alive"})
EXO1200_TASK_STATES: frozenset[str] = frozenset({
    "pending", "running", "failed", "completed", "stopped", "cancelled", "uncertain",
})
EXO1200_FAILURE_CLASSES: frozenset[str] = frozenset({
    "unknown", "transient", "denied", "spend_limit", "cancelled", "permanent",
})
EXO1200_EFFECT_CLASSES: frozenset[str] = frozenset({"unknown", "not_dispatched", "external"})


# ---------------------------------------------------------------------------
# Pure-Z / Pure-Q Strict Helpers (Zero Floats, Zero Bare Asserts)
# ---------------------------------------------------------------------------

def _is_strict_int(val: Any) -> bool:
    return type(val) is int


def _is_nonempty_str(val: Any) -> bool:
    return type(val) is str and len(val.strip()) > 0


def _in_str_set(val: Any, allowed: frozenset[str] | dict[str, Any]) -> bool:
    return type(val) is str and val in allowed


def _has_control_char(val: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in val)


def _is_clean_ascii_text(val: Any) -> bool:
    return _is_nonempty_str(val) and all(32 <= ord(ch) <= 126 for ch in val)


def _is_hex40(val: Any) -> bool:
    return type(val) is str and bool(HEX40_RE.fullmatch(val)) and len(set(val)) > 1


def _is_hex64(val: Any) -> bool:
    return type(val) is str and bool(HEX64_RE.fullmatch(val)) and len(set(val)) > 1


def _is_valid_id(val: Any) -> bool:
    return type(val) is str and bool(ID_RE.fullmatch(val))


def _is_safe_relpath(val: Any) -> bool:
    if type(val) is not str:
        return False
    if not SAFE_RELPATH_RE.fullmatch(val):
        return False
    return not any(part in ("", ".", "..") for part in val.split("/"))


MAX_JSON_DEPTH = 64


def contains_forbidden_non_exact(obj: Any, _depth: int = 0) -> bool:
    """Return True if obj contains any float, complex, non-str dict key, non-JSON container,
    or nesting deeper than MAX_JSON_DEPTH (DoS cap — raises no RecursionError)."""
    if obj is None:
        return False
    if type(obj) in (bool, int, str):
        return False
    if _depth > MAX_JSON_DEPTH:
        return True
    if type(obj) is dict:
        return any(type(k) is not str or contains_forbidden_non_exact(v, _depth + 1) for k, v in obj.items())
    if type(obj) in (list, tuple):
        return any(contains_forbidden_non_exact(v, _depth + 1) for v in obj)
    return True


def canonical_json_bytes(obj: Any) -> bytes:
    if contains_forbidden_non_exact(obj):
        raise AletheiaError("ERR_FLOAT_OR_NON_JSON", "float or non-JSON value forbidden on trust path")
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def canonical_sha256(obj: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


def parse_nonneg_fraction(val: Any, label: str = "tick") -> Fraction:
    """Parse strict non-negative int, Fraction, or canonical reduced 'p/q' string."""
    if type(val) is int:
        if val < 0:
            raise AletheiaError("ERR_NEGATIVE_TICK", f"{label} must be >= 0")
        return Fraction(val, 1)
    if type(val) is Fraction:
        if val < 0:
            raise AletheiaError("ERR_NEGATIVE_TICK", f"{label} must be >= 0")
        return val
    if type(val) is str:
        if len(val) > 4300:
            raise AletheiaError("ERR_INVALID_FRACTION_STR", f"{label} rational string exceeds 4300-char cap")
        if not FRAC_RE.fullmatch(val):
            raise AletheiaError("ERR_INVALID_FRACTION_STR", f"{label} invalid rational string")
        num_s, den_s = val.split("/")
        num = int(num_s)
        den = int(den_s)
        if math.gcd(num, den) != 1:
            raise AletheiaError("ERR_UNREDUCED_FRACTION", f"{label} must be in lowest terms")
        return Fraction(num, den)
    raise AletheiaError("ERR_INVALID_TICK_TYPE", f"{label} must be int, Fraction, or canonical 'p/q' str")


def frac_str(q: Fraction) -> str:
    return f"{q.numerator}/{q.denominator}"


# ---------------------------------------------------------------------------
# 1. Law 1b: Blind-Spot-Free Cross-Repo Serendipity & Unmerged-PR Portal Mining (AUDIT-111R, pending on cave-expedition PRs #1/#27)
# ---------------------------------------------------------------------------

def certify_law1b_serendipity_mining(spec: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed certifier enforcing Aletheia v2.1 Law-1b guards G-1b.1..G-1b.4. "Blind-spot-free" = >=1 open and >=1 closed-unmerged PR mined OVERALL (not per repo, no coverage fraction); executed-witness honest_novelty is caller-declared.

    Declared-Record Scope Boundary: certifies caller-supplied mining records;
    disk re-hashing of frozen GitHub JSON files is performed separately.
    """
    if type(spec) is not dict:
        raise AletheiaError("L1B_INVALID_SPEC", "spec must be a dict")
    if contains_forbidden_non_exact(spec):
        raise AletheiaError("L1B_FLOAT_FORBIDDEN", "float or non-JSON value forbidden in Law-1b spec")
    if set(spec.keys()) != LAW1B_SPEC_KEYS:
        raise AletheiaError("L1B_SPEC_KEYSET_MISMATCH", "unexpected or missing top-level Law-1b keys")
    if spec["schema"] != LAW1B_SCHEMA:
        raise AletheiaError("L1B_INVALID_SCHEMA", f"schema must equal {LAW1B_SCHEMA!r}")
    if not _is_strict_int(spec["external_writes"]):
        raise AletheiaError("L1B_NONZERO_EXTERNAL_WRITES", "external_writes must be strict int 0")
    if spec["external_writes"] != 0:
        raise AletheiaError("L1B_NONZERO_EXTERNAL_WRITES", "Law-1b portal mining must be strictly read-only")

    repos = spec["repos_scanned"]
    if type(repos) is not list:
        raise AletheiaError("L1B_REPOS_EMPTY", "repos_scanned must be a non-empty list")
    if len(repos) == 0:
        raise AletheiaError("L1B_REPOS_EMPTY", "repos_scanned must be non-empty")

    repo_caps: dict[str, tuple[int, int]] = {}
    tot_fetched = 0
    tot_open = 0
    tot_closed_unmerged = 0
    tot_merged = 0

    for idx, row in enumerate(repos):
        if type(row) is not dict:
            raise AletheiaError("L1B_REPO_SCHEMA", f"repos_scanned[{idx}] must be dict")
        if set(row.keys()) != LAW1B_REPO_KEYS:
            raise AletheiaError("L1B_REPO_SCHEMA", f"repos_scanned[{idx}] keyset mismatch")
        rname = row["repo"]
        if type(rname) is not str:
            raise AletheiaError("L1B_INVALID_REPO_NAME", f"repos_scanned[{idx}].repo must be str")
        if not REPO_RE.fullmatch(rname):
            raise AletheiaError("L1B_INVALID_REPO_NAME", f"invalid repo name {rname!r}")
        rkey = rname.lower()
        if rkey in repo_caps:
            raise AletheiaError("L1B_DUPLICATE_REPO", f"duplicate repo {rname!r}")
        if not _is_hex64(row["prs_json_sha256"]):
            raise AletheiaError("L1B_INVALID_PRS_SHA256", f"invalid prs_json_sha256 for {rname}")

        for ck in ("fetched", "open", "closed_unmerged", "merged"):
            if not _is_strict_int(row[ck]):
                raise AletheiaError("L1B_INVALID_REPO_COUNT", f"{rname}.{ck} must be strict int")
            if row[ck] < 0:
                raise AletheiaError("L1B_INVALID_REPO_COUNT", f"{rname}.{ck} must be >= 0")
        if row["fetched"] == 0:
            raise AletheiaError("L1B_EMPTY_REPO_FETCH", f"{rname}.fetched must be > 0")
        if row["open"] + row["closed_unmerged"] + row["merged"] != row["fetched"]:
            raise AletheiaError("L1B_COUNT_CONSERVATION_FAILED", f"{rname} counts do not sum to fetched")

        repo_caps[rkey] = (row["open"], row["closed_unmerged"])
        tot_fetched += row["fetched"]
        tot_open += row["open"]
        tot_closed_unmerged += row["closed_unmerged"]
        tot_merged += row["merged"]

    entries = spec["mined_entries"]
    if type(entries) is not list:
        raise AletheiaError("L1B_ENTRIES_EMPTY", "mined_entries must be a non-empty list")
    if len(entries) == 0:
        raise AletheiaError("L1B_ENTRIES_EMPTY", "mined_entries must be non-empty")

    seen_pr: set[tuple[str, int]] = set()
    mined_open_by_repo: dict[str, int] = {rk: 0 for rk in repo_caps}
    mined_closed_by_repo: dict[str, int] = {rk: 0 for rk in repo_caps}
    mined_open_total = 0
    mined_closed_total = 0
    executed_witnesses = 0
    cataloged_leads = 0

    for idx, item in enumerate(entries):
        if type(item) is not dict:
            raise AletheiaError("L1B_ENTRY_SCHEMA", f"mined_entries[{idx}] must be dict")
        if set(item.keys()) != LAW1B_ENTRY_KEYS:
            raise AletheiaError("L1B_ENTRY_SCHEMA", f"mined_entries[{idx}] keyset mismatch")
        er = item["repo"]
        if type(er) is not str:
            raise AletheiaError("L1B_ENTRY_UNKNOWN_REPO", f"mined_entries[{idx}].repo must be str")
        ekey = er.lower()
        if ekey not in repo_caps:
            raise AletheiaError("L1B_ENTRY_UNKNOWN_REPO", f"entry repo {er!r} not in repos_scanned")
        num = item["number"]
        if not _is_strict_int(num):
            raise AletheiaError("L1B_INVALID_PR_NUMBER", f"PR number must be strict int")
        if num < 1:
            raise AletheiaError("L1B_INVALID_PR_NUMBER", f"PR number must be >= 1")
        pr_key = (ekey, num)
        if pr_key in seen_pr:
            raise AletheiaError("L1B_DUPLICATE_PR_ENTRY", f"duplicate PR entry {er}#{num}")
        seen_pr.add(pr_key)

        st = item["status"]
        if not _in_str_set(st, LAW1B_UNMERGED_STATUSES):
            raise AletheiaError("L1B_INVALID_STATUS", f"status must be open or closed_unmerged, got {st!r}")
        if not _is_hex40(item["head_sha"]):
            raise AletheiaError("L1B_INVALID_HEAD_SHA", f"invalid 40-hex head_sha for {er}#{num}")
        if not _is_hex64(item["snapshot_sha256"]):
            raise AletheiaError("L1B_INVALID_SNAPSHOT_SHA256", f"invalid 64-hex snapshot_sha256 for {er}#{num}")
        mc = item["mechanism_class"]
        if not _in_str_set(mc, LAW1B_MECHANISM_CLASSES):
            raise AletheiaError("L1B_INVALID_MECHANISM_CLASS", f"unknown mechanism_class {mc!r}")
        standing = item["evidence_standing"]
        if not _in_str_set(standing, LAW1B_EVIDENCE_STANDINGS):
            raise AletheiaError("L1B_INVALID_STANDING", f"unknown evidence_standing {standing!r}")
        nov = item["honest_novelty"]
        if not _in_str_set(nov, LAW1B_NOVELTY_LEVELS):
            raise AletheiaError("L1B_INVALID_NOVELTY", f"unknown honest_novelty {nov!r}")
        if standing == "CATALOGED_LEAD":
            if nov != "N0":
                raise AletheiaError("L1B_LEAD_CANNOT_CLAIM_ABOVE_N0", f"CATALOGED_LEAD {er}#{num} capped at N0")
            cataloged_leads += 1
        else:
            executed_witnesses += 1
        if not _is_clean_ascii_text(item["operator_summary"]):
            raise AletheiaError("L1B_INVALID_OPERATOR_SUMMARY", f"operator_summary must be non-empty clean ASCII")

        if st == "open":
            mined_open_total += 1
            mined_open_by_repo[ekey] += 1
            if mined_open_by_repo[ekey] > repo_caps[ekey][0]:
                raise AletheiaError("L1B_REPO_OPEN_COUNT_EXCEEDED", f"{er} mined open PRs exceed scanned open")
        else:
            mined_closed_total += 1
            mined_closed_by_repo[ekey] += 1
            if mined_closed_by_repo[ekey] > repo_caps[ekey][1]:
                raise AletheiaError(
                    "L1B_REPO_CLOSED_UNMERGED_COUNT_EXCEEDED",
                    f"{er} mined closed_unmerged PRs exceed scanned closed_unmerged",
                )

    if tot_closed_unmerged > 0:
        if mined_closed_total == 0:
            raise AletheiaError("L1B_CLOSED_UNMERGED_BLIND_SPOT", "closed_unmerged PRs present but none mined")
    if tot_open > 0:
        if mined_open_total == 0:
            raise AletheiaError("L1B_OPEN_PR_BLIND_SPOT", "open PRs present but none mined")
    if executed_witnesses == 0:
        raise AletheiaError("L1B_ZERO_EXECUTED_WITNESSES", "at least one EXECUTED_EXACT_WITNESS required")

    unmerged_total = tot_open + tot_closed_unmerged
    return {
        "schema": LAW1B_SCHEMA,
        "certified": True,
        "repos_scanned_count": len(repos),
        "total_fetched": tot_fetched,
        "total_open": tot_open,
        "total_closed_unmerged": tot_closed_unmerged,
        "total_merged": tot_merged,
        "unmerged_share": frac_str(Fraction(unmerged_total, tot_fetched)),
        "mined_open_count": mined_open_total,
        "mined_closed_unmerged_count": mined_closed_total,
        "executed_witness_count": executed_witnesses,
        "cataloged_lead_count": cataloged_leads,
    }


# ---------------------------------------------------------------------------
# 2. Two-Zone Blinded Airlock & ClaimLedger Binding (AUDIT-105R)
# ---------------------------------------------------------------------------

def _scan_airlock_leak_keys(obj: Any, path: str = "root") -> list[str]:
    found: list[str] = []
    if type(obj) is dict:
        for k, v in obj.items():
            if type(k) is not str:
                found.append(f"NON_STR_KEY:{path}")
                klabel = "<non_str>"
            else:
                if k.strip().lower() in FORBIDDEN_AIRLOCK_LEAK_KEYS:
                    found.append(f"FORBIDDEN_LEAK_KEY:{path}.{k}")
                klabel = k
            found.extend(_scan_airlock_leak_keys(v, f"{path}.{klabel}"))
    elif type(obj) in (list, tuple):
        for idx, item in enumerate(obj):
            found.extend(_scan_airlock_leak_keys(item, f"{path}[{idx}]"))
    return found


def strip_zone_a_to_airlock_envelope(zone_a_submission: dict[str, Any]) -> dict[str, Any]:
    """M03 Deliberate Stripper: deep-copies only blinded technical fields across the Airlock."""
    if type(zone_a_submission) is not dict:
        raise AletheiaError("INVALID_ZONE_A_SUBMISSION", "zone_a_submission must be dict")
    if contains_forbidden_non_exact(zone_a_submission):
        raise AletheiaError("INVALID_ZONE_A_SUBMISSION", "float or non-JSON value forbidden")
    for req in ("envelope_id", "claim_ledger", "pinned_inputs", "artifact_bundle"):
        if req not in zone_a_submission:
            raise AletheiaError("MISSING_REQUIRED_AIRLOCK_SOURCE_FIELD", f"missing field {req!r}")
    return {
        "schema": AIRLOCK_ENVELOPE_SCHEMA,
        "envelope_id": copy.deepcopy(zone_a_submission["envelope_id"]),
        "claim_ledger": copy.deepcopy(zone_a_submission["claim_ledger"]),
        "pinned_inputs": copy.deepcopy(zone_a_submission["pinned_inputs"]),
        "artifact_bundle": copy.deepcopy(zone_a_submission["artifact_bundle"]),
    }


def validate_airlock_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed validator for a stripped Zone-A -> Zone-B Airlock envelope."""
    violations: list[str] = []
    if type(envelope) is not dict:
        return {"passed": False, "envelope_sha256": None, "violation_count": 1, "violations": ["INVALID_ENVELOPE_OR_FLOAT"]}
    if contains_forbidden_non_exact(envelope):
        return {"passed": False, "envelope_sha256": None, "violation_count": 1, "violations": ["INVALID_ENVELOPE_OR_FLOAT"]}

    if set(envelope.keys()) != ALLOWED_ENVELOPE_KEYS:
        violations.append("ENVELOPE_KEYSET_MISMATCH")
    violations.extend(_scan_airlock_leak_keys(envelope))

    if envelope.get("schema") != AIRLOCK_ENVELOPE_SCHEMA:
        violations.append("INVALID_ENVELOPE_SCHEMA")
    if not _is_valid_id(envelope.get("envelope_id")):
        violations.append("INVALID_ENVELOPE_ID")

    cl = envelope.get("claim_ledger")
    if type(cl) is not dict:
        violations.append("INVALID_CLAIM_LEDGER_SCHEMA")
    elif set(cl.keys()) != ALLOWED_CLAIM_LEDGER_KEYS:
        violations.append("INVALID_CLAIM_LEDGER_SCHEMA")
    else:
        if not _is_valid_id(cl["claim_id"]):
            violations.append("INVALID_CLAIM_ID")
        grammar = cl["finite_outcome_grammar"]
        bad_grammar = type(grammar) is not dict
        if not bad_grammar:
            if not (2 <= len(grammar) <= 64):
                bad_grammar = True
            elif any(
                not _is_clean_ascii_text(g) or len(g) > 64 or g != g.strip() or not _in_str_set(pol, OUTCOME_POLARITIES)
                for g, pol in grammar.items()
            ):
                bad_grammar = True
        if bad_grammar:
            violations.append("INVALID_FINITE_OUTCOME_GRAMMAR")
        fp = cl["falsifier_predicate"]
        if not _is_nonempty_str(fp):
            violations.append("EMPTY_FALSIFIER_PREDICATE")
        elif not _is_clean_ascii_text(fp) or len(fp) > 4096:
            violations.append("INVALID_FALSIFIER_PREDICATE_CONTENT")
        if cl["novelty_default"] != "N0":
            violations.append("NOVELTY_DEFAULT_MUST_BE_N0")
        ceil = cl["linguistic_ceiling"]
        if not _in_str_set(ceil, EVIDENCE_GRADE_RANK):
            violations.append("INVALID_LINGUISTIC_CEILING")

    pi = envelope.get("pinned_inputs")
    if type(pi) is not dict:
        violations.append("INVALID_PINNED_INPUTS_SCHEMA")
    elif set(pi.keys()) != ALLOWED_PINNED_SECTION_KEYS:
        violations.append("INVALID_PINNED_INPUTS_SCHEMA")
    else:
        files = pi["files"]
        if type(files) is not list:
            violations.append("PINNED_FILES_EMPTY")
        elif len(files) == 0:
            violations.append("PINNED_FILES_EMPTY")
        else:
            seen_ids: set[str] = set()
            for idx, fitem in enumerate(files):
                if type(fitem) is not dict:
                    violations.append(f"PINNED_FILE_{idx}_SCHEMA")
                    continue
                if set(fitem.keys()) != ALLOWED_PINNED_INPUT_KEYS:
                    violations.append(f"PINNED_FILE_{idx}_SCHEMA")
                    continue
                fid = fitem["id"]
                if not _is_valid_id(fid):
                    violations.append(f"PINNED_FILE_{idx}_BAD_OR_DUP_ID")
                elif fid in seen_ids:
                    violations.append(f"PINNED_FILE_{idx}_BAD_OR_DUP_ID")
                else:
                    seen_ids.add(fid)
                if not _is_hex64(fitem["sha256"]):
                    violations.append(f"PINNED_FILE_{idx}_BAD_SHA256")
                if not _is_strict_int(fitem["bytes"]):
                    violations.append(f"PINNED_FILE_{idx}_BAD_BYTES")
                elif fitem["bytes"] < 1:
                    violations.append(f"PINNED_FILE_{idx}_BAD_BYTES")
        seeds = pi["seeds"]
        bad_seeds = type(seeds) is not list
        if not bad_seeds:
            if len(seeds) == 0:
                bad_seeds = True
            elif any(not _is_strict_int(s) or s < 0 for s in seeds):
                bad_seeds = True
            elif len(set(seeds)) != len(seeds):
                bad_seeds = True
        if bad_seeds:
            violations.append("PINNED_SEEDS_INVALID")

    ab = envelope.get("artifact_bundle")
    if type(ab) is not list:
        violations.append("ARTIFACT_BUNDLE_EMPTY")
    elif len(ab) == 0:
        violations.append("ARTIFACT_BUNDLE_EMPTY")
    else:
        seen_paths: set[str] = set()
        roles_present: set[str] = set()
        for idx, aitem in enumerate(ab):
            if type(aitem) is not dict:
                violations.append(f"ARTIFACT_{idx}_SCHEMA")
                continue
            if set(aitem.keys()) != ALLOWED_ARTIFACT_KEYS:
                violations.append(f"ARTIFACT_{idx}_SCHEMA")
                continue
            rp = aitem["relpath"]
            if not _is_safe_relpath(rp):
                violations.append(f"ARTIFACT_{idx}_UNSAFE_OR_DUP_RELPATH")
            elif rp in seen_paths:
                violations.append(f"ARTIFACT_{idx}_UNSAFE_OR_DUP_RELPATH")
            else:
                seen_paths.add(rp)
            if not _is_hex64(aitem["sha256"]):
                violations.append(f"ARTIFACT_{idx}_BAD_SHA256")
            role = aitem["role"]
            if not _in_str_set(role, ALLOWED_ARTIFACT_ROLES):
                violations.append(f"ARTIFACT_{idx}_BAD_ROLE")
            else:
                roles_present.add(role)
        if "code" not in roles_present:
            violations.append("ARTIFACT_BUNDLE_REQUIRES_CODE_AND_TEST")
        elif "test" not in roles_present:
            violations.append("ARTIFACT_BUNDLE_REQUIRES_CODE_AND_TEST")

    env_sha = canonical_sha256(envelope) if len(violations) == 0 else None
    return {
        "passed": len(violations) == 0,
        "envelope_sha256": env_sha,
        "violation_count": len(violations),
        "violations": violations,
    }


def certify_two_zone_airlock(spec: dict[str, Any]) -> dict[str, Any]:
    """Certify end-to-end Zone A -> Airlock -> Zone B isolation & ClaimLedger verdict binding."""
    violations: list[str] = []
    if type(spec) is not dict:
        return {"passed": False, "envelope_sha256": None, "violation_count": 1, "violations": ["INVALID_TWO_ZONE_SPEC_OR_FLOAT"]}
    if contains_forbidden_non_exact(spec):
        return {"passed": False, "envelope_sha256": None, "violation_count": 1, "violations": ["INVALID_TWO_ZONE_SPEC_OR_FLOAT"]}
    if set(spec.keys()) != {"zone_a", "airlock_envelope", "zone_b", "verdict_packet"}:
        return {"passed": False, "envelope_sha256": None, "violation_count": 1, "violations": ["UNEXPECTED_TWO_ZONE_KEYS"]}

    za = spec["zone_a"]
    env = spec["airlock_envelope"]
    zb = spec["zone_b"]
    vp = spec["verdict_packet"]

    za_participants: set[str] = set()
    if type(za) is not dict:
        violations.append("ZONE_A_SCHEMA_MISMATCH")
    elif set(za.keys()) != ALLOWED_ZONE_A_KEYS:
        violations.append("ZONE_A_SCHEMA_MISMATCH")
    else:
        if za["mode"] != "socratic":
            violations.append("ZONE_A_MUST_BE_SOCRATIC")
        if za["conductor"] is not None:
            violations.append("ZONE_A_SOCRATIC_MUST_HAVE_NO_CONDUCTOR")
        parts = za["participants"]
        bad_parts = type(parts) is not list
        if not bad_parts:
            if len(parts) < 2:
                bad_parts = True
            elif any(not _is_valid_id(p) for p in parts):
                bad_parts = True
            elif len({p.lower() for p in parts}) != len(parts):
                bad_parts = True
        if bad_parts:
            violations.append("ZONE_A_REQUIRES_AT_LEAST_2_UNIQUE_PARTICIPANTS")
        else:
            za_participants = {p.lower() for p in parts}
        if za["round_robin_enforced"] is not False:
            violations.append("ZONE_A_S03_ROUND_ROBIN_FORBIDDEN")
        if za["silent_turns_allowed"] is not True:
            violations.append("ZONE_A_G08_SILENCE_MUST_BE_VALID")
        if not _is_strict_int(za["silent_turns_observed"]):
            violations.append("ZONE_A_INVALID_SILENT_TURNS")
        elif za["silent_turns_observed"] < 0:
            violations.append("ZONE_A_INVALID_SILENT_TURNS")
        if not _is_strict_int(za["distinct_hypotheses_count"]):
            violations.append("ZONE_A_HOMOGENIZED_SINGLE_HYPOTHESIS")
        elif za["distinct_hypotheses_count"] < 2:
            violations.append("ZONE_A_HOMOGENIZED_SINGLE_HYPOTHESIS")
        if za["output_tag"] != "UNVERIFIED_HYPOTHESIS":
            violations.append("ZONE_A_MUST_TAG_OUTPUT_UNVERIFIED_HYPOTHESIS")
        if za["agreement_counted_as_evidence"] is not False:
            violations.append("ZONE_A_AGREEMENT_CANNOT_BE_EVIDENCE")

    env_res = validate_airlock_envelope(env)
    if not env_res["passed"]:
        for v in env_res["violations"]:
            violations.append(f"AIRLOCK:{v}")
    env_sha = env_res["envelope_sha256"]

    zb_seat: str | None = None
    if type(zb) is not dict:
        violations.append("ZONE_B_SCHEMA_MISMATCH")
    elif set(zb.keys()) != ALLOWED_ZONE_B_KEYS:
        violations.append("ZONE_B_SCHEMA_MISMATCH")
    else:
        if zb["channel_mode"] != "private_c02":
            violations.append("ZONE_B_MUST_USE_PRIVATE_C02_CHANNEL")
        seat = zb["verifier_seat"]
        if not _is_valid_id(seat):
            violations.append("ZONE_B_INVALID_VERIFIER_SEAT")
        else:
            zb_seat = seat
            if seat.lower() in za_participants:
                violations.append("ZONE_B_R3_VERIFIER_IN_ZONE_A_PARTICIPANTS")
        env_id = env.get("envelope_id") if type(env) is dict else None
        if zb["read_scope"] != [env_id]:
            violations.append("ZONE_B_M05_READ_SCOPE_EXCEEDS_STRIPPED_ENVELOPE")
        bchan = zb["blocked_channels"]
        if type(bchan) is not list:
            violations.append("ZONE_B_INVALID_BLOCKED_CHANNELS")
        elif any(not _is_nonempty_str(c) for c in bchan):
            violations.append("ZONE_B_INVALID_BLOCKED_CHANNELS")
        elif not ZONE_B_REQUIRED_BLOCKED_CHANNELS.issubset(set(bchan)):
            violations.append("ZONE_B_M05_MISSING_REQUIRED_BLOCKED_CHANNELS")
        if zb["can_read_zone_a_board"] is not False:
            violations.append("ZONE_B_M05_BOARD_VISIBILITY_LEAK")
        if zb["can_approve_own_changes"] is not False:
            violations.append("ZONE_B_C05_SELF_APPROVAL_FORBIDDEN")
        if zb["write_scopes"] != []:
            violations.append("ZONE_B_I15_VERIFIER_MUST_BE_READ_ONLY")

    if type(vp) is not dict:
        violations.append("VERDICT_PACKET_SCHEMA_MISMATCH")
    elif set(vp.keys()) != ALLOWED_VERDICT_KEYS:
        violations.append("VERDICT_PACKET_SCHEMA_MISMATCH")
    else:
        if vp["schema"] != AIRLOCK_VERDICT_SCHEMA:
            violations.append("VERDICT_INVALID_SCHEMA")
        if type(env) is dict:
            if vp["envelope_id"] != env.get("envelope_id"):
                violations.append("VERDICT_ENVELOPE_ID_MISMATCH")
        if env_sha is not None:
            if vp["envelope_sha256"] != env_sha:
                violations.append("VERDICT_ENVELOPE_SHA256_MISMATCH")
        if zb_seat is not None:
            if vp["verifier_seat"] != zb_seat:
                violations.append("VERDICT_SEAT_MISMATCH")
        pev = vp["part_e_verdict"]
        pig = vp["part_i_grade"]
        if not _in_str_set(pev, ALLOWED_PART_E_VERDICTS):
            violations.append("VERDICT_INVALID_PART_E")
        if not _in_str_set(pig, ALLOWED_PART_I_GRADES):
            violations.append("VERDICT_INVALID_PART_I_GRADE")

        cl_obj = env.get("claim_ledger") if type(env) is dict else None
        if type(cl_obj) is not dict:
            cl_obj = None
        raw_grammar = cl_obj.get("finite_outcome_grammar") if cl_obj is not None else None
        grammar = raw_grammar if type(raw_grammar) is dict else {}
        om = vp["outcome_matched"]
        if om not in grammar:
            violations.append("VERDICT_OUTCOME_NOT_IN_DECLARED_GRAMMAR")
        elif type(om) is str:
            pol = grammar[om]
            if pev == "VERIFIED" and pol != "supports":
                violations.append("VERDICT_OUTCOME_CONTRADICTS_PART_E")
            elif pev in ("PARTIAL_FRAGILE", "FALSIFIED", "NOT_SHOWN") and pol == "supports":
                violations.append("VERDICT_OUTCOME_CONTRADICTS_PART_E")

        cl_ceil = cl_obj.get("linguistic_ceiling") if cl_obj is not None else None
        if type(pig) is str:
            if pig in EVIDENCE_GRADE_RANK:
                if type(cl_ceil) is str:
                    if cl_ceil in EVIDENCE_GRADE_RANK:
                        if EVIDENCE_GRADE_RANK[pig] > EVIDENCE_GRADE_RANK[cl_ceil]:
                            violations.append("VERDICT_PART_I_EXCEEDS_LINGUISTIC_CEILING")
                if pev in ("PARTIAL_FRAGILE", "FALSIFIED", "NOT_SHOWN"):
                    if EVIDENCE_GRADE_RANK[pig] > 0:
                        violations.append("VERDICT_ADVERSE_CANNOT_CLAIM_ELEVATED_PART_I_GRADE")

        r5k = vp["r5_killed"]
        r5t = vp["r5_total"]
        bad_r5 = not _is_strict_int(r5k)
        if not bad_r5:
            if not _is_strict_int(r5t):
                bad_r5 = True
            elif r5t < 1:
                bad_r5 = True
            elif r5k < 0:
                bad_r5 = True
            elif r5k > r5t:
                bad_r5 = True
        if bad_r5:
            violations.append("VERDICT_INVALID_R5_COUNTS")
        elif pev == "VERIFIED":
            if r5k != r5t:
                violations.append("VERDICT_VERIFIED_WITH_R5_SURVIVORS")
            elif r5t < MIN_R5_TOTAL_FOR_VERIFIED:
                violations.append("VERDICT_VERIFIED_R5_FLOOR")

        cex = vp["counterexample"]
        if pev == "VERIFIED":
            if cex is not None:
                violations.append("VERDICT_VERIFIED_MUST_HAVE_NULL_COUNTEREXAMPLE")
        else:
            if not _is_clean_ascii_text(cex):
                violations.append("VERDICT_ADVERSE_REQUIRES_MINIMAL_COUNTEREXAMPLE")

    return {
        "passed": len(violations) == 0,
        "envelope_sha256": env_sha,
        "violation_count": len(violations),
        "violations": violations,
    }


def verify_observational_non_interference(
    zone_a_room_1: dict[str, Any],
    zone_a_room_2: dict[str, Any],
) -> dict[str, Any]:
    """Certify M03/M05 observational non-interference across distinct Zone-A social rooms."""
    if type(zone_a_room_1) is not dict:
        raise AletheiaError("INVALID_NON_INTERFERENCE_INPUTS", "zone_a_room_1 must be dict")
    if type(zone_a_room_2) is not dict:
        raise AletheiaError("INVALID_NON_INTERFERENCE_INPUTS", "zone_a_room_2 must be dict")
    if contains_forbidden_non_exact(zone_a_room_1):
        raise AletheiaError("FLOAT_FORBIDDEN_IN_NON_INTERFERENCE_INPUTS", "float forbidden in room 1")
    if contains_forbidden_non_exact(zone_a_room_2):
        raise AletheiaError("FLOAT_FORBIDDEN_IN_NON_INTERFERENCE_INPUTS", "float forbidden in room 2")

    social_fields = ("transcript", "authors", "models", "agreement_count")
    for k in social_fields:
        if k not in zone_a_room_1:
            raise AletheiaError("MISSING_SOCIAL_METADATA", f"room 1 missing social field {k!r}")
        if k not in zone_a_room_2:
            raise AletheiaError("MISSING_SOCIAL_METADATA", f"room 2 missing social field {k!r}")
        if zone_a_room_1[k] == zone_a_room_2[k]:
            raise AletheiaError("SOCIAL_METADATA_MUST_DIFFER", f"social field {k!r} must differ across rooms")

    env1 = strip_zone_a_to_airlock_envelope(zone_a_room_1)
    env2 = strip_zone_a_to_airlock_envelope(zone_a_room_2)
    v1 = validate_airlock_envelope(env1)
    v2 = validate_airlock_envelope(env2)
    b1 = canonical_json_bytes(env1)
    b2 = canonical_json_bytes(env2)
    passed = v1["passed"] and b1 == b2
    return {
        "passed": passed,
        "envelope_1_valid": v1["passed"],
        "envelope_2_valid": v2["passed"],
        "envelopes_byte_identical": b1 == b2,
        "envelope_sha256": hashlib.sha256(b1).hexdigest() if passed else None,
    }


# ---------------------------------------------------------------------------
# 3. Erlang/OTP Supervision Tree Semantics & exo#1200 Bridge (AUDIT-110R)
# ---------------------------------------------------------------------------

def otp_should_restart(policy: str, exit_reason: str) -> dict[str, Any]:
    """Exact Erlang/OTP 3x3 restart predicate over policy x exit_reason."""
    if not _in_str_set(policy, RESTART_POLICIES):
        raise AletheiaError("ERR_INVALID_POLICY", f"unknown restart policy {policy!r}")
    if not _in_str_set(exit_reason, EXIT_REASONS):
        raise AletheiaError("ERR_INVALID_EXIT_REASON", f"unknown exit_reason {exit_reason!r}")

    if policy == "permanent":
        restart = True
    elif policy == "transient":
        restart = exit_reason == "abnormal"
    else:
        restart = False
    return {
        "policy": policy,
        "exit_reason": exit_reason,
        "should_restart": restart,
        "action": "restart" if restart else "drop_child",
    }


def _should_strategy_restart(child_policy: str, is_crashed: bool, was_alive: bool) -> bool:
    if child_policy == "temporary":
        return False
    return is_crashed or was_alive


def _validate_otp_children(children: Any) -> list[dict[str, Any]]:
    if type(children) is not list:
        raise AletheiaError("ERR_INVALID_CHILDREN", "children must be non-empty list")
    if len(children) == 0:
        raise AletheiaError("ERR_INVALID_CHILDREN", "children must be non-empty list")
    seen: set[str] = set()
    state: list[dict[str, Any]] = []
    for idx, ch in enumerate(children):
        if type(ch) is not dict:
            raise AletheiaError("ERR_SCHEMA_KEYS", f"child[{idx}] must be dict")
        if set(ch.keys()) != OTP_CHILD_KEYS:
            raise AletheiaError("ERR_SCHEMA_KEYS", f"child[{idx}] keyset mismatch")
        cid = ch["id"]
        if not _is_valid_id(cid):
            raise AletheiaError("ERR_INVALID_CHILD_ID", f"invalid child id {cid!r}")
        if cid in seen:
            raise AletheiaError("ERR_INVALID_CHILD_ID", f"duplicate child id {cid!r}")
        seen.add(cid)
        if not _in_str_set(ch["policy"], RESTART_POLICIES):
            raise AletheiaError("ERR_INVALID_POLICY", f"bad policy on {cid}")
        if not _is_strict_int(ch["generation"]):
            raise AletheiaError("ERR_SCHEMA_INT", f"child[{idx}].generation must be int >= 1")
        if ch["generation"] < 1:
            raise AletheiaError("ERR_SCHEMA_INT", f"child[{idx}].generation must be int >= 1")
        if not _is_hex64(ch["snapshot_sha256"]):
            raise AletheiaError("ERR_INVALID_SHA256", f"child[{idx}].snapshot_sha256 invalid")
        if type(ch["alive"]) is not bool:
            raise AletheiaError("ERR_INVALID_ALIVE", f"child[{idx}].alive must be bool")
        if ch["policy"] == "permanent" and not ch["alive"]:
            raise AletheiaError("ERR_DEAD_PERMANENT_CHILD", f"permanent child {cid!r} cannot be dead")
        state.append(copy.deepcopy(ch))
    return state


def apply_otp_strategy_crash(
    strategy: str,
    children: list[dict[str, Any]],
    crashed_id: str,
    exit_reason: str,
    new_snapshot_sha256: str | None = None,
) -> dict[str, Any]:
    """Exact OTP one_for_one / one_for_all / rest_for_one transition preserving non-resurrection."""
    if not _in_str_set(strategy, RESTART_STRATEGIES):
        raise AletheiaError("ERR_INVALID_STRATEGY", f"unknown strategy {strategy!r}")
    if new_snapshot_sha256 is not None:
        if not _is_hex64(new_snapshot_sha256):
            raise AletheiaError("ERR_INVALID_SHA256", "new_snapshot_sha256 must be non-uniform 64-hex")
    state = _validate_otp_children(children)

    idx_map = {c["id"]: i for i, c in enumerate(state)}
    if not _in_str_set(crashed_id, idx_map):
        raise AletheiaError("ERR_UNKNOWN_CHILD", f"unknown child {crashed_id!r}")
    idx = idx_map[crashed_id]
    if not state[idx]["alive"]:
        raise AletheiaError("ERR_CHILD_ALREADY_DEAD", f"child {crashed_id!r} already dead")

    decision = otp_should_restart(state[idx]["policy"], exit_reason)
    state[idx]["alive"] = False
    terminated_order: list[str] = []
    restarted_order: list[str] = []

    if decision["should_restart"]:
        was_alive = [c["alive"] for c in state]
        if strategy == "one_for_one":
            terminate_indices: list[int] = []
            candidate_restart = [idx]
        elif strategy == "one_for_all":
            terminate_indices = [i for i in range(len(state) - 1, -1, -1) if state[i]["alive"]]
            candidate_restart = list(range(len(state)))
        else:
            terminate_indices = [i for i in range(len(state) - 1, idx, -1) if state[i]["alive"]]
            candidate_restart = list(range(idx, len(state)))

        restart_indices = [
            i for i in candidate_restart
            if _should_strategy_restart(state[i]["policy"], i == idx, was_alive[i])
        ]
        for ti in terminate_indices:
            state[ti]["alive"] = False
            terminated_order.append(state[ti]["id"])
        for ri in restart_indices:
            state[ri]["alive"] = True
            state[ri]["generation"] += 1
            if new_snapshot_sha256 is not None:
                state[ri]["snapshot_sha256"] = new_snapshot_sha256
            restarted_order.append(state[ri]["id"])

    return {
        "strategy": strategy,
        "crashed_id": crashed_id,
        "exit_reason": exit_reason,
        "restarted": decision["should_restart"],
        "terminated_order": terminated_order,
        "restarted_order": restarted_order,
        "children_after": state,
    }


def verify_snapshot_non_churn(
    children_after: list[dict[str, Any]],
    author_id: str,
    downstream_ids: list[str],
    strategy: str | None = None,
) -> dict[str, Any]:
    """Certify that every alive downstream child matches author's immutable snapshot_sha256.

    For strategy == "rest_for_one" the downstream set is DETERMINED by child order
    (children after the author), so it is derived, not trusted from the caller."""
    validated = _validate_otp_children(children_after)
    if strategy == "rest_for_one":
        ids = [ch["id"] for ch in validated]
        aidx = ids.index(author_id) if author_id in ids else -1
        if aidx >= 0:
            downstream_ids = ids[aidx + 1:]
    if type(downstream_ids) is not list:
        raise AletheiaError("ERR_INVALID_DOWNSTREAM", "downstream_ids must be non-empty list")
    if len(downstream_ids) == 0:
        raise AletheiaError("ERR_INVALID_DOWNSTREAM", "downstream_ids must be non-empty list")
    by_id: dict[str, dict[str, Any]] = {ch["id"]: ch for ch in validated}
    if not _in_str_set(author_id, by_id):
        raise AletheiaError("ERR_UNKNOWN_AUTHOR", f"author {author_id!r} not in children_after")
    if not by_id[author_id]["alive"]:
        raise AletheiaError("ERR_AUTHOR_NOT_ALIVE", f"author {author_id!r} must be alive")
    author_sha = by_id[author_id]["snapshot_sha256"]
    seen_down: set[str] = set()
    stale: list[str] = []
    for did in downstream_ids:
        if not _in_str_set(did, by_id):
            raise AletheiaError("ERR_UNKNOWN_DOWNSTREAM", f"downstream {did!r} not in children_after")
        if did == author_id:
            raise AletheiaError("ERR_INVALID_DOWNSTREAM", f"author {author_id!r} cannot be downstream of itself")
        if did in seen_down:
            raise AletheiaError("ERR_INVALID_DOWNSTREAM", f"duplicate downstream id {did!r}")
        seen_down.add(did)
        ch = by_id[did]
        if ch["alive"]:
            if ch["snapshot_sha256"] != author_sha:
                stale.append(did)
    passed = len(stale) == 0
    return {
        "passed": passed,
        "error_code": None if passed else "ERR_SNAPSHOT_CHURN",
        "author_snapshot_sha256": author_sha,
        "stale_downstream_ids": stale,
        "stale_downstream_count": len(stale),
    }


def certify_restart_intensity_trace(
    max_restarts: int,
    window_ticks: int | Fraction | str,
    crash_ticks: list[int | Fraction | str],
) -> dict[str, Any]:
    """Pure-Z/Q inclusive sliding-window restart intensity trace (OTP supervisor.erl semantics).

    Rejects backward timestamps (ERR_NON_MONOTONIC_TICK) and trailing crashes after escalation
    (ERR_EVENT_AFTER_ESCALATION).
    """
    if not _is_strict_int(max_restarts):
        raise AletheiaError("ERR_INVALID_MAX_RESTARTS", "max_restarts must be int >= 0")
    if max_restarts < 0:
        raise AletheiaError("ERR_INVALID_MAX_RESTARTS", "max_restarts must be int >= 0")
    window = parse_nonneg_fraction(window_ticks, "window_ticks")
    if window == 0:
        raise AletheiaError("ERR_ZERO_WINDOW", "window_ticks must be > 0")
    if type(crash_ticks) is not list:
        raise AletheiaError("ERR_INVALID_CRASH_TICKS", "crash_ticks must be non-empty list")
    if len(crash_ticks) == 0:
        raise AletheiaError("ERR_INVALID_CRASH_TICKS", "crash_ticks must be non-empty list")

    active: list[Fraction] = []
    prev_t: Fraction | None = None
    escalated = False
    escalated_at: str | None = None
    steps: list[dict[str, Any]] = []

    for idx, raw_t in enumerate(crash_ticks):
        if escalated:
            raise AletheiaError("ERR_EVENT_AFTER_ESCALATION", f"trailing crash at step {idx} after escalation")
        now = parse_nonneg_fraction(raw_t, f"crash_ticks[{idx}]")
        if prev_t is not None:
            if now < prev_t:
                raise AletheiaError("ERR_NON_MONOTONIC_TICK", f"step {idx}: {frac_str(now)} < {frac_str(prev_t)}")
        prev_t = now
        cutoff = now - window
        kept = [t for t in active if t >= cutoff]
        evicted_count = len(active) - len(kept)
        kept.append(now)
        active = kept
        if len(active) > max_restarts:
            escalated = True
            escalated_at = frac_str(now)
            decision = "MAX_RESTART_INTENSITY_EXCEEDED"
        else:
            decision = "RESTART_ALLOWED"
        steps.append({
            "step": idx,
            "tick": frac_str(now),
            "evicted_count": evicted_count,
            "active_count": len(active),
            "decision": decision,
        })

    return {
        "max_restarts": max_restarts,
        "window_ticks": frac_str(window),
        "escalated": escalated,
        "escalated_at": escalated_at,
        "steps": steps,
    }


def certify_monitor_vs_link_isolation(topology: str, exit_reason: str) -> dict[str, Any]:
    """BFS signal-propagation certifier proving unidirectional monitor > link + trap_exit."""
    if not _in_str_set(topology, SIGNAL_TOPOLOGIES):
        raise AletheiaError("ERR_INVALID_TOPOLOGY", f"unknown topology {topology!r}")
    if not _in_str_set(exit_reason, SIGNAL_EXIT_REASONS):
        raise AletheiaError("ERR_INVALID_EXIT_REASON", f"unknown signal exit_reason {exit_reason!r}")

    procs: dict[str, dict[str, Any]] = {
        "coordinator": {"alive": True, "trap_exit": topology == "link_trap_exit", "inbox": []},
        "verifier_1": {"alive": True, "trap_exit": False, "inbox": []},
        "verifier_2": {"alive": True, "trap_exit": False, "inbox": []},
    }
    links: dict[str, list[str]] = {p: [] for p in procs}
    monitors: dict[str, list[tuple[str, str]]] = {p: [] for p in procs}

    if topology == "monitor":
        monitors["verifier_1"].append(("coordinator", "mon-v1"))
        monitors["verifier_2"].append(("coordinator", "mon-v2"))
    else:
        links["coordinator"].extend(["verifier_1", "verifier_2"])
        links["verifier_1"].append("coordinator")
        links["verifier_2"].append("coordinator")

    procs["verifier_1"]["alive"] = False
    queue: deque[tuple[str, str]] = deque([("verifier_1", exit_reason)])
    collateral_kills: list[str] = []

    while queue:
        dead_pid, reason = queue.popleft()
        for watcher, ref in monitors[dead_pid]:
            if procs[watcher]["alive"]:
                procs[watcher]["inbox"].append({"type": "DOWN", "ref": ref, "pid": dead_pid, "reason": reason})
        for peer in links[dead_pid]:
            if not procs[peer]["alive"]:
                continue
            if reason == "kill":
                procs[peer]["alive"] = False
                collateral_kills.append(peer)
                queue.append((peer, "killed"))
            elif procs[peer]["trap_exit"]:
                procs[peer]["inbox"].append({"type": "EXIT", "from": dead_pid, "reason": reason})
            elif reason != "normal":
                procs[peer]["alive"] = False
                collateral_kills.append(peer)
                queue.append((peer, reason))

    coord_alive = procs["coordinator"]["alive"]
    v2_alive = procs["verifier_2"]["alive"]
    isolated = len(collateral_kills) == 0
    return {
        "topology": topology,
        "exit_reason": exit_reason,
        "isolated": isolated,
        "error_code": None if isolated else "ERR_COORDINATOR_COLLATERAL_KILL",
        "coordinator_alive": coord_alive,
        "verifier_2_alive": v2_alive,
        "collateral_kills": collateral_kills,
        "coordinator_inbox": procs["coordinator"]["inbox"],
    }


def decide_hybrid_supervision(
    *,
    task_state: str,
    failure_class: str,
    effect_class: str,
    attempt_number: int,
    max_retries: int,
    stop_requested: bool,
    otp_policy: str,
    exit_reason: str,
) -> dict[str, Any]:
    """Compose exo#1200 safety gates (dominant) with OTP child restart policy."""
    if not _in_str_set(task_state, EXO1200_TASK_STATES):
        raise AletheiaError("ERR_INVALID_TASK_STATE", f"unknown task_state {task_state!r}")
    if not _in_str_set(failure_class, EXO1200_FAILURE_CLASSES):
        raise AletheiaError("ERR_INVALID_FAILURE_CLASS", f"unknown failure_class {failure_class!r}")
    if not _in_str_set(effect_class, EXO1200_EFFECT_CLASSES):
        raise AletheiaError("ERR_INVALID_EFFECT_CLASS", f"unknown effect_class {effect_class!r}")
    if not _is_strict_int(attempt_number):
        raise AletheiaError("ERR_INVALID_ATTEMPT", "attempt_number must be int >= 1")
    if attempt_number < 1:
        raise AletheiaError("ERR_INVALID_ATTEMPT", "attempt_number must be int >= 1")
    if not _is_strict_int(max_retries):
        raise AletheiaError("ERR_INVALID_MAX_RETRIES", "max_retries must be int in 0..10")
    if max_retries < 0:
        raise AletheiaError("ERR_INVALID_MAX_RETRIES", "max_retries must be int in 0..10")
    if max_retries > 10:
        raise AletheiaError("ERR_INVALID_MAX_RETRIES", "max_retries must be int in 0..10")
    if type(stop_requested) is not bool:
        raise AletheiaError("ERR_INVALID_STOP_FLAG", "stop_requested must be bool")

    otp_dec = otp_should_restart(otp_policy, exit_reason)
    uncertain_effects = effect_class != "not_dispatched"

    if stop_requested:
        return {"action": "final", "reason": "cancelled", "reconcile": uncertain_effects, "otp_should_restart": otp_dec["should_restart"]}
    if task_state in ("stopped", "cancelled"):
        return {"action": "final", "reason": "cancelled", "reconcile": uncertain_effects, "otp_should_restart": otp_dec["should_restart"]}
    if failure_class in ("cancelled", "denied", "spend_limit", "permanent"):
        return {"action": "final", "reason": failure_class, "reconcile": uncertain_effects, "otp_should_restart": otp_dec["should_restart"]}
    if task_state == "completed":
        return {"action": "final", "reason": "completed", "reconcile": False, "otp_should_restart": otp_dec["should_restart"]}
    if task_state != "failed":
        return {"action": "reconcile", "reason": "not_settled_failure", "reconcile": True, "otp_should_restart": otp_dec["should_restart"]}
    if uncertain_effects:
        return {"action": "reconcile", "reason": "effects_require_reconciliation", "reconcile": True, "otp_should_restart": otp_dec["should_restart"]}
    if failure_class != "transient":
        return {"action": "reconcile", "reason": "failure_requires_classification", "reconcile": True, "otp_should_restart": otp_dec["should_restart"]}
    if attempt_number > max_retries:
        return {"action": "final", "reason": "retry_budget_exhausted", "reconcile": False, "otp_should_restart": otp_dec["should_restart"]}
    if not otp_dec["should_restart"]:
        return {"action": "final", "reason": "otp_policy_drop_child", "reconcile": False, "otp_should_restart": False}
    return {"action": "retry", "reason": "transient_pre_dispatch_otp_restart", "reconcile": False, "otp_should_restart": True}


# ---------------------------------------------------------------------------
# 4. Deterministic Dynamic Self-Test (Accept + Must-Fail Controls)
# ---------------------------------------------------------------------------

def _run_expected_rejection(fn: Callable[[], Any], expected_code: str) -> dict[str, Any]:
    try:
        fn()
    except AletheiaError as exc:
        return {
            "rejected": exc.code == expected_code,
            "code": exc.code,
            "expected_code": expected_code,
        }
    return {"rejected": False, "code": None, "expected_code": expected_code}


def run_v21_proposals_self_test() -> dict[str, Any]:
    """Dynamically verify accept + must-fail controls across Law 1b, Airlock, and OTP."""
    sha_a = hashlib.sha256(b"aletheia-v21-fixture-a").hexdigest()
    sha_b = hashlib.sha256(b"aletheia-v21-fixture-b").hexdigest()
    sha_c = hashlib.sha256(b"aletheia-v21-fixture-c").hexdigest()
    head_1 = hashlib.sha1(b"head-1").hexdigest()
    head_2 = hashlib.sha1(b"head-2").hexdigest()

    # 1. Law 1b accept + blind-spot rejection
    law1b_spec = {
        "schema": LAW1B_SCHEMA,
        "external_writes": 0,
        "repos_scanned": [
            {"repo": "Foundation-0/math0", "fetched": 20, "open": 10, "closed_unmerged": 1, "merged": 9, "prs_json_sha256": sha_a},
        ],
        "mined_entries": [
            {
                "repo": "Foundation-0/math0", "number": 3, "status": "open",
                "head_sha": head_1, "snapshot_sha256": sha_b,
                "mechanism_class": "EXACT_CERTIFIER_OR_DOMAIN_TOOL",
                "evidence_standing": "EXECUTED_EXACT_WITNESS", "honest_novelty": "N0",
                "operator_summary": "Pure-stdlib finite-field minimum-distance witness",
            },
            {
                "repo": "Foundation-0/math0", "number": 11, "status": "closed_unmerged",
                "head_sha": head_2, "snapshot_sha256": sha_c,
                "mechanism_class": "QUANTILE_OR_INDEX_BOUNDARY",
                "evidence_standing": "CATALOGED_LEAD", "honest_novelty": "N0",
                "operator_summary": "Closed-unmerged boundary candidate cataloged at N0",
            },
        ],
    }
    l1b_ok = certify_law1b_serendipity_mining(law1b_spec)
    l1b_blind = copy.deepcopy(law1b_spec)
    l1b_blind["mined_entries"] = [l1b_blind["mined_entries"][0]]
    l1b_rej = _run_expected_rejection(
        lambda: certify_law1b_serendipity_mining(l1b_blind),
        "L1B_CLOSED_UNMERGED_BLIND_SPOT",
    )

    # 2. Airlock + ClaimLedger + Observational Non-Interference + leaky rejection
    base_tech = {
        "envelope_id": "env-v21-001",
        "claim_ledger": {
            "claim_id": "claim-v21-001",
            "finite_outcome_grammar": {"SUPPORTED": "supports", "REFUTED": "against", "INCONCLUSIVE": "inconclusive"},
            "falsifier_predicate": "residual_sq_norm != 0/1",
            "novelty_default": "N0",
            "linguistic_ceiling": "E2_SEALED",
        },
        "pinned_inputs": {
            "files": [{"id": "dataset-a", "sha256": sha_a, "bytes": 1024}],
            "seeds": [42, 99],
        },
        "artifact_bundle": [
            {"relpath": "src/oracle.py", "sha256": sha_b, "role": "code"},
            {"relpath": "tests/test_r5.py", "sha256": sha_c, "role": "test"},
        ],
    }
    room_1 = dict(base_tech, transcript="unanimous praise", authors=["alice"], models=["m-a"], agreement_count=2)
    room_2 = dict(base_tech, transcript="sharp dissent", authors=["bob"], models=["m-b"], agreement_count=0)
    ni_res = verify_observational_non_interference(room_1, room_2)
    env_clean = strip_zone_a_to_airlock_envelope(room_1)
    env_sha = canonical_sha256(env_clean)
    tz_spec = {
        "zone_a": {
            "mode": "socratic", "conductor": None, "participants": ["alice", "bob"],
            "round_robin_enforced": False, "silent_turns_allowed": True,
            "silent_turns_observed": 1, "distinct_hypotheses_count": 2,
            "output_tag": "UNVERIFIED_HYPOTHESIS", "agreement_counted_as_evidence": False,
        },
        "airlock_envelope": env_clean,
        "zone_b": {
            "channel_mode": "private_c02", "verifier_seat": "blind-verifier-1",
            "read_scope": ["env-v21-001"],
            "blocked_channels": sorted(ZONE_B_REQUIRED_BLOCKED_CHANNELS),
            "can_read_zone_a_board": False, "can_approve_own_changes": False,
            "write_scopes": [],
        },
        "verdict_packet": {
            "schema": AIRLOCK_VERDICT_SCHEMA, "envelope_id": "env-v21-001",
            "envelope_sha256": env_sha, "verifier_seat": "blind-verifier-1",
            "part_e_verdict": "VERIFIED", "part_i_grade": "E2_SEALED",
            "outcome_matched": "SUPPORTED", "r5_killed": 12, "r5_total": 12,
            "counterexample": None,
        },
    }
    tz_ok = certify_two_zone_airlock(tz_spec)
    tz_bad = copy.deepcopy(tz_spec)
    tz_bad["zone_b"]["verifier_seat"] = "ALICE"
    tz_bad["verdict_packet"]["verifier_seat"] = "ALICE"
    tz_rej = certify_two_zone_airlock(tz_bad)

    # 3. Erlang/OTP Frozen-Snapshot rest_for_one vs one_for_one, pure-Q 1/3 intensity, monitor vs link+kill, exo#1200
    snap_v1 = sha_a
    snap_v2 = sha_b
    pipe = [
        {"id": "planner", "policy": "permanent", "generation": 1, "snapshot_sha256": snap_v1, "alive": True},
        {"id": "author", "policy": "transient", "generation": 1, "snapshot_sha256": snap_v1, "alive": True},
        {"id": "airlock", "policy": "permanent", "generation": 1, "snapshot_sha256": snap_v1, "alive": True},
        {"id": "verifier", "policy": "transient", "generation": 1, "snapshot_sha256": snap_v1, "alive": True},
    ]
    rfo = apply_otp_strategy_crash("rest_for_one", pipe, "author", "abnormal", snap_v2)
    rfo_nc = verify_snapshot_non_churn(rfo["children_after"], "author", ["airlock", "verifier"])
    ofo = apply_otp_strategy_crash("one_for_one", pipe, "author", "abnormal", snap_v2)
    ofo_nc = verify_snapshot_non_churn(ofo["children_after"], "author", ["airlock", "verifier"])
    intensity_q = certify_restart_intensity_trace(2, "1/3", ["0/1", "1/3", "2/3", "5/6", "1/1"])
    mon_ok = certify_monitor_vs_link_isolation("monitor", "kill")
    link_fail = certify_monitor_vs_link_isolation("link_trap_exit", "kill")
    exo_stop = decide_hybrid_supervision(
        task_state="failed", failure_class="transient", effect_class="not_dispatched",
        attempt_number=1, max_retries=3, stop_requested=True,
        otp_policy="transient", exit_reason="abnormal",
    )

    checks = {
        "law1b_accept": l1b_ok["certified"] is True and l1b_ok["unmerged_share"] == "11/20",
        "law1b_reject_blind_spot": l1b_rej["rejected"] is True,
        "airlock_non_interference": ni_res["passed"] is True,
        "airlock_accept": tz_ok["passed"] is True,
        "airlock_reject_self_verify": tz_rej["passed"] is False and "ZONE_B_R3_VERIFIER_IN_ZONE_A_PARTICIPANTS" in tz_rej["violations"],
        "otp_rest_for_one_non_churn": rfo_nc["passed"] is True and rfo["children_after"][0]["generation"] == 1,
        "otp_one_for_one_churn_detected": ofo_nc["passed"] is False and ofo_nc["error_code"] == "ERR_SNAPSHOT_CHURN",
        "otp_rational_intensity_escalated": intensity_q["escalated"] is True and intensity_q["escalated_at"] == "1/1",
        "otp_monitor_isolates_kill": mon_ok["isolated"] is True,
        "otp_link_trap_exit_fails_kill": link_fail["isolated"] is False and link_fail["error_code"] == "ERR_COORDINATOR_COLLATERAL_KILL",
        "exo1200_sticky_stop_dominates": exo_stop["action"] == "final" and exo_stop["reason"] == "cancelled",
    }
    passed = all(checks.values())
    out: dict[str, Any] = {
        "schema": SELFTEST_SCHEMA,
        "passed": passed,
        "verdict": "ALETHEIA_V21_PROPOSALS_VERIFIED" if passed else "ALETHEIA_V21_PROPOSALS_FAILED",
        "checks": checks,
        "law1b": l1b_ok,
        "law1b_rejection": l1b_rej,
        "non_interference": ni_res,
        "two_zone_ok": tz_ok,
        "otp_rest_for_one_non_churn": rfo_nc,
        "otp_one_for_one_churn": ofo_nc,
        "otp_intensity_q": intensity_q,
        "otp_monitor_kill": mon_ok,
        "otp_link_trap_kill": link_fail,
        "exo_stop_dominance": exo_stop,
    }
    out["canonical_sha256"] = canonical_sha256(out)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aletheia v2.1 Proposals Pure-Z/Q Self-Test")
    parser.add_argument("--json", action="store_true", help="Emit canonical JSON self-test output")
    args = parser.parse_args(argv)
    res = run_v21_proposals_self_test()
    if args.json:
        sys.stdout.write(json.dumps(res, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n")
    else:
        sys.stdout.write(f"OK {res['verdict']} canonical_sha256={res['canonical_sha256']}\n")
    return 0 if res["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
