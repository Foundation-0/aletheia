#!/usr/bin/env python3
"""Exact pure-rational witnesses for Natural Systems Stage-B Portals 2, 3 and 5.

Portal 2 (reaction-diffusion / Turing symmetry breaking on graphs):
  - per-mode dispersion factorisation of the block operator I (x) J - L (x) D,
  - equal-diffusion obstruction (positive-coefficient certificate),
  - exact spectral-band aliasing on cycles C_3..C_16 and paths P_2..P_8 via Sturm counts,
  - complete-graph all-or-none obstruction.
Portal 3 (Beltrami / helicity transport on a periodic lattice):
  - central-difference curl C is symmetric, div C = 0, C grad = 0,
  - parity P C P = -C (non-chiral helicity-sign obstruction),
  - lattice aliasing: rank C = 2 (n^3 - z) with z = (1 if n odd else 2)^3, proven
    by a mod-p lower bound plus an explicit integer kernel upper bound,
  - skew transport K conserves energy; conserves helicity iff [C, K] = 0,
  - exact Cayley steps conserve every moment v^T C^j v (zero shell transfer),
  - non-commuting skew drifts helicity; symmetric residual I + C/4 drifts the
    helicity Rayleigh quotient monotonically (collapse control).
Portal 5 (Darboux isospectral pairs, dark modes, lapse inertia, Hopf fibre):
  - A L1 = L2 A and charpoly(L1) = (x - c)^(n - m) charpoly(L2),
  - eigenvector transport with norm factor (lambda - c),
  - dark-mode collisions on ker A and exact reconstruction projector,
  - square singular SUSY pair: isospectral yet not losslessly transportable,
  - lapse N L preserves inertia (Sylvester) but not spectrum,
  - quaternion left multiplication is a dark-mode-free converter; the Hopf map
    has an exact one-dimensional S^1 dark fibre.

Every quantity is an int or fractions.Fraction. No floats, no third-party imports.
Exit code 0 iff every check passes; the last stdout line is a canonical JSON receipt.
"""

from __future__ import annotations

from fractions import Fraction as F
import hashlib
import json
import sys
from typing import Any, Iterable


class Checker:
    """Records named exact checks without using assert statements."""

    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []

    def check(self, name: str, ok: bool, detail: Any = "") -> bool:
        self.results.append({"name": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    @property
    def failures(self) -> list[dict[str, Any]]:
        return [r for r in self.results if not r["ok"]]


# ---------------------------------------------------------------------------
# Dense exact linear algebra (int / Fraction)
# ---------------------------------------------------------------------------


def frac_matrix(rows: Iterable[Iterable[Any]]) -> list[list[F]]:
    return [[F(x) for x in row] for row in rows]


def eye(n: int) -> list[list[F]]:
    return [[F(1) if i == j else F(0) for j in range(n)] for i in range(n)]


def transpose(a: list[list[Any]]) -> list[list[Any]]:
    return [list(col) for col in zip(*a)]


def matmul(a: list[list[Any]], b: list[list[Any]]) -> list[list[Any]]:
    bt = transpose(b)
    return [[sum((x * y for x, y in zip(row, col)), 0) for col in bt] for row in a]


def matadd(a: list[list[Any]], b: list[list[Any]], s: Any = 1) -> list[list[Any]]:
    return [[x + s * y for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


def matscale(a: list[list[Any]], s: Any) -> list[list[Any]]:
    return [[s * x for x in row] for row in a]


def matvec(a: list[list[Any]], v: list[Any]) -> list[Any]:
    return [sum((x * y for x, y in zip(row, v)), 0) for row in a]


def dot(u: list[Any], v: list[Any]) -> Any:
    return sum((x * y for x, y in zip(u, v)), 0)


def trace(a: list[list[Any]]) -> Any:
    return sum((a[i][i] for i in range(len(a))), 0)


def diag(values: Iterable[Any]) -> list[list[F]]:
    vals = [F(v) for v in values]
    n = len(vals)
    return [[vals[i] if i == j else F(0) for j in range(n)] for i in range(n)]


def kron(a: list[list[Any]], b: list[list[Any]]) -> list[list[Any]]:
    ra, ca, rb, cb = len(a), len(a[0]), len(b), len(b[0])
    return [[a[i // rb][j // cb] * b[i % rb][j % cb] for j in range(ca * cb)] for i in range(ra * rb)]


def mat_eq(a: list[list[Any]], b: list[list[Any]]) -> bool:
    return len(a) == len(b) and all(len(ra) == len(rb) and all(x == y for x, y in zip(ra, rb)) for ra, rb in zip(a, b))


def inverse(a: list[list[Any]]) -> list[list[F]]:
    n = len(a)
    aug = [[F(x) for x in row] + [F(1) if i == j else F(0) for j in range(n)] for i, row in enumerate(a)]
    for col in range(n):
        piv = next((r for r in range(col, n) if aug[r][col] != 0), None)
        if piv is None:
            raise ValueError("singular matrix")
        aug[col], aug[piv] = aug[piv], aug[col]
        pv = aug[col][col]
        aug[col] = [x / pv for x in aug[col]]
        for r in range(n):
            if r != col and aug[r][col] != 0:
                f = aug[r][col]
                aug[r] = [x - f * y for x, y in zip(aug[r], aug[col])]
    return [row[n:] for row in aug]


def nullspace(a: list[list[Any]]) -> list[list[F]]:
    """Exact rational basis of ker(a) via reduced row echelon form."""
    rows = [[F(x) for x in row] for row in a]
    m, n = len(rows), len(rows[0])
    pivots: list[int] = []
    r = 0
    for col in range(n):
        piv = next((i for i in range(r, m) if rows[i][col] != 0), None)
        if piv is None:
            continue
        rows[r], rows[piv] = rows[piv], rows[r]
        pv = rows[r][col]
        rows[r] = [x / pv for x in rows[r]]
        for i in range(m):
            if i != r and rows[i][col] != 0:
                f = rows[i][col]
                rows[i] = [x - f * y for x, y in zip(rows[i], rows[r])]
        pivots.append(col)
        r += 1
        if r == m:
            break
    free = [c for c in range(n) if c not in pivots]
    basis: list[list[F]] = []
    for fc in free:
        vec = [F(0)] * n
        vec[fc] = F(1)
        for i, pc in enumerate(pivots):
            vec[pc] = -rows[i][fc]
        basis.append(vec)
    return basis


def exact_div(a: Any, k: int) -> Any:
    if isinstance(a, int) and a % k == 0:
        return a // k
    return F(a) / k


def charpoly(m: list[list[Any]]) -> list[Any]:
    """Faddeev-LeVerrier: coefficients of det(xI - M), lowest degree first."""
    n = len(m)
    c: list[Any] = [0] * (n + 1)
    c[n] = 1
    mk: list[list[Any]] = [[0] * n for _ in range(n)]
    for k in range(1, n + 1):
        prod = matmul(m, mk)
        mk = [[prod[i][j] + (c[n - k + 1] if i == j else 0) for j in range(n)] for i in range(n)]
        c[n - k] = exact_div(-trace(matmul(m, mk)), k)
    return c


# ---------------------------------------------------------------------------
# Exact polynomial arithmetic and Sturm root counting (lowest degree first)
# ---------------------------------------------------------------------------


def ptrim(p: Iterable[Any]) -> list[F]:
    out = [F(x) for x in p]
    while len(out) > 1 and out[-1] == 0:
        out.pop()
    return out


def pmul(p: list[Any], q: list[Any]) -> list[F]:
    out = [F(0)] * (len(p) + len(q) - 1)
    for i, a in enumerate(p):
        if a == 0:
            continue
        for j, b in enumerate(q):
            out[i + j] += a * b
    return ptrim(out)


def peval(p: list[Any], x: Any) -> F:
    acc = F(0)
    for coef in reversed(p):
        acc = acc * x + coef
    return acc


def pdivmod(a: list[Any], b: list[Any]) -> tuple[list[F], list[F]]:
    a = ptrim(a)
    b = ptrim(b)
    if b == [0]:
        raise ZeroDivisionError("polynomial division by zero")
    q = [F(0)] * max(1, len(a) - len(b) + 1)
    r = list(a)
    while len(r) >= len(b) and r != [0]:
        shift = len(r) - len(b)
        f = r[-1] / b[-1]
        q[shift] = f
        for i, coef in enumerate(b):
            r[i + shift] -= f * coef
        r = ptrim(r)
        if len(r) < len(b):
            break
    return ptrim(q), ptrim(r)


def pderiv(p: list[Any]) -> list[F]:
    if len(p) <= 1:
        return [F(0)]
    return ptrim([i * p[i] for i in range(1, len(p))])


def sturm_chain(p: list[Any]) -> list[list[F]]:
    p0 = ptrim(p)
    chain = [p0, pderiv(p0)]
    while chain[-1] != [0]:
        _, rem = pdivmod(chain[-2], chain[-1])
        rem = ptrim([-x for x in rem])
        if rem == [0]:
            break
        chain.append(rem)
    return [q for q in chain if q != [0]]


def sign(x: Any) -> int:
    return (x > 0) - (x < 0)


def sign_changes(chain: list[list[F]], x: Any) -> int:
    signs = [s for s in (sign(peval(q, x)) for q in chain) if s != 0]
    return sum(1 for a, b in zip(signs, signs[1:]) if a != b)


def count_distinct_roots(p: list[Any], lo: Any, hi: Any) -> int:
    """Distinct real roots in (lo, hi]; caller guarantees p(lo) != 0 and p(hi) != 0."""
    chain = sturm_chain(p)
    return sign_changes(chain, lo) - sign_changes(chain, hi)


def cauchy_bound(p: list[Any]) -> F:
    q = ptrim(p)
    if len(q) == 1:
        return F(1)
    lead = q[-1]
    return 1 + max(abs(c / lead) for c in q[:-1])


def poly_pow_linear(root: Any, k: int) -> list[F]:
    out = [F(1)]
    for _ in range(k):
        out = pmul(out, [F(-root), F(1)])
    return out


# ---------------------------------------------------------------------------
# Portal 2: reaction-diffusion on graphs
# ---------------------------------------------------------------------------

J_RD = frac_matrix([[7, 15], [F(-21, 2), -10]])
D_RD = diag([1, 10])
BAND_LO = F(5, 2)
BAND_HI = F(7, 2)


def cycle_laplacian(n: int) -> list[list[int]]:
    lap = [[0] * n for _ in range(n)]
    for i in range(n):
        lap[i][i] += 2
        lap[i][(i + 1) % n] -= 1
        lap[i][(i - 1) % n] -= 1
    return lap


def path_laplacian(n: int) -> list[list[int]]:
    lap = [[0] * n for _ in range(n)]
    for i in range(n - 1):
        lap[i][i] += 1
        lap[i + 1][i + 1] += 1
        lap[i][i + 1] -= 1
        lap[i + 1][i] -= 1
    return lap


def complete_laplacian(n: int) -> list[list[int]]:
    return [[(n - 1) if i == j else -1 for j in range(n)] for i in range(n)]


def mode_quadratic(mu: Any) -> list[F]:
    """det(xI - (J - mu D)) lowest degree first."""
    a = matadd(J_RD, D_RD, -F(mu))
    return ptrim([a[0][0] * a[1][1] - a[0][1] * a[1][0], -(a[0][0] + a[1][1]), 1])


def dispersion_det(mu: Any) -> F:
    a = matadd(J_RD, D_RD, -F(mu))
    return a[0][0] * a[1][1] - a[0][1] * a[1][0]


def portal2(ck: Checker) -> dict[str, Any]:
    tr_j = J_RD[0][0] + J_RD[1][1]
    det_j = J_RD[0][0] * J_RD[1][1] - J_RD[0][1] * J_RD[1][0]
    du, dv = D_RD[0][0], D_RD[1][1]
    ck.check("P2.reaction_stable_trJ_neg_detJ_pos", tr_j < 0 and det_j > 0, f"trJ={tr_j} detJ={det_j}")

    # Equal-diffusion obstruction: det(J - mu d I) = d^2 mu^2 - d trJ mu + detJ has positive coefficients.
    # Positive coefficients certify det > 0 for every mu >= 0; trace(J - mu d I) = trJ - 2 mu d < 0 too.
    eq_ok = True
    for d in (F(1, 10), F(1), F(10)):
        coeffs = [det_j, -d * tr_j, d * d]
        eq_ok = eq_ok and all(c > 0 for c in coeffs)
        for n in (3, 4, 6, 12):
            for mu in sorted({2 - 2 * x for x in (F(0), F(1, 2), F(-1, 2), F(-1))}):
                eq_ok = eq_ok and peval(ptrim(coeffs), mu) > 0
            block = matadd(kron(eye(n), J_RD), kron(frac_matrix(cycle_laplacian(n)), matscale(eye(2), d)), -1)
            cp = charpoly(block)
            eq_ok = eq_ok and peval(cp, 0) != 0 and count_distinct_roots(cp, F(0), cauchy_bound(cp)) == 0
    ck.check(
        "P2.equal_diffusion_obstruction_certificate",
        eq_ok,
        "positive-coefficient certificate + 0 positive real eigs of I(x)J - d L(x)I on C_3,C_4,C_6,C_12 for d in {1/10,1,10}",
    )

    # Necessary Turing conditions and the exact band.
    lin = dv * J_RD[0][0] + du * J_RD[1][1]
    disc = lin * lin - 4 * du * dv * det_j
    ck.check("P2.turing_band_nonempty", lin > 0 and disc > 0, f"dv*j11+du*j22={lin} disc={disc}")
    ck.check("P2.activator_inhibitor_sign_split", J_RD[0][0] * J_RD[1][1] < 0 and du != dv, "j11*j22<0 and du!=dv")
    disp_mu = ptrim([det_j, -lin, du * dv])
    ck.check(
        "P2.band_endpoints_are_exact_roots",
        peval(disp_mu, BAND_LO) == 0 and peval(disp_mu, BAND_HI) == 0 and dispersion_det(3) < 0,
        f"det(5/2)={peval(disp_mu, BAND_LO)} det(7/2)={peval(disp_mu, BAND_HI)} det(3)={dispersion_det(3)}",
    )

    # Ring aliasing scan via Sturm counts of Laplacian charpolys inside the open band.
    ring_unstable: list[int] = []
    ring_stable: list[int] = []
    endpoints_clean = True
    ring_polys: dict[int, list[Any]] = {}
    for n in range(3, 17):
        lp = charpoly(cycle_laplacian(n))
        ring_polys[n] = lp
        endpoints_clean = endpoints_clean and peval(lp, BAND_LO) != 0 and peval(lp, BAND_HI) != 0
        hits = count_distinct_roots(lp, BAND_LO, BAND_HI)
        (ring_unstable if hits > 0 else ring_stable).append(n)
    ck.check("P2.ring_band_endpoints_not_eigenvalues", endpoints_clean, "Niven: cos(theta) in {-1/4,-3/4} never rational-angle")
    expected_unstable = [3, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    ck.check(
        "P2.ring_aliasing_matches_hand_derivation",
        ring_unstable == expected_unstable and ring_stable == [4, 5, 7],
        f"unstable={ring_unstable} stable={ring_stable}",
    )

    # Paths: P_n spectrum is contained in C_{2n} spectrum (exact divisibility) and band hits agree.
    path_unstable: list[int] = []
    path_stable: list[int] = []
    divis_ok = True
    for n in range(2, 9):
        pp = charpoly(path_laplacian(n))
        hits = count_distinct_roots(pp, BAND_LO, BAND_HI)
        (path_unstable if hits > 0 else path_stable).append(n)
        big = ring_polys.get(2 * n) if 2 * n in ring_polys else charpoly(cycle_laplacian(2 * n))
        _, rem = pdivmod(big, pp)
        divis_ok = divis_ok and rem == [0]
        ring_hit = count_distinct_roots(big, BAND_LO, BAND_HI) > 0
        divis_ok = divis_ok and (ring_hit == (hits > 0))
    ck.check("P2.path_spectrum_divides_double_ring", divis_ok, "charpoly(P_n) | charpoly(C_2n) and band hits agree")
    ck.check("P2.path_scan", path_unstable == [3, 4, 5, 6, 7, 8] and path_stable == [2], f"unstable={path_unstable} stable={path_stable}")

    # Full block operator M = I (x) J - L (x) D: factorisation and Sturm count of positive real eigenvalues.
    block_counts: dict[int, int] = {}
    factor_ok = True
    for n in (4, 5, 6):
        lap = frac_matrix(cycle_laplacian(n))
        m_op = matadd(kron(eye(n), J_RD), kron(lap, D_RD), -1)
        cp = charpoly(m_op)
        if n in (4, 6):
            spectrum = {4: [0, 2, 2, 4], 6: [0, 1, 1, 3, 3, 4]}[n]
            prod = [F(1)]
            for mu in spectrum:
                prod = pmul(prod, mode_quadratic(mu))
            factor_ok = factor_ok and ptrim(cp) == prod
        bound = cauchy_bound(cp)
        factor_ok = factor_ok and peval(cp, 0) != 0
        block_counts[n] = count_distinct_roots(cp, F(0), bound)
    ck.check("P2.block_operator_factorises_per_mode", factor_ok, "charpoly(I(x)J - L(x)D) = prod_k charpoly(J - mu_k D)")
    ck.check(
        "P2.block_operator_unstable_inertia",
        block_counts == {4: 0, 5: 0, 6: 1},
        f"distinct positive real eigenvalues={block_counts}",
    )

    # Complete graph: one nonzero Laplacian eigenvalue => all-or-none differentiation.
    k5 = charpoly(complete_laplacian(5))
    ck.check("P2.complete_graph_charpoly", ptrim(k5) == pmul([F(0), F(1)], poly_pow_linear(5, 4)), f"charpoly(K5)={k5}")
    nonzero_distinct = count_distinct_roots(k5, F(1, 2), cauchy_bound(k5))
    ck.check(
        "P2.complete_graph_all_or_none",
        nonzero_distinct == 1 and dispersion_det(5) > 0,
        f"distinct nonzero mu={nonzero_distinct} det(J-5D)={dispersion_det(5)}",
    )
    return {
        "J": [[str(x) for x in row] for row in J_RD],
        "D": [str(du), str(dv)],
        "band": [str(BAND_LO), str(BAND_HI)],
        "ring_unstable": ring_unstable,
        "ring_stable": ring_stable,
        "path_unstable": path_unstable,
        "block_positive_eigs": block_counts,
    }


# ---------------------------------------------------------------------------
# Portal 3: central-difference curl on a periodic n^3 lattice (sparse ints)
# ---------------------------------------------------------------------------

Sparse = dict[int, dict[int, int]]


def sp_add(m: Sparse, i: int, j: int, v: int) -> None:
    row = m.setdefault(i, {})
    nv = row.get(j, 0) + v
    if nv == 0:
        row.pop(j, None)
        if not row:
            m.pop(i, None)
    else:
        row[j] = nv


def sp_clean(m: Sparse) -> Sparse:
    return {i: {j: v for j, v in row.items() if v != 0} for i, row in m.items() if any(v != 0 for v in row.values())}


def sp_eq(a: Sparse, b: Sparse) -> bool:
    return sp_clean(a) == sp_clean(b)


def sp_transpose(m: Sparse) -> Sparse:
    out: Sparse = {}
    for i, row in m.items():
        for j, v in row.items():
            sp_add(out, j, i, v)
    return out


def sp_mm(a: Sparse, b: Sparse) -> Sparse:
    out: Sparse = {}
    for i, row in a.items():
        acc: dict[int, int] = {}
        for k, av in row.items():
            for j, bv in b.get(k, {}).items():
                acc[j] = acc.get(j, 0) + av * bv
        acc = {j: v for j, v in acc.items() if v != 0}
        if acc:
            out[i] = acc
    return out


def sp_neg(m: Sparse) -> Sparse:
    return {i: {j: -v for j, v in row.items()} for i, row in m.items()}


def sp_mv(m: Sparse, v: list[Any], nrows: int) -> list[Any]:
    return [sum((a * v[j] for j, a in m.get(i, {}).items()), 0) for i in range(nrows)]


class Lattice:
    def __init__(self, n: int) -> None:
        self.n = n
        self.nn = n ** 3
        self.dim = 3 * self.nn

    def site(self, x: int, y: int, z: int) -> int:
        n = self.n
        return ((x % n) * n + (y % n)) * n + (z % n)

    def coords(self, s: int) -> tuple[int, int, int]:
        n = self.n
        return s // (n * n), (s // n) % n, s % n

    def idx(self, comp: int, s: int) -> int:
        return comp * self.nn + s

    def shift(self, s: int, axis: int, step: int) -> int:
        x, y, z = self.coords(s)
        c = [x, y, z]
        c[axis] += step
        return self.site(*c)

    def curl2(self) -> Sparse:
        """2*C for the central-difference curl (integer entries)."""
        m: Sparse = {}
        # (comp_out, [(comp_in, axis, sign)]): comp_out row = sum sign * D_axis v_comp_in
        terms = {
            0: [(1, 2, -1), (2, 1, +1)],
            1: [(0, 2, +1), (2, 0, -1)],
            2: [(0, 1, -1), (1, 0, +1)],
        }
        for co, lst in terms.items():
            for s in range(self.nn):
                r = self.idx(co, s)
                for ci, axis, sg in lst:
                    sp_add(m, r, self.idx(ci, self.shift(s, axis, +1)), sg)
                    sp_add(m, r, self.idx(ci, self.shift(s, axis, -1)), -sg)
        return m

    def grad2(self) -> Sparse:
        """2*grad: (3 nn) x nn."""
        m: Sparse = {}
        for axis in range(3):
            for s in range(self.nn):
                r = self.idx(axis, s)
                sp_add(m, r, self.shift(s, axis, +1), 1)
                sp_add(m, r, self.shift(s, axis, -1), -1)
        return m

    def div2(self) -> Sparse:
        """2*div: nn x (3 nn)."""
        m: Sparse = {}
        for s in range(self.nn):
            for axis in range(3):
                sp_add(m, s, self.idx(axis, self.shift(s, axis, +1)), 1)
                sp_add(m, s, self.idx(axis, self.shift(s, axis, -1)), -1)
        return m

    def parity(self) -> Sparse:
        """Point reflection p -> -p acting on polar vector fields: (Pv)_c(p) = -v_c(-p)."""
        m: Sparse = {}
        for c in range(3):
            for s in range(self.nn):
                x, y, z = self.coords(s)
                sp_add(m, self.idx(c, s), self.idx(c, self.site(-x, -y, -z)), -1)
        return m

    def scalar_reflection(self) -> Sparse:
        """(R f)(p) = f(-p) on scalar fields."""
        m: Sparse = {}
        for s in range(self.nn):
            x, y, z = self.coords(s)
            sp_add(m, s, self.site(-x, -y, -z), 1)
        return m

    def translation_x(self) -> Sparse:
        m: Sparse = {}
        for c in range(3):
            for s in range(self.nn):
                sp_add(m, self.idx(c, s), self.idx(c, self.shift(s, 0, +1)), 1)
        return m

    def kernel_generators(self) -> list[dict[int, int]]:
        gens: list[dict[int, int]] = []
        g2t = sp_transpose(self.grad2())
        for s in range(self.nn):
            col = g2t.get(s, {})
            if col:
                gens.append(dict(col))
        n = self.n
        if n % 2 == 0:
            for c in range(3):
                for a in range(8):
                    ax, ay, az = (a >> 2) & 1, (a >> 1) & 1, a & 1
                    vec = {
                        self.idx(c, s): 1
                        for s in range(self.nn)
                        if tuple(t % 2 for t in self.coords(s)) == (ax, ay, az)
                    }
                    gens.append(vec)
        else:
            for c in range(3):
                gens.append({self.idx(c, s): 1 for s in range(self.nn)})
        return gens


PRIME = 1_000_000_007


def rank_mod_p(rows: list[list[int]], ncols: int, p: int = PRIME) -> int:
    work = [[x % p for x in r] for r in rows]
    rank = 0
    nrows = len(work)
    for col in range(ncols):
        piv = next((i for i in range(rank, nrows) if work[i][col]), None)
        if piv is None:
            continue
        work[rank], work[piv] = work[piv], work[rank]
        pr = work[rank]
        inv = pow(pr[col], p - 2, p)
        tail = [(x * inv) % p for x in pr[col:]]
        pr[col:] = tail
        for i in range(rank + 1, nrows):
            f = work[i][col]
            if f:
                ri = work[i]
                ri[col:] = [(a - f * b) % p for a, b in zip(ri[col:], tail)]
        rank += 1
        if rank == nrows:
            break
    return rank


def sparse_rows_dense(m: Sparse, nrows: int, ncols: int) -> list[list[int]]:
    out = []
    for i in range(nrows):
        row = [0] * ncols
        for j, v in m.get(i, {}).items():
            row[j] = v
        out.append(row)
    return out


def sp_solve(a: dict[int, dict[int, F]], b: list[F], n: int) -> list[F]:
    rows = [dict(a.get(i, {})) for i in range(n)]
    rhs = list(b)
    for col in range(n):
        piv = next((i for i in range(col, n) if rows[i].get(col, 0) != 0), None)
        if piv is None:
            raise ValueError("singular sparse system")
        rows[col], rows[piv] = rows[piv], rows[col]
        rhs[col], rhs[piv] = rhs[piv], rhs[col]
        pr = rows[col]
        pv = pr[col]
        for i in range(col + 1, n):
            f = rows[i].get(col)
            if f:
                fac = f / pv
                ri = rows[i]
                for j, av in pr.items():
                    nv = ri.get(j, 0) - fac * av
                    if nv == 0:
                        ri.pop(j, None)
                    else:
                        ri[j] = nv
                rhs[i] -= fac * rhs[col]
    x = [F(0)] * n
    for i in range(n - 1, -1, -1):
        acc = rhs[i] - sum((av * x[j] for j, av in rows[i].items() if j > i), F(0))
        x[i] = acc / rows[i][i]
    return x


def cayley_step(k: Sparse, v: list[F], n: int, h: F) -> list[F]:
    """Solve (I - h K) v1 = (I + h K) v0 exactly."""
    lhs: dict[int, dict[int, F]] = {i: {i: F(1)} for i in range(n)}
    for i, row in k.items():
        for j, val in row.items():
            lhs[i][j] = lhs[i].get(j, F(0)) - h * val
            if lhs[i][j] == 0:
                del lhs[i][j]
    kv = sp_mv(k, v, n)
    rhs = [v[i] + h * kv[i] for i in range(n)]
    return sp_solve(lhs, rhs, n)


def moments(c2: Sparse, v: list[F], n: int, jmax: int = 4) -> list[F]:
    out = []
    w = list(v)
    for j in range(jmax + 1):
        out.append(dot(v, w) / (2 ** j))
        if j < jmax:
            w = sp_mv(c2, w, n)
    return out


def portal3(ck: Checker) -> dict[str, Any]:
    summary: dict[str, Any] = {"rank": {}, "kernel": {}, "spurious_kernel": {}}
    for n in (2, 3, 4):
        lat = Lattice(n)
        c2 = lat.curl2()
        z = (1 if n % 2 else 2) ** 3
        expected_rank = 2 * (lat.nn - z)
        if n == 2:
            ck.check("P3.n2_curl_identically_zero", sp_clean(c2) == {}, "D f(x)=f(x+1)-f(x-1)=0 when x+1=x-1 mod 2")
            summary["rank"][n] = 0
            summary["kernel"][n] = lat.dim
            summary["spurious_kernel"][n] = 3 * z - 3
            continue
        ck.check(f"P3.n{n}_curl_symmetric", sp_eq(c2, sp_transpose(c2)), "C^T = C")
        ck.check(f"P3.n{n}_div_curl_zero", sp_clean(sp_mm(lat.div2(), c2)) == {}, "div C = 0")
        ck.check(f"P3.n{n}_curl_grad_zero", sp_clean(sp_mm(c2, lat.grad2())) == {}, "C grad = 0")
        par = lat.parity()
        ck.check(
            f"P3.n{n}_parity_anticommutes",
            sp_eq(sp_mm(sp_mm(par, c2), par), sp_neg(c2)) and sp_clean(sp_mm(par, par)) == {i: {i: 1} for i in range(lat.dim)},
            "P^2 = I and P C P = -C",
        )
        ck.check(
            f"P3.n{n}_parity_is_polar_vector_reflection",
            sp_eq(sp_mm(par, lat.grad2()), sp_mm(lat.grad2(), lat.scalar_reflection())),
            "P grad = grad R (P acts on gradients as a polar-vector point reflection)",
        )
        rank_lo = rank_mod_p(sparse_rows_dense(c2, lat.dim, lat.dim), lat.dim)
        gens = lat.kernel_generators()
        gen_ok = all(all(v == 0 for v in sp_mv(c2, [g.get(i, 0) for i in range(lat.dim)], lat.dim)) for g in gens)
        gen_rank = rank_mod_p([[g.get(i, 0) for i in range(lat.dim)] for g in gens], lat.dim)
        ck.check(
            f"P3.n{n}_exact_rank",
            gen_ok and rank_lo == expected_rank and lat.dim - gen_rank == expected_rank,
            f"rank_p(C)={rank_lo} >= ... <= dim-rank_p(kernel gens)={lat.dim - gen_rank}; formula={expected_rank}",
        )
        summary["rank"][n] = rank_lo
        summary["kernel"][n] = lat.dim - rank_lo
        summary["spurious_kernel"][n] = (lat.dim - rank_lo) - (lat.nn - z) - 3
        ck.check(f"P3.n{n}_spurious_kernel_formula", summary["spurious_kernel"][n] == 3 * z - 3, f"spurious={summary['spurious_kernel'][n]}")

    # Transport experiments on n = 3.
    lat = Lattice(3)
    c2 = lat.curl2()
    dim = lat.dim
    tx = lat.translation_x()
    k_comm = sp_clean({i: dict(row) for i, row in tx.items()})
    for i, row in sp_transpose(tx).items():
        for j, v in row.items():
            sp_add(k_comm, i, j, -v)
    ck.check("P3.K_commuting_is_skew", sp_eq(sp_transpose(k_comm), sp_neg(k_comm)), "K^T = -K")
    ck.check("P3.K_commutes_with_curl", sp_eq(sp_mm(c2, k_comm), sp_mm(k_comm, c2)), "[C, K] = 0")

    v0 = [F(((i * 7 + 3) % 11) - 5, 1 + (i % 3)) for i in range(dim)]
    m0 = moments(c2, v0, dim)
    v = v0
    conserve_ok = True
    for _ in range(3):
        v = cayley_step(k_comm, v, dim, F(1, 2))
        conserve_ok = conserve_ok and moments(c2, v, dim) == m0
    ck.check("P3.cayley_commuting_conserves_all_moments", conserve_ok and v != v0, f"m_0..m_4={[str(x) for x in m0]}")

    # Non-commuting skew: single-site x<->y component rotation.
    drift_site = None
    drift_detail = ""
    for site in range(lat.nn):
        kp: Sparse = {}
        sp_add(kp, lat.idx(0, site), lat.idx(1, site), -1)
        sp_add(kp, lat.idx(1, site), lat.idx(0, site), 1)
        if sp_eq(sp_mm(c2, kp), sp_mm(kp, c2)):
            continue
        v1 = cayley_step(kp, v0, dim, F(1, 2))
        mm1 = moments(c2, v1, dim, 1)
        if mm1[0] == m0[0] and mm1[1] != m0[1]:
            drift_site = site
            drift_detail = f"site={site} E={mm1[0]} H0={m0[1]} H1={mm1[1]}"
            break
    ck.check("P3.noncommuting_skew_conserves_E_drifts_H", drift_site is not None, drift_detail)

    # Symmetric (non-orthogonal) residual I + C/4: helicity Rayleigh quotient strictly increases.
    v = v0
    quotients = []
    for _ in range(5):
        mm_ = moments(c2, v, dim, 2)
        quotients.append(mm_[1] / mm_[0])
        cv = sp_mv(c2, v, dim)
        v = [v[i] + cv[i] / 8 for i in range(dim)]
    strictly_up = all(b > a for a, b in zip(quotients, quotients[1:]))
    ck.check("P3.symmetric_residual_helicity_collapse_drift", strictly_up, f"R_t={[str(q) for q in quotients[:3]]}...")
    summary["moments_v0"] = [str(x) for x in m0]
    summary["noncommuting_drift_site"] = drift_site
    return summary


# ---------------------------------------------------------------------------
# Portal 5: Darboux pairs, dark modes, lapse inertia, Hopf fibre
# ---------------------------------------------------------------------------


def cayley_orthogonal(s: list[list[F]]) -> list[list[F]]:
    n = len(s)
    return matmul(inverse(matadd(eye(n), s, -1)), matadd(eye(n), s, 1))


def inertia(p: list[Any]) -> tuple[int, int, int]:
    b = cauchy_bound(p)
    zero_mult = 0
    q = ptrim(p)
    while q[0] == 0:
        q = q[1:]
        zero_mult += 1
    return count_distinct_roots(q, F(0), b), count_distinct_roots(q, -b, F(0)), zero_mult


def qmul(a: tuple[F, ...], b: tuple[F, ...]) -> tuple[F, F, F, F]:
    a0, a1, a2, a3 = a
    b0, b1, b2, b3 = b
    return (
        a0 * b0 - a1 * b1 - a2 * b2 - a3 * b3,
        a0 * b1 + a1 * b0 + a2 * b3 - a3 * b2,
        a0 * b2 - a1 * b3 + a2 * b0 + a3 * b1,
        a0 * b3 + a1 * b2 - a2 * b1 + a3 * b0,
    )


def qconj(a: tuple[F, ...]) -> tuple[F, F, F, F]:
    return (a[0], -a[1], -a[2], -a[3])


def hopf(q: tuple[F, ...]) -> tuple[F, F, F, F]:
    return qmul(qmul(q, (F(0), F(1), F(0), F(0))), qconj(q))


def left_mult_matrix(q: tuple[F, ...]) -> list[list[F]]:
    a, b, c, d = q
    return [[a, -b, -c, -d], [b, a, -d, c], [c, d, a, -b], [d, -c, b, a]]


def portal5(ck: Checker) -> dict[str, Any]:
    s3 = frac_matrix([[0, 1, 2], [-1, 0, F(1, 2)], [-2, F(-1, 2), 0]])
    s5 = frac_matrix(
        [
            [0, 1, 0, 2, F(1, 3)],
            [-1, 0, 1, 0, F(1, 2)],
            [0, -1, 0, F(2, 3), 1],
            [-2, 0, F(-2, 3), 0, 1],
            [F(-1, 3), F(-1, 2), -1, -1, 0],
        ]
    )
    ck.check("P5.generators_skew", mat_eq(transpose(s3), matscale(s3, -1)) and mat_eq(transpose(s5), matscale(s5, -1)), "S^T=-S")
    u = cayley_orthogonal(s3)
    v = cayley_orthogonal(s5)
    ck.check("P5.rational_orthogonal_U_V", mat_eq(matmul(transpose(u), u), eye(3)) and mat_eq(matmul(transpose(v), v), eye(5)), "U^TU=I, V^TV=I")
    sigma = [F(2), F(3, 2), F(1, 3)]
    sig = [[sigma[i] if i == j else F(0) for j in range(5)] for i in range(3)]
    a = matmul(matmul(u, sig), transpose(v))
    c = F(1, 7)
    l1 = matadd(matmul(transpose(a), a), eye(5), c)
    l2 = matadd(matmul(a, transpose(a)), eye(3), c)
    ck.check("P5.darboux_intertwining", mat_eq(matmul(a, l1), matmul(l2, a)), "A L1 = L2 A")
    cp1 = ptrim(charpoly(l1))
    cp2 = ptrim(charpoly(l2))
    ck.check("P5.charpoly_identity", cp1 == pmul(poly_pow_linear(c, 2), cp2), "charpoly(L1) = (x-c)^2 charpoly(L2)")

    vcols = transpose(v)
    transport_ok = True
    for i in range(3):
        lam = sigma[i] ** 2 + c
        vi = vcols[i]
        avi = matvec(a, vi)
        transport_ok = transport_ok and matvec(l1, vi) == [lam * x for x in vi]
        transport_ok = transport_ok and matvec(l2, avi) == [lam * x for x in avi]
        transport_ok = transport_ok and dot(avi, avi) == (lam - c) * dot(vi, vi)
        back = [x / (lam - c) for x in matvec(transpose(a), avi)]
        transport_ok = transport_ok and back == vi
    ck.check("P5.eigenvector_transport_and_inverse", transport_ok, "L2 (A v) = lam A v, |Av|^2=(lam-c)|v|^2, v = A^T A v/(lam-c)")

    dark_ok = True
    for i in (3, 4):
        vi = vcols[i]
        dark_ok = dark_ok and all(x == 0 for x in matvec(a, vi)) and matvec(l1, vi) == [c * x for x in vi]
    dark_ok = dark_ok and peval(cp2, c) != 0
    ker = nullspace(a)
    dark_ok = dark_ok and len(ker) == 2
    x = [F(1), F(-2), F(3), F(1, 2), F(5)]
    x_shift = [xi + ki for xi, ki in zip(x, ker[0])]
    collision = matvec(a, x) == matvec(a, x_shift) and x != x_shift
    ck.check("P5.dark_modes_and_collision", dark_ok and collision, "A v_3 = A v_4 = 0, c not in spec(L2), A x = A(x + k)")

    aat_inv = inverse(matmul(a, transpose(a)))
    proj = matmul(matmul(transpose(a), aat_inv), a)
    loss = dot(matadd([x], [matvec(proj, x)], -1)[0], matadd([x], [matvec(proj, x)], -1)[0])
    loss_expected = sum((dot(vcols[i], x) ** 2 for i in (3, 4)), F(0))
    ck.check(
        "P5.reconstruction_projector",
        mat_eq(matmul(proj, proj), proj) and mat_eq(transpose(proj), proj) and trace(proj) == 3 and loss == loss_expected,
        f"R^2=R=R^T tr=3 loss={loss}",
    )

    # Square singular discrete SUSY pair: isospectral, distinct potentials, non-transportable dark modes.
    w = [F(1, 2), F(2), F(-1), F(3, 2), F(0)]
    n = len(w)
    asq = [[(-w[i] if i == j else (F(1) if j == i + 1 else F(0))) for j in range(n)] for i in range(n)]
    s1 = matmul(transpose(asq), asq)
    s2 = matmul(asq, transpose(asq))
    tri_ok = all(s1[i][j] == 0 and s2[i][j] == 0 for i in range(n) for j in range(n) if abs(i - j) > 1)
    k1 = nullspace(asq)
    k2 = nullspace(transpose(asq))
    nonparallel = len(k1) == 1 and len(k2) == 1 and nullspace(transpose([k1[0], k2[0]])) == []
    ck.check(
        "P5.susy_square_isospectral_not_lossless",
        ptrim(charpoly(s1)) == ptrim(charpoly(s2))
        and [s1[i][i] for i in range(n)] != [s2[i][i] for i in range(n)]
        and tri_ok
        and nonparallel,
        f"diag(L1)={[str(s1[i][i]) for i in range(n)]} diag(L2)={[str(s2[i][i]) for i in range(n)]} kerA={[str(t) for t in k1[0]]} kerA^T={[str(t) for t in k2[0]]}",
    )

    # Lapse: N L preserves inertia (Sylvester) but not the spectrum.
    lsym = matadd(matmul(a, transpose(a)), eye(3), F(-3))
    lapse = diag([2, F(1, 3), 5])
    cpl = ptrim(charpoly(lsym))
    cpn = ptrim(charpoly(matmul(lapse, lsym)))
    in_l = inertia(cpl)
    in_n = inertia(cpn)
    ck.check("P5.lapse_preserves_inertia_not_spectrum", cpl != cpn and in_l == in_n == (1, 2, 0), f"inertia={in_l}/{in_n}")

    # Hopf: isometric left multiplication; exact S^1 dark fibre of the Hopf map.
    q = (F(1), F(2), F(-1), F(1, 2))
    nq = sum((t * t for t in q), F(0))
    lq = left_mult_matrix(q)
    basis = [tuple(F(1) if i == j else F(0) for j in range(4)) for i in range(4)]
    lm_ok = all(matvec(lq, list(b)) == list(qmul(q, b)) for b in basis)
    ck.check("P5.quaternion_left_mult_isometric", lm_ok and mat_eq(matmul(transpose(lq), lq), matscale(eye(4), nq)), f"|q|^2={nq}")
    hq = hopf(q)
    fibre_ok = hq[0] == 0 and sum((t * t for t in hq[1:]), F(0)) == nq * nq
    for uu in ((F(3, 5), F(4, 5)), (F(5, 13), F(12, 13)), (F(8, 17), F(15, 17))):
        fibre_ok = fibre_ok and hopf(qmul(q, (uu[0], uu[1], F(0), F(0)))) == hq
    off_fibre = hopf(qmul(q, (F(3, 5), F(0), F(4, 5), F(0)))) != hq
    ck.check("P5.hopf_S1_dark_fibre", fibre_ok and off_fibre, f"h(q)={[str(t) for t in hq[1:]]}")
    return {
        "sigma": [str(s) for s in sigma],
        "c": str(c),
        "dark_dim": len(ker),
        "reconstruction_loss_x": str(loss),
        "lapse_inertia": list(in_l),
        "hopf_q": [str(t) for t in hq[1:]],
    }


def main() -> int:
    ck = Checker()
    summary = {"portal2": portal2(ck), "portal3": portal3(ck), "portal5": portal5(ck)}
    for r in ck.results:
        print(f"[{'PASS' if r['ok'] else 'FAIL'}] {r['name']} :: {r['detail']}")
    receipt = {
        "checks_total": len(ck.results),
        "checks_passed": len(ck.results) - len(ck.failures),
        "failed": [r["name"] for r in ck.failures],
        "summary": summary,
    }
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"), default=str)
    receipt["receipt_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":"), default=str))
    return 0 if not ck.failures else 1


if __name__ == "__main__":
    sys.exit(main())
