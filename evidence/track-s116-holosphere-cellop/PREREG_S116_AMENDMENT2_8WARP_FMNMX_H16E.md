# `PREREG-S116-AMENDMENT2`: 8-Warp Zero-`grid.sync()` `.gpu`-Scope `CellOp` (`H16a-v2`) & `HardFMNMXCayleySTE` `5`-Arm $S_3$/$A_5$ Group-Closure Rescue (`H16e` / `EXP-Q23e`)

- **Document ID:** `PREREG-S116-AMENDMENT2-8WARP-FMNMX-H16E-V1`
- **Status:** **IMMUTABLE PRE-RUN AMENDMENT LOCK** (written & SHA-256-logged in `verification/AUDIT_LOG.md` strictly BEFORE Phase-2B GPU execution; immutable parents `PREREG_S116_HOLOSPHERE_PERSISTENT_MEGAKERNEL.md` [`9620db774af3...`] and `PREREG_S116_AMENDMENT1_CELLOP_IMMA_KVRING.md` [`985e1460d186...`] remain 100% untouched).
- **Date (UTC):** `2026-11-25`
- **Owner:** `fractals-probe` (`Track S116` Phase-2B, co-designed with `@orda-aska` on `Moissanite-Labs/silikernels#2` and hardened via `ALETHEIA_CONVERGENCE_ORDA_CELLOP_HOLOSPHERE.md` `OBS-ORDA-01..05`).
- **Phase-2A Ground Truth Anchors (Live RTX 3080 Zone-B `912abc77...`):**
  - `H16a` live parity: `100%` PASS (`IMMA.16832` `max_int32_diff = 0`, `16/16` injected flips caught via 2-shfl `[16,11,4]`, `dp4a` `0.0`, `S^{31}` fused `warp_absmax` `max|q| = 127`, `S^3` bleed `= 0.0`, `"Nat.add_comm"` `12/12` B verbatim KV-ring copy, `0.0` `16 B` $\Pi_{t_0}$ rollback drift, `HMMA.16816: 0` inside `uniform_cell_megakernel_sm86`).
  - `H16c` Super-HBM L2 residency: **SMASHED LIVE** (`601.02 GB/s` sustained = `1.689×` live `355.85 GB/s` STREAM Triad; `817.72 GB/s` = `2.297×` peak P0 boost; `16 MiB` HBM control pegged at `356.92 GB/s`).
  - Honest Phase-2A `H16a` bottleneck diagnosis: `uniform_cell_megakernel_sm86` parked `7/8` warps (`warp_id == 0` only), executed `2×` full-chip `grid.sync()` drains per pass, and ran `48` fused cells vs `12` layers (`7.02 µs/fused-layer` pipelined vs `25.66 µs/layer` on `switch_vm` and `8.09 µs/layer` on async C++ `per_op_48`).

---

## 1. `H16a-v2` — Matched `12`-Layer `d_model=256/512` 8-Warp Zero-`grid.sync()` `.gpu`-Scope Showdown

### 1.1 Architectural Upgrade (`uniform_cell_8warp_sm86`, `__launch_bounds__(256, 1)`)
1. **All `8/8` Warps Active (`8` Parallel $S^{31}$ Heads = `256` ch/CTA):** Every warp `w ∈ 0..7` executes double-buffered `cp.async.ca.shared.global`, zero-swizzle 4-thread-group `Block-H4` + 2-shuffle `[16,11,4]` parity -> `IMMA.16832.S8.S8` (`0` `HMMA.16816`), register `S_fast`, covariant `SU(2)` holonomy + `16 B` $\Pi_{t_0}$ rollback, and fused `warp_absmax` $S^{31} \to s8$ retraction simultaneously in parallel.
2. **Zero `cooperative_groups::this_grid().sync()`:**
   - Within a `d_model = 256` CTA: `8` warps publish `8 × 32 B = 256 B` of retracted `int8` outputs into SMEM (`~4.6 KiB` total SMEM `< 4.6%` of `100 KiB`) and mix cross-head via ONE CTA-local `__syncthreads()` (`~20` cycles vs `~1,800` cycles for `grid.sync()`).
   - Across CTAs (`d_model = 512..1024`): uses native Ampere `.gpu`-scope L2 scoreboard (`ld.acquire.gpu.global.u32` + `red.release.gpu.global.add.u32`) strictly inside `GA104M`'s `4 MiB` L2 cache coherency fabric (`~120–180 ns`, zero PCIe/system-scope fence per layer!).
3. **Law-3 NaN-Safe Branchless `warp_fmnmx_argmax_32` + One-Hot `0x7F` `pack_onehot_imma_a_frag`:**
   - Pre-sanitizes `local_score = isnan(local_score) ? -INFINITY : local_score;` strictly BEFORE the 5-step `FMNMX` (`fmaxf`) + `SEL` butterfly so `(win_score, win_slot)` can NEVER desynchronize on IEEE-754 `NaN`s.
   - Packs `0x7F` (`127`) at `win_slot mod 32` (`0x00` elsewhere) into `IMMA.16832` Operand A (`a0..a3`) so Pass-B executes the exact same `IMMA.16832.S8.S8` pipeline to extract `127 * V_ring[win_slot]` bit-exactly with zero convex mixing and `0` `HMMA` pipe switches.

### 1.2 Locked `H16a-v2` Kill Gate (Matched `12`-Layer `d_model=256/512` Work, RTX 3080 Zone B)
Compare identical `12`-layer work across:
1. Python/PyTorch eager `150`-launch baseline,
2. Async C++ `48`-launch baseline,
3. `holosphere_persistent_vm_sm86` (`switch(opcode)` control, `80` regs, `128` thr, `0` launches/tok),
4. **`uniform_cell_8warp_sm86`** (`switch`-free 8-warp `CellOp`, `0` `grid.sync()`, `0` launches/tok).
- **`CONFIRMED`:** (1) `nvcc 13.4 --ptxas-options=-v` `0 B` stack/spills & `HMMA.16816 == 0` in `uniform_cell_8warp_sm86`; (2) `100%` live bit-exact parity (`max_int32_diff == 0`, `0` NaN argmax desyncs, `0.0` `16 B` rollback drift); AND (3) **`>= 3.0×` lower batch-1 `µs/tok` latency** vs BOTH Python/PyTorch eager `150`-launch AND `holosphere_persistent_vm_sm86` (and strictly faster than async C++ `48`-launch).
- **`PARTIAL`:** (1) and (2) pass, speedup `>= 3.0×` vs PyTorch eager `150`-launch OR `>= 2.0×` vs `switch(opcode)` control, without clearing all 3 comparisons simultaneously.
- **`FALSIFIED`:** Any spill `> 0 B`, parity violation, or `< 2.0×` speedup vs PyTorch eager `150`-launch.

---

## 2. `H16e` (`EXP-Q23e`) — `5`-Arm `CS-08` $S_3$ & $A_5$ Non-Abelian Group-Closure Rescue

Motivated by `Track S114` `H14c = FALSIFIED` (`W10-OBS-42`: softmax convex averaging exits the group manifold) and `ALETHEIA_CONVERGENCE_ORDA_CELLOP_HOLOSPHERE.md` `OBS-ORDA-03` & `OBS-ORDA-05`:

### 2.1 Locked `5`-Arm `CS-08` Design (`3` Seeds `[42, 137, 2026]`, Matched Params `±0.5%`, Equal-Step & Equal-Wall-Clock)
Evaluated on deterministic finite-group word composition for **$S_3$ (`|S_3| = 6`)** and **$A_5$ (`|A_5| = 60`, non-solvable simple group)** with train length `T_train <= 32` and OOD lengths `T_test ∈ {64, 128, 256}`:

| Arm (`H16e`, `CS-08` Parity) | Sequence / Memory Operators | Specific Hypothesis Isolated |
| --- | --- | --- |
| `A0`: `H14c-Softmax-CovariantQKV` (`N0`) | Ordered `SU(2)` + standard softmax covariant QKV | Falsified anchor (`35.30%` $S_3$ / `2.58%` $A_5$ OOD) |
| `A1`: `CellOp-LinearSfast-Only` | `Block-H4` + additive `S_fast` delta rule (`flags&1` OFF, no `SU(2)`) | Pure linear fast-weight ceiling (`OBS-ORDA-05`) |
| `A2`: `CellOp-SoftExp2f-KVRing` | `S_fast` + `CayleySU2` + soft `exp2f` Pass-A KV-ring | Soft-averaging convex-hull relapse control (`W10-OBS-42`) |
| `A3`: `CellOp-HardFMNMX-CayleySTE` | `S_fast` + `CayleySU2` + deterministic `FMNMX` hard top-1 Pass-A + Riemannian tangent `HardFMNMXCayleySTE` backward + $\pm I$-invariant $SO(3)$-adjoint readout `R(q)` | Exact forward group closure + manifold-aligned backward + `2I` double-cover sign invariance (`OBS-ORDA-03`) |
| `A4`: `CellOp-CayleySU2-MultFastWeight` | `CayleySU2` + multiplicative orthogonal fast-weight update (no KV-ring) | Isolates multiplicative holonomy vs discrete KV-ring retrieval |

### 2.2 Exact `HardFMNMXCayleySTE` & $\pm I$-Invariant $SO(3)$-Adjoint Readout Specification
- **Forward:** $\tau^* = \arg\max_\tau s_\tau$ (exact `FMNMX` winner, `0.0` discrepancy vs CUDA), $v_{\text{out}} = v_{\tau^*}$.
- **Backward (Self-Adjoint Tangent Projection on $T_{v^*} S^{31}$):**
  $$g_{\tan} = g - \langle g, v^* \rangle v^*, \qquad \frac{\partial \mathcal{L}}{\partial s_\tau} = \beta \, p_\tau \bigl(\langle g_{\tan}, v_\tau \rangle - \sum_k p_k \langle g_{\tan}, v_k \rangle\bigr), \qquad p = \operatorname{softmax}(\beta (s - \max s)).$$
  Verified against FP64 central finite differences on the tangent surrogate (`max_err <= 1e-8`) before GPU training.
- **$\pm I$-Invariant $SO(3)$-Adjoint Readout (`OBS-ORDA-03`):** Maps each $q = (w,x,y,z) \in SU(2)$ to its $3 \times 3$ adjoint rotation matrix $R(q) \in SO(3)$ satisfying $R(-q) \equiv R(q)$ and $R(p \otimes q) \equiv R(p) R(q)$, eliminating double-cover sign ambiguity on $2I \to A_5$.

### 2.3 Locked `H16e` Literal Kill Gate
- **`CONFIRMED`:** `A3` (or `A4`) achieves **`>= 50.0%` OOD accuracy on $S_3$** AND **`>= 15.0%` OOD accuracy on $A_5$** at `T_test = 128`, beating BOTH `A0` and `A2` by **`>= +15.0 pp` on $S_3$** and **`>= +8.0 pp` on $A_5$** (two-sided Student-$t$ `p_Holm < 0.01`), with `<= +1.0%` BPB regression on `512 B` UTF-8.
- **`PARTIAL`:** Passes $S_3$ (`>= 50.0%` & `>= +15.0 pp`) while $A_5 < 15.0\%$ (or beats `A0`/`A2` significantly without crossing both absolute floors).
- **`FALSIFIED`:** Neither $S_3$ nor $A_5$ passes.
