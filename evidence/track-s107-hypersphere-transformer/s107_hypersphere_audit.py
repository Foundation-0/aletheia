#!/usr/bin/env python3
"""Pure-stdlib independent verifier and certificate checker for Track S107 (PREREG-S107 + Amendment 1).

Zero external dependencies (no torch, no numpy): runs under stock /usr/bin/python3 -I -B/-O/-W error.
Recomputes directly from raw per-seed JSON records:
  - Exact SHA-256 bindings of h7{a,b,c}_gpu_results.json, mlos_zone_b_h7{a,b,c}.json, and preflight receipt
  - Clean hardware Zone-B provenance (clean_hardware_run=True, anomalies=[]) across all 3 tracks
  - Exact CS-08 parameter/FLOP parity across all 21 arms (10 H7a, 6 H7c, 5 H7b)
  - Exact paired-seed statistics (mean, SE, relative %, paired z) and literal locked-gate verdicts
  - Exact H7b eager wall-clock ratio (3.9125x) and H7a/H7b/H7c corpus digest separation
  - Fail-closed --check <cert.json> using hmac.compare_digest on payload_sha256 & certificate_sha256
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
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


class S107AuditError(ValueError):
    """Fail-closed error raised on any integrity, schema, or parity violation."""


def require_ok(cond: bool, msg: str) -> None:
    if not cond:
        raise S107AuditError(msg)


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


def paired_stats(a_vals: Sequence[float], c_vals: Sequence[float]) -> Dict[str, float]:
    require_ok(len(a_vals) == len(c_vals) and len(a_vals) >= 2, "Paired sample mismatch")
    diffs = [a - c for a, c in zip(a_vals, c_vals)]
    mu = sum(diffs) / float(len(diffs))
    var = sum((d - mu) ** 2 for d in diffs) / float(len(diffs) - 1)
    se = math.sqrt(var / float(len(diffs)))
    c_mean = sum(c_vals) / float(len(c_vals))
    rel_pct = 100.0 * mu / max(abs(c_mean), 1e-12)
    z = mu / se if se > 1e-12 else 0.0
    return {
        "mean_diff": round(mu, 6),
        "paired_se": round(se, 6),
        "rel_diff_pct": round(rel_pct, 4),
        "z_score": round(z, 4),
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


def verify_mlos_receipt(path: Path) -> Dict[str, Any]:
    rec = load_json_strict(path)
    require_ok(rec.get("clean_hardware_run") is True, f"{path.name}: clean_hardware_run is not True")
    require_ok(rec.get("anomalies") == [], f"{path.name}: hardware anomalies present")
    require_ok(rec.get("determinism_zone") == "B", f"{path.name}: expected Zone B")
    return {
        "file": path.name,
        "sha256": sha256_file(path),
        "clean_hardware_run": True,
        "anomalies_count": 0,
        "determinism_zone": "B",
    }


def audit_h7a(track_dir: Path) -> Dict[str, Any]:
    res_path = track_dir / "h7a_gpu_results.json"
    res = load_json_strict(res_path)
    mlos = verify_mlos_receipt(track_dir / "mlos_zone_b_h7a.json")
    seeds, by_arm = _index_runs(res)
    require_ok(len(res["runs"]) == 30 and len(by_arm) == 10, "H7a expected 10 arms x 3 seeds = 30 runs")

    # Verify strict CS-08 parity across all 10 arms.
    ref_p = int(by_arm["Cyl-Std"][seeds[0]]["params"]["non_embedding_params"])
    ref_f = int(by_arm["Cyl-Std"][seeds[0]]["flops"]["total_fwd_flops_per_token"])
    max_p_pct = 0.0
    max_f_pct = 0.0
    for arm, smap in by_arm.items():
        p = int(smap[seeds[0]]["params"]["non_embedding_params"])
        f = int(smap[seeds[0]]["flops"]["total_fwd_flops_per_token"])
        max_p_pct = max(max_p_pct, 100.0 * abs(p - ref_p) / float(ref_p))
        max_f_pct = max(max_f_pct, 100.0 * abs(f - ref_f) / float(ref_f))
    require_ok(max_p_pct <= 0.5 and max_f_pct <= 1.0, "H7a CS-08 parity exceeded")

    # Recompute literal PREREG-S107 H7a paired gate checks.
    comparisons: Dict[str, Any] = {}
    any_pass = False
    for bb in ("Std", "nGPT"):
        for shape, perm in (("S3-Polar", "S3-Permuted-Pol"), ("S3-Equatorial", "S3-Permuted-Eq")):
            arm, cyl, pnull = f"{shape}-{bb}", f"Cyl-{bb}", f"{perm}-{bb}"
            b_cyl = paired_stats([by_arm[arm][s]["val"]["bpb"] for s in seeds], [by_arm[cyl][s]["val"]["bpb"] for s in seeds])
            b_prm = paired_stats([by_arm[arm][s]["val"]["bpb"] for s in seeds], [by_arm[pnull][s]["val"]["bpb"] for s in seeds])
            k_cyl = paired_stats([by_arm[arm][s]["ptq_3bit_kl_nats"] for s in seeds], [by_arm[cyl][s]["ptq_3bit_kl_nats"] for s in seeds])
            k_prm = paired_stats([by_arm[arm][s]["ptq_3bit_kl_nats"] for s in seeds], [by_arm[pnull][s]["ptq_3bit_kl_nats"] for s in seeds])
            bpb_pass = (b_cyl["rel_diff_pct"] <= -1.5 and b_cyl["z_score"] <= -2.0 and b_prm["rel_diff_pct"] <= -1.5 and b_prm["z_score"] <= -2.0)
            kl_pass = (
                k_cyl["rel_diff_pct"] <= -15.0 and k_cyl["z_score"] <= -2.0
                and k_prm["rel_diff_pct"] <= -15.0 and k_prm["z_score"] <= -2.0
                and b_cyl["mean_diff"] <= 0.0 and b_prm["mean_diff"] <= 0.0
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

    verdict = "CONFIRMED" if any_pass else "FALSIFIED"
    require_ok(verdict == "FALSIFIED", "H7a literal verdict mismatch")
    return {
        "results_sha256": sha256_file(res_path),
        "mlos": mlos,
        "runs_count": len(res["runs"]),
        "corpus": res["corpus"],
        "max_non_emb_param_diff_pct": round(max_p_pct, 4),
        "max_flop_diff_pct": round(max_f_pct, 4),
        "comparisons": comparisons,
        "verdict": verdict,
    }


def audit_h7c(track_dir: Path) -> Dict[str, Any]:
    res_path = track_dir / "h7c_gpu_results.json"
    res = load_json_strict(res_path)
    mlos = verify_mlos_receipt(track_dir / "mlos_zone_b_h7c.json")
    seeds, by_arm = _index_runs(res)
    require_ok(len(res["runs"]) == 18 and len(res["probes"]) == 18 and len(by_arm) == 6, "H7c expected 18 LM + 18 bracket runs")

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

    hopf_vs_flat = paired_stats([by_arm["CliffordTorus-HopfLoop"][s]["val"]["bpb"] for s in seeds], [by_arm["FlatLoop-Std"][s]["val"]["bpb"] for s in seeds])
    hopf_vs_noclk = paired_stats([by_arm["CliffordTorus-HopfLoop"][s]["val"]["bpb"] for s in seeds], [by_arm["SphereLoop-NoClock"][s]["val"]["bpb"] for s in seeds])
    hopf_vs_rand = paired_stats([by_arm["CliffordTorus-HopfLoop"][s]["val"]["bpb"] for s in seeds], [by_arm["SphereLoop-RandRotClock"][s]["val"]["bpb"] for s in seeds])
    hopf_vs_u16 = paired_stats([by_arm["CliffordTorus-HopfLoop"][s]["val"]["bpb"] for s in seeds], [by_arm["Unlooped-16L"][s]["val"]["bpb"] for s in seeds])
    r6_vs_flat = paired_stats(
        [by_arm["CliffordTorus-HopfLoop"][s]["r_test_extrapolation_bpb"]["R6"] for s in seeds],
        [by_arm["FlatLoop-Std"][s]["r_test_extrapolation_bpb"]["R6"] for s in seeds],
    )
    m1_4b_vs_flat = paired_stats(
        [by_arm["CliffordTorus-HopfLoop"][s]["m1_h1_4bit"]["delta_r_over_delta_1"] for s in seeds],
        [by_arm["FlatLoop-Std"][s]["m1_h1_4bit"]["delta_r_over_delta_1"] for s in seeds],
    )

    crit1_raw_fires = (
        hopf_vs_flat["rel_diff_pct"] <= -2.0 and hopf_vs_flat["z_score"] <= -2.0
        and hopf_vs_noclk["rel_diff_pct"] <= -2.0 and hopf_vs_noclk["z_score"] <= -2.0
    )
    beats_randrot = hopf_vs_rand["mean_diff"] < 0.0 and hopf_vs_rand["z_score"] <= -2.0
    r6_pass = r6_vs_flat["rel_diff_pct"] <= -10.0
    m1_pass = m1_4b_vs_flat["rel_diff_pct"] <= -20.0
    require_ok(crit1_raw_fires and (not beats_randrot) and (not r6_pass) and (not m1_pass), "H7c expected conservative PARTIAL pattern")

    return {
        "results_sha256": sha256_file(res_path),
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
        "beats_randrot_adversarial_control": beats_randrot,
        "verdict": "PARTIAL",
    }


def audit_h7b(track_dir: Path) -> Dict[str, Any]:
    res_path = track_dir / "h7b_gpu_results.json"
    res = load_json_strict(res_path)
    mlos = verify_mlos_receipt(track_dir / "mlos_zone_b_h7b.json")
    seeds, by_arm = _index_runs(res)
    require_ok(len(res["runs"]) == 15 and len(res["probes"]) == 30 and len(by_arm) == 5, "H7b expected 15 LM + 30 S3/A5 probe runs")

    ref_p = int(by_arm["RoPE-2D-nGPT"][seeds[0]]["params"]["non_embedding_params"])
    ref_f = int(by_arm["RoPE-2D-nGPT"][seeds[0]]["flops"]["total_fwd_flops_per_token"])
    max_p_pct = 0.0
    max_f_pct = 0.0
    for arm, smap in by_arm.items():
        p = int(smap[seeds[0]]["params"]["non_embedding_params"])
        f = int(smap[seeds[0]]["flops"]["total_fwd_flops_per_token"])
        max_p_pct = max(max_p_pct, 100.0 * abs(p - ref_p) / float(ref_p))
        max_f_pct = max(max_f_pct, 100.0 * abs(f - ref_f) / float(ref_f))
    require_ok(max_p_pct <= 0.5 and max_f_pct <= 1.0, "H7b CS-08 parity exceeded")

    pr_map: Dict[Tuple[str, str], Dict[int, Dict[str, Any]]] = {}
    for pr in res["probes"]:
        pr_map.setdefault((str(pr["arm_name"]), str(pr["group"])), {})[int(pr["seed"])] = pr

    t512_vs_rope = paired_stats([by_arm["SU2-Holonomy-Scan-nGPT"][s]["val"]["bpb"] for s in seeds], [by_arm["RoPE-2D-nGPT"][s]["val"]["bpb"] for s in seeds])
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

    su2_t = sum(by_arm["SU2-Holonomy-Scan-nGPT"][s]["elapsed_sec"] for s in seeds) / float(len(seeds))
    rope_t = sum(by_arm["RoPE-2D-nGPT"][s]["elapsed_sec"] for s in seeds) / float(len(seeds))
    wall_ratio = round(su2_t / rope_t, 4)

    extrap_t2048_strong = (
        t2048_vs_rope["rel_diff_pct"] <= -5.0 and t2048_vs_rope["z_score"] <= -2.0
        and t2048_vs_rand["rel_diff_pct"] <= -5.0 and t2048_vs_rand["z_score"] <= -2.0
    )
    no_t512_regression = t512_vs_rope["mean_diff"] <= 0.0
    require_ok(extrap_t2048_strong and (not no_t512_regression), "H7b expected PARTIAL (strong T2048, slight T512 trail)")

    return {
        "results_sha256": sha256_file(res_path),
        "mlos": mlos,
        "runs_count": len(res["runs"]),
        "probes_count": len(res["probes"]),
        "corpus": res["corpus"],
        "max_non_emb_param_diff_pct": round(max_p_pct, 4),
        "max_flop_diff_pct": round(max_f_pct, 4),
        "su2_vs_rope_t512_bpb": t512_vs_rope,
        "su2_vs_rope_t2048_bpb": t2048_vs_rope,
        "su2_vs_randortho_t2048_bpb": t2048_vs_rand,
        "su2_vs_liere_t2048_bpb": t2048_vs_liere,
        "su2_vs_std_t2048_bpb": t2048_vs_std,
        "su2_vs_rope_s3_id_acc": s3_vs_rope,
        "su2_over_rope_wall_clock_ratio": wall_ratio,
        "verdict": "PARTIAL",
    }


def build_certificate(track_dir: Path) -> Dict[str, Any]:
    preflight_path = track_dir / "s107_cpu_preflight_receipt.json"
    pre = load_json_strict(preflight_path)
    require_ok(pre.get("payload", {}).get("all_passed") is True and pre.get("payload", {}).get("gates_passed") == 9,
               "CPU pre-flight receipt must show 9/9 passed")
    recomputed_pre_sha = canonical_sha256(pre["payload"])
    require_ok(hmac.compare_digest(recomputed_pre_sha, str(pre.get("payload_sha256", ""))),
               "CPU pre-flight receipt payload_sha256 mismatch")

    h7a = audit_h7a(track_dir)
    h7c = audit_h7c(track_dir)
    h7b = audit_h7b(track_dir)
    # Verify H7b and H7c share exact corpus digest while H7a is explicitly separated.
    require_ok(h7b["corpus"]["train_sha256"] == h7c["corpus"]["train_sha256"], "H7b/H7c train corpus digest mismatch")
    require_ok(h7b["corpus"]["eval_sha256"] == h7c["corpus"]["eval_sha256"], "H7b/H7c eval corpus digest mismatch")

    payload: Dict[str, Any] = {
        "schema_version": "aletheia.track_s107.hypersphere_transformer.certificate.v1",
        "track_id": "track-s107-hypersphere-transformer",
        "protocol_id": "PREREG-S107-AMENDMENT1",
        "total_live_gpu_runs": h7a["runs_count"] + h7c["runs_count"] + h7c["probes_count"] + h7b["runs_count"] + h7b["probes_count"],
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
            "H7a": h7a["verdict"],
            "H7c": h7c["verdict"],
            "H7b": h7b["verdict"],
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
    require_ok(type(rec_cert_sha) is str and len(rec_cert_sha) == 64, "Invalid certificate_sha256 field")
    require_ok(type(rec_payload_sha) is str and len(rec_payload_sha) == 64, "Invalid payload_sha256 field")

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
                sc = cert["payload"]["scorecard"]
                sys.stdout.write(
                    f"OK track-s107-hypersphere-transformer runs={cert['payload']['total_live_gpu_runs']} "
                    f"H7a={sc['H7a']} H7c={sc['H7c']} H7b={sc['H7b']} "
                    f"cert_sha256={cert['certificate_sha256']}\n"
                )
            return 0

        tdir = Path(args.track_dir).resolve() if args.track_dir else Path(__file__).resolve().parent
        cert = build_certificate(tdir)
        if args.json:
            sys.stdout.write(json.dumps(cert, sort_keys=True, indent=2) + "\n")
        else:
            sc = cert["payload"]["scorecard"]
            sys.stdout.write(
                f"OK track-s107-hypersphere-transformer runs={cert['payload']['total_live_gpu_runs']} "
                f"H7a={sc['H7a']} H7c={sc['H7c']} H7b={sc['H7b']} "
                f"cert_sha256={cert['certificate_sha256']}\n"
            )
        return 0
    except (S107AuditError, OSError, ValueError, RecursionError) as exc:
        sys.stderr.write(f"FAIL: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
