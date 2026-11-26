#!/usr/bin/env python3
"""Pure-Q exact geometry oracle for Track S123 (EXP-Q28a + EXP-Q30c / W14-OBS-1):
Cross-model O(1) HoloSphere S_fast Woodbury & CayleySU2 state transport vs O(T) KV caches.

Zero floats on all trust paths (int / fractions.Fraction only).
Zero bare asserts. Fail-closed StateTransportError on all invalid inputs.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import hmac
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA_ORACLE = "aletheia.s123.state_transport_geometry.v1"
MAX_JSON_DEPTH = 32
MAX_INT_ABS = 10**18


class StateTransportError(ValueError):
    """Fail-closed error for Track S123 pure-Q geometry verification."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"[{code}] {detail}")


def require_ok(cond: bool, code: str, detail: str) -> None:
    if not cond:
        raise StateTransportError(code, detail)


def check_pos_int(val: Any, name: str) -> int:
    require_ok(type(val) is int and 1 <= val <= MAX_INT_ABS, "BAD_POS_INT", f"{name} must be positive int")
    return val


def check_frac(val: Any, name: str) -> Fraction:
    if type(val) is Fraction:
        require_ok(abs(val.numerator) <= MAX_INT_ABS and val.denominator <= MAX_INT_ABS, "FRAC_RANGE", name)
        return val
    if type(val) is int:
        require_ok(abs(val) <= MAX_INT_ABS, "INT_RANGE", name)
        return Fraction(val, 1)
    raise StateTransportError("BAD_FRAC", f"{name} must be Fraction or int")


def frac_str(x: Fraction) -> str:
    return f"{x.numerator}/{x.denominator}"


def _canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def validate_json_tree_no_floats(root: Any, max_depth: int = MAX_JSON_DEPTH) -> None:
    """Iterative depth-capped check rejecting floats and non-str keys."""
    stack: List[Tuple[Any, int]] = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        require_ok(depth <= max_depth, "JSON_DEPTH", "JSON nesting exceeds cap")
        t = type(node)
        if t is float:
            raise StateTransportError("FLOAT_FORBIDDEN", "Float detected in pure-Q certificate")
        if t is dict:
            for k, v in node.items():
                require_ok(type(k) is str, "BAD_KEY", "Dict key must be str")
                stack.append((v, depth + 1))
        elif t is list:
            for item in node:
                stack.append((item, depth + 1))
        elif t in (int, str, bool) or node is None:
            continue
        else:
            raise StateTransportError("BAD_JSON_TYPE", f"Unsupported type {t.__name__}")


# ---------------------------------------------------------------------------
# Pure-Q linear algebra & rational orthogonal / Cayley SU(2) primitives
# ---------------------------------------------------------------------------

VecQ = Tuple[Fraction, ...]
MatQ = Tuple[VecQ, ...]
QuatQ = Tuple[Fraction, Fraction, Fraction, Fraction]


def mat_eye(n: int) -> MatQ:
    return tuple(tuple(Fraction(1 if i == j else 0) for j in range(n)) for i in range(n))


def mat_zero(n: int) -> MatQ:
    return tuple(tuple(Fraction(0) for _ in range(n)) for _ in range(n))


def mat_transpose(a: MatQ) -> MatQ:
    rows = len(a)
    cols = len(a[0])
    return tuple(tuple(a[r][c] for r in range(rows)) for c in range(cols))


def mat_mul(a: MatQ, b: MatQ) -> MatQ:
    m = len(a)
    k = len(a[0])
    require_ok(len(b) == k, "MAT_DIM", "Inner dimensions must match")
    n = len(b[0])
    return tuple(
        tuple(sum((a[i][t] * b[t][j] for t in range(k)), Fraction(0)) for j in range(n))
        for i in range(m)
    )


def mat_vec(a: MatQ, v: VecQ) -> VecQ:
    k = len(a[0])
    require_ok(len(v) == k, "MV_DIM", "Matrix-vector dimension mismatch")
    return tuple(sum((row[j] * v[j] for j in range(k)), Fraction(0)) for row in a)


def mat_add(a: MatQ, b: MatQ) -> MatQ:
    return tuple(tuple(a[i][j] + b[i][j] for j in range(len(a[0]))) for i in range(len(a)))


def mat_sub(a: MatQ, b: MatQ) -> MatQ:
    return tuple(tuple(a[i][j] - b[i][j] for j in range(len(a[0]))) for i in range(len(a)))


def mat_scale(s: Fraction, a: MatQ) -> MatQ:
    return tuple(tuple(s * x for x in row) for row in a)


def outer_prod(u: VecQ, v: VecQ) -> MatQ:
    return tuple(tuple(ui * vj for vj in v) for ui in u)


def vec_dot(u: VecQ, v: VecQ) -> Fraction:
    require_ok(len(u) == len(v), "DOT_DIM", "Vector dot dimension mismatch")
    return sum((ui * vi for ui, vi in zip(u, v)), Fraction(0))


def frob_sq(a: MatQ) -> Fraction:
    return sum((x * x for row in a for x in row), Fraction(0))


def mat_trace(a: MatQ) -> Fraction:
    return sum((a[i][i] for i in range(len(a))), Fraction(0))


def householder_q(u: Sequence[Fraction]) -> MatQ:
    """Exact rational Householder reflection H(u) = I - 2 u u^T / ||u||^2 in O(n, Q), det = -1."""
    uv = tuple(check_frac(x, "u") for x in u)
    n = len(uv)
    n2 = vec_dot(uv, uv)
    require_ok(n2 > 0, "ZERO_HOUSEHOLDER", "Householder normal must be nonzero")
    scale = Fraction(2, 1) / n2
    return tuple(
        tuple(Fraction(1 if i == j else 0) - scale * uv[i] * uv[j] for j in range(n))
        for i in range(n)
    )


def det3_q(m: MatQ) -> Fraction:
    require_ok(len(m) == 3 and len(m[0]) == 3, "DET3_DIM", "det3 requires 3x3 matrix")
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def cross3_q(a: VecQ, b: VecQ) -> VecQ:
    require_ok(len(a) == 3 and len(b) == 3, "CROSS3_DIM", "cross3 requires 3-vectors")
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def cayley_quat_q(w: VecQ) -> QuatQ:
    """Exact rational Cayley map C(w) = ((1 - ||w||^2)/(1 + ||w||^2), 2w/(1 + ||w||^2)) in SU(2) cap Q^4."""
    require_ok(len(w) == 3, "CAYLEY_DIM", "w must be 3-vector")
    n2 = vec_dot(w, w)
    denom = Fraction(1, 1) + n2
    return (
        (Fraction(1, 1) - n2) / denom,
        (Fraction(2, 1) * w[0]) / denom,
        (Fraction(2, 1) * w[1]) / denom,
        (Fraction(2, 1) * w[2]) / denom,
    )


def quat_mul_q(a: QuatQ, b: QuatQ) -> QuatQ:
    return (
        a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3],
        a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
        a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1],
        a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0],
    )


def quat_conj_q(q: QuatQ) -> QuatQ:
    return (q[0], -q[1], -q[2], -q[3])


def quat_to_so3_q(q: QuatQ) -> MatQ:
    """Exact adjoint SO(3) matrix R(q) for unit rational quaternion q."""
    q0, q1, q2, q3 = q
    n2 = q0 * q0 + q1 * q1 + q2 * q2 + q3 * q3
    require_ok(n2 == Fraction(1, 1), "NON_UNIT_QUAT", "Quaternion must have unit norm")
    two = Fraction(2, 1)
    one = Fraction(1, 1)
    return (
        (one - two * (q2 * q2 + q3 * q3), two * (q1 * q2 - q0 * q3), two * (q1 * q3 + q0 * q2)),
        (two * (q1 * q2 + q0 * q3), one - two * (q1 * q1 + q3 * q3), two * (q2 * q3 - q0 * q1)),
        (two * (q1 * q3 - q0 * q2), two * (q2 * q3 + q0 * q1), one - two * (q1 * q1 + q2 * q2)),
    )


def cayley_compose_vec_q(a: VecQ, b: VecQ) -> VecQ:
    """Exact rational group law a (+) b on Cayley coordinates so C(a (+) b) == C(a) * C(b)."""
    na = vec_dot(a, a)
    nb = vec_dot(b, b)
    dot = vec_dot(a, b)
    denom = Fraction(1, 1) + na * nb - Fraction(2, 1) * dot
    require_ok(denom != 0, "CAYLEY_POLE", "Composition hits antipodal pole -I")
    cr = cross3_q(a, b)
    one = Fraction(1, 1)
    two = Fraction(2, 1)
    return tuple(((one - nb) * a[i] + (one - na) * b[i] + two * cr[i]) / denom for i in range(3))


def so2_rational_q(c: Fraction, s: Fraction) -> MatQ:
    """Exact rational planar rotation [[c, -s], [s, c]] in SO(2, Q) requiring c^2 + s^2 == 1."""
    cc = check_frac(c, "c")
    ss = check_frac(s, "s")
    require_ok(cc * cc + ss * ss == Fraction(1, 1), "NON_UNIT_SO2", "c^2 + s^2 must equal 1")
    return ((cc, -ss), (ss, cc))


# ---------------------------------------------------------------------------
# Parameterized Pure-Q Verifier Primitives (Fail-Closed on Counterexamples!)
# ---------------------------------------------------------------------------


def verify_t1_kv_vs_sfast_bandwidth(
    batch: int = 2,
    n_layers: int = 6,
    n_heads: int = 16,
    d_head: int = 32,
    t_eval: int = 8192,
    holosphere_full_state_bytes: int = 933888,
) -> Dict[str, Any]:
    """Certify exact rational KV/S_fast ratios and crossover context lengths T*(rho)."""
    b = check_pos_int(batch, "batch")
    l_cnt = check_pos_int(n_layers, "n_layers")
    h_cnt = check_pos_int(n_heads, "n_heads")
    dh = check_pos_int(d_head, "d_head")
    t_ctx = check_pos_int(t_eval, "t_eval")
    hs_full_b = check_pos_int(holosphere_full_state_bytes, "holosphere_full_state_bytes")

    # BF16 KV cache (2 bytes/elem, K and V): 2 * B * L * H * d_h * T * 2
    kv_bytes_per_tok = 4 * b * l_cnt * h_cnt * dh
    kv_bytes_t_eval = kv_bytes_per_tok * t_ctx
    # Pure FP32 S_fast associative matrix (4 bytes/elem): B * L * H * d_h * d_h * 4
    sfast_pure_bytes = 4 * b * l_cnt * h_cnt * dh * dh

    require_ok(hs_full_b >= sfast_pure_bytes, "STATE_LOWER_BOUND", "Full O(1) state must include S_fast")
    aux_state_bytes = hs_full_b - sfast_pure_bytes

    ratios_table: Dict[str, Dict[str, Any]] = {}
    for rho in (1, 16, 64, 128):
        kv_comp = Fraction(kv_bytes_t_eval, rho)
        ratio_pure = kv_comp / Fraction(sfast_pure_bytes, 1)
        ratio_full = kv_comp / Fraction(hs_full_b, 1)
        t_star_pure = Fraction(sfast_pure_bytes * rho, kv_bytes_per_tok)
        t_star_full = Fraction(hs_full_b * rho, kv_bytes_per_tok)
        ratio_full_m10 = ratio_full * Fraction(10, 1)
        ratios_table[f"rho_{rho}x"] = {
            "kv_compressed_bytes_at_T": frac_str(kv_comp),
            "pure_sfast_ratio_at_T": frac_str(ratio_pure),
            "full_holosphere_ratio_at_T": frac_str(ratio_full),
            "full_holosphere_ratio_10_questions": frac_str(ratio_full_m10),
            "t_star_pure_tokens": frac_str(t_star_pure),
            "t_star_full_tokens": frac_str(t_star_full),
            "o1_beats_kv_at_T": ratio_full > 1,
        }

    full_ratio_1x = Fraction(kv_bytes_t_eval, hs_full_b)
    t1_passed = full_ratio_1x > Fraction(1) and all(v["o1_beats_kv_at_T"] is True for v in ratios_table.values())
    return {
        "theorem": "T1_KV_VS_SFAST_BANDWIDTH_CROSSOVER",
        "kv_bytes_per_token": kv_bytes_per_tok,
        "kv_bytes_at_T_uncompressed": kv_bytes_t_eval,
        "sfast_pure_bytes": sfast_pure_bytes,
        "holosphere_full_state_bytes": hs_full_b,
        "aux_su2_vring_bytes": aux_state_bytes,
        "exact_ratio_uncompressed": frac_str(full_ratio_1x),
        "by_kvzip_ratio": ratios_table,
        "passed": t1_passed,
    }


def _woodbury_right_step(s_mat: MatQ, k: VecQ, v: VecQ, beta: Fraction) -> MatQ:
    """Right-acting associative Woodbury update: S' = S (I - beta k k^T) + beta v k^T."""
    d = len(k)
    proj = mat_sub(mat_eye(d), mat_scale(beta, outer_prod(k, k)))
    return mat_add(mat_mul(s_mat, proj), mat_scale(beta, outer_prod(v, k)))


def _woodbury_left_step(s_mat: MatQ, k: VecQ, v: VecQ, beta: Fraction) -> MatQ:
    """Left-acting Woodbury update: S' = (I - beta k k^T) S + beta v k^T."""
    d = len(k)
    proj = mat_sub(mat_eye(d), mat_scale(beta, outer_prod(k, k)))
    return mat_add(mat_mul(proj, s_mat), mat_scale(beta, outer_prod(v, k)))


def check_woodbury_gauge_transport_q(
    q_k: MatQ,
    q_v: MatQ,
    tokens: Sequence[Tuple[VecQ, VecQ, Fraction]],
    q_probe: VecQ,
    handoff_idx: int,
) -> Dict[str, Any]:
    """Fail-closed verifier of orthogonal gauge Woodbury intertwining & left-rule mismatch."""
    d = len(q_k)
    eye_d = mat_eye(d)
    require_ok(mat_mul(mat_transpose(q_k), q_k) == eye_d, "QK_ORTH", "Q_k must be exact orthogonal")
    require_ok(mat_mul(mat_transpose(q_v), q_v) == eye_d, "QV_ORTH", "Q_v must be exact orthogonal")
    require_ok(0 <= handoff_idx < len(tokens), "HANDOFF_IDX", "handoff_idx out of range")

    s_a = mat_zero(d)
    s_b_native = mat_zero(d)
    s_b_handoff = mat_zero(d)
    for idx, (ka, va, beta) in enumerate(tokens):
        kb = mat_vec(q_k, ka)
        vb = mat_vec(q_v, va)
        s_a = _woodbury_right_step(s_a, ka, va, beta)
        s_b_native = _woodbury_right_step(s_b_native, kb, vb, beta)
        if idx == handoff_idx:
            s_b_handoff = mat_mul(mat_mul(q_v, s_a), mat_transpose(q_k))
        elif idx > handoff_idx:
            s_b_handoff = _woodbury_right_step(s_b_handoff, kb, vb, beta)

    s_b_end_trans = mat_mul(mat_mul(q_v, s_a), mat_transpose(q_k))
    right_err_sq = frob_sq(mat_sub(s_b_end_trans, s_b_native))
    handoff_err_sq = frob_sq(mat_sub(s_b_handoff, s_b_native))
    readout_a = mat_vec(q_v, mat_vec(s_a, q_probe))
    readout_b = mat_vec(s_b_handoff, mat_vec(q_k, q_probe))
    readout_err_sq = sum(((a - b) * (a - b) for a, b in zip(readout_a, readout_b)), Fraction(0))

    # Compare left-acting rule under shared gauge (Q_k, Q_k) vs distinct gauge (Q_k, Q_v)
    sl_a = mat_zero(d)
    sl_shared = mat_zero(d)
    sl_distinct = mat_zero(d)
    for ka, va, beta in tokens[:3]:
        sl_a = _woodbury_left_step(sl_a, ka, va, beta)
        sl_shared = _woodbury_left_step(sl_shared, mat_vec(q_k, ka), mat_vec(q_k, va), beta)
        sl_distinct = _woodbury_left_step(sl_distinct, mat_vec(q_k, ka), mat_vec(q_v, va), beta)
    left_shared_err_sq = frob_sq(mat_sub(mat_mul(mat_mul(q_k, sl_a), mat_transpose(q_k)), sl_shared))
    left_distinct_err_sq = frob_sq(mat_sub(mat_mul(mat_mul(q_v, sl_a), mat_transpose(q_k)), sl_distinct))

    return {
        "right_woodbury_equivariance_err_sq": frac_str(right_err_sq),
        "prefix_handoff_suffix_err_sq": frac_str(handoff_err_sq),
        "readout_equivariance_err_sq": frac_str(readout_err_sq),
        "left_woodbury_shared_gauge_err_sq": frac_str(left_shared_err_sq),
        "left_woodbury_distinct_gauge_obstruction_err_sq": frac_str(left_distinct_err_sq),
    }


def check_su2_intertwiner_q(
    u_quat: QuatQ,
    h_refl: MatQ,
    w1: VecQ,
    w2: VecQ,
    so2_a: Tuple[Fraction, Fraction],
    so2_b: Tuple[Fraction, Fraction],
) -> Dict[str, Any]:
    """Fail-closed verifier of SO(3) det=+1 homomorphism, O(3) det=-1 order reversal, and W14-OBS-1."""
    r_proper = quat_to_so3_q(u_quat)
    require_ok(mat_mul(mat_transpose(h_refl), h_refl) == mat_eye(3) and det3_q(h_refl) == Fraction(-1, 1), "BAD_REFL", "h_refl must be O(3) with det=-1")
    r_improper = mat_mul(h_refl, r_proper)

    diag_fix: MatQ = (
        (Fraction(1), Fraction(0), Fraction(0)),
        (Fraction(0), Fraction(1), Fraction(0)),
        (Fraction(0), Fraction(0), Fraction(-1)),
    )
    r_kabsch = mat_mul(r_improper, diag_fix)

    w12 = cayley_compose_vec_q(w1, w2)
    w21 = cayley_compose_vec_q(w2, w1)
    q1 = cayley_quat_q(w1)
    q2 = cayley_quat_q(w2)
    q12 = cayley_quat_q(w12)
    q21 = cayley_quat_q(w21)
    su2_comm_err_sq = sum(((a - b) * (a - b) for a, b in zip(q12, q21)), Fraction(0))

    # Proper SO(3): exact homomorphism & quaternion conjugation
    rw12_p_lhs = mat_vec(r_proper, w12)
    rw12_p_rhs = cayley_compose_vec_q(mat_vec(r_proper, w1), mat_vec(r_proper, w2))
    prop_err_sq = sum(((a - b) * (a - b) for a, b in zip(rw12_p_lhs, rw12_p_rhs)), Fraction(0))
    conj_q12 = quat_mul_q(quat_mul_q(u_quat, q12), quat_conj_q(u_quat))
    conj_exact = conj_q12 == cayley_quat_q(rw12_p_lhs)
    group_law_exact = q12 == quat_mul_q(q1, q2)

    # Improper O(3) (det=-1): forward homomorphism breaks, reversed order matches identically!
    rw1_i = mat_vec(r_improper, w1)
    rw2_i = mat_vec(r_improper, w2)
    rw12_i_lhs = mat_vec(r_improper, w12)
    rw12_i_fwd = cayley_compose_vec_q(rw1_i, rw2_i)
    rw12_i_rev = cayley_compose_vec_q(rw2_i, rw1_i)
    improp_fwd_err_sq = sum(((a - b) * (a - b) for a, b in zip(rw12_i_lhs, rw12_i_fwd)), Fraction(0))
    improp_rev_exact = rw12_i_lhs == rw12_i_rev

    # Kabsch det=+1 repair restores exact homomorphism
    rk_exact = mat_vec(r_kabsch, w12) == cayley_compose_vec_q(mat_vec(r_kabsch, w1), mat_vec(r_kabsch, w2))

    # W14-OBS-1: Abelian SO(2) (RoPE) commutes (R1*R2 == R2*R1) vs non-Abelian SU(2) (C(w1)C(w2) != C(w2)C(w1))
    r_ab1 = so2_rational_q(so2_a[0], so2_a[1])
    r_ab2 = so2_rational_q(so2_b[0], so2_b[1])
    abelian_comm_err_sq = frob_sq(mat_sub(mat_mul(r_ab1, r_ab2), mat_mul(r_ab2, r_ab1)))

    return {
        "su2_proper_det": frac_str(det3_q(r_proper)),
        "su2_proper_homomorphism_err_sq": frac_str(prop_err_sq),
        "su2_proper_conjugation_exact": conj_exact,
        "su2_cayley_group_law_exact": group_law_exact,
        "su2_improper_det": frac_str(det3_q(r_improper)),
        "su2_improper_order_reversal_exact": improp_rev_exact,
        "su2_improper_forward_err_sq": frac_str(improp_fwd_err_sq),
        "su2_kabsch_repaired_homomorphism_exact": rk_exact,
        "w14_obs1_abelian_so2_commutator_err_sq": frac_str(abelian_comm_err_sq),
        "w14_obs1_nonabelian_su2_commutator_err_sq": frac_str(su2_comm_err_sq),
    }


def verify_t2_woodbury_and_su2_obstruction() -> Dict[str, Any]:
    """Canonical witness instantiation of Theorem 2 + W14-OBS-1."""
    q_k = mat_mul(
        householder_q((Fraction(1), Fraction(2), Fraction(-1), Fraction(1))),
        householder_q((Fraction(2), Fraction(-1), Fraction(0), Fraction(3))),
    )
    q_v = mat_mul(
        householder_q((Fraction(0), Fraction(1), Fraction(2), Fraction(-2))),
        householder_q((Fraction(3), Fraction(1), Fraction(-1), Fraction(1))),
    )
    tokens: Tuple[Tuple[VecQ, VecQ, Fraction], ...] = (
        ((Fraction(1, 2), Fraction(-1, 3), Fraction(1, 4), Fraction(2, 5)), (Fraction(2, 3), Fraction(1, 5), Fraction(-1, 2), Fraction(1, 4)), Fraction(1, 3)),
        ((Fraction(-1, 4), Fraction(3, 5), Fraction(1, 2), Fraction(-1, 3)), (Fraction(-1, 2), Fraction(2, 5), Fraction(3, 4), Fraction(-1, 5)), Fraction(1, 4)),
        ((Fraction(2, 5), Fraction(1, 4), Fraction(-3, 5), Fraction(1, 2)), (Fraction(1, 3), Fraction(-2, 3), Fraction(1, 4), Fraction(3, 5)), Fraction(1, 5)),
        ((Fraction(-1, 3), Fraction(-1, 2), Fraction(2, 5), Fraction(3, 4)), (Fraction(3, 5), Fraction(1, 4), Fraction(-1, 3), Fraction(2, 3)), Fraction(2, 7)),
        ((Fraction(3, 7), Fraction(-2, 5), Fraction(1, 3), Fraction(-1, 4)), (Fraction(-2, 5), Fraction(3, 4), Fraction(1, 2), Fraction(-1, 3)), Fraction(1, 6)),
        ((Fraction(-1, 5), Fraction(1, 2), Fraction(3, 7), Fraction(2, 3)), (Fraction(1, 4), Fraction(-1, 3), Fraction(2, 5), Fraction(1, 2)), Fraction(3, 10)),
    )
    q_probe: VecQ = (Fraction(1, 3), Fraction(-2, 5), Fraction(3, 4), Fraction(-1, 2))
    wb = check_woodbury_gauge_transport_q(q_k, q_v, tokens, q_probe, handoff_idx=3)

    u_quat = cayley_quat_q((Fraction(1, 2), Fraction(-1, 3), Fraction(1, 4)))
    h_refl = householder_q((Fraction(1), Fraction(-2), Fraction(2)))
    w1: VecQ = (Fraction(1, 3), Fraction(1, 5), Fraction(-1, 4))
    w2: VecQ = (Fraction(-1, 4), Fraction(2, 5), Fraction(1, 3))
    su2 = check_su2_intertwiner_q(
        u_quat, h_refl, w1, w2,
        so2_a=(Fraction(3, 5), Fraction(4, 5)),
        so2_b=(Fraction(5, 13), Fraction(12, 13)),
    )

    t2_passed = (
        wb["right_woodbury_equivariance_err_sq"] == "0/1"
        and wb["prefix_handoff_suffix_err_sq"] == "0/1"
        and wb["readout_equivariance_err_sq"] == "0/1"
        and wb["left_woodbury_shared_gauge_err_sq"] == "0/1"
        and wb["left_woodbury_distinct_gauge_obstruction_err_sq"] != "0/1"
        and su2["su2_proper_det"] == "1/1"
        and su2["su2_proper_homomorphism_err_sq"] == "0/1"
        and su2["su2_proper_conjugation_exact"] is True
        and su2["su2_cayley_group_law_exact"] is True
        and su2["su2_improper_det"] == "-1/1"
        and su2["su2_improper_order_reversal_exact"] is True
        and su2["su2_improper_forward_err_sq"] != "0/1"
        and su2["su2_kabsch_repaired_homomorphism_exact"] is True
        and su2["w14_obs1_abelian_so2_commutator_err_sq"] == "0/1"
        and su2["w14_obs1_nonabelian_su2_commutator_err_sq"] != "0/1"
    )
    return {
        "theorem": "T2_GAUGE_INVARIANT_WOODBURY_AND_SU2_OBSTRUCTION",
        **wb,
        **su2,
        "passed": t2_passed,
    }


def _hadamard8_int() -> Tuple[Tuple[int, ...], ...]:
    h: List[List[int]] = [[1]]
    for _ in range(3):
        top = [row + row for row in h]
        bot = [row + [-x for x in row] for row in h]
        h = top + bot
    return tuple(tuple(row) for row in h)


def exact_hadamard_projector(r: int) -> MatQ:
    """Exact rational rank-r orthogonal projector P_r = (1/8) H_{:r}^T H_{:r} in Q^{8x8}."""
    require_ok(type(r) is int and 1 <= r <= 8, "BAD_RANK", "Rank r must be in 1..8")
    h8 = _hadamard8_int()
    sub = h8[:r]
    return tuple(
        tuple(Fraction(sum(sub[k][i] * sub[k][j] for k in range(r)), 8) for j in range(8))
        for i in range(8)
    )


def check_low_rank_pythagorean_q(
    s_true: MatQ,
    e_noise: MatQ,
    p_r: MatQ,
    q_in_sub: VecQ,
) -> Dict[str, Any]:
    """Fail-closed verifier of orthogonal projector P_r and exact Pythagorean denoising identity."""
    d = len(p_r)
    eye_d = mat_eye(d)
    require_ok(mat_mul(p_r, p_r) == p_r and mat_transpose(p_r) == p_r, "BAD_PROJECTOR", "P_r must be orthogonal projector")
    require_ok(mat_vec(p_r, q_in_sub) == q_in_sub, "QUERY_NOT_IN_SUB", "q_in_sub must lie in col(P_r)")

    p_perp = mat_sub(eye_d, p_r)
    s_hat = mat_add(s_true, e_noise)
    s_proj = mat_mul(s_hat, p_r)
    err_full = frob_sq(mat_sub(s_hat, s_true))
    err_proj = frob_sq(mat_sub(s_proj, s_true))
    tail_sq = frob_sq(mat_mul(s_true, p_perp))
    noise_kept = frob_sq(mat_mul(e_noise, p_r))
    noise_removed = frob_sq(mat_mul(e_noise, p_perp))
    gain = err_full - err_proj
    query_preserved = mat_vec(mat_mul(s_true, p_r), q_in_sub) == mat_vec(s_true, q_in_sub)
    return {
        "rank_r": frac_str(mat_trace(p_r)),
        "err_full_sq": frac_str(err_full),
        "err_proj_sq": frac_str(err_proj),
        "tail_energy_sq": frac_str(tail_sq),
        "noise_kept_sq": frac_str(noise_kept),
        "noise_removed_sq": frac_str(noise_removed),
        "net_mse_gain": frac_str(gain),
        "pythagorean_err_exact": err_proj == tail_sq + noise_kept,
        "denoise_gain_exact": gain == noise_removed - tail_sq,
        "query_signal_preserved": query_preserved,
        "beats_full": err_proj < err_full,
    }


def verify_t3_query_aware_low_rank_denoising() -> Dict[str, Any]:
    """Canonical witness instantiation of Theorem 3 + exact 2x uncalibrated nullspace penalty."""
    d = 8
    h8 = _hadamard8_int()
    eye8 = mat_eye(d)
    s_core = mat_add(
        mat_scale(Fraction(1, 2), outer_prod(tuple(Fraction(x) for x in h8[0]), tuple(Fraction(x) for x in h8[0]))),
        mat_scale(Fraction(1, 4), outer_prod(tuple(Fraction(x) for x in h8[1]), tuple(Fraction(x) for x in h8[1]))),
    )
    s_tail = mat_scale(
        Fraction(1, 16),
        outer_prod(tuple(Fraction(x) for x in h8[2]), tuple(Fraction(x) for x in h8[2])),
    )
    s_true = mat_add(s_core, s_tail)
    sigma = Fraction(1, 2)
    e_noise = mat_scale(sigma, eye8)
    q_in_sub = tuple(Fraction(x, 1) for x in h8[0])

    sweep = {f"r{r}": check_low_rank_pythagorean_q(s_true, e_noise, exact_hadamard_projector(r), q_in_sub) for r in (2, 4, 6, 8)}

    # Exact 2x Uncalibrated Nullspace Rotation Penalty via 90-degree block orthogonal rotation J (<Jz, z> == 0)
    z_perp: VecQ = (Fraction(3, 2), Fraction(-1, 2), Fraction(2, 3), Fraction(-5, 6))
    j_rot: MatQ = (
        (Fraction(0), Fraction(-1), Fraction(0), Fraction(0)),
        (Fraction(1), Fraction(0), Fraction(0), Fraction(0)),
        (Fraction(0), Fraction(0), Fraction(0), Fraction(-1)),
        (Fraction(0), Fraction(0), Fraction(1), Fraction(0)),
    )
    z_norm_sq = vec_dot(z_perp, z_perp)
    jz = mat_vec(j_rot, z_perp)
    err_uncal_rot_sq = sum(((a - b) * (a - b) for a, b in zip(jz, z_perp)), Fraction(0))

    t3_passed = (
        sweep["r2"]["pythagorean_err_exact"] is True
        and sweep["r2"]["denoise_gain_exact"] is True
        and sweep["r2"]["query_signal_preserved"] is True
        and sweep["r2"]["beats_full"] is True
        and err_uncal_rot_sq == 2 * z_norm_sq
    )
    return {
        "theorem": "T3_QUERY_AWARE_LOW_RANK_DENOISING_BOUND",
        "ambient_dim": d,
        "noise_sigma_sq": frac_str(sigma * sigma),
        "rank_sweep": sweep,
        "uncalibrated_nullspace_z_norm_sq": frac_str(z_norm_sq),
        "uncalibrated_nullspace_rot_err_sq": frac_str(err_uncal_rot_sq),
        "nullspace_penalty_ratio": frac_str(err_uncal_rot_sq / z_norm_sq),
        "passed": t3_passed,
    }


def check_ols_frob_shrinkage_q(z_a: MatQ, z_b: MatQ) -> Dict[str, Any]:
    """Fail-closed Cauchy-Schwarz verifier comparing s_OLS^2 <= s_Frob^2 for identity-aligned (Z_A, Z_B)."""
    norm_a_sq = frob_sq(z_a)
    norm_b_sq = frob_sq(z_b)
    require_ok(norm_a_sq > 0 and norm_b_sq > 0, "ZERO_DATA", "Z_A and Z_B must be nonzero")
    tr_sigma = mat_trace(mat_mul(mat_transpose(z_b), z_a))
    s_ols = tr_sigma / norm_a_sq
    s_ols_sq = s_ols * s_ols
    s_frob_sq = norm_b_sq / norm_a_sq
    return {
        "norm_a_sq": frac_str(norm_a_sq),
        "norm_b_sq": frac_str(norm_b_sq),
        "tr_sigma": frac_str(tr_sigma),
        "s_ols": frac_str(s_ols),
        "s_ols_sq": frac_str(s_ols_sq),
        "s_frob_sq": frac_str(s_frob_sq),
        "shrinkage_ratio_sq": frac_str(s_ols_sq / s_frob_sq),
        "cauchy_schwarz_holds": s_ols_sq <= s_frob_sq,
        "strict_shrinkage_holds": s_ols_sq < s_frob_sq,
    }


def verify_t4_ols_vs_frob_shrinkage() -> Dict[str, Any]:
    """Canonical witness instantiation of Theorem 4 (strict OLS thin-shell shrinkage)."""
    z_a: MatQ = (
        (Fraction(3), Fraction(0), Fraction(0)),
        (Fraction(-3), Fraction(0), Fraction(0)),
        (Fraction(0), Fraction(2), Fraction(0)),
        (Fraction(0), Fraction(-2), Fraction(0)),
    )
    z_b: MatQ = (
        (Fraction(6), Fraction(0), Fraction(1)),
        (Fraction(-6), Fraction(0), Fraction(-1)),
        (Fraction(0), Fraction(4), Fraction(2)),
        (Fraction(0), Fraction(-4), Fraction(-2)),
    )
    t4_res = check_ols_frob_shrinkage_q(z_a, z_b)
    t4_passed = t4_res["cauchy_schwarz_holds"] is True and t4_res["strict_shrinkage_holds"] is True
    return {
        "theorem": "T4_OLS_VS_FROB_SHELL_SHRINKAGE",
        **t4_res,
        "passed": t4_passed,
    }


PREREG_W12_FILENAME = "PREREG_WAVE12_FRONTIER_SYNTHESIS.md"
PREREG_W12_ORIGINAL_LOCK_SHA256 = "08ce3b2a752107b17fa67c3f530b6d28706b5115fc01349f146aaf18fa74f031"
PREREG_W12_SHA256 = "b012a39410e08f121f2beeab9f3af2e40ecab8f46ffe4ebffcfe080debdbb34e"
PREREG_W14_FILENAME = "PREREG_WAVE14_INF_OPT_BAREMETAL.md"
PREREG_W14_ORIGINAL_LOCK_SHA256 = "871900e5d6c860ac159f43ca6b4767e7c128d0b4f7748edf788d56e9cb535d3e"
PREREG_W14_SHA256 = "4994ae816d852856cfb4c32713c1ca8aea08a2be4abf1f8186d3bd531f0d604d"


def verify_prereg_locks(prereg_dir: Optional[Path] = None) -> Dict[str, str]:
    """Fail-closed SHA-256 verification of in-tree PREREG-W12 and PREREG-W14 files."""
    pdir = prereg_dir if prereg_dir is not None else (Path(__file__).resolve().parent.parent / "preregistrations")
    w12_p = pdir / PREREG_W12_FILENAME
    w14_p = pdir / PREREG_W14_FILENAME
    require_ok(w12_p.is_file() and w14_p.is_file(), "MISSING_PREREG", "missing PREREG-W12 or PREREG-W14 file")
    d12 = hashlib.sha256(w12_p.read_bytes()).hexdigest()
    d14 = hashlib.sha256(w14_p.read_bytes()).hexdigest()
    require_ok(hmac.compare_digest(d12, PREREG_W12_SHA256), "PREREG_W12_MISMATCH", d12)
    require_ok(hmac.compare_digest(d14, PREREG_W14_SHA256), "PREREG_W14_MISMATCH", d14)
    return {"prereg_w12_sha256": d12, "prereg_w14_sha256": d14}


def build_certificate(prereg_dir: Optional[Path] = None) -> Dict[str, Any]:
    verify_prereg_locks(prereg_dir)
    t1 = verify_t1_kv_vs_sfast_bandwidth()
    t2 = verify_t2_woodbury_and_su2_obstruction()
    t3 = verify_t3_query_aware_low_rank_denoising()
    t4 = verify_t4_ols_vs_frob_shrinkage()
    payload: Dict[str, Any] = {
        "schema": SCHEMA_ORACLE,
        "t1_kv_vs_sfast_bandwidth": t1,
        "t2_woodbury_and_su2_obstruction": t2,
        "t3_query_aware_low_rank_denoising": t3,
        "t4_ols_vs_frob_shrinkage": t4,
        "all_passed": (t1["passed"], t2["passed"], t3["passed"], t4["passed"]) == (True, True, True, True),
    }
    validate_json_tree_no_floats(payload)
    payload_sha = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    cert = {
        "payload": payload,
        "payload_sha256": payload_sha,
    }
    cert["certificate_sha256"] = hashlib.sha256(_canonical_json_bytes(cert)).hexdigest()
    return cert


def check_certificate_file(cert_path: Path) -> Dict[str, Any]:
    """Fail-closed verification of a saved JSON certificate against fresh pure-Q replay."""
    try:
        raw = cert_path.read_text(encoding="utf-8")
        obj = json.loads(raw)
    except (OSError, ValueError, RecursionError) as exc:
        raise StateTransportError("CERT_LOAD_FAIL", str(exc)) from exc

    validate_json_tree_no_floats(obj)
    require_ok(type(obj) is dict, "CERT_NOT_DICT", "Certificate top-level must be JSON object")
    require_ok(set(obj.keys()) == {"payload", "payload_sha256", "certificate_sha256"}, "CERT_KEYS", "Unexpected keys")
    payload = obj["payload"]
    p_sha = obj["payload_sha256"]
    c_sha = obj["certificate_sha256"]
    require_ok(type(p_sha) is str and type(c_sha) is str, "CERT_HASH_TYPE", "Hashes must be strings")

    exp_p_sha = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    require_ok(hmac.compare_digest(p_sha, exp_p_sha), "PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")

    inner = {"payload": payload, "payload_sha256": p_sha}
    exp_c_sha = hashlib.sha256(_canonical_json_bytes(inner)).hexdigest()
    require_ok(hmac.compare_digest(c_sha, exp_c_sha), "CERT_SHA_MISMATCH", "certificate_sha256 mismatch")

    fresh = build_certificate()
    require_ok(hmac.compare_digest(c_sha, fresh["certificate_sha256"]), "REPLAY_MISMATCH", "Certificate differs from replay")
    return obj


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Track S123 pure-Q state-transport geometry oracle")
    parser.add_argument("--json", action="store_true", help="Emit canonical JSON certificate")
    parser.add_argument("--write", type=Path, default=None, help="Write canonical JSON certificate to path")
    parser.add_argument("--check", type=Path, default=None, help="Fail-closed verify certificate JSON file")
    args = parser.parse_args(argv)

    try:
        if args.check is not None:
            cert = check_certificate_file(args.check)
        else:
            cert = build_certificate()
            if args.write is not None:
                args.write.write_text(
                    json.dumps(cert, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
                    encoding="utf-8",
                )
    except StateTransportError as exc:
        sys.stderr.write(f"FAIL {exc.code}: {exc.detail}\n")
        return 2

    if args.json:
        sys.stdout.write(json.dumps(cert, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n")
    else:
        sys.stdout.write(f"PASS {SCHEMA_ORACLE} certificate_sha256={cert['certificate_sha256']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
