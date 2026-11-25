#!/usr/bin/env python3
"""Track S106 Phase 3 (Amendments 1 & 2: H5a, H5b, H6a, H6b, H6c) Integrity & Verdict Verifier.

Pure stdlib. Independently checks, for gpu_eval_phase3_h5_h6/:
  - Each locked protocol JSON was written (locked_utc) strictly before its results completed.
  - Parent preregistration SHA-256 and amendment SHA-256 prefixes match the locked notes.
  - Both mlos Zone-B receipts: clean_hardware_run=true, anomalies=[], exit 0, no throttling,
    compute VRAM 0 -> 0.
  - Inner result_sha256 of both results files; 0 syndrome errors / 0 out-of-ball groups /
    0 non-block tensor diffs across every arm; matched exact_bpw where the protocol requires it.
  - Re-derives every verdict from raw per-arm numbers using the literal locked rules.
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
AMEND1_PREFIX = "c83910a0e1a98e2a"
AMEND2_PREFIX = "b676cc556c9bbfa0"
HELD_OUT = ("HuggingFaceTB/SmolLM2-360M", "Qwen/Qwen2.5-1.5B", "Qwen/Qwen2.5-3B")
MAX_BYTES = 8 * 1024 * 1024


class S106Phase3Error(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _read(path: pathlib.Path, label: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(str(path), flags)
    except OSError as exc:
        raise S106Phase3Error("FILE_OPEN_ERROR", f"{label}: {exc}") from exc
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise S106Phase3Error("NOT_REGULAR_FILE", label)
        chunks: list[bytes] = []
        tot = 0
        while True:
            c = os.read(fd, 65536)
            if not c:
                break
            tot += len(c)
            if tot > MAX_BYTES:
                raise S106Phase3Error("FILE_TOO_LARGE", label)
            chunks.append(c)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _load(raw: bytes, label: str) -> dict[str, Any]:
    if b"\r" in raw:
        raise S106Phase3Error("CRLF_FORBIDDEN", label)

    def _nd(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in pairs:
            if k in out:
                raise S106Phase3Error("DUPLICATE_KEY", f"{label}: {k}")
            out[k] = v
        return out

    def _bad(c: str) -> Any:
        raise S106Phase3Error("NON_FINITE_JSON", f"{label}: {c}")

    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_nd, parse_constant=_bad)
    except S106Phase3Error:
        raise
    except Exception as exc:
        raise S106Phase3Error("INVALID_JSON", f"{label}: {exc}") from exc
    if type(obj) is not dict:
        raise S106Phase3Error("JSON_ROOT_NOT_OBJECT", label)
    return obj


def _inner(obj: dict[str, Any], key: str, label: str) -> str:
    got = obj.get(key)
    if type(got) is not str or len(got) != 64:
        raise S106Phase3Error("BAD_INNER_SHA", label)
    body = {k: v for k, v in obj.items() if k != key}
    calc = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if not hmac.compare_digest(got, calc):
        raise S106Phase3Error("INNER_SHA_MISMATCH", label)
    return got


def _receipt(path: pathlib.Path, label: str) -> dict[str, Any]:
    raw = _read(path, label)
    r = _load(raw, label)
    if r.get("clean_hardware_run") is not True or r.get("anomalies") != [] or r.get("determinism_zone") != "B":
        raise S106Phase3Error("DIRTY_RECEIPT", label)
    ex = r.get("execution")
    if type(ex) is not dict or ex.get("exit_code") != 0:
        raise S106Phase3Error("NONZERO_EXIT", label)
    for k in ("start_gpu_telemetry", "end_gpu_telemetry"):
        g = r.get(k)
        if type(g) is not dict or g.get("compute_vram_mib") != 0:
            raise S106Phase3Error("VRAM_LEAK", f"{label}.{k}")
        cer = g.get("clocks_event_reasons")
        if type(cer) is not dict or cer.get("thermal_throttled") is not False:
            raise S106Phase3Error("THERMAL_THROTTLED", f"{label}.{k}")
    return {"file_sha256": hashlib.sha256(raw).hexdigest(), "receipt_sha256": r.get("receipt_sha256"),
            "started_utc": ex.get("started_utc"), "ended_utc": ex.get("ended_utc")}


def _sig(a: dict[str, Any], b: dict[str, Any], th: float) -> bool:
    for dom in ("wikitext2", "python"):
        ka, sa = float(a[dom]["mean_kl"]), float(a[dom]["se_kl"])
        kb, sb = float(b[dom]["mean_kl"]), float(b[dom]["se_kl"])
        if not ((kb - ka) / max(kb, 1e-12) >= th and (kb - ka) / max(math.hypot(sa, sb), 1e-12) >= 2.0):
            return False
    return True


def _avg(r: dict[str, Any]) -> float:
    return 0.5 * (float(r["wikitext2"]["mean_kl"]) + float(r["python"]["mean_kl"]))


def _check_arms(arms: dict[str, Any], label: str) -> int:
    n = 0
    for name, a in arms.items():
        n += 1
        for k in ("syndrome_errors", "oob_groups", "non_block_diffs"):
            if a.get(k) != 0:
                raise S106Phase3Error("INTEGRITY_NONZERO", f"{label}.{name}.{k}")
    return n


def regrade_h5(res: dict[str, Any]) -> dict[str, str]:
    models = res["models"]
    holds = sig_cfgs = 0
    for tag in ("E8_20b", "E8_30b", "A16_30b"):
        passes = sig_models = 0
        for m in HELD_OUT:
            a = models[m]["arms"]
            if a[f"flownoise_{tag}"]["exact_bpw"] != a[f"static_{tag}"]["exact_bpw"]:
                raise S106Phase3Error("H5A_BPW_NOT_MATCHED", f"{m}.{tag}")
            passes += int(_sig(a[f"flownoise_{tag}"], a[f"static_{tag}"], 0.15) and _sig(a[f"flownoise_{tag}"], a[f"flownull_{tag}"], 0.0))
            sig_models += int(_sig(a[f"flownoise_{tag}"], a[f"static_{tag}"], 0.0))
        holds += int(passes >= 2)
        sig_cfgs += int(sig_models >= 2)
    h5a = "CONFIRMED" if holds >= 2 else ("PARTIAL" if (holds == 1 or sig_cfgs >= 2) else "FALSIFIED")
    amp_ok = sched_ok = 0
    for m in HELD_OUT:
        a = models[m]["arms"]
        if abs(float(a["sched_depth_p128"]["exact_bpw"]) - float(a["p128_A16_3b"]["exact_bpw"])) > 0.005:
            raise S106Phase3Error("H5B_BPW_NOT_MATCHED", m)
        amp_ok += int(float(models[m]["h5b_cone"]["amplification_q1_over_q4"]) >= 2.0)
        sched_ok += int(_sig(a["sched_depth_p128"], a["p128_A16_3b"], 0.08))
    h5b = "CONFIRMED" if (amp_ok >= 2 and sched_ok >= 2) else "FALSIFIED"
    return {"H5a": h5a, "H5b": h5b}


def regrade_h6(res: dict[str, Any]) -> dict[str, str]:
    models = res["models"]
    pb = sum(int(_sig(models[m]["arms"]["polar_3b"], models[m]["arms"]["flat_3b"], 0.10)) for m in HELD_OUT)
    eb = sum(int(_avg(models[m]["arms"]["equatorial_3b"]) < _avg(models[m]["arms"]["polar_3b"])) for m in HELD_OUT)
    for m in HELD_OUT:
        a = models[m]["arms"]
        for k in ("polar_3b", "equatorial_3b"):
            if abs(float(a[k]["exact_bpw"]) - float(a["flat_3b"]["exact_bpw"])) > 0.005:
                raise S106Phase3Error("H6A_BPW_NOT_MATCHED", f"{m}.{k}")
    h6a = "CONFIRMED" if (pb >= 2 and eb < 2) else "FALSIFIED"
    b1 = sum(int(float(models[m]["h6b_part1"]["gap_db"]) >= -0.15) for m in HELD_OUT)
    eqv = all(float(models[m]["h6b_part1"]["equivariance_exact_frac"]) >= 0.999 for m in HELD_OUT)
    h6b1 = "CONFIRMED" if (b1 >= 2 and eqv) else "FALSIFIED"
    nr = 0
    for tag, native in (("2b", "native_2b"), ("3b", "flat_3b")):
        cnt = 0
        for m in HELD_OUT:
            a = models[m]["arms"]
            cnt += int(_sig(a[f"floworder_{tag}"], a[native], 0.05) and _sig(a[f"floworder_{tag}"], a[f"randorder_{tag}"], 0.05))
        nr += int(cnt >= 2)
    h6b2 = "CONFIRMED" if nr == 2 else ("PARTIAL" if nr == 1 else "FALSIFIED")
    runs = res["h6c_runs"]
    fl = [r for r in runs if r["mode"] == "flat"]
    hp = [r for r in runs if r["mode"] == "hopf"]
    if len(fl) != 2 or len(hp) != 2 or len({r["n_params"] for r in runs}) != 1:
        raise S106Phase3Error("H6C_ARMS_NOT_MATCHED", "seed or parameter-count mismatch")
    ca = max(r["val_bits_per_byte"] for r in hp) < min(r["val_bits_per_byte"] for r in fl)
    mh = sum(r["ptq3_kl_nats"] for r in hp) / 2.0
    mf = sum(r["ptq3_kl_nats"] for r in fl) / 2.0
    cb = mh <= 0.85 * mf and max(r["ptq3_kl_nats"] for r in hp) < min(r["ptq3_kl_nats"] for r in fl)
    h6c = "CONFIRMED" if (ca or cb) else "FALSIFIED"
    return {"H6a": h6a, "H6b_part1": h6b1, "H6b_part2": h6b2, "H6c": h6c}


def _verify_one(d: pathlib.Path, proto_name: str, res_name: str, receipt_name: str, amend_key: str, prefix: str,
                regrade) -> dict[str, Any]:
    proto_raw = _read(d / proto_name, proto_name)
    proto = _load(proto_raw, proto_name)
    res_raw = _read(d / res_name, res_name)
    res = _load(res_raw, res_name)
    if proto.get("parent_preregistration_sha256") != PREREG_SHA256 or res.get("preregistration_sha256") != PREREG_SHA256:
        raise S106Phase3Error("PREREG_MISMATCH", res_name)
    if not str(res.get(amend_key, "")).startswith(prefix) or proto.get(amend_key) != res.get(amend_key):
        raise S106Phase3Error("AMENDMENT_MISMATCH", res_name)
    if not hmac.compare_digest(str(res.get("protocol_file_sha256", "")), hashlib.sha256(proto_raw).hexdigest()):
        raise S106Phase3Error("PROTOCOL_LINK_MISMATCH", res_name)
    if not (str(proto["locked_utc"]) <= str(res["completed_utc"])) or proto["locked_utc"] != res["protocol_locked_utc"]:
        raise S106Phase3Error("TEMPORAL_ORDER", res_name)
    inner = _inner(res, "result_sha256", res_name)
    rec = _receipt(d / receipt_name, receipt_name)
    if not (str(rec["started_utc"]) <= str(proto["locked_utc"]) <= str(rec["ended_utc"])):
        raise S106Phase3Error("PROTOCOL_OUTSIDE_RECEIPT_WINDOW", res_name)
    models = res.get("models")
    if type(models) is not dict or tuple(models.keys()) != HELD_OUT:
        raise S106Phase3Error("HELD_OUT_MISMATCH", res_name)
    n = sum(_check_arms(models[m]["arms"], f"{res_name}.{m}") for m in HELD_OUT)
    if "h6a_pilot_qwen05b" in res:
        n += _check_arms(res["h6a_pilot_qwen05b"], f"{res_name}.pilot")
    gi = res["global_integrity"]
    if gi.get("total_syndrome_errors") != 0 or gi.get("total_oob_groups") != 0 or gi.get("total_non_block_diffs") != 0 or gi.get("total_arms_evaluated") != n:
        raise S106Phase3Error("GLOBAL_INTEGRITY_MISMATCH", res_name)
    recomputed = regrade(res)
    recorded = {k: res["preregistered_verdicts"][k]["verdict"] for k in recomputed}
    if recomputed != recorded:
        raise S106Phase3Error("VERDICT_MISMATCH", f"{res_name}: {recomputed} != {recorded}")
    return {"result_file_sha256": hashlib.sha256(res_raw).hexdigest(), "result_sha256": inner,
            "protocol_file_sha256": hashlib.sha256(proto_raw).hexdigest(), "receipt": rec, "arms": n, "verdicts": recomputed}


def verify_phase3_dir(d: pathlib.Path) -> dict[str, Any]:
    h5 = _verify_one(d, "h5_locked_protocol.json", "s106_h5_results.json", "mlos_zone_b_h5_receipt.json",
                     "amendment1_sha256", AMEND1_PREFIX, regrade_h5)
    h6 = _verify_one(d, "h6_locked_protocol.json", "s106_h6_results.json", "mlos_zone_b_h6_receipt.json",
                     "amendment2_sha256", AMEND2_PREFIX, regrade_h6)
    return {"ok": True, "h5": h5, "h6": h6}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Track S106 Phase 3 (H5/H6) verifier")
    ap.add_argument("--dir", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        res = verify_phase3_dir(a.dir)
    except S106Phase3Error as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    if a.json:
        print(json.dumps(res, sort_keys=True))
    else:
        v = dict(res["h5"]["verdicts"])
        v.update(res["h6"]["verdicts"])
        print(f"S106_PHASE3_OK arms={res['h5']['arms'] + res['h6']['arms']} verdicts={json.dumps(v, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
