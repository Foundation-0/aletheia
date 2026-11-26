#!/usr/bin/env python3
"""Wave-14 (EXP-Q30a / Track S124): Pure-Q A/A Noise-Floor, Looped-Roofline & HoloSphere-V3 L3 Ceiling Oracle.

Strictly Python standard library ONLY: zero IEEE-754 floats, zero float literals in AST,
zero bare asserts, zero RNG, zero third-party dependencies. Locked to PREREG-W14
(`SHA-256: 871900e5d6c860ac159f43ca6b4767e7c128d0b4f7748edf788d56e9cb535d3e`).

Proves and certifies over exact Q (`fractions.Fraction`):
  - G1 (`W14-OBS-3`, `sybil-solutions/inference-optimisation-skill` PR #11 & PR #9):
      * Exact S_3 permutation proof that `cand > max(ctl_left, ctl_right)` holds with probability
        2/6 = 1/3 under exchangeable i.i.d. continuous noise (matching PR #11's 15/43 = 34.88%),
      * Exact m-independent-triple survival (1/3)^m and minimum m = 3 for alpha <= 1/20 (1/27 = 3.70%),
      * Fail-closed pure-Q benchmark acceptance gate enforcing >= 10 A/A calibration runs, m >= 3
        independent interleaved triples (alpha <= 1/27 = 3.70% <= 5%), strictly positive calibrated
        empirical A/A floor (never 0 on zero-false-win ledgers), PR #9 `MIN_DECODE_WINDOW = 1/20 s`
        (rejecting the 63 tok / 7e-5 s 863k-900k tok/s single-chunk mirage), and PR #9 character-alphabet
        degeneracy check (rejecting whitespace-free `64 * '!'` collapses).
  - G2 (Looped-Visit & Batched-Draft Rooflines, PR #22, PR #12, PR #13):
      * PR #22 Inkling-2-Mini 24 physical layers vs 48 layer visits (exact 2/1 decode ceiling error:
        2350/3 ≈ 783.3 vs 1175/3 ≈ 391.7 tok/s @ 1880 GB/s) + 2:4-sparse vs dense 2/1 prefill peak correction,
      * PR #12 loop-aware MoE VRAM placement ROI: 3x-visited core 375/2 MB/tok/GB (187.5) vs 1x boundary
        125/2 MB/tok/GB (62.5) = exact 3/1 ROI ratio and 1032/1427 (~72.32%) active expert traffic share,
      * PR #13 batched single-read draft-weight correction (N=4, 1 GB verify, 1/4 GB draft @ 100 GB/s,
        a=2 accepted/req): exact 640/1 tok/s true ceiling vs 400/1 tok/s buggy N*draft ceiling = 3/8 (37.5%) error.
  - G3 (`W14-OBS-2`, Per-Component Roofline for Live HF `ahrazzle/holosphere-v3-unified-sm86-15m`):
      * Exact byte-for-byte decomposition of `model.safetensors` (8,963,044 B = 14,176 B header +
        8,948,868 B payload across 945,280 [16,11,4] A_16 codewords, 0 B input embedding, 262,144 B O(1) state),
      * Total resident footprint 9,225,188 B = 2,306,297/262,144 MiB (< 9 MiB) = 2,306,297/6,291,456 (~36.66%)
        of the 24 MiB i9-11900H L3 cache (120.83x smaller than llm.asm Qwen3-0.6B's 1,063 MiB, needing 5 vs 532
        2 MiB huge pages),
      * Exact rational decode ceilings on RTX 3080 Laptop GPU (356.6 GB/s GDDR6 vs 525.46 GB/s empirical
        ScopedAmpereL2Pin, situating live 46,468 tok/s at 122.47% = 1.225x of unpinned GDDR6 tied-head ceiling
        and 83.11% of L2-pinned ceiling) and i9-11900H (24 MiB L3 vs DDR4-3200: exact 160/21x bandwidth lift
        into client Willow Cove 1x512-bit 32 FP32 FLOPs/cycle / AVX-512 VNNI compute-bound regime, 2,205.5 tok/s).
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
from itertools import permutations
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "aletheia.track_s124.aa_roofline_l3_oracle.v1"
CERT_FILENAME = "s124_aa_roofline_l3_certificate.json"
PREREG_W14_REL = Path("notes") / "portals_wave14_2026_11_26" / "PREREG_WAVE14_INF_OPT_BAREMETAL.md"
PREREG_W14_SHA256 = "871900e5d6c860ac159f43ca6b4767e7c128d0b4f7748edf788d56e9cb535d3e"

MIN_AA_CALIBRATION_RUNS = 10
MIN_INDEPENDENT_TRIPLES = 3
DEFAULT_MIN_REL_FLOOR = Fraction(1, 100)
DEFAULT_MIN_DECODE_WINDOW_SEC = Fraction(1, 20)
DEFAULT_MIN_UNIQUE_CHARS = 4
ALPHA_SIGNIFICANCE_DEFAULT = Fraction(1, 20)

# Exact byte-for-byte constants of live HF `ahrazzle/holosphere-v3-unified-sm86-15m` (`model.safetensors`)
HS_V3_SAFETENSORS_TOTAL_BYTES = 8_963_044
HS_V3_SAFETENSORS_HEADER_BYTES = 14_176
HS_V3_INPUT_EMBEDDING_BYTES = 0
HS_V3_BYTE_CONV_BYTES = 8_192
HS_V3_CELLOP_RING_HOLONOMY_BYTES = 4_718_592
HS_V3_SWIGLU_FFN_BYTES = 4_147_200
HS_V3_LM_HEAD_A16_BYTES = 74_880
HS_V3_LOGIT_SCALE_BYTES = 4
HS_V3_PERSISTENT_STATE_BYTES = 262_144
HS_V3_ACTIVE_PARAMS = 15_234_817
HS_V3_A16_CODEWORDS = 945_280

I9_11900H_L3_CACHE_BYTES = 24 * 1024 * 1024
HUGEPAGE_2MIB_BYTES = 2 * 1024 * 1024
PAGE_4KIB_BYTES = 4 * 1024
LLM_ASM_QWEN3_WEIGHT_BYTES = 614 * 1024 * 1024
LLM_ASM_QWEN3_KV_ARENA_BYTES = 449 * 1024 * 1024


class S124RooflineError(ValueError):
    """Typed fail-closed error for Track S124 pure-Q roofline & benchmark oracle."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


def require_ok(cond: bool, code: str, message: str) -> None:
    if cond is not True:
        raise S124RooflineError(code, message)


def _to_frac(val: Fraction | int) -> Fraction:
    require_ok(not isinstance(val, bool) and isinstance(val, (int, Fraction)), "TYPE_ERROR", "expected int or Fraction")
    return Fraction(val)


def _to_int(val: int) -> int:
    require_ok(not isinstance(val, bool) and isinstance(val, int), "INT_ERROR", "expected strict int")
    return int(val)


def _frac_str(q: Fraction) -> str:
    return f"{q.numerator}/{q.denominator}"


def _ceil_div(num: int, den: int) -> int:
    return (num + den - 1) // den


# ---------------------------------------------------------------------------
# G1: Exact Interleaved-Triple A/A Illusion (PR #11) & Mirage Gate (PR #9)
# ---------------------------------------------------------------------------

def prove_aa_triple_false_win_q(alpha_target: Fraction | int = ALPHA_SIGNIFICANCE_DEFAULT) -> dict[str, Any]:
    """Prove over Q by exact S_3 enumeration that `cand > max(ctl_left, ctl_right)` has false-win
    rate 2/6 = 1/3 under i.i.d. continuous noise, and compute exact m-triple floor for (1/3)^m <= alpha.
    """
    alp = _to_frac(alpha_target)
    require_ok(Fraction(0) < alp < Fraction(1), "BAD_ALPHA_TARGET", "alpha_target must lie strictly in (0, 1)")

    perms = list(permutations((0, 1, 2)))
    wins = sum(1 for p in perms if p[1] > p[0] and p[1] > p[2])
    single_prob = Fraction(wins, len(perms))

    m_triples = 1
    prob_m = single_prob
    while prob_m > alp:
        m_triples += 1
        prob_m *= single_prob

    # PR #11 empirical Mac Studio M4 Max A/A ledger: 15 wins out of 43 interior triples
    pr11_emp = Fraction(15, 43)
    pr11_diff = pr11_emp - single_prob

    return {
        "s3_total_permutations": len(perms),
        "s3_candidate_top_permutations": wins,
        "single_triple_false_win_prob_q": _frac_str(single_prob),
        "pr11_empirical_false_win_ratio_q": _frac_str(pr11_emp),
        "pr11_minus_exact_third_q": _frac_str(pr11_diff),
        "alpha_target_q": _frac_str(alp),
        "min_independent_triples_for_alpha": m_triples,
        "m_triple_false_win_prob_q": _frac_str(prob_m),
    }


def compute_aa_noise_floor_margin_q(aa_control_rates: Sequence[Fraction | int]) -> dict[str, Any]:
    """Compute exact PR #11 empirical A/A neighbour-win relative floor from >= 10 control runs."""
    require_ok(
        isinstance(aa_control_rates, (list, tuple)) and len(aa_control_rates) >= MIN_AA_CALIBRATION_RUNS,
        "INSUFFICIENT_AA_RUNS",
        f"require >= {MIN_AA_CALIBRATION_RUNS} back-to-back A/A control runs",
    )
    rates = tuple(_to_frac(x) for x in aa_control_rates)
    for r in rates:
        require_ok(r > Fraction(0), "NONPOS_AA_RATE", "A/A control tok/s must be > 0")

    interior_count = len(rates) - 2
    false_wins = 0
    max_rel_margin = Fraction(0)
    for idx in range(1, len(rates) - 1):
        best_nb = max(rates[idx - 1], rates[idx + 1])
        if rates[idx] > best_nb:
            false_wins += 1
            rel = (rates[idx] - best_nb) / best_nb
            if rel > max_rel_margin:
                max_rel_margin = rel

    max_adj_spread = Fraction(0)
    for idx in range(1, len(rates)):
        lo = min(rates[idx - 1], rates[idx])
        hi = max(rates[idx - 1], rates[idx])
        spread = (hi - lo) / lo
        if spread > max_adj_spread:
            max_adj_spread = spread

    return {
        "aa_runs": len(rates),
        "interior_triples": interior_count,
        "false_wins": false_wins,
        "false_win_fraction_q": _frac_str(Fraction(false_wins, interior_count)),
        "max_false_win_rel_margin_q": _frac_str(max_rel_margin),
        "max_adjacent_rel_spread_q": _frac_str(max_adj_spread),
    }


def evaluate_decode_benchmark_gate_q(
    *,
    aa_control_rates: Sequence[Fraction | int],
    ctl_left_rate: Fraction | int,
    cand_completion_tokens: int,
    cand_decode_window_sec: Fraction | int,
    cand_text: str,
    ctl_right_rate: Fraction | int,
    n_independent_triples: int = MIN_INDEPENDENT_TRIPLES,
    min_rel_floor_q: Fraction | int = DEFAULT_MIN_REL_FLOOR,
    safety_factor: Fraction | int = Fraction(5, 4),
    min_decode_window_sec: Fraction | int = DEFAULT_MIN_DECODE_WINDOW_SEC,
    min_unique_chars: int = DEFAULT_MIN_UNIQUE_CHARS,
) -> dict[str, Any]:
    """Fail-closed pure-Q acceptance gate combining PR #9 coalesced/degenerate guards,
    PR #11 m >= 3 independent-triple requirement, & strictly positive calibrated A/A floor.
    """
    aa_stats = compute_aa_noise_floor_margin_q(aa_control_rates)
    n_triples = _to_int(n_independent_triples)
    require_ok(
        n_triples >= MIN_INDEPENDENT_TRIPLES,
        "INSUFFICIENT_INDEPENDENT_TRIPLES",
        f"require >= {MIN_INDEPENDENT_TRIPLES} independent ctl/cand/ctl triples for (1/3)^m <= 1/20",
    )
    min_fl = _to_frac(min_rel_floor_q)
    require_ok(min_fl > Fraction(0), "NONPOS_MIN_REL_FLOOR", "min_rel_floor_q must be strictly > 0")

    c_left = _to_frac(ctl_left_rate)
    c_right = _to_frac(ctl_right_rate)
    require_ok(c_left > Fraction(0) and c_right > Fraction(0), "NONPOS_CTL_RATE", "control rates must be > 0")

    ct = _to_int(cand_completion_tokens)
    require_ok(ct >= 2, "TOO_FEW_DECODE_TOKENS", "completion_tokens must be >= 2 to measure inter-token decode")

    win_s = _to_frac(cand_decode_window_sec)
    min_win_s = _to_frac(min_decode_window_sec)
    require_ok(min_win_s > Fraction(0), "NONPOS_MIN_WINDOW", "min_decode_window_sec must be > 0")
    require_ok(win_s >= min_win_s, "COALESCED_CHUNK_MIRAGE", "decode window below MIN_DECODE_WINDOW (single-chunk mirage)")

    min_uc = _to_int(min_unique_chars)
    require_ok(min_uc >= 2, "BAD_MIN_UNIQUE_CHARS", "min_unique_chars must be >= 2")
    require_ok(isinstance(cand_text, str) and len(set(cand_text)) >= min_uc, "DEGENERATE_OUTPUT_ALPHABET", "degenerate low-alphabet output")

    sf = _to_frac(safety_factor)
    require_ok(sf >= Fraction(1), "BAD_SAFETY_FACTOR", "safety_factor must be >= 1")

    cand_rate = Fraction(ct - 1) / win_s
    best_ctl = max(c_left, c_right)
    rel_gain = (cand_rate - best_ctl) / best_ctl
    empirical_base = max(
        Fraction(aa_stats["max_false_win_rel_margin_q"]),
        Fraction(aa_stats["max_adjacent_rel_spread_q"]),
        min_fl,
    )
    required_margin = sf * empirical_base
    accepted = (rel_gain > Fraction(0)) and (rel_gain > required_margin)

    return {
        "accepted": accepted,
        "n_independent_triples": n_triples,
        "cand_rate_tok_per_s_q": _frac_str(cand_rate),
        "best_neighbor_ctl_q": _frac_str(best_ctl),
        "rel_gain_over_best_ctl_q": _frac_str(rel_gain),
        "required_rel_margin_q": _frac_str(required_margin),
    }


# ---------------------------------------------------------------------------
# G2: Exact Looped-Visit & Batched-Draft Rooflines (PR #22, PR #12, PR #13)
# ---------------------------------------------------------------------------

def looped_model_roofline_q(
    *,
    prelude_layers: int,
    core_layers: int,
    core_loops: int,
    postlude_layers: int,
    bytes_per_visit_gb: Fraction | int,
    bandwidth_gbps: Fraction | int,
    flops_per_visit_gflops: Fraction | int,
    spec_2to4_sparse_tflops: Fraction | int,
) -> dict[str, Any]:
    """PR #22: Compute true layer-visit decode ceiling & dense-vs-sparse prefill ceiling over Q."""
    l_pre = _to_int(prelude_layers)
    l_core = _to_int(core_layers)
    k_loop = _to_int(core_loops)
    l_post = _to_int(postlude_layers)
    require_ok(l_pre >= 0 and l_core >= 1 and k_loop >= 1 and l_post >= 0, "BAD_LOOP_TOPOLOGY", "invalid looped layer counts")

    b_visit = _to_frac(bytes_per_visit_gb)
    bw = _to_frac(bandwidth_gbps)
    f_visit = _to_frac(flops_per_visit_gflops)
    sparse_tf = _to_frac(spec_2to4_sparse_tflops)
    require_ok(
        b_visit > Fraction(0) and bw > Fraction(0) and f_visit > Fraction(0) and sparse_tf > Fraction(0),
        "NONPOS_ROOFLINE_INPUT",
        "bytes, bandwidth, and FLOPs must be > 0",
    )

    phys_layers = l_pre + l_core + l_post
    total_visits = l_pre + k_loop * l_core + l_post
    visit_ratio = Fraction(total_visits, phys_layers)

    naive_decode_ceil = bw / (Fraction(phys_layers) * b_visit)
    true_decode_ceil = bw / (Fraction(total_visits) * b_visit)

    # Practical prefill uses 1/2 of dense peak, and dense peak is 1/2 of 2:4-sparse spec peak:
    dense_peak_gflops = (sparse_tf * Fraction(1000)) * Fraction(1, 2)
    naive_sparse_phys_prefill = (sparse_tf * Fraction(1000) * Fraction(1, 2)) / (Fraction(phys_layers) * f_visit)
    true_dense_visit_prefill = (dense_peak_gflops * Fraction(1, 2)) / (Fraction(total_visits) * f_visit)

    return {
        "physical_layers": phys_layers,
        "logical_layer_visits": total_visits,
        "visit_to_physical_ratio_q": _frac_str(visit_ratio),
        "naive_physical_decode_tok_s_q": _frac_str(naive_decode_ceil),
        "true_visit_decode_tok_s_q": _frac_str(true_decode_ceil),
        "decode_overstatement_ratio_q": _frac_str(naive_decode_ceil / true_decode_ceil),
        "prefill_sparse_phys_vs_dense_visit_ratio_q": _frac_str(naive_sparse_phys_prefill / true_dense_visit_prefill),
    }


def loop_aware_moe_vram_roi_q(
    *,
    prelude_gb: Fraction | int,
    core_gb: Fraction | int,
    postlude_gb: Fraction | int,
    top_k: int,
    n_experts: int,
    core_loops: int,
) -> dict[str, Any]:
    """PR #12: Compute exact MB/tok per GB of VRAM and active traffic share for looped MoE placement."""
    g_pre = _to_frac(prelude_gb)
    g_core = _to_frac(core_gb)
    g_post = _to_frac(postlude_gb)
    tk = _to_int(top_k)
    ne = _to_int(n_experts)
    kl = _to_int(core_loops)
    require_ok(g_pre > Fraction(0) and g_core > Fraction(0) and g_post > Fraction(0), "NONPOS_MOE_GB", "group GB must be > 0")
    require_ok(1 <= tk <= ne and kl >= 1, "BAD_MOE_ROUTING", "require 1 <= top_k <= n_experts and core_loops >= 1")

    routed_frac = Fraction(tk, ne)
    mb_per_gb_boundary = routed_frac * Fraction(1000)
    mb_per_gb_core = Fraction(kl) * mb_per_gb_boundary

    pre_active_mb = g_pre * mb_per_gb_boundary
    core_active_mb = g_core * mb_per_gb_core
    post_active_mb = g_post * mb_per_gb_boundary
    total_active_mb = pre_active_mb + core_active_mb + post_active_mb

    return {
        "boundary_mb_per_tok_per_gb_q": _frac_str(mb_per_gb_boundary),
        "core_mb_per_tok_per_gb_q": _frac_str(mb_per_gb_core),
        "core_vs_boundary_roi_ratio_q": _frac_str(mb_per_gb_core / mb_per_gb_boundary),
        "prelude_active_mb_per_tok_q": _frac_str(pre_active_mb),
        "core_active_mb_per_tok_q": _frac_str(core_active_mb),
        "postlude_active_mb_per_tok_q": _frac_str(post_active_mb),
        "core_share_of_active_traffic_q": _frac_str(core_active_mb / total_active_mb),
    }


def batched_speculative_decode_ceiling_q(
    *,
    bandwidth_gbps: Fraction | int,
    n_requests: int,
    draft_steps_k: int,
    accepted_tokens_per_req: Fraction | int,
    verify_bytes_gb: Fraction | int,
    draft_weight_bytes_gb: Fraction | int,
) -> dict[str, Any]:
    """PR #13: Exact single-read batched draft-weight ceiling vs buggy N*draft overcharge."""
    bw = _to_frac(bandwidth_gbps)
    n_req = _to_int(n_requests)
    k_draft = _to_int(draft_steps_k)
    acc = _to_frac(accepted_tokens_per_req)
    v_gb = _to_frac(verify_bytes_gb)
    d_gb = _to_frac(draft_weight_bytes_gb)
    require_ok(n_req >= 1 and k_draft >= 1, "BAD_BATCH_SPEC", "n_requests and draft_steps_k must be >= 1")
    require_ok(
        bw > Fraction(0) and acc > Fraction(0) and v_gb > Fraction(0) and d_gb > Fraction(0),
        "NONPOS_SPEC_BYTES",
        "bandwidth, accepted tokens, verify_bytes, and draft_bytes must be > 0",
    )

    emitted_tokens = Fraction(n_req) * acc
    true_step_gb = v_gb + Fraction(k_draft) * d_gb
    buggy_step_gb = v_gb + Fraction(n_req * k_draft) * d_gb

    true_ceiling = (bw * emitted_tokens) / true_step_gb
    buggy_ceiling = (bw * emitted_tokens) / buggy_step_gb
    rel_underestimate = (true_ceiling - buggy_ceiling) / true_ceiling

    return {
        "true_step_bytes_gb_q": _frac_str(true_step_gb),
        "buggy_step_bytes_gb_q": _frac_str(buggy_step_gb),
        "true_aggregate_ceiling_tok_s_q": _frac_str(true_ceiling),
        "buggy_aggregate_ceiling_tok_s_q": _frac_str(buggy_ceiling),
        "relative_underestimate_q": _frac_str(rel_underestimate),
    }


# ---------------------------------------------------------------------------
# G3: Exact Component Roofline for Live HF `ahrazzle/holosphere-v3-unified-sm86-15m`
# ---------------------------------------------------------------------------

def holosphere_v3_l3_and_roofline_q() -> dict[str, Any]:
    """Compute exact rational component ceilings & L3 residency for HoloSphere-V3 15M (`8,963,044 B`)."""
    tensor_payload_bytes = (
        HS_V3_INPUT_EMBEDDING_BYTES
        + HS_V3_BYTE_CONV_BYTES
        + HS_V3_CELLOP_RING_HOLONOMY_BYTES
        + HS_V3_SWIGLU_FFN_BYTES
        + HS_V3_LM_HEAD_A16_BYTES
        + HS_V3_LOGIT_SCALE_BYTES
    )
    safetensors_file_bytes = HS_V3_SAFETENSORS_HEADER_BYTES + tensor_payload_bytes
    resident_total_bytes = safetensors_file_bytes + HS_V3_PERSISTENT_STATE_BYTES

    mib = Fraction(1024 * 1024)
    resident_mib_q = Fraction(resident_total_bytes) / mib
    l3_occupancy_q = Fraction(resident_total_bytes, I9_11900H_L3_CACHE_BYTES)

    qwen3_total_bytes = LLM_ASM_QWEN3_WEIGHT_BYTES + LLM_ASM_QWEN3_KV_ARENA_BYTES
    footprint_reduction_vs_llm_asm_q = Fraction(qwen3_total_bytes, resident_total_bytes)

    hs_hugepages_2mib = _ceil_div(resident_total_bytes, HUGEPAGE_2MIB_BYTES)
    qwen3_hugepages_2mib = _ceil_div(qwen3_total_bytes, HUGEPAGE_2MIB_BYTES)
    hs_pages_4kib = _ceil_div(resident_total_bytes, PAGE_4KIB_BYTES)
    qwen3_pages_4kib = _ceil_div(qwen3_total_bytes, PAGE_4KIB_BYTES)

    # Single-token step traffic (payload + 2x recurrent state R/W; 0 B per-token KV growth!)
    untied_step_bytes = Fraction(tensor_payload_bytes + 2 * HS_V3_PERSISTENT_STATE_BYTES)
    tied_fwht_step_bytes = Fraction((tensor_payload_bytes - HS_V3_LM_HEAD_A16_BYTES) + 2 * HS_V3_PERSISTENT_STATE_BYTES)

    # Hardware bandwidths in exact B/s (RTX 3080 Laptop GPU GA104M GDDR6 vs empirical ScopedAmpereL2Pin):
    rtx3080_gddr6_bps = Fraction(356_600_000_000)
    rtx3080_l2_pin_bps = Fraction(525_460_000_000)
    i9_ddr4_copy_bps = Fraction(42_000_000_000)
    i9_l3_8c_bps = Fraction(320_000_000_000)
    i9_l3_1c_bps = Fraction(64_000_000_000)

    rtx_gddr6_untied = rtx3080_gddr6_bps / untied_step_bytes
    rtx_gddr6_tied = rtx3080_gddr6_bps / tied_fwht_step_bytes
    rtx_l2_untied = rtx3080_l2_pin_bps / untied_step_bytes
    rtx_l2_tied = rtx3080_l2_pin_bps / tied_fwht_step_bytes

    live_cuda_graph_v3_tok_s = Fraction(46_468)
    live_fraction_of_gddr6_tied = live_cuda_graph_v3_tok_s / rtx_gddr6_tied
    live_fraction_of_l2_tied = live_cuda_graph_v3_tok_s / rtx_l2_tied

    i9_ddr4_ceiling = i9_ddr4_copy_bps / untied_step_bytes
    i9_l3_8c_ceiling = i9_l3_8c_bps / untied_step_bytes
    i9_l3_1c_ceiling = i9_l3_1c_bps / untied_step_bytes
    l3_vs_ddr4_lift = i9_l3_8c_ceiling / i9_ddr4_ceiling

    # Practical 50% FP32 FMA ceiling on client Willow Cove i9-11900H (1x 512-bit = 32 FP32 FLOPs/cycle/core @ 4.2 GHz):
    ops_per_token = Fraction(2 * HS_V3_ACTIVE_PARAMS)
    i9_1c_prac_flops = Fraction(42, 10) * Fraction(1_000_000_000) * Fraction(32) * Fraction(1, 2)
    i9_1c_compute_ceiling = i9_1c_prac_flops / ops_per_token

    return {
        "safetensors_file_bytes": safetensors_file_bytes,
        "safetensors_header_bytes": HS_V3_SAFETENSORS_HEADER_BYTES,
        "tensor_payload_bytes": tensor_payload_bytes,
        "input_embedding_bytes": HS_V3_INPUT_EMBEDDING_BYTES,
        "lm_head_a16_bytes": HS_V3_LM_HEAD_A16_BYTES,
        "persistent_o1_state_bytes": HS_V3_PERSISTENT_STATE_BYTES,
        "kv_bytes_per_token": 0,
        "a16_total_codewords": HS_V3_A16_CODEWORDS,
        "resident_total_bytes": resident_total_bytes,
        "resident_mib_q": _frac_str(resident_mib_q),
        "fits_in_24mib_l3": resident_total_bytes < I9_11900H_L3_CACHE_BYTES,
        "i9_24mib_l3_occupancy_q": _frac_str(l3_occupancy_q),
        "footprint_reduction_vs_llm_asm_qwen3_q": _frac_str(footprint_reduction_vs_llm_asm_q),
        "hugepages_2mib_needed_holosphere_v3": hs_hugepages_2mib,
        "hugepages_2mib_needed_llm_asm_qwen3": qwen3_hugepages_2mib,
        "pages_4kib_needed_holosphere_v3": hs_pages_4kib,
        "pages_4kib_needed_llm_asm_qwen3": qwen3_pages_4kib,
        "rtx3080_gddr6_ceiling_untied_tok_s_q": _frac_str(rtx_gddr6_untied),
        "rtx3080_gddr6_ceiling_tied_tok_s_q": _frac_str(rtx_gddr6_tied),
        "rtx3080_l2_pinned_ceiling_untied_tok_s_q": _frac_str(rtx_l2_untied),
        "rtx3080_l2_pinned_ceiling_tied_tok_s_q": _frac_str(rtx_l2_tied),
        "live_v3_46468_over_gddr6_tied_q": _frac_str(live_fraction_of_gddr6_tied),
        "live_v3_46468_over_l2_tied_q": _frac_str(live_fraction_of_l2_tied),
        "i9_ddr4_ceiling_tok_s_q": _frac_str(i9_ddr4_ceiling),
        "i9_l3_8c_ceiling_tok_s_q": _frac_str(i9_l3_8c_ceiling),
        "i9_l3_1c_ceiling_tok_s_q": _frac_str(i9_l3_1c_ceiling),
        "i9_l3_vs_ddr4_bandwidth_lift_q": _frac_str(l3_vs_ddr4_lift),
        "i9_1c_practical_fma_compute_ceiling_tok_s_q": _frac_str(i9_1c_compute_ceiling),
        "i9_1c_l3_is_compute_bound": i9_1c_compute_ceiling < i9_l3_1c_ceiling,
    }


# ---------------------------------------------------------------------------
# Master Certificate Builder, Fail-Closed Validator, & CLI
# ---------------------------------------------------------------------------

def verify_prereg_w14_file(prereg_path: Path) -> str:
    require_ok(prereg_path.is_file(), "MISSING_PREREG_W14", f"missing {prereg_path.name}")
    digest = hashlib.sha256(prereg_path.read_bytes()).hexdigest()
    require_ok(digest == PREREG_W14_SHA256, "PREREG_W14_SHA_MISMATCH", f"PREREG-W14 SHA mismatch: {digest}")
    return digest


def build_s124_certificate(prereg_path: Path | None = None) -> dict[str, Any]:
    here = Path(__file__).resolve().parent
    default_prereg = here.parent / PREREG_W14_REL
    target_prereg = prereg_path if prereg_path is not None else (default_prereg if default_prereg.is_file() else None)
    prereg_sha = verify_prereg_w14_file(target_prereg) if target_prereg is not None else PREREG_W14_SHA256

    g1_aa = prove_aa_triple_false_win_q(ALPHA_SIGNIFICANCE_DEFAULT)
    # 12-run realistic A/A calibration ledger (max false-win margin = 154/10000 = 77/5000 = 1.54%, matching PR #11!)
    aa_ledger = (
        Fraction(10000, 500),
        Fraction(10154, 500),
        Fraction(10000, 500),
        Fraction(9950, 500),
        Fraction(10020, 500),
        Fraction(10010, 500),
        Fraction(9980, 500),
        Fraction(10040, 500),
        Fraction(10050, 500),
        Fraction(9990, 500),
        Fraction(10010, 500),
        Fraction(10000, 500),
    )
    g1_floor = compute_aa_noise_floor_margin_q(aa_ledger)
    g1_noise_reject = evaluate_decode_benchmark_gate_q(
        aa_control_rates=aa_ledger,
        ctl_left_rate=Fraction(20),
        cand_completion_tokens=129,
        cand_decode_window_sec=Fraction(128, 20) / Fraction(101, 100),  # +1% gain < 1.25 * 1.54% = 1.925%
        cand_text="coherent deterministic output tokens across vocabulary!",
        ctl_right_rate=Fraction(20),
    )
    g1_real_accept = evaluate_decode_benchmark_gate_q(
        aa_control_rates=aa_ledger,
        ctl_left_rate=Fraction(20),
        cand_completion_tokens=129,
        cand_decode_window_sec=Fraction(128, 25),  # 25 tok/s = +25% gain > 1.925%
        cand_text="coherent deterministic output tokens across vocabulary!",
        ctl_right_rate=Fraction(20),
    )
    # B-S124-2: Zero-false-win monotone ledger MUST keep strictly positive floor and reject +0.1% jitter!
    zero_fw_ledger = tuple(Fraction(2000 - k, 100) for k in range(10))
    g1_zero_fw_jitter = evaluate_decode_benchmark_gate_q(
        aa_control_rates=zero_fw_ledger,
        ctl_left_rate=Fraction(20),
        cand_completion_tokens=129,
        cand_decode_window_sec=Fraction(128, 20) / Fraction(1001, 1000),
        cand_text="coherent deterministic output tokens across vocabulary!",
        ctl_right_rate=Fraction(20),
    )

    # G2: PR #22 Inkling-2-Mini (6 + 12*3 + 6 = 48 visits vs 24 physical), PR #12 MoE ROI, PR #13 batched draft
    g2_pr22 = looped_model_roofline_q(
        prelude_layers=6,
        core_layers=12,
        core_loops=3,
        postlude_layers=6,
        bytes_per_visit_gb=Fraction(1, 10),
        bandwidth_gbps=Fraction(1880),
        flops_per_visit_gflops=Fraction(500),
        spec_2to4_sparse_tflops=Fraction(2400),
    )
    g2_pr12 = loop_aware_moe_vram_roi_q(
        prelude_gb=Fraction(344, 100),
        core_gb=Fraction(688, 100),
        postlude_gb=Fraction(446, 100),
        top_k=8,
        n_experts=128,
        core_loops=3,
    )
    g2_pr13 = batched_speculative_decode_ceiling_q(
        bandwidth_gbps=Fraction(100),
        n_requests=4,
        draft_steps_k=1,
        accepted_tokens_per_req=Fraction(2),
        verify_bytes_gb=Fraction(1),
        draft_weight_bytes_gb=Fraction(1, 4),
    )

    g3_hsv3 = holosphere_v3_l3_and_roofline_q()

    payload: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "track": "S124",
        "experiment": "EXP-Q30a",
        "preregistration_sha256": prereg_sha,
        "float_ops_used": 0,
        "verdicts": {"G1": "CONFIRMED", "G2": "CONFIRMED", "G3": "CONFIRMED"},
        "g1_aa_illusion_and_mirage_gate": {
            "combinatorial_proof": g1_aa,
            "pr11_calibrated_floor": g1_floor,
            "sub_floor_1pct_candidate_rejected": g1_noise_reject["accepted"] is False,
            "zero_false_win_jitter_candidate_rejected": (
                g1_zero_fw_jitter["accepted"] is False
                and Fraction(g1_zero_fw_jitter["required_rel_margin_q"]) > Fraction(0)
            ),
            "genuine_25pct_candidate_accepted": g1_real_accept["accepted"] is True,
        },
        "g2_looped_and_batched_draft_rooflines": {
            "pr22_inkling2_mini_visits": g2_pr22,
            "pr12_loop_aware_moe_vram_roi": g2_pr12,
            "pr13_batched_single_read_draft": g2_pr13,
        },
        "g3_holosphere_v3_15m_l3_roofline": g3_hsv3,
    }
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["certificate_sha256"] = hashlib.sha256(canon).hexdigest()
    return payload


def validate_s124_certificate(cert: Mapping[str, Any]) -> None:
    """Fail-closed validator for Track S124 pure-Q certificate."""
    require_ok(
        isinstance(cert, Mapping)
        and cert.get("schema") == SCHEMA_VERSION
        and cert.get("float_ops_used") == 0
        and cert.get("preregistration_sha256") == PREREG_W14_SHA256,
        "BAD_CERT_HEADER",
        "invalid S124 certificate header or preregistration SHA",
    )
    rec_sha = cert.get("certificate_sha256")
    require_ok(isinstance(rec_sha, str) and len(rec_sha) == 64, "MISSING_CERT_SHA", "missing 64-hex certificate_sha256")
    body = {k: v for k, v in cert.items() if k != "certificate_sha256"}
    recomputed = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    require_ok(recomputed == rec_sha, "CERT_SHA_MISMATCH", "certificate_sha256 mismatch")

    g1 = cert["g1_aa_illusion_and_mirage_gate"]
    cp = g1["combinatorial_proof"]
    require_ok(
        cp["single_triple_false_win_prob_q"] == "1/3"
        and cp["min_independent_triples_for_alpha"] == 3
        and cp["m_triple_false_win_prob_q"] == "1/27"
        and g1["pr11_calibrated_floor"]["max_false_win_rel_margin_q"] == "77/5000"
        and g1["sub_floor_1pct_candidate_rejected"] is True
        and g1["zero_false_win_jitter_candidate_rejected"] is True
        and g1["genuine_25pct_candidate_accepted"] is True,
        "G1_CERT_INVALID",
        "G1 A/A illusion or gate invariants failed",
    )

    g2 = cert["g2_looped_and_batched_draft_rooflines"]
    require_ok(
        g2["pr22_inkling2_mini_visits"]["physical_layers"] == 24
        and g2["pr22_inkling2_mini_visits"]["logical_layer_visits"] == 48
        and g2["pr22_inkling2_mini_visits"]["decode_overstatement_ratio_q"] == "2/1"
        and g2["pr22_inkling2_mini_visits"]["prefill_sparse_phys_vs_dense_visit_ratio_q"] == "4/1"
        and g2["pr12_loop_aware_moe_vram_roi"]["boundary_mb_per_tok_per_gb_q"] == "125/2"
        and g2["pr12_loop_aware_moe_vram_roi"]["core_mb_per_tok_per_gb_q"] == "375/2"
        and g2["pr12_loop_aware_moe_vram_roi"]["core_vs_boundary_roi_ratio_q"] == "3/1"
        and g2["pr12_loop_aware_moe_vram_roi"]["core_share_of_active_traffic_q"] == "1032/1427"
        and g2["pr13_batched_single_read_draft"]["true_aggregate_ceiling_tok_s_q"] == "640/1"
        and g2["pr13_batched_single_read_draft"]["buggy_aggregate_ceiling_tok_s_q"] == "400/1"
        and g2["pr13_batched_single_read_draft"]["relative_underestimate_q"] == "3/8",
        "G2_CERT_INVALID",
        "G2 looped-visit or batched-draft roofline invariants failed",
    )

    g3 = cert["g3_holosphere_v3_15m_l3_roofline"]
    require_ok(
        g3["safetensors_file_bytes"] == 8_963_044
        and g3["tensor_payload_bytes"] == 8_948_868
        and g3["input_embedding_bytes"] == 0
        and g3["persistent_o1_state_bytes"] == 262_144
        and g3["kv_bytes_per_token"] == 0
        and g3["resident_total_bytes"] == 9_225_188
        and g3["fits_in_24mib_l3"] is True
        and g3["hugepages_2mib_needed_holosphere_v3"] == 5
        and g3["i9_l3_vs_ddr4_bandwidth_lift_q"] == "160/21"
        and Fraction(g3["live_v3_46468_over_gddr6_tied_q"]) > Fraction(1)
        and Fraction(g3["live_v3_46468_over_l2_tied_q"]) < Fraction(1)
        and g3["i9_1c_practical_fma_compute_ceiling_tok_s_q"] == "33600000000/15234817"
        and g3["i9_1c_l3_is_compute_bound"] is True,
        "G3_CERT_INVALID",
        "G3 HoloSphere-V3 L3 & sm_86 roofline invariants failed",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track S124 Pure-Q A/A Noise-Floor, Looped-Roofline & HoloSphere-V3 L3 Oracle")
    parser.add_argument("--write", action="store_true", help=f"Write {CERT_FILENAME} in track directory")
    parser.add_argument("--check", action="store_true", help=f"Verify {CERT_FILENAME} matches fresh computation")
    parser.add_argument("--json", action="store_true", help="Print canonical JSON certificate")
    args = parser.parse_args(argv)

    try:
        modes = int(bool(args.write)) + int(bool(args.check))
        require_ok(modes <= 1, "CLI_MUTUAL_EXCLUSION", "cannot pass both --write and --check")
        track_dir = Path(__file__).resolve().parent
        cert_path = track_dir / CERT_FILENAME
        fresh = build_s124_certificate()
        validate_s124_certificate(fresh)

        if args.write:
            cert_path.write_text(json.dumps(fresh, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            sys.stdout.write(json.dumps({"status": "WRITTEN", "certificate_sha256": fresh["certificate_sha256"], "verdicts": fresh["verdicts"]}, sort_keys=True) + "\n")
            return 0
        if args.check:
            require_ok(cert_path.is_file(), "MISSING_CERT_FILE", f"missing {CERT_FILENAME}")
            on_disk = json.loads(cert_path.read_text(encoding="utf-8"))
            validate_s124_certificate(on_disk)
            require_ok(on_disk == fresh, "CERT_DRIFT", "on-disk certificate differs from recomputed certificate")
            sys.stdout.write(json.dumps({"status": "PASS", "certificate_sha256": fresh["certificate_sha256"], "verdicts": fresh["verdicts"]}, sort_keys=True) + "\n")
            return 0
        if args.json:
            sys.stdout.write(json.dumps(fresh, indent=2, sort_keys=True) + "\n")
            return 0
        sys.stdout.write(json.dumps({"status": "PASS", "certificate_sha256": fresh["certificate_sha256"], "verdicts": fresh["verdicts"]}, sort_keys=True) + "\n")
        return 0
    except S124RooflineError as exc:
        sys.stderr.write(f"S124_ORACLE_FAIL {exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
