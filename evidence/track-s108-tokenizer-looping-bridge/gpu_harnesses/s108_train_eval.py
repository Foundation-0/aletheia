#!/usr/bin/env python3
"""Track S108 (PREREG-S108 + Amendment 1) Training & Evaluation Harness (CPU Pre-Flight & RTX 3080).

Executes all 3 amended H8 experiments at matched raw UTF-8 byte windows (strict BPB) with
paired-seed statistics and preregistered pass/kill gate verdicts:
  - H8a: Flat-BPE vs Flat-BPE-Sphere vs Rank1-Kron vs Amended Hybrid-Kron-Sphere
         vs Hybrid-Kron-Sphere-Reinvest (iso-param) vs RandPair adversarial null.
  - H8b: BPE-Std vs Fixed-4B vs BLT-Entropy vs H-Net Cosine (N0) vs 2nd-Order Geodesic Curvature
         (+ Portal-2 Turing D!=dI vs D=dI boundary-nucleation diagnostic).
  - H8c: Part 1 (Adaptive r_bar=2.0 vs Uniform r=2 vs Random r_bar=2.0 on SafeHopfLoopCore),
         Part 2 (Markov-Coupled MTP-8 [TF + unrolled] vs Parallel MTP-8 vs Local AR Byte Decoder,
                 primary BPB strictly from final loop-exit chain-rule head),
         Part 3 (Unconfounded English-JSON vs ABIOS/3 vs Direct-Binary-Oracle vs NullModem-E8-Cell
                 with exact wire_bits accounting, frozen judge, & counterfactual audit decoder).

CPU-only safe (`--device cpu` default; refuses CUDA unless `--device cuda` is explicitly given).
Saves ZERO model weights (`WEIGHTS=0`); writes locked protocol & canonical JSON receipts.
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
import re
import sys
import time
from typing import Any, Sequence

import torch
import torch.nn as nn
import torch.nn.functional as F

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import s108_tokenizer_loop_ops as ops  # noqa: E402

CALCULUS_GLYPHS = "⧄ ⧅ ⦷ ⟠ ⧇ ⦺ ⩩ ⫩"
_ARABIC_SPAN_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\s،؛؟]+")


def seed_everything(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _paired_stats(a_vals: Sequence[float], b_vals: Sequence[float]) -> dict[str, Any]:
    """Paired statistics for (a - b): negative delta means a has LOWER (better) BPB than b."""
    n = min(len(a_vals), len(b_vals))
    if n == 0:
        return {"n": 0, "mean_diff": 0.0, "rel_pct": 0.0, "se": 0.0, "z": 0.0}
    diffs = [float(a_vals[i] - b_vals[i]) for i in range(n)]
    mean_d = sum(diffs) / n
    mean_b = sum(float(b_vals[i]) for i in range(n)) / n
    rel_pct = (100.0 * mean_d / mean_b) if abs(mean_b) > 1e-12 else 0.0
    if n < 2:
        return {"n": n, "mean_diff": round(mean_d, 6), "rel_pct": round(rel_pct, 4), "se": 0.0, "z": 0.0}
    var = sum((d - mean_d) ** 2 for d in diffs) / (n - 1)
    se = math.sqrt(var / n)
    z = (mean_d / se) if se > 1e-12 else (math.copysign(999.0, mean_d) if abs(mean_d) > 1e-12 else 0.0)
    return {
        "n": n,
        "mean_diff": round(mean_d, 6),
        "rel_pct": round(rel_pct, 4),
        "se": round(se, 6),
        "z": round(z, 4),
    }


# ---------------------------------------------------------------------------
# Deterministic 4-Domain Multi-Corpus UTF-8 Byte Loader (Strictly Disjoint Train/Eval)
# ---------------------------------------------------------------------------


def _snap_utf8_slice(buf: bytes, start: int, end: int) -> bytes:
    """Slice raw UTF-8 bytes cleanly on character boundaries so decode('utf-8') is always strict."""
    n = len(buf)
    s = max(0, min(start, n))
    e = max(s, min(end, n))
    while s < e and (buf[s] & 0xC0) == 0x80:
        s += 1
    while e > s:
        try:
            buf[s:e].decode("utf-8", errors="strict")
            return buf[s:e]
        except UnicodeDecodeError:
            e -= 1
    return b""


def _synthetic_domain_bytes(domain: str, min_bytes: int) -> bytes:
    if domain == "english":
        base = (
            "In mathematical physics, exact conservation laws constrain discrete state transport across "
            "curved hyperspheres without relying on floating-point heuristics. A deterministic verifier "
            "checks every algebraic boundary condition before authorizing compute allocation.\n"
        )
    elif domain == "python":
        base = (
            "def verify_conservation(state, operator):\n"
            "    energy_before = sum(x * x for x in state)\n"
            "    next_state = [sum(a * b for a, b in zip(row, state)) for row in operator]\n"
            "    energy_after = sum(x * x for x in next_state)\n"
            "    return energy_before == energy_after\n\n"
        )
    elif domain == "arabic":
        base = (
            "قال ابن الهيثم في كتاب المناظر إن الضوء يمتد على خطوط مستقيمة في الأجسام الشفافة المتشابهة "
            "وذكر ابن سينا في القانون والشفاء أن البرهان الهندسي يضبط القياس الطبيعي بدقة تامة "
            "وبين الخوارزمي في الجبر والمقابلة أن استخراج المجهول يعتمد على حفظ المعادلة وتوازن الحدود.\n"
        )
    elif domain == "abios_calculus":
        base = (
            f"@msg v=3 op=GATE_CHECK src=exo dst=warp sym=[{CALCULUS_GLYPHS}] "
            "kv={inv:schur_psd,c_row:1,rho_cap:2,mode:strict}\n"
            f"@ack v=3 op=RECEIPT_OK hash=sha256:9f86d081884c7d659a2feaa0c55ad015 "
            f"ops=({CALCULUS_GLYPHS}) status=PASS\n"
        )
    else:
        raise ValueError(f"unknown domain: {domain!r}")
    raw = base.encode("utf-8")
    reps = (min_bytes // len(raw)) + 2
    return (raw * reps)[:min_bytes]


def load_multidomain_byte_splits(
    max_bytes_per_domain: int = 32_768,
    allow_local_caches: bool = True,
    fail_closed: bool = False,
) -> tuple[dict[str, dict[str, bytes]], dict[str, str]]:
    """Load deterministic, strictly disjoint train/eval UTF-8 byte streams across all 4 domains."""
    expedition_root = _HERE.parent
    splits: dict[str, dict[str, bytes]] = {}
    eval_cap = max(2048, max_bytes_per_domain // 3)

    # 1. English: strictly disjoint WikiText-2 val (train) vs WikiText-2 test (eval) when available
    eng_tr, eng_ev = b"", b""
    if allow_local_caches:
        wt_cache = Path.home() / ".cache" / "huggingface" / "s49b_eval"
        wt_val = wt_cache / "wikitext2_val.txt"
        wt_test = wt_cache / "wikitext2_test.txt"
        if wt_val.exists() and wt_test.exists():
            eng_tr = _snap_utf8_slice(wt_val.read_bytes(), 0, max_bytes_per_domain)
            eng_ev = _snap_utf8_slice(wt_test.read_bytes(), 0, eval_cap)
    if len(eng_tr) < 2048 or len(eng_ev) < 1024:
        if fail_closed:
            raise RuntimeError("CORPUS_SOURCE_MISSING: english WikiText-2 cache absent; refusing synthetic fallback in gpu-full mode")
        full = _synthetic_domain_bytes("english", max_bytes_per_domain + eval_cap)
        eng_tr = _snap_utf8_slice(full, 0, max_bytes_per_domain)
        eng_ev = _snap_utf8_slice(full, max_bytes_per_domain, max_bytes_per_domain + eval_cap)
    splits["english"] = {"train": eng_tr, "eval": eng_ev}

    # 2. Python: strictly disjoint stdlib modules for train vs held-out eval
    stdlib_dir = Path(json.__file__).resolve().parent.parent
    py_tr_mods = ("ast.py", "fractions.py", "decimal.py", "inspect.py", "difflib.py")
    py_ev_mods = ("json/decoder.py", "json/encoder.py", "argparse.py", "unittest/case.py")
    py_tr = b"\n".join((stdlib_dir / m).read_bytes() for m in py_tr_mods if (stdlib_dir / m).exists())
    py_ev = b"\n".join((stdlib_dir / m).read_bytes() for m in py_ev_mods if (stdlib_dir / m).exists())
    if len(py_tr) < 2048 or len(py_ev) < 1024:
        if fail_closed:
            raise RuntimeError("CORPUS_SOURCE_MISSING: python stdlib sources absent; refusing synthetic fallback in gpu-full mode")
        full_p = _synthetic_domain_bytes("python", max_bytes_per_domain + eval_cap)
        py_tr = _snap_utf8_slice(full_p, 0, max_bytes_per_domain)
        py_ev = _snap_utf8_slice(full_p, max_bytes_per_domain, max_bytes_per_domain + eval_cap)
    else:
        py_tr = _snap_utf8_slice(py_tr, 0, max_bytes_per_domain)
        py_ev = _snap_utf8_slice(py_ev, 0, eval_cap)
    splits["python"] = {"train": py_tr, "eval": py_ev}

    # 3. Multi-byte UTF-8 Unicode/Arabic/Lean formal corpus (strictly file-disjoint train vs eval, ZERO repetition)
    ar_tr, ar_ev = b"", b""
    if allow_local_caches:
        unicode_files: list[Path] = []
        bayt_dir = expedition_root / "publish" / "bayt-al-hikma"
        if bayt_dir.exists():
            unicode_files.extend(
                sorted(p for p in bayt_dir.rglob("*") if p.is_file() and p.suffix in (".md", ".json"))
            )
        unicode_files.extend(sorted(expedition_root.glob("track-s*/**/*.lean")))
        # Strictly file-disjoint split (every 4th file held out for eval -> zero file overlap!)
        tr_parts = [p.read_bytes() for i, p in enumerate(unicode_files) if i % 4 != 3]
        ev_parts = [p.read_bytes() for i, p in enumerate(unicode_files) if i % 4 == 3]
        if tr_parts and ev_parts:
            ar_tr = _snap_utf8_slice(b"\n".join(tr_parts), 0, max_bytes_per_domain)
            ar_ev = _snap_utf8_slice(b"\n".join(ev_parts), 0, eval_cap)
    if len(ar_tr) < 2048 or len(ar_ev) < 1024:
        if fail_closed:
            raise RuntimeError("CORPUS_SOURCE_MISSING: arabic (bayt-al-hikma) sources absent; refusing synthetic fallback in gpu-full mode")
        full_ar = _synthetic_domain_bytes("arabic", max_bytes_per_domain + eval_cap)
        ar_tr = _snap_utf8_slice(full_ar, 0, max_bytes_per_domain)
        ar_ev = _snap_utf8_slice(full_ar, max_bytes_per_domain, max_bytes_per_domain + eval_cap)
    splits["arabic"] = {"train": ar_tr, "eval": ar_ev}

    # 4. ABIOS/3 + structured JSON/agent corpus (strictly file-disjoint train vs eval, ZERO repetition)
    ab_tr, ab_ev = b"", b""
    if allow_local_caches:
        ab_dir = expedition_root / "publish" / "abios-wire-lists-lossless-fix"
        if ab_dir.exists():
            ab_files = sorted(
                p for p in ab_dir.rglob("*") if p.is_file() and p.suffix in (".md", ".jsonl", ".json", ".py")
            )
            tr_ab = [p.read_bytes() for i, p in enumerate(ab_files) if i % 4 != 3]
            ev_ab = [p.read_bytes() for i, p in enumerate(ab_files) if i % 4 == 3]
            if tr_ab and ev_ab:
                ab_tr = _snap_utf8_slice(b"\n".join(tr_ab), 0, max_bytes_per_domain)
                ab_ev = _snap_utf8_slice(b"\n".join(ev_ab), 0, eval_cap)
    if len(ab_tr) < 2048 or len(ab_ev) < 1024:
        if fail_closed:
            raise RuntimeError("CORPUS_SOURCE_MISSING: abios_calculus publish sources absent; refusing synthetic fallback in gpu-full mode")
        full_ab = _synthetic_domain_bytes("abios_calculus", max_bytes_per_domain + eval_cap)
        ab_tr = _snap_utf8_slice(full_ab, 0, max_bytes_per_domain)
        ab_ev = _snap_utf8_slice(full_ab, max_bytes_per_domain, max_bytes_per_domain + eval_cap)
    splits["abios_calculus"] = {"train": ab_tr, "eval": ab_ev}

    digests: dict[str, str] = {}
    for dom, pair in splits.items():
        # Verify strict UTF-8 validity of both splits
        pair["train"].decode("utf-8", errors="strict")
        pair["eval"].decode("utf-8", errors="strict")
        digests[dom] = hashlib.sha256(pair["train"] + b"\x00" + pair["eval"]).hexdigest()
    return splits, digests


# ---------------------------------------------------------------------------
# H8a Model & Runner
# ---------------------------------------------------------------------------


class H8aTokenLM(nn.Module):
    """Language model comparing H8a embedding factorizations on identical BPE streams."""

    def __init__(
        self,
        arm: str,
        vocab_size: int,
        d_model: int,
        n_layers: int,
        n_heads: int,
        codec: ops.MorphStructPairCodec,
        d_a: int = 8,
        d_b: int = 8,
    ) -> None:
        super().__init__()
        self.arm = arm
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.n_layers = n_layers
        if arm == "flat_bpe":
            self.embed: nn.Module = ops.FlatSphereEmbedding(vocab_size, d_model, normalize_rows=False)
        elif arm == "flat_bpe_sphere":
            self.embed = ops.FlatSphereEmbedding(vocab_size, d_model, normalize_rows=True)
        elif arm == "rank1_kron":
            self.embed = ops.Rank1KronEmbedding(
                codec.morph_roots, codec.morph_patterns, codec.n_roots, codec.n_patterns, d_a, d_b, d_model
            )
        elif arm in ("hybrid_kron_sphere", "hybrid_kron_sphere_reinvest"):
            self.embed = ops.HybridKronSphereEmbedding(
                codec.morph_roots, codec.morph_patterns, codec.n_roots, codec.n_patterns, d_a, d_b, d_model
            )
        elif arm == "hybrid_kron_randpair":
            self.embed = ops.HybridKronSphereEmbedding(
                codec.rand_roots, codec.rand_patterns, codec.n_roots, codec.n_patterns, d_a, d_b, d_model
            )
        else:
            raise ValueError(f"unknown H8a arm: {arm!r}")
        self.blocks = nn.ModuleList([ops.CausalSelfAttnBlock(d_model, n_heads, mlp_mult=2) for _ in range(n_layers)])
        self.norm_f = nn.RMSNorm(d_model)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)

    def forward(self, token_ids: torch.Tensor) -> torch.Tensor:
        x = self.embed(token_ids)
        for blk in self.blocks:
            x = blk(x)
        return self.lm_head(self.norm_f(x))


def _eval_token_bpb_on_byte_windows(
    model: H8aTokenLM,
    bpe: Any,
    eval_bytes: bytes,
    ctx_bytes: int,
    stride_bytes: int,
    device: torch.device,
    max_windows: int = 32,
) -> float:
    """Exact UTF-8 BPB on fixed byte windows: total_NLL_nats / (total_UTF8_bytes * ln 2)."""
    model.eval()
    total_nats = 0.0
    total_bytes = 0
    seen = 0
    with torch.no_grad():
        for start in range(0, max(1, len(eval_bytes) - ctx_bytes + 1), stride_bytes):
            if seen >= max_windows:
                break
            window = _snap_utf8_slice(eval_bytes, start, start + ctx_bytes)
            if len(window) < 8:
                continue
            toks = bpe.encode(window)
            if len(toks) < 2:
                continue
            if bpe.decode(toks) != window:
                raise RuntimeError("BPE round-trip decode(encode(window)) != window")
            inp = torch.tensor(toks[:-1], dtype=torch.long, device=device).unsqueeze(0)
            tgt = torch.tensor(toks[1:], dtype=torch.long, device=device).unsqueeze(0)
            logits = model(inp).float()
            nll = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), tgt.reshape(-1), reduction="sum")
            scored_bytes = len(bpe.decode(toks[1:]))
            total_nats += float(nll.item())
            total_bytes += scored_bytes
            seen += 1
    return total_nats / (max(total_bytes, 1) * math.log(2.0))


def _sample_batch(stream: torch.Tensor, batch_size: int, seq_len: int, gen: torch.Generator) -> torch.Tensor:
    max_start = max(1, int(stream.numel()) - seq_len - 1)
    starts = torch.randint(0, max_start, (batch_size,), generator=gen)
    idx = starts.unsqueeze(1) + torch.arange(seq_len + 1).unsqueeze(0)
    return stream[idx]


def run_h8a_experiment(
    splits: dict[str, dict[str, bytes]],
    cfg: dict[str, Any],
    device: torch.device,
) -> dict[str, Any]:
    train_concat = b"\n".join(splits[d]["train"] for d in splits)
    bpe = ops.FastByteLevelBPE(vocab_size=cfg["vocab_size"]).fit(train_concat)
    n_roots = int(math.ceil(math.sqrt(bpe.vocab_size)))
    n_patterns = int(math.ceil(bpe.vocab_size / n_roots))
    codec = ops.MorphStructPairCodec(bpe.id_to_bytes, n_roots=n_roots, n_patterns=n_patterns, seed=cfg["seeds"][0])
    m_ok, r_ok = codec.verify_injective()
    if not (m_ok and r_ok):
        raise RuntimeError("MorphStructPairCodec failed injectivity verification")

    arms = (
        "flat_bpe",
        "flat_bpe_sphere",
        "rank1_kron",
        "hybrid_kron_sphere",
        "hybrid_kron_sphere_reinvest",
        "hybrid_kron_randpair",
    )
    train_t = torch.tensor(bpe.encode(train_concat), dtype=torch.long)
    batch_size = int(cfg.get("batch_size", 1))
    use_bf16 = device.type == "cuda"
    amp_ctx = (lambda: torch.amp.autocast("cuda", dtype=torch.bfloat16)) if use_bf16 else nullcontext

    results: dict[str, Any] = {
        "vocab_size": bpe.vocab_size,
        "n_roots": n_roots,
        "n_patterns": n_patterns,
        "arms": {},
    }
    for arm in arms:
        n_layers = cfg["n_layers"] + (1 if arm == "hybrid_kron_sphere_reinvest" else 0)
        seed_runs: list[dict[str, Any]] = []
        params_info: dict[str, int] = {}
        for sd in cfg["seeds"]:
            seed_everything(sd)
            gen = torch.Generator(device="cpu")
            gen.manual_seed(sd * 97 + 13)
            model = H8aTokenLM(
                arm=arm,
                vocab_size=bpe.vocab_size,
                d_model=cfg["d_model"],
                n_layers=n_layers,
                n_heads=cfg["n_heads"],
                codec=codec,
                d_a=cfg["d_a"],
                d_b=cfg["d_b"],
            ).to(device)
            opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=0.05)
            seq_tok = max(16, min(cfg["seq_tok"], int(train_t.numel()) - 2))
            steps = int(cfg["steps"])
            model.train()
            last_loss = 0.0
            for step in range(steps):
                # Cosine schedule with 10% linear warmup
                warm = max(1, steps // 10)
                if step < warm:
                    lr_now = cfg["lr"] * float(step + 1) / float(warm)
                else:
                    prog = float(step - warm) / float(max(1, steps - warm))
                    lr_now = cfg["lr"] * (0.1 + 0.9 * 0.5 * (1.0 + math.cos(math.pi * prog)))
                for pg in opt.param_groups:
                    pg["lr"] = lr_now
                batch = _sample_batch(train_t, batch_size, seq_tok, gen).to(device, non_blocking=True)
                x, y = batch[:, :-1], batch[:, 1:]
                opt.zero_grad(set_to_none=True)
                with amp_ctx():
                    logits = model(x)
                    loss = F.cross_entropy(logits.float().reshape(-1, logits.shape[-1]), y.reshape(-1))
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                last_loss = float(loss.item())
            dom_bpb = {
                dom: round(
                    _eval_token_bpb_on_byte_windows(
                        model,
                        bpe,
                        splits[dom]["eval"],
                        cfg["ctx_bytes"],
                        cfg["stride_bytes"],
                        device,
                        max_windows=cfg.get("eval_windows", 32),
                    ),
                    6,
                )
                for dom in splits
            }
            ar_ab_bpb = 0.5 * (dom_bpb["arabic"] + dom_bpb["abios_calculus"])
            en_py_bpb = 0.5 * (dom_bpb["english"] + dom_bpb["python"])
            seed_runs.append(
                {
                    "seed": sd,
                    "final_train_loss": round(last_loss, 6),
                    "domain_bpb": dom_bpb,
                    "arabic_abios_bpb": round(ar_ab_bpb, 6),
                    "english_python_bpb": round(en_py_bpb, 6),
                    "mean_bpb": round(sum(dom_bpb.values()) / len(dom_bpb), 6),
                }
            )
            params_info = ops.count_model_params(model)
        flops_per_tok = ops.estimate_transformer_fwd_flops_per_token(
            cfg["d_model"], n_layers, cfg["seq_tok"], bpe.vocab_size, mlp_mult=2
        )
        results["arms"][arm] = {
            "n_layers": n_layers,
            "params": params_info,
            "fwd_flops_per_token": flops_per_tok,
            "runs": seed_runs,
            "mean_bpb_across_seeds": round(sum(r["mean_bpb"] for r in seed_runs) / len(seed_runs), 6),
            "mean_arabic_abios_bpb": round(sum(r["arabic_abios_bpb"] for r in seed_runs) / len(seed_runs), 6),
            "mean_english_python_bpb": round(sum(r["english_python_bpb"] for r in seed_runs) / len(seed_runs), 6),
        }

    # Strict paired-seed PREREG-S108 H8a grading
    hyb_runs = results["arms"]["hybrid_kron_sphere"]["runs"]
    reinv_runs = results["arms"]["hybrid_kron_sphere_reinvest"]["runs"]
    best_hyb_name = (
        "hybrid_kron_sphere_reinvest"
        if results["arms"]["hybrid_kron_sphere_reinvest"]["mean_arabic_abios_bpb"]
        < results["arms"]["hybrid_kron_sphere"]["mean_arabic_abios_bpb"]
        else "hybrid_kron_sphere"
    )
    best_runs = results["arms"][best_hyb_name]["runs"]
    cmp_h8a = {
        "best_hybrid_arm": best_hyb_name,
        "hyb_vs_flat_bpe_ar_ab": _paired_stats(
            [r["arabic_abios_bpb"] for r in hyb_runs],
            [r["arabic_abios_bpb"] for r in results["arms"]["flat_bpe"]["runs"]],
        ),
        "best_vs_flat_bpe_ar_ab": _paired_stats(
            [r["arabic_abios_bpb"] for r in best_runs],
            [r["arabic_abios_bpb"] for r in results["arms"]["flat_bpe"]["runs"]],
        ),
        "best_vs_rank1_ar_ab": _paired_stats(
            [r["arabic_abios_bpb"] for r in best_runs],
            [r["arabic_abios_bpb"] for r in results["arms"]["rank1_kron"]["runs"]],
        ),
        "best_vs_randpair_ar_ab": _paired_stats(
            [r["arabic_abios_bpb"] for r in best_runs],
            [r["arabic_abios_bpb"] for r in results["arms"]["hybrid_kron_randpair"]["runs"]],
        ),
        "best_vs_flat_bpe_en_py": _paired_stats(
            [r["english_python_bpb"] for r in best_runs],
            [r["english_python_bpb"] for r in results["arms"]["flat_bpe"]["runs"]],
        ),
    }
    _ = reinv_runs
    beats_all_3 = all(
        cmp_h8a[k]["rel_pct"] <= -3.0 and cmp_h8a[k]["z"] <= -2.0
        for k in ("best_vs_flat_bpe_ar_ab", "best_vs_rank1_ar_ab", "best_vs_randpair_ar_ab")
    )
    en_py_ok = cmp_h8a["best_vs_flat_bpe_en_py"]["rel_pct"] <= 0.5
    cmp_h8a["verdict"] = "CONFIRMED" if (beats_all_3 and en_py_ok) else "FALSIFIED"
    results["grading"] = cmp_h8a
    return results


# ---------------------------------------------------------------------------
# H8b Model & Runner: Vectorized Strictly Causal DynamicBytePatchLM
# ---------------------------------------------------------------------------


class DynamicBytePatchLM(nn.Module):
    """Strictly causal vectorized byte-level LM with pluggable boundary router (zero future leakage!).

    Causality invariant:
      - Position t only encodes bytes <= t-1 via shifted CausalByteEncoder.
      - Patch boundaries partition positions into patches 0, 1, ..., P-1.
      - Patch k's pooled latent h_p[k] is broadcast ONLY to positions in patch k+1 (patch 0 gets 0).
      - Streaming byte-by-byte NLL matches teacher-forced NLL to < 1e-5 BPB.
    """

    def __init__(
        self,
        router_kind: str,
        d_b: int,
        d_model: int,
        n_layers: int,
        n_heads: int,
        target_patch_len: float = 4.0,
    ) -> None:
        super().__init__()
        if router_kind not in ("fixed_byte4", "blt_entropy", "hnet_cosine", "spherepatch_geodesic2"):
            raise ValueError(f"unknown H8b router_kind: {router_kind!r}")
        self.router_kind = router_kind
        self.d_b = d_b
        self.d_model = d_model
        self.n_layers = n_layers
        self.target_patch_len = target_patch_len
        self.byte_enc = ops.CausalByteEncoder(d_b=d_b, kernel_size=4)
        self.blt_aux = ops.BLTAuxEntropyRouter(d_aux=max(16, d_b // 2)) if router_kind == "blt_entropy" else None
        self.router_scale = nn.Parameter(torch.tensor(6.0))
        self.router_bias = nn.Parameter(torch.tensor(-1.5))
        self.to_patch = nn.Linear(d_b, d_model, bias=False)
        self.patch_blocks = nn.ModuleList([ops.CausalSelfAttnBlock(d_model, n_heads, mlp_mult=2) for _ in range(n_layers)])
        self.patch_norm = nn.RMSNorm(d_model)
        self.from_patch = nn.Linear(d_model, d_b, bias=False)
        self.dec_proj = nn.Linear(d_b, 256)

    def compute_boundary_scores(self, byte_ids: torch.Tensor, u: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        b, seq_len = byte_ids.shape
        zero = torch.zeros((), dtype=u.dtype, device=u.device)
        if self.router_kind == "fixed_byte4":
            pos = torch.arange(seq_len, device=byte_ids.device)
            sig = ((pos % 4) == 0).to(u.dtype).unsqueeze(0).expand(b, -1)
            return sig, zero
        if self.router_kind == "blt_entropy":
            if self.blt_aux is None:
                raise RuntimeError("blt_aux missing")
            aux_logits, norm_ent = self.blt_aux(byte_ids)
            aux_loss = F.cross_entropy(aux_logits.float().reshape(-1, 256), byte_ids.reshape(-1))
            return norm_ent, aux_loss
        if self.router_kind == "hnet_cosine":
            return ops.hnet_first_order_cosine_score(u), zero
        return ops.geodesic_second_order_turning_score(u), zero

    def forward(self, byte_ids: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, dict[str, float]]:
        b, seq_len = byte_ids.shape
        shifted = torch.zeros_like(byte_ids)
        if seq_len > 1:
            shifted[:, 1:] = byte_ids[:, :-1]
        u = self.byte_enc(shifted)  # [B, L, d_b]
        raw_sig, aux_lm_loss = self.compute_boundary_scores(shifted, u)
        if self.router_kind == "fixed_byte4":
            probs = raw_sig
            bal_loss = torch.zeros((), dtype=u.dtype, device=u.device)
        else:
            probs = torch.sigmoid(self.router_scale * raw_sig + self.router_bias)
            probs = torch.cat([torch.ones((b, 1), dtype=u.dtype, device=u.device), probs[:, 1:]], dim=1)
            bal_loss = ops.hnet_ratio_balance_loss(probs, target_rate=1.0 / self.target_patch_len)

        hard_bnd = (probs >= 0.5).to(torch.long)
        hard_bnd[:, 0] = 1
        ste_bnd = hard_bnd.to(u.dtype) - probs.detach() + probs

        # Vectorized causal patch assignment: patch_id[b, t] in {0, ..., P_b - 1}
        patch_id = torch.cumsum(hard_bnd, dim=1) - 1  # [B, L]
        p_max = int(patch_id.max().item()) + 1
        total_patches = int((patch_id[:, -1] + 1).sum().item())

        # Vectorized mean pooling of bytes per patch + STE boundary weight at patch start
        p_sum = torch.zeros((b, p_max, self.d_b), dtype=u.dtype, device=u.device)
        p_cnt = torch.zeros((b, p_max, 1), dtype=u.dtype, device=u.device)
        idx_exp = patch_id.unsqueeze(-1).expand(-1, -1, self.d_b)
        p_sum.scatter_add_(1, idx_exp, u)
        p_cnt.scatter_add_(1, patch_id.unsqueeze(-1), torch.ones((b, seq_len, 1), dtype=u.dtype, device=u.device))
        p_mean = p_sum / p_cnt.clamp_min(1.0)

        # Gather STE gate weight at each patch's starting position (strictly causal)
        gate_sum = torch.zeros((b, p_max, 1), dtype=u.dtype, device=u.device)
        gate_sum.scatter_add_(1, patch_id.unsqueeze(-1), (ste_bnd * hard_bnd.to(u.dtype)).unsqueeze(-1))
        p_mat = p_mean * gate_sum.clamp(0.25, 1.0)

        # Causal patch transformer over [B, P_max, d_model]
        h_p = self.to_patch(p_mat)
        for blk in self.patch_blocks:
            h_p = blk(h_p)
        h_p = self.from_patch(self.patch_norm(h_p))  # [B, P_max, d_b]

        # Shift patches right by 1 (prepend zeros for patch 0) so patch k's context goes strictly to patch k+1!
        h_shifted = torch.cat([torch.zeros((b, 1, self.d_b), dtype=u.dtype, device=u.device), h_p[:, :-1, :]], dim=1)
        patch_context = torch.gather(h_shifted, dim=1, index=idx_exp)

        fused = u + patch_context
        logits = self.dec_proj(fused)
        avg_patch_len = (b * seq_len) / max(total_patches, 1)
        stats = {
            "avg_patch_len": round(float(avg_patch_len), 4),
            "boundary_rate": round(float(total_patches / max(b * seq_len, 1)), 4),
        }
        return logits, aux_lm_loss + 0.1 * bal_loss, stats


def eval_byte_patch_bpb(
    model: DynamicBytePatchLM,
    eval_bytes: bytes,
    ctx_bytes: int,
    stride_bytes: int,
    device: torch.device,
    max_windows: int = 32,
) -> tuple[float, float]:
    """Exact chain-rule UTF-8 BPB (excluding all auxiliary losses, fp32 log-softmax)."""
    model.eval()
    total_nats = 0.0
    total_bytes = 0
    patch_lens: list[float] = []
    seen = 0
    with torch.no_grad():
        for start in range(0, max(1, len(eval_bytes) - ctx_bytes + 1), stride_bytes):
            if seen >= max_windows:
                break
            window = _snap_utf8_slice(eval_bytes, start, start + ctx_bytes)
            if len(window) < 8:
                continue
            b_t = torch.tensor(list(window), dtype=torch.long, device=device).unsqueeze(0)
            logits, _, st = model(b_t)
            nll = F.cross_entropy(logits[:, 1:, :].float().reshape(-1, 256), b_t[:, 1:].reshape(-1), reduction="sum")
            total_nats += float(nll.item())
            total_bytes += len(window) - 1
            patch_lens.append(st["avg_patch_len"])
            seen += 1
    bpb = total_nats / (max(total_bytes, 1) * math.log(2.0))
    mean_pl = sum(patch_lens) / max(len(patch_lens), 1)
    return bpb, mean_pl


def run_h8b_experiment(
    splits: dict[str, dict[str, bytes]],
    cfg: dict[str, Any],
    device: torch.device,
) -> dict[str, Any]:
    train_concat = b"\n".join(splits[d]["train"] for d in splits)
    train_b = torch.tensor(list(train_concat), dtype=torch.long)
    batch_size = int(cfg.get("batch_size", 1))
    use_bf16 = device.type == "cuda"
    amp_ctx = (lambda: torch.amp.autocast("cuda", dtype=torch.bfloat16)) if use_bf16 else nullcontext

    results: dict[str, Any] = {
        "ctx_bytes": cfg["ctx_bytes"],
        "turing_diagnostic": {
            "diff_D_1_10": ops.turing_boundary_nucleation_diagnostic(seq_len=32, d_u=1.0, d_v=10.0),
            "equal_D_5_5_null": ops.turing_boundary_nucleation_diagnostic(seq_len=32, d_u=5.0, d_v=5.0),
        },
        "arms": {},
    }

    # Control A: BPE-Std on IDENTICAL raw UTF-8 byte windows (AMENDMENT1 §5 byte-context parity!)
    bpe = ops.FastByteLevelBPE(vocab_size=cfg.get("bpe_vocab_size", 320)).fit(train_concat)
    n_roots = int(math.ceil(math.sqrt(bpe.vocab_size)))
    n_patterns = int(math.ceil(bpe.vocab_size / n_roots))
    dummy_codec = ops.MorphStructPairCodec(bpe.id_to_bytes, n_roots=n_roots, n_patterns=n_patterns, seed=cfg["seeds"][0])
    bpe_train_t = torch.tensor(bpe.encode(train_concat), dtype=torch.long)
    # Approximate token window covering exact same ctx_bytes bytes
    bytes_per_tok = len(train_concat) / max(int(bpe_train_t.numel()), 1)
    bpe_seq_tok = max(16, min(int(round(cfg["ctx_bytes"] / max(bytes_per_tok, 1.0))), int(bpe_train_t.numel()) - 2))

    bpe_runs: list[dict[str, Any]] = []
    bpe_params_info: dict[str, int] = {}
    for sd in cfg["seeds"]:
        seed_everything(sd)
        gen = torch.Generator(device="cpu")
        gen.manual_seed(sd * 53 + 7)
        bpe_model = H8aTokenLM(
            arm="flat_bpe",
            vocab_size=bpe.vocab_size,
            d_model=cfg["d_model"],
            n_layers=cfg["n_layers"],
            n_heads=cfg["n_heads"],
            codec=dummy_codec,
        ).to(device)
        opt = torch.optim.AdamW(bpe_model.parameters(), lr=cfg["lr"], weight_decay=0.05)
        bpe_model.train()
        last_ce = 0.0
        for _ in range(cfg["steps"]):
            batch = _sample_batch(bpe_train_t, batch_size, bpe_seq_tok, gen).to(device, non_blocking=True)
            t_in, t_tg = batch[:, :-1], batch[:, 1:]
            opt.zero_grad(set_to_none=True)
            with amp_ctx():
                lg = bpe_model(t_in)
                loss = F.cross_entropy(lg.float().reshape(-1, lg.shape[-1]), t_tg.reshape(-1))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(bpe_model.parameters(), 1.0)
            opt.step()
            last_ce = float(loss.item())
        dom_bpb = {
            dom: round(
                _eval_token_bpb_on_byte_windows(
                    bpe_model,
                    bpe,
                    splits[dom]["eval"],
                    cfg["ctx_bytes"],
                    cfg["stride_bytes"],
                    device,
                    max_windows=cfg.get("eval_windows", 32),
                ),
                6,
            )
            for dom in splits
        }
        bpe_runs.append(
            {
                "seed": sd,
                "final_train_ce": round(last_ce, 6),
                "domain_bpb": dom_bpb,
                "arabic_en_gap": round(dom_bpb["arabic"] - dom_bpb["english"], 6),
                "mean_bpb": round(sum(dom_bpb.values()) / len(dom_bpb), 6),
            }
        )
        bpe_params_info = ops.count_model_params(bpe_model)
    results["arms"]["bpe_std"] = {
        "params": bpe_params_info,
        "vocab_size": bpe.vocab_size,
        "bytes_per_tok": round(bytes_per_tok, 4),
        "runs": bpe_runs,
        "mean_bpb_across_seeds": round(sum(r["mean_bpb"] for r in bpe_runs) / len(bpe_runs), 6),
    }

    arms = ("fixed_byte4", "blt_entropy", "hnet_cosine", "spherepatch_geodesic2")
    for arm in arms:
        seed_runs: list[dict[str, Any]] = []
        params_info: dict[str, int] = {}
        for sd in cfg["seeds"]:
            seed_everything(sd)
            gen = torch.Generator(device="cpu")
            gen.manual_seed(sd * 53 + 11)
            model = DynamicBytePatchLM(
                router_kind=arm,
                d_b=cfg["d_b"],
                d_model=cfg["d_model"],
                n_layers=cfg["n_layers"],
                n_heads=cfg["n_heads"],
                target_patch_len=4.0,
            ).to(device)
            opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=0.05)
            seq_b = min(cfg["ctx_bytes"], int(train_b.numel()) - 2)
            model.train()
            last_loss = 0.0
            for _ in range(cfg["steps"]):
                batch = _sample_batch(train_b, batch_size, seq_b - 1, gen).to(device, non_blocking=True)
                opt.zero_grad(set_to_none=True)
                with amp_ctx():
                    logits, aux_loss, _ = model(batch)
                    ce = F.cross_entropy(logits[:, 1:, :].float().reshape(-1, 256), batch[:, 1:].reshape(-1))
                    loss = ce + aux_loss
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                last_loss = float(ce.item())
            dom_bpb: dict[str, float] = {}
            dom_pl: dict[str, float] = {}
            for dom in splits:
                bpb, pl = eval_byte_patch_bpb(
                    model,
                    splits[dom]["eval"],
                    cfg["ctx_bytes"],
                    cfg["stride_bytes"],
                    device,
                    max_windows=cfg.get("eval_windows", 32),
                )
                dom_bpb[dom] = round(bpb, 6)
                dom_pl[dom] = round(pl, 4)
            seed_runs.append(
                {
                    "seed": sd,
                    "final_train_ce": round(last_loss, 6),
                    "domain_bpb": dom_bpb,
                    "domain_avg_patch_len": dom_pl,
                    "arabic_en_gap": round(dom_bpb["arabic"] - dom_bpb["english"], 6),
                    "mean_bpb": round(sum(dom_bpb.values()) / len(dom_bpb), 6),
                }
            )
            params_info = ops.count_model_params(model)
        results["arms"][arm] = {
            "params": params_info,
            "runs": seed_runs,
            "mean_bpb_across_seeds": round(sum(r["mean_bpb"] for r in seed_runs) / len(seed_runs), 6),
        }

    # Strict paired-seed Amendment-1 H8b grading (must beat H-Net N0 by >= 2 SE + beat Fixed-4B & BPE)
    sp_runs = results["arms"]["spherepatch_geodesic2"]["runs"]
    cmp_h8b = {
        "sphere2_vs_hnet_n0": _paired_stats(
            [r["mean_bpb"] for r in sp_runs],
            [r["mean_bpb"] for r in results["arms"]["hnet_cosine"]["runs"]],
        ),
        "sphere2_vs_fixed4": _paired_stats(
            [r["mean_bpb"] for r in sp_runs],
            [r["mean_bpb"] for r in results["arms"]["fixed_byte4"]["runs"]],
        ),
        "sphere2_vs_blt": _paired_stats(
            [r["mean_bpb"] for r in sp_runs],
            [r["mean_bpb"] for r in results["arms"]["blt_entropy"]["runs"]],
        ),
        "sphere2_vs_bpe": _paired_stats(
            [r["mean_bpb"] for r in sp_runs],
            [r["mean_bpb"] for r in results["arms"]["bpe_std"]["runs"]],
        ),
    }
    beats_hnet = cmp_h8b["sphere2_vs_hnet_n0"]["z"] <= -2.0 and cmp_h8b["sphere2_vs_hnet_n0"]["mean_diff"] < 0.0
    beats_fixed = cmp_h8b["sphere2_vs_fixed4"]["z"] <= -2.0 and cmp_h8b["sphere2_vs_fixed4"]["mean_diff"] < 0.0
    beats_bpe = cmp_h8b["sphere2_vs_bpe"]["rel_pct"] <= -2.0 and cmp_h8b["sphere2_vs_bpe"]["z"] <= -2.0
    if beats_hnet and beats_fixed and beats_bpe:
        verdict_b = "CONFIRMED"
    elif beats_fixed and not beats_hnet:
        verdict_b = "FALSIFIED_N0_HNET_EQUIV"
    else:
        verdict_b = "FALSIFIED"
    cmp_h8b["verdict"] = verdict_b
    results["grading"] = cmp_h8b
    return results


# ---------------------------------------------------------------------------
# H8c Runner: Part 1 (Adaptive Loop), Part 2 (MTP-8 vs AR), Part 3 (Unconfounded nullmodem)
# ---------------------------------------------------------------------------


class H8cLoopedPatchLM(nn.Module):
    """Looped patch-level LM combining SafeHopfLoopCore + AdaptiveLoopPacer + pluggable byte-patch head."""

    def __init__(
        self,
        d_model: int,
        n_heads: int,
        head_kind: str = "markov_mtp8",
        patch_len: int = 4,
    ) -> None:
        super().__init__()
        self.d_model = d_model
        self.patch_len = patch_len
        self.head_kind = head_kind
        self.byte_emb = nn.Embedding(256, d_model)
        self.pacer = ops.AdaptiveLoopPacer(d_model=d_model, max_r=4, target_mean_r=2.0)
        self.core = ops.SafeHopfLoopCore(d_model=d_model, n_heads=n_heads, n_inner_layers=2, max_loops=4)
        self.primary_byte_head = ops.LocalARByteDecoder(
            d_model=d_model, d_dec=max(32, d_model // 2), n_heads=n_heads, block_size=patch_len
        )
        if head_kind == "markov_mtp8":
            self.mtp_head: nn.Module = ops.MarkovMTP8Head(d_model=d_model, block_size=8, markov_rank=max(32, d_model // 2))
        elif head_kind == "parallel_mtp8":
            self.mtp_head = ops.ParallelMTP8Head(d_model=d_model, block_size=8)
        elif head_kind == "local_ar":
            self.mtp_head = ops.LocalARByteDecoder(d_model=d_model, d_dec=max(32, d_model // 2), n_heads=n_heads, block_size=8)
        else:
            raise ValueError(f"unknown H8c head_kind: {head_kind!r}")

    def forward(
        self,
        byte_seq: torch.Tensor,
        pacing_mode: str = "adaptive",
        seed: int | None = None,
        unroll_mtp: bool = False,
    ) -> dict[str, Any]:
        b, seq_len = byte_seq.shape
        n_patches = seq_len // self.patch_len
        trimmed = byte_seq[:, : n_patches * self.patch_len].reshape(b, n_patches, self.patch_len)
        patch_x = ops.safe_l2_normalize(self.byte_emb(trimmed).mean(dim=2), dim=-1)
        prev_surp = torch.zeros((b, n_patches), dtype=patch_x.dtype, device=patch_x.device)
        if n_patches > 1:
            diffs = (trimmed[:, :-1, 1:].float() != trimmed[:, :-1, :-1].float()).float().mean(dim=-1)
            prev_surp[:, 1:] = diffs
        depths, ste_w, pace_loss = self.pacer(patch_x, prev_surp, mode=pacing_mode, seed=seed)
        h_exit, loop_diag = self.core.forward_with_depths(patch_x, depths, ste_weights=ste_w)

        if n_patches < 2:
            raise ValueError("need at least 2 patches")
        h_pred = h_exit[:, :-1, :].reshape(-1, self.d_model)
        tgt_next = trimmed[:, 1:, :].reshape(-1, self.patch_len)
        prim_logits = self.primary_byte_head(h_pred, target_bytes=tgt_next, unroll=False)
        prim_ce = F.cross_entropy(prim_logits.float().reshape(-1, 256), tgt_next.reshape(-1))

        pad_tgt = F.pad(tgt_next, (0, max(0, 8 - self.patch_len)), value=0)[:, :8]
        pad_mask = torch.zeros((pad_tgt.shape[0], 8), dtype=torch.float32, device=byte_seq.device)
        pad_mask[:, : min(8, self.patch_len)] = 1.0
        mtp_logits = self.mtp_head(h_pred, target_bytes=pad_tgt, unroll=unroll_mtp)
        mtp_loss_all = F.cross_entropy(mtp_logits.float().reshape(-1, 256), pad_tgt.reshape(-1), reduction="none").reshape_as(pad_mask)
        mtp_ce = (mtp_loss_all * pad_mask).sum() / pad_mask.sum().clamp_min(1.0)

        return {
            "primary_ce": prim_ce,
            "mtp_ce": mtp_ce,
            "pace_loss": pace_loss,
            "depths": depths,
            "loop_diag": loop_diag,
        }


def run_h8c_part3_nullmodem_bench(
    seed: int,
    steps: int,
    device: torch.device,
    n_samples: int = 256,
) -> dict[str, Any]:
    """Unconfounded H8c Part 3 wire-bit parity benchmark with frozen judge & counterfactual audit decoder."""
    seed_everything(seed)
    gen = torch.Generator(device="cpu")
    gen.manual_seed(seed)
    fields = torch.randint(0, 8, (n_samples, 4), generator=gen)
    cut = (n_samples * 3) // 4
    train_f, eval_f = fields[:cut], fields[cut:]

    def fmt_english_json(row: Sequence[int]) -> bytes:
        return json.dumps(
            {"action": int(row[0]), "zone": int(row[1]), "priority": int(row[2]), "gate": int(row[3])},
            separators=(",", ":"),
        ).encode("utf-8")

    def fmt_abios3(row: Sequence[int]) -> bytes:
        return f"@s a={int(row[0])} z={int(row[1])} p={int(row[2])} g={int(row[3])}".encode("utf-8")

    def fmt_binary_oracle(row: Sequence[int]) -> bytes:
        packed = (int(row[0]) << 9) | (int(row[1]) << 6) | (int(row[2]) << 3) | int(row[3])
        return packed.to_bytes(2, "big")

    d_lat = 32
    codec = ops.BlockE8SphereCodec(d_latent=d_lat).to(device)
    sender = nn.Linear(32, d_lat, bias=False).to(device)
    audit_decoder = nn.Linear(d_lat, 32).to(device)
    opt = torch.optim.AdamW(list(sender.parameters()) + list(audit_decoder.parameters()), lr=5e-2)

    def onehot_fields(f: torch.Tensor) -> torch.Tensor:
        return F.one_hot(f, num_classes=8).float().reshape(-1, 32).to(device)

    x_tr = onehot_fields(train_f)
    y_tr = train_f.to(device)
    n_train_steps = max(160, steps)
    for _ in range(n_train_steps):
        opt.zero_grad(set_to_none=True)
        z = ops.safe_l2_normalize(sender(x_tr), dim=-1)
        q_idx = codec.encode_indices(z)
        z_q = codec.decode_indices(q_idx)
        z_ste = z_q - z.detach() + z
        logits = audit_decoder(z_ste).reshape(-1, 4, 8)
        commit = F.mse_loss(z, z_q.detach())
        loss = F.cross_entropy(logits.reshape(-1, 8), y_tr.reshape(-1)) + 0.25 * commit
        loss.backward()
        opt.step()

    for p in list(sender.parameters()) + list(audit_decoder.parameters()):
        p.requires_grad_(False)
    sender.eval()
    audit_decoder.eval()

    x_ev = onehot_fields(eval_f)
    cell_verified = 0
    cell_wire_bits: list[int] = []
    cell_exact_acc = 0
    cell_field_hits = 0
    cf_edit_hits = 0
    json_bits: list[int] = []
    abios_bits: list[int] = []
    bin_bits: list[int] = []

    with torch.no_grad():
        for i in range(len(eval_f)):
            row = [int(v) for v in eval_f[i].tolist()]
            json_bits.append(len(fmt_english_json(row)) * 8)
            abios_bits.append(len(fmt_abios3(row)) * 8)
            bin_bits.append(len(fmt_binary_oracle(row)) * 8)

            z = ops.safe_l2_normalize(sender(x_ev[i : i + 1]), dim=-1).squeeze(0)
            wire = codec.pack_cell(z)
            cell_wire_bits.append(len(wire) * 8)
            z_rec = codec.unpack_cell(wire)
            cell_verified += 1
            pred = audit_decoder(z_rec.unsqueeze(0)).reshape(4, 8).argmax(dim=-1).cpu().tolist()
            cell_field_hits += sum(int(a == b) for a, b in zip(pred, row))
            cell_exact_acc += int(pred == row)

            row_cf = [(row[0] + 1) % 8, row[1], row[2], row[3]]
            x_cf = onehot_fields(torch.tensor([row_cf]))
            z_cf = ops.safe_l2_normalize(sender(x_cf), dim=-1).squeeze(0)
            z_cf_rec = codec.unpack_cell(codec.pack_cell(z_cf))
            pred_cf = audit_decoder(z_cf_rec.unsqueeze(0)).reshape(4, 8).argmax(dim=-1).cpu().tolist()
            cf_edit_hits += int(pred_cf[0] == row_cf[0])

    n_ev = len(eval_f)
    return {
        "seed": seed,
        "state_entropy_bits": 12.0,
        "n_eval": n_ev,
        "arms": {
            "english_json": {"mean_wire_bits": round(sum(json_bits) / n_ev, 2), "lossless_text_acc": 1.0},
            "abios_3": {"mean_wire_bits": round(sum(abios_bits) / n_ev, 2), "lossless_text_acc": 1.0},
            "direct_binary_oracle": {"mean_wire_bits": round(sum(bin_bits) / n_ev, 2), "lossless_acc": 1.0},
            "nullmodem_sphere_cell": {
                "payload_bits": codec.n_blocks * 8,
                "framing_and_hash_bits": (ops.NullModemCell.HASH_BYTES + 8) * 8,
                "total_wire_bits": round(sum(cell_wire_bits) / n_ev, 2),
                "hash_verified_fraction": round(cell_verified / n_ev, 6),
                "frozen_judge_field_acc": round(cell_field_hits / (4 * n_ev), 6),
                "frozen_judge_exact_acc": round(cell_exact_acc / n_ev, 6),
                "counterfactual_edit_acc": round(cf_edit_hits / n_ev, 6),
            },
        },
    }


def run_h8c_experiment(
    splits: dict[str, dict[str, bytes]],
    cfg: dict[str, Any],
    device: torch.device,
) -> dict[str, Any]:
    train_concat = b"\n".join(splits[d]["train"] for d in splits)
    eval_concat = b"\n".join(splits[d]["eval"] for d in splits)
    train_b = torch.tensor(list(train_concat), dtype=torch.long)
    eval_b = torch.tensor(list(eval_concat), dtype=torch.long)
    batch_size = int(cfg.get("batch_size", 1))
    use_bf16 = device.type == "cuda"
    amp_ctx = (lambda: torch.amp.autocast("cuda", dtype=torch.bfloat16)) if use_bf16 else nullcontext

    seq_b = (min(cfg["ctx_bytes"], int(train_b.numel()) - 2, int(eval_b.numel())) // 4) * 4
    ev_n_win = min(int(cfg.get("eval_windows", 16)), max(1, int(eval_b.numel()) // seq_b))
    ev_batch = eval_b[: ev_n_win * seq_b].reshape(ev_n_win, seq_b).to(device)

    part1_out: dict[str, Any] = {}
    for mode in ("adaptive", "uniform", "random"):
        runs: list[dict[str, Any]] = []
        for sd in cfg["seeds"]:
            seed_everything(sd)
            gen = torch.Generator(device="cpu")
            gen.manual_seed(sd * 71 + 3)
            model = H8cLoopedPatchLM(d_model=cfg["d_model"], n_heads=cfg["n_heads"], head_kind="markov_mtp8").to(device)
            opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=0.05)
            model.train()
            for step in range(cfg["steps"]):
                batch = _sample_batch(train_b, batch_size, seq_b - 1, gen).to(device, non_blocking=True)
                opt.zero_grad(set_to_none=True)
                with amp_ctx():
                    out = model(batch, pacing_mode=mode, seed=sd + step)
                    loss = out["primary_ce"] + 0.25 * out["mtp_ce"] + 0.1 * out["pace_loss"]
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
            model.eval()
            with torch.no_grad():
                ev_out = model(ev_batch, pacing_mode=mode, seed=sd)
                prim_bpb = float(ev_out["primary_ce"].item()) / math.log(2.0)
                mean_r = float(ev_out["depths"].float().mean().item())
                depth_hist = {
                    str(d): int((ev_out["depths"] == d).sum().item()) for d in (1, 2, 3, 4)
                }
            runs.append(
                {
                    "seed": sd,
                    "primary_bpb": round(prim_bpb, 6),
                    "exact_mean_r": round(mean_r, 6),
                    "depth_hist": depth_hist,
                    "loop_diag": ev_out["loop_diag"],
                }
            )
        part1_out[mode] = {
            "runs": runs,
            "mean_primary_bpb": round(sum(r["primary_bpb"] for r in runs) / len(runs), 6),
        }

    p1_vs_uni = _paired_stats(
        [r["primary_bpb"] for r in part1_out["adaptive"]["runs"]],
        [r["primary_bpb"] for r in part1_out["uniform"]["runs"]],
    )
    p1_vs_rnd = _paired_stats(
        [r["primary_bpb"] for r in part1_out["adaptive"]["runs"]],
        [r["primary_bpb"] for r in part1_out["random"]["runs"]],
    )
    p1_verdict = (
        "CONFIRMED"
        if (p1_vs_uni["rel_pct"] <= -2.0 and p1_vs_uni["z"] <= -2.0 and p1_vs_rnd["rel_pct"] <= -2.0 and p1_vs_rnd["z"] <= -2.0)
        else "FALSIFIED"
    )

    part2_out: dict[str, Any] = {}
    for head_kind in ("markov_mtp8", "parallel_mtp8", "local_ar"):
        runs_p2: list[dict[str, Any]] = []
        params_p2: dict[str, int] = {}
        for sd in cfg["seeds"]:
            seed_everything(sd)
            gen = torch.Generator(device="cpu")
            gen.manual_seed(sd * 71 + 17)
            model = H8cLoopedPatchLM(d_model=cfg["d_model"], n_heads=cfg["n_heads"], head_kind=head_kind).to(device)
            opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=0.05)
            model.train()
            for _ in range(cfg["steps"]):
                batch = _sample_batch(train_b, batch_size, seq_b - 1, gen).to(device, non_blocking=True)
                opt.zero_grad(set_to_none=True)
                with amp_ctx():
                    out = model(batch, pacing_mode="uniform", seed=sd)
                    loss = out["primary_ce"] + 0.5 * out["mtp_ce"]
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
            model.eval()
            with torch.no_grad():
                ev_tf = model(ev_batch, pacing_mode="uniform", seed=sd, unroll_mtp=False)
                ev_un = model(ev_batch, pacing_mode="uniform", seed=sd, unroll_mtp=True)
            runs_p2.append(
                {
                    "seed": sd,
                    "primary_bpb": round(float(ev_tf["primary_ce"].item()) / math.log(2.0), 6),
                    "mtp_bpb_tf": round(float(ev_tf["mtp_ce"].item()) / math.log(2.0), 6),
                    "mtp_bpb_unrolled": round(float(ev_un["mtp_ce"].item()) / math.log(2.0), 6),
                }
            )
            params_p2 = ops.count_model_params(model)
        part2_out[head_kind] = {
            "params": params_p2,
            "runs": runs_p2,
            "mean_primary_bpb": round(sum(r["primary_bpb"] for r in runs_p2) / len(runs_p2), 6),
            "mean_mtp_bpb_tf": round(sum(r["mtp_bpb_tf"] for r in runs_p2) / len(runs_p2), 6),
            "mean_mtp_bpb_unrolled": round(sum(r["mtp_bpb_unrolled"] for r in runs_p2) / len(runs_p2), 6),
        }

    p2_mk_vs_par_tf = _paired_stats(
        [r["mtp_bpb_tf"] for r in part2_out["markov_mtp8"]["runs"]],
        [r["mtp_bpb_tf"] for r in part2_out["parallel_mtp8"]["runs"]],
    )
    p2_mk_vs_ar_tf = _paired_stats(
        [r["mtp_bpb_tf"] for r in part2_out["markov_mtp8"]["runs"]],
        [r["mtp_bpb_tf"] for r in part2_out["local_ar"]["runs"]],
    )
    p2_verdict = (
        "CONFIRMED"
        if (p2_mk_vs_par_tf["rel_pct"] <= -5.0 and p2_mk_vs_par_tf["z"] <= -2.0)
        else ("PARTIAL" if p2_mk_vs_par_tf["mean_diff"] < 0.0 else "FALSIFIED")
    )

    p3_runs = [
        run_h8c_part3_nullmodem_bench(
            seed=sd,
            steps=max(160, cfg["steps"]),
            device=device,
            n_samples=int(cfg.get("p3_samples", 256)),
        )
        for sd in cfg["seeds"]
    ]
    # Keep flat single-seed shape for backward compatibility while also recording multi-seed runs
    p3_summary = dict(p3_runs[0])
    p3_summary["all_seed_runs"] = p3_runs
    nm_field_mean = sum(r["arms"]["nullmodem_sphere_cell"]["frozen_judge_field_acc"] for r in p3_runs) / len(p3_runs)
    nm_exact_mean = sum(r["arms"]["nullmodem_sphere_cell"]["frozen_judge_exact_acc"] for r in p3_runs) / len(p3_runs)
    nm_cf_mean = sum(r["arms"]["nullmodem_sphere_cell"]["counterfactual_edit_acc"] for r in p3_runs) / len(p3_runs)
    nm_total_bits = p3_runs[0]["arms"]["nullmodem_sphere_cell"]["total_wire_bits"]
    abios_bits = p3_runs[0]["arms"]["abios_3"]["mean_wire_bits"]
    p3_summary["mean_across_seeds"] = {
        "frozen_judge_field_acc": round(nm_field_mean, 6),
        "frozen_judge_exact_acc": round(nm_exact_mean, 6),
        "counterfactual_edit_acc": round(nm_cf_mean, 6),
        "payload_bits": p3_runs[0]["arms"]["nullmodem_sphere_cell"]["payload_bits"],
        "total_wire_bits": nm_total_bits,
        "abios3_wire_bits": abios_bits,
        "english_json_wire_bits": p3_runs[0]["arms"]["english_json"]["mean_wire_bits"],
        "direct_binary_oracle_bits": p3_runs[0]["arms"]["direct_binary_oracle"]["mean_wire_bits"],
    }
    # Honest Amendment-1 §6 wire-bit verdict: total_wire_bits includes 320-bit framing+SHA256!
    p3_verdict = (
        "CONFIRMED"
        if (nm_total_bits < abios_bits and nm_exact_mean >= 0.95 and nm_cf_mean >= 0.95)
        else (
            "PARTIAL"
            if (p3_runs[0]["arms"]["nullmodem_sphere_cell"]["payload_bits"] < abios_bits and nm_field_mean >= 0.95 and nm_cf_mean >= 0.95)
            else "FALSIFIED"
        )
    )

    return {
        "part1_adaptive_pacing": part1_out,
        "part2_mtp8_vs_ar": part2_out,
        "part3_nullmodem": p3_summary,
        "grading": {
            "part1_vs_uniform": p1_vs_uni,
            "part1_vs_random": p1_vs_rnd,
            "part1_verdict": p1_verdict,
            "part2_markov_vs_parallel_tf": p2_mk_vs_par_tf,
            "part2_markov_vs_local_ar_tf": p2_mk_vs_ar_tf,
            "part2_verdict": p2_verdict,
            "part3_verdict": p3_verdict,
        },
    }


# ---------------------------------------------------------------------------
# Protocol Presets & CLI
# ---------------------------------------------------------------------------


def build_preset(mode: str, seeds: list[int]) -> dict[str, Any]:
    if mode == "cpu-smoke":
        return {
            "mode": "cpu-smoke",
            "seeds": seeds,
            "max_bytes_per_domain": 4096,
            "h8a": {
                "vocab_size": 320,
                "d_model": 32,
                "n_layers": 2,
                "n_heads": 4,
                "d_a": 4,
                "d_b": 4,
                "seq_tok": 32,
                "ctx_bytes": 64,
                "stride_bytes": 64,
                "eval_windows": 8,
                "batch_size": 2,
                "steps": 4,
                "lr": 3e-3,
                "seeds": seeds,
            },
            "h8b": {
                "bpe_vocab_size": 320,
                "d_b": 24,
                "d_model": 32,
                "n_layers": 2,
                "n_heads": 4,
                "ctx_bytes": 64,
                "stride_bytes": 64,
                "eval_windows": 8,
                "batch_size": 2,
                "steps": 4,
                "lr": 3e-3,
                "seeds": seeds,
            },
            "h8c": {
                "d_model": 32,
                "n_heads": 4,
                "ctx_bytes": 64,
                "eval_windows": 4,
                "batch_size": 2,
                "steps": 4,
                "p3_samples": 256,
                "lr": 3e-3,
                "seeds": seeds,
            },
        }
    if mode == "gpu-full":
        return {
            "mode": "gpu-full",
            "seeds": seeds,
            "max_bytes_per_domain": 262_144,
            "h8a": {
                "vocab_size": 4096,
                "d_model": 384,
                "n_layers": 6,
                "n_heads": 6,
                "d_a": 16,
                "d_b": 16,
                "seq_tok": 256,
                "ctx_bytes": 512,
                "stride_bytes": 256,
                "eval_windows": 32,
                "batch_size": 16,
                "steps": 400,
                "lr": 1.5e-3,
                "seeds": seeds,
            },
            "h8b": {
                "bpe_vocab_size": 4096,
                "d_b": 96,
                "d_model": 256,
                "n_layers": 4,
                "n_heads": 4,
                "ctx_bytes": 512,
                "stride_bytes": 256,
                "eval_windows": 32,
                "batch_size": 16,
                "steps": 400,
                "lr": 1.5e-3,
                "seeds": seeds,
            },
            "h8c": {
                "d_model": 256,
                "n_heads": 4,
                "ctx_bytes": 512,
                "eval_windows": 32,
                "batch_size": 16,
                "steps": 350,
                "p3_samples": 1024,
                "lr": 1.5e-3,
                "seeds": seeds,
            },
        }
    raise ValueError(f"unsupported mode: {mode!r}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track S108 (PREREG-S108 + Amendment 1) train/eval harness")
    parser.add_argument("--mode", choices=("cpu-smoke", "gpu-full"), default="cpu-smoke")
    parser.add_argument("--track", choices=("all", "h8a", "h8b", "h8c"), default="all")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--seeds", default="42", help="Comma-separated integer seeds (e.g. 42,137,2026)")
    parser.add_argument("--out-dir", default=None, help="Directory to write locked protocol and JSON receipt")
    parser.add_argument("--no-local-caches", action="store_true", help="Force pure synthetic multi-domain corpus")
    args = parser.parse_args(argv)

    if args.device == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("--device cuda requested but CUDA is unavailable")
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")

    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    preset = build_preset(args.mode, seeds)
    splits, corpus_digests = load_multidomain_byte_splits(
        max_bytes_per_domain=preset["max_bytes_per_domain"],
        allow_local_caches=not args.no_local_caches,
        fail_closed=(args.mode == "gpu-full"),
    )

    protocol: dict[str, Any] = {
        "schema": "aletheia.track_s108.locked_protocol.v1",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "parent_preregistration_sha256": ops.PREREG_S108_SHA256,
        "amendment1_sha256": ops.AMENDMENT1_SHA256,
        "mode": args.mode,
        "track": args.track,
        "device": str(device),
        "weights_saved": 0,
        "corpus_sha256": corpus_digests,
        "corpus_byte_sizes": {
            dom: {"train_bytes": len(pair["train"]), "eval_bytes": len(pair["eval"])} for dom, pair in splits.items()
        },
        "preset": preset,
    }
    proto_bytes = (json.dumps(protocol, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    proto_sha = hashlib.sha256(proto_bytes).hexdigest()

    t0 = time.monotonic()
    out_results: dict[str, Any] = {}
    if args.track in ("all", "h8a"):
        out_results["h8a"] = run_h8a_experiment(splits, preset["h8a"], device)
    if args.track in ("all", "h8b"):
        out_results["h8b"] = run_h8b_experiment(splits, preset["h8b"], device)
    if args.track in ("all", "h8c"):
        out_results["h8c"] = run_h8c_experiment(splits, preset["h8c"], device)
    elapsed_s = round(time.monotonic() - t0, 3)

    payload: dict[str, Any] = {
        "schema": "aletheia.track_s108.results.v1",
        "protocol_sha256": proto_sha,
        "parent_preregistration_sha256": ops.PREREG_S108_SHA256,
        "amendment1_sha256": ops.AMENDMENT1_SHA256,
        "mode": args.mode,
        "device": str(device),
        "elapsed_s": elapsed_s,
        "weights_saved": 0,
        "results": out_results,
    }
    inner_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["result_sha256"] = hashlib.sha256(inner_bytes).hexdigest()

    if args.out_dir is not None:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        proto_path = out_dir / "s108_locked_protocol.json"
        res_path = out_dir / f"s108_{args.mode.replace('-', '_')}_results.json"
        proto_path.write_bytes(proto_bytes)
        os.chmod(proto_path, 0o600)
        res_bytes = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        res_path.write_bytes(res_bytes)
        os.chmod(res_path, 0o600)

    print(
        json.dumps(
            {
                "mode": args.mode,
                "track": args.track,
                "device": str(device),
                "elapsed_s": elapsed_s,
                "protocol_sha256": proto_sha,
                "result_sha256": payload["result_sha256"],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
