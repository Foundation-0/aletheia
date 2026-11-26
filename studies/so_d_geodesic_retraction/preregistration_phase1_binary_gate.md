# Pre-Registration Lock — Phase 1: Geometric Cayley Tangent Weight Editing vs. Additive Updates with 16-Byte Spinor Rollback (3 Seeds)

- **Status:** Pre-run locked prior to execution on seeds `[0, 1, 2]` (preserved as the immutable honest `FALSIFIED` prerequisite diagnosing the binary accept/reject obstruction addressed in Phase 2).
- **Hardware Telemetry Scope Policy:** Hardware determinism stamps certify determinism pins, device/driver identity, thermal/clock sanity, and functional/accuracy/KL-drift/rollback provenance only. Zero uncontrolled laptop wattage or per-token energy figures are claimed or reported.

## 1. Pretrained Backbone & Disjoint Prose Corpus

- **Backbone:** Pretrained `HuggingFaceTB/SmolLM2-360M` (`LlamaForCausalLM`, `32` layers, `d_model = 960`, `intermediate_size = 2560`, `vocab_size = 49152`, snapshot `f8027fd0eaeea54caa13c31d31b9fdc459c38b49`, FP32, `allow_tf32 = False`, `CUBLAS_WORKSPACE_CONFIG=:4096:8`, `torch.use_deterministic_algorithms(True)`).
- **Editable Projections (Matched Parameter Budget Across All 4 Arms):** `model.layers[l].mlp.down_proj.weight` (`960 x 2560`) for `l in {29, 30, 31}`, parameterized by identical rank-`r = 16` factors `(U_l, V_l)` (`2 * 960 * 16 = 30,720` edit parameters per layer, `92,160` total across `3` layers, `0.00%` parameter delta across all `4` arms).
- **General Prose Corpus (`Salesforce/wikitext`, `wikitext-2-raw-v1`, snapshot `b08601e04326c79dfdd32d625aee71d232d685c3`):**
  - Principal prose activation subspace (`U_flow`, top `r_flow = 320` eigenvectors per layer, leaving `640` orthogonal dimensions): `48` `validation` paragraphs (`val_rows[:48]`).
  - Prose anchor set `B_0` (`100` high-confidence `p_0 >= 0.90` next-token predictions): `24` disjoint `validation` paragraphs (`val_rows[48:72]`).
  - Disjoint reserve prose KL set (`KL(p_0 || p_t)` in nats): `32` disjoint `test` paragraphs (`test_rows[:32]`).

## 2. Four Arms + Untrained Control (3 Seeds `[0, 1, 2]`)

Across `6` cumulative English reasoning rounds (`R1_phase`, `R2_unit_scale`, `R3_logic`, `R4_compass`, `R5_chrono`, `R6_triage`), each split into disjoint `Practice` (`64` prompts), `Reserve` (`32` prompts), and `Sealed Holdout` (`64` prompts; `384` unseen holdout prompts/seed), with matched `loss < 0.08` early stopping and `4`-prompt prior practice replay across all `4` arms:

1. **`Arm_A_Naive_Additive_DeltaW`:** Unconstrained additive edit $W'_l = (I + U_l V_l^\top) W_l$.
2. **`Arm_B_Projected_Additive_FlowNull`:** Additive edit projected into the prose-flow orthogonal complement $W'_l = (I + P_{\perp,\mathrm{flow}}^{(l)} U_l V_l^\top P_{\perp,\mathrm{flow}}^{(l)}) W_l$ (no Cayley shell-norm preservation).
3. **`Arm_C_Cayley_Tangent_Unprojected`:** Shell-norm-preserving Cayley rotation $W'_l = \mathcal{C}(U_l V_l^\top - V_l U_l^\top) W_l \in SO(960) \cdot W_l$ via exact FP64 rank-`2r` Woodbury solve without prose-subspace projection.
4. **`Arm_D_Cayley_FlowNull_Spinor16B`:** $W'_l = \mathcal{C}(P_{\perp,\mathrm{flow}}^{(l)}(U_l V_l^\top - V_l U_l^\top)P_{\perp,\mathrm{flow}}^{(l)}) W_l$ coupled with a frozen specialist editor (`editor_sha256_invariant = True`), binary cumulative reserve gate (`reserve_gain > 0`, `prose_KL <= 0.005 nats`, `100%` `B_0` anchor retention, unit-sphere `max_shell_err < 1e-5`), and atomic `16 B` `<4f` unit-spinor checkpoint rollback (`UNIT_SPINOR_N2_TOL = 1/1024`, check-before-assign SHA-256 atomicity, verified against `6` adversarial/poisoned edit classes per seed = `18` live attacks).
5. **`Control_Gen0_Untrained`:** Untrained random editor under the identical rank budget and gate.

## 3. Pre-Execution Harness Calibration Addendum

Prior to this locked 3-seed run, an initial diagnostic run identified two harness bugs corrected uniformly across all `4` arms before locking:
1. Unnormalized layer-31 massive-activation probe vectors (`||W x||_2 = 17,677.6`) have 1 FP32 ULP of `2^-9 = 0.001953125`, falsely tripping the `1e-5` shell-norm gate despite `1.1e-7` relative accuracy; fixed by measuring `max_shell_norm_err` on unit-sphere normalized real activation directions (`x_hat = x / ||x||_2`) alongside logged relative real-activation shell error.
2. `torch.linalg.eigh` ascending eigenvalue order caused the prose-bomb poison test to slice bottom eigenvectors; fixed to slice top-16 prose eigenvectors (`u_flow[:, -16:]`) and added targeted orthogonal-subspace reserve-sabotage ascent (`POISON_6`).

## 4. Locked Pass / Fail Decision Gates (`df = 2` Paired Student-$t$ + Holm–Bonferroni)

- **`G1` (`Prose-KL Drift Cure`):** `mean_kl_A / mean_kl_D >= 2.0x` AND `mean_holdout_D >= mean_holdout_A - 1.0 pp` AND `p_Holm(G1_logKL_A_minus_D) < 0.01`.
- **`G2` (`Reserve Commits & Unseen Holdout Gain`):** `min_commits_D >= 4/6` on every seed AND `mean_holdout_gain_vs_base_pp >= +5.0 pp` AND `p_Holm(G2_holdout_D_minus_Base) < 0.01` AND `min_b0_retention_pct == 100.0%`.
- **`G3` (`Exact Shell Norm & 16 B Spinor Rollback`):** `max_cayley_shell_norm_err < 1e-5` across `Arm C` and `Arm D`, `18/18` (`100.0%`) live poison attacks blocked, and `0.0` exact FP32 parameter, logit, and spinor drift across `100%` of rollbacks.
- **Overall Verdict:** `CONFIRMED` iff `G1 AND G2 AND G3`; `PARTIAL` iff `G3 AND (G1 OR G2)`; `FALSIFIED` otherwise.
