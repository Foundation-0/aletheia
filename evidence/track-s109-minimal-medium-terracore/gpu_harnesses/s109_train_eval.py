#!/usr/bin/env python3
"""Track S109 (PREREG-S109 + Amendments 1, 2, & 3 TerraCore) Multi-Seed Training & Evaluation Harness.

Implements all 4 locked hypotheses (H9a, H9b, H9c, H9d) with strict Amendment 1/2/3 gates:
  - Strictly tuple-disjoint train/eval splits (0% (a, b, c, op) overlap), zero UTF-8 truncation (surf_len=128).
  - Multi-seed execution (e.g. --seeds 42,137,2026) with paired-seed SE, z-scores, and 95% bootstrap CIs.
  - H9a: Arm A (2-step English-CoT-15M), Arm A' (Direct-Answer-15M), Arm B (Raw-Deflate-15M),
    Arm B Decompressor-Emulation Control, and Auxiliary Probe-LM bits/bit predictivity.
  - Stage 1: Zero-language SteelmanCore (M -> M, W10-OBS-31 non-antipodal Hopf clock, causal <EOS> pooling,
    h^(mid) latent-CoT supervision) + AuditTraceDecoder trained on canonical Poloidal chart Q_0 ->
    FROZEN & SHA-256 pinned.
  - Arm D-mono: End-to-end unfrozen monolithic anchor quantifying exact modularity cost.
  - Stage 2: Modular Shell-3 MHPlate external plates trained with strict stop_gradient into frozen Core
    (ZERO oracle modifier supervision; zero Core param grads; bit-exact Core SHA-256 invariant).
  - H9d 5-point Bingham Yield sweep Y in {0, 1/4, 1/2, 3/4, 1} + non-strawman matched-rank NoHodge ablation:
    EVERY Y arm evaluated on Regime I (Native CB-6 Transducer ir_len=12 + Learned Plate), Regime II,
    DPI loss & error decomposition, <= 50k MLP CS21_RESIDUAL_LEAK probe, counterfactual h^(r) state-patching
    audit faithfulness, within-system §SWAP, cross-surface Arabic §SWAP, multi-plate §PLATE-SWAP seam
    composition with exact cocycle conservation sum(alpha_i) = 1, and Portal-5 Darboux dark-mode diagnostic.
  - Full CB-1..CB-6 anti-smuggling controls and exact 15M triple CS-08 parity (±0.5% P, ±5% FLOPs).

Strictly CPU-safe (`--device cpu` default; refuses CUDA unless explicitly passed).
Saves ZERO model checkpoints (`WEIGHTS=0`); emits locked protocol + canonical JSON receipt.
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import time
from typing import Any, Sequence

import torch
import torch.nn as nn
import torch.nn.functional as F

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import s109_terracore_models as m  # noqa: E402


def seed_everything(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _autocast_ctx(device: torch.device) -> Any:
    if device.type == "cuda":
        return torch.amp.autocast(device_type="cuda", dtype=torch.bfloat16)
    return nullcontext()


def _sync_if_cuda(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def _reset_peak_vram(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)


def _peak_vram_mib(device: torch.device) -> float:
    if device.type == "cuda":
        return round(float(torch.cuda.max_memory_allocated(device)) / (1024.0 * 1024.0), 3)
    return 0.0


def _sample_batch_idx(n: int, batch_size: int, gen: torch.Generator, device: torch.device) -> torch.Tensor:
    if batch_size >= n:
        return torch.arange(n, device=device)
    return torch.randint(0, n, (batch_size,), generator=gen, dtype=torch.long).to(device)


def _cosine_lr(step: int, total_steps: int, base_lr: float) -> float:
    warmup = max(1, total_steps // 20)
    if step < warmup:
        return base_lr * float(step + 1) / float(warmup)
    prog = float(step - warmup) / float(max(1, total_steps - warmup))
    return base_lr * (0.1 + 0.9 * 0.5 * (1.0 + math.cos(math.pi * min(1.0, prog))))


def _set_lr(opt: torch.optim.Optimizer, lr: float) -> None:
    for pg in opt.param_groups:
        pg["lr"] = lr


def _batch_tensors(examples: Sequence[m.S109Example], surf_len: int, device: torch.device) -> dict[str, torch.Tensor]:
    return {
        "ir": torch.tensor([list(e.canonical_ir_ids) for e in examples], dtype=torch.long, device=device),
        "en": torch.tensor([m.encode_utf8_bytes_fixed(e.surface_en, surf_len) for e in examples], dtype=torch.long, device=device),
        "alt": torch.tensor([m.encode_utf8_bytes_fixed(e.surface_alt, surf_len) for e in examples], dtype=torch.long, device=device),
        "mix": torch.tensor([m.encode_utf8_bytes_fixed(e.surface_mixed, surf_len) for e in examples], dtype=torch.long, device=device),
        "deflate": torch.tensor([m.encode_raw_bytes_fixed(e.deflate_bytes, surf_len) for e in examples], dtype=torch.long, device=device),
        "inter": torch.tensor([e.intermediate for e in examples], dtype=torch.long, device=device),
        "ans": torch.tensor([e.answer for e in examples], dtype=torch.long, device=device),
        "mod": torch.tensor([e.modifier for e in examples], dtype=torch.long, device=device),
    }


def build_preset(mode: str, seeds: list[int]) -> dict[str, Any]:
    """Amendment-3 locked triple-parity presets (±0.5% of 15M & cross-arm, ±5% FLOPs)."""
    if mode == "cpu-smoke":
        # Exact triple parity: P_mono=337,280 vs P_terra=336,081 (-0.36%), F_infer/F_train (-1.20%)
        return {
            "mode": "cpu-smoke",
            "seeds": seeds,
            "n_regime1": 96,
            "n_regime2": 96,
            "ir_len": 16,
            "native_ir_len": 12,
            "surf_len": 48,
            "k_res": 32,
            "core_d": 96,
            "core_heads": 4,
            "core_layers": 2,
            "core_loops": 4,
            "ext_d": 84,
            "ext_heads": 4,
            "ext_layers": 1,
            "mono_d": 96,
            "mono_heads": 4,
            "mono_layers": 4,
            "mono_ffn_dim": 192,
            "batch_size": 32,
            "eval_batch_size": 64,
            "stage1_steps": 16,
            "stage2_steps": 16,
            "mono_steps": 32,
            "decomp_steps": 16,
            "probe_lm_steps": 12,
            "router_steps": 20,
            "lr": 4e-3,
            "lr_stage2": 4e-3,
        }
    if mode == "gpu-full":
        # Amendment-3 exact 15M triple parity (surf_len=128, zero UTF-8 truncation, head_dim=64 Tensor Core aligned!):
        # P_mono=15,023,648 (+0.16% of 15M) vs P_terra=15,003,063 (+0.02% of 15M, ratio=0.9986),
        # F_infer/F_train ratio=0.9949 (-0.51%), Core=10.58M + MHPlate+Audit=4.42M,
        # stage1_steps(1600) + stage2_steps(400) == mono_steps(2000)!
        return {
            "mode": "gpu-full",
            "seeds": seeds,
            "n_regime1": 8192,
            "n_regime2": 8192,
            "ir_len": 24,
            "native_ir_len": 12,
            "surf_len": 128,
            "k_res": 32,
            "core_d": 512,
            "core_heads": 8,
            "core_layers": 5,
            "core_loops": 6,
            "ext_d": 480,
            "ext_heads": 8,
            "ext_layers": 1,
            "mono_d": 512,
            "mono_heads": 8,
            "mono_layers": 7,
            "mono_ffn_dim": 1040,
            "batch_size": 128,
            "eval_batch_size": 256,
            "stage1_steps": 1600,
            "stage2_steps": 400,
            "mono_steps": 2000,
            "decomp_steps": 600,
            "probe_lm_steps": 250,
            "router_steps": 150,
            "lr": 6e-4,
            "lr_stage2": 8e-4,
        }
    raise ValueError(f"unsupported mode: {mode!r}")


# ---------------------------------------------------------------------------
# H9a Arms: Arm A (2-step English-CoT), Arm A' (Direct), Arm B (Deflate), Decompressor, Probe-LM
# ---------------------------------------------------------------------------


def _eval_mono_batches(
    model: m.MonolithicByteReasoner,
    x: torch.Tensor,
    y_ans: torch.Tensor,
    y_inter: torch.Tensor,
    use_cot: bool,
    eval_bs: int,
    device: torch.device,
) -> tuple[float, float, float, float]:
    model.eval()
    _reset_peak_vram(device)
    _sync_if_cuda(device)
    t0 = time.monotonic()
    n = int(x.shape[0])
    correct_ans = 0
    correct_inter = 0
    with torch.no_grad():
        for start in range(0, n, eval_bs):
            xb = x[start : start + eval_bs]
            with _autocast_ctx(device):
                out = model(xb, use_cot_conditioning=use_cot, teacher_inter=None)
            correct_ans += int((out["ans_logits"].float().argmax(dim=-1) == y_ans[start : start + eval_bs]).sum().item())
            correct_inter += int((out["inter_logits"].float().argmax(dim=-1) == y_inter[start : start + eval_bs]).sum().item())
    _sync_if_cuda(device)
    wall_ms = (time.monotonic() - t0) * 1000.0 / max(n, 1)
    peak_mib = _peak_vram_mib(device)
    return correct_ans / max(n, 1), correct_inter / max(n, 1), wall_ms, peak_mib


def _train_mono_arm(
    arm_name: str,
    input_key: str,
    use_cot_supervision: bool,
    tr_r1: dict[str, torch.Tensor],
    ev_r1: dict[str, torch.Tensor],
    tr_r2: dict[str, torch.Tensor],
    ev_r2: dict[str, torch.Tensor],
    cfg: dict[str, Any],
    seed: int,
    device: torch.device,
) -> dict[str, Any]:
    seed_everything(seed)
    gen = torch.Generator(device="cpu").manual_seed(seed + 11)
    model = m.MonolithicByteReasoner(
        d_model=cfg["mono_d"],
        n_heads=cfg["mono_heads"],
        n_layers=cfg["mono_layers"],
        n_classes=16,
        max_len=max(cfg["surf_len"], 128),
        ffn_dim=cfg["mono_ffn_dim"],
    ).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=0.01)
    x_tr = torch.cat([tr_r1[input_key], tr_r2[input_key]], dim=0)
    y_inter = torch.cat([tr_r1["inter"], tr_r2["inter"]], dim=0)
    y_ans = torch.cat([tr_r1["ans"], tr_r2["ans"]], dim=0)
    n_tr = int(x_tr.shape[0])
    bs = int(cfg["batch_size"])
    steps = int(cfg["mono_steps"])

    _reset_peak_vram(device)
    model.train()
    for step in range(steps):
        _set_lr(opt, _cosine_lr(step, steps, cfg["lr"]))
        idx = _sample_batch_idx(n_tr, bs, gen, device)
        opt.zero_grad(set_to_none=True)
        # Scheduled 2-step CoT: teacher-forced first 50% of steps, 100% self-predicted final 50% & eval!
        teacher = y_inter[idx] if (use_cot_supervision and step < steps // 2) else None
        with _autocast_ctx(device):
            out = model(x_tr[idx], use_cot_conditioning=use_cot_supervision, teacher_inter=teacher)
            loss = F.cross_entropy(out["ans_logits"].float(), y_ans[idx])
            if use_cot_supervision:
                loss = loss + 1.0 * F.cross_entropy(out["inter_logits"].float(), y_inter[idx])
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
    train_peak_mib = _peak_vram_mib(device)

    acc_r1, inter_r1, ms_r1, vram_r1 = _eval_mono_batches(
        model, ev_r1[input_key], ev_r1["ans"], ev_r1["inter"], use_cot_supervision, int(cfg["eval_batch_size"]), device
    )
    acc_r2, inter_r2, ms_r2, vram_r2 = _eval_mono_batches(
        model, ev_r2[input_key], ev_r2["ans"], ev_r2["inter"], use_cot_supervision, int(cfg["eval_batch_size"]), device
    )
    p_tot = m.count_module_params(model)
    ledger = m.compute_system_resource_ledger(
        p_core=p_tot,
        p_ext_in=0,
        p_ext_out=0,
        p_audit_head=0,
        core_d=cfg["mono_d"],
        core_layers=cfg["mono_layers"],
        core_loops=1,
        core_seq=cfg["surf_len"],
        ext_d=0,
        ext_seq=0,
        train_steps_total=steps,
        batch_size=bs,
        core_ffn_dim=cfg["mono_ffn_dim"],
    )
    return {
        "arm": arm_name,
        "seed": seed,
        "regime1_exact_acc": round(acc_r1, 6),
        "regime1_inter_acc": round(inter_r1, 6),
        "regime2_exact_acc": round(acc_r2, 6),
        "regime2_inter_acc": round(inter_r2, 6),
        "wall_ms_per_problem_r1": round(ms_r1, 4),
        "wall_ms_per_problem_r2": round(ms_r2, 4),
        "wall_ms_per_problem": round(0.5 * (ms_r1 + ms_r2), 4),
        "eval_peak_vram_mib": round(max(vram_r1, vram_r2), 3),
        "train_peak_vram_mib": train_peak_mib,
        "resource_ledger": ledger,
    }


def _train_decompressor_emulation(
    tr_r1: dict[str, torch.Tensor],
    ev_r1: dict[str, torch.Tensor],
    tr_r2: dict[str, torch.Tensor],
    ev_r2: dict[str, torch.Tensor],
    cfg: dict[str, Any],
    seed: int,
    device: torch.device,
) -> dict[str, Any]:
    """AMENDMENT1 §4.2 Decompressor-Emulation Control: can the 15M core invert raw-deflate -> UTF-8 bytes?"""
    seed_everything(seed + 41)
    gen = torch.Generator(device="cpu").manual_seed(seed + 41)
    model = m.ByteStreamProbeAndDecompressor(
        d_model=cfg["mono_d"],
        n_heads=cfg["mono_heads"],
        n_layers=cfg["mono_layers"],
        max_len=max(cfg["surf_len"], 128),
        ffn_dim=cfg["mono_ffn_dim"],
    ).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=0.01)
    x_tr = torch.cat([tr_r1["deflate"], tr_r2["deflate"]], dim=0)
    y_tr = torch.cat([tr_r1["en"], tr_r2["en"]], dim=0)
    n_tr = int(x_tr.shape[0])
    bs = int(cfg["batch_size"])
    steps = int(cfg["decomp_steps"])

    model.train()
    for step in range(steps):
        _set_lr(opt, _cosine_lr(step, steps, cfg["lr"]))
        idx = _sample_batch_idx(n_tr, bs, gen, device)
        opt.zero_grad(set_to_none=True)
        with _autocast_ctx(device):
            logits = model(x_tr[idx])
            loss = F.cross_entropy(logits.float().reshape(-1, 256), y_tr[idx].reshape(-1))
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()

    def _eval_decomp(x_ev: torch.Tensor, y_ev: torch.Tensor) -> tuple[float, float]:
        model.eval()
        ev_bs = int(cfg["eval_batch_size"])
        n = int(x_ev.shape[0])
        nonpad_correct = 0
        nonpad_total = 0
        exact_seq = 0
        with torch.no_grad():
            for s in range(0, n, ev_bs):
                xb = x_ev[s : s + ev_bs]
                yb = y_ev[s : s + ev_bs]
                with _autocast_ctx(device):
                    preds = model(xb).float().argmax(dim=-1)
                mask = yb != 0
                nonpad_correct += int(((preds == yb) & mask).sum().item())
                nonpad_total += int(mask.sum().item())
                exact_seq += int(((preds == yb) | (~mask)).all(dim=-1).sum().item())
        return nonpad_correct / max(nonpad_total, 1), exact_seq / max(n, 1)

    r1_bacc, r1_exact = _eval_decomp(ev_r1["deflate"], ev_r1["en"])
    r2_bacc, r2_exact = _eval_decomp(ev_r2["deflate"], ev_r2["en"])
    return {
        "regime1_byte_acc": round(r1_bacc, 6),
        "regime1_exact_str_acc": round(r1_exact, 6),
        "regime2_byte_acc": round(r2_bacc, 6),
        "regime2_exact_str_acc": round(r2_exact, 6),
        "p_total": m.count_module_params(model),
    }


def _train_probe_lm_bits_per_bit(
    tr_streams: torch.Tensor,
    ev_streams: torch.Tensor,
    cfg: dict[str, Any],
    seed: int,
    device: torch.device,
) -> dict[str, float]:
    """AMENDMENT1 §4.2 Auxiliary Probe-LM Predictivity in bits/byte and bits/bit on non-pad stream."""
    seed_everything(seed + 73)
    gen = torch.Generator(device="cpu").manual_seed(seed + 73)
    d_probe = min(256, int(cfg["mono_d"]))
    n_heads = 4
    n_layers = min(4, int(cfg["mono_layers"]))
    model = m.ByteStreamProbeAndDecompressor(
        d_model=d_probe, n_heads=n_heads, n_layers=n_layers, max_len=max(cfg["surf_len"], 128)
    ).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=0.01)
    n_tr = int(tr_streams.shape[0])
    bs = int(cfg["batch_size"])
    steps = int(cfg["probe_lm_steps"])

    model.train()
    for step in range(steps):
        _set_lr(opt, _cosine_lr(step, steps, cfg["lr"]))
        idx = _sample_batch_idx(n_tr, bs, gen, device)
        xb = tr_streams[idx, :-1]
        yb = tr_streams[idx, 1:]
        mask = yb != 0
        opt.zero_grad(set_to_none=True)
        with _autocast_ctx(device):
            logits = model(xb).float()
            tok_loss = F.cross_entropy(logits.reshape(-1, 256), yb.reshape(-1), reduction="none").reshape_as(yb)
            loss = (tok_loss * mask.float()).sum() / mask.float().sum().clamp_min(1.0)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()

    model.eval()
    ev_bs = int(cfg["eval_batch_size"])
    tot_nats = 0.0
    tot_bytes = 0
    with torch.no_grad():
        for s in range(0, int(ev_streams.shape[0]), ev_bs):
            xb = ev_streams[s : s + ev_bs, :-1]
            yb = ev_streams[s : s + ev_bs, 1:]
            mask = yb != 0
            with _autocast_ctx(device):
                logits = model(xb).float()
            tok_loss = F.cross_entropy(logits.reshape(-1, 256), yb.reshape(-1), reduction="none").reshape_as(yb)
            tot_nats += float((tok_loss * mask.float()).sum().item())
            tot_bytes += int(mask.sum().item())
    bpb = (tot_nats / max(tot_bytes, 1)) / math.log(2.0)
    return {
        "probe_lm_bits_per_byte": round(bpb, 6),
        "probe_lm_bits_per_bit": round(bpb / 8.0, 6),
    }


# ---------------------------------------------------------------------------
# Stage 1 Frozen Core, Arm D-mono, Stage 2 Plates, CB-1..CB-6, §SWAP, §PLATE-SWAP
# ---------------------------------------------------------------------------


def _run_cb6_syntactic_check(
    tr_r1: dict[str, torch.Tensor],
    ev_r1: dict[str, torch.Tensor],
    v_m: int,
    device: torch.device,
    mode: str,
) -> dict[str, Any]:
    """CB-6: verify Regime-I syntactic transducer yields <= chance + 5 pp on a trivial bag-of-tokens baseline."""
    torch.manual_seed(109006)
    bag_lin = nn.Linear(v_m, 16).to(device)
    opt = torch.optim.AdamW(bag_lin.parameters(), lr=2e-2)

    def bag_feat(ir: torch.Tensor) -> torch.Tensor:
        return F.one_hot(ir, num_classes=v_m).float().mean(dim=1)

    x_tr = bag_feat(tr_r1["ir"])
    x_ev = bag_feat(ev_r1["ir"])
    for _ in range(60):
        opt.zero_grad(set_to_none=True)
        F.cross_entropy(bag_lin(x_tr), tr_r1["ans"]).backward()
        opt.step()
    with torch.no_grad():
        acc = float((bag_lin(x_ev).argmax(dim=-1) == ev_r1["ans"]).float().mean().item())
    chance = 1.0 / 16.0
    tol = 0.05 if mode == "gpu-full" else 0.15
    return {
        "trivial_core_acc": round(acc, 6),
        "chance_acc": round(chance, 6),
        "above_chance": round(acc - chance, 6),
        "cb6_tolerance": tol,
        "cb6_syntactic_only_pass": acc <= chance + tol,
    }


def _train_stage1_frozen_core(
    tr_r1: dict[str, torch.Tensor],
    tr_r2: dict[str, torch.Tensor],
    cfg: dict[str, Any],
    m_vocab_size: int,
    seed: int,
    device: torch.device,
) -> tuple[m.RigidInnerCore, m.AuditTraceDecoder, str, float]:
    """Stage 1: train zero-language SteelmanCore (M -> M) + AuditTraceDecoder on canonical Poloidal chart Q_0."""
    seed_everything(seed)
    gen = torch.Generator(device="cpu").manual_seed(seed + 101)
    core = m.RigidInnerCore(
        m_vocab_size=m_vocab_size,
        d_model=cfg["core_d"],
        n_heads=cfg["core_heads"],
        n_layers=cfg["core_layers"],
        n_loops=cfg["core_loops"],
        k_res=cfg["k_res"],
        n_classes=16,
    ).to(device)
    audit_dec = m.AuditTraceDecoder(d_model=cfg["core_d"], n_classes=16).to(device)
    opt = torch.optim.AdamW(list(core.parameters()) + list(audit_dec.parameters()), lr=cfg["lr"], weight_decay=0.01)

    q0 = m.canonical_poloidal_axis(cfg["k_res"], device=device)
    ir_tr = torch.cat([tr_r1["ir"], tr_r2["ir"]], dim=0)
    mod_tr = torch.cat([tr_r1["mod"], tr_r2["mod"]], dim=0)
    inter_tr = torch.cat([tr_r1["inter"], tr_r2["inter"]], dim=0)
    ans_tr = torch.cat([tr_r1["ans"], tr_r2["ans"]], dim=0)
    is_r2_tr = torch.cat(
        [
            torch.zeros(tr_r1["ir"].shape[0], dtype=torch.bool, device=device),
            torch.ones(tr_r2["ir"].shape[0], dtype=torch.bool, device=device),
        ],
        dim=0,
    )
    n_tr = int(ir_tr.shape[0])
    bs = int(cfg["batch_size"])
    steps = int(cfg["stage1_steps"])
    mid_idx = max(0, cfg["core_loops"] // 2 - 1)

    _reset_peak_vram(device)
    core.train()
    audit_dec.train()
    for step in range(steps):
        _set_lr(opt, _cosine_lr(step, steps, cfg["lr"]))
        idx = _sample_batch_idx(n_tr, bs, gen, device)
        ir_b = ir_tr[idx]
        mod_b = mod_tr[idx]
        inter_b = inter_tr[idx]
        ans_b = ans_tr[idx]
        r2_b = is_r2_tr[idx]

        signs = (2.0 * mod_b.float() - 1.0).unsqueeze(-1)
        r_canon = signs * q0.unsqueeze(0)
        jitter = torch.randn_like(r_canon) * 0.08
        r_canon = m.safe_clamped_unit(r_canon + jitter, dim=-1)
        keep_mask = torch.where(
            r2_b,
            torch.rand((ir_b.shape[0],), device=device) < 0.85,
            torch.rand((ir_b.shape[0],), device=device) < 0.15,
        )
        r_canon = r_canon * keep_mask.float().unsqueeze(-1)

        opt.zero_grad(set_to_none=True)
        with _autocast_ctx(device):
            out = core(ir_b, residual_r=r_canon)
            aud_inter, aud_ans = audit_dec(out["loop_states"][mid_idx], last_idx=out["last_idx"])
            loss = (
                F.cross_entropy(out["ans_logits"].float(), ans_b)
                + 1.0 * F.cross_entropy(out["inter_logits"].float(), inter_b)
                + 0.4 * F.cross_entropy(aud_inter.float(), inter_b)
                + 0.4 * F.cross_entropy(aud_ans.float(), ans_b)
            )
        loss.backward()
        torch.nn.utils.clip_grad_norm_(list(core.parameters()) + list(audit_dec.parameters()), 1.0)
        opt.step()
    peak_mib = _peak_vram_mib(device)

    core_sha = core.freeze_and_pin()
    for p in audit_dec.parameters():
        p.requires_grad_(False)
    core.eval()
    audit_dec.eval()
    return core, audit_dec, core_sha, peak_mib


def _train_stage2_plate(
    core: m.RigidInnerCore,
    astheno: m.ViscoplasticAsthenosphere,
    surface_key: str,
    tr_r1: dict[str, torch.Tensor],
    tr_r2: dict[str, torch.Tensor],
    cfg: dict[str, Any],
    m_vocab_size: int,
    seed: int,
    device: torch.device,
    r1_only: bool = False,
) -> tuple[m.ExternalSurfacePlate, bool]:
    """Stage 2: train MHPlate with strict stop_gradient into frozen SHA-pinned Core (ZERO oracle mod labels!)."""
    seed_everything(seed)
    gen = torch.Generator(device="cpu").manual_seed(seed + 202)
    pre_sha = core.core_weights_sha256()
    plate = m.ExternalSurfacePlate(
        d_ext=cfg["ext_d"],
        m_vocab_size=m_vocab_size,
        ir_len=cfg["ir_len"],
        k_res=cfg["k_res"],
        n_classes=16,
        max_surf_len=max(cfg["surf_len"], 128),
        n_heads=cfg["ext_heads"],
        n_layers=cfg["ext_layers"],
    ).to(device)
    lr2 = float(cfg.get("lr_stage2", cfg["lr"]))
    opt = torch.optim.AdamW(plate.parameters(), lr=lr2, weight_decay=0.01)

    if r1_only:
        surf_tr = tr_r1[surface_key]
        ir_tr = tr_r1["ir"]
        ans_tr = tr_r1["ans"]
    else:
        surf_tr = torch.cat([tr_r1[surface_key], tr_r2[surface_key]], dim=0)
        ir_tr = torch.cat([tr_r1["ir"], tr_r2["ir"]], dim=0)
        ans_tr = torch.cat([tr_r1["ans"], tr_r2["ans"]], dim=0)

    n_tr = int(surf_tr.shape[0])
    bs = int(cfg["batch_size"])
    steps = int(cfg["stage2_steps"] // 2 if r1_only else cfg["stage2_steps"])

    plate.train()
    core.eval()
    for step in range(steps):
        _set_lr(opt, _cosine_lr(step, steps, lr2))
        idx = _sample_batch_idx(n_tr, bs, gen, device)
        surf_b = surf_tr[idx]
        ir_b = ir_tr[idx]
        ans_b = ans_tr[idx]

        opt.zero_grad(set_to_none=True)
        with _autocast_ctx(device):
            ir_logits, u = plate.encode_surface(surf_b)
            r_pol, _, _ = astheno(u)
            ir_loss = F.cross_entropy(ir_logits.float().reshape(-1, m_vocab_size), ir_b.reshape(-1))
            ir_for_core = ir_logits.detach().argmax(dim=-1) if step >= (3 * steps) // 4 else ir_b
            # Frozen Core forward: core params have requires_grad=False; input grad trains r_pol only!
            core_out = core(ir_for_core, residual_r=r_pol)
            core_task_loss = (
                F.cross_entropy(core_out["ans_logits"].float(), ans_b)
                if astheno.yield_number < 1.0
                else torch.zeros((), device=device)
            )
            ext_out_logits = plate.decode_core_output(core_out["ans_logits"].detach())
            out_loss = F.cross_entropy(ext_out_logits.float(), ans_b)
            loss = ir_loss + 1.0 * core_task_loss + 0.5 * out_loss
        loss.backward()
        for p in core.parameters():
            if p.grad is not None:
                raise RuntimeError("Stage-2 stop_gradient violation: frozen Core received gradient!")
        torch.nn.utils.clip_grad_norm_(plate.parameters(), 1.0)
        opt.step()

    post_sha = core.core_weights_sha256()
    if post_sha != pre_sha:
        raise RuntimeError("frozen Core weights SHA-256 mutated during Stage-2 training!")
    plate.eval()
    return plate, (post_sha == pre_sha)


def _train_arm_d_mono(
    tr_r1: dict[str, torch.Tensor],
    ev_r1: dict[str, torch.Tensor],
    tr_r2: dict[str, torch.Tensor],
    ev_r2: dict[str, torch.Tensor],
    cfg: dict[str, Any],
    m_vocab_size: int,
    seed: int,
    device: torch.device,
) -> dict[str, Any]:
    """AMENDMENT1 §3.2 Arm D-mono: end-to-end unfrozen monolithic control quantifying exact modularity cost."""
    seed_everything(seed + 303)
    gen = torch.Generator(device="cpu").manual_seed(seed + 303)
    core = m.RigidInnerCore(
        m_vocab_size=m_vocab_size,
        d_model=cfg["core_d"],
        n_heads=cfg["core_heads"],
        n_layers=cfg["core_layers"],
        n_loops=cfg["core_loops"],
        k_res=cfg["k_res"],
        n_classes=16,
    ).to(device)
    audit_dec = m.AuditTraceDecoder(d_model=cfg["core_d"], n_classes=16).to(device)
    plate = m.ExternalSurfacePlate(
        d_ext=cfg["ext_d"],
        m_vocab_size=m_vocab_size,
        ir_len=cfg["ir_len"],
        k_res=cfg["k_res"],
        n_classes=16,
        max_surf_len=max(cfg["surf_len"], 128),
        n_heads=cfg["ext_heads"],
        n_layers=cfg["ext_layers"],
    ).to(device)
    astheno = m.ViscoplasticAsthenosphere(k=cfg["k_res"], bits_per_dim=3, yield_number=0.5, use_hodge=True).to(device)

    all_params = list(core.parameters()) + list(audit_dec.parameters()) + list(plate.parameters())
    opt = torch.optim.AdamW(all_params, lr=cfg["lr"], weight_decay=0.01)

    surf_tr = torch.cat([tr_r1["en"], tr_r2["en"]], dim=0)
    ir_tr = torch.cat([tr_r1["ir"], tr_r2["ir"]], dim=0)
    inter_tr = torch.cat([tr_r1["inter"], tr_r2["inter"]], dim=0)
    ans_tr = torch.cat([tr_r1["ans"], tr_r2["ans"]], dim=0)
    n_tr = int(surf_tr.shape[0])
    bs = int(cfg["batch_size"])
    steps = int(cfg["mono_steps"])
    mid_idx = max(0, cfg["core_loops"] // 2 - 1)

    core.train()
    audit_dec.train()
    plate.train()
    for step in range(steps):
        _set_lr(opt, _cosine_lr(step, steps, cfg["lr"]))
        idx = _sample_batch_idx(n_tr, bs, gen, device)
        surf_b = surf_tr[idx]
        ir_b = ir_tr[idx]
        inter_b = inter_tr[idx]
        ans_b = ans_tr[idx]

        opt.zero_grad(set_to_none=True)
        with _autocast_ctx(device):
            ir_logits, u = plate.encode_surface(surf_b)
            r_pol, _, _ = astheno(u)
            probs = F.softmax(ir_logits.float(), dim=-1)
            hard_idx = ir_logits.argmax(dim=-1)
            hard_oh = F.one_hot(hard_idx, num_classes=m_vocab_size).float()
            ste_oh = (hard_oh - probs.detach() + probs).to(core.m_emb.weight.dtype)
            soft_emb = torch.matmul(ste_oh, core.m_emb.weight)
            core_out = core(hard_idx, residual_r=r_pol, m_soft_embeds=soft_emb)
            aud_inter, aud_ans = audit_dec(core_out["loop_states"][mid_idx], last_idx=core_out["last_idx"])
            loss = (
                F.cross_entropy(core_out["ans_logits"].float(), ans_b)
                + 1.0 * F.cross_entropy(core_out["inter_logits"].float(), inter_b)
                + 0.5 * F.cross_entropy(ir_logits.float().reshape(-1, m_vocab_size), ir_b.reshape(-1))
                + 0.4 * F.cross_entropy(aud_inter.float(), inter_b)
                + 0.4 * F.cross_entropy(aud_ans.float(), ans_b)
            )
        loss.backward()
        torch.nn.utils.clip_grad_norm_(all_params, 1.0)
        opt.step()

    core.eval()
    audit_dec.eval()
    plate.eval()
    ev_bs = int(cfg["eval_batch_size"])
    acc_r1, _, ms_r1, vram_r1, _ = _eval_plate_core_batches(
        plate, astheno, core, ev_r1["en"], ev_r1["ir"], ev_r1["ans"], ev_bs, device
    )
    acc_r2, r_ev_r2, ms_r2, vram_r2, _ = _eval_plate_core_batches(
        plate, astheno, core, ev_r2["en"], ev_r2["ir"], ev_r2["ans"], ev_bs, device
    )
    r_tr_r2 = _collect_residuals(plate, astheno, tr_r2["en"], ev_bs, device)
    leak = m.run_residual_leak_probe(r_tr_r2, tr_r2["ans"], r_ev_r2, ev_r2["ans"], n_classes=16, seed=seed)
    cf_audit = _counterfactual_audit_faithfulness(core, audit_dec, ev_r2["ir"], r_ev_r2, ev_bs, device)
    return {
        "arm": "arm_d_mono_unfrozen",
        "seed": seed,
        "regime1_core_acc": round(acc_r1, 6),
        "regime2_core_acc": round(acc_r2, 6),
        "wall_ms_per_problem": round(0.5 * (ms_r1 + ms_r2), 4),
        "eval_peak_vram_mib": round(max(vram_r1, vram_r2), 3),
        "residual_leak_probe": leak,
        "counterfactual_audit": cf_audit,
    }


def _collect_residuals(
    plate: m.ExternalSurfacePlate,
    astheno: m.ViscoplasticAsthenosphere,
    surf: torch.Tensor,
    eval_bs: int,
    device: torch.device,
) -> torch.Tensor:
    plate.eval()
    chunks: list[torch.Tensor] = []
    with torch.no_grad():
        for s in range(0, int(surf.shape[0]), eval_bs):
            with _autocast_ctx(device):
                _, u = plate.encode_surface(surf[s : s + eval_bs])
                r_pol, _, _ = astheno(u)
            chunks.append(r_pol.float())
    return torch.cat(chunks, dim=0)


def _eval_plate_core_batches(
    plate: m.ExternalSurfacePlate,
    astheno: m.ViscoplasticAsthenosphere,
    core: m.RigidInnerCore,
    surf: torch.Tensor,
    true_ir: torch.Tensor,
    true_ans: torch.Tensor,
    eval_bs: int,
    device: torch.device,
) -> tuple[float, torch.Tensor, float, float, dict[str, Any]]:
    plate.eval()
    core.eval()
    _reset_peak_vram(device)
    _sync_if_cuda(device)
    t0 = time.monotonic()
    n = int(surf.shape[0])
    correct = 0
    ir_exact = 0
    r_chunks: list[torch.Tensor] = []
    diag_accum = {"pol_tor_orthogonality_err": 0.0, "channel2b_advection_norm": 0.0, "active_flux_fraction": 0.0}
    n_batches = 0
    with torch.no_grad():
        for s in range(0, n, eval_bs):
            sb = surf[s : s + eval_bs]
            irb = true_ir[s : s + eval_bs]
            yb = true_ans[s : s + eval_bs]
            with _autocast_ctx(device):
                ir_lg, u = plate.encode_surface(sb)
                r_pol, _, diag = astheno(u)
                ir_pred = ir_lg.argmax(dim=-1)
                core_out = core(ir_pred, residual_r=r_pol)
            preds = core_out["ans_logits"].float().argmax(dim=-1)
            correct += int((preds == yb).sum().item())
            ir_exact += int((ir_pred == irb).all(dim=-1).sum().item())
            r_chunks.append(r_pol.float())
            diag_accum["pol_tor_orthogonality_err"] = max(
                diag_accum["pol_tor_orthogonality_err"], float(diag["pol_tor_orthogonality_err"])
            )
            diag_accum["channel2b_advection_norm"] += float(diag["channel2b_advection_norm"])
            diag_accum["active_flux_fraction"] += float(diag["active_flux_fraction"])
            n_batches += 1
    _sync_if_cuda(device)
    wall_ms = (time.monotonic() - t0) * 1000.0 / max(n, 1)
    peak_mib = _peak_vram_mib(device)
    diag_out = {
        "yield_number": astheno.yield_number,
        "use_hodge": astheno.use_hodge,
        "max_residual_bits": float(astheno.max_residual_bits),
        "pol_tor_orthogonality_err": diag_accum["pol_tor_orthogonality_err"],
        "channel2b_advection_norm": round(diag_accum["channel2b_advection_norm"] / max(n_batches, 1), 6),
        "active_flux_fraction": round(diag_accum["active_flux_fraction"] / max(n_batches, 1), 6),
        "ir_exact_match_acc": round(ir_exact / max(n, 1), 6),
    }
    return correct / max(n, 1), torch.cat(r_chunks, dim=0), wall_ms, peak_mib, diag_out


def _eval_native_regime1(
    core: m.RigidInnerCore,
    r1_eval_examples: Sequence[m.S109Example],
    m_vocab: m.MinimalMediumVocab,
    native_ir_len: int,
    eval_bs: int,
    device: torch.device,
) -> dict[str, float]:
    """Native Mode (Regime I): CB-6 deterministic Python transducer -> unpadded ir_len=12 Core!"""
    core.eval()
    _reset_peak_vram(device)
    _sync_if_cuda(device)
    t0 = time.monotonic()
    ir_ids_list = [m.regime1_syntactic_transducer(e.surface_en, m_vocab, max_len=native_ir_len) for e in r1_eval_examples]
    ir_ev = torch.tensor(ir_ids_list, dtype=torch.long, device=device)
    y_ev = torch.tensor([e.answer for e in r1_eval_examples], dtype=torch.long, device=device)
    n = int(ir_ev.shape[0])
    correct = 0
    with torch.no_grad():
        for s in range(0, n, eval_bs):
            irb = ir_ev[s : s + eval_bs]
            yb = y_ev[s : s + eval_bs]
            r_zero = torch.zeros((irb.shape[0], core.k_res), dtype=torch.float32, device=device)
            with _autocast_ctx(device):
                out = core(irb, residual_r=r_zero)
            correct += int((out["ans_logits"].float().argmax(dim=-1) == yb).sum().item())
    _sync_if_cuda(device)
    wall_ms = (time.monotonic() - t0) * 1000.0 / max(n, 1)
    return {
        "native_r1_exact_acc": round(correct / max(n, 1), 6),
        "native_r1_wall_ms_per_problem": round(wall_ms, 4),
        "native_r1_peak_vram_mib": _peak_vram_mib(device),
    }


def _counterfactual_audit_faithfulness(
    core: m.RigidInnerCore,
    audit_dec: m.AuditTraceDecoder,
    ir_ev: torch.Tensor,
    r_ev: torch.Tensor,
    eval_bs: int,
    device: torch.device,
) -> dict[str, float]:
    """AMENDMENT1 §5.1: patch h^(mid) from a shifted counterfactual problem and check audit trace shift."""
    n = int(ir_ev.shape[0])
    if n < 2:
        return {"faithfulness": 1.0, "shifted_ans_faithfulness": 1.0, "inter_faithfulness": 1.0, "n_interventions": 0}
    mid_idx = max(0, core.n_loops // 2 - 1)
    core.eval()
    audit_dec.eval()
    agree_ans = 0
    agree_inter = 0
    shifted_total = 0
    shifted_agree = 0
    with torch.no_grad():
        for s in range(0, n, eval_bs):
            irb = ir_ev[s : s + eval_bs]
            rb = r_ev[s : s + eval_bs]
            if irb.shape[0] < 2:
                continue
            with _autocast_ctx(device):
                base_out = core(irb, residual_r=rb)
                h_mid = base_out["loop_states"][mid_idx]
                h_cf = torch.roll(h_mid, shifts=1, dims=0)
                patched_out = core(irb, residual_r=rb, patch_pass_idx=mid_idx, patch_state=h_cf)
                p_aud_inter, p_aud_ans = audit_dec(patched_out["loop_states"][mid_idx], last_idx=patched_out["last_idx"])
            base_ans = base_out["ans_logits"].float().argmax(dim=-1)
            patched_core_ans = patched_out["ans_logits"].float().argmax(dim=-1)
            patched_core_inter = patched_out["inter_logits"].float().argmax(dim=-1)
            aud_ans_pred = p_aud_ans.float().argmax(dim=-1)
            aud_inter_pred = p_aud_inter.float().argmax(dim=-1)
            agree_ans += int((aud_ans_pred == patched_core_ans).sum().item())
            agree_inter += int((aud_inter_pred == patched_core_inter).sum().item())
            shifted = patched_core_ans != base_ans
            shifted_total += int(shifted.sum().item())
            shifted_agree += int(((aud_ans_pred == patched_core_ans) & shifted).sum().item())
    return {
        "faithfulness": round(agree_ans / max(n, 1), 6),
        "shifted_ans_faithfulness": round(shifted_agree / max(shifted_total, 1), 6),
        "inter_faithfulness": round(agree_inter / max(n, 1), 6),
        "n_interventions": n,
        "n_shifted_interventions": shifted_total,
    }


def _train_and_eval_plate_seam_router(
    core: m.RigidInnerCore,
    astheno: m.ViscoplasticAsthenosphere,
    plate_en: m.ExternalSurfacePlate,
    plate_alt: m.ExternalSurfacePlate,
    plate_sym: m.ExternalSurfacePlate,
    tr_r1: dict[str, torch.Tensor],
    ev_r1: dict[str, torch.Tensor],
    tr_r2: dict[str, torch.Tensor],
    ev_r2: dict[str, torch.Tensor],
    cfg: dict[str, Any],
    seed: int,
    device: torch.device,
) -> dict[str, Any]:
    """AMENDMENT2 §PLATE-SWAP: multi-plate seam composition atop frozen Plates & frozen Core using u_tor."""
    seed_everything(seed + 808)
    router = m.PlateSeamRouter(k_res=cfg["k_res"], n_plates=3).to(device)
    plates = (plate_en, plate_alt, plate_sym)
    ev_bs = int(cfg["eval_batch_size"])

    def _extract_plate_outputs(surf_t: torch.Tensor) -> tuple[list[torch.Tensor], list[torch.Tensor], list[torch.Tensor]]:
        irs: list[list[torch.Tensor]] = [[], [], []]
        tors: list[list[torch.Tensor]] = [[], [], []]
        rpols: list[list[torch.Tensor]] = [[], [], []]
        with torch.no_grad():
            for s in range(0, int(surf_t.shape[0]), ev_bs):
                sb = surf_t[s : s + ev_bs]
                for pi, pl in enumerate(plates):
                    with _autocast_ctx(device):
                        ir_lg, u = pl.encode_surface(sb)
                        r_pol, u_tor, _ = astheno(u)
                    irs[pi].append(ir_lg.float())
                    tors[pi].append(u_tor.float())
                    rpols[pi].append(r_pol.float())
        return (
            [torch.cat(c, dim=0) for c in irs],
            [torch.cat(c, dim=0) for c in tors],
            [torch.cat(c, dim=0) for c in rpols],
        )

    n_cal = min(128, int(tr_r2["en"].shape[0]), int(tr_r1["en"].shape[0]))
    cal_surf = torch.cat([tr_r2["en"][:n_cal], tr_r2["alt"][:n_cal], tr_r1["en"][:n_cal], tr_r2["mix"][:n_cal]], dim=0)
    cal_ir_tgt = torch.cat(
        [
            torch.full((n_cal,), 0, dtype=torch.long, device=device),
            torch.full((n_cal,), 1, dtype=torch.long, device=device),
            torch.full((n_cal,), 2, dtype=torch.long, device=device),
            torch.full((n_cal,), 2, dtype=torch.long, device=device),
        ]
    )
    cal_res_tgt = torch.cat(
        [
            torch.full((n_cal,), 0, dtype=torch.long, device=device),
            torch.full((n_cal,), 1, dtype=torch.long, device=device),
            torch.full((n_cal,), 2, dtype=torch.long, device=device),
            torch.full((n_cal,), 0, dtype=torch.long, device=device),
        ]
    )
    _, cal_tors, _ = _extract_plate_outputs(cal_surf)

    opt = torch.optim.AdamW(router.parameters(), lr=1e-2, weight_decay=0.01)
    router.train()
    for _ in range(int(cfg["router_steps"])):
        opt.zero_grad(set_to_none=True)
        cat_tor = torch.cat(cal_tors, dim=-1)
        lg_ir = router.ir_router(cat_tor)
        lg_res = router.res_router(cat_tor)
        loss = F.cross_entropy(lg_ir, cal_ir_tgt) + F.cross_entropy(lg_res, cal_res_tgt)
        loss.backward()
        opt.step()

    router.eval()
    n_ev_part = min(int(ev_r2["en"].shape[0]), int(ev_r1["en"].shape[0]))
    stream_surf = torch.cat([ev_r2["en"][:n_ev_part], ev_r2["alt"][:n_ev_part], ev_r1["en"][:n_ev_part]], dim=0)
    stream_ans = torch.cat([ev_r2["ans"][:n_ev_part], ev_r2["ans"][:n_ev_part], ev_r1["ans"][:n_ev_part]], dim=0)
    stream_tgt = torch.cat(
        [
            torch.full((n_ev_part,), 0, dtype=torch.long, device=device),
            torch.full((n_ev_part,), 1, dtype=torch.long, device=device),
            torch.full((n_ev_part,), 2, dtype=torch.long, device=device),
        ]
    )

    def _eval_routed(surf_t: torch.Tensor, ans_t: torch.Tensor, tgt_ir: torch.Tensor | None) -> dict[str, float]:
        e_irs, e_tors, e_rpols = _extract_plate_outputs(surf_t)
        with torch.no_grad():
            b_ir, b_r, a_ir, a_res = router.blend_plates_dual(e_irs, e_tors, e_rpols)
            cocycle_err = max(
                float((a_ir.sum(dim=-1) - 1.0).abs().max().item()),
                float((a_res.sum(dim=-1) - 1.0).abs().max().item()),
            )
            ir_pred = b_ir.argmax(dim=-1)
            correct = 0
            for s in range(0, int(surf_t.shape[0]), ev_bs):
                with _autocast_ctx(device):
                    out = core(ir_pred[s : s + ev_bs], residual_r=b_r[s : s + ev_bs])
                correct += int((out["ans_logits"].float().argmax(dim=-1) == ans_t[s : s + ev_bs]).sum().item())
            acc = correct / max(int(surf_t.shape[0]), 1)
            route_acc = float((a_ir.argmax(dim=-1) == tgt_ir).float().mean().item()) if tgt_ir is not None else 0.0
        return {"acc": round(acc, 6), "route_acc": round(route_acc, 6), "cocycle_sum_err": cocycle_err}

    stream_res = _eval_routed(stream_surf, stream_ans, stream_tgt)
    mix_res = _eval_routed(ev_r2["mix"], ev_r2["ans"], torch.full((ev_r2["mix"].shape[0],), 2, dtype=torch.long, device=device))
    return {
        "unlabeled_3surface_stream_acc": stream_res["acc"],
        "unlabeled_3surface_route_acc": stream_res["route_acc"],
        "hybrid_mixed_seam_acc": mix_res["acc"],
        "cocycle_sum_err": max(stream_res["cocycle_sum_err"], mix_res["cocycle_sum_err"]),
        "router_params": m.count_module_params(router),
    }


def _eval_single_yield_arm(
    y_val: float,
    use_hodge: bool,
    core: m.RigidInnerCore,
    audit_dec: m.AuditTraceDecoder,
    tr_r1: dict[str, torch.Tensor],
    ev_r1: dict[str, torch.Tensor],
    tr_r2: dict[str, torch.Tensor],
    ev_r2: dict[str, torch.Tensor],
    r1_eval_examples: Sequence[m.S109Example],
    cb5_r2_hyb: float,
    m_vocab: m.MinimalMediumVocab,
    cfg: dict[str, Any],
    seed: int,
    device: torch.device,
) -> tuple[dict[str, Any], m.ExternalSurfacePlate, m.ViscoplasticAsthenosphere]:
    ev_bs = int(cfg["eval_batch_size"])
    seed_off = int(round(y_val * 100)) + (0 if use_hodge else 555)
    astheno = m.ViscoplasticAsthenosphere(
        k=cfg["k_res"], bits_per_dim=3, yield_number=y_val, use_hodge=use_hodge
    ).to(device)
    plate_en, sha_ok = _train_stage2_plate(
        core, astheno, "en", tr_r1, tr_r2, cfg, m_vocab.vocab_size, seed + seed_off, device
    )
    skip_chk = m.verify_zero_skip_paths(plate_en, astheno, core, ev_r2["en"][:8], ev_r2["ir"][:8])

    acc_r1_plate, _, ms_r1_plate, vram_r1_plate, diag_r1 = _eval_plate_core_batches(
        plate_en, astheno, core, ev_r1["en"], ev_r1["ir"], ev_r1["ans"], ev_bs, device
    )
    acc_r2, r_ev_r2, ms_r2, vram_r2, diag_r2 = _eval_plate_core_batches(
        plate_en, astheno, core, ev_r2["en"], ev_r2["ir"], ev_r2["ans"], ev_bs, device
    )
    native_r1 = _eval_native_regime1(core, r1_eval_examples, m_vocab, int(cfg["native_ir_len"]), ev_bs, device)

    with torch.no_grad():
        oracle_ir_plate_r_correct = 0
        for s in range(0, int(ev_r2["ir"].shape[0]), ev_bs):
            with _autocast_ctx(device):
                out_o = core(ev_r2["ir"][s : s + ev_bs], residual_r=r_ev_r2[s : s + ev_bs])
            oracle_ir_plate_r_correct += int(
                (out_o["ans_logits"].float().argmax(dim=-1) == ev_r2["ans"][s : s + ev_bs]).sum().item()
            )
    acc_r2_oracle_ir_plate_r = oracle_ir_plate_r_correct / max(int(ev_r2["ir"].shape[0]), 1)
    total_err_r2 = max(1e-9, 1.0 - acc_r2)
    dpi_gap_vs_oracle = max(0.0, cb5_r2_hyb - acc_r2)
    dpi_error_share = min(1.0, dpi_gap_vs_oracle / total_err_r2)

    r_tr_r2 = _collect_residuals(plate_en, astheno, tr_r2["en"], ev_bs, device)
    leak = m.run_residual_leak_probe(r_tr_r2, tr_r2["ans"], r_ev_r2, ev_r2["ans"], n_classes=16, seed=seed)
    cf_audit = _counterfactual_audit_faithfulness(core, audit_dec, ev_r2["ir"], r_ev_r2, ev_bs, device)

    with torch.no_grad():
        x_enc = plate_en.byte_emb(ev_r2["en"][:256]).mean(dim=1)
        darboux_diag = m.darboux_dark_mode_diagnostic(plate_en.res_head.weight, x_enc)

    # Within-system zero-retrain §SWAP (independent Stage-2 English Plate on identical frozen Core)
    plate_en_swap, swap_en_sha_ok = _train_stage2_plate(
        core, astheno, "en", tr_r1, tr_r2, cfg, m_vocab.vocab_size, seed + seed_off + 1000, device
    )
    acc_r2_en_swap, _, _, _, _ = _eval_plate_core_batches(
        plate_en_swap, astheno, core, ev_r2["en"], ev_r2["ir"], ev_r2["ans"], ev_bs, device
    )

    # Cross-surface / Arabic zero-retrain §SWAP (independent Stage-2 Arabic Plate on identical frozen Core)
    plate_alt, alt_sha_ok = _train_stage2_plate(
        core, astheno, "alt", tr_r1, tr_r2, cfg, m_vocab.vocab_size, seed + seed_off + 2000, device
    )
    acc_r2_alt_swap, _, _, _, diag_alt = _eval_plate_core_batches(
        plate_alt, astheno, core, ev_r2["alt"], ev_r2["ir"], ev_r2["ans"], ev_bs, device
    )

    # Independent Symbolic/Code Plate + §PLATE-SWAP multi-plate seam composition
    plate_sym, sym_sha_ok = _train_stage2_plate(
        core, astheno, "en", tr_r1, tr_r2, cfg, m_vocab.vocab_size, seed + seed_off + 3000, device, r1_only=True
    )
    plate_swap_diag = _train_and_eval_plate_seam_router(
        core, astheno, plate_en, plate_alt, plate_sym, tr_r1, ev_r1, tr_r2, ev_r2, cfg, seed + seed_off, device
    )

    p_core = m.count_module_params(core)
    p_ext_out = m.count_module_params(plate_en.ext_out_head)
    p_ext_in = m.count_module_params(plate_en) - p_ext_out
    p_aud = m.count_module_params(audit_dec)
    ledger = m.compute_system_resource_ledger(
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
        batch_size=int(cfg["batch_size"]),
        ext_layers=cfg["ext_layers"],
        m_vocab_size=m_vocab.vocab_size,
    )

    entry = {
        "yield_number": y_val,
        "use_hodge": use_hodge,
        "core_sha_unchanged": bool(sha_ok and swap_en_sha_ok and alt_sha_ok and sym_sha_ok),
        "zero_skip_path": skip_chk,
        "regime1_native": native_r1,
        "regime1_core_acc": round(acc_r1_plate, 6),
        "regime1_wall_ms_per_problem": round(ms_r1_plate, 4),
        "regime2_core_acc": round(acc_r2, 6),
        "regime2_oracle_ir_plate_r_acc": round(acc_r2_oracle_ir_plate_r, 6),
        "regime2_wall_ms_per_problem": round(ms_r2, 4),
        "eval_peak_vram_mib": round(max(vram_r1_plate, vram_r2, native_r1["native_r1_peak_vram_mib"]), 3),
        "dpi_loss_vs_cb5_r2": round(cb5_r2_hyb - acc_r2, 6),
        "dpi_error_share_r2": round(dpi_error_share, 6),
        "channel2b_diag_r1": diag_r1,
        "channel2b_diag_r2": diag_r2,
        "residual_leak_probe": leak,
        "counterfactual_audit": cf_audit,
        "portal5_darboux_dark_mode": darboux_diag,
        "swap_within_en_acc": round(acc_r2_en_swap, 6),
        "swap_within_drop_pp": round((acc_r2 - acc_r2_en_swap) * 100.0, 4),
        "swap_alt_arabic_acc": round(acc_r2_alt_swap, 6),
        "swap_alt_ir_exact_acc": diag_alt["ir_exact_match_acc"],
        "swap_alt_drop_pp": round((acc_r2 - acc_r2_alt_swap) * 100.0, 4),
        "plate_swap_seam": plate_swap_diag,
        "resource_ledger": ledger,
    }
    return entry, plate_en, astheno


def _run_single_seed(cfg: dict[str, Any], track: str, seed: int, device: torch.device) -> tuple[dict[str, Any], str]:
    m_vocab = m.MinimalMediumVocab()
    r1_all, r2_all, dataset_sha = m.generate_s109_dataset(
        n_regime1=cfg["n_regime1"],
        n_regime2=cfg["n_regime2"],
        seed=seed,
        ir_len=cfg["ir_len"],
    )
    cut1 = (len(r1_all) * 3) // 4
    cut2 = (len(r2_all) * 3) // 4
    r1_eval_ex = r1_all[cut1:]
    tr_r1 = _batch_tensors(r1_all[:cut1], cfg["surf_len"], device)
    ev_r1 = _batch_tensors(r1_eval_ex, cfg["surf_len"], device)
    tr_r2 = _batch_tensors(r2_all[:cut2], cfg["surf_len"], device)
    ev_r2 = _batch_tensors(r2_all[cut2:], cfg["surf_len"], device)

    tr_r1_keys = {(e.a, e.b, e.c, e.op_id) for e in r1_all[:cut1]}
    ev_r1_overlap = sum(1 for e in r1_all[cut1:] if (e.a, e.b, e.c, e.op_id) in tr_r1_keys)
    tr_r2_keys = {(e.a, e.b, e.c, e.op_id) for e in r2_all[:cut2]}
    ev_r2_overlap = sum(1 for e in r2_all[cut2:] if (e.a, e.b, e.c, e.op_id) in tr_r2_keys)

    res: dict[str, Any] = {
        "seed": seed,
        "dataset_sha256": dataset_sha,
        "train_eval_tuple_overlap": {"regime1": ev_r1_overlap, "regime2": ev_r2_overlap},
        "deflate_entropy_stats": m.empirical_binary_entropy_and_redundancy([e.deflate_bytes for e in r1_all + r2_all]),
        "english_entropy_stats": m.empirical_binary_entropy_and_redundancy([e.surface_en.encode("utf-8") for e in r1_all + r2_all]),
    }

    if track in ("all", "h9a", "h9b", "h9c"):
        res["arm_a_english_cot"] = _train_mono_arm(
            "english_cot", "en", True, tr_r1, ev_r1, tr_r2, ev_r2, cfg, seed, device
        )
        res["arm_a_prime_direct"] = _train_mono_arm(
            "direct_answer", "en", False, tr_r1, ev_r1, tr_r2, ev_r2, cfg, seed, device
        )
        res["arm_b_compressed_binary"] = _train_mono_arm(
            "compressed_binary_deflate", "deflate", False, tr_r1, ev_r1, tr_r2, ev_r2, cfg, seed, device
        )
        if track in ("all", "h9a"):
            res["arm_b_decompressor_emulation"] = _train_decompressor_emulation(
                tr_r1, ev_r1, tr_r2, ev_r2, cfg, seed, device
            )
            en_tr_cat = torch.cat([tr_r1["en"], tr_r2["en"]], dim=0)
            en_ev_cat = torch.cat([ev_r1["en"], ev_r2["en"]], dim=0)
            df_tr_cat = torch.cat([tr_r1["deflate"], tr_r2["deflate"]], dim=0)
            df_ev_cat = torch.cat([ev_r1["deflate"], ev_r2["deflate"]], dim=0)
            res["probe_lm_predictivity"] = {
                "english": _train_probe_lm_bits_per_bit(en_tr_cat, en_ev_cat, cfg, seed, device),
                "deflate": _train_probe_lm_bits_per_bit(df_tr_cat, df_ev_cat, cfg, seed + 1, device),
            }

    if track in ("all", "terracore", "h9b", "h9c", "h9d"):
        ev_bs = int(cfg["eval_batch_size"])
        core, audit_dec, core_sha, s1_vram = _train_stage1_frozen_core(tr_r1, tr_r2, cfg, m_vocab.vocab_size, seed, device)
        res["stage1_frozen_core_sha256"] = core_sha
        res["stage1_train_peak_vram_mib"] = s1_vram
        res["cb6_syntactic_check"] = _run_cb6_syntactic_check(tr_r1, ev_r1, m_vocab.vocab_size, device, cfg["mode"])

        q0 = m.canonical_poloidal_axis(cfg["k_res"], device=device)

        def _eval_core_oracle(ir_t: torch.Tensor, r_t: torch.Tensor, ans_t: torch.Tensor) -> float:
            corr = 0
            with torch.no_grad():
                for s in range(0, int(ir_t.shape[0]), ev_bs):
                    with _autocast_ctx(device):
                        out = core(ir_t[s : s + ev_bs], residual_r=r_t[s : s + ev_bs])
                    corr += int((out["ans_logits"].float().argmax(dim=-1) == ans_t[s : s + ev_bs]).sum().item())
            return corr / max(int(ir_t.shape[0]), 1)

        r_zero_r1 = torch.zeros((ev_r1["ir"].shape[0], cfg["k_res"]), device=device)
        r_zero_r2 = torch.zeros((ev_r2["ir"].shape[0], cfg["k_res"]), device=device)
        r_canon_r2 = (2.0 * ev_r2["mod"].float() - 1.0).unsqueeze(-1) * q0.unsqueeze(0)
        cb5_r1 = _eval_core_oracle(ev_r1["ir"], r_zero_r1, ev_r1["ans"])
        cb5_r2_sym = _eval_core_oracle(ev_r2["ir"], r_zero_r2, ev_r2["ans"])
        cb5_r2_hyb = _eval_core_oracle(ev_r2["ir"], r_canon_r2, ev_r2["ans"])

        res["arm_d_mono"] = _train_arm_d_mono(tr_r1, ev_r1, tr_r2, ev_r2, cfg, m_vocab.vocab_size, seed, device)

        yield_sweep: dict[str, Any] = {}
        plates_en_by_y: dict[str, m.ExternalSurfacePlate] = {}
        asthenos_by_y: dict[str, m.ViscoplasticAsthenosphere] = {}
        for y_val in m.YIELD_SWEEP_VALUES:
            key = f"Y_{y_val:.2f}"
            entry, pl_en, asth = _eval_single_yield_arm(
                y_val, True, core, audit_dec, tr_r1, ev_r1, tr_r2, ev_r2, r1_eval_ex, cb5_r2_hyb, m_vocab, cfg, seed, device
            )
            yield_sweep[key] = entry
            plates_en_by_y[key] = pl_en
            asthenos_by_y[key] = asth

        nh_entry, _, _ = _eval_single_yield_arm(
            0.5, False, core, audit_dec, tr_r1, ev_r1, tr_r2, ev_r2, r1_eval_ex, cb5_r2_hyb, m_vocab, cfg, seed, device
        )
        yield_sweep["Y_0.50_NoHodge"] = nh_entry

        plate_mid = plates_en_by_y["Y_0.50"]
        astheno_mid = asthenos_by_y["Y_0.50"]
        rand_core = m.RigidInnerCore(
            m_vocab_size=m_vocab.vocab_size,
            d_model=cfg["core_d"],
            n_heads=cfg["core_heads"],
            n_layers=cfg["core_layers"],
            n_loops=cfg["core_loops"],
            k_res=cfg["k_res"],
            n_classes=16,
        ).to(device)
        rand_core.eval()

        cb1_c = cb2_c = cb3_c = cb4_sym_c = cb4_res_c = 0
        n_ev2 = int(ev_r2["en"].shape[0])
        with torch.no_grad():
            for s in range(0, n_ev2, ev_bs):
                sb = ev_r2["en"][s : s + ev_bs]
                yb = ev_r2["ans"][s : s + ev_bs]
                with _autocast_ctx(device):
                    ir_lg, u_ev = plate_mid.encode_surface(sb)
                    r_pol, _, _ = astheno_mid(u_ev)
                    ir_pred = ir_lg.argmax(dim=-1)
                    c_rand = rand_core(ir_pred, r_pol)["ans_logits"].float()
                    c_out = core(ir_pred, r_pol)["ans_logits"].float()
                    c_sym = core(ir_pred, torch.zeros_like(r_pol))["ans_logits"].float()
                    c_res = core(torch.zeros_like(ir_pred), r_pol)["ans_logits"].float()
                cb1_c += int(((ir_pred[:, 1] % 16) == yb).sum().item())
                cb2_c += int((c_rand.argmax(dim=-1) == yb).sum().item())
                cb3_c += int((torch.roll(c_out, shifts=1, dims=0).argmax(dim=-1) == yb).sum().item())
                cb4_sym_c += int((c_sym.argmax(dim=-1) == yb).sum().item())
                cb4_res_c += int((c_res.argmax(dim=-1) == yb).sum().item())

        res["h9d_yield_sweep"] = yield_sweep
        res["cb1_to_cb5_controls"] = {
            "cb1_identity_core_acc": round(cb1_c / max(n_ev2, 1), 6),
            "cb2_frozen_random_core_acc": round(cb2_c / max(n_ev2, 1), 6),
            "cb3_core_lesion_acc": round(cb3_c / max(n_ev2, 1), 6),
            "cb4_symbolic_only_acc": round(cb4_sym_c / max(n_ev2, 1), 6),
            "cb4_residual_only_acc": round(cb4_res_c / max(n_ev2, 1), 6),
            "cb5_oracle_ir_r1_acc": round(cb5_r1, 6),
            "cb5_oracle_ir_r2_sym_acc": round(cb5_r2_sym, 6),
            "cb5_oracle_ir_r2_hyb_acc": round(cb5_r2_hyb, 6),
        }
        y50 = yield_sweep["Y_0.50"]
        res["swap_and_plate_swap"] = {
            "alt_plate_core_sha_unchanged": y50["core_sha_unchanged"],
            "en_plate_r2_acc": y50["regime2_core_acc"],
            "en_plate_within_swap_r2_acc": y50["swap_within_en_acc"],
            "alt_plate_swap_r2_acc": y50["swap_alt_arabic_acc"],
            "plate_swap_stream_acc": y50["plate_swap_seam"]["unlabeled_3surface_stream_acc"],
            "plate_swap_mixed_acc": y50["plate_swap_seam"]["hybrid_mixed_seam_acc"],
            "cocycle_sum_err": y50["plate_swap_seam"]["cocycle_sum_err"],
        }

    return res, dataset_sha


# ---------------------------------------------------------------------------
# Multi-Seed Statistical Aggregation & Paired Bootstrap CI
# ---------------------------------------------------------------------------


def _mean_se(vals: Sequence[float]) -> dict[str, float]:
    n = len(vals)
    if n == 0:
        return {"mean": 0.0, "se": 0.0, "n": 0}
    mu = sum(vals) / n
    if n == 1:
        return {"mean": round(mu, 6), "se": 0.0, "n": 1}
    var = sum((v - mu) ** 2 for v in vals) / (n - 1)
    return {"mean": round(mu, 6), "se": round(math.sqrt(var / n), 6), "n": n}


def _paired_summary(a_vals: Sequence[float], b_vals: Sequence[float], seed: int = 109) -> dict[str, float]:
    diffs = [a - b for a, b in zip(a_vals, b_vals)]
    n = len(diffs)
    mu = sum(diffs) / max(n, 1)
    if n <= 1:
        return {"delta_mean": round(mu, 6), "se": 0.0, "z": 0.0, "ci95_low": round(mu, 6), "ci95_high": round(mu, 6)}
    var = sum((d - mu) ** 2 for d in diffs) / (n - 1)
    se = math.sqrt(var / n)
    z = mu / se if se > 1e-12 else (float("inf") if mu > 0 else (float("-inf") if mu < 0 else 0.0))
    rng = random.Random(seed)
    boots = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(2000))
    return {
        "delta_mean": round(mu, 6),
        "se": round(se, 6),
        "z": round(z, 3) if math.isfinite(z) else (999.0 if z > 0 else -999.0),
        "ci95_low": round(boots[50], 6),
        "ci95_high": round(boots[1949], 6),
    }


def _aggregate_seeds(per_seed: dict[str, dict[str, Any]], seeds: Sequence[int]) -> dict[str, Any]:
    skeys = [str(s) for s in seeds]
    first = per_seed[skeys[0]]
    agg: dict[str, Any] = {"n_seeds": len(skeys), "seeds": list(seeds)}

    if "arm_a_english_cot" in first:
        for arm in ("arm_a_english_cot", "arm_a_prime_direct", "arm_b_compressed_binary"):
            agg[arm] = {
                "regime1_exact_acc": _mean_se([per_seed[k][arm]["regime1_exact_acc"] for k in skeys]),
                "regime1_inter_acc": _mean_se([per_seed[k][arm]["regime1_inter_acc"] for k in skeys]),
                "regime2_exact_acc": _mean_se([per_seed[k][arm]["regime2_exact_acc"] for k in skeys]),
                "regime2_inter_acc": _mean_se([per_seed[k][arm]["regime2_inter_acc"] for k in skeys]),
                "wall_ms_per_problem_r1": _mean_se([per_seed[k][arm]["wall_ms_per_problem_r1"] for k in skeys]),
                "wall_ms_per_problem_r2": _mean_se([per_seed[k][arm]["wall_ms_per_problem_r2"] for k in skeys]),
                "eval_peak_vram_mib": _mean_se([per_seed[k][arm]["eval_peak_vram_mib"] for k in skeys]),
            }
        agg["h9a_paired_a_minus_b"] = {
            "regime1": _paired_summary(
                [per_seed[k]["arm_a_english_cot"]["regime1_exact_acc"] for k in skeys],
                [per_seed[k]["arm_b_compressed_binary"]["regime1_exact_acc"] for k in skeys],
            ),
            "regime2": _paired_summary(
                [per_seed[k]["arm_a_english_cot"]["regime2_exact_acc"] for k in skeys],
                [per_seed[k]["arm_b_compressed_binary"]["regime2_exact_acc"] for k in skeys],
            ),
        }
        if "arm_b_decompressor_emulation" in first:
            agg["arm_b_decompressor_emulation"] = {
                "regime1_byte_acc": _mean_se([per_seed[k]["arm_b_decompressor_emulation"]["regime1_byte_acc"] for k in skeys]),
                "regime1_exact_str_acc": _mean_se([per_seed[k]["arm_b_decompressor_emulation"]["regime1_exact_str_acc"] for k in skeys]),
                "regime2_byte_acc": _mean_se([per_seed[k]["arm_b_decompressor_emulation"]["regime2_byte_acc"] for k in skeys]),
                "regime2_exact_str_acc": _mean_se([per_seed[k]["arm_b_decompressor_emulation"]["regime2_exact_str_acc"] for k in skeys]),
            }
            agg["probe_lm_predictivity"] = {
                "english_bits_per_bit": _mean_se([per_seed[k]["probe_lm_predictivity"]["english"]["probe_lm_bits_per_bit"] for k in skeys]),
                "deflate_bits_per_bit": _mean_se([per_seed[k]["probe_lm_predictivity"]["deflate"]["probe_lm_bits_per_bit"] for k in skeys]),
            }

    if "h9d_yield_sweep" in first:
        agg["arm_d_mono"] = {
            "regime1_core_acc": _mean_se([per_seed[k]["arm_d_mono"]["regime1_core_acc"] for k in skeys]),
            "regime2_core_acc": _mean_se([per_seed[k]["arm_d_mono"]["regime2_core_acc"] for k in skeys]),
            "leak_above_chance": _mean_se([per_seed[k]["arm_d_mono"]["residual_leak_probe"]["above_chance"] for k in skeys]),
            "audit_faithfulness": _mean_se([per_seed[k]["arm_d_mono"]["counterfactual_audit"]["faithfulness"] for k in skeys]),
        }
        agg["cb1_to_cb5_controls"] = {
            ck: _mean_se([per_seed[k]["cb1_to_cb5_controls"][ck] for k in skeys])
            for ck in first["cb1_to_cb5_controls"].keys()
        }
        agg["cb6_trivial_acc"] = _mean_se([per_seed[k]["cb6_syntactic_check"]["trivial_core_acc"] for k in skeys])

        sweep_agg: dict[str, Any] = {}
        for yk in first["h9d_yield_sweep"].keys():
            sweep_agg[yk] = {
                "native_r1_acc": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["regime1_native"]["native_r1_exact_acc"] for k in skeys]),
                "native_r1_wall_ms": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["regime1_native"]["native_r1_wall_ms_per_problem"] for k in skeys]),
                "regime1_core_acc": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["regime1_core_acc"] for k in skeys]),
                "regime2_core_acc": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["regime2_core_acc"] for k in skeys]),
                "regime2_wall_ms": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["regime2_wall_ms_per_problem"] for k in skeys]),
                "ir_exact_r1": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["channel2b_diag_r1"]["ir_exact_match_acc"] for k in skeys]),
                "ir_exact_r2": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["channel2b_diag_r2"]["ir_exact_match_acc"] for k in skeys]),
                "dpi_loss_vs_cb5_r2": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["dpi_loss_vs_cb5_r2"] for k in skeys]),
                "dpi_error_share_r2": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["dpi_error_share_r2"] for k in skeys]),
                "leak_above_chance": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["residual_leak_probe"]["above_chance"] for k in skeys]),
                "audit_faithfulness": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["counterfactual_audit"]["faithfulness"] for k in skeys]),
                "shifted_audit_faithfulness": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["counterfactual_audit"]["shifted_ans_faithfulness"] for k in skeys]),
                "swap_within_drop_pp": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["swap_within_drop_pp"] for k in skeys]),
                "swap_alt_arabic_acc": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["swap_alt_arabic_acc"] for k in skeys]),
                "swap_alt_ir_exact_acc": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["swap_alt_ir_exact_acc"] for k in skeys]),
                "swap_alt_drop_pp": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["swap_alt_drop_pp"] for k in skeys]),
                "plate_swap_stream_acc": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["plate_swap_seam"]["unlabeled_3surface_stream_acc"] for k in skeys]),
                "plate_swap_route_acc": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["plate_swap_seam"]["unlabeled_3surface_route_acc"] for k in skeys]),
                "plate_swap_mixed_acc": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["plate_swap_seam"]["hybrid_mixed_seam_acc"] for k in skeys]),
                "active_flux_fraction": _mean_se([per_seed[k]["h9d_yield_sweep"][yk]["channel2b_diag_r2"]["active_flux_fraction"] for k in skeys]),
                "all_core_sha_unchanged": all(per_seed[k]["h9d_yield_sweep"][yk]["core_sha_unchanged"] for k in skeys),
                "all_zero_skip_verified": all(per_seed[k]["h9d_yield_sweep"][yk]["zero_skip_path"]["zero_skip_path_verified"] for k in skeys),
                "any_cs21_leak_triggered": any(per_seed[k]["h9d_yield_sweep"][yk]["residual_leak_probe"]["cs21_residual_leak_triggered"] for k in skeys),
            }
        agg["h9d_yield_sweep"] = sweep_agg
        agg["h9d_paired_comparisons"] = {
            "Y050_minus_Y100_r2_acc": _paired_summary(
                [per_seed[k]["h9d_yield_sweep"]["Y_0.50"]["regime2_core_acc"] for k in skeys],
                [per_seed[k]["h9d_yield_sweep"]["Y_1.00"]["regime2_core_acc"] for k in skeys],
            ),
            "Y050_minus_Y000_r2_acc": _paired_summary(
                [per_seed[k]["h9d_yield_sweep"]["Y_0.50"]["regime2_core_acc"] for k in skeys],
                [per_seed[k]["h9d_yield_sweep"]["Y_0.00"]["regime2_core_acc"] for k in skeys],
            ),
            "Y050_minus_Y000_leak": _paired_summary(
                [per_seed[k]["h9d_yield_sweep"]["Y_0.50"]["residual_leak_probe"]["above_chance"] for k in skeys],
                [per_seed[k]["h9d_yield_sweep"]["Y_0.00"]["residual_leak_probe"]["above_chance"] for k in skeys],
            ),
            "Y050_minus_Y000_stream_acc": _paired_summary(
                [per_seed[k]["h9d_yield_sweep"]["Y_0.50"]["plate_swap_seam"]["unlabeled_3surface_stream_acc"] for k in skeys],
                [per_seed[k]["h9d_yield_sweep"]["Y_0.00"]["plate_swap_seam"]["unlabeled_3surface_stream_acc"] for k in skeys],
            ),
            "Y050_minus_NoHodge_stream_acc": _paired_summary(
                [per_seed[k]["h9d_yield_sweep"]["Y_0.50"]["plate_swap_seam"]["unlabeled_3surface_stream_acc"] for k in skeys],
                [per_seed[k]["h9d_yield_sweep"]["Y_0.50_NoHodge"]["plate_swap_seam"]["unlabeled_3surface_stream_acc"] for k in skeys],
            ),
            "Y050_minus_NoHodge_mixed_acc": _paired_summary(
                [per_seed[k]["h9d_yield_sweep"]["Y_0.50"]["plate_swap_seam"]["hybrid_mixed_seam_acc"] for k in skeys],
                [per_seed[k]["h9d_yield_sweep"]["Y_0.50_NoHodge"]["plate_swap_seam"]["hybrid_mixed_seam_acc"] for k in skeys],
            ),
        }
    return agg


def run_s109_suite(
    cfg: dict[str, Any],
    track: str,
    device: torch.device,
) -> tuple[dict[str, Any], str]:
    per_seed: dict[str, dict[str, Any]] = {}
    dataset_shas: dict[str, str] = {}
    for sd in cfg["seeds"]:
        s_res, ds_sha = _run_single_seed(cfg, track, int(sd), device)
        per_seed[str(sd)] = s_res
        dataset_shas[str(sd)] = ds_sha
    agg = _aggregate_seeds(per_seed, cfg["seeds"])

    first_res = dict(per_seed[str(cfg["seeds"][0])])
    first_res["per_seed"] = per_seed
    first_res["aggregate"] = agg
    first_res["dataset_shas_by_seed"] = dataset_shas
    combined_sha = hashlib.sha256(
        json.dumps(dataset_shas, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    return first_res, combined_sha


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track S109 (Minimal-Medium Core + TerraCore H9d) harness")
    parser.add_argument("--mode", choices=("cpu-smoke", "gpu-full"), default="cpu-smoke")
    parser.add_argument("--track", choices=("all", "h9a", "h9b", "h9c", "h9d", "terracore"), default="all")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--seeds", default="42", help="Comma-separated seeds (e.g. 42,137,2026)")
    parser.add_argument("--out-dir", default=None, help="Output dir for locked protocol & JSON receipt")
    args = parser.parse_args(argv)

    if args.device == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("--device cuda requested but CUDA is unavailable")
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")

    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    cfg = build_preset(args.mode, seeds)

    t0 = time.monotonic()
    res, ds_sha = run_s109_suite(cfg, args.track, device)
    elapsed_s = round(time.monotonic() - t0, 3)

    protocol = {
        "schema": "aletheia.track_s109.locked_protocol.v1",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "parent_preregistration_sha256": m.PREREG_S109_SHA256,
        "amendment1_sha256": m.AMENDMENT1_SHA256,
        "amendment2_sha256": m.AMENDMENT2_SHA256,
        "amendment3_sha256": m.AMENDMENT3_SHA256,
        "mode": args.mode,
        "track": args.track,
        "device": str(device),
        "weights_saved": 0,
        "dataset_sha256": ds_sha,
        "preset": cfg,
    }
    proto_bytes = (json.dumps(protocol, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    proto_sha = hashlib.sha256(proto_bytes).hexdigest()

    payload: dict[str, Any] = {
        "schema": "aletheia.track_s109.results.v1",
        "protocol_sha256": proto_sha,
        "parent_preregistration_sha256": m.PREREG_S109_SHA256,
        "amendment1_sha256": m.AMENDMENT1_SHA256,
        "amendment2_sha256": m.AMENDMENT2_SHA256,
        "amendment3_sha256": m.AMENDMENT3_SHA256,
        "mode": args.mode,
        "track": args.track,
        "device": str(device),
        "elapsed_s": elapsed_s,
        "weights_saved": 0,
        "results": res,
    }
    payload["result_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    if args.out_dir is not None:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        p_path = out_dir / "s109_locked_protocol.json"
        r_path = out_dir / f"s109_{args.mode.replace('-', '_')}_results.json"
        p_path.write_bytes(proto_bytes)
        os.chmod(p_path, 0o600)
        r_path.write_bytes((json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
        os.chmod(r_path, 0o600)

    print(
        json.dumps(
            {
                "mode": args.mode,
                "track": args.track,
                "device": str(device),
                "seeds": seeds,
                "elapsed_s": elapsed_s,
                "protocol_sha256": proto_sha,
                "result_sha256": payload["result_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
