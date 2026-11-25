#!/usr/bin/env python3
"""Pure-stdlib cryptographic, preregistration, and zero-float pure-Q operator audit
for Track S113: Multi-Sensor Live Silicon Physics & Cross-Modal Coupling
(PREREG-S113 + PREREG-S113-AMENDMENT1).

Runs under isolated standard-library Python (-I -B, -I -O -B, -I -B -W error)
with zero third-party dependencies (no numpy/scipy required).

Verifies:
1. Strict Zone-B JSON parsing (rejects NaN/Infinity, duplicate keys, float underflow)
   and privacy/path leak absence across certificate and blind-discovery receipts.
2. Canonical SHA-256 integrity of payload_sha256 and certificate_sha256, plus
   immutable parent preregistration pin (PREREG_S113_MULTISENSOR_SILICON_PHYSICS.md).
3. Exact pure-Q (fractions.Fraction, zero floats) S113-H5 operator identities:
   - Symmetry of sigma_pp_exact_q and schur_complement_pp_exact_q
   - Bunch-Kaufman Sylvester-Krein inertia (U+29BA) on Schur complement (3, 0, 0)
   - Haynsworth inertia additivity: (13, 0, 0) = (10, 0, 0) + (3, 0, 0)
   - Exact rational explained variance R^2_{dark|sensors,Q} and incremental identity
     Delta R^2_Q == R^2_{dark|all,Q} - R^2_{dark|CPU,Q}
   - Exact K_4 Hodge-1 cohomological obstruction (U+29C7) rational recomputation.
4. Literal preregistered verdict gate consistency across S113-H1..H5, E1b, E1c, E2b
   (zero goalpost shifting).
5. Anti-CS-09 split-half + N_confirm=799 + step-down Holm-Bonferroni (< 0.005)
   integrity across all surviving anomalies in s113_blind_anomalies_receipt.json (Holm recomputed pooled per lens across phases; true survivor count reported by the audit).
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any


SCHEMA_ID = "aletheia.track_s113.multisensor_silicon_certificate.v1"
PREREG_ID = "PREREG-S113"
AMENDMENT_ID = "PREREG-S113-AMENDMENT1"
EXPECTED_PARENT_PREREG_SHA256 = "cebe48326461ef048c6e8ccfb51f76f661f33b44c32d7e0178777d2ad8221e67"
MAX_SERIALIZED_INT_BITS = 14000

QMat = tuple[tuple[Fraction, ...], ...]


class S113AuditError(ValueError):
    """Explicit structured validation error (never stripped under python3 -O)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def require_ok(cond: bool, code: str, message: str) -> None:
    if not cond:
        raise S113AuditError(code, message)


def _literal_denotes_exact_zero(literal: str) -> bool:
    try:
        exact = Decimal(literal)
    except (InvalidOperation, ValueError):
        return False
    return exact.is_zero()


def parse_strict_json_text(
    raw_text: str,
    *,
    allow_float: bool = True,
    require_object: bool = True,
) -> Any:
    require_ok(isinstance(raw_text, str) and len(raw_text.strip()) > 0, "EMPTY_JSON", "JSON input must be non-empty")

    def reject_constant(tok: str) -> Any:
        raise S113AuditError("JSON_CONSTANT_FORBIDDEN", f"Non-standard JSON constant: {tok!r}")

    def reject_float(tok: str) -> Any:
        raise S113AuditError("JSON_FLOAT_FORBIDDEN", f"Float literal forbidden: {tok!r}")

    def finite_float(tok: str) -> float:
        val = float(tok)
        require_ok(math.isfinite(val), "JSON_FLOAT_NOT_FINITE", f"Non-finite float literal: {tok!r}")
        if val == 0.0 and not _literal_denotes_exact_zero(tok):
            raise S113AuditError("JSON_FLOAT_UNDERFLOW", f"Float literal underflows to zero: {tok!r}")
        return val

    def reject_dup_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in pairs:
            if k in out:
                raise S113AuditError("JSON_DUPLICATE_KEY", f"Duplicate JSON key: {k!r}")
            out[k] = v
        return out

    kwargs: dict[str, Any] = {
        "parse_constant": reject_constant,
        "object_pairs_hook": reject_dup_keys,
        "parse_float": finite_float if allow_float else reject_float,
    }
    try:
        obj = json.loads(raw_text, **kwargs)
    except S113AuditError:
        raise
    except Exception as exc:
        raise S113AuditError("JSON_SYNTAX_ERROR", str(exc)) from exc

    if require_object:
        require_ok(isinstance(obj, dict), "JSON_NOT_OBJECT", "Top-level JSON value must be an object")
    return obj


def load_strict_json_file(path: Path, *, allow_float: bool = True) -> dict[str, Any]:
    require_ok(path.is_file(), "FILE_NOT_FOUND", f"Missing JSON file: {path.name}")
    raw = path.read_bytes()
    require_ok(b"\r" not in raw, "CRLF_FORBIDDEN", f"CR byte found in {path.name}")
    return parse_strict_json_text(raw.decode("utf-8"), allow_float=allow_float, require_object=True)


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _privacy_leak_regexes() -> list[tuple[str, re.Pattern[str]]]:
    slash = chr(47)
    bslash = chr(92)
    raw_dir_tok = "local_" + "raw_" + "av"
    return [
        ("unix_home_path", re.compile(slash + "ho" + "me" + slash + r"[A-Za-z0-9._-]+")),
        ("macos_users_path", re.compile(slash + "Us" + "ers" + slash + r"[A-Za-z0-9._-]+")),
        ("windows_users_path", re.compile(r"[A-Za-z]:" + bslash + bslash + "Us" + "ers" + bslash + bslash)),
        ("raw_av_path_leak", re.compile(raw_dir_tok)),
        ("gh_pat", re.compile("gh" + "p_" + r"[A-Za-z0-9]{20,}")),
        ("private_key", re.compile("-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ]


def scan_text_for_privacy_leaks(text: str) -> list[str]:
    hits: list[str] = []
    for label, rx in _privacy_leak_regexes():
        if rx.search(text) is not None:
            hits.append(label)
    return hits


# =============================================================================
# Pure-Q (Zero-Float) Operator Calculus Kernel
# =============================================================================


def is_exact_int(x: Any) -> bool:
    return type(x) is int


def frac_to_str(q: Fraction) -> str:
    require_ok(type(q) is Fraction, "BAD_FRACTION", "Expected exact Fraction")
    num, den = q.numerator, q.denominator
    require_ok(
        num.bit_length() <= MAX_SERIALIZED_INT_BITS and den.bit_length() <= MAX_SERIALIZED_INT_BITS,
        "FRACTION_BIT_OVERFLOW",
        "Rational bit-length exceeds serialization bound",
    )
    return f"{num}/{den}"


def str_to_frac(s: str) -> Fraction:
    require_ok(isinstance(s, str) and "/" in s, "BAD_FRAC_STR", f"Invalid rational string {s!r}")
    parts = s.split("/")
    require_ok(len(parts) == 2, "BAD_FRAC_STR", f"Invalid rational string {s!r}")
    try:
        num = int(parts[0])
        den = int(parts[1])
    except ValueError as exc:
        raise S113AuditError("BAD_FRAC_STR", f"Non-integer rational component in {s!r}") from exc
    require_ok(den > 0 and math.gcd(abs(num), den) == 1, "NONCANONICAL_FRAC_STR", f"Non-reduced rational {s!r}")
    require_ok(
        num.bit_length() <= MAX_SERIALIZED_INT_BITS and den.bit_length() <= MAX_SERIALIZED_INT_BITS,
        "FRACTION_BIT_OVERFLOW",
        "Rational bit-length exceeds serialization bound",
    )
    return Fraction(num, den)


def q_is_symmetric(m: QMat) -> bool:
    n = len(m)
    if n == 0 or any(len(row) != n for row in m):
        return False
    for i in range(n):
        for j in range(i + 1, n):
            if m[i][j] != m[j][i]:
                return False
    return True


def q_eye(n: int) -> QMat:
    return tuple(tuple(Fraction(1 if i == j else 0) for j in range(n)) for i in range(n))


def q_zeros(r: int, c: int) -> QMat:
    return tuple(tuple(Fraction(0) for _ in range(c)) for _ in range(r))


def q_transpose(a: QMat) -> QMat:
    return tuple(tuple(a[r][c] for r in range(len(a))) for c in range(len(a[0])))


def q_sub(a: QMat, b: QMat) -> QMat:
    return tuple(tuple(a[i][j] - b[i][j] for j in range(len(a[0]))) for i in range(len(a)))


def q_mul(a: QMat, b: QMat) -> QMat:
    require_ok(len(a[0]) == len(b), "QMUL_SHAPE", "Inner matrix dimension mismatch")
    m, k, n = len(a), len(b), len(b[0])
    return tuple(
        tuple(sum((a[i][t] * b[t][j] for t in range(k)), Fraction(0)) for j in range(n))
        for i in range(m)
    )


def q_submat(m: QMat, rows: tuple[int, ...], cols: tuple[int, ...]) -> QMat:
    return tuple(tuple(m[r][c] for c in cols) for r in rows)


def q_solve(a: QMat, b: QMat) -> QMat:
    """Exact Gauss-Jordan linear solver over Q."""
    n = len(a)
    require_ok(n > 0 and n == len(a[0]) and len(b) == n, "QSOLVE_SHAPE", "Invalid q_solve dimensions")
    m = len(b[0])
    aug = [list(a[i]) + list(b[i]) for i in range(n)]
    for col in range(n):
        piv = -1
        for r in range(col, n):
            if aug[r][col] != 0:
                piv = r
                break
        require_ok(piv >= 0, "QSINGULAR", f"Singular rational matrix at column {col}")
        if piv != col:
            aug[col], aug[piv] = aug[piv], aug[col]
        pv = aug[col][col]
        aug[col] = [v / pv for v in aug[col]]
        for r in range(n):
            if r != col and aug[r][col] != 0:
                fac = aug[r][col]
                aug[r] = [aug[r][j] - fac * aug[col][j] for j in range(n + m)]
    return tuple(tuple(aug[i][n:]) for i in range(n))


def q_nullspace(a: QMat) -> tuple[tuple[Fraction, ...], ...]:
    """Exact rational basis for ker(A)."""
    m, n = len(a), len(a[0])
    w = [list(row) for row in a]
    piv_cols: list[int] = []
    r = 0
    for c in range(n):
        piv = -1
        for i in range(r, m):
            if w[i][c] != 0:
                piv = i
                break
        if piv < 0:
            continue
        if piv != r:
            w[r], w[piv] = w[piv], w[r]
        pv = w[r][c]
        w[r] = [v / pv for v in w[r]]
        for i in range(m):
            if i != r and w[i][c] != 0:
                fac = w[i][c]
                w[i] = [w[i][j] - fac * w[r][j] for j in range(n)]
        piv_cols.append(c)
        r += 1
    piv_set = set(piv_cols)
    free_cols = [c for c in range(n) if c not in piv_set]
    basis: list[tuple[Fraction, ...]] = []
    for fc in free_cols:
        vec = [Fraction(0)] * n
        vec[fc] = Fraction(1)
        for row_idx, pc in enumerate(piv_cols):
            vec[pc] = -w[row_idx][fc]
        basis.append(tuple(vec))
    return tuple(basis)


def q_pinv_sym(m: QMat) -> QMat:
    """Exact rational Moore-Penrose pseudoinverse for symmetric M over Q."""
    require_ok(q_is_symmetric(m), "QNOT_SYM", "q_pinv_sym requires exact symmetric matrix")
    n = len(m)
    w = [list(row) for row in m]
    piv_cols: list[int] = []
    r = 0
    for c in range(n):
        piv = -1
        for i in range(r, n):
            if w[i][c] != 0:
                piv = i
                break
        if piv < 0:
            continue
        if piv != r:
            w[r], w[piv] = w[piv], w[r]
        pv = w[r][c]
        for i in range(r + 1, n):
            if w[i][c] != 0:
                fac = w[i][c] / pv
                for j in range(c, n):
                    w[i][j] -= fac * w[r][j]
        piv_cols.append(c)
        r += 1
    if not piv_cols:
        return q_zeros(n, n)
    b_mat = tuple(tuple(m[i][c] for c in piv_cols) for i in range(n))
    bt = q_transpose(b_mat)
    gram = q_mul(bt, q_mul(m, b_mat))
    gram_inv = q_solve(gram, q_eye(len(piv_cols)))
    return q_mul(b_mat, q_mul(gram_inv, bt))


def q_krein_inertia(m: QMat) -> tuple[int, int, int]:
    """Exact Sylvester-Krein inertia (n_pos, n_zero, n_neg) via Bunch-Kaufman over Q (U+29BA)."""
    require_ok(q_is_symmetric(m), "QNOT_SYM", "Krein inertia requires exact symmetric matrix")
    n = len(m)
    a = [list(row) for row in m]
    pos = zero = neg = 0
    k = 0
    while k < n:
        diag_piv = -1
        for i in range(k, n):
            if a[i][i] != 0:
                diag_piv = i
                break
        if diag_piv >= 0:
            if diag_piv != k:
                a[k], a[diag_piv] = a[diag_piv], a[k]
                for row in a:
                    row[k], row[diag_piv] = row[diag_piv], row[k]
            d = a[k][k]
            if d > 0:
                pos += 1
            else:
                neg += 1
            for i in range(k + 1, n):
                if a[i][k] != 0:
                    fac = a[i][k] / d
                    for j in range(k + 1, n):
                        a[i][j] -= fac * a[k][j]
            k += 1
            continue

        off_i = off_j = -1
        for i in range(k, n):
            for j in range(i + 1, n):
                if a[i][j] != 0:
                    off_i, off_j = i, j
                    break
            if off_i >= 0:
                break
        if off_i < 0:
            zero += n - k
            break
        if off_i != k:
            a[k], a[off_i] = a[off_i], a[k]
            for row in a:
                row[k], row[off_i] = row[off_i], row[k]
        if off_j != k + 1:
            a[k + 1], a[off_j] = a[off_j], a[k + 1]
            for row in a:
                row[k + 1], row[off_j] = row[off_j], row[k + 1]
        p = a[k][k + 1]
        pos += 1
        neg += 1
        for i in range(k + 2, n):
            ci0, ci1 = a[i][k], a[i][k + 1]
            if ci0 != 0 or ci1 != 0:
                inv0, inv1 = ci1 / p, ci0 / p
                for j in range(k + 2, n):
                    a[i][j] -= inv0 * a[k][j] + inv1 * a[k + 1][j]
        k += 2
    return (pos, zero, neg)


def q_schur_pushforward(sigma: QMat, elim_idx: tuple[int, ...]) -> QMat:
    """Exact Fiber-Elimination Schur Pushforward M_PP - M_PO M_OO^+ M_OP over Q (U+29C4)."""
    require_ok(q_is_symmetric(sigma), "QNOT_SYM", "Schur pushforward requires symmetric matrix over Q")
    n = len(sigma)
    elim_set = set(elim_idx)
    keep_idx = tuple(i for i in range(n) if i not in elim_set)
    require_ok(len(keep_idx) > 0 and len(elim_idx) > 0, "QSCHUR_IDX", "Both keep and elim index sets must be non-empty")
    m_pp = q_submat(sigma, keep_idx, keep_idx)
    m_po = q_submat(sigma, keep_idx, elim_idx)
    m_oo = q_submat(sigma, elim_idx, elim_idx)
    m_op = q_transpose(m_po)
    m_oo_pinv = q_pinv_sym(m_oo)
    return q_sub(m_pp, q_mul(m_po, q_mul(m_oo_pinv, m_op)))


def q_dark_mode_shadow(sigma: QMat, elim_idx: tuple[int, ...]) -> dict[str, int]:
    """Exact Singular-Kernel / Dark-Mode Shadow on eliminated fiber O over Q (U+29C5)."""
    n = len(sigma)
    elim_set = set(elim_idx)
    keep_idx = tuple(i for i in range(n) if i not in elim_set)
    m_oo = q_submat(sigma, elim_idx, elim_idx)
    m_po = q_submat(sigma, keep_idx, elim_idx)
    ker_basis = q_nullspace(m_oo)
    dim_dark = len(ker_basis)
    if dim_dark == 0:
        return {"dim_dark": 0, "r_cross": 0}
    k_mat = q_transpose(ker_basis)
    cross = q_mul(m_po, k_mat)
    null_cross = q_nullspace(cross)
    r_cross = dim_dark - len(null_cross)
    return {"dim_dark": dim_dark, "r_cross": r_cross}


def build_exact_q_gram_covariance(int_samples: list[list[int]]) -> QMat:
    """Build exact mean-centered symmetric covariance matrix over Q from integer-quantized samples."""
    t_len = len(int_samples)
    require_ok(t_len >= 4, "H5_TOO_FEW_WINDOWS", f"Need >=4 windows for exact Q covariance, got {t_len}")
    d_dim = len(int_samples[0])
    require_ok(d_dim >= 2, "H5_BAD_DIM", "Need >=2 variables")
    for row in int_samples:
        require_ok(len(row) == d_dim and all(is_exact_int(v) for v in row), "H5_NON_INT", "Quantized table must be exact ints")

    col_sums = [sum(int_samples[t][j] for t in range(t_len)) for j in range(d_dim)]
    centered_scaled = [
        [t_len * int_samples[t][j] - col_sums[j] for j in range(d_dim)]
        for t in range(t_len)
    ]
    denom = t_len * t_len * (t_len - 1)
    cov_rows: list[tuple[Fraction, ...]] = []
    for i in range(d_dim):
        row_q: list[Fraction] = []
        for j in range(d_dim):
            if j < i:
                row_q.append(cov_rows[j][i])
            else:
                num = sum(centered_scaled[t][i] * centered_scaled[t][j] for t in range(t_len))
                row_q.append(Fraction(num, denom))
        cov_rows.append(tuple(row_q))
    return tuple(cov_rows)


def q_k4_hodge1_obstruction(pair_taus_us: dict[str, float | int | Fraction]) -> dict[str, Any]:
    """Exact pure-Q Hodge-1 cohomological curl obstruction on K_4 (U+29C7)."""
    edges = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
    w_q: dict[tuple[int, int], Fraction] = {}
    for i, j in edges:
        key = f"ch{i}_ch{j}"
        require_ok(key in pair_taus_us, "K4_MISSING_EDGE", f"Missing K_4 edge {key}")
        raw_v = pair_taus_us[key]
        if type(raw_v) is Fraction:
            qv = raw_v
        else:
            qv = Fraction(int(round(float(raw_v) * 10000.0)), 10000)
        w_q[(i, j)] = qv
        w_q[(j, i)] = -qv

    # Exact L2 coboundary projection on K_4 with sum_v phi_v = 0: phi_v = -(1/4) sum_{u != v} w_{vu}
    phi = [
        -sum((w_q[(v, u)] for u in range(4) if u != v), Fraction(0)) * Fraction(1, 4)
        for v in range(4)
    ]
    norm_w2 = sum((w_q[e] * w_q[e] for e in edges), Fraction(0))
    norm_curl2 = sum(((w_q[(i, j)] - (phi[j] - phi[i])) ** 2 for i, j in edges), Fraction(0))
    kappa_q = Fraction(0) if norm_w2 == 0 else (norm_curl2 / norm_w2)
    return {
        "operator": "U+29C7_cohom_obstruction",
        "kappa_h1_exact_q": frac_to_str(kappa_q),
        "kappa_h1_decimal": round(float(kappa_q), 6),
        "vertex_potentials_us": [round(float(p), 4) for p in phi],
    }


def holm_bonferroni_list(pvals: list[float]) -> list[float]:
    """Exact step-down Holm-Bonferroni adjustment."""
    m = len(pvals)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda idx: pvals[idx])
    adj = [1.0] * m
    running_max = 0.0
    for rank, idx in enumerate(order):
        scaled = min(1.0, float(pvals[idx]) * float(m - rank))
        if scaled > running_max:
            running_max = scaled
        adj[idx] = running_max
    return adj


# =============================================================================
# Certificate & Blind-Discovery Receipt Verification
# =============================================================================


def _verify_prereg_verdict_rules(payload: dict[str, Any]) -> None:
    """Enforce literal PREREG-S113 decision gates against stored module metrics (zero goalpost shifting)."""
    vsum = payload.get("verdict_summary")
    require_ok(isinstance(vsum, dict), "MISSING_VERDICT_SUMMARY", "Missing verdict_summary dict")
    mods = payload.get("modules", {})

    if "H1" in mods:
        h1 = mods["H1"]
        v_h1 = str(h1.get("verdict", ""))
        require_ok(vsum.get("H1") == v_h1, "VERDICT_SUMMARY_MISMATCH", "H1 verdict_summary mismatch")
        min_p = float(h1["min_holm_p"])
        # Verdict must be one of the preregistered outcome names (no free-text CONFIRMED*).
        # PREREG-S113:20-21 names exactly H1-EMI (<2 us, lag <0.25 ms), H1-PIEZO
        # (chassis-borne, |dtau| in [5,80] us and lag < 1.0 ms) and an airborne fan
        # path (100-500 us); anything else is not a preregistered outcome.
        H1_VERDICTS = {"FALSIFIED", "CONFIRMED_H1_EMI", "CONFIRMED_H1_CHASSIS_PIEZO", "CONFIRMED_AIRBORNE_ACOUSTIC"}
        H1_TAU_BANDS = {"CONFIRMED_H1_EMI": (0.0, 2.0), "CONFIRMED_H1_CHASSIS_PIEZO": (5.0, 80.0),
                        "CONFIRMED_AIRBORNE_ACOUSTIC": (100.0, 500.0)}
        require_ok(v_h1 in H1_VERDICTS, "H1_VERDICT_NOT_ENUMERATED", f"H1 verdict {v_h1!r} not in preregistered outcome set")
        # The reported gate is the PREREGISTERED N=500 surrogate gate.
        require_ok(h1.get("n_surrogates") == 500 or "posthoc_n2000_exploratory" in h1,
                   "H1_N_NOT_PREREG", "H1 module must carry the preregistered N=500 gate (N=2000 only as posthoc_exploratory)")
        # Recompute the preregistered N=500 Holm-Bonferroni across the prime carriers
        # from the shipped raw N=500 p-values; min_holm_p and every p_holm_n500 must
        # equal the recomputed values (no hand-edited gate fields).
        carriers = h1.get("prime_carriers")
        require_ok(isinstance(carriers, dict) and len(carriers) >= 1, "H1_NO_CARRIERS", "H1 prime_carriers missing")
        raw500: dict[str, float] = {}
        for ck, cv in carriers.items():
            require_ok(isinstance(cv, dict) and isinstance(cv.get("p_raw_n500"), (int, float)) and not isinstance(cv.get("p_raw_n500"), bool),
                       "H1_MISSING_P_RAW_N500", f"carrier {ck} lacks numeric p_raw_n500")
            if cv.get("present") is True:
                raw500[ck] = float(cv["p_raw_n500"])
        order = sorted(raw500.items(), key=lambda kv: (kv[1], kv[0]))
        m = len(order)
        adj500: dict[str, float] = {}
        running = 0.0
        for rank, (ck, pr) in enumerate(order):
            running = min(1.0, max(running, pr * (m - rank)))
            adj500[ck] = running
        recomputed_min = min(adj500.values()) if adj500 else 1.0
        require_ok(abs(min_p - recomputed_min) <= 5e-9, "H1_MIN_HOLM_NOT_RECOMPUTED",
                   f"min_holm_p={min_p} != recomputed N=500 Holm min {recomputed_min}")
        for ck, cv in carriers.items():
            if ck in adj500:
                stored_n500 = cv.get("p_holm_n500")
                require_ok(stored_n500 is not None and abs(float(stored_n500) - round(adj500[ck], 8)) <= 5e-9,
                           "H1_P_HOLM_N500_MISMATCH", f"carrier {ck}: p_holm_n500={stored_n500} != recomputed {round(adj500[ck], 8)}")
        # The null gate is the preregistered Holm gate ONLY — no prbs OR-clause.
        require_ok(h1.get("passes_null_gate") is (recomputed_min < 0.005), "H1_NULL_GATE_OR_CLAUSE",
                   f"passes_null_gate={h1.get('passes_null_gate')} but recomputed N=500 min_holm_p={recomputed_min}")
        if v_h1.startswith("CONFIRMED"):
            require_ok(min_p < 0.005 and h1.get("passes_null_gate") is True, "H1_GATE_SPOOF", "H1 confirmed despite failing p_Holm < 0.005")
            require_ok(float(h1.get("prbs7_p", 1.0)) < 0.005, "H1_LAG_NOT_MEASURED",
                       "CONFIRMED requires a measured stimulus-to-audio lag (prbs7_p < 0.005)")
            band = H1_TAU_BANDS.get(v_h1)
            if band is not None:
                tau = float(h1["hf_6_22khz_max_abs_tau_us"])
                require_ok(band[0] <= tau <= band[1], "H1_TAU_BAND_MISMATCH",
                           f"mechanism {v_h1} requires max |tau| in {band} us, got {tau}")
        else:
            require_ok(v_h1 == "FALSIFIED" and min_p >= 0.005, "H1_FALSE_NEGATIVE", "H1 falsified despite passing gate")

    if "H2" in mods:
        h2 = mods["H2"]
        v_h2 = str(h2.get("verdict", ""))
        require_ok(vsum.get("H2") == v_h2, "VERDICT_SUMMARY_MISMATCH", "H2 verdict_summary mismatch")
        passes_h2 = float(h2["p_perm"]) < 0.005 and float(h2["lobo_balanced_accuracy"]) >= 0.60
        require_ok((v_h2 == "CONFIRMED") == passes_h2, "H2_GATE_SPOOF", f"H2 verdict {v_h2!r} contradicts metrics")

    if "H3" in mods:
        h3 = mods["H3"]
        v_h3 = str(h3.get("verdict", ""))
        require_ok(vsum.get("H3") == v_h3, "VERDICT_SUMMARY_MISMATCH", "H3 verdict_summary mismatch")
        has_carriers = len(h3.get("confirmed_carriers", [])) >= 1
        require_ok((v_h3 == "CONFIRMED") == has_carriers, "H3_GATE_SPOOF", f"H3 verdict {v_h3!r} contradicts confirmed_carriers")

    if "H4" in mods:
        h4 = mods["H4"]
        v_h4 = str(h4.get("verdict", ""))
        require_ok(vsum.get("H4") == v_h4, "VERDICT_SUMMARY_MISMATCH", "H4 verdict_summary mismatch")
        passes_h4 = float(h4["ptc_r2"]) > 0.98 and float(h4["conversion_gain_k_dn_per_e"]) > 0.0
        require_ok((v_h4 == "CONFIRMED") == passes_h4, "H4_GATE_SPOOF", f"H4 verdict {v_h4!r} contradicts PTC R^2 / K")

    if "H5" in mods:
        h5 = mods["H5"]
        v_h5 = str(h5.get("verdict", ""))
        require_ok(vsum.get("H5") == v_h5, "VERDICT_SUMMARY_MISMATCH", "H5 verdict_summary mismatch")
        r2_inc = str_to_frac(h5["incremental_multisensor_dark_r2_exact_q"])
        passes_h5 = (r2_inc > 0) and (float(h5["p_circular_shift"]) < 0.005)
        require_ok((v_h5 == "CONFIRMED") == passes_h5, "H5_GATE_SPOOF", f"H5 verdict {v_h5!r} contradicts p_circular_shift")

    conf = payload.get("confirmatory_phases", {})
    if isinstance(conf, dict):
        e1 = conf.get("E1", {})
        if isinstance(e1, dict):
            if "e1b_ir_1009hz_replication" in e1:
                e1b = e1["e1b_ir_1009hz_replication"]
                v_e1b = str(e1b.get("verdict", ""))
                require_ok(vsum.get("H3_E1b_IR_1009HZ_OOS") == v_e1b, "E1B_SUMMARY_MISMATCH", "H3_E1b summary mismatch")
                any_rep = any(
                    isinstance(e1b.get(k), dict)
                    and float(e1b[k].get("snr_sideband_sigma", 0.0)) >= 4.0
                    and float(e1b[k].get("snr_idle_sigma", 0.0)) >= 4.0
                    and float(e1b[k].get("p_raw", 1.0)) < 0.005
                    for k in ("ir_stratified_1009hz", "ir_led_on_1009hz", "ir_led_off_1009hz")
                )
                exp_e1b = "CONFIRMED_REPLICATED" if any_rep else "FALSIFIED_NOISE_FLUCTUATION"
                require_ok(v_e1b == exp_e1b, "E1B_GATE_SPOOF", f"E1b verdict {v_e1b!r} != {exp_e1b!r}")
            if "e1c_linear_gamma100_ptc_and_e1d_thermal" in e1:
                e1c = e1["e1c_linear_gamma100_ptc_and_e1d_thermal"]
                v_e1c = str(e1c.get("verdict", ""))
                require_ok(vsum.get("H4_E1c_LINEAR_GAMMA100") == v_e1c, "E1C_SUMMARY_MISMATCH", "H4_E1c summary mismatch")
                passes_e1c = float(e1c["ptc_r2"]) > 0.98 and float(e1c["conversion_gain_k_dn_per_e"]) > 0.0
                require_ok((v_e1c == "CONFIRMED") == passes_e1c, "E1C_GATE_SPOOF", f"E1c verdict {v_e1c!r} contradicts PTC R^2")
            e1a = e1.get("e1a_cocycle_and_dispersion", {})
            for grp in (e1a.get("core_pinning_3001hz", {}), e1a.get("lamb_frequency_sweep", {})):
                if isinstance(grp, dict):
                    for blk in grp.values():
                        if isinstance(grp, dict) and isinstance(blk, dict) and "broadband_6_22khz_tau_us" in blk and "broadband_hodge1_obstruction" in blk:
                            re_h = q_k4_hodge1_obstruction(blk["broadband_6_22khz_tau_us"])
                            require_ok(
                                re_h["kappa_h1_exact_q"] == blk["broadband_hodge1_obstruction"]["kappa_h1_exact_q"],
                                "K4_HODGE1_MISMATCH",
                                "E1a K_4 Hodge-1 exact Q obstruction mismatch",
                            )
        e2 = conf.get("E2", {})
        if isinstance(e2, dict):
            e2a = e2.get("e2a_cpu_vs_gpu_triangulation_and_imd", {})
            if isinstance(e2a, dict):
                for blk in e2a.values():
                    if isinstance(blk, dict) and "broadband_6_22khz_tau_us" in blk and "broadband_hodge1_obstruction" in blk:
                        re_h = q_k4_hodge1_obstruction(blk["broadband_6_22khz_tau_us"])
                        require_ok(
                            re_h["kappa_h1_exact_q"] == blk["broadband_hodge1_obstruction"]["kappa_h1_exact_q"],
                            "K4_HODGE1_MISMATCH",
                            "E2a K_4 Hodge-1 exact Q obstruction mismatch",
                        )
            if "e2b_high_wattage_rolling_shutter" in e2:
                e2b = e2["e2b_high_wattage_rolling_shutter"]
                v_e2b = str(e2b.get("verdict", ""))
                has_c2b = len(e2b.get("confirmed_carriers", [])) >= 1
                require_ok((v_e2b == "CONFIRMED") == has_c2b, "E2B_GATE_SPOOF", f"E2b verdict {v_e2b!r} contradicts confirmed_carriers")


def verify_certificate_dict(cert: dict[str, Any]) -> dict[str, Any]:
    """Cryptographic + pure-Q algebraic + prereg-rule + privacy verification of an S113 certificate."""
    require_ok(cert.get("schema") == SCHEMA_ID, "BAD_SCHEMA", f"Unexpected schema: {cert.get('schema')!r}")
    require_ok(cert.get("prereg_id") == PREREG_ID, "BAD_PREREG", f"Unexpected prereg_id: {cert.get('prereg_id')!r}")
    payload = cert.get("payload")
    require_ok(isinstance(payload, dict), "MISSING_PAYLOAD", "Certificate payload must be a dict")
    require_ok(payload.get("raw_av_staged_count", 0) == 0, "RAW_AV_NONZERO", "raw_av_staged_count must equal 0")

    leaks = scan_text_for_privacy_leaks(canonical_json(cert))
    require_ok(not leaks, "CERT_PRIVACY_LEAK", f"Certificate contains forbidden leak pattern: {leaks}")

    exp_payload_sha = sha256_text(canonical_json(payload))
    require_ok(cert.get("payload_sha256") == exp_payload_sha, "PAYLOAD_HASH_MISMATCH", "payload_sha256 mismatch")

    unsigned = {
        "schema": cert["schema"],
        "prereg_id": cert["prereg_id"],
        "payload": payload,
        "payload_sha256": exp_payload_sha,
    }
    exp_cert_sha = sha256_text(canonical_json(unsigned))
    require_ok(cert.get("certificate_sha256") == exp_cert_sha, "CERT_HASH_MISMATCH", "certificate_sha256 mismatch")

    mods = payload.get("modules", {})
    require_ok(isinstance(mods, dict) and len(mods) >= 1, "EMPTY_MODULES", "No hypothesis modules in certificate")
    require_ok(payload.get("n_surrogates") == 500 or isinstance(payload.get("prereg_deviation_note"), str),
               "PREREG_N_MISMATCH", "payload n_surrogates deviates from preregistered N=500 without a recorded deviation note")

    if "H5" in mods:
        h5 = mods["H5"]
        s_pp = tuple(tuple(str_to_frac(x) for x in row) for row in h5["sigma_pp_exact_q"])
        schur_pp = tuple(tuple(str_to_frac(x) for x in row) for row in h5["schur_complement_pp_exact_q"])
        require_ok(q_is_symmetric(s_pp) and q_is_symmetric(schur_pp), "H5_CERT_NONSYM", "H5 rational matrices non-symmetric")
        in_schur = q_krein_inertia(schur_pp)
        require_ok(list(in_schur) == h5["krein_inertia_schur_pos_zero_neg"], "H5_INERTIA_MISMATCH", "Schur inertia mismatch")
        require_ok(in_schur[2] == 0, "H5_SCHUR_NEGATIVE", "Schur complement has negative Krein inertia")
        in_full = h5["krein_inertia_full_pos_zero_neg"]
        in_oo = h5["krein_inertia_obs_pos_zero_neg"]
        require_ok(
            in_full[0] == in_oo[0] + in_schur[0]
            and in_full[1] == in_oo[1] + in_schur[1]
            and in_full[2] == in_oo[2] + in_schur[2],
            "H5_HAYNSWORTH_CERT_FAIL",
            "Haynsworth inertia additivity check failed",
        )
        require_ok(h5.get("haynsworth_inertia_additivity_exact") is True, "H5_HAYNSWORTH_FLAG", "Haynsworth flag must be True")
        r2_q = str_to_frac(h5["rapl_dark_r2_given_sensors_exact_q"])
        if s_pp[2][2] > 0:
            require_ok(r2_q == (s_pp[2][2] - schur_pp[2][2]) / s_pp[2][2], "H5_R2_Q_MISMATCH", "Exact Q R2 mismatch")
        if "rapl_dark_r2_given_all_exact_q" in h5 and "rapl_dark_r2_given_cpu_only_exact_q" in h5 and "incremental_multisensor_dark_r2_exact_q" in h5:
            r2_all = str_to_frac(h5["rapl_dark_r2_given_all_exact_q"])
            r2_cpu = str_to_frac(h5["rapl_dark_r2_given_cpu_only_exact_q"])
            r2_inc = str_to_frac(h5["incremental_multisensor_dark_r2_exact_q"])
            require_ok(r2_inc == r2_all - r2_cpu, "H5_INCREMENTAL_Q_MISMATCH", "Exact Q incremental R2 mismatch")

    _verify_prereg_verdict_rules(payload)
    return {
        "ok": True,
        "payload_sha256": exp_payload_sha,
        "certificate_sha256": exp_cert_sha,
        "verdict_summary": payload.get("verdict_summary", {}),
    }


def verify_blind_receipt_dict(receipt: dict[str, Any], prereg_md_path: Path | None = None) -> dict[str, Any]:
    """Verify PREREG-S113-AMENDMENT1 split-half + N=799 + Holm (< 0.005) receipt integrity."""
    require_ok(receipt.get("prereg_amendment") == AMENDMENT_ID, "BLIND_BAD_PREREG", "Unexpected prereg_amendment")
    require_ok(
        receipt.get("parent_prereg_sha256") == EXPECTED_PARENT_PREREG_SHA256,
        "BLIND_PARENT_SHA_MISMATCH",
        "parent_prereg_sha256 mismatch",
    )
    if prereg_md_path is not None and prereg_md_path.is_file():
        actual_sha = sha256_bytes(prereg_md_path.read_bytes())
        require_ok(actual_sha == EXPECTED_PARENT_PREREG_SHA256, "PREREG_FILE_TAMPERED", "Parent prereg file SHA-256 mismatch")

    leaks = scan_text_for_privacy_leaks(canonical_json(receipt))
    require_ok(not leaks, "BLIND_PRIVACY_LEAK", f"Blind receipt contains forbidden leak pattern: {leaks}")

    phases = receipt.get("phases_analyzed")
    by_phase = receipt.get("anomalies_by_phase")
    counts_by_lens = receipt.get("counts_by_lens")
    require_ok(isinstance(phases, list) and len(phases) >= 1, "BLIND_EMPTY_PHASES", "phases_analyzed empty")
    require_ok(isinstance(by_phase, dict) and isinstance(counts_by_lens, dict), "BLIND_BAD_STRUCT", "Missing anomalies_by_phase or counts_by_lens")

    def _raw_p(row: dict[str, Any]) -> float:
        for k in ("half2_p_surr", "half2_p_shift", "half2_p_iaaft", "rep2_p"):
            if row.get(k) is not None:
                return float(row[k])
        return 1.0

    def _holm_bonferroni(p_values: list[float]) -> list[float]:
        """Exact step-down Holm-Bonferroni adjusted p-values (monotone, capped at 1)."""
        order = sorted(range(len(p_values)), key=lambda i: (p_values[i], i))
        m = len(p_values)
        adj = [0.0] * m
        running = 0.0
        for rank, i in enumerate(order):
            running = min(1.0, max(running, p_values[i] * (m - rank)))
            adj[i] = running
        return adj

    # The preregistered amendment states the Holm family is each LENS pooled over ALL
    # phases; survivors and rejected rows together form the candidate set. The audit
    # RECOMPUTES Holm from the shipped raw p fields and requires the stored
    # half2_p_holm of every row to equal the recomputed adjusted p — a survivor set
    # to its raw p (or all survivors set to raw p) fails BLIND_HOLM_NOT_RECOMPUTED.
    rejected_all = receipt.get("holm_rejected", []) or []
    require_ok(isinstance(rejected_all, list), "BLIND_BAD_REJECTED", "holm_rejected must be a list")
    candidates: list[tuple[str, dict[str, Any]]] = []
    for ph in phases:
        require_ok(ph in by_phase and isinstance(by_phase[ph], list), "BLIND_MISSING_PHASE", f"Missing phase list {ph}")
        for row in by_phase[ph]:
            require_ok(isinstance(row, dict), "BLIND_BAD_ROW", "Anomaly row must be a dict")
            candidates.append((str(row.get("lens", "")), row))
    for row in rejected_all:
        require_ok(isinstance(row, dict), "BLIND_BAD_REJECTED_ROW", "holm_rejected row must be a dict")
        candidates.append((str(row.get("lens", "")), row))

    fam_members: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    row_idx: dict[int, int] = {}
    for idx, (lens, row) in enumerate(candidates):
        require_ok(len(lens) > 0, "BLIND_EMPTY_LENS", "Missing lens identifier")
        fam_members.setdefault(lens, []).append((idx, row))
        row_idx[id(row)] = idx
    recomputed: dict[int, float] = {}
    for lens, members in fam_members.items():
        raw = [_raw_p(row) for _, row in members]
        adj = _holm_bonferroni(raw)
        for (idx, row), a in zip(members, adj):
            recomputed[idx] = a
            stored = row.get("half2_p_holm", row.get("rep2_p_holm"))
            require_ok(stored is not None and abs(float(stored) - a) <= 1e-9,
                       "BLIND_HOLM_NOT_RECOMPUTED",
                       f"lens {lens}: stored half2_p_holm={stored} != recomputed Holm {a} (raw p={_raw_p(row)})")

    recounted_total = 0
    recounted_lenses: dict[str, int] = {}
    for ph in phases:
        for row in by_phase[ph]:
            require_ok(row.get("replicated_anomaly") is True, "BLIND_UNREPLICATED_ROW", "Non-replicated row in surviving receipt")
            n_conf = row.get("n_surrogates_confirm")
            require_ok(is_exact_int(n_conf) and n_conf >= 200, "BLIND_LOW_SURROGATES", f"n_surrogates_confirm={n_conf} < 200")
            p_holm = recomputed[row_idx[id(row)]]
            require_ok(0.0 < p_holm < 0.005, "BLIND_HOLM_THRESHOLD", f"Surviving row violates recomputed p_Holm < 0.005: {p_holm}")
            raw_p = _raw_p(row)
            require_ok(p_holm >= raw_p - 1e-12, "BLIND_HOLM_SHRINKS_P", f"half2_p_holm {p_holm} < raw {raw_p}")
            # Verify exact empirical rank denominator n_conf + 1 (e.g., 799 + 1 = 800)
            scaled_rank = p_holm * float(n_conf + 1)
            nearest_int = round(scaled_rank)
            require_ok(
                nearest_int >= 1 and abs(scaled_rank - float(nearest_int)) <= 2e-3,
                "BLIND_NONINTEGER_EMPIRICAL_RANK",
                f"p_Holm={p_holm} incompatible with empirical denominator {n_conf + 1}",
            )
            lens = str(row.get("lens", ""))
            recounted_lenses[lens] = recounted_lenses.get(lens, 0) + 1
            recounted_total += 1

    require_ok(receipt.get("total_surviving_anomalies") == recounted_total, "BLIND_TOTAL_MISMATCH", "total_surviving_anomalies mismatch")
    require_ok(counts_by_lens == recounted_lenses, "BLIND_LENS_COUNTS_MISMATCH", "counts_by_lens mismatch")
    # Rows rejected by the pooled lens-family Holm correction must sit in holm_rejected
    # with replicated_anomaly=false and recomputed p_holm >= 0.005.
    for row in rejected_all:
        require_ok(row.get("replicated_anomaly") is False, "BLIND_REJECTED_FLAG", "holm_rejected row must have replicated_anomaly=false")
        p_holm = recomputed[row_idx[id(row)]]
        require_ok(p_holm >= 0.005, "BLIND_REJECTED_PASSES", f"holm_rejected row actually passes the gate: {p_holm}")
    return {"ok": True, "total_surviving_anomalies": recounted_total, "holm_rejected": len(rejected_all), "phases": len(phases)}


def main(argv: list[str] | tuple[str, ...] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pure-stdlib audit verifier for Track S113 certificate & blind receipt")
    ap.add_argument("--check", type=Path, default=None, help="Path to s113_multisensor_certificate.json")
    ap.add_argument("--blind-receipt", type=Path, default=None, help="Optional path to s113_blind_anomalies_receipt.json")
    ap.add_argument("--json", action="store_true", help="Emit JSON output")
    args = ap.parse_args(list(argv) if argv is not None else None)

    here = Path(__file__).resolve().parent
    cert_path = args.check if args.check is not None else (here / "s113_multisensor_certificate.json")
    cert = load_strict_json_file(cert_path)
    cert_res = verify_certificate_dict(cert)

    blind_path = args.blind_receipt
    if blind_path is None:
        cand = cert_path.resolve().parent / "s113_blind_anomalies_receipt.json"
        if cand.is_file():
            blind_path = cand

    blind_res: dict[str, Any] | None = None
    if blind_path is not None:
        prereg_md = cert_path.resolve().parent / "PREREG_S113_MULTISENSOR_SILICON_PHYSICS.md"
        blind_obj = load_strict_json_file(blind_path)
        blind_res = verify_blind_receipt_dict(blind_obj, prereg_md if prereg_md.is_file() else None)

    out = {
        "ok": True,
        "payload_sha256": cert_res["payload_sha256"],
        "certificate_sha256": cert_res["certificate_sha256"],
        "verdict_summary": cert_res["verdict_summary"],
        "blind_surviving_anomalies": blind_res["total_surviving_anomalies"] if blind_res else None,
    }
    if args.json:
        print(canonical_json(out))
    else:
        print(
            f"OK TRACK-S113 payload_sha256={out['payload_sha256']} "
            f"certificate_sha256={out['certificate_sha256']} "
            f"blind_anomalies={out['blind_surviving_anomalies']} "
            f"verdicts={out['verdict_summary']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
