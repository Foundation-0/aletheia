"""Phase B Live Silicon Capture Runner for S71 Proximity Barrier & AVX-512 Unlock.

Must be invoked strictly under:
  mlos gpu-lease --mode train -- flock /tmp/aletheion_rapl_experiment.lock \
    mlos stamp-run --profile <mlos-profiles>/ux582hs-rtx3080-8gb.toml \
    --zone B --output mlos_zone_b_receipt.json -- python3 -I -B s71_run_live.py

Compiles s71_proximity_bench.c inside a private 0o700 temp directory (-Wall -Wextra -Werror),
verifies AC0 == 1 and zero warnings, waits 5 s for chassis thermal quiescence after GPU lease
acquisition, executes the palindromic ABBA live intel-rapl + rdtsc + AVX-512 sweep, writes
s71_empirical_results.json (exact integer raw telemetry + pinned SHAs), and deletes the binary.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GCC_FLAGS = [
    "-O3",
    "-march=native",
    "-mavx512f",
    "-mavx512bw",
    "-mavx512vl",
    "-mavx512vnni",
    "-pthread",
    "-Wall",
    "-Wextra",
    "-Werror",
]


def _read_text_opt(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _read_cpu_pkg_temp_mc() -> int:
    hwmon_root = Path("/sys/class/hwmon")
    if not hwmon_root.exists():
        return 0
    for d in sorted(hwmon_root.iterdir()):
        name = _read_text_opt(str(d / "name"))
        if name == "coretemp":
            val = _read_text_opt(str(d / "temp1_input"))
            body = val[1:] if val.startswith("-") else val
            if body and all("0" <= ch <= "9" for ch in body):
                return int(val)
    return 0


def _query_nvidia_smi() -> dict[str, str]:
    cmd = [
        "nvidia-smi",
        "--query-gpu=name,pstate,power.draw,temperature.gpu,utilization.gpu,memory.used",
        "--format=csv,noheader,nounits",
    ]
    out = subprocess.check_output(cmd, text=True).strip().splitlines()[0]
    cols = [c.strip() for c in out.split(",")]
    keys = ["name", "pstate", "power_draw_w", "temp_c", "util_gpu_pct", "memory_used_mib"]
    return dict(zip(keys, cols))


def main() -> int:
    work = Path(__file__).resolve().parent
    ac_online = _read_text_opt("/sys/class/power_supply/AC0/online")
    if ac_online != "1":
        sys.stderr.write(f"ERROR: AC0/online={ac_online!r} != '1'\n")
        return 2

    prereg_path = work / "s71_preregistration.json"
    c_path = work / "s71_proximity_bench.c"
    lean_path = work / "ProximityBarrierSilicon.lean"

    prereg_raw = prereg_path.read_bytes()
    prereg_obj = json.loads(prereg_raw.decode("utf-8"))
    prereg_file_sha = hashlib.sha256(prereg_raw).hexdigest()
    c_sha = hashlib.sha256(c_path.read_bytes()).hexdigest()
    lean_sha = hashlib.sha256(lean_path.read_bytes()).hexdigest()

    if c_sha != prereg_obj["pinned_sources"]["s71_proximity_bench.c"]:
        sys.stderr.write("ERROR: s71_proximity_bench.c SHA mismatch vs preregistration\n")
        return 3
    if lean_sha != prereg_obj["pinned_sources"]["ProximityBarrierSilicon.lean"]:
        sys.stderr.write("ERROR: ProximityBarrierSilicon.lean SHA mismatch vs preregistration\n")
        return 3

    gcc_ver = subprocess.check_output(["gcc", "--version"], text=True).splitlines()[0].strip()

    with tempfile.TemporaryDirectory(prefix="s71_live_bin_") as td:
        os.chmod(td, 0o700)
        bin_path = Path(td) / "s71_proximity_bench"
        comp = subprocess.run(
            ["gcc", *GCC_FLAGS, str(c_path), "-o", str(bin_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if comp.returncode != 0 or comp.stderr.strip():
            sys.stderr.write(f"ERROR: gcc compile failed rc={comp.returncode} stderr={comp.stderr}\n")
            return 4

        # Short thermal quiescence window after GPU lease handoff
        time.sleep(5)

        started_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        smi_pre = _query_nvidia_smi()
        cpu_temp_pre_mc = _read_cpu_pkg_temp_mc()
        t0_ns = time.monotonic_ns()

        run = subprocess.run(
            [str(bin_path), "--run-live"],
            capture_output=True,
            text=True,
            check=False,
        )
        elapsed_ms = (time.monotonic_ns() - t0_ns) // 1_000_000
        cpu_temp_post_mc = _read_cpu_pkg_temp_mc()
        smi_post = _query_nvidia_smi()
        ended_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if run.returncode != 0:
            sys.stderr.write(f"ERROR: s71_proximity_bench --run-live failed rc={run.returncode} stderr={run.stderr}\n")
            return 5

        bench_raw = json.loads(run.stdout)

    payload: dict[str, Any] = {
        "schema": "aletheia.s71.empirical_results.v1",
        "oracle_class": "sampled",
        "measured_live_silicon": True,
        "ac_online": True,
        "preregistration_file_sha256": prereg_file_sha,
        "preregistration_sha256": prereg_obj["preregistration_sha256"],
        "c_source_sha256": c_sha,
        "lean_source_sha256": lean_sha,
        "gcc_version": gcc_ver,
        "gcc_flags": list(GCC_FLAGS),
        "kernel_release": platform.release(),
        "started_utc": started_utc,
        "ended_utc": ended_utc,
        "elapsed_ms": int(elapsed_ms),
        "cpu_pkg_temp_pre_mc": int(cpu_temp_pre_mc),
        "cpu_pkg_temp_post_mc": int(cpu_temp_post_mc),
        "nvidia_smi_pre": smi_pre,
        "nvidia_smi_post": smi_post,
        "measurements": bench_raw,
    }
    out_path = work / "s71_empirical_results.json"
    out_text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    out_path.write_text(out_text, encoding="utf-8")
    sys.stdout.write(f"WROTE {out_path.name} ({out_path.stat().st_size} bytes, elapsed_ms={elapsed_ms})\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
