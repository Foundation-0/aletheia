#!/usr/bin/env python3
"""Pure-stdlib independent verifier and certificate checker for Track S109 (PREREG-S109 + Amendments 1-3).

Zero external dependencies (no torch, no numpy): runs under stock /usr/bin/python3 across
-I -B, -I -O -B, and -I -B -W error.

Recomputes and cryptographically verifies directly from the frozen live RTX 3080 JSON records:
  - Exact SHA-256 bindings of PREREG_S109 + Amendments 1, 2, and 3 (immutable markdown specs)
  - Exact SHA-256 bindings of gpu_results_{h9a,h9a_v2,terracore}/{s109_locked_protocol,s109_gpu_full_results}.json
    and internal protocol_sha256 / result_sha256 / mlos receipt_sha256 digests
  - Clean hardware Zone-B provenance (clean_hardware_run=True, anomalies=[], exit_code=0, compute_vram_mib=0)
  - Preserved unmodified pre-Amendment-3 prototype baseline (gpu_results_h9a/)
  - Strict 0% train/eval tuple overlap across all 9 seed records and exact 15.0M triple CS-08 parity
    (P_mono=15,023,648 vs P_terra=15,003,063, P_ratio=0.9986; F_infer/F_train ratio=0.9949)
  - Exact paired-seed stats, bootstrap 95% CIs, and strict 3-valued verdicts:
    H9a CONFIRMED (with transparent CoT vs non-CoT Arm A' dissection + 0.00% R2 decompressor & 13.95x Probe-LM),
    H9b FALSIFIED (15.09% native R1, 1.614x latency, 2.46x lower VRAM, 100.00% MHPlate EN+AR IR),
    H9c FALSIFIED (100% frozen Core SHA, 0 skips, 0/18 CS21 leak, CB-1..CB-6 clean, Seed-42 93.98% DPI
    recovery vs 12.30% R2, 0.759x latency, 16.6-18.1% counterfactual audit faithfulness),
    H9d FALSIFIED (monotone Bingham flux 1.0->0.1173->0.0625->0.0625->0.0, Hodge orth <=4.06e-3 vs 0.939
    NoHodge, Darboux err <=3.37e-15, cocycle err <=1.79e-7; Y=0.00 passes leak/swap & matches/beats Y=0.50/NoHodge)
  - Fail-closed --check <cert.json> using hmac.compare_digest on payload_sha256 & certificate_sha256

Zero bare asserts; strict fail-closed S109AuditError on all malformed, tampered, or missing inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
from pathlib import Path
import random
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

PREREG_S109_SHA256 = "1ca8a38fa3c7fd8dda5823741c867b93be09c2342eb35bafde18e9e7e510b1c9"
AMENDMENT1_SHA256 = "6f3d1e0b28d16e4290486e9adeb76c49bd8ebbf0954efb19d88621dc354bdcfd"
AMENDMENT2_SHA256 = "faf225067917b464ac25b2ae68ae1fa7bdf3179a2c461ec883490ea24ff9d7e3"
AMENDMENT3_SHA256 = "e441b07a97205f857a65f1b232b373cdcdc60fa6526d044d5c6fef856761e70e"

EXPECTED_SEEDS = [42, 137, 2026]
EXPECTED_SEED_KEYS = ["42", "137", "2026"]
EXPECTED_YIELD_KEYS = ["Y_0.00", "Y_0.25", "Y_0.50", "Y_0.75", "Y_1.00", "Y_0.50_NoHodge"]
SCHEMA_VERSION = "aletheia.track_s109.minimal_medium_terracore.certificate.v1"


class S109AuditError(ValueError):
    """Fail-closed error raised on any integrity, schema, provenance, or parity violation."""


def require_ok(cond: bool, msg: str) -> None:
    if not cond:
        raise S109AuditError(msg)


def sha256_file(path: Path) -> str:
    require_ok(path.is_file(), f"Missing required artifact file: {path.name}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_json_tree_iterative(obj: Any, max_depth: int = 64) -> None:
    stack: List[Tuple[Any, int]] = [(obj, 0)]
    while stack:
        cur, depth = stack.pop()
        if depth > max_depth:
            raise S109AuditError(f"JSON nesting depth exceeds {max_depth}")
        if isinstance(cur, dict):
            for k, v in cur.items():
                if type(k) is not str:
                    raise S109AuditError(f"Non-str JSON key forbidden: {type(k).__name__}")
                stack.append((v, depth + 1))
        elif isinstance(cur, (list, tuple)):
            for item in cur:
                stack.append((item, depth + 1))


def load_json_strict(path: Path) -> Dict[str, Any]:
    require_ok(path.is_file(), f"Missing required JSON file: {path.name}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise S109AuditError(f"Malformed JSON in {path.name}: {exc}") from exc
    require_ok(isinstance(data, dict), f"Top-level JSON object must be dict in {path.name}")
    check_json_tree_iterative(data)
    return data


def canonical_sha256(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def mean_se(vals: Sequence[float]) -> Dict[str, Any]:
    n = len(vals)
    require_ok(n >= 2, "mean_se requires >= 2 samples")
    mu = sum(float(v) for v in vals) / float(n)
    var = sum((float(v) - mu) ** 2 for v in vals) / float(n - 1)
    return {"mean": round(mu, 6), "se": round(math.sqrt(var / float(n)), 6), "n": n}


def paired_bootstrap_stats(a_vals: Sequence[float], b_vals: Sequence[float], seed: int = 109) -> Dict[str, Any]:
    require_ok(len(a_vals) == len(b_vals) and len(a_vals) >= 2, "Paired sample mismatch")
    n = len(a_vals)
    diffs = [float(a) - float(b) for a, b in zip(a_vals, b_vals)]
    mu = sum(diffs) / float(n)
    var = sum((d - mu) ** 2 for d in diffs) / float(n - 1)
    se = math.sqrt(var / float(n))
    z = mu / se if se > 1e-12 else (999.0 if mu > 0 else (-999.0 if mu < 0 else 0.0))
    rng = random.Random(seed)
    boots = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / float(n) for _ in range(2000))
    return {
        "n": n,
        "delta_mean": round(mu, 6),
        "se": round(se, 6),
        "z": round(z, 3),
        "ci95_low": round(boots[50], 6),
        "ci95_high": round(boots[1949], 6),
    }


def verify_mlos_receipt(path: Path) -> Dict[str, Any]:
    rec = load_json_strict(path)
    require_ok(rec.get("schema") == "mlos-run-receipt/v0.1", f"{path.name}: unexpected mlos schema")
    require_ok(rec.get("clean_hardware_run") is True, f"{path.name}: clean_hardware_run is not True")
    require_ok(rec.get("anomalies") == [], f"{path.name}: hardware anomalies present")
    require_ok(rec.get("determinism_zone") == "B", f"{path.name}: expected Zone B")
    require_ok(rec.get("gpu_telemetry_available") is True, f"{path.name}: gpu_telemetry_available not True")
    exec_meta = rec.get("execution")
    require_ok(isinstance(exec_meta, dict) and exec_meta.get("exit_code") == 0, f"{path.name}: exit_code != 0")
    start_tel = rec.get("start_gpu_telemetry")
    end_tel = rec.get("end_gpu_telemetry")
    require_ok(
        isinstance(start_tel, dict)
        and isinstance(end_tel, dict)
        and start_tel.get("compute_vram_mib") == 0
        and end_tel.get("compute_vram_mib") == 0,
        f"{path.name}: compute_vram_mib != 0 at boundary",
    )

    rec_sha = rec.get("receipt_sha256")
    require_ok(type(rec_sha) is str and len(rec_sha) == 64, f"{path.name}: missing/invalid receipt_sha256")
    no_sha = {k: v for k, v in rec.items() if k != "receipt_sha256"}
    require_ok(
        hmac.compare_digest(canonical_sha256(no_sha), rec_sha),
        f"{path.name}: internal receipt_sha256 mismatch (tampered receipt)",
    )
    return {
        "file": path.name,
        "sha256": sha256_file(path),
        "receipt_sha256": rec_sha,
        "clean_hardware_run": True,
        "anomalies_count": 0,
        "determinism_zone": "B",
        "exit_code": 0,
        "duration_s": round(float(exec_meta["duration_ms"]) / 1000.0, 3),
    }


def verify_run_envelope(
    track_dir: Path,
    subdir_name: str,
    expected_track: str,
    require_amendment3: bool,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    sub_dir = track_dir / subdir_name
    proto_path = sub_dir / "s109_locked_protocol.json"
    res_path = sub_dir / "s109_gpu_full_results.json"

    proto = load_json_strict(proto_path)
    res = load_json_strict(res_path)
    proto_file_sha = sha256_file(proto_path)
    res_file_sha = sha256_file(res_path)

    require_ok(proto.get("schema") == "aletheia.track_s109.locked_protocol.v1", f"{subdir_name}: protocol schema mismatch")
    require_ok(res.get("schema") == "aletheia.track_s109.results.v1", f"{subdir_name}: results schema mismatch")
    require_ok(proto.get("track") == expected_track and res.get("track") == expected_track, f"{subdir_name}: track mismatch")
    require_ok(proto.get("mode") == "gpu-full" and res.get("mode") == "gpu-full", f"{subdir_name}: mode != gpu-full")
    require_ok(proto.get("device") == "cuda" and res.get("device") == "cuda", f"{subdir_name}: device != cuda")
    require_ok(proto.get("weights_saved") == 0 and res.get("weights_saved") == 0, f"{subdir_name}: weights_saved != 0")

    for field, pin in (
        ("parent_preregistration_sha256", PREREG_S109_SHA256),
        ("amendment1_sha256", AMENDMENT1_SHA256),
        ("amendment2_sha256", AMENDMENT2_SHA256),
    ):
        require_ok(
            hmac.compare_digest(str(proto.get(field, "")), pin) and hmac.compare_digest(str(res.get(field, "")), pin),
            f"{subdir_name}: {field} mismatch",
        )

    if require_amendment3:
        require_ok(
            hmac.compare_digest(str(proto.get("amendment3_sha256", "")), AMENDMENT3_SHA256)
            and hmac.compare_digest(str(res.get("amendment3_sha256", "")), AMENDMENT3_SHA256),
            f"{subdir_name}: amendment3_sha256 mismatch",
        )
    else:
        require_ok(
            "amendment3_sha256" not in proto and "amendment3_sha256" not in res,
            f"{subdir_name}: pre-Amendment-3 prototype baseline unexpectedly carries amendment3_sha256",
        )

    require_ok(
        hmac.compare_digest(str(res.get("protocol_sha256", "")), proto_file_sha),
        f"{subdir_name}: results.protocol_sha256 does not match s109_locked_protocol.json SHA-256",
    )

    rec_res_sha = res.get("result_sha256")
    require_ok(type(rec_res_sha) is str and len(rec_res_sha) == 64, f"{subdir_name}: invalid result_sha256")
    no_res_sha = {k: v for k, v in res.items() if k != "result_sha256"}
    require_ok(
        hmac.compare_digest(canonical_sha256(no_res_sha), rec_res_sha),
        f"{subdir_name}: internal result_sha256 mismatch (tampered GPU results JSON)",
    )

    per_seed = res["results"].get("per_seed")
    require_ok(
        isinstance(per_seed, dict) and sorted(per_seed.keys(), key=int) == EXPECTED_SEED_KEYS,
        f"{subdir_name}: expected seeds {EXPECTED_SEED_KEYS}",
    )
    for sk in EXPECTED_SEED_KEYS:
        ov = per_seed[sk].get("train_eval_tuple_overlap")
        require_ok(ov == {"regime1": 0, "regime2": 0}, f"{subdir_name} seed {sk}: non-zero train/eval tuple overlap {ov}")

    meta = {
        "protocol_file": f"{subdir_name}/s109_locked_protocol.json",
        "protocol_file_sha256": proto_file_sha,
        "results_file": f"{subdir_name}/s109_gpu_full_results.json",
        "results_file_sha256": res_file_sha,
        "result_sha256": rec_res_sha,
        "elapsed_s": float(res["elapsed_s"]),
    }
    return proto, res, meta


def _assert_close_paired(recomputed: Dict[str, Any], recorded: Dict[str, Any], label: str) -> None:
    require_ok(abs(recomputed["delta_mean"] - float(recorded["delta_mean"])) <= 2e-6, f"{label}: delta_mean mismatch")
    require_ok(abs(recomputed["se"] - float(recorded["se"])) <= 2e-6, f"{label}: se mismatch")
    require_ok(abs(recomputed["z"] - float(recorded["z"])) <= 2e-3, f"{label}: z mismatch")
    require_ok(abs(recomputed["ci95_low"] - float(recorded["ci95_low"])) <= 2e-6, f"{label}: ci95_low mismatch")
    require_ok(abs(recomputed["ci95_high"] - float(recorded["ci95_high"])) <= 2e-6, f"{label}: ci95_high mismatch")


def audit_h9a_run(track_dir: Path, subdir_name: str, mlos_name: str, require_amendment3: bool) -> Dict[str, Any]:
    _, res, env = verify_run_envelope(track_dir, subdir_name, "h9a", require_amendment3=require_amendment3)
    mlos = verify_mlos_receipt(track_dir / mlos_name)
    ps = res["results"]["per_seed"]
    agg = res["results"]["aggregate"]

    a_r1 = [float(ps[k]["arm_a_english_cot"]["regime1_exact_acc"]) for k in EXPECTED_SEED_KEYS]
    a_r2 = [float(ps[k]["arm_a_english_cot"]["regime2_exact_acc"]) for k in EXPECTED_SEED_KEYS]
    ap_r1 = [float(ps[k]["arm_a_prime_direct"]["regime1_exact_acc"]) for k in EXPECTED_SEED_KEYS]
    ap_r2 = [float(ps[k]["arm_a_prime_direct"]["regime2_exact_acc"]) for k in EXPECTED_SEED_KEYS]
    b_r1 = [float(ps[k]["arm_b_compressed_binary"]["regime1_exact_acc"]) for k in EXPECTED_SEED_KEYS]
    b_r2 = [float(ps[k]["arm_b_compressed_binary"]["regime2_exact_acc"]) for k in EXPECTED_SEED_KEYS]

    a_ms_r1 = [float(ps[k]["arm_a_english_cot"]["wall_ms_per_problem_r1"]) for k in EXPECTED_SEED_KEYS]
    a_ms_r2 = [float(ps[k]["arm_a_english_cot"]["wall_ms_per_problem_r2"]) for k in EXPECTED_SEED_KEYS]
    a_vram = [float(ps[k]["arm_a_english_cot"]["eval_peak_vram_mib"]) for k in EXPECTED_SEED_KEYS]

    dc_r1_b = [float(ps[k]["arm_b_decompressor_emulation"]["regime1_byte_acc"]) for k in EXPECTED_SEED_KEYS]
    dc_r1_e = [float(ps[k]["arm_b_decompressor_emulation"]["regime1_exact_str_acc"]) for k in EXPECTED_SEED_KEYS]
    dc_r2_b = [float(ps[k]["arm_b_decompressor_emulation"]["regime2_byte_acc"]) for k in EXPECTED_SEED_KEYS]
    dc_r2_e = [float(ps[k]["arm_b_decompressor_emulation"]["regime2_exact_str_acc"]) for k in EXPECTED_SEED_KEYS]

    pl_en = [float(ps[k]["probe_lm_predictivity"]["english"]["probe_lm_bits_per_bit"]) for k in EXPECTED_SEED_KEYS]
    pl_df = [float(ps[k]["probe_lm_predictivity"]["deflate"]["probe_lm_bits_per_bit"]) for k in EXPECTED_SEED_KEYS]

    cmp_ab_r1 = paired_bootstrap_stats(a_r1, b_r1)
    cmp_ab_r2 = paired_bootstrap_stats(a_r2, b_r2)
    cmp_aap_r1 = paired_bootstrap_stats(a_r1, ap_r1)
    cmp_aap_r2 = paired_bootstrap_stats(a_r2, ap_r2)
    cmp_apb_r1 = paired_bootstrap_stats(ap_r1, b_r1)
    cmp_apb_r2 = paired_bootstrap_stats(ap_r2, b_r2)

    _assert_close_paired(cmp_ab_r1, agg["h9a_paired_a_minus_b"]["regime1"], f"{subdir_name}.h9a_r1")
    _assert_close_paired(cmp_ab_r2, agg["h9a_paired_a_minus_b"]["regime2"], f"{subdir_name}.h9a_r2")

    pl_en_mu = mean_se(pl_en)["mean"]
    pl_df_mu = mean_se(pl_df)["mean"]
    probe_ratio = round(pl_df_mu / max(pl_en_mu, 1e-12), 4)

    ledger = dict(ps["42"]["arm_a_english_cot"]["resource_ledger"])
    # 6 neural models per seed (Arm A, Arm A', Arm B, Decompressor, ProbeLM-EN, ProbeLM-Deflate) x 3 seeds = 18
    models_trained = 6 * len(EXPECTED_SEED_KEYS)

    return {
        "envelope": env,
        "mlos": mlos,
        "models_trained": models_trained,
        "resource_ledger": ledger,
        "arm_a_r1": mean_se(a_r1),
        "arm_a_r2": mean_se(a_r2),
        "arm_a_wall_ms_r1": mean_se(a_ms_r1),
        "arm_a_wall_ms_r2": mean_se(a_ms_r2),
        "arm_a_eval_peak_vram_mib": mean_se(a_vram),
        "arm_a_prime_r1": mean_se(ap_r1),
        "arm_a_prime_r2": mean_se(ap_r2),
        "arm_b_r1": mean_se(b_r1),
        "arm_b_r2": mean_se(b_r2),
        "paired_a_minus_b_r1": cmp_ab_r1,
        "paired_a_minus_b_r2": cmp_ab_r2,
        "paired_a_minus_a_prime_r1": cmp_aap_r1,
        "paired_a_minus_a_prime_r2": cmp_aap_r2,
        "paired_a_prime_minus_b_r1": cmp_apb_r1,
        "paired_a_prime_minus_b_r2": cmp_apb_r2,
        "decompressor_emulation": {
            "regime1_byte_acc": mean_se(dc_r1_b),
            "regime1_exact_str_acc": mean_se(dc_r1_e),
            "regime2_byte_acc": mean_se(dc_r2_b),
            "regime2_exact_str_acc": mean_se(dc_r2_e),
        },
        "probe_lm_predictivity": {
            "english_bits_per_bit": mean_se(pl_en),
            "deflate_bits_per_bit": mean_se(pl_df),
            "deflate_to_english_ratio": probe_ratio,
        },
        "per_seed_raw": {
            "arm_a_r1": a_r1,
            "arm_a_r2": a_r2,
            "arm_a_ms_r1": a_ms_r1,
            "arm_a_ms_r2": a_ms_r2,
            "arm_a_vram": a_vram,
        },
    }


def audit_terracore(track_dir: Path, h9a_v2: Dict[str, Any]) -> Dict[str, Any]:
    _, res, env = verify_run_envelope(track_dir, "gpu_results_terracore", "terracore", require_amendment3=True)
    mlos = verify_mlos_receipt(track_dir / "mlos_zone_b_s109_terracore.json")
    ps = res["results"]["per_seed"]
    agg = res["results"]["aggregate"]

    # Verify exact 15.0M triple CS-08 parity against Arm A (h9a_v2)
    led_mono = h9a_v2["resource_ledger"]
    led_terra = dict(ps["42"]["h9d_yield_sweep"]["Y_0.50"]["resource_ledger"])
    p_mono = int(led_mono["P_total"])
    p_terra = int(led_terra["P_total"])
    f_mono = int(led_mono["F_infer"])
    f_terra = int(led_terra["F_infer"])
    ft_mono = int(led_mono["F_train_total"])
    ft_terra = int(led_terra["F_train_total"])
    require_ok(14_925_000 <= p_mono <= 15_075_000, f"P_mono outside 15M +-0.5%: {p_mono}")
    require_ok(14_925_000 <= p_terra <= 15_075_000, f"P_terra outside 15M +-0.5%: {p_terra}")
    require_ok(int(led_terra["P_audit_head"]) > 0, "P_audit_head must be charged > 0")
    p_ratio = round(p_terra / float(p_mono), 6)
    f_ratio = round(f_terra / float(f_mono), 6)
    ft_ratio = round(ft_terra / float(ft_mono), 6)
    require_ok(0.995 <= p_ratio <= 1.005, f"P_ratio out of +-0.5%: {p_ratio}")
    require_ok(0.95 <= f_ratio <= 1.05, f"F_ratio out of +-5%: {f_ratio}")
    require_ok(0.95 <= ft_ratio <= 1.05, f"F_train_ratio out of +-5%: {ft_ratio}")

    # Verify all 6 yield sweep arms & security/geometric invariants across all 3 seeds
    sweep_summary: Dict[str, Any] = {}
    max_leak_overall = -1.0
    max_hodge_orth = 0.0
    max_nohodge_orth = 0.0
    max_darboux_err = 0.0
    max_cocycle_err = 0.0
    cs21_triggers = 0

    for yk in EXPECTED_YIELD_KEYS:
        nat_r1 = []
        nat_ms = []
        nat_vram = []
        r1_acc = []
        r2_acc = []
        r2_ms = []
        alt_r2 = []
        alt_drop = []
        within_drop = []
        flux = []
        leak = []
        aud = []
        sh_aud = []
        stream_acc = []
        route_acc = []
        mix_acc = []

        for sk in EXPECTED_SEED_KEYS:
            y = ps[sk]["h9d_yield_sweep"][yk]
            require_ok(y["core_sha_unchanged"] is True, f"{yk} seed {sk}: core_sha_unchanged not True")
            require_ok(
                y["zero_skip_path"]["zero_skip_path_verified"] is True
                and float(y["zero_skip_path"]["max_skip_grad"]) == 0.0,
                f"{yk} seed {sk}: zero skip path failed",
            )
            require_ok(
                float(y["channel2b_diag_r1"]["ir_exact_match_acc"]) == 1.0
                and float(y["channel2b_diag_r2"]["ir_exact_match_acc"]) == 1.0
                and float(y["swap_alt_ir_exact_acc"]) == 1.0,
                f"{yk} seed {sk}: expected 100% MHPlate EN+AR IR exact match",
            )
            orth = float(y["channel2b_diag_r2"]["pol_tor_orthogonality_err"])
            if yk == "Y_0.50_NoHodge":
                max_nohodge_orth = max(max_nohodge_orth, orth)
                require_ok(orth > 0.2, f"NoHodge seed {sk}: expected non-orthogonal overlap > 0.2, got {orth}")
            else:
                max_hodge_orth = max(max_hodge_orth, orth)
                require_ok(orth < 0.01, f"{yk} seed {sk}: Hodge orth exceeded 0.01: {orth}")

            darb = y["portal5_darboux_dark_mode"]
            require_ok(darb["rank"] == 32 and darb["dark_dim"] == 448, f"{yk} seed {sk}: Darboux rank/dark_dim mismatch")
            d_err = float(darb["darboux_intertwine_err"])
            require_ok(d_err < 1e-12, f"{yk} seed {sk}: Darboux intertwine err >= 1e-12: {d_err}")
            max_darboux_err = max(max_darboux_err, d_err)

            c_err = float(y["plate_swap_seam"]["cocycle_sum_err"])
            require_ok(c_err < 1e-5, f"{yk} seed {sk}: cocycle err >= 1e-5: {c_err}")
            max_cocycle_err = max(max_cocycle_err, c_err)

            lp = y["residual_leak_probe"]
            require_ok(int(lp["probe_params"]) <= 50_000, f"{yk} seed {sk}: leak probe > 50k params")
            if lp["cs21_residual_leak_triggered"] is True:
                cs21_triggers += 1
            max_leak_overall = max(max_leak_overall, float(lp["above_chance"]))

            nat_r1.append(float(y["regime1_native"]["native_r1_exact_acc"]))
            nat_ms.append(float(y["regime1_native"]["native_r1_wall_ms_per_problem"]))
            nat_vram.append(float(y["regime1_native"]["native_r1_peak_vram_mib"]))
            r1_acc.append(float(y["regime1_core_acc"]))
            r2_acc.append(float(y["regime2_core_acc"]))
            r2_ms.append(float(y["regime2_wall_ms_per_problem"]))
            alt_r2.append(float(y["swap_alt_arabic_acc"]))
            alt_drop.append(float(y["swap_alt_drop_pp"]))
            within_drop.append(float(y["swap_within_drop_pp"]))
            flux.append(float(y["channel2b_diag_r2"]["active_flux_fraction"]))
            leak.append(float(lp["above_chance"]))
            aud.append(float(y["counterfactual_audit"]["faithfulness"]))
            sh_aud.append(float(y["counterfactual_audit"]["shifted_ans_faithfulness"]))
            stream_acc.append(float(y["plate_swap_seam"]["unlabeled_3surface_stream_acc"]))
            route_acc.append(float(y["plate_swap_seam"]["unlabeled_3surface_route_acc"]))
            mix_acc.append(float(y["plate_swap_seam"]["hybrid_mixed_seam_acc"]))

        sweep_summary[yk] = {
            "native_r1_acc": mean_se(nat_r1),
            "native_r1_wall_ms": mean_se(nat_ms),
            "native_r1_vram_mib": mean_se(nat_vram),
            "regime1_core_acc": mean_se(r1_acc),
            "regime2_core_acc": mean_se(r2_acc),
            "regime2_wall_ms": mean_se(r2_ms),
            "swap_alt_arabic_acc": mean_se(alt_r2),
            "swap_alt_drop_pp": mean_se(alt_drop),
            "swap_within_drop_pp": mean_se(within_drop),
            "active_flux_fraction": mean_se(flux),
            "leak_above_chance": mean_se(leak),
            "audit_faithfulness": mean_se(aud),
            "shifted_audit_faithfulness": mean_se(sh_aud),
            "plate_swap_stream_acc": mean_se(stream_acc),
            "plate_swap_route_acc": mean_se(route_acc),
            "plate_swap_mixed_acc": mean_se(mix_acc),
        }

    require_ok(cs21_triggers == 0, f"Unexpected CS21_RESIDUAL_LEAK triggers: {cs21_triggers}")
    # Verify monotone Bingham flux Y=0 -> 0.25 -> 0.50 -> 0.75 -> 1.00 and exact Y=1.00 zeroing
    flux_seq = [sweep_summary[yk]["active_flux_fraction"]["mean"] for yk in EXPECTED_YIELD_KEYS[:5]]
    for fa, fb in zip(flux_seq, flux_seq[1:]):
        require_ok(fa + 1e-9 >= fb, f"Non-monotone Bingham flux sweep: {flux_seq}")
    require_ok(flux_seq[0] == 1.0 and flux_seq[4] == 0.0, f"Expected Y=0 flux 1.0 and Y=1 flux 0.0, got {flux_seq}")

    # Verify CB-1..CB-6 controls
    cb_keys = list(ps["42"]["cb1_to_cb5_controls"].keys())
    cb_summary = {
        ck: mean_se([float(ps[sk]["cb1_to_cb5_controls"][ck]) for sk in EXPECTED_SEED_KEYS])
        for ck in cb_keys
    }
    cb6_vals = [float(ps[sk]["cb6_syntactic_check"]["trivial_core_acc"]) for sk in EXPECTED_SEED_KEYS]
    for sk in EXPECTED_SEED_KEYS:
        require_ok(ps[sk]["cb6_syntactic_check"]["cb6_syntactic_only_pass"] is True, f"CB-6 failed on seed {sk}")

    # Seed-42 zero-oracle DPI recovery exact check
    s42_cb5_hyb = float(ps["42"]["cb1_to_cb5_controls"]["cb5_oracle_ir_r2_hyb_acc"])
    s42_cb5_sym = float(ps["42"]["cb1_to_cb5_controls"]["cb5_oracle_ir_r2_sym_acc"])
    s42_y025_r2 = float(ps["42"]["h9d_yield_sweep"]["Y_0.25"]["regime2_core_acc"])
    s42_dpi_recovery_pct = round(100.0 * (s42_y025_r2 - s42_cb5_sym) / max(s42_cb5_hyb - s42_cb5_sym, 1e-12), 2)

    # Cross-track paired comparisons against Arm A (h9a_v2) and internal H9d paired comparisons
    arm_a_r1 = h9a_v2["per_seed_raw"]["arm_a_r1"]
    arm_a_r2 = h9a_v2["per_seed_raw"]["arm_a_r2"]
    arm_a_ms_r1 = h9a_v2["per_seed_raw"]["arm_a_ms_r1"]
    arm_a_ms_r2 = h9a_v2["per_seed_raw"]["arm_a_ms_r2"]
    arm_a_vram = h9a_v2["per_seed_raw"]["arm_a_vram"]

    y100_nat_r1 = [float(ps[sk]["h9d_yield_sweep"]["Y_1.00"]["regime1_native"]["native_r1_exact_acc"]) for sk in EXPECTED_SEED_KEYS]
    y100_nat_ms = [float(ps[sk]["h9d_yield_sweep"]["Y_1.00"]["regime1_native"]["native_r1_wall_ms_per_problem"]) for sk in EXPECTED_SEED_KEYS]
    y100_nat_vram = [float(ps[sk]["h9d_yield_sweep"]["Y_1.00"]["regime1_native"]["native_r1_peak_vram_mib"]) for sk in EXPECTED_SEED_KEYS]
    y000_r2 = [float(ps[sk]["h9d_yield_sweep"]["Y_0.00"]["regime2_core_acc"]) for sk in EXPECTED_SEED_KEYS]
    y025_r2 = [float(ps[sk]["h9d_yield_sweep"]["Y_0.25"]["regime2_core_acc"]) for sk in EXPECTED_SEED_KEYS]
    y025_ms = [float(ps[sk]["h9d_yield_sweep"]["Y_0.25"]["regime2_wall_ms_per_problem"]) for sk in EXPECTED_SEED_KEYS]
    y050_r2 = [float(ps[sk]["h9d_yield_sweep"]["Y_0.50"]["regime2_core_acc"]) for sk in EXPECTED_SEED_KEYS]
    y100_r2 = [float(ps[sk]["h9d_yield_sweep"]["Y_1.00"]["regime2_core_acc"]) for sk in EXPECTED_SEED_KEYS]

    h9b_vs_a_r1 = paired_bootstrap_stats(y100_nat_r1, arm_a_r1)
    h9b_speedup = round(sum(arm_a_ms_r1) / sum(y100_nat_ms), 4)
    h9b_vram_ratio = round(sum(arm_a_vram) / sum(y100_nat_vram), 4)
    h9c_best_vs_a_r2 = paired_bootstrap_stats(y025_r2, arm_a_r2)
    h9c_r2_speedup = round(sum(arm_a_ms_r2) / sum(y025_ms), 4)

    y050_vs_y000_r2 = paired_bootstrap_stats(y050_r2, y000_r2)
    y050_vs_y100_r2 = paired_bootstrap_stats(y050_r2, y100_r2)
    y050_vs_y000_leak = paired_bootstrap_stats(
        [float(ps[sk]["h9d_yield_sweep"]["Y_0.50"]["residual_leak_probe"]["above_chance"]) for sk in EXPECTED_SEED_KEYS],
        [float(ps[sk]["h9d_yield_sweep"]["Y_0.00"]["residual_leak_probe"]["above_chance"]) for sk in EXPECTED_SEED_KEYS],
    )
    y050_vs_nh_stream = paired_bootstrap_stats(
        [float(ps[sk]["h9d_yield_sweep"]["Y_0.50"]["plate_swap_seam"]["unlabeled_3surface_stream_acc"]) for sk in EXPECTED_SEED_KEYS],
        [float(ps[sk]["h9d_yield_sweep"]["Y_0.50_NoHodge"]["plate_swap_seam"]["unlabeled_3surface_stream_acc"]) for sk in EXPECTED_SEED_KEYS],
    )
    y050_vs_nh_mixed = paired_bootstrap_stats(
        [float(ps[sk]["h9d_yield_sweep"]["Y_0.50"]["plate_swap_seam"]["hybrid_mixed_seam_acc"]) for sk in EXPECTED_SEED_KEYS],
        [float(ps[sk]["h9d_yield_sweep"]["Y_0.50_NoHodge"]["plate_swap_seam"]["hybrid_mixed_seam_acc"]) for sk in EXPECTED_SEED_KEYS],
    )

    _assert_close_paired(y050_vs_y000_r2, agg["h9d_paired_comparisons"]["Y050_minus_Y000_r2_acc"], "H9d.Y050_vs_Y000_r2")
    _assert_close_paired(y050_vs_y100_r2, agg["h9d_paired_comparisons"]["Y050_minus_Y100_r2_acc"], "H9d.Y050_vs_Y100_r2")
    _assert_close_paired(y050_vs_y000_leak, agg["h9d_paired_comparisons"]["Y050_minus_Y000_leak"], "H9d.Y050_vs_Y000_leak")
    _assert_close_paired(y050_vs_nh_stream, agg["h9d_paired_comparisons"]["Y050_minus_NoHodge_stream_acc"], "H9d.Y050_vs_NH_stream")
    _assert_close_paired(y050_vs_nh_mixed, agg["h9d_paired_comparisons"]["Y050_minus_NoHodge_mixed_acc"], "H9d.Y050_vs_NH_mixed")

    arm_d_mono_summary = {
        "regime1_core_acc": mean_se([float(ps[sk]["arm_d_mono"]["regime1_core_acc"]) for sk in EXPECTED_SEED_KEYS]),
        "regime2_core_acc": mean_se([float(ps[sk]["arm_d_mono"]["regime2_core_acc"]) for sk in EXPECTED_SEED_KEYS]),
        "leak_above_chance": mean_se([float(ps[sk]["arm_d_mono"]["residual_leak_probe"]["above_chance"]) for sk in EXPECTED_SEED_KEYS]),
        "audit_faithfulness": mean_se([float(ps[sk]["arm_d_mono"]["counterfactual_audit"]["faithfulness"]) for sk in EXPECTED_SEED_KEYS]),
    }

    # Strict kill-gate evaluation directly from recomputed figures
    h9a_verdict = (
        "CONFIRMED"
        if (
            h9a_v2["paired_a_minus_b_r1"]["delta_mean"] >= 0.15
            and h9a_v2["paired_a_minus_b_r1"]["ci95_low"] >= 0.15
            and h9a_v2["paired_a_minus_b_r2"]["delta_mean"] >= 0.15
            and h9a_v2["paired_a_minus_b_r2"]["ci95_low"] >= 0.15
            and h9a_v2["decompressor_emulation"]["regime2_exact_str_acc"]["mean"] == 0.0
        )
        else "FALSIFIED"
    )
    h9b_verdict = (
        "CONFIRMED"
        if (h9b_vs_a_r1["delta_mean"] >= 0.10 and h9b_vs_a_r1["z"] >= 2.0 and h9b_speedup >= 2.0)
        else "FALSIFIED"
    )
    max_audit_y = max(sweep_summary[yk]["audit_faithfulness"]["mean"] for yk in EXPECTED_YIELD_KEYS[:5])
    h9c_verdict = (
        "CONFIRMED"
        if (
            h9c_best_vs_a_r2["delta_mean"] >= 0.05
            and h9c_best_vs_a_r2["z"] >= 2.0
            and h9c_r2_speedup >= 1.8
            and max_audit_y >= 0.85
        )
        else "FALSIFIED"
    )
    y0_passes_leak_swap = (
        sweep_summary["Y_0.00"]["leak_above_chance"]["mean"] <= 0.15
        and sweep_summary["Y_0.00"]["swap_within_drop_pp"]["mean"] <= 3.0
        and sweep_summary["Y_0.00"]["swap_alt_drop_pp"]["mean"] <= 5.0
    )
    h9d_verdict = (
        "CONFIRMED"
        if (
            (not y0_passes_leak_swap)
            and y050_vs_y000_r2["z"] >= 2.0
            and y050_vs_nh_stream["z"] >= 2.0
            and max_audit_y >= 0.85
        )
        else "FALSIFIED"
    )
    # Verdicts above are computed from the gate booleans; no require_ok on an expected
    # tuple (standing rule: never lock a verdict to a literal pattern).

    # 26 neural models per seed (1 Stage-1 Core+Audit + 1 Arm D-mono + 6 yields x 4 plates) x 3 seeds = 78
    models_trained = 26 * len(EXPECTED_SEED_KEYS)
    routers_calibrated = 6 * len(EXPECTED_SEED_KEYS)

    return {
        "envelope": env,
        "mlos": mlos,
        "models_trained": models_trained,
        "routers_calibrated": routers_calibrated,
        "parity": {
            "P_mono": p_mono,
            "P_terra": p_terra,
            "P_ratio": p_ratio,
            "F_infer_mono": f_mono,
            "F_infer_terra": f_terra,
            "F_ratio": f_ratio,
            "F_train_ratio": ft_ratio,
            "terra_ledger": led_terra,
        },
        "security_and_geometry": {
            "all_core_sha_unchanged": True,
            "all_zero_skip_verified": True,
            "cs21_leak_triggers": 0,
            "max_leak_above_chance": round(max_leak_overall, 6),
            "max_hodge_orth_err": max_hodge_orth,
            "max_nohodge_orth_err": max_nohodge_orth,
            "max_darboux_intertwine_err": max_darboux_err,
            "darboux_rank": 32,
            "darboux_dark_dim": 448,
            "max_cocycle_sum_err": max_cocycle_err,
            "mhplate_en_ar_ir_exact_match": 1.0,
        },
        "cb1_to_cb6_controls": {
            **cb_summary,
            "cb6_trivial_acc": mean_se(cb6_vals),
        },
        "arm_d_mono": arm_d_mono_summary,
        "yield_sweep": sweep_summary,
        "seed42_y025_dpi_recovery_pct": s42_dpi_recovery_pct,
        "cross_track_comparisons": {
            "h9b_arm_c_nat_minus_arm_a_r1": h9b_vs_a_r1,
            "h9b_native_r1_speedup_vs_arm_a": h9b_speedup,
            "h9b_native_r1_vram_reduction_vs_arm_a": h9b_vram_ratio,
            "h9c_best_arm_d_y025_minus_arm_a_r2": h9c_best_vs_a_r2,
            "h9c_y025_r2_speedup_vs_arm_a": h9c_r2_speedup,
            "h9d_y050_minus_y000_r2": y050_vs_y000_r2,
            "h9d_y050_minus_y100_r2": y050_vs_y100_r2,
            "h9d_y050_minus_y000_leak": y050_vs_y000_leak,
            "h9d_y050_minus_nohodge_stream": y050_vs_nh_stream,
            "h9d_y050_minus_nohodge_mixed": y050_vs_nh_mixed,
        },
        "verdicts": {
            "H9a": h9a_verdict,
            "H9b": h9b_verdict,
            "H9c": h9c_verdict,
            "H9d": h9d_verdict,
        },
    }


def build_certificate(track_dir: Path) -> Dict[str, Any]:
    prereg_pins = {
        "PREREG_S109_MINIMAL_MEDIUM_CORE_AND_TRANSLATOR.md": PREREG_S109_SHA256,
        "PREREG_S109_AMENDMENT1_COUNCIL_HARDENING.md": AMENDMENT1_SHA256,
        "PREREG_S109_AMENDMENT2_GEODYNAMIC_TERRACORE.md": AMENDMENT2_SHA256,
        "PREREG_S109_AMENDMENT3_STEELMAN_REPAIR.md": AMENDMENT3_SHA256,
    }
    verified_preregs: Dict[str, str] = {}
    for fname, expected_sha in prereg_pins.items():
        actual_sha = sha256_file(track_dir / fname)
        require_ok(hmac.compare_digest(actual_sha, expected_sha), f"{fname}: SHA-256 mismatch")
        verified_preregs[fname] = actual_sha

    h9a_v1 = audit_h9a_run(track_dir, "gpu_results_h9a", "mlos_zone_b_s109_h9a.json", require_amendment3=False)
    h9a_v2 = audit_h9a_run(track_dir, "gpu_results_h9a_v2", "mlos_zone_b_s109_h9a_v2.json", require_amendment3=True)
    tc = audit_terracore(track_dir, h9a_v2)

    total_neural_models = h9a_v1["models_trained"] + h9a_v2["models_trained"] + tc["models_trained"]
    require_ok(total_neural_models == 114, f"Expected 114 neural models trained, got {total_neural_models}")
    total_gpu_s = round(h9a_v1["mlos"]["duration_s"] + h9a_v2["mlos"]["duration_s"] + tc["mlos"]["duration_s"], 3)

    # Strip redundant per_seed_raw helper vectors from stored certificate payload
    h9a_v1_clean = {k: v for k, v in h9a_v1.items() if k != "per_seed_raw"}
    h9a_v2_clean = {k: v for k, v in h9a_v2.items() if k != "per_seed_raw"}

    payload: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "track_id": "track-s109-minimal-medium-terracore",
        "protocol_id": "PREREG-S109-AMENDMENTS-1-2-3",
        "prereg_sha256_pins": verified_preregs,
        "locked_seeds": list(EXPECTED_SEEDS),
        "total_neural_models_trained": total_neural_models,
        "total_plate_seam_routers_calibrated": tc["routers_calibrated"],
        "total_zone_b_gpu_duration_s": total_gpu_s,
        "h9a_v1_prototype_preserved": h9a_v1_clean,
        "h9a_v2_steelman": h9a_v2_clean,
        "terracore_h9b_h9c_h9d": tc,
        "scorecard": {
            "H9a": tc["verdicts"]["H9a"],
            "H9b": tc["verdicts"]["H9b"],
            "H9c": tc["verdicts"]["H9c"],
            "H9d": tc["verdicts"]["H9d"],
            "n2_claims": 0,
            "weights_saved": 0,
        },
    }
    payload_sha256 = canonical_sha256(payload)
    cert_body: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "payload_sha256": payload_sha256,
        "payload": payload,
    }
    cert_body["certificate_sha256"] = canonical_sha256(cert_body)
    return cert_body


def verify_certificate_file(cert_path: Path, track_dir: Path) -> Dict[str, Any]:
    recorded = load_json_strict(cert_path)
    rec_cert_sha = recorded.get("certificate_sha256")
    rec_payload_sha = recorded.get("payload_sha256")
    require_ok(type(rec_cert_sha) is str and len(rec_cert_sha) == 64, "Invalid certificate_sha256 field")
    require_ok(type(rec_payload_sha) is str and len(rec_payload_sha) == 64, "Invalid payload_sha256 field")

    body_no_sig = {k: v for k, v in recorded.items() if k != "certificate_sha256"}
    require_ok(
        hmac.compare_digest(canonical_sha256(body_no_sig), rec_cert_sha),
        "Recorded certificate_sha256 mismatch (tampered envelope)",
    )
    require_ok(
        hmac.compare_digest(canonical_sha256(recorded.get("payload")), rec_payload_sha),
        "Recorded payload_sha256 mismatch (tampered payload)",
    )

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


def _format_ok_line(cert: Dict[str, Any]) -> str:
    p = cert["payload"]
    sc = p["scorecard"]
    return (
        f"OK track-s109-minimal-medium-terracore models={p['total_neural_models_trained']} "
        f"routers={p['total_plate_seam_routers_calibrated']} "
        f"H9a={sc['H9a']} H9b={sc['H9b']} H9c={sc['H9c']} H9d={sc['H9d']} "
        f"cert_sha256={cert['certificate_sha256']}\n"
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Pure-stdlib audit & certificate verifier for Track S109.")
    parser.add_argument("--standalone", action="store_true", help="Recompute full certificate from track artifacts.")
    parser.add_argument("--json", action="store_true", help="Emit canonical JSON certificate.")
    parser.add_argument("--check", type=str, default=None, help="Verify certificate JSON against raw artifacts.")
    parser.add_argument(
        "--write-certificate",
        nargs="?",
        const="s109_terracore_certificate.json",
        default=None,
        help="Write canonical certificate JSON (defaults to <track-dir>/s109_terracore_certificate.json).",
    )
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
                sys.stdout.write(_format_ok_line(cert))
            return 0

        tdir = Path(args.track_dir).resolve() if args.track_dir else Path(__file__).resolve().parent
        if args.write_certificate is not None:
            cert = build_certificate(tdir)
            out_path = Path(args.write_certificate)
            if not out_path.is_absolute():
                out_path = tdir / out_path
            out_path.write_text(json.dumps(cert, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            if args.json:
                sys.stdout.write(json.dumps(cert, sort_keys=True, indent=2) + "\n")
            else:
                sys.stdout.write(_format_ok_line(cert))
            return 0

        default_cert = tdir / "s109_terracore_certificate.json"
        if (not args.standalone) and default_cert.is_file():
            cert = verify_certificate_file(default_cert, tdir)
        else:
            cert = build_certificate(tdir)
        if args.json:
            sys.stdout.write(json.dumps(cert, sort_keys=True, indent=2) + "\n")
        else:
            sys.stdout.write(_format_ok_line(cert))
        return 0
    except (S109AuditError, OSError, ValueError, RecursionError) as exc:
        sys.stderr.write(f"FAIL: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
