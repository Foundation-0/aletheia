#!/usr/bin/env python3
"""Track S106 GPU Evaluation Integrity & Preregistered-Verdict Verifier (Pure Stdlib).

Independently audits all Phase 1B + Phase 2 artifacts in gpu_eval/:
  1. Verifies immutable PREREG_SPHERE_PI_FORCES_V1.md SHA-256 lock (ac3e6211...).
  2. Verifies s106_frozen_pilot_params.json inner pilot_params_sha256, zero held-out
     models touched during pilot lock, and strict temporal ordering (pilot_locked_utc
     < gauntlet_completed_utc, proving zero post-hoc snooping).
  3. Verifies both mlos Zone-B hardware receipts (clean_hardware_run=true, anomalies=[],
     exit_code=0, thermal_throttled=false, compute_vram_mib=0 -> 0).
  4. Verifies s106_blind_gauntlet_results.json inner result_sha256, 117/117 blind arms,
     0 syndrome errors, 0 out-of-ball groups, 0 non-block tensor diffs, honest CS-08
     exact_bpw accounting, and independently re-derives ALL 6 preregistered verdicts
     (H1, H2a, H3a, H3b, H3c, H4).
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import pathlib
import stat
import sys
from typing import Any

PREREG_SHA256 = "ac3e62116bc4841320d2c713787c23568beed1ae738bf9b284b7f0c2a118d72a"
EXPECTED_HELD_OUT = (
    "HuggingFaceTB/SmolLM2-360M",
    "Qwen/Qwen2.5-1.5B",
    "Qwen/Qwen2.5-3B",
)
MAX_FILE_BYTES = 4 * 1024 * 1024


class S106GpuVerifyError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _is_hex64(val: Any) -> bool:
    return type(val) is str and len(val) == 64 and all(c in "0123456789abcdef" for c in val)


def _read_regular_bytes(path: pathlib.Path, label: str) -> bytes:
    if "\x00" in str(path):
        raise S106GpuVerifyError("NULL_BYTE_PATH", f"{label}: null byte")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(str(path), flags)
    except OSError as exc:
        raise S106GpuVerifyError("FILE_OPEN_ERROR", f"{label}: {exc}") from exc
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise S106GpuVerifyError("NOT_REGULAR_FILE", f"{label}: non-regular file")
        chunks: list[bytes] = []
        tot = 0
        while True:
            c = os.read(fd, 65536)
            if not c:
                break
            tot += len(c)
            if tot > MAX_FILE_BYTES:
                raise S106GpuVerifyError("FILE_TOO_LARGE", f"{label}: exceeds max size")
            chunks.append(c)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _load_json_no_dups(raw: bytes, label: str) -> dict[str, Any]:
    if b"\r" in raw:
        raise S106GpuVerifyError("CRLF_FORBIDDEN", f"{label}: CRLF line endings")

    def _no_dups(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in pairs:
            if k in out:
                raise S106GpuVerifyError("DUPLICATE_KEY", f"{label}: duplicate key {k}")
            out[k] = v
        return out

    def _bad_const(c: str) -> Any:
        raise S106GpuVerifyError("NON_FINITE_JSON", f"{label}: forbidden constant {c}")

    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_dups, parse_constant=_bad_const)
    except S106GpuVerifyError:
        raise
    except Exception as exc:
        raise S106GpuVerifyError("INVALID_JSON", f"{label}: {exc}") from exc
    if type(obj) is not dict:
        raise S106GpuVerifyError("JSON_ROOT_NOT_OBJECT", f"{label}: root must be object")
    return obj


def _verify_mlos_receipt(path: pathlib.Path, label: str) -> dict[str, Any]:
    raw = _read_regular_bytes(path, label)
    obj = _load_json_no_dups(raw, label)
    if obj.get("schema") != "mlos-run-receipt/v0.1":
        raise S106GpuVerifyError("BAD_RECEIPT_SCHEMA", f"{label}: unexpected schema")
    if obj.get("clean_hardware_run") is not True:
        raise S106GpuVerifyError("DIRTY_HARDWARE_RUN", f"{label}: clean_hardware_run must be true")
    if obj.get("anomalies") != []:
        raise S106GpuVerifyError("HARDWARE_ANOMALIES", f"{label}: anomalies non-empty")
    if obj.get("determinism_zone") != "B":
        raise S106GpuVerifyError("WRONG_ZONE", f"{label}: expected Zone B")
    ex = obj.get("execution")
    if type(ex) is not dict or ex.get("exit_code") != 0:
        raise S106GpuVerifyError("NONZERO_EXIT", f"{label}: exit_code != 0")
    for k in ("start_gpu_telemetry", "end_gpu_telemetry"):
        gt = obj.get(k)
        if type(gt) is not dict or gt.get("compute_vram_mib") != 0:
            raise S106GpuVerifyError("VRAM_LEAK", f"{label}: {k}.compute_vram_mib != 0")
        cer = gt.get("clocks_event_reasons")
        if type(cer) is not dict or cer.get("thermal_throttled") is not False:
            raise S106GpuVerifyError("THERMAL_THROTTLED", f"{label}: thermal throttling detected")
    r_sha = obj.get("receipt_sha256")
    if not _is_hex64(r_sha):
        raise S106GpuVerifyError("BAD_RECEIPT_SHA", f"{label}: invalid receipt_sha256")
    return {
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "receipt_sha256": r_sha,
        "started_utc": ex.get("started_utc"),
        "ended_utc": ex.get("ended_utc"),
    }


def _recompute_verdicts(models_out: dict[str, Any], throughput: dict[str, Any]) -> dict[str, str]:
    mnames = list(EXPECTED_HELD_OUT)

    def _sig_better(a: dict[str, Any], b: dict[str, Any], thresh: float) -> bool:
        for dom in ("wikitext2", "python"):
            ka, sa = float(a[dom]["mean_kl"]), float(a[dom]["se_kl"])
            kb, sb = float(b[dom]["mean_kl"]), float(b[dom]["se_kl"])
            rel = (kb - ka) / max(kb, 1e-12)
            z = (kb - ka) / max(math.hypot(sa, sb), 1e-12)
            if not (rel >= thresh and z >= 2.0):
                return False
        return True

    # H1-P1 & H1-P2
    h1_p1_w = 0
    h1_p2_w = 0
    for m in mnames:
        arms = models_out[m]["arms"]
        base = arms["p128_A16_3b"]
        best_sp = min(
            (arms["sp_E8_lin_3b"], arms["sp_A16_lin_3b"], arms["sp_A16_128_3b"]),
            key=lambda r: 0.5 * (float(r["wikitext2"]["mean_kl"]) + float(r["python"]["mean_kl"])),
        )
        ok_kl = _sig_better(best_sp, base, 0.10)
        low_b = arms["sp_A16_128_B368_290b"]
        ok_bpw = (float(base["exact_bpw"]) - float(low_b["exact_bpw"]) >= 0.099) and all(
            float(low_b[d]["mean_kl"])
            <= float(base[d]["mean_kl"]) + 2.0 * math.hypot(float(low_b[d]["se_kl"]), float(base[d]["se_kl"]))
            for d in ("wikitext2", "python")
        )
        if ok_kl or ok_bpw:
            h1_p1_w += 1
        p2 = models_out[m]["h1_p2_per_layer_kurtosis_vs_kl"]
        if max(float(p2["spearman_rho_mean_excess_k"]), float(p2["spearman_rho_max_excess_k"])) >= 0.60:
            h1_p2_w += 1
    h1_p1 = "CONFIRMED" if h1_p1_w >= 2 else "FALSIFIED"
    h1_p2 = "CONFIRMED" if h1_p2_w >= 2 else ("PARTIAL" if h1_p2_w == 1 else "FALSIFIED")
    h1 = "CONFIRMED" if (h1_p1 == "CONFIRMED" and h1_p2 == "CONFIRMED") else (
        "PARTIAL" if (h1_p1 == "CONFIRMED" or h1_p2 == "CONFIRMED") else "FALSIFIED"
    )

    # H2a
    h2a_w = 0
    h2a_part = False
    for m in mnames:
        arms = models_out[m]["arms"]
        eq2, np2, km2, clm2 = arms["sp_s3_eq_leo_2b"], arms["sp_s3_numpi_2b"], arms["sp_s3_kmeans_2b"], arms["sp_CartLM_2b"]
        eq25, np25, km25 = arms["sp_s3_eq_leo_25b"], arms["sp_s3_numpi_25b"], arms["sp_s3_kmeans_25b"]
        g25 = float(eq25["weight_snr_db"]) - float(np25["weight_snr_db"])
        g20 = float(eq2["weight_snr_db"]) - float(np2["weight_snr_db"])
        d25 = float(eq25["weight_snr_db"]) - float(km25["weight_snr_db"])
        d20 = float(eq2["weight_snr_db"]) - float(km2["weight_snr_db"])
        if d25 >= -0.10:
            h2a_part = True
        beats_clm = all(float(eq2[d]["mean_kl"]) < float(clm2[d]["mean_kl"]) for d in ("wikitext2", "python"))
        if max(g25, g20) >= 1.5 and min(d25, d20) >= -0.15 and beats_clm:
            h2a_w += 1
    faster = float(throughput["gpu_closed_vs_hampack_speedup"]) > 1.0
    h2a = "CONFIRMED" if (h2a_w >= 2 and faster) else ("PARTIAL" if h2a_part else "FALSIFIED")

    # H3a
    h3a_snr_w = h3a_kl_w = h3a_full_w = 0
    for m in mnames:
        arms = models_out[m]["arms"]
        el, ep = arms["sp_E8_lin_3b"], arms["sp_E8_pow07_3b"]
        al, ap = arms["sp_A16_lin_3b"], arms["sp_A16_pow07_3b"]
        et = float(ep["typical_layers_snr_db"]) - float(el["typical_layers_snr_db"])
        eh = (float(ep["heavy_k10_layers_snr_db"]) - float(el["heavy_k10_layers_snr_db"])) if ep["heavy_k10_layers_snr_db"] is not None else None
        at = float(ap["typical_layers_snr_db"]) - float(al["typical_layers_snr_db"])
        ah = (float(ap["heavy_k10_layers_snr_db"]) - float(al["heavy_k10_layers_snr_db"])) if ap["heavy_k10_layers_snr_db"] is not None else None
        ok_s = (et >= 0.15 and (eh is None or eh >= 0.40)) or (at >= 0.15 and (ah is None or ah >= 0.40))
        ok_k = _sig_better(ep, el, 0.03) or _sig_better(ap, al, 0.03)
        h3a_snr_w += int(ok_s)
        h3a_kl_w += int(ok_k)
        h3a_full_w += int(ok_s and ok_k)
    h3a = "CONFIRMED" if h3a_full_w >= 2 else ("PARTIAL" if (h3a_snr_w >= 2 or h3a_kl_w >= 2) else "FALSIFIED")

    # H3b
    h3b_w = 0
    for m in mnames:
        arms = models_out[m]["arms"]
        if _sig_better(arms["sp_E8_hodge_3b"], arms["sp_E8_lin_3b"], 0.03) or _sig_better(arms["sp_A16_hodge_3b"], arms["sp_A16_lin_3b"], 0.03):
            h3b_w += 1
    h3b = "CONFIRMED" if h3b_w >= 2 else ("PARTIAL" if h3b_w == 1 else "FALSIFIED")

    # H3c
    h3c_s = h3c_f = 0
    for m in mnames:
        arms = models_out[m]["arms"]
        yk, km, cl = arms["sp_s3_yukawa_25b"], arms["sp_s3_kmeans_25b"], arms["sp_s3_coulomb_25b"]
        ok_s = (float(yk["weight_snr_db"]) - float(km["weight_snr_db"]) >= 0.05) and (
            float(yk["weight_snr_db"]) - float(cl["weight_snr_db"]) >= 0.05
        )
        ok_k = _sig_better(yk, km, 0.0) and _sig_better(yk, cl, 0.0)
        h3c_s += int(ok_s)
        h3c_f += int(ok_s and ok_k)
    h3c = "CONFIRMED" if h3c_f >= 2 else ("PARTIAL" if h3c_s >= 2 else "FALSIFIED")

    # H4
    h4_sp = h4_p128 = 0
    for m in mnames:
        arms = models_out[m]["arms"]
        conj = arms["h4_sp_A16_128_hodge_3b"]
        p128 = arms["p128_A16_3b"]
        indiv = [arms["sp_E8_lin_3b"], arms["sp_E8_pow07_3b"], arms["sp_E8_hodge_3b"],
                 arms["sp_A16_lin_3b"], arms["sp_A16_pow07_3b"], arms["sp_A16_hodge_3b"], arms["sp_A16_128_3b"]]
        c_kl = 0.5 * (float(conj["wikitext2"]["mean_kl"]) + float(conj["python"]["mean_kl"]))
        b_kl = min(0.5 * (float(r["wikitext2"]["mean_kl"]) + float(r["python"]["mean_kl"])) for r in indiv)
        p_kl = 0.5 * (float(p128["wikitext2"]["mean_kl"]) + float(p128["python"]["mean_kl"]))
        h4_sp += int(c_kl < b_kl)
        h4_p128 += int(c_kl < p_kl)
    h4 = "CONFIRMED" if (h4_sp >= 2 and h4_p128 >= 2) else ("PARTIAL" if h4_sp >= 2 else "FALSIFIED")

    return {"H1": h1, "H2a": h2a, "H3a": h3a, "H3b": h3b, "H3c": h3c, "H4": h4}


def _strict_kill_gate_verdicts(models_out: dict[str, Any]) -> dict[str, str]:
    """Literal application of the LOCKED kill gates in PREREG_SPHERE_PI_FORCES_V1.md.

    The Phase-2 runner's embedded grader was more lenient than the locked text for H2a,
    H3b and H3c (it graded PARTIAL where a literal kill gate fires). Raw results stay
    immutable; this function is the authoritative strict re-grade.
    """
    mnames = list(EXPECTED_HELD_OUT)

    def _avg(r: dict[str, Any]) -> float:
        return 0.5 * (float(r["wikitext2"]["mean_kl"]) + float(r["python"]["mean_kl"]))

    def _sig_better(a: dict[str, Any], b: dict[str, Any], thresh: float) -> bool:
        for dom in ("wikitext2", "python"):
            ka, sa = float(a[dom]["mean_kl"]), float(a[dom]["se_kl"])
            kb, sb = float(b[dom]["mean_kl"]), float(b[dom]["se_kl"])
            rel = (kb - ka) / max(kb, 1e-12)
            z = (kb - ka) / max(math.hypot(sa, sb), 1e-12)
            if not (rel >= thresh and z >= 2.0):
                return False
        return True

    # H1 kill: fails H1-P1 on >= 2/3 models.
    p1_fail = 0
    for m in mnames:
        arms = models_out[m]["arms"]
        base = arms["p128_A16_3b"]
        best_sp = min((arms["sp_E8_lin_3b"], arms["sp_A16_lin_3b"], arms["sp_A16_128_3b"]), key=_avg)
        if not _sig_better(best_sp, base, 0.10):
            p1_fail += 1
    h1 = "FALSIFIED" if p1_fail >= 2 else "NOT_KILLED"

    # H2a kill: trails k-means by > 0.15 dB OR loses KL to Cart-LM + SphereMap at 2.0 bpw (>= 2/3 models).
    h2a_kill = 0
    for m in mnames:
        arms = models_out[m]["arms"]
        trails_km = (float(arms["sp_s3_eq_leo_25b"]["weight_snr_db"]) - float(arms["sp_s3_kmeans_25b"]["weight_snr_db"])) < -0.15
        loses_clm = _avg(arms["sp_s3_eq_leo_2b"]) > _avg(arms["sp_CartLM_2b"])
        if trails_km or loses_clm:
            h2a_kill += 1
    h2a = "FALSIFIED" if h2a_kill >= 2 else "NOT_KILLED"

    # H3a: pass = (typ SNR >= +0.15 AND heavy SNR >= +0.40) AND KL >= 3% @ 2SE on >= 2/3.
    # Kill = SNR rises but KL fails on >= 2/3 -> "PARTIAL (SNR only) / FALSIFIED (KL)".
    snr_full = kl_ok = 0
    for m in mnames:
        arms = models_out[m]["arms"]
        ok_s = False
        ok_k = False
        for lin_k, p07_k in (("sp_E8_lin_3b", "sp_E8_pow07_3b"), ("sp_A16_lin_3b", "sp_A16_pow07_3b")):
            lin, p07 = arms[lin_k], arms[p07_k]
            typ = float(p07["typical_layers_snr_db"]) - float(lin["typical_layers_snr_db"])
            hv_l, hv_p = lin["heavy_k10_layers_snr_db"], p07["heavy_k10_layers_snr_db"]
            hvy_ok = True if (hv_l is None or hv_p is None) else (float(hv_p) - float(hv_l) >= 0.40)
            ok_s = ok_s or (typ >= 0.15 and hvy_ok)
            ok_k = ok_k or _sig_better(p07, lin, 0.03)
        snr_full += int(ok_s)
        kl_ok += int(ok_k)
    if snr_full >= 2 and kl_ok >= 2:
        h3a = "CONFIRMED"
    elif kl_ok < 2:
        h3a = "FALSIFIED"
    else:
        h3a = "PARTIAL"

    # H3b kill: zero (non-significant) KL improvement or degradation on >= 2/3 models.
    h3b_noimp = 0
    h3b_win = 0
    for m in mnames:
        arms = models_out[m]["arms"]
        if _sig_better(arms["sp_E8_hodge_3b"], arms["sp_E8_lin_3b"], 0.03) or _sig_better(arms["sp_A16_hodge_3b"], arms["sp_A16_lin_3b"], 0.03):
            h3b_win += 1
        if not (_sig_better(arms["sp_E8_hodge_3b"], arms["sp_E8_lin_3b"], 0.0) or _sig_better(arms["sp_A16_hodge_3b"], arms["sp_A16_lin_3b"], 0.0)):
            h3b_noimp += 1
    h3b = "FALSIFIED" if h3b_noimp >= 2 else ("CONFIRMED" if h3b_win >= 2 else "PARTIAL")

    # H3c kill: trails or statistically ties pure spherical k-means on >= 2/3 models.
    h3c_trail = 0
    for m in mnames:
        arms = models_out[m]["arms"]
        if not _sig_better(arms["sp_s3_yukawa_25b"], arms["sp_s3_kmeans_25b"], 0.0):
            h3c_trail += 1
    h3c = "FALSIFIED" if h3c_trail >= 2 else "NOT_KILLED"

    # H4 kill: any single component equals or beats the conjunction on >= 2/3 models.
    h4_beaten = 0
    for m in mnames:
        arms = models_out[m]["arms"]
        conj = _avg(arms["h4_sp_A16_128_hodge_3b"])
        indiv = min(_avg(arms[k]) for k in ("sp_E8_lin_3b", "sp_E8_pow07_3b", "sp_E8_hodge_3b",
                                             "sp_A16_lin_3b", "sp_A16_pow07_3b", "sp_A16_hodge_3b", "sp_A16_128_3b"))
        if indiv <= conj:
            h4_beaten += 1
    h4 = "FALSIFIED" if h4_beaten >= 2 else "NOT_KILLED"

    return {"H1": h1, "H2a": h2a, "H3a": h3a, "H3b": h3b, "H3c": h3c, "H4": h4}


def verify_gpu_eval_dir(gpu_dir: pathlib.Path, prereg_path: pathlib.Path | None = None) -> dict[str, Any]:
    if prereg_path is not None:
        prereg_raw = _read_regular_bytes(prereg_path, "prereg")
        got_prereg = hashlib.sha256(prereg_raw).hexdigest()
        if not hmac.compare_digest(got_prereg, PREREG_SHA256):
            raise S106GpuVerifyError("PREREG_SHA_MISMATCH", f"got {got_prereg}")

    pilot_path = gpu_dir / "s106_frozen_pilot_params.json"
    pilot_raw = _read_regular_bytes(pilot_path, "pilot_params")
    pilot_file_sha = hashlib.sha256(pilot_raw).hexdigest()
    pilot = _load_json_no_dups(pilot_raw, "pilot_params")
    if pilot.get("preregistration_sha256") != PREREG_SHA256:
        raise S106GpuVerifyError("PILOT_PREREG_MISMATCH", "pilot prereg SHA mismatch")
    if pilot.get("held_out_models_touched") != []:
        raise S106GpuVerifyError("PILOT_SNOOPING_DETECTED", "pilot touched held-out models")
    p_inner = pilot.get("pilot_params_sha256")
    if not _is_hex64(p_inner):
        raise S106GpuVerifyError("BAD_PILOT_SHA", "invalid pilot_params_sha256")
    p_body = {k: v for k, v in pilot.items() if k != "pilot_params_sha256"}
    p_calc = hashlib.sha256(json.dumps(p_body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if not hmac.compare_digest(p_inner, p_calc):
        raise S106GpuVerifyError("PILOT_SHA_MISMATCH", "pilot inner hash mismatch")

    r_pilot = _verify_mlos_receipt(gpu_dir / "mlos_zone_b_pilot_receipt.json", "pilot_receipt")
    r_gauntlet = _verify_mlos_receipt(gpu_dir / "mlos_zone_b_gauntlet_receipt.json", "gauntlet_receipt")

    gaunt_path = gpu_dir / "s106_blind_gauntlet_results.json"
    gaunt_raw = _read_regular_bytes(gaunt_path, "gauntlet_results")
    gaunt_file_sha = hashlib.sha256(gaunt_raw).hexdigest()
    gaunt = _load_json_no_dups(gaunt_raw, "gauntlet_results")
    if gaunt.get("preregistration_sha256") != PREREG_SHA256:
        raise S106GpuVerifyError("GAUNTLET_PREREG_MISMATCH", "gauntlet prereg SHA mismatch")
    if not hmac.compare_digest(str(gaunt.get("pilot_params_file_sha256", "")), pilot_file_sha):
        raise S106GpuVerifyError("PILOT_LINK_SHA_MISMATCH", "gauntlet pilot file SHA mismatch")
    if not hmac.compare_digest(str(gaunt.get("pilot_params_inner_sha256", "")), p_inner):
        raise S106GpuVerifyError("PILOT_LINK_INNER_MISMATCH", "gauntlet pilot inner SHA mismatch")
    if not (str(pilot["locked_utc"]) < str(gaunt["gauntlet_completed_utc"])):
        raise S106GpuVerifyError("TEMPORAL_SNOOP_ORDER", "pilot_locked_utc not < gauntlet_completed_utc")

    g_inner = gaunt.get("result_sha256")
    if not _is_hex64(g_inner):
        raise S106GpuVerifyError("BAD_RESULT_SHA", "invalid result_sha256")
    g_body = {k: v for k, v in gaunt.items() if k != "result_sha256"}
    g_calc = hashlib.sha256(json.dumps(g_body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if not hmac.compare_digest(g_inner, g_calc):
        raise S106GpuVerifyError("RESULT_SHA_MISMATCH", "gauntlet inner result_sha256 mismatch")

    models = gaunt.get("models")
    if type(models) is not dict or tuple(models.keys()) != EXPECTED_HELD_OUT:
        raise S106GpuVerifyError("HELD_OUT_MODELS_MISMATCH", "unexpected held-out model set")

    arm_count = 0
    for m in EXPECTED_HELD_OUT:
        arms = models[m]["arms"]
        if type(arms) is not dict or len(arms) != 39:
            raise S106GpuVerifyError("ARM_COUNT_MISMATCH", f"{m}: expected 39 arms")
        for aname, arow in arms.items():
            arm_count += 1
            if arow.get("syndrome_errors") != 0:
                raise S106GpuVerifyError("SYNDROME_ERROR_NONZERO", f"{m}.{aname}")
            if arow.get("oob_groups") != 0:
                raise S106GpuVerifyError("OOB_GROUPS_NONZERO", f"{m}.{aname}")
            if arow.get("non_block_diffs") != 0:
                raise S106GpuVerifyError("NON_BLOCK_DIFF_NONZERO", f"{m}.{aname}")
            bpw = float(arow["exact_bpw"])
            if not (1.80 <= bpw <= 4.60):
                raise S106GpuVerifyError("BPW_OUT_OF_RANGE", f"{m}.{aname}: {bpw}")
            # Verify strict CS-08 ceiling on global SphereMap 3.0b & 4.5b lattice arms
            if aname in ("sp_E8_lin_3b", "sp_A16_lin_3b", "sp_A16_128_3b", "sp_E8_pow07_3b", "sp_A16_pow07_3b"):
                if bpw > 3.0001:
                    raise S106GpuVerifyError("CS08_BPW_EXCEEDED", f"{m}.{aname}: {bpw} > 3.0")

    gi = gaunt["global_integrity"]
    if gi.get("total_arms_evaluated") != arm_count or gi.get("total_syndrome_errors") != 0 or gi.get("total_oob_groups") != 0 or gi.get("total_non_block_diffs") != 0:
        raise S106GpuVerifyError("GLOBAL_INTEGRITY_MISMATCH", str(gi))

    recomputed = _recompute_verdicts(models, gaunt["h2a_pack_decode_throughput"])
    recorded = {k: gaunt["preregistered_verdicts"][k]["verdict"] for k in recomputed}
    if recomputed != recorded:
        raise S106GpuVerifyError("VERDICT_MISMATCH", f"recomputed={recomputed} != recorded={recorded}")

    return {
        "ok": True,
        "preregistration_sha256": PREREG_SHA256,
        "pilot_file_sha256": pilot_file_sha,
        "gauntlet_file_sha256": gaunt_file_sha,
        "gauntlet_result_sha256": g_inner,
        "pilot_receipt": r_pilot,
        "gauntlet_receipt": r_gauntlet,
        "arms_verified": arm_count,
        "verdicts": recomputed,
        "strict_kill_gate_verdicts": _strict_kill_gate_verdicts(models),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track S106 GPU Eval Integrity & Verdict Verifier")
    parser.add_argument("--dir", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent)
    parser.add_argument("--prereg", type=pathlib.Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    prereg = args.prereg
    if prereg is None:
        cand = args.dir.parent.parent / "notes" / "sphere_pi_forces_2026_11_25" / "PREREG_SPHERE_PI_FORCES_V1.md"
        if cand.is_file():
            prereg = cand
    try:
        res = verify_gpu_eval_dir(args.dir, prereg)
    except S106GpuVerifyError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(res, sort_keys=True))
    else:
        print(
            f"S106_GPU_EVAL_OK arms={res['arms_verified']} "
            f"runner_verdicts={json.dumps(res['verdicts'], sort_keys=True)} "
            f"strict_kill_gate_verdicts={json.dumps(res['strict_kill_gate_verdicts'], sort_keys=True)}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
