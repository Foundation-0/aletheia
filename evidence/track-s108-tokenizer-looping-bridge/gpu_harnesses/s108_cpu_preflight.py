#!/usr/bin/env python3
"""CPU-only pre-flight smoke, invariance, causality, and CS-08 parity suite for Track S108.

Verifies every mandatory PREREG-S108 + Amendment 1 + 3-Family Pre-Flight gate BEFORE any GPU launch:
  1. Zero bare asserts and zero arccos/acos calls across all Track S108 source files.
  2. H8a scale-gauge collapse immunity (||B_p|| scaled 1e+6x leaves hybrid cosine == gamma_a^2 == 0.25,
     whereas naive un-normalized [A(x)B; A; B] collapses to ~0), BlockStructuredProj side-block
     preservation, Rank1-Kron S104 Thm 8 orthogonal annihilation, and injective BPE/pair round-trips.
  3. H8b exact 0.0 turning on constant-speed great-circle geodesics (non-equivalent to H-Net 1st-order
     cosine step), bounded smooth gradients at cos=1 and cos=-1, strict encoder/decoder causality,
     streaming byte-by-byte vs teacher-forced NLL match (< 1e-5 BPB), and Portal-2 Turing D!=dI
     nucleation period inside [2.60, 3.45] vs D=dI null decay.
  4. H8c antipodal SLERP Norm(0) zero-NaN forward+backward, 1,000-trial exact per-batch loop budget
     sum(r) == 2*N, causal router zero future-target leakage, variable patch length 3..12 MTP-8
     masking + unrolled Markov decode, and Block-8 E8 RAM==WIRE==HASH cell self-verification
     (1-bit tamper rejected) + frozen judge / counterfactual edit decoder check.
  5. End-to-end CPU-only smoke execution of s108_train_eval.py across all 3 tracks (WEIGHTS=0).

Strictly CPU-only (never touches CUDA); runs cleanly across -I -B, -I -O -B, and -I -B -W error.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

import torch
import torch.nn.functional as F

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import s108_tokenizer_loop_ops as ops  # noqa: E402
import s108_train_eval as harness  # noqa: E402


class TestS108CpuPreflight(unittest.TestCase):
    def test_01_zero_bare_asserts_and_zero_arccos_calls(self) -> None:
        files = (
            "s108_tokenizer_loop_ops.py",
            "s108_train_eval.py",
            "s108_cpu_preflight.py",
        )
        for fname in files:
            src = (_HERE / fname).read_text(encoding="utf-8")
            tree = ast.parse(src, filename=fname)
            asserts = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Assert)]
            self.assertEqual(asserts, [], msg=f"bare asserts in {fname}: {asserts}")
            bad_calls: list[int] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    fn = node.func
                    if isinstance(fn, ast.Attribute) and fn.attr in ("acos", "arccos"):
                        bad_calls.append(node.lineno)
                    elif isinstance(fn, ast.Name) and fn.id in ("acos", "arccos"):
                        bad_calls.append(node.lineno)
            self.assertEqual(bad_calls, [], msg=f"forbidden acos/arccos calls in {fname}: {bad_calls}")

    def test_02_h8a_scale_gauge_immunity_block_proj_and_rank1_obstruction(self) -> None:
        torch.manual_seed(42)
        # 2 roots x 2 patterns = 4 tokens
        root_ids = [0, 0, 1, 1]
        pat_ids = [0, 1, 0, 1]
        hyb = ops.HybridKronSphereEmbedding(
            root_ids=root_ids,
            pattern_ids=pat_ids,
            n_roots=2,
            n_patterns=2,
            d_a=4,
            d_b=4,
            d_model=24,
            gammas=(math.sqrt(0.5), math.sqrt(0.25), math.sqrt(0.25)),
            use_block_proj=True,
        )
        r1 = ops.Rank1KronEmbedding(
            root_ids=root_ids,
            pattern_ids=pat_ids,
            n_roots=2,
            n_patterns=2,
            d_a=4,
            d_b=4,
            d_model=24,
        )
        # Set exact orthogonal roots and orthogonal patterns, then blow up ||B_p|| by 1e+6!
        with torch.no_grad():
            hyb.A.weight[0] = torch.tensor([1.0, 0.0, 0.0, 0.0])
            hyb.A.weight[1] = torch.tensor([0.0, 1.0, 0.0, 0.0])
            hyb.B.weight[0] = torch.tensor([1e6, 0.0, 0.0, 0.0])
            hyb.B.weight[1] = torch.tensor([0.0, 1e6, 0.0, 0.0])
            r1.A.weight.copy_(hyb.A.weight)
            r1.B.weight.copy_(hyb.B.weight)

            # Naive un-normalized [A(x)B; A; B] suffers scale-gauge collapse under ||B||=1e6
            a0, b0, b1 = hyb.A.weight[0], hyb.B.weight[0], hyb.B.weight[1]
            naive_00 = F.normalize(torch.cat([(a0[:, None] * b0[None, :]).reshape(-1), a0, b0]), dim=0)
            naive_01 = F.normalize(torch.cat([(a0[:, None] * b1[None, :]).reshape(-1), a0, b1]), dim=0)
            self.assertLess(abs(float(torch.dot(naive_00, naive_01).item())), 1e-6)

            # Pure Rank1-Kron hits exact S104 Thm 8 annihilation (0.0 cosine)
            k00 = r1.raw_kron(torch.tensor([0])).squeeze(0)
            k01 = r1.raw_kron(torch.tensor([1])).squeeze(0)
            self.assertAlmostEqual(float(torch.dot(k00, k01).item()), 0.0, places=5)

            # Amended HybridKronSphereEmbedding retains EXACT gamma_a^2 == 0.25 and gamma_b^2 == 0.25!
            e_raw = hyb.raw_hybrid(torch.tensor([0, 1, 2, 3]))
            norms = torch.linalg.vector_norm(e_raw, dim=-1)
            self.assertLess(float((norms - 1.0).abs().max().item()), 1e-5)
            # Same root (0), orthogonal patterns (0 vs 1) -> cosine == gamma_a^2 == 0.25
            self.assertAlmostEqual(float(torch.dot(e_raw[0], e_raw[1]).item()), 0.25, places=5)
            # Orthogonal roots (0 vs 1), same pattern (0) -> cosine == gamma_b^2 == 0.25
            self.assertAlmostEqual(float(torch.dot(e_raw[0], e_raw[2]).item()), 0.25, places=5)

            # Block-structured projection keeps exact unit norm and reserved side-block energy
            e_proj = hyb(torch.tensor([0, 1, 2, 3]))
            proj_norms = torch.linalg.vector_norm(e_proj, dim=-1)
            self.assertLess(float((proj_norms - 1.0).abs().max().item()), 1e-5)
            proj_mod = hyb.proj
            self.assertIsInstance(proj_mod, ops.BlockStructuredProj)
            d_k = proj_mod.d_k_out
            d_a_out = proj_mod.d_a_out
            # Energy in each disjoint output slice matches fixed gamma^2 == (0.5, 0.25, 0.25)
            en_k = float((e_proj[0, :d_k] ** 2).sum().item())
            en_a = float((e_proj[0, d_k : d_k + d_a_out] ** 2).sum().item())
            en_b = float((e_proj[0, d_k + d_a_out :] ** 2).sum().item())
            self.assertAlmostEqual(en_k, 0.50, places=4)
            self.assertAlmostEqual(en_a, 0.25, places=4)
            self.assertAlmostEqual(en_b, 0.25, places=4)

    def test_03_bpe_and_morph_codec_lossless_and_injective(self) -> None:
        splits, _ = harness.load_multidomain_byte_splits(max_bytes_per_domain=2048, allow_local_caches=False)
        train_all = b"\n".join(splits[d]["train"] for d in splits)
        bpe = ops.DeterministicByteBPE(vocab_size=320).fit(train_all)
        for dom in splits:
            ev = splits[dom]["eval"][:512]
            toks = bpe.encode(ev)
            self.assertEqual(bpe.decode(toks), ev, msg=f"lossless BPE round-trip failed on {dom}")
        n_r = int(math.ceil(math.sqrt(bpe.vocab_size)))
        n_p = int(math.ceil(bpe.vocab_size / n_r))
        codec = ops.MorphStructPairCodec(bpe.id_to_bytes, n_roots=n_r, n_patterns=n_p, seed=42)
        m_ok, r_ok = codec.verify_injective()
        self.assertTrue(m_ok)
        self.assertTrue(r_ok)

    def test_04_h8b_geodesic_curvature_non_equivalent_to_hnet_and_smooth_grad(self) -> None:
        # 1) Constant-speed great-circle geodesic in (e0, e1) plane, step delta = 0.4 rad
        delta = 0.4
        ts = torch.arange(8, dtype=torch.float32) * delta
        u_geo = torch.zeros((1, 8, 4), dtype=torch.float32)
        u_geo[0, :, 0] = torch.cos(ts)
        u_geo[0, :, 1] = torch.sin(ts)

        hnet_s = ops.hnet_first_order_cosine_score(u_geo)
        curv_s = ops.geodesic_second_order_turning_score(u_geo)
        expected_step = 0.5 * (1.0 - math.cos(delta))
        # H-Net 1st-order step is strictly large (~0.0395), while 2nd-order parallel-transport curvature is ~0.0!
        self.assertAlmostEqual(float(hnet_s[0, 3].item()), expected_step, places=4)
        self.assertLess(float(curv_s[0, 2:].max().item()), 1e-5)

        # 2) Sharp 90-degree turn out of (e0, e1) plane into e2 at t=4: curvature jumps cleanly to ~0.5
        u_turn = u_geo.clone()
        # At t=3 we are at (cos(3d), sin(3d), 0, 0); step orthogonally toward e2 at t=4
        u_turn[0, 4, :] = torch.tensor([0.0, 0.0, 1.0, 0.0])
        curv_turn = ops.geodesic_second_order_turning_score(u_turn)
        self.assertGreater(float(curv_turn[0, 4].item()), 0.45)

        # 3) Bounded finite gradients even at cos == 1.0 (identical vectors) and cos == -1.0 (antipodal)
        u_deg = torch.tensor(
            [[[1.0, 0.0, 0.0], [1.0, 0.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]],
            dtype=torch.float32,
            requires_grad=True,
        )
        loss = ops.hnet_first_order_cosine_score(u_deg).sum() + ops.geodesic_second_order_turning_score(u_deg).sum()
        loss.backward()
        self.assertIsNotNone(u_deg.grad)
        self.assertTrue(bool(torch.isfinite(u_deg.grad).all().item()))

    def test_05_h8b_strict_causality_streaming_vs_teacher_forced_and_turing_diag(self) -> None:
        torch.manual_seed(7)
        # Test strict causality & streaming-vs-teacher-forced exact match for every dynamic router
        seq = torch.randint(0, 256, (1, 20), dtype=torch.long)
        for kind in ("fixed_byte4", "blt_entropy", "hnet_cosine", "spherepatch_geodesic2"):
            model = harness.DynamicBytePatchLM(
                router_kind=kind, d_b=16, d_model=24, n_layers=1, n_heads=4, target_patch_len=4.0
            )
            model.eval()
            with torch.no_grad():
                tf_logits, _, _ = model(seq)
                # Mutate future bytes >= 10 -> logits for positions <= 10 MUST be bit-exact / < 1e-5 identical!
                seq_mut = seq.clone()
                seq_mut[0, 10:] = (seq_mut[0, 10:] + 77) % 256
                mut_logits, _, _ = model(seq_mut)
                max_leak = float((tf_logits[:, :11, :] - mut_logits[:, :11, :]).abs().max().item())
                self.assertLess(max_leak, 1e-5, msg=f"future leakage detected in {kind}: {max_leak}")

                # Streaming byte-by-byte vs teacher-forced NLL equivalence (< 1e-5 BPB)
                tf_nll = float(
                    F.cross_entropy(tf_logits[:, 1:, :].float().reshape(-1, 256), seq[:, 1:].reshape(-1), reduction="sum").item()
                )
                stream_nll = 0.0
                for t in range(1, seq.shape[1]):
                    prefix_logits, _, _ = model(seq[:, : t + 1])
                    step_nll = F.cross_entropy(prefix_logits[:, -1, :].float(), seq[:, t], reduction="sum")
                    stream_nll += float(step_nll.item())
                diff_bpb = abs(tf_nll - stream_nll) / ((seq.shape[1] - 1) * math.log(2.0))
                self.assertLess(diff_bpb, 1e-5, msg=f"streaming vs TF BPB mismatch in {kind}: {diff_bpb}")

        # Portal-2 Turing boundary-nucleation diagnostic: D=(1,10) nucleates in [2.60, 3.45], D=(5,5) decays!
        d_diff = ops.turing_boundary_nucleation_diagnostic(seq_len=32, d_u=1.0, d_v=10.0, steps=1000, dt=0.02, seed=42)
        d_null = ops.turing_boundary_nucleation_diagnostic(seq_len=32, d_u=5.0, d_v=5.0, steps=1000, dt=0.02, seed=42)
        self.assertTrue(d_diff["nucleated"], msg=repr(d_diff))
        self.assertGreaterEqual(d_diff["mean_boundary_period"], 2.60, msg=repr(d_diff))
        self.assertLessEqual(d_diff["mean_boundary_period"], 3.45, msg=repr(d_diff))
        self.assertFalse(d_null["nucleated"], msg=repr(d_null))
        self.assertLess(d_null["growth_ratio"], 1e-4, msg=repr(d_null))

    def test_06_h8c_antipodal_slerp_exact_1000_trial_budget_mtp8_and_nullmodem_e8(self) -> None:
        torch.manual_seed(137)
        # 1) Antipodal SLERP safety (forward + backward zero NaN!)
        core = ops.SafeHopfLoopCore(d_model=16, n_heads=4, n_inner_layers=1, max_loops=4)
        with torch.no_grad():
            core.alpha_raw.zero_()  # sigmoid(0) * pi/2 == pi/4 -> cos == sin == sqrt(2)/2
        h = torch.zeros((2, 4, 16), dtype=torch.float32, requires_grad=True)
        h_unit = ops.safe_clamped_unit(torch.ones((2, 4, 16)), dim=-1)
        h_in = (h_unit + h).detach().requires_grad_(True)
        # Choose delta so rotated unit delta is EXACTLY -h_in (antipodal cancellation!)
        delta_antipodal = -core.apply_hopf_phase(h_in, pass_idx=0)
        # Inverse rotation for exact cancellation check:
        theta = core.hopf_freqs * 0.25
        c, s = torch.cos(theta), torch.sin(theta)
        he, ho = -h_in[..., 0::2], -h_in[..., 1::2]
        inv_rot = torch.stack([he * c + ho * s, -he * s + ho * c], dim=-1).reshape_as(h_in)
        out = core.slerp_step(h_in, inv_rot, pass_idx=0)
        self.assertTrue(bool(torch.isfinite(out).all().item()))
        out.sum().backward()
        self.assertIsNotNone(h_in.grad)
        self.assertTrue(bool(torch.isfinite(h_in.grad).all().item()))
        _ = delta_antipodal

        # 2) Unit-norm drift <= 1e-4 across 4 loop passes
        depths_4 = torch.full((2, 6), 4, dtype=torch.long)
        out_4, diag_4 = core.forward_with_depths(torch.randn(2, 6, 16), depths_4)
        self.assertTrue(bool(torch.isfinite(out_4).all().item()))
        self.assertLess(diag_4["max_unit_norm_drift"], 1e-4)

        # 3) 1,000-trial exact per-batch loop budget sum(r) == 2*N + anti-collapse diversity
        gen = torch.Generator(device="cpu")
        gen.manual_seed(2026)
        distinct_seen = 0
        for _ in range(1000):
            sc = torch.randn((2, 8, 3), generator=gen)
            d_alloc = ops.allocate_exact_loop_budget(sc, target_mean_r=2.0, min_r=1, max_r=4)
            self.assertEqual(int(d_alloc.sum().item()), 2 * 2 * 8)
            self.assertGreaterEqual(int(d_alloc.min().item()), 1)
            self.assertLessEqual(int(d_alloc.max().item()), 4)
            if len(set(d_alloc.reshape(-1).tolist())) >= 2:
                distinct_seen += 1
        self.assertGreaterEqual(distinct_seen, 990)

        # 3b) Causal router zero-future-target-leakage check (COLLAB-CLAUDE B7)
        pacer = ops.AdaptiveLoopPacer(d_model=16, max_r=4, target_mean_r=2.0)
        pacer.eval()
        px_a = torch.randn((1, 6, 16))
        surp_a = torch.tensor([[0.0, 0.2, 0.5, 0.1, 0.8, 0.3]])
        px_b = px_a.clone()
        surp_b = surp_a.clone()
        px_b[:, 4:, :] = torch.randn((1, 2, 16))
        surp_b[:, 4:] = 0.99
        with torch.no_grad():
            feat_a = torch.cat([px_a, surp_a.unsqueeze(-1)], dim=-1)
            feat_b = torch.cat([px_b, surp_b.unsqueeze(-1)], dim=-1)
            diff_router = float((pacer.router(feat_a)[:, :4, :] - pacer.router(feat_b)[:, :4, :]).abs().max().item())
        self.assertEqual(diff_router, 0.0)

        # 4) Variable patch lengths (3, 5, 8, 12) -> MTP-8 masked padding + Markov unroll
        raw_seq = torch.arange(28, dtype=torch.long) % 256
        starts = [0, 3, 8, 16]  # lengths: 3, 5, 8, 12
        tgt_b, mask_b, parents = ops.pad_variable_patches_to_blocks(raw_seq, starts, block_size=8)
        # Patch 0 predicts len-5 (1 block), patch 1 predicts len-8 (1 block), patch 2 predicts len-12 (2 blocks) => 4 blocks
        self.assertEqual(len(parents), 4)
        self.assertEqual([int(m.sum().item()) for m in mask_b], [5, 8, 8, 4])
        h_dummy = torch.randn((4, 32))
        mk = ops.MarkovMTP8Head(d_model=32, block_size=8, markov_rank=16)
        pl = ops.ParallelMTP8Head(d_model=32, block_size=8)
        ar = ops.LocalARByteDecoder(d_model=32, d_dec=16, n_heads=4, block_size=8)
        for head in (mk, pl, ar):
            lg_tf = head(h_dummy, target_bytes=tgt_b, unroll=False)
            lg_un = head(h_dummy, target_bytes=None, unroll=True)
            self.assertEqual(tuple(lg_tf.shape), (4, 8, 256))
            self.assertEqual(tuple(lg_un.shape), (4, 8, 256))
            self.assertTrue(bool(torch.isfinite(lg_tf).all().item()))
            self.assertTrue(bool(torch.isfinite(lg_un).all().item()))

        # 5) Block-8 E8 RAM==WIRE==HASH cell self-verification & 1-bit tamper rejection
        e8_cb = ops.build_e8_root_codebook()
        self.assertEqual(tuple(e8_cb.shape), (240, 8))
        cb_norms = torch.linalg.vector_norm(e8_cb, dim=-1)
        self.assertLess(float((cb_norms - 1.0).abs().max().item()), 1e-6)
        codec = ops.BlockE8SphereCodec(d_latent=16)
        z0 = ops.safe_l2_normalize(torch.randn(16), dim=-1)
        wire = codec.pack_cell(z0)
        self.assertEqual(len(wire), 8 + 2 + 32)  # 8B header + 2B E8 indices + 32B SHA-256
        z_rec = codec.unpack_cell(wire)
        self.assertAlmostEqual(float(torch.linalg.vector_norm(z_rec).item()), 1.0, places=5)
        tampered = bytearray(wire)
        tampered[8] ^= 0x01
        with self.assertRaises(ValueError):
            codec.unpack_cell(bytes(tampered))

    def test_07_end_to_end_cpu_smoke_harness(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = harness.main(
                    [
                        "--mode",
                        "cpu-smoke",
                        "--track",
                        "all",
                        "--device",
                        "cpu",
                        "--seeds",
                        "42",
                        "--no-local-caches",
                        "--out-dir",
                        td,
                    ]
                )
            self.assertEqual(rc, 0)
            emitted = json.loads(buf.getvalue())
            proto = json.loads((Path(td) / "s108_locked_protocol.json").read_text(encoding="utf-8"))
            res = json.loads((Path(td) / "s108_cpu_smoke_results.json").read_text(encoding="utf-8"))
            self.assertEqual(emitted["result_sha256"], res["result_sha256"])
            self.assertEqual(proto["parent_preregistration_sha256"], ops.PREREG_S108_SHA256)
            self.assertEqual(proto["amendment1_sha256"], ops.AMENDMENT1_SHA256)
            self.assertEqual(res["weights_saved"], 0)
            self.assertEqual(set(res["results"].keys()), {"h8a", "h8b", "h8c"})
            # Verify all 5 H8b arms present (including BPE-Std on identical byte windows & H-Net cosine N0)
            self.assertEqual(
                set(res["results"]["h8b"]["arms"].keys()),
                {"bpe_std", "fixed_byte4", "blt_entropy", "hnet_cosine", "spherepatch_geodesic2"},
            )
            # Verify exact r_bar == 2.0 in H8c Part 1 across all 3 modes
            for mode in ("adaptive", "uniform", "random"):
                r_mean = res["results"]["h8c"]["part1_adaptive_pacing"][mode]["runs"][0]["exact_mean_r"]
                self.assertAlmostEqual(r_mean, 2.0, places=5, msg=f"H8c Part 1 {mode} mean_r={r_mean}")
            # Verify nullmodem hash verification 100%, strong frozen-judge field acc, and counterfactual edit fidelity
            nm = res["results"]["h8c"]["part3_nullmodem"]["arms"]["nullmodem_sphere_cell"]
            self.assertEqual(nm["hash_verified_fraction"], 1.0)
            self.assertGreaterEqual(nm["frozen_judge_field_acc"], 0.90)
            self.assertGreaterEqual(nm["counterfactual_edit_acc"], 0.85)


if __name__ == "__main__":
    unittest.main()
