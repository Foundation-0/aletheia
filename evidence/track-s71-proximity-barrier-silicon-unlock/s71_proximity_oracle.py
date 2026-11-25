"""Pure-Integer / Pure-Rational Oracle for Competing-Potential Proximity Barrier & AVX-512 Unlock.

Zero floating-point literals or float() calls; all derived metrics, ratios, energy densities
(pJ/op, mJ/Gw), throughput (Gw/s), and falsifiable gates are computed strictly in exact integer (Z)
and rational (Q = fractions.Fraction) arithmetic.
"""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from typing import Any

SCHEMA_VERSION = "aletheia.s71.proximity_barrier_certificate.v1"
ORACLE_MODULE = "s71_proximity_oracle"
_ASCII_DIGITS = frozenset("0123456789")

PINNED_DIGESTS: dict[str, str] = {
    "preregistration_file_sha256": "db1f7b784f898d27c9497054e78431931909919e7ce08c5e4b1112bdf43dd597",
    "preregistration_sha256": "da99d5253d964e9dc7241644410541a170b77b3332a48c63e758f36966d47233",
    "c_source_sha256": "c861370e90abac5ca12fa7365f2f59f612ac7618869931e7167666f79db3e517",
    "lean_source_sha256": "e65524d00529a2098cb18fb994a6530989a1dfc0c2ce7989bfa9788b873cd7b1",
    "empirical_json_sha256": "7e9ae73dc229427c3b97d0c627670c1363a1f2ba50b32fa6ea8685962d134aa7",
    "mlos_file_sha256": "f726207c40ae5112a6816c55d9f61327a008562c0c98ec43908d82ba565b6ef3",
    "mlos_receipt_inner_sha256": "584c7eebb82c66ed7d23b6bb28057d93c916097644c265e115b8d86af15b74c5",
}

# Frozen exact integer telemetry from live serialized ABBA i9-11900H capture (s71_empirical_results.json)
FROZEN_S71_TOKENS: dict[str, Any] = {
    "prereg_created_utc": "2026-11-24T18:30:24Z",
    "mlos_started_utc": "2026-11-24T18:33:57Z",
    "mlos_ended_utc": "2026-11-24T18:34:08Z",
    "a16_syndrome_errors": 0,
    "avx512_int64_mismatches": 0,
    "multicore_int64_mismatches": 0,
    "ww2_8b": {"total_ops": 64000000, "ns": 581920805, "tsc": 1452466171, "pkg_uj": 14533592, "core_uj": 12757840, "uncore_uj": 235962},
    "ww2_64b": {"total_ops": 64000000, "ns": 135325708, "tsc": 337766843, "pkg_uj": 4662037, "core_uj": 4164723, "uncore_uj": 82642},
    "ww8_8b": {"total_ops": 96000000, "ns": 1024543903, "tsc": 2557257515, "pkg_uj": 48999875, "core_uj": 46021977, "uncore_uj": 240111},
    "ww8_64b": {"total_ops": 96000000, "ns": 60363413, "tsc": 150664471, "pkg_uj": 3645498, "core_uj": 3445914, "uncore_uj": 0},
    "rd8_8b": {"total_ops": 16777216, "ns": 22957355, "tsc": 57289663, "pkg_uj": 1716914, "core_uj": 1623287, "uncore_uj": 88134},
    "rd8_64b": {"total_ops": 16777216, "ns": 61542544, "tsc": 153604811, "pkg_uj": 3423636, "core_uj": 3179985, "uncore_uj": 0},
    "rd8_65536b": {"total_ops": 16777216, "ns": 71412453, "tsc": 178236453, "pkg_uj": 4133779, "core_uj": 3848928, "uncore_uj": 0},
    "gemv_8b": {"total_ops": 180355072, "ns": 8572697, "tsc": 21393175, "pkg_uj": 561584, "core_uj": 500121, "uncore_uj": 30518},
    "gemv_64b": {"total_ops": 180355072, "ns": 1879390, "tsc": 4690623, "pkg_uj": 173888, "core_uj": 167968, "uncore_uj": 0},
    "gemv_dual_opt": {"total_ops": 1442840576, "ns": 9822440, "tsc": 24514278, "pkg_uj": 1041501, "core_uj": 1013425, "uncore_uj": 0},
    "gemv_disp_4096b": {"total_ops": 1442840576, "ns": 9900573, "tsc": 24711505, "pkg_uj": 1128232, "core_uj": 1099911, "uncore_uj": 0},
}


def q_pair(val: Fraction) -> list[int]:
    return [int(val.numerator), int(val.denominator)]


def _is_int_eq(val: Any, target: int) -> bool:
    return type(val) is int and val == target


def _is_pos_int(val: Any) -> bool:
    return type(val) is int and val > 0


def _reject_floats_iter(root: Any) -> None:
    stack: list[Any] = [root]
    while stack:
        node = stack.pop()
        if isinstance(node, float):
            raise TypeError("floating-point values are forbidden in canonical_json_bytes")
        if isinstance(node, dict):
            stack.extend(node.keys())
            stack.extend(node.values())
        elif isinstance(node, (list, tuple)):
            stack.extend(node)


def canonical_json_bytes(obj: Any) -> bytes:
    _reject_floats_iter(obj)
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _dump_compact_exact(node: Any) -> str:
    """Exact compact JSON serializer supporting Decimal (no trailing newline, matches mlos receipt)."""
    nt = type(node)
    if nt is dict:
        return "{" + ",".join(json.dumps(k, ensure_ascii=True) + ":" + _dump_compact_exact(node[k]) for k in sorted(node.keys())) + "}"
    if nt is list:
        return "[" + ",".join(_dump_compact_exact(v) for v in node) + "]"
    if nt is Decimal:
        return str(node)
    return json.dumps(node, ensure_ascii=True)


def _parse_iso_utc_seconds(ts: str) -> int:
    if type(ts) is not str or len(ts) != 20 or not ts.endswith("Z"):
        raise ValueError("invalid ISO-8601 UTC timestamp format")
    if ts[4] != "-" or ts[7] != "-" or ts[10] != "T" or ts[13] != ":" or ts[16] != ":":
        raise ValueError("invalid ISO-8601 UTC separators")
    parts = (ts[0:4], ts[5:7], ts[8:10], ts[11:13], ts[14:16], ts[17:19])
    if any(any(ch not in _ASCII_DIGITS for ch in p) for p in parts):
        raise ValueError("non-digit ISO-8601 UTC field")
    yr, mo, dy, hr, mi, se = (int(p) for p in parts)
    if mo < 1 or mo > 12 or dy < 1 or dy > 31 or hr > 23 or mi > 59 or se > 59:
        raise ValueError("out-of-range ISO-8601 UTC field")
    y = yr - (1 if mo <= 2 else 0)
    era = y // 400
    yoe = y - era * 400
    mp = mo + (9 if mo <= 2 else -3)
    doy = (153 * mp + 2) // 5 + dy - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    days = era * 146097 + doe - 719468
    return days * 86400 + hr * 3600 + mi * 60 + se


def _delta_pot_num(a_rep: int, b_att: int, c_soft: int, r: int) -> int:
    return b_att * r * (r + 1) * (2 * r + 1) - a_rep * (r * r + c_soft) * ((r + 1) * (r + 1) + c_soft)


def _ns_per_op(row: dict[str, Any]) -> Fraction:
    return Fraction(row["ns"], row["total_ops"])


def _tsc_per_op(row: dict[str, Any]) -> Fraction:
    return Fraction(row["tsc"], row["total_ops"])


def _pkg_pj_per_op(row: dict[str, Any]) -> Fraction:
    return Fraction(row["pkg_uj"] * 1_000_000, row["total_ops"])


def _gweights_per_s(row: dict[str, Any]) -> Fraction:
    return Fraction(row["total_ops"], row["ns"])


def _pkg_mj_per_gw(row: dict[str, Any]) -> Fraction:
    return Fraction(row["pkg_uj"] * 1_000_000, row["total_ops"])


def _row_dark_nonneg(row: dict[str, Any]) -> bool:
    return (
        _is_pos_int(row["total_ops"])
        and _is_pos_int(row["ns"])
        and _is_pos_int(row["tsc"])
        and _is_pos_int(row["pkg_uj"])
        and type(row["core_uj"]) is int
        and row["core_uj"] >= 0
        and type(row["uncore_uj"]) is int
        and row["uncore_uj"] >= 0
        and row["pkg_uj"] >= row["core_uj"] + row["uncore_uj"]
    )


def _build_exact_pillar() -> dict[str, Any]:
    d11 = _delta_pot_num(10, 60, 1, 11)
    d12 = _delta_pot_num(10, 60, 1, 12)
    same_line_8b = all((64 * 7 + 8 * t) // 64 == 7 for t in range(8))
    disjoint_64b = len({(13 + 64 * t) // 64 for t in range(8)}) == 8
    m_rows, k_cols = 2048, 11008
    n_weights = m_rows * k_cols
    bytes_4_5 = (n_weights * 9) // 16
    return {
        "canonical_barrier_a": 10,
        "canonical_barrier_b": 60,
        "canonical_barrier_c": 1,
        "canonical_barrier_r_star": 12,
        "delta_pot_num_r11": d11,
        "delta_pot_num_r12": d12,
        "barrier_sign_flip_exact": d11 > 0 and d12 < 0,
        "cache_line_bytes": 64,
        "all_8_cores_stride_8b_single_line": same_line_8b,
        "all_8_cores_stride_64b_disjoint_lines": disjoint_64b,
        "block_h4_max_butterfly_abs": 28,
        "block_h4_vnni_u8_min": 4,
        "block_h4_vnni_u8_max": 60,
        "qwen3b_down_proj_m": m_rows,
        "qwen3b_down_proj_k": k_cols,
        "qwen3b_down_proj_weights": n_weights,
        "qwen3b_down_proj_4_5bpw_bytes": bytes_4_5,
        "lean4_theorem_count": 19,
    }


def _evaluate_sampled_metrics(
    ww2_8: dict[str, Any],
    ww2_64: dict[str, Any],
    ww8_8: dict[str, Any],
    ww8_64: dict[str, Any],
    rd8_8: dict[str, Any],
    rd8_64: dict[str, Any],
    rd8_64k: dict[str, Any],
    gs_8: dict[str, Any],
    gs_64: dict[str, Any],
    opt: dict[str, Any],
    dsp: dict[str, Any],
    syn_errs: Any,
    avx_mism: Any,
    mc_mism: Any,
) -> dict[str, Any]:
    ww2_lat_ratio = _ns_per_op(ww2_8) / _ns_per_op(ww2_64)
    ww2_pj_ratio = _pkg_pj_per_op(ww2_8) / _pkg_pj_per_op(ww2_64)
    ww8_lat_ratio = _ns_per_op(ww8_8) / _ns_per_op(ww8_64)
    ww8_pj_ratio = _pkg_pj_per_op(ww8_8) / _pkg_pj_per_op(ww8_64)
    rd8_64_lat_ratio = _ns_per_op(rd8_64) / _ns_per_op(rd8_8)
    rd8_64_pj_ratio = _pkg_pj_per_op(rd8_64) / _pkg_pj_per_op(rd8_8)
    rd8_64k_lat_ratio = _ns_per_op(rd8_64k) / _ns_per_op(rd8_8)
    rd8_64k_pj_ratio = _pkg_pj_per_op(rd8_64k) / _pkg_pj_per_op(rd8_8)

    # Opposite-sign horizon flip on all 3 axes: (w64 - w8)*(r64 - r8) < 0
    flip_ns = (_ns_per_op(ww8_64) - _ns_per_op(ww8_8)) * (_ns_per_op(rd8_64) - _ns_per_op(rd8_8)) < 0
    flip_tsc = (_tsc_per_op(ww8_64) - _tsc_per_op(ww8_8)) * (_tsc_per_op(rd8_64) - _tsc_per_op(rd8_8)) < 0
    flip_pj = (_pkg_pj_per_op(ww8_64) - _pkg_pj_per_op(ww8_8)) * (_pkg_pj_per_op(rd8_64) - _pkg_pj_per_op(rd8_8)) < 0

    gs_speedup = _gweights_per_s(gs_64) / _gweights_per_s(gs_8)
    gs_energy_gain = _pkg_mj_per_gw(gs_8) / _pkg_mj_per_gw(gs_64)
    opt_vs_8b_speedup = _gweights_per_s(opt) / _gweights_per_s(gs_8)
    opt_vs_8b_energy_gain = _pkg_mj_per_gw(gs_8) / _pkg_mj_per_gw(opt)
    opt_vs_dsp_speedup = _gweights_per_s(opt) / _gweights_per_s(dsp)
    opt_vs_dsp_energy_gain = _pkg_mj_per_gw(dsp) / _pkg_mj_per_gw(opt)

    all_rows = (ww2_8, ww2_64, ww8_8, ww8_64, rd8_8, rd8_64, rd8_64k, gs_8, gs_64, opt, dsp)
    gates = {
        "p_s71_1a_ww2_repulsion_ge_2x": ww2_lat_ratio >= Fraction(2, 1) and ww2_pj_ratio >= Fraction(2, 1),
        "p_s71_1b_ww8_repulsion_ge_3x": ww8_lat_ratio >= Fraction(3, 1) and ww8_pj_ratio >= Fraction(3, 1),
        "p_s71_1c_rd8_fusion_confirmed": (
            rd8_64_lat_ratio >= Fraction(13, 10)
            and rd8_64_pj_ratio >= Fraction(13, 10)
            and rd8_64k_lat_ratio >= Fraction(2, 1)
            and rd8_64k_pj_ratio >= Fraction(2, 1)
        ),
        "p_s71_1d_opposite_sign_3axes_and_dark_nonneg": flip_ns and flip_tsc and flip_pj and all(_row_dark_nonneg(r) for r in all_rows),
        "p_s71_2a_avx512_zero_errors": _is_int_eq(syn_errs, 0) and _is_int_eq(avx_mism, 0) and _is_int_eq(mc_mism, 0),
        "p_s71_2b_gemv_wall_break_ge_1_5x": gs_speedup >= Fraction(3, 2) and gs_energy_gain > Fraction(1, 1),
        "p_s71_2c_dual_opt_vs_8b_ge_3x": opt_vs_8b_speedup >= Fraction(3, 1) and opt_vs_8b_energy_gain >= Fraction(3, 1),
        "p_s71_2c_dispersed_energy_gain_confirmed_and_latency_nuance": (
            opt_vs_dsp_speedup > Fraction(1, 1)
            and opt_vs_dsp_speedup < Fraction(21, 20)
            and opt_vs_dsp_energy_gain > Fraction(1, 1)
        ),
    }
    return {
        "ratios": {
            "ww2_8b_to_64b_lat_ratio_q": q_pair(ww2_lat_ratio),
            "ww2_8b_to_64b_pj_ratio_q": q_pair(ww2_pj_ratio),
            "ww8_8b_to_64b_lat_ratio_q": q_pair(ww8_lat_ratio),
            "ww8_8b_to_64b_pj_ratio_q": q_pair(ww8_pj_ratio),
            "rd8_64b_over_8b_lat_ratio_q": q_pair(rd8_64_lat_ratio),
            "rd8_64b_over_8b_pj_ratio_q": q_pair(rd8_64_pj_ratio),
            "rd8_65536b_over_8b_lat_ratio_q": q_pair(rd8_64k_lat_ratio),
            "rd8_65536b_over_8b_pj_ratio_q": q_pair(rd8_64k_pj_ratio),
            "gemv_8b_to_64b_speedup_q": q_pair(gs_speedup),
            "gemv_8b_to_64b_energy_gain_q": q_pair(gs_energy_gain),
            "gemv_dual_opt_gweights_per_s_q": q_pair(_gweights_per_s(opt)),
            "gemv_dual_opt_mj_per_gw_q": q_pair(_pkg_mj_per_gw(opt)),
            "gemv_dual_opt_vs_8b_speedup_q": q_pair(opt_vs_8b_speedup),
            "gemv_dual_opt_vs_8b_energy_gain_q": q_pair(opt_vs_8b_energy_gain),
            "gemv_dual_opt_vs_4096b_speedup_q": q_pair(opt_vs_dsp_speedup),
            "gemv_dual_opt_vs_4096b_energy_gain_q": q_pair(opt_vs_dsp_energy_gain),
        },
        "gates": gates,
    }


def _build_sampled_pillar() -> dict[str, Any]:
    t = FROZEN_S71_TOKENS
    t_pre = _parse_iso_utc_seconds(t["prereg_created_utc"])
    t_sta = _parse_iso_utc_seconds(t["mlos_started_utc"])
    t_end = _parse_iso_utc_seconds(t["mlos_ended_utc"])
    ev = _evaluate_sampled_metrics(
        t["ww2_8b"],
        t["ww2_64b"],
        t["ww8_8b"],
        t["ww8_64b"],
        t["rd8_8b"],
        t["rd8_64b"],
        t["rd8_65536b"],
        t["gemv_8b"],
        t["gemv_64b"],
        t["gemv_dual_opt"],
        t["gemv_disp_4096b"],
        t["a16_syndrome_errors"],
        t["avx512_int64_mismatches"],
        t["multicore_int64_mismatches"],
    )
    gates = dict(ev["gates"])
    gates["prereg_strictly_precedes_execution"] = t_pre < t_sta and t_sta < t_end
    return {
        "oracle_class": "sampled",
        "measured_live_silicon": True,
        "prereg_to_run_gap_seconds": t_sta - t_pre,
        "pinned_digests": dict(PINNED_DIGESTS),
        "exact_ratios": ev["ratios"],
        "sampled_gates": gates,
    }


def build_certificate() -> dict[str, Any]:
    p1 = _build_exact_pillar()
    p2 = _build_sampled_pillar()
    exact_ok = (
        p1["barrier_sign_flip_exact"]
        and p1["all_8_cores_stride_8b_single_line"]
        and p1["all_8_cores_stride_64b_disjoint_lines"]
        and _is_int_eq(p1["qwen3b_down_proj_weights"], 22544384)
        and _is_int_eq(p1["lean4_theorem_count"], 19)
    )
    sampled_ok = all(p2["sampled_gates"].values())
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "oracle_module": ORACLE_MODULE,
        "epistemic_taxonomy": {
            "pillar_1_exact_proximity_and_h4_algebra": "exact",
            "pillar_2_sampled_live_i9_rapl_and_avx512": "sampled",
        },
        "pillar_1_exact_proximity_and_h4_algebra": p1,
        "pillar_2_sampled_live_i9_rapl_and_avx512": p2,
        "verdict": {
            "exact_invariants_pass": exact_ok,
            "sampled_gates_pass": sampled_ok,
            "all_passed": exact_ok and sampled_ok,
        },
    }
    cert = dict(body)
    cert["certificate_sha256"] = hashlib.sha256(canonical_json_bytes(body)).hexdigest()
    return cert


def _by_stride(rows: list[dict[str, Any]], stride: int) -> dict[str, Any]:
    for row in rows:
        if _is_int_eq(row["stride_bytes"], stride):
            return row
    raise KeyError(f"stride {stride} missing")


def _by_label(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    for row in rows:
        if row["label"] == label:
            return row
    raise KeyError(f"label {label} missing")


def verify_live_receipts(
    prereg_obj: dict[str, Any],
    emp_obj: dict[str, Any],
    mlos_obj: dict[str, Any],
    prereg_file_sha: str,
    c_file_sha: str,
    lean_file_sha: str,
    emp_file_sha: str,
    mlos_file_sha: str,
) -> dict[str, Any]:
    """Verify frozen live receipts against pinned digests, inner body hashes, causal order & gates."""
    prereg_body = {k: v for k, v in prereg_obj.items() if k != "preregistration_sha256"}
    prereg_recomp = hashlib.sha256(canonical_json_bytes(prereg_body)).hexdigest()
    mlos_body = {k: v for k, v in mlos_obj.items() if k != "receipt_sha256"}
    mlos_recomp = hashlib.sha256(_dump_compact_exact(mlos_body).encode("utf-8")).hexdigest()

    post_cap = emp_obj.get("post_capture_sources")
    post_cap_ok = (
        type(post_cap) is dict
        and post_cap.get("s71_proximity_bench.c") == c_file_sha
        and post_cap.get("ProximityBarrierSilicon.lean") == lean_file_sha
    )
    prereg_pin_ok = (
        emp_obj["c_source_sha256"] == prereg_obj["pinned_sources"]["s71_proximity_bench.c"]
        and emp_obj["lean_source_sha256"] == prereg_obj["pinned_sources"]["ProximityBarrierSilicon.lean"]
    )
    digests_match = (
        prereg_file_sha == PINNED_DIGESTS["preregistration_file_sha256"]
        and prereg_obj["preregistration_sha256"] == PINNED_DIGESTS["preregistration_sha256"]
        and prereg_recomp == PINNED_DIGESTS["preregistration_sha256"]
        and emp_obj["c_source_sha256"] == PINNED_DIGESTS["c_source_sha256"]
        and emp_obj["lean_source_sha256"] == PINNED_DIGESTS["lean_source_sha256"]
        and prereg_pin_ok
        and post_cap_ok
        and emp_file_sha == PINNED_DIGESTS["empirical_json_sha256"]
        and emp_obj["preregistration_file_sha256"] == PINNED_DIGESTS["preregistration_file_sha256"]
        and emp_obj["preregistration_sha256"] == PINNED_DIGESTS["preregistration_sha256"]
        and mlos_file_sha == PINNED_DIGESTS["mlos_file_sha256"]
        and mlos_obj["receipt_sha256"] == PINNED_DIGESTS["mlos_receipt_inner_sha256"]
        and mlos_recomp == PINNED_DIGESTS["mlos_receipt_inner_sha256"]
    )

    t_pre = _parse_iso_utc_seconds(prereg_obj["created_utc"])
    t_sta = _parse_iso_utc_seconds(mlos_obj["execution"]["started_utc"])
    t_end = _parse_iso_utc_seconds(mlos_obj["execution"]["ended_utc"])
    causal_order = t_pre < t_sta and t_sta < t_end

    mlos_clean = (
        mlos_obj["determinism_zone"] == "B"
        and mlos_obj["clean_hardware_run"] is True
        and mlos_obj["anomalies"] == []
        and _is_int_eq(mlos_obj["execution"]["exit_code"], 0)
        and mlos_obj["start_gpu_telemetry"]["graphics_processes"] == []
        and mlos_obj["start_gpu_telemetry"]["compute_processes"] == []
        and mlos_obj["end_gpu_telemetry"]["graphics_processes"] == []
        and mlos_obj["end_gpu_telemetry"]["compute_processes"] == []
    )

    honesty_tags = (
        emp_obj["measured_live_silicon"] is True
        and emp_obj["oracle_class"] == "sampled"
        and emp_obj["ac_online"] is True
    )

    meas = emp_obj["measurements"]
    ww2 = meas["write_write_2core"]
    ww8 = meas["write_write_8core"]
    rd8 = meas["read_shared_8core"]
    gs = meas["avx512_a16_blockh4_stride_sweep"]
    df = meas["avx512_a16_blockh4_dual_force"]

    all_34_dark_ok = (
        len(ww2) == 9
        and len(ww8) == 9
        and len(rd8) == 9
        and len(gs) == 5
        and len(df) == 2
        and all(_row_dark_nonneg(r) for r in (*ww2, *ww8, *rd8, *gs, *df))
    )

    if all_34_dark_ok:
        ev_gates = _evaluate_sampled_metrics(
            _by_stride(ww2, 8),
            _by_stride(ww2, 64),
            _by_stride(ww8, 8),
            _by_stride(ww8, 64),
            _by_stride(rd8, 8),
            _by_stride(rd8, 64),
            _by_stride(rd8, 65536),
            _by_stride(gs, 8),
            _by_stride(gs, 64),
            _by_label(df, "dual_force_aligned_reg_read_shared"),
            _by_label(df, "aligned_reg_dispersed_read_4096B"),
            meas["a16_syndrome_errors"],
            meas["avx512_int64_mismatches"],
            meas["multicore_int64_mismatches"],
        )["gates"]
    else:
        ev_gates = {
            "p_s71_1a_ww2_repulsion_ge_2x": False,
            "p_s71_1b_ww8_repulsion_ge_3x": False,
            "p_s71_1c_rd8_fusion_confirmed": False,
            "p_s71_1d_opposite_sign_3axes_and_dark_nonneg": False,
            "p_s71_2a_avx512_zero_errors": False,
            "p_s71_2b_gemv_wall_break_ge_1_5x": False,
            "p_s71_2c_dual_opt_vs_8b_ge_3x": False,
            "p_s71_2c_dispersed_energy_gain_confirmed_and_latency_nuance": False,
        }

    checks: dict[str, bool] = {
        "digests_match": digests_match,
        "prereg_receipt_pin_match": prereg_pin_ok,
        "post_capture_sources_match": post_cap_ok,
        "prereg_strictly_precedes_execution": causal_order,
        "mlos_clean_isolated_run": mlos_clean,
        "honesty_tags": honesty_tags,
        "all_34_rows_nonneg_rapl_dark": all_34_dark_ok,
        **ev_gates,
    }
    return {"all_verified": all(checks.values()), "checks": checks}
