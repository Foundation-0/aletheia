# `PREREG-S116-AMENDMENT3` (`EXP-Q23l`): Unified `A5_CellOp_Unified_A3plusA4` Double-Dissociation Fusion & `2,000`-Step $A_5$ `p_Holm < 0.01` Confirmation (`H16e-v2`)

- **Document ID:** `PREREG-S116-AMENDMENT3-UNIFIED-A3A4-A5-V1`
- **Status:** **IMMUTABLE PRE-RUN AMENDMENT LOCK** (written & SHA-256-logged in `verification/AUDIT_LOG.md` strictly BEFORE `H16e-v2` GPU execution; immutable parents `PREREG_S116` [`9620db774af3...`], `AMENDMENT1` [`985e1460d186...`], and `AMENDMENT2` [`eb1b0e571be9...`] remain 100% untouched).
- **Date (UTC):** `2026-11-26`
- **Owner:** `fractals-probe` (`Track S116` Phase-2B Follow-Up `EXP-Q23l`).
- **Phase-2B Ground Truth Anchors (Live RTX 3080 Zone-B `ce894e05...`, `s116_h16e_gpu_results.json` `5b728120...`):**
  - `H16a-v2 = CONFIRMED` (`33.69 µs/tok`, `0.462 mJ/tok` = `106.9×` faster / `195.4×` lower GPU energy vs PyTorch eager `12L`, `9.12×` vs `switch(opcode)` 48-CTA, `100%` live silicon parity).
  - `H16e` (`800` steps) = honest **`PARTIAL`** revealing a textbook **double dissociation**:
    1. `H16e_W_S3`: Both `A3` and `A4` hit **`100.00%`** at `T=128` (`4×` OOD) and `99.87%`/`99.35%` at `T=256` (`8×` OOD), `p_Holm = 0.00026 < 0.01` vs `A0/A2` (`16.21%`/`16.08%`).
    2. `H16e_W_A5`: `A4` (`CayleySU2-MultFastWeight` + `SO(3)` adjoint) hit **`100.00%` at `T=64, 128, AND 256` (`8×` OOD)** on seed `42` (`loss = 0.00063`) and `48.63%` 3-seed `T=128` mean (`100.0% / 18.6% / 27.3%`, `+46.68 pp` vs `A0/A2`), missing `p_Holm < 0.01` ONLY because seeds `137`/`2026` were still exiting the $A_5$ plateau at step `800` (`loss = 0.036–0.039`).
    3. `H16e_M_S3` & `H16e_M_A5` (Scoped Macro Recall `L0..L7`): **`A3`** (`HardFMNMX-CayleySTE`) was the **ONLY** arm beating chance (`H16e_M_S3 = 27.86%`, `+12.17 pp` vs `A2` `p_raw = 0.0045`; `A4` collapsed to `18.29%` chance without a KV-ring!).
    4. `512 B UTF-8 BPB`: `A3` (`5.2937`) & `A4` (`5.2252`) beat `A0` (`8.0021`) by `-33.85%`, while `A1` (`LinearSfast-Only`) achieved `2.7470 BPB` on local byte n-grams (while collapsing to chance on $S_3$/$A_5$).

---

## 1. Unified Architecture (`A5_CellOp_Unified_A3plusA4`, Matched `CS-08` Budget `<= 0.5%` Delta)

Fuses all three `uniform_cell_8warp_sm86` silicon primitives into a single parameter-matched (`<= 0.5%` non-embedding parameter delta vs `A0/A2/A3/A4`) unified `CellOp` arm:
1. **Gated Hard-`FMNMX` KV-Ring -> Multiplicative `BoundedCayleySU2Head` (`A3 + A4`):**
   - `g_kv = sigmoid(W_gate_kv(x))` (bias initialized to `-1.5` so raw generators pass cleanly into `BoundedCayleySU2Head` like `A4`, while `CALL(L_i)` tokens open `g_kv -> 1` to route the **100% unmixed hard-`FMNMX` retrieved macro `y_kv`** cleanly with zero `CALL` embedding interference!):
     $$h_{\text{gen}} = \operatorname{norm}\bigl((1 - g_{\text{kv}}) \odot x + g_{\text{kv}} \odot W_{\text{mem}}(y_{\text{kv}})\bigr).$$
   - Ordered multiplicative `BoundedCayleySU2Head` (`R_max = 1.5`, golden-spiral `||w||_0 = 0.55`) parallel prefix scan $U_t = \Delta U_0 \cdots \Delta U_t \in SU(2)^{n_q}$.
2. **Fused $\pm I$-Invariant $SO(3)$ Adjoint Readout + Gated `S_fast` Local Residual (`A1 + A3 + A4`):**
   - $R(U_t) \in SO(3)^{n_q}$ projected via `W_so3`, fused with exact causal linear `S_fast` fast-weight residual via learnable gate `g_sf = sigmoid(gate_sfast)` (initialized conservatively at `-2.0` so non-Abelian group closure is undisturbed while byte-level UTF-8 n-grams unlock `S_fast` capacity):
     $$o_t = \operatorname{norm}\bigl(W_{\text{so3}}(R(U_t)) + g_{\text{sf}} \, W_{\text{sfast}}(y_{\text{sfast}})\bigr).$$
   - `d_so3` is sized analytically so `non_embedding_param_count(A5)` matches `A0`/`A2`/`A3`/`A4` within **`<= 0.5%`** on every benchmark (`S_3`, `A_5`, `512 B UTF-8`).

---

## 2. Locked `H16e-v2` (`EXP-Q23l`) Protocol & Kill Gates

- **Arms (`5`, matched `CS-08` `<= 0.5%` non-embed params, identical `AdamW(lr=3e-3 -> 1e-4)`, `bsz=256`, `T_train=32`, `beta 4.0 -> 16.0`, seeds `[42, 137, 2026]`):**
  `{A0_H14c_Softmax_CovariantQKV, A2_CellOp_SoftExp2f_KVRing, A3_CellOp_HardFMNMX_CayleySTE, A4_CellOp_CayleySU2_MultFastWeight, A5_CellOp_Unified_A3plusA4}`.
- **Benchmarks (Live RTX 3080 Zone-B `mlos_zone_b_s116_h16e_v2.json` -> `s116_h16e_v2_gpu_results.json`):**
  1. **`H16e_W_A5` (`2,000` steps):** Pure $A_5$ word tracking (`T_train = 32`, zero-teacher-forcing OOD `T_eval ∈ {64, 128, 256}`).
  2. **`H16e_M_S3` (`2,000` steps):** Scoped Macro Recall `L0..L7` in $S_3$ (`T_train = 32`, OOD `T_eval ∈ {64, 128}`).
  3. **`H16e_M_A5` (`2,000` steps):** Scoped Macro Recall `L0..L7` in $A_5$ (`T_train = 32`, OOD `T_eval ∈ {64, 128}`).
  4. **`512 B UTF-8 BPB` (`250` steps):** Causal `512 B` UTF-8 next-byte BPB (`32`-slot sliding KV-ring).
- **Literal Kill Gates:**
  - **`H16e` $A_5$ Confirmation (`CONFIRMED`):** `A5` (or `A4`) achieves **`>= 50.0%` 3-seed mean OOD accuracy on `H16e_W_A5` at `T=128`** (exceeding the `>= 15.0%` Amendment-2 floor), beating BOTH `A0` and `A2` by `>= +8.0 pp` with **`p_Holm < 0.01`** (two-sided paired Student-$t$), AND `<= +1.0%` BPB regression vs `A0` on `512 B` UTF-8.
  - **Double-Dissociation Fusion (`UNIFIED_CONFIRMED`):** `A5_CellOp_Unified_A3plusA4` simultaneously achieves (1) `>= 50.0%` on `H16e_W_A5` (`T=128`, `p_Holm < 0.01` vs `A0/A2`), (2) strictly beats BOTH `A2` and `A4` on `H16e_M_S3` (`T=128`, `>= +20.0 pp`, `p_Holm < 0.01`), AND (3) strictly beats `A3` and `A4` on `512 B` UTF-8 BPB (`<= 4.0 BPB`).
  - **`PARTIAL`:** Clears `H16e` $A_5$ confirmation without clearing all three unified fusion criteria, or clears `H16e_M_S3` fusion without `p_Holm < 0.01` on `H16e_W_A5`.
  - **`FALSIFIED`:** Neither `A5` nor `A4` clears `>= 15.0%` with `p_Holm < 0.01` on `H16e_W_A5` at `2,000` steps.
