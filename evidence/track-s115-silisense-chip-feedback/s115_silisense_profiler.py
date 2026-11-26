#!/usr/bin/env python3
"""SiliSense Non-Textbook Silicon Physics Profiler (Track S115 / PREREG-S115).

Computes the S113 Amendment-1 non-textbook silicon & firmware observables as
dependent variables for chip-level kernel profiling (Moissanite-Labs/silisense
candidate & HoloSphere telemetry bridge), behind a hard fail-closed two-mode
privacy and sensor airlock:

  - Mode 1 ('telemetry-only', DEFAULT):
      Strictly non-acoustic power/clock counters (intel-rapl pkg_w, core_w,
      uncore_w, psys_w + nvidia-smi/NVML gpu_power_w, sm_clock_mhz, throttle
      flags). Computes A3 (increment time-reversal asymmetry), A5 (fast-rail
      precursor lead-lag), and A7 (multi-lag Schur linear-residualized
      rank-copula mutual information with uncore_w). Zero microphone or camera!

  - Mode 2 ('dmic-authorized', FAIL-CLOSED OPT-IN):
      Requires explicit --enable-dmic-authorized, bounded positive
      --authorize-audio-window-sec in (0, 300], and explicit non-empty
      --pi-authorization-token with monotonic expiry enforcement. Adds 48 kHz
      4-channel DMIC A1 (ultrasonic bicoherence), A2 (18.5-22.2 kHz chirality
      + lateral CPU-vs-GPU VRM GCC-PHAT TDOA), A3-62us, and A5-80ms.

  - Camera devices (/dev/video*, V4L2, PipeWire video) are UNCONDITIONALLY
    FORBIDDEN (ERR_CAMERA_FORBIDDEN) across all modes per S113 H3/H4.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Callable, Sequence

import numpy as np
from scipy import ndimage, signal

PREREG_S115_ID = "PREREG-S115-SILICON-PHYSICS-FEEDBACK-OPTIMIZER-V1"
PREREG_S115_RELPATH = "notes/holosphere_kernel_transformer_2026_11_25/PREREG_S115_SILICON_PHYSICS_FEEDBACK_OPTIMIZER.md"
PREREG_S115_SHA256 = "4787a4f407bb09b440c19190a24e89fead862ba9cec96edd68e5d222e0f0dc75"

MAX_AUDIO_WINDOW_SEC = 300.0
MIN_AUTH_TOKEN_LEN = 8

_CAMERA_PATH_RE = re.compile(
    r"(^|/)(dev/video\d*|dev/media\d*|dev/char/81:\d+|v4l(/|$)|v4l2|video4linux|pipewire.*camera|libcamera|ir_led|infrared|ir_camera)",
    re.IGNORECASE,
)
_AUDIO_DEV_RE = re.compile(
    r"(^|/)(dev/snd(/|$)|snd/|alsa|pcmC\d+D\d+|arecord|pw-record|parec)",
    re.IGNORECASE,
)


class SiliSenseError(Exception):
    """Base typed error for SiliSense (never bare AssertionError)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


class SiliSensePermissionError(SiliSenseError):
    """Raised when the sensor/privacy airlock refuses an unauthorized access."""


class SiliSenseValueError(SiliSenseError):
    """Raised on malformed telemetry shapes, parameters, or NaNs/Infs."""


def require_ok(condition: bool, code: str, message: str) -> None:
    """Fail-closed check replacing bare assert statements."""
    if not condition:
        raise SiliSenseValueError(code, message)


def require_perm(condition: bool, code: str, message: str) -> None:
    """Fail-closed permission check for sensor boundaries."""
    if not condition:
        raise SiliSensePermissionError(code, message)


# =============================================================================
# Two-Mode Sensor & Privacy Airlock
# =============================================================================


def validate_endpoint_path(endpoint: str | Path, auth_gate: "AudioAuthorizationGate | None" = None) -> None:
    """Enforce unconditional camera ban and fail-closed audio device gating."""
    require_ok(isinstance(endpoint, (str, Path)), "ERR_BAD_ENDPOINT_TYPE", "Endpoint must be str or Path")
    text = str(endpoint).strip()
    require_ok(len(text) > 0 and "\x00" not in text, "ERR_EMPTY_ENDPOINT", "Endpoint path must be non-empty without NUL")
    candidates = [text, text.replace("\\", "/"), os.path.normpath(text.replace("\\", "/"))]
    if text.startswith("/") or text.startswith(".") or "/" in text or "\\" in text:
        try:
            candidates.append(str(Path(text.replace("\\", "/")).resolve(strict=False)))
        except OSError:
            pass
    for cand in candidates:
        if _CAMERA_PATH_RE.search(cand):
            raise SiliSensePermissionError(
                "ERR_CAMERA_FORBIDDEN",
                f"Camera/optical endpoint {text!r} is permanently forbidden in SiliSense (S113 H3/H4 zero-leakage invariant)",
            )
    for cand in candidates:
        if _AUDIO_DEV_RE.search(cand):
            require_perm(
                auth_gate is not None,
                "ERR_DMIC_DISABLED_DEFAULT",
                f"Audio endpoint {text!r} refused: Mode 1 ('telemetry-only') forbids microphone access",
            )
            if auth_gate is not None:
                auth_gate.verify_active()
            break


@dataclass(frozen=True)
class AudioAuthorizationGate:
    """Capability token gating Mode-2 DMIC access with a monotonic expiry clock."""

    enable_dmic_authorized: bool
    authorize_audio_window_sec: float
    pi_authorization_token: str = field(repr=False)
    created_mono: float = 0.0
    clock_fn: Callable[[], float] = field(default=time.monotonic, repr=False, compare=False)

    def __post_init__(self) -> None:
        require_perm(
            self.enable_dmic_authorized is True,
            "ERR_DMIC_UNAUTHORIZED",
            "Mode 2 DMIC access requires explicit enable_dmic_authorized=True",
        )
        require_perm(
            isinstance(self.authorize_audio_window_sec, (int, float))
            and not isinstance(self.authorize_audio_window_sec, bool)
            and math.isfinite(float(self.authorize_audio_window_sec))
            and 0.0 < float(self.authorize_audio_window_sec) <= MAX_AUDIO_WINDOW_SEC,
            "ERR_AUDIO_WINDOW_BOUNDS",
            f"authorize_audio_window_sec must lie in (0, {MAX_AUDIO_WINDOW_SEC}]",
        )
        require_perm(
            isinstance(self.pi_authorization_token, str)
            and len(self.pi_authorization_token.strip()) >= MIN_AUTH_TOKEN_LEN
            and self.pi_authorization_token.strip().isascii(),
            "ERR_AUTH_TOKEN_INVALID",
            f"Mode 2 DMIC access requires ASCII pi_authorization_token of length >= {MIN_AUTH_TOKEN_LEN}",
        )
        require_perm(
            isinstance(self.created_mono, (int, float))
            and not isinstance(self.created_mono, bool)
            and math.isfinite(float(self.created_mono)),
            "ERR_BAD_CREATED_MONO",
            "created_mono must be finite float",
        )

    @classmethod
    def create(
        cls,
        *,
        enable_dmic_authorized: bool,
        authorize_audio_window_sec: float | None,
        pi_authorization_token: str | None,
        clock_fn: Callable[[], float] = time.monotonic,
    ) -> "AudioAuthorizationGate":
        require_perm(
            enable_dmic_authorized is True,
            "ERR_DMIC_UNAUTHORIZED",
            "Mode 2 DMIC access requires explicit enable_dmic_authorized=True",
        )
        require_perm(
            authorize_audio_window_sec is not None
            and isinstance(authorize_audio_window_sec, (int, float))
            and not isinstance(authorize_audio_window_sec, bool)
            and math.isfinite(float(authorize_audio_window_sec)),
            "ERR_AUDIO_WINDOW_MISSING",
            "Mode 2 DMIC access requires explicit finite --authorize-audio-window-sec",
        )
        win_sec = float(authorize_audio_window_sec)  # type: ignore[arg-type]
        require_perm(
            0.0 < win_sec <= MAX_AUDIO_WINDOW_SEC,
            "ERR_AUDIO_WINDOW_BOUNDS",
            f"authorize_audio_window_sec must lie in (0, {MAX_AUDIO_WINDOW_SEC}], got {win_sec}",
        )
        tok = (pi_authorization_token or "").strip()
        require_perm(
            len(tok) >= MIN_AUTH_TOKEN_LEN and tok.isascii(),
            "ERR_AUTH_TOKEN_INVALID",
            f"Mode 2 DMIC access requires ASCII pi_authorization_token of length >= {MIN_AUTH_TOKEN_LEN}",
        )
        now_m = float(clock_fn())
        return cls(
            enable_dmic_authorized=True,
            authorize_audio_window_sec=win_sec,
            pi_authorization_token=tok,
            created_mono=now_m,
            clock_fn=clock_fn,
        )

    def remaining_sec(self) -> float:
        elapsed = float(self.clock_fn()) - self.created_mono
        return self.authorize_audio_window_sec - elapsed

    def verify_active(self) -> None:
        require_perm(self.enable_dmic_authorized is True, "ERR_DMIC_UNAUTHORIZED", "DMIC gate not enabled")
        elapsed = float(self.clock_fn()) - self.created_mono
        require_perm(
            elapsed >= -1e-9,
            "ERR_CLOCK_SKEW",
            "Monotonic clock moved backwards unexpectedly",
        )
        require_perm(
            elapsed <= self.authorize_audio_window_sec,
            "ERR_AUDIO_WINDOW_EXPIRED",
            f"Authorized audio window ({self.authorize_audio_window_sec:.2f}s) expired ({elapsed:.2f}s elapsed)",
        )


def _check_dmic_permission(auth_gate: AudioAuthorizationGate | None, allow_offline_array: bool) -> None:
    if auth_gate is not None:
        auth_gate.verify_active()
        return
    require_perm(
        allow_offline_array is True,
        "ERR_DMIC_DISABLED_DEFAULT",
        "DMIC observables (A1/A2/A3-62us/A5-80ms) are disabled in default Mode 1 ('telemetry-only'); "
        "pass an active AudioAuthorizationGate or explicit allow_offline_array=True for synthetic/offline arrays.",
    )


# =============================================================================
# Deterministic Surrogate & Multiple-Testing Engines
# =============================================================================


def _clean_1d(arr: Sequence[float] | np.ndarray, name: str, min_len: int = 16) -> np.ndarray:
    x = np.asarray(arr, dtype=np.float64)
    require_ok(x.ndim == 1, "ERR_DIM_1D", f"{name} must be 1D, got shape {x.shape}")
    require_ok(x.shape[0] >= min_len, "ERR_TOO_SHORT", f"{name} length {x.shape[0]} < {min_len}")
    require_ok(bool(np.all(np.isfinite(x))), "ERR_NONFINITE", f"{name} contains NaN or Inf")
    return x


def holm_bonferroni(pvals: Sequence[float]) -> list[float]:
    """Exact step-down Holm-Bonferroni family-wise adjustment."""
    m = len(pvals)
    if m == 0:
        return []
    for p in pvals:
        require_ok(math.isfinite(float(p)) and 0.0 <= float(p) <= 1.0, "ERR_BAD_PVAL", f"Invalid p-value {p}")
    order = sorted(range(m), key=lambda idx: float(pvals[idx]))
    adjusted = [1.0] * m
    running_max = 0.0
    for rank, idx in enumerate(order):
        scaled = min(1.0, float(pvals[idx]) * float(m - rank))
        if scaled > running_max:
            running_max = scaled
        adjusted[idx] = running_max
    return adjusted


def iaaft_surrogates_1d(
    x: np.ndarray,
    n_surr: int,
    rng: np.random.Generator,
    max_iter: int = 35,
) -> np.ndarray:
    """Vectorized Iterative Amplitude-Adjusted Fourier Transform (Schreiber & Schmitz 1996).

    Preserves BOTH the exact empirical amplitude distribution of `x` AND the
    amplitude spectrum |rfft(x)| to prevent colored 1/f or AR(1) spectra from
    generating false positives on nonlinear/asymmetry observables.
    """
    x_clean = _clean_1d(x, "iaaft_input", min_len=16)
    require_ok(n_surr >= 1, "ERR_BAD_NSURR", f"n_surr must be >= 1, got {n_surr}")
    n = x_clean.shape[0]
    if float(np.std(x_clean)) <= 1e-15:
        return np.tile(x_clean, (n_surr, 1))

    sorted_x = np.sort(x_clean)
    orig_fft = np.fft.rfft(x_clean)
    target_amp = np.abs(orig_fft)
    dc_val = orig_fft[0].real

    order = np.argsort(rng.random((n_surr, n)), axis=1)
    cur = sorted_x[order]
    prev_ranks: np.ndarray | None = None

    for _ in range(max_iter):
        spec = np.fft.rfft(cur, axis=1)
        mag = np.abs(spec)
        unit_phase = np.where(mag > 1e-30, spec / np.maximum(mag, 1e-30), 1.0 + 0.0j)
        new_spec = target_amp[None, :] * unit_phase
        new_spec[:, 0] = dc_val + 0.0j
        if n % 2 == 0:
            sign_nyq = np.where(spec[:, -1].real >= 0.0, 1.0, -1.0)
            new_spec[:, -1] = (target_amp[-1] * sign_nyq) + 0.0j
        y = np.fft.irfft(new_spec, n=n, axis=1)
        ranks = np.argsort(np.argsort(y, axis=1), axis=1)
        cur = sorted_x[ranks]
        if prev_ranks is not None and np.array_equal(ranks, prev_ranks):
            break
        prev_ranks = ranks

    return cur


# =============================================================================
# Core Non-Textbook Silicon Lenses (A3, A5, A7 Default + Opt-In A1, A2)
# =============================================================================


def _third_order_asymmetry_1d(x: np.ndarray, lag: int) -> float:
    diff = x[lag:] - x[:-lag]
    var = float(np.mean(diff * diff))
    if var <= 1e-24:
        return 0.0
    m3 = float(np.mean(diff * diff * diff))
    return m3 / (var ** 1.5)


def _third_order_asymmetry_batch(batch: np.ndarray, lag: int) -> np.ndarray:
    diff = batch[:, lag:] - batch[:, :-lag]
    var = np.mean(diff * diff, axis=1)
    m3 = np.mean(diff * diff * diff, axis=1)
    denom = np.maximum(var, 1e-24) ** 1.5
    return np.where(var > 1e-24, m3 / denom, 0.0)


def compute_a3_time_reversal_asymmetry(
    series: Sequence[float] | np.ndarray,
    *,
    dt_ms: float = 5.0,
    lags: Sequence[int] = (1, 2, 3),
    n_iaaft: int = 799,
    seed: int = 42,
) -> dict[str, Any]:
    """Lens A3: Microscopic third-order time-reversal asymmetry A(tau) vs IAAFT null.

    Detects nonlinear sawtooth ramp/cliff steepening from unfused micro-kernel
    bursts (5-15 ms on 200 Hz RAPL/NVML in Mode 1; 20.8-62.5 us on 48 kHz DMIC).
    Uses exact Westfall-Young max-|z| surrogate calibration across `lags` for
    family-wise lag control without conservative Bonferroni loss.
    """
    x = _clean_1d(series, "a3_series", min_len=32)
    require_ok(dt_ms > 0.0 and math.isfinite(dt_ms), "ERR_BAD_DT", "dt_ms must be > 0")
    require_ok(len(lags) >= 1, "ERR_EMPTY_LAGS", "At least one lag required")
    for lag in lags:
        require_ok(isinstance(lag, int) and 1 <= lag < x.shape[0] // 4, "ERR_BAD_LAG", f"Invalid lag {lag}")

    rng = np.random.default_rng(seed)
    surr = iaaft_surrogates_1d(x, n_iaaft, rng)

    per_lag: list[dict[str, Any]] = []
    raw_pvals: list[float] = []
    surr_abs_z_matrix = np.zeros((n_iaaft, len(lags)), dtype=np.float64)

    for l_idx, lag in enumerate(lags):
        obs = _third_order_asymmetry_1d(x, lag)
        null_vals = _third_order_asymmetry_batch(surr, lag)
        mu = float(np.mean(null_vals))
        sd = float(np.std(null_vals, ddof=1)) if n_iaaft > 1 else 0.0
        z_val = 0.0 if sd <= 1e-15 else (obs - mu) / sd
        if sd > 1e-15:
            surr_abs_z_matrix[:, l_idx] = np.abs(null_vals - mu) / sd
        ge_count = int(np.sum(np.abs(null_vals - mu) >= abs(obs - mu) - 1e-15))
        p_emp = float(1 + ge_count) / float(1 + n_iaaft)
        raw_pvals.append(p_emp)
        per_lag.append(
            {
                "lag_samples": int(lag),
                "lag_ms": round(float(lag) * float(dt_ms), 6),
                "asymmetry": round(obs, 6),
                "abs_asymmetry": round(abs(obs), 6),
                "iaaft_mean": round(mu, 6),
                "iaaft_std": round(sd, 6),
                "z_iaaft": round(z_val, 6),
                "p_emp": round(p_emp, 6),
            }
        )

    holm_p = holm_bonferroni(raw_pvals)
    for row, ph in zip(per_lag, holm_p):
        row["p_holm"] = round(ph, 6)

    best_idx = max(range(len(per_lag)), key=lambda i: abs(float(per_lag[i]["z_iaaft"])))
    best = per_lag[best_idx]
    obs_max_abs_z = abs(float(best["z_iaaft"]))
    null_max_abs_z = np.max(surr_abs_z_matrix, axis=1)
    p_max_t = float(1 + int(np.sum(null_max_abs_z >= obs_max_abs_z - 1e-12))) / float(1 + n_iaaft)

    return {
        "lens": "A3_time_reversal_asymmetry",
        "n_samples": int(x.shape[0]),
        "n_iaaft": int(n_iaaft),
        "dominant_lag_samples": best["lag_samples"],
        "dominant_lag_ms": best["lag_ms"],
        "asymmetry": best["asymmetry"],
        "abs_asymmetry": best["abs_asymmetry"],
        "z_iaaft": best["z_iaaft"],
        "p_emp": best["p_emp"],
        "p_holm": round(p_max_t, 6),
        "significant_0p005": bool(p_max_t < 0.005 and obs_max_abs_z >= 3.5),
        "per_lag": per_lag,
    }


def causal_innovation_zscores(series: Sequence[float] | np.ndarray, alpha: float = 0.05) -> np.ndarray:
    """Strictly causal O(N) positive-step innovation z-score (zero lookahead).

    Shared identically between offline A5 analysis and the live H15b
    PrecursorThrottleGovernor ring buffer.
    """
    x = _clean_1d(series, "innovation_series", min_len=16)
    require_ok(0.0 < alpha < 1.0, "ERR_BAD_ALPHA", f"alpha must be in (0, 1), got {alpha}")
    pos_step = np.zeros_like(x)
    pos_step[1:] = np.maximum(0.0, x[1:] - x[:-1])

    z_out = np.zeros_like(x)
    warmup = min(12, x.shape[0] // 2)
    init_slice = pos_step[1 : warmup + 1]
    mu = float(np.mean(init_slice))
    var = max(float(np.var(init_slice)), 1e-4)

    for t in range(1, x.shape[0]):
        val = float(pos_step[t])
        if t >= warmup:
            sd = math.sqrt(max(var, 1e-8))
            raw_z = 0.0 if sd <= 1e-6 else (val - mu) / sd
            z_out[t] = max(-15.0, min(15.0, raw_z))
        diff = val - mu
        mu = (1.0 - alpha) * mu + alpha * val
        var = (1.0 - alpha) * var + alpha * (diff * diff)
    return z_out


def _extract_peaks(z_arr: np.ndarray, thresh: float, min_sep: int) -> np.ndarray:
    candidates = np.flatnonzero(z_arr >= thresh)
    if candidates.size == 0:
        return candidates
    kept: list[int] = []
    last_idx = -min_sep - 1
    for idx in candidates.tolist():
        if idx - last_idx >= min_sep:
            kept.append(idx)
            last_idx = idx
        elif z_arr[idx] > z_arr[kept[-1]]:
            kept[-1] = idx
            last_idx = idx
    return np.asarray(kept, dtype=np.int64)


def compute_a5_precursor_lead_lag(
    fast_series: Sequence[float] | np.ndarray,
    slow_series: Sequence[float] | np.ndarray,
    *,
    dt_ms: float = 5.0,
    max_lag_ms: float = 250.0,
    z_thresh: float = 2.5,
    n_shifts: int = 500,
    seed: int = 42,
) -> dict[str, Any]:
    """Lens A5: Causal fast-rail innovation precursor lead-lag vs circular-shift null.

    Measures whether fast-rail spikes (200 Hz pkg_w/gpu_power_w in Mode 1, or
    48 kHz DMIC ultrasonic envelope in Mode 2) systematically precede slow
    firmware/thermal responses (psys_w, 1 Hz SMI, or SwPowerCap throttle onset)
    at negative lag (fast leads slow).
    """
    f_arr = _clean_1d(fast_series, "a5_fast_series", min_len=64)
    s_arr = _clean_1d(slow_series, "a5_slow_series", min_len=64)
    require_ok(f_arr.shape == s_arr.shape, "ERR_SHAPE_MISMATCH", "fast_series and slow_series must match length")
    require_ok(dt_ms > 0.0 and max_lag_ms >= dt_ms, "ERR_BAD_LAG_MS", "Invalid dt_ms or max_lag_ms")
    require_ok(n_shifts >= 50, "ERR_TOO_FEW_SHIFTS", "n_shifts must be >= 50")

    n = f_arr.shape[0]
    max_lag = max(1, min(int(round(max_lag_ms / dt_ms)), n // 6))
    guard = max(2 * max_lag + 2, n // 10)
    require_ok(n > 2 * guard + 8, "ERR_SERIES_TOO_SHORT_FOR_GUARD", f"Need length > {2 * guard + 8}, got {n}")

    zf = causal_innovation_zscores(f_arr)
    zs = causal_innovation_zscores(s_arr)

    zf_std = float(np.std(zf))
    zs_std = float(np.std(zs))
    if zf_std <= 1e-12 or zs_std <= 1e-12:
        return {
            "lens": "A5_precursor_lead_lag",
            "n_samples": int(n),
            "peak_precursor_lag_samples": -1,
            "peak_precursor_lag_ms": round(-dt_ms, 4),
            "peak_precursor_xcorr": 0.0,
            "median_event_lead_ms": 0.0,
            "precursor_event_rate": 0.0,
            "n_fast_events": 0,
            "n_slow_events": 0,
            "z_circ": 0.0,
            "p_circ": 1.0,
            "significant_0p005": False,
        }

    zf_norm = (zf - float(np.mean(zf))) / zf_std
    zs_norm = (zs - float(np.mean(zs))) / zs_std

    # Causal precursor lags: lag_k in [1 .. max_lag] means fast[t - lag_k] precedes slow[t] (lead = -lag_k * dt_ms)
    obs_corrs = np.array(
        [float(np.dot(zf_norm[:-k], zs_norm[k:])) / float(n - k) for k in range(1, max_lag + 1)],
        dtype=np.float64,
    )
    best_idx = int(np.argmax(obs_corrs))
    best_lag_k = best_idx + 1
    obs_peak = float(obs_corrs[best_idx])

    rng = np.random.default_rng(seed)
    shifts = rng.integers(guard, n - guard, size=n_shifts)
    null_peaks = np.empty(n_shifts, dtype=np.float64)
    for i, sh in enumerate(shifts.tolist()):
        zf_sh = np.roll(zf_norm, int(sh))
        c_max = max(float(np.dot(zf_sh[:-k], zs_norm[k:])) / float(n - k) for k in range(1, max_lag + 1))
        null_peaks[i] = c_max

    null_mu = float(np.mean(null_peaks))
    null_sd = float(np.std(null_peaks, ddof=1))
    z_circ = 0.0 if null_sd <= 1e-15 else (obs_peak - null_mu) / null_sd
    ge_cnt = int(np.sum(null_peaks >= obs_peak - 1e-15))
    p_circ = float(1 + ge_cnt) / float(1 + n_shifts)

    # Event-level precursor coincidence summary
    min_sep = max(2, max_lag // 2)
    fast_ev = _extract_peaks(zf, z_thresh, min_sep=min_sep)
    slow_ev = _extract_peaks(zs, z_thresh, min_sep=min_sep)
    leads_ms: list[float] = []
    for ts in slow_ev.tolist():
        preceding = fast_ev[(fast_ev >= ts - max_lag) & (fast_ev <= ts - 1)]
        if preceding.size > 0:
            nearest_tf = int(preceding[-1])
            leads_ms.append(float(nearest_tf - ts) * float(dt_ms))

    event_rate = float(len(leads_ms)) / float(slow_ev.size) if slow_ev.size > 0 else 0.0
    med_lead = float(np.median(leads_ms)) if leads_ms else round(-float(best_lag_k) * float(dt_ms), 4)

    return {
        "lens": "A5_precursor_lead_lag",
        "n_samples": int(n),
        "peak_precursor_lag_samples": -int(best_lag_k),
        "peak_precursor_lag_ms": round(-float(best_lag_k) * float(dt_ms), 4),
        "peak_precursor_xcorr": round(obs_peak, 6),
        "median_event_lead_ms": round(med_lead, 4),
        "precursor_event_rate": round(event_rate, 6),
        "n_fast_events": int(fast_ev.size),
        "n_slow_events": int(slow_ev.size),
        "z_circ": round(z_circ, 6),
        "p_circ": round(p_circ, 6),
        "significant_0p005": bool(p_circ < 0.005 and z_circ >= 3.0),
    }


def _rank_copula_mi_batch(
    bin_u: np.ndarray,
    ry_batch: np.ndarray,
    n_bins: int,
) -> np.ndarray:
    """Vectorized empirical quantile-copula mutual information across batch rows."""
    m = bin_u.shape[0]
    ranks_v = np.argsort(np.argsort(ry_batch, axis=1), axis=1)
    bins_v = (ranks_v * n_bins) // m

    # Marginal counts are fixed by deterministic quantile binning
    u_counts = np.bincount(bin_u, minlength=n_bins).astype(np.float64)
    p_u = u_counts / float(m)
    h_u = -float(np.sum(np.where(p_u > 0.0, p_u * np.log(np.maximum(p_u, 1e-30)), 0.0)))

    v_single = (np.arange(m) * n_bins) // m
    v_counts = np.bincount(v_single, minlength=n_bins).astype(np.float64)
    p_v = v_counts / float(m)
    h_v = -float(np.sum(np.where(p_v > 0.0, p_v * np.log(np.maximum(p_v, 1e-30)), 0.0)))

    cells = bin_u[None, :] * n_bins + bins_v
    k2 = n_bins * n_bins
    mi_out = np.empty(ry_batch.shape[0], dtype=np.float64)
    mm_bias = float((n_bins - 1) * (n_bins - 1)) / float(2 * m)
    for idx in range(ry_batch.shape[0]):
        c_joint = np.bincount(cells[idx], minlength=k2).astype(np.float64)
        p_uv = c_joint / float(m)
        h_uv = -float(np.sum(np.where(p_uv > 0.0, p_uv * np.log(np.maximum(p_uv, 1e-30)), 0.0)))
        mi_out[idx] = (h_u + h_v - h_uv) - mm_bias
    return mi_out


def compute_a7_nonlinear_uncore_copula_mi(
    uncore_w: Sequence[float] | np.ndarray,
    target_series: Sequence[float] | np.ndarray,
    *,
    max_linear_lag: int = 5,
    n_bins: int | None = None,
    n_iaaft: int = 199,
    seed: int = 42,
) -> dict[str, Any]:
    """Lens A7: Multi-lag linear Schur residualization + rank-copula MI vs IAAFT null.

    Projects `target_series` orthogonal to {1, uncore_w(t - L) .. uncore_w(t + L)}
    so all linear lag correlations vanish (|rho| <= 1e-9), then measures purely
    nonlinear copula mutual information (tail/burst ring-bus contention) against
    IAAFT surrogates of the linear-free residual.
    """
    u = _clean_1d(uncore_w, "a7_uncore_w", min_len=48)
    y = _clean_1d(target_series, "a7_target_series", min_len=48)
    require_ok(u.shape == y.shape, "ERR_SHAPE_MISMATCH", "uncore_w and target_series must have identical length")
    require_ok(0 <= max_linear_lag <= u.shape[0] // 8, "ERR_BAD_MAX_LAG", f"Invalid max_linear_lag={max_linear_lag}")

    n = u.shape[0]
    lag = int(max_linear_lag)
    m = n - 2 * lag
    u_mid = u[lag : n - lag]
    y_mid = y[lag : n - lag]

    if float(np.std(u_mid)) <= 1e-14 or float(np.std(y_mid)) <= 1e-14:
        return {
            "lens": "A7_nonlinear_uncore_copula_mi",
            "n_interior": int(m),
            "n_bins": 3,
            "max_abs_residual_linear_corr": 0.0,
            "copula_mi_nats": 0.0,
            "copula_mi_bits": 0.0,
            "z_iaaft": 0.0,
            "p_emp": 1.0,
            "significant_0p005": False,
        }

    cols = [np.ones(m, dtype=np.float64)]
    for k in range(-lag, lag + 1):
        cols.append(u[lag + k : n - lag + k])
    design = np.column_stack(cols)
    beta, *_ = np.linalg.lstsq(design, y_mid, rcond=None)
    r_y = y_mid - design @ beta

    ry_std = float(np.std(r_y))
    max_lin_corr = 0.0
    if ry_std > 1e-14:
        ry_c = (r_y - float(np.mean(r_y))) / ry_std
        for k in range(-lag, lag + 1):
            uk = u[lag + k : n - lag + k]
            uk_std = float(np.std(uk))
            if uk_std > 1e-14:
                c_val = abs(float(np.dot(ry_c, (uk - float(np.mean(uk))) / uk_std)) / float(m))
                if c_val > max_lin_corr:
                    max_lin_corr = c_val

    require_ok(
        max_lin_corr <= 1e-7,
        "ERR_SCHUR_RESIDUAL_NOT_ORTHOGONAL",
        f"Multi-lag linear residualization failed: max_lin_corr={max_lin_corr}",
    )

    k_bins = int(n_bins) if n_bins is not None else max(3, min(6, int(math.sqrt(float(m) / 8.0))))
    require_ok(2 <= k_bins <= 12, "ERR_BAD_NBINS", f"Invalid n_bins={k_bins}")

    bin_u = (np.argsort(np.argsort(u_mid)) * k_bins) // m
    obs_mi_raw = float(_rank_copula_mi_batch(bin_u, r_y[None, :], k_bins)[0])

    rng = np.random.default_rng(seed)
    surr_ry = iaaft_surrogates_1d(r_y, n_iaaft, rng)
    null_mi = _rank_copula_mi_batch(bin_u, surr_ry, k_bins)

    mu = float(np.mean(null_mi))
    sd = float(np.std(null_mi, ddof=1)) if n_iaaft > 1 else 0.0
    z_val = 0.0 if sd <= 1e-15 else (obs_mi_raw - mu) / sd
    ge_cnt = int(np.sum(null_mi >= obs_mi_raw - 1e-15))
    p_emp = float(1 + ge_cnt) / float(1 + n_iaaft)
    mi_pos = max(0.0, obs_mi_raw)

    return {
        "lens": "A7_nonlinear_uncore_copula_mi",
        "n_interior": int(m),
        "n_bins": int(k_bins),
        "max_abs_residual_linear_corr": round(max_lin_corr, 12),
        "copula_mi_nats": round(mi_pos, 6),
        "copula_mi_bits": round(mi_pos / math.log(2.0), 6),
        "raw_mm_mi_nats": round(obs_mi_raw, 6),
        "iaaft_mean_nats": round(mu, 6),
        "iaaft_std_nats": round(sd, 6),
        "z_iaaft": round(z_val, 6),
        "p_emp": round(p_emp, 6),
        "significant_0p005": bool(p_emp <= 0.005 and z_val >= 3.5),
    }


# =============================================================================
# Mode-2 Opt-In Authorized DMIC Lenses (A1 & A2)
# =============================================================================


def _bicoherence_principal_triangle(
    x: np.ndarray,
    window: np.ndarray,
    step: int,
    k1_idx: np.ndarray,
    k2_idx: np.ndarray,
    ksum_idx: np.ndarray,
) -> np.ndarray:
    n_fft = window.shape[0]
    n_seg = 1 + (x.shape[0] - n_fft) // step
    strides = (x.strides[0] * step, x.strides[0])
    frames = np.lib.stride_tricks.as_strided(x, shape=(n_seg, n_fft), strides=strides)
    spec = np.fft.rfft((frames - np.mean(frames, axis=1, keepdims=True)) * window[None, :], axis=1)

    p12 = spec[:, k1_idx] * spec[:, k2_idx]
    s3 = spec[:, ksum_idx]
    bispec = np.mean(p12 * np.conj(s3), axis=0)
    denom = np.mean(np.abs(p12) ** 2, axis=0) * np.mean(np.abs(s3) ** 2, axis=0)
    return np.where(denom > 1e-30, (np.abs(bispec) ** 2) / np.maximum(denom, 1e-30), 0.0)


def compute_a1_ultrasonic_bicoherence(
    dmic_wave: Sequence[float] | np.ndarray,
    *,
    fs: int = 48000,
    f_min_hz: float = 6000.0,
    f_max_hz: float = 23000.0,
    n_fft: int = 256,
    n_iaaft: int = 99,
    seed: int = 42,
    auth_gate: AudioAuthorizationGate | None = None,
    allow_offline_array: bool = False,
) -> dict[str, Any]:
    """Lens A1 (Mode-2 Opt-In): Kim-Powers normalized ultrasonic auto-bicoherence."""
    _check_dmic_permission(auth_gate, allow_offline_array)
    x = _clean_1d(dmic_wave, "a1_dmic_wave", min_len=max(4 * n_fft, 1024))
    require_ok(fs >= 16000 and n_fft >= 64, "ERR_BAD_A1_PARAMS", "Invalid fs or n_fft")
    require_ok(0.0 < f_min_hz < f_max_hz <= 0.5 * fs, "ERR_BAD_A1_BAND", "Invalid ultrasonic band")

    freqs = np.fft.rfftfreq(n_fft, d=1.0 / float(fs))
    valid_bins = np.flatnonzero((freqs >= f_min_hz) & (freqs <= f_max_hz))
    require_ok(valid_bins.size >= 4, "ERR_EMPTY_A1_TRIANGLE", "Too few FFT bins in ultrasonic band")

    k_max = int(valid_bins[-1])
    k1_list: list[int] = []
    k2_list: list[int] = []
    ks_list: list[int] = []
    for k1 in valid_bins.tolist():
        for k2 in valid_bins.tolist():
            if k2 <= k1 and (k1 + k2) <= k_max:
                k1_list.append(int(k1))
                k2_list.append(int(k2))
                ks_list.append(int(k1 + k2))
    require_ok(len(k1_list) >= 1, "ERR_NO_A1_TRIADS", "No valid bicoherence triads in band")

    k1_arr = np.asarray(k1_list, dtype=np.int64)
    k2_arr = np.asarray(k2_list, dtype=np.int64)
    ks_arr = np.asarray(ks_list, dtype=np.int64)
    win = np.hanning(n_fft)
    step = n_fft // 2

    b2_obs = _bicoherence_principal_triangle(x, win, step, k1_arr, k2_arr, ks_arr)
    peak_i = int(np.argmax(b2_obs))
    obs_max = float(b2_obs[peak_i])
    top_k = min(5, b2_obs.size)
    obs_top5 = float(np.mean(np.sort(b2_obs)[-top_k:]))

    rng = np.random.default_rng(seed)
    surr = iaaft_surrogates_1d(x, n_iaaft, rng, max_iter=25)
    null_max = np.empty(n_iaaft, dtype=np.float64)
    for s_idx in range(n_iaaft):
        b2_s = _bicoherence_principal_triangle(surr[s_idx], win, step, k1_arr, k2_arr, ks_arr)
        null_max[s_idx] = float(np.max(b2_s))

    mu = float(np.mean(null_max))
    sd = float(np.std(null_max, ddof=1)) if n_iaaft > 1 else 0.0
    z_val = 0.0 if sd <= 1e-15 else (obs_max - mu) / sd
    ge_cnt = int(np.sum(null_max >= obs_max - 1e-15))
    p_emp = float(1 + ge_cnt) / float(1 + n_iaaft)

    return {
        "lens": "A1_ultrasonic_bicoherence",
        "max_b2": round(obs_max, 6),
        "mean_top5_b2": round(obs_top5, 6),
        "peak_triad_hz": [
            round(float(freqs[k1_arr[peak_i]]), 2),
            round(float(freqs[k2_arr[peak_i]]), 2),
            round(float(freqs[ks_arr[peak_i]]), 2),
        ],
        "iaaft_mean_max_b2": round(mu, 6),
        "iaaft_std_max_b2": round(sd, 6),
        "z_iaaft": round(z_val, 6),
        "p_emp": round(p_emp, 6),
        "significant_0p005": bool(p_emp <= 0.01 and z_val >= 3.5),
    }


def compute_a2_chiral_vrm_balance(
    dmic_4ch: np.ndarray,
    *,
    fs: int = 48000,
    chiral_band_hz: tuple[float, float] = (18500.0, 22200.0),
    vrm_band_hz: tuple[float, float] = (12000.0, 22000.0),
    bezel_spacing_m: float = 0.134,
    c_sound_m_s: float = 343.0,
    n_fft: int = 1024,
    n_surr: int = 99,
    seed: int = 42,
    auth_gate: AudioAuthorizationGate | None = None,
    allow_offline_array: bool = False,
) -> dict[str, Any]:
    """Lens A2 (Mode-2 Opt-In): 18.5-22.2 kHz acoustic chirality + CPU/GPU VRM lateral TDOA."""
    _check_dmic_permission(auth_gate, allow_offline_array)
    arr = np.asarray(dmic_4ch, dtype=np.float64)
    require_ok(arr.ndim == 2 and arr.shape[1] >= 2, "ERR_BAD_DMIC_SHAPE", f"Expected (N, >=2) DMIC array, got {arr.shape}")
    require_ok(arr.shape[0] >= 4 * n_fft, "ERR_DMIC_TOO_SHORT", f"Need >= {4 * n_fft} samples, got {arr.shape[0]}")
    require_ok(bool(np.all(np.isfinite(arr))), "ERR_NONFINITE", "dmic_4ch contains NaN or Inf")

    ch_left = arr[:, 0]
    ch_right = arr[:, -1]
    win = np.hanning(n_fft)
    step = n_fft // 2
    n_seg = 1 + (arr.shape[0] - n_fft) // step

    f_l = np.lib.stride_tricks.as_strided(ch_left, shape=(n_seg, n_fft), strides=(ch_left.strides[0] * step, ch_left.strides[0]))
    f_r = np.lib.stride_tricks.as_strided(ch_right, shape=(n_seg, n_fft), strides=(ch_right.strides[0] * step, ch_right.strides[0]))
    zl = np.fft.rfft((f_l - np.mean(f_l, axis=1, keepdims=True)) * win[None, :], axis=1)
    zr = np.fft.rfft((f_r - np.mean(f_r, axis=1, keepdims=True)) * win[None, :], axis=1)

    freqs = np.fft.rfftfreq(n_fft, d=1.0 / float(fs))
    c_mask = (freqs >= chiral_band_hz[0]) & (freqs <= chiral_band_hz[1])
    require_ok(int(np.sum(c_mask)) >= 4, "ERR_EMPTY_CHIRAL_BAND", "Chiral band has < 4 FFT bins")

    s_lr = np.mean(zl[:, c_mask] * np.conj(zr[:, c_mask]), axis=0)
    p_ll = np.mean(np.abs(zl[:, c_mask]) ** 2, axis=0)
    p_rr = np.mean(np.abs(zr[:, c_mask]) ** 2, axis=0)
    coh_denom = np.sqrt(np.maximum(p_ll * p_rr, 1e-30))
    chi = np.imag(s_lr) / coh_denom
    peak_c = int(np.argmax(np.abs(chi)))
    obs_max_chi = float(np.abs(chi[peak_c]))
    obs_signed_chi = float(chi[peak_c])
    peak_chi_hz = float(freqs[c_mask][peak_c])

    # Locally median-smoothed PSD surrogates (avoids monochromatic random-phase inflation)
    psd_l = ndimage.median_filter(np.mean(np.abs(zl) ** 2, axis=0), size=9, mode="nearest")[c_mask]
    psd_r = ndimage.median_filter(np.mean(np.abs(zr) ** 2, axis=0), size=9, mode="nearest")[c_mask]
    amp_l = np.sqrt(np.maximum(psd_l, 1e-30) * 0.5)
    amp_r = np.sqrt(np.maximum(psd_r, 1e-30) * 0.5)

    rng = np.random.default_rng(seed)
    n_cbins = int(np.sum(c_mask))
    null_chi = np.empty(n_surr, dtype=np.float64)
    for idx in range(n_surr):
        sl = (rng.standard_normal((n_seg, n_cbins)) + 1j * rng.standard_normal((n_seg, n_cbins))) * amp_l[None, :]
        sr = (rng.standard_normal((n_seg, n_cbins)) + 1j * rng.standard_normal((n_seg, n_cbins))) * amp_r[None, :]
        c_surr = np.mean(sl * np.conj(sr), axis=0)
        denom_surr = np.sqrt(np.maximum(np.mean(np.abs(sl) ** 2, axis=0) * np.mean(np.abs(sr) ** 2, axis=0), 1e-30))
        chi_surr = np.abs(np.imag(c_surr)) / denom_surr
        null_chi[idx] = float(np.max(chi_surr))

    mu = float(np.mean(null_chi))
    sd = float(np.std(null_chi, ddof=1)) if n_surr > 1 else 0.0
    z_chiral = 0.0 if sd <= 1e-15 else (obs_max_chi - mu) / sd
    ge_cnt = int(np.sum(null_chi >= obs_max_chi - 1e-15))
    p_emp = float(1 + ge_cnt) / float(1 + n_surr)

    # Sub-sample bandpass GCC-PHAT lateral TDOA across bezel spacing
    v_mask = (freqs >= vrm_band_hz[0]) & (freqs <= vrm_band_hz[1])
    cross_vrm = np.mean(zl * np.conj(zr), axis=0)
    phat = np.zeros_like(cross_vrm)
    phat[v_mask] = cross_vrm[v_mask] / np.maximum(np.abs(cross_vrm[v_mask]), 1e-30)

    interp = 8
    n_pad = interp * n_fft
    cc = np.fft.irfft(phat, n=n_pad)
    cc_shifted = np.fft.fftshift(cc)
    lags_sec = (np.arange(n_pad) - (n_pad // 2)) / float(fs * interp)

    tau_bound = float(bezel_spacing_m) / float(c_sound_m_s) * 1.15
    valid_tau = np.flatnonzero(np.abs(lags_sec) <= tau_bound)
    sub_cc = cc_shifted[valid_tau]
    best_local = int(np.argmax(sub_cc))
    best_global = int(valid_tau[best_local])

    # Parabolic 3-point sub-bin refinement
    delta = 0.0
    if 0 < best_global < n_pad - 1:
        y0 = float(cc_shifted[best_global - 1])
        y1 = float(cc_shifted[best_global])
        y2 = float(cc_shifted[best_global + 1])
        denom_p = y0 - 2.0 * y1 + y2
        if abs(denom_p) > 1e-18:
            delta = max(-0.5, min(0.5, 0.5 * (y0 - y2) / denom_p))

    # In numpy.fft conventions, if left leads right by tau > 0 (x_r(t) = x_l(t - tau)),
    # Z_l * conj(Z_r) = |Z_l|^2 * exp(+i omega tau), whose irfft(exp(+i 2pi k d / N)) peaks at n = -d.
    # Therefore tau_left_leads_right_s = -peak_lag_s: positive => left (CPU VRM) closer; negative => right (GPU VRM) closer.
    peak_lag_s = (float(best_global - (n_pad // 2)) + delta) / float(fs * interp)
    tau_left_leads_s = -peak_lag_s
    tau_us = tau_left_leads_s * 1e6
    # Lateral displacement from array midpoint (+cm toward right/GPU VRM, -cm toward left/CPU VRM)
    lateral_offset_cm = -0.5 * float(c_sound_m_s) * tau_left_leads_s * 100.0
    dominant_rail = "GPU_VRM_RIGHT" if lateral_offset_cm > 0.5 else ("CPU_VRM_LEFT" if lateral_offset_cm < -0.5 else "BALANCED_MIDLINE")

    return {
        "lens": "A2_chiral_vrm_balance",
        "max_abs_chirality": round(obs_max_chi, 6),
        "signed_peak_chirality": round(obs_signed_chi, 6),
        "peak_chirality_hz": round(peak_chi_hz, 2),
        "z_chiral": round(z_chiral, 6),
        "p_emp": round(p_emp, 6),
        "tdoa_left_leads_right_us": round(tau_us, 3),
        "lateral_vrm_offset_cm": round(lateral_offset_cm, 4),
        "dominant_vrm_rail": dominant_rail,
        "significant_0p005": bool(p_emp <= 0.01 and z_chiral >= 3.5),
    }


def extract_ultrasonic_envelope(
    dmic_wave: np.ndarray,
    *,
    fs: int = 48000,
    band_hz: tuple[float, float] = (15000.0, 22000.0),
    bin_ms: float = 1.0,
    auth_gate: AudioAuthorizationGate | None = None,
    allow_offline_array: bool = False,
) -> np.ndarray:
    """Extract 1 ms RMS ultrasonic envelope in [15, 22] kHz for Mode-2 A5-80ms precursor analysis."""
    _check_dmic_permission(auth_gate, allow_offline_array)
    x = _clean_1d(dmic_wave, "dmic_envelope_input", min_len=1024)
    sos = signal.butter(4, [band_hz[0] / (0.5 * fs), band_hz[1] / (0.5 * fs)], btype="bandpass", output="sos")
    filtered = signal.sosfiltfilt(sos, x)
    win_samples = max(8, int(round(float(fs) * float(bin_ms) / 1000.0)))
    n_bins = x.shape[0] // win_samples
    require_ok(n_bins >= 64, "ERR_ENVELOPE_TOO_SHORT", f"Need >= 64 envelope bins, got {n_bins}")
    trimmed = filtered[: n_bins * win_samples].reshape(n_bins, win_samples)
    return np.sqrt(np.mean(trimmed * trimmed, axis=1) + 1e-24)


# =============================================================================
# Read-Only Mode-1 Linux Hardware Telemetry Readers (Never Called in Unit Tests)
# =============================================================================


class RaplSysfsReader:
    """Safe read-only intel-rapl sysfs energy-counter reader (Mode 1, zero mic/camera)."""

    def __init__(self, powercap_root: Path = Path("/sys/class/powercap")) -> None:
        validate_endpoint_path(powercap_root, auth_gate=None)
        self.powercap_root = powercap_root
        self._domains: dict[str, tuple[Path, int]] = {}
        self._last_energy_uj: dict[str, int] = {}
        self._last_mono: float | None = None

    def discover(self) -> list[str]:
        if not self.powercap_root.is_dir():
            return []
        found: dict[str, tuple[Path, int]] = {}
        for d in sorted(self.powercap_root.glob("intel-rapl:*")):
            if d.is_symlink():
                continue
            name_file = d / "name"
            energy_file = d / "energy_uj"
            max_file = d / "max_energy_range_uj"
            if name_file.is_file() and energy_file.is_file():
                try:
                    raw_name = name_file.read_text(encoding="utf-8").strip().lower()
                    max_uj = int(max_file.read_text(encoding="utf-8").strip()) if max_file.is_file() else (1 << 32)
                    key = (
                        "psys_w"
                        if "psys" in raw_name
                        else "pkg_w"
                        if raw_name.startswith("package")
                        else "core_w"
                        if raw_name == "core"
                        else "uncore_w"
                        if raw_name == "uncore"
                        else f"rapl_{raw_name}_w"
                    )
                    found[key] = (energy_file, max_uj)
                except OSError:
                    continue
        self._domains = found
        return sorted(found.keys())

    def sample_watts(self, clock_fn: Callable[[], float] = time.monotonic) -> dict[str, float]:
        if not self._domains:
            self.discover()
        now_m = float(clock_fn())
        cur_uj: dict[str, int] = {}
        for key, (efile, _) in self._domains.items():
            cur_uj[key] = int(efile.read_text(encoding="utf-8").strip())
        if self._last_mono is None:
            self._last_mono = now_m
            self._last_energy_uj = cur_uj
            return {k: 0.0 for k in cur_uj}
        dt = max(now_m - self._last_mono, 1e-6)
        watts: dict[str, float] = {}
        for key, val in cur_uj.items():
            prev = self._last_energy_uj.get(key, val)
            _, max_uj = self._domains[key]
            delta_uj = val - prev
            if delta_uj < 0:
                delta_uj += max_uj
            watts[key] = float(delta_uj) * 1e-6 / dt
        self._last_mono = now_m
        self._last_energy_uj = cur_uj
        return watts


def query_proc_irq_and_cpu_khz(
    proc_stat_path: Path = Path("/proc/stat"),
    cpufreq_glob_root: Path = Path("/sys/devices/system/cpu"),
) -> dict[str, float | int]:
    """Read Mode-1 non-acoustic OS IRQ / context-switch counters and mean CPU clock kHz."""
    validate_endpoint_path(proc_stat_path, auth_gate=None)
    validate_endpoint_path(cpufreq_glob_root, auth_gate=None)
    intr_total = 0
    ctxt_total = 0
    if proc_stat_path.is_file():
        for line in proc_stat_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("intr "):
                parts = line.split()
                if len(parts) >= 2:
                    intr_total = int(parts[1])
            elif line.startswith("ctxt "):
                parts = line.split()
                if len(parts) >= 2:
                    ctxt_total = int(parts[1])
    khz_vals: list[float] = []
    if cpufreq_glob_root.is_dir():
        for fpath in sorted(cpufreq_glob_root.glob("cpu[0-9]*/cpufreq/scaling_cur_freq")):
            try:
                khz_vals.append(float(fpath.read_text(encoding="utf-8").strip()))
            except OSError:
                continue
    mean_khz = float(np.mean(khz_vals)) if khz_vals else 0.0
    return {
        "intr_total": intr_total,
        "ctxt_total": ctxt_total,
        "mean_cpu_clock_khz": round(mean_khz, 2),
    }


def query_nvidia_smi_once(timeout_sec: float = 2.0) -> dict[str, float | int]:
    """Read single GPU power/clock/throttle sample via list-argv nvidia-smi (no shell=True)."""
    cmd = [
        "nvidia-smi",
        "--query-gpu=power.draw,clocks.current.sm,temperature.gpu,clocks_event_reasons.sw_power_cap,clocks_event_reasons.hw_thermal_slowdown",
        "--format=csv,noheader,nounits",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec, check=False)
    require_ok(proc.returncode == 0, "ERR_NVIDIA_SMI_FAILED", proc.stderr.strip() or "nvidia-smi returned non-zero")
    line = proc.stdout.strip().splitlines()[0]
    parts = [p.strip() for p in line.split(",")]
    require_ok(len(parts) >= 5, "ERR_NVIDIA_SMI_PARSE", f"Unexpected nvidia-smi CSV: {line!r}")
    sw_cap = 1 if parts[3].lower() == "active" else 0
    hw_therm = 1 if parts[4].lower() == "active" else 0
    return {
        "gpu_power_w": float(parts[0]),
        "sm_clock_mhz": float(parts[1]),
        "gpu_temp_c": float(parts[2]),
        "sw_power_cap_active": sw_cap,
        "hw_thermal_slowdown_active": hw_therm,
    }


# =============================================================================
# Unified SiliSense Trace Profiler
# =============================================================================


class SiliSenseProfiler:
    """Unified Mode-1 / Mode-2 profiler for HoloSphere & standalone silicon traces."""

    def __init__(
        self,
        *,
        mode: str = "telemetry-only",
        auth_gate: AudioAuthorizationGate | None = None,
        n_iaaft: int = 199,
        n_shifts: int = 500,
        seed: int = 42,
    ) -> None:
        require_ok(
            mode in ("telemetry-only", "dmic-authorized"),
            "ERR_UNKNOWN_MODE",
            f"mode must be 'telemetry-only' or 'dmic-authorized', got {mode!r}",
        )
        if mode == "dmic-authorized":
            require_perm(
                auth_gate is not None,
                "ERR_DMIC_UNAUTHORIZED",
                "mode='dmic-authorized' requires an active AudioAuthorizationGate",
            )
            if auth_gate is not None:
                auth_gate.verify_active()
        else:
            require_perm(
                auth_gate is None,
                "ERR_MODE_GATE_CONFLICT",
                "Do not pass AudioAuthorizationGate when mode='telemetry-only'",
            )
        self.mode = mode
        self.auth_gate = auth_gate
        self.n_iaaft = int(n_iaaft)
        self.n_shifts = int(n_shifts)
        self.seed = int(seed)

    def profile_trace(
        self,
        trace: dict[str, Any],
        *,
        allow_offline_dmic: bool = False,
    ) -> dict[str, Any]:
        """Compute all authorized non-textbook observables on a telemetry trace dict."""
        for key in trace:
            if _CAMERA_PATH_RE.search(str(key)):
                raise SiliSensePermissionError(
                    "ERR_CAMERA_FORBIDDEN",
                    f"Camera field {key!r} is forbidden in SiliSense traces",
                )

        dt_ms = float(trace.get("dt_ms", 5.0))
        gpu_w = _clean_1d(trace["gpu_power_w"], "gpu_power_w", min_len=64)
        uncore_w = _clean_1d(trace["uncore_w"], "uncore_w", min_len=64)
        slow_resp = _clean_1d(trace.get("slow_throttle_or_psys", trace.get("psys_w", gpu_w)), "slow_response", min_len=64)
        fast_rail = _clean_1d(trace.get("fast_power_w", gpu_w + uncore_w), "fast_power_w", min_len=64)

        a3_res = compute_a3_time_reversal_asymmetry(
            gpu_w,
            dt_ms=dt_ms,
            lags=(1, 2, 3),
            n_iaaft=self.n_iaaft,
            seed=self.seed,
        )
        a5_res = compute_a5_precursor_lead_lag(
            fast_rail,
            slow_resp,
            dt_ms=dt_ms,
            max_lag_ms=max(50.0, 40.0 * dt_ms),
            n_shifts=self.n_shifts,
            seed=self.seed + 1,
        )
        a7_res = compute_a7_nonlinear_uncore_copula_mi(
            uncore_w,
            gpu_w,
            max_linear_lag=5,
            n_iaaft=self.n_iaaft,
            seed=self.seed + 2,
        )

        result: dict[str, Any] = {
            "prereg_id": PREREG_S115_ID,
            "mode": self.mode,
            "dmic_authorized": bool(self.mode == "dmic-authorized"),
            "dt_ms": round(dt_ms, 6),
            "mean_gpu_power_w": round(float(np.mean(gpu_w)), 4),
            "std_gpu_power_w": round(float(np.std(gpu_w, ddof=1)), 4),
            "mean_uncore_w": round(float(np.mean(uncore_w)), 4),
            "observables": {
                "A3_telemetry": a3_res,
                "A5_precursor": a5_res,
                "A7_uncore_copula_mi": a7_res,
            },
        }

        has_dmic = ("dmic_4ch_48k" in trace) or ("dmic_mono_48k" in trace)
        if has_dmic:
            if self.mode != "dmic-authorized" and not allow_offline_dmic:
                raise SiliSensePermissionError(
                    "ERR_DMIC_DISABLED_DEFAULT",
                    "Trace contains DMIC audio arrays while profiler is in Mode 1 ('telemetry-only')",
                )
            fs = int(trace.get("dmic_fs_hz", 48000))
            if "dmic_4ch_48k" in trace:
                dmic_4ch = np.asarray(trace["dmic_4ch_48k"], dtype=np.float64)
                dmic_mono = dmic_4ch[:, 0]
            else:
                dmic_mono = _clean_1d(trace["dmic_mono_48k"], "dmic_mono_48k", min_len=2048)
                dmic_4ch = None

            a1_res = compute_a1_ultrasonic_bicoherence(
                dmic_mono,
                fs=fs,
                n_iaaft=min(self.n_iaaft, 99),
                seed=self.seed + 3,
                auth_gate=self.auth_gate,
                allow_offline_array=allow_offline_dmic,
            )
            a3_dmic = compute_a3_time_reversal_asymmetry(
                dmic_mono[: min(dmic_mono.shape[0], 8192)],
                dt_ms=1000.0 / float(fs),
                lags=(1, 2, 3),
                n_iaaft=min(self.n_iaaft, 99),
                seed=self.seed + 4,
            )
            result["observables"]["A1_ultrasonic_bicoherence"] = a1_res
            result["observables"]["A3_dmic_62us"] = a3_dmic

            if dmic_4ch is not None:
                result["observables"]["A2_chiral_vrm_balance"] = compute_a2_chiral_vrm_balance(
                    dmic_4ch,
                    fs=fs,
                    n_surr=min(self.n_iaaft, 99),
                    seed=self.seed + 5,
                    auth_gate=self.auth_gate,
                    allow_offline_array=allow_offline_dmic,
                )

        p_family = [
            float(result["observables"]["A3_telemetry"]["p_holm"]),
            float(result["observables"]["A5_precursor"]["p_circ"]),
            float(result["observables"]["A7_uncore_copula_mi"]["p_emp"]),
        ]
        if "A1_ultrasonic_bicoherence" in result["observables"]:
            p_family.append(float(result["observables"]["A1_ultrasonic_bicoherence"]["p_emp"]))
        if "A2_chiral_vrm_balance" in result["observables"]:
            p_family.append(float(result["observables"]["A2_chiral_vrm_balance"]["p_emp"]))

        holm_family = holm_bonferroni(p_family)
        result["min_family_holm_p"] = round(min(holm_family), 6)
        result["any_non_textbook_significant_0p005"] = bool(min(holm_family) < 0.005)
        return result


# =============================================================================
# Synthetic Reference Trace Generator & Deterministic CLI Self-Check
# =============================================================================


def make_synthetic_workload_trace(
    kind: str,
    *,
    n_samples: int = 400,
    dt_ms: float = 5.0,
    seed: int = 42,
    target_mean_gpu_w: float = 95.0,
) -> dict[str, Any]:
    """Generate deterministic Mode-1 traces for 'eager_microkernel' vs 'fused_holosphere'."""
    require_ok(
        kind in ("eager_microkernel", "fused_holosphere", "colored_null"),
        "ERR_BAD_SYNTH_KIND",
        f"Unknown synthetic trace kind {kind!r}",
    )
    rng = np.random.default_rng(seed)
    t_idx = np.arange(n_samples, dtype=np.float64)

    # Colored AR(1) uncore ring-bus baseline
    uncore = np.zeros(n_samples, dtype=np.float64)
    eps_u = rng.standard_normal(n_samples)
    for t in range(1, n_samples):
        uncore[t] = 0.70 * uncore[t - 1] + eps_u[t]

    fast_spikes = np.zeros(n_samples, dtype=np.float64)

    if kind == "eager_microkernel":
        # Aperiodic broadband micro-kernel ramp-up + sharp launch-boundary cliff (produces strong A3 shockwave asymmetry)
        saw = np.zeros(n_samples, dtype=np.float64)
        pos = 0
        while pos < n_samples:
            period = int(rng.integers(5, 11))
            end_p = min(n_samples, pos + period)
            span = end_p - pos
            if span >= 2:
                ramp = np.linspace(-1.0, 1.0, span, dtype=np.float64)
                saw[pos:end_p] = ramp
            pos = end_p
        # Purely nonlinear uncore ring-bus contention bursts (zero linear corr, high A7 copula MI)
        nl_contention = 1.45 * ((uncore * uncore) - float(np.mean(uncore * uncore)))
        gpu_raw = 9.5 * saw + nl_contention + 0.45 * rng.standard_normal(n_samples)
        gpu_w = target_mean_gpu_w + (gpu_raw - float(np.mean(gpu_raw)))
        # Aperiodic precursor ramps leading SwPowerCap/psys onset by 16 samples (-80 ms at 5 ms/sample)
        slow_resp = 105.0 + 0.30 * rng.standard_normal(n_samples)
        burst_t = 28
        while burst_t < n_samples - 28:
            fast_spikes[burst_t : burst_t + 4] += np.array([5.0, 11.0, 17.0, 17.0], dtype=np.float64)
            slow_resp[burst_t + 16 : burst_t + 22] += np.array([4.5, 9.5, 14.5, 14.5, 12.0, 8.0], dtype=np.float64)
            burst_t += int(rng.integers(33, 69))
    elif kind == "fused_holosphere":
        # Smooth warp-resident execution: symmetric fluctuations + minimal nonlinear uncore contention
        ar_gpu = np.zeros(n_samples, dtype=np.float64)
        eps_g = rng.standard_normal(n_samples)
        for t in range(1, n_samples):
            ar_gpu[t] = 0.65 * ar_gpu[t - 1] + 1.8 * eps_g[t]
        gpu_w = target_mean_gpu_w + (ar_gpu - float(np.mean(ar_gpu))) + 0.35 * uncore
        gpu_w = target_mean_gpu_w + (gpu_w - float(np.mean(gpu_w)))
        slow_resp = 105.0 + 0.5 * rng.standard_normal(n_samples)
    else:
        # Pure linear multi-lag AR(1) null (must trigger ZERO false positives on A3, A5, A7)
        ar_gpu = np.zeros(n_samples, dtype=np.float64)
        eps_g = rng.standard_normal(n_samples)
        for t in range(2, n_samples):
            ar_gpu[t] = 0.80 * ar_gpu[t - 1] + 1.5 * uncore[t] - 0.9 * uncore[t - 1] + eps_g[t]
        gpu_w = target_mean_gpu_w + (ar_gpu - float(np.mean(ar_gpu)))
        slow_resp = np.zeros(n_samples, dtype=np.float64)
        eps_s = rng.standard_normal(n_samples)
        for t in range(1, n_samples):
            slow_resp[t] = 0.82 * slow_resp[t - 1] + eps_s[t]
        slow_resp = 105.0 + slow_resp

    return {
        "dt_ms": dt_ms,
        "gpu_power_w": gpu_w,
        "uncore_w": 8.0 + uncore,
        "fast_power_w": gpu_w + 8.0 + uncore + fast_spikes,
        "slow_throttle_or_psys": slow_resp,
    }


def _run_deterministic_demo() -> dict[str, Any]:
    profiler = SiliSenseProfiler(mode="telemetry-only", n_iaaft=99, n_shifts=200, seed=42)
    eager = profiler.profile_trace(make_synthetic_workload_trace("eager_microkernel", seed=42))
    fused = profiler.profile_trace(make_synthetic_workload_trace("fused_holosphere", seed=42))
    null_prof = profiler.profile_trace(make_synthetic_workload_trace("colored_null", seed=42))
    return {
        "prereg_id": PREREG_S115_ID,
        "default_mode": profiler.mode,
        "camera_policy": "ERR_CAMERA_FORBIDDEN",
        "eager_a3_z": eager["observables"]["A3_telemetry"]["z_iaaft"],
        "fused_a3_z": fused["observables"]["A3_telemetry"]["z_iaaft"],
        "eager_a5_lead_ms": eager["observables"]["A5_precursor"]["peak_precursor_lag_ms"],
        "eager_a5_p_circ": eager["observables"]["A5_precursor"]["p_circ"],
        "eager_a7_z": eager["observables"]["A7_uncore_copula_mi"]["z_iaaft"],
        "fused_a7_z": fused["observables"]["A7_uncore_copula_mi"]["z_iaaft"],
        "colored_null_any_fp_0p005": null_prof["any_non_textbook_significant_0p005"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SiliSense Non-Textbook Silicon Physics Profiler (PREREG-S115)")
    parser.add_argument("--profile-json", type=Path, default=None, help="Offline JSON telemetry trace to profile")
    parser.add_argument("--enable-dmic-authorized", action="store_true", help="Opt-in Mode 2 DMIC authorization flag")
    parser.add_argument("--authorize-audio-window-sec", type=float, default=None, help="Bounded audio window in (0, 300] sec")
    parser.add_argument("--pi-authorization-token", type=str, default=None, help="Explicit PI authorization token")
    parser.add_argument("--demo-synthetic", action="store_true", help="Run deterministic CPU-only synthetic self-check")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args(argv)

    gate: AudioAuthorizationGate | None = None
    mode = "telemetry-only"
    if args.enable_dmic_authorized or args.authorize_audio_window_sec is not None or args.pi_authorization_token is not None:
        gate = AudioAuthorizationGate.create(
            enable_dmic_authorized=bool(args.enable_dmic_authorized),
            authorize_audio_window_sec=args.authorize_audio_window_sec,
            pi_authorization_token=args.pi_authorization_token,
        )
        mode = "dmic-authorized"

    if args.profile_json is not None:
        validate_endpoint_path(args.profile_json, auth_gate=gate)
        raw = json.loads(args.profile_json.read_text(encoding="utf-8"))
        profiler = SiliSenseProfiler(mode=mode, auth_gate=gate)
        out = profiler.profile_trace(raw, allow_offline_dmic=False)
        print(json.dumps(out, sort_keys=True, indent=2))
        return 0

    summary = _run_deterministic_demo()
    if args.json or args.demo_synthetic or argv is None:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
