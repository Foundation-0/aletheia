#!/usr/bin/env python3
"""Track S53 Phase 1: Pure-Z/Q Independent Zero-Shared-Code Verifier (R1-R5 / Zone-B).

100% Python 3 stdlib, ZERO floats, ZERO bare asserts, ZERO external dependencies,
ZERO shared imports with `sensor_tomography_probe.py`.

Independently verifies from raw anonymous integer matrix `X_anonymous`:
  1. Strict Zone-B atomic `dir_fd` (`O_NOFOLLOW`, `S_ISREG`, streaming byte cap,
     logical `$PWD` guard, CRLF/BOM/NUL/float/duplicate-key/depth/int-bit rejection).
  2. Exact SHA-256 binding of `raw_sensor_snapshot.json` and `X_anonymous`.
  3. Exact Stage-A zero-variance dropout and exact affine+permutation gauge
     invariance (`max_diff == 0` identically in Q).
  4. Independent pure-Q recomputation of R^2, precision partial correlation P^2,
     Bareiss-Sylvester SPD inertia, blind greedy modularity clustering & exact ARI,
     empirical Schur dark-mode complement S_{A|B} (eta_i, rho^2_{ij|B}, PR),
     time-reversal asymmetry A^2_ij(tau) / dir_ij(tau) / Gamma_ij(tau) / Phi_i(tau),
     exact circular-shift nulls (N=200), and split-half out-of-sample replication.
  5. Deterministic `--self-test` with exact synthetic controls (symmetric diffusive,
     causal one-way chain, hidden common-driver Schur dark mode, and tamper kills).

Verification modes (standard 3-mode isolated parity):
  python3 -I -B sensor_tomography_audit.py --self-test
  python3 -I -O -B sensor_tomography_audit.py --self-test
  python3 -I -B -W error sensor_tomography_audit.py --self-test
"""

from __future__ import annotations

import argparse
import copy
import errno
from fractions import Fraction
import hashlib
import json
import math
from operator import mul
import os
from pathlib import Path
import random
import stat
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA_RAW = "aletheia.s53_raw_sensor_snapshot.v1"
SCHEMA_CERT = "aletheia.s53_beyond_language_tomography.v1"

MAX_FILE_BYTES = 8 * 1024 * 1024
READ_CHUNK_BYTES = 65_536
MAX_JSON_DEPTH = 64
MAX_INT_BITS = 3321
MAX_INT_DIGITS = 1000
_EXACT_PATH_TYPES = (Path, type(Path()))


class SensorAuditError(ValueError):
    """Typed fail-closed error for Track S53 verification and Zone-B guards."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def require_ok(cond: bool, code: str, detail: str) -> None:
    if not cond:
        raise SensorAuditError(code, detail)


def fmt_q(val: Fraction) -> str:
    if val.denominator == 1:
        return str(val.numerator)
    return f"{val.numerator}/{val.denominator}"


_Q12_SCALE = 10**12


def _q12_ticks(val: Fraction) -> int:
    """Exact pure-integer floor projection to 10^-12 grid (zero floats, zero coprime blowup)."""
    return (val.numerator * _Q12_SCALE) // val.denominator


def q12_floor(val: Fraction) -> Fraction:
    """Exact pure-integer floor projection to 10^-12 rational grid (zero floats)."""
    return Fraction(_q12_ticks(val), _Q12_SCALE)


def parse_exact_q(raw: Any, label: str) -> Fraction:
    require_ok(type(raw) is str, "INVALID_Q_TYPE", f"{label}: expected exact str")
    require_ok(len(raw) > 0, "EMPTY_Q", f"{label}: empty rational")
    require_ok(raw == raw.strip(), "INVALID_Q_SPACING", f"{label}: surrounding whitespace forbidden")
    parts = raw.split("/")
    require_ok(len(parts) in (1, 2), "INVALID_Q_FORMAT", f"{label}: malformed rational")

    def _parse_int_part(tok: str, allow_neg: bool) -> int:
        require_ok(len(tok) > 0, "INVALID_Q_FORMAT", f"{label}: empty integer token")
        sign = 1
        body = tok
        if body[0] == "-":
            require_ok(allow_neg, "INVALID_Q_SIGN", f"{label}: negative denominator forbidden")
            sign = -1
            body = body[1:]
        require_ok(len(body) > 0 and len(body) <= MAX_INT_DIGITS, "INT_DIGIT_LIMIT", f"{label}: digit cap exceeded")
        require_ok(all("0" <= ch <= "9" for ch in body), "INVALID_Q_DIGIT", f"{label}: non-ASCII digit")
        if len(body) > 1:
            require_ok(body[0] != "0", "LEADING_ZERO_Q", f"{label}: leading zero forbidden")
        val = sign * int(body)
        require_ok(abs(val).bit_length() <= MAX_INT_BITS, "INT_BIT_LIMIT", f"{label}: bit limit exceeded")
        return val

    num = _parse_int_part(parts[0], allow_neg=True)
    if len(parts) == 1:
        return Fraction(num, 1)
    den = _parse_int_part(parts[1], allow_neg=False)
    require_ok(den > 0, "ZERO_DENOMINATOR", f"{label}: denominator must be > 0")
    q = Fraction(num, den)
    require_ok(fmt_q(q) == raw, "NONCANONICAL_Q", f"{label}: rational string not canonical")
    return q


def _require_exact_int(val: Any, label: str, *, lo: Optional[int] = None, hi: Optional[int] = None) -> int:
    require_ok(type(val) is int, "INVALID_INT", f"{label}: must be exact int")
    require_ok(abs(val).bit_length() <= MAX_INT_BITS, "INT_BIT_LIMIT", f"{label}: exceeds {MAX_INT_BITS} bits")
    if lo is not None:
        require_ok(val >= lo, "INT_BOUNDS", f"{label}: must be >= {lo}")
    if hi is not None:
        require_ok(val <= hi, "INT_BOUNDS", f"{label}: must be <= {hi}")
    return val


def _require_exact_int_eq(val: Any, expected: int, code: str, label: str) -> None:
    require_ok(type(val) is int and val == expected, code, f"{label}: expected exact int {expected}")


def _require_exact_int_list(val: Any, code: str, label: str, expected: Sequence[int]) -> None:
    require_ok(type(val) is list and len(val) == len(expected), code, f"{label}: exact int list length/type mismatch")
    for item, exp in zip(val, expected):
        require_ok(type(item) is int and item == exp, code, f"{label}: element mismatch")


def _validate_json_tree_iter(obj: Any, label: str) -> None:
    """Iterative exact-JSON tree guard (no floats, no subclasses, depth/bit/NUL/surrogate capped)."""
    stack: List[Tuple[Any, int]] = [(obj, 1 if type(obj) in (dict, list) else 0)]
    while stack:
        cur, depth = stack.pop()
        require_ok(depth <= MAX_JSON_DEPTH, "JSON_DEPTH_LIMIT", f"{label}: depth > {MAX_JSON_DEPTH}")
        t = type(cur)
        if cur is None or t is bool:
            continue
        if t is int:
            require_ok(abs(cur).bit_length() <= MAX_INT_BITS, "INT_BIT_LIMIT", f"{label}: int > {MAX_INT_BITS} bits")
            continue
        if t is str:
            require_ok("\x00" not in cur, "NUL_BYTE_FORBIDDEN", f"{label}: NUL in string")
            try:
                cur.encode("utf-8", errors="strict")
            except UnicodeEncodeError as exc:
                raise SensorAuditError("INVALID_UTF8_SURROGATE", f"{label}: lone UTF-16 surrogate") from exc
            continue
        if t is list:
            for item in cur:
                stack.append((item, depth + 1 if type(item) in (dict, list) else depth))
            continue
        if t is dict:
            for k, v in cur.items():
                require_ok(type(k) is str, "INVALID_JSON_KEY", f"{label}: key must be exact str")
                stack.append((k, depth))
                stack.append((v, depth + 1 if type(v) in (dict, list) else depth))
            continue
        raise SensorAuditError("FORBIDDEN_JSON_TYPE", f"{label}: disallowed type {t.__name__}")


def _require_concrete_path(val: Any, label: str) -> Path:
    require_ok(type(val) in _EXACT_PATH_TYPES, "INVALID_PATH_TYPE", f"{label}: must be concrete pathlib.Path")
    raw = str(val)
    require_ok("\x00" not in raw, "NUL_BYTE_FORBIDDEN", f"{label}: NUL byte forbidden")
    try:
        raw.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise SensorAuditError("INVALID_UTF8_SURROGATE", f"{label}: lone UTF-16 surrogate") from exc
    return val


def _open_dir_chain(dir_parts: Sequence[str], *, start_abs: bool, label: str) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        cur_fd = os.open("/" if start_abs else ".", flags)
    except OSError as exc:
        raise SensorAuditError("FILE_READ_ERROR", f"{label}: base dir open failed ({exc})") from exc
    for comp in dir_parts:
        try:
            nxt_fd = os.open(comp, flags, dir_fd=cur_fd)
        except OSError as exc:
            os.close(cur_fd)
            if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                raise SensorAuditError("SYMLINK_FORBIDDEN", f"{label}: symlink/non-dir ancestor {comp!r}") from exc
            if exc.errno == errno.ENOENT:
                raise SensorAuditError("FILE_NOT_FOUND", f"{label}: missing ancestor {comp!r}") from exc
            raise SensorAuditError("FILE_READ_ERROR", f"{label}: ancestor open failed ({exc})") from exc
        os.close(cur_fd)
        cur_fd = nxt_fd
    return cur_fd


def _verify_logical_pwd(cwd: Path, label: str) -> None:
    pwd = os.environ.get("PWD")
    if pwd is None:
        return
    if not pwd.startswith("/"):
        return
    try:
        st_pwd = os.stat(pwd)
        st_cwd = os.stat(cwd)
    except (OSError, ValueError):
        return
    if (st_pwd.st_dev, st_pwd.st_ino) == (st_cwd.st_dev, st_cwd.st_ino):
        dfd = _open_dir_chain(list(Path(pwd).parts[1:]), start_abs=True, label=label)
        os.close(dfd)


def _split_path_parts(path: Path, label: str) -> Tuple[bool, List[str]]:
    raw_parts = list(path.parts)
    if path.is_absolute():
        raw_parts = raw_parts[1:]
    else:
        try:
            cwd = Path(os.getcwd())
        except OSError as exc:
            raise SensorAuditError("CWD_UNAVAILABLE", f"{label}: CWD unavailable ({exc})") from exc
        _verify_logical_pwd(cwd, label)
        raw_parts = list(cwd.parts)[1:] + raw_parts
    clean: List[str] = []
    for part in raw_parts:
        if part in ("", "."):
            continue
        require_ok(part != "..", "PARENT_TRAVERSAL_FORBIDDEN", f"{label}: '..' component forbidden")
        clean.append(part)
    return True, clean


def read_regular_bytes_safe(path: Path, label: str, *, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    p = _require_concrete_path(path, label)
    _require_exact_int(max_bytes, "max_bytes", lo=1, hi=MAX_FILE_BYTES)
    start_abs, parts = _split_path_parts(p, label)
    require_ok(bool(parts), "NOT_A_REGULAR_FILE", f"{label}: root is not a regular file")
    dfd = _open_dir_chain(parts[:-1], start_abs=start_abs, label=label)
    leaf = parts[-1]
    fd: Optional[int] = None
    try:
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise SensorAuditError("SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden") from exc
            if exc.errno == errno.ENOENT:
                raise SensorAuditError("FILE_NOT_FOUND", f"{label}: file not found") from exc
            raise SensorAuditError("FILE_READ_ERROR", f"{label}: open failed ({exc})") from exc
        st = os.fstat(fd)
        require_ok(stat.S_ISREG(st.st_mode), "NOT_A_REGULAR_FILE", f"{label}: target must be regular file")
        require_ok(st.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: hardlinked file forbidden")
        require_ok(st.st_size <= max_bytes, "FILE_TOO_LARGE", f"{label}: size exceeds {max_bytes} byte cap")
        chunks: List[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, READ_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"{label}: exceeds {max_bytes} byte cap")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        if fd is not None:
            os.close(fd)
        os.close(dfd)


def parse_strict_json_bytes(raw: bytes, label: str) -> Any:
    require_ok(b"\r" not in raw, "CRLF_FORBIDDEN", f"{label}: CRLF/CR forbidden")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise SensorAuditError("INVALID_UTF8", f"{label}: invalid UTF-8 ({exc})") from exc
    require_ok(not text.startswith("\ufeff"), "BOM_FORBIDDEN", f"{label}: UTF-8 BOM forbidden")
    require_ok("\x00" not in text, "NUL_BYTE_FORBIDDEN", f"{label}: NUL byte forbidden")

    # Iterative container nesting depth guard
    depth = 0
    in_str = False
    esc = False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in ("{", "["):
            depth += 1
            require_ok(depth <= MAX_JSON_DEPTH, "JSON_DEPTH_LIMIT", f"{label}: depth > {MAX_JSON_DEPTH}")
        elif ch in ("}", "]"):
            depth -= 1

    def _reject_float(tok: str) -> Any:
        raise SensorAuditError("FLOAT_JSON_FORBIDDEN", f"{label}: float literal {tok!r} forbidden")

    def _reject_const(tok: str) -> Any:
        raise SensorAuditError("NONFINITE_JSON_FORBIDDEN", f"{label}: constant {tok!r} forbidden")

    def _check_int(tok: str) -> int:
        body = tok[1:] if tok.startswith("-") else tok
        require_ok(len(body) <= MAX_INT_DIGITS, "INT_DIGIT_LIMIT", f"{label}: integer > {MAX_INT_DIGITS} digits")
        val = int(tok)
        require_ok(abs(val).bit_length() <= MAX_INT_BITS, "INT_BIT_LIMIT", f"{label}: integer > {MAX_INT_BITS} bits")
        return val

    def _no_dup_pairs(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, v in pairs:
            require_ok(k not in out, "DUPLICATE_JSON_KEY", f"{label}: duplicate key {k!r}")
            out[k] = v
        return out

    try:
        obj = json.loads(
            text,
            parse_float=_reject_float,
            parse_constant=_reject_const,
            parse_int=_check_int,
            object_pairs_hook=_no_dup_pairs,
        )
    except SensorAuditError:
        raise
    except (ValueError, RecursionError) as exc:
        raise SensorAuditError("INVALID_JSON", f"{label}: JSON parse error ({exc})") from exc
    require_ok(type(obj) is dict, "JSON_ROOT_NOT_OBJECT", f"{label}: root must be JSON object")
    return obj


def canonical_json_bytes(obj: Any) -> bytes:
    _validate_json_tree_iter(obj, "canonical_json")
    return (
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n"
    ).encode("utf-8")


# ==============================================================================
# Independent Pure-Z/Q Mathematical Re-Implementation (Zero Shared Code)
# ==============================================================================


def _indep_cov_and_centered(x_q: Sequence[Sequence[Fraction]]) -> Tuple[List[List[Fraction]], List[List[Fraction]]]:
    t_len = len(x_q)
    d = len(x_q[0])
    means = [sum(x_q[t][j] for t in range(t_len)) / t_len for j in range(d)]
    z = [[x_q[t][j] - means[j] for j in range(d)] for t in range(t_len)]
    dens = [math.lcm(*(z[t][j].denominator for t in range(t_len))) for j in range(d)]
    cols_i = [[z[t][j].numerator * (dens[j] // z[t][j].denominator) for t in range(t_len)] for j in range(d)]
    cov = [[Fraction(0) for _ in range(d)] for _ in range(d)]
    for i in range(d):
        ci = cols_i[i]
        di = dens[i] * t_len
        for j in range(i, d):
            val = Fraction(sum(map(mul, ci, cols_i[j])), di * dens[j])
            cov[i][j] = val
            cov[j][i] = val
    return z, cov


def _indep_invert_q(mat: Sequence[Sequence[Fraction]]) -> List[List[Fraction]]:
    n = len(mat)
    a = [list(mat[i]) + [Fraction(1 if i == j else 0) for j in range(n)] for i in range(n)]
    for col in range(n):
        piv_r = -1
        for r in range(col, n):
            if a[r][col] != 0:
                piv_r = r
                break
        require_ok(piv_r >= 0, "SINGULAR_MATRIX", f"singular at col {col}")
        if piv_r != col:
            a[col], a[piv_r] = a[piv_r], a[col]
        pv = a[col][col]
        for c in range(2 * n):
            a[col][c] /= pv
        for r in range(n):
            if r == col:
                continue
            fac = a[r][col]
            if fac == 0:
                continue
            for c in range(2 * n):
                a[r][c] -= fac * a[col][c]
    return [row[n:] for row in a]


def _indep_spd_inertia_q(mat: Sequence[Sequence[Fraction]]) -> Tuple[int, int, int]:
    """Independent exact Sylvester leading-pivot congruence check for symmetric matrices."""
    n = len(mat)
    w = [list(row) for row in mat]
    pos = 0
    zero = 0
    neg = 0
    i = 0
    while i < n:
        if w[i][i] != 0:
            p = w[i][i]
            if p > 0:
                pos += 1
            else:
                neg += 1
            for r in range(i + 1, n):
                if w[r][i] != 0:
                    fac = w[r][i] / p
                    for c in range(i + 1, n):
                        w[r][c] -= fac * w[i][c]
            i += 1
        else:
            sj = -1
            for j in range(i + 1, n):
                if w[i][j] != 0:
                    sj = j
                    break
            if sj < 0:
                zero += 1
                i += 1
            else:
                if sj != i + 1:
                    w[i + 1], w[sj] = w[sj], w[i + 1]
                    for r in range(n):
                        w[r][i + 1], w[r][sj] = w[r][sj], w[r][i + 1]
                b = w[i][i + 1]
                d_val = w[i + 1][i + 1]
                b2 = b * b
                pos += 1
                neg += 1
                for r in range(i + 2, n):
                    u0, u1 = w[r][i], w[r][i + 1]
                    for c in range(i + 2, n):
                        v0, v1 = w[i][c], w[i + 1][c]
                        w[r][c] -= (-d_val * u0 * v0 + b * (u0 * v1 + u1 * v0)) / b2
                i += 2
    return (pos, zero, neg)


def _indep_r2_and_partial(
    cov: Sequence[Sequence[Fraction]],
    lam: Fraction,
) -> Tuple[List[List[Fraction]], List[List[Fraction]], Tuple[int, int, int]]:
    d = len(cov)
    r2 = [[Fraction(1) if i == j else (cov[i][j] * cov[i][j]) / (cov[i][i] * cov[j][j]) for j in range(d)] for i in range(d)]
    reg = [[cov[i][j] + (lam * cov[i][i] if i == j else Fraction(0)) for j in range(d)] for i in range(d)]
    inert = _indep_spd_inertia_q(reg)
    inv_reg = _indep_invert_q(reg)
    p2 = [
        [Fraction(1) if i == j else (inv_reg[i][j] * inv_reg[i][j]) / (inv_reg[i][i] * inv_reg[j][j]) for j in range(d)]
        for i in range(d)
    ]
    return r2, p2, inert


def _indep_modularity_cluster(aff: Sequence[Sequence[Fraction]]) -> Tuple[List[int], Fraction]:
    d = len(aff)
    w = [[0 if i == j else _q12_ticks(aff[i][j]) for j in range(d)] for i in range(d)]
    deg = [sum(w[i]) for i in range(d)]
    two_m = sum(deg)
    if two_m == 0:
        return list(range(d)), Fraction(0)
    two_m_sq = two_m * two_m
    comms: List[List[int]] = [[i] for i in range(d)]

    def _sig(m: Sequence[int]) -> Tuple[int, int, Tuple[int, ...]]:
        return (len(m), sum(deg[u] for u in m), tuple(sorted(deg[u] for u in m)))

    q_num = sum(
        (sum(w[u][v] for u in m for v in m) * two_m) - (sum(deg[u] for u in m) ** 2)
        for m in comms
    )
    while len(comms) > 1:
        best_d = 0
        best_ab: Optional[Tuple[int, int]] = None
        best_t: Optional[Tuple[Any, Any]] = None
        nc = len(comms)
        for a in range(nc):
            ma = comms[a]
            ka = sum(deg[u] for u in ma)
            for b in range(a + 1, nc):
                mb = comms[b]
                kb = sum(deg[u] for u in mb)
                eab = sum(w[u][v] for u in ma for v in mb)
                delta = (2 * eab * two_m) - (2 * ka * kb)
                if delta <= 0:
                    continue
                sa, sb = _sig(ma), _sig(mb)
                ct = (sa, sb) if sa <= sb else (sb, sa)
                if delta > best_d:
                    best_d = delta
                    best_ab = (a, b)
                    best_t = ct
                elif delta == best_d:
                    if ct < best_t:  # type: ignore[operator]
                        best_ab = (a, b)
                        best_t = ct
        if best_ab is None:
            break
        a, b = best_ab
        merged = sorted(comms[a] + comms[b])
        comms = [comms[k] for k in range(nc) if k != a and k != b] + [merged]
        q_num += best_d
    comms_sorted = sorted(comms, key=_sig, reverse=True)
    out = [0] * d
    for cid, m in enumerate(comms_sorted):
        for u in m:
            out[u] = cid
    return out, Fraction(q_num, two_m_sq)


def _indep_ari_q(la: Sequence[Any], lb: Sequence[Any]) -> Fraction:
    n = len(la)
    c2 = lambda k: (k * (k - 1)) // 2
    cnt: Dict[Tuple[Any, Any], int] = {}
    rs: Dict[Any, int] = {}
    cs: Dict[Any, int] = {}
    for a, b in zip(la, lb):
        cnt[(a, b)] = cnt.get((a, b), 0) + 1
        rs[a] = rs.get(a, 0) + 1
        cs[b] = cs.get(b, 0) + 1
    sc = sum(c2(v) for v in cnt.values())
    sa = sum(c2(v) for v in rs.values())
    sb = sum(c2(v) for v in cs.values())
    tot = c2(n)
    exp = Fraction(sa * sb, tot)
    mx = Fraction(sa + sb, 2)
    den = mx - exp
    if den == 0:
        return Fraction(1) if sc == exp else Fraction(0)
    return (Fraction(sc) - exp) / den


def _indep_schur(
    cov: Sequence[Sequence[Fraction]],
    idx_a: Sequence[int],
    idx_b: Sequence[int],
    lam: Fraction,
) -> Dict[str, Any]:
    na, nb = len(idx_a), len(idx_b)
    saa = [[cov[i][j] for j in idx_a] for i in idx_a]
    sab = [[cov[i][j] for j in idx_b] for i in idx_a]
    sba = [[cov[i][j] for j in idx_a] for i in idx_b]
    sbb = [
        [cov[idx_b[r]][idx_b[c]] + (lam * cov[idx_b[r]][idx_b[r]] if r == c else Fraction(0)) for c in range(nb)]
        for r in range(nb)
    ]
    ibb = _indep_invert_q(sbb)
    m_mat = [[sum(ibb[r][k] * sba[k][c] for k in range(nb)) for c in range(na)] for r in range(nb)]
    sch = [[saa[r][c] - sum(sab[r][k] * m_mat[k][c] for k in range(nb)) for c in range(na)] for r in range(na)]
    inert = _indep_spd_inertia_q(sch)
    eta_t = [_q12_ticks(sch[r][r] / saa[r][r]) for r in range(na)]
    off_t = [
        _q12_ticks((sch[r][c] * sch[r][c]) / (sch[r][r] * sch[c][c]))
        for r in range(na)
        for c in range(r + 1, na)
    ]
    raw_t = [
        _q12_ticks((saa[r][c] * saa[r][c]) / (saa[r][r] * saa[c][c]))
        for r in range(na)
        for c in range(r + 1, na)
    ]
    pr_den = Fraction(na * _Q12_SCALE + 2 * sum(off_t), _Q12_SCALE)
    pr = Fraction(na * na) / pr_den
    return {
        "inertia": list(inert),
        "eta_mean": Fraction(sum(eta_t), na * _Q12_SCALE),
        "raw_r2_mean": Fraction(sum(raw_t), len(raw_t) * _Q12_SCALE),
        "off_rho2_mean": Fraction(sum(off_t), len(off_t) * _Q12_SCALE),
        "off_rho2_max": Fraction(max(off_t), _Q12_SCALE),
        "pr": pr,
        "compression": Fraction(na) / pr,
    }


def _indep_asymmetry(
    z: Sequence[Sequence[Fraction]],
    cov: Sequence[Sequence[Fraction]],
    tau: int,
) -> Tuple[Fraction, Fraction, Fraction, List[List[Fraction]], List[List[int]], List[List[Fraction]]]:
    t_len = len(z)
    d = len(z[0])
    ne = t_len - tau
    dens = [math.lcm(*(z[t][j].denominator for t in range(t_len))) for j in range(d)]
    cols_i = [[z[t][j].numerator * (dens[j] // z[t][j].denominator) for t in range(t_len)] for j in range(d)]
    cols_e = [c[:ne] for c in cols_i]
    cols_l = [c[tau:] for c in cols_i]
    a2 = [[Fraction(0) for _ in range(d)] for _ in range(d)]
    dm = [[0 for _ in range(d)] for _ in range(d)]
    gm = [[Fraction(0) for _ in range(d)] for _ in range(d)]
    a2_t: List[int] = []
    gm_t: List[int] = []
    for i in range(d):
        cie = cols_e[i]
        cil = cols_l[i]
        di = dens[i] * ne
        for j in range(i + 1, d):
            scale_d = di * dens[j]
            cij = Fraction(sum(map(mul, cie, cols_l[j])), scale_d)
            cji = Fraction(sum(map(mul, cols_e[j], cil)), scale_d)
            diff = cij - cji
            sm = cij + cji
            val = (diff * diff) / (cov[i][i] * cov[j][j])
            sgn = 1 if diff > 0 else (-1 if diff < 0 else 0)
            gden = sm * sm + diff * diff
            gv = (diff * diff) / gden if gden > 0 else Fraction(0)
            a2[i][j] = a2[j][i] = val
            dm[i][j] = sgn
            dm[j][i] = -sgn
            gm[i][j] = gm[j][i] = gv
            a2_t.append(_q12_ticks(val))
            gm_t.append(_q12_ticks(gv))
    return (
        Fraction(sum(a2_t), len(a2_t) * _Q12_SCALE),
        Fraction(max(a2_t), _Q12_SCALE),
        Fraction(sum(gm_t), len(gm_t) * _Q12_SCALE),
        a2,
        dm,
        gm,
    )


def verify_certificate_dict(raw_obj: Dict[str, Any], raw_sha: str, cert_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Full independent zero-shared-code exact-Q replay and verification of Track S53 certificate."""
    require_ok(type(raw_obj) is dict, "JSON_ROOT_NOT_OBJECT", "raw_obj must be exact dict")
    require_ok(type(cert_obj) is dict, "JSON_ROOT_NOT_OBJECT", "cert_obj must be exact dict")
    require_ok(type(raw_sha) is str, "INVALID_RAW_SHA", "raw_sha must be exact str")
    _validate_json_tree_iter(raw_obj, "raw_obj")
    _validate_json_tree_iter(cert_obj, "cert_obj")

    require_ok(cert_obj.get("schema_version") == SCHEMA_CERT, "SCHEMA_MISMATCH", "bad cert schema")
    require_ok(raw_obj.get("schema_version") == SCHEMA_RAW, "SCHEMA_MISMATCH", "bad raw schema")
    payload = cert_obj.get("payload")
    require_ok(type(payload) is dict, "INVALID_PAYLOAD", "payload must be dict")
    expected_psha = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    require_ok(cert_obj.get("payload_sha256") == expected_psha, "PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")

    require_ok(payload.get("raw_snapshot_sha256") == raw_sha, "RAW_SHA_MISMATCH", "raw snapshot SHA mismatch")
    x_rows = raw_obj.get("X_anonymous")
    gt_ch = raw_obj.get("held_out_ground_truth_channels")
    require_ok(type(x_rows) is list and len(x_rows) >= 8, "INVALID_MATRIX", "X_anonymous must be list len >= 8")
    require_ok(type(gt_ch) is list and len(gt_ch) >= 6, "INVALID_CHANNELS_LIST", "ground truth channels missing")
    for ch in gt_ch:
        require_ok(
            type(ch) is dict and type(ch.get("module")) is str,
            "INVALID_CHANNELS",
            "channel metadata must be dict with str module",
        )
    x_sha = hashlib.sha256(canonical_json_bytes(x_rows)).hexdigest()
    require_ok(raw_obj.get("x_anonymous_sha256") == x_sha, "X_SHA_MISMATCH", "raw x_anonymous_sha256 mismatch")
    require_ok(payload.get("x_anonymous_sha256") == x_sha, "X_SHA_MISMATCH", "cert x_anonymous_sha256 mismatch")
    require_ok(raw_obj.get("sudo_used") is False, "PRIVACY_POLICY", "sudo_used must be False")
    if raw_obj.get("audio_authorized_only") is True:
        require_ok(raw_obj.get("camera_accessed") is False, "PRIVACY_POLICY", "camera_accessed must be False")
        require_ok(raw_obj.get("mic_accessed") is True, "PRIVACY_POLICY", "mic_accessed must be True for authorized audio")
        cw = raw_obj.get("audio_consent_window")
        rc = raw_obj.get("room_noise_covariate")
        require_ok(type(cw) is str and len(cw) > 0, "PRIVACY_POLICY", "audio_consent_window required")
        require_ok(type(rc) is str and len(rc) > 0, "PRIVACY_POLICY", "room_noise_covariate required")
    else:
        require_ok(raw_obj.get("mic_cam_accessed") is False, "PRIVACY_POLICY", "mic_cam_accessed must be False")
        require_ok(raw_obj.get("camera_accessed", False) is False, "PRIVACY_POLICY", "camera_accessed must be False")

    t_len = len(x_rows)
    d_total = len(gt_ch)
    for row in x_rows:
        require_ok(type(row) is list and len(row) == d_total, "INVALID_ROW", "row width mismatch")
        for cell in row:
            _require_exact_int(cell, "X_cell")

    # 1. Zero-variance dropout
    active = [j for j in range(d_total) if min(x_rows[t][j] for t in range(t_len)) != max(x_rows[t][j] for t in range(t_len))]
    zvar = [j for j in range(d_total) if j not in active]
    _require_exact_int_list(payload.get("active_orig_indices"), "ACTIVE_IDX_MISMATCH", "active_orig_indices", active)
    _require_exact_int_list(payload.get("zero_variance_orig_indices"), "ZVAR_IDX_MISMATCH", "zero_variance_orig_indices", zvar)
    d_dyn = len(active)
    _require_exact_int_eq(payload.get("dynamic_channel_count"), d_dyn, "DYN_COUNT_MISMATCH", "dynamic_channel_count")

    lam = parse_exact_q(payload.get("ridge_lambda_q"), "ridge_lambda_q")
    require_ok(lam > 0, "INVALID_RIDGE", "ridge lambda must be > 0")

    x_dyn_q = [[Fraction(x_rows[t][j]) for j in active] for t in range(t_len)]
    z_mat, cov = _indep_cov_and_centered(x_dyn_q)
    r2, p2, reg_inert = _indep_r2_and_partial(cov, lam)
    comm_r2, mod_r2 = _indep_modularity_cluster(r2)
    comm_p2, mod_p2 = _indep_modularity_cluster(p2)

    # 2. Verify Stage-B coupling & clustering
    sb_c = payload.get("stage_b_coupling_and_blind_clustering")
    require_ok(type(sb_c) is dict, "MISSING_SECTION", "missing coupling section")
    _require_exact_int_list(sb_c.get("sigma_reg_inertia"), "INERTIA_MISMATCH", "sigma_reg_inertia", list(reg_inert))
    require_ok(sb_c.get("sigma_reg_is_spd") is (reg_inert == (d_dyn, 0, 0)), "SPD_FLAG_MISMATCH", "SPD flag mismatch")
    num_pairs = (d_dyn * (d_dyn - 1)) // 2
    obs_mr2 = Fraction(
        sum(_q12_ticks(r2[i][j]) for i in range(d_dyn) for j in range(i + 1, d_dyn)),
        num_pairs * _Q12_SCALE,
    )
    require_ok(parse_exact_q(sb_c.get("mean_pair_r2_q"), "mean_pair_r2_q") == q12_floor(obs_mr2), "MEAN_R2_MISMATCH", "mean R^2 mismatch")
    _require_exact_int_list(sb_c.get("blind_r2_labels"), "BLIND_R2_MISMATCH", "blind_r2_labels", comm_r2)
    require_ok(parse_exact_q(sb_c.get("blind_r2_modularity_q"), "mod_r2") == q12_floor(mod_r2), "MOD_R2_MISMATCH", "R^2 modularity mismatch")
    _require_exact_int_list(sb_c.get("blind_p2_labels"), "BLIND_P2_MISMATCH", "blind_p2_labels", comm_p2)
    require_ok(parse_exact_q(sb_c.get("blind_p2_modularity_q"), "mod_p2") == q12_floor(mod_p2), "MOD_P2_MISMATCH", "P^2 modularity mismatch")

    gt_mods = [gt_ch[j]["module"] for j in active]
    ari_r2 = _indep_ari_q(comm_r2, gt_mods)
    ari_p2 = _indep_ari_q(comm_p2, gt_mods)
    require_ok(parse_exact_q(sb_c.get("held_out_ari_r2_q"), "ari_r2") == ari_r2, "ARI_R2_MISMATCH", "ARI R^2 mismatch")
    require_ok(parse_exact_q(sb_c.get("held_out_ari_p2_q"), "ari_p2") == ari_p2, "ARI_P2_MISMATCH", "ARI P^2 mismatch")

    # 3. Verify Stage-A gauge invariance independently
    sa = payload.get("stage_a_gauge_invariance")
    require_ok(type(sa) is dict, "MISSING_SECTION", "missing gauge section")
    gseed = _require_exact_int(sa.get("gauge_seed"), "gauge_seed", lo=0)
    rng_g = random.Random(gseed)
    perm = list(range(d_dyn))
    rng_g.shuffle(perm)
    scales = [Fraction(rng_g.randint(1, 50000), rng_g.randint(1, 500)) for _ in range(d_dyn)]
    shifts = [Fraction(rng_g.randint(-100000, 100000), rng_g.randint(1, 100)) for _ in range(d_dyn)]
    xg = [[scales[perm[nj]] * x_dyn_q[t][perm[nj]] + shifts[perm[nj]] for nj in range(d_dyn)] for t in range(t_len)]
    zg, covg = _indep_cov_and_centered(xg)
    r2g, p2g, _ = _indep_r2_and_partial(covg, lam)
    r2_gauge_ok = all(
        r2g[ni][nj] == r2[perm[ni]][perm[nj]]
        for ni in range(d_dyn)
        for nj in range(d_dyn)
    )
    p2_gauge_ok = all(
        p2g[ni][nj] == p2[perm[ni]][perm[nj]]
        for ni in range(d_dyn)
        for nj in range(d_dyn)
    )
    comm_r2_g, _ = _indep_modularity_cluster(r2g)
    unperm_g = [0] * d_dyn
    for ni in range(d_dyn):
        unperm_g[perm[ni]] = comm_r2_g[ni]
    gauge_ari = _indep_ari_q(comm_r2, unperm_g)
    require_ok(parse_exact_q(sa.get("max_r2_diff_q"), "max_r2_diff_q") == 0, "GAUGE_DIFF_NONZERO", "max_r2_diff != 0")
    require_ok(parse_exact_q(sa.get("max_partial_p2_diff_q"), "max_p2_diff_q") == 0, "GAUGE_DIFF_NONZERO", "max_p2_diff != 0")
    require_ok(
        parse_exact_q(sa.get("blind_cluster_gauge_ari_q"), "gauge_ari") == gauge_ari,
        "GAUGE_ARI_MISMATCH",
        "blind_cluster_gauge_ari_q mismatch",
    )
    require_ok(gauge_ari == 1, "GAUGE_ARI_MISMATCH", "blind cluster gauge ARI != 1")

    # 4. Verify Schur dark modes (blind + physical, independently re-derived partitions)
    sb_s = payload.get("stage_b_schur_dark_modes")
    require_ok(type(sb_s) is dict, "MISSING_SECTION", "missing schur section")
    comm_counts: Dict[int, int] = {}
    for cid in comm_r2:
        comm_counts[cid] = comm_counts.get(cid, 0) + 1
    largest_cid = sorted(comm_counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    exp_ba = [i for i in range(d_dyn) if comm_r2[i] == largest_cid]
    exp_bb = [i for i in range(d_dyn) if comm_r2[i] != largest_cid]
    if len(exp_bb) == 0:
        exp_ba = list(range(d_dyn // 2))
        exp_bb = list(range(d_dyn // 2, d_dyn))
    _require_exact_int_list(sb_s.get("blind_largest_cluster_a_indices"), "INVALID_SCHUR_IDX", "blind_a", exp_ba)
    _require_exact_int_list(sb_s.get("blind_complement_b_indices"), "INVALID_SCHUR_IDX", "blind_b", exp_bb)
    sch_b = _indep_schur(cov, exp_ba, exp_bb, lam)
    cert_sb = sb_s.get("blind_partition_schur")
    require_ok(type(cert_sb) is dict, "MISSING_SCHUR_BLIND", "missing blind schur")
    _require_exact_int_list(cert_sb.get("schur_inertia"), "SCHUR_INERTIA_MISMATCH", "blind_schur_inertia", sch_b["inertia"])
    require_ok(
        parse_exact_q(cert_sb.get("mean_unexplained_variance_eta_q"), "eta_b") == q12_floor(sch_b["eta_mean"]),
        "SCHUR_ETA_MISMATCH",
        "blind eta mismatch",
    )
    require_ok(
        parse_exact_q(cert_sb.get("mean_raw_offdiag_r2_q"), "raw_r2_b") == q12_floor(sch_b["raw_r2_mean"]),
        "SCHUR_RAW_R2_MISMATCH",
        "blind raw R^2 mismatch",
    )
    require_ok(
        parse_exact_q(cert_sb.get("mean_residual_offdiag_rho2_q"), "rho2_b") == q12_floor(sch_b["off_rho2_mean"]),
        "SCHUR_RHO2_MISMATCH",
        "blind rho2 mismatch",
    )
    require_ok(
        parse_exact_q(cert_sb.get("residual_participation_ratio_q"), "pr_b") == q12_floor(sch_b["pr"]),
        "SCHUR_PR_MISMATCH",
        "blind PR mismatch",
    )
    inv_perm = [0] * d_dyn
    for ni, oi in enumerate(perm):
        inv_perm[oi] = ni
    ba_g = [inv_perm[oi] for oi in exp_ba]
    bb_g = [inv_perm[oi] for oi in exp_bb]
    sch_bg = _indep_schur(covg, ba_g, bb_g, lam)
    schur_gauge_ok = all((
        q12_floor(sch_b["eta_mean"]) == q12_floor(sch_bg["eta_mean"]),
        q12_floor(sch_b["off_rho2_mean"]) == q12_floor(sch_bg["off_rho2_mean"]),
        q12_floor(sch_b["pr"]) == q12_floor(sch_bg["pr"]),
    ))
    require_ok(sa.get("schur_gauge_exact_match") is schur_gauge_ok, "GAUGE_SCHUR_FAIL", "schur gauge flag mismatch")

    thermal_mods = ("cpu_die_thermal", "chassis_acpi_thermal", "nvme_thermal")
    exp_pa = [i for i, m in enumerate(gt_mods) if m in thermal_mods]
    exp_pb = [i for i, m in enumerate(gt_mods) if m not in thermal_mods]
    _require_exact_int_list(sb_s.get("physical_thermal_a_indices"), "PHYS_SCHUR_IDX", "phys_a", exp_pa)
    _require_exact_int_list(sb_s.get("physical_driver_b_indices"), "PHYS_SCHUR_IDX", "phys_b", exp_pb)
    cert_sp = sb_s.get("physical_partition_schur")
    if len(exp_pa) >= 2 and len(exp_pb) >= 1:
        require_ok(type(cert_sp) is dict, "MISSING_PHYS_SCHUR", "physical_partition_schur required")
        sch_p = _indep_schur(cov, exp_pa, exp_pb, lam)
        _require_exact_int_list(cert_sp.get("schur_inertia"), "PHYS_SCHUR_INERTIA", "phys_schur_inertia", sch_p["inertia"])
        require_ok(
            parse_exact_q(cert_sp.get("mean_unexplained_variance_eta_q"), "eta_p") == q12_floor(sch_p["eta_mean"]),
            "PHYS_SCHUR_ETA",
            "phys eta mismatch",
        )
        require_ok(
            parse_exact_q(cert_sp.get("mean_raw_offdiag_r2_q"), "raw_r2_p") == q12_floor(sch_p["raw_r2_mean"]),
            "PHYS_SCHUR_RAW_R2",
            "phys raw R^2 mismatch",
        )
        require_ok(
            parse_exact_q(cert_sp.get("mean_residual_offdiag_rho2_q"), "rho2_p") == q12_floor(sch_p["off_rho2_mean"]),
            "PHYS_SCHUR_RHO2",
            "phys rho2 mismatch",
        )
        require_ok(
            parse_exact_q(cert_sp.get("residual_participation_ratio_q"), "pr_p") == q12_floor(sch_p["pr"]),
            "PHYS_SCHUR_PR",
            "phys PR mismatch",
        )
    else:
        require_ok(cert_sp is None, "UNEXPECTED_PHYS_SCHUR", "physical_partition_schur must be None")

    # 5. Verify Time-Reversal Asymmetry across ALL expected lags & gauge invariance
    sb_t = payload.get("stage_b_time_reversal_dissipation")
    require_ok(type(sb_t) is dict, "MISSING_SECTION", "missing asymmetry section")
    cadence_hz = _require_exact_int(raw_obj.get("cadence_hz", 2), "cadence_hz", lo=1, hi=1000)
    is_4hz_long = cadence_hz == 4 and t_len >= 40
    exp_lags: Tuple[int, ...] = (1, 2, 4, 8, 12) if is_4hz_long else (1, 2, 3, 5)
    ptau = 4 if is_4hz_long else 2
    _require_exact_int_eq(sb_t.get("primary_tau"), ptau, "PRIMARY_TAU_MISMATCH", "primary_tau")
    by_lag = sb_t.get("by_lag")
    require_ok(
        type(by_lag) is dict and set(by_lag.keys()) == {str(lv) for lv in exp_lags},
        "MISSING_LAG",
        "by_lag keys mismatch",
    )
    ma2 = Fraction(0)
    asym_gauge_ok = False
    for lag_v in exp_lags:
        lag_rec = by_lag[str(lag_v)]
        require_ok(type(lag_rec) is dict, "INVALID_LAG_REC", f"lag {lag_v} must be dict")
        _require_exact_int_eq(lag_rec.get("tau"), lag_v, "LAG_TAU_MISMATCH", f"lag_{lag_v}.tau")
        la2, lxa2, lgm, _a2m, _dm, _gm = _indep_asymmetry(z_mat, cov, lag_v)
        require_ok(parse_exact_q(lag_rec.get("mean_asymmetry_a2_q"), "mean_a2") == q12_floor(la2), "MEAN_A2_MISMATCH", "mean A^2 mismatch")
        require_ok(parse_exact_q(lag_rec.get("max_asymmetry_a2_q"), "max_a2") == q12_floor(lxa2), "MAX_A2_MISMATCH", "max A^2 mismatch")
        require_ok(
            parse_exact_q(lag_rec.get("mean_dissipation_gamma_q"), "mean_gamma") == q12_floor(lgm),
            "MEAN_GAMMA_MISMATCH",
            "mean Gamma mismatch",
        )
        if lag_v == ptau:
            ma2 = la2
            ma2_g, mxa2_g, mgm_g, _, _, _ = _indep_asymmetry(zg, covg, ptau)
            asym_gauge_ok = all((la2 == ma2_g, lxa2 == mxa2_g, lgm == mgm_g))
    require_ok(
        sa.get("asymmetry_gauge_exact_match") is asym_gauge_ok,
        "GAUGE_ASYM_FAIL",
        "asymmetry gauge flag mismatch",
    )
    require_ok(
        sa.get("all_gauge_invariants_exact") is all((r2_gauge_ok, p2_gauge_ok, gauge_ari == 1, schur_gauge_ok, asym_gauge_ok)),
        "GAUGE_FLAG_FALSE",
        "gauge invariance flag false",
    )

    # 5b. Independently verify pure-Q SI-2019 Landauer Thermodynamic Erasure Bridge (required iff RAPL & Package present)
    rapl_pkg = [
        j for j, ch in enumerate(gt_ch)
        if (ch.get("module"), ch.get("device")) == ("cpu_rapl_energy_uj", "intel-rapl:0")
    ]
    pkg_tmp = [
        j for j, ch in enumerate(gt_ch)
        if (ch.get("module"), ch.get("label")) == ("cpu_die_thermal", "Package id 0")
    ]
    lb = sb_t.get("landauer_thermodynamic_bridge")
    if rapl_pkg and pkg_tmp:
        require_ok(type(lb) is dict and lb.get("oracle_class") == "exact", "INVALID_LANDAUER", "landauer section required")
        tot_uj = sum(x_rows[t][rapl_pkg[0]] for t in range(t_len))
        _require_exact_int_eq(lb.get("total_energy_uj"), tot_uj, "RAPL_ENERGY_MISMATCH", "total_energy_uj")
        mt_mc = Fraction(sum(x_rows[t][pkg_tmp[0]] for t in range(t_len)), t_len)
        mt_k = (mt_mc / Fraction(1000)) + Fraction(27315, 100)
        require_ok(
            parse_exact_q(lb.get("mean_package_temp_kelvin_q"), "mean_t_k") == q12_floor(mt_k),
            "LANDAUER_TEMP_MISMATCH",
            "mean package temp Kelvin mismatch",
        )
        kb = Fraction(1380649, 10**29)
        ln2_lo = Fraction(693147180559, 10**12)
        ln2_hi = Fraction(693147180560, 10**12)
        tot_j = Fraction(tot_uj, 10**6)
        eb_lo = kb * mt_k * ln2_lo
        eb_hi = kb * mt_k * ln2_hi
        q_lo = tot_j / eb_hi
        q_hi = tot_j / eb_lo
        b_lo = q_lo.numerator // q_lo.denominator
        b_hi = (q_hi.numerator + q_hi.denominator - 1) // q_hi.denominator
        _require_exact_int_eq(lb.get("landauer_bits_lower_bound"), b_lo, "LANDAUER_LO_MISMATCH", "landauer_bits_lower_bound")
        _require_exact_int_eq(lb.get("landauer_bits_upper_bound"), b_hi, "LANDAUER_HI_MISMATCH", "landauer_bits_upper_bound")
        _require_exact_int_eq(lb.get("s38_qfree_reversible_bits"), 0, "S38_QFREE_MISMATCH", "s38_qfree_reversible_bits")
        require_ok(
            lb.get("s38_mfree_single_and_bracket_bits_q") == ["19/16", "6/5"],
            "S38_MFREE_MISMATCH",
            "S38 Landauer bracket mismatch",
        )
        el_ms = max(1, _require_exact_int(raw_obj.get("elapsed_ms"), "elapsed_ms", lo=1))
        mp_w = tot_j / Fraction(el_ms, 1000)
        require_ok(
            parse_exact_q(lb.get("mean_package_power_w_q"), "mean_p_w") == q12_floor(mp_w),
            "LANDAUER_POWER_MISMATCH",
            "mean package power W mismatch",
        )
    else:
        require_ok(lb is None, "UNEXPECTED_LANDAUER", "landauer section must be None without RAPL/Package")

    # 6. Verify Exact Circular-Shift Null, IAAFT Schema/Grid Bounds, & Split-Half Out-of-Sample Replication
    nulls = payload.get("adversarial_nulls_and_replication")
    require_ok(type(nulls) is dict, "MISSING_NULLS", "missing nulls section")
    cn = nulls.get("circular_shift_null_exact")
    require_ok(type(cn) is dict and cn.get("oracle_class") == "exact", "INVALID_CIRC_NULL", "bad circular null")
    n_surr = _require_exact_int(cn.get("n_surrogates"), "n_surrogates", lo=10, hi=2000)
    n_seed = _require_exact_int(cn.get("seed"), "null_seed", lo=0)
    require_ok(parse_exact_q(cn.get("obs_mean_r2_q"), "obs_mr2") == q12_floor(obs_mr2), "NULL_OBS_R2_MISMATCH", "null obs R^2 mismatch")
    require_ok(parse_exact_q(cn.get("obs_mean_a2_q"), "obs_ma2") == q12_floor(ma2), "NULL_OBS_A2_MISMATCH", "null obs A^2 mismatch")

    # Independently replay circular-shift null
    cols_int = [[x_rows[t][j] for t in range(t_len)] for j in active]
    rng_n = random.Random(n_seed)
    min_sh = max(5, t_len // 10)
    max_sh = t_len - min_sh
    ne = t_len - ptau
    s_num = t_len * t_len * _Q12_SCALE
    s_den = ne * ne
    ge_r2 = 0
    ge_a2 = 0
    for _ in range(n_surr):
        z_cols: List[List[int]] = []
        v_cols: List[int] = []
        for col in cols_int:
            sh = rng_n.randint(min_sh, max_sh)
            sc = col[sh:] + col[:sh]
            sm = sum(sc)
            zc = [t_len * v - sm for v in sc]
            z_cols.append(zc)
            v_cols.append(sum(u * u for u in zc))
        z_cols_e = [zc[:ne] for zc in z_cols]
        z_cols_l = [zc[ptau:] for zc in z_cols]
        r2_t_acc = 0
        a2_t_acc = 0
        for i in range(d_dyn):
            zi = z_cols[i]
            vi = v_cols[i]
            zi_e = z_cols_e[i]
            zi_l = z_cols_l[i]
            for j in range(i + 1, d_dyn):
                zj = z_cols[j]
                dv = vi * v_cols[j]
                d0 = sum(map(mul, zi, zj))
                r2_t_acc += (d0 * d0 * _Q12_SCALE) // dv
                dij = sum(map(mul, zi_e, z_cols_l[j]))
                dji = sum(map(mul, z_cols_e[j], zi_l))
                df = dij - dji
                a2_t_acc += (s_num * df * df) // (s_den * dv)
        if Fraction(r2_t_acc, num_pairs * _Q12_SCALE) >= obs_mr2:
            ge_r2 += 1
        if Fraction(a2_t_acc, num_pairs * _Q12_SCALE) >= ma2:
            ge_a2 += 1
    require_ok(
        parse_exact_q(cn.get("p_mean_r2_q"), "p_r2") == Fraction(ge_r2 + 1, n_surr + 1),
        "CIRC_P_R2_MISMATCH",
        "circular-shift p(R^2) mismatch",
    )
    require_ok(
        parse_exact_q(cn.get("p_mean_a2_q"), "p_a2") == Fraction(ge_a2 + 1, n_surr + 1),
        "CIRC_P_A2_MISMATCH",
        "circular-shift p(A^2) mismatch",
    )

    iaaft = nulls.get("iaaft_null_sampled")
    require_ok(type(iaaft) is dict and iaaft.get("oracle_class") == "sampled", "INVALID_IAAFT", "bad IAAFT metadata")
    if iaaft.get("available") is True:
        n_ia = _require_exact_int(iaaft.get("n_surrogates"), "iaaft_n_surr", lo=10, hi=2000)
        pr2_i = parse_exact_q(iaaft.get("p_mean_r2_q"), "iaaft_p_r2")
        pa2_i = parse_exact_q(iaaft.get("p_mean_a2_q"), "iaaft_p_a2")
        require_ok(
            Fraction(0) < pr2_i <= Fraction(1) and (pr2_i * (n_ia + 1)).denominator == 1,
            "IAAFT_P_BOUNDS",
            "IAAFT p(R^2) out of grid (0,1]",
        )
        require_ok(
            Fraction(0) < pa2_i <= Fraction(1) and (pa2_i * (n_ia + 1)).denominator == 1,
            "IAAFT_P_BOUNDS",
            "IAAFT p(A^2) out of grid (0,1]",
        )
        require_ok(parse_exact_q(iaaft.get("z_squared_mean_r2_q"), "iaaft_z2_r2") >= 0, "IAAFT_Z2_NEG", "z^2 < 0")
        require_ok(parse_exact_q(iaaft.get("z_squared_mean_a2_q"), "iaaft_z2_a2") >= 0, "IAAFT_Z2_NEG", "z^2 < 0")

    sh_rec = nulls.get("split_half_replication_exact")
    require_ok(type(sh_rec) is dict, "MISSING_SPLIT_HALF", "missing split_half_replication_exact")
    mid = t_len // 2
    h1_q = x_dyn_q[:mid]
    h2_q = x_dyn_q[mid : 2 * mid]
    both_dyn = [
        j
        for j in range(d_dyn)
        if (min(h1_q[t][j] for t in range(mid)) != max(h1_q[t][j] for t in range(mid)))
        and (min(h2_q[t][j] for t in range(mid)) != max(h2_q[t][j] for t in range(mid)))
    ]
    _require_exact_int_eq(sh_rec.get("both_halves_dynamic_count"), len(both_dyn), "SPLIT_HALF_MISMATCH", "both_halves_dynamic_count")
    _require_exact_int_eq(sh_rec.get("half_len"), mid, "SPLIT_HALF_MISMATCH", "half_len")
    if len(both_dyn) >= 4:
        h1_sub = [[row[j] for j in both_dyn] for row in h1_q]
        h2_sub = [[row[j] for j in both_dyn] for row in h2_q]
        z1, s1 = _indep_cov_and_centered(h1_sub)
        z2, s2 = _indep_cov_and_centered(h2_sub)
        nb = len(both_dyn)
        r2_h1 = [[Fraction(1) if i == j else (s1[i][j] * s1[i][j]) / (s1[i][i] * s1[j][j]) for j in range(nb)] for i in range(nb)]
        r2_h2 = [[Fraction(1) if i == j else (s2[i][j] * s2[i][j]) / (s2[i][i] * s2[j][j]) for j in range(nb)] for i in range(nb)]
        c_h1, _ = _indep_modularity_cluster(r2_h1)
        c_h2, _ = _indep_modularity_cluster(r2_h2)
        split_ari = _indep_ari_q(c_h1, c_h2)
        ma1, _, _, a2_1, dm_1, gm_1 = _indep_asymmetry(z1, s1, ptau)
        ma2_h, _, _, _, dm_2, _ = _indep_asymmetry(z2, s2, ptau)
        pairs_1 = [(a2_1[i][j], dm_1[i][j], i, j, gm_1[i][j]) for i in range(nb) for j in range(i + 1, nb)]
        top_k = sorted(pairs_1, key=lambda r: (r[0], r[4]), reverse=True)[:10]
        agree = sum(1 for r in top_k if r[1] != 0 and dm_2[r[2]][r[3]] == r[1])
        require_ok(
            parse_exact_q(sh_rec.get("split_half_cluster_ari_q"), "split_ari") == split_ari,
            "SPLIT_HALF_MISMATCH",
            "split_half_cluster_ari_q mismatch",
        )
        _require_exact_int_eq(sh_rec.get("top10_arrow_sign_matches"), agree, "SPLIT_HALF_MISMATCH", "top10_arrow_sign_matches")
        _require_exact_int_eq(sh_rec.get("top10_arrow_count"), len(top_k), "SPLIT_HALF_MISMATCH", "top10_arrow_count")
        exp_conc = Fraction(agree, len(top_k)) if top_k else Fraction(0)
        require_ok(
            parse_exact_q(sh_rec.get("top10_arrow_sign_concordance_q"), "split_conc") == exp_conc,
            "SPLIT_HALF_MISMATCH",
            "top10_arrow_sign_concordance_q mismatch",
        )
        require_ok(
            parse_exact_q(sh_rec.get("half1_mean_a2_q"), "h1_a2") == q12_floor(ma1),
            "SPLIT_HALF_MISMATCH",
            "half1_mean_a2_q mismatch",
        )
        require_ok(
            parse_exact_q(sh_rec.get("half2_mean_a2_q"), "h2_a2") == q12_floor(ma2_h),
            "SPLIT_HALF_MISMATCH",
            "half2_mean_a2_q mismatch",
        )

    return {
        "valid": True,
        "payload_sha256": expected_psha,
        "raw_snapshot_sha256": raw_sha,
        "dynamic_channel_count": d_dyn,
        "gauge_invariance_exact": True,
        "blind_r2_clusters": len(set(comm_r2)),
        "held_out_ari_r2_q": fmt_q(ari_r2),
        "blind_schur_pr_q": fmt_q(q12_floor(sch_b["pr"])),
        "primary_tau": ptau,
        "mean_asymmetry_a2_q": fmt_q(q12_floor(ma2)),
        "circ_p_mean_r2_q": fmt_q(Fraction(ge_r2 + 1, n_surr + 1)),
        "circ_p_mean_a2_q": fmt_q(Fraction(ge_a2 + 1, n_surr + 1)),
    }


def run_self_test() -> Dict[str, Any]:
    """Deterministic zero-float self-test covering mathematical controls & Zone-B tamper kills."""
    # Control 1: Strictly time-symmetric synthetic signal -> A^2(tau) == 0 identically!
    sym_rows: List[List[Fraction]] = []
    for t in range(20):
        # Palindromic waves (x[t] == x[19-t]) guarantee exact time-reversal symmetry C_ij(tau) == C_ji(tau)
        u = min(t, 19 - t)
        sym_rows.append([Fraction(u * u), Fraction(3 * u + 1), Fraction((u - 4) * (u - 4))])
    zs, cs = _indep_cov_and_centered(sym_rows)
    ma2_sym, mxa2_sym, _, _, _, _ = _indep_asymmetry(zs, cs, 2)
    sym_ok = all((ma2_sym == 0, mxa2_sym == 0))

    # Control 2: One-way causal lag chain x1[t] = x0[t-1] -> strictly positive A^2(1) and dir(0->1) == +1!
    base_wave = [1, 4, 2, 7, 3, 9, 1, 5, 8, 2, 6, 4, 10, 3, 7, 2, 5, 9, 4, 6]
    causal_rows = [
        [Fraction(base_wave[t]), Fraction(base_wave[t - 1] if t > 0 else base_wave[0])]
        for t in range(len(base_wave))
    ]
    zc, cc = _indep_cov_and_centered(causal_rows)
    ma2_c, _, _, _, dm_c, _ = _indep_asymmetry(zc, cc, 1)
    causal_ok = all((ma2_c > 0, dm_c[0][1] == 1))

    # Control 3: Hidden common-driver dark mode S_{A|B}: A0 = H + e0, A1 = H + e1, B0 = independent
    # Conditioning on B0 leaves rho^2_{A0,A1|B0} > 0 (detecting hidden reservoir H!)
    h_wave = [2, 5, 1, 6, 3, 7, 2, 8, 4, 6, 1, 5, 7, 3, 8, 2]
    b_wave = [1, -1, 1, -1, 2, -2, 2, -2, 1, -1, 1, -1, 2, -2, 2, -2]
    e0 = [1, 0, -1, 0, 1, 0, -1, 0, 1, 0, -1, 0, 1, 0, -1, 0]
    e1 = [0, 1, 0, -1, 0, 1, 0, -1, 0, 1, 0, -1, 0, 1, 0, -1]
    dm_rows = [
        [Fraction(3 * h_wave[t] + e0[t]), Fraction(3 * h_wave[t] + e1[t]), Fraction(b_wave[t])]
        for t in range(len(h_wave))
    ]
    _, cdm = _indep_cov_and_centered(dm_rows)
    sch_dm = _indep_schur(cdm, [0, 1], [2], Fraction(1, 20))
    dark_ok = all((
        sch_dm["inertia"] == [2, 0, 0],
        sch_dm["off_rho2_mean"] > Fraction(1, 2),
        sch_dm["pr"] < Fraction(3, 2),
    ))

    # Control 4: Zone-B parser tampers (float, dup key, crlf, zero denom, non-canon) must all fail closed
    killed: List[str] = []
    for name, fn in (
        ("zoneb_float_json", lambda: parse_strict_json_bytes(b'{"a": 1.5}\n', "t")),
        ("zoneb_dup_key", lambda: parse_strict_json_bytes(b'{"a": 1, "a": 2}\n', "t")),
        ("zoneb_crlf", lambda: parse_strict_json_bytes(b'{"a": 1}\r\n', "t")),
        ("zoneb_zero_denom", lambda: parse_exact_q("1/0", "t")),
        ("zoneb_noncanon_q", lambda: parse_exact_q("2/4", "t")),
    ):
        failed_closed = False
        try:
            fn()
        except SensorAuditError:
            failed_closed = True
        if failed_closed:
            killed.append(name)

    return {
        "self_test_passed": all((sym_ok, causal_ok, dark_ok, len(killed) == 5)),
        "symmetric_control_a2_q": fmt_q(ma2_sym),
        "causal_control_a2_q": fmt_q(ma2_c),
        "causal_control_dir": dm_c[0][1],
        "dark_mode_control_pr_q": fmt_q(sch_dm["pr"]),
        "dark_mode_control_rho2_q": fmt_q(sch_dm["off_rho2_mean"]),
        "tamper_controls_killed": len(killed),
        "killed_cases": killed,
    }


def _validate_argv(argv: Optional[Sequence[str]]) -> Optional[List[str]]:
    if argv is None:
        return None
    require_ok(type(argv) in (list, tuple), "INVALID_ARGV", "argv must be list/tuple")
    out: List[str] = []
    for tok in argv:
        require_ok(type(tok) is str, "INVALID_ARGV", "argv token must be exact str")
        require_ok("\x00" not in tok, "NUL_BYTE_FORBIDDEN", "NUL in argv")
        try:
            tok.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise SensorAuditError("INVALID_UTF8_SURROGATE", "lone surrogate in argv") from exc
        out.append(tok)
    return out


_CERT_TO_DEFAULT_RAW: Dict[str, str] = {
    "pre_rapl_baseline_certificate.json": "pre_rapl_baseline_snapshot.json",
    "sensor_tomography_certificate.json": "raw_sensor_snapshot.json",
    "phase2_controlled_certificate.json": "phase2_controlled_snapshot.json",
}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Track S53 Independent Zero-Shared-Code Verifier")
    parser.add_argument("--self-test", action="store_true", help="Run deterministic mathematical & Zone-B self-test")
    parser.add_argument("--raw", type=Path, default=None, help="Path to raw_sensor_snapshot.json")
    parser.add_argument("--check", type=Path, default=None, help="Path to sensor_tomography_certificate.json")
    try:
        checked = _validate_argv(argv)
    except SensorAuditError as exc:
        sys.stderr.write(json.dumps({"error": True, "code": exc.code, "detail": exc.detail}, sort_keys=True) + "\n")
        return 2
    try:
        args = parser.parse_args(checked)
    except SystemExit as exc:
        return int(exc.code) if type(exc.code) is int else 2

    try:
        if args.self_test or args.check is None:
            res = run_self_test()
            print(json.dumps(res, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
            return 0
        if args.raw is not None:
            raw_p = args.raw
        elif args.check.name in _CERT_TO_DEFAULT_RAW:
            raw_p = args.check.parent / _CERT_TO_DEFAULT_RAW[args.check.name]
        else:
            # Auto-pair fallback restricted to known certificate names. A missing
            # certificate file still fails below with FILE_NOT_FOUND via the normal
            # read path; an existing but unknown certificate name fails closed here.
            read_regular_bytes_safe(args.check, "certificate")
            raise SensorAuditError(
                "UNKNOWN_CERT_NO_DEFAULT_RAW",
                "no --raw given and certificate name has no known default raw pairing",
            )
        raw_bytes = read_regular_bytes_safe(raw_p, "raw_snapshot")
        cert_bytes = read_regular_bytes_safe(args.check, "certificate")
        raw_obj = parse_strict_json_bytes(raw_bytes, "raw_snapshot")
        cert_obj = parse_strict_json_bytes(cert_bytes, "certificate")
        raw_sha = hashlib.sha256(raw_bytes).hexdigest()
        res = verify_certificate_dict(raw_obj, raw_sha, cert_obj)
        print(json.dumps(res, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
        return 0
    except SensorAuditError as exc:
        sys.stderr.write(json.dumps({"error": True, "code": exc.code, "detail": exc.detail}, sort_keys=True) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
