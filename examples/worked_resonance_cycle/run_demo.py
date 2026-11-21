#!/usr/bin/env python3
"""
The Aletheia Method — Worked Resonance Cycle (Live 3-Second Exact Demo).

Replays the Cave Expedition Chain 1 progression (AUDIT-001 -> AUDIT-002 -> AUDIT-014)
end-to-end in 100% pure Python 3 standard library with ZERO IEEE-754 floats and
ZERO bare `assert` statements (R1-R5 compliant; bit-identical under -I -B,
-I -O -B, -I -B -W error, and -I -O -B -W error):

  Stage 1 — Pass-1 Buggy Prototype (AUDIT-001 FALSIFIED):
      Omitting P = H - Q >= 0 forges rank(P) >= 117 on a 2x2 matrix.
  Stage 2 — Steelman Projection (AUDIT-002 VERIFIED N2):
      Exact W (+) W^perp block slack identity & guarded scale-invariant R_opt(u, t, S, b).
  Stage 3 — Active Observer Tomography & Sharpness Wall (G_obs, AUDIT-002):
      Zero-shared-code Faddeev-LeVerrier + Cayley-Hamilton + Descartes exact inertia
      oracle over Q(i) on a dense, strictly complex, non-commuting indefinite 4x4
      matrix H = P + Q (rank(P) = 2, n_+(H_perp) = 2, b = 1), PLUS an exact rational
      rank-1 decoy proving the 2nd-moment wall min rank(P) = max(1, ceil(R_opt)) = 1.
  Stage 4 — Resonance Breakthrough (AUDIT-014 VERIFIED N2):
      4th-moment Stieltjes-Hankel bound R_H4 breaks straight through the quadratic wall
      on the exact same non-commuting indefinite matrix (certifying rank(P) >= 2)
      while correctly respecting the rank-1 decoy (returning exact 1).
  Stage 5 — R5 Must-Fail Controls & Live Refusal-Site Mutation Suite (Gate 7):
      7 negative controls blocked + 3 live guard-deletion mutants caught & killed.

Run:
  python3 -I -O -B -W error examples/worked_resonance_cycle/run_demo.py
  python3 -I -O -B -W error examples/worked_resonance_cycle/run_demo.py --json
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import sys
from typing import Any, Sequence


# ==============================================================================
# STRICT R1/R3/R4 GATE INFRASTRUCTURE (ZERO FLOATS, ZERO BARE ASSERTS)
# ==============================================================================
class CertError(ValueError):
    """Structured default-reject verification failure (never stripped by -O)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


def require(cond: bool, code: str, message: str) -> None:
    """Explicit non-assert guard safe under python3 -O."""
    if not cond:
        raise CertError(code, message)


def parse_exact_fraction(val: Any) -> Fraction:
    """R3 strict rational guard: accept ONLY int (excluding bool!) or Fraction."""
    if isinstance(val, bool) or not isinstance(val, (int, Fraction)):
        raise CertError(
            "INVALID_TYPE",
            f"expected exact int or Fraction (not bool/float), got {type(val).__name__}: {val!r}",
        )
    return val if isinstance(val, Fraction) else Fraction(val)


def parse_exact_int(val: Any, min_value: int | None = None) -> int:
    """R3 strict integer guard: reject bool, float, Fraction, str."""
    if isinstance(val, bool) or not isinstance(val, int):
        raise CertError(
            "INVALID_TYPE",
            f"expected exact int (not bool/float), got {type(val).__name__}: {val!r}",
        )
    if min_value is not None and val < min_value:
        raise CertError("INVALID_B", f"expected int >= {min_value}, got {val}")
    return val


def frac_str(q: Fraction) -> str:
    """Canonical lowest-terms rational string."""
    q = parse_exact_fraction(q)
    return str(q.numerator) if q.denominator == 1 else f"{q.numerator}/{q.denominator}"


def frac_decimal_str(q: Fraction, digits: int = 6) -> str:
    """Exact integer-arithmetic decimal formatting (zero IEEE floats!)."""
    q = parse_exact_fraction(q)
    neg = q < 0
    a = -q if neg else q
    scale = 10 ** digits
    # Round half-up purely in integer arithmetic
    scaled = (2 * a.numerator * scale + a.denominator) // (2 * a.denominator)
    whole, frac = divmod(scaled, scale)
    sign = "-" if neg and scaled > 0 else ""
    return f"{sign}{whole}.{frac:0{digits}d}"


def ceil_fraction(q: Fraction) -> int:
    """Exact integer ceiling of a Fraction without floats."""
    q = parse_exact_fraction(q)
    num, den = q.numerator, q.denominator
    return -((-num) // den)


# ==============================================================================
# PRIMARY EXACT GAUSSIAN RATIONAL LINEAR ALGEBRA Q(i)
# ==============================================================================
@dataclass(frozen=True)
class Qi:
    """Exact Gaussian rational a + b*i with a, b in Q."""

    re: Fraction
    im: Fraction = Fraction(0)

    def __post_init__(self) -> None:
        if (
            isinstance(self.re, bool)
            or isinstance(self.im, bool)
            or not isinstance(self.re, Fraction)
            or not isinstance(self.im, Fraction)
        ):
            raise CertError("INVALID_TYPE", f"Qi requires Fraction parts, got ({self.re!r}, {self.im!r})")

    @staticmethod
    def of(re: int | Fraction, im: int | Fraction = 0) -> Qi:
        return Qi(parse_exact_fraction(re), parse_exact_fraction(im))

    def __add__(self, o: Qi) -> Qi:
        return Qi(self.re + o.re, self.im + o.im)

    def __sub__(self, o: Qi) -> Qi:
        return Qi(self.re - o.re, self.im - o.im)

    def __neg__(self) -> Qi:
        return Qi(-self.re, -self.im)

    def __mul__(self, o: Qi) -> Qi:
        return Qi(self.re * o.re - self.im * o.im, self.re * o.im + self.im * o.re)

    def conj(self) -> Qi:
        return Qi(self.re, -self.im)

    def norm_sq(self) -> Fraction:
        return self.re * self.re + self.im * self.im

    def __truediv__(self, o: Qi) -> Qi:
        d = o.norm_sq()
        require(d != 0, "DIV_BY_ZERO", "division by zero in Q(i)")
        num = self * o.conj()
        return Qi(num.re / d, num.im / d)

    def is_zero(self) -> bool:
        return self.re == 0 and self.im == 0


Q0 = Qi(Fraction(0))
Q1 = Qi(Fraction(1))
CMat = list[list[Qi]]


def czeros(n: int, m: int) -> CMat:
    return [[Q0 for _ in range(m)] for _ in range(n)]


def ceye(n: int) -> CMat:
    return [[Q1 if i == j else Q0 for j in range(n)] for i in range(n)]


def cdiag(vals: Sequence[int | Fraction]) -> CMat:
    n = len(vals)
    M = czeros(n, n)
    for i, v in enumerate(vals):
        M[i][i] = Qi.of(v)
    return M


def validate_cmat_square(A: Any, label: str = "matrix") -> int:
    require(isinstance(A, list) and len(A) > 0, "INVALID_MATRIX", f"{label} must be non-empty list")
    n = len(A)
    for i, row in enumerate(A):
        require(isinstance(row, list) and len(row) == n, "DIM_MISMATCH", f"{label} row {i} not length {n}")
        for j, entry in enumerate(row):
            require(isinstance(entry, Qi), "INVALID_TYPE", f"{label}[{i}][{j}] must be Qi")
    return n


def is_hermitian(A: CMat) -> bool:
    if not isinstance(A, list) or len(A) == 0:
        return False
    n = len(A)
    for row in A:
        if not isinstance(row, list) or len(row) != n:
            return False
        for entry in row:
            if not isinstance(entry, Qi):
                return False
    for i in range(n):
        if A[i][i].im != 0:
            return False
        for j in range(i + 1, n):
            if A[i][j] != A[j][i].conj():
                return False
    return True


def cadd(A: CMat, B: CMat) -> CMat:
    return [[a + b for a, b in zip(rA, rB)] for rA, rB in zip(A, B)]


def csub(A: CMat, B: CMat) -> CMat:
    return [[a - b for a, b in zip(rA, rB)] for rA, rB in zip(A, B)]


def cscale(s: Fraction, A: CMat) -> CMat:
    sq = Qi(s)
    return [[sq * v for v in row] for row in A]


def cdagger(A: CMat) -> CMat:
    return [[A[i][j].conj() for i in range(len(A))] for j in range(len(A[0]))]


def cmul(A: CMat, B: CMat) -> CMat:
    n, k, m = len(A), len(B), len(B[0])
    require(len(A[0]) == k, "DIM_MISMATCH", "cmul inner dimension mismatch")
    out = czeros(n, m)
    for i in range(n):
        for j in range(m):
            acc = Q0
            for t in range(k):
                acc = acc + A[i][t] * B[t][j]
            out[i][j] = acc
    return out


def ctrace_real(A: CMat) -> Fraction:
    acc = Q0
    for i in range(len(A)):
        acc = acc + A[i][i]
    require(acc.im == 0, "NONREAL_TRACE", "trace of Hermitian matrix must be real")
    return acc.re


def cfrob_sq(A: CMat) -> Fraction:
    return sum((v.norm_sq() for row in A for v in row), Fraction(0))


def crank(A: CMat) -> int:
    """Exact matrix rank over Q(i) via Gaussian elimination."""
    n, m = len(A), len(A[0])
    M = [row[:] for row in A]
    r = 0
    for col in range(m):
        piv = None
        for i in range(r, n):
            if not M[i][col].is_zero():
                piv = i
                break
        if piv is None:
            continue
        M[r], M[piv] = M[piv], M[r]
        pv = M[r][col]
        for i in range(r + 1, n):
            if not M[i][col].is_zero():
                fac = M[i][col] / pv
                for j in range(col, m):
                    M[i][j] = M[i][j] - fac * M[r][j]
        r += 1
    return r


def is_psd_hermitian(A: CMat) -> bool:
    """Exact PSD check for Hermitian A over Q(i) via Schur-complement diagonal elimination."""
    if not is_hermitian(A):
        return False
    n = len(A)
    M = [row[:] for row in A]
    for k in range(n):
        dk = M[k][k]
        if dk.im != 0 or dk.re < 0:
            return False
        if dk.re == 0:
            for j in range(k + 1, n):
                if not M[k][j].is_zero() or not M[j][k].is_zero():
                    return False
            continue
        for i in range(k + 1, n):
            if not M[i][k].is_zero():
                fac = M[i][k] / dk
                for j in range(k + 1, n):
                    M[i][j] = M[i][j] - fac * M[k][j]
    return True


def spectral_moments(H: CMat, max_k: int = 4) -> dict[int, Fraction]:
    """Exact rational spectral moments S_k = tr(H^k) for k = 1..max_k."""
    require(is_hermitian(H), "MATRIX_NOT_HERMITIAN", "H must be Hermitian")
    moments: dict[int, Fraction] = {}
    Hk = H
    moments[1] = ctrace_real(Hk)
    for k in range(2, max_k + 1):
        Hk = cmul(Hk, H)
        moments[k] = ctrace_real(Hk)
    return moments


# ==============================================================================
# ZERO-SHARED-CODE OBSERVER TOMOGRAPHY ORACLE (FADDEEV-LEVERRIER + DESCARTES)
# Uses ONLY raw (Fraction, Fraction) tuples — ZERO shared functions with Qi/CMat!
# ==============================================================================
RawCMat = list[list[tuple[Fraction, Fraction]]]


def to_raw_cmat(A: CMat) -> RawCMat:
    """Serialize CMat across the oracle boundary into raw (Fraction, Fraction) tuples."""
    return [[(v.re, v.im) for v in row] for row in A]


def independent_hermitian_inertia_oracle(M: RawCMat) -> dict[str, Any]:
    """
    Zero-shared-code exact Hermitian inertia oracle (G_obs):
      1. Validates Hermitianity directly on raw (re, im) tuples.
      2. Computes characteristic polynomial p(x) = det(xI - M) in Q[x] via
         Faddeev-LeVerrier recursion: B_1 = M, c_1 = -tr(B_1),
         B_k = M (B_{k-1} + c_{k-1} I), c_k = -tr(B_k) / k.
      3. Self-checks the exact Cayley-Hamilton identity B_n + c_n I == 0!
      4. Counts exact (n_pos, n_neg, n_zero) via Descartes' rule of signs
         (exact, not merely an upper bound, because Hermitian => all roots real).
    """
    if not isinstance(M, list) or len(M) == 0:
        raise CertError("ORACLE_INVALID_MATRIX", "empty matrix passed to independent oracle")
    n = len(M)
    for i, row in enumerate(M):
        if not isinstance(row, list) or len(row) != n:
            raise CertError("ORACLE_DIM_MISMATCH", f"non-square row {i}")
        for j, entry in enumerate(row):
            if (
                not isinstance(entry, tuple)
                or len(entry) != 2
                or isinstance(entry[0], bool)
                or isinstance(entry[1], bool)
                or not isinstance(entry[0], Fraction)
                or not isinstance(entry[1], Fraction)
            ):
                raise CertError("ORACLE_INVALID_ENTRY", f"invalid raw entry at ({i},{j})")

    for i in range(n):
        if M[i][i][1] != 0:
            raise CertError("ORACLE_NOT_HERMITIAN", f"non-real diagonal at ({i},{i})")
        for j in range(i + 1, n):
            if M[i][j][0] != M[j][i][0] or M[i][j][1] != -M[j][i][1]:
                raise CertError("ORACLE_NOT_HERMITIAN", f"Hermitian mismatch at ({i},{j})")

    def _raw_mul(X: RawCMat, Y: RawCMat) -> RawCMat:
        out: RawCMat = []
        for r in range(n):
            row_out: list[tuple[Fraction, Fraction]] = []
            for c in range(n):
                sr = Fraction(0)
                si = Fraction(0)
                for t in range(n):
                    xr, xi = X[r][t]
                    yr, yi = Y[t][c]
                    sr += xr * yr - xi * yi
                    si += xr * yi + xi * yr
                row_out.append((sr, si))
            out.append(row_out)
        return out

    def _raw_trace(X: RawCMat) -> Fraction:
        tr_r = Fraction(0)
        tr_i = Fraction(0)
        for i in range(n):
            tr_r += X[i][i][0]
            tr_i += X[i][i][1]
        if tr_i != 0:
            raise CertError("ORACLE_NONREAL_TRACE", "characteristic polynomial trace not real")
        return tr_r

    coeffs: list[Fraction] = [Fraction(1)]
    B: RawCMat = [row[:] for row in M]
    coeffs.append(-_raw_trace(B))
    for k in range(2, n + 1):
        c_prev = coeffs[-1]
        shifted: RawCMat = [
            [(B[r][c][0] + (c_prev if r == c else Fraction(0)), B[r][c][1]) for c in range(n)]
            for r in range(n)
        ]
        B = _raw_mul(M, shifted)
        coeffs.append(-_raw_trace(B) / Fraction(k))

    # Internal Cayley-Hamilton self-check: B_n + c_n I == 0 identically
    cn = coeffs[-1]
    for r in range(n):
        for c in range(n):
            rr = B[r][c][0] + (cn if r == c else Fraction(0))
            ri = B[r][c][1]
            if rr != 0 or ri != 0:
                raise CertError("ORACLE_CAYLEY_HAMILTON_FAIL", f"nonzero residue at ({r},{c})")

    # Extract exact multiplicity of 0 and Descartes sign changes
    poly = coeffs[:]
    n_zero = 0
    while len(poly) > 1 and poly[-1] == 0:
        poly.pop()
        n_zero += 1

    def _sign_changes(seq: list[Fraction]) -> int:
        nz = [x for x in seq if x != 0]
        return sum(1 for a, b in zip(nz, nz[1:]) if (a > 0) != (b > 0))

    n_pos = _sign_changes(poly)
    alt = [c if (idx % 2 == 0) else -c for idx, c in enumerate(poly)]
    n_neg = _sign_changes(alt)
    if n_pos + n_neg + n_zero != n:
        raise CertError(
            "ORACLE_DESCARTES_MISMATCH",
            f"roots ({n_pos}, {n_neg}, {n_zero}) do not sum to {n}",
        )

    return {
        "n": n,
        "inertia": [n_pos, n_neg, n_zero],
        "n_pos": n_pos,
        "n_neg": n_neg,
        "n_zero": n_zero,
        "charpoly_coeffs": [frac_str(c) for c in coeffs],
        "cayley_hamilton_zero": True,
    }


# ==============================================================================
# BOUND FORMULAS & HARDENED CERTIFIERS (STAGES 1-5)
# ==============================================================================
def buggy_pass1_lemma32(
    H: CMat,
    Q: CMat,
    b: int,
    c: Fraction = Fraction(2),
) -> Fraction:
    """
    INTENTIONALLY BUGGY Pass-1 prototype reproducing AUDIT-001 (pair_06_block_00.py):
    Omits the P = H - Q >= 0 check! Used ONLY in Stage 1 to demonstrate the Pass-1
    forgery (rank >= 117 on a 2x2 matrix) before Steelman & Hardening.
    """
    P = csub(H, Q)
    u = ctrace_real(P)
    t = ctrace_real(Q)
    S = cfrob_sq(H)
    Tc = u + c * t
    return (Tc * Tc) / S - c * c * Fraction(b)


def R_lemma32_fixed_c(
    u: Fraction, t: Fraction, S: Fraction, b: int, c: Fraction = Fraction(2)
) -> Fraction:
    """Baseline scale-optimized fixed-c Lemma 3.2 (c >= 1)."""
    u_f = parse_exact_fraction(u)
    t_f = parse_exact_fraction(t)
    S_f = parse_exact_fraction(S)
    b_i = parse_exact_int(b, min_value=0)
    c_f = parse_exact_fraction(c)
    require(c_f >= 1, "INVALID_WEIGHT_C", "Lemma 3.2 requires c >= 1")
    Tc = u_f + c_f * t_f
    if u_f <= 0 or Tc <= 0 or S_f <= 0:
        return Fraction(0)
    val = (Tc * Tc) / S_f - c_f * c_f * Fraction(b_i)
    return val if val > 0 else Fraction(0)


def R_G_fable(u: Fraction, t: Fraction, S: Fraction, b: int) -> Fraction:
    """Baseline unscaled additive envelope R_G from loom#7."""
    u_f = parse_exact_fraction(u)
    t_f = parse_exact_fraction(t)
    S_f = parse_exact_fraction(S)
    b_i = parse_exact_int(b, min_value=0)
    if b_i > 0 and t_f >= Fraction(b_i):
        raw = 2 * u_f + (t_f * t_f) / Fraction(b_i) - S_f
    else:
        raw = 2 * (u_f + t_f) - S_f - Fraction(b_i)
    return raw if raw > 0 else Fraction(0)


def R_opt_guarded(u: Fraction, t: Fraction, S: Fraction, b: int) -> Fraction:
    """
    Theorem A1 (AUDIT-002, VERIFIED N2):
    Guarded scale-invariant projected-inertia envelope on W (+) W^perp:
      n_+(Pi_{W^perp} H Pi_{W^perp}) >= R_opt(u, t, S, b).
    """
    u_f = parse_exact_fraction(u)
    t_f = parse_exact_fraction(t)
    S_f = parse_exact_fraction(S)
    b_i = parse_exact_int(b, min_value=0)
    if u_f <= 0 or (u_f + t_f) <= 0:
        return Fraction(0)
    require(S_f > 0, "INVALID_FROB_NORM", "S = ||H||_F^2 must be > 0 when u + t > 0")
    if b_i > 0 and t_f > 0 and t_f * (u_f + t_f) >= Fraction(b_i) * S_f:
        denom = S_f - (t_f * t_f) / Fraction(b_i)
        require(denom > 0, "INFEASIBLE_MOMENTS", "feasible u > 0, t > 0 requires S > t^2 / b")
        return (u_f * u_f) / denom
    val = ((u_f + t_f) * (u_f + t_f)) / S_f - Fraction(b_i)
    return val if val > 0 else Fraction(0)


def certify_matrix_ropt(
    H: CMat,
    Q: CMat,
    b: int,
    *,
    _mutate_skip_p_psd: bool = False,
    _mutate_skip_hermitian: bool = False,
) -> dict[str, Any]:
    """
    Hardened TCB certifier for R_opt (with explicit R5 mutation hooks strictly for Stage 5).
    """
    nH = validate_cmat_square(H, "H")
    nQ = validate_cmat_square(Q, "Q")
    require(nH == nQ, "DIM_MISMATCH", f"H ({nH}x{nH}) and Q ({nQ}x{nQ}) dimensions differ")
    b_i = parse_exact_int(b, min_value=0)

    if not _mutate_skip_hermitian:
        require(is_hermitian(H), "MATRIX_NOT_HERMITIAN", "H must be Hermitian")
        require(is_hermitian(Q), "MATRIX_NOT_HERMITIAN", "Q must be Hermitian")

    P = csub(H, Q)
    if not _mutate_skip_p_psd:
        require(is_psd_hermitian(P), "P_NOT_PSD", "P = H - Q must be positive semidefinite")

    if not _mutate_skip_hermitian:
        q_oracle = independent_hermitian_inertia_oracle(to_raw_cmat(Q))
        require(
            q_oracle["n_pos"] <= b_i,
            "Q_INERTIA_EXCEEDS_B",
            f"n_+(Q) = {q_oracle['n_pos']} exceeds claimed b = {b_i}",
        )

    u = ctrace_real(P)
    t = ctrace_real(Q)
    S = cfrob_sq(H)
    if _mutate_skip_p_psd:
        # Expose what fixed-c=2 does when P >= 0 guard is deleted (AUDIT-001)
        Tc = u + Fraction(2) * t
        bound = (Tc * Tc) / S - Fraction(4 * b_i) if S > 0 else Fraction(0)
    else:
        bound = R_opt_guarded(u, t, S, b_i)

    return {
        "u": u,
        "t": t,
        "S": S,
        "b": b_i,
        "bound": bound,
        "min_rank_cert": max(1, ceil_fraction(bound)) if u > 0 else 0,
    }


def certify_stieltjes_hankel_deg4(
    moments: dict[int, Fraction],
    b: int,
    a_coeffs: Sequence[Any],
    *,
    _mutate_skip_nonneg_hankel: bool = False,
) -> dict[str, Any]:
    """
    Theorem A2 (AUDIT-014, VERIFIED N2) exact degree-4 Stieltjes-Hankel TCB certifier:
      Given a = (s, p) with s >= 0, p >= 0:
        q_{s,p}(lam) = 1 - s*lam + p*lam^2,
        phi_{s,p}(lam) = 1 - q_{s,p}(lam)^2 <= 1_{(0, +inf)}(lam) on ALL of R!
      Hence rank(P) >= n_+(H_perp) >= n_+(H) - b >= tr(phi_{s,p}(H)) - b.
    """
    b_i = parse_exact_int(b, min_value=0)
    require(
        isinstance(a_coeffs, (list, tuple)) and len(a_coeffs) == 2,
        "INVALID_WITNESS",
        "degree-4 Stieltjes-Hankel witness requires exactly 2 coefficients (s, p)",
    )
    s = parse_exact_fraction(a_coeffs[0])
    p = parse_exact_fraction(a_coeffs[1])
    if not _mutate_skip_nonneg_hankel:
        require(s >= 0, "NEGATIVE_HANKEL_COEFF", f"s = {s} < 0 violates phi(lam) <= 0 on lam <= 0")
        require(p >= 0, "NEGATIVE_HANKEL_COEFF", f"p = {p} < 0 violates phi(lam) <= 0 on lam <= 0")

    for k in (1, 2, 3, 4):
        require(k in moments, "MISSING_SPECTRAL_MOMENT", f"missing moment S_{k}")
        parse_exact_fraction(moments[k])

    S1, S2, S3, S4 = moments[1], moments[2], moments[3], moments[4]
    # phi(lam) = 1 - (1 - s*lam + p*lam^2)^2
    #          = 2*s*lam - (s^2 + 2*p)*lam^2 + 2*s*p*lam^3 - p^2*lam^4
    tr_phi = 2 * s * S1 - (s * s + 2 * p) * S2 + 2 * s * p * S3 - (p * p) * S4
    raw = tr_phi - Fraction(b_i)
    bound = raw if raw > 0 else Fraction(0)
    return {
        "s": s,
        "p": p,
        "tr_phi": tr_phi,
        "bound": bound,
        "min_rank_cert": ceil_fraction(bound),
    }


def R_hankel4_optimal(moments: dict[int, Fraction], b: int) -> dict[str, Any]:
    """Exact closed-form KKT global optimum of Theorem A2 at degree 4 (R_H4)."""
    b_i = parse_exact_int(b, min_value=0)
    S1 = parse_exact_fraction(moments[1])
    S2 = parse_exact_fraction(moments[2])
    S3 = parse_exact_fraction(moments[3])
    S4 = parse_exact_fraction(moments[4])

    candidates: list[tuple[Fraction, Fraction]] = [(Fraction(0), Fraction(0))]
    if S2 > 0 and S1 > 0:
        candidates.append((S1 / S2, Fraction(0)))
    det = S2 * S4 - S3 * S3
    if det > 0:
        s_star = (S1 * S4 - S2 * S3) / det
        p_star = (S1 * S3 - S2 * S2) / det
        if s_star >= 0 and p_star >= 0:
            candidates.append((s_star, p_star))

    best: dict[str, Any] | None = None
    for cand in candidates:
        cert = certify_stieltjes_hankel_deg4(moments, b_i, cand)
        if best is None or cert["bound"] > best["bound"]:
            best = cert
    require(best is not None, "INTERNAL_H4_EMPTY", "no KKT candidate evaluated")
    return best  # type: ignore[return-value]


# ==============================================================================
# BENCHMARK CONSTRUCTION: DENSE NON-COMMUTING COMPLEX INDEFINITE 4x4 OVER Q(i)
# ==============================================================================
def build_exact_unitary_4x4() -> CMat:
    """
    Construct a dense exact unitary U in Q(i)^{4x4} from exact (3,4,5) Pythagorean
    2x2 unitary rotations mixing all 4 coordinates:
      U = U_{01}(complex) @ U_{23}(real) @ U_{12}(complex).
    """
    c35 = Qi.of(Fraction(3, 5))
    c45 = Qi.of(Fraction(4, 5))
    i45 = Qi.of(0, Fraction(4, 5))
    i35 = Qi.of(0, Fraction(3, 5))

    U01 = ceye(4)
    U01[0][0], U01[0][1] = c35, i45
    U01[1][0], U01[1][1] = i45, c35

    U23 = ceye(4)
    U23[2][2], U23[2][3] = c45, c35
    U23[3][2], U23[3][3] = -c35, c45

    U12 = ceye(4)
    U12[1][1], U12[1][2] = c45, i35
    U12[2][1], U12[2][2] = i35, c45

    U = cmul(cmul(U01, U23), U12)
    # Self-verify U U* == I_4 identically over Q(i)
    prod = cmul(U, cdagger(U))
    I4 = ceye(4)
    require(prod == I4, "UNITARY_FAIL", "exact Q(i) unitary check U U* == I failed")
    return U


def build_chain1_noncommuting_system() -> dict[str, Any]:
    """
    Construct the canonical Chain-1 non-commuting indefinite 4x4 complex Hermitian
    benchmark H = P + Q over Q(i) with:
      - H_0 = diag(16, 4, 4, -1) => S_1 = 23, S_2 = 289 = 17^2, 2*S_2 - S_1^2 = 49 = 7^2!
      - v = (12/5, (8/5)i, 0, 0)^T => v* diag(16, 4, 4)^{-1} v = 9/25 + 16/25 = 1
      - Q_0 = v v* - e_4 e_4* (indefinite: eigenvalues +208/25 and -1; n_+(Q) = b = 1)
      - P_0 = H_0 - Q_0 >= 0 (exact rank 2, strictly non-commuting with Q_0!)
      - Conjugate (P_0, Q_0, H_0) by dense exact unitary U in Q(i)^{4x4}.
    """
    H0 = cdiag([16, 4, 4, -1])
    v = [Qi.of(Fraction(12, 5)), Qi.of(0, Fraction(8, 5)), Q0, Q0]

    Q0_mat = czeros(4, 4)
    for i in range(4):
        for j in range(4):
            Q0_mat[i][j] = v[i] * v[j].conj()
    Q0_mat[3][3] = Q0_mat[3][3] - Q1

    P0_mat = csub(H0, Q0_mat)
    U = build_exact_unitary_4x4()
    Udag = cdagger(U)

    H = cmul(cmul(U, H0), Udag)
    P = cmul(cmul(U, P0_mat), Udag)
    Q = cmul(cmul(U, Q0_mat), Udag)

    # Orthogonal projector Pi_W onto W = range(Q_+) = span(U v)
    w_vec = [sum((U[i][t] * v[t] for t in range(4)), Q0) for i in range(4)]
    w_norm_sq = sum((x.norm_sq() for x in w_vec), Fraction(0))
    Pi_W = czeros(4, 4)
    for i in range(4):
        for j in range(4):
            Pi_W[i][j] = (w_vec[i] * w_vec[j].conj()) / Qi(w_norm_sq)
    Pi_W_perp = csub(ceye(4), Pi_W)

    # Confirm non-commutation [P, Q] != 0 and nonzero imaginary entries
    comm = csub(cmul(P, Q), cmul(Q, P))
    comm_norm_sq = cfrob_sq(comm)
    has_complex = any(entry.im != 0 for row in H for entry in row)
    require(comm_norm_sq > 0, "COMMUTING_FAIL", "benchmark must be strictly non-commuting")
    require(has_complex, "REAL_ONLY_FAIL", "benchmark must have nonzero imaginary entries")

    # Also build exact Q_+ and Q_- for the 6-term slack identity check
    Qp0 = czeros(4, 4)
    for i in range(4):
        for j in range(4):
            Qp0[i][j] = v[i] * v[j].conj()
    Qm0 = cdiag([0, 0, 0, 1])
    Qp = cmul(cmul(U, Qp0), Udag)
    Qm = cmul(cmul(U, Qm0), Udag)

    return {
        "H": H,
        "P": P,
        "Q": Q,
        "Qp": Qp,
        "Qm": Qm,
        "Pi_W": Pi_W,
        "Pi_W_perp": Pi_W_perp,
        "b": 1,
        "comm_norm_sq": comm_norm_sq,
    }


# ==============================================================================
# FIVE-STAGE LIVE RESONANCE CYCLE
# ==============================================================================
def run_stage1_pass1_bug() -> dict[str, Any]:
    """Stage 1: Reproduces AUDIT-001 Pass-1 prototype forgery (rank >= 117 on 2x2)."""
    H = cdiag([1, 0])
    Q10 = cdiag([10, 0])
    Q11 = cdiag([11, 0])

    forged_117 = buggy_pass1_lemma32(H, Q10, b=1, c=Fraction(2))
    forged_140 = buggy_pass1_lemma32(H, Q11, b=1, c=Fraction(2))
    require(forged_117 == Fraction(117), "STAGE1_MISMATCH", f"expected 117, got {forged_117}")
    require(forged_140 == Fraction(140), "STAGE1_MISMATCH", f"expected 140, got {forged_140}")
    require(not is_psd_hermitian(csub(H, Q10)), "STAGE1_PSD_EXPECTED_FALSE", "P = diag(-9, 0) cannot be PSD")

    return {
        "stage": 1,
        "name": "Pass-1 Buggy Prototype (AUDIT-001 FALSIFIED)",
        "matrix_dim": 2,
        "H_diag": ["1", "0"],
        "Q_diag": ["10", "0"],
        "P_diag": ["-9", "0"],
        "P_is_psd": False,
        "forged_rank_bound_Q10": frac_str(forged_117),
        "forged_rank_bound_Q11": frac_str(forged_140),
        "cave_trap": "Static critique stops here and logs N0; Aletheia logs FALSIFIED and invokes Law 2 (Steelman).",
    }


def run_stage2_steelman_projection(sys_data: dict[str, Any]) -> dict[str, Any]:
    """Stage 2: Steelman Lemma 3.2 on W (+) W^perp -> exact guarded R_opt (AUDIT-002)."""
    H, P, Q = sys_data["H"], sys_data["P"], sys_data["Q"]
    Qp, Qm = sys_data["Qp"], sys_data["Qm"]
    Pi_W, Pi_Wp = sys_data["Pi_W"], sys_data["Pi_W_perp"]
    b = sys_data["b"]

    # Verify exact 6-term nonnegative slack inequality at c = 2 on the non-commuting system
    c = Fraction(2)
    u = ctrace_real(P)
    t = ctrace_real(Q)
    S = cfrob_sq(H)

    P11 = cmul(cmul(Pi_W, P), Pi_W)
    P12 = cmul(cmul(Pi_W, P), Pi_Wp)
    H_perp = cmul(cmul(Pi_Wp, H), Pi_Wp)
    n_pos_H_perp = independent_hermitian_inertia_oracle(to_raw_cmat(H_perp))["n_pos"]

    lhs_gap = Fraction(n_pos_H_perp) + c * c * Fraction(b) - (2 * u + 2 * c * t - S)
    term_p11_qm = 2 * (c - 1) * (ctrace_real(P11) + ctrace_real(Qm))
    term_p12 = 2 * cfrob_sq(P12)
    term_block = cfrob_sq(csub(cadd(P11, Qp), cscale(c, Pi_W)))
    rhs_slack_lb = term_p11_qm + term_p12 + term_block
    require(rhs_slack_lb >= 0 and lhs_gap >= rhs_slack_lb, "SLACK_FAIL", "6-term slack inequality failed")

    # Verify exact scale invariance at lambda = 17/5
    lam = Fraction(17, 5)
    ropt_base = R_opt_guarded(u, t, S, b)
    ropt_scaled = R_opt_guarded(lam * u, lam * t, lam * lam * S, b)
    require(ropt_base == ropt_scaled, "SCALE_INV_FAIL", "R_opt not scale invariant")

    # Verify both AUDIT-002 boundary guards (raw formula would crash with 0/0 or return -1/5)
    guard1_zero_u = R_opt_guarded(Fraction(0), Fraction(2), Fraction(4), 1)
    guard2_neg_else = R_opt_guarded(Fraction(1), Fraction(1), Fraction(5), 1)
    require(guard1_zero_u == Fraction(0), "GUARD1_FAIL", "Guard 1 (u=0, t^2=bS) failed")
    require(guard2_neg_else == Fraction(0), "GUARD2_FAIL", "Guard 2 (negative else-branch) failed")

    # Exact Scan 23848 Mode B benchmark (rho = 0 and rho = 3/4)
    w1 = Fraction(6404, 10000) ** 2
    w2 = Fraction(3596, 10000) ** 2
    scan_rows = {}
    for label, rho in [("rho=0", Fraction(0)), ("rho=3/4", Fraction(3, 4))]:
        S_r = w1 * w1 + w2 * w2 + 2 * w1 * w2 * rho * rho
        ro = R_opt_guarded(w2, w1, S_r, 1)
        rc2 = R_lemma32_fixed_c(w2, w1, S_r, 1, c=Fraction(2))
        require(ro > rc2, "SCAN_BEAT_FAIL", f"expected R_opt > Lemma32(c=2) at {label}")
        scan_rows[label] = {
            "R_opt_exact": frac_str(ro),
            "R_opt_dec": frac_decimal_str(ro, 6),
            "Lemma32_c2_dec": frac_decimal_str(rc2, 6),
        }
    require(scan_rows["rho=0"]["R_opt_exact"] == "1", "SCAN_RHO0_FAIL", "expected exact 1 at rho=0")
    require(scan_rows["rho=3/4"]["Lemma32_c2_dec"] == "0.000000", "SCAN_RHO34_FAIL", "expected c=2 collapse at rho=3/4")

    return {
        "stage": 2,
        "name": "Steelman Projection on W (+) W^perp (AUDIT-002 VERIFIED N2)",
        "slack_lhs_gap_c2": frac_str(lhs_gap),
        "slack_explicit_nonneg_lb_c2": frac_str(rhs_slack_lb),
        "scale_invariance_lambda_17_5_exact": True,
        "boundary_guard_1_u0_t2_eq_bS": frac_str(guard1_zero_u),
        "boundary_guard_2_neg_else_clamped": frac_str(guard2_neg_else),
        "scan23848_mode_b": scan_rows,
    }


def run_stage3_tomography_and_sharpness_wall(sys_data: dict[str, Any]) -> dict[str, Any]:
    """Stage 3: Zero-shared-code Faddeev-LeVerrier+Descartes oracle + exact rational rank-1 wall."""
    H, P, Q = sys_data["H"], sys_data["P"], sys_data["Q"]
    Pi_Wp = sys_data["Pi_W_perp"]
    b = sys_data["b"]

    P_perp = cmul(cmul(Pi_Wp, P), Pi_Wp)
    H_perp = cmul(cmul(Pi_Wp, H), Pi_Wp)

    # Zero-shared-code independent inertia oracle checks
    H_oracle = independent_hermitian_inertia_oracle(to_raw_cmat(H))
    P_oracle = independent_hermitian_inertia_oracle(to_raw_cmat(P))
    Q_oracle = independent_hermitian_inertia_oracle(to_raw_cmat(Q))
    Hp_oracle = independent_hermitian_inertia_oracle(to_raw_cmat(H_perp))

    rank_P = crank(P)
    rank_P_perp = crank(P_perp)
    n_pos_H_perp = Hp_oracle["n_pos"]

    require(P_oracle["n_neg"] == 0 and P_oracle["n_pos"] == 2, "P_INERTIA_FAIL", "expected P inertia (2,0,2)")
    require(Q_oracle["inertia"] == [1, 1, 2], "Q_INERTIA_FAIL", "expected Q inertia (1,1,2)")
    require(H_oracle["inertia"] == [3, 1, 0], "H_INERTIA_FAIL", "expected H inertia (3,1,0)")
    require(rank_P == 2 and rank_P_perp == 2 and n_pos_H_perp == 2, "CHAIN_FAIL", "expected chain 2>=2>=2")

    u = ctrace_real(P)
    t = ctrace_real(Q)
    S = cfrob_sq(H)
    require(u == Fraction(392, 25) and t == Fraction(183, 25) and S == Fraction(289), "MOMENT_FAIL", "unexpected (u,t,S)")

    ropt = R_opt_guarded(u, t, S, b)
    rc2 = R_lemma32_fixed_c(u, t, S, b, c=Fraction(2))
    rg = R_G_fable(u, t, S, b)
    require(ropt == Fraction(240, 289), "ROPT_FAIL", f"expected 240/289, got {ropt}")
    require(rc2 == Fraction(0) and rg == Fraction(0), "BASELINES_FAIL", "expected fixed c=2 and R_G collapse to 0")
    require(Fraction(n_pos_H_perp) >= ropt, "CHAIN_ROPT_FAIL", "n_+(H_perp) < R_opt")

    # Construct the EXACT RATIONAL RANK-1 DECOY proving the quadratic sharpness wall!
    # Since S_1 = 23, S_2 = 289 = 17^2, 2*S_2 - S_1^2 = 49 = 7^2 => h_hi = 15, h_lo = 8!
    P_decoy = cdiag([0, Fraction(392, 25)])
    Q_decoy = cdiag([15, Fraction(-192, 25)])
    H_decoy = cadd(P_decoy, Q_decoy)

    P_decoy_oracle = independent_hermitian_inertia_oracle(to_raw_cmat(P_decoy))
    Q_decoy_oracle = independent_hermitian_inertia_oracle(to_raw_cmat(Q_decoy))
    require(P_decoy_oracle["n_neg"] == 0 and P_decoy_oracle["n_pos"] == 1, "DECOY_P_FAIL", "decoy must be PSD rank 1")
    require(Q_decoy_oracle["n_pos"] == 1, "DECOY_Q_FAIL", "decoy must have n_+(Q) == 1")
    require(ctrace_real(P_decoy) == u, "DECOY_U_FAIL", "decoy tr(P) != u")
    require(ctrace_real(Q_decoy) == t, "DECOY_T_FAIL", "decoy tr(Q) != t")
    require(cfrob_sq(H_decoy) == S, "DECOY_S_FAIL", "decoy ||H||_F^2 != S")

    # Also verify exact integer equality sharpness witnesses in Regime 1 & Regime 2
    r1_exact = R_opt_guarded(Fraction(6), Fraction(5), Fraction(43), 1)  # P=diag(0,3,3), Q=diag(5,0,0)
    r2_exact = R_opt_guarded(Fraction(10), Fraction(-4), Fraction(12), 1)  # P=diag(0,5,5), Q=diag(2,-3,-3)
    require(r1_exact == Fraction(2) and r2_exact == Fraction(2), "EXACT_SHARP_FAIL", "exact sharpness check failed")

    return {
        "stage": 3,
        "name": "Observer Tomography (G_obs) & Quadratic Sharpness Wall (AUDIT-002)",
        "noncommuting_benchmark": {
            "dim": 4,
            "strictly_complex": True,
            "commutator_frob_sq": frac_str(sys_data["comm_norm_sq"]),
            "H_inertia_descartes": H_oracle["inertia"],
            "H_cayley_hamilton_zero": H_oracle["cayley_hamilton_zero"],
            "P_inertia_descartes": P_oracle["inertia"],
            "Q_inertia_descartes": Q_oracle["inertia"],
            "H_perp_inertia_descartes": Hp_oracle["inertia"],
            "true_rank_P": rank_P,
            "true_rank_P_perp": rank_P_perp,
            "true_n_pos_H_perp": n_pos_H_perp,
            "moments_u_t_S_b": [frac_str(u), frac_str(t), frac_str(S), b],
            "Lemma32_c2_bound": frac_str(rc2),
            "Fable_RG_bound": frac_str(rg),
            "R_opt_exact": frac_str(ropt),
            "R_opt_dec": frac_decimal_str(ropt, 6),
            "R_opt_min_rank_cert": max(1, ceil_fraction(ropt)),
        },
        "sharpness_wall_exact_decoy": {
            "P_decoy_diag": ["0", "392/25"],
            "Q_decoy_diag": ["15", "-192/25"],
            "H_decoy_diag": ["15", "8"],
            "decoy_rank_P": 1,
            "decoy_n_pos_Q": 1,
            "identical_u_t_S_b": True,
            "wall_proven": "min rank(P) = max(1, ceil(240/289)) = 1; NO 2nd-moment theorem can certify rank >= 2 here.",
        },
        "exact_integer_tightness_regimes": {
            "regime1_u6_t5_S43_b1": frac_str(r1_exact),
            "regime2_u10_tm4_S12_b1": frac_str(r2_exact),
        },
        "_H_decoy": H_decoy,
    }


def run_stage4_resonance_breakthrough(sys_data: dict[str, Any], H_decoy: CMat) -> dict[str, Any]:
    """Stage 4: Theorem A2 (R_H4) smashes through the proven 2nd-moment wall (AUDIT-014)."""
    H = sys_data["H"]
    b = sys_data["b"]

    # Compute exact rational moments S_1..S_4 of the dense non-commuting complex indefinite H
    moms_H = spectral_moments(H, max_k=4)
    require(
        moms_H[1] == Fraction(23)
        and moms_H[2] == Fraction(289)
        and moms_H[3] == Fraction(4223)
        and moms_H[4] == Fraction(66049),
        "H_MOMENTS_FAIL",
        f"unexpected moments {moms_H}",
    )

    cert_H = R_hankel4_optimal(moms_H, b=b)
    # Must strictly break past 1 (certifying rank(P) >= 2) while staying <= true n_+(H_perp) = 2!
    require(cert_H["bound"] > Fraction(1), "H4_BREAK_FAIL", f"R_H4 failed to break wall 1: {cert_H['bound']}")
    require(cert_H["bound"] <= Fraction(2), "H4_SOUND_FAIL", f"R_H4 exceeded true n_+(H_perp)=2: {cert_H['bound']}")
    require(cert_H["min_rank_cert"] == 2, "H4_RANK_FAIL", "expected certified min rank == 2")

    # Verify the polynomial pointwise bound phi_{s*, p*}(lam) <= 1_{(0,+inf)}(lam) at every eigenvalue
    s_star, p_star = cert_H["s"], cert_H["p"]
    eig_evals = {}
    for lam_int in (16, 4, -1):
        lam = Fraction(lam_int)
        q_val = Fraction(1) - s_star * lam + p_star * lam * lam
        phi_val = Fraction(1) - q_val * q_val
        if lam <= 0:
            require(phi_val <= 0, "PHI_NEG_FAIL", f"phi({lam}) = {phi_val} > 0")
        else:
            require(phi_val <= 1, "PHI_POS_FAIL", f"phi({lam}) = {phi_val} > 1")
        eig_evals[str(lam_int)] = frac_decimal_str(phi_val, 6)

    # Check R_H4 on the rank-1 decoy H_decoy = diag(15, 8): MUST respect rank(P_decoy) = 1!
    moms_decoy = spectral_moments(H_decoy, max_k=4)
    cert_decoy = R_hankel4_optimal(moms_decoy, b=b)
    require(cert_decoy["bound"] == Fraction(1), "DECOY_H4_FAIL", f"expected R_H4(decoy) == 1, got {cert_decoy['bound']}")

    return {
        "stage": 4,
        "name": "Resonance Breakthrough — 4th-Moment Stieltjes-Hankel R_H4 (AUDIT-014 VERIFIED N2)",
        "noncommuting_H_moments_S1_to_S4": [frac_str(moms_H[k]) for k in (1, 2, 3, 4)],
        "optimal_witness_s_p": [frac_str(s_star), frac_str(p_star)],
        "phi_at_eigenvalues_16_4_m1": eig_evals,
        "R_H4_exact": frac_str(cert_H["bound"]),
        "R_H4_dec": frac_decimal_str(cert_H["bound"], 6),
        "R_H4_min_rank_cert": cert_H["min_rank_cert"],
        "wall_broken": True,
        "decoy_moments_S1_to_S4": [frac_str(moms_decoy[k]) for k in (1, 2, 3, 4)],
        "R_H4_on_rank1_decoy_exact": frac_str(cert_decoy["bound"]),
        "decoy_separation": "Same (S1, S2) = (23, 289), but higher moments (4223, 66049) vs (3887, 54721) break the rank-1 degeneracy!",
    }


def run_stage5_r5_controls_and_mutations() -> dict[str, Any]:
    """Stage 5: 7 must-fail controls + 3 live refusal-site mutations (Gate 7 R5)."""
    controls_spec: list[tuple[str, str, Any]] = [
        (
            "C1_missing_P_psd_forgery",
            "P_NOT_PSD",
            lambda: certify_matrix_ropt(cdiag([1, 0]), cdiag([10, 0]), b=1),
        ),
        (
            "C2_non_hermitian_H",
            "MATRIX_NOT_HERMITIAN",
            lambda: certify_matrix_ropt(
                [[Qi.of(2), Qi.of(1)], [Q0, Qi.of(2)]],
                [[Q0, Qi.of(1)], [Q0, Q0]],
                b=0,
            ),
        ),
        (
            "C3_negative_hankel_coeff",
            "NEGATIVE_HANKEL_COEFF",
            lambda: certify_stieltjes_hankel_deg4(
                {1: Fraction(-9), 2: Fraction(101), 3: Fraction(-999), 4: Fraction(10001)},
                b=0,
                a_coeffs=(Fraction(1), Fraction(-11, 100)),
            ),
        ),
        (
            "C4_bool_input_leak",
            "INVALID_TYPE",
            lambda: R_opt_guarded(Fraction(1), Fraction(1), Fraction(2), True),  # type: ignore[arg-type]
        ),
        (
            "C5_float_input_leak",
            "INVALID_TYPE",
            lambda: R_opt_guarded(Fraction(1), Fraction(1), 2.0, 1),  # type: ignore[arg-type]
        ),
        (
            "C6_negative_b",
            "INVALID_B",
            lambda: R_opt_guarded(Fraction(1), Fraction(1), Fraction(2), -1),
        ),
        (
            "C7_dim_mismatch_H_Q",
            "DIM_MISMATCH",
            lambda: certify_matrix_ropt(ceye(3), czeros(2, 2), b=0),
        ),
    ]

    control_results: list[dict[str, Any]] = []
    for name, expected_code, fn in controls_spec:
        caught_code: str | None = None
        try:
            fn()
        except CertError as exc:
            caught_code = exc.code
        require(
            caught_code == expected_code,
            "CONTROL_FAILED",
            f"control {name}: expected {expected_code}, got {caught_code}",
        )
        control_results.append({"control": name, "expected": expected_code, "caught": caught_code, "passed": True})

    # Live Refusal-Site Mutation Suite (R5): deleting any guard MUST allow a forgery!
    mutations: list[dict[str, Any]] = []

    # Mutant 1: Delete P >= 0 guard -> C1 forges rank >= 117 on 2x2 matrix!
    m1 = certify_matrix_ropt(cdiag([1, 0]), cdiag([10, 0]), b=1, _mutate_skip_p_psd=True)
    require(m1["bound"] == Fraction(117), "MUTANT1_NOT_EXPLOITED", "deleting P>=0 guard should forge 117")
    mutations.append({
        "mutant": "M1_delete_P_psd_guard",
        "forged_result": f"rank >= {frac_str(m1['bound'])} on 2x2",
        "killed_by_control": "C1_missing_P_psd_forgery",
        "killed": True,
    })

    # Mutant 2: Delete Hermitian guard -> C2 passes non-Hermitian H=[[2,1],[0,2]], Q=[[0,1],[0,0]]
    # (note P = H - Q = 2*I_2 IS genuinely PSD Hermitian, proving the Hermitian guard is non-redundant!)
    m2 = certify_matrix_ropt(
        [[Qi.of(2), Qi.of(1)], [Q0, Qi.of(2)]],
        [[Q0, Qi.of(1)], [Q0, Q0]],
        b=0,
        _mutate_skip_hermitian=True,
    )
    require(m2["bound"] == Fraction(16, 9), "MUTANT2_NOT_EXPLOITED", "deleting Hermitian guard should accept [[2,1],[0,2]]")
    mutations.append({
        "mutant": "M2_delete_hermitian_guard",
        "forged_result": f"accepted non-Hermitian H,Q (with PSD P=2I) yielding bound {frac_str(m2['bound'])}",
        "killed_by_control": "C2_non_hermitian_H",
        "killed": True,
    })

    # Mutant 3: Delete a_k >= 0 guard -> C3 forges rank >= 2 on rank-1 indefinite diag(1, -10)!
    # At lam = -10, a = (1, -11/100) gives q(-10) = 1 + 10 - 11 = 0 => phi(-10) = +1 on a NEGATIVE eigenvalue!
    m3 = certify_stieltjes_hankel_deg4(
        {1: Fraction(-9), 2: Fraction(101), 3: Fraction(-999), 4: Fraction(10001)},
        b=0,
        a_coeffs=(Fraction(1), Fraction(-11, 100)),
        _mutate_skip_nonneg_hankel=True,
    )
    require(m3["bound"] == Fraction(19879, 10000) and m3["min_rank_cert"] == 2, "MUTANT3_NOT_EXPLOITED", "deleting a_k>=0 should forge rank >= 2")
    mutations.append({
        "mutant": "M3_delete_hankel_nonneg_guard",
        "forged_result": f"bound {frac_str(m3['bound'])} ({frac_decimal_str(m3['bound'], 4)}) -> forges rank >= 2 on rank-1 diag(1,-10)",
        "killed_by_control": "C3_negative_hankel_coeff",
        "killed": True,
    })

    return {
        "stage": 5,
        "name": "R5 Must-Fail Controls & Live Refusal-Site Mutation Suite (Gate 7)",
        "controls_passed": len(control_results),
        "controls_total": len(control_results),
        "controls": control_results,
        "mutants_killed": len(mutations),
        "mutants_total": len(mutations),
        "mutations": mutations,
    }


def run_all() -> dict[str, Any]:
    sys_data = build_chain1_noncommuting_system()
    s1 = run_stage1_pass1_bug()
    s2 = run_stage2_steelman_projection(sys_data)
    s3_full = run_stage3_tomography_and_sharpness_wall(sys_data)
    H_decoy = s3_full.pop("_H_decoy")
    s4 = run_stage4_resonance_breakthrough(sys_data, H_decoy)
    s5 = run_stage5_r5_controls_and_mutations()

    payload = {
        "demo": "aletheia.worked_resonance_cycle.v1",
        "oracle_class": "exact",
        "arithmetic": "pure_python_stdlib_Q_and_Qi_zero_floats",
        "stages": [s1, s2, s3_full, s4, s5],
        "verdict": "ALL_5_STAGES_VERIFIED",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["canonical_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def print_human_report(res: dict[str, Any]) -> None:
    s1, s2, s3, s4, s5 = res["stages"]
    bm = s3["noncommuting_benchmark"]
    decoy = s3["sharpness_wall_exact_decoy"]
    line = "=" * 78
    print(line)
    print("  THE ALETHEIA METHOD — WORKED RESONANCE CYCLE (LIVE EXACT-ARITHMETIC DEMO)")
    print("  Pure Python 3 stdlib | Zero floats | Zero bare asserts | Q & Q(i) exact")
    print(line)

    print(f"\n[STAGE 1] {s1['name']}")
    print(f"  2x2 test: H = diag(1, 0), Q = diag(10, 0), P = H - Q = diag(-9, 0) [PSD={s1['P_is_psd']}]")
    print(f"  Buggy prototype (no P >= 0 check) FORGES: rank(P) >= {s1['forged_rank_bound_Q10']} (and >= {s1['forged_rank_bound_Q11']} for Q=diag(11,0))!")
    print(f"  -> {s1['cave_trap']}")

    print(f"\n[STAGE 2] {s2['name']}")
    print(f"  Exact W (+) W^perp 6-term slack at c=2: LHS gap {s2['slack_lhs_gap_c2']} >= explicit nonneg slack {s2['slack_explicit_nonneg_lb_c2']}")
    print(f"  Exact scale invariance (lambda = 17/5): {s2['scale_invariance_lambda_17_5_exact']}")
    print(f"  Boundary guards: u=0,t^2=bS -> {s2['boundary_guard_1_u0_t2_eq_bS']} | neg else-branch -> {s2['boundary_guard_2_neg_else_clamped']}")
    sc0 = s2["scan23848_mode_b"]["rho=0"]
    sc34 = s2["scan23848_mode_b"]["rho=3/4"]
    print(f"  Scan 23848 Mode B: rho=0 -> R_opt = {sc0['R_opt_exact']} (vs c=2: {sc0['Lemma32_c2_dec']}) | rho=3/4 -> R_opt = {sc34['R_opt_dec']} (vs c=2: {sc34['Lemma32_c2_dec']})")

    print(f"\n[STAGE 3] {s3['name']}")
    print(f"  Dense 4x4 strictly complex non-commuting indefinite H = P + Q over Q(i):")
    print(f"    ||[P, Q]||_F^2 = {bm['commutator_frob_sq']} > 0 | H inertia (Descartes) = {bm['H_inertia_descartes']} (Cayley-Hamilton == 0)")
    print(f"    True chain: rank(P)={bm['true_rank_P']} >= rank(P_perp)={bm['true_rank_P_perp']} >= n_+(H_perp)={bm['true_n_pos_H_perp']} (b=1)")
    print(f"    2nd-moment bounds: Lemma32(c=2) = {bm['Lemma32_c2_bound']} | Fable R_G = {bm['Fable_RG_bound']} | R_opt = {bm['R_opt_exact']} ({bm['R_opt_dec']}) -> cert >= {bm['R_opt_min_rank_cert']}")
    print(f"  EXACT RATIONAL SHARPNESS WALL (Pythagorean triple 8^2 + 15^2 = 17^2 = 289):")
    print(f"    Decoy: P_decoy = diag(0, 392/25) [rank 1], Q_decoy = diag(15, -192/25) [b=1], H_decoy = diag(15, 8)")
    print(f"    Matches (u, t, S, b) = ({', '.join(map(str, bm['moments_u_t_S_b']))}) IDENTICALLY -> {decoy['wall_proven']}")

    print(f"\n[STAGE 4] {s4['name']}")
    print(f"  Higher moments of H: (S1, S2, S3, S4) = ({', '.join(s4['noncommuting_H_moments_S1_to_S4'])})")
    print(f"  Exact KKT witness (s*, p*) = ({s4['optimal_witness_s_p'][0]}, {s4['optimal_witness_s_p'][1]}) > 0")
    print(f"  phi(eig) check (<= 1 on +eig, <= 0 on -eig): {s4['phi_at_eigenvalues_16_4_m1']}")
    print(f"  BREAKTHROUGH: R_H4(H, b=1) = {s4['R_H4_exact']} ({s4['R_H4_dec']}) > 1 -> CERTIFIES rank(P) >= n_+(H_perp) >= {s4['R_H4_min_rank_cert']}!")
    print(f"  Sanity check on rank-1 decoy: R_H4(H_decoy, b=1) = {s4['R_H4_on_rank1_decoy_exact']} (exact!)")

    print(f"\n[STAGE 5] {s5['name']}")
    print(f"  Must-fail negative controls: {s5['controls_passed']}/{s5['controls_total']} rejected with exact error codes")
    print(f"  Live refusal-site mutations: {s5['mutants_killed']}/{s5['mutants_total']} guard deletions caught & killed:")
    for mut in s5["mutations"]:
        print(f"    - {mut['mutant']} -> {mut['forged_result']} [KILLED by {mut['killed_by_control']}]")

    print(f"\n{line}")
    print(f"  VERDICT: {res['verdict']} | Canonical SHA-256: {res['canonical_sha256']}")
    print(line)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="The Aletheia Method: 3-second exact-arithmetic Worked Resonance Cycle demo."
    )
    parser.add_argument("--json", action="store_true", help="Emit canonical deterministic JSON.")
    args = parser.parse_args(argv)
    res = run_all()
    if args.json:
        print(json.dumps(res, indent=2, sort_keys=True))
    else:
        print_human_report(res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
