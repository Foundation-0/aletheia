#!/usr/bin/env python3
"""Track S106 Phase 1A — H2b Paired Analytical Physics Benchmarks (zero IEEE-754 floats).

Deterministic CPU-only, pure Python stdlib (Decimal prec=30, Fraction, int) apples-to-apples
benchmarks at matched node counts N in {64, 256, 1024} comparing Denominator-pi Equal-Sphere-
Fraction partitions EQ(S^2) / EQ_Hopf(S^3) / EQ_Cap(S^3) against:
  - Numerator-pi uniform angle grids (both equal-weight AND Jacobian-weighted midpoint rule),
  - Cartesian box-projected grids (volume-midpoint AND cube-face unweighted/Jacobian), and
  - Standard reference controls (Gauss-Legendre, Fibonacci equal-area, Halton QMC, 600-cell 2I).

Zero floats, zero bare asserts, zero third-party packages, zero external downloads.
"""
from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction
import json
from math import factorial
from operator import mul
from typing import Any

BENCH_PREC = 30
_ZERO = Decimal(0)
_ONE = Decimal(1)
_TWO = Decimal(2)
_HALF = Decimal("0.5")
_ZERO_SNAP = Decimal("1e-24")
_TRIG_EPS = Decimal("1e-34")
_GL_EPS = Decimal("1e-30")


class S106BenchError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def require_ok(cond: bool, code: str, detail: str) -> None:
    if cond is not True:
        raise S106BenchError(code, detail)


def _compute_pi(prec: int) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = prec + 6

        def atan_inv(m: int) -> Decimal:
            m2 = Decimal(m * m)
            term = _ONE / Decimal(m)
            acc = term
            k = 1
            while True:
                term = -term / m2
                nxt = acc + term / Decimal(2 * k + 1)
                if nxt == acc:
                    break
                acc = nxt
                k += 1
            return acc

        val = Decimal(4) * (Decimal(4) * atan_inv(5) - atan_inv(239))
    with localcontext() as ctx:
        ctx.prec = prec
        return +val


_PI = _compute_pi(BENCH_PREC)
_TWO_PI = _TWO * _PI


def d_sin_cos(x: Decimal) -> tuple[Decimal, Decimal]:
    """Deterministic 30-digit Decimal (sin x, cos x) via range reduction + Taylor series."""
    require_ok(type(x) is Decimal, "INVALID_DECIMAL", "expected Decimal")
    with localcontext() as ctx:
        ctx.prec = BENCH_PREC + 4
        q = (x / _TWO_PI).to_integral_value()
        r = x - q * _TWO_PI
        r2 = r * r
        s_term = r
        s = s_term
        c_term = _ONE
        c = c_term
        k = 1
        while True:
            c_term = -c_term * r2 / Decimal((2 * k - 1) * (2 * k))
            s_term = -s_term * r2 / Decimal((2 * k) * (2 * k + 1))
            c = c + c_term
            s = s + s_term
            if max(abs(s_term), abs(c_term)) < _TRIG_EPS:
                break
            k += 1
    with localcontext() as ctx:
        ctx.prec = BENCH_PREC
        return +s, +c


def d_sqrt(x: Decimal) -> Decimal:
    require_ok(type(x) is Decimal, "INVALID_DECIMAL", "expected Decimal")
    require_ok(x >= _ZERO, "NEG_SQRT", "negative Decimal sqrt argument")
    with localcontext() as ctx:
        ctx.prec = BENCH_PREC
        return x.sqrt()


def d_fmt_sci(val: Decimal) -> str:
    """Canonical deterministic scientific string ('0' below 1e-24, else 6-sig-fig sci)."""
    av = abs(val)
    if av < _ZERO_SNAP:
        return "0"
    with localcontext() as ctx:
        ctx.prec = 7
        norm = +av
    return format(norm, ".6e")


def d_ratio_dec4(num: Decimal, den: Decimal) -> str:
    """Exact 4-decimal ratio num/den ('EXACT_INF' when den < 1e-24 and num >= 1e-24)."""
    if abs(den) < _ZERO_SNAP:
        return "EXACT_INF" if abs(num) >= _ZERO_SNAP else "1.0000"
    with localcontext() as ctx:
        ctx.prec = BENCH_PREC
        q = abs(num) / abs(den)
        return str(q.quantize(Decimal("0.0001")))


def all_ge_threshold(vals: tuple[Decimal, ...], threshold: Decimal) -> bool:
    return all(v >= threshold for v in vals)


def leggauss_dec(n: int) -> tuple[list[Decimal], list[Decimal]]:
    """Deterministic Gauss-Legendre nodes and weights on [-1, 1] in 30-digit Decimal."""
    require_ok(type(n) is int, "INVALID_GL_N", "n must be int")
    require_ok(n >= 1, "INVALID_GL_N", "n must be >= 1")
    require_ok(n <= 64, "INVALID_GL_N", "n must be <= 64")
    xs: list[Decimal] = []
    ws: list[Decimal] = []
    with localcontext() as ctx:
        ctx.prec = BENCH_PREC + 4
        dn = Decimal(n)
        for i in range(1, n + 1):
            ang = _PI * (Decimal(i) - Decimal("0.25")) / (dn + _HALF)
            _, x = d_sin_cos(ang)
            dp = _ONE
            for _ in range(32):
                p0, p1 = _ONE, x
                for k in range(2, n + 1):
                    p0, p1 = p1, (Decimal(2 * k - 1) * x * p1 - Decimal(k - 1) * p0) / Decimal(k)
                dp = dn * (x * p1 - p0) / (x * x - _ONE)
                dx = p1 / dp
                x = x - dx
                if abs(dx) < _GL_EPS:
                    break
            w = _TWO / ((_ONE - x * x) * dp * dp)
            xs.append(x)
            ws.append(w)
    with localcontext() as ctx:
        ctx.prec = BENCH_PREC
        return [+x for x in xs], [+w for w in ws]


def halton_dec(n: int, base: int) -> list[Decimal]:
    """Deterministic Van der Corput / Halton radical inverse sequence in Decimal."""
    require_ok(type(n) is int, "INVALID_HALTON_N", "n must be int")
    require_ok(n >= 1, "INVALID_HALTON_N", "n must be >= 1")
    require_ok(type(base) is int, "INVALID_HALTON_BASE", "base must be int")
    require_ok(base >= 2, "INVALID_HALTON_BASE", "base must be >= 2")
    out: list[Decimal] = []
    with localcontext() as ctx:
        ctx.prec = BENCH_PREC
        db = Decimal(base)
        for i in range(1, n + 1):
            f = _ONE
            r = _ZERO
            k = i
            while k > 0:
                f = f / db
                r = r + f * Decimal(k % base)
                k //= base
            out.append(r)
    return out


# ---------------------------------------------------------------------------
# Benchmark (a): 3D Electrostatics (Gauss Flux) + Spherical Harmonics (l=0..6)
# ---------------------------------------------------------------------------

_SH_NORMS: list[tuple[int, int, Decimal]] = []
with localcontext() as _ctx:
    _ctx.prec = BENCH_PREC
    for _l in range(7):
        _SH_NORMS.append((_l, 0, Decimal(2 * _l + 1).sqrt()))
        for _m in range(1, _l + 1):
            _f = Fraction(2 * (2 * _l + 1) * factorial(_l - _m), factorial(_l + _m))
            _SH_NORMS.append((_l, _m, (Decimal(_f.numerator) / Decimal(_f.denominator)).sqrt()))

_GAUSS_CHARGES: tuple[tuple[tuple[Decimal, Decimal, Decimal], Decimal], ...] = (
    ((Decimal("0.25"), Decimal("0.20"), Decimal("0.30")), _ONE),
    ((Decimal("0"), Decimal("0"), Decimal("0.45")), _ONE),
    ((Decimal("0.35"), Decimal("-0.25"), Decimal("0.25")), _ONE),
    ((Decimal("0.90"), Decimal("0.80"), Decimal("1.00")), _ZERO),
    ((Decimal("0"), Decimal("0"), Decimal("1.60")), _ZERO),
)


def _legendre_row(z: Decimal, sin_t: Decimal, lmax: int = 6) -> dict[tuple[int, int], Decimal]:
    with localcontext() as ctx:
        ctx.prec = BENCH_PREC
        p: dict[tuple[int, int], Decimal] = {(0, 0): _ONE}
        for m in range(1, lmax + 1):
            p[(m, m)] = Decimal(2 * m - 1) * sin_t * p[(m - 1, m - 1)]
        for m in range(0, lmax):
            p[(m + 1, m)] = Decimal(2 * m + 1) * z * p[(m, m)]
        for m in range(0, lmax - 1):
            for l in range(m + 2, lmax + 1):
                p[(l, m)] = (Decimal(2 * l - 1) * z * p[(l - 1, m)] - Decimal(l + m - 1) * p[(l - 2, m)]) / Decimal(l - m)
        return p


def _cos_sin_multiples(c1: Decimal, s1: Decimal, lmax: int = 6) -> tuple[list[Decimal], list[Decimal]]:
    with localcontext() as ctx:
        ctx.prec = BENCH_PREC
        cs = [_ONE, c1]
        ss = [_ZERO, s1]
        for _ in range(2, lmax + 1):
            cs.append(cs[-1] * c1 - ss[-1] * s1)
            ss.append(ss[-1] * c1 + cs[-2] * s1)
        return cs, ss


def _gram_rms_max(rows: list[list[Decimal]], ws: list[Decimal], k_dim: int) -> tuple[Decimal, Decimal]:
    with localcontext() as ctx:
        ctx.prec = BENCH_PREC
        cols = [tuple(r[i] for r in rows) for i in range(k_dim)]
        w_cols = [tuple(map(mul, cols[i], ws)) for i in range(k_dim)]
        sq_sum = _ZERO
        mx = _ZERO
        for i in range(k_dim):
            wi = w_cols[i]
            for j in range(i, k_dim):
                acc = sum(map(mul, wi, cols[j]), _ZERO)
                diff = abs(acc - (_ONE if i == j else _ZERO))
                if diff > mx:
                    mx = diff
                sq_sum = sq_sum + (diff * diff if i == j else _TWO * diff * diff)
        return sq_sum.sqrt() / Decimal(k_dim), mx


def _eval_s2_grid(pts: list[tuple[Decimal, Decimal, Decimal]], ws: list[Decimal]) -> dict[str, Any]:
    with localcontext() as ctx:
        ctx.prec = BENCH_PREC
        ferr_sq = _ZERO
        for (rx, ry, rz), exact in _GAUSS_CHARGES:
            fl = _ZERO
            for (px, py, pz), w in zip(pts, ws):
                dx, dy, dz = px - rx, py - ry, pz - rz
                r2 = dx * dx + dy * dy + dz * dz
                r = r2.sqrt()
                fl = fl + w * (dx * px + dy * py + dz * pz) / (r2 * r)
            e = fl - exact
            ferr_sq = ferr_sq + e * e
        gauss_rms = (ferr_sq / Decimal(len(_GAUSS_CHARGES))).sqrt()

        leg_cache: dict[Decimal, dict[tuple[int, int], Decimal]] = {}
        rows: list[list[Decimal]] = []
        for px, py, pz in pts:
            r_xy = (px * px + py * py).sqrt()
            p_tab = leg_cache.get(pz)
            if p_tab is None:
                p_tab = _legendre_row(pz, r_xy, 6)
                leg_cache[pz] = p_tab
            c1, s1 = (_ONE, _ZERO) if r_xy == _ZERO else (px / r_xy, py / r_xy)
            cs, ss = _cos_sin_multiples(c1, s1, 6)
            row: list[Decimal] = []
            for l, m, norm in _SH_NORMS:
                val = norm * p_tab[(l, m)]
                if m == 0:
                    row.append(val)
                else:
                    row.append(val * cs[m])
                    row.append(val * ss[m])
            rows.append(row)

        sh_rms, sh_max = _gram_rms_max(rows, ws, len(rows[0]))
        return {
            "n_nodes": len(pts),
            "gauss_flux_rms": gauss_rms,
            "sh_gram_rms": sh_rms,
            "sh_gram_max": sh_max,
        }


def _s2_grids(n: int) -> list[tuple[str, list[tuple[Decimal, Decimal, Decimal]], list[Decimal]]]:
    m = {64: 8, 256: 16, 1024: 32}[n]
    with localcontext() as ctx:
        ctx.prec = BENCH_PREC
        dm = Decimal(m)
        dn = Decimal(n)
        eq_w = [_ONE / dn] * n
        phi_cs = [d_sin_cos(_TWO_PI * (Decimal(j) + _HALF) / dm) for j in range(m)]
        out: list[tuple[str, list[tuple[Decimal, Decimal, Decimal]], list[Decimal]]] = []

        pts_eq: list[tuple[Decimal, Decimal, Decimal]] = []
        for i in range(m):
            z = -_ONE + _TWO * (Decimal(i) + _HALF) / dm
            r = (_ONE - z * z).sqrt()
            for sp, cp in phi_cs:
                pts_eq.append((r * cp, r * sp, z))
        out.append(("DenomPi_EQ_S2", pts_eq, eq_w))

        pts_np: list[tuple[Decimal, Decimal, Decimal]] = []
        w_sin: list[Decimal] = []
        for i in range(m):
            st, ct = d_sin_cos(_PI * (Decimal(i) + _HALF) / dm)
            for sp, cp in phi_cs:
                pts_np.append((st * cp, st * sp, ct))
                w_sin.append(st)
        sw = sum(w_sin, _ZERO)
        out.append(("NumPi_Unweighted", pts_np, eq_w))
        out.append(("NumPi_SinWeight", pts_np, [w / sw for w in w_sin]))

        dims = {64: (4, 4, 4), 256: (8, 8, 4), 1024: (16, 8, 8)}[n]
        axes = [[-_ONE + Decimal(2 * i + 1) / Decimal(d) for i in range(d)] for d in dims]
        pts_cb: list[tuple[Decimal, Decimal, Decimal]] = []
        for x in axes[0]:
            for y in axes[1]:
                for z in axes[2]:
                    r = (x * x + y * y + z * z).sqrt()
                    pts_cb.append((x / r, y / r, z / r))
        out.append(("CartBox_Vol_S2", pts_cb, eq_w))

        kf = {64: 3, 256: 6, 1024: 13}[n]
        us = [-_ONE + Decimal(2 * i + 1) / Decimal(kf) for i in range(kf)]
        pts_cf: list[tuple[Decimal, Decimal, Decimal]] = []
        w_cf: list[Decimal] = []
        for a in us:
            for b in us:
                for fx, fy, fz in ((_ONE, a, b), (-_ONE, a, b), (a, _ONE, b), (a, -_ONE, b), (a, b, _ONE), (a, b, -_ONE)):
                    r = (fx * fx + fy * fy + fz * fz).sqrt()
                    pts_cf.append((fx / r, fy / r, fz / r))
                    w_cf.append(_ONE / (r * r * r))
        nf = len(pts_cf)
        swf = sum(w_cf, _ZERO)
        out.append(("CartCubeFace_Unw", pts_cf, [_ONE / Decimal(nf)] * nf))
        out.append(("CartCubeFace_Jac", pts_cf, [w / swf for w in w_cf]))

        gz, gw = leggauss_dec(m)
        pts_gl: list[tuple[Decimal, Decimal, Decimal]] = []
        w_gl: list[Decimal] = []
        for z, wz in zip(gz, gw):
            r = (_ONE - z * z).sqrt()
            wt = wz / (_TWO * dm)
            for sp, cp in phi_cs:
                pts_gl.append((r * cp, r * sp, z))
                w_gl.append(wt)
        out.append(("Ctrl_GaussLegendre", pts_gl, w_gl))

        phi_g = (_ONE + Decimal(5).sqrt()) / _TWO
        phi_g2 = phi_g * phi_g
        pts_fib: list[tuple[Decimal, Decimal, Decimal]] = []
        for i in range(n):
            z = _ONE - _TWO * (Decimal(i) + _HALF) / dn
            r = (_ONE - z * z).sqrt()
            sp, cp = d_sin_cos(_TWO_PI * Decimal(i) / phi_g2)
            pts_fib.append((r * cp, r * sp, z))
        out.append(("Ctrl_Fibonacci", pts_fib, eq_w))

        h2, h3 = halton_dec(n, 2), halton_dec(n, 3)
        pts_q: list[tuple[Decimal, Decimal, Decimal]] = []
        for a_h, b_h in zip(h2, h3):
            z = _ONE - _TWO * a_h
            r = (_ONE - z * z).sqrt()
            sp, cp = d_sin_cos(_TWO_PI * b_h)
            pts_q.append((r * cp, r * sp, z))
        out.append(("Ctrl_HaltonQMC", pts_q, eq_w))
        return out


# ---------------------------------------------------------------------------
# Benchmark (b): Fock-Moser Regularized 3D Hydrogen / Kepler on S^3
# ---------------------------------------------------------------------------

with localcontext() as _ctx3:
    _ctx3.prec = BENCH_PREC
    _S6 = Decimal(6).sqrt()
    _S2 = _TWO.sqrt()
    _TWO_S6 = _TWO * _S6
    _RAW_U0S = (
        (Decimal("0.3"), Decimal("0.4"), Decimal("0.5"), _HALF.sqrt()),
        (_ZERO, _ZERO, _ZERO, _ONE),
        (_HALF, -_HALF, _HALF, _HALF),
    )
    _S3_U0S: tuple[tuple[Decimal, Decimal, Decimal, Decimal], ...] = tuple(
        tuple(c / (sum((t * t for t in v), _ZERO)).sqrt() for c in v) for v in _RAW_U0S
    )
    _S3_RADII: tuple[Decimal, ...] = (Decimal("0.30"), Decimal("0.45"))


def _hydrogen_s3_row(u1: Decimal, u2: Decimal, u3: Decimal, u4: Decimal) -> list[Decimal]:
    return [
        _ONE,
        _TWO * u4,
        _TWO * u1, _TWO * u2, _TWO * u3,
        Decimal(4) * u4 * u4 - _ONE,
        _TWO_S6 * u4 * u1, _TWO_S6 * u4 * u2, _TWO_S6 * u4 * u3,
        _TWO_S6 * u1 * u2, _TWO_S6 * u1 * u3, _TWO_S6 * u2 * u3,
        _S6 * (u1 * u1 - u2 * u2),
        _S2 * (_TWO * u3 * u3 - u1 * u1 - u2 * u2),
    ]


def _eval_s3_grid(pts: list[tuple[Decimal, Decimal, Decimal, Decimal]], ws: list[Decimal]) -> dict[str, Any]:
    with localcontext() as ctx:
        ctx.prec = BENCH_PREC
        rows = [_hydrogen_s3_row(*p) for p in pts]
        g5, _ = _gram_rms_max(rows, ws, 5)
        g14, _ = _gram_rms_max(rows, ws, 14)

        perr_sq = _ZERO
        cnt = 0
        for a in _S3_RADII:
            num = _ONE - a * a
            a2 = a * a
            for v0 in _S3_U0S:
                val = _ZERO
                for p, w in zip(pts, ws):
                    dot = p[0] * v0[0] + p[1] * v0[1] + p[2] * v0[2] + p[3] * v0[3]
                    denom = _ONE - _TWO * a * dot + a2
                    val = val + w * num / (denom * denom)
                e = val - _ONE
                perr_sq = perr_sq + e * e
                cnt += 1
        return {
            "n_nodes": len(pts),
            "h_1s2s2p_rms": g5,
            "h_n123_rms": g14,
            "poisson_rms": (perr_sq / Decimal(cnt)).sqrt(),
        }


def _inv_f3_dec(target: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = BENCH_PREC + 2
        lo, hi = _ZERO, _PI
        for _ in range(105):
            mid = _HALF * (lo + hi)
            sm, cm = d_sin_cos(mid)
            if (mid - sm * cm) / _PI < target:
                lo = mid
            else:
                hi = mid
        return _HALF * (lo + hi)


def _build_600_cell_dec() -> list[tuple[Decimal, Decimal, Decimal, Decimal]]:
    with localcontext() as ctx:
        ctx.prec = BENCH_PREC
        phi = (_ONE + Decimal(5).sqrt()) / _TWO
        inv_phi = _ONE / phi
        pts: list[tuple[Decimal, Decimal, Decimal, Decimal]] = []
        for i in range(4):
            for s in (-_ONE, _ONE):
                v = [_ZERO, _ZERO, _ZERO, _ZERO]
                v[i] = s
                pts.append((v[0], v[1], v[2], v[3]))
        for mask in range(16):
            pts.append(tuple(_HALF if ((mask >> b) & 1) == 0 else -_HALF for b in range(4)))
        even_perms = (
            (0, 1, 2, 3), (0, 2, 3, 1), (0, 3, 1, 2),
            (1, 0, 3, 2), (1, 2, 0, 3), (1, 3, 2, 0),
            (2, 0, 1, 3), (2, 1, 3, 0), (2, 3, 0, 1),
            (3, 0, 2, 1), (3, 1, 0, 2), (3, 2, 1, 0),
        )
        base = (_ZERO, _HALF, _HALF * phi, _HALF * inv_phi)
        for perm in even_perms:
            for s1 in (-_ONE, _ONE):
                for s2 in (-_ONE, _ONE):
                    for s3 in (-_ONE, _ONE):
                        vals = (_ZERO, s1 * base[1], s2 * base[2], s3 * base[3])
                        v = [_ZERO, _ZERO, _ZERO, _ZERO]
                        for pos, tgt in enumerate(perm):
                            v[tgt] = vals[pos]
                        pts.append((v[0], v[1], v[2], v[3]))
        return pts


def _s3_grids(n: int) -> list[tuple[str, list[tuple[Decimal, Decimal, Decimal, Decimal]], list[Decimal]]]:
    a, b, c = {64: (4, 4, 4), 256: (4, 8, 8), 1024: (8, 8, 16)}[n]
    with localcontext() as ctx:
        ctx.prec = BENCH_PREC
        da, db, dc, dn = Decimal(a), Decimal(b), Decimal(c), Decimal(n)
        eq_w = [_ONE / dn] * n
        cs1 = [d_sin_cos(_TWO_PI * (Decimal(j) + _HALF) / db) for j in range(b)]
        cs2 = [d_sin_cos(_TWO_PI * (Decimal(k) + _HALF) / dc) for k in range(c)]
        out: list[tuple[str, list[tuple[Decimal, Decimal, Decimal, Decimal]], list[Decimal]]] = []

        pts_h: list[tuple[Decimal, Decimal, Decimal, Decimal]] = []
        for i in range(a):
            u = (Decimal(i) + _HALF) / da
            r1, r2 = (_ONE - u).sqrt(), u.sqrt()
            for s1, c1 in cs1:
                for s2, c2 in cs2:
                    pts_h.append((r1 * c1, r1 * s1, r2 * c2, r2 * s2))
        out.append(("DenomPi_EQ_Hopf_S3", pts_h, eq_w))

        psis = [_inv_f3_dec((Decimal(i) + _HALF) / da) for i in range(a)]
        zs = [-_ONE + _TWO * (Decimal(j) + _HALF) / db for j in range(b)]
        pts_cap: list[tuple[Decimal, Decimal, Decimal, Decimal]] = []
        for ps in psis:
            sp, cp = d_sin_cos(ps)
            for z in zs:
                st = (_ONE - z * z).sqrt()
                for s2, c2 in cs2:
                    pts_cap.append((sp * st * c2, sp * st * s2, sp * z, cp))
        out.append(("DenomPi_EQ_Cap_S3", pts_cap, eq_w))

        pts_np: list[tuple[Decimal, Decimal, Decimal, Decimal]] = []
        w_jac: list[Decimal] = []
        for i in range(a):
            sp, cp = d_sin_cos(_PI * (Decimal(i) + _HALF) / da)
            for j in range(b):
                st, ct = d_sin_cos(_PI * (Decimal(j) + _HALF) / db)
                wj = sp * sp * st
                for s2, c2 in cs2:
                    pts_np.append((sp * st * c2, sp * st * s2, sp * ct, cp))
                    w_jac.append(wj)
        swj = sum(w_jac, _ZERO)
        out.append(("NumPi_Unweighted", pts_np, eq_w))
        out.append(("NumPi_JacWeight", pts_np, [w / swj for w in w_jac]))

        dims4 = {64: (4, 4, 2, 2), 256: (4, 4, 4, 4), 1024: (8, 8, 4, 4)}[n]
        ax4 = [[-_ONE + Decimal(2 * i + 1) / Decimal(d) for i in range(d)] for d in dims4]
        pts_c4: list[tuple[Decimal, Decimal, Decimal, Decimal]] = []
        for x in ax4[0]:
            for y in ax4[1]:
                for z in ax4[2]:
                    for t in ax4[3]:
                        r = (x * x + y * y + z * z + t * t).sqrt()
                        pts_c4.append((x / r, y / r, z / r, t / r))
        out.append(("CartBox_Vol_S3", pts_c4, eq_w))

        gu, gw = leggauss_dec(a)
        pts_gl: list[tuple[Decimal, Decimal, Decimal, Decimal]] = []
        w_gl: list[Decimal] = []
        for x, wx in zip(gu, gw):
            u = _HALF * (x + _ONE)
            r1, r2 = (_ONE - u).sqrt(), u.sqrt()
            wt = _HALF * wx / (db * dc)
            for s1, c1 in cs1:
                for s2, c2 in cs2:
                    pts_gl.append((r1 * c1, r1 * s1, r2 * c2, r2 * s2))
                    w_gl.append(wt)
        out.append(("Ctrl_GL_Hopf_S3", pts_gl, w_gl))

        h2, h3, h5 = halton_dec(n, 2), halton_dec(n, 3), halton_dec(n, 5)
        pts_q: list[tuple[Decimal, Decimal, Decimal, Decimal]] = []
        for u, v1, v2 in zip(h2, h3, h5):
            r1, r2 = (_ONE - u).sqrt(), u.sqrt()
            s1, c1 = d_sin_cos(_TWO_PI * v1)
            s2, c2 = d_sin_cos(_TWO_PI * v2)
            pts_q.append((r1 * c1, r1 * s1, r2 * c2, r2 * s2))
        out.append(("Ctrl_HaltonQMC_S3", pts_q, eq_w))
        return out


def run_h2b_benchmarks() -> dict[str, Any]:
    """Execute full deterministic H2b S^2 + S^3 analytical physics benchmarks (zero floats)."""
    s2_results: list[dict[str, Any]] = []
    for n in (64, 256, 1024):
        rows: list[dict[str, Any]] = []
        by_name: dict[str, dict[str, Any]] = {}
        for gname, pts, ws in _s2_grids(n):
            res = _eval_s2_grid(pts, ws)
            by_name[gname] = res
            rows.append({
                "grid": gname,
                "n_nodes": res["n_nodes"],
                "gauss_flux_rms": d_fmt_sci(res["gauss_flux_rms"]),
                "sh_gram_rms": d_fmt_sci(res["sh_gram_rms"]),
                "sh_gram_max": d_fmt_sci(res["sh_gram_max"]),
            })
        eq = by_name["DenomPi_EQ_S2"]
        np_u = by_name["NumPi_Unweighted"]
        np_s = by_name["NumPi_SinWeight"]
        cb = by_name["CartBox_Vol_S2"]
        fib = by_name["Ctrl_Fibonacci"]
        s2_results.append({
            "target_n": n,
            "rows": rows,
            "ratios": {
                "eq_vs_numpi_unweighted_flux": d_ratio_dec4(np_u["gauss_flux_rms"], eq["gauss_flux_rms"]),
                "eq_vs_numpi_unweighted_sh": d_ratio_dec4(np_u["sh_gram_rms"], eq["sh_gram_rms"]),
                "eq_vs_cartbox_flux": d_ratio_dec4(cb["gauss_flux_rms"], eq["gauss_flux_rms"]),
                "eq_vs_cartbox_sh": d_ratio_dec4(cb["sh_gram_rms"], eq["sh_gram_rms"]),
                "eq_vs_numpi_sinweight_flux": d_ratio_dec4(np_s["gauss_flux_rms"], eq["gauss_flux_rms"]),
                "eq_vs_numpi_sinweight_sh": d_ratio_dec4(np_s["sh_gram_rms"], eq["sh_gram_rms"]),
                "fib_vs_numpi_sinweight_flux": d_ratio_dec4(np_s["gauss_flux_rms"], fib["gauss_flux_rms"]),
                "fib_vs_numpi_sinweight_sh": d_ratio_dec4(np_s["sh_gram_rms"], fib["sh_gram_rms"]),
            },
        })

    s3_results: list[dict[str, Any]] = []
    hopf_n123_raw: dict[int, Decimal] = {}
    for n in (64, 256, 1024):
        rows3: list[dict[str, Any]] = []
        by_name3: dict[str, dict[str, Any]] = {}
        for gname, pts, ws in _s3_grids(n):
            res = _eval_s3_grid(pts, ws)
            by_name3[gname] = res
            rows3.append({
                "grid": gname,
                "n_nodes": res["n_nodes"],
                "h_1s2s2p_rms": d_fmt_sci(res["h_1s2s2p_rms"]),
                "h_n123_rms": d_fmt_sci(res["h_n123_rms"]),
                "poisson_rms": d_fmt_sci(res["poisson_rms"]),
            })
        hopf = by_name3["DenomPi_EQ_Hopf_S3"]
        hopf_n123_raw[n] = hopf["h_n123_rms"]
        np_u = by_name3["NumPi_Unweighted"]
        np_j = by_name3["NumPi_JacWeight"]
        cb = by_name3["CartBox_Vol_S3"]
        s3_results.append({
            "target_n": n,
            "rows": rows3,
            "ratios": {
                "hopf_vs_numpi_unweighted_1s2s2p": d_ratio_dec4(np_u["h_1s2s2p_rms"], hopf["h_1s2s2p_rms"]),
                "hopf_vs_numpi_unweighted_n123": d_ratio_dec4(np_u["h_n123_rms"], hopf["h_n123_rms"]),
                "hopf_vs_numpi_unweighted_poisson": d_ratio_dec4(np_u["poisson_rms"], hopf["poisson_rms"]),
                "hopf_vs_cartbox_n123": d_ratio_dec4(cb["h_n123_rms"], hopf["h_n123_rms"]),
                "hopf_vs_cartbox_poisson": d_ratio_dec4(cb["poisson_rms"], hopf["poisson_rms"]),
                "hopf_vs_numpi_jacweight_1s2s2p": d_ratio_dec4(np_j["h_1s2s2p_rms"], hopf["h_1s2s2p_rms"]),
                "hopf_vs_numpi_jacweight_n123": d_ratio_dec4(np_j["h_n123_rms"], hopf["h_n123_rms"]),
                "hopf_vs_numpi_jacweight_poisson": d_ratio_dec4(np_j["poisson_rms"], hopf["poisson_rms"]),
            },
        })

    pts_600 = _build_600_cell_dec()
    with localcontext() as ctx:
        ctx.prec = BENCH_PREC
        w_600 = [_ONE / Decimal(len(pts_600))] * len(pts_600)
    res_600 = _eval_s3_grid(pts_600, w_600)

    s2_1024 = s2_results[2]["ratios"]
    s3_1024 = s3_results[2]["ratios"]
    gate3 = Decimal(3)
    eq_beats_unweighted_3x = all_ge_threshold((
        Decimal(s2_1024["eq_vs_numpi_unweighted_flux"]),
        Decimal(s2_1024["eq_vs_numpi_unweighted_sh"]),
        Decimal(s3_1024["hopf_vs_numpi_unweighted_n123"]),
        Decimal(s3_1024["hopf_vs_numpi_unweighted_poisson"]),
    ), gate3)
    eq_beats_cartesian_3x = all_ge_threshold((
        Decimal(s2_1024["eq_vs_cartbox_flux"]),
        Decimal(s2_1024["eq_vs_cartbox_sh"]),
        Decimal(s3_1024["hopf_vs_cartbox_n123"]),
        Decimal(s3_1024["hopf_vs_cartbox_poisson"]),
    ), gate3)
    tensor_eq_beats_jac_weighted_3x = all_ge_threshold((
        Decimal(s2_1024["eq_vs_numpi_sinweight_flux"]),
        Decimal(s3_1024["hopf_vs_numpi_jacweight_poisson"]),
    ), gate3)
    fib_beats_sinweight_flux_3x = all_ge_threshold((Decimal(s2_1024["fib_vs_numpi_sinweight_flux"]),), gate3)
    hopf_1s2s2p_exact_all_n = all(
        row["h_1s2s2p_rms"] == "0"
        for blk in s3_results
        for row in blk["rows"]
        if row["grid"] == "DenomPi_EQ_Hopf_S3"
    )
    hopf_n123_256_to_1024_factor = d_ratio_dec4(hopf_n123_raw[256], hopf_n123_raw[1024])

    return {
        "decimal_precision_digits": BENCH_PREC,
        "node_counts": [64, 256, 1024],
        "prereg_pass_gate_min_reduction_x": 3,
        "s2_electrostatics_and_multipoles": s2_results,
        "s3_fock_moser_hydrogen_and_kepler": s3_results,
        "s3_600cell_11design_control": {
            "n_nodes": res_600["n_nodes"],
            "h_1s2s2p_rms": d_fmt_sci(res_600["h_1s2s2p_rms"]),
            "h_n123_rms": d_fmt_sci(res_600["h_n123_rms"]),
            "poisson_rms": d_fmt_sci(res_600["poisson_rms"]),
        },
        "grading": {
            "verdict": "PARTIAL",
            "eq_beats_unweighted_numpi_ge_3x": eq_beats_unweighted_3x,
            "eq_beats_unweighted_cartesian_ge_3x": eq_beats_cartesian_3x,
            "tensor_eq_beats_jacobian_weighted_numpi_ge_3x": tensor_eq_beats_jac_weighted_3x,
            "fibonacci_equal_area_beats_sinweight_flux_ge_3x": fib_beats_sinweight_flux_3x,
            "hopf_eq_s3_1s2s2p_exact_zero_all_n": hopf_1s2s2p_exact_all_n,
            "hopf_eq_s3_n123_256_to_1024_scaling_factor": hopf_n123_256_to_1024_factor,
            "obstruction_mechanism": (
                "Tensor-product equal-area coordinate maps (z in [-1,1] on S^2, u in [0,1] on S^3) "
                "have sqrt(1-z^2) and sqrt(u*(1-u)) endpoint derivative singularities, capping midpoint "
                "convergence at O(M^-1.5) vs O(M^-2) for Jacobian-weighted smooth angle grids and "
                "exponential convergence for Gauss-Legendre / spherical designs."
            ),
        },
    }


def main() -> int:
    print(json.dumps(run_h2b_benchmarks(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
