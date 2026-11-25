# Track S93: Landmark Forensic, Exact-Operator, & Cross-Framework Tomography of OpenAI's $\omega_F = 9/4$ & `SpectralFlatLaw` (`openai/math`) $\times$ `open-goat/pequalnp-proofs` $\times$ Anthropic `vp-vnp` (`S75`/`S82`)

**Track ID:** `TRACK-S93-OPENAI-OMEGA94-VS-VPVNP-FORENSICS`  
**Schema Version:** `aletheia.s93_openai_omega94_vpvnp_forensics.v1`  
**Novelty Classification:** **`N1`** (exact pure-$\mathbb{Z}/\mathbb{Q}$ operator analysis, live forensic R12 trust & statement-fidelity audit, Law-5 `CAT(0)` reconciliation, and `18/18` universally quantified `∀` pure-`Init` `Lean 4.36.0` theorems)  
**Pinned External Commits:** `openai/math @ 3344da59991ed94f9ba711217b29c1d760badfa6` (`v4.34.1`) & `open-goat/pequalnp-proofs @ 1fa81fa383a2c3dd82666ddbc771e25731a37e8f` (`v4.36.0`) — read strictly read-only (`0` repo clones or snapshot files copied into `expedition/`)  
**Certificate File SHA-256:** `d4627fc4ed7a8af368bb33dad470cbea0677161afc4ffc6736a41171f51eeaa9` (`21,800` B, `0o600`)  
**Certificate Envelope SHA-256:** `0aefcf8f3e02bd61d2eed464835eaa14aba1c3d5cef0039d2a9c0cfaac35f116`  
**Payload SHA-256:** `668b0911f1bd1612596003f80af576b95956e615f1fb89cd1fcc77905ee37775`

---

## 1. Executive Summary & Explicit `N0` vs. `N1` Boundary

- **`N0` (External Published Monuments & Prior Expedition Tracks):**
  - OpenAI Nov 24, 2026 preprints & Lean formalizations (`openai/math`): *The matrix multiplication exponent is nine fourths* ($\omega_F = 9/4$, $\alpha_F = 1/2$, closed-form rectangular exponent, `ExactExponent.lean`, `RationalCircuits.lean`, `FieldFormula.lean`) and *Euclidean geometry in the asymptotic spectrum of tensors* (`SpectralFlatLaw.lean`, `BookCAT0.lean`, `Theorem 1.2` existence of spectral flats); prior upper bounds by Strassen (1969), Coppersmith–Winograd (1990), Alman (2021 laser barrier `2.3078`), Alman–Vassilevska Williams (2024 `2.371339`), OpenAI Staggered Extraction (Sep 2026 `2.371055`), Amanov–van den Berg–Zuiddam / Lü (`9/4` upper bound).
  - Anthropic `vp-vnp` (`11b6c7e3`, audited in `Track S75` & `Track S82`): `Thm C.1` Bruhat–Tits `CAT(0)` curvature, `Thm D.2` *Flat vs. Contracting* dichotomy on $\mathrm{Mat}_\mu(\mathbb{F}_2)$, `Rem D.3` non-Euclidean rank metric.
  - `open-goat/pequalnp-proofs` (`pequalnp.com/papers/note-1` 10 edge-function lower bounds, `CircuitLowerBounds/Helpers`, `CheckLemma.lean`, `check-lean.mjs`, `outside-guard.mjs`) and prior `Track S41` (Pólya `0/512`) & `Track S44` (static Lean envelope pre-filter).
- **`N1` (Track S93 New Exact Synthesis, Forensic Discoveries, & Machine-Checked Proofs):**
  1. **Dual-Model Statement-Fidelity Discovery in `openai/math`:** Live forensic inspection resolves the paper-vs-Lean division-gate question accurately: `ComparatorChallenges/MatrixExponent.lean` + `docs/107.md` expose ONLY **division-free** straight-line programs (`add`/`sub`/`mul` in `MvPolynomial I F`, `3` expected `sorry` challenge stubs), while internal `RationalCircuits.lean` + `FieldFormula.lean` **do** formalize **division gates (`Build.div` over `FractionRing(MvPolynomial)`)** and prove `omega F = 9/4` & `Rectangle.exponent_eq`, bridged via `SquareRankModel.lean` and `Integral/RingFormula.lean`. Across all `13` fetched proof/definition Lean files in `openai/math` and `15` proof files in `open-goat/pequalnp-proofs`, `aletheia#34` R10 finds **`0` non-import trust escapes**.
  2. **Unified Non-Euclidean `CAT(0)` Gram Obstruction Reconciling `SpectralFlatLaw` vs. `vp-vnp` `Rem D.3` & `Thm D.2`:** `SpectralFlatLaw.lean` explicitly builds ON `CATZero X` (`import OAI.Geometry.HyperbolicGroups.CATZero`). On any isometric convex Euclidean chart $e : C \hookrightarrow X$, normalized mean width equals triangle half-perimeter $P/2$, giving ratio $P / (P/2) = 2$ (cannot prove $\omega > 2$). Breaking past `2` to `9/4` requires leaving Euclidean flats to OpenAI's unit-arm `CAT(0)` tripod (`det G = -4 < 0`, $v^\top G v = -3 < 0$, Bruhat–Tits CN slack `2 > 0`, ratio `6 / (8/3) = 9/4`), which exhibits the exact same negative-Gram obstruction signature as `vp-vnp` `Rem D.3`'s $\mathrm{Mat}_2(\mathbb{F}_2)$ witness (`det G = -1/4 < 0`, $u^\top G u = -1 < 0$). Moreover, OpenAI's `Theorem 1.2` (existence of arbitrary-dimension spectral flats) directly supplies the Euclidean-flat price input required by `vp-vnp` `App. E`, while leaving `Thm D.2`'s $\mathrm{Mat}_\mu(\mathbb{F}_2)$ contraction question distinct.
  3. **`18/18` Universally Quantified (`∀`) Pure-`Init` `Lean 4.36.0` Library (`OmegaNineFourthsAndSpectrum.lean`):** Zero external imports, zero `Classical.choice`, `2` literal `[]` + `1` `[propext]` + `15` `[propext, Quot.sound]`, `0` warnings, `0` stderr.

---

## 2. Cryptographically Pinned Primary Provenance (`12` Wave-6/Forensic + `4` Upstream Expedition Certs)

### 2.1 Wave-6 Snapshot & Live GitHub Forensic Artifacts (`12/12` On-Disk Exact Match)

| Source ID | Repository | Size (B) | SHA-256 Prefix | Forensic Role |
|---|---|---|---|---|
| `oai_omega94_readme` | `openai/math` | `1,921` | `c83864717e5f42ac...` | OpenAI Nov 24 2026 omega_F = 9/4 preprint scope & citation |
| `oai_docs_107` | `openai/math` | `1,972` | `31d88810902fccb1...` | Lean formalization scope (division-free Comparator statement & closed-form rectangular formula) |
| `oai_exact_exponent_lean` | `openai/math` | `2,869` | `a0e2433ae4939e46...` | Lean proofs of square_exponent (9/4), dual_exponent (1/2), rectangular_exponent |
| `oai_euclidean_spectrum_readme` | `openai/math` | `2,090` | `06a50b3ce05458fb...` | Companion paper: Euclidean geometry in the asymptotic spectrum of tensors |
| `pnp_note1_text` | `open-goat/pequalnp-proofs` | `91,850` | `f8afe8d27b1d8582...` | pequalnp.com/papers/note-1: 10 Lean-checked edge-function lower bounds |
| `pnp_proofs_readme` | `open-goat/pequalnp-proofs` | `4,057` | `3978f486edf474c4...` | open-goat/pequalnp-proofs checker contract & lemma-leasing architecture |
| `oai_spectral_flat_law_lean` | `openai/math` | `5,898` | `b6e4a67710c1dae1...` | CATZero X + convex Euclidean chart -> P.diagonal = meanWidth |
| `oai_rational_circuits_lean` | `openai/math` | `2,431` | `f25885e4de68fbcf...` | Internal rational-circuit model with Build.div over FractionRing(MvPolynomial) |
| `oai_field_formula_lean` | `openai/math` | `1,053` | `d5d83f16abde382e...` | omega_eq (F : Field) : omega F = 9/4 & Rectangle.exponent_eq |
| `oai_comparator_matrix_exponent_lean` | `openai/math` | `4,504` | `a56cd2267e261903...` | Isolated division-free Comparator challenge file (3 sorry stubs) |
| `pnp_check_lemma_lean` | `open-goat/pequalnp-proofs` | `30,349` | `86997b026ef2b80d...` | Kernel replay, statement-env isolation, axiom allowlist, reduce text/waste screens |
| `pnp_outside_guard_mjs` | `open-goat/pequalnp-proofs` | `36,528` | `a4fde1897820a2a4...` | PR intake guard (plain blob 100644, UTF-8/NUL/bidi, header-only imports) |

### 2.2 Frozen Upstream Expedition Certificates (`4/4` On-Disk Exact Match)

| Track | Frozen Certificate | SHA-256 Prefix | Cross-Framework Bridge |
|---|---|---|---|
| `S41` | `track-s41-praxis-witness-encryption-tomography/praxis_we_tomography_certificate.json` | `006e0eb496188cf7...` | Polya 0/512 sign-map barrier & SOS rank-gap vs circuit lower-bound barriers |
| `S44` | `track-s44-formal-agent-quantum-hodge-tomography/formal_agent_quantum_hodge_certificate.json` | `214a1824a7d1705b...` | Prior static pequalnp proof-envelope pre-filter vs live CheckLemma.lean kernel replay |
| `S75` | `track-s75-vp-vnp-formal-audit/s75_vp_vnp_certificate.json` | `7e383c1cfe049372...` | Anthropic vp-vnp Thm C.1 CAT(0), Thm D.2 Flat vs Contracting, Rem D.3 det G = -1/4 |
| `S82` | `track-s82-vpvnp-cross-field-propagation/s82_vpvnp_propagation_certificate.json` | `10c1203cd9c9f80d...` | Executable T-13..T-15 formal trust gates & non-Euclidean code rank-metric witness |

---

## 3. Pillar 1 — Exact Pure-$\mathbb{Q}$ Analysis of OpenAI's Rectangular Formula $\omega_F(a,b,c)$

For positive weights sorted $x \ge y \ge z > 0$:
$$\omega_F(a,b,c) = x + y + \frac{\max((x+y)z - xy, 0)^2}{4xyz}$$

- **Square Exponent:** $\omega_F(1,1,1) =$ **`9/4`** (`2.250000`, irreducible excess `1/4` above output size `2`).
- **Dual Exponent:** $\alpha_F =$ **`1/2`** — for all $t \in [0, 1/2]$ (e.g., LoRA/rectangular rank $r \le \sqrt{d}$), $\omega_F(1,1,t) = 2$ (exact $O(n^2)$ linear-time regime); for $t \in (1/2, 1]$, exact super-quadratic penalty $\frac{(2t-1)^2}{4t} > 0$.
- **Exact $S_3$ Permutation Symmetry & General Harmonic Threshold:** All `6/6` permutations of `(1, 3/4, 1/2)` evaluate identically to **`169/96`** (`1.760417`), while `(1, 3/4, 3/7)` hits the exact harmonic threshold $xy/(x+y) = 3/7$ with $\omega_F =$ **`7/4`** (`1.750000`).
- **Strict Midpoint Convexity:** Verified exact Jensen gap $\frac{(t_2 - t_1)^2}{8 t_1 t_2 (t_1 + t_2)} > 0$ on `(1/2, 1) -> 1/24` (`0.041667`), `(2/3, 1) -> 1/80` (`0.012500`), and `(3/5, 4/5) -> 5/672` (`0.007440`).

| $t$ | $\omega_F(1,1,t)$ (Exact / 6-dp) | Penalty Above `2` | Linear $O(n^2)$ | Cor. 1.3 Floor | Exceeds Cor. 1.3 |
|---|---|---|---|---|---|
| `0` | `2` (**2.000000**) | `0` | `True` | `2` | `False` |
| `1/4` | `2` (**2.000000**) | `0` | `True` | `2` | `False` |
| `1/3` | `2` (**2.000000**) | `0` | `True` | `2` | `False` |
| `1/2` | `2` (**2.000000**) | `0` | `True` | `2` | `False` |
| `3/5` | `121/60` (**2.016667**) | `1/60` | `False` | `2` | `True` |
| `2/3` | `49/24` (**2.041667**) | `1/24` | `False` | `2` | `True` |
| `3/4` | `25/12` (**2.083333**) | `1/12` | `False` | `33/16` | `True` |
| `4/5` | `169/80` (**2.112500**) | `9/80` | `False` | `21/10` | `True` |
| `1` | `9/4` (**2.250000**) | `1/4` | `False` | `9/4` | `False` |

### 3.1 Historical Benchmark Comparison (Exact Pure-$\mathbb{Z}/\mathbb{Q}$, Strassen Power Bracket $2^{280} < 7^{100} < 2^{281}$)

| Benchmark | Exact Rational Exponent | Margin Above `9/4` |
|---|---|---|
| Naive cubic | `3` | `3/4` (**0.750000**) |
| Strassen (1969, exact lower bound 14/5 < log2 7) | `14/5` | `11/20` (**0.550000**) |
| Alman-Vassilevska Williams (2024) | `2371339/1000000` | `121339/1000000` (**0.121339**) |
| OpenAI Staggered Extraction (Sep 2026) | `474211/200000` | `24211/200000` (**0.121055**) |
| Coppersmith-Winograd Laser Barrier (Alman 2021) | `11539/5000` | `289/5000` (**0.057800**) |
| OpenAI Exact Exponent (Nov 24 2026) | `9/4` | `0` (**0.000000**) |

### 3.2 Corollary 1.2 Finite-Size Rank & Gate Floors ($n = k^4$)

| $k$ | Side $n = k^4$ | Output $n^2$ | Border Rank Floor $n^{9/4} = k^9$ | Nonscalar Gate Floor $\lceil n^{9/4}/2 \rceil$ | Naive $n^3$ | Rank / Output |
|---|---|---|---|---|---|---|
| `2` | `16` | `256` | **`512`** | **`256`** | `4,096` | `2x` |
| `4` | `256` | `65,536` | **`262,144`** | **`131,072`** | `16,777,216` | `4x` |
| `8` | `4,096` | `16,777,216` | **`134,217,728`** | **`67,108,864`** | `68,719,476,736` | `8x` |

---

## 4. Pillar 2 — Live Forensic Trust & Statement-Fidelity Audit (`T-13..T-15`)

- **`openai/math` (`3344da59...`, `v4.34.1`):**
  - **R10 15-Class Static Scan:** `13/13` fetched proof/definition Lean files have **`0` non-import trust-escape findings** (`0` `sorry`, `0` `axiom`, `0` `native_decide`, `0` `unsafe`, `0` `partial`, `0` `run_cmd`/`eval`). The `3` `sorry` lines live exclusively in `ComparatorChallenges/MatrixExponent.lean` (`L108, L119, L132`, standard `T-13` challenge stubs), and `2` meta lines live in `lakefile.lean` (`L307, L313`).
  - **Dual-Model Statement Fidelity:** `ComparatorChallenges/MatrixExponent.lean` + `docs/107.md` formalize division-free straight-line programs (`MvPolynomial I F`, cost `1` per `+`/`-`/`*`), whereas internal `RationalCircuits.lean` + `FieldFormula.lean` also formalize `Build.div` over `FractionRing(MvPolynomial)` and prove `omega F = 9/4` & `Rectangle.exponent_eq`.
  - **Honest Caveats:** Uses `Mathlib` + `Classical.choice`; single Lean `v4.34.1` kernel (no `nanoda` dual-kernel receipt observed); not locally rebuilt on `v4.36.0`; full human mathematical review of transitive definitions (`Rounds.installable`, `contact_of_installations`, `SpectralPlacementPrices`) remains external.
- **`open-goat/pequalnp-proofs` (`1fa81fa3...`, `v4.36.0`):**
  - **R10 15-Class Static Scan:** `15/15` fetched proof files (`10` `MetaComplexity/L*.lean` + `5` `CircuitLowerBounds/Helpers/*.lean`) have **`0` non-import trust-escape findings**.
  - **Checker Architecture (`CheckLemma.lean` + `check-lean.mjs` + `outside-guard.mjs`):** Full `Kernel.Environment.replay` (skipping `unsafe`/`partial`), isolated `stmtEnv = Mathlib + PEqualNP.Defs` (`redeclares` refused except `sameTheorem`), transitive axiom walk (`[propext, Classical.choice, Quot.sound]`), verifier binary SHA-256 pinning, `LAKE_ARTIFACT_CACHE=false`, and red-teamed `reduce` text/meta/waste screens. Remaining limitation: single Lean kernel (no independent `nanoda`).

| Formal Program | Toolchain | Proof Files (Escapes) | Challenge Stubs | `T-13` | `T-14` (Dual Kernel) | `T-15` | All 3 Pass |
|---|---|---|---|---|---|---|---|
| `anthropics/formal-math/vp-vnp` | `leanprover/lean4:v4.33.1` | `323` (`0` esc) | `5` | `True` | `True` | `True` | **`True`** |
| `openai/math (omega_F = 9/4 & SpectralFlatLaw)` | `leanprover/lean4:v4.34.1` | `13` (`0` esc) | `3` | `True` | `False` | `True` | **`False`** |
| `open-goat/pequalnp-proofs (note-1 & CircuitHelpers)` | `leanprover/lean4:v4.36.0` | `15` (`0` esc) | `0` | `True` | `False` | `True` | **`False`** |
| `Track S93 Pure-Init Companion (OmegaNineFourthsAndSpectrum.lean)` | `leanprover/lean4:v4.36.0` | `1` (`0` esc) | `0` | `True` | `False` | `True` | **`False`** |

*(Single-kernel honesty: Track S93 verifies `OmegaNineFourthsAndSpectrum.lean` via a single live `Lean 4.36.0` kernel + R12 static gate with zero independent `nanoda` kernel, so `T-14` and `All 3 Pass` are graded `False` identically to `openai/math` and `open-goat/pequalnp-proofs`.)*

---

## 5. Pillar 3 — Exact Law-5 Reconciliation: `SpectralFlatLaw` vs. `vp-vnp` `Rem D.3` & `Thm D.2`

1. **Unified Ambient `CAT(0)` Geometry:** Both OpenAI's `SpectralFlatLaw.lean` (`import OAI.Geometry.HyperbolicGroups.CATZero`, `BookCAT0.lean`) and Anthropic `vp-vnp` (`Thm C.1`) operate inside an ambient **Alexandrov/Bruhat–Tits `CAT(0)` spectral space `X`**.
2. **Euclidean Flats ($\kappa = 0$) Enforce Ratio `2` (Cannot Prove $\omega > 2$):** On any convex isometric Euclidean chart $e : C \hookrightarrow X$, `SpectralFlatLaw` forces $P(\Delta_S(q)) = W(S) \log_2 q$ (triangle half-perimeter $P/2$), giving ratio `P / (P/2) = 2 < 9/4` identically:

| Euclidean Chart | Sides | Perimeter $P$ | Mean Width $W = P/2$ | Ratio $P / W$ | Gram $\det G$ |
|---|---|---|---|---|---|
| Pythagorean (3,4,5) triangle | `['3', '4', '5']` | `12` | **`6`** | **`2`** | `144` (`> 0`) |
| Pythagorean (5,12,13) triangle | `['5', '12', '13']` | `30` | **`15`** | **`2`** | `3600` (`> 0`) |
| Equilateral (2,2,2) triangle | `['2', '2', '2']` | `6` | **`3`** | **`2`** | `12` (`> 0`) |

   For the planar `[0,3] x [0,4]` rectangle: perimeter `14`, normalized mean width **`7`** (`> 6` for the `(3,4,5)` triangle, interior point insertion delta `0`).
3. **Strict Non-Euclidean `CAT(0)` Obstructions ($\kappa < 0$) — Identical Negative-Gram Signature in BOTH Papers:**
   - **OpenAI's $\omega = 9/4$ Unit-Arm `CAT(0)` Tripod `{o, a, b, c}`:** Arm length `1`, tip distances `2` (perimeter `6`), shared-label rate **`8/3`** (strict defect `1/3` below Euclidean half-perimeter `3`) $\implies$ ratio **`9/4`**. Centered at `o`, its Gram matrix $G_{\text{tripod}} = \begin{pmatrix}1&-1&-1\\-1&1&-1\\-1&-1&1\end{pmatrix}$ has exact **`det G = -4 < 0`** and negative quadratic witness $v=(1,1,1) \implies v^\top G v =$ **`-3 < 0`**, while satisfying the Bruhat–Tits `CAT(0)` CN inequality with strict slack **`2 > 0`**!
   - **Anthropic `vp-vnp` `Rem D.3` 5-Point $\mathrm{Mat}_2(\mathbb{F}_2)$ Witness (`Track S75`):** `['0', 'E00', 'E01', 'E11', 'E00+E11']` has exact **`det G = -1/4 < 0`** and negative quadratic witness $u=(2,-1,2,-2) \implies u^\top G u =$ **`-1 < 0`** ($u^\top (2G) u = -2$).
4. **Law-5 Domain-Boundary & `Thm D.2` Interaction Verdict:** Zero contradiction! `SpectralFlatLaw` requires an isometric Euclidean chart, which is mathematically blocked on BOTH the tripod (`det G = -4`) and $\mathrm{Mat}_2(\mathbb{F}_2)$ (`det G = -1/4`). Conversely, OpenAI's `Theorem 1.2` (arbitrary-dimension Euclidean spectral flats over every field) directly supplies the Euclidean-flat price input required by `vp-vnp` `App. E` ($L(\mathrm{HC}_m) > m^{c(\log_2 m)^{1/3}}$), while leaving `Thm D.2`'s $\mathrm{Mat}_\mu(\mathbb{F}_2)$ contraction constant distinct.

---

## 6. Pillar 4 — `pequalnp.com/papers/note-1` (`10` Edge-Function Bounds) & `CircuitLowerBounds` Barriers

### 6.1 Complete Pinned `note-1` Inventory (`10/10` Live `MetaComplexity/L*.lean` SHAs Matched)

| ID | Lean File | Run | SHA-256 Prefix | Checked Statement |
|---|---|---|---|---|
| `L-meta-204` | `MetaComplexity/L204.lean` | `run-013633` | `1308ac8f2ec851e9...` | girth >= 7, hub dist >= 7: circuit size >= |A| + |E| + tau(G) - 1 |
| `L-meta-104` | `MetaComplexity/L104.lean` | `run-011343` | `75617a57212dbd89...` | forest with an edge: circuit size >= |E| + tau(G) - 1 |
| `L-meta-102` | `MetaComplexity/L102.lean` | `run-011301` | `45cd27aa7813352e...` | path P_n: exact circuit size n + floor(n/2) - 2 for n >= 2 |
| `L-meta-106` | `MetaComplexity/L106.lean` | `run-012105` | `71511d285c9435cd...` | cycle C_n (n >= 5): exact circuit size n + ceil(n/2) - 1 |
| `L-meta-105` | `MetaComplexity/L105.lean` | `run-011310` | `dbe2df52532b13cf...` | any graph with edge & vertex cover T: upper bound |E| + |T| - 1 |
| `L-meta-154` | `MetaComplexity/L154.lean` | `run-013182` | `f851f344c5486812...` | monotone (no NOT gate) upper bound |E| + |T| - 1 |
| `L-meta-115` | `MetaComplexity/L115.lean` | `run-012892` | `1459e770fd0425a4...` | girth >= 9, hub dist >= 7: monotone lower bound |E| + |T| - 1 |
| `L-meta-113` | `MetaComplexity/L113.lean` | `run-014387` | `64498f1b781d0e16...` | girth >= 9, hub dist >= 9: NOT elimination without size blow-up |
| `L-meta-112` | `MetaComplexity/L112.lean` | `run-011875` | `0a7cc50eb99404bd...` | 4-cycle C_4 obstruction: exact size 3 < |E| + tau - 1 = 5 (biclique K_{2,2}) |
| `L-meta-107` | `MetaComplexity/L107.lean` | `run-011915` | `259743e9dbcb05e0...` | no-pair-funnel reader lemma: (3,4) gate-elimination step |

- **Exact Path & Cycle Verification:** Paths $P_2..P_8$ match $|E|+\tau-1 = n + \lfloor n/2 \rfloor - 2 = (1, 2, 4, 5, 7, 8, 10)$; cycles $C_5..C_{10}$ match $|E|+\tau-1 = n + \lceil n/2 \rceil - 1 = (7, 8, 10, 11, 13, 14)$.
- **Exact $C_4$ Law-5 Biclique Collapse (`L-meta-112`):** Formula predicts `5` gates, yet exhaustive `16/16` truth-table verification proves $f_{C_4} = (x_0 \lor x_2) \land (x_1 \lor x_3)$ uses exactly **`3` gates** (exact **`2`-gate deficit**), driven by the `3/4`-coincident pair funnel at `(x_0, x_2)` that violates `L-meta-107`.

### 6.2 Five `CircuitLowerBounds/Helpers` Modules & Cross-Track Barrier Crosswalk (`S41` $\times$ `S44` $\times$ `S75` $\times$ `S93`)

| Helper Module | SHA-256 Prefix | Complexity Barrier Class |
|---|---|---|
| `Depth3.lean` | `ada3488f0a54069a...` | Depth-3 circuit layering (classical AC^0 / bounded-depth) |
| `Discriminator.lean` | `e4bdb389f5e76aaa...` | HMPST discriminator lemma (depth-2 TC^0 / threshold barrier) |
| `Lindsey.lean` | `252d50035309001a...` | Lindsey inner-product discrepancy lemma (communication / sign-rank) |
| `ParitySmol.lean` | `bbc98e27076684dd...` | Razborov-Smolensky F_3 polynomial approx (natural-proofs barrier) |
| `SatFive.lean` | `d1aeffbd3cc6138a...` | 4-bit clause-gadget encoding for fine-grained k-SAT reductions |

- **Verified Finite Witnesses:** `Lindsey` ($n=3$ Hadamard matrix: `64/64` orthogonality checks, `4x4` rectangle `64 <= 128`); `ParitySmol` (`central_sq`: $\binom{2k}{k}^2(2k+1) \le 16^k$ verified exact for `k = 0..8`, `k=8: 2,815,827,300 <= 4,294,967,296`); `SatFive` (`4`-bit clause block `len = 4n` for `n in {0,1,3,5}`).

| Track | Circuit / Proof Model | Evades Natural Proofs | Barrier Verdict |
|---|---|---|---|
| `S41` | Sign-flip det vs perm (Polya 0/512) | `False` | Fixed-dimension algebraic sign obstruction |
| `S44` | Static Lean proof-envelope pre-filter | `False` | Pre-filter now complemented by CheckLemma.lean kernel replay |
| `S75` | Division-free arithmetic & border circuits (VP != VNP) | `True` | Evades EGOW/FSV via CAT(0) Zorn prices + diag; breaks on Boolean (x^2-x) garbage |
| `S93/openai-math` | Formal arithmetic/rational circuits (omega_F = 9/4) | `True` | Breaks CW laser barrier 2.3078 via CAT(0) tripod + compression; formal algebraic model |
| `S93/pequalnp-proofs` | Fan-in-2 Boolean circuits (note-1 & AC^0/TC^0 helpers) | `False` | Linear gate-elim stops at C_4 biclique; helpers inside classical AC^0/TC^0 natural barriers |

---

## 7. Pure-`Init` `Lean 4.36.0` Formal Companion (`18/18` Universally Quantified `∀` Theorems)

Compiled live with `leanprover/lean4:v4.36.0` (`OmegaNineFourthsAndSpectrum.lean`, SHA-256 `59bb6bc1c798403db69092109575f7772fd8bdfdd0d8026f5d5910947c69a6ab`, `0` external imports, `0` warnings, `0` stderr bytes, scratch `lake build` clean). Axiom footprint: **`2`** literal `[]`, **`1`** `[propext]`, **`15`** `[propext, Quot.sound]`, **`0`** `Classical.choice`, **`0`** `sorryAx`, **`0`** `Lean.ofReduceBool`, **`0`** `Lean.trustCompiler`.

| # | Theorem (`OmegaNineFourthsAndSpectrum.*`) | Pillar | Quantification | Live Axioms | Statement |
|---|---|---|---|---|---|
| 1 | `omega_square_exact_nine_fourths` | Pillar 1 | `∀ s : Int (0 < s)` | `[propext, Quot.sound]` | Scaling-invariant square formula omega_F(s,s,s) = 9/4 |
| 2 | `omega_rectangular_flat_below_half` | Pillar 1 | `∀ x y z : Int` | `[propext, Quot.sound]` | Harmonic flat regime (x+y)z <= xy => penalty vanishes (alpha_F >= 1/2) |
| 3 | `omega_rectangular_strict_penalty_above_half` | Pillar 1 | `∀ x y z : Int` | `[propext, Quot.sound]` | Strict super-quadratic penalty for (x+y)z > xy (alpha_F = 1/2 sharp) |
| 4 | `omega_one_one_t_strict_midpoint_convex` | Pillar 1 | `∀ a b D : Int` | `[propext, Quot.sound]` | Strict midpoint Jensen convexity of omega_F(1,1,t) on (0,1] |
| 5 | `omega_symmetric_x_y_invariance` | Pillar 1 | `∀ x y z : Int` | `[propext]` | Exact swap invariance under exchanging larger weights (x, y) |
| 6 | `finite_size_gate_floor_scaling` | Pillar 2 | `∀ k : Int (2 <= k)` | `[propext, Quot.sound]` | Finite-size scaling separation k^8 < k^9 < k^12 (n^2 < n^(9/4) < n^3) |
| 7 | `cw_barrier_strictly_above_nine_fourths` | Pillar 2 | `∀ s : Int (0 < s)` | `[propext, Quot.sound]` | Strict chain 2 < 9/4 < 2.3078 (CW) < 2.371055 < 2.371339 < 2.8 < 3 |
| 8 | `division_free_vs_rational_cost_monotone` | Pillar 2 | `∀ lb c_rat c_df c_lin : Int` | `[propext, Quot.sound]` | Rational circuit lower bounds lift to division-free + linear costs |
| 9 | `trust_gate_t13_t14_t15_fail_closed` | Pillar 2 | `∀ t13 t14 t15 : Bool` | `[]` | Fail-closed conjunction soundness of T-13, T-14, T-15 trust scorecard |
| 10 | `euclidean_flat_triangle_ratio_two` | Pillar 3 | `∀ a b c : Int` | `[propext, Quot.sound]` | Cleared-denominator ceiling `(2*P = 2*P) ∧ (8*P < 9*P)` for `P = a + b + c > 0` (`rfl` first conjunct; second proves `2 < 9/4` without integer-division truncation; Lean docstring prose mentions `P/2`) |
| 11 | `cat0_tripod_ratio_nine_fourths` | Pillar 3 | `∀ r : Int (0 < r)` | `[propext, Quot.sound]` | CAT(0) arm-r tripod shared rate (8/3)r < 3r achieves exact ratio 9/4 |
| 12 | `cat0_tripod_non_euclidean_gram_negative` | Pillar 3 | `∀ r : Int (0 < r)` | `[propext, Quot.sound]` | Tripod Gram matrix has v^T G v = -3r^2 < 0 and det(G) = -4r^6 < 0 |
| 13 | `cat0_tripod_cn_inequality_strict_slack` | Pillar 3 | `∀ r : Int (0 < r)` | `[propext, Quot.sound]` | Bruhat-Tits CAT(0) CN inequality holds on tripod with strict slack 8r^2 |
| 14 | `vpvnp_rem_d3_scaled_gram_negative` | Pillar 3 | `∀ s : Int (0 < s)` | `[propext, Quot.sound]` | Scaled Anthropic Rem D.3 Mat_2(F_2) witness has u^T(2G)u = -2s^2 < 0 |
| 15 | `pequalnp_path_size_identity` | Pillar 4 | `∀ n : Int (2 <= n)` | `[propext, Quot.sound]` | pequalnp note-1 path edge-function size |E| + tau - 1 = n + floor(n/2) - 2 |
| 16 | `pequalnp_cycle_size_identity` | Pillar 4 | `∀ n : Int (5 <= n)` | `[propext, Quot.sound]` | pequalnp note-1 cycle size n + ceil(n/2) - 1 >= 7 > 3 (above C_4) |
| 17 | `pequalnp_c4_biclique_factorization_exact` | Pillar 4 | `∀ x0 x1 x2 x3 : Bool` | `[]` | Exact 3-gate C_4 biclique factorization & 3/4 pair-funnel coincidence |
| 18 | `pequalnp_satfive_block_length_and_lindsey_sq` | Pillar 4 | `∀ n : Nat, a b : Int` | `[propext, Quot.sound]` | SatFive 4-bit block scaling & Lindsey/Cauchy-Schwarz 2ab <= a^2 + b^2 |

---

## 8. Aletheia R1–R5 & R12 Verification Gates & Hardening Receipts

- **R1–R2 Exactness, Immutability & Zero-Float Enforcement:** `s93_omega94_vpvnp_oracle.py` and `verify_s93_omega94_vpvnp.py` contain `0` floating-point literals, `0` `float()` calls, `0` `.isdigit()` calls, `0` `random` imports, `0` bare `assert`s, immutable `MappingProxyType` global provenance/statement tables (zero cross-call aliasing), and `MAX_RATIONAL_STR_LEN = 256` blocking `>4300`-digit rational DoS strings before `int()`.
- **R3 Zone-B Filesystem, Field-Complete `SEC`/`FR0`/`FR1` Pinning, R12 Static Lean Hardening & Strict 5-Key Lean Env Allowlist:** Symlink/hardlink/FIFO/oversize/NUL/surrogate/cwd-symlink checks verified live; field-complete canonical payload pinning (`PAYLOAD_CANONICAL_PIN_MISMATCH`) closes all `11/11` `AUDIT-193` `F01, F04–F13` re-signed semantic/narrative forgeries plus `S93-FACT-01` across `SEC`, `FR0`, and `FR1`; zero-TOCTOU `lean --stdin` elaboration uses a strict `5`-key subprocess env allowlist (`SAFE_LEAN_ENV_KEYS = {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}`) on both `--version` and `--stdin` — blocking `LD_PRELOAD`, `LD_LIBRARY_PATH`, `DYLD_INSERT_LIBRARIES`, `LEAN_SRC_PATH`, `LEAN_PATH`, `LEAN_OPTS`, `LEAN_SYSROOT`, `ELAN_TOOLCHAIN`, `ELAN_HOME`, `LEAN_CC`, `LAKE_HOME`, and any unlisted ambient variable (verified live & mocked across `12` poisoned vars); R12 static Lean gate blocks `dbg_trace`/`dbgTrace*`/`dbgSleep`/`dbgStackTrace`/`dbg_sleep`/`dbg_stack_trace`/`panic!`/`unreachable!`/`panicWithPosWithDecl`/`set_option`/`warn.sorry`, `\bLean\s*\.` direct meta/kernel escapes, `@[...]` / `attribute [...]` escapes (`extern|implemented_by|export|init|builtin_init|term_elab|command_elab|tactic|macro|macro_rules|csimp`), `debug.terminalTacticsAsSorry`, `bv_decide`, `#guard`/`#guard_msgs`, end-anchored `decide (native := ...)`, struct-punning `config := { native }`, and `Char := '"'` quote-desync bypasses (verified via comment-only stripping + direct `"` ban), with `0` FP on clean controls (`decide (native := false)`, `decide (native := Bool.false)`, `decide (config := { native := false })`, `export Nat (succ)`, `attribute [simp] init`, `SmoothShell.partial`, and `private`/`protected theorem` discovery).
- **9-Env Isolated R4 + RO-Dir + Dual Lean-Less CI Parity:** `test_s93_omega94_vpvnp_r5.py` passes **`15/15 OK ×9`** (`-I -B`, `-I -O -B`, `-I -B -W error`, `PYTHONHASHSEED=42`, `umask 077`, `chmod 644`, RO-dir `0o500`, bare `env -i PATH=/usr/bin:/bin`, and `env -i PATH=/usr/bin:/bin HOME=/nonexistent`; `0` skipped tests!). `--standalone` and `--check --json` are byte-identical (`cmp -s ×4`) across all three R4 modes plus `PYTHONHASHSEED=42`.
- **Genuine `82/82` 4-Surface v2.1 Zero-Bypass Fuzzing (ZBF):** `CLI 25 + FR1 19 + FR0 19 + SEC 19 = 82/82` rejected cleanly (`0` bypasses, `0` crashes, `baseline_ok=True ×4`).
- **Live Mutation Testing (`aletheia-fast-mutate --guards require_ok --workers 1 --timeout 180 --max-mutants 0`):** **`237/237` (`100.0%`)** killed (`17/17` oracle + `220/220` verifier; `0` survivors, `0` timeouts, `truncated=False ×2`, `null_mutant=passed ×2`).
- **Null-Checked Whole-File DFS AST Boolean-Operator Mutation (boolean operator flip + sub-condition deletion):** **`284/284` (`100.0%`)** killed (`54/54` oracle + `230/230` verifier; `0` survivors, `0` timeouts, `null_ok=True ×2`).
- **Dual Static Audit Gate:** `aletheia audit-check --lean-audit --strict-ancestors --safety-scan --scripts verify_s93_omega94_vpvnp.py test_s93_omega94_vpvnp_r5.py` passes cleanly (`PASS ×2`, `0` Lean findings/notices, `0` safety findings, `0` leaks, `0` bare `assert`s, `0` CRLF).

---

## 9. Frozen Track File Inventory (`7` Companion Files + `REPORT.md`)

| File | Lines | Bytes | Mode | SHA-256 |
|---|---|---|---|---|
| `OmegaNineFourthsAndSpectrum.lean` | `377` | `20,536` | `0o644` | `59bb6bc1c798403db69092109575f7772fd8bdfdd0d8026f5d5910947c69a6ab` |
| `lakefile.toml` | `5` | `137` | `0o644` | `7d9e9aec20e4acd0d05e13716dcd001d5d4db1e12a792a44355ce6b2301e0511` |
| `lean-toolchain` | `1` | `25` | `0o644` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |
| `s93_omega94_vpvnp_certificate.json` | `1` | `21,800` | `0o600` | `d4627fc4ed7a8af368bb33dad470cbea0677161afc4ffc6736a41171f51eeaa9` |
| `s93_omega94_vpvnp_oracle.py` | `864` | `40,507` | `0o644` | `6a05b1148c9392fd8e7674940e82610705b6b9feb7458862391865174c000e05` |
| `test_s93_omega94_vpvnp_r5.py` | `1189` | `83,422` | `0o644` | `3ddf0768ae0c0d611770002c64eebe6218cd1bdd54ad5589f46d023408910089` |
| `verify_s93_omega94_vpvnp.py` | `1090` | `56,831` | `0o644` | `fce2e9a43ce4319cb57ad91e1f7c1ca4f2e5ff33c1a34d7ead79964b417e80a3` |

*(Note: `REPORT.md` is the 8th file in the track directory; its own SHA-256 is recorded externally in the completion receipt.)*
