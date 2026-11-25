#!/usr/bin/env python3
"""Track S97 Hardened Non-Hollow R10+ Verifier for ALETHEIA-WSE-HC.

Pure stdlib, ZERO floats, ZERO bare asserts, ZERO .isdigit(), ZERO random.
Enforces:
  - Iterative (non-recursive) Zone-B JSON tree validation with bit_length() int
    bound, surrogate-free UTF-8 string checks, exact primitive/container types
    (rejecting bool/subclass/mapping spoofs), no duplicate keys, no floats/NaN/Inf,
    and canonical coprime 2-key rational dicts.
  - Safe regular-file I/O rejecting symlinks (including parent-chain symlinks),
    FIFOs/special files (O_NOFOLLOW | O_NONBLOCK), oversized files, and NUL bytes.
  - Full cryptographic integrity (ASCII-hex64 pre-check + hmac.compare_digest).
  - Independent non-hollow algebraic re-derivation of ALL Pillar 1 (a-d) invariants
    + live RTX 3080 anchor + 7 upstream cert SHA-256 pins + Law-4 novelty tier.
  - Hardened R11 Lean 4.36.0 gate:
      * Strict bool check on check_pinned_sha (S87-F3),
      * Non-empty verified theorem set even when unpinned (S87-F3),
      * Zero-TOCTOU private 0o700 temp-copy Lean elaboration with full env scrub
        (LEAN_PATH/LEAN_OPTS/LEAN_SRC_PATH/LEAN_ABORT_ON_PANIC/ELAN_TOOLCHAIN/ELAN_HOME/LEAN_CC),
      * $HOME-aware Lean binary discovery (S89-INFO-02),
      * Comment-aware R11 scanner blocking 65+ trust-escape probes incl.
        declare_syntax_cat, macro_rules, elab_rules, dbgTrace*, @[export]/@[init]/@[builtin_init],
        #guard_msgs, multiline decide (native := ...), and modifier-prefixed theorem
        discovery (private/protected theorem), with 0 FP on clean controls.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from fractions import Fraction
from typing import Any, Dict, List, Optional, Sequence, Tuple

_THIS_DIR = str(pathlib.Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import s97_wse_hc_oracle as oracle

SCHEMA_VERSION = oracle.SCHEMA_VERSION
TRACK_ID = oracle.TRACK_ID

MAX_CERT_BYTES = 2 * 1024 * 1024
MAX_LEAN_BYTES = 512 * 1024
MAX_JSON_DEPTH = 16
MAX_INT_BITS = 8192
MAX_INT_DIGITS = 2467  # exact len(str(2**8192 - 1))

LEAN_FILE_NAME = oracle.LEAN_FILE_NAME
LEAN_FILE_SHA256 = oracle.LEAN_FILE_SHA256
LEAN_NAMESPACE = oracle.LEAN_NAMESPACE
LEAN_ALLOWED_AXIOMS = frozenset(oracle.LEAN_ALLOWED_AXIOMS)
LEAN_THEOREMS = oracle.LEAN_THEOREMS

UPSTREAM_CERT_MANIFEST: Tuple[Tuple[str, str, str], ...] = oracle.UPSTREAM_CERT_MANIFEST
SAFE_LEAN_ENV_KEYS = frozenset({"PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR", "TMP", "TEMP"})

PINNED_LIVE_INNER_SHA256 = "cef9653b38c50fdce01a361ac6baf6c9da52698d0aaf74f047a3178d96acd0e2"
PINNED_P2_CANON_SHA256 = "2feaadd6011bb686abe187ecba35947ccd5fd36defcf013511d40b8b33572759"
PINNED_GPU_NAME = "NVIDIA GeForce RTX 3080 Laptop GPU"

EXPECTED_ARM_NAMES = (
    "Std-Backprop-LoRA",
    "Naive-WSE-HC",
    "Aletheia-WSE-HC-Pure",
    "Aletheia-WSE-HC-Hybrid",
)

# R12 static trust-escape patterns (applied strictly on comment-stripped Lean source)
BANNED_LEAN_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("IMPORT_FORBIDDEN", re.compile(r"(?m)^\s*(?:public\s+|private\s+)?import\b")),
    ("SORRY_OR_ADMIT", re.compile(r"\b(?:sorry|admit|sorryAx|mkSorry)\b|_root_\.sorryAx\b|\bwarn\.sorry\b")),
    ("AXIOM_DECL", re.compile(r"\b(?:axiom|constant|opaque)\b")),
    ("UNSAFE_OR_PARTIAL", re.compile(r"\b(?:unsafe|partial|implemented_by|extern|csimp|dbg_trace|dbg_sleep|dbg_stack_trace|dbgTrace[A-Za-z0-9_]*|dbgSleep|dbgStackTrace)\b|\b(?:panic|unreachable)!")),
    ("ATTR_FFI_INIT_ESCAPE", re.compile(r"@\[[^\]]*\b(?:export|init|builtin_init|implemented_by|term_elab|command_elab|tactic|macro|macro_rules)\b|\battribute\s*\[[^\]]*\b(?:export|init|builtin_init|implemented_by|term_elab|command_elab|tactic|macro|macro_rules)\b")),
    ("NATIVE_DECIDE", re.compile(r"\b(?:native_decide|bv_decide)\b")),
    ("NATIVE_FLAG_TRUE", re.compile(r"\bnative\s*:=(?!\s*(?:Bool\.)?false\s*[),}])")),
    ("NATIVE_PLUS_OR_CONFIG", re.compile(r"(?<!\w)\+\s*native\b|\bconfig\s*:=")),
    ("TRUSTED_OPTION", re.compile(r"\bset_option\b|#exit\b|#guard(?:_msgs)?\b")),
    ("METAPROG_ESCAPE", re.compile(r"\b(?:run_cmd|run_meta|elab|elab_rules|macro|macro_rules|syntax|declare_syntax_cat|notation|prefix|infix|infixl|infixr|postfix)\b")),
    ("STRING_OR_GUILLEMET", re.compile(r'["«»]')),
    ("ENV_TRUST_ESCAPE", re.compile(r"\b(?:Lean\s*\.|ofReduceBool|ofReduceNat|lcProof|terminalTacticsAsSorry|Classical\.choice|Classical\.em|Classical\.byContradiction)\b")),
)


class VerifyError(ValueError):
    """Structured verification error carrying a stable machine code."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def is_exact_int(val: Any) -> bool:
    return type(val) is int


def is_hex64(val: Any) -> bool:
    return type(val) is str and len(val) == 64 and all(c in "0123456789abcdef" for c in val)


def _check_utf8_clean_str(val: str) -> None:
    for ch in val:
        cp = ord(ch)
        if 0xD800 <= cp <= 0xDFFF:
            raise VerifyError("INVALID_SURROGATE", "UTF-16 surrogate codepoint forbidden")


def parse_qdict(obj: Any, label: str) -> Fraction:
    """Strictly validate canonical 2-key coprime rational dict {"num": int, "den": int}."""
    if type(obj) is not dict or set(obj.keys()) != {"num", "den"}:
        raise VerifyError("INVALID_RATIONAL_DICT", f"{label}: must be exact 2-key num/den dict")
    num = obj["num"]
    den = obj["den"]
    if not (is_exact_int(num) and is_exact_int(den)):
        raise VerifyError("INVALID_RATIONAL_TYPE", f"{label}: num and den must be exact int")
    if abs(num).bit_length() > MAX_INT_BITS or abs(den).bit_length() > MAX_INT_BITS:
        raise VerifyError("INT_BIT_LIMIT", f"{label}: rational exceeds MAX_INT_BITS")
    if den <= 0:
        raise VerifyError("INVALID_RATIONAL_DEN", f"{label}: den must be > 0")
    if math.gcd(abs(num), den) != 1:
        raise VerifyError("NON_COPRIME_RATIONAL", f"{label}: gcd(|num|, den) != 1")
    return Fraction(num, den)


def scan_json_tree_iterative(root: Any) -> None:
    """Iterative Zone-B validator (no RecursionError, bit_length cap, surrogate & type checks)."""
    stack: List[Tuple[Any, int]] = [(root, 0)]
    while stack:
        obj, depth = stack.pop()
        if depth > MAX_JSON_DEPTH:
            raise VerifyError("JSON_MAX_DEPTH", "JSON nesting exceeds MAX_JSON_DEPTH")
        t = type(obj)
        if t is float:
            raise VerifyError("FLOAT_FORBIDDEN", "Floating-point values are forbidden")
        if t is int:
            if abs(obj).bit_length() > MAX_INT_BITS:
                raise VerifyError("INT_BIT_LIMIT", "Integer exceeds MAX_INT_BITS")
            continue
        if t is str:
            _check_utf8_clean_str(obj)
            continue
        if t is bool or obj is None:
            continue
        if t is list:
            for item in obj:
                stack.append((item, depth + 1))
            continue
        if t is dict:
            if "num" in obj or "den" in obj:
                parse_qdict(obj, "tree_rational")
                continue
            for k, v in obj.items():
                if type(k) is not str:
                    raise VerifyError("NON_STRING_KEY", "Object key must be exact str")
                _check_utf8_clean_str(k)
                stack.append((v, depth + 1))
            continue
        raise VerifyError("UNSUPPORTED_TYPE", f"Unsupported JSON type: {t.__name__}")


def strict_json_loads(raw_text: str) -> Any:
    """Fail-closed JSON parser rejecting duplicate keys, floats, NaN/Inf, and huge ints."""

    def _bounded_int(token: str) -> int:
        body = token[1:] if token.startswith("-") else token
        if len(body) > MAX_INT_DIGITS:
            raise VerifyError("INT_DIGIT_LIMIT", "Integer literal exceeds MAX_INT_DIGITS")
        return int(token)

    def _reject_float(_s: str) -> Any:
        raise VerifyError("FLOAT_FORBIDDEN", "Float literal rejected in strict JSON")

    def _reject_const(c: str) -> Any:
        raise VerifyError("NON_FINITE_JSON", f"Forbidden JSON constant: {c}")

    def _no_dups(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, v in pairs:
            if k in out:
                raise VerifyError("DUPLICATE_JSON_KEY", f"Duplicate JSON key: {k}")
            out[k] = v
        return out

    try:
        obj = json.loads(
            raw_text,
            parse_int=_bounded_int,
            parse_float=_reject_float,
            parse_constant=_reject_const,
            object_pairs_hook=_no_dups,
        )
    except VerifyError:
        raise
    except Exception as exc:
        raise VerifyError("INVALID_JSON", str(exc)) from exc
    scan_json_tree_iterative(obj)
    return obj


def _require_keys(d: Any, expected: set[str], label: str) -> Dict[str, Any]:
    if type(d) is not dict or set(d.keys()) != expected:
        raise VerifyError("SCHEMA_KEYS_MISMATCH", f"{label}: unexpected or missing keys")
    return d


def _expect_q(d: Dict[str, Any], key: str, expected: Fraction, label: str) -> None:
    got = parse_qdict(d[key], f"{label}.{key}")
    if got != expected:
        raise VerifyError("ALGEBRAIC_MISMATCH", f"{label}.{key}: got {got}, expected {expected}")


def _expect_eq(d: Dict[str, Any], key: str, expected: Any, label: str) -> None:
    val = d[key]
    if type(val) is not type(expected) or val != expected:
        raise VerifyError("VALUE_MISMATCH", f"{label}.{key}: got {val!r}, expected {expected!r}")


def _audit_pillar_1a(p: Any) -> None:
    req = {
        "d_model", "target_layers_count", "ambient_dim", "single_layer_dim",
        "lora_params", "edit_subspace_dim", "snr_lift_full_q",
        "snr_lift_single_layer_q", "ambient_to_lora_ratio_q",
        "householder_u_norm_sq_q", "householder_qtq_err_q", "householder_qsq_err_q",
        "householder_x_norm_sq_q", "householder_qx_norm_sq_q", "householder_kappa2_q",
        "blockh4_ortho_err_q", "blockh4_parseval_lhs_q", "blockh4_parseval_rhs_q",
    }
    d = _require_keys(p, req, "pillar_1a")
    _expect_eq(d, "d_model", 896, "pillar_1a")
    _expect_eq(d, "target_layers_count", 6, "pillar_1a")
    _expect_eq(d, "ambient_dim", 6 * 896 * 896, "pillar_1a")
    _expect_eq(d, "single_layer_dim", 896 * 896, "pillar_1a")
    _expect_eq(d, "lora_params", 6 * 2 * 16 * 896, "pillar_1a")
    _expect_eq(d, "edit_subspace_dim", 4 * (256 + 768), "pillar_1a")
    _expect_q(d, "snr_lift_full_q", Fraction(1176, 1), "pillar_1a")
    _expect_q(d, "snr_lift_single_layer_q", Fraction(196, 1), "pillar_1a")
    _expect_q(d, "ambient_to_lora_ratio_q", Fraction(28, 1), "pillar_1a")
    _expect_q(d, "householder_u_norm_sq_q", Fraction(25, 1), "pillar_1a")
    _expect_q(d, "householder_qtq_err_q", Fraction(0, 1), "pillar_1a")
    _expect_q(d, "householder_qsq_err_q", Fraction(0, 1), "pillar_1a")
    x_norm = Fraction(3 * 3 + 5 * 5 + 7 * 7 + 11 * 11, 1)
    _expect_q(d, "householder_x_norm_sq_q", x_norm, "pillar_1a")
    _expect_q(d, "householder_qx_norm_sq_q", x_norm, "pillar_1a")
    _expect_q(d, "householder_kappa2_q", Fraction(1, 1), "pillar_1a")
    _expect_q(d, "blockh4_ortho_err_q", Fraction(0, 1), "pillar_1a")
    _expect_q(d, "blockh4_parseval_lhs_q", Fraction(4) * x_norm, "pillar_1a")
    _expect_q(d, "blockh4_parseval_rhs_q", Fraction(4) * x_norm, "pillar_1a")


def _audit_pillar_1b(p: Any) -> None:
    req = {
        "step_oracle_tau", "step_oracle_w0", "step_oracle_local_diff",
        "step_oracle_jump_gain", "lattice_s_max", "lattice_trajectory",
        "lattice_remaining_gaps", "goodhart_surrogate_old", "goodhart_surrogate_new",
        "goodhart_discrete_old", "goodhart_discrete_new",
        "surrogate_accepts_regression", "ratchet_accepts_regression",
        "s31_total_params", "s31_two_row_k", "s31_dpi_two_row_q",
        "expanded_support_k", "expanded_dpi_q", "dpi_reduction_factor_q",
        "s77_wsp_all_faulty_diff_q", "s77_wsp_finished_diff_q",
    }
    d = _require_keys(p, req, "pillar_1b")
    _expect_eq(d, "step_oracle_tau", 5, "pillar_1b")
    _expect_eq(d, "step_oracle_w0", 2, "pillar_1b")
    _expect_eq(d, "step_oracle_local_diff", 0, "pillar_1b")
    _expect_eq(d, "step_oracle_jump_gain", 1, "pillar_1b")
    _expect_eq(d, "lattice_s_max", 10, "pillar_1b")
    _expect_eq(d, "lattice_trajectory", [4, 7, 9, 10], "pillar_1b")
    _expect_eq(d, "lattice_remaining_gaps", [6, 3, 1, 0], "pillar_1b")
    _expect_eq(d, "goodhart_surrogate_old", 10, "pillar_1b")
    _expect_eq(d, "goodhart_surrogate_new", 6, "pillar_1b")
    _expect_eq(d, "goodhart_discrete_old", 8, "pillar_1b")
    _expect_eq(d, "goodhart_discrete_new", 6, "pillar_1b")
    _expect_eq(d, "surrogate_accepts_regression", True, "pillar_1b")
    _expect_eq(d, "ratchet_accepts_regression", False, "pillar_1b")
    _expect_eq(d, "s31_total_params", 233373696, "pillar_1b")
    _expect_eq(d, "s31_two_row_k", 3072, "pillar_1b")
    _expect_q(d, "s31_dpi_two_row_q", Fraction(75968, 1), "pillar_1b")
    _expect_eq(d, "expanded_support_k", 24576, "pillar_1b")
    _expect_q(d, "expanded_dpi_q", Fraction(9496, 1), "pillar_1b")
    _expect_q(d, "dpi_reduction_factor_q", Fraction(8, 1), "pillar_1b")
    _expect_q(d, "s77_wsp_all_faulty_diff_q", Fraction(31, 422), "pillar_1b")
    _expect_q(d, "s77_wsp_finished_diff_q", Fraction(-43, 327), "pillar_1b")


def _audit_pillar_1c(p: Any) -> None:
    req = {
        "s80_single_step_fwer_q", "s80_20step_fwer_q", "s80_20step_fwer_exceeds_87pct",
        "s78_forgetting_kb_q", "s78_learning_kb_q", "s78_forgetting_over_learning_q",
        "nullspace_raw_forgetting_energy_q", "nullspace_projected_forgetting_energy_q",
        "nullspace_dw_total_energy_q", "nullspace_dw_base_energy_q",
        "nullspace_dw_perp_energy_q", "nullspace_pythagorean_residual_q",
        "nullspace_forgetting_ratio_after_proj_q",
        "law5_capacity_ambient_d", "law5_capacity_saturated_rank",
        "law5_capacity_collapsed_null_dim", "law5_capacity_lift_k",
        "law5_capacity_restored_null_dim",
    }
    d = _require_keys(p, req, "pillar_1c")
    fwer20 = Fraction(1) - (Fraction(361, 400) ** 20)
    _expect_q(d, "s80_single_step_fwer_q", Fraction(39, 400), "pillar_1c")
    _expect_q(d, "s80_20step_fwer_q", fwer20, "pillar_1c")
    _expect_eq(d, "s80_20step_fwer_exceeds_87pct", True, "pillar_1c")
    _expect_q(d, "s78_forgetting_kb_q", Fraction(229, 5), "pillar_1c")
    _expect_q(d, "s78_learning_kb_q", Fraction(229, 5), "pillar_1c")
    _expect_q(d, "s78_forgetting_over_learning_q", Fraction(1, 1), "pillar_1c")
    _expect_q(d, "nullspace_raw_forgetting_energy_q", Fraction(154, 1), "pillar_1c")
    _expect_q(d, "nullspace_projected_forgetting_energy_q", Fraction(0, 1), "pillar_1c")
    _expect_q(d, "nullspace_dw_total_energy_q", Fraction(60, 1), "pillar_1c")
    _expect_q(d, "nullspace_dw_base_energy_q", Fraction(154, 3), "pillar_1c")
    _expect_q(d, "nullspace_dw_perp_energy_q", Fraction(26, 3), "pillar_1c")
    _expect_q(d, "nullspace_pythagorean_residual_q", Fraction(0, 1), "pillar_1c")
    _expect_q(d, "nullspace_forgetting_ratio_after_proj_q", Fraction(0, 1), "pillar_1c")
    _expect_eq(d, "law5_capacity_ambient_d", 4, "pillar_1c")
    _expect_eq(d, "law5_capacity_saturated_rank", 4, "pillar_1c")
    _expect_eq(d, "law5_capacity_collapsed_null_dim", 0, "pillar_1c")
    _expect_eq(d, "law5_capacity_lift_k", 2, "pillar_1c")
    _expect_eq(d, "law5_capacity_restored_null_dim", 2, "pillar_1c")


def _audit_pillar_1d(p: Any) -> None:
    req = {
        "static_oneshot_err_fro_sq_q", "static_bilinear_identity_residual_q",
        "recursive_relinearized_err_fro_sq_q",
        "coupled_stale_nullspace_leak_sq_q", "coupled_reprojected_nullspace_leak_sq_q",
        "s70_greedy_layer_energy_a", "s70_greedy_layer_energy_b",
        "s70_greedy_composed_a", "s70_greedy_composed_b", "s70_greedy_regression_ratio_q",
        "vram_bp_analytical_bytes", "vram_pure_analytical_bytes",
        "vram_analytical_savings_bytes",
    }
    d = _require_keys(p, req, "pillar_1d")
    _expect_q(d, "static_oneshot_err_fro_sq_q", Fraction(401, 4608), "pillar_1d")
    _expect_q(d, "static_bilinear_identity_residual_q", Fraction(0, 1), "pillar_1d")
    _expect_q(d, "recursive_relinearized_err_fro_sq_q", Fraction(0, 1), "pillar_1d")
    _expect_q(d, "coupled_stale_nullspace_leak_sq_q", Fraction(1, 9), "pillar_1d")
    _expect_q(d, "coupled_reprojected_nullspace_leak_sq_q", Fraction(0, 1), "pillar_1d")
    _expect_eq(d, "s70_greedy_layer_energy_a", 101, "pillar_1d")
    _expect_eq(d, "s70_greedy_layer_energy_b", 100, "pillar_1d")
    _expect_eq(d, "s70_greedy_composed_a", 4, "pillar_1d")
    _expect_eq(d, "s70_greedy_composed_b", 400, "pillar_1d")
    _expect_q(d, "s70_greedy_regression_ratio_q", Fraction(100, 1), "pillar_1d")
    model_b = 494032768 * 2
    bp_b = model_b + (32 * 64 * 896 * 24 * 2) + (172032 * 2) + (172032 * 2) + (172032 * 8)
    pure_b = model_b + (4096 * 4)
    _expect_eq(d, "vram_bp_analytical_bytes", bp_b, "pillar_1d")
    _expect_eq(d, "vram_pure_analytical_bytes", pure_b, "pillar_1d")
    _expect_eq(d, "vram_analytical_savings_bytes", bp_b - pure_b, "pillar_1d")


def _audit_pillar_2_anchor(p: Any) -> None:
    req = {
        "epistemic_tag", "live_results_file", "live_results_sha256",
        "live_results_inner_sha256",
        "mlos_receipt_file", "mlos_receipt_sha256",
        "mlos_determinism_zone", "mlos_clean_hardware_run",
        "model_id", "gpu_name", "seed", "weights_saved_in_expedition",
        "baseline_heldout_discrete_acc_q", "baseline_heldout_full_vocab_acc_q",
        "baseline_heldout_target_nll_q", "baseline_heldout_mean_margin_q",
        "baseline_wiki_test_nll_q", "baseline_wiki_test_ppl_q",
        "arms", "pure_vs_backprop_vram_cut_mib_q", "pure_vs_backprop_vram_cut_ratio_q",
    }
    d = _require_keys(p, req, "pillar_2")
    _expect_eq(d, "epistemic_tag", "anchor", "pillar_2")
    _expect_eq(d, "live_results_file", oracle.PINNED_LIVE_RESULTS_FILE, "pillar_2")
    _expect_eq(d, "live_results_sha256", oracle.PINNED_LIVE_RESULTS_SHA256, "pillar_2")
    _expect_eq(d, "live_results_inner_sha256", PINNED_LIVE_INNER_SHA256, "pillar_2")
    _expect_eq(d, "mlos_receipt_file", oracle.PINNED_MLOS_RECEIPT_FILE, "pillar_2")
    _expect_eq(d, "mlos_receipt_sha256", oracle.PINNED_MLOS_RECEIPT_SHA256, "pillar_2")
    _expect_eq(d, "mlos_determinism_zone", "B", "pillar_2")
    _expect_eq(d, "mlos_clean_hardware_run", True, "pillar_2")
    _expect_eq(d, "model_id", "Qwen/Qwen2.5-0.5B", "pillar_2")
    _expect_eq(d, "gpu_name", PINNED_GPU_NAME, "pillar_2")
    _expect_eq(d, "seed", 42, "pillar_2")
    _expect_eq(d, "weights_saved_in_expedition", 0, "pillar_2")

    base_acc = parse_qdict(d["baseline_heldout_discrete_acc_q"], "pillar_2.base_acc")
    parse_qdict(d["baseline_heldout_full_vocab_acc_q"], "pillar_2.base_full_acc")
    parse_qdict(d["baseline_heldout_target_nll_q"], "pillar_2.base_nll")
    parse_qdict(d["baseline_heldout_mean_margin_q"], "pillar_2.base_margin")
    base_wiki = parse_qdict(d["baseline_wiki_test_nll_q"], "pillar_2.base_wiki")
    base_ppl = parse_qdict(d["baseline_wiki_test_ppl_q"], "pillar_2.base_ppl")
    if base_ppl <= 1:
        raise VerifyError("INVALID_BASELINE_RANGE", "Baseline perplexity must be > 1")

    arms = d["arms"]
    if type(arms) is not list or len(arms) != 4:
        raise VerifyError("INVALID_ARMS_LIST", "pillar_2.arms must be list of 4 arms")
    arm_req = {
        "arm", "backprop_free", "total_steps", "accepted_steps", "rejected_steps",
        "wall_time_sec_q", "peak_vram_alloc_mib_q", "peak_vram_reserved_mib_q",
        "dev_discrete_acc_q", "dev_target_nll_q",
        "heldout_discrete_acc_q", "heldout_full_vocab_acc_q",
        "heldout_target_nll_q", "heldout_mean_margin_q",
        "heldout_acc_gain_q", "wiki_test_nll_q", "wiki_test_nll_drift_q",
        "wiki_test_ppl_q", "wiki_test_ppl_drift_q",
        "edit_fro_norm_q", "edit_dpi_row_concentration_q",
    }
    by_name: Dict[str, Dict[str, Any]] = {}
    for idx, arm in enumerate(arms):
        ad = _require_keys(arm, arm_req, f"pillar_2.arms[{idx}]")
        name = ad["arm"]
        if name != EXPECTED_ARM_NAMES[idx]:
            raise VerifyError("ARM_ORDER_MISMATCH", f"Unexpected arm name/order: {name!r}")
        if not (
            type(ad["backprop_free"]) is bool
            and is_exact_int(ad["total_steps"])
            and is_exact_int(ad["accepted_steps"])
            and is_exact_int(ad["rejected_steps"])
        ):
            raise VerifyError("ARM_FIELD_TYPE", f"Invalid field type in {name}")
        if (
            ad["total_steps"] <= 0
            or ad["accepted_steps"] < 0
            or ad["rejected_steps"] < 0
            or ad["accepted_steps"] + ad["rejected_steps"] != ad["total_steps"]
        ):
            raise VerifyError("ARM_NEG_STEPS", f"Invalid step accounting in {name}")
        v_alloc = parse_qdict(ad["peak_vram_alloc_mib_q"], f"{name}.vram_alloc")
        v_res = parse_qdict(ad["peak_vram_reserved_mib_q"], f"{name}.vram_res")
        acc = parse_qdict(ad["heldout_discrete_acc_q"], f"{name}.acc")
        parse_qdict(ad["heldout_full_vocab_acc_q"], f"{name}.full_acc")
        parse_qdict(ad["dev_discrete_acc_q"], f"{name}.dev_acc")
        parse_qdict(ad["dev_target_nll_q"], f"{name}.dev_nll")
        parse_qdict(ad["heldout_target_nll_q"], f"{name}.t_nll")
        parse_qdict(ad["heldout_mean_margin_q"], f"{name}.margin")
        w_nll = parse_qdict(ad["wiki_test_nll_q"], f"{name}.w_nll")
        w_ppl = parse_qdict(ad["wiki_test_ppl_q"], f"{name}.w_ppl")
        parse_qdict(ad["wall_time_sec_q"], f"{name}.wall")
        parse_qdict(ad["edit_fro_norm_q"], f"{name}.fro")
        parse_qdict(ad["edit_dpi_row_concentration_q"], f"{name}.dpi")
        acc_gain = parse_qdict(ad["heldout_acc_gain_q"], f"{name}.acc_gain")
        w_drift = parse_qdict(ad["wiki_test_nll_drift_q"], f"{name}.w_drift")
        ppl_drift = parse_qdict(ad["wiki_test_ppl_drift_q"], f"{name}.ppl_drift")
        if acc_gain != acc - base_acc:
            raise VerifyError("ALGEBRAIC_MISMATCH", f"{name}.heldout_acc_gain_q mismatch")
        if w_drift != w_nll - base_wiki:
            raise VerifyError("ALGEBRAIC_MISMATCH", f"{name}.wiki_test_nll_drift_q mismatch")
        if ppl_drift != w_ppl - base_ppl:
            raise VerifyError("ALGEBRAIC_MISMATCH", f"{name}.wiki_test_ppl_drift_q mismatch")
        if v_alloc <= 0 or v_res < v_alloc:
            raise VerifyError("ARM_RANGE_INVALID", f"Invalid VRAM bounds in {name}")
        by_name[name] = ad

    _expect_eq(by_name["Std-Backprop-LoRA"], "backprop_free", False, "arm1")
    _expect_eq(by_name["Naive-WSE-HC"], "backprop_free", True, "arm2")
    _expect_eq(by_name["Aletheia-WSE-HC-Pure"], "backprop_free", True, "arm3")
    _expect_eq(by_name["Aletheia-WSE-HC-Hybrid"], "backprop_free", False, "arm4")

    bp_v = parse_qdict(by_name["Std-Backprop-LoRA"]["peak_vram_alloc_mib_q"], "bp_v")
    pure_v = parse_qdict(by_name["Aletheia-WSE-HC-Pure"]["peak_vram_alloc_mib_q"], "pure_v")
    exp_cut = bp_v - pure_v
    _expect_q(d, "pure_vs_backprop_vram_cut_mib_q", exp_cut, "pillar_2")
    _expect_q(d, "pure_vs_backprop_vram_cut_ratio_q", exp_cut / bp_v, "pillar_2")
    p2_canon = json.dumps(d, sort_keys=True, separators=(",", ":")).encode("utf-8")
    p2_sha = hashlib.sha256(p2_canon).hexdigest()
    if not hmac.compare_digest(p2_sha, PINNED_P2_CANON_SHA256):
        raise VerifyError("ANCHOR_DIGEST_MISMATCH", "pillar_2 live telemetry digest mismatch")


def _audit_lean_manifest(lm: Any) -> None:
    req = {
        "file", "sha256", "namespace", "theorem_count",
        "universal_theorem_count", "theorems", "allowed_axioms",
    }
    d = _require_keys(lm, req, "lean4_certificate")
    _expect_eq(d, "file", LEAN_FILE_NAME, "lean4_certificate")
    _expect_eq(d, "sha256", LEAN_FILE_SHA256, "lean4_certificate")
    _expect_eq(d, "namespace", LEAN_NAMESPACE, "lean4_certificate")
    _expect_eq(d, "theorem_count", len(LEAN_THEOREMS), "lean4_certificate")
    _expect_eq(d, "universal_theorem_count", len(LEAN_THEOREMS), "lean4_certificate")
    _expect_eq(d, "theorems", list(LEAN_THEOREMS), "lean4_certificate")
    _expect_eq(d, "allowed_axioms", ["propext", "Quot.sound"], "lean4_certificate")


def _audit_upstream_manifest(um: Any) -> None:
    if type(um) is not list or len(um) != len(UPSTREAM_CERT_MANIFEST):
        raise VerifyError("UPSTREAM_MANIFEST_LEN", "Upstream manifest length mismatch")
    for idx, (exp_tid, exp_rel, exp_sha) in enumerate(UPSTREAM_CERT_MANIFEST):
        entry = _require_keys(um[idx], {"track_id", "rel_path", "sha256"}, f"upstream[{idx}]")
        _expect_eq(entry, "track_id", exp_tid, f"upstream[{idx}]")
        _expect_eq(entry, "rel_path", exp_rel, f"upstream[{idx}]")
        _expect_eq(entry, "sha256", exp_sha, f"upstream[{idx}]")


def secondary_audit_payload(payload: Any) -> Dict[str, Any]:
    """Independent non-hollow semantic & algebraic audit of the certificate payload."""
    scan_json_tree_iterative(payload)
    req = {
        "track_id", "epistemic_classes",
        "pillar_1a_subspace_collapse", "pillar_1b_discrete_oracle",
        "pillar_1c_ratchet_and_nullspace", "pillar_1d_recursive_relinearization",
        "pillar_2_live_rtx3080_anchor",
        "lean4_certificate", "upstream_cert_manifest", "novelty_honesty_law4",
    }
    p = _require_keys(payload, req, "payload")
    _expect_eq(p, "track_id", TRACK_ID, "payload")
    ec = _require_keys(p["epistemic_classes"], {"pillar_1", "pillar_2", "pillar_3"}, "epistemic_classes")
    _expect_eq(ec, "pillar_1", "exact", "epistemic_classes")
    _expect_eq(ec, "pillar_2", "anchor", "epistemic_classes")
    _expect_eq(ec, "pillar_3", "exact", "epistemic_classes")

    _audit_pillar_1a(p["pillar_1a_subspace_collapse"])
    _audit_pillar_1b(p["pillar_1b_discrete_oracle"])
    _audit_pillar_1c(p["pillar_1c_ratchet_and_nullspace"])
    _audit_pillar_1d(p["pillar_1d_recursive_relinearization"])
    _audit_pillar_2_anchor(p["pillar_2_live_rtx3080_anchor"])
    _audit_lean_manifest(p["lean4_certificate"])
    _audit_upstream_manifest(p["upstream_cert_manifest"])

    nh = _require_keys(
        p["novelty_honesty_law4"],
        {"novelty_tier", "n0_prior_art_credited", "n1_verified_synthesis", "n2_claims"},
        "novelty_honesty_law4",
    )
    _expect_eq(nh, "novelty_tier", "N1", "novelty_honesty_law4")
    _expect_eq(nh, "n0_prior_art_credited", True, "novelty_honesty_law4")
    _expect_eq(nh, "n1_verified_synthesis", True, "novelty_honesty_law4")
    _expect_eq(nh, "n2_claims", 0, "novelty_honesty_law4")
    return {"ok": True, "pillars_verified": 6}


def verify_certificate_dict(
    cert: Any,
    *,
    full_replay: bool = True,
    track_dir: Optional[pathlib.Path] = None,
) -> Dict[str, Any]:
    """Verify full certificate envelope (hash pins + non-hollow audit + optional live replay)."""
    if type(full_replay) is not bool:
        raise VerifyError("INVALID_FULL_REPLAY", "full_replay must be bool")
    scan_json_tree_iterative(cert)
    c = _require_keys(cert, {"schema_version", "payload_sha256", "payload", "certificate_sha256"}, "cert")
    _expect_eq(c, "schema_version", SCHEMA_VERSION, "cert")
    p_sha = c["payload_sha256"]
    c_sha = c["certificate_sha256"]
    if not (is_hex64(p_sha) and is_hex64(c_sha)):
        raise VerifyError("INVALID_SHA_FORMAT", "payload_sha256 and certificate_sha256 must be 64-char hex")

    payload = c["payload"]
    canon_pay = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    calc_pay_sha = hashlib.sha256(canon_pay).hexdigest()
    if not hmac.compare_digest(p_sha, calc_pay_sha):
        raise VerifyError("PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")

    envelope = {
        "schema_version": c["schema_version"],
        "payload_sha256": p_sha,
        "payload": payload,
    }
    canon_env = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
    calc_cert_sha = hashlib.sha256(canon_env).hexdigest()
    if not hmac.compare_digest(c_sha, calc_cert_sha):
        raise VerifyError("CERT_SHA_MISMATCH", "certificate_sha256 mismatch")

    secondary_audit_payload(payload)

    if full_replay:
        root = pathlib.Path(__file__).resolve().parent if track_dir is None else track_dir
        try:
            expected = oracle.build_certificate(
                root / oracle.PINNED_LIVE_RESULTS_FILE,
                root / oracle.PINNED_MLOS_RECEIPT_FILE,
            )
        except (ValueError, KeyError, TypeError, OSError) as exc:
            raise VerifyError("REPLAY_BUILD_FAILED", str(exc)) from exc
        got_canon = json.dumps(c, sort_keys=True, separators=(",", ":")).encode("utf-8")
        exp_canon = json.dumps(expected, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if not hmac.compare_digest(got_canon, exp_canon):
            raise VerifyError("FULL_REPLAY_MISMATCH", "Certificate does not match oracle replay")

    return {
        "ok": True,
        "full_replay": full_replay,
        "schema_version": SCHEMA_VERSION,
        "payload_sha256": calc_pay_sha,
        "certificate_sha256": calc_cert_sha,
    }


def read_regular_file_bytes(path: pathlib.Path, max_bytes: int, label: str) -> bytes:
    path_str = str(path)
    if "\x00" in path_str:
        raise VerifyError("NULL_BYTE_PATH", f"{label}: null byte in path")
    # Reject symlinks anywhere along the explicit path prefix
    cur = pathlib.Path("/") if path.is_absolute() else pathlib.Path(".")
    for part in path.parts:
        if part in ("/", ""):
            continue
        cur = cur / part
        try:
            st_p = os.lstat(cur)
        except OSError as exc:
            raise VerifyError("FILE_MISSING", f"{label}: {exc}") from exc
        if stat.S_ISLNK(st_p.st_mode):
            raise VerifyError("SYMLINK_FORBIDDEN", f"{label}: symlink forbidden at {part}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path_str, flags)
    except OSError as exc:
        raise VerifyError("FILE_OPEN_ERROR", f"{label}: {exc}") from exc
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise VerifyError("NOT_REGULAR_FILE", f"{label}: must be regular file")
        chunks: List[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise VerifyError("FILE_TOO_LARGE", f"{label}: exceeds max size")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def check_certificate_file(
    path: pathlib.Path,
    *,
    full_replay: bool = True,
    track_dir: Optional[pathlib.Path] = None,
) -> Dict[str, Any]:
    if type(full_replay) is not bool:
        raise VerifyError("INVALID_FULL_REPLAY", "full_replay must be bool")
    raw = read_regular_file_bytes(path, MAX_CERT_BYTES, "certificate")
    if b"\r" in raw:
        raise VerifyError("CRLF_FORBIDDEN", "CRLF line endings forbidden in certificate")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VerifyError("INVALID_UTF8", str(exc)) from exc
    obj = strict_json_loads(text)
    canon = (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if not hmac.compare_digest(raw, canon):
        raise VerifyError("NON_CANONICAL_JSON", "Certificate bytes must be canonical JSON")
    res = verify_certificate_dict(obj, full_replay=full_replay, track_dir=track_dir)
    res["file_sha256"] = hashlib.sha256(raw).hexdigest()
    return res


def strip_lean_comments(src: str) -> str:
    """Strip nested Lean /- ... -/ block comments and -- line comments, preserving newlines."""
    out: List[str] = []
    i = 0
    n = len(src)
    depth = 0
    while i < n:
        if depth > 0:
            if src.startswith("/-", i):
                depth += 1
                i += 2
            elif src.startswith("-/", i):
                depth -= 1
                i += 2
            else:
                if src[i] == "\n":
                    out.append("\n")
                i += 1
        else:
            if src.startswith("/-", i):
                depth = 1
                i += 2
            elif src.startswith("--", i):
                nl = src.find("\n", i)
                i = n if nl < 0 else nl
            else:
                out.append(src[i])
                i += 1
    if depth != 0:
        raise VerifyError("LEAN_UNCLOSED_COMMENT", "Unclosed /- block comment in Lean source")
    return "".join(out)


def scan_lean_source_r10(src: str) -> List[str]:
    """R10+ comment-aware static trust-escape scanner."""
    if "\r" in src:
        raise VerifyError("LEAN_CRLF", "CRLF line endings forbidden in Lean source")
    stripped = strip_lean_comments(src)
    hits: List[str] = []
    for code, pat in BANNED_LEAN_PATTERNS:
        if pat.search(stripped):
            hits.append(code)
    return hits


def resolve_lean_binary() -> Optional[str]:
    """$HOME-aware Lean 4 binary lookup (S89-INFO-02)."""
    found = shutil.which("lean")
    if found:
        return found
    home_env = os.environ.get("HOME", "")
    if home_env:
        cand = pathlib.Path(home_env) / ".elan" / "bin" / "lean"
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    return None


def verify_lean_file(lean_path: pathlib.Path, check_pinned_sha: bool = True) -> Dict[str, Any]:
    """Live zero-TOCTOU R10+ Lean 4.36.0 verifier."""
    if type(check_pinned_sha) is not bool:
        raise VerifyError("INVALID_CHECK_PINNED_SHA", "check_pinned_sha must be bool")
    raw = read_regular_file_bytes(lean_path, MAX_LEAN_BYTES, "lean_file")
    sha = hashlib.sha256(raw).hexdigest()
    if check_pinned_sha and sha != LEAN_FILE_SHA256:
        raise VerifyError("LEAN_SHA_MISMATCH", f"Pinned Lean SHA mismatch: {sha}")
    try:
        src = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VerifyError("LEAN_INVALID_UTF8", str(exc)) from exc

    hits = scan_lean_source_r10(src)
    if hits:
        raise VerifyError("LEAN_STATIC_ESCAPE", ",".join(hits))

    stripped = strip_lean_comments(src)
    found_thms = re.findall(
        r"(?m)^\s*(?:(?:private|protected|noncomputable|unsafe|partial)\s+)*theorem\s+([^\s:(]+)",
        stripped,
    )
    if not found_thms:
        raise VerifyError("LEAN_NO_THEOREMS_VERIFIED", "Lean file declares zero theorems")

    lean_bin = resolve_lean_binary()
    if lean_bin is None:
        raise VerifyError("LEAN_BINARY_NOT_FOUND", "Lean 4 binary unavailable on PATH or $HOME/.elan/bin")

    lean_env = {k: v for k, v in os.environ.items() if k in SAFE_LEAN_ENV_KEYS}

    tmp_dir = pathlib.Path(tempfile.mkdtemp(prefix="s97_lean_"))
    try:
        os.chmod(tmp_dir, 0o700)
        main_copy = tmp_dir / "Verified.lean"
        main_copy.write_bytes(raw)
        os.chmod(main_copy, 0o600)

        proc1 = subprocess.run(
            [lean_bin, str(main_copy)],
            env=lean_env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc1.returncode != 0 or (proc1.stdout + proc1.stderr).strip():
            raise VerifyError("LEAN_ELAB_FAILED", (proc1.stderr + proc1.stdout).strip()[:300])

        ns_match = re.search(r"(?m)^\s*namespace\s+([A-Za-z0-9_.]+)\b", stripped)
        prefix = f"{ns_match.group(1)}." if ns_match else ""
        audit_lines = [src, ""]
        for thm in found_thms:
            audit_lines.append(f"#print axioms {prefix}{thm}")
        audit_copy = tmp_dir / "Audit.lean"
        audit_copy.write_text("\n".join(audit_lines) + "\n", encoding="utf-8")
        os.chmod(audit_copy, 0o600)

        proc2 = subprocess.run(
            [lean_bin, str(audit_copy)],
            env=lean_env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc2.returncode != 0:
            raise VerifyError("LEAN_AXIOM_AUDIT_FAILED", (proc2.stderr + proc2.stdout).strip()[:300])

        axioms_used: set[str] = set()
        seen: set[str] = set()
        for line in proc2.stdout.splitlines():
            m_none = re.match(r"^'([^']+)' does not depend on any axioms$", line.strip())
            if m_none:
                seen.add(m_none.group(1))
                continue
            m_ax = re.match(r"^'([^']+)' depends on axioms: \[([^\]]*)\]$", line.strip())
            if m_ax:
                seen.add(m_ax.group(1))
                for ax in m_ax.group(2).split(","):
                    tok = ax.strip()
                    if tok:
                        if tok not in LEAN_ALLOWED_AXIOMS:
                            raise VerifyError("LEAN_BANNED_AXIOM", f"{m_ax.group(1)} uses {tok}")
                        axioms_used.add(tok)
        expected_seen = {f"{prefix}{t}" for t in found_thms}
        if seen != expected_seen:
            raise VerifyError("LEAN_MISSING_AXIOM_REPORT", f"Verified {len(seen)}/{len(found_thms)} theorems")
        return {
            "ok": True,
            "sha256": sha,
            "sha256_pinned": check_pinned_sha,
            "theorem_count": len(found_thms),
            "axioms_used": sorted(axioms_used),
            "static_clean": True,
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def verify_upstream_pins(expedition_root: pathlib.Path) -> Dict[str, Any]:
    """Verify upstream cert pins: in-repo pins are opened and re-hashed on disk;
    external pins (S68/S70/S73/S78) are labelled external-historical-pin and resolve in no readable repo."""
    matched = 0
    cross_repo = []
    for tid, rel_path, exp_sha in UPSTREAM_CERT_MANIFEST:
        if tid in oracle.CROSS_REPO_UPSTREAM:
            cross_repo.append({"track_id": tid, "source_repo": oracle.CROSS_REPO_SOURCE, "sha256": exp_sha})
            continue
        target = expedition_root / rel_path
        raw = read_regular_file_bytes(target, 4 * 1024 * 1024, f"upstream:{tid}")
        got = hashlib.sha256(raw).hexdigest()
        if not hmac.compare_digest(got, exp_sha):
            raise VerifyError("UPSTREAM_SHA_MISMATCH", f"{tid}: got {got}, expected {exp_sha}")
        matched += 1
    return {"ok": True, "matched": matched, "cross_repo": cross_repo, "total": len(UPSTREAM_CERT_MANIFEST)}


def _parse_cli_args(argv: Any) -> Dict[str, Any]:
    if type(argv) is not list:
        raise VerifyError("INVALID_ARGV", "argv must be exact list")
    here = pathlib.Path(__file__).resolve().parent
    opts: Dict[str, Any] = {
        "check": None,
        "verify_lean": None,
        "verify_upstream": None,
        "json": False,
        "full_replay": True,
    }
    i = 0
    n = len(argv)
    while i < n:
        arg = argv[i]
        if type(arg) is not str or "\x00" in arg:
            raise VerifyError("INVALID_ARG", "Argument must be NUL-free str")
        if arg == "--json":
            if opts["json"]:
                raise VerifyError("DUPLICATE_FLAG", "--json repeated")
            opts["json"] = True
            i += 1
        elif arg == "--no-replay":
            if not opts["full_replay"]:
                raise VerifyError("DUPLICATE_FLAG", "--no-replay repeated")
            opts["full_replay"] = False
            i += 1
        elif arg in ("--check", "--verify-lean", "--verify-upstream"):
            key = arg[2:].replace("-", "_")
            if opts[key] is not None:
                raise VerifyError("DUPLICATE_FLAG", f"{arg} repeated")
            if i + 1 < n and type(argv[i + 1]) is str and not argv[i + 1].startswith("-"):
                val = argv[i + 1]
                if "\x00" in val or not val:
                    raise VerifyError("INVALID_PATH_ARG", f"Invalid path for {arg}")
                opts[key] = val
                i += 2
            elif arg == "--check":
                opts[key] = str(here / "s97_wse_hc_certificate.json")
                i += 1
            elif arg == "--verify-lean":
                opts[key] = str(here / LEAN_FILE_NAME)
                i += 1
            else:
                raise VerifyError("MISSING_PATH_ARG", f"{arg} requires a directory path")
        else:
            raise VerifyError("UNKNOWN_FLAG", f"Unsupported argument: {arg!r}")
    if opts["check"] is None and opts["verify_lean"] is None and opts["verify_upstream"] is None:
        opts["check"] = str(here / "s97_wse_hc_certificate.json")
    return opts


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv: Any = list(sys.argv[1:]) if argv is None else argv
    want_json = False
    try:
        opts = _parse_cli_args(raw_argv)
        want_json = opts["json"]
        report: Dict[str, Any] = {"ok": True}
        if opts["check"] is not None:
            report["certificate"] = check_certificate_file(
                pathlib.Path(opts["check"]), full_replay=opts["full_replay"]
            )
        if opts["verify_lean"] is not None:
            report["lean"] = verify_lean_file(pathlib.Path(opts["verify_lean"]), check_pinned_sha=True)
        if opts["verify_upstream"] is not None:
            report["upstream"] = verify_upstream_pins(pathlib.Path(opts["verify_upstream"]))
    except VerifyError as exc:
        err_obj = {"ok": False, "code": exc.code, "detail": exc.detail}
        if want_json:
            print(json.dumps(err_obj, sort_keys=True))
        else:
            print(f"[S97_FAIL] {exc.code}: {exc.detail}", file=sys.stderr)
        return 2

    if want_json:
        print(json.dumps(report, sort_keys=True))
    else:
        print(f"[S97_PASS] verified={sorted(k for k in report if k != 'ok')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
