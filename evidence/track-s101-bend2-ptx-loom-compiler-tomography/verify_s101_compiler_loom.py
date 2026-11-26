#!/usr/bin/env python3
"""
Track S101 Hardened Standalone Verifier, Live CPU ptxas/nvdisasm Gate & R10+ Lean 4.36.0 Auditor.

Supports:
  --standalone --json         Compute and emit canonical zero-float certificate JSON to stdout
  --write <cert.json>         Atomically write canonical 0o600 certificate JSON via dir_fd + fsync
  --check <cert.json>         Fail-closed Zone-B hardened verification of certificate JSON on disk
  --verify-lean <file.lean>   Full R10+ static Lean 4 audit + live Lean 4.36.0 axiom check
  --verify-ptx                Live CPU ptxas --gpu-name=sm_86 + nvdisasm SASS verification (0 GPU)
  --verify-upstream <dir>     Verify all 5 pinned S52/S68/S86/S94 upstream receipt SHA-256s
  --verify-bend <dir>         Verify all 7 pinned Bend 2 clone file SHA-256s
  --verify-loom <dir>         Verify all 5 pinned siliconcordat/loom git blob SHA-256s

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
import tempfile
import threading
from typing import Any

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from s101_compiler_loom_oracle import (
    BEND2_FILE_MANIFEST,
    BEND2_HEAD_SHA,
    CERT_SCHEMA,
    CERT_TRACK_ID,
    LEAN_FILE_NAME,
    LEAN_FILE_SHA256,
    LEAN_THEOREMS,
    LOOM_BRANCH_REFS,
    LOOM_DOC_MANIFEST,
    MAX_INT_BITS,
    MAX_JSON_DEPTH,
    PTX_KERNEL_SPECS,
    S101Error,
    UPSTREAM_RECEIPT_MANIFEST,
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
        "pillar1_bend2_adversarial_tomography",
        "pillar2_sm86_ptx_sass_audit",
        "pillar3_loom_libcuda_roofline",
        "pillar4_provenance_and_lean4",
    }
)
_P1_KEYS = frozenset(
    {
        "bend2_commit",
        "hvm_dropped_confirmed",
        "cuda_kept_confirmed",
        "cuda_uses_uvm_managed_alloc",
        "tcb_loc_audit",
        "bendtt_lean436_live_audit",
        "law4_latency_honesty",
        "pillar_verified",
    }
)
_TCB_KEYS = frozenset(
    {
        "bend_ts_loc",
        "comp_ts_loc",
        "safe_ts_loc",
        "main_ts_loc",
        "untrusted_ts_loc",
        "bendtt_lean_kernel_loc",
        "total_compiler_loc",
        "untrusted_to_kernel_ratio_q",
        "untrusted_to_kernel_ratio_dec",
        "kernel_loc_share_q",
        "kernel_loc_share_pct_dec",
    }
)
_BENDTT_KEYS = frozenset(
    {
        "compiled_rc",
        "stdout_bytes",
        "stderr_bytes",
        "theorems_count",
        "sorry_count",
        "admit_count",
        "axiom_decl_count",
        "unsafe_decl_count",
        "native_decide_count",
        "partial_parser_defs",
        "csimp_theorems",
        "tactic_warnings_on_lean436",
        "fuel_budget",
        "top_theorem_axioms",
        "sub_subz_axioms",
        "type_in_type_dead_girard_caveat",
        "elaborator_and_parser_unverified",
        "f32_axiomatic_unverified",
    }
)
_LAT_KEYS = frozenset(
    {"bend_cli_status", "lean436_peano_3thm_median_ms", "lean436_bendtt_full_ms", "proven_commons_catalog_repos"}
)
_P2_KEYS = frozenset(
    {
        "cuda_toolkit_release",
        "target_arch",
        "gpu_runtime_touched",
        "kernels",
        "s86_empirical_hazard_anchor",
        "s68_blockh4_dp4a_anchor",
        "sm86_occupancy_comparison",
        "zero_spill_all_kernels",
        "pillar_verified",
    }
)
_KERNELS_WRAP_KEYS = frozenset({"atomic_cas_hazard", "det_warp_shfl_cce", "fused_blockh4_dp4a"})
_K_ATOMIC_KEYS = frozenset(
    {
        "symbol",
        "ptx_sha256",
        "registers",
        "stack_frame_bytes",
        "spill_stores_bytes",
        "spill_loads_bytes",
        "cmem0_bytes",
        "sass_total_instructions",
        "sass_atomg_cas_count",
        "sass_red_add_f32_ftz_count",
        "sass_bssy_count",
        "sass_bsync_count",
        "sass_yield_count",
        "sass_shfl_bfly_count",
        "sass_idp4a_count",
        "deterministic_0ulp",
    }
)
_K_SHFL_KEYS = frozenset(
    {
        "symbol",
        "ptx_sha256",
        "registers",
        "stack_frame_bytes",
        "spill_stores_bytes",
        "spill_loads_bytes",
        "cmem0_bytes",
        "sass_total_instructions",
        "sass_atomg_cas_count",
        "sass_red_add_f32_ftz_count",
        "sass_shfl_bfly_count",
        "sass_fadd_count",
        "sass_idp4a_count",
        "deterministic_0ulp",
    }
)
_K_H4_KEYS = frozenset(
    {
        "symbol",
        "ptx_sha256",
        "registers",
        "stack_frame_bytes",
        "spill_stores_bytes",
        "spill_loads_bytes",
        "cmem0_bytes",
        "sass_total_instructions",
        "sass_atomg_cas_count",
        "sass_red_add_f32_ftz_count",
        "sass_fadd_count",
        "sass_ldg128_count",
        "sass_iadd3_count",
        "sass_prmt_count",
        "sass_idp4a_count",
        "sass_imad_count",
        "deterministic_0ulp",
    }
)
_S86_ANC_KEYS = frozenset(
    {
        "atomic_cas_divergent_rows",
        "total_rows",
        "atomic_cas_divergent_frac_q",
        "atomic_cas_divergent_pct_dec",
        "atomic_cas_max_ulp",
        "atomic_add_divergent_rows",
        "atomic_add_divergent_frac_q",
        "atomic_add_divergent_pct_dec",
        "atomic_add_max_ulp",
        "cce_det_max_ulp",
        "cce_det_unique_hashes",
    }
)
_S68_ANC_KEYS = frozenset({"max_butterfly_abs", "scale_factor_q", "bpw_q", "lossless_int8_dp4a"})
_OCC_WRAP_KEYS = frozenset({"s101_16reg_kernels", "s52_52reg_live_repair"})
_OCC_KEYS = frozenset(
    {
        "regs_per_thread",
        "alloc_regs_per_warp",
        "active_warps_per_sm",
        "max_warps_per_sm",
        "occupancy_q",
        "occupancy_pct_dec",
        "reg_file_util_q",
        "full_occupancy_achieved",
    }
)
_P3_KEYS = frozenset(
    {
        "dispatch_crossover_4b_n3_216ops",
        "dispatch_crossover_27b_n8_3584ops",
        "law5_pcie_gen4x8_double_buffer",
        "s94_residency_cliff_bridge",
        "loom_main_doc04_exact",
        "loom_pr5_contextual_compute",
        "loom_pr7_exact_inertia",
        "loom_pr9_gate_contracts",
        "pillar_verified",
    }
)
_DISP_KEYS = frozenset(
    {
        "num_launches",
        "eager_per_op_us_q",
        "uvm_fault_us_q",
        "graph_launch_us_q",
        "total_eager_us_q",
        "total_uvm_us_q",
        "graph_collapse_vs_eager_q",
        "graph_collapse_vs_uvm_q",
        "crossover_bytes_eager_q",
        "crossover_bytes_uvm_q",
        "crossover_bytes_graph_q",
        "uvm_strictly_worse_than_eager",
        "graph_strictly_beats_eager",
    }
)
_PCIE_KEYS = frozenset(
    {
        "bw_gpu_gb_s_q",
        "bw_pcie_gb_s_q",
        "gpu_over_pcie_bw_ratio_q",
        "gpu_over_pcie_bw_ratio_dec",
        "decode_b1_transfer_bound",
        "double_buffer_hides_dense_b1",
    }
)
_S94_BR_KEYS = frozenset({"b_crit_bpw_q", "b_crit_bpw_dec", "c_gpu_weight_gb_q", "b_ram_gb_s_q", "b_ssd_gb_s_q"})
_LOOM4_KEYS = frozenset(
    {
        "ive_4b_total_macs",
        "ive_27b_total_macs",
        "bf16_kulisch_product_span_bits",
        "bf16_kulisch_guard_bits",
        "bf16_kulisch_container_bits",
        "int8_g128_max_dot",
        "int8_2pow20_blocks_max_bits",
    }
)
_LOOM5_KEYS = frozenset({"closed_pathway_eval_cost", "s94_sparse_moe_active_frac_q", "s86_csr_budget_ceiling_q"})
_LOOM7_KEYS = frozenset({"tridiag_3x3_det_q", "tridiag_2x2_leading_det_q", "true_inertia_pos_neg_zero", "indefinite_witness_verified"})
_LOOM9_KEYS = frozenset(
    {"relations_count", "planted_harness_breaks_caught", "weak_escape_rate_q", "strong_escape_rate_q", "escape_reduction_factor_q"}
)
_P4_KEYS = frozenset(
    {
        "upstream_receipt_count",
        "upstream_receipt_manifest",
        "bend2_file_count",
        "bend2_file_manifest",
        "loom_branch_count",
        "loom_branch_refs",
        "loom_doc_count",
        "loom_doc_manifest",
        "lean4_certificate",
        "novelty_honesty_law4",
    }
)
_UP_ENTRY_KEYS = frozenset({"track_id", "rel_path", "sha256"})
_BEND_ENTRY_KEYS = frozenset({"rel_path", "sha256"})
_LOOM_REF_KEYS = frozenset({"ref", "commit_sha"})
_LOOM_DOC_KEYS = frozenset({"git_spec", "sha256"})
_LEAN_CERT_KEYS = frozenset({"file", "sha256", "theorem_count", "theorems", "allowed_axioms"})
_NOVELTY_KEYS = frozenset({"novelty_tier", "n0_prior_art_anchored", "n1_exact_synthesis_verified", "n2_claims"})
_PAYLOAD_BOOL_KEYS = frozenset(
    {
        "cuda_kept_confirmed",
        "cuda_uses_uvm_managed_alloc",
        "decode_b1_transfer_bound",
        "deterministic_0ulp",
        "double_buffer_hides_dense_b1",
        "elaborator_and_parser_unverified",
        "f32_axiomatic_unverified",
        "full_occupancy_achieved",
        "gpu_runtime_touched",
        "graph_strictly_beats_eager",
        "hvm_dropped_confirmed",
        "indefinite_witness_verified",
        "lossless_int8_dp4a",
        "n0_prior_art_anchored",
        "n1_exact_synthesis_verified",
        "pillar_verified",
        "type_in_type_dead_girard_caveat",
        "uvm_strictly_worse_than_eager",
        "zero_spill_all_kernels",
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
        raise S101Error("INVALID_MAX_DEPTH", "max_depth must be int in [1, 256]")
    stack: list[tuple[Any, int]] = [(obj, 0)]
    while stack:
        cur, depth = stack.pop()
        if depth > max_depth:
            raise S101Error("JSON_DEPTH_EXCEEDED", f"nesting depth > {max_depth}")
        t = type(cur)
        if t is dict:
            for k, v in cur.items():
                if type(k) is not str:
                    raise S101Error("NON_STR_KEY", "dict keys must be strict str")
                try:
                    k.encode("utf-8")
                except UnicodeEncodeError as exc:
                    raise S101Error("INVALID_UNICODE_STR", f"lone surrogate key: {exc}") from exc
                stack.append((v, depth + 1))
        elif t is list:
            for item in cur:
                stack.append((item, depth + 1))
        elif t is int:
            if cur.bit_length() > MAX_INT_BITS:
                raise S101Error("INT_BIT_LIMIT", f"int exceeds {MAX_INT_BITS} bits")
        elif t is str:
            try:
                cur.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise S101Error("INVALID_UNICODE_STR", f"lone surrogate str: {exc}") from exc
        elif t is bool or cur is None:
            continue
        else:
            raise S101Error("FORBIDDEN_JSON_TYPE", f"forbidden JSON value type: {t.__name__}")


def _no_dups_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise S101Error("DUPLICATE_JSON_KEY", f"duplicate key: {k}")
        out[k] = v
    return out


def _forbid_float(token: str) -> Any:
    raise S101Error("FLOAT_FORBIDDEN", f"float literal forbidden: {token}")


def _forbid_constant(token: str) -> Any:
    raise S101Error("NONFINITE_CONSTANT", f"non-finite constant forbidden: {token}")


def _parse_capped_int_token(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    if len(digits) > MAX_INT_DIGITS:
        raise S101Error("INT_DIGIT_LIMIT", f"integer token exceeds {MAX_INT_DIGITS} digits")
    val = int(token)
    if val.bit_length() > MAX_INT_BITS:
        raise S101Error("INT_BIT_LIMIT", f"integer token exceeds {MAX_INT_BITS} bits")
    return val


def parse_strict_json(text: str) -> Any:
    if type(text) is not str:
        raise S101Error("INVALID_JSON_TEXT", "JSON text must be strict str")
    try:
        encoded = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise S101Error("INVALID_UNICODE_STR", f"lone surrogate in JSON text: {exc}") from exc
    if len(encoded) > MAX_JSON_BYTES:
        raise S101Error("JSON_TOO_LARGE", f"JSON exceeds {MAX_JSON_BYTES} bytes")
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_no_dups_hook,
            parse_int=_parse_capped_int_token,
            parse_float=_forbid_float,
            parse_constant=_forbid_constant,
        )
    except S101Error:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise S101Error("JSON_DECODE_ERROR", f"invalid JSON: {exc}") from exc
    validate_json_tree_iterative(parsed)
    return parsed


def require_sha256_hex(val: Any, label: str) -> str:
    if type(val) is not str:
        raise S101Error("INVALID_DIGEST_TYPE", f"{label} must be strict str")
    if len(val) != 64:
        raise S101Error("INVALID_DIGEST_LEN", f"{label} must have length 64")
    if any(ch not in _HEX_LOWER for ch in val):
        raise S101Error("INVALID_DIGEST_HEX", f"{label} must be lowercase ASCII hex")
    return val


def exact_typed_equal(lhs: Any, rhs: Any) -> bool:
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
        raise S101Error("BAD_RATIONAL_DICT", "rational dict must have exact keys {num, den}")
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


def _audit_occupancy(entry: Any, expect_full: bool) -> None:
    d = _req_dict(entry, _OCC_KEYS, "BAD_OCC_SCHEMA")
    rpt = _req_int(d["regs_per_thread"], "BAD_OCC_INV")
    arw = _req_int(d["alloc_regs_per_warp"], "BAD_OCC_INV")
    aw = _req_int(d["active_warps_per_sm"], "BAD_OCC_INV")
    mw = _req_int(d["max_warps_per_sm"], "BAD_OCC_INV")
    occ = _parse_rat_dict(d["occupancy_q"])
    util = _parse_rat_dict(d["reg_file_util_q"])
    require_ok(arw > 0, "BAD_OCC_INV", "alloc_regs_per_warp must be positive")
    require_ok(mw > 0, "BAD_OCC_INV", "max_warps_per_sm must be positive")
    _check_invariants(
        [
            (rpt > 0, "BAD_OCC_INV"),
            (arw == ((rpt * 32 + 255) // 256) * 256, "BAD_OCC_INV"),
            (aw == min(mw, 65536 // arw), "BAD_OCC_INV"),
            (occ == Fraction(aw, mw), "BAD_OCC_INV"),
            (d["occupancy_pct_dec"] == frac_to_dec_str(occ * 100, 2), "BAD_OCC_INV"),
            (util == Fraction(aw * arw, 65536), "BAD_OCC_INV"),
            (d["full_occupancy_achieved"] is expect_full, "BAD_OCC_INV"),
            ((aw == mw) is expect_full, "BAD_OCC_INV"),
        ]
    )


def _audit_dispatch(entry: Any, bw_gpu: Fraction) -> None:
    d = _req_dict(entry, _DISP_KEYS, "BAD_DISP_SCHEMA")
    nl = _req_int(d["num_launches"], "BAD_DISP_INV")
    te = _parse_rat_dict(d["eager_per_op_us_q"])
    tu = _parse_rat_dict(d["uvm_fault_us_q"])
    tg = _parse_rat_dict(d["graph_launch_us_q"])
    tote = _parse_rat_dict(d["total_eager_us_q"])
    totu = _parse_rat_dict(d["total_uvm_us_q"])
    ce = _parse_rat_dict(d["graph_collapse_vs_eager_q"])
    cu = _parse_rat_dict(d["graph_collapse_vs_uvm_q"])
    me = _parse_rat_dict(d["crossover_bytes_eager_q"])
    mu = _parse_rat_dict(d["crossover_bytes_uvm_q"])
    mg = _parse_rat_dict(d["crossover_bytes_graph_q"])
    require_ok(nl >= 2, "BAD_DISP_INV", "num_launches must be >= 2")
    require_ok(tg > 0, "BAD_DISP_INV", "graph_launch_us must be positive")
    bpu = bw_gpu * 1000
    _check_invariants(
        [
            (te > 0, "BAD_DISP_INV"),
            (tu > te, "BAD_DISP_INV"),
            (tote == nl * te, "BAD_DISP_INV"),
            (totu == nl * tu, "BAD_DISP_INV"),
            (ce == tote / tg, "BAD_DISP_INV"),
            (cu == totu / tg, "BAD_DISP_INV"),
            (me == bpu * te, "BAD_DISP_INV"),
            (mu == bpu * tu, "BAD_DISP_INV"),
            (mg == bpu * tg, "BAD_DISP_INV"),
            (d["uvm_strictly_worse_than_eager"] is True, "BAD_DISP_INV"),
            (d["graph_strictly_beats_eager"] is True, "BAD_DISP_INV"),
            (tg < tote, "BAD_DISP_INV"),
        ]
    )


def _audit_pillar1(p1: dict[str, Any]) -> None:
    tcb = _req_dict(p1["tcb_loc_audit"], _TCB_KEYS, "BAD_P1_TCB")
    btt = _req_dict(p1["bendtt_lean436_live_audit"], _BENDTT_KEYS, "BAD_P1_BTT")
    lat = _req_dict(p1["law4_latency_honesty"], _LAT_KEYS, "BAD_P1_LAT")
    b_loc = _req_int(tcb["bend_ts_loc"], "BAD_P1_INV")
    c_loc = _req_int(tcb["comp_ts_loc"], "BAD_P1_INV")
    s_loc = _req_int(tcb["safe_ts_loc"], "BAD_P1_INV")
    m_loc = _req_int(tcb["main_ts_loc"], "BAD_P1_INV")
    u_loc = _req_int(tcb["untrusted_ts_loc"], "BAD_P1_INV")
    k_loc = _req_int(tcb["bendtt_lean_kernel_loc"], "BAD_P1_INV")
    tot_loc = _req_int(tcb["total_compiler_loc"], "BAD_P1_INV")
    u2k = _parse_rat_dict(tcb["untrusted_to_kernel_ratio_q"])
    ksh = _parse_rat_dict(tcb["kernel_loc_share_q"])
    require_ok(k_loc > 0, "BAD_P1_INV", "kernel LOC must be positive")
    require_ok(tot_loc > 0, "BAD_P1_INV", "total LOC must be positive")
    _check_invariants(
        [
            (p1["pillar_verified"] is True, "BAD_P1_INV"),
            (p1["bend2_commit"] == BEND2_HEAD_SHA, "BAD_P1_INV"),
            (p1["hvm_dropped_confirmed"] is True, "BAD_P1_INV"),
            (p1["cuda_kept_confirmed"] is True, "BAD_P1_INV"),
            (p1["cuda_uses_uvm_managed_alloc"] is True, "BAD_P1_INV"),
            (b_loc == 4021, "BAD_P1_INV"),
            (c_loc == 6455, "BAD_P1_INV"),
            (s_loc == 1729, "BAD_P1_INV"),
            (m_loc == 1190, "BAD_P1_INV"),
            (k_loc == 3861, "BAD_P1_INV"),
            (u_loc == b_loc + c_loc + s_loc + m_loc, "BAD_P1_INV"),
            (tot_loc == u_loc + k_loc, "BAD_P1_INV"),
            (u2k == Fraction(u_loc, k_loc), "BAD_P1_INV"),
            (tcb["untrusted_to_kernel_ratio_dec"] == frac_to_dec_str(u2k, 4), "BAD_P1_INV"),
            (ksh == Fraction(k_loc, tot_loc), "BAD_P1_INV"),
            (tcb["kernel_loc_share_pct_dec"] == frac_to_dec_str(ksh * 100, 2), "BAD_P1_INV"),
            (_req_int(btt["compiled_rc"], "BAD_P1_INV") == 0, "BAD_P1_INV"),
            (_req_int(btt["stdout_bytes"], "BAD_P1_INV") == 8307, "BAD_P1_INV"),
            (_req_int(btt["stderr_bytes"], "BAD_P1_INV") == 0, "BAD_P1_INV"),
            (_req_int(btt["theorems_count"], "BAD_P1_INV") == 228, "BAD_P1_INV"),
            (_req_int(btt["sorry_count"], "BAD_P1_INV") == 0, "BAD_P1_INV"),
            (_req_int(btt["admit_count"], "BAD_P1_INV") == 0, "BAD_P1_INV"),
            (_req_int(btt["axiom_decl_count"], "BAD_P1_INV") == 0, "BAD_P1_INV"),
            (_req_int(btt["unsafe_decl_count"], "BAD_P1_INV") == 0, "BAD_P1_INV"),
            (_req_int(btt["native_decide_count"], "BAD_P1_INV") == 0, "BAD_P1_INV"),
            (_req_int(btt["partial_parser_defs"], "BAD_P1_INV") == 17, "BAD_P1_INV"),
            (_req_int(btt["csimp_theorems"], "BAD_P1_INV") == 1, "BAD_P1_INV"),
            (_req_int(btt["tactic_warnings_on_lean436"], "BAD_P1_INV") == 72, "BAD_P1_INV"),
            (_req_int(btt["fuel_budget"], "BAD_P1_INV") == 400_000_000, "BAD_P1_INV"),
            (btt["top_theorem_axioms"] == ["propext", "Classical.choice", "Quot.sound"], "BAD_P1_INV"),
            (btt["sub_subz_axioms"] == ["propext", "Quot.sound"], "BAD_P1_INV"),
            (btt["type_in_type_dead_girard_caveat"] is True, "BAD_P1_INV"),
            (btt["elaborator_and_parser_unverified"] is True, "BAD_P1_INV"),
            (btt["f32_axiomatic_unverified"] is True, "BAD_P1_INV"),
            (lat["bend_cli_status"] == "unexecuted_bun_missing", "BAD_P1_INV"),
            (_req_int(lat["lean436_peano_3thm_median_ms"], "BAD_P1_INV") == 696, "BAD_P1_INV"),
            (_req_int(lat["lean436_bendtt_full_ms"], "BAD_P1_INV") == 42656, "BAD_P1_INV"),
            (_req_int(lat["proven_commons_catalog_repos"], "BAD_P1_INV") == 40, "BAD_P1_INV"),
        ]
    )


def _audit_pillar2(p2: dict[str, Any]) -> None:
    kw = _req_dict(p2["kernels"], _KERNELS_WRAP_KEYS, "BAD_P2_KERNELS")
    ka = _req_dict(kw["atomic_cas_hazard"], _K_ATOMIC_KEYS, "BAD_P2_KA")
    kb = _req_dict(kw["det_warp_shfl_cce"], _K_SHFL_KEYS, "BAD_P2_KB")
    kc = _req_dict(kw["fused_blockh4_dp4a"], _K_H4_KEYS, "BAD_P2_KC")
    s86 = _req_dict(p2["s86_empirical_hazard_anchor"], _S86_ANC_KEYS, "BAD_P2_S86")
    s68 = _req_dict(p2["s68_blockh4_dp4a_anchor"], _S68_ANC_KEYS, "BAD_P2_S68")
    occ = _req_dict(p2["sm86_occupancy_comparison"], _OCC_WRAP_KEYS, "BAD_P2_OCC")
    _audit_occupancy(occ["s101_16reg_kernels"], True)
    _audit_occupancy(occ["s52_52reg_live_repair"], False)
    ptx_pins = {name: hashlib.sha256(src.encode("utf-8")).hexdigest() for name, src in PTX_KERNEL_SPECS}
    cas_rows = _req_int(s86["atomic_cas_divergent_rows"], "BAD_P2_INV")
    add_rows = _req_int(s86["atomic_add_divergent_rows"], "BAD_P2_INV")
    tot_rows = _req_int(s86["total_rows"], "BAD_P2_INV")
    cas_f = _parse_rat_dict(s86["atomic_cas_divergent_frac_q"])
    add_f = _parse_rat_dict(s86["atomic_add_divergent_frac_q"])
    require_ok(tot_rows > 0, "BAD_P2_INV", "total_rows must be positive")
    for kdict, sym, exp_regs, exp_cmem, exp_tot in (
        (ka, "s101_atomic_cas_reduce_f32", 10, 372, 32),
        (kb, "s101_det_warp_shfl_reduce_f32", 16, 368, 32),
        (kc, "s101_fused_blockh4_dp4a_int32", 16, 376, 40),
    ):
        k_sha = require_sha256_hex(kdict["ptx_sha256"], "ptx_sha256")
        _check_invariants(
            [
                (kdict["symbol"] == sym, "BAD_P2_INV"),
                (hmac.compare_digest(k_sha, ptx_pins[sym]), "BAD_P2_INV"),
                (_req_int(kdict["registers"], "BAD_P2_INV") == exp_regs, "BAD_P2_INV"),
                (_req_int(kdict["stack_frame_bytes"], "BAD_P2_INV") == 0, "BAD_P2_INV"),
                (_req_int(kdict["spill_stores_bytes"], "BAD_P2_INV") == 0, "BAD_P2_INV"),
                (_req_int(kdict["spill_loads_bytes"], "BAD_P2_INV") == 0, "BAD_P2_INV"),
                (_req_int(kdict["cmem0_bytes"], "BAD_P2_INV") == exp_cmem, "BAD_P2_INV"),
                (_req_int(kdict["sass_total_instructions"], "BAD_P2_INV") == exp_tot, "BAD_P2_INV"),
            ]
        )
    _check_invariants(
        [
            (p2["pillar_verified"] is True, "BAD_P2_INV"),
            (p2["cuda_toolkit_release"] == "13.4", "BAD_P2_INV"),
            (p2["target_arch"] == "sm_86", "BAD_P2_INV"),
            (p2["gpu_runtime_touched"] is False, "BAD_P2_INV"),
            (p2["zero_spill_all_kernels"] is True, "BAD_P2_INV"),
            (occ["s101_16reg_kernels"]["regs_per_thread"] == 16, "BAD_P2_INV"),
            (occ["s101_16reg_kernels"]["max_warps_per_sm"] == 48, "BAD_P2_INV"),
            (occ["s52_52reg_live_repair"]["regs_per_thread"] == 52, "BAD_P2_INV"),
            (occ["s52_52reg_live_repair"]["max_warps_per_sm"] == 48, "BAD_P2_INV"),
            (_req_int(ka["sass_atomg_cas_count"], "BAD_P2_INV") == 1, "BAD_P2_INV"),
            (_req_int(ka["sass_red_add_f32_ftz_count"], "BAD_P2_INV") == 1, "BAD_P2_INV"),
            (_req_int(ka["sass_bssy_count"], "BAD_P2_INV") == 1, "BAD_P2_INV"),
            (_req_int(ka["sass_bsync_count"], "BAD_P2_INV") == 1, "BAD_P2_INV"),
            (_req_int(ka["sass_yield_count"], "BAD_P2_INV") == 1, "BAD_P2_INV"),
            (_req_int(ka["sass_shfl_bfly_count"], "BAD_P2_INV") == 0, "BAD_P2_INV"),
            (_req_int(ka["sass_idp4a_count"], "BAD_P2_INV") == 0, "BAD_P2_INV"),
            (ka["deterministic_0ulp"] is False, "BAD_P2_INV"),
            (_req_int(kb["sass_atomg_cas_count"], "BAD_P2_INV") == 0, "BAD_P2_INV"),
            (_req_int(kb["sass_red_add_f32_ftz_count"], "BAD_P2_INV") == 0, "BAD_P2_INV"),
            (_req_int(kb["sass_shfl_bfly_count"], "BAD_P2_INV") == 5, "BAD_P2_INV"),
            (_req_int(kb["sass_fadd_count"], "BAD_P2_INV") == 5, "BAD_P2_INV"),
            (_req_int(kb["sass_idp4a_count"], "BAD_P2_INV") == 0, "BAD_P2_INV"),
            (kb["deterministic_0ulp"] is True, "BAD_P2_INV"),
            (_req_int(kc["sass_atomg_cas_count"], "BAD_P2_INV") == 0, "BAD_P2_INV"),
            (_req_int(kc["sass_red_add_f32_ftz_count"], "BAD_P2_INV") == 0, "BAD_P2_INV"),
            (_req_int(kc["sass_fadd_count"], "BAD_P2_INV") == 0, "BAD_P2_INV"),
            (_req_int(kc["sass_ldg128_count"], "BAD_P2_INV") == 1, "BAD_P2_INV"),
            (_req_int(kc["sass_iadd3_count"], "BAD_P2_INV") == 6, "BAD_P2_INV"),
            (_req_int(kc["sass_prmt_count"], "BAD_P2_INV") == 2, "BAD_P2_INV"),
            (_req_int(kc["sass_idp4a_count"], "BAD_P2_INV") == 1, "BAD_P2_INV"),
            (_req_int(kc["sass_imad_count"], "BAD_P2_INV") == 5, "BAD_P2_INV"),
            (kc["deterministic_0ulp"] is True, "BAD_P2_INV"),
            (cas_rows == 863, "BAD_P2_INV"),
            (tot_rows == 1024, "BAD_P2_INV"),
            (cas_f == Fraction(cas_rows, tot_rows), "BAD_P2_INV"),
            (s86["atomic_cas_divergent_pct_dec"] == frac_to_dec_str(cas_f * 100, 2), "BAD_P2_INV"),
            (_req_int(s86["atomic_cas_max_ulp"], "BAD_P2_INV") == 15, "BAD_P2_INV"),
            (add_rows == 63, "BAD_P2_INV"),
            (add_f == Fraction(add_rows, tot_rows), "BAD_P2_INV"),
            (s86["atomic_add_divergent_pct_dec"] == frac_to_dec_str(add_f * 100, 2), "BAD_P2_INV"),
            (_req_int(s86["atomic_add_max_ulp"], "BAD_P2_INV") == 2, "BAD_P2_INV"),
            (_req_int(s86["cce_det_max_ulp"], "BAD_P2_INV") == 0, "BAD_P2_INV"),
            (_req_int(s86["cce_det_unique_hashes"], "BAD_P2_INV") == 1, "BAD_P2_INV"),
            (_req_int(s68["max_butterfly_abs"], "BAD_P2_INV") == 28, "BAD_P2_INV"),
            (_parse_rat_dict(s68["scale_factor_q"]) == Fraction(1, 2), "BAD_P2_INV"),
            (_parse_rat_dict(s68["bpw_q"]) == Fraction(9, 2), "BAD_P2_INV"),
            (s68["lossless_int8_dp4a"] is True, "BAD_P2_INV"),
        ]
    )


def _audit_pillar3(p3: dict[str, Any]) -> None:
    pcie = _req_dict(p3["law5_pcie_gen4x8_double_buffer"], _PCIE_KEYS, "BAD_P3_PCIE")
    bw_gpu = _parse_rat_dict(pcie["bw_gpu_gb_s_q"])
    bw_pcie = _parse_rat_dict(pcie["bw_pcie_gb_s_q"])
    bw_rat = _parse_rat_dict(pcie["gpu_over_pcie_bw_ratio_q"])
    require_ok(bw_pcie > 0, "BAD_P3_INV", "bw_pcie must be positive")
    d4 = p3["dispatch_crossover_4b_n3_216ops"]
    d27 = p3["dispatch_crossover_27b_n8_3584ops"]
    _audit_dispatch(d4, bw_gpu)
    _audit_dispatch(d27, bw_gpu)
    s94 = _req_dict(p3["s94_residency_cliff_bridge"], _S94_BR_KEYS, "BAD_P3_S94")
    l4 = _req_dict(p3["loom_main_doc04_exact"], _LOOM4_KEYS, "BAD_P3_L4")
    l5 = _req_dict(p3["loom_pr5_contextual_compute"], _LOOM5_KEYS, "BAD_P3_L5")
    l7 = _req_dict(p3["loom_pr7_exact_inertia"], _LOOM7_KEYS, "BAD_P3_L7")
    l9 = _req_dict(p3["loom_pr9_gate_contracts"], _LOOM9_KEYS, "BAD_P3_L9")
    b_crit = _parse_rat_dict(s94["b_crit_bpw_q"])
    b_ram = _parse_rat_dict(s94["b_ram_gb_s_q"])
    b_ssd = _parse_rat_dict(s94["b_ssd_gb_s_q"])
    span = _req_int(l4["bf16_kulisch_product_span_bits"], "BAD_P3_INV")
    guard = _req_int(l4["bf16_kulisch_guard_bits"], "BAD_P3_INV")
    cont = _req_int(l4["bf16_kulisch_container_bits"], "BAD_P3_INV")
    max_blk_bits = _req_int(l4["int8_2pow20_blocks_max_bits"], "BAD_P3_INV")
    moe_f = _parse_rat_dict(l5["s94_sparse_moe_active_frac_q"])
    csr_c = _parse_rat_dict(l5["s86_csr_budget_ceiling_q"])
    det3 = _parse_rat_dict(l7["tridiag_3x3_det_q"])
    det2 = _parse_rat_dict(l7["tridiag_2x2_leading_det_q"])
    esc_w = _parse_rat_dict(l9["weak_escape_rate_q"])
    esc_s = _parse_rat_dict(l9["strong_escape_rate_q"])
    esc_r = _parse_rat_dict(l9["escape_reduction_factor_q"])
    require_ok(esc_s > 0, "BAD_P3_INV", "strong_escape_rate must be positive")
    _check_invariants(
        [
            (p3["pillar_verified"] is True, "BAD_P3_INV"),
            (bw_gpu == Fraction(1783, 5), "BAD_P3_INV"),
            (bw_pcie == Fraction(12, 1), "BAD_P3_INV"),
            (bw_rat == bw_gpu / bw_pcie, "BAD_P3_INV"),
            (pcie["gpu_over_pcie_bw_ratio_dec"] == frac_to_dec_str(bw_rat, 4), "BAD_P3_INV"),
            (pcie["decode_b1_transfer_bound"] is True, "BAD_P3_INV"),
            (pcie["double_buffer_hides_dense_b1"] is False, "BAD_P3_INV"),
            (d4["num_launches"] == 216, "BAD_P3_INV"),
            (_parse_rat_dict(d4["eager_per_op_us_q"]) == Fraction(12, 1), "BAD_P3_INV"),
            (_parse_rat_dict(d4["uvm_fault_us_q"]) == Fraction(35, 1), "BAD_P3_INV"),
            (_parse_rat_dict(d4["graph_launch_us_q"]) == Fraction(1, 1), "BAD_P3_INV"),
            (d27["num_launches"] == 3584, "BAD_P3_INV"),
            (_parse_rat_dict(d27["eager_per_op_us_q"]) == Fraction(12, 1), "BAD_P3_INV"),
            (_parse_rat_dict(d27["uvm_fault_us_q"]) == Fraction(35, 1), "BAD_P3_INV"),
            (_parse_rat_dict(d27["graph_launch_us_q"]) == Fraction(1, 1), "BAD_P3_INV"),
            (b_crit == Fraction(325, 171), "BAD_P3_INV"),
            (s94["b_crit_bpw_dec"] == frac_to_dec_str(b_crit, 4), "BAD_P3_INV"),
            (_parse_rat_dict(s94["c_gpu_weight_gb_q"]) == Fraction(13, 2), "BAD_P3_INV"),
            (b_ram == Fraction(50, 1), "BAD_P3_INV"),
            (b_ssd == Fraction(6, 1), "BAD_P3_INV"),
            (_req_int(l4["ive_4b_total_macs"], "BAD_P3_INV") == 1_509_949_440, "BAD_P3_INV"),
            (_req_int(l4["ive_27b_total_macs"], "BAD_P3_INV") == 10_737_418_240, "BAD_P3_INV"),
            (span == 522, "BAD_P3_INV"),
            (guard == 64, "BAD_P3_INV"),
            (cont == 640, "BAD_P3_INV"),
            (span + guard <= cont, "BAD_P3_INV"),
            (_req_int(l4["int8_g128_max_dot"], "BAD_P3_INV") == 1 << 21, "BAD_P3_INV"),
            (max_blk_bits == 41, "BAD_P3_INV"),
            (_req_int(l5["closed_pathway_eval_cost"], "BAD_P3_INV") == 0, "BAD_P3_INV"),
            (moe_f == Fraction(1, 20), "BAD_P3_INV"),
            (csr_c == Fraction(1, 160), "BAD_P3_INV"),
            (det3 == Fraction(-1, 1), "BAD_P3_INV"),
            (det2 == Fraction(0, 1), "BAD_P3_INV"),
            (l7["true_inertia_pos_neg_zero"] == [2, 1, 0], "BAD_P3_INV"),
            (l7["indefinite_witness_verified"] is True, "BAD_P3_INV"),
            (_req_int(l9["relations_count"], "BAD_P3_INV") == 5, "BAD_P3_INV"),
            (_req_int(l9["planted_harness_breaks_caught"], "BAD_P3_INV") == 32, "BAD_P3_INV"),
            (esc_w == Fraction(7, 10), "BAD_P3_INV"),
            (esc_s == Fraction(1, 50), "BAD_P3_INV"),
            (esc_r == esc_w / esc_s, "BAD_P3_INV"),
        ]
    )


def _audit_pillar4(p4: dict[str, Any]) -> None:
    require_ok(p4["upstream_receipt_count"] == len(UPSTREAM_RECEIPT_MANIFEST), "BAD_UP_COUNT", "upstream count mismatch")
    up_list = p4["upstream_receipt_manifest"]
    require_ok(type(up_list) is list and len(up_list) == len(UPSTREAM_RECEIPT_MANIFEST), "BAD_UP_LIST", "upstream list mismatch")
    for entry, (exp_tid, exp_rel, exp_sha) in zip(up_list, UPSTREAM_RECEIPT_MANIFEST):
        ed = _req_dict(entry, _UP_ENTRY_KEYS, "BAD_UP_ENTRY")
        e_sha = require_sha256_hex(ed["sha256"], "upstream_receipt_manifest.sha256")
        _check_invariants(
            [
                (ed["track_id"] == exp_tid, "BAD_UP_PIN"),
                (ed["rel_path"] == exp_rel, "BAD_UP_PIN"),
                (hmac.compare_digest(e_sha, exp_sha), "BAD_UP_PIN"),
            ]
        )
    require_ok(p4["bend2_file_count"] == len(BEND2_FILE_MANIFEST), "BAD_BEND_COUNT", "bend2 count mismatch")
    b_list = p4["bend2_file_manifest"]
    require_ok(type(b_list) is list and len(b_list) == len(BEND2_FILE_MANIFEST), "BAD_BEND_LIST", "bend2 list mismatch")
    for entry, (exp_rel, exp_sha) in zip(b_list, BEND2_FILE_MANIFEST):
        ed = _req_dict(entry, _BEND_ENTRY_KEYS, "BAD_BEND_ENTRY")
        e_sha = require_sha256_hex(ed["sha256"], "bend2_file_manifest.sha256")
        _check_invariants(
            [
                (ed["rel_path"] == exp_rel, "BAD_BEND_PIN"),
                (hmac.compare_digest(e_sha, exp_sha), "BAD_BEND_PIN"),
            ]
        )
    require_ok(p4["loom_branch_count"] == len(LOOM_BRANCH_REFS), "BAD_LOOM_REF_COUNT", "loom branch count mismatch")
    lr_list = p4["loom_branch_refs"]
    require_ok(type(lr_list) is list and len(lr_list) == len(LOOM_BRANCH_REFS), "BAD_LOOM_REF_LIST", "loom branch list mismatch")
    for entry, (exp_ref, exp_sha) in zip(lr_list, LOOM_BRANCH_REFS):
        ed = _req_dict(entry, _LOOM_REF_KEYS, "BAD_LOOM_REF_ENTRY")
        _check_invariants(
            [
                (ed["ref"] == exp_ref, "BAD_LOOM_REF_PIN"),
                (ed["commit_sha"] == exp_sha, "BAD_LOOM_REF_PIN"),
            ]
        )
    require_ok(p4["loom_doc_count"] == len(LOOM_DOC_MANIFEST), "BAD_LOOM_DOC_COUNT", "loom doc count mismatch")
    ld_list = p4["loom_doc_manifest"]
    require_ok(type(ld_list) is list and len(ld_list) == len(LOOM_DOC_MANIFEST), "BAD_LOOM_DOC_LIST", "loom doc list mismatch")
    for entry, (exp_spec, exp_sha) in zip(ld_list, LOOM_DOC_MANIFEST):
        ed = _req_dict(entry, _LOOM_DOC_KEYS, "BAD_LOOM_DOC_ENTRY")
        e_sha = require_sha256_hex(ed["sha256"], "loom_doc_manifest.sha256")
        _check_invariants(
            [
                (ed["git_spec"] == exp_spec, "BAD_LOOM_DOC_PIN"),
                (hmac.compare_digest(e_sha, exp_sha), "BAD_LOOM_DOC_PIN"),
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
    """Fail-closed in-memory Zone-B field-complete secondary auditor across all 4 pillars."""
    validate_json_tree_iterative(payload)
    if type(payload) is not dict:
        raise S101Error("BAD_PAYLOAD_TYPE", "payload must be strict dict")
    if frozenset(payload.keys()) != _PAYLOAD_KEYS:
        raise S101Error("BAD_PAYLOAD_KEYS", "payload keys mismatch")

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

    _audit_pillar1(_req_dict(payload["pillar1_bend2_adversarial_tomography"], _P1_KEYS, "BAD_P1_SCHEMA"))
    _audit_pillar2(_req_dict(payload["pillar2_sm86_ptx_sass_audit"], _P2_KEYS, "BAD_P2_SCHEMA"))
    _audit_pillar3(_req_dict(payload["pillar3_loom_libcuda_roofline"], _P3_KEYS, "BAD_P3_SCHEMA"))
    _audit_pillar4(_req_dict(payload["pillar4_provenance_and_lean4"], _P4_KEYS, "BAD_P4_SCHEMA"))
    return payload


def verify_certificate_dict(cert: Any, *, full_replay: bool = True) -> dict[str, Any]:
    """Fail-closed in-memory Zone-B verifier supporting FR1 (full_replay=True) and FR0 (full_replay=False)."""
    require_ok(type(full_replay) is bool, "INVALID_FULL_REPLAY", "full_replay must be strict bool")
    validate_json_tree_iterative(cert)
    if type(cert) is not dict:
        raise S101Error("NON_OBJECT_ROOT", "certificate root must be strict dict")
    if frozenset(cert.keys()) != _CERT_KEYS:
        raise S101Error("BAD_CERT_KEYS", "certificate keys mismatch")
    if cert["schema"] != CERT_SCHEMA:
        raise S101Error("BAD_SCHEMA", "schema mismatch")
    if cert["track_id"] != CERT_TRACK_ID:
        raise S101Error("BAD_TRACK_ID", "track_id mismatch")

    payload = cert["payload"]
    if type(payload) is not dict:
        raise S101Error("BAD_PAYLOAD_TYPE", "payload must be strict dict")

    claimed_p_sha = require_sha256_hex(cert["payload_sha256"], "payload_sha256")
    claimed_c_sha = require_sha256_hex(cert["certificate_sha256"], "certificate_sha256")

    calc_p_sha = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    if not hmac.compare_digest(claimed_p_sha, calc_p_sha):
        raise S101Error("PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")

    envelope = {
        "schema": cert["schema"],
        "track_id": cert["track_id"],
        "payload_sha256": claimed_p_sha,
        "payload": payload,
    }
    calc_c_sha = hashlib.sha256(canonical_json_bytes(envelope)).hexdigest()
    if not hmac.compare_digest(claimed_c_sha, calc_c_sha):
        raise S101Error("CERT_SHA_MISMATCH", "certificate_sha256 mismatch")

    secondary_audit_payload(payload)

    if full_replay:
        expected = build_certificate()
        if not exact_typed_equal(payload, expected["payload"]):
            raise S101Error("PAYLOAD_ORACLE_MISMATCH", "payload disagrees with exact-Q oracle")
        if not hmac.compare_digest(claimed_c_sha, expected["certificate_sha256"]):
            raise S101Error("ORACLE_CERT_SHA_MISMATCH", "certificate_sha256 disagrees with exact-Q oracle")
    return cert


def audit_certificate_object(cert: Any) -> dict[str, Any]:
    return verify_certificate_dict(cert, full_replay=True)


# ---------------------------------------------------------------------------
# Hardened dir_fd File I/O (TOCTOU, Symlink, FIFO, Hardlink, 0o600 Atomic Write)
# ---------------------------------------------------------------------------

def _validate_path(path: Any) -> None:
    if type(path) not in _EXACT_PATH_TYPES:
        raise S101Error("INVALID_PATH_TYPE", "path must be concrete pathlib.Path")
    raw = str(path)
    try:
        raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise S101Error("INVALID_UNICODE_STR", f"lone surrogate in path: {exc}") from exc
    if "\x00" in raw:
        raise S101Error("INVALID_PATH_NUL", "NUL byte forbidden in path")


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
        raise S101Error("INVALID_UNICODE_STR", f"lone surrogate in PWD: {exc}") from exc
    cur_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in Path(pwd).parts[1:]:
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if _is_symlink_at(cur_fd, comp):
                    raise S101Error("SYMLINK_ANCESTOR_FORBIDDEN", f"symlink in PWD: {comp}") from exc
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
        raise S101Error("INVALID_PATH", "path must name a regular file")
    ancestors, leaf = parts[:-1], parts[-1]
    cur_fd = os.open("/" if is_abs else ".", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in ancestors:
            try:
                nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur_fd)
            except OSError as exc:
                if _is_symlink_at(cur_fd, comp):
                    raise S101Error("SYMLINK_ANCESTOR_FORBIDDEN", f"symlink ancestor: {comp}") from exc
                raise S101Error("PARENT_DIR_ERROR", f"cannot open ancestor {comp}: {exc}") from exc
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
                raise S101Error("SYMLINK_FORBIDDEN", f"symlink forbidden: {path}") from exc
            raise S101Error("FILE_READ_ERROR", f"cannot open {path}: {exc}") from exc
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise S101Error("NOT_REGULAR_FILE", f"not a regular file: {path}")
        if st.st_nlink != 1:
            raise S101Error("HARDLINK_FORBIDDEN", f"hardlink forbidden (st_nlink={st.st_nlink})")
        if st.st_size > max_bytes:
            raise S101Error("FILE_TOO_LARGE", f"file exceeds {max_bytes} bytes")
        chunks: list[bytes] = []
        total = 0
        while True:
            try:
                chunk = os.read(fd, _READ_CHUNK_BYTES)
            except OSError as exc:
                raise S101Error("FILE_READ_ERROR", f"read error on {path}: {exc}") from exc
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise S101Error("FILE_TOO_LARGE", f"stream exceeded {max_bytes} bytes")
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
            raise S101Error("SYMLINK_FORBIDDEN", f"symlink target forbidden: {path}")
        try:
            st_existing = os.lstat(leaf, dir_fd=dir_fd)
            if not stat.S_ISREG(st_existing.st_mode):
                raise S101Error("NOT_REGULAR_FILE", f"target is not a regular file: {path}")
            if st_existing.st_nlink > 1:
                raise S101Error("HARDLINK_FORBIDDEN", f"target hardlink forbidden: {path}")
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
                raise S101Error("FILE_WRITE_ERROR", "short zero write")
            written += n
        os.fsync(fd)
        st_tmp = os.fstat(fd)
        if st_tmp.st_nlink != 1:
            raise S101Error("HARDLINK_FORBIDDEN", "temp file gained extra hardlink")
        os.close(fd)
        fd = -1
        os.replace(tmp_name, leaf, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        tmp_name = ""
        os.fsync(dir_fd)
    except S101Error:
        raise
    except OSError as exc:
        raise S101Error("FILE_WRITE_ERROR", f"atomic write failed: {exc}") from exc
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
        raise S101Error("CRLF_FORBIDDEN", "CR/CRLF bytes forbidden in canonical certificate")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise S101Error("INVALID_UTF8", f"invalid UTF-8: {exc}") from exc
    parsed = parse_strict_json(text)
    cert = audit_certificate_object(parsed)
    expected_bytes = canonical_json_bytes(cert) + b"\n"
    if raw != expected_bytes:
        raise S101Error("NONCANONICAL_BYTES", "certificate file bytes are not canonical LF-terminated JSON")
    return cert


# ---------------------------------------------------------------------------
# Pinned Manifest & Live CPU ptxas/nvdisasm Verifiers
# ---------------------------------------------------------------------------

def verify_upstream_manifest(exp_root: Path) -> dict[str, Any]:
    _validate_path(exp_root)
    verified = 0
    for tid, rel, expected_sha in UPSTREAM_RECEIPT_MANIFEST:
        raw = read_regular_file_bytes(exp_root / rel, max_bytes=MAX_JSON_BYTES)
        actual_sha = hashlib.sha256(raw).hexdigest()
        require_ok(
            hmac.compare_digest(actual_sha, expected_sha),
            "UPSTREAM_SHA_MISMATCH",
            f"upstream receipt SHA mismatch for {tid}",
        )
        verified += 1
    return {
        "status": "UPSTREAM_VERIFIED",
        "receipts_verified": verified,
        "expected_receipts": len(UPSTREAM_RECEIPT_MANIFEST),
    }


def verify_bend_clone(bend_dir: Path) -> dict[str, Any]:
    _validate_path(bend_dir)
    verified = 0
    for rel, expected_sha in BEND2_FILE_MANIFEST:
        raw = read_regular_file_bytes(bend_dir / rel, max_bytes=MAX_JSON_BYTES)
        actual_sha = hashlib.sha256(raw).hexdigest()
        require_ok(
            hmac.compare_digest(actual_sha, expected_sha),
            "BEND_SHA_MISMATCH",
            f"Bend 2 file SHA mismatch for {rel}",
        )
        verified += 1
    return {
        "status": "BEND2_VERIFIED",
        "files_verified": verified,
        "expected_files": len(BEND2_FILE_MANIFEST),
    }


def _scrubbed_tool_env() -> dict[str, str]:
    """Minimal safe subprocess env stripping LEAN_PATH/LEAN_OPTS/ELAN_*/LD_PRELOAD/LD_LIBRARY_PATH/GIT_*."""
    env: dict[str, str] = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    home_val = os.environ.get("HOME")
    if home_val:
        env["HOME"] = home_val
    return env


def verify_loom_clone(loom_dir: Path) -> dict[str, Any]:
    _validate_path(loom_dir)
    git_bin = shutil.which("git")
    require_ok(git_bin is not None, "GIT_NOT_FOUND", "git binary required for --verify-loom")
    clean_env = _scrubbed_tool_env()
    verified = 0
    for git_spec, expected_sha in LOOM_DOC_MANIFEST:
        proc = subprocess.run(
            [str(git_bin), "-C", str(loom_dir), "show", git_spec],
            capture_output=True,
            timeout=30,
            check=False,
            env=clean_env,
        )
        require_ok(proc.returncode == 0, "LOOM_GIT_SHOW_FAILED", f"git show failed for {git_spec}")
        actual_sha = hashlib.sha256(proc.stdout).hexdigest()
        require_ok(
            hmac.compare_digest(actual_sha, expected_sha),
            "LOOM_SHA_MISMATCH",
            f"Loom blob SHA mismatch for {git_spec}",
        )
        verified += 1
    return {
        "status": "LOOM_VERIFIED",
        "docs_verified": verified,
        "expected_docs": len(LOOM_DOC_MANIFEST),
    }


def _find_cuda_cpu_tool(name: str, env_key: str) -> str:
    env_bin = os.environ.get(env_key)
    if env_bin:
        p = Path(env_bin)
        if p.is_file():
            return str(p)
        raise S101Error("CUDA_TOOL_NOT_FOUND", f"{env_key} does not name an existing file")
    found = shutil.which(name)
    if found is not None:
        return found
    opt_bin = Path("/opt/cuda/bin") / name
    if opt_bin.is_file():
        return str(opt_bin)
    raise S101Error("CUDA_TOOL_NOT_FOUND", f"{name} not found on PATH, {env_key}, or /opt/cuda/bin")


_PTXAS_REGS_RE = re.compile(r"Used\s+(\d+)\s+registers.*?(\d+)\s+bytes\s+cmem\[0\]")
_PTXAS_SPILL_RE = re.compile(r"(\d+)\s+bytes\s+stack\s+frame,\s+(\d+)\s+bytes\s+spill\s+stores,\s+(\d+)\s+bytes\s+spill\s+loads")
_SASS_OP_RE = re.compile(r"/\*[0-9a-f]+\*/\s+(?:@!?P\d+\s+)?([A-Z][A-Z0-9_.]+)")


def verify_ptx_kernels_live() -> dict[str, Any]:
    """Compile and disassemble all 3 canonical sm_86 PTX kernels offline on CPU (0 GPU touch)."""
    ptxas_bin = _find_cuda_cpu_tool("ptxas", "PTXAS_BIN")
    nvdisasm_bin = _find_cuda_cpu_tool("nvdisasm", "NVDISASM_BIN")
    clean_env = _scrubbed_tool_env()
    expected_p2 = build_certificate()["payload"]["pillar2_sm86_ptx_sass_audit"]["kernels"]
    key_map = (
        ("atomic_cas_hazard", "s101_atomic_cas_reduce_f32", PTX_KERNEL_SPECS[0][1]),
        ("det_warp_shfl_cce", "s101_det_warp_shfl_reduce_f32", PTX_KERNEL_SPECS[1][1]),
        ("fused_blockh4_dp4a", "s101_fused_blockh4_dp4a_int32", PTX_KERNEL_SPECS[2][1]),
    )
    results: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="s101_ptx_") as td:
        tdir = Path(td)
        for kkey, sym, src in key_map:
            ptx_p = tdir / f"{sym}.ptx"
            cubin_p = tdir / f"{sym}.cubin"
            ptx_p.write_text(src, encoding="utf-8")
            p1 = subprocess.run(
                [ptxas_bin, "--gpu-name=sm_86", "--verbose", str(ptx_p), "-o", str(cubin_p)],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                env=clean_env,
            )
            require_ok(p1.returncode == 0, "PTXAS_COMPILE_FAILED", f"ptxas failed on {sym}: {p1.stderr}")
            m_sp = _PTXAS_SPILL_RE.search(p1.stderr)
            m_rg = _PTXAS_REGS_RE.search(p1.stderr)
            require_ok(m_sp is not None and m_rg is not None, "PTXAS_PARSE_FAILED", f"cannot parse ptxas stats for {sym}")
            assert_stack = int(m_sp.group(1))
            assert_st = int(m_sp.group(2))
            assert_ld = int(m_sp.group(3))
            regs = int(m_rg.group(1))
            cmem0 = int(m_rg.group(2))
            p2 = subprocess.run(
                [nvdisasm_bin, str(cubin_p)],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                env=clean_env,
            )
            require_ok(p2.returncode == 0, "NVDISASM_FAILED", f"nvdisasm failed on {sym}: {p2.stderr}")
            ops: dict[str, int] = {}
            for line in p2.stdout.splitlines():
                mo = _SASS_OP_RE.search(line)
                if mo is not None:
                    op = mo.group(1)
                    ops[op] = ops.get(op, 0) + 1
            exp = expected_p2[kkey]
            extra_checks: list[tuple[bool, str]] = (
                [
                    (ops.get("BSSY", 0) == exp["sass_bssy_count"], "PTX_SASS_DRIFT"),
                    (ops.get("BSYNC", 0) == exp["sass_bsync_count"], "PTX_SASS_DRIFT"),
                    (ops.get("YIELD", 0) == exp["sass_yield_count"], "PTX_SASS_DRIFT"),
                    (ops.get("SHFL.BFLY", 0) == exp["sass_shfl_bfly_count"], "PTX_SASS_DRIFT"),
                ]
                if kkey == "atomic_cas_hazard"
                else (
                    [
                        (ops.get("SHFL.BFLY", 0) == exp["sass_shfl_bfly_count"], "PTX_SASS_DRIFT"),
                        (ops.get("FADD", 0) == exp["sass_fadd_count"], "PTX_SASS_DRIFT"),
                    ]
                    if kkey == "det_warp_shfl_cce"
                    else [
                        (ops.get("FADD", 0) == exp["sass_fadd_count"], "PTX_SASS_DRIFT"),
                        (ops.get("FFMA", 0) == 0, "PTX_SASS_DRIFT"),
                        (ops.get("LDG.E.128", 0) == exp["sass_ldg128_count"], "PTX_SASS_DRIFT"),
                        (ops.get("IADD3", 0) == exp["sass_iadd3_count"], "PTX_SASS_DRIFT"),
                        (ops.get("PRMT", 0) == exp["sass_prmt_count"], "PTX_SASS_DRIFT"),
                        (ops.get("IMAD", 0) == exp["sass_imad_count"], "PTX_SASS_DRIFT"),
                    ]
                )
            )
            _check_invariants(
                [
                    (assert_stack == 0, "PTX_SPILL_NONZERO"),
                    (assert_st == 0, "PTX_SPILL_NONZERO"),
                    (assert_ld == 0, "PTX_SPILL_NONZERO"),
                    (regs == exp["registers"], "PTX_STATS_DRIFT"),
                    (cmem0 == exp["cmem0_bytes"], "PTX_STATS_DRIFT"),
                    (sum(ops.values()) == exp["sass_total_instructions"], "PTX_SASS_DRIFT"),
                    (ops.get("ATOMG.E.CAS.STRONG.GPU", 0) == exp["sass_atomg_cas_count"], "PTX_SASS_DRIFT"),
                    (ops.get("RED.E.ADD.F32.FTZ.RN.STRONG.GPU", 0) == exp["sass_red_add_f32_ftz_count"], "PTX_SASS_DRIFT"),
                    (ops.get("IDP.4A.S8.S8", 0) == exp["sass_idp4a_count"], "PTX_SASS_DRIFT"),
                ]
                + extra_checks
            )
            results[sym] = {"registers": regs, "cmem0_bytes": cmem0, "sass_total": sum(ops.values())}
    return {"status": "PTX_SM86_VERIFIED", "kernels_verified": len(results), "kernels": results}


# ---------------------------------------------------------------------------
# Upgraded R10+ Static Lean 4 Scanner + Live Lean 4.36.0 Axiom Verifier
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
_LEAN4_CHAR_PREV_IDENT = "_'»!?"
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
    if i + 2 < n and source[i + 1] not in ("\\", "\n") and source[i + 2] == "'":
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
    out: list[str] = []
    errors: list[str] = []
    i = 0
    n = len(source)
    depth = 0
    in_str = False
    in_interp = False
    pending_interp = False
    interp_stack: list[int] = []
    raw_hashes = -1
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
        if raw_hashes >= 0:
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
            out.append("  ")
            i += 2
            continue
        if ch == "-" and nxt == "-":
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch.isspace():
            out.append(ch)
            i += 1
            continue
        if ch != '"':
            pending_interp = False
        if interp_stack:
            if ch == "{":
                interp_stack[-1] += 1
                out.append(ch)
                i += 1
                continue
            if ch == "}":
                interp_stack[-1] -= 1
                out.append(ch)
                i += 1
                if interp_stack[-1] == 0:
                    interp_stack.pop()
                    in_interp = True
                continue
        if ch == '"':
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
        elif ch == "'" and (i == 0 or not (source[i - 1].isalnum() or source[i - 1] in _LEAN4_CHAR_PREV_IDENT)):
            char_end = _match_lean4_char_literal_end(source, i, n)
            if char_end is not None:
                out.append(" " * (char_end - i))
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
                out.append(" " * (j - i + 1))
                i = j + 1
            else:
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
                out.append(source[i : w_end + 1])
                i = w_end + 1
                continue
            if word in _LEAN4_INTERP_KEYWORDS:
                pending_interp = True
            out.append(word)
            i = w_end
        else:
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
    if type(source) is not str:
        raise S101Error("INVALID_LEAN_SOURCE", "Lean source must be strict str")
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
        raise S101Error("LEAN_BINARY_NOT_FOUND", "LEAN_BIN does not name an existing file")
    found = shutil.which("lean")
    if found is not None:
        return found
    home_env = os.environ.get("HOME")
    if home_env:
        elan_lean = Path(home_env) / ".elan" / "bin" / "lean"
        if elan_lean.is_file():
            return str(elan_lean)
    raise S101Error("LEAN_BINARY_NOT_FOUND", "lean binary not found on PATH, LEAN_BIN, or $HOME/.elan/bin")


def verify_lean_file(path: Path, *, check_pinned_sha: bool = True) -> dict[str, Any]:
    require_ok(type(check_pinned_sha) is bool, "INVALID_CHECK_PINNED_SHA", "check_pinned_sha must be strict bool")
    raw = read_regular_file_bytes(path, max_bytes=MAX_JSON_BYTES)
    if b"\r" in raw:
        raise S101Error("CRLF_FORBIDDEN", "CR/CRLF forbidden in Lean file")
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise S101Error("INVALID_UTF8", f"invalid UTF-8 in Lean file: {exc}") from exc
    sha = hashlib.sha256(raw).hexdigest()
    if check_pinned_sha and not hmac.compare_digest(sha, LEAN_FILE_SHA256):
        raise S101Error("LEAN_SHA_MISMATCH", "Lean file SHA-256 does not match pinned digest")
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
    parser = argparse.ArgumentParser(description="Track S101 Bend 2, sm_86 PTX & Loom Verifier")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--standalone", action="store_true", help="Run exact-Q oracle and emit canonical JSON")
    mode.add_argument("--write", type=Path, help="Atomically write canonical 0o600 certificate JSON")
    mode.add_argument("--check", type=Path, help="Verify canonical certificate JSON fail-closed")
    mode.add_argument("--verify-lean", type=Path, help="Run R10+ static + live Lean 4.36.0 kernel verification")
    mode.add_argument("--verify-ptx", action="store_true", help="Compile & disassemble 3 sm_86 PTX kernels offline on CPU")
    mode.add_argument("--verify-upstream", type=Path, help="Verify all 5 pinned S52/S68/S86/S94 receipt SHA-256s")
    mode.add_argument("--verify-bend", type=Path, help="Verify all 7 pinned Bend 2 clone file SHA-256s")
    mode.add_argument("--verify-loom", type=Path, help="Verify all 5 pinned siliconcordat/loom git blob SHA-256s")
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
        if args.verify_ptx:
            res = verify_ptx_kernels_live()
            if args.json:
                sys.stdout.buffer.write(canonical_json_bytes(res) + b"\n")
            return 0
        if args.verify_upstream is not None:
            res = verify_upstream_manifest(args.verify_upstream)
            if args.json:
                sys.stdout.buffer.write(canonical_json_bytes(res) + b"\n")
            return 0
        if args.verify_bend is not None:
            res = verify_bend_clone(args.verify_bend)
            if args.json:
                sys.stdout.buffer.write(canonical_json_bytes(res) + b"\n")
            return 0
        if args.verify_loom is not None:
            res = verify_loom_clone(args.verify_loom)
            if args.json:
                sys.stdout.buffer.write(canonical_json_bytes(res) + b"\n")
            return 0
        cert = build_certificate()
        audit_certificate_object(cert)
        out_bytes = canonical_json_bytes(cert) + b"\n"
        sys.stdout.buffer.write(out_bytes)
        return 0
    except S101Error as exc:
        sys.stderr.write(f"ERROR [{exc.code}]: {exc.message}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
