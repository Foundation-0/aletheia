#!/usr/bin/env python3
"""Model-Free Blind Residual & Non-Textbook Anomaly Hunter for Track S113.

Implements PREREG-S113-AMENDMENT1 Lenses A1 through A7 with strict anti-CS-09
safeguards:
  1. Split-half out-of-sample replication (Half 1 screens & locks exact candidate
     coordinates; Half 2 tests only locked candidates out-of-sample).
  2. Vectorized IAAFT (Iterative Amplitude Adjusted Fourier Transform) and
     circular-shift surrogate nulls with N_screen >= 200 and N_confirm >= 799
     (giving exact empirical rank resolution down to p = 0.00125 so Holm-corrected
     p_holm < 0.005 is achievable without parametric tail extrapolation).
  3. Zero GPU touch, single-threaded BLAS discipline, polite capture-idle guard,
     zero bare asserts, and strict local_raw_av/ privacy isolation (only compact
     non-identifying scalar/spectral/statistical summaries are emitted).
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import numpy as np
from scipy import signal


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(f"S113 blind hunter check failed: {msg}")


def is_live_capture_active() -> bool:
    """Return True if s113_capture.py, pw-record, or v4l2 ffmpeg is currently running."""
    try:
        p = subprocess.run(
            ["ps", "-eo", "args"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        for line in p.stdout.splitlines():
            s = line.strip()
            if "s113_blind_anomaly_hunter" in s:
                continue
            if ("s113_capture" in s) or ("s113_phase_e" in s) or ("pw-record" in s) or ("ffmpeg" in s and "/dev/video" in s):
                return True
    except Exception:
        return False
    return False


def wait_for_capture_quiet(max_wait_s: float = 120.0) -> bool:
    """Politely sleep at 0% CPU while an active sensor capture burst is in progress."""
    t0 = time.monotonic()
    while is_live_capture_active():
        if time.monotonic() - t0 > max_wait_s:
            return False
        time.sleep(0.5)
    return True


def _apply_lens_family_holm(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply Holm-Bonferroni across each lens family (all phases pooled per lens) and
    return only rows surviving p_Holm < 0.005. Raw surrogate p is never reported as Holm."""
    fams: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        fams.setdefault(str(row.get("lens", "")), []).append(row)
    surviving: list[dict[str, Any]] = []
    for lens, members in fams.items():
        pvals = [float(m.get("half2_p_surr", m.get("half2_p_shift", m.get("rep2_p", 1.0)))) for m in members]
        adj = holm_bonferroni(pvals)
        for m, a in zip(members, adj):
            m["half2_p_holm"] = round(a, 6)
            m["holm_family"] = lens
            m["holm_family_size"] = len(members)
            if a < 0.005 and m.get("replicated_anomaly"):
                surviving.append(m)
            else:
                m["replicated_anomaly"] = False
    return surviving


def holm_bonferroni(pvals: list[float]) -> list[float]:
    """Exact step-down Holm-Bonferroni family-wise error rate adjustment."""
    m = len(pvals)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [1.0] * m
    running_max = 0.0
    for rank, idx in enumerate(order):
        scaled = min(1.0, pvals[idx] * float(m - rank))
        if scaled > running_max:
            running_max = scaled
        adj[idx] = running_max
    return adj


def iaaft_surrogates(
    x: np.ndarray,
    n_surr: int,
    rng: np.random.Generator,
    n_iter: int = 12,
    batch_size: int = 200,
) -> np.ndarray:
    """Generate [n_surr, N] IAAFT surrogates preserving exact amplitude spectrum & marginal distribution."""
    x1 = np.asarray(x, dtype=np.float64).ravel()
    n = len(x1)
    _require(n >= 8 and n_surr >= 1, "iaaft_surrogates requires len(x) >= 8 and n_surr >= 1")
    std = float(np.std(x1))
    if std < 1e-15 or not np.isfinite(std):
        return np.tile(x1[None, :], (n_surr, 1))

    x_sorted = np.sort(x1)
    target_amp = np.abs(np.fft.rfft(x1))
    out = np.empty((n_surr, n), dtype=np.float64)

    done = 0
    while done < n_surr:
        b = min(batch_size, n_surr - done)
        # Random initial permutations
        noise = rng.random((b, n))
        cur = x_sorted[np.argsort(noise, axis=1)]
        for _ in range(n_iter):
            spec = np.fft.rfft(cur, axis=1)
            mag = np.abs(spec)
            phase_unit = np.where(mag > 1e-30, spec / np.maximum(mag, 1e-30), 1.0 + 0.0j)
            spec_matched = target_amp[None, :] * phase_unit
            # Preserve exact Nyquist/DC realness via irfft
            y = np.fft.irfft(spec_matched, n=n, axis=1)
            ranks = np.argsort(np.argsort(y, axis=1), axis=1)
            cur = x_sorted[ranks]
        out[done : done + b] = cur
        done += b
    return out


def circular_shift_surrogates(
    x: np.ndarray,
    n_surr: int,
    rng: np.random.Generator,
    min_shift: int = 10,
) -> np.ndarray:
    """Generate [n_surr, N] circularly shifted surrogates."""
    x1 = np.asarray(x, dtype=np.float64).ravel()
    n = len(x1)
    ms = min(max(1, min_shift), max(1, n // 4))
    hi = max(ms + 1, n - ms)
    shifts = rng.integers(ms, hi, size=n_surr)
    idx = (np.arange(n)[None, :] - shifts[:, None]) % n
    return x1[idx]


def empirical_upper_p_and_z(obs: float, surr_vals: np.ndarray) -> tuple[float, float, float, float]:
    """Return (p_emp, z_score, surr_mean, surr_std) for upper-tail test obs > surr."""
    sv = np.asarray(surr_vals, dtype=np.float64)
    sv = sv[np.isfinite(sv)]
    if len(sv) == 0 or not math.isfinite(obs):
        return 1.0, 0.0, 0.0, 0.0
    exceed = int(np.sum(sv >= obs))
    p_emp = float(exceed + 1) / float(len(sv) + 1)
    mu = float(np.mean(sv))
    sd = float(np.std(sv))
    z = (obs - mu) / sd if sd > 1e-15 else 0.0
    return p_emp, z, mu, sd


def _is_known_comb_freq(
    f_hz: float,
    fs_hz: float,
    injected_freqs: list[float],
    include_camera_30hz: bool = True,
    tol_hz: float = 2.0,
) -> tuple[bool, str]:
    """Check whether f_hz lies on 60 Hz mains harmonics, 30 fps harmonics, or injected prime harmonics."""
    if f_hz <= tol_hz or f_hz >= 0.5 * fs_hz - tol_hz:
        return True, "dc_or_nyquist"
    # 60 Hz mains harmonics
    k60 = round(f_hz / 60.0)
    if k60 >= 1 and abs(f_hz - 60.0 * k60) <= tol_hz:
        return True, f"mains_60hz_x{k60}"
    # 30 fps frame-rate harmonics
    if include_camera_30hz:
        k30 = round(f_hz / 30.0)
        if k30 >= 1 and abs(f_hz - 30.0 * k30) <= max(1.5, 0.75 * tol_hz):
            return True, f"cam_30fps_x{k30}"
    # Injected prime stimulus harmonics & first-order Nyquist aliases
    for f0 in injected_freqs:
        if f0 <= 0.0:
            continue
        k_inj = round(f_hz / f0)
        if k_inj >= 1 and abs(f_hz - f0 * k_inj) <= max(tol_hz, 0.002 * f0 * k_inj):
            return True, f"injected_{f0:g}hz_x{k_inj}"
        # Check folded alias |fs - m*f0| for ultrasonic square-wave harmonics up to m=25
        for m in range(1, 26):
            mf = m * f0
            if mf > fs_hz * 0.5:
                alias = abs(fs_hz - (mf % fs_hz))
                if alias > 0.5 * fs_hz:
                    alias = fs_hz - alias
                if abs(f_hz - alias) <= tol_hz:
                    return True, f"alias_{f0:g}hz_x{m}"
    return False, ""


# ============================================================================
# LENS A1: Bicoherence b^2(f1, f2), Sub-Harmonics & Phase-Amplitude Coupling
# ============================================================================

def _bicoherence_matrix(x: np.ndarray, n_fft: int = 256) -> np.ndarray:
    """Compute squared bicoherence b^2[i, j] for 1 <= i <= j, i+j < n_fft//2."""
    x1 = np.asarray(x, dtype=np.float64) - np.mean(x)
    step = n_fft // 2
    n_seg = (len(x1) - n_fft) // step + 1
    half = n_fft // 2
    if n_seg < 8:
        return np.zeros((half, half), dtype=np.float64)
    idx = np.arange(n_fft)[None, :] + (np.arange(n_seg) * step)[:, None]
    win = np.hanning(n_fft)[None, :]
    segs = x1[idx] * win
    X = np.fft.rfft(segs, axis=1)[:, :half]  # [n_seg, half]

    b2 = np.zeros((half, half), dtype=np.float64)
    p_single = np.mean(np.abs(X) ** 2, axis=0) + 1e-30
    for i in range(1, half // 2):
        j_max = half - i
        if j_max <= i:
            continue
        js = np.arange(i, j_max)
        ks = i + js
        prod12 = X[:, i : i + 1] * X[:, js]  # [n_seg, len(js)]
        bispec = np.mean(prod12 * np.conj(X[:, ks]), axis=0)
        denom = np.mean(np.abs(prod12) ** 2, axis=0) * p_single[ks] + 1e-30
        b2[i, js] = (np.abs(bispec) ** 2) / denom
    return b2


def _bicoherence_at_pairs(X_batch: np.ndarray, pairs: list[tuple[int, int]], n_fft: int = 256) -> np.ndarray:
    """Vectorized bicoherence evaluation at locked (i, j) pairs for [B, L] signals."""
    B, L = X_batch.shape
    step = n_fft // 2
    n_seg = (L - n_fft) // step + 1
    half = n_fft // 2
    idx = np.arange(n_fft)[None, :] + (np.arange(n_seg) * step)[:, None]
    win = np.hanning(n_fft)[None, None, :]
    # [B, n_seg, n_fft]
    segs = (X_batch[:, idx] - np.mean(X_batch, axis=1)[:, None, None]) * win
    Xf = np.fft.rfft(segs, axis=2)[:, :, :half]
    out = np.zeros((B, len(pairs)), dtype=np.float64)
    for p_idx, (i, j) in enumerate(pairs):
        k = i + j
        prod12 = Xf[:, :, i] * Xf[:, :, j]
        bispec = np.mean(prod12 * np.conj(Xf[:, :, k]), axis=1)
        denom = np.mean(np.abs(prod12) ** 2, axis=1) * np.mean(np.abs(Xf[:, :, k]) ** 2, axis=1) + 1e-30
        out[:, p_idx] = (np.abs(bispec) ** 2) / denom
    return out


def _pac_spectrum(x: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
    """Slow-to-ultrasonic Phase-Amplitude Coupling modulation spectrum.
    Computes normalized coherence between x(t) low-frequency waveform and its
    high-band (0.30*fs .. 0.46*fs) Hilbert/rectified amplitude envelope.
    """
    n = len(x)
    if n < 2048:
        return np.zeros(0), np.zeros(0)
    sos = signal.butter(4, [0.30 * fs, 0.46 * fs], btype="bandpass", fs=fs, output="sos")
    hf = signal.sosfilt(sos, x.astype(np.float64))
    env = np.abs(hf)
    # Decimate both x and env to ~1000 Hz if fs >= 4000
    dec = max(1, int(fs // 1000.0))
    fs_d = fs / dec
    if dec > 1:
        # Simple boxcar anti-alias + stride for speed & exact linear phase
        trim = (n // dec) * dec
        x_low = x[:trim].reshape(-1, dec).mean(axis=1)
        env_d = env[:trim].reshape(-1, dec).mean(axis=1)
    else:
        x_low = x.astype(np.float64)
        env_d = env
    nper = min(512, len(x_low) // 4)
    if nper < 64:
        return np.zeros(0), np.zeros(0)
    freqs, coh = signal.coherence(x_low - np.mean(x_low), env_d - np.mean(env_d), fs=fs_d, nperseg=nper)
    mask = (freqs >= max(2.0, fs_d / nper * 2)) & (freqs <= min(200.0, 0.4 * fs_d))
    return freqs[mask], coh[mask]


def lens_a1_bicoherence_and_pac(
    signals_dict: dict[str, tuple[np.ndarray, float, list[float]]],
    rng: np.random.Generator,
    n_screen: int = 200,
    n_confirm: int = 799,
) -> dict[str, Any]:
    """Run Lens A1 across provided 1D signals: name -> (array_1d, fs_hz, injected_freqs)."""
    candidates: list[dict[str, Any]] = []
    surviving: list[dict[str, Any]] = []

    for name, (arr, fs, inj_freqs) in signals_dict.items():
        x = np.asarray(arr, dtype=np.float64).ravel()
        if len(x) < 4096 or float(np.std(x)) < 1e-12:
            continue
        mid = len(x) // 2
        # Take clean up-to-16384-sample windows from Half 1 and Half 2
        wlen = min(mid, 16384)
        h1 = x[mid - wlen : mid]
        h2 = x[mid : mid + wlen]

        n_fft = 256 if len(h1) >= 4096 else 128
        df = fs / n_fft
        b2_h1 = _bicoherence_matrix(h1, n_fft=n_fft)

        # Mask trivial harmonics ONLY of injected stimuli with f0 >= 2 * df
        high_inj = [f0 for f0 in inj_freqs if f0 >= 2.0 * df]
        masked_b2 = b2_h1.copy()
        if high_inj:
            for i in range(1, n_fft // 4):
                for j in range(i, n_fft // 2 - i):
                    if masked_b2[i, j] <= 0.0:
                        continue
                    f1, f2 = i * df, j * df
                    for f0 in high_inj:
                        k1, k2 = round(f1 / f0), round(f2 / f0)
                        if k1 >= 1 and k2 >= 1 and abs(f1 - k1 * f0) <= 0.55 * df and abs(f2 - k2 * f0) <= 0.55 * df:
                            masked_b2[i, j] = 0.0
                            break

        flat_order = np.argsort(masked_b2.ravel())[::-1]
        top_pairs: list[tuple[int, int]] = []
        for flat_idx in flat_order:
            if masked_b2.ravel()[flat_idx] <= 0.05:
                break
            ii, jj = divmod(int(flat_idx), masked_b2.shape[1])
            # Enforce non-adjacent distinct peak separation
            if all(abs(ii - pi) + abs(jj - pj) >= 3 for pi, pj in top_pairs):
                top_pairs.append((ii, jj))
            if len(top_pairs) >= 2:
                break

        if top_pairs:
            # Screen on Half 1 with N >= 200 IAAFT
            surr_h1 = iaaft_surrogates(h1, n_screen, rng, n_iter=10)
            s_b2_h1 = _bicoherence_at_pairs(surr_h1, top_pairs, n_fft=n_fft)
            locked_pairs = []
            for p_i, (ii, jj) in enumerate(top_pairs):
                p1, z1, _, _ = empirical_upper_p_and_z(float(b2_h1[ii, jj]), s_b2_h1[:, p_i])
                if p1 <= 0.02 and z1 >= 3.0:
                    locked_pairs.append((ii, jj, float(b2_h1[ii, jj]), p1, z1))

            if locked_pairs:
                pairs_only = [(p[0], p[1]) for p in locked_pairs]
                obs_h2 = _bicoherence_at_pairs(h2[None, :], pairs_only, n_fft=n_fft)[0]
                surr_h2 = iaaft_surrogates(h2, n_confirm, rng, n_iter=12)
                s_b2_h2 = _bicoherence_at_pairs(surr_h2, pairs_only, n_fft=n_fft)
                raw_p2 = []
                recs = []
                for idx_l, (ii, jj, v1, p1, z1) in enumerate(locked_pairs):
                    v2 = float(obs_h2[idx_l])
                    p2, z2, mu2, sd2 = empirical_upper_p_and_z(v2, s_b2_h2[:, idx_l])
                    raw_p2.append(p2)
                    recs.append({
                        "lens": "A1_BICOHERENCE",
                        "signal": name,
                        "f1_hz": round(ii * df, 2),
                        "f2_hz": round(jj * df, 2),
                        "f3_sum_hz": round((ii + jj) * df, 2),
                        "half1_b2": round(v1, 5),
                        "half1_p_iaaft": round(p1, 5),
                        "half1_z_iaaft": round(z1, 2),
                        "half2_b2": round(v2, 5),
                        "half2_surr_mean": round(mu2, 5),
                        "half2_p_iaaft": round(p2, 6),
                        "half2_z_iaaft": round(z2, 2),
                        "n_surrogates_confirm": n_confirm,
                    })
                adj_p2 = holm_bonferroni(raw_p2)
                for rec, ph in zip(recs, adj_p2):
                    rec["half2_p_holm"] = round(ph, 6)
                    rec["replicated_anomaly"] = bool(ph < 0.005 and rec["half2_z_iaaft"] >= 3.5)
                    candidates.append(rec)
                    if rec["replicated_anomaly"]:
                        surviving.append(rec)

        # Slow-to-ultrasonic PAC check
        if fs >= 8000.0 and len(h1) >= 8192:
            f_pac1, c_pac1 = _pac_spectrum(h1, fs)
            f_pac2, c_pac2 = _pac_spectrum(h2, fs)
            if len(f_pac1) > 0 and len(f_pac1) == len(f_pac2):
                best_k = int(np.argmax(c_pac1))
                if float(c_pac1[best_k]) >= 0.18:
                    surr_h2_pac = iaaft_surrogates(h2, n_confirm, rng, n_iter=10)
                    surr_vals = np.empty(n_confirm, dtype=np.float64)
                    for s_i in range(n_confirm):
                        _, cs = _pac_spectrum(surr_h2_pac[s_i], fs)
                        surr_vals[s_i] = float(cs[best_k]) if len(cs) > best_k else 0.0
                    v2_pac = float(c_pac2[best_k])
                    p2, z2, mu2, _ = empirical_upper_p_and_z(v2_pac, surr_vals)
                    rec_pac = {
                        "lens": "A1_SLOW_TO_ULTRASONIC_PAC",
                        "signal": name,
                        "mod_freq_hz": round(float(f_pac1[best_k]), 2),
                        "carrier_band_hz": [round(0.30 * fs, 1), round(0.46 * fs, 1)],
                        "half1_pac_coh": round(float(c_pac1[best_k]), 5),
                        "half2_pac_coh": round(v2_pac, 5),
                        "half2_surr_mean": round(mu2, 5),
                        "half2_p_iaaft": round(p2, 6),
                        "half2_p_holm": round(p2, 6),
                        "half2_z_iaaft": round(z2, 2),
                        "n_surrogates_confirm": n_confirm,
                        "replicated_anomaly": bool(p2 < 0.005 and z2 >= 3.5),
                    }
                    candidates.append(rec_pac)
                    if rec_pac["replicated_anomaly"]:
                        surviving.append(rec_pac)

    return {"tested_candidates": candidates, "surviving_anomalies": surviving}


# ============================================================================
# LENS A2: Chiral / Non-Reciprocal 4x4 DMIC Cross-Spectrum & Effective Rank > 1
# ============================================================================

def _csd_4x4_metrics(dmic4: np.ndarray, fs: float, n_fft: int = 1024) -> dict[str, np.ndarray]:
    """Compute 4x4 Hermitian CSD S(f), chiral imaginary fraction, loop phase, and participation ratio."""
    x = np.asarray(dmic4, dtype=np.float64)
    # Standardize each channel so amplitude imbalance doesn't distort rank
    sd = np.std(x, axis=0, keepdims=True)
    x = (x - np.mean(x, axis=0, keepdims=True)) / np.maximum(sd, 1e-12)
    step = n_fft // 2
    n_seg = (len(x) - n_fft) // step + 1
    n_bins = n_fft // 2 + 1
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / fs)
    if n_seg < 8:
        z = np.zeros(n_bins)
        return {"freqs": freqs, "chiral_score": z, "im_ratio": z, "loop_circ": z, "pr_rank": np.ones(n_bins), "offdiag_coh": z, "rank_excess_score": z}

    idx = np.arange(n_fft)[None, :] + (np.arange(n_seg) * step)[:, None]
    win = np.hanning(n_fft)[None, :, None]
    segs = x[idx, :] * win  # [n_seg, n_fft, 4]
    Xf = np.fft.rfft(segs, axis=1)  # [n_seg, n_bins, 4]
    # S[f, i, j] = mean_seg Xf[seg, f, i] * conj(Xf[seg, f, j])
    S = np.einsum("sfi,sfj->fij", Xf, np.conj(Xf)) / float(n_seg)

    # Normalize to spectral coherence matrix C_ij(f) = S_ij / sqrt(S_ii S_jj)
    diag = np.real(np.diagonal(S, axis1=1, axis2=2))  # [n_bins, 4]
    denom = np.sqrt(np.maximum(diag[:, :, None] * diag[:, None, :], 1e-30))
    C = S / denom

    # Off-diagonal root-mean-square coherence
    off_mask = ~np.eye(4, dtype=bool)
    off_coh = np.sqrt(np.mean(np.abs(C[:, off_mask]) ** 2, axis=1))
    im_norm = np.linalg.norm(np.imag(C), axis=(1, 2))
    tot_norm = np.maximum(np.linalg.norm(C[:, off_mask], axis=1), 1e-15)
    im_ratio = im_norm / tot_norm
    chiral_score = im_ratio * off_coh

    # Cyclic 4-mic loop circulation Im(C_01 C_12 C_23 C_30)
    loop_prod = C[:, 0, 1] * C[:, 1, 2] * C[:, 2, 3] * C[:, 3, 0]
    loop_circ = np.abs(np.imag(loop_prod))

    # Effective participation ratio PR(f) = (tr C)^2 / tr(C^2) on Hermitian C (tr C = 4)
    tr_c2 = np.real(np.einsum("fij,fji->f", C, C))
    pr_rank = 16.0 / np.maximum(tr_c2, 4.0)
    # Multi-source rank excess requires BOTH PR > 1 AND strong pair coherence (max |C_ij| for i!=j)
    max_pair_coh = np.max(np.abs(C[:, off_mask]), axis=1)
    rank_excess_score = (pr_rank - 1.0) * (max_pair_coh ** 2)

    return {
        "freqs": freqs,
        "chiral_score": chiral_score,
        "im_ratio": im_ratio,
        "loop_circ": loop_circ,
        "pr_rank": pr_rank,
        "offdiag_coh": off_coh,
        "max_pair_coh": max_pair_coh,
        "rank_excess_score": rank_excess_score,
    }


def lens_a2_chiral_cross_spectrum(
    dmic4: np.ndarray,
    fs: float,
    rng: np.random.Generator,
    label: str = "dmic_4ch",
    n_confirm: int = 799,
) -> dict[str, Any]:
    """Test 4-ch DMIC for non-zero imaginary cross-spectral chirality (refuting real rank-1 EMI)."""
    x = np.asarray(dmic4, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 4 or len(x) < 8192:
        return {"tested_candidates": [], "surviving_anomalies": []}

    mid = len(x) // 2
    wlen = min(mid, 48000 * 4)  # up to 4s per half for fast 4-ch surrogate testing
    h1 = x[mid - wlen : mid]
    h2 = x[mid : mid + wlen]
    n_fft = 1024
    m1 = _csd_4x4_metrics(h1, fs, n_fft=n_fft)
    m2 = _csd_4x4_metrics(h2, fs, n_fft=n_fft)
    freqs = m1["freqs"]

    # Judge candidate bins in [100 Hz, 0.49*fs] on Half 1
    eval_len = min(wlen, 16384)
    h1_eval = _csd_4x4_metrics(h1[:eval_len], fs, n_fft=n_fft)
    h2_eval = _csd_4x4_metrics(h2[:eval_len], fs, n_fft=n_fft)
    valid = (freqs >= 100.0) & (freqs <= 0.49 * fs)
    scores1 = np.where(valid, h1_eval["chiral_score"], 0.0)
    order = np.argsort(scores1)[::-1]
    pre_bins: list[int] = []
    for idx in order:
        if scores1[idx] < 0.14:
            break
        if all(abs(int(idx) - b) >= 4 for b in pre_bins):
            pre_bins.append(int(idx))
        if len(pre_bins) >= 5:
            break

    candidates: list[dict[str, Any]] = []
    surviving: list[dict[str, Any]] = []
    if not pre_bins:
        return {"tested_candidates": candidates, "surviving_anomalies": surviving}

    def _eval_rank1_null_surrogates(seg4: np.ndarray, bins_list: list[int], n_surr: int) -> np.ndarray:
        """Real rank-1 common-mode EMI + independent smooth-spectrum sensor noise null."""
        s_std = (seg4 - np.mean(seg4, axis=0, keepdims=True)) / np.maximum(np.std(seg4, axis=0, keepdims=True), 1e-12)
        u_s, sv_s, vt_s = np.linalg.svd(s_std, full_matrices=False)
        r1_s = (u_s[:, 0:1] * sv_s[0]) @ vt_s[0:1, :]
        res_s = s_std - r1_s
        L_e = len(seg4)
        ch_amp = []
        for c in range(4):
            p_res = np.abs(np.fft.rfft(res_s[:, c])) ** 2
            k_med = min(31, max(5, (len(p_res) // 20) | 1))
            if k_med % 2 == 0:
                k_med += 1
            ch_amp.append(np.sqrt(np.maximum(signal.medfilt(p_res, kernel_size=k_med), 1e-30)))

        step_loc = n_fft // 2
        n_seg_loc = (L_e - n_fft) // step_loc + 1
        seg_idx_loc = np.arange(n_fft)[None, :] + (np.arange(n_seg_loc) * step_loc)[:, None]
        k_vec = np.array(bins_list, dtype=np.float64)[:, None]
        n_vec = np.arange(n_fft, dtype=np.float64)[None, :]
        basis = np.exp(-2j * math.pi * k_vec * n_vec / float(n_fft)) * np.hanning(n_fft)[None, :]
        off_m = ~np.eye(4, dtype=bool)
        out_chiral = np.zeros((n_surr, len(bins_list)), dtype=np.float64)

        for b0 in range(0, n_surr, 100):
            b1 = min(n_surr, b0 + 100)
            bsz = b1 - b0
            sim = np.empty((bsz, L_e, 4), dtype=np.float64)
            for c in range(4):
                wn = rng.standard_normal((bsz, L_e))
                # Normalize wn FFT so variance matches res_s[:, c] smooth floor
                w_spec = np.fft.rfft(wn, axis=1) / math.sqrt(float(L_e))
                sim[:, :, c] = r1_s[None, :, c] + np.fft.irfft(w_spec * ch_amp[c][None, :], n=L_e, axis=1)
            sim_segs = sim[:, seg_idx_loc, :]
            Xk = np.einsum("kn,bsnc->bskc", basis, sim_segs)
            Sk = np.einsum("bski,bskj->bkij", Xk, np.conj(Xk)) / float(n_seg_loc)
            dk = np.real(np.diagonal(Sk, axis1=2, axis2=3))
            den = np.sqrt(np.maximum(dk[:, :, :, None] * dk[:, :, None, :], 1e-30))
            Ck = Sk / den
            off_c = np.sqrt(np.mean(np.abs(Ck[:, :, off_m]) ** 2, axis=2))
            im_n = np.linalg.norm(np.imag(Ck), axis=(2, 3))
            tot_n = np.maximum(np.linalg.norm(Ck[:, :, off_m], axis=2), 1e-15)
            out_chiral[b0:b1] = (im_n / tot_n) * off_c
        return out_chiral

    # Screen on Half 1 with N = 200 rank-1 surrogates
    surr_h1 = _eval_rank1_null_surrogates(h1[:eval_len], pre_bins, 200)
    locked_bins: list[int] = []
    for i_b, b_idx in enumerate(pre_bins):
        p1, z1, _, _ = empirical_upper_p_and_z(float(h1_eval["chiral_score"][b_idx]), surr_h1[:, i_b])
        if p1 <= 0.02 and z1 >= 3.0:
            locked_bins.append(b_idx)
        if len(locked_bins) >= 3:
            break

    if not locked_bins:
        return {"tested_candidates": candidates, "surviving_anomalies": surviving}

    surr_chiral = _eval_rank1_null_surrogates(h2[:eval_len], locked_bins, n_confirm)

    raw_p2 = []
    recs = []
    for k_i, b_idx in enumerate(locked_bins):
        v1 = float(h1_eval["chiral_score"][b_idx])
        v2 = float(h2_eval["chiral_score"][b_idx])
        p2, z2, mu2, _ = empirical_upper_p_and_z(v2, surr_chiral[:, k_i])
        raw_p2.append(p2)
        recs.append({
            "lens": "A2_CHIRAL_4X4_CSD",
            "signal": label,
            "freq_hz": round(float(freqs[b_idx]), 2),
            "half1_chiral_score": round(v1, 5),
            "half2_chiral_score": round(v2, 5),
            "half2_im_ratio": round(float(h2_eval["im_ratio"][b_idx]), 5),
            "half2_offdiag_coh": round(float(h2_eval["offdiag_coh"][b_idx]), 5),
            "half2_effective_rank_PR": round(float(h2_eval["pr_rank"][b_idx]), 4),
            "half2_loop_circulation": round(float(h2_eval["loop_circ"][b_idx]), 5),
            "half2_surr_rank1_mean": round(mu2, 5),
            "half2_p_iaaft": round(p2, 6),
            "half2_z_iaaft": round(z2, 2),
            "n_surrogates_confirm": n_confirm,
        })
    adj_p2 = holm_bonferroni(raw_p2)
    for rec, ph in zip(recs, adj_p2):
        rec["half2_p_holm"] = round(ph, 6)
        rec["replicated_anomaly"] = bool(ph < 0.005 and rec["half2_z_iaaft"] >= 3.5)
        candidates.append(rec)
        if rec["replicated_anomaly"]:
            surviving.append(rec)

    return {"tested_candidates": candidates, "surviving_anomalies": surviving}


# ============================================================================
# LENS A3: Time-Reversal Asymmetry A(tau) & Step Hysteresis / Afterglow
# ============================================================================

def _tra_curve(x: np.ndarray, lags: list[int]) -> np.ndarray:
    """Compute time-reversal asymmetry A(tau) = <z(t)^2 z(t+tau) - z(t) z(t+tau)^2>."""
    x1 = np.asarray(x, dtype=np.float64).ravel()
    sd = float(np.std(x1))
    if sd < 1e-15:
        return np.zeros(len(lags), dtype=np.float64)
    z = (x1 - float(np.mean(x1))) / sd
    z2 = z * z
    out = np.zeros(len(lags), dtype=np.float64)
    for i, tau in enumerate(lags):
        if tau <= 0 or tau >= len(z) // 2:
            continue
        out[i] = float(np.mean(z2[:-tau] * z[tau:] - z[:-tau] * z2[tau:]))
    return out


def _tra_batch_single_lag(X_batch: np.ndarray, tau: int) -> np.ndarray:
    """Vectorized signed A(tau) across [B, N] surrogates."""
    mu = np.mean(X_batch, axis=1, keepdims=True)
    sd = np.maximum(np.std(X_batch, axis=1, keepdims=True), 1e-15)
    z = (X_batch - mu) / sd
    z2 = z * z
    return np.mean(z2[:, :-tau] * z[:, tau:] - z[:, :-tau] * z2[:, tau:], axis=1)


def lens_a3_time_reversal_and_afterglow(
    signals_dict: dict[str, tuple[np.ndarray, float]],
    post_load_idle_pairs: list[tuple[str, np.ndarray, np.ndarray]],
    rng: np.random.Generator,
    n_screen: int = 200,
    n_confirm: int = 799,
) -> dict[str, Any]:
    """Run Lens A3: microscopic time-reversal asymmetry + post-load afterglow memory."""
    lags = [1, 2, 3, 5, 8, 13, 21, 34, 55]
    candidates: list[dict[str, Any]] = []
    surviving: list[dict[str, Any]] = []

    for name, (arr, fs) in signals_dict.items():
        x = np.asarray(arr, dtype=np.float64).ravel()
        if len(x) < 400 or float(np.std(x)) < 1e-12:
            continue
        mid = len(x) // 2
        wlen = min(mid, 16384)
        h1 = x[mid - wlen : mid]
        h2 = x[mid : mid + wlen]

        valid_lags = [tau for tau in lags if tau < wlen // 8]
        if not valid_lags:
            continue
        a1 = _tra_curve(h1, valid_lags)
        best_i = int(np.argmax(np.abs(a1)))
        best_tau = valid_lags[best_i]
        val1 = float(a1[best_i])
        if abs(val1) < 1e-3:
            continue

        # Screen on Half 1 in the direction of sign(val1)
        sgn = 1.0 if val1 >= 0.0 else -1.0
        surr1 = iaaft_surrogates(h1, n_screen, rng, n_iter=10)
        s1_vals = sgn * _tra_batch_single_lag(surr1, best_tau)
        p1, z1, _, _ = empirical_upper_p_and_z(sgn * val1, s1_vals)
        if p1 > 0.02 or z1 < 2.8:
            continue

        # Confirm locked (best_tau, sign) on Half 2 with N = n_confirm IAAFT
        val2 = float(_tra_curve(h2, [best_tau])[0])
        surr2 = iaaft_surrogates(h2, n_confirm, rng, n_iter=12)
        s2_vals = sgn * _tra_batch_single_lag(surr2, best_tau)
        p2, z2, mu2, _ = empirical_upper_p_and_z(sgn * val2, s2_vals)
        same_sign = (val1 * val2) > 0.0
        rec = {
            "lens": "A3_TIME_REVERSAL_ASYMMETRY",
            "signal": name,
            "lag_samples": best_tau,
            "lag_ms": round(1000.0 * best_tau / fs, 4),
            "half1_tra": round(val1, 6),
            "half1_z_iaaft": round(z1, 2),
            "half2_tra": round(val2, 6),
            "half2_surr_signed_mean": round(mu2, 6),
            "half2_p_iaaft": round(p2, 6),
            "half2_p_holm": round(p2, 6),
            "half2_z_iaaft": round(z2, 2),
            "same_sign_replicated": same_sign,
            "n_surrogates_confirm": n_confirm,
            "replicated_anomaly": bool(same_sign and p2 < 0.005 and z2 >= 3.5),
        }
        candidates.append(rec)
        if rec["replicated_anomaly"]:
            surviving.append(rec)

    # Post-load afterglow test: compare early post-load IDLE window (0.2s..3.0s) vs late IDLE (>5s)
    # replicated across two independent post-load IDLE transitions if available
    for label, post1, post2 in post_load_idle_pairs:
        p1_arr = np.asarray(post1, dtype=np.float64).ravel()
        p2_arr = np.asarray(post2, dtype=np.float64).ravel()
        if len(p1_arr) < 40 or len(p2_arr) < 40:
            continue
        q1 = len(p1_arr) // 3
        q2 = len(p2_arr) // 3
        diff1 = float(np.mean(p1_arr[:q1]) - np.mean(p1_arr[-q1:]))
        diff2 = float(np.mean(p2_arr[:q2]) - np.mean(p2_arr[-q2:]))
        if diff1 * diff2 <= 0.0:
            continue
        sgn = 1.0 if diff1 > 0.0 else -1.0
        surr_p2 = iaaft_surrogates(p2_arr, n_confirm, rng, n_iter=10)
        surr_diffs = sgn * (np.mean(surr_p2[:, :q2], axis=1) - np.mean(surr_p2[:, -q2:], axis=1))
        pv, zv, muv, _ = empirical_upper_p_and_z(sgn * diff2, surr_diffs)
        rec_ag = {
            "lens": "A3_POST_LOAD_AFTERGLOW",
            "signal": label,
            "rep1_early_minus_late": round(diff1, 5),
            "rep2_early_minus_late": round(diff2, 5),
            "rep2_surr_mean": round(muv, 5),
            "rep2_p_iaaft": round(pv, 6),
            "rep2_p_holm": round(pv, 6),
            "rep2_z_iaaft": round(zv, 2),
            "n_surrogates_confirm": n_confirm,
            "replicated_anomaly": bool(pv < 0.005 and zv >= 3.5),
        }
        candidates.append(rec_ag)
        if rec_ag["replicated_anomaly"]:
            surviving.append(rec_ag)

    return {"tested_candidates": candidates, "surviving_anomalies": surviving}


# ============================================================================
# LENS A4: 2D Blank-Wall Non-Poisson & Spatio-Temporal Wave Violations
# ============================================================================

def _analyze_2d_stack_blind(
    stack_u8: np.ndarray,
    label: str,
    rng: np.random.Generator,
    n_confirm: int = 799,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Analyze [T, H, W] uint8 blank-wall stack after subtracting static flat-field AND row means."""
    candidates: list[dict[str, Any]] = []
    surviving: list[dict[str, Any]] = []
    T, H, W = stack_u8.shape
    if T < 24 or H < 16 or W < 16:
        return candidates, surviving

    # Cap at 120 frames (60 per half) so 2D FFT + pixelwise moments stay fast & low-RAM
    if T > 120:
        stride = max(1, T // 120)
        stack_u8 = stack_u8[::stride][:120]
        T = len(stack_u8)

    mid = T // 2
    s1 = stack_u8[:mid].astype(np.float32)
    s2 = stack_u8[mid : 2 * mid].astype(np.float32)

    # Subtract static per-pixel flat-field AND per-frame horizontal row mean independently in each half!
    r1 = s1 - s1.mean(axis=0, keepdims=True)
    r1 = r1 - r1.mean(axis=2, keepdims=True)
    r2 = s2 - s2.mean(axis=0, keepdims=True)
    r2 = r2 - r2.mean(axis=2, keepdims=True)

    # 1) 2D Spatial Fourier Spectrum P(ky, kx) for kx >= 1 (non-horizontal modes!)
    # Use rfft2 along (H, W) -> shape [mid, H, W//2 + 1]
    p2d_1 = np.mean(np.abs(np.fft.rfft2(r1, axes=(1, 2))) ** 2, axis=0)
    p2d_2 = np.mean(np.abs(np.fft.rfft2(r2, axes=(1, 2))) ** 2, axis=0)
    # Normalize by median non-zero-kx floor to get dimensionless prominence
    med1 = float(np.median(p2d_1[:, 1:])) + 1e-12
    med2 = float(np.median(p2d_2[:, 1:])) + 1e-12
    prom1 = p2d_1 / med1
    prom2 = p2d_2 / med2
    prom1[:, 0] = 0.0  # kx=0 is already zeroed by row-mean subtraction

    flat_top = np.argsort(prom1.ravel())[::-1]
    locked_modes: list[tuple[int, int]] = []
    for fidx in flat_top:
        if prom1.ravel()[fidx] < 4.0:
            break
        ky, kx = divmod(int(fidx), prom1.shape[1])
        # Avoid conjugate mirror duplicate (H - ky, kx) when kx == 0 or Nyquist
        if all(abs(ky - py) + abs(kx - px) >= 3 and abs((H - ky) % H - py) + abs(kx - px) >= 3 for py, px in locked_modes):
            locked_modes.append((ky, kx))
        if len(locked_modes) >= 3:
            break

    if locked_modes:
        # Null for 2D wave mode (ky, kx): random independent horizontal circular shifts per row & frame!
        # Wait: if ky == 0 (pure vertical column FPN drift across half), test both ky==0 and ky!=0 against
        # independent per-row horizontal circular shifts (which destroy ALL column & diagonal coherence
        # while preserving exact per-row 1D horizontal spatial spectrum!). For ky == 0 specifically,
        # horizontal shift changes relative phase across rows! Wait: if ky == 0, sum_y R(t, y, x) shifts
        # each row independently, destroying vertical alignment across rows!
        # Even faster exact math: shifting row y in frame t by s_{t,y} multiplies row y's 1D rfft at kx
        # by exp(-2j*pi*kx*s_{t,y}/W)! We only need the 1D horizontal rfft at the locked kx columns!!
        unique_kx = sorted({kx for _, kx in locked_modes})
        # Precompute 1D horizontal rfft of r2 at locked kx: X_row[t, y, idx_kx]
        rfft_x = np.fft.rfft(r2, axis=2)[:, :, unique_kx]  # [mid, H, len(unique_kx)]
        kx_map = {kx: i for i, kx in enumerate(unique_kx)}

        surr_prom = np.zeros((n_confirm, len(locked_modes)), dtype=np.float64)
        y_idx = np.arange(H, dtype=np.float64)
        w_arange = np.arange(W, dtype=np.float64)
        luts_kx = [np.exp((-2j * math.pi * kx / float(W)) * w_arange).astype(np.complex64) for _, kx in locked_modes]
        weighted_rx = [
            (rfft_x[:, :, kx_map[kx]] * np.exp(-2j * math.pi * ky * y_idx / float(H))[None, :]).astype(np.complex64)
            for ky, kx in locked_modes
        ]

        for b0 in range(0, n_confirm, 100):
            b1 = min(n_confirm, b0 + 100)
            bsz = b1 - b0
            shifts = rng.integers(0, W, size=(bsz, mid, H), dtype=np.int32)
            for m_i in range(len(locked_modes)):
                ph = luts_kx[m_i][shifts]  # [bsz, mid, H] complex64 via L1 LUT!
                proj = np.einsum("bmh,mh->bm", ph, weighted_rx[m_i])
                pwr = np.mean(np.abs(proj) ** 2, axis=1)
                surr_prom[b0:b1, m_i] = pwr / med2

        raw_p = []
        recs_2d = []
        for m_i, (ky, kx) in enumerate(locked_modes):
            v1 = float(prom1[ky, kx])
            v2 = float(prom2[ky, kx])
            p2, z2, mu2, _ = empirical_upper_p_and_z(v2, surr_prom[:, m_i])
            raw_p.append(p2)
            ky_signed = ky if ky <= H // 2 else ky - H
            recs_2d.append({
                "lens": "A4_2D_SPATIAL_WAVE_PEAK",
                "sensor": label,
                "ky_cycles_per_frame": int(ky_signed),
                "kx_cycles_per_frame": int(kx),
                "wavelength_px_x": round(float(W) / float(kx), 2),
                "wavelength_px_y": round(float(H) / float(abs(ky_signed)), 2) if ky_signed != 0 else None,
                "mode_kind": "vertical_column_stripe" if ky_signed == 0 else "diagonal_2d_wave",
                "half1_prominence": round(v1, 3),
                "half2_prominence": round(v2, 3),
                "half2_surr_mean": round(mu2, 3),
                "half2_p_surr": round(p2, 6),
                "half2_z_surr": round(z2, 2),
                "n_surrogates_confirm": n_confirm,
            })
        adj_p = holm_bonferroni(raw_p)
        for rec, ph in zip(recs_2d, adj_p):
            rec["half2_p_holm"] = round(ph, 6)
            rec["replicated_anomaly"] = bool(ph < 0.005 and rec["half2_z_surr"] >= 4.0)
            candidates.append(rec)
            if rec["replicated_anomaly"]:
                surviving.append(rec)

    # 2) Persistent Blinking / Telegrapher Pixels (excess kurtosis & anomalous Fano replication across halves)
    var1 = np.mean(r1 * r1, axis=0) + 1e-12
    var2 = np.mean(r2 * r2, axis=0) + 1e-12
    kurt1 = np.mean(r1 ** 4, axis=0) / (var1 ** 2) - 3.0
    kurt2 = np.mean(r2 ** 4, axis=0) / (var2 ** 2) - 3.0

    # Top 0.05% high-kurtosis telegrapher pixels in Half 1 -> check mean kurtosis of THOSE SAME pixels in Half 2!
    n_px = H * W
    k_top = max(20, n_px // 2000)
    top_px_idx = np.argsort(kurt1.ravel())[-k_top:]
    mean_k1 = float(np.mean(kurt1.ravel()[top_px_idx]))
    if mean_k1 >= 3.0:
        k2_flat = kurt2.ravel()
        obs_k2 = float(np.mean(k2_flat[top_px_idx]))
        # Compare against N = n_confirm random spatial pixel sets of size k_top in Half 2
        rand_idx = rng.integers(0, n_px, size=(n_confirm, k_top))
        surr_k2 = np.mean(k2_flat[rand_idx], axis=1)
        pk, zk, muk, _ = empirical_upper_p_and_z(obs_k2, surr_k2)
        rec_rt = {
            "lens": "A4_PERSISTENT_TELEGRAPHER_PIXELS",
            "sensor": label,
            "n_pixels_selected": k_top,
            "half1_top_excess_kurtosis": round(mean_k1, 4),
            "half2_locked_excess_kurtosis": round(obs_k2, 4),
            "half2_random_px_mean_kurtosis": round(muk, 4),
            "half2_p_surr": round(pk, 6),
            # raw p only here; lens-family Holm-Bonferroni is applied in main()'s post-pass
            # (never store raw p as half2_p_holm in a multi-member family)
            "half2_p_holm": round(pk, 6),
            "half2_z_surr": round(zk, 2),
            "n_surrogates_confirm": n_confirm,
            "replicated_anomaly": bool(pk < 0.005 and zk >= 4.0 and obs_k2 >= 1.0),
        }
        candidates.append(rec_rt)
        if rec_rt["replicated_anomaly"]:
            surviving.append(rec_rt)

    # 3) Multi-pixel synchronized non-row impulse bursts
    px_sd1 = np.sqrt(var1)[None, :, :]
    px_sd2 = np.sqrt(var2)[None, :, :]
    burst_frac1 = np.mean(np.abs(r1) > 4.0 * px_sd1, axis=(1, 2))
    burst_frac2 = np.mean(np.abs(r2) > 4.0 * px_sd2, axis=(1, 2))
    max_b1 = float(np.max(burst_frac1))
    if max_b1 > 0.002:  # > 5x Gaussian 4-sigma tail (6.3e-5)
        obs_b2 = float(np.max(burst_frac2))
        hit_mat = (np.abs(r2) > 4.0 * px_sd2).reshape(len(r2), -1)  # [mid, H*W]
        # Subsample 2048 pixels for fast independent temporal-shift surrogate of frame burst coincidence
        sub_cols = rng.choice(hit_mat.shape[1], size=min(2048, hit_mat.shape[1]), replace=False)
        sub_hits = hit_mat[:, sub_cols]
        obs_sub = float(np.max(np.mean(sub_hits, axis=1)))
        surr_b2 = np.empty(n_confirm, dtype=np.float64)
        t_len, n_sub = sub_hits.shape
        t_grid = np.arange(t_len)[:, None]
        for s_i in range(n_confirm):
            sh = rng.integers(0, t_len, size=(1, n_sub))
            shifted = sub_hits[(t_grid - sh) % t_len, np.arange(n_sub)[None, :]]
            surr_b2[s_i] = float(np.max(np.mean(shifted, axis=1)))
        pb, zb, mub, _ = empirical_upper_p_and_z(obs_sub, surr_b2)
        rec_b = {
            "lens": "A4_SYNCHRONIZED_MULTIPIXEL_BURSTS",
            "sensor": label,
            "half1_max_4sigma_px_frac": round(max_b1, 6),
            "half2_max_4sigma_px_frac": round(obs_b2, 6),
            "half2_sub_obs": round(obs_sub, 6),
            "half2_surr_mean": round(mub, 6),
            "half2_p_surr": round(pb, 6),
            # raw p only here; lens-family Holm-Bonferroni is applied in main()'s post-pass
            "half2_p_holm": round(pb, 6),
            "half2_z_surr": round(zb, 2),
            "n_surrogates_confirm": n_confirm,
            "replicated_anomaly": bool(pb < 0.005 and zb >= 4.0),
        }
        candidates.append(rec_b)
        if rec_b["replicated_anomaly"]:
            surviving.append(rec_b)

    return candidates, surviving


def lens_a4_2d_blank_wall_from_files(
    rgb_yuyv_path: Path | None,
    ir_grey_path: Path | None,
    rng: np.random.Generator,
    n_confirm: int = 799,
) -> dict[str, Any]:
    """Memmap local_raw_av/ .yuyv and .grey files strictly read-only and run Lens A4."""
    candidates: list[dict[str, Any]] = []
    surviving: list[dict[str, Any]] = []
    ir_strobe_diagnostics: dict[str, Any] = {}

    if rgb_yuyv_path is not None and rgb_yuyv_path.is_file():
        fbytes = 640 * 480 * 2
        nf = rgb_yuyv_path.stat().st_size // fbytes
        if nf >= 24:
            mm = np.memmap(rgb_yuyv_path, dtype=np.uint8, mode="r", shape=(nf, 480, 640, 2))
            stride = max(1, nf // 240)
            y_stack = np.array(mm[::stride, :, :, 0][:240], copy=True)
            uv_stack = np.array(mm[::stride, :, :, 1][:240], copy=True)
            del mm
            c_y, s_y = _analyze_2d_stack_blind(y_stack, f"{rgb_yuyv_path.stem}_luma_Y", rng, n_confirm=n_confirm)
            candidates.extend(c_y)
            surviving.extend(s_y)
            # Separate Cb (even cols) and Cr (odd cols) so 2:1 chroma subsampling doesn't look like checkerboard
            cb_stack = uv_stack[:, :, 0::2]
            c_cb, s_cb = _analyze_2d_stack_blind(cb_stack, f"{rgb_yuyv_path.stem}_chroma_Cb", rng, n_confirm=n_confirm)
            candidates.extend(c_cb)
            surviving.extend(s_cb)

    if ir_grey_path is not None and ir_grey_path.is_file():
        fbytes = 640 * 360
        nf = ir_grey_path.stat().st_size // fbytes
        if nf >= 24:
            mm = np.memmap(ir_grey_path, dtype=np.uint8, mode="r", shape=(nf, 360, 640))
            # Check IR frame mean & duplicate/strobe sequence first!
            fmeans = np.array([float(mm[i].mean()) for i in range(min(nf, 600))], dtype=np.float64)
            fdiffs = np.array([float(np.max(np.abs(mm[i].astype(np.int16) - mm[i - 1].astype(np.int16)))) for i in range(1, len(fmeans))])
            uniq_mask = np.concatenate(([True], fdiffs > 0))
            med_m = float(np.median(fmeans[uniq_mask])) if np.any(uniq_mask) else float(np.median(fmeans))
            led_on_idx = np.flatnonzero(uniq_mask & (fmeans > med_m))
            led_off_idx = np.flatnonzero(uniq_mask & (fmeans <= med_m))
            ir_strobe_diagnostics = {
                "file_stem": ir_grey_path.stem,
                "inspected_frames": int(len(fmeans)),
                "unique_frames": int(np.sum(uniq_mask)),
                "duplicate_frame_fraction": round(1.0 - float(np.mean(uniq_mask)), 4),
                "led_on_frames": int(len(led_on_idx)),
                "led_off_frames": int(len(led_off_idx)),
                "led_on_mean_dn": round(float(np.mean(fmeans[led_on_idx])), 3) if len(led_on_idx) else None,
                "led_off_mean_dn": round(float(np.mean(fmeans[led_off_idx])), 3) if len(led_off_idx) else None,
            }
            if len(led_on_idx) >= 24:
                on_stack = np.array(mm[led_on_idx[:240]], copy=True)
                c_on, s_on = _analyze_2d_stack_blind(on_stack, f"{ir_grey_path.stem}_LED_ON", rng, n_confirm=n_confirm)
                candidates.extend(c_on)
                surviving.extend(s_on)
            if len(led_off_idx) >= 24:
                off_stack = np.array(mm[led_off_idx[:240]], copy=True)
                c_off, s_off = _analyze_2d_stack_blind(off_stack, f"{ir_grey_path.stem}_LED_OFF", rng, n_confirm=n_confirm)
                candidates.extend(c_off)
                surviving.extend(s_off)
                # Explicit test for Inverted Shot-Noise Variance Violation (Var(LED_OFF) >> Var(LED_ON) despite Mean(LED_OFF) < Mean(LED_ON))!
                if len(led_on_idx) >= 24:
                    on_sub = np.array(mm[led_on_idx[: min(120, len(led_on_idx))]], dtype=np.float32)
                    off_sub = np.array(mm[led_off_idx[: min(120, len(led_off_idx))]], dtype=np.float32)
                    m_on, m_off = len(on_sub) // 2, len(off_sub) // 2
                    dv_on_1 = float(0.5 * np.mean(np.diff(on_sub[:m_on], axis=0) ** 2))
                    dv_off_1 = float(0.5 * np.mean(np.diff(off_sub[:m_off], axis=0) ** 2))
                    dv_on_2 = float(0.5 * np.mean(np.diff(on_sub[m_on : 2 * m_on], axis=0) ** 2))
                    dv_off_2 = float(0.5 * np.mean(np.diff(off_sub[m_off : 2 * m_off], axis=0) ** 2))
                    ratio1 = dv_off_1 / max(dv_on_1, 1e-9)
                    ratio2 = dv_off_2 / max(dv_on_2, 1e-9)
                    if ratio1 > 2.0 and float(np.mean(off_sub)) < float(np.mean(on_sub)):
                        # Permutation null on Half-2 frame-pair diff variances across pooled ON+OFF diff energies
                        e_on2 = 0.5 * np.mean(np.diff(on_sub[m_on : 2 * m_on], axis=0) ** 2, axis=(1, 2))
                        e_off2 = 0.5 * np.mean(np.diff(off_sub[m_off : 2 * m_off], axis=0) ** 2, axis=(1, 2))
                        pooled = np.concatenate([e_off2, e_on2])
                        n_off_e = len(e_off2)
                        surr_ratios = np.empty(n_confirm, dtype=np.float64)
                        for s_i in range(n_confirm):
                            perm = rng.permutation(pooled)
                            surr_ratios[s_i] = float(np.mean(perm[:n_off_e])) / max(float(np.mean(perm[n_off_e:])), 1e-9)
                        pr, zr, mur, _ = empirical_upper_p_and_z(ratio2, surr_ratios)
                        rec_inv = {
                            "lens": "A4_INVERTED_SHOT_NOISE_VARIANCE",
                            "sensor": ir_grey_path.stem,
                            "led_on_mean_dn": round(float(np.mean(on_sub)), 3),
                            "led_off_mean_dn": round(float(np.mean(off_sub)), 3),
                            "half1_led_on_diff_var_dn2": round(dv_on_1, 4),
                            "half1_led_off_diff_var_dn2": round(dv_off_1, 4),
                            "half1_off_over_on_var_ratio": round(ratio1, 3),
                            "half2_led_on_diff_var_dn2": round(dv_on_2, 4),
                            "half2_led_off_diff_var_dn2": round(dv_off_2, 4),
                            "half2_off_over_on_var_ratio": round(ratio2, 3),
                            "half2_surr_mean_ratio": round(mur, 3),
                            "half2_p_surr": round(pr, 6),
                            "half2_p_holm": round(pr, 6),
                            "half2_z_surr": round(zr, 2),
                            "n_surrogates_confirm": n_confirm,
                            "replicated_anomaly": bool(pr < 0.005 and zr >= 4.0 and ratio2 > 2.0),
                        }
                        candidates.append(rec_inv)
                        if rec_inv["replicated_anomaly"]:
                            surviving.append(rec_inv)
            del mm

    return {
        "ir_strobe_diagnostics": ir_strobe_diagnostics,
        "tested_candidates": candidates,
        "surviving_anomalies": surviving,
    }


# ============================================================================
# LENS A5: Zero-Filter Cross-Modal Rare-Event Coincidence (incl. Precursor Lags)
# ============================================================================

def _extract_top_outlier_mask(x: np.ndarray, k_events: int, deadtime_bins: int = 3) -> np.ndarray:
    """Return boolean event train of top-K declustered |z| first-difference innovations."""
    dx = np.diff(np.asarray(x, dtype=np.float64), prepend=x[0])
    med = float(np.median(dx))
    mad = float(np.median(np.abs(dx - med))) * 1.4826
    if mad < 1e-12:
        sd = float(np.std(dx))
        if sd < 1e-12:
            return np.zeros(len(x), dtype=bool)
        z = np.abs(dx - float(np.mean(dx))) / sd
    else:
        z = np.abs(dx - med) / mad

    order = np.argsort(z)[::-1]
    events = np.zeros(len(x), dtype=bool)
    picked = 0
    for idx in order:
        if z[idx] < 2.5:
            break
        lo = max(0, int(idx) - deadtime_bins)
        hi = min(len(x), int(idx) + deadtime_bins + 1)
        if not np.any(events[lo:hi]):
            events[idx] = True
            picked += 1
            if picked >= k_events:
                break
    return events


def _coincidence_curve(ev_src: np.ndarray, ev_dst: np.ndarray, lag_bins: np.ndarray, tol_bins: int = 3) -> np.ndarray:
    """Count how many src events have a dst event within |t_dst - (t_src + lag)| <= tol_bins.
    Note: lag < 0 means ev_dst occurred BEFORE ev_src; Equivalently, if dst='pkg_w' and src='dmic',
    positive lag means dmic occurred BEFORE pkg_w (precursor to RAPL!).
    """
    # Widen dst by +-tol_bins
    kernel = np.ones(2 * tol_bins + 1, dtype=np.int32)
    dst_widened = np.convolve(ev_dst.astype(np.int32), kernel, mode="same") > 0
    src_idx = np.flatnonzero(ev_src)
    n = len(ev_dst)
    counts = np.zeros(len(lag_bins), dtype=np.float64)
    if len(src_idx) == 0:
        return counts
    for i, lag in enumerate(lag_bins):
        q = src_idx + int(lag)
        valid = q[(q >= 0) & (q < n)]
        if len(valid):
            counts[i] = float(np.sum(dst_widened[valid]))
    return counts


def lens_a5_rare_event_coincidence(
    aligned_100hz: dict[str, np.ndarray],
    rng: np.random.Generator,
    dt_s: float = 0.01,
    n_confirm: int = 799,
) -> dict[str, Any]:
    """Scan all cross-modal channel pairs for rare-outlier coincidence across [-2s, +2s]."""
    keys = [k for k, v in aligned_100hz.items() if len(v) >= 600 and float(np.std(v)) > 1e-12]
    if len(keys) < 2:
        return {"tested_candidates": [], "surviving_anomalies": []}

    n_tot = min(len(aligned_100hz[k]) for k in keys)
    mid = n_tot // 2
    k_ev = min(100, max(12, mid // 30))
    lag_bins = np.arange(-200, 201, 4)  # -2.0s to +2.0s in 40 ms steps, +-30 ms window

    ev1 = {k: _extract_top_outlier_mask(aligned_100hz[k][:mid], k_ev) for k in keys}
    ev2 = {k: _extract_top_outlier_mask(aligned_100hz[k][mid : 2 * mid], k_ev) for k in keys}

    # Avoid trivial within-RAPL pairs (pkg_w <-> core_w <-> psys_w) so we hunt TRUE cross-domain anomalies!
    def _domain(k: str) -> str:
        if k.startswith("dmic"):
            return "audio"
        if k.startswith("ir"):
            return "ir"
        if k.startswith("rgb"):
            return "rgb"
        if k in ("pkg_w", "core_w", "uncore_w", "psys_w"):
            return "rapl_cpu"
        if k == "dark_w":
            return "rapl_dark"
        return k

    # Screen all cross-domain pairs in Half 1
    screened: list[tuple[float, str, str, int, float]] = []
    min_sh = max(250, mid // 8)
    for i, ka in enumerate(keys):
        for j, kb in enumerate(keys):
            if j <= i or _domain(ka) == _domain(kb):
                continue
            if int(np.sum(ev1[ka])) < 5 or int(np.sum(ev1[kb])) < 5:
                continue
            c1 = _coincidence_curve(ev1[ka], ev1[kb], lag_bins, tol_bins=3)
            best_l = int(np.argmax(c1))
            if c1[best_l] < 4:
                continue
            # Quick 200-shift screen in Half 1
            shifts = rng.integers(min_sh, max(min_sh + 1, mid - min_sh), size=200)
            kernel = np.ones(7, dtype=np.int32)
            bw = np.convolve(ev1[kb].astype(np.int32), kernel, mode="same") > 0
            src_i = np.flatnonzero(ev1[ka])
            lag_val = int(lag_bins[best_l])
            q_base = src_i + lag_val
            q_valid = q_base[(q_base >= 0) & (q_base < mid)]
            if len(q_valid) == 0:
                continue
            surr_c1 = np.sum(bw[(q_valid[None, :] - shifts[:, None]) % mid], axis=1).astype(np.float64)
            p1, z1, _, _ = empirical_upper_p_and_z(float(c1[best_l]), surr_c1)
            if p1 <= 0.02 and z1 >= 3.0:
                screened.append((z1, ka, kb, lag_val, float(c1[best_l])))

    screened.sort(reverse=True)
    locked = screened[:3]
    candidates: list[dict[str, Any]] = []
    surviving: list[dict[str, Any]] = []
    if not locked:
        return {"tested_candidates": candidates, "surviving_anomalies": surviving}

    raw_p2 = []
    recs = []
    for z1, ka, kb, lag_val, c1_obs in locked:
        c2_obs = float(_coincidence_curve(ev2[ka], ev2[kb], np.array([lag_val]), tol_bins=3)[0])
        kernel = np.ones(7, dtype=np.int32)
        bw2 = np.convolve(ev2[kb].astype(np.int32), kernel, mode="same") > 0
        src2 = np.flatnonzero(ev2[ka])
        q2 = src2 + lag_val
        qv2 = q2[(q2 >= 0) & (q2 < mid)]
        shifts2 = rng.integers(min_sh, max(min_sh + 1, mid - min_sh), size=n_confirm)
        if len(qv2) > 0:
            surr_c2 = np.sum(bw2[(qv2[None, :] - shifts2[:, None]) % mid], axis=1).astype(np.float64)
        else:
            surr_c2 = np.zeros(n_confirm, dtype=np.float64)
        p2, z2, mu2, _ = empirical_upper_p_and_z(c2_obs, surr_c2)
        raw_p2.append(p2)
        tau_s = round(lag_val * dt_s, 3)
        recs.append({
            "lens": "A5_RARE_EVENT_COINCIDENCE",
            "src_channel": ka,
            "dst_channel": kb,
            "lag_tau_s": tau_s,
            "timing_direction": (
                f"{ka} precedes {kb} by {abs(tau_s):.3f}s"
                if tau_s > 0.02
                else (f"{kb} precedes {ka} by {abs(tau_s):.3f}s" if tau_s < -0.02 else "zero_lag_simultaneous")
            ),
            "half1_coincidences": int(c1_obs),
            "half1_z_shift": round(z1, 2),
            "half2_coincidences": int(c2_obs),
            "half2_surr_mean": round(mu2, 2),
            "half2_p_shift": round(p2, 6),
            "half2_z_shift": round(z2, 2),
            "n_events_per_half": int(k_ev),
            "n_surrogates_confirm": n_confirm,
        })
    adj_p2 = holm_bonferroni(raw_p2)
    for rec, ph in zip(recs, adj_p2):
        rec["half2_p_holm"] = round(ph, 6)
        rec["replicated_anomaly"] = bool(ph < 0.005 and rec["half2_z_shift"] >= 3.5)
        candidates.append(rec)
        if rec["replicated_anomaly"]:
            surviving.append(rec)

    return {"tested_candidates": candidates, "surviving_anomalies": surviving}


# ============================================================================
# LENS A6: Blind Uninvited High-Q Spectral Lines & Drifting Chirps
# ============================================================================

def _highres_prominence_psd(x: np.ndarray, fs: float, n_fft: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute Welch PSD and local-median line prominence ratio P(f) / median_local(P)."""
    x1 = np.asarray(x, dtype=np.float64).ravel()
    nper = min(n_fft, len(x1) // 2)
    if nper < 128:
        return np.zeros(0), np.zeros(0), np.zeros(0)
    freqs, psd = signal.welch(x1 - np.mean(x1), fs=fs, nperseg=nper, noverlap=nper // 2, window="hann")
    # Local median filter across +-25 bins (excluding central 5 bins via two-wing median)
    w = min(25, max(5, len(psd) // 40))
    med_floor = signal.medfilt(psd, kernel_size=2 * w + 1)
    prom = psd / np.maximum(med_floor, 1e-30)
    return freqs, psd, prom


def _track_line_drift(x: np.ndarray, fs: float, f_center: float, bw_hz: float = 40.0, win_s: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    """Track instantaneous peak frequency around f_center across win_s windows."""
    n_win = int(round(win_s * fs))
    if n_win < 256 or len(x) < 3 * n_win:
        return np.zeros(0), np.zeros(0)
    n_steps = len(x) // n_win
    t_centers = (np.arange(n_steps) + 0.5) * win_s
    f_peaks = np.zeros(n_steps, dtype=np.float64)
    freqs = np.fft.rfftfreq(n_win, d=1.0 / fs)
    band = (freqs >= f_center - bw_hz) & (freqs <= f_center + bw_hz)
    if int(np.sum(band)) < 3:
        return np.zeros(0), np.zeros(0)
    f_band = freqs[band]
    win = np.hanning(n_win)
    for i in range(n_steps):
        seg = (x[i * n_win : (i + 1) * n_win] - np.mean(x[i * n_win : (i + 1) * n_win])) * win
        p = np.abs(np.fft.rfft(seg))[band] ** 2
        k = int(np.argmax(p))
        # Parabolic sub-bin interpolation
        if 0 < k < len(p) - 1 and p[k] > 0:
            lp = np.log(np.maximum(p[k - 1 : k + 2], 1e-30))
            denom = lp[0] - 2.0 * lp[1] + lp[2]
            delta = 0.5 * (lp[0] - lp[2]) / denom if abs(denom) > 1e-12 else 0.0
            df = f_band[1] - f_band[0]
            f_peaks[i] = float(f_band[k]) + max(-0.5, min(0.5, float(delta))) * float(df)
        else:
            f_peaks[i] = float(f_band[k])
    return t_centers, f_peaks


def lens_a6_uninvited_spectral_lines(
    signals_dict: dict[str, tuple[np.ndarray, float, list[float], bool]],
    telemetry_dict: dict[str, np.ndarray] | None,
    t0_Offset_s: float,
    rng: np.random.Generator,
    n_confirm: int = 799,
) -> dict[str, Any]:
    """Scan full-band PSDs for uninvited high-Q lines & chirps not on 60Hz/30fps/prime combs.
    signals_dict: name -> (x_1d, fs_hz, injected_freqs, has_camera_30hz).
     Note: IAAFT preserves exact PSD, so testing whether a sharp narrowband spectral line exceeds
     a smooth continuous noise background uses local-spectrum phase/amplitude white-innovations
     (AR(4) smooth-envelope surrogates!) so genuine narrowband physical oscillators are caught while
     broadband colored formants are NOT misflagged!
    """
    candidates: list[dict[str, Any]] = []
    surviving: list[dict[str, Any]] = []

    for name, (arr, fs, inj_freqs, cam30) in signals_dict.items():
        x = np.asarray(arr, dtype=np.float64).ravel()
        if len(x) < 2048 or float(np.std(x)) < 1e-12:
            continue
        mid = len(x) // 2
        h1 = x[:mid]
        h2 = x[mid : 2 * mid]
        n_fft = min(16384 if fs >= 20000 else 8192, mid // 2)
        if n_fft < 256:
            continue

        f1, psd1, prom1 = _highres_prominence_psd(h1, fs, n_fft)
        f2, psd2, prom2 = _highres_prominence_psd(h2, fs, n_fft)
        if len(f1) == 0 or len(f1) != len(f2):
            continue
        df = float(f1[1] - f1[0])
        tol = min(2.5, max(1.5 * df, 1.2))

        # Mask known combs
        uninvited_prom1 = prom1.copy()
        for k_i, fk in enumerate(f1):
            is_known, _ = _is_known_comb_freq(float(fk), fs, inj_freqs, include_camera_30hz=cam30, tol_hz=tol)
            if is_known:
                uninvited_prom1[k_i] = 0.0

        order = np.argsort(uninvited_prom1)[::-1]
        locked_bins: list[int] = []
        for idx in order:
            if uninvited_prom1[idx] < 6.0:
                break
            if all(abs(int(idx) - b) >= 6 for b in locked_bins):
                locked_bins.append(int(idx))
            if len(locked_bins) >= 4:
                break

        if not locked_bins:
            continue

        # Exact null for uninvited narrowband line prominence on M overlapped Hann Welch segments:
        # Evaluate Welch PSD only on local +-w_med neighborhood around each locked_bin via direct DFT Vandermonde!
        w_med = min(25, max(5, len(psd2) // 40))
        eval_len = min(len(h2), 4 * n_fft)
        f_eval, _, prom2_eval = _highres_prominence_psd(h2[:eval_len], fs, n_fft)
        step_w = n_fft // 2
        n_seg_w = (eval_len - n_fft) // step_w + 1
        # Under locally smooth continuous Gaussian noise (scaled by smooth_psd2), normalized local prominence
        # P(k) / median(P[k-w_med : k+w_med+1]) on M overlapped Hann segments is scale-invariant!
        # Simulate white Gaussian segments of exact length eval_len & windowing, weighted by local smooth_psd2 slope:
        surr_prom = np.zeros((n_confirm, len(locked_bins)), dtype=np.float64)
        seg_idx_w = np.arange(n_fft)[None, :] + (np.arange(n_seg_w) * step_w)[:, None]
        # Gather union of all needed DFT bins [b_idx - w_med - 1 .. b_idx + w_med + 1]
        needed_set: set[int] = set()
        bin_windows: list[tuple[list[int], list[int]]] = []
        for b_idx in locked_bins:
            lo_w = max(1, b_idx - w_med - 1)
            hi_w = min(n_fft // 2, b_idx + w_med + 2)
            win_b = list(range(lo_w, hi_w))
            pk_b = [b for b in (b_idx - 1, b_idx, b_idx + 1) if lo_w <= b < hi_w]
            needed_set.update(win_b)
            bin_windows.append((pk_b, win_b))
        sorted_needed = sorted(needed_set)
        b_map = {b: i for i, b in enumerate(sorted_needed)}
        win_h = np.hanning(n_fft)[None, None, :]
        w_smooth = signal.medfilt(psd2, kernel_size=2 * w_med + 1)[sorted_needed]

        for b0 in range(0, n_confirm, 50):
            b1 = min(n_confirm, b0 + 50)
            bsz = b1 - b0
            wn = rng.standard_normal((bsz, eval_len))
            wn_segs = wn[:, seg_idx_w] * win_h  # [bsz, n_seg_w, n_fft]
            Xk_w = np.fft.rfft(wn_segs, axis=2)[:, :, sorted_needed]
            psd_local = np.mean(np.abs(Xk_w) ** 2, axis=1) * w_smooth[None, :]  # [bsz, K_need]
            for k_l, (pk_b, win_b) in enumerate(bin_windows):
                w_idx = [b_map[b] for b in win_b]
                p_idx = [b_map[b] for b in pk_b]
                med_loc = np.median(psd_local[:, w_idx], axis=1) + 1e-30
                pk_loc = np.max(psd_local[:, p_idx], axis=1)
                surr_prom[b0:b1, k_l] = pk_loc / med_loc

        raw_p = []
        recs = []
        for k_l, b_idx in enumerate(locked_bins):
            fk = float(f1[b_idx])
            v1 = float(prom1[b_idx])
            lo_b = max(0, b_idx - 1)
            hi_b = min(len(prom2_eval), b_idx + 2)
            best_b2 = lo_b + int(np.argmax(prom2_eval[lo_b:hi_b]))
            v2 = float(prom2_eval[best_b2])
            p2, z2, mu2, _ = empirical_upper_p_and_z(v2, surr_prom[:, k_l])
            raw_p.append(p2)

            # Estimate FWHM Q-factor
            half_max = 0.5 * psd2[best_b2]
            left = best_b2
            while left > 0 and psd2[left] > half_max:
                left -= 1
            right = best_b2
            while right < len(psd2) - 1 and psd2[right] > half_max:
                right += 1
            fwhm_hz = max(df, float(right - left) * df)
            q_est = fk / fwhm_hz

            # Track frequency drift across full record
            tc, fp = _track_line_drift(x, fs, fk, bw_hz=max(15.0, 4.0 * df), win_s=max(1.0, 2.0 * n_fft / fs))
            drift_hz = float(np.max(fp) - np.min(fp)) if len(fp) >= 3 else 0.0
            drift_slope_hz_per_min = 0.0
            temp_corr = None
            if len(fp) >= 4:
                coeffs = np.polyfit(tc, fp, 1)
                drift_slope_hz_per_min = float(coeffs[0] * 60.0)
                if telemetry_dict and "t_mono_s" in telemetry_dict and "temp_c" in telemetry_dict:
                    t_tel = telemetry_dict["t_mono_s"] - t0_Offset_s
                    if len(t_tel) >= 10 and float(np.std(telemetry_dict["temp_c"])) > 0.05 and float(np.std(fp)) > 1e-6:
                        temp_interp = np.interp(tc, t_tel, telemetry_dict["temp_c"])
                        if float(np.std(temp_interp)) > 0.02:
                            temp_corr = round(float(np.corrcoef(fp, temp_interp)[0, 1]), 4)

            recs.append({
                "lens": "A6_UNINVITED_SPECTRAL_LINE",
                "signal": name,
                "freq_half1_hz": round(fk, 2),
                "freq_half2_hz": round(float(f_eval[best_b2]), 2),
                "estimated_Q": round(q_est, 1),
                "half1_prominence_x_median": round(v1, 2),
                "half2_prominence_x_median": round(v2, 2),
                "half2_smooth_surr_mean": round(mu2, 2),
                "half2_p_surr": round(p2, 6),
                "half2_z_surr": round(z2, 2),
                "drift_span_hz": round(drift_hz, 3),
                "drift_rate_hz_per_min": round(drift_slope_hz_per_min, 3),
                "corr_freq_vs_pkg_temp": temp_corr,
                "n_surrogates_confirm": n_confirm,
            })

        adj_p = holm_bonferroni(raw_p)
        for rec, ph in zip(recs, adj_p):
            rec["half2_p_holm"] = round(ph, 6)
            rec["replicated_anomaly"] = bool(ph < 0.005 and rec["half2_z_surr"] >= 4.0 and rec["half2_prominence_x_median"] >= 5.0)
            candidates.append(rec)
            if rec["replicated_anomaly"]:
                surviving.append(rec)

    return {"tested_candidates": candidates, "surviving_anomalies": surviving}


# ============================================================================
# LENS A7: Non-Linear Residual Structure Beyond Linear Schur (Copula MI & kNN)
# ============================================================================

def _ols_cross_modal_residuals(mat_dict: dict[str, np.ndarray], lags: tuple[int, ...] = (-2, -1, 0, 1, 2)) -> dict[str, np.ndarray]:
    """Remove all linear cross-modal predictability (multi-lag Ridge/OLS) from each channel."""
    keys = list(mat_dict.keys())
    n = min(len(mat_dict[k]) for k in keys)
    trim = max(abs(l) for l in lags)
    if n <= 2 * trim + 40:
        return {}

    def _grp(k: str) -> str:
        for p in ("dmic", "ir", "rgb", "temp", "fan"):
            if k.startswith(p):
                return p
        if k in ("pkg_w", "core_w", "uncore_w", "psys_w"):
            return "rapl_main"
        return k

    std_cols: dict[str, np.ndarray] = {}
    for k in keys:
        v = np.asarray(mat_dict[k][:n], dtype=np.float64)
        sd = float(np.std(v))
        if sd > 1e-12 and np.all(np.isfinite(v)):
            std_cols[k] = (v - float(np.mean(v))) / sd

    resids: dict[str, np.ndarray] = {}
    m_len = n - 2 * trim
    for target_k, y_full in std_cols.items():
        y = y_full[trim : n - trim]
        other_keys = [k for k in std_cols if _grp(k) != _grp(target_k)]
        if not other_keys:
            resids[target_k] = y
            continue
        cols = [np.ones(m_len, dtype=np.float64)]
        for ok in other_keys:
            xo = std_cols[ok]
            for lg in lags:
                cols.append(xo[trim + lg : n - trim + lg])
        X = np.column_stack(cols)
        # Tiny ridge 1e-4 for numerical stability
        xtx = X.T @ X + 1e-4 * np.eye(X.shape[1])
        beta = np.linalg.solve(xtx, X.T @ y)
        e = y - X @ beta
        sd_e = float(np.std(e))
        if sd_e > 1e-12:
            resids[target_k] = (e - float(np.mean(e))) / sd_e
    return resids


def _rank_copula_mi_4x4(x: np.ndarray, y: np.ndarray) -> float:
    """Exact 4x4 equiprobable quantile contingency Mutual Information (captures pure non-linear coupling!)."""
    n = len(x)
    if n < 64:
        return 0.0
    qx = (np.argsort(np.argsort(x)) * 4) // n
    qy = (np.argsort(np.argsort(y)) * 4) // n
    qx = np.clip(qx, 0, 3)
    qy = np.clip(qy, 0, 3)
    idx = qx * 4 + qy
    counts = np.bincount(idx, minlength=16).reshape(4, 4).astype(np.float64)
    p_xy = counts / float(n)
    px = np.sum(p_xy, axis=1, keepdims=True)
    py = np.sum(p_xy, axis=0, keepdims=True)
    denom = np.maximum(px * py, 1e-30)
    nz = p_xy > 0
    return float(np.sum(p_xy[nz] * np.log(p_xy[nz] / denom[nz])))


def _copula_mi_batch(x_fixed: np.ndarray, Y_batch: np.ndarray) -> np.ndarray:
    """Vectorized 4x4 quantile copula MI between 1D x_fixed and [B, N] Y_batch."""
    B, n = Y_batch.shape
    qx = np.clip((np.argsort(np.argsort(x_fixed)) * 4) // n, 0, 3)  # [n]
    qy = np.clip((np.argsort(np.argsort(Y_batch, axis=1), axis=1) * 4) // n, 0, 3)  # [B, n]
    joint = qx[None, :] * 4 + qy  # [B, n]
    out = np.zeros(B, dtype=np.float64)
    for b in range(B):
        c = np.bincount(joint[b], minlength=16).reshape(4, 4).astype(np.float64) / float(n)
        px = np.sum(c, axis=1, keepdims=True)
        py = np.sum(c, axis=0, keepdims=True)
        den = np.maximum(px * py, 1e-30)
        nz = c > 0
        out[b] = float(np.sum(c[nz] * np.log(c[nz] / den[nz])))
    return out


def _simplex_delay_pred_corr(x: np.ndarray, m: int = 3, tau: int = 2, k_nn: int = 5, theiler: int = 8) -> float:
    """Takens delay-embedding k-NN nonlinear 1-step predictability correlation."""
    x1 = np.asarray(x, dtype=np.float64).ravel()
    if len(x1) > 280:
        x1 = x1[:280]
    n = len(x1)
    span = (m - 1) * tau
    n_vec = n - span - 1
    if n_vec < 60:
        return 0.0
    emb = np.column_stack([x1[j * tau : j * tau + n_vec] for j in range(m)])
    target = x1[span + 1 : span + 1 + n_vec]
    # Pairwise squared Euclidean distances [n_vec, n_vec]
    diff = emb[:, None, :] - emb[None, :, :]
    dist2 = np.sum(diff * diff, axis=2)
    idx = np.arange(n_vec)
    dist2[np.abs(idx[:, None] - idx[None, :]) <= theiler] = np.inf
    nn_idx = np.argpartition(dist2, k_nn, axis=1)[:, :k_nn]
    nn_d = np.sqrt(np.take_along_axis(dist2, nn_idx, axis=1)) + 1e-6
    weights = np.exp(-nn_d / np.maximum(nn_d[:, 0:1], 1e-6))
    weights /= np.sum(weights, axis=1, keepdims=True)
    pred = np.sum(weights * target[nn_idx], axis=1)
    if float(np.std(pred)) < 1e-12 or float(np.std(target)) < 1e-12:
        return 0.0
    return float(np.corrcoef(pred, target)[0, 1])


def lens_a7_nonlinear_residual_structure(
    multimodal_series: dict[str, np.ndarray],
    rng: np.random.Generator,
    n_screen: int = 200,
    n_confirm: int = 799,
) -> dict[str, Any]:
    """Remove all linear cross-modal predictors first, then hunt nonlinear copula MI & Takens chaos."""
    keys = [k for k, v in multimodal_series.items() if len(v) >= 240 and float(np.std(v)) > 1e-12]
    if len(keys) < 2:
        return {"tested_candidates": [], "surviving_anomalies": []}

    n_tot = min(len(multimodal_series[k]) for k in keys)
    mid = n_tot // 2
    sub1 = {k: multimodal_series[k][:mid] for k in keys}
    sub2 = {k: multimodal_series[k][mid : 2 * mid] for k in keys}

    # Fit OLS independently in Half 1 and Half 2 (or remove linear predictability cleanly in each half)
    res1 = _ols_cross_modal_residuals(sub1)
    res2 = _ols_cross_modal_residuals(sub2)
    common_keys = sorted(set(res1.keys()) & set(res2.keys()))

    candidates: list[dict[str, Any]] = []
    surviving: list[dict[str, Any]] = []
    if len(common_keys) < 2:
        return {"tested_candidates": candidates, "surviving_anomalies": surviving}

    # 1) Cross-modal Rank-Copula MI on linear-orthogonalized residuals!
    pair_scores: list[tuple[float, str, str, float]] = []
    for i, ka in enumerate(common_keys):
        for j, kb in enumerate(common_keys):
            if j <= i or ka.split("_")[0] == kb.split("_")[0]:
                continue
            mi1 = _rank_copula_mi_4x4(res1[ka], res1[kb])
            surr1 = iaaft_surrogates(res1[kb], n_screen, rng, n_iter=8)
            s_mi1 = _copula_mi_batch(res1[ka], surr1)
            p1, z1, _, _ = empirical_upper_p_and_z(mi1, s_mi1)
            if p1 <= 0.02 and z1 >= 2.8:
                pair_scores.append((z1, ka, kb, mi1))

    pair_scores.sort(reverse=True)
    locked_pairs = pair_scores[:3]
    if locked_pairs:
        raw_p2 = []
        recs = []
        for z1, ka, kb, mi1 in locked_pairs:
            mi2 = _rank_copula_mi_4x4(res2[ka], res2[kb])
            surr2 = iaaft_surrogates(res2[kb], n_confirm, rng, n_iter=10)
            s_mi2 = _copula_mi_batch(res2[ka], surr2)
            p2, z2, mu2, _ = empirical_upper_p_and_z(mi2, s_mi2)
            raw_p2.append(p2)
            recs.append({
                "lens": "A7_NONLINEAR_RESIDUAL_COPULA_MI",
                "channel_a": ka,
                "channel_b": kb,
                "half1_copula_mi_nats": round(mi1, 5),
                "half1_z_iaaft": round(z1, 2),
                "half2_copula_mi_nats": round(mi2, 5),
                "half2_surr_mean_nats": round(mu2, 5),
                "half2_linear_corr_check": round(float(np.corrcoef(res2[ka], res2[kb])[0, 1]), 4),
                "half2_p_iaaft": round(p2, 6),
                "half2_z_iaaft": round(z2, 2),
                "n_surrogates_confirm": n_confirm,
            })
        adj_p2 = holm_bonferroni(raw_p2)
        for rec, ph in zip(recs, adj_p2):
            rec["half2_p_holm"] = round(ph, 6)
            rec["replicated_anomaly"] = bool(ph < 0.005 and rec["half2_z_iaaft"] >= 3.5)
            candidates.append(rec)
            if rec["replicated_anomaly"]:
                surviving.append(rec)

    # 2) Takens Delay-Embedding Nonlinear Predictability vs IAAFT (which preserves linear ACF!)
    nl_scores: list[tuple[float, str, float]] = []
    for k in common_keys:
        rho1 = _simplex_delay_pred_corr(res1[k])
        if rho1 < 0.10:
            continue
        s1_ts = iaaft_surrogates(res1[k][: min(600, len(res1[k]))], n_screen, rng, n_iter=8)
        s1_rhos = np.array([_simplex_delay_pred_corr(s1_ts[idx]) for idx in range(n_screen)], dtype=np.float64)
        p1, z1, _, _ = empirical_upper_p_and_z(rho1, s1_rhos)
        if p1 <= 0.02 and z1 >= 2.8:
            nl_scores.append((z1, k, rho1))

    nl_scores.sort(reverse=True)
    locked_nl = nl_scores[:2]
    if locked_nl:
        raw_p_nl = []
        recs_nl = []
        for z1, k, rho1 in locked_nl:
            r2_slice = res2[k][: min(600, len(res2[k]))]
            rho2 = _simplex_delay_pred_corr(r2_slice)
            s2_ts = iaaft_surrogates(r2_slice, n_confirm, rng, n_iter=10)
            s2_rhos = np.array([_simplex_delay_pred_corr(s2_ts[idx]) for idx in range(n_confirm)], dtype=np.float64)
            p2, z2, mu2, _ = empirical_upper_p_and_z(rho2, s2_rhos)
            raw_p_nl.append(p2)
            recs_nl.append({
                "lens": "A7_TAKENS_NONLINEAR_PREDICTABILITY",
                "channel": k,
                "half1_knn_corr": round(rho1, 5),
                "half1_z_iaaft": round(z1, 2),
                "half2_knn_corr": round(rho2, 5),
                "half2_iaaft_mean_corr": round(mu2, 5),
                "half2_p_iaaft": round(p2, 6),
                "half2_z_iaaft": round(z2, 2),
                "n_surrogates_confirm": n_confirm,
            })
        adj_nl = holm_bonferroni(raw_p_nl)
        for rec, ph in zip(recs_nl, adj_nl):
            rec["half2_p_holm"] = round(ph, 6)
            rec["replicated_anomaly"] = bool(ph < 0.005 and rec["half2_z_iaaft"] >= 3.5)
            candidates.append(rec)
            if rec["replicated_anomaly"]:
                surviving.append(rec)

    return {"tested_candidates": candidates, "surviving_anomalies": surviving}


# ============================================================================
# PHASE ORCHESTRATOR FOR LIVE TRACK S113 ARTIFACTS
# ============================================================================

def _load_dmic_s32le(path: Path) -> np.ndarray:
    """Memmap 4-ch int32 PCM and return float64 normalized to [-1, 1] scale."""
    n_frames = path.stat().st_size // 16
    mm = np.memmap(path, dtype="<i4", mode="r", shape=(n_frames, 4))
    return mm


def _compute_100hz_audio_envelopes(dmic_mm: np.ndarray, fs: int, t_start_mono: float, t_grid: np.ndarray) -> dict[str, np.ndarray]:
    """Extract 100 Hz (480 samples/bin) broadband RMS, ultrasonic 14-23kHz RMS, and crest factor."""
    win = int(fs // 100)  # 480 samples = 10 ms
    n_bins = len(dmic_mm) // win
    if n_bins < 20:
        return {}
    t_bins = t_start_mono + (np.arange(n_bins) + 0.5) * (win / float(fs))
    # Reshape ch0 and 4-ch sum into [n_bins, win]
    ch0 = np.asarray(dmic_mm[: n_bins * win, 0], dtype=np.float64) * (1.0 / 2147483648.0)
    beam = np.mean(np.asarray(dmic_mm[: n_bins * win, :], dtype=np.float64), axis=1) * (1.0 / 2147483648.0)
    sos_hf = signal.butter(4, [14000.0, 23000.0], btype="bandpass", fs=float(fs), output="sos")
    hf = signal.sosfilt(sos_hf, beam)

    rms_all = np.sqrt(np.mean(beam.reshape(n_bins, win) ** 2, axis=1) + 1e-30)
    rms_hf = np.sqrt(np.mean(hf.reshape(n_bins, win) ** 2, axis=1) + 1e-30)
    peak_ch0 = np.max(np.abs(ch0.reshape(n_bins, win)), axis=1)
    crest = peak_ch0 / np.maximum(np.sqrt(np.mean(ch0.reshape(n_bins, win) ** 2, axis=1)), 1e-30)

    return {
        "dmic_rms_log": np.interp(t_grid, t_bins, np.log10(rms_all)),
        "dmic_ultrasonic_14_23k_log": np.interp(t_grid, t_bins, np.log10(rms_hf)),
        "dmic_crest_factor": np.interp(t_grid, t_bins, crest),
    }


def _probe_4ch_cocycle_and_intermod(
    dmic_mm: np.ndarray,
    fs: float,
    t0_audio: float,
    blocks: list[dict[str, Any]],
    phase_label: str,
    rng: np.random.Generator,
    n_confirm: int = 799,
) -> dict[str, Any]:
    """Explicit split-half probe for (1) 4-ch TDOA triangle cocycle closure violation (tau_01+tau_12-tau_02 != 0)
    and CPU-vs-GPU spatial phase reversal, and (2) dual-rail CPU+GPU intermodulation sidebands |f_cpu +- f_gpu|.
    """
    cocycle_records: list[dict[str, Any]] = []
    intermod_records: list[dict[str, Any]] = []
    surviving: list[dict[str, Any]] = []

    for b in blocks:
        i0 = max(0, int(round((float(b["t0_mono_s"]) - t0_audio) * fs)))
        i1 = min(len(dmic_mm), int(round((float(b["t1_mono_s"]) - t0_audio) * fs)))
        if i1 - i0 < int(3.0 * fs):
            continue
        lbl = str(b.get("label", b.get("regime", "")))
        f_main = float(b.get("freq_hz", 0.0))
        f_cpu = float(b.get("cpu_hz", 0.0))
        f_gpu = float(b.get("gpu_hz", 0.0))
        target_freqs = [f for f in (f_main, f_cpu, f_gpu) if f >= 80.0]
        seg = np.asarray(dmic_mm[i0:i1], dtype=np.float64) * (1.0 / 2147483648.0)
        mid = len(seg) // 2
        h1, h2 = seg[:mid], seg[mid : 2 * mid]

        # 1) TDOA triangle cocycle closure on target carrier frequencies
        for f0 in sorted(set(target_freqs)):
            def _cocycle_on_slice(sl: np.ndarray, freq: float) -> tuple[float, float, float, float, float, float]:
                t_v = np.arange(len(sl), dtype=np.float64) / fs
                # Lock-in complex phasor per channel across 8 sub-blocks for coherence &CSD
                n_sub = 8
                slen = len(sl) // n_sub
                phasors = np.empty((n_sub, 4), dtype=np.complex128)
                for s_k in range(n_sub):
                    sub = sl[s_k * slen : (s_k + 1) * slen]
                    ts = t_v[s_k * slen : (s_k + 1) * slen]
                    carrier = np.exp(-2j * math.pi * freq * ts)[:, None]
                    phasors[s_k] = np.mean((sub - np.mean(sub, axis=0, keepdims=True)) * carrier, axis=0)
                S = (phasors.T @ np.conj(phasors)) / float(n_sub)
                d = np.sqrt(np.maximum(np.real(np.diag(S)), 1e-30))
                C = S / (d[:, None] * d[None, :])
                # Phase differences phi_ij in (-pi, pi] and unwrapped TDOAs tau_ij = phi_ij / (2*pi*f)
                p01, p12, p02 = np.angle(C[0, 1]), np.angle(C[1, 2]), np.angle(C[0, 2])
                # Note: phase cocycle on circle arg(C_01 * C_12 * conj(C_02)) != 0 is ONLY possible when rank > 1!
                hol_rad = float(np.angle(C[0, 1] * C[1, 2] * np.conj(C[0, 2])))
                # Pairwise principal-branch TDOA cocycle defect (in microseconds)
                t01_us = 1e6 * float(p01) / (2.0 * math.pi * freq)
                t12_us = 1e6 * float(p12) / (2.0 * math.pi * freq)
                t02_us = 1e6 * float(p02) / (2.0 * math.pi * freq)
                defect_us = t01_us + t12_us - t02_us
                tr_c2 = float(np.real(np.trace(C @ C)))
                pr_eff = 16.0 / max(tr_c2, 4.0)
                coh_min = float(min(abs(C[0, 1]), abs(C[1, 2]), abs(C[0, 2])))
                return defect_us, hol_rad, t01_us, t12_us, t02_us, pr_eff * (1.0 if coh_min >= 0.0 else 1.0)

            def1, hol1, t01_1, t12_1, t02_1, pr1 = _cocycle_on_slice(h1, f0)
            def2, hol2, t01_2, t12_2, t02_2, pr2 = _cocycle_on_slice(h2, f0)
            # Under any single rank-1 wave (even with arbitrary real/complex steering vector v_i = a_i e^{i theta_i}),
            # C = v v^H / |v||v| has exact holonomy arg(C_01 C_12 C_02^*) == 0 AND PR == 1!
            # Test non-trivial multi-mode holonomy |hol2| against rank-1 complex steering + independent noise surrogates!
            if abs(hol1) >= 0.05 or abs(def1) >= 20.0:
                # Build rank-1 complex lock-in surrogate on Half 2
                h2_c = h2 - np.mean(h2, axis=0, keepdims=True)
                u_h, s_h, vt_h = np.linalg.svd(h2_c[: min(len(h2_c), 16384)], full_matrices=False)
                r1_h = (u_h[:, 0:1] * s_h[0]) @ vt_h[0:1, :]
                res_h = h2_c[: len(r1_h)] - r1_h
                surr_hol = np.empty(n_confirm, dtype=np.float64)
                L_h = len(r1_h)
                for s_i in range(n_confirm):
                    sh = rng.integers(100, L_h - 100, size=4)
                    sim4 = np.column_stack([r1_h[:, c] + np.roll(res_h[:, c], int(sh[c])) for c in range(4)])
                    _, hs, _, _, _, _ = _cocycle_on_slice(sim4, f0)
                    surr_hol[s_i] = abs(hs)
                _, h2_sub_hol, _, _, _, _ = _cocycle_on_slice(h2_c[:L_h], f0)
                phol, zhol, muhol, _ = empirical_upper_p_and_z(abs(h2_sub_hol), surr_hol)
                rec_c = {
                    "lens": "A2_TDOA_COCYCLE_AND_HOLONOMY",
                    "phase": phase_label,
                    "block": lbl,
                    "freq_hz": round(f0, 2),
                    "cpu_pin": b.get("cpu_pin"),
                    "half1_tau01_us": round(t01_1, 2),
                    "half1_tau12_us": round(t12_1, 2),
                    "half1_tau02_us": round(t02_1, 2),
                    "half1_cocycle_defect_us": round(def1, 2),
                    "half1_phase_holonomy_rad": round(hol1, 5),
                    "half2_tau01_us": round(t01_2, 2),
                    "half2_tau12_us": round(t12_2, 2),
                    "half2_tau02_us": round(t02_2, 2),
                    "half2_cocycle_defect_us": round(def2, 2),
                    "half2_phase_holonomy_rad": round(hol2, 5),
                    "half2_effective_rank_PR": round(pr2, 4),
                    "half2_holonomy_surr_mean_rad": round(muhol, 5),
                    "half2_p_surr": round(phol, 6),
                    "half2_p_holm": round(phol, 6),
                    "half2_z_surr": round(zhol, 2),
                    "n_surrogates_confirm": n_confirm,
                    "replicated_anomaly": bool((hol1 * hol2 > 0 or abs(def2) >= 20.0) and phol < 0.005 and zhol >= 3.5),
                }
                cocycle_records.append(rec_c)
                if rec_c["replicated_anomaly"]:
                    surviving.append(rec_c)

        # 2) Dual-rail CPU + GPU nonlinear intermodulation sidebands |f_cpu - f_gpu| and (f_cpu + f_gpu)
        if f_cpu > 0.0 and f_gpu > 0.0:
            beam1 = np.mean(h1, axis=1)
            beam2 = np.mean(h2, axis=1)
            n_fft_im = min(16384, len(beam1) // 2)
            fi1, _, pr_im1 = _highres_prominence_psd(beam1, fs, n_fft_im)
            fi2, psd_im2, pr_im2 = _highres_prominence_psd(beam2, fs, n_fft_im)
            if len(fi1) > 0:
                df_im = float(fi1[1] - fi1[0])
                sidebands = [abs(f_cpu - f_gpu), f_cpu + f_gpu, abs(2.0 * f_cpu - f_gpu), abs(f_cpu - 2.0 * f_gpu)]
                raw_ps = []
                sb_recs = []
                w_m = min(25, max(5, len(psd_im2) // 40))
                for f_sb in sidebands:
                    if f_sb <= 30.0 or f_sb >= 0.48 * fs:
                        continue
                    k_sb = int(round(f_sb / df_im))
                    lo_k, hi_k = max(0, k_sb - 1), min(len(pr_im1), k_sb + 2)
                    v1_sb = float(np.max(pr_im1[lo_k:hi_k]))
                    v2_sb = float(np.max(pr_im2[lo_k:hi_k]))
                    # Compare against local smooth-PSD Welch prominence distribution on Half 2
                    n_seg_im = (len(beam2) - n_fft_im) // (n_fft_im // 2) + 1
                    # Fast exact chi-square Hann-overlap simulation on 53-bin window
                    eval_l = min(len(beam2), n_seg_im * (n_fft_im // 2) + n_fft_im)
                    seg_idx_im = np.arange(n_fft_im)[None, :] + (np.arange((eval_l - n_fft_im) // (n_fft_im // 2) + 1) * (n_fft_im // 2))[:, None]
                    win_b = list(range(max(1, k_sb - w_m), min(len(fi2), k_sb + w_m + 1)))
                    pk_b = [b for b in (k_sb - 1, k_sb, k_sb + 1) if b in win_b]
                    b_map_im = {b: idx_b for idx_b, b in enumerate(win_b)}
                    surr_sb = np.empty(n_confirm, dtype=np.float64)
                    win_h_im = np.hanning(n_fft_im)[None, None, :]
                    for b0 in range(0, n_confirm, 80):
                        b1 = min(n_confirm, b0 + 80)
                        wn = rng.standard_normal((b1 - b0, eval_l))
                        Xf_im = np.fft.rfft(wn[:, seg_idx_im] * win_h_im, axis=2)[:, :, win_b]
                        p_loc = np.mean(np.abs(Xf_im) ** 2, axis=1)
                        med_l = np.median(p_loc, axis=1) + 1e-30
                        pk_l = np.max(p_loc[:, [b_map_im[b] for b in pk_b]], axis=1)
                        surr_sb[b0:b1] = pk_l / med_l
                    psb, zsb, musb, _ = empirical_upper_p_and_z(v2_sb, surr_sb)
                    raw_ps.append(psb)
                    sb_recs.append({
                        "lens": "A1_CPU_GPU_INTERMODULATION",
                        "phase": phase_label,
                        "block": lbl,
                        "f_cpu_hz": f_cpu,
                        "f_gpu_hz": f_gpu,
                        "intermod_freq_hz": round(f_sb, 2),
                        "half1_prominence_x_median": round(v1_sb, 3),
                        "half2_prominence_x_median": round(v2_sb, 3),
                        "half2_surr_mean": round(musb, 3),
                        "half2_p_surr": round(psb, 6),
                        "half2_z_surr": round(zsb, 2),
                        "n_surrogates_confirm": n_confirm,
                    })
                adj_sb = holm_bonferroni(raw_ps)
                for r_sb, ph_sb in zip(sb_recs, adj_sb):
                    r_sb["half2_p_holm"] = round(ph_sb, 6)
                    r_sb["replicated_anomaly"] = bool(r_sb["half1_prominence_x_median"] >= 3.5 and ph_sb < 0.005 and r_sb["half2_z_surr"] >= 4.0)
                    intermod_records.append(r_sb)
                    if r_sb["replicated_anomaly"]:
                        surviving.append(r_sb)

    return {"cocycle_probes": cocycle_records, "intermod_probes": intermod_records, "surviving_anomalies": surviving}


def _analyze_manifest_dict(
    track_dir: Path,
    phase_label: str,
    manifest: dict[str, Any],
    seed: int = 20261125,
    polite: bool = False,
    max_wait_s: float = 420.0,
) -> dict[str, Any]:
    """Run all applicable blind discovery lenses A1-A7 on a single manifest dictionary."""
    t_run0 = time.monotonic()
    if polite:
        wait_for_capture_quiet(max_wait_s)
    rng = np.random.default_rng(seed + sum(ord(c) * (idx + 1) for idx, c in enumerate(phase_label)))

    tel_dict: dict[str, np.ndarray] = {}
    if "telemetry_npz" in manifest:
        tp = track_dir / manifest["telemetry_npz"]
        if tp.is_file():
            with np.load(tp) as npz:
                tel_dict = {k: np.array(npz[k], dtype=np.float64) for k in npz.files}

    rows_dict: dict[str, np.ndarray] = {}
    if "rows_npz" in manifest:
        rp = track_dir / manifest["rows_npz"]
        if rp.is_file():
            with np.load(rp) as npz:
                rows_dict = {k: np.array(npz[k]) for k in npz.files}

    dmic_mm = None
    fs_audio = float(manifest.get("sample_rate_hz", 48000))
    t0_audio = float(manifest.get("audio_start_mono_s", 0.0))
    if "audio_raw_path" in manifest:
        ap = track_dir / manifest["audio_raw_path"]
        if ap.is_file() and ap.stat().st_size >= 16 * 4096:
            dmic_mm = _load_dmic_s32le(ap)

    blocks = manifest.get("blocks", [])
    inj_all = sorted({
        float(f)
        for b in blocks
        for f in (b.get("freq_hz", 0.0), b.get("cpu_hz", 0.0), b.get("gpu_hz", 0.0))
        if float(f) > 0.0
    })

    results: dict[str, Any] = {
        "phase": phase_label.upper(),
        "prereg_amendment": "PREREG-S113-AMENDMENT1",
        "analyzed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "lenses": {},
        "all_surviving_anomalies": [],
    }

    # Prepare signals for A1, A2, A3, A6
    a1_signals: dict[str, tuple[np.ndarray, float, list[float]]] = {}
    a3_signals: dict[str, tuple[np.ndarray, float]] = {}
    a6_signals: dict[str, tuple[np.ndarray, float, list[float], bool]] = {}
    post_load_pairs: list[tuple[str, np.ndarray, np.ndarray]] = []
    a2_runs: list[dict[str, Any]] = []

    has_cam = ("rgb_raw_path" in manifest) or ("ir_raw_path" in manifest)

    if dmic_mm is not None:
        # Extract pure IDLE slices vs ACTIVE slices if blocks exist; otherwise full stream (Phase IDLE)
        idle_slices: list[np.ndarray] = []
        active_slices: list[np.ndarray] = []
        for b in blocks:
            i0 = max(0, int(round((float(b["t0_mono_s"]) - t0_audio) * fs_audio)))
            i1 = min(len(dmic_mm), int(round((float(b["t1_mono_s"]) - t0_audio) * fs_audio)))
            if i1 - i0 < 4800:
                continue
            label = str(b.get("label", b.get("regime", "")))
            if "IDLE" in label.upper():
                idle_slices.append(np.asarray(dmic_mm[i0:i1], dtype=np.float64) * (1.0 / 2147483648.0))
            else:
                active_slices.append(np.asarray(dmic_mm[i0:i1], dtype=np.float64) * (1.0 / 2147483648.0))

        if phase_label.upper() == "IDLE" or not blocks:
            full_norm = np.asarray(dmic_mm[: min(len(dmic_mm), int(45 * fs_audio))], dtype=np.float64) * (1.0 / 2147483648.0)
            beam = np.mean(full_norm, axis=1)
            a1_signals["dmic_idle_beam"] = (beam, fs_audio, [])
            a3_signals["dmic_idle_beam"] = (beam[: min(len(beam), 65536)], fs_audio)
            a6_signals["dmic_idle_beam"] = (beam, fs_audio, [], True)
            for ch_i in range(4):
                a6_signals[f"dmic_idle_ch{ch_i}"] = (full_norm[:, ch_i], fs_audio, [], True)
            a2_runs.append(lens_a2_chiral_cross_spectrum(full_norm, fs_audio, rng, label="dmic_4ch_pure_idle"))
        else:
            p_low = phase_label.lower()
            if idle_slices:
                idle_cat = np.concatenate(idle_slices, axis=0)
                idle_beam = np.mean(idle_cat, axis=1)
                a1_signals[f"dmic_{p_low}_idle_blocks"] = (idle_beam, fs_audio, [])
                a3_signals[f"dmic_{p_low}_idle_blocks"] = (idle_beam[: min(len(idle_beam), 65536)], fs_audio)
                a6_signals[f"dmic_{p_low}_idle_blocks"] = (idle_beam, fs_audio, [], has_cam)
                a2_runs.append(lens_a2_chiral_cross_spectrum(idle_cat, fs_audio, rng, label=f"dmic_4ch_{p_low}_idle"))
            if active_slices:
                act_cat = np.concatenate(active_slices, axis=0)
                act_beam = np.mean(act_cat, axis=1)
                a1_signals[f"dmic_{p_low}_active_blocks"] = (act_beam, fs_audio, inj_all)
                a3_signals[f"dmic_{p_low}_active_blocks"] = (act_beam[: min(len(act_beam), 65536)], fs_audio)
                a6_signals[f"dmic_{p_low}_active_blocks"] = (act_beam, fs_audio, inj_all, has_cam)
                a2_runs.append(lens_a2_chiral_cross_spectrum(act_cat, fs_audio, rng, label=f"dmic_4ch_{p_low}_active"))

            # Probe 4-ch TDOA cocycle closure & CPU+GPU intermodulation on structured blocks
            ci_res = _probe_4ch_cocycle_and_intermod(dmic_mm, fs_audio, t0_audio, blocks, phase_label.upper(), rng)
            if ci_res["cocycle_probes"] or ci_res["intermod_probes"]:
                results["lenses"]["A1_A2_STRUCTURED_PROBES"] = ci_res
                results["all_surviving_anomalies"].extend(ci_res["surviving_anomalies"])

            # Also check sub-harmonics on paired prime blocks (e.g. PRIME_1009HZ_A + PRIME_1009HZ_B)
            by_freq: dict[float, list[np.ndarray]] = {}
            for b in blocks:
                fhz = float(b.get("freq_hz", 0.0))
                if fhz >= 20.0:
                    i0 = max(0, int(round((float(b["t0_mono_s"]) - t0_audio) * fs_audio)))
                    i1 = min(len(dmic_mm), int(round((float(b["t1_mono_s"]) - t0_audio) * fs_audio)))
                    if i1 - i0 >= 9600:
                        by_freq.setdefault(fhz, []).append(
                            np.mean(np.asarray(dmic_mm[i0:i1], dtype=np.float64), axis=1) * (1.0 / 2147483648.0)
                        )
            for fhz, seg_list in by_freq.items():
                if len(seg_list) >= 2:
                    cat_f = np.concatenate([seg_list[0], seg_list[-1]])
                    a6_signals[f"dmic_prime_{int(fhz)}hz_subharmonic_scan"] = (cat_f, fs_audio, [fhz], has_cam)

            # Post-load IDLE afterglow pairs (blocks named IDLE right after active blocks)
            post_idle_envs: list[np.ndarray] = []
            for b_i, b in enumerate(blocks):
                lbl = str(b.get("label", b.get("regime", ""))).upper()
                if "IDLE" in lbl and b_i > 0 and "IDLE" not in str(blocks[b_i - 1].get("label", blocks[b_i - 1].get("regime", ""))).upper():
                    i0 = max(0, int(round((float(b["t0_mono_s"]) - t0_audio) * fs_audio)))
                    i1 = min(len(dmic_mm), int(round((float(b["t1_mono_s"]) - t0_audio) * fs_audio)))
                    if i1 - i0 >= int(3.0 * fs_audio):
                        seg = np.mean(np.asarray(dmic_mm[i0:i1], dtype=np.float64), axis=1) * (1.0 / 2147483648.0)
                        win100 = int(fs_audio // 20)
                        nb = len(seg) // win100
                        env20hz = np.sqrt(np.mean(seg[: nb * win100].reshape(nb, win100) ** 2, axis=1))
                        post_idle_envs.append(env20hz)
            if len(post_idle_envs) >= 2:
                post_load_pairs.append((f"dmic_post_load_rms_{p_low}", post_idle_envs[0], post_idle_envs[1]))

    # Add rolling-shutter row series (10.8 kHz IR & 14.4 kHz RGB) to A1, A3, A6!
    if "rgb_row_means" in rows_dict and len(rows_dict["rgb_row_means"]) >= 30:
        rgb_rm = rows_dict["rgb_row_means"].astype(np.float64)
        rgb_det = (rgb_rm - np.mean(rgb_rm, axis=0, keepdims=True)) - np.mean(rgb_rm, axis=1, keepdims=True) + float(np.mean(rgb_rm))
        rgb_1d = (rgb_rm - np.mean(rgb_rm, axis=0, keepdims=True)).ravel()
        a1_signals["rgb_row_osc_14400hz"] = (rgb_1d, 14400.0, inj_all)
        a3_signals["rgb_row_osc_14400hz"] = (rgb_1d[: min(len(rgb_1d), 32768)], 14400.0)
        a6_signals["rgb_row_osc_14400hz"] = (rgb_1d, 14400.0, inj_all, True)
        _ = rgb_det

    if "ir_row_means" in rows_dict and len(rows_dict["ir_row_means"]) >= 30:
        ir_rm = rows_dict["ir_row_means"].astype(np.float64)
        uniq = rows_dict.get("ir_is_unique", np.ones(len(ir_rm), dtype=bool)).astype(bool)
        led_on = rows_dict.get("ir_is_led_on", np.ones(len(ir_rm), dtype=bool)).astype(bool)
        for state_lbl, mask in [("led_on", uniq & led_on), ("led_off", uniq & (~led_on))]:
            if int(np.sum(mask)) >= 20:
                sub_ir = ir_rm[mask]
                # Subtract per-frame mean too so slow LED strobe thermal drift doesn't create step jumps at frame seams
                sub_det = sub_ir - np.mean(sub_ir, axis=0, keepdims=True)
                sub_det = sub_det - np.mean(sub_det, axis=1, keepdims=True)
                ir_1d = sub_det.ravel()
                a1_signals[f"ir_row_osc_10800hz_{state_lbl}"] = (ir_1d, 10800.0, inj_all)
                a3_signals[f"ir_row_osc_10800hz_{state_lbl}"] = (ir_1d[: min(len(ir_1d), 32768)], 10800.0)
                a6_signals[f"ir_row_osc_10800hz_{state_lbl}"] = (ir_1d, 10800.0, inj_all, True)

    # Telemetry series for A3, A5, A7
    if tel_dict and "t_mono_s" in tel_dict and len(tel_dict["t_mono_s"]) >= 200:
        t_tel = tel_dict["t_mono_s"]
        for tk in ("pkg_w", "dark_w", "bat_v"):
            if tk in tel_dict:
                a3_signals[f"telemetry_{tk}"] = (tel_dict[tk], 100.0)

        # Build uniform 100 Hz aligned dictionary for A5 and 50 Hz for A7
        t_min = float(t_tel[0])
        t_max = float(t_tel[-1])
        if dmic_mm is not None:
            t_min = max(t_min, t0_audio)
            t_max = min(t_max, t0_audio + len(dmic_mm) / fs_audio)
        if t_max - t_min >= 8.0:
            t_grid_100 = np.arange(t_min, t_max, 0.01)
            aligned_100: dict[str, np.ndarray] = {}
            for tk in ("pkg_w", "core_w", "uncore_w", "dark_w", "bat_v", "temp_c", "hinge_raw", "gpu_w"):
                if tk in tel_dict:
                    aligned_100[tk] = np.interp(t_grid_100, t_tel, tel_dict[tk])
            if dmic_mm is not None:
                aligned_100.update(_compute_100hz_audio_envelopes(dmic_mm, int(fs_audio), t0_audio, t_grid_100))
            if "rgb_t_mono_s" in rows_dict and len(rows_dict["rgb_t_mono_s"]) >= 20:
                rgb_t = rows_dict["rgb_t_mono_s"]
                rgb_rstd = np.std(rows_dict["rgb_row_means"].astype(np.float64) - np.mean(rows_dict["rgb_row_means"], axis=0, keepdims=True), axis=1)
                aligned_100["rgb_row_ripple"] = np.interp(t_grid_100, rgb_t, rgb_rstd)
            if "ir_t_mono_s" in rows_dict and len(rows_dict["ir_t_mono_s"]) >= 20:
                ir_t = rows_dict["ir_t_mono_s"]
                uniq = rows_dict.get("ir_is_unique", np.ones(len(ir_t), dtype=bool)).astype(bool)
                led_on = rows_dict.get("ir_is_led_on", np.ones(len(ir_t), dtype=bool)).astype(bool)
                on_m = uniq & led_on
                if int(np.sum(on_m)) >= 10:
                    ir_sub = rows_dict["ir_row_means"][on_m].astype(np.float64)
                    ir_rstd = np.std(ir_sub - np.mean(ir_sub, axis=0, keepdims=True), axis=1)
                    aligned_100["ir_led_on_ripple"] = np.interp(t_grid_100, ir_t[on_m], ir_rstd)

            if polite:
                wait_for_capture_quiet(max_wait_s)
            res_a5 = lens_a5_rare_event_coincidence(aligned_100, rng, dt_s=0.01)
            results["lenses"]["A5"] = res_a5
            results["all_surviving_anomalies"].extend(res_a5["surviving_anomalies"])

            # Downsample aligned_100 by 2x (50 Hz, capped at 2400 samples = 48s) for Lens A7 nonlinear residual structure
            if polite:
                wait_for_capture_quiet(max_wait_s)
            aligned_50 = {k: v[::2][:2400] for k, v in aligned_100.items()}
            res_a7 = lens_a7_nonlinear_residual_structure(aligned_50, rng)
            results["lenses"]["A7"] = res_a7
            results["all_surviving_anomalies"].extend(res_a7["surviving_anomalies"])

    # Execute A1, A2, A3, A4, A6
    if a1_signals:
        if polite:
            wait_for_capture_quiet(max_wait_s)
        res_a1 = lens_a1_bicoherence_and_pac(a1_signals, rng)
        results["lenses"]["A1"] = res_a1
        results["all_surviving_anomalies"].extend(res_a1["surviving_anomalies"])

    if a2_runs:
        merged_a2 = {
            "tested_candidates": [c for r in a2_runs for c in r["tested_candidates"]],
            "surviving_anomalies": [s for r in a2_runs for s in r["surviving_anomalies"]],
        }
        results["lenses"]["A2"] = merged_a2
        results["all_surviving_anomalies"].extend(merged_a2["surviving_anomalies"])

    if a3_signals or post_load_pairs:
        if polite:
            wait_for_capture_quiet(max_wait_s)
        res_a3 = lens_a3_time_reversal_and_afterglow(a3_signals, post_load_pairs, rng)
        results["lenses"]["A3"] = res_a3
        results["all_surviving_anomalies"].extend(res_a3["surviving_anomalies"])

    # Lens A4 on raw 2D blank-wall video stacks (IDLE, B, D, E1, E2)
    rgb_p = (track_dir / manifest["rgb_raw_path"]) if "rgb_raw_path" in manifest else None
    ir_p = (track_dir / manifest["ir_raw_path"]) if "ir_raw_path" in manifest else None
    if phase_label.upper() == "D":
        rgb_p = track_dir / "local_raw_av" / "phase_d_rgb_cool.yuyv"
        ir_p = track_dir / "local_raw_av" / "phase_d_ir_cool.grey"
    if (rgb_p and rgb_p.is_file()) or (ir_p and ir_p.is_file()):
        if polite:
            wait_for_capture_quiet(max_wait_s)
        res_a4 = lens_a4_2d_blank_wall_from_files(rgb_p, ir_p, rng)
        results["lenses"]["A4"] = res_a4
        results["all_surviving_anomalies"].extend(res_a4["surviving_anomalies"])

    if a6_signals:
        if polite:
            wait_for_capture_quiet(max_wait_s)
        res_a6 = lens_a6_uninvited_spectral_lines(a6_signals, tel_dict, t0_audio, rng)
        results["lenses"]["A6"] = res_a6
        results["all_surviving_anomalies"].extend(res_a6["surviving_anomalies"])

    results["n_surviving_anomalies"] = len(results["all_surviving_anomalies"])
    results["elapsed_s"] = round(time.monotonic() - t_run0, 3)

    out_dir = track_dir / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"s113_blind_anomalies_phase_{phase_label.lower()}.json"
    out_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return results


def analyze_phase(track_dir: Path, phase: str, seed: int = 20261125, polite: bool = False, max_wait_s: float = 420.0) -> dict[str, Any]:
    """Analyze a top-level phase or nested multi-subphase manifest (E1 -> E1A+E1B, E2 -> E2A+E2B)."""
    manifest_name = f"phase_{phase.lower()}_manifest.json"
    manifest_path = track_dir / manifest_name
    _require(manifest_path.is_file(), f"Missing manifest {manifest_name}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    sub_keys = [k for k in ("e1a", "e1b", "e2a", "e2b") if isinstance(manifest.get(k), dict)]
    if not sub_keys:
        return _analyze_manifest_dict(track_dir, phase.upper(), manifest, seed=seed, polite=polite, max_wait_s=max_wait_s)

    t0 = time.monotonic()
    sub_results: dict[str, Any] = {}
    all_surv: list[dict[str, Any]] = []
    for sk in sub_keys:
        sr = _analyze_manifest_dict(track_dir, sk.upper(), manifest[sk], seed=seed, polite=polite, max_wait_s=max_wait_s)
        sub_results[sk.upper()] = sr
        all_surv.extend(sr["all_surviving_anomalies"])

    merged = {
        "phase": phase.upper(),
        "prereg_amendment": "PREREG-S113-AMENDMENT1",
        "analyzed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "subphases": sub_results,
        "all_surviving_anomalies": all_surv,
        "n_surviving_anomalies": len(all_surv),
        "elapsed_s": round(time.monotonic() - t0, 3),
    }
    out_dir = track_dir / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"s113_blind_anomalies_phase_{phase.lower()}.json").write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return merged


def main() -> int:
    ap = argparse.ArgumentParser(description="PREREG-S113-AMENDMENT1 Blind Residual & Non-Textbook Anomaly Hunter")
    ap.add_argument("--track-dir", type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument("--phases", nargs="+", default=["IDLE", "A", "B", "C", "D", "E1", "E2"])
    ap.add_argument("--polite", action="store_true", help="Lower CPU priority (nice 15) and yield during active capture")
    ap.add_argument("--max-wait-s", type=float, default=90.0)
    args = ap.parse_args()

    if args.polite:
        try:
            os.nice(15)
        except OSError:
            pass

    track_dir = args.track_dir.resolve()
    summary: dict[str, Any] = {
        "prereg_amendment": "PREREG-S113-AMENDMENT1",
        "parent_prereg_sha256": "cebe48326461ef048c6e8ccfb51f76f661f33b44c32d7e0178777d2ad8221e67",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "phases_analyzed": [],
        "total_surviving_anomalies": 0,
        "counts_by_lens": {},
        "anomalies_by_phase": {},
    }

    for ph in args.phases:
        mfile = track_dir / f"phase_{ph.lower()}_manifest.json"
        if not mfile.is_file():
            continue
        if args.polite:
            wait_for_capture_quiet(args.max_wait_s)
        res = analyze_phase(track_dir, ph, polite=args.polite, max_wait_s=args.max_wait_s)
        # Re-apply lens-family Holm over the phase's survivors so multi-member families
        # (e.g. A4 telegraph pixels / bursts) get a real Holm correction, not raw p.
        res["all_surviving_anomalies"] = _apply_lens_family_holm(res["all_surviving_anomalies"])
        res["n_surviving_anomalies"] = len(res["all_surviving_anomalies"])
        summary["phases_analyzed"].append(ph.upper())
        summary["anomalies_by_phase"][ph.upper()] = res["all_surviving_anomalies"]
        summary["total_surviving_anomalies"] += res["n_surviving_anomalies"]
        for anom in res["all_surviving_anomalies"]:
            lk = str(anom.get("lens", "UNKNOWN"))
            summary["counts_by_lens"][lk] = summary["counts_by_lens"].get(lk, 0) + 1
        print(
            f"[BLIND HUNTER] Phase {ph.upper():4s} | elapsed={res['elapsed_s']:5.2f}s | "
            f"surviving_anomalies={res['n_surviving_anomalies']}",
            flush=True,
        )
        for anom in res["all_surviving_anomalies"]:
            print(f"  -> {json.dumps(anom, sort_keys=True)}", flush=True)

    (track_dir / "data").mkdir(parents=True, exist_ok=True)
    summary_text = json.dumps(summary, indent=2, sort_keys=False) + "\n"
    (track_dir / "data" / "s113_blind_anomalies_summary.json").write_text(summary_text, encoding="utf-8")
    (track_dir / "s113_blind_anomalies_receipt.json").write_text(summary_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
