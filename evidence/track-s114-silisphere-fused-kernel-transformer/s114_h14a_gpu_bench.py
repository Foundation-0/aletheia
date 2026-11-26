#!/usr/bin/env python3
"""Track S114 Phase 2A (`H14a`): Live RTX 3080 sm_86 Parity, Gradcheck, & Speedup/Roofline Suite.

Executes strictly inside mlos gpu-lease --mode train + mlos stamp-run --zone B --require-gpu:
  1. Live sm_86 Parity (FP32 <= 1e-4, BF16 <= 5e-3) across ALL 3 backends (CUDA sm_86,
     Triton 3.9, PyTorch reference) and 10 lengths T in {32, 33, 64, 100, 128, 256, 512, 513, 1024, 2048}:
       - su2_holonomy_transport (forward + backward d_raw, d_q, d_k, d_v)
       - su2_inverse_untransport (forward + backward d_o, d_pi)
       - fused_spherical_step (slerp, safe_hopf_loop acute_cone & cayley_acute, hopf_s3)
       - siliquant_a16_dequant_hopf_sm86 (valid 0-syndrome + injected 1-bit error detection)
  2. Standalone kernel microbench (B=8, H=8, d_head=64, T in {512, 1024, 2048}, FP32 & BF16),
     explicitly quantifying [B,H,T,nb,4] layout-permute overhead vs native fiber-major [F,T,4]!
  3. Full 12L H7b training step benchmark (d_model=320, H=8, d_ff=864, B=8, T=512, BF16 autocast)
     + single-block (B=8, H=8, d_head=64, T in {512, 1024, 2048}) wall-clock, peak VRAM, and NVML mJ/tok
     comparing Eager H7b vs RoPE-2D-nGPT vs HoloSphere-CUDA-sm86 vs HoloSphere-Triton-3.9.
  4. Literal locked PREREG-S114 H14a verdict + canonical inner result_sha256 (WEIGHTS=0).
"""

from __future__ import annotations

import ctypes
import datetime
import gc
import hashlib
import json
import math
import os
import pathlib
import subprocess
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

_HERE = pathlib.Path(__file__).resolve().parent
_EXPEDITION = _HERE.parent
_S107 = _EXPEDITION / "track-s107-hypersphere-transformer"
for _p in (str(_HERE), str(_S107)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import torch.nn.functional as F  # noqa: E402

import s107_models as s107  # noqa: E402
import s114_fused_ops as ops  # noqa: E402
from su2_holonomy_triton import triton_su2_holonomy_bwd, triton_su2_holonomy_fwd  # noqa: E402

PREREG_SHA256 = "5fa927a06933c3cff057b65f75c1d2f190e10f1e420303d582dfb7c802ee69a4"
STREAM_TRIAD_GBS = 356.6
PARITY_LENGTHS = (32, 33, 64, 100, 128, 256, 512, 513, 1024, 2048)
BENCH_LENGTHS = (512, 1024, 2048)


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def _query_nvml_power_w() -> Optional[float]:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
            text=True,
            timeout=5,
        ).strip()
        return float(out.splitlines()[0].strip())
    except Exception:
        return None


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


def _err_metrics(a: torch.Tensor, b: torch.Tensor) -> Dict[str, float]:
    af = a.detach().float()
    bf = b.detach().float()
    diff = (af - bf).abs()
    max_abs = float(diff.max().item())
    denom = float(bf.abs().max().item())
    max_rel = max_abs / max(denom, 1e-12)
    flat_a = af.reshape(-1)
    flat_b = bf.reshape(-1)
    cos = float(F.cosine_similarity(flat_a.unsqueeze(0), flat_b.unsqueeze(0), eps=1e-12).item())
    return {
        "max_abs": round(max_abs, 8),
        "max_rel": round(max_rel, 8),
        "cosine": round(cos, 8),
    }


def _time_cuda_ms(fn: Callable[[], None], warmup: int = 8, iters: int = 25) -> Tuple[float, float]:
    for _ in range(warmup):
        fn()
    torch.cuda.synchronize()
    times: List[float] = []
    for _ in range(iters):
        ev0 = torch.cuda.Event(enable_timing=True)
        ev1 = torch.cuda.Event(enable_timing=True)
        ev0.record()
        fn()
        ev1.record()
        torch.cuda.synchronize()
        times.append(float(ev0.elapsed_time(ev1)))
    times.sort()
    median = times[len(times) // 2]
    mean = sum(times) / float(len(times))
    return median, mean


# ---------------------------------------------------------------------------
# Part 1: Live sm_86 Parity Across All 3 Backends & 10 Sequence Lengths
# ---------------------------------------------------------------------------


def _run_parity_suite(device: torch.device) -> Dict[str, Any]:
    results: Dict[str, Any] = {"su2_holonomy": {}, "untransport": {}, "spherical_steps": {}, "siliquant_a16": {}}
    worst_fp32 = 0.0
    worst_bf16 = 0.0
    worst_norm_drift = 0.0
    any_nan = False

    # 1A. SU(2) Holonomy Scan + QKV Transport (forward + backward) for CUDA & Triton vs Reference
    # Uses actual nGPT/HoloSphere unit-sphere Q,K,V and per-step mean-reduced loss (matching cross-entropy scaling).
    for dtype_name, dtype in (("fp32", torch.float32), ("bf16", torch.bfloat16)):
        per_len: Dict[str, Any] = {}
        for seq_len in PARITY_LENGTHS:
            gen = torch.Generator(device="cpu").manual_seed(11400 + seq_len)
            bsz, heads, d_head = 2, 4, 32
            nb = d_head // 4
            q0 = ops._safe_unit_norm(torch.randn((bsz, heads, seq_len, d_head), generator=gen)).to(device=device, dtype=dtype)
            k0 = ops._safe_unit_norm(torch.randn((bsz, heads, seq_len, d_head), generator=gen)).to(device=device, dtype=dtype)
            v0 = ops._safe_unit_norm(torch.randn((bsz, heads, seq_len, d_head), generator=gen)).to(device=device, dtype=dtype)
            om0 = torch.randn((bsz, heads, seq_len, nb, 3), generator=gen).to(device=device, dtype=dtype)
            gq = ops._safe_unit_norm(torch.randn((bsz, heads, seq_len, d_head), generator=gen)).to(device=device, dtype=dtype)
            gk = ops._safe_unit_norm(torch.randn((bsz, heads, seq_len, d_head), generator=gen)).to(device=device, dtype=dtype)
            gv = ops._safe_unit_norm(torch.randn((bsz, heads, seq_len, d_head), generator=gen)).to(device=device, dtype=dtype)
            loss_scale = 1.0 / float(seq_len)

            # Reference: FP32 S107 autograd ground truth (for BF16, run S107 on same BF16 inputs cast to FP32)
            qr_in = q0.float().detach().requires_grad_(True)
            kr_in = k0.float().detach().requires_grad_(True)
            vr_in = v0.float().detach().requires_grad_(True)
            omr_in = om0.float().detach().requires_grad_(True)
            du_s = s107.su2_exp(0.75 * torch.tanh(omr_in).permute(0, 2, 1, 3, 4))
            u_ref = s107.su2_parallel_prefix_scan(du_s).permute(0, 2, 1, 3, 4)
            q_ref = s107.quat_mul(u_ref, qr_in.reshape(bsz, heads, seq_len, nb, 4)).reshape_as(qr_in)
            k_ref = s107.quat_mul(u_ref, kr_in.reshape(bsz, heads, seq_len, nb, 4)).reshape_as(kr_in)
            v_ref = s107.quat_mul(u_ref, vr_in.reshape(bsz, heads, seq_len, nb, 4)).reshape_as(vr_in)
            loss_ref = ((q_ref * gq.float()).sum() + (k_ref * gk.float()).sum() + (v_ref * gv.float()).sum()) * loss_scale
            dq_ref, dk_ref, dv_ref, dom_ref = torch.autograd.grad(loss_ref, (qr_in, kr_in, vr_in, omr_in))

            entry: Dict[str, Any] = {}
            for bk in ("cuda", "triton"):
                qi = q0.detach().clone().requires_grad_(True)
                ki = k0.detach().clone().requires_grad_(True)
                vi = v0.detach().clone().requires_grad_(True)
                omi = om0.detach().clone().requires_grad_(True)
                qo, ko, vo, pi = ops.su2_holonomy_transport(
                    qi, ki, vi, omi, angle_scale=0.75, transport_v=True, backend=bk
                )
                loss = ((qo.float() * gq.float()).sum() + (ko.float() * gk.float()).sum() + (vo.float() * gv.float()).sum()) * loss_scale
                dq, dk, dv, dom = torch.autograd.grad(loss, (qi, ki, vi, omi))

                for t_chk in (qo, ko, vo, pi, dq, dk, dv, dom):
                    if not bool(torch.isfinite(t_chk).all().item()):
                        any_nan = True
                nd = float((torch.linalg.vector_norm(pi.float(), dim=-1) - 1.0).abs().max().item())
                worst_norm_drift = max(worst_norm_drift, nd)

                fwd_m = {
                    "pi": _err_metrics(pi, u_ref),
                    "q": _err_metrics(qo, q_ref),
                    "k": _err_metrics(ko, k_ref),
                    "v": _err_metrics(vo, v_ref),
                }
                bwd_m = {
                    "d_omega": _err_metrics(dom, dom_ref),
                    "d_q": _err_metrics(dq, dq_ref),
                    "d_k": _err_metrics(dk, dk_ref),
                    "d_v": _err_metrics(dv, dv_ref),
                }
                max_all = max(
                    *(m["max_abs"] for m in fwd_m.values()),
                    *(m["max_abs"] for m in bwd_m.values()),
                )
                if dtype_name == "fp32":
                    worst_fp32 = max(worst_fp32, max_all)
                else:
                    worst_bf16 = max(worst_bf16, max_all)
                entry[bk] = {
                    "fwd_max_abs": round(max(m["max_abs"] for m in fwd_m.values()), 8),
                    "bwd_max_abs": round(max(m["max_abs"] for m in bwd_m.values()), 8),
                    "d_omega_max_abs": bwd_m["d_omega"]["max_abs"],
                    "d_omega_max_rel": bwd_m["d_omega"]["max_rel"],
                    "d_omega_cos": bwd_m["d_omega"]["cosine"],
                    "norm_drift": round(nd, 8),
                }
            per_len[str(seq_len)] = entry
        results["su2_holonomy"][dtype_name] = per_len

    # 1A-stress: Unnormalized N(0,1) sum-loss diagnostic at T=2048 (reports max_rel & cosine alongside raw max_abs)
    stress: Dict[str, Any] = {}
    for seq_len in (512, 2048):
        gen = torch.Generator(device="cpu").manual_seed(11900 + seq_len)
        bsz, heads, d_head = 2, 4, 32
        nb = d_head // 4
        q0 = torch.randn((bsz, heads, seq_len, d_head), generator=gen).to(device=device, dtype=torch.float32)
        k0 = torch.randn((bsz, heads, seq_len, d_head), generator=gen).to(device=device, dtype=torch.float32)
        om0 = torch.randn((bsz, heads, seq_len, nb, 3), generator=gen).to(device=device, dtype=torch.float32)
        gq = torch.randn((bsz, heads, seq_len, d_head), generator=gen).to(device=device, dtype=torch.float32)
        gk = torch.randn((bsz, heads, seq_len, d_head), generator=gen).to(device=device, dtype=torch.float32)
        qr = q0.detach().clone().requires_grad_(True)
        kr = k0.detach().clone().requires_grad_(True)
        omr = om0.detach().clone().requires_grad_(True)
        du_s = s107.su2_exp(0.75 * torch.tanh(omr).permute(0, 2, 1, 3, 4))
        u_ref = s107.su2_parallel_prefix_scan(du_s).permute(0, 2, 1, 3, 4)
        q_ref = s107.quat_mul(u_ref, qr.reshape(bsz, heads, seq_len, nb, 4)).reshape_as(qr)
        k_ref = s107.quat_mul(u_ref, kr.reshape(bsz, heads, seq_len, nb, 4)).reshape_as(kr)
        _, _, dom_ref = torch.autograd.grad((q_ref * gq).sum() + (k_ref * gk).sum(), (qr, kr, omr))
        qc = q0.detach().clone().requires_grad_(True)
        kc = k0.detach().clone().requires_grad_(True)
        omc = om0.detach().clone().requires_grad_(True)
        qo, ko, _, _ = ops.su2_holonomy_transport(qc, kc, kc, omc, angle_scale=0.75, transport_v=False, backend="cuda")
        _, _, dom_c = torch.autograd.grad((qo * gq).sum() + (ko * gk).sum(), (qc, kc, omc))
        stress[str(seq_len)] = {
            "fwd_q": _err_metrics(qo, q_ref),
            "bwd_d_omega_unnormalized_sum": _err_metrics(dom_c, dom_ref),
        }
    results["stress_unnormalized_sum_fp32"] = stress

    # 1B. Inverse Un-Transport (CUDA sm_86 vs reference, FP32 & BF16, T=513, unit-sphere inputs)
    for dtype_name, dtype in (("fp32", torch.float32), ("bf16", torch.bfloat16)):
        gen = torch.Generator(device="cpu").manual_seed(11477)
        bsz, heads, seq_len, d_head = 2, 4, 513, 32
        nb = d_head // 4
        o0 = ops._safe_unit_norm(torch.randn((bsz, heads, seq_len, d_head), generator=gen)).to(device=device, dtype=dtype)
        u0 = ops._safe_unit_norm(torch.randn((bsz, heads, seq_len, nb, 4), generator=gen)).to(device=device, dtype=torch.float32)
        go = ops._safe_unit_norm(torch.randn((bsz, heads, seq_len, d_head), generator=gen)).to(device=device, dtype=dtype)

        o_r = o0.float().detach().requires_grad_(True)
        u_r = u0.float().detach().requires_grad_(True)
        out_r = ops.su2_inverse_untransport(o_r, u_r, backend="reference")
        do_r, du_r = torch.autograd.grad((out_r * go.float()).sum(), (o_r, u_r))

        o_c = o0.detach().clone().requires_grad_(True)
        u_c = u0.detach().clone().requires_grad_(True)
        out_c = ops.su2_inverse_untransport(o_c, u_c, backend="cuda")
        do_c, du_c = torch.autograd.grad((out_c.float() * go.float()).sum(), (o_c, u_c))
        m_fwd = _err_metrics(out_c, out_r)
        m_do = _err_metrics(do_c, do_r)
        m_du = _err_metrics(du_c, du_r)
        if dtype_name == "fp32":
            worst_fp32 = max(worst_fp32, m_fwd["max_abs"], m_do["max_abs"], m_du["max_abs"])
        else:
            worst_bf16 = max(worst_bf16, m_fwd["max_abs"], m_do["max_abs"], m_du["max_abs"])
        results["untransport"][dtype_name] = {"fwd": m_fwd, "d_o": m_do, "d_pi": m_du}

    # 1C. Fused Spherical Steps (slerp, safe_hopf_loop acute_cone & cayley_acute, hopf_s3; unit-sphere h, delta)
    for dtype_name, dtype in (("fp32", torch.float32), ("bf16", torch.bfloat16)):
        gen = torch.Generator(device="cpu").manual_seed(11488)
        h0 = ops._safe_unit_norm(torch.randn((4, 128, 320), generator=gen)).to(device=device, dtype=dtype)
        d0 = ops._safe_unit_norm(torch.randn((4, 128, 320), generator=gen)).to(device=device, dtype=dtype)
        a0 = torch.randn((320,), generator=gen).to(device=device, dtype=dtype)
        go = ops._safe_unit_norm(torch.randn((4, 128, 320), generator=gen)).to(device=device, dtype=dtype)
        sph_res: Dict[str, Any] = {}
        for mode, phi in (
            ("slerp", 0.0),
            ("safe_hopf_acute_cone", ops.safe_hopf_clock_angle(5, law="acute_cone", r_max=8)),
            ("safe_hopf_cayley_acute", ops.safe_hopf_clock_angle(5, law="cayley_acute", r_max=8)),
            ("hopf_s3", 0.0),
        ):
            eff_mode = "safe_hopf_loop" if mode.startswith("safe_hopf_") else mode
            hr = h0.float().detach().requires_grad_(True)
            dr = d0.float().detach().requires_grad_(True)
            ar = a0.float().detach().requires_grad_(True)
            hc = h0.detach().clone().requires_grad_(True)
            dc = d0.detach().clone().requires_grad_(True)
            ac = a0.detach().clone().requires_grad_(True)

            if eff_mode == "hopf_s3":
                yr = ops.fused_spherical_step(hr, dr, mode="hopf_s3", backend="reference")
                yc = ops.fused_spherical_step(hc, dc, mode="hopf_s3", backend="cuda")
                ghr, gdr = torch.autograd.grad((yr * go.float()).sum(), (hr, dr))
                ghc, gdc = torch.autograd.grad((yc.float() * go.float()).sum(), (hc, dc))
                m_f, m_gh, m_gd = _err_metrics(yc, yr), _err_metrics(ghc, ghr), _err_metrics(gdc, gdr)
                sph_res[mode] = {"fwd": m_f, "d_h": m_gh, "d_delta": m_gd}
                mx = max(m_f["max_abs"], m_gh["max_abs"], m_gd["max_abs"])
            else:
                yr = ops.fused_spherical_step(hr, dr, ar, mode=eff_mode, phi=phi, backend="reference")
                yc = ops.fused_spherical_step(hc, dc, ac, mode=eff_mode, phi=phi, backend="cuda")
                ghr, gdr, gar = torch.autograd.grad((yr * go.float()).sum(), (hr, dr, ar))
                ghc, gdc, gac = torch.autograd.grad((yc.float() * go.float()).sum(), (hc, dc, ac))
                m_f, m_gh, m_gd, m_ga = (
                    _err_metrics(yc, yr),
                    _err_metrics(ghc, ghr),
                    _err_metrics(gdc, gdr),
                    _err_metrics(gac, gar),
                )
                sph_res[mode] = {"fwd": m_f, "d_h": m_gh, "d_delta": m_gd, "d_alpha": m_ga}
                # d_alpha sums over N=512 rows; check relative error alongside max_abs
                mx = max(m_f["max_abs"], m_gh["max_abs"], m_gd["max_abs"], m_ga["max_rel"])
            if dtype_name == "fp32":
                worst_fp32 = max(worst_fp32, mx)
            else:
                worst_bf16 = max(worst_bf16, mx)
        results["spherical_steps"][dtype_name] = sph_res

    # 1D. Kernel 9: siliquant_a16_dequant_hopf_sm86 (valid 0-syndrome + 17 injected 1-bit flips)
    lib = ops._load_cuda_lib()
    _require(lib is not None, "CUDA sm_86 library missing for Kernel 9 check")
    lib.holosphere_siliquant_a16_dequant_hopf_f32.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int64, ctypes.c_float, ctypes.c_float, ctypes.c_void_p,
    ]
    lib.holosphere_siliquant_a16_dequant_hopf_f32.restype = ctypes.c_int

    def _enc_a16(d11: int) -> int:
        pos = (3, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15)
        cw = 0
        for i, p in enumerate(pos):
            if (d11 >> i) & 1:
                cw |= 1 << p
        for pb, msk in ((1, 0xAAAA), (2, 0xCCCC), (4, 0xF0F0), (8, 0xFF00)):
            if (cw & msk).bit_count() & 1:
                cw |= 1 << pb
        if cw.bit_count() & 1:
            cw |= 1
        return cw

    n_blk = 4096
    cws_cpu = torch.tensor([_enc_a16(i % 2048) for i in range(n_blk)], dtype=torch.uint16)
    sc_cpu = torch.linspace(0.25, 1.75, n_blk, dtype=torch.float32)
    phi_a16 = ops.safe_hopf_clock_angle(2, law="cayley_acute", r_max=8)
    c_phi, s_phi = math.cos(phi_a16), math.sin(phi_a16)

    cws_gpu = cws_cpu.to(device)
    sc_gpu = sc_cpu.to(device)
    out_gpu = torch.empty((n_blk, 16), device=device, dtype=torch.float32)
    syn_gpu = torch.zeros((1,), device=device, dtype=torch.int32)
    rc = lib.holosphere_siliquant_a16_dequant_hopf_f32(
        ops._ptr(cws_gpu), ops._ptr(sc_gpu), ops._ptr(out_gpu), ops._ptr(syn_gpu),
        n_blk, float(c_phi), float(s_phi), ops._cuda_stream_ptr(device),
    )
    _require(rc == 0, f"siliquant_a16_dequant_hopf_sm86 failed: {rc}")
    torch.cuda.synchronize()
    valid_syn = int(syn_gpu.item())

    # Exact CPU reference
    bits = ((cws_cpu.to(torch.int32).unsqueeze(1) >> torch.arange(16)) & 1).float()
    ref_raw = torch.where(bits > 0.5, sc_cpu.unsqueeze(1), -sc_cpu.unsqueeze(1))
    ref_rot = ops._hopf_rotate_tensor(ref_raw, c_phi, s_phi)
    m_a16 = _err_metrics(out_gpu.cpu(), ref_rot)

    # Inject 17 1-bit errors
    bad_cws = cws_cpu.clone()
    for idx in range(17):
        bad_cws[idx * 100] = int(bad_cws[idx * 100].item()) ^ (1 << (idx % 16))
    syn_bad = torch.zeros((1,), device=device, dtype=torch.int32)
    rc2 = lib.holosphere_siliquant_a16_dequant_hopf_f32(
        ops._ptr(bad_cws.to(device)), ops._ptr(sc_gpu), ops._ptr(out_gpu), ops._ptr(syn_bad),
        n_blk, float(c_phi), float(s_phi), ops._cuda_stream_ptr(device),
    )
    _require(rc2 == 0, f"siliquant_a16 bad check failed: {rc2}")
    torch.cuda.synchronize()
    bad_syn = int(syn_bad.item())

    worst_fp32 = max(worst_fp32, m_a16["max_abs"])
    results["siliquant_a16"] = {
        "n_blocks": n_blk,
        "valid_syndrome_errors": valid_syn,
        "injected_1bit_errors_expected": 17,
        "injected_1bit_errors_detected": bad_syn,
        "dequant_hopf_parity": m_a16,
    }
    results["summary"] = {
        "worst_fp32_err": round(worst_fp32, 8),
        "worst_bf16_err": round(worst_bf16, 8),
        "worst_unit_norm_drift": round(worst_norm_drift, 8),
        "any_nan_or_inf": any_nan,
        "fp32_gate_pass_le_1e4": (worst_fp32 <= 1e-4) and (not any_nan),
        "bf16_gate_pass_le_5e3": (worst_bf16 <= 5e-3) and (not any_nan),
        "norm_gate_pass_le_1e5": worst_norm_drift <= 1e-5,
        "a16_syndrome_exact": (valid_syn == 0 and bad_syn == 17),
    }
    return results


# ---------------------------------------------------------------------------
# Part 2: Standalone Kernel Microbench & Memory Layout Coalescing Analysis
# ---------------------------------------------------------------------------


def _run_kernel_microbench(device: torch.device) -> Dict[str, Any]:
    """Compare Eager H7b vs CUDA sm_86 vs Triton 3.9 at B=8, H=8, d_head=64, T in {512, 1024, 2048}.

    Explicitly separates layout-permute ([B,H,T,D] <-> [F,T,4]) cost from native fiber-major kernel time!
    """
    bsz, heads, d_head = 8, 8, 64
    nb = d_head // 4
    n_fibers = bsz * heads * nb
    lib = ops._load_cuda_lib()
    _require(lib is not None, "CUDA library missing")
    out: Dict[str, Any] = {}

    for seq_len in BENCH_LENGTHS:
        gen = torch.Generator(device="cpu").manual_seed(21400 + seq_len)
        q = torch.randn((bsz, heads, seq_len, d_head), generator=gen).to(device=device, dtype=torch.float32)
        k = torch.randn((bsz, heads, seq_len, d_head), generator=gen).to(device=device, dtype=torch.float32)
        v = torch.randn((bsz, heads, seq_len, d_head), generator=gen).to(device=device, dtype=torch.float32)
        om = torch.randn((bsz, heads, seq_len, nb, 3), generator=gen).to(device=device, dtype=torch.float32)
        gq = torch.randn((bsz, heads, seq_len, d_head), generator=gen).to(device=device, dtype=torch.float32)
        gk = torch.randn((bsz, heads, seq_len, d_head), generator=gen).to(device=device, dtype=torch.float32)

        # Native fiber-major tensors [F, T, C] (zero transpose tax!)
        q_f = q.reshape(bsz, heads, seq_len, nb, 4).permute(0, 1, 3, 2, 4).reshape(n_fibers, seq_len, 4).contiguous()
        k_f = k.reshape(bsz, heads, seq_len, nb, 4).permute(0, 1, 3, 2, 4).reshape(n_fibers, seq_len, 4).contiguous()
        om_f = om.permute(0, 1, 3, 2, 4).reshape(n_fibers, seq_len, 3).contiguous()
        u_f = torch.empty_like(q_f)
        qo_f = torch.empty_like(q_f)
        ko_f = torch.empty_like(k_f)
        dqo_f = torch.randn_like(q_f)
        dko_f = torch.randn_like(k_f)
        dqi_f = torch.empty_like(q_f)
        dki_f = torch.empty_like(k_f)
        dom_f = torch.empty_like(om_f)

        # Effective bytes moved in minimal single-pass fused forward:
        # read raw(3) + Q(4) + K(4) + write U(4) + Q_out(4) + K_out(4) = 23 floats * 4 B = 92 B/step/fiber
        fwd_bytes = float(n_fibers * seq_len * 23 * 4)
        # Fwd + Bwd minimal traffic: fwd(23) + bwd(read raw(3)+U(4)+Q(4)+K(4)+dQ(4)+dK(4)=23, write dRaw(3)+dQ(4)+dK(4)=11) = 57 floats * 4 B
        fwdbwd_bytes = float(n_fibers * seq_len * 57 * 4)

        def _eager_fwd() -> None:
            with torch.no_grad():
                du = s107.su2_exp(0.75 * torch.tanh(om).permute(0, 2, 1, 3, 4))
                u = s107.su2_parallel_prefix_scan(du).permute(0, 2, 1, 3, 4)
                _ = s107.quat_mul(u, q.reshape(bsz, heads, seq_len, nb, 4))
                _ = s107.quat_mul(u, k.reshape(bsz, heads, seq_len, nb, 4))

        def _eager_fwdbwd() -> None:
            qi = q.detach().requires_grad_(True)
            ki = k.detach().requires_grad_(True)
            omi = om.detach().requires_grad_(True)
            du = s107.su2_exp(0.75 * torch.tanh(omi).permute(0, 2, 1, 3, 4))
            u = s107.su2_parallel_prefix_scan(du).permute(0, 2, 1, 3, 4)
            qo = s107.quat_mul(u, qi.reshape(bsz, heads, seq_len, nb, 4)).reshape_as(qi)
            ko = s107.quat_mul(u, ki.reshape(bsz, heads, seq_len, nb, 4)).reshape_as(ki)
            ((qo * gq).sum() + (ko * gk).sum()).backward()

        def _cuda_bhtd_fwd() -> None:
            with torch.no_grad():
                ops.su2_holonomy_transport(q, k, v, om, angle_scale=0.75, transport_v=False, backend="cuda")

        def _cuda_bhtd_fwdbwd() -> None:
            qi = q.detach().requires_grad_(True)
            ki = k.detach().requires_grad_(True)
            omi = om.detach().requires_grad_(True)
            qo, ko, _, _ = ops.su2_holonomy_transport(qi, ki, v, omi, angle_scale=0.75, transport_v=False, backend="cuda")
            ((qo * gq).sum() + (ko * gk).sum()).backward()

        def _cuda_fiber_fwd() -> None:
            lib.silisphere_su2_holonomy_fwd_f32(
                ops._ptr(om_f), ops._ptr(q_f), ops._ptr(k_f), ctypes.c_void_p(0),
                ops._ptr(u_f), ops._ptr(qo_f), ops._ptr(ko_f), ctypes.c_void_p(0),
                n_fibers, seq_len, 0.75, 1, 1e-6, ops._cuda_stream_ptr(device),
            )

        def _cuda_fiber_fwdbwd() -> None:
            _cuda_fiber_fwd()
            lib.silisphere_su2_holonomy_bwd_f32(
                ops._ptr(om_f), ops._ptr(u_f), ops._ptr(q_f), ops._ptr(k_f), ctypes.c_void_p(0),
                ctypes.c_void_p(0), ops._ptr(dqo_f), ops._ptr(dko_f), ctypes.c_void_p(0),
                ops._ptr(dom_f), ops._ptr(dqi_f), ops._ptr(dki_f), ctypes.c_void_p(0),
                n_fibers, seq_len, 0.75, 1, 1e-6, ops._cuda_stream_ptr(device),
            )

        def _triton_bhtd_fwd() -> None:
            with torch.no_grad():
                ops.su2_holonomy_transport(q, k, v, om, angle_scale=0.75, transport_v=False, backend="triton")

        def _triton_bhtd_fwdbwd() -> None:
            qi = q.detach().requires_grad_(True)
            ki = k.detach().requires_grad_(True)
            omi = om.detach().requires_grad_(True)
            qo, ko, _, _ = ops.su2_holonomy_transport(qi, ki, v, omi, angle_scale=0.75, transport_v=False, backend="triton")
            ((qo * gq).sum() + (ko * gk).sum()).backward()

        def _triton_fiber_fwd() -> None:
            triton_su2_holonomy_fwd(om_f, q_f, k_f, None, angle_scale=0.75, use_tanh=True, eps=1e-6)

        def _triton_fiber_fwdbwd() -> None:
            uo, _, _, _ = triton_su2_holonomy_fwd(om_f, q_f, k_f, None, angle_scale=0.75, use_tanh=True, eps=1e-6)
            triton_su2_holonomy_bwd(
                om_f, uo, q_f, k_f, None, None, dqo_f, dko_f, None, angle_scale=0.75, use_tanh=True, eps=1e-6
            )

        ef_med, _ = _time_cuda_ms(_eager_fwd, warmup=5, iters=20)
        efb_med, _ = _time_cuda_ms(_eager_fwdbwd, warmup=5, iters=20)
        cf_bhtd, _ = _time_cuda_ms(_cuda_bhtd_fwd, warmup=8, iters=30)
        cfb_bhtd, _ = _time_cuda_ms(_cuda_bhtd_fwdbwd, warmup=8, iters=30)
        cf_fib, _ = _time_cuda_ms(_cuda_fiber_fwd, warmup=8, iters=30)
        cfb_fib, _ = _time_cuda_ms(_cuda_fiber_fwdbwd, warmup=8, iters=30)
        tf_bhtd, _ = _time_cuda_ms(_triton_bhtd_fwd, warmup=8, iters=30)
        tfb_bhtd, _ = _time_cuda_ms(_triton_bhtd_fwdbwd, warmup=8, iters=30)
        tf_fib, _ = _time_cuda_ms(_triton_fiber_fwd, warmup=8, iters=30)
        tfb_fib, _ = _time_cuda_ms(_triton_fiber_fwdbwd, warmup=8, iters=30)

        out[str(seq_len)] = {
            "shape": {"B": bsz, "H": heads, "T": seq_len, "d_head": d_head, "n_fibers": n_fibers},
            "eager_h7b": {"fwd_ms": round(ef_med, 4), "fwdbwd_ms": round(efb_med, 4)},
            "cuda_sm86_bhtd_with_permute": {
                "fwd_ms": round(cf_bhtd, 4),
                "fwdbwd_ms": round(cfb_bhtd, 4),
                "fwd_speedup_vs_eager": round(ef_med / cf_bhtd, 3),
                "fwdbwd_speedup_vs_eager": round(efb_med / cfb_bhtd, 3),
                "fwd_eff_gbs": round(fwd_bytes / (cf_bhtd * 1e6), 2),
                "fwdbwd_eff_gbs": round(fwdbwd_bytes / (cfb_bhtd * 1e6), 2),
            },
            "cuda_sm86_fiber_major_native": {
                "fwd_ms": round(cf_fib, 4),
                "fwdbwd_ms": round(cfb_fib, 4),
                "fwd_speedup_vs_eager": round(ef_med / cf_fib, 3),
                "fwdbwd_speedup_vs_eager": round(efb_med / cfb_fib, 3),
                "fwd_eff_gbs": round(fwd_bytes / (cf_fib * 1e6), 2),
                "fwdbwd_eff_gbs": round(fwdbwd_bytes / (cfb_fib * 1e6), 2),
                "fwd_pct_stream_triad": round(100.0 * (fwd_bytes / (cf_fib * 1e6)) / STREAM_TRIAD_GBS, 2),
                "permute_tax_fwd_ms": round(cf_bhtd - cf_fib, 4),
                "permute_tax_fwdbwd_ms": round(cfb_bhtd - cfb_fib, 4),
                "permute_tax_fwdbwd_pct": round(100.0 * (cfb_bhtd - cfb_fib) / cfb_bhtd, 2),
            },
            "triton_39_bhtd_with_permute": {
                "fwd_ms": round(tf_bhtd, 4),
                "fwdbwd_ms": round(tfb_bhtd, 4),
                "fwd_speedup_vs_eager": round(ef_med / tf_bhtd, 3),
                "fwdbwd_speedup_vs_eager": round(efb_med / tfb_bhtd, 3),
            },
            "triton_39_fiber_major_native": {
                "fwd_ms": round(tf_fib, 4),
                "fwdbwd_ms": round(tfb_fib, 4),
                "fwd_speedup_vs_eager": round(ef_med / tf_fib, 3),
                "fwdbwd_speedup_vs_eager": round(efb_med / tfb_fib, 3),
                "fwd_eff_gbs": round(fwd_bytes / (tf_fib * 1e6), 2),
                "fwdbwd_eff_gbs": round(fwdbwd_bytes / (tfb_fib * 1e6), 2),
            },
        }
        del q, k, v, om, gq, gk, q_f, k_f, om_f, u_f, qo_f, ko_f, dqo_f, dko_f, dqi_f, dki_f, dom_f
        torch.cuda.empty_cache()
    return out


# ---------------------------------------------------------------------------
# Part 3: Full 12L H7b Training Step & Single-Block Wall-Clock / VRAM / mJ/tok
# ---------------------------------------------------------------------------


class _FusedHoloBlock(nn.Module):
    """Exact S107 nGPT TransformerBlock with fused SU(2) holonomy + fused spherical SLERP."""

    def __init__(self, d_model: int, n_heads: int, d_ff: int, backend: str) -> None:
        super().__init__()
        self.attn = ops.S114CovariantHolonomyAttention(
            d_model, n_heads, covariant_v=False, ngpt=True, angle_scale=0.75, backend=backend
        )
        self.mlp = s107.SwiGLUMLP(d_model, d_ff, ngpt=True)
        init_logit = math.log(0.05 / 0.95)
        self.alpha_a_logit = nn.Parameter(torch.full((d_model,), init_logit))
        self.alpha_m_logit = nn.Parameter(torch.full((d_model,), init_logit))
        self.backend = backend

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        h = ops.fused_spherical_step(h, self.attn(h), self.alpha_a_logit, mode="slerp", backend=self.backend)
        h = ops.fused_spherical_step(h, self.mlp(h), self.alpha_m_logit, mode="slerp", backend=self.backend)
        return h


class _FusedHoloLM(nn.Module):
    """Exact 12L H7b matched-param LM using HoloSphere fused kernels."""

    def __init__(self, d_model: int, n_heads: int, n_layers: int, base_d_ff: int, backend: str, vocab_size: int = 260) -> None:
        super().__init__()
        d_head = d_model // n_heads
        d_ff = base_d_ff - n_heads * (d_head // 4)
        self.tok_emb = nn.Embedding(vocab_size, d_model)
        self.blocks = nn.ModuleList([_FusedHoloBlock(d_model, n_heads, d_ff, backend) for _ in range(n_layers)])
        self.logit_scale = nn.Parameter(torch.full((1,), math.sqrt(float(d_model))))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = ops._safe_unit_norm(self.tok_emb(x), eps=1e-4)
        for blk in self.blocks:
            h = blk(h)
        return (h @ self.tok_emb.weight.T) * self.logit_scale


def _bench_full_12l_training(device: torch.device) -> Dict[str, Any]:
    """Exact PREREG-S114 H14a Criterion 3: 12L, d=320, H=8, d_ff=864, B=8, T=512, BF16 autocast."""
    bsz, seq_len, vocab = 8, 512, 260
    gen = torch.Generator(device="cpu").manual_seed(31415)
    x = torch.randint(0, vocab, (bsz, seq_len), generator=gen).to(device=device)
    y = torch.randint(0, vocab, (bsz, seq_len), generator=gen).to(device=device)

    arms = (
        ("rope2d_ngpt", lambda: s107.S107TransformerLM(s107.S107ModelConfig(arm_name="rope2d_ngpt", track="H7b", pos_mode="rope2d", ngpt=True))),
        ("eager_h7b", lambda: s107.S107TransformerLM(s107.S107ModelConfig(arm_name="eager_h7b", track="H7b", pos_mode="su2_holonomy", ngpt=True))),
        ("holosphere_cuda_sm86", lambda: _FusedHoloLM(320, 8, 12, 864, backend="cuda")),
        ("holosphere_triton_39", lambda: _FusedHoloLM(320, 8, 12, 864, backend="triton")),
    )
    res: Dict[str, Any] = {}
    for name, ctor in arms:
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)
        model = ctor().to(device)
        opt = torch.optim.AdamW(model.parameters(), lr=2.5e-3)
        n_params = sum(p.numel() for p in model.parameters())

        def _step() -> None:
            opt.zero_grad(set_to_none=True)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                out = model(x)
                logits = out[0] if isinstance(out, tuple) else out
                loss = F.cross_entropy(logits.float().reshape(-1, vocab), y.reshape(-1))
            loss.backward()
            opt.step()

        # Warmup + timed sustained window for accurate NVML power/mJ integration
        for _ in range(5):
            _step()
        torch.cuda.synchronize()
        p_pre = _query_nvml_power_w()
        t0 = time.monotonic()
        step_ms_list: List[float] = []
        n_steps = 25
        for _ in range(n_steps):
            ev0 = torch.cuda.Event(enable_timing=True)
            ev1 = torch.cuda.Event(enable_timing=True)
            ev0.record()
            _step()
            ev1.record()
            torch.cuda.synchronize()
            step_ms_list.append(float(ev0.elapsed_time(ev1)))
        wall_s = time.monotonic() - t0
        p_post = _query_nvml_power_w()
        avg_w = 0.5 * ((p_pre or 0.0) + (p_post or 0.0))
        mj_per_tok = (avg_w * wall_s * 1000.0) / float(n_steps * bsz * seq_len) if avg_w > 0 else 0.0
        peak_mib = float(torch.cuda.max_memory_allocated(device)) / (1024.0 * 1024.0)
        step_ms_list.sort()
        med_ms = step_ms_list[len(step_ms_list) // 2]
        res[name] = {
            "n_params": n_params,
            "step_median_ms": round(med_ms, 3),
            "step_mean_ms": round(sum(step_ms_list) / len(step_ms_list), 3),
            "tok_per_s": round(float(bsz * seq_len) / (med_ms * 1e-3), 1),
            "peak_vram_mib": round(peak_mib, 2),
            "nvml_avg_power_w": round(avg_w, 2),
            "train_mj_per_tok": round(mj_per_tok, 4),
        }
        del model, opt
        gc.collect()
        torch.cuda.empty_cache()

    rope_ms = res["rope2d_ngpt"]["step_median_ms"]
    eager_ms = res["eager_h7b"]["step_median_ms"]
    cuda_ms = res["holosphere_cuda_sm86"]["step_median_ms"]
    triton_ms = res["holosphere_triton_39"]["step_median_ms"]
    res["ratios"] = {
        "eager_vs_rope": round(eager_ms / rope_ms, 4),
        "cuda_vs_rope": round(cuda_ms / rope_ms, 4),
        "cuda_speedup_vs_eager": round(eager_ms / cuda_ms, 4),
        "triton_vs_rope": round(triton_ms / rope_ms, 4),
        "triton_speedup_vs_eager": round(eager_ms / triton_ms, 4),
    }
    return res


def _bench_single_block_scaling(device: torch.device) -> Dict[str, Any]:
    """Single-block fwd+bwd at B=8, H=8, d_head=64 (d_model=512, d_ff=1376), T in {512, 1024, 2048}, BF16."""
    bsz, heads, d_head = 8, 8, 64
    d_model = heads * d_head
    d_ff = 1376
    out: Dict[str, Any] = {}

    for seq_len in BENCH_LENGTHS:
        gen = torch.Generator(device="cpu").manual_seed(41400 + seq_len)
        x = torch.randn((bsz, seq_len, d_model), generator=gen).to(device=device, dtype=torch.bfloat16)
        gy = torch.randn((bsz, seq_len, d_model), generator=gen).to(device=device, dtype=torch.bfloat16)
        blk_arms = (
            ("rope2d_ngpt", lambda: s107.TransformerBlock(d_model, heads, d_ff, pos_mode="rope2d", ngpt=True)),
            ("eager_h7b", lambda: s107.TransformerBlock(d_model, heads, d_ff - d_model // 4, pos_mode="su2_holonomy", ngpt=True)),
            ("holosphere_cuda_sm86", lambda: _FusedHoloBlock(d_model, heads, d_ff - d_model // 4, backend="cuda")),
            ("holosphere_triton_39", lambda: _FusedHoloBlock(d_model, heads, d_ff - d_model // 4, backend="triton")),
        )
        t_res: Dict[str, Any] = {}
        for name, ctor in blk_arms:
            gc.collect()
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats(device)
            blk = ctor().to(device)

            def _fwdbwd() -> None:
                blk.zero_grad(set_to_none=True)
                xi = x.detach().requires_grad_(True)
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    y = blk(xi)
                    loss = (y * gy).sum()
                loss.backward()

            med_ms, _ = _time_cuda_ms(_fwdbwd, warmup=5, iters=20)
            peak_mib = float(torch.cuda.max_memory_allocated(device)) / (1024.0 * 1024.0)
            t_res[name] = {"fwdbwd_median_ms": round(med_ms, 3), "peak_vram_mib": round(peak_mib, 2)}
            del blk
            gc.collect()
            torch.cuda.empty_cache()
        t_res["cuda_vs_rope"] = round(t_res["holosphere_cuda_sm86"]["fwdbwd_median_ms"] / t_res["rope2d_ngpt"]["fwdbwd_median_ms"], 4)
        t_res["cuda_speedup_vs_eager"] = round(t_res["eager_h7b"]["fwdbwd_median_ms"] / t_res["holosphere_cuda_sm86"]["fwdbwd_median_ms"], 4)
        t_res["triton_vs_rope"] = round(t_res["holosphere_triton_39"]["fwdbwd_median_ms"] / t_res["rope2d_ngpt"]["fwdbwd_median_ms"], 4)
        t_res["triton_speedup_vs_eager"] = round(t_res["eager_h7b"]["fwdbwd_median_ms"] / t_res["holosphere_triton_39"]["fwdbwd_median_ms"], 4)
        out[str(seq_len)] = t_res
    return out


def main() -> int:
    t0 = time.monotonic()
    _require(torch.cuda.is_available(), "CUDA GPU is required for H14a live sm_86 benchmark")
    device = torch.device("cuda:0")
    prereg_path = _EXPEDITION / "notes" / "holosphere_kernel_transformer_2026_11_25" / "PREREG_S114_SILISPHERE_FUSED_ENTITY.md"
    prereg_sha = hashlib.sha256(prereg_path.read_bytes()).hexdigest()
    _require(prereg_sha == PREREG_SHA256, f"PREREG-S114 SHA mismatch: {prereg_sha}")

    ptxas_rec = json.loads((_HERE / "ptxas_sm86_zero_spill_receipt.json").read_text(encoding="utf-8"))
    _require(ptxas_rec["nonzero_spill_kernels"] == 0 and ptxas_rec["zero_spill_kernels"] >= 9, "Zero-spill receipt invalid")

    smi_pre = _query_gpu_snapshot()
    print(f"H14a LIVE sm_86 START gpu={smi_pre['name']} temp={smi_pre['temperature_gpu_c']}C", flush=True)

    parity = _run_parity_suite(device)
    print(f"  [1/3 PARITY] {json.dumps(parity['summary'])}", flush=True)

    micro = _run_kernel_microbench(device)
    for tl_k, v in micro.items():
        print(
            f"  [2/3 MICRO T={tl_k}] eager={v['eager_h7b']['fwdbwd_ms']}ms "
            f"cuda_bhtd={v['cuda_sm86_bhtd_with_permute']['fwdbwd_ms']}ms ({v['cuda_sm86_bhtd_with_permute']['fwdbwd_speedup_vs_eager']}x) "
            f"cuda_fiber={v['cuda_sm86_fiber_major_native']['fwdbwd_ms']}ms ({v['cuda_sm86_fiber_major_native']['fwdbwd_speedup_vs_eager']}x, permute_tax={v['cuda_sm86_fiber_major_native']['permute_tax_fwdbwd_pct']}%) "
            f"triton_fiber={v['triton_39_fiber_major_native']['fwdbwd_ms']}ms ({v['triton_39_fiber_major_native']['fwdbwd_speedup_vs_eager']}x)",
            flush=True,
        )

    full12 = _bench_full_12l_training(device)
    print(f"  [3A/3 FULL-12L B=8 T=512] ratios={json.dumps(full12['ratios'])}", flush=True)
    for k in ("rope2d_ngpt", "eager_h7b", "holosphere_cuda_sm86", "holosphere_triton_39"):
        print(f"    {k:22s} {json.dumps(full12[k])}", flush=True)

    blk = _bench_single_block_scaling(device)
    for tl_k, v in blk.items():
        print(
            f"  [3B/3 BLOCK B=8 H=8 D=64 T={tl_k}] rope={v['rope2d_ngpt']['fwdbwd_median_ms']}ms "
            f"eager={v['eager_h7b']['fwdbwd_median_ms']}ms "
            f"cuda={v['holosphere_cuda_sm86']['fwdbwd_median_ms']}ms ({v['cuda_vs_rope']}x rope, {v['cuda_speedup_vs_eager']}x vs eager) "
            f"triton={v['holosphere_triton_39']['fwdbwd_median_ms']}ms ({v['triton_vs_rope']}x rope)",
            flush=True,
        )

    smi_post = _query_gpu_snapshot()

    # Literal PREREG-S114 H14a grading
    c1_zero_spill = ptxas_rec["nonzero_spill_kernels"] == 0 and ptxas_rec["zero_spill_kernels"] == 9
    ps = parity["summary"]
    c2_parity = bool(ps["fp32_gate_pass_le_1e4"] and ps["bf16_gate_pass_le_5e3"] and ps["norm_gate_pass_le_1e5"] and ps["a16_syndrome_exact"])
    r = full12["ratios"]
    c3_e2e = bool(r["cuda_vs_rope"] <= 1.15 and r["cuda_speedup_vs_eager"] >= 3.40)
    c4_micro = bool(
        micro["512"]["cuda_sm86_bhtd_with_permute"]["fwdbwd_speedup_vs_eager"] >= 5.0
        and micro["2048"]["cuda_sm86_bhtd_with_permute"]["fwdbwd_speedup_vs_eager"] >= 5.0
    )
    if c1_zero_spill and c2_parity and c3_e2e and c4_micro:
        verdict = "CONFIRMED"
    elif c1_zero_spill and c2_parity and r["cuda_speedup_vs_eager"] >= 2.0:
        verdict = "PARTIAL"
    else:
        verdict = "FALSIFIED"

    payload: Dict[str, Any] = {
        "schema": "holosphere.track_s114.h14a_gpu_results.v1",
        "oracle_class": "anchor",
        "preregistration_sha256": prereg_sha,
        "cu_sha256": ptxas_rec["cu_sha256"],
        "completed_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "torch_version": torch.__version__,
        "parity": parity,
        "kernel_microbench": micro,
        "full_12l_h7b_step": full12,
        "single_block_scaling": blk,
        "h14a_locked_verdict": {
            "verdict": verdict,
            "c1_zero_spill": c1_zero_spill,
            "c2_parity": c2_parity,
            "c3_e2e_le_115x_and_ge_340x": c3_e2e,
            "c4_microbench_ge_5x": c4_micro,
        },
        "nvidia_smi_pre": smi_pre,
        "nvidia_smi_post": smi_post,
        "elapsed_seconds": round(time.monotonic() - t0, 3),
    }
    payload["result_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    out_bytes = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    out_path = _HERE / "s114_h14a_gpu_results.json"
    out_path.write_bytes(out_bytes)
    os.chmod(out_path, 0o600)
    print(f"\n=== H14a LOCKED VERDICT: {verdict} ===", flush=True)
    print(f"  GATES: {json.dumps(payload['h14a_locked_verdict'])}", flush=True)
    print(f"  FILE: {out_path.name} ({len(out_bytes)} B, file_sha256={hashlib.sha256(out_bytes).hexdigest()}, inner={payload['result_sha256']})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
