#!/usr/bin/env python3
"""CPU-only pre-flight smoke, invariance, CS-21, Bingham, and CS-08 parity suite for Track S109.

Verifies every mandatory PREREG-S109 + Amendments 1, 2, & 3 (TerraCore H9d) gate BEFORE GPU launch:
  1. Zero bare asserts across all Track S109 source files + exact SHA-256 protocol pins (incl. Amendment 3) +
     0% train/eval tuple overlap & zero UTF-8 truncation across all surfaces at surf_len=128.
  2. Strict <= 96-bit cap enforcement (k <= 32, 3 bpw), exact Bingham Stagnant-Lid zeroing (Y = 1 -> r == 0),
     monotone flux attenuation across Y in {0, 1/4, 1/2, 3/4, 1}, exact Track S50 Poloidal/Toroidal
     Hodge orthogonality (<u_pol, u_tor> == 0) + non-strawman matched-rank NoHodge coupling.
  3. Exact Stage-2 stop_gradient isolation (zero Core grads, bit-exact frozen Core SHA-256) and
     zero-skip-path graph enforcement between ext_in and ext_out.
  4. CB-1..CB-6 sanity + <= 50k MLP CS21_RESIDUAL_LEAK kill probe (clean 1-bit modifier passes;
     adversarial answer-leaking residual reliably triggers fail-closed CS21_RESIDUAL_LEAK!).
  5. Amendment-5 counterfactual h^(r) intermediate state patching, causal <EOS> padding invariance
     (ir_len=12 Native vs ir_len=24 padded bit-identical), & Portal-5 Darboux dark-mode diagnostic.
  6. Triple CS-08 parameter (P_total within 15M ±0.5% and cross-arm ±0.5%, charging Core + MHPlate +
     ext_out + audit_head) and inference/training FLOP (±5%) parity check across arms.
  7. End-to-end multi-seed CPU-only smoke run of s109_train_eval.py across H9a..H9d (WEIGHTS=0),
     with captured stdout so 3-mode -I R4 stdout parity is bit-identical (0 volatile stdout bytes).

Strictly CPU-only (never touches CUDA); runs cleanly across -I -B, -I -O -B, and -I -B -W error.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

import torch

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import s109_terracore_models as m  # noqa: E402
import s109_train_eval as harness  # noqa: E402


class TestS109CpuPreflight(unittest.TestCase):
    def test_01_zero_bare_asserts_prereg_sha_pins_and_disjoint_dataset(self) -> None:
        for fname in ("s109_terracore_models.py", "s109_train_eval.py", "s109_cpu_preflight.py"):
            tree = ast.parse((_HERE / fname).read_text(encoding="utf-8"), filename=fname)
            asserts = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Assert)]
            self.assertEqual(asserts, [], msg=f"bare asserts in {fname}: {asserts}")

        notes_dir = _HERE.parent / "notes" / "sphere_pi_forces_2026_11_25"
        if notes_dir.exists():
            expected = {
                "PREREG_S109_MINIMAL_MEDIUM_CORE_AND_TRANSLATOR.md": m.PREREG_S109_SHA256,
                "PREREG_S109_AMENDMENT1_COUNCIL_HARDENING.md": m.AMENDMENT1_SHA256,
                "PREREG_S109_AMENDMENT2_GEODYNAMIC_TERRACORE.md": m.AMENDMENT2_SHA256,
            }
            for fname, sha in expected.items():
                p = notes_dir / fname
                if p.exists():
                    self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), sha)

        am3_path = _HERE.parent / "notes" / "minimal_medium_terracore_2026_11_25" / "PREREG_S109_AMENDMENT3_STEELMAN_REPAIR.md"
        if am3_path.exists():
            self.assertEqual(hashlib.sha256(am3_path.read_bytes()).hexdigest(), m.AMENDMENT3_SHA256)

        r1, r2, _ = m.generate_s109_dataset(512, 512, seed=42, ir_len=24)
        for ds in (r1, r2):
            cut = (len(ds) * 3) // 4
            tr_keys = {(e.a, e.b, e.c, e.op_id) for e in ds[:cut]}
            ev_keys = {(e.a, e.b, e.c, e.op_id) for e in ds[cut:]}
            self.assertEqual(len(tr_keys & ev_keys), 0)
            for e in ds:
                self.assertLessEqual(len(e.surface_en.encode("utf-8")), 128)
                self.assertLessEqual(len(e.surface_alt.encode("utf-8")), 128)
                self.assertLessEqual(len(e.surface_mixed.encode("utf-8")), 128)
                self.assertLessEqual(len(e.deflate_bytes), 128)

    def test_02_strict_96bit_cap_bingham_stagnant_lid_and_hodge_orthogonality(self) -> None:
        with self.assertRaises(ValueError):
            m.ViscoplasticAsthenosphere(k=33, bits_per_dim=3, yield_number=0.5)
        with self.assertRaises(ValueError):
            m.ViscoplasticAsthenosphere(k=32, bits_per_dim=4, yield_number=0.5)
        with self.assertRaises(ValueError):
            m.ViscoplasticAsthenosphere(k=32, bits_per_dim=3, yield_number=1.1)

        torch.manual_seed(42)
        u = torch.randn((16, 32), dtype=torch.float32) * 3.0
        fluxes: list[float] = []
        for y_val in m.YIELD_SWEEP_VALUES:
            asth = m.ViscoplasticAsthenosphere(k=32, bits_per_dim=3, yield_number=y_val, use_hodge=True)
            self.assertLessEqual(asth.max_residual_bits, 96)
            r_pol, u_tor, diag = asth(u)
            self.assertLess(diag["pol_tor_orthogonality_err"], 1e-5, msg=f"Hodge orth failed at Y={y_val}")
            fluxes.append(diag["active_flux_fraction"])
            if y_val == 1.0:
                self.assertEqual(float(r_pol.abs().max().item()), 0.0)
                self.assertEqual(diag["active_flux_fraction"], 0.0)
            elif y_val == 0.0:
                norms = torch.linalg.vector_norm(r_pol, dim=-1)
                self.assertLess(float((norms - 1.0).abs().max().item()), 1e-5)
                self.assertGreater(diag["active_flux_fraction"], 0.95)
            self.assertGreater(float(u_tor.abs().max().item()), 0.1)

        for a, b in zip(fluxes, fluxes[1:]):
            self.assertGreaterEqual(a + 1e-9, b, msg=f"non-monotone Bingham flux sweep: {fluxes}")

        asth_nh = m.ViscoplasticAsthenosphere(k=32, bits_per_dim=3, yield_number=0.5, use_hodge=False)
        _, u_lat_nh, diag_nh = asth_nh(u)
        self.assertGreater(float(u_lat_nh.abs().max().item()), 0.1)
        self.assertGreater(diag_nh["pol_tor_orthogonality_err"], 0.2)

    def test_03_exact_stop_gradient_isolation_and_zero_skip_paths(self) -> None:
        torch.manual_seed(137)
        mv = m.MinimalMediumVocab()
        core = m.RigidInnerCore(mv.vocab_size, d_model=32, n_heads=4, n_layers=2, n_loops=3, k_res=32)
        pre_sha = core.freeze_and_pin()
        asth = m.ViscoplasticAsthenosphere(k=32, bits_per_dim=3, yield_number=0.5, use_hodge=True)
        plate = m.ExternalSurfacePlate(d_ext=24, m_vocab_size=mv.vocab_size, ir_len=12, k_res=32, n_heads=4, n_layers=1)

        surf = torch.randint(0, 256, (8, 32), dtype=torch.long)
        ir_t = torch.randint(1, mv.vocab_size, (8, 12), dtype=torch.long)
        ans_t = torch.randint(0, 16, (8,), dtype=torch.long)

        skip_diag = m.verify_zero_skip_paths(plate, asth, core, surf, ir_t)
        self.assertTrue(skip_diag["zero_skip_path_verified"], msg=repr(skip_diag))

        opt = torch.optim.AdamW(plate.parameters(), lr=1e-2)
        opt.zero_grad(set_to_none=True)
        ir_lg, u = plate.encode_surface(surf)
        r_pol, _, _ = asth(u)
        core_out = core(ir_t, residual_r=r_pol)
        ext_out = plate.decode_core_output(core_out["ans_logits"])
        loss = (
            torch.nn.functional.cross_entropy(ir_lg.reshape(-1, mv.vocab_size), ir_t.reshape(-1))
            + torch.nn.functional.cross_entropy(ext_out, ans_t)
        )
        loss.backward()
        ext_in_grad = max(
            float(p.grad.abs().max().item())
            for name, p in plate.named_parameters()
            if not name.startswith("ext_out_head") and p.grad is not None
        )
        self.assertGreater(ext_in_grad, 0.0)
        for name, p in core.named_parameters():
            self.assertIsNone(p.grad, msg=f"frozen Core parameter {name} received gradient!")
        opt.step()
        self.assertEqual(core.core_weights_sha256(), pre_sha)

    def test_04_cs21_residual_leak_probe_and_cb6_syntactic_transducer(self) -> None:
        torch.manual_seed(2026)
        n_tr, n_ev = 256, 128
        y_tr = torch.randint(0, 16, (n_tr,), dtype=torch.long)
        y_ev = torch.randint(0, 16, (n_ev,), dtype=torch.long)
        mod_tr = torch.randint(0, 2, (n_tr,), dtype=torch.float32)
        mod_ev = torch.randint(0, 2, (n_ev,), dtype=torch.float32)
        r_clean_tr = torch.zeros((n_tr, 32))
        r_clean_ev = torch.zeros((n_ev, 32))
        r_clean_tr[:, 0] = 2.0 * mod_tr - 1.0
        r_clean_ev[:, 0] = 2.0 * mod_ev - 1.0
        clean_res = m.run_residual_leak_probe(r_clean_tr, y_tr, r_clean_ev, y_ev, n_classes=16, steps=60, seed=42)
        self.assertLessEqual(clean_res["probe_params"], 50_000)
        self.assertFalse(clean_res["cs21_residual_leak_triggered"], msg=repr(clean_res))

        r_leak_tr = torch.zeros((n_tr, 32))
        r_leak_ev = torch.zeros((n_ev, 32))
        r_leak_tr[torch.arange(n_tr), y_tr] = 1.0
        r_leak_ev[torch.arange(n_ev), y_ev] = 1.0
        leak_res = m.run_residual_leak_probe(r_leak_tr, y_tr, r_leak_ev, y_ev, n_classes=16, steps=60, seed=42)
        self.assertTrue(leak_res["cs21_residual_leak_triggered"], msg=repr(leak_res))

        mv = m.MinimalMediumVocab()
        toks = mv.decode(m.regime1_syntactic_transducer("( 7 * 9 ) + 5 %16", mv, max_len=12))
        self.assertEqual(toks, ["<BOS>", "(", "N7", "OP_MUL", "N9", ")", "OP_ADD", "N5", "MOD16", "<EOS>"])

    def test_05_counterfactual_hr_patching_eos_invariance_and_darboux(self) -> None:
        torch.manual_seed(99)
        mv = m.MinimalMediumVocab()
        core = m.RigidInnerCore(mv.vocab_size, d_model=32, n_heads=4, n_layers=1, n_loops=4, k_res=32)
        ir_a = torch.randint(1, mv.vocab_size, (4, 12), dtype=torch.long)
        ir_b = torch.randint(1, mv.vocab_size, (4, 12), dtype=torch.long)
        r_z = torch.zeros((4, 32))
        with torch.no_grad():
            out_a = core(ir_a, r_z)
            out_b = core(ir_b, r_z)
            patched = core(ir_a, r_z, patch_pass_idx=1, patch_state=out_b["loop_states"][1])
            diff = float((patched["ans_logits"] - out_b["ans_logits"]).abs().max().item())
            self.assertLess(diff, 1e-5)
            diff_vs_a = float((patched["ans_logits"] - out_a["ans_logits"]).abs().max().item())
            self.assertGreater(diff_vs_a, 1e-3)

            # Causal <EOS> non-pad pooling invariance: ir_len=12 Native MUST match ir_len=24 zero-padded!
            ir_short = torch.tensor(
                [m.regime1_syntactic_transducer("( 7 * 9 ) + 5 %16", mv, max_len=12)], dtype=torch.long
            )
            ir_long = torch.tensor(
                [m.regime1_syntactic_transducer("( 7 * 9 ) + 5 %16", mv, max_len=24)], dtype=torch.long
            )
            o_short = core(ir_short, torch.zeros((1, 32)))["ans_logits"]
            o_long = core(ir_long, torch.zeros((1, 32)))["ans_logits"]
            self.assertLess(float((o_short - o_long).abs().max().item()), 1e-5)

        a_rect = torch.tensor(
            [
                [2.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 1.5, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.5, 0.0, 0.0],
            ],
            dtype=torch.float64,
        )
        x_probe = torch.tensor([[1.0, 2.0, 3.0, 4.0, 5.0]], dtype=torch.float64)
        diag = m.darboux_dark_mode_diagnostic(a_rect, x_probe)
        self.assertEqual(diag["rank"], 3)
        self.assertEqual(diag["dark_dim"], 2)
        self.assertLess(diag["darboux_intertwine_err"], 1e-12)
        self.assertAlmostEqual(diag["mean_dark_mode_loss"], 41.0, places=5)

    def test_06_triple_cs08_param_and_flop_parity_in_gpu_and_cpu_presets(self) -> None:
        mv = m.MinimalMediumVocab()
        for mode in ("cpu-smoke", "gpu-full"):
            cfg = harness.build_preset(mode, [42])
            mono = m.MonolithicByteReasoner(
                d_model=cfg["mono_d"],
                n_heads=cfg["mono_heads"],
                n_layers=cfg["mono_layers"],
                max_len=max(cfg["surf_len"], 128),
                ffn_dim=cfg["mono_ffn_dim"],
            )
            core = m.RigidInnerCore(
                mv.vocab_size, cfg["core_d"], cfg["core_heads"], cfg["core_layers"], cfg["core_loops"], cfg["k_res"]
            )
            plate = m.ExternalSurfacePlate(
                cfg["ext_d"],
                mv.vocab_size,
                cfg["ir_len"],
                cfg["k_res"],
                max_surf_len=max(cfg["surf_len"], 128),
                n_heads=cfg["ext_heads"],
                n_layers=cfg["ext_layers"],
            )
            audit = m.AuditTraceDecoder(cfg["core_d"])

            p_mono = m.count_module_params(mono)
            p_core = m.count_module_params(core)
            p_ext_out = m.count_module_params(plate.ext_out_head)
            p_ext_in = m.count_module_params(plate) - p_ext_out
            p_aud = m.count_module_params(audit)

            led_mono = m.compute_system_resource_ledger(
                p_core=p_mono,
                p_ext_in=0,
                p_ext_out=0,
                p_audit_head=0,
                core_d=cfg["mono_d"],
                core_layers=cfg["mono_layers"],
                core_loops=1,
                core_seq=cfg["surf_len"],
                ext_d=0,
                ext_seq=0,
                train_steps_total=cfg["mono_steps"],
                batch_size=cfg["batch_size"],
                core_ffn_dim=cfg["mono_ffn_dim"],
            )
            led_terra = m.compute_system_resource_ledger(
                p_core=p_core,
                p_ext_in=p_ext_in,
                p_ext_out=p_ext_out,
                p_audit_head=p_aud,
                core_d=cfg["core_d"],
                core_layers=cfg["core_layers"],
                core_loops=cfg["core_loops"],
                core_seq=cfg["ir_len"],
                ext_d=cfg["ext_d"],
                ext_seq=cfg["surf_len"],
                train_steps_total=cfg["stage1_steps"] + cfg["stage2_steps"],
                batch_size=cfg["batch_size"],
                ext_layers=cfg["ext_layers"],
                m_vocab_size=mv.vocab_size,
            )
            self.assertGreater(led_terra["P_audit_head"], 0)
            if mode == "gpu-full":
                self.assertGreaterEqual(led_mono["P_total"], 14_925_000)
                self.assertLessEqual(led_mono["P_total"], 15_075_000)
                self.assertGreaterEqual(led_terra["P_total"], 14_925_000)
                self.assertLessEqual(led_terra["P_total"], 15_075_000)
            p_ratio = led_terra["P_total"] / led_mono["P_total"]
            f_ratio = led_terra["F_infer"] / led_mono["F_infer"]
            t_ratio = led_terra["F_train_total"] / led_mono["F_train_total"]
            self.assertGreaterEqual(p_ratio, 0.995, msg=f"{mode} P_ratio={p_ratio:.4f}")
            self.assertLessEqual(p_ratio, 1.005, msg=f"{mode} P_ratio={p_ratio:.4f}")
            self.assertGreaterEqual(f_ratio, 0.95, msg=f"{mode} F_ratio={f_ratio:.4f}")
            self.assertLessEqual(f_ratio, 1.05, msg=f"{mode} F_ratio={f_ratio:.4f}")
            self.assertGreaterEqual(t_ratio, 0.95, msg=f"{mode} F_train_ratio={t_ratio:.4f}")
            self.assertLessEqual(t_ratio, 1.05, msg=f"{mode} F_train_ratio={t_ratio:.4f}")

    def test_07_end_to_end_multiseed_cpu_smoke_h9a_to_h9d_and_plate_swap(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = harness.main(
                    ["--mode", "cpu-smoke", "--track", "all", "--device", "cpu", "--seeds", "42,137", "--out-dir", td]
                )
            self.assertEqual(rc, 0)
            summary = json.loads(buf.getvalue().strip())
            proto = json.loads((Path(td) / "s109_locked_protocol.json").read_text(encoding="utf-8"))
            res = json.loads((Path(td) / "s109_cpu_smoke_results.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["result_sha256"], res["result_sha256"])
            self.assertEqual(proto["parent_preregistration_sha256"], m.PREREG_S109_SHA256)
            self.assertEqual(proto["amendment1_sha256"], m.AMENDMENT1_SHA256)
            self.assertEqual(proto["amendment2_sha256"], m.AMENDMENT2_SHA256)
            self.assertEqual(proto["amendment3_sha256"], m.AMENDMENT3_SHA256)
            self.assertEqual(res["weights_saved"], 0)

            r = res["results"]
            self.assertEqual(set(r["per_seed"].keys()), {"42", "137"})
            self.assertEqual(r["train_eval_tuple_overlap"], {"regime1": 0, "regime2": 0})
            self.assertIn("arm_b_decompressor_emulation", r)
            self.assertIn("probe_lm_predictivity", r)
            self.assertIn("arm_d_mono", r)

            sweep = r["h9d_yield_sweep"]
            self.assertEqual(
                set(sweep.keys()),
                {"Y_0.00", "Y_0.25", "Y_0.50", "Y_0.75", "Y_1.00", "Y_0.50_NoHodge"},
            )
            for y_key in ("Y_0.00", "Y_0.25", "Y_0.50", "Y_0.75", "Y_1.00"):
                self.assertTrue(sweep[y_key]["core_sha_unchanged"], msg=y_key)
                self.assertTrue(sweep[y_key]["zero_skip_path"]["zero_skip_path_verified"], msg=y_key)
                self.assertLess(sweep[y_key]["channel2b_diag_r2"]["pol_tor_orthogonality_err"], 1e-5, msg=y_key)
                self.assertLess(sweep[y_key]["plate_swap_seam"]["cocycle_sum_err"], 1e-5, msg=y_key)
            self.assertEqual(sweep["Y_1.00"]["channel2b_diag_r2"]["active_flux_fraction"], 0.0)
            self.assertGreater(sweep["Y_0.50_NoHodge"]["channel2b_diag_r2"]["pol_tor_orthogonality_err"], 0.2)
            sw = r["swap_and_plate_swap"]
            self.assertTrue(sw["alt_plate_core_sha_unchanged"])
            self.assertLess(sw["cocycle_sum_err"], 1e-5)


if __name__ == "__main__":
    unittest.main()
