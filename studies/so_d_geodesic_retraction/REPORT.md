# Two-Phase Study Report: $SO(d)$ Cayley Geodesic Step Retraction ($\gamma \in \{1, 1/2, 1/4\}$) & 16-Byte Unit-Spinor Rollback on `SmolLM2-360M`

- **Study Artifacts:** `studies/so_d_geodesic_retraction/`
- **Committed Protocol Records:**
  - Phase 1 (3-seed binary gate): `preregistration_phase1_binary_gate.md` (`SHA-256: 441867f0a81cf4323542ec1bf5a915140fedc3bc3e0e0aae72f2f677291c4d40`)
  - Phase 2 (5-seed geodesic retraction, clarified post-audit protocol record): `preregistration_phase2_geodesic_retraction.md` (`SHA-256: 41df4e46669f17a42da33351ea3e6180d44499e99255955006d76e197091ced9`; original pre-amendment lock SHA-256: `d505a3219240985cf66f508253a8c08eab3802f1cf087d1de09abfd62a1a0d84`)
- **Verified Study Certificate:** `so_d_geodesic_retraction_certificate.json`
  - `payload_sha256`: `9c96cf0ac5fd8aec6c9aec25b264059da94e4a14cc7dde51d0b04c41ee6179a6`
  - `certificate_sha256`: `ef1cda74445458021f148cafc1a9f618eac909122da876143d73a9316ed56146`
- **Hardware & Telemetry Policy Scope:** Live RTX 3080 Laptop GPU FP32 execution (`allow_tf32 = False`, `CUBLAS_WORKSPACE_CONFIG=:4096:8`, `torch.use_deterministic_algorithms(True)`), editing `model.layers[29, 30, 31].mlp.down_proj` on pretrained `HuggingFaceTB/SmolLM2-360M` (`f8027fd0eaeea54caa13c31d31b9fdc459c38b49`) with real `Salesforce/wikitext-2-raw-v1` (`b08601e04326c79dfdd32d625aee71d232d685c3`). All arms share an identical matched rank-`16` edit budget (`92,160` parameters, `0.00%` delta). Hardware determinism receipts (`phase1_hardware_determinism.json`, `phase2_hardware_determinism.json`) omit NVML power draw readings and certify determinism pins and functional provenance only (`energy_power_status = UNCONTROLLED_LAPTOP_NOT_CLAIMED`).

---

## 1. Exact-$\mathbb{Q}$ Non-Axis-Aligned $SO(6)$ Cayley Geodesic Geometry Oracle (`VERIFIED`)

In `verify_so_d_geodesic_retraction.py`, `verify_oracle_ast_purity()` enforces zero `ast.Div`, zero floats/complex, zero negative `ast.Pow`, zero `Fraction(str)`/`from_float`, and zero imports across all `7` Module A oracle functions. `certify_exact_so_d_cayley_oracle()` constructs the exact rational orthogonal complement projector $P_\perp = I_6 - \frac{1}{4}(u_1 u_1^\top + u_2 u_2^\top)$ for the non-axis-aligned orthogonal 2D protected flow basis $u_1 = (1, 1, 1, 1, 0, 0)^\top$, $u_2 = (1, -1, 0, 0, 1, -1)^\top$, projects a dense skew-symmetric generator $S = P_\perp A P_\perp \in \mathfrak{so}(6)$, and evaluates $Q(\gamma S) = (I - \gamma S)(I + \gamma S)^{-1}$ strictly over `fractions.Fraction`:

| Geodesic Step $\gamma$ | $Q^\top Q = I_6$ | $\det Q$ | $\|Qx\|_2^2 - \|x\|_2^2$ | $\|Qu_1 - u_1\|_2^2 + \|Qu_2 - u_2\|_2^2$ | $\|Q(\gamma S) - I_6\|_F^2$ | Upper Bound $4\gamma^2\|S\|_F^2$ |
| :---: | :---: | :---: | :---: | :---: | ---: | ---: |
| `1/1` | `True` | `1/1` | `0/1` | `0/1` | `686384/310869` | `3757/1440` |
| `1/2` | `True` | `1/1` | `0/1` | `0/1` | `2489744/3992289` | `3757/5760` |
| `1/4` | `True` | `1/1` | `0/1` | `0/1` | `9703184/60189969` | `3757/23040` |

Both the exact Cayley contraction inequality $\|Q(\gamma S) - I_6\|_F^2 \le 4\gamma^2 \|S\|_F^2$ and strict geodesic monotonicity hold identically in $\mathbb{Q}$: `9703184/60189969 < 2489744/3992289 < 686384/310869`.

---

## 2. Phase 1 Prerequisite (`3` Seeds `[0, 1, 2]`, Binary Gate) — Honest `FALSIFIED`

On `SmolLM2-360M`, the top `320 / 960` `WikiText-2` validation eigenvectors explain `93.28%` (`layer_29`), `96.68%` (`layer_30`), and `99.83%` (`layer_31`) of activation variance, leaving `640` free orthogonal dimensions.

| Arm (`92,160` edit params, `0.00%` $\Delta$) | Commits (`/6`) | Sealed Holdout (`mean`, $\Delta$ vs Base) | `WikiText-2` Test Prose `KL` | `KL` Ratio vs `Arm D` | `B_0` Retention | Max Unit Shell Err |
| :--- | :---: | ---: | ---: | ---: | ---: | ---: |
| Unedited Base | — | `42.62%` (`+0.00 pp`) | `0.000000 nats` | — | `100.0%` | `0.000e+00` |
| `Control_Gen0_Untrained` | `[0,0,0]` | `42.62%` (`+0.00 pp`) | `0.000000 nats` | — | `100.0%` | — |
| `Arm_A_Naive_Additive_DeltaW` | `[6,6,6]` | `58.42%` (`+15.80 pp`) | `0.324329 nats` | `131.80x` | `100.0%` | `2.469e-01` |
| `Arm_B_Projected_Additive_FlowNull` | `[6,6,6]` | `59.98%` (`+17.36 pp`) | `0.008148 nats` | `3.31x` | `100.0%` | `4.776e-01` |
| `Arm_C_Cayley_Tangent_Unprojected` | `[6,6,6]` | `58.85%` (`+16.23 pp`) | `0.465795 nats` | `189.28x` | `100.0%` | `7.629e-06` |
| `Arm_D_Cayley_FlowNull_Spinor16B` | `[4,4,4]` | `49.91%` (`+7.29 pp`) | `0.002461 nats` | `1.00x` | `100.0%` | `6.676e-06` |

- **Phase 1 Gate Evaluation (`df = 2`):** `G1 = False` (`KL_A / KL_D = 131.80x`, max `Arm D` KL `0.002841 <= 0.005 nats`, but `hold_D - hold_A = -8.51 pp` against the `1.0 pp` margin and `p_Holm = 0.0603 >= 0.01`), `G2 = False` (`mean_gain = +7.29 pp`, `p_Holm = 0.0607 >= 0.01`), `G3 = True` (`max_shell = 7.629e-6 < 1e-5`, `18/18` live poison attacks blocked, `0.0` exact FP32 drift across all `24/24` rollbacks). Overall verdict: **`FALSIFIED`**.
- **Mechanistic Diagnosis:** On all `3/3` seeds, Round 6 (`R6_triage`) reached `100.0%` reserve accuracy with `100%` `B_0` retention and `shell_err <= 4.8e-6`, but marginally exceeded the cumulative `0.005 nats` ceiling (`KL = 0.00686 / 0.00594 / 0.00535 nats`). Binary rejection discarded `R6_triage` completely.

---

## 3. Phase 2 Geodesic Retraction (`5` Seeds `[0, 1, 2, 3, 4]`, $\gamma \in \{1, 1/2, 1/4\}$) — `CONFIRMED`

| Arm (`92,160` edit params, `0.00%` $\Delta$) | Commits (`/6`) | Retraction Rescues | Sealed Holdout (`mean`, $\Delta$ vs Base) | `WikiText-2` Test Prose `KL` | `KL` Ratio vs `Arm D` | `B_0` Retention | Max Unit Shell Err | Max Rel Real-Act Err |
| :--- | :---: | :---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Unedited Base | — | — | `41.51%` (`+0.00 pp`) | `0.000000 nats` | — | `100.0%` | `0.000e+00` | `0.000e+00` |
| `Control_Gen0_Untrained` | `[0,0,0,1,0]` | — | `41.51%` (`+0.00 pp`) | `0.000000 nats` | — | `100.0%` | — | — |
| `Arm_A_Naive_Additive_DeltaW` | `[6,6,6,6,6]` | `0` | `57.34%` (`+15.83 pp`) | `0.324084 nats` | `77.70x` | `100.0%` | `2.469e-01` | `4.463e-02` |
| `Arm_B_Projected_Additive_FlowNull` | `[6,6,6,6,6]` | `0` | `60.57%` (`+19.06 pp`) | `0.007764 nats` | `1.86x` | `100.0%` | `4.776e-01` | `7.975e-02` |
| `Arm_C_Cayley_Tangent_Unprojected` | `[6,6,6,6,6]` | `0` | `59.84%` (`+18.33 pp`) | `0.384662 nats` | `92.22x` | `100.0%` | `7.629e-06` | `7.860e-07` |
| `Arm_D_Cayley_FlowNull_Retract_Spinor16B` | `[5,5,5,5,4]` | `4` | **`60.31%`** (**`+18.80 pp`**) | **`0.004171 nats`** | **`1.00x`** | **`100.0%`** | **`7.629e-06`** | **`8.650e-07`** |

### Per-Seed Head-to-Head & Fresh Unseen Seed Subset (`3–4`) Breakdown

| Seed / Subset | Base Holdout | `Arm A` Holdout (`KL`) | `Arm D` Holdout (`KL`) | `Arm D - Arm A` (`KL` Factor) | `Arm D` Commits (`Retraction`) |
| :--- | ---: | ---: | ---: | ---: | :---: |
| Seed `0` (reused from Phase 1) | `42.19%` | `56.77%` (`0.075585`) | `61.98%` (`0.004431`) | `+5.21 pp` (`17.1x` lower) | `5/6` (`R6 at gamma=1/2`) |
| Seed `1` (reused from Phase 1) | `41.67%` | `59.64%` (`0.706872`) | `60.16%` (`0.004123`) | `+0.52 pp` (`171.4x` lower) | `5/6` (`R6 at gamma=1/2`) |
| Seed `2` (reused from Phase 1) | `44.01%` | `58.85%` (`0.190529`) | `60.94%` (`0.003412`) | `+2.09 pp` (`55.8x` lower) | `5/6` (`R6 at gamma=1/2`) |
| Seed `3` (**fresh unseen**) | `39.06%` | `56.25%` (`0.422964`) | `57.55%` (`0.004879`) | `+1.30 pp` (`86.7x` lower) | `5/6` (`0` retractions needed) |
| Seed `4` (**fresh unseen**) | `40.62%` | `55.21%` (`0.224469`) | `60.94%` (`0.004011`) | `+5.73 pp` (`56.0x` lower) | `4/6` (`R6 at gamma=1/2`) |
| **Reused Subset (`0–2`, `n = 3`)** | `42.62%` | `58.42%` (`0.324329`) | `61.02%` (`0.003989`) | `+2.60 pp` (`81.3x` lower) | `15/18` (`3` rescues) |
| **Fresh Unseen Subset (`3–4`, `n = 2`)** | `39.84%` | `55.73%` (`0.323717`) | `59.24%` (`0.004445`) | **`+3.52 pp` (`72.8x` lower)** | `9/12` (`1` rescue) |
| **Full Phase 2 (`0–4`, `n = 5`)** | `41.51%` | `57.34%` (`0.324084`) | **`60.31%`** (`0.004171`) | **`+2.97 pp` (`77.7x` lower)** | `24/30` (`4` rescues) |

### Per-Round Attribution of the `+11.11 pp` Seeds `0–2` Shift (Phase 1 `49.91%` -> Phase 2 `61.02%`)

| Round | Phase 1 `Arm D` Mean (`0–2`) | Phase 2 `Arm D` Mean (`0–2`) | Per-Round $\Delta$ | Contribution to 6-Round Mean |
| :--- | :---: | :---: | :---: | :---: |
| `R1_phase` | `33.33%` | `35.42%` | `+2.08 pp` | `+0.35 pp` |
| `R2_unit_scale` | `86.46%` | `88.02%` | `+1.56 pp` | `+0.26 pp` |
| `R3_logic` | `61.98%` | `67.71%` | `+5.73 pp` | `+0.95 pp` |
| `R4_compass` | `28.65%` | `27.08%` | `-1.56 pp` | `-0.26 pp` |
| `R5_chrono` | `49.48%` | `50.00%` | `+0.52 pp` | `+0.09 pp` |
| **`R6_triage` (retraction target)** | **`39.58%`** | **`97.92%`** | **`+58.33 pp`** | **`+9.72 pp` (`87.5%` of total shift)** |

### Locked Phase 2 Gate Evaluation (`df = 4` Exact Closed-Form Paired Student-$t$ + Holm–Bonferroni)

| Gate | Locked Criterion (Parsed Uniquely from Protocol) | Live Measured Result | Verdict |
| :--- | :--- | :--- | :---: |
| **`G1`** | `KL_A / KL_D >= 2.0x` AND `p_Holm < 0.01` AND `hold_D >= hold_A - 2.0 pp` AND `max_arm_d_KL <= 0.005 nats` | `KL_A / KL_D = 77.70x`, `t(4) = 10.895`, `p_Holm = 0.000806 < 0.01`, `hold_D - hold_A = +2.97 pp`, `max_arm_d_KL = 0.004879 <= 0.005` (also satisfies Phase 1's parsed `1.0 pp` margin: `passes_stricter_phase1_g1_margin = True`) | **`PASS`** |
| **`G2`** | `min_commits >= 4/6` (`5/5` seeds) AND `mean_gain >= +5.0 pp` AND `p_Holm < 0.01` AND `B_0 == 100%` | `commits = [5, 5, 5, 5, 4]`, `mean_gain = +18.80 pp`, `t(4) = 31.846`, `p_Holm = 1.739e-5 << 0.01`, `B_0 = 100.0%` | **`PASS`** |
| **`G3`** | `max_cayley_shell < 1e-5` AND `30/30` poison blocked AND `0.0` rollback drift | `max_cayley_shell = 7.629e-6` (`= 2^-17`, single FP32 rounding step in `layers[29..31]` GEMM; `< 1e-5` ceiling), `30/30` (`100.0%`) poison attacks blocked, `0.0` exact FP32 param/logit/spinor drift across all `36/36` rollbacks | **`PASS`** |
| **Overall** | `CONFIRMED` iff `G1 & G2 & G3` | `G1 = True`, `G2 = True`, `G3 = True` | **`CONFIRMED`** |

---

## 4. Limitations, Disclosures, & Verification Reproducibility

1. **`G1` Margin Change & Protocol Amendment Provenance:** Phase 2 used a `2.0 pp` `G1` holdout parity margin (`1.0 pp -> 2.0 pp` relative to Phase 1). `preregistration_phase2_geodesic_retraction.md` records the clarified post-audit protocol text (original pre-amendment lock SHA-256 `d505a3219240985cf66f508253a8c08eab3802f1cf087d1de09abfd62a1a0d84`) with zero realized Phase 2 outcomes embedded. `verify_so_d_geodesic_retraction.py` uniquely parses all `8` gate thresholds from both hashed Markdown files and confirms Phase 2 passes **both** the `2.0 pp` Phase-2 margin and Phase 1's dynamically parsed `1.0 pp` margin.
2. **Partially Dependent Seed Set (`0–2` Reused + `3–4` Fresh):** Phase 2 seeds `[0, 1, 2, 3, 4]` include the `3` seeds (`0–2`) observed during Phase 1 failure analysis alongside `2` newly added unseen seeds (`3–4`), making Phase 2 a partially dependent extension rather than an independent fresh `n = 5` replication. The fresh unseen subset (`3–4`, filtered dynamically by explicit seed ID) independently confirms the effect (`+3.52 pp` vs `Arm A`, `+19.40 pp` vs `Base`, `72.83x` lower prose KL), and per-round attribution shows `87.5%` (`+9.72 / +11.11 pp`) of the seeds `0–2` gain came directly from rescuing `R6_triage`.
3. **Arm-D Selective Acceptance Gate Asymmetry & FP32 Shell Margin:** The cumulative `KL <= 0.005 nats` acceptance/retraction gate applies selectively to `Arm D` (its defining mechanism), whereas `Arm A/B/C` execute all `6` edit rounds unconditionally under the identical `92,160`-parameter budget. Maximum unit-sphere shell norm error (`7.629e-6 = 2^-17`) reflects standard FP32 matmul accumulation near the `1e-5` ceiling (`max_real_act_rel_shell_err = 8.65e-7`), compared with `0.247–0.478` for additive updates (`Arm A/B`).
4. **Scope of Offline `--check --require-pinned` Verification:** Proves Module A pure-$\mathbb{Q}$ AST purity, exact-$\mathbb{Q}$ Cayley identities, and end-to-end cryptographic/statistical/gate consistency of the committed on-disk study artifacts against `PINNED_CERTIFICATE_SHA256`; it does not re-execute GPU model training.
