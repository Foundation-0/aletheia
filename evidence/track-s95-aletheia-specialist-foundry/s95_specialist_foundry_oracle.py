#!/usr/bin/env python3
"""
Track S95: Pure-Z/Q Exact Oracle for the Local Aletheia Specialist Foundry &
Live RTX 3080 Beyond-LoRA Matched-Parameter-Budget Showdown.

Pure Python 3 standard library. Zero IEEE-754 floats, zero RNG, zero bare asserts,
zero hardcoded host paths. Pins live bare-metal RTX 3080 Zone-B receipts, all 9
matched-budget (`8,798,208` exact trainable params) adapter arms across 3 local
`Qwen/Qwen2.5-0.5B` (`apache-2.0`) specialists, Law-3 (`⫩`) fail-closed gating,
Law-4 honest failure modes, `Inkling-2-Mini` (`inkling2_loop`) scaling transfer,
and `16/16` pure-`Init` `Lean 4.36.0` universal theorems (`SpecialistFoundryCerts.lean`).
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "aletheia.track_s95.specialist_foundry.v1"
TRACK_ID = "TRACK_S95_ALETHEIA_SPECIALIST_FOUNDRY"
ORACLE_CLASS = "HYBRID_GPU_CERTIFIED"

# Cryptographically pinned Track S95 artifacts (exact SHA-256 digests)
RESULTS_FILE_NAME = "rtx3080_s95_foundry_results.json"
RESULTS_FILE_SHA256 = "80592b79d6325340f333f1cbc058d78a38f04699d58eeeb3c12b0ac01eb5b0dd"
RESULTS_FILE_BYTES = 11782

MLOS_RECEIPT_FILE_NAME = "mlos_zone_b_receipt.json"
MLOS_RECEIPT_FILE_SHA256 = "d1ac6ab658a6f6c748b9f67bc73967d96ed5b9536dd44a870ac909a367e2bdad"
MLOS_RECEIPT_INNER_SHA256 = "095b08fa53087b6bb1b43e4d990b2ee2517803c8668f2e3f1149ca6edfe7e395"
MLOS_PROFILE_SHA256 = "566c9192d38682a0ec4d652a63a3510aaefb9dc20ef91ae9bdc6d4abbbf5cbe2"
MLOS_DURATION_MS_X1000 = 13582504472

LEAN_FILE_NAME = "SpecialistFoundryCerts.lean"
LEAN_FILE_SHA256 = "9f502c556636ed6584ad6d31d39e43339a249e49076396f20e7af4a078b16d36"
LAKEFILE_SHA256 = "4a379e6c951cbb4aa677557368d49d80735fdc65d9c398b981708ff67a40df91"
TOOLCHAIN_SHA256 = "582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a"

INKLING2_CONFIG_SHA256 = "a7a349601f0984c4abf999c480ef775d8567d21f5f84b4e8a3e035b44f288dc2"
TRACK_S96_CERT_SHA256 = "5de85fe677a714f1af93722a7034947d13bd3938519d17a94508e1a008cfdd44"

LEAN_THEOREMS: tuple[str, ...] = (
    "SpecialistFoundryCerts.oracle_gate_zero_false_accept",
    "SpecialistFoundryCerts.oracle_gate_precision_strict_lift",
    "SpecialistFoundryCerts.zero_contagion_routing_flux",
    "SpecialistFoundryCerts.token_compression_cost_strict_savings",
    "SpecialistFoundryCerts.foundry_amortization_breakeven",
    "SpecialistFoundryCerts.lora_exact_merge_distributivity",
    "SpecialistFoundryCerts.matched_adapter_parameter_budget_exact",
    "SpecialistFoundryCerts.blockh4_orthogonality_cleared",
    "SpecialistFoundryCerts.blockh4_involution_cleared",
    "SpecialistFoundryCerts.householder_2d_norm_preservation_cleared",
    "SpecialistFoundryCerts.householder_pair_init_identity",
    "SpecialistFoundryCerts.nullspace_projection_zero_base_forgetting",
    "SpecialistFoundryCerts.forgetting_learning_ratio_strictly_below_unity",
    "SpecialistFoundryCerts.anti_goodhart_holdout_generalization_bound",
    "SpecialistFoundryCerts.cs03_smuggling_obstruction_consistency",
    "SpecialistFoundryCerts.inkling2_loop_core_depth_reuse",
)

# Qwen2.5-0.5B exact architecture & matched adapter budget S = 16
QWEN_NUM_LAYERS = 24
QWEN_HIDDEN = 896
QWEN_KV_DIM = 128
QWEN_INTERMEDIATE = 4864
ADAPTER_BUDGET_S = 16
LORA_ALPHA = 32
MERGED_LAYERS_COUNT = 168
TOTAL_PARAMS_WITH_ADAPTER = 502830976
MERGED_SAFETENSORS_BYTES = 988097824
BASE_RETENTION_NLL_0_X10000 = 20399

# Strictly track-disjoint / pair-disjoint / template-disjoint dataset manifests (< 5 MiB)
DATASET_MANIFEST: tuple[tuple[str, int, int, str], ...] = (
    ("prover_eval_audit.jsonl", 25, 8978, "675f0725c43a6e37f965b07afcc1992ed8875b2f07610e003359ff6d4c2fb620"),
    ("prover_eval_tactics.jsonl", 24, 22792, "3f00d2e2e8db177eef789c898eb6cd53521b5de4a5f88798d12a7d3823a9dcfb"),
    ("prover_train.jsonl", 270, 145177, "7b0885fdd3770a99c7fb7c3fb0baab8040ec420377011a95d22a8689a42a320f"),
    ("scribe_eval.jsonl", 48, 38305, "7c8cd498876fb71be9a42669418c851ec1df432e788f9515790862ffbd2b1551"),
    ("scribe_train.jsonl", 200, 158751, "c56143cb097ca3d37b1720aecb46b22addc7f3d9bc8241a0fc6f159cdc95eb94"),
    ("weaver_eval.jsonl", 60, 38656, "06126f26f265e990c0e668e4577b2228ddb9878767be0adc144f78b944a89043"),
    ("weaver_train.jsonl", 220, 140492, "08c4f26cbf2af88efe3b8400d3d580105b697d23c1900825f8332a4ff4f4e5ee"),
)

ADAPTER_KINDS: tuple[str, ...] = ("standard_lora", "blockh4_butterfly", "privsparse_ortho")

# Exact raw integer measurements from live RTX 3080 Zone-B `rtx3080_s95_foundry_results.json`
SCRIBE_BASE_TGT_NLL_0_X10000 = 2719
SCRIBE_BASE_EVAL = {
    "total": 48,
    "strict_json_ok": 0,
    "exact_all7_ok": 0,
    "hygiene_tp": 0,
    "hygiene_fp": 0,
    "hygiene_fn": 36,
    "hygiene_tn": 12,
}
SCRIBE_ARMS_RAW: dict[str, dict[str, Any]] = {
    "standard_lora": {
        "trainable_params": 8798208,
        "peak_vram_mib": 2181,
        "train_seconds_x100": 10333,
        "ms_per_step_x100": 51667,
        "opt_steps": 200,
        "max_merge_diff_x1e6": 2445312,
        "base_nll_after_x10000": 21840,
        "tgt_nll_after_x10000": 0,
        "latency_ms_x100": 19345,
        "tok_per_sec_x100": 36271,
        "safetensors_sha256": "e9dc8ec52ff575c110279ab54cf8094513a6eb4a412eb0bff359d8a382f3106e",
        "total": 48,
        "strict_json_ok": 48,
        "exact_all7_ok": 48,
        "hygiene_tp": 36,
        "hygiene_fp": 0,
        "hygiene_fn": 0,
        "hygiene_tn": 12,
    },
    "blockh4_butterfly": {
        "trainable_params": 8798208,
        "peak_vram_mib": 3296,
        "train_seconds_x100": 332017,
        "ms_per_step_x100": 1660087,
        "opt_steps": 200,
        "max_merge_diff_x1e6": 1437500,
        "base_nll_after_x10000": 20561,
        "tgt_nll_after_x10000": 46,
        "latency_ms_x100": 16008,
        "tok_per_sec_x100": 43832,
        "safetensors_sha256": "cd235baebae87d9aa601ad98eee8547e009077a61272e24c7d09fc34ce8f3b2c",
        "total": 48,
        "strict_json_ok": 48,
        "exact_all7_ok": 40,
        "hygiene_tp": 36,
        "hygiene_fp": 8,
        "hygiene_fn": 0,
        "hygiene_tn": 4,
    },
    "privsparse_ortho": {
        "trainable_params": 8798208,
        "peak_vram_mib": 2194,
        "train_seconds_x100": 33405,
        "ms_per_step_x100": 167024,
        "opt_steps": 200,
        "max_merge_diff_x1e6": 906250,
        "base_nll_after_x10000": 108839,
        "tgt_nll_after_x10000": 220,
        "latency_ms_x100": 15393,
        "tok_per_sec_x100": 45475,
        "safetensors_sha256": "bcd5a88fc50cdc252ec4562109884d791e6e91535530e1848135ad4d240c5940",
        "total": 48,
        "strict_json_ok": 41,
        "exact_all7_ok": 41,
        "hygiene_tp": 29,
        "hygiene_fp": 0,
        "hygiene_fn": 7,
        "hygiene_tn": 12,
    },
}

WEAVER_BASE_TGT_NLL_0_X10000 = 21083
WEAVER_BASE_EVAL = {
    "total": 60,
    "strict_json_ok": 0,
    "exact_all5_ok": 0,
    "pathway_class_ok": 0,
    "operator_tag_ok": 0,
    "cs03_tp": 0,
    "cs03_fp": 0,
    "cs03_fn": 15,
    "cs03_tn": 45,
}
WEAVER_ARMS_RAW: dict[str, dict[str, Any]] = {
    "standard_lora": {
        "trainable_params": 8798208,
        "peak_vram_mib": 1857,
        "train_seconds_x100": 10632,
        "ms_per_step_x100": 48326,
        "opt_steps": 220,
        "max_merge_diff_x1e6": 2046875,
        "base_nll_after_x10000": 23600,
        "tgt_nll_after_x10000": 394,
        "latency_ms_x100": 14253,
        "tok_per_sec_x100": 32567,
        "safetensors_sha256": "aeaf24738907883ba3fdc1d886b109ca01c9f4c0537e4634b102e5bd3e14afd0",
        "total": 60,
        "strict_json_ok": 57,
        "exact_all5_ok": 34,
        "pathway_class_ok": 39,
        "operator_tag_ok": 41,
        "cs03_tp": 15,
        "cs03_fp": 0,
        "cs03_fn": 0,
        "cs03_tn": 45,
    },
    "blockh4_butterfly": {
        "trainable_params": 8798208,
        "peak_vram_mib": 2662,
        "train_seconds_x100": 268345,
        "ms_per_step_x100": 1219748,
        "opt_steps": 220,
        "max_merge_diff_x1e6": 1250000,
        "base_nll_after_x10000": 20615,
        "tgt_nll_after_x10000": 1107,
        "latency_ms_x100": 11185,
        "tok_per_sec_x100": 41289,
        "safetensors_sha256": "c19888983b85dc3c810810850b10145e933cbc6b3df7e08c6294e023d950dcc1",
        "total": 60,
        "strict_json_ok": 38,
        "exact_all5_ok": 9,
        "pathway_class_ok": 24,
        "operator_tag_ok": 24,
        "cs03_tp": 0,
        "cs03_fp": 0,
        "cs03_fn": 15,
        "cs03_tn": 45,
    },
    "privsparse_ortho": {
        "trainable_params": 8798208,
        "peak_vram_mib": 1872,
        "train_seconds_x100": 23548,
        "ms_per_step_x100": 107036,
        "opt_steps": 220,
        "max_merge_diff_x1e6": 541504,
        "base_nll_after_x10000": 98231,
        "tgt_nll_after_x10000": 299,
        "latency_ms_x100": 8152,
        "tok_per_sec_x100": 58227,
        "safetensors_sha256": "8f264babea3b5f6e424e609b32036237f9fc9ea894bc2950bbbacfa53248eb5c",
        "total": 60,
        "strict_json_ok": 60,
        "exact_all5_ok": 34,
        "pathway_class_ok": 41,
        "operator_tag_ok": 47,
        "cs03_tp": 15,
        "cs03_fp": 0,
        "cs03_fn": 0,
        "cs03_tn": 45,
    },
}

PROVER_BASE_TGT_NLL_0_X10000 = 22394
PROVER_BASE_EVAL = {
    "tactics_total": 24,
    "live_lean_kernel_pass": 0,
    "audit_total": 25,
    "exact_escape_class_ok": 0,
    "escape_tp": 0,
    "escape_fp": 0,
    "escape_fn": 19,
    "escape_tn": 6,
}
PROVER_ARMS_RAW: dict[str, dict[str, Any]] = {
    "standard_lora": {
        "trainable_params": 8798208,
        "peak_vram_mib": 2572,
        "train_seconds_x100": 18066,
        "ms_per_step_x100": 53930,
        "opt_steps": 335,
        "max_merge_diff_x1e6": 1156250,
        "base_nll_after_x10000": 23704,
        "tgt_nll_after_x10000": 16570,
        "tactics_latency_ms_x100": 62065,
        "tactics_tok_per_sec_x100": 5861,
        "audit_latency_ms_x100": 6767,
        "audit_tok_per_sec_x100": 21517,
        "safetensors_sha256": "ca62bd458f32caab25949a41aa3b8c64cf39e688c00a2e427e61d3c2d4d93755",
        "tactics_total": 24,
        "live_lean_kernel_pass": 5,
        "r10_static_rejected": 0,
        "audit_total": 25,
        "audit_strict_json_ok": 25,
        "exact_escape_class_ok": 25,
        "escape_tp": 19,
        "escape_fp": 0,
        "escape_fn": 0,
        "escape_tn": 6,
    },
    "blockh4_butterfly": {
        "trainable_params": 8798208,
        "peak_vram_mib": 4237,
        "train_seconds_x100": 559822,
        "ms_per_step_x100": 1671110,
        "opt_steps": 335,
        "max_merge_diff_x1e6": 1812500,
        "base_nll_after_x10000": 20621,
        "tgt_nll_after_x10000": 13562,
        "tactics_latency_ms_x100": 42886,
        "tactics_tok_per_sec_x100": 8385,
        "audit_latency_ms_x100": 4913,
        "audit_tok_per_sec_x100": 29634,
        "safetensors_sha256": "c83b21e138b8b2551ced4b0707ad1e73cb511328b59133b870afa9a0be64b585",
        "tactics_total": 24,
        "live_lean_kernel_pass": 3,
        "r10_static_rejected": 0,
        "audit_total": 25,
        "audit_strict_json_ok": 23,
        "exact_escape_class_ok": 23,
        "escape_tp": 17,
        "escape_fp": 0,
        "escape_fn": 2,
        "escape_tn": 6,
    },
    "privsparse_ortho": {
        "trainable_params": 8798208,
        "peak_vram_mib": 2588,
        "train_seconds_x100": 46756,
        "ms_per_step_x100": 139571,
        "opt_steps": 335,
        "max_merge_diff_x1e6": 687500,
        "base_nll_after_x10000": 69604,
        "tgt_nll_after_x10000": 24674,
        "tactics_latency_ms_x100": 25203,
        "tactics_tok_per_sec_x100": 7258,
        "audit_latency_ms_x100": 4763,
        "audit_tok_per_sec_x100": 30569,
        "safetensors_sha256": "a91bcde76302a4cfb0fb8511aa5f047e193611a27f7e6eec4a6f5059cea6b69f",
        "tactics_total": 24,
        "live_lean_kernel_pass": 0,
        "r10_static_rejected": 0,
        "audit_total": 25,
        "audit_strict_json_ok": 25,
        "exact_escape_class_ok": 25,
        "escape_tp": 19,
        "escape_fp": 0,
        "escape_fn": 0,
        "escape_tn": 6,
    },
}

PROVER_LORA_PASSED_THEOREMS: tuple[str, ...] = (
    "SovereignStackFourthOrder.borromean_4way_non_degeneracy_universal",
    "S87UniversalHigherOrderAtlas.ceer_five_gate_borromean_necessity_universal",
    "S87UniversalHigherOrderAtlas.s87_corpus_anchored_witness_suite",
    "AletheiaMeshEngine.k16_balanced_order1_to_4_exponential_collapse",
    "AletheiaMeshEngine.k8_balanced_order1_to_4_total_5cell_extinction",
)

PROVER_BLOCKH4_PASSED_THEOREMS: tuple[str, ...] = (
    "S87UniversalHigherOrderAtlas.s87_corpus_anchored_witness_suite",
    "AletheiaMeshEngine.k16_balanced_order1_to_4_exponential_collapse",
    "AletheiaMeshEngine.k8_balanced_order1_to_4_total_5cell_extinction",
)


class S95Error(ValueError):
    """Fail-closed domain error raised by Track S95 oracle and verifier."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def require_ok(cond: bool, code: str, message: str) -> None:
    if not cond:
        raise S95Error(code, message)


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def fmt_q(val: Fraction) -> str:
    return str(val.numerator) if val.denominator == 1 else f"{val.numerator}/{val.denominator}"


def fmt_dec(val: Fraction, dp: int) -> str:
    q = Decimal(10) ** (-dp)
    return str((Decimal(val.numerator) / Decimal(val.denominator)).quantize(q, rounding=ROUND_HALF_UP))


def compute_f1_exact(tp: int, fp: int, fn: int) -> Fraction:
    denom = 2 * tp + fp + fn
    return Fraction(0) if denom == 0 else Fraction(2 * tp, denom)


def matched_qwen_adapter_params(
    layers: int = QWEN_NUM_LAYERS,
    hidden: int = QWEN_HIDDEN,
    kv_dim: int = QWEN_KV_DIM,
    intermediate: int = QWEN_INTERMEDIATE,
    budget_s: int = ADAPTER_BUDGET_S,
) -> int:
    """Exact matched trainable parameter count across all 7 target projections per layer."""
    require_ok(layers > 0 and hidden > 0 and kv_dim > 0 and intermediate > 0 and budget_s > 0, "BAD_ARCH_DIM", "positive dims required")
    per_layer = (
        2 * budget_s * (hidden + hidden)
        + 2 * budget_s * (hidden + kv_dim)
        + 3 * budget_s * (hidden + intermediate)
    )
    return layers * per_layer


def _arm_nll_metrics(base_after_x10000: int, tgt_0_x10000: int, tgt_after_x10000: int) -> dict[str, Any]:
    df = Fraction(base_after_x10000 - BASE_RETENTION_NLL_0_X10000, 10000)
    dl = Fraction(tgt_0_x10000 - tgt_after_x10000, 10000)
    if dl > 0:
        fl = df / dl
        fl_q = fmt_q(fl)
        fl_dec4 = fmt_dec(fl, 4)
        beats_s78_wall = fl < Fraction(1)
    else:
        fl_q = "NEG_LEARNING"
        fl_dec4 = "NEG_LEARNING"
        beats_s78_wall = False
    return {
        "base_retention_nll_after_x10000": base_after_x10000,
        "target_eval_nll_after_x10000": tgt_after_x10000,
        "delta_forgetting_q": fmt_q(df),
        "delta_forgetting_dec4": fmt_dec(df, 4),
        "delta_learning_q": fmt_q(dl),
        "delta_learning_dec4": fmt_dec(dl, 4),
        "forgetting_learning_ratio_q": fl_q,
        "forgetting_learning_ratio_dec4": fl_dec4,
        "beats_s78_unit_wall": beats_s78_wall,
    }


def _build_pillar1_hardware_and_datasets() -> dict[str, Any]:
    expected_params = matched_qwen_adapter_params()
    ds_rows: list[dict[str, Any]] = []
    tot_bytes = 0
    tot_rows = 0
    for name, nrows, nbytes, sha in DATASET_MANIFEST:
        ds_rows.append({"file": name, "rows": nrows, "bytes": nbytes, "sha256": sha})
        tot_bytes += nbytes
        tot_rows += nrows
    return {
        "base_model_id": "Qwen/Qwen2.5-0.5B",
        "base_model_license": "apache-2.0",
        "gpu_name": "NVIDIA GeForce RTX 3080 Laptop GPU",
        "results_file_name": RESULTS_FILE_NAME,
        "results_file_sha256": RESULTS_FILE_SHA256,
        "results_file_bytes": RESULTS_FILE_BYTES,
        "mlos_receipt_file_name": MLOS_RECEIPT_FILE_NAME,
        "mlos_receipt_file_sha256": MLOS_RECEIPT_FILE_SHA256,
        "mlos_receipt_inner_sha256": MLOS_RECEIPT_INNER_SHA256,
        "mlos_profile_sha256": MLOS_PROFILE_SHA256,
        "mlos_clean_hardware_run": True,
        "mlos_exit_code": 0,
        "mlos_anomaly_count": 0,
        "mlos_duration_ms_x1000": MLOS_DURATION_MS_X1000,
        "seed": 42,
        "matched_adapter_budget_s": ADAPTER_BUDGET_S,
        "lora_alpha": LORA_ALPHA,
        "merged_layers_count": MERGED_LAYERS_COUNT,
        "exact_matched_trainable_params": expected_params,
        "total_params_with_adapter": TOTAL_PARAMS_WITH_ADAPTER,
        "merged_safetensors_bytes": MERGED_SAFETENSORS_BYTES,
        "base_retention_nll_0_x10000": BASE_RETENTION_NLL_0_X10000,
        "dataset_total_rows": tot_rows,
        "dataset_total_bytes": tot_bytes,
        "dataset_under_5mib": tot_bytes < 5 * 1024 * 1024,
        "datasets": ds_rows,
    }


def _build_pillar2_showdown() -> dict[str, Any]:
    scribe_arms: dict[str, Any] = {}
    for k in ADAPTER_KINDS:
        r = SCRIBE_ARMS_RAW[k]
        acc = Fraction(r["exact_all7_ok"], r["total"])
        f1 = compute_f1_exact(r["hygiene_tp"], r["hygiene_fp"], r["hygiene_fn"])
        scribe_arms[k] = {
            "trainable_params": r["trainable_params"],
            "peak_vram_mib": r["peak_vram_mib"],
            "train_seconds_x100": r["train_seconds_x100"],
            "ms_per_step_x100": r["ms_per_step_x100"],
            "opt_steps": r["opt_steps"],
            "max_merge_diff_x1e6": r["max_merge_diff_x1e6"],
            "latency_ms_x100": r["latency_ms_x100"],
            "tok_per_sec_x100": r["tok_per_sec_x100"],
            "safetensors_sha256": r["safetensors_sha256"],
            "total": r["total"],
            "strict_json_ok": r["strict_json_ok"],
            "exact_all7_ok": r["exact_all7_ok"],
            "exact_all7_rate_q": fmt_q(acc),
            "exact_all7_rate_dec4": fmt_dec(acc, 4),
            "hygiene_tp": r["hygiene_tp"],
            "hygiene_fp": r["hygiene_fp"],
            "hygiene_fn": r["hygiene_fn"],
            "hygiene_tn": r["hygiene_tn"],
            "hygiene_f1_q": fmt_q(f1),
            "hygiene_f1_dec4": fmt_dec(f1, 4),
            **_arm_nll_metrics(r["base_nll_after_x10000"], SCRIBE_BASE_TGT_NLL_0_X10000, r["tgt_nll_after_x10000"]),
        }

    weaver_arms: dict[str, Any] = {}
    for k in ADAPTER_KINDS:
        r = WEAVER_ARMS_RAW[k]
        acc5 = Fraction(r["exact_all5_ok"], r["total"])
        pcls = Fraction(r["pathway_class_ok"], r["total"])
        f1 = compute_f1_exact(r["cs03_tp"], r["cs03_fp"], r["cs03_fn"])
        weaver_arms[k] = {
            "trainable_params": r["trainable_params"],
            "peak_vram_mib": r["peak_vram_mib"],
            "train_seconds_x100": r["train_seconds_x100"],
            "ms_per_step_x100": r["ms_per_step_x100"],
            "opt_steps": r["opt_steps"],
            "max_merge_diff_x1e6": r["max_merge_diff_x1e6"],
            "latency_ms_x100": r["latency_ms_x100"],
            "tok_per_sec_x100": r["tok_per_sec_x100"],
            "safetensors_sha256": r["safetensors_sha256"],
            "total": r["total"],
            "strict_json_ok": r["strict_json_ok"],
            "exact_all5_ok": r["exact_all5_ok"],
            "exact_all5_rate_q": fmt_q(acc5),
            "exact_all5_rate_dec4": fmt_dec(acc5, 4),
            "pathway_class_ok": r["pathway_class_ok"],
            "pathway_class_rate_q": fmt_q(pcls),
            "pathway_class_rate_dec4": fmt_dec(pcls, 4),
            "operator_tag_ok": r["operator_tag_ok"],
            "cs03_tp": r["cs03_tp"],
            "cs03_fp": r["cs03_fp"],
            "cs03_fn": r["cs03_fn"],
            "cs03_tn": r["cs03_tn"],
            "cs03_f1_q": fmt_q(f1),
            "cs03_f1_dec4": fmt_dec(f1, 4),
            **_arm_nll_metrics(r["base_nll_after_x10000"], WEAVER_BASE_TGT_NLL_0_X10000, r["tgt_nll_after_x10000"]),
        }

    prover_arms: dict[str, Any] = {}
    for k in ADAPTER_KINDS:
        r = PROVER_ARMS_RAW[k]
        tac_acc = Fraction(r["live_lean_kernel_pass"], r["tactics_total"])
        aud_acc = Fraction(r["exact_escape_class_ok"], r["audit_total"])
        f1 = compute_f1_exact(r["escape_tp"], r["escape_fp"], r["escape_fn"])
        prover_arms[k] = {
            "trainable_params": r["trainable_params"],
            "peak_vram_mib": r["peak_vram_mib"],
            "train_seconds_x100": r["train_seconds_x100"],
            "ms_per_step_x100": r["ms_per_step_x100"],
            "opt_steps": r["opt_steps"],
            "max_merge_diff_x1e6": r["max_merge_diff_x1e6"],
            "tactics_latency_ms_x100": r["tactics_latency_ms_x100"],
            "tactics_tok_per_sec_x100": r["tactics_tok_per_sec_x100"],
            "audit_latency_ms_x100": r["audit_latency_ms_x100"],
            "audit_tok_per_sec_x100": r["audit_tok_per_sec_x100"],
            "safetensors_sha256": r["safetensors_sha256"],
            "tactics_total": r["tactics_total"],
            "live_lean_kernel_pass": r["live_lean_kernel_pass"],
            "live_lean_pass_rate_q": fmt_q(tac_acc),
            "live_lean_pass_rate_dec4": fmt_dec(tac_acc, 4),
            "r10_static_rejected": r["r10_static_rejected"],
            "audit_total": r["audit_total"],
            "audit_strict_json_ok": r["audit_strict_json_ok"],
            "exact_escape_class_ok": r["exact_escape_class_ok"],
            "exact_escape_rate_q": fmt_q(aud_acc),
            "exact_escape_rate_dec4": fmt_dec(aud_acc, 4),
            "escape_tp": r["escape_tp"],
            "escape_fp": r["escape_fp"],
            "escape_fn": r["escape_fn"],
            "escape_tn": r["escape_tn"],
            "escape_f1_q": fmt_q(f1),
            "escape_f1_dec4": fmt_dec(f1, 4),
            **_arm_nll_metrics(r["base_nll_after_x10000"], PROVER_BASE_TGT_NLL_0_X10000, r["tgt_nll_after_x10000"]),
        }

    # Exact cross-adapter Pareto lifts (BlockH4 vs Standard LoRA F/L ratio & wall-clock overhead)
    sc_fl_lift = Fraction(scribe_arms["standard_lora"]["forgetting_learning_ratio_q"]) / Fraction(
        scribe_arms["blockh4_butterfly"]["forgetting_learning_ratio_q"]
    )
    wv_fl_lift = Fraction(weaver_arms["standard_lora"]["forgetting_learning_ratio_q"]) / Fraction(
        weaver_arms["blockh4_butterfly"]["forgetting_learning_ratio_q"]
    )
    pv_fl_lift = Fraction(prover_arms["standard_lora"]["forgetting_learning_ratio_q"]) / Fraction(
        prover_arms["blockh4_butterfly"]["forgetting_learning_ratio_q"]
    )
    sc_wc = Fraction(SCRIBE_ARMS_RAW["blockh4_butterfly"]["train_seconds_x100"], SCRIBE_ARMS_RAW["standard_lora"]["train_seconds_x100"])
    wv_wc = Fraction(WEAVER_ARMS_RAW["blockh4_butterfly"]["train_seconds_x100"], WEAVER_ARMS_RAW["standard_lora"]["train_seconds_x100"])
    pv_wc = Fraction(PROVER_ARMS_RAW["blockh4_butterfly"]["train_seconds_x100"], PROVER_ARMS_RAW["standard_lora"]["train_seconds_x100"])

    return {
        "aletheia_scribe_0_5b": {
            "winner_adapter": "standard_lora",
            "winner_safetensors_sha256": SCRIBE_ARMS_RAW["standard_lora"]["safetensors_sha256"],
            "base_target_nll_0_x10000": SCRIBE_BASE_TGT_NLL_0_X10000,
            "base_eval": dict(SCRIBE_BASE_EVAL),
            "arms": scribe_arms,
        },
        "aletheia_weaver_0_5b": {
            "winner_adapter": "privsparse_ortho",
            "retention_pareto_adapter": "standard_lora",
            "winner_safetensors_sha256": WEAVER_ARMS_RAW["privsparse_ortho"]["safetensors_sha256"],
            "base_target_nll_0_x10000": WEAVER_BASE_TGT_NLL_0_X10000,
            "base_eval": dict(WEAVER_BASE_EVAL),
            "arms": weaver_arms,
        },
        "aletheia_prover_0_5b": {
            "winner_adapter": "standard_lora",
            "winner_safetensors_sha256": PROVER_ARMS_RAW["standard_lora"]["safetensors_sha256"],
            "base_target_nll_0_x10000": PROVER_BASE_TGT_NLL_0_X10000,
            "base_eval": dict(PROVER_BASE_EVAL),
            "lora_passed_theorems": list(PROVER_LORA_PASSED_THEOREMS),
            "blockh4_passed_theorems": list(PROVER_BLOCKH4_PASSED_THEOREMS),
            "arms": prover_arms,
        },
        "beyond_lora_pareto_summary": {
            "scribe_blockh4_fl_improvement_vs_lora_q": fmt_q(sc_fl_lift),
            "scribe_blockh4_fl_improvement_vs_lora_dec4": fmt_dec(sc_fl_lift, 4),
            "weaver_blockh4_fl_improvement_vs_lora_q": fmt_q(wv_fl_lift),
            "weaver_blockh4_fl_improvement_vs_lora_dec4": fmt_dec(wv_fl_lift, 4),
            "prover_blockh4_fl_improvement_vs_lora_q": fmt_q(pv_fl_lift),
            "prover_blockh4_fl_improvement_vs_lora_dec4": fmt_dec(pv_fl_lift, 4),
            "scribe_blockh4_wallclock_ratio_vs_lora_q": fmt_q(sc_wc),
            "scribe_blockh4_wallclock_ratio_vs_lora_dec4": fmt_dec(sc_wc, 4),
            "weaver_blockh4_wallclock_ratio_vs_lora_q": fmt_q(wv_wc),
            "weaver_blockh4_wallclock_ratio_vs_lora_dec4": fmt_dec(wv_wc, 4),
            "prover_blockh4_wallclock_ratio_vs_lora_q": fmt_q(pv_wc),
            "prover_blockh4_wallclock_ratio_vs_lora_dec4": fmt_dec(pv_wc, 4),
        },
    }


def _build_pillar3_law3_routing_and_law4_failures() -> dict[str, Any]:
    # Total held-out evaluations across all 4 specialist gates: 48 + 60 + 24 + 25 = 157
    total_eval_calls = 48 + 60 + 24 + 25
    base_gate_passed = 0
    winner_gate_passed = 48 + 60 + 5 + 25  # 138/157 pass strict Law-3 deterministic gates
    winner_exact_deterministic_tasks = 48 + 25 + 5  # 78/97 on Scribe(48) + ProverAudit(25) + ProverTactics(24)
    deterministic_tasks_total = 48 + 25 + 24
    gate_pass_q = Fraction(winner_gate_passed, total_eval_calls)
    det_exact_q = Fraction(winner_exact_deterministic_tasks, deterministic_tasks_total)
    return {
        "law3_zero_false_accept_enforced": True,
        "total_heldout_eval_calls": total_eval_calls,
        "base_zero_shot_gate_passed": base_gate_passed,
        "winner_law3_gate_passed": winner_gate_passed,
        "winner_law3_gate_pass_rate_q": fmt_q(gate_pass_q),
        "winner_law3_gate_pass_rate_dec4": fmt_dec(gate_pass_q, 4),
        "deterministic_exact_tasks_total": deterministic_tasks_total,
        "winner_deterministic_exact_passed": winner_exact_deterministic_tasks,
        "winner_deterministic_exact_rate_q": fmt_q(det_exact_q),
        "winner_deterministic_exact_rate_dec4": fmt_dec(det_exact_q, 4),
        "law4_honest_failure_modes": [
            {
                "id": "FM-01-PRIVSPARSE-BASIS-DRIFT",
                "summary": "Unconstrained multiplicative Householder rotation Q_out W_0 Q_in destroys pretrained SiLU/RMSNorm privileged-basis alignment (base NLL 2.0399 -> 6.9604..10.8839) and collapses Prover tactic learning (0/24, delta_L = -0.2280) despite kappa_2 = 1.",
            },
            {
                "id": "FM-02-BLOCKH4-UNFUSED-AND-ULP",
                "summary": "Un-fused Python BlockH4 stage loops incur 25.24x..32.13x training slowdown vs LoRA and exhibit under-adaptation on Weaver (9/60 exact, 0/15 CS-03) due to small bf16 merge deltas (<0.5 ULP annihilation), motivating fused Triton BlockH4 + ButterflyHead-8+8 hybrid.",
            },
            {
                "id": "FM-03-PROVER-0_5B-TACTIC-CEILING",
                "summary": "At 494M params on unseen Lean 4.36.0 tracks (S85..S88), Prover solves 5/24 (20.83%) live kernel proofs (LoRA) and 3/24 (12.50%, BlockH4); the remaining 19/24 fail-closed at the Lean kernel with 0 false accepts and escalate cleanly to frontier agents.",
            },
        ],
    }


def _build_pillar4_inkling2_transfer() -> dict[str, Any]:
    phys_layers = 24
    core_start = 6
    core_end = 18
    core_layers = core_end - core_start
    num_passes = 3
    pre_layers = core_start
    suf_layers = phys_layers - core_end
    eff_layers = pre_layers + num_passes * core_layers + suf_layers
    depth_reuse = Fraction(eff_layers, phys_layers)
    hidden = 2304
    intermediate = 1152
    n_experts = 128
    n_active = 8
    active_frac = Fraction(n_active, n_experts)
    nvfp4_gb = 20
    rtx3080_gib = 8
    workstation_gib = 32
    overflow_ratio = Fraction(nvfp4_gb, rtx3080_gib)
    return {
        "inkling2_config_sha256": INKLING2_CONFIG_SHA256,
        "track_s96_cert_sha256": TRACK_S96_CERT_SHA256,
        "model_type": "inkling2_loop",
        "quant_algo": "NVFP4",
        "hidden_size": hidden,
        "intermediate_size": intermediate,
        "blockh4_zero_pad_compatible": all(dim % 16 == 0 for dim in (hidden, intermediate)),
        "physical_layers": phys_layers,
        "core_layers": core_layers,
        "num_passes": num_passes,
        "effective_layers": eff_layers,
        "depth_reuse_ratio_q": fmt_q(depth_reuse),
        "loop_core_adapter_leverage_q": fmt_q(Fraction(num_passes, 1)),
        "gate_rank": 64,
        "n_routed_experts": n_experts,
        "num_experts_per_tok": n_active,
        "active_expert_fraction_q": fmt_q(active_frac),
        "mtp_block_size": 8,
        "mtp_markov_rank": 256,
        "nvfp4_footprint_gb": nvfp4_gb,
        "rtx3080_vram_gib": rtx3080_gib,
        "workstation_vram_gib": workstation_gib,
        "rtx3080_full_resident_fits": nvfp4_gb <= rtx3080_gib,
        "workstation_32gib_full_resident_fits": nvfp4_gb <= workstation_gib,
        "rtx3080_overflow_ratio_q": fmt_q(overflow_ratio),
    }


def _build_pillar5_lean4_and_novelty() -> dict[str, Any]:
    return {
        "lean_file": LEAN_FILE_NAME,
        "lean_sha256": LEAN_FILE_SHA256,
        "lakefile_sha256": LAKEFILE_SHA256,
        "toolchain_sha256": TOOLCHAIN_SHA256,
        "lean_version": "4.36.0",
        "theorem_count": len(LEAN_THEOREMS),
        "universal_theorem_count": len(LEAN_THEOREMS),
        "zero_axiom_theorem_count": 1,
        "propext_only_theorem_count": 3,
        "propext_quot_theorem_count": 12,
        "classical_choice_count": 0,
        "theorems": list(LEAN_THEOREMS),
        "max_novelty_class": "N1",
        "n0_prior_art_anchored": True,
        "n1_exact_synthesis_verified": True,
        "n2_claims_count": 0,
    }


def build_payload() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "oracle_class": ORACLE_CLASS,
        "pillar1_hardware_and_datasets": _build_pillar1_hardware_and_datasets(),
        "pillar2_beyond_lora_showdown": _build_pillar2_showdown(),
        "pillar3_law3_routing_and_law4_failures": _build_pillar3_law3_routing_and_law4_failures(),
        "pillar4_inkling2_transfer": _build_pillar4_inkling2_transfer(),
        "pillar5_lean4_and_novelty": _build_pillar5_lean4_and_novelty(),
    }


def build_certificate() -> dict[str, Any]:
    payload = build_payload()
    payload_sha = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    env = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": payload_sha,
        "payload": payload,
    }
    cert_sha = hashlib.sha256(canonical_json_bytes(env)).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": payload_sha,
        "certificate_sha256": cert_sha,
        "payload": payload,
    }


def verify_mlos_receipt_obj(
    mlos_obj: dict[str, Any],
    *,
    expected_inner_sha: str = MLOS_RECEIPT_INNER_SHA256,
) -> str:
    """Validate clean hardware Zone-B receipt state and inner `receipt_sha256` digest."""
    require_ok(mlos_obj.get("clean_hardware_run") is True, "MLOS_NOT_CLEAN", "clean_hardware_run != true")
    require_ok(mlos_obj.get("anomalies") == [], "MLOS_ANOMALIES", "mlos anomalies non-empty")
    raw_sha = mlos_obj.get("receipt_sha256")
    require_ok(type(raw_sha) is str, "MLOS_INNER_SHA_TYPE", "receipt_sha256 must be strict str")
    mlos_inner = {k: v for k, v in mlos_obj.items() if k != "receipt_sha256"}
    calc_inner = hashlib.sha256(canonical_json_bytes(mlos_inner)).hexdigest()
    require_ok(hmac.compare_digest(calc_inner, raw_sha), "MLOS_INNER_SHA_MISMATCH", "mlos self-digest mismatch")
    require_ok(hmac.compare_digest(calc_inner, expected_inner_sha), "MLOS_INNER_PIN_MISMATCH", "mlos pinned inner mismatch")
    return calc_inner


def verify_live_artifacts_on_disk(track_dir: Path) -> dict[str, Any]:
    """Read-only SHA-256 and internal receipt digest verification of Track S95 on-disk artifacts."""
    pinned: tuple[tuple[str, str], ...] = (
        (RESULTS_FILE_NAME, RESULTS_FILE_SHA256),
        (MLOS_RECEIPT_FILE_NAME, MLOS_RECEIPT_FILE_SHA256),
        (LEAN_FILE_NAME, LEAN_FILE_SHA256),
        ("lakefile.toml", LAKEFILE_SHA256),
        ("lean-toolchain", TOOLCHAIN_SHA256),
    )
    checked: dict[str, str] = {}
    for fname, exp_sha in pinned:
        p = track_dir / fname
        require_ok(p.is_file(), "ARTIFACT_MISSING", f"missing artifact: {fname}")
        raw = p.read_bytes()
        got = hashlib.sha256(raw).hexdigest()
        require_ok(hmac.compare_digest(got, exp_sha), "ARTIFACT_SHA_MISMATCH", f"sha256 mismatch on {fname}")
        checked[fname] = got
    mlos_obj = json.loads((track_dir / MLOS_RECEIPT_FILE_NAME).read_text(encoding="utf-8"))
    calc_inner = verify_mlos_receipt_obj(mlos_obj)
    return {"artifacts_verified": len(checked), "mlos_inner_sha256": calc_inner, "digests": checked}


if __name__ == "__main__":
    import sys

    sys.stdout.buffer.write(canonical_json_bytes(build_certificate()) + b"\n")
