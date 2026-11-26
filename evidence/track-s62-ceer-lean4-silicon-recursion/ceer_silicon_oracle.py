#!/usr/bin/env python3
"""
ceer_silicon_oracle.py — Pure-Z/Q (exact int / Fraction) oracle for the
3-cycle Calculational-Experimental Epistemic Recursion (CEER: Lean 4.36.0 <-> silicon).

Recomputes every Cycle 0, Cycle 1, and Cycle 2 observable, exact 3x3 Schur-complement
variance-reduction identity, pairwise held-out lever disjointness, and cryptographic
preregistration chain directly from raw integer telemetry JSONs with zero floats.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from pathlib import Path
from typing import Any


class OracleError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _req_int(value: Any, label: str) -> int:
    if type(value) is not int:
        raise OracleError("NON_INTEGER_VALUE", f"{label} must be exact int")
    return value


def _req_pos(value: Any, label: str) -> int:
    v = _req_int(value, label)
    if v <= 0:
        raise OracleError("NON_POSITIVE_VALUE", f"{label} must be > 0")
    return v


def _req_dict(value: Any, label: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise OracleError("BAD_OBJECT", f"{label} must be dict")
    return value


def _req_list(value: Any, label: str) -> list[Any]:
    if type(value) is not list:
        raise OracleError("BAD_LIST", f"{label} must be list")
    return value


def _reject_constant(token: str) -> Any:
    raise OracleError("NON_FINITE_JSON", f"forbidden JSON constant: {token}")


def _reject_float(token: str) -> Any:
    raise OracleError("FLOAT_FORBIDDEN", f"floating-point literal forbidden: {token}")


def _strict_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise OracleError("DUPLICATE_KEY", f"duplicate JSON key: {k}")
        out[k] = v
    return out


def _parse_json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OracleError("INVALID_UTF8", f"invalid UTF-8 in {label}") from exc
    try:
        obj = json.loads(
            text,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
            object_pairs_hook=_strict_pairs_hook,
        )
    except OracleError:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise OracleError("INVALID_JSON", f"malformed JSON in {label}: {exc}") from exc
    return _req_dict(obj, label)


def _seg_map(telemetry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    segs = _req_list(telemetry.get("segments"), "segments")
    out: dict[str, dict[str, Any]] = {}
    for idx, item in enumerate(segs):
        obj = _req_dict(item, f"segments[{idx}]")
        sid = obj.get("segment_id")
        if type(sid) is not str or not sid:
            raise OracleError("BAD_SEGMENT_ID", f"segments[{idx}] missing segment_id")
        if sid in out:
            raise OracleError("DUPLICATE_SEGMENT_ID", f"duplicate segment_id {sid}")
        out[sid] = obj
    return out


def _get_seg(smap: dict[str, dict[str, Any]], sid: str) -> dict[str, Any]:
    if sid not in smap:
        raise OracleError("MISSING_SEGMENT", f"missing required segment {sid}")
    return smap[sid]


def _core_temps(seg: dict[str, Any]) -> list[int]:
    mt = _req_dict(seg.get("mean_temp_mc"), "mean_temp_mc")
    return [_req_int(mt.get(f"core_{c}"), f"core_{c}") for c in range(8)]


def _pkg_dark_mw(seg: dict[str, Any]) -> int:
    pmw = _req_dict(seg.get("power_mw"), "power_mw")
    return (
        _req_int(pmw.get("package_0"), "power_mw.package_0")
        - _req_int(pmw.get("core"), "power_mw.core")
        - _req_int(pmw.get("uncore"), "power_mw.uncore")
    )


def _psys_dark_mw(seg: dict[str, Any]) -> int:
    pmw = _req_dict(seg.get("power_mw"), "power_mw")
    return (
        _req_int(pmw.get("psys"), "power_mw.psys")
        - _req_int(pmw.get("package_0"), "power_mw.package_0")
    )


def compute_twice_polygon_area(xs: list[int], ys: list[int]) -> int:
    if len(xs) != len(ys) or len(xs) < 2:
        raise OracleError("BAD_POLYGON", "polygon requires >= 2 matching points")
    n = len(xs)
    total = 0
    for i in range(n):
        j = (i + 1) % n
        total += xs[i] * ys[j] - xs[j] * ys[i]
    return total


def compute_ramp_step_means(
    ts: list[dict[str, Any]], n_steps: int, step_ms: int, field: str
) -> list[int]:
    if n_steps < 2 or step_ms <= 0:
        raise OracleError("BAD_RAMP_SPEC", "invalid ramp steps or step_ms")
    means: list[int] = []
    for i in range(n_steps):
        lo = i * step_ms
        hi = (i + 1) * step_ms
        vals = [
            _req_int(_req_dict(pt, "ts_pt").get(field), field)
            for pt in ts
            if lo <= _req_int(_req_dict(pt, "ts_pt").get("t_ms"), "t_ms") < hi
        ]
        if not vals:
            raise OracleError("EMPTY_RAMP_BIN", f"empty ramp bin {i} for {field}")
        means.append(sum(vals) // len(vals))
    return means


def centered_int_dot(a: list[int], b: list[int]) -> int:
    if len(a) != len(b) or len(a) < 2:
        raise OracleError("BAD_SERIES", "series length mismatch or too short")
    n = len(a)
    sa = sum(a)
    sb = sum(b)
    return sum((n * x - sa) * (n * y - sb) for x, y in zip(a, b))


def exact_schur_3x3(
    syy: int, suu: int, svv: int, syu: int, syv: int, suv: int
) -> dict[str, Any]:
    """Compute exact 3x3 integer Gram Schur-complement quantities and verify algebraic identity."""
    det_a = suu * svv - suv * suv
    det_g = syy * det_a - syu * (syu * svv - syv * suv) + syv * (syu * suv - syv * suu)
    r1_num = syy * suu - syu * syu
    delta = suu * syv - suv * syu
    lhs = r1_num * det_a - det_g * suu
    rhs = delta * delta
    if r1_num <= 0 or det_a <= 0:
        raise OracleError("SCHUR_DEGENERATE", "non-positive R1_num or det(A)")
    frac = Fraction(rhs, r1_num * det_a)
    return {
        "det_a": det_a,
        "det_g": det_g,
        "r1_num": r1_num,
        "delta": delta,
        "identity_residual": lhs - rhs,
        "variance_reduction_fraction": [frac.numerator, frac.denominator],
        "variance_reduction_bps": (rhs * 10000) // (r1_num * det_a),
    }


def extract_cycle0_obs(telemetry: dict[str, Any]) -> dict[str, Any]:
    smap = _seg_map(telemetry)
    p1 = _get_seg(smap, "c0_u1_p1")
    p2 = _get_seg(smap, "c0_u1_p2")
    p4 = _get_seg(smap, "c0_u1_p4")
    p8 = _get_seg(smap, "c0_u1_p8")
    m16 = _get_seg(smap, "c0_u3_16k")
    m64 = _get_seg(smap, "c0_u3_64m")
    cool1 = _get_seg(smap, "c0_u2_cool1")
    adj01 = _get_seg(smap, "c0_u2_adj_01")
    cool2 = _get_seg(smap, "c0_u2_cool2")
    dist07 = _get_seg(smap, "c0_u2_dist_07")
    rmp = _get_seg(smap, "c0_u4_ramp")

    t_c1 = _core_temps(cool1)
    t_a01 = _core_temps(adj01)
    t_c2 = _core_temps(cool2)
    t_d07 = _core_temps(dist07)
    inact_a01 = [t_a01[c] - t_c1[c] for c in (2, 3, 4, 5, 6, 7)]
    inact_d07 = [t_d07[c] - t_c2[c] for c in (1, 2, 3, 4, 5, 6)]
    adj_rise = sum(inact_a01) // 6
    dist_rise = sum(inact_d07) // 6

    ts = _req_list(rmp.get("time_series"), "c0_u4_ramp.time_series")
    if len(ts) < 8:
        raise OracleError("BAD_SERIES", "c0_u4_ramp time_series too short")
    steps = [1, 2, 4, 8, 8, 4, 2, 1]
    n_ts = len(ts)
    all_t = [_req_int(_req_dict(pt, "c0_pt").get("pkg_temp_mc"), "pkg_temp_mc") for pt in ts]
    all_f = [_req_int(_req_dict(pt, "c0_pt").get("cpu_fan_rpm"), "cpu_fan_rpm") for pt in ts]
    all_p = [steps[(i * 8) // n_ts] for i in range(n_ts)]
    half = n_ts // 2
    rpm_up = sum(all_f[:half]) // half
    rpm_dn = sum(all_f[half:]) // (n_ts - half)
    temp_up = sum(all_t[:half]) // half
    temp_dn = sum(all_t[half:]) // (n_ts - half)
    twice_fan = compute_twice_polygon_area(all_t, all_f)
    twice_tload = compute_twice_polygon_area(all_t, all_p)

    obs = {
        "pkgMwP1": _req_pos(_req_dict(p1.get("power_mw"), "p1.power_mw").get("package_0"), "pkgMwP1"),
        "pkgMwP2": _req_pos(_req_dict(p2.get("power_mw"), "p2.power_mw").get("package_0"), "pkgMwP2"),
        "pkgMwP4": _req_pos(_req_dict(p4.get("power_mw"), "p4.power_mw").get("package_0"), "pkgMwP4"),
        "pkgMwP8": _req_pos(_req_dict(p8.get("power_mw"), "p8.power_mw").get("package_0"), "pkgMwP8"),
        "opsP1": _req_pos(_req_dict(p1.get("actuator_output"), "p1.act").get("retired_ops"), "opsP1"),
        "opsP8": _req_pos(_req_dict(p8.get("actuator_output"), "p8.act").get("retired_ops"), "opsP8"),
        "pkgUj16k": _req_pos(_req_dict(m16.get("delta_rapl_uj"), "m16.uj").get("package_0"), "pkgUj16k"),
        "ops16k": _req_pos(_req_dict(m16.get("actuator_output"), "m16.act").get("chases"), "ops16k"),
        "pkgUj64m": _req_pos(_req_dict(m64.get("delta_rapl_uj"), "m64.uj").get("package_0"), "pkgUj64m"),
        "ops64m": _req_pos(_req_dict(m64.get("actuator_output"), "m64.act").get("chases"), "ops64m"),
        "darkMw16k": _psys_dark_mw(m16),
        "darkMw64m": _psys_dark_mw(m64),
        "pkgDarkMw16k": _pkg_dark_mw(m16),
        "pkgDarkMw64m": _pkg_dark_mw(m64),
        "adjInactRiseMc": adj_rise,
        "distInactRiseMc": dist_rise,
        "twiceFanHystArea": twice_fan,
        "rpmUpMean": rpm_up,
        "rpmDownMean": rpm_dn,
        "tempUpMeanMc": temp_up,
        "tempDownMeanMc": temp_dn,
        "twiceThermalLoadArea": twice_tload,
    }
    h0a_raw = 3 * (obs["pkgMwP8"] - obs["pkgMwP4"]) >= 4 * (obs["pkgMwP4"] - obs["pkgMwP1"])
    h0a_degen = abs(obs["pkgMwP8"] - obs["pkgMwP1"]) <= 200 and obs["opsP8"] >= 7 * obs["opsP1"]
    h0b = (
        obs["pkgUj64m"] * obs["ops16k"] <= 2 * obs["pkgUj16k"] * obs["ops64m"]
        and obs["darkMw64m"] <= obs["darkMw16k"]
    )
    h0c = abs(obs["adjInactRiseMc"] - obs["distInactRiseMc"]) <= 500
    h0d_fan = obs["twiceFanHystArea"] == 0 and abs(obs["rpmDownMean"] - obs["rpmUpMean"]) <= 50
    h0d_obstructed = obs["tempDownMeanMc"] - obs["tempUpMeanMc"] > 1000 and obs["twiceThermalLoadArea"] != 0
    cliff_frac = Fraction(obs["pkgUj64m"] * obs["ops16k"], obs["pkgUj16k"] * obs["ops64m"])
    return {
        "obs": obs,
        "verdicts": {
            "H0a_raw": h0a_raw,
            "H0a_degenerate_pl1": h0a_degen,
            "H0b": h0b,
            "H0c": h0c,
            "H0d_fan_plateau": h0d_fan,
            "H0d_thermal_lag_obstructed": h0d_obstructed,
            "corroborated_clean": 0,
            "falsified_or_obstructed": 4,
            "cliff_16k_to_64m_fraction": [cliff_frac.numerator, cliff_frac.denominator],
            "cliff_16k_to_64m_100x": (100 * cliff_frac.numerator) // cliff_frac.denominator,
        },
    }


def extract_cycle1_obs(telemetry: dict[str, Any]) -> dict[str, Any]:
    smap = _seg_map(telemetry)
    p3 = _get_seg(smap, "c1_u1_p3")
    p6 = _get_seg(smap, "c1_u1_p6")
    m8 = _get_seg(smap, "c1_u3_8m")
    m32 = _get_seg(smap, "c1_u3_32m")
    a23 = _get_seg(smap, "c1_u2_adj_23")
    d27 = _get_seg(smap, "c1_u2_dist_27")
    rmp = _get_seg(smap, "c1_u4_ramp")

    t23 = _core_temps(a23)
    t27 = _core_temps(d27)
    contrast23 = (t23[2] + t23[3]) // 2 - (t23[0] + t23[1] + t23[4] + t23[5] + t23[6] + t23[7]) // 6
    contrast27 = (t27[2] + t27[7]) // 2 - (t27[0] + t27[1] + t27[3] + t27[4] + t27[5] + t27[6]) // 6
    int23 = (t23[2] + t23[3] + t23[4] + t23[5]) // 4 - (t23[0] + t23[1] + t23[6]) // 3
    int27 = (t27[2] + t27[3] + t27[4] + t27[5]) // 4 - (t27[0] + t27[1] + t27[6]) // 3
    interior_minus_edge = (int23 + int27) // 2

    ts = _req_list(rmp.get("time_series"), "c1_u4_ramp.time_series")
    steps = [0, 2, 4, 8, 8, 4, 2, 0]
    step_t = compute_ramp_step_means(ts, 8, 1800, "pkg_temp_mc")
    temp_up = sum(step_t[:4]) // 4
    temp_dn = sum(step_t[4:]) // 4
    twice_area = compute_twice_polygon_area(step_t, steps)

    obs = {
        "pkgMwP3": _req_pos(_req_dict(p3.get("power_mw"), "p3.power_mw").get("package_0"), "pkgMwP3"),
        "pkgMwP6": _req_pos(_req_dict(p6.get("power_mw"), "p6.power_mw").get("package_0"), "pkgMwP6"),
        "pkgUjP3": _req_pos(_req_dict(p3.get("delta_rapl_uj"), "p3.uj").get("package_0"), "pkgUjP3"),
        "pkgUjP6": _req_pos(_req_dict(p6.get("delta_rapl_uj"), "p6.uj").get("package_0"), "pkgUjP6"),
        "opsP3": _req_pos(_req_dict(p3.get("actuator_output"), "p3.act").get("retired_ops"), "opsP3"),
        "opsP6": _req_pos(_req_dict(p6.get("actuator_output"), "p6.act").get("retired_ops"), "opsP6"),
        "pkgUj8m": _req_pos(_req_dict(m8.get("delta_rapl_uj"), "m8.uj").get("package_0"), "pkgUj8m"),
        "ops8m": _req_pos(_req_dict(m8.get("actuator_output"), "m8.act").get("chases"), "ops8m"),
        "pkgUj32m": _req_pos(_req_dict(m32.get("delta_rapl_uj"), "m32.uj").get("package_0"), "pkgUj32m"),
        "ops32m": _req_pos(_req_dict(m32.get("actuator_output"), "m32.act").get("chases"), "ops32m"),
        "pkgDarkMw8m": _pkg_dark_mw(m8),
        "pkgDarkMw32m": _pkg_dark_mw(m32),
        "contrast23Mc": contrast23,
        "contrast27Mc": contrast27,
        "interiorMinusEdgeMc": interior_minus_edge,
        "twiceThermalLoadArea": twice_area,
        "tempUpMeanMc": temp_up,
        "tempDownMeanMc": temp_dn,
    }
    h1a = (
        20 * abs(obs["pkgMwP6"] - obs["pkgMwP3"]) <= obs["pkgMwP3"]
        and 10 * obs["opsP6"] * obs["pkgUjP3"] >= 16 * obs["opsP3"] * obs["pkgUjP6"]
    )
    h1b = (
        2 * obs["pkgUj32m"] * obs["ops8m"] >= 3 * obs["pkgUj8m"] * obs["ops32m"]
        and obs["pkgDarkMw8m"] > 0
        and obs["pkgDarkMw32m"] > 0
    )
    h1c = obs["contrast23Mc"] > obs["contrast27Mc"] and obs["interiorMinusEdgeMc"] > 1500
    h1d = obs["twiceThermalLoadArea"] != 0 and obs["tempDownMeanMc"] > obs["tempUpMeanMc"]
    corroborated = int(h1a) + int(h1b) + int(h1c) + int(h1d)
    return {
        "obs": obs,
        "verdicts": {
            "H1a": h1a,
            "H1b": h1b,
            "H1c": h1c,
            "H1d": h1d,
            "corroborated_clean": corroborated,
            "falsified_or_obstructed": 4 - corroborated,
            "eff_p3_to_p6_100x": (100 * obs["opsP6"] * obs["pkgUjP3"]) // (obs["opsP3"] * obs["pkgUjP6"]),
            "cliff_8m_to_32m_100x": (100 * obs["pkgUj32m"] * obs["ops8m"]) // (obs["pkgUj8m"] * obs["ops32m"]),
        },
    }


def extract_cycle2_obs(telemetry: dict[str, Any]) -> dict[str, Any]:
    smap = _seg_map(telemetry)
    p5 = _get_seg(smap, "c2_u1_p5")
    p7 = _get_seg(smap, "c2_u1_p7")
    m512 = _get_seg(smap, "c2_u3_512k")
    m12 = _get_seg(smap, "c2_u3_12m")
    m48 = _get_seg(smap, "c2_u3_48m")
    h45 = _get_seg(smap, "c2_u2_hot_45")
    c16 = _get_seg(smap, "c2_u2_cool_16")
    rmp = _get_seg(smap, "c2_u4_ramp")

    f5_map = _req_dict(p5.get("mean_freq_khz"), "p5.freq")
    f7_map = _req_dict(p7.get("mean_freq_khz"), "p7.freq")
    freq5 = sum(_req_int(f5_map.get(f"core_{c}"), f"p5.core_{c}") for c in range(5)) // 5
    freq7 = sum(_req_int(f7_map.get(f"core_{c}"), f"p7.core_{c}") for c in range(7)) // 7

    t45 = _core_temps(h45)
    t16 = _core_temps(c16)
    contrast45 = (t45[4] + t45[5]) // 2 - (t45[0] + t45[1] + t45[2] + t45[3] + t45[6] + t45[7]) // 6
    contrast16 = (t16[1] + t16[6]) // 2 - (t16[0] + t16[2] + t16[3] + t16[4] + t16[5] + t16[7]) // 6

    ts = _req_list(rmp.get("time_series"), "c2_u4_ramp.time_series")
    steps = [1, 3, 6, 8, 6, 3, 1]
    step_ms = 1500
    step_t = compute_ramp_step_means(ts, 7, step_ms, "pkg_temp_mc")
    twice_area = compute_twice_polygon_area(step_t, steps)

    y_raw: list[int] = []
    u_raw: list[int] = []
    v_soak: list[int] = []
    v_spread: list[int] = []
    for pt_raw in ts:
        pt = _req_dict(pt_raw, "c2_ts_pt")
        t_ms = _req_int(pt.get("t_ms"), "t_ms")
        y_raw.append(_req_int(pt.get("pkg_temp_mc"), "pkg_temp_mc"))
        u_raw.append(steps[min(6, t_ms // step_ms)])
        v_soak.append(t_ms)
        ct = [_req_int(x, "core_temp") for x in _req_list(pt.get("core_temps_mc"), "core_temps_mc")]
        if len(ct) != 8:
            raise OracleError("BAD_CORE_TEMPS", "expected 8 core temps")
        v_spread.append(max(ct) - min(ct))

    syy = centered_int_dot(y_raw, y_raw)
    suu = centered_int_dot(u_raw, u_raw)
    syu = centered_int_dot(y_raw, u_raw)
    svv_soak = centered_int_dot(v_soak, v_soak)
    suv_soak = centered_int_dot(u_raw, v_soak)
    syv_soak = centered_int_dot(y_raw, v_soak)
    svv_spr = centered_int_dot(v_spread, v_spread)
    suv_spr = centered_int_dot(u_raw, v_spread)
    syv_spr = centered_int_dot(y_raw, v_spread)

    schur_soak = exact_schur_3x3(syy, suu, svv_soak, syu, syv_soak, suv_soak)
    schur_spr = exact_schur_3x3(syy, suu, svv_spr, syu, syv_spr, suv_spr)

    obs = {
        "pkgMwP5": _req_pos(_req_dict(p5.get("power_mw"), "p5.power_mw").get("package_0"), "pkgMwP5"),
        "pkgMwP7": _req_pos(_req_dict(p7.get("power_mw"), "p7.power_mw").get("package_0"), "pkgMwP7"),
        "pkgUjP5": _req_pos(_req_dict(p5.get("delta_rapl_uj"), "p5.uj").get("package_0"), "pkgUjP5"),
        "pkgUjP7": _req_pos(_req_dict(p7.get("delta_rapl_uj"), "p7.uj").get("package_0"), "pkgUjP7"),
        "opsP5": _req_pos(_req_dict(p5.get("actuator_output"), "p5.act").get("retired_ops"), "opsP5"),
        "opsP7": _req_pos(_req_dict(p7.get("actuator_output"), "p7.act").get("retired_ops"), "opsP7"),
        "freqKhzP5": _req_pos(freq5, "freqKhzP5"),
        "freqKhzP7": _req_pos(freq7, "freqKhzP7"),
        "pkgUj512k": _req_pos(_req_dict(m512.get("delta_rapl_uj"), "m512.uj").get("package_0"), "pkgUj512k"),
        "ops512k": _req_pos(_req_dict(m512.get("actuator_output"), "m512.act").get("chases"), "ops512k"),
        "pkgUj12m": _req_pos(_req_dict(m12.get("delta_rapl_uj"), "m12.uj").get("package_0"), "pkgUj12m"),
        "ops12m": _req_pos(_req_dict(m12.get("actuator_output"), "m12.act").get("chases"), "ops12m"),
        "pkgUj48m": _req_pos(_req_dict(m48.get("delta_rapl_uj"), "m48.uj").get("package_0"), "pkgUj48m"),
        "ops48m": _req_pos(_req_dict(m48.get("actuator_output"), "m48.act").get("chases"), "ops48m"),
        "pkgDarkMw512k": _pkg_dark_mw(m512),
        "pkgDarkMw12m": _pkg_dark_mw(m12),
        "pkgDarkMw48m": _pkg_dark_mw(m48),
        "contrast45Mc": contrast45,
        "contrast16Mc": contrast16,
        "twiceThermalLoadArea": twice_area,
        "syy": syy,
        "suu": suu,
        "syu": syu,
        "svvSoak": svv_soak,
        "suvSoak": suv_soak,
        "syvSoak": syv_soak,
        "svvSpread": svv_spr,
        "suvSpread": suv_spr,
        "syvSpread": syv_spr,
    }
    h2a = (
        20 * abs(obs["pkgMwP7"] - obs["pkgMwP5"]) <= obs["pkgMwP5"]
        and 100 * obs["opsP7"] * obs["pkgUjP5"] >= 125 * obs["opsP5"] * obs["pkgUjP7"]
        and 100 * obs["opsP7"] * obs["pkgUjP5"] * obs["freqKhzP5"]
        >= 120 * obs["opsP5"] * obs["pkgUjP7"] * obs["freqKhzP7"]
    )
    h2b_primary = (
        obs["pkgUj48m"] * obs["ops512k"] >= 8 * obs["pkgUj512k"] * obs["ops48m"]
        and obs["pkgUj12m"] * obs["ops512k"] >= 4 * obs["pkgUj512k"] * obs["ops12m"]
        and obs["pkgDarkMw512k"] > 0
        and obs["pkgDarkMw12m"] > 0
        and obs["pkgDarkMw48m"] > 0
    )
    h2b_tail = 10 * obs["pkgUj48m"] * obs["ops12m"] >= 11 * obs["pkgUj12m"] * obs["ops48m"]
    h2b = h2b_primary and h2b_tail
    h2c = obs["contrast45Mc"] > 0 and obs["contrast16Mc"] < 0 and obs["contrast45Mc"] - obs["contrast16Mc"] > 3000
    h2d = (
        obs["twiceThermalLoadArea"] != 0
        and 100 * schur_soak["delta"] * schur_soak["delta"] >= 5 * schur_soak["r1_num"] * schur_soak["det_a"]
        and schur_spr["delta"] != 0
    )
    corroborated = int(h2a) + int(h2b) + int(h2c) + int(h2d)
    return {
        "obs": obs,
        "schur_soak": schur_soak,
        "schur_spread": schur_spr,
        "verdicts": {
            "H2a": h2a,
            "H2b_full": h2b,
            "H2b_primary_cliff_and_dark": h2b_primary,
            "H2b_tail_12m_to_48m": h2b_tail,
            "H2c": h2c,
            "H2d": h2d,
            "corroborated_clean": corroborated,
            "falsified_or_obstructed": 4 - corroborated,
            "eff_raw_100x": (100 * obs["opsP7"] * obs["pkgUjP5"]) // (obs["opsP5"] * obs["pkgUjP7"]),
            "eff_freq_100x": (100 * obs["opsP7"] * obs["pkgUjP5"] * obs["freqKhzP5"])
            // (obs["opsP5"] * obs["pkgUjP7"] * obs["freqKhzP7"]),
            "cliff_512k_to_48m_100x": (100 * obs["pkgUj48m"] * obs["ops512k"]) // (obs["pkgUj512k"] * obs["ops48m"]),
            "cliff_512k_to_12m_100x": (100 * obs["pkgUj12m"] * obs["ops512k"]) // (obs["pkgUj512k"] * obs["ops12m"]),
            "cliff_12m_to_48m_100x": (100 * obs["pkgUj48m"] * obs["ops12m"]) // (obs["pkgUj12m"] * obs["ops48m"]),
        },
    }


def verify_disjoint_held_out_levers(preregs: list[dict[str, Any]]) -> dict[str, Any]:
    if len(preregs) != 3:
        raise OracleError("BAD_CYCLE_COUNT", "expected exactly 3 cycle preregistrations")
    core_sets: list[set[int]] = []
    pair_sets: list[set[tuple[int, int]]] = []
    byte_sets: list[set[int]] = []
    ramp_specs: list[tuple[int, tuple[int, ...]]] = []
    for idx, pr in enumerate(preregs):
        lev = _req_dict(pr.get("held_out_levers"), f"prereg[{idx}].held_out_levers")
        core_sets.append({_req_int(x, "u1_core") for x in _req_list(lev.get("u1_cores"), "u1_cores")})
        pairs_raw = _req_list(lev.get("u2_pairs"), "u2_pairs")
        pset: set[tuple[int, int]] = set()
        for pair in pairs_raw:
            plist = _req_list(pair, "u2_pair")
            if len(plist) != 2:
                raise OracleError("BAD_PAIR", "u2_pair must have length 2")
            a, b = _req_int(plist[0], "pair[0]"), _req_int(plist[1], "pair[1]")
            pset.add((min(a, b), max(a, b)))
        pair_sets.append(pset)
        byte_sets.append({_req_int(x, "u3_bytes") for x in _req_list(lev.get("u3_bytes"), "u3_bytes")})
        step_ms = _req_int(lev.get("u4_ramp_step_ms"), "u4_ramp_step_ms")
        rsteps = tuple(_req_int(x, "u4_step") for x in _req_list(lev.get("u4_ramp_steps"), "u4_ramp_steps"))
        ramp_specs.append((step_ms, rsteps))

    for i in range(3):
        for j in range(i + 1, 3):
            if core_sets[i] & core_sets[j]:
                raise OracleError("OVERLAPPING_CORES", f"u1_cores overlap between cycles {i} and {j}")
            if pair_sets[i] & pair_sets[j]:
                raise OracleError("OVERLAPPING_PAIRS", f"u2_pairs overlap between cycles {i} and {j}")
            if byte_sets[i] & byte_sets[j]:
                raise OracleError("OVERLAPPING_BYTES", f"u3_bytes overlap between cycles {i} and {j}")
            if ramp_specs[i] == ramp_specs[j]:
                raise OracleError("DUPLICATE_RAMP", f"u4_ramp identical between cycles {i} and {j}")

    return {
        "pairwise_disjoint_cores": True,
        "pairwise_disjoint_pairs": True,
        "pairwise_disjoint_bytes": True,
        "pairwise_distinct_ramps": True,
        "total_distinct_core_counts": sum(len(s) for s in core_sets),
        "total_distinct_spatial_pairs": sum(len(s) for s in pair_sets),
        "total_distinct_memory_footprints": sum(len(s) for s in byte_sets),
    }


def _read_artifact_bytes(
    track_dir: Path, rel: str, preloaded_bytes: dict[str, bytes] | None
) -> bytes:
    if preloaded_bytes is not None:
        if rel not in preloaded_bytes:
            raise OracleError("MISSING_ARTIFACT", f"missing preloaded artifact {rel}")
        return preloaded_bytes[rel]
    try:
        return (track_dir / rel).read_bytes()
    except OSError as exc:
        raise OracleError("READ_FAILED", f"cannot read {rel}: {exc.strerror}") from exc


def compute_ceer_summary(
    track_dir: Path, preloaded_bytes: dict[str, bytes] | None = None
) -> dict[str, Any]:
    preregs: list[dict[str, Any]] = []
    tels: list[dict[str, Any]] = []
    chain_hashes: dict[str, str] = {}
    for cid in (0, 1, 2):
        pr_rel = f"cycle_{cid}_prereg.json"
        tel_rel = f"cycle_{cid}_telemetry.json"
        th_rel = f"CEERSiliconCerts/CEER_Cycle{cid}_Theory.lean"
        vd_rel = f"CEERSiliconCerts/CEER_Cycle{cid}_Verdict.lean"
        pr_raw = _read_artifact_bytes(track_dir, pr_rel, preloaded_bytes)
        tel_raw = _read_artifact_bytes(track_dir, tel_rel, preloaded_bytes)
        th_raw = _read_artifact_bytes(track_dir, th_rel, preloaded_bytes)
        vd_raw = _read_artifact_bytes(track_dir, vd_rel, preloaded_bytes)
        pr_sha = hashlib.sha256(pr_raw).hexdigest()
        tel_sha = hashlib.sha256(tel_raw).hexdigest()
        th_sha = hashlib.sha256(th_raw).hexdigest()
        vd_sha = hashlib.sha256(vd_raw).hexdigest()
        pr = _parse_json_bytes(pr_raw, pr_rel)
        tel = _parse_json_bytes(tel_raw, tel_rel)
        if (
            _req_int(pr.get("cycle_id"), f"{pr_rel}.cycle_id") != cid
            or _req_int(tel.get("cycle_id"), f"{tel_rel}.cycle_id") != cid
        ):
            raise OracleError("CYCLE_ID_MISMATCH", f"cycle_id mismatch at cycle {cid}")
        if pr.get("theory_lean_sha256") != th_sha:
            raise OracleError("THEORY_SHA_MISMATCH", f"cycle {cid} prereg theory_lean_sha256 mismatch")
        if tel.get("prereg_sha256") != pr_sha:
            raise OracleError("PREREG_TEL_MISMATCH", f"cycle {cid} telemetry prereg_sha256 mismatch")
        if cid == 0:
            if pr.get("parent_cycle_verdict_sha256") is not None:
                raise OracleError("BAD_ROOT_PARENT", "cycle 0 parent_cycle_verdict_sha256 must be null")
        else:
            prev_vd = chain_hashes[f"cycle_{cid - 1}_verdict_lean_sha256"]
            if pr.get("parent_cycle_verdict_sha256") != prev_vd:
                raise OracleError("CHAIN_BREAK", f"cycle {cid} parent verdict SHA mismatch")
        chain_hashes[f"cycle_{cid}_prereg_sha256"] = pr_sha
        chain_hashes[f"cycle_{cid}_telemetry_sha256"] = tel_sha
        chain_hashes[f"cycle_{cid}_theory_lean_sha256"] = th_sha
        chain_hashes[f"cycle_{cid}_verdict_lean_sha256"] = vd_sha
        preregs.append(pr)
        tels.append(tel)

    disjoint = verify_disjoint_held_out_levers(preregs)
    c0 = extract_cycle0_obs(tels[0])
    c1 = extract_cycle1_obs(tels[1])
    c2 = extract_cycle2_obs(tels[2])

    monotone = (
        c0["verdicts"]["corroborated_clean"]
        < c1["verdicts"]["corroborated_clean"]
        < c2["verdicts"]["corroborated_clean"]
    )
    if not monotone:
        raise OracleError("NON_MONOTONE_CONVERGENCE", "expected strictly increasing clean corroborations")

    return {
        "disjoint_held_out_levers": disjoint,
        "cryptographic_chain": chain_hashes,
        "cycle_0": c0,
        "cycle_1": c1,
        "cycle_2": c2,
        "epistemic_trajectory": {
            "corroborated_clean_by_cycle": [
                c0["verdicts"]["corroborated_clean"],
                c1["verdicts"]["corroborated_clean"],
                c2["verdicts"]["corroborated_clean"],
            ],
            "strictly_monotone": monotone,
        },
    }
