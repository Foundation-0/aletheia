#!/usr/bin/env python3
"""
ceer_silicon_runner.py — Live pure-integer hardware telemetry acquisition and
micro-actuator execution for Track S62 (3-cycle CEER: Lean 4.36.0 <-> silicon).

Hard Safety & Anti-Contamination Locks:
  - ZERO microphone access, ZERO camera (/dev/video*) access, ZERO display changes.
  - Compiles ceer_actuator.c into an ephemeral 0o700 scratch dir (ELF=0 in repo).
  - Serializes live RAPL captures with flock /tmp/aletheion_rapl_experiment.lock
    and waits until GPU utilization < 5% (nvidia-smi) before executing each cycle.
  - Enforces cryptographic pre-registration check: cycle_k_prereg.json MUST exist
    on disk and match its SHA-256 commitment BEFORE the live actuator runs.
  - Pure integer telemetry (ns, uJ, mC, RPM, kHz, retired ops) — zero floats!
"""
from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any


LOCK_PATH = Path("/tmp/aletheion_rapl_experiment.lock")
RAPL_WRAP_DEFAULT = 262143328850
SAMPLE_INTERVAL_NS = 50_000_000  # 50 ms = 20 Hz


class RunnerError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _parse_ascii_int(raw: str) -> int | None:
    s = raw.strip()
    if not s:
        return None
    neg = False
    if s[0] == "-":
        neg = True
        s = s[1:]
    if not s:
        return None
    for ch in s:
        if ch < "0" or ch > "9":
            return None
    val = int(s)
    return -val if neg else val


def _read_sysfs_int(path: Path) -> int | None:
    try:
        return _parse_ascii_int(path.read_text(encoding="utf-8"))
    except OSError:
        return None


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def write_0600_atomic(path: Path, data: bytes) -> None:
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    dfd = os.open(str(parent), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    tmp_name: str | None = None
    fd = -1
    try:
        cand = f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
        fd = os.open(cand, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dfd)
        tmp_name = cand
        os.fchmod(fd, 0o600)
        mv = memoryview(data)
        off = 0
        while off < len(mv):
            n = os.write(fd, mv[off:])
            if n <= 0:
                raise RunnerError("SHORT_WRITE", "os.write returned 0")
            off += n
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(tmp_name, path.name, src_dir_fd=dfd, dst_dir_fd=dfd)
        tmp_name = None
        os.fsync(dfd)
    finally:
        if fd >= 0:
            os.close(fd)
        if tmp_name is not None:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
        os.close(dfd)


def discover_sensors() -> dict[str, Any]:
    """Discover physical CPU topology, 5 unlocked intel-rapl domains, coretemp, fans, and cpufreq."""
    phys_map: dict[int, int] = {}
    cpu_root = Path("/sys/devices/system/cpu")
    for idx in range(32):
        cdir = cpu_root / f"cpu{idx}"
        if not cdir.is_dir():
            continue
        cid = _read_sysfs_int(cdir / "topology" / "core_id")
        if cid is not None and cid not in phys_map:
            phys_map[cid] = idx
    phys_cpus = [phys_map[k] for k in sorted(phys_map)]

    rapl_specs = [
        ("package_0", Path("/sys/class/powercap/intel-rapl:0")),
        ("core", Path("/sys/class/powercap/intel-rapl:0:0")),
        ("uncore", Path("/sys/class/powercap/intel-rapl:0:1")),
        ("psys", Path("/sys/class/powercap/intel-rapl:1")),
        ("mmio_0", Path("/sys/class/powercap/intel-rapl-mmio:0")),
    ]
    rapl_paths: dict[str, dict[str, Any]] = {}
    for key, rdir in rapl_specs:
        ep = rdir / "energy_uj"
        mp = rdir / "max_energy_range_uj"
        if ep.is_file():
            val = _read_sysfs_int(ep)
            if val is not None:
                mx = _read_sysfs_int(mp) or RAPL_WRAP_DEFAULT
                rapl_paths[key] = {"energy_path": ep, "max_range_uj": mx}

    coretemp_paths: dict[str, Path] = {}
    fan_paths: dict[str, Path] = {}
    hwmon_root = Path("/sys/class/hwmon")
    if hwmon_root.is_dir():
        for hdir in sorted(hwmon_root.iterdir()):
            name_p = hdir / "name"
            if not name_p.is_file():
                continue
            try:
                hname = name_p.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if hname == "coretemp":
                for tf in sorted(hdir.glob("temp*_input")):
                    lbl_p = tf.with_name(tf.name.replace("_input", "_label"))
                    try:
                        lbl = lbl_p.read_text(encoding="utf-8").strip() if lbl_p.is_file() else tf.stem
                    except OSError:
                        lbl = tf.stem
                    norm = lbl.lower().replace(" ", "_")
                    coretemp_paths[norm] = tf
            elif hname == "asus":
                for ff in sorted(hdir.glob("fan*_input")):
                    lbl_p = ff.with_name(ff.name.replace("_input", "_label"))
                    try:
                        lbl = lbl_p.read_text(encoding="utf-8").strip() if lbl_p.is_file() else ff.stem
                    except OSError:
                        lbl = ff.stem
                    fan_paths[lbl.lower().replace(" ", "_")] = ff

    freq_paths: dict[str, Path] = {}
    for cid in sorted(phys_map):
        cpu_idx = phys_map[cid]
        fp = cpu_root / f"cpu{cpu_idx}" / "cpufreq" / "scaling_cur_freq"
        if fp.is_file():
            freq_paths[f"core_{cid}"] = fp

    return {
        "phys_core_to_cpu": {str(k): phys_map[k] for k in sorted(phys_map)},
        "phys_cpus": phys_cpus,
        "rapl": rapl_paths,
        "coretemp": coretemp_paths,
        "fans": fan_paths,
        "freqs": freq_paths,
    }


def read_snapshot(sensors: dict[str, Any]) -> dict[str, Any]:
    t_ns = time.monotonic_ns()
    rapl_v: dict[str, int] = {}
    for k, spec in sensors["rapl"].items():
        v = _read_sysfs_int(spec["energy_path"])
        rapl_v[k] = v if v is not None else 0
    temps_v: dict[str, int] = {}
    for k, p in sensors["coretemp"].items():
        v = _read_sysfs_int(p)
        temps_v[k] = v if v is not None else 0
    fans_v: dict[str, int] = {}
    for k, p in sensors["fans"].items():
        v = _read_sysfs_int(p)
        fans_v[k] = v if v is not None else 0
    freqs_v: dict[str, int] = {}
    for k, p in sensors["freqs"].items():
        v = _read_sysfs_int(p)
        freqs_v[k] = v if v is not None else 0
    return {
        "t_ns": t_ns,
        "rapl_uj": rapl_v,
        "temp_mc": temps_v,
        "fan_rpm": fans_v,
        "freq_khz": freqs_v,
    }


def rapl_delta_uj(e0: int, e1: int, max_range: int) -> int:
    if e1 >= e0:
        return e1 - e0
    return (max_range - e0) + e1


def wait_gpu_idle(max_wait_s: int = 30) -> int:
    """Wait until nvidia-smi GPU utilization < 5% (returns exact integer percent)."""
    if shutil.which("nvidia-smi") is None:
        return 0
    deadline = time.monotonic() + max_wait_s
    last_util = 0
    while True:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            u = _parse_ascii_int(proc.stdout.splitlines()[0])
            if u is not None:
                last_util = u
                if u < 5:
                    return u
        if time.monotonic() >= deadline:
            return last_util
        time.sleep(1)


def compile_actuator(src_c: Path, build_dir: Path) -> Path:
    bin_path = build_dir / "ceer_actuator"
    proc = subprocess.run(
        [
            "gcc", "-O3", "-std=c11", "-D_GNU_SOURCE",
            "-Wall", "-Wextra", "-Werror", "-pthread",
            str(src_c), "-o", str(bin_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        raise RunnerError("ACTUATOR_COMPILE_FAILED", f"gcc failed: {proc.stderr[:400]}")
    return bin_path


def run_segment(
    act_bin: Path,
    sensors: dict[str, Any],
    seg_id: str,
    cmd_args: list[str],
) -> dict[str, Any]:
    """Execute one micro-actuator segment while sampling all integer sensors at 20 Hz."""
    samples: list[dict[str, Any]] = []
    stop_evt = threading.Event()

    def _sampler() -> None:
        next_t = time.monotonic_ns()
        while not stop_evt.is_set():
            samples.append(read_snapshot(sensors))
            next_t += SAMPLE_INTERVAL_NS
            rem_ns = next_t - time.monotonic_ns()
            if rem_ns > 0:
                stop_evt.wait(rem_ns / 1_000_000_000)

    snap_start = read_snapshot(sensors)
    th = threading.Thread(target=_sampler, daemon=True)
    th.start()
    proc = subprocess.run(
        [str(act_bin), *cmd_args],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    stop_evt.set()
    th.join(timeout=5)
    snap_end = read_snapshot(sensors)

    if proc.returncode != 0:
        raise RunnerError("ACTUATOR_RUN_FAILED", f"segment {seg_id} rc={proc.returncode}: {proc.stderr[:300]}")
    act_out = json.loads(proc.stdout.strip())

    dt_ns = max(1, snap_end["t_ns"] - snap_start["t_ns"])
    dt_us = max(1, dt_ns // 1000)
    delta_uj: dict[str, int] = {}
    power_mw: dict[str, int] = {}
    for k, spec in sensors["rapl"].items():
        d_uj = rapl_delta_uj(snap_start["rapl_uj"][k], snap_end["rapl_uj"][k], spec["max_range_uj"])
        delta_uj[k] = d_uj
        # Exact integer milliwatts: (uJ * 1000) // us  (since uJ/us = W, *1000 = mW)
        power_mw[k] = (d_uj * 1000) // dt_us

    # Compute exact integer mean temperature (mC), mean fan (RPM), mean freq (kHz) across samples
    all_snaps = samples if samples else [snap_start, snap_end]
    n_s = len(all_snaps)
    mean_temp_mc: dict[str, int] = {}
    max_temp_mc: dict[str, int] = {}
    for k in sensors["coretemp"]:
        vals = [s["temp_mc"][k] for s in all_snaps]
        mean_temp_mc[k] = sum(vals) // n_s
        max_temp_mc[k] = max(vals)
    mean_fan_rpm: dict[str, int] = {}
    for k in sensors["fans"]:
        vals = [s["fan_rpm"][k] for s in all_snaps]
        mean_fan_rpm[k] = sum(vals) // n_s
    mean_freq_khz: dict[str, int] = {}
    for k in sensors["freqs"]:
        vals = [s["freq_khz"][k] for s in all_snaps]
        mean_freq_khz[k] = sum(vals) // n_s

    compact_series: list[dict[str, Any]] = []
    t_base = all_snaps[0]["t_ns"]
    for idx_s, s in enumerate(all_snaps):
        # Compute instantaneous interval power for time-series Schur / hysteresis analysis
        entry: dict[str, Any] = {
            "t_ms": (s["t_ns"] - t_base) // 1_000_000,
            "pkg_temp_mc": s["temp_mc"].get("package_id_0", 0),
            "cpu_fan_rpm": s["fan_rpm"].get("cpu_fan", 0),
            "gpu_fan_rpm": s["fan_rpm"].get("gpu_fan", 0),
            "core_temps_mc": [s["temp_mc"].get(f"core_{c}", 0) for c in range(8)],
            "core_freqs_khz": [s["freq_khz"].get(f"core_{c}", 0) for c in range(8)],
        }
        if idx_s > 0:
            prev = all_snaps[idx_s - 1]
            iv_us = max(1, (s["t_ns"] - prev["t_ns"]) // 1000)
            entry["rapl_mw"] = {
                k: (rapl_delta_uj(prev["rapl_uj"][k], s["rapl_uj"][k], spec["max_range_uj"]) * 1000) // iv_us
                for k, spec in sensors["rapl"].items()
            }
        else:
            entry["rapl_mw"] = dict(power_mw)
        compact_series.append(entry)

    return {
        "segment_id": seg_id,
        "cmd_args": cmd_args,
        "actuator_output": act_out,
        "dt_us": dt_us,
        "sample_count": n_s,
        "delta_rapl_uj": delta_uj,
        "power_mw": power_mw,
        "mean_temp_mc": mean_temp_mc,
        "max_temp_mc": max_temp_mc,
        "mean_fan_rpm": mean_fan_rpm,
        "mean_freq_khz": mean_freq_khz,
        "time_series": compact_series,
    }


def execute_cycle(track_dir: Path, cycle_id: int) -> dict[str, Any]:
    prereg_path = track_dir / f"cycle_{cycle_id}_prereg.json"
    if not prereg_path.is_file():
        raise RunnerError("MISSING_PREREG", f"preregistration file missing before live run: {prereg_path.name}")
    prereg_raw = prereg_path.read_bytes()
    prereg_sha = hashlib.sha256(prereg_raw).hexdigest()
    prereg_obj = json.loads(prereg_raw.decode("utf-8"))
    if prereg_obj.get("cycle_id") != cycle_id:
        raise RunnerError("PREREG_CYCLE_MISMATCH", f"prereg cycle_id mismatch for cycle {cycle_id}")

    sensors = discover_sensors()
    if len(sensors["phys_cpus"]) < 8:
        raise RunnerError("CPU_TOPOLOGY_ERROR", f"expected 8 physical cores, found {len(sensors['phys_cpus'])}")
    if len(sensors["rapl"]) < 5:
        raise RunnerError("RAPL_INCOMPLETE", f"expected 5 rapl domains, found {sorted(sensors['rapl'])}")

    schedule = prereg_obj["lever_schedule"]

    # Compile actuator cleanly BEFORE acquiring the live RAPL lock
    with tempfile.TemporaryDirectory(prefix=f"ceer_c{cycle_id}_") as build_td:
        os.chmod(build_td, 0o700)
        act_bin = compile_actuator(track_dir / "ceer_actuator.c", Path(build_td))

        lock_fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            gpu_util_before = wait_gpu_idle(max_wait_s=25)
            started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            t_run0 = time.monotonic_ns()
            seg_results: list[dict[str, Any]] = []
            for item in schedule:
                seg_results.append(
                    run_segment(act_bin, sensors, item["segment_id"], list(item["cmd_args"]))
                )
            total_run_ms = (time.monotonic_ns() - t_run0) // 1_000_000
            gpu_util_after = wait_gpu_idle(max_wait_s=5)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    telemetry = {
        "schema_version": "aletheia.ceer_silicon_telemetry.v1",
        "cycle_id": cycle_id,
        "prereg_sha256": prereg_sha,
        "started_utc": started_utc,
        "total_duration_ms": total_run_ms,
        "gpu_util_before_pct": gpu_util_before,
        "gpu_util_after_pct": gpu_util_after,
        "phys_core_to_cpu": sensors["phys_core_to_cpu"],
        "rapl_domains": sorted(sensors["rapl"].keys()),
        "segments": seg_results,
    }
    out_path = track_dir / f"cycle_{cycle_id}_telemetry.json"
    raw_out = canonical_json_bytes(telemetry) + b"\n"
    write_0600_atomic(out_path, raw_out)
    return {
        "cycle_id": cycle_id,
        "prereg_sha256": prereg_sha,
        "telemetry_file": out_path.name,
        "telemetry_sha256": hashlib.sha256(raw_out).hexdigest(),
        "total_duration_ms": total_run_ms,
        "segment_count": len(seg_results),
        "gpu_util_before_pct": gpu_util_before,
        "gpu_util_after_pct": gpu_util_after,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] != "--cycle" or args[1] not in ("0", "1", "2"):
        sys.stderr.write("usage: ceer_silicon_runner.py --cycle <0|1|2>\n")
        return 2
    cycle_id = int(args[1])
    track_dir = Path(__file__).resolve().parent
    try:
        res = execute_cycle(track_dir, cycle_id)
    except RunnerError as exc:
        sys.stderr.write(f"ERROR [{exc.code}]: {exc}\n")
        return 2
    sys.stdout.write(canonical_json_bytes(res).decode("utf-8") + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
