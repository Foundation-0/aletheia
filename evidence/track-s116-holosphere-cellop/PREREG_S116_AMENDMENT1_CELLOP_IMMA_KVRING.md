# `PREREG-S116-AMENDMENT1`: Zero-Swizzle 4-Thread-Group `Block-H4 -> m16n8k32.s8`, 2-Shuffle Distributed `[16,11,4]` Syndrome, Fused `warp_absmax` `S^{31} -> s8`, & Branchless `1`-in-`8` Covariant KV-Ring `CellOp` (`EXP-Q23a..d`)

- **Document ID:** `PREREG-S116-AMENDMENT1-CELLOP-IMMA-KVRING-V1`
- **Status:** **IMMUTABLE PRE-RUN AMENDMENT LOCK** (written & SHA-256-logged in `verification/AUDIT_LOG.md` strictly BEFORE any GPU execution; immutable parent `PREREG_S116_HOLOSPHERE_PERSISTENT_MEGAKERNEL.md` left 100% untouched at SHA-256 `9620db774af30b8b6e4ef8c241ccd5ed4cb489dd2fb3b414234633ea83c93c85`).
- **Date (UTC):** `2026-11-25`
- **Owner:** `fractals-probe` (`Track S116` / `EXP-Q23a..d`, co-designed with `@orda-aska` on `Moissanite-Labs/silikernels#2` Piece 1).

---

## 1. Three Pre-GPU `sm_86` `CellOp` Refinements Locked Before Phase-2 Execution

Following `@orda-aska`'s detailed `m16n8k32.s8` + `1`-in-`8` KV-ring specification on `Moissanite-Labs/silikernels#2`, this pre-execution amendment locks three strictly additive bare-metal `sm_86` refinements into `holosphere_megakernel_sm86.cu` and `s116_megakernel_ref.py`:

### 1.1 Zero-Swizzle 4-Thread-Group `Block-H4 -> mma.sync.aligned.m16n8k32.row.col.s32.s8.s8.s32` + 2-Shuffle Distributed `[16, 11, 4]` Syndrome
- **1 Scale Group = 1 MMA `K=32` Tile:** Two contiguous `uint64_t` `A_16 Block-H4` words (`32` signed 4-bit nibbles) share exactly `1 × __half` scale with zero scale-boundary splitting.
- **Per-Thread Load (`2 × uint16_t` only, `0` SMEM swizzle):** For `groupID = lane >> 2` (`0..7`) and `tid = lane & 3` (`0..3`), each thread loads ONLY its own `tid`-th `16`-bit nibble chunk from `w64_lo` (`b0`) and `w64_hi` (`b1`), using UB-safe sign extension:
  ```cpp
  static_cast<int32_t>(static_cast<uint32_t>((nibs >> shift) & 0xFu) << 28) >> 28
  ```
- **2-Shuffle Distributed `[16, 11, 4]` Parity Check:** Each thread extracts the `4` LSB parity bits of its own `16`-bit chunk shifted to `tid * 4`, OR-reduces across the 4-thread group in **2 register shuffles** (`__shfl_xor_sync(0xFFFFFFFFu, odd, 1)` + `__shfl_xor_sync(0xFFFFFFFFu, odd, 2)`), and evaluates the 5-mask Extended Hamming `[16, 11, 4]` `__popc` syndrome (`0xFFFF, 0xAAAA, 0xCCCC, 0xF0F0, 0xFF00`) identically across the 4 lanes — cutting per-thread parity extraction overhead by `4×` while preserving fail-closed zeroing on corruption.

### 1.2 Fused `warp_absmax` `S^{31} -> s8` Activation Quantization (`cvt.rni.sat.s8.f32`, Zero Extra Shuffles)
- **Dynamic-Range Cure:** For $x \in S^{31}$ ($\|x\|_2 = 1$), the RMS coordinate magnitude is $1/\sqrt{32} \approx 0.1768$, so naive `127.0f * x_i` clusters around `±22` (`~4.5` effective bits).
- **Zero-Overhead Fusion:** Inside the exact same warp norm reduction butterflies (`__shfl_xor_sync`), we fuse `amax = max_lane(|x_i|)` (`FMNMX`, `0` SMEM, `0` extra shuffles), so `warp_absmax = amax * rsqrtf(sq + eps^2)` is immediately available in registers.
- **Exact `s8` Quantization & Epilogue Folding:** Quantizing via inline PTX `cvt.rni.sat.s8.f32(x_norm * (127.0f / fmaxf(warp_absmax, eps)))` captures the full `7.9`-bit signed dynamic range (`max |q_i| = 127`, `|127 * 28 * 32| = 113,792 << 2^{31} - 1`), folding `0.5f * __half2float(scale_fp16) * (warp_absmax / 127.0f)` once in the single post-MMA `s32 -> f32` epilogue multiply!

### 1.3 Branchless `flags & 1` (`S116_CELL_IS_KV_RING`) `1`-in-`8` Covariant KV-Ring Lookup (`selp.b32`)
- **Preserving Exact Long-Range Copying Without `switch(opcode)` Envelope Bloat:** To support exact verbatim Lean 4.36 theorem/identifier recall (`Nat.add_comm`, SHA-256 receipts, multi-hop bindings) inside the single-opcode `__launch_bounds__(256, 1)` envelope, every 8th `S116CellOp` sets `flags & 1` (`S116_CELL_IS_KV_RING = 1`).
- **Predicated Pointer Aliasing (`selp.b32`):** The `128 B` `weight_blockh4_ptr` payload is aliased directly to canonical `8 × 32` `s8` L2 KV-ring bytes (premultiplied by inverse holonomy $U_\tau$ at write time). Inside the uniform loop, inline PTX `selp.b32` selects branchlessly between `blockh4_group_to_packed_s8(...)` and raw `s8` KV-ring words feeding the **exact same `mma.sync.aligned.m16n8k32.row.col.s32.s8.s8.s32` pipeline** — keeping `0 B` spills, `0` divergent branches, and `16 B` $\Pi_{t_0}$ holonomy rollback intact.

---

## 2. Amended Verification Gates (Strictly Additive to `PREREG-S116`)

All parent `PREREG-S116` hypotheses (`H16a..d`) and kill thresholds remain unchanged and binding, plus three additive Phase-1/Phase-2 parity assertions:
1. **2-Shuffle Syndrome Exactness:** Distributed 4-lane 2-shuffle `[16,11,4]` syndrome matches full 64-bit syndrome across 100% of valid and 1-/2-bit corrupted `Block-H4` words (`0` mismatches).
2. **`warp_absmax` `S^{31} -> s8` Utilization:** Fused `warp_absmax` quantization achieves `max(|q_i|) == 127` (full `7.9`-bit range) and cuts `S^{31}` dequantization RMSE by `>= 2.0×` vs naive `round(127 * x_i)`.
3. **Branchless `flags & 1` KV-Ring Exact Copy:** `S116_CELL_IS_KV_RING` retrieves exact verbatim key/token payloads inside `uniform_cell_megakernel_sm86` with `0` extra `ptxas` register spills (`0 B` stack/spills on all `7/7` kernels) and real `SEL` + `CVT` + `FMNMX` + `IMMA.16832` SASS emission.
