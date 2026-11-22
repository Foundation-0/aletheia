"""
`aletheia.gates_v2`: Pure-Q Zero-Float v2.0 Gate-Contract Engine.

Implements all verified Round-10 / v2.0 Aletheia governance gates in pure Python 3
standard library (`int`, `fractions.Fraction`, zero floats on trust paths, zero bare asserts):
  1. `evaluate_r6_r7_gate` — Contract R6 (owner-pinned checks) & R7 (measured from bytes, not declared)
  2. `certify_two_direction_r3` — Two-Direction R3 (Dir (i) accept->reject & Dir (ii) reject stays reject)
  3. `evaluate_sampled_integrity` — aletheia#3 §4 (partial zero-hit coverage is NOT_SHOWN, never PASS)
  4. `certify_oracle_contract` — aletheia#3 §§5-7 (exact arithmetic != exact oracle; anchor vs replay; feedback channels)
  5. `certify_gate8_subspace_latch` — aletheia#3 §8 (exact Q col(Phi) projection, sin^2(theta), BLIND_AUDIT_IN_COL_PHI halt)
  6. `certify_transformational_steelman` — Law 2b (AUDIT-088R: 7 morphism families T1-T7 + 4 anti-epicycle guards G1-G4)
  7. `certify_own_terms_phase1` — Own-Terms-First Phase-1 Gate (AUDIT-084R: OTF-TIGHT-01..05, no-float Rule-6 check)
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from typing import Any, Callable


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

MORPHISM_FAMILIES = frozenset(
    {
        "T1_GAUGE_SIMILARITY",
        "T2_AFFINE_BREGMAN_SHIFT",
        "T3_DIVERGENCE_CHART",
        "T4_SPECTRAL_PSD_SHIFT",
        "T5_SEMIRING_TROPICALIZATION",
        "T6_SUBSPACE_QUOTIENT_DUAL",
        "T7_MONOTONE_ORDER_DOMAIN_SPLIT",
    }
)
STEELMAN_KEYS = frozenset(
    {
        "proposed_verdict",
        "families_searched",
        "literal_failure_witness",
        "transform_family",
        "preserved_invariant_core",
        "modified_hypotheses",
        "transform_rank",
        "transform_dof",
        "held_out_constraints",
        "fixed_globally",
        "null_false_passes",
        "null_total",
        "max_null_rate",
        "max_residual_gap",
        "surviving_obstruction",
    }
)
MAX_PROTOCOL_NULL_RATE = Fraction(1, 10)

OWN_TERMS_SPEC_KEYS = frozenset(
    {
        "measurable_definition_present",
        "pinned_net_ids",
        "per_net_alpha",
        "max_fwer",
        "min_signal_margin",
        "max_control_score",
    }
)
OWN_TERMS_MEAS_KEYS = frozenset(
    {
        "net_id",
        "observed_score",
        "iid_null_score",
        "spectrum_null_score",
        "control_score",
    }
)


def _is_strict_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_clean_ascii(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) > 0
        and value == value.strip()
        and all(32 <= ord(ch) <= 126 for ch in value)
    )


def _is_lower_hex(value: object, expected_len: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == expected_len
        and all(ch in "0123456789abcdef" for ch in value)
    )


def _fmt_q(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}" if value.denominator != 1 else str(value.numerator)


def _verify_no_floats(obj: object) -> None:
    if isinstance(obj, float):
        raise ValueError("FLOAT_FORBIDDEN")
    if isinstance(obj, dict):
        for k, v in obj.items():
            _verify_no_floats(k)
            _verify_no_floats(v)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _verify_no_floats(item)


def _parse_exact_rational(value: object) -> Fraction:
    if isinstance(value, Fraction):
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
    if not digits or not digits.isdigit():
        raise ValueError("RATIONAL_INVALID_NUMERATOR")
    num = -int(digits) if neg else int(digits)
    if len(parts) == 1:
        return Fraction(num, 1)
    den_s = parts[1]
    if not den_s or not den_s.isdigit():
        raise ValueError("RATIONAL_INVALID_DENOMINATOR")
    den = int(den_s)
    if den <= 0:
        raise ValueError("RATIONAL_NONPOSITIVE_DENOMINATOR")
    return Fraction(num, den)


def _strict_typed_equal(left: object, right: object) -> bool:
    """Recursive equality preserving exact runtime types (1 != True, 1 != 1.0)."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        if set(left.keys()) != set(right.keys()):
            return False
        return all(_strict_typed_equal(left[k], right[k]) for k in left)
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(_strict_typed_equal(x, y) for x, y in zip(left, right))
    return left == right


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
    if not isinstance(parsed, dict):
        raise ValueError("PAYLOAD_ROOT_NOT_OBJECT")
    return parsed


# ---------------------------------------------------------------------------
# 1. R6 (Pinned Checks) & R7 (Measured, Not Declared)
# ---------------------------------------------------------------------------


def evaluate_r6_r7_gate(
    pinned_rules: dict[str, Any],
    submission: dict[str, Any],
    artifact_bytes: bytes,
) -> dict[str, Any]:
    """Fail-closed R6 (owner-pinned rules) + R7 (byte-recomputed measurements) gate."""
    if not isinstance(pinned_rules, dict) or frozenset(pinned_rules.keys()) != PINNED_RULE_KEYS:
        raise ValueError("R6_PINNED_RULES_SCHEMA_MISMATCH")
    rule_id = pinned_rules["rule_id"]
    if not _is_clean_ascii(rule_id):
        raise ValueError("R6_INVALID_RULE_ID")
    check_ids = pinned_rules["expected_check_ids"]
    if not isinstance(check_ids, (list, tuple)) or len(check_ids) == 0:
        raise ValueError("R6_EMPTY_CHECK_IDS")
    if any(not _is_clean_ascii(cid) for cid in check_ids):
        raise ValueError("R6_INVALID_CHECK_ID")
    if len({cid.lower() for cid in check_ids}) != len(check_ids):
        raise ValueError("R6_DUPLICATE_CHECK_ID")

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

    if not isinstance(submission, dict) or frozenset(submission.keys()) != SUBMISSION_KEYS:
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

    measured_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
    declared_sha256 = submission["declared_sha256"]
    if not _is_lower_hex(declared_sha256, 64):
        raise ValueError("R7_INVALID_DECLARED_SHA256")
    if declared_sha256 != measured_sha256:
        raise ValueError("R7_DECLARED_SHA256_MISMATCH")

    payload = _parse_strict_json_bytes(artifact_bytes)
    if frozenset(payload.keys()) != PAYLOAD_KEYS:
        raise ValueError("R7_PAYLOAD_SCHEMA_MISMATCH")

    measured_alpha = _parse_exact_rational(payload["header_alpha"])
    entries = payload["vector_entries"]
    if not isinstance(entries, list) or len(entries) == 0:
        raise ValueError("R7_EMPTY_VECTOR_ENTRIES")
    if len(entries) > max_dim:
        raise ValueError("R6_VECTOR_DIM_EXCEEDS_MAX")

    vec = [_parse_exact_rational(x) for x in entries]
    measured_sq_norm = sum((v * v for v in vec), Fraction(0, 1))

    declared_sq = _parse_exact_rational(submission["declared_sq_norm"])
    declared_alpha = _parse_exact_rational(submission["declared_header_alpha"])
    if declared_sq != measured_sq_norm:
        raise ValueError("R7_DECLARED_NORM_MISMATCH")
    if declared_alpha != measured_alpha:
        raise ValueError("R7_DECLARED_ALPHA_MISMATCH")

    if measured_alpha != exp_alpha:
        raise ValueError("R6_HEADER_ALPHA_OUT_OF_SPEC")
    if measured_sq_norm < min_sq:
        raise ValueError("R6_MEASURED_NORM_BELOW_MIN")
    if measured_sq_norm > max_sq:
        raise ValueError("R6_MEASURED_NORM_ABOVE_MAX")

    return {
        "status": "ACCEPTED",
        "rule_id": rule_id,
        "checked_ids": list(check_ids),
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


def _dot_q(u: list[Fraction], v: list[Fraction]) -> Fraction:
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
    """Fail-closed Law 2b gate enforcing 7-family morphism search + 4 anti-epicycle guards."""
    _verify_no_floats(spec)
    if not isinstance(spec, dict) or frozenset(spec.keys()) != STEELMAN_KEYS:
        raise ValueError("TS_SCHEMA_MISMATCH")

    verdict = spec["proposed_verdict"]
    if verdict == "FALSIFIED_RAW":
        raise ValueError("G4_RAW_FALSIFIED_FORBIDDEN")
    if verdict not in ("TRANSFORMED_EXACT", "BOUNDED_TRANSFORM_CORE", "INVARIANT_FALSIFIED"):
        raise ValueError("TS_INVALID_VERDICT")

    families = spec["families_searched"]
    if not isinstance(families, (list, tuple)) or len(families) == 0:
        raise ValueError("TS_EMPTY_FAMILIES_SEARCHED")
    if any(not isinstance(f, str) or f not in MORPHISM_FAMILIES for f in families):
        raise ValueError("TS_UNKNOWN_MORPHISM_FAMILY")
    if len(set(families)) != len(families):
        raise ValueError("TS_DUPLICATE_MORPHISM_FAMILY")

    if not _is_clean_ascii(spec["literal_failure_witness"]):
        raise ValueError("G3_MISSING_LITERAL_FAILURE_WITNESS")

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

    null_fp = spec["null_false_passes"]
    null_tot = spec["null_total"]
    if not _is_strict_int(null_tot) or null_tot <= 0:
        raise ValueError("G1_EMPTY_NULL_SUITE")
    if not _is_strict_int(null_fp) or null_fp < 0 or null_fp > null_tot:
        raise ValueError("G1_INVALID_NULL_FALSE_PASSES")

    max_null_rate = _parse_exact_rational(spec["max_null_rate"])
    if max_null_rate < Fraction(0, 1) or max_null_rate > MAX_PROTOCOL_NULL_RATE:
        raise ValueError("G1_MAX_NULL_RATE_OUT_OF_RANGE")

    null_rate = Fraction(null_fp, null_tot)
    if null_rate > max_null_rate:
        raise ValueError("G1_NULL_FALSE_PASS_EXCEEDED")

    max_gap = _parse_exact_rational(spec["max_residual_gap"])
    if max_gap < Fraction(0, 1):
        raise ValueError("G3_NEGATIVE_RESIDUAL_GAP")

    t_family = spec["transform_family"]
    core = spec["preserved_invariant_core"]
    mod_hyp = spec["modified_hypotheses"]
    obs = spec["surviving_obstruction"]

    if verdict == "INVARIANT_FALSIFIED":
        if len(families) != len(MORPHISM_FAMILIES):
            raise ValueError("G4_INCOMPLETE_MORPHISM_SEARCH")
        if not _is_clean_ascii(obs):
            raise ValueError("G4_MISSING_SURVIVING_OBSTRUCTION")
        if t_family is not None or core is not None or mod_hyp is not None or t_rank != 0 or t_dof != 0:
            raise ValueError("G4_CONTRADICTORY_RESCUE_FIELDS_ON_FALSIFIED")
        if max_gap == Fraction(0, 1):
            raise ValueError("G4_FALSIFIED_HAS_ZERO_GAP")
        status = "CERTIFIED_INVARIANT_FALSIFIED"
    else:
        if obs is not None:
            raise ValueError("G0_CONTRADICTORY_OBSTRUCTION_ON_RESCUE")
        if not isinstance(t_family, str) or t_family not in families:
            raise ValueError("G3_TRANSFORM_FAMILY_NOT_SEARCHED")
        if not _is_clean_ascii(core) or not _is_clean_ascii(mod_hyp):
            raise ValueError("G3_MISSING_SCOPE_DELTA")
        if t_rank <= 0:
            raise ValueError("G1_DEGENERATE_ZERO_RANK_TRANSFORM")
        if t_dof >= constraints:
            raise ValueError("G2_DOF_EXCEEDS_CONSTRAINTS")
        if max_null_rate > Fraction(0, 1) and Fraction(null_tot, 1) * max_null_rate < Fraction(1, 1):
            raise ValueError("G1_INSUFFICIENT_NULL_RESOLUTION")
        if verdict == "TRANSFORMED_EXACT" and max_gap != Fraction(0, 1):
            raise ValueError("G3_EXACT_RESCUE_HAS_NONZERO_GAP")
        status = f"CERTIFIED_{verdict}"

    return {
        "admitted": True,
        "status": status,
        "proposed_verdict": verdict,
        "families_searched_count": len(families),
        "null_false_pass_rate": _fmt_q(null_rate),
        "max_residual_gap": _fmt_q(max_gap),
        "dof_margin": constraints - t_dof,
    }


# ---------------------------------------------------------------------------
# 7. Own-Terms-First Phase-1 Gate (AUDIT-084R: OTF-TIGHT-01..05)
# ---------------------------------------------------------------------------


def certify_own_terms_phase1(
    pinned_spec: dict[str, Any],
    net_measurements: list[dict[str, Any]],
) -> dict[str, Any]:
    """Own-Terms-First Phase-1 gate (R6 pre-pinned nets, Bonferroni FWER, Tier-4A/4B nulls, Rule 5 & Rule 6)."""
    # OTF-BUG-01 fix: reject floats unconditionally BEFORE Rule-6 early return!
    _verify_no_floats(pinned_spec)
    _verify_no_floats(net_measurements)

    if not isinstance(pinned_spec, dict) or frozenset(pinned_spec.keys()) != OWN_TERMS_SPEC_KEYS:
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

    if len(pinned_ids) == 0:
        raise ValueError("OTF_EMPTY_PINNED_NETS")
    if any(not _is_clean_ascii(nid) for nid in pinned_ids):
        raise ValueError("OTF_INVALID_NET_ID")
    pinned_low = [nid.lower() for nid in pinned_ids]
    if len(set(pinned_low)) != len(pinned_low):
        raise ValueError("OTF_DUPLICATE_PINNED_NET_ID")

    alpha = _parse_exact_rational(pinned_spec["per_net_alpha"])
    max_fwer = _parse_exact_rational(pinned_spec["max_fwer"])
    min_margin = _parse_exact_rational(pinned_spec["min_signal_margin"])
    max_ctrl = _parse_exact_rational(pinned_spec["max_control_score"])

    if alpha <= Fraction(0, 1) or alpha > Fraction(1, 1):
        raise ValueError("OTF_INVALID_ALPHA")
    if max_fwer <= Fraction(0, 1) or max_fwer > Fraction(1, 1):
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
    min_iid_margin: Fraction | None = None
    min_spec_margin: Fraction | None = None
    min_ctrl_margin: Fraction | None = None

    for row in net_measurements:
        if not isinstance(row, dict) or frozenset(row.keys()) != OWN_TERMS_MEAS_KEYS:
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

        obs = _parse_exact_rational(row["observed_score"])
        iid_n = _parse_exact_rational(row["iid_null_score"])
        spec_n = _parse_exact_rational(row["spectrum_null_score"])
        ctrl = _parse_exact_rational(row["control_score"])

        # Magnitude-safe null margins (OTF-BUG-02 fix)
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

        min_iid_margin = iid_m if min_iid_margin is None else min(min_iid_margin, iid_m)
        min_spec_margin = spec_m if min_spec_margin is None else min(min_spec_margin, spec_m)
        min_ctrl_margin = ctrl_m if min_ctrl_margin is None else min(min_ctrl_margin, ctrl_m)

    return {
        "certified": True,
        "decision": "P1_VERIFIED_INVARIANT",
        "nets_verified": len(seen_low),
        "bonferroni_fwer": _fmt_q(bonf_fwer),
        "min_iid_margin": _fmt_q(min_iid_margin if min_iid_margin is not None else Fraction(0, 1)),
        "min_spectrum_margin": _fmt_q(min_spec_margin if min_spec_margin is not None else Fraction(0, 1)),
        "min_control_margin": _fmt_q(min_ctrl_margin if min_ctrl_margin is not None else Fraction(0, 1)),
    }


def run_v2_gates_self_test() -> dict[str, Any]:
    """Run deterministic zero-float self-test across all 7 Aletheia v2.0 gates."""
    payload_bytes = (json.dumps({"header_alpha": "4", "vector_entries": ["3", "2", "1"]}, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    r6r7_ok = evaluate_r6_r7_gate(
        {
            "rule_id": "aletheia.v2.selftest.r6r7",
            "expected_check_ids": ["r7_sha256", "r7_sq_norm", "r6_alpha"],
            "min_sq_norm": "0",
            "max_sq_norm": "20",
            "expected_header_alpha": "4",
            "max_vector_dim": 8,
        },
        {
            "declared_sha256": hashlib.sha256(payload_bytes).hexdigest(),
            "declared_sq_norm": "14",
            "declared_header_alpha": "4",
            "declared_status": "PASS",
            "submitter_rule_overrides": {},
        },
        payload_bytes,
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
    sampled_not_shown = evaluate_sampled_integrity(1, 4, 0)
    oracle_ok = certify_oracle_contract(
        {
            "oracle_class": "anchor",
            "evidence_basis": "external_domain_data",
            "feedback_channel": "none_to_proposer_spec_owner_only",
        }
    )
    phi = [["1", "0", "0", "0"], ["0", "1", "0", "0"]]
    latch_oblique = certify_gate8_subspace_latch(phi, ["1", "0", "2", "0"], "5", "2")
    latch_blind = certify_gate8_subspace_latch(phi, ["3", "4", "0", "0"], "0", "2")

    ts_rescue = certify_transformational_steelman(
        {
            "proposed_verdict": "TRANSFORMED_EXACT",
            "families_searched": ["T1_GAUGE_SIMILARITY"],
            "literal_failure_witness": "row sums [3/2, 3/4] != [1, 1]",
            "transform_family": "T1_GAUGE_SIMILARITY",
            "preserved_invariant_core": "tr=1, det=0 similarity spectrum",
            "modified_hypotheses": "non-stochastic diagonal gauge similarity",
            "transform_rank": 2,
            "transform_dof": 1,
            "held_out_constraints": 4,
            "fixed_globally": True,
            "null_false_passes": 0,
            "null_total": 10,
            "max_null_rate": "1/10",
            "max_residual_gap": "0",
            "surviving_obstruction": None,
        }
    )
    otf_ok = certify_own_terms_phase1(
        {
            "measurable_definition_present": True,
            "pinned_net_ids": ["rate_a", "rate_b"],
            "per_net_alpha": "1/50",
            "max_fwer": "1/20",
            "min_signal_margin": "1/10",
            "max_control_score": "1/20",
        },
        [
            {"net_id": "rate_a", "observed_score": "3/10", "iid_null_score": "1/20", "spectrum_null_score": "1/10", "control_score": "1/25"},
            {"net_id": "rate_b", "observed_score": "4/10", "iid_null_score": "1/20", "spectrum_null_score": "1/10", "control_score": "1/20"},
        ],
    )

    out = {
        "schema": "aletheia.gates_v2.selftest.v1",
        "passed": True,
        "verdict": "ALETHEIA_V2_GATES_VERIFIED",
        "r6_r7": r6r7_ok,
        "two_direction_r3": r3_res,
        "sampled_not_shown": sampled_not_shown,
        "oracle_contract": oracle_ok,
        "gate8_oblique_latch": latch_oblique,
        "gate8_blind_audit": latch_blind,
        "law2b_steelman": ts_rescue,
        "own_terms_phase1": otf_ok,
    }
    canon = json.dumps(out, sort_keys=True, separators=(",", ":"))
    out["canonical_sha256"] = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    return out
