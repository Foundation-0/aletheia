#!/usr/bin/env python3
"""
Domain-Agnostic CEER (Calculational-Experimental Epistemic Recursion) Engine.

Pure Python 3 standard library (`int` and `fractions.Fraction` only; zero floats,
zero bare asserts, zero external dependencies).

Implements a typed, cryptographically latched recursive scientific cycle:
  overarching math theory -> preregistered held-out micro-levers & observables
  -> exact pure-Z/Q adjudication -> obstruction-lift chain -> repeat.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import hmac
import json
from typing import Any

ENGINE_SCHEMA = "aletheia.ceer_engine.v1"
MAX_JSON_DEPTH = 64
MAX_INT_DIGITS = 1000
_MAX_INT_LIMIT = 10**MAX_INT_DIGITS
_HEX_LOWER = frozenset("0123456789abcdef")
_ASCII_DIGITS = frozenset("0123456789")
_ALLOWED_PREDICATE_KINDS = frozenset(
    {
        "LINEAR_SCALING",
        "CONCAVE_SECOND_DIFF",
        "SCHUR_DARK_DROP",
        "HYSTERESIS_ZERO_AREA",
        "HYSTERESIS_NONZERO_AREA",
        "RATIONAL_ENCLOSURE",
    }
)


class CEERError(ValueError):
    """Typed fail-closed error raised by the CEER engine."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _require_clean_str(val: Any, label: str, allow_empty: bool = False) -> str:
    if type(val) is not str:
        raise CEERError("CEER_INVALID_STR", f"{label} must be strict str")
    if not allow_empty and not val:
        raise CEERError("CEER_EMPTY_STR", f"{label} must be non-empty")
    if "\x00" in val:
        raise CEERError("CEER_NUL_STR", f"{label} contains NUL byte")
    try:
        val.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CEERError("CEER_INVALID_UTF8", f"{label} contains lone surrogate") from exc
    return val


def _require_exact_int(val: Any, label: str, min_val: int | None = None) -> int:
    if type(val) is not int:
        raise CEERError("CEER_INVALID_INT", f"{label} must be strict int")
    if abs(val) >= _MAX_INT_LIMIT:
        raise CEERError("CEER_INT_OVERFLOW", f"{label} exceeds integer digit bound")
    if min_val is not None and val < min_val:
        raise CEERError("CEER_INT_TOO_SMALL", f"{label} < {min_val}")
    return val


def _require_sha256_hex(val: Any, label: str) -> str:
    s = _require_clean_str(val, label)
    if len(s) != 64 or any(ch not in _HEX_LOWER for ch in s):
        raise CEERError("CEER_INVALID_SHA256", f"{label} must be 64 lowercase hex chars")
    return s


def validate_json_tree(obj: Any, max_depth: int = MAX_JSON_DEPTH) -> None:
    """Iteratively validate strict zero-float, zero-subclass JSON-compatible data."""
    limit = _require_exact_int(max_depth, "max_depth", min_val=1)
    stack: list[tuple[Any, int]] = [(obj, 0)]
    while stack:
        cur, depth = stack.pop()
        if depth > limit:
            raise CEERError("CEER_JSON_DEPTH", f"JSON nesting exceeds {limit}")
        t = type(cur)
        if t is dict:
            for k, v in cur.items():
                _require_clean_str(k, "json_key", allow_empty=True)
                stack.append((v, depth + 1))
        elif t is list:
            for item in cur:
                stack.append((item, depth + 1))
        elif t is str:
            _require_clean_str(cur, "json_str", allow_empty=True)
        elif t is int:
            _require_exact_int(cur, "json_int")
        elif t is bool or cur is None:
            continue
        else:
            raise CEERError("CEER_FORBIDDEN_TYPE", f"forbidden JSON type: {t.__name__}")


def canonical_json_bytes(obj: Any) -> bytes:
    """Serialize validated strict JSON object into canonical ASCII LF-terminated bytes."""
    validate_json_tree(obj)
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return (text + "\n").encode("utf-8")


def sha256_canonical(obj: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


def fmt_q(val: Fraction) -> str:
    if type(val) is not Fraction:
        raise CEERError("CEER_INVALID_FRACTION", "expected exact Fraction")
    if val.denominator == 1:
        return str(val.numerator)
    return f"{val.numerator}/{val.denominator}"


def parse_q(raw: Any, label: str = "rational") -> Fraction:
    s = _require_clean_str(raw, label)
    if s != s.strip():
        raise CEERError("CEER_RATIONAL_WHITESPACE", f"{label} has surrounding whitespace")
    parts = s.split("/")
    if len(parts) not in (1, 2):
        raise CEERError("CEER_RATIONAL_FORMAT", f"{label} invalid rational syntax")
    num_s = parts[0]
    neg = num_s.startswith("-")
    mag_s = num_s[1:] if neg else num_s
    if not mag_s or any(ch not in _ASCII_DIGITS for ch in mag_s):
        raise CEERError("CEER_RATIONAL_FORMAT", f"{label} invalid numerator")
    if len(mag_s) > 1 and mag_s[0] == "0":
        raise CEERError("CEER_RATIONAL_NONCANON", f"{label} leading zero in numerator")
    if neg and mag_s == "0":
        raise CEERError("CEER_RATIONAL_NONCANON", f"{label} negative zero forbidden")
    if len(mag_s) > MAX_INT_DIGITS:
        raise CEERError("CEER_INT_OVERFLOW", f"{label}.num exceeds digit bound")
    num = _require_exact_int(int(num_s), f"{label}.num")
    if len(parts) == 1:
        return Fraction(num, 1)
    den_s = parts[1]
    if not den_s or any(ch not in _ASCII_DIGITS for ch in den_s) or den_s[0] == "0":
        raise CEERError("CEER_RATIONAL_FORMAT", f"{label} invalid denominator")
    if len(den_s) > MAX_INT_DIGITS:
        raise CEERError("CEER_INT_OVERFLOW", f"{label}.den exceeds digit bound")
    den = _require_exact_int(int(den_s), f"{label}.den", min_val=2)
    q = Fraction(num, den)
    if q.denominator != den:
        raise CEERError("CEER_RATIONAL_NONCANON", f"{label} fraction not reduced")
    return q


def _normalize_lever_list(raw: Any, label: str, allow_empty: bool = False) -> list[list[int]]:
    if type(raw) is not list:
        raise CEERError("CEER_INVALID_LEVERS", f"{label} must be list of int vectors")
    if not allow_empty and not raw:
        raise CEERError("CEER_EMPTY_LEVERS", f"{label} must be non-empty")
    out: list[list[int]] = []
    width: int | None = None
    seen: set[tuple[int, ...]] = set()
    for idx, row in enumerate(raw):
        if type(row) is not list or not row:
            raise CEERError("CEER_INVALID_LEVER_ROW", f"{label}[{idx}] must be non-empty int list")
        vec = [_require_exact_int(x, f"{label}[{idx}][{j}]") for j, x in enumerate(row)]
        if width is None:
            width = len(vec)
        elif len(vec) != width:
            raise CEERError("CEER_LEVER_WIDTH", f"{label}[{idx}] width mismatch")
        key = tuple(vec)
        if key in seen:
            raise CEERError("CEER_DUPLICATE_LEVER", f"duplicate lever in {label}: {vec}")
        seen.add(key)
        out.append(vec)
    return out


def _require_int_list(val: Any, label: str, min_len: int = 1) -> list[int]:
    if type(val) is not list or len(val) < min_len:
        raise CEERError("CEER_INVALID_INT_LIST", f"{label} must be list of >= {min_len} ints")
    return [_require_exact_int(x, f"{label}[{i}]") for i, x in enumerate(val)]


def _require_dict_field(parent: dict[str, Any], key: str, label: str) -> dict[str, Any]:
    val = parent.get(key)
    if type(val) is not dict:
        raise CEERError("CEER_INVALID_OBS", f"{label} must be strict dict")
    return val


# ---------------------------------------------------------------------------
# Pure-Z / Pure-Q Exact Physical & Geometric Adjudication Operators
# ---------------------------------------------------------------------------


def eval_linear_scaling(
    controls: list[int],
    values: list[int],
    idle_value: int,
    tol_q: Fraction,
) -> dict[str, Any]:
    """Check whether net response (y_k - y_idle) scales linearly with control u_k within tol_q."""
    if type(controls) is not list or type(values) is not list or len(controls) < 2 or len(controls) != len(values):
        raise CEERError("CEER_INVALID_SERIES", "linear scaling requires >=2 matched (u, y) points")
    if tol_q < 0:
        raise CEERError("CEER_INVALID_TOL", "tolerance must be non-negative")
    u0 = _require_exact_int(controls[0], "u0", min_val=1)
    y0 = _require_exact_int(values[0], "y0")
    y_idle = _require_exact_int(idle_value, "idle_value")
    net0 = y0 - y_idle
    if net0 <= 0:
        raise CEERError("CEER_NONPOSITIVE_BASELINE", "baseline net response must be positive")
    base_slope = Fraction(net0, u0)
    max_rel_err = Fraction(0)
    worst_idx = 0
    for idx in range(1, len(controls)):
        uk = _require_exact_int(controls[idx], f"u[{idx}]", min_val=1)
        yk = _require_exact_int(values[idx], f"y[{idx}]")
        slope_k = Fraction(yk - y_idle, uk)
        rel_err = abs(slope_k - base_slope) / base_slope
        if rel_err > max_rel_err:
            max_rel_err = rel_err
            worst_idx = idx
    passed = max_rel_err <= tol_q
    uw = controls[worst_idx]
    yw = values[worst_idx]
    return {
        "kind": "LINEAR_SCALING",
        "passed": passed,
        "u0": u0,
        "y0": y0,
        "idle_value": y_idle,
        "worst_u": uw,
        "worst_y": yw,
        "tol_q": fmt_q(tol_q),
        "max_rel_error_q": fmt_q(max_rel_err),
        "lhs_scaled_int": abs((yw - y_idle) * u0 - net0 * uw) * tol_q.denominator,
        "rhs_scaled_int": tol_q.numerator * net0 * uw,
    }


def eval_concave_second_diff(controls: list[int], values: list[int]) -> dict[str, Any]:
    """Exact cross-multiplied divided 2nd difference on 3+ strictly increasing controls."""
    if type(controls) is not list or type(values) is not list or len(controls) < 3 or len(controls) != len(values):
        raise CEERError("CEER_INVALID_SERIES", "concavity requires >=3 matched (u, y) points")
    diffs: list[int] = []
    for idx in range(len(controls) - 2):
        u0 = _require_exact_int(controls[idx], f"u[{idx}]")
        u1 = _require_exact_int(controls[idx + 1], f"u[{idx + 1}]")
        u2 = _require_exact_int(controls[idx + 2], f"u[{idx + 2}]")
        if not (u0 < u1 < u2):
            raise CEERError("CEER_NONMONOTONE_CONTROLS", "controls must strictly increase")
        y0 = _require_exact_int(values[idx], f"y[{idx}]")
        y1 = _require_exact_int(values[idx + 1], f"y[{idx + 1}]")
        y2 = _require_exact_int(values[idx + 2], f"y[{idx + 2}]")
        d2 = (y2 - y1) * (u1 - u0) - (y1 - y0) * (u2 - u1)
        diffs.append(d2)
    passed = all(d < 0 for d in diffs)
    return {
        "kind": "CONCAVE_SECOND_DIFF",
        "passed": passed,
        "controls": list(controls),
        "values": list(values),
        "second_diffs_int": diffs,
        "max_second_diff_int": max(diffs),
    }


def _invert_matrix_q(mat: list[list[Fraction]]) -> list[list[Fraction]]:
    n = len(mat)
    aug = [list(mat[i]) + [Fraction(1 if i == j else 0) for j in range(n)] for i in range(n)]
    for col in range(n):
        piv = -1
        for r in range(col, n):
            if aug[r][col] != 0:
                piv = r
                break
        if piv == -1:
            raise CEERError("CEER_SINGULAR_BLOCK", "Schur conditioning block G_BB is singular")
        if piv != col:
            aug[col], aug[piv] = aug[piv], aug[col]
        pv = aug[col][col]
        aug[col] = [x / pv for x in aug[col]]
        for r in range(n):
            if r != col:
                fac = aug[r][col]
                aug[r] = [aug[r][c] - fac * aug[col][c] for c in range(2 * n)]
    return [row[n:] for row in aug]


def compute_normalized_schur_eta_q(
    matrix_q: list[list[Fraction]],
    visible_a: list[int],
    dark_b: list[int],
) -> tuple[Fraction, Fraction, list[Fraction]]:
    """Compute exact per-channel normalized Schur residual eta_bar and dark-mode drop (1 - eta_bar)."""
    t_rows = len(matrix_q)
    if t_rows < 3:
        raise CEERError("CEER_TOO_FEW_ROWS", "Schur matrix requires at least 3 rows")
    d_cols = len(matrix_q[0])
    if not visible_a or not dark_b:
        raise CEERError("CEER_EMPTY_PARTITION", "visible_a and dark_b must be non-empty")
    if set(visible_a) & set(dark_b):
        raise CEERError("CEER_OVERLAP_PARTITION", "visible_a and dark_b must be disjoint")
    if len(set(visible_a)) != len(visible_a) or len(set(dark_b)) != len(dark_b):
        raise CEERError("CEER_DUP_PARTITION", "duplicate channel index in partition")
    for idx in visible_a + dark_b:
        if idx < 0 or idx >= d_cols:
            raise CEERError("CEER_BAD_COL_IDX", f"column index {idx} out of range 0..{d_cols - 1}")

    means = [sum(matrix_q[r][c] for r in range(t_rows)) / t_rows for c in range(d_cols)]
    centered = [[matrix_q[r][c] - means[c] for c in range(d_cols)] for r in range(t_rows)]

    def gram(rows_idx: list[int], cols_idx: list[int]) -> list[list[Fraction]]:
        return [
            [sum(centered[r][i] * centered[r][j] for r in range(t_rows)) for j in cols_idx]
            for i in rows_idx
        ]

    g_aa = gram(visible_a, visible_a)
    g_ab = gram(visible_a, dark_b)
    g_bb = gram(dark_b, dark_b)
    g_bb_inv = _invert_matrix_q(g_bb)

    na = len(visible_a)
    nb = len(dark_b)
    # Compute diagonal of S = G_AA - G_AB G_BB^{-1} G_BA exactly
    ratios: list[Fraction] = []
    for i in range(na):
        var_i = g_aa[i][i]
        if var_i <= 0:
            raise CEERError("CEER_ZERO_VARIANCE", f"visible channel {visible_a[i]} has zero variance")
        proj_i = Fraction(0)
        for p in range(nb):
            g_ab_ip = g_ab[i][p]
            if g_ab_ip == 0:
                continue
            inner = sum(g_bb_inv[p][q] * g_ab[i][q] for q in range(nb))
            proj_i += g_ab_ip * inner
        s_ii = var_i - proj_i
        ratios.append(s_ii / var_i)

    eta_bar = sum(ratios) / na
    dark_drop = Fraction(1) - eta_bar
    return eta_bar, dark_drop, ratios


def eval_schur_dark_drop(
    matrix_int: list[list[int]],
    visible_a: list[int],
    dark_b: list[int],
    threshold_q: Fraction,
    expect_at_least: bool,
) -> dict[str, Any]:
    """Evaluate exact Schur dark-mode variance reduction and verify Stage-A gauge invariance."""
    if type(matrix_int) is not list or len(matrix_int) < 3 or type(matrix_int[0]) is not list:
        raise CEERError("CEER_INVALID_MATRIX", "matrix_int must have >= 3 list rows")
    width = len(matrix_int[0])
    if width < 2:
        raise CEERError("CEER_INVALID_MATRIX", "matrix_int must have >= 2 cols")
    mat_q: list[list[Fraction]] = []
    for r_idx, row in enumerate(matrix_int):
        if type(row) is not list or len(row) != width:
            raise CEERError("CEER_RAGGED_MATRIX", f"matrix row {r_idx} width mismatch")
        mat_q.append([Fraction(_require_exact_int(x, f"X[{r_idx}][{c}]")) for c, x in enumerate(row)])

    eta_bar, dark_drop, ratios = compute_normalized_schur_eta_q(mat_q, visible_a, dark_b)

    # Exact Stage-A gauge invariance check: reverse channel order + independent positive rational affine rescaling
    perm_a = list(reversed(visible_a))
    perm_b = list(reversed(dark_b))
    scales = [Fraction(3 + 2 * c, 5 + c) for c in range(width)]
    shifts = [Fraction(7 * (c + 1), 3) for c in range(width)]
    gauged = [[mat_q[r][c] * scales[c] + shifts[c] for c in range(width)] for r in range(len(mat_q))]
    eta_gauge, drop_gauge, _ = compute_normalized_schur_eta_q(gauged, perm_a, perm_b)
    gauge_dev = abs(eta_bar - eta_gauge) + abs(dark_drop - drop_gauge)
    passed = (dark_drop >= threshold_q) if expect_at_least else (dark_drop <= threshold_q)

    return {
        "kind": "SCHUR_DARK_DROP",
        "passed": passed,
        "expect_at_least": expect_at_least,
        "threshold_q": fmt_q(threshold_q),
        "eta_bar_q": fmt_q(eta_bar),
        "dark_drop_q": fmt_q(dark_drop),
        "channel_etas_q": [fmt_q(x) for x in ratios],
        "stage_a_gauge_deviation_q": fmt_q(gauge_dev),
    }


def eval_hysteresis_loop(
    xs: list[int],
    ys: list[int],
    expect_nonzero: bool,
    min_abs_twice_area: int = 1,
) -> dict[str, Any]:
    """Exact discrete signed twice-area 2*A = sum_t (y_{t+1} + y_t) * (x_{t+1} - x_t)."""
    if type(xs) is not list or type(ys) is not list or len(xs) < 4 or len(xs) != len(ys):
        raise CEERError("CEER_INVALID_LOOP", "hysteresis loop requires >= 4 matched (x, y) points")
    min_a = _require_exact_int(min_abs_twice_area, "min_abs_twice_area", min_val=0)
    m = len(xs)
    x_clean = [_require_exact_int(v, f"x[{i}]") for i, v in enumerate(xs)]
    y_clean = [_require_exact_int(v, f"y[{i}]") for i, v in enumerate(ys)]
    twice_area = 0
    for i in range(m):
        j = (i + 1) % m
        twice_area += (y_clean[j] + y_clean[i]) * (x_clean[j] - x_clean[i])
    abs_area = abs(twice_area)
    if expect_nonzero:
        passed = abs_area >= min_a
        kind = "HYSTERESIS_NONZERO_AREA"
    else:
        passed = abs_area == 0
        kind = "HYSTERESIS_ZERO_AREA"
    return {
        "kind": kind,
        "passed": passed,
        "xs": x_clean,
        "ys": y_clean,
        "twice_area_int": twice_area,
        "abs_twice_area_int": abs_area,
        "min_abs_twice_area": min_a,
    }


def eval_rational_enclosure(
    observed_pairs: list[list[int]],
    lower_bounds_q: list[Fraction],
    upper_bounds_q: list[Fraction],
) -> dict[str, Any]:
    """Check exact integer cross-multiplied enclosure L_k <= n_k / d_k <= U_k across held-out points."""
    if type(observed_pairs) is not list or not observed_pairs or len(observed_pairs) != len(lower_bounds_q) or len(observed_pairs) != len(upper_bounds_q):
        raise CEERError("CEER_ENCLOSURE_LEN", "enclosure bounds and observations length mismatch")
    n = len(observed_pairs)
    point_results: list[dict[str, Any]] = []
    all_ok = True
    for idx in range(n):
        pair = observed_pairs[idx]
        if type(pair) is not list or len(pair) != 2:
            raise CEERError("CEER_ENCLOSURE_PAIR", f"observed_pairs[{idx}] must be [num, den]")
        num = _require_exact_int(pair[0], f"obs[{idx}].num")
        den = _require_exact_int(pair[1], f"obs[{idx}].den", min_val=1)
        lo = lower_bounds_q[idx]
        hi = upper_bounds_q[idx]
        if lo > hi:
            raise CEERError("CEER_ENCLOSURE_ORDER", f"lower bound > upper bound at index {idx}")
        val = Fraction(num, den)
        ok = lo <= val <= hi
        if not ok:
            all_ok = False
        point_results.append(
            {
                "num": num,
                "den": den,
                "value_q": fmt_q(val),
                "lo_q": fmt_q(lo),
                "hi_q": fmt_q(hi),
                "ok": ok,
            }
        )
    return {
        "kind": "RATIONAL_ENCLOSURE",
        "passed": all_ok,
        "points": point_results,
    }


# ---------------------------------------------------------------------------
# Typed CEER Cycle State Machine & Pluggable Hardware Adapter
# ---------------------------------------------------------------------------


def commit_preregistration(prereg: dict[str, Any]) -> str:
    """Validate a TheorySpec preregistration and return its immutable SHA-256 latch."""
    if type(prereg) is not dict:
        raise CEERError("CEER_INVALID_PREREG", "prereg must be strict dict")
    validate_json_tree(prereg)
    _require_clean_str(prereg.get("theory_id"), "theory_id")
    cyc = _require_exact_int(prereg.get("cycle_index"), "cycle_index", min_val=0)
    prior_sha = prereg.get("prior_cycle_sha256")
    prior_obs = prereg.get("prior_obstruction_code")
    if cyc == 0:
        if prior_sha is not None or prior_obs is not None:
            raise CEERError("CEER_BROKEN_CHAIN", "cycle 0 must not declare prior chain links")
    else:
        _require_sha256_hex(prior_sha, "prior_cycle_sha256")
        _require_clean_str(prior_obs, "prior_obstruction_code")
    train = _normalize_lever_list(prereg.get("train_levers"), "train_levers", allow_empty=(cyc == 0))
    ev = _normalize_lever_list(prereg.get("eval_levers"), "eval_levers", allow_empty=False)
    if set(map(tuple, train)) & set(map(tuple, ev)):
        raise CEERError("CEER_INSAMPLE_LEAK", "eval_levers overlaps prior train_levers")
    schema = prereg.get("observable_schema")
    if type(schema) is not list or not schema:
        raise CEERError("CEER_INVALID_SCHEMA", "observable_schema must be non-empty list")
    for i, ch_name in enumerate(schema):
        _require_clean_str(ch_name, f"observable_schema[{i}]")
    preds = prereg.get("predictions")
    if type(preds) is not list or not preds:
        raise CEERError("CEER_EMPTY_PREDICTIONS", "predictions must be non-empty list")
    seen_ids: set[str] = set()
    for i, pred in enumerate(preds):
        if type(pred) is not dict:
            raise CEERError("CEER_INVALID_PRED", f"predictions[{i}] must be dict")
        pid = _require_clean_str(pred.get("id"), f"predictions[{i}].id")
        if pid in seen_ids:
            raise CEERError("CEER_DUP_PRED_ID", f"duplicate prediction id: {pid}")
        seen_ids.add(pid)
        kind = _require_clean_str(pred.get("kind"), f"predictions[{i}].kind")
        if kind not in _ALLOWED_PREDICATE_KINDS:
            raise CEERError("CEER_UNKNOWN_PRED_KIND", f"unknown predicate kind: {kind}")
        if kind == "LINEAR_SCALING":
            parse_q(pred.get("tol_q"), f"{pid}.tol_q")
        elif kind == "SCHUR_DARK_DROP":
            if type(pred.get("expect_at_least")) is not bool:
                raise CEERError("CEER_INVALID_BOOL", f"{pid}.expect_at_least must be bool")
            _require_int_list(pred.get("visible_a"), f"{pid}.visible_a")
            _require_int_list(pred.get("dark_b"), f"{pid}.dark_b")
            parse_q(pred.get("threshold_q"), f"{pid}.threshold_q")
        elif kind == "HYSTERESIS_NONZERO_AREA":
            _require_exact_int(pred.get("min_abs_twice_area"), f"{pid}.min_abs_twice_area", min_val=0)
        elif kind == "RATIONAL_ENCLOSURE":
            lo_b = pred.get("lower_bounds_q")
            hi_b = pred.get("upper_bounds_q")
            if type(lo_b) is not list or type(hi_b) is not list or not lo_b or len(lo_b) != len(hi_b):
                raise CEERError("CEER_INVALID_PRED", f"{pid} requires matched non-empty lower_bounds_q/upper_bounds_q")
            for x in lo_b:
                parse_q(x, f"{pid}.lo")
            for x in hi_b:
                parse_q(x, f"{pid}.hi")
    return sha256_canonical(prereg)


def adapt_external_sensor_cycle(
    eval_levers: list[list[int]],
    observable_schema: list[str],
    sensor_rows: list[dict[str, int]],
    core_series: dict[str, Any],
    hysteresis_loop: dict[str, Any],
    enclosure_pairs: list[list[int]],
) -> dict[str, Any]:
    """Pluggable adapter mapping external integer sensor tables (e.g. RAPL/coretemp) to CEER observation."""
    norm_eval = _normalize_lever_list(eval_levers, "eval_levers", allow_empty=False)
    if type(observable_schema) is not list or len(observable_schema) < 2:
        raise CEERError("CEER_INVALID_SCHEMA", "observable_schema requires >= 2 channels")
    clean_schema = [_require_clean_str(c, f"schema[{i}]") for i, c in enumerate(observable_schema)]
    if type(sensor_rows) is not list or len(sensor_rows) < 3:
        raise CEERError("CEER_INVALID_SENSOR_ROWS", "sensor_rows requires >= 3 integer records")
    matrix: list[list[int]] = []
    for r_idx, rec in enumerate(sensor_rows):
        if type(rec) is not dict:
            raise CEERError("CEER_INVALID_SENSOR_ROW", f"sensor_rows[{r_idx}] must be dict")
        row_vals: list[int] = []
        for ch in clean_schema:
            if ch not in rec:
                raise CEERError("CEER_MISSING_CHANNEL", f"sensor_rows[{r_idx}] missing channel {ch}")
            row_vals.append(_require_exact_int(rec[ch], f"sensor_rows[{r_idx}].{ch}"))
        matrix.append(row_vals)
    obs = {
        "eval_levers": norm_eval,
        "observable_schema": clean_schema,
        "sensor_matrix": matrix,
        "core_series": core_series,
        "hysteresis_loop": hysteresis_loop,
        "enclosure_pairs": enclosure_pairs,
    }
    validate_json_tree(obs)
    return obs


def evaluate_cycle(
    prereg: dict[str, Any],
    prereg_sha256: str,
    observation: dict[str, Any],
    prior_cycle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute one cryptographically latched CEER adjudication cycle."""
    expected_sha = commit_preregistration(prereg)
    claimed_sha = _require_sha256_hex(prereg_sha256, "prereg_sha256")
    if not hmac.compare_digest(expected_sha, claimed_sha):
        raise CEERError("CEER_PREREG_MISMATCH", "preregistration digest mismatch")
    validate_json_tree(observation)
    if type(observation) is not dict:
        raise CEERError("CEER_INVALID_OBS", "observation must be strict dict")

    cyc = prereg["cycle_index"]
    if cyc == 0:
        if prior_cycle is not None:
            raise CEERError("CEER_BROKEN_CHAIN", "cycle 0 must have prior_cycle=None")
    else:
        if type(prior_cycle) is not dict:
            raise CEERError("CEER_BROKEN_CHAIN", "cycle >= 1 requires prior_cycle dict")
        prior_sha = _require_sha256_hex(prior_cycle.get("cycle_sha256"), "prior_cycle.cycle_sha256")
        if not hmac.compare_digest(prereg["prior_cycle_sha256"], prior_sha):
            raise CEERError("CEER_BROKEN_CHAIN", "prior_cycle_sha256 does not match prior cycle")
        if prior_cycle.get("verdict") != "FALSIFIED":
            raise CEERError("CEER_BROKEN_CHAIN", "cannot lift from non-falsified prior cycle")
        prior_falsified = prior_cycle.get("falsified_predicates")
        if type(prior_falsified) is not list or prereg["prior_obstruction_code"] not in prior_falsified:
            raise CEERError("CEER_BROKEN_CHAIN", "prior_obstruction_code not in prior falsified predicates")
        prior_seen_list = _normalize_lever_list(
            prior_cycle.get("seen_levers_cumulative"),
            "prior_cycle.seen_levers_cumulative",
            allow_empty=False,
        )
        prior_seen = set(map(tuple, prior_seen_list))
        declared_train = set(map(tuple, prereg["train_levers"]))
        if not prior_seen.issubset(declared_train):
            raise CEERError("CEER_INSAMPLE_LEAK", "train_levers omits previously observed levers")

    if observation.get("eval_levers") != prereg["eval_levers"]:
        raise CEERError("CEER_OBSERVATION_MISMATCH", "observation eval_levers != prereg eval_levers")
    if observation.get("observable_schema") != prereg["observable_schema"]:
        raise CEERError("CEER_OBSERVATION_MISMATCH", "observation schema != prereg schema")

    pred_outcomes: list[dict[str, Any]] = []
    falsified_ids: list[str] = []
    corroborated_ids: list[str] = []

    for pred in prereg["predictions"]:
        pid = pred["id"]
        kind = pred["kind"]
        if kind == "LINEAR_SCALING":
            cs = _require_dict_field(observation, "core_series", "observation.core_series")
            ev_res = eval_linear_scaling(
                cs.get("controls"),
                cs.get("values"),
                cs.get("idle_value"),
                parse_q(pred["tol_q"], f"{pid}.tol_q"),
            )
        elif kind == "CONCAVE_SECOND_DIFF":
            cs = _require_dict_field(observation, "core_series", "observation.core_series")
            ev_res = eval_concave_second_diff(cs.get("controls"), cs.get("values"))
        elif kind == "SCHUR_DARK_DROP":
            ev_res = eval_schur_dark_drop(
                observation.get("sensor_matrix"),
                pred["visible_a"],
                pred["dark_b"],
                parse_q(pred["threshold_q"], f"{pid}.threshold_q"),
                expect_at_least=pred["expect_at_least"],
            )
        elif kind == "HYSTERESIS_ZERO_AREA":
            hl = _require_dict_field(observation, "hysteresis_loop", "observation.hysteresis_loop")
            ev_res = eval_hysteresis_loop(hl.get("xs"), hl.get("ys"), expect_nonzero=False, min_abs_twice_area=0)
        elif kind == "HYSTERESIS_NONZERO_AREA":
            hl = _require_dict_field(observation, "hysteresis_loop", "observation.hysteresis_loop")
            ev_res = eval_hysteresis_loop(
                hl.get("xs"),
                hl.get("ys"),
                expect_nonzero=True,
                min_abs_twice_area=pred["min_abs_twice_area"],
            )
        else:
            ev_res = eval_rational_enclosure(
                observation.get("enclosure_pairs"),
                [parse_q(x, f"{pid}.lo") for x in pred["lower_bounds_q"]],
                [parse_q(x, f"{pid}.hi") for x in pred["upper_bounds_q"]],
            )
        rec = {"id": pid, **ev_res}
        pred_outcomes.append(rec)
        if ev_res["passed"]:
            corroborated_ids.append(pid)
        else:
            falsified_ids.append(pid)

    verdict = "CORROBORATED" if not falsified_ids else "FALSIFIED"
    seen_cum: list[list[int]] = []
    if prior_cycle is not None:
        seen_cum.extend(prior_seen_list)
    seen_cum.extend(prereg["eval_levers"])

    body = {
        "cycle_index": cyc,
        "theory_id": prereg["theory_id"],
        "prereg_sha256": expected_sha,
        "observation_sha256": sha256_canonical(observation),
        "prior_cycle_sha256": prereg["prior_cycle_sha256"],
        "prior_obstruction_code": prereg["prior_obstruction_code"],
        "verdict": verdict,
        "corroborated_predicates": corroborated_ids,
        "falsified_predicates": falsified_ids,
        "predicate_results": pred_outcomes,
        "seen_levers_cumulative": seen_cum,
    }
    cycle_sha = sha256_canonical(body)
    return {
        **body,
        "cycle_sha256": cycle_sha,
        "prereg": prereg,
        "observation": observation,
    }


def build_self_demo_cycles() -> dict[str, Any]:
    """Run the deterministic 3-cycle pure-Z/Q physical-dissipation CEER benchmark end-to-end."""
    schema = ["pkg_mw", "core_mw", "uncore_mw", "psys_mw", "temp_mc", "fan_rpm"]

    # Cycle 0: T0 (idealized linear core scaling, flat dark-mode coupling, zero fan hysteresis)
    prereg0: dict[str, Any] = {
        "theory_id": "T0_LINEAR_SINGLE_VALUED",
        "cycle_index": 0,
        "prior_cycle_sha256": None,
        "prior_obstruction_code": None,
        "train_levers": [],
        "eval_levers": [[1, 16], [2, 256], [4, 4096]],
        "observable_schema": schema,
        "predictions": [
            {"id": "H0_LINEAR_CORE", "kind": "LINEAR_SCALING", "tol_q": "1/20"},
            {
                "id": "H0_FLAT_DARK_MODE",
                "kind": "SCHUR_DARK_DROP",
                "visible_a": [0, 1],
                "dark_b": [2, 3],
                "threshold_q": "1/10",
                "expect_at_least": False,
            },
            {"id": "H0_ZERO_HYSTERESIS", "kind": "HYSTERESIS_ZERO_AREA"},
        ],
    }
    obs0 = adapt_external_sensor_cycle(
        eval_levers=[[1, 16], [2, 256], [4, 4096]],
        observable_schema=schema,
        sensor_rows=[
            {"pkg_mw": 14000, "core_mw": 9000, "uncore_mw": 1800, "psys_mw": 21200, "temp_mc": 54000, "fan_rpm": 2100},
            {"pkg_mw": 22500, "core_mw": 16600, "uncore_mw": 2600, "psys_mw": 31800, "temp_mc": 64000, "fan_rpm": 2600},
            {"pkg_mw": 31800, "core_mw": 23800, "uncore_mw": 4700, "psys_mw": 45600, "temp_mc": 76000, "fan_rpm": 3500},
            {"pkg_mw": 37400, "core_mw": 27200, "uncore_mw": 6800, "psys_mw": 55400, "temp_mc": 83000, "fan_rpm": 4100},
            {"pkg_mw": 26100, "core_mw": 18900, "uncore_mw": 3900, "psys_mw": 37900, "temp_mc": 71000, "fan_rpm": 3300},
            {"pkg_mw": 17900, "core_mw": 12200, "uncore_mw": 2400, "psys_mw": 26400, "temp_mc": 59000, "fan_rpm": 2500},
        ],
        core_series={"controls": [1, 2, 4], "values": [14000, 22500, 31800], "idle_value": 5000},
        hysteresis_loop={
            "xs": [54000, 64000, 76000, 83000, 76000, 64000],
            "ys": [2100, 2600, 3400, 4100, 3850, 3150],
        },
        enclosure_pairs=[[9000, 1], [17500, 2], [26800, 4]],
    )
    c0 = evaluate_cycle(prereg0, commit_preregistration(prereg0), obs0, prior_cycle=None)

    # Cycle 1: T1 lifts linear & flat-dark obstructions onto unseen held-out levers, tests single-branch cooling
    prereg1: dict[str, Any] = {
        "theory_id": "T1_CONCAVE_SCHUR_SINGLE_BRANCH",
        "cycle_index": 1,
        "prior_cycle_sha256": c0["cycle_sha256"],
        "prior_obstruction_code": "H0_LINEAR_CORE",
        "train_levers": [[1, 16], [2, 256], [4, 4096]],
        "eval_levers": [[3, 8192], [6, 32768], [8, 65536]],
        "observable_schema": schema,
        "predictions": [
            {"id": "H1_CONCAVE_POWER", "kind": "CONCAVE_SECOND_DIFF"},
            {
                "id": "H1_SCHUR_DARK_COUPLING",
                "kind": "SCHUR_DARK_DROP",
                "visible_a": [0, 1],
                "dark_b": [2, 3],
                "threshold_q": "1/2",
                "expect_at_least": True,
            },
            {"id": "H1_ZERO_HYSTERESIS", "kind": "HYSTERESIS_ZERO_AREA"},
        ],
    }
    obs1 = adapt_external_sensor_cycle(
        eval_levers=[[3, 8192], [6, 32768], [8, 65536]],
        observable_schema=schema,
        sensor_rows=[
            {"pkg_mw": 27600, "core_mw": 20400, "uncore_mw": 4100, "psys_mw": 40100, "temp_mc": 69000, "fan_rpm": 3000},
            {"pkg_mw": 38900, "core_mw": 28500, "uncore_mw": 7200, "psys_mw": 58200, "temp_mc": 81000, "fan_rpm": 3950},
            {"pkg_mw": 43800, "core_mw": 31200, "uncore_mw": 9100, "psys_mw": 67400, "temp_mc": 88000, "fan_rpm": 4600},
            {"pkg_mw": 41200, "core_mw": 29800, "uncore_mw": 8300, "psys_mw": 62900, "temp_mc": 84000, "fan_rpm": 4450},
            {"pkg_mw": 32400, "core_mw": 23600, "uncore_mw": 5600, "psys_mw": 47800, "temp_mc": 74000, "fan_rpm": 3650},
            {"pkg_mw": 24100, "core_mw": 17300, "uncore_mw": 3400, "psys_mw": 34900, "temp_mc": 65000, "fan_rpm": 2950},
        ],
        core_series={"controls": [3, 6, 8], "values": [27600, 38900, 43800], "idle_value": 5000},
        hysteresis_loop={
            "xs": [65000, 74000, 81000, 88000, 81000, 74000],
            "ys": [2800, 3300, 3950, 4600, 4350, 3750],
        },
        enclosure_pairs=[[22600, 3], [33900, 6], [38800, 8]],
    )
    c1 = evaluate_cycle(prereg1, commit_preregistration(prereg1), obs1, prior_cycle=c0)

    # Cycle 2: T2 lifts the remaining H1_ZERO_HYSTERESIS obstruction onto unseen held-out levers -> full closure
    prereg2: dict[str, Any] = {
        "theory_id": "T2_HYSTERETIC_SCHUR_CLOSURE",
        "cycle_index": 2,
        "prior_cycle_sha256": c1["cycle_sha256"],
        "prior_obstruction_code": "H1_ZERO_HYSTERESIS",
        "train_levers": [[1, 16], [2, 256], [4, 4096], [3, 8192], [6, 32768], [8, 65536]],
        "eval_levers": [[5, 16384], [7, 49152], [9, 98304]],
        "observable_schema": schema,
        "predictions": [
            {"id": "H2_CONCAVE_POWER", "kind": "CONCAVE_SECOND_DIFF"},
            {
                "id": "H2_SCHUR_DARK_CLOSURE",
                "kind": "SCHUR_DARK_DROP",
                "visible_a": [0, 1],
                "dark_b": [2, 3],
                "threshold_q": "1/2",
                "expect_at_least": True,
            },
            {
                "id": "H2_HYSTERETIC_LOOP_AREA",
                "kind": "HYSTERESIS_NONZERO_AREA",
                "min_abs_twice_area": 5000000,
            },
            {
                "id": "H2_RATIONAL_ENCLOSURE",
                "kind": "RATIONAL_ENCLOSURE",
                "lower_bounds_q": ["6000", "5000", "4000"],
                "upper_bounds_q": ["7000", "6000", "5000"],
            },
        ],
    }
    obs2 = adapt_external_sensor_cycle(
        eval_levers=[[5, 16384], [7, 49152], [9, 98304]],
        observable_schema=schema,
        sensor_rows=[
            {"pkg_mw": 35800, "core_mw": 26100, "uncore_mw": 6100, "psys_mw": 52700, "temp_mc": 78000, "fan_rpm": 3700},
            {"pkg_mw": 41700, "core_mw": 30000, "uncore_mw": 8200, "psys_mw": 63500, "temp_mc": 85000, "fan_rpm": 4300},
            {"pkg_mw": 45200, "core_mw": 32100, "uncore_mw": 9800, "psys_mw": 70600, "temp_mc": 90000, "fan_rpm": 4850},
            {"pkg_mw": 42900, "core_mw": 30700, "uncore_mw": 8900, "psys_mw": 66100, "temp_mc": 86000, "fan_rpm": 4650},
            {"pkg_mw": 34200, "core_mw": 24900, "uncore_mw": 5800, "psys_mw": 50200, "temp_mc": 76000, "fan_rpm": 3850},
            {"pkg_mw": 28400, "core_mw": 20700, "uncore_mw": 4300, "psys_mw": 41400, "temp_mc": 70000, "fan_rpm": 3250},
        ],
        core_series={"controls": [5, 7, 9], "values": [35800, 41700, 45200], "idle_value": 5000},
        hysteresis_loop={
            "xs": [70000, 78000, 85000, 90000, 85000, 78000],
            "ys": [3100, 3700, 4300, 4850, 4650, 4100],
        },
        enclosure_pairs=[[30800, 5], [36700, 7], [40200, 9]],
    )
    c2 = evaluate_cycle(prereg2, commit_preregistration(prereg2), obs2, prior_cycle=c1)

    return {
        "schema": ENGINE_SCHEMA,
        "cycles": [c0, c1, c2],
        "epistemic_lifts_verified": 2,
        "final_verdict": c2["verdict"],
    }
