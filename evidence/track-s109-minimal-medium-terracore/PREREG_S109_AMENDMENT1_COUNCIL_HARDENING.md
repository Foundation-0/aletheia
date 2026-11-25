# Preregistration Amendment 1 (`PREREG-S109-AMENDMENT1-COUNCIL-HARDENING`)

- **Status:** `LOCKED_PREREGISTRATION_AMENDMENT_1` *(2026-11-25; parent `PREREG-S109` SHA `1ca8a38fa3c7fd8dda5823741c867b93be09c2342eb35bafde18e9e7e510b1c9` remains 100% immutable and unmutated)*
- **Source Audits (Unanimous 3-Family Pre-Flight Consensus, `#2787`):**
  1. `verification/reports/COLLAB-INKLING2-S109-LOOP-MODULARITY-PREFLIGHT.md`
  2. `verification/reports/COLLAB-CLAUDE-S109-CS21-PREFLIGHT.md`
  3. `verification/reports/COLLAB-GLM53-S109-INFO-THEORY-PREFLIGHT.md`

All 5 unanimous blocking/high-severity consensus repairs below are **mandatory pre-execution overrides** before any GPU training runs under `EXP-Q10a..c`:

---

## Amendment 1 (`§H9c-CONTRACT` — Blocking Modularity & Gauge-Collapse Repair)
1. **Strict Bandwidth Cap on Continuous Residual:** Replace the unconstrained `~1,500–6,900`-bit continuous residual in Arm D with a strictly low-dimensional hypersphere residual $r \in S^{k-1}$ with **$k \le 32$, quantized at `3 bpw` $\implies B_{\text{res}} \le 96$ bits/problem**!
2. **Zero Skip-Path Graph Enforcement:** Assert via computational-graph check that **zero** edges connect `ext_in` directly to `ext_out` bypassing the Core.
3. **Canonical Chart & Two-Stage Frozen-Core Protocol:**
   - **Stage 1:** Train Core ($\mathcal{M} \to \mathcal{M}$) on canonical chart $Q_0$ with paraphrase-anchor invariance and $O(4)$ chart-jitter augmentation; **freeze and SHA-256 hash Core weights** upon Stage-1 completion.
   - **Stage 2:** Train external converters (`ext_in`, `ext_out`) with strict **`stop_gradient` into the frozen Core** (proving genuine modularity rather than monolithic end-to-end co-adaptation!).
4. **Strict Core-Only Scoring & Residual-Leak Kill Probe:** Scored task answers MUST be extracted strictly from the Core's discrete $\mathcal{M}$ output channel. Train an adversarial `<= 50k`-parameter MLP probe predicting the ground-truth answer directly from `r` alone: **if probe accuracy $\ge 25\%$ above chance, IMMEDIATELY FAIL-CLOSED with `CS21_RESIDUAL_LEAK`!**

## Amendment 2 (`CB-1..CB-6` + `§SWAP` — Blocking `CS-21` Anti-Smuggling & Swappability Gates)
Every run MUST execute and report all 6 anti-smuggling controls plus both swappability tests:
- **`CB-1` (Converter-Only / Identity Core):** Replace Core with identity pass-through (`acc` must collapse to chance).
- **`CB-2` (Frozen-Random Core):** Replace trained Core with fixed random-init weights (prevents outer converter from memorizing task mapping).
- **`CB-3` (Core-Lesion):** Replace Core outputs with batch-shuffled / mean states.
- **`CB-4` (Channel Ablation):** Zero out `r` (symbolic-only) and zero out symbolic skeleton (residual-only) independently on trained Arm D.
- **`CB-5` (Oracle-IR Upper Bound):** Feed ground-truth canonical IR directly into frozen Core so External-Converter DPI loss is measured exactly: $\text{DPI\_loss} := \text{acc}(\text{Oracle-IR}) - \text{acc}(\text{External-Translator})$.
- **`CB-6` (Regime-I Purely Syntactic Transducer Check):** Deterministic Regime-I outer scripts are **strictly syntactic transducers** (zero SymPy/SAT/algebraic simplification allowed!); verified by passing script output to a trivial baseline Core (`acc <= chance + 5 pp`).
- **`§SWAP` (True Zero-Retrain Converter Swap Gate):** Swap an independently trained Stage-2 external converter onto the **frozen SHA-pinned Core** with zero Core gradient steps:
  - Within-system swap drop **$\le 3$ pp**,
  - Cross-surface / paraphrase / second-language swap drop **$\le 5$ pp**.

## Amendment 3 (`CS-08` Total Compute, Parameter & Fair Baseline Parity)
1. **Triple Resource Parity (`±5%`):** Match **all three** budgets simultaneously across arms:
   - Total parameters $P_{\text{total}} = P_{\text{core}} + P_{\text{ext\_in}} + P_{\text{ext\_out}} + P_{\text{audit\_head}} = 15\text{M} \pm 0.5\%$ (explicitly charging the audit-decoder `lm_head`!),
   - Total training FLOPs $F_{\text{train\_total}}$ (`±5%`), AND
   - Per-problem inference FLOPs $F_{\text{infer}}$ (`±5%`, fixing the `R=6` `~4.4×` loop-FLOP mismatch against non-looped Arm A!).
2. **Fair Arm-A Baseline & Monolithic Upper-Bound Anchors:**
   - Give `English-CoT-15M` (Arm A) a tied compact vocabulary (`<= 4k` BPE or byte-level, eliminating the unfair `8.4M` embedding tax of a `32k` vocab inside a `15M` budget!).
   - Match supervision parity across arms (identical solver-derived intermediate traces available to Arm A as English CoT and Arms C/D as canonical IR).
   - Add **`Arm A'`** (direct-answer non-CoT floor) and **`Arm D-mono`** (end-to-end unfrozen monolithic control to quantify the exact modularity cost!).

## Amendment 4 (`H9a` Redundancy-Conservation Law & Sole Cross-Arm Metric)
1. **Information-Theoretic Precision:** Lossless compression is DPI-tight ($I(Y; B) = I(Y; X)$); `H9a` tests a **finite-capacity learnability obstruction** governed by residual redundancy $\Delta(B) = L - H_2(X) \to 0$ (retracting the informal "exponentially harder" phrasing in `PREREG-S109` line 29).
2. **Sharpened Arm B Controls:** Use raw-deflate / static order-0 arithmetic coding, add a **decompressor-emulation control** (can the `15M` Core even invert the coding?), and log auxiliary probe-LM bits/bit predictivity.
3. **Sole Cross-Arm Primary Metric:** **Exact-match task accuracy on raw UTF-8 ground truth** (plus end-to-end wall latency and peak VRAM). Cross-arm Bits-Per-Byte (`BPB`) is forbidden when comparing incompatible target encodings.

## Amendment 5 (Causal Intervention Audit Faithfulness & 3-Valued Verdicts)
1. **Counterfactual State-Patching Faithfulness:** Replace decodable-probe audit fidelity (vulnerable to `Track S100`'s `0.4272` gauge gap) with **causal intervention faithfulness**: patch intermediate Core states $h^{(r)} \leftarrow \tilde{h}^{(r)}$ from a counterfactual problem and require the human-readable audit decoder's emitted reasoning trace to shift consistently with the Core's actual patched output on **$\ge 85\%$** of interventions!
2. **Strict 3-Valued Verdicts:** Every sub-hypothesis (`H9a`, `H9b`, `H9c`) reports **`CONFIRMED` / `FALSIFIED` / `INCONCLUSIVE`** (using paired bootstrap / TOST equivalence intervals across seeds so underpowered runs never masquerade as confirmations or falsifications).
