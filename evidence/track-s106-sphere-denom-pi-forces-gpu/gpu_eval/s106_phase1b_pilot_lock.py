#!/usr/bin/env python3
"""Track S106 Phase 1B: Pilot Parameter Lock (STRICTLY Synthetic Gaussian + Qwen/Qwen2.5-0.5B).

Locks EVERY universal constant BEFORE any held-out model (SmolLM2-360M, Qwen2.5-1.5B,
Qwen2.5-3B) is ever loaded:
  1. Universal Gaussian 1D Lloyd-Max codebooks (2b, 3b, 4b)
  2. Universal Gaussian Power-0.7 radial warp scale s & integer shell LUT rho[m] for E_8 & A_16
     (+ linear shell LUT ablation gamma=1.0)
  3. Best closed-form LUT-free Denominator-pi EQ(S^3) variant (Leopardi-8c vs Hopf-Hex-4b)
  4. Best Gravity+Yukawa (mu, lam) & Gravity+Coulomb lam on synthetic Gaussian S^3 (K=256)
  5. Live Qwen/Qwen2.5-0.5B KL pilot sweep locking:
       - Hodge transverse weight lambda_perp in {2.0, 4.0}
       - Exact H4 conjunction components (anti-bloat rule: keep ONLY Phase-1B winners!)

Writes immutable s106_frozen_pilot_params.json (0o600) with SHA-256 lock.
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
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import s106_quant_ops as ops

EVAL_SEED = 2026112506
SEQ_LEN = 512
N_EVAL_CHUNKS = 8
LOGIT_TOK_CHUNK = 128

STDLIB_PY_MODULES = (
    "fractions.py",
    "difflib.py",
    "decimal.py",
    "statistics.py",
    "argparse.py",
    "json/decoder.py",
)


def _load_python_eval_text() -> tuple[str, str]:
    stdlib_dir = Path(json.__file__).resolve().parent.parent
    chunks: list[str] = []
    h = hashlib.sha256()
    for rel in STDLIB_PY_MODULES:
        raw = (stdlib_dir / rel).read_bytes()
        h.update(rel.encode("utf-8") + b"\0" + raw)
        chunks.append(raw.decode("utf-8", errors="ignore"))
    return "\n\n".join(chunks), h.hexdigest()


def _tokenize_chunks(tokenizer: Any, text: str, n_chunks: int, seq_len: int) -> torch.Tensor:
    ids = tokenizer(text, return_tensors="pt", add_special_tokens=False).input_ids[0]
    need = n_chunks * seq_len
    if ids.numel() < need:
        ids = ids.repeat((need // ids.numel()) + 1)
    return ids[:need].reshape(n_chunks, seq_len).contiguous()


@torch.no_grad()
def _collect_reference_logits(
    model: torch.nn.Module, chunks: torch.Tensor, device: torch.device
) -> tuple[list[torch.Tensor], float]:
    ref_lp: list[torch.Tensor] = []
    tot_nll = 0.0
    tot_toks = 0
    for i in range(chunks.shape[0]):
        inp = chunks[i : i + 1].to(device)
        logits = model(inp, use_cache=False).logits[:, :-1, :]
        targets = inp[:, 1:]
        seq_t = logits.shape[1]
        parts: list[torch.Tensor] = []
        for s0 in range(0, seq_t, LOGIT_TOK_CHUNK):
            s1 = min(s0 + LOGIT_TOK_CHUNK, seq_t)
            lp = F.log_softmax(logits[:, s0:s1, :].to(torch.float32), dim=-1)
            nll = F.nll_loss(lp.reshape(-1, lp.shape[-1]), targets[:, s0:s1].reshape(-1), reduction="sum")
            tot_nll += float(nll.item())
            tot_toks += int(targets[:, s0:s1].numel())
            parts.append(lp.cpu())
            del lp
        ref_lp.append(torch.cat(parts, dim=1))
        del inp, logits, parts
    torch.cuda.empty_cache()
    return ref_lp, math.exp(tot_nll / max(tot_toks, 1))


@torch.no_grad()
def _score_against_reference(
    model: torch.nn.Module,
    chunks: torch.Tensor,
    ref_lp: list[torch.Tensor],
    device: torch.device,
) -> dict[str, float]:
    kl_list: list[float] = []
    chunk_means: list[float] = []
    tot_nll = 0.0
    tot_toks = 0
    same_top1 = 0
    for i in range(chunks.shape[0]):
        inp = chunks[i : i + 1].to(device)
        logits = model(inp, use_cache=False).logits[:, :-1, :]
        targets = inp[:, 1:]
        ref_cpu = ref_lp[i]
        seq_t = logits.shape[1]
        c_kls: list[float] = []
        for s0 in range(0, seq_t, LOGIT_TOK_CHUNK):
            s1 = min(s0 + LOGIT_TOK_CHUNK, seq_t)
            log_q = F.log_softmax(logits[:, s0:s1, :].to(torch.float32), dim=-1)
            log_p = ref_cpu[:, s0:s1, :].to(device)
            tok_kl = (torch.exp(log_p) * (log_p - log_q)).sum(dim=-1).reshape(-1)
            vals = tok_kl.cpu().tolist()
            kl_list.extend(vals)
            c_kls.extend(vals)
            nll = F.nll_loss(log_q.reshape(-1, log_q.shape[-1]), targets[:, s0:s1].reshape(-1), reduction="sum")
            tot_nll += float(nll.item())
            tot_toks += int(targets[:, s0:s1].numel())
            same_top1 += int((log_q.argmax(dim=-1) == log_p.argmax(dim=-1)).sum().item())
            del log_q, log_p, tok_kl
        chunk_means.append(sum(c_kls) / max(len(c_kls), 1))
        del inp, logits
    torch.cuda.empty_cache()
    kl_t = torch.tensor(kl_list, dtype=torch.float64)
    cm_t = torch.tensor(chunk_means, dtype=torch.float64)
    se_tok = float(kl_t.std(unbiased=True).item() / math.sqrt(float(len(kl_list))))
    se_chunk = float(cm_t.std(unbiased=True).item() / math.sqrt(float(len(chunk_means))))
    return {
        "mean_kl": round(float(kl_t.mean().item()), 8),
        "se_kl": round(se_tok, 8),
        "chunk_se_kl": round(se_chunk, 8),
        "p95_kl": round(float(torch.quantile(kl_t, 0.95).item()), 8),
        "ppl": round(math.exp(tot_nll / max(tot_toks, 1)), 6),
        "top1_match_pct": round(100.0 * float(same_top1) / float(max(tot_toks, 1)), 4),
        "tokens_scored": tot_toks,
    }


def _collect_block_linears(model: torch.nn.Module) -> list[tuple[str, torch.nn.Linear]]:
    return [
        (name, mod)
        for name, mod in model.named_modules()
        if isinstance(mod, torch.nn.Linear) and name.startswith("model.layers.")
    ]


def _codebook_oos_stats(cb: torch.Tensor, u_oos: torch.Tensor) -> dict[str, float]:
    dots = u_oos @ cb.T
    best = dots.max(dim=-1).values
    mc = float(best.mean().item())
    wc = float(best.min().item())
    g = cb @ cb.T
    g.fill_diagonal_(-2.0)
    min_deg = math.degrees(math.acos(min(1.0, float(g.max().item()))))
    snr = -10.0 * math.log10(max(1e-12, 2.0 * (1.0 - mc)))
    return {
        "mean_cos": round(mc, 6),
        "worst_cos": round(wc, 6),
        "min_ang_deg": round(min_deg, 3),
        "dir_snr_db": round(snr, 4),
    }


def main() -> int:
    t0 = time.monotonic()
    torch.manual_seed(EVAL_SEED)
    device = torch.device("cuda:0")
    here = Path(__file__).resolve().parent
    prereg_path = here.parent.parent / "notes" / "sphere_pi_forces_2026_11_25" / "PREREG_SPHERE_PI_FORCES_V1.md"
    prereg_sha = hashlib.sha256(prereg_path.read_bytes()).hexdigest()
    if prereg_sha != ops.PREREG_SHA256:
        raise RuntimeError(f"Preregistration SHA mismatch: {prereg_sha} != {ops.PREREG_SHA256}")

    print("=== PHASE 1B STEP 1: UNIVERSAL GAUSSIAN PARAMETER FIT ===", flush=True)
    rng = np.random.default_rng(20261125)
    g1d = rng.standard_normal(400_000)
    lm_gauss = {
        str(b): [round(x, 7) for x in ops.fit_lloyd_max_1d(g1d, 1 << b, n_iter=40)]
        for b in (2, 3, 4)
    }

    # Universal Gaussian radial-warp & linear shell LUTs (E_8 and A_16 at 2.0 and 3.0 bpw)
    shell_luts: dict[str, dict[str, Any]] = {}
    for bpw_key, lat_key in (("2.0", "E8"), ("3.0", "E8"), ("2.0", "A16"), ("3.0", "A16")):
        r2_max, pay_bpw = ops.GLOBAL_BALL_BOUNDS[bpw_key][lat_key]
        for gamma_tag, gamma_val in (("power07", 0.7), ("linear", 1.0)):
            s_opt, lut, g_snr = ops.fit_universal_radial_warp_lut(
                lat_key, r2_max, gamma_val, device=device, n_samples=65536, seed=20261125
            )
            key = f"{lat_key}_{bpw_key}_{gamma_tag}"
            shell_luts[key] = {
                "lattice": lat_key,
                "bpw_key": bpw_key,
                "r2_max": r2_max,
                "payload_bpw": pay_bpw,
                "gamma": gamma_val,
                "scale_s": s_opt,
                "gaussian_snr_db": g_snr,
                "rho": lut,
            }
            print(f"  [LUT] {key:22s}: R2={r2_max:3d} s={s_opt:.5f} GaussSNR={g_snr:.3f} dB (M={len(lut)-1})", flush=True)

    # S^3 (K=256) analytical EQ vs Numerator-pi vs Gravity-only vs Coulomb vs Yukawa (STRICTLY on Gaussian!)
    x4 = torch.tensor(rng.standard_normal((40000, 4)), dtype=torch.float32, device=device)
    u4 = x4 / torch.norm(x4, dim=-1, keepdim=True).clamp_min(1e-12)
    u4_tr, u4_oos = u4[:20000], u4[20000:]

    cb_num_s3 = ops.build_numerator_pi_s3(4, 8, 8).to(device)
    cb_eq_s3_leo = ops.build_eq_s3_leopardi().to(device)
    cb_eq_s3_hopf = ops.build_eq_s3_hopf_hex().to(device)
    st_num_s3 = _codebook_oos_stats(cb_num_s3, u4_oos)
    st_leo_s3 = _codebook_oos_stats(cb_eq_s3_leo, u4_oos)
    st_hopf_s3 = _codebook_oos_stats(cb_eq_s3_hopf, u4_oos)
    print(f"  [S^3 Num-pi  256] {st_num_s3}", flush=True)
    print(f"  [S^3 EQ-Leo  256] {st_leo_s3}", flush=True)
    print(f"  [S^3 EQ-Hopf 256] {st_hopf_s3}", flush=True)

    # Pick winning closed-form EQ(S^3) strictly on Gaussian OOS mean_cos
    best_eq_s3_name = "leopardi_8c" if st_leo_s3["mean_cos"] >= st_hopf_s3["mean_cos"] else "hopf_hex_4b"
    cb_eq_s3_best = cb_eq_s3_leo if best_eq_s3_name == "leopardi_8c" else cb_eq_s3_hopf

    # Force codebooks on S^3 (K=256): Gravity-only, Coulomb (sweep lam on Gaussian), Yukawa (sweep mu, lam on Gaussian)
    cb_grav_s3 = ops.train_force_spherical_codebook(u4_tr, 256, force_mode="gravity_only", steps=20, seed=42)
    st_grav_s3 = _codebook_oos_stats(cb_grav_s3, u4_oos)
    print(f"  [S^3 Gravity 256] {st_grav_s3}", flush=True)

    best_coul = None
    for lam_c in (0.0005, 0.001, 0.002, 0.005):
        cb_c = ops.train_force_spherical_codebook(u4_tr, 256, force_mode="coulomb", lam=lam_c, steps=20, seed=42)
        st_c = _codebook_oos_stats(cb_c, u4_oos)
        print(f"  [S^3 Coulomb lam={lam_c}] {st_c}", flush=True)
        if best_coul is None or st_c["mean_cos"] > best_coul[0]["mean_cos"]:
            best_coul = (st_c, lam_c, cb_c)

    best_yuk = None
    for mu_y in (3.0, 3.5, 4.0):
        for lam_y in (0.03, 0.05, 0.08):
            cb_y = ops.train_force_spherical_codebook(
                u4_tr, 256, force_mode="yukawa", mu=mu_y, lam=lam_y, steps=20, seed=42
            )
            st_y = _codebook_oos_stats(cb_y, u4_oos)
            print(f"  [S^3 Yukawa mu={mu_y} lam={lam_y}] {st_y}", flush=True)
            if best_yuk is None or st_y["mean_cos"] > best_yuk[0]["mean_cos"]:
                best_yuk = (st_y, mu_y, lam_y, cb_y)

    # S^7 (K=4096 & K=256) analytical EQ(S^7) vs Numerator-pi
    x8 = torch.tensor(rng.standard_normal((24000, 8)), dtype=torch.float32, device=device)
    u8 = x8 / torch.norm(x8, dim=-1, keepdim=True).clamp_min(1e-12)
    cb_num_s7 = ops.build_numerator_pi_s7(256).to(device)
    cb_eq_s7_256 = ops.build_eq_s7_haar(256).to(device)
    cb_eq_s7_4096 = ops.build_eq_s7_haar(4096).to(device)
    st_num_s7 = _codebook_oos_stats(cb_num_s7, u8)
    st_eq_s7_256 = _codebook_oos_stats(cb_eq_s7_256, u8)
    st_eq_s7_4096 = _codebook_oos_stats(cb_eq_s7_4096, u8)
    print(f"  [S^7 Num-pi  256] {st_num_s7}", flush=True)
    print(f"  [S^7 EQ-Haar 256] {st_eq_s7_256}", flush=True)
    print(f"  [S^7 EQ-Haar 4096] {st_eq_s7_4096}", flush=True)

    # Fit universal Gaussian gain codebooks (0b and 2b for S^3, 4b for S^7 K=4096)
    s3_cbs = {
        "num_pi": cb_num_s3,
        "eq_s3_leo": cb_eq_s3_leo,
        "eq_s3_hopf": cb_eq_s3_hopf,
        "gravity_only": cb_grav_s3,
        "coulomb": best_coul[2],
        "yukawa": best_yuk[3],
    }
    s3_gain_cbs: dict[str, dict[str, list[float]]] = {}
    for cname, cb_t in s3_cbs.items():
        s3_gain_cbs[cname] = {
            "0b": ops.fit_universal_gain_cb(cb_t, 0, device=device),
            "2b": ops.fit_universal_gain_cb(cb_t, 2, device=device),
        }
    s7_eq4096_gain_4b = ops.fit_universal_gain_cb(cb_eq_s7_4096, 4, device=device)

    print("\n=== PHASE 1B STEP 2: LIVE PILOT LOCK ON Qwen/Qwen2.5-0.5B ONLY ===", flush=True)
    s49b_cache = Path.home() / ".cache" / "huggingface" / "s49b_eval"
    pins = json.loads((s49b_cache / "pins.json").read_text(encoding="utf-8"))
    q05_dir = pins["Qwen/Qwen2.5-0.5B"]["local_dir"]
    wt_test_text = (s49b_cache / "wikitext2_test.txt").read_text(encoding="utf-8")
    py_test_text, py_sha = _load_python_eval_text()

    tokenizer = AutoTokenizer.from_pretrained(q05_dir, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        q05_dir, local_files_only=True, dtype=torch.bfloat16
    ).to(device)
    model.eval()

    linears = _collect_block_linears(model)
    orig_cpu = {n: m.weight.detach().cpu().clone() for n, m in linears}
    tot_w = sum(int(m.weight.numel()) for _, m in linears)

    wt_chunks = _tokenize_chunks(tokenizer, wt_test_text, N_EVAL_CHUNKS, SEQ_LEN)
    py_chunks = _tokenize_chunks(tokenizer, py_test_text, N_EVAL_CHUNKS, SEQ_LEN)
    ref_wt, base_wt_ppl = _collect_reference_logits(model, wt_chunks, device)
    ref_py, base_py_ppl = _collect_reference_logits(model, py_chunks, device)
    print(f"  Qwen2.5-0.5B BF16 base: WikiPPL={base_wt_ppl:.4f} PyPPL={base_py_ppl:.4f} ({len(linears)} mats, {tot_w:,} wts)", flush=True)

    def _run_pilot_arm(name: str, quant_fn) -> dict[str, Any]:
        tot_err = 0.0
        tot_sig = 0.0
        bpw_num = 0.0
        syn_t = 0
        oob_t = 0
        with torch.no_grad():
            for lname, mod in linears:
                wf = orig_cpu[lname].to(device=device, dtype=torch.float32)
                wq, st = quant_fn(lname, wf)
                dw = wq - wf
                tot_err += float((dw * dw).sum().item())
                tot_sig += float((wf * wf).sum().item())
                bpw_num += float(st["exact_bpw"]) * float(wf.numel())
                syn_t += int(st["syndrome_errors"])
                oob_t += int(st["oob_groups"])
                mod.weight.copy_(wq.to(torch.bfloat16))
                del wf, wq, dw
        wt_s = _score_against_reference(model, wt_chunks, ref_wt, device)
        py_s = _score_against_reference(model, py_chunks, ref_py, device)
        snr = 10.0 * math.log10(max(tot_sig, 1e-30) / max(tot_err, 1e-30))
        avg_bpw = bpw_num / float(tot_w)
        mean_kl_avg = 0.5 * (wt_s["mean_kl"] + py_s["mean_kl"])
        row = {
            "arm": name,
            "exact_bpw": round(avg_bpw, 5),
            "weight_snr_db": round(snr, 4),
            "syndrome_errors": syn_t,
            "oob_groups": oob_t,
            "wikitext2": wt_s,
            "python": py_s,
            "avg_kl": round(mean_kl_avg, 8),
        }
        print(
            f"  [PILOT {name:34s}] bpw={avg_bpw:.4f} SNR={snr:6.3f}dB "
            f"WikiKL={wt_s['mean_kl']:.5f}±{wt_s['se_kl']:.5f} "
            f"PyKL={py_s['mean_kl']:.5f}±{py_s['se_kl']:.5f} syn={syn_t} oob={oob_t}",
            flush=True,
        )
        return row

    pilot_arms: dict[str, Any] = {}

    # Baseline per-128 siliquant A_16 at 3.0 bpw
    pilot_arms["p128_A16_3b"] = _run_pilot_arm(
        "p128_A16_3b",
        lambda _n, wf: ops.quant_per_block_ball_matrix(wf, "3.0", "A16", 128, block_h=0),
    )

    # SphereMap + E_8 linear vs Power-0.7 LUT vs Hodge lambda_perp in {2.0, 4.0}
    lut_e8_3_p07 = torch.tensor(shell_luts["E8_3.0_power07"]["rho"], dtype=torch.float32)
    s_e8_3_p07 = shell_luts["E8_3.0_power07"]["scale_s"]
    lut_a16_3_p07 = torch.tensor(shell_luts["A16_3.0_power07"]["rho"], dtype=torch.float32)
    s_a16_3_p07 = shell_luts["A16_3.0_power07"]["scale_s"]

    def _sp_wrap(fn):
        def _inner(_n, wf):
            w_sp, dr, dc, ex, _, _ = ops.spheremap_forward(wf, block_size=64)
            wq_sp, st = fn(w_sp, ex)
            return ops.spheremap_inverse(wq_sp, dr, dc, block_size=64), st
        return _inner

    pilot_arms["sp_E8_lin_3b"] = _run_pilot_arm(
        "sp_E8_lin_3b",
        _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(wsp, "E8", "3.0", extra_bpw=ex)),
    )
    pilot_arms["sp_E8_pow07_3b"] = _run_pilot_arm(
        "sp_E8_pow07_3b",
        _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(
            wsp, "E8", "3.0", gamma=0.7, scale_s=s_e8_3_p07, shell_lut=lut_e8_3_p07, extra_bpw=ex
        )),
    )
    pilot_arms["sp_E8_hodge2_3b"] = _run_pilot_arm(
        "sp_E8_hodge2_3b",
        _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(
            wsp, "E8", "3.0", hodge_lambda_perp=2.0, extra_bpw=ex
        )),
    )
    pilot_arms["sp_E8_hodge4_3b"] = _run_pilot_arm(
        "sp_E8_hodge4_3b",
        _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(
            wsp, "E8", "3.0", hodge_lambda_perp=4.0, extra_bpw=ex
        )),
    )
    pilot_arms["sp_A16_lin_3b"] = _run_pilot_arm(
        "sp_A16_lin_3b",
        _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(wsp, "A16", "3.0", extra_bpw=ex)),
    )
    pilot_arms["sp_A16_pow07_3b"] = _run_pilot_arm(
        "sp_A16_pow07_3b",
        _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(
            wsp, "A16", "3.0", gamma=0.7, scale_s=s_a16_3_p07, shell_lut=lut_a16_3_p07, extra_bpw=ex
        )),
    )
    pilot_arms["sp_A16_128_3b"] = _run_pilot_arm(
        "sp_A16_128_3b",
        _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(wsp, "A16_128", "3.0", extra_bpw=ex)),
    )
    pilot_arms["sp_A16_pow07_hodge2_3b"] = _run_pilot_arm(
        "sp_A16_pow07_hodge2_3b",
        _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(
            wsp, "A16", "3.0", gamma=0.7, scale_s=s_a16_3_p07, shell_lut=lut_a16_3_p07,
            hodge_lambda_perp=2.0, extra_bpw=ex
        )),
    )
    pilot_arms["sp_A16_128_hodge2_3b"] = _run_pilot_arm(
        "sp_A16_128_hodge2_3b",
        _sp_wrap(lambda wsp, ex: ops.quant_global_ball_matrix(
            wsp, "A16_128", "3.0", hodge_lambda_perp=2.0, extra_bpw=ex
        )),
    )

    # Lock Hodge lambda_perp in {2.0, 4.0} strictly from Qwen2.5-0.5B avg_kl!
    locked_hodge_lambda = (
        2.0 if pilot_arms["sp_E8_hodge2_3b"]["avg_kl"] <= pilot_arms["sp_E8_hodge4_3b"]["avg_kl"] else 4.0
    )

    # Lock H4 conjunction strictly from Phase-1B winners (anti-bloat rule!)
    h4_candidates = {
        "sp_A16_128": pilot_arms["sp_A16_128_3b"]["avg_kl"],
        "sp_A16_128_hodge": pilot_arms["sp_A16_128_hodge2_3b"]["avg_kl"],
        "sp_A16_pow07": pilot_arms["sp_A16_pow07_3b"]["avg_kl"],
        "sp_A16_pow07_hodge": pilot_arms["sp_A16_pow07_hodge2_3b"]["avg_kl"],
        "sp_E8_pow07": pilot_arms["sp_E8_pow07_3b"]["avg_kl"],
    }
    # Always include SphereMap + best high-dim lattice + winning H3 operator(s) that improved 0.5B KL
    use_pow07_in_h4 = (
        pilot_arms["sp_E8_pow07_3b"]["avg_kl"] < pilot_arms["sp_E8_lin_3b"]["avg_kl"]
        or pilot_arms["sp_A16_pow07_3b"]["avg_kl"] < pilot_arms["sp_A16_lin_3b"]["avg_kl"]
    )
    use_hodge_in_h4 = (
        min(pilot_arms["sp_E8_hodge2_3b"]["avg_kl"], pilot_arms["sp_E8_hodge4_3b"]["avg_kl"])
        < pilot_arms["sp_E8_lin_3b"]["avg_kl"]
    )
    h4_best_3b_arm = min(h4_candidates, key=lambda k: h4_candidates[k])

    frozen_obj: dict[str, Any] = {
        "schema": "aletheia.track_s106.frozen_pilot_params.v1",
        "preregistration_sha256": prereg_sha,
        "locked_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pilot_models_used": ["synthetic_gaussian_N01", "Qwen/Qwen2.5-0.5B"],
        "held_out_models_touched": [],
        "eval_seed": EVAL_SEED,
        "python_stdlib_sha256": py_sha,
        "lm_gauss_1d": lm_gauss,
        "shell_luts": shell_luts,
        "locked_constants": {
            "spheremap_sinkhorn_iters": 8,
            "spheremap_hadamard_block": 64,
            "h3a_gamma": 0.7,
            "h3b_hodge_lambda_perp": locked_hodge_lambda,
            "h2a_best_eq_s3_variant": best_eq_s3_name,
            "h3c_coulomb_lam": best_coul[1],
            "h3c_yukawa_mu": best_yuk[1],
            "h3c_yukawa_lam": best_yuk[2],
            "h4_use_pow07": use_pow07_in_h4,
            "h4_use_hodge": use_hodge_in_h4,
            "h4_best_3b_pilot_recipe": h4_best_3b_arm,
        },
        "s3_gaussian_oos_geometry": {
            "num_pi_256": st_num_s3,
            "eq_s3_leopardi_256": st_leo_s3,
            "eq_s3_hopf_hex_256": st_hopf_s3,
            "gravity_only_256": st_grav_s3,
            "coulomb_256": best_coul[0],
            "yukawa_256": best_yuk[0],
        },
        "s7_gaussian_oos_geometry": {
            "num_pi_256": st_num_s7,
            "eq_s7_haar_256": st_eq_s7_256,
            "eq_s7_haar_4096": st_eq_s7_4096,
        },
        "frozen_s3_codebooks": {
            "gravity_only_256": [[round(float(x), 7) for x in row] for row in cb_grav_s3.cpu().tolist()],
            "coulomb_256": [[round(float(x), 7) for x in row] for row in best_coul[2].cpu().tolist()],
            "yukawa_256": [[round(float(x), 7) for x in row] for row in best_yuk[3].cpu().tolist()],
        },
        "frozen_gain_codebooks": {
            "s3": s3_gain_cbs,
            "s7_eq4096_4b": s7_eq4096_gain_4b,
        },
        "pilot_qwen05b_results": {
            "base_wikitext2_ppl": round(base_wt_ppl, 6),
            "base_python_ppl": round(base_py_ppl, 6),
            "arms": pilot_arms,
        },
        "elapsed_seconds": round(time.monotonic() - t0, 3),
    }

    canon_payload = json.dumps(frozen_obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    frozen_obj["pilot_params_sha256"] = hashlib.sha256(canon_payload).hexdigest()

    out_path = here / "s106_frozen_pilot_params.json"
    out_bytes = (json.dumps(frozen_obj, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    out_path.write_bytes(out_bytes)
    os.chmod(out_path, 0o600)
    file_sha = hashlib.sha256(out_bytes).hexdigest()

    print(f"\n=== PHASE 1B PILOT LOCKED ===", flush=True)
    print(f"  LOCKED CONSTANTS: {json.dumps(frozen_obj['locked_constants'])}", flush=True)
    print(f"  FILE: {out_path.name} ({len(out_bytes)} B, mode=0o600, file_sha256={file_sha})", flush=True)
    print(f"  INNER pilot_params_sha256={frozen_obj['pilot_params_sha256']}", flush=True)

    del model, ref_wt, ref_py, orig_cpu
    gc.collect()
    torch.cuda.empty_cache()
    return 0


if __name__ == "__main__":
    sys.exit(main())
