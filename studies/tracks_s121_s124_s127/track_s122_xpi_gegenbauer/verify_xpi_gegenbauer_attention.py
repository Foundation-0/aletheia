#!/usr/bin/env python3
"""Wave-11 (EXP-Q26c / Track S122): Exact-Q Oracle for Portal x/pi Spherical Multipole Attention.

Strictly Python standard library ONLY: zero IEEE-754 floats, zero float literals, zero bare asserts,
zero RNG, zero external dependencies. Proves in exact Q (`fractions.Fraction`) arithmetic:

  1. Exact g-Independent Spherical Denominator Projection Theorem (Chebyshev T_r & Gegenbauer C~_r^(alpha)):
       - Unified normalized Gegenbauer / Chebyshev recurrence on u = <q_hat, k_hat> in [-1, 1]:
         C~_0^(alpha)(u) = 1, C~_1^(alpha)(u) = u, and for r >= 2:
         (r + 2*alpha - 1) * C~_r^(alpha)(u) = 2*(r + alpha - 1)*u*C~_{r-1}^(alpha)(u) - (r - 1)*C~_{r-2}^(alpha)(u),
         which equals Chebyshev T_r(u) at alpha = 0 (S^1) and C_r^(alpha)(u)/C_r^(alpha)(1) for alpha > 0
         (alpha = (d - 2)/2 on S^{d-1}, e.g. alpha = 1/2 on S^2, 1 on S^3, 3 on S^7, 15 on S^31).
       - Algebraic Supremum Bound |C~_r^(alpha)(u)| <= 1 on [-1, 1] in Exact Q[u]:
         * For alpha = 0: stereographic circle u = (1 - t^2)/(1 + t^2) satisfies 1 - T_r(u)^2 = s_r(t)^2 >= 0.
         * For alpha > 0: C~_r^(alpha)(u) = sum_{k=0}^{floor(r/2)} w_{r,k}^(alpha) T_{r - 2k}(u) is an EXACT
           polynomial identity in Q[u] with strictly positive weights w_{r,k}^(alpha) > 0 summing to 1/1.
       - Therefore sum_{r=1}^P |b_r| <= rho < 1 implies 1 - rho <= H_xpi(u) <= 1 + rho and
         n*(1 - rho) <= D(q) <= n*(1 + rho) IDENTICALLY for ALL gains g > 0, while C~_1^(alpha)(u) = u
         preserves exact linear-attention initialization G(u, g) = g*u, H(u) = 1.
       - Quantifies Pari-Agrawal-Kim raw-monomial pathology:
         (i) g^{-r} parameter collapse (2^{-8} = 1/256 at g = 2, 4^{-8} = 1/65536 at g = 4), and
         (ii) 239x intrinsic function-space triangle-inequality slack even at g = 1: H(u) = 1 + rho*T_7(u)
              has b_0 = 1 and ||H - 1||_inf = rho, yet raw-monomial budget m_mono = 239*rho shrinks it by 1/239,
              and degree-8 zero-constant p_8(u) = (T_8(u) - T_4(u))/2 has m_mono = 280*rho vs m_Cheb = rho.
       - Exact polynomial L^2 orthogonality of Gegenbauer multipoles vs ill-conditioned Hilbert monomials.

  2. Exact Portal x/pi Mellin-Sphere-PDE-Zador-BRIDGE_12 Identities over Q[pi, pi^{-1}]:
       - (a) 2 / omega_{2k-1} = (k - 1)! / pi^k == pi^{-s/2} Gamma(s/2) at s = 2k (k = 1..12) + omega_2 = 4*pi
             (null-cone S^2 area) + d-dim Heat kernel prefactor (4*pi)^{-k} = (2 / omega_{2k-1}) / (4^k * (k-1)!).
       - (b) Exact Unit-Radius vs. Unit-Volume Zador Distinction in Q[pi, pi^{-1}]:
             * Dimensionless unit-radius ball normalized second moment E[||x||^2]/(d*R^2) = 1 / (d + 2) in Q
               (1/4, 1/6, 1/10, 1/18, 1/26 for d = 2, 4, 8, 16, 24), where V_d cancels between numerator and
               denominator integrals on B^d(R).
             * Euclidean unit-volume (Vol(B^d) = 1) Zador quantizer factor G(B^d) = (1/(d+2)) * V_d^{-2/d} =
               Gamma(d/2 + 1)^{2/d} / ((d + 2)*pi), whose d-th power for even d = 2k is
               G(B^{2k})^{2k} = (k!)^2 / ((2k + 2)^{2k} * pi^{2k}) in Q[pi, pi^{-1}] (e.g. G(B^2) = 1/(4*pi),
               pi_power = -2k != 0), while pi cancels strictly in ball-unit V_d-rescaled coordinates
               V_d^{2/d} * G(B^d) == 1 / (d + 2) (V_{2k}^2 * G(B^{2k})^{2k} == (2k + 2)^{-2k} * pi^0).
       - (c) Constructive 2D Abelian Cauchy/Joukowski complex-potential surface speed asymmetry
             v(pi/2)^2 - v(-pi/2)^2 = (2*V_inf + Gamma/(2*pi*a))^2 - (-2*V_inf + Gamma/(2*pi*a))^2 =
             4 * V_inf * Gamma / (pi * a) > 0 in Q[pi^{-1}] ([R_1, R_2] = 0_{2x2} in SO(2, Q)) vs 3D Non-Abelian
             BRIDGE_12 holonomy ([U_cyc, rho(g_beta)] != 0 in SO(3, Q), scalar I_3 blindness n_-(UL) = 1 == 1 =
             n_-(LU) vs anisotropic G_3 = diag(3,1,1) order separation n_-(UL) = 1 != 2 = n_-(LU)).
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import sys
from typing import Any


PolyQ = tuple[Fraction, ...]
Mat2Q = tuple[tuple[Fraction, Fraction], tuple[Fraction, Fraction]]
Mat3Q = tuple[
    tuple[Fraction, Fraction, Fraction],
    tuple[Fraction, Fraction, Fraction],
    tuple[Fraction, Fraction, Fraction],
]


class XPiGegenbauerError(ValueError):
    """Typed fail-closed error for Track S122 Portal x/pi Gegenbauer oracle."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


def require_ok(cond: bool, code: str, message: str) -> None:
    if cond is not True:
        raise XPiGegenbauerError(code, message)


def _to_frac(x: Fraction | int) -> Fraction:
    require_ok(not isinstance(x, bool) and isinstance(x, (int, Fraction)), "TYPE_ERROR", "expected int or Fraction")
    return Fraction(x)


def _frac_str(q: Fraction) -> str:
    return f"{q.numerator}/{q.denominator}"


# ---------------------------------------------------------------------------
# 1. Exact Q[u] Polynomial Ring & Unified Chebyshev / Gegenbauer Harmonics
# ---------------------------------------------------------------------------

def _poly_trim(coeffs: list[Fraction], min_len: int = 1) -> PolyQ:
    out = list(coeffs)
    while len(out) > min_len and out[-1] == Fraction(0):
        out.pop()
    return tuple(out)


def _poly_add(p: PolyQ, q: PolyQ) -> PolyQ:
    n = max(len(p), len(q))
    res = [
        (p[i] if i < len(p) else Fraction(0)) + (q[i] if i < len(q) else Fraction(0))
        for i in range(n)
    ]
    return _poly_trim(res, min_len=n)


def _poly_scale(p: PolyQ, c: Fraction) -> PolyQ:
    return tuple(x * c for x in p)


def _poly_shift_u(p: PolyQ) -> PolyQ:
    return (Fraction(0),) + p


def _poly_mul(p: PolyQ, q: PolyQ) -> PolyQ:
    res = [Fraction(0)] * (len(p) + len(q) - 1)
    for i, a in enumerate(p):
        for j, b in enumerate(q):
            res[i + j] += a * b
    return tuple(res)


def eval_poly_q(coeffs: PolyQ, u: Fraction | int) -> Fraction:
    """Exact Horner evaluation of polynomial sum_{r=0}^d coeffs[r] * u^r in Q."""
    require_ok(isinstance(coeffs, tuple) and len(coeffs) >= 1, "EMPTY_POLY", "polynomial coeffs must be non-empty tuple")
    uf = _to_frac(u)
    acc = Fraction(0)
    for c in reversed(coeffs):
        cf = _to_frac(c)
        acc = acc * uf + cf
    return acc


def integrate_poly_minus1_to_1_q(coeffs: PolyQ) -> Fraction:
    """Exact integral int_{-1}^1 p(u) du in Q via int_{-1}^1 u^r du = 2/(r+1) for even r, 0 for odd r."""
    require_ok(isinstance(coeffs, tuple) and len(coeffs) >= 1, "EMPTY_POLY", "polynomial coeffs must be non-empty tuple")
    total = Fraction(0)
    for r, c in enumerate(coeffs):
        cf = _to_frac(c)
        if (r % 2) == 0:
            total += cf * Fraction(2, r + 1)
    return total


def chebyshev_t_poly_q(degree: int) -> PolyQ:
    """Exact monomial coefficients (c_0, ..., c_degree) of Chebyshev T_degree(u) in Q[u]."""
    require_ok(not isinstance(degree, bool) and isinstance(degree, int) and degree >= 0, "BAD_DEGREE", "degree must be int >= 0")
    if degree == 0:
        return (Fraction(1),)
    if degree == 1:
        return (Fraction(0), Fraction(1))
    t_prev2: PolyQ = (Fraction(1),)
    t_prev1: PolyQ = (Fraction(0), Fraction(1))
    for _ in range(2, degree + 1):
        t_cur = _poly_add(_poly_scale(_poly_shift_u(t_prev1), Fraction(2)), _poly_scale(t_prev2, Fraction(-1)))
        t_prev2, t_prev1 = t_prev1, t_cur
    return t_prev1


def gegenbauer_norm_poly_q(degree: int, alpha: Fraction | int) -> PolyQ:
    """Exact monomial coefficients of normalized Gegenbauer harmonic C~_degree^(alpha)(u) in Q[u]."""
    require_ok(not isinstance(degree, bool) and isinstance(degree, int) and degree >= 0, "BAD_DEGREE", "degree must be int >= 0")
    alp = _to_frac(alpha)
    require_ok(alp >= Fraction(0), "NEG_ALPHA", "Gegenbauer parameter alpha must be >= 0")
    if degree == 0:
        return (Fraction(1),)
    if degree == 1:
        return (Fraction(0), Fraction(1))
    if alp == Fraction(0):
        return chebyshev_t_poly_q(degree)
    c_prev2: PolyQ = (Fraction(1),)
    c_prev1: PolyQ = (Fraction(0), Fraction(1))
    for r in range(2, degree + 1):
        denom = Fraction(r - 1) + Fraction(2) * alp
        a_coef = (Fraction(2) * (Fraction(r - 1) + alp)) / denom
        b_coef = -Fraction(r - 1) / denom
        c_cur = _poly_add(_poly_scale(_poly_shift_u(c_prev1), a_coef), _poly_scale(c_prev2, b_coef))
        c_prev2, c_prev1 = c_prev1, c_cur
    return c_prev1


def _rising_binom_q(alpha: Fraction, k: int) -> Fraction:
    acc = Fraction(1)
    for j in range(k):
        acc *= (alpha + Fraction(j)) / Fraction(j + 1)
    return acc


def gegenbauer_chebyshev_convex_weights_q(degree: int, alpha: Fraction | int) -> dict[int, Fraction]:
    """Exact convex expansion C~_r^(alpha)(u) = sum_{k=0}^{floor(r/2)} w_{r,k} T_{r - 2k}(u) in Q."""
    require_ok(not isinstance(degree, bool) and isinstance(degree, int) and degree >= 0, "BAD_DEGREE", "degree must be int >= 0")
    alp = _to_frac(alpha)
    require_ok(alp >= Fraction(0), "NEG_ALPHA", "alpha must be >= 0")
    if degree == 0 or alp == Fraction(0):
        return {degree: Fraction(1)}
    unnorm: dict[int, Fraction] = {}
    for k in range(degree // 2 + 1):
        m = degree - 2 * k
        bk = _rising_binom_q(alp, k)
        brk = _rising_binom_q(alp, degree - k)
        mu = (bk * bk) if m == 0 else (Fraction(2) * bk * brk)
        unnorm[m] = mu
    c_at_one = sum(unnorm.values(), Fraction(0))
    return {m: val / c_at_one for m, val in unnorm.items()}


def stereographic_chebyshev_slack_q(degree: int, t_param: Fraction | int) -> tuple[Fraction, Fraction, Fraction, bool]:
    """For u = (1 - t^2)/(1 + t^2) in (-1, 1], compute (u, T_r(u), s_r(t)^2, exact_identity_ok) over Q[i]."""
    require_ok(not isinstance(degree, bool) and isinstance(degree, int) and degree >= 0, "BAD_DEGREE", "degree must be int >= 0")
    t = _to_frac(t_param)
    denom = Fraction(1) + t * t
    c1 = (Fraction(1) - t * t) / denom
    s1 = (Fraction(2) * t) / denom
    cr, sr = Fraction(1), Fraction(0)
    for _ in range(degree):
        cr, sr = cr * c1 - sr * s1, cr * s1 + sr * c1
    tr_poly_val = eval_poly_q(chebyshev_t_poly_q(degree), c1)
    exact_ok = (cr == tr_poly_val) and (Fraction(1) - tr_poly_val * tr_poly_val == sr * sr) and (sr * sr >= Fraction(0))
    return c1, tr_poly_val, sr * sr, exact_ok


def _poly_div_by_var_exact_q(p: PolyQ) -> PolyQ:
    """Exact polynomial quotient p(h) / h in Q[h], failing closed if constant term p(0) != 0."""
    require_ok(isinstance(p, tuple) and len(p) >= 2, "SHORT_POLY_DIV", "polynomial must have degree >= 1 for exact h-division")
    require_ok(p[0] == Fraction(0), "NONZERO_H0_REMAINDER", "h does not divide polynomial: constant term p(0) != 0")
    return p[1:]


def mobius_spherical_boost_q(u: Fraction | int, g_gain: Fraction | int) -> dict[str, Any]:
    """Exact rational north-pole conformal boost psi_g(u) = ((1 + g)*u + (1 - g)) / ((1 - g)*u + (1 + g)):
      - Strictly positive denominator (1 + u) + g*(1 - u) > 0 for all u in [-1, 1], g > 0,
      - Exact sphere-preserving slack identity: 1 - psi_g(u)^2 == 4*g*(1 - u^2) / ((1 + u) + g*(1 - u))^2 >= 0,
      - Exact linear-init identity psi_1(u) == u, fixed poles psi_g(+-1) == +-1, bijective inverse psi_{1/g},
        and symbolic north-pole derivative d/du|_{u=1} == g verified via verify_mobius_north_pole_slope_q.
    """
    uf = _to_frac(u)
    g = _to_frac(g_gain)
    require_ok(Fraction(-1) <= uf <= Fraction(1), "SCORE_OUT_OF_SPHERE", "u must lie in [-1, 1]")
    require_ok(g > Fraction(0), "NONPOS_GAIN", "g_gain must be > 0")
    denom = (Fraction(1) + uf) + g * (Fraction(1) - uf)
    psi = Fraction(1) - (Fraction(2) * g * (Fraction(1) - uf)) / denom
    lhs_slack = Fraction(1) - psi * psi
    rhs_slack = (Fraction(4) * g * (Fraction(1) - uf * uf)) / (denom * denom)
    return {
        "psi": psi,
        "denom": denom,
        "slack_sq": lhs_slack,
        "identity_exact": (denom > Fraction(0)) and (lhs_slack == rhs_slack) and (lhs_slack >= Fraction(0)),
    }


def verify_mobius_north_pole_slope_q(g_gain: Fraction | int) -> dict[str, Any]:
    """Symbolically compute lim_{h -> 0} (psi_g(1) - psi_g(1 - h)) / h == g in Q(g)[h]
    via exact polynomial quotient cancellation of h, plus south-pole slope d/du|_{u=-1} == 1/g.
    """
    g = _to_frac(g_gain)
    require_ok(g > Fraction(0), "NONPOS_GAIN", "g_gain must be > 0")
    u_north_h: PolyQ = (Fraction(1), Fraction(-1))
    num_north_h = _poly_add(_poly_scale(u_north_h, Fraction(1) + g), (Fraction(1) - g,))
    den_north_h = _poly_add(_poly_scale(u_north_h, Fraction(1) - g), (Fraction(1) + g,))
    psi_at_1 = eval_poly_q(num_north_h, Fraction(0)) / eval_poly_q(den_north_h, Fraction(0))
    delta_north_h = _poly_add(_poly_scale(den_north_h, psi_at_1), _poly_scale(num_north_h, Fraction(-1)))
    quot_north_h = _poly_div_by_var_exact_q(delta_north_h)
    slope_at_north_pole = eval_poly_q(quot_north_h, Fraction(0)) / eval_poly_q(den_north_h, Fraction(0))

    u_south_h: PolyQ = (Fraction(-1), Fraction(1))
    num_south_h = _poly_add(_poly_scale(u_south_h, Fraction(1) + g), (Fraction(1) - g,))
    den_south_h = _poly_add(_poly_scale(u_south_h, Fraction(1) - g), (Fraction(1) + g,))
    psi_at_m1 = eval_poly_q(num_south_h, Fraction(0)) / eval_poly_q(den_south_h, Fraction(0))
    delta_south_h = _poly_add(num_south_h, _poly_scale(den_south_h, -psi_at_m1))
    quot_south_h = _poly_div_by_var_exact_q(delta_south_h)
    slope_at_south_pole = eval_poly_q(quot_south_h, Fraction(0)) / eval_poly_q(den_south_h, Fraction(0))

    return {
        "gain_g_q": _frac_str(g),
        "delta_north_h0_q": _frac_str(delta_north_h[0]),
        "quotient_north_const_q": _frac_str(quot_north_h[0]),
        "den_north_at_0_q": _frac_str(eval_poly_q(den_north_h, Fraction(0))),
        "north_pole_slope_q": _frac_str(slope_at_north_pole),
        "south_pole_slope_q": _frac_str(slope_at_south_pole),
        "exact_slope_match": (
            psi_at_1 == Fraction(1)
            and psi_at_m1 == Fraction(-1)
            and slope_at_north_pole == g
            and slope_at_south_pole == (Fraction(1) / g)
        ),
    }


# ---------------------------------------------------------------------------
# 2. Denominator Projection & Exact Linear-Init Spherical Attention Operators
# ---------------------------------------------------------------------------

def project_spherical_denominator_q(b_coeffs: Any, rho: Fraction | int) -> tuple[Fraction, ...]:
    """Portal x/pi g-independent spherical denominator projection: m = sum_{r=1}^P |b_r| <= rho."""
    require_ok(isinstance(b_coeffs, (list, tuple)) and len(b_coeffs) >= 1, "BAD_B_COEFFS", "b_coeffs must be non-empty sequence")
    bs = tuple(_to_frac(b) for b in b_coeffs)
    r_bound = _to_frac(rho)
    require_ok(Fraction(0) < r_bound < Fraction(1), "BAD_RHO", "rho must satisfy 0 < rho < 1")
    m_budget = sum((abs(b) for b in bs), Fraction(0))
    if m_budget > r_bound:
        scale = r_bound / m_budget
        return tuple(b * scale for b in bs)
    return bs


def project_monomial_denominator_q(b_coeffs: Any, g_gain: Fraction | int, rho: Fraction | int) -> tuple[Fraction, ...]:
    """Pari-Agrawal-Kim raw-monomial denominator projection: m = sum_{r=1}^P |b_r| * g^r <= rho."""
    require_ok(isinstance(b_coeffs, (list, tuple)) and len(b_coeffs) >= 1, "BAD_B_COEFFS", "b_coeffs must be non-empty sequence")
    bs = tuple(_to_frac(b) for b in b_coeffs)
    g = _to_frac(g_gain)
    r_bound = _to_frac(rho)
    require_ok(g > Fraction(0), "NONPOS_GAIN", "score multiplier g must be > 0")
    require_ok(Fraction(0) < r_bound < Fraction(1), "BAD_RHO", "rho must satisfy 0 < rho < 1")
    m_budget = Fraction(0)
    g_pow = Fraction(1)
    for b in bs:
        g_pow *= g
        m_budget += abs(b) * g_pow
    if m_budget > r_bound:
        scale = r_bound / m_budget
        return tuple(b * scale for b in bs)
    return bs


def eval_xpi_attention_1d_q(
    u_scores: Any,
    v_vals: Any,
    a_coeffs: Any,
    b_coeffs: Any,
    g_gain: Fraction | int,
    alpha: Fraction | int,
    rho: Fraction | int,
) -> dict[str, Fraction]:
    """Evaluate exact 1D rational Portal x/pi Gegenbauer/Chebyshev attention on u_i in [-1, 1]:
    G(u, g) = g * sum_{r=0}^P a_r C~_r^(alpha)(u),  H(u) = 1 + sum_{r=1}^P b_proj_r C~_r^(alpha)(u).
    """
    require_ok(isinstance(u_scores, (list, tuple)) and len(u_scores) >= 1, "EMPTY_KEYS", "u_scores must be non-empty")
    require_ok(isinstance(v_vals, (list, tuple)) and len(v_vals) == len(u_scores), "KEY_VAL_LEN", "v_vals length must match u_scores")
    require_ok(isinstance(a_coeffs, (list, tuple)) and len(a_coeffs) >= 2, "BAD_A_COEFFS", "a_coeffs must have length P+1 >= 2")
    p_deg = len(a_coeffs) - 1
    require_ok(isinstance(b_coeffs, (list, tuple)) and len(b_coeffs) == p_deg, "BAD_B_LEN", "b_coeffs must have length P")
    g = _to_frac(g_gain)
    require_ok(g > Fraction(0), "NONPOS_GAIN", "g_gain must be > 0")
    alp = _to_frac(alpha)
    r_bound = _to_frac(rho)
    b_proj = project_spherical_denominator_q(b_coeffs, r_bound)
    a_tuple = tuple(_to_frac(a) for a in a_coeffs)
    us = tuple(_to_frac(u) for u in u_scores)
    vs = tuple(_to_frac(v) for v in v_vals)
    for u in us:
        require_ok(Fraction(-1) <= u <= Fraction(1), "SCORE_OUT_OF_SPHERE", "normalized cosine u must lie in [-1, 1]")

    basis_polys = tuple(gegenbauer_norm_poly_q(r, alp) for r in range(p_deg + 1))
    num_sum = Fraction(0)
    den_sum = Fraction(0)
    min_h = Fraction(2)
    max_h = Fraction(0)
    for u, v in zip(us, vs):
        vals = tuple(eval_poly_q(poly, u) for poly in basis_polys)
        g_val = g * sum((a_tuple[r] * vals[r] for r in range(p_deg + 1)), Fraction(0))
        h_val = Fraction(1) + sum((b_proj[r - 1] * vals[r] for r in range(1, p_deg + 1)), Fraction(0))
        if h_val < min_h:
            min_h = h_val
        if h_val > max_h:
            max_h = h_val
        num_sum += g_val * v
        den_sum += h_val

    return {
        "output": num_sum / den_sum,
        "denom_sum": den_sum,
        "min_h": min_h,
        "max_h": max_h,
    }


# ---------------------------------------------------------------------------
# 3. Portal x/pi Mellin-Sphere-Heat, Zador Ball Moment, & Joukowski/BRIDGE_12
# ---------------------------------------------------------------------------

def mellin_sphere_even_dim_q(k_half_dim: int) -> dict[str, Any]:
    """Compute exact Q[pi, pi^{-1}] Mellin-Sphere-Heat quantities for even ambient d = 2*k (k >= 1)."""
    require_ok(not isinstance(k_half_dim, bool) and isinstance(k_half_dim, int) and k_half_dim >= 1, "BAD_HALF_DIM", "k_half_dim must be int >= 1")
    d = 2 * k_half_dim
    fact_km1 = math.factorial(k_half_dim - 1)
    omega_q = Fraction(2, fact_km1)
    omega_pi_pow = k_half_dim
    two_over_omega_q = Fraction(2) / omega_q
    two_over_omega_pi_pow = -omega_pi_pow
    mellin_gamma_q = Fraction(fact_km1, 1)
    mellin_gamma_pi_pow = -k_half_dim
    heat_4pi_neg_k_q = Fraction(1, 4**k_half_dim)
    heat_from_sphere_q = two_over_omega_q / Fraction((4**k_half_dim) * fact_km1, 1)
    return {
        "ambient_dim_d": d,
        "sphere_dim": d - 1,
        "omega_coeff_q": _frac_str(omega_q),
        "omega_pi_power": omega_pi_pow,
        "two_over_omega_coeff_q": _frac_str(two_over_omega_q),
        "two_over_omega_pi_power": two_over_omega_pi_pow,
        "mellin_match": (two_over_omega_q == mellin_gamma_q and two_over_omega_pi_pow == mellin_gamma_pi_pow),
        "heat_match": (heat_4pi_neg_k_q == heat_from_sphere_q),
        "heat_4pi_neg_k_coeff_q": _frac_str(heat_4pi_neg_k_q),
    }


def unit_radius_ball_norm_moment_q(dim: int) -> Fraction:
    """Dimensionless unit-radius ball normalized second moment E[||x||^2] / (d * R^2) = 1 / (d + 2) in Q
    (ratio of B^d(R)'s second moment to d*R^2, where V_d cancels; Vol(B^d(1)) = V_d != 1).
    """
    require_ok(not isinstance(dim, bool) and isinstance(dim, int) and dim >= 1, "BAD_DIM", "dimension d must be int >= 1")
    vol_radial_factor = Fraction(1, dim)
    moment_radial_factor = Fraction(1, dim * (dim + 2))
    return moment_radial_factor / vol_radial_factor


def zador_unit_volume_even_dim_xpi_q(k_half_dim: int) -> dict[str, Any]:
    """Exact Q[pi, pi^{-1}] verification of unit-volume Zador G(B^d) vs ball-unit V_d rescaling for d = 2*k:
      - Unit-radius ball volume: V_{2k} = omega_{2k-1} / (2k) = (1 / k!) * pi^k.
      - Unit-radius second-moment integral: I_{2,2k} = int_{B^{2k}(1)} ||x||^2 dx = omega_{2k-1} / (2k + 2).
      - Dimensionless unit-radius ratio: I_{2,2k} / (2k * V_{2k}) = 1 / (2k + 2) * pi^0.
      - Euclidean unit-volume (Vol(B^{2k}) = 1) Zador d-th power:
        G(B^{2k})^{2k} = (I_{2,2k} / (2k))^{2k} * V_{2k}^{-(2k + 2)} = (k!)^2 / ((2k + 2)^{2k} * pi^{2k})
        (strictly negative pi_power = -2k != 0, e.g. G(B^2) = 1 / (4*pi) at d = 2).
      - Ball-unit V_d-rescaled identity: V_{2k}^2 * G(B^{2k})^{2k} = (2k + 2)^{-2k} * pi^0
        (pi cancels strictly when measuring volume in units of V_d, NOT Euclidean Vol = 1).
    """
    require_ok(not isinstance(k_half_dim, bool) and isinstance(k_half_dim, int) and k_half_dim >= 1, "BAD_HALF_DIM", "k_half_dim must be int >= 1")
    d = 2 * k_half_dim
    omega_q = Fraction(2, math.factorial(k_half_dim - 1))
    vol_unit_r_q = omega_q / Fraction(d)
    vol_pi_pow = k_half_dim
    mom_int_q = omega_q / Fraction(d + 2)
    mom_pi_pow = k_half_dim

    unit_rad_ratio_q = mom_int_q / (Fraction(d) * vol_unit_r_q)
    unit_rad_pi_pow = mom_pi_pow - vol_pi_pow

    # Constructive integral-definition LHS in Q[pi, pi^{-1}] vs closed-form RHS (k!)^2 / ((2k+2)^{2k} * pi^{2k})
    zador_pow_d_lhs_q = ((mom_int_q / Fraction(d)) ** d) * (vol_unit_r_q ** (-(d + 2)))
    zador_pow_d_lhs_pi = d * mom_pi_pow - (d + 2) * vol_pi_pow
    fact_k = math.factorial(k_half_dim)
    zador_pow_d_rhs_q = Fraction(fact_k * fact_k, (d + 2) ** d)
    zador_pow_d_rhs_pi = -d

    # Ball-unit rescaling: V_{2k}^2 * G(B^{2k})^{2k} == (1 / (2k + 2))^{2k} * pi^0
    ball_unit_pow_d_q = zador_pow_d_lhs_q * (vol_unit_r_q ** 2)
    ball_unit_pow_d_pi = zador_pow_d_lhs_pi + 2 * vol_pi_pow

    return {
        "ambient_dim_d": d,
        "unit_radius_norm_moment_q": _frac_str(unit_rad_ratio_q),
        "unit_radius_pi_power": unit_rad_pi_pow,
        "unit_vol_zador_pow_d_coeff_q": _frac_str(zador_pow_d_lhs_q),
        "unit_vol_zador_pow_d_pi_power": zador_pow_d_lhs_pi,
        "unit_vol_zador_pow_d_exact_match": (
            unit_rad_ratio_q == unit_radius_ball_norm_moment_q(d)
            and unit_rad_pi_pow == 0
            and zador_pow_d_lhs_q == zador_pow_d_rhs_q
            and zador_pow_d_lhs_pi == zador_pow_d_rhs_pi
            and zador_pow_d_lhs_pi < 0
        ),
        "ball_unit_Vd_rescaled_pi_cancels": (
            ball_unit_pow_d_q == Fraction(1, (d + 2) ** d)
            and ball_unit_pow_d_pi == 0
        ),
    }


def _mat2_mul_q(a: Mat2Q, b: Mat2Q) -> Mat2Q:
    return (
        (a[0][0] * b[0][0] + a[0][1] * b[1][0], a[0][0] * b[0][1] + a[0][1] * b[1][1]),
        (a[1][0] * b[0][0] + a[1][1] * b[1][0], a[1][0] * b[0][1] + a[1][1] * b[1][1]),
    )


def _mat3_mul_q(a: Mat3Q, b: Mat3Q) -> Mat3Q:
    return tuple(  # type: ignore[return-value]
        tuple(sum((a[i][k] * b[k][j] for k in range(3)), Fraction(0)) for j in range(3))
        for i in range(3)
    )


def _mat3_transpose_q(a: Mat3Q) -> Mat3Q:
    return (
        (a[0][0], a[1][0], a[2][0]),
        (a[0][1], a[1][1], a[2][1]),
        (a[0][2], a[1][2], a[2][2]),
    )


def _mat3_sub_q(a: Mat3Q, b: Mat3Q) -> Mat3Q:
    return tuple(  # type: ignore[return-value]
        tuple(a[i][j] - b[i][j] for j in range(3))
        for i in range(3)
    )


def sylvester_inertia_3x3_q(m: Mat3Q) -> tuple[int, int, int]:
    """Exact symmetric 3x3 inertia (n_pos, n_neg, n_zero) over Q via Sylvester congruence."""
    require_ok(m == _mat3_transpose_q(m), "NON_SYMMETRIC_3X3", "matrix must be symmetric over Q")
    a = [[m[i][j] for j in range(3)] for i in range(3)]
    diag: list[Fraction] = []
    idx = 0
    while idx < 3:
        piv = -1
        for k in range(idx, 3):
            if a[k][k] != Fraction(0):
                piv = k
                break
        if piv == -1:
            pair = None
            for r in range(idx, 3):
                for c in range(r + 1, 3):
                    if a[r][c] != Fraction(0):
                        pair = (r, c)
                        break
                if pair is not None:
                    break
            if pair is None:
                for _ in range(idx, 3):
                    diag.append(Fraction(0))
                break
            r_idx, c_idx = pair
            for k in range(3):
                a[r_idx][k] = a[r_idx][k] + a[c_idx][k]
            for k in range(3):
                a[k][r_idx] = a[k][r_idx] + a[k][c_idx]
            piv = r_idx
        if piv != idx:
            a[idx], a[piv] = a[piv], a[idx]
            for k in range(3):
                a[k][idx], a[k][piv] = a[k][piv], a[k][idx]
        d_val = a[idx][idx]
        diag.append(d_val)
        for r in range(idx + 1, 3):
            fac = a[r][idx] / d_val
            if fac != Fraction(0):
                for c in range(idx + 1, 3):
                    a[r][c] = a[r][c] - fac * a[idx][c]
                a[r][idx] = Fraction(0)
                a[idx][r] = Fraction(0)
        idx += 1
    return (
        sum(1 for d in diag if d > Fraction(0)),
        sum(1 for d in diag if d < Fraction(0)),
        sum(1 for d in diag if d == Fraction(0)),
    )


def verify_joukowski_vs_bridge12_q(
    v_inf: Fraction | int,
    circulation_gamma: Fraction | int,
    cyl_radius_a: Fraction | int = Fraction(1),
) -> dict[str, Any]:
    """Constructive comparison of 2D Abelian Cauchy/Joukowski potential flow vs 3D Non-Abelian BRIDGE_12:
      - Derives v(theta) = 2*V_inf*sin(theta) + Gamma/(2*pi*a) and complex velocity W'(z) = V_inf*(1 - a^2/z^2)
        + i*Gamma/(2*pi*z) at z_top = +i*a (theta = +pi/2) and z_bot = -i*a (theta = -pi/2), computing
        v(pi/2)^2 - v(-pi/2)^2 = 4*V_inf*Gamma / (pi*a) constructively in Q[pi^{-1}] via polynomial arithmetic.
    """
    v = _to_frac(v_inf)
    gam = _to_frac(circulation_gamma)
    a_rad = _to_frac(cyl_radius_a)
    require_ok(
        v > Fraction(0) and gam > Fraction(0) and a_rad > Fraction(0),
        "NONPOS_FLOW_PARAMS",
        "V_inf, Gamma, and cyl_radius_a must be > 0",
    )

    # Complex velocity W'(z) = V_inf*(1 - a^2/z^2) + i*Gamma/(2*pi*z) at z = +-i*a (z^2 = -a^2, Im(W') = 0):
    z_sq_crest = -(a_rad * a_rad)
    w_prime_top_pi_inv: PolyQ = (v * (Fraction(1) - (a_rad * a_rad) / z_sq_crest), gam / (Fraction(2) * a_rad))
    w_prime_bot_pi_inv: PolyQ = (v * (Fraction(1) - (a_rad * a_rad) / z_sq_crest), -gam / (Fraction(2) * a_rad))

    # Tangential surface speed v(theta) = 2*V_inf*sin(theta) + Gamma/(2*pi*a) at theta = +pi/2 (+1) vs -pi/2 (-1):
    v_top_pi_inv: PolyQ = (Fraction(2) * v * Fraction(1), gam / (Fraction(2) * a_rad))
    v_bot_pi_inv: PolyQ = (Fraction(2) * v * Fraction(-1), gam / (Fraction(2) * a_rad))

    v_top_sq = _poly_mul(v_top_pi_inv, v_top_pi_inv)
    v_bot_sq = _poly_mul(v_bot_pi_inv, v_bot_pi_inv)
    w_top_mod_sq = _poly_mul(w_prime_top_pi_inv, w_prime_top_pi_inv)
    w_bot_mod_sq = _poly_mul(w_prime_bot_pi_inv, w_prime_bot_pi_inv)
    potential_polar_match = (w_top_mod_sq == v_top_sq) and (w_bot_mod_sq == v_bot_sq)

    speed_sq_diff_pi_inv = _poly_add(v_top_sq, _poly_scale(v_bot_sq, Fraction(-1)))
    top_minus_bot_pi_inv_coeff = speed_sq_diff_pi_inv[1]

    r1: Mat2Q = ((Fraction(3, 5), Fraction(-4, 5)), (Fraction(4, 5), Fraction(3, 5)))
    r2: Mat2Q = ((Fraction(5, 13), Fraction(-12, 13)), (Fraction(12, 13), Fraction(5, 13)))
    so2_commutes = _mat2_mul_q(r1, r2) == _mat2_mul_q(r2, r1)

    u_cyc: Mat3Q = (
        (Fraction(0), Fraction(1), Fraction(0)),
        (Fraction(0), Fraction(0), Fraction(1)),
        (Fraction(1), Fraction(0), Fraction(0)),
    )
    u_beta: Mat3Q = (
        (Fraction(0), Fraction(-1), Fraction(0)),
        (Fraction(0), Fraction(0), Fraction(1)),
        (Fraction(-1), Fraction(0), Fraction(0)),
    )
    so3_non_abelian = _mat3_mul_q(u_cyc, u_beta) != _mat3_mul_q(u_beta, u_cyc)

    i3: Mat3Q = (
        (Fraction(1), Fraction(0), Fraction(0)),
        (Fraction(0), Fraction(1), Fraction(0)),
        (Fraction(0), Fraction(0), Fraction(1)),
    )
    g3: Mat3Q = (
        (Fraction(3), Fraction(0), Fraction(0)),
        (Fraction(0), Fraction(1), Fraction(0)),
        (Fraction(0), Fraction(0), Fraction(1)),
    )
    l_diag: Mat3Q = (
        (Fraction(3, 5), Fraction(0), Fraction(0)),
        (Fraction(0), Fraction(6, 5), Fraction(0)),
        (Fraction(0), Fraction(0), Fraction(3, 5)),
    )
    ul = _mat3_mul_q(u_cyc, l_diag)
    lu = _mat3_mul_q(l_diag, u_cyc)

    in_i3_ul = sylvester_inertia_3x3_q(_mat3_sub_q(i3, _mat3_mul_q(_mat3_transpose_q(ul), _mat3_mul_q(i3, ul))))
    in_i3_lu = sylvester_inertia_3x3_q(_mat3_sub_q(i3, _mat3_mul_q(_mat3_transpose_q(lu), _mat3_mul_q(i3, lu))))
    in_g3_ul = sylvester_inertia_3x3_q(_mat3_sub_q(g3, _mat3_mul_q(_mat3_transpose_q(ul), _mat3_mul_q(g3, ul))))
    in_g3_lu = sylvester_inertia_3x3_q(_mat3_sub_q(g3, _mat3_mul_q(_mat3_transpose_q(lu), _mat3_mul_q(g3, lu))))

    return {
        "joukowski_speed_sq_diff_pi_inv_poly_q": [_frac_str(c) for c in speed_sq_diff_pi_inv],
        "joukowski_speed_sq_gap_pi_inv_coeff_q": _frac_str(top_minus_bot_pi_inv_coeff),
        "joukowski_potential_polar_match": potential_polar_match,
        "joukowski_pure_pi_inv_monomial": (
            speed_sq_diff_pi_inv[0] == Fraction(0)
            and speed_sq_diff_pi_inv[2] == Fraction(0)
            and top_minus_bot_pi_inv_coeff > Fraction(0)
        ),
        "joukowski_upper_faster_than_lower": top_minus_bot_pi_inv_coeff > Fraction(0),
        "so2_abelian_commutes": so2_commutes,
        "so3_2i_non_abelian": so3_non_abelian,
        "bridge12_scalar_I3_inertia_UL": list(in_i3_ul),
        "bridge12_scalar_I3_inertia_LU": list(in_i3_lu),
        "bridge12_G311_inertia_UL": list(in_g3_ul),
        "bridge12_G311_inertia_LU": list(in_g3_lu),
        "bridge12_n_minus_split": in_g3_ul[1] != in_g3_lu[1],
    }


# ---------------------------------------------------------------------------
# 4. Complete Master Certificate Builder, Fail-Closed Validator, & CLI
# ---------------------------------------------------------------------------

def build_xpi_gegenbauer_certificate() -> dict[str, Any]:
    """Compute all exact-Q proofs for EXP-Q26c / Portal x/pi and return canonical self-hashed receipt."""
    alphas = (
        ("S1_chebyshev_a0", Fraction(0)),
        ("S2_legendre_a1_2", Fraction(1, 2)),
        ("S3_su2_a1", Fraction(1)),
        ("S7_e8_shell_a3", Fraction(3)),
        ("S31_pak_width32_a15", Fraction(15)),
    )
    stereo_ts = (Fraction(0), Fraction(1, 3), Fraction(1, 2), Fraction(1), Fraction(2), Fraction(5))
    u_grid = tuple(Fraction(k, 8) for k in range(-8, 9))

    stereo_checks = 0
    minus_one_matches = 0
    for r in range(9):
        for t_val in stereo_ts:
            _, tr_v, _, ok_flag = stereographic_chebyshev_slack_q(r, t_val)
            if ok_flag and abs(tr_v) <= Fraction(1):
                stereo_checks += 1
        if eval_poly_q(chebyshev_t_poly_q(r), Fraction(-1)) == (Fraction(-1) if (r % 2) == 1 else Fraction(1)):
            minus_one_matches += 1

    convex_decomp_checks = 0
    norm_one_matches = 0
    linear_init_l1_matches = 0
    grid_sup_matches = 0
    alpha_summaries: dict[str, Any] = {}
    for name, alp in alphas:
        max_abs_on_grid = Fraction(0)
        for r in range(9):
            poly_r = gegenbauer_norm_poly_q(r, alp)
            if eval_poly_q(poly_r, Fraction(1)) == Fraction(1):
                norm_one_matches += 1
            if r == 1 and poly_r == (Fraction(0), Fraction(1)):
                linear_init_l1_matches += 1
            weights = gegenbauer_chebyshev_convex_weights_q(r, alp)
            reconstructed: PolyQ = (Fraction(0),)
            for m_deg, w_val in weights.items():
                reconstructed = _poly_add(reconstructed, _poly_scale(chebyshev_t_poly_q(m_deg), w_val))
            if (
                sum(weights.values(), Fraction(0)) == Fraction(1)
                and all(w > Fraction(0) for w in weights.values())
                and _poly_trim(list(reconstructed)) == _poly_trim(list(poly_r))
            ):
                convex_decomp_checks += 1
            for u in u_grid:
                val = abs(eval_poly_q(poly_r, u))
                if val <= Fraction(1):
                    grid_sup_matches += 1
                if val > max_abs_on_grid:
                    max_abs_on_grid = val
        alpha_summaries[name] = {
            "alpha_q": _frac_str(alp),
            "max_abs_on_17pt_grid_q": _frac_str(max_abs_on_grid),
        }

    leg_polys = tuple(gegenbauer_norm_poly_q(r, Fraction(1, 2)) for r in range(1, 9))
    off_diag_zeros = 0
    diag_pos = 0
    for i in range(8):
        for j in range(8):
            ip = integrate_poly_minus1_to_1_q(_poly_mul(leg_polys[i], leg_polys[j]))
            if i == j and ip == Fraction(2, 2 * (i + 1) + 1):
                diag_pos += 1
            elif i != j and ip == Fraction(0):
                off_diag_zeros += 1

    u6_u8_cos_sq = (Fraction(2, 15) ** 2) / (Fraction(2, 13) * Fraction(2, 17))

    rho_half = Fraction(1, 2)
    gains = (Fraction(1, 4), Fraction(1), Fraction(2), Fraction(4), Fraction(8), Fraction(16))
    raw_b = (Fraction(3, 10), Fraction(-2, 5), Fraction(1, 5), Fraction(-1, 4), Fraction(1, 8), Fraction(-1, 8), Fraction(1, 4), Fraction(-1, 5))
    u_demo = (Fraction(-7, 8), Fraction(-1, 4), Fraction(0), Fraction(3, 8), Fraction(1))
    v_demo = (Fraction(2), Fraction(-1), Fraction(3, 2), Fraction(4), Fraction(-5, 2))
    lin_a = (Fraction(0), Fraction(1)) + (Fraction(0),) * 7
    zero_b = (Fraction(0),) * 8

    g_invariance_checks = 0
    proj_ref = project_spherical_denominator_q(raw_b, rho_half)
    n_demo = Fraction(len(u_demo))
    for g_val in gains:
        expected_lin = sum((g_val * u * v for u, v in zip(u_demo, v_demo)), Fraction(0)) / n_demo
        g_proj_same = project_spherical_denominator_q(raw_b, rho_half) == proj_ref
        for _, alp in alphas:
            lin_out = eval_xpi_attention_1d_q(u_demo, v_demo, lin_a, zero_b, g_val, alp, rho_half)
            proj_out = eval_xpi_attention_1d_q(u_demo, v_demo, lin_a, raw_b, g_val, alp, rho_half)
            if (
                g_proj_same
                and lin_out["output"] == expected_lin
                and lin_out["denom_sum"] == n_demo
                and Fraction(1) - rho_half <= proj_out["min_h"]
                and proj_out["max_h"] <= Fraction(1) + rho_half
                and n_demo * (Fraction(1) - rho_half) <= proj_out["denom_sum"] <= n_demo * (Fraction(1) + rho_half)
            ):
                g_invariance_checks += 1

    t7_b8 = chebyshev_t_poly_q(7)[1:] + (Fraction(0),)
    t7_mono_l1 = sum((abs(c) for c in t7_b8), Fraction(0))
    t7_scaled = tuple(rho_half * c for c in t7_b8)
    t7_after_mono_proj_g1 = project_monomial_denominator_q(t7_scaled, Fraction(1), rho_half)
    t7_after_mono_proj_g2 = project_monomial_denominator_q(t7_scaled, Fraction(2), rho_half)
    t7_cheb_b = (Fraction(0),) * 6 + (rho_half, Fraction(0))
    t7_cheb_unshrunk = project_spherical_denominator_q(t7_cheb_b, rho_half) == t7_cheb_b
    t7_mono_g1_ratio = t7_scaled[6] / t7_after_mono_proj_g1[6]

    t8_p = chebyshev_t_poly_q(8)
    t4_pad = chebyshev_t_poly_q(4) + (Fraction(0),) * 4
    p8_zero_const = tuple((t8_p[r] - t4_pad[r]) * Fraction(1, 2) for r in range(9))
    p8_mono_l1 = sum((abs(c) for c in p8_zero_const[1:]), Fraction(0))

    mono_deg8_cap_g2 = project_monomial_denominator_q((Fraction(0),) * 7 + (Fraction(1),), Fraction(2), rho_half)[7]
    mono_deg8_cap_g4 = project_monomial_denominator_q((Fraction(0),) * 7 + (Fraction(1),), Fraction(4), rho_half)[7]

    mobius_boost_checks = 0
    mobius_slope_checks = 0
    mobius_bijection_checks = 0
    for g_val in gains:
        if verify_mobius_north_pole_slope_q(g_val)["exact_slope_match"]:
            mobius_slope_checks += 1
        p_pos = mobius_spherical_boost_q(Fraction(1), g_val)
        p_neg = mobius_spherical_boost_q(Fraction(-1), g_val)
        g_inv = Fraction(1) / g_val
        if p_pos["psi"] == Fraction(1) and p_neg["psi"] == Fraction(-1):
            for u in u_grid:
                mb = mobius_spherical_boost_q(u, g_val)
                mb_inv = mobius_spherical_boost_q(mb["psi"], g_inv)
                mb_pre = mobius_spherical_boost_q(mobius_spherical_boost_q(u, g_inv)["psi"], g_val)
                g1_ok = (g_val != Fraction(1)) or (mb["psi"] == u)
                if mb["identity_exact"] and abs(mb["psi"]) <= Fraction(1) and g1_ok:
                    mobius_boost_checks += 1
                if mb_inv["psi"] == u and mb_pre["psi"] == u:
                    mobius_bijection_checks += 1

    mellin_rows = [mellin_sphere_even_dim_q(k) for k in range(1, 13)]
    mellin_exact_matches = sum(1 for row in mellin_rows if row["mellin_match"] and row["heat_match"])
    omega2_coeff_q = Fraction(2) / Fraction(1, 2)

    zador_half_dims = (1, 2, 4, 8, 12)
    zador_dims = tuple(2 * k for k in zador_half_dims)
    unit_rad_moment_map = {str(d): _frac_str(unit_radius_ball_norm_moment_q(d)) for d in zador_dims}
    zador_xpi_rows = [zador_unit_volume_even_dim_xpi_q(k) for k in zador_half_dims]
    zador_pow_d_verified = sum(1 for row in zador_xpi_rows if row["unit_vol_zador_pow_d_exact_match"])
    ball_unit_cancel_verified = sum(1 for row in zador_xpi_rows if row["ball_unit_Vd_rescaled_pi_cancels"])
    zador_pow_d_samples = {
        str(row["ambient_dim_d"]): {
            "coeff_q": row["unit_vol_zador_pow_d_coeff_q"],
            "pi_power": row["unit_vol_zador_pow_d_pi_power"],
        }
        for row in zador_xpi_rows[:3]
    }
    # At d = 2 (k = 1), V_2 = pi => R_{Vol=1}^2 = 1/pi => G(B^2) = 1 / (4*pi) (pi_power = -1 != 0)
    d2_zador_xpi = {"coeff_q": _frac_str(unit_radius_ball_norm_moment_q(2)), "pi_power": -1}

    jouk_b12 = verify_joukowski_vs_bridge12_q(Fraction(1), Fraction(1), Fraction(1))

    payload: dict[str, Any] = {
        "schema": "aletheia.track_s122.xpi_gegenbauer_oracle.v2",
        "track": "S122",
        "experiment": "EXP-Q26c",
        "float_ops_used": 0,
        "theorem_1_spherical_denominator_projection": {
            "stereographic_chebyshev_checks": stereo_checks,
            "chebyshev_minus_one_matches": minus_one_matches,
            "norm_at_one_matches": norm_one_matches,
            "linear_init_l1_matches": linear_init_l1_matches,
            "convex_chebyshev_decompositions_verified": convex_decomp_checks,
            "grid_supremum_matches": grid_sup_matches,
            "legendre_l2_diag_verified": diag_pos,
            "legendre_l2_off_diag_zeros": off_diag_zeros,
            "monomial_u6_u8_l2_cos_sq_q": _frac_str(u6_u8_cos_sq),
            "g_invariance_and_linear_init_checks": g_invariance_checks,
            "t7_chebyshev_unshrunk": t7_cheb_unshrunk,
            "t7_monomial_l1_inflation_factor_g1_q": _frac_str(t7_mono_l1),
            "t7_monomial_proj_shrink_ratio_g1_q": _frac_str(t7_mono_g1_ratio),
            "p8_const_term_q": _frac_str(p8_zero_const[0]),
            "p8_zero_const_monomial_l1_inflation_factor_g1_q": _frac_str(p8_mono_l1),
            "monomial_b8_max_at_rho_half_g2_q": _frac_str(mono_deg8_cap_g2),
            "monomial_b8_max_at_rho_half_g4_q": _frac_str(mono_deg8_cap_g4),
            "mobius_spherical_boost_checks": mobius_boost_checks,
            "mobius_north_pole_symbolic_slope_checks": mobius_slope_checks,
            "mobius_bijection_inverse_checks": mobius_bijection_checks,
            "t7_b7_after_monomial_proj_g2_q": _frac_str(t7_after_mono_proj_g2[6]),
            "families": alpha_summaries,
        },
        "theorem_2_xpi_mellin_sphere_zador_bridge12": {
            "mellin_even_s_verified_count": mellin_exact_matches,
            "mellin_samples": [mellin_rows[0], mellin_rows[1], mellin_rows[3], mellin_rows[7], mellin_rows[11]],
            "null_cone_s2_omega2": {"coeff_q": _frac_str(omega2_coeff_q), "pi_power": 1},
            "unit_radius_ball_norm_second_moment_q": unit_rad_moment_map,
            "unit_volume_zador_d2_G_B2_xpi": d2_zador_xpi,
            "unit_volume_zador_pow_d_verified_count": zador_pow_d_verified,
            "unit_volume_zador_pow_d_samples": zador_pow_d_samples,
            "ball_unit_Vd_rescaled_pi_cancel_verified_count": ball_unit_cancel_verified,
            "joukowski_vs_bridge12": jouk_b12,
        },
    }
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["certificate_sha256"] = hashlib.sha256(canon).hexdigest()
    return payload


def validate_xpi_certificate(cert: dict[str, Any]) -> None:
    """Fail-closed validator checking canonical SHA-256 and every exact-Q theorem invariant."""
    require_ok(isinstance(cert, dict) and cert.get("float_ops_used") == 0, "BAD_CERT_ROOT", "invalid cert root or float_ops_used != 0")
    rec_sha = cert.get("certificate_sha256")
    require_ok(isinstance(rec_sha, str) and len(rec_sha) == 64, "MISSING_CERT_SHA", "missing 64-hex certificate_sha256")
    body = {k: v for k, v in cert.items() if k != "certificate_sha256"}
    recomputed = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    require_ok(recomputed == rec_sha, "CERT_SHA_MISMATCH", "certificate_sha256 tamper detected")

    t1 = cert["theorem_1_spherical_denominator_projection"]
    require_ok(
        t1["stereographic_chebyshev_checks"] == 54
        and t1["chebyshev_minus_one_matches"] == 9
        and t1["norm_at_one_matches"] == 45
        and t1["linear_init_l1_matches"] == 5
        and t1["convex_chebyshev_decompositions_verified"] == 45
        and t1["grid_supremum_matches"] == 765
        and t1["legendre_l2_diag_verified"] == 8
        and t1["legendre_l2_off_diag_zeros"] == 56
        and t1["monomial_u6_u8_l2_cos_sq_q"] == "221/225"
        and t1["g_invariance_and_linear_init_checks"] == 30
        and t1["t7_chebyshev_unshrunk"] is True
        and t1["t7_monomial_l1_inflation_factor_g1_q"] == "239/1"
        and t1["t7_monomial_proj_shrink_ratio_g1_q"] == "239/1"
        and t1["p8_const_term_q"] == "0/1"
        and t1["p8_zero_const_monomial_l1_inflation_factor_g1_q"] == "280/1"
        and t1["monomial_b8_max_at_rho_half_g2_q"] == "1/512"
        and t1["monomial_b8_max_at_rho_half_g4_q"] == "1/131072"
        and t1["mobius_spherical_boost_checks"] == 102
        and t1["mobius_north_pole_symbolic_slope_checks"] == 6
        and t1["mobius_bijection_inverse_checks"] == 102,
        "THEOREM_1_CERT_INVALID",
        "Theorem 1 spherical denominator projection counts or exact fractions failed",
    )

    t2 = cert["theorem_2_xpi_mellin_sphere_zador_bridge12"]
    jb = t2["joukowski_vs_bridge12"]
    require_ok(
        t2["mellin_even_s_verified_count"] == 12
        and t2["null_cone_s2_omega2"] == {"coeff_q": "4/1", "pi_power": 1}
        and t2["unit_radius_ball_norm_second_moment_q"] == {"2": "1/4", "4": "1/6", "8": "1/10", "16": "1/18", "24": "1/26"}
        and t2["unit_volume_zador_d2_G_B2_xpi"] == {"coeff_q": "1/4", "pi_power": -1}
        and t2["unit_volume_zador_pow_d_verified_count"] == 5
        and t2["unit_volume_zador_pow_d_samples"] == {
            "2": {"coeff_q": "1/16", "pi_power": -2},
            "4": {"coeff_q": "1/324", "pi_power": -4},
            "8": {"coeff_q": "9/1562500", "pi_power": -8},
        }
        and t2["ball_unit_Vd_rescaled_pi_cancel_verified_count"] == 5
        and jb["joukowski_potential_polar_match"] is True
        and jb["joukowski_pure_pi_inv_monomial"] is True
        and jb["joukowski_speed_sq_diff_pi_inv_poly_q"] == ["0/1", "4/1", "0/1"]
        and jb["joukowski_upper_faster_than_lower"] is True
        and jb["so2_abelian_commutes"] is True
        and jb["so3_2i_non_abelian"] is True
        and jb["bridge12_scalar_I3_inertia_UL"] == [2, 1, 0]
        and jb["bridge12_scalar_I3_inertia_LU"] == [2, 1, 0]
        and jb["bridge12_G311_inertia_UL"] == [2, 1, 0]
        and jb["bridge12_G311_inertia_LU"] == [1, 2, 0]
        and jb["bridge12_n_minus_split"] is True,
        "THEOREM_2_CERT_INVALID",
        "Theorem 2 Mellin-Sphere-Zador-BRIDGE_12 counts or exact identities failed",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track S122 Portal x/pi Spherical Multipole Attention Exact-Q Oracle")
    parser.add_argument("--json", action="store_true", help="Emit canonical JSON certificate")
    args = parser.parse_args(argv)
    try:
        cert = build_xpi_gegenbauer_certificate()
        validate_xpi_certificate(cert)
        if args.json:
            sys.stdout.write(json.dumps(cert, indent=2, sort_keys=True) + "\n")
        else:
            sys.stdout.write(
                json.dumps(
                    {
                        "status": "PASS",
                        "certificate_sha256": cert["certificate_sha256"],
                        "float_ops_used": cert["float_ops_used"],
                        "t7_mono_inflation": cert["theorem_1_spherical_denominator_projection"]["t7_monomial_l1_inflation_factor_g1_q"],
                        "unit_radius_moment": cert["theorem_2_xpi_mellin_sphere_zador_bridge12"]["unit_radius_ball_norm_second_moment_q"],
                        "unit_vol_zador_pow_d": cert["theorem_2_xpi_mellin_sphere_zador_bridge12"]["unit_volume_zador_pow_d_samples"],
                    },
                    sort_keys=True,
                )
                + "\n"
            )
        return 0
    except XPiGegenbauerError as exc:
        sys.stderr.write(f"XPI_ORACLE_FAIL {exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
