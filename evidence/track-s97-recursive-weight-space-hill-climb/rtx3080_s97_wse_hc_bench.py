#!/usr/bin/env python3
"""Live 4-Way RTX 3080 Qwen2.5-0.5B Benchmark for Track S97 (ALETHEIA-WSE-HC).

Compares 4 arms under identical seed, model weights, target modules, held-out
discrete oracle, and held-out WikiText-2 retention eval (HF_HUB_OFFLINE=1, ZERO
saved weights):
  - Arm 1: Std-Backprop-LoRA (AdamW autograd LoRA)
  - Arm 2: Naive-WSE-HC (unratcheted isotropic Gaussian weight-space hill climb)
  - Arm 3: Aletheia-WSE-HC-Pure (backprop-free privileged+BlockH4+nullspace+ratchet)
  - Arm 4: Aletheia-WSE-HC-Hybrid (1-step grad proposal + recursive nullspace ratchet)
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import pathlib
import stat
import time
from typing import Dict, List, Tuple

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = "Qwen/Qwen2.5-0.5B"
SEED = 42
TARGET_LAYERS = [18, 19, 20, 21, 22, 23]  # 6 upper self_attn.o_proj (896 x 896)
LORA_RANK = 16
BASE_NULLSPACE_RANK = 128  # top-128 WikiText-2 val PCs projected out by nullspace gate
PRIV_TOP_K = 256  # top-256 privileged-basis output neurons (multiple of 4 for BlockH4)
DPI_MAX = 16.0
EPS_WIKI_DRIFT = 0.005


def set_all_seeds(seed: int) -> None:
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def resolve_local_snapshot() -> Tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    cache_root = pathlib.Path(
        os.environ.get("HF_HOME", str(pathlib.Path.home() / ".cache" / "huggingface"))
    )
    model_root = cache_root / "hub" / "models--Qwen--Qwen2.5-0.5B" / "snapshots"
    snaps = sorted([p for p in model_root.iterdir() if p.is_dir()]) if model_root.is_dir() else []
    if not snaps:
        raise RuntimeError("Local Qwen2.5-0.5B snapshot not found in HF cache")
    wiki_val = cache_root / "s49b_eval" / "wikitext2_val.txt"
    wiki_test = cache_root / "s49b_eval" / "wikitext2_test.txt"
    if not wiki_val.is_file() or not wiki_test.is_file():
        raise RuntimeError("Local WikiText-2 val/test files not found in HF cache")
    return snaps[-1], wiki_val, wiki_test


def build_epistemic_audit_dataset() -> Dict[str, List[Tuple[str, str]]]:
    """Deterministic structured epistemic verification dataset (disjoint splits).

    Rule: Output PASS iff asserts=0, leaks=0, lean=1, mut=100; else output FAIL.
    Hard near-boundary FAIL cases (mut=99, mut=98, asserts=1, leaks=1, lean=0)
    challenge Qwen2.5-0.5B without fine-tuning while remaining cleanly learnable.
    """
    state = 1337
    seen = set()
    pass_recs: List[Tuple[str, str]] = []
    fail_recs: List[Tuple[str, str]] = []
    idx = 0
    while len(pass_recs) < 40 or len(fail_recs) < 40:
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        tid = 100 + idx
        idx += 1
        steps = 4 + (state % 12)
        thms = 12 + ((state >> 4) % 15)
        want_pass = (len(pass_recs) <= len(fail_recs)) and len(pass_recs) < 40
        if want_pass:
            ba, lk, lc, mp = 0, 0, 1, 100
            label = " PASS"
        else:
            mode = (state >> 8) % 5
            ba, lk, lc, mp = 0, 0, 1, 100
            if mode == 0:
                ba = 1 + ((state >> 12) % 3)
            elif mode == 1:
                lk = 1 + ((state >> 12) % 2)
            elif mode == 2:
                lc = 0
            elif mode == 3:
                mp = 95 + ((state >> 12) % 5)  # 95..99 near-100 boundary!
            else:
                mp = 99
                lk = 1
            label = " FAIL"
        key = (steps, thms, ba, lk, lc, mp)
        if key in seen:
            continue
        seen.add(key)
        prompt = (
            "Rule: Output PASS if asserts=0, leaks=0, lean=1, mut=100; else output FAIL.\n"
            f"Record R{tid}: steps={steps} thms={thms} asserts={ba} leaks={lk} lean={lc} mut={mp}\n"
            "Ruling:"
        )
        if want_pass:
            pass_recs.append((prompt, label))
        else:
            fail_recs.append((prompt, label))

    interleaved: List[Tuple[str, str]] = []
    for p, f in zip(pass_recs, fail_recs):
        interleaved.append(p)
        interleaved.append(f)
    return {
        "train": interleaved[0:32],
        "dev": interleaved[32:48],
        "test": interleaved[48:80],
    }


def tokenize_wiki_blocks(
    tokenizer, path: pathlib.Path, max_blocks: int, block_len: int = 128
) -> torch.Tensor:
    text = path.read_text(encoding="utf-8", errors="ignore")
    ids = tokenizer.encode(text[:120000], add_special_tokens=False)
    n_tok = (len(ids) // block_len) * block_len
    ids = ids[: min(n_tok, max_blocks * block_len)]
    return torch.tensor(ids, dtype=torch.long).view(-1, block_len)


def encode_audit_split(
    tokenizer, split: List[Tuple[str, str]], pass_id: int, fail_id: int
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    seqs = [tokenizer.encode(p, add_special_tokens=False) for p, _ in split]
    max_len = max(len(s) for s in seqs)
    pad_id = tokenizer.eos_token_id if tokenizer.eos_token_id is not None else 0
    input_ids = torch.full((len(seqs), max_len), pad_id, dtype=torch.long)
    attn_mask = torch.zeros((len(seqs), max_len), dtype=torch.long)
    targets = torch.zeros(len(seqs), dtype=torch.long)
    for i, (s, (_, lbl)) in enumerate(zip(seqs, split)):
        input_ids[i, : len(s)] = torch.tensor(s, dtype=torch.long)
        attn_mask[i, : len(s)] = 1
        targets[i] = pass_id if lbl.strip() == "PASS" else fail_id
    return input_ids, attn_mask, targets


@torch.no_grad()
def eval_wiki_nll(model, blocks: torch.Tensor, device: torch.device) -> float:
    """Memory-lean batch_size=1 WikiText NLL eval (avoids artificial FP32 logit spikes)."""
    total_nll = 0.0
    total_tok = 0
    for i in range(blocks.size(0)):
        b = blocks[i : i + 1].to(device)
        out = model(input_ids=b, use_cache=False)
        logits = out.logits[:, :-1, :].float()
        labels = b[:, 1:]
        loss_sum = F.cross_entropy(
            logits.reshape(-1, logits.size(-1)), labels.reshape(-1), reduction="sum"
        )
        total_nll += float(loss_sum.item())
        total_tok += int(labels.numel())
        del out, logits
    return total_nll / max(1, total_tok)


@torch.no_grad()
def eval_audit_oracle(
    model,
    input_ids: torch.Tensor,
    attn_mask: torch.Tensor,
    targets: torch.Tensor,
    pass_id: int,
    fail_id: int,
    device: torch.device,
    chunk_size: int = 8,
) -> Dict[str, float]:
    """Chunked forward-only oracle evaluation (keeps inference VRAM minimal and fair)."""
    n_tot = input_ids.size(0)
    nll_sum = 0.0
    bin_ok = 0
    full_ok = 0
    margin_sum = 0.0
    for i in range(0, n_tot, chunk_size):
        inp = input_ids[i : i + chunk_size].to(device)
        msk = attn_mask[i : i + chunk_size].to(device)
        tgt = targets[i : i + chunk_size].to(device)
        out = model(input_ids=inp, attention_mask=msk, use_cache=False)
        last_idx = msk.sum(dim=1) - 1
        row_idx = torch.arange(inp.size(0), device=device)
        last_logits = out.logits[row_idx, last_idx, :].float()

        nll_sum += float(F.cross_entropy(last_logits, tgt, reduction="sum").item())
        pair_logits = torch.stack([last_logits[:, pass_id], last_logits[:, fail_id]], dim=1)
        pair_targets = (tgt == fail_id).long()
        bin_ok += int((pair_logits.argmax(dim=1) == pair_targets).sum().item())
        full_ok += int((last_logits.argmax(dim=1) == tgt).sum().item())
        correct_l = pair_logits[row_idx, pair_targets]
        wrong_l = pair_logits[row_idx, 1 - pair_targets]
        margin_sum += float((correct_l - wrong_l).sum().item())
        del out, last_logits
    return {
        "discrete_acc": bin_ok / max(1, n_tot),
        "full_vocab_acc": full_ok / max(1, n_tot),
        "target_nll": nll_sum / max(1, n_tot),
        "mean_margin": margin_sum / max(1, n_tot),
    }


def apply_block_h4_cols(x: torch.Tensor) -> torch.Tensor:
    """Exact orthonormal 4-point Hadamard transform along last dimension (scaled by 1/2)."""
    orig_shape = x.shape
    v = x.reshape(*orig_shape[:-1], -1, 4)
    a, b, c, d = v[..., 0], v[..., 1], v[..., 2], v[..., 3]
    y0 = 0.5 * (a + b + c + d)
    y1 = 0.5 * (a - b + c - d)
    y2 = 0.5 * (a + b - c - d)
    y3 = 0.5 * (a - b - c + d)
    return torch.stack([y0, y1, y2, y3], dim=-1).reshape(orig_shape)


@torch.no_grad()
def calibrate_nullspace_and_privileged_basis(
    model, wiki_val_blocks: torch.Tensor, device: torch.device
) -> Tuple[Dict[int, torch.Tensor], Dict[int, torch.Tensor]]:
    """Capture WikiText-2 val input covariance -> nullspace projector U_base
    and output activation norm -> top-K privileged neuron indices for each target o_proj."""
    covs: Dict[int, torch.Tensor] = {}
    out_energy: Dict[int, torch.Tensor] = {}
    hooks = []

    def make_hook(li: int):
        def _hook(_mod, inp, out):
            x = inp[0].detach().float().reshape(-1, inp[0].shape[-1])
            y = out.detach().float().reshape(-1, out.shape[-1])
            if li not in covs:
                covs[li] = x.T @ x
                out_energy[li] = (y * y).sum(dim=0)
            else:
                covs[li] += x.T @ x
                out_energy[li] += (y * y).sum(dim=0)
        return _hook

    for li in TARGET_LAYERS:
        mod = model.model.layers[li].self_attn.o_proj
        hooks.append(mod.register_forward_hook(make_hook(li)))

    for i in range(wiki_val_blocks.size(0)):
        b = wiki_val_blocks[i : i + 1].to(device)
        _ = model(input_ids=b, use_cache=False)

    for h in hooks:
        h.remove()

    u_bases: Dict[int, torch.Tensor] = {}
    priv_indices: Dict[int, torch.Tensor] = {}
    for li in TARGET_LAYERS:
        _evals, evecs = torch.linalg.eigh(covs[li])
        u_bases[li] = evecs[:, -BASE_NULLSPACE_RANK:].contiguous()
        priv_indices[li] = torch.topk(out_energy[li], k=PRIV_TOP_K).indices.sort().values
    return u_bases, priv_indices


def project_nullspace(dw: torch.Tensor, u_base: torch.Tensor) -> torch.Tensor:
    """Exact orthogonal projection dw_perp = dw * (I - U_base U_base^T) -> dw_perp @ X_base = 0."""
    return dw - (dw @ u_base) @ u_base.T


def smooth_dpi_cap(dw: torch.Tensor, max_row_to_mean: float = 8.0) -> torch.Tensor:
    """Smoothly damp extreme outlier rows so edit stays within DPI concentration ceiling."""
    row_e = (dw * dw).sum(dim=1)
    mean_e = float(row_e.mean().item())
    if mean_e <= 1e-18:
        return dw
    cap_e = mean_e * max_row_to_mean
    scale = torch.clamp(torch.sqrt(cap_e / torch.clamp(row_e, min=1e-18)), max=1.0)
    return dw * scale.unsqueeze(1)


def compute_edit_dpi(deltas: Dict[int, torch.Tensor]) -> Dict[str, float]:
    """Compute total Frobenius norm and active-layer max-row-to-mean-row energy ratio (DPI)."""
    row_energies = []
    tot_sq = 0.0
    for li in TARGET_LAYERS:
        dw = deltas[li].float()
        re = (dw * dw).sum(dim=1)
        layer_sq = float(re.sum().item())
        if layer_sq > 1e-18:
            row_energies.append(re)
            tot_sq += layer_sq
    if not row_energies:
        return {"fro_norm": 0.0, "dpi_row_concentration": 0.0}
    all_re = torch.cat(row_energies, dim=0)
    mean_re = float(all_re.mean().item())
    max_re = float(all_re.max().item())
    dpi = (max_re / mean_re) if mean_re > 1e-18 else 0.0
    return {
        "fro_norm": math.sqrt(max(0.0, tot_sq)),
        "dpi_row_concentration": dpi,
    }


def load_fresh_model(model_path: pathlib.Path, device: torch.device):
    gc.collect()
    if torch.cuda.is_initialized():
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)
    model = AutoModelForCausalLM.from_pretrained(
        str(model_path),
        dtype=torch.bfloat16,
        local_files_only=True,
    ).to(device)
    model.eval()
    return model


def run_arm1_std_backprop_lora(
    model_path: pathlib.Path,
    device: torch.device,
    splits: Dict[str, Tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
    wiki_val: torch.Tensor,
    wiki_test: torch.Tensor,
    pass_id: int,
    fail_id: int,
) -> Dict[str, object]:
    """Arm 1: Standard Backprop AdamW LoRA on TARGET_LAYERS o_proj (rank=16, 30 steps)."""
    set_all_seeds(SEED)
    model = load_fresh_model(model_path, device)
    for p in model.parameters():
        p.requires_grad_(False)

    d_model = model.config.hidden_size
    lora_A: Dict[int, torch.nn.Parameter] = {}
    lora_B: Dict[int, torch.nn.Parameter] = {}
    hooks = []
    scale = 2.0 / math.sqrt(LORA_RANK)
    for li in TARGET_LAYERS:
        a = torch.nn.Parameter(torch.randn(LORA_RANK, d_model, device=device, dtype=torch.bfloat16) * 0.02)
        b = torch.nn.Parameter(torch.zeros(d_model, LORA_RANK, device=device, dtype=torch.bfloat16))
        lora_A[li] = a
        lora_B[li] = b

        def make_lora_hook(aa, bb):
            def _h(_mod, inp, out):
                x = inp[0]
                return out + F.linear(F.linear(x, aa), bb) * scale
            return _h

        hooks.append(model.model.layers[li].self_attn.o_proj.register_forward_hook(make_lora_hook(a, b)))

    params = list(lora_A.values()) + list(lora_B.values())
    opt = torch.optim.AdamW(params, lr=1.5e-3, weight_decay=0.0)
    tr_inp, tr_msk, tr_tgt = splits["train"]
    tr_inp_d, tr_msk_d, tr_tgt_d = tr_inp.to(device), tr_msk.to(device), tr_tgt.to(device)
    last_idx = tr_msk_d.sum(dim=1) - 1
    row_idx = torch.arange(tr_inp_d.size(0), device=device)

    torch.cuda.reset_peak_memory_stats(device)
    t0 = time.perf_counter()
    for _step in range(30):
        opt.zero_grad(set_to_none=True)
        out = model(input_ids=tr_inp_d, attention_mask=tr_msk_d, use_cache=False)
        last_logits = out.logits[row_idx, last_idx, :].float()
        loss = F.cross_entropy(last_logits, tr_tgt_d)
        loss.backward()
        opt.step()
    torch.cuda.synchronize(device)
    wall_s = time.perf_counter() - t0
    peak_alloc_mib = torch.cuda.max_memory_allocated(device) / (1024.0 * 1024.0)
    peak_res_mib = torch.cuda.max_memory_reserved(device) / (1024.0 * 1024.0)

    deltas: Dict[int, torch.Tensor] = {}
    with torch.no_grad():
        for h in hooks:
            h.remove()
        for li in TARGET_LAYERS:
            dw = (lora_B[li].float() @ lora_A[li].float()) * scale
            deltas[li] = dw
            model.model.layers[li].self_attn.o_proj.weight.add_(dw.to(torch.bfloat16))

    dev_m = eval_audit_oracle(model, *splits["dev"], pass_id, fail_id, device)
    test_m = eval_audit_oracle(model, *splits["test"], pass_id, fail_id, device)
    w_val = eval_wiki_nll(model, wiki_val, device)
    w_test = eval_wiki_nll(model, wiki_test, device)
    dpi_m = compute_edit_dpi(deltas)

    del model, opt, lora_A, lora_B, deltas
    gc.collect()
    torch.cuda.empty_cache()
    return {
        "arm": "Std-Backprop-LoRA",
        "backprop_free": False,
        "steps": 30,
        "accepted_steps": 30,
        "wall_time_sec": round(wall_s, 4),
        "peak_vram_alloc_mib": round(peak_alloc_mib, 2),
        "peak_vram_reserved_mib": round(peak_res_mib, 2),
        "dev": dev_m,
        "heldout_test": test_m,
        "wiki_val_nll": round(w_val, 6),
        "wiki_test_nll": round(w_test, 6),
        "wiki_test_ppl": round(math.exp(w_test), 4),
        "edit_fro_norm": round(dpi_m["fro_norm"], 6),
        "edit_dpi_row_concentration": round(dpi_m["dpi_row_concentration"], 4),
    }


def run_arm2_naive_wse_hc(
    model_path: pathlib.Path,
    device: torch.device,
    splits: Dict[str, Tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
    wiki_val: torch.Tensor,
    wiki_test: torch.Tensor,
    pass_id: int,
    fail_id: int,
) -> Dict[str, object]:
    """Arm 2: Naive unratcheted isotropic Gaussian WSE hill climb (reproduces WSP/songe)."""
    set_all_seeds(SEED + 1)
    model = load_fresh_model(model_path, device)
    d_model = model.config.hidden_size
    deltas = {li: torch.zeros(d_model, d_model, device=device, dtype=torch.float32) for li in TARGET_LAYERS}

    tr_inp, tr_msk, tr_tgt = splits["train"]
    torch.cuda.reset_peak_memory_stats(device)
    t0 = time.perf_counter()
    accepted = 0
    sigma = 0.012
    with torch.inference_mode():
        for step in range(40):
            start = (step * 8) % tr_inp.size(0)
            mb = (tr_inp[start : start + 8], tr_msk[start : start + 8], tr_tgt[start : start + 8])
            cur_mb = eval_audit_oracle(model, *mb, pass_id, fail_id, device)
            cur_score = cur_mb["discrete_acc"] - 0.1 * cur_mb["target_nll"]

            li = TARGET_LAYERS[step % len(TARGET_LAYERS)]
            w_mod = model.model.layers[li].self_attn.o_proj.weight
            orig_w = w_mod.data.clone()
            noise = torch.randn(d_model, d_model, device=device, dtype=torch.bfloat16) * sigma
            w_mod.add_(noise)
            cand_mb = eval_audit_oracle(model, *mb, pass_id, fail_id, device)
            cand_score = cand_mb["discrete_acc"] - 0.1 * cand_mb["target_nll"]
            if cand_score >= cur_score:
                deltas[li].add_(noise.float())
                accepted += 1
            else:
                w_mod.data.copy_(orig_w)
    torch.cuda.synchronize(device)
    wall_s = time.perf_counter() - t0
    peak_alloc_mib = torch.cuda.max_memory_allocated(device) / (1024.0 * 1024.0)
    peak_res_mib = torch.cuda.max_memory_reserved(device) / (1024.0 * 1024.0)

    dev_m = eval_audit_oracle(model, *splits["dev"], pass_id, fail_id, device)
    test_m = eval_audit_oracle(model, *splits["test"], pass_id, fail_id, device)
    w_val = eval_wiki_nll(model, wiki_val, device)
    w_test = eval_wiki_nll(model, wiki_test, device)
    dpi_m = compute_edit_dpi(deltas)

    del model, deltas
    gc.collect()
    torch.cuda.empty_cache()
    return {
        "arm": "Naive-WSE-HC",
        "backprop_free": True,
        "steps": 40,
        "accepted_steps": accepted,
        "wall_time_sec": round(wall_s, 4),
        "peak_vram_alloc_mib": round(peak_alloc_mib, 2),
        "peak_vram_reserved_mib": round(peak_res_mib, 2),
        "dev": dev_m,
        "heldout_test": test_m,
        "wiki_val_nll": round(w_val, 6),
        "wiki_test_nll": round(w_test, 6),
        "wiki_test_ppl": round(math.exp(w_test), 4),
        "edit_fro_norm": round(dpi_m["fro_norm"], 6),
        "edit_dpi_row_concentration": round(dpi_m["dpi_row_concentration"], 4),
    }


def run_arm3_aletheia_wse_hc_pure(
    model_path: pathlib.Path,
    device: torch.device,
    splits: Dict[str, Tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
    wiki_val: torch.Tensor,
    wiki_test: torch.Tensor,
    pass_id: int,
    fail_id: int,
    base_wiki_val_nll: float,
) -> Dict[str, object]:
    """Arm 3: Backprop-Free ALETHEIA-WSE-HC-Pure.
    Zero autograd / zero optimizer states; recursive multi-direction 2-point ZO
    hill climb strictly inside top-K privileged-basis + BlockH4 + Householder QR
    + exact nullspace ker(X_base^T) subspace, gated by hard 5-gate ratchet.
    """
    set_all_seeds(SEED + 2)
    model = load_fresh_model(model_path, device)
    d_model = model.config.hidden_size
    deltas = {li: torch.zeros(d_model, d_model, device=device, dtype=torch.float32) for li in TARGET_LAYERS}

    torch.cuda.reset_peak_memory_stats(device)
    t0 = time.perf_counter()
    with torch.inference_mode():
        u_bases, priv_indices = calibrate_nullspace_and_privileged_basis(model, wiki_val, device)
        cur_dev = eval_audit_oracle(model, *splits["dev"], pass_id, fail_id, device)
        accepted = 0
        rejected_ratchet = 0

        # 24 recursive rounds: each round estimates directional ascent over K=4
        # orthogonal BlockH4 privileged-basis + nullspace probes (pure forward passes!)
        mu = 0.025
        for rnd in range(24):
            li = TARGET_LAYERS[rnd % len(TARGET_LAYERS)]
            w_mod = model.model.layers[li].self_attn.o_proj.weight
            orig_w = w_mod.data.clone()
            p_idx = priv_indices[li]
            u_b = u_bases[li]

            # Build K=4 orthonormal privileged-basis BlockH4 + nullspace probe directions
            # (exact kappa_2=1 via QR Householder + zero base interference via U_base!)
            k_probes = 4
            u_raw = torch.randn(PRIV_TOP_K, k_probes, device=device, dtype=torch.float32)
            u_q, _ = torch.linalg.qr(apply_block_h4_cols(u_raw.T).T, mode="reduced")
            v_raw = torch.randn(d_model, k_probes, device=device, dtype=torch.float32)
            v_h4 = apply_block_h4_cols(v_raw.T).T
            v_perp = v_h4 - u_b @ (u_b.T @ v_h4)
            v_q, _ = torch.linalg.qr(v_perp, mode="reduced")

            # Purely forward-only 2-point finite-difference directional ascent on train
            comb_dir = torch.zeros(d_model, d_model, device=device, dtype=torch.float32)
            for k in range(k_probes):
                z_sub = torch.outer(u_q[:, k], v_q[:, k])  # unit Frobenius norm rank-1
                z_full = torch.zeros(d_model, d_model, device=device, dtype=torch.float32)
                z_full[p_idx, :] = z_sub
                z_step = (z_full * mu).to(torch.bfloat16)

                w_mod.data.copy_(orig_w)
                w_mod.add_(z_step)
                m_plus = eval_audit_oracle(model, *splits["train"], pass_id, fail_id, device)

                w_mod.data.copy_(orig_w)
                w_mod.sub_(z_step)
                m_minus = eval_audit_oracle(model, *splits["train"], pass_id, fail_id, device)

                # Maximize discrete_acc + smooth margin - target_nll (purely forward!)
                s_plus = 2.0 * m_plus["discrete_acc"] + 0.25 * m_plus["mean_margin"] - 0.5 * m_plus["target_nll"]
                s_minus = 2.0 * m_minus["discrete_acc"] + 0.25 * m_minus["mean_margin"] - 0.5 * m_minus["target_nll"]
                coeff = (s_plus - s_minus) / (2.0 * mu)
                comb_dir.add_(z_full * coeff)

            w_mod.data.copy_(orig_w)
            dn = float(torch.linalg.norm(comb_dir).item())
            if dn <= 1e-10:
                rejected_ratchet += 1
                continue
            unit_dir = smooth_dpi_cap(comb_dir / dn, max_row_to_mean=10.0)
            unit_dir = project_nullspace(unit_dir, u_b)
            unit_dir = unit_dir / max(float(torch.linalg.norm(unit_dir).item()), 1e-10)

            # Multi-scale hill-climb step search gated strictly by 5-gate Aletheia ratchet
            best_alpha = None
            best_dev = None
            for alpha in (0.18, 0.09, 0.045, 0.02):
                cand_step = (unit_dir * alpha).to(torch.bfloat16)
                w_mod.data.copy_(orig_w)
                w_mod.add_(cand_step)
                deltas[li].add_(cand_step.float())

                cand_dev = eval_audit_oracle(model, *splits["dev"], pass_id, fail_id, device)
                cand_wval = eval_wiki_nll(model, wiki_val, device)
                cand_dpi = compute_edit_dpi(deltas)["dpi_row_concentration"]

                gate_target = (cand_dev["discrete_acc"] > cur_dev["discrete_acc"]) or (
                    cand_dev["discrete_acc"] == cur_dev["discrete_acc"]
                    and cand_dev["target_nll"] < cur_dev["target_nll"] - 1e-4
                )
                gate_base = cand_wval <= (base_wiki_val_nll + EPS_WIKI_DRIFT)
                gate_dpi = cand_dpi <= DPI_MAX
                gate_finite = math.isfinite(cand_dev["target_nll"]) and math.isfinite(cand_wval)

                deltas[li].sub_(cand_step.float())
                if gate_target and gate_base and gate_dpi and gate_finite:
                    if best_dev is None or (
                        cand_dev["discrete_acc"] > best_dev["discrete_acc"]
                        or (
                            cand_dev["discrete_acc"] == best_dev["discrete_acc"]
                            and cand_dev["target_nll"] < best_dev["target_nll"]
                        )
                    ):
                        best_alpha = alpha
                        best_dev = cand_dev

            w_mod.data.copy_(orig_w)
            if best_alpha is not None and best_dev is not None:
                win_step = (unit_dir * best_alpha).to(torch.bfloat16)
                w_mod.add_(win_step)
                deltas[li].add_(win_step.float())
                cur_dev = best_dev
                accepted += 1
            else:
                rejected_ratchet += 1

    torch.cuda.synchronize(device)
    wall_s = time.perf_counter() - t0
    peak_alloc_mib = torch.cuda.max_memory_allocated(device) / (1024.0 * 1024.0)
    peak_res_mib = torch.cuda.max_memory_reserved(device) / (1024.0 * 1024.0)

    dev_m = eval_audit_oracle(model, *splits["dev"], pass_id, fail_id, device)
    test_m = eval_audit_oracle(model, *splits["test"], pass_id, fail_id, device)
    w_val = eval_wiki_nll(model, wiki_val, device)
    w_test = eval_wiki_nll(model, wiki_test, device)
    dpi_m = compute_edit_dpi(deltas)

    del model, deltas, u_bases, priv_indices
    gc.collect()
    torch.cuda.empty_cache()
    return {
        "arm": "Aletheia-WSE-HC-Pure",
        "backprop_free": True,
        "steps": 24,
        "accepted_steps": accepted,
        "rejected_ratchet": rejected_ratchet,
        "wall_time_sec": round(wall_s, 4),
        "peak_vram_alloc_mib": round(peak_alloc_mib, 2),
        "peak_vram_reserved_mib": round(peak_res_mib, 2),
        "dev": dev_m,
        "heldout_test": test_m,
        "wiki_val_nll": round(w_val, 6),
        "wiki_test_nll": round(w_test, 6),
        "wiki_test_ppl": round(math.exp(w_test), 4),
        "edit_fro_norm": round(dpi_m["fro_norm"], 6),
        "edit_dpi_row_concentration": round(dpi_m["dpi_row_concentration"], 4),
    }


def run_arm4_aletheia_wse_hc_hybrid(
    model_path: pathlib.Path,
    device: torch.device,
    splits: Dict[str, Tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
    wiki_val: torch.Tensor,
    wiki_test: torch.Tensor,
    pass_id: int,
    fail_id: int,
    base_wiki_val_nll: float,
) -> Dict[str, object]:
    """Arm 4: ALETHEIA-WSE-HC-Hybrid (Augmenting Backprop).
    Recursive multi-round: cheap 1-step gradient proposal on live mutated weights
    -> exact nullspace projection (I - U_base U_base^T) + smooth DPI row cap
    -> multi-scale recursive hill-climb line search gated by hard 5-gate ratchet
    -> mid-run recursive nullspace re-calibration (curing S68/S70 cross-layer shift!).
    """
    set_all_seeds(SEED + 3)
    model = load_fresh_model(model_path, device)
    for p in model.parameters():
        p.requires_grad_(False)
    for li in TARGET_LAYERS:
        model.model.layers[li].self_attn.o_proj.weight.requires_grad_(True)

    d_model = model.config.hidden_size
    deltas = {li: torch.zeros(d_model, d_model, device=device, dtype=torch.float32) for li in TARGET_LAYERS}

    tr_inp, tr_msk, tr_tgt = splits["train"]
    tr_inp_d, tr_msk_d, tr_tgt_d = tr_inp.to(device), tr_msk.to(device), tr_tgt.to(device)
    last_idx = tr_msk_d.sum(dim=1) - 1
    row_idx = torch.arange(tr_inp_d.size(0), device=device)

    torch.cuda.reset_peak_memory_stats(device)
    t0 = time.perf_counter()
    u_bases, _priv_indices = calibrate_nullspace_and_privileged_basis(model, wiki_val, device)
    cur_dev = eval_audit_oracle(model, *splits["dev"], pass_id, fail_id, device)
    accepted = 0
    rejected_ratchet = 0
    relinearizations = 1

    for rnd in range(12):
        if rnd == 6:
            u_bases, _ = calibrate_nullspace_and_privileged_basis(model, wiki_val, device)
            relinearizations += 1

        model.zero_grad(set_to_none=True)
        out = model(input_ids=tr_inp_d, attention_mask=tr_msk_d, use_cache=False)
        last_logits = out.logits[row_idx, last_idx, :].float()
        loss = F.cross_entropy(last_logits, tr_tgt_d)
        loss.backward()

        props: Dict[int, torch.Tensor] = {}
        with torch.no_grad():
            for li in TARGET_LAYERS:
                g = model.model.layers[li].self_attn.o_proj.weight.grad.float()
                g_perp = project_nullspace(g, u_bases[li])
                g_smooth = smooth_dpi_cap(-g_perp, max_row_to_mean=8.0)
                g_smooth = project_nullspace(g_smooth, u_bases[li])
                gn = float(torch.linalg.norm(g_smooth).item())
                props[li] = g_smooth / max(gn, 1e-8)
            model.zero_grad(set_to_none=True)

            orig_ws = {li: model.model.layers[li].self_attn.o_proj.weight.data.clone() for li in TARGET_LAYERS}
            best_alpha = None
            best_dev = None
            for alpha in (0.16, 0.08, 0.04, 0.02, 0.01):
                for li in TARGET_LAYERS:
                    step_t = (props[li] * alpha).to(torch.bfloat16)
                    model.model.layers[li].self_attn.o_proj.weight.data.copy_(orig_ws[li])
                    model.model.layers[li].self_attn.o_proj.weight.add_(step_t)
                    deltas[li].add_(step_t.float())

                cand_dev = eval_audit_oracle(model, *splits["dev"], pass_id, fail_id, device)
                cand_wval = eval_wiki_nll(model, wiki_val, device)
                cand_dpi = compute_edit_dpi(deltas)["dpi_row_concentration"]

                gate_target = (cand_dev["discrete_acc"] > cur_dev["discrete_acc"]) or (
                    cand_dev["discrete_acc"] == cur_dev["discrete_acc"]
                    and cand_dev["target_nll"] < cur_dev["target_nll"] - 1e-4
                )
                gate_base = cand_wval <= (base_wiki_val_nll + EPS_WIKI_DRIFT)
                gate_dpi = cand_dpi <= DPI_MAX
                gate_finite = math.isfinite(cand_dev["target_nll"]) and math.isfinite(cand_wval)

                for li in TARGET_LAYERS:
                    step_t = (props[li] * alpha).to(torch.bfloat16)
                    deltas[li].sub_(step_t.float())

                if gate_target and gate_base and gate_dpi and gate_finite:
                    if best_dev is None or (
                        cand_dev["discrete_acc"] > best_dev["discrete_acc"]
                        or (
                            cand_dev["discrete_acc"] == best_dev["discrete_acc"]
                            and cand_dev["target_nll"] < best_dev["target_nll"]
                        )
                    ):
                        best_alpha = alpha
                        best_dev = cand_dev

            for li in TARGET_LAYERS:
                model.model.layers[li].self_attn.o_proj.weight.data.copy_(orig_ws[li])
            if best_alpha is not None and best_dev is not None:
                for li in TARGET_LAYERS:
                    step_t = (props[li] * best_alpha).to(torch.bfloat16)
                    model.model.layers[li].self_attn.o_proj.weight.add_(step_t)
                    deltas[li].add_(step_t.float())
                cur_dev = best_dev
                accepted += 1
            else:
                rejected_ratchet += 1

    torch.cuda.synchronize(device)
    wall_s = time.perf_counter() - t0
    peak_alloc_mib = torch.cuda.max_memory_allocated(device) / (1024.0 * 1024.0)
    peak_res_mib = torch.cuda.max_memory_reserved(device) / (1024.0 * 1024.0)

    dev_m = eval_audit_oracle(model, *splits["dev"], pass_id, fail_id, device)
    test_m = eval_audit_oracle(model, *splits["test"], pass_id, fail_id, device)
    w_val = eval_wiki_nll(model, wiki_val, device)
    w_test = eval_wiki_nll(model, wiki_test, device)
    dpi_m = compute_edit_dpi(deltas)

    del model, deltas, u_bases
    gc.collect()
    torch.cuda.empty_cache()
    return {
        "arm": "Aletheia-WSE-HC-Hybrid",
        "backprop_free": False,
        "rounds": 12,
        "relinearizations": relinearizations,
        "accepted_steps": accepted,
        "rejected_ratchet": rejected_ratchet,
        "wall_time_sec": round(wall_s, 4),
        "peak_vram_alloc_mib": round(peak_alloc_mib, 2),
        "peak_vram_reserved_mib": round(peak_res_mib, 2),
        "dev": dev_m,
        "heldout_test": test_m,
        "wiki_val_nll": round(w_val, 6),
        "wiki_test_nll": round(w_test, 6),
        "wiki_test_ppl": round(math.exp(w_test), 4),
        "edit_fro_norm": round(dpi_m["fro_norm"], 6),
        "edit_dpi_row_concentration": round(dpi_m["dpi_row_concentration"], 4),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Track S97 Live 4-Way RTX 3080 Qwen2.5-0.5B Benchmark")
    ap.add_argument("--out", required=True, help="Output compact JSON receipt path")
    args = ap.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU required for live RTX 3080 benchmark")
    device = torch.device("cuda:0")
    torch.cuda.set_device(device)
    _warmup = torch.empty(1, device=device)
    del _warmup
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(device)
    model_path, wiki_val_path, wiki_test_path = resolve_local_snapshot()

    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    pass_ids = tokenizer.encode(" PASS", add_special_tokens=False)
    fail_ids = tokenizer.encode(" FAIL", add_special_tokens=False)
    if len(pass_ids) != 1 or len(fail_ids) != 1:
        raise RuntimeError(f"Expected single-token PASS/FAIL labels, got {pass_ids}, {fail_ids}")
    pass_id, fail_id = pass_ids[0], fail_ids[0]

    raw_ds = build_epistemic_audit_dataset()
    splits = {k: encode_audit_split(tokenizer, v, pass_id, fail_id) for k, v in raw_ds.items()}
    wiki_val = tokenize_wiki_blocks(tokenizer, wiki_val_path, max_blocks=16, block_len=128)
    wiki_test = tokenize_wiki_blocks(tokenizer, wiki_test_path, max_blocks=24, block_len=128)

    set_all_seeds(SEED)
    base_model = load_fresh_model(model_path, device)
    torch.cuda.reset_peak_memory_stats(device)
    base_dev = eval_audit_oracle(base_model, *splits["dev"], pass_id, fail_id, device)
    base_test = eval_audit_oracle(base_model, *splits["test"], pass_id, fail_id, device)
    base_wval = eval_wiki_nll(base_model, wiki_val, device)
    base_wtest = eval_wiki_nll(base_model, wiki_test, device)
    base_peak_alloc = torch.cuda.max_memory_allocated(device) / (1024.0 * 1024.0)
    del base_model
    gc.collect()
    torch.cuda.empty_cache()

    baseline = {
        "arm": "Base-Qwen2.5-0.5B",
        "peak_vram_alloc_mib": round(base_peak_alloc, 2),
        "dev": base_dev,
        "heldout_test": base_test,
        "wiki_val_nll": round(base_wval, 6),
        "wiki_test_nll": round(base_wtest, 6),
        "wiki_test_ppl": round(math.exp(base_wtest), 4),
    }
    print("[BASE]", json.dumps(baseline), flush=True)

    arm1 = run_arm1_std_backprop_lora(model_path, device, splits, wiki_val, wiki_test, pass_id, fail_id)
    print("[ARM1]", json.dumps(arm1), flush=True)

    arm2 = run_arm2_naive_wse_hc(model_path, device, splits, wiki_val, wiki_test, pass_id, fail_id)
    print("[ARM2]", json.dumps(arm2), flush=True)

    arm3 = run_arm3_aletheia_wse_hc_pure(
        model_path, device, splits, wiki_val, wiki_test, pass_id, fail_id, base_wval
    )
    print("[ARM3]", json.dumps(arm3), flush=True)

    arm4 = run_arm4_aletheia_wse_hc_hybrid(
        model_path, device, splits, wiki_val, wiki_test, pass_id, fail_id, base_wval
    )
    print("[ARM4]", json.dumps(arm4), flush=True)

    arms = [arm1, arm2, arm3, arm4]
    for a in arms:
        a["heldout_acc_gain"] = round(a["heldout_test"]["discrete_acc"] - base_test["discrete_acc"], 6)
        a["wiki_test_nll_drift"] = round(a["wiki_test_nll"] - base_wtest, 6)
        a["wiki_test_ppl_drift"] = round(a["wiki_test_ppl"] - baseline["wiki_test_ppl"], 4)

    result = {
        "schema_version": "s97_live_wse_hc_v1",
        "model_id": MODEL_ID,
        "gpu_name": torch.cuda.get_device_name(device),
        "torch_version": torch.__version__,
        "seed": SEED,
        "target_layers": TARGET_LAYERS,
        "target_module": "self_attn.o_proj",
        "lora_rank": LORA_RANK,
        "base_nullspace_rank": BASE_NULLSPACE_RANK,
        "privileged_top_k": PRIV_TOP_K,
        "dpi_max": DPI_MAX,
        "eps_wiki_drift": EPS_WIKI_DRIFT,
        "split_sizes": {
            "train": len(raw_ds["train"]),
            "dev_ratchet": len(raw_ds["dev"]),
            "heldout_test": len(raw_ds["test"]),
            "wiki_val_blocks": int(wiki_val.size(0)),
            "wiki_test_blocks": int(wiki_test.size(0)),
            "wiki_block_len": 128,
        },
        "baseline": baseline,
        "arms": arms,
        "weights_saved_in_expedition": 0,
    }
    canon = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    result["result_sha256"] = hashlib.sha256(canon).hexdigest()

    out_path = pathlib.Path(args.out)
    out_bytes = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    fd = os.open(str(out_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, out_bytes)
    finally:
        os.close(fd)
    os.chmod(out_path, stat.S_IRUSR | stat.S_IWUSR)
    print(f"[S97_LIVE_OK] out={out_path.name} sha={result['result_sha256'][:16]}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
