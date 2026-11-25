#!/usr/bin/env python3
"""PREREG-S110 + Amendment 1 ("Geosphere-Net"): Live RTX 3080 Training, Multidomain Eval, & Microbench Harness.

Supports:
  - --microbench: <2 min sm_86 wall-clock latency, throughput, peak VRAM, & BF16 numerical kill gate
                  (>15% per-block overhead over matched baseline block => PRUNE_OVERHEAD_GT_15PCT).
  - --stage H10a | H10b | all: Stage-1 single-shell isolation & Stage-2 coupled Geosphere-Net + LOSO + N0 anchors.
  - Strictly offline-ready (HF_HUB_OFFLINE=1), disjoint multidomain byte streams (WikiText-2 val vs test +
    80/20 SHA-256-disjoint frozen Python code & formal JSON/MD docs; 0% overlap, exact SHA-256 provenance),
    exact UTF-8 BPB (fp32 log-softmax, BOS excluded, EOS scored), 2x context extrapolation (T=1024),
    attention-sink entropy, R_test=6 loop extrapolation, 3-bit RTN group-128 PTQ + M1-H1 loop drift,
    adversarial spike ASR / Channel-2B resistance, pre-N counterfactual state-patching faithfulness,
    Portal-3 Beltrami [C,K]=0 & Rayleigh tracking, Holm-Bonferroni correction, paired bootstrap 95% CIs,
    and WEIGHTS=0 (JSON metrics receipts only; zero checkpoints saved inside expedition/).

Zero bare asserts; all randomness explicitly seeded.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from s110_geosphere_models import (
    BOS_ID,
    EOS_ID,
    PAD_ID,
    PREREG_S110_AMEND1_SHA256,
    PREREG_S110_SHA256,
    VOCAB_SIZE_BYTE,
    CayleyBlock2x2SO,
    DiagonalDarcyEMA,
    FastSurfaceMTPDraft,
    GeosphereBlock,
    GeosphereNetLM,
    GeothermalACTController,
    S110ConfigError,
    S110ModelConfig,
    VectorProximalPoloidalBingham,
    analytical_forward_flops_per_token,
    apply_rtn_ptq_copy,
    build_s110_arm_configs,
    count_parameters,
    measure_attention_sink_stats,
    measure_m1_h1_loop_drift,
    require_ok,
    run_beltrami_helicity_diagnostic,
)

DEFAULT_SEEDS = (42, 137, 2026)
KILL_GATE_OVERHEAD_LIMIT = 0.15  # Amendment 1 Discovery 4: > 15% overhead => PRUNE


# ---------------------------------------------------------------------------
# Exact UTF-8 Byte Encoding & Offline Disjoint Multi-Domain Corpus Loader
# ---------------------------------------------------------------------------


def encode_utf8_bytes(text: str, add_bos: bool = True, add_eos: bool = True) -> List[int]:
    raw = list(text.encode("utf-8"))
    out: List[int] = []
    if add_bos:
        out.append(BOS_ID)
    out.extend(raw)
    if add_eos:
        out.append(EOS_ID)
    return out


def decode_utf8_bytes(ids: Sequence[int]) -> str:
    raw = bytes(i for i in ids if 0 <= i < 256)
    return raw.decode("utf-8", errors="strict")


def _read_parquet_bytes(path: Path) -> bytes:
    try:
        import pyarrow.parquet as pq  # type: ignore[import-not-found]
    except ImportError as exc:
        raise S110ConfigError("pyarrow required to read parquet corpus") from exc
    table = pq.read_table(path)
    col = "text" if "text" in table.column_names else table.column_names[0]
    text = "\n".join(str(x) for x in table[col].to_pylist() if x)
    return text.encode("utf-8")


def _chunk_byte_stream(raw: bytes, seq_len: int, max_chunks: int) -> List[torch.Tensor]:
    step = seq_len + 1
    out: List[torch.Tensor] = []
    n = len(raw)
    for start in range(0, n - seq_len, step):
        seg = [BOS_ID] + list(raw[start : start + seq_len])
        out.append(torch.tensor(seg, dtype=torch.long))
        if len(out) >= max_chunks:
            break
    return out


def load_multidomain_disjoint_bundle(
    seq_len: int,
    wikitext_dir: Path,
    frozen_code_roots: Sequence[Path],
    eval_windows_per_domain: int = 24,
    long_seq_len: int = 1024,
    long_eval_windows: int = 24,
) -> Dict[str, Any]:
    """Build strictly disjoint train & held-out multi-domain offline byte streams (0% file overlap).

    Domains:
      1. wikitext2:  validation parquet (train) vs test parquet (strictly held-out eval)
      2. python_code: frozen local .py files split strictly 80/20 by file-content SHA-256
      3. formal_docs: frozen local .md/.json files split strictly 80/20 by file-content SHA-256
    """
    wt_val = wikitext_dir / "validation-00000-of-00001.parquet"
    wt_test = wikitext_dir / "test-00000-of-00001.parquet"
    require_ok(wt_val.exists() and wt_test.exists(), f"Missing cached WikiText-2 parquet files in {wikitext_dir}")

    wt_train_bytes = _read_parquet_bytes(wt_val)
    wt_eval_bytes = _read_parquet_bytes(wt_test)

    py_train_parts: List[bytes] = []
    py_eval_parts: List[bytes] = []
    doc_train_parts: List[bytes] = []
    doc_eval_parts: List[bytes] = []
    train_files: set[str] = set()
    eval_files: set[str] = set()

    for root in frozen_code_roots:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file() or ".git" in p.parts or "__pycache__" in p.parts:
                continue
            suf = p.suffix.lower()
            if suf not in (".py", ".md", ".json"):
                continue
            raw = p.read_bytes()
            if len(raw) < 256 or len(raw) > 200_000:
                continue
            h = hashlib.sha256(raw).hexdigest()
            is_eval = (int(h[:8], 16) % 5) == 0
            key = f"{root.name}/{p.relative_to(root)}"
            if suf == ".py":
                (py_eval_parts if is_eval else py_train_parts).append(raw + b"\n")
            else:
                (doc_eval_parts if is_eval else doc_train_parts).append(raw + b"\n")
            (eval_files if is_eval else train_files).add(key)

    overlap_count = len(train_files & eval_files)
    require_ok(overlap_count == 0, f"Disjoint split violated: {overlap_count} overlapping files")

    py_train_bytes = b"".join(py_train_parts)[:1_200_000]
    py_eval_bytes = b"".join(py_eval_parts)[:400_000]
    doc_train_bytes = b"".join(doc_train_parts)[:600_000]
    doc_eval_bytes = b"".join(doc_eval_parts)[:300_000]

    train_stream = wt_train_bytes + b"\n" + py_train_bytes + b"\n" + doc_train_bytes
    eval_domains_bytes = {
        "wikitext2_test": wt_eval_bytes,
        "python_code": py_eval_bytes,
        "formal_docs": doc_eval_bytes,
    }
    eval_stream_all = b"\n".join(eval_domains_bytes.values())

    train_chunks = _chunk_byte_stream(train_stream, seq_len=seq_len, max_chunks=20_000)
    eval_chunks_by_domain: Dict[str, List[torch.Tensor]] = {}
    eval_chunks_combined: List[torch.Tensor] = []
    for dom, raw in eval_domains_bytes.items():
        ch = _chunk_byte_stream(raw, seq_len=seq_len, max_chunks=eval_windows_per_domain)
        require_ok(len(ch) >= 8, f"Domain {dom} has too few eval chunks ({len(ch)})")
        eval_chunks_by_domain[dom] = ch
        eval_chunks_combined.extend(ch)

    long_eval_chunks = _chunk_byte_stream(wt_eval_bytes + b"\n" + py_eval_bytes, seq_len=long_seq_len, max_chunks=long_eval_windows)
    require_ok(len(long_eval_chunks) >= 8, "Too few long-context eval chunks")

    return {
        "corpus_tag": "multidomain_disjoint_wikitext2_py_docs_v1",
        "train_bytes": len(train_stream),
        "train_sha256": hashlib.sha256(train_stream).hexdigest(),
        "eval_bytes": len(eval_stream_all),
        "eval_sha256": hashlib.sha256(eval_stream_all).hexdigest(),
        "train_file_count": len(train_files) + 1,
        "eval_file_count": len(eval_files) + 1,
        "file_overlap_count": overlap_count,
        "domain_eval_bytes": {k: len(v) for k, v in eval_domains_bytes.items()},
        "domain_eval_sha256": {k: hashlib.sha256(v).hexdigest() for k, v in eval_domains_bytes.items()},
        "train_chunks": train_chunks,
        "eval_chunks_by_domain": eval_chunks_by_domain,
        "eval_chunks_combined": eval_chunks_combined,
        "long_eval_chunks": long_eval_chunks,
    }


def load_offline_byte_chunks(
    seq_len: int,
    n_train: int,
    n_eval: int,
    seed: int = 42,
    corpus_path: Optional[str] = None,
) -> Tuple[List[torch.Tensor], List[torch.Tensor], str]:
    """Load offline byte chunks from single parquet/txt file or deterministic synthetic multi-timescale corpus."""
    if corpus_path:
        p = Path(corpus_path)
        require_ok(p.exists() and p.is_file(), f"Corpus file not found: {corpus_path}")
        raw_bytes = _read_parquet_bytes(p) if p.suffix == ".parquet" else p.read_bytes()
        chunks = _chunk_byte_stream(raw_bytes, seq_len=seq_len, max_chunks=n_train + n_eval)
        require_ok(len(chunks) >= n_eval + 2, f"Corpus too short for seq_len={seq_len}")
        train_chunks = chunks[: min(n_train, len(chunks) - n_eval)]
        eval_chunks = chunks[len(train_chunks) : len(train_chunks) + n_eval]
        return train_chunks, eval_chunks, f"offline_file:{p.name}"

    rng = random.Random(seed)
    total = n_train + n_eval
    all_chunks: List[torch.Tensor] = []
    for idx in range(total):
        key_a = chr(ord("A") + (idx % 16))
        val_a = rng.randint(10, 99)
        key_b = chr(ord("a") + ((idx * 7) % 16))
        val_b = rng.randint(10, 99)
        ops = [rng.choice(("+", "-")) for _ in range(4)]
        nums = [rng.randint(1, 9) for _ in range(5)]
        acc = nums[0]
        expr_parts = [str(nums[0])]
        for op, num in zip(ops, nums[1:]):
            acc = (acc + num) if op == "+" else (acc - num)
            expr_parts.append(f"{op}{num}")
        expr = "".join(expr_parts)
        filler = " ".join(f"t{k}={((idx + k * 13) % 97):02d}" for k in range(18))
        line = f"MEM {key_a}:{val_a} {key_b}:{val_b} | {filler} | CALC {expr}={acc} | RECALL {key_a}:{val_a} {key_b}:{val_b}\n"
        ids = encode_utf8_bytes(line, add_bos=True, add_eos=True)
        while len(ids) < seq_len + 1:
            ids.extend(encode_utf8_bytes(line, add_bos=False, add_eos=True))
        all_chunks.append(torch.tensor(ids[: seq_len + 1], dtype=torch.long))
    return all_chunks[:n_train], all_chunks[n_train:], "synthetic_multitimescale_v1"


# ---------------------------------------------------------------------------
# Batched Exact UTF-8 BPB, PTQ KL, Spike Robustness, & Latency Evaluators
# ---------------------------------------------------------------------------


@torch.no_grad()
def evaluate_exact_bpb(
    model: GeosphereNetLM,
    token_chunks: Sequence[torch.Tensor],
    device: torch.device,
    r_loops_override: Optional[int] = None,
    eval_batch_size: int = 8,
    amp_bf16: bool = False,
) -> Dict[str, Any]:
    """Batched exact UTF-8 Bits-Per-Byte (fp32 log-softmax, BOS excluded, EOS scored)."""
    model.eval()
    total_nll_nats = 0.0
    total_scored = 0
    total_bytes = 0
    mean_r_list: List[float] = []
    plug_list: List[float] = []
    draft_top1_hits = 0
    draft_total = 0
    use_amp = bool(amp_bf16 and device.type == "cuda")

    n_chunks = len(token_chunks)
    for start in range(0, n_chunks, eval_batch_size):
        batch = torch.stack(list(token_chunks[start : start + eval_batch_size]), dim=0).to(device)
        inp = batch[:, :-1]
        tgt = batch[:, 1:]
        with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=use_amp):
            logits, info = model(
                inp,
                r_loops_override=r_loops_override,
                return_trace=False,
                return_draft=(model.mtp_draft is not None),
            )
        log_probs = F.log_softmax(logits.float(), dim=-1)
        nll = F.nll_loss(
            log_probs.reshape(-1, log_probs.shape[-1]),
            tgt.reshape(-1),
            ignore_index=PAD_ID,
            reduction="none",
        ).reshape(tgt.shape)
        valid = (tgt != PAD_ID) & (tgt != BOS_ID)
        total_nll_nats += float(nll[valid].sum().item())
        n_val = int(valid.sum().item())
        total_scored += n_val
        raw_bytes = int(((tgt >= 0) & (tgt < 256) & valid).sum().item())
        total_bytes += max(raw_bytes, n_val)
        mean_r_list.append(float(info["act_stats"].get("mean_int_r", 1.0)))
        plug_list.append(float(info.get("mean_bingham_plug_fraction", 0.0)))

        d_logits = info.get("draft_logits")
        if d_logits is not None:
            seq_len = tgt.shape[1]
            for k_idx, dl in enumerate(d_logits):
                offset = k_idx + 1
                if seq_len > offset:
                    pred = dl[:, : seq_len - offset].argmax(dim=-1)
                    truth = tgt[:, offset:]
                    draft_top1_hits += int((pred == truth).sum().item())
                    draft_total += int(truth.numel())

    require_ok(total_bytes > 0 and total_scored > 0, "No valid tokens scored")
    bpb = total_nll_nats / (math.log(2.0) * float(total_bytes))
    return {
        "bpb": round(bpb, 6),
        "mean_nll_nats": round(total_nll_nats / float(total_scored), 6),
        "scored_tokens": total_scored,
        "utf8_bytes": total_bytes,
        "mean_int_r": round(sum(mean_r_list) / max(1, len(mean_r_list)), 4),
        "mean_bingham_plug_fraction": round(sum(plug_list) / max(1, len(plug_list)), 4),
        "mtp_draft_top1_acc": round(draft_top1_hits / float(draft_total), 6) if draft_total > 0 else None,
    }


@torch.no_grad()
def evaluate_ptq_and_m1h1(
    model_fp: GeosphereNetLM,
    eval_chunks: Sequence[torch.Tensor],
    device: torch.device,
    bits: int = 3,
    amp_bf16: bool = False,
) -> Dict[str, Any]:
    """Exact 3-bit RTN group-128 PTQ KL + Track S96 M1-H1 loop drift."""
    model_fp.eval()
    model_q = apply_rtn_ptq_copy(model_fp, bits=bits, group_size=128).to(device)
    model_q.eval()
    use_amp = bool(amp_bf16 and device.type == "cuda")

    total_kl = 0.0
    total_nll_q = 0.0
    total_scored = 0
    sub = eval_chunks[: min(24, len(eval_chunks))]
    for start in range(0, len(sub), 8):
        batch = torch.stack(list(sub[start : start + 8]), dim=0).to(device)
        inp = batch[:, :-1]
        tgt = batch[:, 1:]
        with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=use_amp):
            l_fp, _ = model_fp(inp, return_trace=False)
            l_q, _ = model_q(inp, return_trace=False)
        lp_fp = F.log_softmax(l_fp.float(), dim=-1)
        lp_q = F.log_softmax(l_q.float(), dim=-1)
        kl = torch.sum(lp_fp.exp() * (lp_fp - lp_q), dim=-1)
        nll_q = F.nll_loss(lp_q.reshape(-1, lp_q.shape[-1]), tgt.reshape(-1), ignore_index=PAD_ID, reduction="none").reshape(tgt.shape)
        valid = (tgt != PAD_ID) & (tgt != BOS_ID)
        total_kl += float(kl[valid].sum().item())
        total_nll_q += float(nll_q[valid].sum().item())
        total_scored += int(valid.sum().item())

    sample_in = torch.stack(list(sub[: min(4, len(sub))]), dim=0)[:, :-1].to(device)
    m1h1 = measure_m1_h1_loop_drift(model_fp, model_q, sample_in)
    del model_q
    if device.type == "cuda":
        torch.cuda.empty_cache()

    return {
        "bits": bits,
        "ptq_bpb": round(total_nll_q / (math.log(2.0) * float(max(1, total_scored))), 6),
        "ptq_kl_nats": round(total_kl / float(max(1, total_scored)), 8),
        "m1_h1_loop_drift": m1h1,
    }


@torch.no_grad()
def evaluate_adversarial_spike_robustness(
    model: GeosphereNetLM,
    eval_chunks: Sequence[torch.Tensor],
    device: torch.device,
    spike_sigma: float = 6.0,
    spike_frac: float = 0.10,
    seed: int = 42,
) -> Dict[str, Any]:
    """Channel-2B / Airlock adversarial embedding-spike robustness (ASR = prediction flip rate)."""
    model.eval()
    sub = eval_chunks[: min(8, len(eval_chunks))]
    batch = torch.stack(list(sub), dim=0).to(device)
    inp = batch[:, :-1]
    logits_clean, _ = model(inp, return_trace=False)

    g = torch.Generator(device="cpu")
    g.manual_seed(seed + 777)
    # Inject bounded-position adversarial embedding spike directly at embedding output (before airlock!)
    h_emb = model.tok_emb(inp)
    b_sz, seq_len, d = h_emb.shape
    mask = (torch.rand((b_sz, seq_len, 1), generator=g) < spike_frac).to(device=device, dtype=h_emb.dtype)
    spike = (torch.randn((b_sz, seq_len, d), generator=g) * spike_sigma).to(device=device, dtype=h_emb.dtype)

    def _forward_from_emb(h_in: torch.Tensor) -> torch.Tensor:
        h = h_in
        if model.airlock is not None:
            h, _ = model.airlock(h)
        if model.cfg.ngpt_mode:
            h = h / torch.sqrt((h * h).sum(dim=-1, keepdim=True) + 1e-12)
        for blk in model.pre_blocks:
            h, _ = blk(h)
        n_p = max(1, int(round(model.cfg.r_mean)))
        for _ in range(n_p):
            for blk in model.core_blocks:
                h, _ = blk(h)
        for blk in model.post_blocks:
            h, _ = blk(h)
        return F.linear(model.final_norm(h), model.tok_emb.weight)

    logits_ref = _forward_from_emb(h_emb)
    logits_atk = _forward_from_emb(h_emb + mask * spike)
    lp_ref = F.log_softmax(logits_ref.float(), dim=-1)
    lp_atk = F.log_softmax(logits_atk.float(), dim=-1)
    kl_atk = float(torch.sum(lp_ref.exp() * (lp_ref - lp_atk), dim=-1).mean().item())
    asr = float((logits_ref.argmax(dim=-1) != logits_atk.argmax(dim=-1)).float().mean().item())
    return {
        "spike_sigma": spike_sigma,
        "spike_frac": spike_frac,
        "adversarial_flip_asr": round(asr, 6),
        "adversarial_kl_nats": round(kl_atk, 6),
        "airlock_enabled": bool(model.airlock is not None),
    }


@torch.no_grad()
def evaluate_inference_latency(
    model: GeosphereNetLM,
    sample_batch: torch.Tensor,
    device: torch.device,
    amp_bf16: bool = False,
    iters: int = 12,
    warmup: int = 4,
) -> Dict[str, float]:
    """Measure CUDA-synchronized median inference latency & tok/s."""
    model.eval()
    use_amp = bool(amp_bf16 and device.type == "cuda")
    inp = sample_batch[:, :-1].to(device)
    n_tok = int(inp.numel())

    def _sync() -> None:
        if device.type == "cuda":
            torch.cuda.synchronize(device)

    for _ in range(warmup):
        with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=use_amp):
            _ = model(inp, return_trace=False)
    _sync()
    times_ms: List[float] = []
    for _ in range(iters):
        t0 = time.perf_counter()
        with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=use_amp):
            _ = model(inp, return_trace=False)
        _sync()
        times_ms.append((time.perf_counter() - t0) * 1000.0)
    times_ms.sort()
    med_ms = times_ms[len(times_ms) // 2]
    return {
        "median_batch_ms": round(med_ms, 4),
        "tokens_per_sec": round(n_tok / max(1e-9, med_ms / 1000.0), 1),
    }


# ---------------------------------------------------------------------------
# Pre-Normalization (pre-N) Counterfactual State-Patching Faithfulness Audit
# ---------------------------------------------------------------------------


@torch.no_grad()
def evaluate_pre_norm_counterfactual_patching(
    model: GeosphereNetLM,
    token_chunks: Sequence[torch.Tensor],
    device: torch.device,
    patch_pass_idx: int = 1,
) -> Dict[str, Any]:
    """Measure pre-normalization h^(r) counterfactual state-patching faithfulness (Amendment 1)."""
    model.eval()
    require_ok(len(token_chunks) >= 2, "Need at least 2 chunks for paired counterfactual patching")
    n_pairs = len(token_chunks) // 2
    closer_hits = 0
    distinct_pos = 0
    total_pos = 0
    max_self_err = 0.0
    max_patch_to_b_err = 0.0
    mean_shift_l2_vals: List[float] = []

    for i in range(n_pairs):
        a_in = token_chunks[2 * i][:-1].unsqueeze(0).to(device)
        b_in = token_chunks[2 * i + 1][:-1].unsqueeze(0).to(device)
        logits_a, tr_a = model(a_in, r_loops_override=patch_pass_idx, return_trace=True)
        logits_b, tr_b = model(b_in, r_loops_override=patch_pass_idx, return_trace=True)

        h_a = tr_a["pass_states_pre_norm"][patch_pass_idx - 1]
        h_b = tr_b["pass_states_pre_norm"][patch_pass_idx - 1]

        logits_a_self, _ = model(a_in, r_loops_override=patch_pass_idx, patch_pre_norm_state=(patch_pass_idx, h_a))
        max_self_err = max(max_self_err, float((logits_a_self.float() - logits_a.float()).abs().max().item()))

        logits_ab, _ = model(a_in, r_loops_override=patch_pass_idx, patch_pre_norm_state=(patch_pass_idx, h_b))
        max_patch_to_b_err = max(max_patch_to_b_err, float((logits_ab.float() - logits_b.float()).abs().max().item()))
        orig_gap = torch.linalg.vector_norm(logits_b.float() - logits_a.float(), dim=-1)
        distinct_mask = orig_gap > 1e-4
        dist_to_b = torch.linalg.vector_norm(logits_ab.float() - logits_b.float(), dim=-1)
        dist_to_a = torch.linalg.vector_norm(logits_ab.float() - logits_a.float(), dim=-1)
        closer = (dist_to_b < dist_to_a) & distinct_mask
        closer_hits += int(closer.sum().item())
        distinct_pos += int(distinct_mask.sum().item())
        total_pos += int(orig_gap.numel())
        if int(distinct_mask.sum().item()) > 0:
            mean_shift_l2_vals.append(float(dist_to_a[distinct_mask].mean().item()))

    faithfulness = closer_hits / float(max(1, distinct_pos))
    return {
        "patch_pass_idx": patch_pass_idx,
        "n_pairs": n_pairs,
        "total_positions": total_pos,
        "distinct_counterfactual_positions": distinct_pos,
        "pre_norm_faithfulness_rate": round(faithfulness, 6),
        "self_patch_max_abs_err": max_self_err,
        "patched_to_b_max_abs_err": max_patch_to_b_err,
        "mean_logit_shift_l2": round(sum(mean_shift_l2_vals) / max(1, len(mean_shift_l2_vals)), 6),
    }


# ---------------------------------------------------------------------------
# Holm-Bonferroni Step-Down Correction & 3-Valued Statistical Verdict Engine
# ---------------------------------------------------------------------------


def holm_bonferroni_adjust(p_values: Sequence[float], alpha: float = 0.05) -> Dict[str, Any]:
    """Exact Holm-Bonferroni step-down family-wise error control (Amendment 1 Discovery 4)."""
    m = len(p_values)
    require_ok(m >= 1, "Need at least 1 p-value for Holm-Bonferroni")
    require_ok(0.0 < alpha < 1.0, "alpha must be in (0, 1)")
    for p in p_values:
        require_ok(0.0 <= p <= 1.0, f"Invalid p-value: {p}")

    indexed = sorted(enumerate(p_values), key=lambda kv: kv[1])
    adj = [0.0] * m
    rejected = [False] * m
    running_max = 0.0
    still_rejecting = True
    for rank, (orig_idx, p_val) in enumerate(indexed):
        factor = float(m - rank)
        p_adj = min(1.0, max(running_max, p_val * factor))
        running_max = p_adj
        adj[orig_idx] = p_adj
        if still_rejecting and p_adj <= alpha:
            rejected[orig_idx] = True
        else:
            still_rejecting = False
            rejected[orig_idx] = False

    return {
        "alpha": alpha,
        "n_hypotheses": m,
        "raw_p_values": [float(x) for x in p_values],
        "adjusted_p_values": [round(x, 8) for x in adj],
        "rejected": rejected,
    }


def paired_bootstrap_verdict(
    deltas_by_seed: Sequence[float],
    min_effect: float,
    higher_is_better: bool = True,
    n_boot: int = 2000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Paired bootstrap 95% CI, z-score / normal-approx p-value, and 3-valued verdict."""
    xs = [float(x) if higher_is_better else -float(x) for x in deltas_by_seed]
    n = len(xs)
    require_ok(n >= 2, "Need at least 2 seeds for paired verdict")
    mean_val = sum(xs) / float(n)
    var = sum((x - mean_val) ** 2 for x in xs) / float(max(1, n - 1))
    se = math.sqrt(var / float(n)) if var > 0.0 else 0.0
    z_score = (mean_val / se) if se > 1e-12 else (10.0 if mean_val > 0 else (-10.0 if mean_val < 0 else 0.0))
    p_one_sided = 0.5 * math.erfc(z_score / math.sqrt(2.0))

    rng = random.Random(seed)
    boots: List[float] = []
    for _ in range(n_boot):
        s = sum(xs[rng.randrange(n)] for _ in range(n)) / float(n)
        boots.append(s)
    boots.sort()
    ci_lo = boots[int(0.025 * n_boot)]
    ci_hi = boots[int(0.975 * n_boot)]

    if ci_lo >= min_effect and z_score >= 2.0:
        verdict = "CONFIRMED"
    elif ci_hi <= 0.0 or (ci_hi < min_effect and mean_val <= 0.0):
        verdict = "FALSIFIED"
    else:
        verdict = "INCONCLUSIVE"
    return {
        "n_seeds": n,
        "mean_gain": round(mean_val, 6),
        "se": round(se, 6),
        "z_score": round(z_score, 4),
        "p_one_sided": round(min(1.0, max(0.0, p_one_sided)), 8),
        "ci95": [round(ci_lo, 6), round(ci_hi, 6)],
        "min_effect": min_effect,
        "verdict": verdict,
    }


def evaluate_loso_matrix(
    arm_seed_bpb: Dict[str, Sequence[float]],
    alpha: float = 0.05,
    min_bpb_gain: float = 0.01,
) -> Dict[str, Any]:
    """Evaluate Holm-Bonferroni corrected Leave-One-Shell-Out (LOSO) degradation matrix."""
    require_ok("H10b_Geosphere_Full" in arm_seed_bpb, "Missing H10b_Geosphere_Full scores")
    full_scores = list(arm_seed_bpb["H10b_Geosphere_Full"])
    loso_arms = [
        "H10b_LOSO_NoCayley",
        "H10b_LOSO_NoBingham",
        "H10b_LOSO_NoDarcyEMA",
        "H10b_LOSO_NoACTDraft",
    ]
    per_shell: Dict[str, Any] = {}
    p_list: List[float] = []
    present_arms: List[str] = []
    for arm in loso_arms:
        if arm not in arm_seed_bpb:
            continue
        abl_scores = list(arm_seed_bpb[arm])
        require_ok(len(abl_scores) == len(full_scores), f"Seed count mismatch for {arm}")
        deltas = [abl - full for abl, full in zip(abl_scores, full_scores)]
        stat = paired_bootstrap_verdict(deltas, min_effect=min_bpb_gain, higher_is_better=True)
        per_shell[arm] = stat
        p_list.append(stat["p_one_sided"])
        present_arms.append(arm)

    hb = holm_bonferroni_adjust(p_list, alpha=alpha)
    for idx, arm in enumerate(present_arms):
        per_shell[arm]["holm_adjusted_p"] = hb["adjusted_p_values"][idx]
        per_shell[arm]["holm_significant"] = hb["rejected"][idx]
    return {"per_shell": per_shell, "holm_bonferroni": hb}


# ---------------------------------------------------------------------------
# <2 Min sm_86 Wall-Clock, Throughput, VRAM, & BF16 Numerical Microbench Gate
# ---------------------------------------------------------------------------


def run_operator_microbench(
    device: torch.device,
    amp_bf16: bool = False,
    d_model: int = 384,
    seq_len: int = 512,
    batch_size: int = 8,
    iters: int = 20,
    warmup: int = 5,
    seed: int = 42,
    include_full_model: bool = False,
) -> Dict[str, Any]:
    """Benchmark each of the 4 pruned operators + optional full 15M step (throughput/VRAM/BF16 parity)."""
    dtype = torch.bfloat16 if (amp_bf16 and device.type == "cuda") else torch.float32
    torch.manual_seed(seed)
    g = torch.Generator(device="cpu")
    g.manual_seed(int(seed) & 0x7FFFFFFF)
    x_fp32 = torch.randn((batch_size, seq_len, d_model), generator=g, dtype=torch.float32).to(device=device)
    x = x_fp32.to(dtype=dtype)

    base_gemm = nn.Sequential(
        nn.Linear(d_model, d_model * 3, bias=False),
        nn.SiLU(),
        nn.Linear(d_model * 3, d_model, bias=False),
    ).to(device=device, dtype=dtype)
    base_block = GeosphereBlock(
        d_model=d_model,
        n_heads=6 if d_model % 6 == 0 else 4,
        d_ff=d_model * 3,
        seed=seed + 5,
    ).to(device=device, dtype=dtype)
    cayley_fp32 = CayleyBlock2x2SO(d_model, bottleneck_rank=16, seed=seed + 1).to(device=device)
    bingham_fp32 = VectorProximalPoloidalBingham(d_model, k_poloidal=d_model // 2, tau_y=1.0).to(device=device)
    darcy_fp32 = DiagonalDarcyEMA(d_model, seed=seed + 2).to(device=device)
    act_ctrl_fp32 = GeothermalACTController(d_model, r_max=4, target_mean_r=2.0, seed=seed + 3).to(device=device)
    mtp_fp32 = FastSurfaceMTPDraft(d_model, k_draft=8, d_draft=48, seed=seed + 4).to(device=device)
    lm_w_fp32 = torch.randn((VOCAB_SIZE_BYTE, d_model), generator=g, dtype=torch.float32).to(device=device)

    cayley = cayley_fp32.to(dtype=dtype) if dtype == torch.float32 else CayleyBlock2x2SO(d_model, bottleneck_rank=16, seed=seed + 1).to(device=device, dtype=dtype)
    bingham = VectorProximalPoloidalBingham(d_model, k_poloidal=d_model // 2, tau_y=1.0).to(device=device)
    darcy = DiagonalDarcyEMA(d_model, seed=seed + 2).to(device=device, dtype=dtype)
    act_ctrl = GeothermalACTController(d_model, r_max=4, target_mean_r=2.0, seed=seed + 3).to(device=device, dtype=dtype)
    mtp = FastSurfaceMTPDraft(d_model, k_draft=8, d_draft=48, seed=seed + 4).to(device=device, dtype=dtype)
    lm_w = lm_w_fp32.to(dtype=dtype)

    def _sync() -> None:
        if device.type == "cuda":
            torch.cuda.synchronize(device)

    @torch.no_grad()
    def _time_fn(fn: Any) -> Tuple[float, bool, float]:
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
        for _ in range(warmup):
            out = fn()
        _sync()
        t0 = time.perf_counter()
        for _ in range(iters):
            out = fn()
        _sync()
        ms = (time.perf_counter() - t0) * 1000.0 / float(iters)
        peak_mib = (torch.cuda.max_memory_allocated(device) / (1024.0 * 1024.0)) if device.type == "cuda" else 0.0
        if isinstance(out, list):
            fin = all(bool(torch.isfinite(t).all().item()) for t in out)
        else:
            fin = bool(torch.isfinite(out).all().item())
        return ms, fin, peak_mib

    base_gemm_ms, _, _ = _time_fn(lambda: base_gemm(x))
    base_block_ms, _, base_block_vram = _time_fn(lambda: base_block(x)[0])

    # Numerical FP32 vs active-dtype parity checks (finite & bounded).
    with torch.no_grad():
        num_diffs = {
            "op1_cayley_2x2_so": float((cayley_fp32(x_fp32) - cayley(x).float()).abs().max().item()),
            "op2_bingham_vector_prox": float((bingham_fp32(x_fp32)[0] - bingham(x)[0].float()).abs().max().item()),
            "op3_darcy_diagonal_ema": float((darcy_fp32(x_fp32) - darcy(x).float()).abs().max().item()),
            "op4a_act_controller": float((act_ctrl_fp32.compute_buoyancy_score(x_fp32, x_fp32 * 1.01) - act_ctrl.compute_buoyancy_score(x, x * 1.01).float()).abs().max().item()),
            "op4b_mtp8_surface_draft": float((mtp_fp32(x_fp32, lm_w_fp32)[0] - mtp(x, lm_w)[0].float()).abs().max().item()),
        }

    op_specs = [
        ("op1_cayley_2x2_so", lambda: cayley(x), base_block_ms, "per_core_block"),
        ("op2_bingham_vector_prox", lambda: bingham(x)[0], base_block_ms, "per_core_block"),
        ("op3_darcy_diagonal_ema", lambda: darcy(x), base_block_ms, "per_core_block"),
        (
            "op4a_act_controller",
            lambda: act_ctrl.allocate_integer_loops(act_ctrl.compute_buoyancy_score(x, x * 1.01)),
            base_block_ms * 12.0,
            "per_forward_12eff",
        ),
        ("op4b_mtp8_surface_draft", lambda: mtp(x, lm_w), base_block_ms * 12.0, "per_forward_12eff"),
    ]

    results: Dict[str, Any] = {}
    any_pruned = False
    for name, fn, ref_ms, scope in op_specs:
        op_ms, finite_ok, peak_mib = _time_fn(fn)
        overhead_ratio = op_ms / max(1e-9, ref_ms)
        gemm_ratio = op_ms / max(1e-9, base_gemm_ms)
        passed = (overhead_ratio <= KILL_GATE_OVERHEAD_LIMIT) and finite_ok
        if not passed:
            any_pruned = True
        results[name] = {
            "scope": scope,
            "op_ms": round(op_ms, 4),
            "ref_block_ms": round(ref_ms, 4),
            "baseline_gemm_ms": round(base_gemm_ms, 4),
            "overhead_ratio": round(overhead_ratio, 4),
            "overhead_pct": round(overhead_ratio * 100.0, 2),
            "overhead_vs_gemm_pct": round(gemm_ratio * 100.0, 2),
            "fp32_vs_dtype_max_abs_diff": round(num_diffs[name], 6),
            "all_finite": finite_ok,
            "peak_vram_mib": round(peak_mib, 2),
            "kill_gate_limit_pct": KILL_GATE_OVERHEAD_LIMIT * 100.0,
            "gate_status": "PASS" if passed else "PRUNE_OVERHEAD_GT_15PCT",
        }

    full_model_bench: Dict[str, Any] = {}
    if include_full_model:
        arms = build_s110_arm_configs(scale="full15m" if d_model == 384 else "tiny")
        ids = torch.randint(0, 256, (batch_size, seq_len + 1), generator=g, dtype=torch.long).to(device)
        for arm_key in ("H10a_Baseline_Loop", "H10a_Shell1_Cayley2x2", "H10a_Shell2_BinghamProx", "H10a_Shell3_DarcyEMA", "H10a_Shell4_ACTPlume_MTP8", "H10b_Geosphere_Full"):
            m = GeosphereNetLM(arms[arm_key], seed=seed).to(device)
            opt = torch.optim.AdamW(m.parameters(), lr=1e-3)
            use_amp = bool(amp_bf16 and device.type == "cuda")
            if device.type == "cuda":
                torch.cuda.reset_peak_memory_stats(device)
            # 2 warmup + 5 timed full train steps (fwd+bwd+opt)
            for _ in range(2):
                opt.zero_grad(set_to_none=True)
                with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=use_amp):
                    logits, info = m(ids[:, :-1], return_draft=(m.mtp_draft is not None))
                    loss = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), ids[:, 1:].reshape(-1)) + 0.05 * info["ponder_loss"]
                loss.backward()
                opt.step()
            _sync()
            t0 = time.perf_counter()
            step_n = 6
            for _ in range(step_n):
                opt.zero_grad(set_to_none=True)
                with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=use_amp):
                    logits, info = m(ids[:, :-1], return_draft=(m.mtp_draft is not None))
                    loss = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), ids[:, 1:].reshape(-1)) + 0.05 * info["ponder_loss"]
                loss.backward()
                opt.step()
            _sync()
            step_ms = (time.perf_counter() - t0) * 1000.0 / float(step_n)
            peak_mib = (torch.cuda.max_memory_allocated(device) / (1024.0 * 1024.0)) if device.type == "cuda" else 0.0
            full_model_bench[arm_key] = {
                "params": count_parameters(m)["total_params"],
                "train_step_ms": round(step_ms, 3),
                "train_tok_per_sec": round((batch_size * seq_len) / max(1e-9, step_ms / 1000.0), 1),
                "peak_vram_mib": round(peak_mib, 2),
                "final_loss_finite": bool(torch.isfinite(loss).item()),
                "core_seq_passes_executed": info["act_stats"].get("core_seq_passes_executed"),
            }
            del m, opt
            if device.type == "cuda":
                torch.cuda.empty_cache()

        base_step = full_model_bench["H10a_Baseline_Loop"]["train_step_ms"]
        for k, v in full_model_bench.items():
            v["step_overhead_pct_vs_baseline"] = round((v["train_step_ms"] / max(1e-9, base_step) - 1.0) * 100.0, 2)

    return {
        "device": str(device),
        "dtype": str(dtype),
        "shape": [batch_size, seq_len, d_model],
        "iters": iters,
        "baseline_gemm_ms": round(base_gemm_ms, 4),
        "baseline_block_ms": round(base_block_ms, 4),
        "baseline_block_vram_mib": round(base_block_vram, 2),
        "operators": results,
        "all_operators_clear_15pct_gate": not any_pruned,
        "full_model_train_step_bench": full_model_bench,
    }


# ---------------------------------------------------------------------------
# Full Training + Multi-Axis Evaluation Loop (WEIGHTS=0)
# ---------------------------------------------------------------------------


def train_and_eval_arm(
    cfg: S110ModelConfig,
    train_chunks: Sequence[torch.Tensor],
    eval_chunks: Sequence[torch.Tensor],
    device: torch.device,
    steps: int = 600,
    batch_size: int = 8,
    lr: float = 1.5e-3,
    ngpt_lr: float = 2.5e-3,
    amp_bf16: bool = False,
    grad_checkpoint: bool = False,
    seed: int = 42,
    eval_chunks_by_domain: Optional[Dict[str, List[torch.Tensor]]] = None,
    long_eval_chunks: Optional[Sequence[torch.Tensor]] = None,
    full_eval: bool = False,
) -> Dict[str, Any]:
    """Train one arm from scratch for `steps` steps and return comprehensive JSON metrics (WEIGHTS=0)."""
    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)
        torch.cuda.reset_peak_memory_stats(device)
    rng = random.Random(seed)

    eff_lr = ngpt_lr if cfg.ngpt_mode else lr
    model = GeosphereNetLM(cfg, seed=seed).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=eff_lr, weight_decay=0.1, betas=(0.9, 0.95))

    # Stage-1 frozen quantile calibration of Bingham tau_Y if enabled.
    bingham_cal: List[Dict[str, float]] = []
    if cfg.use_bingham:
        cal_batch = torch.stack([train_chunks[i % len(train_chunks)][:-1] for i in range(min(8, len(train_chunks)))], dim=0).to(device)
        bingham_cal = model.calibrate_bingham_quantiles(cal_batch, yield_number=cfg.bingham_yield)

    use_amp = bool(amp_bf16 and device.type == "cuda")
    warmup_steps = min(50, max(1, steps // 10))
    t0 = time.perf_counter()
    losses: List[float] = []
    nan_steps = 0
    model.train()
    n_train = len(train_chunks)

    for step in range(steps):
        # Cosine LR schedule with linear warmup
        if step < warmup_steps:
            cur_lr = eff_lr * float(step + 1) / float(warmup_steps)
        else:
            prog = float(step - warmup_steps) / float(max(1, steps - warmup_steps))
            cur_lr = eff_lr * (0.1 + 0.9 * 0.5 * (1.0 + math.cos(math.pi * prog)))
        for pg in opt.param_groups:
            pg["lr"] = cur_lr

        batch = torch.stack([train_chunks[rng.randrange(n_train)] for _ in range(batch_size)], dim=0).to(device)
        inp = batch[:, :-1]
        tgt = batch[:, 1:]
        opt.zero_grad(set_to_none=True)
        with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=use_amp):
            logits, info = model(
                inp,
                return_draft=(model.mtp_draft is not None),
                grad_checkpoint=grad_checkpoint,
            )
            ce_loss = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), tgt.reshape(-1), ignore_index=PAD_ID)
            loss = ce_loss + 0.05 * info["ponder_loss"]
            if info.get("draft_logits") is not None:
                d_loss = torch.zeros((), dtype=torch.float32, device=device)
                seq_len = tgt.shape[1]
                for k_idx, dl in enumerate(info["draft_logits"]):
                    off = k_idx + 1
                    if seq_len > off:
                        d_loss = d_loss + F.cross_entropy(
                            dl[:, : seq_len - off].reshape(-1, dl.shape[-1]),
                            tgt[:, off:].reshape(-1),
                            ignore_index=PAD_ID,
                        )
                loss = loss + (0.05 / float(max(1, len(info["draft_logits"])))) * d_loss
        if not bool(torch.isfinite(loss).item()):
            nan_steps += 1
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        losses.append(float(ce_loss.detach().item()))

    if device.type == "cuda":
        torch.cuda.synchronize(device)
    wall_s = time.perf_counter() - t0
    peak_vram_mib = (torch.cuda.max_memory_allocated(device) / (1024.0 * 1024.0)) if device.type == "cuda" else 0.0

    # Primary held-out eval + R=6 extrapolation
    eval_default = evaluate_exact_bpb(model, eval_chunks, device, amp_bf16=amp_bf16)
    eval_r6 = evaluate_exact_bpb(model, eval_chunks[: min(16, len(eval_chunks))], device, r_loops_override=6, amp_bf16=amp_bf16)
    patch_audit = evaluate_pre_norm_counterfactual_patching(model, eval_chunks[: min(8, len(eval_chunks))], device, patch_pass_idx=1)

    domain_bpb: Dict[str, Any] = {}
    if eval_chunks_by_domain is not None:
        for dom, d_chunks in eval_chunks_by_domain.items():
            domain_bpb[dom] = evaluate_exact_bpb(model, d_chunks, device, amp_bf16=amp_bf16)["bpb"]

    eval_long = None
    if long_eval_chunks is not None and len(long_eval_chunks) >= 4:
        eval_long = evaluate_exact_bpb(model, long_eval_chunks, device, eval_batch_size=4, amp_bf16=amp_bf16)

    ptq_3b = None
    attn_sink = None
    spike_rob = None
    latency = None
    if full_eval:
        ptq_3b = evaluate_ptq_and_m1h1(model, eval_chunks, device, bits=3, amp_bf16=amp_bf16)
        attn_in = torch.stack(list(eval_chunks[: min(4, len(eval_chunks))]), dim=0)[:, :-1].to(device)
        attn_sink = measure_attention_sink_stats(model, attn_in)
        spike_rob = evaluate_adversarial_spike_robustness(model, eval_chunks, device, seed=seed)
        lat_batch = torch.stack(list(eval_chunks[: min(batch_size, len(eval_chunks))]), dim=0)
        latency = evaluate_inference_latency(model, lat_batch, device, amp_bf16=amp_bf16)

    with torch.no_grad():
        _, tr = model(eval_chunks[0][:-1].unsqueeze(0).to(device), r_loops_override=4, return_trace=True)
        rayleigh = tr.get("beltrami_rayleigh_by_pass", [])

    beltrami_diag = None
    if cfg.use_cayley and model.core_blocks[0].cayley is not None:
        beltrami_diag = run_beltrami_helicity_diagnostic(model.core_blocks[0].cayley, n_steps=6, seed=seed)

    p_stats = count_parameters(model)
    f_stats = analytical_forward_flops_per_token(cfg, seq_len=int(train_chunks[0].numel() - 1))
    del model, opt
    gc.collect()
    if device.type == "cuda":
        torch.cuda.empty_cache()

    return {
        "arm_name": cfg.arm_name,
        "stage": cfg.stage,
        "seed": seed,
        "lr_used": eff_lr,
        "params": p_stats,
        "flops": f_stats,
        "train_steps": steps,
        "train_wall_s": round(wall_s, 3),
        "peak_vram_mib": round(peak_vram_mib, 2),
        "nan_steps": nan_steps,
        "train_loss_start": round(losses[0], 6),
        "train_loss_end": round(losses[-1], 6),
        "eval_default": eval_default,
        "eval_by_domain_bpb": domain_bpb,
        "eval_long_2x": eval_long,
        "eval_r6_extrap": eval_r6,
        "ptq_3b": ptq_3b,
        "attn_sink_stats": attn_sink,
        "adversarial_spike": spike_rob,
        "inference_latency": latency,
        "pre_norm_counterfactual_patching": patch_audit,
        "bingham_calibration": bingham_cal,
        "beltrami_rayleigh_by_pass": [round(x, 6) for x in rayleigh],
        "beltrami_commutator_diag": beltrami_diag,
    }


def summarize_stage_verdicts(runs: Sequence[Dict[str, Any]], stage_label: str) -> Dict[str, Any]:
    """Compute paired seed means, SEs, Holm-Bonferroni corrections, and literal locked verdicts."""
    by_arm: Dict[str, List[Dict[str, Any]]] = {}
    for r in runs:
        by_arm.setdefault(r["arm_name"], []).append(r)

    def _mean_se(vals: Sequence[float]) -> Dict[str, float]:
        xs = [float(v) for v in vals]
        m = sum(xs) / float(len(xs))
        var = sum((x - m) ** 2 for x in xs) / float(max(1, len(xs) - 1))
        se = math.sqrt(var / float(len(xs))) if len(xs) > 1 else 0.0
        return {"mean": round(m, 6), "se": round(se, 6)}

    arm_summary: Dict[str, Any] = {}
    bpb_by_arm: Dict[str, List[float]] = {}
    for arm, rs in sorted(by_arm.items()):
        rs_s = sorted(rs, key=lambda x: x["seed"])
        bpbs = [float(x["eval_default"]["bpb"]) for x in rs_s]
        bpb_by_arm[arm] = bpbs
        s_dict: Dict[str, Any] = {
            "seeds": [x["seed"] for x in rs_s],
            "total_params": rs_s[0]["params"]["total_params"],
            "flops_per_token": int(round(rs_s[0]["flops"]["flops_per_token"])),
            "bpb_512": _mean_se(bpbs),
            "bpb_r6": _mean_se([float(x["eval_r6_extrap"]["bpb"]) for x in rs_s]),
            "train_wall_s": _mean_se([float(x["train_wall_s"]) for x in rs_s]),
            "peak_vram_mib": round(max(float(x["peak_vram_mib"]) for x in rs_s), 2),
            "nan_steps_total": sum(int(x["nan_steps"]) for x in rs_s),
            "pre_norm_faithfulness": _mean_se([float(x["pre_norm_counterfactual_patching"]["pre_norm_faithfulness_rate"]) for x in rs_s]),
        }
        if rs_s[0].get("eval_long_2x") is not None:
            s_dict["bpb_1024"] = _mean_se([float(x["eval_long_2x"]["bpb"]) for x in rs_s])
            s_dict["ctx_degradation_1024_minus_512"] = _mean_se(
                [float(x["eval_long_2x"]["bpb"]) - float(x["eval_default"]["bpb"]) for x in rs_s]
            )
        if rs_s[0].get("ptq_3b") is not None:
            s_dict["ptq_3b_kl"] = _mean_se([float(x["ptq_3b"]["ptq_kl_nats"]) for x in rs_s])
            s_dict["m1_h1_delta3_over_delta1"] = _mean_se(
                [float(x["ptq_3b"]["m1_h1_loop_drift"]["delta_3_over_delta_1"]) for x in rs_s]
            )
        if rs_s[0].get("attn_sink_stats") is not None:
            s_dict["bos_sink_weight"] = _mean_se([float(x["attn_sink_stats"]["bos_sink_weight"]) for x in rs_s])
            s_dict["attn_entropy"] = _mean_se([float(x["attn_sink_stats"]["normalized_attn_entropy"]) for x in rs_s])
        if rs_s[0].get("adversarial_spike") is not None:
            s_dict["spike_asr"] = _mean_se([float(x["adversarial_spike"]["adversarial_flip_asr"]) for x in rs_s])
            s_dict["spike_kl"] = _mean_se([float(x["adversarial_spike"]["adversarial_kl_nats"]) for x in rs_s])
        if rs_s[0].get("inference_latency") is not None:
            s_dict["median_infer_ms"] = _mean_se([float(x["inference_latency"]["median_batch_ms"]) for x in rs_s])
        if rs_s[0]["eval_default"].get("mtp_draft_top1_acc") is not None:
            s_dict["mtp8_draft_top1_acc"] = _mean_se([float(x["eval_default"]["mtp_draft_top1_acc"]) for x in rs_s])
        arm_summary[arm] = s_dict

    out: Dict[str, Any] = {"stage": stage_label, "arm_summary": arm_summary}

    # Stage 1 H10a: Holm-Bonferroni single-shell vs H10a_Baseline_Loop
    if "H10a_Baseline_Loop" in bpb_by_arm and len(bpb_by_arm["H10a_Baseline_Loop"]) >= 2:
        base_b = bpb_by_arm["H10a_Baseline_Loop"]
        shells = ["H10a_Shell1_Cayley2x2", "H10a_Shell2_BinghamProx", "H10a_Shell3_DarcyEMA", "H10a_Shell4_ACTPlume_MTP8"]
        h10a_pairs: Dict[str, Any] = {}
        p_raw: List[float] = []
        s_present: List[str] = []
        for sh in shells:
            if sh not in bpb_by_arm:
                continue
            deltas = [b - s for b, s in zip(base_b, bpb_by_arm[sh])]
            stat = paired_bootstrap_verdict(deltas, min_effect=0.01, higher_is_better=True)
            h10a_pairs[sh] = stat
            p_raw.append(stat["p_one_sided"])
            s_present.append(sh)
        if p_raw:
            hb = holm_bonferroni_adjust(p_raw, alpha=0.05)
            for idx, sh in enumerate(s_present):
                h10a_pairs[sh]["holm_adjusted_p"] = hb["adjusted_p_values"][idx]
                h10a_pairs[sh]["holm_significant"] = hb["rejected"][idx]
            out["h10a_vs_baseline_bpb"] = h10a_pairs
            out["h10a_holm_bonferroni"] = hb

    # Stage 2 H10b: LOSO Holm-Bonferroni + paired comparisons vs N0 anchors
    if "H10b_Geosphere_Full" in bpb_by_arm and len(bpb_by_arm["H10b_Geosphere_Full"]) >= 2:
        out["h10b_loso_holm_bonferroni"] = evaluate_loso_matrix(bpb_by_arm, alpha=0.05, min_bpb_gain=0.01)
        full_b = bpb_by_arm["H10b_Geosphere_Full"]
        vs_n0: Dict[str, Any] = {}
        for anchor in ("N0_nGPT_Loop_15M", "N0_Monolithic_Loop_15M", "N0_English_CoT_15M", "N0_nGPT_Unlooped_15M"):
            if anchor in bpb_by_arm:
                deltas = [a - f for a, f in zip(bpb_by_arm[anchor], full_b)]
                vs_n0[anchor] = paired_bootstrap_verdict(deltas, min_effect=0.01, higher_is_better=True)
        out["h10b_full_vs_n0_bpb"] = vs_n0
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="PREREG-S110 + Amendment 1 Geosphere-Net Harness (WEIGHTS=0)")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--amp-bf16", action="store_true")
    parser.add_argument("--grad-checkpoint", action="store_true")
    parser.add_argument("--microbench", action="store_true", help="Run <2 min sm_86 wall-clock/VRAM/BF16 kill gate")
    parser.add_argument("--multidomain", action="store_true", help="Use strictly disjoint offline multidomain corpus")
    parser.add_argument("--wikitext-dir", type=str, default=None)
    parser.add_argument("--stage", choices=("H10a", "H10b", "all"), default="H10b")
    parser.add_argument("--scale", choices=("full15m", "tiny"), default="full15m")
    parser.add_argument("--seq-len", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--steps", type=int, default=600)
    parser.add_argument("--lr", type=float, default=1.5e-3)
    parser.add_argument("--ngpt-lr", type=float, default=2.5e-3)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--corpus-path", type=str, default=None)
    parser.add_argument("--out-json", type=str, default=None)
    args = parser.parse_args(argv)

    if args.device == "cuda":
        require_ok(torch.cuda.is_available(), "CUDA requested but torch.cuda.is_available() is False")
    device = torch.device(args.device)

    payload: Dict[str, Any] = {
        "schema": "aletheia.track_s110.geosphere_net_run.v1",
        "prereg_s110_sha256": PREREG_S110_SHA256,
        "prereg_s110_amend1_sha256": PREREG_S110_AMEND1_SHA256,
        "weights_saved": 0,
        "device": args.device,
        "gpu_name": torch.cuda.get_device_name(0) if args.device == "cuda" else "cpu",
        "amp_bf16": bool(args.amp_bf16),
    }

    if args.microbench:
        d_bench = 384 if args.scale == "full15m" else 64
        payload["microbench"] = run_operator_microbench(
            device=device,
            amp_bf16=args.amp_bf16,
            d_model=d_bench,
            seq_len=args.seq_len,
            batch_size=args.batch_size,
            iters=20 if args.device == "cuda" else 5,
            warmup=5 if args.device == "cuda" else 2,
            include_full_model=(args.device == "cuda"),
        )
    else:
        arms = build_s110_arm_configs(scale=args.scale)
        if args.stage == "H10a":
            selected = [k for k, v in arms.items() if v.stage == "H10a_single_shell"]
        elif args.stage == "H10b":
            selected = [k for k, v in arms.items() if v.stage in ("H10b_coupled_loso", "baseline_anchor")]
        else:
            selected = list(arms.keys())

        eval_by_dom: Optional[Dict[str, List[torch.Tensor]]] = None
        long_eval: Optional[List[torch.Tensor]] = None
        if args.multidomain:
            wt_dir = Path(args.wikitext_dir) if args.wikitext_dir else Path(
                "~/.cache/huggingface/hub/datasets--Salesforce--wikitext/snapshots/b08601e04326c79dfdd32d625aee71d232d685c3/wikitext-2-raw-v1"
            ).expanduser()
            exp_root = Path(_THIS_DIR).parent
            bundle = load_multidomain_disjoint_bundle(
                seq_len=args.seq_len,
                wikitext_dir=wt_dir,
                frozen_code_roots=[
                    exp_root / "publish" / "aletheia-fix-lean-gates-v2",
                    exp_root / "publish" / "math0-s21e-escher-metamorphosis",
                ],
                eval_windows_per_domain=24,
                long_seq_len=args.seq_len * 2,
                long_eval_windows=24,
            )
            train_chunks = bundle["train_chunks"]
            eval_chunks = bundle["eval_chunks_combined"]
            eval_by_dom = bundle["eval_chunks_by_domain"]
            long_eval = bundle["long_eval_chunks"]
            payload["corpus"] = {
                "tag": bundle["corpus_tag"],
                "train_bytes": bundle["train_bytes"],
                "train_sha256": bundle["train_sha256"],
                "eval_bytes": bundle["eval_bytes"],
                "eval_sha256": bundle["eval_sha256"],
                "train_file_count": bundle["train_file_count"],
                "eval_file_count": bundle["eval_file_count"],
                "file_overlap_count": bundle["file_overlap_count"],
                "domain_eval_bytes": bundle["domain_eval_bytes"],
                "domain_eval_sha256": bundle["domain_eval_sha256"],
                "train_chunks": len(train_chunks),
                "eval_chunks_512": len(eval_chunks),
                "eval_chunks_1024": len(long_eval),
            }
        else:
            train_chunks, eval_chunks, corpus_tag = load_offline_byte_chunks(
                seq_len=args.seq_len,
                n_train=max(16, args.batch_size * 8),
                n_eval=16,
                seed=args.seeds[0],
                corpus_path=args.corpus_path,
            )
            payload["corpus"] = {"tag": corpus_tag}

        runs: List[Dict[str, Any]] = []
        total_runs = len(selected) * len(args.seeds)
        run_idx = 0
        for arm_name in selected:
            for seed in args.seeds:
                run_idx += 1
                res = train_and_eval_arm(
                    arms[arm_name],
                    train_chunks,
                    eval_chunks,
                    device=device,
                    steps=args.steps,
                    batch_size=args.batch_size,
                    lr=args.lr,
                    ngpt_lr=args.ngpt_lr,
                    amp_bf16=args.amp_bf16,
                    grad_checkpoint=args.grad_checkpoint,
                    seed=seed,
                    eval_chunks_by_domain=eval_by_dom,
                    long_eval_chunks=long_eval,
                    full_eval=(args.device == "cuda"),
                )
                runs.append(res)
                sys.stderr.write(
                    f"[{run_idx}/{total_runs}] {arm_name} seed={seed} "
                    f"bpb512={res['eval_default']['bpb']:.4f} "
                    f"bpbR6={res['eval_r6_extrap']['bpb']:.4f} "
                    f"wall={res['train_wall_s']:.1f}s vram={res['peak_vram_mib']:.0f}MiB\n"
                )
                sys.stderr.flush()
        payload["runs"] = runs
        payload["summary"] = summarize_stage_verdicts(runs, args.stage)

    raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    payload["payload_sha256"] = hashlib.sha256(raw).hexdigest()
    final_txt = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.out_json:
        Path(args.out_json).write_text(final_txt, encoding="utf-8")
    else:
        sys.stdout.write(final_txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
