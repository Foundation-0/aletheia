# Preregistration Protocol (`PREREG-S108`): Aletheia Cross-Pollination on Tokenizer Replacement × `Moissanite-Labs` Ecosystem × `Inkling-2-Mini` Looping (`H8a`, `H8b`, `H8c`)

- **Protocol ID:** `PREREG-S108-TOKENIZER-CROSS-POLLINATION-INKLING-LOOP`
- **Status:** `LOCKED_PREREGISTRATION` *(auto-captured & locked per `SOP-12`, 2026-11-25; grounded in live SOP-9 excavation of `Moissanite-Labs/{tokenpage, scry, nullmodem, abios, spliceware, siliquant, exorien}` + verified Tracks `S92`, `S96`, `S100`, `S104`)*
- **Universal Tokenizer-Invariant Metric (Mandatory Anti-`CS-08` / Anti-`CS-11` Gauge Rule):** Because different tokenizers and tokenizer-free models produce completely different sequence lengths, **perplexity-per-token is strictly forbidden as a cross-architecture metric**. Every experiment MUST report **exact Bits-Per-Byte (`BPB = total_NLL_nats / (total_UTF8_bytes * ln 2)`)** at **matched total parameter budget ($\pm 0.5\%$) AND matched total training/inference FLOPs ($\pm 1.0\%$)** across identical held-out byte streams (`English Wikipedia`, `Python source`, `S92 Classical Arabic`, and `ABIOS/SYM-2P + aletheia calculus` agent traffic), across **$\ge 3$ seeds (`42, 137, 2026`)**.
- **Mandatory Law-4 `N0` Prior-Art Anchors (Zero False `N2` Claims):**
  1. **Standard BPE (`Qwen2.5` / `SmolLM2` / trained domain BPE)** — flat discrete lookup table baseline.
  2. **Byte Latent Transformer (`BLT`, Pagnoni et al. Dec 2024)** — auxiliary byte-LM entropy patching + local byte encoder/decoder.
  3. **`H-Net` (Hwang, Wang, & Gu, Jul 2025)** — end-to-end learnable hierarchical dynamic byte chunking.
  4. **`word2ket` / `TT-Embeddings` (Panahi et al. ICLR 2020; Hrinchuk et al. 2020)** — prior art for Kronecker/tensor-train embedding compression (explicitly credited in `Track S104`).
  5. **`Moissanite-Labs` Public Portals Audited Live (`SOP-9`, `isPrivate == false`):**
     - `Moissanite-Labs/tokenpage` (`CHARTER.md`, `charter/language-tracks`, PR `#1/#5/#13`): `7`-tokenizer ABIOS waste, Track A cross-language density survival, Track B learned symbolic language + translator, and the **`0.4272` representation-vs-readout gauge gap** (`11.32/11.49 = 98.52%` bits already present in hidden states vs `0.558` zero-shot text readout!).
     - `Moissanite-Labs/scry` (`CHARTER.md`, PR `#4`): training without English, dense symbolic cognition, small phone/browser translator, mandatory human-readable audit traces.
     - `Moissanite-Labs/nullmodem` (`CHARTER.md`, PR `#3` `2026-11-18-ram-wire-hash-cell-gossip.md`): below-text agent-to-agent exchange (KV caches, latent states, `1,088`-byte self-verifying `RAM == WIRE == HASH` cells with `4`-anchor admission + human-readable audit renderer).
     - `Moissanite-Labs/abios` (`PR #38/#39/#47/#51/#53`): `ABIOS/3` (`41.29%` fewer tokens than Markdown), `SYM-2P`, lossless `wire_lists.py`, spec-in-context readout recovery (`4–6/23 -> 18/23`).
     - `Moissanite-Labs/exorien` (`docs/direction.md`, `exorien/grounding.py`): explicit coordinate-frame / unit / referent grounding without implicit prose assumptions.

---

## Stage A / Stage B Aletheia Deconstruction of the "Tokenizer"

Stripping the label "tokenizer" reveals that static BPE silently conflates **four distinct mathematical operators** inside a single frozen, English-biased lookup table:
1. **Boundary Segmentation ($B^* \to \Sigma^*$):** Fixed greedy merges causing `1.99×–4.42×` Arabic token tax (`Track S100`), `2–3` raw byte tokens per `aletheia calculus` glyph (`⧄ ⧅ ⦷ ⟠ ⧇ ⦺ ⩩ ⫩`), and severe JSON/ABIOS fragmentation (`tokenpage#1`).
2. **Unstructured Lookup Lift ($\Sigma \to \mathbb{R}^d$, `token_embd` + `lm_head`):** Consumes `15–27%+` of active small-model parameters (e.g. `201,024 × 2,304 × 2 = 926M` untied params on `Inkling-2-Mini`!), encodes zero morphological/structural compositionality, and exposes a `75,968×` `S31` `DPI` row-concentration attack surface (`Track S100`/`S104`).
3. **Wire Serialization (`agent A -> text -> agent B`):** Forces continuous hyperspherical hidden states through a lossy discrete text bottleneck (`0.4272` gauge gap in `tokenpage#5/#13`), even when both agents share a harness (`nullmodem`).
4. **Compute-Depth Pacing (Clock Allocation):** Secretly assigns compute per byte! High-density symbols get starved of forward-pass depth while fragmented UTF-8 bytes burn redundant attention ticks.

**Exact-Operator Unification Thesis:** A tokenizer and a vector quantizer (`siliquant`) are **inverse halves of the same discrete-to-hypersphere map** ($B^* \leftrightarrow S^{d-1}$). Replacing static BPE with (a) **Hybrid Kronecker-Spherical compositional embeddings**, (b) **geodesic-curvature dynamic byte-to-sphere patching**, and (c) **looped `Inkling`-style compute pacing + Markov-coupled multi-byte prediction + `nullmodem` sphere-lattice cell transport** decouples all four functions cleanly!

---

## Track `H8a` (`EXP-Q09a`): Hybrid Kronecker-Spherical Compositional Embedding (`Track S104` Live Realization)

### Stage-B Operator & Law-5 Obstruction Repair
Pure rank-1 Kronecker embeddings $E(r, p) = A_r \otimes B_p$ fail `Track S104` **Theorem 8 & Theorem 10** (`shared_root_annihilated_by_orthogonal_patterns`: $\langle A_r \otimes B_p, A_r \otimes B_{p'}\rangle = 0$ whenever $\langle B_p, B_{p'}\rangle = 0$). Using `Track S104` **Theorems 14–16**'s repaired rank-2 hybrid projected onto $S^{d-1}$:
$$E_{\text{hyb}}(r, p) = \operatorname{Norm}_{S^{d-1}}\!\big(\,[A_r \otimes B_p \; ; \; A_r \; ; \; B_p]\,\big)$$
preserves strictly positive shared-root AND shared-pattern similarity even under orthogonal factors, enforces exact table-level **`C_row(E) = 1`** (`S31` `DPI` invariance), and compresses large multilingual/symbolic vocabularies (`scry` + `tokenpage` Track A/B + `S92` Arabic roots + `ABIOS` opcodes) by **`10×–575×`**, freeing `token_embd` parameters to move into the transformer core!

### Arms (Matched Total Model Params `~15M`, Equal Training FLOPs, Multi-Domain Corpus: English + Python + Arabic + ABIOS)
1. **Control A (`Flat-BPE`):** Standard flat `token_embd` (`V = 32,768`).
2. **Control B (`Rank1-Kron`):** Pure rank-1 $A_r \otimes B_p$ factored embedding (`word2ket` / `S104` naive baseline — directly tests `S104 Thm 8` obstruction empirically!).
3. **Arm 1 (`Hybrid-Kron-Sphere`):** `S104 Thm 14–16` `[A_r ⊗ B_p ; A_r ; B_p]` normalized onto $S^{d-1}$ where $(r, p)$ factorizes byte-ngram/morpheme root × morphological/structural pattern (reinvesting freed embedding params into core depth/width!).
4. **Adversarial Null (`Hybrid-Kron-RandPair`):** Identical `Hybrid-Kron-Sphere` architecture with **randomly hashed $(r, p)$ assignments** (tests whether real morphological/structural factoring beats random hashing!).

### Pass & Kill Gates (`H8a`)
- **`CONFIRMED`:** `Hybrid-Kron-Sphere` beats BOTH `Flat-BPE` AND `Rank1-Kron` AND `Hybrid-Kron-RandPair` by **$\ge 3\%$ lower BPB on Classical Arabic + ABIOS/operator domains ($\ge 2$ SE)** with **$\le 0.5\%$ degradation (or gain) on English/Python BPB**, while maintaining exact `C_row(E) = 1`!
- **`FALSIFIED`:** `Hybrid-Kron-Sphere` fails to beat `Flat-BPE` or `Hybrid-Kron-RandPair` on multilingual/symbolic BPB, OR `Rank1-Kron` matches `Hybrid-Kron-Sphere` (falsifying empirical impact of `Thm 8` at this scale).

---

## Track `H8b` (`EXP-Q09b`): Geodesic-Curvature Byte-to-Sphere Patching (`SpherePatch`) vs. BPE & `BLT` Entropy Patching

### Stage-B Operator
Eliminate static tokenization completely ($V_{\text{in}} = 256$ raw UTF-8 bytes!). A tiny causal byte encoder (`2`-layer local conv/SSM/window-attention, `< 5%` FLOPs) maps each raw byte $b_t$ onto $S^{d_b - 1}$. Instead of requiring a separate external pretrained byte-LM (`BLT`), trigger patch boundaries directly from the **intrinsic hypersphere geodesic angular velocity** of the byte stream:
$$\theta_t = \arccos\!\big(\langle u_t, u_{t-1}\rangle_{S^{d_b - 1}}\big) \in [0, \pi] \quad \Longleftrightarrow \quad \text{denominator-}\pi\text{ turn } \frac{\theta_t}{\pi} \in [0, 1],$$
pooling bytes between high-curvature turns ($\theta_t / \pi > \tau_{\text{turn}}$, regulated to match target average compression ratio $C \approx 4\text{–}6$ bytes/patch via a differentiable load-balance loss as in `H-Net`) straight onto the latent backbone's hypersphere $S^{d-1}$!

### Arms (Matched Total Params `~15M`, Matched Total FLOPs, Identical Byte Streams)
1. **Control A (`BPE-Std`):** Standard `32k` BPE transformer.
2. **Control B (`Fixed-Byte4`):** Fixed `4`-byte uniform patching (zero dynamic boundary detection).
3. **Control C (`BLT-Entropy`):** Auxiliary small byte-LM next-byte entropy patching (`BLT` `N0` prior-art anchor, matched patch rate $C$).
4. **Arm 1 (`SpherePatch-Geodesic`):** Intrinsic geodesic angular-velocity ($\theta_t / \pi$) dynamic byte-to-sphere patching (matched patch rate $C$, zero separate external byte-LM!).

### Pass & Kill Gates (`H8b`)
- **`CONFIRMED`:** `SpherePatch-Geodesic` achieves **strictly lower cross-domain BPB ($\ge 2\%$ improvement on Arabic + `ABIOS`/calculus + code, parity or better on English, $\ge 2$ SE)** vs. `BPE-Std` AND `Fixed-Byte4`, AND either **matches/beats `BLT-Entropy` at lower encoder FLOP overhead** OR cuts Arabic-vs-English BPB parity gap by **$\ge 25\%$** vs. `BPE-Std`.
- **`FALSIFIED`:** `SpherePatch-Geodesic` underperforms `Fixed-Byte4` or fails to match `BPE-Std` on cross-domain BPB at equal total FLOPs.

---

## Track `H8c` (`EXP-Q09c`): `Inkling-2-Mini` Looped Core × Tokenizer-Free Adaptive Pacing, Markov `MTP-8` Byte Head, & `nullmodem` Sphere-Lattice Cell Bus

### Stage-B Synthesis of Looping + Tokenizer Replacement
Directly tests the **three high-leverage interactions** between `thinkingmachines/Inkling-2-Mini`'s looped core (`Track S96`) and tokenizer replacement (`tokenpage`/`scry`/`nullmodem`):
1. **Part 1 — Adaptive Loop-Depth Pacing on the Clifford Torus (Replacing Static Token Compute Allocation):**
   - Feed variable-density patches (`SpherePatch` or dense `ABIOS`/`scry` symbols) into a `CliffordTorus-HopfLoop` core (`H7c`) equipped with a lightweight **surprisal/curvature loop router** choosing $r(p) \in \{1, 2, 3, 4\}$ core passes per patch subject to a **strict mean loop budget $\bar{r} = 2.0$** (`CS-08` exact FLOP equality with uniform $R=2$ looping!).
   - *Hypothesis:* Spending `1` loop on predictable boilerplate patches and `3–4` loops on high-curvature / dense symbolic / reasoning patches strictly beats uniform $R=2$ looping at **identical average FLOPs per byte**!
2. **Part 2 — Reclaiming `token_embd`/`lm_head` via Markov-Coupled `MTP-8` Byte-Patch Decoding:**
   - Mirroring `Inkling-2-Mini`'s `MTP` (`block_size = 8`, `markov_rank = 256`, `target_layer_ids = [5, 23, 41, 48]`), replace the massive `32k`-vocab `token_embd`/`lm_head` with a `256`-byte vocabulary + compact Markov-coupled `8`-byte patch decoder fed from loop-exit states, reinvesting **100% of freed embedding parameters** straight into the looped core!
   - *Explicit Law-5 Ablation:* Compare **Markov-coupled `MTP-8`** vs. **independent parallel `MTP-8`** (testing the exact intra-patch byte-dependence obstruction!) vs. **tiny autoregressive local byte decoder** (`BLT`-style) at equal total params & FLOPs!
3. **Part 3 — `nullmodem` Zero-Tokenizer Agent-to-Agent Sphere-Lattice Cell Bus (Closing `tokenpage#5`'s `0.4272` Readout Gauge Gap):**
   - On `tokenpage#5`'s structured multi-field agent task (`11.49`-bit ground-truth state), compare two instances of the looped hypersphere model communicating via:
     - *(Baseline 1)* English JSON text tokens,
     - *(Baseline 2)* `ABIOS/3` compact symbolic tokens,
     - *(Arm 3 — `NullModem-SphereCell`)* Direct transmission of loop-exit latent states on $S^{d-1}$ quantized via **denominator-$\pi$ `EQ(S^{d-1})` / $E_8$ lattice indices** wrapped in a self-verifying `RAM == WIRE == HASH` cell (`nullmodem#3`, `SHA-256`/BLAKE3 checked) + a mandatory **human-readable audit decoder** (`scry`/`nullmodem` oversight requirement!).
   - *Hypothesis:* `NullModem-SphereCell` beats BOTH English JSON and `ABIOS/3` on **(bits on wire × recovered task accuracy)** AND cuts `tokenpage#5`'s `0.4272` representation-vs-readout gauge gap by **$\ge 50\%$**, while maintaining **$\ge 95\%$ human-readable audit-decoder fidelity**!

### Pass & Kill Gates (`H8c`)
- **Part 1 (`CONFIRMED`):** Adaptive loop pacing ($\bar{r}=2.0$) beats uniform $R=2.0$ looping AND random-budget pacing null by **$\ge 2\%$ BPB or $\ge 8$ pp multi-hop reasoning accuracy ($\ge 2$ SE)** at identical mean FLOPs/byte.
- **Part 2 (`CONFIRMED`):** Reinvesting reclaimed `token_embd`/`lm_head` params into the looped core with Markov-coupled `MTP-8` (or local byte decoder) matches or beats equal-total-param BPE on multi-domain BPB AND beats independent parallel `MTP-8` by **$\ge 5\%$ BPB** (confirming the intra-patch coupling obstruction!).
- **Part 3 (`CONFIRMED`):** `NullModem-SphereCell` strictly Pareto-dominates both English JSON and `ABIOS/3` on `(wire_bytes, exact_task_accuracy)`, cuts readout gauge gap by $\ge 50\%$, and passes $\ge 95\%$ audit-decoder round-trip check; **`FALSIFIED`** if `ABIOS/3` matches or beats `NullModem-SphereCell` at equal bytes, or if the human audit decoder fails `< 90%`.

---

## Execution Order & Pre-Flight Red-Team Gate
1. **Pre-Flight Cross-Family Design & Prior-Art Audit (CPU-Only, Zero GPU Burn):** Route BOTH `PREREG-S107` and `PREREG-S108` through `@council-router` for independent mathematical/systems red-teaming (including live looped-architecture perspective and strict `CS-08` FLOP-accounting verification) BEFORE launching GPU training.
2. **GPU Execution Sequence (`mlos gpu-lease --mode train` on RTX 3080):**
   - Finish active **`Track S106` (`H1–H4` $\to$ `H5` $\to$ `H6a–H6c`)** first (unperturbed!).
   - Use **`H6c`'s live pilot diagnostics** + pre-flight council red-team sign-off to launch **`PREREG-S107` (`H7a`, `H7b`, `H7c`)** and **`PREREG-S108` (`H8a`, `H8b`, `H8c`)** cleanly!
   - Preserve **`M1-H1`** (`64 GiB` MacBook M1 Max `aletheia handoff`) for live `26.4B` `Inkling-2-Mini` scaling validation once local `15M` micro-architectures clear their kill gates!
