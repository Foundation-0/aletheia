# Track S100: Multi-Tokenizer / Protocol / Non-English Density Engine & Deterministic 3-Node M1 Max (`64 GiB`) + `client-omarchy` Handoff Pack

- **Track ID:** `TRACK-S100-TOKENPAGE-ABIOS-SCRY-AND-M1MAX-HANDOFF`
- **Schema Version:** `aletheia.track_s100.tokenpage_abios_m1max_handoff.v1`
- **Novelty Classification (Law 4):** **`N1`** (`n2_claims = 0`; explicit `N0` credit to all upstream repositories and tracks below)
- **Compute Posture:** Strictly **CPU-only & offline** (`CUDA_VISIBLE_DEVICES="" HF_HUB_OFFLINE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`), **0** GPU touch, **0** GitHub pushes/writes, **0** raw dataset or weight copies inside `expedition/`.

---

## 1. Own-Terms Problem Statement & Scope (`OWN_TERMS_FIRST`)

Language-model agents suffer from **four coupled wire-and-representation inefficiencies** that prior studies have measured in isolation across separate repositories:

1. **Protocol & Operator BPE Fragmentation (`Moissanite-Labs/tokenpage#1`, `abios#38/#39/#51`, `aletheia calculus`):** Verbose Markdown/JSON burns swarm context tokens, yet naive Unicode operator glyphs (`⧄ ⧅ ⦷ ⟠ ⧇ ⦺ ⩩ ⫩`) fragment into `2–3` raw UTF-8 byte-fallback tokens under stock BPE tokenizers, erasing most of their byte-length advantage until dedicated protocol tokens are reserved.
2. **Non-English Vocabulary-Tax × Translation-Loss Compounding (`Track S92` × `Bayt al-Hikma`):** Classical scientific Arabic incurs a `1.99×–4.42×` BPE token tax relative to English, tempting practitioners to translate into English before reasoning — yet English translation simultaneously destroys `51.96%` of overall scientific edges and `91.76%–94.74%` of cross-discipline edges (`Track S92`), amplifying super-exponentially on higher-order $k$-simplices.
3. **Representation-vs-Readout Gauge Gap & Wire-Codec Non-Injectivity (`tokenpage#5/#13`, `abios#39/#51`):** Compact encodings pack high latent mutual information (`0.96 bits/tok`, `11.32–11.40 / 11.49` bits) into hidden states while zero-shot readout collapses (`0.558`/`0.542`, `19/24` position-`0,1` bias), and unguarded wire-list encoders (`abios#39` `wire_lists.py`) silently drop whitespace strings, corrupt scalar lists, or split bracketed strings across whitespace boundaries.
4. **Heterogeneous Multi-Machine Execution Seams (RTX 3080 `8 GiB` × MacBook M1 Max `64 GiB` × `client-omarchy` Edge):** Long-context looped models (`Inkling-2-Mini` `20 GB`), simultaneous `Bonsai 2.5 27B` (`5.93 GB`) vs `FP16` (`53.80 GB`) parity runs, live `siliconcordat/weft` E8 Part C (`Qwen3.5-4B`) + `weft-loom` `E11c` DAWE verification, and `exyber` + `nullmodem` cross-host KV transfer require **machine-checkable, SHA-256-pinned, zero-float preregistered `aletheia handoff` manifests** with fail-closed pass/kill gates.

### Explicit `N0` Prior-Art Ledger (Do Not Duplicate)

| Upstream Work (`N0`) | What Already Exists (Credited, Not Duplicated) | Track S100 Extension (`N1`) |
|---|---|---|
| `Moissanite-Labs/tokenpage` (`#1`, `#5`, `#13`) | `7`-tokenizer ABIOS waste audit (`#1`); `Qwen2.5-0.5B` hidden-state probes & `1.5B` QA (`#5`); prior unfloored KL sign-reversal & `112`-row hygiene catch (`#13`). | Exact pure-$\mathbb{Q}$ gauge-gap decomposition (`tokenpage#5/#13` × `abios#51`) + pure-`Init` Lean theorem (`Thm 5`). |
| `Moissanite-Labs/abios` (`#38`, `#39`, `#47`, `#51`) | Canonical `ABIOS/3` spec (`#38`), `wire_lists.py` (`#39`), state-transfer RFC (`#47`), `SYM-2P` spec-in-context `4–6/23 -> 18/23` (`#51`). | Live `Qwen2.5` vs `SmolLM2` 4-form audit on `review-fix-verify-merge.jsonl`, pure-stdlib reproduction & lossless single-token fix of all `3` `PR #39` `wire_lists.py` bugs (`Thm 6`). |
| `Moissanite-Labs/scry` (`#1`, `#2`, `#4`) | Toy collapse baseline (`#1`), prior hysteresis band & $PGL(2,\mathbb{Q})$ Möbius reduction (`#4`). | **Zero toy collapse duplication**; targets real multi-tokenizer/protocol & `weft-loom#46/#47` execution handoffs. |
| `Track S92` & `Foundation-0/bayt-al-hikma` | `12` pure-Arabic scientific treatises (`1.50M` Arabic tokens), `12` bilingual catalogs (`148` pairs), English edge-loss ladders. | Live offline `Qwen2.5` & `SmolLM2` tokenization of ALL `12` treatises & `148` pairs + exact **Vocabulary-Tax × Translation-Loss Compounding Theorem** (`Thms 1–3`). |
| `Track S31`, `S86`, `S89`, `S94` & `siliquant#97/#98` | `S31` `DPI` `token_embd` concentration (`75,968×`), `S94` Householder isometry & `Bonsai 2.5` 3-tier roofline, `siliquant#97` `[H_8, D] != 0` catch. | Reserved protocol-token surgery sweep (`K in {16,32,64,128}`), `S31` `DPI` row-norm safety bounds (`Thms 7–12`), and SHA-pinned 3-node `aletheia handoff` manifests (`Thms 13–18`). |

---

## 2. Pillar 1 — Live CPU Multi-Tokenizer & Cross-Language Density Audit

All measurements were captured strictly offline on CPU via Rust `tokenizers` against SHA-256-pinned local tokenizers (`Qwen2.5-0.5B`: `151,665` active / `151,936` padded vocab, SHA `c0382117...`; `SmolLM2-360M`: `49,152` vocab, SHA `9ca9acdd...`) and frozen into [`s100_tokenizer_anchor.json`](./s100_tokenizer_anchor.json) (`file_sha256 = 7a0e698b...`, `payload_sha256 = 94dee3fe...`).

### 2.1 `Moissanite-Labs/abios` `review-fix-verify-merge.jsonl` (`12` Packets) — 4 Lossless Forms

| Wire Rendering (100% Lossless) | UTF-8 Bytes | `Qwen2.5` Tokens | `SmolLM2` Tokens | Savings vs Markdown (`Qwen2.5` / `SmolLM2`) |
|---|---:|---:|---:|---:|
| Pretty JSON (2-space indent) | `6,244` | `2,694` | `2,799` | `-10.46%` / `-6.55%` (expansion) |
| Verbose Markdown Prose | `5,619` | `2,439` | `2,627` | baseline (`0.00%`) |
| `SYM-2P` Canonical JSONL (`cee1c4d8...`) | `4,531` | `1,766` | `1,956` | **`27.59%`** (`673/2439`) / **`25.54%`** |
| `ABIOS/3` Compact Payload Only | `3,050` | `1,336` | `1,443` | **`45.22%`** / **`45.07%`** |
| `ABIOS/3` Full (Payload + Explicit L-18 Setup `96`/`104` tok) | `3,282` | `1,432` | `1,547` | **`41.29%`** (`1007/2439`) / **`41.11%`** (`1080/2627`) |

- Against `SYM-2P` JSONL itself, `ABIOS/3` full (including explicit L-18 decode-sufficient setup) saves **`18.91%`** (`167/883`) on `Qwen2.5` and **`20.91%`** (`409/1956`) on `SmolLM2`, breaking even at **`N* = 3` packets** on both tokenizers.

### 2.2 `aletheia calculus` 8-Glyph Fragmentation & `5` Frozen Aletheia Certificates

- Every single one of the `8` Aletheia calculus glyphs (`⧄ ⧅ ⦷ ⟠ ⧇ ⦺ ⩩ ⫩`, `3` UTF-8 bytes each) fragments into **`2–3` BPE tokens** under `Qwen2.5` (total **`17` tok** = `17/8 = 2.125 tok/glyph`; `⩩` = `3` raw byte tokens) and **`3` raw UTF-8 byte tokens** EVERY time under `SmolLM2` (**`24` tok** = `3.000 tok/glyph`).
- On the 8-operator expression `A ⧄ B ⧅ C ⦷ D ⟠ E ⧇ F ⦺ G ⩩ H ⫩ I` (`49 B` vs `154 B` ASCII):
  - Raw Unicode glyphs cost `32` tok (`Qwen2.5`) / `33` tok (`SmolLM2`) vs `37` / `47` tok for ASCII (`68.2%` byte reduction yields only `13.5%` token reduction on `Qwen2.5`!).
  - Reserving `8` dedicated protocol tokens collapses the expression to **`17` tokens** on BOTH tokenizers (**`46.88%`** saving vs raw glyphs on `Qwen2.5`; **`48.48%`** on `SmolLM2`).
- Across the `5` frozen Aletheia certificates (`S31`, `S86`, `S89`, `S92`, `S94`; `114,394 B`), canonical JSON yields **`48,234`** `Qwen2.5` tokens (`2.3716 B/tok`) and **`55,485`** `SmolLM2` tokens (`2.0617 B/tok`).

### 2.3 Exact Pure-$\mathbb{Q}$ Vocabulary-Tax × Translation-Loss Compounding (`Track S92` Corpus)

- **12 Raw-Arabic Scientific Treatises (`14,843,023 B`, `1,581,301` words):**
  - `Qwen2.5`: **`3,389,784` tokens** (`2.1437 tok/w`, `4.3788 B/tok`).
  - `SmolLM2`: **`7,756,740` tokens** (`4.9053 tok/w`, `1.9136 B/tok`) — **`2.2883×`** (`+4,366,956` extra tokens; per-treatise span `2.0201×` on `biruni_masudi` to **`2.5474×`** on `nafis_tashrih`).
- **12 Bilingual Arabic-English Scientific Catalogs (`148` parallel pairs; `13,047 B` Ar / `5,613 B` En):**
  - `Qwen2.5`: `2,734` Ar vs `1,373` En -> **`1.9913×`** Arabic/English BPE token tax.
  - `SmolLM2`: `6,141` Ar vs `1,388` En -> **`4.4244×`** Arabic/English BPE token tax (`2.2219×` cross-tokenizer Arabic tax amplification at near-identical English counts!).
- **Exact Vocabulary-Tax × Translation-Loss Compounding Ladder (`E_en / E_ar = 1 / (tax * r^m)`):**

| Regime & Tokenizer | BPE Tax (`Ar/En`) | Simplex $k$ ($m$ edges) | `S92` Retention $r^m$ | English / Raw-Arabic Cost per Retained Simplex | Raw Arabic Strictly Cheaper? |
|---|---:|---:|---:|---:|:---:|
| Overall Catalog (`r = 319/664`) — `Qwen2.5` | `1.9913×` | `k=1` (`m=1`) | `0.480422` | **`1.0453×`** | **YES** |
| Overall Catalog (`r = 319/664`) — `SmolLM2` | `4.4244×` | `k=1` (`m=1`) | `0.480422` | `0.4705×` | No (BPE tax wins at `k=1`) |
| Overall Catalog (`r = 319/664`) — `Qwen2.5` | `1.9913×` | `k=2` (`m=3`) | `0.110884` | **`4.5290×`** | **YES** |
| Overall Catalog (`r = 319/664`) — `SmolLM2` | `4.4244×` | `k=2` (`m=3`) | `0.110884` | **`2.0384×`** | **YES** |
| Cross-Discipline (`r = 7/85`) — `Qwen2.5` | `1.9913×` | `k=1` (`m=1`) | `0.082353` | **`6.0981×`** | **YES** |
| Cross-Discipline (`r = 7/85`) — `SmolLM2` | `4.4244×` | `k=1` (`m=1`) | `0.082353` | **`2.7446×`** | **YES** |
| Cross-Discipline (`r = 7/85`) — `Qwen2.5` | `1.9913×` | `k=2` (`m=3`) | `0.000559` | **`899.1552×`** | **YES** |
| Cross-Discipline (`r = 7/85`) — `SmolLM2` | `4.4244×` | `k=2` (`m=3`) | `0.000559` | **`404.6812×`** | **YES** |

**Key Structural Takeaway:** Translating classical Arabic into English to avoid a `1.99×–4.42×` BPE penalty is mathematically self-defeating: on cross-discipline scientific edges, English already burns **`2.74×–6.10×`** MORE tokens per surviving edge at `k=1` and **`404×–899×`** MORE tokens per surviving triangle at `k=2`! The sole rational remedy is **keeping native Arabic and closing the BPE gap via vocabulary surgery (`Pillar 2`)**.

### 2.4 Gauge Gap (`tokenpage#5/#13` × `abios#51`) & `abios#39` `wire_lists.py` Codec Diagnosis

- **Gauge Gap:** `tokenpage#5`/`#13` recovers `11.32–11.40 / 11.49` latent bits (`98.52%`) on `glyph_g1` while `1.5B` zero-shot readout falls to `0.558` (`0.542` with legend; `19/24` pos-`0,1` collapse), leaving an exact **`0.4272`** (`490858/1149000`, i.e., `1132/1149 - 558/1000`) representation-vs-readout gauge gap (and confirming `+1.7670` bits unfloored KL calibration gain vs `-1.97` floored sign-flip artifact). `abios#51` demonstrates that spec-in-context cuts this gap sharply: `SYM-2P` accuracy jumps from `4–6/23` to **`18/23`** (`+12/23 = +0.5217`) and compile jumps **`0/2 -> 2/2`**.
- **`abios#39` (`3e251f0b92a8`) `wire_lists.py` Exact Defects & Lossless Fix:**
  1. `[' ']` -> encodes as `"[ ]"` -> `json.loads("[ ]")` returns `[]` (**silent length `1 -> 0` data loss**).
  2. `[1, 2]` -> falls back to `"[1,2]"` -> `decode_string_list` rejects non-str JSON list and splits on `;` -> returns `["1,2"]` (**silent cardinality `2 -> 1` corruption**).
  3. `['see [1] now']` -> falls back to unquoted `'["see [1] now"]'` containing spaces -> outer whitespace tokenizer splits into **`3` fragments** (`decode('["see') -> None` arity crash).
  - Our pure-stdlib `encode_fixed_wire_list` / `decode_fixed_wire_list` (`S[...]` for space/delimiter-free safe strings; space-free percent-escaped `J:...` typed JSON carrier otherwise) passes **`6/6`** single-token lossless round-trip bijections across all `3` adversarial probes and `3` clean controls.

---

## 3. Pillar 2 — Reserved Protocol-Token Surgery & `S31` `DPI` `token_embd` Safety Bound

Adding $K \in \{16, 32, 64, 128\}$ reserved protocol + Aletheia + Arabic-root tokens incurs negligible parameter overhead (exact `K * d` tied, `2 * K * d` untied) while amortizing L-18 setup in **`2–7` swarm turns**:

| Model (`d`, Base Params) | $K$ Added | Tied Params (`ppm`) | Untied Params (`ppm`) | Break-Even Turn $N^*$ | Net Savings @ 1,000 Turns |
|---|---:|---:|---:|---:|---:|
| `Qwen2.5-0.5B` (`896`, `494.0M`) | `16` | `14,336` (`29.02 ppm`) | `28,672` (`58.04 ppm`) | `7` | `14,904` tok |
| `Qwen2.5-0.5B` (`896`, `494.0M`) | `32` | `28,672` (`58.04 ppm`) | `57,344` (`116.07 ppm`) | `4` | `27,904` tok |
| `Qwen2.5-1.5B` (`1536`, `1.54B`) | `64` | `98,304` (`63.68 ppm`) | `196,608` (`127.36 ppm`) | `3` | `43,904` tok |
| `Qwen2.5-3B` (`2048`, `3.09B`) | `128` | `262,144` (`84.95 ppm`) | `524,288` (`169.90 ppm`) | `2` | `67,904` tok |
| `SmolLM2-360M` (`960`, `361.8M`) | `16` | `15,360` (`42.45 ppm`) | `30,720` (`84.90 ppm`) | `5` | `21,896` tok |
| `SmolLM2-360M` (`960`, `361.8M`) | `128` | `122,880` (`339.62 ppm`) | `245,760` (`679.23 ppm`) | `2` | **`95,896` tok** |

- **Exact `S31` `DPI` & `S94` Householder `token_embd` Safety Bound (`Thms 9–11`):**
  - Initializing all `K` appended rows to exact base mean squared row norm $M$ (`||e_new||^2 = M`) leaves the combined `(V + K)`-row `S31` `DPI` peak-to-mean concentration ratio identically **`1`** (zero embedding misfolding!).
  - Conversely, even ONE uncalibrated spike row with squared norm `16 * M` drives `DPI` concentration to **`811,008 / 50,693 = 15.9984×`** (`Qwen2.5`, `V+K = 152,064`) and **`15.9951×`** (`SmolLM2`, `V+K = 49,280`), approaching the exact `S31` two-row misfolding regime (`75,968×`).
  - Applying an orthogonal `S94` Householder reflection (`d = (3/5, 4/5, 0, 0)`) to any appended row (`u = (7, -1, 4, 2)`, `||u||^2 = 70`) is an exact isometry (`||H u||^2 = 70`, `delta = 0`) and exact involution (`H(H u) = u`), preserving `S31` `DPI` bounds identically across neuron-basis reflections.

---

## 4. Pillar 3 — Deterministic 3-Node `aletheia handoff` Pack (MacBook M1 Max `64 GiB` + `client-omarchy`)

Each handoff carries an independent canonical SHA-256 `manifest_sha256`, exact memory residency margins, zero-float acceptance predicates, and explicit fail-closed kill gates (all `4` single-gate Borromean ablations verified rejected!):

| Handoff ID | Target Node | Workload & Pinned Anchors | Exact Memory / Speedup Bound | Pass / Kill Gate (Zero-Float) | `manifest_sha256` (prefix) |
|---|---|---|---|---|---|
| **`M1-H1`** | `node_m1max_macos` (`64 GiB`) | `Inkling-2-Mini` (`20 GB`, config `a7a34960...`, `24 L`, `core 6..18 × 3`, `128/8` MoE) + `weft-loom#46/#47` windowed sampling | `30 GiB <= 64 GiB` (`34 GiB` headroom); `W=8` waves cuts `200` calls `514 s -> 64.25 s` (`8.0000×`); `(3/4)^3 = 27/64 < 1 < 125/64 = (5/4)^3` | Pass: `acc >= 11/20`, `format_breaks == 0`, `wall <= 120 s` (+ execution-phase drift-ratio control below) | `2f0e3f821281e77b` |
| **`M1-H2`** | `node_m1max_macos` (`64 GiB`) | `siliconcordat/weft` E8 Part C (`Qwen3.5-4B` live verification) + `weft-loom` `E11c` DAWE | `18 GiB <= 64 GiB` (`46 GiB` headroom); E8 `RMSNorm` sandwich `eta=1/10 -> [1/22, 1/20]`, `L=4` split `[1/82, 1/80]` (`4×` suppression) | Pass: pinned GGUF SHA, `new_task >= 4/5`, `iid_drop <= 1/10`, `ret >= 9/10`, `rollback == 0` | `90b270103ede14ae` |
| **`M1-H3`** | `node_m1max_macos` (`64 GiB`) | `Bonsai 2.5 27B` (`5.93 GB`) vs `FP16` (`53.80 GB`) dual-load parity (`+3.00 GB` OS budget = `62.73 GB`) + fixed `[H_8, D]` `siliquant#97` Gemma-3-12B | `62.73 GB <= 64 GB` (**`1.27 GB` headroom** vs `47.30 GB` RTX 3080 spill!); buggy `hHBG128` `2.9778×` blowup (`||[H_2, diag(8,1)]||_F^2 = 98`) | Pass: `0` OOM dual-load, `fixed_hhbg_kl <= 7/200`, `bonsai_tool >= 19/20` | `e919a1901e865fd7` |
| **`EDGE-H1`** | `node_client_omarchy` (`16 GiB` CPU) | `exyber` (`iroh`/BLAKE3) + `nullmodem` cross-host KV transfer (`Qwen2.5-1.5B` `28,672 B/tok`) | `1 Gbps` LAN `L* = 3` tok; at `4,096` tok transfer beats CPU prefill **`8.6732×`**; `10 Mbps` WAN (`22.9 ms/tok > 2 ms/tok`) NEVER wins | Pass: BLAKE3 exact, signed KV, `logit_diff <= 1/10000`, `speedup >= 2` | `a396d54b5c26923a` |

- **Preregistered Execution-Phase Control Addendum for `M1-H1` (execution-phase review):** The certificate's `ρ^3 = 27/64` contraction bound governs propagation of an *initial* perturbation under ideal arithmetic, whereas fresh per-pass quantization noise accumulates as `1 + ρ + ρ^2`. Before claiming `3×` looped adapter leverage on live Apple Silicon runs, `M1-H1` execution MUST additionally measure per-pass relative-$L_2$ drift $\Delta_i = \|h_i - h_i^{\text{unlooped\_FP}}\|_2 / \|h_i\|_2$ against a matched unique-layer FP reference and a matched single-pass NVFP4 control $\Delta_{1,\text{control}}$, enforcing the falsifiable drift-ratio kill gate **`Δ_3 / Δ_1_control <= 2` AND `Δ_3 <= 5e-2`** (kill `M1-H1` if loop recurrence dominates fresh quantization noise).

---

## 5. Pillar 4 — Pure-`Init` `Lean 4.36.0` Companion & Strongest Steelman Critique (Law 2b)

- **[`TokenpageAbiosHandoff.lean`](./TokenpageAbiosHandoff.lean)** (`37,721 B`, SHA `f2300ddf...`): **`18/18` universally quantified (`∀`) theorems**, `0` external imports, `0` warnings, **`1 []` + `17 [propext]`** (`0` `Classical.choice`, `0` `Quot.sound`, `0` `sorryAx`), verified via both `lean --stdin` and clean scratch `lake build` (`4 jobs`).
- **Strongest Steelman Critique & Explicit Falsification Boundaries (Law 2b):**
  1. **Semantic-Loss Independence Approximation:** Our higher-order simplex compounding `(r/d)^m` models independent edge retention (inherited from `Track S92`). If translated terms preserve correlated semantic clusters rather than independent edges, empirical $k$-simplex survival will exceed `(r/d)^m` — falsifiable by measuring actual $k$-clique survival directly on full translated classical Arabic treatises (not just 148 bilingual catalog pairs).
  2. **Vocab-Surgery Per-Turn Savings Are Distribution-Dependent:** Our `delta_tok_per_turn` (`15–96` tok/turn) is grounded on `review-fix-verify-merge.jsonl`, `aletheia calculus` expressions, and `Track S92` classical Arabic. Workloads dominated by novel free-form English prose with rare protocol tokens will achieve smaller per-turn savings (increasing $N^*$) and require re-measuring break-even empirically on target logs.
  3. **Handoff Manifests Are Preregistered Specs, Not Live M1 Max / `client-omarchy` Execution Receipts:** Track S100 executes strictly CPU-only on the local workstation and certifies the *exact deterministic mathematical bounds and pass/kill gates* for `M1-H1..EDGE-H1`; live Apple Silicon Metal / `exyber` execution measurements remain pending remote node runs and must fail closed if any gate triggers.
  4. **Untested Readout Alignment Under Fine-Tuning:** Reserving protocol tokens removes BPE fragmentation and preserves `S31` `DPI` norms, but newly initialized rows still require brief LoRA/spec-in-context alignment (`abios#51`) to close `tokenpage#5`'s readout gauge gap.

---

## 6. Verification Artifacts, R2 Hardening, & Local File Manifest (`10` Files)

- [`s100_live_tokenizer_capture.py`](./s100_live_tokenizer_capture.py) — Offline CPU Rust-`tokenizers` capture script producing [`s100_tokenizer_anchor.json`](./s100_tokenizer_anchor.json) (`0o644`, `18,642 B`).
- [`s100_tokenpage_handoff_oracle.py`](./s100_tokenpage_handoff_oracle.py) — 100% pure-stdlib exact-$\mathbb{Z}/\mathbb{Q}$ oracle.
- [`verify_s100_tokenpage_handoff.py`](./verify_s100_tokenpage_handoff.py) — Field-complete Zone-B verifier (`574/574` single-leaf coverage on `SEC`/`FR0`/`FR1`, pre-`int()` `MAX_INT_DIGITS` rational cap blocking `>4300`-digit DoS), read-only pin auditor, and R12 static + scrubbed-env (`LEAN_*`/`ELAN_*`/`LAKE_*`/`LD_*`) live Lean 4.36.0 gate.
- [`test_s100_tokenpage_handoff_r5.py`](./test_s100_tokenpage_handoff_r5.py) — Assertion-free, `0`-skip R5 test suite across isolated `-I`, bare `env -i`, `HOME=/nonexistent`, and live `LEAN_PATH` `Init.olean` hijack immunity.
- [`s100_tokenpage_handoff_certificate.json`](./s100_tokenpage_handoff_certificate.json) — Canonical `0o644` certificate (`21,363 B`, `certificate_sha256 = 6eb1eee9...`, `payload_sha256 = 4d1e959a...`).
- [`TokenpageAbiosHandoff.lean`](./TokenpageAbiosHandoff.lean), [`lakefile.toml`](./lakefile.toml), [`lean-toolchain`](./lean-toolchain) — Pure-`Init` Lean `4.36.0` companion (`18/18` universal `∀` theorems).

| File | Lines | Bytes | Mode | Exact SHA-256 (`R2` Freeze) | Lock Status |
|---|---:|---:|:---:|---|---|
| `TokenpageAbiosHandoff.lean` | `708` | `37,721` | `0o644` | `f2300ddf230a3792f59532574dfe6f96aed34c2cd4658b1d02b2fb6fffd9699e` | Core frozen |
| `lakefile.toml` | `6` | `137` | `0o644` | `9cecaa0a27cd307e9f2f3499741cecd7bc0f60f73d75be04428f1868d5c875db` | Core frozen |
| `lean-toolchain` | `1` | `25` | `0o644` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` | Core frozen |
| `s100_live_tokenizer_capture.py` | `620` | `28,304` | `0o644` | `e4d2d5d703d5ab970021e89647180fc17cd636573bbce2629be4955ae3dcef1c` | Core frozen |
| `s100_tokenizer_anchor.json` | `1` | `18,642` | `0o644` | `7a0e698bd976420299c14233af56087b4486e3c90443e0ce63104888ac85b55a` | Core frozen |
| `s100_tokenpage_handoff_oracle.py` | `1,006` | `46,485` | `0o644` | `803b5d23e8071b12386d845ba8d9c1860e8cf51ae0545a439cd33bad4a4ebec2` | Core frozen |
| `s100_tokenpage_handoff_certificate.json` | `1` | `21,363` | `0o644` | `0c478d77f191491f18f06968a9563ef117c765d982c6abc6e03d27c2ef75dd4d` | Core frozen |
| `verify_s100_tokenpage_handoff.py` | `1,662` | `75,387` | `0o644` | `c5344f8ad3f57a9da731c1ec4edb70ad88e7072a31de91a8df88c746c278265c` | R2 Hardened |
| `test_s100_tokenpage_handoff_r5.py` | `1,044` | `62,130` | `0o644` | `f8f1741899f6ef819be091f2a46da58f64e4db803faec8f0721e60f2ce5cde91` | R2 Hardened |
| `REPORT.md` | — | — | `0o644` | *(this file)* | R2 Updated |
