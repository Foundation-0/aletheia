# `PREREG-S116-AMENDMENT4B` (`EXP-Q23m`): Exact `2,000`-Step Macro Parity & Identity-Anchored $SU(2)$ Multiplicative Gate Lock (`H16e-v3`)

- **Document ID:** `PREREG-S116-AMENDMENT4B-STEP-PARITY-V1`
- **Status:** **IMMUTABLE PRE-RUN ADDENDUM** (locked & SHA-256-logged in `verification/AUDIT_LOG.md` strictly BEFORE any live GPU run on preregistered seeds `[42, 137, 2026]`; all immutable parents `PREREG_S116` [`9620db774af3...`], `AMENDMENT1` [`985e1460d186...`], `AMENDMENT2` [`eb1b0e571be9...`], `AMENDMENT3` [`0f58e288d2a1...`], and `AMENDMENT4` [`d22ceaa5251a...`] remain 100% untouched).
- **Date (UTC):** `2026-11-26`
- **Owner:** `fractals-probe` (`Track S116` GPU Slot 2 — `OBS-ORDA-26`).

## 1. Pre-Run Technical Clarifications (Zero Preregistered Seed Leakage)

During pre-run implementation debugging strictly on non-preregistered diagnostic seed `7` (zero executions on locked seeds `[42, 137, 2026]`), two purely mechanical issues were resolved:

1. **Exact `H16e-v2` Step-Budget Parity (`steps_macro = 2,000`):**
   - `H16e-v2` (`PREREG-S116-AMENDMENT3`, `s116_h16e_v2_gpu_results.json`) trained ALL macro recall tasks (`H16e_M_S3` and `H16e_M_A5`) for **`2,000` steps** (where `A5` groks `H16e_M_S3` from `~30%` at step `1,200` to `94.40%` at step `2,000`).
   - This addendum aligns `H16e_M_S3`, `H16e_M_A5`, and `H16e_M2_A5` to the exact same **`2,000`-step** budget (`T_train = 32` for `M_S3`/`M_A5`, `T_train = 40` for `M2_A5`, `T_eval ∈ {64, 128, 256}`, locked seeds `[42, 137, 2026]`) so `H16e-v3` is strictly apples-to-apples with `H16e-v2`.
2. **Exact Identity-Anchored $SU(2)$ Multiplicative Geodesic Gate & Dedicated `cayley_ring` (`OBS-ORDA-26`):**
   - Linear quaternion blending `(1 - g_kv)*q_exec + g_kv*q_ret` with `dot < 0` sign flip induces a discontinuous hemisphere flip at $180^\circ$ involutions ($w = 0$) and shrinks $180^\circ$ rotations whenever $g_{\text{kv}} < 1$.
   - `A6_RelationalCellOp` uses:
     - Dedicated `cayley_ring` (`BoundedCayleySU2Head`) for `U_pre` -> northern-hemisphere canonicalized $\Delta U_\tau = U^{\text{pre}}_\tau (U^{\text{pre}}_{\tau-\text{span}})^\dagger$ in `V_ring` (`w >= 0`, preserving 100% of $SO(3)$ including $180^\circ$ at $w = 0$).
     - Exact identity-anchored $SU(2)$ multiplicative gating `dq_eff = dq_macro * dq_local`, where `dq_macro = norm((1 - g_kv)*I + g_kv*du_ret)` and `dq_local = norm(g_kv*I + (1 - g_kv)*dq_exec_raw)` (exact `dq_exec_raw` at `g_kv = 0`, exact `du_ret` at `g_kv = 1`, smooth geodesic everywhere with zero antipodal cut).
   - Verified pre-run `CS-08 <= 0.5%` non-embedding parameter parity across all 3 tasks: `H16e_M_S3 = 0.1874%`, `H16e_M_A5 = 0.1982%`, `H16e_M2_A5 = 0.1982%`.

## 2. Unchanged Literal Kill Gates (Identical to `PREREG-S116-AMENDMENT4`)

All kill gates, statistical tests (paired two-sided Student-$t$ with Holm-Bonferroni correction across seeds `[42, 137, 2026]`), and literal `CONFIRMED` / `PARTIAL` / `FALSIFIED` criteria remain **100% identical** to `PREREG-S116-AMENDMENT4` §2.
