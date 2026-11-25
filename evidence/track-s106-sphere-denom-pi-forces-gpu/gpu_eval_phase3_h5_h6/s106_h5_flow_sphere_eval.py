#!/usr/bin/env python3
"""Track S106 Amendment 1 (PREREG-S106-AMENDMENT1-H5): Data-Flow Proper-Time Metric Sphere.

H5a: Zero-extra-bit white-noise Flow-SphereMap (W D_flow^noise) vs static SphereMap vs
     real-text Flow-SphereMap (WikiText-2 *validation*, disjoint from test) vs permuted-D_flow
     null, at identical exact_bpw (E8 2.0, E8 3.0, A16 3.0), on blind held-out
     SmolLM2-360M, Qwen2.5-1.5B, Qwen2.5-3B x {WikiText-2 test, Python stdlib}.
     D_flow^-1 is folded into the existing FP16 column vector D_c (re-rounded to FP16), so
     exact_bpw is bit-for-bit identical to static SphereMap.
H5b: Causal depth-time cone: identical relative perturbation eps=0.05 injected into each
     layer's down_proj + o_proj, final-logit KL measured per layer; Q1/Q4 amplification ratio.
     Fixed, model-agnostic depth-time schedule (Q1 @ 3.5 bpw, middle @ 3.0, Q4 @ 2.5) vs
     uniform 3.0 vs reversed schedule, all on siliquant per-128 A_16 at matched mean bpw.

Every grading rule and constant is written to h5_locked_protocol.json BEFORE any model loads.
Zero tuning on held-out models. Zero model weights written to disk.
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

import torch

_HERE = Path(__file__).resolve().parent
_TRACK = _HERE.parent
_GPU_EVAL = _TRACK / "gpu_eval"  # frozen Phase-2 operator library, imported read-only
if str(_GPU_EVAL) not in sys.path:
    sys.path.insert(0, str(_GPU_EVAL))

import s106_quant_ops as ops  # noqa: E402
import s106_phase2_blind_gauntlet as p2  # noqa: E402

AMEND1_SHA_PREFIX = "c83910a0e1a98e2a"
EVAL_SEED = 2026112507
N_FLOW_CHUNKS = 8
N_PROBE_CHUNKS = 4
H5B_EPS = 0.05
H5A_CONFIGS = (("E8", "2.0"), ("E8", "3.0"), ("A16", "3.0"))

# Exact per-128 A_16^8 ball bounds (exact BigInt theta-series; R2=650 reproduces the 3.0 bound).
EXTRA_PER_BLOCK = {
    "2.5": {128: {"A16": (324, 2.37286)}},
    "3.5": {128: {"A16": (1302, 3.37459)}},
}

LOCKED_PROTOCOL: dict[str, Any] = {
    "schema": "aletheia.track_s106.h5_locked_protocol.v1",
    "parent_preregistration_sha256": ops.PREREG_SHA256,
    "amendment1_sha256_prefix": AMEND1_SHA_PREFIX,
    "held_out_models": list(p2.__dict__.get("EXPECTED_HELD_OUT", ())) or [
        "HuggingFaceTB/SmolLM2-360M", "Qwen/Qwen2.5-1.5B", "Qwen/Qwen2.5-3B"],
    "eval_seed": EVAL_SEED,
    "seq_len": p2.SEQ_LEN,
    "n_eval_chunks": p2.N_EVAL_CHUNKS,
    "n_flow_chunks": N_FLOW_CHUNKS,
    "flow_noise_source": "uniform random token ids (torch.Generator seeded EVAL_SEED), zero dataset",
    "flow_real_source": "WikiText-2 validation split (disjoint from WikiText-2 test used for scoring)",
    "flow_definition": "D_flow[j] = sqrt(mean_tokens x_j^2) at the input of each block linear, normalized to mean 1",
    "flow_spheremap": "W_flow = W diag(D_flow); SphereMap(W_flow); reconstruct H64(Q) * D_r * fp16(D_c / D_flow)",
    "null_control": "D_flow^noise permuted by a per-matrix SHA-256-seeded permutation",
    "h5a_configs": [list(c) for c in H5A_CONFIGS],
    "h5a_model_config_pass": "flow_noise beats static by >= 15% rel KL with z >= 2 on BOTH corpora AND beats null with z >= 2 on BOTH corpora",
    "h5a_config_holds": "model_config_pass on >= 2 of 3 held-out models",
    "h5a_verdict": "CONFIRMED if config holds on >= 2 of 3 configs; PARTIAL if holds on exactly 1 config OR flow_noise beats static at z >= 2 on both corpora on >= 2 models in >= 2 configs; else FALSIFIED",
    "h5b_eps": H5B_EPS,
    "h5b_perturbed_modules": ["mlp.down_proj", "self_attn.o_proj"],
    "h5b_probe": f"first {N_PROBE_CHUNKS} WikiText-2 test chunks",
    "h5b_amplification_pass": "mean KL over first-quartile layers / mean KL over last-quartile layers >= 2.0",
    "h5b_schedule": "per-128 A16: first floor(L/4) layers 3.5 bpw, last floor(L/4) layers 2.5 bpw, rest 3.0 bpw",
    "h5b_schedule_pass": "depth schedule beats uniform 3.0 by >= 8% rel KL with z >= 2 on BOTH corpora",
    "h5b_verdict": "CONFIRMED iff amplification passes on >= 2 of 3 models AND schedule passes on >= 2 of 3 models; else FALSIFIED (sub-results logged)",
    "exploratory_not_graded": ["p128_A16_3b_flownoise (column scale stored as FP16: +16/m bpw counted)", "reversed depth schedule"],
    "extra_per_block_bounds": {k: {"128": {"A16": list(v[128]["A16"])}} for k, v in EXTRA_PER_BLOCK.items()},
}


def _sig_better(a: dict[str, Any], b: dict[str, Any], thresh: float) -> bool:
    for dom in ("wikitext2", "python"):
        ka, sa = float(a[dom]["mean_kl"]), float(a[dom]["se_kl"])
        kb, sb = float(b[dom]["mean_kl"]), float(b[dom]["se_kl"])
        rel = (kb - ka) / max(kb, 1e-12)
        z = (kb - ka) / max(math.hypot(sa, sb), 1e-12)
        if not (rel >= thresh and z >= 2.0):
            return False
    return True


def _rel(a: dict[str, Any], b: dict[str, Any], dom: str) -> float:
    kb = float(b[dom]["mean_kl"])
    return round((kb - float(a[dom]["mean_kl"])) / max(kb, 1e-12), 6)


@torch.no_grad()
def _capture_dflow(model: torch.nn.Module, linears: list[tuple[str, torch.nn.Linear]],
                   chunks: torch.Tensor, device: torch.device) -> dict[str, torch.Tensor]:
    sums: dict[str, torch.Tensor] = {}
    counts: dict[str, int] = {}
    hooks = []
    for name, mod in linears:
        sums[name] = torch.zeros(mod.in_features, device=device, dtype=torch.float64)
        counts[name] = 0

        def _mk(lname: str):
            def _h(_m, inputs):
                x = inputs[0].detach().reshape(-1, inputs[0].shape[-1]).to(torch.float64)
                sums[lname] += (x * x).sum(dim=0)
                counts[lname] += int(x.shape[0])
            return _h

        hooks.append(mod.register_forward_pre_hook(_mk(name)))
    for i in range(chunks.shape[0]):
        model(chunks[i:i + 1].to(device), use_cache=False)
    for h in hooks:
        h.remove()
    out: dict[str, torch.Tensor] = {}
    for n in sums:
        d = torch.sqrt(sums[n] / max(counts[n], 1)).to(torch.float32)
        d = d / d.mean().clamp_min(1e-12)
        out[n] = d.clamp_min(1e-3).cpu()
    del sums
    torch.cuda.empty_cache()
    return out


def _flow_quant(wf: torch.Tensor, dflow: torch.Tensor, lat: str, bpw: str) -> tuple[torch.Tensor, dict[str, Any]]:
    w_flow = wf * dflow.unsqueeze(0)
    w_sp, dr, dc, ex, _, _ = ops.spheremap_forward(w_flow, block_size=64)
    q_sp, st = ops.quant_global_ball_matrix(w_sp, lat, bpw, extra_bpw=ex)
    dc_comb = (dc / dflow).to(torch.float16).to(torch.float32)
    if not bool(torch.isfinite(dc_comb).all()) or float(dc_comb.min()) <= 0.0:
        raise RuntimeError("FP16 composite column scale out of range")
    wq = ops.apply_block_hadamard(q_sp, block_size=64) * dr.unsqueeze(1) * dc_comb.unsqueeze(0)
    return wq, st


def _static_quant(wf: torch.Tensor, lat: str, bpw: str) -> tuple[torch.Tensor, dict[str, Any]]:
    w_sp, dr, dc, ex, _, _ = ops.spheremap_forward(wf, block_size=64)
    q_sp, st = ops.quant_global_ball_matrix(w_sp, lat, bpw, extra_bpw=ex)
    return ops.spheremap_inverse(q_sp, dr, dc, block_size=64), st


def _null_perm(n: int, tag: str) -> torch.Tensor:
    seed = int(hashlib.sha256(tag.encode("utf-8")).hexdigest()[:8], 16)
    return torch.randperm(n, generator=torch.Generator(device="cpu").manual_seed(seed))


def _eval_model(repo_id: str, local_dir: str, wt_test: str, wt_val: str, py_test: str,
                device: torch.device) -> dict[str, Any]:
    print(f"\n{'=' * 80}\nH5 BLIND HELD-OUT MODEL: {repo_id}\n{'=' * 80}", flush=True)
    t0 = time.monotonic()
    tok = p2.AutoTokenizer.from_pretrained(local_dir, local_files_only=True)
    model = p2.AutoModelForCausalLM.from_pretrained(local_dir, local_files_only=True, dtype=torch.bfloat16).to(device)
    model.eval()
    linears = p2._collect_block_linears(model)
    n_layers = max(p2._layer_idx(n) for n, _ in linears) + 1
    snaps = p2._snapshot_non_block_tensors(model)
    orig = {n: m.weight.detach().cpu().clone() for n, m in linears}
    tot_w = sum(int(m.weight.numel()) for _, m in linears)

    wt_chunks = p2._tokenize_chunks(tok, wt_test, p2.N_EVAL_CHUNKS, p2.SEQ_LEN)
    py_chunks = p2._tokenize_chunks(tok, py_test, p2.N_EVAL_CHUNKS, p2.SEQ_LEN)
    val_chunks = p2._tokenize_chunks(tok, wt_val, N_FLOW_CHUNKS, p2.SEQ_LEN)
    gen = torch.Generator().manual_seed(EVAL_SEED)
    noise_chunks = torch.randint(0, int(model.config.vocab_size), (N_FLOW_CHUNKS, p2.SEQ_LEN), generator=gen)

    ref_wt, base_wt_ppl, _ = p2._collect_reference_logits(model, wt_chunks, device)
    ref_py, base_py_ppl, _ = p2._collect_reference_logits(model, py_chunks, device)
    d_noise = _capture_dflow(model, linears, noise_chunks, device)
    d_real = _capture_dflow(model, linears, val_chunks, device)
    d_null = {n: d_noise[n][_null_perm(d_noise[n].numel(), f"{repo_id}:{n}:h5_null")] for n in d_noise}
    spread_noise = max(float(d.max() / d.min()) for d in d_noise.values())
    print(f"  BF16 base Wiki PPL={base_wt_ppl:.4f} Py PPL={base_py_ppl:.4f} | max D_flow^noise spread={spread_noise:.1f}x", flush=True)

    def _run(arm: str, fn) -> dict[str, Any]:
        tot_err = tot_sig = bpw_num = 0.0
        syn = oob = 0
        with torch.no_grad():
            for ln, mod in linears:
                wf = orig[ln].to(device=device, dtype=torch.float32)
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
        nb = p2._count_non_block_diffs(model, snaps)
        wt_s = p2._score_against_reference(model, wt_chunks, ref_wt, device)
        py_s = p2._score_against_reference(model, py_chunks, ref_py, device)
        snr = 10.0 * math.log10(max(tot_sig, 1e-30) / max(tot_err, 1e-30))
        row = {"arm": arm, "exact_bpw": round(bpw_num / float(tot_w), 5), "weight_snr_db": round(snr, 4),
               "syndrome_errors": syn, "oob_groups": oob, "non_block_diffs": nb,
               "wikitext2": wt_s, "python": py_s}
        print(f"  [{arm:28s}] bpw={row['exact_bpw']:.4f} SNR={snr:6.3f}dB WikiKL={wt_s['mean_kl']:.5f}±{wt_s['se_kl']:.5f} "
              f"PyKL={py_s['mean_kl']:.5f}±{py_s['se_kl']:.5f} syn={syn} oob={oob} nb={nb}", flush=True)
        return row

    arms: dict[str, Any] = {}
    for lat, bpw in H5A_CONFIGS:
        tag = f"{lat}_{bpw.replace('.', '')}b"
        arms[f"static_{tag}"] = _run(f"static_{tag}", lambda _n, wf, L=lat, B=bpw: _static_quant(wf, L, B))
        arms[f"flownoise_{tag}"] = _run(f"flownoise_{tag}", lambda n, wf, L=lat, B=bpw: _flow_quant(wf, d_noise[n].to(wf.device), L, B))
        arms[f"flowreal_{tag}"] = _run(f"flowreal_{tag}", lambda n, wf, L=lat, B=bpw: _flow_quant(wf, d_real[n].to(wf.device), L, B))
        arms[f"flownull_{tag}"] = _run(f"flownull_{tag}", lambda n, wf, L=lat, B=bpw: _flow_quant(wf, d_null[n].to(wf.device), L, B))

    # Exploratory (NOT graded): per-128 A16 with D_flow^noise column pre-scaling, scale vector billed at 16/m bpw.
    def _p128_flow(n: str, wf: torch.Tensor) -> tuple[torch.Tensor, dict[str, Any]]:
        dfl = d_noise[n].to(device=wf.device).to(torch.float16).to(torch.float32)
        wq, st = ops.quant_per_block_ball_matrix(wf * dfl.unsqueeze(0), "3.0", "A16", 128, row_chunk=512)
        st = dict(st)
        st["exact_bpw"] = float(st["exact_bpw"]) + 16.0 / float(wf.shape[0])
        return wq / dfl.unsqueeze(0), st

    arms["p128_A16_3b"] = _run("p128_A16_3b", lambda _n, wf: ops.quant_per_block_ball_matrix(wf, "3.0", "A16", 128, row_chunk=512))
    arms["p128_A16_3b_flownoise"] = _run("p128_A16_3b_flownoise", _p128_flow)

    # H5b depth-time schedules on per-128 A16
    q = n_layers // 4

    def _sched_bpw(layer: int, reverse: bool) -> str:
        first, last = ("2.5", "3.5") if reverse else ("3.5", "2.5")
        if layer < q:
            return first
        if layer >= n_layers - q:
            return last
        return "3.0"

    arms["sched_depth_p128"] = _run("sched_depth_p128", lambda n, wf: ops.quant_per_block_ball_matrix(
        wf, _sched_bpw(p2._layer_idx(n), False), "A16", 128, row_chunk=512))
    arms["sched_reverse_p128"] = _run("sched_reverse_p128", lambda n, wf: ops.quant_per_block_ball_matrix(
        wf, _sched_bpw(p2._layer_idx(n), True), "A16", 128, row_chunk=512))

    # H5b causal cone perturbation probe
    with torch.no_grad():
        for ln, mod in linears:
            mod.weight.copy_(orig[ln].to(device=device, dtype=torch.bfloat16))
    probe_chunks = wt_chunks[:N_PROBE_CHUNKS]
    probe_ref = ref_wt[:N_PROBE_CHUNKS]
    targets = [(ln, m) for ln, m in linears if ln.endswith("mlp.down_proj") or ln.endswith("self_attn.o_proj")]
    per_layer: list[dict[str, Any]] = []
    for li in range(n_layers):
        mods = [(ln, m) for ln, m in targets if p2._layer_idx(ln) == li]
        with torch.no_grad():
            for ln, m in mods:
                w = orig[ln].to(device=device, dtype=torch.float32)
                g = torch.Generator(device="cpu").manual_seed(int(hashlib.sha256(f"{repo_id}:{ln}:h5b".encode()).hexdigest()[:8], 16))
                z = torch.randn(w.shape, generator=g, dtype=torch.float32).to(device)
                z = z * (H5B_EPS * torch.linalg.norm(w) / torch.linalg.norm(z).clamp_min(1e-12))
                m.weight.copy_((w + z).to(torch.bfloat16))
                del w, z
        sc = p2._score_against_reference(model, probe_chunks, probe_ref, device)
        with torch.no_grad():
            for ln, m in mods:
                m.weight.copy_(orig[ln].to(device=device, dtype=torch.bfloat16))
        per_layer.append({"layer": li, "wiki_kl": sc["mean_kl"]})
    kl_vec = [r["wiki_kl"] for r in per_layer]
    q1 = sum(kl_vec[:q]) / max(q, 1)
    q4 = sum(kl_vec[n_layers - q:]) / max(q, 1)
    amp = q1 / max(q4, 1e-12)
    print(f"  [H5b CONE] L={n_layers} Q1 mean KL={q1:.5f} Q4 mean KL={q4:.5f} amplification={amp:.3f}x", flush=True)

    out = {
        "repo_id": repo_id, "num_hidden_layers": n_layers, "total_block_weights": tot_w,
        "reference_bf16": {"wikitext2_ppl": round(base_wt_ppl, 6), "python_ppl": round(base_py_ppl, 6)},
        "max_dflow_noise_spread": round(spread_noise, 3),
        "arms": arms,
        "h5b_cone": {"eps": H5B_EPS, "quartile_size": q, "q1_mean_kl": round(q1, 8), "q4_mean_kl": round(q4, 8),
                     "amplification_q1_over_q4": round(amp, 6), "per_layer": per_layer},
        "model_elapsed_seconds": round(time.monotonic() - t0, 3),
    }
    del model, ref_wt, ref_py, orig, d_noise, d_real, d_null
    gc.collect()
    torch.cuda.empty_cache()
    return out


def _grade(models: dict[str, Any]) -> dict[str, Any]:
    names = list(models.keys())
    h5a_cfg: dict[str, Any] = {}
    holds = 0
    sig_cfgs = 0
    for lat, bpw in H5A_CONFIGS:
        tag = f"{lat}_{bpw.replace('.', '')}b"
        passes = 0
        sig_models = 0
        det: dict[str, Any] = {}
        for m in names:
            a = models[m]["arms"]
            fn, st, nu, fr = a[f"flownoise_{tag}"], a[f"static_{tag}"], a[f"flownull_{tag}"], a[f"flowreal_{tag}"]
            ok_static = _sig_better(fn, st, 0.15)
            ok_null = _sig_better(fn, nu, 0.0)
            sig = _sig_better(fn, st, 0.0)
            passes += int(ok_static and ok_null)
            sig_models += int(sig)
            det[m] = {"rel_vs_static_wiki": _rel(fn, st, "wikitext2"), "rel_vs_static_py": _rel(fn, st, "python"),
                      "rel_vs_null_wiki": _rel(fn, nu, "wikitext2"), "rel_vs_null_py": _rel(fn, nu, "python"),
                      "real_rel_vs_static_wiki": _rel(fr, st, "wikitext2"), "real_rel_vs_static_py": _rel(fr, st, "python"),
                      "beats_static_15pct_2se": ok_static, "beats_null_2se": ok_null, "beats_static_2se_any": sig}
        cfg_holds = passes >= 2
        holds += int(cfg_holds)
        sig_cfgs += int(sig_models >= 2)
        h5a_cfg[tag] = {"holds": cfg_holds, "models_passing": passes, "details": det}
    if holds >= 2:
        h5a = "CONFIRMED"
    elif holds == 1 or sig_cfgs >= 2:
        h5a = "PARTIAL"
    else:
        h5a = "FALSIFIED"

    amp_ok = sched_ok = 0
    h5b_det: dict[str, Any] = {}
    for m in names:
        a = models[m]["arms"]
        amp = float(models[m]["h5b_cone"]["amplification_q1_over_q4"])
        s_ok = _sig_better(a["sched_depth_p128"], a["p128_A16_3b"], 0.08)
        amp_ok += int(amp >= 2.0)
        sched_ok += int(s_ok)
        h5b_det[m] = {"amplification": amp, "amp_pass": amp >= 2.0, "sched_pass": s_ok,
                      "sched_rel_wiki": _rel(a["sched_depth_p128"], a["p128_A16_3b"], "wikitext2"),
                      "sched_rel_py": _rel(a["sched_depth_p128"], a["p128_A16_3b"], "python"),
                      "reverse_rel_wiki": _rel(a["sched_reverse_p128"], a["p128_A16_3b"], "wikitext2"),
                      "reverse_rel_py": _rel(a["sched_reverse_p128"], a["p128_A16_3b"], "python"),
                      "bpw_uniform": a["p128_A16_3b"]["exact_bpw"], "bpw_depth": a["sched_depth_p128"]["exact_bpw"]}
    h5b = "CONFIRMED" if (amp_ok >= 2 and sched_ok >= 2) else "FALSIFIED"
    return {"H5a": {"verdict": h5a, "configs": h5a_cfg},
            "H5b": {"verdict": h5b, "amp_models_passing": amp_ok, "sched_models_passing": sched_ok, "details": h5b_det}}


def main() -> int:
    t_start = time.monotonic()
    torch.manual_seed(EVAL_SEED)
    device = torch.device("cuda:0")
    notes = _TRACK.parent / "notes" / "sphere_pi_forces_2026_11_25"
    prereg_sha = hashlib.sha256((notes / "PREREG_SPHERE_PI_FORCES_V1.md").read_bytes()).hexdigest()
    amend_sha = hashlib.sha256((notes / "PREREG_SPHERE_PI_FORCES_AMENDMENT1_H5.md").read_bytes()).hexdigest()
    if prereg_sha != ops.PREREG_SHA256 or not amend_sha.startswith(AMEND1_SHA_PREFIX):
        raise RuntimeError(f"Preregistration lock mismatch: {prereg_sha} / {amend_sha}")
    for k, v in EXTRA_PER_BLOCK.items():
        ops.PER_BLOCK_BOUNDS[k] = v

    proto = dict(LOCKED_PROTOCOL)
    proto["amendment1_sha256"] = amend_sha
    proto["locked_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    proto_bytes = (json.dumps(proto, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    proto_path = _HERE / "h5_locked_protocol.json"
    proto_path.write_bytes(proto_bytes)
    os.chmod(proto_path, 0o600)
    proto_sha = hashlib.sha256(proto_bytes).hexdigest()
    print(f"H5 PROTOCOL LOCKED {proto['locked_utc']} sha256={proto_sha}", flush=True)

    ac = Path("/sys/class/power_supply/AC0/online").read_text(encoding="utf-8").strip()
    if ac != "1":
        raise RuntimeError("AC power required")
    cache = Path.home() / ".cache" / "huggingface"
    pins = json.loads((cache / "s49b_eval" / "pins.json").read_text(encoding="utf-8"))
    q15 = json.loads((cache / "s60_eval" / "qwen15b_pin.json").read_text(encoding="utf-8"))
    q3 = json.loads((cache / "s63_eval" / "qwen3b_pin.json").read_text(encoding="utf-8"))
    wt_test = (cache / "s49b_eval" / "wikitext2_test.txt").read_text(encoding="utf-8")
    wt_val = (cache / "s49b_eval" / "wikitext2_val.txt").read_text(encoding="utf-8")
    py_test, py_sha = p2._load_python_eval_text()
    smi_pre = p2._query_nvidia_smi()

    models: dict[str, Any] = {}
    for rid, ldir in (("HuggingFaceTB/SmolLM2-360M", pins["HuggingFaceTB/SmolLM2-360M"]["local_dir"]),
                      ("Qwen/Qwen2.5-1.5B", q15["local_dir"]), ("Qwen/Qwen2.5-3B", q3["local_dir"])):
        models[rid] = _eval_model(rid, ldir, wt_test, wt_val, py_test, device)

    verdicts = _grade(models)
    tot_syn = sum(a["syndrome_errors"] for m in models.values() for a in m["arms"].values())
    tot_oob = sum(a["oob_groups"] for m in models.values() for a in m["arms"].values())
    tot_nb = sum(a["non_block_diffs"] for m in models.values() for a in m["arms"].values())
    payload: dict[str, Any] = {
        "schema": "aletheia.track_s106.h5_results.v1",
        "oracle_class": "anchor",
        "preregistration_sha256": prereg_sha,
        "amendment1_sha256": amend_sha,
        "protocol_file_sha256": proto_sha,
        "protocol_locked_utc": proto["locked_utc"],
        "completed_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python_stdlib_sha256": py_sha,
        "wikitext2_test_sha256": pins["wikitext2"]["test_sha256"],
        "wikitext2_val_sha256": pins["wikitext2"]["val_sha256"],
        "global_integrity": {"total_arms_evaluated": sum(len(m["arms"]) for m in models.values()),
                             "total_syndrome_errors": tot_syn, "total_oob_groups": tot_oob, "total_non_block_diffs": tot_nb},
        "models": models,
        "preregistered_verdicts": verdicts,
        "nvidia_smi_pre": smi_pre,
        "nvidia_smi_post": p2._query_nvidia_smi(),
        "elapsed_seconds": round(time.monotonic() - t_start, 3),
    }
    payload["result_sha256"] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    out_bytes = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    out_path = _HERE / "s106_h5_results.json"
    out_path.write_bytes(out_bytes)
    os.chmod(out_path, 0o600)
    print("\n=== H5 VERDICTS (PREREG-S106-AMENDMENT1-H5, literal locked gates) ===", flush=True)
    for k, v in verdicts.items():
        print(f"  {k}: {v['verdict']}", flush=True)
    print(f"  INTEGRITY: {json.dumps(payload['global_integrity'])}", flush=True)
    print(f"  FILE: {out_path.name} ({len(out_bytes)} B, sha256={hashlib.sha256(out_bytes).hexdigest()}, inner={payload['result_sha256']})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
