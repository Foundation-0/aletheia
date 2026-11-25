# Track S95 — Local Aletheia Specialist Foundry & Live RTX 3080 Beyond-LoRA Matched-Budget Showdown

**Schema:** `aletheia.track_s95.specialist_foundry.v1`  
**Certificate Envelope SHA-256:** `43ac437b64fb71c46972337249d6a7ee72dcfa33498bd5fb86b86f7f99befe2e`  
**Certificate File SHA-256:** `b6cee3035ea86edeb4d33ad2cbf7cebcab0284b53b24e044b3cf9ee0f2f8d93d`  
**Payload SHA-256:** `18fce09c589a915aa04e61c0cfec64600aa57dbf2f7781683d72604f5d5ad7c8`  
**Live Hardware Receipt:** [mlos_zone_b_receipt.json](mlos_zone_b_receipt.json) (`d1ac6ab658a6f6c748b9f67bc73967d96ed5b9536dd44a870ac909a367e2bdad`; inner `receipt_sha256 = 095b08fa53087b6bb1b43e4d990b2ee2517803c8668f2e3f1149ca6edfe7e395`, `clean_hardware_run = true`, `exit_code = 0`, `anomalies = []`, `duration_ms = 13,582,504.472`)  
**Lean 4.36.0 Companion:** [SpecialistFoundryCerts.lean](SpecialistFoundryCerts.lean) (`9f502c556636ed6584ad6d31d39e43339a249e49076396f20e7af4a078b16d36`) — **`16/16` universally quantified (`∀`) pure-`Init` theorems (`1 [] + 3 [propext] + 12 [propext, Quot.sound]`, `0` `Classical.choice`, `0` `sorryAx`, `0` warnings)**  
**Law-4 Novelty Tier:** **`N1`** (`n0_prior_art_anchored = true`, `n1_exact_synthesis_verified = true`, **`n2_claims_count = 0`**)

---

## 1. Executive Summary & `OWN_TERMS_FIRST` Steelman

Track S95 builds, trains, evaluates, and certifies **three local super-specialized `Qwen/Qwen2.5-0.5B` (`apache-2.0`, `494M` base / `502,830,976` adapter-wrapped params) micro-models** live on an `8 GiB` NVIDIA GeForce RTX 3080 Laptop GPU under strict Zone-B determinism (`mlos stamp-run --zone B --require-gpu`, `seed = 42`, fixed-order chunked-LSE loss `chunk_size = 64`), wrapped in a mandatory fail-closed **Law-3 (`⫩`) Deterministic Verification Router** ([aletheia_specialist_router.py](aletheia_specialist_router.py)) so zero unverified micro-model output can pass downstream.

Rather than assuming standard LoRA is optimal, we executed a **strictly matched-parameter-budget `3 × 3 = 9`-run live RTX 3080 showdown** across all `168` target linear projections (`24` layers × `7` modules `q/k/v/o/gate/up/down`), holding trainable parameter count identically at **`8,798,208`** (`16 * (in_f + out_f)` per layer = `100.0000%` exact parity) across three distinct adapter geometries:

1. **`standard_lora`:** Dense rank-`16` additive baseline ($\Delta W = \frac{\alpha}{r} B A$, $\alpha = 32$).
2. **`blockh4_butterfly`:** Full-rank `S = 16`-stage orthogonal `BlockH4` Walsh–Hadamard butterfly with deterministic stage-distinct cyclic permutations (`0` extra trainable parameters, siliquant-native).
3. **`privsparse_ortho`:** Activation-calibrated base-nullspace projector $P_\perp$ (`r_null = 14`, `⧅`) plus exact isometric Householder reflection pairs $Q_{\mathrm{out}}(v_1, v_2) W_0 Q_{\mathrm{in}}(u_1, u_2)$ ($\kappa_2 = 1$ exact, exact identity at init).

### Key Empirical & Mathematical Findings (Honest Law-4 Three-Way Pareto Frontier)

- **Zero-Shot Base Collapse vs. Verified Specialist Lift:** Base `Qwen/Qwen2.5-0.5B` scores **`0/157` (`0.00%`)** across all four strict Law-3 tasks (`0/48` Scribe, `0/60` Weaver, `0/24` live `Lean 4.36.0` proofs, `0/25` R10+ escape audit). Fine-tuned empirical winners lift Law-3 gate-verified pass rate to **`138/157` (`87.90%`)** and deterministic exact accuracy across `Scribe + Prover_Audit + Prover_Tactics` to **`78/97` (`80.41%`)**, with **zero false accepts** (`0` unverified outputs pass the router).
- **`BlockH4-Butterfly` Shatters Track S78's `1.00` Forgetting Wall (`8.74×–22.58×` Lower `F/L` Ratio than LoRA):** Across all three specialists, `blockh4_butterfly` achieves **`F/L = 0.0606` (`2/33`)** on Scribe (**`8.7446×`** lower than LoRA `0.5300`), **`0.0108` (`27/2497`)** on Weaver (**`14.3087×`** lower than LoRA `0.1547`), and **`0.0251` (`37/1472`)** on Prover (**`22.5765×`** lower than LoRA `0.5675` — while reaching **lower held-out Prover NLL `1.3562` vs. LoRA `1.6570`** and solving `3/24` live unseen-track Lean proofs!).
- **Honest Failure Mode 1 (`FM-01-PRIVSPARSE-BASIS-DRIFT`):** Despite exact $\kappa_2 = 1$ isometry and winning `Weaver` on oracle score (`41/60` pathway, `47/60` operator tag, `60/60` strict JSON, `15/15` unseen-template `CS-03` smuggling detection, lowest Weaver NLL `0.0299`), unconstrained multiplicative Householder rotation $Q_{\mathrm{out}} W_0 Q_{\mathrm{in}}$ rotates pretrained weights off `SiLU`/`RMSNorm` privileged neuron axes (`Track S96` Theorem 3), exploding held-out base-domain NLL from `2.0399` to **`6.9604–10.8839`** (`F/L = 3.7448` Weaver, `35.3902` Scribe, and negative held-out learning `ΔL = -0.2280` with `0/24` live Lean tactics on Prover).
- **Honest Failure Mode 2 (`FM-02-BLOCKH4-UNFUSED-AND-ULP`):** Pure-PyTorch un-fused `BlockH4` stage loops run **`25.24×–32.13×`** slower than LoRA (`12.20–16.71 s/step` vs. `0.48–0.54 s/step`) and severely under-adapt Weaver (`9/60` exact, `0/15` `CS-03`). Independent weight-space audit ([COLLAB-QWEN4MAX-S95-BLOCKH4-HYBRID.md](../verification/reports/COLLAB-QWEN4MAX-S95-BLOCKH4-HYBRID.md)) diagnosed the exact physical mechanism on our frozen checkpoints: `81.40%` of Butterfly's learned $\Delta W$ entries fell below $\frac{1}{2}$-ULP of `bf16` $W_0$ and were zeroed upon release merge (vs. `8.73%` for LoRA), with near-zero cosine alignment (`0.003–0.019`) to LoRA's task subspace — directly motivating the preregistered `ButterflyHead-8+8` hybrid and a fused Triton/CUDA `BlockH4` kernel.
- **Honest Failure Mode 3 (`FM-03-PROVER-0_5B-TACTIC-CEILING`):** On completely unseen tracks (`S85–S88`), `Aletheia-Prover-0.5B` (`standard_lora`) proves **`5/24` (`20.83%`)** theorems end-to-end under live `Lean 4.36.0` (`2` universal `∀` theorems + `3` exact ground witness suites, `0` R10+ violations, `0` forbidden axioms), while `19/24` multi-step algebraic proofs fail closed at the Lean kernel (`0` false accepts) and escalate cleanly to frontier agents.

---

## 2. Pillar 1 — Strictly Disjoint Datasets, Matched Budget & Zone-B Hardware Provenance

All training and evaluation datasets (`847` total rows, **`553,151` B `< 5 MiB`**, secret-scrubbed, zero absolute user-home path leaks) and all three merged `model.safetensors` winners (`988,097,824` B each) are stored strictly outside `expedition/` (`WEIGHTS = 0` inside the repository):

| Dataset Split (`hf-releases/aletheia-specialists/datasets/`) | Disjointness Guarantee | Rows | Bytes | Verified SHA-256 |
| :--- | :--- | :---: | :---: | :--- |
| `scribe_train.jsonl` | Tracks `S15..S74` (`0` overlap w/ eval) | `200` | `158,751` | `c56143cb097ca3d37b1720aecb46b22addc7f3d9bc8241a0fc6f159cdc95eb94` |
| `scribe_eval.jsonl` | Unseen tracks `S75..S90` | `48` | `38,305` | `7c8cd498876fb71be9a42669418c851ec1df432e788f9515790862ffbd2b1551` |
| `weaver_train.jsonl` | Disjoint `S83/S84/S89` pairs + `7` CS-03 templates | `220` | `140,492` | `08c4f26cbf2af88efe3b8400d3d580105b697d23c1900825f8332a4ff4f4e5ee` |
| `weaver_eval.jsonl` | `45` unseen pairs + `15` unseen-template CS-03 traps | `60` | `38,656` | `06126f26f265e990c0e668e4577b2228ddb9878767be0adc144f78b944a89043` |
| `prover_train.jsonl` | `120` `S54..S84` tactics + `150` R10+ audit (`266` kept $\le 384$ tok) | `270` | `145,177` | `7b0885fdd3770a99c7fb7c3fb0baab8040ec420377011a95d22a8689a42a320f` |
| `prover_eval_tactics.jsonl` | Unseen live-verified `S85..S88` Lean theorems | `24` | `22,792` | `3f00d2e2e8db177eef789c898eb6cd53521b5de4a5f88798d12a7d3823a9dcfb` |
| `prover_eval_audit.jsonl` | Unseen-template 15-class R10+ escape snippets | `25` | `8,978` | `675f0725c43a6e37f965b07afcc1992ed8875b2f07610e003359ff6d4c2fb620` |

**Exact Matched Parameter Budget Formula (`Qwen/Qwen2.5-0.5B`, `S = 16`, `24` layers, `168` merged projections):**
$$P = 24 \times \Big(2 \cdot 16 \cdot (896+896) + 2 \cdot 16 \cdot (896+128) + 3 \cdot 16 \cdot (896+4864)\Big) = 24 \times 366{,}592 = 8{,}798{,}208$$

---

## 3. Pillar 2 — Live RTX 3080 `3 × 3` Matched-Budget Beyond-LoRA Showdown

All metrics below are computed purely over exact $\mathbb{Q}$ (`fractions.Fraction` / `Decimal ROUND_HALF_UP`, zero floats) from [rtx3080_s95_foundry_results.json](rtx3080_s95_foundry_results.json) (`80592b79...`). Held-out base-domain retention baseline on 16 unseen technical/code passages is $\mathrm{NLL}_{\mathrm{base},0} = \frac{20399}{10000} = 2.0399$.

### 3.1 `Aletheia-Scribe-0.5B` (Held-Out Unseen Tracks `S75..S90`, `N = 48`, $\mathrm{NLL}_{\mathrm{tgt},0} = 0.2719$)

| Arm (`P = 8,798,208`) | Strict JSON | Exact All-7 | Hygiene F1 | Base NLL (`ΔF`) | Target NLL (`ΔL`) | Exact `F / L` Ratio | Peak VRAM | Train Time | Inference |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Base `Qwen2.5-0.5B` | `0/48` | `0/48` (`0.00%`) | `0.0000` | `2.0399` (`0`) | `0.2719` (`0`) | — | — | — | `294.23 ms` |
| **`standard_lora` (Winner)** | **`48/48`** | **`48/48` (`100.00%`)** | **`1.0000` (`1`)** | `2.1840` (`+0.1441`) | **`0.0000`** (`0.2719`) | `1441/2719` (`0.5300`) | **`2,181 MiB`** | **`103.33 s`** | `193.45 ms` (`362.71 tok/s`) |
| `blockh4_butterfly` | `48/48` | `40/48` (`83.33%`) | `0.9000` (`9/10`) | **`2.0561` (`+0.0162`)** | `0.0046` (`0.2673`) | **`2/33` (`0.0606`, `8.7446×` better)** | `3,296 MiB` | `3,320.17 s` (`32.13×`) | `160.08 ms` (`438.32 tok/s`) |
| `privsparse_ortho` | `41/48` | `41/48` (`85.42%`) | `0.8923` (`58/65`) | `10.8839` (`+8.8440`) | `0.0220` (`0.2499`) | `29480/833` (`35.3902`) | `2,194 MiB` | `334.05 s` | `153.93 ms` (`454.75 tok/s`) |

### 3.2 `Aletheia-Weaver-0.5B` (Held-Out `45` Unseen Mesh Pairs + `15` Unseen-Template `CS-03` Traps, `N = 60`, $\mathrm{NLL}_{\mathrm{tgt},0} = 2.1083$)

| Arm (`P = 8,798,208`) | Strict JSON | Exact All-5 | Pathway (`⧅/⦺/⧇`) | `CS-03` TP / F1 | Base NLL (`ΔF`) | Target NLL (`ΔL`) | Exact `F / L` Ratio | Peak VRAM | Train Time |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Base `Qwen2.5-0.5B` | `0/60` | `0/60` (`0.00%`) | `0/60` (`0.00%`) | `0/15` (`0.0000`) | `2.0399` (`0`) | `2.1083` (`0`) | — | — | — |
| `standard_lora` (Retention Pareto) | `57/60` | `34/60` (`56.67%`) | `39/60` (`65.00%`) | **`15/15` (`1.0000`)** | `2.3600` (`+0.3201`) | `0.0394` (`2.0689`) | `3201/20689` (`0.1547`) | **`1,857 MiB`** | **`106.32 s`** |
| `blockh4_butterfly` | `38/60` | `9/60` (`15.00%`) | `24/60` (`40.00%`) | `0/15` (`0.0000`) | **`2.0615` (`+0.0216`)** | `0.1107` (`1.9976`) | **`27/2497` (`0.0108`, `14.3087×` better)** | `2,662 MiB` | `2,683.45 s` (`25.24×`) |
| **`privsparse_ortho` (Oracle Winner)** | **`60/60`** | **`34/60` (`56.67%`)** | **`41/60` (`68.33%`)** | **`15/15` (`1.0000`)** | `9.8231` (`+7.7832`) | **`0.0299`** (`2.0784`) | `3243/866` (`3.7448`) | `1,872 MiB` | `235.48 s` |

### 3.3 `Aletheia-Prover-0.5B` (Held-Out `24` Live Unseen-Track `S85..S88` Lean Theorems + `25` Unseen-Template R10+ Audit, $\mathrm{NLL}_{\mathrm{tgt},0} = 2.2394$)

| Arm (`P = 8,798,208`) | Live Lean Kernel Pass | R10+ Audit Exact / F1 | Base NLL (`ΔF`) | Target NLL (`ΔL`) | Exact `F / L` Ratio | Peak VRAM | Train Time | Tactics / Audit Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Base `Qwen2.5-0.5B` | `0/24` (`0.00%`) | `0/25` (`0.0000`) | `2.0399` (`0`) | `2.2394` (`0`) | — | — | — | `466.67 ms` / `225.05 ms` |
| **`standard_lora` (Winner)** | **`5/24` (`20.83%`)** | **`25/25` (`1.0000`)** | `2.3704` (`+0.3305`) | `1.6570` (`0.5824`) | `3305/5824` (`0.5675`) | **`2,572 MiB`** | **`180.66 s`** | `620.65 ms` / `67.67 ms` |
| `blockh4_butterfly` | `3/24` (`12.50%`) | `23/25` (`0.9444`, `17/18`) | **`2.0621` (`+0.0222`)** | **`1.3562` (`0.8832`)** | **`37/1472` (`0.0251`, `22.5765×` better)** | `4,237 MiB` | `5,598.22 s` (`30.99×`) | `428.86 ms` / `49.13 ms` |
| `privsparse_ortho` | `0/24` (`0.00%`) | `25/25` (`1.0000`) | `6.9604` (`+4.9205`) | `2.4674` (`-0.2280`) | `NEG_LEARNING` | `2,588 MiB` | `467.56 s` | `252.03 ms` / `47.63 ms` |

**Live `Lean 4.36.0` Kernel-Verified Unseen-Track Theorems Solved (`0` R10+ Violations, `0` Forbidden Axioms):**
- `standard_lora` (`5/24`): `SovereignStackFourthOrder.borromean_4way_non_degeneracy_universal`, `S87UniversalHigherOrderAtlas.ceer_five_gate_borromean_necessity_universal`, `S87UniversalHigherOrderAtlas.s87_corpus_anchored_witness_suite`, `AletheiaMeshEngine.k16_balanced_order1_to_4_exponential_collapse`, `AletheiaMeshEngine.k8_balanced_order1_to_4_total_5cell_extinction`.
- `blockh4_butterfly` (`3/24`): `S87UniversalHigherOrderAtlas.s87_corpus_anchored_witness_suite`, `AletheiaMeshEngine.k16_balanced_order1_to_4_exponential_collapse`, `AletheiaMeshEngine.k8_balanced_order1_to_4_total_5cell_extinction`.

**Deployed Merged Release Weights (Strictly Outside `expedition/` in `hf-releases/aletheia-specialists/`, `988,097,824` B each):**
- `aletheia-scribe-0.5b/model.safetensors` (`standard_lora`): `e9dc8ec52ff575c110279ab54cf8094513a6eb4a412eb0bff359d8a382f3106e`
- `aletheia-weaver-0.5b/model.safetensors` (`privsparse_ortho`): `8f264babea3b5f6e424e609b32036237f9fc9ea894bc2950bbbacfa53248eb5c`
- `aletheia-prover-0.5b/model.safetensors` (`standard_lora`): `ca62bd458f32caab25949a41aa3b8c64cf39e688c00a2e427e61d3c2d4d93755`

*(Note: Because `privsparse_ortho` traded base-domain retention `ΔF = +7.7832` for `+2/60` Weaver pathway accuracy, production deployments that reuse a single model across general tasks should prefer Weaver's retention-Pareto `standard_lora` checkpoint `aeaf2473...` or the preregistered `ButterflyHead-8+8` hybrid; single-purpose dedicated Weaver workers behind the Law-3 gate suffer zero external contagion from base-domain drift.)*

---

## 4. Pillar 4 — `thinkingmachines/Inkling-2-Mini` (`inkling2_loop`) Scaling Transfer

Cross-pinned verbatim against `inkling2_mini_config.json` (`a7a349601f0984c4abf999c480ef775d8567d21f5f84b4e8a3e035b44f288dc2`) and frozen `Track S96` (`s96_beyond_lora_inkling_certificate.json`, SHA-256 `5de85fe677a714f1af93722a7034947d13bd3938519d17a94508e1a008cfdd44`):

- **Zero-Padding `BlockH4` Compatibility:** `hidden_size = 2304` and `intermediate_size = 1152` are both exact multiples of `4` and `16`, enabling native zero-padding transfer of `BlockH4-Butterfly` / `ButterflyHead-8+8`.
- **Exact `2×` Depth Reuse & `3×` Loop-Core Adapter Leverage (`SpecialistFoundryCerts.inkling2_loop_core_depth_reuse`):** `24` physical layers (`6` pre + `12` core `[6..18)` × `3` passes + `6` suffix) yield **`48` effective layers** (`48 / 24 = 2`), giving every loop-core adapter **`3×`** effective layer leverage (`gate_rank = 64`, `128` routed experts / `8` active = `1/16`, `mtp.block_size = 8`, `mtp.markov_rank = 256`, `NVFP4`).
- **Honest Hardware Roofline:** `20 GB` NVFP4 exceeds an `8 GiB` RTX 3080 (`20 / 8 = 5/2×`, `rtx3080_full_resident_fits = false`), fitting full-resident on a `>= 32 GiB` workstation (`workstation_32gib_full_resident_fits = true`) while `Qwen2.5-0.5B` serves as the fast Tier-1 `8 GiB` local specialist foundry (`~1.86–4.24 GiB` peak training VRAM).

---

## 5. Pillar 5 — Lean `4.36.0` Universal Theorems, Verification Receipts & Law-4 Honesty

### 5.1 Pure-`Init` `Lean 4.36.0` Companion (`SpecialistFoundryCerts.lean`, `16/16` Universal `∀` Theorems)

1. `oracle_gate_zero_false_accept` (`[propext, Quot.sound]`)
2. `oracle_gate_precision_strict_lift` (`[propext, Quot.sound]`)
3. `zero_contagion_routing_flux` (`[propext]`)
4. `token_compression_cost_strict_savings` (`[propext, Quot.sound]`)
5. `foundry_amortization_breakeven` (`[propext, Quot.sound]`)
6. `lora_exact_merge_distributivity` (`[propext]`)
7. `matched_adapter_parameter_budget_exact` (`[propext]`)
8. `blockh4_orthogonality_cleared` (`[propext, Quot.sound]`)
9. `blockh4_involution_cleared` (`[propext, Quot.sound]`)
10. `householder_2d_norm_preservation_cleared` (`[propext, Quot.sound]`)
11. `householder_pair_init_identity` (`[propext, Quot.sound]`)
12. `nullspace_projection_zero_base_forgetting` (`[]`, strictly zero axioms!)
13. `forgetting_learning_ratio_strictly_below_unity` (`[propext, Quot.sound]`)
14. `anti_goodhart_holdout_generalization_bound` (`[propext, Quot.sound]`)
15. `cs03_smuggling_obstruction_consistency` (`[propext, Quot.sound]`)
16. `inkling2_loop_core_depth_reuse` (`[propext, Quot.sound]`)

### 5.2 Complete Hardening & Verification Gate Receipts

- **Live `Lean 4.36.0` & R12 Scanner:** Direct `lean SpecialistFoundryCerts.lean` (`rc=0, stderr=0 B`), scrubbed 6-var env `lean --stdin` (`16/16` theorems verified, `r12_findings=0`), scratch `lake build` (`0` warnings), `0`-theorem file rejection, full R12 escape battery (`0` FP on `14` clean controls).
- **Exhaustive Single-Leaf Re-Signed Tamper Coverage (`SEC`, `FR0`, `FR1`):** **`476/476 = 100.0%`** single-leaf tamper rejection across ALL three verification surfaces (`SEC`, `FR0`, AND `FR1`; `0` bypasses, `0` crashes, `caller_immutable = true`), preserving all 5 independent algebraic pillar audits before the final payload-digest pin inside `secondary_audit_payload` (`0` oracle replay in `SEC`/`FR0`).
- **Direct 4-Surface v2.1 `zone_b_fuzzer`:** **`82/82 PASS`** (`CLI 25/25`, `FR1 19/19`, `FR0 19/19`, `SEC 19/19`; `bypasses = 0, crashes = 0`).
- **Live `aletheia-fast-mutate --guards require_ok --workers 2 --timeout 180 --max-mutants 0`:** **`244/244 KILLED = 100.0%`** (`s95_specialist_foundry_oracle.py 10/10`, `verify_s95_specialist_foundry.py 234/234`; `survived = 0, truncated = False, null_mutant = passed ×2`).
- **Null-Controlled Whole-File DFS AST `BoolOp` (`OP_SWAP + SUBCOND_DEL`):** **`74/74 KILLED = 100.0%`** (`oracle 6/6`, `verifier 68/68`; `survived = 0, timeouts = 0, null_rc = 0 ×2`).
- **Multi-Mode `-I`, Lean-Less CI & RO-Dir Parity (`0` Skips):** `14/14 OK` across `-I -B`, `-I -O -B`, `-I -B -W error`, `PYTHONHASHSEED=42`, `umask 077`, CI `chmod 644` + `0o555` RO-dir, bare `env -i PATH=/usr/bin:/bin`, and `env -i PATH=/usr/bin:/bin HOME=/nonexistent`.
- **Dual `aletheia audit-check --lean-audit --strict-ancestors --safety-scan --scripts verify_s95_specialist_foundry.py test_s95_specialist_foundry_r5.py aletheia_specialist_router.py`:** **`PASS ×2`** (`R12` & `FM`; `r4_scripts_passed = 3/3`, `lean_findings = 0`, `safety_findings = 0`, `bare_asserts = 0`, `leaks = 0`, `crlf = 0`, `pycache = 0`).

### 5.3 Honest Law-4 Novelty Accounting (`N0` / `N1`, `n2_claims_count = 0`)

- **`N0` (Prior Art Explicitly Credited):** Qwen2.5-0.5B (`apache-2.0`); Hu et al. (2021) LoRA; Dao et al. (2019/2022) Monarch/Butterfly structured linear maps; Householder (1958) reflections; OWM/OGD/GPM nullspace continual learning; Thinking Machines `Inkling-2-Mini` (`inkling2_loop`); upstream `Track S78` & `Track S96`; independent weight-space diagnosis `COLLAB-QWEN4MAX-S95-BLOCKH4-HYBRID.md`.
- **`N1` (Verified Synthesis & Live Empirical Showdown in Track S95):** Live Zone-B bare-metal RTX 3080 matched-parameter-budget (`8,798,208`) `3 × 3` showdown establishing the empirical `BlockH4` forgetting-ratio lift (`8.74×–22.58×` vs. LoRA) alongside explicit Law-4 failure modes (`FM-01..FM-03`), fail-closed Law-3 router (`aletheia_specialist_router.py`), field-complete Zone-B + R12 pure-$\mathbb{Z}/\mathbb{Q}$ verifier, and `16/16` universal `∀` pure-`Init` Lean `4.36.0` companion.
- **`N2` Claims:** **`0`**.

---

## 6. Frozen Companion-File Manifest & Reproducible Commands

| File | Lines | Bytes | Mode | SHA-256 |
| :--- | :---: | :---: | :---: | :--- |
| `SpecialistFoundryCerts.lean` | `282` | `14,425` | `0o644` | `9f502c556636ed6584ad6d31d39e43339a249e49076396f20e7af4a078b16d36` |
| `aletheia_specialist_router.py` | `584` | `23,427` | `0o644` | `33ca914432f5656a7cca83631f1fbe641796d23716cb3b20e791022778584c0d` |
| `lakefile.toml` | `5` | `122` | `0o644` | `4a379e6c951cbb4aa677557368d49d80735fdc65d9c398b981708ff67a40df91` |
| `lean-toolchain` | `1` | `25` | `0o644` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |
| `mlos_zone_b_receipt.json` | `93` | `2,647` | `0o600` | `d1ac6ab658a6f6c748b9f67bc73967d96ed5b9536dd44a870ac909a367e2bdad` |
| `rtx3080_s95_foundry_results.json` | `1` | `11,782` | `0o600` | `80592b79d6325340f333f1cbc058d78a38f04699d58eeeb3c12b0ac01eb5b0dd` |
| `rtx3080_s95_foundry_train.py` | `1,621` | `76,545` | `0o644` | `bb3e80da88cce8a31baeb4a3f68b8cb9416972e04a1f00e92d4e3047d52c6bef` |
| `s95_specialist_foundry_certificate.json` | `1` | `17,105` | `0o600` | `b6cee3035ea86edeb4d33ad2cbf7cebcab0284b53b24e044b3cf9ee0f2f8d93d` |
| `s95_specialist_foundry_oracle.py` | `805` | `33,806` | `0o644` | `4089d61effcc4b4eb5d435378f5cee7af2d54467f2ae1d222403e8ab3ee869f6` |
| `test_s95_specialist_foundry_r5.py` | `997` | `62,758` | `0o644` | `ae16381c6e3d422d7232d288ea02391e878b495fe7a8dc80c26fc5b8020c078e` |
| `verify_s95_specialist_foundry.py` | `1,427` | `64,356` | `0o644` | `4aa626f219f0a5a83abdbf2b7f463d6c56aa2e0cb66105a7bfaf7287e524a9bb` |

```bash
# 1. Exact pure-Q certificate parity, Zone-B check & pinned live artifacts
python3 -I -B verify_s95_specialist_foundry.py --standalone | cmp - s95_specialist_foundry_certificate.json
python3 -I -B verify_s95_specialist_foundry.py --check s95_specialist_foundry_certificate.json --json
python3 -I -B verify_s95_specialist_foundry.py --verify-artifacts . --json

# 2. Live R12 static + scrubbed Lean 4.36.0 kernel verification
python3 -I -B verify_s95_specialist_foundry.py --verify-lean SpecialistFoundryCerts.lean --json

# 3. Full assertion-free R5 test suite (live Lean + 0-skip bare Lean-less CI)
python3 -I -B test_s95_specialist_foundry_r5.py -v
env -i PATH=/usr/bin:/bin python3 -I -B test_s95_specialist_foundry_r5.py -v
```
