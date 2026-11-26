#!/usr/bin/env python3
"""Track S53 Phase 1: Beyond-Language Raw Physical Sensor Tomography Probe.

Captures a passive, ultra-lightweight (<1% CPU, zero sudo, zero microphone/camera)
multi-channel thermal-electrical-mechanical time series from live Linux sysfs
(`hwmon*`, `thermal_zone*`, `cpufreq`, `iio:device*`) and streaming `nvidia-smi`,
then runs a strict Stage-A -> Stage-B beyond-language operator extractor:

  Stage A (Label-Stripping & Exact Affine+Permutation Gauge Invariance):
    - Drops all human channel names and physical units; feeds ONLY anonymous
      integer matrix X in Z^(T x D) into the extractor.
    - Automatically drops stationary channels strictly via the label-free
      algebraic invariant Var(x_j) == 0.
    - Stress-tests exact invariance under seeded random column permutation pi
      and random per-channel positive rational affine rescalings x_j -> a_j*x_j + b_j.

  Stage B (Blind Pure-Q Relational, Schur Dark-Mode & Dissipation Invariants):
    1. Exact scale-free squared correlation R^2 and regularized precision partial
       correlation P_ij (zero sqrt, zero floats in exact core) + blind pure-Q
       greedy modularity clustering -> held-out exact rational ARI.
    2. Empirical off-brane dark-mode Schur complement S_{A|B} (Bareiss-Sylvester
       exact SPD inertia, unexplained variance eta_i, residual cross-coupling
       rho^2_{ij|B}, and exact affine-invariant participation ratio PR(S_{A|B})).
    3. Dimensionless time-reversal asymmetry A^2_ij(tau), causal arrow dir_ij(tau),
       dissipation fraction Gamma_ij(tau), and blind source/sink flow Phi_i(tau),
       separating conductive/symmetric (`qfree`-like) vs. dissipative/irreversible
       (`mfree`-like) physical couplings.
    4. Matched adversarial nulls: pure-Q circular-shift surrogates (exact) +
       IAAFT amplitude-spectrum-and-marginal-preserving surrogates (sampled, when
       numpy is available) + out-of-sample split-half replication.

Verification:
  python3 -I -B sensor_tomography_probe.py --analyze raw_sensor_snapshot.json --out-cert sensor_tomography_certificate.json
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA_RAW = "aletheia.s53_raw_sensor_snapshot.v1"
SCHEMA_CERT = "aletheia.s53_beyond_language_tomography.v1"

RIDGE_LAMBDA = Fraction(1, 20)
LAGS: Tuple[int, ...] = (1, 2, 3, 5)
GAUGE_SEED = 2026112401
NULL_SEED = 2026112402
IAAFT_SEED = 2026112403
CLUSTER_NULL_SEED = 2026112404
NUM_SURROGATES = 200
IAAFT_ITERS = 30


class ProbeError(Exception):
    """Typed fail-closed error for sensor capture and analysis."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _require(cond: bool, code: str, detail: str) -> None:
    if not cond:
        raise ProbeError(code, detail)


def _fmt_q(val: Fraction) -> str:
    if val.denominator == 1:
        return str(val.numerator)
    return f"{val.numerator}/{val.denominator}"


_Q12_SCALE = 10**12


def _q12_ticks(val: Fraction) -> int:
    """Exact pure-integer floor projection to 10^-12 grid (zero floats, zero coprime blowup)."""
    return (val.numerator * _Q12_SCALE) // val.denominator


def _q12_frac(val: Fraction) -> Fraction:
    return Fraction(_q12_ticks(val), _Q12_SCALE)


def _fmt_q12(val: Fraction) -> str:
    """Exact pure-integer floor projection to 10^-12 rational grid (zero floats, compact JSON)."""
    return _fmt_q(_q12_frac(val))


def _canonical_json_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _atomic_write_0600(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = f".{path.name}.tmp.{os.getpid()}"
    tmp_path = path.parent / tmp_name
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(data)
        written = 0
        while written < len(data):
            n = os.write(fd, view[written:])
            _require(n > 0, "SHORT_WRITE", "os.write returned 0 bytes")
            written += n
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(str(tmp_path), str(path))


def _read_int_sysfs(path: Path) -> Optional[int]:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    sign = 1
    body = raw
    if body[0] in ("+", "-"):
        if body[0] == "-":
            sign = -1
        body = body[1:]
    if not body or not all("0" <= ch <= "9" for ch in body):
        return None
    return sign * int(body)


def _parse_scaled_decimal_int(raw: str, scale_pow10: int) -> Optional[int]:
    s = raw.strip()
    if not s or s.upper() in ("[N/A]", "N/A", "NAN"):
        return None
    sign = 1
    if s[0] in ("+", "-"):
        if s[0] == "-":
            sign = -1
        s = s[1:]
    if "." in s:
        parts = s.split(".")
        if len(parts) != 2:
            return None
        whole, frac = parts[0], parts[1]
    else:
        whole, frac = s, ""
    if not whole or not all("0" <= ch <= "9" for ch in whole):
        return None
    if frac and not all("0" <= ch <= "9" for ch in frac):
        return None
    if len(frac) > scale_pow10:
        frac = frac[:scale_pow10]
    else:
        frac = frac + ("0" * (scale_pow10 - len(frac)))
    return sign * int(whole + frac)


def _discover_sysfs_channels() -> List[Dict[str, Any]]:
    """Discover readable thermal/electrical/mechanical sysfs channels (ZERO mic/cam, ZERO sudo)."""
    channels: List[Dict[str, Any]] = []

    hwmon_root = Path("/sys/class/hwmon")
    if hwmon_root.is_dir():
        for hdir in sorted(hwmon_root.iterdir(), key=lambda p: p.name):
            name_file = hdir / "name"
            try:
                dev_name = name_file.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            for pat, kind in (
                ("temp*_input", "temp_mC"),
                ("fan*_input", "fan_rpm"),
                ("power*_input", "power_uW"),
                ("in*_input", "volt_mV"),
                ("curr*_input", "curr_mA"),
            ):
                for fpath in sorted(hdir.glob(pat), key=lambda p: p.name):
                    if _read_int_sysfs(fpath) is None:
                        continue
                    lbl_path = fpath.with_name(fpath.name.replace("_input", "_label"))
                    lbl = ""
                    try:
                        if lbl_path.is_file():
                            lbl = lbl_path.read_text(encoding="utf-8").strip()
                    except OSError:
                        lbl = ""
                    if dev_name == "coretemp":
                        module = "cpu_die_thermal"
                    elif dev_name == "nvme":
                        module = "nvme_thermal"
                    elif dev_name == "asus" and kind == "fan_rpm":
                        module = "mechanical_cooling"
                    elif dev_name in ("acpitz", "iwlwifi_1"):
                        module = "chassis_acpi_thermal"
                    else:
                        module = "power_bus"
                    channels.append(
                        {
                            "source": "sysfs",
                            "path": str(fpath),
                            "device": dev_name,
                            "field": fpath.name,
                            "label": lbl or fpath.name,
                            "unit_scale": kind,
                            "module": module,
                        }
                    )

    tz_root = Path("/sys/class/thermal")
    if tz_root.is_dir():
        for zdir in sorted(tz_root.glob("thermal_zone*"), key=lambda p: p.name):
            tfile = zdir / "temp"
            if _read_int_sysfs(tfile) is None:
                continue
            try:
                ztype = (zdir / "type").read_text(encoding="utf-8").strip()
            except OSError:
                ztype = zdir.name
            channels.append(
                {
                    "source": "sysfs",
                    "path": str(tfile),
                    "device": zdir.name,
                    "field": "temp",
                    "label": ztype,
                    "unit_scale": "temp_mC",
                    "module": "chassis_acpi_thermal",
                }
            )

    # Physical core frequencies (1 per physical core: even policies 0,2,...,14 if present)
    cpufreq_root = Path("/sys/devices/system/cpu/cpufreq")
    if cpufreq_root.is_dir():
        for pol_idx in (0, 2, 4, 6, 8, 10, 12, 14):
            fpath = cpufreq_root / f"policy{pol_idx}" / "scaling_cur_freq"
            if _read_int_sysfs(fpath) is not None:
                channels.append(
                    {
                        "source": "sysfs",
                        "path": str(fpath),
                        "device": f"policy{pol_idx}",
                        "field": "scaling_cur_freq",
                        "label": f"cpu_core{pol_idx // 2}_freq_kHz",
                        "unit_scale": "freq_kHz",
                        "module": "cpu_clock_electrical",
                    }
                )

    # IIO hinge/orientation sensors (strictly non-AV physical sensors)
    iio_root = Path("/sys/bus/iio/devices")
    if iio_root.is_dir():
        for idir in sorted(iio_root.glob("iio:device*"), key=lambda p: p.name):
            try:
                iname = (idir / "name").read_text(encoding="utf-8").strip()
            except OSError:
                iname = idir.name
            for fpath in sorted(idir.glob("in_*_raw"), key=lambda p: p.name):
                if _read_int_sysfs(fpath) is None:
                    continue
                lbl_path = fpath.with_name(fpath.name.replace("_raw", "_label"))
                lbl = fpath.name
                try:
                    if lbl_path.is_file():
                        lbl = lbl_path.read_text(encoding="utf-8").strip()
                except OSError:
                    pass
                channels.append(
                    {
                        "source": "sysfs",
                        "path": str(fpath),
                        "device": f"{idir.name}:{iname}",
                        "field": fpath.name,
                        "label": lbl,
                        "unit_scale": "raw_int",
                        "module": "chassis_hinge_iio",
                    }
                )

    # Intel RAPL micro-Joule energy counters (per-interval delta_uj; strictly non-AV, zero sudo)
    rapl_root = Path("/sys/class/powercap")
    if rapl_root.is_dir():
        for rdir in sorted(rapl_root.glob("intel-rapl*"), key=lambda p: p.name):
            if not rdir.is_dir():
                continue
            efile = rdir / "energy_uj"
            if _read_int_sysfs(efile) is None:
                continue
            try:
                rname = (rdir / "name").read_text(encoding="utf-8").strip()
            except OSError:
                rname = rdir.name
            max_range = _read_int_sysfs(rdir / "max_energy_range_uj") or 0
            channels.append(
                {
                    "source": "sysfs_rapl_delta",
                    "path": str(efile),
                    "device": rdir.name,
                    "field": "delta_energy_uj",
                    "label": f"{rdir.name}:{rname}_dE_uJ",
                    "unit_scale": "energy_uJ_per_step",
                    "module": "cpu_rapl_energy_uj",
                    "max_range_uj": max_range,
                }
            )

    return channels


GPU_CHANNELS: Tuple[Tuple[str, str, int], ...] = (
    ("gpu_power_cW", "power_cW", 2),
    ("gpu_temp_C", "temp_C", 0),
    ("gpu_clock_sm_MHz", "freq_MHz", 0),
    ("gpu_clock_mem_MHz", "freq_MHz", 0),
    ("gpu_util_pct", "pct", 0),
    ("gpu_mem_util_pct", "pct", 0),
)


def capture_live_snapshot(duration_seconds: int, hz: int) -> Dict[str, Any]:
    """Capture passive live multi-channel physical time series (<1% CPU, zero mic/cam)."""
    _require(duration_seconds >= 10 and duration_seconds <= 600, "INVALID_DURATION", "duration must be in [10, 600]")
    _require(hz in (1, 2, 4, 5), "INVALID_HZ", "hz must be in {1, 2, 4, 5}")
    target_samples = duration_seconds * hz
    interval_ms = 1000 // hz

    sysfs_meta = _discover_sysfs_channels()
    _require(len(sysfs_meta) >= 10, "TOO_FEW_SENSORS", f"found only {len(sysfs_meta)} readable sysfs channels")

    gpu_cmd = [
        "stdbuf",
        "-oL",
        "nvidia-smi",
        "--query-gpu=power.draw,temperature.gpu,clocks.current.sm,clocks.current.memory,utilization.gpu,utilization.memory",
        "--format=csv,noheader,nounits",
        "-lms",
        str(interval_ms),
    ]
    gpu_proc: Optional[subprocess.Popen[str]] = None
    gpu_enabled = False
    try:
        gpu_proc = subprocess.Popen(
            gpu_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        gpu_enabled = True
    except OSError:
        gpu_proc = None
        gpu_enabled = False

    all_meta: List[Dict[str, Any]] = []
    for idx, ch in enumerate(sysfs_meta):
        all_meta.append(
            {
                "channel_id": idx,
                "source": ch["source"],
                "device": ch["device"],
                "field": ch["field"],
                "label": ch["label"],
                "unit_scale": ch["unit_scale"],
                "module": ch["module"],
            }
        )
    if gpu_enabled:
        base_idx = len(all_meta)
        for offset, (glabel, gunit, _pow10) in enumerate(GPU_CHANNELS):
            all_meta.append(
                {
                    "channel_id": base_idx + offset,
                    "source": "nvidia-smi",
                    "device": "gpu0",
                    "field": glabel,
                    "label": glabel,
                    "unit_scale": gunit,
                    "module": "gpu_electromechanical",
                }
            )

    sysfs_paths = [Path(ch["path"]) for ch in sysfs_meta]
    is_rapl = [ch["source"] == "sysfs_rapl_delta" for ch in sysfs_meta]
    rapl_max_range = [int(ch.get("max_range_uj", 0)) for ch in sysfs_meta]
    timestamps_ms: List[int] = []
    rows: List[List[int]] = []
    last_sysfs = [_read_int_sysfs(p) or 0 for p in sysfs_paths]
    last_rapl_raw = [_read_int_sysfs(p) or 0 for p in sysfs_paths]
    last_gpu = [0] * len(GPU_CHANNELS)

    # Warm-up tick so first RAPL delta covers one exact sampling interval
    if gpu_enabled and gpu_proc is not None and gpu_proc.stdout is not None:
        _ = gpu_proc.stdout.readline()
    else:
        time.sleep(interval_ms / 1000)
    for j, p in enumerate(sysfs_paths):
        v0 = _read_int_sysfs(p)
        if v0 is not None:
            last_sysfs[j] = v0
            last_rapl_raw[j] = v0

    t0_ns = time.monotonic_ns()
    t0_utc_s = int(time.time())
    try:
        for sample_idx in range(target_samples):
            if gpu_enabled and gpu_proc is not None and gpu_proc.stdout is not None:
                line = gpu_proc.stdout.readline()
                if line:
                    parts = [p.strip() for p in line.strip().split(",")]
                    if len(parts) == len(GPU_CHANNELS):
                        parsed_gpu: List[int] = []
                        ok_gpu = True
                        for p_str, (_gl, _gu, pow10) in zip(parts, GPU_CHANNELS):
                            val = _parse_scaled_decimal_int(p_str, pow10)
                            if val is None:
                                ok_gpu = False
                                break
                            parsed_gpu.append(val)
                        if ok_gpu:
                            last_gpu = parsed_gpu
            else:
                target_ns = t0_ns + ((sample_idx + 1) * interval_ms * 1_000_000)
                rem_ns = target_ns - time.monotonic_ns()
                if rem_ns > 0:
                    time.sleep(rem_ns / 1_000_000_000)

            now_ms = (time.monotonic_ns() - t0_ns) // 1_000_000
            cur_sysfs: List[int] = []
            for j, p in enumerate(sysfs_paths):
                v = _read_int_sysfs(p)
                if is_rapl[j]:
                    if v is None:
                        delta_v = 0
                    else:
                        prev = last_rapl_raw[j]
                        if v >= prev:
                            delta_v = v - prev
                        elif rapl_max_range[j] > prev:
                            delta_v = (rapl_max_range[j] - prev) + v
                        else:
                            delta_v = 0
                        last_rapl_raw[j] = v
                    cur_sysfs.append(delta_v)
                else:
                    if v is None:
                        v = last_sysfs[j]
                    else:
                        last_sysfs[j] = v
                    cur_sysfs.append(v)

            timestamps_ms.append(int(now_ms))
            if gpu_enabled:
                rows.append(cur_sysfs + list(last_gpu))
            else:
                rows.append(cur_sysfs)
    finally:
        if gpu_proc is not None:
            gpu_proc.terminate()
            try:
                gpu_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                gpu_proc.kill()
                gpu_proc.wait(timeout=2)

    elapsed_ms = timestamps_ms[-1] if timestamps_ms else 0
    payload = {
        "schema_version": SCHEMA_RAW,
        "capture_utc_epoch_s": t0_utc_s,
        "cadence_hz": hz,
        "nominal_interval_ms": interval_ms,
        "elapsed_ms": elapsed_ms,
        "sample_count": len(rows),
        "channel_count": len(all_meta),
        "mic_cam_accessed": False,
        "sudo_used": False,
        "timestamps_ms": timestamps_ms,
        "X_anonymous": rows,
        "held_out_ground_truth_channels": all_meta,
    }
    raw_hash = hashlib.sha256(_canonical_json_bytes(rows)).hexdigest()
    payload["x_anonymous_sha256"] = raw_hash
    return payload


# ==============================================================================
# Stage A -> Stage B Pure-Z/Q Exact Operator Algebra (Zero Floats)
# ==============================================================================


def _exact_center_gram(x_mat: Sequence[Sequence[Fraction]]) -> Tuple[List[List[Fraction]], List[List[Fraction]]]:
    """Return centered matrix Z (T x D) and exact sample covariance Sigma = (1/T) Z^T Z."""
    t_len = len(x_mat)
    _require(t_len >= 8, "TOO_FEW_SAMPLES", "need >= 8 samples")
    d_len = len(x_mat[0])
    means = [sum(x_mat[t][j] for t in range(t_len)) / t_len for j in range(d_len)]
    z_mat = [[x_mat[t][j] - means[j] for j in range(d_len)] for t in range(t_len)]
    sigma: List[List[Fraction]] = [[Fraction(0) for _ in range(d_len)] for _ in range(d_len)]
    for i in range(d_len):
        zi = [z_mat[t][i] for t in range(t_len)]
        for j in range(i, d_len):
            zj = [z_mat[t][j] for t in range(t_len)]
            dot = sum(a * b for a, b in zip(zi, zj)) / t_len
            sigma[i][j] = dot
            sigma[j][i] = dot
    return z_mat, sigma


def _exact_matrix_inverse_q(mat: Sequence[Sequence[Fraction]]) -> List[List[Fraction]]:
    """Exact pure-Q Gauss-Jordan inversion with strict pivot verification."""
    n = len(mat)
    aug = [list(mat[i]) + [Fraction(1 if i == j else 0) for j in range(n)] for i in range(n)]
    for col in range(n):
        pivot_row = -1
        for r in range(col, n):
            if aug[r][col] != 0:
                pivot_row = r
                break
        _require(pivot_row >= 0, "SINGULAR_MATRIX", f"matrix singular at column {col}")
        if pivot_row != col:
            aug[col], aug[pivot_row] = aug[pivot_row], aug[col]
        piv = aug[col][col]
        aug[col] = [v / piv for v in aug[col]]
        for r in range(n):
            if r != col and aug[r][col] != 0:
                factor = aug[r][col]
                aug[r] = [aug[r][c] - factor * aug[col][c] for c in range(2 * n)]
    return [row[n:] for row in aug]


def _bareiss_principal_minor_inertia_q(sym_mat: Sequence[Sequence[Fraction]]) -> Tuple[int, int, int]:
    """Exact pure-Q leading-principal-minor Sylvester/Bareiss inertia for symmetric matrices."""
    n = len(sym_mat)
    # Exact congruence diagonalization (LDL^T for symmetric matrices with zero pivots handled)
    work = [list(row) for row in sym_mat]
    n_pos = 0
    n_zero = 0
    n_neg = 0
    idx = 0
    while idx < n:
        if work[idx][idx] != 0:
            piv = work[idx][idx]
            if piv > 0:
                n_pos += 1
            else:
                n_neg += 1
            for r in range(idx + 1, n):
                if work[r][idx] != 0:
                    factor = work[r][idx] / piv
                    for c in range(idx + 1, n):
                        work[r][c] -= factor * work[idx][c]
            idx += 1
        else:
            # Look for non-zero off-diagonal entry in remaining submatrix
            swap_j = -1
            for j in range(idx + 1, n):
                if work[idx][j] != 0:
                    swap_j = j
                    break
            if swap_j < 0:
                n_zero += 1
                idx += 1
            else:
                # 2x2 hyperbolic pivot block [[0, b], [b, d]] has inertia (1, 0, 1)
                if swap_j != idx + 1:
                    work[idx + 1], work[swap_j] = work[swap_j], work[idx + 1]
                    for r in range(n):
                        work[r][idx + 1], work[r][swap_j] = work[r][swap_j], work[r][idx + 1]
                b = work[idx][idx + 1]
                d = work[idx + 1][idx + 1]
                b2 = b * b
                n_pos += 1
                n_neg += 1
                # Inverse of [[0, b], [b, d]] is [[-d/b^2, 1/b], [1/b, 0]]
                for r in range(idx + 2, n):
                    u0 = work[r][idx]
                    u1 = work[r][idx + 1]
                    for c in range(idx + 2, n):
                        v0 = work[idx][c]
                        v1 = work[idx + 1][c]
                        work[r][c] -= (-d * u0 * v0 + b * (u0 * v1 + u1 * v0)) / b2
                idx += 2
    return (n_pos, n_zero, n_neg)


def _sign_q(val: Fraction) -> int:
    if val > 0:
        return 1
    if val < 0:
        return -1
    return 0


def _compute_scale_free_r2_and_partial(
    sigma: Sequence[Sequence[Fraction]],
    ridge_lambda: Fraction,
) -> Tuple[List[List[Fraction]], List[List[int]], List[List[Fraction]], List[List[int]], Tuple[int, int, int]]:
    """Compute exact affine-invariant R^2, sign(R), regularized partial-corr^2 P, sign(P), and SPD inertia."""
    d = len(sigma)
    r2_mat: List[List[Fraction]] = [[Fraction(0) for _ in range(d)] for _ in range(d)]
    r_sign: List[List[int]] = [[0 for _ in range(d)] for _ in range(d)]
    for i in range(d):
        for j in range(d):
            if i == j:
                r2_mat[i][j] = Fraction(1)
                r_sign[i][j] = 1
            else:
                denom = sigma[i][i] * sigma[j][j]
                _require(denom > 0, "ZERO_VARIANCE_CHANNEL", f"zero variance at ({i},{j})")
                r2_mat[i][j] = (sigma[i][j] * sigma[i][j]) / denom
                r_sign[i][j] = _sign_q(sigma[i][j])

    # Scale-covariant ridge: Sigma_lambda = Sigma + lambda * diag(Sigma)
    sigma_reg = [
        [sigma[i][j] + (ridge_lambda * sigma[i][i] if i == j else Fraction(0)) for j in range(d)]
        for i in range(d)
    ]
    inertia_reg = _bareiss_principal_minor_inertia_q(sigma_reg)
    theta = _exact_matrix_inverse_q(sigma_reg)

    p2_mat: List[List[Fraction]] = [[Fraction(0) for _ in range(d)] for _ in range(d)]
    p_sign: List[List[int]] = [[0 for _ in range(d)] for _ in range(d)]
    for i in range(d):
        for j in range(d):
            if i == j:
                p2_mat[i][j] = Fraction(1)
                p_sign[i][j] = 1
            else:
                denom = theta[i][i] * theta[j][j]
                _require(denom > 0, "NON_SPD_PRECISION", f"non-positive precision diagonal at ({i},{j})")
                p2_mat[i][j] = (theta[i][j] * theta[i][j]) / denom
                p_sign[i][j] = _sign_q(-theta[i][j])

    return r2_mat, r_sign, p2_mat, p_sign, inertia_reg


def _blind_greedy_modularity_q(affinity: Sequence[Sequence[Fraction]]) -> Tuple[List[int], Fraction]:
    """Deterministic permutation-invariant pure-Z/Q greedy modularity clustering (blind K, 10^12 common grid)."""
    d = len(affinity)
    # Common 10^12 integer ticks avoid coprime denominator blowup while staying 100% exact & gauge-invariant
    w = [[0 if i == j else _q12_ticks(affinity[i][j]) for j in range(d)] for i in range(d)]
    deg = [sum(w[i]) for i in range(d)]
    two_m = sum(deg)
    if two_m == 0:
        return list(range(d)), Fraction(0)

    two_m_sq = two_m * two_m
    comms: List[List[int]] = [[i] for i in range(d)]

    def _comm_signature(members: Sequence[int]) -> Tuple[int, int, Tuple[int, ...]]:
        return (len(members), sum(deg[u] for u in members), tuple(sorted(deg[u] for u in members)))

    # Maintain exact integer numerator of Q * two_m^2
    cur_q_num = sum(
        (sum(w[u][v] for u in m for v in m) * two_m) - (sum(deg[u] for u in m) ** 2)
        for m in comms
    )
    while len(comms) > 1:
        best_delta_num = 0
        best_pair: Optional[Tuple[int, int]] = None
        best_tie: Optional[Tuple[Any, Any]] = None
        num_c = len(comms)
        for a in range(num_c):
            ma = comms[a]
            ka = sum(deg[u] for u in ma)
            for b in range(a + 1, num_c):
                mb = comms[b]
                kb = sum(deg[u] for u in mb)
                e_ab = sum(w[u][v] for u in ma for v in mb)
                # delta * two_m^2 = 2 * e_ab * two_m - 2 * ka * kb (exact pure integer!)
                delta_num = (2 * e_ab * two_m) - (2 * ka * kb)
                if delta_num > best_delta_num:
                    best_delta_num = delta_num
                    best_pair = (a, b)
                    sig_a = _comm_signature(ma)
                    sig_b = _comm_signature(mb)
                    best_tie = (sig_a, sig_b) if sig_a <= sig_b else (sig_b, sig_a)
                elif delta_num == best_delta_num and best_pair is not None and delta_num > 0:
                    sig_a = _comm_signature(ma)
                    sig_b = _comm_signature(mb)
                    cand_tie = (sig_a, sig_b) if sig_a <= sig_b else (sig_b, sig_a)
                    if best_tie is None or cand_tie < best_tie:
                        best_pair = (a, b)
                        best_tie = cand_tie
        if best_pair is None or best_delta_num <= 0:
            break
        a, b = best_pair
        merged = sorted(comms[a] + comms[b])
        comms = [comms[k] for k in range(num_c) if k != a and k != b] + [merged]
        cur_q_num += best_delta_num

    comms_sorted = sorted(comms, key=_comm_signature, reverse=True)
    labels = [0] * d
    for cid, members in enumerate(comms_sorted):
        for u in members:
            labels[u] = cid
    return labels, Fraction(cur_q_num, two_m_sq)


def _exact_ari_q(labels_a: Sequence[Any], labels_b: Sequence[Any]) -> Fraction:
    """Exact pure-Q Adjusted Rand Index between two partitions."""
    n = len(labels_a)
    _require(n == len(labels_b) and n >= 2, "INVALID_ARI_LEN", "partitions must match with len >= 2")

    def _comb2(k: int) -> int:
        return (k * (k - 1)) // 2

    counts: Dict[Tuple[Any, Any], int] = {}
    row_sums: Dict[Any, int] = {}
    col_sums: Dict[Any, int] = {}
    for a, b in zip(labels_a, labels_b):
        counts[(a, b)] = counts.get((a, b), 0) + 1
        row_sums[a] = row_sums.get(a, 0) + 1
        col_sums[b] = col_sums.get(b, 0) + 1

    sum_comb_c = sum(_comb2(v) for v in counts.values())
    sum_comb_a = sum(_comb2(v) for v in row_sums.values())
    sum_comb_b = sum(_comb2(v) for v in col_sums.values())
    total_comb = _comb2(n)
    expected = Fraction(sum_comb_a * sum_comb_b, total_comb)
    max_idx = Fraction(sum_comb_a + sum_comb_b, 2)
    denom = max_idx - expected
    if denom == 0:
        return Fraction(1) if sum_comb_c == expected else Fraction(0)
    return (Fraction(sum_comb_c) - expected) / denom


def _empirical_schur_dark_mode_q(
    sigma: Sequence[Sequence[Fraction]],
    idx_a: Sequence[int],
    idx_b: Sequence[int],
    ridge_lambda: Fraction,
) -> Dict[str, Any]:
    """Exact pure-Q Schur complement S_{A|B} = Sigma_AA - Sigma_AB (Sigma_BB + lam*diag)^-1 Sigma_BA."""
    na = len(idx_a)
    nb = len(idx_b)
    _require(na >= 2 and nb >= 1, "INVALID_SCHUR_PARTITION", "need |A| >= 2 and |B| >= 1")

    sig_aa = [[sigma[i][j] for j in idx_a] for i in idx_a]
    sig_ab = [[sigma[i][j] for j in idx_b] for i in idx_a]
    sig_ba = [[sigma[i][j] for j in idx_a] for i in idx_b]
    sig_bb_reg = [
        [sigma[idx_b[r]][idx_b[c]] + (ridge_lambda * sigma[idx_b[r]][idx_b[r]] if r == c else Fraction(0)) for c in range(nb)]
        for r in range(nb)
    ]
    inv_bb = _exact_matrix_inverse_q(sig_bb_reg)

    # M = inv_bb @ sig_ba (nb x na)
    m_mat = [
        [sum(inv_bb[r][k] * sig_ba[k][c] for k in range(nb)) for c in range(na)]
        for r in range(nb)
    ]
    # S = sig_aa - sig_ab @ M (na x na)
    schur = [
        [sig_aa[r][c] - sum(sig_ab[r][k] * m_mat[k][c] for k in range(nb)) for c in range(na)]
        for r in range(na)
    ]
    inertia_s = _bareiss_principal_minor_inertia_q(schur)

    # Scale-free dark-mode variance retention eta_i and off-diagonal residual rho^2_{ij|B}
    eta_ratios: List[Fraction] = []
    for r in range(na):
        _require(sig_aa[r][r] > 0 and schur[r][r] > 0, "NON_POS_SCHUR_DIAG", f"non-pos diag at A[{r}]")
        eta_ratios.append(schur[r][r] / sig_aa[r][r])

    offdiag_rho2: List[Fraction] = []
    raw_offdiag_r2: List[Fraction] = []
    for r in range(na):
        for c in range(r + 1, na):
            rho2_cond = (schur[r][c] * schur[r][c]) / (schur[r][r] * schur[c][c])
            rho2_raw = (sig_aa[r][c] * sig_aa[r][c]) / (sig_aa[r][r] * sig_aa[c][c])
            offdiag_rho2.append(rho2_cond)
            raw_offdiag_r2.append(rho2_raw)

    eta_ticks = [_q12_ticks(v) for v in eta_ratios]
    off_ticks = [_q12_ticks(v) for v in offdiag_rho2]
    raw_ticks = [_q12_ticks(v) for v in raw_offdiag_r2]

    mean_eta = Fraction(sum(eta_ticks), na * _Q12_SCALE)
    mean_offdiag_rho2 = Fraction(sum(off_ticks), len(off_ticks) * _Q12_SCALE)
    mean_raw_r2 = Fraction(sum(raw_ticks), len(raw_ticks) * _Q12_SCALE)
    max_offdiag_rho2 = Fraction(max(off_ticks), _Q12_SCALE)
    # Exact affine-invariant participation ratio PR(S_corr) = |A|^2 / (|A| + 2 * sum_{r<c} rho^2_{rc|B})
    pr_denom = Fraction(na * _Q12_SCALE + 2 * sum(off_ticks), _Q12_SCALE)
    participation_ratio = Fraction(na * na) / pr_denom
    dark_mode_compression = Fraction(na) / participation_ratio

    return {
        "dim_a": na,
        "dim_b": nb,
        "schur_inertia": list(inertia_s),
        "schur_is_spd": inertia_s == (na, 0, 0),
        "eta_ratios_q": [_fmt_q12(v) for v in eta_ratios],
        "mean_unexplained_variance_eta_q": _fmt_q12(mean_eta),
        "mean_raw_offdiag_r2_q": _fmt_q12(mean_raw_r2),
        "mean_residual_offdiag_rho2_q": _fmt_q12(mean_offdiag_rho2),
        "max_residual_offdiag_rho2_q": _fmt_q12(max_offdiag_rho2),
        "residual_participation_ratio_q": _fmt_q12(participation_ratio),
        "dark_mode_compression_factor_q": _fmt_q12(dark_mode_compression),
    }


def _compute_time_reversal_asymmetry_q(
    z_mat: Sequence[Sequence[Fraction]],
    sigma: Sequence[Sequence[Fraction]],
    tau: int,
) -> Dict[str, Any]:
    """Exact affine-invariant lagged time-reversal asymmetry A^2_ij(tau), dir_ij(tau), Gamma_ij(tau), Phi_i(tau)."""
    t_len = len(z_mat)
    d = len(z_mat[0])
    n_eff = t_len - tau
    _require(n_eff >= 4, "LAG_TOO_LARGE", f"lag {tau} too large for T={t_len}")

    c_tau = [[Fraction(0) for _ in range(d)] for _ in range(d)]
    for i in range(d):
        zi_early = [z_mat[t][i] for t in range(n_eff)]
        for j in range(d):
            zj_late = [z_mat[t + tau][j] for t in range(n_eff)]
            c_tau[i][j] = sum(a * b for a, b in zip(zi_early, zj_late)) / n_eff

    a2_mat = [[Fraction(0) for _ in range(d)] for _ in range(d)]
    dir_mat = [[0 for _ in range(d)] for _ in range(d)]
    gamma_mat = [[Fraction(0) for _ in range(d)] for _ in range(d)]
    pair_records: List[Tuple[Fraction, int, int, int, Fraction]] = []

    for i in range(d):
        for j in range(i + 1, d):
            diff = c_tau[i][j] - c_tau[j][i]
            summ = c_tau[i][j] + c_tau[j][i]
            denom = sigma[i][i] * sigma[j][j]
            a2 = (diff * diff) / denom
            sgn = _sign_q(diff)
            g_den = (summ * summ) + (diff * diff)
            gamma = (diff * diff) / g_den if g_den > 0 else Fraction(0)
            a2_mat[i][j] = a2
            a2_mat[j][i] = a2
            dir_mat[i][j] = sgn
            dir_mat[j][i] = -sgn
            gamma_mat[i][j] = gamma
            gamma_mat[j][i] = gamma
            pair_records.append((a2, sgn, i, j, gamma))

    phi_scores: List[Fraction] = []
    for i in range(d):
        acc_ticks = sum(dir_mat[i][j] * _q12_ticks(a2_mat[i][j]) for j in range(d) if j != i)
        phi_scores.append(Fraction(acc_ticks, (d - 1) * _Q12_SCALE))

    mean_a2 = Fraction(sum(_q12_ticks(rec[0]) for rec in pair_records), len(pair_records) * _Q12_SCALE)
    max_a2 = Fraction(max(_q12_ticks(rec[0]) for rec in pair_records), _Q12_SCALE)
    mean_gamma = Fraction(sum(_q12_ticks(rec[4]) for rec in pair_records), len(pair_records) * _Q12_SCALE)
    top_pairs = sorted(pair_records, key=lambda r: (r[0], r[4]), reverse=True)[:10]

    return {
        "tau": tau,
        "mean_asymmetry_a2_exact": mean_a2,
        "max_asymmetry_a2_exact": max_a2,
        "mean_asymmetry_a2_q": _fmt_q12(mean_a2),
        "max_asymmetry_a2_q": _fmt_q12(max_a2),
        "mean_dissipation_gamma_q": _fmt_q12(mean_gamma),
        "phi_source_sink_q": [_fmt_q12(v) for v in phi_scores],
        "a2_mat": a2_mat,
        "dir_mat": dir_mat,
        "gamma_mat": gamma_mat,
        "top_pairs": [
            {
                "dyn_i": r[2],
                "dyn_j": r[3],
                "a2_q": _fmt_q12(r[0]),
                "dir": r[1],
                "gamma_q": _fmt_q12(r[4]),
            }
            for r in top_pairs
        ],
    }


def _fast_int_stats_for_null(
    cols_int: Sequence[Sequence[int]],
    tau: int,
) -> Tuple[Fraction, Fraction, Fraction]:
    """Pure-integer fast computation of (mean_R2, mean_A2(tau), max_A2(tau)) on 10^12 grid (zero floats)."""
    d = len(cols_int)
    t_len = len(cols_int[0])
    z_cols: List[List[int]] = []
    vars_int: List[int] = []
    for col in cols_int:
        s = sum(col)
        zc = [t_len * v - s for v in col]
        v2 = sum(u * u for u in zc)
        z_cols.append(zc)
        vars_int.append(v2)

    n_eff = t_len - tau
    num_pairs = (d * (d - 1)) // 2
    r2_ticks_sum = 0
    a2_ticks_sum = 0
    a2_ticks_max = 0

    scale_num = t_len * t_len * _Q12_SCALE
    scale_den = n_eff * n_eff

    for i in range(d):
        zi = z_cols[i]
        vi = vars_int[i]
        zi_e = zi[:n_eff]
        zi_l = zi[tau:]
        for j in range(i + 1, d):
            zj = z_cols[j]
            vj = vars_int[j]
            denom_v = vi * vj
            dot0 = sum(a * b for a, b in zip(zi, zj))
            r2_ticks_sum += (dot0 * dot0 * _Q12_SCALE) // denom_v

            dot_ij = sum(a * b for a, b in zip(zi_e, zj[tau:]))
            dot_ji = sum(a * b for a, b in zip(zj[:n_eff], zi_l))
            diff = dot_ij - dot_ji
            a2_t = (scale_num * diff * diff) // (scale_den * denom_v)
            a2_ticks_sum += a2_t
            if a2_t > a2_ticks_max:
                a2_ticks_max = a2_t

    return (
        Fraction(r2_ticks_sum, num_pairs * _Q12_SCALE),
        Fraction(a2_ticks_sum, num_pairs * _Q12_SCALE),
        Fraction(a2_ticks_max, _Q12_SCALE),
    )


def _run_circular_shift_null_q(
    cols_int: Sequence[Sequence[int]],
    obs_mean_r2: Fraction,
    obs_mean_a2: Fraction,
    obs_max_a2: Fraction,
    tau: int,
    n_surrogates: int,
    seed: int,
) -> Dict[str, Any]:
    """Exact pure-Q circular-shift null preserving per-channel autocorrelation and marginals."""
    rng = random.Random(seed)
    t_len = len(cols_int[0])
    min_shift = max(5, t_len // 10)
    max_shift = t_len - min_shift

    ge_r2 = 0
    ge_a2_mean = 0
    ge_a2_max = 0
    null_r2_vals: List[Fraction] = []
    null_a2_vals: List[Fraction] = []
    null_a2max_vals: List[Fraction] = []

    for _ in range(n_surrogates):
        shifted = []
        for col in cols_int:
            sh = rng.randint(min_shift, max_shift)
            shifted.append(col[sh:] + col[:sh])
        mr2, ma2, mxa2 = _fast_int_stats_for_null(shifted, tau)
        null_r2_vals.append(mr2)
        null_a2_vals.append(ma2)
        null_a2max_vals.append(mxa2)
        if mr2 >= obs_mean_r2:
            ge_r2 += 1
        if ma2 >= obs_mean_a2:
            ge_a2_mean += 1
        if mxa2 >= obs_max_a2:
            ge_a2_max += 1

    null_r2_mean = sum(null_r2_vals) / n_surrogates
    null_a2_mean = sum(null_a2_vals) / n_surrogates
    null_a2max_mean = sum(null_a2max_vals) / n_surrogates
    null_r2_max = max(null_r2_vals)
    null_a2_max_s = max(null_a2_vals)

    return {
        "oracle_class": "exact",
        "method": "pure_q_circular_shift",
        "seed": seed,
        "n_surrogates": n_surrogates,
        "tau": tau,
        "obs_mean_r2_q": _fmt_q12(obs_mean_r2),
        "null_mean_r2_q": _fmt_q12(null_r2_mean),
        "null_max_r2_q": _fmt_q12(null_r2_max),
        "p_mean_r2_q": _fmt_q(Fraction(ge_r2 + 1, n_surrogates + 1)),
        "obs_mean_a2_q": _fmt_q12(obs_mean_a2),
        "null_mean_a2_q": _fmt_q12(null_a2_mean),
        "null_max_mean_a2_q": _fmt_q12(null_a2_max_s),
        "p_mean_a2_q": _fmt_q(Fraction(ge_a2_mean + 1, n_surrogates + 1)),
        "obs_max_a2_q": _fmt_q12(obs_max_a2),
        "null_mean_of_max_a2_q": _fmt_q12(null_a2max_mean),
        "p_max_a2_q": _fmt_q(Fraction(ge_a2_max + 1, n_surrogates + 1)),
    }


def _run_iaaft_null_sampled(
    cols_int: Sequence[Sequence[int]],
    obs_mean_r2_q: Fraction,
    obs_mean_a2_q: Fraction,
    obs_max_a2_q: Fraction,
    tau: int,
    n_surrogates: int,
    seed: int,
) -> Dict[str, Any]:
    """Matched IAAFT surrogate null (amplitude-spectrum + marginal preserving; sampled oracle class)."""
    try:
        import numpy as np  # type: ignore[import-not-found]
    except ImportError:
        return {
            "oracle_class": "sampled",
            "method": "iaaft_unavailable_in_stdlib_mode",
            "available": False,
        }

    rng = np.random.default_rng(seed)
    t_len = len(cols_int[0])
    d = len(cols_int)
    x_arr = np.asarray(cols_int, dtype=np.float64)  # shape (D, T)
    sorted_vals = np.sort(x_arr, axis=1)
    amp_spec = np.abs(np.fft.rfft(x_arr, axis=1))

    # Quantize IAAFT statistics to exact rationals with denominator 10^6 so cert JSON stays zero-float!
    q_scale = 1_000_000
    obs_r2_s = int(obs_mean_r2_q * q_scale)
    obs_a2_s = int(obs_mean_a2_q * q_scale)
    obs_mxa2_s = int(obs_max_a2_q * q_scale)

    ge_r2 = 0
    ge_a2 = 0
    ge_mxa2 = 0
    r2_acc = 0
    a2_acc = 0
    mxa2_acc = 0
    r2_sq_acc = 0
    a2_sq_acc = 0

    for _ in range(n_surrogates):
        # Independent IAAFT per channel
        surr = np.empty_like(x_arr)
        for j in range(d):
            s_cur = rng.permutation(x_arr[j])
            target_amp = amp_spec[j]
            target_sorted = sorted_vals[j]
            for _it in range(IAAFT_ITERS):
                fft_cur = np.fft.rfft(s_cur)
                phases = np.angle(fft_cur)
                spec_matched = np.fft.irfft(target_amp * np.exp(1j * phases), n=t_len)
                ranks = np.argsort(np.argsort(spec_matched))
                s_cur = target_sorted[ranks]
            surr[j] = s_cur

        # Compute exact scale-free stats on surrogate
        z = surr - surr.mean(axis=1, keepdims=True)
        var = np.sum(z * z, axis=1)
        if np.any(var <= 0):
            continue
        cov0 = (z @ z.T) / t_len
        var_s = var / t_len
        denom_mat = np.outer(var_s, var_s)
        r2_mat = (cov0 * cov0) / denom_mat
        iu = np.triu_indices(d, k=1)
        mr2_val = int(round(float(np.mean(r2_mat[iu])) * q_scale))

        n_eff = t_len - tau
        c_tau = (z[:, :n_eff] @ z[:, tau:].T) / n_eff
        diff = c_tau - c_tau.T
        a2_mat = (diff * diff) / denom_mat
        ma2_val = int(round(float(np.mean(a2_mat[iu])) * q_scale))
        mxa2_val = int(round(float(np.max(a2_mat[iu])) * q_scale))

        r2_acc += mr2_val
        a2_acc += ma2_val
        mxa2_acc += mxa2_val
        r2_sq_acc += mr2_val * mr2_val
        a2_sq_acc += ma2_val * ma2_val
        if mr2_val >= obs_r2_s:
            ge_r2 += 1
        if ma2_val >= obs_a2_s:
            ge_a2 += 1
        if mxa2_val >= obs_mxa2_s:
            ge_mxa2 += 1

    mean_r2_q = Fraction(r2_acc, n_surrogates * q_scale)
    mean_a2_q = Fraction(a2_acc, n_surrogates * q_scale)
    mean_mxa2_q = Fraction(mxa2_acc, n_surrogates * q_scale)
    var_r2_q = Fraction(r2_sq_acc, n_surrogates * q_scale * q_scale) - (mean_r2_q * mean_r2_q)
    var_a2_q = Fraction(a2_sq_acc, n_surrogates * q_scale * q_scale) - (mean_a2_q * mean_a2_q)
    z2_r2_q = ((obs_mean_r2_q - mean_r2_q) ** 2) / var_r2_q if var_r2_q > 0 else Fraction(0)
    z2_a2_q = ((obs_mean_a2_q - mean_a2_q) ** 2) / var_a2_q if var_a2_q > 0 else Fraction(0)

    return {
        "oracle_class": "sampled",
        "method": "numpy_iaaft_per_channel",
        "available": True,
        "seed": seed,
        "n_surrogates": n_surrogates,
        "iaaft_iters": IAAFT_ITERS,
        "tau": tau,
        "null_mean_r2_q": _fmt_q12(mean_r2_q),
        "p_mean_r2_q": _fmt_q(Fraction(ge_r2 + 1, n_surrogates + 1)),
        "z_squared_mean_r2_q": _fmt_q12(z2_r2_q),
        "null_mean_a2_q": _fmt_q12(mean_a2_q),
        "p_mean_a2_q": _fmt_q(Fraction(ge_a2 + 1, n_surrogates + 1)),
        "z_squared_mean_a2_q": _fmt_q12(z2_a2_q),
        "null_mean_of_max_a2_q": _fmt_q12(mean_mxa2_q),
        "p_max_a2_q": _fmt_q(Fraction(ge_mxa2 + 1, n_surrogates + 1)),
    }


def _cluster_permutation_null_q(
    blind_labels: Sequence[int],
    gt_labels: Sequence[str],
    obs_ari: Fraction,
    n_perms: int,
    seed: int,
) -> Dict[str, Any]:
    rng = random.Random(seed)
    gt_list = list(gt_labels)
    ge = 0
    ari_ticks_sum = 0
    max_ari = Fraction(-1)
    for _ in range(n_perms):
        perm = list(gt_list)
        rng.shuffle(perm)
        ari = _exact_ari_q(blind_labels, perm)
        ari_ticks_sum += _q12_ticks(ari)
        if ari > max_ari:
            max_ari = ari
        if ari >= obs_ari:
            ge += 1
    mean_ari = Fraction(ari_ticks_sum, n_perms * _Q12_SCALE)
    return {
        "oracle_class": "exact",
        "method": "exact_label_permutation_null",
        "seed": seed,
        "n_perms": n_perms,
        "obs_ari_q": _fmt_q(obs_ari),
        "null_mean_ari_q": _fmt_q12(mean_ari),
        "null_max_ari_q": _fmt_q12(max_ari),
        "p_ari_q": _fmt_q(Fraction(ge + 1, n_perms + 1)),
    }


def analyze_snapshot(raw_snapshot: Dict[str, Any], raw_bytes_sha256: str) -> Dict[str, Any]:
    """Run full Stage-A -> Stage-B beyond-language blind tomography on raw snapshot."""
    x_rows_int: List[List[int]] = raw_snapshot["X_anonymous"]
    gt_channels: List[Dict[str, Any]] = raw_snapshot["held_out_ground_truth_channels"]
    t_len = len(x_rows_int)
    d_total = len(x_rows_int[0])
    _require(d_total == len(gt_channels), "CHANNEL_COUNT_MISMATCH", "X_anonymous width != ground truth count")

    # Stage A.1: Strictly label-free zero-variance channel dropout
    active_orig_indices: List[int] = []
    zero_var_orig_indices: List[int] = []
    for j in range(d_total):
        col = [x_rows_int[t][j] for t in range(t_len)]
        if min(col) == max(col):
            zero_var_orig_indices.append(j)
        else:
            active_orig_indices.append(j)

    d_dyn = len(active_orig_indices)
    _require(d_dyn >= 6, "TOO_FEW_DYNAMIC_CHANNELS", f"only {d_dyn} dynamic channels found")

    x_dyn_int = [[x_rows_int[t][j] for j in active_orig_indices] for t in range(t_len)]
    x_dyn_q = [[Fraction(v) for v in row] for row in x_dyn_int]
    cols_dyn_int = [[x_dyn_int[t][j] for t in range(t_len)] for j in range(d_dyn)]

    # Stage B.1: Exact scale-free R^2 and regularized partial-correlation P
    z_mat, sigma = _exact_center_gram(x_dyn_q)
    r2_mat, r_sign, p2_mat, p_sign, reg_inertia = _compute_scale_free_r2_and_partial(sigma, RIDGE_LAMBDA)

    # Blind pure-Q greedy modularity clustering on R^2 and on P^2
    blind_comm_r2, mod_q_r2 = _blind_greedy_modularity_q(r2_mat)
    blind_comm_p2, mod_q_p2 = _blind_greedy_modularity_q(p2_mat)

    # Stage A.2: Exact Affine + Permutation Gauge-Invariance Stress Test
    rng_g = random.Random(GAUGE_SEED)
    perm = list(range(d_dyn))
    rng_g.shuffle(perm)
    scales_q = [Fraction(rng_g.randint(1, 50000), rng_g.randint(1, 500)) for _ in range(d_dyn)]
    shifts_q = [Fraction(rng_g.randint(-100000, 100000), rng_g.randint(1, 100)) for _ in range(d_dyn)]
    # X'[t][new_j] = scales_q[orig_j] * X[t][orig_j] + shifts_q[orig_j], where orig_j = perm[new_j]
    x_gauged_q = [
        [scales_q[perm[nj]] * x_dyn_q[t][perm[nj]] + shifts_q[perm[nj]] for nj in range(d_dyn)]
        for t in range(t_len)
    ]
    z_g, sigma_g = _exact_center_gram(x_gauged_q)
    r2_g, _rs_g, p2_g, _ps_g, _in_g = _compute_scale_free_r2_and_partial(sigma_g, RIDGE_LAMBDA)
    blind_comm_r2_g, mod_q_r2_g = _blind_greedy_modularity_q(r2_g)

    max_diff_r2 = Fraction(0)
    max_diff_p2 = Fraction(0)
    for ni in range(d_dyn):
        oi = perm[ni]
        for nj in range(d_dyn):
            oj = perm[nj]
            dr = abs(r2_g[ni][nj] - r2_mat[oi][oj])
            dp = abs(p2_g[ni][nj] - p2_mat[oi][oj])
            if dr > max_diff_r2:
                max_diff_r2 = dr
            if dp > max_diff_p2:
                max_diff_p2 = dp
    unpermuted_comm_g = [0] * d_dyn
    for ni in range(d_dyn):
        unpermuted_comm_g[perm[ni]] = blind_comm_r2_g[ni]
    gauge_ari_exact = _exact_ari_q(blind_comm_r2, unpermuted_comm_g)

    # Stage B.2: Empirical Off-Brane Dark-Mode Schur Complement (Portal 56 / S37)
    # (a) Blind partition: largest blind-discovered R^2 cluster A conditioned on all other blind channels B
    comm_counts: Dict[int, int] = {}
    for cid in blind_comm_r2:
        comm_counts[cid] = comm_counts.get(cid, 0) + 1
    largest_cid = sorted(comm_counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    blind_a = [i for i in range(d_dyn) if blind_comm_r2[i] == largest_cid]
    blind_b = [i for i in range(d_dyn) if blind_comm_r2[i] != largest_cid]
    if len(blind_b) == 0:
        # Fallback purely blind split by median diagonal degree if 1 cluster
        blind_a = list(range(d_dyn // 2))
        blind_b = list(range(d_dyn // 2, d_dyn))
    schur_blind = _empirical_schur_dark_mode_q(sigma, blind_a, blind_b, RIDGE_LAMBDA)

    # Check exact gauge invariance on blind Schur partition too
    inv_perm = [0] * d_dyn
    for ni, oi in enumerate(perm):
        inv_perm[oi] = ni
    blind_a_g = [inv_perm[oi] for oi in blind_a]
    blind_b_g = [inv_perm[oi] for oi in blind_b]
    schur_blind_g = _empirical_schur_dark_mode_q(sigma_g, blind_a_g, blind_b_g, RIDGE_LAMBDA)
    schur_gauge_exact = (
        schur_blind["mean_unexplained_variance_eta_q"] == schur_blind_g["mean_unexplained_variance_eta_q"]
        and schur_blind["mean_residual_offdiag_rho2_q"] == schur_blind_g["mean_residual_offdiag_rho2_q"]
        and schur_blind["residual_participation_ratio_q"] == schur_blind_g["residual_participation_ratio_q"]
    )

    # (b) Held-out physical partition: A = die/chassis/nvme thermals, B = clocks/fans/GPU/power
    dyn_gt_modules = [gt_channels[orig_j]["module"] for orig_j in active_orig_indices]
    phys_a = [i for i, m in enumerate(dyn_gt_modules) if m in ("cpu_die_thermal", "chassis_acpi_thermal", "nvme_thermal")]
    phys_b = [i for i, m in enumerate(dyn_gt_modules) if m not in ("cpu_die_thermal", "chassis_acpi_thermal", "nvme_thermal")]
    schur_physical: Optional[Dict[str, Any]] = None
    if len(phys_a) >= 2 and len(phys_b) >= 1:
        schur_physical = _empirical_schur_dark_mode_q(sigma, phys_a, phys_b, RIDGE_LAMBDA)

    # Stage B.3: Time-Reversal Asymmetry / Physical Silq qfree-vs-mfree Dissipation Arrow
    asym_by_lag: Dict[str, Dict[str, Any]] = {}
    asym_gauge_exact = True
    cadence_hz = int(raw_snapshot.get("cadence_hz", 2))
    if cadence_hz == 4 and t_len >= 40:
        lags_to_probe: Tuple[int, ...] = (1, 2, 4, 8, 12)
        primary_tau = 4  # 1.0 s physical lag at 4 Hz
    else:
        lags_to_probe = LAGS
        primary_tau = 2  # 1.0 s physical lag at 2 Hz
    primary_asym_raw: Optional[Dict[str, Any]] = None

    for tau in lags_to_probe:
        res_t = _compute_time_reversal_asymmetry_q(z_mat, sigma, tau)
        if tau == primary_tau:
            primary_asym_raw = res_t
            res_tg = _compute_time_reversal_asymmetry_q(z_g, sigma_g, tau)
            if (
                res_t["mean_asymmetry_a2_q"] != res_tg["mean_asymmetry_a2_q"]
                or res_t["max_asymmetry_a2_q"] != res_tg["max_asymmetry_a2_q"]
                or res_t["mean_dissipation_gamma_q"] != res_tg["mean_dissipation_gamma_q"]
            ):
                asym_gauge_exact = False
        asym_by_lag[str(tau)] = {
            "tau": tau,
            "mean_asymmetry_a2_q": res_t["mean_asymmetry_a2_q"],
            "max_asymmetry_a2_q": res_t["max_asymmetry_a2_q"],
            "mean_dissipation_gamma_q": res_t["mean_dissipation_gamma_q"],
            "phi_source_sink_q": res_t["phi_source_sink_q"],
            "top_pairs": res_t["top_pairs"],
        }

    _require(primary_asym_raw is not None, "MISSING_PRIMARY_TAU", "primary lag missing")

    # Separate within-die core-to-core (conductive/reversible qfree-like) vs cross-domain (dissipative mfree-like)
    die_indices = [i for i, m in enumerate(dyn_gt_modules) if m == "cpu_die_thermal"]
    non_die_drivers = [
        i for i, m in enumerate(dyn_gt_modules)
        if m in (
            "cpu_rapl_energy_uj",
            "mechanical_cooling",
            "cpu_clock_electrical",
            "gpu_electromechanical",
            "chassis_acpi_thermal",
            "acoustic_airborne",
        )
    ]
    a2_p = primary_asym_raw["a2_mat"]
    gamma_p = primary_asym_raw["gamma_mat"]
    within_die_a2_t = [_q12_ticks(a2_p[i][j]) for idx_i, i in enumerate(die_indices) for j in die_indices[idx_i + 1 :]]
    within_die_gm_t = [_q12_ticks(gamma_p[i][j]) for idx_i, i in enumerate(die_indices) for j in die_indices[idx_i + 1 :]]
    cross_drv_a2_t = [_q12_ticks(a2_p[i][j]) for i in die_indices for j in non_die_drivers]
    cross_drv_gm_t = [_q12_ticks(gamma_p[i][j]) for i in die_indices for j in non_die_drivers]

    mean_wd_a2 = Fraction(sum(within_die_a2_t), len(within_die_a2_t) * _Q12_SCALE) if within_die_a2_t else Fraction(0)
    mean_wd_gm = Fraction(sum(within_die_gm_t), len(within_die_gm_t) * _Q12_SCALE) if within_die_gm_t else Fraction(0)
    mean_cd_a2 = Fraction(sum(cross_drv_a2_t), len(cross_drv_a2_t) * _Q12_SCALE) if cross_drv_a2_t else Fraction(0)
    mean_cd_gm = Fraction(sum(cross_drv_gm_t), len(cross_drv_gm_t) * _Q12_SCALE) if cross_drv_gm_t else Fraction(0)

    qfree_vs_mfree = {
        "tau": primary_tau,
        "within_die_pair_count": len(within_die_a2_t),
        "cross_domain_pair_count": len(cross_drv_a2_t),
        "within_die_mean_a2_q": _fmt_q12(mean_wd_a2),
        "within_die_mean_gamma_q": _fmt_q12(mean_wd_gm),
        "cross_domain_mean_a2_q": _fmt_q12(mean_cd_a2),
        "cross_domain_mean_gamma_q": _fmt_q12(mean_cd_gm),
        "cross_to_within_a2_ratio_q": _fmt_q12(mean_cd_a2 / mean_wd_a2) if (mean_wd_a2 > 0 and cross_drv_a2_t) else "0",
    }

    # Stage B.4: Held-Out Evaluation (STRICTLY post-extraction!) + Nulls + Split-Half
    ari_r2_gt = _exact_ari_q(blind_comm_r2, dyn_gt_modules)
    ari_p2_gt = _exact_ari_q(blind_comm_p2, dyn_gt_modules)
    cluster_null_r2 = _cluster_permutation_null_q(blind_comm_r2, dyn_gt_modules, ari_r2_gt, NUM_SURROGATES, CLUSTER_NULL_SEED)

    # Observed global mean R^2 across unique pairs (10^12 exact integer tick sum)
    num_pairs = (d_dyn * (d_dyn - 1)) // 2
    obs_mean_r2 = Fraction(
        sum(_q12_ticks(r2_mat[i][j]) for i in range(d_dyn) for j in range(i + 1, d_dyn)),
        num_pairs * _Q12_SCALE,
    )
    obs_mean_a2 = primary_asym_raw["mean_asymmetry_a2_exact"]
    obs_max_a2 = primary_asym_raw["max_asymmetry_a2_exact"]

    circ_null = _run_circular_shift_null_q(
        cols_dyn_int, obs_mean_r2, obs_mean_a2, obs_max_a2, primary_tau, NUM_SURROGATES, NULL_SEED
    )
    iaaft_null = _run_iaaft_null_sampled(
        cols_dyn_int, obs_mean_r2, obs_mean_a2, obs_max_a2, primary_tau, NUM_SURROGATES, IAAFT_SEED
    )

    # Out-of-Sample Split-Half Replication (First half vs. Second half)
    mid = t_len // 2
    h1_q = x_dyn_q[:mid]
    h2_q = x_dyn_q[mid : 2 * mid]
    # Keep channels dynamic in BOTH halves for clean split-half test
    both_dyn = [
        j
        for j in range(d_dyn)
        if (min(h1_q[t][j] for t in range(mid)) != max(h1_q[t][j] for t in range(mid)))
        and (min(h2_q[t][j] for t in range(mid)) != max(h2_q[t][j] for t in range(mid)))
    ]
    split_half: Dict[str, Any] = {"both_halves_dynamic_count": len(both_dyn), "half_len": mid}
    if len(both_dyn) >= 4:
        h1_sub = [[row[j] for j in both_dyn] for row in h1_q]
        h2_sub = [[row[j] for j in both_dyn] for row in h2_q]
        z1, s1 = _exact_center_gram(h1_sub)
        z2, s2 = _exact_center_gram(h2_sub)
        r2_h1, _, _, _, _ = _compute_scale_free_r2_and_partial(s1, RIDGE_LAMBDA)
        r2_h2, _, _, _, _ = _compute_scale_free_r2_and_partial(s2, RIDGE_LAMBDA)
        c_h1, _ = _blind_greedy_modularity_q(r2_h1)
        c_h2, _ = _blind_greedy_modularity_q(r2_h2)
        split_ari = _exact_ari_q(c_h1, c_h2)

        as1 = _compute_time_reversal_asymmetry_q(z1, s1, primary_tau)
        as2 = _compute_time_reversal_asymmetry_q(z2, s2, primary_tau)
        top_k = as1["top_pairs"][:10]
        agree = 0
        for rec in top_k:
            ii, jj, sgn1 = rec["dyn_i"], rec["dyn_j"], rec["dir"]
            if sgn1 != 0 and as2["dir_mat"][ii][jj] == sgn1:
                agree += 1
        split_half["split_half_cluster_ari_q"] = _fmt_q(split_ari)
        split_half["top10_arrow_sign_concordance_q"] = _fmt_q(Fraction(agree, len(top_k))) if top_k else "0"
        split_half["top10_arrow_sign_matches"] = agree
        split_half["top10_arrow_count"] = len(top_k)
        split_half["half1_mean_a2_q"] = as1["mean_asymmetry_a2_q"]
        split_half["half2_mean_a2_q"] = as2["mean_asymmetry_a2_q"]

    # Exact SI-2019 pure-Q Landauer Thermodynamic Erasure Bridge (Track S38 qfree vs mfree)
    # k_B = 1380649 * 10^-29 J/K (exact by 2019 SI); ln(2) in [693147180559/10^12, 693147180560/10^12]
    landauer_bridge: Optional[Dict[str, Any]] = None
    rapl_pkg_orig = [
        j for j, ch in enumerate(gt_channels)
        if ch.get("module") == "cpu_rapl_energy_uj" and ch.get("device") == "intel-rapl:0"
    ]
    pkg_temp_orig = [
        j for j, ch in enumerate(gt_channels)
        if ch.get("module") == "cpu_die_thermal" and ch.get("label") == "Package id 0"
    ]
    if rapl_pkg_orig and pkg_temp_orig:
        r_idx = rapl_pkg_orig[0]
        t_idx = pkg_temp_orig[0]
        total_e_uj = sum(x_rows_int[t][r_idx] for t in range(t_len))
        mean_t_mc = Fraction(sum(x_rows_int[t][t_idx] for t in range(t_len)), t_len)
        mean_t_kelvin = (mean_t_mc / Fraction(1000)) + Fraction(27315, 100)
        k_b_exact = Fraction(1380649, 10**29)
        ln2_lo = Fraction(693147180559, 10**12)
        ln2_hi = Fraction(693147180560, 10**12)
        total_e_joules = Fraction(total_e_uj, 10**6)
        e_bit_lo = k_b_exact * mean_t_kelvin * ln2_lo
        e_bit_hi = k_b_exact * mean_t_kelvin * ln2_hi
        # Total Landauer-equivalent erased bits N = E / (k_B T ln 2) -> exact integer [floor, ceil] bracket
        q_lo = total_e_joules / e_bit_hi
        q_hi = total_e_joules / e_bit_lo
        bits_lo = q_lo.numerator // q_lo.denominator
        bits_hi = (q_hi.numerator + q_hi.denominator - 1) // q_hi.denominator
        elapsed_ms_raw = max(1, int(raw_snapshot.get("elapsed_ms", 1)))
        mean_power_w = total_e_joules / Fraction(elapsed_ms_raw, 1000)
        landauer_bridge = {
            "oracle_class": "exact",
            "rapl_domain": "intel-rapl:0 (package-0)",
            "total_energy_uj": total_e_uj,
            "mean_package_power_w_q": _fmt_q12(mean_power_w),
            "mean_package_temp_kelvin_q": _fmt_q12(mean_t_kelvin),
            "landauer_bits_lower_bound": int(bits_lo),
            "landauer_bits_upper_bound": int(bits_hi),
            "s38_qfree_reversible_bits": 0,
            "s38_mfree_single_and_bracket_bits_q": ["19/16", "6/5"],
        }

    # Map dynamic indices to held-out labels strictly in an isolated post-hoc section
    dynamic_channel_legend = [
        {
            "dyn_idx": idx,
            "orig_channel_id": active_orig_indices[idx],
            "device": gt_channels[active_orig_indices[idx]]["device"],
            "label": gt_channels[active_orig_indices[idx]]["label"],
            "module": gt_channels[active_orig_indices[idx]]["module"],
            "blind_r2_cluster": blind_comm_r2[idx],
            "blind_p2_cluster": blind_comm_p2[idx],
            "phi_tau2_q": asym_by_lag[str(primary_tau)]["phi_source_sink_q"][idx],
        }
        for idx in range(d_dyn)
    ]

    payload = {
        "schema_version": SCHEMA_CERT,
        "raw_snapshot_sha256": raw_bytes_sha256,
        "x_anonymous_sha256": raw_snapshot["x_anonymous_sha256"],
        "sample_count": t_len,
        "total_channels_captured": d_total,
        "dynamic_channel_count": d_dyn,
        "zero_variance_channel_count": len(zero_var_orig_indices),
        "active_orig_indices": active_orig_indices,
        "zero_variance_orig_indices": zero_var_orig_indices,
        "ridge_lambda_q": _fmt_q(RIDGE_LAMBDA),
        "stage_a_gauge_invariance": {
            "oracle_class": "exact",
            "gauge_seed": GAUGE_SEED,
            "max_r2_diff_q": _fmt_q(max_diff_r2),
            "max_partial_p2_diff_q": _fmt_q(max_diff_p2),
            "blind_cluster_gauge_ari_q": _fmt_q(gauge_ari_exact),
            "schur_gauge_exact_match": schur_gauge_exact,
            "asymmetry_gauge_exact_match": asym_gauge_exact,
            "all_gauge_invariants_exact": (
                max_diff_r2 == 0
                and max_diff_p2 == 0
                and gauge_ari_exact == 1
                and schur_gauge_exact
                and asym_gauge_exact
            ),
        },
        "stage_b_coupling_and_blind_clustering": {
            "oracle_class": "exact",
            "sigma_reg_inertia": list(reg_inertia),
            "sigma_reg_is_spd": reg_inertia == (d_dyn, 0, 0),
            "mean_pair_r2_q": _fmt_q12(obs_mean_r2),
            "blind_r2_cluster_count": len(set(blind_comm_r2)),
            "blind_r2_modularity_q": _fmt_q12(mod_q_r2),
            "blind_r2_labels": blind_comm_r2,
            "blind_p2_cluster_count": len(set(blind_comm_p2)),
            "blind_p2_modularity_q": _fmt_q12(mod_q_p2),
            "blind_p2_labels": blind_comm_p2,
            "held_out_ari_r2_q": _fmt_q(ari_r2_gt),
            "held_out_ari_p2_q": _fmt_q(ari_p2_gt),
            "cluster_permutation_null": cluster_null_r2,
        },
        "stage_b_schur_dark_modes": {
            "oracle_class": "exact",
            "blind_largest_cluster_a_indices": blind_a,
            "blind_complement_b_indices": blind_b,
            "blind_partition_schur": schur_blind,
            "physical_thermal_a_indices": phys_a,
            "physical_driver_b_indices": phys_b,
            "physical_partition_schur": schur_physical,
        },
        "stage_b_time_reversal_dissipation": {
            "oracle_class": "exact",
            "primary_tau": primary_tau,
            "by_lag": asym_by_lag,
            "qfree_vs_mfree_separation": qfree_vs_mfree,
            "landauer_thermodynamic_bridge": landauer_bridge,
        },
        "adversarial_nulls_and_replication": {
            "circular_shift_null_exact": circ_null,
            "iaaft_null_sampled": iaaft_null,
            "split_half_replication_exact": split_half,
        },
        "held_out_posthoc_channel_legend": dynamic_channel_legend,
    }
    payload_sha = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    return {
        "schema_version": SCHEMA_CERT,
        "payload_sha256": payload_sha,
        "payload": payload,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Track S53 Beyond-Language Physical Sensor Tomography Probe")
    parser.add_argument("--capture-seconds", type=int, default=0, help="Passive capture duration in seconds (10..600)")
    parser.add_argument("--hz", type=int, default=2, help="Passive polling frequency in Hz (default: 2)")
    parser.add_argument("--out-raw", type=Path, default=None, help="Output path for raw_sensor_snapshot.json")
    parser.add_argument("--analyze", type=Path, default=None, help="Analyze existing raw_sensor_snapshot.json")
    parser.add_argument("--out-cert", type=Path, default=None, help="Output path for sensor_tomography_certificate.json")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        raw_path = args.analyze
        if args.capture_seconds > 0:
            snap = capture_live_snapshot(args.capture_seconds, args.hz)
            raw_bytes = _canonical_json_bytes(snap)
            out_raw = args.out_raw or (Path(__file__).resolve().parent / "raw_sensor_snapshot.json")
            _atomic_write_0600(out_raw, raw_bytes)
            raw_path = out_raw
            print(
                json.dumps(
                    {
                        "captured": True,
                        "out_raw": str(out_raw),
                        "samples": snap["sample_count"],
                        "channels": snap["channel_count"],
                        "elapsed_ms": snap["elapsed_ms"],
                        "raw_sha256": hashlib.sha256(raw_bytes).hexdigest(),
                    },
                    sort_keys=True,
                )
            )

        if raw_path is not None:
            raw_bytes = raw_path.read_bytes()
            raw_sha = hashlib.sha256(raw_bytes).hexdigest()
            snap_loaded = json.loads(raw_bytes.decode("utf-8"))
            cert = analyze_snapshot(snap_loaded, raw_sha)
            cert_bytes = _canonical_json_bytes(cert)
            if args.out_cert is not None:
                _atomic_write_0600(args.out_cert, cert_bytes)
            print(
                json.dumps(
                    {
                        "analyzed": True,
                        "payload_sha256": cert["payload_sha256"],
                        "cert_sha256": hashlib.sha256(cert_bytes).hexdigest(),
                        "dynamic_channels": cert["payload"]["dynamic_channel_count"],
                        "zero_var_channels": cert["payload"]["zero_variance_channel_count"],
                        "gauge_exact": cert["payload"]["stage_a_gauge_invariance"]["all_gauge_invariants_exact"],
                        "blind_r2_clusters": cert["payload"]["stage_b_coupling_and_blind_clustering"]["blind_r2_cluster_count"],
                        "held_out_ari_r2": cert["payload"]["stage_b_coupling_and_blind_clustering"]["held_out_ari_r2_q"],
                        "blind_schur_pr": cert["payload"]["stage_b_schur_dark_modes"]["blind_partition_schur"]["residual_participation_ratio_q"],
                        "circ_p_r2": cert["payload"]["adversarial_nulls_and_replication"]["circular_shift_null_exact"]["p_mean_r2_q"],
                        "circ_p_a2": cert["payload"]["adversarial_nulls_and_replication"]["circular_shift_null_exact"]["p_mean_a2_q"],
                    },
                    sort_keys=True,
                )
            )
    except ProbeError as exc:
        sys.stderr.write(json.dumps({"error": True, "code": exc.code, "detail": exc.detail}, sort_keys=True) + "\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
