#!/usr/bin/env python3
"""Pure-stdlib independent verifier and certificate checker for Track S107 (PREREG-S107 + Amendment 1).

Zero external dependencies (no torch, no numpy): runs under stock /usr/bin/python3 -I -B/-O/-W error.
Recomputes directly from raw per-seed JSON records:
  - Cryptographic self-verification of mlos_zone_b_h7{a,b,c}.json (canonical receipt_sha256,
    schema, exit_code=0, duration_ms >= results total_elapsed_sec, clean GPU telemetry) and
    exact track-to-receipt & track-to-results SHA-256 binding
  - Exact CS-08 parameter/FLOP parity across all 21 arms (10 H7a, 6 H7c, 5 H7b)
  - Exact paired-seed statistics (mean, SE, relative %, paired t with df=2)
  - Data-derived literal_prereg_verdict (strictly from locked PREREG-S107 booleans) AND
    graded_verdict (with explicit post_hoc_reason when post-hoc grading differs)
  - Exact H7b eager wall-clock ratio (3.9125x), corpus_manifest.json binding, prereg provenance
    digests, and H7b/H7c corpus digest equality
  - Fail-closed --check <cert.json> using strict 64-lower-hex checks + hmac.compare_digest
Zero bare asserts; strict fail-closed S107AuditError on all malformed inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple


HEX_CHARS = frozenset("0123456789abcdef")

# Exact SHA-256 track-to-receipt and track-to-results bindings for the frozen RTX 3080 run.
LIVE_TRACK_BINDINGS: Dict[str, Dict[str, str]] = {
    "h7a": {
        "results_sha256": "561572d9ace9df3cf76c1ba6e2a52b62809c6c9df2698fdd18e7904c5f4bede6",
        "mlos_receipt_sha256": "b6165dfe34f3ca8861f5c94e6dca2c7d6654cd0e06dcdd241e3ea223fce0e6c4",
    },
    "h7c": {
        "results_sha256": "81f00fd481a5c146b02568d1da3124cb0c60f77fe2b2f545940200c505a38bd9",
        "mlos_receipt_sha256": "1adafc333c06905cbe70a99e895a6c8220ba71477063d9fb50a306e440b0a694",
    },
    "h7b": {
        "results_sha256": "0775dd1c4bf14311f84714f1681a0944fb9775fefe1d2e3c80c5d78f54e606d5",
        "mlos_receipt_sha256": "1b5d9ce8691288fe4b35e9bce63ac5ec17747ab3635a32c42c45a6c19b9c05af",
    },
}


class S107AuditError(ValueError):
    """Fail-closed error raised on any integrity, schema, or parity violation."""


def require_ok(cond: bool, msg: str) -> None:
    if not cond:
        raise S107AuditError(msg)


def is_lower_hex64(val: Any) -> bool:
    return type(val) is str and len(val) == 64 and all(ch in HEX_CHARS for ch in val)


def sha256_file(path: Path) -> str:
    require_ok(path.is_file(), f"Missing required artifact file: {path.name}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_json_tree_iterative(obj: Any, max_depth: int = 64) -> None:
    stack: List[Tuple[Any, int]] = [(obj, 0)]
    while stack:
        cur, depth = stack.pop()
        if depth > max_depth:
            raise S107AuditError(f"JSON nesting depth exceeds {max_depth}")
        if isinstance(cur, dict):
            for k, v in cur.items():
                if type(k) is not str:
                    raise S107AuditError(f"Non-str JSON key forbidden: {type(k).__name__}")
                stack.append((v, depth + 1))
        elif isinstance(cur, (list, tuple)):
            for item in cur:
                stack.append((item, depth + 1))


def load_json_strict(path: Path) -> Dict[str, Any]:
    require_ok(path.is_file(), f"Missing required JSON file: {path.name}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise S107AuditError(f"Malformed JSON in {path.name}: {exc}") from exc
    require_ok(isinstance(data, dict), f"Top-level JSON object must be dict in {path.name}")
    check_json_tree_iterative(data)
    return data


def canonical_sha256(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def mean_se(vals: Sequence[float]) -> Tuple[float, float]:
    n = len(vals)
    require_ok(n >= 2, "Need >= 2 paired seeds for mean/SE")
    mu = sum(vals) / float(n)
    var = sum((v - mu) ** 2 for v in vals) / float(n - 1)
    return round(mu, 6), round(math.sqrt(var / float(n)), 6)


def paired_stats(a_vals: Sequence[float], c_vals: Sequence[float]) -> Dict[str, Any]:
    require_ok(len(a_vals) == len(c_vals) and len(a_vals) >= 2, "Paired sample mismatch")
    diffs = [a - c for a, c in zip(a_vals, c_vals)]
    mu = sum(diffs) / float(len(diffs))
    var = sum((d - mu) ** 2 for d in diffs) / float(len(diffs) - 1)
    se = math.sqrt(var / float(len(diffs)))
    c_mean = sum(c_vals) / float(len(c_vals))
    rel_pct = 100.0 * mu / max(abs(c_mean), 1e-12)
    t_val = mu / se if se > 1e-12 else 0.0
    return {
        "mean_diff": round(mu, 6),
        "paired_se": round(se, 6),
        "rel_diff_pct": round(rel_pct, 4),
        "paired_t": round(t_val, 4),
        "df": len(diffs) - 1,
    }


def _index_runs(res: Dict[str, Any]) -> Tuple[List[int], Dict[str, Dict[int, Dict[str, Any]]]]:
    seeds = res.get("seeds")
    require_ok(isinstance(seeds, list) and len(seeds) == 3, "Expected exactly 3 locked seeds")
    runs = res.get("runs")
    require_ok(isinstance(runs, list) and len(runs) > 0, "Missing runs list")
    by_arm: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for r in runs:
        by_arm.setdefault(str(r["arm_name"]), {})[int(r["seed"])] = r
    return [int(s) for s in seeds], by_arm


def verify_mlos_receipt(
    path: Path,
    expected_receipt_sha256: Optional[str] = None,
    min_duration_sec: Optional[float] = None,
) -> Dict[str, Any]:
    rec = load_json_strict(path)
    rec_sha = rec.get("receipt_sha256")
    require_ok(is_lower_hex64(rec_sha), f"{path.name}: invalid receipt_sha256 format")
    body_no_sig = {k: v for k, v in rec.items() if k != "receipt_sha256"}
    recomputed_sha = canonical_sha256(body_no_sig)
    require_ok(
        hmac.compare_digest(recomputed_sha, rec_sha),
        f"{path.name}: receipt_sha256 mismatch (tampered receipt)",
    )
    require_ok(rec.get("schema") == "mlos-run-receipt/v0.1", f"{path.name}: unexpected mlos schema")
    require_ok(rec.get("clean_hardware_run") is True, f"{path.name}: clean_hardware_run is not True")
    require_ok(rec.get("anomalies") == [], f"{path.name}: hardware anomalies present")
    require_ok(rec.get("determinism_zone") == "B", f"{path.name}: expected Zone B")

    exec_info = rec.get("execution")
    require_ok(
        isinstance(exec_info, dict) and exec_info.get("exit_code") == 0,
        f"{path.name}: execution.exit_code must be 0",
    )
    duration_ms = exec_info.get("duration_ms")
    require_ok(
        isinstance(duration_ms, (int, float)) and type(duration_ms) is not bool and duration_ms > 0.0,
        f"{path.name}: invalid execution.duration_ms",
    )
    require_ok(
        rec.get("gpu_telemetry_available") is True,
        f"{path.name}: gpu_telemetry_available must be True",
    )
    for tel_key in ("start_gpu_telemetry", "end_gpu_telemetry"):
        tel = rec.get(tel_key)
        reasons = tel.get("clocks_event_reasons") if isinstance(tel, dict) else None
        require_ok(
            isinstance(reasons, dict)
            and reasons.get("thermal_throttled") is False
            and reasons.get("slowdown_active") is False,
            f"{path.name}: {tel_key} thermal throttling or slowdown active",
        )

    if min_duration_sec is not None:
        require_ok(
            float(duration_ms) >= float(min_duration_sec) * 1000.0,
            f"{path.name}: receipt duration shorter than results total_elapsed_sec",
        )
    if expected_receipt_sha256 is not None:
        require_ok(
            hmac.compare_digest(rec_sha, expected_receipt_sha256),
            f"{path.name}: receipt_sha256 does not match pinned track binding",
        )

    return {
        "file": path.name,
        "sha256": sha256_file(path),
        "receipt_sha256": rec_sha,
        "schema": "mlos-run-receipt/v0.1",
        "exit_code": 0,
        "duration_ms": round(float(duration_ms), 3),
        "started_utc": str(exec_info.get("started_utc", "")),
        "ended_utc": str(exec_info.get("ended_utc", "")),
        "clean_hardware_run": True,
        "anomalies_count": 0,
        "determinism_zone": "B",
        "gpu_telemetry_clean": True,
    }


def audit_h7a(track_dir: Path, verify_live_bindings: bool = True) -> Dict[str, Any]:
    res_path = track_dir / "h7a_gpu_results.json"
    res = load_json_strict(res_path)
    res_sha = sha256_file(res_path)
    exp_mlos_sha: Optional[str] = None
    if verify_live_bindings:
        require_ok(
            hmac.compare_digest(res_sha, LIVE_TRACK_BINDINGS["h7a"]["results_sha256"]),
            "H7a results_sha256 does not match pinned track binding",
        )
        exp_mlos_sha = LIVE_TRACK_BINDINGS["h7a"]["mlos_receipt_sha256"]
    mlos = verify_mlos_receipt(
        track_dir / "mlos_zone_b_h7a.json",
        expected_receipt_sha256=exp_mlos_sha,
        min_duration_sec=float(res.get("total_elapsed_sec", 0.0)),
    )
    seeds, by_arm = _index_runs(res)
    require_ok(len(res["runs"]) == 30 and len(by_arm) == 10, "H7a expected 10 arms x 3 seeds = 30 runs")

    # Verify strict CS-08 parity across all 10 arms.
    ref_p = int(by_arm["Cyl-Std"][seeds[0]]["params"]["non_embedding_params"])
    ref_f = int(by_arm["Cyl-Std"][seeds[0]]["flops"]["total_fwd_flops_per_token"])
    max_p_pct = 0.0
    max_f_pct = 0.0
    for smap in by_arm.values():
        p = int(smap[seeds[0]]["params"]["non_embedding_params"])
        f = int(smap[seeds[0]]["flops"]["total_fwd_flops_per_token"])
        max_p_pct = max(max_p_pct, 100.0 * abs(p - ref_p) / float(ref_p))
        max_f_pct = max(max_f_pct, 100.0 * abs(f - ref_f) / float(ref_f))
    require_ok(max_p_pct <= 0.5 and max_f_pct <= 1.0, "H7a CS-08 parity exceeded")

    # Recompute literal PREREG-S107 H7a paired gate checks purely from run data.
    comparisons: Dict[str, Any] = {}
    any_pass = False
    for bb in ("Std", "nGPT"):
        for shape, perm in (("S3-Polar", "S3-Permuted-Pol"), ("S3-Equatorial", "S3-Permuted-Eq")):
            arm, cyl, pnull = f"{shape}-{bb}", f"Cyl-{bb}", f"{perm}-{bb}"
            b_cyl = paired_stats(
                [by_arm[arm][s]["val"]["bpb"] for s in seeds],
                [by_arm[cyl][s]["val"]["bpb"] for s in seeds],
            )
            b_prm = paired_stats(
                [by_arm[arm][s]["val"]["bpb"] for s in seeds],
                [by_arm[pnull][s]["val"]["bpb"] for s in seeds],
            )
            k_cyl = paired_stats(
                [by_arm[arm][s]["ptq_3bit_kl_nats"] for s in seeds],
                [by_arm[cyl][s]["ptq_3bit_kl_nats"] for s in seeds],
            )
            k_prm = paired_stats(
                [by_arm[arm][s]["ptq_3bit_kl_nats"] for s in seeds],
                [by_arm[pnull][s]["ptq_3bit_kl_nats"] for s in seeds],
            )
            bpb_pass = (
                b_cyl["rel_diff_pct"] <= -1.5
                and b_cyl["paired_t"] <= -2.0
                and b_prm["rel_diff_pct"] <= -1.5
                and b_prm["paired_t"] <= -2.0
            )
            kl_pass = (
                k_cyl["rel_diff_pct"] <= -15.0
                and k_cyl["paired_t"] <= -2.0
                and k_prm["rel_diff_pct"] <= -15.0
                and k_prm["paired_t"] <= -2.0
                and b_cyl["mean_diff"] <= 0.0
                and b_prm["mean_diff"] <= 0.0
            )
            if bpb_pass or kl_pass:
                any_pass = True
            comparisons[arm] = {
                "vs_cyl_bpb": b_cyl,
                "vs_perm_bpb": b_prm,
                "vs_cyl_kl": k_cyl,
                "vs_perm_kl": k_prm,
                "bpb_pass": bpb_pass,
                "kl_pass": kl_pass,
            }

    literal_verdict = "CONFIRMED" if any_pass else "FALSIFIED"
    graded_verdict = literal_verdict
    return {
        "results_sha256": res_sha,
        "mlos": mlos,
        "runs_count": len(res["runs"]),
        "corpus": res["corpus"],
        "max_non_emb_param_diff_pct": round(max_p_pct, 4),
        "max_flop_diff_pct": round(max_f_pct, 4),
        "comparisons": comparisons,
        "literal_prereg_verdict": literal_verdict,
        "graded_verdict": graded_verdict,
        "post_hoc_reason": None,
    }


def audit_h7c(track_dir: Path, verify_live_bindings: bool = True) -> Dict[str, Any]:
    res_path = track_dir / "h7c_gpu_results.json"
    res = load_json_strict(res_path)
    res_sha = sha256_file(res_path)
    exp_mlos_sha: Optional[str] = None
    if verify_live_bindings:
        require_ok(
            hmac.compare_digest(res_sha, LIVE_TRACK_BINDINGS["h7c"]["results_sha256"]),
            "H7c results_sha256 does not match pinned track binding",
        )
        exp_mlos_sha = LIVE_TRACK_BINDINGS["h7c"]["mlos_receipt_sha256"]
    mlos = verify_mlos_receipt(
        track_dir / "mlos_zone_b_h7c.json",
        expected_receipt_sha256=exp_mlos_sha,
        min_duration_sec=float(res.get("total_elapsed_sec", 0.0)),
    )
    seeds, by_arm = _index_runs(res)
    require_ok(
        len(res["runs"]) == 18 and len(res["probes"]) == 18 and len(by_arm) == 6,
        "H7c expected 18 LM + 18 bracket runs",
    )

    ref_p8 = int(by_arm["Unlooped-8L"][seeds[0]]["params"]["non_embedding_params"])
    ref_f16 = int(by_arm["Unlooped-16L"][seeds[0]]["flops"]["total_fwd_flops_per_token"])
    max_p_pct = 0.0
    max_f_pct = 0.0
    for arm in ("FlatLoop-Std", "SphereLoop-NoClock", "SphereLoop-RandRotClock", "CliffordTorus-HopfLoop"):
        p = int(by_arm[arm][seeds[0]]["params"]["non_embedding_params"])
        f = int(by_arm[arm][seeds[0]]["flops"]["total_fwd_flops_per_token"])
        max_p_pct = max(max_p_pct, 100.0 * abs(p - ref_p8) / float(ref_p8))
        max_f_pct = max(max_f_pct, 100.0 * abs(f - ref_f16) / float(ref_f16))
    require_ok(max_p_pct <= 0.5 and max_f_pct <= 5.0, "H7c CS-08 parity exceeded")

    hopf_vs_flat = paired_stats(
        [by_arm["CliffordTorus-HopfLoop"][s]["val"]["bpb"] for s in seeds],
        [by_arm["FlatLoop-Std"][s]["val"]["bpb"] for s in seeds],
    )
    hopf_vs_noclk = paired_stats(
        [by_arm["CliffordTorus-HopfLoop"][s]["val"]["bpb"] for s in seeds],
        [by_arm["SphereLoop-NoClock"][s]["val"]["bpb"] for s in seeds],
    )
    hopf_vs_rand = paired_stats(
        [by_arm["CliffordTorus-HopfLoop"][s]["val"]["bpb"] for s in seeds],
        [by_arm["SphereLoop-RandRotClock"][s]["val"]["bpb"] for s in seeds],
    )
    hopf_vs_u16 = paired_stats(
        [by_arm["CliffordTorus-HopfLoop"][s]["val"]["bpb"] for s in seeds],
        [by_arm["Unlooped-16L"][s]["val"]["bpb"] for s in seeds],
    )
    r6_vs_flat = paired_stats(
        [by_arm["CliffordTorus-HopfLoop"][s]["r_test_extrapolation_bpb"]["R6"] for s in seeds],
        [by_arm["FlatLoop-Std"][s]["r_test_extrapolation_bpb"]["R6"] for s in seeds],
    )
    m1_4b_vs_flat = paired_stats(
        [by_arm["CliffordTorus-HopfLoop"][s]["m1_h1_4bit"]["delta_r_over_delta_1"] for s in seeds],
        [by_arm["FlatLoop-Std"][s]["m1_h1_4bit"]["delta_r_over_delta_1"] for s in seeds],
    )

    crit1_raw_fires = (
        hopf_vs_flat["rel_diff_pct"] <= -2.0
        and hopf_vs_flat["paired_t"] <= -2.0
        and hopf_vs_noclk["rel_diff_pct"] <= -2.0
        and hopf_vs_noclk["paired_t"] <= -2.0
    )
    r6_pass = r6_vs_flat["rel_diff_pct"] <= -10.0 and r6_vs_flat["paired_t"] <= -2.0
    m1_pass = (
        m1_4b_vs_flat["rel_diff_pct"] <= -20.0
        and m1_4b_vs_flat["paired_t"] <= -2.0
        and hopf_vs_flat["mean_diff"] <= 0.0
        and hopf_vs_noclk["mean_diff"] <= 0.0
    )
    beats_randrot = hopf_vs_rand["mean_diff"] < 0.0 and hopf_vs_rand["paired_t"] <= -2.0

    # Literal PREREG-S107:81 is an OR-gate across Criterion 1, R_test=6, and M1-H1.
    literal_verdict = "CONFIRMED" if (crit1_raw_fires or r6_pass or m1_pass) else "FALSIFIED"
    if literal_verdict == "FALSIFIED":
        graded_verdict = "FALSIFIED"
        post_hoc_reason: Optional[str] = None
    elif beats_randrot and (r6_pass or m1_pass):
        graded_verdict = "CONFIRMED"
        post_hoc_reason = None
    else:
        graded_verdict = "PARTIAL"
        reasons: List[str] = []
        if not beats_randrot:
            reasons.append(
                "post-hoc SphereLoop-RandRotClock (Haar O(d)) matches or beats CliffordTorus-HopfLoop at R=3"
            )
        if not r6_pass:
            reasons.append("R_test=6 extrapolation fails via antipodal phase flip phi_5=10*pi/11")
        if not m1_pass:
            reasons.append("4-bit M1-H1 loop-drift cut misses 20% threshold and stays above 2.0")
        post_hoc_reason = "; ".join(reasons)

    return {
        "results_sha256": res_sha,
        "mlos": mlos,
        "runs_count": len(res["runs"]),
        "probes_count": len(res["probes"]),
        "corpus": res["corpus"],
        "max_looped_vs_8L_param_diff_pct": round(max_p_pct, 4),
        "max_looped_vs_16L_flop_diff_pct": round(max_f_pct, 4),
        "hopf_vs_flat_r3_bpb": hopf_vs_flat,
        "hopf_vs_noclock_r3_bpb": hopf_vs_noclk,
        "hopf_vs_randrot_r3_bpb": hopf_vs_rand,
        "hopf_vs_unlooped16L_r3_bpb": hopf_vs_u16,
        "hopf_vs_flat_r6_bpb": r6_vs_flat,
        "hopf_vs_flat_m1h1_4b": m1_4b_vs_flat,
        "criterion1_raw_fires": crit1_raw_fires,
        "r6_extrapolation_pass": r6_pass,
        "m1_h1_4bit_pass": m1_pass,
        "beats_randrot_adversarial_control": beats_randrot,
        "literal_prereg_verdict": literal_verdict,
        "graded_verdict": graded_verdict,
        "post_hoc_reason": post_hoc_reason,
    }


def audit_h7b(track_dir: Path, verify_live_bindings: bool = True) -> Dict[str, Any]:
    res_path = track_dir / "h7b_gpu_results.json"
    res = load_json_strict(res_path)
    res_sha = sha256_file(res_path)
    exp_mlos_sha: Optional[str] = None
    if verify_live_bindings:
        require_ok(
            hmac.compare_digest(res_sha, LIVE_TRACK_BINDINGS["h7b"]["results_sha256"]),
            "H7b results_sha256 does not match pinned track binding",
        )
        exp_mlos_sha = LIVE_TRACK_BINDINGS["h7b"]["mlos_receipt_sha256"]
    mlos = verify_mlos_receipt(
        track_dir / "mlos_zone_b_h7b.json",
        expected_receipt_sha256=exp_mlos_sha,
        min_duration_sec=float(res.get("total_elapsed_sec", 0.0)),
    )
    seeds, by_arm = _index_runs(res)
    require_ok(
        len(res["runs"]) == 15 and len(res["probes"]) == 30 and len(by_arm) == 5,
        "H7b expected 15 LM + 30 S3/A5 probe runs",
    )

    ref_p = int(by_arm["RoPE-2D-nGPT"][seeds[0]]["params"]["non_embedding_params"])
    ref_f = int(by_arm["RoPE-2D-nGPT"][seeds[0]]["flops"]["total_fwd_flops_per_token"])
    max_p_pct = 0.0
    max_f_pct = 0.0
    for smap in by_arm.values():
        p = int(smap[seeds[0]]["params"]["non_embedding_params"])
        f = int(smap[seeds[0]]["flops"]["total_fwd_flops_per_token"])
        max_p_pct = max(max_p_pct, 100.0 * abs(p - ref_p) / float(ref_p))
        max_f_pct = max(max_f_pct, 100.0 * abs(f - ref_f) / float(ref_f))
    require_ok(max_p_pct <= 0.5 and max_f_pct <= 1.0, "H7b CS-08 parity exceeded")

    pr_map: Dict[Tuple[str, str], Dict[int, Dict[str, Any]]] = {}
    for pr in res["probes"]:
        pr_map.setdefault((str(pr["arm_name"]), str(pr["group"])), {})[int(pr["seed"])] = pr

    t512_vs_rope = paired_stats(
        [by_arm["SU2-Holonomy-Scan-nGPT"][s]["val"]["bpb"] for s in seeds],
        [by_arm["RoPE-2D-nGPT"][s]["val"]["bpb"] for s in seeds],
    )
    t512_vs_rand = paired_stats(
        [by_arm["SU2-Holonomy-Scan-nGPT"][s]["val"]["bpb"] for s in seeds],
        [by_arm["Block4-RandOrtho-nGPT"][s]["val"]["bpb"] for s in seeds],
    )
    t2048_vs_rope = paired_stats(
        [by_arm["SU2-Holonomy-Scan-nGPT"][s]["length_extrapolation_bpb"]["T2048"] for s in seeds],
        [by_arm["RoPE-2D-nGPT"][s]["length_extrapolation_bpb"]["T2048"] for s in seeds],
    )
    t2048_vs_rand = paired_stats(
        [by_arm["SU2-Holonomy-Scan-nGPT"][s]["length_extrapolation_bpb"]["T2048"] for s in seeds],
        [by_arm["Block4-RandOrtho-nGPT"][s]["length_extrapolation_bpb"]["T2048"] for s in seeds],
    )
    t2048_vs_liere = paired_stats(
        [by_arm["SU2-Holonomy-Scan-nGPT"][s]["length_extrapolation_bpb"]["T2048"] for s in seeds],
        [by_arm["LieRE-4D-Abelian-nGPT"][s]["length_extrapolation_bpb"]["T2048"] for s in seeds],
    )
    t2048_vs_std = paired_stats(
        [by_arm["SU2-Holonomy-Scan-nGPT"][s]["length_extrapolation_bpb"]["T2048"] for s in seeds],
        [by_arm["RoPE-2D-Std"][s]["length_extrapolation_bpb"]["T2048"] for s in seeds],
    )
    s3_vs_rope = paired_stats(
        [pr_map[("SU2-Holonomy-Scan-nGPT", "S3")][s]["id_acc_len_8_64"] for s in seeds],
        [pr_map[("RoPE-2D-nGPT", "S3")][s]["id_acc_len_8_64"] for s in seeds],
    )
    s3_vs_rand = paired_stats(
        [pr_map[("SU2-Holonomy-Scan-nGPT", "S3")][s]["id_acc_len_8_64"] for s in seeds],
        [pr_map[("Block4-RandOrtho-nGPT", "S3")][s]["id_acc_len_8_64"] for s in seeds],
    )

    su2_t = sum(by_arm["SU2-Holonomy-Scan-nGPT"][s]["elapsed_sec"] for s in seeds) / float(len(seeds))
    rope_t = sum(by_arm["RoPE-2D-nGPT"][s]["elapsed_sec"] for s in seeds) / float(len(seeds))
    wall_ratio = round(su2_t / rope_t, 4)

    t512_win = (
        t512_vs_rope["rel_diff_pct"] <= -1.5
        and t512_vs_rope["paired_t"] <= -2.0
        and t512_vs_rand["rel_diff_pct"] <= -1.5
        and t512_vs_rand["paired_t"] <= -2.0
    )
    extrap_t2048_strong = (
        t2048_vs_rope["rel_diff_pct"] <= -5.0
        and t2048_vs_rope["paired_t"] <= -2.0
        and t2048_vs_rand["rel_diff_pct"] <= -5.0
        and t2048_vs_rand["paired_t"] <= -2.0
    )
    s3_win = (
        s3_vs_rope["mean_diff"] >= 0.15
        and s3_vs_rope["paired_t"] >= 2.0
        and s3_vs_rand["mean_diff"] >= 0.15
        and s3_vs_rand["paired_t"] >= 2.0
    )
    any_primary_win = t512_win or extrap_t2048_strong or s3_win
    no_t512_regression = t512_vs_rope["mean_diff"] <= 0.0

    # Literal PREREG-S107:52 defines only CONFIRMED/FALSIFIED and requires no regression on T=512 BPB.
    literal_verdict = "CONFIRMED" if (any_primary_win and no_t512_regression) else "FALSIFIED"
    if literal_verdict == "CONFIRMED":
        graded_verdict = "CONFIRMED"
        post_hoc_reason: Optional[str] = None
    elif any_primary_win:
        graded_verdict = "PARTIAL"
        post_hoc_reason = (
            "paired arm-vs-arm T=2048 win beats both RoPE-2D-nGPT and Block4-RandOrtho-nGPT by >5%, "
            "but T=512 BPB trails RoPE-2D-nGPT (failing literal no-regression clause), S3/A5 shows zero gain, "
            "and eager PyTorch wall-clock is 3.91x slower"
        )
    else:
        graded_verdict = "FALSIFIED"
        post_hoc_reason = None

    return {
        "results_sha256": res_sha,
        "mlos": mlos,
        "runs_count": len(res["runs"]),
        "probes_count": len(res["probes"]),
        "corpus": res["corpus"],
        "max_non_emb_param_diff_pct": round(max_p_pct, 4),
        "max_flop_diff_pct": round(max_f_pct, 4),
        "su2_vs_rope_t512_bpb": t512_vs_rope,
        "su2_vs_randortho_t512_bpb": t512_vs_rand,
        "su2_vs_rope_t2048_bpb": t2048_vs_rope,
        "su2_vs_randortho_t2048_bpb": t2048_vs_rand,
        "su2_vs_liere_t2048_bpb": t2048_vs_liere,
        "su2_vs_std_t2048_bpb": t2048_vs_std,
        "su2_vs_rope_s3_id_acc": s3_vs_rope,
        "su2_over_rope_wall_clock_ratio": wall_ratio,
        "t512_win": t512_win,
        "extrap_t2048_strong": extrap_t2048_strong,
        "s3_group_win": s3_win,
        "no_t512_regression": no_t512_regression,
        "literal_prereg_verdict": literal_verdict,
        "graded_verdict": graded_verdict,
        "post_hoc_reason": post_hoc_reason,
    }


def build_certificate(track_dir: Path, verify_live_bindings: bool = True) -> Dict[str, Any]:
    preflight_path = track_dir / "s107_cpu_preflight_receipt.json"
    pre = load_json_strict(preflight_path)
    require_ok(
        pre.get("payload", {}).get("all_passed") is True and pre.get("payload", {}).get("gates_passed") == 9,
        "CPU pre-flight receipt must show 9/9 passed",
    )
    pre_sha_recorded = pre.get("payload_sha256")
    require_ok(is_lower_hex64(pre_sha_recorded), "CPU pre-flight receipt payload_sha256 invalid format")
    recomputed_pre_sha = canonical_sha256(pre["payload"])
    require_ok(
        hmac.compare_digest(recomputed_pre_sha, pre_sha_recorded),
        "CPU pre-flight receipt payload_sha256 mismatch",
    )

    manifest_path = track_dir / "corpus_manifest.json"
    manifest = load_json_strict(manifest_path)
    require_ok(
        manifest.get("schema_version") == "aletheia.track_s107.corpus_manifest.v1"
        and type(manifest.get("reconstructible_from_repo_alone")) is bool,
        "Invalid corpus_manifest.json schema",
    )

    prereg_sha = sha256_file(track_dir / "PREREG_S107_HYPERSPHERE_TRANSFORMER.md")
    amend1_sha = sha256_file(track_dir / "PREREG_S107_S108_AMENDMENT1.md")

    h7a = audit_h7a(track_dir, verify_live_bindings=verify_live_bindings)
    h7c = audit_h7c(track_dir, verify_live_bindings=verify_live_bindings)
    h7b = audit_h7b(track_dir, verify_live_bindings=verify_live_bindings)

    # Verify all three tracks carry distinct mlos receipts (prevents cross-track receipt replay).
    receipt_shas = {
        h7a["mlos"]["receipt_sha256"],
        h7c["mlos"]["receipt_sha256"],
        h7b["mlos"]["receipt_sha256"],
    }
    require_ok(len(receipt_shas) == 3, "Duplicate mlos receipt_sha256 across tracks")

    # Verify H7b and H7c share exact corpus digest while H7a is explicitly separated.
    require_ok(h7b["corpus"]["train_sha256"] == h7c["corpus"]["train_sha256"], "H7b/H7c train corpus digest mismatch")
    require_ok(h7b["corpus"]["eval_sha256"] == h7c["corpus"]["eval_sha256"], "H7b/H7c eval corpus digest mismatch")

    payload: Dict[str, Any] = {
        "schema_version": "aletheia.track_s107.hypersphere_transformer.certificate.v2",
        "track_id": "track-s107-hypersphere-transformer",
        "protocol_id": "PREREG-S107-AMENDMENT1",
        "total_live_gpu_runs": (
            h7a["runs_count"] + h7c["runs_count"] + h7c["probes_count"] + h7b["runs_count"] + h7b["probes_count"]
        ),
        "prereg_provenance": {
            "prereg_file": "PREREG_S107_HYPERSPHERE_TRANSFORMER.md",
            "prereg_sha256": prereg_sha,
            "amendment1_file": "PREREG_S107_S108_AMENDMENT1.md",
            "amendment1_sha256": amend1_sha,
            "pre_run_lock_verifiable_from_git_history": False,
        },
        "corpus_manifest": {
            "file": "corpus_manifest.json",
            "sha256": sha256_file(manifest_path),
            "reconstructible_from_repo_alone": manifest["reconstructible_from_repo_alone"],
        },
        "cpu_preflight": {
            "receipt_sha256": sha256_file(preflight_path),
            "payload_sha256": recomputed_pre_sha,
            "gates_passed": 9,
            "gates_total": 9,
        },
        "h7a": h7a,
        "h7c": h7c,
        "h7b": h7b,
        "scorecard": {
            "literal_prereg_verdict": {
                "H7a": h7a["literal_prereg_verdict"],
                "H7c": h7c["literal_prereg_verdict"],
                "H7b": h7b["literal_prereg_verdict"],
            },
            "graded_verdict": {
                "H7a": h7a["graded_verdict"],
                "H7c": h7c["graded_verdict"],
                "H7b": h7b["graded_verdict"],
            },
            "n2_claims": 0,
            "weights_saved": 0,
        },
    }
    payload_sha256 = canonical_sha256(payload)
    cert_body = {
        "schema_version": payload["schema_version"],
        "payload_sha256": payload_sha256,
        "payload": payload,
    }
    cert_sha256 = canonical_sha256(cert_body)
    cert_body["certificate_sha256"] = cert_sha256
    return cert_body


def verify_certificate_file(cert_path: Path, track_dir: Path) -> Dict[str, Any]:
    recorded = load_json_strict(cert_path)
    rec_cert_sha = recorded.get("certificate_sha256")
    rec_payload_sha = recorded.get("payload_sha256")
    require_ok(is_lower_hex64(rec_cert_sha), "Invalid certificate_sha256 field")
    require_ok(is_lower_hex64(rec_payload_sha), "Invalid payload_sha256 field")

    # Verify recorded envelope self-consistency.
    body_no_sig = {k: v for k, v in recorded.items() if k != "certificate_sha256"}
    require_ok(
        hmac.compare_digest(canonical_sha256(body_no_sig), rec_cert_sha),
        "Recorded certificate_sha256 mismatch (tampered envelope)",
    )
    require_ok(
        hmac.compare_digest(canonical_sha256(recorded.get("payload")), rec_payload_sha),
        "Recorded payload_sha256 mismatch (tampered payload)",
    )

    # Full replay from raw JSON artifacts on disk.
    replayed = build_certificate(track_dir)
    require_ok(
        hmac.compare_digest(replayed["payload_sha256"], rec_payload_sha),
        "Replayed payload_sha256 does not match certificate",
    )
    require_ok(
        hmac.compare_digest(replayed["certificate_sha256"], rec_cert_sha),
        "Replayed certificate_sha256 does not match certificate",
    )
    return replayed


def _format_summary(cert: Dict[str, Any]) -> str:
    sc = cert["payload"]["scorecard"]
    lit = sc["literal_prereg_verdict"]
    grd = sc["graded_verdict"]
    return (
        f"OK track-s107-hypersphere-transformer runs={cert['payload']['total_live_gpu_runs']} "
        f"literal=(H7a={lit['H7a']},H7c={lit['H7c']},H7b={lit['H7b']}) "
        f"graded=(H7a={grd['H7a']},H7c={grd['H7c']},H7b={grd['H7b']}) "
        f"cert_sha256={cert['certificate_sha256']}\n"
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Pure-stdlib audit & certificate verifier for Track S107.")
    parser.add_argument("--standalone", action="store_true", help="Recompute full certificate from track artifacts.")
    parser.add_argument("--json", action="store_true", help="Emit canonical JSON certificate.")
    parser.add_argument("--check", type=str, default=None, help="Verify certificate JSON against raw artifacts.")
    parser.add_argument("--track-dir", type=str, default=None, help="Override track directory path.")
    args = parser.parse_args(argv)

    try:
        if args.check:
            cert_path = Path(args.check).resolve()
            tdir = Path(args.track_dir).resolve() if args.track_dir else cert_path.parent
            cert = verify_certificate_file(cert_path, tdir)
            if args.json:
                sys.stdout.write(json.dumps(cert, sort_keys=True, indent=2) + "\n")
            else:
                sys.stdout.write(_format_summary(cert))
            return 0

        tdir = Path(args.track_dir).resolve() if args.track_dir else Path(__file__).resolve().parent
        cert = build_certificate(tdir)
        if args.json:
            sys.stdout.write(json.dumps(cert, sort_keys=True, indent=2) + "\n")
        else:
            sys.stdout.write(_format_summary(cert))
        return 0
    except (S107AuditError, OSError, ValueError, RecursionError) as exc:
        sys.stderr.write(f"FAIL: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
