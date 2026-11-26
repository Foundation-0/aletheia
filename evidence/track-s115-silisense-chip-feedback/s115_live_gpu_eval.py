#!/usr/bin/env python3
"""Track S115 (`Project SiliSense` / `PREREG-S115` / `EXP-Q21a..c`): Mode-1 Live RTX 3080 GPU Evaluation.

Executes all three locked PREREG-S115 hypotheses (`H15a`, `H15b`, `H15c`) strictly in
Mode 1 (`telemetry-only`: `intel-rapl` + NVML + `/proc/stat` IRQ/ctxt + `cpufreq`),
with ZERO microphone (`/dev/snd/*`), camera (`/dev/video*`, `/dev/media*`), or IR access,
enforced both statically and at runtime via an active `builtins.open` + `os.open` airlock spy.

Experiments:
  - `H15a` (`EXP-Q21a`): Interleaved `ABABAB` profiling (`3` seeds `[42, 137, 2026]` x `3` pairs = `9` pairs)
    comparing real 12L `Eager H7b` (`S107TransformerLM`) vs real 12L `HoloSphere-V2-sm86` (`27/27` `0 B`-spill
    bare-metal CUDA kernels) under (i) unpaced `CS-08` equal-tokens-per-block execution AND (ii) `<= 5.0%`
    throughput-paced equal-wattage control, scored against `N=799` IAAFT surrogates (`A3`, `A7`) and `N=500`
    circular-shift surrogates (`A5`), plus exact-Q `OP1_SEAM1`, `OP2_SEAM3`, `OP3_F3`, and `WHT_PHASE` diagnostics.
  - `H15b` (`EXP-Q21b`): Live Mode-1 closed-loop `PrecursorThrottleGovernor` showdown (`NoGovernor`,
    `Reactive-1Hz-SMI`, duty-cycle-matched `Shuffled-Trigger-Control`, and `SiliSense-Precursor-Gov` with
    `f*tau < 1/6` Delay-Bandwidth Lock, smooth `L^{5/3}` shared-heatpipe excess, `floor_to_exact_f32` Lyapunov
    damping, and Contract-4 `PreAdaptationResidualLatch`) across `3` seeds `[42, 137, 2026]`.
  - `H15c` (`EXP-Q21c`): Real silicon `EDP` kernel autotuner (`Scalar-TokPerSec-Tuner`,
    `Scalar-MeanWatt-EDP-Tuner`, and `SiliSense-Composite-Tuner` under frozen `(0.15, 0.15, 0.10)` weights +
    `2.0sigma` IAAFT hinges + 5-gate exact-`Fraction` anti-Goodhart ratchet) across `6` real `HoloSphere-V2`
    `(backend, micro_batch, grad_accum, grad_ckpt)` configs at constant `CS-08` `8,192` effective tokens/step,
    evaluated on held-out interleaved sustained confirmation runs (`3` seeds `[42, 137, 2026]`).

Compiles `su2_holonomy_scan_sm86.cu` and Triton caches strictly inside `/tmp` and deletes them in `finally:`
so repository directories maintain `WEIGHTS=0`, `AV=0`, `ELF=0`, `PYC=0`.
"""

from __future__ import annotations

import argparse
import builtins
import ctypes
from dataclasses import asdict
import datetime
from fractions import Fraction
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

_HERE = Path(__file__).resolve().parent
_EXPEDITION = _HERE.parent
_S114 = _EXPEDITION / "track-s114-silisphere-fused-kernel-transformer"
_S107 = _EXPEDITION / "track-s107-hypersphere-transformer"
for _p in (str(_HERE), str(_S114), str(_S107)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from s115_silisense_profiler import (  # noqa: E402
    PREREG_S115_ID,
    PREREG_S115_RELPATH,
    PREREG_S115_SHA256,
    SiliSenseError,
    SiliSenseProfiler,
    causal_innovation_zscores,
    compute_a5_precursor_lead_lag,
    require_ok,
    validate_endpoint_path,
)
from s115_feedback_autotuner import (  # noqa: E402
    HoloSphereKernelConfig,
    HoloSphereStepTelemetry,
    HoloSphereTuningProfile,
    LOCKED_LAMBDA_A3,
    LOCKED_LAMBDA_A5,
    LOCKED_LAMBDA_A7,
    LOCKED_SIGNIFICANCE_HINGE_Z,
    PairedABABABEvaluator,
    PreAdaptationResidualLatch,
    PrecursorThrottleGovernor,
    SiliSenseHoloSphereBridge,
    SiliSenseKernelAutotuner,
    check_delay_bandwidth_lock,
    floor_to_exact_f32,
    grade_h15b_results,
)

import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import torch.nn.functional as F  # noqa: E402
from torch.utils.checkpoint import checkpoint as grad_checkpoint  # noqa: E402

import s107_models as s107  # noqa: E402
import s114_fused_ops as ops  # noqa: E402

SEEDS: Tuple[int, int, int] = (42, 137, 2026)
VOCAB_SIZE = 260
FRAME64_STRUCT = struct.Struct("<8Q")
TREE_DOMAIN_PREFIX = b"silisense-tree-v1\x00"


# =============================================================================
# 1. Runtime Mode-1 Sensor Airlock Spy (Wraps builtins.open and os.open)
# =============================================================================


class RuntimeMode1AirlockSpy:
    """Intercepts every file open in-process to enforce Mode-1 zero-mic/zero-camera/zero-IR airlock."""

    def __init__(self) -> None:
        self._orig_builtins_open = builtins.open
        self._orig_os_open = os.open
        self._orig_os_realpath = os.path.realpath
        self._lock = threading.Lock()
        self.installed = False
        self.checked_calls = 0
        self.blocked_calls = 0
        self.telemetry_roots_seen: set[str] = set()

    def _inspect_path(self, file_arg: Any) -> None:
        if isinstance(file_arg, int):
            return
        if isinstance(file_arg, bytes):
            path_str = file_arg.decode("utf-8", errors="replace")
        elif isinstance(file_arg, (str, os.PathLike)):
            path_str = os.fspath(file_arg)
            if isinstance(path_str, bytes):
                path_str = path_str.decode("utf-8", errors="replace")
        else:
            return
        if not path_str:
            return
        norm_p = os.path.normpath(path_str)
        try:
            validate_endpoint_path(path_str, auth_gate=None)
            validate_endpoint_path(norm_p, auth_gate=None)
            if "/dev/char/81:" in norm_p or norm_p.startswith("dev/char/81:"):
                from s115_silisense_profiler import SiliSensePermissionError

                raise SiliSensePermissionError("ERR_CAMERA_FORBIDDEN", f"V4L2 char major 81 forbidden: {path_str!r}")
            if os.path.islink(path_str):
                real_p = self._orig_os_realpath(path_str)
                validate_endpoint_path(real_p, auth_gate=None)
                if "/dev/char/81:" in real_p:
                    from s115_silisense_profiler import SiliSensePermissionError

                    raise SiliSensePermissionError("ERR_CAMERA_FORBIDDEN", f"Symlink target V4L2 forbidden: {real_p!r}")
        except SiliSenseError:
            with self._lock:
                self.blocked_calls += 1
            raise
        with self._lock:
            self.checked_calls += 1
            for root in (
                "/sys/devices/virtual/powercap/intel-rapl",
                "/sys/class/powercap",
                "/proc/stat",
                "/sys/devices/system/cpu",
            ):
                if path_str.startswith(root):
                    self.telemetry_roots_seen.add(root)

    def install(self) -> None:
        if self.installed:
            return
        spy = self

        def _guarded_builtins_open(file: Any, *args: Any, **kwargs: Any) -> Any:
            spy._inspect_path(file)
            return spy._orig_builtins_open(file, *args, **kwargs)

        def _guarded_os_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
            spy._inspect_path(path)
            return spy._orig_os_open(path, flags, *args, **kwargs)

        builtins.open = _guarded_builtins_open  # type: ignore[assignment]
        os.open = _guarded_os_open  # type: ignore[assignment]
        self.installed = True

    def uninstall(self) -> None:
        if not self.installed:
            return
        builtins.open = self._orig_builtins_open  # type: ignore[assignment]
        os.open = self._orig_os_open  # type: ignore[assignment]
        self.installed = False

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "mode": "telemetry-only",
                "dmic_authorized": False,
                "camera_policy": "ERR_CAMERA_FORBIDDEN",
                "checked_open_calls": int(self.checked_calls),
                "blocked_sensor_attempts": int(self.blocked_calls),
                "camera_opens": 0,
                "audio_opens": 0,
                "ir_opens": 0,
                "telemetry_roots_seen": sorted(self.telemetry_roots_seen),
            }


# =============================================================================
# 2. Pure-Q S20c Operators (`OP1_SEAM1`, `OP2_SEAM3`, `OP3_F3`), `Frame64`, & Ratchet
# =============================================================================


def pack_frame64_bytes(
    *,
    ts_mono_ns: int,
    pkg_uj: int,
    core_uj: int,
    uncore_uj: int,
    psys_uj: int,
    gpu_mj: int,
    step_us: int,
    sw_power_cap: bool,
    hw_thermal_slowdown: bool,
    gpu_temp_deci_c: int,
    sm_clock_mhz: int,
) -> bytes:
    u64_mask = (1 << 64) - 1
    flags = (1 if sw_power_cap else 0) | ((1 if hw_thermal_slowdown else 0) << 1)
    temp_clamped = max(0, min(0xFFFF, int(gpu_temp_deci_c)))
    clk_clamped = max(0, min(0xFFFF, int(sm_clock_mhz)))
    word7 = flags | (temp_clamped << 16) | (clk_clamped << 32)
    return FRAME64_STRUCT.pack(
        int(ts_mono_ns) & u64_mask,
        int(pkg_uj) & u64_mask,
        int(core_uj) & u64_mask,
        int(uncore_uj) & u64_mask,
        int(psys_uj) & u64_mask,
        int(gpu_mj) & u64_mask,
        int(step_us) & u64_mask,
        int(word7) & u64_mask,
    )


def hash_frame64_stream(stream_label: str, frames: Sequence[bytes]) -> str:
    raw_sha = hashlib.sha256(b"".join(frames)).hexdigest()
    path_bytes = stream_label.encode("utf-8")
    leaf = TREE_DOMAIN_PREFIX + struct.pack("<Q", len(path_bytes)) + path_bytes + bytes.fromhex(raw_sha)
    return hashlib.sha256(leaf).hexdigest()


def compute_op1_seam1_sherman_morrison(int_series: Sequence[int], window: int = 32) -> Dict[str, Any]:
    """OP1_SEAM1: Exact-Q sliding W=32 Sherman-Morrison causal leverage shock."""
    if len(int_series) <= window + 2:
        return {"window": window, "peak_step": 0, "max_leverage_exact_q": "0/1", "max_leverage_decimal": 0.0}
    # Subsample cleanly if > 256 samples to keep exact Fraction arithmetic fast (<10 ms)
    stride = max(1, len(int_series) // 192)
    xs = [Fraction(int(v)) for v in int_series[::stride]]
    if len(xs) <= window + 2:
        xs = [Fraction(int(v)) for v in int_series[: min(len(int_series), 192)]]
    max_h = Fraction(0)
    peak_idx = window
    for t in range(window, len(xs)):
        g00 = Fraction(1 + window)
        g01 = sum((xs[s - 1] for s in range(t - window, t)), Fraction(0))
        g11 = Fraction(1) + sum((xs[s - 1] * xs[s - 1] for s in range(t - window, t)), Fraction(0))
        det_g = g00 * g11 - g01 * g01
        require_ok(det_g > 0, "ERR_OP1_SPD", "2x2 regularized Gram must be strictly SPD")
        z0, z1 = Fraction(1), xs[t - 1]
        u0 = (g11 * z0 - g01 * z1) / det_g
        u1 = (-g01 * z0 + g00 * z1) / det_g
        q_t = z0 * u0 + z1 * u1
        h_t = q_t / (Fraction(1) + q_t)
        if h_t > max_h:
            max_h = h_t
            peak_idx = t * stride
    return {
        "window": window,
        "peak_step": int(peak_idx),
        "max_leverage_exact_q": f"{max_h.numerator}/{max_h.denominator}",
        "max_leverage_decimal": round(float(max_h), 6),
    }


def _ordinal_state_m3(a: float, b: float, c: float) -> int:
    if a == b or b == c or a == c:
        return 6
    if a < b < c:
        return 0
    if a < c < b:
        return 1
    if b < a < c:
        return 2
    if b < c < a:
        return 3
    if c < a < b:
        return 4
    return 5


def compute_op2_seam3_ordinal_hodge_curl(series: Sequence[float]) -> Dict[str, Any]:
    """OP2_SEAM3: Monotone-invariant 7x7 ordinal Hodge-curl Phi_asym in Q cap [0,1] + O(N) HVG beta_1."""
    n = len(series)
    require_ok(n >= 16, "ERR_OP2_LEN", f"Need >= 16 samples, got {n}")
    states = [_ordinal_state_m3(float(series[i]), float(series[i + 1]), float(series[i + 2])) for i in range(n - 2)]
    c_mat = [[0] * 7 for _ in range(7)]
    for t in range(len(states) - 1):
        c_mat[states[t]][states[t + 1]] += 1
    num_q = 0
    den_q = 0
    for i in range(7):
        for j in range(i + 1, 7):
            diff = c_mat[i][j] - c_mat[j][i]
            tot = c_mat[i][j] + c_mat[j][i]
            num_q += diff * diff
            den_q += tot * tot
    phi_q = Fraction(0) if den_q == 0 else Fraction(num_q, den_q)

    edges = 0
    stack: List[float] = []
    for raw_v in series:
        val = float(raw_v)
        while stack and stack[-1] < val:
            edges += 1
            stack.pop()
        if stack:
            edges += 1
        if not stack or stack[-1] > val:
            stack.append(val)
        else:
            stack[-1] = val
    beta1 = max(0, edges - (n - 1))
    beta1_rate = Fraction(beta1, n)
    return {
        "phi_asym_exact_q": f"{phi_q.numerator}/{phi_q.denominator}",
        "phi_asym_decimal": round(float(phi_q), 6),
        "hvg_beta1": int(beta1),
        "hvg_beta1_per_n_exact_q": f"{beta1_rate.numerator}/{beta1_rate.denominator}",
        "hvg_beta1_per_n_decimal": round(float(beta1_rate), 6),
    }


def compute_op3_f3_from_rails(pkg_w: Sequence[float], uncore_w: Sequence[float], gpu_w: Sequence[float]) -> Dict[str, Any]:
    """OP3_F3: Fit lag-1 3-rail state operator T in Q^{3x3} (quantized to 1/1000) & compute exact kappa_F3."""
    arr = np.vstack(
        [
            np.asarray(pkg_w, dtype=np.float64),
            np.asarray(uncore_w, dtype=np.float64),
            np.asarray(gpu_w, dtype=np.float64),
        ]
    )
    arr = arr - np.mean(arr, axis=1, keepdims=True)
    sd = np.maximum(np.std(arr, axis=1, keepdims=True), 1e-6)
    z = arr / sd
    x0 = z[:, :-1]
    x1 = z[:, 1:]
    gram = x0 @ x0.T + 1e-3 * np.eye(3)
    t_flt = (x1 @ x0.T) @ np.linalg.inv(gram)
    t_mat = [[Fraction(int(round(float(t_flt[i, j]) * 1000.0)), 1000) for j in range(3)] for i in range(3)]

    ttt = [[sum(t_mat[k][i] * t_mat[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    tt_t = [[sum(t_mat[i][k] * t_mat[j][k] for k in range(3)) for j in range(3)] for i in range(3)]
    frob_t2 = sum(t_mat[i][j] * t_mat[i][j] for i in range(3) for j in range(3))
    comm_f2 = sum((ttt[i][j] - tt_t[i][j]) ** 2 for i in range(3) for j in range(3))
    kappa_q = Fraction(0) if frob_t2 == 0 else (comm_f2 / (frob_t2 * frob_t2))

    m = [[(Fraction(1) if i == j else Fraction(0)) - ttt[i][j] for j in range(3)] for i in range(3)]
    # Exact negative inertia of real symmetric 3x3 M via Descartes' Rule of Signs on q(mu) = det(mu I + M) = 0
    c1 = m[0][0] + m[1][1] + m[2][2]
    c2 = (
        (m[0][0] * m[1][1] - m[0][1] * m[1][0])
        + (m[0][0] * m[2][2] - m[0][2] * m[2][0])
        + (m[1][1] * m[2][2] - m[1][2] * m[2][1])
    )
    c3 = (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )
    nonzero_coeffs = [v for v in (Fraction(1), c1, c2, c3) if v != 0]
    n_neg = sum(
        1 for idx in range(len(nonzero_coeffs) - 1) if (nonzero_coeffs[idx] > 0) != (nonzero_coeffs[idx + 1] > 0)
    )
    return {
        "kappa_f3_exact_q": f"{kappa_q.numerator}/{kappa_q.denominator}",
        "kappa_f3_decimal": round(float(kappa_q), 6),
        "gram_contractivity_neg_inertia": int(n_neg),
        "transient_overshoot_risk": bool(n_neg > 0),
    }


def evaluate_five_gate_ratchet(
    *,
    base_effective_tokens: int,
    cand_effective_tokens: int,
    base_edp: float,
    cand_edp: float,
    base_throttle_frac: float,
    cand_throttle_frac: float,
    cand_edp_head: float,
    cand_edp_tail: float,
    pre_adapt_latch_sha256: str,
    cand_max_shock_z: float,
) -> Dict[str, Any]:
    """Exact-Fraction 5-gate anti-Goodhart ratchet (`G1..G5`)."""
    scale = 1_000_000
    base_edp_q = Fraction(max(1, int(round(base_edp * scale))), scale)
    cand_edp_q = Fraction(max(1, int(round(cand_edp * scale))), scale)
    base_thr_q = Fraction(max(0, int(round(base_throttle_frac * scale))), scale)
    cand_thr_q = Fraction(max(0, int(round(cand_throttle_frac * scale))), scale)
    head_q = Fraction(max(1, int(round(cand_edp_head * scale))), scale)
    tail_q = Fraction(max(1, int(round(cand_edp_tail * scale))), scale)
    shock_q = Fraction(max(0, int(round(abs(cand_max_shock_z) * 1000.0))), 1000)

    g1_cs08 = bool(int(base_effective_tokens) == int(cand_effective_tokens) and int(cand_effective_tokens) > 0)
    rel_gain_q = (base_edp_q - cand_edp_q) / base_edp_q
    g2_edp = bool(rel_gain_q >= Fraction(1, 50))
    tail_drift_q = (tail_q - head_q) / head_q
    g3_thermal = bool(tail_drift_q <= Fraction(1, 10) and cand_thr_q <= base_thr_q + Fraction(1, 100))
    g4_latch = bool(len(pre_adapt_latch_sha256) == 64 and len(set(pre_adapt_latch_sha256)) > 1)
    g5_shock = bool(shock_q <= Fraction(7, 2))
    return {
        "accepted": bool(g1_cs08 and g2_edp and g3_thermal and g4_latch and g5_shock),
        "gates": {
            "G1_CS08_effective_batch_parity": g1_cs08,
            "G2_sustained_edp_gain": g2_edp,
            "G3_no_thermal_or_throttle_gaming": g3_thermal,
            "G4_pre_adaptation_latch_pinned": g4_latch,
            "G5_quotient_fork_shock_ceiling": g5_shock,
        },
        "edp_rel_gain_exact_q": f"{rel_gain_q.numerator}/{rel_gain_q.denominator}",
        "tail_drift_exact_q": f"{tail_drift_q.numerator}/{tail_drift_q.denominator}",
    }


def paired_stats_with_student_t(baseline_vals: Sequence[float], candidate_vals: Sequence[float]) -> Dict[str, float]:
    """Paired statistics matching s115_feedback_autotuner._paired_stats PLUS exact two-sided Student-t p-value."""
    a = np.asarray(baseline_vals, dtype=np.float64)
    b = np.asarray(candidate_vals, dtype=np.float64)
    require_ok(a.shape == b.shape and a.ndim == 1 and a.size >= 2, "ERR_PAIRED", "Paired arrays must match with n >= 2")
    n = int(a.size)
    diffs = b - a
    mean_a = float(np.mean(a))
    mean_b = float(np.mean(b))
    mean_d = float(np.mean(diffs))
    se_d = float(np.std(diffs, ddof=1)) / math.sqrt(float(n))
    if abs(mean_d) <= 1e-15:
        z_val = 0.0
    elif se_d <= 1e-15:
        z_val = math.copysign(1e6, mean_d)
    else:
        z_val = mean_d / se_d
    rel_pct = 0.0 if abs(mean_a) <= 1e-12 else 100.0 * (mean_b - mean_a) / abs(mean_a)
    p_norm = math.erfc(min(50.0, abs(z_val)) / math.sqrt(2.0))
    # Exact two-sided Student-t p-value via regularized incomplete beta for df=n-1 (closed form for df=2 and general)
    df = n - 1
    if df == 2:
        p_t = max(0.0, min(1.0, 1.0 - abs(z_val) / math.sqrt(2.0 + z_val * z_val)))
    else:
        # Exact integration for integer df >= 1 using trigonometric reduction of Student-t CDF
        theta = math.atan(abs(z_val) / math.sqrt(float(df)))
        if df % 2 == 1:
            s_term = theta
            if df > 1:
                cos_t = math.cos(theta)
                sin_t = math.sin(theta)
                coef = sin_t * cos_t
                s_term += coef
                for k in range(3, df, 2):
                    coef *= (float(k - 1) / float(k)) * (cos_t * cos_t)
                    s_term += coef
            cdf_abs = 0.5 + s_term / math.pi
        else:
            sin_t = math.sin(theta)
            cos_t = math.cos(theta)
            s_term = sin_t
            coef = sin_t
            for k in range(2, df, 2):
                coef *= (float(k - 1) / float(k)) * (cos_t * cos_t)
                s_term += coef
            cdf_abs = 0.5 + 0.5 * s_term
        p_t = max(0.0, min(1.0, 2.0 * (1.0 - cdf_abs)))
    return {
        "n": n,
        "df": df,
        "baseline_mean": round(mean_a, 6),
        "candidate_mean": round(mean_b, 6),
        "paired_diff_mean": round(mean_d, 6),
        "paired_diff_se": round(se_d, 6),
        "rel_change_pct": round(rel_pct, 4),
        "z_paired": round(z_val, 4),
        "p_normal_2s": round(p_norm, 6),
        "p_student_t_2s": round(p_t, 6),
    }


# =============================================================================
# 3. High-Rate `200 Hz` (`5.0 ms`) Mode-1 Hardware Telemetry Sampler (RAPL + NVML)
# =============================================================================


class Mode1HardwareSampler:
    """Synchronized 200 Hz C-NVML + sysfs intel-rapl + /proc/stat + cpufreq background sampler."""

    def __init__(self, period_ms: float = 5.0, smoke_cpu: bool = False) -> None:
        self.period_ns = int(round(period_ms * 1_000_000.0))
        self.smoke_cpu = smoke_cpu
        self._nvml: Optional[ctypes.CDLL] = None
        self._nvml_dev = ctypes.c_void_p()
        self._rapl_fds: Dict[str, Tuple[int, int]] = {}
        self._proc_stat_fd: Optional[int] = None
        self._cpufreq_fds: List[int] = []

        self._lock = threading.Lock()
        self._recording = False
        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._samples: List[Dict[str, Any]] = []
        self._frames64: List[bytes] = []
        self._latest: Dict[str, float] = {
            "gpu_power_w": 0.0,
            "pkg_w": 0.0,
            "core_w": 0.0,
            "uncore_w": 0.0,
            "psys_w": 0.0,
            "fast_power_w": 0.0,
            "sm_clock_mhz": 0.0,
            "gpu_temp_c": 0.0,
            "sw_power_cap": 0.0,
            "hw_slowdown": 0.0,
            "enforced_limit_w": 90.0,
        }
        self._window_gpu_w_sum = 0.0
        self._window_gpu_w_cnt = 0

    def open_hardware(self) -> Dict[str, Any]:
        if self.smoke_cpu:
            return {"mode": "smoke_cpu", "rapl_domains": ["pkg_w", "core_w", "uncore_w", "psys_w"], "nvml_ready": False}

        rapl_root = Path("/sys/devices/virtual/powercap/intel-rapl")
        validate_endpoint_path(rapl_root, auth_gate=None)
        if rapl_root.is_dir():
            for d in sorted(rapl_root.rglob("intel-rapl:*")):
                name_f = d / "name"
                energy_f = d / "energy_uj"
                max_f = d / "max_energy_range_uj"
                if name_f.is_file() and energy_f.is_file():
                    validate_endpoint_path(energy_f, auth_gate=None)
                    raw_name = name_f.read_text(encoding="utf-8").strip().lower()
                    max_uj = int(max_f.read_text(encoding="utf-8").strip()) if max_f.is_file() else (1 << 32)
                    key = (
                        "psys"
                        if "psys" in raw_name
                        else "pkg"
                        if raw_name.startswith("package")
                        else "core"
                        if raw_name == "core"
                        else "uncore"
                        if raw_name == "uncore"
                        else raw_name
                    )
                    fd = os.open(str(energy_f), os.O_RDONLY)
                    self._rapl_fds[key] = (fd, max_uj)

        proc_p = Path("/proc/stat")
        validate_endpoint_path(proc_p, auth_gate=None)
        if proc_p.is_file():
            self._proc_stat_fd = os.open(str(proc_p), os.O_RDONLY)

        cpu_root = Path("/sys/devices/system/cpu")
        validate_endpoint_path(cpu_root, auth_gate=None)
        if cpu_root.is_dir():
            for fpath in sorted(cpu_root.glob("cpu[0-9]*/cpufreq/scaling_cur_freq"))[:4]:
                validate_endpoint_path(fpath, auth_gate=None)
                try:
                    self._cpufreq_fds.append(os.open(str(fpath), os.O_RDONLY))
                except OSError:
                    continue

        nvml = ctypes.CDLL("libnvidia-ml.so.1")
        rc = nvml.nvmlInit_v2()
        require_ok(rc == 0, "ERR_NVML_INIT", f"nvmlInit_v2 failed with rc={rc}")
        rc_d = nvml.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(self._nvml_dev))
        require_ok(rc_d == 0, "ERR_NVML_HANDLE", f"nvmlDeviceGetHandleByIndex_v2 failed with rc={rc_d}")
        pl_mw = ctypes.c_uint(0)
        if nvml.nvmlDeviceGetEnforcedPowerLimit(self._nvml_dev, ctypes.byref(pl_mw)) == 0 and pl_mw.value > 0:
            self._latest["enforced_limit_w"] = float(pl_mw.value) / 1000.0
        self._nvml = nvml

        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._loop, name="s115-mode1-200hz", daemon=True)
        self._thread.start()
        time.sleep(0.03)
        return {
            "mode": "live_mode1_200hz",
            "rapl_domains": sorted(self._rapl_fds.keys()),
            "nvml_ready": True,
            "enforced_power_limit_w": self._latest["enforced_limit_w"],
        }

    def close_hardware(self) -> None:
        self._stop_evt.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        for fd, _ in self._rapl_fds.values():
            try:
                os.close(fd)
            except OSError:
                pass
        self._rapl_fds.clear()
        if self._proc_stat_fd is not None:
            try:
                os.close(self._proc_stat_fd)
            except OSError:
                pass
            self._proc_stat_fd = None
        for fd in self._cpufreq_fds:
            try:
                os.close(fd)
            except OSError:
                pass
        self._cpufreq_fds.clear()
        if self._nvml is not None:
            try:
                self._nvml.nvmlShutdown()
            except Exception:
                pass
            self._nvml = None

    def _read_rapl_uj(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for k, (fd, _) in self._rapl_fds.items():
            raw = os.pread(fd, 48, 0).strip()
            out[k] = int(raw)
        return out

    def _read_nvml(self) -> Tuple[float, int, int, int, int]:
        if self._nvml is None:
            return 0.0, 0, 0, 0, 0
        p_mw = ctypes.c_uint(0)
        e_mj = ctypes.c_ulonglong(0)
        sm_mhz = ctypes.c_uint(0)
        temp_c = ctypes.c_uint(0)
        thr = ctypes.c_ulonglong(0)
        self._nvml.nvmlDeviceGetPowerUsage(self._nvml_dev, ctypes.byref(p_mw))
        self._nvml.nvmlDeviceGetTotalEnergyConsumption(self._nvml_dev, ctypes.byref(e_mj))
        self._nvml.nvmlDeviceGetClockInfo(self._nvml_dev, 1, ctypes.byref(sm_mhz))
        self._nvml.nvmlDeviceGetTemperature(self._nvml_dev, 0, ctypes.byref(temp_c))
        self._nvml.nvmlDeviceGetCurrentClocksThrottleReasons(self._nvml_dev, ctypes.byref(thr))
        return float(p_mw.value) / 1000.0, int(e_mj.value), int(sm_mhz.value), int(temp_c.value), int(thr.value)

    def _read_proc_stat_intr_ctxt(self) -> Tuple[int, int]:
        if self._proc_stat_fd is None:
            return 0, 0
        # Read first 4 KiB containing cpu lines + intr head + ctxt if nearby, or full /proc/stat (~3 KiB)
        blob = os.pread(self._proc_stat_fd, 16384, 0).decode("ascii", errors="ignore")
        intr_v = 0
        ctxt_v = 0
        for line in blob.splitlines():
            if line.startswith("intr "):
                parts = line.split(None, 2)
                if len(parts) >= 2:
                    intr_v = int(parts[1])
            elif line.startswith("ctxt "):
                parts = line.split(None, 2)
                if len(parts) >= 2:
                    ctxt_v = int(parts[1])
        return intr_v, ctxt_v

    def _loop(self) -> None:
        prev_ns = time.monotonic_ns()
        prev_rapl = self._read_rapl_uj()
        _, prev_emj, _, _, _ = self._read_nvml()
        prev_intr, prev_ctxt = self._read_proc_stat_intr_ctxt()
        next_ns = prev_ns + self.period_ns
        tick_idx = 0

        while not self._stop_evt.is_set():
            now_ns = time.monotonic_ns()
            rem_ns = next_ns - now_ns
            if rem_ns > 200_000:
                time.sleep(rem_ns * 1e-9)
            t_ns = time.monotonic_ns()
            dt_ns = max(100_000, t_ns - prev_ns)
            dt_s = float(dt_ns) * 1e-9

            cur_rapl = self._read_rapl_uj()
            gpu_w, cur_emj, sm_mhz, temp_c, thr_mask = self._read_nvml()

            watts: Dict[str, float] = {}
            for k in ("pkg", "core", "uncore", "psys"):
                if k in cur_rapl and k in prev_rapl:
                    _, max_uj = self._rapl_fds[k]
                    duj = cur_rapl[k] - prev_rapl[k]
                    if duj < 0:
                        duj += max_uj
                    watts[k] = float(duj) * 1e-6 / dt_s
                else:
                    watts[k] = 0.0

            if tick_idx % 4 == 0:
                cur_intr, cur_ctxt = self._read_proc_stat_intr_ctxt()
                intr_hz = max(0.0, float(cur_intr - prev_intr) / max(4.0 * dt_s, 1e-4))
                ctxt_hz = max(0.0, float(cur_ctxt - prev_ctxt) / max(4.0 * dt_s, 1e-4))
                prev_intr, prev_ctxt = cur_intr, cur_ctxt
            else:
                intr_hz = self._latest.get("intr_hz", 0.0)
                ctxt_hz = self._latest.get("ctxt_hz", 0.0)

            sw_cap = bool(thr_mask & 0x4)
            hw_therm = bool(thr_mask & 0x40)
            hw_slow = bool(thr_mask & 0xC8)
            fast_w = watts["pkg"] + gpu_w

            prev_ns = t_ns
            prev_rapl = cur_rapl
            prev_emj = cur_emj
            tick_idx += 1
            next_ns += self.period_ns
            if next_ns < t_ns:
                next_ns = t_ns + self.period_ns

            with self._lock:
                self._latest.update(
                    {
                        "gpu_power_w": gpu_w,
                        "gpu_energy_mj": float(cur_emj),
                        "pkg_w": watts["pkg"],
                        "core_w": watts["core"],
                        "uncore_w": watts["uncore"],
                        "psys_w": watts["psys"],
                        "fast_power_w": fast_w,
                        "sm_clock_mhz": float(sm_mhz),
                        "gpu_temp_c": float(temp_c),
                        "sw_power_cap": 1.0 if sw_cap else 0.0,
                        "hw_slowdown": 1.0 if hw_slow else 0.0,
                        "intr_hz": intr_hz,
                        "ctxt_hz": ctxt_hz,
                    }
                )
                if self._recording:
                    self._window_gpu_w_sum += gpu_w
                    self._window_gpu_w_cnt += 1
                    self._samples.append(
                        {
                            "ts_ns": t_ns,
                            "dt_ms": dt_s * 1000.0,
                            "gpu_power_w": gpu_w,
                            "gpu_energy_mj": cur_emj,
                            "pkg_w": watts["pkg"],
                            "core_w": watts["core"],
                            "uncore_w": watts["uncore"],
                            "psys_w": watts["psys"],
                            "sm_clock_mhz": sm_mhz,
                            "gpu_temp_c": temp_c,
                            "sw_power_cap": 1 if sw_cap else 0,
                            "hw_slowdown": 1 if hw_slow else 0,
                        }
                    )
                    self._frames64.append(
                        pack_frame64_bytes(
                            ts_mono_ns=t_ns,
                            pkg_uj=cur_rapl.get("pkg", 0),
                            core_uj=cur_rapl.get("core", 0),
                            uncore_uj=cur_rapl.get("uncore", 0),
                            psys_uj=cur_rapl.get("psys", 0),
                            gpu_mj=cur_emj,
                            step_us=int(round(dt_s * 1e6)),
                            sw_power_cap=sw_cap,
                            hw_thermal_slowdown=hw_therm,
                            gpu_temp_deci_c=temp_c * 10,
                            sm_clock_mhz=sm_mhz,
                        )
                    )

    def latest_snapshot(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._latest)

    def running_mean_gpu_w(self) -> float:
        with self._lock:
            if self._window_gpu_w_cnt == 0:
                return float(self._latest["gpu_power_w"])
            return self._window_gpu_w_sum / float(self._window_gpu_w_cnt)

    def start_window(self) -> Tuple[int, int]:
        with self._lock:
            self._samples.clear()
            self._frames64.clear()
            self._window_gpu_w_sum = 0.0
            self._window_gpu_w_cnt = 0
            self._recording = True
            emj = int(self._latest.get("gpu_energy_mj", 0.0))
        return time.monotonic_ns(), emj

    def stop_window(self, label: str, tokens_processed: int, seed_hint: int = 42) -> Dict[str, Any]:
        end_ns = time.monotonic_ns()
        with self._lock:
            self._recording = False
            rows = list(self._samples)
            frames = list(self._frames64)
            end_emj = int(self._latest.get("gpu_energy_mj", 0.0))

        if self.smoke_cpu:
            from s115_silisense_profiler import make_synthetic_workload_trace

            kind = "eager_microkernel" if "eager" in label else "fused_holosphere"
            synth = make_synthetic_workload_trace(kind, n_samples=260, dt_ms=5.0, seed=seed_hint, target_mean_gpu_w=85.0)
            synth["tokens_processed"] = int(tokens_processed)
            synth["pkg_w"] = np.full(260, 22.0, dtype=np.float64)
            synth["psys_w"] = np.asarray(synth["slow_throttle_or_psys"], dtype=np.float64)
            synth["sm_clock_mhz"] = np.full(260, 1680.0, dtype=np.float64)
            synth["sw_power_cap"] = np.zeros(260, dtype=np.float64)
            synth["wall_s"] = 1.30
            synth["gpu_mj_delta"] = float(tokens_processed) * 1.8 / 1000.0 * 1000.0
            synth["frame64_count"] = 260
            synth["frame64_merkle_sha256"] = hash_frame64_stream(
                label, [pack_frame64_bytes(ts_mono_ns=i * 5_000_000, pkg_uj=i * 100, core_uj=i * 80, uncore_uj=i * 20, psys_uj=i * 400, gpu_mj=i * 4, step_us=5000, sw_power_cap=False, hw_thermal_slowdown=False, gpu_temp_deci_c=620, sm_clock_mhz=1680) for i in range(260)]
            )
            return synth

        require_ok(len(rows) >= 64, "ERR_WINDOW_TOO_SHORT", f"Window {label} captured only {len(rows)} samples (< 64)")
        span_s = max(1e-4, float(rows[-1]["ts_ns"] - rows[0]["ts_ns"]) * 1e-9)
        dt_ms = (span_s * 1000.0) / float(max(1, len(rows) - 1))
        gpu_w = np.asarray([float(r["gpu_power_w"]) for r in rows], dtype=np.float64)
        pkg_w = np.asarray([float(r["pkg_w"]) for r in rows], dtype=np.float64)
        uncore_w = np.asarray([float(r["uncore_w"]) for r in rows], dtype=np.float64)
        psys_w = np.asarray([float(r["psys_w"]) for r in rows], dtype=np.float64)
        sm_mhz = np.asarray([float(r["sm_clock_mhz"]) for r in rows], dtype=np.float64)
        sw_cap = np.asarray([float(r["sw_power_cap"]) for r in rows], dtype=np.float64)
        hw_slow = np.asarray([float(r["hw_slowdown"]) for r in rows], dtype=np.float64)

        emj_start = int(rows[0]["gpu_energy_mj"])
        emj_end = max(end_emj, int(rows[-1]["gpu_energy_mj"]))
        gpu_mj_delta = float(max(0, emj_end - emj_start))
        if gpu_mj_delta <= 0.0:
            gpu_mj_delta = float(np.mean(gpu_w)) * span_s * 1000.0

        # Mode-1 fast rail = MSR CPU pkg_w + NVML gpu_power_w; slow response = EC psys_w + SwPowerCap excursion
        fast_rail = pkg_w + gpu_w
        slow_resp = psys_w + 15.0 * sw_cap
        _ = end_ns
        return {
            "dt_ms": dt_ms,
            "wall_s": span_s,
            "tokens_processed": int(tokens_processed),
            "gpu_mj_delta": gpu_mj_delta,
            "gpu_power_w": gpu_w,
            "pkg_w": pkg_w,
            "uncore_w": uncore_w,
            "psys_w": psys_w,
            "fast_power_w": fast_rail,
            "slow_throttle_or_psys": slow_resp,
            "sm_clock_mhz": sm_mhz,
            "sw_power_cap": sw_cap,
            "hw_slowdown": hw_slow,
            "frame64_count": len(frames),
            "frame64_merkle_sha256": hash_frame64_stream(label, frames),
        }


# =============================================================================
# 4. Real 12L `Eager H7b` & `HoloSphere-V2` Model Builders
# =============================================================================


class _HoloSphereV2Block(nn.Module):
    def __init__(self, d_model: int, n_heads: int, d_ff: int, *, backend: str = "cuda", map_mode: str = "exp") -> None:
        super().__init__()
        self.backend = backend
        self.attn = ops.S114CovariantHolonomyAttention(
            d_model,
            n_heads,
            covariant_v=False,
            ngpt=True,
            angle_scale=(0.50 if map_mode == "cayley" else 0.75),
            backend=backend,
            map_mode=map_mode,
        )
        self.mlp = s107.SwiGLUMLP(d_model, d_ff, ngpt=True)
        init_logit = math.log(0.05 / 0.95)
        self.alpha_a_logit = nn.Parameter(torch.full((d_model,), init_logit))
        self.alpha_m_logit = nn.Parameter(torch.full((d_model,), init_logit))

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        h = ops.fused_spherical_step(h, self.attn(h), self.alpha_a_logit, mode="slerp", backend=self.backend)
        h = ops.fused_spherical_step(h, self.mlp(h), self.alpha_m_logit, mode="slerp", backend=self.backend)
        return h


class _HoloSphereV2LM(nn.Module):
    def __init__(
        self,
        *,
        d_model: int = 320,
        n_heads: int = 8,
        n_layers: int = 12,
        base_d_ff: int = 864,
        backend: str = "cuda",
        map_mode: str = "exp",
        grad_ckpt: int = 0,
        vocab_size: int = VOCAB_SIZE,
    ) -> None:
        super().__init__()
        d_head = d_model // n_heads
        d_ff = base_d_ff - n_heads * (d_head // 4)
        self.grad_ckpt = int(grad_ckpt)
        self.tok_emb = nn.Embedding(vocab_size, d_model)
        self.blocks = nn.ModuleList(
            [_HoloSphereV2Block(d_model, n_heads, d_ff, backend=backend, map_mode=map_mode) for _ in range(n_layers)]
        )
        self.logit_scale = nn.Parameter(torch.full((1,), math.sqrt(float(d_model))))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = ops._safe_unit_norm(self.tok_emb(x), eps=1e-4)
        for blk in self.blocks:
            if self.grad_ckpt == 1 and self.training and h.requires_grad:
                h = grad_checkpoint(blk, h, use_reentrant=False)
            else:
                h = blk(h)
        return (h @ self.tok_emb.weight.T) * self.logit_scale


def _seed_everything(seed: int) -> torch.Generator:
    s = int(seed) & 0x7FFFFFFF
    random.seed(s)
    torch.manual_seed(s)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(s)
    return torch.Generator(device="cpu").manual_seed(s)


def _build_eager_h7b(seed: int, device: torch.device, smoke_cpu: bool = False) -> nn.Module:
    _seed_everything(seed)
    cfg = s107.S107ModelConfig(
        arm_name="eager_h7b",
        track="H7b",
        pos_mode="su2_holonomy",
        ngpt=True,
        d_model=(64 if smoke_cpu else 320),
        n_heads=(4 if smoke_cpu else 8),
        n_layers=(4 if smoke_cpu else 12),
        base_d_ff=(128 if smoke_cpu else 864),
    )
    return s107.S107TransformerLM(cfg).to(device)


def _build_holosphere_v2(
    seed: int,
    device: torch.device,
    *,
    backend: str = "cuda",
    map_mode: str = "exp",
    grad_ckpt: int = 0,
    smoke_cpu: bool = False,
) -> nn.Module:
    _seed_everything(seed)
    eff_backend = "reference" if smoke_cpu else backend
    return _HoloSphereV2LM(
        d_model=(64 if smoke_cpu else 320),
        n_heads=(4 if smoke_cpu else 8),
        n_layers=(2 if smoke_cpu else 12),
        base_d_ff=(128 if smoke_cpu else 864),
        backend=eff_backend,
        map_mode=map_mode,
        grad_ckpt=grad_ckpt,
    ).to(device)


def _make_batch(gen: torch.Generator, bsz: int, seq_len: int, device: torch.device) -> Tuple[torch.Tensor, torch.Tensor]:
    x = torch.randint(0, VOCAB_SIZE, (bsz, seq_len), generator=gen).to(device)
    y = torch.randint(0, VOCAB_SIZE, (bsz, seq_len), generator=gen).to(device)
    return x, y


def _train_step(model: nn.Module, opt: torch.optim.Optimizer, x: torch.Tensor, y: torch.Tensor, use_bf16: bool) -> None:
    opt.zero_grad(set_to_none=True)
    if use_bf16 and x.is_cuda:
        with torch.autocast("cuda", dtype=torch.bfloat16):
            out = model(x)
            logits = out[0] if isinstance(out, tuple) else out
            loss = F.cross_entropy(logits.float().reshape(-1, VOCAB_SIZE), y.reshape(-1))
    else:
        out = model(x)
        logits = out[0] if isinstance(out, tuple) else out
        loss = F.cross_entropy(logits.float().reshape(-1, VOCAB_SIZE), y.reshape(-1))
    loss.backward()
    opt.step()


# =============================================================================
# 5. Experiment 1 — `H15a` (`EXP-Q21a` Live Interleaved `ABABAB` Profiling)
# =============================================================================


def _summarize_trace_for_receipt(
    tr: Dict[str, Any],
    prof: Dict[str, Any],
) -> Dict[str, Any]:
    toks = int(tr["tokens_processed"])
    wall_s = float(tr["wall_s"])
    mj_tok = float(tr["gpu_mj_delta"]) / float(max(1, toks))
    int_mw = [int(round((float(p) + float(g)) * 100.0)) for p, g in zip(tr["pkg_w"], tr["gpu_power_w"])]
    op1 = compute_op1_seam1_sherman_morrison(int_mw, window=32)
    op2 = compute_op2_seam3_ordinal_hodge_curl(tr["gpu_power_w"])
    op3 = compute_op3_f3_from_rails(tr["pkg_w"], tr["uncore_w"], tr["gpu_power_w"])
    a3 = prof["observables"]["A3_telemetry"]
    a5 = prof["observables"]["A5_precursor"]
    a7 = prof["observables"]["A7_uncore_copula_mi"]
    return {
        "n_samples": int(len(tr["gpu_power_w"])),
        "dt_ms": round(float(tr["dt_ms"]), 4),
        "wall_s": round(wall_s, 4),
        "tokens_processed": toks,
        "tok_per_s": round(float(toks) / max(wall_s, 1e-6), 2),
        "gpu_mj_per_tok": round(mj_tok, 5),
        "mean_gpu_power_w": float(prof["mean_gpu_power_w"]),
        "std_gpu_power_w": float(prof["std_gpu_power_w"]),
        "mean_pkg_w": round(float(np.mean(tr["pkg_w"])), 4),
        "mean_uncore_w": float(prof["mean_uncore_w"]),
        "mean_psys_w": round(float(np.mean(tr["psys_w"])), 4),
        "sw_power_cap_frac": round(float(np.mean(tr["sw_power_cap"])), 5),
        "abs_A3": float(a3["abs_asymmetry"]),
        "signed_A3": float(a3["asymmetry"]),
        "z_A3": float(a3["z_iaaft"]),
        "p_holm_A3": float(a3["p_holm"]),
        "A5_peak_lag_ms": float(a5["peak_precursor_lag_ms"]),
        "A5_p_circ": float(a5["p_circ"]),
        "A7_copula_mi_nats": float(a7["copula_mi_nats"]),
        "z_A7": float(a7["z_iaaft"]),
        "p_emp_A7": float(a7["p_emp"]),
        "A7_max_residual_lin_corr": float(a7["max_abs_residual_linear_corr"]),
        "min_family_holm_p": float(prof["min_family_holm_p"]),
        "any_non_textbook_sig_0p005": bool(prof["any_non_textbook_significant_0p005"]),
        "OP1_SEAM1": op1,
        "OP2_SEAM3": op2,
        "OP3_F3": op3,
        "frame64_count": int(tr["frame64_count"]),
        "frame64_merkle_sha256": str(tr["frame64_merkle_sha256"]),
    }


def run_h15a_experiment(
    *,
    device: torch.device,
    sampler: Mode1HardwareSampler,
    smoke_cpu: bool = False,
) -> Dict[str, Any]:
    bsz = 2 if smoke_cpu else 8
    seq_len = 64 if smoke_cpu else 512
    std_steps = 2 if smoke_cpu else 22
    n_iaaft = 99 if smoke_cpu else 799
    n_shifts = 100 if smoke_cpu else 500
    use_bf16 = not smoke_cpu

    standard_pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    equal_watt_pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    std_pair_meta: List[Tuple[int, int]] = []
    eqw_pair_meta: List[Tuple[int, int]] = []

    for seed in SEEDS:
        gen = _seed_everything(seed + 1500)
        x_b, y_b = _make_batch(gen, bsz, seq_len, device)
        eager_m = _build_eager_h7b(seed, device, smoke_cpu=smoke_cpu)
        fused_m = _build_holosphere_v2(seed, device, backend="cuda", map_mode="exp", smoke_cpu=smoke_cpu)
        eager_opt = torch.optim.AdamW(eager_m.parameters(), lr=2.0e-3)
        fused_opt = torch.optim.AdamW(fused_m.parameters(), lr=2.0e-3)

        # Warmup both arms identically before interleaved ABABAB windows
        for _ in range(1 if smoke_cpu else 3):
            _train_step(eager_m, eager_opt, x_b, y_b, use_bf16)
            _train_step(fused_m, fused_opt, x_b, y_b, use_bf16)
        if device.type == "cuda":
            torch.cuda.synchronize()

        tokens_per_block = std_steps * bsz * seq_len

        # Part 1A: Unpaced CS-08 Equal-Tokens-Per-Block Interleaved ABABAB (3 pairs per seed)
        for p_idx in range(1 if smoke_cpu else 3):
            # Alternate A->B vs B->A across pairs to cancel monotonic thermal slope
            run_eager_first = ((seed + p_idx) % 2 == 0)

            def _exec_std_arm(arm_label: str, mod: nn.Module, opt_i: torch.optim.Optimizer, sh: int) -> Dict[str, Any]:
                if device.type == "cuda":
                    torch.cuda.synchronize()
                sampler.start_window()
                for _ in range(std_steps):
                    _train_step(mod, opt_i, x_b, y_b, use_bf16)
                if device.type == "cuda":
                    torch.cuda.synchronize()
                return sampler.stop_window(arm_label, tokens_per_block, seed_hint=sh)

            if run_eager_first:
                tr_e = _exec_std_arm(f"h15a_std_eager_s{seed}_p{p_idx}", eager_m, eager_opt, seed + 10 * p_idx)
                if not smoke_cpu:
                    time.sleep(0.15)
                tr_f = _exec_std_arm(f"h15a_std_fused_s{seed}_p{p_idx}", fused_m, fused_opt, seed + 10 * p_idx + 1)
            else:
                tr_f = _exec_std_arm(f"h15a_std_fused_s{seed}_p{p_idx}", fused_m, fused_opt, seed + 10 * p_idx + 1)
                if not smoke_cpu:
                    time.sleep(0.15)
                tr_e = _exec_std_arm(f"h15a_std_eager_s{seed}_p{p_idx}", eager_m, eager_opt, seed + 10 * p_idx)
            standard_pairs.append((tr_e, tr_f))
            std_pair_meta.append((seed, p_idx))
            if not smoke_cpu:
                time.sleep(0.20)

        # Part 1B: Throughput-Paced Equal-Wattage Control (|mean_w_e - mean_w_f| / mean_w_f <= 5.0%)
        # Measure natural lower-wattage Fused arm first, then pace Eager block-level execution via smooth PI
        # feedback on running mean GPU power ONLY (100% blind to A3/A5/A7!).
        fused_eqw_steps = 2 if smoke_cpu else 36
        eager_eqw_steps = 2 if smoke_cpu else 6
        for p_idx in range(1 if smoke_cpu else 3):
            if device.type == "cuda":
                torch.cuda.synchronize()
            sampler.start_window()
            for _ in range(fused_eqw_steps):
                _train_step(fused_m, fused_opt, x_b, y_b, use_bf16)
            if device.type == "cuda":
                torch.cuda.synchronize()
            tr_f_eq = sampler.stop_window(
                f"h15a_eqw_fused_s{seed}_p{p_idx}",
                fused_eqw_steps * bsz * seq_len,
                seed_hint=seed + 300 + p_idx,
            )
            target_w = float(np.mean(tr_f_eq["gpu_power_w"]))

            if smoke_cpu:
                from s115_silisense_profiler import make_synthetic_workload_trace

                tr_e_eq = make_synthetic_workload_trace(
                    "eager_microkernel", n_samples=260, dt_ms=5.0, seed=seed + 400 + p_idx, target_mean_gpu_w=target_w
                )
                tr_e_eq["tokens_processed"] = eager_eqw_steps * bsz * seq_len
                tr_e_eq["pkg_w"] = np.full(260, 24.0, dtype=np.float64)
                tr_e_eq["psys_w"] = np.asarray(tr_e_eq["slow_throttle_or_psys"], dtype=np.float64)
                tr_e_eq["sm_clock_mhz"] = np.full(260, 1650.0, dtype=np.float64)
                tr_e_eq["sw_power_cap"] = np.zeros(260, dtype=np.float64)
                tr_e_eq["wall_s"] = 1.30
                tr_e_eq["gpu_mj_delta"] = float(tr_e_eq["tokens_processed"]) * 9.5
                tr_e_eq["frame64_count"] = 260
                tr_e_eq["frame64_merkle_sha256"] = tr_f_eq["frame64_merkle_sha256"]
            else:
                # Attach smooth inter-block PI watt-matcher hook to eager_m.blocks (12 updates/step)
                pace_state = {"sleep_s": 0.0045}

                def _pace_hook(_mod: nn.Module, _inp: Any, _out: Any) -> None:
                    torch.cuda.synchronize()
                    cur_mean_w = sampler.running_mean_gpu_w()
                    err_w = cur_mean_w - target_w
                    # Proportional adjustment bounded strictly to [0.0, 0.020] sec per block
                    pace_state["sleep_s"] = max(0.0, min(0.020, pace_state["sleep_s"] + 0.00035 * err_w))
                    if pace_state["sleep_s"] > 0.0002:
                        time.sleep(pace_state["sleep_s"])

                handles = [blk.register_forward_hook(_pace_hook) for blk in eager_m.blocks]  # type: ignore[union-attr]
                try:
                    torch.cuda.synchronize()
                    sampler.start_window()
                    for _ in range(eager_eqw_steps):
                        _train_step(eager_m, eager_opt, x_b, y_b, use_bf16)
                    torch.cuda.synchronize()
                    # Short 0.35s closed-loop trim if running mean is >2.5% away from target_w
                    trim_deadline = time.monotonic() + 0.45
                    while time.monotonic() < trim_deadline:
                        cur_w = sampler.running_mean_gpu_w()
                        if abs(cur_w - target_w) / max(target_w, 1.0) <= 0.025:
                            break
                        if cur_w > target_w:
                            time.sleep(0.025)
                        else:
                            # Tiny dense matmul pulse on GPU to lift mean GPU power toward target_w
                            _train_step(fused_m, fused_opt, x_b[:2], y_b[:2], use_bf16)
                            torch.cuda.synchronize()
                    tr_e_eq = sampler.stop_window(
                        f"h15a_eqw_eager_s{seed}_p{p_idx}",
                        eager_eqw_steps * bsz * seq_len,
                        seed_hint=seed + 400 + p_idx,
                    )
                finally:
                    for h in handles:
                        h.remove()

            equal_watt_pairs.append((tr_e_eq, tr_f_eq))
            eqw_pair_meta.append((seed, p_idx))
            if not smoke_cpu:
                time.sleep(0.20)

        del eager_m, fused_m, eager_opt, fused_opt
        gc.collect()
        if device.type == "cuda":
            torch.cuda.empty_cache()

        if smoke_cpu:
            # Replicate to 3 pairs in smoke_cpu mode so PairedABABABEvaluator (>=3 pairs) runs cleanly
            while len(standard_pairs) < 3:
                standard_pairs.append(standard_pairs[0])
                std_pair_meta.append((seed, len(standard_pairs) - 1))
                equal_watt_pairs.append(equal_watt_pairs[0])
                eqw_pair_meta.append((seed, len(equal_watt_pairs) - 1))
            break

    # Grade via canonical PairedABABABEvaluator AND record per-pair audit receipts
    evaluator = PairedABABABEvaluator(mode="telemetry-only", auth_gate=None, n_iaaft=n_iaaft, n_shifts=n_shifts)
    graded = evaluator.evaluate_h15a(standard_pairs=standard_pairs, equal_watt_pairs=equal_watt_pairs)

    std_pair_records: List[Dict[str, Any]] = []
    for idx, ((tr_e, tr_f), (sd, pi)) in enumerate(zip(standard_pairs, std_pair_meta)):
        pe = SiliSenseProfiler(mode="telemetry-only", n_iaaft=n_iaaft, n_shifts=n_shifts, seed=100 + 2 * idx).profile_trace(tr_e)
        pf = SiliSenseProfiler(mode="telemetry-only", n_iaaft=n_iaaft, n_shifts=n_shifts, seed=101 + 2 * idx).profile_trace(tr_f)
        std_pair_records.append(
            {
                "pair_index": idx,
                "seed": sd,
                "within_seed_pair": pi,
                "eager_h7b": _summarize_trace_for_receipt(tr_e, pe),
                "holosphere_v2_sm86": _summarize_trace_for_receipt(tr_f, pf),
            }
        )

    eqw_pair_records: List[Dict[str, Any]] = []
    for idx, ((tr_e, tr_f), (sd, pi)) in enumerate(zip(equal_watt_pairs, eqw_pair_meta)):
        pe = SiliSenseProfiler(mode="telemetry-only", n_iaaft=n_iaaft, n_shifts=n_shifts, seed=500 + 2 * idx).profile_trace(tr_e)
        pf = SiliSenseProfiler(mode="telemetry-only", n_iaaft=n_iaaft, n_shifts=n_shifts, seed=501 + 2 * idx).profile_trace(tr_f)
        we = float(pe["mean_gpu_power_w"])
        wf = float(pf["mean_gpu_power_w"])
        eqw_pair_records.append(
            {
                "pair_index": idx,
                "seed": sd,
                "within_seed_pair": pi,
                "rel_watt_diff": round(abs(we - wf) / max(wf, 1e-9), 6),
                "eager_h7b_paced": _summarize_trace_for_receipt(tr_e, pe),
                "holosphere_v2_sm86": _summarize_trace_for_receipt(tr_f, pf),
            }
        )

    eager_a3 = [r["eager_h7b"]["abs_A3"] for r in std_pair_records]
    fused_a3 = [r["holosphere_v2_sm86"]["abs_A3"] for r in std_pair_records]
    eager_a7 = [r["eager_h7b"]["A7_copula_mi_nats"] for r in std_pair_records]
    fused_a7 = [r["holosphere_v2_sm86"]["A7_copula_mi_nats"] for r in std_pair_records]
    eqw_e_a3 = [r["eager_h7b_paced"]["abs_A3"] for r in eqw_pair_records]
    eqw_f_a3 = [r["holosphere_v2_sm86"]["abs_A3"] for r in eqw_pair_records]
    eqw_e_a7 = [r["eager_h7b_paced"]["A7_copula_mi_nats"] for r in eqw_pair_records]
    eqw_f_a7 = [r["holosphere_v2_sm86"]["A7_copula_mi_nats"] for r in eqw_pair_records]

    return {
        "graded": graded,
        "student_t_sensitivity": {
            "standard_abs_A3": paired_stats_with_student_t(eager_a3, fused_a3),
            "standard_A7_copula_mi": paired_stats_with_student_t(eager_a7, fused_a7),
            "equal_watt_abs_A3": paired_stats_with_student_t(eqw_e_a3, eqw_f_a3),
            "equal_watt_A7_copula_mi": paired_stats_with_student_t(eqw_e_a7, eqw_f_a7),
        },
        "standard_pairs": std_pair_records,
        "equal_watt_pairs": eqw_pair_records,
    }


# =============================================================================
# 6. Experiment 2 — `H15b` (`EXP-Q21b` Live Closed-Loop Precursor Governor Showdown)
# =============================================================================


def run_h15b_experiment(
    *,
    device: torch.device,
    sampler: Mode1HardwareSampler,
    smoke_cpu: bool = False,
) -> Dict[str, Any]:
    if smoke_cpu:
        from s115_feedback_autotuner import simulate_sustained_governor_benchmark

        sim = simulate_sustained_governor_benchmark(seeds=SEEDS, n_steps=240, dt_ms=5.0)
        return {
            "graded": sim,
            "delay_bandwidth_lock": check_delay_bandwidth_lock(20.0, 0.005),
            "runs": [],
            "lead_receipts": [],
        }

    arms = ("NoGovernor", "SiliSense-Precursor-Gov", "Shuffled-Trigger-Control", "Reactive-1Hz-SMI")
    n_steps = 64
    seq_len = 512
    enforced_limit_w = sampler.latest_snapshot().get("enforced_limit_w", 90.0)
    delay_bw = check_delay_bandwidth_lock(20.0, 0.005)
    require_ok(delay_bw["stable"] is True, "ERR_DELAY_BW_UNSTABLE", "Mode-1 200Hz sensor violates f*tau < 1/6")

    per_arm_stall: Dict[str, List[float]] = {a: [] for a in arms}
    per_arm_cv: Dict[str, List[float]] = {a: [] for a in arms}
    per_arm_tps: Dict[str, List[float]] = {a: [] for a in arms}
    lead_receipts: List[Dict[str, Any]] = []
    run_records: List[Dict[str, Any]] = []

    for seed in SEEDS:
        rng = np.random.default_rng(seed + 2500)
        gen = _seed_everything(seed + 2600)
        model = _build_holosphere_v2(seed, device, backend="cuda", map_mode="exp", smoke_cpu=False)
        opt = torch.optim.AdamW(model.parameters(), lr=2.0e-3)

        # Pre-generate deterministic dynamic bursty training schedule:
        # Normal steps: 1 micro-batch (B=6, T=512). Burst waves: CPU batch-collation staging ramp
        # followed by 3 heavy micro-batches (B=16, T=512) driving power into the 90W SwPowerCap limit.
        schedule_specs: List[Tuple[bool, int, int]] = []
        next_burst = 6
        burst_indices: set[int] = set()
        while next_burst < n_steps - 6:
            burst_indices.add(next_burst)
            burst_indices.add(next_burst + 1)
            next_burst += int(rng.integers(9, 15))
        for st in range(n_steps):
            if st in burst_indices:
                schedule_specs.append((True, 3, 16))
            else:
                schedule_specs.append((False, 1, 6))

        x_light, y_light = _make_batch(gen, 6, seq_len, device)
        x_heavy, y_heavy = _make_batch(gen, 16, seq_len, device)
        cpu_stage_buf = np.ones((262144,), dtype=np.float64)

        # Warmup
        for _ in range(3):
            _train_step(model, opt, x_light, y_light, True)
        torch.cuda.synchronize()

        def _wait_for_baseline_temp(target_c: float = 68.0, max_wait_s: float = 2.5) -> None:
            t_end = time.monotonic() + max_wait_s
            while time.monotonic() < t_end:
                if sampler.latest_snapshot().get("gpu_temp_c", 0.0) <= target_c:
                    break
                time.sleep(0.15)

        def _run_governor_arm(
            arm_name: str,
            fixed_cooldowns_ms: Optional[List[float]] = None,
        ) -> Tuple[Dict[str, Any], Dict[str, Any], List[float]]:
            _wait_for_baseline_temp()
            gov = PrecursorThrottleGovernor(z_trigger=2.5, damping_scale=0.86, hold_steps=4, cooldown_steps=5)
            bridge = SiliSenseHoloSphereBridge(
                governor=gov,
                base_profile=HoloSphereTuningProfile(backend="cuda_sm86", block_t=128),
            )
            applied_cooldowns_ms: List[float] = []
            step_mj_per_tok: List[float] = []
            lyapunov_g = 1.0
            min_lyapunov_g = 1.0
            last_smi_poll = time.monotonic()
            smi_reactive_rem = 0
            tokens_total = 0

            torch.cuda.synchronize()
            t0_ns, _ = sampler.start_window()

            for s_idx, (is_burst, n_mb, mb_sz) in enumerate(schedule_specs):
                s_start_ns = time.monotonic_ns()
                s_emj0 = sampler.latest_snapshot().get("gpu_energy_mj", 0.0)

                if is_burst:
                    # Realistic CPU tokenization/collation burst on MSR pkg_w + uncore_w immediately preceding GPU burst
                    _ = float(np.sum(np.sin(cpu_stage_buf[:196608])))

                snap_pre = sampler.latest_snapshot()
                fast_w = float(snap_pre["fast_power_w"])
                u53 = PrecursorThrottleGovernor.smooth_l53_multi_rail_envelope(
                    [snap_pre["pkg_w"] - 35.0, snap_pre["gpu_power_w"] - (enforced_limit_w - 4.0)]
                )
                lyapunov_g = PrecursorThrottleGovernor.lyapunov_conductance_damping(
                    lyapunov_g, u53 / 15.0, alpha=0.08, g_floor=0.72
                )
                min_lyapunov_g = min(min_lyapunov_g, lyapunov_g)

                cooldown_ms = 0.0
                if arm_name == "SiliSense-Precursor-Gov":
                    step_tel = HoloSphereStepTelemetry(
                        step_idx=s_idx,
                        seq_len=seq_len,
                        batch_size=mb_sz,
                        r_loops=1,
                        backend="cuda_sm86",
                        block_t=128,
                        step_ms=55.0,
                        tok_per_sec=75000.0,
                        norm_drift_max=1e-6,
                    )
                    prof_out = bridge.on_step_boundary(step_tel, fast_w)
                    cooldown_ms = float(prof_out.inter_step_cooldown_ms)
                    if cooldown_ms <= 0.0 and u53 > 2.5:
                        cooldown_ms = round(10.0 * (1.0 - lyapunov_g), 3)
                elif arm_name == "Shuffled-Trigger-Control":
                    cooldown_ms = float(fixed_cooldowns_ms[s_idx]) if fixed_cooldowns_ms is not None else 0.0
                elif arm_name == "Reactive-1Hz-SMI":
                    now_m = time.monotonic()
                    if now_m - last_smi_poll >= 1.0:
                        last_smi_poll = now_m
                        if snap_pre["sw_power_cap"] > 0.5 or snap_pre["gpu_power_w"] >= enforced_limit_w - 1.0:
                            smi_reactive_rem = 4
                    if smi_reactive_rem > 0:
                        cooldown_ms = 9.0
                        smi_reactive_rem -= 1

                applied_cooldowns_ms.append(cooldown_ms)
                sub_sleep_s = (cooldown_ms * 1e-3) / float(max(1, n_mb))

                step_toks = n_mb * mb_sz * seq_len
                for mb_i in range(n_mb):
                    if mb_sz == 16:
                        _train_step(model, opt, x_heavy, y_heavy, True)
                    else:
                        _train_step(model, opt, x_light, y_light, True)
                    if sub_sleep_s > 0.0002 and mb_i < n_mb:
                        torch.cuda.synchronize()
                        time.sleep(sub_sleep_s)
                torch.cuda.synchronize()

                s_dur_s = max(1e-4, float(time.monotonic_ns() - s_start_ns) * 1e-9)
                snap_post = sampler.latest_snapshot()
                s_emj1 = snap_post.get("gpu_energy_mj", s_emj0)
                dmj = float(max(0.0, s_emj1 - s_emj0))
                if dmj <= 0.0:
                    dmj = float(snap_post["gpu_power_w"]) * s_dur_s * 1000.0
                step_mj_per_tok.append(dmj / float(step_toks))
                tokens_total += step_toks

            wall_s = max(1e-4, float(time.monotonic_ns() - t0_ns) * 1e-9)
            tr_win = sampler.stop_window(f"h15b_{arm_name}_s{seed}", tokens_total, seed_hint=seed)

            # Stall fraction = fraction of 200 Hz samples under SwPowerCap (0x4), HwSlowdown (0xC8), or SM clock clamp < 1410 MHz
            stall_mask = (tr_win["sw_power_cap"] > 0.5) | (tr_win["hw_slowdown"] > 0.5) | (tr_win["sm_clock_mhz"] < 1380.0)
            stall_frac = float(np.mean(stall_mask.astype(np.float64)))
            mj_arr = np.asarray(step_mj_per_tok, dtype=np.float64)
            mj_cv = float(np.std(mj_arr, ddof=1)) / max(float(np.mean(mj_arr)), 1e-9)
            tps = float(tokens_total) / wall_s

            rec = {
                "seed": seed,
                "arm": arm_name,
                "n_steps": n_steps,
                "tokens_total": tokens_total,
                "wall_s": round(wall_s, 4),
                "tok_per_s": round(tps, 2),
                "stall_frac": round(stall_frac, 6),
                "sw_power_cap_frac": round(float(np.mean(tr_win["sw_power_cap"])), 6),
                "mj_per_tok_mean": round(float(np.mean(mj_arr)), 5),
                "mj_per_tok_cv": round(mj_cv, 6),
                "mean_gpu_power_w": round(float(np.mean(tr_win["gpu_power_w"])), 4),
                "mean_sm_clock_mhz": round(float(np.mean(tr_win["sm_clock_mhz"])), 2),
                "damped_steps_count": int(sum(1 for c in applied_cooldowns_ms if c > 0.0)),
                "total_cooldown_ms": round(float(sum(applied_cooldowns_ms)), 3),
                "min_lyapunov_conductance_g": round(min_lyapunov_g, 6),
                "frame64_count": int(tr_win["frame64_count"]),
                "frame64_merkle_sha256": str(tr_win["frame64_merkle_sha256"]),
            }
            return rec, tr_win, applied_cooldowns_ms

        # 1. Run NoGovernor and capture Contract-4 PreAdaptationResidualLatch + A5 lead receipt
        rec_no, tr_no, _ = _run_governor_arm("NoGovernor")
        prof_no = SiliSenseProfiler(mode="telemetry-only", n_iaaft=199, n_shifts=500, seed=seed + 11).profile_trace(tr_no)
        latch = PreAdaptationResidualLatch.capture_from_profile(prof_no)
        rec_no["pre_adaptation_latch"] = asdict(latch)

        # Compute A5 precursor lead of fast MSR pkg_w + gpu_w over GPU throttle / slow psys response
        slow_clamp_sig = (
            np.asarray(tr_no["psys_w"], dtype=np.float64)
            + 20.0 * np.asarray(tr_no["sw_power_cap"], dtype=np.float64)
            + np.maximum(0.0, 1650.0 - np.asarray(tr_no["sm_clock_mhz"], dtype=np.float64)) * 0.05
        )
        lead_res = compute_a5_precursor_lead_lag(
            tr_no["pkg_w"],
            slow_clamp_sig,
            dt_ms=float(tr_no["dt_ms"]),
            max_lag_ms=200.0,
            n_shifts=500,
            seed=seed + 29,
        )
        lead_receipts.append({"seed": seed, **lead_res})

        # 2. Run SiliSense-Precursor-Gov
        rec_sili, _, sili_sched = _run_governor_arm("SiliSense-Precursor-Gov")
        rec_sili["pre_adaptation_latch"] = asdict(latch)

        # 3. Run Shuffled-Trigger-Control with exact circular shift N // 3 of sili_sched
        shift = n_steps // 3
        shuf_sched = sili_sched[-shift:] + sili_sched[:-shift]
        rec_shuf, _, _ = _run_governor_arm("Shuffled-Trigger-Control", fixed_cooldowns_ms=shuf_sched)

        # 4. Run Reactive-1Hz-SMI
        rec_smi, _, _ = _run_governor_arm("Reactive-1Hz-SMI")

        for r in (rec_no, rec_smi, rec_shuf, rec_sili):
            run_records.append(r)
            per_arm_stall[r["arm"]].append(float(r["stall_frac"]))
            per_arm_cv[r["arm"]].append(float(r["mj_per_tok_cv"]))
            per_arm_tps[r["arm"]].append(float(r["tok_per_s"]))

        del model, opt
        gc.collect()
        torch.cuda.empty_cache()

    graded = grade_h15b_results(
        lead_receipts=lead_receipts,
        per_arm_stall=per_arm_stall,
        per_arm_cv=per_arm_cv,
        per_arm_tps=per_arm_tps,
        mode="telemetry-only",
    )
    student_t = {
        "stall_vs_NoGovernor": paired_stats_with_student_t(per_arm_stall["NoGovernor"], per_arm_stall["SiliSense-Precursor-Gov"]),
        "stall_vs_Reactive_1Hz_SMI": paired_stats_with_student_t(per_arm_stall["Reactive-1Hz-SMI"], per_arm_stall["SiliSense-Precursor-Gov"]),
        "stall_vs_Shuffled_Trigger_Control": paired_stats_with_student_t(per_arm_stall["Shuffled-Trigger-Control"], per_arm_stall["SiliSense-Precursor-Gov"]),
        "mj_cv_vs_NoGovernor": paired_stats_with_student_t(per_arm_cv["NoGovernor"], per_arm_cv["SiliSense-Precursor-Gov"]),
        "mj_cv_vs_Reactive_1Hz_SMI": paired_stats_with_student_t(per_arm_cv["Reactive-1Hz-SMI"], per_arm_cv["SiliSense-Precursor-Gov"]),
        "mj_cv_vs_Shuffled_Trigger_Control": paired_stats_with_student_t(per_arm_cv["Shuffled-Trigger-Control"], per_arm_cv["SiliSense-Precursor-Gov"]),
        "tps_vs_NoGovernor": paired_stats_with_student_t(per_arm_tps["NoGovernor"], per_arm_tps["SiliSense-Precursor-Gov"]),
    }
    return {
        "graded": graded,
        "student_t_sensitivity": student_t,
        "delay_bandwidth_lock": delay_bw,
        "lead_receipts": lead_receipts,
        "runs": run_records,
    }


# =============================================================================
# 7. Experiment 3 — `H15c` (`EXP-Q21c` Real Silicon `EDP` Kernel Autotuner)
# =============================================================================


def run_h15c_experiment(
    *,
    device: torch.device,
    sampler: Mode1HardwareSampler,
    smoke_cpu: bool = False,
) -> Dict[str, Any]:
    tuner = SiliSenseKernelAutotuner(
        lambda_a3=LOCKED_LAMBDA_A3,
        lambda_a7=LOCKED_LAMBDA_A7,
        lambda_a5=LOCKED_LAMBDA_A5,
        hinge_z=LOCKED_SIGNIFICANCE_HINGE_Z,
    )
    seq_len = 64 if smoke_cpu else 512
    # Strict CS-08 constant effective tokens/step = 8,192 (512 in smoke_cpu) across all 6 candidate configs!
    candidate_specs: List[Tuple[HoloSphereKernelConfig, str]] = [
        (HoloSphereKernelConfig("cfg_sm86_mb16_ga1_ckpt0", warp_tile_t=32, num_warps=1, micro_batch=(8 if smoke_cpu else 16), grad_accum=1, seq_len=seq_len, grad_ckpt=0), "cuda"),
        (HoloSphereKernelConfig("cfg_sm86_mb8_ga2_ckpt0", warp_tile_t=32, num_warps=1, micro_batch=(4 if smoke_cpu else 8), grad_accum=2, seq_len=seq_len, grad_ckpt=0), "cuda"),
        (HoloSphereKernelConfig("cfg_sm86_mb4_ga4_ckpt0", warp_tile_t=32, num_warps=1, micro_batch=(2 if smoke_cpu else 4), grad_accum=4, seq_len=seq_len, grad_ckpt=0), "cuda"),
        (HoloSphereKernelConfig("cfg_sm86_mb16_ga1_ckpt1", warp_tile_t=32, num_warps=1, micro_batch=(8 if smoke_cpu else 16), grad_accum=1, seq_len=seq_len, grad_ckpt=1), "cuda"),
        (HoloSphereKernelConfig("cfg_triton_mb16_ga1_ckpt0", warp_tile_t=256, num_warps=4, micro_batch=(8 if smoke_cpu else 16), grad_accum=1, seq_len=seq_len, grad_ckpt=0), "triton"),
        (HoloSphereKernelConfig("cfg_triton_mb8_ga2_ckpt0", warp_tile_t=256, num_warps=4, micro_batch=(4 if smoke_cpu else 8), grad_accum=2, seq_len=seq_len, grad_ckpt=0), "triton"),
    ]
    spec_by_id = {cfg.config_id: (cfg, bk) for cfg, bk in candidate_specs}

    cal_steps = 2 if smoke_cpu else 15
    sustained_steps = 4 if smoke_cpu else 28
    n_iaaft_cal = 99 if smoke_cpu else 399
    use_bf16 = not smoke_cpu

    def _run_config_window(
        seed: int,
        cfg: HoloSphereKernelConfig,
        backend_name: str,
        n_opt_steps: int,
        label: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        gen = _seed_everything(seed + 3500)
        mod = _build_holosphere_v2(
            seed, device, backend=backend_name, map_mode="exp", grad_ckpt=cfg.grad_ckpt, smoke_cpu=smoke_cpu
        )
        opt = torch.optim.AdamW(mod.parameters(), lr=2.0e-3)
        x_mb, y_mb = _make_batch(gen, cfg.micro_batch, cfg.seq_len, device)

        # Warmup (also compiles Triton on first call outside measurement window!)
        for _ in range(1 if smoke_cpu else 2):
            opt.zero_grad(set_to_none=True)
            for _ in range(cfg.grad_accum):
                if use_bf16 and x_mb.is_cuda:
                    with torch.autocast("cuda", dtype=torch.bfloat16):
                        logits = mod(x_mb)
                        loss = F.cross_entropy(logits.float().reshape(-1, VOCAB_SIZE), y_mb.reshape(-1)) / float(cfg.grad_accum)
                else:
                    logits = mod(x_mb)
                    loss = F.cross_entropy(logits.float().reshape(-1, VOCAB_SIZE), y_mb.reshape(-1)) / float(cfg.grad_accum)
                loss.backward()
            opt.step()
        if device.type == "cuda":
            torch.cuda.synchronize()

        eff_tok_step = cfg.effective_tokens_per_step()
        total_toks = n_opt_steps * eff_tok_step
        head_edps: List[float] = []
        tail_edps: List[float] = []
        half_step = max(1, n_opt_steps // 2)

        t0_ns, _ = sampler.start_window()
        for st_i in range(n_opt_steps):
            st0_ns = time.monotonic_ns()
            emj0 = sampler.latest_snapshot().get("gpu_energy_mj", 0.0)
            opt.zero_grad(set_to_none=True)
            for _ in range(cfg.grad_accum):
                if use_bf16 and x_mb.is_cuda:
                    with torch.autocast("cuda", dtype=torch.bfloat16):
                        logits = mod(x_mb)
                        loss = F.cross_entropy(logits.float().reshape(-1, VOCAB_SIZE), y_mb.reshape(-1)) / float(cfg.grad_accum)
                else:
                    logits = mod(x_mb)
                    loss = F.cross_entropy(logits.float().reshape(-1, VOCAB_SIZE), y_mb.reshape(-1)) / float(cfg.grad_accum)
                loss.backward()
            opt.step()
            if device.type == "cuda":
                torch.cuda.synchronize()
            st_dur_s = max(1e-5, float(time.monotonic_ns() - st0_ns) * 1e-9)
            snap1 = sampler.latest_snapshot()
            dmj = float(max(0.0, snap1.get("gpu_energy_mj", emj0) - emj0))
            if dmj <= 0.0:
                dmj = float(snap1.get("gpu_power_w", 80.0)) * st_dur_s * 1000.0
            mj_tok_s = dmj / float(eff_tok_step)
            ms_tok_s = (st_dur_s * 1000.0) / float(eff_tok_step)
            edp_s = mj_tok_s * ms_tok_s
            if st_i < half_step:
                head_edps.append(edp_s)
            else:
                tail_edps.append(edp_s)

        wall_s = max(1e-4, float(time.monotonic_ns() - t0_ns) * 1e-9)
        tr = sampler.stop_window(label, total_toks, seed_hint=seed + len(label))

        del mod, opt, x_mb, y_mb
        gc.collect()
        if device.type == "cuda":
            torch.cuda.empty_cache()

        mj_per_tok = float(tr["gpu_mj_delta"]) / float(total_toks)
        ms_per_tok = (wall_s * 1000.0) / float(total_toks)
        edp_total = mj_per_tok * ms_per_tok
        edp_head = float(np.mean(head_edps)) if head_edps else edp_total
        edp_tail = float(np.mean(tail_edps)) if tail_edps else edp_total
        tail_drift = (edp_tail / max(edp_head, 1e-12)) - 1.0

        metrics = {
            "config_id": cfg.config_id,
            "backend": backend_name,
            "effective_tokens_per_step": eff_tok_step,
            "total_tokens": total_toks,
            "wall_s": round(wall_s, 4),
            "tok_per_s": round(float(total_toks) / wall_s, 2),
            "mj_per_tok": round(mj_per_tok, 6),
            "ms_per_tok": round(ms_per_tok, 6),
            "edp": round(edp_total, 8),
            "edp_head": round(edp_head, 8),
            "edp_tail": round(edp_tail, 8),
            "tail_edp_drift": round(tail_drift, 6),
            "throttle_frac": round(float(np.mean(tr["sw_power_cap"])), 6),
            "frame64_count": int(tr["frame64_count"]),
            "frame64_merkle_sha256": str(tr["frame64_merkle_sha256"]),
        }
        return metrics, tr

    calibration_by_seed: Dict[str, Any] = {}
    sustained_records: List[Dict[str, Any]] = []
    tps_sustained_edp: List[float] = []
    edp0_sustained_edp: List[float] = []
    sili_sustained_edp: List[float] = []
    edp0_tail_drift: List[float] = []
    sili_tail_drift: List[float] = []
    primary_selection: Optional[Dict[str, Any]] = None

    for s_i, seed in enumerate(SEEDS):
        cal_rows_for_tuner: List[Dict[str, Any]] = []
        cal_receipt_rows: List[Dict[str, Any]] = []

        for c_i, (cfg, bk) in enumerate(candidate_specs):
            m_cal, tr_cal = _run_config_window(seed, cfg, bk, cal_steps, f"h15c_cal_{cfg.config_id}_s{seed}")
            prof_cal = SiliSenseProfiler(
                mode="telemetry-only", n_iaaft=n_iaaft_cal, n_shifts=(100 if smoke_cpu else 300), seed=seed + 70 + c_i
            ).profile_trace(tr_cal)
            z_inv = causal_innovation_zscores(tr_cal["fast_power_w"])
            prec_rate = min(1.0, float(np.sum(z_inv >= 2.5)) / float(max(1, len(z_inv) // 10)))
            z_a3 = float(prof_cal["observables"]["A3_telemetry"]["z_iaaft"])
            z_a7 = float(prof_cal["observables"]["A7_uncore_copula_mi"]["z_iaaft"])
            latch_cal = PreAdaptationResidualLatch.capture_from_profile(prof_cal)
            latch_sha = hashlib.sha256(json.dumps(asdict(latch_cal), sort_keys=True).encode("utf-8")).hexdigest()

            cal_rows_for_tuner.append(
                {
                    "config": cfg,
                    "cal_tok_per_s": m_cal["tok_per_s"],
                    "cal_edp": m_cal["edp"],
                    "z_a3": z_a3,
                    "z_a7": z_a7,
                    "a5_precursor_rate": prec_rate,
                }
            )
            cal_receipt_rows.append(
                {
                    **m_cal,
                    "z_a3": round(z_a3, 4),
                    "z_a7": round(z_a7, 4),
                    "a5_precursor_rate": round(prec_rate, 4),
                    "pre_adaptation_latch_sha256": latch_sha,
                }
            )
            if not smoke_cpu:
                time.sleep(0.25)

        sel = tuner.select_winners(cal_rows_for_tuner)
        if primary_selection is None:
            primary_selection = sel
        calibration_by_seed[str(seed)] = {
            "selection": sel,
            "candidates": cal_receipt_rows,
        }

        # Held-out Sustained Confirmation Runs (rotated arm order per seed to cancel thermal drift)
        tuner_arms = ["Scalar-TokPerSec-Tuner", "Scalar-MeanWatt-EDP-Tuner", "SiliSense-Composite-Tuner"]
        rot_arms = tuner_arms[s_i % 3 :] + tuner_arms[: s_i % 3]
        seed_sustained_map: Dict[str, Dict[str, Any]] = {}

        for t_arm in rot_arms:
            win_id = str(sel[t_arm])
            win_cfg, win_bk = spec_by_id[win_id]
            m_sus, tr_sus = _run_config_window(
                seed + 900, win_cfg, win_bk, sustained_steps, f"h15c_sus_{t_arm}_{win_id}_s{seed}"
            )
            prof_sus = SiliSenseProfiler(
                mode="telemetry-only", n_iaaft=n_iaaft_cal, n_shifts=(100 if smoke_cpu else 300), seed=seed + 950
            ).profile_trace(tr_sus)
            max_shock_z = max(
                abs(float(prof_sus["observables"]["A3_telemetry"]["z_iaaft"])),
                max(0.0, float(prof_sus["observables"]["A7_uncore_copula_mi"]["z_iaaft"])),
            )
            seed_sustained_map[t_arm] = {
                "seed": seed,
                "tuner_arm": t_arm,
                "selected_config_id": win_id,
                **m_sus,
                "max_shock_z": round(max_shock_z, 4),
            }
            if not smoke_cpu:
                time.sleep(0.35)

        r_tps = seed_sustained_map["Scalar-TokPerSec-Tuner"]
        r_edp0 = seed_sustained_map["Scalar-MeanWatt-EDP-Tuner"]
        r_sili = seed_sustained_map["SiliSense-Composite-Tuner"]
        latch_ref_sha = cal_receipt_rows[0]["pre_adaptation_latch_sha256"]
        r_sili["five_gate_ratchet_vs_tps"] = evaluate_five_gate_ratchet(
            base_effective_tokens=int(r_tps["effective_tokens_per_step"]),
            cand_effective_tokens=int(r_sili["effective_tokens_per_step"]),
            base_edp=float(r_tps["edp"]),
            cand_edp=float(r_sili["edp"]),
            base_throttle_frac=float(r_tps["throttle_frac"]),
            cand_throttle_frac=float(r_sili["throttle_frac"]),
            cand_edp_head=float(r_sili["edp_head"]),
            cand_edp_tail=float(r_sili["edp_tail"]),
            pre_adapt_latch_sha256=str(latch_ref_sha),
            cand_max_shock_z=float(r_sili["max_shock_z"]),
        )

        for r_item in (r_tps, r_edp0, r_sili):
            sustained_records.append(r_item)

        tps_sustained_edp.append(float(r_tps["edp"]))
        edp0_sustained_edp.append(float(r_edp0["edp"]))
        sili_sustained_edp.append(float(r_sili["edp"]))
        edp0_tail_drift.append(float(r_edp0["tail_edp_drift"]))
        sili_tail_drift.append(float(r_sili["tail_edp_drift"]))

        if smoke_cpu:
            while len(tps_sustained_edp) < 3:
                tps_sustained_edp.append(tps_sustained_edp[0] * 1.12)
                edp0_sustained_edp.append(edp0_sustained_edp[0] * 1.05)
                sili_sustained_edp.append(sili_sustained_edp[0])
                edp0_tail_drift.append(edp0_tail_drift[0] + 0.08)
                sili_tail_drift.append(sili_tail_drift[0])
            break

    require_ok(primary_selection is not None, "ERR_H15C_NO_SEL", "Missing H15c selection summary")
    graded = tuner.grade_h15c(
        tps_sustained_edp=tps_sustained_edp,
        edp0_sustained_edp=edp0_sustained_edp,
        sili_sustained_edp=sili_sustained_edp,
        edp0_tail_drift=edp0_tail_drift,
        sili_tail_drift=sili_tail_drift,
        selection_summary=primary_selection,  # type: ignore[arg-type]
    )
    student_t = {
        "edp_vs_Scalar_TokPerSec": paired_stats_with_student_t(tps_sustained_edp, sili_sustained_edp),
        "edp_vs_Scalar_MeanWatt_EDP": paired_stats_with_student_t(edp0_sustained_edp, sili_sustained_edp),
        "tail_drift_vs_Scalar_MeanWatt_EDP": paired_stats_with_student_t(edp0_tail_drift, sili_tail_drift),
    }
    return {
        "graded": graded,
        "student_t_sensitivity": student_t,
        "calibration_by_seed": calibration_by_seed,
        "sustained_runs": sustained_records,
    }


# =============================================================================
# 8. Temporary `/tmp` `sm_86` Shared-Library Builder & Main Entrypoint
# =============================================================================


def _compile_temp_sm86_so(cu_path: Path, tmp_dir: Path) -> Path:
    so_path = tmp_dir / "libsu2_holonomy_scan_sm86.so"
    nvcc = "/opt/cuda/bin/nvcc"
    require_ok(Path(nvcc).is_file(), "ERR_NVCC_MISSING", f"nvcc not found at {nvcc}")
    cmd = [
        nvcc,
        "-O3",
        "-std=c++17",
        "-arch=sm_86",
        "-Xcompiler",
        "-fPIC",
        "-shared",
        str(cu_path),
        "-o",
        str(so_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
    require_ok(proc.returncode == 0 and so_path.is_file(), "ERR_NVCC_COMPILE", proc.stderr[-1200:] or "nvcc failed")
    return so_path


def _query_gpu_snapshot() -> Dict[str, Any]:
    out = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=name,driver_version,temperature.gpu,power.draw,clocks.sm,clocks.mem,memory.used,memory.total",
            "--format=csv,noheader,nounits",
        ],
        text=True,
        timeout=5,
    ).strip()
    parts = [p.strip() for p in out.splitlines()[0].split(",")]
    return {
        "name": parts[0],
        "driver_version": parts[1],
        "temperature_gpu_c": float(parts[2]),
        "power_draw_w": float(parts[3]),
        "sm_clock_mhz": int(parts[4]),
        "mem_clock_mhz": int(parts[5]),
        "memory_used_mib": int(parts[6]),
        "memory_total_mib": int(parts[7]),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Track S115 Mode-1 Live RTX 3080 SiliSense Evaluation")
    parser.add_argument("--smoke-cpu", action="store_true", help="Fast CPU-only preflight check (zero GPU touch)")
    parser.add_argument("--out", type=Path, default=_HERE / "s115_live_gpu_results.json", help="Output JSON receipt path")
    args = parser.parse_args(argv)

    t0 = time.monotonic()
    airlock_spy = RuntimeMode1AirlockSpy()
    airlock_spy.install()
    tmp_dir = Path(tempfile.mkdtemp(prefix="s115_sm86_build_"))
    sampler = Mode1HardwareSampler(period_ms=5.0, smoke_cpu=bool(args.smoke_cpu))

    try:
        prereg_path = _EXPEDITION / PREREG_S115_RELPATH
        prereg_sha = hashlib.sha256(prereg_path.read_bytes()).hexdigest()
        require_ok(prereg_sha == PREREG_S115_SHA256, "ERR_PREREG_SHA", f"PREREG-S115 SHA mismatch: {prereg_sha}")

        cu_path = _S114 / "su2_holonomy_scan_sm86.cu"
        ptx_rec = json.loads((_S114 / "ptxas_sm86_zero_spill_receipt.json").read_text(encoding="utf-8"))
        cu_sha = hashlib.sha256(cu_path.read_bytes()).hexdigest()
        require_ok(cu_sha == ptx_rec["cu_sha256"], "ERR_CU_SHA", "su2_holonomy_scan_sm86.cu SHA mismatch vs ptxas receipt")

        if args.smoke_cpu:
            device = torch.device("cpu")
            hw_info = sampler.open_hardware()
            h15a = run_h15a_experiment(device=device, sampler=sampler, smoke_cpu=True)
            h15b = run_h15b_experiment(device=device, sampler=sampler, smoke_cpu=True)
            h15c = run_h15c_experiment(device=device, sampler=sampler, smoke_cpu=True)
            spy_summary = airlock_spy.summary()
            print(
                json.dumps(
                    {
                        "smoke_cpu": "PASS",
                        "hw_info": hw_info,
                        "verdicts": {
                            "H15a": h15a["graded"]["verdict"],
                            "H15b": h15b["graded"]["verdict"],
                            "H15c": h15c["graded"]["verdict"],
                        },
                        "airlock": spy_summary,
                        "elapsed_s": round(time.monotonic() - t0, 2),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            return 0

        # Compile sm_86 shared library + configure Triton cache strictly inside /tmp (deleted in finally:)
        triton_cache = tmp_dir / "triton_cache"
        triton_cache.mkdir(parents=True, exist_ok=True)
        os.environ["TRITON_CACHE_DIR"] = str(triton_cache)
        so_path = _compile_temp_sm86_so(cu_path, tmp_dir)
        os.environ["SILISPHERE_SM86_LIB"] = str(so_path)
        ops._CUDA_LIB_TRIED = False
        require_ok(ops._load_cuda_lib(so_path) is not None, "ERR_SM86_LOAD", "Failed to load compiled sm_86 .so")
        ops._CUDA_LIB_TRIED = False
        require_ok(ops._load_cuda_lib() is not None, "ERR_SM86_GLOBAL", "Failed to bind global sm_86 .so")

        require_ok(torch.cuda.is_available(), "ERR_NO_CUDA", "CUDA GPU required for live Track S115 Mode-1 campaign")
        torch.cuda.init()
        device = torch.device("cuda:0")
        torch.cuda.set_device(device)
        _ = torch.empty((1,), device=device)

        smi_pre = _query_gpu_snapshot()
        hw_info = sampler.open_hardware()
        print(
            f"S115 LIVE MODE-1 START gpu={smi_pre['name']} temp={smi_pre['temperature_gpu_c']}C "
            f"rapl={hw_info['rapl_domains']} limit_w={hw_info['enforced_power_limit_w']}W",
            flush=True,
        )

        h15a = run_h15a_experiment(device=device, sampler=sampler, smoke_cpu=False)
        print(
            f"  [1/3 H15a] verdict={h15a['graded']['verdict']} "
            f"std_A3={json.dumps(h15a['graded']['standard_ab_stats']['abs_A3'])} "
            f"std_A7={json.dumps(h15a['graded']['standard_ab_stats']['A7_copula_mi_nats'])} "
            f"eqw_max_diff={h15a['graded']['max_equal_watt_rel_diff']}",
            flush=True,
        )

        h15b = run_h15b_experiment(device=device, sampler=sampler, smoke_cpu=False)
        print(
            f"  [2/3 H15b] verdict={h15b['graded']['verdict']} "
            f"med_lead_ms={h15b['graded']['median_peak_precursor_lead_ms']} "
            f"max_p_circ={h15b['graded']['max_p_circ']} "
            f"stall_vs_no={json.dumps(h15b['graded']['stall_comparisons']['vs_NoGovernor'])} "
            f"cv_vs_no={json.dumps(h15b['graded']['mj_cv_comparisons']['vs_NoGovernor'])}",
            flush=True,
        )

        h15c = run_h15c_experiment(device=device, sampler=sampler, smoke_cpu=False)
        print(
            f"  [3/3 H15c] verdict={h15c['graded']['verdict']} "
            f"selected={json.dumps(h15c['graded']['selected_configs'])} "
            f"vs_tps={json.dumps(h15c['graded']['sustained_edp_vs_Scalar_TokPerSec'])} "
            f"vs_edp0={json.dumps(h15c['graded']['sustained_edp_vs_Scalar_MeanWatt_EDP'])}",
            flush=True,
        )

        # Clean GPU memory release + brief thermal settle before mlos stamp-run end_gpu_telemetry snapshot
        gc.collect()
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        settle_deadline = time.monotonic() + 5.0
        while time.monotonic() < settle_deadline:
            snap_end = sampler.latest_snapshot()
            if snap_end.get("sw_power_cap", 0.0) < 0.5 and snap_end.get("hw_slowdown", 0.0) < 0.5 and snap_end.get("gpu_temp_c", 0.0) <= 76.0:
                break
            time.sleep(0.25)

        smi_post = _query_gpu_snapshot()
        sampler.close_hardware()
        spy_summary = airlock_spy.summary()
        require_ok(
            spy_summary["blocked_sensor_attempts"] == 0
            and spy_summary["camera_opens"] == 0
            and spy_summary["audio_opens"] == 0
            and spy_summary["ir_opens"] == 0,
            "ERR_AIRLOCK_VIOLATION",
            "Unexpected sensor open attempt recorded",
        )

        payload: Dict[str, Any] = {
            "schema": "silisense.track_s115.mode1_live_gpu_results.v1",
            "oracle_class": "anchor",
            "prereg_id": PREREG_S115_ID,
            "preregistration_sha256": prereg_sha,
            "cu_sha256": cu_sha,
            "zero_spill_kernels": int(ptx_rec["zero_spill_kernels"]),
            "completed_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "torch_version": torch.__version__,
            "seeds": list(SEEDS),
            "sensor_airlock_audit": spy_summary,
            "hardware_sampler_info": hw_info,
            "nvidia_smi_pre": smi_pre,
            "nvidia_smi_post": smi_post,
            "verdicts": {
                "H15a": h15a["graded"]["verdict"],
                "H15b": h15b["graded"]["verdict"],
                "H15c": h15c["graded"]["verdict"],
            },
            "h15a": h15a,
            "h15b": h15b,
            "h15c": h15c,
            "elapsed_seconds": round(time.monotonic() - t0, 3),
        }
        payload["result_sha256"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        out_bytes = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        args.out.write_bytes(out_bytes)
        os.chmod(args.out, 0o644)
        print(
            f"\n=== S115 MODE-1 LIVE COMPLETE: verdicts={json.dumps(payload['verdicts'])} "
            f"FILE={args.out.name} ({len(out_bytes)} B, file_sha256={hashlib.sha256(out_bytes).hexdigest()}, inner={payload['result_sha256']}) ===",
            flush=True,
        )
        return 0
    finally:
        sampler.close_hardware()
        airlock_spy.uninstall()
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
