#!/usr/bin/env python3
"""
Standalone adversarial & boundary test runner for `tests/fixture_verifier.py`.
Used by `aletheia mutate tests/fixture_verifier.py --test-cmd "python3 fixture_verifier_test.py"`.
Zero bare asserts (100% python3 -I -O -B safe).
"""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from fixture_verifier import VerifyError, verify_2x2_psd, verify_rank_trace_gt


def expect_reject(fn, label: str) -> None:
    try:
        fn()
    except VerifyError:
        return
    raise RuntimeError(f"MUST-FAIL CONTROL ACCEPTED: {label}")


def main() -> None:
    # 1. Tight positive boundary controls (kill strictness flips `<` -> `<=` and `<=` -> `<`):
    #    - Zero matrix [[0,0],[0,0]] is PSD with tr == 0 AND det == 0!
    verify_2x2_psd("0", "0", "0")
    #    - Rank-1 boundary with target_rank_gt == 0 (kills target_rank_gt < 0 -> <= 0)
    r1 = verify_rank_trace_gt("1", "0", "0", 0)
    if r1["certified_min_rank"] != 1:
        raise RuntimeError("rank-1 positive failed")
    #    - Rank-2 positive using int and Fraction inputs
    r2 = verify_rank_trace_gt(2, Fraction(0), "2", 1)
    if r2["certified_min_rank"] != 2:
        raise RuntimeError("rank-2 positive failed")

    # 2. Tight negative must-fail controls isolating EVERY guard & boundary operator:
    expect_reject(lambda: verify_2x2_psd(True, 0, 1), "bool_rejected")
    expect_reject(lambda: verify_2x2_psd(0.5, 0, 1), "float_rejected")
    expect_reject(lambda: verify_2x2_psd(None, 0, 1), "none_rejected")
    expect_reject(lambda: verify_2x2_psd("1/2\n", 0, 1), "trailing_newline_rejected")
    # Negative definite: det = +4 > 0, ONLY tr < 0 catches it!
    expect_reject(lambda: verify_2x2_psd(-2, 0, -2), "neg_def_tr_lt_0")
    # Indefinite: tr = +2 > 0, ONLY det < 0 catches it!
    expect_reject(lambda: verify_2x2_psd(1, 2, 1), "indef_det_lt_0")
    # target_rank_gt type & range controls
    expect_reject(lambda: verify_rank_trace_gt(1, 0, 1, True), "bool_target")  # type: ignore[arg-type]
    expect_reject(lambda: verify_rank_trace_gt(1, 0, 1, "1"), "str_target")  # type: ignore[arg-type]
    expect_reject(lambda: verify_rank_trace_gt(1, 0, 1, -1), "neg_target")
    # Exact tie lhs == rhs: a=1, b=0, c=0, target_rank_gt=1 => tr^2 = 1 == 1 * frob_sq (kills `<=` -> `<`!)
    expect_reject(lambda: verify_rank_trace_gt(1, 0, 0, 1), "exact_tie_lhs_eq_rhs")
    # Strict violation lhs < rhs: a=1, b=0, c=0, target_rank_gt=2 => 1 < 2
    expect_reject(lambda: verify_rank_trace_gt(1, 0, 0, 2), "lhs_lt_rhs")


if __name__ == "__main__":
    main()
    print("FIXTURE_VERIFIER_TEST_OK")
