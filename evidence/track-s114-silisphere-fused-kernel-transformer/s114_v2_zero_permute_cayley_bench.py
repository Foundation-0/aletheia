#!/usr/bin/env python3
"""Track S114 V2 Live RTX 3080 sm_86 Benchmark: Zero-Permute BHTD, Direct-BF16, Cayley2x2, & cayley_su2.

Executes strictly inside mlos gpu-lease --mode train + mlos stamp-run --zone B --require-gpu:
  1. Live sm_86 Parity (FP32 <= 1e-4, BF16 <= 5e-3, norm_drift <= 1e-5) across ALL V2 kernels:
       - Zero-permute strided BHTD Holonomy (BOTH contiguous [B,H,T,D] AND [B,T,H,D].transpose(1,2),
         BOTH su2_exp AND SFU-free cayley_su2, BOTH FP32 AND native BF16, T in {32, 33, 100, 512, 513, 2048},
         d_head in {32 (nb=8), 40 (nb=10 tail-mask!), 64 (nb=16)})
       - Native BF16 fused_spherical_slerp_hopf_{fwd,bwd}_bf16
       - Beltrami [C, K] = 0 holosphere_cayley2x2_{fwd,bwd}_{f32,bf16} (full & broadcast omega + moment drift)
       - Zero-HBM-epilogue holosphere_hopf_s3_cayley2x2_{fwd,bwd}_{f32,bf16}
  2. Zero-Permute Kernel Microbench (B=8, H=8, d_head=64, T in {512, 1024, 2048}):
       - Eager H7b vs V1 Fiber-Major vs V2 Zero-Permute BHTD (FP32, BF16, cayley_su2 BF16)
  3. Cayley2x2 & Hopf-S^3 + Cayley2x2 Standalone Microbench (B=8, T=512, d=384, BF16 — exact S110 shape!)
  4. Full 12L H7b Step (d=320, H=8, d_ff=864, B=8, T=512, BF16 autocast, NVML mJ/tok, peak VRAM):
       - rope2d_ngpt
       - eager_h7b
       - holosphere_v2_cuda_sm86 (Zero-permute + direct-BF16 SLERP)
       - holosphere_v2_cayley_su2 (Zero-permute SFU-free pure-rational cayley_su2!)
       - holosphere_v2_plus_cayley2x2_fused (Stage +1a fused Cayley2x2 post-MLP overhead!)
       - holosphere_v2_plus_cayley2x2_eager (Apples-to-apples eager Cayley2x2 overhead!)
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

PREREG_SHA256 = "5fa927a06933c3cff057b65f75c1d2f190e10f1e420303d582dfb7c802ee69a4"
STREAM_TRIAD_GBS = 356.6


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


def _err(a: torch.Tensor, b: torch.Tensor) -> Dict[str, float]:
    af, bf = a.detach().float(), b.detach().float()
    max_abs = float((af - bf).abs().max().item())
    denom = float(bf.abs().max().item())
    max_rel = max_abs / max(denom, 1e-12)
    cos = float(F.cosine_similarity(af.reshape(1, -1), bf.reshape(1, -1), eps=1e-12).item())
    return {"max_abs": round(max_abs, 8), "max_rel": round(max_rel, 8), "cosine": round(cos, 8)}


def _time_cuda_ms(fn: Callable[[], None], warmup: int = 8, iters: int = 30) -> Tuple[float, float]:
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
    return times[len(times) // 2], sum(times) / float(len(times))


# ---------------------------------------------------------------------------
# Part 1: Exhaustive V2 Parity (Zero-Permute BHTD, Strided BTH, Cayley2x2, cayley_su2)
# ---------------------------------------------------------------------------


def _run_v2_parity(device: torch.device) -> Dict[str, Any]:
    worst_fp32 = 0.0
    worst_bf16 = 0.0
    worst_nd = 0.0
    any_nan = False
    bhtd_rows: List[Dict[str, Any]] = []

    # Test contiguous [B,H,T,D] AND transposed [B,T,H,D].transpose(1,2), nb=10 (non-multiple of 4!) & nb=16
    configs = (
        (32, 32, False, "exp"),
        (33, 40, True, "exp"),     # nb=10 tail mask + transposed [B,T,H,D] + non-power-of-2 T!
        (37, 40, False, "cayley"), # GPT-6 non-multiple-of-32 length
        (100, 40, True, "cayley"),
        (255, 64, True, "exp"),    # GPT-6 256-1 boundary
        (512, 64, False, "exp"),
        (513, 40, True, "exp"),
        (513, 64, True, "cayley"),
        (2048, 40, True, "exp"),
        (2048, 64, False, "cayley"),
    )
    for dtype_name, dtype in (("fp32", torch.float32), ("bf16", torch.bfloat16)):
        for seq_len, d_head, transposed, map_mode in configs:
            gen = torch.Generator(device="cpu").manual_seed(51400 + seq_len + d_head + (1 if map_mode == "cayley" else 0))
            bsz, heads = 2, 4
            nb = d_head // 4
            angle_sc = 0.50 if map_mode == "cayley" else 0.75
            if transposed:
                q0 = ops._safe_unit_norm(torch.randn((bsz, seq_len, heads, d_head), generator=gen)).to(device, dtype).transpose(1, 2)
                k0 = ops._safe_unit_norm(torch.randn((bsz, seq_len, heads, d_head), generator=gen)).to(device, dtype).transpose(1, 2)
                v0 = ops._safe_unit_norm(torch.randn((bsz, seq_len, heads, d_head), generator=gen)).to(device, dtype).transpose(1, 2)
                om0 = torch.randn((bsz, seq_len, heads, nb, 3), generator=gen).to(device, dtype).transpose(1, 2)
            else:
                q0 = ops._safe_unit_norm(torch.randn((bsz, heads, seq_len, d_head), generator=gen)).to(device, dtype)
                k0 = ops._safe_unit_norm(torch.randn((bsz, heads, seq_len, d_head), generator=gen)).to(device, dtype)
                v0 = ops._safe_unit_norm(torch.randn((bsz, heads, seq_len, d_head), generator=gen)).to(device, dtype)
                om0 = torch.randn((bsz, heads, seq_len, nb, 3), generator=gen).to(device, dtype)
            gq = ops._safe_unit_norm(torch.randn((bsz, heads, seq_len, d_head), generator=gen)).to(device, dtype)
            gk = ops._safe_unit_norm(torch.randn((bsz, heads, seq_len, d_head), generator=gen)).to(device, dtype)
            gv = ops._safe_unit_norm(torch.randn((bsz, heads, seq_len, d_head), generator=gen)).to(device, dtype)
            sc = 1.0 / float(seq_len)

            # Exact FP32 reference
            qr, kr, vr, omr = (t.float().detach().requires_grad_(True) for t in (q0, k0, v0, om0))
            qro, kro, vro, pir = ops.su2_holonomy_transport(
                qr, kr, vr, omr, angle_scale=angle_sc, transport_v=True, backend="reference", map_mode=map_mode
            )
            lr = ((qro * gq.float()).sum() + (kro * gk.float()).sum() + (vro * gv.float()).sum()) * sc
            dqr, dkr, dvr, domr = torch.autograd.grad(lr, (qr, kr, vr, omr))

            # V2 CUDA zero-permute kernel (preserving exact transposed strides if transposed=True!)
            qc, kc, vc, omc = (t.detach().clone().requires_grad_(True) for t in (q0, k0, v0, om0))
            if transposed:
                qc = q0.transpose(1, 2).contiguous().detach().requires_grad_(True)
                kc = k0.transpose(1, 2).contiguous().detach().requires_grad_(True)
                vc = v0.transpose(1, 2).contiguous().detach().requires_grad_(True)
                omc = om0.transpose(1, 2).contiguous().detach().requires_grad_(True)
                qco, kco, vco, pic = ops.su2_holonomy_transport(
                    qc.transpose(1, 2), kc.transpose(1, 2), vc.transpose(1, 2), omc.transpose(1, 2),
                    angle_scale=angle_sc, transport_v=True, backend="cuda", map_mode=map_mode,
                )
            else:
                qco, kco, vco, pic = ops.su2_holonomy_transport(
                    qc, kc, vc, omc, angle_scale=angle_sc, transport_v=True, backend="cuda", map_mode=map_mode,
                )
            lc = ((qco.float() * gq.float()).sum() + (kco.float() * gk.float()).sum() + (vco.float() * gv.float()).sum()) * sc
            dqc, dkc, dvc, domc = torch.autograd.grad(lc, (qc, kc, vc, omc))
            if transposed:
                dqc, dkc, dvc, domc = dqc.transpose(1, 2), dkc.transpose(1, 2), dvc.transpose(1, 2), domc.transpose(1, 2)

            for t_chk in (qco, kco, vco, pic, dqc, dkc, dvc, domc):
                if not bool(torch.isfinite(t_chk).all().item()):
                    any_nan = True
            nd = float((torch.linalg.vector_norm(pic.float(), dim=-1) - 1.0).abs().max().item())
            worst_nd = max(worst_nd, nd)
            fwd_max = max(_err(qco, qro)["max_abs"], _err(kco, kro)["max_abs"], _err(vco, vro)["max_abs"], _err(pic, pir)["max_abs"])
            bwd_max = max(_err(dqc, dqr)["max_abs"], _err(dkc, dkr)["max_abs"], _err(dvc, dvr)["max_abs"], _err(domc, domr)["max_abs"])
            mx = max(fwd_max, bwd_max)
            if dtype_name == "fp32":
                worst_fp32 = max(worst_fp32, mx)
            else:
                worst_bf16 = max(worst_bf16, mx)
            bhtd_rows.append({
                "dtype": dtype_name, "T": seq_len, "d_head": d_head, "nb": nb,
                "layout": "BTH_transposed" if transposed else "BHT_contig",
                "map_mode": map_mode, "fwd_max_abs": round(fwd_max, 8), "bwd_max_abs": round(bwd_max, 8),
                "norm_drift": round(nd, 8),
            })

    # Native BF16 SLERP + Safe-Hopf + Cayley2x2 + Fused Hopf-S^3+Cayley2x2 parity
    op_parity: Dict[str, Any] = {}
    for dtype_name, dtype in (("fp32", torch.float32), ("bf16", torch.bfloat16)):
        gen = torch.Generator(device="cpu").manual_seed(51499)
        h0 = ops._safe_unit_norm(torch.randn((8, 128, 384), generator=gen)).to(device, dtype)
        d0 = ops._safe_unit_norm(torch.randn((8, 128, 384), generator=gen)).to(device, dtype)
        w0 = (0.5 * torch.randn((8, 128, 192), generator=gen)).to(device, dtype)
        a0 = torch.randn((384,), generator=gen).to(device, torch.float32)
        go = ops._safe_unit_norm(torch.randn((8, 128, 384), generator=gen)).to(device, dtype)

        # 1. Direct-BF16 / FP32 Spherical SLERP + cayley_acute Safe-Hopf
        phi = ops.safe_hopf_clock_angle(5, law="cayley_acute", r_max=8)
        hr, dr, ar = h0.float().detach().requires_grad_(True), d0.float().detach().requires_grad_(True), a0.float().detach().requires_grad_(True)
        yr = ops.fused_spherical_step(hr, dr, ar, mode="safe_hopf_loop", phi=phi, backend="reference")
        ghr, gdr, gar = torch.autograd.grad((yr * go.float()).sum(), (hr, dr, ar))
        hc, dc, ac = h0.detach().clone().requires_grad_(True), d0.detach().clone().requires_grad_(True), a0.detach().clone().requires_grad_(True)
        yc = ops.fused_spherical_step(hc, dc, ac, mode="safe_hopf_loop", phi=phi, backend="cuda")
        ghc, gdc, gac = torch.autograd.grad((yc.float() * go.float()).sum(), (hc, dc, ac))
        m_slerp = {"fwd": _err(yc, yr), "d_h": _err(ghc, ghr), "d_delta": _err(gdc, gdr), "d_alpha": _err(gac, gar)}

        # 2. Cayley2x2
        xr, wr = h0.float().detach().requires_grad_(True), w0.float().detach().requires_grad_(True)
        yr_c = ops.cayley_2x2_rotate(xr, wr, backend="reference")
        gxr, gwr = torch.autograd.grad((yr_c * go.float()).sum(), (xr, wr))
        xc, wc = h0.detach().clone().requires_grad_(True), w0.detach().clone().requires_grad_(True)
        yc_c = ops.cayley_2x2_rotate(xc, wc, backend="cuda")
        gxc, gwc = torch.autograd.grad((yc_c.float() * go.float()).sum(), (xc, wc))
        m_cay = {"fwd": _err(yc_c, yr_c), "d_x": _err(gxc, gxr), "d_omega": _err(gwc, gwr)}

        # 3. Zero-HBM-epilogue Hopf-S^3 + Cayley2x2
        hr2, dr2, wr2 = h0.float().detach().requires_grad_(True), d0.float().detach().requires_grad_(True), w0.float().detach().requires_grad_(True)
        yr_hc = ops.hopf_s3_cayley_2x2_step(hr2, dr2, wr2, backend="reference")
        ghr2, gdr2, gwr2 = torch.autograd.grad((yr_hc * go.float()).sum(), (hr2, dr2, wr2))
        hc2, dc2, wc2 = h0.detach().clone().requires_grad_(True), d0.detach().clone().requires_grad_(True), w0.detach().clone().requires_grad_(True)
        yc_hc = ops.hopf_s3_cayley_2x2_step(hc2, dc2, wc2, backend="cuda")
        ghc2, gdc2, gwc2 = torch.autograd.grad((yc_hc.float() * go.float()).sum(), (hc2, dc2, wc2))
        m_hc = {"fwd": _err(yc_hc, yr_hc), "d_h": _err(ghc2, ghr2), "d_delta": _err(gdc2, gdr2), "d_omega": _err(gwc2, gwr2)}

        mx_op = max(
            m_slerp["fwd"]["max_abs"], m_slerp["d_h"]["max_abs"], m_slerp["d_delta"]["max_abs"], m_slerp["d_alpha"]["max_rel"],
            m_cay["fwd"]["max_abs"], m_cay["d_x"]["max_abs"], m_cay["d_omega"]["max_abs"],
            m_hc["fwd"]["max_abs"], m_hc["d_h"]["max_abs"], m_hc["d_delta"]["max_abs"], m_hc["d_omega"]["max_abs"],
        )
        if dtype_name == "fp32":
            worst_fp32 = max(worst_fp32, mx_op)
        else:
            worst_bf16 = max(worst_bf16, mx_op)
        op_parity[dtype_name] = {"slerp_hopf": m_slerp, "cayley2x2": m_cay, "hopf_s3_cayley2x2": m_hc}

    # Live GPU Beltrami [C, K] = 0 helicity moment conservation (m0..m4 across 8 iterations in FP32)
    d_bel = 384
    n_half = (d_bel // 2) // 2
    diag_vals: List[float] = []
    for q_i in range(n_half):
        lam = float(q_i + 1) / float(n_half)
        diag_vals.extend([lam, lam, -lam, -lam])
    c_diag = torch.tensor(diag_vals, device=device, dtype=torch.float32)
    gen_b = torch.Generator(device="cpu").manual_seed(11477)
    v_bel = ops._safe_unit_norm(torch.randn((1, 1, d_bel), generator=gen_b)).to(device, torch.float32)
    w_bel = torch.empty((1, 1, d_bel // 2)).uniform_(-0.35, 0.35, generator=gen_b).to(device, torch.float32)
    m0_bel = [float((v_bel * (c_diag ** p) * v_bel).sum().item()) for p in range(5)]
    max_bel_drift = 0.0
    cur_bel = v_bel.clone()
    for _ in range(8):
        cur_bel = ops.cayley_2x2_rotate(cur_bel, w_bel, backend="cuda")
        for p in range(5):
            mp = float((cur_bel * (c_diag ** p) * cur_bel).sum().item())
            max_bel_drift = max(max_bel_drift, abs(mp - m0_bel[p]))

    return {
        "bhtd_rows": bhtd_rows,
        "op_parity": op_parity,
        "gpu_beltrami_m0_m4_max_drift": round(max_bel_drift, 10),
        "summary": {
            "worst_fp32_err": round(worst_fp32, 8),
            "worst_bf16_err": round(worst_bf16, 8),
            "worst_unit_norm_drift": round(worst_nd, 8),
            "beltrami_m0_m4_drift_le_1e6": max_bel_drift <= 1e-6,
            "any_nan_or_inf": any_nan,
            "all_v2_parity_pass": (worst_fp32 <= 1e-4) and (worst_bf16 <= 5e-3) and (worst_nd <= 1e-5) and (max_bel_drift <= 1e-6) and (not any_nan),
        },
    }


# ---------------------------------------------------------------------------
# Part 2: V2 Zero-Permute & Cayley2x2 Standalone Microbenches
# ---------------------------------------------------------------------------


def _run_v2_microbench(device: torch.device) -> Dict[str, Any]:
    bsz, heads, d_head = 8, 8, 64
    nb = d_head // 4
    n_fibers = bsz * heads * nb
    lib = ops._load_cuda_lib()
    _require(lib is not None, "CUDA library missing")
    holo_out: Dict[str, Any] = {}

    for seq_len in (512, 1024, 2048):
        gen = torch.Generator(device="cpu").manual_seed(61400 + seq_len)
        q = torch.randn((bsz, heads, seq_len, d_head), generator=gen).to(device, torch.float32)
        k = torch.randn((bsz, heads, seq_len, d_head), generator=gen).to(device, torch.float32)
        v = torch.randn((bsz, heads, seq_len, d_head), generator=gen).to(device, torch.float32)
        om = torch.randn((bsz, heads, seq_len, nb, 3), generator=gen).to(device, torch.float32)
        gq = torch.randn((bsz, heads, seq_len, d_head), generator=gen).to(device, torch.float32)
        gk = torch.randn((bsz, heads, seq_len, d_head), generator=gen).to(device, torch.float32)

        q_bf, k_bf, v_bf, om_bf = q.bfloat16(), k.bfloat16(), v.bfloat16(), om.bfloat16()
        gq_bf, gk_bf = gq.bfloat16(), gk.bfloat16()
        # Realistic transposed [B, T, H, D].transpose(1, 2) inputs directly from Linear projections!
        q_tr = q_bf.transpose(1, 2).contiguous().transpose(1, 2)
        k_tr = k_bf.transpose(1, 2).contiguous().transpose(1, 2)
        v_tr = v_bf.transpose(1, 2).contiguous().transpose(1, 2)
        om_tr = om_bf.transpose(1, 2).contiguous().transpose(1, 2)

        # V1 fiber-major reference buffer
        q_f = q.reshape(bsz, heads, seq_len, nb, 4).permute(0, 1, 3, 2, 4).reshape(n_fibers, seq_len, 4).contiguous()
        k_f = k.reshape(bsz, heads, seq_len, nb, 4).permute(0, 1, 3, 2, 4).reshape(n_fibers, seq_len, 4).contiguous()
        om_f = om.permute(0, 1, 3, 2, 4).reshape(n_fibers, seq_len, 3).contiguous()
        u_f, qo_f, ko_f = torch.empty_like(q_f), torch.empty_like(q_f), torch.empty_like(k_f)
        dqo_f, dko_f = torch.randn_like(q_f), torch.randn_like(k_f)
        dqi_f, dki_f, dom_f = torch.empty_like(q_f), torch.empty_like(k_f), torch.empty_like(om_f)

        fwd_bytes_f32 = float(n_fibers * seq_len * 23 * 4)
        fwdbwd_bytes_f32 = float(n_fibers * seq_len * 57 * 4)
        # BF16 minimal traffic: U is FP32 (4*4=16B), raw(3)+Q(4)+K(4)+Qout(4)+Kout(4)=19 bf16 (38B) -> 54 B/step/fiber fwd
        fwd_bytes_bf16 = float(n_fibers * seq_len * (4 * 4 + 19 * 2))

        def _eager_fwdbwd() -> None:
            qi, ki, omi = q.detach().requires_grad_(True), k.detach().requires_grad_(True), om.detach().requires_grad_(True)
            du = s107.su2_exp(0.75 * torch.tanh(omi).permute(0, 2, 1, 3, 4))
            u = s107.su2_parallel_prefix_scan(du).permute(0, 2, 1, 3, 4)
            qo = s107.quat_mul(u, qi.reshape(bsz, heads, seq_len, nb, 4)).reshape_as(qi)
            ko = s107.quat_mul(u, ki.reshape(bsz, heads, seq_len, nb, 4)).reshape_as(ki)
            ((qo * gq).sum() + (ko * gk).sum()).backward()

        def _v1_fiber_fwdbwd() -> None:
            lib.silisphere_su2_holonomy_fwd_f32(
                ops._ptr(om_f), ops._ptr(q_f), ops._ptr(k_f), ctypes.c_void_p(0),
                ops._ptr(u_f), ops._ptr(qo_f), ops._ptr(ko_f), ctypes.c_void_p(0),
                n_fibers, seq_len, 0.75, 1, 1e-6, ops._cuda_stream_ptr(device),
            )
            lib.silisphere_su2_holonomy_bwd_f32(
                ops._ptr(om_f), ops._ptr(u_f), ops._ptr(q_f), ops._ptr(k_f), ctypes.c_void_p(0),
                ctypes.c_void_p(0), ops._ptr(dqo_f), ops._ptr(dko_f), ctypes.c_void_p(0),
                ops._ptr(dom_f), ops._ptr(dqi_f), ops._ptr(dki_f), ctypes.c_void_p(0),
                n_fibers, seq_len, 0.75, 1, 1e-6, ops._cuda_stream_ptr(device),
            )

        def _v2_bhtd_f32_fwd() -> None:
            with torch.no_grad():
                ops.su2_holonomy_transport(q, k, v, om, angle_scale=0.75, transport_v=False, backend="cuda", map_mode="exp")

        def _v2_bhtd_f32_fwdbwd() -> None:
            qi, ki, omi = q.detach().requires_grad_(True), k.detach().requires_grad_(True), om.detach().requires_grad_(True)
            qo, ko, _, _ = ops.su2_holonomy_transport(qi, ki, v, omi, angle_scale=0.75, transport_v=False, backend="cuda", map_mode="exp")
            ((qo * gq).sum() + (ko * gk).sum()).backward()

        def _v2_bhtd_bf16_fwd() -> None:
            with torch.no_grad():
                ops.su2_holonomy_transport(q_tr, k_tr, v_tr, om_tr, angle_scale=0.75, transport_v=False, backend="cuda", map_mode="exp")

        def _v2_bhtd_bf16_fwdbwd() -> None:
            qi = q_tr.detach().requires_grad_(True)
            ki = k_tr.detach().requires_grad_(True)
            omi = om_tr.detach().requires_grad_(True)
            qo, ko, _, _ = ops.su2_holonomy_transport(qi, ki, v_tr, omi, angle_scale=0.75, transport_v=False, backend="cuda", map_mode="exp")
            ((qo * gq_bf).sum() + (ko * gk_bf).sum()).backward()

        def _v2_cayley_bf16_fwdbwd() -> None:
            qi = q_tr.detach().requires_grad_(True)
            ki = k_tr.detach().requires_grad_(True)
            omi = om_tr.detach().requires_grad_(True)
            qo, ko, _, _ = ops.su2_holonomy_transport(qi, ki, v_tr, omi, angle_scale=0.50, transport_v=False, backend="cuda", map_mode="cayley")
            ((qo * gq_bf).sum() + (ko * gk_bf).sum()).backward()

        e_fb, _ = _time_cuda_ms(_eager_fwdbwd, warmup=5, iters=18)
        v1_fib, _ = _time_cuda_ms(_v1_fiber_fwdbwd, warmup=8, iters=30)
        v2_f32_f, _ = _time_cuda_ms(_v2_bhtd_f32_fwd, warmup=8, iters=30)
        v2_f32_fb, _ = _time_cuda_ms(_v2_bhtd_f32_fwdbwd, warmup=8, iters=30)
        v2_bf_f, _ = _time_cuda_ms(_v2_bhtd_bf16_fwd, warmup=8, iters=30)
        v2_bf_fb, _ = _time_cuda_ms(_v2_bhtd_bf16_fwdbwd, warmup=8, iters=30)
        v2_cay_fb, _ = _time_cuda_ms(_v2_cayley_bf16_fwdbwd, warmup=8, iters=30)

        holo_out[str(seq_len)] = {
            "eager_h7b_fwdbwd_ms": round(e_fb, 4),
            "v1_fiber_major_fwdbwd_ms": round(v1_fib, 4),
            "v2_zero_permute_f32": {
                "fwd_ms": round(v2_f32_f, 4),
                "fwdbwd_ms": round(v2_f32_fb, 4),
                "fwdbwd_speedup_vs_eager": round(e_fb / v2_f32_fb, 2),
                "fwd_eff_gbs": round(fwd_bytes_f32 / (v2_f32_f * 1e6), 2),
                "fwdbwd_eff_gbs": round(fwdbwd_bytes_f32 / (v2_f32_fb * 1e6), 2),
                "fwd_pct_stream_triad": round(100.0 * (fwd_bytes_f32 / (v2_f32_f * 1e6)) / STREAM_TRIAD_GBS, 2),
            },
            "v2_zero_permute_bf16_transposed": {
                "fwd_ms": round(v2_bf_f, 4),
                "fwdbwd_ms": round(v2_bf_fb, 4),
                "fwdbwd_speedup_vs_eager": round(e_fb / v2_bf_fb, 2),
                "fwd_eff_gbs": round(fwd_bytes_bf16 / (v2_bf_f * 1e6), 2),
            },
            "v2_cayley_su2_bf16_transposed": {
                "fwdbwd_ms": round(v2_cay_fb, 4),
                "fwdbwd_speedup_vs_eager": round(e_fb / v2_cay_fb, 2),
            },
        }
        del q, k, v, om, gq, gk, q_bf, k_bf, v_bf, om_bf, gq_bf, gk_bf, q_tr, k_tr, v_tr, om_tr
        del q_f, k_f, om_f, u_f, qo_f, ko_f, dqo_f, dko_f, dqi_f, dki_f, dom_f
        torch.cuda.empty_cache()

    # Exact S110 Cayley2x2 microbench shape: B=8, T=512, d=384, BF16
    gen_c = torch.Generator(device="cpu").manual_seed(61488)
    xc = torch.randn((8, 512, 384), generator=gen_c).to(device, torch.bfloat16)
    dc = torch.randn((8, 512, 384), generator=gen_c).to(device, torch.bfloat16)
    wc = (0.5 * torch.randn((8, 512, 192), generator=gen_c)).to(device, torch.bfloat16)
    gyc = torch.randn((8, 512, 384), generator=gen_c).to(device, torch.bfloat16)

    def _eager_cayley_fb() -> None:
        xi, wi = xc.detach().requires_grad_(True), wc.detach().requires_grad_(True)
        xf = xi.float().reshape(8, 512, 192, 2)
        wf = wi.float()
        w2 = wf * wf
        inv_d = 1.0 / (1.0 + w2)
        c, s = (1.0 - w2) * inv_d, (2.0 * wf) * inv_d
        y = torch.stack((c * xf[..., 0] + s * xf[..., 1], -s * xf[..., 0] + c * xf[..., 1]), dim=-1).reshape_as(xi).to(xi.dtype)
        (y * gyc).sum().backward()

    def _fused_cayley_fb() -> None:
        xi, wi = xc.detach().requires_grad_(True), wc.detach().requires_grad_(True)
        y = ops.cayley_2x2_rotate(xi, wi, backend="cuda")
        (y * gyc).sum().backward()

    def _fused_hopf_cayley_fb() -> None:
        hi, di, wi = xc.detach().requires_grad_(True), dc.detach().requires_grad_(True), wc.detach().requires_grad_(True)
        y = ops.hopf_s3_cayley_2x2_step(hi, di, wi, backend="cuda")
        (y * gyc).sum().backward()

    def _eager_hopf_cayley_fb() -> None:
        hi, di, wi = xc.detach().requires_grad_(True), dc.detach().requires_grad_(True), wc.detach().requires_grad_(True)
        z = ops.fused_spherical_step(hi, di, mode="hopf_s3", backend="reference")
        y = ops.cayley_2x2_rotate(z, wi, backend="reference")
        (y * gyc).sum().backward()

    ec_ms, _ = _time_cuda_ms(_eager_cayley_fb, warmup=8, iters=30)
    fc_ms, _ = _time_cuda_ms(_fused_cayley_fb, warmup=8, iters=30)
    ehc_ms, _ = _time_cuda_ms(_eager_hopf_cayley_fb, warmup=8, iters=30)
    fhc_ms, _ = _time_cuda_ms(_fused_hopf_cayley_fb, warmup=8, iters=30)

    return {
        "holonomy_bhtd": holo_out,
        "cayley2x2_s110_shape_b8_t512_d384_bf16": {
            "eager_cayley2x2_fwdbwd_ms": round(ec_ms, 4),
            "fused_sm86_cayley2x2_fwdbwd_ms": round(fc_ms, 4),
            "cayley2x2_speedup": round(ec_ms / fc_ms, 2),
            "eager_hopf_s3_plus_cayley2x2_fwdbwd_ms": round(ehc_ms, 4),
            "fused_sm86_hopf_s3_cayley2x2_fwdbwd_ms": round(fhc_ms, 4),
            "hopf_s3_cayley2x2_speedup": round(ehc_ms / fhc_ms, 2),
        },
    }


# ---------------------------------------------------------------------------
# Part 3: Full 12L Training Step (H7b V2 Zero-Permute + cayley_su2 + Cayley2x2 Stage+1a)
# ---------------------------------------------------------------------------


class _Cayley2x2PostMLP(nn.Module):
    """Exact S110 #1 data-dependent low-rank Cayley2x2 module (rank=16)."""

    def __init__(self, d_model: int, rank: int = 16, fused: bool = True) -> None:
        super().__init__()
        self.n_pairs = d_model // 2
        self.fused = fused
        self.base_omega = nn.Parameter(torch.zeros(self.n_pairs))
        self.w_down = nn.Linear(d_model, rank, bias=False)
        self.w_up = nn.Linear(rank, self.n_pairs, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        om = self.base_omega.view(1, 1, self.n_pairs) + 0.75 * torch.tanh(self.w_up(F.silu(self.w_down(x))))
        if self.fused:
            return ops.cayley_2x2_rotate(x, om, backend="cuda")
        xf = x.float().reshape(*x.shape[:-1], self.n_pairs, 2)
        wf = om.float()
        w2 = wf * wf
        inv_d = 1.0 / (1.0 + w2)
        c, s = (1.0 - w2) * inv_d, (2.0 * wf) * inv_d
        return torch.stack((c * xf[..., 0] + s * xf[..., 1], -s * xf[..., 0] + c * xf[..., 1]), dim=-1).reshape_as(x).to(x.dtype)


class _V2HoloBlock(nn.Module):
    def __init__(self, d_model: int, n_heads: int, d_ff: int, map_mode: str = "exp", cayley_mode: str = "none") -> None:
        super().__init__()
        self.attn = ops.S114CovariantHolonomyAttention(
            d_model, n_heads, covariant_v=False, ngpt=True,
            angle_scale=(0.50 if map_mode == "cayley" else 0.75),
            backend="cuda", map_mode=map_mode,
        )
        self.mlp = s107.SwiGLUMLP(d_model, d_ff, ngpt=True)
        init_logit = math.log(0.05 / 0.95)
        self.alpha_a_logit = nn.Parameter(torch.full((d_model,), init_logit))
        self.alpha_m_logit = nn.Parameter(torch.full((d_model,), init_logit))
        self.cayley = _Cayley2x2PostMLP(d_model, rank=16, fused=(cayley_mode == "fused")) if cayley_mode != "none" else None

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        h = ops.fused_spherical_step(h, self.attn(h), self.alpha_a_logit, mode="slerp", backend="cuda")
        delta_m = self.mlp(h)
        if self.cayley is not None:
            delta_m = self.cayley(delta_m)
        h = ops.fused_spherical_step(h, delta_m, self.alpha_m_logit, mode="slerp", backend="cuda")
        return h


class _V2HoloLM(nn.Module):
    def __init__(self, d_model: int, n_heads: int, n_layers: int, base_d_ff: int, map_mode: str = "exp", cayley_mode: str = "none", vocab_size: int = 260) -> None:
        super().__init__()
        d_head = d_model // n_heads
        d_ff = base_d_ff - n_heads * (d_head // 4)
        self.tok_emb = nn.Embedding(vocab_size, d_model)
        self.blocks = nn.ModuleList([_V2HoloBlock(d_model, n_heads, d_ff, map_mode=map_mode, cayley_mode=cayley_mode) for _ in range(n_layers)])
        self.logit_scale = nn.Parameter(torch.full((1,), math.sqrt(float(d_model))))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = ops._safe_unit_norm(self.tok_emb(x), eps=1e-4)
        for blk in self.blocks:
            h = blk(h)
        return (h @ self.tok_emb.weight.T) * self.logit_scale


def _bench_v2_full_12l(device: torch.device) -> Dict[str, Any]:
    bsz, seq_len, vocab = 8, 512, 260
    gen = torch.Generator(device="cpu").manual_seed(71415)
    x = torch.randint(0, vocab, (bsz, seq_len), generator=gen).to(device)
    y = torch.randint(0, vocab, (bsz, seq_len), generator=gen).to(device)

    arms = (
        ("rope2d_ngpt", lambda: s107.S107TransformerLM(s107.S107ModelConfig(arm_name="rope2d_ngpt", track="H7b", pos_mode="rope2d", ngpt=True))),
        ("eager_h7b", lambda: s107.S107TransformerLM(s107.S107ModelConfig(arm_name="eager_h7b", track="H7b", pos_mode="su2_holonomy", ngpt=True))),
        ("holosphere_v2_sm86", lambda: _V2HoloLM(320, 8, 12, 864, map_mode="exp", cayley_mode="none")),
        ("holosphere_v2_cayley_su2", lambda: _V2HoloLM(320, 8, 12, 864, map_mode="cayley", cayley_mode="none")),
        ("holosphere_v2_plus_cayley2x2_fused", lambda: _V2HoloLM(320, 8, 12, 864, map_mode="exp", cayley_mode="fused")),
        ("holosphere_v2_plus_cayley2x2_eager", lambda: _V2HoloLM(320, 8, 12, 864, map_mode="exp", cayley_mode="eager")),
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
    v2_ms = res["holosphere_v2_sm86"]["step_median_ms"]
    cs_ms = res["holosphere_v2_cayley_su2"]["step_median_ms"]
    c2f_ms = res["holosphere_v2_plus_cayley2x2_fused"]["step_median_ms"]
    c2e_ms = res["holosphere_v2_plus_cayley2x2_eager"]["step_median_ms"]
    res["ratios"] = {
        "v2_vs_rope": round(v2_ms / rope_ms, 4),
        "v2_speedup_vs_eager": round(eager_ms / v2_ms, 4),
        "v2_cayley_su2_vs_rope": round(cs_ms / rope_ms, 4),
        "v2_cayley_su2_speedup_vs_eager": round(eager_ms / cs_ms, 4),
        "cayley2x2_fused_overhead_pct": round(100.0 * (c2f_ms - v2_ms) / v2_ms, 2),
        "cayley2x2_eager_overhead_pct": round(100.0 * (c2e_ms - v2_ms) / v2_ms, 2),
        "v2_plus_cayley2x2_fused_vs_rope": round(c2f_ms / rope_ms, 4),
    }
    return res


def main() -> int:
    t0 = time.monotonic()
    _require(torch.cuda.is_available(), "CUDA GPU required")
    device = torch.device("cuda:0")
    ptxas_rec = json.loads((_HERE / "ptxas_sm86_zero_spill_receipt.json").read_text(encoding="utf-8"))
    _require(ptxas_rec["nonzero_spill_kernels"] == 0 and ptxas_rec["zero_spill_kernels"] == 27, "V2 27-kernel zero-spill receipt invalid")

    smi_pre = _query_gpu_snapshot()
    print(f"V2 LIVE sm_86 START gpu={smi_pre['name']} temp={smi_pre['temperature_gpu_c']}C kernels=27/27_zero_spill", flush=True)

    parity = _run_v2_parity(device)
    print(f"  [1/3 V2 PARITY] {json.dumps(parity['summary'])} beltrami_drift={parity['gpu_beltrami_m0_m4_max_drift']}", flush=True)

    micro = _run_v2_microbench(device)
    for tl_k, v in micro["holonomy_bhtd"].items():
        print(
            f"  [2A/3 HOLO T={tl_k}] eager={v['eager_h7b_fwdbwd_ms']}ms v1_fib={v['v1_fiber_major_fwdbwd_ms']}ms "
            f"v2_f32={v['v2_zero_permute_f32']['fwdbwd_ms']}ms ({v['v2_zero_permute_f32']['fwdbwd_speedup_vs_eager']}x, {v['v2_zero_permute_f32']['fwd_eff_gbs']} GB/s = {v['v2_zero_permute_f32']['fwd_pct_stream_triad']}% Triad) "
            f"v2_bf16={v['v2_zero_permute_bf16_transposed']['fwdbwd_ms']}ms ({v['v2_zero_permute_bf16_transposed']['fwdbwd_speedup_vs_eager']}x) "
            f"v2_cay_su2={v['v2_cayley_su2_bf16_transposed']['fwdbwd_ms']}ms ({v['v2_cayley_su2_bf16_transposed']['fwdbwd_speedup_vs_eager']}x)",
            flush=True,
        )
    print(f"  [2B/3 CAYLEY2x2 S110-SHAPE] {json.dumps(micro['cayley2x2_s110_shape_b8_t512_d384_bf16'])}", flush=True)

    full12 = _bench_v2_full_12l(device)
    print(f"  [3/3 V2 FULL-12L B=8 T=512] ratios={json.dumps(full12['ratios'])}", flush=True)
    for k in (
        "rope2d_ngpt", "eager_h7b", "holosphere_v2_sm86", "holosphere_v2_cayley_su2",
        "holosphere_v2_plus_cayley2x2_fused", "holosphere_v2_plus_cayley2x2_eager",
    ):
        print(f"    {k:36s} {json.dumps(full12[k])}", flush=True)

    smi_post = _query_gpu_snapshot()
    payload: Dict[str, Any] = {
        "schema": "holosphere.track_s114.v2_zero_permute_cayley_results.v1",
        "oracle_class": "anchor",
        "preregistration_sha256": PREREG_SHA256,
        "cu_sha256": ptxas_rec["cu_sha256"],
        "zero_spill_kernels": ptxas_rec["zero_spill_kernels"],
        "completed_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "torch_version": torch.__version__,
        "parity": parity,
        "microbench": micro,
        "full_12l_step": full12,
        "nvidia_smi_pre": smi_pre,
        "nvidia_smi_post": smi_post,
        "elapsed_seconds": round(time.monotonic() - t0, 3),
    }
    payload["result_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    out_bytes = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    out_path = _HERE / "s114_v2_gpu_results.json"
    out_path.write_bytes(out_bytes)
    os.chmod(out_path, 0o600)
    print(
        f"\n=== V2 COMPLETE: all_parity_pass={parity['summary']['all_v2_parity_pass']} "
        f"FILE={out_path.name} ({len(out_bytes)} B, file_sha256={hashlib.sha256(out_bytes).hexdigest()}, inner={payload['result_sha256']}) ===",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
