#!/usr/bin/env python3
"""Track S114 Unified Kernel-Isomorphic SiliSphere Operators & Autograd Bindings.

Exposes the exact unified ABI shared with silisphere/kernels/:
  - su2_holonomy_transport(q, k, v, omega, *, angle_scale=0.75, transport_v=False, eps=1e-6, backend="auto")
  - su2_inverse_untransport(o, pi_path, *, backend="auto")
  - fused_spherical_step(h, delta, alpha=None, *, mode="slerp"|"safe_hopf_loop"|"hopf_s3", phi=0.0, alpha_scale=0.45*pi, eps=1e-4, backend="auto")
  - safe_hopf_clock_angle(pass_idx, *, law="acute_cone"|"unaliased_coprime"|"pinned_train_step", r_max=8, r_train=3)
  - safe_hopf_clock(x, pass_idx, *, law="acute_cone"|"unaliased_coprime"|"pinned_train_step", r_max=8, r_train=3)

Dispatches cleanly across:
  1. "cuda"      -> Bare-metal sm_86 shared library (su2_holonomy_scan_sm86.cu, 0 B spills) via ctypes
  2. "triton"    -> Triton 3.9 fused associative scan + su(2) suffix backward (su2_holonomy_triton.py)
  3. "reference" -> Exact pure-PyTorch CPU/GPU implementation executing the IDENTICAL Lie-algebraic
                    su(2) additive-suffix-sum reverse-mode adjoint (verifiable in float64 via gradcheck).

Zero bare asserts; strict typed S114OpError on contract violations.
"""

from __future__ import annotations

import ctypes
import math
import os
from pathlib import Path
from typing import Any, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from su2_holonomy_triton import (
    TRITON_AVAILABLE,
    triton_su2_holonomy_bwd,
    triton_su2_holonomy_fwd,
)


class S114OpError(ValueError):
    """Fail-closed contract violation in Track S114 fused operators."""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise S114OpError(msg)


# ---------------------------------------------------------------------------
# Bare-Metal CUDA sm_86 ctypes Bridge (Lazy-Loaded ONLY When Requested on CUDA)
# ---------------------------------------------------------------------------

_CUDA_LIB: Optional[ctypes.CDLL] = None
_CUDA_LIB_TRIED = False


def _load_cuda_lib(lib_path: Optional[Path] = None) -> Optional[ctypes.CDLL]:
    global _CUDA_LIB, _CUDA_LIB_TRIED
    if lib_path is None and _CUDA_LIB_TRIED:
        return _CUDA_LIB
    candidates = []
    if lib_path is not None:
        candidates.append(lib_path)
    env_lib = os.environ.get("SILISPHERE_SM86_LIB")
    if env_lib:
        candidates.append(Path(env_lib))
    here = Path(__file__).resolve().parent
    candidates.extend(
        [
            here / "libsu2_holonomy_scan_sm86.so",
            here / "build" / "libsu2_holonomy_scan_sm86.so",
        ]
    )
    loaded: Optional[ctypes.CDLL] = None
    for cand in candidates:
        if cand.is_file():
            cdll = ctypes.CDLL(str(cand))
            _configure_cuda_signatures(cdll)
            loaded = cdll
            break
    if lib_path is None:
        _CUDA_LIB = loaded
        _CUDA_LIB_TRIED = True
    return loaded


def _configure_cuda_signatures(lib: ctypes.CDLL) -> None:
    vp = ctypes.c_void_p
    ci = ctypes.c_int
    ci64 = ctypes.c_int64
    cf = ctypes.c_float
    lib.silisphere_su2_holonomy_fwd_f32.argtypes = [
        vp, vp, vp, vp, vp, vp, vp, vp, ci, ci, cf, ci, cf, vp
    ]
    lib.silisphere_su2_holonomy_fwd_f32.restype = ci
    lib.silisphere_su2_holonomy_bwd_f32.argtypes = [
        vp, vp, vp, vp, vp, vp, vp, vp, vp, vp, vp, vp, vp, ci, ci, cf, ci, cf, vp
    ]
    lib.silisphere_su2_holonomy_bwd_f32.restype = ci
    lib.silisphere_su2_untransport_fwd_f32.argtypes = [vp, vp, vp, ci64, vp]
    lib.silisphere_su2_untransport_fwd_f32.restype = ci
    lib.silisphere_su2_untransport_bwd_f32.argtypes = [vp, vp, vp, vp, vp, ci64, vp]
    lib.silisphere_su2_untransport_bwd_f32.restype = ci
    lib.silisphere_spherical_slerp_hopf_fwd_f32.argtypes = [
        vp, vp, vp, vp, ci, ci, cf, cf, cf, cf, vp
    ]
    lib.silisphere_spherical_slerp_hopf_fwd_f32.restype = ci
    lib.silisphere_spherical_slerp_hopf_bwd_f32.argtypes = [
        vp, vp, vp, vp, vp, vp, vp, ci, ci, cf, cf, cf, cf, vp
    ]
    lib.silisphere_spherical_slerp_hopf_bwd_f32.restype = ci
    lib.silisphere_hopf_s3_residual_fwd_f32.argtypes = [vp, vp, vp, ci64, vp]
    lib.silisphere_hopf_s3_residual_fwd_f32.restype = ci
    lib.silisphere_hopf_s3_residual_bwd_f32.argtypes = [vp, vp, vp, vp, vp, ci64, vp]
    lib.silisphere_hopf_s3_residual_bwd_f32.restype = ci
    # V2 Zero-Permute Strided BHTD Holonomy (FP32 & BF16, su2_exp & cayley_su2)
    bhtd_fwd_args = [
        vp, vp, vp, vp, vp, vp, vp, vp,
        ci, ci, ci, ci,
        ci64, ci64, ci64, ci64, ci64, ci64,
        cf, ci, cf, vp,
    ]
    bhtd_bwd_args = [
        vp, vp, vp, vp, vp, vp, vp, vp, vp, vp, vp, vp, vp,
        ci, ci, ci, ci,
        ci64, ci64, ci64, ci64, ci64, ci64,
        cf, ci, cf, vp,
    ]
    for sfx in ("f32", "bf16", "cayley_f32", "cayley_bf16"):
        fwd_fn = getattr(lib, f"silisphere_su2_holonomy_bhtd_fwd_{sfx}", None)
        bwd_fn = getattr(lib, f"silisphere_su2_holonomy_bhtd_bwd_{sfx}", None)
        if fwd_fn is not None:
            fwd_fn.argtypes = bhtd_fwd_args
            fwd_fn.restype = ci
        if bwd_fn is not None:
            bwd_fn.argtypes = bhtd_bwd_args
            bwd_fn.restype = ci
    # V2 Direct-BF16 Spherical SLERP + Safe-Hopf
    if hasattr(lib, "silisphere_spherical_slerp_hopf_fwd_bf16"):
        lib.silisphere_spherical_slerp_hopf_fwd_bf16.argtypes = [
            vp, vp, vp, vp, ci, ci, cf, cf, cf, cf, vp
        ]
        lib.silisphere_spherical_slerp_hopf_fwd_bf16.restype = ci
        lib.silisphere_spherical_slerp_hopf_bwd_bf16.argtypes = [
            vp, vp, vp, vp, vp, vp, vp, ci, ci, cf, cf, cf, cf, vp
        ]
        lib.silisphere_spherical_slerp_hopf_bwd_bf16.restype = ci
    # V2 Beltrami Cayley2x2 & Fused Hopf-S^3 + Cayley2x2 (FP32 & BF16)
    for sfx in ("f32", "bf16"):
        for nm, args in (
            (f"holosphere_cayley2x2_fwd_{sfx}", [vp, vp, vp, ci64, vp]),
            (f"holosphere_cayley2x2_bwd_{sfx}", [vp, vp, vp, vp, vp, ci64, vp]),
            (f"holosphere_hopf_s3_cayley2x2_fwd_{sfx}", [vp, vp, vp, vp, ci64, vp]),
            (f"holosphere_hopf_s3_cayley2x2_bwd_{sfx}", [vp, vp, vp, vp, vp, vp, vp, ci64, vp]),
        ):
            fn = getattr(lib, nm, None)
            if fn is not None:
                fn.argtypes = args
                fn.restype = ci


def _ptr(t: Optional[torch.Tensor]) -> ctypes.c_void_p:
    return ctypes.c_void_p(0 if t is None else int(t.data_ptr()))


def _cuda_stream_ptr(device: torch.device) -> ctypes.c_void_p:
    return ctypes.c_void_p(int(torch.cuda.current_stream(device).cuda_stream))


def _resolve_backend(backend: str, is_cuda: bool, dtype: torch.dtype) -> str:
    _require(backend in ("auto", "cuda", "triton", "reference"), f"Unknown backend: {backend!r}")
    if backend == "reference":
        return "reference"
    if not is_cuda or dtype == torch.float64:
        if backend in ("cuda", "triton"):
            raise S114OpError(f"Backend {backend!r} requires CUDA float32/bfloat16/float16 tensors")
        return "reference"
    if backend == "cuda":
        _require(_load_cuda_lib() is not None, "libsu2_holonomy_scan_sm86.so not found")
        return "cuda"
    if backend == "triton":
        _require(TRITON_AVAILABLE, "Triton backend requested but triton is unavailable")
        return "triton"
    # auto on CUDA: prefer bare-metal sm_86 -> triton -> reference
    if _load_cuda_lib() is not None:
        return "cuda"
    if TRITON_AVAILABLE:
        return "triton"
    return "reference"


# ---------------------------------------------------------------------------
# Exact Quaternion & Lie-Algebra Reference Math (Works in FP32 and FP64!)
# ---------------------------------------------------------------------------


def quat_mul(p: torch.Tensor, q: torch.Tensor) -> torch.Tensor:
    pw, px, py, pz = p.unbind(dim=-1)
    qw, qx, qy, qz = q.unbind(dim=-1)
    return torch.stack(
        (
            pw * qw - px * qx - py * qy - pz * qz,
            pw * qx + px * qw + py * qz - pz * qy,
            pw * qy - px * qz + py * qw + pz * qx,
            pw * qz + px * qy - py * qx + pz * qw,
        ),
        dim=-1,
    )


def quat_conj(q: torch.Tensor) -> torch.Tensor:
    qw, qx, qy, qz = q.unbind(dim=-1)
    return torch.stack((qw, -qx, -qy, -qz), dim=-1)


def _safe_unit_norm(x: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    n2 = torch.sum(x * x, dim=-1, keepdim=True)
    return x * torch.rsqrt(torch.clamp(n2, min=eps * eps))


def _su2_exp_from_raw_ref(
    raw: torch.Tensor, angle_scale: float, use_tanh: bool, eps: float, map_mode: str = "exp"
) -> torch.Tensor:
    w = (angle_scale * torch.tanh(raw)) if use_tanh else raw
    if map_mode == "cayley":
        n2 = torch.sum(w * w, dim=-1, keepdim=True)
        inv_d = 1.0 / (1.0 + n2)
        return torch.cat(((1.0 - n2) * inv_d, (2.0 * inv_d) * w), dim=-1)
    th = torch.sqrt(torch.sum(w * w, dim=-1, keepdim=True) + (eps * eps))
    c = torch.cos(th)
    sinc = torch.sin(th) / th
    q0 = torch.cat((c, sinc * w), dim=-1)
    return _safe_unit_norm(q0, eps=eps)


def _su2_scan_ref_fwd(
    raw_f: torch.Tensor,
    q_f: Optional[torch.Tensor],
    k_f: Optional[torch.Tensor],
    v_f: Optional[torch.Tensor],
    angle_scale: float,
    use_tanh: bool,
    eps: float,
    map_mode: str = "exp",
) -> Tuple[torch.Tensor, Optional[torch.Tensor], Optional[torch.Tensor], Optional[torch.Tensor]]:
    """Exact Hillis-Steele right-accumulating prefix product U(t) = du_0 * ... * du_t on [F, T, ...]."""
    seq_len = raw_f.shape[1]
    cur = _su2_exp_from_raw_ref(raw_f, angle_scale, use_tanh, eps, map_mode=map_mode)
    offset = 1
    while offset < seq_len:
        prod = _safe_unit_norm(quat_mul(cur[:, :-offset], cur[:, offset:]), eps=eps)
        cur = torch.cat((cur[:, :offset], prod), dim=1)
        offset *= 2
    q_out = quat_mul(cur, q_f) if q_f is not None else None
    k_out = quat_mul(cur, k_f) if k_f is not None else None
    v_out = quat_mul(cur, v_f) if v_f is not None else None
    return cur, q_out, k_out, v_out


def _su2_scan_ref_bwd(
    raw_f: torch.Tensor,
    u_f: torch.Tensor,
    q_f: Optional[torch.Tensor],
    k_f: Optional[torch.Tensor],
    v_f: Optional[torch.Tensor],
    du_ext: Optional[torch.Tensor],
    dq_out: Optional[torch.Tensor],
    dk_out: Optional[torch.Tensor],
    dv_out: Optional[torch.Tensor],
    angle_scale: float,
    use_tanh: bool,
    eps: float,
    map_mode: str = "exp",
) -> Tuple[torch.Tensor, Optional[torch.Tensor], Optional[torch.Tensor], Optional[torch.Tensor]]:
    """Exact Lie-algebraic su(2) additive-suffix-sum backward mirroring su2_holonomy_scan_qkv_bwd_sm86."""
    u_c = quat_conj(u_f)
    g_u = torch.zeros_like(u_f) if du_ext is None else du_ext.clone()

    dq_in = dk_in = dv_in = None
    if q_f is not None and dq_out is not None:
        dq_in = quat_mul(u_c, dq_out)
        g_u = g_u + quat_mul(dq_out, quat_conj(q_f))
    if k_f is not None and dk_out is not None:
        dk_in = quat_mul(u_c, dk_out)
        g_u = g_u + quat_mul(dk_out, quat_conj(k_f))
    if v_f is not None and dv_out is not None:
        dv_in = quat_mul(u_c, dv_out)
        g_u = g_u + quat_mul(dv_out, quat_conj(v_f))

    # m_s = Im(g_s * conj(U_s)) in su(2) ~= R^3
    m_full = quat_mul(g_u, u_c)
    m_im = m_full[..., 1:]  # [F, T, 3]
    # Reverse additive suffix sum S_t = sum_{s=t}^{T-1} m_s
    s_im = torch.flip(torch.cumsum(torch.flip(m_im, dims=[1]), dim=1), dims=[1])
    s_quat = torch.cat((torch.zeros_like(s_im[..., :1]), s_im), dim=-1)
    u_bar = quat_mul(s_quat, u_f)

    # dL/d(du_t) = conj(U_{t-1}) * u_bar_t (and u_bar_0 at t=0)
    if u_f.shape[1] > 1:
        id_q = torch.zeros_like(u_f[:, :1])
        id_q[..., 0] = 1.0
        u_prev = torch.cat((id_q, u_f[:, :-1]), dim=1)
        g_du = quat_mul(quat_conj(u_prev), u_bar)
    else:
        g_du = u_bar

    # Chain g_du through cayley_su2(omega) or safe_unit_norm(su2_exp(omega))
    th_r = torch.tanh(raw_f) if use_tanh else None
    w = (angle_scale * th_r) if (use_tanh and th_r is not None) else raw_f
    if map_mode == "cayley":
        n2 = torch.sum(w * w, dim=-1, keepdim=True)
        two_d = 2.0 / (1.0 + n2)
        proj = g_du[..., :1] + torch.sum(g_du[..., 1:] * w, dim=-1, keepdim=True)
        d_w = two_d * (g_du[..., 1:] - (two_d * proj) * w)
    else:
        theta = torch.sqrt(torch.sum(w * w, dim=-1, keepdim=True) + (eps * eps))
        s_th = torch.sin(theta)
        c_th = torch.cos(theta)
        sinc = s_th / theta

        q0 = torch.cat((c_th, sinc * w), dim=-1)
        inv_q0 = torch.rsqrt(torch.clamp(torch.sum(q0 * q0, dim=-1, keepdim=True), min=eps * eps))
        du_u = q0 * inv_q0
        dot_g_du = torch.sum(g_du * du_u, dim=-1, keepdim=True)
        g_q0 = (g_du - dot_g_du * du_u) * inv_q0

        t2 = theta * theta
        taylor = -1.0 / 3.0 + t2 * (1.0 / 30.0 - t2 / 840.0)
        exact = (theta * c_th - s_th) / (theta * t2)
        dsinc_div_th = torch.where(theta < 1e-2, taylor, exact)
        dot_gv_w = torch.sum(g_q0[..., 1:] * w, dim=-1, keepdim=True)
        radial_coeff = -sinc * g_q0[..., :1] + dsinc_div_th * dot_gv_w
        d_w = sinc * g_q0[..., 1:] + radial_coeff * w
    d_raw = (d_w * angle_scale * (1.0 - th_r * th_r)) if (use_tanh and th_r is not None) else d_w
    return d_raw, dq_in, dk_in, dv_in


# ---------------------------------------------------------------------------
# Custom torch.autograd.Function Wrappers (CUDA / Triton / Exact Reference)
# ---------------------------------------------------------------------------


class _SU2HolonomyTransportFn(torch.autograd.Function):
    @staticmethod
    def forward(
        ctx: Any,
        raw_f: torch.Tensor,
        q_f: torch.Tensor,
        k_f: torch.Tensor,
        v_f: Optional[torch.Tensor],
        angle_scale: float,
        use_tanh: bool,
        eps: float,
        backend: str,
        map_mode: str = "exp",
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        # raw_f: [F, T, 3], q_f/k_f/(v_f): [F, T, 4]
        in_dtype = q_f.dtype
        work_dtype = torch.float64 if in_dtype == torch.float64 else torch.float32
        raw_w = raw_f.to(work_dtype).contiguous()
        q_w = q_f.to(work_dtype).contiguous()
        k_w = k_f.to(work_dtype).contiguous()
        v_w = v_f.to(work_dtype).contiguous() if v_f is not None else None
        has_v = v_w is not None

        if backend == "cuda" and map_mode == "exp":
            lib = _load_cuda_lib()
            _require(lib is not None, "CUDA library not loaded")
            n_fibers, seq_len, _ = raw_w.shape
            u_w = torch.empty((n_fibers, seq_len, 4), device=raw_w.device, dtype=torch.float32)
            qo_w = torch.empty_like(u_w)
            ko_w = torch.empty_like(u_w)
            vo_w = torch.empty_like(u_w) if has_v else None
            rc = lib.silisphere_su2_holonomy_fwd_f32(
                _ptr(raw_w), _ptr(q_w), _ptr(k_w), _ptr(v_w),
                _ptr(u_w), _ptr(qo_w), _ptr(ko_w), _ptr(vo_w),
                int(n_fibers), int(seq_len), float(angle_scale), int(1 if use_tanh else 0),
                float(eps), _cuda_stream_ptr(raw_w.device),
            )
            _require(rc == 0, f"silisphere_su2_holonomy_fwd_f32 failed with cudaError={rc}")
        elif backend == "triton" and map_mode == "exp":
            u_w, qo_w, ko_w, vo_w = triton_su2_holonomy_fwd(
                raw_w, q_w, k_w, v_w, angle_scale=angle_scale, use_tanh=use_tanh, eps=eps
            )
        else:
            u_w, qo_w, ko_w, vo_w = _su2_scan_ref_fwd(
                raw_w, q_w, k_w, v_w, angle_scale, use_tanh, eps, map_mode=map_mode
            )

        _require(qo_w is not None and ko_w is not None, "Q/K rotated outputs missing")
        ctx.angle_scale = angle_scale
        ctx.use_tanh = use_tanh
        ctx.eps = eps
        ctx.backend = backend
        ctx.map_mode = map_mode
        ctx.in_dtype = in_dtype
        ctx.has_v = has_v
        ctx.save_for_backward(raw_w, u_w, q_w, k_w, v_w if v_w is not None else torch.empty(0, device=raw_w.device))
        v_ret = vo_w.to(in_dtype) if vo_w is not None else torch.empty(0, device=raw_w.device, dtype=in_dtype)
        # Keep SU(2) holonomy path U in work_dtype (FP32/FP64) to preserve S^3 unit-norm invariant (<=1e-5) under BF16.
        return qo_w.to(in_dtype), ko_w.to(in_dtype), v_ret, u_w

    @staticmethod
    def backward(
        ctx: Any,
        dq_out: Optional[torch.Tensor],
        dk_out: Optional[torch.Tensor],
        dv_out: Optional[torch.Tensor],
        du_out: Optional[torch.Tensor],
    ) -> Tuple[Optional[torch.Tensor], ...]:
        raw_w, u_w, q_w, k_w, v_saved = ctx.saved_tensors
        v_w = v_saved if ctx.has_v else None
        work_dtype = raw_w.dtype
        dq_w = dq_out.to(work_dtype).contiguous() if dq_out is not None else torch.zeros_like(q_w)
        dk_w = dk_out.to(work_dtype).contiguous() if dk_out is not None else torch.zeros_like(k_w)
        dv_w = (
            dv_out.to(work_dtype).contiguous()
            if (ctx.has_v and dv_out is not None and dv_out.numel() > 0)
            else None
        )
        du_w = du_out.to(work_dtype).contiguous() if du_out is not None else None

        if ctx.backend == "cuda" and ctx.map_mode == "exp":
            lib = _load_cuda_lib()
            _require(lib is not None, "CUDA library not loaded")
            n_fibers, seq_len, _ = raw_w.shape
            d_raw = torch.empty_like(raw_w)
            dq_in = torch.empty_like(q_w)
            dk_in = torch.empty_like(k_w)
            dv_in = torch.empty_like(v_w) if (v_w is not None and dv_w is not None) else None
            rc = lib.silisphere_su2_holonomy_bwd_f32(
                _ptr(raw_w), _ptr(u_w), _ptr(q_w), _ptr(k_w), _ptr(v_w),
                _ptr(du_w), _ptr(dq_w), _ptr(dk_w), _ptr(dv_w),
                _ptr(d_raw), _ptr(dq_in), _ptr(dk_in), _ptr(dv_in),
                int(n_fibers), int(seq_len), float(ctx.angle_scale), int(1 if ctx.use_tanh else 0),
                float(ctx.eps), _cuda_stream_ptr(raw_w.device),
            )
            _require(rc == 0, f"silisphere_su2_holonomy_bwd_f32 failed with cudaError={rc}")
        elif ctx.backend == "triton" and ctx.map_mode == "exp":
            d_raw, dq_in, dk_in, dv_in = triton_su2_holonomy_bwd(
                raw_w, u_w, q_w, k_w, v_w, du_w, dq_w, dk_w, dv_w,
                angle_scale=ctx.angle_scale, use_tanh=ctx.use_tanh, eps=ctx.eps,
            )
        else:
            d_raw, dq_in, dk_in, dv_in = _su2_scan_ref_bwd(
                raw_w, u_w, q_w, k_w, v_w, du_w, dq_w, dk_w, dv_w,
                ctx.angle_scale, ctx.use_tanh, ctx.eps, map_mode=ctx.map_mode,
            )

        in_dtype = ctx.in_dtype
        return (
            d_raw.to(in_dtype),
            dq_in.to(in_dtype) if dq_in is not None else None,
            dk_in.to(in_dtype) if dk_in is not None else None,
            dv_in.to(in_dtype) if dv_in is not None else None,
            None,
            None,
            None,
            None,
            None,
        )


def _match_q4_layout(t: torch.Tensor, bsz: int, n_heads: int, seq_len: int, d_head: int) -> Tuple[torch.Tensor, bool]:
    """Allow zero-copy contiguous [B,H,T,D] OR zero-copy [B,T,H,D].transpose(1,2); else contiguous."""
    st = t.stride()
    if t.is_contiguous():
        return t, False
    if st == (seq_len * n_heads * d_head, d_head, n_heads * d_head, 1):
        return t, True
    return t.contiguous(), False


def _match_raw_layout(r: torch.Tensor, bsz: int, n_heads: int, seq_len: int, n_blocks: int) -> Tuple[torch.Tensor, bool]:
    """Allow zero-copy contiguous [B,H,T,nb,3] OR zero-copy [B,T,H,nb,3].transpose(1,2); else contiguous."""
    st = r.stride()
    if r.is_contiguous():
        return r, False
    if st == (seq_len * n_heads * n_blocks * 3, n_blocks * 3, n_heads * n_blocks * 3, 3, 1):
        return r, True
    return r.contiguous(), False


class _SU2HolonomyBHTDFn(torch.autograd.Function):
    """V2 Zero-Permute Direct FP32/BF16 BHTD Holonomy Scan (supports su2_exp & cayley_su2)."""

    @staticmethod
    def forward(
        ctx: Any,
        omega: torch.Tensor,
        q: torch.Tensor,
        k: torch.Tensor,
        v: Optional[torch.Tensor],
        angle_scale: float,
        use_tanh: bool,
        eps: float,
        map_mode: str,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        lib = _load_cuda_lib()
        _require(lib is not None, "CUDA library not loaded")
        bsz, n_heads, seq_len, d_head = q.shape
        n_blocks = d_head // 4
        in_dtype = q.dtype
        use_bf16 = (in_dtype == torch.bfloat16)
        io_dtype = torch.bfloat16 if use_bf16 else torch.float32

        q_io = q if q.dtype == io_dtype else q.to(io_dtype)
        k_io = k if k.dtype == io_dtype else k.to(io_dtype)
        v_io = (v if v.dtype == io_dtype else v.to(io_dtype)) if v is not None else None
        om_io = omega if omega.dtype == io_dtype else omega.to(io_dtype)

        q_io, q_tr = _match_q4_layout(q_io, bsz, n_heads, seq_len, d_head)
        k_io, k_tr = _match_q4_layout(k_io, bsz, n_heads, seq_len, d_head)
        v_tr = q_tr
        if v_io is not None:
            v_io, v_tr = _match_q4_layout(v_io, bsz, n_heads, seq_len, d_head)
        # Ensure q, k, (v) share one stride layout (typically all True from w_q/k/v or all False)
        if k_tr != q_tr or v_tr != q_tr:
            q_io, k_io = q_io.contiguous(), k_io.contiguous()
            if v_io is not None:
                v_io = v_io.contiguous()
            q_tr = False
        om_io, om_tr = _match_raw_layout(om_io, bsz, n_heads, seq_len, n_blocks)

        in_sb = q_io.stride(0) // 4
        in_sh = q_io.stride(1) // 4
        in_st = q_io.stride(2) // 4
        raw_sb = om_io.stride(0) // 3
        raw_sh = om_io.stride(1) // 3
        raw_st = om_io.stride(2) // 3

        u_out = torch.empty((bsz, n_heads, seq_len, n_blocks, 4), device=q_io.device, dtype=torch.float32)
        q_out = torch.empty((bsz, n_heads, seq_len, d_head), device=q_io.device, dtype=io_dtype)
        k_out = torch.empty((bsz, n_heads, seq_len, d_head), device=q_io.device, dtype=io_dtype)
        v_out = torch.empty((bsz, n_heads, seq_len, d_head), device=q_io.device, dtype=io_dtype) if v_io is not None else None

        sfx = ("cayley_" if map_mode == "cayley" else "") + ("bf16" if use_bf16 else "f32")
        fwd_fn = getattr(lib, f"silisphere_su2_holonomy_bhtd_fwd_{sfx}")
        rc = fwd_fn(
            _ptr(om_io), _ptr(q_io), _ptr(k_io), _ptr(v_io),
            _ptr(u_out), _ptr(q_out), _ptr(k_out), _ptr(v_out),
            int(bsz), int(n_heads), int(seq_len), int(n_blocks),
            int(in_sb), int(in_sh), int(in_st),
            int(raw_sb), int(raw_sh), int(raw_st),
            float(angle_scale), int(1 if use_tanh else 0), float(eps),
            _cuda_stream_ptr(q_io.device),
        )
        _require(rc == 0, f"silisphere_su2_holonomy_bhtd_fwd_{sfx} failed: {rc}")

        ctx.angle_scale = angle_scale
        ctx.use_tanh = use_tanh
        ctx.eps = eps
        ctx.map_mode = map_mode
        ctx.in_dtype = in_dtype
        ctx.io_dtype = io_dtype
        ctx.use_bf16 = use_bf16
        ctx.has_v = v_io is not None
        ctx.q_tr = q_tr
        ctx.om_tr = om_tr
        ctx.strides = (in_sb, in_sh, in_st, raw_sb, raw_sh, raw_st)
        ctx.save_for_backward(om_io, u_out, q_io, k_io, v_io if v_io is not None else torch.empty(0, device=q_io.device))
        v_ret = v_out if v_out is not None else torch.empty(0, device=q_io.device, dtype=io_dtype)
        return q_out.to(in_dtype), k_out.to(in_dtype), v_ret.to(in_dtype), u_out

    @staticmethod
    def backward(
        ctx: Any,
        dq_out: Optional[torch.Tensor],
        dk_out: Optional[torch.Tensor],
        dv_out: Optional[torch.Tensor],
        du_out: Optional[torch.Tensor],
    ) -> Tuple[Optional[torch.Tensor], ...]:
        lib = _load_cuda_lib()
        _require(lib is not None, "CUDA library not loaded")
        om_io, u_out, q_io, k_io, v_saved = ctx.saved_tensors
        v_io = v_saved if ctx.has_v else None
        bsz, n_heads, seq_len, d_head = q_io.shape
        n_blocks = d_head // 4
        io_dtype = ctx.io_dtype
        in_sb, in_sh, in_st, raw_sb, raw_sh, raw_st = ctx.strides

        dq_o = dq_out.to(io_dtype).contiguous() if dq_out is not None else torch.zeros((bsz, n_heads, seq_len, d_head), device=q_io.device, dtype=io_dtype)
        dk_o = dk_out.to(io_dtype).contiguous() if dk_out is not None else torch.zeros((bsz, n_heads, seq_len, d_head), device=q_io.device, dtype=io_dtype)
        dv_o = dv_out.to(io_dtype).contiguous() if (ctx.has_v and dv_out is not None and dv_out.numel() > 0) else None
        du_e = du_out.to(torch.float32).contiguous() if du_out is not None else None

        # Allocate input grads in the EXACT input memory layout (zero-copy into w_q/k/v/omega backward GEMMs!)
        if ctx.q_tr:
            dq_in = torch.empty((bsz, seq_len, n_heads, d_head), device=q_io.device, dtype=io_dtype).transpose(1, 2)
            dk_in = torch.empty((bsz, seq_len, n_heads, d_head), device=q_io.device, dtype=io_dtype).transpose(1, 2)
            dv_in = torch.empty((bsz, seq_len, n_heads, d_head), device=q_io.device, dtype=io_dtype).transpose(1, 2) if (v_io is not None and dv_o is not None) else None
        else:
            dq_in = torch.empty((bsz, n_heads, seq_len, d_head), device=q_io.device, dtype=io_dtype)
            dk_in = torch.empty((bsz, n_heads, seq_len, d_head), device=q_io.device, dtype=io_dtype)
            dv_in = torch.empty((bsz, n_heads, seq_len, d_head), device=q_io.device, dtype=io_dtype) if (v_io is not None and dv_o is not None) else None
        if ctx.om_tr:
            d_raw = torch.empty((bsz, seq_len, n_heads, n_blocks, 3), device=q_io.device, dtype=io_dtype).transpose(1, 2)
        else:
            d_raw = torch.empty((bsz, n_heads, seq_len, n_blocks, 3), device=q_io.device, dtype=io_dtype)

        sfx = ("cayley_" if ctx.map_mode == "cayley" else "") + ("bf16" if ctx.use_bf16 else "f32")
        bwd_fn = getattr(lib, f"silisphere_su2_holonomy_bhtd_bwd_{sfx}")
        rc = bwd_fn(
            _ptr(om_io), _ptr(u_out), _ptr(q_io), _ptr(k_io), _ptr(v_io),
            _ptr(du_e), _ptr(dq_o), _ptr(dk_o), _ptr(dv_o),
            _ptr(d_raw), _ptr(dq_in), _ptr(dk_in), _ptr(dv_in),
            int(bsz), int(n_heads), int(seq_len), int(n_blocks),
            int(in_sb), int(in_sh), int(in_st),
            int(raw_sb), int(raw_sh), int(raw_st),
            float(ctx.angle_scale), int(1 if ctx.use_tanh else 0), float(ctx.eps),
            _cuda_stream_ptr(q_io.device),
        )
        _require(rc == 0, f"silisphere_su2_holonomy_bhtd_bwd_{sfx} failed: {rc}")

        in_dtype = ctx.in_dtype
        return (
            d_raw if d_raw.dtype == in_dtype else d_raw.to(in_dtype),
            dq_in if dq_in.dtype == in_dtype else dq_in.to(in_dtype),
            dk_in if dk_in.dtype == in_dtype else dk_in.to(in_dtype),
            (dv_in if dv_in.dtype == in_dtype else dv_in.to(in_dtype)) if dv_in is not None else None,
            None,
            None,
            None,
            None,
        )


class _SU2InverseUntransportFn(torch.autograd.Function):
    @staticmethod
    def forward(
        ctx: Any, o_q: torch.Tensor, pi_q: torch.Tensor, backend: str
    ) -> torch.Tensor:
        in_dtype = o_q.dtype
        work_dtype = torch.float64 if in_dtype == torch.float64 else torch.float32
        o_w = o_q.to(work_dtype).contiguous()
        u_w = pi_q.to(work_dtype).contiguous()
        if backend == "cuda":
            lib = _load_cuda_lib()
            _require(lib is not None, "CUDA library not loaded")
            out_w = torch.empty_like(o_w)
            n_quads = o_w.numel() // 4
            rc = lib.silisphere_su2_untransport_fwd_f32(
                _ptr(u_w), _ptr(o_w), _ptr(out_w), int(n_quads), _cuda_stream_ptr(o_w.device)
            )
            _require(rc == 0, f"silisphere_su2_untransport_fwd_f32 failed: {rc}")
        else:
            out_w = quat_mul(quat_conj(u_w), o_w)
        ctx.backend = backend
        ctx.in_dtype = in_dtype
        ctx.save_for_backward(o_w, u_w)
        return out_w.to(in_dtype)

    @staticmethod
    def backward(ctx: Any, do_out: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, None]:
        o_w, u_w = ctx.saved_tensors
        work_dtype = o_w.dtype
        do_w = do_out.to(work_dtype).contiguous()
        if ctx.backend == "cuda":
            lib = _load_cuda_lib()
            _require(lib is not None, "CUDA library not loaded")
            do_in = torch.empty_like(o_w)
            du_out = torch.empty_like(u_w)
            n_quads = o_w.numel() // 4
            rc = lib.silisphere_su2_untransport_bwd_f32(
                _ptr(u_w), _ptr(o_w), _ptr(do_w), _ptr(do_in), _ptr(du_out),
                int(n_quads), _cuda_stream_ptr(o_w.device),
            )
            _require(rc == 0, f"silisphere_su2_untransport_bwd_f32 failed: {rc}")
        else:
            do_in = quat_mul(u_w, do_w)
            du_out = quat_mul(o_w, quat_conj(do_w))
        return do_in.to(ctx.in_dtype), du_out.to(ctx.in_dtype), None


class _HopfS3ResidualFn(torch.autograd.Function):
    @staticmethod
    def forward(ctx: Any, h: torch.Tensor, delta: torch.Tensor, backend: str) -> torch.Tensor:
        in_dtype = h.dtype
        work_dtype = torch.float64 if in_dtype == torch.float64 else torch.float32
        h_w = h.to(work_dtype).contiguous()
        d_w = delta.to(work_dtype).contiguous()
        if backend == "cuda":
            lib = _load_cuda_lib()
            _require(lib is not None, "CUDA library not loaded")
            out_w = torch.empty_like(h_w)
            rc = lib.silisphere_hopf_s3_residual_fwd_f32(
                _ptr(h_w), _ptr(d_w), _ptr(out_w), int(h_w.numel() // 4), _cuda_stream_ptr(h_w.device)
            )
            _require(rc == 0, f"silisphere_hopf_s3_residual_fwd_f32 failed: {rc}")
        else:
            sh = h_w.shape
            hq = h_w.reshape(-1, 4)
            dq = d_w.reshape(-1, 4)
            inv_u = torch.rsqrt(1.0 + torch.sum(dq[:, 1:] * dq[:, 1:], dim=-1, keepdim=True))
            u = torch.cat((inv_u, dq[:, 1:] * inv_u), dim=-1)
            g = torch.exp(torch.tanh(dq[:, :1]))
            out_w = (g * quat_mul(u, hq)).reshape(sh)
        ctx.backend = backend
        ctx.in_dtype = in_dtype
        ctx.save_for_backward(h_w, d_w)
        return out_w.to(in_dtype)

    @staticmethod
    def backward(ctx: Any, grad_out: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, None]:
        h_w, d_w = ctx.saved_tensors
        go_w = grad_out.to(h_w.dtype).contiguous()
        if ctx.backend == "cuda":
            lib = _load_cuda_lib()
            _require(lib is not None, "CUDA library not loaded")
            gh = torch.empty_like(h_w)
            gd = torch.empty_like(d_w)
            rc = lib.silisphere_hopf_s3_residual_bwd_f32(
                _ptr(h_w), _ptr(d_w), _ptr(go_w), _ptr(gh), _ptr(gd),
                int(h_w.numel() // 4), _cuda_stream_ptr(h_w.device),
            )
            _require(rc == 0, f"silisphere_hopf_s3_residual_bwd_f32 failed: {rc}")
        else:
            sh = h_w.shape
            hq = h_w.reshape(-1, 4)
            dq = d_w.reshape(-1, 4)
            goq = go_w.reshape(-1, 4)
            inv_u = torch.rsqrt(1.0 + torch.sum(dq[:, 1:] * dq[:, 1:], dim=-1, keepdim=True))
            u = torch.cat((inv_u, dq[:, 1:] * inv_u), dim=-1)
            th0 = torch.tanh(dq[:, :1])
            g = torch.exp(th0)
            prod = quat_mul(u, hq)
            dg = torch.sum(goq * prod, dim=-1, keepdim=True)
            dd0 = dg * g * (1.0 - th0 * th0)
            g_prod = g * goq
            gh = quat_mul(quat_conj(u), g_prod).reshape(sh)
            gu = quat_mul(g_prod, quat_conj(hq))
            dot_gu_u = torch.sum(gu * u, dim=-1, keepdim=True)
            gd_xyz = (gu[:, 1:] - dot_gu_u * u[:, 1:]) * inv_u
            gd = torch.cat((dd0, gd_xyz), dim=-1).reshape(sh)
        return gh.to(ctx.in_dtype), gd.to(ctx.in_dtype), None


def _hopf_rotate_tensor(x: torch.Tensor, cos_phi: float, sin_phi: float) -> torch.Tensor:
    if sin_phi == 0.0 and cos_phi == 1.0:
        return x
    sh = x.shape
    b = x.reshape(*sh[:-1], sh[-1] // 4, 4)
    a, bx, u, v = b.unbind(dim=-1)
    return torch.stack(
        (a * cos_phi - bx * sin_phi, a * sin_phi + bx * cos_phi, u * cos_phi + v * sin_phi, -u * sin_phi + v * cos_phi),
        dim=-1,
    ).reshape(sh)


def _hopf_rotate_tensor_t(g: torch.Tensor, cos_phi: float, sin_phi: float) -> torch.Tensor:
    if sin_phi == 0.0 and cos_phi == 1.0:
        return g
    sh = g.shape
    b = g.reshape(*sh[:-1], sh[-1] // 4, 4)
    a, bx, u, v = b.unbind(dim=-1)
    return torch.stack(
        (a * cos_phi + bx * sin_phi, -a * sin_phi + bx * cos_phi, u * cos_phi - v * sin_phi, u * sin_phi + v * cos_phi),
        dim=-1,
    ).reshape(sh)


class _FusedSphericalSlerpHopfFn(torch.autograd.Function):
    @staticmethod
    def forward(
        ctx: Any,
        h: torch.Tensor,
        delta: torch.Tensor,
        alpha_logit: torch.Tensor,
        alpha_scale: float,
        cos_phi: float,
        sin_phi: float,
        eps: float,
        backend: str,
    ) -> torch.Tensor:
        in_dtype = h.dtype
        al_dtype = alpha_logit.dtype
        sh = h.shape
        d_model = sh[-1]
        use_bf16_io = (
            backend == "cuda"
            and in_dtype == torch.bfloat16
            and delta.dtype == torch.bfloat16
            and hasattr(_load_cuda_lib(), "silisphere_spherical_slerp_hopf_fwd_bf16")
        )
        if use_bf16_io:
            lib = _load_cuda_lib()
            _require(lib is not None, "CUDA library not loaded")
            h2d = h.reshape(-1, d_model).contiguous()
            d2d = delta.reshape(-1, d_model).contiguous()
            al1d = alpha_logit.to(torch.float32).reshape(d_model).contiguous()
            out2d = torch.empty_like(h2d)
            rc = lib.silisphere_spherical_slerp_hopf_fwd_bf16(
                _ptr(h2d), _ptr(d2d), _ptr(al1d), _ptr(out2d),
                int(h2d.shape[0]), int(d_model), float(alpha_scale),
                float(cos_phi), float(sin_phi), float(eps), _cuda_stream_ptr(h2d.device),
            )
            _require(rc == 0, f"silisphere_spherical_slerp_hopf_fwd_bf16 failed: {rc}")
        else:
            work_dtype = torch.float64 if in_dtype == torch.float64 else torch.float32
            h2d = h.to(work_dtype).reshape(-1, d_model).contiguous()
            d2d = delta.to(work_dtype).reshape(-1, d_model).contiguous()
            al1d = alpha_logit.to(work_dtype).reshape(d_model).contiguous()
            if backend == "cuda":
                lib = _load_cuda_lib()
                _require(lib is not None, "CUDA library not loaded")
                out2d = torch.empty_like(h2d)
                rc = lib.silisphere_spherical_slerp_hopf_fwd_f32(
                    _ptr(h2d), _ptr(d2d), _ptr(al1d), _ptr(out2d),
                    int(h2d.shape[0]), int(d_model), float(alpha_scale),
                    float(cos_phi), float(sin_phi), float(eps), _cuda_stream_ptr(h2d.device),
                )
                _require(rc == 0, f"silisphere_spherical_slerp_hopf_fwd_f32 failed: {rc}")
            else:
                h_u = _safe_unit_norm(h2d, eps=eps)
                d_rot = _hopf_rotate_tensor(d2d, cos_phi, sin_phi)
                d_u = _safe_unit_norm(d_rot, eps=eps)
                alpha = alpha_scale * torch.sigmoid(al1d).unsqueeze(0)
                mixed = torch.cos(alpha) * h_u + torch.sin(alpha) * d_u
                denom = torch.sqrt(torch.sum(mixed * mixed, dim=-1, keepdim=True) + (eps * eps))
                out2d = mixed / denom

        ctx.alpha_scale = alpha_scale
        ctx.cos_phi = cos_phi
        ctx.sin_phi = sin_phi
        ctx.eps = eps
        ctx.backend = backend
        ctx.use_bf16_io = use_bf16_io
        ctx.in_dtype = in_dtype
        ctx.al_dtype = al_dtype
        ctx.orig_shape = sh
        ctx.save_for_backward(h2d, d2d, al1d)
        return out2d.reshape(sh) if out2d.dtype == in_dtype else out2d.reshape(sh).to(in_dtype)

    @staticmethod
    def backward(ctx: Any, grad_out: torch.Tensor) -> Tuple[Any, ...]:
        h2d, d2d, al1d = ctx.saved_tensors
        d_model = h2d.shape[-1]
        if ctx.use_bf16_io:
            lib = _load_cuda_lib()
            _require(lib is not None, "CUDA library not loaded")
            go2d = grad_out.to(torch.bfloat16).reshape(-1, d_model).contiguous()
            gh2d = torch.empty_like(h2d)
            gd2d = torch.empty_like(d2d)
            gal1d = torch.zeros_like(al1d)
            rc = lib.silisphere_spherical_slerp_hopf_bwd_bf16(
                _ptr(h2d), _ptr(d2d), _ptr(al1d), _ptr(go2d),
                _ptr(gh2d), _ptr(gd2d), _ptr(gal1d),
                int(h2d.shape[0]), int(d_model), float(ctx.alpha_scale),
                float(ctx.cos_phi), float(ctx.sin_phi), float(ctx.eps),
                _cuda_stream_ptr(h2d.device),
            )
            _require(rc == 0, f"silisphere_spherical_slerp_hopf_bwd_bf16 failed: {rc}")
        else:
            go2d = grad_out.to(h2d.dtype).reshape(-1, d_model).contiguous()
            if ctx.backend == "cuda":
                lib = _load_cuda_lib()
                _require(lib is not None, "CUDA library not loaded")
                gh2d = torch.empty_like(h2d)
                gd2d = torch.empty_like(d2d)
                gal1d = torch.zeros_like(al1d)
                rc = lib.silisphere_spherical_slerp_hopf_bwd_f32(
                    _ptr(h2d), _ptr(d2d), _ptr(al1d), _ptr(go2d),
                    _ptr(gh2d), _ptr(gd2d), _ptr(gal1d),
                    int(h2d.shape[0]), int(d_model), float(ctx.alpha_scale),
                    float(ctx.cos_phi), float(ctx.sin_phi), float(ctx.eps),
                    _cuda_stream_ptr(h2d.device),
                )
                _require(rc == 0, f"silisphere_spherical_slerp_hopf_bwd_f32 failed: {rc}")
            else:
                eps = ctx.eps
                h2 = torch.sum(h2d * h2d, dim=-1, keepdim=True)
                d2 = torch.sum(d2d * d2d, dim=-1, keepdim=True)
                inv_h = torch.rsqrt(torch.clamp(h2, min=eps * eps))
                inv_d = torch.rsqrt(torch.clamp(d2, min=eps * eps))
                h_u = h2d * inv_h
                d_rot = _hopf_rotate_tensor(d2d, ctx.cos_phi, ctx.sin_phi)
                d_u = d_rot * inv_d
                sig = torch.sigmoid(al1d).unsqueeze(0)
                alpha = ctx.alpha_scale * sig
                ca, sa = torch.cos(alpha), torch.sin(alpha)
                mixed = ca * h_u + sa * d_u
                m2 = torch.sum(mixed * mixed, dim=-1, keepdim=True)
                m_active = m2 > (eps * eps)
                inv_m = torch.where(m_active, torch.rsqrt(m2 + eps * eps), torch.zeros_like(m2))
                dot_go_m = torch.sum(go2d * mixed, dim=-1, keepdim=True)
                g_mixed = torch.where(
                    m_active,
                    go2d * inv_m - (dot_go_m * (inv_m * inv_m * inv_m)) * mixed,
                    torch.zeros_like(go2d),
                )

                g_hu = g_mixed * ca
                g_du = g_mixed * sa
                ch = torch.where(h2 > eps * eps, torch.sum(g_hu * h_u, dim=-1, keepdim=True), torch.zeros_like(h2))
                cd = torch.where(d2 > eps * eps, torch.sum(g_du * d_u, dim=-1, keepdim=True), torch.zeros_like(d2))
                gh2d = (g_hu - ch * h_u) * inv_h
                gd_rot = (g_du - cd * d_u) * inv_d
                gd2d = _hopf_rotate_tensor_t(gd_rot, ctx.cos_phi, ctx.sin_phi)
                g_alpha = g_mixed * (-sa * h_u + ca * d_u)
                gal1d = torch.sum(g_alpha * ctx.alpha_scale * sig * (1.0 - sig), dim=0)

        return (
            gh2d.reshape(ctx.orig_shape) if gh2d.dtype == ctx.in_dtype else gh2d.reshape(ctx.orig_shape).to(ctx.in_dtype),
            gd2d.reshape(ctx.orig_shape) if gd2d.dtype == ctx.in_dtype else gd2d.reshape(ctx.orig_shape).to(ctx.in_dtype),
            gal1d if gal1d.dtype == ctx.al_dtype else gal1d.to(ctx.al_dtype),
            None,
            None,
            None,
            None,
            None,
        )


def _reduce_broadcast_grad(grad: torch.Tensor, target_shape: Tuple[int, ...]) -> torch.Tensor:
    out = grad
    while out.ndim > len(target_shape):
        out = out.sum(dim=0)
    for dim, size in enumerate(target_shape):
        if size == 1 and out.shape[dim] != 1:
            out = out.sum(dim=dim, keepdim=True)
    return out


class _Cayley2x2Fn(torch.autograd.Function):
    """V2 Beltrami [C, K] = 0 2x2 Block-Diagonal Cayley SO(d) Rotation (FP64/FP32/BF16)."""

    @staticmethod
    def forward(ctx: Any, x: torch.Tensor, omega: torch.Tensor, backend: str) -> torch.Tensor:
        in_dtype = x.dtype
        om_dtype = omega.dtype
        om_orig_shape = tuple(omega.shape)
        n_pairs = x.shape[-1] // 2
        om_full = omega.expand(*x.shape[:-1], n_pairs)
        use_bf16_io = (
            backend == "cuda"
            and in_dtype == torch.bfloat16
            and hasattr(_load_cuda_lib(), "holosphere_cayley2x2_fwd_bf16")
        )
        if use_bf16_io:
            lib = _load_cuda_lib()
            _require(lib is not None, "CUDA library not loaded")
            x_w = x.contiguous()
            om_w = om_full.to(torch.bfloat16).contiguous()
            y_w = torch.empty_like(x_w)
            rc = lib.holosphere_cayley2x2_fwd_bf16(
                _ptr(x_w), _ptr(om_w), _ptr(y_w), int(x_w.numel() // 4), _cuda_stream_ptr(x_w.device)
            )
            _require(rc == 0, f"holosphere_cayley2x2_fwd_bf16 failed: {rc}")
        else:
            work_dtype = torch.float64 if (in_dtype == torch.float64 or om_dtype == torch.float64) else torch.float32
            x_w = x.to(work_dtype).contiguous()
            om_w = om_full.to(work_dtype).contiguous()
            if backend == "cuda":
                lib = _load_cuda_lib()
                _require(lib is not None, "CUDA library not loaded")
                y_w = torch.empty_like(x_w)
                rc = lib.holosphere_cayley2x2_fwd_f32(
                    _ptr(x_w), _ptr(om_w), _ptr(y_w), int(x_w.numel() // 4), _cuda_stream_ptr(x_w.device)
                )
                _require(rc == 0, f"holosphere_cayley2x2_fwd_f32 failed: {rc}")
            else:
                xp = x_w.reshape(*x_w.shape[:-1], n_pairs, 2)
                w2 = om_w * om_w
                inv_d = 1.0 / (1.0 + w2)
                c = (1.0 - w2) * inv_d
                s = (2.0 * om_w) * inv_d
                x0, x1 = xp.unbind(dim=-1)
                y_w = torch.stack((c * x0 + s * x1, -s * x0 + c * x1), dim=-1).reshape_as(x_w)

        ctx.backend = backend
        ctx.use_bf16_io = use_bf16_io
        ctx.in_dtype = in_dtype
        ctx.om_dtype = om_dtype
        ctx.om_orig_shape = om_orig_shape
        ctx.save_for_backward(x_w, om_w)
        return y_w if y_w.dtype == in_dtype else y_w.to(in_dtype)

    @staticmethod
    def backward(ctx: Any, grad_y: torch.Tensor) -> Tuple[Optional[torch.Tensor], Optional[torch.Tensor], None]:
        x_w, om_w = ctx.saved_tensors
        gy_w = grad_y.to(x_w.dtype).contiguous()
        if ctx.use_bf16_io:
            lib = _load_cuda_lib()
            _require(lib is not None, "CUDA library not loaded")
            gx_w = torch.empty_like(x_w)
            gw_full = torch.empty_like(om_w)
            rc = lib.holosphere_cayley2x2_bwd_bf16(
                _ptr(x_w), _ptr(om_w), _ptr(gy_w), _ptr(gx_w), _ptr(gw_full),
                int(x_w.numel() // 4), _cuda_stream_ptr(x_w.device),
            )
            _require(rc == 0, f"holosphere_cayley2x2_bwd_bf16 failed: {rc}")
        elif ctx.backend == "cuda":
            lib = _load_cuda_lib()
            _require(lib is not None, "CUDA library not loaded")
            gx_w = torch.empty_like(x_w)
            gw_full = torch.empty_like(om_w)
            rc = lib.holosphere_cayley2x2_bwd_f32(
                _ptr(x_w), _ptr(om_w), _ptr(gy_w), _ptr(gx_w), _ptr(gw_full),
                int(x_w.numel() // 4), _cuda_stream_ptr(x_w.device),
            )
            _require(rc == 0, f"holosphere_cayley2x2_bwd_f32 failed: {rc}")
        else:
            n_pairs = x_w.shape[-1] // 2
            xp = x_w.reshape(*x_w.shape[:-1], n_pairs, 2)
            gp = gy_w.reshape(*gy_w.shape[:-1], n_pairs, 2)
            w2 = om_w * om_w
            inv_d = 1.0 / (1.0 + w2)
            c = (1.0 - w2) * inv_d
            s = (2.0 * om_w) * inv_d
            x0, x1 = xp.unbind(dim=-1)
            g0, g1 = gp.unbind(dim=-1)
            gx_w = torch.stack((c * g0 - s * g1, s * g0 + c * g1), dim=-1).reshape_as(x_w)
            y0 = c * x0 + s * x1
            y1 = -s * x0 + c * x1
            gw_full = (2.0 * inv_d) * (g0 * y1 - g1 * y0)

        gw = _reduce_broadcast_grad(gw_full.float() if ctx.use_bf16_io else gw_full, ctx.om_orig_shape)
        return (
            gx_w if gx_w.dtype == ctx.in_dtype else gx_w.to(ctx.in_dtype),
            gw if gw.dtype == ctx.om_dtype else gw.to(ctx.om_dtype),
            None,
        )


class _HopfS3Cayley2x2Fn(torch.autograd.Function):
    """V2 Zero-HBM-Epilogue Fused Hopf-S^3 Residual + Beltrami Cayley2x2 Rotation."""

    @staticmethod
    def forward(ctx: Any, h: torch.Tensor, delta: torch.Tensor, omega: torch.Tensor, backend: str) -> torch.Tensor:
        in_dtype = h.dtype
        om_dtype = omega.dtype
        om_orig_shape = tuple(omega.shape)
        n_pairs = h.shape[-1] // 2
        om_full = omega.expand(*h.shape[:-1], n_pairs)
        use_bf16_io = (
            backend == "cuda"
            and in_dtype == torch.bfloat16
            and delta.dtype == torch.bfloat16
            and hasattr(_load_cuda_lib(), "holosphere_hopf_s3_cayley2x2_fwd_bf16")
        )
        if use_bf16_io:
            lib = _load_cuda_lib()
            _require(lib is not None, "CUDA library not loaded")
            h_w = h.contiguous()
            d_w = delta.contiguous()
            om_w = om_full.to(torch.bfloat16).contiguous()
            out_w = torch.empty_like(h_w)
            rc = lib.holosphere_hopf_s3_cayley2x2_fwd_bf16(
                _ptr(h_w), _ptr(d_w), _ptr(om_w), _ptr(out_w),
                int(h_w.numel() // 4), _cuda_stream_ptr(h_w.device),
            )
            _require(rc == 0, f"holosphere_hopf_s3_cayley2x2_fwd_bf16 failed: {rc}")
        else:
            work_dtype = torch.float64 if (in_dtype == torch.float64 or om_dtype == torch.float64) else torch.float32
            h_w = h.to(work_dtype).contiguous()
            d_w = delta.to(work_dtype).contiguous()
            om_w = om_full.to(work_dtype).contiguous()
            if backend == "cuda":
                lib = _load_cuda_lib()
                _require(lib is not None, "CUDA library not loaded")
                out_w = torch.empty_like(h_w)
                rc = lib.holosphere_hopf_s3_cayley2x2_fwd_f32(
                    _ptr(h_w), _ptr(d_w), _ptr(om_w), _ptr(out_w),
                    int(h_w.numel() // 4), _cuda_stream_ptr(h_w.device),
                )
                _require(rc == 0, f"holosphere_hopf_s3_cayley2x2_fwd_f32 failed: {rc}")
            else:
                sh = h_w.shape
                hq, dq = h_w.reshape(-1, 4), d_w.reshape(-1, 4)
                inv_u = torch.rsqrt(1.0 + torch.sum(dq[:, 1:] * dq[:, 1:], dim=-1, keepdim=True))
                u = torch.cat((inv_u, dq[:, 1:] * inv_u), dim=-1)
                g_sc = torch.exp(torch.tanh(dq[:, :1]))
                z = (g_sc * quat_mul(u, hq)).reshape(*sh[:-1], n_pairs, 2)
                w2 = om_w * om_w
                inv_d = 1.0 / (1.0 + w2)
                c, s = (1.0 - w2) * inv_d, (2.0 * om_w) * inv_d
                z0, z1 = z.unbind(dim=-1)
                out_w = torch.stack((c * z0 + s * z1, -s * z0 + c * z1), dim=-1).reshape(sh)

        ctx.backend = backend
        ctx.use_bf16_io = use_bf16_io
        ctx.in_dtype = in_dtype
        ctx.om_dtype = om_dtype
        ctx.om_orig_shape = om_orig_shape
        ctx.save_for_backward(h_w, d_w, om_w)
        return out_w if out_w.dtype == in_dtype else out_w.to(in_dtype)

    @staticmethod
    def backward(ctx: Any, grad_out: torch.Tensor) -> Tuple[Optional[torch.Tensor], Optional[torch.Tensor], Optional[torch.Tensor], None]:
        h_w, d_w, om_w = ctx.saved_tensors
        go_w = grad_out.to(h_w.dtype).contiguous()
        if ctx.use_bf16_io:
            lib = _load_cuda_lib()
            _require(lib is not None, "CUDA library not loaded")
            gh_w = torch.empty_like(h_w)
            gd_w = torch.empty_like(d_w)
            gw_full = torch.empty_like(om_w)
            rc = lib.holosphere_hopf_s3_cayley2x2_bwd_bf16(
                _ptr(h_w), _ptr(d_w), _ptr(om_w), _ptr(go_w),
                _ptr(gh_w), _ptr(gd_w), _ptr(gw_full),
                int(h_w.numel() // 4), _cuda_stream_ptr(h_w.device),
            )
            _require(rc == 0, f"holosphere_hopf_s3_cayley2x2_bwd_bf16 failed: {rc}")
        elif ctx.backend == "cuda":
            lib = _load_cuda_lib()
            _require(lib is not None, "CUDA library not loaded")
            gh_w = torch.empty_like(h_w)
            gd_w = torch.empty_like(d_w)
            gw_full = torch.empty_like(om_w)
            rc = lib.holosphere_hopf_s3_cayley2x2_bwd_f32(
                _ptr(h_w), _ptr(d_w), _ptr(om_w), _ptr(go_w),
                _ptr(gh_w), _ptr(gd_w), _ptr(gw_full),
                int(h_w.numel() // 4), _cuda_stream_ptr(h_w.device),
            )
            _require(rc == 0, f"holosphere_hopf_s3_cayley2x2_bwd_f32 failed: {rc}")
        else:
            sh = h_w.shape
            n_pairs = sh[-1] // 2
            hq, dq = h_w.reshape(-1, 4), d_w.reshape(-1, 4)
            inv_u = torch.rsqrt(1.0 + torch.sum(dq[:, 1:] * dq[:, 1:], dim=-1, keepdim=True))
            u = torch.cat((inv_u, dq[:, 1:] * inv_u), dim=-1)
            th0 = torch.tanh(dq[:, :1])
            g_sc = torch.exp(th0)
            prod = quat_mul(u, hq)
            z = (g_sc * prod).reshape(*sh[:-1], n_pairs, 2)
            gp = go_w.reshape(*sh[:-1], n_pairs, 2)
            w2 = om_w * om_w
            inv_d = 1.0 / (1.0 + w2)
            c, s = (1.0 - w2) * inv_d, (2.0 * om_w) * inv_d
            z0, z1 = z.unbind(dim=-1)
            g0, g1 = gp.unbind(dim=-1)
            gz = torch.stack((c * g0 - s * g1, s * g0 + c * g1), dim=-1).reshape(-1, 4)
            y0, y1 = c * z0 + s * z1, -s * z0 + c * z1
            gw_full = (2.0 * inv_d) * (g0 * y1 - g1 * y0)

            dg = torch.sum(gz * prod, dim=-1, keepdim=True)
            dd0 = dg * g_sc * (1.0 - th0 * th0)
            g_prod = g_sc * gz
            gh_w = quat_mul(quat_conj(u), g_prod).reshape(sh)
            gu = quat_mul(g_prod, quat_conj(hq))
            dot_gu_u = torch.sum(gu * u, dim=-1, keepdim=True)
            gd_w = torch.cat((dd0, (gu[:, 1:] - dot_gu_u * u[:, 1:]) * inv_u), dim=-1).reshape(sh)

        gw = _reduce_broadcast_grad(gw_full.float() if ctx.use_bf16_io else gw_full, ctx.om_orig_shape)
        return (
            gh_w if gh_w.dtype == ctx.in_dtype else gh_w.to(ctx.in_dtype),
            gd_w if gd_w.dtype == ctx.in_dtype else gd_w.to(ctx.in_dtype),
            gw if gw.dtype == ctx.om_dtype else gw.to(ctx.om_dtype),
            None,
        )


# ---------------------------------------------------------------------------
# Public Unified ABI (Aligned 1-to-1 with silisphere/kernels/ #3053!)
# ---------------------------------------------------------------------------


def safe_hopf_clock_angle(
    pass_idx: int,
    *,
    law: str = "acute_cone",
    r_max: int = 8,
    r_train: int = 3,
    t_max: float = 0.75,
    rate: float = 0.35,
) -> float:
    """Compute Hopf S^1 fiber clock angle for loop pass pass_idx.

    - 'acute_cone' (W10-OBS-31 fix): phi_r = pi * (r + 1) / (2 * r_max + 1) in (0, pi/2)
      for all 0 <= r < r_max, guaranteeing cos(phi_r) > 0 strictly.
    - 'cayley_acute' (SFU-free rational Cayley law aligned with holosphere/lean/):
      t_r = t_max * tanh(rate * (r + 1)) in (0, 1), cos(phi) = (1 - t^2)/(1 + t^2) > 0,
      sin(phi) = 2t/(1 + t^2), phi = atan2(2t, 1 - t^2) in (0, pi/2).
    - 'unaliased_coprime': phi_r = 2 * pi * r / 11 (Track S107 baseline).
    - 'pinned_train_step': phi_r = 2 * pi * r / r_train.
    """
    _require(pass_idx >= 0, f"pass_idx must be >= 0, got {pass_idx}")
    if law == "acute_cone":
        _require(r_max >= 1, f"r_max must be >= 1, got {r_max}")
        eff_r = min(pass_idx, r_max - 1)
        return math.pi * float(eff_r + 1) / float(2 * r_max + 1)
    if law == "cayley_acute":
        _require(0.0 < t_max < 1.0, f"cayley_acute requires 0 < t_max < 1, got {t_max}")
        tr = t_max * math.tanh(rate * float(pass_idx + 1))
        return math.atan2(2.0 * tr, 1.0 - tr * tr)
    if law == "unaliased_coprime":
        return 2.0 * math.pi * float(pass_idx) / 11.0
    if law == "pinned_train_step":
        _require(r_train >= 1, f"r_train must be >= 1, got {r_train}")
        return 2.0 * math.pi * float(pass_idx) / float(r_train)
    raise S114OpError(f"Unknown Hopf clock law: {law!r}")


def safe_hopf_clock(
    x: torch.Tensor,
    pass_idx: int,
    *,
    law: str = "acute_cone",
    r_max: int = 8,
    r_train: int = 3,
    t_max: float = 0.75,
    rate: float = 0.35,
) -> torch.Tensor:
    """Apply exact orthogonal Hopf S^1 fiber rotation to 4D blocks of x."""
    _require(x.shape[-1] % 4 == 0, f"safe_hopf_clock requires last dim % 4 == 0, got {x.shape[-1]}")
    if law == "cayley_acute":
        _require(pass_idx >= 0 and 0.0 < t_max < 1.0, "invalid cayley_acute parameters")
        tr = t_max * math.tanh(rate * float(pass_idx + 1))
        denom = 1.0 + tr * tr
        return _hopf_rotate_tensor(x, (1.0 - tr * tr) / denom, (2.0 * tr) / denom)
    phi = safe_hopf_clock_angle(pass_idx, law=law, r_max=r_max, r_train=r_train, t_max=t_max, rate=rate)
    return _hopf_rotate_tensor(x, math.cos(phi), math.sin(phi))


def su2_holonomy_transport(
    q: torch.Tensor,
    k: torch.Tensor,
    v: torch.Tensor,
    omega: torch.Tensor,
    *,
    angle_scale: Optional[float] = 0.75,
    transport_v: bool = False,
    eps: float = 1e-6,
    backend: str = "auto",
    map_mode: str = "exp",
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Fused associative SU(2) holonomy scan + covariant (Q,K[,V]) parallel transport.

    Args:
      q, k, v: [B, H, T, D] with D % 4 == 0 (n_blocks = D // 4).
      omega:   [B, H, T, n_blocks, 3] (pre-tanh if angle_scale is not None, else raw su(2)).
      angle_scale: float scaling after tanh(omega), or None for raw su(2) input.
      transport_v: if True, also left-multiplies V by Pi(t) for H14c covariant transport.
      map_mode: 'exp' (standard su2_exp) or 'cayley' (SFU-free rational (1-|w|^2, 2w)/(1+|w|^2)).
    Returns:
      (q_rot, k_rot, v_rot, pi_path) with q_rot/k_rot/v_rot [B, H, T, D],
      pi_path [B, H, T, n_blocks, 4] (always FP32/FP64 for S^3 manifold precision).
    """
    _require(map_mode in ("exp", "cayley"), f"Unknown map_mode: {map_mode!r}")
    _require(math.isfinite(eps) and eps > 0.0, f"eps must be finite and > 0, got {eps}")
    if angle_scale is not None:
        _require(math.isfinite(angle_scale), f"angle_scale must be finite, got {angle_scale}")
    _require(q.ndim == 4 and k.shape == q.shape and v.shape == q.shape, "q, k, v must share [B, H, T, D]")
    bsz, n_heads, seq_len, d_head = q.shape
    _require(d_head % 4 == 0, f"d_head must be divisible by 4, got {d_head}")
    n_blocks = d_head // 4
    _require(
        omega.shape == (bsz, n_heads, seq_len, n_blocks, 3),
        f"omega expected {(bsz, n_heads, seq_len, n_blocks, 3)}, got {tuple(omega.shape)}",
    )
    resolved = _resolve_backend(backend, q.is_cuda, q.dtype)
    use_tanh = angle_scale is not None
    eff_scale = 1.0 if angle_scale is None else float(angle_scale)

    # V2 Fast Path: Zero-Permute Strided Coalesced BHTD CUDA Kernel (direct FP32 & BF16!)
    if resolved == "cuda":
        lib = _load_cuda_lib()
        if lib is not None and hasattr(lib, "silisphere_su2_holonomy_bhtd_fwd_f32"):
            q_rot, k_rot, v_rot_raw, pi_path = _SU2HolonomyBHTDFn.apply(
                omega, q, k, v if transport_v else None, eff_scale, use_tanh, float(eps), map_mode
            )
            v_rot = v_rot_raw if transport_v else v
            return q_rot, k_rot, v_rot, pi_path

    # Fiber-major [B * H * nb, T, C] path for Triton / Reference / V1 fallback
    n_fibers = bsz * n_heads * n_blocks
    raw_f = omega.permute(0, 1, 3, 2, 4).reshape(n_fibers, seq_len, 3)
    q_f = q.reshape(bsz, n_heads, seq_len, n_blocks, 4).permute(0, 1, 3, 2, 4).reshape(n_fibers, seq_len, 4)
    k_f = k.reshape(bsz, n_heads, seq_len, n_blocks, 4).permute(0, 1, 3, 2, 4).reshape(n_fibers, seq_len, 4)
    v_f = (
        v.reshape(bsz, n_heads, seq_len, n_blocks, 4).permute(0, 1, 3, 2, 4).reshape(n_fibers, seq_len, 4)
        if transport_v
        else None
    )

    qo_f, ko_f, vo_f, u_f = _SU2HolonomyTransportFn.apply(
        raw_f, q_f, k_f, v_f, eff_scale, use_tanh, float(eps), resolved, map_mode
    )

    def _from_fiber(t_f: torch.Tensor) -> torch.Tensor:
        return t_f.reshape(bsz, n_heads, n_blocks, seq_len, 4).permute(0, 1, 3, 2, 4)

    q_rot = _from_fiber(qo_f).reshape(bsz, n_heads, seq_len, d_head)
    k_rot = _from_fiber(ko_f).reshape(bsz, n_heads, seq_len, d_head)
    v_rot = _from_fiber(vo_f).reshape(bsz, n_heads, seq_len, d_head) if transport_v else v
    pi_path = _from_fiber(u_f)
    return q_rot, k_rot, v_rot, pi_path


def cayley_2x2_rotate(
    x: torch.Tensor,
    omega: torch.Tensor,
    *,
    backend: str = "auto",
) -> torch.Tensor:
    """V2 Beltrami [C, K] = 0 exact 2x2 block-diagonal Cayley SO(d) rotation (0 B spills)."""
    _require(x.ndim >= 1 and x.shape[-1] > 0 and x.shape[-1] % 4 == 0, f"x last dim must be positive multiple of 4, got {tuple(x.shape)}")
    n_pairs = x.shape[-1] // 2
    _require(omega.ndim >= 1 and omega.shape[-1] == n_pairs, f"omega last dim must equal {n_pairs}, got {tuple(omega.shape)}")
    resolved = _resolve_backend(backend, x.is_cuda, x.dtype)
    return _Cayley2x2Fn.apply(x, omega, resolved)


def hopf_s3_cayley_2x2_step(
    h: torch.Tensor,
    delta: torch.Tensor,
    omega: torch.Tensor,
    *,
    backend: str = "auto",
) -> torch.Tensor:
    """V2 Zero-HBM-epilogue fused Hopf-S^3 residual + Beltrami Cayley2x2 rotation (0 B spills)."""
    _require(h.shape == delta.shape and h.shape[-1] % 4 == 0, "h and delta must share shape with D%4==0")
    n_pairs = h.shape[-1] // 2
    _require(omega.ndim >= 1 and omega.shape[-1] == n_pairs, f"omega last dim must equal {n_pairs}, got {tuple(omega.shape)}")
    resolved = _resolve_backend(backend, h.is_cuda, h.dtype)
    return _HopfS3Cayley2x2Fn.apply(h, delta, omega, resolved)


def su2_inverse_untransport(
    o: torch.Tensor,
    pi_path: torch.Tensor,
    *,
    backend: str = "auto",
) -> torch.Tensor:
    """Apply covariant inverse parallel transport L(conj(Pi_t)) O_t (H14c)."""
    _require(o.ndim == 4 and o.shape[-1] % 4 == 0, f"o must be [B, H, T, D] with D%4==0, got {tuple(o.shape)}")
    bsz, n_heads, seq_len, d_head = o.shape
    n_blocks = d_head // 4
    _require(
        pi_path.shape == (bsz, n_heads, seq_len, n_blocks, 4),
        f"pi_path expected {(bsz, n_heads, seq_len, n_blocks, 4)}, got {tuple(pi_path.shape)}",
    )
    resolved = _resolve_backend(backend, o.is_cuda, o.dtype)
    o_q = o.reshape(bsz, n_heads, seq_len, n_blocks, 4)
    out_q = _SU2InverseUntransportFn.apply(o_q, pi_path, resolved)
    return out_q.reshape(bsz, n_heads, seq_len, d_head)


def fused_spherical_step(
    h: torch.Tensor,
    delta: torch.Tensor,
    alpha: Optional[torch.Tensor] = None,
    *,
    mode: str = "slerp",
    phi: float = 0.0,
    alpha_scale: float = 0.45 * math.pi,
    eps: float = 1e-4,
    backend: str = "auto",
) -> torch.Tensor:
    """Unified fused spherical residual step (slerp | safe_hopf_loop | hopf_s3)."""
    _require(math.isfinite(eps) and eps > 0.0, f"eps must be finite and > 0, got {eps}")
    _require(h.shape == delta.shape and h.shape[-1] % 4 == 0, "h and delta must share shape with D%4==0")
    resolved = _resolve_backend(backend, h.is_cuda, h.dtype)
    if mode == "hopf_s3":
        return _HopfS3ResidualFn.apply(h, delta, resolved)
    _require(mode in ("slerp", "safe_hopf_loop"), f"Unknown spherical step mode: {mode!r}")
    _require(alpha is not None, f"mode={mode!r} requires alpha (logit tensor of shape [D] or scalar)")
    if alpha.ndim == 0 or alpha.numel() == 1:
        al_vec = alpha.reshape(1).expand(h.shape[-1])
    else:
        _require(alpha.shape == (h.shape[-1],), f"alpha expected ({h.shape[-1]},), got {tuple(alpha.shape)}")
        al_vec = alpha
    eff_phi = 0.0 if mode == "slerp" else float(phi)
    return _FusedSphericalSlerpHopfFn.apply(
        h, delta, al_vec, float(alpha_scale), math.cos(eff_phi), math.sin(eff_phi), float(eps), resolved
    )


# ---------------------------------------------------------------------------
# Composable Modules Ready for H14a / H14b / H14c & silisphere Integration
# ---------------------------------------------------------------------------


class S114CovariantHolonomyAttention(nn.Module):
    """Fused SU(2) Holonomy Attention supporting QK-only (H14a) & full covariant QKV+untransport (H14c)."""

    def __init__(
        self,
        d_model: int,
        n_heads: int,
        *,
        covariant_v: bool = True,
        ngpt: bool = True,
        angle_scale: float = 0.75,
        backend: str = "auto",
        map_mode: str = "exp",
    ) -> None:
        super().__init__()
        _require(d_model % n_heads == 0, "d_model must be divisible by n_heads")
        d_head = d_model // n_heads
        _require(d_head % 4 == 0, "d_head must be divisible by 4")
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_head = d_head
        self.n_blocks = d_head // 4
        self.covariant_v = covariant_v
        self.ngpt = ngpt
        self.angle_scale = angle_scale
        self.backend = backend
        self.map_mode = map_mode

        self.w_q = nn.Linear(d_model, d_model, bias=False)
        self.w_k = nn.Linear(d_model, d_model, bias=False)
        self.w_v = nn.Linear(d_model, d_model, bias=False)
        self.w_o = nn.Linear(d_model, d_model, bias=False)
        self.w_omega = nn.Linear(d_model, 3 * n_heads * self.n_blocks, bias=False)
        if ngpt:
            # Block-4 tied sqk preserves exact SU(2) 4-block equivariance: L(U)(c_b * q_b) == c_b * L(U)(q_b)
            self.sqk = nn.Parameter(torch.ones(1, n_heads, 1, self.n_blocks, 1))
        else:
            self.register_parameter("sqk", None)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        bsz, seq_len, _ = x.shape
        q = self.w_q(x).view(bsz, seq_len, self.n_heads, self.d_head).transpose(1, 2)
        k = self.w_k(x).view(bsz, seq_len, self.n_heads, self.d_head).transpose(1, 2)
        v = self.w_v(x).view(bsz, seq_len, self.n_heads, self.d_head).transpose(1, 2)
        omega = self.w_omega(x).view(bsz, seq_len, self.n_heads, self.n_blocks, 3).transpose(1, 2)

        q, k, v, pi_path = su2_holonomy_transport(
            q, k, v, omega,
            angle_scale=self.angle_scale,
            transport_v=self.covariant_v,
            backend=self.backend,
            map_mode=self.map_mode,
        )
        if self.ngpt and self.sqk is not None:
            sqk_exp = self.sqk.expand(1, self.n_heads, 1, self.n_blocks, 4).reshape(1, self.n_heads, 1, self.d_head)
            q = _safe_unit_norm(q, eps=1e-4) * sqk_exp
            k = _safe_unit_norm(k, eps=1e-4) * sqk_exp
            scale = math.sqrt(float(self.d_head))
        else:
            scale = 1.0 / math.sqrt(float(self.d_head))

        attn_out = F.scaled_dot_product_attention(q, k, v, is_causal=True, scale=scale)
        if self.covariant_v:
            attn_out = su2_inverse_untransport(attn_out, pi_path, backend=self.backend)
        attn_out = attn_out.transpose(1, 2).contiguous().view(bsz, seq_len, self.d_model)
        return self.w_o(attn_out)


__all__ = [
    "S114OpError",
    "quat_mul",
    "quat_conj",
    "safe_hopf_clock_angle",
    "safe_hopf_clock",
    "su2_holonomy_transport",
    "su2_inverse_untransport",
    "fused_spherical_step",
    "cayley_2x2_rotate",
    "hopf_s3_cayley_2x2_step",
    "S114CovariantHolonomyAttention",
]
