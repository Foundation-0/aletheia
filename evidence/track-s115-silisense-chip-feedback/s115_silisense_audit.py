#!/usr/bin/env python3
"""Track S115 (`Project SiliSense` / `PREREG-S115`) Pure-Stdlib Audit & Certificate Verifier.

Strictly Python standard library ONLY (`0` third-party imports, `0` torch/numpy/scipy).
Zero bare asserts. Zero hardcoded verdict strings: `H15a`, `H15b`, and `H15c` verdicts
are recomputed strictly from raw per-pair / per-seed hardware measurements, paired
statistics (normal z and exact two-sided Student-t), Mode-1 sensor-airlock spy logs,
and Ring-0 `mlos` Zone-B hardware provenance receipts.

Usage:
    python3 -I -B s115_silisense_audit.py --write
    python3 -I -B s115_silisense_audit.py --standalone --json
    python3 -I -B s115_silisense_audit.py --check [s115_silisense_certificate.json]
"""

from __future__ import annotations

import argparse
import datetime
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

SCHEMA_VERSION = "silisense.track_s115.audit_certificate.v1"
CERT_FILENAME = "s115_silisense_certificate.json"
RESULTS_FILENAME = "s115_live_gpu_results.json"
ZONE_B_FILENAME = "mlos_zone_b_s115_mode1.json"
REPORT_FILENAME = "REPORT_S115_SILISENSE_GPU_EVAL.md"
PREREG_FILENAME = "PREREG_S115_SILICON_PHYSICS_FEEDBACK_OPTIMIZER.md"
PREREG_SHA256 = "4787a4f407bb09b440c19190a24e89fead862ba9cec96edd68e5d222e0f0dc75"

EXPECTED_SEEDS = (42, 137, 2026)
EXPECTED_RAPL_DOMAINS = ("core", "pkg", "psys", "uncore")
H15B_EXPECTED_ARMS = (
    "NoGovernor",
    "Reactive-1Hz-SMI",
    "Shuffled-Trigger-Control",
    "SiliSense-Precursor-Gov",
)
H15C_EXPECTED_TUNERS = (
    "Scalar-TokPerSec-Tuner",
    "Scalar-MeanWatt-EDP-Tuner",
    "SiliSense-Composite-Tuner",
)

# Locked PREREG-S115 numerical thresholds and composite objective weights
H15A_REL_DROP_MAX = -20.0
H15A_Z_MAX = -2.0
H15A_EQW_DIFF_MAX = 0.05
A7_SCHUR_CORR_MAX = 1e-9

H15B_MODE1_LEAD_MAX_MS = -20.0
H15B_P_CIRC_MAX = 0.005
H15B_STALL_REL_MAX = -25.0
H15B_CV_REL_MAX = -20.0
H15B_Z_MAX = -2.0
H15B_TPS_REL_MIN = -2.0
H15B_PARTIAL_TPS_MIN = -5.0

LOCKED_LAMBDA_A3 = 0.15
LOCKED_LAMBDA_A7 = 0.15
LOCKED_LAMBDA_A5 = 0.10
LOCKED_HINGE_Z = 2.0
H15C_CS08_EFF_TOKENS = 8192
H15C_VS_TPS_REL_MAX = -5.0
H15C_VS_EDP0_REL_MAX = -2.0
H15C_DRIFT_REL_MAX = -15.0
H15C_Z_MAX = -2.0
H15C_PARTIAL_TIE_BAND = 2.0

WEIGHT_SUFFIXES = frozenset({".pt", ".pth", ".ckpt", ".safetensors", ".bin", ".gguf", ".onnx", ".npz", ".npy"})
AV_SUFFIXES = frozenset({".wav", ".flac", ".ogg", ".mp3", ".mp4", ".mkv", ".avi", ".webm", ".s32le", ".yuyv", ".grey"})
ELF_SUFFIXES = frozenset({".so", ".o", ".a"})
ELF_MAGIC = b"\x7fELF"


class S115AuditError(ValueError):
    """Typed fail-closed audit violation."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.detail = message
        super().__init__(f"[{code}] {message}")


def require_ok(cond: bool, code: str, message: str) -> None:
    if not cond:
        raise S115AuditError(code, message)


def _canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    require_ok(path.is_file(), "MISSING_FILE", f"Required artifact missing: {path.name}")
    return _sha256_bytes(path.read_bytes())


def _reject_nonfinite_json_constant(token: str) -> Any:
    raise ValueError(f"Non-finite JSON constant forbidden: {token}")


def _parse_finite_json_float(raw: str) -> float:
    val = float(raw)
    if not math.isfinite(val):
        raise ValueError(f"Overflow JSON float forbidden in input: {raw}")
    return val


def _load_json_dict(path: Path) -> Dict[str, Any]:
    require_ok(path.is_file(), "MISSING_JSON", f"Missing JSON artifact: {path.name}")
    try:
        obj = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_nonfinite_json_constant,
            parse_float=_parse_finite_json_float,
        )
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise S115AuditError("MALFORMED_JSON", f"Malformed JSON in {path.name}: {exc}") from exc
    require_ok(isinstance(obj, dict), "SCHEMA_ROOT", f"JSON root must be an object in {path.name}")
    return obj


def _parse_utc(raw: Any, label: str) -> datetime.datetime:
    require_ok(isinstance(raw, str), "BAD_TIMESTAMP", f"Invalid UTC timestamp for {label}")
    try:
        dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise S115AuditError("BAD_TIMESTAMP", f"Unparseable UTC timestamp for {label}: {raw}") from exc
    require_ok(dt.tzinfo is not None, "NAIVE_TIMESTAMP", f"Timestamp for {label} must include timezone")
    return dt.astimezone(datetime.timezone.utc)


def _as_float(val: Any, label: str) -> float:
    require_ok(
        isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(float(val)),
        "BAD_NUMBER",
        f"Non-finite or non-numeric value for {label}",
    )
    return float(val)


def _as_int(val: Any, label: str) -> int:
    require_ok(isinstance(val, int) and not isinstance(val, bool), "BAD_INT", f"Non-int value for {label}")
    return int(val)


def _verify_inner_hash(obj: Mapping[str, Any], field_name: str, label: str) -> str:
    recorded = obj.get(field_name)
    require_ok(isinstance(recorded, str) and len(recorded) == 64, "MISSING_INNER_HASH", f"Missing {field_name} in {label}")
    body = {k: v for k, v in obj.items() if k != field_name}
    recomputed = _sha256_bytes(_canonical_bytes(body))
    require_ok(recomputed == recorded, "INNER_HASH_MISMATCH", f"{label} {field_name} mismatch: {recomputed} != {recorded}")
    return recomputed


def _student_t_two_sided_p(abs_t: float, df: int) -> float:
    require_ok(df >= 1, "BAD_DF", f"Invalid degrees of freedom: {df}")
    if df == 2:
        return max(0.0, min(1.0, 1.0 - abs_t / math.sqrt(2.0 + abs_t * abs_t)))
    theta = math.atan(abs_t / math.sqrt(float(df)))
    if df % 2 == 1:
        s_term = theta
        if df > 1:
            cos_t = math.cos(theta)
            sin_t = math.sin(theta)
            coef = sin_t * cos_t
            s_term += coef
            for k in range(3, df, 2):
                coef *= (float(k - 1) / float(k)) * (cos_t * cos_t)
                s_term += coef
        cdf_abs = 0.5 + s_term / math.pi
    else:
        sin_t = math.sin(theta)
        cos_t = math.cos(theta)
        s_term = sin_t
        coef = sin_t
        for k in range(2, df, 2):
            coef *= (float(k - 1) / float(k)) * (cos_t * cos_t)
            s_term += coef
        cdf_abs = 0.5 + 0.5 * s_term
    return max(0.0, min(1.0, 2.0 * (1.0 - cdf_abs)))


def recompute_paired_stats(baseline_vals: Sequence[float], candidate_vals: Sequence[float]) -> Dict[str, float]:
    n = len(baseline_vals)
    require_ok(n == len(candidate_vals) and n >= 3, "PAIRED_LEN", "Paired vectors must have equal length >= 3")
    diffs = [float(cand) - float(base) for base, cand in zip(baseline_vals, candidate_vals)]
    mean_a = sum(baseline_vals) / float(n)
    mean_b = sum(candidate_vals) / float(n)
    mean_d = sum(diffs) / float(n)
    var = sum((d - mean_d) ** 2 for d in diffs) / float(n - 1)
    se = math.sqrt(max(0.0, var) / float(n))
    if abs(mean_d) <= 1e-15:
        z_val = 0.0
    elif se <= 1e-15:
        z_val = math.copysign(1e6, mean_d)
    else:
        z_val = mean_d / se
    rel_pct = 0.0 if abs(mean_a) <= 1e-12 else 100.0 * (mean_b - mean_a) / abs(mean_a)
    p_norm = math.erfc(min(50.0, abs(z_val)) / math.sqrt(2.0))
    p_t = _student_t_two_sided_p(abs(z_val), n - 1)
    return {
        "baseline_mean": round(mean_a, 6),
        "candidate_mean": round(mean_b, 6),
        "paired_diff_mean": round(mean_d, 6),
        "paired_diff_se": round(se, 6),
        "rel_change_pct": round(rel_pct, 4),
        "z_paired": round(z_val, 4),
        "p_normal_2s": round(p_norm, 6),
        "p_student_t_2s": round(p_t, 6),
    }


def grade_h15a_pure(
    *,
    any_sig_0p005: bool,
    a3_rel_pct: float,
    a3_z: float,
    a7_rel_pct: float,
    a7_z: float,
    max_eqw_rel_diff: float,
    eqw_a3_z: float,
    eqw_a7_z: float,
) -> Dict[str, Any]:
    """Pure PREREG-S115 H15a grading function (zero hardcoded verdict literals)."""
    c1 = bool(any_sig_0p005)
    a3_drops = (a3_rel_pct <= H15A_REL_DROP_MAX) and (a3_z <= H15A_Z_MAX)
    a7_drops = (a7_rel_pct <= H15A_REL_DROP_MAX) and (a7_z <= H15A_Z_MAX)
    c2 = bool(a3_drops and a7_drops)
    c3 = bool((max_eqw_rel_diff <= H15A_EQW_DIFF_MAX) and ((eqw_a3_z <= H15A_Z_MAX) or (eqw_a7_z <= H15A_Z_MAX)))
    if c1 and c2 and c3:
        verdict = "CONFIRMED"
    elif c1 and (a3_drops or a7_drops):
        verdict = "PARTIAL"
    else:
        verdict = "FALSIFIED"
    return {
        "criterion_1_non_gaussian_activity_0p005": c1,
        "criterion_2_both_a3_and_a7_reduced_20pct": c2,
        "criterion_3_equal_watt_non_confound": c3,
        "verdict": verdict,
    }


def grade_h15b_pure(
    *,
    med_lead_ms: float,
    max_p_circ: float,
    stall_no_rel: float,
    stall_no_z: float,
    stall_smi_rel: float,
    stall_smi_z: float,
    stall_shuf_z: float,
    cv_no_rel: float,
    cv_no_z: float,
    cv_smi_rel: float,
    cv_smi_z: float,
    cv_shuf_z: float,
    tps_no_rel: float,
) -> Dict[str, Any]:
    """Pure PREREG-S115 H15b grading function (zero hardcoded verdict literals)."""
    c1 = (max_p_circ < H15B_P_CIRC_MAX) and (med_lead_ms <= H15B_MODE1_LEAD_MAX_MS)
    stall_win = (
        (stall_no_rel <= H15B_STALL_REL_MAX)
        and (stall_no_z <= H15B_Z_MAX)
        and (stall_smi_rel <= H15B_STALL_REL_MAX)
        and (stall_smi_z <= H15B_Z_MAX)
        and (stall_shuf_z <= H15B_Z_MAX)
    )
    cv_win = (
        (cv_no_rel <= H15B_CV_REL_MAX)
        and (cv_no_z <= H15B_Z_MAX)
        and (cv_smi_rel <= H15B_CV_REL_MAX)
        and (cv_smi_z <= H15B_Z_MAX)
        and (cv_shuf_z <= H15B_Z_MAX)
    )
    tps_ok = tps_no_rel >= H15B_TPS_REL_MIN
    c2 = bool((stall_win or cv_win) and tps_ok)
    if c1 and c2:
        verdict = "CONFIRMED"
    elif c1 or (((stall_no_rel <= H15B_STALL_REL_MAX) or (cv_no_rel <= H15B_CV_REL_MAX)) and (tps_no_rel >= H15B_PARTIAL_TPS_MIN)):
        verdict = "PARTIAL"
    else:
        verdict = "FALSIFIED"
    return {
        "criterion_1_precursor_lead": bool(c1),
        "criterion_2_closed_loop_stability": bool(c2),
        "verdict": verdict,
    }


def grade_h15c_pure(
    *,
    vs_tps_rel: float,
    vs_tps_z: float,
    vs_edp0_rel: float,
    vs_edp0_z: float,
    drift_vs_edp0_rel: float,
    drift_vs_edp0_z: float,
) -> Dict[str, Any]:
    """Pure PREREG-S115 H15c grading function (zero hardcoded verdict literals)."""
    c1 = (vs_tps_rel <= H15C_VS_TPS_REL_MAX) and (vs_tps_z <= H15C_Z_MAX)
    c2 = ((vs_edp0_rel <= H15C_VS_EDP0_REL_MAX) and (vs_edp0_z <= H15C_Z_MAX)) or (
        (drift_vs_edp0_rel <= H15C_DRIFT_REL_MAX) and (drift_vs_edp0_z <= H15C_Z_MAX)
    )
    if c1 and c2:
        verdict = "CONFIRMED"
    elif c1 and (abs(vs_edp0_rel) <= H15C_PARTIAL_TIE_BAND):
        verdict = "PARTIAL"
    else:
        verdict = "FALSIFIED"
    return {
        "criterion_1_edp_vs_scalar_tps": bool(c1),
        "criterion_2_edp_or_drift_vs_mean_watt": bool(c2),
        "verdict": verdict,
    }


def _check_directory_hygiene(track_dir: Path) -> Dict[str, int]:
    weights = 0
    av_files = 0
    elfs = 0
    for p in sorted(track_dir.rglob("*")):
        if not p.is_file():
            continue
        suf = p.suffix.lower()
        if suf in WEIGHT_SUFFIXES:
            weights += 1
        if suf in AV_SUFFIXES:
            av_files += 1
        is_elf = suf in ELF_SUFFIXES
        if not is_elf:
            with p.open("rb") as fh:
                if fh.read(4) == ELF_MAGIC:
                    is_elf = True
        if is_elf:
            elfs += 1
    require_ok(weights == 0, "HYGIENE_WEIGHTS", f"Found {weights} weight files in track directory (WEIGHTS=0 required)")
    require_ok(av_files == 0, "HYGIENE_AV", f"Found {av_files} audio/video files in track directory (AV=0 required)")
    require_ok(elfs == 0, "HYGIENE_ELF", f"Found {elfs} ELF/shared-object binaries in track directory (ELF=0 required)")
    return {"weights_count": weights, "av_count": av_files, "elf_count": elfs}


def _resolve_prereg_path(track_dir: Path) -> Optional[Path]:
    local_copy = track_dir / PREREG_FILENAME
    if local_copy.is_file():
        return local_copy
    notes_copy = track_dir.parent / "notes" / "holosphere_kernel_transformer_2026_11_25" / PREREG_FILENAME
    if notes_copy.is_file():
        return notes_copy
    return None


def _verify_zone_b_receipt(track_dir: Path, result_data: Mapping[str, Any]) -> Dict[str, Any]:
    receipt_path = track_dir / ZONE_B_FILENAME
    rec = _load_json_dict(receipt_path)
    receipt_sha = _verify_inner_hash(rec, "receipt_sha256", ZONE_B_FILENAME)
    require_ok(rec.get("schema") == "mlos-run-receipt/v0.1", "RECEIPT_SCHEMA", f"Bad receipt schema in {ZONE_B_FILENAME}")
    require_ok(rec.get("determinism_zone") == "B", "RECEIPT_ZONE", f"Receipt {ZONE_B_FILENAME} must be Zone B")
    require_ok(rec.get("clean_hardware_run") is True, "RECEIPT_UNCLEAN", f"Receipt {ZONE_B_FILENAME} clean_hardware_run != True")
    require_ok(rec.get("anomalies") == [], "RECEIPT_ANOMALIES", f"Receipt {ZONE_B_FILENAME} has non-empty anomalies")
    require_ok(rec.get("gpu_telemetry_available") is True, "RECEIPT_NO_GPU_TEL", "Missing GPU telemetry in Zone-B receipt")

    exe = rec.get("execution")
    require_ok(isinstance(exe, dict) and exe.get("exit_code") == 0, "RECEIPT_EXIT_CODE", "Non-zero exit_code in Zone-B receipt")
    started_dt = _parse_utc(exe.get("started_utc"), "zone_b.started_utc")
    ended_dt = _parse_utc(exe.get("ended_utc"), "zone_b.ended_utc")
    completed_dt = _parse_utc(result_data.get("completed_utc"), "results.completed_utc")
    require_ok(
        started_dt <= completed_dt <= ended_dt,
        "RECEIPT_TIME_WINDOW",
        f"completed_utc {completed_dt} outside Zone-B execution window [{started_dt}, {ended_dt}]",
    )

    for phase in ("start_gpu_telemetry", "end_gpu_telemetry"):
        tel = rec.get(phase)
        require_ok(isinstance(tel, dict), "RECEIPT_TEL_OBJ", f"Missing {phase} in Zone-B receipt")
        require_ok(tel.get("compute_vram_mib") == 0, "RECEIPT_COMPUTE_VRAM", f"Non-zero compute_vram_mib in {phase}")
        cer = tel.get("clocks_event_reasons")
        require_ok(isinstance(cer, dict), "RECEIPT_CLOCKS_OBJ", f"Missing clocks_event_reasons in {phase}")
        require_ok(cer.get("thermal_throttled") is False, "RECEIPT_THERMAL_THROTTLE", f"Thermal throttle in {phase}")
        require_ok(cer.get("slowdown_active") is False, "RECEIPT_SLOWDOWN", f"Clock slowdown in {phase}")

    return {
        "receipt_file": ZONE_B_FILENAME,
        "receipt_file_sha256": _sha256_file(receipt_path),
        "receipt_sha256": receipt_sha,
        "bound_result_file": RESULTS_FILENAME,
        "bound_result_file_sha256": _sha256_file(track_dir / RESULTS_FILENAME),
        "bound_result_inner_sha256": str(result_data["result_sha256"]),
        "started_utc": str(exe["started_utc"]),
        "completed_utc": str(result_data["completed_utc"]),
        "ended_utc": str(exe["ended_utc"]),
        "duration_ms": _as_float(exe["duration_ms"], "zone_b.duration_ms"),
        "start_temp_c": _as_float(rec["start_gpu_telemetry"]["temperature_gpu_c"], "zone_b.start_temp_c"),
        "end_temp_c": _as_float(rec["end_gpu_telemetry"]["temperature_gpu_c"], "zone_b.end_temp_c"),
    }


def _verify_airlock_and_sampler(result_data: Mapping[str, Any]) -> Dict[str, Any]:
    air = result_data.get("sensor_airlock_audit")
    require_ok(isinstance(air, dict), "AIRLOCK_MISSING", "Missing sensor_airlock_audit block")
    require_ok(air.get("mode") == "telemetry-only", "AIRLOCK_MODE", "Mode must be telemetry-only")
    require_ok(air.get("dmic_authorized") is False, "AIRLOCK_DMIC", "dmic_authorized must be False in Mode 1")
    require_ok(air.get("camera_policy") == "ERR_CAMERA_FORBIDDEN", "AIRLOCK_CAMERA_POLICY", "Missing ERR_CAMERA_FORBIDDEN policy")
    require_ok(_as_int(air.get("checked_open_calls"), "checked_open_calls") > 0, "AIRLOCK_INACTIVE", "Runtime open spy checked 0 calls")
    for k in ("blocked_sensor_attempts", "camera_opens", "audio_opens", "ir_opens"):
        require_ok(_as_int(air.get(k), k) == 0, "AIRLOCK_BREACH", f"Non-zero {k} in sensor_airlock_audit")

    hw = result_data.get("hardware_sampler_info")
    require_ok(isinstance(hw, dict), "SAMPLER_INFO_MISSING", "Missing hardware_sampler_info")
    doms = hw.get("rapl_domains")
    require_ok(
        isinstance(doms, list) and tuple(sorted(str(x) for x in doms)) == EXPECTED_RAPL_DOMAINS,
        "RAPL_DOMAINS_MISMATCH",
        f"Expected all 4 intel-rapl domains {EXPECTED_RAPL_DOMAINS}, got {doms!r}",
    )
    require_ok(hw.get("nvml_ready") is True, "NVML_NOT_READY", "nvml_ready must be True")
    return {
        "mode": "telemetry-only",
        "checked_open_calls": int(air["checked_open_calls"]),
        "sensor_violations": 0,
        "rapl_domains": list(EXPECTED_RAPL_DOMAINS),
        "enforced_power_limit_w": _as_float(hw.get("enforced_power_limit_w"), "enforced_power_limit_w"),
    }


def _check_exact_q_ops(block: Mapping[str, Any], label: str) -> None:
    op1 = block.get("OP1_SEAM1")
    op2 = block.get("OP2_SEAM3")
    op3 = block.get("OP3_F3")
    require_ok(isinstance(op1, dict) and isinstance(op2, dict) and isinstance(op3, dict), "MISSING_EXACT_Q", f"Missing OP1/2/3 in {label}")
    q1 = Fraction(str(op1["max_leverage_exact_q"]))
    q2 = Fraction(str(op2["phi_asym_exact_q"]))
    q3 = Fraction(str(op3["kappa_f3_exact_q"]))
    require_ok(Fraction(0) <= q1 < Fraction(1), "OP1_BOUNDS", f"OP1 leverage {q1} outside [0, 1) in {label}")
    require_ok(Fraction(0) <= q2 <= Fraction(1), "OP2_BOUNDS", f"OP2 Hodge curl {q2} outside [0, 1] in {label}")
    require_ok(q3 >= Fraction(0), "OP3_BOUNDS", f"OP3 kappa_F3 {q3} < 0 in {label}")
    require_ok(isinstance(block.get("frame64_merkle_sha256"), str) and len(block["frame64_merkle_sha256"]) == 64, "FRAME64_HASH", f"Bad frame64 hash in {label}")


def _recompute_h15a(h15a: Mapping[str, Any], top_verdicts: Mapping[str, Any]) -> Dict[str, Any]:
    std_pairs = h15a.get("standard_pairs")
    eqw_pairs = h15a.get("equal_watt_pairs")
    require_ok(isinstance(std_pairs, list) and len(std_pairs) == 9, "H15A_STD_COUNT", "H15a must have 9 standard_pairs (3 seeds x 3 pairs)")
    require_ok(isinstance(eqw_pairs, list) and len(eqw_pairs) == 9, "H15A_EQW_COUNT", "H15a must have 9 equal_watt_pairs (3 seeds x 3 pairs)")

    seeds_seen = sorted({int(r["seed"]) for r in std_pairs})
    require_ok(tuple(seeds_seen) == EXPECTED_SEEDS, "H15A_SEEDS", f"H15a seeds mismatch: {seeds_seen}")

    eager_a3: List[float] = []
    fused_a3: List[float] = []
    eager_a7: List[float] = []
    fused_a7: List[float] = []
    any_sig = False

    for idx, row in enumerate(std_pairs):
        e = row["eager_h7b"]
        f = row["holosphere_v2_sm86"]
        tok_e = _as_int(e["tokens_processed"], f"h15a.std[{idx}].eager.tokens")
        tok_f = _as_int(f["tokens_processed"], f"h15a.std[{idx}].fused.tokens")
        require_ok(tok_e == tok_f and tok_e > 0, "H15A_CS08_TOKENS", f"Pair {idx} token mismatch: {tok_e} vs {tok_f}")
        require_ok(_as_float(e["A7_max_residual_lin_corr"], "e.lin_corr") <= A7_SCHUR_CORR_MAX, "H15A_SCHUR_E", "Eager A7 residual not orthogonal")
        require_ok(_as_float(f["A7_max_residual_lin_corr"], "f.lin_corr") <= A7_SCHUR_CORR_MAX, "H15A_SCHUR_F", "Fused A7 residual not orthogonal")
        _check_exact_q_ops(e, f"h15a.std[{idx}].eager")
        _check_exact_q_ops(f, f"h15a.std[{idx}].fused")
        if bool(e["any_non_textbook_sig_0p005"]) or bool(f["any_non_textbook_sig_0p005"]):
            any_sig = True
        eager_a3.append(_as_float(e["abs_A3"], f"h15a.std[{idx}].e.a3"))
        fused_a3.append(_as_float(f["abs_A3"], f"h15a.std[{idx}].f.a3"))
        eager_a7.append(_as_float(e["A7_copula_mi_nats"], f"h15a.std[{idx}].e.a7"))
        fused_a7.append(_as_float(f["A7_copula_mi_nats"], f"h15a.std[{idx}].f.a7"))

    eqw_e_a3: List[float] = []
    eqw_f_a3: List[float] = []
    eqw_e_a7: List[float] = []
    eqw_f_a7: List[float] = []
    max_eqw_diff = 0.0
    for idx, row in enumerate(eqw_pairs):
        e = row["eager_h7b_paced"]
        f = row["holosphere_v2_sm86"]
        we = _as_float(e["mean_gpu_power_w"], f"h15a.eqw[{idx}].we")
        wf = _as_float(f["mean_gpu_power_w"], f"h15a.eqw[{idx}].wf")
        require_ok(we > 0.0 and wf > 0.0, "H15A_EQW_POS", "GPU power must be > 0")
        rel_w = abs(we - wf) / wf
        if rel_w > max_eqw_diff:
            max_eqw_diff = rel_w
        eqw_e_a3.append(_as_float(e["abs_A3"], f"h15a.eqw[{idx}].e.a3"))
        eqw_f_a3.append(_as_float(f["abs_A3"], f"h15a.eqw[{idx}].f.a3"))
        eqw_e_a7.append(_as_float(e["A7_copula_mi_nats"], f"h15a.eqw[{idx}].e.a7"))
        eqw_f_a7.append(_as_float(f["A7_copula_mi_nats"], f"h15a.eqw[{idx}].f.a7"))

    st_a3 = recompute_paired_stats(eager_a3, fused_a3)
    st_a7 = recompute_paired_stats(eager_a7, fused_a7)
    eq_a3 = recompute_paired_stats(eqw_e_a3, eqw_f_a3)
    eq_a7 = recompute_paired_stats(eqw_e_a7, eqw_f_a7)

    graded_pure = grade_h15a_pure(
        any_sig_0p005=any_sig,
        a3_rel_pct=st_a3["rel_change_pct"],
        a3_z=st_a3["z_paired"],
        a7_rel_pct=st_a7["rel_change_pct"],
        a7_z=st_a7["z_paired"],
        max_eqw_rel_diff=max_eqw_diff,
        eqw_a3_z=eq_a3["z_paired"],
        eqw_a7_z=eq_a7["z_paired"],
    )

    rec_graded = h15a["graded"]
    for gk in ("criterion_1_non_gaussian_activity_0p005", "criterion_2_both_a3_and_a7_reduced_20pct", "criterion_3_equal_watt_non_confound"):
        require_ok(rec_graded.get(gk) is graded_pure[gk], "H15A_GATE_MISMATCH", f"H15a {gk} mismatch: {graded_pure[gk]} != {rec_graded.get(gk)}")
    require_ok(
        graded_pure["verdict"] == rec_graded.get("verdict") == top_verdicts.get("H15a"),
        "H15A_VERDICT_MISMATCH",
        f"H15a verdict mismatch: recomputed {graded_pure['verdict']} vs recorded {rec_graded.get('verdict')}",
    )
    return {
        "verdict": graded_pure["verdict"],
        "gates": {k: v for k, v in graded_pure.items() if k != "verdict"},
        "max_equal_watt_rel_diff": round(max_eqw_diff, 6),
        "standard_abs_A3": st_a3,
        "standard_A7_copula_mi": st_a7,
        "equal_watt_abs_A3": eq_a3,
        "equal_watt_A7_copula_mi": eq_a7,
    }


def _recompute_h15b(h15b: Mapping[str, Any], top_verdicts: Mapping[str, Any]) -> Dict[str, Any]:
    runs = h15b.get("runs")
    leads = h15b.get("lead_receipts")
    require_ok(isinstance(runs, list) and len(runs) == 12, "H15B_RUN_COUNT", "H15b must have 12 runs (4 arms x 3 seeds)")
    require_ok(isinstance(leads, list) and len(leads) == 3, "H15B_LEAD_COUNT", "H15b must have 3 lead_receipts")

    dbw = h15b.get("delay_bandwidth_lock")
    require_ok(isinstance(dbw, dict) and _as_float(dbw.get("f_tau_product"), "dbw.f_tau") < (1.0 / 6.0) and dbw.get("stable") is True, "H15B_DELAY_BW", "Delay-Bandwidth Lock f*tau < 1/6 failed")

    by_arm: Dict[str, List[Dict[str, Any]]] = {}
    by_seed: Dict[int, Dict[str, Dict[str, Any]]] = {}
    for row in runs:
        arm = str(row["arm"])
        sd = _as_int(row["seed"], "h15b.seed")
        by_arm.setdefault(arm, []).append(row)
        by_seed.setdefault(sd, {})[arm] = row
        g_min = _as_float(row["min_lyapunov_conductance_g"], f"h15b.{arm}.{sd}.g")
        require_ok(0.70 <= g_min <= 1.0, "H15B_LYAPUNOV_BOUNDS", f"Lyapunov conductance {g_min} out of bounds")

    require_ok(set(by_arm.keys()) == set(H15B_EXPECTED_ARMS), "H15B_ARMS", f"Unexpected H15b arms: {sorted(by_arm.keys())}")
    require_ok(tuple(sorted(by_seed.keys())) == EXPECTED_SEEDS, "H15B_SEEDS", f"Unexpected H15b seeds: {sorted(by_seed.keys())}")

    for sd, arm_map in by_seed.items():
        tok_set = {_as_int(r["tokens_total"], f"h15b.s{sd}.tok") for r in arm_map.values()}
        require_ok(len(tok_set) == 1 and next(iter(tok_set)) > 0, "H15B_CS08_TOKENS", f"H15b seed {sd} token mismatch: {tok_set}")
        # Verify Shuffled-Trigger-Control matches SiliSense-Precursor-Gov duty cycle identically!
        sili_r = arm_map["SiliSense-Precursor-Gov"]
        shuf_r = arm_map["Shuffled-Trigger-Control"]
        require_ok(
            _as_int(sili_r["damped_steps_count"], "sili.damped") == _as_int(shuf_r["damped_steps_count"], "shuf.damped")
            and abs(_as_float(sili_r["total_cooldown_ms"], "sili.cd") - _as_float(shuf_r["total_cooldown_ms"], "shuf.cd")) <= 1e-2,
            "H15B_SHUFFLED_DUTY_MISMATCH",
            f"Shuffled control duty-cycle mismatch at seed {sd}",
        )

    def _vec(arm_name: str, field: str) -> List[float]:
        rs = sorted(by_arm[arm_name], key=lambda r: int(r["seed"]))
        return [_as_float(r[field], f"h15b.{arm_name}.{field}") for r in rs]

    lead_lags = sorted(_as_float(r["peak_precursor_lag_ms"], "lead.lag") for r in leads)
    med_lead = lead_lags[len(lead_lags) // 2]
    max_p_circ = max(_as_float(r["p_circ"], "lead.p_circ") for r in leads)

    st_no = recompute_paired_stats(_vec("NoGovernor", "stall_frac"), _vec("SiliSense-Precursor-Gov", "stall_frac"))
    st_smi = recompute_paired_stats(_vec("Reactive-1Hz-SMI", "stall_frac"), _vec("SiliSense-Precursor-Gov", "stall_frac"))
    st_shuf = recompute_paired_stats(_vec("Shuffled-Trigger-Control", "stall_frac"), _vec("SiliSense-Precursor-Gov", "stall_frac"))

    cv_no = recompute_paired_stats(_vec("NoGovernor", "mj_per_tok_cv"), _vec("SiliSense-Precursor-Gov", "mj_per_tok_cv"))
    cv_smi = recompute_paired_stats(_vec("Reactive-1Hz-SMI", "mj_per_tok_cv"), _vec("SiliSense-Precursor-Gov", "mj_per_tok_cv"))
    cv_shuf = recompute_paired_stats(_vec("Shuffled-Trigger-Control", "mj_per_tok_cv"), _vec("SiliSense-Precursor-Gov", "mj_per_tok_cv"))
    tps_no = recompute_paired_stats(_vec("NoGovernor", "tok_per_s"), _vec("SiliSense-Precursor-Gov", "tok_per_s"))

    graded_pure = grade_h15b_pure(
        med_lead_ms=med_lead,
        max_p_circ=max_p_circ,
        stall_no_rel=st_no["rel_change_pct"],
        stall_no_z=st_no["z_paired"],
        stall_smi_rel=st_smi["rel_change_pct"],
        stall_smi_z=st_smi["z_paired"],
        stall_shuf_z=st_shuf["z_paired"],
        cv_no_rel=cv_no["rel_change_pct"],
        cv_no_z=cv_no["z_paired"],
        cv_smi_rel=cv_smi["rel_change_pct"],
        cv_smi_z=cv_smi["z_paired"],
        cv_shuf_z=cv_shuf["z_paired"],
        tps_no_rel=tps_no["rel_change_pct"],
    )
    rec_graded = h15b["graded"]
    for gk in ("criterion_1_precursor_lead", "criterion_2_closed_loop_stability"):
        require_ok(rec_graded.get(gk) is graded_pure[gk], "H15B_GATE_MISMATCH", f"H15b {gk} mismatch")
    require_ok(
        graded_pure["verdict"] == rec_graded.get("verdict") == top_verdicts.get("H15b"),
        "H15B_VERDICT_MISMATCH",
        f"H15b verdict mismatch: recomputed {graded_pure['verdict']} vs recorded {rec_graded.get('verdict')}",
    )
    return {
        "verdict": graded_pure["verdict"],
        "gates": {k: v for k, v in graded_pure.items() if k != "verdict"},
        "median_peak_precursor_lead_ms": round(med_lead, 4),
        "max_p_circ": round(max_p_circ, 6),
        "stall_vs_NoGovernor": st_no,
        "stall_vs_Reactive_1Hz_SMI": st_smi,
        "stall_vs_Shuffled_Trigger_Control": st_shuf,
        "mj_cv_vs_NoGovernor": cv_no,
        "mj_cv_vs_Reactive_1Hz_SMI": cv_smi,
        "mj_cv_vs_Shuffled_Trigger_Control": cv_shuf,
        "throughput_vs_NoGovernor": tps_no,
    }


def _recompute_h15c(h15c: Mapping[str, Any], top_verdicts: Mapping[str, Any]) -> Dict[str, Any]:
    cal_by_seed = h15c.get("calibration_by_seed")
    sus_runs = h15c.get("sustained_runs")
    require_ok(isinstance(cal_by_seed, dict) and len(cal_by_seed) == 3, "H15C_CAL_SEEDS", "H15c must have 3 calibration seeds")
    require_ok(isinstance(sus_runs, list) and len(sus_runs) == 9, "H15C_SUS_COUNT", "H15c must have 9 sustained_runs (3 tuners x 3 seeds)")

    # Recompute J(theta) winner selections from raw calibration candidates per seed
    verified_selections: Dict[str, Dict[str, str]] = {}
    for sd in EXPECTED_SEEDS:
        block = cal_by_seed.get(str(sd))
        require_ok(isinstance(block, dict), "H15C_SEED_MISSING", f"Missing calibration for seed {sd}")
        cands = block.get("candidates")
        require_ok(isinstance(cands, list) and len(cands) == 6, "H15C_CAND_COUNT", f"Seed {sd} must have 6 candidate configs")
        for c in cands:
            require_ok(
                _as_int(c.get("effective_tokens_per_step"), "eff_tok") == H15C_CS08_EFF_TOKENS,
                "H15C_CS08_CAL",
                f"CS-08 effective_tokens_per_step != {H15C_CS08_EFF_TOKENS}",
            )
        min_edp = min(_as_float(c["edp"], "cal.edp") for c in cands)
        require_ok(min_edp > 0.0, "H15C_EDP_POS", "Calibration EDP must be > 0")
        j_scores: List[Tuple[float, str]] = []
        for c in cands:
            cid = str(c["config_id"])
            edp_v = _as_float(c["edp"], f"{cid}.edp")
            za3 = abs(_as_float(c["z_a3"], f"{cid}.za3"))
            za7 = _as_float(c["z_a7"], f"{cid}.za7")
            prec = _as_float(c["a5_precursor_rate"], f"{cid}.prec")
            j_val = (
                (edp_v / min_edp)
                + LOCKED_LAMBDA_A3 * max(0.0, za3 - LOCKED_HINGE_Z)
                + LOCKED_LAMBDA_A7 * max(0.0, za7 - LOCKED_HINGE_Z)
                + LOCKED_LAMBDA_A5 * prec
            )
            j_scores.append((j_val, cid))

        win_tps = max(cands, key=lambda r: _as_float(r["tok_per_s"], "cal.tps"))["config_id"]
        win_edp0 = min(cands, key=lambda r: _as_float(r["edp"], "cal.edp"))["config_id"]
        win_sili = min(j_scores, key=lambda t: t[0])[1]
        rec_sel = block["selection"]
        require_ok(
            rec_sel.get("Scalar-TokPerSec-Tuner") == win_tps
            and rec_sel.get("Scalar-MeanWatt-EDP-Tuner") == win_edp0
            and rec_sel.get("SiliSense-Composite-Tuner") == win_sili,
            "H15C_SELECTION_MISMATCH",
            f"Seed {sd} selection mismatch",
        )
        verified_selections[str(sd)] = {
            "Scalar-TokPerSec-Tuner": str(win_tps),
            "Scalar-MeanWatt-EDP-Tuner": str(win_edp0),
            "SiliSense-Composite-Tuner": str(win_sili),
        }

    by_tuner: Dict[str, List[Dict[str, Any]]] = {}
    for row in sus_runs:
        require_ok(
            _as_int(row.get("effective_tokens_per_step"), "sus.eff_tok") == H15C_CS08_EFF_TOKENS,
            "H15C_CS08_SUS",
            "Sustained run violated CS-08 effective_tokens_per_step",
        )
        t_arm = str(row["tuner_arm"])
        sd = _as_int(row["seed"], "sus.seed")
        require_ok(t_arm in H15C_EXPECTED_TUNERS, "H15C_TUNERS", f"Unexpected H15c tuner arm: {t_arm!r}")
        require_ok(str(sd) in verified_selections, "H15C_SUS_SEEDS", f"Unexpected H15c sustained seed: {sd}")
        require_ok(
            str(row["selected_config_id"]) == verified_selections[str(sd)][t_arm],
            "H15C_SUS_CONFIG_BIND",
            f"Sustained run {t_arm} seed {sd} config mismatch vs calibration winner",
        )
        by_tuner.setdefault(t_arm, []).append(row)

    require_ok(set(by_tuner.keys()) == set(H15C_EXPECTED_TUNERS), "H15C_TUNERS", "Unexpected H15c tuner arms")

    def _sus_vec(t_arm: str, field: str) -> List[float]:
        rs = sorted(by_tuner[t_arm], key=lambda r: int(r["seed"]))
        require_ok(tuple(int(r["seed"]) for r in rs) == EXPECTED_SEEDS, "H15C_SUS_SEEDS", f"Seed mismatch for {t_arm}")
        return [_as_float(r[field], f"h15c.{t_arm}.{field}") for r in rs]

    vs_tps = recompute_paired_stats(_sus_vec("Scalar-TokPerSec-Tuner", "edp"), _sus_vec("SiliSense-Composite-Tuner", "edp"))
    vs_edp0 = recompute_paired_stats(_sus_vec("Scalar-MeanWatt-EDP-Tuner", "edp"), _sus_vec("SiliSense-Composite-Tuner", "edp"))
    drift_vs = recompute_paired_stats(_sus_vec("Scalar-MeanWatt-EDP-Tuner", "tail_edp_drift"), _sus_vec("SiliSense-Composite-Tuner", "tail_edp_drift"))

    graded_pure = grade_h15c_pure(
        vs_tps_rel=vs_tps["rel_change_pct"],
        vs_tps_z=vs_tps["z_paired"],
        vs_edp0_rel=vs_edp0["rel_change_pct"],
        vs_edp0_z=vs_edp0["z_paired"],
        drift_vs_edp0_rel=drift_vs["rel_change_pct"],
        drift_vs_edp0_z=drift_vs["z_paired"],
    )
    rec_graded = h15c["graded"]
    for gk in ("criterion_1_edp_vs_scalar_tps", "criterion_2_edp_or_drift_vs_mean_watt"):
        require_ok(rec_graded.get(gk) is graded_pure[gk], "H15C_GATE_MISMATCH", f"H15c {gk} mismatch")
    require_ok(
        graded_pure["verdict"] == rec_graded.get("verdict") == top_verdicts.get("H15c"),
        "H15C_VERDICT_MISMATCH",
        f"H15c verdict mismatch: recomputed {graded_pure['verdict']} vs recorded {rec_graded.get('verdict')}",
    )
    return {
        "verdict": graded_pure["verdict"],
        "gates": {k: v for k, v in graded_pure.items() if k != "verdict"},
        "selected_configs_by_seed": verified_selections,
        "sustained_edp_vs_Scalar_TokPerSec": vs_tps,
        "sustained_edp_vs_Scalar_MeanWatt_EDP": vs_edp0,
        "tail_edp_drift_vs_Scalar_MeanWatt_EDP": drift_vs,
    }


def build_certificate(track_dir: Path) -> Dict[str, Any]:
    """Audit all Track S115 Mode-1 evidence on disk and return a canonical self-hashed certificate."""
    hygiene = _check_directory_hygiene(track_dir)

    prereg_path = _resolve_prereg_path(track_dir)
    require_ok(prereg_path is not None, "MISSING_PREREG", f"Missing {PREREG_FILENAME} in track bundle or notes")
    prereg_sha = _sha256_file(prereg_path)  # type: ignore[arg-type]
    require_ok(prereg_sha == PREREG_SHA256, "PREREG_SHA_MISMATCH", f"PREREG SHA mismatch: {prereg_sha}")

    results_path = track_dir / RESULTS_FILENAME
    result_data = _load_json_dict(results_path)
    _verify_inner_hash(result_data, "result_sha256", RESULTS_FILENAME)
    require_ok(
        result_data.get("preregistration_sha256") == PREREG_SHA256,
        "RESULT_PREREG_SHA",
        "results preregistration_sha256 mismatch",
    )

    zone_b = _verify_zone_b_receipt(track_dir, result_data)
    airlock = _verify_airlock_and_sampler(result_data)

    report_path = track_dir / REPORT_FILENAME
    report_sha = _sha256_file(report_path)
    report_txt = report_path.read_text(encoding="utf-8")
    require_ok(PREREG_SHA256 in report_txt, "REPORT_PREREG_REF", f"{REPORT_FILENAME} must cite PREREG SHA-256")
    require_ok(zone_b["receipt_sha256"] in report_txt, "REPORT_ZONEB_REF", f"{REPORT_FILENAME} must cite Zone-B receipt_sha256")

    top_verdicts = result_data.get("verdicts")
    require_ok(isinstance(top_verdicts, dict), "MISSING_VERDICTS", "Missing verdicts object in results JSON")

    h15a_cert = _recompute_h15a(result_data["h15a"], top_verdicts)
    h15b_cert = _recompute_h15b(result_data["h15b"], top_verdicts)
    h15c_cert = _recompute_h15c(result_data["h15c"], top_verdicts)

    cert: Dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "track": "S115",
        "novelty_classification": "N1",
        "n2_claims": 0,
        "preregistration_sha256": PREREG_SHA256,
        "prereg_verified": True,
        "report_file": REPORT_FILENAME,
        "report_sha256": report_sha,
        "hygiene": hygiene,
        "sensor_airlock": airlock,
        "zone_b_provenance": zone_b,
        "verdicts": {
            "H15a": h15a_cert["verdict"],
            "H15b": h15b_cert["verdict"],
            "H15c": h15c_cert["verdict"],
        },
        "h15a": h15a_cert,
        "h15b": h15b_cert,
        "h15c": h15c_cert,
    }
    cert["cert_sha256"] = _sha256_bytes(_canonical_bytes(cert))
    return cert


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Track S115 SiliSense Pure-Stdlib Audit & Certificate Verifier")
    parser.add_argument("--track-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--write", action="store_true", help=f"Write {CERT_FILENAME} in track directory")
    parser.add_argument("--standalone", action="store_true", help="Recompute certificate to stdout without writing")
    parser.add_argument("--json", action="store_true", help="Format output as canonical JSON")
    parser.add_argument("--check", nargs="?", const=CERT_FILENAME, default=None, help="Verify on-disk certificate matches fresh audit")
    args = parser.parse_args(argv)

    try:
        modes_active = int(bool(args.write)) + int(args.check is not None) + int(bool(args.standalone))
        require_ok(modes_active <= 1, "CLI_MUTUAL_EXCLUSION", "Choose at most one of --write, --check, --standalone")
        fresh = build_certificate(args.track_dir)
        fresh_bytes = json.dumps(fresh, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"

        if args.write:
            out_p = args.track_dir / CERT_FILENAME
            out_p.write_bytes(fresh_bytes)
            sys.stdout.write(json.dumps({"status": "WRITTEN", "cert_sha256": fresh["cert_sha256"], "verdicts": fresh["verdicts"]}, sort_keys=True) + "\n")
            return 0

        if args.check is not None:
            chk_p = Path(args.check)
            if not chk_p.is_absolute():
                chk_p = args.track_dir / chk_p
            on_disk = _load_json_dict(chk_p)
            _verify_inner_hash(on_disk, "cert_sha256", chk_p.name)
            require_ok(on_disk == fresh, "CERT_DRIFT", f"On-disk {chk_p.name} differs from recomputed audit certificate")
            sys.stdout.write(json.dumps({"status": "PASS", "cert_sha256": fresh["cert_sha256"], "verdicts": fresh["verdicts"]}, sort_keys=True) + "\n")
            return 0

        if args.standalone or args.json:
            sys.stdout.write(fresh_bytes.decode("ascii"))
            return 0

        sys.stdout.write(json.dumps({"status": "PASS", "cert_sha256": fresh["cert_sha256"], "verdicts": fresh["verdicts"]}, sort_keys=True) + "\n")
        return 0
    except S115AuditError as exc:
        sys.stderr.write(f"S115_AUDIT_FAIL {exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
