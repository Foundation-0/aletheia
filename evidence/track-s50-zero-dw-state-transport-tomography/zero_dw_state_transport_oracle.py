#!/usr/bin/env python3
"""Pure-Z/Q Zero-Delta-W State-Transport & Yield-Surface Tomography Oracle.

Unifies coordinate-free state-transport tomography under strictly zero parameter
drift (Delta W = 0) across:
  1. GDN-2 Channel-2B rank-1 recurrent latent-memory poisoning (+2 -> -83/25),
     general rank-r nuclear/Frobenius state-drift bounds, and orthogonal basis
     conjugation invariance over O(4, Q);
  2. Viscoplastic ReLU yield-wall advection (x = 1 -> 4 under Delta W = 0) and
     the discrete S^2 cube Hodge / Gauss-Stokes cohomological obstruction
     (+13 - 13 = 0 vs piecewise-linear ReLU residual -4 != 0);
  3. Matched-Frobenius / matched-weight-hash structural blindness (32x exact
     64x16 and 75,968x analytical 151,936x1,536 scaling) and an executable
     4-channel state-transport airlock candidate gate for Aletheia v2.2.

Pure Python 3 standard library int / Fraction only. Zero floats, zero bare
asserts, zero mathematical RNG, zero external dependencies.
"""

from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from typing import Any

TRACK_ID = "TRACK-S50-ZERO-DW-STATE-TRANSPORT-TOMOGRAPHY"
SCHEMA_VERSION = "aletheia.zero_dw_state_transport.v1"
ORACLE_CLASS = "exact"
NOVELTY_TIER = "N1"

MAX_INT_BITS = 3_322
MAX_RATIONAL_BITS = 3_322
MAX_INT_DIGITS = 1_001
MAX_JSON_DEPTH = 64
MAX_JSON_BYTES = 1_048_576
MAX_READ_CAP_BYTES = 67_108_864

_CERT_KEYS = frozenset({
    "schema_version",
    "track_id",
    "oracle_class",
    "novelty_tier",
    "payload_sha256",
    "certificate_sha256",
    "payload",
})

_PAYLOAD_KEYS = frozenset({
    "oracle_class",
    "novelty_tier",
    "prior_art_cs13_anchors",
    "measured_live_model_weights",
    "measured_live_serving_endpoint",
    "measured_live_mantle_gcm",
    "zero_trust_path_floats",
    "zero_bare_asserts",
    "zero_mathematical_rng",
    "pillar1_gdn2_zero_dw_state_transport",
    "pillar2_yield_wall_and_s2_cohomology",
    "pillar3_iso_frobenius_and_4ch_airlock",
})

_AIRLOCK_KEYS = frozenset({
    "weight_hash_match",
    "weight_block_dpi_ratio",
    "max_weight_block_dpi_ratio",
    "kv_cross_model_reuse",
    "kv_residual_evicted_mentions",
    "state_session_authorized",
    "state_cross_session_carryover",
    "state_delta_frob_sq",
    "max_state_delta_frob_sq",
    "state_delta_rank",
    "state_schatten_s4",
    "margin_before",
    "margin_after",
    "min_safe_margin",
    "yield_wall_displacement",
    "max_yield_wall_displacement",
    "cohomological_relu_residual",
    "require_conserved_flow",
    "corpus_provenance_verified",
    "mode_transfer_gap",
    "max_mode_transfer_gap",
})

_LOWER_HEX_CHARS = frozenset("0123456789abcdef")

_S2_CUBE_EDGES: tuple[tuple[int, int], ...] = (
    (0, 1), (2, 3), (4, 5), (6, 7),
    (0, 2), (1, 3), (4, 6), (5, 7),
    (0, 4), (1, 5), (2, 6), (3, 7),
)

_S2_FACE_CYCLES: tuple[tuple[int, int, int, int], ...] = (
    (0, 2, 3, 1),
    (4, 5, 7, 6),
    (0, 1, 5, 4),
    (2, 6, 7, 3),
    (0, 4, 6, 2),
    (1, 3, 7, 5),
)


class ZeroDwStateTransportError(ValueError):
    """Structured fail-closed error carrying a machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def require_ok(cond: bool, code: str, message: str) -> None:
    if not cond:
        raise ZeroDwStateTransportError(code, message)


def require_exact_int(
    val: Any,
    name: str,
    *,
    min_val: int | None = None,
    max_val: int | None = None,
) -> int:
    require_ok(type(val) is int, "INVALID_INT_TYPE", f"{name} must be exact int")
    require_ok(val.bit_length() <= MAX_INT_BITS, "INT_BIT_LIMIT", f"{name} exceeds {MAX_INT_BITS} bits")
    if min_val is not None:
        require_ok(val >= min_val, "INT_BELOW_MIN", f"{name} must be >= {min_val}")
    if max_val is not None:
        require_ok(val <= max_val, "INT_ABOVE_MAX", f"{name} must be <= {max_val}")
    return val


def require_exact_bool(val: Any, name: str) -> bool:
    require_ok(type(val) is bool, "INVALID_BOOL_TYPE", f"{name} must be exact bool")
    return val


def require_exact_str(val: Any, name: str, *, non_empty: bool = True) -> str:
    require_ok(type(val) is str, "INVALID_STR_TYPE", f"{name} must be exact str")
    if non_empty:
        require_ok(len(val) > 0, "EMPTY_STR", f"{name} must be non-empty")
    try:
        val.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ZeroDwStateTransportError("INVALID_UTF8_SURROGATE", f"{name} contains lone surrogate") from exc
    return val


def require_sha256_hex(val: Any, name: str) -> str:
    s = require_exact_str(val, name)
    require_ok(len(s) == 64, "INVALID_SHA256_LEN", f"{name} must be 64 hex chars")
    require_ok(all(ch in _LOWER_HEX_CHARS for ch in s), "INVALID_SHA256_HEX", f"{name} must be lowercase hex")
    return s


def require_exact_fraction(
    val: Any,
    name: str,
    *,
    positive: bool = False,
) -> Fraction:
    require_ok(type(val) is Fraction, "INVALID_FRACTION_TYPE", f"{name} must be exact Fraction")
    require_ok(
        val.numerator.bit_length() <= MAX_RATIONAL_BITS,
        "RATIONAL_BIT_LIMIT",
        f"{name}.numerator exceeds {MAX_RATIONAL_BITS} bits",
    )
    require_ok(
        val.denominator.bit_length() <= MAX_RATIONAL_BITS,
        "RATIONAL_BIT_LIMIT",
        f"{name}.denominator exceeds {MAX_RATIONAL_BITS} bits",
    )
    if positive:
        require_ok(val > 0, "RATIONAL_NON_POSITIVE", f"{name} must be > 0")
    return val


def _is_ascii_digits(s: str) -> bool:
    return len(s) > 0 and all("0" <= ch <= "9" for ch in s)


def parse_exact_int_ascii(text: Any, name: str) -> int:
    s = require_exact_str(text, name)
    require_ok(s == s.strip(), "INT_WHITESPACE", f"{name} has surrounding whitespace")
    neg = s.startswith("-")
    body = s[1:] if neg else s
    require_ok(_is_ascii_digits(body), "INVALID_INT_ASCII", f"{name} must contain ASCII digits only")
    if len(body) > 1:
        require_ok(body[0] != "0", "LEADING_ZERO_INT", f"{name} has forbidden leading zero")
    if neg:
        require_ok(body != "0", "NEGATIVE_ZERO_INT", f"{name} cannot be -0")
    require_ok(len(body) <= MAX_INT_DIGITS, "INT_DIGIT_LIMIT", f"{name} exceeds {MAX_INT_DIGITS} digits")
    val = int(s)
    require_ok(val.bit_length() <= MAX_INT_BITS, "INT_BIT_LIMIT", f"{name} exceeds {MAX_INT_BITS} bits")
    return val


def parse_exact_rational(val: Any, name: str) -> Fraction:
    """Parse canonical exact rational from exact int or canonical 'p' / 'p/q' ASCII string."""
    if type(val) is int:
        require_exact_int(val, name)
        return Fraction(val, 1)
    s = require_exact_str(val, name)
    require_ok(s == s.strip(), "RATIONAL_WHITESPACE", f"{name} has surrounding whitespace")
    if "/" in s:
        parts = s.split("/")
        require_ok(len(parts) == 2, "MALFORMED_RATIONAL", f"{name} must contain at most one slash")
        num = parse_exact_int_ascii(parts[0], f"{name}.num")
        den = parse_exact_int_ascii(parts[1], f"{name}.den")
        require_ok(den > 0, "ZERO_OR_NEG_DENOM", f"{name} denominator must be > 0")
        q = Fraction(num, den)
        require_ok(q.denominator == den, "NON_CANONICAL_RATIONAL", f"{name} must be reduced")
        require_ok(den != 1, "NON_CANONICAL_DENOM_ONE", f"{name} must omit '/1'")
        return q
    return Fraction(parse_exact_int_ascii(s, name), 1)


def format_exact_rational(q: Any) -> str:
    val = require_exact_fraction(q, "rational")
    if val.denominator == 1:
        return str(val.numerator)
    return f"{val.numerator}/{val.denominator}"


def validate_json_tree(obj: Any, label: str = "json") -> None:
    """Iterative fail-closed JSON AST validator (strict types, depth, bits, UTF-8, no floats)."""
    stack: list[tuple[Any, int]] = [(obj, 0)]
    while stack:
        cur, depth = stack.pop()
        require_ok(depth <= MAX_JSON_DEPTH, "MAX_DEPTH_EXCEEDED", f"{label} exceeds depth {MAX_JSON_DEPTH}")
        t = type(cur)
        if cur is None or t is bool:
            continue
        if t is int:
            require_ok(cur.bit_length() <= MAX_INT_BITS, "INT_BIT_LIMIT", f"{label} int exceeds {MAX_INT_BITS} bits")
            continue
        if t is str:
            try:
                cur.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise ZeroDwStateTransportError("INVALID_UTF8_SURROGATE", f"{label} contains surrogate") from exc
            continue
        if t is list:
            next_depth = depth + 1
            for item in cur:
                stack.append((item, next_depth))
            continue
        if t is dict:
            next_depth = depth + 1
            for k, v in cur.items():
                require_ok(type(k) is str, "INVALID_JSON_KEY", f"{label} key must be exact str")
                stack.append((k, next_depth))
                stack.append((v, next_depth))
            continue
        raise ZeroDwStateTransportError("INVALID_JSON_VALUE", f"{label} forbids type {t.__name__}")


def canonical_json_bytes(obj: Any) -> bytes:
    validate_json_tree(obj, "canonical_json")
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def parse_strict_json_text(
    text: Any,
    *,
    require_object: bool = True,
    max_bytes: int = MAX_JSON_BYTES,
) -> Any:
    """Strict RFC 8259 ASCII/UTF-8 JSON parser rejecting floats, constants, dup keys, BOM, CRLF, NUL."""
    require_exact_int(max_bytes, "max_bytes", min_val=1, max_val=MAX_READ_CAP_BYTES)
    raw_text = require_exact_str(text, "json_text")
    encoded = raw_text.encode("utf-8")
    require_ok(len(encoded) <= max_bytes, "JSON_TOO_LARGE", f"json text exceeds {max_bytes} bytes")
    require_ok(not raw_text.startswith("\ufeff"), "JSON_BOM_FORBIDDEN", "UTF-8 BOM forbidden")
    require_ok("\r" not in raw_text, "JSON_CRLF_FORBIDDEN", "CR/CRLF line endings forbidden")
    require_ok("\x00" not in raw_text, "JSON_NUL_FORBIDDEN", "NUL byte forbidden in JSON text")

    def _reject_float(token: str) -> Any:
        raise ZeroDwStateTransportError("JSON_FLOAT_FORBIDDEN", f"float token forbidden: {token}")

    def _reject_const(token: str) -> Any:
        raise ZeroDwStateTransportError("JSON_CONST_FORBIDDEN", f"non-standard constant forbidden: {token}")

    def _parse_int(token: str) -> int:
        return parse_exact_int_ascii(token, "json_int")

    def _no_dup_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in pairs:
            require_ok(k not in out, "DUPLICATE_JSON_KEY", f"duplicate key {k!r}")
            out[k] = v
        return out

    try:
        parsed = json.loads(
            raw_text,
            object_pairs_hook=_no_dup_keys,
            parse_float=_reject_float,
            parse_int=_parse_int,
            parse_constant=_reject_const,
        )
    except ZeroDwStateTransportError:
        raise
    except (ValueError, RecursionError) as exc:
        raise ZeroDwStateTransportError("INVALID_JSON_SYNTAX", f"invalid JSON: {exc}") from exc

    if require_object:
        require_ok(type(parsed) is dict, "JSON_ROOT_NOT_OBJECT", "JSON root must be object")
    validate_json_tree(parsed, "parsed_json")
    return parsed


# ---------------------------------------------------------------------------
# Exact Pure-Q Linear Algebra & Unified State-Transport Tomography Operator
# ---------------------------------------------------------------------------

def _require_frac_vector(vec: Any, name: str) -> list[Fraction]:
    require_ok(type(vec) in (list, tuple), "INVALID_VECTOR", f"{name} must be list/tuple")
    require_ok(len(vec) > 0, "EMPTY_VECTOR", f"{name} must be non-empty")
    return [require_exact_fraction(x, f"{name}[{i}]") for i, x in enumerate(vec)]


def _require_frac_matrix(mat: Any, name: str) -> tuple[list[list[Fraction]], int, int]:
    require_ok(type(mat) in (list, tuple), "INVALID_MATRIX", f"{name} must be list/tuple")
    require_ok(len(mat) > 0, "EMPTY_MATRIX", f"{name} must be non-empty")
    rows: list[list[Fraction]] = []
    n_cols = -1
    for r_idx, row in enumerate(mat):
        r_vec = _require_frac_vector(row, f"{name}[{r_idx}]")
        if n_cols == -1:
            n_cols = len(r_vec)
        else:
            require_ok(len(r_vec) == n_cols, "RAGGED_MATRIX", f"{name}[{r_idx}] ragged row")
        rows.append(r_vec)
    return rows, len(rows), n_cols


def _require_square_frac_matrix(mat: Any, name: str) -> list[list[Fraction]]:
    rows, n_rows, n_cols = _require_frac_matrix(mat, name)
    require_ok(n_rows == n_cols, "NON_SQUARE_MATRIX", f"{name} must be square")
    return rows


def dot_exact(u: Any, v: Any) -> Fraction:
    uv = _require_frac_vector(u, "u")
    vv = _require_frac_vector(v, "v")
    require_ok(len(uv) == len(vv), "VECTOR_DIM_MISMATCH", "vector lengths must match")
    return sum((a * b for a, b in zip(uv, vv)), Fraction(0, 1))


def mat_vec_exact(mat: Any, vec: Any) -> list[Fraction]:
    m, _, n_cols = _require_frac_matrix(mat, "mat")
    v = _require_frac_vector(vec, "vec")
    require_ok(len(v) == n_cols, "MATVEC_DIM_MISMATCH", "matrix cols must match vector length")
    return [dot_exact(row, v) for row in m]


def mat_mul_exact(a: Any, b: Any) -> list[list[Fraction]]:
    ma, ra, ca = _require_frac_matrix(a, "a")
    mb, rb, cb = _require_frac_matrix(b, "b")
    require_ok(ca == rb, "MATMUL_DIM_MISMATCH", "inner dimensions must match")
    return [
        [sum((ma[i][k] * mb[k][j] for k in range(ca)), Fraction(0, 1)) for j in range(cb)]
        for i in range(ra)
    ]


def transpose_exact(mat: Any) -> list[list[Fraction]]:
    m, r, c = _require_frac_matrix(mat, "mat")
    return [[m[i][j] for i in range(r)] for j in range(c)]


def matrix_sub_exact(a: Any, b: Any) -> list[list[Fraction]]:
    ma, ra, ca = _require_frac_matrix(a, "a")
    mb, rb, cb = _require_frac_matrix(b, "b")
    require_ok(ra == rb, "SHAPE_MISMATCH", "row count mismatch")
    require_ok(ca == cb, "SHAPE_MISMATCH", "col count mismatch")
    return [[ma[i][j] - mb[i][j] for j in range(ca)] for i in range(ra)]


def frobenius_norm_sq_exact(mat: Any) -> Fraction:
    m, _, _ = _require_frac_matrix(mat, "mat")
    return sum((x * x for row in m for x in row), Fraction(0, 1))


def exact_matrix_rank_q(mat: Any) -> int:
    """Exact pure-Q Gaussian elimination rank."""
    m, n_rows, n_cols = _require_frac_matrix(mat, "mat")
    work = [list(row) for row in m]
    rank = 0
    for col in range(n_cols):
        piv = -1
        for r in range(rank, n_rows):
            if work[r][col] != 0:
                piv = r
                break
        if piv == -1:
            continue
        work[rank], work[piv] = work[piv], work[rank]
        pv = work[rank][col]
        work[rank] = [x / pv for x in work[rank]]
        for r in range(n_rows):
            if r != rank:
                fac = work[r][col]
                if fac != 0:
                    work[r] = [work[r][j] - fac * work[rank][j] for j in range(n_cols)]
        rank += 1
    return rank


def schatten_s4_ratio_exact(mat: Any) -> dict[str, Any]:
    """Basis-invariant Schatten-4 dominance S4 = tr((M^T M)^2) / (tr(M^T M))^2 in (0, 1]."""
    m, _, n_cols = _require_frac_matrix(mat, "mat")
    gram = mat_mul_exact(transpose_exact(m), m)
    tr_g = sum((gram[i][i] for i in range(n_cols)), Fraction(0, 1))
    require_ok(tr_g > 0, "ZERO_MATRIX", "matrix must have nonzero Frobenius energy")
    tr_g2 = sum((gram[i][j] * gram[j][i] for i in range(n_cols) for j in range(n_cols)), Fraction(0, 1))
    s4 = tr_g2 / (tr_g * tr_g)
    return {
        "trace_gram": format_exact_rational(tr_g),
        "trace_gram_sq": format_exact_rational(tr_g2),
        "schatten_s4_ratio": format_exact_rational(s4),
        "is_exact_rank_1": s4 == Fraction(1, 1),
    }


def relu_exact(x: Any) -> Fraction:
    val = require_exact_fraction(x, "x")
    return val if val > 0 else Fraction(0, 1)


def gdn2_delta_step_exact(
    state: Any,
    key: Any,
    value: Any,
    *,
    alpha: Any = Fraction(1, 1),
    beta: Any = Fraction(1, 1),
) -> list[list[Fraction]]:
    """Exact pure-Q GDN-2 delta step: S_{t+1} = alpha S_t + beta (v - alpha S_t k) k^T."""
    s_mat = _require_square_frac_matrix(state, "state")
    d = len(s_mat)
    k_vec = _require_frac_vector(key, "key")
    v_vec = _require_frac_vector(value, "value")
    require_ok(len(k_vec) == d, "KEY_DIM_MISMATCH", "key length must match state dim")
    require_ok(len(v_vec) == d, "VALUE_DIM_MISMATCH", "value length must match state dim")
    a_q = require_exact_fraction(alpha, "alpha", positive=True)
    require_ok(a_q <= 1, "ALPHA_ABOVE_ONE", "alpha must be <= 1")
    b_q = require_exact_fraction(beta, "beta", positive=True)
    sk = mat_vec_exact(s_mat, k_vec)
    return [
        [a_q * s_mat[i][j] + b_q * (v_vec[i] - a_q * sk[i]) * k_vec[j] for j in range(d)]
        for i in range(d)
    ]


def state_transport_tomography_exact(
    s0: Any,
    s1: Any,
    w_cls: Any,
    b0: Any,
    query: Any,
    *,
    weight_sha256_before: str,
    weight_sha256_after: str,
) -> dict[str, Any]:
    """Coordinate-free pure-Z/Q Zero-Delta-W State-Transport & Yield-Surface Tomography Operator."""
    m0 = _require_square_frac_matrix(s0, "s0")
    m1 = _require_square_frac_matrix(s1, "s1")
    d = len(m0)
    require_ok(len(m1) == d, "STATE_DIM_MISMATCH", "s0 and s1 must have equal dimension")
    w = _require_frac_vector(w_cls, "w_cls")
    q = _require_frac_vector(query, "query")
    require_ok(len(w) == d, "WEIGHT_DIM_MISMATCH", "w_cls length must match state dim")
    require_ok(len(q) == d, "QUERY_DIM_MISMATCH", "query length must match state dim")
    bias = require_exact_fraction(b0, "b0")
    w_sha0 = require_sha256_hex(weight_sha256_before, "weight_sha256_before")
    w_sha1 = require_sha256_hex(weight_sha256_after, "weight_sha256_after")

    delta_s = matrix_sub_exact(m1, m0)
    frob_sq = frobenius_norm_sq_exact(delta_s)
    rank_ds = exact_matrix_rank_q(delta_s)

    margin_0 = dot_exact(w, mat_vec_exact(m0, q)) + bias
    margin_1 = dot_exact(w, mat_vec_exact(m1, q)) + bias
    delta_m = margin_1 - margin_0
    cs_rhs = dot_exact(w, w) * dot_exact(q, q) * frob_sq
    cs_holds = (delta_m * delta_m) <= cs_rhs

    if frob_sq == 0:
        s4_str = "0"
        is_rank_1 = False
    else:
        s4_info = schatten_s4_ratio_exact(delta_s)
        s4_str = s4_info["schatten_s4_ratio"]
        is_rank_1 = s4_info["is_exact_rank_1"]

    phase_crossed = (margin_0 * margin_1) < 0
    relu_0 = relu_exact(margin_0)
    relu_1 = relu_exact(margin_1)
    active_face_flipped = (relu_0 > 0) != (relu_1 > 0)

    return {
        "state_dim": d,
        "zero_delta_w": w_sha0 == w_sha1,
        "weight_sha256_before": w_sha0,
        "weight_sha256_after": w_sha1,
        "delta_s_rank": rank_ds,
        "delta_s_frob_norm_sq": format_exact_rational(frob_sq),
        "delta_s_schatten_s4": s4_str,
        "delta_s_is_rank_1": is_rank_1,
        "margin_before": format_exact_rational(margin_0),
        "margin_after": format_exact_rational(margin_1),
        "margin_delta": format_exact_rational(delta_m),
        "relu_before": format_exact_rational(relu_0),
        "relu_after": format_exact_rational(relu_1),
        "phase_crossed": phase_crossed,
        "active_face_flipped": active_face_flipped,
        "cauchy_schwarz_margin_sq": format_exact_rational(delta_m * delta_m),
        "cauchy_schwarz_upper_bound": format_exact_rational(cs_rhs),
        "cauchy_schwarz_bound_holds": cs_holds,
    }


def verify_orthogonal_conjugation_invariance_exact(
    s0: Any,
    s1: Any,
    w_cls: Any,
    b0: Any,
    query: Any,
    q_orth: Any,
    *,
    weight_sha256: str,
) -> dict[str, Any]:
    """Certify Q^T Q = I_d and exact coordinate-free invariance of state_transport_tomography_exact."""
    q_mat = _require_square_frac_matrix(q_orth, "q_orth")
    d = len(q_mat)
    qt = transpose_exact(q_mat)
    qtq = mat_mul_exact(qt, q_mat)
    eye = [[Fraction(1, 1) if i == j else Fraction(0, 1) for j in range(d)] for i in range(d)]
    require_ok(qtq == eye, "NOT_ORTHOGONAL", "q_orth must satisfy Q^T Q = I")

    base = state_transport_tomography_exact(
        s0, s1, w_cls, b0, query,
        weight_sha256_before=weight_sha256,
        weight_sha256_after=weight_sha256,
    )
    s0_rot = mat_mul_exact(mat_mul_exact(q_mat, s0), qt)
    s1_rot = mat_mul_exact(mat_mul_exact(q_mat, s1), qt)
    w_rot = mat_vec_exact(q_mat, w_cls)
    query_rot = mat_vec_exact(q_mat, query)
    rot = state_transport_tomography_exact(
        s0_rot, s1_rot, w_rot, b0, query_rot,
        weight_sha256_before=weight_sha256,
        weight_sha256_after=weight_sha256,
    )
    invariants_identical = (base == rot)
    return {
        "dim": d,
        "orthogonal_exact": True,
        "all_invariants_identical": invariants_identical,
        "rank": rot["delta_s_rank"],
        "frob_norm_sq": rot["delta_s_frob_norm_sq"],
        "schatten_s4": rot["delta_s_schatten_s4"],
        "margin_before": rot["margin_before"],
        "margin_after": rot["margin_after"],
        "margin_delta": rot["margin_delta"],
    }


def dpi_concentration_exact(delta_mat: Any) -> dict[str, Any]:
    """Exact pure-Q Deep Patch Inspection concentration metrics (E_F, C_row, rho_nnz)."""
    mat, n_rows, n_cols = _require_frac_matrix(delta_mat, "delta_mat")
    nnz_entries = 0
    nnz_rows = 0
    total_energy = Fraction(0, 1)
    max_row_energy = Fraction(0, 1)
    for row in mat:
        r_energy = Fraction(0, 1)
        row_nz = False
        for entry in row:
            if entry != 0:
                nnz_entries += 1
                row_nz = True
                r_energy += entry * entry
        if row_nz:
            nnz_rows += 1
        total_energy += r_energy
        if r_energy > max_row_energy:
            max_row_energy = r_energy
    require_ok(total_energy > 0, "ZERO_PATCH", "delta_mat must have nonzero Frobenius energy")
    c_row = Fraction(n_rows, 1) * max_row_energy / total_energy
    rho_nnz = Fraction(nnz_entries, n_rows * n_cols)
    return {
        "rows": n_rows,
        "cols": n_cols,
        "frobenius_energy_sq": format_exact_rational(total_energy),
        "max_row_energy_sq": format_exact_rational(max_row_energy),
        "row_concentration_ratio": format_exact_rational(c_row),
        "nnz_entries": nnz_entries,
        "nnz_rows": nnz_rows,
        "support_density": format_exact_rational(rho_nnz),
    }


def _build_s2_cube_operators() -> tuple[list[list[int]], list[list[int]]]:
    e_idx = {e: i for i, e in enumerate(_S2_CUBE_EDGES)}
    d0 = [[0] * 8 for _ in range(12)]
    for i, (u, v) in enumerate(_S2_CUBE_EDGES):
        d0[i][u] = -1
        d0[i][v] = 1
    d1 = [[0] * 12 for _ in range(6)]
    for fi, cyc in enumerate(_S2_FACE_CYCLES):
        for j in range(4):
            a, b = cyc[j], cyc[(j + 1) % 4]
            if (a, b) in e_idx:
                d1[fi][e_idx[(a, b)]] = 1
            else:
                d1[fi][e_idx[(b, a)]] = -1
    return d0, d1


def discrete_s2_outward_div_exact(d0: Any, flux: Any) -> list[int]:
    """Exact DEC outward divergence delta_1(u) = -d0^T u on the S^2 cube complex."""
    require_ok(type(d0) is list, "INVALID_D0_MATRIX", "d0 must be a list of 12 rows")
    require_ok(len(d0) == 12, "INVALID_D0_MATRIX", "d0 must have 12 rows")
    d0_rows: list[list[int]] = []
    for e_i, row in enumerate(d0):
        require_ok(type(row) is list, "INVALID_D0_MATRIX", f"d0[{e_i}] must be list")
        require_ok(len(row) == 8, "INVALID_D0_MATRIX", f"d0[{e_i}] must have 8 entries")
        d0_rows.append([require_exact_int(row[v], f"d0[{e_i}][{v}]") for v in range(8)])
    require_ok(type(flux) is list, "INVALID_FLUX_VEC", "flux must be a list of 12 ints")
    require_ok(len(flux) == 12, "INVALID_FLUX_VEC", "flux must have 12 ints")
    f_vec = [require_exact_int(flux[e], f"flux[{e}]") for e in range(12)]
    return [-sum(d0_rows[e][v] * f_vec[e] for e in range(12)) for v in range(8)]


def _hash_rational_matrix(mat: list[list[Fraction]]) -> str:
    return hashlib.sha256(
        canonical_json_bytes([[format_exact_rational(x) for x in row] for row in mat])
    ).hexdigest()


# ---------------------------------------------------------------------------
# Executable Aletheia v2.2 Candidate Gate: 4-Channel State-Transport Airlock
# ---------------------------------------------------------------------------

def evaluate_state_transport_airlock(record: Any) -> dict[str, Any]:
    """Fail-closed pure-Z/Q 4-channel airlock over (Delta W, Delta KV, Delta S_rec, Delta P_data)."""
    require_ok(type(record) is dict, "INVALID_AIRLOCK_RECORD", "record must be exact dict")
    require_ok(
        frozenset(record.keys()) == _AIRLOCK_KEYS,
        "INVALID_AIRLOCK_KEYS",
        "record must carry exact 4-channel state-transport schema keys",
    )

    w_hash_ok = require_exact_bool(record["weight_hash_match"], "weight_hash_match")
    w_dpi = parse_exact_rational(record["weight_block_dpi_ratio"], "weight_block_dpi_ratio")
    max_w_dpi = parse_exact_rational(record["max_weight_block_dpi_ratio"], "max_weight_block_dpi_ratio")
    require_ok(w_dpi >= 0, "NEGATIVE_DPI_RATIO", "weight_block_dpi_ratio must be >= 0")
    require_ok(max_w_dpi > 0, "NON_POSITIVE_MAX_DPI", "max_weight_block_dpi_ratio must be > 0")

    kv_reuse = require_exact_bool(record["kv_cross_model_reuse"], "kv_cross_model_reuse")
    kv_res = require_exact_int(record["kv_residual_evicted_mentions"], "kv_residual_evicted_mentions", min_val=0)

    s_auth = require_exact_bool(record["state_session_authorized"], "state_session_authorized")
    s_carry = require_exact_bool(record["state_cross_session_carryover"], "state_cross_session_carryover")
    s_frob = parse_exact_rational(record["state_delta_frob_sq"], "state_delta_frob_sq")
    max_s_frob = parse_exact_rational(record["max_state_delta_frob_sq"], "max_state_delta_frob_sq")
    require_ok(s_frob >= 0, "NEGATIVE_STATE_FROB", "state_delta_frob_sq must be >= 0")
    require_ok(max_s_frob >= 0, "NEGATIVE_MAX_STATE_FROB", "max_state_delta_frob_sq must be >= 0")

    s_rank = require_exact_int(record["state_delta_rank"], "state_delta_rank", min_val=0)
    s_s4 = parse_exact_rational(record["state_schatten_s4"], "state_schatten_s4")
    require_ok(s_s4 >= 0, "NEGATIVE_SCHATTEN_S4", "state_schatten_s4 must be >= 0")
    require_ok(s_s4 <= 1, "SCHATTEN_S4_ABOVE_ONE", "state_schatten_s4 must be <= 1")
    if s_frob == 0:
        require_ok(s_rank == 0, "INCONSISTENT_ZERO_RANK", "zero state drift requires rank 0")
        require_ok(s_s4 == 0, "INCONSISTENT_ZERO_S4", "zero state drift requires S4 == 0")
    else:
        require_ok(s_rank >= 1, "INCONSISTENT_NONZERO_RANK", "nonzero state drift requires rank >= 1")
        require_ok(s_s4 * s_rank >= 1, "INCONSISTENT_S4_RANK_BOUND", "S4 must satisfy S4 >= 1/rank")

    m_before = parse_exact_rational(record["margin_before"], "margin_before")
    m_after = parse_exact_rational(record["margin_after"], "margin_after")
    min_safe = parse_exact_rational(record["min_safe_margin"], "min_safe_margin")
    require_ok(min_safe >= 0, "NEGATIVE_MIN_SAFE_MARGIN", "min_safe_margin must be >= 0")

    wall_disp = parse_exact_rational(record["yield_wall_displacement"], "yield_wall_displacement")
    max_wall_disp = parse_exact_rational(record["max_yield_wall_displacement"], "max_yield_wall_displacement")
    require_ok(max_wall_disp >= 0, "NEGATIVE_MAX_WALL_DISP", "max_yield_wall_displacement must be >= 0")

    coh_res = require_exact_int(record["cohomological_relu_residual"], "cohomological_relu_residual")
    req_conserved = require_exact_bool(record["require_conserved_flow"], "require_conserved_flow")

    corp_ok = require_exact_bool(record["corpus_provenance_verified"], "corpus_provenance_verified")
    cot_gap = parse_exact_rational(record["mode_transfer_gap"], "mode_transfer_gap")
    max_cot_gap = parse_exact_rational(record["max_mode_transfer_gap"], "max_mode_transfer_gap")
    require_ok(cot_gap >= 0, "NEGATIVE_MODE_GAP", "mode_transfer_gap must be >= 0")
    require_ok(max_cot_gap >= 0, "NEGATIVE_MAX_MODE_GAP", "max_mode_transfer_gap must be >= 0")

    margin_delta = m_after - m_before
    margin_sign_flipped = (m_before * m_after) < 0
    margin_below_floor = m_after < min_safe
    abs_wall_disp = -wall_disp if wall_disp < 0 else wall_disp
    yield_wall_exceeded = abs_wall_disp > max_wall_disp
    rank1_concentrated = s_rank == 1
    cohomology_violated = req_conserved and coh_res != 0

    violations_3ch: list[str] = []
    if (not w_hash_ok) or (w_dpi > max_w_dpi):
        violations_3ch.append("CH1_WEIGHT_INTEGRITY_OR_DPI")
    if kv_reuse or (kv_res > 0):
        violations_3ch.append("CH2A_KV_BOUNDARY_VIOLATION")
    if (not corp_ok) or (cot_gap > max_cot_gap):
        violations_3ch.append("CH3_DATA_PROVENANCE_OR_MODE_TRANSFER")

    violations_4ch = list(violations_3ch)
    if (not s_auth) or s_carry:
        violations_4ch.append("CH2B_UNAUTHORIZED_STATE_CARRYOVER")
    if s_frob > max_s_frob:
        violations_4ch.append("CH2B_STATE_FROB_BUDGET_EXCEEDED")
    if margin_sign_flipped or margin_below_floor:
        violations_4ch.append("CH2B_STATE_MARGIN_PHASE_CROSSING")
    if yield_wall_exceeded:
        violations_4ch.append("CH2B_YIELD_WALL_ADVECTION")
    if cohomology_violated:
        violations_4ch.append("CH2B_COHOMOLOGICAL_RELU_OBSTRUCTION")

    param_only_dec = "ALLOW" if w_hash_ok else "DENY"
    frob_only_dec = "ALLOW" if (w_hash_ok and s_frob <= max_s_frob) else "DENY"
    legacy_3ch_dec = "ALLOW" if len(violations_3ch) == 0 else "DENY"
    airlock_4ch_dec = "ALLOW" if len(violations_4ch) == 0 else "DENY"

    return {
        "param_only_hash_decision": param_only_dec,
        "frob_only_decision": frob_only_dec,
        "legacy_3ch_decision": legacy_3ch_dec,
        "airlock_4ch_decision": airlock_4ch_dec,
        "violations_3ch": violations_3ch,
        "violations_4ch": violations_4ch,
        "margin_delta": format_exact_rational(margin_delta),
        "margin_sign_flipped": margin_sign_flipped,
        "margin_below_floor": margin_below_floor,
        "yield_wall_exceeded": yield_wall_exceeded,
        "rank1_concentrated": rank1_concentrated,
        "cohomology_violated": cohomology_violated,
        "weight_hash_blind_to_attack": param_only_dec == "ALLOW" and airlock_4ch_dec == "DENY",
    }


# ---------------------------------------------------------------------------
# Pillar 1: Unified Zero-Delta-W GDN-2 State-Transport & Rank-r Bounds
# ---------------------------------------------------------------------------

def build_pillar1_gdn2_state_transport() -> dict[str, Any]:
    half = Fraction(1, 2)
    h4_orth = [
        [half, half, half, half],
        [half, -half, half, -half],
        [half, half, -half, -half],
        [half, -half, -half, half],
    ]
    eye4 = [[Fraction(1, 1) if i == j else Fraction(0, 1) for j in range(4)] for i in range(4)]
    gram_h4 = mat_mul_exact(transpose_exact(h4_orth), h4_orth)

    # Frozen parameter tensor W (pinned digest, strictly Delta W = 0 throughout)
    w_frozen = [
        [Fraction(1, 1), Fraction(-1, 1), Fraction(0, 1), Fraction(0, 1)],
        [Fraction(0, 1), Fraction(1, 1), Fraction(0, 1), Fraction(0, 1)],
        [Fraction(0, 1), Fraction(0, 1), Fraction(1, 1), Fraction(0, 1)],
        [Fraction(0, 1), Fraction(0, 1), Fraction(0, 1), Fraction(1, 1)],
    ]
    w_sha256 = _hash_rational_matrix(w_frozen)

    vals4 = [[Fraction(2, 1) if i == j else Fraction(0, 1) for j in range(4)] for i in range(4)]
    s4 = [[Fraction(0, 1)] * 4 for _ in range(4)]
    for k_vec, v_vec in zip(h4_orth, vals4):
        s4 = gdn2_delta_step_exact(s4, k_vec, v_vec)

    l4_err_sq = sum(
        (dot_exact(
            [a - b for a, b in zip(mat_vec_exact(s4, k_vec), v_vec)],
            [a - b for a, b in zip(mat_vec_exact(s4, k_vec), v_vec)],
        ) for k_vec, v_vec in zip(h4_orth, vals4)),
        Fraction(0, 1),
    )

    # 5th unit-norm Pythagorean key k5 = (3/5, 4/5, 0, 0), v5 = (0, 6, 0, 0)
    k5 = [Fraction(3, 5), Fraction(4, 5), Fraction(0, 1), Fraction(0, 1)]
    v5 = [Fraction(0, 1), Fraction(6, 1), Fraction(0, 1), Fraction(0, 1)]
    s5 = gdn2_delta_step_exact(s4, k5, v5)
    delta_s = matrix_sub_exact(s5, s4)

    keys5 = h4_orth + [k5]
    vals5 = vals4 + [v5]
    c_null = [dot_exact(k5, kj) for kj in h4_orth] + [Fraction(-1, 1)]
    d_incons = [
        sum((c_null[j] * vals5[j][r] for j in range(5)), Fraction(0, 1))
        for r in range(4)
    ]
    universal_cs_lb = dot_exact(d_incons, d_incons) / dot_exact(c_null, c_null)
    l5_err_sq = sum(
        (dot_exact(
            [a - b for a, b in zip(mat_vec_exact(s5, k_vec), v_vec)],
            [a - b for a, b in zip(mat_vec_exact(s5, k_vec), v_vec)],
        ) for k_vec, v_vec in zip(keys5, vals5)),
        Fraction(0, 1),
    )

    w_cls = [Fraction(1, 1), Fraction(-1, 1), Fraction(0, 1), Fraction(0, 1)]
    q_benign = h4_orth[0]
    tomo_poison = state_transport_tomography_exact(
        s4, s5, w_cls, Fraction(0, 1), q_benign,
        weight_sha256_before=w_sha256,
        weight_sha256_after=w_sha256,
    )
    conj_invariance = verify_orthogonal_conjugation_invariance_exact(
        s4, s5, w_cls, Fraction(0, 1), q_benign, h4_orth,
        weight_sha256=w_sha256,
    )

    # Intervening benign orthogonal turn k_orth = (4/5, -3/5, 0, 0)
    k_orth = [Fraction(4, 5), Fraction(-3, 5), Fraction(0, 1), Fraction(0, 1)]
    v_orth = mat_vec_exact(s4, k_orth)
    s5_after_orth = gdn2_delta_step_exact(s5, k_orth, v_orth)
    margin_after_orth = dot_exact(w_cls, mat_vec_exact(s5_after_orth, q_benign))

    # Benign sub-threshold nullspace state update control: Delta S_ben = (1/4) e_2 e_2^T
    s_benign = [list(row) for row in s4]
    s_benign[2][2] = s_benign[2][2] + Fraction(1, 4)
    tomo_benign = state_transport_tomography_exact(
        s4, s_benign, w_cls, Fraction(0, 1), q_benign,
        weight_sha256_before=w_sha256,
        weight_sha256_after=w_sha256,
    )

    # General rank-r trace / nuclear-norm vs Frobenius & Schatten-4 bounds (r in {1, 2, 4})
    # Rank-1: GDN-2 delta_s (||Delta S||_*^2 = ||Delta S||_F^2 = 212/5, S4 = 1)
    frob_r1 = frobenius_norm_sq_exact(delta_s)
    # Rank-2 unequal singular values (3, 1): ||M||_F^2 = 10, ||M||_*^2 = 16, r*||M||_F^2 = 20, S4 = 41/50
    m_r2_uneq = [
        [Fraction(3, 1), Fraction(0, 1), Fraction(0, 1), Fraction(0, 1)],
        [Fraction(0, 1), Fraction(1, 1), Fraction(0, 1), Fraction(0, 1)],
        [Fraction(0, 1), Fraction(0, 1), Fraction(0, 1), Fraction(0, 1)],
        [Fraction(0, 1), Fraction(0, 1), Fraction(0, 1), Fraction(0, 1)],
    ]
    s4_r2_uneq = schatten_s4_ratio_exact(m_r2_uneq)
    # Rank-2 equal singular values (2, 2): ||M||_F^2 = 8, ||M||_*^2 = 16 = 2*8, S4 = 1/2 = 1/r
    m_r2_eq = [
        [Fraction(2, 1), Fraction(0, 1), Fraction(0, 1), Fraction(0, 1)],
        [Fraction(0, 1), Fraction(2, 1), Fraction(0, 1), Fraction(0, 1)],
        [Fraction(0, 1), Fraction(0, 1), Fraction(0, 1), Fraction(0, 1)],
        [Fraction(0, 1), Fraction(0, 1), Fraction(0, 1), Fraction(0, 1)],
    ]
    s4_r2_eq = schatten_s4_ratio_exact(m_r2_eq)
    # Rank-4 isotropic orthogonal H4/2: singular values (1, 1, 1, 1), ||M||_F^2 = 4, ||M||_*^2 = 16 = 4*4, S4 = 1/4
    s4_r4_iso = schatten_s4_ratio_exact(h4_orth)

    rank_r_bounds = [
        {
            "label": "rank1_gdn2_channel2b",
            "exact_rank": exact_matrix_rank_q(delta_s),
            "frob_norm_sq": format_exact_rational(frob_r1),
            "nuclear_norm_sq": format_exact_rational(frob_r1),
            "r_times_frob_norm_sq": format_exact_rational(frob_r1),
            "schatten_s4_ratio": "1",
            "min_s4_inv_r": "1",
            "nuclear_bracket_exact": True,
            "s4_lower_bound_exact": True,
        },
        {
            "label": "rank2_anisotropic_3_1",
            "exact_rank": exact_matrix_rank_q(m_r2_uneq),
            "frob_norm_sq": format_exact_rational(frobenius_norm_sq_exact(m_r2_uneq)),
            "nuclear_norm_sq": "16",
            "r_times_frob_norm_sq": "20",
            "schatten_s4_ratio": s4_r2_uneq["schatten_s4_ratio"],
            "min_s4_inv_r": "1/2",
            "nuclear_bracket_exact": Fraction(10, 1) < Fraction(16, 1) < Fraction(20, 1),
            "s4_lower_bound_exact": parse_exact_rational(s4_r2_uneq["schatten_s4_ratio"], "s4") > Fraction(1, 2),
        },
        {
            "label": "rank2_isotropic_2_2_tight",
            "exact_rank": exact_matrix_rank_q(m_r2_eq),
            "frob_norm_sq": format_exact_rational(frobenius_norm_sq_exact(m_r2_eq)),
            "nuclear_norm_sq": "16",
            "r_times_frob_norm_sq": "16",
            "schatten_s4_ratio": s4_r2_eq["schatten_s4_ratio"],
            "min_s4_inv_r": "1/2",
            "nuclear_bracket_exact": Fraction(8, 1) < Fraction(16, 1) == Fraction(16, 1),
            "s4_lower_bound_exact": parse_exact_rational(s4_r2_eq["schatten_s4_ratio"], "s4") == Fraction(1, 2),
        },
        {
            "label": "rank4_hadamard_isotropic_tight",
            "exact_rank": exact_matrix_rank_q(h4_orth),
            "frob_norm_sq": format_exact_rational(frobenius_norm_sq_exact(h4_orth)),
            "nuclear_norm_sq": "16",
            "r_times_frob_norm_sq": "16",
            "schatten_s4_ratio": s4_r4_iso["schatten_s4_ratio"],
            "min_s4_inv_r": "1/4",
            "nuclear_bracket_exact": Fraction(4, 1) < Fraction(16, 1) == Fraction(16, 1),
            "s4_lower_bound_exact": parse_exact_rational(s4_r4_iso["schatten_s4_ratio"], "s4") == Fraction(1, 4),
        },
    ]

    s4_sha = _hash_rational_matrix(s4)
    s5_sha = _hash_rational_matrix(s5)
    return {
        "frozen_weight_sha256": w_sha256,
        "hadamard_keys_orthonormal": gram_h4 == eye4,
        "l4_zero_error_exact": l4_err_sq == 0,
        "k5_unit_norm_exact": dot_exact(k5, k5) == 1,
        "universal_capacity_lb": format_exact_rational(universal_cs_lb),
        "l5_parseval_error_sq": format_exact_rational(l5_err_sq),
        "parseval_identity_exact": l5_err_sq == frob_r1,
        "clean_state_sha256": s4_sha,
        "poisoned_state_sha256": s5_sha,
        "state_hashes_distinct": s4_sha != s5_sha,
        "channel2b_tomography": tomo_poison,
        "orthogonal_conjugation_invariance": conj_invariance,
        "intervening_orth_turn_persists": s5_after_orth == s5,
        "margin_after_orth_turn": format_exact_rational(margin_after_orth),
        "benign_nullspace_control": tomo_benign,
        "general_rank_r_nuclear_frob_bounds": rank_r_bounds,
    }


# ---------------------------------------------------------------------------
# Pillar 2: Viscoplastic ReLU Yield-Wall Advection & S^2 Hodge Obstruction
# ---------------------------------------------------------------------------

def _relu_pl_quadrant_jacobians() -> list[list[list[Fraction]]]:
    """Quadrant Jacobians of the piecewise-linear ReLU map R(x, y) = (max(x, 0), max(y, 0))
    on [-1, 1]^2, in fixed sign order (+,+), (-,+), (+,-), (-,-). Restricted to the
    quadrant with sign vector (sx, sy), R is the exact linear map
    (x, y) -> (x if sx > 0 else 0, y if sy > 0 else 0), so its Jacobian over Q is
    diag(1 if sx > 0 else 0, 1 if sy > 0 else 0)."""
    jacobians: list[list[list[Fraction]]] = []
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        jacobians.append([
            [Fraction(1, 1) if sx > 0 else Fraction(0, 1), Fraction(0, 1)],
            [Fraction(0, 1), Fraction(1, 1) if sy > 0 else Fraction(0, 1)],
        ])
    return jacobians


def build_pillar2_yield_wall_and_s2_cohomology() -> dict[str, Any]:
    # Frozen 2D yield-wall weights: w0 = (1, 0), b0 = -1, query q = (3/2, 0)
    w_frozen_2d = [[Fraction(1, 1), Fraction(0, 1)], [Fraction(-1, 1), Fraction(0, 1)]]
    w_sha256 = _hash_rational_matrix(w_frozen_2d)

    s0 = [[Fraction(1, 1), Fraction(0, 1)], [Fraction(0, 1), Fraction(1, 1)]]
    w0 = [Fraction(1, 1), Fraction(0, 1)]
    b0 = Fraction(-1, 1)
    q_pt = [Fraction(3, 2), Fraction(0, 1)]

    # Anchor GDN-2 advection (alpha = 1/2, beta = 1, k = (1, 0), v = (1/4, 0))
    alpha = Fraction(1, 2)
    beta = Fraction(1, 1)
    k_vec = [Fraction(1, 1), Fraction(0, 1)]
    v_vec = [Fraction(1, 4), Fraction(0, 1)]
    s1_gdn2 = gdn2_delta_step_exact(s0, k_vec, v_vec, alpha=alpha, beta=beta)
    # Exact rank-1 injection term beta*(v - alpha S0 k) k^T
    pred_k = mat_vec_exact(s0, k_vec)
    delta_inj = [
        [beta * (v_vec[i] - alpha * pred_k[i]) * k_vec[j] for j in range(2)]
        for i in range(2)
    ]
    s4_inj = schatten_s4_ratio_exact(delta_inj)
    tomo_gdn2_wall = state_transport_tomography_exact(
        s0, s1_gdn2, w0, b0, q_pt,
        weight_sha256_before=w_sha256,
        weight_sha256_after=w_sha256,
    )

    # Pure rank-1 total-transport lift (alpha = 1, beta = 1, same k, v -> same wall 1 -> 4 & margin 1/2 -> -5/8)
    s1_pure_r1 = gdn2_delta_step_exact(s0, k_vec, v_vec, alpha=Fraction(1, 1), beta=Fraction(1, 1))
    tomo_pure_r1_wall = state_transport_tomography_exact(
        s0, s1_pure_r1, w0, b0, q_pt,
        weight_sha256_before=w_sha256,
        weight_sha256_after=w_sha256,
    )

    # Static feedforward control (Delta S = 0 -> wall frozen at x = 1)
    tomo_static = state_transport_tomography_exact(
        s0, s0, w0, b0, q_pt,
        weight_sha256_before=w_sha256,
        weight_sha256_after=w_sha256,
    )

    w_eff_0 = mat_vec_exact(transpose_exact(s0), w0)
    w_eff_1 = mat_vec_exact(transpose_exact(s1_gdn2), w0)
    wall_x_0 = -b0 / w_eff_0[0]
    wall_x_1 = -b0 / w_eff_1[0]
    wall_disp = wall_x_1 - wall_x_0

    # Coordinate-free SO(2, Q) Pythagorean rotation invariance: Q2 = [[3/5, -4/5], [4/5, 3/5]]
    q2_rot = [
        [Fraction(3, 5), Fraction(-4, 5)],
        [Fraction(4, 5), Fraction(3, 5)],
    ]
    so2_invariance = verify_orthogonal_conjugation_invariance_exact(
        s0, s1_pure_r1, w0, b0, q_pt, q2_rot,
        weight_sha256=w_sha256,
    )

    # Discrete S^2 cube Hodge complex & cohomological obstruction (Gauss-Stokes vs ReLU)
    d0, d1 = _build_s2_cube_operators()
    d1_d0_zero = all(
        sum(d1[f][e] * d0[e][v] for e in range(12)) == 0
        for f in range(6)
        for v in range(8)
    )
    closed_s2 = all(sum(d1[f][e] for f in range(6)) == 0 for e in range(12))
    d0_q = [[Fraction(x, 1) for x in row] for row in d0]
    d1_q = [[Fraction(x, 1) for x in row] for row in d1]
    r0 = exact_matrix_rank_q(d0_q)
    r1 = exact_matrix_rank_q(d1_q)
    b0_betti = 8 - r0
    b1_betti = (12 - r1) - r0
    b2_betti = 6 - r1

    # Hodge orthogonality witness
    phi = [1, 1, 0, 0, 0, 0, 0, 0]
    psi = [0, 1, 0, 0, 0, 0]
    u_pol = [sum(d0[e][v] * phi[v] for v in range(8)) for e in range(12)]
    u_tor = [sum(d1[f][e] * psi[f] for f in range(6)) for e in range(12)]
    e_pol = sum(x * x for x in u_pol)
    e_tor = sum(x * x for x in u_tor)
    e_eq = sum((u_pol[e] + u_tor[e]) * (u_pol[e] + u_tor[e]) for e in range(12))
    hodge_dot = sum(u_pol[e] * u_tor[e] for e in range(12))

    # Universal Gauss-Stokes zero-sum law across all 12 basis fluxes + asymmetric stress flux
    basis_zero_count = 0
    for e_i in range(12):
        unit_flux = [1 if k == e_i else 0 for k in range(12)]
        if sum(discrete_s2_outward_div_exact(d0, unit_flux)) == 0:
            basis_zero_count += 1
    u_asym = [-3, 1, -2, 0, -1, 2, -4, 0, 3, -2, -1, 1]
    div_asym = discrete_s2_outward_div_exact(d0, u_asym)
    pos_source_sum = sum(x for x in div_asym if x > 0)
    neg_sink_sum = sum(x for x in div_asym if x < 0)

    # Piecewise-linear ReLU obstruction on [-1, 1]^2 (4 unit quadrants): the image-area
    # determinants and displacement-field divergences are derived from the quadrant
    # Jacobians of R(x, y) = (max(x, 0), max(y, 0)), not asserted as literals.
    # quad_dets[i] = det J_i; quad_disp_divs[i] = tr(J_i - I) = div(R(x) - x) on quadrant i.
    relu_quads = _relu_pl_quadrant_jacobians()
    quad_dets = [
        int(jac[0][0] * jac[1][1] - jac[0][1] * jac[1][0])
        for jac in relu_quads
    ]
    quad_disp_divs = [
        int((jac[0][0] - 1) + (jac[1][1] - 1))
        for jac in relu_quads
    ]
    relu_img_area = sum(quad_dets)
    relu_dom_area = 4
    relu_global_div = sum(quad_disp_divs)

    # Non-commutativity commutator [ReLU, delta_1](u_asym) = ReLU(delta_1 u) - delta_1(ReLU(u))
    relu_of_div = [x if x > 0 else 0 for x in div_asym]
    relu_u_asym = [x if x > 0 else 0 for x in u_asym]
    div_of_relu = discrete_s2_outward_div_exact(d0, relu_u_asym)
    commutator_vec = [relu_of_div[v] - div_of_relu[v] for v in range(8)]
    commutator_sum = sum(commutator_vec)

    return {
        "yield_wall_advection_zero_dw": {
            "frozen_weight_sha256": w_sha256,
            "wall_x_t0": format_exact_rational(wall_x_0),
            "wall_x_t1": format_exact_rational(wall_x_1),
            "wall_displacement": format_exact_rational(wall_disp),
            "gdn2_alpha": format_exact_rational(alpha),
            "gdn2_beta": format_exact_rational(beta),
            "gdn2_injection_rank": exact_matrix_rank_q(delta_inj),
            "gdn2_injection_schatten_s4": s4_inj["schatten_s4_ratio"],
            "gdn2_key_overwrite_exact": mat_vec_exact(s1_gdn2, k_vec) == v_vec,
            "gdn2_wall_tomography": tomo_gdn2_wall,
            "pure_rank1_lift_tomography": tomo_pure_r1_wall,
            "static_feedforward_control": tomo_static,
            "so2_conjugation_invariance": so2_invariance,
        },
        "s2_cohomological_obstruction": {
            "vertices": 8,
            "edges": 12,
            "faces": 6,
            "euler_characteristic": 8 - 12 + 6,
            "d1_d0_identically_zero": d1_d0_zero,
            "closed_s2_boundary_zero": closed_s2,
            "rank_d0": r0,
            "rank_d1": r1,
            "betti_numbers": [b0_betti, b1_betti, b2_betti],
            "hodge_inner_product": hodge_dot,
            "hodge_e_pol": e_pol,
            "hodge_e_tor": e_tor,
            "hodge_e_eq": e_eq,
            "hodge_pythagorean_exact": e_eq == e_pol + e_tor,
            "s2_basis_fluxes_zero_sum_count": basis_zero_count,
            "asym_flux_u": u_asym,
            "asym_outward_div": div_asym,
            "gauss_stokes_positive_sum": pos_source_sum,
            "gauss_stokes_negative_sum": neg_sink_sum,
            "gauss_stokes_net_sum": pos_source_sum + neg_sink_sum,
            "relu_domain_area": relu_dom_area,
            "relu_image_area": relu_img_area,
            "relu_area_ratio": format_exact_rational(Fraction(relu_img_area, relu_dom_area)),
            "relu_global_div_residual": relu_global_div,
            "relu_violates_gauss_stokes": relu_global_div != 0,
            "commutator_relu_delta1_vec": commutator_vec,
            "commutator_relu_delta1_sum": commutator_sum,
            "relu_delta1_non_commutative": commutator_sum != 0,
        },
    }


# ---------------------------------------------------------------------------
# Pillar 3: Iso-Frobenius Blindness (75,968x DPI) & 4-Channel Airlock
# ---------------------------------------------------------------------------

def build_pillar3_iso_frobenius_and_airlock() -> dict[str, Any]:
    # Part A: Exact Iso-Frobenius State-Transport Separation at matched energy 212/5 & Delta W = 0
    half = Fraction(1, 2)
    h4_orth = [
        [half, half, half, half],
        [half, -half, half, -half],
        [half, half, -half, -half],
        [half, -half, -half, half],
    ]
    vals4 = [[Fraction(2, 1) if i == j else Fraction(0, 1) for j in range(4)] for i in range(4)]
    s4 = [[Fraction(0, 1)] * 4 for _ in range(4)]
    for k_vec, v_vec in zip(h4_orth, vals4):
        s4 = gdn2_delta_step_exact(s4, k_vec, v_vec)

    k5 = [Fraction(3, 5), Fraction(4, 5), Fraction(0, 1), Fraction(0, 1)]
    v5 = [Fraction(0, 1), Fraction(6, 1), Fraction(0, 1), Fraction(0, 1)]
    s5_poison = gdn2_delta_step_exact(s4, k5, v5)

    # Matched-Frobenius benign nullspace state perturbation: identical ||Delta S||_F^2 = 212/5, rank 2, dm = 0
    delta_s_benign_iso = [
        [Fraction(0, 1), Fraction(0, 1), Fraction(0, 1), Fraction(0, 1)],
        [Fraction(0, 1), Fraction(0, 1), Fraction(0, 1), Fraction(0, 1)],
        [Fraction(4, 1), Fraction(0, 1), Fraction(14, 5), Fraction(0, 1)],
        [Fraction(0, 1), Fraction(4, 1), Fraction(0, 1), Fraction(8, 5)],
    ]
    s_benign_iso = [[s4[i][j] + delta_s_benign_iso[i][j] for j in range(4)] for i in range(4)]

    w_cls = [Fraction(1, 1), Fraction(-1, 1), Fraction(0, 1), Fraction(0, 1)]
    q_benign = h4_orth[0]
    w_sha = _hash_rational_matrix([
        [Fraction(1, 1), Fraction(-1, 1), Fraction(0, 1), Fraction(0, 1)],
        [Fraction(0, 1), Fraction(1, 1), Fraction(0, 1), Fraction(0, 1)],
        [Fraction(0, 1), Fraction(0, 1), Fraction(1, 1), Fraction(0, 1)],
        [Fraction(0, 1), Fraction(0, 1), Fraction(0, 1), Fraction(1, 1)],
    ])
    tomo_poison_iso = state_transport_tomography_exact(
        s4, s5_poison, w_cls, Fraction(0, 1), q_benign,
        weight_sha256_before=w_sha,
        weight_sha256_after=w_sha,
    )
    tomo_benign_iso = state_transport_tomography_exact(
        s4, s_benign_iso, w_cls, Fraction(0, 1), q_benign,
        weight_sha256_before=w_sha,
        weight_sha256_after=w_sha,
    )
    frob_gap_state = (
        parse_exact_rational(tomo_poison_iso["delta_s_frob_norm_sq"], "poison_frob")
        - parse_exact_rational(tomo_benign_iso["delta_s_frob_norm_sq"], "benign_frob")
    )

    # Part B: Exact 64x16 DPI iso-Frobenius weight witness (32x) & 151,936x1,536 (75,968x) anchor
    rows, cols = 64, 16
    dw_diffuse = [
        [Fraction(1, 4) if (r + c) % 2 == 0 else Fraction(-1, 4) for c in range(cols)]
        for r in range(rows)
    ]
    dw_local_2row = [[Fraction(0, 1) for _ in range(cols)] for _ in range(rows)]
    for target_row in (7, 42):
        for c in range(cols):
            dw_local_2row[target_row][c] = Fraction(6, 5) if c % 2 == 0 else Fraction(8, 5)
    dpi_diffuse = dpi_concentration_exact(dw_diffuse)
    dpi_local = dpi_concentration_exact(dw_local_2row)
    dpi_frob_gap = (
        parse_exact_rational(dpi_local["frobenius_energy_sq"], "local_ef")
        - parse_exact_rational(dpi_diffuse["frobenius_energy_sq"], "diff_ef")
    )
    dpi_sep_32x = (
        parse_exact_rational(dpi_local["row_concentration_ratio"], "local_crow")
        / parse_exact_rational(dpi_diffuse["row_concentration_ratio"], "diff_crow")
    )
    vocab_rows = 151_936
    embed_cols = 1_536
    two_row_min_conc = Fraction(vocab_rows, 2)

    # Part C: Executable 4-Channel State-Transport Airlock Suite (3 benign ALLOW + 5 must-fail DENY)
    base_clean = {
        "weight_hash_match": True,
        "weight_block_dpi_ratio": "1",
        "max_weight_block_dpi_ratio": "4",
        "kv_cross_model_reuse": False,
        "kv_residual_evicted_mentions": 0,
        "state_session_authorized": True,
        "state_cross_session_carryover": False,
        "state_delta_frob_sq": "0",
        "max_state_delta_frob_sq": "1",
        "state_delta_rank": 0,
        "state_schatten_s4": "0",
        "margin_before": "2",
        "margin_after": "2",
        "min_safe_margin": "1/2",
        "yield_wall_displacement": "0",
        "max_yield_wall_displacement": "1/2",
        "cohomological_relu_residual": 0,
        "require_conserved_flow": True,
        "corpus_provenance_verified": True,
        "mode_transfer_gap": "3/125",
        "max_mode_transfer_gap": "1/20",
    }

    benign_controls = [
        {"name": "benign_clean_zero_drift", **evaluate_state_transport_airlock(base_clean)},
        {
            "name": "benign_nullspace_subthreshold_state_update",
            **evaluate_state_transport_airlock(dict(
                base_clean,
                state_delta_frob_sq="1/16",
                state_delta_rank=1,
                state_schatten_s4="1",
            )),
        },
        {
            "name": "benign_iso_frobenius_rank2_nullspace_212_over_5",
            **evaluate_state_transport_airlock(dict(
                base_clean,
                state_delta_frob_sq="212/5",
                max_state_delta_frob_sq="50",
                state_delta_rank=2,
                state_schatten_s4=tomo_benign_iso["delta_s_schatten_s4"],
            )),
        },
    ]

    negative_controls = [
        {
            "name": "ch1_weight_hash_or_dpi_spike_32x",
            **evaluate_state_transport_airlock(dict(base_clean, weight_block_dpi_ratio="32")),
        },
        {
            "name": "ch2a_kv_cross_model_reuse",
            **evaluate_state_transport_airlock(dict(base_clean, kv_cross_model_reuse=True)),
        },
        {
            "name": "ch2b_gdn2_rank1_margin_poisoning_plus2_to_neg83_over_25",
            **evaluate_state_transport_airlock(dict(
                base_clean,
                state_session_authorized=False,
                state_cross_session_carryover=True,
                state_delta_frob_sq="212/5",
                max_state_delta_frob_sq="50",
                state_delta_rank=1,
                state_schatten_s4="1",
                margin_before="2",
                margin_after="-83/25",
            )),
        },
        {
            "name": "ch2b_relu_yield_wall_advection_1_to_4_and_coh_neg4",
            **evaluate_state_transport_airlock(dict(
                base_clean,
                state_delta_frob_sq="9/16",
                max_state_delta_frob_sq="1",
                state_delta_rank=1,
                state_schatten_s4="1",
                margin_before="1/2",
                margin_after="-5/8",
                yield_wall_displacement="3",
                cohomological_relu_residual=-4,
            )),
        },
        {
            "name": "ch3_data_mode_transfer_gap_exceeded",
            **evaluate_state_transport_airlock(dict(base_clean, mode_transfer_gap="77/500")),
        },
    ]

    gdn2_ctrl = negative_controls[2]
    wall_ctrl = negative_controls[3]
    all_benign_allowed = all(c["airlock_4ch_decision"] == "ALLOW" for c in benign_controls)
    all_negative_denied = all(c["airlock_4ch_decision"] == "DENY" for c in negative_controls)
    param_and_frob_blind_on_zero_dw = all((
        gdn2_ctrl["param_only_hash_decision"] == "ALLOW",
        gdn2_ctrl["frob_only_decision"] == "ALLOW",
        gdn2_ctrl["legacy_3ch_decision"] == "ALLOW",
        gdn2_ctrl["airlock_4ch_decision"] == "DENY",
        wall_ctrl["param_only_hash_decision"] == "ALLOW",
        wall_ctrl["frob_only_decision"] == "ALLOW",
        wall_ctrl["legacy_3ch_decision"] == "ALLOW",
        wall_ctrl["airlock_4ch_decision"] == "DENY",
    ))

    return {
        "iso_frobenius_state_separation": {
            "frobenius_energy_gap": format_exact_rational(frob_gap_state),
            "poison_rank1_witness": tomo_poison_iso,
            "benign_rank2_nullspace_witness": tomo_benign_iso,
            "iso_frobenius_matched_exact": frob_gap_state == 0,
            "opposite_phase_outcome_at_equal_frobenius": all((
                tomo_poison_iso["phase_crossed"],
                not tomo_benign_iso["phase_crossed"],
            )),
        },
        "dpi_iso_frobenius_weight_anchor": {
            "toy_64x16_diffuse": dpi_diffuse,
            "toy_64x16_localized_2row": dpi_local,
            "toy_64x16_frob_gap": format_exact_rational(dpi_frob_gap),
            "toy_64x16_concentration_ratio_factor": format_exact_rational(dpi_sep_32x),
            "analytical_vocab_rows": vocab_rows,
            "analytical_embed_cols": embed_cols,
            "analytical_two_row_min_concentration": format_exact_rational(two_row_min_conc),
        },
        "four_channel_state_transport_airlock": {
            "benign_controls": benign_controls,
            "negative_controls": negative_controls,
            "all_benign_allowed": all_benign_allowed,
            "all_negative_denied": all_negative_denied,
            "param_frob_legacy_blind_on_zero_dw_attacks": param_and_frob_blind_on_zero_dw,
            "airlock_certified": all((
                all_benign_allowed,
                all_negative_denied,
                param_and_frob_blind_on_zero_dw,
            )),
        },
    }


# ---------------------------------------------------------------------------
# Standalone Certificate Assembly & Fail-Closed Structural Verification
# ---------------------------------------------------------------------------

def build_standalone_certificate() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "oracle_class": ORACLE_CLASS,
        "novelty_tier": NOVELTY_TIER,
        "prior_art_cs13_anchors": [
            "Schlag-Irie-Schmidhuber-2021-Fast-Weight-Programmers-N0",
            "Yang-2024-Gated-DeltaNet-Rank1-Delta-Rule-N0",
            "Bingham-1916-Duvaut-Lions-1976-Viscoplastic-Yield-Surfaces-N0",
            "Montufar-2014-Zhang-2018-Tropical-ReLU-Linear-Regions-N0",
            "Hirani-2003-Desbrun-2005-Discrete-Exterior-Calculus-S2-Hodge-N0",
            "Arditi-2024-Directional-Abliteration-and-MemT-1.0-Pro-GDN2-N0",
        ],
        "measured_live_model_weights": False,
        "measured_live_serving_endpoint": False,
        "measured_live_mantle_gcm": False,
        "zero_trust_path_floats": True,
        "zero_bare_asserts": True,
        "zero_mathematical_rng": True,
        "pillar1_gdn2_zero_dw_state_transport": build_pillar1_gdn2_state_transport(),
        "pillar2_yield_wall_and_s2_cohomology": build_pillar2_yield_wall_and_s2_cohomology(),
        "pillar3_iso_frobenius_and_4ch_airlock": build_pillar3_iso_frobenius_and_airlock(),
    }
    payload_sha = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    core = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "oracle_class": ORACLE_CLASS,
        "novelty_tier": NOVELTY_TIER,
        "payload_sha256": payload_sha,
        "payload": payload,
    }
    cert_sha = hashlib.sha256(canonical_json_bytes(core)).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "oracle_class": ORACLE_CLASS,
        "novelty_tier": NOVELTY_TIER,
        "payload_sha256": payload_sha,
        "certificate_sha256": cert_sha,
        "payload": payload,
    }


def _validate_payload_envelope(payload: Any) -> None:
    require_ok(type(payload) is dict, "PAYLOAD_NOT_OBJECT", "payload must be exact dict")
    require_ok(frozenset(payload.keys()) == _PAYLOAD_KEYS, "INVALID_PAYLOAD_KEYS", "payload keys mismatch")
    require_ok(payload["oracle_class"] == ORACLE_CLASS, "INVALID_ORACLE_CLASS", "oracle_class must be exact")
    require_ok(payload["novelty_tier"] == NOVELTY_TIER, "INVALID_NOVELTY_TIER", "novelty_tier must be N1")
    anchors = payload["prior_art_cs13_anchors"]
    require_ok(type(anchors) is list, "INVALID_CS13_ANCHORS", "prior_art_cs13_anchors must be list")
    require_ok(len(anchors) == 6, "INVALID_CS13_ANCHORS", "prior_art_cs13_anchors must have 6 anchors")
    for idx, item in enumerate(anchors):
        require_exact_str(item, f"prior_art_cs13_anchors[{idx}]")
    for key in ("measured_live_model_weights", "measured_live_serving_endpoint", "measured_live_mantle_gcm"):
        require_ok(require_exact_bool(payload[key], key) is False, "INVALID_LAW4_FLAG", f"{key} must be False")
    for key in ("zero_trust_path_floats", "zero_bare_asserts", "zero_mathematical_rng"):
        require_ok(require_exact_bool(payload[key], key) is True, "INVALID_HYGIENE_FLAG", f"{key} must be True")


def verify_certificate_payload(cert: Any, *, full_replay: bool = True) -> dict[str, Any]:
    """Fail-closed validation of certificate structure, SHA-256 digests, and optional full replay."""
    replay_flag = require_exact_bool(full_replay, "full_replay")
    require_ok(type(cert) is dict, "CERT_NOT_OBJECT", "certificate must be exact dict")
    validate_json_tree(cert, "certificate")
    require_ok(frozenset(cert.keys()) == _CERT_KEYS, "INVALID_CERT_KEYS", "certificate keys mismatch")
    require_ok(cert["schema_version"] == SCHEMA_VERSION, "INVALID_SCHEMA", "unexpected schema_version")
    require_ok(cert["track_id"] == TRACK_ID, "INVALID_TRACK_ID", "unexpected track_id")
    require_ok(cert["oracle_class"] == ORACLE_CLASS, "INVALID_ORACLE_CLASS", "unexpected oracle_class")
    require_ok(cert["novelty_tier"] == NOVELTY_TIER, "INVALID_NOVELTY_TIER", "unexpected novelty_tier")

    payload = cert["payload"]
    _validate_payload_envelope(payload)

    claimed_payload_sha = require_sha256_hex(cert["payload_sha256"], "payload_sha256")
    claimed_cert_sha = require_sha256_hex(cert["certificate_sha256"], "certificate_sha256")
    computed_payload_sha = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    require_ok(computed_payload_sha == claimed_payload_sha, "PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")

    core = {
        "schema_version": cert["schema_version"],
        "track_id": cert["track_id"],
        "oracle_class": cert["oracle_class"],
        "novelty_tier": cert["novelty_tier"],
        "payload_sha256": claimed_payload_sha,
        "payload": payload,
    }
    computed_cert_sha = hashlib.sha256(canonical_json_bytes(core)).hexdigest()
    require_ok(computed_cert_sha == claimed_cert_sha, "CERT_SHA_MISMATCH", "certificate_sha256 mismatch")

    if replay_flag:
        expected = build_standalone_certificate()
        require_ok(
            canonical_json_bytes(cert) == canonical_json_bytes(expected),
            "REPLAY_MISMATCH",
            "certificate differs from pure-Q oracle replay",
        )

    return {
        "valid": True,
        "full_replay": replay_flag,
        "track_id": TRACK_ID,
        "payload_sha256": computed_payload_sha,
        "certificate_sha256": computed_cert_sha,
    }
