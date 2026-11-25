# Preregistration Protocol (`PREREG-S109`): Minimal-Medium Core Reasoner & Boundary Translator Architecture (`H9a`, `H9b`, `H9c`)

- **Protocol ID:** `PREREG-S109-MINIMAL-MEDIUM-CORE-AND-TRANSLATOR`
- **Status:** `LOCKED_PREREGISTRATION` *(auto-captured & locked per `SOP-12`, 2026-11-25; directly operationalizes `Moissanite-Labs/scry` + `tokenpage` Track B + `nullmodem` + `Track S44` `CS-21` + `Track S92`/`S100` DPI translation bounds + `Track S96` looped latent depth)*
- **Originating PI Insight (Strict Zero-Language Core Wall):** Train a compact, low-hardware-footprint **Core Model** whose inputs and outputs are **100% exclusively a non-language computational medium $\mathcal{M}$** (dense typed symbols, code/AST, numbers, binary, matrices, or continuous hypersphere states) — **ZERO human-language tokens ever enter or leave the Core**, and **100% of human-language conversion happens strictly OUTSIDE the Core** via a swappable external script, compiler, or lightweight boundary translator.
- **Architectural Corollary (Dual Operating Modes):**
  1. **Native Mode ($\mathcal{M} \to \mathcal{M}$, External Converter Bypassed):** Agent-to-agent (`nullmodem`), tool/verifier/OS loops, and formal math/code reasoning run directly on the Core with **zero language-conversion overhead** and **zero language-vocabulary parameters**!
  2. **Human-Interface Mode (`Text -> External Converter -> Core(M -> M) -> External Converter -> Text`):** Swappable external language converters (English, Arabic, etc.) sit strictly outside the frozen Core, allowing one small Core to serve any language or modality without retraining Core weights.
- **Mandatory Anti-`CS-08` / Anti-`CS-21` Accounting Rule (Zero Hidden Offloading):**
  - Per `Track S44` (`CS-21` *Classical-Control Offloading Mirage*), we report **BOTH** (a) **Native Core-only metrics** (`P_core`, native `M -> M` accuracy, latency, VRAM) AND (b) **Full Human-Round-Trip metrics** counting **100% of external converter parameters, script CPU time, and translator latency**:
    $$P_{\text{total}} = P_{\text{core}} + P_{\text{ext\_in}} + P_{\text{ext\_out}} \le P_{\max} \quad (\pm 0.5\%), \qquad T_{\text{wall}} = T_{\text{ext\_in}} + T_{\text{core}} + T_{\text{ext\_out}},$$
    explicitly decomposing end-to-end errors into **External-Converter DPI Loss** vs. **Core Reasoning Error**!
  - No arm may smuggle a large external LLM as its outer translator while claiming small total budget.
- **Mandatory Law-4 `N0` Prior-Art Anchors (Zero False `N2` Claims):**
  1. **`COCONUT` (Chain of Continuous Thought)** — Hao et al., Dec 2024 (feeding continuous last hidden states back as next input embeddings without discrete token decoding).
  2. **`Huginn-3.5B` (Scaling Test-Time Compute with Latent Reasoning)** — Geiping et al., Feb 2025 (recurrent-depth latent thinking before text decoding).
  3. **Program-of-Thought / PAL / Formal-DSL Small Reasoners** (Chen et al. 2022; Gao et al. 2023) & `Moissanite-Labs/scry` (`CHARTER.md`).
  4. **Exact Prior Obstructions From Our Expedition:**
     - `Track S92` / `Track S100`: Surface translation destroys `51.96%` of overall scientific edges and `91.76%` of cross-discipline edges (Data Processing Inequality $I(Y; \text{Sym}) \le I(Y; X)$).
     - `Track S100` (`tokenpage#5/#13`): `0.4272` representation-vs-readout gauge gap (`98.52%` bits present in continuous hidden states vs. `0.558` discrete readout).
     - `Track S96` (`Thm 18`): Looped core per-pass quantization noise $G_3(\rho) = 1 + \rho + \rho^2$.

---

## Stage A / Stage B Taxonomy of "Most Efficient Thought Mediums"

| Medium Class | Boundary Converter | Information Density | Exact Structural Strength | Exact Law-5 Obstruction |
|---|---|---|---|---|
| **1. Raw Compressed Binary** (gzip/Huffman bits) | Deterministic script | Maximal Shannon bits/byte | Tiny wire length | **Shannon–Kolmogorov Predictability Inversion:** removes statistical structure, making next-step neural prediction exponentially harder! |
| **2. Canonical Typed Symbolic IR** (`SYM-2P` / S-expr / RPN / `aletheia` glyphs / minimal bytecode) | Deterministic parser (structured tasks) OR tiny `~3–4M` translator (prose) | `~10–15` bits/sym (`41–48%` shorter than prose; tiny vocab $V \le 2048$ cuts `token_embd` `30×–150×`) | Exact arithmetic/logic/AST compositionality, `100%` human-auditable & machine-checkable | **Translator-DPI Information Bottleneck (`Track S92`):** lossy prose-to-symbol compression permanently drops ambiguous/implicit semantic edges before the Core sees them! |
| **3. Continuous Hypersphere Latent Vectors** ($h^{(r)} \in S^{d-1}$ via looped core) | Byte/Sphere encoder + lightweight text/audit decoder | `~1,500–6,900` bits/vector (`3 bpw` $E_8$/$A_{16}$), zero `lm_head` softmax during thought! | Superposition / parallel hypothesis tracking, zero discrete readout collapse, direct `nullmodem` sharing | **Opacity & Exact-Symbol Drift:** continuous states drift on exact multi-digit integers/hashes and are opaque without a forced human-readable audit decoder! |
| **4. Hybrid Dual-Channel Core (Symbolic Skeleton + Continuous $S^{d-1}$ Residual)** | Dual front-end (typed symbol stream + continuous $S^{d-1}$ residual vector) + audit back-end | Combines exact discrete anchors + lossless continuous nuance | Keeps exactness of Class 2 AND continuous bandwidth of Class 3 while repairing `Track S92`'s Translator-DPI loss! | Higher interface coupling complexity — must prove strict Pareto dominance over Classes 1, 2, 3, and English-CoT at equal total `P_total` & `T_wall`! |

---

## Falsifiable Hypotheses, Arms & Kill Gates (`H9a`, `H9b`, `H9c`)

### Shared Benchmark Suite (Matched Total Budget `P_total = 15M ± 0.5%`, Equal Training Compute, `3` Seeds `42, 137, 2026`, Single RTX 3080)
Evaluated across **two strictly separated task regimes** so we expose *both* where pure symbolic/latent thought shines AND where translation loss hurts:
- **Regime I (Structured / Formal Reasoning):** Multi-step arithmetic & symbolic algebra, Horn-clause / propositional SAT deduction, short Python/bytecode execution tracing, and `ABIOS/3` multi-agent state-machine transitions.
- **Regime II (Ambiguous Natural-Language Reasoning):** Grade-school math word problems with distractor clauses, multi-hop natural-language entity/relation tracking with implicit pragmatic constraints (directly stressing the `Track S92` Translator-DPI bottleneck!).

### Four Matched-Total-Budget Arms (`P_total = 15M` Across Core + Boundary!)
1. **Control A (`English-CoT-15M`):** Standard `15M` transformer thinking via explicit English Chain-of-Thought tokens.
2. **Negative Control B (`Compressed-Binary-15M`):** Deterministic lossless compression script (`zlib`/arithmetic/Huffman bit-stream) wrapping a `15M` core (**tests `H9a` Shannon–Kolmogorov obstruction**).
3. **Arm C (`Pure-Symbolic-Core-11M + Trans-4M` — `scry` Pure Symbolic):** `11M` zero-English core trained exclusively on canonical typed S-expression / RPN / `SYM-2P` IR ($V = 1,024$ — saving `> 85%` of embedding params!) + deterministic script on Regime I / `4M` learned bidirectional translator on Regime II (**tests `H9b`**).
4. **Arm D (`Hybrid-Loop-Core-11M + Dual-Bridge-4M` — Latent-Symbolic Split Core):** `11M` **Clifford-Torus $S^3$ Looped Core** (`H7c`) performing $R \in \{1..6\}$ continuous hypersphere thought steps (zero `lm_head` during thinking!) + `4M` boundary encoder/decoder passing **BOTH** the canonical symbolic skeleton **AND** a compact continuous $S^{d-1}$ semantic residual vector (plus a mandatory human-readable trace decoder for `scry`/`nullmodem` oversight — **tests `H9c`**).

---

### Sub-Hypotheses & Explicit Kill Gates

- **`H9a` (Shannon–Kolmogorov Predictability Inversion Obstruction):**
  - *Hypothesis:* `Compressed-Binary-15M` (Arm B) degrades accuracy by **$\ge 15$ percentage points** vs. `English-CoT-15M` (Arm A) at equal training compute on BOTH Regime I and Regime II — proving that "fewer bytes via entropy-maximizing compression" is *anti-correlated* with neural compute efficiency (only *structure-preserving* compression helps!).
  - *Kill Gate:* If Arm B matches or beats Arm A, our Shannon–Kolmogorov obstruction is falsified and raw compressed-bit modeling becomes a live frontier!

- **`H9b` (Pure Canonical Symbolic Core `scry` — Regime Split & Translator-DPI Wall):**
  - *Hypothesis:* At equal total system budget (`15M` params), `Pure-Symbolic-Core` (Arm C):
    1. **Strictly dominates `English-CoT-15M`** on **Regime I** (structured/formal reasoning): **$\ge 10$ pp higher exact-match accuracy** AND **$\ge 2.0\times$ faster wall-clock latency (`ms/problem`)** at lower peak VRAM (thanks to `41–48%` shorter sequences + `V = 1,024` tiny `lm_head`).
    2. **Hits the `Track S92` Translator-DPI Bottleneck on Regime II** (ambiguous NL word problems): dropping accuracy relative to `English-CoT-15M` OR showing $\ge 30\%$ of its errors directly traceable to front-end translator information drop (`I(Y; Sym) < I(Y; X)`).
  - *Kill Gate:* `FALSIFIED` if Arm C fails to beat `English-CoT-15M` by $\ge 10$ pp OR $\ge 2.0\times$ speedup on Regime I. (If Arm C ALSO beats Arm A on Regime II with zero residual channel, then pure symbolic translation is even stronger than our `S92` DPI bound predicted!)

- **`H9c` (Hybrid Latent-Loop Core + Continuous $S^{d-1}$ Residual Bridge — Closing Both Walls!):**
  - *Hypothesis:* Passing a continuous hypersphere semantic residual vector alongside the symbolic skeleton into a looped continuous-thought core (Arm D, `11M + 4M = 15M` total):
    1. **Matches or beats `Pure-Symbolic-Core` (Arm C)** on Regime I,
    2. **Repairs $\ge 50\%$ of Arm C's Regime-II Translator-DPI accuracy gap** AND **beats `English-CoT-15M` (Arm A) on BOTH accuracy ($\ge 5$ pp) AND end-to-end wall-clock speed ($\ge 1.8\times$ faster, zero `lm_head` during intermediate latent loops!)** across 3 seeds ($\ge 2$ SE), AND
    3. **Maintains $\ge 90\%$ human-auditable trace fidelity** (its audit decoder faithfully explains the Core's intermediate reasoning steps, verified against ground-truth symbolic derivation!).
  - *Kill Gate (`FALSIFIED`):* Fails to beat `English-CoT-15M` on `(accuracy, wall_latency)` Pareto frontier at matched `15M` total budget, OR fails to recover $\ge 50\%$ of Arm C's Regime-II translator loss, OR audit-decoder faithfulness drops below `85%`.

---

## Integration With Active Queue & `Moissanite-Labs` Ecosystem
- **Directly feeds:** `Moissanite-Labs/scry` (core charter deliverable #1–#3), `Moissanite-Labs/tokenpage` (Track B codebook + translator), `Moissanite-Labs/nullmodem` (continuous $S^{d-1}$ state exchange + auditability), and `Moissanite-Labs/siliquant` (3-bit quantized small-core deployment on edge/CPU/phone hardware!).
- **Execution Slot:** Pre-flight council red-team alongside `PREREG-S107`/`PREREG-S108` (`@council-router`), then queued on RTX 3080 as **`EXP-Q10a..c`** immediately after `PREREG-S108` (reusing the exact `H7c` Clifford-Torus looped core & `H8b/H8c` byte-sphere translator harness!).
