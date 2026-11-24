#!/usr/bin/env python3
"""
R5 Verification & Mutation-Complete Test Suite for the Domain-Agnostic CEER Engine.

Zero bare `assert` statements (all checks route through `require_ok`), zero host device-node
paths (uses scratch `os.mkfifo` for non-regular file tests), `umask 077` compatible, pure stdlib.
"""
from __future__ import annotations

import contextlib
import copy
import errno
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ceer_audit as ca  # noqa: E402
import ceer_engine as ce  # noqa: E402
import ceer_lean4_synth as cls  # noqa: E402


def require_ok(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _expect_err(exc_type: type[Exception], code: str, fn: Any, *args: Any, **kwargs: Any) -> None:
    try:
        fn(*args, **kwargs)
    except exc_type as exc:
        got = getattr(exc, "code", None)
        require_ok(got == code, f"expected code={code!r}, got {got!r} ({exc})")
        return
    raise AssertionError(f"expected {exc_type.__name__}({code!r}), but call succeeded")


def _resign_cert(cert: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(cert)
    payload_sha = hashlib.sha256(ca.canonical_json_bytes(out["payload"])).hexdigest()
    out["payload_sha256"] = payload_sha
    env = {
        "schema": out["schema"],
        "track_id": out["track_id"],
        "payload_sha256": payload_sha,
        "payload": out["payload"],
    }
    out["certificate_sha256"] = hashlib.sha256(ca.canonical_json_bytes(env)).hexdigest()
    return out


class _SubInt(int):
    pass


class _SubStr(str):
    pass


class _SubList(list):
    pass


class _SubDict(dict):
    pass


class TestCEEREnginePureZQ(unittest.TestCase):
    def test_01_primitives_rationals_and_json_tree(self) -> None:
        require_ok(ce.fmt_q(Fraction(0, 1)) == "0", "fmt_q(0)")
        require_ok(ce.fmt_q(Fraction(-7, 1)) == "-7", "fmt_q(-7)")
        require_ok(ce.fmt_q(Fraction(3, 5)) == "3/5", "fmt_q(3/5)")
        _expect_err(ce.CEERError, "CEER_INVALID_FRACTION", ce.fmt_q, 3)

        require_ok(ce.parse_q("0") == Fraction(0), "parse 0")
        require_ok(ce.parse_q("-5") == Fraction(-5), "parse -5")
        require_ok(ce.parse_q("3/2") == Fraction(3, 2), "parse 3/2")
        require_ok(ce.parse_q("-3/2") == Fraction(-3, 2), "parse -3/2")
        _expect_err(ce.CEERError, "CEER_INVALID_STR", ce.parse_q, 123)
        _expect_err(ce.CEERError, "CEER_EMPTY_STR", ce.parse_q, "")
        _expect_err(ce.CEERError, "CEER_NUL_STR", ce.parse_q, "1\x00")
        _expect_err(ce.CEERError, "CEER_INVALID_UTF8", ce.parse_q, "\ud800")
        _expect_err(ce.CEERError, "CEER_RATIONAL_WHITESPACE", ce.parse_q, " 1")
        _expect_err(ce.CEERError, "CEER_RATIONAL_FORMAT", ce.parse_q, "1/2/3")
        _expect_err(ce.CEERError, "CEER_RATIONAL_FORMAT", ce.parse_q, "-")
        _expect_err(ce.CEERError, "CEER_RATIONAL_FORMAT", ce.parse_q, "1a")
        _expect_err(ce.CEERError, "CEER_RATIONAL_NONCANON", ce.parse_q, "01")
        _expect_err(ce.CEERError, "CEER_RATIONAL_NONCANON", ce.parse_q, "-0")
        _expect_err(ce.CEERError, "CEER_RATIONAL_FORMAT", ce.parse_q, "1/")
        _expect_err(ce.CEERError, "CEER_RATIONAL_FORMAT", ce.parse_q, "1/02")
        _expect_err(ce.CEERError, "CEER_RATIONAL_FORMAT", ce.parse_q, "1/2a")
        _expect_err(ce.CEERError, "CEER_INT_TOO_SMALL", ce.parse_q, "3/1")
        _expect_err(ce.CEERError, "CEER_RATIONAL_NONCANON", ce.parse_q, "2/4")

        # Exact integer digit bounds (10**1000 - 1 passes; 10**1000 and 10**5000 fail)
        require_ok(ce._require_exact_int(10**1000 - 1, "ok") == 10**1000 - 1, "1000-digit max int ok")
        _expect_err(ce.CEERError, "CEER_INVALID_INT", ce._require_exact_int, True, "b")
        _expect_err(ce.CEERError, "CEER_INT_OVERFLOW", ce._require_exact_int, 10**1000, "d1001")
        _expect_err(ce.CEERError, "CEER_INT_OVERFLOW", ce._require_exact_int, 10**5000, "d5000")
        _expect_err(ce.CEERError, "CEER_INT_TOO_SMALL", ce._require_exact_int, 0, "m", min_val=1)
        _expect_err(ce.CEERError, "CEER_INVALID_SHA256", ce._require_sha256_hex, "A" * 64, "h")
        _expect_err(ce.CEERError, "CEER_INVALID_SHA256", ce._require_sha256_hex, "a" * 63, "h")

        # JSON tree validation bounds (exact depth == limit passes, empty str allowed, forbidden types fail)
        ce.validate_json_tree({"": "", "a": [1, True, None, "ok"]}, max_depth=2)
        _expect_err(ce.CEERError, "CEER_JSON_DEPTH", ce.validate_json_tree, {"a": [1]}, max_depth=1)
        for bad in (3 / 2, _SubInt(1), _SubStr("x"), _SubList([1]), _SubDict({"a": 1}), (1,)):
            _expect_err(ce.CEERError, "CEER_FORBIDDEN_TYPE", ce.validate_json_tree, {"x": bad})
        _expect_err(ce.CEERError, "CEER_INVALID_STR", ce.validate_json_tree, {1: "v"})

        # Lever normalization errors
        _expect_err(ce.CEERError, "CEER_INVALID_LEVERS", ce._normalize_lever_list, "bad", "l")
        _expect_err(ce.CEERError, "CEER_EMPTY_LEVERS", ce._normalize_lever_list, [], "l")
        _expect_err(ce.CEERError, "CEER_INVALID_LEVER_ROW", ce._normalize_lever_list, [[]], "l")
        _expect_err(ce.CEERError, "CEER_INVALID_LEVER_ROW", ce._normalize_lever_list, ["x"], "l")
        _expect_err(ce.CEERError, "CEER_LEVER_WIDTH", ce._normalize_lever_list, [[1], [1, 2]], "l")
        _expect_err(ce.CEERError, "CEER_DUPLICATE_LEVER", ce._normalize_lever_list, [[1, 2], [1, 2]], "l")

    def test_02_exact_operators_linear_concave_schur_hysteresis_enclosure(self) -> None:
        # Linear scaling: pass (incl. exact tol_q=0) & fail + guards
        r_lin_ok = ce.eval_linear_scaling([1, 2, 4], [1500, 2500, 4500], 500, Fraction(0))
        require_ok(r_lin_ok["passed"] is True and r_lin_ok["max_rel_error_q"] == "0", f"lin ok: {r_lin_ok}")
        r_lin_bad = ce.eval_linear_scaling([1, 2, 4], [1500, 2200, 3100], 500, Fraction(1, 20))
        require_ok(r_lin_bad["passed"] is False and r_lin_bad["worst_u"] == 4, f"lin bad: {r_lin_bad}")
        _expect_err(ce.CEERError, "CEER_INVALID_SERIES", ce.eval_linear_scaling, [1], [10], 0, Fraction(1, 10))
        _expect_err(ce.CEERError, "CEER_INVALID_SERIES", ce.eval_linear_scaling, [1, 2], [10], 0, Fraction(1, 10))
        _expect_err(ce.CEERError, "CEER_INVALID_TOL", ce.eval_linear_scaling, [1, 2], [10, 20], 0, Fraction(-1, 10))
        _expect_err(ce.CEERError, "CEER_NONPOSITIVE_BASELINE", ce.eval_linear_scaling, [1, 2], [10, 20], 10, Fraction(1, 10))

        # Concave 2nd diff: pass & fail + guards
        r_conc_ok = ce.eval_concave_second_diff([1, 2, 4], [10, 18, 28])
        require_ok(r_conc_ok["passed"] is True and r_conc_ok["max_second_diff_int"] < 0, f"conc ok: {r_conc_ok}")
        r_conc_bad = ce.eval_concave_second_diff([1, 2, 4], [10, 18, 40])
        require_ok(r_conc_bad["passed"] is False, f"conc bad: {r_conc_bad}")
        _expect_err(ce.CEERError, "CEER_INVALID_SERIES", ce.eval_concave_second_diff, [1, 2], [10, 20])
        _expect_err(ce.CEERError, "CEER_INVALID_SERIES", ce.eval_concave_second_diff, [1, 2, 3], [10, 20])
        _expect_err(ce.CEERError, "CEER_NONMONOTONE_CONTROLS", ce.eval_concave_second_diff, [1, 1, 3], [10, 20, 30])
        _expect_err(ce.CEERError, "CEER_NONMONOTONE_CONTROLS", ce.eval_concave_second_diff, [1, 3, 2], [10, 20, 30])

        # Matrix inversion pivot swap + singular rejection
        inv = ce._invert_matrix_q([[Fraction(0), Fraction(1)], [Fraction(1), Fraction(0)]])
        require_ok(inv == [[Fraction(0), Fraction(1)], [Fraction(1), Fraction(0)]], "swap pivot inv")
        _expect_err(ce.CEERError, "CEER_SINGULAR_BLOCK", ce._invert_matrix_q, [[Fraction(1), Fraction(1)], [Fraction(1), Fraction(1)]])

        # Schur dark drop: exact Stage-A invariance + orthogonal (g_ab_ip == 0) + error guards
        orth_mat = [
            [1, 0, 10, 0],
            [-1, 0, 10, 0],
            [0, 1, -10, 1],
            [0, -1, -10, -1],
        ]
        r_sch_orth = ce.eval_schur_dark_drop(orth_mat, [0, 1], [2, 3], Fraction(1, 2), expect_at_least=False)
        require_ok(r_sch_orth["stage_a_gauge_deviation_q"] == "0", f"gauge dev: {r_sch_orth}")
        require_ok(r_sch_orth["passed"] is True, f"orth schur: {r_sch_orth}")
        r_sch_fail = ce.eval_schur_dark_drop(orth_mat, [0, 1], [2, 3], Fraction(9, 10), expect_at_least=True)
        require_ok(r_sch_fail["passed"] is False, "high threshold fails")
        _expect_err(ce.CEERError, "CEER_INVALID_MATRIX", ce.eval_schur_dark_drop, ((1, 2), (3, 4), (5, 6)), [0], [1], Fraction(1, 2), True)
        _expect_err(ce.CEERError, "CEER_INVALID_MATRIX", ce.eval_schur_dark_drop, [[1, 2], [3, 4]], [0], [1], Fraction(1, 2), True)
        _expect_err(ce.CEERError, "CEER_INVALID_MATRIX", ce.eval_schur_dark_drop, [[1], [2], [3]], [0], [0], Fraction(1, 2), True)
        _expect_err(ce.CEERError, "CEER_RAGGED_MATRIX", ce.eval_schur_dark_drop, [[1, 2], [3], [5, 6]], [0], [1], Fraction(1, 2), True)
        _expect_err(ce.CEERError, "CEER_RAGGED_MATRIX", ce.eval_schur_dark_drop, [[1, 2], (3, 4), [5, 6]], [0], [1], Fraction(1, 2), True)
        _expect_err(ce.CEERError, "CEER_TOO_FEW_ROWS", ce.compute_normalized_schur_eta_q, [[Fraction(1), Fraction(2)]], [0], [1])
        q_mat = [[Fraction(1), Fraction(2)], [Fraction(3), Fraction(4)], [Fraction(5), Fraction(9)]]
        _expect_err(ce.CEERError, "CEER_EMPTY_PARTITION", ce.compute_normalized_schur_eta_q, q_mat, [], [1])
        _expect_err(ce.CEERError, "CEER_EMPTY_PARTITION", ce.compute_normalized_schur_eta_q, q_mat, [0], [])
        _expect_err(ce.CEERError, "CEER_OVERLAP_PARTITION", ce.compute_normalized_schur_eta_q, q_mat, [0], [0])
        _expect_err(ce.CEERError, "CEER_DUP_PARTITION", ce.compute_normalized_schur_eta_q, q_mat, [0, 0], [1])
        _expect_err(ce.CEERError, "CEER_DUP_PARTITION", ce.compute_normalized_schur_eta_q, q_mat, [0], [1, 1])
        _expect_err(ce.CEERError, "CEER_BAD_COL_IDX", ce.compute_normalized_schur_eta_q, q_mat, [-1], [1])
        _expect_err(ce.CEERError, "CEER_BAD_COL_IDX", ce.compute_normalized_schur_eta_q, q_mat, [0], [2])
        zero_var = [[Fraction(5), Fraction(1)], [Fraction(5), Fraction(2)], [Fraction(5), Fraction(4)]]
        _expect_err(ce.CEERError, "CEER_ZERO_VARIANCE", ce.compute_normalized_schur_eta_q, zero_var, [0], [1])

        # Hysteresis loop: zero-area pass, nonzero fail/pass, guards
        r_h0 = ce.eval_hysteresis_loop([1, 2, 3, 2], [10, 20, 30, 20], expect_nonzero=False, min_abs_twice_area=0)
        require_ok(r_h0["passed"] is True and r_h0["twice_area_int"] == 0, f"zero area: {r_h0}")
        r_h1 = ce.eval_hysteresis_loop([0, 10, 10, 0], [0, 0, 10, 10], expect_nonzero=True, min_abs_twice_area=200)
        require_ok(r_h1["passed"] is True and r_h1["abs_twice_area_int"] == 200, f"square area: {r_h1}")
        r_h1_low = ce.eval_hysteresis_loop([0, 10, 10, 0], [0, 0, 10, 10], expect_nonzero=True, min_abs_twice_area=201)
        require_ok(r_h1_low["passed"] is False, "below min_abs_twice_area")
        _expect_err(ce.CEERError, "CEER_INVALID_LOOP", ce.eval_hysteresis_loop, [1, 2, 3], [1, 2, 3], False)
        _expect_err(ce.CEERError, "CEER_INVALID_LOOP", ce.eval_hysteresis_loop, [1, 2, 3, 4], [1, 2, 3], False)

        # Rational enclosure: pass (incl. exact point interval lo == hi), fail, guards
        r_enc_ok = ce.eval_rational_enclosure([[5, 2], [2, 1]], [Fraction(2), Fraction(2)], [Fraction(3), Fraction(2)])
        require_ok(r_enc_ok["passed"] is True, "enc ok")
        r_enc_lo = ce.eval_rational_enclosure([[3, 2]], [Fraction(2)], [Fraction(3)])
        require_ok(r_enc_lo["passed"] is False, "enc below lo")
        r_enc_hi = ce.eval_rational_enclosure([[7, 2]], [Fraction(2)], [Fraction(3)])
        require_ok(r_enc_hi["passed"] is False, "enc above hi")
        _expect_err(ce.CEERError, "CEER_ENCLOSURE_LEN", ce.eval_rational_enclosure, [], [], [])
        _expect_err(ce.CEERError, "CEER_ENCLOSURE_LEN", ce.eval_rational_enclosure, [[1, 1]], [Fraction(0), Fraction(0)], [Fraction(1)])
        _expect_err(ce.CEERError, "CEER_ENCLOSURE_LEN", ce.eval_rational_enclosure, [[1, 1]], [Fraction(0)], [Fraction(1), Fraction(1)])
        _expect_err(ce.CEERError, "CEER_ENCLOSURE_PAIR", ce.eval_rational_enclosure, [[1]], [Fraction(0)], [Fraction(2)])
        _expect_err(ce.CEERError, "CEER_ENCLOSURE_PAIR", ce.eval_rational_enclosure, [(1, 2)], [Fraction(0)], [Fraction(2)])
        _expect_err(ce.CEERError, "CEER_ENCLOSURE_ORDER", ce.eval_rational_enclosure, [[1, 1]], [Fraction(3)], [Fraction(2)])

    def test_03_state_machine_prereg_latches_and_external_adapter(self) -> None:
        demo = ce.build_self_demo_cycles()
        c0, c1, c2 = demo["cycles"]
        require_ok(c0["verdict"] == "FALSIFIED", "c0 falsified")
        require_ok(c1["verdict"] == "FALSIFIED", "c1 falsified")
        require_ok(c2["verdict"] == "CORROBORATED", "c2 corroborated")
        require_ok(demo["epistemic_lifts_verified"] == 2, "2 epistemic lifts")

        # Preregistration validation & anti-Goodhart refusals
        _expect_err(ce.CEERError, "CEER_INVALID_PREREG", ce.commit_preregistration, [])
        p0_bad_prior = copy.deepcopy(c0["prereg"])
        p0_bad_prior["prior_cycle_sha256"] = "a" * 64
        _expect_err(ce.CEERError, "CEER_BROKEN_CHAIN", ce.commit_preregistration, p0_bad_prior)
        p0_bad_obs = copy.deepcopy(c0["prereg"])
        p0_bad_obs["prior_obstruction_code"] = "H0"
        _expect_err(ce.CEERError, "CEER_BROKEN_CHAIN", ce.commit_preregistration, p0_bad_obs)

        p1_leak = copy.deepcopy(c1["prereg"])
        p1_leak["eval_levers"] = [[1, 16], [9, 99]]
        _expect_err(ce.CEERError, "CEER_INSAMPLE_LEAK", ce.commit_preregistration, p1_leak)

        p0_bad_schema = copy.deepcopy(c0["prereg"])
        p0_bad_schema["observable_schema"] = []
        _expect_err(ce.CEERError, "CEER_INVALID_SCHEMA", ce.commit_preregistration, p0_bad_schema)
        p0_bad_schema["observable_schema"] = "bad"
        _expect_err(ce.CEERError, "CEER_INVALID_SCHEMA", ce.commit_preregistration, p0_bad_schema)

        p0_bad_pred = copy.deepcopy(c0["prereg"])
        p0_bad_pred["predictions"] = []
        _expect_err(ce.CEERError, "CEER_EMPTY_PREDICTIONS", ce.commit_preregistration, p0_bad_pred)
        p0_bad_pred["predictions"] = "nonempty"
        _expect_err(ce.CEERError, "CEER_EMPTY_PREDICTIONS", ce.commit_preregistration, p0_bad_pred)
        p0_bad_pred["predictions"] = ["x"]
        _expect_err(ce.CEERError, "CEER_INVALID_PRED", ce.commit_preregistration, p0_bad_pred)
        p0_bad_pred["predictions"] = [
            {"id": "A", "kind": "CONCAVE_SECOND_DIFF"},
            {"id": "A", "kind": "CONCAVE_SECOND_DIFF"},
        ]
        _expect_err(ce.CEERError, "CEER_DUP_PRED_ID", ce.commit_preregistration, p0_bad_pred)
        p0_bad_pred["predictions"] = [{"id": "A", "kind": "NO_SUCH_KIND"}]
        _expect_err(ce.CEERError, "CEER_UNKNOWN_PRED_KIND", ce.commit_preregistration, p0_bad_pred)

        # evaluate_cycle fail-closed guards
        _expect_err(ce.CEERError, "CEER_PREREG_MISMATCH", ce.evaluate_cycle, c0["prereg"], "0" * 64, c0["observation"])
        _expect_err(ce.CEERError, "CEER_INVALID_OBS", ce.evaluate_cycle, c0["prereg"], c0["prereg_sha256"], [])
        _expect_err(ce.CEERError, "CEER_BROKEN_CHAIN", ce.evaluate_cycle, c0["prereg"], c0["prereg_sha256"], c0["observation"], c0)
        _expect_err(ce.CEERError, "CEER_BROKEN_CHAIN", ce.evaluate_cycle, c1["prereg"], c1["prereg_sha256"], c1["observation"], None)

        bad_prior_sha = copy.deepcopy(c0)
        bad_prior_sha["cycle_sha256"] = "0" * 64
        _expect_err(ce.CEERError, "CEER_BROKEN_CHAIN", ce.evaluate_cycle, c1["prereg"], c1["prereg_sha256"], c1["observation"], bad_prior_sha)

        bad_prior_verd = copy.deepcopy(c0)
        bad_prior_verd["verdict"] = "CORROBORATED"
        _expect_err(ce.CEERError, "CEER_BROKEN_CHAIN", ce.evaluate_cycle, c1["prereg"], c1["prereg_sha256"], c1["observation"], bad_prior_verd)

        bad_prior_obs_code = copy.deepcopy(c0)
        bad_prior_obs_code["falsified_predicates"] = ["OTHER"]
        _expect_err(ce.CEERError, "CEER_BROKEN_CHAIN", ce.evaluate_cycle, c1["prereg"], c1["prereg_sha256"], c1["observation"], bad_prior_obs_code)
        bad_prior_obs_code["falsified_predicates"] = "H0_LINEAR_CORE"
        _expect_err(ce.CEERError, "CEER_BROKEN_CHAIN", ce.evaluate_cycle, c1["prereg"], c1["prereg_sha256"], c1["observation"], bad_prior_obs_code)

        # train_levers omitting prior observed levers -> CEER_INSAMPLE_LEAK
        p1_omit = copy.deepcopy(c1["prereg"])
        p1_omit["train_levers"] = [[1, 16]]
        _expect_err(
            ce.CEERError, "CEER_INSAMPLE_LEAK",
            ce.evaluate_cycle, p1_omit, ce.commit_preregistration(p1_omit), c1["observation"], c0,
        )
        # eval_levers reusing prior cycle levers despite non-overlapping train_levers mock
        c0_extra_seen = copy.deepcopy(c0)
        c0_extra_seen["seen_levers_cumulative"] = [[1, 16], [2, 256], [4, 4096], [3, 8192]]
        p1_with_train = copy.deepcopy(c1["prereg"])
        p1_with_train["train_levers"] = [[1, 16], [2, 256], [4, 4096]]
        _expect_err(
            ce.CEERError, "CEER_INSAMPLE_LEAK",
            ce.evaluate_cycle, p1_with_train, ce.commit_preregistration(p1_with_train), c1["observation"], c0_extra_seen,
        )
        p1_reuse = copy.deepcopy(c1["prereg"])
        p1_reuse["train_levers"] = [[1, 16], [2, 256], [4, 4096], [99, 99]]
        c0_reuse = copy.deepcopy(c0)
        c0_reuse["seen_levers_cumulative"] = [[1, 16], [2, 256], [4, 4096]]
        # Now construct prior_seen subset of train_levers AND overlapping eval_levers is impossible unless
        # prior_seen has an eval lever; above already tested prior_seen not subset. Let's test exact second branch:
        # prior_seen = [[1,16],[2,256],[4,4096]], train_levers = [[1,16],[2,256],[4,4096]], eval_levers = [[3,8192]]
        # Actually notice commit_preregistration already forbids train & eval overlap; if prior_seen <= train_levers
        # and train_levers & eval_levers == empty, then prior_seen & eval_levers is mathematically empty!
        # Let's verify observation mismatch & invalid bool in SCHUR_DARK_DROP:
        obs_bad_lv = copy.deepcopy(c0["observation"])
        obs_bad_lv["eval_levers"] = [[9, 9]]
        _expect_err(ce.CEERError, "CEER_OBSERVATION_MISMATCH", ce.evaluate_cycle, c0["prereg"], c0["prereg_sha256"], obs_bad_lv)
        obs_bad_sc = copy.deepcopy(c0["observation"])
        obs_bad_sc["observable_schema"] = ["x", "y"]
        _expect_err(ce.CEERError, "CEER_OBSERVATION_MISMATCH", ce.evaluate_cycle, c0["prereg"], c0["prereg_sha256"], obs_bad_sc)

        # Per-kind prereg/obs/prior-cycle & direct operator non-list validation (zero raw KeyError/TypeError)
        _expect_err(ce.CEERError, "CEER_INVALID_SERIES", ce.eval_linear_scaling, 123, [1, 2], 0, Fraction(1, 10))
        _expect_err(ce.CEERError, "CEER_INVALID_SERIES", ce.eval_linear_scaling, [1, 2], 123, 0, Fraction(1, 10))
        _expect_err(ce.CEERError, "CEER_INVALID_SERIES", ce.eval_concave_second_diff, 123, [1, 2, 3])
        _expect_err(ce.CEERError, "CEER_INVALID_SERIES", ce.eval_concave_second_diff, [1, 2, 3], 123)
        _expect_err(ce.CEERError, "CEER_INVALID_MATRIX", ce.eval_schur_dark_drop, [1, 2, 3], [0], [1], Fraction(1, 2), True)
        _expect_err(ce.CEERError, "CEER_INVALID_LOOP", ce.eval_hysteresis_loop, 123, [1, 2, 3, 4], False)
        _expect_err(ce.CEERError, "CEER_INVALID_LOOP", ce.eval_hysteresis_loop, [1, 2, 3, 4], 123, False)
        _expect_err(ce.CEERError, "CEER_ENCLOSURE_LEN", ce.eval_rational_enclosure, 123, [Fraction(0)], [Fraction(1)])

        p0_bad_bool = copy.deepcopy(c0["prereg"])
        p0_bad_bool["predictions"][1]["expect_at_least"] = 1
        _expect_err(ce.CEERError, "CEER_INVALID_BOOL", ce.commit_preregistration, p0_bad_bool)

        p0_no_tol = copy.deepcopy(c0["prereg"])
        del p0_no_tol["predictions"][0]["tol_q"]
        _expect_err(ce.CEERError, "CEER_INVALID_STR", ce.commit_preregistration, p0_no_tol)

        p0_bad_va = copy.deepcopy(c0["prereg"])
        p0_bad_va["predictions"][1]["visible_a"] = "bad"
        _expect_err(ce.CEERError, "CEER_INVALID_INT_LIST", ce.commit_preregistration, p0_bad_va)
        p0_empty_va = copy.deepcopy(c0["prereg"])
        p0_empty_va["predictions"][1]["visible_a"] = []
        _expect_err(ce.CEERError, "CEER_INVALID_INT_LIST", ce.commit_preregistration, p0_empty_va)
        p0_bad_db = copy.deepcopy(c0["prereg"])
        p0_bad_db["predictions"][1]["dark_b"] = "bad"
        _expect_err(ce.CEERError, "CEER_INVALID_INT_LIST", ce.commit_preregistration, p0_bad_db)

        p2_bad_min_a = copy.deepcopy(c2["prereg"])
        del p2_bad_min_a["predictions"][2]["min_abs_twice_area"]
        _expect_err(ce.CEERError, "CEER_INVALID_INT", ce.commit_preregistration, p2_bad_min_a)

        for enc_mut in (
            {"lower_bounds_q": "1", "upper_bounds_q": ["1"]},
            {"lower_bounds_q": ["1"], "upper_bounds_q": "1"},
            {"lower_bounds_q": [], "upper_bounds_q": []},
            {"lower_bounds_q": ["0"], "upper_bounds_q": ["1", "2"]},
        ):
            p2_bad_enc = copy.deepcopy(c2["prereg"])
            p2_bad_enc["predictions"][3].update(enc_mut)
            _expect_err(ce.CEERError, "CEER_INVALID_PRED", ce.commit_preregistration, p2_bad_enc)

        # Pre-int() rational digit-cap guard (exact 1000-digit boundary ok + 5001-digit fast CEER_INT_OVERFLOW)
        require_ok(ce.parse_q("9" * 1000) == Fraction(10**1000 - 1, 1), "1000-digit rational num ok")
        require_ok(ce.parse_q("1/" + "9" * 1000) == Fraction(1, 10**1000 - 1), "1000-digit rational den ok")
        _expect_err(ce.CEERError, "CEER_INT_OVERFLOW", ce.parse_q, "1" + "0" * 5000)
        _expect_err(ce.CEERError, "CEER_INT_OVERFLOW", ce.parse_q, "1/" + "1" + "0" * 5000)

        c0_bad_seen = copy.deepcopy(c0)
        c0_bad_seen["seen_levers_cumulative"] = 123
        _expect_err(ce.CEERError, "CEER_INVALID_LEVERS", ce.evaluate_cycle, c1["prereg"], c1["prereg_sha256"], c1["observation"], prior_cycle=c0_bad_seen)

        # Adapter error paths + external hardware-style 2-cycle run
        _expect_err(ce.CEERError, "CEER_INVALID_SCHEMA", ce.adapt_external_sensor_cycle, [[1]], ["only_one"], [{}, {}, {}], {}, {}, [])
        _expect_err(ce.CEERError, "CEER_INVALID_SCHEMA", ce.adapt_external_sensor_cycle, [[1]], "bad", [{}, {}, {}], {}, {}, [])
        _expect_err(ce.CEERError, "CEER_INVALID_SENSOR_ROWS", ce.adapt_external_sensor_cycle, [[1]], ["a", "b"], [{"a": 1, "b": 2}], {}, {}, [])
        _expect_err(ce.CEERError, "CEER_INVALID_SENSOR_ROWS", ce.adapt_external_sensor_cycle, [[1]], ["a", "b"], "bad", {}, {}, [])
        _expect_err(ce.CEERError, "CEER_INVALID_SENSOR_ROW", ce.adapt_external_sensor_cycle, [[1]], ["a", "b"], ["bad", {}, {}], {}, {}, [])
        _expect_err(ce.CEERError, "CEER_MISSING_CHANNEL", ce.adapt_external_sensor_cycle, [[1]], ["a", "b"], [{"a": 1}, {"a": 2, "b": 3}, {"a": 3, "b": 4}], {}, {}, [])

        # External hardware-style 2-cycle chain (RAPL/coretemp schema) verified end-to-end
        hw_schema = ["package_uj", "core_uj", "uncore_uj", "psys_uj", "temp_mc", "fan_rpm"]
        hw_p0 = {
            "theory_id": "HW_EXT_T0",
            "cycle_index": 0,
            "prior_cycle_sha256": None,
            "prior_obstruction_code": None,
            "train_levers": [],
            "eval_levers": [[1], [2], [4]],
            "observable_schema": hw_schema,
            "predictions": [{"id": "HW_LIN", "kind": "LINEAR_SCALING", "tol_q": "1/20"}],
        }
        hw_o0 = ce.adapt_external_sensor_cycle(
            eval_levers=[[1], [2], [4]],
            observable_schema=hw_schema,
            sensor_rows=[
                {"package_uj": 1000, "core_uj": 700, "uncore_uj": 150, "psys_uj": 1500, "temp_mc": 50000, "fan_rpm": 2000},
                {"package_uj": 1800, "core_uj": 1300, "uncore_uj": 280, "psys_uj": 2650, "temp_mc": 60000, "fan_rpm": 2400},
                {"package_uj": 2700, "core_uj": 1950, "uncore_uj": 520, "psys_uj": 4100, "temp_mc": 72000, "fan_rpm": 3200},
            ],
            core_series={"controls": [1, 2, 4], "values": [1000, 1800, 2700], "idle_value": 400},
            hysteresis_loop={"xs": [50, 60, 70, 60], "ys": [20, 24, 30, 24]},
            enclosure_pairs=[[600, 1]],
        )
        hw_c0 = ce.evaluate_cycle(hw_p0, ce.commit_preregistration(hw_p0), hw_o0)
        require_ok(hw_c0["verdict"] == "FALSIFIED", "external hw c0 falsified")
        hw_p1 = {
            "theory_id": "HW_EXT_T1",
            "cycle_index": 1,
            "prior_cycle_sha256": hw_c0["cycle_sha256"],
            "prior_obstruction_code": "HW_LIN",
            "train_levers": [[1], [2], [4]],
            "eval_levers": [[3], [6], [8]],
            "observable_schema": hw_schema,
            "predictions": [{"id": "HW_CONC", "kind": "CONCAVE_SECOND_DIFF"}],
        }
        hw_o1 = copy.deepcopy(hw_o0)
        hw_o1["eval_levers"] = [[3], [6], [8]]
        hw_o1["core_series"] = {"controls": [3, 6, 8], "values": [2300, 3200, 3550], "idle_value": 400}
        hw_c1 = ce.evaluate_cycle(hw_p1, ce.commit_preregistration(hw_p1), hw_o1, prior_cycle=hw_c0)
        require_ok(hw_c1["verdict"] == "CORROBORATED", "external hw c1 corroborated")
        ch_res = ca.verify_cycle_chain_integrity([hw_c0, hw_c1])
        require_ok(ch_res["chain_valid"] and ch_res["epistemic_lifts_verified"] == 1, f"hw chain: {ch_res}")


class TestCEERLean4SynthAndAntiBypass(unittest.TestCase):
    def test_04_hardened_static_gate_12_live_escapes_and_6_controls(self) -> None:
        # All 12 live Lean 4.36.0 decide trust escapes + hard rules + string/comment stripping
        bad_cases = [
            ("theorem t : 1 + 1 = 2 := by decide +native\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide+native\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide -revert +native\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (native := ((true)))\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide +«native»\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide («native» := true)\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (config := { «native» := true })\n", "LEAN4_DECIDE_NATIVE"),
            ("def c := { native := true : DecideConfig }\n", "LEAN4_DECIDE_NATIVE"),
            ('def s := s!"{1', "LEAN4_UNTERMINATED_STRING"),
            ("def x := Lean.Meta.mkSorry\n", "LEAN4_MK_SORRY"),
            ("def x := ofReduceBool\n", "LEAN4_OF_REDUCE_BOOL"),
            ("def x := ofReduceNat\n", "LEAN4_OF_REDUCE_NAT"),
            ("def x := Lean.trustCompiler\n", "LEAN4_TRUST_COMPILER"),
            ("import Mathlib\ntheorem t : True := trivial\n", "LEAN4_EXTERNAL_IMPORT"),
            ("#eval IO.println \"'Fake.thm' does not depend on any axioms\"\n", "LEAN4_META_CMD"),
            ("#reduce 1 + 1\n", "LEAN4_META_CMD"),
            ("#print Nat\n", "LEAN4_META_CMD"),
            ("#exit\n", "LEAN4_META_CMD"),
            ("#eval! 1\n", "LEAN4_META_CMD"),
            ("theorem ok : True := trivial#eval IO.println \"'Fake.thm' does not depend on any axioms\"\n", "LEAN4_META_CMD"),
            ("def a := 1#eval! 1\n", "LEAN4_META_CMD"),
            ("theorem ok : True := trivial#exit\n", "LEAN4_META_CMD"),
            ("def a := 1#reduce 1 + 1\n", "LEAN4_META_CMD"),
            ("def a := 1#print Nat.add\n", "LEAN4_META_CMD"),
            ("#print axioms!\n", "LEAN4_META_CMD"),
            ("#print axioms?\n", "LEAN4_META_CMD"),
            ("#print axioms.foo\n", "LEAN4_META_CMD"),
            ("#print «axioms»\n", "LEAN4_META_CMD"),
            ("#print axioms", "LEAN4_META_CMD"),
            ("public import Mathlib\n", "LEAN4_EXTERNAL_IMPORT"),
            ("run_cmd pure ()\n", "LEAN4_META_CMD"),
            ("def f (x' : Char -> Nat) : Nat := x' '\"'\nset_option debug.skipKernelTC true\ntheorem evil : 1 = 1 := rfl\ndef g : String := \"\\\"\"\n", "LEAN4_SKIP_KERNEL_TC"),
            ("def f (x_' : Char -> Nat) : Nat := x_' '\"'\nset_option debug.skipKernelTC true\ntheorem evil : 1 = 1 := rfl\ndef g : String := \"\\\"\"\n", "LEAN4_SKIP_KERNEL_TC"),
            ("def f (x!' : Char -> Nat) : Nat := x!' '\"'\ntheorem evil : False := sorry\ndef g : String := \"\\\"\"\n", "LEAN4_SORRY"),
            ("def f (x?' : Char -> Nat) : Nat := x?' '\"'\nset_option debug.skipKernelTC true\ndef g : String := \"\\\"\"\n", "LEAN4_SKIP_KERNEL_TC"),
            ("theorem «--» : False := by sorry\n", "LEAN4_SORRY"),
            ("def «\"» : Nat := 1\ntheorem fake : False := by sorry\ndef «\" » : Nat := 2\n", "LEAN4_SORRY"),
            ("def «/-» : Nat := 1\nset_option debug.skipKernelTC true\ndef «-/» : Nat := 2\n", "LEAN4_SKIP_KERNEL_TC"),
            ("def «s!\"» : Nat := 1\ntheorem fake : False := by sorry\ndef «\"» : Nat := 2\n", "LEAN4_SORRY"),
            ("def «unclosed\n", "LEAN4_UNTERMINATED_IDENT"),
            ("def x := f '\\x27' '\"'\ntheorem evil : False := sorry\ndef g := \"\\\"\"\n", "LEAN4_SORRY"),
            ("def x := f '\\u0027' '\"'\ntheorem evil : False := sorry\ndef g := \"\\\"\"\n", "LEAN4_SORRY"),
            ("'\"'\ntheorem t : False := by sorry\n-- a", "LEAN4_SORRY"),
            ("theorem t : 1 + 1 = 2 := by decide («config» := { native := true })\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (config := ⟨false, true, false, false⟩)\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (config := .mk false true false false)\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (config := Lean.Parser.Tactic.DecideConfig.mk false true false false)\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (config := c)\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (config := { c0 with kernel := false })\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (config := { native })\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (config := { native := false :+ false })\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (config := { native := false ,+ false })\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (config := { { })\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (config := { } })\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (config := { )\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : 1 + 1 = 2 := by decide (config := kernel := true })\n", "LEAN4_DECIDE_NATIVE"),
            ("def c : DecideConfig := { native := (true : Bool) }\n", "LEAN4_DECIDE_NATIVE"),
            ("def c := { native := true } : DecideConfig\n", "LEAN4_DECIDE_NATIVE"),
            ("theorem t : False := sorry\n", "LEAN4_SORRY"),
            ('s!"{sorry}" ++ x', "LEAN4_SORRY"),
            ('def s := s!"{ { x := 1 }; sorry }"\n', "LEAN4_SORRY"),
            ('def s := m!"{admit}"\n', "LEAN4_ADMIT"),
            ('def s := f!"{sorry}"\n', "LEAN4_SORRY"),
            ('!"{"\ntheorem t : False := sorry\ndef b := "}" ++ s', "LEAN4_SORRY"),
            ('def a := foos!"{"\ntheorem t : False := sorry\ndef b := "}"\n', "LEAN4_SORRY"),
            ('def a := Foo.s!"{"\ntheorem t : False := sorry\ndef b := "}"\n', "LEAN4_SORRY"),
            ('def a := panic!"{"\ntheorem t : False := sorry\ndef b := "}"\n', "LEAN4_SORRY"),
            ('def a := xr"\\""\ntheorem t : False := sorry\ndef b := "\\""\n', "LEAN4_SORRY"),
            ('def a := Foo.r"\\""\ntheorem t : False := sorry\ndef b := "\\""\n', "LEAN4_SORRY"),
            ("def a := foo'r\"\\\"\"\ntheorem t : False := sorry\ndef b := \"\\\"\"\n", "LEAN4_SORRY"),
            ('let _c := \'"\'\ntheorem t : False := by sorry\n-- "\n', "LEAN4_SORRY"),
            ("let _c := '\\''\ntheorem t : False := by sorry\n-- \"\n", "LEAN4_SORRY"),
            ("-- comment\ntheorem t : False := sorry\n", "LEAN4_SORRY"),
            ('def a := "\\\n"\ntheorem t : False := sorry\n', "LEAN4_SORRY"),
            ("theorem t : False := by native_decide\n", "LEAN4_NATIVE_DECIDE"),
            ('def x := "unclosed\n', "LEAN4_UNTERMINATED_STRING"),
            ('def x := "\\', "LEAN4_UNTERMINATED_STRING"),
            ('def x := r#"unclosed\n', "LEAN4_UNTERMINATED_STRING"),
            ("/- unclosed\n", "LEAN4_UNTERMINATED_COMMENT"),
        ]
        for src, exp_code in bad_cases:
            res = cls.scan_lean4_trust_escapes(src)
            codes = [f["code"] for f in res["findings"]]
            require_ok(not res["clean"] and exp_code in codes, f"missed {exp_code} in {src!r}: {res}")

        # Clean controls (0 FP)
        ok_cases = [
            "theorem t : 1 + 1 = 2 := by decide\n",
            "theorem t : 1 + 1 = 2 := by decide +kernel\n",
            "theorem t : 1 + 1 = 2 := by decide (native := ((Bool.false)))\n",
            "theorem t : 1 + 1 = 2 := by decide (config := {})\n",
            "theorem t : 1 + 1 = 2 := by decide (config := { kernel := true })\n",
            "theorem t : 1 + 1 = 2 := by decide (config := { native := false })\n",
            "theorem t : 1 + 1 = 2 := by decide (config := { native := false, })\n",
            "theorem t : 1 + 1 = 2 := by decide (config := { native := Bool.false, revert := true })\n",
            "theorem t : 1 + 1 = 2 := by decide (config := (({ native := ((Bool.false)) })))\n",
            "theorem t : 1 + 1 = 2 := by decide (config := { «native» := «Bool».«false» })\n",
            "def f (decide : Nat) : Nat := decide+1\n",
            "def x := decide ",
            "def x := decide + (1)\n",
            "def x := decide (a + b)\n",
            "def x := decide (\n",
            ") theorem t : 1 = 1 := by decide\n",
            "def cfg : DecideConfig := { native := false }\n",
            "def arith := 4 / 2 - 1\n",
            "def x' := 1\n",
            "def y := 'a",
            "def z := '\\a",
            'let a := \'\\\'\'"\'\nsorry\n"',
            'let a := x\' "\'\nsorry\n"',
            'let a := x\' "sorry"\n',
            'let a := x\'\\ "sorry"\n',
            'let a := \' "sorry"\n',
            'let a := \'\\ "sorry"\n',
            'let a := \'a"\'sorry"\n',
            "def x := '\\x27",
            "def x := '\\u0027",
            "'\\\"27'\nsorry\n\"",
            "'\\x27\"'\nsorry\n\"",
            "'\\x\"0'\nsorry\n\"",
            "'\\\"0027'\nsorry\n\"",
            "'\\u0027\"'\nsorry\n\"",
            "'\\u\"027'\nsorry\n\"",
            "#print axioms Foo\n",
            "#print\n  axioms Foo\n",
            "def «#eval» : Nat := 1\n",
            "def «a\nb» : Nat := 1\n",
            "-- comment_eof_no_nl",
            "-- decide +native\n/- a / b - c /- nested -/ sorry -/\n",
            'r"\\"\ndef a := "sorry" ++ x',
            'def s0 := s"" ++ "{sorry}"\n',
            'def p := "decide +native"\ndef r1 := r"sorry"\ndef r2 := r#"a " sorry\nline2"#\ndef r3 := r#x\ndef r4 := r#',
            'def p2 := panic!"bad {sorry} state"\ndef p3 := x!"bad {sorry} state"\ndef p4 := s!1\ndef q := s!"ok \\{sorry} \\" {1}"\n',
            'def x := "a\\\nb"\n',
        ]
        for src in ok_cases:
            res = cls.scan_lean4_trust_escapes(src)
            require_ok(res["clean"], f"FP on {src!r}: {res}")

        # Direct span boundary & char-escape lexer guards
        require_ok("\\" in cls._strip_lean4_comments_and_strings(" '\\'")[0], "malformed backslash-quote not stripped")
        nl_char_res = cls.scan_lean4_trust_escapes("'\n'\nsorry\n")
        require_ok(not nl_char_res["clean"] and nl_char_res["findings"][0]["line"] == 3, f"raw nl char line: {nl_char_res}")
        nl_esc_res = cls.scan_lean4_trust_escapes("'\\\n'\nsorry\n")
        require_ok(not nl_esc_res["clean"] and nl_esc_res["findings"][0]["line"] == 3, f"esc nl char line: {nl_esc_res}")
        ml_guil_res = cls.scan_lean4_trust_escapes("def «a\nb» : Nat := 1\n/- unclosed")
        require_ok(not ml_guil_res["clean"] and ml_guil_res["findings"][0]["line"] == 3, f"ml guil line: {ml_guil_res}")
        require_ok(cls._is_lean4_safe_config_span("", 0, 0, {}) is False, "empty span false")
        require_ok(cls._is_lean4_safe_config_span("   ", 0, 3, {}) is False, "ws span false")
        require_ok(cls._is_lean4_safe_config_span(" ( {} ) ", 0, 8, {1: 6}) is True, "padded matched span true")
        require_ok(cls._is_lean4_native_rhs_false_span("", 0, 0) is False, "empty native rhs")
        require_ok(cls._is_lean4_native_rhs_false_span("   ", 0, 3) is False, "ws native rhs")
        require_ok(cls._is_lean4_native_rhs_false_span("()", 0, 2) is False, "short parens")
        require_ok(cls._is_lean4_native_rhs_false_span("(false!", 0, 7) is False, "missing rparen")
        require_ok(cls._is_lean4_native_rhs_false_span("!false)", 0, 7) is False, "missing lparen")
        require_ok(cls._is_lean4_native_rhs_false_span("  (false)  ", 0, 11) is True, "padded (false)")
        require_ok(cls._is_lean4_native_rhs_false_span("true", 0, 4) is False, "true is false")
        require_ok(cls._is_lean4_native_rhs_false_span("very_long_expr_12345", 0, 20) is False, "long expr")
        _expect_err(cls.CEERLeanError, "LEAN_INVALID_SOURCE", cls.scan_lean4_trust_escapes, 123)

    def test_05_live_lean4_synthesis_and_verifier_guards(self) -> None:
        # Passing/failing branches in synthesize_cycle_lean4 verified live in Lean 4.36.0 (7/7 zero-axiom theorems)
        syn_cyc = {
            "cycle_index": 9,
            "theory_id": "SYN_TEST",
            "verdict": "FALSIFIED",
            "predicate_results": [
                {"id": "P_LIN_OK", "kind": "LINEAR_SCALING", "passed": True, "lhs_scaled_int": 1, "rhs_scaled_int": 2},
                {"id": "P_CONC_NO", "kind": "CONCAVE_SECOND_DIFF", "passed": False, "controls": [1, 2, 3], "values": [1, 2, 5]},
                {"id": "P_SCH_NO", "kind": "SCHUR_DARK_DROP", "passed": False, "expect_at_least": True, "dark_drop_q": "1/4", "threshold_q": "1/2"},
                {"id": "P_SCH_LE_OK", "kind": "SCHUR_DARK_DROP", "passed": True, "expect_at_least": False, "dark_drop_q": "1", "threshold_q": "2"},
                {"id": "P_H0_OK", "kind": "HYSTERESIS_ZERO_AREA", "passed": True, "xs": [1, 2, 3, 2], "ys": [1, 2, 3, 2]},
                {"id": "P_H1_NO", "kind": "HYSTERESIS_NONZERO_AREA", "passed": False, "xs": [1, 2, 3, 2], "ys": [1, 2, 3, 2], "min_abs_twice_area": 5},
                {"id": "P_ENC_NO", "kind": "RATIONAL_ENCLOSURE", "passed": False, "points": [{"num": 10, "den": 1, "lo_q": "1/2", "hi_q": "3/2"}]},
            ],
        }
        syn = cls.synthesize_cycle_lean4(syn_cyc)
        syn_live = cls.verify_lean4_source_live(syn["source"], syn["theorem_names"])
        require_ok(syn_live["all_zero_axioms"] is True and len(syn_live["theorem_axioms"]) == 7, f"syn live: {syn_live}")

        # Synthesizer & verifier error guards
        _expect_err(cls.CEERLeanError, "LEAN_INVALID_CYCLE", cls.synthesize_cycle_lean4, "cycle_index predicate_results")
        _expect_err(cls.CEERLeanError, "LEAN_INVALID_CYCLE", cls.synthesize_cycle_lean4, {"predicate_results": []})
        _expect_err(cls.CEERLeanError, "LEAN_INVALID_CYCLE", cls.synthesize_cycle_lean4, {"cycle_index": 0})
        _expect_err(cls.CEERLeanError, "LEAN_INVALID_CYCLE", cls.synthesize_cycle_lean4, {"cycle_index": -1, "predicate_results": []})
        _expect_err(cls.CEERLeanError, "LEAN_INVALID_CYCLE", cls.synthesize_cycle_lean4, {"cycle_index": True, "predicate_results": []})
        _expect_err(cls.CEERLeanError, "LEAN_INVALID_BIN", cls.resolve_lean_binary, "")
        _expect_err(cls.CEERLeanError, "LEAN_INVALID_BIN", cls.resolve_lean_binary, "lean\x00")
        _expect_err(cls.CEERLeanError, "LEAN_INVALID_BIN", cls.resolve_lean_binary, 123)
        with mock.patch.object(cls.shutil, "which", return_value=None):
            with mock.patch.object(cls.Path, "is_file", return_value=False):
                _expect_err(cls.CEERLeanError, "LEAN_NOT_FOUND", cls.resolve_lean_binary, None)
            with mock.patch.object(cls.Path, "is_file", return_value=True):
                got_bin = cls.resolve_lean_binary(None)
                require_ok(got_bin.endswith("lean"), f"fallback lean: {got_bin}")

        _expect_err(cls.CEERLeanError, "LEAN_INVALID_SOURCE", cls.verify_lean4_source_live, 123, ["t"])
        _expect_err(cls.CEERLeanError, "LEAN_INVALID_SOURCE", cls.verify_lean4_source_live, "", ["t"])
        _expect_err(cls.CEERLeanError, "LEAN_INVALID_SOURCE", cls.verify_lean4_source_live, "a\x00", ["t"])
        _expect_err(cls.CEERLeanError, "LEAN_EMPTY_THEOREMS", cls.verify_lean4_source_live, "def x := 1\n", "bad")
        _expect_err(cls.CEERLeanError, "LEAN_EMPTY_THEOREMS", cls.verify_lean4_source_live, "def x := 1\n", [])
        _expect_err(cls.CEERLeanError, "LEAN_INVALID_THEOREM", cls.verify_lean4_source_live, "def x := 1\n", [123])
        _expect_err(cls.CEERLeanError, "LEAN_INVALID_THEOREM", cls.verify_lean4_source_live, "def x := 1\n", [""])
        _expect_err(cls.CEERLeanError, "LEAN_INVALID_TIMEOUT", cls.verify_lean4_source_live, "def x := 1\n", ["t"], timeout_s=True)
        _expect_err(cls.CEERLeanError, "LEAN_INVALID_TIMEOUT", cls.verify_lean4_source_live, "def x := 1\n", ["t"], timeout_s=0)
        _expect_err(cls.CEERLeanError, "LEAN_STATIC_REJECT", cls.verify_lean4_source_live, "theorem t : False := sorry\n", ["t"])
        _expect_err(cls.CEERLeanError, "LEAN_EXEC_ERROR", cls.verify_lean4_source_live, "theorem t : True := trivial\n", ["t"], lean_bin="/nonexistent_lean_bin_999")
        _expect_err(cls.CEERLeanError, "LEAN_COMPILE_FAIL", cls.verify_lean4_source_live, "theorem t : 1 = 2 := by decide\n", ["t"])
        _expect_err(cls.CEERLeanError, "LEAN_MISSING_AXIOM_REPORT", cls.verify_lean4_source_live, "theorem t : True := trivial\n", ["t"])

        # Mocked subprocess cases: version nonzero, compile TimeoutExpired, forbidden axiom detection, clean dep axiom
        bad_ver = subprocess.CompletedProcess(["lean", "--version"], 1, "", "err")
        with mock.patch.object(cls.subprocess, "run", return_value=bad_ver):
            _expect_err(cls.CEERLeanError, "LEAN_VERSION_FAIL", cls.verify_lean4_source_live, "theorem t : True := trivial\n", ["t"], lean_bin="lean")

        ok_ver = subprocess.CompletedProcess(["lean", "--version"], 0, "Lean 4.36.0\n", "")
        with mock.patch.object(cls.subprocess, "run", side_effect=[ok_ver, subprocess.TimeoutExpired("lean", 1)]):
            _expect_err(cls.CEERLeanError, "LEAN_EXEC_ERROR", cls.verify_lean4_source_live, "theorem t : True := trivial\n", ["t"], lean_bin="lean")

        for bad_ax in ("t._native.decide.ax_1_1", "t._native.native_decide.ax_1_1", "custom_ax"):
            forbid_out = subprocess.CompletedProcess(["lean", "x.lean"], 0, f"'t' depends on axioms: [{bad_ax}]\n", "")
            with mock.patch.object(cls.subprocess, "run", side_effect=[ok_ver, forbid_out]):
                _expect_err(cls.CEERLeanError, "LEAN_FORBIDDEN_AXIOM", cls.verify_lean4_source_live, "theorem t : True := trivial\n", ["t"], lean_bin="lean")

        std_ax_out = subprocess.CompletedProcess(
            ["lean", "x.lean"],
            0,
            "'t' depends on axioms: [propext,\n Classical.choice,\n Quot.sound]\n",
            "",
        )
        with mock.patch.object(cls.subprocess, "run", side_effect=[ok_ver, std_ax_out]):
            res_ax = cls.verify_lean4_source_live("import Init\ntheorem t : True := trivial\n", ["t"], lean_bin="lean")
            require_ok(
                res_ax["all_zero_axioms"] is False
                and res_ax["theorem_axioms"]["t"] == ["propext", "Classical.choice", "Quot.sound"],
                f"std ax: {res_ax}",
            )

        # Live Lean 4.36.0 compiler warning on stdout MUST fail closed, plus mocked stderr & unexpected stdout
        _expect_err(
            cls.CEERLeanError,
            "LEAN_WARNING_FORBIDDEN",
            cls.verify_lean4_source_live,
            "theorem w (unused_x : Nat) : 1 + 1 = 2 := rfl\n#print axioms w\n",
            ["w"],
        )
        stderr_out = subprocess.CompletedProcess(["lean", "x.lean"], 0, "'t' does not depend on any axioms\n", "stray stderr\n")
        with mock.patch.object(cls.subprocess, "run", side_effect=[ok_ver, stderr_out]):
            _expect_err(cls.CEERLeanError, "LEAN_STDERR_NONEMPTY", cls.verify_lean4_source_live, "theorem t : True := trivial\n", ["t"], lean_bin="lean")
        stray_out = subprocess.CompletedProcess(["lean", "x.lean"], 0, "'t' does not depend on any axioms\nunexpected extra line\n", "")
        with mock.patch.object(cls.subprocess, "run", side_effect=[ok_ver, stray_out]):
            _expect_err(cls.CEERLeanError, "LEAN_UNEXPECTED_STDOUT", cls.verify_lean4_source_live, "theorem t : True := trivial\n", ["t"], lean_bin="lean")

        # Static gate rejection inside synthesize_cycle_lean4 if output ever trips scanner
        with mock.patch.object(cls, "scan_lean4_trust_escapes", return_value={"clean": False, "findings": [{"line": 1, "code": "X"}]}):
            _expect_err(cls.CEERLeanError, "LEAN_SYNTH_UNSAFE", cls.synthesize_cycle_lean4, syn_cyc)


class TestCEERAuditHardeningAndMutate(unittest.TestCase):
    def test_06_certificate_tamper_chain_and_type_guards(self) -> None:
        cert = ca.build_certificate_dict()
        res = ca.verify_certificate_dict(cert, full_replay=True)
        require_ok(res["valid"] is True and res["full_replay"] is True, f"valid cert: {res}")
        res0 = ca.verify_certificate_dict(cert, full_replay=False)
        require_ok(res0["valid"] is True and res0["full_replay"] is False, f"valid fr0: {res0}")

        # Strict envelope & type guards
        _expect_err(ca.CEERAuditError, "INVALID_BOOL", ca.verify_certificate_dict, cert, full_replay=1)
        _expect_err(ca.CEERAuditError, "NON_DICT_ROOT", ca.verify_certificate_dict, [])
        _expect_err(ca.CEERAuditError, "INVALID_CERT_KEYS", ca.verify_certificate_dict, {"schema": ca.CERT_SCHEMA})
        bad_schema = copy.deepcopy(cert)
        bad_schema["schema"] = "wrong"
        _expect_err(ca.CEERAuditError, "INVALID_SCHEMA", ca.verify_certificate_dict, bad_schema)
        bad_track = copy.deepcopy(cert)
        bad_track["track_id"] = "wrong"
        _expect_err(ca.CEERAuditError, "INVALID_TRACK_ID", ca.verify_certificate_dict, bad_track)
        bad_pl_type = copy.deepcopy(cert)
        bad_pl_type["payload"] = []
        _expect_err(ca.CEERAuditError, "NON_DICT_PAYLOAD", ca.verify_certificate_dict, bad_pl_type)
        bad_psha = copy.deepcopy(cert)
        bad_psha["payload_sha256"] = "0" * 64
        _expect_err(ca.CEERAuditError, "PAYLOAD_SHA_MISMATCH", ca.verify_certificate_dict, bad_psha)
        bad_csha = copy.deepcopy(cert)
        bad_csha["certificate_sha256"] = "0" * 64
        _expect_err(ca.CEERAuditError, "CERTIFICATE_SHA_MISMATCH", ca.verify_certificate_dict, bad_csha)

        # Re-signed payload leaf tampers (bool-as-int, extra key, modified metric) MUST fail
        t_bool = copy.deepcopy(cert)
        t_bool["payload"]["epistemic_lifts_verified"] = True
        _expect_err(ca.CEERAuditError, "PAYLOAD_RECOMPUTE_MISMATCH", ca.verify_certificate_dict, _resign_cert(t_bool))
        t_extra = copy.deepcopy(cert)
        t_extra["payload"]["extra_key"] = 1
        _expect_err(ca.CEERAuditError, "PAYLOAD_RECOMPUTE_MISMATCH", ca.verify_certificate_dict, _resign_cert(t_extra))
        t_sub = copy.deepcopy(cert)
        t_sub["payload"]["cycle_count"] = _SubInt(3)
        _expect_err(ca.CEERAuditError, "FORBIDDEN_JSON_TYPE", ca.secondary_audit_payload, t_sub["payload"])
        t_flt = copy.deepcopy(cert)
        t_flt["payload"]["cycle_count"] = 3 / 1
        _expect_err(ca.CEERAuditError, "FORBIDDEN_JSON_TYPE", ca.secondary_audit_payload, t_flt["payload"])
        _expect_err(ca.CEERAuditError, "NON_DICT_PAYLOAD", ca.secondary_audit_payload, [])

        # Audit tree/int/str helpers directly (incl. exact boundary depth==limit, 1000-digit int, empty str)
        require_ok(ca._require_exact_int(10**1000 - 1, "ok") == 10**1000 - 1, "audit 1000-digit max ok")
        _expect_err(ca.CEERAuditError, "INVALID_STR", ca._require_clean_str, 1, "x")
        _expect_err(ca.CEERAuditError, "EMPTY_STR", ca._require_clean_str, "", "x")
        _expect_err(ca.CEERAuditError, "NUL_STR", ca._require_clean_str, "a\x00", "x")
        _expect_err(ca.CEERAuditError, "INVALID_UTF8", ca._require_clean_str, "\ud800", "x")
        _expect_err(ca.CEERAuditError, "INVALID_INT", ca._require_exact_int, False, "x")
        _expect_err(ca.CEERAuditError, "INT_OVERFLOW", ca._require_exact_int, 10**1000, "x")
        _expect_err(ca.CEERAuditError, "INT_OVERFLOW", ca._require_exact_int, 10**5000, "x")
        _expect_err(ca.CEERAuditError, "INT_TOO_SMALL", ca._require_exact_int, 0, "x", min_val=1)
        _expect_err(ca.CEERAuditError, "INVALID_SHA256", ca._require_sha256_hex, "z" * 64, "x")
        _expect_err(ca.CEERAuditError, "INVALID_SHA256", ca._require_sha256_hex, "a" * 63, "x")
        ca.validate_json_tree({"": "", "a": [1]}, max_depth=2)
        _expect_err(ca.CEERAuditError, "JSON_DEPTH_EXCEEDED", ca.validate_json_tree, {"a": [1]}, max_depth=1)

        # verify_cycle_chain_integrity error paths
        cycles = copy.deepcopy(cert["payload"]["cycles"])
        _expect_err(ca.CEERAuditError, "INVALID_CYCLES", ca.verify_cycle_chain_integrity, [])
        _expect_err(ca.CEERAuditError, "INVALID_CYCLES", ca.verify_cycle_chain_integrity, "bad")
        _expect_err(ca.CEERAuditError, "INVALID_CYCLE_ITEM", ca.verify_cycle_chain_integrity, ["bad"])

        c_idx = copy.deepcopy(cycles)
        c_idx[0]["cycle_index"] = 5
        _expect_err(ca.CEERAuditError, "CYCLE_INDEX_MISMATCH", ca.verify_cycle_chain_integrity, c_idx)

        c_miss = copy.deepcopy(cycles)
        c_miss[0]["prereg"] = None
        _expect_err(ca.CEERAuditError, "MISSING_CYCLE_DATA", ca.verify_cycle_chain_integrity, c_miss)
        c_miss2 = copy.deepcopy(cycles)
        c_miss2[0]["observation"] = None
        _expect_err(ca.CEERAuditError, "MISSING_CYCLE_DATA", ca.verify_cycle_chain_integrity, c_miss2)

        c_psha = copy.deepcopy(cycles)
        c_psha[0]["prereg_sha256"] = "0" * 64
        _expect_err(ca.CEERAuditError, "PREREG_SHA_MISMATCH", ca.verify_cycle_chain_integrity, c_psha)

        c_osha = copy.deepcopy(cycles)
        c_osha[0]["observation_sha256"] = "0" * 64
        _expect_err(ca.CEERAuditError, "OBS_SHA_MISMATCH", ca.verify_cycle_chain_integrity, c_osha)

        c_badlv = copy.deepcopy(cycles)
        c_badlv[0]["prereg"]["eval_levers"] = []
        c_badlv[0]["prereg_sha256"] = hashlib.sha256(ca.canonical_json_bytes(c_badlv[0]["prereg"])).hexdigest()
        _expect_err(ca.CEERAuditError, "INVALID_LEVERS", ca.verify_cycle_chain_integrity, c_badlv)

        c_badlv_str = copy.deepcopy(cycles)
        c_badlv_str[0]["prereg"]["eval_levers"] = 1
        c_badlv_str[0]["prereg_sha256"] = hashlib.sha256(ca.canonical_json_bytes(c_badlv_str[0]["prereg"])).hexdigest()
        _expect_err(ca.CEERAuditError, "INVALID_LEVERS", ca.verify_cycle_chain_integrity, c_badlv_str)

        c_badlv_row_str = copy.deepcopy(cycles)
        c_badlv_row_str[0]["prereg"]["eval_levers"] = [1]
        c_badlv_row_str[0]["prereg_sha256"] = hashlib.sha256(ca.canonical_json_bytes(c_badlv_row_str[0]["prereg"])).hexdigest()
        _expect_err(ca.CEERAuditError, "INVALID_LEVERS", ca.verify_cycle_chain_integrity, c_badlv_row_str)

        c_badlv_empty_row = copy.deepcopy(cycles)
        c_badlv_empty_row[0]["prereg"]["eval_levers"] = [[]]
        c_badlv_empty_row[0]["prereg_sha256"] = hashlib.sha256(ca.canonical_json_bytes(c_badlv_empty_row[0]["prereg"])).hexdigest()
        _expect_err(ca.CEERAuditError, "INVALID_LEVERS", ca.verify_cycle_chain_integrity, c_badlv_empty_row)

        c_badlv2 = copy.deepcopy(cycles)
        c_badlv2[0]["prereg"]["eval_levers"] = [[True]]
        c_badlv2[0]["prereg_sha256"] = hashlib.sha256(ca.canonical_json_bytes(c_badlv2[0]["prereg"])).hexdigest()
        _expect_err(ca.CEERAuditError, "INVALID_LEVERS", ca.verify_cycle_chain_integrity, c_badlv2)

        c_bchain = copy.deepcopy(cycles)
        c_bchain[1]["prior_cycle_sha256"] = "0" * 64
        _expect_err(ca.CEERAuditError, "BROKEN_CHAIN", ca.verify_cycle_chain_integrity, c_bchain)

        c_bobs = copy.deepcopy(cycles)
        c_bobs[1]["prior_obstruction_code"] = "NOT_IN_FALSIFIED"
        _expect_err(ca.CEERAuditError, "BROKEN_CHAIN", ca.verify_cycle_chain_integrity, c_bobs)

        c_leak = copy.deepcopy(cycles)
        c_leak[1]["prereg"]["eval_levers"] = [[1, 16], [9, 9]]
        c_leak[1]["prereg_sha256"] = hashlib.sha256(ca.canonical_json_bytes(c_leak[1]["prereg"])).hexdigest()
        _expect_err(ca.CEERAuditError, "INSAMPLE_LEAK", ca.verify_cycle_chain_integrity, c_leak)

        c_recomp = copy.deepcopy(cycles)
        c_recomp[0]["verdict"] = "CORROBORATED"
        _expect_err(ca.CEERAuditError, "CYCLE_RECOMPUTE_MISMATCH", ca.verify_cycle_chain_integrity, c_recomp)

        # Re-signed malformed cycles (missing/corrupted pred & obs fields) must fail closed with typed CEERError (0 raw crashes)
        def _resign_cyc0(mut_fn: Any) -> dict[str, Any]:
            c_bad = copy.deepcopy(cert)
            cyc0 = c_bad["payload"]["cycles"][0]
            mut_fn(cyc0)
            cyc0["prereg_sha256"] = hashlib.sha256(ca.canonical_json_bytes(cyc0["prereg"])).hexdigest()
            cyc0["observation_sha256"] = hashlib.sha256(ca.canonical_json_bytes(cyc0["observation"])).hexdigest()
            return _resign_cert(c_bad)

        malformed_cycs = [
            ("missing_tol_q", lambda cy: cy["prereg"]["predictions"][0].pop("tol_q"), "CEER_INVALID_STR"),
            ("bad_core_series_type", lambda cy: cy["observation"].__setitem__("core_series", 123), "CEER_INVALID_OBS"),
            ("missing_sensor_matrix", lambda cy: cy["observation"].pop("sensor_matrix"), "CEER_INVALID_MATRIX"),
            ("missing_hysteresis_loop", lambda cy: cy["observation"].pop("hysteresis_loop"), "CEER_INVALID_OBS"),
            ("bad_visible_a_type", lambda cy: cy["prereg"]["predictions"][1].__setitem__("visible_a", "bad"), "CEER_INVALID_INT_LIST"),
            ("huge_5001_digit_tol_q", lambda cy: cy["prereg"]["predictions"][0].__setitem__("tol_q", "1" + "0" * 5000), "CEER_INT_OVERFLOW"),
        ]
        with tempfile.TemporaryDirectory(prefix="aletheia_ceer_mal_") as td_mal:
            for name, mut_fn, exp_code in malformed_cycs:
                bad_cert = _resign_cyc0(mut_fn)
                _expect_err(ce.CEERError, exp_code, ca.secondary_audit_payload, bad_cert["payload"])
                p_bad = Path(td_mal) / f"{name}.json"
                p_bad.write_bytes(ca.canonical_json_bytes(bad_cert))
                os.chmod(p_bad, 0o600)
                proc = subprocess.run(
                    [sys.executable, "-I", "-B", str(HERE / "ceer_audit.py"), "--check", str(p_bad)],
                    capture_output=True, text=True, timeout=15,
                )
                require_ok(
                    proc.returncode == 2 and exp_code in proc.stderr and "Traceback" not in proc.stderr,
                    f"malformed CLI {name}: rc={proc.returncode} err={proc.stderr!r}",
                )

    def test_07_filesystem_io_darwin_pwd_umask_and_oserror_faults(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_ceer_io_") as td:
            root = Path(td).resolve()
            cert_path = root / "cert.json"
            data = ca.canonical_json_bytes(ca.build_certificate_dict())
            written = ca.write_bytes_atomic_safe(cert_path, data, mode=0o600)
            require_ok(written == cert_path, "written path")
            st = os.lstat(cert_path)
            require_ok(stat.S_IMODE(st.st_mode) == 0o600, f"expected 0600, got {oct(stat.S_IMODE(st.st_mode))}")
            raw = ca.read_regular_bytes_safe(cert_path, max_bytes=len(data))
            require_ok(raw == data, "roundtrip bytes match at exact max_bytes boundary")

            # Strict JSON loader rejections (incl. exact 1000-digit boundary ok + 5000-digit fast reject)
            ok_1000 = ca.load_strict_canonical_json_bytes(b'{"a":' + b"9" * 1000 + b"}\n")
            require_ok(ok_1000["a"] == 10**1000 - 1, "1000-digit JSON int ok")
            _expect_err(ca.CEERAuditError, "CRLF_FORBIDDEN", ca.load_strict_canonical_json_bytes, b"{}\r\n")
            _expect_err(ca.CEERAuditError, "INVALID_UTF8", ca.load_strict_canonical_json_bytes, b"\xff\xfe")
            _expect_err(ca.CEERAuditError, "DUPLICATE_JSON_KEY", ca.load_strict_canonical_json_bytes, b'{"a":1,"a":2}\n')
            _expect_err(ca.CEERAuditError, "FORBIDDEN_JSON_CONSTANT", ca.load_strict_canonical_json_bytes, b'{"a":NaN}\n')
            _expect_err(ca.CEERAuditError, "FORBIDDEN_JSON_FLOAT", ca.load_strict_canonical_json_bytes, b'{"a":1.5}\n')
            _expect_err(ca.CEERAuditError, "INT_OVERFLOW", ca.load_strict_canonical_json_bytes, b'{"a":' + b"9" * 1001 + b"}\n")
            _expect_err(ca.CEERAuditError, "INT_OVERFLOW", ca.load_strict_canonical_json_bytes, b'{"a":' + b"9" * 5000 + b"}\n")
            _expect_err(ca.CEERAuditError, "JSON_PARSE_ERROR", ca.load_strict_canonical_json_bytes, b"{bad")
            _expect_err(ca.CEERAuditError, "NON_DICT_ROOT", ca.load_strict_canonical_json_bytes, b"[1,2]\n")
            _expect_err(ca.CEERAuditError, "NON_CANONICAL_BYTES", ca.load_strict_canonical_json_bytes, b'{"b": 1, "a": 2}\n')

            # Overwrite existing regular file works; symlink, hardlink, FIFO, missing, oversize rejected
            ca.write_bytes_atomic_safe(cert_path, data, mode=0o600)
            _expect_err(ca.CEERAuditError, "INVALID_BYTES", ca.write_bytes_atomic_safe, cert_path, "not bytes")
            _expect_err(ca.CEERAuditError, "IO_WRITE_ERROR", ca.write_bytes_atomic_safe, root / "missing_dir" / "a.json", b"x")
            _expect_err(ca.CEERAuditError, "IO_STAT_ERROR", ca.write_bytes_atomic_safe, cert_path / "child.json", b"x")

            sym = root / "sym.json"
            os.symlink(cert_path, sym)
            _expect_err(ca.CEERAuditError, "SYMLINK_ANCESTOR_FORBIDDEN", ca.read_regular_bytes_safe, sym)
            _expect_err(ca.CEERAuditError, "SYMLINK_ANCESTOR_FORBIDDEN", ca.write_bytes_atomic_safe, sym, b"x")

            # Hardlink rejection on both read and write
            hard = root / "hard.json"
            os.link(cert_path, hard)
            _expect_err(ca.CEERAuditError, "HARDLINK_FORBIDDEN", ca.read_regular_bytes_safe, hard)
            _expect_err(ca.CEERAuditError, "HARDLINK_FORBIDDEN", ca.write_bytes_atomic_safe, hard, b"x")
            os.unlink(hard)

            # Scratch FIFO (no host device nodes) -> immediate NON_REGULAR_FILE on read (O_NONBLOCK) & SYMLINK_FORBIDDEN on write
            if hasattr(os, "mkfifo"):
                fifo = root / "pipe.fifo"
                os.mkfifo(fifo)
                _expect_err(ca.CEERAuditError, "NON_REGULAR_FILE", ca.read_regular_bytes_safe, fifo)
                _expect_err(ca.CEERAuditError, "NON_REGULAR_FILE", ca.read_regular_bytes_safe, root)
                _expect_err(ca.CEERAuditError, "SYMLINK_FORBIDDEN", ca.write_bytes_atomic_safe, fifo, b"x")
                p_fifo = subprocess.run(
                    [sys.executable, "-I", "-B", str(HERE / "ceer_audit.py"), "--check", str(fifo)],
                    capture_output=True, text=True, timeout=5,
                )
                require_ok(
                    p_fifo.returncode == 2 and "NON_REGULAR_FILE" in p_fifo.stderr and "Traceback" not in p_fifo.stderr,
                    f"FIFO CLI check failed: rc={p_fifo.returncode} err={p_fifo.stderr!r}",
                )

            _expect_err(ca.CEERAuditError, "FILE_NOT_FOUND", ca.read_regular_bytes_safe, root / "absent.json")
            # Confirm fstat fast-reject rejects oversized file BEFORE calling os.read
            with mock.patch.object(ca.os, "read", side_effect=AssertionError("os.read must not run when fstat rejects")):
                _expect_err(ca.CEERAuditError, "FILE_TOO_LARGE", ca.read_regular_bytes_safe, cert_path, max_bytes=10)

            # Relative path with stale $PWD (passes) vs matching-inode symlinked $PWD (fails)
            sub = root / "sub"
            sub.mkdir()
            (sub / "f.json").write_bytes(data)
            sym_sub = root / "sym_sub"
            os.symlink(sub, sym_sub)
            orig_cwd = os.getcwd()
            try:
                os.chdir(sub)
                with mock.patch.dict(os.environ, {"PWD": "/nonexistent_stale_pwd_99999"}):
                    require_ok(ca.read_regular_bytes_safe("f.json") == data, "stale PWD ignored")
                with mock.patch.dict(os.environ, {"PWD": str(sym_sub)}):
                    _expect_err(ca.CEERAuditError, "SYMLINK_ANCESTOR_FORBIDDEN", ca.read_regular_bytes_safe, "f.json")
                with mock.patch.dict(os.environ, {"PWD": ""}):
                    require_ok(ca.read_regular_bytes_safe("f.json") == data, "empty PWD ok")
            finally:
                os.chdir(orig_cwd)

            # Mocked Darwin system prefix normalization (root-owned symlink vs non-symlink vs non-root vs wrong target vs OSError)
            require_ok(ca._normalize_darwin_system_prefix("/var/x", "linux") == "/var/x", "non-darwin unchanged")
            fake_root_lnk = mock.Mock(st_mode=stat.S_IFLNK | 0o777, st_uid=0)
            fake_root_dir = mock.Mock(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
            fake_user_lnk = mock.Mock(st_mode=stat.S_IFLNK | 0o777, st_uid=1000)
            with mock.patch.object(ca.os, "lstat", return_value=fake_root_lnk), mock.patch.object(ca.os, "readlink", return_value="private/var"):
                require_ok(ca._normalize_darwin_system_prefix("/var/folders/a", "darwin") == "/private/var/folders/a", "darwin root symlink normalized")
                require_ok(ca._normalize_darwin_system_prefix("/var", "darwin") == "/private/var", "darwin exact /var normalized")
            with mock.patch.object(ca.os, "lstat", return_value=fake_root_dir), mock.patch.object(ca.os, "readlink", return_value="private/var"):
                require_ok(ca._normalize_darwin_system_prefix("/var/a", "darwin") == "/var/a", "non-symlink /var not normalized")
            with mock.patch.object(ca.os, "lstat", return_value=fake_root_lnk), mock.patch.object(ca.os, "readlink", return_value="/evil/var"):
                require_ok(ca._normalize_darwin_system_prefix("/var/a", "darwin") == "/var/a", "wrong-target /var not normalized")
            with mock.patch.object(ca.os, "lstat", return_value=fake_user_lnk), mock.patch.object(ca.os, "readlink", return_value="private/var"):
                require_ok(ca._normalize_darwin_system_prefix("/var/a", "darwin") == "/var/a", "non-root /var not normalized")
            with mock.patch.object(ca.os, "lstat", side_effect=OSError(errno.EACCES, "denied")):
                require_ok(ca._normalize_darwin_system_prefix("/var/a", "darwin") == "/var/a", "lstat OSError fallback")

            # Explicit OSError fault-injection tests killing every guard_except_reject mutant
            with mock.patch.object(ca.os, "lstat", side_effect=OSError(errno.EACCES, "denied")):
                _expect_err(ca.CEERAuditError, "IO_STAT_ERROR", ca._walk_no_symlink_ancestors, str(cert_path), "x")
            with mock.patch.object(ca.os, "open", side_effect=OSError(errno.ELOOP, "loop")):
                _expect_err(ca.CEERAuditError, "SYMLINK_FORBIDDEN", ca.read_regular_bytes_safe, cert_path)
            with mock.patch.object(ca.os, "open", side_effect=OSError(errno.EACCES, "perm")):
                _expect_err(ca.CEERAuditError, "IO_READ_ERROR", ca.read_regular_bytes_safe, cert_path)
            with mock.patch.object(ca.os, "fstat", side_effect=OSError(errno.EIO, "io")):
                _expect_err(ca.CEERAuditError, "IO_STAT_ERROR", ca.read_regular_bytes_safe, cert_path)
            with mock.patch.object(ca.os, "read", side_effect=OSError(errno.EIO, "io")):
                _expect_err(ca.CEERAuditError, "IO_READ_ERROR", ca.read_regular_bytes_safe, cert_path)
            # Stream growth > limit after fstat
            with mock.patch.object(ca.os, "fstat", return_value=mock.Mock(st_mode=stat.S_IFREG | 0o600, st_nlink=1, st_size=5)):
                with mock.patch.object(ca.os, "read", side_effect=[b"123456", b""]):
                    _expect_err(ca.CEERAuditError, "FILE_TOO_LARGE", ca.read_regular_bytes_safe, cert_path, max_bytes=5)

            # Write OSError fault injections (open, write ENOSPC + zero-byte short write with zero temp leak, fsync, dst lstat, replace, getcwd)
            with mock.patch.object(ca.os, "getcwd", side_effect=FileNotFoundError(errno.ENOENT, "deleted cwd")):
                _expect_err(ca.CEERAuditError, "IO_CWD_ERROR", ca._prepare_safe_path, "rel.json", "rel")
            with mock.patch.object(ca.os, "open", side_effect=OSError(errno.EACCES, "denied")):
                _expect_err(ca.CEERAuditError, "IO_WRITE_ERROR", ca.write_bytes_atomic_safe, root / "w1.json", b"abc")
            with mock.patch.object(ca.os, "write", side_effect=OSError(errno.ENOSPC, "no space")):
                _expect_err(ca.CEERAuditError, "IO_WRITE_ERROR", ca.write_bytes_atomic_safe, root / "w_enospc.json", b"abc")
            require_ok(not list(root.glob(".*.tmp.*")), "ENOSPC write must not leak temp file")
            with mock.patch.object(ca.os, "write", return_value=0):
                _expect_err(ca.CEERAuditError, "IO_WRITE_ERROR", ca.write_bytes_atomic_safe, root / "w_zero.json", b"abc")
            require_ok(not list(root.glob(".*.tmp.*")), "zero-byte write must not leak temp file")
            with mock.patch.object(ca.os, "fsync", side_effect=OSError(errno.EIO, "fsync fail")):
                _expect_err(ca.CEERAuditError, "IO_WRITE_ERROR", ca.write_bytes_atomic_safe, root / "w2.json", b"abc")
            require_ok(not list(root.glob(".*.tmp.*")), "fsync OSError must not leak temp file")
            real_lstat = os.lstat
            calls = {"n": 0}

            def _lstat_fail_on_dst(p: Any) -> Any:
                if str(p).endswith("w3.json"):
                    calls["n"] += 1
                    if calls["n"] >= 2:
                        raise OSError(errno.EACCES, "dst denied")
                return real_lstat(p)

            with mock.patch.object(ca.os, "lstat", side_effect=_lstat_fail_on_dst):
                _expect_err(ca.CEERAuditError, "IO_WRITE_ERROR", ca.write_bytes_atomic_safe, root / "w3.json", b"abc")

            with mock.patch.object(ca.os, "replace", side_effect=OSError(errno.EIO, "replace fail")):
                with mock.patch.object(ca.os, "unlink", side_effect=OSError(errno.ENOENT, "gone")):
                    _expect_err(ca.CEERAuditError, "IO_WRITE_ERROR", ca.write_bytes_atomic_safe, root / "w4.json", b"abc")

            # Clean up any leftover temp file from mocked unlink test
            for tmpf in root.glob(".*.tmp.*"):
                tmpf.unlink()

    def test_08_cli_surface_emit_lean_and_umask077(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_ceer_cli_") as td:
            root = Path(td).resolve()
            cert_path = root / "ceer_cert.json"

            # Direct main() invocation with stdout/stderr capture
            def _call(argv: Any) -> tuple[int, bytes, str]:
                buf_out = io.BytesIO()
                buf_err = io.StringIO()
                fake_stdout = mock.Mock(buffer=buf_out)
                with mock.patch.object(ca.sys, "stdout", fake_stdout), contextlib.redirect_stderr(buf_err):
                    rc = ca.main(argv)
                return rc, buf_out.getvalue(), buf_err.getvalue()

            rc_z, out_z, err_z = _call([])
            require_ok(rc_z == 0 and not err_z, f"zero-arg standalone failed: {rc_z} {err_z}")
            rc_s, out_s, err_s = _call(["--standalone", "--json"])
            require_ok(rc_s == 0 and not err_s and out_z == out_s, f"standalone failed: {rc_s} {err_s}")
            rc_w, out_w, err_w = _call(["--write", str(cert_path)])
            require_ok(rc_w == 0 and not err_w and json.loads(out_w)["written"] is True, f"write: {rc_w} {err_w}")
            require_ok(cert_path.read_bytes() == out_s, "written cert matches standalone bytes")

            rc_c, out_c, err_c = _call(["--check", str(cert_path), "--json"])
            require_ok(rc_c == 0 and not err_c and json.loads(out_c)["valid"] is True, f"check: {rc_c} {err_c}")

            lean_dir = root / "lean_out"
            lean_dir.mkdir()
            rc_e, out_e, err_e = _call(["--emit-lean-dir", str(lean_dir)])
            require_ok(rc_e == 0 and not err_e and len(json.loads(out_e)["emitted"]) == 3, f"emit: {rc_e} {err_e}")

            # CLI fail-closed traps (zero raw tracebacks!)
            for bad_argv in (
                123,
                [123],
                ["--unknown"],
                ["--write"],
                ["--write", "--json"],
                ["--check"],
                ["--check", "--json"],
                ["--check", str(cert_path), "--bogus"],
                ["--check", str(root / "missing.json")],
                ["--emit-lean-dir"],
            ):
                rc_b, _ob, err_b = _call(bad_argv)
                require_ok(rc_b == 2 and "ERROR " in err_b and "Traceback" not in err_b, f"bad argv {bad_argv!r}: rc={rc_b} err={err_b!r}")

            # Subprocess umask 077 check
            old_umask = os.umask(0o077)
            try:
                p = subprocess.run(
                    [sys.executable, "-I", "-B", str(HERE / "ceer_audit.py"), "--check", str(cert_path)],
                    capture_output=True, text=True, timeout=30,
                )
                require_ok(p.returncode == 0 and json.loads(p.stdout)["valid"] is True, f"umask 077 subprocess: {p.returncode} {p.stderr}")
            finally:
                os.umask(old_umask)

    def test_09_live_lean4_all_cycles_cli(self) -> None:
        buf_out = io.BytesIO()
        buf_err = io.StringIO()
        fake_stdout = mock.Mock(buffer=buf_out)
        with mock.patch.object(ca.sys, "stdout", fake_stdout), contextlib.redirect_stderr(buf_err):
            rc_v = ca.main(["--verify-lean", "--json"])
        live_v = json.loads(buf_out.getvalue())
        require_ok(
            rc_v == 0
            and not buf_err.getvalue()
            and live_v["lean_live_verified"] is True
            and live_v["cycles_compiled"] == 3
            and live_v["all_zero_axioms"] is True,
            f"verify-lean: {rc_v} {buf_err.getvalue()} {live_v}",
        )


if __name__ == "__main__":
    unittest.main()
