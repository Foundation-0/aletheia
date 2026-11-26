#!/usr/bin/env python3
"""Wave-11 (EXP-Q25a / Track S121): Exact S^{d-1} & SU(2) Holonomy Extrapolation Geometry for LoopCD.

Zero IEEE-754 floats, zero bare asserts, zero RNG, zero external dependencies.
Proves in exact Q (`fractions.Fraction`) arithmetic and exposes zero-FLOP callable operators for:
  1. Euclidean `LoopCD-Hidden` (`h_raw = (1 + omega)*h_R - omega*h_1`) + `RMSNorm` on S^{d-1}:
       - Exact rational angular law: tan(alpha) = (omega * sin(theta)) / (1 + omega * (1 - cos(theta)))
         = (2 * omega * s) / (1 + (1 + 2*omega) * s^2) for s = tan(theta/2) > 0,
       - Universal self-damping saturation bound:
         tan((pi - theta)/2) - tan(alpha) = (1 + s^2) / (s * (1 + (1 + 2*omega) * s^2)) > 0
         for ALL s > 0 and omega >= 0, proving 0 <= alpha < (pi - theta)/2 < pi/2 and
         total angle theta + alpha < (pi + theta)/2 < pi (zero antipodal wraparound!),
       - Exact O(d, Q) Householder equivariance on S^{d-1} and Chebyshev comparison against
         naive geodesic SLERP extrapolation (alpha_SLERP = omega * theta), which wraps past
         the chord normal, equator, and antipode pi.
  2. Zero-FLOP Spinor-Holonomy Extrapolation U_guide = U_R * (U_1^{-1} * U_R)^omega in SU(2):
       - Exact rational Cayley-BCH composition law on Im(H):
         C^{-1}(C(a) * C(b)) = ((1 - ||b||^2)*a + (1 - ||a||^2)*b + 2*(a x b))
                               / (1 + ||a||^2 * ||b||^2 - 2*<a, b>),
         with strict denominator lower bound >= (1 - (4/5)^2)^2 = 81/625 > 0 across HoloSphere's
         acute Cayley ball ||w|| <= 4/5 = 0.8 (Theorem #48),
       - Palindromic Strang Quadratic BCH Cancellation Theorem:
         For right-ordered holonomy U_R * (U_1^dag * U_R)^omega, the quadratic Lie bracket
         -(omega/2)*[X, Y] + (1/2)*[Y, -omega*X] == 0 cancels IDENTICALLY for all omega, making
         zero-FLOP linear Cayley tangent w_lin = (1 + omega)*w_R - omega*w_1 automatically
         O(||w||^3)-accurate (O(lam^6) squared chordal error, ~64x drop per halving!), whereas
         left-ordered (U_1^dag * U_R)^omega * U_R suffers an O(||w||^2) commutator error
         (O(lam^4) squared error, ~16x drop per halving),
       - Exact rational Cayley-BCH operator w_CayBCH(omega) = C^{-1}(U_R * C(omega * w_Delta)),
         achieving literally 0/1 error against U_R * (U_1^dag * U_R)^1 at omega = 1 and exact
         endpoints U_R (omega = 0) and U_1 (omega = -1).
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import hmac
import json
import sys
from typing import Any


Vec3Q = tuple[Fraction, Fraction, Fraction]
QuatQ = tuple[Fraction, Fraction, Fraction, Fraction]
VecNQ = tuple[Fraction, ...]

CAYLEY_BALL_RADIUS_MAX = Fraction(4, 5)


class LoopCDGeometryError(ValueError):
    """Typed fail-closed error for Track S121 LoopCD S^{d-1} & SU(2) geometry."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


def require_ok(cond: bool, code: str, message: str) -> None:
    if cond is not True:
        raise LoopCDGeometryError(code, message)


def _to_frac(x: Fraction | int) -> Fraction:
    require_ok(not isinstance(x, bool) and isinstance(x, (Fraction, int)), "TYPE_ERROR", "expected int or Fraction")
    return Fraction(x)


def _to_vec_nq(v: Any, min_dim: int = 2) -> VecNQ:
    require_ok(isinstance(v, (list, tuple)) and len(v) >= min_dim, "BAD_VEC_DIM", f"expected sequence len >= {min_dim}")
    return tuple(_to_frac(c) for c in v)


def _to_vec3_q(v: Any) -> Vec3Q:
    require_ok(isinstance(v, (list, tuple)) and len(v) == 3, "BAD_VEC3", "expected 3-element vector")
    return (_to_frac(v[0]), _to_frac(v[1]), _to_frac(v[2]))


def _dot_nq(u: VecNQ, v: VecNQ) -> Fraction:
    require_ok(len(u) == len(v), "DIM_MISMATCH", "vector dimension mismatch")
    return sum((a * b for a, b in zip(u, v)), Fraction(0))


def _dot3_q(u: Vec3Q, v: Vec3Q) -> Fraction:
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


def _cross3_q(u: Vec3Q, v: Vec3Q) -> Vec3Q:
    return (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )


def _quat_conj_q(q: QuatQ) -> QuatQ:
    return (q[0], -q[1], -q[2], -q[3])


def _quat_mul_q(p: QuatQ, q: QuatQ) -> QuatQ:
    return (
        p[0] * q[0] - p[1] * q[1] - p[2] * q[2] - p[3] * q[3],
        p[0] * q[1] + p[1] * q[0] + p[2] * q[3] - p[3] * q[2],
        p[0] * q[2] - p[1] * q[3] + p[2] * q[0] + p[3] * q[1],
        p[0] * q[3] + p[1] * q[2] - p[2] * q[1] + p[3] * q[0],
    )


def _quat_norm_sq_q(q: QuatQ) -> Fraction:
    return q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]


def _quat_dist_sq_q(p: QuatQ, q: QuatQ) -> Fraction:
    return sum(((a - b) * (a - b) for a, b in zip(p, q)), Fraction(0))


def _frac_str(q: Fraction) -> str:
    return f"{q.numerator}/{q.denominator}"


# ---------------------------------------------------------------------------
# 1. Exact S^{d-1} Euclidean LoopCD-Hidden + RMSNorm Extrapolation Geometry
# ---------------------------------------------------------------------------

def stereo_cos_sin_q(s_half_tan: Fraction | int) -> tuple[Fraction, Fraction]:
    """Exact rational (cos(theta), sin(theta)) for s = tan(theta/2) >= 0."""
    s = _to_frac(s_half_tan)
    require_ok(s >= 0, "NEG_HALF_TAN", "s = tan(theta/2) must be >= 0")
    denom = Fraction(1) + s * s
    return (Fraction(1) - s * s) / denom, (Fraction(2) * s) / denom


def loopcd_hidden_raw_q(h1: Any, hr: Any, omega: Fraction | int) -> VecNQ:
    """LoopCD Eq. (2): h' = h_R + omega * (h_R - h_1) = (1 + omega)*h_R - omega*h_1."""
    v1 = _to_vec_nq(h1, min_dim=2)
    vr = _to_vec_nq(hr, min_dim=2)
    require_ok(len(v1) == len(vr), "HIDDEN_DIM_MISMATCH", "h_1 and h_R dimensions must match")
    w = _to_frac(omega)
    require_ok(w >= -1, "OMEGA_BELOW_MINUS_ONE", "omega must be >= -1")
    one_plus_w = Fraction(1) + w
    return tuple(one_plus_w * r - w * a for a, r in zip(v1, vr))


def loopcd_tan_alpha_q(s_half_tan: Fraction | int, omega: Fraction | int) -> Fraction:
    """Exact rational tan(alpha) of LoopCD-Hidden + RMSNorm beyond h_R for s = tan(theta/2) > 0."""
    s = _to_frac(s_half_tan)
    w = _to_frac(omega)
    require_ok(s > 0, "NONPOS_HALF_TAN", "s = tan(theta/2) must be > 0")
    require_ok(w >= 0, "NEG_OMEGA", "guidance strength omega must be >= 0")
    return (Fraction(2) * w * s) / (Fraction(1) + (Fraction(1) + Fraction(2) * w) * s * s)


def loopcd_chord_normal_margin_q(s_half_tan: Fraction | int, omega: Fraction | int) -> Fraction:
    """Exact rational saturation gap tan((pi - theta)/2) - tan(alpha(omega, theta)) > 0."""
    s = _to_frac(s_half_tan)
    w = _to_frac(omega)
    require_ok(s > 0, "NONPOS_HALF_TAN", "s = tan(theta/2) must be > 0")
    require_ok(w >= 0, "NEG_OMEGA", "guidance strength omega must be >= 0")
    return (Fraction(1) + s * s) / (s * (Fraction(1) + (Fraction(1) + Fraction(2) * w) * s * s))


def adaptive_omega_top2_q(
    omega_max: Fraction | int,
    p_top1: Fraction | int,
    p_top2: Fraction | int,
) -> Fraction:
    """Exact LoopCD Eq. (4) margin-based adaptive strength: omega_max * (1 - (p_1 - p_2))."""
    w_max = _to_frac(omega_max)
    p1 = _to_frac(p_top1)
    p2 = _to_frac(p_top2)
    require_ok(w_max >= 0, "NEG_OMEGA_MAX", "omega_max must be >= 0")
    require_ok(Fraction(0) <= p2 <= p1 <= Fraction(1), "BAD_TOP2_PROBS", "require 0 <= p2 <= p1 <= 1")
    require_ok(p1 + p2 <= Fraction(1), "PROB_SUM_GT_ONE", "top-2 probabilities must sum to <= 1")
    return w_max * (Fraction(1) - (p1 - p2))


# ---------------------------------------------------------------------------
# 2. Exact Zero-FLOP SU(2) Spinor-Holonomy Extrapolation Operators
# ---------------------------------------------------------------------------

def cayley_su2_q(w: Any) -> QuatQ:
    """Exact rational Cayley map C(w) = (1 - ||w||^2, 2*w) / (1 + ||w||^2) in SU(2, Q)."""
    v = _to_vec3_q(w)
    nsq = _dot3_q(v, v)
    denom = Fraction(1) + nsq
    two = Fraction(2)
    return ((Fraction(1) - nsq) / denom, (two * v[0]) / denom, (two * v[1]) / denom, (two * v[2]) / denom)


def inv_cayley_su2_q(q: QuatQ) -> Vec3Q:
    """Exact inverse Cayley map C^{-1}(q) = vec(q) / (1 + q_0) for q_0 != -1."""
    require_ok(isinstance(q, tuple) and len(q) == 4, "BAD_QUAT", "expected 4-tuple quaternion")
    q_f = (_to_frac(q[0]), _to_frac(q[1]), _to_frac(q[2]), _to_frac(q[3]))
    require_ok(_quat_norm_sq_q(q_f) == Fraction(1), "NON_UNIT_QUAT", "quaternion must have unit normSq == 1")
    denom = Fraction(1) + q_f[0]
    require_ok(denom != Fraction(0), "ANTIPODAL_MINUS_I", "Cayley chart undefined at q_0 == -1")
    return (q_f[1] / denom, q_f[2] / denom, q_f[3] / denom)


def cayley_compose_vec_q(a_vec: Any, b_vec: Any) -> Vec3Q:
    """Exact non-Abelian Cayley-BCH composition law on R^3:
    C(cayley_compose_vec_q(a, b)) == C(a) * C(b) in SU(2, Q),
    given by ((1 - ||b||^2)*a + (1 - ||a||^2)*b + 2*(a x b)) / (1 + ||a||^2 * ||b||^2 - 2*<a, b>).
    """
    a = _to_vec3_q(a_vec)
    b = _to_vec3_q(b_vec)
    na = _dot3_q(a, a)
    nb = _dot3_q(b, b)
    denom = Fraction(1) + na * nb - Fraction(2) * _dot3_q(a, b)
    require_ok(denom > Fraction(0), "CAYLEY_ANTIPODAL_PRODUCT", "C(a)*C(b) hit antipode -I (denom == 0)")
    ca = Fraction(1) - nb
    cb = Fraction(1) - na
    cr = _cross3_q(a, b)
    two = Fraction(2)
    return (
        (ca * a[0] + cb * b[0] + two * cr[0]) / denom,
        (ca * a[1] + cb * b[1] + two * cr[1]) / denom,
        (ca * a[2] + cb * b[2] + two * cr[2]) / denom,
    )


def su2_cayley_linear_guide_q(w1: Any, wr: Any, omega: Fraction | int) -> Vec3Q:
    """Zero-FLOP Linear Cayley-tangent guidance w_lin = (1 + omega)*w_R - omega*w_1.
    By Palindromic Strang Cancellation, this is automatically O(||w||^3)-accurate for
    right-ordered holonomy U_R * (U_1^dag * U_R)^omega!
    """
    u1 = _to_vec3_q(w1)
    ur = _to_vec3_q(wr)
    w = _to_frac(omega)
    c_r = Fraction(1) + w
    return (c_r * ur[0] - w * u1[0], c_r * ur[1] - w * u1[1], c_r * ur[2] - w * u1[2])


def su2_relative_cayley_delta_q(
    w1: Any,
    wr: Any,
    enforce_acute_ball: bool = True,
) -> Vec3Q:
    """Exact relative holonomy Cayley vector w_Delta = C^{-1}(C(w_1)^dag * C(w_R))
    = cayley_compose_vec_q(-w_1, w_R).
    """
    u1 = _to_vec3_q(w1)
    ur = _to_vec3_q(wr)
    if enforce_acute_ball:
        r2_max = CAYLEY_BALL_RADIUS_MAX * CAYLEY_BALL_RADIUS_MAX
        require_ok(
            _dot3_q(u1, u1) <= r2_max and _dot3_q(ur, ur) <= r2_max,
            "OUTSIDE_ACUTE_BALL",
            "Cayley vectors must satisfy ||w|| <= 4/5",
        )
    neg_u1: Vec3Q = (-u1[0], -u1[1], -u1[2])
    return cayley_compose_vec_q(neg_u1, ur)


def su2_cayley_exact_bch_guide_q(
    w1: Any,
    wr: Any,
    omega: Fraction | int,
    enforce_acute_ball: bool = True,
) -> Vec3Q:
    """Exact rational Cayley-BCH holonomy extrapolation:
    C(w_CayBCH(omega)) == C(w_R) * C(omega * w_Delta) in SU(2, Q).
    """
    u1 = _to_vec3_q(w1)
    ur = _to_vec3_q(wr)
    w = _to_frac(omega)
    require_ok(w >= Fraction(-1), "OMEGA_BELOW_MINUS_ONE", "omega must be >= -1")
    w_delta = su2_relative_cayley_delta_q(u1, ur, enforce_acute_ball=enforce_acute_ball)
    scaled_delta: Vec3Q = (w * w_delta[0], w * w_delta[1], w * w_delta[2])
    return cayley_compose_vec_q(ur, scaled_delta)


# ---------------------------------------------------------------------------
# 3. Exhaustive Rational Proof Suite & Canonical Certificate Builder
# ---------------------------------------------------------------------------

def _householder_apply_q(normal_v: VecNQ, x: VecNQ) -> VecNQ:
    """Exact O(d, Q) Householder reflection H(v) x = x - 2 * (<v, x> / <v, v>) * v."""
    vv = _dot_nq(normal_v, normal_v)
    require_ok(vv > Fraction(0), "ZERO_HOUSEHOLDER_VEC", "Householder normal must be nonzero")
    scale = Fraction(2) * _dot_nq(normal_v, x) / vv
    return tuple(xi - scale * vi for xi, vi in zip(x, normal_v))


def verify_sphere_extrapolation_theorems() -> dict[str, Any]:
    s_grid = (
        Fraction(1, 20),
        Fraction(1, 5),
        Fraction(1, 2),
        Fraction(1, 1),
        Fraction(2, 1),
        Fraction(5, 1),
    )
    omega_grid = (
        Fraction(0, 1),
        Fraction(1, 4),
        Fraction(1, 2),
        Fraction(1, 1),
        Fraction(2, 1),
        Fraction(8, 1),
    )
    householder_v8: VecNQ = (
        Fraction(1), Fraction(-2), Fraction(3), Fraction(-1),
        Fraction(2), Fraction(1), Fraction(-3), Fraction(2),
    )

    angular_law_matches = 0
    saturation_bound_matches = 0
    householder_equiv_matches = 0
    monotonicity_matches = 0
    unit_norm_checks = 0
    raw_norm_checks = 0

    for s in s_grid:
        cos_t, sin_t = stereo_cos_sin_q(s)
        hr_8: VecNQ = (Fraction(1), Fraction(0)) + (Fraction(0),) * 6
        up_8: VecNQ = (Fraction(0), Fraction(1)) + (Fraction(0),) * 6
        h1_8: VecNQ = (cos_t, -sin_t) + (Fraction(0),) * 6

        hr_rot = _householder_apply_q(householder_v8, hr_8)
        h1_rot = _householder_apply_q(householder_v8, h1_8)
        if (
            cos_t * cos_t + sin_t * sin_t == Fraction(1)
            and _dot_nq(h1_8, h1_8) == Fraction(1)
            and _dot_nq(hr_rot, hr_rot) == Fraction(1)
            and _dot_nq(h1_rot, h1_rot) == Fraction(1)
            and _dot_nq(h1_rot, hr_rot) == cos_t
        ):
            unit_norm_checks += 1

        prev_tan: Fraction | None = None
        for w in omega_grid:
            raw = loopcd_hidden_raw_q(h1_8, hr_8, w)
            c_par = _dot_nq(raw, hr_8)
            c_perp = _dot_nq(raw, up_8)
            norm_sq = _dot_nq(raw, raw)
            expected_norm_sq = Fraction(1) + Fraction(2) * w * (Fraction(1) + w) * (Fraction(1) - cos_t)
            if c_par >= Fraction(1) and norm_sq == expected_norm_sq:
                raw_norm_checks += 1

            tan_from_vec = c_perp / c_par
            tan_from_trig = (w * sin_t) / (Fraction(1) + w * (Fraction(1) - cos_t))
            tan_closed = loopcd_tan_alpha_q(s, w)
            if tan_from_vec == tan_from_trig == tan_closed:
                angular_law_matches += 1

            cot_half = Fraction(1) / s
            margin = loopcd_chord_normal_margin_q(s, w)
            if cot_half - tan_closed == margin and margin > Fraction(0):
                saturation_bound_matches += 1

            raw_rot = loopcd_hidden_raw_q(h1_rot, hr_rot, w)
            if _householder_apply_q(householder_v8, raw) == raw_rot:
                householder_equiv_matches += 1

            if prev_tan is not None and tan_closed > prev_tan:
                monotonicity_matches += 1
            prev_tan = tan_closed

    cos_90, sin_90 = stereo_cos_sin_q(1)
    h1_90: VecNQ = (cos_90, -sin_90)
    slerp_90_w1: VecNQ = (-cos_90, sin_90)
    slerp_90_dot_h1 = _dot_nq(slerp_90_w1, h1_90)
    tan_loopcd_90_w1 = loopcd_tan_alpha_q(1, 1)

    cos_obt, sin_obt = stereo_cos_sin_q(2)
    slerp_2theta_sin = Fraction(2) * sin_obt * cos_obt
    raw_obt = loopcd_hidden_raw_q((cos_obt, -sin_obt), (Fraction(1), Fraction(0)), 1)
    loopcd_total_sin_num = sin_obt * raw_obt[0] + cos_obt * raw_obt[1]
    tan_loopcd_obt_w1 = loopcd_tan_alpha_q(2, 1)

    tan_small = loopcd_tan_alpha_q(Fraction(1, 20), Fraction(1, 2))
    rel_err_small = abs(tan_small - Fraction(1, 20)) / Fraction(1, 20)

    return {
        "grid_pairs_tested": len(s_grid) * len(omega_grid),
        "unit_norm_and_isometry_checks": unit_norm_checks,
        "raw_norm_identity_matches": raw_norm_checks,
        "angular_law_matches": angular_law_matches,
        "saturation_bound_matches": saturation_bound_matches,
        "householder_8d_equivariance_matches": householder_equiv_matches,
        "strict_omega_monotonicity_steps": monotonicity_matches,
        "witness_90deg_slerp_dot_h1": _frac_str(slerp_90_dot_h1),
        "witness_90deg_w1_tan_alpha": _frac_str(tan_loopcd_90_w1),
        "witness_obtuse_s2_slerp_sin2theta": _frac_str(slerp_2theta_sin),
        "witness_obtuse_s2_loopcd_total_sin_num": _frac_str(loopcd_total_sin_num),
        "witness_obtuse_s2_loopcd_tan_alpha": _frac_str(tan_loopcd_obt_w1),
        "witness_small_s1_20_w1_2_tan_alpha": _frac_str(tan_small),
        "witness_small_s1_20_w1_2_rel_diff": _frac_str(rel_err_small),
    }


def verify_su2_holonomy_extrapolation_theorems() -> dict[str, Any]:
    witness_pairs: tuple[tuple[Vec3Q, Vec3Q], ...] = (
        ((Fraction(1, 5), Fraction(0), Fraction(0)), (Fraction(0), Fraction(1, 4), Fraction(0))),
        ((Fraction(2, 5), Fraction(-1, 5), Fraction(1, 10)), (Fraction(1, 5), Fraction(3, 10), Fraction(-2, 5))),
        ((Fraction(-3, 5), Fraction(0), Fraction(2, 5)), (Fraction(2, 5), Fraction(2, 5), Fraction(-1, 5))),
        ((Fraction(4, 5), Fraction(0), Fraction(0)), (Fraction(-4, 5), Fraction(0), Fraction(0))),
    )
    omega_vals = (Fraction(-1), Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(1))

    delta_identity_matches = 0
    bch_product_matches = 0
    endpoint_w0_matches = 0
    endpoint_wm1_matches = 0
    exact_step_w1_matches = 0
    su2_unit_matches = 0
    min_rel_denom = Fraction(100)

    for w1, wr in witness_pairs:
        u1 = cayley_su2_q(w1)
        ur = cayley_su2_q(wr)
        if _quat_norm_sq_q(u1) == Fraction(1) and _quat_norm_sq_q(ur) == Fraction(1):
            su2_unit_matches += 1

        rel_denom = Fraction(1) + _dot3_q(w1, w1) * _dot3_q(wr, wr) + Fraction(2) * _dot3_q(w1, wr)
        if rel_denom < min_rel_denom:
            min_rel_denom = rel_denom

        delta_u = _quat_mul_q(_quat_conj_q(u1), ur)
        w_delta = su2_relative_cayley_delta_q(w1, wr, enforce_acute_ball=True)
        if cayley_su2_q(w_delta) == delta_u and inv_cayley_su2_q(delta_u) == w_delta:
            delta_identity_matches += 1

        u_exact_w1 = _quat_mul_q(ur, delta_u)

        for om in omega_vals:
            w_bch = su2_cayley_exact_bch_guide_q(w1, wr, om, enforce_acute_ball=True)
            u_bch = cayley_su2_q(w_bch)
            w_delta_scaled = (om * w_delta[0], om * w_delta[1], om * w_delta[2])
            u_rhs = _quat_mul_q(ur, cayley_su2_q(w_delta_scaled))
            if u_bch == u_rhs:
                bch_product_matches += 1

            w_lin = su2_cayley_linear_guide_q(w1, wr, om)
            if om == Fraction(0) and w_lin == wr and w_bch == wr and u_bch == ur:
                endpoint_w0_matches += 1
            if om == Fraction(-1) and w_lin == w1 and w_bch == w1 and u_bch == u1:
                endpoint_wm1_matches += 1
            if om == Fraction(1) and u_bch == u_exact_w1 and _quat_dist_sq_q(u_bch, u_exact_w1) == Fraction(0):
                exact_step_w1_matches += 1

    left_order_errs: list[Fraction] = []
    right_order_errs: list[Fraction] = []
    exact_bch_errs: list[Fraction] = []
    strang_hierarchy_matches = 0
    for k in (0, 1, 2, 3):
        lam = Fraction(1, 1 << k)
        w1_s: Vec3Q = (lam * Fraction(1, 5), Fraction(0), Fraction(0))
        wr_s: Vec3Q = (Fraction(0), lam * Fraction(1, 4), Fraction(0))
        u1_s = cayley_su2_q(w1_s)
        ur_s = cayley_su2_q(wr_s)
        du_s = _quat_mul_q(_quat_conj_q(u1_s), ur_s)
        u_right = _quat_mul_q(ur_s, du_s)
        u_left = _quat_mul_q(du_s, ur_s)
        u_lin = cayley_su2_q(su2_cayley_linear_guide_q(w1_s, wr_s, 1))
        u_exact_bch = cayley_su2_q(su2_cayley_exact_bch_guide_q(w1_s, wr_s, 1))
        e_left = _quat_dist_sq_q(u_lin, u_left)
        e_right = _quat_dist_sq_q(u_lin, u_right)
        e_bch = _quat_dist_sq_q(u_exact_bch, u_right)
        if e_bch == Fraction(0) and Fraction(0) < e_right < e_left:
            strang_hierarchy_matches += 1
        left_order_errs.append(e_left)
        right_order_errs.append(e_right)
        exact_bch_errs.append(e_bch)

    left_ratio = left_order_errs[2] / left_order_errs[3]
    right_ratio = right_order_errs[2] / right_order_errs[3]
    om_tie = adaptive_omega_top2_q(Fraction(1, 2), Fraction(1, 3), Fraction(1, 3))
    om_settled = adaptive_omega_top2_q(Fraction(1, 2), Fraction(1, 1), Fraction(0, 1))

    return {
        "witness_pairs_tested": len(witness_pairs),
        "su2_unit_norm_matches": su2_unit_matches,
        "min_acute_ball_cayley_denom": _frac_str(min_rel_denom),
        "delta_cayley_identity_matches": delta_identity_matches,
        "exact_bch_product_matches": bch_product_matches,
        "endpoint_omega_0_matches": endpoint_w0_matches,
        "endpoint_omega_minus1_matches": endpoint_wm1_matches,
        "exact_geodesic_omega_1_matches": exact_step_w1_matches,
        "strang_hierarchy_scale_matches": strang_hierarchy_matches,
        "dyadic_lam1_8_err_sq_left_order": _frac_str(left_order_errs[3]),
        "dyadic_lam1_8_err_sq_right_strang_linear": _frac_str(right_order_errs[3]),
        "dyadic_lam1_8_err_sq_exact_cayley_bch": _frac_str(exact_bch_errs[3]),
        "dyadic_halving_ratio_left_order": _frac_str(left_ratio),
        "dyadic_halving_ratio_right_strang_linear": _frac_str(right_ratio),
        "adaptive_tie_omega": _frac_str(om_tie),
        "adaptive_settled_omega": _frac_str(om_settled),
    }


def build_certificate() -> dict[str, Any]:
    s_res = verify_sphere_extrapolation_theorems()
    u_res = verify_su2_holonomy_extrapolation_theorems()
    payload: dict[str, Any] = {
        "schema_version": "aletheia.s121_loopcd_sphere_su2_geometry.v1",
        "track": "S121",
        "queue_id": "EXP-Q25a",
        "sphere_rmsnorm_theorems": s_res,
        "su2_holonomy_theorems": u_res,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["payload_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def validate_certificate(cert: dict[str, Any]) -> None:
    sp = cert["sphere_rmsnorm_theorems"]
    require_ok(
        sp["grid_pairs_tested"] == 36
        and sp["unit_norm_and_isometry_checks"] == 6
        and sp["raw_norm_identity_matches"] == 36
        and sp["angular_law_matches"] == 36
        and sp["saturation_bound_matches"] == 36
        and sp["householder_8d_equivariance_matches"] == 36
        and sp["strict_omega_monotonicity_steps"] == 30
        and sp["witness_90deg_slerp_dot_h1"] == "-1/1"
        and sp["witness_90deg_w1_tan_alpha"] == "1/2"
        and sp["witness_obtuse_s2_slerp_sin2theta"] == "-24/25"
        and sp["witness_obtuse_s2_loopcd_total_sin_num"] == "8/5"
        and sp["witness_obtuse_s2_loopcd_tan_alpha"] == "4/13"
        and sp["witness_small_s1_20_w1_2_tan_alpha"] == "10/201"
        and sp["witness_small_s1_20_w1_2_rel_diff"] == "1/201",
        "SPHERE_CERT_INVALID",
        "S^{d-1} LoopCD-Hidden + RMSNorm theorem counts failed",
    )
    su = cert["su2_holonomy_theorems"]
    left_r = Fraction(su["dyadic_halving_ratio_left_order"])
    right_r = Fraction(su["dyadic_halving_ratio_right_strang_linear"])
    require_ok(
        su["witness_pairs_tested"] == 4
        and su["su2_unit_norm_matches"] == 4
        and su["min_acute_ball_cayley_denom"] == "81/625"
        and su["delta_cayley_identity_matches"] == 4
        and su["exact_bch_product_matches"] == 20
        and su["endpoint_omega_0_matches"] == 4
        and su["endpoint_omega_minus1_matches"] == 4
        and su["exact_geodesic_omega_1_matches"] == 4
        and su["strang_hierarchy_scale_matches"] == 4
        and su["dyadic_lam1_8_err_sq_exact_cayley_bch"] == "0/1"
        and Fraction(15) < left_r < Fraction(17)
        and right_r > Fraction(60)
        and su["adaptive_tie_omega"] == "1/2"
        and su["adaptive_settled_omega"] == "0/1",
        "SU2_CERT_INVALID",
        "SU(2) spinor-holonomy extrapolation theorem counts failed",
    )
    sha_val = cert.get("payload_sha256")
    require_ok(type(sha_val) is str, "CERT_SHA_MISSING", "payload_sha256 must be a string")
    body = {k: v for k, v in cert.items() if k != "payload_sha256"}
    expected_sha = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    require_ok(hmac.compare_digest(sha_val, expected_sha), "CERT_SHA_MISMATCH", "payload_sha256 digest mismatch")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EXP-Q25a Exact LoopCD S^{d-1} & SU(2) Holonomy Geometry Oracle.")
    parser.add_argument("--json", action="store_true", help="Emit canonical JSON certificate.")
    parser.add_argument("--check", action="store_true", help="Run fail-closed theorem verification.")
    args = parser.parse_args(argv)

    try:
        cert = build_certificate()
        validate_certificate(cert)
    except LoopCDGeometryError as exc:
        sys.stderr.write(f"FAIL S121_LOOPCD_GEOMETRY {exc}\n")
        return 2
    if args.json:
        sys.stdout.write(json.dumps(cert, sort_keys=True, indent=2) + "\n")
    elif args.check:
        sys.stdout.write(f"PASS S121_LOOPCD_GEOMETRY payload_sha256={cert['payload_sha256']}\n")
    else:
        sp = cert["sphere_rmsnorm_theorems"]
        su = cert["su2_holonomy_theorems"]
        sys.stdout.write(
            f"S121_LOOPCD_GEOMETRY_OK sphere_law={sp['angular_law_matches']}/36 "
            f"sat_bound={sp['saturation_bound_matches']}/36 "
            f"su2_cayley_bch={su['exact_bch_product_matches']}/20 "
            f"min_denom={su['min_acute_ball_cayley_denom']} "
            f"payload_sha256={cert['payload_sha256']}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
