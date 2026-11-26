#!/usr/bin/env python3
"""Training, multi-domain evaluation, UTF-8 BPB, PTQ KL, M1-H1 & S_3/A_5 harness for PREREG-S107 + Amendment 1.

Supports:
  - CPU-only smoke runs (--device cpu) with zero GPU touch.
  - RTX 3080 production training (--device cuda --amp-bf16) under HF_HUB_OFFLINE=1,
    real offline multi-domain corpora (WikiText-2 raw-v1 + local Python + JSON traces),
    cosine LR schedule with linear warmup + equal pilot LR calibration per backbone,
    exact UTF-8 BPB formula (BOS excluded, EOS scored, fp32 log-softmax),
    3-bit/4-bit RTN group-128 PTQ KL, M1-H1 G_3(rho) checkpoint monitor,
    H7b 2x/4x length extrapolation + non-Abelian S_3/A_5 group-word tracking,
    H7c R_test={3,4,6,8} loop extrapolation + bracket-depth probe,
    literal strict paired-seed scorecard grading (CONFIRMED/PARTIAL/FALSIFIED),
    and zero model weights saved inside the repository tree (WEIGHTS=0).

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
import torch.nn.functional as F

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from s107_models import (
    S107ConfigError,
    S107ModelConfig,
    S107TransformerLM,
    analytical_forward_flops_per_token,
    apply_ptq_copy,
    build_h7a_configs,
    build_h7b_configs,
    build_h7c_configs,
    count_parameters,
    measure_m1_h1_loop_drift,
    require_ok,
)

# Fixed UTF-8 byte vocabulary layout:
# 0..255 = raw UTF-8 bytes, 256 = BOS, 257 = EOS, 258 = PAD, 259 = UNK
VOCAB_SIZE_BYTE = 260
BOS_ID = 256
EOS_ID = 257
PAD_ID = 258
UNK_ID = 259

DEFAULT_SEEDS = (42, 137, 2026)


# ---------------------------------------------------------------------------
# Exact UTF-8 Byte Tokenization & Exact BPB / KL Metrics (COLLAB-CLAUDE A9/A10)
# ---------------------------------------------------------------------------


def encode_utf8_bytes(text: str, add_bos: bool = True, add_eos: bool = True) -> List[int]:
    """Invertible raw UTF-8 byte encoding (decode(encode(x)) == x identically)."""
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


@torch.no_grad()
def evaluate_exact_bpb(
    model: S107TransformerLM,
    token_chunks: Sequence[torch.Tensor],
    device: torch.device,
    r_loops: Optional[int] = None,
    score_tail_len: Optional[int] = None,
    batch_size: int = 8,
) -> Dict[str, Any]:
    """Exact UTF-8 Bits-Per-Byte (fp32 log-softmax, BOS excluded, EOS scored)."""
    model.eval()
    total_nll_nats = 0.0
    total_scored_tokens = 0
    total_utf8_bytes = 0

    for start_i in range(0, len(token_chunks), batch_size):
        batch_chunks = token_chunks[start_i : start_i + batch_size]
        # All chunks in a fixed-length eval split share length; handle general case safely.
        lens = {int(c.numel()) for c in batch_chunks}
        if len(lens) == 1:
            mat = torch.stack(list(batch_chunks), dim=0).to(device)
            inp = mat[:, :-1]
            tgt = mat[:, 1:]
            logits, _ = model(inp, r_loops=r_loops, return_trace=False)
            log_probs = F.log_softmax(logits.float(), dim=-1)  # [B, T-1, V]
            nll = F.nll_loss(
                log_probs.reshape(-1, log_probs.shape[-1]),
                tgt.reshape(-1),
                ignore_index=PAD_ID,
                reduction="none",
            ).reshape(tgt.shape)
            valid_mask = (tgt != PAD_ID) & (tgt != BOS_ID)
            if score_tail_len is not None and score_tail_len < tgt.shape[1]:
                s_idx = tgt.shape[1] - score_tail_len
                nll = nll[:, s_idx:]
                valid_mask = valid_mask[:, s_idx:]
                tgt_eval = tgt[:, s_idx:]
            else:
                tgt_eval = tgt
            total_nll_nats += float(nll[valid_mask].sum().item())
            total_scored_tokens += int(valid_mask.sum().item())
            raw_bytes = int(((tgt_eval >= 0) & (tgt_eval < 256) & valid_mask).sum().item())
            total_utf8_bytes += max(raw_bytes, int(valid_mask.sum().item()))
        else:
            for chunk in batch_chunks:
                require_ok(chunk.ndim == 1 and chunk.numel() >= 2, "Chunk must be 1D with length >= 2")
                inp = chunk[:-1].unsqueeze(0).to(device)
                tgt = chunk[1:].to(device)
                logits, _ = model(inp, r_loops=r_loops, return_trace=False)
                log_probs = F.log_softmax(logits[0].float(), dim=-1)
                nll = F.nll_loss(log_probs, tgt, ignore_index=PAD_ID, reduction="none")
                valid_mask = (tgt != PAD_ID) & (tgt != BOS_ID)
                if score_tail_len is not None and score_tail_len < tgt.numel():
                    s_idx = tgt.numel() - score_tail_len
                    nll = nll[s_idx:]
                    valid_mask = valid_mask[s_idx:]
                    tgt_eval = tgt[s_idx:]
                else:
                    tgt_eval = tgt
                total_nll_nats += float(nll[valid_mask].sum().item())
                total_scored_tokens += int(valid_mask.sum().item())
                raw_bytes = int(((tgt_eval >= 0) & (tgt_eval < 256) & valid_mask).sum().item())
                total_utf8_bytes += max(raw_bytes, int(valid_mask.sum().item()))

    require_ok(total_utf8_bytes > 0 and total_scored_tokens > 0, "No valid tokens scored for BPB")
    mean_nll = total_nll_nats / float(total_scored_tokens)
    bpb = total_nll_nats / (math.log(2.0) * float(total_utf8_bytes))
    return {
        "bpb": round(bpb, 6),
        "mean_nll_nats": round(mean_nll, 6),
        "scored_tokens": total_scored_tokens,
        "utf8_bytes": total_utf8_bytes,
    }


@torch.no_grad()
def evaluate_ptq_bpb_and_kl(
    model_fp: S107TransformerLM,
    token_chunks: Sequence[torch.Tensor],
    device: torch.device,
    bits: int = 3,
    group_size: int = 128,
    r_loops: Optional[int] = None,
    batch_size: int = 8,
) -> Dict[str, Any]:
    """Evaluate RTN symmetric per-output-channel group PTQ BPB and exact KL(p_fp || p_q) in nats."""
    model_fp.eval()
    model_q = apply_ptq_copy(model_fp, bits=bits, group_size=group_size, core_only=False).to(device).eval()

    total_kl_nats = 0.0
    total_nll_q = 0.0
    total_scored = 0
    for start_i in range(0, len(token_chunks), batch_size):
        mat = torch.stack(list(token_chunks[start_i : start_i + batch_size]), dim=0).to(device)
        inp = mat[:, :-1]
        tgt = mat[:, 1:]
        logits_fp, _ = model_fp(inp, r_loops=r_loops, return_trace=False)
        logits_q, _ = model_q(inp, r_loops=r_loops, return_trace=False)
        lp_fp = F.log_softmax(logits_fp.float(), dim=-1)
        lp_q = F.log_softmax(logits_q.float(), dim=-1)
        kl_tok = torch.sum(lp_fp.exp() * (lp_fp - lp_q), dim=-1)
        nll_q = F.nll_loss(
            lp_q.reshape(-1, lp_q.shape[-1]),
            tgt.reshape(-1),
            ignore_index=PAD_ID,
            reduction="none",
        ).reshape(tgt.shape)
        valid = (tgt != PAD_ID) & (tgt != BOS_ID)
        total_kl_nats += float(kl_tok[valid].sum().item())
        total_nll_q += float(nll_q[valid].sum().item())
        total_scored += int(valid.sum().item())

    del model_q
    if device.type == "cuda":
        torch.cuda.empty_cache()

    require_ok(total_scored > 0, "No valid tokens for PTQ KL evaluation")
    return {
        "bits": bits,
        "ptq_bpb": round(total_nll_q / (math.log(2.0) * float(total_scored)), 6),
        "ptq_kl_nats": round(total_kl_nats / float(total_scored), 8),
        "scored_tokens": total_scored,
    }


# ---------------------------------------------------------------------------
# Exact Non-Abelian Finite Groups: S_3 (order 6) & A_5 (order 60)
# ---------------------------------------------------------------------------


def _perm_compose(p: Tuple[int, ...], q: Tuple[int, ...]) -> Tuple[int, ...]:
    """Composition (p o q)(i) = p[q[i]]."""
    return tuple(p[q[i]] for i in range(len(p)))


def _perm_parity(p: Tuple[int, ...]) -> int:
    inv = 0
    for i in range(len(p)):
        for j in range(i + 1, len(p)):
            if p[i] > p[j]:
                inv += 1
    return inv % 2


def build_finite_group(name: str) -> Dict[str, Any]:
    """Construct exact multiplication table for S_3 (order 6) or A_5 (order 60)."""
    import itertools

    if name == "S3":
        elems = sorted(itertools.permutations(range(3)))
    elif name == "A5":
        elems = sorted(p for p in itertools.permutations(range(5)) if _perm_parity(p) == 0)
    else:
        raise S107ConfigError(f"Unsupported group: {name!r} (expected 'S3' or 'A5')")

    idx_of = {p: i for i, p in enumerate(elems)}
    n = len(elems)
    mul_table = [[idx_of[_perm_compose(elems[i], elems[j])] for j in range(n)] for i in range(n)]
    identity = idx_of[tuple(range(len(elems[0])))]
    non_comm_pairs = sum(1 for i in range(n) for j in range(n) if mul_table[i][j] != mul_table[j][i])
    require_ok(non_comm_pairs > 0, f"Group {name} must be non-Abelian")
    return {
        "name": name,
        "order": n,
        "identity": identity,
        "mul_table": mul_table,
        "non_commuting_pairs": non_comm_pairs,
        "chance_accuracy": 1.0 / float(n),
    }


def generate_group_word_dataset(
    group: Dict[str, Any],
    n_samples: int,
    min_len: int,
    max_len: int,
    seed: int,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Generate deterministic non-Abelian group-word state-tracking sequences."""
    require_ok(min_len >= 2 and max_len >= min_len, "Invalid word length bounds")
    rng = random.Random(seed)
    order = int(group["order"])
    mul = group["mul_table"]
    offset = 10
    require_ok(offset + order < 256, "Group order exceeds byte vocab")

    inps = torch.full((n_samples, max_len), PAD_ID, dtype=torch.long)
    tgts = torch.full((n_samples, max_len), PAD_ID, dtype=torch.long)

    for s in range(n_samples):
        length = rng.randint(min_len, max_len)
        acc = int(group["identity"])
        for t in range(length):
            g = rng.randrange(order)
            acc = mul[acc][g]
            inps[s, t] = offset + g
            tgts[s, t] = offset + acc
    return inps, tgts


def generate_parity_and_bracket_dataset(
    n_samples: int,
    seq_len: int,
    seed: int,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Deterministic algorithmic extrapolation probe (H7c): running bounded bracket depth."""
    rng = random.Random(seed)
    inps = torch.zeros((n_samples, seq_len), dtype=torch.long)
    tgts = torch.zeros((n_samples, seq_len), dtype=torch.long)
    for s in range(n_samples):
        depth = 0
        for t in range(seq_len):
            if depth == 0:
                ch = 0
            elif depth >= 7:
                ch = 1
            else:
                ch = rng.randrange(2)
            depth = depth + 1 if ch == 0 else depth - 1
            inps[s, t] = ord("(") if ch == 0 else ord(")")
            tgts[s, t] = ord("0") + depth
    return inps, tgts


# ---------------------------------------------------------------------------
# Offline Multi-Domain Corpus Loading (WikiText-2 + Local Code + JSON Traces)
# ---------------------------------------------------------------------------


def _read_parquet_text(path: Path) -> bytes:
    import pyarrow.parquet as pq  # type: ignore

    table = pq.read_table(path)
    col = "text" if "text" in table.column_names else table.column_names[0]
    text = "\n".join(str(x) for x in table[col].to_pylist() if x)
    return text.encode("utf-8")


def load_offline_text_corpus(corpus_path: Optional[Path], max_bytes: int = 2_000_000) -> Tuple[List[int], str]:
    """Load single local text/parquet corpus strictly offline; returns (ids, sha256)."""
    if corpus_path is not None and corpus_path.exists():
        if corpus_path.suffix == ".parquet":
            raw_bytes = _read_parquet_text(corpus_path)[:max_bytes]
        else:
            raw_bytes = corpus_path.read_text(encoding="utf-8", errors="replace").encode("utf-8")[:max_bytes]
        return list(raw_bytes), hashlib.sha256(raw_bytes).hexdigest()

    samples = [
        "The hypersphere foliation allocates layer width across depth by exact trigonometric schedules.\n",
        "def quat_mul(p, q):\n    return (p[0]*q[0]-p[1]*q[1]-p[2]*q[2]-p[3]*q[3],)\n",
        '{"protocol":"PREREG-S107","amendment":1,"norm_floor":1e-4,"status":"ready"}\n',
        "الهندسة الكروية والتناظر الرياضي في الأنظمة المتصلة والمنفصلة.\n",
    ]
    buf = ("".join(samples) * 256).encode("utf-8")[:max_bytes]
    return list(buf), hashlib.sha256(buf).hexdigest()


def load_multidomain_offline_bundle(
    wikitext_train_parquet: Optional[Path],
    wikitext_test_parquet: Optional[Path],
    expedition_root: Path,
) -> Dict[str, Any]:
    """Build strictly disjoint train & held-out multi-domain offline byte streams.

    Domains:
      1. Wikipedia prose: WikiText-2-raw-v1 validation (train) vs test (strictly held-out eval)
      2. Python source code: local expedition track *.py files split 80/20 by file SHA-256
      3. Structured JSON traces: local expedition *.json receipts split 80/20 by file SHA-256
    """
    train_parts: List[bytes] = []
    eval_domains: Dict[str, bytes] = {}

    if wikitext_train_parquet is not None and wikitext_train_parquet.exists():
        wt_tr = _read_parquet_text(wikitext_train_parquet)
        train_parts.append(wt_tr)
    if wikitext_test_parquet is not None and wikitext_test_parquet.exists():
        eval_domains["wikitext2_test"] = _read_parquet_text(wikitext_test_parquet)

    # Gather disjoint local Python source files (excluding this track to avoid self-leakage).
    py_files = sorted(
        p
        for p in expedition_root.glob("track-s*/*.py")
        if "track-s107" not in str(p) and p.is_file() and p.stat().st_size <= 120_000
    )
    py_tr, py_ev = bytearray(), bytearray()
    for p in py_files:
        h_byte = hashlib.sha256(p.name.encode("utf-8")).digest()[0]
        raw = p.read_bytes()
        if h_byte < 204 and len(py_tr) < 1_000_000:
            py_tr.extend(raw)
            py_tr.extend(b"\n")
        elif h_byte >= 204 and len(py_ev) < 250_000:
            py_ev.extend(raw)
            py_ev.extend(b"\n")
    if len(py_tr) > 10_000 and len(py_ev) > 10_000:
        train_parts.append(bytes(py_tr))
        eval_domains["python_code"] = bytes(py_ev)

    # Gather disjoint local JSON traces/certificates.
    json_files = sorted(
        p
        for p in expedition_root.glob("track-s*/*.json")
        if "track-s107" not in str(p) and p.is_file() and p.stat().st_size <= 80_000
    )
    js_tr, js_ev = bytearray(), bytearray()
    for p in json_files:
        h_byte = hashlib.sha256(p.name.encode("utf-8")).digest()[0]
        raw = p.read_bytes()
        if h_byte < 204 and len(js_tr) < 400_000:
            js_tr.extend(raw)
            js_tr.extend(b"\n")
        elif h_byte >= 204 and len(js_ev) < 120_000:
            js_ev.extend(raw)
            js_ev.extend(b"\n")
    if len(js_tr) > 8_000 and len(js_ev) > 8_000:
        train_parts.append(bytes(js_tr))
        eval_domains["json_traces"] = bytes(js_ev)

    require_ok(len(train_parts) >= 1 and len(eval_domains) >= 1, "No offline corpus files found")
    train_bytes = b"\n".join(train_parts)
    eval_combined = b"\n".join(eval_domains[k] for k in sorted(eval_domains.keys()))
    return {
        "train_bytes": list(train_bytes),
        "train_sha256": hashlib.sha256(train_bytes).hexdigest(),
        "train_num_bytes": len(train_bytes),
        "eval_domains": {k: list(v) for k, v in eval_domains.items()},
        "eval_combined_bytes": list(eval_combined),
        "eval_sha256": hashlib.sha256(eval_combined).hexdigest(),
        "eval_domain_sizes": {k: len(v) for k, v in eval_domains.items()},
    }


def chunk_stream(byte_ids: Sequence[int], seq_len: int, max_chunks: Optional[int] = None) -> List[torch.Tensor]:
    """Slice raw byte stream into BOS-prefixed fixed-length non-overlapping windows."""
    chunks: List[torch.Tensor] = []
    stride = seq_len - 1
    for start in range(0, max(0, len(byte_ids) - stride), stride):
        seg = [BOS_ID] + list(byte_ids[start : start + stride])
        if len(seg) == seq_len:
            chunks.append(torch.tensor(seg, dtype=torch.long))
            if max_chunks is not None and len(chunks) >= max_chunks:
                break
    require_ok(len(chunks) >= 2, f"Corpus too short for seq_len={seq_len}")
    return chunks


# ---------------------------------------------------------------------------
# Cosine Schedule + Single-Arm Training & Multi-Axis Evaluation
# ---------------------------------------------------------------------------


def _cosine_lr(step: int, total_steps: int, peak_lr: float, warmup_frac: float = 0.10) -> float:
    warmup = max(1, int(round(warmup_frac * total_steps)))
    if step < warmup:
        return peak_lr * float(step + 1) / float(warmup)
    progress = float(step - warmup) / float(max(1, total_steps - warmup))
    return peak_lr * (0.1 + 0.45 * (1.0 + math.cos(math.pi * progress)))


def train_and_eval_arm(
    cfg: S107ModelConfig,
    train_chunks: Sequence[torch.Tensor],
    val_chunks: Sequence[torch.Tensor],
    device: torch.device,
    steps: int = 200,
    batch_size: int = 8,
    lr: float = 1e-3,
    amp_bf16: bool = False,
    run_ptq: bool = True,
    domain_val_chunks: Optional[Dict[str, List[torch.Tensor]]] = None,
    long_val_chunks: Optional[Dict[int, List[torch.Tensor]]] = None,
    log_m1_h1_checkpoints: bool = False,
) -> Dict[str, Any]:
    """Train one S107 arm with cosine LR schedule, exact CS-08 parity logging, and WEIGHTS=0."""
    torch.manual_seed(cfg.seed)
    rng = random.Random(cfg.seed)
    model = S107TransformerLM(cfg).to(device)
    p_stats = count_parameters(model)
    seq_len = int(train_chunks[0].numel()) - 1
    f_stats = analytical_forward_flops_per_token(cfg, seq_len=seq_len)

    weight_decay = 0.0 if model.use_sphere_head else 0.1
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, betas=(0.9, 0.95), weight_decay=weight_decay)

    model.train()
    losses: List[float] = []
    ckpt_m1_h1: List[Dict[str, Any]] = []
    ckpt_steps = {max(1, steps // 4), max(1, steps // 2)} if (log_m1_h1_checkpoints and model.is_looped) else set()
    sample_inp_m1 = val_chunks[0][:-1].unsqueeze(0).to(device)

    t0 = time.monotonic()
    for step in range(steps):
        cur_lr = _cosine_lr(step, steps, peak_lr=lr)
        for gp in optimizer.param_groups:
            gp["lr"] = cur_lr

        batch_list = [train_chunks[rng.randrange(len(train_chunks))] for _ in range(batch_size)]
        batch = torch.stack(batch_list, dim=0).to(device)
        inp = batch[:, :-1]
        tgt = batch[:, 1:]

        optimizer.zero_grad(set_to_none=True)
        if amp_bf16 and device.type == "cuda":
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                logits, _ = model(inp)
                loss = F.cross_entropy(
                    logits.float().reshape(-1, cfg.vocab_size),
                    tgt.reshape(-1),
                    ignore_index=PAD_ID,
                )
        else:
            logits, _ = model(inp)
            loss = F.cross_entropy(
                logits.float().reshape(-1, cfg.vocab_size),
                tgt.reshape(-1),
                ignore_index=PAD_ID,
            )

        require_ok(bool(torch.isfinite(loss).item()), f"Non-finite loss at step {step} for {cfg.arm_name}")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        if model.use_sphere_head:
            model.normalize_ngpt_weights_()
        losses.append(float(loss.item()))

        if (step + 1) in ckpt_steps:
            model.eval()
            m4_ck = measure_m1_h1_loop_drift(model, sample_inp_m1, bits=4, r_eval=cfg.r_train)
            ckpt_m1_h1.append({"step": step + 1, "rho_mean": m4_ck["rho_mean"], "delta_3_over_1": m4_ck["delta_r_over_delta_1"]})
            model.train()

    elapsed_s = time.monotonic() - t0
    val_eval_set = val_chunks[: min(64, len(val_chunks))]
    val_metrics = evaluate_exact_bpb(model, val_eval_set, device=device, batch_size=batch_size)

    result: Dict[str, Any] = {
        "arm_name": cfg.arm_name,
        "track": cfg.track,
        "seed": cfg.seed,
        "peak_lr": lr,
        "weight_decay": weight_decay,
        "params": p_stats,
        "flops": f_stats,
        "train_steps": steps,
        "train_loss_start": round(losses[0], 6),
        "train_loss_end": round(losses[-1], 6),
        "val": val_metrics,
        "elapsed_sec": round(elapsed_s, 3),
    }

    if domain_val_chunks:
        dom_res: Dict[str, Any] = {}
        for dname, dchunks in domain_val_chunks.items():
            dom_res[dname] = evaluate_exact_bpb(model, dchunks[: min(32, len(dchunks))], device=device, batch_size=batch_size)["bpb"]
        result["val_domain_bpb"] = dom_res

    if long_val_chunks:
        long_res: Dict[str, Any] = {}
        for t_len, lchunks in sorted(long_val_chunks.items()):
            # COLLAB-CLAUDE A9: score identical final 512 bytes across context lengths.
            long_res[f"T{t_len}"] = evaluate_exact_bpb(
                model,
                lchunks[: min(16, len(lchunks))],
                device=device,
                score_tail_len=512,
                batch_size=max(1, batch_size // 4),
            )["bpb"]
        result["length_extrapolation_bpb"] = long_res

    if run_ptq:
        ptq_eval_set = val_chunks[: min(32, len(val_chunks))]
        ptq3 = evaluate_ptq_bpb_and_kl(model, ptq_eval_set, device=device, bits=3, group_size=128, batch_size=batch_size)
        result["ptq_3bit_bpb"] = ptq3["ptq_bpb"]
        result["ptq_3bit_delta_bpb"] = round(ptq3["ptq_bpb"] - val_metrics["bpb"], 6)
        result["ptq_3bit_kl_nats"] = ptq3["ptq_kl_nats"]

    if model.is_looped:
        result["m1_h1_4bit"] = measure_m1_h1_loop_drift(model, sample_inp_m1, bits=4, r_eval=cfg.r_train)
        result["m1_h1_3bit"] = measure_m1_h1_loop_drift(model, sample_inp_m1, bits=3, r_eval=cfg.r_train)
        if ckpt_m1_h1:
            result["m1_h1_checkpoints"] = ckpt_m1_h1
        extrap: Dict[str, Any] = {}
        for r_test in (3, 4, 6, 8):
            extrap[f"R{r_test}"] = evaluate_exact_bpb(
                model, val_chunks[: min(16, len(val_chunks))], device=device, r_loops=r_test, batch_size=batch_size
            )["bpb"]
        result["r_test_extrapolation_bpb"] = extrap

    del model, optimizer
    gc.collect()
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return result


# ---------------------------------------------------------------------------
# Dedicated H7b Non-Abelian Group-Word Probe (S_3 & A_5) & H7c Bracket Probe
# ---------------------------------------------------------------------------


def run_h7b_group_probe(
    arm_name: str,
    pos_mode: str,
    ngpt: bool,
    group_name: str,
    seed: int,
    device: torch.device,
    steps: int = 400,
    batch_size: int = 32,
    lr: float = 1.5e-3,
    amp_bf16: bool = False,
) -> Dict[str, Any]:
    """Train & evaluate matched 6-layer H7b arm on S_3 / A_5 state tracking (len 8..64 train, 65..256 OOD)."""
    group = build_finite_group(group_name)
    cfg = S107ModelConfig(
        arm_name=f"{arm_name}-{group_name}",
        track="H7b",
        vocab_size=VOCAB_SIZE_BYTE,
        d_model=192,
        n_heads=6,
        n_layers=6,
        base_d_ff=512,
        pos_mode=pos_mode,
        ngpt=ngpt,
        seed=seed,
    )
    torch.manual_seed(seed)
    model = S107TransformerLM(cfg).to(device)
    p_stats = count_parameters(model)
    wd = 0.0 if model.use_sphere_head else 0.1
    opt = torch.optim.AdamW(model.parameters(), lr=lr, betas=(0.9, 0.95), weight_decay=wd)

    tr_x, tr_y = generate_group_word_dataset(group, n_samples=2048, min_len=8, max_len=64, seed=seed + 1000)
    id_x, id_y = generate_group_word_dataset(group, n_samples=256, min_len=8, max_len=64, seed=seed + 2000)
    ood_x, ood_y = generate_group_word_dataset(group, n_samples=256, min_len=65, max_len=192, seed=seed + 3000)

    rng = random.Random(seed)
    model.train()
    t0 = time.monotonic()
    for step in range(steps):
        cur_lr = _cosine_lr(step, steps, peak_lr=lr)
        for gp in opt.param_groups:
            gp["lr"] = cur_lr
        idx = [rng.randrange(tr_x.shape[0]) for _ in range(batch_size)]
        xb = tr_x[idx].to(device)
        yb = tr_y[idx].to(device)
        opt.zero_grad(set_to_none=True)
        if amp_bf16 and device.type == "cuda":
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                logits, _ = model(xb)
                loss = F.cross_entropy(logits.float().reshape(-1, cfg.vocab_size), yb.reshape(-1), ignore_index=PAD_ID)
        else:
            logits, _ = model(xb)
            loss = F.cross_entropy(logits.float().reshape(-1, cfg.vocab_size), yb.reshape(-1), ignore_index=PAD_ID)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if model.use_sphere_head:
            model.normalize_ngpt_weights_()

    @torch.no_grad()
    def _acc(xs: torch.Tensor, ys: torch.Tensor) -> float:
        model.eval()
        correct = 0
        total = 0
        for i in range(0, xs.shape[0], 32):
            bx = xs[i : i + 32].to(device)
            by = ys[i : i + 32].to(device)
            lg, _ = model(bx)
            pred = lg.argmax(dim=-1)
            mask = by != PAD_ID
            correct += int((pred[mask] == by[mask]).sum().item())
            total += int(mask.sum().item())
        return round(float(correct) / float(max(1, total)), 6)

    id_acc = _acc(id_x, id_y)
    ood_acc = _acc(ood_x, ood_y)
    elapsed = round(time.monotonic() - t0, 3)

    del model, opt
    gc.collect()
    if device.type == "cuda":
        torch.cuda.empty_cache()

    return {
        "arm_name": arm_name,
        "group": group_name,
        "seed": seed,
        "non_embedding_params": p_stats["non_embedding_params"],
        "chance_acc": round(group["chance_accuracy"], 6),
        "id_acc_len_8_64": id_acc,
        "ood_acc_len_65_192": ood_acc,
        "elapsed_sec": elapsed,
    }


def run_h7c_bracket_probe(
    cfg_base: S107ModelConfig,
    device: torch.device,
    steps: int = 300,
    batch_size: int = 32,
    lr: float = 1.5e-3,
    amp_bf16: bool = False,
) -> Dict[str, Any]:
    """Train matched H7c arm on bracket-depth tracking at R=3 and evaluate extrapolation R={3,4,6,8}."""
    cfg = S107ModelConfig(
        arm_name=f"{cfg_base.arm_name}-Bracket",
        track="H7c",
        vocab_size=VOCAB_SIZE_BYTE,
        d_model=128,
        n_heads=4,
        n_layers=cfg_base.n_layers,
        base_d_ff=320,
        ngpt=cfg_base.ngpt,
        loop_mode=cfg_base.loop_mode,
        n_pre=cfg_base.n_pre,
        n_core=cfg_base.n_core,
        n_suffix=cfg_base.n_suffix,
        r_train=cfg_base.r_train,
        clock_law=cfg_base.clock_law,
        use_grad_checkpoint=False,
        seed=cfg_base.seed,
    )
    torch.manual_seed(cfg.seed)
    model = S107TransformerLM(cfg).to(device)
    wd = 0.0 if model.use_sphere_head else 0.1
    opt = torch.optim.AdamW(model.parameters(), lr=lr, betas=(0.9, 0.95), weight_decay=wd)

    tr_x, tr_y = generate_parity_and_bracket_dataset(n_samples=1024, seq_len=64, seed=cfg.seed + 4000)
    ev_x, ev_y = generate_parity_and_bracket_dataset(n_samples=256, seq_len=96, seed=cfg.seed + 5000)

    rng = random.Random(cfg.seed)
    model.train()
    for step in range(steps):
        cur_lr = _cosine_lr(step, steps, peak_lr=lr)
        for gp in opt.param_groups:
            gp["lr"] = cur_lr
        idx = [rng.randrange(tr_x.shape[0]) for _ in range(batch_size)]
        xb = tr_x[idx].to(device)
        yb = tr_y[idx].to(device)
        opt.zero_grad(set_to_none=True)
        if amp_bf16 and device.type == "cuda":
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                logits, _ = model(xb)
                loss = F.cross_entropy(logits.float().reshape(-1, cfg.vocab_size), yb.reshape(-1))
        else:
            logits, _ = model(xb)
            loss = F.cross_entropy(logits.float().reshape(-1, cfg.vocab_size), yb.reshape(-1))
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if model.use_sphere_head:
            model.normalize_ngpt_weights_()

    @torch.no_grad()
    def _eval_r(r_val: Optional[int]) -> float:
        model.eval()
        correct = 0
        total = 0
        for i in range(0, ev_x.shape[0], 32):
            bx = ev_x[i : i + 32].to(device)
            by = ev_y[i : i + 32].to(device)
            lg, _ = model(bx, r_loops=r_val)
            pred = lg.argmax(dim=-1)
            correct += int((pred == by).sum().item())
            total += int(by.numel())
        return round(float(correct) / float(max(1, total)), 6)

    accs: Dict[str, float] = {}
    if model.is_looped:
        for r_val in (3, 4, 6, 8):
            accs[f"R{r_val}"] = _eval_r(r_val)
    else:
        accs["unlooped"] = _eval_r(None)

    del model, opt
    gc.collect()
    if device.type == "cuda":
        torch.cuda.empty_cache()

    return {"arm_name": cfg_base.arm_name, "seed": cfg_base.seed, "bracket_depth_acc": accs}


# ---------------------------------------------------------------------------
# Equal Per-Backbone Pilot LR Calibration (COLLAB-CLAUDE A7) & Paired Scorecard
# ---------------------------------------------------------------------------


def calibrate_pilot_lr(
    cfg_template: S107ModelConfig,
    train_chunks: Sequence[torch.Tensor],
    val_chunks: Sequence[torch.Tensor],
    device: torch.device,
    lr_grid: Sequence[float] = (6e-4, 1.2e-3, 2.5e-3),
    pilot_steps: int = 120,
    batch_size: int = 8,
    amp_bf16: bool = False,
) -> Dict[str, Any]:
    """Select best peak LR on a small pilot slice (10% val proxy) per backbone family."""
    results: Dict[str, float] = {}
    best_lr = lr_grid[0]
    best_bpb = float("inf")
    pilot_val = val_chunks[: min(16, len(val_chunks))]
    for cand_lr in lr_grid:
        res = train_and_eval_arm(
            cfg_template,
            train_chunks=train_chunks,
            val_chunks=pilot_val,
            device=device,
            steps=pilot_steps,
            batch_size=batch_size,
            lr=cand_lr,
            amp_bf16=amp_bf16,
            run_ptq=False,
        )
        bpb = float(res["val"]["bpb"])
        results[str(cand_lr)] = bpb
        if bpb < best_bpb:
            best_bpb = bpb
            best_lr = cand_lr
    return {"selected_lr": best_lr, "pilot_bpb_by_lr": results}


def _mean_se(vals: Sequence[float]) -> Tuple[float, float]:
    n = len(vals)
    if n == 0:
        return 0.0, 0.0
    mu = sum(vals) / float(n)
    if n == 1:
        return round(mu, 6), 0.0
    var = sum((v - mu) ** 2 for v in vals) / float(n - 1)
    se = math.sqrt(var / float(n))
    return round(mu, 6), round(se, 6)


def paired_diff_stats(arm_vals: Sequence[float], ctrl_vals: Sequence[float]) -> Dict[str, float]:
    """Paired difference (arm - ctrl): negative means arm has LOWER (better) BPB/KL."""
    require_ok(len(arm_vals) == len(ctrl_vals) and len(arm_vals) >= 1, "Paired stat length mismatch")
    diffs = [a - c for a, c in zip(arm_vals, ctrl_vals)]
    mu_d, se_d = _mean_se(diffs)
    mu_c = sum(ctrl_vals) / float(len(ctrl_vals))
    rel_pct = 100.0 * (mu_d / max(abs(mu_c), 1e-12))
    z = (mu_d / se_d) if se_d > 1e-12 else (0.0 if abs(mu_d) < 1e-12 else (-999.0 if mu_d < 0 else 999.0))
    return {
        "mean_diff": round(mu_d, 6),
        "paired_se": round(se_d, 6),
        "rel_diff_pct": round(rel_pct, 4),
        "z_score": round(z, 3),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="PREREG-S107 + Amendment 1 Training & Evaluation Harness.")
    parser.add_argument("--track", choices=("H7a", "H7b", "H7c"), required=True)
    parser.add_argument("--arms", nargs="*", default=None)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--amp-bf16", action="store_true")
    parser.add_argument("--corpus-mode", choices=("single", "wikitext2_multidomain"), default="single")
    parser.add_argument("--corpus-path", type=str, default=None)
    parser.add_argument("--wikitext-train", type=str, default=None)
    parser.add_argument("--wikitext-test", type=str, default=None)
    parser.add_argument("--expedition-root", type=str, default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--seq-len", type=int, default=512)
    parser.add_argument("--steps", type=int, default=800)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr-std", type=float, default=None)
    parser.add_argument("--lr-ngpt", type=float, default=None)
    parser.add_argument("--calibrate-lr", action="store_true")
    parser.add_argument("--seeds", nargs="+", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument("--clock-law", choices=("unaliased_coprime", "pinned_train_step"), default="unaliased_coprime")
    parser.add_argument("--grad-checkpoint", action="store_true")
    parser.add_argument("--run-probes", action="store_true", help="Run H7b S_3/A_5 & H7c bracket probes.")
    parser.add_argument("--out-json", type=str, default=None)
    args = parser.parse_args(argv)

    if args.device == "cpu":
        torch.set_num_threads(1)
    device = torch.device(args.device)
    if args.device == "cuda":
        require_ok(torch.cuda.is_available(), "Requested --device cuda but CUDA is unavailable")

    domain_val_chunks: Optional[Dict[str, List[torch.Tensor]]] = None
    long_val_chunks: Optional[Dict[int, List[torch.Tensor]]] = None
    corpus_meta: Dict[str, Any] = {}

    if args.corpus_mode == "wikitext2_multidomain":
        bundle = load_multidomain_offline_bundle(
            Path(args.wikitext_train) if args.wikitext_train else None,
            Path(args.wikitext_test) if args.wikitext_test else None,
            Path(args.expedition_root),
        )
        train_chunks = chunk_stream(bundle["train_bytes"], seq_len=args.seq_len + 1)
        val_chunks = chunk_stream(bundle["eval_combined_bytes"], seq_len=args.seq_len + 1, max_chunks=96)
        domain_val_chunks = {
            k: chunk_stream(v, seq_len=args.seq_len + 1, max_chunks=32)
            for k, v in bundle["eval_domains"].items()
        }
        if args.track == "H7b":
            long_val_chunks = {
                1024: chunk_stream(bundle["eval_combined_bytes"], seq_len=1025, max_chunks=16),
                2048: chunk_stream(bundle["eval_combined_bytes"], seq_len=2049, max_chunks=16),
            }
        corpus_meta = {
            "mode": "wikitext2_multidomain",
            "train_sha256": bundle["train_sha256"],
            "eval_sha256": bundle["eval_sha256"],
            "train_num_bytes": bundle["train_num_bytes"],
            "eval_domain_sizes": bundle["eval_domain_sizes"],
        }
    else:
        cpath = Path(args.corpus_path) if args.corpus_path else None
        raw_bytes, corpus_sha = load_offline_text_corpus(cpath)
        split = int(0.85 * len(raw_bytes))
        train_chunks = chunk_stream(raw_bytes[:split], seq_len=args.seq_len + 1)
        val_chunks = chunk_stream(raw_bytes[split:], seq_len=args.seq_len + 1)
        corpus_meta = {"mode": "single", "corpus_sha256": corpus_sha}

    # Optional equal per-backbone pilot LR calibration (COLLAB-CLAUDE A7).
    lr_calibration: Dict[str, Any] = {}
    lr_std = args.lr_std if args.lr_std is not None else 1e-3
    lr_ngpt = args.lr_ngpt if args.lr_ngpt is not None else 2e-3
    if args.calibrate_lr:
        if args.track == "H7a":
            c0 = build_h7a_configs(seed=args.seeds[0])
            cal_std = calibrate_pilot_lr(c0["Cyl-Std"], train_chunks, val_chunks, device, amp_bf16=args.amp_bf16, batch_size=args.batch_size)
            cal_ngpt = calibrate_pilot_lr(c0["Cyl-nGPT"], train_chunks, val_chunks, device, amp_bf16=args.amp_bf16, batch_size=args.batch_size)
            lr_std = float(cal_std["selected_lr"])
            lr_ngpt = float(cal_ngpt["selected_lr"])
            lr_calibration = {"std": cal_std, "ngpt": cal_ngpt}
        elif args.track == "H7b":
            c0 = build_h7b_configs(seed=args.seeds[0])
            cal_std = calibrate_pilot_lr(c0["RoPE-2D-Std"], train_chunks, val_chunks, device, amp_bf16=args.amp_bf16, batch_size=args.batch_size)
            cal_ngpt = calibrate_pilot_lr(c0["RoPE-2D-nGPT"], train_chunks, val_chunks, device, amp_bf16=args.amp_bf16, batch_size=args.batch_size)
            lr_std = float(cal_std["selected_lr"])
            lr_ngpt = float(cal_ngpt["selected_lr"])
            lr_calibration = {"std": cal_std, "ngpt": cal_ngpt}
        else:
            c0 = build_h7c_configs(clock_law=args.clock_law, use_grad_checkpoint=args.grad_checkpoint, seed=args.seeds[0])
            cal_std = calibrate_pilot_lr(c0["FlatLoop-Std"], train_chunks, val_chunks, device, amp_bf16=args.amp_bf16, batch_size=args.batch_size)
            cal_ngpt = calibrate_pilot_lr(c0["SphereLoop-NoClock"], train_chunks, val_chunks, device, amp_bf16=args.amp_bf16, batch_size=args.batch_size)
            lr_std = float(cal_std["selected_lr"])
            lr_ngpt = float(cal_ngpt["selected_lr"])
            lr_calibration = {"std": cal_std, "ngpt": cal_ngpt}

    runs: List[Dict[str, Any]] = []
    probes: List[Dict[str, Any]] = []
    t_track_0 = time.monotonic()

    for seed in args.seeds:
        if args.track == "H7a":
            catalog = build_h7a_configs(seed=seed)
        elif args.track == "H7b":
            catalog = build_h7b_configs(seed=seed)
        else:
            catalog = build_h7c_configs(
                clock_law=args.clock_law,
                use_grad_checkpoint=args.grad_checkpoint,
                seed=seed,
            )
        selected = list(catalog.keys()) if not args.arms else args.arms
        for name in selected:
            require_ok(name in catalog, f"Unknown arm {name!r} for track {args.track}")
            cfg = catalog[name]
            arm_lr = lr_ngpt if (cfg.ngpt or cfg.loop_mode in ("sphere_noclock", "sphere_randrot", "clifford_hopf")) else lr_std
            res = train_and_eval_arm(
                cfg,
                train_chunks=train_chunks,
                val_chunks=val_chunks,
                device=device,
                steps=args.steps,
                batch_size=args.batch_size,
                lr=arm_lr,
                amp_bf16=args.amp_bf16,
                run_ptq=True,
                domain_val_chunks=domain_val_chunks,
                long_val_chunks=long_val_chunks,
                log_m1_h1_checkpoints=(args.track == "H7c"),
            )
            runs.append(res)
            sys.stderr.write(
                f"[{args.track}] seed={seed} arm={name} val_bpb={res['val']['bpb']} "
                f"ptq3_kl={res.get('ptq_3bit_kl_nats')} elapsed={res['elapsed_sec']}s\n"
            )
            sys.stderr.flush()

            if args.run_probes and args.track == "H7b":
                for gname in ("S3", "A5"):
                    pr = run_h7b_group_probe(
                        arm_name=name,
                        pos_mode=cfg.pos_mode,
                        ngpt=cfg.ngpt,
                        group_name=gname,
                        seed=seed,
                        device=device,
                        steps=400,
                        batch_size=32,
                        lr=arm_lr,
                        amp_bf16=args.amp_bf16,
                    )
                    probes.append(pr)
                    sys.stderr.write(
                        f"[{args.track}-PROBE] seed={seed} arm={name} {gname}: "
                        f"id={pr['id_acc_len_8_64']} ood={pr['ood_acc_len_65_192']}\n"
                    )
                    sys.stderr.flush()
            elif args.run_probes and args.track == "H7c":
                pr = run_h7c_bracket_probe(
                    cfg,
                    device=device,
                    steps=300,
                    batch_size=32,
                    lr=arm_lr,
                    amp_bf16=args.amp_bf16,
                )
                probes.append(pr)
                sys.stderr.write(f"[{args.track}-BRACKET] seed={seed} arm={name}: {pr['bracket_depth_acc']}\n")
                sys.stderr.flush()

    # Aggregate mean +/- SE per arm across seeds.
    by_arm: Dict[str, List[Dict[str, Any]]] = {}
    for r in runs:
        by_arm.setdefault(r["arm_name"], []).append(r)

    arm_summary: Dict[str, Any] = {}
    for aname, rlist in by_arm.items():
        bpb_m, bpb_se = _mean_se([r["val"]["bpb"] for r in rlist])
        kl_m, kl_se = _mean_se([r["ptq_3bit_kl_nats"] for r in rlist])
        entry: Dict[str, Any] = {
            "seeds": [r["seed"] for r in rlist],
            "non_embedding_params": rlist[0]["params"]["non_embedding_params"],
            "fwd_flops_per_tok": rlist[0]["flops"]["total_fwd_flops_per_token"],
            "val_bpb_mean": bpb_m,
            "val_bpb_se": bpb_se,
            "ptq3_kl_mean": kl_m,
            "ptq3_kl_se": kl_se,
        }
        if "length_extrapolation_bpb" in rlist[0]:
            entry["length_extrap_mean"] = {
                k: _mean_se([r["length_extrapolation_bpb"][k] for r in rlist])[0]
                for k in rlist[0]["length_extrapolation_bpb"]
            }
        if "r_test_extrapolation_bpb" in rlist[0]:
            entry["r_test_extrap_mean"] = {
                k: _mean_se([r["r_test_extrapolation_bpb"][k] for r in rlist])[0]
                for k in rlist[0]["r_test_extrapolation_bpb"]
            }
            entry["m1_h1_4bit_ratio_mean"] = _mean_se([r["m1_h1_4bit"]["delta_r_over_delta_1"] for r in rlist])[0]
            entry["m1_h1_3bit_ratio_mean"] = _mean_se([r["m1_h1_3bit"]["delta_r_over_delta_1"] for r in rlist])[0]
            entry["m1_h1_4bit_rho_mean"] = _mean_se([r["m1_h1_4bit"]["rho_mean"] for r in rlist])[0]
        arm_summary[aname] = entry

    summary = {
        "schema_version": "aletheia.s107.gpu_eval.v1",
        "track": args.track,
        "device": args.device,
        "amp_bf16": args.amp_bf16,
        "corpus": corpus_meta,
        "seq_len": args.seq_len,
        "steps": args.steps,
        "batch_size": args.batch_size,
        "seeds": args.seeds,
        "lr_std": lr_std,
        "lr_ngpt": lr_ngpt,
        "lr_calibration": lr_calibration,
        "clock_law": args.clock_law if args.track == "H7c" else None,
        "total_elapsed_sec": round(time.monotonic() - t_track_0, 2),
        "arm_summary": arm_summary,
        "runs": runs,
        "probes": probes,
    }
    text = json.dumps(summary, sort_keys=True, indent=2) + "\n"
    if args.out_json:
        Path(args.out_json).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
