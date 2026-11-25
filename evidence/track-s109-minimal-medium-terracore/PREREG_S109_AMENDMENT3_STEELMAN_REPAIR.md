# Preregistration Amendment 3 (`PREREG-S109-AMENDMENT3-STEELMAN-REPAIR`)

- **Status:** `LOCKED_PREREGISTRATION_AMENDMENT_3` *(2026-11-25; parent `PREREG-S109` `1ca8a38fa3c7fd8dda5823741c867b93be09c2342eb35bafde18e9e7e510b1c9`, `AMENDMENT1` `6f3d1e0b28d16e4290486e9adeb76c49bd8ebbf0954efb19d88621dc354bdcfd`, and `AMENDMENT2` `faf225067917b464ac25b2ae68ae1fa7bdf3179a2c461ec883490ea24ff9d7e3` remain 100% immutable and unmutated; strictly preserves ALL `AMENDMENT1` + `AMENDMENT2` contracts and 3-valued kill gates)*
- **Originating Law-2 / Anti-Strawman Steelman Trigger:**
  - The initial unmodified `gpu_results_h9a/` Zone-B baseline (`mlos_zone_b_s109_h9a.json`, `receipt_sha256=1587a95bfb5b7459701631f71b69bf71f4ab5f2e8896739698c0b5eac01e3aa2`, `result_sha256=187e348d19e2f78824dc63dc51bbd23dd291781cbf1f907b9e79c4fe6e14b282`) is **preserved untouched** as the honest prototype-friction baseline.
  - Pre-run single-seed GPU diagnostics revealed three concrete engineering/prototype bottlenecks that left **both** `Arm A` (`English-CoT-15M`, `7.57% / 6.84%`) and the prototype `ExternalSurfacePlate` (`0.00%` exact IR match) + `RigidInnerCore` (`6.1%`) stuck near the `6.25%` chance floor on the strictly tuple-disjoint (`0%` overlap) 2-step modular task `(a op b) + c + mod (mod 16)`:
    1. **Prototype `ExternalSurfacePlate` Global-Pooling Bottleneck (`0.00%` IR match):** Compressing `128` UTF-8 bytes into a single pooled vector before predicting `ir_len * V_M` logits destroyed positional operand extraction.
    2. **Prototype `RigidInnerCore` Antipodal Hopf Phase Flip (`W10-OBS-31`) & Flat Padding Pooling:** `phi_r = 2*pi*(r+1)/R` hit `216 deg` (`cos < 0`) at `R=5`, lacked a scaled per-loop phase embedding (`std=0.02`), pooled `<PAD>` token `-1` instead of `<EOS>`, and supervised `inter_head` only at the final loop rather than `h^(mid)`.
    3. **Prototype `Arm A` (`English-CoT-15M`) Non-CoT Single-Pass Pooling & Hot LR:** `lr=1.2e-3` on `d=480, L=8` over `1,000` steps with parallel auxiliary loss (never conditioning the answer step on the predicted intermediate step) and `<PAD>` byte `127` pooling prevented `Arm A` from performing genuine 2-step CoT reasoning — creating a strawman control against `Arm B`, `Arm C`, and `Arm D`.

---

## Locked Architectural & Training Steelman Repairs (Applied Symmetrically Before 3-Seed GPU Execution)

1. **Shell 3 `ExternalSurfacePlate` (`MHPlate` — Multi-Head Cross-Attention Surface Transducer):**
   - Replaces flat global pooling with `byte_emb(256, d_ext) + pos_emb(128, d_ext)` -> residual `Conv1d(k=5)` -> `1` `CausalCoreBlock(d_ext, n_heads=8)` -> multi-head cross-attention from `ir_len + 1` learned queries (`ir_len` IR slot queries + `1` residual slot query) -> `ir_head(d_ext -> V_M)` and `res_head(d_ext -> k_res)`.
   - Retains **zero** `ext_in -> ext_out` skip paths (`verify_zero_skip_paths == True`), strict Stage-2 `stop_gradient` into the frozen SHA-256-pinned Core, and ZERO oracle modifier labels in Stage 2.
2. **Shell 1 `RigidInnerCore` (`SteelmanCore` — Safe-Hopf Latent-CoT Core):**
   - Applies `Track S107` (`W10-OBS-31`) strictly non-antipodal Hopf loop clock $\phi_r = \pi (r+1) / (2R + 1) \in (0, \pi/2)$, `0.02`-scaled per-loop embedding `loop_emb[r]`, `alpha_raw` init `-1.2`, **causal last-non-pad (`<EOS>`) pooling** (making `ir_len=12` Native Mode and `ir_len=24` Human-Interface Mode bit-identical!), and supervises `inter_head` at intermediate loop state `h^(mid)` while `ans_head` reads final loop state `h^(R-1)` (genuinely decomposing step 1 -> step 2 in continuous $S^{d-1}$ latent space without decoding intermediate text tokens).
3. **Fair Steelman `Arm A` (`English-CoT-15M`, 2-Step Explicit Intermediate Conditioning):**
   - `MonolithicByteReasoner` uses **causal last-non-pad byte pooling** (`(byte_ids != 0).sum(dim=1) - 1`).
   - `Arm A` (`English-CoT-15M`, `use_cot_supervision=True`) performs genuine 2-step CoT: layers `0..3` predict `inter_logits`, inject `inter_emb(inter_pred)` at the active token slot (teacher-forced during first 50% of training, 100% self-predicted thereafter and at eval), and layers `4..6` compute `ans_logits`.
   - `Arm A'` (`Direct-Answer-15M`) and `Arm B` (`Compressed-Binary-15M`, raw-deflate `wbits=-15`) use the exact same `15M` backbone without intermediate CoT conditioning (matched `P_total`, `F_infer`, `F_train_total`).
4. **Exact Triple `CS-08` Resource Parity (`15.00M ± 0.5%`, `F_infer ± 5%`, `F_train_total ± 5%`):**
   - **Monolithic Arms (`Arm A`, `Arm A'`, `Arm B`):** `d_model = 512, n_heads = 8 (head_dim=64), n_layers = 7, ffn_dim = 1040, surf_len = 128`, `mono_steps = 2000`, `batch_size = 128`, `lr = 6e-4` (cosine with 5% warmup).
     - `P_mono = 15,023,648` (`+0.16%` vs `15.0M`), `F_infer = 4.022 GFLOPs/problem`.
   - **TerraCore Arms (`Arm C` / `Y = 1.00`, `Arm D` / `Y ∈ {0, 0.25, 0.50, 0.75}`, `Y_0.50_NoHodge`, `Arm D-mono`):** `core_d = 512, core_heads = 8, core_layers = 5, core_loops = 6, ir_len = 24` (`ir_len = 12` in Regime-I Native Mode), `ext_d = 480, ext_heads = 8, ext_layers = 1, surf_len = 128`, `stage1_steps = 1600`, `stage2_steps = 400` (`stage1 + stage2 = 2000 == mono_steps`), `batch_size = 128`, `lr = 6e-4` (Stage 1) / `8e-4` (Stage 2).
     - `P_core = 10.58M`, `P_ext_in + P_ext_out = 4.15M`, `P_audit_head = 0.28M`, **`P_total = 15,003,063`** (`+0.02%` vs `15.0M`, ratio `0.9986` vs `P_mono`!).
     - **`F_infer_terra / F_infer_mono = 0.9949` (`-0.51%`)**, **`F_train_terra / F_train_mono = 0.9949` (`-0.51%`)**.
5. **Immutable Preservation & Kill-Gate Integrity:**
   - All `3` seeds `[42, 137, 2026]` run live on RTX 3080 under `flock` + `mlos gpu-lease --mode train` + `mlos stamp-run --zone B --require-gpu` into `gpu_results_h9a_v2/` (`mlos_zone_b_s109_h9a_v2.json`) and `gpu_results_terracore/` (`mlos_zone_b_s109_terracore.json`).
   - All `H9a`, `H9b`, `H9c`, `H9d` 3-valued kill gates (`CONFIRMED` / `FALSIFIED` / `INCONCLUSIVE`), `CB-1..CB-6`, `CS21_RESIDUAL_LEAK`, `§SWAP`, `§PLATE-SWAP`, and `>= 85%` counterfactual $h^{(r)}$ audit faithfulness remain 100% unchanged and strictly enforced.
