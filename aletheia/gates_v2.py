"""
`aletheia.gates_v2`: Pure-Q Zero-Float v2.0 Gate-Contract Engine.

Implements all verified Round-10 / v2.0 Aletheia governance gates in pure Python 3
standard library (`int`, `fractions.Fraction`, zero floats on trust paths, zero bare asserts):
  1. `evaluate_r6_r7_gate` — Contract R6 (owner-pinned registered checks) & R7 (measured from bytes)
  2. `certify_two_direction_r3` — Two-Direction R3 (Dir (i) accept->reject & Dir (ii) reject stays reject)
  3. `evaluate_sampled_integrity` — aletheia#3 §4 (partial zero-hit coverage is NOT_SHOWN, never PASS)
  4. `certify_oracle_contract` — aletheia#3 §§5-7 (exact arithmetic != exact oracle; anchor vs replay; feedback channels)
  5. `certify_gate8_subspace_latch` — aletheia#3 §8 (exact Q col(Phi) projection, sin^2(theta), BLIND_AUDIT_IN_COL_PHI halt)
  6. `certify_transformational_steelman` — Law 2b (AUDIT-088R: 7 harmonized morphism families T1-T7 + 4 anti-epicycle guards G1-G4)
  7. `certify_own_terms_phase1` — Own-Terms-First Phase-1 Gate (AUDIT-084R: OTF-TIGHT-01/03, multi-axis nets, error-budget ceilings, Rules 3-6)
  8. `certify_own_terms_model_ladder` — Own-Terms-First Orthogonal Model-Ladder Remainder Oracle (AUDIT-084R: OTF-TIGHT-02)
  9. `certify_own_terms_symbol_utility` — Own-Terms-First Rule-2 5-Tier Symbol Operational-Utility Classifier (AUDIT-084R: OTF-TIGHT-04)
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import math
from typing import Any, Callable

from .strict_io import AletheiaError

MAX_CONTAINER_DEPTH = 64
MAX_RATIONAL_DIGITS = 1000
_ASCII_DIGITS = frozenset("0123456789")


PINNED_RULE_KEYS = frozenset(
    {
        "rule_id",
        "expected_check_ids",
        "min_sq_norm",
        "max_sq_norm",
        "expected_header_alpha",
        "max_vector_dim",
    }
)
R6_REGISTERED_CHECKS = frozenset(
    {
        "r7_sha256",
        "r7_payload_schema",
        "r7_sq_norm",
        "r7_header_alpha",
        "r6_vector_dim",
        "r6_alpha",
        "r6_sq_norm_bounds",
    }
)
SUBMISSION_KEYS = frozenset(
    {
        "declared_sha256",
        "declared_sq_norm",
        "declared_header_alpha",
        "declared_status",
        "submitter_rule_overrides",
    }
)
PAYLOAD_KEYS = frozenset({"header_alpha", "vector_entries"})
ALLOWED_DECLARED_STATUSES = frozenset({"PASS", "CANDIDATE"})

ORACLE_CONTRACT_KEYS = frozenset({"oracle_class", "evidence_basis", "feedback_channel"})
EXACT_ORACLE_BASES = frozenset(
    {
        "formal_proof",
        "symbolic_identity",
        "per_input_certificate",
        "exhaustive_enumeration",
    }
)
SAMPLED_ORACLE_BASES = frozenset(
    {
        "random_finite_sample",
        "random_finite_sample_exact_arithmetic",
    }
)
EXPECTED_FEEDBACK_CHANNEL = {
    "exact": "full_counterexample_and_repair",
    "sampled": "family_only_with_fresh_post_repair_seed",
    "anchor": "none_to_proposer_spec_owner_only",
    "reference_replay": "diff_against_upstream_reference",
}

# Harmonized verbatim with Round-10 AUDIT-088R (arm5-transformational-steelman)
MORPHISM_FAMILIES = frozenset(
    {
        "T1_GAUGE_SIMILARITY",
        "T2_AFFINE_BREGMAN",
        "T3_METRIC_CHART",
        "T4_SPECTRAL_PSD_SHIFT",
        "T5_SEMIRING_TROPICAL",
        "T6_SUBSPACE_PROJECTION",
        "T7_ORDER_DOMAIN_RESIDUAL",
    }
)
STEELMAN_KEYS = frozenset(
    {
        "proposed_verdict",
        "literal_failed",
        "literal_failure_witness",
        "families_searched",
        "transform_family",
        "preserved_invariant_core",
        "modified_hypotheses",
        "transform_rank",
        "transform_dof",
        "held_out_constraints",
        "fixed_globally",
        "target_pass_count",
        "target_total_count",
        "null_false_passes",
        "null_total",
        "max_null_rate",
        "residual_gap",
        "max_residual_gap",
        "relabelled_as_literal",
        "surviving_obstruction",
        "obstruction_survives_all_searched",
    }
)
MAX_PROTOCOL_NULL_RATE = Fraction(1, 10)
MIN_ZERO_CEILING_NULL_TOTAL = 10

OWN_TERMS_NET_AXES = frozenset({"rate", "quantization", "scale", "window", "instrument"})
OTF_MAX_PER_NET_ALPHA = Fraction(1, 10)
OTF_MAX_FWER_CEILING = Fraction(1, 4)
OWN_TERMS_SPEC_KEYS = frozenset(
    {
        "measurable_definition_present",
        "pinned_net_ids",
        "per_net_alpha",
        "max_fwer",
        "min_signal_margin",
        "max_control_score",
        "held_out_verified",
        "second_instrument_verified",
    }
)
OWN_TERMS_MEAS_KEYS = frozenset(
    {
        "net_id",
        "axis",
        "observed_score",
        "observed_p_value",
        "iid_null_score",
        "spectrum_null_score",
        "control_score",
    }
)
OWN_TERMS_SYMBOL_KEYS = frozenset(
    {
        "symbol",
        "op_id",
        "reproducible_from_rules",
        "unseen_physical_prediction",
        "adds_rule_beyond_standard",
        "overloads_distinct_constructs",
    }
)


def _is_strict_int(value: object) -> bool:
    return type(value) is int


def _is_clean_ascii(value: object) -> bool:
    return (
        type(value) is str
        and len(value) > 0
        and value == value.strip()
        and all(32 <= ord(ch) <= 126 for ch in value)
    )


def _is_lower_hex(value: object, expected_len: int) -> bool:
    return (
        type(value) is str
        and len(value) == expected_len
        and all(ch in "0123456789abcdef" for ch in value)
    )


def _fmt_q(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}" if value.denominator != 1 else str(value.numerator)


def _verify_no_floats(obj: object) -> None:
    """Reject any float in a nested dict/list/tuple, walking at most MAX_CONTAINER_DEPTH levels.

    Error precedence (both outcomes reject the input): an item deeper than MAX_CONTAINER_DEPTH
    raises AletheiaError("MAX_DEPTH_EXCEEDED") when it is reached, before its type is examined,
    so a float nested more than 64 levels deep reports MAX_DEPTH_EXCEEDED, not FLOAT_FORBIDDEN.
    The walk is depth-first and stops at the first violation, so an input holding both a shallow
    float and an over-deep branch reports whichever of the two the walk reaches first.
    """
    stack: list[tuple[object, int]] = [(obj, 0)]
    while stack:
        item, depth = stack.pop()
        if depth > MAX_CONTAINER_DEPTH:
            raise AletheiaError("MAX_DEPTH_EXCEEDED", f"container nesting depth exceeds {MAX_CONTAINER_DEPTH}")
        if isinstance(item, float):
            raise ValueError("FLOAT_FORBIDDEN")
        if isinstance(item, dict):
            for k, v in item.items():
                stack.append((k, depth + 1))
                stack.append((v, depth + 1))
        elif isinstance(item, (list, tuple)):
            for sub in item:
                stack.append((sub, depth + 1))


def _parse_exact_rational(value: object) -> Fraction:
    if type(value) is Fraction:
        return value
    if _is_strict_int(value):
        return Fraction(value, 1)
    if not _is_clean_ascii(value):
        raise ValueError("RATIONAL_TYPE_OR_SYNTAX")
    parts = value.split("/")
    if len(parts) > 2:
        raise ValueError("RATIONAL_TOO_MANY_SLASHES")
    num_s = parts[0]
    neg = num_s.startswith("-")
    digits = num_s[1:] if neg else num_s
    if not digits or len(digits) > MAX_RATIONAL_DIGITS or any(ch not in _ASCII_DIGITS for ch in digits):
        raise ValueError("RATIONAL_INVALID_NUMERATOR")
    if len(digits) > 1 and digits[0] == "0":
        raise ValueError("RATIONAL_LEADING_ZERO")
    if neg and digits == "0":
        raise ValueError("RATIONAL_NEGATIVE_ZERO")
    num = -int(digits) if neg else int(digits)
    if len(parts) == 1:
        return Fraction(num, 1)
    den_s = parts[1]
    if not den_s or len(den_s) > MAX_RATIONAL_DIGITS or any(ch not in _ASCII_DIGITS for ch in den_s):
        raise ValueError("RATIONAL_INVALID_DENOMINATOR")
    if len(den_s) > 1 and den_s[0] == "0":
        raise ValueError("RATIONAL_LEADING_ZERO")
    den = int(den_s)
    if den <= 0:
        raise ValueError("RATIONAL_NONPOSITIVE_DENOMINATOR")
    if den == 1:
        raise ValueError("RATIONAL_UNIT_DENOMINATOR")
    if math.gcd(abs(num), den) != 1:
        raise ValueError("RATIONAL_NOT_REDUCED")
    return Fraction(num, den)


def _typed_key(key: object) -> tuple[type, object]:
    return (type(key), key)


def _strict_typed_equal(left: object, right: object) -> bool:
    """Iterative equality preserving exact runtime types (1 != True, 1 != 1.0).

    Dict keys and set elements are compared by (type, value) so int/bool/float
    collisions (1 == True == 1.0) cannot pass as equal. The walk is iterative
    so deeply nested configs fail closed instead of raising RecursionError.
    """
    stack: list[tuple[object, object]] = [(left, right)]
    while stack:
        a, b = stack.pop()
        if type(a) is not type(b):
            return False
        if isinstance(a, dict):
            typed_b = {_typed_key(k): v for k, v in b.items()}  # type: ignore[union-attr]
            if len(typed_b) != len(a):
                return False
            for k, v in a.items():
                tk = _typed_key(k)
                if tk not in typed_b:
                    return False
                stack.append((v, typed_b[tk]))
        elif isinstance(a, (list, tuple)):
            if len(a) != len(b):  # type: ignore[arg-type]
                return False
            stack.extend(zip(a, b))  # type: ignore[arg-type]
        elif isinstance(a, (set, frozenset)):
            try:
                typed_a = {_typed_key(x) for x in a}
                typed_b_set = {_typed_key(x) for x in b}  # type: ignore[union-attr]
            except TypeError:
                return False
            if typed_a != typed_b_set:
                return False
        elif a != b:
            return False
    return True


def _reject_json_float(raw: str) -> Any:
    raise ValueError(f"JSON_FLOAT_FORBIDDEN:{raw}")


def _reject_json_constant(raw: str) -> Any:
    raise ValueError(f"JSON_CONSTANT_FORBIDDEN:{raw}")


def _no_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"JSON_DUPLICATE_KEY:{k}")
        out[k] = v
    return out


def _parse_strict_json_bytes(raw: bytes) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("PAYLOAD_INVALID_UTF8") from exc
    try:
        parsed = json.loads(
            text,
            parse_float=_reject_json_float,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_no_duplicate_json_keys,
        )
    except json.JSONDecodeError as exc:
        raise ValueError("PAYLOAD_INVALID_JSON") from exc
    except RecursionError as exc:
        raise AletheiaError("MAX_DEPTH_EXCEEDED", f"container nesting depth exceeds {MAX_CONTAINER_DEPTH}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("PAYLOAD_ROOT_NOT_OBJECT")
    _verify_no_floats(parsed)
    return parsed


# ---------------------------------------------------------------------------
# 1. R6 (Pinned Registered Checks) & R7 (Measured, Not Declared)
# ---------------------------------------------------------------------------


def evaluate_r6_r7_gate(
    pinned_rules: dict[str, Any],
    submission: dict[str, Any],
    artifact_bytes: bytes,
) -> dict[str, Any]:
    """Fail-closed R6 (owner-pinned registered checks) + R7 (byte-recomputed measurements) gate."""
    if not isinstance(pinned_rules, dict):
        raise ValueError("R6_PINNED_RULES_NOT_DICT")
    if frozenset(pinned_rules.keys()) != PINNED_RULE_KEYS:
        raise ValueError("R6_PINNED_RULES_SCHEMA_MISMATCH")
    rule_id = pinned_rules["rule_id"]
    if not _is_clean_ascii(rule_id):
        raise ValueError("R6_INVALID_RULE_ID")
    check_ids = pinned_rules["expected_check_ids"]
    if not isinstance(check_ids, (list, tuple)):
        raise ValueError("R6_CHECK_IDS_NOT_SEQUENCE")
    if len(check_ids) == 0:
        raise ValueError("R6_EMPTY_CHECK_IDS")
    if any(not _is_clean_ascii(cid) for cid in check_ids):
        raise ValueError("R6_INVALID_CHECK_ID")
    if len({cid.lower() for cid in check_ids}) != len(check_ids):
        raise ValueError("R6_DUPLICATE_CHECK_ID")
    if any(cid not in R6_REGISTERED_CHECKS for cid in check_ids):
        raise ValueError("R6_UNKNOWN_CHECK_ID")

    min_sq = _parse_exact_rational(pinned_rules["min_sq_norm"])
    max_sq = _parse_exact_rational(pinned_rules["max_sq_norm"])
    if min_sq < Fraction(0, 1):
        raise ValueError("R6_NEGATIVE_MIN_SQ_NORM")
    if max_sq < min_sq:
        raise ValueError("R6_INVERTED_SQ_NORM_RANGE")
    exp_alpha = _parse_exact_rational(pinned_rules["expected_header_alpha"])
    if exp_alpha <= Fraction(0, 1):
        raise ValueError("R6_NONPOSITIVE_EXPECTED_ALPHA")
    max_dim = pinned_rules["max_vector_dim"]
    if not _is_strict_int(max_dim) or max_dim <= 0:
        raise ValueError("R6_INVALID_MAX_VECTOR_DIM")

    if not isinstance(submission, dict):
        raise ValueError("R6_SUBMISSION_NOT_DICT")
    if frozenset(submission.keys()) != SUBMISSION_KEYS:
        raise ValueError("R6_SUBMISSION_SCHEMA_MISMATCH")
    overrides = submission["submitter_rule_overrides"]
    if not isinstance(overrides, dict):
        raise ValueError("R6_OVERRIDES_NOT_OBJECT")
    if len(overrides) > 0:
        raise ValueError("R6_SUBMITTER_RULE_OVERRIDE")

    declared_status = submission["declared_status"]
    if not isinstance(declared_status, str) or declared_status not in ALLOWED_DECLARED_STATUSES:
        raise ValueError("R6_INVALID_DECLARED_STATUS")

    if not isinstance(artifact_bytes, bytes):
        raise ValueError("R7_ARTIFACT_NOT_BYTES")
    if len(artifact_bytes) == 0:
        raise ValueError("R7_NULL_ARTIFACT_BYTES")

    executed: dict[str, str] = {}

    measured_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
    declared_sha256 = submission["declared_sha256"]
    if not _is_lower_hex(declared_sha256, 64):
        raise ValueError("R7_INVALID_DECLARED_SHA256")
    if declared_sha256 != measured_sha256:
        raise ValueError("R7_DECLARED_SHA256_MISMATCH")
    executed["r7_sha256"] = "PASS"

    payload = _parse_strict_json_bytes(artifact_bytes)
    if frozenset(payload.keys()) != PAYLOAD_KEYS:
        raise ValueError("R7_PAYLOAD_SCHEMA_MISMATCH")
    executed["r7_payload_schema"] = "PASS"

    measured_alpha = _parse_exact_rational(payload["header_alpha"])
    entries = payload["vector_entries"]
    if not isinstance(entries, list) or len(entries) == 0:
        raise ValueError("R7_EMPTY_VECTOR_ENTRIES")
    if len(entries) > max_dim:
        raise ValueError("R6_VECTOR_DIM_EXCEEDS_MAX")
    executed["r6_vector_dim"] = "PASS"

    vec = [_parse_exact_rational(x) for x in entries]
    measured_sq_norm = sum((v * v for v in vec), Fraction(0, 1))

    declared_sq = _parse_exact_rational(submission["declared_sq_norm"])
    declared_alpha = _parse_exact_rational(submission["declared_header_alpha"])
    if declared_sq != measured_sq_norm:
        raise ValueError("R7_DECLARED_NORM_MISMATCH")
    executed["r7_sq_norm"] = "PASS"
    if declared_alpha != measured_alpha:
        raise ValueError("R7_DECLARED_ALPHA_MISMATCH")
    executed["r7_header_alpha"] = "PASS"

    if measured_alpha != exp_alpha:
        raise ValueError("R6_HEADER_ALPHA_OUT_OF_SPEC")
    executed["r6_alpha"] = "PASS"
    if measured_sq_norm < min_sq:
        raise ValueError("R6_MEASURED_NORM_BELOW_MIN")
    if measured_sq_norm > max_sq:
        raise ValueError("R6_MEASURED_NORM_ABOVE_MAX")
    executed["r6_sq_norm_bounds"] = "PASS"

    checked_results = {cid: executed[cid] for cid in check_ids}
    return {
        "status": "ACCEPTED",
        "rule_id": rule_id,
        "checked_ids": list(check_ids),
        "executed_checks": checked_results,
        "measured_sha256": measured_sha256,
        "measured_sq_norm": _fmt_q(measured_sq_norm),
        "measured_header_alpha": _fmt_q(measured_alpha),
        "vector_dim": len(vec),
    }


# ---------------------------------------------------------------------------
# 2. Two-Direction R3 Re-Spelling Certifier
# ---------------------------------------------------------------------------


def certify_two_direction_r3(
    gate_fn: Callable[[Any], bool],
    accepted_case: dict[str, Any],
    rejected_case: dict[str, Any],
    accepted_respellings: list[tuple[str, Any]],
    rejected_respellings: list[tuple[str, Any]],
) -> dict[str, Any]:
    """Certify Direction (i) (accept->reject) & Direction (ii) (reject stays reject)."""
    if not accepted_respellings:
        raise ValueError("R3_EMPTY_DIR1_CASES")
    if not rejected_respellings:
        raise ValueError("R3_EMPTY_DIR2_CASES")
    if gate_fn(accepted_case) is not True:
        raise ValueError("R3_BASELINE_ACCEPT_FAILED")
    if gate_fn(rejected_case) is not False:
        raise ValueError("R3_BASELINE_REJECT_FAILED")

    seen_labels: set[str] = set()
    dir1_failures: list[str] = []
    for label, mutated in accepted_respellings:
        if not _is_clean_ascii(label):
            raise ValueError("R3_INVALID_DIR1_LABEL")
        low = label.lower()
        if low in seen_labels:
            raise ValueError("R3_DUPLICATE_LABEL")
        seen_labels.add(low)
        if _strict_typed_equal(mutated, accepted_case):
            raise ValueError("R3_NOOP_DIR1_CASE")
        if gate_fn(mutated) is not False:
            dir1_failures.append(label)

    dir2_failures: list[str] = []
    for label, mutated in rejected_respellings:
        if not _is_clean_ascii(label):
            raise ValueError("R3_INVALID_DIR2_LABEL")
        low = label.lower()
        if low in seen_labels:
            raise ValueError("R3_DUPLICATE_LABEL")
        seen_labels.add(low)
        if _strict_typed_equal(mutated, rejected_case):
            raise ValueError("R3_NOOP_DIR2_CASE")
        if gate_fn(mutated) is not False:
            dir2_failures.append(label)

    return {
        "passed": len(dir1_failures) == 0 and len(dir2_failures) == 0,
        "dir1_total": len(accepted_respellings),
        "dir1_rejected": len(accepted_respellings) - len(dir1_failures),
        "dir1_failures": dir1_failures,
        "dir2_total": len(rejected_respellings),
        "dir2_stayed_rejected": len(rejected_respellings) - len(dir2_failures),
        "dir2_failures": dir2_failures,
    }


# ---------------------------------------------------------------------------
# 3 & 4. Sampled Gate-Integrity NOT_SHOWN & Oracle-Class Feedback Contract
# ---------------------------------------------------------------------------


def evaluate_sampled_integrity(
    tested_count: int,
    total_discovered: int,
    hits_found: int,
) -> dict[str, Any]:
    """aletheia#3 §4: sampled gate-integrity with 0 hits is NOT_SHOWN, never PASS."""
    if not _is_strict_int(total_discovered) or total_discovered <= 0:
        raise ValueError("SAMPLED_INVALID_TOTAL")
    if not _is_strict_int(tested_count) or tested_count < 0 or tested_count > total_discovered:
        raise ValueError("SAMPLED_INVALID_TESTED")
    if not _is_strict_int(hits_found) or hits_found < 0 or hits_found > tested_count:
        raise ValueError("SAMPLED_INVALID_HITS")

    if hits_found > 0:
        verdict = "FAIL"
        passed = False
    elif tested_count < total_discovered:
        verdict = "NOT_SHOWN"
        passed = False
    else:
        verdict = "PASS"
        passed = True

    return {
        "verdict": verdict,
        "passed": passed,
        "tested_count": tested_count,
        "total_discovered": total_discovered,
        "hits_found": hits_found,
        "coverage_fraction": _fmt_q(Fraction(tested_count, total_discovered)),
    }


def certify_oracle_contract(spec: dict[str, Any]) -> dict[str, Any]:
    """aletheia#3 §§5-7: exact arithmetic != exact oracle; anchor != replay; feedback rules."""
    if not isinstance(spec, dict) or frozenset(spec.keys()) != ORACLE_CONTRACT_KEYS:
        raise ValueError("ORACLE_CONTRACT_SCHEMA_MISMATCH")
    oracle_class = spec["oracle_class"]
    if not isinstance(oracle_class, str) or oracle_class not in EXPECTED_FEEDBACK_CHANNEL:
        raise ValueError("ORACLE_UNKNOWN_CLASS")
    basis = spec["evidence_basis"]
    if not _is_clean_ascii(basis):
        raise ValueError("ORACLE_INVALID_BASIS")
    feedback = spec["feedback_channel"]
    if not _is_clean_ascii(feedback):
        raise ValueError("ORACLE_INVALID_FEEDBACK")

    if oracle_class == "exact" and basis not in EXACT_ORACLE_BASES:
        raise ValueError("ORACLE_EXACT_REQUIRES_NON_SAMPLED_BASIS")
    if oracle_class == "sampled" and basis not in SAMPLED_ORACLE_BASES:
        raise ValueError("ORACLE_SAMPLED_INVALID_BASIS")
    if oracle_class == "anchor" and basis != "external_domain_data":
        raise ValueError("ORACLE_ANCHOR_REQUIRES_EXTERNAL_DATA")
    if oracle_class == "reference_replay" and basis != "untouched_upstream_replay":
        raise ValueError("ORACLE_REPLAY_REQUIRES_UPSTREAM")

    expected_fb = EXPECTED_FEEDBACK_CHANNEL[oracle_class]
    if feedback != expected_fb:
        raise ValueError("ORACLE_FEEDBACK_CHANNEL_MISMATCH")

    return {
        "valid": True,
        "oracle_class": oracle_class,
        "evidence_basis": basis,
        "feedback_channel": feedback,
        "failure_routes_to": "spec_owner" if oracle_class == "anchor" else "proposer_or_implementer",
    }


# ---------------------------------------------------------------------------
# 5. Gate-8 Exact Pure-Q Subspace Projection & Blind-Audit Latch
# ---------------------------------------------------------------------------


def _dot_q(u: list[Fraction] | tuple[Fraction, ...], v: list[Fraction] | tuple[Fraction, ...]) -> Fraction:
    return sum((a * b for a, b in zip(u, v)), Fraction(0, 1))


def _exact_pivot_columns_q(columns: list[list[Fraction]]) -> list[int]:
    m = len(columns[0])
    r = len(columns)
    mat = [[columns[j][i] for j in range(r)] for i in range(m)]
    pivots: list[int] = []
    row = 0
    for col in range(r):
        pivot_row = None
        for i in range(row, m):
            if mat[i][col] != Fraction(0, 1):
                pivot_row = i
                break
        if pivot_row is None:
            continue
        mat[row], mat[pivot_row] = mat[pivot_row], mat[row]
        pv = mat[row][col]
        mat[row] = [x / pv for x in mat[row]]
        for i in range(m):
            if i != row and mat[i][col] != Fraction(0, 1):
                factor = mat[i][col]
                mat[i] = [mat[i][c] - factor * mat[row][c] for c in range(r)]
        pivots.append(col)
        row += 1
        if row == m:
            break
    return pivots


def _solve_linear_q(gram: list[list[Fraction]], rhs: list[Fraction]) -> list[Fraction]:
    k = len(rhs)
    aug = [gram[i][:] + [rhs[i]] for i in range(k)]
    for col in range(k):
        pivot_row = col
        while pivot_row < k and aug[pivot_row][col] == Fraction(0, 1):
            pivot_row += 1
        if pivot_row == k:
            raise ValueError("LATCH_SINGULAR_GRAM")
        aug[col], aug[pivot_row] = aug[pivot_row], aug[col]
        pv = aug[col][col]
        aug[col] = [x / pv for x in aug[col]]
        for i in range(k):
            if i != col and aug[i][col] != Fraction(0, 1):
                factor = aug[i][col]
                aug[i] = [aug[i][c] - factor * aug[col][c] for c in range(k + 1)]
    return [aug[i][k] for i in range(k)]


def certify_gate8_subspace_latch(
    phi_columns: list[list[Any]],
    audit_vector: list[Any],
    residual_sq: Any,
    noise_var_s2: Any,
) -> dict[str, Any]:
    """aletheia#3 §8: exact pure-Q col(Phi) projection, sin^2(theta) & BLIND_AUDIT_IN_COL_PHI halt."""
    if not isinstance(phi_columns, list) or len(phi_columns) == 0:
        raise ValueError("LATCH_EMPTY_PHI")
    if not isinstance(phi_columns[0], list) or len(phi_columns[0]) == 0:
        raise ValueError("LATCH_EMPTY_PHI_COLUMN")
    m = len(phi_columns[0])
    cols_q: list[list[Fraction]] = []
    for col in phi_columns:
        if not isinstance(col, list) or len(col) != m:
            raise ValueError("LATCH_RAGGED_PHI")
        cols_q.append([_parse_exact_rational(x) for x in col])

    if not isinstance(audit_vector, list) or len(audit_vector) != m:
        raise ValueError("LATCH_AUDIT_VECTOR_DIM_MISMATCH")
    a_q = [_parse_exact_rational(x) for x in audit_vector]
    a_norm_sq = _dot_q(a_q, a_q)
    if a_norm_sq <= Fraction(0, 1):
        raise ValueError("LATCH_ZERO_AUDIT_VECTOR")

    res_q = _parse_exact_rational(residual_sq)
    if res_q < Fraction(0, 1):
        raise ValueError("LATCH_NEGATIVE_RESIDUAL")
    s2_q = _parse_exact_rational(noise_var_s2)
    if s2_q <= Fraction(0, 1):
        raise ValueError("LATCH_NONPOSITIVE_NOISE_VAR")

    pivot_idx = _exact_pivot_columns_q(cols_q)
    rank = len(pivot_idx)
    surviving_audits = m - rank

    if rank == 0:
        a_par = [Fraction(0, 1)] * m
    else:
        basis = [cols_q[j] for j in pivot_idx]
        gram = [[_dot_q(basis[i], basis[j]) for j in range(rank)] for i in range(rank)]
        rhs = [_dot_q(basis[i], a_q) for i in range(rank)]
        coeffs = _solve_linear_q(gram, rhs)
        a_par = [
            sum((coeffs[j] * basis[j][i] for j in range(rank)), Fraction(0, 1))
            for i in range(m)
        ]

    a_perp = [a_q[i] - a_par[i] for i in range(m)]
    par_norm_sq = _dot_q(a_par, a_par)
    perp_norm_sq = _dot_q(a_perp, a_perp)
    ortho_dot = _dot_q(a_par, a_perp)
    pythag_residual = a_norm_sq - (par_norm_sq + perp_norm_sq)

    sin2_theta = perp_norm_sq / a_norm_sq
    cos2_theta = par_norm_sq / a_norm_sq
    postfit_budget = Fraction(surviving_audits, 1) * s2_q

    if surviving_audits == 0:
        decision = "SATURATED_NO_SURVIVING_AUDITS"
        halt = True
    elif perp_norm_sq == Fraction(0, 1):
        decision = "BLIND_AUDIT_IN_COL_PHI"
        halt = True
    elif res_q > postfit_budget:
        decision = "LATCH_HALT"
        halt = True
    else:
        decision = "WITHIN_POSTFIT_BUDGET"
        halt = False

    return {
        "ambient_dim_m": m,
        "phi_rank": rank,
        "surviving_independent_audits": surviving_audits,
        "audit_norm_sq": _fmt_q(a_norm_sq),
        "parallel_norm_sq": _fmt_q(par_norm_sq),
        "orthogonal_norm_sq": _fmt_q(perp_norm_sq),
        "sin2_theta_attenuation": _fmt_q(sin2_theta),
        "cos2_theta_captured": _fmt_q(cos2_theta),
        "orthogonality_residual": _fmt_q(ortho_dot),
        "pythagorean_residual": _fmt_q(pythag_residual),
        "residual_sq": _fmt_q(res_q),
        "postfit_budget_m_minus_rank_s2": _fmt_q(postfit_budget),
        "decision": decision,
        "halt": halt,
    }


# ---------------------------------------------------------------------------
# 6. Law 2b — Transformational Steelman / Morphism-Before-Dismissal (AUDIT-088R)
# ---------------------------------------------------------------------------


def certify_transformational_steelman(spec: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed Law 2b gate enforcing 7 harmonized morphism families + 4 anti-epicycle guards.

    Enforces AUDIT-088R G0-G4 on both rescues (TRANSFORMED_EXACT, BOUNDED_TRANSFORM_CORE)
    and exhaustive INVARIANT_FALSIFIED verdicts, including uniform G1 null-resolution
    (null_total * max_null_rate >= 1 for max_null_rate > 0, and null_total >= 10 when
    max_null_rate == 0).

    Declared-record scope: this pure-Q schema/inequality gate certifies that a
    caller-supplied record is well-formed and satisfies the stated mathematical
    inequalities. It does NOT establish from the dict alone that the underlying
    measurements, null suites, or held-out evaluations were actually executed or that
    free-text witness fields match the declared numbers; execution provenance must be
    verified separately via clean-room replay or R6/R7 byte-recomputed artifacts.
    """
    _verify_no_floats(spec)
    if not isinstance(spec, dict):
        raise ValueError("TS_SPEC_NOT_DICT")
    if frozenset(spec.keys()) != STEELMAN_KEYS:
        raise ValueError("TS_SCHEMA_MISMATCH")

    verdict = spec["proposed_verdict"]
    if verdict == "FALSIFIED_RAW":
        raise ValueError("G4_RAW_FALSIFIED_FORBIDDEN")
    if verdict not in ("TRANSFORMED_EXACT", "BOUNDED_TRANSFORM_CORE", "INVARIANT_FALSIFIED"):
        raise ValueError("TS_INVALID_VERDICT")

    literal_failed = spec["literal_failed"]
    if not isinstance(literal_failed, bool):
        raise ValueError("G0_INVALID_LITERAL_FAILED_TYPE")
    if not literal_failed:
        raise ValueError("G0_LITERAL_CLAIM_NOT_FAILED")

    if not _is_clean_ascii(spec["literal_failure_witness"]):
        raise ValueError("G3_MISSING_LITERAL_FAILURE_WITNESS")

    relabelled = spec["relabelled_as_literal"]
    if not isinstance(relabelled, bool):
        raise ValueError("G3_INVALID_RELABELLED_TYPE")
    if relabelled:
        raise ValueError("G3_SILENT_GOALPOST_MOVING")

    families = spec["families_searched"]
    if not isinstance(families, (list, tuple)):
        raise ValueError("TS_FAMILIES_NOT_SEQUENCE")
    if len(families) == 0:
        raise ValueError("TS_EMPTY_FAMILIES_SEARCHED")
    if any(not isinstance(f, str) or f not in MORPHISM_FAMILIES for f in families):
        raise ValueError("TS_UNKNOWN_MORPHISM_FAMILY")
    if len(set(families)) != len(families):
        raise ValueError("TS_DUPLICATE_MORPHISM_FAMILY")

    fixed_globally = spec["fixed_globally"]
    if not isinstance(fixed_globally, bool):
        raise ValueError("G2_INVALID_FIXED_GLOBALLY_TYPE")
    if not fixed_globally:
        raise ValueError("G2_NOT_FIXED_GLOBALLY")

    t_rank = spec["transform_rank"]
    t_dof = spec["transform_dof"]
    constraints = spec["held_out_constraints"]
    if not _is_strict_int(t_rank) or t_rank < 0:
        raise ValueError("G1_INVALID_TRANSFORM_RANK")
    if not _is_strict_int(t_dof) or t_dof < 0:
        raise ValueError("G2_INVALID_TRANSFORM_DOF")
    if not _is_strict_int(constraints) or constraints <= 0:
        raise ValueError("G2_INVALID_CONSTRAINTS")

    target_tot = spec["target_total_count"]
    target_pass = spec["target_pass_count"]
    if not _is_strict_int(target_tot) or target_tot <= 0:
        raise ValueError("G1_INVALID_TARGET_TOTAL")
    if not _is_strict_int(target_pass) or target_pass < 0 or target_pass > target_tot:
        raise ValueError("G1_INVALID_TARGET_PASS_COUNT")

    null_fp = spec["null_false_passes"]
    null_tot = spec["null_total"]
    if not _is_strict_int(null_tot) or null_tot <= 0:
        raise ValueError("G1_EMPTY_NULL_SUITE")
    if not _is_strict_int(null_fp) or null_fp < 0 or null_fp > null_tot:
        raise ValueError("G1_INVALID_NULL_FALSE_PASSES")

    max_null_rate = _parse_exact_rational(spec["max_null_rate"])
    if max_null_rate < Fraction(0, 1) or max_null_rate > MAX_PROTOCOL_NULL_RATE:
        raise ValueError("G1_MAX_NULL_RATE_OUT_OF_RANGE")

    # G1 null-resolution enforced uniformly on BOTH rescues and INVARIANT_FALSIFIED
    if max_null_rate == Fraction(0, 1):
        if null_tot < MIN_ZERO_CEILING_NULL_TOTAL:
            raise ValueError("G1_INSUFFICIENT_NULL_RESOLUTION")
    elif Fraction(null_tot, 1) * max_null_rate < Fraction(1, 1):
        raise ValueError("G1_INSUFFICIENT_NULL_RESOLUTION")

    null_rate = Fraction(null_fp, null_tot)
    if null_rate > max_null_rate:
        raise ValueError("G1_NULL_FALSE_PASS_EXCEEDED")

    res_gap = _parse_exact_rational(spec["residual_gap"])
    max_gap = _parse_exact_rational(spec["max_residual_gap"])
    if res_gap < Fraction(0, 1) or max_gap < Fraction(0, 1):
        raise ValueError("G3_NEGATIVE_RESIDUAL_GAP")

    obs_survives = spec["obstruction_survives_all_searched"]
    if not isinstance(obs_survives, bool):
        raise ValueError("G4_INVALID_OBSTRUCTION_SURVIVES_TYPE")

    t_family = spec["transform_family"]
    core = spec["preserved_invariant_core"]
    mod_hyp = spec["modified_hypotheses"]
    obs = spec["surviving_obstruction"]

    if verdict == "INVARIANT_FALSIFIED":
        if len(families) != len(MORPHISM_FAMILIES):
            raise ValueError("G4_INCOMPLETE_MORPHISM_SEARCH")
        if not _is_clean_ascii(obs):
            raise ValueError("G4_MISSING_SURVIVING_OBSTRUCTION")
        if not obs_survives:
            raise ValueError("G4_OBSTRUCTION_NOT_INVARIANT_ACROSS_FAMILIES")
        if t_family is not None or core is not None or mod_hyp is not None or t_rank != 0 or t_dof != 0:
            raise ValueError("G4_CONTRADICTORY_RESCUE_FIELDS_ON_FALSIFIED")
        if target_pass == target_tot:
            raise ValueError("G4_FALSIFIED_HAS_NO_FAILING_TARGET")
        if res_gap == Fraction(0, 1):
            raise ValueError("G4_FALSIFIED_HAS_ZERO_GAP")
        status = "CERTIFIED_INVARIANT_FALSIFIED"
    else:
        if obs is not None or obs_survives:
            raise ValueError("G0_CONTRADICTORY_OBSTRUCTION_ON_RESCUE")
        if t_family not in families:
            raise ValueError("G3_TRANSFORM_FAMILY_NOT_SEARCHED")
        if not _is_clean_ascii(core) or not _is_clean_ascii(mod_hyp):
            raise ValueError("G3_MISSING_SCOPE_DELTA")
        if t_rank <= 0:
            raise ValueError("G1_DEGENERATE_ZERO_RANK_TRANSFORM")
        if target_pass < target_tot:
            raise ValueError("G1_TRANSFORMED_TARGET_FAILED")
        if t_dof >= constraints:
            raise ValueError("G2_DOF_EXCEEDS_CONSTRAINTS")
        if verdict == "TRANSFORMED_EXACT":
            if res_gap != Fraction(0, 1) or max_gap != Fraction(0, 1):
                raise ValueError("G3_EXACT_RESCUE_HAS_NONZERO_GAP")
        else:
            if res_gap == Fraction(0, 1) or res_gap > max_gap:
                raise ValueError("G3_BOUNDED_RESCUE_GAP_OUT_OF_RANGE")
        status = f"CERTIFIED_{verdict}"

    return {
        "admitted": True,
        "status": status,
        "proposed_verdict": verdict,
        "families_searched_count": len(families),
        "target_pass_rate": _fmt_q(Fraction(target_pass, target_tot)),
        "null_false_pass_rate": _fmt_q(null_rate),
        "residual_gap": _fmt_q(res_gap),
        "max_residual_gap": _fmt_q(max_gap),
        "dof_margin": constraints - t_dof,
    }


# ---------------------------------------------------------------------------
# 7. Own-Terms-First Phase-1 Gate (AUDIT-084R: OTF-TIGHT-01, OTF-TIGHT-03, Rules 3-6)
# ---------------------------------------------------------------------------


def certify_own_terms_phase1(
    pinned_spec: dict[str, Any],
    net_measurements: list[dict[str, Any]],
) -> dict[str, Any]:
    """Own-Terms-First Phase-1 gate: >=2 pinned nets across >=2 distinct axes, non-vacuous FWER/alpha,
    held-out + second-instrument verification, Tier-4A/4B nulls, Rule-5 controls, and Rule-6 return.

    Declared-record scope: this pure-Q schema/inequality gate certifies that a
    caller-supplied specification and measurement record are well-formed and satisfy the
    stated inequalities. It does NOT establish from the dicts alone that the underlying
    null suites, held-out runs, or second-instrument checks were executed, nor that
    distinct net/axis labels represent physically distinct measurements; execution
    provenance must be verified separately via clean-room replay or R6/R7 artifacts.
    """
    _verify_no_floats(pinned_spec)
    _verify_no_floats(net_measurements)

    if not isinstance(pinned_spec, dict):
        raise ValueError("OTF_SPEC_NOT_DICT")
    if frozenset(pinned_spec.keys()) != OWN_TERMS_SPEC_KEYS:
        raise ValueError("OTF_SPEC_SCHEMA_MISMATCH")
    if not isinstance(net_measurements, list):
        raise ValueError("OTF_MEASUREMENTS_NOT_LIST")
    pinned_ids = pinned_spec["pinned_net_ids"]
    if not isinstance(pinned_ids, (list, tuple)):
        raise ValueError("OTF_PINNED_NETS_NOT_SEQUENCE")
    measurable = pinned_spec["measurable_definition_present"]
    if not isinstance(measurable, bool):
        raise ValueError("OTF_INVALID_MEASURABLE_FLAG")
    if not measurable:
        return {
            "certified": False,
            "decision": "RETURN_TO_AUTHOR_FOR_DEFINITION",
            "reason": "Rule 6: claim lacks a measurable definition; return to author without inventing one",
        }

    if len(pinned_ids) < 2:
        raise ValueError("OTF_INSUFFICIENT_PINNED_NETS")
    if any(not _is_clean_ascii(nid) for nid in pinned_ids):
        raise ValueError("OTF_INVALID_NET_ID")
    pinned_low = [nid.lower() for nid in pinned_ids]
    if len(set(pinned_low)) != len(pinned_low):
        raise ValueError("OTF_DUPLICATE_PINNED_NET_ID")

    held_out = pinned_spec["held_out_verified"]
    if not isinstance(held_out, bool):
        raise ValueError("OTF_INVALID_HELD_OUT_FLAG")
    if not held_out:
        raise ValueError("OTF_HELD_OUT_NOT_VERIFIED")

    second_inst = pinned_spec["second_instrument_verified"]
    if not isinstance(second_inst, bool):
        raise ValueError("OTF_INVALID_SECOND_INSTRUMENT_FLAG")
    if not second_inst:
        raise ValueError("OTF_SECOND_INSTRUMENT_NOT_VERIFIED")

    alpha = _parse_exact_rational(pinned_spec["per_net_alpha"])
    max_fwer = _parse_exact_rational(pinned_spec["max_fwer"])
    min_margin = _parse_exact_rational(pinned_spec["min_signal_margin"])
    max_ctrl = _parse_exact_rational(pinned_spec["max_control_score"])

    if alpha <= Fraction(0, 1) or alpha > OTF_MAX_PER_NET_ALPHA:
        raise ValueError("OTF_INVALID_ALPHA")
    if max_fwer <= Fraction(0, 1) or max_fwer > OTF_MAX_FWER_CEILING:
        raise ValueError("OTF_INVALID_MAX_FWER")
    if min_margin <= Fraction(0, 1):
        raise ValueError("OTF_NONPOSITIVE_SIGNAL_MARGIN")
    if max_ctrl < Fraction(0, 1):
        raise ValueError("OTF_NEGATIVE_MAX_CONTROL")

    bonf_fwer = Fraction(len(pinned_ids), 1) * alpha
    if bonf_fwer > max_fwer:
        raise ValueError("OTF_BONFERRONI_FWER_EXCEEDED")

    if len(net_measurements) != len(pinned_ids):
        raise ValueError("OTF_MEASUREMENT_COUNT_MISMATCH")

    seen_low: set[str] = set()
    axes_seen: set[str] = set()
    max_obs_p: Fraction | None = None
    min_iid_margin: Fraction | None = None
    min_spec_margin: Fraction | None = None
    min_ctrl_margin: Fraction | None = None

    for row in net_measurements:
        if not isinstance(row, dict):
            raise ValueError("OTF_MEASUREMENT_NOT_DICT")
        if frozenset(row.keys()) != OWN_TERMS_MEAS_KEYS:
            raise ValueError("OTF_MEASUREMENT_SCHEMA_MISMATCH")
        nid = row["net_id"]
        if not _is_clean_ascii(nid):
            raise ValueError("OTF_INVALID_MEASUREMENT_NET_ID")
        nlow = nid.lower()
        if nlow not in pinned_low:
            raise ValueError("OTF_UNPINNED_NET_ID")
        if nlow in seen_low:
            raise ValueError("OTF_DUPLICATE_MEASUREMENT_NET_ID")
        seen_low.add(nlow)

        axis = row["axis"]
        if not _is_clean_ascii(axis) or axis.lower() not in OWN_TERMS_NET_AXES:
            raise ValueError("OTF_INVALID_NET_AXIS")
        axes_seen.add(axis.lower())

        obs_p = _parse_exact_rational(row["observed_p_value"])
        if obs_p < Fraction(0, 1) or obs_p > Fraction(1, 1):
            raise ValueError("OTF_INVALID_P_VALUE")
        if obs_p > alpha:
            raise ValueError("OTF_ALPHA_THRESHOLD_EXCEEDED")

        obs = _parse_exact_rational(row["observed_score"])
        iid_n = _parse_exact_rational(row["iid_null_score"])
        spec_n = _parse_exact_rational(row["spectrum_null_score"])
        ctrl = _parse_exact_rational(row["control_score"])

        iid_m = obs - abs(iid_n)
        spec_m = obs - abs(spec_n)
        ctrl_abs = abs(ctrl)
        ctrl_m = obs - ctrl_abs

        if iid_m < min_margin:
            raise ValueError("OTF_TIER4A_IID_NULL_FAILED")
        if spec_m < min_margin:
            raise ValueError("OTF_TIER4B_SPECTRUM_NULL_FAILED")
        if ctrl_abs > max_ctrl or ctrl_m < min_margin:
            raise ValueError("OTF_RULE5_CONTROL_CONTAMINATED")

        max_obs_p = obs_p if max_obs_p is None else max(max_obs_p, obs_p)
        min_iid_margin = iid_m if min_iid_margin is None else min(min_iid_margin, iid_m)
        min_spec_margin = spec_m if min_spec_margin is None else min(min_spec_margin, spec_m)
        min_ctrl_margin = ctrl_m if min_ctrl_margin is None else min(min_ctrl_margin, ctrl_m)

    if len(axes_seen) < 2:
        raise ValueError("OTF_INSUFFICIENT_DISTINCT_AXES")

    return {
        "certified": True,
        "decision": "P1_VERIFIED_INVARIANT",
        "nets_verified": len(seen_low),
        "axes_verified": sorted(axes_seen),
        "bonferroni_fwer": _fmt_q(bonf_fwer),
        "max_observed_p_value": _fmt_q(max_obs_p if max_obs_p is not None else Fraction(0, 1)),
        "min_iid_margin": _fmt_q(min_iid_margin if min_iid_margin is not None else Fraction(0, 1)),
        "min_spectrum_margin": _fmt_q(min_spec_margin if min_spec_margin is not None else Fraction(0, 1)),
        "min_control_margin": _fmt_q(min_ctrl_margin if min_ctrl_margin is not None else Fraction(0, 1)),
    }


# ---------------------------------------------------------------------------
# 8. Own-Terms-First Orthogonal Model-Ladder Remainder Oracle (AUDIT-084R: OTF-TIGHT-02)
# ---------------------------------------------------------------------------


def certify_own_terms_model_ladder(
    train_signal: list[Any] | tuple[Any, ...],
    unseen_signal: list[Any] | tuple[Any, ...],
    basis_vectors: list[list[Any]] | tuple[tuple[Any, ...], ...],
    scrambled_null_corr_sq: list[Any] | tuple[Any, ...],
    min_unseen_corr_sq: Any,
    min_remainder_energy_ratio: Any,
) -> dict[str, Any]:
    """OTF-TIGHT-02: Pure-Q orthogonal projection onto M_k^perp across a nested model ladder.

    Declared-record scope: computes exact orthogonal projections and squared correlations
    from the caller-supplied vectors, and checks the stated thresholds against the
    caller-supplied `scrambled_null_corr_sq`. It does NOT establish from the arguments
    alone that `unseen_signal` was held out from `train_signal` or that the scrambled
    null suite was independently executed; provenance must be verified separately.
    """
    _verify_no_floats((train_signal, unseen_signal, basis_vectors, scrambled_null_corr_sq, min_unseen_corr_sq, min_remainder_energy_ratio))
    if not isinstance(train_signal, (list, tuple)) or not isinstance(unseen_signal, (list, tuple)):
        raise ValueError("OTF_LADDER_SIGNAL_NOT_SEQUENCE")
    if len(train_signal) < 2 or len(train_signal) != len(unseen_signal):
        raise ValueError("OTF_LADDER_INVALID_SIGNAL_LENGTH")
    n_len = len(train_signal)
    y_train = tuple(_parse_exact_rational(v) for v in train_signal)
    y_unseen = tuple(_parse_exact_rational(v) for v in unseen_signal)

    e_train = _dot_q(y_train, y_train)
    e_unseen = _dot_q(y_unseen, y_unseen)
    if e_train == Fraction(0, 1) or e_unseen == Fraction(0, 1):
        raise ValueError("OTF_LADDER_ZERO_SIGNAL_ENERGY")

    if not isinstance(basis_vectors, (list, tuple)) or len(basis_vectors) < 2:
        raise ValueError("OTF_LADDER_INSUFFICIENT_RUNGS")
    if not isinstance(scrambled_null_corr_sq, (list, tuple)) or len(scrambled_null_corr_sq) != len(basis_vectors):
        raise ValueError("OTF_LADDER_NULL_LENGTH_MISMATCH")

    min_corr = _parse_exact_rational(min_unseen_corr_sq)
    if min_corr <= Fraction(0, 1) or min_corr > Fraction(1, 1):
        raise ValueError("OTF_LADDER_INVALID_MIN_CORR")
    min_eratio = _parse_exact_rational(min_remainder_energy_ratio)
    if min_eratio <= Fraction(0, 1) or min_eratio >= Fraction(1, 1):
        raise ValueError("OTF_LADDER_INVALID_MIN_ENERGY_RATIO")

    basis: list[tuple[Fraction, ...]] = []
    null_corrs: list[Fraction] = []
    for bv_raw, nc_raw in zip(basis_vectors, scrambled_null_corr_sq):
        if not isinstance(bv_raw, (list, tuple)) or len(bv_raw) != n_len:
            raise ValueError("OTF_LADDER_BASIS_DIM_MISMATCH")
        bv = tuple(_parse_exact_rational(x) for x in bv_raw)
        if _dot_q(bv, bv) == Fraction(0, 1):
            raise ValueError("OTF_LADDER_ZERO_BASIS_VECTOR")
        for prev in basis:
            if _dot_q(prev, bv) != Fraction(0, 1):
                raise ValueError("OTF_LADDER_NON_ORTHOGONAL_BASIS")
        nc = _parse_exact_rational(nc_raw)
        if nc < Fraction(0, 1) or nc > Fraction(1, 1):
            raise ValueError("OTF_LADDER_INVALID_NULL_CORR")
        basis.append(bv)
        null_corrs.append(nc)

    y_hat_tr = [Fraction(0, 1)] * n_len
    y_hat_un = [Fraction(0, 1)] * n_len
    rungs: list[dict[str, Any]] = []
    for idx, (bv, nc) in enumerate(zip(basis, null_corrs), start=1):
        bv_norm_sq = _dot_q(bv, bv)
        coeff_tr = _dot_q(y_train, bv) / bv_norm_sq
        coeff_un = _dot_q(y_unseen, bv) / bv_norm_sq
        for j in range(n_len):
            y_hat_tr[j] += coeff_tr * bv[j]
            y_hat_un[j] += coeff_un * bv[j]
        r_tr = tuple(y_train[j] - y_hat_tr[j] for j in range(n_len))
        r_un = tuple(y_unseen[j] - y_hat_un[j] for j in range(n_len))
        e_r_tr = _dot_q(r_tr, r_tr)
        e_r_un = _dot_q(r_un, r_un)
        e_ratio_tr = e_r_tr / e_train
        e_ratio_un = e_r_un / e_unseen
        if e_r_tr == Fraction(0, 1) or e_r_un == Fraction(0, 1):
            cross = Fraction(0, 1)
            corr_sq = Fraction(0, 1)
        else:
            cross = _dot_q(r_tr, r_un)
            corr_sq = (cross * cross) / (e_r_tr * e_r_un)
        pos_aligned = cross > Fraction(0, 1)
        structured = (
            e_ratio_tr >= min_eratio
            and e_ratio_un >= min_eratio
            and pos_aligned
            and corr_sq >= min_corr
            and corr_sq > nc
        )
        rungs.append(
            {
                "rung_k": idx,
                "train_coeff": _fmt_q(coeff_tr),
                "unseen_coeff": _fmt_q(coeff_un),
                "train_residual_energy_ratio": _fmt_q(e_ratio_tr),
                "unseen_residual_energy_ratio": _fmt_q(e_ratio_un),
                "unseen_positive_alignment": pos_aligned,
                "unseen_residual_corr_sq": _fmt_q(corr_sq),
                "scrambled_null_corr_sq": _fmt_q(nc),
                "structured_at_rung": structured,
            }
        )

    any_earlier = any(r["structured_at_rung"] for r in rungs[:-1])
    final_structured = rungs[-1]["structured_at_rung"]
    if final_structured:
        classification = "STRUCTURED_REMAINDER_SURVIVING_LADDER"
    elif any_earlier:
        classification = "FINITE_MODEL_MISSPECIFICATION"
    else:
        classification = "NO_STRUCTURED_REMAINDER"

    return {
        "signal_length": n_len,
        "ladder_depth": len(rungs),
        "train_energy": _fmt_q(e_train),
        "classification": classification,
        "single_model_test_confounded": any_earlier and not final_structured,
        "rungs": rungs,
    }


# ---------------------------------------------------------------------------
# 9. Own-Terms-First Rule-2 Symbol Operational-Utility Classifier (AUDIT-084R: OTF-TIGHT-04)
# ---------------------------------------------------------------------------


def certify_own_terms_symbol_utility(symbols: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> dict[str, Any]:
    """OTF-TIGHT-04: Classify proposed symbols strictly across 5 operational-utility tiers.

    Declared-record scope: validates the schema and classifies each caller-supplied symbol
    record deterministically from its declared boolean flags; it does NOT independently
    verify from the dicts alone that the underlying reproducibility or unseen-prediction
    checks were executed.
    """
    _verify_no_floats(symbols)
    if not isinstance(symbols, (list, tuple)) or len(symbols) == 0:
        raise ValueError("OTF_SYMBOLS_EMPTY_OR_NOT_SEQUENCE")

    seen_ops: set[str] = set()
    seen_syms: set[str] = set()
    counts = {
        "OPERATIONAL_NEW_PRIMITIVE": 0,
        "TYPED_ENGINEERING_OPERATOR": 0,
        "COMPOSITION_SHORTHAND_RENAMING": 0,
        "OVERLOADED_RENAMING": 0,
        "NON_REPRODUCIBLE_SYMBOL": 0,
    }
    records: list[dict[str, str]] = []

    for entry in symbols:
        if not isinstance(entry, dict) or frozenset(entry.keys()) != OWN_TERMS_SYMBOL_KEYS:
            raise ValueError("OTF_SYMBOL_SCHEMA_MISMATCH")
        sym = entry["symbol"]
        op_id = entry["op_id"]
        if not _is_clean_ascii(sym) or not _is_clean_ascii(op_id):
            raise ValueError("OTF_SYMBOL_INVALID_ID")
        op_key = op_id.lower()
        if op_key in seen_ops:
            raise ValueError("OTF_SYMBOL_DUPLICATE_OP_ID")
        seen_ops.add(op_key)
        sym_key = sym.lower()
        if sym_key in seen_syms:
            raise ValueError("OTF_SYMBOL_DUPLICATE")
        seen_syms.add(sym_key)

        repro = entry["reproducible_from_rules"]
        pred = entry["unseen_physical_prediction"]
        adds = entry["adds_rule_beyond_standard"]
        overload = entry["overloads_distinct_constructs"]
        if (
            not isinstance(repro, bool)
            or not isinstance(pred, bool)
            or not isinstance(adds, bool)
            or not isinstance(overload, bool)
        ):
            raise ValueError("OTF_SYMBOL_INVALID_BOOL_FLAG")

        if not repro:
            cls = "NON_REPRODUCIBLE_SYMBOL"
        elif overload:
            cls = "OVERLOADED_RENAMING"
        elif adds and pred:
            cls = "OPERATIONAL_NEW_PRIMITIVE"
        elif adds:
            cls = "TYPED_ENGINEERING_OPERATOR"
        else:
            cls = "COMPOSITION_SHORTHAND_RENAMING"

        counts[cls] += 1
        records.append({"op_id": op_id, "symbol": sym, "classification": cls})

    total = len(symbols)
    renaming_total = counts["COMPOSITION_SHORTHAND_RENAMING"] + counts["OVERLOADED_RENAMING"]
    return {
        "total_symbols": total,
        "counts": counts,
        "renaming_total": renaming_total,
        "renaming_ratio": _fmt_q(Fraction(renaming_total, total)),
        "new_primitive_ratio": _fmt_q(Fraction(counts["OPERATIONAL_NEW_PRIMITIVE"], total)),
        "records": records,
    }


def _run_expected_rejection(fn: Callable[[], Any], expected_code: str) -> dict[str, Any]:
    try:
        fn()
    except ValueError as exc:
        actual = str(exc)
        return {
            "rejected": actual == expected_code,
            "expected_code": expected_code,
            "actual_code": actual,
        }
    return {
        "rejected": False,
        "expected_code": expected_code,
        "actual_code": None,
    }


def run_v2_gates_self_test() -> dict[str, Any]:
    """Run deterministic zero-float self-test across all 9 Aletheia v2.0 gates (pass + rejection controls)."""
    payload_bytes = (
        json.dumps({"header_alpha": "4", "vector_entries": ["3", "2", "1"]}, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    r6_rules = {
        "rule_id": "aletheia.v2.selftest.r6r7",
        "expected_check_ids": ["r7_sha256", "r7_sq_norm", "r6_alpha"],
        "min_sq_norm": "0",
        "max_sq_norm": "20",
        "expected_header_alpha": "4",
        "max_vector_dim": 8,
    }
    r6_sub = {
        "declared_sha256": hashlib.sha256(payload_bytes).hexdigest(),
        "declared_sq_norm": "14",
        "declared_header_alpha": "4",
        "declared_status": "PASS",
        "submitter_rule_overrides": {},
    }
    r6r7_ok = evaluate_r6_r7_gate(r6_rules, r6_sub, payload_bytes)
    r6r7_rej = _run_expected_rejection(
        lambda: evaluate_r6_r7_gate({**r6_rules, "expected_check_ids": ["no_such_check_zzz"]}, r6_sub, payload_bytes),
        "R6_UNKNOWN_CHECK_ID",
    )

    def _strict_gate(rec: Any) -> bool:
        return (
            isinstance(rec, dict)
            and isinstance(rec.get("flag"), bool)
            and rec["flag"] is True
            and rec.get("verdict") == "VERIFIED"
        )

    r3_res = certify_two_direction_r3(
        _strict_gate,
        {"flag": True, "verdict": "VERIFIED"},
        {"flag": True, "verdict": "FAILED"},
        [("dir1_int1", {"flag": 1, "verdict": "VERIFIED"})],
        [("dir2_int1_note_d", {"flag": 1, "verdict": "FAILED"})],
    )
    r3_rej = _run_expected_rejection(
        lambda: certify_two_direction_r3(
            _strict_gate,
            {"flag": True, "verdict": "VERIFIED"},
            {"flag": True, "verdict": "FAILED"},
            [("dup", {"flag": 1, "verdict": "VERIFIED"})],
            [("DUP", {"flag": 1, "verdict": "FAILED"})],
        ),
        "R3_DUPLICATE_LABEL",
    )

    sampled_not_shown = evaluate_sampled_integrity(1, 4, 0)
    sampled_rej = _run_expected_rejection(
        lambda: evaluate_sampled_integrity(0, 0, 0),
        "SAMPLED_INVALID_TOTAL",
    )

    oracle_ok = certify_oracle_contract(
        {
            "oracle_class": "anchor",
            "evidence_basis": "external_domain_data",
            "feedback_channel": "none_to_proposer_spec_owner_only",
        }
    )
    oracle_rej = _run_expected_rejection(
        lambda: certify_oracle_contract(
            {
                "oracle_class": "exact",
                "evidence_basis": "random_finite_sample_exact_arithmetic",
                "feedback_channel": "full_counterexample_and_repair",
            }
        ),
        "ORACLE_EXACT_REQUIRES_NON_SAMPLED_BASIS",
    )

    phi = [["1", "0", "0", "0"], ["0", "1", "0", "0"]]
    latch_oblique = certify_gate8_subspace_latch(phi, ["1", "0", "2", "0"], "5", "2")
    latch_blind = certify_gate8_subspace_latch(phi, ["3", "4", "0", "0"], "0", "2")
    latch_rej = _run_expected_rejection(
        lambda: certify_gate8_subspace_latch(phi, ["0", "0", "0", "0"], "0", "2"),
        "LATCH_ZERO_AUDIT_VECTOR",
    )

    ts_spec = {
        "proposed_verdict": "TRANSFORMED_EXACT",
        "literal_failed": True,
        "literal_failure_witness": "row sums [3/2, 3/4] != [1, 1]",
        "families_searched": ["T1_GAUGE_SIMILARITY"],
        "transform_family": "T1_GAUGE_SIMILARITY",
        "preserved_invariant_core": "tr=1, det=0 similarity spectrum",
        "modified_hypotheses": "non-stochastic diagonal gauge similarity",
        "transform_rank": 2,
        "transform_dof": 1,
        "held_out_constraints": 4,
        "fixed_globally": True,
        "target_pass_count": 4,
        "target_total_count": 4,
        "null_false_passes": 0,
        "null_total": 10,
        "max_null_rate": "1/10",
        "residual_gap": "0",
        "max_residual_gap": "0",
        "relabelled_as_literal": False,
        "surviving_obstruction": None,
        "obstruction_survives_all_searched": False,
    }
    ts_rescue = certify_transformational_steelman(ts_spec)
    ts_rej = _run_expected_rejection(
        lambda: certify_transformational_steelman({**ts_spec, "proposed_verdict": "FALSIFIED_RAW"}),
        "G4_RAW_FALSIFIED_FORBIDDEN",
    )

    otf_spec = {
        "measurable_definition_present": True,
        "pinned_net_ids": ["net_rate", "net_quant"],
        "per_net_alpha": "1/50",
        "max_fwer": "1/20",
        "min_signal_margin": "1/10",
        "max_control_score": "1/20",
        "held_out_verified": True,
        "second_instrument_verified": True,
    }
    otf_rows = [
        {
            "net_id": "net_rate",
            "axis": "rate",
            "observed_score": "3/10",
            "observed_p_value": "1/100",
            "iid_null_score": "1/20",
            "spectrum_null_score": "1/10",
            "control_score": "1/25",
        },
        {
            "net_id": "net_quant",
            "axis": "quantization",
            "observed_score": "2/5",
            "observed_p_value": "1/100",
            "iid_null_score": "1/20",
            "spectrum_null_score": "1/10",
            "control_score": "1/20",
        },
    ]
    otf_ok = certify_own_terms_phase1(otf_spec, otf_rows)
    otf_rej = _run_expected_rejection(
        lambda: certify_own_terms_phase1({**otf_spec, "pinned_net_ids": ["only_one"]}, otf_rows[:1]),
        "OTF_INSUFFICIENT_PINNED_NETS",
    )

    ladder_ok = certify_own_terms_model_ladder(
        ["1", "2", "3", "4"],
        ["2", "2", "3", "4"],
        [["1", "0", "0", "0"], ["0", "1", "0", "0"]],
        ["1/10", "1/10"],
        "1/2",
        "1/4",
    )
    ladder_rej = _run_expected_rejection(
        lambda: certify_own_terms_model_ladder(
            ["1", "2", "3", "4"],
            ["2", "2", "3", "4"],
            [["1", "1", "0", "0"], ["1", "0", "0", "0"]],
            ["1/10", "1/10"],
            "1/2",
            "1/4",
        ),
        "OTF_LADDER_NON_ORTHOGONAL_BASIS",
    )

    sym_ok = certify_own_terms_symbol_utility(
        [
            {
                "symbol": "|/|",
                "op_id": "OP-01",
                "reproducible_from_rules": True,
                "unseen_physical_prediction": False,
                "adds_rule_beyond_standard": False,
                "overloads_distinct_constructs": False,
            },
            {
                "symbol": "_|T",
                "op_id": "OP-08",
                "reproducible_from_rules": True,
                "unseen_physical_prediction": False,
                "adds_rule_beyond_standard": True,
                "overloads_distinct_constructs": False,
            },
        ]
    )
    sym_rej = _run_expected_rejection(
        lambda: certify_own_terms_symbol_utility([]),
        "OTF_SYMBOLS_EMPTY_OR_NOT_SEQUENCE",
    )

    checks = {
        "r6_r7_accept": (
            r6r7_ok.get("status") == "ACCEPTED"
            and r6r7_ok.get("measured_sq_norm") == "14"
            and r6r7_ok.get("executed_checks") == {"r7_sha256": "PASS", "r7_sq_norm": "PASS", "r6_alpha": "PASS"}
        ),
        "r6_r7_reject": r6r7_rej["rejected"] is True,
        "two_direction_r3_accept": (
            r3_res.get("passed") is True
            and r3_res.get("dir1_rejected") == 1
            and r3_res.get("dir2_stayed_rejected") == 1
        ),
        "two_direction_r3_reject": r3_rej["rejected"] is True,
        "sampled_not_shown": (
            sampled_not_shown.get("verdict") == "NOT_SHOWN"
            and sampled_not_shown.get("passed") is False
            and sampled_not_shown.get("coverage_fraction") == "1/4"
        ),
        "sampled_reject": sampled_rej["rejected"] is True,
        "oracle_contract_accept": (
            oracle_ok.get("valid") is True
            and oracle_ok.get("failure_routes_to") == "spec_owner"
        ),
        "oracle_contract_reject": oracle_rej["rejected"] is True,
        "gate8_oblique_latch": (
            latch_oblique.get("decision") == "LATCH_HALT"
            and latch_oblique.get("halt") is True
            and latch_oblique.get("sin2_theta_attenuation") == "4/5"
        ),
        "gate8_blind_audit": (
            latch_blind.get("decision") == "BLIND_AUDIT_IN_COL_PHI"
            and latch_blind.get("halt") is True
            and latch_blind.get("sin2_theta_attenuation") == "0"
        ),
        "gate8_reject": latch_rej["rejected"] is True,
        "law2b_steelman_accept": (
            ts_rescue.get("admitted") is True
            and ts_rescue.get("status") == "CERTIFIED_TRANSFORMED_EXACT"
            and ts_rescue.get("residual_gap") == "0"
        ),
        "law2b_steelman_reject": ts_rej["rejected"] is True,
        "own_terms_phase1_accept": (
            otf_ok.get("certified") is True
            and otf_ok.get("decision") == "P1_VERIFIED_INVARIANT"
            and otf_ok.get("nets_verified") == 2
            and otf_ok.get("axes_verified") == ["quantization", "rate"]
        ),
        "own_terms_phase1_reject": otf_rej["rejected"] is True,
        "own_terms_model_ladder_accept": (
            ladder_ok.get("classification") == "STRUCTURED_REMAINDER_SURVIVING_LADDER"
            and ladder_ok.get("single_model_test_confounded") is False
        ),
        "own_terms_model_ladder_reject": ladder_rej["rejected"] is True,
        "own_terms_symbol_utility_accept": (
            sym_ok.get("renaming_ratio") == "1/2"
            and sym_ok.get("counts", {}).get("TYPED_ENGINEERING_OPERATOR") == 1
        ),
        "own_terms_symbol_utility_reject": sym_rej["rejected"] is True,
    }
    passed = all(checks.values())

    out = {
        "schema": "aletheia.gates_v2.selftest.v2",
        "passed": passed,
        "verdict": "ALETHEIA_V2_GATES_VERIFIED" if passed else "ALETHEIA_V2_GATES_FAILED",
        "checks": checks,
        "r6_r7": r6r7_ok,
        "r6_r7_rejection": r6r7_rej,
        "two_direction_r3": r3_res,
        "two_direction_r3_rejection": r3_rej,
        "sampled_not_shown": sampled_not_shown,
        "sampled_rejection": sampled_rej,
        "oracle_contract": oracle_ok,
        "oracle_contract_rejection": oracle_rej,
        "gate8_oblique_latch": latch_oblique,
        "gate8_blind_audit": latch_blind,
        "gate8_rejection": latch_rej,
        "law2b_steelman": ts_rescue,
        "law2b_rejection": ts_rej,
        "own_terms_phase1": otf_ok,
        "own_terms_phase1_rejection": otf_rej,
        "own_terms_model_ladder": ladder_ok,
        "own_terms_model_ladder_rejection": ladder_rej,
        "own_terms_symbol_utility": sym_ok,
        "own_terms_symbol_utility_rejection": sym_rej,
    }
    _verify_no_floats(out)
    out["canonical_sha256"] = hashlib.sha256(
        json.dumps(out, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return out
