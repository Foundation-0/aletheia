#!/usr/bin/env python3
"""Track S114 (`HoloSphere` / `SiliSphere`) Pure-Stdlib Audit & Certificate Verifier.

Strictly Python standard library only (zero torch/numpy/third-party imports).
Zero bare asserts. Zero hardcoded verdict literals: H14a, H14b, and H14c verdicts
are recomputed from raw numerical evidence, paired statistics, V1 (9/9) + V2 (27/27)
ptxas zero-spill receipts, fail-closed PREREG SHA-256 verification, and Ring-0
mlos Zone-B hardware telemetry receipts.

Note on Zone-B receipts: mlos receipt_sha256 is an unkeyed SHA-256 integrity
self-hash (detecting accidental edits/truncation, not adversarial forgery). Each
receipt is cross-checked for distinct hashes, clean telemetry, and UTC window
containment (started_utc <= completed_utc <= ended_utc).

Usage:
    python3 -I -B s114_holosphere_audit.py --write
    python3 -I -B s114_holosphere_audit.py --standalone --json
    python3 -I -B s114_holosphere_audit.py --check [s114_holosphere_certificate.json]
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

SCHEMA_VERSION = "holosphere.track_s114.audit_certificate.v2"
CERT_FILENAME = "s114_holosphere_certificate.json"
PREREG_FILENAME = "PREREG_S114_SILISPHERE_FUSED_ENTITY.md"
PREREG_SHA256 = "5fa927a06933c3cff057b65f75c1d2f190e10f1e420303d582dfb7c802ee69a4"
AMENDMENT1_FILENAME = "PREREG_S114_AMENDMENT1_S107_S108_CONVERGENCE.md"
AMENDMENT1_SHA256 = "b661b54359dacd455813f4d83e6547e0a89036afb6d527566c2a97f905e89a12"
REPORT_FILENAME = "REPORT_S114_HOLOSPHERE_GPU_EVAL.md"
PTXAS_V1_FILENAME = "ptxas_sm86_zero_spill_receipt_v1.json"
PTXAS_V2_FILENAME = "ptxas_sm86_zero_spill_receipt.json"
CU_FILENAME = "su2_holonomy_scan_sm86.cu"

GENERATOR_SCRIPTS: Tuple[str, ...] = (
    "s114_fused_ops.py",
    "su2_holonomy_triton.py",
    "s114_h14a_gpu_bench.py",
    "s114_v2_zero_permute_cayley_bench.py",
    "s114_h14bc_gpu_train_eval.py",
)

EXPECTED_SEEDS = (42, 137, 2026)
H14B_PREREG_CANDIDATES = (
    "HoloSphere-V2-SU2-Unlooped",
    "HoloSphere-V2-Full-Entity",
)
H14B_EXPECTED_ARMS = (
    "RoPE-2D-Std",
    "RoPE-2D-nGPT",
    "RoPE-2D-nGPT+MarkovMTP8",
    "HoloSphere-V2-SU2-Unlooped",
    "HoloSphere-V2-CayleySU2-Unlooped",
    "HoloSphere-V2-Stage1a-Cayley2x2",
    "HoloSphere-V2-Full-Entity",
)
H14C_EXPECTED_ARMS = (
    "RoPE-2D-nGPT",
    "Abelian-SO2-Phase",
    "H7b-QK-Only",
    "HoloSphere-V2-QKV-NoUntransport",
    "HoloSphere-V2-Full-Covariant-QKV-Untransport",
)

# Locked PREREG-S114 numerical thresholds
FP32_MAX_ABS = 1e-4
BF16_MAX_ABS = 5e-3
NORM_DRIFT_MAX = 1e-5
BELTRAMI_DRIFT_MAX = 1e-6
H14A_MAX_VS_ROPE = 1.15
H14A_MIN_VS_EAGER = 3.40
H14A_PARTIAL_VS_EAGER = 2.00
H14A_MIN_MICRO_SPEEDUP = 5.0
H14B_REL_PCT_MAX = -5.0
H14B_Z_MAX = -2.0
H14B_T512_REG_MAX = 0.5
H14B_MJ_RATIO_MAX = 1.15
H14B_BUDGET_SLACK_S = 1.0
H14C_S3_FLOOR = 50.0
H14C_S3_MARGIN = 15.0
H14C_A5_FLOOR = 15.0
H14C_A5_MARGIN = 8.0
H14C_Z_MIN = 2.0
PARAM_DELTA_MAX = 0.005
MAX_JSON_BYTES = 16 * 1024 * 1024

WEIGHT_SUFFIXES = frozenset({".pt", ".pth", ".ckpt", ".safetensors", ".bin", ".gguf", ".onnx"})
ELF_SUFFIXES = frozenset({".so", ".o", ".a"})
ELF_MAGIC = b"\x7fELF"

ZONE_B_BINDINGS: Tuple[Tuple[str, str, str], ...] = (
    ("h14a", "mlos_zone_b_s114_h14a.json", "s114_h14a_gpu_results.json"),
    ("v2", "mlos_zone_b_s114_v2.json", "s114_v2_gpu_results.json"),
    ("h14bc", "mlos_zone_b_s114_h14bc.json", "s114_h14bc_gpu_results.json"),
)


class S114AuditError(ValueError):
    """Typed fail-closed audit violation."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.detail = message
        super().__init__(f"[{code}] {message}")


def require_ok(cond: bool, code: str, message: str) -> None:
    if not cond:
        raise S114AuditError(code, message)


def _canonical_bytes(obj: Any) -> bytes:
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise S114AuditError("NON_CANONICAL_JSON", f"Non-canonical or NaN/Inf JSON value: {exc}") from exc


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    require_ok(path.is_file(), "MISSING_FILE", f"Required artifact missing: {path.name}")
    return _sha256_bytes(path.read_bytes())


def _load_json_dict(path: Path) -> Dict[str, Any]:
    require_ok(path.is_file(), "MISSING_JSON", f"Missing JSON artifact: {path.name}")
    require_ok(path.stat().st_size <= MAX_JSON_BYTES, "JSON_TOO_LARGE", f"JSON artifact exceeds size cap: {path.name}")
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise S114AuditError("MALFORMED_JSON", f"Malformed JSON in {path.name}: {exc}") from exc
    require_ok(isinstance(obj, dict), "SCHEMA_ROOT", f"JSON root must be an object in {path.name}")
    return obj


def _parse_utc(raw: Any, label: str) -> datetime.datetime:
    require_ok(isinstance(raw, str), "BAD_TIMESTAMP", f"Invalid UTC timestamp for {label}")
    try:
        dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise S114AuditError("BAD_TIMESTAMP", f"Unparseable UTC timestamp for {label}: {raw}") from exc
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
    require_ok(type(val) is int, "BAD_INT", f"Expected exact int (not bool/float/str) for {label}")
    return val


def _verify_inner_hash(obj: Mapping[str, Any], field_name: str, label: str) -> str:
    recorded = obj.get(field_name)
    require_ok(isinstance(recorded, str) and len(recorded) == 64, "MISSING_INNER_HASH", f"Missing {field_name} in {label}")
    body = {k: v for k, v in obj.items() if k != field_name}
    recomputed = _sha256_bytes(_canonical_bytes(body))
    require_ok(recomputed == recorded, "INNER_HASH_MISMATCH", f"{label} {field_name} mismatch: {recomputed} != {recorded}")
    return recomputed


def _paired_stats(a_vals: Sequence[float], b_vals: Sequence[float]) -> Dict[str, float]:
    n = len(a_vals)
    require_ok(n == len(b_vals) and n >= 2, "PAIRED_LEN", "Paired vectors must have equal length >= 2")
    diffs = [float(a - b) for a, b in zip(a_vals, b_vals)]
    mean_a = sum(a_vals) / float(n)
    mean_b = sum(b_vals) / float(n)
    mean_d = sum(diffs) / float(n)
    require_ok(abs(mean_b) > 1e-12, "ZERO_BASELINE", "Baseline mean is zero in paired comparison")
    rel_pct = 100.0 * mean_d / mean_b
    var = sum((d - mean_d) ** 2 for d in diffs) / float(n - 1)
    se = math.sqrt(var / float(n))
    t_stat = (mean_d / se) if se > 1e-12 else (0.0 if abs(mean_d) < 1e-12 else math.copysign(99.0, mean_d))
    p_norm = math.erfc(abs(t_stat) / math.sqrt(2.0))
    p_t = max(0.0, min(1.0, 1.0 - abs(t_stat) / math.sqrt(2.0 + t_stat * t_stat))) if n == 3 else p_norm
    return {
        "mean_a": round(mean_a, 6),
        "mean_b": round(mean_b, 6),
        "mean_diff": round(mean_d, 6),
        "rel_pct": round(rel_pct, 4),
        "se": round(se, 6),
        "z_or_t": round(t_stat, 4),
        "p_normal_2s": round(p_norm, 6),
        "p_t_df2_2s": round(p_t, 6),
    }


def grade_h14a(
    *,
    c1_zero_spill: bool,
    c2_parity: bool,
    cuda_vs_rope: float,
    cuda_speedup_vs_eager: float,
    micro_512_speedup: float,
    micro_2048_speedup: float,
) -> Dict[str, Any]:
    """Pure PREREG-S114 H14a grading function (zero hardcoded outcome)."""
    c3_e2e = (cuda_vs_rope <= H14A_MAX_VS_ROPE) and (cuda_speedup_vs_eager >= H14A_MIN_VS_EAGER)
    c4_micro = (micro_512_speedup >= H14A_MIN_MICRO_SPEEDUP) and (micro_2048_speedup >= H14A_MIN_MICRO_SPEEDUP)
    if c1_zero_spill and c2_parity and c3_e2e and c4_micro:
        verdict = "CONFIRMED"
    elif c1_zero_spill and c2_parity and c4_micro and (cuda_speedup_vs_eager >= H14A_PARTIAL_VS_EAGER):
        verdict = "PARTIAL"
    else:
        verdict = "FALSIFIED"
    return {
        "c1_zero_spill": c1_zero_spill,
        "c2_parity": c2_parity,
        "c3_e2e_le_115x_and_ge_340x": c3_e2e,
        "c4_microbench_ge_5x": c4_micro,
        "verdict": verdict,
    }


def grade_h14b_arm(
    *,
    rel_pct_2048_vs_ngpt: float,
    z_2048_vs_ngpt: float,
    rel_pct_2048_vs_std: float,
    z_2048_vs_std: float,
    rel_pct_512_vs_ngpt: float,
    mj_ratio_512: float,
    mj_ratio_2048: float,
) -> Dict[str, bool]:
    """Pure PREREG-S114 H14b per-arm gate evaluation."""
    c1 = (
        (rel_pct_2048_vs_ngpt <= H14B_REL_PCT_MAX)
        and (z_2048_vs_ngpt <= H14B_Z_MAX)
        and (rel_pct_2048_vs_std <= H14B_REL_PCT_MAX)
        and (z_2048_vs_std <= H14B_Z_MAX)
    )
    c2 = rel_pct_512_vs_ngpt <= H14B_T512_REG_MAX
    c3 = (mj_ratio_512 <= H14B_MJ_RATIO_MAX) and (mj_ratio_2048 <= H14B_MJ_RATIO_MAX)
    return {
        "c1_t2048_ge_5pct_z_le_m2": c1,
        "c2_t512_non_regression": c2,
        "c3_mj_le_115x": c3,
    }


def grade_h14b_campaign(arm_gates: Mapping[str, Mapping[str, bool]]) -> str:
    """Pure PREREG-S114 H14b campaign verdict derived solely from per-arm gate booleans."""
    any_confirmed = any(
        g["c1_t2048_ge_5pct_z_le_m2"] and g["c2_t512_non_regression"] and g["c3_mj_le_115x"]
        for g in arm_gates.values()
    )
    any_partial = any(g["c1_t2048_ge_5pct_z_le_m2"] for g in arm_gates.values())
    if any_confirmed:
        return "CONFIRMED"
    if any_partial:
        return "PARTIAL"
    return "FALSIFIED"


def grade_h14c_group(
    *,
    ood_acc_mean: float,
    acc_floor: float,
    margin_pp: float,
    diff_vs_rope: float,
    z_vs_rope: float,
    diff_vs_qk: float,
    z_vs_qk: float,
) -> bool:
    """Pure PREREG-S114 H14c per-group gate evaluation."""
    return (
        (ood_acc_mean >= acc_floor)
        and (diff_vs_rope >= margin_pp)
        and (z_vs_rope >= H14C_Z_MIN)
        and (diff_vs_qk >= margin_pp)
        and (z_vs_qk >= H14C_Z_MIN)
    )


def grade_h14c_campaign(s3_pass: bool, a5_pass: bool) -> str:
    """Pure PREREG-S114 H14c campaign verdict derived solely from group gate booleans."""
    if s3_pass and a5_pass:
        return "CONFIRMED"
    if s3_pass or a5_pass:
        return "PARTIAL"
    return "FALSIFIED"


def _check_directory_hygiene(track_dir: Path) -> Dict[str, int]:
    weights = 0
    elfs = 0
    symlinks = 0
    for p in sorted(track_dir.rglob("*")):
        if p.is_symlink():
            symlinks += 1
            continue
        if not p.is_file():
            continue
        suf = p.suffix.lower()
        if suf in WEIGHT_SUFFIXES:
            weights += 1
        is_elf = suf in ELF_SUFFIXES
        if not is_elf:
            with p.open("rb") as fh:
                if fh.read(4) == ELF_MAGIC:
                    is_elf = True
        if is_elf:
            elfs += 1
    require_ok(symlinks == 0, "HYGIENE_SYMLINK", f"Found {symlinks} symlinks in track directory (SYMLINKS=0 required)")
    require_ok(weights == 0, "HYGIENE_WEIGHTS", f"Found {weights} weight files in track directory (WEIGHTS=0 required)")
    require_ok(elfs == 0, "HYGIENE_ELF", f"Found {elfs} ELF/shared-object binaries in track directory (ELF=0 required)")
    return {"symlinks_count": symlinks, "weights_count": weights, "elf_count": elfs}


def _verify_ptxas_receipt(
    track_dir: Path,
    filename: str,
    *,
    expected_kernels: int,
    expected_cu_sha: Optional[str],
    v1_schema: bool,
) -> Dict[str, Any]:
    ptxas = _load_json_dict(track_dir / filename)
    require_ok(ptxas.get("arch") == "sm_86", "PTXAS_ARCH", f"{filename} arch must be sm_86")
    cu_sha = ptxas.get("cu_sha256")
    require_ok(isinstance(cu_sha, str) and len(cu_sha) == 64, "PTXAS_CU_SHA", f"{filename} missing 64-hex cu_sha256")
    if expected_cu_sha is not None:
        require_ok(cu_sha == expected_cu_sha, "PTXAS_CU_SHA", f"{filename} cu_sha256 does not match {CU_FILENAME}")

    kernels = ptxas.get("kernels")
    require_ok(
        isinstance(kernels, list) and len(kernels) == expected_kernels,
        "PTXAS_KERNEL_COUNT",
        f"{filename} must list exactly {expected_kernels} kernels",
    )
    require_ok(
        _as_int(ptxas.get("total_kernels"), f"{filename}.total_kernels") == len(kernels),
        "PTXAS_TOTAL_MISMATCH",
        f"{filename} total_kernels != len(kernels)",
    )
    require_ok(
        _as_int(ptxas.get("nonzero_spill_kernels"), f"{filename}.nonzero_spill_kernels") == 0,
        "PTXAS_NONZERO_SPILL",
        f"{filename} nonzero_spill_kernels must be 0",
    )

    sym_key = "mangled_name" if v1_schema else "symbol"
    stack_key = "stack_bytes" if v1_schema else "stack_frame_bytes"
    store_key = "spill_stores" if v1_schema else "spill_store_bytes"
    load_key = "spill_loads" if v1_schema else "spill_load_bytes"

    seen_syms: set[str] = set()
    max_regs = 0
    for idx, k in enumerate(kernels):
        require_ok(isinstance(k, dict), "PTXAS_KERNEL_ENTRY", f"{filename} kernel[{idx}] must be a dict")
        sym = k.get(sym_key)
        require_ok(isinstance(sym, str) and len(sym) > 0, "PTXAS_KERNEL_SYMBOL", f"{filename} kernel[{idx}] missing symbol")
        seen_syms.add(sym)
        stack_b = _as_int(k.get(stack_key), f"{filename}.k{idx}.stack")
        store_b = _as_int(k.get(store_key), f"{filename}.k{idx}.store")
        load_b = _as_int(k.get(load_key), f"{filename}.k{idx}.load")
        zero_flag = True if v1_schema else (k.get("zero_spill") is True)
        require_ok(
            stack_b == 0 and store_b == 0 and load_b == 0 and zero_flag,
            "PTXAS_KERNEL_SPILL",
            f"Kernel spill detected in {filename}:{sym}",
        )
        regs = _as_int(k.get("registers"), f"{filename}.k{idx}.regs")
        if regs > max_regs:
            max_regs = regs

    require_ok(len(seen_syms) == len(kernels), "PTXAS_DUP_SYMBOL", f"{filename} contains duplicate kernel symbols")
    require_ok(
        _as_int(ptxas.get("zero_spill_kernels"), f"{filename}.zero_spill_kernels") == len(kernels),
        "PTXAS_ZERO_COUNT",
        f"{filename} zero_spill_kernels mismatch",
    )
    return {
        "receipt_file": filename,
        "cu_sha256": cu_sha,
        "total_kernels": len(kernels),
        "zero_spill_kernels": len(kernels),
        "nonzero_spill_kernels": 0,
        "max_registers": max_regs,
    }


def _verify_zone_b_receipt(
    track_dir: Path,
    receipt_name: str,
    result_name: str,
    result_data: Mapping[str, Any],
) -> Dict[str, Any]:
    receipt_path = track_dir / receipt_name
    rec = _load_json_dict(receipt_path)
    receipt_sha = _verify_inner_hash(rec, "receipt_sha256", receipt_name)
    require_ok(rec.get("schema") == "mlos-run-receipt/v0.1", "RECEIPT_SCHEMA", f"Bad receipt schema in {receipt_name}")
    require_ok(rec.get("determinism_zone") == "B", "RECEIPT_ZONE", f"Receipt {receipt_name} must be Zone B")
    require_ok(rec.get("clean_hardware_run") is True, "RECEIPT_UNCLEAN", f"Receipt {receipt_name} clean_hardware_run is not True")
    require_ok(rec.get("anomalies") == [], "RECEIPT_ANOMALIES", f"Receipt {receipt_name} has non-empty anomalies")
    require_ok(rec.get("gpu_telemetry_available") is True, "RECEIPT_NO_GPU_TEL", f"Receipt {receipt_name} missing GPU telemetry")

    exe = rec.get("execution")
    require_ok(isinstance(exe, dict), "RECEIPT_EXE_OBJ", f"Missing execution block in {receipt_name}")
    require_ok(_as_int(exe.get("exit_code"), f"{receipt_name}.exit_code") == 0, "RECEIPT_EXIT_CODE", f"Non-zero exit_code in {receipt_name}")
    started_dt = _parse_utc(exe.get("started_utc"), f"{receipt_name}.started_utc")
    ended_dt = _parse_utc(exe.get("ended_utc"), f"{receipt_name}.ended_utc")
    completed_dt = _parse_utc(result_data.get("completed_utc"), f"{result_name}.completed_utc")
    require_ok(
        started_dt <= completed_dt <= ended_dt,
        "RECEIPT_TIME_WINDOW",
        f"{result_name} completed_utc outside {receipt_name} execution window",
    )

    for phase in ("start_gpu_telemetry", "end_gpu_telemetry"):
        tel = rec.get(phase)
        require_ok(isinstance(tel, dict), "RECEIPT_TEL_OBJ", f"Missing {phase} in {receipt_name}")
        require_ok(
            _as_int(tel.get("compute_vram_mib"), f"{receipt_name}.{phase}.compute_vram_mib") == 0,
            "RECEIPT_COMPUTE_VRAM",
            f"Non-zero compute_vram_mib in {receipt_name}.{phase}",
        )
        cer = tel.get("clocks_event_reasons")
        require_ok(isinstance(cer, dict), "RECEIPT_CLOCKS_OBJ", f"Missing clocks_event_reasons in {receipt_name}.{phase}")
        require_ok(cer.get("thermal_throttled") is False, "RECEIPT_THERMAL_THROTTLE", f"Thermal throttle in {receipt_name}.{phase}")
        require_ok(cer.get("slowdown_active") is False, "RECEIPT_SLOWDOWN", f"Clock slowdown in {receipt_name}.{phase}")

    return {
        "receipt_file": receipt_name,
        "receipt_file_sha256": _sha256_file(receipt_path),
        "receipt_sha256": receipt_sha,
        "receipt_auth_note": "unkeyed_self_hash_integrity_only",
        "bound_result_file": result_name,
        "bound_result_file_sha256": _sha256_file(track_dir / result_name),
        "bound_result_inner_sha256": str(result_data["result_sha256"]),
        "started_utc": str(exe["started_utc"]),
        "completed_utc": str(result_data["completed_utc"]),
        "ended_utc": str(exe["ended_utc"]),
        "duration_ms": _as_float(exe["duration_ms"], f"{receipt_name}.duration_ms"),
        "start_temp_c": _as_float(rec["start_gpu_telemetry"]["temperature_gpu_c"], f"{receipt_name}.start_temp_c"),
        "end_temp_c": _as_float(rec["end_gpu_telemetry"]["temperature_gpu_c"], f"{receipt_name}.end_temp_c"),
    }


def _recompute_h14a(h14a: Mapping[str, Any], ptxas_v1: Mapping[str, Any]) -> Dict[str, Any]:
    require_ok(
        h14a.get("cu_sha256") == ptxas_v1["cu_sha256"],
        "H14A_CU_SHA",
        "H14a cu_sha256 does not match V1 ptxas receipt",
    )
    parity = h14a["parity"]
    su2 = parity["su2_holonomy"]
    worst_fp32 = 0.0
    worst_bf16 = 0.0
    worst_norm = 0.0

    for dtype_key in ("fp32", "bf16"):
        len_map = su2[dtype_key]
        require_ok(isinstance(len_map, dict) and len(len_map) >= 5, "H14A_PARITY_LEN", f"Insufficient H14a {dtype_key} lengths")
        for t_key, backends in len_map.items():
            for bk in ("cuda", "triton"):
                row = backends[bk]
                err = max(_as_float(row["fwd_max_abs"], f"h14a.{dtype_key}.{t_key}.{bk}.fwd"), _as_float(row["bwd_max_abs"], f"h14a.{dtype_key}.{t_key}.{bk}.bwd"))
                nd = _as_float(row["norm_drift"], f"h14a.{dtype_key}.{t_key}.{bk}.norm")
                if dtype_key == "fp32":
                    worst_fp32 = max(worst_fp32, err)
                else:
                    worst_bf16 = max(worst_bf16, err)
                worst_norm = max(worst_norm, nd)

    untr = parity["untransport"]
    for dtype_key in ("fp32", "bf16"):
        for sub_k in ("fwd", "d_o", "d_pi"):
            val = _as_float(untr[dtype_key][sub_k]["max_abs"], f"h14a.untransport.{dtype_key}.{sub_k}")
            if dtype_key == "fp32":
                worst_fp32 = max(worst_fp32, val)
            else:
                worst_bf16 = max(worst_bf16, val)

    sph = parity["spherical_steps"]
    for dtype_key in ("fp32", "bf16"):
        for mode_k, fields in sph[dtype_key].items():
            for fk, fv in fields.items():
                val = _as_float(fv["max_abs"], f"h14a.sph.{dtype_key}.{mode_k}.{fk}")
                if dtype_key == "fp32":
                    worst_fp32 = max(worst_fp32, val)
                else:
                    worst_bf16 = max(worst_bf16, val)

    a16 = parity["siliquant_a16"]
    a16_exact = (
        _as_int(a16["valid_syndrome_errors"], "h14a.a16.valid") == 0
        and _as_int(a16["injected_1bit_errors_expected"], "h14a.a16.exp") > 0
        and _as_int(a16["injected_1bit_errors_detected"], "h14a.a16.det") == _as_int(a16["injected_1bit_errors_expected"], "h14a.a16.exp")
    )
    any_nan = parity["summary"]["any_nan_or_inf"] is not False
    c1_zero_spill = (ptxas_v1["nonzero_spill_kernels"] == 0) and (ptxas_v1["zero_spill_kernels"] == 9)
    c2_parity = (
        (not any_nan)
        and (worst_fp32 <= FP32_MAX_ABS)
        and (worst_bf16 <= BF16_MAX_ABS)
        and (worst_norm <= NORM_DRIFT_MAX)
        and a16_exact
    )

    f12 = h14a["full_12l_h7b_step"]
    rope_ms = _as_float(f12["rope2d_ngpt"]["step_median_ms"], "h14a.rope_ms")
    eager_ms = _as_float(f12["eager_h7b"]["step_median_ms"], "h14a.eager_ms")
    cuda_ms = _as_float(f12["holosphere_cuda_sm86"]["step_median_ms"], "h14a.cuda_ms")
    require_ok(rope_ms > 0.0 and cuda_ms > 0.0 and eager_ms > 0.0, "H14A_TIMING_POS", "H14a step timings must be positive")
    cuda_vs_rope = cuda_ms / rope_ms
    cuda_speedup_vs_eager = eager_ms / cuda_ms

    micro = h14a["kernel_microbench"]
    m512_eager = _as_float(micro["512"]["eager_h7b"]["fwdbwd_ms"], "h14a.micro512.eager")
    m512_cuda = _as_float(micro["512"]["cuda_sm86_bhtd_with_permute"]["fwdbwd_ms"], "h14a.micro512.cuda")
    m2048_eager = _as_float(micro["2048"]["eager_h7b"]["fwdbwd_ms"], "h14a.micro2048.eager")
    m2048_cuda = _as_float(micro["2048"]["cuda_sm86_bhtd_with_permute"]["fwdbwd_ms"], "h14a.micro2048.cuda")
    require_ok(m512_cuda > 0.0 and m2048_cuda > 0.0, "H14A_MICRO_POS", "H14a microbench timings must be positive")
    micro_512_speedup = m512_eager / m512_cuda
    micro_2048_speedup = m2048_eager / m2048_cuda

    graded = grade_h14a(
        c1_zero_spill=c1_zero_spill,
        c2_parity=c2_parity,
        cuda_vs_rope=cuda_vs_rope,
        cuda_speedup_vs_eager=cuda_speedup_vs_eager,
        micro_512_speedup=micro_512_speedup,
        micro_2048_speedup=micro_2048_speedup,
    )
    recorded_verdict = h14a["h14a_locked_verdict"]["verdict"]
    require_ok(
        graded["verdict"] == recorded_verdict,
        "H14A_VERDICT_MISMATCH",
        f"Recomputed H14a verdict {graded['verdict']} != recorded {recorded_verdict}",
    )
    return {
        "cu_sha256": str(h14a["cu_sha256"]),
        "recomputed_gates": graded,
        "verdict": graded["verdict"],
        "worst_fp32_max_abs": round(worst_fp32, 8),
        "worst_bf16_max_abs": round(worst_bf16, 8),
        "worst_unit_norm_drift": round(worst_norm, 8),
        "a16_syndrome_exact": a16_exact,
        "cuda_vs_rope": round(cuda_vs_rope, 4),
        "cuda_speedup_vs_eager": round(cuda_speedup_vs_eager, 4),
        "micro_512_bhtd_speedup": round(micro_512_speedup, 3),
        "micro_2048_bhtd_speedup": round(micro_2048_speedup, 3),
        "fiber_major_t2048_gbs": _as_float(micro["2048"]["cuda_sm86_fiber_major_native"]["fwd_eff_gbs"], "h14a.fiber_gbs"),
    }


def _recompute_v2(v2: Mapping[str, Any], ptxas_v2: Mapping[str, Any]) -> Dict[str, Any]:
    require_ok(v2.get("cu_sha256") == ptxas_v2["cu_sha256"], "V2_CU_SHA", "V2 cu_sha256 != ptxas_v2 cu_sha256")
    require_ok(
        _as_int(v2.get("zero_spill_kernels"), "v2.zero_spill_kernels") == ptxas_v2["zero_spill_kernels"],
        "V2_ZERO_SPILL_COUNT",
        "V2 zero_spill_kernels mismatch",
    )
    parity = v2["parity"]
    rows = parity["bhtd_rows"]
    require_ok(isinstance(rows, list) and len(rows) >= 20, "V2_PARITY_ROWS", "V2 parity must have >= 20 rows")
    worst_fp32 = 0.0
    worst_bf16 = 0.0
    worst_norm = 0.0
    for idx, row in enumerate(rows):
        err = max(_as_float(row["fwd_max_abs"], f"v2.row{idx}.fwd"), _as_float(row["bwd_max_abs"], f"v2.row{idx}.bwd"))
        nd = _as_float(row["norm_drift"], f"v2.row{idx}.norm")
        if row["dtype"] == "fp32":
            worst_fp32 = max(worst_fp32, err)
        else:
            worst_bf16 = max(worst_bf16, err)
        worst_norm = max(worst_norm, nd)

    beltrami = _as_float(parity["gpu_beltrami_m0_m4_max_drift"], "v2.beltrami")
    require_ok(parity["summary"]["any_nan_or_inf"] is False, "V2_NAN_INF", "V2 reported NaN/Inf")
    require_ok(worst_fp32 <= FP32_MAX_ABS, "V2_FP32_PARITY", f"V2 worst FP32 err {worst_fp32} > {FP32_MAX_ABS}")
    require_ok(worst_bf16 <= BF16_MAX_ABS, "V2_BF16_PARITY", f"V2 worst BF16 err {worst_bf16} > {BF16_MAX_ABS}")
    require_ok(worst_norm <= NORM_DRIFT_MAX, "V2_NORM_DRIFT", f"V2 norm drift {worst_norm} > {NORM_DRIFT_MAX}")
    require_ok(beltrami <= BELTRAMI_DRIFT_MAX, "V2_BELTRAMI_DRIFT", f"V2 Beltrami drift {beltrami} > {BELTRAMI_DRIFT_MAX}")

    f12 = v2["full_12l_step"]
    rope_ms = _as_float(f12["rope2d_ngpt"]["step_median_ms"], "v2.rope_ms")
    eager_ms = _as_float(f12["eager_h7b"]["step_median_ms"], "v2.eager_ms")
    v2_ms = _as_float(f12["holosphere_v2_sm86"]["step_median_ms"], "v2.v2_ms")
    cs_ms = _as_float(f12["holosphere_v2_cayley_su2"]["step_median_ms"], "v2.cayley_su2_ms")
    require_ok(rope_ms > 0.0 and v2_ms > 0.0 and cs_ms > 0.0 and eager_ms > 0.0, "V2_TIMING_POS", "V2 timings must be positive")
    v2_vs_rope = v2_ms / rope_ms
    v2_vs_eager = eager_ms / v2_ms
    require_ok(v2_vs_rope <= H14A_MAX_VS_ROPE, "V2_VS_ROPE", f"V2 vs RoPE ratio {v2_vs_rope:.4f} > {H14A_MAX_VS_ROPE}")
    require_ok(v2_vs_eager >= H14A_MIN_VS_EAGER, "V2_VS_EAGER", f"V2 vs Eager speedup {v2_vs_eager:.4f} < {H14A_MIN_VS_EAGER}")
    return {
        "cu_sha256": str(v2["cu_sha256"]),
        "worst_fp32_max_abs": round(worst_fp32, 8),
        "worst_bf16_max_abs": round(worst_bf16, 8),
        "worst_unit_norm_drift": round(worst_norm, 8),
        "gpu_beltrami_m0_m4_max_drift": beltrami,
        "v2_vs_rope": round(v2_vs_rope, 4),
        "v2_speedup_vs_eager": round(v2_vs_eager, 4),
        "v2_cayley_su2_vs_rope": round(cs_ms / rope_ms, 4),
    }


def _recompute_h14b(h14b: Mapping[str, Any]) -> Dict[str, Any]:
    runs = h14b["runs"]
    require_ok(isinstance(runs, list) and len(runs) == 21, "H14B_RUN_COUNT", "H14b must have 21 runs (7 arms x 3 seeds)")
    by_arm: Dict[str, List[Dict[str, Any]]] = {}
    for row in runs:
        by_arm.setdefault(str(row["arm_name"]), []).append(row)
    require_ok(set(by_arm.keys()) == set(H14B_EXPECTED_ARMS), "H14B_ARMS", "H14b arm set mismatch")

    for arm_name, rs in by_arm.items():
        seeds = tuple(sorted(_as_int(r["seed"], f"h14b.{arm_name}.seed") for r in rs))
        require_ok(seeds == EXPECTED_SEEDS, "H14B_SEEDS", f"H14b seeds mismatch for {arm_name}: {seeds}")

    rope_ngpt = sorted(by_arm["RoPE-2D-nGPT"], key=lambda r: _as_int(r["seed"], "ngpt.seed"))
    rope_std = sorted(by_arm["RoPE-2D-Std"], key=lambda r: _as_int(r["seed"], "std.seed"))
    ref_params = _as_float(rope_ngpt[0]["params"]["non_embedding_params"], "h14b.ref_params")
    require_ok(ref_params > 0.0, "H14B_REF_PARAMS", "H14b reference non_embedding_params must be positive")

    max_param_delta = 0.0
    max_budget_overshoot_s = 0.0
    for arm_name, rs in by_arm.items():
        for r in rs:
            p_arm = _as_float(r["params"]["non_embedding_params"], f"h14b.{arm_name}.params")
            delta = abs(p_arm - ref_params) / ref_params
            require_ok(delta <= PARAM_DELTA_MAX, "H14B_PARAM_PARITY", f"H14b {arm_name} param delta {delta:.5f} > {PARAM_DELTA_MAX}")
            max_param_delta = max(max_param_delta, delta)

            t_budget = _as_float(r["t_budget_s"], f"h14b.{arm_name}.t_budget_s")
            wc_time = _as_float(r["equal_wallclock"]["train_time_s"], f"h14b.{arm_name}.wc_time")
            overshoot = wc_time - t_budget
            require_ok(
                wc_time > 0.0 and overshoot <= H14B_BUDGET_SLACK_S,
                "H14B_BUDGET_OVERSHOOT",
                f"H14b {arm_name} eq-WC time {wc_time} violates budget {t_budget} (+{H14B_BUDGET_SLACK_S}s)",
            )
            max_budget_overshoot_s = max(max_budget_overshoot_s, overshoot)

    ngpt_mj_512 = sum(_as_float(r["inference_T512"]["gross_mj_per_tok"], "ngpt.mj512") for r in rope_ngpt) / 3.0
    ngpt_mj_2048 = sum(_as_float(r["inference_T2048"]["gross_mj_per_tok"], "ngpt.mj2048") for r in rope_ngpt) / 3.0
    require_ok(ngpt_mj_512 > 0.0 and ngpt_mj_2048 > 0.0, "H14B_MJ_POS", "RoPE-2D-nGPT inference mJ/tok must be positive")

    arm_gates: Dict[str, Dict[str, bool]] = {}
    arm_metrics: Dict[str, Any] = {}
    recorded_cmp = h14b["comparisons"]

    for arm_name in sorted(by_arm.keys()):
        if not arm_name.startswith("HoloSphere-V2-"):
            continue
        rs = sorted(by_arm[arm_name], key=lambda r: _as_int(r["seed"], f"{arm_name}.seed"))
        st_ngpt_2048 = _paired_stats(
            [_as_float(r["equal_wallclock"]["T2048"]["bpb"], f"{arm_name}.wc2048") for r in rs],
            [_as_float(r["equal_wallclock"]["T2048"]["bpb"], "ngpt.wc2048") for r in rope_ngpt],
        )
        st_std_2048 = _paired_stats(
            [_as_float(r["equal_wallclock"]["T2048"]["bpb"], f"{arm_name}.wc2048") for r in rs],
            [_as_float(r["equal_wallclock"]["T2048"]["bpb"], "std.wc2048") for r in rope_std],
        )
        st_ngpt_512 = _paired_stats(
            [_as_float(r["equal_wallclock"]["T512"]["bpb"], f"{arm_name}.wc512") for r in rs],
            [_as_float(r["equal_wallclock"]["T512"]["bpb"], "ngpt.wc512") for r in rope_ngpt],
        )
        st_eqstep_2048 = _paired_stats(
            [_as_float(r["equal_step"]["T2048"]["bpb"], f"{arm_name}.es2048") for r in rs],
            [_as_float(r["equal_step"]["T2048"]["bpb"], "ngpt.es2048") for r in rope_ngpt],
        )
        arm_mj_512 = sum(_as_float(r["inference_T512"]["gross_mj_per_tok"], f"{arm_name}.mj512") for r in rs) / 3.0
        arm_mj_2048 = sum(_as_float(r["inference_T2048"]["gross_mj_per_tok"], f"{arm_name}.mj2048") for r in rs) / 3.0
        mj_r512 = arm_mj_512 / ngpt_mj_512
        mj_r2048 = arm_mj_2048 / ngpt_mj_2048

        gates = grade_h14b_arm(
            rel_pct_2048_vs_ngpt=st_ngpt_2048["rel_pct"],
            z_2048_vs_ngpt=st_ngpt_2048["z_or_t"],
            rel_pct_2048_vs_std=st_std_2048["rel_pct"],
            z_2048_vs_std=st_std_2048["z_or_t"],
            rel_pct_512_vs_ngpt=st_ngpt_512["rel_pct"],
            mj_ratio_512=mj_r512,
            mj_ratio_2048=mj_r2048,
        )
        rec_arm = recorded_cmp[arm_name]
        for gk, gv in gates.items():
            require_ok(
                rec_arm[gk] is gv,
                "H14B_GATE_MISMATCH",
                f"H14b {arm_name} gate {gk} mismatch: recomputed {gv} != recorded {rec_arm[gk]}",
            )
        arm_gates[arm_name] = gates
        arm_metrics[arm_name] = {
            "lock_status": "preregistered" if arm_name in H14B_PREREG_CANDIDATES else "exploratory",
            "gates": gates,
            "eq_wc_t2048_vs_rope_ngpt": st_ngpt_2048,
            "eq_wc_t2048_vs_rope_std": st_std_2048,
            "eq_wc_t512_vs_rope_ngpt": st_ngpt_512,
            "eq_step_t2048_vs_rope_ngpt": st_eqstep_2048,
            "inf_mj_ratio_t512": round(mj_r512, 4),
            "inf_mj_ratio_t2048": round(mj_r2048, 4),
        }

    prereg_verdict = grade_h14b_campaign({k: arm_gates[k] for k in H14B_PREREG_CANDIDATES})
    all_arms_verdict = grade_h14b_campaign(arm_gates)
    recorded_verdict = h14b["h14b_locked_verdict"]
    require_ok(
        prereg_verdict == recorded_verdict and all_arms_verdict == recorded_verdict,
        "H14B_VERDICT_MISMATCH",
        f"Recomputed H14b verdict (prereg={prereg_verdict}, all={all_arms_verdict}) != recorded {recorded_verdict}",
    )
    passing_arms = sorted(
        k for k, g in arm_gates.items() if g["c1_t2048_ge_5pct_z_le_m2"] and g["c2_t512_non_regression"] and g["c3_mj_le_115x"]
    )
    return {
        "verdict": prereg_verdict,
        "preregistered_arms_verdict": prereg_verdict,
        "all_arms_verdict": all_arms_verdict,
        "passing_arms": passing_arms,
        "max_param_delta": round(max_param_delta, 6),
        "max_budget_overshoot_s": round(max_budget_overshoot_s, 4),
        "arms": arm_metrics,
    }


def _recompute_h14c(h14c: Mapping[str, Any]) -> Dict[str, Any]:
    runs = h14c["runs"]
    require_ok(isinstance(runs, list) and len(runs) == 30, "H14C_RUN_COUNT", "H14c must have 30 runs (2 groups x 5 arms x 3 seeds)")

    group_results: Dict[str, Any] = {}
    group_pass: Dict[str, bool] = {}
    max_param_delta = 0.0

    for gname, acc_floor, margin_pp in (("S3", H14C_S3_FLOOR, H14C_S3_MARGIN), ("A5", H14C_A5_FLOOR, H14C_A5_MARGIN)):
        by_arm: Dict[str, List[Dict[str, Any]]] = {}
        for row in runs:
            if row["group"] == gname:
                by_arm.setdefault(str(row["arm_name"]), []).append(row)
        require_ok(set(by_arm.keys()) == set(H14C_EXPECTED_ARMS), "H14C_ARMS", f"H14c {gname} arm set mismatch")
        for arm_name, rs in by_arm.items():
            seeds = tuple(sorted(_as_int(r["seed"], f"h14c.{gname}.{arm_name}.seed") for r in rs))
            require_ok(seeds == EXPECTED_SEEDS, "H14C_SEEDS", f"H14c {gname}/{arm_name} seeds mismatch: {seeds}")

        rope = sorted(by_arm["RoPE-2D-nGPT"], key=lambda r: _as_int(r["seed"], f"h14c.{gname}.rope.seed"))
        ref_params = _as_float(rope[0]["params"]["non_embedding_params"], f"h14c.{gname}.ref_params")
        require_ok(ref_params > 0.0, "H14C_REF_PARAMS", f"H14c {gname} ref params must be positive")
        for arm_name, rs in by_arm.items():
            for r in rs:
                p_arm = _as_float(r["params"]["non_embedding_params"], f"h14c.{gname}.{arm_name}.params")
                delta = abs(p_arm - ref_params) / ref_params
                require_ok(delta <= PARAM_DELTA_MAX, "H14C_PARAM_PARITY", f"H14c {gname}/{arm_name} param delta {delta:.5f} > {PARAM_DELTA_MAX}")
                max_param_delta = max(max_param_delta, delta)

        cov = sorted(by_arm["HoloSphere-V2-Full-Covariant-QKV-Untransport"], key=lambda r: _as_int(r["seed"], "cov.seed"))
        qk = sorted(by_arm["H7b-QK-Only"], key=lambda r: _as_int(r["seed"], "qk.seed"))
        cov_ood = [_as_float(r["ood_acc_pct"], f"h14c.{gname}.cov") for r in cov]
        rope_ood = [_as_float(r["ood_acc_pct"], f"h14c.{gname}.rope") for r in rope]
        qk_ood = [_as_float(r["ood_acc_pct"], f"h14c.{gname}.qk") for r in qk]

        ood_mean = round(sum(cov_ood) / 3.0, 3)
        vs_rope = _paired_stats(cov_ood, rope_ood)
        vs_qk = _paired_stats(cov_ood, qk_ood)
        passed = grade_h14c_group(
            ood_acc_mean=ood_mean,
            acc_floor=acc_floor,
            margin_pp=margin_pp,
            diff_vs_rope=vs_rope["mean_diff"],
            z_vs_rope=vs_rope["z_or_t"],
            diff_vs_qk=vs_qk["mean_diff"],
            z_vs_qk=vs_qk["z_or_t"],
        )
        rec_pass = h14c["comparisons"][gname]["locked_criterion_pass"]
        require_ok(
            rec_pass is passed,
            "H14C_GATE_MISMATCH",
            f"H14c {gname} gate mismatch: recomputed {passed} != recorded {rec_pass}",
        )
        group_pass[gname] = passed
        group_results[gname] = {
            "covariant_ood_acc_mean": ood_mean,
            "vs_rope": vs_rope,
            "vs_qk_only": vs_qk,
            "locked_criterion_pass": passed,
        }

    verdict = grade_h14c_campaign(group_pass["S3"], group_pass["A5"])
    recorded_verdict = h14c["h14c_locked_verdict"]
    require_ok(
        verdict == recorded_verdict,
        "H14C_VERDICT_MISMATCH",
        f"Recomputed H14c verdict {verdict} != recorded {recorded_verdict}",
    )
    return {
        "verdict": verdict,
        "max_param_delta": round(max_param_delta, 6),
        "groups": group_results,
    }


def build_certificate(track_dir: Path) -> Dict[str, Any]:
    """Audit all Track S114 raw evidence from disk and return a canonical self-hashed certificate."""
    try:
        hygiene = _check_directory_hygiene(track_dir)

        # Fail-closed PREREG + Amendment 1 verification (must reside inside track_dir)
        prereg_sha = _sha256_file(track_dir / PREREG_FILENAME)
        require_ok(prereg_sha == PREREG_SHA256, "PREREG_SHA_MISMATCH", f"PREREG SHA mismatch: {prereg_sha}")

        amend1_sha = _sha256_file(track_dir / AMENDMENT1_FILENAME)
        require_ok(amend1_sha == AMENDMENT1_SHA256, "AMENDMENT1_SHA_MISMATCH", f"Amendment 1 SHA mismatch: {amend1_sha}")

        report_path = track_dir / REPORT_FILENAME
        report_sha = _sha256_file(report_path)
        require_ok(
            PREREG_SHA256 in report_path.read_text(encoding="utf-8"),
            "REPORT_PREREG_REF",
            f"{REPORT_FILENAME} must reference immutable PREREG SHA-256",
        )

        cu_sha = _sha256_file(track_dir / CU_FILENAME)
        ptxas_v1 = _verify_ptxas_receipt(track_dir, PTXAS_V1_FILENAME, expected_kernels=9, expected_cu_sha=None, v1_schema=True)
        ptxas_v2 = _verify_ptxas_receipt(track_dir, PTXAS_V2_FILENAME, expected_kernels=27, expected_cu_sha=cu_sha, v1_schema=False)

        h14a_data = _load_json_dict(track_dir / "s114_h14a_gpu_results.json")
        v2_data = _load_json_dict(track_dir / "s114_v2_gpu_results.json")
        h14bc_data = _load_json_dict(track_dir / "s114_h14bc_gpu_results.json")

        for label, payload in (("h14a", h14a_data), ("v2", v2_data), ("h14bc", h14bc_data)):
            _verify_inner_hash(payload, "result_sha256", label)
            require_ok(
                payload.get("preregistration_sha256") == PREREG_SHA256,
                "RESULT_PREREG_SHA",
                f"{label} preregistration_sha256 mismatch",
            )

        require_ok(
            h14bc_data.get("cu_sha256") == ptxas_v2["cu_sha256"],
            "H14BC_CU_SHA",
            "h14bc cu_sha256 != ptxas_v2 cu_sha256",
        )
        require_ok(
            _as_int(h14bc_data.get("zero_spill_kernels"), "h14bc.zero_spill_kernels") == ptxas_v2["zero_spill_kernels"],
            "H14BC_ZERO_SPILL",
            "h14bc zero_spill_kernels mismatch",
        )
        corpus = h14bc_data["corpus"]
        require_ok(
            corpus["train_sha256"] != corpus["eval_sha256"] and _as_int(corpus["train_num_bytes"], "corpus.train_num_bytes") > 0,
            "CORPUS_DISJOINT",
            "Train/eval corpus SHA collision or empty train corpus",
        )

        # Zone-B receipt verification & distinct-receipt binding
        result_map = {"h14a": h14a_data, "v2": v2_data, "h14bc": h14bc_data}
        zone_b_receipts: Dict[str, Any] = {}
        seen_receipt_hashes: set[str] = set()
        for key, rec_name, res_name in ZONE_B_BINDINGS:
            bound = _verify_zone_b_receipt(track_dir, rec_name, res_name, result_map[key])
            seen_receipt_hashes.add(bound["receipt_sha256"])
            zone_b_receipts[key] = bound
        require_ok(
            len(seen_receipt_hashes) == len(ZONE_B_BINDINGS),
            "DUPLICATE_ZONE_B_RECEIPT",
            "Zone-B receipts must be distinct across campaigns",
        )

        h14a_audit = _recompute_h14a(h14a_data, ptxas_v1)
        v2_audit = _recompute_v2(v2_data, ptxas_v2)
        h14b_audit = _recompute_h14b(h14bc_data["h14b"])
        h14c_audit = _recompute_h14c(h14bc_data["h14c"])

        pinned_files: Dict[str, str] = {
            PREREG_FILENAME: prereg_sha,
            AMENDMENT1_FILENAME: amend1_sha,
            REPORT_FILENAME: report_sha,
            CU_FILENAME: cu_sha,
            PTXAS_V1_FILENAME: _sha256_file(track_dir / PTXAS_V1_FILENAME),
            PTXAS_V2_FILENAME: _sha256_file(track_dir / PTXAS_V2_FILENAME),
            "s114_h14a_gpu_results.json": _sha256_file(track_dir / "s114_h14a_gpu_results.json"),
            "s114_v2_gpu_results.json": _sha256_file(track_dir / "s114_v2_gpu_results.json"),
            "s114_h14bc_gpu_results.json": _sha256_file(track_dir / "s114_h14bc_gpu_results.json"),
            "mlos_zone_b_s114_h14a.json": zone_b_receipts["h14a"]["receipt_file_sha256"],
            "mlos_zone_b_s114_v2.json": zone_b_receipts["v2"]["receipt_file_sha256"],
            "mlos_zone_b_s114_h14bc.json": zone_b_receipts["h14bc"]["receipt_file_sha256"],
        }
        for script_name in GENERATOR_SCRIPTS:
            pinned_files[script_name] = _sha256_file(track_dir / script_name)

        cert: Dict[str, Any] = {
            "schema": SCHEMA_VERSION,
            "track": "track-s114-silisphere-fused-kernel-transformer",
            "novelty_class": "N1",
            "n2_claims": 0,
            "prereg_verified": True,
            "preregistration_sha256": prereg_sha,
            "amendment1_sha256": amend1_sha,
            "hygiene": hygiene,
            "ptxas_sm86_v1": ptxas_v1,
            "ptxas_sm86_v2": ptxas_v2,
            "zone_b_receipts": zone_b_receipts,
            "verdicts": {
                "H14a": h14a_audit["verdict"],
                "H14b": h14b_audit["verdict"],
                "H14c": h14c_audit["verdict"],
            },
            "h14a": h14a_audit,
            "v2_foundry": v2_audit,
            "h14b": h14b_audit,
            "h14c": h14c_audit,
            "pinned_file_sha256": pinned_files,
        }
        cert["cert_sha256"] = _sha256_bytes(_canonical_bytes(cert))
        return cert
    except S114AuditError:
        raise
    except (KeyError, TypeError, ValueError, ZeroDivisionError, AttributeError, OSError) as exc:
        raise S114AuditError("MALFORMED_SCHEMA", f"Malformed schema during Track S114 audit: {exc}") from exc


def format_certificate(cert: Mapping[str, Any]) -> str:
    return json.dumps(cert, indent=2, sort_keys=True, allow_nan=False) + "\n"


def verify_certificate(track_dir: Path, cert_path: Path) -> Dict[str, Any]:
    """Load stored certificate, validate self-hash, recompute from raw evidence, and require exact match."""
    stored = _load_json_dict(cert_path)
    _verify_inner_hash(stored, "cert_sha256", cert_path.name)
    recomputed = build_certificate(track_dir)
    require_ok(
        stored == recomputed,
        "CERT_MISMATCH",
        f"Stored certificate {cert_path.name} diverges from freshly recomputed raw evidence",
    )
    return recomputed


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Track S114 Pure-Stdlib Audit & Certificate Verifier")
    parser.add_argument("--track-dir", type=Path, default=Path(__file__).resolve().parent)
    mode_grp = parser.add_mutually_exclusive_group()
    mode_grp.add_argument("--write", action="store_true", help="Recompute and write s114_holosphere_certificate.json")
    mode_grp.add_argument("--standalone", action="store_true", help="Recompute from raw evidence without reading stored cert")
    mode_grp.add_argument("--check", nargs="?", const=CERT_FILENAME, default=None, help="Verify stored certificate file")
    parser.add_argument("--json", action="store_true", help="Emit canonical JSON certificate to stdout")
    args = parser.parse_args(argv)

    track_dir = args.track_dir.resolve()
    try:
        if args.write:
            cert = build_certificate(track_dir)
            out_path = track_dir / CERT_FILENAME
            out_path.write_text(format_certificate(cert), encoding="utf-8")
            print(json.dumps({"status": "WROTE", "cert_file": out_path.name, "cert_sha256": cert["cert_sha256"], "verdicts": cert["verdicts"]}, sort_keys=True))
            return 0

        if args.standalone:
            cert = build_certificate(track_dir)
            if args.json:
                sys.stdout.write(format_certificate(cert))
            else:
                print(json.dumps({"status": "PASS", "cert_sha256": cert["cert_sha256"], "verdicts": cert["verdicts"]}, sort_keys=True))
            return 0

        cert_arg = args.check if args.check is not None else CERT_FILENAME
        cert_path = Path(cert_arg) if Path(cert_arg).is_absolute() else (track_dir / cert_arg)
        cert = verify_certificate(track_dir, cert_path)
        if args.json:
            sys.stdout.write(format_certificate(cert))
        else:
            print(json.dumps({"status": "PASS", "cert_file": cert_path.name, "cert_sha256": cert["cert_sha256"], "verdicts": cert["verdicts"]}, sort_keys=True))
        return 0
    except S114AuditError as exc:
        sys.stderr.write(f"AUDIT_FAIL {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
