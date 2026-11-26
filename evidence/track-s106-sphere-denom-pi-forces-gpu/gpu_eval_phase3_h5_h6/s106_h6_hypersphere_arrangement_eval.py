#!/usr/bin/env python3
"""Track S106 Amendment 2 (PREREG-S106-AMENDMENT2-H6): 4D Hypersphere Foliation & Hopf-Fiber Arrangement.

H6a  S^3 depth-time foliation bit arrangement at matched 3.00 bpw mean (siliquant per-128 A_16):
     Polar-curvature (high bits where cos^2 psi_l is largest = entry/exit poles) vs Equatorial
     (high bits where sin^2 psi_l is largest) vs Flat (uniform 3.0). psi_l = (l + 1/2) pi / L.
     Tail fraction f in {1/3, 1/4} (+/-0.5 bpw tails) locked on Qwen2.5-0.5B ONLY.
H6b  Part 1: Hopf-fiber quantizer EQ(S^2) base x uniform S^1 fiber (K = 256, LUT-free factored
     encode) vs direct EQ(S^3) (Leopardi 8c) directional SNR on SphereMap'd held-out weights,
     plus exact O(1) fiber-phase equivariance check. (K_b, K_f) split locked on Gaussian only.
     Part 2: zero-cost MLP intermediate-channel reordering (down_proj columns; gate/up rows are
     quantized row-independently so their error is permutation-invariant) by data-flow order
     (descending D_flow^noise) vs native vs seeded random permutation, per-128 A_16 @ 2.0 & 3.0.
H6c  ~10.7M-param byte-level micro-LM pilot: Hopf/SU(2)-coupled S^3 residual update vs standard
     flat residual, identical params/tokens/optimizer/seeds; val bits/byte + 3-bit PTQ KL.
     ZERO weights saved (WEIGHTS=0).

All rules/constants are written to h6_locked_protocol.json before any model is loaded.
"""

from __future__ import annotations

import datetime
import gc
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

_HERE = Path(__file__).resolve().parent
_TRACK = _HERE.parent
_GPU_EVAL = _TRACK / "gpu_eval"
for _p in (str(_GPU_EVAL), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import s106_quant_ops as ops  # noqa: E402
import s106_phase2_blind_gauntlet as p2  # noqa: E402
import s106_h5_flow_sphere_eval as h5  # noqa: E402

AMEND2_SHA_PREFIX = "b676cc556c9bbfa0"
EVAL_SEED = 2026112508
HELD_OUT = ("HuggingFaceTB/SmolLM2-360M", "Qwen/Qwen2.5-1.5B", "Qwen/Qwen2.5-3B")
H6A_FRACTIONS = (1.0 / 3.0, 1.0 / 4.0)
H6B_SPLITS = ((16, 16), (32, 8), (64, 4))
MICRO = {"d_model": 384, "n_layers": 6, "n_heads": 6, "mlp_mult": 4, "seq": 256, "batch": 16,
         "steps": 800, "lr": 1e-3, "warmup": 50, "wd": 0.1, "seeds": [11, 12], "eval_windows": 64}

LOCKED_PROTOCOL: dict[str, Any] = {
    "schema": "aletheia.track_s106.h6_locked_protocol.v1",
    "parent_preregistration_sha256": ops.PREREG_SHA256,
    "amendment2_sha256_prefix": AMEND2_SHA_PREFIX,
    "held_out_models": list(HELD_OUT),
    "eval_seed": EVAL_SEED,
    "h6a_quantizer": "siliquant per-128 A16 (bounds 2.5/3.0/3.5 bpw from exact theta series)",
    "h6a_psi": "psi_l = (l + 1/2) pi / L",
    "h6a_polar": "top round(f L) layers by cos^2 psi -> 3.5 bpw, bottom round(f L) -> 2.5 bpw, rest 3.0",
    "h6a_equatorial": "top round(f L) layers by sin^2 psi -> 3.5 bpw, bottom round(f L) -> 2.5 bpw, rest 3.0",
    "h6a_fraction_candidates": list(H6A_FRACTIONS),
    "h6a_fraction_lock": "polar fraction with lower mean(Wiki,Py) KL on Qwen/Qwen2.5-0.5B pilot",
    "h6a_pass": "polar beats flat by >= 10% rel KL, z >= 2, both corpora, on >= 2/3 held-out models",
    "h6a_kill": "fails pass OR equatorial mean KL < polar mean KL on >= 2/3 held-out models",
    "h6b1_splits": [list(s) for s in H6B_SPLITS],
    "h6b1_split_lock": "highest Gaussian OOS mean cosine (factored encode)",
    "h6b1_metric": "directional SNR = -10 log10(2 (1 - mean cos)) over all 4-blocks of SphereMap'd block matrices",
    "h6b1_pass": "Hopf factored-encode dir SNR within 0.15 dB of EQ(S^3) Leopardi-8c on >= 2/3 models AND >= 99.9% exact fiber-index shift under e^{i 2 pi m / K_f} rotation",
    "h6b2_order": "down_proj input channels sorted by descending D_flow^noise (random-token excitation)",
    "h6b2_null": "SHA-256-seeded random permutation",
    "h6b2_pass_rate": "flow order beats native AND random by >= 5% rel KL, z >= 2, both corpora",
    "h6b2_verdict": "CONFIRMED if pass_rate holds on >= 2/3 models at BOTH 2.0 and 3.0; PARTIAL if at exactly one rate; else FALSIFIED",
    "h6c_config": MICRO,
    "h6c_train_text": "WikiText-2 validation (bytes)",
    "h6c_eval_text": "WikiText-2 test (bytes), first eval_windows non-overlapping windows",
    "h6c_hopf_update": "per 4-block: h <- exp(tanh(D0)) * (normalize(1, D1, D2, D3) (x) h), quaternion left product; zero extra params",
    "h6c_pass": "CONFIRMED if (a) both Hopf seeds have lower val bits/byte than both flat seeds OR (b) Hopf mean PTQ KL <= 0.85 x flat mean AND max Hopf seed PTQ KL < min flat seed PTQ KL; else FALSIFIED",
}


# ---------------------------------------------------------------------------
# H6b Part 1: Hopf-fiber factored quantizer on S^3
# ---------------------------------------------------------------------------
def _eq_s2_rings(k_b: int) -> list[int]:
    n_r = max(1, int(round(math.sqrt(k_b * math.pi) / 2.0)))
    raw = [math.sin((r + 0.5) * math.pi / n_r) for r in range(n_r)]
    s = sum(raw)
    cnt = [max(1, int(round(k_b * w / s))) for w in raw]
    while sum(cnt) != k_b:
        diff = k_b - sum(cnt)
        idx = n_r // 2 if diff > 0 else max(range(n_r), key=lambda k: cnt[k])
        cnt[idx] += 1 if diff > 0 else -1
    return cnt


def hopf_encode_decode(u: torch.Tensor, k_b: int, k_f: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Factored Hopf encode of unit 4-vectors u -> (base_idx, fiber_idx, decoded unit vector)."""
    rings = _eq_s2_rings(k_b)
    cum = [0]
    for c in rings:
        cum.append(cum[-1] + c)
    dev = u.device
    rings_t = torch.tensor(rings, device=dev, dtype=torch.int64)
    cum_t = torch.tensor(cum, device=dev, dtype=torch.int64)
    a, b, c, d = u[:, 0], u[:, 1], u[:, 2], u[:, 3]
    r1sq = a * a + b * b
    r2sq = c * c + d * d
    zc = (r1sq - r2sq).clamp(-1.0, 1.0)  # cos(theta) on the S^2 base
    al1 = torch.atan2(b, a)
    al2 = torch.atan2(d, c)
    phi = torch.remainder(al1 - al2 + math.pi, 2.0 * math.pi) - math.pi
    # Base: equal-area z bands (Archimedes), ring index from cumulative cell counts
    pos = (zc + 1.0) * 0.5 * k_b
    ring = torch.searchsorted(cum_t[1:].to(torch.float32), pos.contiguous(), right=True).clamp(0, len(rings) - 1)
    nr = rings_t[ring]
    off = (ring % 2).to(torch.float32) * (math.pi / nr.to(torch.float32))
    jb = torch.floor(torch.remainder(phi + math.pi - off, 2.0 * math.pi) / (2.0 * math.pi / nr.to(torch.float32))).to(torch.int64)
    jb = torch.minimum(jb, nr - 1)
    base_idx = cum_t[ring] + jb
    phi_c = -math.pi + off + (jb.to(torch.float32) + 0.5) * (2.0 * math.pi / nr.to(torch.float32))
    # Fiber coordinate measured against the branch of phi nearest the decoded base longitude, so the
    # decoder (a function of indices only) never crosses the +/-pi cut: f = alpha1 - phi_t / 2 (mod 2 pi).
    phi_t = phi_c + (torch.remainder(phi - phi_c + math.pi, 2.0 * math.pi) - math.pi)
    fib_ang = torch.remainder(al1 - 0.5 * phi_t, 2.0 * math.pi)
    fib_idx = torch.floor(fib_ang / (2.0 * math.pi / k_f)).to(torch.int64).clamp(0, k_f - 1)
    # Decode cell centres
    z0 = -1.0 + 2.0 * cum_t[ring].to(torch.float32) / k_b
    z1 = -1.0 + 2.0 * cum_t[ring + 1].to(torch.float32) / k_b
    zm = 0.5 * (z0 + z1)
    f_c = (fib_idx.to(torch.float32) + 0.5) * (2.0 * math.pi / k_f)
    a1 = f_c + 0.5 * phi_c
    a2 = f_c - 0.5 * phi_c
    m1 = torch.sqrt(((1.0 + zm) * 0.5).clamp_min(0.0))
    m2 = torch.sqrt(((1.0 - zm) * 0.5).clamp_min(0.0))
    dec = torch.stack([m1 * torch.cos(a1), m1 * torch.sin(a1), m2 * torch.cos(a2), m2 * torch.sin(a2)], dim=1)
    return base_idx, fib_idx, dec


def _rotate_fiber(u: torch.Tensor, delta: float) -> torch.Tensor:
    cs, sn = math.cos(delta), math.sin(delta)
    a, b, c, d = u[:, 0], u[:, 1], u[:, 2], u[:, 3]
    return torch.stack([a * cs - b * sn, a * sn + b * cs, c * cs - d * sn, c * sn + d * cs], dim=1)


def _dir_snr(mean_cos: float) -> float:
    return -10.0 * math.log10(max(1e-12, 2.0 * (1.0 - mean_cos)))


# ---------------------------------------------------------------------------
# H6c: micro-LM
# ---------------------------------------------------------------------------
def _quat_left(p: torch.Tensor, q: torch.Tensor) -> torch.Tensor:
    a1, b1, c1, d1 = p.unbind(-1)
    a2, b2, c2, d2 = q.unbind(-1)
    return torch.stack([
        a1 * a2 - b1 * b2 - c1 * c2 - d1 * d2,
        a1 * b2 + b1 * a2 + c1 * d2 - d1 * c2,
        a1 * c2 - b1 * d2 + c1 * a2 + d1 * b2,
        a1 * d2 + b1 * c2 - c1 * b2 + d1 * a2,
    ], dim=-1)


class _RMS(nn.Module):
    def __init__(self, d: int) -> None:
        super().__init__()
        self.w = nn.Parameter(torch.ones(d))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.rsqrt((x * x).mean(-1, keepdim=True) + 1e-6) * self.w


class _Block(nn.Module):
    def __init__(self, d: int, h: int, mult: int, mode: str) -> None:
        super().__init__()
        self.h, self.mode = h, mode
        self.n1, self.n2 = _RMS(d), _RMS(d)
        self.qkv = nn.Linear(d, 3 * d, bias=False)
        self.o = nn.Linear(d, d, bias=False)
        self.up = nn.Linear(d, mult * d, bias=False)
        self.down = nn.Linear(mult * d, d, bias=False)

    def _res(self, x: torch.Tensor, delta: torch.Tensor) -> torch.Tensor:
        if self.mode == "flat":
            return x + delta
        sh = x.shape
        xq = x.reshape(*sh[:-1], sh[-1] // 4, 4)
        dq = delta.reshape(*sh[:-1], sh[-1] // 4, 4)
        one = torch.ones_like(dq[..., :1])
        u = torch.cat([one, dq[..., 1:]], dim=-1)
        u = u / torch.linalg.vector_norm(u, dim=-1, keepdim=True)
        g = torch.exp(torch.tanh(dq[..., :1]))
        return (g * _quat_left(u, xq)).reshape(sh)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, t, d = x.shape
        q, k, v = self.qkv(self.n1(x)).split(d, dim=-1)
        q = q.view(b, t, self.h, d // self.h).transpose(1, 2)
        k = k.view(b, t, self.h, d // self.h).transpose(1, 2)
        v = v.view(b, t, self.h, d // self.h).transpose(1, 2)
        a = F.scaled_dot_product_attention(q, k, v, is_causal=True).transpose(1, 2).reshape(b, t, d)
        x = self._res(x, self.o(a))
        x = self._res(x, self.down(F.gelu(self.up(self.n2(x)))))
        return x


class _MicroLM(nn.Module):
    def __init__(self, mode: str) -> None:
        super().__init__()
        d = MICRO["d_model"]
        self.emb = nn.Embedding(256, d)
        self.pos = nn.Parameter(torch.zeros(MICRO["seq"], d))
        self.blocks = nn.ModuleList([_Block(d, MICRO["n_heads"], MICRO["mlp_mult"], mode) for _ in range(MICRO["n_layers"])])
        self.nf = _RMS(d)
        nn.init.normal_(self.emb.weight, std=0.02)
        nn.init.normal_(self.pos, std=0.01)

    def forward(self, idx: torch.Tensor) -> torch.Tensor:
        x = self.emb(idx) + self.pos[: idx.shape[1]]
        for blk in self.blocks:
            x = blk(x)
        return self.nf(x) @ self.emb.weight.T


def _train_eval_micro(mode: str, seed: int, train_b: torch.Tensor, eval_b: torch.Tensor, device: torch.device) -> dict[str, Any]:
    torch.manual_seed(seed)
    model = _MicroLM(mode).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=MICRO["lr"], betas=(0.9, 0.95), weight_decay=MICRO["wd"])
    gen = torch.Generator().manual_seed(seed)
    seq, bs = MICRO["seq"], MICRO["batch"]
    t0 = time.monotonic()
    model.train()
    for step in range(MICRO["steps"]):
        lr = MICRO["lr"] * min(1.0, (step + 1) / MICRO["warmup"]) * 0.5 * (1.0 + math.cos(math.pi * step / MICRO["steps"]))
        for gp in opt.param_groups:
            gp["lr"] = lr
        st = torch.randint(0, train_b.numel() - seq - 1, (bs,), generator=gen)
        xb = torch.stack([train_b[s:s + seq + 1] for s in st.tolist()]).to(device)
        with torch.autocast("cuda", dtype=torch.bfloat16):
            logits = model(xb[:, :-1])
        loss = F.cross_entropy(logits.float().reshape(-1, 256), xb[:, 1:].reshape(-1))
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
    train_s = time.monotonic() - t0
    model.eval()
    nw = MICRO["eval_windows"]
    ev = eval_b[: nw * (seq + 1)].view(nw, seq + 1).to(device)

    @torch.no_grad()
    def _logp(m: nn.Module) -> torch.Tensor:
        return F.log_softmax(m(ev[:, :-1]).float(), dim=-1)

    lp_fp = _logp(model)
    nll = float(F.nll_loss(lp_fp.reshape(-1, 256), ev[:, 1:].reshape(-1)).item())
    syn = oob = 0
    with torch.no_grad():
        for mod in model.modules():
            if isinstance(mod, nn.Linear):
                wq, s = ops.quant_per_block_ball_matrix(mod.weight.detach().float(), "3.0", "A16", 128, row_chunk=512)
                syn += int(s["syndrome_errors"])
                oob += int(s["oob_groups"])
                mod.weight.copy_(wq)
    lp_q = _logp(model)
    kl = float((lp_fp.exp() * (lp_fp - lp_q)).sum(-1).mean().item())
    nll_q = float(F.nll_loss(lp_q.reshape(-1, 256), ev[:, 1:].reshape(-1)).item())
    del model, opt
    torch.cuda.empty_cache()
    return {"mode": mode, "seed": seed, "n_params": n_params, "final_train_loss": round(float(loss.item()), 6),
            "val_bits_per_byte": round(nll / math.log(2.0), 6), "ptq3_bits_per_byte": round(nll_q / math.log(2.0), 6),
            "ptq3_kl_nats": round(kl, 8), "ptq_syndrome_errors": syn, "ptq_oob_groups": oob, "train_seconds": round(train_s, 2)}


# ---------------------------------------------------------------------------
# Shared model-level arm runner
# ---------------------------------------------------------------------------
class _Ctx:
    def __init__(self, repo_id: str, local_dir: str, wt_test: str, py_test: str, device: torch.device) -> None:
        self.repo_id = repo_id
        self.device = device
        tok = p2.AutoTokenizer.from_pretrained(local_dir, local_files_only=True)
        self.model = p2.AutoModelForCausalLM.from_pretrained(local_dir, local_files_only=True, dtype=torch.bfloat16).to(device)
        self.model.eval()
        self.linears = p2._collect_block_linears(self.model)
        self.n_layers = max(p2._layer_idx(n) for n, _ in self.linears) + 1
        self.snaps = p2._snapshot_non_block_tensors(self.model)
        self.orig = {n: m.weight.detach().cpu().clone() for n, m in self.linears}
        self.tot_w = sum(int(m.weight.numel()) for _, m in self.linears)
        self.wt = p2._tokenize_chunks(tok, wt_test, p2.N_EVAL_CHUNKS, p2.SEQ_LEN)
        self.py = p2._tokenize_chunks(tok, py_test, p2.N_EVAL_CHUNKS, p2.SEQ_LEN)
        self.ref_wt, self.ppl_wt, _ = p2._collect_reference_logits(self.model, self.wt, device)
        self.ref_py, self.ppl_py, _ = p2._collect_reference_logits(self.model, self.py, device)
        gen = torch.Generator().manual_seed(EVAL_SEED)
        self.noise = torch.randint(0, int(self.model.config.vocab_size), (h5.N_FLOW_CHUNKS, p2.SEQ_LEN), generator=gen)

    def run(self, arm: str, fn) -> dict[str, Any]:
        tot_err = tot_sig = bpw_num = 0.0
        syn = oob = 0
        with torch.no_grad():
            for ln, mod in self.linears:
                wf = self.orig[ln].to(device=self.device, dtype=torch.float32)
                wq, st = fn(ln, wf)
                dw = wq - wf
                tot_err += float((dw * dw).sum().item())
                tot_sig += float((wf * wf).sum().item())
                bpw_num += float(st["exact_bpw"]) * float(wf.numel())
                syn += int(st["syndrome_errors"])
                oob += int(st["oob_groups"])
                mod.weight.copy_(wq.to(torch.bfloat16))
                del wf, wq, dw
        torch.cuda.empty_cache()
        nb = p2._count_non_block_diffs(self.model, self.snaps)
        wt_s = p2._score_against_reference(self.model, self.wt, self.ref_wt, self.device)
        py_s = p2._score_against_reference(self.model, self.py, self.ref_py, self.device)
        snr = 10.0 * math.log10(max(tot_sig, 1e-30) / max(tot_err, 1e-30))
        row = {"arm": arm, "exact_bpw": round(bpw_num / float(self.tot_w), 5), "weight_snr_db": round(snr, 4),
               "syndrome_errors": syn, "oob_groups": oob, "non_block_diffs": nb, "wikitext2": wt_s, "python": py_s}
        print(f"  [{arm:26s}] bpw={row['exact_bpw']:.4f} SNR={snr:6.3f}dB WikiKL={wt_s['mean_kl']:.5f}±{wt_s['se_kl']:.5f} "
              f"PyKL={py_s['mean_kl']:.5f}±{py_s['se_kl']:.5f} syn={syn} oob={oob} nb={nb}", flush=True)
        return row

    def close(self) -> None:
        self.linears.clear()
        del self.linears, self.model, self.ref_wt, self.ref_py, self.orig, self.wt, self.py, self.noise, self.snaps
        gc.collect()
        torch.cuda.empty_cache()


def _schedule(n_layers: int, frac: float, kind: str) -> dict[str, str]:
    psi = [(l + 0.5) * math.pi / n_layers for l in range(n_layers)]
    key = [math.cos(p) ** 2 for p in psi] if kind == "polar" else [math.sin(p) ** 2 for p in psi]
    k = int(round(frac * n_layers))
    order = sorted(range(n_layers), key=lambda l: (-key[l], l))
    hi, lo = set(order[:k]), set(order[n_layers - k:])
    return {str(l): ("3.5" if l in hi else ("2.5" if l in lo else "3.0")) for l in range(n_layers)}


def _p128_sched(sched: dict[str, str]):
    return lambda n, wf: ops.quant_per_block_ball_matrix(wf, sched[str(p2._layer_idx(n))], "A16", 128, row_chunk=512)


def _avg(r: dict[str, Any]) -> float:
    return 0.5 * (float(r["wikitext2"]["mean_kl"]) + float(r["python"]["mean_kl"]))


def main() -> int:
    t_start = time.monotonic()
    torch.manual_seed(EVAL_SEED)
    device = torch.device("cuda:0")
    notes = _TRACK.parent / "notes" / "sphere_pi_forces_2026_11_25"
    prereg_sha = hashlib.sha256((notes / "PREREG_SPHERE_PI_FORCES_V1.md").read_bytes()).hexdigest()
    amend_sha = hashlib.sha256((notes / "PREREG_SPHERE_PI_FORCES_AMENDMENT2_H6.md").read_bytes()).hexdigest()
    if prereg_sha != ops.PREREG_SHA256 or not amend_sha.startswith(AMEND2_SHA_PREFIX):
        raise RuntimeError(f"Preregistration lock mismatch: {prereg_sha} / {amend_sha}")
    for k, v in h5.EXTRA_PER_BLOCK.items():
        ops.PER_BLOCK_BOUNDS[k] = v

    proto = dict(LOCKED_PROTOCOL)
    proto["amendment2_sha256"] = amend_sha
    proto["locked_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    proto_bytes = (json.dumps(proto, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    proto_path = _HERE / "h6_locked_protocol.json"
    proto_path.write_bytes(proto_bytes)
    os.chmod(proto_path, 0o600)
    proto_sha = hashlib.sha256(proto_bytes).hexdigest()
    print(f"H6 PROTOCOL LOCKED {proto['locked_utc']} sha256={proto_sha}", flush=True)

    cache = Path.home() / ".cache" / "huggingface"
    pins = json.loads((cache / "s49b_eval" / "pins.json").read_text(encoding="utf-8"))
    q15 = json.loads((cache / "s60_eval" / "qwen15b_pin.json").read_text(encoding="utf-8"))
    q3 = json.loads((cache / "s63_eval" / "qwen3b_pin.json").read_text(encoding="utf-8"))
    wt_test = (cache / "s49b_eval" / "wikitext2_test.txt").read_text(encoding="utf-8")
    wt_val = (cache / "s49b_eval" / "wikitext2_val.txt").read_text(encoding="utf-8")
    py_test, py_sha = p2._load_python_eval_text()
    smi_pre = p2._query_nvidia_smi()

    # ---- H6b Part 1 split lock on Gaussian (no model) ----
    rng = np.random.default_rng(20261125)
    xg = torch.tensor(rng.standard_normal((40000, 4)), dtype=torch.float32, device=device)
    ug = xg / torch.linalg.vector_norm(xg, dim=1, keepdim=True)
    split_scores = {}
    for kb, kf in H6B_SPLITS:
        _, _, dec = hopf_encode_decode(ug, kb, kf)
        split_scores[f"{kb}x{kf}"] = round(float((ug * dec).sum(1).mean().item()), 6)
    best_split = max(H6B_SPLITS, key=lambda s: split_scores[f"{s[0]}x{s[1]}"])
    cb_eq = ops.build_eq_s3_leopardi().to(device)
    eq_g = round(float((ug @ cb_eq.T).max(1).values.mean().item()), 6)
    print(f"  [H6b-1 Gaussian lock] splits={split_scores} -> {best_split}; EQ(S^3) mean_cos={eq_g}", flush=True)

    # ---- H6a fraction lock on Qwen2.5-0.5B ONLY ----
    pilot_ctx = _Ctx("Qwen/Qwen2.5-0.5B", pins["Qwen/Qwen2.5-0.5B"]["local_dir"], wt_test, py_test, device)
    pilot_arms = {}
    for fr in H6A_FRACTIONS:
        tag = f"polar_f{int(round(1 / fr))}"
        pilot_arms[tag] = pilot_ctx.run(f"pilot_{tag}", _p128_sched(_schedule(pilot_ctx.n_layers, fr, "polar")))
    pilot_ctx.close()
    del pilot_ctx
    gc.collect()
    torch.cuda.empty_cache()
    locked_frac = min(H6A_FRACTIONS, key=lambda f: _avg(pilot_arms[f"polar_f{int(round(1 / f))}"]))
    print(f"  [H6a pilot lock on Qwen2.5-0.5B] fraction=1/{int(round(1 / locked_frac))}", flush=True)

    models: dict[str, Any] = {}
    for rid, ldir in ((HELD_OUT[0], pins[HELD_OUT[0]]["local_dir"]), (HELD_OUT[1], q15["local_dir"]), (HELD_OUT[2], q3["local_dir"])):
        print(f"\n{'=' * 80}\nH6 BLIND HELD-OUT MODEL: {rid}\n{'=' * 80}", flush=True)
        t0 = time.monotonic()
        ctx = _Ctx(rid, ldir, wt_test, py_test, device)
        arms: dict[str, Any] = {}
        arms["flat_3b"] = ctx.run("flat_3b", lambda _n, wf: ops.quant_per_block_ball_matrix(wf, "3.0", "A16", 128, row_chunk=512))
        arms["polar_3b"] = ctx.run("polar_3b", _p128_sched(_schedule(ctx.n_layers, locked_frac, "polar")))
        arms["equatorial_3b"] = ctx.run("equatorial_3b", _p128_sched(_schedule(ctx.n_layers, locked_frac, "equatorial")))

        # H6b Part 2: data-flow channel order on down_proj input
        dfl = h5._capture_dflow(ctx.model, ctx.linears, ctx.noise, device)
        perms_flow = {n: torch.argsort(dfl[n], descending=True, stable=True) for n, _ in ctx.linears if n.endswith("mlp.down_proj")}
        perms_rand = {n: h5._null_perm(dfl[n].numel(), f"{rid}:{n}:h6b_rand") for n in perms_flow}

        def _perm_q(perms: dict[str, torch.Tensor], bpw: str):
            def _fn(n: str, wf: torch.Tensor):
                if n not in perms:
                    return ops.quant_per_block_ball_matrix(wf, bpw, "A16", 128, row_chunk=512)
                pm = perms[n].to(wf.device)
                inv = torch.empty_like(pm)
                inv[pm] = torch.arange(pm.numel(), device=wf.device)
                wq, st = ops.quant_per_block_ball_matrix(wf[:, pm].contiguous(), bpw, "A16", 128, row_chunk=512)
                return wq[:, inv].contiguous(), st
            return _fn

        arms["native_2b"] = ctx.run("native_2b", lambda _n, wf: ops.quant_per_block_ball_matrix(wf, "2.0", "A16", 128, row_chunk=512))
        for bpw, tag in (("2.0", "2b"), ("3.0", "3b")):
            arms[f"floworder_{tag}"] = ctx.run(f"floworder_{tag}", _perm_q(perms_flow, bpw))
            arms[f"randorder_{tag}"] = ctx.run(f"randorder_{tag}", _perm_q(perms_rand, bpw))

        # H6b Part 1: directional SNR + equivariance on SphereMap'd 4-blocks
        cos_eq = cos_hopf = 0.0
        n_blk = 0
        eq_shift_ok = eq_shift_tot = 0
        kb, kf = best_split
        with torch.no_grad():
            for ln, _ in ctx.linears:
                wf = ctx.orig[ln].to(device=device, dtype=torch.float32)
                w_sp, _, _, _, _, _ = ops.spheremap_forward(wf, block_size=64)
                z = w_sp.reshape(-1, 4)
                u = z / torch.linalg.vector_norm(z, dim=1, keepdim=True).clamp_min(1e-12)
                for i0 in range(0, u.shape[0], 1 << 20):
                    uc = u[i0:i0 + (1 << 20)]
                    cos_eq += float((uc @ cb_eq.T).max(1).values.double().sum().item())
                    bi, fi, dec = hopf_encode_decode(uc, kb, kf)
                    cos_hopf += float((uc * dec).sum(1).double().sum().item())
                    n_blk += uc.shape[0]
                    if eq_shift_tot < 2_000_000:
                        bi2, fi2, _ = hopf_encode_decode(_rotate_fiber(uc, 2.0 * math.pi * 3 / kf), kb, kf)
                        eq_shift_ok += int(((bi2 == bi) & (fi2 == (fi + 3) % kf)).sum().item())
                        eq_shift_tot += uc.shape[0]
                del wf, w_sp, z, u
        snr_eq = _dir_snr(cos_eq / n_blk)
        snr_hopf = _dir_snr(cos_hopf / n_blk)
        h6b1 = {"split": f"{kb}x{kf}", "eq_s3_dir_snr_db": round(snr_eq, 4), "hopf_dir_snr_db": round(snr_hopf, 4),
                "gap_db": round(snr_hopf - snr_eq, 4), "equivariance_exact_frac": round(eq_shift_ok / max(eq_shift_tot, 1), 6),
                "blocks": n_blk}
        print(f"  [H6b-1] {h6b1}", flush=True)
        models[rid] = {"repo_id": rid, "num_hidden_layers": ctx.n_layers, "total_block_weights": ctx.tot_w,
                       "reference_bf16": {"wikitext2_ppl": round(ctx.ppl_wt, 6), "python_ppl": round(ctx.ppl_py, 6)},
                       "polar_schedule": _schedule(ctx.n_layers, locked_frac, "polar"),
                       "equatorial_schedule": _schedule(ctx.n_layers, locked_frac, "equatorial"),
                       "arms": arms, "h6b_part1": h6b1, "model_elapsed_seconds": round(time.monotonic() - t0, 3)}
        ctx.close()
        del ctx, dfl, perms_flow, perms_rand
        gc.collect()
        torch.cuda.empty_cache()

    # ---- H6c micro-LM pilot ----
    train_b = torch.tensor(list(wt_val.encode("utf-8")), dtype=torch.long)
    eval_b = torch.tensor(list(wt_test.encode("utf-8")), dtype=torch.long)
    h6c_runs = []
    for mode in ("flat", "hopf"):
        for sd in MICRO["seeds"]:
            r = _train_eval_micro(mode, sd, train_b, eval_b, device)
            print(f"  [H6c] {r}", flush=True)
            h6c_runs.append(r)

    # ---- Grading (literal locked rules) ----
    def sig(a, b, th):
        return h5._sig_better(a, b, th)

    h6a_pass = sum(int(sig(models[m]["arms"]["polar_3b"], models[m]["arms"]["flat_3b"], 0.10)) for m in HELD_OUT)
    eq_beats = sum(int(_avg(models[m]["arms"]["equatorial_3b"]) < _avg(models[m]["arms"]["polar_3b"])) for m in HELD_OUT)
    h6a = "CONFIRMED" if (h6a_pass >= 2 and eq_beats < 2) else "FALSIFIED"

    b1_pass = sum(int(models[m]["h6b_part1"]["gap_db"] >= -0.15) for m in HELD_OUT)
    b1_eqv = all(models[m]["h6b_part1"]["equivariance_exact_frac"] >= 0.999 for m in HELD_OUT)
    h6b1 = "CONFIRMED" if (b1_pass >= 2 and b1_eqv) else "FALSIFIED"

    rate_ok = {}
    for tag, native in (("2b", "native_2b"), ("3b", "flat_3b")):
        cnt = 0
        for m in HELD_OUT:
            a = models[m]["arms"]
            cnt += int(sig(a[f"floworder_{tag}"], a[native], 0.05) and sig(a[f"floworder_{tag}"], a[f"randorder_{tag}"], 0.05))
        rate_ok[tag] = cnt >= 2
    nrates = sum(int(v) for v in rate_ok.values())
    h6b2 = "CONFIRMED" if nrates == 2 else ("PARTIAL" if nrates == 1 else "FALSIFIED")

    fl = [r for r in h6c_runs if r["mode"] == "flat"]
    hp = [r for r in h6c_runs if r["mode"] == "hopf"]
    c_a = max(r["val_bits_per_byte"] for r in hp) < min(r["val_bits_per_byte"] for r in fl)
    c_b = (np.mean([r["ptq3_kl_nats"] for r in hp]) <= 0.85 * np.mean([r["ptq3_kl_nats"] for r in fl])
           and max(r["ptq3_kl_nats"] for r in hp) < min(r["ptq3_kl_nats"] for r in fl))
    h6c = "CONFIRMED" if (c_a or c_b) else "FALSIFIED"

    verdicts = {
        "H6a": {"verdict": h6a, "polar_beats_flat_models": h6a_pass, "equatorial_beats_polar_models": eq_beats,
                "locked_fraction": locked_frac},
        "H6b_part1": {"verdict": h6b1, "within_015db_models": b1_pass, "equivariance_all": b1_eqv, "split": f"{best_split[0]}x{best_split[1]}"},
        "H6b_part2": {"verdict": h6b2, "rate_holds": rate_ok},
        "H6c": {"verdict": h6c, "criterion_a_nll": bool(c_a), "criterion_b_ptq": bool(c_b)},
    }
    tot = [a for m in models.values() for a in m["arms"].values()] + list(pilot_arms.values())
    payload: dict[str, Any] = {
        "schema": "aletheia.track_s106.h6_results.v1", "oracle_class": "anchor",
        "preregistration_sha256": prereg_sha, "amendment2_sha256": amend_sha,
        "protocol_file_sha256": proto_sha, "protocol_locked_utc": proto["locked_utc"],
        "completed_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python_stdlib_sha256": py_sha,
        "h6b1_gaussian_split_scores": split_scores, "h6b1_gaussian_eq_s3_mean_cos": eq_g,
        "h6a_pilot_qwen05b": pilot_arms,
        "models": models, "h6c_runs": h6c_runs,
        "global_integrity": {"total_arms_evaluated": len(tot),
                             "total_syndrome_errors": sum(a["syndrome_errors"] for a in tot) + sum(r["ptq_syndrome_errors"] for r in h6c_runs),
                             "total_oob_groups": sum(a["oob_groups"] for a in tot) + sum(r["ptq_oob_groups"] for r in h6c_runs),
                             "total_non_block_diffs": sum(a["non_block_diffs"] for a in tot)},
        "preregistered_verdicts": verdicts,
        "nvidia_smi_pre": smi_pre, "nvidia_smi_post": p2._query_nvidia_smi(),
        "elapsed_seconds": round(time.monotonic() - t_start, 3),
    }
    payload["result_sha256"] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    out_bytes = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    out_path = _HERE / "s106_h6_results.json"
    out_path.write_bytes(out_bytes)
    os.chmod(out_path, 0o600)
    print("\n=== H6 VERDICTS (PREREG-S106-AMENDMENT2-H6, literal locked gates) ===", flush=True)
    for k, v in verdicts.items():
        print(f"  {k}: {v['verdict']}  {json.dumps({kk: vv for kk, vv in v.items() if kk != 'verdict'})}", flush=True)
    print(f"  INTEGRITY: {json.dumps(payload['global_integrity'])}", flush=True)
    print(f"  FILE: {out_path.name} ({len(out_bytes)} B, sha256={hashlib.sha256(out_bytes).hexdigest()}, inner={payload['result_sha256']})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
