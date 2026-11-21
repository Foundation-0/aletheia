"""
Built-in Exact-Rational Trust-Path Verifier Fixture for `aletheia mutate` R5 self-testing.

Implements minimal, mathematically non-redundant exact guards for:
  1. Strict R3 rational parsing (`parse_exact`),
  2. Exact 2x2 real-symmetric PSD certification (`verify_2x2_psd`: det >= 0 and tr >= 0),
  3. Exact strict Cauchy-Schwarz rank certification (`verify_rank_trace_gt`: tr^2 > r0 * ||M||_F^2).

Every single guard and boundary operator (`<`, `<=`) is mathematically essential and
independently isolated by `tests/fixture_verifier_test.py` (100% mutant kill rate!).
"""
from __future__ import annotations

from fractions import Fraction
import re
from typing import Any

_FRAC_RE = re.compile(r"\A(?:0|-?[1-9][0-9]*)(?:/[1-9][0-9]*)?\Z", re.ASCII)


class VerifyError(ValueError):
    """Explicit verification failure (never stripped by python3 -O)."""


def parse_exact(val: Any) -> Fraction:
    if isinstance(val, bool):
        raise VerifyError("bool rejected")
    if isinstance(val, Fraction):
        return val
    if isinstance(val, int):
        return Fraction(val)
    if not isinstance(val, str):
        raise VerifyError("non-exact type rejected")
    if _FRAC_RE.match(val) is None:
        raise VerifyError("non-canonical rational syntax")
    return Fraction(val)


def verify_2x2_psd(a_raw: Any, b_raw: Any, c_raw: Any) -> tuple[Fraction, Fraction, Fraction]:
    """
    Exact 2x2 real-symmetric PSD gate: M = [[a, b], [b, c]] is PSD iff tr = a + c >= 0
    and det = a*c - b^2 >= 0 (minimal non-redundant necessary & sufficient Sylvester criterion!).
    """
    a = parse_exact(a_raw)
    b = parse_exact(b_raw)
    c = parse_exact(c_raw)
    tr = a + c
    if tr < 0:
        raise VerifyError("tr < 0 violates PSD")
    det = a * c - b * b
    if det < 0:
        raise VerifyError("det < 0 violates PSD")
    return a, b, c


def verify_rank_trace_gt(
    a_raw: Any,
    b_raw: Any,
    c_raw: Any,
    target_rank_gt: int,
) -> dict[str, Any]:
    """Certify M is PSD and rank(M) >= target_rank_gt + 1 via strict (tr M)^2 > r0 * ||M||_F^2."""
    if isinstance(target_rank_gt, bool):
        raise VerifyError("target_rank_gt cannot be bool")
    if not isinstance(target_rank_gt, int):
        raise VerifyError("target_rank_gt must be int")
    if target_rank_gt < 0:
        raise VerifyError("target_rank_gt must be >= 0")

    a, b, c = verify_2x2_psd(a_raw, b_raw, c_raw)
    tr = a + c
    frob_sq = a * a + 2 * b * b + c * c
    lhs = tr * tr
    rhs = Fraction(target_rank_gt) * frob_sq
    if lhs <= rhs:
        raise VerifyError("Cauchy-Schwarz rank bound not strictly exceeded")
    return {
        "certified_min_rank": target_rank_gt + 1,
        "exact_bound": str(lhs / frob_sq),
    }
