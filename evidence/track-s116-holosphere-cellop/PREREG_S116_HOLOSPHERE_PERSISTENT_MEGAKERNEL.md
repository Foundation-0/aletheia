# `PREREG-S116`: Bare-Metal `sm_86` `switch`-Free `CellOp` vs. `switch(opcode)` Persistent Cooperative Megakernel VM & L2/SRAM-Resident `Siliquant` `A_16 Block-H4` `mma.sync` Prototype (`EXP-Q23a..d`)

- **Document ID:** `PREREG-S116-HOLOSPHERE-PERSISTENT-MEGAKERNEL-V1`
- **Status:** **IMMUTABLE PRE-RUN LOCK** (written & SHA-256-logged in `verification/AUDIT_LOG.md` strictly BEFORE any GPU execution or benchmark run)
- **Date (UTC):** `2026-11-25`
- **Owner:** `fractals-probe` (`Track S116` / `EXP-Q23a..d`, `Moissanite-Labs/silikernels#2` bare-metal megakernel foundry)
- **Provenance & Lineage:** Directly operationalizes `@orda-aska`'s full `Moissanite-Labs/silikernels#2` architecture — BOTH the initial Model-as-Runtime persistent VM AND the follow-up diagnosis of **Together AI's Fixed Launch Envelope Trap** proposing a **`switch`-free Single-Opcode `uniform_cell_megakernel` (`CellOp`)** with pointer-swapped specialist tiles (`scribe -> weaver -> prover`) — fused atop our verified `Track S68` (`Siliquant` `A_16 Block-H4`), `Track S106` (Hopf-$S^3$), `Track S107` ($SU(2)$ Holonomy & Safe-Hopf looping), `Track S110` (`Cayley2x2`), `Track S114` (`sm_86` `su2_holonomy_scan_sm86.cu` + `Lean 4.36.0` `16 B` $\Pi_{t_0}$ rollback theorem `p5_su2_holonomy_repoisoning_and_16b_rollback`), and `Track S115` (`SiliSense` non-acoustic `uncore_w` copula telemetry).
- **Target Hardware (`GA104M` Consumer Ampere `sm_86`):** NVIDIA GeForce RTX 3080 Laptop GPU (`GA104M`, Compute Capability `8.6`, `48` Streaming Multiprocessors, `256 KiB` Register File / SM = `12.000 MiB` RF, up to `100 KiB` configurable Shared Memory / SM = `4,800 KiB` = `4.6875 MiB` SMEM, `4.000 MiB` unified L2 cache -> **`20.6875 MiB` total on-chip SRAM**, `8 GiB` GDDR6 off-chip memory with measured empirical STREAM Triad bandwidth **`356.6 GB/s`**, `110W` AC `P0`).
- **Execution Discipline:** Phase 1 is strictly CPU + `nvcc -arch=sm_86 --ptxas-options=-v` compile & `cuobjdump --dump-sass` verification (`CUDA_VISIBLE_DEVICES=""`, `0` GPU runtime calls). Phase 2 Zone-B RTX 3080 runs execute strictly AFTER this lock is hashed in `verification/AUDIT_LOG.md`, Phase-1 preflight passes `3-mode -I`, and `mlos gpu-lease` + `mlos stamp-run --zone B --require-gpu` are acquired cleanly (`HF_HUB_OFFLINE=1`, `WEIGHTS=0`, `ELF=0`, `0` GitHub pushes without sign-off).

---

## 1. Honest `sm_86` Hardware Scope Boundaries & Novelty Classification (`N1`)

### 1.1 Explicit Law-4 `GA104M` (`sm_86`) Hardware Boundaries (Non-Overclaiming Scope)
`Moissanite-Labs/silikernels#2` analyzes a datacenter Hopper/Blackwell vision alongside NVIDIA's physical silicon hard floor. On our single consumer Ampere laptop GPU (`GA104M`, `sm_86`), three hardware features are physically absent or cryptographically locked and are **explicitly scoped out** rather than simulated as claims:
1. **No GPUDirect RDMA / Multi-GPU NVSHMEM:** Single-GPU consumer `GA104M` lacks an RDMA-capable NIC peer mapping and multi-GPU NVLink/NVSHMEM fabric. We replace host-to-GPU ingestion faithfully for single-GPU silicon with a **zero-copy PCIe host-pinned mapped raw UTF-8 byte ring buffer** (`cudaHostAllocMapped` + `cudaHostGetDevicePointer` + PTX system-scope `ld.acquire.sys.global.u32` / `st.release.sys.global.u32`), achieving **`0` host CUDA kernel launches per token** while remaining 100% honest about single-GPU PCIe transport.
2. **No Hopper/Blackwell TMA or `wgmma`:** Ampere `sm_86` lacks Hopper `cp.async.bulk.tensor` (TMA) and warpgroup `wgmma.mma_async`. We use native Ampere hardware equivalents: **`cp.async.ca.shared.global`** (`LDGSTS` double-buffered global-to-shared transfer), warp-synchronous **`mma.sync.aligned.m16n8k32.row.col.s32.s8.s8.s32`** (`IMMA.16832.S8.S8`, `2×` peak INT8 TOPS vs BF16) + **`mma.sync.aligned.m16n8k16.row.col.f32.bf16.bf16.f32`** (`HMMA.16816.F32.BF16`) + **`dp4a.s32.s32`** (`IDP.4A.S8.S8`), and **`cudaLaunchCooperativeKernel`** (`48` persistent CTAs = `1` CTA/SM with `cooperative_groups::this_grid().sync()`).
3. **No Unsigned GSP Microcode / Raw SASS Binary Injection:** NVIDIA cryptographically signs GSP firmware and GigaThread Engine microcode. We do **not** bypass firmware signatures or inject undocumented hand-patched SASS binaries; persistent residency is achieved strictly via sanctioned CUDA Cooperative Groups + documented inline PTX audited by `nvcc --ptxas-options=-v` (`0 B` spills) and `cuobjdump --dump-sass`.

### 1.2 Honest Novelty Classification (`N1`, `n2_claims = 0`)
- **Established Prior Art (`N0`):** Persistent GPU megakernels (Stanford Hazy Research Megakernels 2025; ForgeMegakernel; Together AI Fixed Launch Envelope Postmortem), byte-level tokenizer-free models (Meta Byte Latent Transformer / BLT), hyperspherical transformers (`nGPT`), linear/fast-weight delta rules, Ampere `cp.async` + `mma.sync` / `dp4a` pipelines, and tile-swizzled INT4 weight dequantization (Marlin / FlashInfer / AWQ) are established `N0` primitives.
- **Scoped Contribution (`N1`):**
  1. Direct controlled `sm_86` empirical comparison between a **`switch`-free Single-Opcode `uniform_cell_megakernel_sm86` (`CellOp`)** and a matched **`switch(opcode)` persistent megakernel VM (`holosphere_persistent_vm_sm86`)** to measure Together AI's Fixed Launch Envelope register/occupancy/latency gap directly on Ampere silicon;
  2. Native **`Siliquant` `A_16 Block-H4` -> `mma.sync.aligned.m16n8k32` (INT8 Tensor Core) & `dp4a.s32.s32` bridge**: because 4-point Sylvester Hadamard $H_4 [c_0, c_1, c_2, c_3]^T$ on signed 4-bit nibbles satisfies $|r_i| \le 28 \le 127$ (symmetric `[-7, +7]`) and $|r_i| \le 32 \le 127$ (two's complement `[-8, +7]`), `Block-H4` unpacks inline into exact packed `int8` words with **zero FP16 conversion**, verified live by `5 × __popc` Extended Hamming `[16, 11, 4]` parity on the 16 nibble LSBs with fail-closed zero-clamping;
  3. **Pointer-swapped specialist tiles (`scribe -> weaver -> prover`)** guarded by our `Lean 4.36.0`-proved **`16 B` $\Pi_{t_0}$ holonomy rollback checkpoint** (`p5_su2_holonomy_repoisoning_and_16b_rollback`), preventing non-decaying right-coset $R_{\text{err}} \in SU(2)$ error on speculative rollbacks or specialist transitions;
  4. Preregistered `CS-08` quality, super-HBM residency (`> 356.6 GB/s`), and `SiliSense` (`Track S115`) `uncore_w`/IRQ jitter falsification gates.

---

## 2. Exact `GA104M` On-Chip SRAM / L2 Residency Budget

To break the off-chip GDDR6 bandwidth straw (`356.6 GB/s` empirical STREAM Triad on `GA104M`), the active unique model weights of a weight-tied looped `HoloSphere` core must fit strictly inside the `4.000 MiB` L2 cache (`+ 4.6875 MiB` SMEM `+ 12.000 MiB` RF = `20.6875 MiB` aggregate on-chip SRAM):

| Component (`d_model=256`, `n_heads=8`, `d_ff=384`, `L_unique=4`, looped `R=3` -> `12L`, `V=256` UTF-8) | Unique Parameters | `BF16` (`16 bpp`) | `A_16 Block-H4` / Swizzled `INT4` (`4.50 bpp`) | `siliquant` `A_16` Binary-Sign (`2.00 bpp`) |
| --- | ---: | ---: | ---: | ---: |
| Attention / Fast-Slow Core (`4 * 4 * 256 * 256`) | `1,048,576` | `2.000 MiB` | `0.563 MiB` | `0.250 MiB` |
| Holonomy `W_omega` + `Cayley2x2` (`4 * (256*192 + 256*128)`) | `327,680` | `0.625 MiB` | `0.176 MiB` | `0.078 MiB` |
| Gated FFN (`4 * 3 * 256 * 384`) | `1,179,648` | `2.250 MiB` | `0.633 MiB` | `0.281 MiB` |
| Tied Byte Embed / LM-Head (`256 * 256`) | `65,536` | `0.125 MiB` | `0.035 MiB` | `0.016 MiB` |
| **Total Unique Core** | **`2,621,440`** | **`5.000 MiB`** | **`1.406 MiB`** | **`0.625 MiB`** |
| **Share of `GA104M` `4.000 MiB` L2 Cache** | — | `125.0%` (spills L2) | **`35.2%` (L2-resident!)** | **`15.6%` (L2-resident!)** |
| **Share of `GA104M` `20.6875 MiB` Total On-Chip SRAM** | — | `24.2%` | **`6.8%`** | **`3.0%`** |

At `T=512` batch-1 decode, `4` unique-layer BF16 KV caches add `2.000 MiB`, keeping **`1.406 + 2.000 = 3.406 MiB < 4.000 MiB` L2** (`85.2%` of L2 alone, before even counting `4.6875 MiB` SMEM).

---

## 3. Dual Megakernel Architecture: `switch`-Free `CellOp` vs. `switch(opcode)` Control

To test Together AI's Fixed Launch Envelope Trap directly on `sm_86`, `holosphere_megakernel_sm86.cu` compiles BOTH cooperative persistent megakernels into the same translation unit at **`0 B` stack / `0 B` spills**:

### 3.1 `switch`-Free Single-Opcode `uniform_cell_megakernel_sm86` (`S116CellOp`, `__launch_bounds__(256, 1)`)
- **Zero `switch(opcode)` branching:** Every descriptor in VRAM is an identical `32`-byte aligned `S116CellOp` (`weight_blockh4_ptr`, `weight_scale_ptr`, `in_slot`, `out_slot`, `norm_group`, `flags`, `eigen_alpha`, `decay_eta`).
- **`cp.async` Double-Buffering:** Prefetches `CellOp[pc + 1]`'s `A_16 Block-H4` weight tile (`128 B` = `16 × uint64_t` = `8` columns × `32` `s8` weights) into `smem_w_buf[(pc & 1) ^ 1]` via `cp.async.ca.shared.global` while computing `CellOp[pc]`.
- **Inline `Block-H4` -> `IMMA.16832.S8.S8`:** Verifies `[16, 11, 4]` Extended Hamming parity on the 16 nibble LSBs (`5 × __popc`), applies fail-closed zero-clamping on corruption, executes 4-point Sylvester $H_4$ butterfly directly into packed `4×int8` registers, and fires `mma.sync.aligned.m16n8k32.row.col.s32.s8.s8.s32` (applying `0.5f * scale * x_scale` once on the `s32 -> f32` epilogue!).
- **Persistent Register Fast-Weight State (`S_fast`), `SU(2)` Holonomy + `16 B` $\Pi_{t_0}$ Rollback, & Warp Retraction:** Updates register-resident `S_fast` via delta rule (`decay_eta`), performs spherical tangent blending (`eigen_alpha`), executes covariant $SU(2)$ holonomy with `16 B` `float4` checkpoint save/restore (`S116_CELL_CKPT_SAVE` / `S116_CELL_CKPT_ROLLBACK`) for zero-poisoning specialist pointer swaps (`scribe -> weaver -> prover`), and retracts onto `S^3`/`S^15`/`S^31` via `warp_local_norm_quad`.

### 3.2 `switch(opcode)` Control (`holosphere_persistent_vm_sm86`, `S116Inst`, `__launch_bounds__(128, 1)`)
- Multi-opcode VM dispatching across `9` opcodes (`0..8`: `OP_HALT`, `OP_EMBED_BYTE`, `OP_MMA_TILE` [`HMMA.16816.F32.BF16`], `OP_WARP_NORM_S3_S15_S31`, `OP_SU2_HOLONOMY_STEP`, `OP_CAYLEY2X2`, `OP_SILIQUANT_A16_DEQUANT`, `OP_SAMPLE_ARGMAX`, `OP_RING_COMMIT`) polling the same `cudaHostAllocMapped` UTF-8 byte ring buffer (`0..255`).
- Directly exposes the worst-case register envelope inflation (`ptxas` register count & active-warp ceiling) vs `uniform_cell_megakernel_sm86`!

---

## 4. Locked Falsifiable Hypotheses & Literal Kill Gates (`H16a..d`)

All seeds (`[42, 137, 2026]`), disjoint UTF-8 byte splits (matching `Track S107`/`S114` discipline), parameter parity (`±0.5%`), equal-wall-clock `CS-08` budgets, and paired statistics (`mean ± SE`, paired `z`-score, Holm-corrected `p_Holm`) are frozen prior to GPU execution.

### `H16a` (`EXP-Q23a`) — `switch`-Free `CellOp` vs. `switch(opcode)` Persistent Cooperative `sm_86` Megakernel Latency, Fixed-Envelope Registers, Parity, & Zero-Spill Gate
- **Claim:** Launching a single `48`-CTA cooperative persistent `sm_86` megakernel polling a `cudaHostAllocMapped` UTF-8 byte ring buffer (`0` host CUDA launches/token) beats per-op CUDA launch latency by `>= 3.0×`, AND eliminating `switch(opcode)` branching via the uniform `CellOp` loop (`uniform_cell_megakernel_sm86`) measurably reduces the `ptxas` fixed-envelope register footprint and improves batch-1 throughput vs the `switch(opcode)` control (`holosphere_persistent_vm_sm86`).
- **Locked Pass Criteria (ALL 4 required for `CONFIRMED`):**
  1. **Zero-Spill & Real-ISA Compiler Gate:** `/opt/cuda/bin/nvcc -O3 -std=c++17 -arch=sm_86 --ptxas-options=-v` reports **`0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads`** on 100% of kernels (`7/7`), `0` compiler warnings, and `cuobjdump --dump-sass` confirms real `IMMA.16832`, `HMMA.16816`, `IDP` (`dp4a`), `LDGSTS`, `SHFL`, `POPC`, and `MEMBAR` emission.
  2. **Fixed Launch Envelope Register Gate:** `uniform_cell_megakernel_sm86` (`switch`-free, `256` threads/CTA) uses strictly fewer registers per thread (`>= 15%` lower `ptxas` register footprint) than the `switch(opcode)` control `holosphere_persistent_vm_sm86` while executing double-buffered `cp.async` + `Block-H4` + `IMMA.16832` + `SU(2)` holonomy + `16 B` rollback.
  3. **Exact Decode & Specialist-Swap Rollback Parity Gate:** Batch-1 decode matches reference within **`max |delta| <= 1e-3` (BF16)** and **bit-exact `int32` parity (`0` diff)** on `Block-H4` `IMMA.16832` / `dp4a`, with `0` NaNs/Infs, 100% identical sampled byte stream across `>= 256` wrapped ring bytes, and exact `16 B` $\Pi_{t_0}$ rollback invariance (`||U_restored - U_t0||_2 == 0.0`) across `scribe -> weaver -> prover` pointer swaps.
  4. **Batch-1 Latency Kill Gate (RTX 3080, Zone B):** Persistent megakernel achieves **`>= 3.0×` lower batch-1 `µs/tok` latency** vs per-op CUDA launch baseline (`~150` kernel launches/token) with strictly **`0` host CUDA kernel launches/token** during streaming, AND `uniform_cell_megakernel_sm86` beats `holosphere_persistent_vm_sm86` on sustained `µs/tok`.
- **Literal Kill / Grading Rule:**
  - `CONFIRMED`: Criteria 1, 2, 3, and 4 ALL pass.
  - `PARTIAL`: Criteria 1, 2, and 3 pass, AND speedup vs per-op is `>= 1.8×` (or `CellOp` ties `switch(opcode)` within `±5%`).
  - `FALSIFIED`: Any spill `> 0 B`, parity violation, or speedup `< 1.8×`.

### `H16b` (`EXP-Q23b`) — Register-Local Normalization Pareto Showdown ($S^3$ vs $S^{15}$ vs $S^{31}$ vs Global `nGPT` `L2`) at Exact `CS-08` Parity
- **Claim:** Replacing `nGPT`'s cross-warp global `L2` hypersphere norm with register-local `float4` $S^3$ (`4`-coord, `0.0%` cross-bank bleed, `0` shuffles) or warp-subgroup `__shfl_xor_sync` $S^{15}$ (`16`-coord) / $S^{31}$ (`32`-coord) norms eliminates cross-warp synchronization barriers without degrading equal-wall-clock (`CS-08`) BPB.
- **Arms (`3` seeds `[42, 137, 2026]`, matched params `±0.5%`, equal wall-clock `CS-08` budget, `T=512` & `T=2048`):**
  1. `Global-nGPT-L2` (`N0` global cross-warp `L2` baseline)
  2. `RegLocal-S3-Float4` (`4`-coord pure-register $S^3$, `0.0%` cross-bank bleed)
  3. `WarpLocal-S15-Shfl` (`16`-coord `2`-shuffle $S^{15}$)
  4. `WarpLocal-S31-Shfl` (`32`-coord `3`-shuffle $S^{31}$)
- **Locked Pass Criteria (BOTH required for `CONFIRMED`):**
  1. **Norm Kernel Efficiency Gate:** Local norm kernels execute with `0` `__syncthreads()` barriers and beat `Global-nGPT-L2` normalization latency by **`>= 1.35×`**.
  2. **Equal-Wall-Clock (`CS-08`) Quality Pareto Gate:** At least one local-norm arm matches or beats `Global-nGPT-L2` BPB within **`<= +0.5%` regression ceiling** (or improves BPB with `z <= -2.0`) at both `T=512` and `T=2048`.
- **Literal Kill / Grading Rule:**
  - `CONFIRMED`: Both 1 and 2 pass.
  - `PARTIAL`: Criterion 1 passes, but best local-norm arm regresses `+0.5%..+2.0%` BPB vs `Global-nGPT-L2`.
  - `FALSIFIED`: Criterion 1 fails OR all three local-norm arms regress `> +2.0%` BPB.

### `H16c` (`EXP-Q23c`) — On-Chip L2/SRAM-Resident Looped `HoloSphere` (`~1.41 MiB < 4.0 MiB` L2) + Native `Block-H4` `mma.sync`-Swizzled Layout Co-Training vs PTQ
- **Claim:** Packing the weight-tied looped `HoloSphere` core (`2.62M` unique params -> `1.406 MiB` `A_16 Block-H4` / `4.5 bpp` or `0.625 MiB` `A_16` binary-sign) strictly inside `GA104M`'s `4.000 MiB` L2 cache enables true on-chip weight residency exceeding off-chip GDDR6 bandwidth, while co-training natively in the `A_16 Block-H4` `mma.sync.aligned.m16n8k32`-swizzled layout with learnable per-block scales outperforms offline PTQ.
- **Locked Pass Criteria (BOTH required for `CONFIRMED`):**
  1. **Super-HBM Effective Bandwidth Kill Gate (RTX 3080, Zone B):** Batch-1 persistent decode sustains effective weight bandwidth `(effective_weight_bytes_per_token / decode_sec_per_token)` strictly **`> 356.6 GB/s`** (beating measured `GA104M` GDDR6 STREAM Triad `356.6 GB/s`), proving true on-chip L2/SRAM residency!
  2. **Layout Co-Training vs PTQ Quality Gate (`3` seeds):** Native `Block-H4` `mma.sync`-swizzled co-training beats matched-bitwidth offline PTQ by **`>= 3.0%` relative BPB (`z <= -2.0`)** AND stays within `<= +2.0%` BPB of the BF16 upper bound.
- **Literal Kill / Grading Rule:**
  - `CONFIRMED`: Both 1 and 2 pass.
  - `PARTIAL`: Exactly one of 1 (`> 356.6 GB/s`) or 2 (`>= 3.0%` over PTQ) passes.
  - `FALSIFIED`: Effective bandwidth `<= 356.6 GB/s` AND co-training fails to beat PTQ by `>= 3.0%`.

### `H16d` (`EXP-Q23d`) — `SiliSense` (`Track S115`) Telemetry: `150` Launches/Tok vs `1`-Launch Persistent Megakernel
- **Claim:** Collapsing `~150` host CUDA kernel launches/token into a single persistent megakernel measurably silences host-GPU PCIe/uncore power coupling and host interrupt jitter on real silicon.
- **Protocol:** Interleaved `ABABAB` Zone-B run on RTX 3080 under `SiliSense` Mode 1 (`telemetry-only`, non-acoustic `intel-rapl` + NVML + `/proc/interrupts`; unconditional camera ban; equal-wattage pacing control matching `PREREG-S115`).
- **Locked Pass Criteria (BOTH required for `CONFIRMED`):**
  1. **`uncore_w` Copula MI (`A7`) Kill Gate:** `1`-launch persistent megakernel reduces multi-lag Schur-residualized `uncore_w` copula MI (`A7`) by **`>= 40.0%` (`z <= -2.0`, `p_Holm < 0.005`)** vs per-op launch.
  2. **Host-IRQ Jitter Kill Gate:** Reduces host CUDA/PCIe IRQ rate and inter-token latency jitter (CV / `p99 - p50` spread) by **`>= 40.0%` (`z <= -2.0`)**.
- **Literal Kill / Grading Rule:**
  - `CONFIRMED`: Both 1 and 2 pass (and hold against equal-wattage pacing control).
  - `PARTIAL`: One passes `>= 40.0%` and the other improves `>= 20.0%` (`z <= -2.0`).
  - `FALSIFIED`: Both fail `< 40.0%` reduction or collapse under equal-wattage pacing control.

---

## 5. Anti-Snooping, Reproducibility, & Hygiene Guardrails

- **Phase-1 Zero-GPU Lock:** Phase 1 builds, compiles (`nvcc -O3 -std=c++17 -arch=sm_86 --ptxas-options=-v`), extracts SASS (`cuobjdump --dump-sass`), saves `ptxas_s116_zero_spill_receipt.json`, deletes all temporary `.so`/`.cubin`/`.o` binaries (`ELF=0`), and verifies the pure-stdlib CPU VM reference & `unittest` suite across all `3` isolated Python modes (`-I -B`, `-I -O -B`, `-I -B -W error`) under `CUDA_VISIBLE_DEVICES=""`.
- **Phase-2 Zone-B GPU Execution:** Executes strictly AFTER `PREREG-S116` SHA-256 is logged in `verification/AUDIT_LOG.md`, Phase-1 passes dual `aletheia audit-check --strict-ancestors --safety-scan`, and the GPU lease is free and acquired via `mlos gpu-lease`.
- **Artifact Discipline:** `WEIGHTS=0`, `ELF=0`, `PYC=0`, `0` bare `assert`s, `0` user-home leaks, `0` CRLF, `0` GitHub pushes without sign-off.
