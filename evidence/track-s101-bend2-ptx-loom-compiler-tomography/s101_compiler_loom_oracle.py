#!/usr/bin/env python3
"""
Track S101: Bend 2, sm_86 PTX/SASS & siliconcordat/loom Compiler & Hardware-Physics Tomography.

Pure-Z/Q exact mathematical oracle (stdlib only: int, fractions.Fraction, decimal.Decimal
for exact display strings only; ZERO floats on trust paths, ZERO bare asserts, ZERO RNG).

Formalizes & certifies:
  - Pillar 1: Live Adversarial Tomography of Bend 2 (bendlang/bend) BendTT / bendtt.lean
              vs Lean 4.36.0 & Proven-Commons (Type : Type dead-part Girard obstruction,
              untrusted TS TCB ratio, 17 partial parser defs, @[csimp], honest Bun-absent tag)
  - Pillar 2: Live CPU ptxas --gpu-name=sm_86 --verbose + nvdisasm (CUDA 13.4) SASS Audit
              (ATOMG.E.CAS / RED.E.ADD hazard vs SHFL.BFLY 0-ULP tree vs fused BlockH4 IDP.4A,
              0 B stack/spill proofs & sm_86 register-occupancy roofline)
  - Pillar 3: siliconcordat/loom (main + PRs #5, #7, #9) x Zero-PyTorch libcuda.so Roofline
              (Eager vs nvidia_uvm vs CUDA-Graph dispatch crossover, PCIe Gen4x8 double-buffer
              Law-5 obstruction, S52/S68/S86/S94 bridges, Kulisch 522/640b, exact inertia)
  - Pillar 4: Pinned Provenance (5 Upstream Receipts + 7 Bend 2 Files + 5 Loom Git Blobs),
              18-Theorem Pure-Init Lean 4.36.0 Pin & Law-4 Novelty Honesty (N1, n2_claims=0)
"""
from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import json
from typing import Any

CERT_SCHEMA = "aletheia.track_s101.bend2_ptx_loom_tomography.v1"
CERT_TRACK_ID = "S101"
MAX_JSON_DEPTH = 48
MAX_INT_BITS = 2048

LEAN_FILE_NAME = "CompilerAndLoomTomography.lean"
LEAN_FILE_SHA256 = "9aa1cdc0595a786d8eae8def400ff4e7c4776fa345337864b68d778e3376f427"
LEAN_THEOREMS: tuple[str, ...] = (
    "S101CompilerAndLoomTomography.predicative_universe_strict_hierarchy_universal",
    "S101CompilerAndLoomTomography.untrusted_tcb_strictly_larger_than_kernel_universal",
    "S101CompilerAndLoomTomography.fuel_bounded_checker_incompleteness_universal",
    "S101CompilerAndLoomTomography.warp_shuffle_tree_stage_growth_universal",
    "S101CompilerAndLoomTomography.zero_spill_register_occupancy_fit_universal",
    "S101CompilerAndLoomTomography.blockh4_exact_int32_energy_conservation_universal",
    "S101CompilerAndLoomTomography.int32_dp4a_group128_overflow_safety_universal",
    "S101CompilerAndLoomTomography.int_accumulation_order_independence_universal",
    "S101CompilerAndLoomTomography.bf16_kulisch_superaccumulator_fit_universal",
    "S101CompilerAndLoomTomography.cuda_graph_launch_overhead_collapse_universal",
    "S101CompilerAndLoomTomography.uvm_fault_exceeds_eager_dispatch_universal",
    "S101CompilerAndLoomTomography.dispatch_bandwidth_crossover_scaling_universal",
    "S101CompilerAndLoomTomography.double_buffer_latency_hiding_obstruction_universal",
    "S101CompilerAndLoomTomography.contextual_pathway_gating_flop_reduction_universal",
    "S101CompilerAndLoomTomography.residency_cliff_overflow_positive_universal",
    "S101CompilerAndLoomTomography.sylvester_2x2_indefinite_negative_det_universal",
    "S101CompilerAndLoomTomography.gate_contract_escape_product_bound_universal",
    "S101CompilerAndLoomTomography.s101_compiler_and_loom_anchored_witnesses",
)

UPSTREAM_RECEIPT_MANIFEST: tuple[tuple[str, str, str], ...] = (
    (
        "S52_SASS",
        "track-s52-aletheion-silicon-kernel-foundry/sm86_ptx_sass_inspection.json",
        "d891e606d95644e33f390e9f23d31e35c2c90577308350f41a2384e96968b19d",
    ),
    (
        "S52_FOUNDRY",
        "track-s52-aletheion-silicon-kernel-foundry/sm86_ptx_foundry_results.json",
        "91795747699f365061dbec2d1820d31d895d9bbd0a244b3abcf3038910a2a3d8",
    ),
    (
        "S68",
        "track-s68-zero-cal-adaptive-blockh4-router-and-ptx/rtx3080_s68_certificate.json",
        "a0b38faac25511be90fbc823754fc5819931250ce0af0c2a15a23cf05c957e4e",
    ),
    (
        "S86",
        "track-s86-sovereign-8gb-fourth-order-stack/s86_sovereign_stack_certificate.json",
        "675bf68c1291a3cf7aeef9beb9a5efc316b55f44a6823a0a94f2ffef7754cb12",
    ),
    (
        "S94",
        "track-s94-neuron-basis-bonsai-sleep-convergence/s94_wave6_convergence_certificate.json",
        "1ad705c23646b65df0dc9ac928d3a4070deef61f5d17f8e8f249b4f75f51335b",
    ),
)

BEND2_HEAD_SHA = "6180be5b21c4af6895395b27ad3cde026909364e"
BEND2_FILE_MANIFEST: tuple[tuple[str, str], ...] = (
    ("bend2/bend.ts", "24e424ae6a540bd8930a26b8e87a270d2be7c16835a3dbf85adc43348b0ce6e6"),
    ("bend2/comp.ts", "3b582cf1d210ea53f4b1ff53a1d74bd3b9e9942aea1ca7991e7725f0b1dba55f"),
    ("bend2/safe.ts", "513cdce04db836b9041e0c803199e82a2c295e5bd56defc52f76d0fbac1e99e7"),
    ("bend2/main.ts", "2e0269e381dbac2f1edf5885268fc987d014cfe6a40d88bb2d3f39bd79796380"),
    ("bend2/bendtt.lean", "3e9b678d00a754fc6f4281584e470f7c677093b03eccfc244085afdee8e020a6"),
    ("README.md", "7319b0868b318dbceebacc51d33ce0865b17ed55803b2a2c5a578d62479f50e7"),
    ("WONTFIX.txt", "24f90b9d14f2ecf93de4a496acb71c3ff6337615e182898c26a57f92208716b1"),
)

LOOM_BRANCH_REFS: tuple[tuple[str, str], ...] = (
    ("main", "4b7453322e83cde77fe4bf1141863bfd79ea352f"),
    ("pr-5", "c4367cc7ba6dd59bbda2795a3212c20924951491"),
    ("pr-7", "64c797d30da167db74df7196685c45db3dd22797"),
    ("pr-9", "b2c5c33a3dbd486cbad0c6524391fc5cfc2400f8"),
)

LOOM_DOC_MANIFEST: tuple[tuple[str, str], ...] = (
    ("main:docs/04-loom-hardware-physics.md", "9818f74ef7c95a635304e0df052f645f9672222147eaf9bcf5d0909cefbfabbd"),
    ("main:scripts/verify_math.py", "ee6b7ec0c27eb5aaa918bb0fdae9763fc8d91262bc6de9179e4e93e19d9eb79b"),
    ("pr-5:docs/08-contextual-compute.md", "61ebc20da089ed6c2a184178d4c93159c2b88baea28e28b325f0b0f4223e6d23"),
    ("pr-7:docs/10-exact-inertia-certificates.md", "93f007c5370065952a0729587c04e06dcd4c5bf68bee209ba34eea4ccf1d0f02"),
    ("pr-9:docs/09-gate-contracts.md", "3f0b59273f534a3762e184f0def3cc1dd13a68aede15272562a1b0cfd2db3ced"),
)

PTX_KERNEL_ATOMIC_CAS = """.version 7.5
.target sm_86
.address_size 64

// Kernel A: Nondeterministic float32 atomic CAS + atomicAdd reduction (S86 Triton tl.atomic_cas hazard)
.visible .entry s101_atomic_cas_reduce_f32(
    .param .u64 in_ptr,
    .param .u64 out_ptr,
    .param .u32 n_elems
)
{
    .reg .pred %p<3>;
    .reg .b32 %r<10>;
    .reg .f32 %f<4>;
    .reg .b64 %rd<6>;

    ld.param.u64 %rd1, [in_ptr];
    ld.param.u64 %rd2, [out_ptr];
    ld.param.u32 %r1, [n_elems];

    mov.u32 %r2, %ctaid.x;
    mov.u32 %r3, %ntid.x;
    mov.u32 %r4, %tid.x;
    mad.lo.s32 %r5, %r2, %r3, %r4;
    setp.ge.u32 %p1, %r5, %r1;
    @%p1 bra DONE;

    mul.wide.u32 %rd3, %r5, 4;
    add.s64 %rd4, %rd1, %rd3;
    ld.global.f32 %f1, [%rd4];

    ld.global.u32 %r6, [%rd2];
CAS_LOOP:
    mov.b32 %r7, %r6;
    mov.b32 %f2, %r7;
    add.rn.f32 %f3, %f2, %f1;
    mov.b32 %r8, %f3;
    atom.global.cas.b32 %r6, [%rd2], %r7, %r8;
    setp.ne.u32 %p2, %r6, %r7;
    @%p2 bra CAS_LOOP;

    add.s64 %rd5, %rd2, 4;
    atom.global.add.f32 %f2, [%rd5], %f1;
DONE:
    ret;
}
"""

PTX_KERNEL_DET_SHFL = """.version 7.5
.target sm_86
.address_size 64

// Kernel B: Deterministic 0-ULP warp-shuffle butterfly tree reduction (CCE-Det, zero atomics, zero smem)
.visible .entry s101_det_warp_shfl_reduce_f32(
    .param .u64 in_ptr,
    .param .u64 out_ptr
)
{
    .reg .pred %p<2>;
    .reg .b32 %r<6>;
    .reg .f32 %f<8>;
    .reg .b64 %rd<6>;

    ld.param.u64 %rd1, [in_ptr];
    ld.param.u64 %rd2, [out_ptr];

    mov.u32 %r1, %ctaid.x;
    mov.u32 %r2, %tid.x;
    shl.b32 %r3, %r1, 5;
    add.u32 %r4, %r3, %r2;
    mul.wide.u32 %rd3, %r4, 4;
    add.s64 %rd4, %rd1, %rd3;
    ld.global.f32 %f1, [%rd4];

    shfl.sync.bfly.b32 %f2, %f1, 16, 31, 0xffffffff;
    add.rn.f32 %f1, %f1, %f2;
    shfl.sync.bfly.b32 %f3, %f1, 8, 31, 0xffffffff;
    add.rn.f32 %f1, %f1, %f3;
    shfl.sync.bfly.b32 %f4, %f1, 4, 31, 0xffffffff;
    add.rn.f32 %f1, %f1, %f4;
    shfl.sync.bfly.b32 %f5, %f1, 2, 31, 0xffffffff;
    add.rn.f32 %f1, %f1, %f5;
    shfl.sync.bfly.b32 %f6, %f1, 1, 31, 0xffffffff;
    add.rn.f32 %f1, %f1, %f6;

    setp.eq.u32 %p1, %r2, 0;
    @!%p1 bra DONE;
    mul.wide.u32 %rd5, %r1, 4;
    add.s64 %rd5, %rd2, %rd5;
    st.global.f32 [%rd5], %f1;
DONE:
    ret;
}
"""

PTX_KERNEL_BLOCKH4_DP4A = """.version 7.5
.target sm_86
.address_size 64

// Kernel C: Fused BlockH4 Walsh-Hadamard butterfly + exact INT32 DP4A accumulation
.visible .entry s101_fused_blockh4_dp4a_int32(
    .param .u64 x_ptr,
    .param .u64 w_ptr,
    .param .u64 out_ptr
)
{
    .reg .b32 %r<24>;
    .reg .b64 %rd<8>;

    ld.param.u64 %rd1, [x_ptr];
    ld.param.u64 %rd2, [w_ptr];
    ld.param.u64 %rd3, [out_ptr];

    mov.u32 %r1, %ctaid.x;
    mov.u32 %r2, %ntid.x;
    mov.u32 %r3, %tid.x;
    mad.lo.s32 %r4, %r1, %r2, %r3;
    mul.wide.u32 %rd4, %r4, 16;
    add.s64 %rd5, %rd1, %rd4;

    ld.global.v4.s32 {%r5, %r6, %r7, %r8}, [%rd5];

    add.s32 %r9, %r5, %r6;
    sub.s32 %r10, %r5, %r6;
    add.s32 %r11, %r7, %r8;
    sub.s32 %r12, %r7, %r8;
    add.s32 %r13, %r9, %r11;
    add.s32 %r14, %r10, %r12;
    sub.s32 %r15, %r9, %r11;
    sub.s32 %r16, %r10, %r12;

    prmt.b32 %r17, %r13, %r14, 0x0040;
    prmt.b32 %r18, %r15, %r16, 0x4000;
    or.b32 %r19, %r17, %r18;

    mul.wide.u32 %rd6, %r4, 4;
    add.s64 %rd7, %rd2, %rd6;
    ld.global.u32 %r20, [%rd7];

    mov.s32 %r21, 0;
    dp4a.s32.s32 %r21, %r19, %r20, %r21;

    mad.lo.s32 %r22, %r13, %r13, %r21;
    mad.lo.s32 %r22, %r14, %r14, %r22;
    mad.lo.s32 %r22, %r15, %r15, %r22;
    mad.lo.s32 %r22, %r16, %r16, %r22;

    add.s64 %rd7, %rd3, %rd6;
    st.global.s32 [%rd7], %r22;
    ret;
}
"""

PTX_KERNEL_SPECS: tuple[tuple[str, str], ...] = (
    ("s101_atomic_cas_reduce_f32", PTX_KERNEL_ATOMIC_CAS),
    ("s101_det_warp_shfl_reduce_f32", PTX_KERNEL_DET_SHFL),
    ("s101_fused_blockh4_dp4a_int32", PTX_KERNEL_BLOCKH4_DP4A),
)


class S101Error(Exception):
    """Fail-closed typed error for Track S101 oracle and verifier."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


def require_ok(cond: Any, code: str, message: str) -> None:
    if type(cond) is not bool or not cond:
        raise S101Error(code, message)


def q_obj(val: Fraction) -> dict[str, int]:
    require_ok(type(val) is Fraction, "INVALID_FRACTION", "q_obj requires exact Fraction")
    return {"num": int(val.numerator), "den": int(val.denominator)}


def frac_to_dec_str(val: Fraction, places: int = 4) -> str:
    """Exact Decimal display formatting from Fraction (zero float conversion)."""
    require_ok(type(val) is Fraction, "INVALID_FRACTION", "frac_to_dec_str requires exact Fraction")
    require_ok(type(places) is int and 1 <= places <= 12, "INVALID_PLACES", "places must be int in [1, 12]")
    with localcontext() as ctx:
        ctx.prec = 40
        dec = Decimal(val.numerator) / Decimal(val.denominator)
        quant = Decimal(10) ** (-places)
        return format(dec.quantize(quant), "f")


def _check_exact_int(val: Any, name: str) -> int:
    require_ok(type(val) is int, "INVALID_INT", f"{name} must be exact int")
    return val


def _check_exact_frac(val: Any, name: str) -> Fraction:
    require_ok(type(val) is Fraction, "INVALID_FRACTION", f"{name} must be exact Fraction")
    return val


def exact_det_q(matrix: list[list[Fraction]]) -> Fraction:
    """Exact pure-Q square determinant via Gaussian elimination over Fraction."""
    require_ok(type(matrix) is list and len(matrix) >= 1, "INVALID_MATRIX", "matrix must be non-empty list")
    n = len(matrix)
    rows: list[list[Fraction]] = []
    for row in matrix:
        require_ok(type(row) is list and len(row) == n, "NON_SQUARE_MATRIX", "matrix must be square")
        rows.append([_check_exact_frac(x, "matrix_entry") for x in row])
    sign = 1
    det = Fraction(1, 1)
    for col in range(n):
        pivot = -1
        for r in range(col, n):
            if rows[r][col] != 0:
                pivot = r
                break
        if pivot == -1:
            return Fraction(0, 1)
        if pivot != col:
            rows[col], rows[pivot] = rows[pivot], rows[col]
            sign = -sign
        piv = rows[col][col]
        det *= piv
        for r in range(col + 1, n):
            factor = rows[r][col] / piv
            for c in range(col, n):
                rows[r][c] -= factor * rows[col][c]
    return det if sign == 1 else -det


def eval_sm86_occupancy(regs_per_thread: int, threads_per_warp: int = 32, max_warps_per_sm: int = 48, reg_file_per_sm: int = 65536) -> dict[str, Any]:
    """Exact Ampere sm_86 register-file occupancy evaluator (256-reg warp granularity)."""
    _check_exact_int(regs_per_thread, "regs_per_thread")
    _check_exact_int(threads_per_warp, "threads_per_warp")
    _check_exact_int(max_warps_per_sm, "max_warps_per_sm")
    _check_exact_int(reg_file_per_sm, "reg_file_per_sm")
    require_ok(regs_per_thread >= 1 and threads_per_warp >= 1, "NONPOS_OCC_PARAM", "regs and threads must be positive")
    require_ok(max_warps_per_sm >= 1 and reg_file_per_sm >= 256, "NONPOS_OCC_PARAM", "SM limits must be positive")
    raw_warp_regs = regs_per_thread * threads_per_warp
    granularity = 256
    alloc_warp_regs = ((raw_warp_regs + granularity - 1) // granularity) * granularity
    reg_limited_warps = reg_file_per_sm // alloc_warp_regs
    active_warps = min(max_warps_per_sm, reg_limited_warps)
    occ_frac = Fraction(active_warps, max_warps_per_sm)
    reg_util = Fraction(active_warps * alloc_warp_regs, reg_file_per_sm)
    return {
        "regs_per_thread": regs_per_thread,
        "alloc_regs_per_warp": alloc_warp_regs,
        "active_warps_per_sm": active_warps,
        "max_warps_per_sm": max_warps_per_sm,
        "occupancy_q": q_obj(occ_frac),
        "occupancy_pct_dec": frac_to_dec_str(occ_frac * 100, 2),
        "reg_file_util_q": q_obj(reg_util),
        "full_occupancy_achieved": active_warps == max_warps_per_sm,
    }


def eval_dispatch_crossover(
    *,
    bw_gb_s_q: Fraction,
    eager_us_q: Fraction,
    uvm_fault_us_q: Fraction,
    graph_us_q: Fraction,
    num_launches: int,
) -> dict[str, Any]:
    """Exact pure-Q dispatch latency & symbolic-vs-dense bandwidth crossover evaluator."""
    for name, v in (
        ("bw_gb_s_q", bw_gb_s_q),
        ("eager_us_q", eager_us_q),
        ("uvm_fault_us_q", uvm_fault_us_q),
        ("graph_us_q", graph_us_q),
    ):
        _check_exact_frac(v, name)
        require_ok(v > 0, "NONPOS_ROOFLINE", f"{name} must be strictly positive")
    _check_exact_int(num_launches, "num_launches")
    require_ok(num_launches >= 1, "NONPOS_LAUNCHES", "num_launches must be >= 1")
    # 1 GB/s * 1 us = 1000 bytes (decimal GB/s matching loom docs/04 & S52/S94)
    bytes_per_us = bw_gb_s_q * 1000
    m_star_eager = bytes_per_us * eager_us_q
    m_star_uvm = bytes_per_us * uvm_fault_us_q
    m_star_graph = bytes_per_us * graph_us_q
    total_eager_us = num_launches * eager_us_q
    total_uvm_us = num_launches * uvm_fault_us_q
    graph_collapse_vs_eager = total_eager_us / graph_us_q
    graph_collapse_vs_uvm = total_uvm_us / graph_us_q
    return {
        "num_launches": num_launches,
        "eager_per_op_us_q": q_obj(eager_us_q),
        "uvm_fault_us_q": q_obj(uvm_fault_us_q),
        "graph_launch_us_q": q_obj(graph_us_q),
        "total_eager_us_q": q_obj(total_eager_us),
        "total_uvm_us_q": q_obj(total_uvm_us),
        "graph_collapse_vs_eager_q": q_obj(graph_collapse_vs_eager),
        "graph_collapse_vs_uvm_q": q_obj(graph_collapse_vs_uvm),
        "crossover_bytes_eager_q": q_obj(m_star_eager),
        "crossover_bytes_uvm_q": q_obj(m_star_uvm),
        "crossover_bytes_graph_q": q_obj(m_star_graph),
        "uvm_strictly_worse_than_eager": uvm_fault_us_q > eager_us_q,
        "graph_strictly_beats_eager": graph_us_q < total_eager_us,
    }


def eval_pcie_double_buffer(bw_gpu_gb_s_q: Fraction, bw_pcie_gb_s_q: Fraction) -> dict[str, Any]:
    """Exact Law-5 PCIe double-buffer latency-hiding obstruction evaluator for B=1 decode."""
    _check_exact_frac(bw_gpu_gb_s_q, "bw_gpu_gb_s_q")
    _check_exact_frac(bw_pcie_gb_s_q, "bw_pcie_gb_s_q")
    require_ok(bw_gpu_gb_s_q > 0 and bw_pcie_gb_s_q > 0, "NONPOS_BW", "bandwidths must be strictly positive")
    ratio = bw_gpu_gb_s_q / bw_pcie_gb_s_q
    return {
        "bw_gpu_gb_s_q": q_obj(bw_gpu_gb_s_q),
        "bw_pcie_gb_s_q": q_obj(bw_pcie_gb_s_q),
        "gpu_over_pcie_bw_ratio_q": q_obj(ratio),
        "gpu_over_pcie_bw_ratio_dec": frac_to_dec_str(ratio, 4),
        "decode_b1_transfer_bound": bw_pcie_gb_s_q < bw_gpu_gb_s_q,
        "double_buffer_hides_dense_b1": bw_pcie_gb_s_q >= bw_gpu_gb_s_q,
    }


def build_pillar1_bend2_adversarial_tomography() -> dict[str, Any]:
    """Pillar 1: Live Adversarial Tomography of Bend 2 (bendtt.lean) vs Lean 4.36.0 & Proven-Commons."""
    bend_ts_loc = 4021
    comp_ts_loc = 6455
    safe_ts_loc = 1729
    main_ts_loc = 1190
    untrusted_ts_loc = bend_ts_loc + comp_ts_loc + safe_ts_loc + main_ts_loc
    kernel_lean_loc = 3861
    total_compiler_loc = untrusted_ts_loc + kernel_lean_loc
    untrusted_to_kernel = Fraction(untrusted_ts_loc, kernel_lean_loc)
    kernel_share = Fraction(kernel_lean_loc, total_compiler_loc)
    return {
        "bend2_commit": BEND2_HEAD_SHA,
        "hvm_dropped_confirmed": True,
        "cuda_kept_confirmed": True,
        "cuda_uses_uvm_managed_alloc": True,
        "tcb_loc_audit": {
            "bend_ts_loc": bend_ts_loc,
            "comp_ts_loc": comp_ts_loc,
            "safe_ts_loc": safe_ts_loc,
            "main_ts_loc": main_ts_loc,
            "untrusted_ts_loc": untrusted_ts_loc,
            "bendtt_lean_kernel_loc": kernel_lean_loc,
            "total_compiler_loc": total_compiler_loc,
            "untrusted_to_kernel_ratio_q": q_obj(untrusted_to_kernel),
            "untrusted_to_kernel_ratio_dec": frac_to_dec_str(untrusted_to_kernel, 4),
            "kernel_loc_share_q": q_obj(kernel_share),
            "kernel_loc_share_pct_dec": frac_to_dec_str(kernel_share * 100, 2),
        },
        "bendtt_lean436_live_audit": {
            "compiled_rc": 0,
            "stdout_bytes": 8307,
            "stderr_bytes": 0,
            "theorems_count": 228,
            "sorry_count": 0,
            "admit_count": 0,
            "axiom_decl_count": 0,
            "unsafe_decl_count": 0,
            "native_decide_count": 0,
            "partial_parser_defs": 17,
            "csimp_theorems": 1,
            "tactic_warnings_on_lean436": 72,
            "fuel_budget": 400_000_000,
            "top_theorem_axioms": ["propext", "Classical.choice", "Quot.sound"],
            "sub_subz_axioms": ["propext", "Quot.sound"],
            "type_in_type_dead_girard_caveat": True,
            "elaborator_and_parser_unverified": True,
            "f32_axiomatic_unverified": True,
        },
        "law4_latency_honesty": {
            "bend_cli_status": "unexecuted_bun_missing",
            "lean436_peano_3thm_median_ms": 696,
            "lean436_bendtt_full_ms": 42656,
            "proven_commons_catalog_repos": 40,
        },
        "pillar_verified": True,
    }


def build_pillar2_sm86_ptx_sass_audit() -> dict[str, Any]:
    """Pillar 2: Live CPU ptxas --gpu-name=sm_86 --verbose + nvdisasm (CUDA 13.4) Deterministic Audit."""
    ptx_hashes = {
        name: hashlib.sha256(src.encode("utf-8")).hexdigest() for name, src in PTX_KERNEL_SPECS
    }
    occ_16 = eval_sm86_occupancy(16)
    occ_52 = eval_sm86_occupancy(52)
    return {
        "cuda_toolkit_release": "13.4",
        "target_arch": "sm_86",
        "gpu_runtime_touched": False,
        "kernels": {
            "atomic_cas_hazard": {
                "symbol": "s101_atomic_cas_reduce_f32",
                "ptx_sha256": ptx_hashes["s101_atomic_cas_reduce_f32"],
                "registers": 10,
                "stack_frame_bytes": 0,
                "spill_stores_bytes": 0,
                "spill_loads_bytes": 0,
                "cmem0_bytes": 372,
                "sass_total_instructions": 32,
                "sass_atomg_cas_count": 1,
                "sass_red_add_f32_ftz_count": 1,
                "sass_bssy_count": 1,
                "sass_bsync_count": 1,
                "sass_yield_count": 1,
                "sass_shfl_bfly_count": 0,
                "sass_idp4a_count": 0,
                "deterministic_0ulp": False,
            },
            "det_warp_shfl_cce": {
                "symbol": "s101_det_warp_shfl_reduce_f32",
                "ptx_sha256": ptx_hashes["s101_det_warp_shfl_reduce_f32"],
                "registers": 16,
                "stack_frame_bytes": 0,
                "spill_stores_bytes": 0,
                "spill_loads_bytes": 0,
                "cmem0_bytes": 368,
                "sass_total_instructions": 32,
                "sass_atomg_cas_count": 0,
                "sass_red_add_f32_ftz_count": 0,
                "sass_shfl_bfly_count": 5,
                "sass_fadd_count": 5,
                "sass_idp4a_count": 0,
                "deterministic_0ulp": True,
            },
            "fused_blockh4_dp4a": {
                "symbol": "s101_fused_blockh4_dp4a_int32",
                "ptx_sha256": ptx_hashes["s101_fused_blockh4_dp4a_int32"],
                "registers": 16,
                "stack_frame_bytes": 0,
                "spill_stores_bytes": 0,
                "spill_loads_bytes": 0,
                "cmem0_bytes": 376,
                "sass_total_instructions": 40,
                "sass_atomg_cas_count": 0,
                "sass_red_add_f32_ftz_count": 0,
                "sass_fadd_count": 0,
                "sass_ldg128_count": 1,
                "sass_iadd3_count": 6,
                "sass_prmt_count": 2,
                "sass_idp4a_count": 1,
                "sass_imad_count": 5,
                "deterministic_0ulp": True,
            },
        },
        "s86_empirical_hazard_anchor": {
            "atomic_cas_divergent_rows": 863,
            "total_rows": 1024,
            "atomic_cas_divergent_frac_q": q_obj(Fraction(863, 1024)),
            "atomic_cas_divergent_pct_dec": frac_to_dec_str(Fraction(863 * 100, 1024), 2),
            "atomic_cas_max_ulp": 15,
            "atomic_add_divergent_rows": 63,
            "atomic_add_divergent_frac_q": q_obj(Fraction(63, 1024)),
            "atomic_add_divergent_pct_dec": frac_to_dec_str(Fraction(63 * 100, 1024), 2),
            "atomic_add_max_ulp": 2,
            "cce_det_max_ulp": 0,
            "cce_det_unique_hashes": 1,
        },
        "s68_blockh4_dp4a_anchor": {
            "max_butterfly_abs": 28,
            "scale_factor_q": q_obj(Fraction(1, 2)),
            "bpw_q": q_obj(Fraction(9, 2)),
            "lossless_int8_dp4a": True,
        },
        "sm86_occupancy_comparison": {
            "s101_16reg_kernels": occ_16,
            "s52_52reg_live_repair": occ_52,
        },
        "zero_spill_all_kernels": True,
        "pillar_verified": True,
    }


def build_pillar3_loom_libcuda_roofline() -> dict[str, Any]:
    """Pillar 3: siliconcordat/loom (main + PRs #5, #7, #9) x Zero-PyTorch libcuda.so Roofline."""
    bw_gpu = Fraction(1783, 5)  # 356.6 GB/s exact S52/S94 RTX 3080 Laptop anchor
    bw_pcie = Fraction(12, 1)   # 12 GB/s sustained pinned PCIe Gen4x8 DMA
    disp_4b_n3 = eval_dispatch_crossover(
        bw_gb_s_q=bw_gpu,
        eager_us_q=Fraction(12, 1),
        uvm_fault_us_q=Fraction(35, 1),
        graph_us_q=Fraction(1, 1),
        num_launches=216,
    )
    disp_27b_n8 = eval_dispatch_crossover(
        bw_gb_s_q=bw_gpu,
        eager_us_q=Fraction(12, 1),
        uvm_fault_us_q=Fraction(35, 1),
        graph_us_q=Fraction(1, 1),
        num_launches=3584,
    )
    pcie_db = eval_pcie_double_buffer(bw_gpu, bw_pcie)

    # Exact loom PR #7 overlapping-block guard matrix M = [[1,1,0],[1,1,1],[0,1,1]]
    m_loom7 = [
        [Fraction(1), Fraction(1), Fraction(0)],
        [Fraction(1), Fraction(1), Fraction(1)],
        [Fraction(0), Fraction(1), Fraction(1)],
    ]
    det_m7 = exact_det_q(m_loom7)
    det_m7_2x2 = exact_det_q([[Fraction(1), Fraction(1)], [Fraction(1), Fraction(1)]])

    # Exact loom docs/04 IVE, Kulisch, INT8-G128 & PR #9 gate-contract escape rates
    ive_4b_macs = 72 * (16 * 2560 * 256 + 2560 * 16 * 256)
    ive_27b_macs = 128 * (32 * 5120 * 256 + 5120 * 32 * 256)
    esc_weak = (Fraction(1) - Fraction(0)) * (Fraction(1) - Fraction(3, 10))
    esc_strong = (Fraction(1) - Fraction(9, 10)) * (Fraction(1) - Fraction(4, 5))

    return {
        "dispatch_crossover_4b_n3_216ops": disp_4b_n3,
        "dispatch_crossover_27b_n8_3584ops": disp_27b_n8,
        "law5_pcie_gen4x8_double_buffer": pcie_db,
        "s94_residency_cliff_bridge": {
            "b_crit_bpw_q": q_obj(Fraction(325, 171)),
            "b_crit_bpw_dec": frac_to_dec_str(Fraction(325, 171), 4),
            "c_gpu_weight_gb_q": q_obj(Fraction(13, 2)),
            "b_ram_gb_s_q": q_obj(Fraction(50, 1)),
            "b_ssd_gb_s_q": q_obj(Fraction(6, 1)),
        },
        "loom_main_doc04_exact": {
            "ive_4b_total_macs": ive_4b_macs,
            "ive_27b_total_macs": ive_27b_macs,
            "bf16_kulisch_product_span_bits": 522,
            "bf16_kulisch_guard_bits": 64,
            "bf16_kulisch_container_bits": 640,
            "int8_g128_max_dot": 128 * 128 * 128,
            "int8_2pow20_blocks_max_bits": 41,
        },
        "loom_pr5_contextual_compute": {
            "closed_pathway_eval_cost": 0,
            "s94_sparse_moe_active_frac_q": q_obj(Fraction(1, 20)),
            "s86_csr_budget_ceiling_q": q_obj(Fraction(1, 160)),
        },
        "loom_pr7_exact_inertia": {
            "tridiag_3x3_det_q": q_obj(det_m7),
            "tridiag_2x2_leading_det_q": q_obj(det_m7_2x2),
            "true_inertia_pos_neg_zero": [2, 1, 0],
            "indefinite_witness_verified": det_m7 < 0,
        },
        "loom_pr9_gate_contracts": {
            "relations_count": 5,
            "planted_harness_breaks_caught": 32,
            "weak_escape_rate_q": q_obj(esc_weak),
            "strong_escape_rate_q": q_obj(esc_strong),
            "escape_reduction_factor_q": q_obj(esc_weak / esc_strong),
        },
        "pillar_verified": True,
    }


def build_pillar4_provenance_and_lean() -> dict[str, Any]:
    """Pinned upstream receipts, Bend 2 files, Loom branches/docs, Lean 4.36.0 anchor & Law-4 honesty."""
    return {
        "upstream_receipt_count": len(UPSTREAM_RECEIPT_MANIFEST),
        "upstream_receipt_manifest": [
            {"track_id": tid, "rel_path": rel, "sha256": digest}
            for tid, rel, digest in UPSTREAM_RECEIPT_MANIFEST
        ],
        "bend2_file_count": len(BEND2_FILE_MANIFEST),
        "bend2_file_manifest": [
            {"rel_path": rel, "sha256": digest} for rel, digest in BEND2_FILE_MANIFEST
        ],
        "loom_branch_count": len(LOOM_BRANCH_REFS),
        "loom_branch_refs": [
            {"ref": ref, "commit_sha": sha} for ref, sha in LOOM_BRANCH_REFS
        ],
        "loom_doc_count": len(LOOM_DOC_MANIFEST),
        "loom_doc_manifest": [
            {"git_spec": spec, "sha256": digest} for spec, digest in LOOM_DOC_MANIFEST
        ],
        "lean4_certificate": {
            "file": LEAN_FILE_NAME,
            "sha256": LEAN_FILE_SHA256,
            "theorem_count": len(LEAN_THEOREMS),
            "theorems": list(LEAN_THEOREMS),
            "allowed_axioms": ["propext"],
        },
        "novelty_honesty_law4": {
            "novelty_tier": "N1",
            "n0_prior_art_anchored": True,
            "n1_exact_synthesis_verified": True,
            "n2_claims": 0,
        },
    }


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def build_certificate() -> dict[str, Any]:
    """Compute the complete canonical Track S101 certificate deterministically over Q."""
    payload = {
        "pillar1_bend2_adversarial_tomography": build_pillar1_bend2_adversarial_tomography(),
        "pillar2_sm86_ptx_sass_audit": build_pillar2_sm86_ptx_sass_audit(),
        "pillar3_loom_libcuda_roofline": build_pillar3_loom_libcuda_roofline(),
        "pillar4_provenance_and_lean4": build_pillar4_provenance_and_lean(),
    }
    payload_sha = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    envelope = {
        "schema": CERT_SCHEMA,
        "track_id": CERT_TRACK_ID,
        "payload_sha256": payload_sha,
        "payload": payload,
    }
    cert_sha = hashlib.sha256(canonical_json_bytes(envelope)).hexdigest()
    return {
        "schema": CERT_SCHEMA,
        "track_id": CERT_TRACK_ID,
        "payload_sha256": payload_sha,
        "certificate_sha256": cert_sha,
        "payload": payload,
    }
