#!/usr/bin/env python3
"""Track S38 (Portal 36): Nested Simulation & Silq Boundary-Typing Calculus.

Pure Python 3 standard library over exact Z / Q / D[i, sqrt(2)].
Zero external dependencies, zero AST floats, zero float() calls, zero bare
asserts, zero .isdigit()/.isnumeric()/.isdecimal(), zero RNG calls.

Formalizes Portal 36 (Level 0 Continuum -> Level 1 Simulated !T Determinism ->
Level 2 silq-lang/silq Boundary Compiler) across four mathematical pillars:
  P1: Exact dyadic cyclotomic ring D[i, sqrt(2)] = Z[1/2, sqrt(2), i] Clifford+T
      unitary engine, group relations, and exact Born probability conservation.
  P2: Executable static core silq-lang/silq type-checker enforcing !T vs linear T,
      const, qfree, lifted, mfree, forget, and measure laws.
  P3: Exact uncomputation vs dropped-garbage entanglement & Portal 35 partial-trace
      theorem (rho_O = Tr_H rho_OH, purity Tr(rho_O^2) in Q, linear entropy S_L).
  P4: Exact Landauer erasure vs reversible Toffoli bijection accounting (Landauer
      1961, N0) and Level-0 / Level-1 / Level-2 nested-simulation complexity gap.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import hmac
import json
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "aletheia.silq_boundary_calculus.certificate.v1"
TRACK_ID = "TRACK-S38-SILQ-NESTED-BOUNDARY-CALCULUS"

MAX_JSON_BYTES = 1_048_576
HARD_MAX_BYTES_CAP = 64 * 1024 * 1024
MAX_JSON_DEPTH = 64
MAX_INT_BITS = 2048
MAX_INT_DIGITS = 617
MAX_RATIONAL_CHARS = 2 * MAX_INT_DIGITS + 2
MAX_FORMAT_BITS = 4096

_HEX_LOWER = frozenset("0123456789abcdef")
_ASCII_DIGITS = frozenset("0123456789")
_CERT_KEYS = frozenset({"schema", "track_id", "payload_sha256", "certificate_sha256", "payload"})
_PILLAR_KEYS = (
    "pillar1_cyclotomic_clifford_t",
    "pillar2_silq_static_typechecker",
    "pillar3_uncomputation_partial_trace",
    "pillar4_landauer_nested_simulation",
)
_PAYLOAD_KEYS = frozenset({
    "oracle_class",
    "novelty_classification",
    "literature_anchors_n0",
    "zero_floats_exact_arithmetic",
    "all_verified",
    *_PILLAR_KEYS,
})
_ALLOWED_BOOL_KEYS = frozenset({
    "CCX2_eq_I",
    "CNOT2_eq_I",
    "CZ2_eq_I",
    "H2_eq_I",
    "HXH_eq_Z",
    "HZH_eq_X",
    "IH_CNOT_IH_eq_CZ",
    "S2_eq_Z",
    "T2_eq_S",
    "T4_eq_Z",
    "T8_eq_I",
    "X2_eq_I",
    "Y2_eq_I",
    "Z2_eq_I",
    "algebraic_group_isomorphic_l0_l2",
    "all_born_nonneg",
    "all_dyadic",
    "all_gates_unitary_and_dyadic",
    "all_group_relations_verified",
    "all_must_fail_rejected",
    "all_valid_accepted",
    "all_verified",
    "all_witnesses_unit_norm",
    "born_sum_is_one",
    "erasure_bracket_verified",
    "hermitian",
    "interference_destroyed",
    "interference_preserved",
    "involution_verified",
    "is_bijection",
    "is_dyadic",
    "is_unitary",
    "must_fail_non_unitary_rejected",
    "overhead_strictly_increasing_from_n2",
    "pillar_verified",
    "purity_imag_and_sqrt2_zero",
    "purity_strictly_dropped",
    "trace_is_one",
    "well_typed",
    "zero_floats_exact_arithmetic",
})

Q0 = Fraction(0, 1)
Q1 = Fraction(1, 1)
Q2 = Fraction(2, 1)
QHALF = Fraction(1, 2)

CyclotomicAmp = tuple[Fraction, Fraction, Fraction, Fraction]
CycMatrix = list[list[CyclotomicAmp]]

CYC_ZERO: CyclotomicAmp = (Q0, Q0, Q0, Q0)
CYC_ONE: CyclotomicAmp = (Q1, Q0, Q0, Q0)
CYC_NEG_ONE: CyclotomicAmp = (-Q1, Q0, Q0, Q0)
CYC_I: CyclotomicAmp = (Q0, Q0, Q1, Q0)
CYC_NEG_I: CyclotomicAmp = (Q0, Q0, -Q1, Q0)
CYC_INV_SQRT2: CyclotomicAmp = (Q0, QHALF, Q0, Q0)
CYC_NEG_INV_SQRT2: CyclotomicAmp = (Q0, -QHALF, Q0, Q0)
CYC_OMEGA8: CyclotomicAmp = (Q0, QHALF, Q0, QHALF)


class SilqBoundaryError(ValueError):
    """Fail-closed typed error (never stripped by python3 -O)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


# ---------------------------------------------------------------------------
# Zone-B Exact Primitives: Types, Bounded Int/Rational, Decimal, JSON, SHA256
# ---------------------------------------------------------------------------

def require_bool(val: Any, label: str) -> bool:
    if type(val) is not bool:
        raise SilqBoundaryError("INVALID_BOOL", f"{label} must be exact bool")
    return val


def require_int(val: Any, label: str, lo: int | None = None, hi: int | None = None) -> int:
    if type(val) is not int:
        raise SilqBoundaryError("INVALID_INT", f"{label} must be exact int")
    if lo is not None and val < lo:
        raise SilqBoundaryError("INT_OUT_OF_RANGE", f"{label} < {lo}")
    if hi is not None and val > hi:
        raise SilqBoundaryError("INT_OUT_OF_RANGE", f"{label} > {hi}")
    return val


def require_str(val: Any, label: str, max_len: int = MAX_JSON_BYTES) -> str:
    cap = require_int(max_len, f"{label}.max_len", lo=1, hi=HARD_MAX_BYTES_CAP)
    if type(val) is not str:
        raise SilqBoundaryError("INVALID_STR", f"{label} must be exact str")
    if len(val) > cap:
        raise SilqBoundaryError("STR_TOO_LONG", f"{label} exceeds length {cap}")
    try:
        val.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise SilqBoundaryError("INVALID_UTF8_SURROGATE", f"{label} contains lone UTF-16 surrogate") from exc
    return val


def require_hex64(val: Any, label: str) -> str:
    s = require_str(val, label, max_len=64)
    if len(s) != 64 or any(ch not in _HEX_LOWER for ch in s):
        raise SilqBoundaryError("INVALID_HEX64", f"{label} must be 64 lowercase hex chars")
    return s


def constant_time_hex64_equal(left: Any, right: Any, label: str) -> bool:
    a = require_hex64(left, f"{label}.left")
    b = require_hex64(right, f"{label}.right")
    return hmac.compare_digest(a.encode("ascii"), b.encode("ascii"))


def _is_canonical_ascii_digits(s: str) -> bool:
    if not s:
        return False
    if any(ch not in _ASCII_DIGITS for ch in s):
        return False
    if len(s) > 1 and s[0] == "0":
        return False
    return True


def parse_bounded_int(raw: Any, label: str = "int", lo: int | None = None, hi: int | None = None) -> int:
    """Strictly parse exact int or canonical ASCII integer string within optional [lo, hi]."""
    t = type(raw)
    if t is int:
        if raw.bit_length() > MAX_INT_BITS:
            raise SilqBoundaryError("INT_TOO_LARGE", f"{label} exceeds bit limit")
        val = raw
    elif t is str:
        if len(raw) > MAX_INT_DIGITS + 1:
            raise SilqBoundaryError("INVALID_INT_STR", f"{label} string oversized")
        neg = raw.startswith("-")
        digits = raw[1:] if neg else raw
        if not _is_canonical_ascii_digits(digits):
            raise SilqBoundaryError("INVALID_INT_STR", f"{label} not canonical ASCII integer")
        if neg and digits == "0":
            raise SilqBoundaryError("INVALID_INT_STR", f"{label} negative zero forbidden")
        val = -int(digits) if neg else int(digits)
        if val.bit_length() > MAX_INT_BITS:
            raise SilqBoundaryError("INT_TOO_LARGE", f"{label} exceeds bit limit")
    else:
        raise SilqBoundaryError("INVALID_INT", f"{label} must be exact int or str")
    return require_int(val, label, lo=lo, hi=hi)


def parse_exact_rational(raw: Any, label: str = "rational") -> Fraction:
    """Strictly parse exact int, Fraction, or canonical ASCII rational ('p' or 'p/q')."""
    t = type(raw)
    if t is int:
        if raw.bit_length() > MAX_INT_BITS:
            raise SilqBoundaryError("RATIONAL_TOO_LARGE", f"{label} exceeds bit limit")
        return Fraction(raw, 1)
    if t is Fraction:
        if raw.numerator.bit_length() > MAX_INT_BITS or raw.denominator.bit_length() > MAX_INT_BITS:
            raise SilqBoundaryError("RATIONAL_TOO_LARGE", f"{label} fraction exceeds bit limit")
        return raw
    if t is not str:
        raise SilqBoundaryError("INVALID_RATIONAL_TYPE", f"{label} must be int, Fraction, or str")
    if len(raw) > MAX_RATIONAL_CHARS:
        raise SilqBoundaryError("INVALID_RATIONAL_STR", f"{label} string oversized")
    parts = raw.split("/")
    if len(parts) == 1:
        num_s, den_s = parts[0], None
    elif len(parts) == 2:
        num_s, den_s = parts[0], parts[1]
    else:
        raise SilqBoundaryError("INVALID_RATIONAL_STR", f"{label} contains multiple '/'")
    neg = num_s.startswith("-")
    num_digits = num_s[1:] if neg else num_s
    if not _is_canonical_ascii_digits(num_digits):
        raise SilqBoundaryError("INVALID_RATIONAL_STR", f"{label} numerator not canonical ASCII digits")
    if neg and num_digits == "0":
        raise SilqBoundaryError("INVALID_RATIONAL_STR", f"{label} negative zero forbidden")
    num_val = -int(num_digits) if neg else int(num_digits)
    if den_s is None:
        den_val = 1
    else:
        if not _is_canonical_ascii_digits(den_s):
            raise SilqBoundaryError("INVALID_RATIONAL_STR", f"{label} denominator not canonical ASCII digits")
        den_val = int(den_s)
        if den_val <= 1:
            raise SilqBoundaryError("INVALID_RATIONAL_STR", f"{label} denominator must be > 1")
        reduced = Fraction(num_val, den_val)
        if reduced.denominator != den_val:
            raise SilqBoundaryError("NON_CANONICAL_RATIONAL", f"{label} fraction is not reduced")
    if num_val.bit_length() > MAX_INT_BITS or den_val.bit_length() > MAX_INT_BITS:
        raise SilqBoundaryError("RATIONAL_TOO_LARGE", f"{label} exceeds bit limit")
    return Fraction(num_val, den_val)


def format_rational(val: Any, label: str = "rational") -> str:
    if type(val) is not Fraction:
        raise SilqBoundaryError("INVALID_RATIONAL_TYPE", f"{label} must be exact Fraction")
    if val.numerator.bit_length() > MAX_FORMAT_BITS or val.denominator.bit_length() > MAX_FORMAT_BITS:
        raise SilqBoundaryError("RATIONAL_TOO_LARGE", f"{label} exceeds formatting limit")
    if val.denominator == 1:
        return str(val.numerator)
    return f"{val.numerator}/{val.denominator}"


def format_decimal_trunc(val: Any, places: int = 4, label: str = "decimal") -> str:
    """Exact pure-integer decimal truncation with '-0.00'/'-0' normalized to non-negative zero."""
    if type(val) is not Fraction:
        raise SilqBoundaryError("INVALID_RATIONAL_TYPE", f"{label} must be exact Fraction")
    dp = require_int(places, f"{label}.places", lo=0, hi=24)
    if val.numerator.bit_length() > MAX_FORMAT_BITS or val.denominator.bit_length() > MAX_FORMAT_BITS:
        raise SilqBoundaryError("RATIONAL_TOO_LARGE", f"{label} exceeds formatting limit")
    neg = val.numerator < 0
    scale = 10 ** dp
    scaled = (abs(val.numerator) * scale) // val.denominator
    if scaled == 0:
        neg = False
    sign = "-" if neg else ""
    if dp == 0:
        return f"{sign}{scaled}"
    whole, frac = divmod(scaled, scale)
    return f"{sign}{whole}.{frac:0{dp}d}"


def _int_exceeds_limits(val: int) -> bool:
    return val.bit_length() > MAX_INT_BITS


def validate_json_tree_iterative(obj: Any, max_depth: int = MAX_JSON_DEPTH) -> None:
    """Iterative Zone-B validator blocking cycles, depth overflow, floats, subclasses, huge ints, surrogates."""
    limit = require_int(max_depth, "max_depth", lo=1, hi=256)
    stack: list[tuple[Any, int, bool]] = [(obj, 0, False)]
    active_ids: set[int] = set()
    while stack:
        cur, depth, leaving = stack.pop()
        if leaving:
            active_ids.discard(id(cur))
            continue
        if depth > limit:
            raise SilqBoundaryError("JSON_DEPTH_EXCEEDED", f"JSON nesting exceeds depth {limit}")
        t = type(cur)
        if t is dict:
            cid = id(cur)
            if cid in active_ids:
                raise SilqBoundaryError("JSON_CYCLE", "cyclic dict forbidden")
            active_ids.add(cid)
            stack.append((cur, depth, True))
            for k, v in cur.items():
                require_str(k, "json_key")
                stack.append((v, depth + 1, False))
        elif t is list:
            cid = id(cur)
            if cid in active_ids:
                raise SilqBoundaryError("JSON_CYCLE", "cyclic list forbidden")
            active_ids.add(cid)
            stack.append((cur, depth, True))
            for item in cur:
                stack.append((item, depth + 1, False))
        elif t is str:
            require_str(cur, "json_str")
        elif t is int:
            if _int_exceeds_limits(cur):
                raise SilqBoundaryError("INT_TOO_LARGE", "integer exceeds Zone-B digit/bit limits")
        elif t is bool or cur is None:
            continue
        else:
            raise SilqBoundaryError("FORBIDDEN_JSON_TYPE", f"forbidden type {t.__name__}")


def _strict_object_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise SilqBoundaryError("DUPLICATE_JSON_KEY", f"duplicate key {k!r}")
        out[k] = v
    return out


def _reject_float_literal(tok: str) -> Any:
    raise SilqBoundaryError("FLOAT_FORBIDDEN", f"JSON float literal forbidden: {tok}")


def _reject_constant_literal(tok: str) -> Any:
    raise SilqBoundaryError("NONFINITE_CONSTANT", f"JSON non-finite constant forbidden: {tok}")


def parse_strict_json_text(text: Any, require_object: bool = True, max_bytes: int = MAX_JSON_BYTES) -> Any:
    require_bool(require_object, "require_object")
    cap = require_int(max_bytes, "max_bytes", lo=1, hi=HARD_MAX_BYTES_CAP)
    s = require_str(text, "json_text", max_len=cap)
    if len(s.encode("utf-8")) > cap:
        raise SilqBoundaryError("JSON_TOO_LARGE", f"JSON UTF-8 bytes exceed {cap}")
    try:
        parsed = json.loads(
            s,
            object_pairs_hook=_strict_object_pairs_hook,
            parse_float=_reject_float_literal,
            parse_constant=_reject_constant_literal,
        )
    except SilqBoundaryError:
        raise
    except RecursionError as exc:
        raise SilqBoundaryError("JSON_DEPTH_EXCEEDED", "JSON nesting exceeded parser recursion limit") from exc
    except ValueError as exc:
        raise SilqBoundaryError("INVALID_JSON", f"invalid JSON syntax or int digits: {type(exc).__name__}") from exc
    validate_json_tree_iterative(parsed)
    if require_object and type(parsed) is not dict:
        raise SilqBoundaryError("JSON_NOT_OBJECT", "JSON root must be an object")
    return parsed


def canonical_json_bytes(obj: Any) -> bytes:
    validate_json_tree_iterative(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def sha256_hex(data: Any) -> str:
    if type(data) is not bytes:
        raise SilqBoundaryError("INVALID_BYTES", "sha256_hex requires exact bytes")
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Pillar 1: Exact Dyadic Cyclotomic Ring D[i, sqrt(2)] & Clifford+T Engine
# ---------------------------------------------------------------------------

def cyc_make(a: Any, b: Any = Q0, c: Any = Q0, d: Any = Q0) -> CyclotomicAmp:
    """Construct exact element a + b*sqrt(2) + i*(c + d*sqrt(2)) in Q(sqrt(2), i)."""
    return (
        parse_exact_rational(a, "cyc.a"),
        parse_exact_rational(b, "cyc.b"),
        parse_exact_rational(c, "cyc.c"),
        parse_exact_rational(d, "cyc.d"),
    )


def _require_cyc(z: Any, label: str = "cyc") -> CyclotomicAmp:
    if type(z) is not tuple or len(z) != 4:
        raise SilqBoundaryError("INVALID_CYCLOTOMIC", f"{label} must be 4-tuple of Fraction")
    return (
        parse_exact_rational(z[0], f"{label}[0]"),
        parse_exact_rational(z[1], f"{label}[1]"),
        parse_exact_rational(z[2], f"{label}[2]"),
        parse_exact_rational(z[3], f"{label}[3]"),
    )


def cyc_add(z1: Any, z2: Any) -> CyclotomicAmp:
    a1, b1, c1, d1 = _require_cyc(z1, "z1")
    a2, b2, c2, d2 = _require_cyc(z2, "z2")
    return (a1 + a2, b1 + b2, c1 + c2, d1 + d2)


def cyc_sub(z1: Any, z2: Any) -> CyclotomicAmp:
    a1, b1, c1, d1 = _require_cyc(z1, "z1")
    a2, b2, c2, d2 = _require_cyc(z2, "z2")
    return (a1 - a2, b1 - b2, c1 - c2, d1 - d2)


def cyc_mul(z1: Any, z2: Any) -> CyclotomicAmp:
    a1, b1, c1, d1 = _require_cyc(z1, "z1")
    a2, b2, c2, d2 = _require_cyc(z2, "z2")
    ra = (a1 * a2 + Q2 * b1 * b2) - (c1 * c2 + Q2 * d1 * d2)
    rb = (a1 * b2 + b1 * a2) - (c1 * d2 + d1 * c2)
    ic = (a1 * c2 + Q2 * b1 * d2) + (c1 * a2 + Q2 * d1 * b2)
    id_ = (a1 * d2 + b1 * c2) + (c1 * b2 + d1 * a2)
    return (ra, rb, ic, id_)


def cyc_conj(z: Any) -> CyclotomicAmp:
    a, b, c, d = _require_cyc(z, "z")
    return (a, b, -c, -d)


def cyc_abs_sq(z: Any) -> tuple[Fraction, Fraction]:
    """Exact |z|^2 = u + v*sqrt(2) in Q[sqrt(2)] (returns (u, v))."""
    a, b, c, d = _require_cyc(z, "z")
    u = a * a + Q2 * b * b + c * c + Q2 * d * d
    v = Q2 * (a * b + c * d)
    return (u, v)


def _qsqrt2_nonneg(u: Any, v: Any) -> bool:
    """Exact algebraic sign test u + v*sqrt(2) >= 0 without floats."""
    if type(u) is not Fraction or type(v) is not Fraction:
        raise SilqBoundaryError("INVALID_RATIONAL_TYPE", "_qsqrt2_nonneg requires exact Fraction inputs")
    if u >= Q0 and v >= Q0:
        return True
    if u < Q0 and v <= Q0:
        return False
    if u >= Q0:
        return u * u >= Q2 * v * v
    return Q2 * v * v >= u * u


def cyc_is_dyadic(z: Any) -> bool:
    """True iff all 4 rational components have exact power-of-2 denominators (in Z[1/2, sqrt(2), i])."""
    comps = _require_cyc(z, "z")
    return all((q.denominator & (q.denominator - 1)) == 0 for q in comps)


def cyc_format(z: Any) -> list[str]:
    a, b, c, d = _require_cyc(z, "z")
    return [format_rational(a), format_rational(b), format_rational(c), format_rational(d)]


def _require_cyc_matrix(mat: Any, label: str = "matrix") -> CycMatrix:
    if type(mat) not in (list, tuple) or len(mat) == 0:
        raise SilqBoundaryError("INVALID_MATRIX", f"{label} must be non-empty list/tuple")
    n = len(mat)
    out: CycMatrix = []
    for r_idx, row in enumerate(mat):
        if type(row) not in (list, tuple) or len(row) != n:
            raise SilqBoundaryError("INVALID_MATRIX", f"{label} row {r_idx} must have length {n}")
        out.append([_require_cyc(cell, f"{label}[{r_idx}][{c_idx}]") for c_idx, cell in enumerate(row)])
    return out


def mat_identity_cyc(dim: int) -> CycMatrix:
    n = require_int(dim, "dim", lo=1, hi=16)
    return [[CYC_ONE if r == c else CYC_ZERO for c in range(n)] for r in range(n)]


def mat_mul_cyc(m1: Any, m2: Any) -> CycMatrix:
    a = _require_cyc_matrix(m1, "m1")
    b = _require_cyc_matrix(m2, "m2")
    n = len(a)
    if len(b) != n:
        raise SilqBoundaryError("MATRIX_DIM_MISMATCH", "matrix dimensions must match")
    out: CycMatrix = []
    for r in range(n):
        row: list[CyclotomicAmp] = []
        for c in range(n):
            acc = CYC_ZERO
            for k in range(n):
                acc = cyc_add(acc, cyc_mul(a[r][k], b[k][c]))
            row.append(acc)
        out.append(row)
    return out


def mat_dagger_cyc(mat: Any) -> CycMatrix:
    a = _require_cyc_matrix(mat, "mat")
    n = len(a)
    return [[cyc_conj(a[c][r]) for c in range(n)] for r in range(n)]


def mat_kron_cyc(m1: Any, m2: Any) -> CycMatrix:
    a = _require_cyc_matrix(m1, "m1")
    b = _require_cyc_matrix(m2, "m2")
    na, nb = len(a), len(b)
    if na * nb > 16:
        raise SilqBoundaryError("MATRIX_TOO_LARGE", "Kronecker product dimension capped at 16")
    out: CycMatrix = []
    for ra in range(na):
        for rb in range(nb):
            row: list[CyclotomicAmp] = []
            for ca in range(na):
                for cb in range(nb):
                    row.append(cyc_mul(a[ra][ca], b[rb][cb]))
            out.append(row)
    return out


def is_unitary_cyc(mat: Any) -> bool:
    """True iff square cyclotomic matrix satisfies U^dagger * U = I (hence U * U^dagger = I)."""
    a = _require_cyc_matrix(mat, "mat")
    return mat_mul_cyc(mat_dagger_cyc(a), a) == mat_identity_cyc(len(a))


def is_matrix_dyadic(mat: Any) -> bool:
    a = _require_cyc_matrix(mat, "mat")
    return all(cyc_is_dyadic(cell) for row in a for cell in row)


def _canonical_gates() -> dict[str, CycMatrix]:
    g_x: CycMatrix = [[CYC_ZERO, CYC_ONE], [CYC_ONE, CYC_ZERO]]
    g_y: CycMatrix = [[CYC_ZERO, CYC_NEG_I], [CYC_I, CYC_ZERO]]
    g_z: CycMatrix = [[CYC_ONE, CYC_ZERO], [CYC_ZERO, CYC_NEG_ONE]]
    g_h: CycMatrix = [[CYC_INV_SQRT2, CYC_INV_SQRT2], [CYC_INV_SQRT2, CYC_NEG_INV_SQRT2]]
    g_s: CycMatrix = [[CYC_ONE, CYC_ZERO], [CYC_ZERO, CYC_I]]
    g_t: CycMatrix = [[CYC_ONE, CYC_ZERO], [CYC_ZERO, CYC_OMEGA8]]
    g_cnot: CycMatrix = [
        [CYC_ONE, CYC_ZERO, CYC_ZERO, CYC_ZERO],
        [CYC_ZERO, CYC_ONE, CYC_ZERO, CYC_ZERO],
        [CYC_ZERO, CYC_ZERO, CYC_ZERO, CYC_ONE],
        [CYC_ZERO, CYC_ZERO, CYC_ONE, CYC_ZERO],
    ]
    g_cz: CycMatrix = [
        [CYC_ONE, CYC_ZERO, CYC_ZERO, CYC_ZERO],
        [CYC_ZERO, CYC_ONE, CYC_ZERO, CYC_ZERO],
        [CYC_ZERO, CYC_ZERO, CYC_ONE, CYC_ZERO],
        [CYC_ZERO, CYC_ZERO, CYC_ZERO, CYC_NEG_ONE],
    ]
    g_ccx = mat_identity_cyc(8)
    g_ccx[6][6] = CYC_ZERO
    g_ccx[7][7] = CYC_ZERO
    g_ccx[6][7] = CYC_ONE
    g_ccx[7][6] = CYC_ONE
    return {
        "X": g_x,
        "Y": g_y,
        "Z": g_z,
        "H": g_h,
        "S": g_s,
        "T": g_t,
        "CNOT": g_cnot,
        "CZ": g_cz,
        "CCX": g_ccx,
    }


def apply_gate_state(
    state: Sequence[Any],
    n_qubits: int,
    gate_matrix: Any,
    targets: Sequence[int],
) -> list[CyclotomicAmp]:
    """Apply an exact k-qubit cyclotomic matrix (k in 1..3) to an n-qubit state vector."""
    nq = require_int(n_qubits, "n_qubits", lo=1, hi=5)
    dim = 1 << nq
    if type(state) not in (list, tuple) or len(state) != dim:
        raise SilqBoundaryError("INVALID_STATE", f"state must be list/tuple of length {dim}")
    vec = [_require_cyc(amp, f"state[{i}]") for i, amp in enumerate(state)]
    mat = _require_cyc_matrix(gate_matrix, "gate_matrix")
    if type(targets) not in (list, tuple) or len(targets) == 0:
        raise SilqBoundaryError("INVALID_TARGETS", "targets must be non-empty list/tuple")
    t_list = [require_int(q, f"targets[{i}]", lo=0, hi=nq - 1) for i, q in enumerate(targets)]
    if len(set(t_list)) != len(t_list):
        raise SilqBoundaryError("DUPLICATE_TARGET_QUBIT", "target qubits must be distinct")
    k = len(t_list)
    if len(mat) != (1 << k):
        raise SilqBoundaryError("GATE_TARGET_MISMATCH", f"gate dim {len(mat)} != 2^{k}")

    # Qubit 0 is MSB (bit nq - 1), qubit q is bit (nq - 1 - q)
    bit_pos = [nq - 1 - q for q in t_list]
    out: list[CyclotomicAmp] = [CYC_ZERO] * dim
    for idx in range(dim):
        amp = vec[idx]
        if amp == CYC_ZERO:
            continue
        col = 0
        base = idx
        for j, bp in enumerate(bit_pos):
            bval = (idx >> bp) & 1
            col = (col << 1) | bval
            base &= ~(1 << bp)
        for row in range(1 << k):
            entry = mat[row][col]
            if entry == CYC_ZERO:
                continue
            dst = base
            for j, bp in enumerate(bit_pos):
                if (row >> (k - 1 - j)) & 1:
                    dst |= 1 << bp
            out[dst] = cyc_add(out[dst], cyc_mul(entry, amp))
    return out


def state_born_summary(state: Sequence[Any]) -> dict[str, Any]:
    """Compute exact Born probabilities |z_k|^2 in Q[sqrt(2)] and verify unit norm."""
    if type(state) not in (list, tuple) or len(state) == 0:
        raise SilqBoundaryError("INVALID_STATE", "state must be non-empty list/tuple")
    vec = [_require_cyc(amp, f"state[{i}]") for i, amp in enumerate(state)]
    probs: list[list[str]] = []
    sum_u = Q0
    sum_v = Q0
    all_nonneg = True
    for amp in vec:
        u, v = cyc_abs_sq(amp)
        sum_u += u
        sum_v += v
        if not _qsqrt2_nonneg(u, v):
            all_nonneg = False
        probs.append([format_rational(u), format_rational(v)])
    return {
        "born_probs_qsqrt2": probs,
        "sum_q": format_rational(sum_u),
        "sum_sqrt2": format_rational(sum_v),
        "born_sum_is_one": sum_u == Q1 and sum_v == Q0,
        "all_born_nonneg": all_nonneg,
        "all_dyadic": all(cyc_is_dyadic(z) for z in vec),
    }


def build_pillar1_cyclotomic() -> dict[str, Any]:
    gates = _canonical_gates()
    gate_certs: list[dict[str, Any]] = []
    for name in ("X", "Y", "Z", "H", "S", "T", "CNOT", "CZ", "CCX"):
        m = gates[name]
        gate_certs.append({
            "gate": name,
            "dim": len(m),
            "is_unitary": is_unitary_cyc(m),
            "is_dyadic": is_matrix_dyadic(m),
        })

    i2 = mat_identity_cyc(2)
    i4 = mat_identity_cyc(4)
    i8 = mat_identity_cyc(8)
    t2 = mat_mul_cyc(gates["T"], gates["T"])
    t4 = mat_mul_cyc(t2, t2)
    t8 = mat_mul_cyc(t4, t4)
    i_kron_h = mat_kron_cyc(i2, gates["H"])
    relations = {
        "X2_eq_I": mat_mul_cyc(gates["X"], gates["X"]) == i2,
        "Y2_eq_I": mat_mul_cyc(gates["Y"], gates["Y"]) == i2,
        "Z2_eq_I": mat_mul_cyc(gates["Z"], gates["Z"]) == i2,
        "H2_eq_I": mat_mul_cyc(gates["H"], gates["H"]) == i2,
        "T2_eq_S": t2 == gates["S"],
        "S2_eq_Z": mat_mul_cyc(gates["S"], gates["S"]) == gates["Z"],
        "T4_eq_Z": t4 == gates["Z"],
        "T8_eq_I": t8 == i2,
        "HXH_eq_Z": mat_mul_cyc(mat_mul_cyc(gates["H"], gates["X"]), gates["H"]) == gates["Z"],
        "HZH_eq_X": mat_mul_cyc(mat_mul_cyc(gates["H"], gates["Z"]), gates["H"]) == gates["X"],
        "CNOT2_eq_I": mat_mul_cyc(gates["CNOT"], gates["CNOT"]) == i4,
        "CZ2_eq_I": mat_mul_cyc(gates["CZ"], gates["CZ"]) == i4,
        "IH_CNOT_IH_eq_CZ": mat_mul_cyc(mat_mul_cyc(i_kron_h, gates["CNOT"]), i_kron_h) == gates["CZ"],
        "CCX2_eq_I": mat_mul_cyc(gates["CCX"], gates["CCX"]) == i8,
    }

    # Exact Born witnesses on Clifford+T states
    s_bell = apply_gate_state([CYC_ONE, CYC_ZERO, CYC_ZERO, CYC_ZERO], 2, gates["H"], [0])
    s_bell = apply_gate_state(s_bell, 2, gates["CNOT"], [0, 1])

    s_magic = apply_gate_state([CYC_ONE, CYC_ZERO], 1, gates["H"], [0])
    s_magic = apply_gate_state(s_magic, 1, gates["T"], [0])
    s_magic_h = apply_gate_state(s_magic, 1, gates["H"], [0])

    s_ghz = apply_gate_state([CYC_ONE] + [CYC_ZERO] * 7, 3, gates["H"], [0])
    s_ghz = apply_gate_state(s_ghz, 3, gates["CNOT"], [0, 1])
    s_ghz = apply_gate_state(s_ghz, 3, gates["CNOT"], [1, 2])

    s_toff = apply_gate_state([CYC_ONE] + [CYC_ZERO] * 7, 3, gates["H"], [0])
    s_toff = apply_gate_state(s_toff, 3, gates["H"], [1])
    s_toff = apply_gate_state(s_toff, 3, gates["CCX"], [0, 1, 2])

    witnesses = {
        "bell_pair": state_born_summary(s_bell),
        "magic_HTH_ket0": state_born_summary(s_magic_h),
        "ghz_3q": state_born_summary(s_ghz),
        "toffoli_superposed": state_born_summary(s_toff),
    }

    non_unitary = [[CYC_ONE, CYC_ONE], [CYC_ZERO, CYC_ONE]]
    non_unitary_rejected = not is_unitary_cyc(non_unitary)

    all_gates_ok = all(all((g["is_unitary"], g["is_dyadic"])) for g in gate_certs)
    all_rels_ok = all(relations.values())
    all_wit_ok = all(all((w["born_sum_is_one"], w["all_born_nonneg"], w["all_dyadic"])) for w in witnesses.values())

    return {
        "ring_representation": "a + b*sqrt(2) + i*(c + d*sqrt(2)), (a,b,c,d) in D^4",
        "gate_certifications": gate_certs,
        "group_relations_verified": relations,
        "born_witnesses": witnesses,
        "all_gates_unitary_and_dyadic": all_gates_ok,
        "all_group_relations_verified": all_rels_ok,
        "all_witnesses_unit_norm": all_wit_ok,
        "must_fail_non_unitary_rejected": non_unitary_rejected,
        "pillar_verified": all((all_gates_ok, all_rels_ok, all_wit_ok, non_unitary_rejected)),
    }


# ---------------------------------------------------------------------------
# Pillar 2: Executable Static silq-lang/silq Core Type-Checker
# ---------------------------------------------------------------------------

_VALID_TYPES = frozenset({"!B", "B"})
_VALID_ANNOTATIONS = frozenset({"qfree", "lifted", "mfree", "general"})
_QFREE_GATES = frozenset({"X", "CNOT", "CCX"})
_UNITARY_NON_DIAG_GATES = frozenset({"H", "Y"})
_UNITARY_DIAG_GATES = frozenset({"Z", "S", "T", "CZ", "phase"})
_ALL_UNITARY_GATES = _UNITARY_NON_DIAG_GATES | _UNITARY_DIAG_GATES
_GATE_CTRL_ARITY: dict[str, int] = {
    "X": 0,
    "Y": 0,
    "Z": 0,
    "H": 0,
    "S": 0,
    "T": 0,
    "phase": 0,
    "CNOT": 1,
    "CZ": 1,
    "CCX": 2,
}


def _require_ident(raw: Any, label: str) -> str:
    s = require_str(raw, label, max_len=64)
    if not s:
        raise SilqBoundaryError("INVALID_IDENT", f"{label} identifier cannot be empty")
    return s


def typecheck_silq_program(prog: Any) -> dict[str, Any]:
    """Static Silq core type-checker enforcing !T vs T, const, qfree, lifted, mfree, forget, measure."""
    if type(prog) is not dict:
        raise SilqBoundaryError("INVALID_PROGRAM", "program must be strict dict")
    name = _require_ident(prog.get("name"), "program.name")
    ann = require_str(prog.get("annotation"), "program.annotation", max_len=16)
    if ann not in _VALID_ANNOTATIONS:
        raise SilqBoundaryError("INVALID_ANNOTATION", f"unsupported annotation {ann!r}")
    params = prog.get("params")
    body = prog.get("body")
    ret_vars = prog.get("returns")
    if type(params) is not list or type(body) is not list or type(ret_vars) is not list:
        raise SilqBoundaryError("INVALID_PROGRAM_STRUCTURE", "params, body, returns must be strict lists")

    # Symbol table: var -> {type, const, live, lifted_deps, inverse_gate, tainted_by, order}
    env: dict[str, dict[str, Any]] = {}
    order_seq = 0
    synthesized: list[str] = []

    def _reject(code: str, detail: str) -> dict[str, Any]:
        return {
            "name": name,
            "annotation": ann,
            "well_typed": False,
            "type_error_code": code,
            "type_error_detail": detail,
            "synthesized_uncomputations": synthesized,
        }

    for p_idx, pspec in enumerate(params):
        if type(pspec) is not dict:
            raise SilqBoundaryError("INVALID_PARAM", f"params[{p_idx}] must be dict")
        pname = _require_ident(pspec.get("name"), f"params[{p_idx}].name")
        ptype = require_str(pspec.get("type"), f"params[{p_idx}].type", max_len=8)
        if ptype not in _VALID_TYPES:
            raise SilqBoundaryError("INVALID_PARAM_TYPE", f"unsupported type {ptype!r}")
        pconst = require_bool(pspec.get("const"), f"params[{p_idx}].const")
        if pname in env:
            raise SilqBoundaryError("DUPLICATE_PARAM", f"duplicate parameter {pname}")
        if ann == "lifted" and ptype == "B" and not pconst:
            return _reject("LIFTED_REQUIRES_CONST_QPARAMS", f"lifted param {pname}: B must be const")
        order_seq += 1
        env[pname] = {
            "type": ptype,
            "const": pconst,
            "live": True,
            "lifted_deps": None,
            "inverse_gate": None,
            "tainted_by": None,
            "order": order_seq,
        }

    def _is_live(var_name: str) -> bool:
        return var_name in env and env[var_name]["live"]

    def _taint_dependents(var_name: str) -> None:
        env[var_name]["tainted_by"] = var_name
        for info in env.values():
            if info["lifted_deps"] is not None and var_name in info["lifted_deps"]:
                info["tainted_by"] = var_name

    def _can_auto_uncompute(var_name: str) -> bool:
        info = env[var_name]
        if info["lifted_deps"] is None or info["tainted_by"] is not None:
            return False
        return all(env[dep]["live"] for dep in info["lifted_deps"])

    for s_idx, stmt in enumerate(body):
        if type(stmt) is not dict:
            raise SilqBoundaryError("INVALID_STMT", f"body[{s_idx}] must be dict")
        op = require_str(stmt.get("op"), f"body[{s_idx}].op", max_len=32)

        if op == "alloc_q":
            dst = _require_ident(stmt.get("dst"), f"body[{s_idx}].dst")
            if dst in env:
                raise SilqBoundaryError("DUPLICATE_VAR", f"variable {dst} already bound")
            order_seq += 1
            env[dst] = {
                "type": "B",
                "const": False,
                "live": True,
                "lifted_deps": None,
                "inverse_gate": None,
                "tainted_by": None,
                "order": order_seq,
            }

        elif op == "lifted_and":
            dst = _require_ident(stmt.get("dst"), f"body[{s_idx}].dst")
            c1 = _require_ident(stmt.get("ctrl1"), f"body[{s_idx}].ctrl1")
            c2 = _require_ident(stmt.get("ctrl2"), f"body[{s_idx}].ctrl2")
            if dst in env:
                raise SilqBoundaryError("DUPLICATE_VAR", f"variable {dst} already bound")
            if not all((_is_live(c1), _is_live(c2))):
                return _reject("UNBOUND_OR_DEAD_VAR", f"lifted_and requires live operands {c1}, {c2}")
            if c1 == c2:
                return _reject("QUANTUM_CLONING_FORBIDDEN", f"lifted_and cannot alias control {c1}")
            if env[c1]["type"] != "B" or env[c2]["type"] != "B":
                return _reject("TYPE_MISMATCH", f"lifted_and requires quantum B controls, got {env[c1]['type']}, {env[c2]['type']}")
            order_seq += 1
            env[dst] = {
                "type": "B",
                "const": False,
                "live": True,
                "lifted_deps": frozenset({c1, c2}),
                "inverse_gate": f"CCX({c1},{c2},{dst})",
                "tainted_by": None,
                "order": order_seq,
            }

        elif op == "qfree_gate":
            gate = require_str(stmt.get("gate"), f"body[{s_idx}].gate", max_len=16)
            if gate not in _QFREE_GATES:
                raise SilqBoundaryError("INVALID_GATE", f"unsupported qfree gate {gate!r}")
            ctrls = stmt.get("controls")
            tgt = _require_ident(stmt.get("target"), f"body[{s_idx}].target")
            if type(ctrls) is not list:
                raise SilqBoundaryError("INVALID_CONTROLS", "controls must be list")
            ctrl_names = [_require_ident(c, f"body[{s_idx}].controls[{ci}]") for ci, c in enumerate(ctrls)]
            if len(ctrl_names) != _GATE_CTRL_ARITY[gate]:
                return _reject("GATE_ARITY_MISMATCH", f"gate {gate} requires {_GATE_CTRL_ARITY[gate]} controls")
            all_wires = [*ctrl_names, tgt]
            if len(set(all_wires)) != len(all_wires):
                return _reject("QUANTUM_CLONING_FORBIDDEN", f"aliased qubits in {gate}")
            if not all(_is_live(w) for w in all_wires):
                return _reject("UNBOUND_OR_DEAD_VAR", f"dead or unbound wire in {gate}")
            if any(env[w]["type"] != "B" for w in all_wires):
                return _reject("TYPE_MISMATCH", f"quantum gate {gate} requires quantum B wires")
            if env[tgt]["const"]:
                return _reject("CONST_MODIFICATION_FORBIDDEN", f"cannot mutate const parameter {tgt} with {gate}")
            _taint_dependents(tgt)

        elif op == "unitary_gate":
            gate = require_str(stmt.get("gate"), f"body[{s_idx}].gate", max_len=16)
            if gate not in _ALL_UNITARY_GATES:
                raise SilqBoundaryError("INVALID_GATE", f"unsupported unitary gate {gate!r}")
            if ann in ("qfree", "lifted"):
                return _reject("NON_QFREE_OP_IN_QFREE", f"gate {gate} forbidden inside {ann} function")
            ctrls = stmt.get("controls")
            tgt = _require_ident(stmt.get("target"), f"body[{s_idx}].target")
            if type(ctrls) is not list:
                raise SilqBoundaryError("INVALID_CONTROLS", "controls must be list")
            ctrl_names = [_require_ident(c, f"body[{s_idx}].controls[{ci}]") for ci, c in enumerate(ctrls)]
            if len(ctrl_names) != _GATE_CTRL_ARITY[gate]:
                return _reject("GATE_ARITY_MISMATCH", f"gate {gate} requires {_GATE_CTRL_ARITY[gate]} controls")
            all_wires = [*ctrl_names, tgt]
            if len(set(all_wires)) != len(all_wires):
                return _reject("QUANTUM_CLONING_FORBIDDEN", f"aliased qubits in {gate}")
            if not all(_is_live(w) for w in all_wires):
                return _reject("UNBOUND_OR_DEAD_VAR", f"dead or unbound wire in {gate}")
            if any(env[w]["type"] != "B" for w in all_wires):
                return _reject("TYPE_MISMATCH", f"unitary gate {gate} requires quantum B wires")
            if any(env[w]["const"] for w in all_wires):
                return _reject("CONST_MODIFICATION_FORBIDDEN", f"cannot apply unitary {gate} to const parameter")
            if gate in _UNITARY_NON_DIAG_GATES:
                _taint_dependents(tgt)

        elif op == "dup":
            src = _require_ident(stmt.get("src"), f"body[{s_idx}].src")
            dst = _require_ident(stmt.get("dst"), f"body[{s_idx}].dst")
            if dst in env:
                raise SilqBoundaryError("DUPLICATE_VAR", f"variable {dst} already bound")
            if not _is_live(src):
                return _reject("UNBOUND_OR_DEAD_VAR", f"dup source {src} unbound or dead")
            if env[src]["type"] != "!B":
                return _reject("QUANTUM_CLONING_FORBIDDEN", f"cannot clone linear quantum variable {src}: B")
            order_seq += 1
            env[dst] = {
                "type": "!B",
                "const": False,
                "live": True,
                "lifted_deps": None,
                "inverse_gate": None,
                "tainted_by": None,
                "order": order_seq,
            }

        elif op == "measure":
            src = _require_ident(stmt.get("src"), f"body[{s_idx}].src")
            dst = _require_ident(stmt.get("dst"), f"body[{s_idx}].dst")
            if dst in env:
                raise SilqBoundaryError("DUPLICATE_VAR", f"variable {dst} already bound")
            if ann in ("mfree", "qfree", "lifted"):
                return _reject("MEASURE_IN_MFREE_OR_QFREE", f"measure forbidden inside {ann} function")
            if not _is_live(src):
                return _reject("UNBOUND_OR_DEAD_VAR", f"measure source {src} unbound or dead")
            if env[src]["type"] != "B":
                return _reject("TYPE_MISMATCH", f"measure requires quantum variable B, got {env[src]['type']}")
            if env[src]["const"]:
                return _reject("CONST_CONSUMPTION_FORBIDDEN", f"cannot measure/consume const parameter {src}")
            env[src]["live"] = False
            _taint_dependents(src)
            order_seq += 1
            env[dst] = {
                "type": "!B",
                "const": False,
                "live": True,
                "lifted_deps": None,
                "inverse_gate": None,
                "tainted_by": None,
                "order": order_seq,
            }

        elif op == "forget":
            var = _require_ident(stmt.get("var"), f"body[{s_idx}].var")
            if not _is_live(var):
                return _reject("UNBOUND_OR_DEAD_VAR", f"forget target {var} unbound or dead")
            if not _can_auto_uncompute(var):
                return _reject("UNCOMPUTATION_FAILED", f"cannot uncompute {var} (not lifted or dependency mutated)")
            synthesized.append(env[var]["inverse_gate"])
            env[var]["live"] = False

        else:
            raise SilqBoundaryError("UNKNOWN_OP", f"unsupported Silq IR op {op!r}")

    # Validate return list and perform Silq block-exit automatic uncomputation (LIFO order)
    ret_names = [_require_ident(r, f"returns[{ri}]") for ri, r in enumerate(ret_vars)]
    if len(set(ret_names)) != len(ret_names):
        return _reject("QUANTUM_CLONING_FORBIDDEN", "duplicate variable in return list")
    for r in ret_names:
        if not _is_live(r):
            return _reject("UNBOUND_OR_DEAD_VAR", f"returned variable {r} is unbound or consumed")
        if env[r]["const"] and env[r]["type"] == "B":
            return _reject("CONST_CONSUMPTION_FORBIDDEN", f"cannot return const quantum parameter {r}")

    returned_set = set(ret_names)
    # LIFO exit check: unreturned non-const quantum vars must be cleanly uncomputable
    remaining_q = sorted(
        (v for v, info in env.items() if all((info["live"], info["type"] == "B", not info["const"], v not in returned_set))),
        key=lambda v: env[v]["order"],
        reverse=True,
    )
    for var in remaining_q:
        if _can_auto_uncompute(var):
            synthesized.append(env[var]["inverse_gate"])
            env[var]["live"] = False
        else:
            return _reject("UNCONSUMED_QUANTUM_DROP", f"silent drop of non-uncomputable quantum variable {var}")

    return {
        "name": name,
        "annotation": ann,
        "well_typed": True,
        "type_error_code": None,
        "type_error_detail": None,
        "return_types": [env[r]["type"] for r in ret_names],
        "synthesized_uncomputations": synthesized,
    }


def build_pillar2_silq_typechecker() -> dict[str, Any]:
    valid_programs: list[dict[str, Any]] = [
        {
            "name": "bell_pair_mfree",
            "annotation": "mfree",
            "params": [],
            "body": [
                {"op": "alloc_q", "dst": "a"},
                {"op": "alloc_q", "dst": "b"},
                {"op": "unitary_gate", "gate": "H", "controls": [], "target": "a"},
                {"op": "qfree_gate", "gate": "CNOT", "controls": ["a"], "target": "b"},
            ],
            "returns": ["a", "b"],
        },
        {
            "name": "deutsch_jozsa_kickback_mfree",
            "annotation": "mfree",
            "params": [
                {"name": "x", "type": "B", "const": False},
                {"name": "y", "type": "B", "const": False},
            ],
            "body": [
                {"op": "unitary_gate", "gate": "H", "controls": [], "target": "x"},
                {"op": "qfree_gate", "gate": "X", "controls": [], "target": "y"},
                {"op": "unitary_gate", "gate": "H", "controls": [], "target": "y"},
                {"op": "qfree_gate", "gate": "CNOT", "controls": ["x"], "target": "y"},
                {"op": "unitary_gate", "gate": "H", "controls": [], "target": "x"},
            ],
            "returns": ["x", "y"],
        },
        {
            "name": "toffoli_lifted_auto_uncompute",
            "annotation": "mfree",
            "params": [
                {"name": "a", "type": "B", "const": True},
                {"name": "b", "type": "B", "const": True},
            ],
            "body": [
                {"op": "lifted_and", "dst": "tmp", "ctrl1": "a", "ctrl2": "b"},
                {"op": "unitary_gate", "gate": "phase", "controls": [], "target": "tmp"},
            ],
            "returns": [],
        },
        {
            "name": "grover_2q_diffusion_mfree",
            "annotation": "mfree",
            "params": [
                {"name": "q0", "type": "B", "const": False},
                {"name": "q1", "type": "B", "const": False},
            ],
            "body": [
                {"op": "unitary_gate", "gate": "H", "controls": [], "target": "q0"},
                {"op": "unitary_gate", "gate": "H", "controls": [], "target": "q1"},
                {"op": "qfree_gate", "gate": "X", "controls": [], "target": "q0"},
                {"op": "qfree_gate", "gate": "X", "controls": [], "target": "q1"},
                {"op": "unitary_gate", "gate": "CZ", "controls": ["q0"], "target": "q1"},
                {"op": "qfree_gate", "gate": "X", "controls": [], "target": "q0"},
                {"op": "qfree_gate", "gate": "X", "controls": [], "target": "q1"},
                {"op": "unitary_gate", "gate": "H", "controls": [], "target": "q0"},
                {"op": "unitary_gate", "gate": "H", "controls": [], "target": "q1"},
            ],
            "returns": ["q0", "q1"],
        },
        {
            "name": "observe_4d_slice_explicit_measure",
            "annotation": "general",
            "params": [
                {"name": "O", "type": "B", "const": False},
                {"name": "H", "type": "B", "const": False},
            ],
            "body": [
                {"op": "qfree_gate", "gate": "CNOT", "controls": ["O"], "target": "H"},
                {"op": "measure", "src": "H", "dst": "m_h"},
            ],
            "returns": ["O", "m_h"],
        },
        {
            "name": "classical_dup_and_lifted_oracle",
            "annotation": "lifted",
            "params": [
                {"name": "c", "type": "!B", "const": False},
                {"name": "a", "type": "B", "const": True},
                {"name": "b", "type": "B", "const": True},
            ],
            "body": [
                {"op": "dup", "src": "c", "dst": "c_copy"},
                {"op": "lifted_and", "dst": "out", "ctrl1": "a", "ctrl2": "b"},
            ],
            "returns": ["out"],
        },
    ]

    must_fail_programs: list[tuple[dict[str, Any], str]] = [
        (
            {
                "name": "fail_silent_drop_entangled_H",
                "annotation": "general",
                "params": [
                    {"name": "O", "type": "B", "const": False},
                    {"name": "H", "type": "B", "const": False},
                ],
                "body": [
                    {"op": "qfree_gate", "gate": "CNOT", "controls": ["O"], "target": "H"},
                ],
                "returns": ["O"],
            },
            "UNCONSUMED_QUANTUM_DROP",
        ),
        (
            {
                "name": "fail_clone_quantum_wire",
                "annotation": "mfree",
                "params": [{"name": "q", "type": "B", "const": False}],
                "body": [{"op": "dup", "src": "q", "dst": "q2"}],
                "returns": ["q", "q2"],
            },
            "QUANTUM_CLONING_FORBIDDEN",
        ),
        (
            {
                "name": "fail_H_inside_qfree",
                "annotation": "qfree",
                "params": [{"name": "q", "type": "B", "const": False}],
                "body": [{"op": "unitary_gate", "gate": "H", "controls": [], "target": "q"}],
                "returns": ["q"],
            },
            "NON_QFREE_OP_IN_QFREE",
        ),
        (
            {
                "name": "fail_measure_inside_mfree",
                "annotation": "mfree",
                "params": [{"name": "q", "type": "B", "const": False}],
                "body": [{"op": "measure", "src": "q", "dst": "m"}],
                "returns": ["m"],
            },
            "MEASURE_IN_MFREE_OR_QFREE",
        ),
        (
            {
                "name": "fail_forget_after_dep_mutated",
                "annotation": "mfree",
                "params": [
                    {"name": "a", "type": "B", "const": False},
                    {"name": "b", "type": "B", "const": True},
                ],
                "body": [
                    {"op": "lifted_and", "dst": "tmp", "ctrl1": "a", "ctrl2": "b"},
                    {"op": "qfree_gate", "gate": "X", "controls": [], "target": "a"},
                    {"op": "forget", "var": "tmp"},
                ],
                "returns": ["a"],
            },
            "UNCOMPUTATION_FAILED",
        ),
        (
            {
                "name": "fail_modify_const_param",
                "annotation": "qfree",
                "params": [{"name": "a", "type": "B", "const": True}],
                "body": [{"op": "qfree_gate", "gate": "X", "controls": [], "target": "a"}],
                "returns": [],
            },
            "CONST_MODIFICATION_FORBIDDEN",
        ),
        (
            {
                "name": "fail_nonconst_param_in_lifted",
                "annotation": "lifted",
                "params": [{"name": "a", "type": "B", "const": False}],
                "body": [{"op": "qfree_gate", "gate": "X", "controls": [], "target": "a"}],
                "returns": ["a"],
            },
            "LIFTED_REQUIRES_CONST_QPARAMS",
        ),
    ]

    valid_results = [typecheck_silq_program(p) for p in valid_programs]
    fail_results: list[dict[str, Any]] = []
    for prog, exp_code in must_fail_programs:
        res = typecheck_silq_program(prog)
        res["expected_error_code"] = exp_code
        fail_results.append(res)

    all_valid_ok = all(r["well_typed"] is True for r in valid_results)
    auto_uncomp_ok = valid_results[2]["synthesized_uncomputations"] == ["CCX(a,b,tmp)"]
    all_fail_ok = all(
        all((r["well_typed"] is False, r["type_error_code"] == r["expected_error_code"]))
        for r in fail_results
    )

    return {
        "valid_program_count": len(valid_results),
        "must_fail_program_count": len(fail_results),
        "valid_programs": valid_results,
        "must_fail_programs": fail_results,
        "all_valid_accepted": all_valid_ok,
        "all_must_fail_rejected": all_fail_ok,
        "pillar_verified": all((all_valid_ok, auto_uncomp_ok, all_fail_ok)),
    }


# ---------------------------------------------------------------------------
# Pillar 3: Exact Uncomputation vs Garbage Entanglement & Partial-Trace Theorem
# ---------------------------------------------------------------------------

def partial_trace_state(
    state: Sequence[Any],
    n_qubits: int,
    keep_qubits: Sequence[int],
) -> CycMatrix:
    """Compute exact reduced density matrix rho_O = Tr_H(|Psi><Psi|) in D[i, sqrt(2)]."""
    nq = require_int(n_qubits, "n_qubits", lo=2, hi=5)
    dim = 1 << nq
    if type(state) not in (list, tuple) or len(state) != dim:
        raise SilqBoundaryError("INVALID_STATE", f"state must have length {dim}")
    vec = [_require_cyc(amp, f"state[{i}]") for i, amp in enumerate(state)]
    if type(keep_qubits) not in (list, tuple) or len(keep_qubits) == 0:
        raise SilqBoundaryError("INVALID_KEEP_QUBITS", "keep_qubits must be non-empty list/tuple")
    keep = [require_int(q, f"keep[{i}]", lo=0, hi=nq - 1) for i, q in enumerate(keep_qubits)]
    if len(set(keep)) != len(keep) or len(keep) >= nq:
        raise SilqBoundaryError("INVALID_KEEP_QUBITS", "keep_qubits must be distinct proper subset of qubits")

    trace_out = [q for q in range(nq) if q not in keep]
    k_dim = 1 << len(keep)
    h_dim = 1 << len(trace_out)
    keep_bits = [nq - 1 - q for q in keep]
    hide_bits = [nq - 1 - q for q in trace_out]

    def _combine(o_idx: int, h_idx: int) -> int:
        full = 0
        for j, bp in enumerate(keep_bits):
            if (o_idx >> (len(keep) - 1 - j)) & 1:
                full |= 1 << bp
        for j, bp in enumerate(hide_bits):
            if (h_idx >> (len(trace_out) - 1 - j)) & 1:
                full |= 1 << bp
        return full

    rho: CycMatrix = [[CYC_ZERO for _ in range(k_dim)] for _ in range(k_dim)]
    for i in range(k_dim):
        for j in range(k_dim):
            acc = CYC_ZERO
            for h in range(h_dim):
                amp_i = vec[_combine(i, h)]
                amp_j = vec[_combine(j, h)]
                acc = cyc_add(acc, cyc_mul(amp_i, cyc_conj(amp_j)))
            rho[i][j] = acc
    return rho


def density_matrix_purity(rho: Any) -> dict[str, Any]:
    """Certify exact trace, Hermiticity, purity Tr(rho^2) in Q, and linear entropy S_L = 1 - Tr(rho^2)."""
    mat = _require_cyc_matrix(rho, "rho")
    n = len(mat)
    hermitian = mat_dagger_cyc(mat) == mat
    tr = CYC_ZERO
    for i in range(n):
        tr = cyc_add(tr, mat[i][i])
    rho_sq = mat_mul_cyc(mat, mat)
    pur = CYC_ZERO
    for i in range(n):
        pur = cyc_add(pur, rho_sq[i][i])

    diag_probs = [format_rational(mat[i][i][0]) for i in range(n)]
    diag_exact_q = all((mat[i][i][1], mat[i][i][2], mat[i][i][3]) == (Q0, Q0, Q0) for i in range(n))
    pur_exact_q = (pur[1], pur[2], pur[3]) == (Q0, Q0, Q0)
    tr_is_one = tr == CYC_ONE
    lin_entropy = Q1 - pur[0]
    return {
        "dim": n,
        "hermitian": hermitian,
        "trace_is_one": tr_is_one,
        "purity_imag_and_sqrt2_zero": all((pur_exact_q, diag_exact_q)),
        "purity_Tr_rho_sq": format_rational(pur[0]),
        "linear_entropy_S_L": format_rational(lin_entropy),
        "diagonal_probabilities": diag_probs,
    }


def build_pillar3_uncomputation_partial_trace() -> dict[str, Any]:
    gates = _canonical_gates()

    # Witness Pair 1: 1-bit Deutsch-Jozsa balanced oracle (O=[0], H=[1])
    s0_2q = [CYC_ONE, CYC_ZERO, CYC_ZERO, CYC_ZERO]
    s_oracle = apply_gate_state(s0_2q, 2, gates["H"], [0])
    s_oracle = apply_gate_state(s_oracle, 2, gates["CNOT"], [0, 1])
    s_oracle = apply_gate_state(s_oracle, 2, gates["Z"], [1])

    # Witness A: Silq forget(H) = CNOT(0, 1), then interference H(0)
    s_clean = apply_gate_state(s_oracle, 2, gates["CNOT"], [0, 1])
    s_clean = apply_gate_state(s_clean, 2, gates["H"], [0])
    dj_clean = density_matrix_purity(partial_trace_state(s_clean, 2, [0]))
    dj_clean["interference_preserved"] = (
        dj_clean["purity_Tr_rho_sq"],
        dj_clean["linear_entropy_S_L"],
        dj_clean["diagonal_probabilities"],
    ) == ("1", "0", ["0", "1"])

    # Witness B: Dropped un-uncomputed garbage H, apply H(0) directly, trace out H
    s_garbage = apply_gate_state(s_oracle, 2, gates["H"], [0])
    dj_garbage = density_matrix_purity(partial_trace_state(s_garbage, 2, [0]))
    dj_garbage["interference_destroyed"] = (
        dj_garbage["purity_Tr_rho_sq"],
        dj_garbage["linear_entropy_S_L"],
        dj_garbage["diagonal_probabilities"],
    ) == ("1/2", "1/2", ["1/2", "1/2"])

    # Witness Pair 2: 3-qubit Toffoli lifted_and + Grover diffusion (O=[0,1], H=[2])
    def _apply_grover_2q_diffusion(st: list[CyclotomicAmp]) -> list[CyclotomicAmp]:
        cur = apply_gate_state(st, 3, gates["H"], [0])
        cur = apply_gate_state(cur, 3, gates["H"], [1])
        cur = apply_gate_state(cur, 3, gates["X"], [0])
        cur = apply_gate_state(cur, 3, gates["X"], [1])
        cur = apply_gate_state(cur, 3, gates["CZ"], [0, 1])
        cur = apply_gate_state(cur, 3, gates["X"], [0])
        cur = apply_gate_state(cur, 3, gates["X"], [1])
        cur = apply_gate_state(cur, 3, gates["H"], [0])
        cur = apply_gate_state(cur, 3, gates["H"], [1])
        return cur

    s0_3q = [CYC_ONE] + [CYC_ZERO] * 7
    s_toff_mark = apply_gate_state(s0_3q, 3, gates["H"], [0])
    s_toff_mark = apply_gate_state(s_toff_mark, 3, gates["H"], [1])
    s_toff_mark = apply_gate_state(s_toff_mark, 3, gates["CCX"], [0, 1, 2])
    s_toff_mark = apply_gate_state(s_toff_mark, 3, gates["Z"], [2])

    # Witness A2: With Silq forget(tmp) = CCX(0, 1, 2) + Grover diffusion -> P(|11>) = 1, purity = 1
    s_grover_clean = apply_gate_state(s_toff_mark, 3, gates["CCX"], [0, 1, 2])
    s_grover_clean = _apply_grover_2q_diffusion(s_grover_clean)
    grover_clean = density_matrix_purity(partial_trace_state(s_grover_clean, 3, [0, 1]))
    grover_clean["interference_preserved"] = (
        grover_clean["purity_Tr_rho_sq"],
        grover_clean["linear_entropy_S_L"],
        grover_clean["diagonal_probabilities"],
    ) == ("1", "0", ["0", "0", "0", "1"])

    # Witness B2: Dropped un-uncomputed tmp + Grover diffusion -> P(|11>) = 5/8, purity = 5/8, S_L = 3/8
    s_grover_garbage = _apply_grover_2q_diffusion(s_toff_mark)
    grover_garbage = density_matrix_purity(partial_trace_state(s_grover_garbage, 3, [0, 1]))
    grover_garbage["interference_destroyed"] = (
        grover_garbage["purity_Tr_rho_sq"],
        grover_garbage["linear_entropy_S_L"],
        grover_garbage["diagonal_probabilities"],
    ) == ("5/8", "3/8", ["1/8", "1/8", "1/8", "5/8"])

    dj_drop = parse_exact_rational(dj_garbage["purity_Tr_rho_sq"]) < parse_exact_rational(dj_clean["purity_Tr_rho_sq"])
    grover_drop = parse_exact_rational(grover_garbage["purity_Tr_rho_sq"]) < parse_exact_rational(grover_clean["purity_Tr_rho_sq"])

    verified = all((
        dj_clean["hermitian"],
        dj_clean["trace_is_one"],
        dj_clean["purity_imag_and_sqrt2_zero"],
        dj_clean["interference_preserved"],
        dj_garbage["hermitian"],
        dj_garbage["trace_is_one"],
        dj_garbage["purity_imag_and_sqrt2_zero"],
        dj_garbage["interference_destroyed"],
        grover_clean["hermitian"],
        grover_clean["trace_is_one"],
        grover_clean["purity_imag_and_sqrt2_zero"],
        grover_clean["interference_preserved"],
        grover_garbage["hermitian"],
        grover_garbage["trace_is_one"],
        grover_garbage["purity_imag_and_sqrt2_zero"],
        grover_garbage["interference_destroyed"],
        dj_drop,
        grover_drop,
    ))

    return {
        "deutsch_jozsa_uncomputed_clean": dj_clean,
        "deutsch_jozsa_dropped_garbage": dj_garbage,
        "toffoli_grover_uncomputed_clean": grover_clean,
        "toffoli_grover_dropped_garbage": grover_garbage,
        "purity_strictly_dropped": all((dj_drop, grover_drop)),
        "pillar_verified": verified,
    }


# ---------------------------------------------------------------------------
# Pillar 4: Landauer Erasure vs Reversibility & Nested-Simulation Gap
# ---------------------------------------------------------------------------

def analyze_classical_gate_erasure(
    n_in_bits: int,
    n_out_bits: int,
    truth_table: Sequence[int],
) -> dict[str, Any]:
    """Exact pure-Z/Q Landauer preimage-fiber erasure accounting for any finite Boolean map."""
    ni = require_int(n_in_bits, "n_in_bits", lo=1, hi=6)
    no = require_int(n_out_bits, "n_out_bits", lo=1, hi=6)
    n_states = 1 << ni
    max_out = (1 << no) - 1
    if type(truth_table) not in (list, tuple) or len(truth_table) != n_states:
        raise SilqBoundaryError("INVALID_TRUTH_TABLE", f"truth_table must have length {n_states}")
    outputs = [require_int(y, f"truth_table[{i}]", lo=0, hi=max_out) for i, y in enumerate(truth_table)]

    fibers: dict[int, int] = {}
    for y in outputs:
        fibers[y] = fibers.get(y, 0) + 1

    # Exact Landauer conditional entropy product: 2^(n_states * H(X|Y)) = prod_y (|f^{-1}(y)|)^(|f^{-1}(y)|)
    entropy_power_product = 1
    for cnt in fibers.values():
        entropy_power_product *= cnt ** cnt
    max_fiber = max(fibers.values())
    is_bij = len(fibers) == n_states and ni == no
    involution = is_bij and all(outputs[outputs[x]] == x for x in range(n_states))

    return {
        "n_in_bits": ni,
        "n_out_bits": no,
        "input_state_count": n_states,
        "distinct_output_count": len(fibers),
        "fiber_sizes": {str(k): fibers[k] for k in sorted(fibers)},
        "max_fiber_size": max_fiber,
        "is_bijection": is_bij,
        "involution_verified": involution,
        "two_pow_N_H_X_given_Y": entropy_power_product,
    }


def build_nested_simulation_table(max_qubits: int = 20) -> list[dict[str, Any]]:
    """Certify exact Level-0/Level-2 algebraic dim vs Level-1 classical state-vector overhead for n=1..max_qubits."""
    n_max = require_int(max_qubits, "max_qubits", lo=2, hi=24)
    rows: list[dict[str, Any]] = []
    for n in range(1, n_max + 1):
        h_dim = 1 << n
        q_comps = 4 * h_dim
        rho_entries = 1 << (2 * n)
        overhead = Fraction(h_dim, n)
        rows.append({
            "n_qubits": n,
            "hilbert_dim_2n": h_dim,
            "cyclotomic_q_components_4x2n": q_comps,
            "density_matrix_entries_4n": rho_entries,
            "overhead_2n_over_n": format_rational(overhead),
            "overhead_decimal_trunc2": format_decimal_trunc(overhead, places=2),
        })
    return rows


def build_pillar4_landauer_nested_simulation() -> dict[str, Any]:
    # Classical irreversible AND: (a, b) -> a & b
    and_table = [((x >> 1) & (x & 1)) for x in range(4)]
    and_stats = analyze_classical_gate_erasure(2, 1, and_table)
    # Pure-Z Landauer erasure bracket for AND: H(X|Y) = (3/4)*log2(3),
    # 19/16 < (3/4)*log2(3) < 6/5 <=> 2^19 < 3^12 AND 3^15 < 2^24
    # Derived directly from exact power_product = 2^(4*H(X|Y)) = 27:
    # 19/16 < H <=> 2^19 < 27^4 (524288 < 531441) and H < 6/5 <=> 27^5 < 2^24 (14348907 < 16777216)
    p_and = and_stats["two_pow_N_H_X_given_Y"]
    and_bracket_ok = all(((1 << 19) < (p_and ** 4), (p_and ** 5) < (1 << 24)))
    and_stats["landauer_erasure_lower_bound_bits"] = "19/16"
    and_stats["landauer_erasure_upper_bound_bits"] = "6/5"
    and_stats["erasure_bracket_verified"] = and_bracket_ok

    # Constant 1-bit reset ERASE: x -> 0 (exact 1 bit erased: 2^(2*1) = 4)
    erase_stats = analyze_classical_gate_erasure(1, 1, [0, 0])

    # Reversible 3-bit Toffoli CCX: (a, b, c) -> (a, b, c ^ (a & b))
    ccx_table = [((x & 6) | ((x & 1) ^ (((x >> 2) & 1) & ((x >> 1) & 1)))) for x in range(8)]
    ccx_stats = analyze_classical_gate_erasure(3, 3, ccx_table)

    # Exact Level-0 / Level-1 / Level-2 separation table n=1..20
    sim_table = build_nested_simulation_table(20)
    overheads = [parse_exact_rational(r["overhead_2n_over_n"]) for r in sim_table]
    strictly_inc_n2 = all(overheads[i] < overheads[i + 1] for i in range(1, len(overheads) - 1))

    # Algebraic isomorphism witness: Level-0 unitary group and Level-2 Silq mfree Clifford+T share U^dagger U = I
    gates = _canonical_gates()
    l0_l2_iso = all(is_unitary_cyc(gates[k]) for k in ("H", "T", "CNOT", "CCX"))

    verified = all((
        not and_stats["is_bijection"],
        and_stats["fiber_sizes"] == {"0": 3, "1": 1},
        p_and == 27,
        and_bracket_ok,
        not erase_stats["is_bijection"],
        erase_stats["two_pow_N_H_X_given_Y"] == 4,
        ccx_stats["is_bijection"],
        ccx_stats["involution_verified"],
        ccx_stats["two_pow_N_H_X_given_Y"] == 1,
        len(sim_table) == 20,
        sim_table[0]["hilbert_dim_2n"] == 2,
        sim_table[19]["hilbert_dim_2n"] == 1048576,
        sim_table[19]["cyclotomic_q_components_4x2n"] == 4194304,
        strictly_inc_n2,
        l0_l2_iso,
    ))

    return {
        "irreversible_and_2_to_1": and_stats,
        "irreversible_reset_1_to_1": erase_stats,
        "reversible_toffoli_3_to_3": ccx_stats,
        "nested_simulation_table_n1_to_n20": sim_table,
        "overhead_strictly_increasing_from_n2": strictly_inc_n2,
        "algebraic_group_isomorphic_l0_l2": l0_l2_iso,
        "pillar_verified": verified,
    }


# ---------------------------------------------------------------------------
# Standalone Certificate Builder & Zone-B Payload Validator
# ---------------------------------------------------------------------------

def build_standalone_certificate() -> dict[str, Any]:
    p1 = build_pillar1_cyclotomic()
    p2 = build_pillar2_silq_typechecker()
    p3 = build_pillar3_uncomputation_partial_trace()
    p4 = build_pillar4_landauer_nested_simulation()

    all_ok = all((
        p1["pillar_verified"],
        p2["pillar_verified"],
        p3["pillar_verified"],
        p4["pillar_verified"],
    ))

    payload: dict[str, Any] = {
        "oracle_class": "exact",
        "novelty_classification": "N1",
        "literature_anchors_n0": [
            "Bichsel, Baader, Gehr, Vechev (PLDI 2020): Silq High-Level Quantum Language",
            "Landauer (IBM J. Res. Dev. 1961): Irreversibility and Heat Generation",
        ],
        "zero_floats_exact_arithmetic": True,
        "all_verified": all_ok,
        "pillar1_cyclotomic_clifford_t": p1,
        "pillar2_silq_static_typechecker": p2,
        "pillar3_uncomputation_partial_trace": p3,
        "pillar4_landauer_nested_simulation": p4,
    }
    payload_sha = sha256_hex(canonical_json_bytes(payload))
    cert_body = {
        "schema": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": payload_sha,
        "payload": payload,
    }
    cert_sha = sha256_hex(canonical_json_bytes(cert_body))
    return {
        "schema": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": payload_sha,
        "certificate_sha256": cert_sha,
        "payload": payload,
    }


_PILLAR_KEYSETS: dict[str, frozenset[str]] = {
    "pillar1_cyclotomic_clifford_t": frozenset({
        "ring_representation",
        "gate_certifications",
        "all_gates_unitary_and_dyadic",
        "group_relations_verified",
        "all_group_relations_verified",
        "born_witnesses",
        "all_witnesses_unit_norm",
        "must_fail_non_unitary_rejected",
        "pillar_verified",
    }),
    "pillar2_silq_static_typechecker": frozenset({
        "valid_program_count",
        "valid_programs",
        "all_valid_accepted",
        "must_fail_program_count",
        "must_fail_programs",
        "all_must_fail_rejected",
        "pillar_verified",
    }),
    "pillar3_uncomputation_partial_trace": frozenset({
        "deutsch_jozsa_uncomputed_clean",
        "deutsch_jozsa_dropped_garbage",
        "toffoli_grover_uncomputed_clean",
        "toffoli_grover_dropped_garbage",
        "purity_strictly_dropped",
        "pillar_verified",
    }),
    "pillar4_landauer_nested_simulation": frozenset({
        "irreversible_and_2_to_1",
        "irreversible_reset_1_to_1",
        "reversible_toffoli_3_to_3",
        "nested_simulation_table_n1_to_n20",
        "overhead_strictly_increasing_from_n2",
        "algebraic_group_isomorphic_l0_l2",
        "pillar_verified",
    }),
}


def _validate_payload_structure(payload: dict[str, Any]) -> None:
    """Structural, pillar-keyset, and bool-vs-int schema gate enforced under both full_replay=False and True."""
    if frozenset(payload.keys()) != _PAYLOAD_KEYS:
        raise SilqBoundaryError("INVALID_PAYLOAD_KEYS", "payload top-level keys mismatch")
    if payload["oracle_class"] != "exact":
        raise SilqBoundaryError("INVALID_PAYLOAD_META", "oracle_class must be 'exact'")
    if payload["novelty_classification"] != "N1":
        raise SilqBoundaryError("INVALID_PAYLOAD_META", "novelty_classification must be 'N1'")
    if payload["zero_floats_exact_arithmetic"] is not True:
        raise SilqBoundaryError("INVALID_PAYLOAD_META", "zero_floats_exact_arithmetic must be True")
    if payload["all_verified"] is not True:
        raise SilqBoundaryError("INVALID_PAYLOAD_META", "all_verified must be True")
    anchors = payload["literature_anchors_n0"]
    if type(anchors) is not list or len(anchors) != 2:
        raise SilqBoundaryError("INVALID_PAYLOAD_META", "literature_anchors_n0 must be 2-element list")
    for pkey in _PILLAR_KEYS:
        pdict = payload[pkey]
        if type(pdict) is not dict:
            raise SilqBoundaryError("INVALID_PILLAR_TYPE", f"{pkey} must be strict dict")
        if frozenset(pdict.keys()) != _PILLAR_KEYSETS[pkey]:
            raise SilqBoundaryError("INVALID_PILLAR_KEYS", f"{pkey} keys mismatch")
        if pdict["pillar_verified"] is not True:
            raise SilqBoundaryError("PILLAR_NOT_VERIFIED", f"{pkey}.pillar_verified must be True")

    stack: list[Any] = [payload]
    while stack:
        cur = stack.pop()
        if type(cur) is dict:
            for k, v in cur.items():
                if type(v) is bool:
                    if k not in _ALLOWED_BOOL_KEYS:
                        raise SilqBoundaryError("BOOL_IN_NON_BOOL_FIELD", f"unexpected bool in field {k}")
                elif k in _ALLOWED_BOOL_KEYS:
                    raise SilqBoundaryError("NON_BOOL_IN_BOOL_FIELD", f"expected exact bool in field {k}")
                elif type(v) in (dict, list):
                    stack.append(v)
        else:
            for item in cur:
                if type(item) is bool:
                    raise SilqBoundaryError("BOOL_IN_LIST", "bool element forbidden inside list")
                if type(item) in (dict, list):
                    stack.append(item)


def validate_certificate_payload(cert: Any, full_replay: bool = True) -> dict[str, Any]:
    """Zone-B hardened in-memory certificate validator (callable directly by S19c fuzzer)."""
    require_bool(full_replay, "full_replay")
    validate_json_tree_iterative(cert)
    if type(cert) is not dict:
        raise SilqBoundaryError("CERT_NOT_DICT", "certificate root must be strict dict")
    if frozenset(cert.keys()) != _CERT_KEYS:
        raise SilqBoundaryError("INVALID_CERT_KEYS", "certificate keys mismatch")
    if cert["schema"] != SCHEMA_VERSION:
        raise SilqBoundaryError("INVALID_SCHEMA", "unexpected certificate schema")
    if cert["track_id"] != TRACK_ID:
        raise SilqBoundaryError("INVALID_TRACK_ID", "unexpected track_id")

    payload = cert["payload"]
    if type(payload) is not dict:
        raise SilqBoundaryError("PAYLOAD_NOT_DICT", "payload must be strict dict")

    claimed_payload_sha = require_hex64(cert["payload_sha256"], "payload_sha256")
    actual_payload_sha = sha256_hex(canonical_json_bytes(payload))
    if not constant_time_hex64_equal(claimed_payload_sha, actual_payload_sha, "payload_sha256"):
        raise SilqBoundaryError("PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")

    claimed_cert_sha = require_hex64(cert["certificate_sha256"], "certificate_sha256")
    cert_body = {
        "schema": cert["schema"],
        "track_id": cert["track_id"],
        "payload_sha256": claimed_payload_sha,
        "payload": payload,
    }
    actual_cert_sha = sha256_hex(canonical_json_bytes(cert_body))
    if not constant_time_hex64_equal(claimed_cert_sha, actual_cert_sha, "certificate_sha256"):
        raise SilqBoundaryError("CERT_SHA_MISMATCH", "certificate_sha256 mismatch")

    _validate_payload_structure(payload)

    if full_replay:
        fresh = build_standalone_certificate()
        if not constant_time_hex64_equal(actual_payload_sha, fresh["payload_sha256"], "recomputed_payload_sha256"):
            raise SilqBoundaryError("RECOMPUTATION_MISMATCH", "payload differs from deterministic recomputation")

    return {
        "valid": True,
        "schema": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": actual_payload_sha,
        "certificate_sha256": actual_cert_sha,
        "full_replay": full_replay,
    }
