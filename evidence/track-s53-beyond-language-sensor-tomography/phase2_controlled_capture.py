#!/usr/bin/env python3
"""Track S53 Phase 2: 60-Second Controlled 4-Regime Beyond-Language Acoustic + RAPL + Thermal + Fan Capture.

Consent & Privacy Contract:
  - Authorized audio-only capture via PipeWire default microphone (`pw-record` 48 kHz mono s16 WAV).
  - ZERO camera (`/dev/video*`) access.
  - Raw WAV stored strictly in `local_raw_av/` (dir mode 0700, file mode 0600; NEVER committed to git
    or corpus archives). Only stripped, non-reconstructible 250 ms coarse spectral-band energy integers,
    SHA-256 provenance, and dimensionless Stage-A -> Stage-B invariants enter snapshots/certificates.

Controlled 4-Regime Stimulus Protocol (60 s @ 4 Hz = 240 synchronized 250 ms frames):
  R0 (0-15 s):  Quiet ambient control (baseline swarm + stationary distant-laptop fan floor).
  R1 (15-30 s): Structured reversible burst (`qfree`-analog: 1-worker L1-resident Feistel bijection).
  R2 (30-45 s): High-dissipation erasure burst (`mfree`-analog: 6-worker L3-exceeding overwrite + dense ALU).
  R3 (45-60 s): Thermal-acoustic hysteresis relaxation tail (all stimulus halted at t=45.0 s sharp).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import wave
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import sensor_tomography_probe as probe

SCHEMA_PHASE2_RAW = "aletheia.s53_phase2_controlled_snapshot.v1"
ROOM_NOISE_COVARIATE = "room_quiet_with_distant_second_laptop_fan_across_room"
AUDIO_CONSENT_WINDOW = "2026-11-24 06:48-07:48 CST (12:48-13:48 UTC)"

# Tight deterministic worker snippets (executed as clean child processes and terminated at regime end)
_R1_REVERSIBLE_SNIPPET = """
import time
# L1-resident 512-entry reversible Feistel bijection (low cache miss, deterministic)
arr = list(range(512))
mask = 0xFFFF
t_end = time.monotonic() + 20.0
k = 0x5A3C
while time.monotonic() < t_end:
    for i in range(512):
        x = arr[i]
        l = (x >> 16) & mask
        r = x & mask
        nl = r
        nr = l ^ (((r * 25173 + 13849 + k) >> 3) & mask)
        arr[i] = (nl << 16) | nr
    k = (k + 1) & mask
"""

_R2_ERASURE_SNIPPET = """
import os, time
import numpy as np
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
rng = np.random.default_rng(int(os.getpid()) & 0xFFFFFFFF)
# 32 MiB buffer (> 24 MiB L3 cache) overwritten irreversibly + dense matmul heat generation
buf = bytearray(32 * 1024 * 1024)
a = rng.standard_normal((384, 384))
b = rng.standard_normal((384, 384))
t_end = time.monotonic() + 20.0
step = 0
while time.monotonic() < t_end:
    # Irreversible bit erasure across L3-exceeding memory
    pat = (step * 73 + 19) & 0xFF
    buf[:] = bytes([pat]) * len(buf)
    c = a @ b
    a = 0.5 * a + 0.5 * (c / (np.linalg.norm(c) + 1.0))
    step += 1
"""


def _extract_audio_bands_250ms(wav_path: Path, n_frames: int, sample_rate: int = 48000) -> Tuple[List[List[int]], Dict[str, Any]]:
    """Convert raw 48 kHz mono s16 WAV into non-reconstructible 250 ms coarse spectral-band integers."""
    with wave.open(str(wav_path), "rb") as wf:
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
        sr = wf.getframerate()
        total_pcm = wf.getnframes()
        raw_pcm = wf.readframes(total_pcm)

    if sw != 2 or ch != 1 or sr != sample_rate:
        raise RuntimeError(f"Unexpected WAV format: ch={ch}, sw={sw}, sr={sr}")

    samples = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float64)
    frame_len = sample_rate // 4  # 12,000 samples = 250 ms
    freqs = np.fft.rfftfreq(frame_len, d=1.0 / sample_rate)
    window = np.hanning(frame_len)

    # 6 coarse physical acoustic bands + total RMS^2 + spectral centroid (zero speech reconstructibility)
    m_sub = (freqs >= 20.0) & (freqs < 100.0)       # motor/chassis fundamental (60 Hz @ 3600 RPM)
    m_bpf = (freqs >= 100.0) & (freqs < 500.0)      # fan blade-pass harmonics
    m_air = (freqs >= 500.0) & (freqs < 2000.0)     # turbulent airflow & upper harmonics
    m_mid = (freqs >= 2000.0) & (freqs < 6000.0)    # chassis / aerodynamic hiss
    m_hi = (freqs >= 6000.0) & (freqs <= 20000.0)   # VRM / inductor high-freq band
    m_all = (freqs >= 20.0) & (freqs <= 20000.0)

    band_rows: List[List[int]] = []
    # Also accumulate per-regime average narrowband spectrum (4 Hz bins) strictly for distant-fan R0 subtraction diagnostics
    reg_spec_acc = {r: np.zeros(len(freqs), dtype=np.float64) for r in range(4)}
    reg_spec_cnt = {r: 0 for r in range(4)}

    for idx in range(n_frames):
        s0 = idx * frame_len
        s1 = s0 + frame_len
        if s1 <= len(samples):
            seg = samples[s0:s1]
        elif s0 < len(samples):
            seg = np.pad(samples[s0:], (0, s1 - len(samples)))
        else:
            seg = np.zeros(frame_len, dtype=np.float64)

        seg_dc = seg - np.mean(seg)
        rms_sq = int(round(float(np.mean(seg_dc * seg_dc)) * 100.0))  # exact 0.01 LSB^2 integer units
        spec = np.fft.rfft(seg_dc * window)
        psd = (spec.real * spec.real + spec.imag * spec.imag) / (frame_len * frame_len)

        e_sub = int(round(float(np.sum(psd[m_sub])) * 1000.0))
        e_bpf = int(round(float(np.sum(psd[m_bpf])) * 1000.0))
        e_air = int(round(float(np.sum(psd[m_air])) * 1000.0))
        e_mid = int(round(float(np.sum(psd[m_mid])) * 1000.0))
        e_hi = int(round(float(np.sum(psd[m_hi])) * 1000.0))
        tot_p = float(np.sum(psd[m_all]))
        centroid_hz = int(round(float(np.sum(freqs[m_all] * psd[m_all]) / tot_p))) if tot_p > 1e-12 else 0

        band_rows.append([rms_sq, e_sub, e_bpf, e_air, e_mid, e_hi, centroid_hz])
        reg_id = min(3, idx // 60)
        reg_spec_acc[reg_id] += psd
        reg_spec_cnt[reg_id] += 1

    # R0 stationary ambient spectral subtraction summary (separates distant fan lines from local R2 boost!)
    r0_psd = reg_spec_acc[0] / max(1, reg_spec_cnt[0])
    r2_psd = reg_spec_acc[2] / max(1, reg_spec_cnt[2])
    r0_top_idx = np.argsort(r0_psd[m_all])[-5:][::-1]
    all_freqs = freqs[m_all]
    r0_top_peaks_hz = [int(round(float(all_freqs[k]))) for k in r0_top_idx]

    # Excess R2 - R0 peaks (strictly local self-excited acoustic lines above distant-fan floor!)
    excess_r2 = np.maximum(0.0, r2_psd - r0_psd)
    ex_top_idx = np.argsort(excess_r2[m_all])[-5:][::-1]
    r2_excess_peaks_hz = [int(round(float(all_freqs[k]))) for k in ex_top_idx]

    meta = {
        "sample_rate_hz": sample_rate,
        "total_pcm_samples": total_pcm,
        "duration_ms": int(round(1000.0 * total_pcm / sample_rate)),
        "frame_len_samples": frame_len,
        "r0_ambient_top5_peaks_hz": r0_top_peaks_hz,
        "r2_minus_r0_local_excess_top5_peaks_hz": r2_excess_peaks_hz,
    }
    return band_rows, meta


AUDIO_CHANNELS: Tuple[Tuple[str, str], ...] = (
    ("ac_rms_sq_0p01", "acoustic_energy"),
    ("ac_band_20_100hz", "acoustic_band_mE"),
    ("ac_band_100_500hz", "acoustic_band_mE"),
    ("ac_band_500_2000hz", "acoustic_band_mE"),
    ("ac_band_2k_6khz", "acoustic_band_mE"),
    ("ac_band_6k_20khz", "acoustic_band_mE"),
    ("ac_spectral_centroid_hz", "freq_hz"),
)


def run_phase2_capture() -> Dict[str, Any]:
    av_dir = HERE / "local_raw_av"
    av_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(str(av_dir), 0o700)

    utc_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    wav_path = av_dir / f"phase2_60s_48khz_mono_{utc_tag}.wav"

    hz = 4
    duration_s = 60
    target_samples = duration_s * hz  # 240 frames @ 250 ms
    interval_ms = 250

    sysfs_meta = probe._discover_sysfs_channels()
    sysfs_paths = [Path(ch["path"]) for ch in sysfs_meta]
    is_rapl = [ch["source"] == "sysfs_rapl_delta" for ch in sysfs_meta]
    rapl_max_range = [int(ch.get("max_range_uj", 0)) for ch in sysfs_meta]

    gpu_cmd = [
        "stdbuf",
        "-oL",
        "nvidia-smi",
        "--query-gpu=power.draw,temperature.gpu,clocks.current.sm,clocks.current.memory,utilization.gpu,utilization.memory",
        "--format=csv,noheader,nounits",
        "-lms",
        str(interval_ms),
    ]
    gpu_proc = subprocess.Popen(gpu_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)

    pw_cmd = [
        "pw-record",
        "--rate",
        "48000",
        "--channels",
        "1",
        "--format",
        "s16",
        "--container",
        "wav",
        str(wav_path),
    ]

    last_sysfs = [probe._read_int_sysfs(p) or 0 for p in sysfs_paths]
    last_rapl_raw = [probe._read_int_sysfs(p) or 0 for p in sysfs_paths]
    last_gpu = [0] * len(probe.GPU_CHANNELS)

    # Warm-up 1 tick before START
    if gpu_proc.stdout is not None:
        _ = gpu_proc.stdout.readline()
    for j, p in enumerate(sysfs_paths):
        v0 = probe._read_int_sysfs(p)
        if v0 is not None:
            last_sysfs[j] = v0
            last_rapl_raw[j] = v0

    workers: List[subprocess.Popen[bytes]] = []
    active_regime = -1

    def _stop_workers() -> None:
        nonlocal workers
        for w in workers:
            try:
                w.terminate()
            except OSError:
                pass
        for w in workers:
            try:
                w.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    w.kill()
                    w.wait(timeout=1)
                except OSError:
                    pass
        workers = []

    start_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    t0_ns = time.monotonic_ns()
    pw_proc = subprocess.Popen(pw_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    timestamps_ms: List[int] = []
    regimes: List[int] = []
    sys_gpu_rows: List[List[int]] = []

    try:
        for idx in range(target_samples):
            # Regime transitions at frames 0 (R0), 60 (R1), 120 (R2), 180 (R3)
            reg_id = min(3, idx // 60)
            if reg_id != active_regime:
                _stop_workers()
                if reg_id == 1:
                    # R1: 1-worker L1-resident reversible Feistel bijection (qfree-analog)
                    workers = [
                        subprocess.Popen([sys.executable, "-I", "-B", "-c", _R1_REVERSIBLE_SNIPPET], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    ]
                elif reg_id == 2:
                    # R2: 6-worker L3-exceeding irreversible erasure + dense ALU (mfree-analog)
                    workers = [
                        subprocess.Popen([sys.executable, "-B", "-c", _R2_ERASURE_SNIPPET], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        for _ in range(6)
                    ]
                active_regime = reg_id

            if gpu_proc.stdout is not None:
                line = gpu_proc.stdout.readline()
                if line:
                    parts = [p.strip() for p in line.strip().split(",")]
                    if len(parts) == len(probe.GPU_CHANNELS):
                        parsed_g: List[int] = []
                        ok_g = True
                        for p_s, (_gl, _gu, p10) in zip(parts, probe.GPU_CHANNELS):
                            v = probe._parse_scaled_decimal_int(p_s, p10)
                            if v is None:
                                ok_g = False
                                break
                            parsed_g.append(v)
                        if ok_g:
                            last_gpu = parsed_g

            now_ms = (time.monotonic_ns() - t0_ns) // 1_000_000
            cur_sys: List[int] = []
            for j, p in enumerate(sysfs_paths):
                v = probe._read_int_sysfs(p)
                if is_rapl[j]:
                    if v is None:
                        dv = 0
                    else:
                        prev = last_rapl_raw[j]
                        if v >= prev:
                            dv = v - prev
                        elif rapl_max_range[j] > prev:
                            dv = (rapl_max_range[j] - prev) + v
                        else:
                            dv = 0
                        last_rapl_raw[j] = v
                    cur_sys.append(dv)
                else:
                    if v is None:
                        v = last_sysfs[j]
                    else:
                        last_sysfs[j] = v
                    cur_sys.append(v)

            timestamps_ms.append(int(now_ms))
            regimes.append(reg_id)
            sys_gpu_rows.append(cur_sys + list(last_gpu))
    finally:
        _stop_workers()
        try:
            pw_proc.terminate()
            pw_proc.wait(timeout=3)
        except Exception:
            try:
                pw_proc.kill()
                pw_proc.wait(timeout=2)
            except Exception:
                pass
        stop_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        try:
            gpu_proc.terminate()
            gpu_proc.wait(timeout=3)
        except Exception:
            try:
                gpu_proc.kill()
                gpu_proc.wait(timeout=2)
            except Exception:
                pass

    os.chmod(str(wav_path), 0o600)
    wav_bytes = wav_path.read_bytes()
    wav_sha256 = hashlib.sha256(wav_bytes).hexdigest()

    audio_rows, audio_meta = _extract_audio_bands_250ms(wav_path, target_samples, sample_rate=48000)

    # Assemble combined channel metadata and anonymous integer matrix
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
    base_g = len(all_meta)
    for offset, (gl, gu, _p10) in enumerate(probe.GPU_CHANNELS):
        all_meta.append(
            {
                "channel_id": base_g + offset,
                "source": "nvidia-smi",
                "device": "gpu0",
                "field": gl,
                "label": gl,
                "unit_scale": gu,
                "module": "gpu_electromechanical",
            }
        )
    base_a = len(all_meta)
    for offset, (al, au) in enumerate(AUDIO_CHANNELS):
        all_meta.append(
            {
                "channel_id": base_a + offset,
                "source": "pw-record_250ms_coarse_band",
                "device": "mic0_coarse_energy",
                "field": al,
                "label": al,
                "unit_scale": au,
                "module": "acoustic_airborne",
            }
        )

    combined_rows = [sg + au for sg, au in zip(sys_gpu_rows, audio_rows)]
    x_sha = hashlib.sha256(probe._canonical_json_bytes(combined_rows)).hexdigest()

    snap = {
        "schema_version": probe.SCHEMA_RAW,
        "phase": "phase2_controlled_4regime_audio_rapl",
        "audio_consent_window": AUDIO_CONSENT_WINDOW,
        "room_noise_covariate": ROOM_NOISE_COVARIATE,
        "capture_start_utc": start_utc,
        "capture_stop_utc": stop_utc,
        "capture_utc_epoch_s": int(time.time()),
        "cadence_hz": hz,
        "nominal_interval_ms": interval_ms,
        "elapsed_ms": timestamps_ms[-1] if timestamps_ms else 0,
        "sample_count": len(combined_rows),
        "channel_count": len(all_meta),
        "mic_accessed": True,
        "audio_authorized_only": True,
        "camera_accessed": False,
        "sudo_used": False,
        "local_wav_filename": wav_path.name,
        "local_wav_bytes": len(wav_bytes),
        "local_wav_sha256": wav_sha256,
        "local_wav_mode_octal": "0600",
        "audio_spectral_summary": audio_meta,
        "regime_schedule": regimes,
        "timestamps_ms": timestamps_ms,
        "X_anonymous": combined_rows,
        "held_out_ground_truth_channels": all_meta,
        "x_anonymous_sha256": x_sha,
    }
    snap_bytes = probe._canonical_json_bytes(snap)
    out_raw = HERE / "phase2_controlled_snapshot.json"
    probe._atomic_write_0600(out_raw, snap_bytes)

    # Compute immediate exact R0..R3 regime summary + causal peak lags for instant [audio-stopped] report!
    def _find_ch(label_substr: str) -> Optional[int]:
        for c in all_meta:
            if label_substr in c["label"]:
                return c["channel_id"]
        return None

    idx_rapl_pkg = _find_ch("intel-rapl:0:package-0")
    idx_rapl_core = _find_ch("intel-rapl:0:0:core")
    idx_tcpu = _find_ch("TCPU")
    idx_pkg_t = _find_ch("Package id 0")
    idx_fan1 = _find_ch("cpu_fan")
    idx_fan2 = _find_ch("gpu_fan")
    idx_ac_rms = _find_ch("ac_rms_sq_0p01")
    idx_ac_bpf = _find_ch("ac_band_100_500hz")
    idx_ac_air = _find_ch("ac_band_500_2000hz")
    idx_ac_hi = _find_ch("ac_band_6k_20khz")

    regime_summary: Dict[str, Any] = {}
    for r in range(4):
        idxs = [t for t, rg in enumerate(regimes) if rg == r]
        def _mean(cid: Optional[int]) -> float:
            if cid is None or not idxs:
                return 0.0
            return sum(combined_rows[t][cid] for t in idxs) / len(idxs)

        # Convert 250ms delta_uJ to Watts: W = (uJ / 1e6) / 0.25 = uJ / 250_000
        regime_summary[f"R{r}"] = {
            "rapl_pkg_W": round(_mean(idx_rapl_pkg) / 250_000.0, 2),
            "rapl_core_W": round(_mean(idx_rapl_core) / 250_000.0, 2),
            "tcpu_C": round(_mean(idx_tcpu) / 1000.0, 2),
            "pkg_temp_C": round(_mean(idx_pkg_t) / 1000.0, 2),
            "cpu_fan_rpm": round(_mean(idx_fan1), 1),
            "gpu_fan_rpm": round(_mean(idx_fan2), 1),
            "ac_rms_sq": round(_mean(idx_ac_rms), 1),
            "ac_bpf_100_500hz": round(_mean(idx_ac_bpf), 1),
            "ac_air_500_2000hz": round(_mean(idx_ac_air), 1),
            "ac_hi_6k_20khz": round(_mean(idx_ac_hi), 1),
        }

    # Cross-correlation peak lag scan tau in [-24, +24] steps (-6s .. +6s)
    def _peak_lag(c_src: Optional[int], c_dst: Optional[int]) -> Dict[str, Any]:
        if c_src is None or c_dst is None:
            return {"best_lag_steps": 0, "best_lag_ms": 0, "peak_corr": 0.0}
        xs = np.array([combined_rows[t][c_src] for t in range(target_samples)], dtype=np.float64)
        ys = np.array([combined_rows[t][c_dst] for t in range(target_samples)], dtype=np.float64)
        xs -= xs.mean()
        ys -= ys.mean()
        if np.std(xs) == 0 or np.std(ys) == 0:
            return {"best_lag_steps": 0, "best_lag_ms": 0, "peak_corr": 0.0}
        best_r = -2.0
        best_tau = 0
        for tau in range(-24, 25):
            if tau >= 0:
                a, b = xs[: target_samples - tau], ys[tau:]
            else:
                a, b = xs[-tau:], ys[: target_samples + tau]
            den = float(np.linalg.norm(a) * np.linalg.norm(b))
            r_val = float(np.dot(a, b) / den) if den > 0 else 0.0
            if r_val > best_r:
                best_r = r_val
                best_tau = tau
        return {"best_lag_steps": best_tau, "best_lag_ms": best_tau * 250, "peak_corr": round(best_r, 4)}

    lags_summary = {
        "rapl_pkg_to_pkg_temp": _peak_lag(idx_rapl_pkg, idx_pkg_t),
        "rapl_pkg_to_tcpu": _peak_lag(idx_rapl_pkg, idx_tcpu),
        "pkg_temp_to_cpu_fan": _peak_lag(idx_pkg_t, idx_fan1),
        "rapl_pkg_to_cpu_fan": _peak_lag(idx_rapl_pkg, idx_fan1),
        "cpu_fan_to_ac_rms": _peak_lag(idx_fan1, idx_ac_rms),
        "cpu_fan_to_ac_air_500_2k": _peak_lag(idx_fan1, idx_ac_air),
        "rapl_pkg_to_ac_rms": _peak_lag(idx_rapl_pkg, idx_ac_rms),
        "rapl_pkg_to_ac_air_500_2k": _peak_lag(idx_rapl_pkg, idx_ac_air),
    }

    r0_rms = max(1e-9, regime_summary["R0"]["ac_rms_sq"])
    r2_rms = max(1e-9, regime_summary["R2"]["ac_rms_sq"])
    r2_vs_r0_db = round(10.0 * float(np.log10(r2_rms / r0_rms)), 2)

    out_summary = {
        "status": "AUDIO_STOPPED_CLEAN",
        "start_utc": start_utc,
        "stop_utc": stop_utc,
        "local_wav_filename": wav_path.name,
        "local_wav_bytes": len(wav_bytes),
        "local_wav_sha256": wav_sha256,
        "local_wav_duration_ms": audio_meta["duration_ms"],
        "snapshot_sha256": hashlib.sha256(snap_bytes).hexdigest(),
        "samples": len(combined_rows),
        "channels": len(all_meta),
        "r2_vs_r0_acoustic_snr_db": r2_vs_r0_db,
        "r0_ambient_top5_peaks_hz": audio_meta["r0_ambient_top5_peaks_hz"],
        "r2_excess_local_top5_peaks_hz": audio_meta["r2_minus_r0_local_excess_top5_peaks_hz"],
        "regimes": regime_summary,
        "causal_peak_lags": lags_summary,
    }
    return out_summary


def main() -> int:
    summary = run_phase2_capture()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
