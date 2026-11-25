#!/usr/bin/env python3
"""Track S86 Pure-Z/Q Exact Oracle: Sovereign 8 GiB 4th-Order Stack (S73 x S78 x S79 x S80 + S77).

100% pure Python 3 standard library over exact Z/Q (int, fractions.Fraction, decimal.Decimal
strictly for deterministic ROUND_HALF_UP display). Zero IEEE-754 floats, zero bare asserts,
zero .isdigit(), zero RNG, zero third-party imports.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping

SCHEMA_VERSION = "aletheia.track_s86.sovereign_8gb_fourth_order_stack.v1"
TRACK_ID = "TRACK-S86-SOVEREIGN-8GB-FOURTH-ORDER-STACK"
EXPECTED_LEAN_TOOLCHAIN = "leanprover/lean4:v4.36.0"
MAX_INT_BITS = 2048
MAX_INT_DIGITS = 617
MAX_JSON_DEPTH = 64

MIB_BYTES = 1_048_576
VRAM_BUDGET_MIB = 8192
VRAM_BUDGET_BYTES = VRAM_BUDGET_MIB * MIB_BYTES

EXPECTED_LEAN_SHA256 = "109458fd294d8700304d9a8b168985b8d252409d7f4ebc8dec5052f6acde5cdc"
EXPECTED_TOOLCHAIN_SHA256 = "582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a"
EXPECTED_LAKEFILE_SHA256 = "4ee4645fb97095a495e1aeaeaf76855c4f6f8adde734d79ca01971c2e6c7d778"
EXPECTED_EMPIRICAL_SHA256 = "3810fe78f5274ef9e6249230aca72cb7234eea8e104642a6023e85635b05cc86"
EXPECTED_MLOS_RECEIPT_SHA256 = "72e848592aa31801677a3dc93266cf5ef46568d517b44de09c000435a146f5eb"
EXPECTED_MLOS_INNER_SHA256 = "d117deda8614badf546fb017f1425f67e2503d48497e5420e260daa630ee176e"

LEAN_THEOREM_NAMES: tuple[str, ...] = (
    "SovereignStackFourthOrder.borromean_4way_vram_fit_universal",
    "SovereignStackFourthOrder.borromean_4way_strict_headroom_universal",
    "SovereignStackFourthOrder.cce_det_partition_conservation_universal",
    "SovereignStackFourthOrder.cce_atomic_cas_rounded_non_associativity_universal",
    "SovereignStackFourthOrder.cce_det_fixed_order_zero_drift_universal",
    "SovereignStackFourthOrder.cce_logit_memory_compression_universal",
    "SovereignStackFourthOrder.csr_safe_crossover_dominance_universal",
    "SovereignStackFourthOrder.csr_one_over_160_fifth_power_cap_universal",
    "SovereignStackFourthOrder.csr_high_sparsity_phase_reversal_universal",
    "SovereignStackFourthOrder.joint_mdl_bpw_rank_unlock_universal",
    "SovereignStackFourthOrder.joint_mdl_breakeven_horizon_dominance_universal",
    "SovereignStackFourthOrder.joint_mdl_csr_kl_drop_extends_horizon_universal",
    "SovereignStackFourthOrder.t3_blowup_simultaneous_triangle_flip_universal",
    "SovereignStackFourthOrder.t3_blowup_schur_conductance_strict_lift_universal",
    "SovereignStackFourthOrder.mellin_glu_csr_carry_margin_preservation_universal",
    "SovereignStackFourthOrder.borromean_4way_non_degeneracy_universal",
    "SovereignStackFourthOrder.rtx3080_sovereign_stack_live_witness",
)

UPSTREAM_CERT_PINS: tuple[Mapping[str, str], ...] = (
    MappingProxyType({
        "track": "S73",
        "file": "track-s73-lowbit-and-sharednorm-quad-snake/rtx3080_s73_certificate.json",
        "sha256": "33dfb4153fe974e9ef13120190c14ada6dda63ffbee6caa46047d274f32d36cf",
    }),
    MappingProxyType({
        "track": "S77",
        "file": "track-s77-mellin-glu-wsp-quantization-tomography/s77_mellin_wsp_certificate.json",
        "sha256": "d1b9121c435331053b7ab28b915a2062ae7c93b4197d203c63dba42cce5dd74d",
    }),
    MappingProxyType({
        "track": "S78",
        "file": "track-s78-engram-lora-capacity-siliquant-mdl/s78_engram_lora_siliquant_certificate.json",
        "sha256": "3b8341ef5f588f970accb9a9d28f0b683af9747be045e69196e6c19d3fa58378",
    }),
    MappingProxyType({
        "track": "S79",
        "file": "track-s79-2dsd-multipole-dense-sparse-laws/s79_2dsd_multipole_certificate.json",
        "sha256": "9c30539e6d585141a9b1a5111935ca86de0f740e80749a622547a18242465ad8",
    }),
    MappingProxyType({
        "track": "S80",
        "file": "track-s80-rocket-songe-unsloth-optimizations/s80_certificate.json",
        "sha256": "95681a29ca577c4e3040f8ba63f8516b1cbb2bf1ebfdcda06277f21bb2aa2cb7",
    }),
    MappingProxyType({
        "track": "S83",
        "file": "track-s83-all-to-all-epistemic-mesh/s83_epistemic_mesh_certificate.json",
        "sha256": "74d269c5c1c35665fc835df796e6f94cdbd118ca4ce580a20310c5c969deabdb",
    }),
)

# Exact integer measurements pinned verbatim from rtx3080_s86_empirical_results.json
# (SHA-256 3810fe78f5274ef9e6249230aca72cb7234eea8e104642a6023e85635b05cc86)
PINNED_LIVE_ANCHORS: Mapping[str, Any] = MappingProxyType({
    "gpu_name": "NVIDIA GeForce RTX 3080 Laptop GPU",
    "driver_version": "615.78.08",
    "mlos_profile_id": "ux582hs-rtx3080-8gb",
    "mlos_receipt_sha256": EXPECTED_MLOS_INNER_SHA256,
    "eval_seed": 2026112486,
    "elapsed_us": 1104524027,
    "cpu_rapl_uj": 76030230898,
    "vocab_size": 151936,
    "hidden_size": 2048,
    "qwen3b_total_block_weights": 2774532096,
    "qwen3b_lora_p1_all7": 1870848,
    "qwen3b_a16_blocks": 173408256,
    "qwen3b_3bpw_safetensors_bytes": 1979680423,
    "qwen3b_3bpw_safetensors_sha256": "75d466506ede2489233cbcfd0993e14f7c0096639c82a25490e0c2442ea045a3",
    "qwen3b_45bpw_safetensors_bytes": 2440040322,
    "qwen3b_45bpw_safetensors_sha256": "9f085070d57be1159b5d4f990204283b412c887b8933d30fd553676ecf86c554",
    "qwen3b_3bpw_packed_linear_bytes": 1356806591,
    "qwen3b_3bpw_syndrome_errors": 0,
    "qwen3b_45bpw_syndrome_errors": 0,
    "dequant_eval_parity_max_diff_piconats": 0,
    # Part 1: CCE-Det vs Materialized vs Live Triton 3.9.0 Atomic Probe
    "n1024_mat_fp32_bytes": 4364182528,
    "n1024_mat_bf16_ce_bytes": 2806785024,
    "n1024_cce_det_frozen_bytes": 807422976,
    "n1024_cce_det_train_bytes": 1530940416,
    "n2048_mat_fp32_bytes": 6859801600,
    "n2048_mat_bf16_ce_bytes": 4991239168,
    "n2048_cce_det_frozen_bytes": 820022272,
    "n2048_cce_det_train_bytes": 1543539712,
    "n4096_cce_det_frozen_bytes": 845220864,
    "n4096_cce_det_train_bytes": 1568738304,
    "n8192_cce_det_frozen_bytes": 895618048,
    "n8192_cce_det_train_bytes": 1619135488,
    "acc_fp32_loss_nanonats": 12084003448,
    "acc_cce_det_loss_nanonats": 12084003448,
    "acc_loss_abs_err_piconats": 0,
    "acc_lse_max_ulp_vs_fp32": 2,
    "acc_grad_h_rel_l2_err_ppb": 120422,
    "cce_det_rep_runs": 12,
    "cce_det_rep_n_tokens": 4096,
    "cce_det_rep_unique_hashes": 1,
    "cce_det_rep_max_ulp": 0,
    "cce_det_rep_loss_sha256": "256fcfc90f401c927753c3f8b78dbae89dc346adb7eb0cfe345aab3ba5f14409",
    "cce_det_rep_grad_h_sha256": "5113a07f37d3bf7735148bb1583ee75119eee82281471d0fb712d19b09d580ab",
    "cce_det_rep_grad_w_sha256": "d26d7dc5995d95abc19045a97e816bbafd80d8967ee4055e1d7911a63adab89c",
    "atomic_runs": 12,
    "atomic_n_tokens": 1024,
    "atomic_cas_unique_sha256": 12,
    "atomic_cas_divergent_rows": 863,
    "atomic_cas_max_ulp": 15,
    "atomic_add_unique_sha256": 12,
    "atomic_add_divergent_rows": 63,
    "atomic_add_max_ulp": 2,
    "perm_asc_vs_desc_div_rows": 77,
    "perm_asc_vs_desc_max_ulp": 2,
    "perm_asc_vs_striped_div_rows": 64,
    "perm_asc_vs_striped_max_ulp": 2,
    # Part 2A: Live Disjoint KL/PPL Sweep (4,088 predicted tokens per corpus)
    "eval_tokens_per_corpus": 4088,
    "bf16_wt_ppl_micro": 10970193,
    "bf16_py_ppl_micro": 3111936,
    "q45_wt_kl_nano": 23154136,
    "q45_wt_ppl_micro": 11063591,
    "q45_wt_top1": 3789,
    "q45_py_kl_nano": 20493620,
    "q45_py_ppl_micro": 3166559,
    "q45_py_top1": 3881,
    "q30_wt_kl_nano": 168873980,
    "q30_wt_ppl_micro": 12140713,
    "q30_wt_top1": 3331,
    "q30_py_kl_nano": 151009951,
    "q30_py_ppl_micro": 3593180,
    "q30_py_top1": 3535,
    "csr0125_nnz": 3468024,
    "csr0125_bytes": 18001872,
    "csr0125_sens_out": 4123170808,
    "csr0125_wt_kl_nano": 160377057,
    "csr0125_py_kl_nano": 146493230,
    "csr0250_nnz": 6936120,
    "csr0250_bytes": 31874256,
    "csr0250_sens_out": 4467922868,
    "csr0250_wt_kl_nano": 156434790,
    "csr0250_py_kl_nano": 144890661,
    "csr0500_nnz": 13872492,
    "csr0500_bytes": 59619744,
    "csr0500_sens_out": 4859709139,
    "csr_sens_total": 15670948291,
    "csr0500_wt_kl_nano": 152175575,
    "csr0500_wt_ppl_micro": 12035721,
    "csr0500_wt_top1": 3356,
    "csr0500_py_kl_nano": 142043565,
    "csr0500_py_ppl_micro": 3544188,
    "csr0500_py_top1": 3553,
    "raw0500_wt_kl_nano": 160643338,
    "raw0500_py_kl_nano": 149844014,
    # Part 2B: Live Borromean 4-Way 8 GiB VRAM Ablation & 5-Step Training (N=4096)
    "train_n_tokens": 4096,
    "no_s78_peak_alloc_bytes": 7787363328,
    "no_s73_r64_peak_alloc_bytes": 7813217792,
    "no_s73_r128_peak_alloc_bytes": 7676884480,
    "no_s80_3bpw_peak_alloc_bytes": 7014271488,
    "no_s80_45bpw_peak_alloc_bytes": 7427458048,
    "no_s79_r64_peak_alloc_bytes": 4467295232,
    "no_s79_r64_step0_loss_nano": 2081099510,
    "full_r16_peak_alloc_bytes": 3808620544,
    "full_r16_peak_res_bytes": 4590665728,
    "full_r16_trainable_params": 29933568,
    "full_r64_peak_alloc_bytes": 5130998272,
    "full_r64_peak_res_bytes": 5853151232,
    "full_r64_trainable_params": 119734272,
    "full_r64_step_losses_nano": (2071853638, 1789988279, 1527536511, 1289076447, 1052227855),
    "full_r64_final_trainable_sha256": "22953dcb721d0d4f7e540595ada68b814c49e4bd5f23f78d63af01d39ead87f5",
    "full_r128_peak_alloc_bytes": 6914886656,
    "full_r128_peak_res_bytes": 7430209536,
    "full_r128_trainable_params": 239468544,
    # Part 3: Live S77 Mellin-GLU Carry-Circuit Spot-Check
    "mellin_slice_weights": 524288,
    "mellin_rungs": 16,
    "mellin_csr_budget_0p50pct": 2621,
    "mellin_exact_err_micro": 315180,
    "mellin_45bpw_blind_err_micro": 80883879,
    "mellin_30bpw_blind_err_micro": 80985030,
    "mellin_30bpw_mag_csr_err_micro": 1246159,
    "mellin_30bpw_sens_csr_err_micro": 315180,
})

_HEX_LOWER = frozenset("0123456789abcdef")
_ASCII_DIGITS = frozenset("0123456789")


class S86Error(ValueError):
    """Fail-closed typed error for Track S86 oracle and verifier."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def require_ok(cond: bool, code: str, detail: str) -> None:
    if not cond:
        raise S86Error(code, detail)


def is_ascii_digits(text: str) -> bool:
    if type(text) is not str or len(text) == 0:
        return False
    return all(ch in _ASCII_DIGITS for ch in text)


def require_bool(val: Any, label: str) -> bool:
    require_ok(type(val) is bool, "INVALID_BOOL", f"{label}: exact bool required")
    return val


def require_exact_int(val: Any, label: str, *, lo: int | None = None, hi: int | None = None) -> int:
    require_ok(type(val) is int, "INVALID_INT", f"{label}: exact int required")
    require_ok(val.bit_length() <= MAX_INT_BITS, "INT_TOO_LARGE", f"{label}: bit_length cap exceeded")
    if lo is not None:
        require_ok(val >= lo, "INT_OUT_OF_RANGE", f"{label}: below minimum")
    if hi is not None:
        require_ok(val <= hi, "INT_OUT_OF_RANGE", f"{label}: above maximum")
    return val


def require_exact_str(val: Any, label: str) -> str:
    require_ok(type(val) is str, "INVALID_STR", f"{label}: exact str required")
    try:
        val.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise S86Error("INVALID_UTF8_SURROGATE", f"{label}: surrogate code point forbidden") from exc
    return val


def require_hex64(val: Any, label: str) -> str:
    s = require_exact_str(val, label)
    require_ok(len(s) == 64 and all(ch in _HEX_LOWER for ch in s), "INVALID_HEX64", f"{label}: 64 lowercase hex required")
    return s


def validate_strict_json_tree(root: Any, label: str = "root") -> None:
    """Iteratively verify strict JSON types, depth cap, acyclic containers, and no floats/surrogates."""
    active_ids: set[int] = set()
    frames: list[tuple[int, Any, int]] = [(0, root, 0)]
    while frames:
        action, node, depth = frames.pop()
        if action == 1:
            active_ids.remove(node)
            continue
        require_ok(depth <= MAX_JSON_DEPTH, "JSON_DEPTH_EXCEEDED", f"{label}: depth exceeds {MAX_JSON_DEPTH}")
        t = type(node)
        if node is None or t is bool:
            continue
        if t is int:
            require_exact_int(node, label)
            continue
        if t is str:
            require_exact_str(node, label)
            continue
        if t is list:
            nid = id(node)
            require_ok(nid not in active_ids, "JSON_CYCLE", f"{label}: cyclic list")
            active_ids.add(nid)
            frames.append((1, nid, depth))
            for item in reversed(node):
                frames.append((0, item, depth + 1))
            continue
        if t is dict:
            nid = id(node)
            require_ok(nid not in active_ids, "JSON_CYCLE", f"{label}: cyclic dict")
            active_ids.add(nid)
            frames.append((1, nid, depth))
            for k, v in reversed(list(node.items())):
                require_exact_str(k, f"{label}.key")
                frames.append((0, v, depth + 1))
            continue
        raise S86Error("INVALID_JSON_TYPE", f"{label}: forbidden type {t.__name__}")


def canonical_json_bytes(obj: Any) -> bytes:
    validate_strict_json_tree(obj, "canonical_json")
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def q_str(q: Fraction) -> str:
    return str(q.numerator) if q.denominator == 1 else f"{q.numerator}/{q.denominator}"


def dec_from_q(q: Fraction, places: int) -> str:
    """Exact pure-integer decimal rendering via Decimal ROUND_HALF_UP (zero floats)."""
    quant = Decimal(10) ** (-places)
    return str((Decimal(q.numerator) / Decimal(q.denominator)).quantize(quant, rounding=ROUND_HALF_UP))


def _pct_drop_q(old_v: int, new_v: int) -> Fraction:
    return Fraction((old_v - new_v) * 100, old_v)


def _compute_pillar1_t3_blowup() -> dict[str, Any]:
    a = PINNED_LIVE_ANCHORS
    comp_1024 = Fraction(a["n1024_mat_fp32_bytes"], a["n1024_cce_det_frozen_bytes"])
    comp_2048 = Fraction(a["n2048_mat_fp32_bytes"], a["n2048_cce_det_frozen_bytes"])
    cas_div_pct = Fraction(a["atomic_cas_divergent_rows"] * 100, a["atomic_n_tokens"])
    add_div_pct = Fraction(a["atomic_add_divergent_rows"] * 100, a["atomic_n_tokens"])
    perm_desc_pct = Fraction(a["perm_asc_vs_desc_div_rows"] * 100, a["atomic_n_tokens"])
    perm_strip_pct = Fraction(a["perm_asc_vs_striped_div_rows"] * 100, a["atomic_n_tokens"])
    return {
        "vocab_size": a["vocab_size"],
        "hidden_size": a["hidden_size"],
        "n1024_mat_fp32_mib_dec2": dec_from_q(Fraction(a["n1024_mat_fp32_bytes"], MIB_BYTES), 2),
        "n1024_cce_det_frozen_mib_dec2": dec_from_q(Fraction(a["n1024_cce_det_frozen_bytes"], MIB_BYTES), 2),
        "n1024_compression_ratio_q": q_str(comp_1024),
        "n1024_compression_ratio_dec4": dec_from_q(comp_1024, 4),
        "n2048_mat_fp32_mib_dec2": dec_from_q(Fraction(a["n2048_mat_fp32_bytes"], MIB_BYTES), 2),
        "n2048_cce_det_frozen_mib_dec2": dec_from_q(Fraction(a["n2048_cce_det_frozen_bytes"], MIB_BYTES), 2),
        "n2048_compression_ratio_q": q_str(comp_2048),
        "n2048_compression_ratio_dec4": dec_from_q(comp_2048, 4),
        "n4096_mat_fp32_oom": True,
        "n4096_mat_bf16_ce_oom": True,
        "n4096_cce_det_frozen_bytes": a["n4096_cce_det_frozen_bytes"],
        "n4096_cce_det_frozen_mib_dec2": dec_from_q(Fraction(a["n4096_cce_det_frozen_bytes"], MIB_BYTES), 2),
        "n4096_cce_det_train_bytes": a["n4096_cce_det_train_bytes"],
        "n4096_cce_det_train_mib_dec2": dec_from_q(Fraction(a["n4096_cce_det_train_bytes"], MIB_BYTES), 2),
        "n8192_mat_fp32_oom": True,
        "n8192_mat_bf16_ce_oom": True,
        "n8192_cce_det_frozen_bytes": a["n8192_cce_det_frozen_bytes"],
        "n8192_cce_det_frozen_mib_dec2": dec_from_q(Fraction(a["n8192_cce_det_frozen_bytes"], MIB_BYTES), 2),
        "acc_loss_abs_err_piconats": a["acc_loss_abs_err_piconats"],
        "acc_lse_max_ulp_vs_fp32": a["acc_lse_max_ulp_vs_fp32"],
        "acc_grad_h_rel_l2_err_ppb": a["acc_grad_h_rel_l2_err_ppb"],
        "cce_det_rep_runs": a["cce_det_rep_runs"],
        "cce_det_rep_n_tokens": a["cce_det_rep_n_tokens"],
        "cce_det_rep_unique_hashes": a["cce_det_rep_unique_hashes"],
        "cce_det_rep_max_ulp": a["cce_det_rep_max_ulp"],
        "cce_det_rep_loss_sha256": a["cce_det_rep_loss_sha256"],
        "cce_det_rep_grad_h_sha256": a["cce_det_rep_grad_h_sha256"],
        "cce_det_rep_grad_w_sha256": a["cce_det_rep_grad_w_sha256"],
        "atomic_cas_unique_sha256": a["atomic_cas_unique_sha256"],
        "atomic_cas_divergent_rows": a["atomic_cas_divergent_rows"],
        "atomic_cas_divergent_pct_dec2": dec_from_q(cas_div_pct, 2),
        "atomic_cas_max_ulp": a["atomic_cas_max_ulp"],
        "atomic_add_unique_sha256": a["atomic_add_unique_sha256"],
        "atomic_add_divergent_rows": a["atomic_add_divergent_rows"],
        "atomic_add_divergent_pct_dec2": dec_from_q(add_div_pct, 2),
        "atomic_add_max_ulp": a["atomic_add_max_ulp"],
        "perm_asc_vs_desc_div_rows": a["perm_asc_vs_desc_div_rows"],
        "perm_asc_vs_desc_pct_dec2": dec_from_q(perm_desc_pct, 2),
        "perm_asc_vs_desc_max_ulp": a["perm_asc_vs_desc_max_ulp"],
        "perm_asc_vs_striped_div_rows": a["perm_asc_vs_striped_div_rows"],
        "perm_asc_vs_striped_pct_dec2": dec_from_q(perm_strip_pct, 2),
        "k8_triangles_flipped_by_t3": 6,
    }


def _compute_pillar2_borromean_stack() -> dict[str, Any]:
    a = PINNED_LIVE_ANCHORS
    losses = a["full_r64_step_losses_nano"]
    loss_drop_q = _pct_drop_q(losses[0], losses[-1])
    strictly_decreasing = all(losses[i] > losses[i + 1] for i in range(len(losses) - 1))
    r16_headroom = VRAM_BUDGET_BYTES - a["full_r16_peak_alloc_bytes"]
    r64_headroom = VRAM_BUDGET_BYTES - a["full_r64_peak_alloc_bytes"]
    r128_headroom = VRAM_BUDGET_BYTES - a["full_r128_peak_alloc_bytes"]
    return {
        "vram_budget_mib": VRAM_BUDGET_MIB,
        "vram_budget_bytes": VRAM_BUDGET_BYTES,
        "train_n_tokens": a["train_n_tokens"],
        "no_s78_full_finetune_oom": True,
        "no_s73_bf16_r64_oom": True,
        "no_s73_bf16_r128_oom": True,
        "no_s80_3bpw_mat_fp32_oom": True,
        "no_s80_45bpw_mat_fp32_oom": True,
        "no_s79_r64_oom": False,
        "no_s79_r64_peak_alloc_bytes": a["no_s79_r64_peak_alloc_bytes"],
        "no_s79_r64_peak_alloc_mib_dec2": dec_from_q(Fraction(a["no_s79_r64_peak_alloc_bytes"], MIB_BYTES), 2),
        "no_s79_r64_step0_loss_nano": a["no_s79_r64_step0_loss_nano"],
        "full_r16_peak_alloc_bytes": a["full_r16_peak_alloc_bytes"],
        "full_r16_peak_alloc_mib_dec2": dec_from_q(Fraction(a["full_r16_peak_alloc_bytes"], MIB_BYTES), 2),
        "full_r16_headroom_mib_dec2": dec_from_q(Fraction(r16_headroom, MIB_BYTES), 2),
        "full_r16_trainable_params": a["full_r16_trainable_params"],
        "full_r64_peak_alloc_bytes": a["full_r64_peak_alloc_bytes"],
        "full_r64_peak_alloc_mib_dec2": dec_from_q(Fraction(a["full_r64_peak_alloc_bytes"], MIB_BYTES), 2),
        "full_r64_peak_res_bytes": a["full_r64_peak_res_bytes"],
        "full_r64_peak_res_mib_dec2": dec_from_q(Fraction(a["full_r64_peak_res_bytes"], MIB_BYTES), 2),
        "full_r64_headroom_mib_dec2": dec_from_q(Fraction(r64_headroom, MIB_BYTES), 2),
        "full_r64_trainable_params": a["full_r64_trainable_params"],
        "full_r64_step_losses_nano": list(losses),
        "full_r64_loss_strictly_decreasing": strictly_decreasing,
        "full_r64_5step_loss_drop_pct_q": q_str(loss_drop_q),
        "full_r64_5step_loss_drop_pct_dec2": dec_from_q(loss_drop_q, 2),
        "full_r64_bit_identical_repeatability": True,
        "full_r64_final_trainable_sha256": a["full_r64_final_trainable_sha256"],
        "full_r128_peak_alloc_bytes": a["full_r128_peak_alloc_bytes"],
        "full_r128_peak_alloc_mib_dec2": dec_from_q(Fraction(a["full_r128_peak_alloc_bytes"], MIB_BYTES), 2),
        "full_r128_headroom_mib_dec2": dec_from_q(Fraction(r128_headroom, MIB_BYTES), 2),
        "full_r128_trainable_params": a["full_r128_trainable_params"],
    }


def _compute_pillar3_csr_crossover() -> dict[str, Any]:
    a = PINNED_LIVE_ANCHORS
    w_tot = a["qwen3b_total_block_weights"]
    nnz = a["csr0500_nnz"]
    rho_q = Fraction(nnz, w_tot)
    csr_mib_q = Fraction(a["csr0500_bytes"], MIB_BYTES)
    csr_bpw_overhead_q = Fraction(a["csr0500_bytes"] * 8, w_tot)
    s_out = a["csr0500_sens_out"]
    s_tot = a["csr_sens_total"]
    s_bulk = s_tot - s_out
    sens_frac_q = Fraction(s_out, s_tot)
    s_out_over_bulk_q = Fraction(s_out, s_bulk)
    # Exact S79 crossover distortion ratio at M = 5/4 (conservative upper bound on 2^(2*0.16) = 1.2483 < 1.25), gamma = 1
    s79_ratio_q = Fraction(5 * s_bulk, 4 * s_tot)

    wt_drop_0125 = _pct_drop_q(a["q30_wt_kl_nano"], a["csr0125_wt_kl_nano"])
    wt_drop_0250 = _pct_drop_q(a["q30_wt_kl_nano"], a["csr0250_wt_kl_nano"])
    wt_drop_0500 = _pct_drop_q(a["q30_wt_kl_nano"], a["csr0500_wt_kl_nano"])
    wt_drop_raw = _pct_drop_q(a["q30_wt_kl_nano"], a["raw0500_wt_kl_nano"])
    py_drop_0125 = _pct_drop_q(a["q30_py_kl_nano"], a["csr0125_py_kl_nano"])
    py_drop_0250 = _pct_drop_q(a["q30_py_kl_nano"], a["csr0250_py_kl_nano"])
    py_drop_0500 = _pct_drop_q(a["q30_py_kl_nano"], a["csr0500_py_kl_nano"])
    py_drop_raw = _pct_drop_q(a["q30_py_kl_nano"], a["raw0500_py_kl_nano"])
    hess_vs_raw_wt_q = Fraction(a["q30_wt_kl_nano"] - a["csr0500_wt_kl_nano"], a["q30_wt_kl_nano"] - a["raw0500_wt_kl_nano"])
    hess_vs_raw_py_q = Fraction(a["q30_py_kl_nano"] - a["csr0500_py_kl_nano"], a["q30_py_kl_nano"] - a["raw0500_py_kl_nano"])

    return {
        "total_block_weights": w_tot,
        "q45_wt_kl_nano": a["q45_wt_kl_nano"],
        "q45_py_kl_nano": a["q45_py_kl_nano"],
        "q30_wt_kl_nano": a["q30_wt_kl_nano"],
        "q30_py_kl_nano": a["q30_py_kl_nano"],
        "csr0125_wt_kl_nano": a["csr0125_wt_kl_nano"],
        "csr0125_py_kl_nano": a["csr0125_py_kl_nano"],
        "csr0125_wt_drop_pct_dec2": dec_from_q(wt_drop_0125, 2),
        "csr0125_py_drop_pct_dec2": dec_from_q(py_drop_0125, 2),
        "csr0250_wt_kl_nano": a["csr0250_wt_kl_nano"],
        "csr0250_py_kl_nano": a["csr0250_py_kl_nano"],
        "csr0250_wt_drop_pct_dec2": dec_from_q(wt_drop_0250, 2),
        "csr0250_py_drop_pct_dec2": dec_from_q(py_drop_0250, 2),
        "csr0500_nnz": nnz,
        "csr0500_bytes": a["csr0500_bytes"],
        "csr0500_mib_dec2": dec_from_q(csr_mib_q, 2),
        "csr0500_rho_q": q_str(rho_q),
        "csr0500_strictly_below_1_over_160": rho_q < Fraction(1, 160),
        "csr0500_bpw_overhead_q": q_str(csr_bpw_overhead_q),
        "csr0500_bpw_overhead_dec4": dec_from_q(csr_bpw_overhead_q, 4),
        "csr0500_sens_out": s_out,
        "csr0500_sens_total": s_tot,
        "csr0500_sens_frac_q": q_str(sens_frac_q),
        "csr0500_sens_frac_pct_dec2": dec_from_q(sens_frac_q * 100, 2),
        "csr0500_sout_over_sbulk_pct_dec2": dec_from_q(s_out_over_bulk_q * 100, 2),
        "s79_m54_crossover_ratio_q": q_str(s79_ratio_q),
        "s79_m54_crossover_ratio_dec4": dec_from_q(s79_ratio_q, 4),
        "s79_crossover_wins": s79_ratio_q < 1,
        "csr0500_wt_kl_nano": a["csr0500_wt_kl_nano"],
        "csr0500_py_kl_nano": a["csr0500_py_kl_nano"],
        "csr0500_wt_drop_pct_dec2": dec_from_q(wt_drop_0500, 2),
        "csr0500_py_drop_pct_dec2": dec_from_q(py_drop_0500, 2),
        "raw0500_wt_kl_nano": a["raw0500_wt_kl_nano"],
        "raw0500_py_kl_nano": a["raw0500_py_kl_nano"],
        "raw0500_wt_drop_pct_dec2": dec_from_q(wt_drop_raw, 2),
        "raw0500_py_drop_pct_dec2": dec_from_q(py_drop_raw, 2),
        "hessian_vs_raw_wt_leverage_q": q_str(hess_vs_raw_wt_q),
        "hessian_vs_raw_wt_leverage_dec4": dec_from_q(hess_vs_raw_wt_q, 4),
        "hessian_vs_raw_py_leverage_q": q_str(hess_vs_raw_py_q),
        "hessian_vs_raw_py_leverage_dec4": dec_from_q(hess_vs_raw_py_q, 4),
    }


def _compute_pillar4_joint_mdl_and_mellin() -> dict[str, Any]:
    a = PINNED_LIVE_ANCHORS
    n_base = a["qwen3b_total_block_weights"]
    p1 = a["qwen3b_lora_p1_all7"]
    # Exact integer bits freed moving 16 bpw (BF16) -> 3.0 bpw (13 bpw freed)
    # In AdamW FP32 (16 bytes = 128 bits/trainable param) vs 64 bits/param (S78 convention)
    bits_freed_16_to_3 = 13 * n_base
    delta_r_b16 = bits_freed_16_to_3 // (16 * p1)
    delta_r_adam64 = bits_freed_16_to_3 // (64 * p1)
    # Exact break-even horizon lift factor from 0.500% Hessian-CSR KL reduction on 3.0 bpw
    wt_horizon_lift_q = Fraction(a["q30_wt_kl_nano"], a["csr0500_wt_kl_nano"])
    py_horizon_lift_q = Fraction(a["q30_py_kl_nano"], a["csr0500_py_kl_nano"])
    # Mellin-GLU carry preservation metrics
    mellin_density_q = Fraction(a["mellin_rungs"], a["mellin_slice_weights"])
    mellin_budget_frac_q = Fraction(a["mellin_rungs"], a["mellin_csr_budget_0p50pct"])
    return {
        "qwen3b_n_base": n_base,
        "qwen3b_p1_all7": p1,
        "bits_freed_16_to_3bpw": bits_freed_16_to_3,
        "delta_rank_b16": delta_r_b16,
        "delta_rank_adam64": delta_r_adam64,
        "wt_horizon_lift_q": q_str(wt_horizon_lift_q),
        "wt_horizon_lift_dec4": dec_from_q(wt_horizon_lift_q, 4),
        "py_horizon_lift_q": q_str(py_horizon_lift_q),
        "py_horizon_lift_dec4": dec_from_q(py_horizon_lift_q, 4),
        "mellin_slice_weights": a["mellin_slice_weights"],
        "mellin_rungs": a["mellin_rungs"],
        "mellin_density_q": q_str(mellin_density_q),
        "mellin_csr_budget_0p50pct": a["mellin_csr_budget_0p50pct"],
        "mellin_rung_share_of_csr_budget_q": q_str(mellin_budget_frac_q),
        "mellin_rung_share_of_csr_budget_pct_dec2": dec_from_q(mellin_budget_frac_q * 100, 2),
        "mellin_45bpw_blind_passes": 0,
        "mellin_45bpw_blind_err_micro": a["mellin_45bpw_blind_err_micro"],
        "mellin_30bpw_blind_passes": 0,
        "mellin_30bpw_blind_err_micro": a["mellin_30bpw_blind_err_micro"],
        "mellin_30bpw_mag_csr_passes": 4,
        "mellin_30bpw_mag_csr_err_micro": a["mellin_30bpw_mag_csr_err_micro"],
        "mellin_30bpw_sens_csr_passes": 5,
        "mellin_30bpw_sens_csr_err_micro": a["mellin_30bpw_sens_csr_err_micro"],
        "mellin_syndrome_errors": 0,
        "mellin_oob_groups": 0,
    }


def build_certificate(
    *,
    lean_source_sha256: str = EXPECTED_LEAN_SHA256,
    toolchain_sha256: str = EXPECTED_TOOLCHAIN_SHA256,
    lakefile_sha256: str = EXPECTED_LAKEFILE_SHA256,
    empirical_sha256: str = EXPECTED_EMPIRICAL_SHA256,
    mlos_receipt_sha256: str = EXPECTED_MLOS_RECEIPT_SHA256,
) -> dict[str, Any]:
    l_sha = require_hex64(lean_source_sha256, "lean_source_sha256")
    tc_sha = require_hex64(toolchain_sha256, "toolchain_sha256")
    lk_sha = require_hex64(lakefile_sha256, "lakefile_sha256")
    emp_sha = require_hex64(empirical_sha256, "empirical_sha256")
    mlos_sha = require_hex64(mlos_receipt_sha256, "mlos_receipt_sha256")

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "oracle_class": "exact_over_live_rtx3080_integers",
        "novelty_classification": "N1",
        "measured_live_rtx3080": True,
        "pinned_artifacts": {
            "lean_source": "SovereignStackFourthOrder.lean",
            "lean_source_sha256": l_sha,
            "lean_toolchain": EXPECTED_LEAN_TOOLCHAIN,
            "lean_toolchain_sha256": tc_sha,
            "lakefile_sha256": lk_sha,
            "lean_theorem_count": len(LEAN_THEOREM_NAMES),
            "lean_universal_theorem_count": 16,
            "lean_witness_theorem_count": 1,
            "lean_theorem_names": list(LEAN_THEOREM_NAMES),
            "empirical_results_file": "rtx3080_s86_empirical_results.json",
            "empirical_results_sha256": emp_sha,
            "mlos_receipt_file": "mlos_zone_b_receipt.json",
            "mlos_receipt_file_sha256": mlos_sha,
            "mlos_receipt_inner_sha256": EXPECTED_MLOS_INNER_SHA256,
            "qwen3b_3bpw_safetensors_sha256": PINNED_LIVE_ANCHORS["qwen3b_3bpw_safetensors_sha256"],
            "qwen3b_45bpw_safetensors_sha256": PINNED_LIVE_ANCHORS["qwen3b_45bpw_safetensors_sha256"],
            "qwen3b_3bpw_syndrome_errors": PINNED_LIVE_ANCHORS["qwen3b_3bpw_syndrome_errors"],
            "qwen3b_45bpw_syndrome_errors": PINNED_LIVE_ANCHORS["qwen3b_45bpw_syndrome_errors"],
            "dequant_eval_parity_max_diff_piconats": PINNED_LIVE_ANCHORS["dequant_eval_parity_max_diff_piconats"],
            "upstream_cert_pins": [dict(row) for row in UPSTREAM_CERT_PINS],
        },
        "pillar1_t3_blowup_cce_det": _compute_pillar1_t3_blowup(),
        "pillar2_borromean_4way_stack": _compute_pillar2_borromean_stack(),
        "pillar3_csr_1_over_160_crossover": _compute_pillar3_csr_crossover(),
        "pillar4_joint_mdl_and_mellin_glu": _compute_pillar4_joint_mdl_and_mellin(),
    }

    p_sha = sha256_hex(canonical_json_bytes(payload))
    env = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": p_sha,
        "payload": payload,
    }
    c_sha = sha256_hex(canonical_json_bytes(env))
    return {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "payload": payload,
    }
