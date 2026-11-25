#!/usr/bin/env python3
"""
Track S96 Hardened Standalone Verifier, Upstream/Spec Auditor & R12 Lean 4.36.0 Gate.

Supports:
  --standalone --json         Compute and emit canonical zero-float certificate JSON to stdout
  --write <cert.json>         Atomically write canonical 0o600 certificate JSON via dir_fd + fsync
  --check <cert.json>         Fail-closed Zone-B hardened verification of certificate JSON on disk
  --verify-lean <file.lean>   Full R12 static Lean 4 audit + live scrubbed Lean 4.36.0 --stdin axiom check
  --verify-upstream <dir>     Verify all 10 pinned upstream expedition certificate SHA-256s
  --verify-inkling <dir>      Verify both pinned Inkling-2-Mini local spec SHA-256s

Zero floats on trust paths, zero bare asserts, zero external dependencies, zero RNG calls.
"""
from __future__ import annotations

import argparse
import errno
from fractions import Fraction
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
import threading
from typing import Any

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from s96_beyond_lora_inkling_oracle import (
    CERT_SCHEMA,
    CERT_TRACK_ID,
    INKLING_SPEC_MANIFEST,
    LEAN_FILE_NAME,
    LEAN_FILE_SHA256,
    LEAN_THEOREMS,
    MAX_INT_BITS,
    MAX_JSON_DEPTH,
    S96Error,
    UPSTREAM_CERT_MANIFEST,
    build_certificate,
    canonical_json_bytes,
    frac_to_dec_str,
    require_ok,
)

MAX_JSON_BYTES = 1_048_576
_READ_CHUNK_BYTES = 65_536
MAX_INT_DIGITS = 617
_HEX_LOWER = frozenset("0123456789abcdef")
_CERT_KEYS = frozenset({"schema", "track_id", "payload_sha256", "certificate_sha256", "payload"})
_RAT_KEYS = frozenset({"num", "den"})
_PAYLOAD_KEYS = frozenset(
    {
        "pillar1_lora_three_bottlenecks",
        "pillar2_beyond_lora_architectures",
        "pillar3_inkling2_loop_and_roofline",
        "pillar4_provenance_and_lean4",
    }
)
_P1_KEYS = frozenset(
    {
        "qwen25_05b_r16_starvation",
        "s78_fig3_vproj_r128",
        "s78_full_rank_r512",
        "privileged_basis_commutator",
        "s78_fig7_unit_conservation",
        "pillar_verified",
    }
)
_LORA_METRIC_KEYS = frozenset(
    {
        "m",
        "n",
        "rank",
        "p_raw",
        "d_eff",
        "eta_alg_q",
        "unreachable_dim",
        "unreachable_frac_q",
        "unreachable_pct_dec",
        "rank_starved",
    }
)
_COMM_KEYS = frozenset(
    {
        "anisotropic_comm_frob_sq_q",
        "isotropic_comm_frob_sq_q",
        "commutator_nonzero_under_anisotropy",
        "commutator_zero_under_isotropy",
    }
)
_UNIT_CONS_KEYS = frozenset(
    {"forgetting_kb_q", "learning_kb_q", "forgetting_over_learning_q", "unit_conservation_exact"}
)
_P2_KEYS = frozenset(
    {
        "matched_budget_blockh4_butterfly",
        "privsparse_householder_isometry",
        "nullspace_projected_antiforgetting",
        "s95_bf16_ulp_diagnosis_and_hybrid_prereg",
        "pillar_verified",
    }
)
_S95_HYB_KEYS = frozenset(
    {
        "bf16_half_ulp_threshold_q",
        "bf16_half_ulp_zero_frac_butterfly_q",
        "bf16_half_ulp_zero_frac_lora_q",
        "bf16_annihilation_ratio_q",
        "bf16_annihilation_ratio_dec",
        "butterflyhead_proj_dim",
        "butterflyhead_stages_s",
        "butterflyhead_rank_r",
        "butterflyhead_bfly_params",
        "butterflyhead_head_params",
        "butterflyhead_total_params_per_proj",
        "butterflyhead_nullspace_top_k",
        "butterflyhead_frob_cap_frac_q",
        "butterflyhead_head_lr_q",
        "butterflyhead_bfly_lr_q",
        "butterflyhead_lr_ratio_q",
        "s104_kronecker_rank2_head_params",
        "s104_kronecker_compression_ratio_q",
        "pass_exact_all5_min_q",
        "kill_exact_all5_max_q",
        "pass_nll_retention_ratio_cap_q",
        "pass_bf16_zero_frac_cap_q",
        "pass_top16_energy_cap_q",
        "pass_sigma_max_cap_q",
        "pass_rel_frob_cap_q",
        "pass_peak_vram_cap_mib",
        "exact_budget_parity_verified",
    }
)
_BF_KEYS = frozenset(
    {
        "dim",
        "matched_lora_rank",
        "matched_param_budget",
        "standard_lora_rank",
        "butterfly_rank",
        "butterfly_interleaved_rank",
        "full_rank_advantage_q",
        "blockh4_exact_orthogonal",
        "law5_unpermuted_cross_block_sq_q",
        "interleaved_cross_block_sq_q",
        "law5_locality_obstruction_verified",
        "interleave_restores_mixing",
    }
)
_HH_KEYS = frozenset(
    {
        "s42_fisher_waterfilling_gain_q",
        "householder_dim",
        "householder_det_q",
        "householder_exact_orthogonal",
        "householder_exact_involutive",
        "probe_norm_sq_before_q",
        "probe_norm_sq_after_q",
        "householder_kappa2_q",
        "s82_shear_kappa2_lower_q",
        "cures_s82_shear_blowup",
    }
)
_NS_WRAP_KEYS = frozenset({"rank2_calibration_projection", "law5_full_rank_saturation_control"})
_NS_KEYS = frozenset(
    {
        "dim",
        "base_rank",
        "nullspace_dim",
        "raw_forgetting_sq_q",
        "projected_forgetting_sq_q",
        "projected_update_energy_sq_q",
        "exact_zero_forgetting",
        "nullspace_saturated",
    }
)
_P3_KEYS = frozenset(
    {
        "inkling2_config_exact",
        "loop_core_adapter_amplification",
        "per_pass_quant_noise_and_m1h1_gate",
        "hardware_roofline_comparison",
        "pillar_verified",
    }
)
_M1H1_KEYS = frozenset(
    {
        "s76_g3_quant_amp_q",
        "s76_g3_quant_amp_dec",
        "s76_g3_over_rho3_ratio_q",
        "s76_passes_m1h1_drift_gate",
        "high_rho_q",
        "high_rho_3pass_init_q",
        "high_rho_g3_quant_amp_q",
        "high_rho_g3_quant_amp_dec",
        "high_rho_contracts_init_but_kills_m1h1",
        "threshold_lo_rho_q",
        "threshold_lo_g3_q",
        "threshold_hi_rho_q",
        "threshold_hi_g3_q",
        "m1h1_max_drift_ratio_delta3_over_delta1_ctrl_q",
        "m1h1_max_rel_l2_drift_delta3_q",
        "requires_unique_layer_fp_baseline",
        "requires_single_pass_nvfp4_control",
    }
)
_INK_CFG_KEYS = frozenset(
    {
        "hidden_size",
        "sqrt_hidden_size",
        "num_hidden_layers",
        "vocab_size",
        "unpadded_vocab_size",
        "num_attention_heads",
        "num_key_value_heads",
        "head_dim",
        "local_layer_count",
        "global_layer_count",
        "sliding_window_size",
        "n_routed_experts",
        "num_experts_per_tok",
        "active_expert_frac_q",
        "intermediate_size",
        "intermediate_over_hidden_q",
        "mlp_gate_softcap",
        "mlp_up_softcap",
        "route_scale",
        "core_start",
        "core_end",
        "core_layers",
        "num_passes",
        "gate_rank",
        "effective_layers",
        "depth_reuse_ratio_q",
        "gate_rank_over_sqrt_hidden_q",
        "mtp_block_size",
        "mtp_markov_rank",
        "mtp_target_layer_ids",
        "readme_total_params_b_q",
        "readme_physical_active_b_q",
        "readme_effective_active_b_q",
        "readme_effective_over_physical_active_q",
    }
)
_LOOP_AMP_KEYS = frozenset(
    {
        "gate_adapter_params_per_core_layer",
        "core_adapter_total_params",
        "nonloop_equivalent_params",
        "effective_layer_leverage_q",
        "s76_contractive_rho_q",
        "s76_3pass_error_bound_q",
        "divergent_3pass_error_q",
        "contractive_3pass_stable",
    }
)
_ROOF_WRAP_KEYS = frozenset(
    {"rtx3080_8gib", "workstation_32gib", "qwen25_05b_bf16_vram_frac_of_8gib_q", "qwen25_05b_bf16_vram_pct_dec"}
)
_ROOF_KEYS = frozenset(
    {
        "model_gb_q",
        "gpu_vram_gb_q",
        "full_resident_fits",
        "full_resident_overflow_gb_q",
        "model_over_vram_ratio_q",
        "streamed_vram_gb_q",
        "streamed_fits_gpu",
        "cold_experts_gb_q",
        "cold_fits_host_ram",
        "streaming_tier_feasible",
    }
)
_P4_KEYS = frozenset(
    {
        "inkling_spec_count",
        "inkling_spec_manifest",
        "upstream_corpus_count",
        "upstream_cert_manifest",
        "lean4_certificate",
        "novelty_honesty_law4",
    }
)
_SPEC_ENTRY_KEYS = frozenset({"filename", "sha256"})
_MANIFEST_ENTRY_KEYS = frozenset({"track_id", "rel_path", "sha256"})
_LEAN_CERT_KEYS = frozenset({"file", "sha256", "theorem_count", "theorems", "allowed_axioms"})
_NOVELTY_KEYS = frozenset({"novelty_tier", "n0_prior_art_anchored", "n1_exact_synthesis_verified", "n2_claims"})
_PAYLOAD_BOOL_KEYS = frozenset(
    {
        "blockh4_exact_orthogonal",
        "cold_fits_host_ram",
        "commutator_nonzero_under_anisotropy",
        "commutator_zero_under_isotropy",
        "contractive_3pass_stable",
        "cures_s82_shear_blowup",
        "exact_budget_parity_verified",
        "exact_zero_forgetting",
        "full_resident_fits",
        "high_rho_contracts_init_but_kills_m1h1",
        "householder_exact_involutive",
        "householder_exact_orthogonal",
        "interleave_restores_mixing",
        "law5_locality_obstruction_verified",
        "n0_prior_art_anchored",
        "n1_exact_synthesis_verified",
        "nullspace_saturated",
        "pillar_verified",
        "rank_starved",
        "requires_single_pass_nvfp4_control",
        "requires_unique_layer_fp_baseline",
        "s76_passes_m1h1_drift_gate",
        "streamed_fits_gpu",
        "streaming_tier_feasible",
        "unit_conservation_exact",
    }
)
_EXACT_PATH_TYPES = (Path, type(Path()))
_TEMP_NAME_LOCK = threading.Lock()
_ALLOWED_LEAN_AXIOMS = frozenset({"propext"})


# ---------------------------------------------------------------------------
# Strict Zone-B Zero-Float JSON, Rational & Digest Primitives
# ---------------------------------------------------------------------------

def validate_json_tree_iterative(obj: Any, max_depth: int = MAX_JSON_DEPTH) -> None:
    if type(max_depth) is not int or max_depth < 1 or max_depth > 256:
        raise S96Error("INVALID_MAX_DEPTH", "max_depth must be int in [1, 256]")
    stack: list[tuple[Any, int]] = [(obj, 0)]
    while stack:
        cur, depth = stack.pop()
        if depth > max_depth:
            raise S96Error("JSON_DEPTH_EXCEEDED", f"nesting depth > {max_depth}")
        t = type(cur)
        if t is dict:
            for k, v in cur.items():
                if type(k) is not str:
                    raise S96Error("NON_STR_KEY", "dict keys must be strict str")
                try:
                    k.encode("utf-8")
                except UnicodeEncodeError as exc:
                    raise S96Error("INVALID_UNICODE_STR", f"lone surrogate key: {exc}") from exc
                stack.append((v, depth + 1))
        elif t is list:
            for item in cur:
                stack.append((item, depth + 1))
        elif t is int:
            if cur.bit_length() > MAX_INT_BITS:
                raise S96Error("INT_BIT_LIMIT", f"int exceeds {MAX_INT_BITS} bits")
        elif t is str:
            try:
                cur.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise S96Error("INVALID_UNICODE_STR", f"lone surrogate str: {exc}") from exc
        elif t is bool or cur is None:
            continue
        else:
            raise S96Error("FORBIDDEN_JSON_TYPE", f"forbidden JSON value type: {t.__name__}")


def _no_dups_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise S96Error("DUPLICATE_JSON_KEY", f"duplicate key: {k}")
        out[k] = v
    return out


def _forbid_float(token: str) -> Any:
    raise S96Error("FLOAT_FORBIDDEN", f"float literal forbidden: {token}")


def _forbid_constant(token: str) -> Any:
    raise S96Error("NONFINITE_CONSTANT", f"non-finite constant forbidden: {token}")


def _parse_capped_int_token(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    if len(digits) > MAX_INT_DIGITS:
        raise S96Error("INT_DIGIT_LIMIT", f"integer token exceeds {MAX_INT_DIGITS} digits")
    val = int(token)
    if val.bit_length() > MAX_INT_BITS:
        raise S96Error("INT_BIT_LIMIT", f"integer token exceeds {MAX_INT_BITS} bits")
    return val


def parse_strict_json(text: str) -> Any:
    if type(text) is not str:
        raise S96Error("INVALID_JSON_TEXT", "JSON text must be strict str")
    try:
        encoded = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise S96Error("INVALID_UNICODE_STR", f"lone surrogate in JSON text: {exc}") from exc
    if len(encoded) > MAX_JSON_BYTES:
        raise S96Error("JSON_TOO_LARGE", f"JSON exceeds {MAX_JSON_BYTES} bytes")
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_no_dups_hook,
            parse_int=_parse_capped_int_token,
            parse_float=_forbid_float,
            parse_constant=_forbid_constant,
        )
    except S96Error:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise S96Error("JSON_DECODE_ERROR", f"invalid JSON: {exc}") from exc
    validate_json_tree_iterative(parsed)
    return parsed


def require_sha256_hex(val: Any, label: str) -> str:
    if type(val) is not str:
        raise S96Error("INVALID_DIGEST_TYPE", f"{label} must be strict str")
    if len(val) != 64:
        raise S96Error("INVALID_DIGEST_LEN", f"{label} must have length 64")
    if any(ch not in _HEX_LOWER for ch in val):
        raise S96Error("INVALID_DIGEST_HEX", f"{label} must be lowercase ASCII hex")
    return val


def exact_typed_equal(lhs: Any, rhs: Any) -> bool:
    """Iterative strict structural + exact-type equality (rejects bool/int swaps & subclasses)."""
    stack: list[tuple[Any, Any]] = [(lhs, rhs)]
    while stack:
        a, b = stack.pop()
        ta, tb = type(a), type(b)
        if ta is not tb:
            return False
        if ta is dict:
            if len(a) != len(b):
                return False
            for k, va in a.items():
                if k not in b:
                    return False
                stack.append((va, b[k]))
        elif ta is list:
            if len(a) != len(b):
                return False
            for va, vb in zip(a, b):
                stack.append((va, vb))
        elif a != b:
            return False
    return True


def _req_dict(obj: Any, expected_keys: frozenset[str], code: str) -> dict[str, Any]:
    require_ok(type(obj) is dict, code, f"{code}: expected strict dict")
    require_ok(frozenset(obj.keys()) == expected_keys, code, f"{code}: exact keys mismatch")
    return obj


def _req_int(obj: Any, code: str) -> int:
    require_ok(type(obj) is int, code, f"{code}: expected exact int")
    return obj


def _parse_rat_dict(obj: Any) -> Fraction:
    if type(obj) is not dict or frozenset(obj.keys()) != _RAT_KEYS:
        raise S96Error("BAD_RATIONAL_DICT", "rational dict must have exact keys {num, den}")
    num_v = obj["num"]
    den_v = obj["den"]
    require_ok(
        type(num_v) is int and type(den_v) is int and den_v > 0 and math.gcd(abs(num_v), den_v) == 1,
        "BAD_RATIONAL_DICT",
        "rational dict must have canonical coprime int num and positive int den",
    )
    return Fraction(num_v, den_v)


def _check_invariants(checks: list[tuple[bool, str]]) -> None:
    for ok, code in checks:
        require_ok(ok, code, f"semantic invariant failed: {code}")


def _audit_lora_metric(entry: Any, expect_starved: bool) -> None:
    d = _req_dict(entry, _LORA_METRIC_KEYS, "BAD_LORA_SCHEMA")
    m = _req_int(d["m"], "BAD_LORA_INV")
    n = _req_int(d["n"], "BAD_LORA_INV")
    r = _req_int(d["rank"], "BAD_LORA_INV")
    p_raw = _req_int(d["p_raw"], "BAD_LORA_INV")
    d_eff = _req_int(d["d_eff"], "BAD_LORA_INV")
    unr = _req_int(d["unreachable_dim"], "BAD_LORA_INV")
    eta = _parse_rat_dict(d["eta_alg_q"])
    ufrac = _parse_rat_dict(d["unreachable_frac_q"])
    min_d = min(m, n)
    require_ok(r > 0, "BAD_LORA_INV", "rank must be positive")
    require_ok(r <= min_d, "BAD_LORA_INV", "rank must be <= min(m, n)")
    require_ok(p_raw == r * (m + n), "BAD_LORA_INV", "p_raw mismatch")
    _check_invariants(
        [
            (d_eff == p_raw - r * r, "BAD_LORA_INV"),
            (eta == Fraction(d_eff, p_raw), "BAD_LORA_INV"),
            (unr == min_d - r, "BAD_LORA_INV"),
            (ufrac == Fraction(unr, min_d), "BAD_LORA_INV"),
            (d["unreachable_pct_dec"] == frac_to_dec_str(ufrac * 100, 2), "BAD_LORA_INV"),
            (d["rank_starved"] is expect_starved, "BAD_LORA_INV"),
            ((unr > 0) is expect_starved, "BAD_LORA_INV"),
        ]
    )


def _audit_nullspace_entry(entry: Any, expect_saturated: bool) -> None:
    d = _req_dict(entry, _NS_KEYS, "BAD_NS_SCHEMA")
    dim = _req_int(d["dim"], "BAD_NS_INV")
    br = _req_int(d["base_rank"], "BAD_NS_INV")
    ns = _req_int(d["nullspace_dim"], "BAD_NS_INV")
    raw_f = _parse_rat_dict(d["raw_forgetting_sq_q"])
    proj_f = _parse_rat_dict(d["projected_forgetting_sq_q"])
    proj_e = _parse_rat_dict(d["projected_update_energy_sq_q"])
    _check_invariants(
        [
            (br > 0, "BAD_NS_INV"),
            (br <= dim, "BAD_NS_INV"),
            (ns == dim - br, "BAD_NS_INV"),
            (raw_f > 0, "BAD_NS_INV"),
            (proj_f == 0, "BAD_NS_INV"),
            (d["exact_zero_forgetting"] is True, "BAD_NS_INV"),
            (d["nullspace_saturated"] is expect_saturated, "BAD_NS_INV"),
            ((ns == 0) is expect_saturated, "BAD_NS_INV"),
            ((proj_e == 0) if expect_saturated else (proj_e > 0), "BAD_NS_INV"),
        ]
    )


def _audit_roofline_entry(entry: Any, expect_full_fits: bool) -> None:
    d = _req_dict(entry, _ROOF_KEYS, "BAD_ROOF_SCHEMA")
    mod = _parse_rat_dict(d["model_gb_q"])
    vram = _parse_rat_dict(d["gpu_vram_gb_q"])
    ovf = _parse_rat_dict(d["full_resident_overflow_gb_q"])
    rat = _parse_rat_dict(d["model_over_vram_ratio_q"])
    svram = _parse_rat_dict(d["streamed_vram_gb_q"])
    cold = _parse_rat_dict(d["cold_experts_gb_q"])
    require_ok(vram > 0, "BAD_ROOF_INV", "gpu_vram_gb must be positive")
    _check_invariants(
        [
            (rat == mod / vram, "BAD_ROOF_INV"),
            (d["full_resident_fits"] is expect_full_fits, "BAD_ROOF_INV"),
            ((mod <= vram) is expect_full_fits, "BAD_ROOF_INV"),
            (ovf == max(Fraction(0), mod - vram), "BAD_ROOF_INV"),
            (svram > 0, "BAD_ROOF_INV"),
            (svram <= vram, "BAD_ROOF_INV"),
            (cold > 0, "BAD_ROOF_INV"),
            (cold < mod, "BAD_ROOF_INV"),
            (d["streamed_fits_gpu"] is True, "BAD_ROOF_INV"),
            (d["cold_fits_host_ram"] is True, "BAD_ROOF_INV"),
            (d["streaming_tier_feasible"] is True, "BAD_ROOF_INV"),
        ]
    )


def _audit_pillar1(p1: dict[str, Any]) -> None:
    qwen = p1["qwen25_05b_r16_starvation"]
    f3 = p1["s78_fig3_vproj_r128"]
    full = p1["s78_full_rank_r512"]
    _audit_lora_metric(qwen, True)
    _audit_lora_metric(f3, True)
    _audit_lora_metric(full, False)
    comm = _req_dict(p1["privileged_basis_commutator"], _COMM_KEYS, "BAD_P1_COMM")
    cons = _req_dict(p1["s78_fig7_unit_conservation"], _UNIT_CONS_KEYS, "BAD_P1_CONS")
    f_kb = _parse_rat_dict(cons["forgetting_kb_q"])
    l_kb = _parse_rat_dict(cons["learning_kb_q"])
    ratio = _parse_rat_dict(cons["forgetting_over_learning_q"])
    require_ok(l_kb == Fraction(229, 5), "BAD_P1_INV", "learning_kb mismatch")
    _check_invariants(
        [
            (p1["pillar_verified"] is True, "BAD_P1_INV"),
            (qwen["m"] == 896, "BAD_P1_INV"),
            (qwen["n"] == 896, "BAD_P1_INV"),
            (qwen["rank"] == 16, "BAD_P1_INV"),
            (f3["m"] == 512, "BAD_P1_INV"),
            (f3["n"] == 1024, "BAD_P1_INV"),
            (f3["rank"] == 128, "BAD_P1_INV"),
            (full["m"] == 512, "BAD_P1_INV"),
            (full["n"] == 1024, "BAD_P1_INV"),
            (full["rank"] == 512, "BAD_P1_INV"),
            (_parse_rat_dict(comm["anisotropic_comm_frob_sq_q"]) == Fraction(54, 1), "BAD_P1_INV"),
            (_parse_rat_dict(comm["isotropic_comm_frob_sq_q"]) == Fraction(0, 1), "BAD_P1_INV"),
            (comm["commutator_nonzero_under_anisotropy"] is True, "BAD_P1_INV"),
            (comm["commutator_zero_under_isotropy"] is True, "BAD_P1_INV"),
            (f_kb == Fraction(229, 5), "BAD_P1_INV"),
            (ratio == f_kb / l_kb, "BAD_P1_INV"),
            (cons["unit_conservation_exact"] is True, "BAD_P1_INV"),
        ]
    )


def _audit_pillar2(p2: dict[str, Any]) -> None:
    bf = _req_dict(p2["matched_budget_blockh4_butterfly"], _BF_KEYS, "BAD_P2_BF")
    hh = _req_dict(p2["privsparse_householder_isometry"], _HH_KEYS, "BAD_P2_HH")
    ns = _req_dict(p2["nullspace_projected_antiforgetting"], _NS_WRAP_KEYS, "BAD_P2_NS")
    hyb = _req_dict(p2["s95_bf16_ulp_diagnosis_and_hybrid_prereg"], _S95_HYB_KEYS, "BAD_P2_HYB")
    ns_r2 = ns["rank2_calibration_projection"]
    ns_sat = ns["law5_full_rank_saturation_control"]
    _audit_nullspace_entry(ns_r2, False)
    _audit_nullspace_entry(ns_sat, True)
    dim = _req_int(bf["dim"], "BAD_P2_INV")
    mr = _req_int(bf["matched_lora_rank"], "BAD_P2_INV")
    pb = _req_int(bf["matched_param_budget"], "BAD_P2_INV")
    r_lora = _req_int(bf["standard_lora_rank"], "BAD_P2_INV")
    r_bf = _req_int(bf["butterfly_rank"], "BAD_P2_INV")
    r_mix = _req_int(bf["butterfly_interleaved_rank"], "BAD_P2_INV")
    adv = _parse_rat_dict(bf["full_rank_advantage_q"])
    s42_gain = _parse_rat_dict(hh["s42_fisher_waterfilling_gain_q"])
    hh_dim = _req_int(hh["householder_dim"], "BAD_P2_INV")
    p_before = _parse_rat_dict(hh["probe_norm_sq_before_q"])
    p_after = _parse_rat_dict(hh["probe_norm_sq_after_q"])
    k2_hh = _parse_rat_dict(hh["householder_kappa2_q"])
    k2_sh = _parse_rat_dict(hh["s82_shear_kappa2_lower_q"])
    bfly_z = _parse_rat_dict(hyb["bf16_half_ulp_zero_frac_butterfly_q"])
    lora_z = _parse_rat_dict(hyb["bf16_half_ulp_zero_frac_lora_q"])
    ann_r = _parse_rat_dict(hyb["bf16_annihilation_ratio_q"])
    bh_d = _req_int(hyb["butterflyhead_proj_dim"], "BAD_P2_INV")
    bh_s = _req_int(hyb["butterflyhead_stages_s"], "BAD_P2_INV")
    bh_r = _req_int(hyb["butterflyhead_rank_r"], "BAD_P2_INV")
    bh_bp = _req_int(hyb["butterflyhead_bfly_params"], "BAD_P2_INV")
    bh_hp = _req_int(hyb["butterflyhead_head_params"], "BAD_P2_INV")
    bh_tp = _req_int(hyb["butterflyhead_total_params_per_proj"], "BAD_P2_INV")
    h_lr = _parse_rat_dict(hyb["butterflyhead_head_lr_q"])
    b_lr = _parse_rat_dict(hyb["butterflyhead_bfly_lr_q"])
    k_p = _req_int(hyb["s104_kronecker_rank2_head_params"], "BAD_P2_INV")
    require_ok(mr == 2, "BAD_P2_INV", "matched_lora_rank mismatch")
    require_ok(r_lora == mr, "BAD_P2_INV", "standard_lora_rank mismatch")
    require_ok(lora_z == Fraction(873, 10000), "BAD_P2_INV", "lora_zero_frac mismatch")
    require_ok(h_lr == Fraction(3, 10000), "BAD_P2_INV", "head_lr mismatch")
    require_ok(k_p == 3616, "BAD_P2_INV", "kronecker_params mismatch")
    _check_invariants(
        [
            (p2["pillar_verified"] is True, "BAD_P2_INV"),
            (dim == 8, "BAD_P2_INV"),
            (pb == 2 * mr * dim, "BAD_P2_INV"),
            (r_bf == dim, "BAD_P2_INV"),
            (r_mix == dim, "BAD_P2_INV"),
            (adv == Fraction(r_bf, r_lora), "BAD_P2_INV"),
            (bf["blockh4_exact_orthogonal"] is True, "BAD_P2_INV"),
            (_parse_rat_dict(bf["law5_unpermuted_cross_block_sq_q"]) == Fraction(0, 1), "BAD_P2_INV"),
            (_parse_rat_dict(bf["interleaved_cross_block_sq_q"]) == Fraction(660, 1), "BAD_P2_INV"),
            (bf["law5_locality_obstruction_verified"] is True, "BAD_P2_INV"),
            (bf["interleave_restores_mixing"] is True, "BAD_P2_INV"),
            (s42_gain == Fraction(263, 16), "BAD_P2_INV"),
            (hh_dim == 4, "BAD_P2_INV"),
            (_parse_rat_dict(hh["householder_det_q"]) == Fraction(-1, 1), "BAD_P2_INV"),
            (hh["householder_exact_orthogonal"] is True, "BAD_P2_INV"),
            (hh["householder_exact_involutive"] is True, "BAD_P2_INV"),
            (p_before == Fraction(30, 1), "BAD_P2_INV"),
            (p_before == p_after, "BAD_P2_INV"),
            (k2_hh == Fraction(1, 1), "BAD_P2_INV"),
            (k2_sh == Fraction(1309, 500), "BAD_P2_INV"),
            (hh["cures_s82_shear_blowup"] is True, "BAD_P2_INV"),
            (ns_r2["dim"] == 4, "BAD_NS_INV"),
            (ns_r2["base_rank"] == 2, "BAD_NS_INV"),
            (_parse_rat_dict(ns_r2["raw_forgetting_sq_q"]) == Fraction(46, 1), "BAD_NS_INV"),
            (_parse_rat_dict(ns_r2["projected_update_energy_sq_q"]) == Fraction(11, 1), "BAD_NS_INV"),
            (ns_sat["dim"] == 4, "BAD_NS_INV"),
            (ns_sat["base_rank"] == 4, "BAD_NS_INV"),
            (_parse_rat_dict(ns_sat["raw_forgetting_sq_q"]) == Fraction(29, 1), "BAD_NS_INV"),
            (_parse_rat_dict(hyb["bf16_half_ulp_threshold_q"]) == Fraction(1, 256), "BAD_P2_INV"),
            (bfly_z == Fraction(407, 500), "BAD_P2_INV"),
            (ann_r == bfly_z / lora_z, "BAD_P2_INV"),
            (hyb["bf16_annihilation_ratio_dec"] == frac_to_dec_str(ann_r, 4), "BAD_P2_INV"),
            (bh_d == 896, "BAD_P2_INV"),
            (bh_s == 8, "BAD_P2_INV"),
            (bh_r == 8, "BAD_P2_INV"),
            (bh_bp == bh_s * (bh_d + bh_d), "BAD_P2_INV"),
            (bh_hp == bh_r * (bh_d + bh_d), "BAD_P2_INV"),
            (bh_tp == bh_bp + bh_hp, "BAD_P2_INV"),
            (_req_int(hyb["butterflyhead_nullspace_top_k"], "BAD_P2_INV") == 32, "BAD_P2_INV"),
            (_parse_rat_dict(hyb["butterflyhead_frob_cap_frac_q"]) == Fraction(1, 50), "BAD_P2_INV"),
            (b_lr == Fraction(3, 1000), "BAD_P2_INV"),
            (_parse_rat_dict(hyb["butterflyhead_lr_ratio_q"]) == b_lr / h_lr, "BAD_P2_INV"),
            (_parse_rat_dict(hyb["s104_kronecker_compression_ratio_q"]) == Fraction(bh_hp, k_p), "BAD_P2_INV"),
            (_parse_rat_dict(hyb["pass_exact_all5_min_q"]) == Fraction(17, 30), "BAD_P2_INV"),
            (_parse_rat_dict(hyb["kill_exact_all5_max_q"]) == Fraction(2, 5), "BAD_P2_INV"),
            (_parse_rat_dict(hyb["pass_nll_retention_ratio_cap_q"]) == Fraction(2, 1), "BAD_P2_INV"),
            (_parse_rat_dict(hyb["pass_bf16_zero_frac_cap_q"]) == Fraction(7, 20), "BAD_P2_INV"),
            (_parse_rat_dict(hyb["pass_top16_energy_cap_q"]) == Fraction(3, 5), "BAD_P2_INV"),
            (_parse_rat_dict(hyb["pass_sigma_max_cap_q"]) == Fraction(7, 20), "BAD_P2_INV"),
            (_parse_rat_dict(hyb["pass_rel_frob_cap_q"]) == Fraction(1, 40), "BAD_P2_INV"),
            (_req_int(hyb["pass_peak_vram_cap_mib"], "BAD_P2_INV") == 7168, "BAD_P2_INV"),
            (hyb["exact_budget_parity_verified"] is True, "BAD_P2_INV"),
        ]
    )


def _audit_pillar3(p3: dict[str, Any]) -> None:
    cfg = _req_dict(p3["inkling2_config_exact"], _INK_CFG_KEYS, "BAD_P3_CFG")
    amp = _req_dict(p3["loop_core_adapter_amplification"], _LOOP_AMP_KEYS, "BAD_P3_AMP")
    m1h1 = _req_dict(p3["per_pass_quant_noise_and_m1h1_gate"], _M1H1_KEYS, "BAD_P3_M1H1")
    roof = _req_dict(p3["hardware_roofline_comparison"], _ROOF_WRAP_KEYS, "BAD_P3_ROOF")
    r3080 = roof["rtx3080_8gib"]
    w32 = roof["workstation_32gib"]
    _audit_roofline_entry(r3080, False)
    _audit_roofline_entry(w32, True)
    qwen_vf = _parse_rat_dict(roof["qwen25_05b_bf16_vram_frac_of_8gib_q"])
    h = _req_int(cfg["hidden_size"], "BAD_P3_INV")
    sh = _req_int(cfg["sqrt_hidden_size"], "BAD_P3_INV")
    nl = _req_int(cfg["num_hidden_layers"], "BAD_P3_INV")
    vs = _req_int(cfg["vocab_size"], "BAD_P3_INV")
    uvs = _req_int(cfg["unpadded_vocab_size"], "BAD_P3_INV")
    nah = _req_int(cfg["num_attention_heads"], "BAD_P3_INV")
    nkv = _req_int(cfg["num_key_value_heads"], "BAD_P3_INV")
    hd = _req_int(cfg["head_dim"], "BAD_P3_INV")
    llc = _req_int(cfg["local_layer_count"], "BAD_P3_INV")
    glc = _req_int(cfg["global_layer_count"], "BAD_P3_INV")
    sws = _req_int(cfg["sliding_window_size"], "BAD_P3_INV")
    mgs = _req_int(cfg["mlp_gate_softcap"], "BAD_P3_INV")
    mus = _req_int(cfg["mlp_up_softcap"], "BAD_P3_INV")
    rs = _req_int(cfg["route_scale"], "BAD_P3_INV")
    cs = _req_int(cfg["core_start"], "BAD_P3_INV")
    ce = _req_int(cfg["core_end"], "BAD_P3_INV")
    cl = _req_int(cfg["core_layers"], "BAD_P3_INV")
    np_ = _req_int(cfg["num_passes"], "BAD_P3_INV")
    gr = _req_int(cfg["gate_rank"], "BAD_P3_INV")
    eff = _req_int(cfg["effective_layers"], "BAD_P3_INV")
    ne = _req_int(cfg["n_routed_experts"], "BAD_P3_INV")
    ea = _req_int(cfg["num_experts_per_tok"], "BAD_P3_INV")
    inter = _req_int(cfg["intermediate_size"], "BAD_P3_INV")
    mtp_bs = _req_int(cfg["mtp_block_size"], "BAD_P3_INV")
    mtp_mr = _req_int(cfg["mtp_markov_rank"], "BAD_P3_INV")
    mtp_ids = cfg["mtp_target_layer_ids"]
    require_ok(type(mtp_ids) is list, "BAD_P3_INV", "mtp_target_layer_ids must be strict list")
    for tid in mtp_ids:
        _req_int(tid, "BAD_P3_INV")
    rm_tot = _parse_rat_dict(cfg["readme_total_params_b_q"])
    rm_phys = _parse_rat_dict(cfg["readme_physical_active_b_q"])
    rm_eff = _parse_rat_dict(cfg["readme_effective_active_b_q"])
    rm_rat = _parse_rat_dict(cfg["readme_effective_over_physical_active_q"])
    c_per = _req_int(amp["gate_adapter_params_per_core_layer"], "BAD_P3_INV")
    c_tot = _req_int(amp["core_adapter_total_params"], "BAD_P3_INV")
    nl_eq = _req_int(amp["nonloop_equivalent_params"], "BAD_P3_INV")
    rho = _parse_rat_dict(amp["s76_contractive_rho_q"])
    err3 = _parse_rat_dict(amp["s76_3pass_error_bound_q"])
    div3 = _parse_rat_dict(amp["divergent_3pass_error_q"])
    g3_s76 = _parse_rat_dict(m1h1["s76_g3_quant_amp_q"])
    rho_hi = _parse_rat_dict(m1h1["high_rho_q"])
    rho3_hi = _parse_rat_dict(m1h1["high_rho_3pass_init_q"])
    g3_hi = _parse_rat_dict(m1h1["high_rho_g3_quant_amp_q"])
    thr_lo_r = _parse_rat_dict(m1h1["threshold_lo_rho_q"])
    thr_lo_g = _parse_rat_dict(m1h1["threshold_lo_g3_q"])
    thr_hi_r = _parse_rat_dict(m1h1["threshold_hi_rho_q"])
    thr_hi_g = _parse_rat_dict(m1h1["threshold_hi_g3_q"])
    drift_cap = _parse_rat_dict(m1h1["m1h1_max_drift_ratio_delta3_over_delta1_ctrl_q"])
    require_ok(h == 2304, "BAD_P3_INV", "hidden_size mismatch")
    require_ok(sh == 48, "BAD_P3_INV", "sqrt_hidden_size mismatch")
    require_ok(nl == 24, "BAD_P3_INV", "num_hidden_layers mismatch")
    require_ok(ne == 128, "BAD_P3_INV", "n_routed_experts mismatch")
    require_ok(np_ == 3, "BAD_P3_INV", "num_passes mismatch")
    require_ok(rm_phys == Fraction(17, 5), "BAD_P3_INV", "readme_physical_active_b_q mismatch")
    require_ok(rho == Fraction(1, 4), "BAD_P3_INV", "s76_contractive_rho_q mismatch")
    require_ok(err3 == rho**np_, "BAD_P3_INV", "s76_3pass_error_bound_q mismatch")
    _check_invariants(
        [
            (p3["pillar_verified"] is True, "BAD_P3_INV"),
            (vs == 201024, "BAD_P3_INV"),
            (uvs == 200058, "BAD_P3_INV"),
            (nah == 24, "BAD_P3_INV"),
            (nkv == 8, "BAD_P3_INV"),
            (hd == 128, "BAD_P3_INV"),
            (llc == 20, "BAD_P3_INV"),
            (glc == nl - llc, "BAD_P3_INV"),
            (sws == 1024, "BAD_P3_INV"),
            (ea == 8, "BAD_P3_INV"),
            (inter == 1152, "BAD_P3_INV"),
            (mgs == 4, "BAD_P3_INV"),
            (mus == 25, "BAD_P3_INV"),
            (rs == 8, "BAD_P3_INV"),
            (cs == 6, "BAD_P3_INV"),
            (ce == 18, "BAD_P3_INV"),
            (cl == ce - cs, "BAD_P3_INV"),
            (gr == 64, "BAD_P3_INV"),
            (mtp_bs == 8, "BAD_P3_INV"),
            (mtp_mr == 256, "BAD_P3_INV"),
            (mtp_ids == [5, 23, 41, 48], "BAD_P3_INV"),
            (rm_tot == Fraction(132, 5), "BAD_P3_INV"),
            (rm_eff == Fraction(27, 5), "BAD_P3_INV"),
            (rm_rat == rm_eff / rm_phys, "BAD_P3_INV"),
            (_parse_rat_dict(r3080["model_gb_q"]) == Fraction(20, 1), "BAD_ROOF_INV"),
            (_parse_rat_dict(r3080["gpu_vram_gb_q"]) == Fraction(8, 1), "BAD_ROOF_INV"),
            (_parse_rat_dict(r3080["streamed_vram_gb_q"]) == Fraction(8, 1), "BAD_ROOF_INV"),
            (_parse_rat_dict(r3080["cold_experts_gb_q"]) == Fraction(27, 2), "BAD_ROOF_INV"),
            (_parse_rat_dict(w32["model_gb_q"]) == Fraction(20, 1), "BAD_ROOF_INV"),
            (_parse_rat_dict(w32["gpu_vram_gb_q"]) == Fraction(32, 1), "BAD_ROOF_INV"),
            (_parse_rat_dict(w32["streamed_vram_gb_q"]) == Fraction(8, 1), "BAD_ROOF_INV"),
            (_parse_rat_dict(w32["cold_experts_gb_q"]) == Fraction(27, 2), "BAD_ROOF_INV"),
            (qwen_vf == Fraction(247, 2048), "BAD_P3_INV"),
            (roof["qwen25_05b_bf16_vram_pct_dec"] == frac_to_dec_str(qwen_vf * 100, 2), "BAD_P3_INV"),
            (eff == cs + np_ * cl + (nl - ce), "BAD_P3_INV"),
            (_parse_rat_dict(cfg["depth_reuse_ratio_q"]) == Fraction(eff, nl), "BAD_P3_INV"),
            (_parse_rat_dict(cfg["gate_rank_over_sqrt_hidden_q"]) == Fraction(gr, sh), "BAD_P3_INV"),
            (_parse_rat_dict(cfg["active_expert_frac_q"]) == Fraction(ea, ne), "BAD_P3_INV"),
            (_parse_rat_dict(cfg["intermediate_over_hidden_q"]) == Fraction(inter, h), "BAD_P3_INV"),
            (c_per == 2 * gr * h, "BAD_P3_INV"),
            (c_tot == cl * c_per, "BAD_P3_INV"),
            (nl_eq == np_ * c_tot, "BAD_P3_INV"),
            (_parse_rat_dict(amp["effective_layer_leverage_q"]) == Fraction(np_, 1), "BAD_P3_INV"),
            (div3 == Fraction(5, 4) ** np_, "BAD_P3_INV"),
            (amp["contractive_3pass_stable"] is True, "BAD_P3_INV"),
            (g3_s76 == sum((rho**i for i in range(np_)), Fraction(0)), "BAD_P3_INV"),
            (m1h1["s76_g3_quant_amp_dec"] == frac_to_dec_str(g3_s76, 4), "BAD_P3_INV"),
            (_parse_rat_dict(m1h1["s76_g3_over_rho3_ratio_q"]) == g3_s76 / err3, "BAD_P3_INV"),
            (m1h1["s76_passes_m1h1_drift_gate"] is True, "BAD_P3_INV"),
            (rho_hi == Fraction(3, 4), "BAD_P3_INV"),
            (rho3_hi == rho_hi**np_, "BAD_P3_INV"),
            (g3_hi == sum((rho_hi**i for i in range(np_)), Fraction(0)), "BAD_P3_INV"),
            (m1h1["high_rho_g3_quant_amp_dec"] == frac_to_dec_str(g3_hi, 4), "BAD_P3_INV"),
            (m1h1["high_rho_contracts_init_but_kills_m1h1"] is True, "BAD_P3_INV"),
            (thr_lo_r == Fraction(3, 5), "BAD_P3_INV"),
            (thr_lo_g == sum((thr_lo_r**i for i in range(np_)), Fraction(0)), "BAD_P3_INV"),
            (thr_hi_r == Fraction(5, 8), "BAD_P3_INV"),
            (thr_hi_g == sum((thr_hi_r**i for i in range(np_)), Fraction(0)), "BAD_P3_INV"),
            (drift_cap == Fraction(2, 1), "BAD_P3_INV"),
            (_parse_rat_dict(m1h1["m1h1_max_rel_l2_drift_delta3_q"]) == Fraction(1, 20), "BAD_P3_INV"),
            (m1h1["requires_unique_layer_fp_baseline"] is True, "BAD_P3_INV"),
            (m1h1["requires_single_pass_nvfp4_control"] is True, "BAD_P3_INV"),
        ]
    )


def _audit_pillar4(p4: dict[str, Any]) -> None:
    require_ok(p4["inkling_spec_count"] == len(INKLING_SPEC_MANIFEST), "BAD_SPEC_COUNT", "inkling_spec_count mismatch")
    specs = p4["inkling_spec_manifest"]
    require_ok(type(specs) is list and len(specs) == len(INKLING_SPEC_MANIFEST), "BAD_SPEC_LIST", "inkling_spec_manifest mismatch")
    for entry, (exp_fn, exp_sha) in zip(specs, INKLING_SPEC_MANIFEST):
        ed = _req_dict(entry, _SPEC_ENTRY_KEYS, "BAD_SPEC_ENTRY")
        e_sha = require_sha256_hex(ed["sha256"], "inkling_spec_manifest.sha256")
        _check_invariants(
            [
                (ed["filename"] == exp_fn, "BAD_SPEC_PIN"),
                (hmac.compare_digest(e_sha, exp_sha), "BAD_SPEC_PIN"),
            ]
        )
    require_ok(
        p4["upstream_corpus_count"] == len(UPSTREAM_CERT_MANIFEST),
        "BAD_CORPUS_COUNT",
        "upstream_corpus_count mismatch",
    )
    manifest = p4["upstream_cert_manifest"]
    require_ok(
        type(manifest) is list and len(manifest) == len(UPSTREAM_CERT_MANIFEST),
        "BAD_MANIFEST_LIST",
        "upstream_cert_manifest length mismatch",
    )
    for entry, (exp_tid, exp_rel, exp_sha) in zip(manifest, UPSTREAM_CERT_MANIFEST):
        ed = _req_dict(entry, _MANIFEST_ENTRY_KEYS, "BAD_MANIFEST_ENTRY")
        e_sha = require_sha256_hex(ed["sha256"], "upstream_cert_manifest.sha256")
        _check_invariants(
            [
                (ed["track_id"] == exp_tid, "BAD_MANIFEST_PIN"),
                (ed["rel_path"] == exp_rel, "BAD_MANIFEST_PIN"),
                (hmac.compare_digest(e_sha, exp_sha), "BAD_MANIFEST_PIN"),
            ]
        )
    lean_cert = _req_dict(p4["lean4_certificate"], _LEAN_CERT_KEYS, "BAD_LEAN_CERT_SCHEMA")
    lean_sha = require_sha256_hex(lean_cert["sha256"], "lean4_certificate.sha256")
    _check_invariants(
        [
            (lean_cert["file"] == LEAN_FILE_NAME, "BAD_LEAN_PIN"),
            (hmac.compare_digest(lean_sha, LEAN_FILE_SHA256), "BAD_LEAN_PIN"),
            (lean_cert["theorem_count"] == len(LEAN_THEOREMS), "BAD_THEOREM_COUNT"),
            (lean_cert["theorems"] == list(LEAN_THEOREMS), "BAD_THEOREM_LIST"),
            (lean_cert["allowed_axioms"] == ["propext"], "BAD_ALLOWED_AXIOMS"),
        ]
    )
    nov = _req_dict(p4["novelty_honesty_law4"], _NOVELTY_KEYS, "BAD_NOVELTY_SCHEMA")
    _check_invariants(
        [
            (nov["novelty_tier"] == "N1", "BAD_NOVELTY_CLAIMS"),
            (nov["n0_prior_art_anchored"] is True, "BAD_NOVELTY_CLAIMS"),
            (nov["n1_exact_synthesis_verified"] is True, "BAD_NOVELTY_CLAIMS"),
            (nov["n2_claims"] == 0, "BAD_NOVELTY_CLAIMS"),
        ]
    )


def secondary_audit_payload(payload: Any) -> dict[str, Any]:
    """Fail-closed in-memory Zone-B secondary auditor verifying schemas & algebraic invariants across all 4 pillars."""
    validate_json_tree_iterative(payload)
    if type(payload) is not dict:
        raise S96Error("BAD_PAYLOAD_TYPE", "payload must be strict dict")
    if frozenset(payload.keys()) != _PAYLOAD_KEYS:
        raise S96Error("BAD_PAYLOAD_KEYS", "payload keys mismatch")

    stack: list[Any] = [payload]
    while stack:
        cur = stack.pop()
        if type(cur) is dict:
            if "num" in cur or "den" in cur:
                _parse_rat_dict(cur)
            for k, v in cur.items():
                if type(v) is bool:
                    require_ok(k in _PAYLOAD_BOOL_KEYS, "UNEXPECTED_BOOL_FIELD", f"unexpected bool at {k}")
                elif k == "sha256":
                    require_sha256_hex(v, "sha256")
                elif type(v) in (dict, list):
                    stack.append(v)
        else:
            for item in cur:
                require_ok(type(item) is not bool, "UNEXPECTED_BOOL_ITEM", "unexpected bool in payload list")
                if type(item) in (dict, list):
                    stack.append(item)

    _audit_pillar1(_req_dict(payload["pillar1_lora_three_bottlenecks"], _P1_KEYS, "BAD_P1_SCHEMA"))
    _audit_pillar2(_req_dict(payload["pillar2_beyond_lora_architectures"], _P2_KEYS, "BAD_P2_SCHEMA"))
    _audit_pillar3(_req_dict(payload["pillar3_inkling2_loop_and_roofline"], _P3_KEYS, "BAD_P3_SCHEMA"))
    _audit_pillar4(_req_dict(payload["pillar4_provenance_and_lean4"], _P4_KEYS, "BAD_P4_SCHEMA"))
    return payload


def verify_certificate_dict(cert: Any, *, full_replay: bool = True) -> dict[str, Any]:
    """Fail-closed in-memory Zone-B verifier supporting FR1 (full_replay=True) and FR0 (full_replay=False)."""
    require_ok(type(full_replay) is bool, "INVALID_FULL_REPLAY", "full_replay must be strict bool")
    validate_json_tree_iterative(cert)
    if type(cert) is not dict:
        raise S96Error("NON_OBJECT_ROOT", "certificate root must be strict dict")
    if frozenset(cert.keys()) != _CERT_KEYS:
        raise S96Error("BAD_CERT_KEYS", "certificate keys mismatch")
    if cert["schema"] != CERT_SCHEMA:
        raise S96Error("BAD_SCHEMA", "schema mismatch")
    if cert["track_id"] != CERT_TRACK_ID:
        raise S96Error("BAD_TRACK_ID", "track_id mismatch")

    payload = cert["payload"]
    if type(payload) is not dict:
        raise S96Error("BAD_PAYLOAD_TYPE", "payload must be strict dict")

    claimed_p_sha = require_sha256_hex(cert["payload_sha256"], "payload_sha256")
    claimed_c_sha = require_sha256_hex(cert["certificate_sha256"], "certificate_sha256")

    calc_p_sha = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    if not hmac.compare_digest(claimed_p_sha, calc_p_sha):
        raise S96Error("PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")

    envelope = {
        "schema": cert["schema"],
        "track_id": cert["track_id"],
        "payload_sha256": claimed_p_sha,
        "payload": payload,
    }
    calc_c_sha = hashlib.sha256(canonical_json_bytes(envelope)).hexdigest()
    if not hmac.compare_digest(claimed_c_sha, calc_c_sha):
        raise S96Error("CERT_SHA_MISMATCH", "certificate_sha256 mismatch")

    secondary_audit_payload(payload)

    if full_replay:
        expected = build_certificate()
        if not exact_typed_equal(payload, expected["payload"]):
            raise S96Error("PAYLOAD_ORACLE_MISMATCH", "payload disagrees with exact-Q oracle")
        if not hmac.compare_digest(claimed_c_sha, expected["certificate_sha256"]):
            raise S96Error("ORACLE_CERT_SHA_MISMATCH", "certificate_sha256 disagrees with exact-Q oracle")
    return cert


def audit_certificate_object(cert: Any) -> dict[str, Any]:
    """Fail-closed in-memory Zone-B hardened full-replay auditor."""
    return verify_certificate_dict(cert, full_replay=True)


# ---------------------------------------------------------------------------
# Hardened dir_fd File I/O (TOCTOU, Symlink, FIFO, Hardlink, 0o600 Atomic Write)
# ---------------------------------------------------------------------------

def _validate_path(path: Any) -> None:
    if type(path) not in _EXACT_PATH_TYPES:
        raise S96Error("INVALID_PATH_TYPE", "path must be concrete pathlib.Path")
    raw = str(path)
    try:
        raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise S96Error("INVALID_UNICODE_STR", f"lone surrogate in path: {exc}") from exc
    if "\x00" in raw:
        raise S96Error("INVALID_PATH_NUL", "NUL byte forbidden in path")


def _is_symlink_at(dfd: int, name: str) -> bool:
    try:
        return stat.S_ISLNK(os.lstat(name, dir_fd=dfd).st_mode)
    except OSError:
        return False


def _check_pwd_no_symlinks() -> None:
    pwd = os.environ.get("PWD")
    if pwd is None or not os.path.isabs(pwd):
        return
    try:
        pwd.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise S96Error("INVALID_UNICODE_STR", f"lone surrogate in PWD: {exc}") from exc
    cur_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in Path(pwd).parts[1:]:
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if _is_symlink_at(cur_fd, comp):
                    raise S96Error("SYMLINK_ANCESTOR_FORBIDDEN", f"symlink in PWD: {comp}") from exc
                return
            os.close(cur_fd)
            cur_fd = nxt
    finally:
        os.close(cur_fd)


def _open_parent_dir_fd(path: Path) -> tuple[int, str]:
    _validate_path(path)
    is_abs = path.is_absolute()
    if not is_abs:
        _check_pwd_no_symlinks()
    parts = path.parts[1:] if is_abs else path.parts
    if len(parts) == 0 or parts[-1] == "..":
        raise S96Error("INVALID_PATH", "path must name a regular file")
    ancestors, leaf = parts[:-1], parts[-1]
    cur_fd = os.open("/" if is_abs else ".", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in ancestors:
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if _is_symlink_at(cur_fd, comp):
                    raise S96Error("SYMLINK_ANCESTOR_FORBIDDEN", f"symlink ancestor: {comp}") from exc
                raise S96Error("PARENT_DIR_ERROR", f"cannot open ancestor {comp}: {exc}") from exc
            os.close(cur_fd)
            cur_fd = nxt
        return cur_fd, leaf
    except BaseException:
        os.close(cur_fd)
        raise


def read_regular_file_bytes(path: Path, *, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    dir_fd, leaf = _open_parent_dir_fd(path)
    fd = -1
    try:
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise S96Error("SYMLINK_FORBIDDEN", f"symlink forbidden: {path}") from exc
            raise S96Error("FILE_READ_ERROR", f"cannot open {path}: {exc}") from exc
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise S96Error("NOT_REGULAR_FILE", f"not a regular file: {path}")
        if st.st_nlink != 1:
            raise S96Error("HARDLINK_FORBIDDEN", f"hardlink forbidden (st_nlink={st.st_nlink})")
        if st.st_size > max_bytes:
            raise S96Error("FILE_TOO_LARGE", f"file exceeds {max_bytes} bytes")
        chunks: list[bytes] = []
        total = 0
        while True:
            try:
                chunk = os.read(fd, _READ_CHUNK_BYTES)
            except OSError as exc:
                raise S96Error("FILE_READ_ERROR", f"read error on {path}: {exc}") from exc
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise S96Error("FILE_TOO_LARGE", f"stream exceeded {max_bytes} bytes")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(dir_fd)


def write_atomic_0600_bytes(path: Path, data: bytes) -> None:
    dir_fd, leaf = _open_parent_dir_fd(path)
    tmp_name = ""
    fd = -1
    try:
        if _is_symlink_at(dir_fd, leaf):
            raise S96Error("SYMLINK_FORBIDDEN", f"symlink target forbidden: {path}")
        try:
            st_existing = os.lstat(leaf, dir_fd=dir_fd)
            if not stat.S_ISREG(st_existing.st_mode):
                raise S96Error("NOT_REGULAR_FILE", f"target is not a regular file: {path}")
            if st_existing.st_nlink > 1:
                raise S96Error("HARDLINK_FORBIDDEN", f"target hardlink forbidden: {path}")
        except FileNotFoundError:
            pass
        with _TEMP_NAME_LOCK:
            tmp_name = f".{leaf}.tmp.{secrets.token_hex(8)}"
            fd = os.open(
                tmp_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK,
                0o600,
                dir_fd=dir_fd,
            )
        os.fchmod(fd, 0o600)
        view = memoryview(data)
        written = 0
        while written < len(data):
            n = os.write(fd, view[written:])
            if n <= 0:
                raise S96Error("FILE_WRITE_ERROR", "short zero write")
            written += n
        os.fsync(fd)
        st_tmp = os.fstat(fd)
        if st_tmp.st_nlink != 1:
            raise S96Error("HARDLINK_FORBIDDEN", "temp file gained extra hardlink")
        os.close(fd)
        fd = -1
        os.replace(tmp_name, leaf, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        tmp_name = ""
        os.fsync(dir_fd)
    except S96Error:
        raise
    except OSError as exc:
        raise S96Error("FILE_WRITE_ERROR", f"atomic write failed: {exc}") from exc
    finally:
        if fd >= 0:
            os.close(fd)
        if tmp_name:
            try:
                os.unlink(tmp_name, dir_fd=dir_fd)
            except OSError:
                pass
        os.close(dir_fd)


def check_certificate_file(path: Path) -> dict[str, Any]:
    raw = read_regular_file_bytes(path, max_bytes=MAX_JSON_BYTES)
    if b"\r" in raw:
        raise S96Error("CRLF_FORBIDDEN", "CR/CRLF bytes forbidden in canonical certificate")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise S96Error("INVALID_UTF8", f"invalid UTF-8: {exc}") from exc
    parsed = parse_strict_json(text)
    cert = audit_certificate_object(parsed)
    expected_bytes = canonical_json_bytes(cert) + b"\n"
    if raw != expected_bytes:
        raise S96Error("NONCANONICAL_BYTES", "certificate file bytes are not canonical LF-terminated JSON")
    return cert


def verify_upstream_manifest(exp_root: Path) -> dict[str, Any]:
    """Fail-closed verification of all 10 pinned upstream certificate SHA-256s on disk."""
    _validate_path(exp_root)
    verified = 0
    for tid, rel, expected_sha in UPSTREAM_CERT_MANIFEST:
        raw = read_regular_file_bytes(exp_root / rel, max_bytes=MAX_JSON_BYTES)
        actual_sha = hashlib.sha256(raw).hexdigest()
        require_ok(
            hmac.compare_digest(actual_sha, expected_sha),
            "UPSTREAM_SHA_MISMATCH",
            f"upstream certificate SHA mismatch for {tid}",
        )
        verified += 1
    return {
        "status": "UPSTREAM_VERIFIED",
        "tracks_verified": verified,
        "expected_tracks": len(UPSTREAM_CERT_MANIFEST),
    }


def verify_inkling_specs(spec_dir: Path) -> dict[str, Any]:
    """Fail-closed verification of both pinned Inkling-2-Mini local spec SHA-256s on disk."""
    _validate_path(spec_dir)
    verified = 0
    for fn, expected_sha in INKLING_SPEC_MANIFEST:
        raw = read_regular_file_bytes(spec_dir / fn, max_bytes=MAX_JSON_BYTES)
        actual_sha = hashlib.sha256(raw).hexdigest()
        require_ok(
            hmac.compare_digest(actual_sha, expected_sha),
            "INKLING_SPEC_SHA_MISMATCH",
            f"Inkling spec SHA mismatch for {fn}",
        )
        verified += 1
    return {
        "status": "INKLING_SPECS_VERIFIED",
        "specs_verified": verified,
        "expected_specs": len(INKLING_SPEC_MANIFEST),
    }


# ---------------------------------------------------------------------------
# R12 Static Lean 4 Scanner + Live Scrubbed Lean 4.36.0 --stdin Axiom Verifier
# ---------------------------------------------------------------------------

_LEAN4_HARD_LINE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsorry\b"), "LEAN4_SORRY"),
    (re.compile(r"\badmit\b"), "LEAN4_ADMIT"),
    (re.compile(r"(?<!\.)\baxiom\b"), "LEAN4_AXIOM"),
    (re.compile(r"(?<!\.)\bunsafe\b"), "LEAN4_UNSAFE"),
    (re.compile(r"(?<!\.)\bopaque\b"), "LEAN4_OPAQUE"),
    (re.compile(r"(?<!\.)\b(?:dbg_trace|dbg_sleep|dbg_stack_trace)\b|\b(?:dbgTrace|dbgTraceVal|dbgTraceIfShared|dbgSleep|dbgStackTrace)\b"), "LEAN4_DBG_TRACE"),
    (re.compile(r"(?<!\.)\b(?:panic!|unreachable!)(?![\w'!?])|\bpanicWithPosWithDecl\b"), "LEAN4_PANIC_ESCAPE"),
    (re.compile(r"\bnative_decide\b"), "LEAN4_NATIVE_DECIDE"),
    (re.compile(r"\bbv_decide\b"), "LEAN4_BV_DECIDE"),
    (re.compile(r"\bsorryAx\b"), "LEAN4_SORRY_AX"),
    (re.compile(r"\bLean\.Meta\.mkSorry\b|\bmkSorry\b"), "LEAN4_MK_SORRY"),
    (re.compile(r"\bLean\.ofReduceBool\b|\bofReduceBool\b"), "LEAN4_OF_REDUCE_BOOL"),
    (re.compile(r"\bLean\.ofReduceNat\b|\bofReduceNat\b"), "LEAN4_OF_REDUCE_NAT"),
    (re.compile(r"\bLean\.trustCompiler\b|\btrustCompiler\b"), "LEAN4_TRUST_COMPILER"),
    (re.compile(r"\bLean\.(?:Elab|Meta|Core|Environment|Kernel)\b"), "LEAN4_LEAN_META_API"),
)
_LEAN4_PARTIAL_DECL_RE = re.compile(r"(?<!\.)\bpartial\s+(?:def|instance|abbrev)\b", flags=re.DOTALL)
_LEAN4_GUILLEMET_RE = re.compile(r"«([A-Za-z_][A-Za-z0-9_']*)»")
_LEAN4_SIMPLE_GUILLEMET_RE = re.compile(r"\A[A-Za-z_][A-Za-z0-9_']*\Z")
_LEAN4_DEBUG_RE = re.compile(
    r"\b(?:debug\s*\.\s*(?:skipKernelTC|byAsSorry|proofAsSorry|terminalTacticsAsSorry)|warn\s*\.\s*sorry)\b",
    flags=re.DOTALL,
)
_LEAN4_PRINT_KW = (
    "def|theorem|lemma|axiom|inductive|structure|class|instance|opaque|abbrev|example|"
    "namespace|section|end|open|variable|universe|import|set_option|attribute|"
    "local|scoped|private|protected|noncomputable|partial|unsafe|meta|where|by|in|let|have"
)
_LEAN4_SPOOF_RE = re.compile(
    r"#(?:eval!?(?![\w'!?])|reduce(?![\w'!?])|exit(?![\w'!?])|guard_msgs(?![\w'!?])|guard(?![\w'!?])|"
    r"print(?![\w'!?])(?!\s+axioms[ \t]+(?!(?:" + _LEAN4_PRINT_KW + r")(?![\w'!?]))[A-Za-z_]))"
    r"|(?<!\.)\b(?:run_cmd|run_meta|initialize|builtin_initialize)\b",
    flags=re.DOTALL,
)
_LEAN4_IMPORT_RE = re.compile(
    r"(?:^|\n)[ \t]*(?:(?:public|private|meta)\s+)*import\s+([A-Za-z0-9_.]+)",
    flags=re.DOTALL,
)
_LEAN4_ATTR_OPEN_RE = re.compile(r"(?:@|(?<!\.)\battribute\s*)\[", flags=re.DOTALL)
_LEAN4_HARD_ATTR_RE = re.compile(
    r"\b(extern|implemented_by|csimp|export|init|builtin_init|term_elab|command_elab|tactic|macro|macro_rules)\b"
)
_LEAN4_META_SYNTAX_RE = re.compile(
    r"(?<!\.)\b(?:syntax|macro_rules|macro|elab|elab_rules|declare_syntax_cat|notation|prefix|infixl|infixr|infix|postfix)\b"
)
_LEAN4_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_LEAN4_INTERP_BANG_WORDS = frozenset(
    ("s", "f", "m", "v", "println", "reportIssue", "reportDbgIssue", "reportEMatchIssue")
)
_LEAN4_INTERP_KEYWORDS = frozenset(("dbg_trace", "throwError"))
_LEAN4_DECIDE_KW_RE = re.compile(r"\bdecide\b")
_LEAN4_FLAG_TOK_RE = re.compile(r"[+-][A-Za-z0-9_]+")
_LEAN4_OPT_PREFIX_RE = re.compile(r"\s*([A-Za-z0-9_]+)\s*:=")
_LEAN4_CONFIG_NATIVE_RE = re.compile(r"\bnative\b(?:\s*:=\s*([^},]*))?")
_LEAN4_CONFIG_WITH_RE = re.compile(r"\bwith\b")
_LEAN4_DECIDE_CFG_BIND_RE = re.compile(
    r"\b(?:DecideConfig|Decide\.Config)\b[ \t)]*:=\s*(?:\(\s*)*\{[^}{]*\bnative\s*:=\s*([^}{,]*)(?:,[^}{]*)?\}"
    r"|\{[^}{]*\bnative\s*:=\s*([^}{,]*)(?:,[^}{]*)?\}\s*:\s*(?:[A-Za-z_][A-Za-z0-9_]*\.)*(?:DecideConfig|Decide\.Config)\b",
    flags=re.DOTALL,
)
_LEAN4_AXIOM_OUT_RE = re.compile(
    r"^'([^']+)'\s+(?:does not depend on any axioms|depends on axioms:\s*\[([^\]]*)\])$"
)


def _is_lean4_ident_prev(source: str, pos: int) -> bool:
    if pos < 0:
        return False
    ch = source[pos]
    if ch.isalnum() or ch in "_.'":
        return True
    if ch in "!?":
        for k in range(pos - 1, -1, -1):
            if source[k] not in "!?":
                return source[k].isalnum() or source[k] in "_'"
        return False
    return False


def _match_lean4_char_literal_end(source: str, i: int, n: int) -> int | None:
    """Return end index of a Lean 4 Char literal starting at source[i] == "'", or None."""
    if i + 2 < n and source[i + 1] not in ("\\", "'") and source[i + 2] == "'":
        return i + 3
    if i + 3 < n and source[i + 1] == "\\":
        esc = source[i + 2]
        if source[i + 3] == "'" and esc != "\n":
            return i + 4
        if (
            esc == "x"
            and i + 5 < n
            and source[i + 5] == "'"
            and all(c in _LEAN4_HEX_DIGITS for c in source[i + 3 : i + 5])
        ):
            return i + 6
        if (
            esc == "u"
            and i + 7 < n
            and source[i + 7] == "'"
            and all(c in _LEAN4_HEX_DIGITS for c in source[i + 3 : i + 7])
        ):
            return i + 8
    return None


def _strip_lean4_r10(source: str) -> tuple[str, list[str]]:
    """R10+ Lean 4 comment/char/string/raw-string/spaced-interp/unknown-bang stripper."""
    out: list[str] = []
    errors: list[str] = []
    i = 0
    n = len(source)
    depth = 0
    in_str = False
    in_interp = False
    pending_interp = False
    in_ident = False
    interp_stack: list[int] = []
    raw_hashes = -1
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if depth > 0:
            in_ident = False
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
        if raw_hashes >= 0:
            in_ident = False
            close_seq = '"' + ("#" * raw_hashes)
            if source.startswith(close_seq, i):
                out.append(" " * len(close_seq))
                i += len(close_seq)
                raw_hashes = -1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if in_str:
            in_ident = False
            if ch == "\\":
                out.append(" \n" if nxt == "\n" else "  ")
                i += 2
            elif ch == '"':
                in_str = False
                out.append(" ")
                i += 1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if in_interp:
            in_ident = False
            if ch == "\\":
                out.append(" \n" if nxt == "\n" else "  ")
                i += 2
            elif ch == "{":
                interp_stack.append(1)
                in_interp = False
                out.append(" ")
                i += 1
            elif ch == '"':
                in_interp = False
                out.append(" ")
                i += 1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if ch == "/" and nxt == "-":
            depth = 1
            in_ident = False
            out.append("  ")
            i += 2
            continue
        if ch == "-" and nxt == "-":
            in_ident = False
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch.isspace():
            in_ident = False
            out.append(ch)
            i += 1
            continue
        if ch != '"':
            pending_interp = False
        if interp_stack:
            if ch == "{":
                in_ident = False
                interp_stack[-1] += 1
                out.append(ch)
                i += 1
                continue
            if ch == "}":
                in_ident = False
                interp_stack[-1] -= 1
                out.append(ch)
                i += 1
                if interp_stack[-1] == 0:
                    interp_stack.pop()
                    in_interp = True
                continue
        if ch == '"':
            in_ident = False
            if pending_interp:
                in_interp = True
                pending_interp = False
            else:
                if _is_lean4_ident_prev(source, i - 2) and source[i - 1] == "!":
                    is_panic = (
                        source[i - 6 : i] == "panic!"
                        and not _is_lean4_ident_prev(source, i - 7)
                    )
                    if not is_panic:
                        errors.append("LEAN4_UNKNOWN_BANG_STRING")
                in_str = True
            out.append(" ")
            i += 1
        elif ch == "«":
            in_ident = False
            end_g = source.find("»", i + 1)
            if end_g == -1:
                errors.append("LEAN4_UNTERMINATED_IDENT")
                break
            inner = source[i + 1 : end_g]
            if _LEAN4_SIMPLE_GUILLEMET_RE.match(inner) is not None and inner != "axioms":
                out.append(source[i : end_g + 1])
            else:
                out.append(" " * (end_g - i + 1))
            i = end_g + 1
        elif ch == "'" and not in_ident:
            char_end = _match_lean4_char_literal_end(source, i, n)
            if char_end is not None:
                out.append("".join("\n" if c == "\n" else " " for c in source[i:char_end]))
                i = char_end
            else:
                out.append(ch)
                i += 1
        elif ch == "r" and not _is_lean4_ident_prev(source, i - 1):
            j = i + 1
            while j < n and source[j] == "#":
                j += 1
            if j < n and source[j] == '"':
                raw_hashes = j - (i + 1)
                in_ident = False
                out.append(" " * (j - i + 1))
                i = j + 1
            else:
                in_ident = True
                out.append(ch)
                i += 1
        elif ch.isalpha() and not _is_lean4_ident_prev(source, i - 1):
            w_end = i + 1
            while w_end < n and (source[w_end].isalnum() or source[w_end] == "_"):
                w_end += 1
            word = source[i:w_end]
            next_ch = source[w_end] if w_end < n else ""
            if next_ch == "!" and word in _LEAN4_INTERP_BANG_WORDS:
                pending_interp = True
                in_ident = False
                out.append(source[i : w_end + 1])
                i = w_end + 1
                continue
            if word in _LEAN4_INTERP_KEYWORDS:
                pending_interp = True
            in_ident = True
            out.append(word)
            i = w_end
        else:
            if ch.isalpha() or ch == "_":
                in_ident = True
            elif in_ident and (ch.isdigit() or ch in "'!?"):
                in_ident = True
            else:
                in_ident = False
            out.append(ch)
            i += 1
    if depth > 0:
        errors.append("LEAN4_UNTERMINATED_COMMENT")
    elif in_str or in_interp or raw_hashes >= 0 or interp_stack:
        errors.append("LEAN4_UNTERMINATED_STRING")
    return "".join(out), errors


def _strip_outer_parens(rhs: str) -> str:
    s = rhs.strip()
    while len(s) >= 2 and s[0] == "(" and s[-1] == ")":
        s = s[1:-1].strip()
    return s


def _is_native_false(rhs: str) -> bool:
    return _strip_outer_parens(rhs) in ("false", "Bool.false")


def _scan_decide_native(cleaned: str) -> bool:
    for mc in _LEAN4_DECIDE_CFG_BIND_RE.finditer(cleaned):
        for g in mc.groups():
            if g is not None and not _is_native_false(g):
                return True
    n = len(cleaned)
    match_rp: dict[int, int] = {}
    pstack: list[int] = []
    for idx, ch in enumerate(cleaned):
        if ch == "(":
            pstack.append(idx)
        elif ch == ")" and pstack:
            match_rp[pstack.pop()] = idx
    for m in _LEAN4_DECIDE_KW_RE.finditer(cleaned):
        pos = m.end()
        while True:
            while pos < n and cleaned[pos].isspace():
                pos += 1
            if pos >= n:
                break
            ch = cleaned[pos]
            if ch in "+-":
                mf = _LEAN4_FLAG_TOK_RE.match(cleaned, pos)
                if mf is None:
                    break
                if mf.group(0) == "+native":
                    return True
                pos = mf.end()
                continue
            if ch == "(":
                close_i = match_rp.get(pos)
                if close_i is None:
                    break
                mp = _LEAN4_OPT_PREFIX_RE.match(cleaned, pos + 1, close_i)
                if mp is None:
                    break
                key = mp.group(1)
                rhs = cleaned[mp.end() : close_i].strip()
                if key == "native" and not _is_native_false(rhs):
                    return True
                if key == "config":
                    inner = _strip_outer_parens(rhs)
                    if not (inner.startswith("{") and inner.endswith("}")):
                        return True
                    body = inner[1:-1]
                    if "{" in body or "}" in body or _LEAN4_CONFIG_WITH_RE.search(body) is not None:
                        return True
                    for mn in _LEAN4_CONFIG_NATIVE_RE.finditer(body):
                        if mn.group(1) is None or not _is_native_false(mn.group(1)):
                            return True
                pos = close_i + 1
                continue
            break
    return False


def audit_lean4_source_r10(source: str) -> list[str]:
    """Return list of R10+ static Lean 4 finding codes (empty list iff clean)."""
    if type(source) is not str:
        raise S96Error("INVALID_LEAN_SOURCE", "Lean source must be strict str")
    cleaned, findings = _strip_lean4_r10(source)
    cleaned = _LEAN4_GUILLEMET_RE.sub(r"\1", cleaned)
    for line in cleaned.splitlines():
        for pat, code in _LEAN4_HARD_LINE_RULES:
            if pat.search(line) is not None:
                findings.append(code)
    for m_imp in _LEAN4_IMPORT_RE.finditer(cleaned):
        root_pkg = m_imp.group(1).split(".")[0]
        if root_pkg != "Init":
            findings.append("LEAN4_NON_INIT_IMPORT")
    if _LEAN4_PARTIAL_DECL_RE.search(cleaned) is not None:
        findings.append("LEAN4_PARTIAL")
    if _scan_decide_native(cleaned):
        findings.append("LEAN4_DECIDE_NATIVE")
    if _LEAN4_DEBUG_RE.search(cleaned) is not None:
        findings.append("LEAN4_SKIP_KERNEL_TC")
    if _LEAN4_SPOOF_RE.search(cleaned) is not None:
        findings.append("LEAN4_EVAL_SPOOF")
    if _LEAN4_META_SYNTAX_RE.search(cleaned) is not None:
        findings.append("LEAN4_META_SYNTAX_ESCAPE")
    match_rb: dict[int, int] = {}
    bstack: list[int] = []
    for idx, ch in enumerate(cleaned):
        if ch == "[":
            bstack.append(idx)
        elif ch == "]" and bstack:
            match_rb[bstack.pop()] = idx
    for m_open in _LEAN4_ATTR_OPEN_RE.finditer(cleaned):
        lb = m_open.end() - 1
        rb = match_rb.get(lb)
        if rb is not None and _LEAN4_HARD_ATTR_RE.search(cleaned, lb + 1, rb) is not None:
            findings.append("LEAN4_ATTR_TRUST_ESCAPE")
    return findings


def _find_lean_binary() -> str:
    env_bin = os.environ.get("LEAN_BIN")
    if env_bin:
        p = Path(env_bin)
        if p.is_file():
            return str(p)
        raise S96Error("LEAN_BINARY_NOT_FOUND", "LEAN_BIN does not name an existing file")
    found = shutil.which("lean")
    if found is not None:
        return found
    home_env = os.environ.get("HOME")
    if home_env:
        elan_lean = Path(home_env) / ".elan" / "bin" / "lean"
        if elan_lean.is_file():
            return str(elan_lean)
    raise S96Error("LEAN_BINARY_NOT_FOUND", "lean binary not found on PATH, LEAN_BIN, or $HOME/.elan/bin")


def _scrubbed_tool_env() -> dict[str, str]:
    """Minimal safe subprocess env stripping LEAN_PATH/LEAN_OPTS/LEAN_SYSROOT/ELAN_*/LEAN_CC/LD_*."""
    env: dict[str, str] = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    home_val = os.environ.get("HOME")
    if home_val:
        env["HOME"] = home_val
    return env


def verify_lean_file(path: Path, *, check_pinned_sha: bool = True) -> dict[str, Any]:
    require_ok(type(check_pinned_sha) is bool, "INVALID_CHECK_PINNED_SHA", "check_pinned_sha must be strict bool")
    raw = read_regular_file_bytes(path, max_bytes=MAX_JSON_BYTES)
    if b"\r" in raw:
        raise S96Error("CRLF_FORBIDDEN", "CR/CRLF forbidden in Lean file")
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise S96Error("INVALID_UTF8", f"invalid UTF-8 in Lean file: {exc}") from exc
    sha = hashlib.sha256(raw).hexdigest()
    if check_pinned_sha and not hmac.compare_digest(sha, LEAN_FILE_SHA256):
        raise S96Error("LEAN_SHA_MISMATCH", "Lean file SHA-256 does not match pinned digest")
    findings = audit_lean4_source_r10(source)
    require_ok(len(findings) == 0, "LEAN_R10_STATIC_FINDING", f"R10 findings: {findings}")
    lean_bin = _find_lean_binary()
    proc = subprocess.run(
        [lean_bin, "--stdin"],
        input=source,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=_scrubbed_tool_env(),
    )
    require_ok(proc.returncode == 0, "LEAN_COMPILE_FAILED", f"lean exited {proc.returncode}: {proc.stderr}")
    require_ok(proc.stderr == "", "LEAN_STDERR_NONEMPTY", f"unexpected lean stderr: {proc.stderr}")
    records: list[str] = []
    for raw_line in proc.stdout.splitlines():
        s = raw_line.strip()
        if records and "[" in records[-1] and "]" not in records[-1]:
            records[-1] = records[-1] + " " + s
        else:
            records.append(s)
    seen: dict[str, list[str]] = {}
    for line in records:
        m = _LEAN4_AXIOM_OUT_RE.match(line)
        require_ok(m is not None, "LEAN_UNEXPECTED_OUTPUT", f"unexpected lean output line: {line}")
        thm = m.group(1)
        require_ok(thm not in seen, "LEAN_DUPLICATE_THEOREM", f"duplicate #print axioms for {thm}")
        ax_raw = m.group(2)
        ax_list = [] if ax_raw is None else [a.strip() for a in ax_raw.split(",") if a.strip()]
        for ax in ax_list:
            require_ok(ax in _ALLOWED_LEAN_AXIOMS, "LEAN_FORBIDDEN_AXIOM", f"{thm} uses forbidden axiom {ax}")
        seen[thm] = ax_list
    require_ok(len(seen) >= 1, "LEAN_NO_THEOREMS_VERIFIED", "at least one theorem axiom printout required")
    if check_pinned_sha:
        require_ok(tuple(seen.keys()) == LEAN_THEOREMS, "LEAN_THEOREM_SET_MISMATCH", "theorem set mismatch")
    return {
        "lean_file": path.name,
        "sha256": sha,
        "r10_findings": 0,
        "theorems_verified": len(seen),
        "allowed_axioms": sorted(_ALLOWED_LEAN_AXIOMS),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track S96 Beyond-LoRA & Inkling-2-Mini Verifier")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--standalone", action="store_true", help="Run exact-Q oracle and emit canonical JSON")
    mode.add_argument("--write", type=Path, help="Atomically write canonical 0o600 certificate JSON")
    mode.add_argument("--check", type=Path, help="Verify canonical certificate JSON fail-closed")
    mode.add_argument("--verify-lean", type=Path, help="Run R12 static + live scrubbed Lean 4.36.0 --stdin verification")
    mode.add_argument("--verify-upstream", type=Path, help="Verify all 10 pinned upstream certificate SHA-256s")
    mode.add_argument("--verify-inkling", type=Path, help="Verify both pinned Inkling-2-Mini local spec SHA-256s")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args(argv)

    try:
        if args.write is not None:
            cert = build_certificate()
            audit_certificate_object(cert)
            out_bytes = canonical_json_bytes(cert) + b"\n"
            write_atomic_0600_bytes(args.write, out_bytes)
            if args.json:
                sys.stdout.buffer.write(
                    canonical_json_bytes(
                        {"status": "WRITTEN", "certificate_sha256": cert["certificate_sha256"]}
                    )
                    + b"\n"
                )
            return 0
        if args.check is not None:
            cert = check_certificate_file(args.check)
            if args.json:
                sys.stdout.buffer.write(
                    canonical_json_bytes(
                        {"status": "PASS", "certificate_sha256": cert["certificate_sha256"]}
                    )
                    + b"\n"
                )
            return 0
        if args.verify_lean is not None:
            res = verify_lean_file(args.verify_lean, check_pinned_sha=True)
            if args.json:
                sys.stdout.buffer.write(canonical_json_bytes(res) + b"\n")
            return 0
        if args.verify_upstream is not None:
            res = verify_upstream_manifest(args.verify_upstream)
            if args.json:
                sys.stdout.buffer.write(canonical_json_bytes(res) + b"\n")
            return 0
        if args.verify_inkling is not None:
            res = verify_inkling_specs(args.verify_inkling)
            if args.json:
                sys.stdout.buffer.write(canonical_json_bytes(res) + b"\n")
            return 0
        cert = build_certificate()
        audit_certificate_object(cert)
        out_bytes = canonical_json_bytes(cert) + b"\n"
        sys.stdout.buffer.write(out_bytes)
        return 0
    except S96Error as exc:
        sys.stderr.write(f"ERROR [{exc.code}]: {exc.message}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
