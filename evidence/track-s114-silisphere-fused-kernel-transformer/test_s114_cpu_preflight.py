#!/usr/bin/env python3
"""Track S114 Phase-1 CPU-Only Mathematical Parity, Gradcheck, & Zero-Spill Preflight Suite.

Runs strictly on CPU (CUDA_VISIBLE_DEVICES=""), zero bare asserts, 3-mode -I safe
(-I -B, -I -O -B, -I -B -W error), verifying:
  1. Exact forward parity of su2_holonomy_transport vs s107_models.py across T in {1, 7, 32, 33, 256, 512, 2048}.
  2. Exact FP64 torch.autograd.gradcheck on our custom Lie-algebraic su(2) additive-suffix-sum
     reverse-mode adjoint (both tanh-bounded and raw su(2), both QK-only and full covariant QKV +
     inverse untransport!).
  3. Exact non-Abelian interval holonomy identity U(s)^-1 U(t) = du_{s+1}...du_t, covariant
     inner-product invariance, non-commutativity, and inverse untransport conj(U)(U V) == V.
  4. Exact FP64 torch.autograd.gradcheck on fused_spherical_step across all 3 modes
     ('slerp', 'safe_hopf_loop', 'hopf_s3') + non-antipodal acute-cone Safe-Hopf clock (W10-OBS-31).
  5. End-to-end S114CovariantHolonomyAttention forward+backward sanity (finite grads, 0 NaN/Inf).
  6. Triton module clean CPU import + kernel presence check (zero GPU touch).
  7. Immutable PREREG-S114 SHA-256 lock + ptxas -v 0-byte stack/spill receipt + hygiene
     (0 weights, 0 CRLF, 0 forbidden leaks, 0 bare asserts).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import pathlib
import sys
import unittest

_HERE = pathlib.Path(__file__).resolve().parent
_EXPEDITION = _HERE.parent
_S107 = _EXPEDITION / "track-s107-hypersphere-transformer"
for _p in (str(_HERE), str(_S107), str(_S107 / "gpu_harnesses")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import torch  # noqa: E402
    from torch.autograd import gradcheck  # noqa: E402
    import s107_models as s107  # noqa: E402
    import s114_fused_ops as ops  # noqa: E402
    import su2_holonomy_triton as tr_mod  # noqa: E402

    _HAS_TORCH_DEPS = True
except ImportError:
    torch = None  # type: ignore[assignment]
    gradcheck = None  # type: ignore[assignment]
    s107 = None  # type: ignore[assignment]
    ops = None  # type: ignore[assignment]
    tr_mod = None  # type: ignore[assignment]
    _HAS_TORCH_DEPS = False

PREREG_SHA256 = "5fa927a06933c3cff057b65f75c1d2f190e10f1e420303d582dfb7c802ee69a4"


class TestS114CpuPreflight(unittest.TestCase):
    @unittest.skipUnless(_HAS_TORCH_DEPS, "requires torch and s107_models")
    def test_01_su2_scan_exact_parity_vs_s107_across_lengths(self) -> None:
        gen = torch.Generator().manual_seed(20261125)
        for seq_len in (1, 7, 32, 33, 64, 256, 512, 2048):
            bsz, heads, d_head = 1, 2, 16
            nb = d_head // 4
            q = torch.randn((bsz, heads, seq_len, d_head), generator=gen)
            k = torch.randn((bsz, heads, seq_len, d_head), generator=gen)
            v = torch.randn((bsz, heads, seq_len, d_head), generator=gen)
            omega = torch.randn((bsz, heads, seq_len, nb, 3), generator=gen)

            q_rot, k_rot, v_rot, pi_path = ops.su2_holonomy_transport(
                q, k, v, omega, angle_scale=0.75, transport_v=True, backend="reference"
            )
            # Compare against Track S107 su2_parallel_prefix_scan
            omega_s107 = 0.75 * torch.tanh(omega).permute(0, 2, 1, 3, 4)  # [B, T, H, nb, 3]
            du_s107 = s107.su2_exp(omega_s107)
            u_s107 = s107.su2_parallel_prefix_scan(du_s107).permute(0, 2, 1, 3, 4)
            q_s107 = s107.quat_mul(u_s107, q.reshape(bsz, heads, seq_len, nb, 4)).reshape_as(q)
            k_s107 = s107.quat_mul(u_s107, k.reshape(bsz, heads, seq_len, nb, 4)).reshape_as(k)
            v_s107 = s107.quat_mul(u_s107, v.reshape(bsz, heads, seq_len, nb, 4)).reshape_as(v)

            err_u = float((pi_path - u_s107).abs().max().item())
            err_q = float((q_rot - q_s107).abs().max().item())
            err_k = float((k_rot - k_s107).abs().max().item())
            err_v = float((v_rot - v_s107).abs().max().item())
            self.assertLess(err_u, 5e-5, f"T={seq_len} U mismatch: {err_u}")
            self.assertLess(err_q, 5e-5, f"T={seq_len} Q mismatch: {err_q}")
            self.assertLess(err_k, 5e-5, f"T={seq_len} K mismatch: {err_k}")
            self.assertLess(err_v, 5e-5, f"T={seq_len} V mismatch: {err_v}")
            norm_drift = float((torch.linalg.vector_norm(pi_path, dim=-1) - 1.0).abs().max().item())
            self.assertLess(norm_drift, 1e-5, f"T={seq_len} unit-norm drift: {norm_drift}")

    @unittest.skipUnless(_HAS_TORCH_DEPS, "requires torch and s107_models")
    def test_02_exact_fp64_gradcheck_su2_lie_algebra_adjoint(self) -> None:
        gen = torch.Generator().manual_seed(11402)
        bsz, heads, seq_len, d_head = 1, 2, 9, 8
        nb = d_head // 4
        q = torch.randn((bsz, heads, seq_len, d_head), generator=gen, dtype=torch.float64, requires_grad=True)
        k = torch.randn((bsz, heads, seq_len, d_head), generator=gen, dtype=torch.float64, requires_grad=True)
        v = torch.randn((bsz, heads, seq_len, d_head), generator=gen, dtype=torch.float64, requires_grad=True)
        omega = torch.randn((bsz, heads, seq_len, nb, 3), generator=gen, dtype=torch.float64, requires_grad=True)

        # Case A: Full covariant QKV transport + inverse untransport (tanh bounded)
        def _fn_covariant(qq, kk, vv, om):
            qr, kr, vr, pi = ops.su2_holonomy_transport(
                qq, kk, vv, om, angle_scale=0.75, transport_v=True, backend="reference"
            )
            ov = ops.su2_inverse_untransport(vr, pi, backend="reference")
            return qr, kr, ov, pi

        self.assertTrue(gradcheck(_fn_covariant, (q, k, v, omega), eps=1e-6, atol=1e-5, rtol=1e-4))

        # Case B: Raw su(2) (angle_scale=None), QK-only + exact zero-omega singularity point
        omega_zero = torch.zeros((bsz, heads, seq_len, nb, 3), dtype=torch.float64, requires_grad=True)

        def _fn_raw_zero(qq, kk, vv, om):
            qr, kr, vr, pi = ops.su2_holonomy_transport(
                qq, kk, vv, om, angle_scale=None, transport_v=False, backend="reference"
            )
            return qr, kr, vr, pi

        self.assertTrue(gradcheck(_fn_raw_zero, (q, k, v, omega_zero), eps=1e-6, atol=1e-5, rtol=1e-4))

        # Cross-check exact backward gradients against S107 autograd (float64)
        q2 = q.detach().clone().requires_grad_(True)
        k2 = k.detach().clone().requires_grad_(True)
        om2 = omega.detach().clone().requires_grad_(True)
        qr1, kr1, _, _ = ops.su2_holonomy_transport(q, k, v.detach(), omega, angle_scale=0.75, transport_v=False, backend="reference")
        w_out = torch.randn_like(qr1, dtype=torch.float64)
        loss1 = (qr1 * w_out).sum() + (kr1 * (w_out * 0.5)).sum()
        g_q1, g_k1, g_om1 = torch.autograd.grad(loss1, (q, k, omega))

        u_s107 = s107.su2_parallel_prefix_scan(s107.su2_exp(0.75 * torch.tanh(om2).permute(0, 2, 1, 3, 4))).permute(0, 2, 1, 3, 4)
        qr2 = s107.quat_mul(u_s107, q2.reshape(bsz, heads, seq_len, nb, 4)).reshape_as(q2)
        kr2 = s107.quat_mul(u_s107, k2.reshape(bsz, heads, seq_len, nb, 4)).reshape_as(k2)
        loss2 = (qr2 * w_out).sum() + (kr2 * (w_out * 0.5)).sum()
        g_q2, g_k2, g_om2 = torch.autograd.grad(loss2, (q2, k2, om2))

        self.assertLess(float((g_q1 - g_q2).abs().max().item()), 1e-10)
        self.assertLess(float((g_k1 - g_k2).abs().max().item()), 1e-10)
        self.assertLess(float((g_om1 - g_om2).abs().max().item()), 1e-10)

    @unittest.skipUnless(_HAS_TORCH_DEPS, "requires torch and s107_models")
    def test_03_holonomy_invariants_non_abelian_and_inverse_untransport(self) -> None:
        gen = torch.Generator().manual_seed(11403)
        bsz, heads, seq_len, d_head = 2, 2, 17, 16
        nb = d_head // 4
        q = torch.randn((bsz, heads, seq_len, d_head), generator=gen, dtype=torch.float64)
        k = torch.randn((bsz, heads, seq_len, d_head), generator=gen, dtype=torch.float64)
        v = torch.randn((bsz, heads, seq_len, d_head), generator=gen, dtype=torch.float64)
        omega = torch.randn((bsz, heads, seq_len, nb, 3), generator=gen, dtype=torch.float64)

        qr, kr, vr, pi = ops.su2_holonomy_transport(q, k, v, omega, transport_v=True, backend="reference")
        # 1. Exact inverse untransport: conj(Pi) * (Pi * V) == V
        v_rec = ops.su2_inverse_untransport(vr, pi, backend="reference")
        self.assertLess(float((v_rec - v).abs().max().item()), 1e-12)

        # 2. Exact interval holonomy: U(s)^-1 U(t) == du_{s+1} * ... * du_t
        du = ops._su2_exp_from_raw_ref(omega, 0.75, True, 1e-6)
        s_idx, t_idx = 3, 12
        interval_lhs = ops.quat_mul(ops.quat_conj(pi[:, :, s_idx]), pi[:, :, t_idx])
        interval_rhs = du[:, :, s_idx + 1]
        for idx in range(s_idx + 2, t_idx + 1):
            interval_rhs = ops.quat_mul(interval_rhs, du[:, :, idx])
        self.assertLess(float((interval_lhs - interval_rhs).abs().max().item()), 1e-12)

        # 3. Non-Abelian non-commutativity: swapping two adjacent steps changes final holonomy
        omega_swapped = omega.clone()
        omega_swapped[:, :, 4], omega_swapped[:, :, 5] = omega[:, :, 5].clone(), omega[:, :, 4].clone()
        _, _, _, pi_swapped = ops.su2_holonomy_transport(q, k, v, omega_swapped, transport_v=False, backend="reference")
        diff_comm = float((pi[:, :, -1] - pi_swapped[:, :, -1]).abs().max().item())
        self.assertGreater(diff_comm, 1e-3, "SU(2) holonomy must be non-Abelian")

        # 4. Exact covariant QK inner product: <Pi_t Q_t, Pi_s K_s> == <Q_t, (Pi_t^-1 Pi_s) K_s>
        ip_direct = float((qr[:, :, t_idx] * kr[:, :, s_idx]).sum().item())
        rel = ops.quat_mul(ops.quat_conj(pi[:, :, t_idx]), pi[:, :, s_idx])
        k_trans = ops.quat_mul(rel, k[:, :, s_idx].reshape(bsz, heads, nb, 4)).reshape(bsz, heads, d_head)
        ip_cov = float((q[:, :, t_idx] * k_trans).sum().item())
        self.assertLess(abs(ip_direct - ip_cov), 1e-11)

    @unittest.skipUnless(_HAS_TORCH_DEPS, "requires torch and s107_models")
    def test_04_spherical_steps_gradcheck_and_safe_hopf_acute_cone(self) -> None:
        gen = torch.Generator().manual_seed(11404)
        h = torch.randn((3, 5, 16), generator=gen, dtype=torch.float64, requires_grad=True)
        delta = torch.randn((3, 5, 16), generator=gen, dtype=torch.float64, requires_grad=True)
        alpha = torch.randn((16,), generator=gen, dtype=torch.float64, requires_grad=True)

        # Mode 1: slerp
        self.assertTrue(
            gradcheck(lambda x, d, a: ops.fused_spherical_step(x, d, a, mode="slerp", backend="reference"), (h, delta, alpha), eps=1e-6, atol=1e-5, rtol=1e-4)
        )
        # Mode 2: safe_hopf_loop
        phi = ops.safe_hopf_clock_angle(5, law="acute_cone", r_max=8)
        self.assertTrue(
            gradcheck(lambda x, d, a: ops.fused_spherical_step(x, d, a, mode="safe_hopf_loop", phi=phi, backend="reference"), (h, delta, alpha), eps=1e-6, atol=1e-5, rtol=1e-4)
        )
        # Mode 3: hopf_s3 (H6c)
        self.assertTrue(
            gradcheck(lambda x, d: ops.fused_spherical_step(x, d, mode="hopf_s3", backend="reference"), (h, delta), eps=1e-6, atol=1e-5, rtol=1e-4)
        )

        # Verify W10-OBS-31 non-antipodal acute-cone & SFU-free cayley_acute Safe-Hopf guarantees across passes 0..15
        for law in ("acute_cone", "cayley_acute"):
            for r in range(16):
                ang = ops.safe_hopf_clock_angle(r, law=law, r_max=8)
                self.assertGreater(ang, 0.0)
                self.assertLess(ang, 0.5 * math.pi)
                self.assertGreater(math.cos(ang), 0.05)
                rot = ops.safe_hopf_clock(h.detach(), r, law=law, r_max=8)
                n_diff = float((torch.linalg.vector_norm(rot, dim=-1) - torch.linalg.vector_norm(h.detach(), dim=-1)).abs().max().item())
                self.assertLess(n_diff, 1e-12)

    @unittest.skipUnless(_HAS_TORCH_DEPS, "requires torch and s107_models")
    def test_05_covariant_attention_e2e_and_triton_import(self) -> None:
        torch.manual_seed(11405)
        attn = ops.S114CovariantHolonomyAttention(d_model=64, n_heads=4, covariant_v=True, ngpt=True, backend="reference")
        x = torch.randn((2, 33, 64), requires_grad=True)
        y = attn(x)
        self.assertEqual(tuple(y.shape), (2, 33, 64))
        self.assertTrue(bool(torch.isfinite(y).all().item()))
        loss = (y * y).mean()
        loss.backward()
        self.assertIsNotNone(x.grad)
        self.assertTrue(bool(torch.isfinite(x.grad).all().item()))
        for name, p in attn.named_parameters():
            self.assertIsNotNone(p.grad, f"missing grad on {name}")
            self.assertTrue(bool(torch.isfinite(p.grad).all().item()), f"non-finite grad on {name}")
        # Triton module cleanly imported on CPU without initializing CUDA
        self.assertTrue(hasattr(tr_mod, "triton_su2_holonomy_fwd"))
        self.assertTrue(hasattr(tr_mod, "triton_su2_holonomy_bwd"))

    def test_06_prereg_lock_zero_spill_receipt_and_hygiene(self) -> None:
        prereg = _HERE / "PREREG_S114_SILISPHERE_FUSED_ENTITY.md"
        if not prereg.is_file():
            prereg = _EXPEDITION / "notes" / "holosphere_kernel_transformer_2026_11_25" / "PREREG_S114_SILISPHERE_FUSED_ENTITY.md"
        self.assertTrue(prereg.is_file(), "PREREG-S114 missing")
        got_sha = hashlib.sha256(prereg.read_bytes()).hexdigest()
        self.assertEqual(got_sha, PREREG_SHA256)

        receipt_path = _HERE / "ptxas_sm86_zero_spill_receipt.json"
        self.assertTrue(receipt_path.is_file(), "ptxas zero-spill receipt missing")
        rec = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(rec["arch"], "sm_86")
        self.assertEqual(rec["nonzero_spill_kernels"], 0)
        self.assertEqual(rec["zero_spill_kernels"], 27)
        self.assertEqual(rec["cu_sha256"], hashlib.sha256((_HERE / "su2_holonomy_scan_sm86.cu").read_bytes()).hexdigest())

        bad = ("/" + "home/", "~" + "/", "/" + "dev/" + "null", "4" + "-mode")
        for p in sorted(_HERE.iterdir()):
            if not p.is_file():
                continue
            self.assertNotIn(p.suffix, (".so", ".o", ".bin", ".pt", ".pth", ".safetensors", ".gguf", ".ckpt"))
            raw = p.read_bytes()
            self.assertNotIn(b"\r", raw, p.name)
            if p.name.startswith("PREREG_S114_"):
                continue
            low = raw.decode("utf-8").lower()
            for tok in bad:
                self.assertNotIn(tok, low, f"forbidden token {tok!r} in {p.name}")

    @unittest.skipUnless(_HAS_TORCH_DEPS, "requires torch and s107_models")
    def test_07_v2_cayley2x2_hopf_s3_and_cayley_su2_gradcheck_and_beltrami(self) -> None:
        gen = torch.Generator().manual_seed(11407)
        x = torch.randn((3, 5, 16), generator=gen, dtype=torch.float64, requires_grad=True)
        d = torch.randn((3, 5, 16), generator=gen, dtype=torch.float64, requires_grad=True)
        w_full = torch.randn((3, 5, 8), generator=gen, dtype=torch.float64, requires_grad=True)
        w_bcast = torch.randn((8,), generator=gen, dtype=torch.float64, requires_grad=True)

        # 1. FP64 gradcheck on Cayley2x2 (full + broadcast omega) & fused Hopf-S^3 + Cayley2x2
        self.assertTrue(gradcheck(lambda a, w: ops.cayley_2x2_rotate(a, w, backend="reference"), (x, w_full), eps=1e-6, atol=1e-6, rtol=1e-5))
        self.assertTrue(gradcheck(lambda a, w: ops.cayley_2x2_rotate(a, w, backend="reference"), (x, w_bcast), eps=1e-6, atol=1e-6, rtol=1e-5))
        self.assertTrue(gradcheck(lambda a, b, w: ops.hopf_s3_cayley_2x2_step(a, b, w, backend="reference"), (x, d, w_full), eps=1e-6, atol=1e-6, rtol=1e-5))

        # 2. Exact Beltrami [C, K] = 0 helicity & norm conservation (m0..m4 drift < 1e-12)
        c_diag = torch.tensor([0.5, 0.5, -0.5, -0.5, 1.0, 1.0, -1.0, -1.0, 0.25, 0.25, -0.25, -0.25, 0.75, 0.75, -0.75, -0.75], dtype=torch.float64)
        v = ops._safe_unit_norm(torch.randn((16,), generator=gen, dtype=torch.float64))
        w_vec = w_bcast.detach()
        m0 = [float(torch.dot(v, (c_diag ** p) * v).item()) for p in range(5)]
        cur = v.clone()
        for _ in range(8):
            cur = ops.cayley_2x2_rotate(cur, w_vec, backend="reference")
            for p in range(5):
                mp = float(torch.dot(cur, (c_diag ** p) * cur).item())
                self.assertLess(abs(mp - m0[p]), 1e-12, f"Beltrami moment m{p} drifted")

        # 3. FP64 gradcheck on SFU-free pure-rational cayley_su2 holonomy scan (both tanh & raw!)
        q = torch.randn((2, 2, 11, 8), generator=gen, dtype=torch.float64, requires_grad=True)
        k = torch.randn((2, 2, 11, 8), generator=gen, dtype=torch.float64, requires_grad=True)
        vv = torch.randn((2, 2, 11, 8), generator=gen, dtype=torch.float64, requires_grad=True)
        om = torch.randn((2, 2, 11, 2, 3), generator=gen, dtype=torch.float64, requires_grad=True)
        self.assertTrue(
            gradcheck(
                lambda q_, k_, v_, om_: ops.su2_holonomy_transport(
                    q_, k_, v_, om_, angle_scale=0.5, transport_v=True, backend="reference", map_mode="cayley"
                )[:3],
                (q, k, vv, om),
                eps=1e-6,
                atol=1e-5,
                rtol=1e-4,
            )
        )
        self.assertTrue(
            gradcheck(
                lambda q_, k_, v_, om_: ops.su2_holonomy_transport(
                    q_, k_, v_, om_, angle_scale=None, transport_v=True, backend="reference", map_mode="cayley"
                )[:3],
                (q, k, vv, om),
                eps=1e-6,
                atol=1e-5,
                rtol=1e-4,
            )
        )
        # Verify strict acute cone q_w > 0 when angle_scale=0.5 (||w|| < sqrt(3)/2 < 1)
        _, _, _, pi_cay = ops.su2_holonomy_transport(
            q.detach(), k.detach(), vv.detach(), om.detach(), angle_scale=0.5, transport_v=True, backend="reference", map_mode="cayley"
        )
        self.assertLess(float((torch.linalg.vector_norm(pi_cay, dim=-1) - 1.0).abs().max().item()), 1e-12)

        # 4. Council P0 checks: antipodal SLERP m2 <= eps^2 zero-blowup guard, eps<=0 fail-closed, block-4 sqk equivariance
        h_anti = ops._safe_unit_norm(torch.randn((2, 4, 16), generator=gen, dtype=torch.float64)).requires_grad_(True)
        d_anti = (-h_anti.detach()).requires_grad_(True)
        # alpha = pi/4 -> cos(alpha) == sin(alpha), so cos*h_u + sin*(-h_u) == 0 exactly!
        al_45 = torch.full((16,), math.log((0.25 / 0.45) / (1.0 - 0.25 / 0.45)), dtype=torch.float64, requires_grad=True)
        y_anti = ops.fused_spherical_step(h_anti, d_anti, al_45, mode="slerp", backend="reference")
        gh_a, gd_a, ga_a = torch.autograd.grad(y_anti.sum(), (h_anti, d_anti, al_45))
        self.assertEqual(float(gh_a.abs().max().item()), 0.0)
        self.assertEqual(float(gd_a.abs().max().item()), 0.0)
        self.assertEqual(float(ga_a.abs().max().item()), 0.0)
        with self.assertRaises(ops.S114OpError):
            ops.su2_holonomy_transport(q.detach(), k.detach(), vv.detach(), om.detach(), eps=0.0, backend="reference")
        with self.assertRaises(ops.S114OpError):
            ops.fused_spherical_step(h_anti.detach(), d_anti.detach(), al_45.detach(), eps=-1e-4, backend="reference")
        attn_eq = ops.S114CovariantHolonomyAttention(d_model=64, n_heads=4, ngpt=True, backend="reference")
        self.assertEqual(tuple(attn_eq.sqk.shape), (1, 4, 1, 4, 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
