# `PREREG-S116-AMENDMENT4` (`EXP-Q23m`): Relational Macro Holonomy $\Delta U_{L_k} = U_{\tau_1} U_{\tau_0}^\dagger$ in `V_ring` + $T_{\Delta U_{\tau^*}} S^3$ Tangent STE (`H16e-v3` / `A6_RelationalCellOp`)

- **Document ID:** `PREREG-S116-AMENDMENT4-RELATIONAL-MACRO-HOLONOMY-V1`
- **Status:** **IMMUTABLE PRE-RUN AMENDMENT LOCK** (written & SHA-256-logged in `verification/AUDIT_LOG.md` strictly BEFORE `H16e-v3` GPU execution; immutable parents `PREREG_S116` [`9620db774af3...`], `AMENDMENT1` [`985e1460d186...`], `AMENDMENT2` [`eb1b0e571be9...`], and `AMENDMENT3` [`0f58e288d2a1...`] remain 100% untouched).
- **Date (UTC):** `2026-11-26`
- **Owner:** `fractals-probe` (`Track S116` GPU Slot 2 — `OBS-ORDA-26` / `W10-OBS-60`).
- **Phase-2B / `H16e-v2` Ground Truth Anchors (Live RTX 3080 Zone-B `782e455b...`, `s116_h16e_v2_gpu_results.json` `6343592e...`):**
  - `A5_CellOp_Unified_A3plusA4` smashed `H16e_M_S3` (`99.35%` `T64`, `94.40% ± 3.04%` `T128`, `p_Holm = 0.0015 < 0.01` vs all 4 controls) and reached `52.34%` `T64` / `33.01%` `T128` (seed `137`: `94.53%` `T64`, `76.76%` `T128`) on `H16e_M_A5`, but still stored raw feature vectors in `V_ring` and mapped them through `w_mem_out` + `BoundedCayleySU2Head` a second time, causing 3-seed variance `[5.9%, 76.8%, 16.4%]` on non-solvable $A_5$ macro recall.

---

## 1. Exact Left-Action Relational Holonomy Operator (`OBS-ORDA-26` / `A6_RelationalCellOp`)

1. **Left-Action Holonomy Convention:**
   $$U_t = q(\omega_t) \cdot U_{t-1}, \qquad U_{-1} = I = (1, 0, 0, 0) \in SU(2)^{n_q}.$$
   For any macro definition spanning $(\tau_0, \tau_1]$ (whether 1-step `span=1` or multi-step composed `span=2` $L_k = g_{k,1} g_{k,2}$):
   $$U^{\text{pre}}_{\tau_1} = \bigl(q(\omega_m) \cdots q(\omega_1)\bigr) \cdot U^{\text{pre}}_{\tau_0} \implies \Delta U_{L_k} = U^{\text{pre}}_{\tau_1} \cdot \bigl(U^{\text{pre}}_{\tau_0}\bigr)^\dagger = q(\omega_m) \cdots q(\omega_1) \in SU(2)^{n_q}.$$
   Verified algebraically pre-run: $\Delta U_{L_k} \cdot U^{\text{pre}}_{\tau_0} \equiv U^{\text{pre}}_{\tau_1}$ to `< 1e-6`, eliminating frame-conjugation mixing ($U_{\tau_0}^\dagger U_{\tau_1}$) when $L_k$ is invoked at a new non-commuting frame $U_{t-1} \neq U_{\tau_0}$.
2. **Direct $SU(2)$ `V_ring` + Exact 4D $T_{\Delta U_{\tau^*}} S^3$ Tangent STE (`HardFMNMXS3TangentSTE`):**
   - `V_ring` stores the gauge-invariant unit quaternion operators $\Delta U_\tau \in (S^3)^{n_q}$ directly.
   - Forward selects $\tau^* = \arg\max_{\tau \le t} s_{t,\tau}$ (Law-3 NaN-safe deterministic hard `FMNMX`) and returns $\Delta U_{\tau^*} \in (S^3)^{n_q}$ directly (`||\Delta U_{\tau^*}||_2 \equiv 1.0`, zero feature distortion).
   - Backward projects each 4D quaternion fiber $f$ onto its exact tangent space $T_{q^*_f} S^3$:
     $$g_{\tan, f} = g_f - \langle g_f, q^*_f \rangle_4 \, q^*_f,$$
     verified against FP64 central finite differences (`max_err <= 1e-8`) pre-run.
   - Sign-aligned quaternion gating (`w_gate_kv`, `w_gate_exec`) left-multiplies $U_t = dq^{\text{eff}}_t \cdot U_{t-1}$, followed by fused $\pm I$-invariant $SO(3)$ adjoint readout $R(U_t)$ + gated `S_fast` residual, with analytical `d_so3` matching `CS-08` non-embedding parameters within **`<= 0.5%`**.

---

## 2. Locked `H16e-v3` (`EXP-Q23m`) Protocol & Kill Gates

- **Arms (`4`, matched `CS-08` `<= 0.5%` non-embed params, locked seeds `[42, 137, 2026]`, `T_train = 32`, `beta 4.0 -> 16.0`, `AdamW(lr=3e-3 -> 1e-4)`):**
  `{A3_CellOp_HardFMNMX_CayleySTE, A4_CellOp_CayleySU2_MultFastWeight, A5_CellOp_Unified_A3plusA4, A6_RelationalCellOp}`.
- **Benchmarks (Live RTX 3080 Zone-B `mlos_zone_b_s116_h16e_v3.json` -> `s116_h16e_v3_gpu_results.json`):**
  1. **`H16e_M_S3`** (`1,200` steps, `T_eval ∈ {64, 128, 256}` `8×` OOD): 1-step Scoped Macro Recall `L0..L7` in $S_3$.
  2. **`H16e_M_A5`** (`2,000` steps, `T_eval ∈ {64, 128, 256}` `8×` OOD): 1-step Scoped Macro Recall `L0..L7` in non-solvable $A_5$.
  3. **`H16e_M2_A5`** (`1,200` steps, `T_eval ∈ {64, 128, 256}` `8×` OOD, `{A3, A5, A6}`): **2-step Composed Relational Macro Recall** (`L_k = g_{k,1} g_{k,2}`, testing genuine multi-step $\Delta U_{L_k} = U_{\tau_1} U_{\tau_0}^\dagger$ composition!).
- **Literal Kill Gates:**
  - **`CONFIRMED`:** `A6_RelationalCellOp` achieves **`>= 90.0%` on `H16e_M_S3` (`T=128`)** AND **`>= 50.0%` 3-seed mean on `H16e_M_A5` (`T=128`)** (beating `A4` by `>= +45 pp`, `p_Holm < 0.01`, AND improving over `A5` on `H16e_M_A5` or `H16e_M2_A5`!).
  - **`PARTIAL`:** `A6_RelationalCellOp` achieves `>= 90.0%` on `H16e_M_S3` (`T=128`) and beats `A3`/`A4` significantly on `H16e_M_A5` or `H16e_M2_A5` without clearing all `p_Holm < 0.01` thresholds simultaneously.
  - **`FALSIFIED`:** `A6_RelationalCellOp` fails to beat `A4` on `H16e_M_S3` or fails to exceed `15.0%` on `H16e_M_A5` (`T=128`).
