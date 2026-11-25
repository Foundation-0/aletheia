#!/usr/bin/env python3
"""Zone-B Hardened Standalone CLI, R12 Live Lean 4.36.0 & Secondary Auditor for Track S86 (R3).

100% pure Python 3 stdlib, zero IEEE-754 floats, zero bare asserts, zero .isdigit(),
zero mathematical RNG (secrets.token_hex used strictly for atomic temp filenames).
Includes full R12 Lean 4.36.0 static pre-filter (paired with mandatory live `#print axioms`
kernel verification under allowlisted `SAFE_LEAN_ENV_KEYS` subprocess scrubbing), pre-`int()`
>4300-digit rational/decimal bounds, empirical JSON anchor cross-verification, field-complete
every-leaf SEC/FR0 pinning, and 0-skip Lean-less CI compatibility.
"""
from __future__ import annotations

import errno
from fractions import Fraction
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
from typing import Any, Sequence

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import s86_sovereign_stack_oracle as oracle  # noqa: E402

MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_ALLOWED_CAP_BYTES = 64 * 1024 * 1024
_READ_CHUNK_BYTES = 65_536
_EXACT_PATH_TYPES = (Path, type(Path()))
_DIR_OPEN_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_TEMP_NAME_LOCK = threading.Lock()
_TEMP_SEQ = 0
_ALLOWED_LEAN_AXIOMS = frozenset({"propext"})
SAFE_LEAN_ENV_KEYS: frozenset[str] = frozenset({"PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "TERM", "USER"})

_CERT_KEYS = frozenset({"schema_version", "track_id", "payload_sha256", "certificate_sha256", "payload"})
_PAYLOAD_KEYS = frozenset({
    "schema_version",
    "track_id",
    "oracle_class",
    "novelty_classification",
    "measured_live_rtx3080",
    "pinned_artifacts",
    "pillar1_t3_blowup_cce_det",
    "pillar2_borromean_4way_stack",
    "pillar3_csr_1_over_160_crossover",
    "pillar4_joint_mdl_and_mellin_glu",
})
_PINNED_KEYS = frozenset({
    "lean_source",
    "lean_source_sha256",
    "lean_toolchain",
    "lean_toolchain_sha256",
    "lakefile_sha256",
    "lean_theorem_count",
    "lean_universal_theorem_count",
    "lean_witness_theorem_count",
    "lean_theorem_names",
    "empirical_results_file",
    "empirical_results_sha256",
    "mlos_receipt_file",
    "mlos_receipt_file_sha256",
    "mlos_receipt_inner_sha256",
    "qwen3b_3bpw_safetensors_sha256",
    "qwen3b_45bpw_safetensors_sha256",
    "qwen3b_3bpw_syndrome_errors",
    "qwen3b_45bpw_syndrome_errors",
    "dequant_eval_parity_max_diff_piconats",
    "upstream_cert_pins",
})
_UPSTREAM_PIN_KEYS = frozenset({"track", "file", "sha256"})
_P1_KEYS = frozenset({
    "vocab_size",
    "hidden_size",
    "n1024_mat_fp32_mib_dec2",
    "n1024_cce_det_frozen_mib_dec2",
    "n1024_compression_ratio_q",
    "n1024_compression_ratio_dec4",
    "n2048_mat_fp32_mib_dec2",
    "n2048_cce_det_frozen_mib_dec2",
    "n2048_compression_ratio_q",
    "n2048_compression_ratio_dec4",
    "n4096_mat_fp32_oom",
    "n4096_mat_bf16_ce_oom",
    "n4096_cce_det_frozen_bytes",
    "n4096_cce_det_frozen_mib_dec2",
    "n4096_cce_det_train_bytes",
    "n4096_cce_det_train_mib_dec2",
    "n8192_mat_fp32_oom",
    "n8192_mat_bf16_ce_oom",
    "n8192_cce_det_frozen_bytes",
    "n8192_cce_det_frozen_mib_dec2",
    "acc_loss_abs_err_piconats",
    "acc_lse_max_ulp_vs_fp32",
    "acc_grad_h_rel_l2_err_ppb",
    "cce_det_rep_runs",
    "cce_det_rep_n_tokens",
    "cce_det_rep_unique_hashes",
    "cce_det_rep_max_ulp",
    "cce_det_rep_loss_sha256",
    "cce_det_rep_grad_h_sha256",
    "cce_det_rep_grad_w_sha256",
    "atomic_cas_unique_sha256",
    "atomic_cas_divergent_rows",
    "atomic_cas_divergent_pct_dec2",
    "atomic_cas_max_ulp",
    "atomic_add_unique_sha256",
    "atomic_add_divergent_rows",
    "atomic_add_divergent_pct_dec2",
    "atomic_add_max_ulp",
    "perm_asc_vs_desc_div_rows",
    "perm_asc_vs_desc_pct_dec2",
    "perm_asc_vs_desc_max_ulp",
    "perm_asc_vs_striped_div_rows",
    "perm_asc_vs_striped_pct_dec2",
    "k8_triangles_flipped_by_t3",
})
_P2_KEYS = frozenset({
    "vram_budget_mib",
    "vram_budget_bytes",
    "train_n_tokens",
    "no_s78_full_finetune_oom",
    "no_s73_bf16_r64_oom",
    "no_s73_bf16_r128_oom",
    "no_s80_3bpw_mat_fp32_oom",
    "no_s80_45bpw_mat_fp32_oom",
    "no_s79_r64_oom",
    "no_s79_r64_peak_alloc_bytes",
    "no_s79_r64_peak_alloc_mib_dec2",
    "no_s79_r64_step0_loss_nano",
    "full_r16_peak_alloc_bytes",
    "full_r16_peak_alloc_mib_dec2",
    "full_r16_headroom_mib_dec2",
    "full_r16_trainable_params",
    "full_r64_peak_alloc_bytes",
    "full_r64_peak_alloc_mib_dec2",
    "full_r64_peak_res_bytes",
    "full_r64_peak_res_mib_dec2",
    "full_r64_headroom_mib_dec2",
    "full_r64_trainable_params",
    "full_r64_step_losses_nano",
    "full_r64_loss_strictly_decreasing",
    "full_r64_5step_loss_drop_pct_q",
    "full_r64_5step_loss_drop_pct_dec2",
    "full_r64_bit_identical_repeatability",
    "full_r64_final_trainable_sha256",
    "full_r128_peak_alloc_bytes",
    "full_r128_peak_alloc_mib_dec2",
    "full_r128_headroom_mib_dec2",
    "full_r128_trainable_params",
})
_P3_KEYS = frozenset({
    "total_block_weights",
    "q45_wt_kl_nano",
    "q45_py_kl_nano",
    "q30_wt_kl_nano",
    "q30_py_kl_nano",
    "csr0125_wt_kl_nano",
    "csr0125_py_kl_nano",
    "csr0125_wt_drop_pct_dec2",
    "csr0125_py_drop_pct_dec2",
    "csr0250_wt_kl_nano",
    "csr0250_py_kl_nano",
    "csr0250_wt_drop_pct_dec2",
    "csr0250_py_drop_pct_dec2",
    "csr0500_nnz",
    "csr0500_bytes",
    "csr0500_mib_dec2",
    "csr0500_rho_q",
    "csr0500_strictly_below_1_over_160",
    "csr0500_bpw_overhead_q",
    "csr0500_bpw_overhead_dec4",
    "csr0500_sens_out",
    "csr0500_sens_total",
    "csr0500_sens_frac_q",
    "csr0500_sens_frac_pct_dec2",
    "csr0500_sout_over_sbulk_pct_dec2",
    "s79_m54_crossover_ratio_q",
    "s79_m54_crossover_ratio_dec4",
    "s79_crossover_wins",
    "csr0500_wt_kl_nano",
    "csr0500_py_kl_nano",
    "csr0500_wt_drop_pct_dec2",
    "csr0500_py_drop_pct_dec2",
    "raw0500_wt_kl_nano",
    "raw0500_py_kl_nano",
    "raw0500_wt_drop_pct_dec2",
    "raw0500_py_drop_pct_dec2",
    "hessian_vs_raw_wt_leverage_q",
    "hessian_vs_raw_wt_leverage_dec4",
    "hessian_vs_raw_py_leverage_q",
    "hessian_vs_raw_py_leverage_dec4",
})
_P4_KEYS = frozenset({
    "qwen3b_n_base",
    "qwen3b_p1_all7",
    "bits_freed_16_to_3bpw",
    "delta_rank_b16",
    "delta_rank_adam64",
    "wt_horizon_lift_q",
    "wt_horizon_lift_dec4",
    "py_horizon_lift_q",
    "py_horizon_lift_dec4",
    "mellin_slice_weights",
    "mellin_rungs",
    "mellin_density_q",
    "mellin_csr_budget_0p50pct",
    "mellin_rung_share_of_csr_budget_q",
    "mellin_rung_share_of_csr_budget_pct_dec2",
    "mellin_45bpw_blind_passes",
    "mellin_45bpw_blind_err_micro",
    "mellin_30bpw_blind_passes",
    "mellin_30bpw_blind_err_micro",
    "mellin_30bpw_mag_csr_passes",
    "mellin_30bpw_mag_csr_err_micro",
    "mellin_30bpw_sens_csr_passes",
    "mellin_30bpw_sens_csr_err_micro",
    "mellin_syndrome_errors",
    "mellin_oob_groups",
})

# R12 Lean 4 static pre-filter patterns (applied after comment stripping; paired with mandatory
# live `Lean 4.36.0` `#print axioms` verification). Blocks quotes/guillemets (incl. Char literals),
# all R10+/R11/R12 escape tokens (`dbgTrace*`, `dbgSleep`, `dbgStackTrace`, `dbg_sleep`,
# `dbg_stack_trace`, `dbg_trace_if`, `@[export|init|builtin_init|...]`, `attribute [...]`,
# `export`, `builtin_init`, capitalized `Lean.`/`IO.`/`System.`/`Meta.`/`Elab.`), `+native`
# tactic modifiers, and single-/multi-line `native :=` boolean-expression bypasses while keeping
# `decide (native := false)` & `decide (native := Bool.false)` false-positive free.
_LEAN4_BANNED_RE = re.compile(
    r"(?:"
    r"\"|'|«|»"
    r"|\b(?:import|sorry|admit|axiom|unsafe|implemented_by|extern|csimp|native_decide|sorryAx)\b"
    r"|\b(?:partial|opaque|initialize|builtin_initialize|builtin_init|export|run_cmd|run_meta)\b"
    r"|\b(?:notation|infixl?|infixr|prefix|postfix|macro|macro_rules|syntax|declare_syntax_cat|elab|elab_rules)\b"
    r"|\b(?:ofReduceBool|ofReduceNat|trustCompiler|mkSorry|throwError|DecideConfig)\b"
    r"|\b(?:dbg_trace|dbg_trace_if|dbg_sleep|dbg_stack_trace|dbgTrace|dbgTraceVal|dbgTraceIfShared|dbgSleep|dbgStackTrace)\b"
    r"|@\s*\[[^\]]*\b(?:export|init|builtin_init|implemented_by|extern|csimp)\b"
    r"|\battribute\s*\[[^\]]*\b(?:export|init|builtin_init|implemented_by|extern|csimp)\b"
    r"|\b(?:Lean|IO|System|Meta|Elab)\s*\."
    r"|#\s*(?:eval|reduce|guard_msgs|exit)\b"
    r"|\bdebug\s*\."
    r"|\bset_option\b"
    r"|(?<!\w)\+\s*native\b"
    r"|\bconfig\s*:="
    r"|\{[^}]*\bnative\b"
    r"|\bdecide\s*\([^)]*\brevert\b"
    r"|\bnative\s*:=(?!\s*(?:Bool\.)?false\s*(?:[),}]|\Z))"
    r")"
)
_POS_DEC2_RE = re.compile(r"\A(?:0|[1-9][0-9]*)\.[0-9]{2}\Z")
_LEAN4_AXIOM_NONE_RE = re.compile(r"^'([A-Za-z0-9_.]+)' does not depend on any axioms$")
_LEAN4_AXIOM_DEP_RE = re.compile(r"^'([A-Za-z0-9_.]+)' depends on axioms: \[([^\]]*)\]$")

# Field-complete pinned exact checks closing all 38 single-leaf SEC/FR0 degrees of freedom
# (all other 165 leaves are already pinned by relational/schema invariants in secondary_audit_payload).
_PINNED_SEC_EXACT_CHECKS: tuple[tuple[str, str, Any], ...] = (
    ("pinned_artifacts", "lean_source_sha256", oracle.EXPECTED_LEAN_SHA256),
    ("pinned_artifacts", "lean_toolchain_sha256", oracle.EXPECTED_TOOLCHAIN_SHA256),
    ("pinned_artifacts", "lakefile_sha256", oracle.EXPECTED_LAKEFILE_SHA256),
    ("pinned_artifacts", "empirical_results_sha256", oracle.EXPECTED_EMPIRICAL_SHA256),
    ("pinned_artifacts", "qwen3b_3bpw_safetensors_sha256", oracle.PINNED_LIVE_ANCHORS["qwen3b_3bpw_safetensors_sha256"]),
    ("pinned_artifacts", "qwen3b_45bpw_safetensors_sha256", oracle.PINNED_LIVE_ANCHORS["qwen3b_45bpw_safetensors_sha256"]),
    ("pillar1_t3_blowup_cce_det", "n4096_cce_det_frozen_bytes", oracle.PINNED_LIVE_ANCHORS["n4096_cce_det_frozen_bytes"]),
    ("pillar1_t3_blowup_cce_det", "n4096_cce_det_train_bytes", oracle.PINNED_LIVE_ANCHORS["n4096_cce_det_train_bytes"]),
    ("pillar1_t3_blowup_cce_det", "n8192_cce_det_frozen_bytes", oracle.PINNED_LIVE_ANCHORS["n8192_cce_det_frozen_bytes"]),
    ("pillar1_t3_blowup_cce_det", "acc_lse_max_ulp_vs_fp32", oracle.PINNED_LIVE_ANCHORS["acc_lse_max_ulp_vs_fp32"]),
    ("pillar1_t3_blowup_cce_det", "acc_grad_h_rel_l2_err_ppb", oracle.PINNED_LIVE_ANCHORS["acc_grad_h_rel_l2_err_ppb"]),
    ("pillar1_t3_blowup_cce_det", "cce_det_rep_runs", oracle.PINNED_LIVE_ANCHORS["cce_det_rep_runs"]),
    ("pillar1_t3_blowup_cce_det", "cce_det_rep_loss_sha256", oracle.PINNED_LIVE_ANCHORS["cce_det_rep_loss_sha256"]),
    ("pillar1_t3_blowup_cce_det", "cce_det_rep_grad_h_sha256", oracle.PINNED_LIVE_ANCHORS["cce_det_rep_grad_h_sha256"]),
    ("pillar1_t3_blowup_cce_det", "cce_det_rep_grad_w_sha256", oracle.PINNED_LIVE_ANCHORS["cce_det_rep_grad_w_sha256"]),
    ("pillar1_t3_blowup_cce_det", "atomic_cas_max_ulp", oracle.PINNED_LIVE_ANCHORS["atomic_cas_max_ulp"]),
    ("pillar1_t3_blowup_cce_det", "atomic_add_max_ulp", oracle.PINNED_LIVE_ANCHORS["atomic_add_max_ulp"]),
    ("pillar1_t3_blowup_cce_det", "perm_asc_vs_desc_max_ulp", oracle.PINNED_LIVE_ANCHORS["perm_asc_vs_desc_max_ulp"]),
    ("pillar2_borromean_4way_stack", "no_s79_r64_peak_alloc_bytes", oracle.PINNED_LIVE_ANCHORS["no_s79_r64_peak_alloc_bytes"]),
    ("pillar2_borromean_4way_stack", "no_s79_r64_step0_loss_nano", oracle.PINNED_LIVE_ANCHORS["no_s79_r64_step0_loss_nano"]),
    ("pillar2_borromean_4way_stack", "full_r16_peak_alloc_bytes", oracle.PINNED_LIVE_ANCHORS["full_r16_peak_alloc_bytes"]),
    ("pillar2_borromean_4way_stack", "full_r64_peak_alloc_bytes", oracle.PINNED_LIVE_ANCHORS["full_r64_peak_alloc_bytes"]),
    ("pillar2_borromean_4way_stack", "full_r64_peak_res_bytes", oracle.PINNED_LIVE_ANCHORS["full_r64_peak_res_bytes"]),
    ("pillar2_borromean_4way_stack", "full_r64_step_losses_nano", oracle.PINNED_LIVE_ANCHORS["full_r64_step_losses_nano"]),
    ("pillar2_borromean_4way_stack", "full_r64_final_trainable_sha256", oracle.PINNED_LIVE_ANCHORS["full_r64_final_trainable_sha256"]),
    ("pillar2_borromean_4way_stack", "full_r128_peak_alloc_bytes", oracle.PINNED_LIVE_ANCHORS["full_r128_peak_alloc_bytes"]),
    ("pillar3_csr_1_over_160_crossover", "q45_wt_kl_nano", oracle.PINNED_LIVE_ANCHORS["q45_wt_kl_nano"]),
    ("pillar3_csr_1_over_160_crossover", "q45_py_kl_nano", oracle.PINNED_LIVE_ANCHORS["q45_py_kl_nano"]),
    ("pillar3_csr_1_over_160_crossover", "csr0125_wt_kl_nano", oracle.PINNED_LIVE_ANCHORS["csr0125_wt_kl_nano"]),
    ("pillar3_csr_1_over_160_crossover", "csr0125_py_kl_nano", oracle.PINNED_LIVE_ANCHORS["csr0125_py_kl_nano"]),
    ("pillar3_csr_1_over_160_crossover", "csr0250_wt_kl_nano", oracle.PINNED_LIVE_ANCHORS["csr0250_wt_kl_nano"]),
    ("pillar3_csr_1_over_160_crossover", "csr0250_py_kl_nano", oracle.PINNED_LIVE_ANCHORS["csr0250_py_kl_nano"]),
    ("pillar4_joint_mdl_and_mellin_glu", "mellin_45bpw_blind_err_micro", oracle.PINNED_LIVE_ANCHORS["mellin_45bpw_blind_err_micro"]),
    ("pillar4_joint_mdl_and_mellin_glu", "mellin_30bpw_blind_err_micro", oracle.PINNED_LIVE_ANCHORS["mellin_30bpw_blind_err_micro"]),
    ("pillar4_joint_mdl_and_mellin_glu", "mellin_30bpw_mag_csr_err_micro", oracle.PINNED_LIVE_ANCHORS["mellin_30bpw_mag_csr_err_micro"]),
    ("pillar4_joint_mdl_and_mellin_glu", "mellin_30bpw_sens_csr_err_micro", oracle.PINNED_LIVE_ANCHORS["mellin_30bpw_sens_csr_err_micro"]),
)

# Direct JSON-path bindings cross-checking rtx3080_s86_empirical_results.json against PINNED_LIVE_ANCHORS
_EMPIRICAL_ANCHOR_PATHS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("eval_seed",), "eval_seed"),
    (("elapsed_us",), "elapsed_us"),
    (("cpu_rapl_uj",), "cpu_rapl_uj"),
    (("model_pins", "total_block_weights"), "qwen3b_total_block_weights"),
    (("model_pins", "qwen25_3b_3bpw_safetensors_sha256"), "qwen3b_3bpw_safetensors_sha256"),
    (("model_pins", "qwen25_3b_45bpw_safetensors_sha256"), "qwen3b_45bpw_safetensors_sha256"),
    (("model_pins", "qwen3b_3bpw_syndrome_check", "total_syndrome_errors"), "qwen3b_3bpw_syndrome_errors"),
    (("model_pins", "qwen3b_45bpw_syndrome_check", "total_syndrome_errors"), "qwen3b_45bpw_syndrome_errors"),
    (("part1_cce_det_t3_blowup", "vocab_size"), "vocab_size"),
    (("part1_cce_det_t3_blowup", "hidden_size"), "hidden_size"),
    (("part1_cce_det_t3_blowup", "vram_sweep", "N_1024", "materialized_fp32_frozen_head", "peak_alloc_bytes"), "n1024_mat_fp32_bytes"),
    (("part1_cce_det_t3_blowup", "vram_sweep", "N_1024", "cce_det_frozen_head", "peak_alloc_bytes"), "n1024_cce_det_frozen_bytes"),
    (("part1_cce_det_t3_blowup", "vram_sweep", "N_2048", "materialized_fp32_frozen_head", "peak_alloc_bytes"), "n2048_mat_fp32_bytes"),
    (("part1_cce_det_t3_blowup", "vram_sweep", "N_2048", "cce_det_frozen_head", "peak_alloc_bytes"), "n2048_cce_det_frozen_bytes"),
    (("part1_cce_det_t3_blowup", "vram_sweep", "N_4096", "cce_det_frozen_head", "peak_alloc_bytes"), "n4096_cce_det_frozen_bytes"),
    (("part1_cce_det_t3_blowup", "vram_sweep", "N_4096", "cce_det_trainable_head", "peak_alloc_bytes"), "n4096_cce_det_train_bytes"),
    (("part1_cce_det_t3_blowup", "vram_sweep", "N_8192", "cce_det_frozen_head", "peak_alloc_bytes"), "n8192_cce_det_frozen_bytes"),
    (("part1_cce_det_t3_blowup", "accuracy_vs_fp32_ref", "loss_abs_err_piconats"), "acc_loss_abs_err_piconats"),
    (("part1_cce_det_t3_blowup", "accuracy_vs_fp32_ref", "lse_max_ulp_vs_fp32"), "acc_lse_max_ulp_vs_fp32"),
    (("part1_cce_det_t3_blowup", "accuracy_vs_fp32_ref", "grad_h_rel_l2_err_ppb"), "acc_grad_h_rel_l2_err_ppb"),
    (("part1_cce_det_t3_blowup", "cce_det_repeatability", "loss_sha256"), "cce_det_rep_loss_sha256"),
    (("part1_cce_det_t3_blowup", "cce_det_repeatability", "grad_h_sha256"), "cce_det_rep_grad_h_sha256"),
    (("part1_cce_det_t3_blowup", "cce_det_repeatability", "grad_w_sha256"), "cce_det_rep_grad_w_sha256"),
    (("part1_cce_det_t3_blowup", "triton_atomic_and_permutation_probe", "atomic_cas_spinlock", "max_divergent_rows"), "atomic_cas_divergent_rows"),
    (("part1_cce_det_t3_blowup", "triton_atomic_and_permutation_probe", "atomic_add", "max_divergent_rows"), "atomic_add_divergent_rows"),
    (("part1_cce_det_t3_blowup", "triton_atomic_and_permutation_probe", "tile_permutation_drift", "asc_vs_desc_divergent_rows"), "perm_asc_vs_desc_div_rows"),
    (("part1_cce_det_t3_blowup", "triton_atomic_and_permutation_probe", "tile_permutation_drift", "asc_vs_striped_divergent_rows"), "perm_asc_vs_striped_div_rows"),
    (("part2_sovereign_stack", "dequant_eval_parity_max_diff_piconats"), "dequant_eval_parity_max_diff_piconats"),
    (("part2_sovereign_stack", "eval_arms", "siliquant_4p5bpw_quad_snake", "wikitext2", "kl_nanonats"), "q45_wt_kl_nano"),
    (("part2_sovereign_stack", "eval_arms", "siliquant_4p5bpw_quad_snake", "cpython", "kl_nanonats"), "q45_py_kl_nano"),
    (("part2_sovereign_stack", "eval_arms", "siliquant_3p0bpw_quad_snake_nocsr", "wikitext2", "kl_nanonats"), "q30_wt_kl_nano"),
    (("part2_sovereign_stack", "eval_arms", "siliquant_3p0bpw_quad_snake_nocsr", "cpython", "kl_nanonats"), "q30_py_kl_nano"),
    (("part2_sovereign_stack", "eval_arms", "hessian_csr_0p125pct", "wikitext2", "kl_nanonats"), "csr0125_wt_kl_nano"),
    (("part2_sovereign_stack", "eval_arms", "hessian_csr_0p125pct", "cpython", "kl_nanonats"), "csr0125_py_kl_nano"),
    (("part2_sovereign_stack", "eval_arms", "hessian_csr_0p250pct", "wikitext2", "kl_nanonats"), "csr0250_wt_kl_nano"),
    (("part2_sovereign_stack", "eval_arms", "hessian_csr_0p250pct", "cpython", "kl_nanonats"), "csr0250_py_kl_nano"),
    (("part2_sovereign_stack", "eval_arms", "hessian_csr_0p500pct", "csr_nnz"), "csr0500_nnz"),
    (("part2_sovereign_stack", "eval_arms", "hessian_csr_0p500pct", "csr_bytes"), "csr0500_bytes"),
    (("part2_sovereign_stack", "eval_arms", "hessian_csr_0p500pct", "sens_out_scaled"), "csr0500_sens_out"),
    (("part2_sovereign_stack", "eval_arms", "hessian_csr_0p500pct", "sens_total_scaled"), "csr_sens_total"),
    (("part2_sovereign_stack", "eval_arms", "hessian_csr_0p500pct", "wikitext2", "kl_nanonats"), "csr0500_wt_kl_nano"),
    (("part2_sovereign_stack", "eval_arms", "hessian_csr_0p500pct", "cpython", "kl_nanonats"), "csr0500_py_kl_nano"),
    (("part2_sovereign_stack", "eval_arms", "raw_mag_csr_0p500pct", "wikitext2", "kl_nanonats"), "raw0500_wt_kl_nano"),
    (("part2_sovereign_stack", "eval_arms", "raw_mag_csr_0p500pct", "cpython", "kl_nanonats"), "raw0500_py_kl_nano"),
    (("part2_sovereign_stack", "vram_and_training_ablations", "no_s79_3bpw_nocsr_lora_r64_cce_det", "peak_alloc_bytes"), "no_s79_r64_peak_alloc_bytes"),
    (("part2_sovereign_stack", "vram_and_training_ablations", "full_4way_3bpw_csr0p50_lora_r16_cce_det", "peak_alloc_bytes"), "full_r16_peak_alloc_bytes"),
    (("part2_sovereign_stack", "vram_and_training_ablations", "full_4way_3bpw_csr0p50_lora_r64_cce_det_run1", "peak_alloc_bytes"), "full_r64_peak_alloc_bytes"),
    (("part2_sovereign_stack", "vram_and_training_ablations", "full_4way_3bpw_csr0p50_lora_r64_cce_det_run1", "peak_reserved_bytes"), "full_r64_peak_res_bytes"),
    (("part2_sovereign_stack", "vram_and_training_ablations", "full_4way_3bpw_csr0p50_lora_r64_cce_det_run1", "step_losses_nanonats"), "full_r64_step_losses_nano"),
    (("part2_sovereign_stack", "vram_and_training_ablations", "full_4way_3bpw_csr0p50_lora_r64_cce_det_run1", "final_trainable_sha256"), "full_r64_final_trainable_sha256"),
    (("part2_sovereign_stack", "vram_and_training_ablations", "full_4way_3bpw_csr0p50_lora_r128_cce_det", "peak_alloc_bytes"), "full_r128_peak_alloc_bytes"),
    (("part3_mellin_glu_carry_spotcheck", "total_slice_weights"), "mellin_slice_weights"),
    (("part3_mellin_glu_carry_spotcheck", "grafted_mellin_rungs"), "mellin_rungs"),
    (("part3_mellin_glu_carry_spotcheck", "regimes", "a16_blockh4_4p5bpw", "blind_no_csr", "max_abs_err_micro"), "mellin_45bpw_blind_err_micro"),
    (("part3_mellin_glu_carry_spotcheck", "regimes", "a16_blockh4_3p0bpw", "blind_no_csr", "max_abs_err_micro"), "mellin_30bpw_blind_err_micro"),
    (("part3_mellin_glu_carry_spotcheck", "regimes", "a16_blockh4_3p0bpw", "blind_mag_csr_0p50pct", "max_abs_err_micro"), "mellin_30bpw_mag_csr_err_micro"),
    (("part3_mellin_glu_carry_spotcheck", "regimes", "a16_blockh4_3p0bpw", "sensitivity_csr_0p50pct_fp32", "max_abs_err_micro"), "mellin_30bpw_sens_csr_err_micro"),
)


# ---------------------------------------------------------------------------
# Hardened Zone-B File I/O (dir_fd step-down, $PWD symlink ban, O_NOFOLLOW)
# ---------------------------------------------------------------------------

def _require_concrete_path(path: Any, label: str) -> Path:
    oracle.require_ok(type(path) in _EXACT_PATH_TYPES, "INVALID_PATH_TYPE", f"{label}: exact Path required")
    s = str(path)
    oracle.require_ok("\x00" not in s, "INVALID_PATH", f"{label}: NUL path")
    return path


def _check_pwd_no_symlink(label: str) -> None:
    pwd = os.environ.get("PWD")
    if not pwd:
        return
    p = Path(pwd)
    if not p.is_absolute():
        return
    cur = Path("/")
    for part in p.parts[1:]:
        cur = cur / part
        try:
            st = os.lstat(cur)
        except OSError:
            return
        oracle.require_ok(not stat.S_ISLNK(st.st_mode), "SYMLINK_FORBIDDEN", f"{label}: $PWD contains symlink")


def _open_parent_dir_fd_strict(path: Path, label: str) -> tuple[int, str]:
    p = _require_concrete_path(path, label)
    if not p.is_absolute():
        _check_pwd_no_symlink(label)
        p = Path(os.getcwd()) / p
    parts = p.parts
    oracle.require_ok(len(parts) >= 2, "INVALID_PATH", f"{label}: invalid path structure")
    oracle.require_ok(
        all(part not in ("", ".", "..") for part in parts[1:]),
        "PATH_TRAVERSAL_FORBIDDEN",
        f"{label}: dot segments forbidden",
    )
    dfd = os.open("/", _DIR_OPEN_FLAGS)
    try:
        for seg in parts[1:-1]:
            nxt = os.open(seg, _DIR_OPEN_FLAGS, dir_fd=dfd)
            os.close(dfd)
            dfd = nxt
    except OSError as exc:
        os.close(dfd)
        code = "SYMLINK_FORBIDDEN" if exc.errno in (errno.ELOOP, errno.ENOTDIR) else "DIR_OPEN_ERROR"
        raise oracle.S86Error(code, f"{label}: cannot open parent directory") from exc
    return dfd, parts[-1]


def read_regular_bytes_capped(path: Path, label: str, *, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    oracle.require_exact_int(max_bytes, "max_bytes", lo=1, hi=MAX_ALLOWED_CAP_BYTES)
    dfd, leaf = _open_parent_dir_fd_strict(path, label)
    fd = -1
    try:
        fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
        st = os.fstat(fd)
        oracle.require_ok(stat.S_ISREG(st.st_mode), "NON_REGULAR_FILE", f"{label}: regular file required")
        oracle.require_ok(st.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: hardlink forbidden")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, _READ_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            oracle.require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"{label}: exceeds {max_bytes} bytes")
            chunks.append(chunk)
        return b"".join(chunks)
    except oracle.S86Error:
        raise
    except OSError as exc:
        code = "SYMLINK_FORBIDDEN" if exc.errno == errno.ELOOP else "FILE_READ_ERROR"
        raise oracle.S86Error(code, f"{label}: read failed") from exc
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(dfd)


def write_regular_bytes_safe(path: Path, data: bytes, label: str) -> None:
    global _TEMP_SEQ
    oracle.require_ok(type(data) is bytes, "INVALID_BYTES", f"{label}: exact bytes required")
    dfd, leaf = _open_parent_dir_fd_strict(path, label)
    tmp_name: str | None = None
    try:
        try:
            st_dst = os.lstat(leaf, dir_fd=dfd)
            oracle.require_ok(not stat.S_ISLNK(st_dst.st_mode), "SYMLINK_FORBIDDEN", f"{label}: target is symlink")
            oracle.require_ok(stat.S_ISREG(st_dst.st_mode), "NON_REGULAR_FILE", f"{label}: target non-regular")
            oracle.require_ok(st_dst.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: target hardlinked")
        except FileNotFoundError:
            pass
        with _TEMP_NAME_LOCK:
            _TEMP_SEQ += 1
            seq = _TEMP_SEQ
        tmp_name = f".s86_tmp_{os.getpid()}_{seq}_{secrets.token_hex(8)}"
        fd = os.open(tmp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=dfd)
        try:
            os.fchmod(fd, 0o600)
            view = memoryview(data)
            written = 0
            while written < len(view):
                n_w = os.write(fd, view[written:])
                oracle.require_ok(n_w > 0, "FILE_WRITE_ERROR", f"{label}: zero-byte write")
                written += n_w
            os.fsync(fd)
            oracle.require_ok(os.fstat(fd).st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: temp hardlinked")
        finally:
            os.close(fd)
        os.replace(tmp_name, leaf, src_dir_fd=dfd, dst_dir_fd=dfd)
        tmp_name = None
        os.fsync(dfd)
    except oracle.S86Error:
        raise
    except OSError as exc:
        raise oracle.S86Error("FILE_WRITE_ERROR", f"{label}: write failed") from exc
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
        os.close(dfd)


# ---------------------------------------------------------------------------
# Strict Zero-Float Canonical JSON & Rational Parsers
# ---------------------------------------------------------------------------

def _parse_bounded_int(token: str) -> int:
    s = oracle.require_exact_str(token, "json_int")
    neg = s.startswith("-")
    body = s[1:] if neg else s
    oracle.require_ok(oracle.is_ascii_digits(body), "INVALID_INT_TOKEN", "non-ASCII digits")
    oracle.require_ok(len(body) <= oracle.MAX_INT_DIGITS, "INT_TOO_LARGE", "int digits cap")
    oracle.require_ok(not (len(body) > 1 and body[0] == "0"), "NONCANONICAL_INT", "leading zero")
    oracle.require_ok(not (neg and body == "0"), "NONCANONICAL_INT", "negative zero")
    val = int(s)
    oracle.require_ok(val.bit_length() <= oracle.MAX_INT_BITS, "INT_TOO_LARGE", "int bits cap")
    return val


def _reject_float(token: str) -> Any:
    raise oracle.S86Error("FLOAT_FORBIDDEN", f"IEEE-754 float forbidden: {token!r}")


def _reject_const(token: str) -> Any:
    raise oracle.S86Error("NONFINITE_JSON_CONSTANT", f"JSON constant forbidden: {token!r}")


def _no_dup_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        oracle.require_ok(k not in out, "DUPLICATE_JSON_KEY", f"duplicate key {k!r}")
        out[k] = v
    return out


def parse_strict_json_bytes(raw: bytes, label: str = "json", *, require_canonical: bool = True) -> dict[str, Any]:
    oracle.require_ok(type(raw) is bytes, "INVALID_BYTES", f"{label}: exact bytes required")
    oracle.require_ok(not raw.startswith(b"\xef\xbb\xbf"), "BOM_FORBIDDEN", f"{label}: UTF-8 BOM forbidden")
    oracle.require_ok(b"\r" not in raw, "CRLF_FORBIDDEN", f"{label}: CR forbidden")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise oracle.S86Error("INVALID_UTF8", f"{label}: invalid UTF-8") from exc
    try:
        obj = json.loads(
            text,
            parse_float=_reject_float,
            parse_int=_parse_bounded_int,
            parse_constant=_reject_const,
            object_pairs_hook=_no_dup_pairs,
        )
    except oracle.S86Error:
        raise
    except (ValueError, RecursionError) as exc:
        raise oracle.S86Error("INVALID_JSON", f"{label}: malformed JSON") from exc
    oracle.require_ok(type(obj) is dict, "INVALID_ROOT_TYPE", f"{label}: root must be dict")
    oracle.validate_strict_json_tree(obj, label)
    if require_canonical:
        oracle.require_ok(
            hmac.compare_digest(raw, oracle.canonical_json_bytes(obj)),
            "NONCANONICAL_JSON",
            f"{label}: not canonical ASCII LF JSON",
        )
    return obj


def parse_canonical_rational_str(val: Any, label: str) -> Fraction:
    s = oracle.require_exact_str(val, label)
    oracle.require_ok(len(s) > 0, "INVALID_RATIONAL", f"{label}: empty")
    oracle.require_ok(len(s) <= 2 * oracle.MAX_INT_DIGITS + 2, "INT_TOO_LARGE", f"{label}: rational length cap")
    if "/" in s:
        parts = s.split("/")
        oracle.require_ok(len(parts) == 2, "INVALID_RATIONAL", f"{label}: multiple slashes")
        num = _parse_bounded_int(parts[0])
        oracle.require_ok(not parts[1].startswith("-"), "INVALID_RATIONAL", f"{label}: negative den")
        den = _parse_bounded_int(parts[1])
        oracle.require_ok(den > 1, "NONCANONICAL_RATIONAL", f"{label}: den must be > 1")
        q = Fraction(num, den)
        oracle.require_ok(q.denominator == den, "NONCANONICAL_RATIONAL", f"{label}: not reduced")
        return q
    return Fraction(_parse_bounded_int(s), 1)


def _parse_pos_dec2(val: Any, label: str) -> Fraction:
    s = oracle.require_exact_str(val, label)
    oracle.require_ok(len(s) <= oracle.MAX_INT_DIGITS + 3, "INT_TOO_LARGE", f"{label}: dec2 digits cap")
    oracle.require_ok(_POS_DEC2_RE.match(s) is not None, "PILLAR1_DEC", f"{label}: invalid dec2")
    q = Fraction(int(s.replace(".", "")), 100)
    oracle.require_ok(q > 0, "PILLAR1_DEC", f"{label}: non-positive dec2")
    return q


def _require_exact_dict(obj: Any, keys: frozenset[str], label: str) -> dict[str, Any]:
    oracle.require_ok(type(obj) is dict, "INVALID_SCHEMA_DICT", f"{label}: exact dict required")
    oracle.require_ok(frozenset(obj.keys()) == keys, "INVALID_SCHEMA_KEYS", f"{label}: keyset mismatch")
    return obj


# ---------------------------------------------------------------------------
# R10+ 15-Class Lean 4.36.0 Static & Live Kernel Gate
# ---------------------------------------------------------------------------

def _strip_lean4_comments(source: str) -> str:
    out: list[str] = []
    i = 0
    n = len(source)
    depth = 0
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if depth > 0:
            if ch == "/" and nxt == "-":
                depth += 1
                out.append("  ")
                i += 2
            elif ch == "-" and nxt == "/":
                depth -= 1
                out.append("  ")
                i += 2
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if ch == "/" and nxt == "-":
            depth = 1
            out.append("  ")
            i += 2
        elif ch == "-" and nxt == "-":
            out.append("  ")
            i += 2
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
        else:
            out.append(ch)
            i += 1
    oracle.require_ok(depth == 0, "LEAN4_UNTERMINATED_COMMENT", "unterminated Lean block comment")
    return "".join(out)


def static_gate_lean4_source(source: str) -> None:
    s = oracle.require_exact_str(source, "lean_source")
    oracle.require_ok("\r" not in s and "\x00" not in s, "LEAN4_BAD_CHARS", "CR/NUL in Lean source")
    cleaned = _strip_lean4_comments(s)
    m = _LEAN4_BANNED_RE.search(cleaned)
    oracle.require_ok(m is None, "LEAN4_TRUST_ESCAPE", f"banned Lean construct: {m.group(0)!r}" if m else "")
    for thm in oracle.LEAN_THEOREM_NAMES:
        short = thm.split(".")[-1]
        oracle.require_ok(f"theorem {short}" in cleaned, "LEAN4_MISSING_THEOREM", f"missing {short}")
        oracle.require_ok(f"#print axioms {thm}" in cleaned, "LEAN4_MISSING_PRINT_AXIOMS", f"missing #print axioms {thm}")


def resolve_lean_binary() -> str:
    env_bin = os.environ.get("ALETHEIA_LEAN_BIN")
    if env_bin is not None:
        oracle.require_exact_str(env_bin, "ALETHEIA_LEAN_BIN")
        p = Path(env_bin)
        oracle.require_ok(p.is_file() and os.access(str(p), os.X_OK), "LEAN_BINARY_UNAVAILABLE", "ALETHEIA_LEAN_BIN unusable")
        return str(p)
    found = shutil.which("lean")
    if found is not None and os.access(found, os.X_OK):
        return found
    home_env = os.environ.get("HOME")
    if home_env:
        home_p = Path(home_env)
        for rel in ((".local", "bin", "lean"), (".elan", "bin", "lean")):
            cand = home_p.joinpath(*rel)
            if cand.is_file() and os.access(str(cand), os.X_OK):
                return str(cand)
    raise oracle.S86Error("LEAN_BINARY_UNAVAILABLE", "lean executable not found")


def _scrubbed_lean_env() -> dict[str, str]:
    """Build allowlisted Lean subprocess environment stripping LEAN_*, ELAN_*, LD_*, and other injections."""
    return {k: v for k, v in os.environ.items() if k in SAFE_LEAN_ENV_KEYS}


def verify_lean4_file_live(lean_path: Path, *, enforce_sha256: bool = True) -> dict[str, Any]:
    oracle.require_bool(enforce_sha256, "enforce_sha256")
    raw = read_regular_bytes_capped(lean_path, "lean_source", max_bytes=1024 * 1024)
    l_sha = oracle.sha256_hex(raw)
    if enforce_sha256:
        oracle.require_ok(hmac.compare_digest(l_sha, oracle.EXPECTED_LEAN_SHA256), "LEAN4_SHA_MISMATCH", "Lean SHA mismatch")
    try:
        src = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise oracle.S86Error("INVALID_UTF8", "Lean source invalid UTF-8") from exc
    static_gate_lean4_source(src)
    lean_bin = resolve_lean_binary()
    clean_env = _scrubbed_lean_env()
    try:
        v_proc = subprocess.run([lean_bin, "--version"], env=clean_env, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise oracle.S86Error("LEAN_EXEC_ERROR", "lean --version failed") from exc
    oracle.require_ok(v_proc.returncode == 0 and "4.36.0" in v_proc.stdout, "LEAN_VERSION_MISMATCH", "Lean 4.36.0 required")
    # Zero-TOCTOU private temp execution from already-verified bytes
    with tempfile.TemporaryDirectory(prefix="s86_lean_") as tmpd:
        tmp_file = Path(tmpd) / "SovereignStackFourthOrder.lean"
        write_regular_bytes_safe(tmp_file, raw, "tmp_lean")
        try:
            proc = subprocess.run([lean_bin, str(tmp_file)], env=clean_env, capture_output=True, text=True, timeout=120, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise oracle.S86Error("LEAN_EXEC_ERROR", "lean elaboration failed") from exc
    oracle.require_ok(proc.returncode == 0, "LEAN_COMPILE_FAIL", f"lean rc={proc.returncode}")
    oracle.require_ok(proc.stderr.strip() == "", "LEAN_STDERR_NONEMPTY", "lean stderr must be empty")
    oracle.require_ok("warning:" not in proc.stdout.lower(), "LEAN_WARNING_FORBIDDEN", "lean warning forbidden")

    joined_lines: list[str] = []
    pending = ""
    for raw_line in proc.stdout.splitlines():
        s_line = raw_line.strip()
        if not s_line:
            continue
        if pending:
            pending = f"{pending} {s_line}"
            if "]" in s_line:
                joined_lines.append(pending)
                pending = ""
        elif "[" in s_line and "]" not in s_line:
            pending = s_line
        else:
            joined_lines.append(s_line)
    oracle.require_ok(pending == "", "LEAN_UNEXPECTED_STDOUT", "unterminated axiom list")

    seen: dict[str, list[str]] = {}
    for s_line in joined_lines:
        m_none = _LEAN4_AXIOM_NONE_RE.match(s_line)
        if m_none is not None:
            thm_name = m_none.group(1)
            oracle.require_ok(thm_name not in seen, "LEAN_DUPLICATE_THEOREM", thm_name)
            seen[thm_name] = []
            continue
        m_dep = _LEAN4_AXIOM_DEP_RE.match(s_line)
        oracle.require_ok(m_dep is not None, "LEAN_UNEXPECTED_STDOUT", s_line[:80])
        thm_name = m_dep.group(1)
        oracle.require_ok(thm_name not in seen, "LEAN_DUPLICATE_THEOREM", thm_name)
        axs = [a.strip() for a in m_dep.group(2).split(",") if a.strip()]
        for ax in axs:
            oracle.require_ok(ax in _ALLOWED_LEAN_AXIOMS, "LEAN_BANNED_AXIOM", f"{thm_name}: {ax}")
        seen[thm_name] = axs

    oracle.require_ok(frozenset(seen.keys()) == frozenset(oracle.LEAN_THEOREM_NAMES), "LEAN_THEOREM_SET_MISMATCH", "theorem set")
    zero_ax = sum(1 for v in seen.values() if len(v) == 0)
    return {
        "lean_valid": True,
        "lean_source_sha256": l_sha,
        "theorems_verified": len(seen),
        "zero_axiom_theorems": zero_ax,
        "axioms_by_theorem": seen,
    }


# ---------------------------------------------------------------------------
# Field-Complete Secondary Semantic Auditor (FR0 / SEC)
# ---------------------------------------------------------------------------

def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    p = _require_exact_dict(payload, _PAYLOAD_KEYS, "payload")
    oracle.require_ok(p["schema_version"] == oracle.SCHEMA_VERSION, "SCHEMA_MISMATCH", "payload schema")
    oracle.require_ok(p["track_id"] == oracle.TRACK_ID, "SCHEMA_MISMATCH", "payload track_id")
    oracle.require_ok(p["oracle_class"] == "exact_over_live_rtx3080_integers", "SCHEMA_MISMATCH", "oracle_class")
    oracle.require_ok(p["novelty_classification"] == "N1", "SCHEMA_MISMATCH", "novelty_classification")
    oracle.require_ok(oracle.require_bool(p["measured_live_rtx3080"], "measured_live_rtx3080") is True, "LIVE_FLAG", "live flag")

    pa = _require_exact_dict(p["pinned_artifacts"], _PINNED_KEYS, "pinned_artifacts")
    oracle.require_ok(pa["lean_source"] == "SovereignStackFourthOrder.lean", "PIN_MISMATCH", "lean_source")
    oracle.require_hex64(pa["lean_source_sha256"], "pa.lean_sha")
    oracle.require_ok(pa["lean_toolchain"] == oracle.EXPECTED_LEAN_TOOLCHAIN, "PIN_MISMATCH", "lean_toolchain")
    oracle.require_hex64(pa["lean_toolchain_sha256"], "pa.tc_sha")
    oracle.require_hex64(pa["lakefile_sha256"], "pa.lake_sha")
    n_thm = oracle.require_exact_int(pa["lean_theorem_count"], "pa.n_thm", lo=17, hi=17)
    oracle.require_exact_int(pa["lean_universal_theorem_count"], "pa.n_univ", lo=16, hi=16)
    oracle.require_exact_int(pa["lean_witness_theorem_count"], "pa.n_wit", lo=1, hi=1)
    oracle.require_ok(type(pa["lean_theorem_names"]) is list and pa["lean_theorem_names"] == list(oracle.LEAN_THEOREM_NAMES), "PIN_MISMATCH", "theorem names")
    oracle.require_ok(pa["empirical_results_file"] == "rtx3080_s86_empirical_results.json", "PIN_MISMATCH", "emp file")
    oracle.require_hex64(pa["empirical_results_sha256"], "pa.emp_sha")
    oracle.require_ok(pa["mlos_receipt_file"] == "mlos_zone_b_receipt.json", "PIN_MISMATCH", "mlos file")
    mlos_fsha = oracle.require_hex64(pa["mlos_receipt_file_sha256"], "pa.mlos_file_sha")
    oracle.require_ok(hmac.compare_digest(mlos_fsha, oracle.EXPECTED_MLOS_RECEIPT_SHA256), "PIN_MISMATCH", "mlos file sha")
    mlos_isha = oracle.require_hex64(pa["mlos_receipt_inner_sha256"], "pa.mlos_inner_sha")
    oracle.require_ok(hmac.compare_digest(mlos_isha, oracle.EXPECTED_MLOS_INNER_SHA256), "PIN_MISMATCH", "mlos inner sha")
    oracle.require_hex64(pa["qwen3b_3bpw_safetensors_sha256"], "pa.q30_sha")
    oracle.require_hex64(pa["qwen3b_45bpw_safetensors_sha256"], "pa.q45_sha")
    oracle.require_exact_int(pa["qwen3b_3bpw_syndrome_errors"], "pa.syn30", lo=0, hi=0)
    oracle.require_exact_int(pa["qwen3b_45bpw_syndrome_errors"], "pa.syn45", lo=0, hi=0)
    oracle.require_exact_int(pa["dequant_eval_parity_max_diff_piconats"], "pa.parity", lo=0, hi=0)
    ups = pa["upstream_cert_pins"]
    oracle.require_ok(type(ups) is list and len(ups) == 6, "PIN_MISMATCH", "upstream_cert_pins")
    expected_ups = {r["track"]: (r["file"], r["sha256"]) for r in oracle.UPSTREAM_CERT_PINS}
    seen_tracks: set[str] = set()
    for row in ups:
        rd = _require_exact_dict(row, _UPSTREAM_PIN_KEYS, "upstream_pin")
        trk = oracle.require_exact_str(rd["track"], "up.track")
        fpath = oracle.require_exact_str(rd["file"], "up.file")
        fsha = oracle.require_hex64(rd["sha256"], "up.sha256")
        oracle.require_ok(trk in expected_ups, "PIN_MISMATCH", f"unknown upstream track {trk}")
        exp_file, exp_sha = expected_ups[trk]
        oracle.require_ok(fpath == exp_file, "PIN_MISMATCH", f"upstream file {trk}")
        oracle.require_ok(hmac.compare_digest(fsha, exp_sha), "PIN_MISMATCH", f"upstream sha {trk}")
        seen_tracks.add(trk)
    oracle.require_ok(len(seen_tracks) == 6, "PIN_MISMATCH", "duplicate upstream tracks")

    # Pillar 1: T3 Blow-Up CCE-Det vs Materialized vs Live Triton Atomics
    p1 = _require_exact_dict(p["pillar1_t3_blowup_cce_det"], _P1_KEYS, "pillar1")
    oracle.require_exact_int(p1["vocab_size"], "p1.V", lo=151936, hi=151936)
    oracle.require_exact_int(p1["hidden_size"], "p1.H", lo=2048, hi=2048)
    m1024 = _parse_pos_dec2(p1["n1024_mat_fp32_mib_dec2"], "p1.n1024_mat_fp32_mib_dec2")
    z1024 = _parse_pos_dec2(p1["n1024_cce_det_frozen_mib_dec2"], "p1.n1024_cce_det_frozen_mib_dec2")
    m2048 = _parse_pos_dec2(p1["n2048_mat_fp32_mib_dec2"], "p1.n2048_mat_fp32_mib_dec2")
    z2048 = _parse_pos_dec2(p1["n2048_cce_det_frozen_mib_dec2"], "p1.n2048_cce_det_frozen_mib_dec2")
    c1024 = parse_canonical_rational_str(p1["n1024_compression_ratio_q"], "p1.c1024")
    c2048 = parse_canonical_rational_str(p1["n2048_compression_ratio_q"], "p1.c2048")
    oracle.require_ok(c1024 > 5 and c2048 > 8, "PILLAR1_RATIO", "compression ratio")
    oracle.require_ok(
        abs(m1024 / z1024 - c1024) < Fraction(1, 100) and abs(m2048 / z2048 - c2048) < Fraction(1, 100),
        "PILLAR1_RATIO",
        "dec2 ratio consistency",
    )
    oracle.require_ok(p1["n1024_compression_ratio_dec4"] == oracle.dec_from_q(c1024, 4), "PILLAR1_DEC", "c1024 dec4")
    oracle.require_ok(p1["n2048_compression_ratio_dec4"] == oracle.dec_from_q(c2048, 4), "PILLAR1_DEC", "c2048 dec4")
    for bkey in ("n4096_mat_fp32_oom", "n4096_mat_bf16_ce_oom", "n8192_mat_fp32_oom", "n8192_mat_bf16_ce_oom"):
        oracle.require_ok(oracle.require_bool(p1[bkey], f"p1.{bkey}") is True, "PILLAR1_OOM", bkey)
    for b_int_key in ("n4096_cce_det_frozen_bytes", "n4096_cce_det_train_bytes", "n8192_cce_det_frozen_bytes"):
        v = oracle.require_exact_int(p1[b_int_key], f"p1.{b_int_key}", lo=1, hi=oracle.VRAM_BUDGET_BYTES - 1)
        dec_k = b_int_key.replace("_bytes", "_mib_dec2")
        oracle.require_ok(p1[dec_k] == oracle.dec_from_q(Fraction(v, oracle.MIB_BYTES), 2), "PILLAR1_DEC", dec_k)
    oracle.require_exact_int(p1["acc_loss_abs_err_piconats"], "p1.loss_err", lo=0, hi=0)
    oracle.require_exact_int(p1["acc_lse_max_ulp_vs_fp32"], "p1.lse_ulp", lo=0, hi=8)
    oracle.require_exact_int(p1["acc_grad_h_rel_l2_err_ppb"], "p1.gh_ppb", lo=0, hi=1_000_000)
    oracle.require_exact_int(p1["cce_det_rep_runs"], "p1.rep_runs", lo=10, hi=100)
    oracle.require_exact_int(p1["cce_det_rep_n_tokens"], "p1.rep_n", lo=4096, hi=4096)
    oracle.require_exact_int(p1["cce_det_rep_unique_hashes"], "p1.rep_uniq", lo=1, hi=1)
    oracle.require_exact_int(p1["cce_det_rep_max_ulp"], "p1.rep_ulp", lo=0, hi=0)
    for hkey in ("cce_det_rep_loss_sha256", "cce_det_rep_grad_h_sha256", "cce_det_rep_grad_w_sha256"):
        oracle.require_hex64(p1[hkey], f"p1.{hkey}")
    oracle.require_exact_int(p1["atomic_cas_unique_sha256"], "p1.cas_uniq", lo=2, hi=12)
    oracle.require_exact_int(p1["atomic_cas_max_ulp"], "p1.cas_ulp", lo=1, hi=1000)
    oracle.require_exact_int(p1["atomic_add_unique_sha256"], "p1.add_uniq", lo=2, hi=12)
    oracle.require_exact_int(p1["atomic_add_max_ulp"], "p1.add_ulp", lo=1, hi=1000)
    oracle.require_exact_int(p1["perm_asc_vs_desc_max_ulp"], "p1.pdesc_u", lo=1, hi=1000)
    for r_k, pct_k in (
        ("atomic_cas_divergent_rows", "atomic_cas_divergent_pct_dec2"),
        ("atomic_add_divergent_rows", "atomic_add_divergent_pct_dec2"),
        ("perm_asc_vs_desc_div_rows", "perm_asc_vs_desc_pct_dec2"),
        ("perm_asc_vs_striped_div_rows", "perm_asc_vs_striped_pct_dec2"),
    ):
        rv = oracle.require_exact_int(p1[r_k], f"p1.{r_k}", lo=1, hi=1024)
        oracle.require_ok(p1[pct_k] == oracle.dec_from_q(Fraction(rv * 100, 1024), 2), "PILLAR1_DEC", pct_k)
    oracle.require_exact_int(p1["k8_triangles_flipped_by_t3"], "p1.k8_flip", lo=6, hi=6)

    # Pillar 2: Borromean 4-Way 8 GiB Stack
    p2 = _require_exact_dict(p["pillar2_borromean_4way_stack"], _P2_KEYS, "pillar2")
    oracle.require_exact_int(p2["vram_budget_mib"], "p2.bud_mib", lo=8192, hi=8192)
    bud_b = oracle.require_exact_int(p2["vram_budget_bytes"], "p2.bud_b", lo=oracle.VRAM_BUDGET_BYTES, hi=oracle.VRAM_BUDGET_BYTES)
    oracle.require_exact_int(p2["train_n_tokens"], "p2.n_tok", lo=4096, hi=4096)
    for oom_k in (
        "no_s78_full_finetune_oom",
        "no_s73_bf16_r64_oom",
        "no_s73_bf16_r128_oom",
        "no_s80_3bpw_mat_fp32_oom",
        "no_s80_45bpw_mat_fp32_oom",
    ):
        oracle.require_ok(oracle.require_bool(p2[oom_k], f"p2.{oom_k}") is True, "PILLAR2_OOM", oom_k)
    oracle.require_ok(oracle.require_bool(p2["no_s79_r64_oom"], "p2.no_s79_oom") is False, "PILLAR2_NO79", "no_s79")
    no79_b = oracle.require_exact_int(p2["no_s79_r64_peak_alloc_bytes"], "p2.no79_b", lo=1, hi=bud_b - 1)
    oracle.require_ok(p2["no_s79_r64_peak_alloc_mib_dec2"] == oracle.dec_from_q(Fraction(no79_b, oracle.MIB_BYTES), 2), "PILLAR2_DEC", "no79 mib")
    r16_b = oracle.require_exact_int(p2["full_r16_peak_alloc_bytes"], "p2.r16_b", lo=1, hi=bud_b - 1)
    r64_b = oracle.require_exact_int(p2["full_r64_peak_alloc_bytes"], "p2.r64_b", lo=r16_b + 1, hi=bud_b - 1)
    r128_b = oracle.require_exact_int(p2["full_r128_peak_alloc_bytes"], "p2.r128_b", lo=r64_b + 1, hi=bud_b - 1)
    r64_res = oracle.require_exact_int(p2["full_r64_peak_res_bytes"], "p2.r64_res", lo=r64_b, hi=bud_b - 1)
    oracle.require_ok(p2["full_r64_peak_res_mib_dec2"] == oracle.dec_from_q(Fraction(r64_res, oracle.MIB_BYTES), 2), "PILLAR2_DEC", "r64 res")
    for b_val, pk_k, hr_k in (
        (r16_b, "full_r16_peak_alloc_mib_dec2", "full_r16_headroom_mib_dec2"),
        (r64_b, "full_r64_peak_alloc_mib_dec2", "full_r64_headroom_mib_dec2"),
        (r128_b, "full_r128_peak_alloc_mib_dec2", "full_r128_headroom_mib_dec2"),
    ):
        oracle.require_ok(p2[pk_k] == oracle.dec_from_q(Fraction(b_val, oracle.MIB_BYTES), 2), "PILLAR2_DEC", pk_k)
        oracle.require_ok(p2[hr_k] == oracle.dec_from_q(Fraction(bud_b - b_val, oracle.MIB_BYTES), 2), "PILLAR2_DEC", hr_k)
    for rk, pk in ((16, "full_r16_trainable_params"), (64, "full_r64_trainable_params"), (128, "full_r128_trainable_params")):
        oracle.require_exact_int(p2[pk], f"p2.{pk}", lo=rk * 1870848, hi=rk * 1870848)
    losses = p2["full_r64_step_losses_nano"]
    oracle.require_ok(type(losses) is list and len(losses) == 5, "PILLAR2_LOSSES", "5 step losses")
    for idx in range(5):
        oracle.require_exact_int(losses[idx], f"p2.loss.{idx}", lo=1)
    oracle.require_ok(all(losses[i] > losses[i + 1] for i in range(4)), "PILLAR2_DESCENT", "loss must strictly decrease")
    oracle.require_ok(oracle.require_bool(p2["full_r64_loss_strictly_decreasing"], "p2.dec") is True, "PILLAR2_DESCENT", "dec flag")
    oracle.require_ok(oracle.require_bool(p2["full_r64_bit_identical_repeatability"], "p2.rep") is True, "PILLAR2_REP", "rep flag")
    oracle.require_hex64(p2["full_r64_final_trainable_sha256"], "p2.sha")
    no79_loss = oracle.require_exact_int(p2["no_s79_r64_step0_loss_nano"], "p2.no79_l", lo=1)
    oracle.require_ok(losses[0] < no79_loss, "PILLAR2_CSR_STEP0", "CSR must improve step-0 loss")
    ldrop_q = parse_canonical_rational_str(p2["full_r64_5step_loss_drop_pct_q"], "p2.ldrop_q")
    oracle.require_ok(ldrop_q == Fraction((losses[0] - losses[-1]) * 100, losses[0]), "PILLAR2_LDROP", "drop exact")
    oracle.require_ok(p2["full_r64_5step_loss_drop_pct_dec2"] == oracle.dec_from_q(ldrop_q, 2), "PILLAR2_DEC", "drop dec2")

    # Pillar 3: CSR 1/160 Crossover & Live KL Sweep
    p3 = _require_exact_dict(p["pillar3_csr_1_over_160_crossover"], _P3_KEYS, "pillar3")
    wtot = oracle.require_exact_int(p3["total_block_weights"], "p3.wtot", lo=1)
    nnz = oracle.require_exact_int(p3["csr0500_nnz"], "p3.nnz", lo=1)
    csr_b = oracle.require_exact_int(p3["csr0500_bytes"], "p3.bytes", lo=1)
    oracle.require_ok(p3["csr0500_mib_dec2"] == oracle.dec_from_q(Fraction(csr_b, oracle.MIB_BYTES), 2), "PILLAR3_DEC", "csr mib")
    bpw_ov = parse_canonical_rational_str(p3["csr0500_bpw_overhead_q"], "p3.bpw_q")
    oracle.require_ok(bpw_ov == Fraction(csr_b * 8, wtot), "PILLAR3_DEC", "bpw overhead q")
    oracle.require_ok(p3["csr0500_bpw_overhead_dec4"] == oracle.dec_from_q(bpw_ov, 4), "PILLAR3_DEC", "bpw overhead dec4")
    rho_q = parse_canonical_rational_str(p3["csr0500_rho_q"], "p3.rho_q")
    oracle.require_ok(rho_q == Fraction(nnz, wtot) and rho_q < Fraction(1, 160), "PILLAR3_CAP", "rho < 1/160")
    oracle.require_ok(oracle.require_bool(p3["csr0500_strictly_below_1_over_160"], "p3.cap") is True, "PILLAR3_CAP", "cap flag")
    s_out = oracle.require_exact_int(p3["csr0500_sens_out"], "p3.sout", lo=1)
    s_tot = oracle.require_exact_int(p3["csr0500_sens_total"], "p3.stot", lo=s_out + 1)
    sfrac_q = parse_canonical_rational_str(p3["csr0500_sens_frac_q"], "p3.sfrac")
    oracle.require_ok(sfrac_q == Fraction(s_out, s_tot), "PILLAR3_DEC", "sens frac q")
    oracle.require_ok(p3["csr0500_sens_frac_pct_dec2"] == oracle.dec_from_q(sfrac_q * 100, 2), "PILLAR3_DEC", "sens frac pct")
    oracle.require_ok(
        p3["csr0500_sout_over_sbulk_pct_dec2"] == oracle.dec_from_q(Fraction(s_out * 100, s_tot - s_out), 2),
        "PILLAR3_DEC",
        "sout/sbulk pct",
    )
    ratio_q = parse_canonical_rational_str(p3["s79_m54_crossover_ratio_q"], "p3.ratio")
    oracle.require_ok(ratio_q == Fraction(5 * (s_tot - s_out), 4 * s_tot) and ratio_q < 1, "PILLAR3_CROSS", "S79 crossover")
    oracle.require_ok(p3["s79_m54_crossover_ratio_dec4"] == oracle.dec_from_q(ratio_q, 4), "PILLAR3_DEC", "ratio dec4")
    oracle.require_ok(oracle.require_bool(p3["s79_crossover_wins"], "p3.wins") is True, "PILLAR3_CROSS", "wins flag")
    q45_wt = oracle.require_exact_int(p3["q45_wt_kl_nano"], "p3.q45_wt", lo=1)
    q30_wt = oracle.require_exact_int(p3["q30_wt_kl_nano"], "p3.q30_wt", lo=1)
    c125_wt = oracle.require_exact_int(p3["csr0125_wt_kl_nano"], "p3.c125_wt", lo=1)
    c25_wt = oracle.require_exact_int(p3["csr0250_wt_kl_nano"], "p3.c25_wt", lo=1)
    c50_wt = oracle.require_exact_int(p3["csr0500_wt_kl_nano"], "p3.c50_wt", lo=1)
    raw_wt = oracle.require_exact_int(p3["raw0500_wt_kl_nano"], "p3.raw_wt", lo=1)
    oracle.require_ok(q45_wt < c50_wt < c25_wt < c125_wt < q30_wt, "PILLAR3_WT_ORDER", "monotonic WikiKL ladder")
    oracle.require_ok(c50_wt < raw_wt < q30_wt, "PILLAR3_WT_ORDER", "Hessian CSR < Raw CSR < 3.0 bpw WikiKL")
    q45_py = oracle.require_exact_int(p3["q45_py_kl_nano"], "p3.q45_py", lo=1)
    q30_py = oracle.require_exact_int(p3["q30_py_kl_nano"], "p3.q30_py", lo=1)
    c125_py = oracle.require_exact_int(p3["csr0125_py_kl_nano"], "p3.c125_py", lo=1)
    c25_py = oracle.require_exact_int(p3["csr0250_py_kl_nano"], "p3.c25_py", lo=1)
    c50_py = oracle.require_exact_int(p3["csr0500_py_kl_nano"], "p3.c50_py", lo=1)
    raw_py = oracle.require_exact_int(p3["raw0500_py_kl_nano"], "p3.raw_py", lo=1)
    oracle.require_ok(q45_py < c50_py < c25_py < c125_py < q30_py, "PILLAR3_PY_ORDER", "monotonic PyKL ladder")
    oracle.require_ok(c50_py < raw_py < q30_py, "PILLAR3_PY_ORDER", "Hessian CSR < Raw CSR < 3.0 bpw PyKL")
    for arm_v, base_v, d_key in (
        (c125_wt, q30_wt, "csr0125_wt_drop_pct_dec2"),
        (c25_wt, q30_wt, "csr0250_wt_drop_pct_dec2"),
        (c50_wt, q30_wt, "csr0500_wt_drop_pct_dec2"),
        (raw_wt, q30_wt, "raw0500_wt_drop_pct_dec2"),
        (c125_py, q30_py, "csr0125_py_drop_pct_dec2"),
        (c25_py, q30_py, "csr0250_py_drop_pct_dec2"),
        (c50_py, q30_py, "csr0500_py_drop_pct_dec2"),
        (raw_py, q30_py, "raw0500_py_drop_pct_dec2"),
    ):
        oracle.require_ok(p3[d_key] == oracle.dec_from_q(Fraction((base_v - arm_v) * 100, base_v), 2), "PILLAR3_DEC", d_key)
    h_wt = parse_canonical_rational_str(p3["hessian_vs_raw_wt_leverage_q"], "p3.h_wt")
    h_py = parse_canonical_rational_str(p3["hessian_vs_raw_py_leverage_q"], "p3.h_py")
    oracle.require_ok(
        h_wt == Fraction(q30_wt - c50_wt, q30_wt - raw_wt) and h_py == Fraction(q30_py - c50_py, q30_py - raw_py),
        "PILLAR3_LEV",
        "Hessian leverage exact",
    )
    oracle.require_ok(p3["hessian_vs_raw_wt_leverage_dec4"] == oracle.dec_from_q(h_wt, 4), "PILLAR3_DEC", "h_wt dec4")
    oracle.require_ok(p3["hessian_vs_raw_py_leverage_dec4"] == oracle.dec_from_q(h_py, 4), "PILLAR3_DEC", "h_py dec4")

    # Pillar 4: Joint MDL Horizon Lift & S77 Mellin-GLU Carry Preservation
    p4 = _require_exact_dict(p["pillar4_joint_mdl_and_mellin_glu"], _P4_KEYS, "pillar4")
    oracle.require_exact_int(p4["qwen3b_n_base"], "p4.nb", lo=wtot, hi=wtot)
    p1_all7 = oracle.require_exact_int(p4["qwen3b_p1_all7"], "p4.p1", lo=1870848, hi=1870848)
    bits_freed = oracle.require_exact_int(p4["bits_freed_16_to_3bpw"], "p4.bf", lo=13 * wtot, hi=13 * wtot)
    oracle.require_exact_int(p4["delta_rank_b16"], "p4.dr16", lo=bits_freed // (16 * p1_all7), hi=bits_freed // (16 * p1_all7))
    oracle.require_exact_int(p4["delta_rank_adam64"], "p4.dr64", lo=bits_freed // (64 * p1_all7), hi=bits_freed // (64 * p1_all7))
    wt_lift = parse_canonical_rational_str(p4["wt_horizon_lift_q"], "p4.wt_lift")
    py_lift = parse_canonical_rational_str(p4["py_horizon_lift_q"], "p4.py_lift")
    oracle.require_ok(wt_lift == Fraction(q30_wt, c50_wt), "PILLAR4_LIFT", "wt lift")
    oracle.require_ok(py_lift == Fraction(q30_py, c50_py), "PILLAR4_LIFT", "py lift")
    oracle.require_ok(p4["wt_horizon_lift_dec4"] == oracle.dec_from_q(wt_lift, 4), "PILLAR4_DEC", "wt lift dec4")
    oracle.require_ok(p4["py_horizon_lift_dec4"] == oracle.dec_from_q(py_lift, 4), "PILLAR4_DEC", "py lift dec4")
    m_w = oracle.require_exact_int(p4["mellin_slice_weights"], "p4.mw", lo=1)
    m_r = oracle.require_exact_int(p4["mellin_rungs"], "p4.mr", lo=1)
    m_b = oracle.require_exact_int(p4["mellin_csr_budget_0p50pct"], "p4.mb", lo=m_r)
    oracle.require_ok(parse_canonical_rational_str(p4["mellin_density_q"], "p4.md") == Fraction(m_r, m_w), "PILLAR4_MELLIN", "density")
    m_sh = parse_canonical_rational_str(p4["mellin_rung_share_of_csr_budget_q"], "p4.msh")
    oracle.require_ok(m_sh == Fraction(m_r, m_b), "PILLAR4_MELLIN", "rung share")
    oracle.require_ok(p4["mellin_rung_share_of_csr_budget_pct_dec2"] == oracle.dec_from_q(m_sh * 100, 2), "PILLAR4_DEC", "rung share pct")
    oracle.require_exact_int(p4["mellin_45bpw_blind_passes"], "p4.m45b", lo=0, hi=0)
    oracle.require_exact_int(p4["mellin_45bpw_blind_err_micro"], "p4.e45b", lo=500000)
    oracle.require_exact_int(p4["mellin_30bpw_blind_passes"], "p4.m30b", lo=0, hi=0)
    oracle.require_exact_int(p4["mellin_30bpw_blind_err_micro"], "p4.e30b", lo=500000)
    oracle.require_exact_int(p4["mellin_30bpw_mag_csr_passes"], "p4.m30m", lo=4, hi=4)
    oracle.require_exact_int(p4["mellin_30bpw_sens_csr_passes"], "p4.m30s", lo=5, hi=5)
    oracle.require_exact_int(p4["mellin_30bpw_sens_csr_err_micro"], "p4.esens", lo=1, hi=499999)
    oracle.require_exact_int(p4["mellin_30bpw_mag_csr_err_micro"], "p4.emag", lo=500000)
    oracle.require_exact_int(p4["mellin_syndrome_errors"], "p4.msyn", lo=0, hi=0)
    oracle.require_exact_int(p4["mellin_oob_groups"], "p4.moob", lo=0, hi=0)

    # Field-complete exact leaf pinning closing every remaining SEC/FR0 degree of freedom
    for sec_k, fld_k, exp_val in _PINNED_SEC_EXACT_CHECKS:
        actual = p[sec_k][fld_k]
        if type(exp_val) is str:
            oracle.require_ok(hmac.compare_digest(actual, exp_val), "PIN_MISMATCH", f"{sec_k}.{fld_k}")
        elif type(exp_val) is tuple:
            oracle.require_ok(tuple(actual) == exp_val, "ANCHOR_MISMATCH", f"{sec_k}.{fld_k}")
        else:
            oracle.require_ok(actual == exp_val, "ANCHOR_MISMATCH", f"{sec_k}.{fld_k}")

    return {
        "secondary_audit_passed": True,
        "lean_theorem_count": n_thm,
        "csr_wins": True,
        "mellin_rescued": True,
    }


def _crosscheck_empirical_anchors(emp_obj: dict[str, Any]) -> None:
    """Cross-verify parsed rtx3080_s86_empirical_results.json content against oracle.PINNED_LIVE_ANCHORS."""
    for path_keys, anchor_key in _EMPIRICAL_ANCHOR_PATHS:
        cur: Any = emp_obj
        for k in path_keys:
            oracle.require_ok(type(cur) is dict and k in cur, "EMPIRICAL_SCHEMA_MISMATCH", f"missing {k}")
            cur = cur[k]
        expected = oracle.PINNED_LIVE_ANCHORS[anchor_key]
        if type(expected) is tuple:
            oracle.require_ok(type(cur) is list and tuple(cur) == expected, "EMPIRICAL_ANCHOR_MISMATCH", anchor_key)
        else:
            oracle.require_ok(cur == expected, "EMPIRICAL_ANCHOR_MISMATCH", anchor_key)


def _load_static_track_artifacts(track_dir: Path) -> tuple[str, str, str, str, str]:
    lean_raw = read_regular_bytes_capped(track_dir / "SovereignStackFourthOrder.lean", "lean_source", max_bytes=1024 * 1024)
    try:
        lean_src = lean_raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise oracle.S86Error("INVALID_UTF8", "Lean source invalid UTF-8") from exc
    static_gate_lean4_source(lean_src)
    tc_raw = read_regular_bytes_capped(track_dir / "lean-toolchain", "lean-toolchain", max_bytes=256)
    try:
        tc_text = tc_raw.decode("utf-8", "strict").strip()
    except UnicodeDecodeError as exc:
        raise oracle.S86Error("INVALID_UTF8", "lean-toolchain invalid UTF-8") from exc
    oracle.require_ok(tc_text == oracle.EXPECTED_LEAN_TOOLCHAIN, "TOOLCHAIN_MISMATCH", "unexpected lean-toolchain")
    lake_raw = read_regular_bytes_capped(track_dir / "lakefile.toml", "lakefile.toml", max_bytes=4096)
    emp_raw = read_regular_bytes_capped(track_dir / "rtx3080_s86_empirical_results.json", "empirical_results")
    emp_obj = parse_strict_json_bytes(emp_raw, "empirical_results", require_canonical=False)
    _crosscheck_empirical_anchors(emp_obj)
    mlos_raw = read_regular_bytes_capped(track_dir / "mlos_zone_b_receipt.json", "mlos_receipt")
    return (
        oracle.sha256_hex(lean_raw),
        oracle.sha256_hex(tc_raw),
        oracle.sha256_hex(lake_raw),
        oracle.sha256_hex(emp_raw),
        oracle.sha256_hex(mlos_raw),
    )


def verify_certificate_dict(
    cert: Any,
    *,
    full_replay: bool = True,
    track_dir: Path | None = None,
) -> dict[str, Any]:
    oracle.require_bool(full_replay, "full_replay")
    oracle.require_ok(type(cert) is dict, "INVALID_CERT_TYPE", "certificate must be exact dict")
    oracle.validate_strict_json_tree(cert, "certificate")
    _require_exact_dict(cert, _CERT_KEYS, "certificate")
    oracle.require_ok(cert["schema_version"] == oracle.SCHEMA_VERSION, "SCHEMA_MISMATCH", "cert schema_version")
    oracle.require_ok(cert["track_id"] == oracle.TRACK_ID, "SCHEMA_MISMATCH", "cert track_id")

    p_sha = oracle.require_hex64(cert["payload_sha256"], "payload_sha256")
    c_sha = oracle.require_hex64(cert["certificate_sha256"], "certificate_sha256")
    payload = cert["payload"]
    sec_res = secondary_audit_payload(payload)

    recomputed_p = oracle.sha256_hex(oracle.canonical_json_bytes(payload))
    oracle.require_ok(hmac.compare_digest(p_sha, recomputed_p), "PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")
    env = {
        "schema_version": cert["schema_version"],
        "track_id": cert["track_id"],
        "payload_sha256": p_sha,
        "payload": payload,
    }
    recomputed_c = oracle.sha256_hex(oracle.canonical_json_bytes(env))
    oracle.require_ok(hmac.compare_digest(c_sha, recomputed_c), "CERT_SHA_MISMATCH", "certificate_sha256 mismatch")

    replayed = False
    if full_replay:
        root = Path(_THIS_DIR) if track_dir is None else _require_concrete_path(track_dir, "track_dir")
        l_sha, tc_sha, lk_sha, emp_sha, mlos_sha = _load_static_track_artifacts(root)
        expected = oracle.build_certificate(
            lean_source_sha256=l_sha,
            toolchain_sha256=tc_sha,
            lakefile_sha256=lk_sha,
            empirical_sha256=emp_sha,
            mlos_receipt_sha256=mlos_sha,
        )
        oracle.require_ok(
            hmac.compare_digest(oracle.canonical_json_bytes(cert), oracle.canonical_json_bytes(expected)),
            "FULL_REPLAY_MISMATCH",
            "certificate does not match exact pure-Z/Q replay",
        )
        replayed = True

    return {
        "valid": True,
        "full_replay": replayed,
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "secondary_audit": sec_res,
    }


def write_certificate_file(path: Path, *, track_dir: Path | None = None) -> dict[str, Any]:
    root = Path(_THIS_DIR) if track_dir is None else _require_concrete_path(track_dir, "track_dir")
    l_sha, tc_sha, lk_sha, emp_sha, mlos_sha = _load_static_track_artifacts(root)
    cert = oracle.build_certificate(
        lean_source_sha256=l_sha,
        toolchain_sha256=tc_sha,
        lakefile_sha256=lk_sha,
        empirical_sha256=emp_sha,
        mlos_receipt_sha256=mlos_sha,
    )
    raw = oracle.canonical_json_bytes(cert)
    write_regular_bytes_safe(path, raw, "certificate")
    return {
        "written": True,
        "bytes": len(raw),
        "file_sha256": oracle.sha256_hex(raw),
        "certificate_sha256": cert["certificate_sha256"],
    }


def check_certificate_file(path: Path, *, full_replay: bool = True, track_dir: Path | None = None) -> dict[str, Any]:
    raw = read_regular_bytes_capped(path, "certificate")
    cert = parse_strict_json_bytes(raw, "certificate", require_canonical=True)
    res = verify_certificate_dict(cert, full_replay=full_replay, track_dir=track_dir)
    res["file_sha256"] = oracle.sha256_hex(raw)
    return res


def _parse_cli_args(argv: Any) -> dict[str, Any]:
    oracle.require_ok(type(argv) is list, "INVALID_ARGV", "argv must be exact list")
    mode: str | None = None
    target_path: str | None = None
    want_json = False
    i = 0
    n = len(argv)
    while i < n:
        arg = oracle.require_exact_str(argv[i], "argv")
        oracle.require_ok("\x00" not in arg, "NUL_BYTE_FORBIDDEN", "NUL byte in argv")
        if arg == "--json":
            oracle.require_ok(not want_json, "DUPLICATE_FLAG", "--json repeated")
            want_json = True
            i += 1
        elif arg in ("--standalone", "--verify-lean"):
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "conflicting mode flags")
            mode = arg[2:]
            i += 1
            if arg == "--verify-lean" and i < n and not oracle.require_exact_str(argv[i], "lean_arg").startswith("-"):
                val = oracle.require_exact_str(argv[i], "lean_arg")
                oracle.require_ok("\x00" not in val and len(val) > 0, "INVALID_PATH_ARG", "invalid lean path")
                target_path = val
                i += 1
        elif arg in ("--check", "--write"):
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "conflicting mode flags")
            oracle.require_ok(i + 1 < n, "MISSING_PATH_ARG", f"{arg} requires path")
            val = oracle.require_exact_str(argv[i + 1], f"{arg} path")
            oracle.require_ok("\x00" not in val and len(val) > 0 and not val.startswith("-"), "INVALID_PATH_ARG", f"invalid path {val!r}")
            mode = arg[2:]
            target_path = val
            i += 2
        elif arg.startswith("--check=") or arg.startswith("--write="):
            oracle.require_ok(mode is None, "CONFLICTING_MODE", "conflicting mode flags")
            flag_name, val = arg.split("=", 1)
            oracle.require_ok(len(val) > 0 and not val.startswith("-"), "INVALID_PATH_ARG", f"invalid path {val!r}")
            mode = flag_name[2:]
            target_path = val
            i += 1
        else:
            raise oracle.S86Error("UNKNOWN_FLAG", f"unsupported flag: {arg!r}")
    return {"mode": mode if mode is not None else "default", "target": target_path, "json": want_json}


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv: Any = list(sys.argv[1:]) if argv is None else argv
    try:
        opts = _parse_cli_args(raw_argv)
        mode = opts["mode"]
        if mode == "standalone":
            root = Path(_THIS_DIR)
            l_sha, tc_sha, lk_sha, emp_sha, mlos_sha = _load_static_track_artifacts(root)
            cert = oracle.build_certificate(
                lean_source_sha256=l_sha,
                toolchain_sha256=tc_sha,
                lakefile_sha256=lk_sha,
                empirical_sha256=emp_sha,
                mlos_receipt_sha256=mlos_sha,
            )
            sys.stdout.write(oracle.canonical_json_bytes(cert).decode("ascii"))
            return 0
        if mode == "write":
            res = write_certificate_file(Path(opts["target"]))
            if opts["json"]:
                sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii"))
            else:
                sys.stdout.write(f"WROTE {res['file_sha256']}\n")
            return 0
        if mode == "verify-lean":
            lpath = Path(_THIS_DIR) / "SovereignStackFourthOrder.lean" if opts["target"] is None else Path(opts["target"])
            res = verify_lean4_file_live(lpath, enforce_sha256=True)
            if opts["json"]:
                sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii"))
            else:
                sys.stdout.write(f"LEAN_OK {res['theorems_verified']} {res['lean_source_sha256']}\n")
            return 0
        if mode == "check":
            res = check_certificate_file(Path(opts["target"]), full_replay=True)
            if opts["json"]:
                sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii"))
            else:
                sys.stdout.write(f"OK {res['certificate_sha256']}\n")
            return 0
        res = check_certificate_file(Path(_THIS_DIR) / "s86_sovereign_stack_certificate.json", full_replay=True)
        if opts["json"]:
            sys.stdout.write(oracle.canonical_json_bytes(res).decode("ascii"))
        else:
            sys.stdout.write(f"OK {res['certificate_sha256']}\n")
        return 0
    except oracle.S86Error as exc:
        err_obj = {"error": True, "code": exc.code, "detail": exc.detail}
        sys.stderr.write(json.dumps(err_obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
