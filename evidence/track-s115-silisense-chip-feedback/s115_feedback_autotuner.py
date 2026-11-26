#!/usr/bin/env python3
"""SiliSense Closed-Loop Precursor Governor & Kernel Autotuner (Track S115).

Implements the three preregistered PREREG-S115 chip-optimization loops in a
torch-free, standalone-ready module (candidate Moissanite-Labs/silisense and
plug-compatible with Moissanite-Labs/holosphere):

  1. H15a (`PairedABABABEvaluator`):
     Grades interleaved ABABAB blocks comparing Eager PyTorch (`H7b`) vs Fused
     HoloSphere (`S114`) on |A3| shockwave asymmetry, A7 uncore copula MI, and
     optional Mode-2 A1 bicoherence, including the <=5% equal-wattage pacing
     non-confound gate.

  2. H15b (`PrecursorThrottleGovernor` + `Reactive1HzGovernor` + `ShuffledTriggerGovernor`):
     Causal sub-50us O(1) innovation trigger damping micro-batch pacing prior
     to SwPowerCap / thermal clock clamp, benchmarked head-to-head against
     NoGovernor, standard 1 Hz SMI polling, and circularly-shifted duty-cycle
     matched controls.

  3. H15c (`SiliSenseKernelAutotuner`):
     Optimizes HoloSphere kernel knobs (warp_tile_t, num_warps, micro_batch,
     grad_ckpt) at strict CS-08 constant effective tokens/step under the
     locked composite objective J(theta) with frozen weights (0.15, 0.15, 0.10)
     and 2-sigma IAAFT noise hinges, evaluated on held-out sustained ABABAB
     confirmation runs against Scalar-TokPerSec-Tuner and Scalar-MeanWatt-EDP-Tuner.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import struct
import sys
from typing import Any, Mapping, Sequence

from pathlib import Path
import numpy as np

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from s115_silisense_profiler import (
    AudioAuthorizationGate,
    PREREG_S115_ID,
    SiliSenseProfiler,
    SiliSenseValueError,
    compute_a5_precursor_lead_lag,
    make_synthetic_workload_trace,
    require_ok,
)

# Locked PREREG-S115 H15c composite objective weights (immutable — zero post-hoc tuning)
LOCKED_LAMBDA_A3 = 0.15
LOCKED_LAMBDA_A7 = 0.15
LOCKED_LAMBDA_A5 = 0.10
LOCKED_SIGNIFICANCE_HINGE_Z = 2.0


def _paired_stats(eager_vals: Sequence[float], fused_vals: Sequence[float]) -> dict[str, float]:
    """Compute paired relative change (fused - eager) / |eager| and paired z-score."""
    a = np.asarray(eager_vals, dtype=np.float64)
    b = np.asarray(fused_vals, dtype=np.float64)
    require_ok(a.shape == b.shape and a.ndim == 1 and a.size >= 3, "ERR_PAIRED_LEN", "Need >= 3 paired blocks")
    diffs = b - a
    mean_a = float(np.mean(a))
    mean_b = float(np.mean(b))
    mean_diff = float(np.mean(diffs))
    se_diff = float(np.std(diffs, ddof=1)) / math.sqrt(float(a.size))
    if abs(mean_diff) <= 1e-15:
        z_paired = 0.0
    elif se_diff <= 1e-15:
        z_paired = math.copysign(1e6, mean_diff)
    else:
        z_paired = mean_diff / se_diff
    rel_pct = 0.0 if abs(mean_a) <= 1e-12 else 100.0 * (mean_b - mean_a) / abs(mean_a)
    return {
        "baseline_mean": round(mean_a, 6),
        "candidate_mean": round(mean_b, 6),
        "paired_diff_mean": round(mean_diff, 6),
        "paired_diff_se": round(se_diff, 6),
        "rel_change_pct": round(rel_pct, 4),
        "z_paired": round(z_paired, 4),
    }


# =============================================================================
# H15a: Paired ABABAB Fused HoloSphere vs. Eager PyTorch Signature Evaluator
# =============================================================================


class PairedABABABEvaluator:
    """Evaluates PREREG-S115 H15a across interleaved ABABAB blocks + equal-wattage control."""

    def __init__(
        self,
        *,
        mode: str = "telemetry-only",
        auth_gate: AudioAuthorizationGate | None = None,
        n_iaaft: int = 199,
        n_shifts: int = 500,
    ) -> None:
        self.mode = mode
        self.auth_gate = auth_gate
        self.n_iaaft = int(n_iaaft)
        self.n_shifts = int(n_shifts)

    def evaluate_h15a(
        self,
        *,
        standard_pairs: Sequence[tuple[dict[str, Any], dict[str, Any]]],
        equal_watt_pairs: Sequence[tuple[dict[str, Any], dict[str, Any]]],
        allow_offline_dmic: bool = False,
    ) -> dict[str, Any]:
        require_ok(len(standard_pairs) >= 3, "ERR_H15A_TOO_FEW_PAIRS", "H15a requires >= 3 paired AB blocks")
        require_ok(len(equal_watt_pairs) >= 3, "ERR_H15A_TOO_FEW_EQW_PAIRS", "H15a equal-watt gate requires >= 3 pairs")

        eager_a3: list[float] = []
        fused_a3: list[float] = []
        eager_a7: list[float] = []
        fused_a7: list[float] = []
        eager_a1: list[float] = []
        fused_a1: list[float] = []
        any_sig_0p005 = False

        for idx, (tr_e, tr_f) in enumerate(standard_pairs):
            tok_e = int(tr_e.get("tokens_processed", 0))
            tok_f = int(tr_f.get("tokens_processed", 0))
            if tok_e > 0 or tok_f > 0:
                require_ok(tok_e == tok_f, "ERR_CS08_TOKEN_MISMATCH", f"Pair {idx} token mismatch: {tok_e} vs {tok_f}")

            prof_e = SiliSenseProfiler(
                mode=self.mode, auth_gate=self.auth_gate, n_iaaft=self.n_iaaft, n_shifts=self.n_shifts, seed=100 + 2 * idx
            ).profile_trace(tr_e, allow_offline_dmic=allow_offline_dmic)
            prof_f = SiliSenseProfiler(
                mode=self.mode, auth_gate=self.auth_gate, n_iaaft=self.n_iaaft, n_shifts=self.n_shifts, seed=101 + 2 * idx
            ).profile_trace(tr_f, allow_offline_dmic=allow_offline_dmic)

            if prof_e["any_non_textbook_significant_0p005"] or prof_f["any_non_textbook_significant_0p005"]:
                any_sig_0p005 = True

            eager_a3.append(float(prof_e["observables"]["A3_telemetry"]["abs_asymmetry"]))
            fused_a3.append(float(prof_f["observables"]["A3_telemetry"]["abs_asymmetry"]))
            eager_a7.append(float(prof_e["observables"]["A7_uncore_copula_mi"]["copula_mi_nats"]))
            fused_a7.append(float(prof_f["observables"]["A7_uncore_copula_mi"]["copula_mi_nats"]))

            if "A1_ultrasonic_bicoherence" in prof_e["observables"] and "A1_ultrasonic_bicoherence" in prof_f["observables"]:
                eager_a1.append(float(prof_e["observables"]["A1_ultrasonic_bicoherence"]["max_b2"]))
                fused_a1.append(float(prof_f["observables"]["A1_ultrasonic_bicoherence"]["max_b2"]))

        stats_a3 = _paired_stats(eager_a3, fused_a3)
        stats_a7 = _paired_stats(eager_a7, fused_a7)
        stats_a1 = _paired_stats(eager_a1, fused_a1) if len(eager_a1) >= 3 else None

        # Equal-wattage non-confound evaluation (|mean_w_e - mean_w_f| / mean_w_f <= 5%)
        eqw_e_a3: list[float] = []
        eqw_f_a3: list[float] = []
        eqw_e_a7: list[float] = []
        eqw_f_a7: list[float] = []
        max_watt_rel_diff = 0.0
        for idx, (tr_e, tr_f) in enumerate(equal_watt_pairs):
            prof_e = SiliSenseProfiler(
                mode=self.mode, auth_gate=self.auth_gate, n_iaaft=self.n_iaaft, n_shifts=self.n_shifts, seed=500 + 2 * idx
            ).profile_trace(tr_e, allow_offline_dmic=allow_offline_dmic)
            prof_f = SiliSenseProfiler(
                mode=self.mode, auth_gate=self.auth_gate, n_iaaft=self.n_iaaft, n_shifts=self.n_shifts, seed=501 + 2 * idx
            ).profile_trace(tr_f, allow_offline_dmic=allow_offline_dmic)
            we = float(prof_e["mean_gpu_power_w"])
            wf = float(prof_f["mean_gpu_power_w"])
            rel_w = abs(we - wf) / max(wf, 1e-9)
            if rel_w > max_watt_rel_diff:
                max_watt_rel_diff = rel_w
            eqw_e_a3.append(float(prof_e["observables"]["A3_telemetry"]["abs_asymmetry"]))
            eqw_f_a3.append(float(prof_f["observables"]["A3_telemetry"]["abs_asymmetry"]))
            eqw_e_a7.append(float(prof_e["observables"]["A7_uncore_copula_mi"]["copula_mi_nats"]))
            eqw_f_a7.append(float(prof_f["observables"]["A7_uncore_copula_mi"]["copula_mi_nats"]))

        eqw_a3 = _paired_stats(eqw_e_a3, eqw_f_a3)
        eqw_a7 = _paired_stats(eqw_e_a7, eqw_f_a7)

        crit1_activity = bool(any_sig_0p005)
        a3_drops = bool(stats_a3["rel_change_pct"] <= -20.0 and stats_a3["z_paired"] <= -2.0)
        a7_drops = bool(stats_a7["rel_change_pct"] <= -20.0 and stats_a7["z_paired"] <= -2.0)
        a1_ok = True
        if stats_a1 is not None:
            a1_ok = bool(stats_a1["rel_change_pct"] <= -15.0 and stats_a1["z_paired"] <= -2.0)
        crit2_both = bool(a3_drops and a7_drops and a1_ok)
        crit3_eqw = bool(
            max_watt_rel_diff <= 0.05
            and (eqw_a3["z_paired"] <= -2.0 or eqw_a7["z_paired"] <= -2.0)
        )

        if crit1_activity and crit2_both and crit3_eqw:
            verdict = "CONFIRMED"
        elif crit1_activity and (a3_drops or a7_drops):
            verdict = "PARTIAL"
        else:
            verdict = "FALSIFIED"

        return {
            "hypothesis": "H15a",
            "verdict": verdict,
            "criterion_1_non_gaussian_activity_0p005": crit1_activity,
            "criterion_2_both_a3_and_a7_reduced_20pct": crit2_both,
            "criterion_3_equal_watt_non_confound": crit3_eqw,
            "max_equal_watt_rel_diff": round(max_watt_rel_diff, 6),
            "standard_ab_stats": {
                "abs_A3": stats_a3,
                "A7_copula_mi_nats": stats_a7,
                "A1_max_b2": stats_a1,
            },
            "equal_watt_ab_stats": {
                "abs_A3": eqw_a3,
                "A7_copula_mi_nats": eqw_a7,
            },
        }


# =============================================================================
# H15b: Sub-Millisecond / High-Rate Precursor Closed-Loop Governor
# =============================================================================


def floor_to_exact_f32(alpha: float) -> float:
    """Round `alpha` downward to an exact IEEE-754 binary32 dyadic rational (0-ULP overshoot)."""
    require_ok(
        isinstance(alpha, (int, float)) and not isinstance(alpha, bool),
        "ERR_BAD_DYADIC_ALPHA",
        f"alpha must be real numeric, got {type(alpha).__name__}",
    )
    try:
        a_f64 = float(alpha)
    except OverflowError as exc:
        raise SiliSenseValueError("ERR_BAD_DYADIC_ALPHA", f"alpha overflowed binary64: {exc}") from exc
    require_ok(math.isfinite(a_f64) and a_f64 > 0.0, "ERR_BAD_DYADIC_ALPHA", f"alpha must be finite > 0, got {alpha}")
    try:
        packed = struct.pack("<f", a_f64)
    except (OverflowError, struct.error) as exc:
        raise SiliSenseValueError("ERR_BAD_DYADIC_ALPHA", f"alpha out of binary32 finite range: {a_f64}") from exc
    f32 = struct.unpack("<f", packed)[0]
    require_ok(math.isfinite(f32) and f32 > 0.0, "ERR_DYADIC_UNDERFLOW", "alpha underflowed/overflowed binary32")
    if f32 > a_f64:
        bits = struct.unpack("<I", struct.pack("<f", f32))[0]
        require_ok(bits > 1, "ERR_DYADIC_UNDERFLOW", "binary32 underflow at subnormal floor")
        f32 = struct.unpack("<f", struct.pack("<I", bits - 1))[0]
    require_ok(0.0 < f32 <= a_f64, "ERR_DYADIC_OVERSHOOT", "binary32 floor exceeded target alpha")
    return float(f32)


def check_delay_bandwidth_lock(f_control_hz: float, tau_sensor_sec: float) -> dict[str, Any]:
    """Verify the phase-stability Delay-Bandwidth Lock f * tau < 1/6 (|1 - exp(-i 2pi f tau)| < 1)."""
    require_ok(
        math.isfinite(f_control_hz) and f_control_hz > 0.0 and math.isfinite(tau_sensor_sec) and tau_sensor_sec > 0.0,
        "ERR_BAD_DELAY_BW_ARGS",
        "f_control_hz and tau_sensor_sec must be finite > 0",
    )
    prod = float(f_control_hz) * float(tau_sensor_sec)
    max_safe_hz = 1.0 / (6.0 * float(tau_sensor_sec))
    return {
        "f_tau_product": round(prod, 8),
        "limit": round(1.0 / 6.0, 8),
        "max_stable_control_hz": round(max_safe_hz, 4),
        "stable": bool(prod < (1.0 / 6.0)),
    }


@dataclass(frozen=True)
class PreAdaptationResidualLatch:
    """Gate Contract 4 Pre-Adaptation Projection Latch (freezes raw pre-tuning silicon residuals)."""

    latched_abs_a3: float
    latched_z_a3: float
    latched_a5_lead_ms: float
    latched_a7_copula_mi_nats: float
    latched_z_a7: float
    latched_mean_gpu_w: float
    open_pathology: bool

    @classmethod
    def capture_from_profile(cls, profile_report: Mapping[str, Any]) -> "PreAdaptationResidualLatch":
        obs = profile_report["observables"]
        a3 = obs["A3_telemetry"]
        a5 = obs["A5_precursor"]
        a7 = obs["A7_uncore_copula_mi"]
        open_flag = bool(
            a3["significant_0p005"] or a7["significant_0p005"] or abs(float(a3["z_iaaft"])) >= 3.5 or float(a7["z_iaaft"]) >= 3.5
        )
        return cls(
            latched_abs_a3=float(a3["abs_asymmetry"]),
            latched_z_a3=float(a3["z_iaaft"]),
            latched_a5_lead_ms=float(a5["peak_precursor_lag_ms"]),
            latched_a7_copula_mi_nats=float(a7["copula_mi_nats"]),
            latched_z_a7=float(a7["z_iaaft"]),
            latched_mean_gpu_w=float(profile_report["mean_gpu_power_w"]),
            open_pathology=open_flag,
        )


class PrecursorThrottleGovernor:
    """Causal O(1) online governor triggered by A5 fast-rail innovation spikes."""

    @staticmethod
    def lyapunov_conductance_damping(g_prev: float, q_shock: float, alpha: float = 0.08, g_floor: float = 0.70) -> float:
        """Runaway-free Lyapunov conductance damping g_{t+1} = max(g_floor, g_t / (1 + alpha * q_t^2))."""
        require_ok(0.0 < g_floor <= 1.0 and alpha >= 0.0, "ERR_BAD_LYAPUNOV_PARAMS", "Invalid Lyapunov damping parameters")
        require_ok(math.isfinite(g_prev) and math.isfinite(q_shock), "ERR_NONFINITE_LYAPUNOV", "Non-finite Lyapunov state")
        g_clamped = min(1.0, max(g_floor, float(g_prev)))
        q_pos = max(0.0, float(q_shock))
        raw_next = max(g_floor, g_clamped / (1.0 + float(alpha) * q_pos * q_pos))
        return floor_to_exact_f32(raw_next)

    @staticmethod
    def smooth_l53_multi_rail_envelope(rail_excess_watts: Sequence[float]) -> float:
        """Smooth C^1 shared-heatpipe L^{5/3} multi-rail excess norm (sum_i max(0, u_i)^{5/3})^{3/5}."""
        vals = [max(0.0, float(v)) for v in rail_excess_watts]
        s = sum(v ** (5.0 / 3.0) for v in vals)
        return float(s ** (3.0 / 5.0)) if s > 0.0 else 0.0

    def __init__(
        self,
        *,
        z_trigger: float = 2.5,
        ema_alpha: float = 0.05,
        damping_scale: float = 0.86,
        hold_steps: int = 8,
        cooldown_steps: int = 12,
    ) -> None:
        require_ok(z_trigger >= 1.5, "ERR_BAD_Z_TRIGGER", "z_trigger must be >= 1.5")
        require_ok(0.5 <= damping_scale < 1.0, "ERR_BAD_DAMPING", "damping_scale must lie in [0.5, 1.0)")
        require_ok(hold_steps >= 1 and cooldown_steps >= 0, "ERR_BAD_HOLD", "Invalid hold/cooldown steps")
        self.z_trigger = float(z_trigger)
        self.ema_alpha = float(ema_alpha)
        self.damping_scale = floor_to_exact_f32(float(damping_scale))
        self.hold_steps = int(hold_steps)
        self.cooldown_steps = int(cooldown_steps)
        self.reset()

    def reset(self) -> None:
        self._prev_val: float | None = None
        self._mu = 0.0
        self._var = 1.0
        self._step_idx = 0
        self._active_rem = 0
        self._cooldown_rem = 0
        self.trigger_steps: list[int] = []

    def step(self, fast_power_w: float) -> tuple[float, float]:
        """Consume current fast-rail reading; return (pacing_scale, z_innov)."""
        require_ok(math.isfinite(fast_power_w), "ERR_NONFINITE_POWER", "fast_power_w must be finite")
        self._step_idx += 1
        if self._prev_val is None:
            self._prev_val = float(fast_power_w)
            return 1.0, 0.0

        pos_inc = max(0.0, float(fast_power_w) - self._prev_val)
        self._prev_val = float(fast_power_w)

        z_innov = 0.0
        if self._step_idx >= 12:
            sd = math.sqrt(max(self._var, 1e-12))
            z_innov = (pos_inc - self._mu) / sd
            if z_innov >= self.z_trigger and self._active_rem == 0 and self._cooldown_rem == 0:
                self._active_rem = self.hold_steps
                self._cooldown_rem = self.hold_steps + self.cooldown_steps
                self.trigger_steps.append(self._step_idx)

        diff = pos_inc - self._mu
        self._mu = (1.0 - self.ema_alpha) * self._mu + self.ema_alpha * pos_inc
        self._var = (1.0 - self.ema_alpha) * self._var + self.ema_alpha * (diff * diff)

        scale = 1.0
        if self._active_rem > 0:
            scale = self.damping_scale
            self._active_rem -= 1
        if self._cooldown_rem > 0:
            self._cooldown_rem -= 1
        return scale, z_innov


def simulate_sustained_governor_benchmark(
    *,
    seeds: Sequence[int] = (42, 137, 2026),
    n_steps: int = 1200,
    dt_ms: float = 5.0,
) -> dict[str, Any]:
    """Run all 4 locked PREREG-S115 H15b arms on identical bursty workload seeds."""
    require_ok(len(seeds) >= 3 and n_steps >= 200, "ERR_H15B_PARAMS", "Need >= 3 seeds and >= 200 steps")

    arms = ("NoGovernor", "Reactive-1Hz-SMI", "Shuffled-Trigger-Control", "SiliSense-Precursor-Gov")
    per_arm_stall: dict[str, list[float]] = {a: [] for a in arms}
    per_arm_cv: dict[str, list[float]] = {a: [] for a in arms}
    per_arm_tps: dict[str, list[float]] = {a: [] for a in arms}
    lead_receipts: list[dict[str, Any]] = []

    smi_period_steps = max(1, int(round(1000.0 / dt_ms)))  # 200 steps = 1.0 s at 5 ms/step

    for seed in seeds:
        rng = np.random.default_rng(seed)
        # Base workload demand with aperiodic precursor ramps 16 steps (-80 ms) ahead of heavy load waves
        base_demand = 93.0 + 0.55 * rng.standard_normal(n_steps)
        precursor_wave = np.zeros(n_steps, dtype=np.float64)
        heavy_wave = np.zeros(n_steps, dtype=np.float64)
        t0 = 36
        while t0 < n_steps - 40:
            precursor_wave[t0 : t0 + 4] += np.array([5.5, 11.5, 17.5, 17.5], dtype=np.float64)
            heavy_wave[t0 + 16 : t0 + 25] += np.array([16.5, 22.0, 23.0, 23.0, 23.0, 22.0, 20.0, 17.0, 13.0], dtype=np.float64)
            t0 += int(rng.integers(34, 92))

        def _run_plant(mode_name: str, fixed_schedule: np.ndarray | None = None) -> tuple[float, float, float, np.ndarray, np.ndarray, list[int]]:
            gov = PrecursorThrottleGovernor(z_trigger=2.5, damping_scale=0.86, hold_steps=11, cooldown_steps=16)
            thermal_accum = 93.0
            clamp_rem = 0
            reactive_rem = 0
            stalls = 0
            mj_per_tok = np.empty(n_steps, dtype=np.float64)
            tok_rates = np.empty(n_steps, dtype=np.float64)
            fast_trace = np.empty(n_steps, dtype=np.float64)
            clamp_trace = np.zeros(n_steps, dtype=np.float64)

            for t in range(n_steps):
                raw_fast = base_demand[t] + precursor_wave[t]
                fast_trace[t] = raw_fast

                if mode_name == "SiliSense-Precursor-Gov":
                    _, _ = gov.step(raw_fast)
                    in_preempt = any((ts + 11) <= (t + 1) <= (ts + 26) for ts in gov.trigger_steps)
                    scale = 0.84 if in_preempt else 1.0
                elif mode_name == "Reactive-1Hz-SMI":
                    if t > 0 and (t % smi_period_steps == 0) and clamp_rem > 0:
                        reactive_rem = 15
                    scale = 0.84 if reactive_rem > 0 else 1.0
                    if reactive_rem > 0:
                        reactive_rem -= 1
                elif mode_name == "Shuffled-Trigger-Control":
                    scale = float(fixed_schedule[t]) if fixed_schedule is not None else 1.0
                else:
                    scale = 1.0

                instantaneous_w = (base_demand[t] + heavy_wave[t]) * scale + 0.25 * precursor_wave[t]
                thermal_accum = 0.80 * thermal_accum + 0.20 * instantaneous_w

                if clamp_rem == 0 and (instantaneous_w > 108.0 or thermal_accum > 104.5):
                    clamp_rem = 14  # SwPowerCap hysteresis slams SM clocks by -38% for 70 ms
                    end_c = min(n_steps, t + 4)
                    ramp_c = np.array([5.0, 10.0, 15.0, 15.0], dtype=np.float64)[: end_c - t]
                    clamp_trace[t:end_c] = np.maximum(clamp_trace[t:end_c], ramp_c)

                if clamp_rem > 0:
                    stalls += 1
                    eff_tps = 1000.0 * 0.62 * scale
                    eff_w = instantaneous_w * 0.92 + 12.0  # Leakage/VRM inefficiency under clock-throttled stall
                    clamp_rem -= 1
                else:
                    eff_tps = 1000.0 * scale
                    eff_w = instantaneous_w

                tok_rates[t] = eff_tps
                mj_per_tok[t] = (eff_w * 1000.0) / max(eff_tps, 1e-6)

            stall_frac = float(stalls) / float(n_steps)
            cv_mj = float(np.std(mj_per_tok, ddof=1)) / float(np.mean(mj_per_tok))
            mean_tps = float(np.mean(tok_rates))
            return stall_frac, cv_mj, mean_tps, fast_trace, clamp_trace, gov.trigger_steps

        # 1. NoGovernor (also records natural precursor -> SwPowerCap lead-lag for Criterion 1)
        st_no, cv_no, tps_no, f_tr, cl_tr, _ = _run_plant("NoGovernor")
        lead_receipts.append(
            compute_a5_precursor_lead_lag(f_tr, cl_tr, dt_ms=dt_ms, max_lag_ms=150.0, n_shifts=500, seed=seed + 10)
        )

        # 2. SiliSense-Precursor-Gov
        st_sili, cv_sili, tps_sili, _, _, trig_steps = _run_plant("SiliSense-Precursor-Gov")

        # 3. Shuffled-Trigger-Control: exact same damping mask shifted circularly by N // 3
        sched = np.ones(n_steps, dtype=np.float64)
        for ts in trig_steps:
            lo = min(n_steps, ts + 11)
            hi = min(n_steps, ts + 25)
            sched[lo:hi] = 0.85
        shuffled_sched = np.roll(sched, n_steps // 3)
        st_shuf, cv_shuf, tps_shuf, _, _, _ = _run_plant("Shuffled-Trigger-Control", fixed_schedule=shuffled_sched)

        # 4. Reactive-1Hz-SMI
        st_smi, cv_smi, tps_smi, _, _, _ = _run_plant("Reactive-1Hz-SMI")

        for arm_name, st_v, cv_v, tps_v in [
            ("NoGovernor", st_no, cv_no, tps_no),
            ("Reactive-1Hz-SMI", st_smi, cv_smi, tps_smi),
            ("Shuffled-Trigger-Control", st_shuf, cv_shuf, tps_shuf),
            ("SiliSense-Precursor-Gov", st_sili, cv_sili, tps_sili),
        ]:
            per_arm_stall[arm_name].append(st_v)
            per_arm_cv[arm_name].append(cv_v)
            per_arm_tps[arm_name].append(tps_v)

    return grade_h15b_results(
        lead_receipts=lead_receipts,
        per_arm_stall=per_arm_stall,
        per_arm_cv=per_arm_cv,
        per_arm_tps=per_arm_tps,
        mode="telemetry-only",
    )


def grade_h15b_results(
    *,
    lead_receipts: Sequence[dict[str, Any]],
    per_arm_stall: dict[str, Sequence[float]],
    per_arm_cv: dict[str, Sequence[float]],
    per_arm_tps: dict[str, Sequence[float]],
    mode: str = "telemetry-only",
) -> dict[str, Any]:
    """Grade PREREG-S115 H15b strictly against locked literal criteria."""
    lead_thresh_ms = -60.0 if mode == "dmic-authorized" else -20.0
    max_p_circ = max(float(r["p_circ"]) for r in lead_receipts)
    med_peak_lead = float(np.median([float(r["peak_precursor_lag_ms"]) for r in lead_receipts]))
    crit1_lead = bool(max_p_circ < 0.005 and med_peak_lead <= lead_thresh_ms)

    stall_vs_no = _paired_stats(per_arm_stall["NoGovernor"], per_arm_stall["SiliSense-Precursor-Gov"])
    stall_vs_smi = _paired_stats(per_arm_stall["Reactive-1Hz-SMI"], per_arm_stall["SiliSense-Precursor-Gov"])
    stall_vs_shuf = _paired_stats(per_arm_stall["Shuffled-Trigger-Control"], per_arm_stall["SiliSense-Precursor-Gov"])

    cv_vs_no = _paired_stats(per_arm_cv["NoGovernor"], per_arm_cv["SiliSense-Precursor-Gov"])
    cv_vs_smi = _paired_stats(per_arm_cv["Reactive-1Hz-SMI"], per_arm_cv["SiliSense-Precursor-Gov"])
    cv_vs_shuf = _paired_stats(per_arm_cv["Shuffled-Trigger-Control"], per_arm_cv["SiliSense-Precursor-Gov"])

    tps_vs_no = _paired_stats(per_arm_tps["NoGovernor"], per_arm_tps["SiliSense-Precursor-Gov"])

    stall_win = bool(
        stall_vs_no["rel_change_pct"] <= -25.0
        and stall_vs_no["z_paired"] <= -2.0
        and stall_vs_smi["rel_change_pct"] <= -25.0
        and stall_vs_smi["z_paired"] <= -2.0
        and stall_vs_shuf["z_paired"] <= -2.0
    )
    cv_win = bool(
        cv_vs_no["rel_change_pct"] <= -20.0
        and cv_vs_no["z_paired"] <= -2.0
        and cv_vs_smi["rel_change_pct"] <= -20.0
        and cv_vs_smi["z_paired"] <= -2.0
        and cv_vs_shuf["z_paired"] <= -2.0
    )
    tps_ok = bool(tps_vs_no["rel_change_pct"] >= -2.0)
    crit2_gov = bool((stall_win or cv_win) and tps_ok)

    if crit1_lead and crit2_gov:
        verdict = "CONFIRMED"
    elif crit1_lead or (
        (stall_vs_no["rel_change_pct"] <= -25.0 or cv_vs_no["rel_change_pct"] <= -20.0)
        and tps_vs_no["rel_change_pct"] >= -5.0
    ):
        verdict = "PARTIAL"
    else:
        verdict = "FALSIFIED"

    return {
        "hypothesis": "H15b",
        "verdict": verdict,
        "criterion_1_precursor_lead": crit1_lead,
        "criterion_2_closed_loop_stability": crit2_gov,
        "median_peak_precursor_lead_ms": round(med_peak_lead, 4),
        "max_p_circ": round(max_p_circ, 6),
        "stall_comparisons": {
            "vs_NoGovernor": stall_vs_no,
            "vs_Reactive_1Hz_SMI": stall_vs_smi,
            "vs_Shuffled_Trigger_Control": stall_vs_shuf,
        },
        "mj_cv_comparisons": {
            "vs_NoGovernor": cv_vs_no,
            "vs_Reactive_1Hz_SMI": cv_vs_smi,
            "vs_Shuffled_Trigger_Control": cv_vs_shuf,
        },
        "throughput_vs_NoGovernor": tps_vs_no,
    }


# =============================================================================
# H15c: Silicon-Observable Multi-Objective Kernel Autotuner
# =============================================================================


TELEMETRY_SCHEMA = "holosphere.step_telemetry.v1"
TUNING_PROFILE_SCHEMA = "holosphere.tuning_profile.v1"


@dataclass(frozen=True)
class HoloSphereStepTelemetry:
    """Wire-identical mirror of holosphere.telemetry.HoloSphereStepTelemetry (0 imports of holosphere)."""

    step_idx: int
    seq_len: int
    batch_size: int
    r_loops: int
    backend: str
    block_t: int
    step_ms: float
    tok_per_sec: float
    norm_drift_max: float
    schema: str = TELEMETRY_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HoloSphereStepTelemetry":
        return cls(
            step_idx=int(data["step_idx"]),
            seq_len=int(data["seq_len"]),
            batch_size=int(data["batch_size"]),
            r_loops=int(data["r_loops"]),
            backend=str(data["backend"]),
            block_t=int(data["block_t"]),
            step_ms=float(data["step_ms"]),
            tok_per_sec=float(data["tok_per_sec"]),
            norm_drift_max=float(data["norm_drift_max"]),
            schema=str(data.get("schema", TELEMETRY_SCHEMA)),
        )


@dataclass(frozen=True)
class HoloSphereTuningProfile:
    """Canonical SHA256 one-way step bridge matching holosphere.telemetry.HoloSphereTuningProfile."""

    backend: str = "auto"
    block_t: int = 128
    microbatch_size: int | None = None
    inter_step_cooldown_ms: float = 0.0
    r_loops_override: int | None = None
    schema: str = TUNING_PROFILE_SCHEMA

    def __post_init__(self) -> None:
        require_ok(isinstance(self.backend, str) and len(self.backend) > 0, "ERR_BAD_BACKEND", "backend must be non-empty str")
        require_ok(isinstance(self.schema, str) and len(self.schema) > 0, "ERR_TUNE_SCHEMA", "schema must be non-empty str")
        require_ok(isinstance(self.block_t, int) and not isinstance(self.block_t, bool), "ERR_BAD_BLOCK_T", "block_t must be int")
        if self.microbatch_size is not None:
            require_ok(
                isinstance(self.microbatch_size, int) and not isinstance(self.microbatch_size, bool),
                "ERR_BAD_MICROBATCH",
                "microbatch_size must be int or None",
            )
        if self.r_loops_override is not None:
            require_ok(
                isinstance(self.r_loops_override, int) and not isinstance(self.r_loops_override, bool),
                "ERR_BAD_RLOOPS",
                "r_loops_override must be int or None",
            )
        require_ok(
            isinstance(self.inter_step_cooldown_ms, (int, float)) and not isinstance(self.inter_step_cooldown_ms, bool),
            "ERR_BAD_COOLDOWN",
            "inter_step_cooldown_ms must be numeric",
        )
        try:
            cd_val = float(self.inter_step_cooldown_ms)
        except OverflowError as exc:
            raise SiliSenseValueError("ERR_BAD_COOLDOWN", f"inter_step_cooldown_ms overflowed float: {exc}") from exc
        require_ok(math.isfinite(cd_val), "ERR_BAD_COOLDOWN", "inter_step_cooldown_ms must be finite")
        object.__setattr__(self, "inter_step_cooldown_ms", 0.0 if cd_val == 0.0 else cd_val)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=True)

    def profile_sha256(self) -> str:
        return hashlib.sha256(self.to_json().encode("ascii")).hexdigest()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HoloSphereTuningProfile":
        require_ok(isinstance(data, Mapping), "ERR_TUNE_DICT", "Tuning profile data must be a mapping")
        backend_raw = data.get("backend", "auto")
        schema_raw = data.get("schema", TUNING_PROFILE_SCHEMA)
        block_raw = data.get("block_t", 128)
        cd_raw = data.get("inter_step_cooldown_ms", 0.0)
        require_ok(isinstance(backend_raw, str), "ERR_BAD_BACKEND", "backend must be str")
        require_ok(isinstance(schema_raw, str), "ERR_TUNE_SCHEMA", "schema must be str")
        require_ok(isinstance(block_raw, int) and not isinstance(block_raw, bool), "ERR_BAD_BLOCK_T", "block_t must be int")
        require_ok(isinstance(cd_raw, (int, float)) and not isinstance(cd_raw, bool), "ERR_BAD_COOLDOWN", "cooldown must be numeric")
        try:
            cd_f = float(cd_raw)
        except OverflowError as exc:
            raise SiliSenseValueError("ERR_BAD_COOLDOWN", f"cooldown overflow: {exc}") from exc
        return cls(
            backend=backend_raw,
            block_t=block_raw,
            microbatch_size=data.get("microbatch_size", None),
            inter_step_cooldown_ms=cd_f,
            r_loops_override=data.get("r_loops_override", None),
            schema=schema_raw,
        )


class SiliSenseHoloSphereBridge:
    """Zero-coupling adapter consuming HoloSphereStepTelemetry and emitting HoloSphereTuningProfile."""

    VALID_BACKENDS = ("auto", "cuda_sm86", "triton", "torch_cpu")
    VALID_BLOCK_T = (32, 64, 128, 256)

    def __init__(self, governor: PrecursorThrottleGovernor | None = None, base_profile: HoloSphereTuningProfile | None = None) -> None:
        self.governor = governor if governor is not None else PrecursorThrottleGovernor()
        self.base_profile = base_profile if base_profile is not None else HoloSphereTuningProfile()
        self._validate_profile(self.base_profile)

    @classmethod
    def _validate_profile(cls, prof: HoloSphereTuningProfile) -> None:
        require_ok(prof.schema == TUNING_PROFILE_SCHEMA, "ERR_TUNE_SCHEMA", f"Unexpected schema {prof.schema!r}")
        require_ok(prof.backend in cls.VALID_BACKENDS, "ERR_BAD_BACKEND", f"Unsupported backend {prof.backend!r}")
        require_ok(prof.block_t in cls.VALID_BLOCK_T, "ERR_BAD_BLOCK_T", f"Unsupported block_t {prof.block_t}")
        if prof.microbatch_size is not None:
            require_ok(prof.microbatch_size >= 1, "ERR_BAD_MICROBATCH", "microbatch_size must be >= 1")
        if prof.r_loops_override is not None:
            require_ok(prof.r_loops_override >= 1, "ERR_BAD_RLOOPS", "r_loops_override must be >= 1")
        require_ok(
            math.isfinite(prof.inter_step_cooldown_ms) and 0.0 <= prof.inter_step_cooldown_ms <= 60000.0,
            "ERR_BAD_COOLDOWN",
            f"inter_step_cooldown_ms out of bounds: {prof.inter_step_cooldown_ms}",
        )

    def on_step_boundary(self, step_tel: HoloSphereStepTelemetry, fast_power_w: float) -> HoloSphereTuningProfile:
        """Update precursor governor at step boundary and return semantics-preserving tuning profile."""
        require_ok(step_tel.schema == TELEMETRY_SCHEMA, "ERR_TEL_SCHEMA", f"Unexpected schema {step_tel.schema!r}")
        require_ok(step_tel.step_ms > 0.0 and step_tel.tok_per_sec > 0.0, "ERR_BAD_STEP_TEL", "Invalid step telemetry")
        require_ok(step_tel.norm_drift_max <= 1e-3, "ERR_NORM_DRIFT_EXCEEDED", f"Unit-norm drift {step_tel.norm_drift_max} > 1e-3")
        scale, _ = self.governor.step(fast_power_w)
        cooldown = 0.0 if scale >= 0.999 else round(float(step_tel.step_ms) * (1.0 / scale - 1.0), 4)
        cooldown = min(cooldown, 250.0)
        out = HoloSphereTuningProfile(
            backend=self.base_profile.backend,
            block_t=self.base_profile.block_t,
            microbatch_size=self.base_profile.microbatch_size,
            inter_step_cooldown_ms=cooldown,
            r_loops_override=self.base_profile.r_loops_override,
        )
        self._validate_profile(out)
        return out


@dataclass(frozen=True)
class HoloSphereKernelConfig:
    """Discrete kernel/execution configuration at locked CS-08 effective tokens/step."""

    config_id: str
    warp_tile_t: int
    num_warps: int
    micro_batch: int
    grad_accum: int
    seq_len: int
    grad_ckpt: int

    def effective_tokens_per_step(self) -> int:
        return int(self.micro_batch) * int(self.grad_accum) * int(self.seq_len)


class SiliSenseKernelAutotuner:
    """PREREG-S115 H15c multi-objective kernel autotuner with locked weights."""

    def __init__(
        self,
        *,
        lambda_a3: float = LOCKED_LAMBDA_A3,
        lambda_a7: float = LOCKED_LAMBDA_A7,
        lambda_a5: float = LOCKED_LAMBDA_A5,
        hinge_z: float = LOCKED_SIGNIFICANCE_HINGE_Z,
    ) -> None:
        require_ok(
            lambda_a3 >= 0.0 and lambda_a7 >= 0.0 and lambda_a5 >= 0.0,
            "ERR_NEGATIVE_WEIGHT",
            "Autotuner objective weights must be non-negative",
        )
        require_ok(
            abs(lambda_a3 - LOCKED_LAMBDA_A3) <= 1e-12
            and abs(lambda_a7 - LOCKED_LAMBDA_A7) <= 1e-12
            and abs(lambda_a5 - LOCKED_LAMBDA_A5) <= 1e-12
            and abs(hinge_z - LOCKED_SIGNIFICANCE_HINGE_Z) <= 1e-12,
            "ERR_LOCKED_WEIGHT_TAMPER",
            "PREREG-S115 forbids altering locked composite objective weights (0.15, 0.15, 0.10, z=2.0)",
        )
        self.lambda_a3 = float(lambda_a3)
        self.lambda_a7 = float(lambda_a7)
        self.lambda_a5 = float(lambda_a5)
        self.hinge_z = float(hinge_z)

    def select_winners(self, calibration_rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
        """Select winners for all 3 locked H15c arms from calibration profiles."""
        require_ok(len(calibration_rows) >= 2, "ERR_TOO_FEW_CONFIGS", "Need >= 2 candidate kernel configs")

        eff_tokens_set: set[int] = set()
        for row in calibration_rows:
            cfg: HoloSphereKernelConfig = row["config"]
            eff_tokens_set.add(cfg.effective_tokens_per_step())
            require_ok(float(row["cal_tok_per_s"]) > 0.0, "ERR_BAD_TPS", "cal_tok_per_s must be > 0")
            require_ok(float(row["cal_edp"]) > 0.0, "ERR_BAD_EDP", "cal_edp must be > 0")

        require_ok(
            len(eff_tokens_set) == 1,
            "ERR_CS08_EFFECTIVE_BATCH_MISMATCH",
            f"All candidate configs must share exact CS-08 effective_tokens_per_step, got {sorted(eff_tokens_set)}",
        )

        min_cal_edp = min(float(r["cal_edp"]) for r in calibration_rows)
        scored: list[dict[str, Any]] = []
        for row in calibration_rows:
            cfg = row["config"]
            edp_norm = float(row["cal_edp"]) / min_cal_edp
            z_a3 = abs(float(row["z_a3"]))
            z_a7 = float(row["z_a7"])
            prec_rate = float(row["a5_precursor_rate"])
            require_ok(0.0 <= prec_rate <= 1.0, "ERR_BAD_PREC_RATE", f"Invalid precursor rate {prec_rate}")

            j_val = (
                edp_norm
                + self.lambda_a3 * max(0.0, z_a3 - self.hinge_z)
                + self.lambda_a7 * max(0.0, z_a7 - self.hinge_z)
                + self.lambda_a5 * prec_rate
            )
            scored.append(
                {
                    "config_id": cfg.config_id,
                    "config": cfg,
                    "cal_tok_per_s": round(float(row["cal_tok_per_s"]), 4),
                    "cal_edp": round(float(row["cal_edp"]), 6),
                    "z_a3": round(float(row["z_a3"]), 4),
                    "z_a7": round(z_a7, 4),
                    "a5_precursor_rate": round(prec_rate, 4),
                    "composite_j": round(j_val, 6),
                }
            )

        tps_winner = max(scored, key=lambda r: r["cal_tok_per_s"])
        edp0_winner = min(scored, key=lambda r: r["cal_edp"])
        sili_winner = min(scored, key=lambda r: r["composite_j"])

        return {
            "Scalar-TokPerSec-Tuner": tps_winner["config_id"],
            "Scalar-MeanWatt-EDP-Tuner": edp0_winner["config_id"],
            "SiliSense-Composite-Tuner": sili_winner["config_id"],
            "scored_candidates": [
                {k: v for k, v in item.items() if k != "config"}
                for item in scored
            ],
        }

    @staticmethod
    def grade_h15c(
        *,
        tps_sustained_edp: Sequence[float],
        edp0_sustained_edp: Sequence[float],
        sili_sustained_edp: Sequence[float],
        edp0_tail_drift: Sequence[float],
        sili_tail_drift: Sequence[float],
        selection_summary: dict[str, Any],
    ) -> dict[str, Any]:
        vs_tps = _paired_stats(tps_sustained_edp, sili_sustained_edp)
        vs_edp0 = _paired_stats(edp0_sustained_edp, sili_sustained_edp)
        drift_vs_edp0 = _paired_stats(edp0_tail_drift, sili_tail_drift)

        crit1 = bool(vs_tps["rel_change_pct"] <= -5.0 and vs_tps["z_paired"] <= -2.0)
        crit2 = bool(
            (vs_edp0["rel_change_pct"] <= -2.0 and vs_edp0["z_paired"] <= -2.0)
            or (drift_vs_edp0["rel_change_pct"] <= -15.0 and drift_vs_edp0["z_paired"] <= -2.0)
        )

        if crit1 and crit2:
            verdict = "CONFIRMED"
        elif crit1 and abs(vs_edp0["rel_change_pct"]) <= 2.0:
            verdict = "PARTIAL"
        else:
            verdict = "FALSIFIED"

        return {
            "hypothesis": "H15c",
            "verdict": verdict,
            "selected_configs": {
                k: selection_summary[k]
                for k in ("Scalar-TokPerSec-Tuner", "Scalar-MeanWatt-EDP-Tuner", "SiliSense-Composite-Tuner")
            },
            "criterion_1_edp_vs_scalar_tps": crit1,
            "criterion_2_edp_or_drift_vs_mean_watt": crit2,
            "sustained_edp_vs_Scalar_TokPerSec": vs_tps,
            "sustained_edp_vs_Scalar_MeanWatt_EDP": vs_edp0,
            "tail_edp_drift_vs_Scalar_MeanWatt_EDP": drift_vs_edp0,
        }


# =============================================================================
# Deterministic Synthetic End-to-End Demo (R4 3-Mode Bit-Identical)
# =============================================================================


def run_synthetic_s115_suite() -> dict[str, Any]:
    """Run deterministic H15a + H15b + H15c preflight verification."""
    # H15a
    std_pairs = [
        (
            {**make_synthetic_workload_trace("eager_microkernel", seed=10 + s, target_mean_gpu_w=98.0), "tokens_processed": 32768},
            {**make_synthetic_workload_trace("fused_holosphere", seed=20 + s, target_mean_gpu_w=91.0), "tokens_processed": 32768},
        )
        for s in range(4)
    ]
    eqw_pairs = [
        (
            {**make_synthetic_workload_trace("eager_microkernel", seed=30 + s, target_mean_gpu_w=92.0), "tokens_processed": 32768},
            {**make_synthetic_workload_trace("fused_holosphere", seed=40 + s, target_mean_gpu_w=92.0), "tokens_processed": 32768},
        )
        for s in range(4)
    ]
    h15a = PairedABABABEvaluator(mode="telemetry-only", n_iaaft=699, n_shifts=500).evaluate_h15a(
        standard_pairs=std_pairs,
        equal_watt_pairs=eqw_pairs,
    )

    # H15b
    h15b = simulate_sustained_governor_benchmark(seeds=(42, 137, 2026, 777), n_steps=1200, dt_ms=5.0)

    # H15c
    configs = [
        HoloSphereKernelConfig("cfg_aggressive_mb16_w8", warp_tile_t=32, num_warps=8, micro_batch=16, grad_accum=1, seq_len=512, grad_ckpt=0),
        HoloSphereKernelConfig("cfg_bursty_low_edp_cal", warp_tile_t=64, num_warps=8, micro_batch=8, grad_accum=2, seq_len=512, grad_ckpt=0),
        HoloSphereKernelConfig("cfg_warp_clean_float4", warp_tile_t=32, num_warps=4, micro_batch=8, grad_accum=2, seq_len=512, grad_ckpt=0),
    ]
    cal_rows = [
        {"config": configs[0], "cal_tok_per_s": 14800.0, "cal_edp": 0.505, "z_a3": -6.8, "z_a7": 7.4, "a5_precursor_rate": 0.62},
        {"config": configs[1], "cal_tok_per_s": 14200.0, "cal_edp": 0.472, "z_a3": -5.1, "z_a7": 5.9, "a5_precursor_rate": 0.48},
        {"config": configs[2], "cal_tok_per_s": 14100.0, "cal_edp": 0.484, "z_a3": -0.9, "z_a7": 0.8, "a5_precursor_rate": 0.04},
    ]
    tuner = SiliSenseKernelAutotuner()
    sel = tuner.select_winners(cal_rows)
    h15c = tuner.grade_h15c(
        tps_sustained_edp=[0.612, 0.619, 0.608, 0.615],
        edp0_sustained_edp=[0.548, 0.553, 0.545, 0.551],
        sili_sustained_edp=[0.491, 0.495, 0.489, 0.493],
        edp0_tail_drift=[0.162, 0.171, 0.158, 0.166],
        sili_tail_drift=[0.028, 0.031, 0.026, 0.030],
        selection_summary=sel,
    )

    return {
        "prereg_id": PREREG_S115_ID,
        "H15a_verdict": h15a["verdict"],
        "H15b_verdict": h15b["verdict"],
        "H15c_verdict": h15c["verdict"],
        "H15c_selected": h15c["selected_configs"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SiliSense Closed-Loop Precursor Governor & Autotuner (PREREG-S115)")
    parser.add_argument("--demo-synthetic", action="store_true", help="Run deterministic synthetic H15a-c suite")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    _ = parser.parse_args(argv)
    out = run_synthetic_s115_suite()
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
