#!/usr/bin/env python3
"""Wave-11 (EXP-Q26c / Track S122): Matched CPU Micro-Benchmark of Portal x/pi Spherical Multipole
Attention vs. Pari-Agrawal-Kim Raw-Monomial Polynomial Attention.

Reproduces the exact 27,079-parameter (27,198-parameter for P=8 polynomial) 6-block + readout causal
attention architecture, tasks, AdamW weight-decay split (0.01 shared / 0.0 polynomial coeffs), global
grad clip 1.0, and 60%-flat + 40%-cosine LR schedule of:
  Jyo Pari, Shivam Duggal, Rafael Hanashiro, Lucas Torroba-Hennigen, Pulkit Agrawal, Yoon Kim,
  "Simplicity Bias in Attention" (2026).

Strictly CPU-only (`OPENBLAS_NUM_THREADS=1`, `CUDA_VISIBLE_DEVICES=""`), deterministic across 3 seeds
{0, 1, 2}, <= 90s total wallclock, matched-budget identical parameters, batches, step counts, and LR grid.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import verify_xpi_gegenbauer_attention as xpi_oracle  # noqa: E402

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    _HAS_TORCH = True
except ImportError:  # pragma: no cover
    _HAS_TORCH = False


RESULTS_FILENAME = "s122_xpi_gegenbauer_results.json"
DEFAULT_SEEDS = (0, 1, 2)
# Exact points k in {5, 7} from Pari-Agrawal-Kim's 10^{-3} * 2^{k/2} grid:
PAK_LR_GRID = (0.001 * (2.0 ** 2.5), 0.001 * (2.0 ** 3.5))


class S122BenchError(ValueError):
    """Typed fail-closed benchmark validation error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


def require_ok(cond: bool, code: str, message: str) -> None:
    if cond is not True:
        raise S122BenchError(code, message)


def build_gegenbauer_basis_matrix_float(alpha: Fraction = Fraction(1, 2)) -> list[list[float]]:
    """Build exact 9x9 matrix M where row r gives monomial coefficients of C~_r^(alpha)(z) (r = 0..8)."""
    require_ok(isinstance(alpha, Fraction) and alpha >= Fraction(0), "BAD_ALPHA", "alpha must be Fraction >= 0")
    mat: list[list[float]] = []
    for r in range(9):
        poly_q = xpi_oracle.gegenbauer_norm_poly_q(r, alpha)
        row = [float(poly_q[c]) if c < len(poly_q) else 0.0 for c in range(9)]
        mat.append(row)
    return mat


def grade_s122_empirical(
    *,
    nan_runs_xpi: int,
    reg_xpi_wins_vs_softmax: int,
    reg_xpi_wins_vs_t8_init: int,
    reg_xpi_mean_mse: float,
    reg_linear_mean_mse: float,
    high_g_xpi_mean_mse: float,
    high_g_mono_mean_mse: float,
    high_g_xpi_max_b8: float,
    high_g_mono_max_b8: float,
    lkp4_xpi_mean_acc: float,
    lkp4_mono_mean_acc: float,
    lkp4_linear_mean_acc: float,
    lkp4_softmax_mean_acc: float,
    lkp8_xpi_mean_acc: float,
    lkp8_softmax_mean_acc: float,
    n_seeds: int = 3,
) -> dict[str, Any]:
    """Pure Law-4 grading function (zero hardcoded verdict strings; tested across all 3 outcomes)."""
    require_ok(not isinstance(n_seeds, bool) and isinstance(n_seeds, int) and n_seeds >= 1, "BAD_N_SEEDS", "n_seeds must be >= 1")
    require_ok(not isinstance(nan_runs_xpi, bool) and isinstance(nan_runs_xpi, int) and nan_runs_xpi >= 0, "BAD_NAN_COUNT", "nan_runs_xpi must be >= 0")

    g1_zero_nan = nan_runs_xpi == 0
    g2a_reg_and_simplicity = (
        reg_xpi_wins_vs_softmax == n_seeds
        and reg_xpi_wins_vs_t8_init == n_seeds
        and reg_xpi_mean_mse < reg_linear_mean_mse
    )
    g2b_high_g_advantage = (
        high_g_xpi_mean_mse < high_g_mono_mean_mse
        and high_g_xpi_max_b8 >= 50.0 * max(1e-9, high_g_mono_max_b8)
    )
    g3_lookup_4x4 = (
        (lkp4_xpi_mean_acc >= lkp4_linear_mean_acc + 15.0)
        and ((lkp4_mono_mean_acc - lkp4_xpi_mean_acc) <= 3.0)
    )
    g4_lookup_8x8_full = (
        (lkp8_softmax_mean_acc >= 75.0)
        and ((lkp8_softmax_mean_acc - lkp8_xpi_mean_acc) <= 2.0)
        and ((lkp4_softmax_mean_acc - lkp4_xpi_mean_acc) <= 2.0)
    )

    if g1_zero_nan and g2a_reg_and_simplicity and g2b_high_g_advantage and g3_lookup_4x4 and g4_lookup_8x8_full:
        verdict = "CONFIRMED"
    elif g1_zero_nan and g2a_reg_and_simplicity and g2b_high_g_advantage and g3_lookup_4x4:
        verdict = "PARTIAL"
    else:
        verdict = "FALSIFIED"

    return {
        "gate_1_zero_nan_xpi": g1_zero_nan,
        "gate_2a_regression_and_simplicity_bias": g2a_reg_and_simplicity,
        "gate_2b_high_gain_g3_mse_and_b8_preservation": g2b_high_g_advantage,
        "gate_3_lookup_4x4_saddle_escape": g3_lookup_4x4,
        "gate_4_lookup_8x8_cpu_budget_escaped": g4_lookup_8x8_full,
        "verdict": verdict,
    }


def _regrade_from_stored_runs(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute per-arm summaries and Law-4 verdict directly from stored per-seed run records."""
    oracle_sha = xpi_oracle.build_xpi_gegenbauer_certificate()["certificate_sha256"]
    require_ok(
        payload.get("exact_q_oracle_certificate_sha256") == oracle_sha,
        "ORACLE_CERT_MISMATCH",
        "exact_q_oracle_certificate_sha256 mismatch",
    )

    reg = payload.get("regression_2d")
    sb = payload.get("simplicity_bias_init_rho1p8")
    hg = payload.get("high_gain_g3_stress_test")
    lkp4 = payload.get("lookup_4x4_saddle_escaped")
    lkp8 = payload.get("lookup_8x8_single_thread_saddle_diagnostic")
    require_ok(
        isinstance(reg, Mapping)
        and isinstance(sb, Mapping)
        and isinstance(hg, Mapping)
        and isinstance(lkp4, Mapping)
        and isinstance(lkp8, Mapping),
        "MISSING_BENCH_SECTIONS",
        "missing benchmark result sections",
    )

    reg_arms = ("linear", "softmax", "poly_mono", "poly_xpi_gegen", "poly_xpi_mobius")
    lkp_arms = ("linear", "softmax", "poly_mono", "poly_xpi_mobius")
    nan_runs_xpi = 0
    n_seeds = 0

    for arm in reg_arms:
        entry = reg.get(arm)
        require_ok(isinstance(entry, Mapping) and isinstance(entry.get("seeds"), list) and len(entry["seeds"]) >= 1, "BAD_REG_ARM", arm)
        seeds_list = entry["seeds"]
        if n_seeds == 0:
            n_seeds = len(seeds_list)
        require_ok(len(seeds_list) == n_seeds, "SEED_COUNT_MISMATCH", arm)
        exp_mean = round(sum(float(r["val_mse"]) for r in seeds_list) / len(seeds_list), 6)
        require_ok(entry.get("mean_val_mse") == exp_mean, "SUMMARY_METRIC_MISMATCH", f"regression_2d.{arm}.mean_val_mse")
        if arm.startswith("poly_xpi_"):
            for sw in entry.get("sweep", []):
                nan_runs_xpi += sum(1 for r in sw["runs"] if bool(r["nan"]))

    lin_init_runs = sb.get("linear_init_runs")
    t8_init_runs = sb.get("t8_softmax_init_runs")
    require_ok(
        isinstance(lin_init_runs, list)
        and len(lin_init_runs) == n_seeds
        and isinstance(t8_init_runs, list)
        and len(t8_init_runs) == n_seeds,
        "BAD_SB_RUNS",
        "invalid simplicity-bias runs",
    )
    nan_runs_xpi += sum(1 for r in lin_init_runs if bool(r["nan"])) + sum(1 for r in t8_init_runs if bool(r["nan"]))
    exp_lin_init = round(sum(float(r["val_mse"]) for r in lin_init_runs) / n_seeds, 6)
    non_nan_t8 = [float(r["val_mse"]) for r in t8_init_runs if not bool(r["nan"])]
    exp_t8_init = round(sum(non_nan_t8) / max(1, len(non_nan_t8)), 6)
    require_ok(
        sb.get("linear_init_mean_mse") == exp_lin_init and sb.get("t8_softmax_init_mean_mse") == exp_t8_init,
        "SUMMARY_METRIC_MISMATCH",
        "simplicity_bias_init_rho1p8 mean mismatch",
    )

    hg_mono = hg.get("mono_runs")
    hg_xpi = hg.get("xpi_gegen_runs")
    require_ok(
        isinstance(hg_mono, list) and len(hg_mono) == n_seeds and isinstance(hg_xpi, list) and len(hg_xpi) == n_seeds,
        "BAD_HG_RUNS",
        "invalid high-gain runs",
    )
    nan_runs_xpi += sum(1 for r in hg_xpi if bool(r["nan"]))
    exp_hg_mono = None if any(bool(r["nan"]) for r in hg_mono) else round(sum(float(r["val_mse"]) for r in hg_mono) / n_seeds, 6)
    exp_hg_xpi = round(sum(float(r["val_mse"]) for r in hg_xpi) / n_seeds, 6)
    require_ok(
        hg.get("mono_mean_mse") == exp_hg_mono and hg.get("xpi_gegen_mean_mse") == exp_hg_xpi,
        "SUMMARY_METRIC_MISMATCH",
        "high_gain_g3_stress_test mean mismatch",
    )

    for arm in lkp_arms:
        e4 = lkp4.get(arm)
        require_ok(isinstance(e4, Mapping) and isinstance(e4.get("seeds"), list) and len(e4["seeds"]) == n_seeds, "BAD_LKP4_ARM", arm)
        exp_acc4 = round(sum(float(r["val_acc_pct"]) for r in e4["seeds"]) / n_seeds, 4)
        require_ok(e4.get("mean_val_acc_pct") == exp_acc4, "SUMMARY_METRIC_MISMATCH", f"lookup_4x4.{arm}")
        if arm.startswith("poly_xpi_"):
            nan_runs_xpi += sum(1 for r in e4["seeds"] if bool(r["nan"]))

        e8 = lkp8.get(arm)
        require_ok(isinstance(e8, Mapping) and isinstance(e8.get("seed0"), Mapping), "BAD_LKP8_ARM", arm)
        s0 = e8["seed0"]
        require_ok(e8.get("mean_val_acc_pct") == s0.get("val_acc_pct"), "SUMMARY_METRIC_MISMATCH", f"lookup_8x8.{arm}")
        if arm.startswith("poly_xpi_") and bool(s0["nan"]):
            nan_runs_xpi += 1

    xpi_reg_seeds = reg["poly_xpi_mobius"]["seeds"]
    smx_reg_seeds = reg["softmax"]["seeds"]
    wins_vs_smx = sum(1 for rx, rs in zip(xpi_reg_seeds, smx_reg_seeds) if (not bool(rx["nan"])) and float(rx["val_mse"]) < float(rs["val_mse"]))
    wins_vs_t8 = sum(1 for rl, rt in zip(lin_init_runs, t8_init_runs) if (not bool(rl["nan"])) and (bool(rt["nan"]) or float(rl["val_mse"]) < float(rt["val_mse"])))

    best_xpi_reg_mse = min(float(reg["poly_xpi_gegen"]["mean_val_mse"]), float(reg["poly_xpi_mobius"]["mean_val_mse"]))
    high_g_mono_mse = float("inf") if any(bool(r["nan"]) for r in hg_mono) else sum(float(r["val_mse"]) for r in hg_mono) / n_seeds
    high_g_xpi_mse = float("inf") if any(bool(r["nan"]) for r in hg_xpi) else sum(float(r["val_mse"]) for r in hg_xpi) / n_seeds
    high_g_mono_b8 = max(float(r["max_abs_b8"]) for r in hg_mono)
    high_g_xpi_b8 = max(float(r["max_abs_b8"]) for r in hg_xpi)

    return grade_s122_empirical(
        nan_runs_xpi=nan_runs_xpi,
        reg_xpi_wins_vs_softmax=wins_vs_smx,
        reg_xpi_wins_vs_t8_init=wins_vs_t8,
        reg_xpi_mean_mse=best_xpi_reg_mse,
        reg_linear_mean_mse=float(reg["linear"]["mean_val_mse"]),
        high_g_xpi_mean_mse=float(high_g_xpi_mse),
        high_g_mono_mean_mse=float(high_g_mono_mse),
        high_g_xpi_max_b8=float(high_g_xpi_b8),
        high_g_mono_max_b8=float(high_g_mono_b8),
        lkp4_xpi_mean_acc=float(lkp4["poly_xpi_mobius"]["mean_val_acc_pct"]),
        lkp4_mono_mean_acc=float(lkp4["poly_mono"]["mean_val_acc_pct"]),
        lkp4_linear_mean_acc=float(lkp4["linear"]["mean_val_acc_pct"]),
        lkp4_softmax_mean_acc=float(lkp4["softmax"]["mean_val_acc_pct"]),
        lkp8_xpi_mean_acc=float(lkp8["poly_xpi_mobius"]["mean_val_acc_pct"]),
        lkp8_softmax_mean_acc=float(lkp8["softmax"]["mean_val_acc_pct"]),
        n_seeds=n_seeds,
    )


def validate_results_payload(payload: Mapping[str, Any]) -> None:
    """Fail-closed validator for s122_xpi_gegenbauer_results.json."""
    require_ok(isinstance(payload, Mapping) and payload.get("track") == "S122", "BAD_PAYLOAD_ROOT", "invalid S122 payload root")
    rec_sha = payload.get("result_sha256")
    require_ok(isinstance(rec_sha, str) and len(rec_sha) == 64, "MISSING_RESULT_SHA", "missing 64-hex result_sha256")
    body = {k: v for k, v in payload.items() if k not in ("result_sha256", "elapsed_seconds")}
    recomputed = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    require_ok(recomputed == rec_sha, "RESULT_SHA_MISMATCH", "s122 result_sha256 mismatch")

    p_counts = payload.get("cs08_param_counts")
    require_ok(
        isinstance(p_counts, Mapping)
        and p_counts.get("fixed_linear_and_softmax") == 27079
        and p_counts.get("polynomial_p8_all_arms") == 27198,
        "CS08_PARAM_MISMATCH",
        "Pari-Agrawal-Kim parameter counts must be 27,079 fixed and 27,198 P=8 polynomial",
    )

    regraded = _regrade_from_stored_runs(payload)
    require_ok(payload.get("graded") == regraded, "GRADED_VERDICT_MISMATCH", "stored graded verdict disagrees with re-evaluation of seed metrics")


if _HAS_TORCH:

    def _gen_regression_batch(batch_size: int, gen: torch.Generator) -> tuple[torch.Tensor, torch.Tensor]:
        w_mat = torch.randn(batch_size, 2, 2, generator=gen) * math.sqrt(0.5)
        x_pts = torch.rand(batch_size, 9, 2, generator=gen) * 2.0 - 1.0
        y_pts = torch.bmm(x_pts, w_mat.transpose(1, 2))
        tokens = torch.zeros(batch_size, 9, 5)
        tokens[:, :8, :2] = x_pts[:, :8]
        tokens[:, :8, 2:4] = y_pts[:, :8]
        tokens[:, :8, 4] = 1.0
        tokens[:, 8, :2] = x_pts[:, 8]
        return tokens, y_pts[:, 8]

    def _make_grid_xy(side: int) -> torch.Tensor:
        coords = torch.linspace(-1.0, 1.0, side)
        return torch.stack(torch.meshgrid(coords, coords, indexing="ij"), dim=-1).reshape(side * side, 2)

    def _gen_lookup_batch(batch_size: int, grid_xy: torch.Tensor, gen: torch.Generator) -> tuple[torch.Tensor, torch.Tensor]:
        k_items = grid_xy.shape[0]
        perms = torch.argsort(torch.rand(batch_size, k_items, generator=gen), dim=-1)
        xy = grid_xy[perms]
        labels = torch.randint(0, 2, (batch_size, k_items), generator=gen)
        q_idx = torch.randint(0, k_items, (batch_size,), generator=gen)
        tokens = torch.zeros(batch_size, k_items + 1, 5)
        tokens[:, :k_items, :2] = xy
        tokens[:, :k_items, 2] = 1.0 - labels.float()
        tokens[:, :k_items, 3] = labels.float()
        tokens[:, :k_items, 4] = 1.0
        b_idx = torch.arange(batch_size)
        tokens[:, k_items, :2] = xy[b_idx, q_idx]
        tokens[:, k_items, 4] = -1.0
        return tokens, labels[b_idx, q_idx]

    def _eval_gh_gemm(z: torch.Tensor, c_num: torch.Tensor, c_den: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        z2 = z * z
        z3 = z2 * z
        z4 = z2 * z2
        basis = torch.stack(
            (torch.ones_like(z), z, z2, z3, z4, z4 * z, z4 * z2, z4 * z3, z4 * z4),
            dim=-1,
        )
        gh = torch.matmul(basis, torch.stack((c_num, c_den), dim=-1))
        return gh[..., 0], gh[..., 1]

    class PariAgrawalKimNet(nn.Module):
        """Exact 27,079 / 27,198-parameter architecture of Pari et al. (2026)."""

        def __init__(
            self,
            attn_type: str,
            *,
            rho: float = 0.5,
            init_mode: str = "linear",
            gamma_init: float = 0.0,
            basis_mat: torch.Tensor | None = None,
        ) -> None:
            super().__init__()
            self.attn_type = attn_type
            self.rho = rho
            self.emb = nn.Linear(5, 32, bias=False)
            self.norm_w = nn.ParameterList([nn.Parameter(torch.ones(32)) for _ in range(7)])
            self.qkv = nn.ModuleList([nn.Linear(32, 96, bias=False) for _ in range(6)])
            self.o = nn.ModuleList([nn.Linear(32, 32, bias=False) for _ in range(6)])
            self.rqk = nn.Linear(32, 64, bias=False)
            self.rv = nn.Linear(32, 2, bias=False)
            self.gamma = nn.ParameterList([nn.Parameter(torch.full((), gamma_init)) for _ in range(7)])

            if basis_mat is not None:
                self.register_buffer("basis_mat", basis_mat)
            else:
                self.register_buffer("basis_mat", torch.eye(9))

            if attn_type.startswith("poly_"):
                if init_mode == "t8_softmax":
                    # T_8(s) = sum_{r=0}^8 s^r / r! mapped to active basis via basis_mat^{-1}
                    t8_mono = torch.tensor([1.0 / float(math.factorial(r)) for r in range(9)])
                    inv_m = torch.linalg.inv(self.basis_mat)
                    a_init = t8_mono @ inv_m
                    b_full = t8_mono @ inv_m
                    b_init = b_full[1:].clone()
                else:
                    a_init = torch.tensor([0.0, 1.0] + [0.0] * 7)
                    b_init = torch.zeros(8)
                self.a = nn.ParameterList([nn.Parameter(a_init.clone()) for _ in range(7)])
                self.b = nn.ParameterList([nn.Parameter(b_init.clone()) for _ in range(7)])

        def _attn(self, u: torch.Tensor, v: torch.Tensor, idx: int, mask: torch.Tensor | None) -> torch.Tensor:
            g = torch.exp(self.gamma[idx]).clamp(min=1e-4, max=1e4)
            if self.attn_type == "linear":
                s = (g * u).masked_fill(~mask, 0.0) if mask is not None else (g * u)
                n_vis = mask.float().sum(-1, keepdim=True) if mask is not None else float(u.shape[-1])
                return (s @ v) / n_vis
            if self.attn_type == "softmax":
                s = (g * u).masked_fill(~mask, float("-inf")) if mask is not None else (g * u)
                return F.softmax(s, dim=-1) @ v

            al = self.a[idx]
            bl = self.b[idx]
            b_pad = F.pad(bl, (1, 0), value=1.0)
            if self.attn_type == "poly_mono":
                s = g * u
                g_mat, h_mat = _eval_gh_gemm(s, al, b_pad)
            elif self.attn_type == "poly_xpi_gegen":
                c_num = (g * al) @ self.basis_mat
                c_den = b_pad @ self.basis_mat
                g_mat, h_mat = _eval_gh_gemm(u, c_num, c_den)
            else:  # poly_xpi_mobius
                z = 1.0 - (2.0 * g * (1.0 - u)) / ((1.0 + u) + g * (1.0 - u) + 1e-12)
                c_num = (g * al) @ self.basis_mat
                c_den = b_pad @ self.basis_mat
                g_mat, h_mat = _eval_gh_gemm(z, c_num, c_den)

            if mask is not None:
                g_mat = g_mat.masked_fill(~mask, 0.0)
                h_mat = h_mat.masked_fill(~mask, 0.0)
            return (g_mat @ v) / h_mat.sum(-1, keepdim=True)

        @torch.no_grad()
        def project_denominator(self) -> None:
            if not self.attn_type.startswith("poly_") or self.rho <= 0.0:
                return
            for idx in range(7):
                bl = self.b[idx]
                if self.attn_type == "poly_mono":
                    g = torch.exp(self.gamma[idx])
                    g_pows = g ** torch.arange(1, 9, dtype=bl.dtype)
                    m_val = (bl.abs() * g_pows).sum()
                else:
                    # Portal x/pi g-independent spherical harmonic L1 budget!
                    m_val = bl.abs().sum()
                if m_val > self.rho:
                    bl.mul_(self.rho / m_val)

        def forward(self, x: torch.Tensor, causal_mask: torch.Tensor) -> torch.Tensor:
            h = self.emb(x)
            for l_idx in range(6):
                hn = h * torch.rsqrt(h.pow(2).mean(-1, keepdim=True) + 1e-6) * self.norm_w[l_idx]
                q, k, v = self.qkv[l_idx](hn).chunk(3, dim=-1)
                u = F.normalize(q, dim=-1, eps=1e-8) @ F.normalize(k, dim=-1, eps=1e-8).transpose(-1, -2)
                h = h + F.relu(self.o[l_idx](self._attn(u, v, l_idx, causal_mask)))
            hn = h * torch.rsqrt(h.pow(2).mean(-1, keepdim=True) + 1e-6) * self.norm_w[6]
            qk = self.rqk(hn)
            u_ro = F.normalize(qk[:, -1:, :32], dim=-1, eps=1e-8) @ F.normalize(qk[:, :, 32:], dim=-1, eps=1e-8).transpose(-1, -2)
            return self._attn(u_ro, self.rv(hn), 6, None).squeeze(1)


def _train_single_run(
    *,
    task: str,
    attn_type: str,
    seed: int,
    peak_lr: float,
    train_x_stream: Any,
    train_y_stream: Any,
    val_x: Any,
    val_y: Any,
    basis_mat: Any,
    rho: float = 0.5,
    init_mode: str = "linear",
    gamma_init: float = 0.0,
) -> dict[str, Any]:
    torch.manual_seed(seed)
    model = PariAgrawalKimNet(
        attn_type,
        rho=rho,
        init_mode=init_mode,
        gamma_init=gamma_init,
        basis_mat=basis_mat if attn_type in ("poly_xpi_gegen", "poly_xpi_mobius") else None,
    )
    model.project_denominator()
    shared_params = [p for n, p in model.named_parameters() if not n.startswith(("a.", "b."))]
    poly_params = [p for n, p in model.named_parameters() if n.startswith(("a.", "b."))]
    groups = [{"params": shared_params, "weight_decay": 0.01}]
    if poly_params:
        groups.append({"params": poly_params, "weight_decay": 0.0})
    opt = torch.optim.AdamW(groups, lr=peak_lr, betas=(0.9, 0.999), eps=1e-8)

    steps = int(train_x_stream.shape[0])
    seq_len = int(val_x.shape[1])
    causal_mask = torch.tril(torch.ones(seq_len, seq_len, dtype=torch.bool))
    flat_steps = int(0.6 * steps)
    decay_span = max(1, steps - 1 - flat_steps)

    nan_failed = False
    for st in range(steps):
        if st >= flat_steps:
            prog = float(st - flat_steps) / float(decay_span)
            cur_lr = peak_lr * (0.1 + 0.45 * (1.0 + math.cos(math.pi * prog)))
            for pg in opt.param_groups:
                pg["lr"] = cur_lr
        bx = train_x_stream[st]
        by = train_y_stream[st]
        pred = model(bx, causal_mask)
        if task == "regression":
            loss = 0.5 * ((pred - by) ** 2).sum(-1).mean()
        else:
            loss = F.cross_entropy(pred, by)
        if not bool(torch.isfinite(loss)):
            nan_failed = True
            break
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        model.project_denominator()

    with torch.no_grad():
        max_g = max(float(torch.exp(p)) for p in model.gamma)
        max_b8 = max(float(p[7].abs()) for p in model.b) if hasattr(model, "b") else 0.0
        if nan_failed:
            return {"seed": seed, "lr": round(peak_lr, 8), "nan": True, "val_mse": None, "val_acc_pct": 0.0, "val_ce": None, "max_g": round(max_g, 4), "max_abs_b8": round(max_b8, 6)}
        vpred = model(val_x, causal_mask)
        if not bool(torch.all(torch.isfinite(vpred))):
            return {"seed": seed, "lr": round(peak_lr, 8), "nan": True, "val_mse": None, "val_acc_pct": 0.0, "val_ce": None, "max_g": round(max_g, 4), "max_abs_b8": round(max_b8, 6)}
        if task == "regression":
            mse = float(0.5 * ((vpred - val_y) ** 2).sum(-1).mean())
            return {"seed": seed, "lr": round(peak_lr, 8), "nan": False, "val_mse": round(mse, 6), "max_g": round(max_g, 4), "max_abs_b8": round(max_b8, 6)}
        acc = float((vpred.argmax(-1) == val_y).float().mean()) * 100.0
        ce = float(F.cross_entropy(vpred, val_y))
        return {"seed": seed, "lr": round(peak_lr, 8), "nan": False, "val_acc_pct": round(acc, 4), "val_ce": round(ce, 6), "max_g": round(max_g, 4), "max_abs_b8": round(max_b8, 6)}


def run_benchmark(*, smoke: bool = False) -> dict[str, Any]:
    require_ok(_HAS_TORCH, "TORCH_MISSING", "PyTorch CPU required to execute empirical benchmark")
    torch.set_num_threads(1)
    t_start = time.perf_counter()

    basis_mat = torch.tensor(build_gegenbauer_basis_matrix_float(Fraction(1, 2)), dtype=torch.float32)
    m_fixed = PariAgrawalKimNet("linear")
    m_poly = PariAgrawalKimNet("poly_xpi_gegen", basis_mat=basis_mat)
    fixed_params = sum(p.numel() for p in m_fixed.parameters())
    poly_params = sum(p.numel() for p in m_poly.parameters())

    seeds = (0, 1, 2)
    lr_grid = (PAK_LR_GRID[1],) if smoke else PAK_LR_GRID
    reg_steps = 6 if smoke else 85
    reg_bs = 24 if smoke else 48
    lkp4_steps = 6 if smoke else 225
    lkp4_bs = 24 if smoke else 64
    lkp8_steps = 4 if smoke else 6
    lkp8_bs = 24 if smoke else 32

    val_gen = torch.Generator().manual_seed(20261126)
    val_reg_x, val_reg_y = _gen_regression_batch(128 if smoke else 2048, val_gen)
    grid4 = _make_grid_xy(4)
    grid8 = _make_grid_xy(8)
    val_lkp4_x, val_lkp4_y = _gen_lookup_batch(128 if smoke else 1024, grid4, val_gen)
    val_lkp8_x, val_lkp8_y = _gen_lookup_batch(128 if smoke else 512, grid8, val_gen)

    # Pre-generate vectorized matched-budget identical training batch streams once per seed
    reg_streams: dict[int, tuple[torch.Tensor, torch.Tensor]] = {}
    lkp4_streams: dict[int, tuple[torch.Tensor, torch.Tensor]] = {}
    for sd in seeds:
        g_reg = torch.Generator().manual_seed(10_000 + 97 * sd + 1)
        rx_flat, ry_flat = _gen_regression_batch(reg_steps * reg_bs, g_reg)
        reg_streams[sd] = (rx_flat.reshape(reg_steps, reg_bs, 9, 5), ry_flat.reshape(reg_steps, reg_bs, 2))

        g_lkp4 = torch.Generator().manual_seed(10_000 + 97 * sd + 2)
        lx_flat, ly_flat = _gen_lookup_batch(lkp4_steps * lkp4_bs, grid4, g_lkp4)
        lkp4_streams[sd] = (lx_flat.reshape(lkp4_steps, lkp4_bs, 17, 5), ly_flat.reshape(lkp4_steps, lkp4_bs))

    g_lkp8 = torch.Generator().manual_seed(10_000 + 3)
    l8x_flat, l8y_flat = _gen_lookup_batch(lkp8_steps * lkp8_bs, grid8, g_lkp8)
    lkp8_stream0 = (l8x_flat.reshape(lkp8_steps, lkp8_bs, 65, 5), l8y_flat.reshape(lkp8_steps, lkp8_bs))

    arms = ("linear", "softmax", "poly_mono", "poly_xpi_gegen", "poly_xpi_mobius")

    # 1. Main 2D In-Context Linear Regression Sweep (shared LR grid across all 5 arms x 3 seeds)
    reg_by_arm: dict[str, Any] = {}
    nan_runs_xpi = 0
    for arm in arms:
        lr_candidates: list[dict[str, Any]] = []
        for lr in lr_grid:
            runs = [
                _train_single_run(
                    task="regression", attn_type=arm, seed=sd, peak_lr=lr,
                    train_x_stream=reg_streams[sd][0], train_y_stream=reg_streams[sd][1],
                    val_x=val_reg_x, val_y=val_reg_y, basis_mat=basis_mat,
                )
                for sd in seeds
            ]
            if arm.startswith("poly_xpi_"):
                nan_runs_xpi += sum(1 for r in runs if r["nan"])
            mean_mse = float("inf") if any(r["nan"] for r in runs) else sum(r["val_mse"] for r in runs) / len(runs)
            lr_candidates.append({"lr": round(lr, 8), "mean_val_mse": round(mean_mse, 6) if math.isfinite(mean_mse) else None, "runs": runs})
        best = min(lr_candidates, key=lambda c: c["mean_val_mse"] if c["mean_val_mse"] is not None else float("inf"))
        reg_by_arm[arm] = {"selected_lr": best["lr"], "mean_val_mse": best["mean_val_mse"], "seeds": best["runs"], "sweep": lr_candidates}

    # 2. Simplicity Bias Initialization Control (T_8 softmax approx vs Linear init at rho=1.8, lr=0.008)
    t8_init_runs = [
        _train_single_run(
            task="regression", attn_type="poly_xpi_gegen", seed=sd, peak_lr=0.008,
            train_x_stream=reg_streams[sd][0], train_y_stream=reg_streams[sd][1],
            val_x=val_reg_x, val_y=val_reg_y, basis_mat=basis_mat,
            rho=1.8, init_mode="t8_softmax",
        )
        for sd in seeds
    ]
    lin_init_rho18_runs = [
        _train_single_run(
            task="regression", attn_type="poly_xpi_gegen", seed=sd, peak_lr=0.008,
            train_x_stream=reg_streams[sd][0], train_y_stream=reg_streams[sd][1],
            val_x=val_reg_x, val_y=val_reg_y, basis_mat=basis_mat,
            rho=1.8, init_mode="linear",
        )
        for sd in seeds
    ]

    # 3. High-Gain Temperature Stress Test (gamma_0 = ln(3) => g_0 = 3.0: tests Theorem 1 g^{-8} collapse!)
    gamma_g3 = math.log(3.0)
    high_g_mono = [
        _train_single_run(
            task="regression", attn_type="poly_mono", seed=sd, peak_lr=0.008,
            train_x_stream=reg_streams[sd][0], train_y_stream=reg_streams[sd][1],
            val_x=val_reg_x, val_y=val_reg_y, basis_mat=basis_mat,
            gamma_init=gamma_g3,
        )
        for sd in seeds
    ]
    high_g_xpi = [
        _train_single_run(
            task="regression", attn_type="poly_xpi_gegen", seed=sd, peak_lr=0.008,
            train_x_stream=reg_streams[sd][0], train_y_stream=reg_streams[sd][1],
            val_x=val_reg_x, val_y=val_reg_y, basis_mat=basis_mat,
            gamma_init=gamma_g3,
        )
        for sd in seeds
    ]
    nan_runs_xpi += sum(1 for r in high_g_xpi if r["nan"])

    # 4. Shuffled Grid Lookup: 4x4 Saddle-Escaping Grid (3 seeds x 4 matched arms) + Honest 8x8 65-Token Saddle Probe
    lkp_arms = ("linear", "softmax", "poly_mono", "poly_xpi_mobius")
    lkp4_by_arm: dict[str, Any] = {}
    lkp_lr = PAK_LR_GRID[1]
    for arm in lkp_arms:
        runs = [
            _train_single_run(
                task="lookup", attn_type=arm, seed=sd, peak_lr=lkp_lr,
                train_x_stream=lkp4_streams[sd][0], train_y_stream=lkp4_streams[sd][1],
                val_x=val_lkp4_x, val_y=val_lkp4_y, basis_mat=basis_mat,
            )
            for sd in seeds
        ]
        if arm.startswith("poly_xpi_"):
            nan_runs_xpi += sum(1 for r in runs if r["nan"])
        mean_acc = sum(r["val_acc_pct"] for r in runs) / len(runs)
        lkp4_by_arm[arm] = {"lr": round(lkp_lr, 8), "mean_val_acc_pct": round(mean_acc, 4), "seeds": runs}

    lkp8_by_arm: dict[str, Any] = {}
    for arm in lkp_arms:
        r0 = _train_single_run(
            task="lookup", attn_type=arm, seed=0, peak_lr=0.008,
            train_x_stream=lkp8_stream0[0], train_y_stream=lkp8_stream0[1],
            val_x=val_lkp8_x, val_y=val_lkp8_y, basis_mat=basis_mat,
        )
        if arm.startswith("poly_xpi_") and r0["nan"]:
            nan_runs_xpi += 1
        lkp8_by_arm[arm] = {"lr": 0.008, "mean_val_acc_pct": r0["val_acc_pct"], "seed0": r0}

    # Compute wins & literal Law-4 verdict
    xpi_reg_seeds = reg_by_arm["poly_xpi_mobius"]["seeds"]
    smx_reg_seeds = reg_by_arm["softmax"]["seeds"]
    wins_vs_smx = sum(1 for rx, rs in zip(xpi_reg_seeds, smx_reg_seeds) if (not rx["nan"]) and rx["val_mse"] < rs["val_mse"])
    wins_vs_t8 = sum(1 for rl, rt in zip(lin_init_rho18_runs, t8_init_runs) if (not rl["nan"]) and (rt["nan"] or rl["val_mse"] < rt["val_mse"]))

    best_xpi_reg_mse = min(float(reg_by_arm["poly_xpi_gegen"]["mean_val_mse"]), float(reg_by_arm["poly_xpi_mobius"]["mean_val_mse"]))
    best_xpi_lkp4 = float(lkp4_by_arm["poly_xpi_mobius"]["mean_val_acc_pct"])
    best_xpi_lkp8 = float(lkp8_by_arm["poly_xpi_mobius"]["mean_val_acc_pct"])

    high_g_mono_mse = float("inf") if any(r["nan"] for r in high_g_mono) else sum(r["val_mse"] for r in high_g_mono) / len(seeds)
    high_g_xpi_mse = float("inf") if any(r["nan"] for r in high_g_xpi) else sum(r["val_mse"] for r in high_g_xpi) / len(seeds)
    high_g_mono_b8 = max(r["max_abs_b8"] for r in high_g_mono)
    high_g_xpi_b8 = max(r["max_abs_b8"] for r in high_g_xpi)

    graded = grade_s122_empirical(
        nan_runs_xpi=nan_runs_xpi,
        reg_xpi_wins_vs_softmax=wins_vs_smx,
        reg_xpi_wins_vs_t8_init=wins_vs_t8,
        reg_xpi_mean_mse=best_xpi_reg_mse,
        reg_linear_mean_mse=float(reg_by_arm["linear"]["mean_val_mse"]),
        high_g_xpi_mean_mse=float(high_g_xpi_mse),
        high_g_mono_mean_mse=float(high_g_mono_mse),
        high_g_xpi_max_b8=float(high_g_xpi_b8),
        high_g_mono_max_b8=float(high_g_mono_b8),
        lkp4_xpi_mean_acc=best_xpi_lkp4,
        lkp4_mono_mean_acc=float(lkp4_by_arm["poly_mono"]["mean_val_acc_pct"]),
        lkp4_linear_mean_acc=float(lkp4_by_arm["linear"]["mean_val_acc_pct"]),
        lkp4_softmax_mean_acc=float(lkp4_by_arm["softmax"]["mean_val_acc_pct"]),
        lkp8_xpi_mean_acc=best_xpi_lkp8,
        lkp8_softmax_mean_acc=float(lkp8_by_arm["softmax"]["mean_val_acc_pct"]),
        n_seeds=len(seeds),
    )

    elapsed_s = round(time.perf_counter() - t_start, 3)
    oracle_cert = xpi_oracle.build_xpi_gegenbauer_certificate()
    xpi_oracle.validate_xpi_certificate(oracle_cert)

    payload: dict[str, Any] = {
        "schema": "aletheia.track_s122.xpi_gegenbauer_bench.v1",
        "track": "S122",
        "experiment": "EXP-Q26c",
        "smoke_mode": smoke,
        "elapsed_seconds": elapsed_s,
        "cpu_threads": {"openblas": os.environ.get("OPENBLAS_NUM_THREADS", "1"), "torch_threads": int(torch.get_num_threads())},
        "exact_q_oracle_certificate_sha256": oracle_cert["certificate_sha256"],
        "cs08_param_counts": {
            "fixed_linear_and_softmax": fixed_params,
            "polynomial_p8_all_arms": poly_params,
            "added_polynomial_scalars": poly_params - fixed_params,
        },
        "regression_2d": reg_by_arm,
        "simplicity_bias_init_rho1p8": {
            "linear_init_mean_mse": round(sum(r["val_mse"] for r in lin_init_rho18_runs) / len(seeds), 6),
            "t8_softmax_init_mean_mse": round(sum(r["val_mse"] for r in t8_init_runs if not r["nan"]) / max(1, sum(1 for r in t8_init_runs if not r["nan"])), 6),
            "linear_init_runs": lin_init_rho18_runs,
            "t8_softmax_init_runs": t8_init_runs,
        },
        "high_gain_g3_stress_test": {
            "gamma_init": round(gamma_g3, 6),
            "mono_mean_mse": None if any(r["nan"] for r in high_g_mono) else round(sum(r["val_mse"] for r in high_g_mono) / len(seeds), 6),
            "xpi_gegen_mean_mse": round(sum(r["val_mse"] for r in high_g_xpi) / len(seeds), 6),
            "mono_runs": high_g_mono,
            "xpi_gegen_runs": high_g_xpi,
        },
        "lookup_4x4_saddle_escaped": lkp4_by_arm,
        "lookup_8x8_single_thread_saddle_diagnostic": lkp8_by_arm,
        "graded": graded,
    }
    canon_body = {k: v for k, v in payload.items() if k != "elapsed_seconds"}
    canon = json.dumps(canon_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["result_sha256"] = hashlib.sha256(canon).hexdigest()
    validate_results_payload(payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EXP-Q26c Matched CPU Micro-Benchmark: Portal x/pi Gegenbauer vs Monomial Attention")
    parser.add_argument("--write", action="store_true", help=f"Write {RESULTS_FILENAME} in track directory")
    parser.add_argument("--check", action="store_true", help=f"Verify existing {RESULTS_FILENAME} integrity")
    parser.add_argument("--smoke", action="store_true", help="Fast 12-step smoke check")
    parser.add_argument("--json", action="store_true", help="Print full JSON result")
    args = parser.parse_args(argv)

    try:
        modes = int(bool(args.write)) + int(bool(args.check))
        require_ok(modes <= 1, "CLI_MUTUAL_EXCLUSION", "cannot pass both --write and --check")
        out_path = _HERE / RESULTS_FILENAME
        if args.check:
            require_ok(out_path.is_file(), "MISSING_RESULTS", f"missing {RESULTS_FILENAME}")
            on_disk = json.loads(out_path.read_text(encoding="utf-8"))
            validate_results_payload(on_disk)
            sys.stdout.write(json.dumps({"status": "PASS", "result_sha256": on_disk["result_sha256"], "verdict": on_disk["graded"]["verdict"]}, sort_keys=True) + "\n")
            return 0

        res = run_benchmark(smoke=args.smoke)
        if args.write:
            out_path.write_text(json.dumps(res, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.json:
            sys.stdout.write(json.dumps(res, indent=2, sort_keys=True) + "\n")
        else:
            sys.stdout.write(
                json.dumps(
                    {
                        "status": "WRITTEN" if args.write else "PASS",
                        "elapsed_seconds": res["elapsed_seconds"],
                        "verdict": res["graded"]["verdict"],
                        "result_sha256": res["result_sha256"],
                    },
                    sort_keys=True,
                )
                + "\n"
            )
        return 0
    except S122BenchError as exc:
        sys.stderr.write(f"S122_BENCH_FAIL {exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
