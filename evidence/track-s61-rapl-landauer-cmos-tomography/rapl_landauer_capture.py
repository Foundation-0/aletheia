#!/usr/bin/env python3
"""Controlled Millisecond intel-rapl + Thermal Silicon Capture Orchestrator.

Strictly zero microphone, zero camera, zero display changes, zero ELF binaries left
in the study directory. Compiles rapl_landauer_microkernels.c inside a TemporaryDirectory,
verifies GPU utilization < 5% (serialized under mlos gpu-lease --mode train), executes
the 7-regime 50 ms (20 Hz) integer capture, and writes canonical 0o600 JSON snapshot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time


_HERE = Path(__file__).resolve().parent


def _query_gpu_util_pct() -> dict[str, int]:
    proc = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=utilization.gpu,utilization.memory,memory.used,temperature.gpu",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    first_line = proc.stdout.strip().splitlines()[0]
    parts = [int(p.strip()) for p in first_line.split(",")]
    return {
        "gpu_util_pct": parts[0],
        "mem_util_pct": parts[1],
        "mem_used_mib": parts[2],
        "gpu_temp_c": parts[3],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture 7-regime 50ms intel-rapl silicon snapshot")
    parser.add_argument("--samples", type=int, default=100, help="Samples per regime (default 100 @ 50ms = 5s)")
    parser.add_argument("--tick-ms", type=int, default=50, help="Sampling interval in ms (default 50)")
    parser.add_argument("--settle-ms", type=int, default=1000, help="Inter-regime settle ms (default 1000)")
    parser.add_argument("--max-gpu-util", type=int, default=5, help="Max allowed GPU util pct before capture")
    parser.add_argument("--skip-gpu-check", action="store_true", help="Skip GPU idle gate (for dry smoke test only)")
    parser.add_argument(
        "--output",
        type=str,
        default=str(_HERE / "rapl_landauer_snapshot.json"),
        help="Output snapshot JSON path (written atomically with mode 0o600)",
    )
    args = parser.parse_args(argv)

    c_src = _HERE / "rapl_landauer_microkernels.c"
    c_bytes = c_src.read_bytes()
    c_sha = hashlib.sha256(c_bytes).hexdigest()

    gpu_pre = _query_gpu_util_pct()
    if not args.skip_gpu_check and gpu_pre["gpu_util_pct"] >= args.max_gpu_util:
        raise SystemExit(
            f"ABORT: GPU util {gpu_pre['gpu_util_pct']}% >= {args.max_gpu_util}% "
            f"(wait for mlos gpu-lease idle window before RAPL capture)"
        )

    with tempfile.TemporaryDirectory(prefix="s61_rapl_build_") as td:
        td_path = Path(td)
        bin_path = td_path / "rapl_landauer_microkernels"
        raw_json_path = td_path / "raw_out.json"
        compile_cmd = [
            "gcc",
            "-O3",
            "-march=native",
            "-mavx512f",
            "-mavx512dq",
            "-mavx512bw",
            "-mavx512vl",
            "-mavx512vnni",
            "-pthread",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(c_src),
            "-o",
            str(bin_path),
        ]
        subprocess.run(compile_cmd, check=True, timeout=60)

        t_start_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        subprocess.run(
            [
                str(bin_path),
                "--samples",
                str(args.samples),
                "--tick-ms",
                str(args.tick_ms),
                "--settle-ms",
                str(args.settle_ms),
                "--output",
                str(raw_json_path),
            ],
            check=True,
            timeout=300,
        )
        t_end_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        gpu_post = _query_gpu_util_pct()
        raw = json.loads(raw_json_path.read_text(encoding="utf-8"))

    snapshot = {
        "schema_version": "aletheia.track_s61.rapl_landauer_snapshot.v1",
        "capture_utc_start": t_start_utc,
        "capture_utc_end": t_end_utc,
        "privacy_locks": {
            "audio_capture_accessed": False,
            "camera_accessed": False,
            "display_modified": False,
        },
        "host_spec": {
            "os": platform.system().lower(),
            "machine": platform.machine(),
            "cpu_model": "11th Gen Intel(R) Core(TM) i9-11900H @ 2.50GHz",
            "l1d_kib_per_core": 48,
            "l2_kib_per_core": 1280,
            "l3_mib_shared": 24,
        },
        "gpu_quiescence_gate": {
            "pre_capture": gpu_pre,
            "post_capture": gpu_post,
            "max_allowed_gpu_util_pct": args.max_gpu_util,
            "gpu_idle_verified": (
                gpu_pre["gpu_util_pct"] < args.max_gpu_util
                and gpu_post["gpu_util_pct"] < args.max_gpu_util
            ),
        },
        "microkernels_c_sha256": c_sha,
        "harness_version": raw["harness_version"],
        "num_workers": raw["num_workers"],
        "worker_cpus": raw["worker_cpus"],
        "sampler_cpu": raw["sampler_cpu"],
        "tick_ms": raw["tick_ms"],
        "settle_ms": raw["settle_ms"],
        "samples_per_regime": raw["samples_per_regime"],
        "dram_bytes_per_worker": raw["dram_bytes_per_worker"],
        "dram_total_bytes": raw["dram_total_bytes"],
        "step_algebra_self_checked": raw["step_algebra_self_checked"],
        "channels": raw["channels"],
        "regimes": raw["regimes"],
        "regime_labels": raw["regime_labels"],
        "t_rel_us": raw["t_rel_us"],
        "dt_us": raw["dt_us"],
        "X_anonymous": raw["X_anonymous"],
    }

    payload_bytes = (
        json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n"
    ).encode("ascii")

    out_path = Path(args.output)
    tmp_path = out_path.with_name(f".{out_path.name}.{os.getpid()}.tmp")
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.write(fd, payload_bytes)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(str(tmp_path), str(out_path))
    snap_sha = hashlib.sha256(payload_bytes).hexdigest()
    print(json.dumps({"written": True, "bytes": len(payload_bytes), "sha256": snap_sha, "gpu_idle_verified": snapshot["gpu_quiescence_gate"]["gpu_idle_verified"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
