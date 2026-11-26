#!/usr/bin/env python3
"""Track S116 (`HoloSphere CellOp` Persistent Megakernel) Pure-Stdlib Audit & Certificate Verifier.

Strictly Python standard library ONLY (`0` third-party imports, `0` torch/numpy/scipy).
Zero bare asserts. Zero hardcoded verdict strings: all hardware parity, `ptxas` zero-spill,
speedup/energy/L2 ratios, `CS-08 <= 0.5%` parameter parity, paired two-sided Student-t &
Holm-Bonferroni statistics, Lean 4.36.0 source hygiene, and literal PREREG kill-gate verdicts
(`H16a-v2`, `H16c-v2`, `H16e`, `H16e-v2`, `H16e-v3`) are recomputed strictly from raw shipped
artifacts and Ring-0 `mlos` Zone-B hardware provenance receipts.

Usage:
    python3 -I -B s116_cellop_audit.py --write
    python3 -I -B s116_cellop_audit.py --standalone --json
    python3 -I -B s116_cellop_audit.py --check [s116_cellop_certificate.json]
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

SCHEMA_VERSION = "holosphere.track_s116.cellop_audit_certificate.v1"
CERT_FILENAME = "s116_cellop_certificate.json"
REPORT_FILENAME = "REPORT_S116_CELLOP_EVAL.md"
PTXAS_FILENAME = "ptxas_s116_zero_spill_receipt.json"
LEAN_RELPATH = Path("lean") / "HoloSphereCellOpInvariants.lean"
LEAN_SHA256 = "78c8e3bae5bd16569c539ceadc4b0f8a82fc3ee762625579687f8cddc914dfc4"
LEAN_EXPECTED_THEOREMS = (
    "HoloSphereCellOpInvariants.p1_blockh4_involutory_and_int8_bounds",
    "HoloSphereCellOpInvariants.p2_cayley_unit_ball_so3_involution_and_even",
    "HoloSphereCellOpInvariants.p3_cayley_exact_inverse_reversibility",
    "HoloSphereCellOpInvariants.p4_hadamard256_byte_orthogonality",
    "HoloSphereCellOpInvariants.p4b_bent_phase_preserves_orthogonality",
)
LEAN_FORBIDDEN_TOKENS = ("sorry", "native_decide", "Classical.choice", "import Mathlib")

PREREG_SPECS: Tuple[Tuple[str, str, str], ...] = (
    (
        "prereg_s116",
        "PREREG_S116_HOLOSPHERE_PERSISTENT_MEGAKERNEL.md",
        "9620db774af30b8b6e4ef8c241ccd5ed4cb489dd2fb3b414234633ea83c93c85",
    ),
    (
        "amendment1",
        "PREREG_S116_AMENDMENT1_CELLOP_IMMA_KVRING.md",
        "985e1460d186b376b0d0fe90a271e32df3579c66b2490702958daa2dfc3fea68",
    ),
    (
        "amendment2",
        "PREREG_S116_AMENDMENT2_8WARP_FMNMX_H16E.md",
        "eb1b0e571be990b47150c80a2ee1d75a337a6601f736084eddb95399ccb559a6",
    ),
    (
        "amendment3",
        "PREREG_S116_AMENDMENT3_UNIFIED_A3A4_A5.md",
        "0f58e288d2a11a0308fb7b004904c49c90eb592df3d0e00c2f155bacaf81eaf2",
    ),
    (
        "amendment4",
        "PREREG_S116_AMENDMENT4_RELATIONAL_MACRO_HOLONOMY.md",
        "d22ceaa5251a7c5ca9a2cd6f7fc17853119398ad87ea98ac8850774d0b3f0bfc",
    ),
    (
        "amendment4b",
        "PREREG_S116_AMENDMENT4B_STEP_PARITY.md",
        "0194c2863b7d35af4c4f5ba5aede2eeb863461d22cb2ac97b399953f554d69d1",
    ),
)

# (tag, receipt_file, result_file, prereg_key, original_unmodified_run_receipt_sha256, has_inner_payload_sha)
ZONE_B_SPECS: Tuple[Tuple[str, str, str, str, str, bool], ...] = (
    (
        "phase2b",
        "mlos_zone_b_s116_phase2b.json",
        "s116_phase2b_gpu_results.json",
        "amendment2",
        "739f8708a22152763f3a8c8b448809bb3363dd2f592966ce1069056a03786d18",
        False,
    ),
    (
        "phase2b_pt12l",
        "mlos_zone_b_s116_phase2b_pt12l.json",
        "s116_phase2b_pytorch_12l_results.json",
        "amendment2",
        "7ed1b354b5cc478d7951f7616bed8e1fb488d8d85255f512b053db07b6e77d57",
        True,
    ),
    (
        "h16e_v1",
        "mlos_zone_b_s116_h16e.json",
        "s116_h16e_gpu_results.json",
        "amendment2",
        "ce894e0592286894fef9fce7bbba93dc5b70fa3b4c65957b34e9b9026e9ef7cc",
        True,
    ),
    (
        "h16e_v2",
        "mlos_zone_b_s116_h16e_v2.json",
        "s116_h16e_v2_gpu_results.json",
        "amendment3",
        "782e455bf1a9dadc236b9e6c989fb27cd1bec31c2287061b952c18e17534e9c6",
        True,
    ),
    (
        "h16e_v3",
        "mlos_zone_b_s116_h16e_v3.json",
        "s116_h16e_v3_gpu_results.json",
        "amendment4b",
        "e5169c7367469bda524440f598e590bc242f59347a9dd12f0f25a70882460948",
        True,
    ),
)

# Locked numerical thresholds from PREREG-S116 Amendments 2, 3, 4/4B
CS08_MAX_DELTA_PCT = 0.5
STAT_TOL_COARSE = 1.0 / 1024.0
STAT_TOL_PROB = 1.0 / 65536.0
H16A_MIN_SPEEDUP_CONFIRM = 3.0
H16A_MIN_SPEEDUP_PARTIAL = 2.0
H16C_MIN_PIN_GAIN = 1.25
H16C_MIN_STREAM_RATIO = 1.25
H16E_V1_S3_FLOOR = 50.0
H16E_V1_S3_GAIN = 15.0
H16E_V1_A5_FLOOR = 15.0
H16E_V1_A5_GAIN = 8.0
H16E_P_HOLM_MAX = 0.01
H16E_UTF8_MAX_REGRESS_PCT = 1.0
H16E_V2_WA5_FLOOR = 50.0
H16E_V2_MS3_GAIN = 20.0
H16E_V2_UTF8_FUSION_MAX_BPB = 4.0
H16E_V3_MS3_FLOOR = 90.0
H16E_V3_MA5_FLOOR = 50.0
H16E_V3_MA5_GAIN_A4 = 45.0
H16E_V3_PARTIAL_A5_FLOOR = 15.0

WEIGHT_SUFFIXES = frozenset({".pt", ".pth", ".ckpt", ".safetensors", ".bin", ".gguf", ".onnx", ".npz", ".npy"})
AV_SUFFIXES = frozenset({".wav", ".flac", ".ogg", ".mp3", ".mp4", ".mkv", ".avi", ".webm", ".s32le", ".yuyv", ".grey"})
ELF_SUFFIXES = frozenset({".so", ".o", ".a"})
ELF_MAGIC = b"\x7fELF"


class S116AuditError(ValueError):
    """Typed fail-closed audit violation."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.detail = message
        super().__init__(f"[{code}] {message}")


def require_ok(cond: bool, code: str, message: str) -> None:
    if not cond:
        raise S116AuditError(code, message)


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
        raise S116AuditError("MALFORMED_JSON", f"Malformed JSON in {path.name}: {exc}") from exc
    require_ok(isinstance(obj, dict), "SCHEMA_ROOT", f"JSON root must be an object in {path.name}")
    return obj


def _parse_utc(raw: Any, label: str) -> datetime.datetime:
    require_ok(isinstance(raw, str), "BAD_TIMESTAMP", f"Invalid UTC timestamp for {label}")
    try:
        dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise S116AuditError("BAD_TIMESTAMP", f"Unparseable UTC timestamp for {label}: {raw}") from exc
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
    require_ok(
        isinstance(val, int) and not isinstance(val, bool),
        "BAD_INT",
        f"Non-integer or boolean value for {label}",
    )
    return int(val)


def _verify_inner_hash(obj: Mapping[str, Any], field_name: str, label: str) -> str:
    recorded = obj.get(field_name)
    require_ok(isinstance(recorded, str) and len(recorded) == 64, "MISSING_INNER_HASH", f"Missing {field_name} in {label}")
    body = {k: v for k, v in obj.items() if k != field_name}
    recomputed = _sha256_bytes(_canonical_bytes(body))
    require_ok(recomputed == recorded, "INNER_HASH_MISMATCH", f"{label} {field_name} mismatch")
    return recomputed


def student_t_two_sided_df2_p(abs_t: float) -> float:
    """Exact closed-form two-sided Student-t p-value for df = 2 (n = 3 seeds)."""
    val = _as_float(abs_t, "abs_t")
    require_ok(val >= 0.0, "BAD_ABS_T", f"abs_t must be >= 0, got {val}")
    return max(0.0, min(1.0, 1.0 - val / math.sqrt(2.0 + val * val)))


def holm_bonferroni_adjust(p_vals: Sequence[float]) -> List[float]:
    """Exact step-down Holm-Bonferroni multiplicity adjustment over m >= 1 p-values."""
    m = len(p_vals)
    require_ok(m >= 1, "HOLM_EMPTY", "Holm-Bonferroni requires >= 1 p-value")
    clean: List[float] = []
    for idx, pv in enumerate(p_vals):
        pf = _as_float(pv, f"holm.p[{idx}]")
        require_ok(0.0 <= pf <= 1.0, "HOLM_P_BOUNDS", f"p-value {pf} outside [0, 1]")
        clean.append(pf)
    order = sorted(range(m), key=lambda i: clean[i])
    adjusted = [0.0] * m
    running_max = 0.0
    for rank, orig_idx in enumerate(order):
        running_max = max(running_max, min(1.0, float(m - rank) * clean[orig_idx]))
        adjusted[orig_idx] = running_max
    return adjusted


def recompute_paired_t_df2(cand_vals: Sequence[float], base_vals: Sequence[float]) -> Dict[str, float]:
    """Recompute exact paired two-sided Student-t (df = 2) statistics over 3 seeds."""
    require_ok(len(cand_vals) == 3 and len(base_vals) == 3, "PAIRED_LEN3", "Paired 3-seed vectors required")
    diffs = [_as_float(a, "cand") - _as_float(b, "base") for a, b in zip(cand_vals, base_vals)]
    mean_d = sum(diffs) / 3.0
    var = sum((d - mean_d) ** 2 for d in diffs) / 2.0
    se = math.sqrt(var / 3.0)
    if abs(mean_d) <= 1e-15:
        t_val = 0.0
    elif se <= 1e-15:
        t_val = math.copysign(1e6, mean_d)
    else:
        t_val = mean_d / se
    p_raw = student_t_two_sided_df2_p(abs(t_val))
    return {"mean_diff": mean_d, "t_stat": t_val, "p_raw": p_raw}


# ---------------------------------------------------------------------------
# Pure PREREG Literal-Gate Grading Functions (Zero Hardcoded Verdict Literals)
# ---------------------------------------------------------------------------

def grade_h16a_v2_pure(
    *,
    zero_spill: bool,
    hmma_zero: bool,
    parity_pass: bool,
    speedup_vs_pt12l: float,
    speedup_vs_switch_48cta: float,
    speedup_vs_perop_48: float,
) -> Dict[str, Any]:
    hw_ok = bool(zero_spill and hmma_zero and parity_pass)
    beats_pt = speedup_vs_pt12l >= H16A_MIN_SPEEDUP_CONFIRM
    beats_switch = speedup_vs_switch_48cta >= H16A_MIN_SPEEDUP_CONFIRM
    beats_perop = speedup_vs_perop_48 > 1.0
    if hw_ok and beats_pt and beats_switch and beats_perop:
        verdict = "CONFIRMED"
    elif hw_ok and (beats_pt or speedup_vs_switch_48cta >= H16A_MIN_SPEEDUP_PARTIAL):
        verdict = "PARTIAL"
    else:
        verdict = "FALSIFIED"
    return {
        "hw_zero_spill_and_parity": hw_ok,
        "beats_pt12l_3x": beats_pt,
        "beats_switch_48cta_3x": beats_switch,
        "beats_async_cpp_perop": beats_perop,
        "verdict": verdict,
    }


def grade_h16c_v2_pure(
    *,
    clamp_exact: bool,
    pin_speedup_t2048: float,
    pin_speedup_t8192_1pass: float,
    pinned_4pass_vs_stream: float,
    weight_in_a_vs_b: float,
) -> Dict[str, Any]:
    l2_pin_ok = (pin_speedup_t2048 >= H16C_MIN_PIN_GAIN) and (pin_speedup_t8192_1pass >= H16C_MIN_PIN_GAIN)
    super_hbm_ok = pinned_4pass_vs_stream >= H16C_MIN_STREAM_RATIO
    weight_a_ok = weight_in_a_vs_b > 1.0
    if clamp_exact and l2_pin_ok and super_hbm_ok and weight_a_ok:
        verdict = "CONFIRMED"
    elif clamp_exact and (l2_pin_ok or super_hbm_ok):
        verdict = "PARTIAL"
    else:
        verdict = "FALSIFIED"
    return {
        "clamp_exact": bool(clamp_exact),
        "l2_pin_gain_pass": l2_pin_ok,
        "super_hbm_stream_pass": super_hbm_ok,
        "weight_in_a_faster": weight_a_ok,
        "verdict": verdict,
    }


def grade_h16e_v1_pure(
    *,
    s3_acc: float,
    s3_gain_a0: float,
    s3_gain_a2: float,
    s3_p_a0: float,
    s3_p_a2: float,
    a5_acc: float,
    a5_gain_a0: float,
    a5_gain_a2: float,
    a5_p_a0: float,
    a5_p_a2: float,
    utf8_delta_pct: float,
) -> Dict[str, Any]:
    s3_pass = (
        s3_acc >= H16E_V1_S3_FLOOR
        and s3_gain_a0 >= H16E_V1_S3_GAIN
        and s3_gain_a2 >= H16E_V1_S3_GAIN
        and s3_p_a0 < H16E_P_HOLM_MAX
        and s3_p_a2 < H16E_P_HOLM_MAX
    )
    a5_pass = (
        a5_acc >= H16E_V1_A5_FLOOR
        and a5_gain_a0 >= H16E_V1_A5_GAIN
        and a5_gain_a2 >= H16E_V1_A5_GAIN
        and a5_p_a0 < H16E_P_HOLM_MAX
        and a5_p_a2 < H16E_P_HOLM_MAX
    )
    utf8_ok = utf8_delta_pct <= H16E_UTF8_MAX_REGRESS_PCT
    if s3_pass and a5_pass and utf8_ok:
        verdict = "CONFIRMED"
    elif s3_pass or a5_pass:
        verdict = "PARTIAL"
    else:
        verdict = "FALSIFIED"
    return {"s3_gate_pass": s3_pass, "a5_gate_pass": a5_pass, "utf8_bpb_gate_pass": utf8_ok, "verdict": verdict}


def grade_h16e_v2_pure(
    *,
    a5_wa5_acc: float,
    a5_wa5_gain_a0: float,
    a5_wa5_gain_a2: float,
    a5_wa5_p_a0: float,
    a5_wa5_p_a2: float,
    a4_wa5_acc: float,
    a4_wa5_gain_a0: float,
    a4_wa5_gain_a2: float,
    a4_wa5_p_a0: float,
    a4_wa5_p_a2: float,
    a5_ms3_gain_a2: float,
    a5_ms3_gain_a4: float,
    a5_ms3_p_a2: float,
    a5_ms3_p_a4: float,
    a5_utf8_bpb: float,
    a3_utf8_bpb: float,
    a4_utf8_bpb: float,
    a5_utf8_delta_pct: float,
) -> Dict[str, Any]:
    a5_wa5_pass = (
        a5_wa5_acc >= H16E_V2_WA5_FLOOR
        and a5_wa5_gain_a0 >= H16E_V1_A5_GAIN
        and a5_wa5_gain_a2 >= H16E_V1_A5_GAIN
        and a5_wa5_p_a0 < H16E_P_HOLM_MAX
        and a5_wa5_p_a2 < H16E_P_HOLM_MAX
    )
    a4_wa5_pass = (
        a4_wa5_acc >= H16E_V2_WA5_FLOOR
        and a4_wa5_gain_a0 >= H16E_V1_A5_GAIN
        and a4_wa5_gain_a2 >= H16E_V1_A5_GAIN
        and a4_wa5_p_a0 < H16E_P_HOLM_MAX
        and a4_wa5_p_a2 < H16E_P_HOLM_MAX
    )
    ms3_fusion_pass = (
        a5_ms3_gain_a2 >= H16E_V2_MS3_GAIN
        and a5_ms3_gain_a4 >= H16E_V2_MS3_GAIN
        and a5_ms3_p_a2 < H16E_P_HOLM_MAX
        and a5_ms3_p_a4 < H16E_P_HOLM_MAX
    )
    utf8_fusion_pass = (
        a5_utf8_bpb <= H16E_V2_UTF8_FUSION_MAX_BPB
        and a5_utf8_bpb < a3_utf8_bpb
        and a5_utf8_bpb < a4_utf8_bpb
    )
    h16e_a5_confirmed = (a5_wa5_pass or a4_wa5_pass) and (a5_utf8_delta_pct <= H16E_UTF8_MAX_REGRESS_PCT)
    if a5_wa5_pass and ms3_fusion_pass and utf8_fusion_pass:
        verdict = "UNIFIED_CONFIRMED"
    elif h16e_a5_confirmed or ms3_fusion_pass:
        verdict = "PARTIAL"
    else:
        verdict = "FALSIFIED"
    return {
        "a5_wa5_pass": a5_wa5_pass,
        "a4_wa5_pass": a4_wa5_pass,
        "ms3_fusion_pass": ms3_fusion_pass,
        "utf8_fusion_pass": utf8_fusion_pass,
        "h16e_a5_confirmed": h16e_a5_confirmed,
        "verdict": verdict,
    }


def grade_h16e_v3_pure(
    *,
    a6_ms3: float,
    a6_ma5: float,
    a4_ma5: float,
    a5_ma5: float,
    a6_vs_a4_p_holm: float,
    a6_m2: float,
    a5_m2: float,
) -> Dict[str, Any]:
    ms3_pass = a6_ms3 >= H16E_V3_MS3_FLOOR
    ma5_pass = (
        a6_ma5 >= H16E_V3_MA5_FLOOR
        and (a6_ma5 - a4_ma5) >= H16E_V3_MA5_GAIN_A4
        and a6_vs_a4_p_holm < H16E_P_HOLM_MAX
    )
    improves_over_a5 = (a6_ma5 > a5_ma5) or (a6_m2 > a5_m2)
    if ms3_pass and ma5_pass and improves_over_a5:
        verdict = "CONFIRMED"
    elif ms3_pass and (a6_ma5 >= H16E_V3_PARTIAL_A5_FLOOR or a6_m2 >= H16E_V3_PARTIAL_A5_FLOOR):
        verdict = "PARTIAL"
    else:
        verdict = "FALSIFIED"
    return {
        "ms3_pass": ms3_pass,
        "ma5_pass": ma5_pass,
        "improves_over_a5": improves_over_a5,
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Sub-Verifiers (Hygiene, PREREGs, Zone-B Receipts, ptxas, Stats, Lean)
# ---------------------------------------------------------------------------

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
    require_ok(weights == 0, "HYGIENE_WEIGHTS", f"Found {weights} weight files (WEIGHTS=0 required)")
    require_ok(av_files == 0, "HYGIENE_AV", f"Found {av_files} audio/video files (AV=0 required)")
    require_ok(elfs == 0, "HYGIENE_ELF", f"Found {elfs} ELF binaries (ELF=0 required)")
    return {"weights_count": weights, "av_count": av_files, "elf_count": elfs}


def _verify_preregs(track_dir: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for key, fname, expected_sha in PREREG_SPECS:
        actual = _sha256_file(track_dir / fname)
        require_ok(actual == expected_sha, "PREREG_SHA_MISMATCH", f"PREREG mismatch for {fname}")
        out[key] = actual
    return out


def _verify_zone_b_receipts(
    track_dir: Path,
    prereg_shas: Mapping[str, str],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    receipt_summaries: Dict[str, Dict[str, Any]] = {}
    loaded_results: Dict[str, Dict[str, Any]] = {}
    for tag, rec_name, res_name, prereg_key, expected_orig_sha, has_inner_sha in ZONE_B_SPECS:
        rec = _load_json_dict(track_dir / rec_name)
        bound_sha = _verify_inner_hash(rec, "receipt_sha256", rec_name)
        require_ok(rec.get("schema") == "mlos-run-receipt/v0.1", "RECEIPT_SCHEMA", f"Bad schema in {rec_name}")
        require_ok(rec.get("determinism_zone") == "B", "RECEIPT_ZONE", f"Non-Zone-B receipt: {rec_name}")
        require_ok(rec.get("clean_hardware_run") is True, "RECEIPT_UNCLEAN", f"Unclean hardware run: {rec_name}")
        require_ok(rec.get("anomalies") == [], "RECEIPT_ANOMALIES", f"Non-empty anomalies in {rec_name}")
        require_ok(rec.get("gpu_telemetry_available") is True, "RECEIPT_NO_GPU_TEL", f"No GPU tel in {rec_name}")
        require_ok(
            rec.get("original_unmodified_run_receipt_sha256") == expected_orig_sha,
            "RECEIPT_ORIG_SHA",
            f"Original unmodified receipt SHA mismatch in {rec_name}",
        )
        require_ok(
            rec.get("preregistration_sha256") == prereg_shas[prereg_key],
            "RECEIPT_PREREG_BIND",
            f"PREREG binding mismatch in {rec_name}",
        )
        exe = rec.get("execution")
        require_ok(isinstance(exe, dict) and exe.get("exit_code") == 0, "RECEIPT_EXIT_CODE", f"Non-zero exit in {rec_name}")
        t_start = _parse_utc(exe.get("started_utc"), f"{rec_name}.started_utc")
        t_end = _parse_utc(exe.get("ended_utc"), f"{rec_name}.ended_utc")
        require_ok(t_end >= t_start, "RECEIPT_TIME_ORDER", f"ended_utc < started_utc in {rec_name}")

        res_path = track_dir / res_name
        res_obj = _load_json_dict(res_path)
        res_file_sha = _sha256_file(res_path)
        if has_inner_sha:
            res_inner_sha = _verify_inner_hash(res_obj, "payload_sha256", res_name)
        else:
            res_inner_sha = _sha256_bytes(_canonical_bytes(res_obj))
        require_ok(
            rec.get("result_sha256") == res_inner_sha,
            "RECEIPT_RESULT_BIND",
            f"result_sha256 mismatch in {rec_name}",
        )
        require_ok(
            rec.get("bound_result_file_sha256") == res_file_sha,
            "RECEIPT_FILE_BIND",
            f"bound_result_file_sha256 mismatch in {rec_name}",
        )
        receipt_summaries[tag] = {
            "file": rec_name,
            "receipt_sha256": bound_sha,
            "original_unmodified_run_receipt_sha256": expected_orig_sha,
            "result_file": res_name,
            "result_sha256": res_inner_sha,
            "bound_result_file_sha256": res_file_sha,
            "preregistration_sha256": prereg_shas[prereg_key],
            "started_utc": exe["started_utc"],
            "ended_utc": exe["ended_utc"],
        }
        loaded_results[tag] = res_obj
    return receipt_summaries, loaded_results


def _verify_ptxas(track_dir: Path) -> Dict[str, Any]:
    ptx = _load_json_dict(track_dir / PTXAS_FILENAME)
    require_ok(ptx.get("all_zero_spill") is True, "PTXAS_SPILL_FLAG", "ptxas all_zero_spill != True")
    kernels = ptx.get("kernels")
    require_ok(isinstance(kernels, list) and len(kernels) == 10, "PTXAS_KERNEL_COUNT", "Expected 10 kernels in ptxas")
    require_ok(_as_int(ptx.get("kernel_count"), "ptxas.kernel_count") == 10, "PTXAS_COUNT_FIELD", "kernel_count != 10")
    u8_regs = -1
    for k in kernels:
        sp_ld = _as_int(k.get("spill_loads_bytes"), "ptxas.spill_loads_bytes")
        sp_st = _as_int(k.get("spill_stores_bytes"), "ptxas.spill_stores_bytes")
        st_fr = _as_int(k.get("stack_frame_bytes"), "ptxas.stack_frame_bytes")
        k_regs = _as_int(k.get("registers"), "ptxas.registers")
        require_ok(
            sp_ld == 0 and sp_st == 0 and st_fr == 0,
            "PTXAS_NONZERO_SPILL",
            f"Non-zero spill/stack in kernel {k.get('name')}",
        )
        if "uniform_cell_8warp_sm86" in str(k.get("name", "")):
            u8_regs = k_regs
    require_ok(0 < u8_regs <= 75, "PTXAS_U8_REGS", f"uniform_cell_8warp_sm86 regs={u8_regs} out of (0, 75]")
    per_sass = ptx.get("per_kernel_sass_counts", {})
    u8_sass_matches = [v for k, v in per_sass.items() if "uniform_cell_8warp_sm86" in k]
    require_ok(len(u8_sass_matches) == 1, "PTXAS_U8_SASS", "Missing uniform_cell_8warp_sm86 SASS entry")
    u8_sass = u8_sass_matches[0]
    imma_cnt = _as_int(u8_sass.get("IMMA.16832", 0), "ptxas.IMMA.16832")
    hmma_cnt = _as_int(u8_sass.get("HMMA.16816", 0), "ptxas.HMMA.16816")
    require_ok(imma_cnt >= 1, "PTXAS_NO_IMMA", "uniform_cell_8warp_sm86 missing IMMA.16832")
    require_ok(hmma_cnt == 0, "PTXAS_HMMA_PRESENT", "uniform_cell_8warp_sm86 must have 0 HMMA.16816")
    return {
        "file_sha256": _sha256_file(track_dir / PTXAS_FILENAME),
        "kernel_count": len(kernels),
        "all_zero_spill": True,
        "uniform_cell_8warp_regs": u8_regs,
        "uniform_cell_8warp_imma_16832": imma_cnt,
        "uniform_cell_8warp_hmma_16816": hmma_cnt,
    }


def _audit_group_tasks(tasks_obj: Mapping[str, Any], ref_arm: str, label: str) -> Dict[str, Any]:
    """Recompute CS-08 <= 0.5% param parity and paired Student-t + Holm-Bonferroni across all tasks."""
    out: Dict[str, Any] = {}
    for tk, tv in sorted(tasks_obj.items()):
        arms = tv["arms"]
        p_ref = _as_float(arms[ref_arm]["non_embedding_params"], f"{label}.{tk}.p_ref")
        max_delta = max(
            abs(_as_float(av["non_embedding_params"], f"{label}.{tk}.{an}.p") - p_ref) * 100.0 / p_ref
            for an, av in arms.items()
        )
        require_ok(max_delta <= CS08_MAX_DELTA_PCT, "CS08_VIOLATION", f"{label}.{tk} CS-08 delta {max_delta:.4f}% > 0.5%")
        recorded_delta = _as_float(tv["cs08_max_non_embed_param_delta_pct"], f"{label}.{tk}.cs08")
        require_ok(
            abs(max_delta - recorded_delta) <= STAT_TOL_COARSE,
            "CS08_MISMATCH",
            f"{label}.{tk} recomputed CS-08 {max_delta:.4f}% != recorded {recorded_delta:.4f}%",
        )

        rec_stats = tv["stats_t128"]
        stat_names = list(rec_stats.keys())
        recomp_rows: List[Tuple[str, Dict[str, float]]] = []
        for sname in stat_names:
            cand_pfx, base_pfx = sname.split("_vs_")
            cand_key = [k for k in arms if k.startswith(cand_pfx + "_")][0]
            base_key = [k for k in arms if k.startswith(base_pfx + "_")][0]
            xs = [_as_float(r["ood_final_acc_pct"]["T128"], f"{label}.{tk}.{cand_key}") for r in arms[cand_key]["per_seed"]]
            ys = [_as_float(r["ood_final_acc_pct"]["T128"], f"{label}.{tk}.{base_key}") for r in arms[base_key]["per_seed"]]
            recomp_rows.append((sname, recompute_paired_t_df2(xs, ys)))

        p_holm_list = holm_bonferroni_adjust([row["p_raw"] for _, row in recomp_rows])
        verified_stats: Dict[str, Dict[str, float]] = {}
        for (sname, row), p_holm in zip(recomp_rows, p_holm_list):
            rec = rec_stats[sname]
            require_ok(
                abs(row["mean_diff"] - _as_float(rec["mean_diff"], f"{label}.{tk}.{sname}.md")) <= STAT_TOL_COARSE,
                "STAT_DIFF_MISMATCH",
                f"{label}.{tk}.{sname} mean_diff mismatch",
            )
            require_ok(
                abs(row["t_stat"] - _as_float(rec["t_stat"], f"{label}.{tk}.{sname}.t")) <= STAT_TOL_COARSE,
                "STAT_T_MISMATCH",
                f"{label}.{tk}.{sname} t_stat mismatch",
            )
            require_ok(
                abs(row["p_raw"] - _as_float(rec["p_raw"], f"{label}.{tk}.{sname}.p_raw")) <= STAT_TOL_PROB,
                "STAT_PRAW_MISMATCH",
                f"{label}.{tk}.{sname} p_raw mismatch",
            )
            require_ok(
                abs(p_holm - _as_float(rec["p_holm"], f"{label}.{tk}.{sname}.p_holm")) <= STAT_TOL_PROB,
                "STAT_PHOLM_MISMATCH",
                f"{label}.{tk}.{sname} p_holm mismatch",
            )
            verified_stats[sname] = {
                "mean_diff": round(row["mean_diff"], 4),
                "t_stat": round(row["t_stat"], 4),
                "p_raw": round(row["p_raw"], 8),
                "p_holm": round(p_holm, 8),
            }
        out[tk] = {"cs08_max_delta_pct": round(max_delta, 4), "stats_t128": verified_stats}
    return out


def _verify_lean_artifact(track_dir: Path) -> Dict[str, Any]:
    lean_path = track_dir / LEAN_RELPATH
    lean_sha = _sha256_file(lean_path)
    require_ok(lean_sha == LEAN_SHA256, "LEAN_SHA_MISMATCH", "HoloSphereCellOpInvariants.lean SHA-256 mismatch")
    text = lean_path.read_text(encoding="utf-8")
    code_only = re.sub(r"--[^\n]*", "", re.sub(r"/-.*?-/", "", text, flags=re.DOTALL))
    for tok in LEAN_FORBIDDEN_TOKENS:
        require_ok(tok not in code_only, "LEAN_FORBIDDEN_TOKEN", f"Forbidden token {tok!r} in Lean proof")
    found_axioms = [line.strip() for line in code_only.splitlines() if line.strip().startswith("#print axioms ")]
    expected_lines = [f"#print axioms {t}" for t in LEAN_EXPECTED_THEOREMS]
    require_ok(found_axioms == expected_lines, "LEAN_THEOREM_SET", "Unexpected #print axioms list in Lean proof")
    return {"file": str(LEAN_RELPATH), "sha256": lean_sha, "theorem_count": len(found_axioms)}


def build_certificate(track_dir: Path) -> Dict[str, Any]:
    hygiene = _check_directory_hygiene(track_dir)
    prereg_shas = _verify_preregs(track_dir)
    receipts, results = _verify_zone_b_receipts(track_dir, prereg_shas)
    ptxas_summary = _verify_ptxas(track_dir)
    lean_summary = _verify_lean_artifact(track_dir)

    # Report SHA pin + verify every bound Zone-B receipt SHA is disclosed in REPORT
    report_path = track_dir / REPORT_FILENAME
    report_sha = _sha256_file(report_path)
    report_text = report_path.read_text(encoding="utf-8")
    for tag, rsum in receipts.items():
        require_ok(
            rsum["receipt_sha256"] in report_text,
            "REPORT_MISSING_RECEIPT",
            f"Bound receipt_sha256 for {tag} missing from {REPORT_FILENAME}",
        )

    # 1. H16a-v2 & H16c-v2 recomputation from live Phase-2B silicon + live PyTorch 12L baseline
    p2b = results["phase2b"]
    pt12 = results["phase2b_pt12l"]
    par = p2b["phase2b_live_parity"]
    parity_ok = (
        par.get("all_parity_pass") is True
        and par.get("fmnmx_onehot_nan_desyncs") == 0
        and par.get("fmnmx_onehot_imma_max_int32_diff") == 0
        and par.get("weight_in_a_imma_max_int32_diff") == 0
        and par.get("weight_in_a_valid_syndrome_errors") == 0
        and par.get("weight_in_a_injected_16_flips_caught") == 16
        and par.get("cell8warp_2cta_syndrome_errors") == 0
        and par.get("cell8warp_2cta_nan_desyncs") == 0
        and par.get("cell8warp_2cta_passb_max_int32_diff") == 0
        and _as_float(par.get("cell8warp_2cta_16b_pi_t0_rollback_max_drift"), "rollback_drift") == 0.0
    )
    require_ok(parity_ok, "PHASE2B_PARITY_FAIL", "Phase-2B live hardware parity failed")

    h16a_raw = p2b["h16a_v2_matched_12layer_showdown"]
    u8_us = _as_float(h16a_raw["uniform_cell_8warp_d256_1cta"]["us_per_tok"], "u8_us")
    u8_mj = _as_float(h16a_raw["uniform_cell_8warp_d256_1cta"]["mj_per_tok"], "u8_mj")
    pt_t2048_us = _as_float(pt12["T_2048"]["us_per_tok"], "pt_t2048_us")
    pt_t8192_us = _as_float(pt12["T_8192"]["us_per_tok"], "pt_t8192_us")
    pt_t2048_mj = _as_float(pt12["T_2048"]["mj_per_tok"], "pt_t2048_mj")
    pt_t8192_mj = _as_float(pt12["T_8192"]["mj_per_tok"], "pt_t8192_mj")
    sw48_us = _as_float(h16a_raw["switch_opcode_vm_12l_48cta"]["us_per_tok"], "sw48_us")
    perop48_us = _as_float(h16a_raw["async_cpp_per_op_12l_48"]["us_per_tok"], "perop48_us")
    perop150_us = _as_float(h16a_raw["async_cpp_per_op_150"]["us_per_tok"], "perop150_us")
    sp_pt2048 = pt_t2048_us / u8_us
    sp_pt8192 = pt_t8192_us / u8_us
    sp_sw48 = sw48_us / u8_us
    sp_perop48 = perop48_us / u8_us
    sp_perop150 = perop150_us / u8_us
    energy_ratio_t2048 = pt_t2048_mj / u8_mj
    energy_ratio_t8192 = pt_t8192_mj / u8_mj
    mem = p2b["memory_footprint_accounting"]
    state_comp_t8192 = _as_float(mem["transformer_12l_d256_kv_cache_t8192_bytes"], "kv8192") / _as_float(
        mem["cellop_fixed_o1_recurrent_state_bytes"], "o1_state"
    )
    h16a_gate = grade_h16a_v2_pure(
        zero_spill=ptxas_summary["all_zero_spill"],
        hmma_zero=(ptxas_summary["uniform_cell_8warp_hmma_16816"] == 0),
        parity_pass=parity_ok,
        speedup_vs_pt12l=sp_pt2048,
        speedup_vs_switch_48cta=sp_sw48,
        speedup_vs_perop_48=sp_perop48,
    )

    h16c_raw = p2b["h16c_v2_l2_persistence_and_weight_in_a"]
    stream_triad = _as_float(p2b["live_gddr6_stream_triad_gb_s"], "stream_triad")
    pin_sp_2048 = _as_float(h16c_raw["t2048_24mib_polluted_1pass_pinned_gb_s"], "pin2048") / _as_float(
        h16c_raw["t2048_24mib_polluted_1pass_unpinned_gb_s"], "unpin2048"
    )
    pin_sp_8192_1p = _as_float(h16c_raw["t8192_96mib_polluted_1pass_pinned_gb_s"], "pin8192_1p") / _as_float(
        h16c_raw["t8192_96mib_polluted_1pass_unpinned_gb_s"], "unpin8192_1p"
    )
    pin_4p_gb_s = _as_float(h16c_raw["t8192_96mib_polluted_4pass_pinned_gb_s"], "pin8192_4p")
    pin_4p_vs_stream = pin_4p_gb_s / stream_triad
    wa_vs_wb = _as_float(h16c_raw["weight_in_a_n8_tops"], "wa_tops") / _as_float(
        h16c_raw["weight_in_b_ref_tops"], "wb_tops"
    )
    h16c_gate = grade_h16c_v2_pure(
        clamp_exact=(h16c_raw.get("clamp_exact_ga104m_ceiling") is True),
        pin_speedup_t2048=pin_sp_2048,
        pin_speedup_t8192_1pass=pin_sp_8192_1p,
        pinned_4pass_vs_stream=pin_4p_vs_stream,
        weight_in_a_vs_b=wa_vs_wb,
    )

    # 2. H16e (800-step) audit & literal gate recomputation
    v1 = results["h16e_v1"]
    v1_tasks = _audit_group_tasks(v1["tasks"], "A0_H14c_Softmax_CovariantQKV", "h16e_v1")
    v1_s3 = v1["tasks"]["H16e_W_S3"]["arms"]["A3_CellOp_HardFMNMX_CayleySTE"]["t128_mean_pct"]
    v1_a3_a5 = v1["tasks"]["H16e_W_A5"]["arms"]["A3_CellOp_HardFMNMX_CayleySTE"]["t128_mean_pct"]
    v1_utf8_a0 = _as_float(v1["utf8_512b_guard"]["A0_H14c_Softmax_CovariantQKV"]["mean_val_bpb_512b"], "v1_utf8_a0")
    v1_utf8_a3 = _as_float(v1["utf8_512b_guard"]["A3_CellOp_HardFMNMX_CayleySTE"]["mean_val_bpb_512b"], "v1_utf8_a3")
    v1_utf8_delta = 100.0 * (v1_utf8_a3 - v1_utf8_a0) / v1_utf8_a0
    v1_gate = grade_h16e_v1_pure(
        s3_acc=_as_float(v1_s3, "v1_s3"),
        s3_gain_a0=v1_tasks["H16e_W_S3"]["stats_t128"]["A3_vs_A0"]["mean_diff"],
        s3_gain_a2=v1_tasks["H16e_W_S3"]["stats_t128"]["A3_vs_A2"]["mean_diff"],
        s3_p_a0=v1_tasks["H16e_W_S3"]["stats_t128"]["A3_vs_A0"]["p_holm"],
        s3_p_a2=v1_tasks["H16e_W_S3"]["stats_t128"]["A3_vs_A2"]["p_holm"],
        a5_acc=_as_float(v1_a3_a5, "v1_a3_a5"),
        a5_gain_a0=v1_tasks["H16e_W_A5"]["stats_t128"]["A3_vs_A0"]["mean_diff"],
        a5_gain_a2=v1_tasks["H16e_W_A5"]["stats_t128"]["A3_vs_A2"]["mean_diff"],
        a5_p_a0=v1_tasks["H16e_W_A5"]["stats_t128"]["A3_vs_A0"]["p_holm"],
        a5_p_a2=v1_tasks["H16e_W_A5"]["stats_t128"]["A3_vs_A2"]["p_holm"],
        utf8_delta_pct=v1_utf8_delta,
    )
    require_ok(
        v1_gate["verdict"] == v1["prereg_s116_amendment2_gate"]["verdict"],
        "H16E_V1_VERDICT_MISMATCH",
        "Recomputed H16e-v1 verdict disagrees with recorded JSON",
    )

    # 3. H16e-v2 (2,000-step A5 unified fusion) audit & literal gate recomputation
    v2 = results["h16e_v2"]
    v2_tasks = _audit_group_tasks(v2["tasks"], "A0_H14c_Softmax_CovariantQKV", "h16e_v2")
    v2_u = v2["utf8_512b_guard"]
    v2_u_a0 = _as_float(v2_u["A0_H14c_Softmax_CovariantQKV"]["mean_val_bpb_512b"], "v2_u_a0")
    v2_u_a3 = _as_float(v2_u["A3_CellOp_HardFMNMX_CayleySTE"]["mean_val_bpb_512b"], "v2_u_a3")
    v2_u_a4 = _as_float(v2_u["A4_CellOp_CayleySU2_MultFastWeight"]["mean_val_bpb_512b"], "v2_u_a4")
    v2_u_a5 = _as_float(v2_u["A5_CellOp_Unified_A3plusA4"]["mean_val_bpb_512b"], "v2_u_a5")
    v2_u_delta = 100.0 * (v2_u_a5 - v2_u_a0) / v2_u_a0
    v2_gate = grade_h16e_v2_pure(
        a5_wa5_acc=_as_float(v2["tasks"]["H16e_W_A5"]["arms"]["A5_CellOp_Unified_A3plusA4"]["t128_mean_pct"], "v2_a5_wa5"),
        a5_wa5_gain_a0=v2_tasks["H16e_W_A5"]["stats_t128"]["A5_vs_A0"]["mean_diff"],
        a5_wa5_gain_a2=v2_tasks["H16e_W_A5"]["stats_t128"]["A5_vs_A2"]["mean_diff"],
        a5_wa5_p_a0=v2_tasks["H16e_W_A5"]["stats_t128"]["A5_vs_A0"]["p_holm"],
        a5_wa5_p_a2=v2_tasks["H16e_W_A5"]["stats_t128"]["A5_vs_A2"]["p_holm"],
        a4_wa5_acc=_as_float(v2["tasks"]["H16e_W_A5"]["arms"]["A4_CellOp_CayleySU2_MultFastWeight"]["t128_mean_pct"], "v2_a4_wa5"),
        a4_wa5_gain_a0=v2_tasks["H16e_W_A5"]["stats_t128"]["A4_vs_A0"]["mean_diff"],
        a4_wa5_gain_a2=v2_tasks["H16e_W_A5"]["stats_t128"]["A4_vs_A2"]["mean_diff"],
        a4_wa5_p_a0=v2_tasks["H16e_W_A5"]["stats_t128"]["A4_vs_A0"]["p_holm"],
        a4_wa5_p_a2=v2_tasks["H16e_W_A5"]["stats_t128"]["A4_vs_A2"]["p_holm"],
        a5_ms3_gain_a2=v2_tasks["H16e_M_S3"]["stats_t128"]["A5_vs_A2"]["mean_diff"],
        a5_ms3_gain_a4=v2_tasks["H16e_M_S3"]["stats_t128"]["A5_vs_A4"]["mean_diff"],
        a5_ms3_p_a2=v2_tasks["H16e_M_S3"]["stats_t128"]["A5_vs_A2"]["p_holm"],
        a5_ms3_p_a4=v2_tasks["H16e_M_S3"]["stats_t128"]["A5_vs_A4"]["p_holm"],
        a5_utf8_bpb=v2_u_a5,
        a3_utf8_bpb=v2_u_a3,
        a4_utf8_bpb=v2_u_a4,
        a5_utf8_delta_pct=v2_u_delta,
    )
    require_ok(
        v2_gate["verdict"] == v2["prereg_s116_amendment3_gate"]["verdict"],
        "H16E_V2_VERDICT_MISMATCH",
        "Recomputed H16e-v2 verdict disagrees with recorded JSON",
    )

    # 4. H16e-v3 (2,000-step A6 relational macro holonomy) audit & literal gate recomputation
    v3 = results["h16e_v3"]
    v3_tasks = _audit_group_tasks(v3["tasks"], "A3_CellOp_HardFMNMX_CayleySTE", "h16e_v3")
    v3_gate = grade_h16e_v3_pure(
        a6_ms3=_as_float(v3["tasks"]["H16e_M_S3"]["arms"]["A6_RelationalCellOp"]["t128_mean_pct"], "v3_a6_ms3"),
        a6_ma5=_as_float(v3["tasks"]["H16e_M_A5"]["arms"]["A6_RelationalCellOp"]["t128_mean_pct"], "v3_a6_ma5"),
        a4_ma5=_as_float(v3["tasks"]["H16e_M_A5"]["arms"]["A4_CellOp_CayleySU2_MultFastWeight"]["t128_mean_pct"], "v3_a4_ma5"),
        a5_ma5=_as_float(v3["tasks"]["H16e_M_A5"]["arms"]["A5_CellOp_Unified_A3plusA4"]["t128_mean_pct"], "v3_a5_ma5"),
        a6_vs_a4_p_holm=v3_tasks["H16e_M_A5"]["stats_t128"]["A6_vs_A4"]["p_holm"],
        a6_m2=_as_float(v3["tasks"]["H16e_M2_A5"]["arms"]["A6_RelationalCellOp"]["t128_mean_pct"], "v3_a6_m2"),
        a5_m2=_as_float(v3["tasks"]["H16e_M2_A5"]["arms"]["A5_CellOp_Unified_A3plusA4"]["t128_mean_pct"], "v3_a5_m2"),
    )
    require_ok(
        v3_gate["verdict"] == v3["prereg_s116_amendment4_gate"]["verdict"],
        "H16E_V3_VERDICT_MISMATCH",
        "Recomputed H16e-v3 verdict disagrees with recorded JSON",
    )

    cert: Dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "track": "track-s116-holosphere-cellop",
        "n2_claims": 0,
        "hygiene": hygiene,
        "prereg_sha256": prereg_shas,
        "report_sha256": report_sha,
        "ptxas": ptxas_summary,
        "lean": lean_summary,
        "zone_b_receipts": receipts,
        "verdicts": {
            "H16a_v2": h16a_gate["verdict"],
            "H16c_v2": h16c_gate["verdict"],
            "H16e_v1": v1_gate["verdict"],
            "H16e_v2": v2_gate["verdict"],
            "H16e_v3": v3_gate["verdict"],
        },
        "h16a_v2": {
            "u8_d256_us_per_tok": round(u8_us, 6),
            "u8_d256_mj_per_tok": round(u8_mj, 6),
            "speedup_vs_pt12l_t2048": round(sp_pt2048, 4),
            "speedup_vs_pt12l_t8192": round(sp_pt8192, 4),
            "energy_ratio_vs_pt12l_t2048": round(energy_ratio_t2048, 4),
            "energy_ratio_vs_pt12l_t8192": round(energy_ratio_t8192, 4),
            "speedup_vs_switch_48cta": round(sp_sw48, 4),
            "speedup_vs_perop_48": round(sp_perop48, 4),
            "speedup_vs_perop_150": round(sp_perop150, 4),
            "state_compression_t8192": round(state_comp_t8192, 4),
            "gates": h16a_gate,
        },
        "h16c_v2": {
            "stream_triad_gb_s": round(stream_triad, 4),
            "pin_speedup_t2048": round(pin_sp_2048, 4),
            "pin_speedup_t8192_1pass": round(pin_sp_8192_1p, 4),
            "pinned_4pass_gb_s": round(pin_4p_gb_s, 4),
            "pinned_4pass_vs_stream": round(pin_4p_vs_stream, 4),
            "weight_in_a_vs_b": round(wa_vs_wb, 4),
            "gates": h16c_gate,
        },
        "h16e_v1": {"tasks": v1_tasks, "utf8_a3_delta_vs_a0_pct": round(v1_utf8_delta, 4), "gates": v1_gate},
        "h16e_v2": {
            "tasks": v2_tasks,
            "utf8_a5_bpb": round(v2_u_a5, 6),
            "utf8_a5_delta_vs_a0_pct": round(v2_u_delta, 4),
            "gates": v2_gate,
        },
        "h16e_v3": {
            "tasks": v3_tasks,
            "a5_m_s3_ood_pct": v3["tasks"]["H16e_M_S3"]["arms"]["A5_CellOp_Unified_A3plusA4"]["mean_ood_final_acc_pct"],
            "a6_m_s3_ood_pct": v3["tasks"]["H16e_M_S3"]["arms"]["A6_RelationalCellOp"]["mean_ood_final_acc_pct"],
            "gates": v3_gate,
        },
    }
    cert["cert_sha256"] = _sha256_bytes(_canonical_bytes(cert))
    return cert


def check_certificate(track_dir: Path, cert_path: Path) -> Dict[str, Any]:
    recorded = _load_json_dict(cert_path)
    recorded_sha = _verify_inner_hash(recorded, "cert_sha256", cert_path.name)
    rebuilt = build_certificate(track_dir)
    require_ok(
        rebuilt["cert_sha256"] == recorded_sha,
        "CERT_DRIFT",
        f"Recomputed cert_sha256 {rebuilt['cert_sha256']} != recorded {recorded_sha}",
    )
    return rebuilt


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Track S116 HoloSphere CellOp Pure-Stdlib Audit")
    parser.add_argument("--track-dir", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", nargs="?", const=CERT_FILENAME, default=None)
    parser.add_argument("--standalone", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    track_dir = Path(args.track_dir).resolve()
    try:
        modes_active = int(bool(args.write)) + int(args.check is not None) + int(bool(args.standalone))
        require_ok(modes_active <= 1, "CLI_CONFLICT", "Choose at most one of --write, --check, --standalone")
        if args.check is not None:
            cp = Path(args.check)
            if not cp.is_absolute():
                cp = track_dir / cp
            cert = check_certificate(track_dir, cp)
        else:
            cert = build_certificate(track_dir)
            if args.write:
                out_path = track_dir / CERT_FILENAME
                out_path.write_text(json.dumps(cert, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        if args.json:
            sys.stdout.write(json.dumps(cert, sort_keys=True, indent=2, allow_nan=False) + "\n")
        else:
            v = cert["verdicts"]
            sys.stdout.write(
                f"S116_CELLOP_AUDIT_OK H16a_v2={v['H16a_v2']} H16c_v2={v['H16c_v2']} "
                f"H16e_v1={v['H16e_v1']} H16e_v2={v['H16e_v2']} H16e_v3={v['H16e_v3']} "
                f"cert_sha256={cert['cert_sha256']}\n"
            )
        return 0
    except S116AuditError as exc:
        sys.stderr.write(f"S116_CELLOP_AUDIT_FAIL {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
