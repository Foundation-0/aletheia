# Track S77 — Mellin-GLU Quadrature × `WSP-Gym` × `siliquant` Lattice Quantization & `DPI`/`BWI` Tomography

- **Track:** `Track S77` (Wave-4 Epistemic Lattice)
- **Date:** `2026-11-24`
- **Highest Novelty Class (Law 4):** **`N1`** (`0` `N2` claims — disciplined cross-track exact-$\mathbb{Q}$ synthesis, runnable collision proofs, and pure-`Init` Lean 4.36.0 formalization of prior art)
- **External Anchor Papers / Repos:**
  - `arXiv:2611.26450` (*"A CPU Inside an LLM"*)
  - `emeraldant/WSP-Gym` (pinned read-only `HEAD = d050d16dda5ed3243f5c59d115e931e44ef3da53`)
- **Cross-Track Bridges:** `siliquant` (`BlockH4`, `A_16`, `E_8`, `Track S72`/`S72b` stratified quad grouping), `Track S31` (`DPI`/`BWI` weight tomography), `Track S70` (`SwiGLU` hidden-channel permutation invariance), `CS-08` (compute-budget wall), `CS-15`/`CS-18` (random-edit baseline wall)

---

## 1. `OWN_TERMS_FIRST` — Reading Both Sources on Their Own Terms Before Collision

### 1.1 `arXiv:2611.26450` (*"A CPU Inside an LLM"*)
`arXiv:2611.26450` constructs explicit, hand-compiled, bit-exact multi-digit decimal arithmetic & control-flow circuits embedded inside real pretrained `Granite 4.2 3B` and `Qwen 3.5 4B` Transformers without degrading natural-language perplexity (`< 0.002` nats KL divergence). Its technical core rests on three load-bearing theorems:
1. **Theorem 3.2(1) — Single-Layer Bias-Free GLU Scale-Collapse Impossibility:** Under RMSNorm scale contraction $\lambda \to 0^+$, any single bias-free SwiGLU layer collapses quadratically ($\|F_1(\lambda u)\|_2 = O(\lambda^2)$), forcing weight-norm products to grow as $\Omega(\lambda_{\min}^{-2})$ to maintain unit threshold output.
2. **Theorem 3.2(2) — Mellin-GLU Log-Grid Quadrature:** A log-spaced bank of scaled gate/up weights $\alpha_k = e^{k\Delta}$ ($\Delta = 0.55$, $N_q \le 39$) cancels the unknown RMSNorm scale factor $\lambda$ via the Mellin integral $\frac{12}{\pi^2}\int_{-\infty}^\infty \mathrm{SiLU}(-e^u \tilde r)(-e^u \tilde v)\,du = x / r_0$ across a $>250\times$ RMSNorm dynamic swing with discretization error $\le 6.2551 \times 10^{-6}$.
3. **Theorem 3.4(2) — Axis-Aligned Width Extension, Differential Tied Readout & Quantization Fragility:** Widening the residual stream $d \to d + K$ with norm compensation $\gamma_{\mathrm{NL}} = \sqrt{d / (d + K)}$ (`Granite`: $d=2560, K=1140$, `1.33M` nnz = `0.0363%`; `Qwen`: $d=2560, K=2555$, `2.39M` nnz = `0.0568%`) and unit-offset RMSNorm differential pairs $(w_{p_m}, w_{n_m}) = (+254, -256)$ guarantees exact `0` off-trigger logit residual and `510 * E * delta` active push. Critically (Tables 3 & 6(b)), uniform `INT8`/`INT4` PTQ on $W_{\mathrm{circ}}$ **collapses** (`Err = 37.4 / 81.0`) because small $\alpha_k$ rungs underflow to zero; preserving $W_{\mathrm{circ}}$ in an FP32 `SparseSidecar` while quantizing $W_{\mathrm{NL}}$ to `INT4`/`INT8` recovers `5/5` G3–G7 and `100%` Qwen ALU (`0 / 11,134` OOD triggers). In its Impact Statement, the paper explicitly warns that dormant `0x0000` complement-pure grafts are invisible to black-box perplexity and require white-box structural weight auditing.

### 1.2 `emeraldant/WSP-Gym` (`HEAD = d050d16dda5ed3243f5c59d115e931e44ef3da53`)
`WSP-Gym` benchmarks white-box weight-space agents that inspect and repair planted faults (`sign_flip_in`, `sign_flip_out`, `swap_out_cols`, `weight_corrupt`, `scale_out_col`, `bias_shift`, `label_swap`) in `500` synthetic MLP networks (`data/test_id.jsonl`: `422` faulty + `78` clean) plus `500` planted backdoors (`data/test_audit.jsonl`) and real-LLM edits on `Qwen3.5-0.8B` (`MATH-500`, `N = 500`, and an `8`-layer `256`-problem dev slice). On its own terms, `WSP-Gym` is refreshingly transparent about two harsh empirical walls:
- On synthetic `test_id`, RL-trained `scale_rl` reaches `350/422` (`82.9384%`, `78/78` clean) in `19,035` tokens vs `untrained_thinking`'s `319/422` (`75.5924%`, `60/78` clean) in `5,298,074` tokens — a **`278.3333x`** token reduction — while `untrained_thinking` hits length cutoffs on `110/500` (`22.00%`) networks (`95/422 = 22.51%` of faulty).
- On real `Qwen3.5-0.8B` `MATH-500`, single-layer weight edits jump from `41/500` (`8.20%`) to `~37%–38%`, **but a completely random row swap (`random_L23`) ALREADY achieves `188/500` (`37.60%`)**, matching or beating every trained and untrained weight editor — and a zero-weight-edit `"Wait"` logit ban (`wait_ban`) achieves `194/500` (`38.80%`).

---

## 2. Law-2 Steelman Critique (Strongest Counter-Arguments Before Ruling)

1. **Steelman for `arXiv:2611.26450` vs. `siliquant`:** One could argue that because $W_{\mathrm{circ}}$ is only `0.0363%`–`0.0568%` of total parameters, simply keeping $W_{\mathrm{circ}}$ in an unquantized FP32 `SparseSidecar` already solves deployment cost without any lattice quantizer engineering. **Refinement / Resolution:** True for an explicitly known, author-grafted sidecar — **false** if a model is quantized blind by a downstream user running whole-layer `INT4`/`INT8` or unsorted `BlockH4` quantization (which silently destroys the circuit), AND our Pillar 2 exact-$\mathbb{Q}$ proof shows that **`Track S72`/`S72b` scale-stratified quad grouping (`4 × 4` sorted quads, intra-quad span `8x`) rescues `5/5` exact carry even in pure `INT8` (`0/16` rungs zeroed, `max_err = 0.162721 < 0.5`) without needing any FP32 sidecar!**
2. **Steelman for `WSP-Gym` `scale_rl` vs. `CS-08`:** Even if `untrained_thinking` wins on the finished subset, a `278.3333x` token reduction (`38.07` vs `10,596.15` tok/net) is a massive practical compute advantage under fixed latency budgets. **Refinement / Resolution:** Fully acknowledged! Our `CS-08` analysis does **not** deny the `278.3333x` efficiency gain; rather, it enforces **strict separation of accuracy capability vs. budget truncation** — proving via exact paired binomial McNemar that `74/77` (`96.10%`) of `scale_rl`'s exclusive wins arise strictly from `untrained_thinking`'s `95` length cutoffs, and conditioning on the `327` finished faulty networks produces a strict **sign flip** (`untrained_thinking = 319/327 = 97.5535%` vs `scale_rl = 276/327 = 84.4037%`, **`-13.1498 pp`**, exact two-sided $p < 10^{-10}$).
3. **Steelman for Single-Snapshot `DPI`/`BWI` Security Scanning:** Does single-snapshot `DPI`/`BWI` detect ALL weight-space backdoors? **Honest Negative Result:** **NO!** On `WSP-Gym`'s symmetry-hidden 1–3-edit faults (`sign_flip_in`, `swap_out_cols`, `bias_shift`), single-snapshot row-energy concentration $C_{\mathrm{row}}$ is **mathematically blind** (`1.0000` vs `1.0000` on our exact `4 × 4` model; `2.3736` clean vs `2.4777` `sign_flip_in` on `500` real `WSP-Gym` networks). Single-snapshot `DPI`/`BWI` strictly exposes **high-dynamic-range grafted circuits** (`arXiv:2611.26450` Mellin-GLU beacons: `span >= 1024x`, `C_row = 7.9675`, `offblock_nnz = 0`, `(+254, -256)` norm-pair overload `65,025x`), whereas small-edit symmetry-hidden faults strictly require **white-box diff-`DPI`** ($\Delta W = W_{\mathrm{faulty}} - W_{\mathrm{clean}}$, spiking `1.0000 -> 4.0000` in exact model and `2.4777 -> 7.7241` empirically on `sign_flip_in`) plus explicit bias/norm channel inspection!

---

## 3. Exact Pure-$\mathbb{Q}$ Verification Summary (All Derived Values Computed via `decimal.Decimal`)

### 3.1 Pillar 1 — Exact-$\mathbb{Q}$ Primitives (`arXiv:2611.26450` & `Track S70`)
- **Single-Layer GLU Quadratic Collapse (`Thm 3.2(1)`):** Exact rational kernel $\phi_{\mathrm{rat}}(s) = \frac{3s}{(1+s^2)(1+4s^2)}$ obeys $F_1(0) = 0$ and $0 < F_1(\lambda) \le 3\lambda^2$ across $\lambda \in \{1, 1/4, 1/16, 1/256\}$; hitting target `9/10` at $\lambda_{\min} = 1/256$ forces weight-norm product $\ge 98304/5 = \mathbf{19660.8}$.
- **Runnable 21-Rung Exact-$\mathbb{Q}$ Mellin-GLU Telescoping Quadrature (`k = -10..10`, `1,048,576x` weight span):** Exact rational telescoping residual `== 0` across all `5` RMSNorm scales $\lambda \in \{1/32, 1/4, 1, 4, 32\}$ (`1,024x` swing) for max decimal carry payload $C = 81$, with exact max error `347892434082 / 4402341479425` ($\mathbf{0.07902441} < 0.5$, `5/5` exact carry passes).
- **2-Layer Exact-$\mathbb{Q}$ Boolean Gate `(a AND b) OR (NOT c)`:** `24/24` (`100.00%`) exact across all `8` truth assignments $\times$ `3` RMSNorm scales $\lambda \in \{1/8, 1, 8\}$.
- **Axis-Aligned Width Extension & Differential Tied Readout (`Thm 3.4(2)`):**
  - `Granite 4.2 3B`: $\gamma_{\mathrm{NL}}^2 = 128/185$ ($\mathbf{0.69189189}$), sparse nnz $= 133/366000$ ($\mathbf{0.0363\%}$).
  - `Qwen 3.5 4B`: $\gamma_{\mathrm{NL}}^2 = 512/1023$ ($\mathbf{0.50048876}$), sparse nnz $= 239/420600$ ($\mathbf{0.0568\%}$).
  - Norm pair $(+254, -256)$: exact `0` off-trigger residual; exact `10710 = 510 * 7 * 3` active push.
- **`Track S70` SwiGLU Hidden-Channel Permutation Invariance:** `24/24` permutations of a 4-channel block achieve exact `max_abs_diff = 0/1`.

### 3.2 Pillar 2 — Collision #1: Mellin-GLU $\times$ `siliquant` Lattice Quantization Margin (`16`-Rung, `4 × 4` Quads, `C = 81`, `64x` Swing, Margin `< 0.5`)

| Quantization Regime | Zeroed Rungs | Carry Passes ($\|e\| < 0.5$) | Exact Max Abs Error (`Decimal`) | Verdict |
|---|---:|---:|---:|---|
| `exact_fp32_sparse_sidecar` | `0 / 16` | `5 / 5` | `0.079044` | **PASS** (baseline / FP32 sidecar) |
| `uniform_group_int4` (`qmax=7`) | **`12 / 16`** | **`0 / 5`** | **`80.996216`** | **FAIL** (matches Table 3 `Err = 81.0`) |
| `uniform_group_int8` (`qmax=127`) | **`8 / 16`** | **`0 / 5`** | **`79.772966`** | **FAIL** (small $\alpha_k$ underflow) |
| `unsorted_blockh4_int8` (`H_4/2` cross-scale) | **`4 / 16`** | **`1 / 5`** | **`18.010635`** | **FAIL** (`H_4` outlier bleed) |
| **`stratified_s72_quad_int8`** (`4 × 4` sorted quads, span `8x`) | **`0 / 16`** | **`5 / 5`** | **`0.162721`** | **PASS (RESCUED!)** |
| `stratified_s72_quad_int4` (`4 × 4` sorted quads, `qmax=7`) | `0 / 16` | `0 / 5` | `1.904832` | **FAIL** (fixes underflow; step $> 0.5/81$) |

### 3.3 Pillar 3 — Collision #2: `Track S31` `DPI`/`BWI` & `WSP-Gym` `CS-08`/`CS-15`/`CS-18`

#### A. Three-Regime `DPI`/`BWI` Boundary (Exact Runnable Matrices)
| Regime | $C_{\mathrm{row}}$ | `BWI` Span | Squared Overload | $L_0$ Density | Single-Snapshot Detectable? |
|---|---:|---:|---:|---:|---|
| `clean_dense` (`4 × 4`) | `1.0000` | `4.0000` | `2.1333` | `1.0000` | Baseline |
| `symmetry_hidden_sign_flip` (`4 × 4`) | `1.0000` | `4.0000` | `2.1333` | `1.0000` | **NO** (blind; matches `WSP-Gym` `2.3736` vs `2.4777`) |
| `whitebox_diff_dw` ($\Delta W$) | **`4.0000`** | `4.0000` | `2.1333` | `0.2500` | **YES (diff-`DPI`)** (matches `WSP-Gym` `7.7241` spike) |
| `mellin_glu_graft_single_snapshot` (`8 × 8`) | **`7.9675`** | **`1024.0000`** | **`19.9187`** | `0.3125` | **YES (single-snapshot)** (`offblock=0`, norm overload `65,025x`) |

#### B. `CS-08` Compute-Budget Wall (`WSP-Gym` `test_id`, `500` Networks = `422` Faulty + `78` Clean)
- **All `422` faulty networks:** `scale_rl = 350/422` (`82.9384%`, `78/78 = 100.00%` clean, `19,035` tokens) vs `untrained_thinking = 319/422` (`75.5924%`, `60/78 = 76.92%` clean, `5,298,074` tokens): diff **`+7.3460 pp`** (`+31/422`), exact two-sided McNemar $p = \mathbf{0.006591}$, exact token compression **`278.3333x`**.
- **Length cutoffs:** `110/500` (`22.00%`) total, `95/422` (`22.51%`) faulty; **`74/77` (`96.10%`)** of `scale_rl`'s exclusive wins occur strictly on cutoff networks.
- **Finished-Subset Exact Sign Flip (`327 = 422 - 95` finished faulty networks):** `untrained_thinking = 319/327` (**`97.5535%`**) vs `scale_rl = 276/327` (**`84.4037%`**), diff **`-13.1498 pp`** (`-43/327`, paired `b10 = 3` vs `b01 = 46`, exact two-sided binomial McNemar **$p < 10^{-10}$**, specifically $6.981 \times 10^{-11}$)!

#### C. `CS-15`/`CS-18` Random-Edit Baseline Wall (`WSP-Gym` `Qwen3.5-0.8B` `MATH-500`, `N = 500`)
- Baseline `random_L23` (random row swap) = **`188/500` (`37.60%`)** vs `unedited = 41/500` (`8.20%`, `b10 = 6, b01 = 153`, exact $p < 10^{-30}$).
- **Every weight editor is statistically indistinguishable from `random_L23` ($p \in [0.854630, 1.000000]$):**
  - `untrained_reason_L23`: `191/500` (`38.20%`, `delta = +3`, `b10 = 61, b01 = 58`, exact $p = \mathbf{0.854630}$)
  - `real_rl_L23`: `186/500` (`37.20%`, `delta = -2`, `b10 = 53, b01 = 55`, exact $p = \mathbf{0.923401}$)
  - `formula_rl_L23`: `187/500` (`37.40%`, `delta = -1`, `b10 = 54, b01 = 55`, exact $p = \mathbf{1.000000}$)
  - `n573_x2_published_edit`: `185/500` (`37.00%`, `delta = -3`, `b10 = 58, b01 = 61`, exact $p = \mathbf{0.854630}$)
- **Zero-weight-edit `wait_ban`:** `194/500` (**`38.80%`**, `delta = +6`, `b10 = 62, b01 = 56`, exact $p = \mathbf{0.645497}$), outperforming every weight-space editor without touching a single weight.
- **8-Layer `256`-Problem Dev Slice (`table_qwen_slice_summary.csv`):** `random = +10.25 pp` strictly dominates `untrained_reasoning (+7.71 pp)`, `formula_rl (+7.47 pp)`, `real_rl (+6.88 pp)`, and `scale_rl (+1.90 pp)`.

### 3.4 Pillar 4 — Pure-`Init` Lean 4.36.0 Formalization (`MellinGluQuantMargin.lean`)
- **Toolchain:** `leanprover/lean4:v4.36.0` (pure `Init`, `0` external imports, `0` warnings on both `lean` and clean-copy `lake build`).
- **Theorems (`18/18`):** `2` strictly axiom-free (`[]`: `dpi_row_concentration_iso_frobenius_gap`, `cs08_budget_wall_sign_flip_exact`), `16` strictly `[propext]` (`0` `sorryAx`, `0` `Classical.choice`, `0` `Quot.sound`, `0` `Lean.ofReduceBool`, `0` `Lean.trustCompiler`).
- **R9 11-Class Static Audit:** `0` findings, `0` notices (`aletheia-fix-lean-gates-v2` `e06992d` AND built-in verifier scanner).

---

## 4. Honest Law-4 Novelty Accounting (`N0` / `N1` Only — `0` `N2` Claims)

| Item | Class | Justification |
|---|---|---|
| `arXiv:2611.26450` Thms 3.2–3.4 & Tables 3/6(b) | `N0` | External prior art (reproduced & anchored cleanly) |
| `emeraldant/WSP-Gym` `test_id`, `test_audit`, `MATH-500` runs | `N0` | External empirical benchmark (7 core files SHA-256 pinned) |
| `Track S31` `DPI`/`BWI`, `Track S70` SwiGLU symmetry, `Track S72`/`S72b` stratified quads | `N0` | Prior expedition tracks referenced & unified |
| Pure-`Init` Lean 4.36.0 `MellinGluQuantMargin.lean` (`18` theorems, `⊆ {propext}`, R9 clean) | `N1` | New machine-checked constructive formalization |
| Exact-$\mathbb{Q}$ `16`-rung 4-quad Mellin-GLU $\times$ `siliquant` collision & stratified `INT8` rescue | `N1` | New quantitative cross-track proof & exact oracle |
| Exact-$\mathbb{Q}$ 3-regime `DPI`/`BWI` boundary + `CS-08` finished-subset sign flip & `CS-15`/`CS-18` McNemar unification | `N1` | New disciplined statistical & structural tomography synthesis |

---

## 5. Deliverable Manifest & Reproduction Commands

- `MellinGluQuantMargin.lean` (`lean-toolchain`, `lakefile.toml`) — Pure-`Init` Lean 4.36.0 formalization (`18` theorems, `sha256: 41d3c044bc08b82cd16c6a5a77109ff4eae122add5efb4e5870678081c91ba7b`)
- `s77_mellin_wsp_tomography.py` — Pure-$\mathbb{Z}/\mathbb{Q}$ stdlib oracle (`0` floats, `0` bare asserts, `0` RNG)
- `verify_s77_mellin_wsp.py` — Hardened Zone-B CLI & 4-surface (`CLI` / `FR1` / `FR0` / `SEC`) verifier (`--standalone --json`, `--write`, `--check`, `--verify-lean`) + R10 Lean 4 auditor
- `test_s77_mellin_wsp_r5.py` — Assertion-free R5 `unittest` suite (scratch `os.mkfifo` non-regular probes; `100.0%` `aletheia-fast-mutate` + `100.0%` whole-file DFS AST `BoolOp` + `82/82` 4-surface `zone_b_fuzzer`)
- `s77_mellin_wsp_certificate.json` — Canonical `0o600` zero-float LF-terminated JSON certificate (`certificate_sha256: fd571ef4b43020c80a3f8d3569a3e5b70a75d9b872dd9cad7fc2b4b50d7476c8`)
- `REPORT.md` — This report

```bash
python3 -I -B verify_s77_mellin_wsp.py --standalone --json | cmp - s77_mellin_wsp_certificate.json
python3 -I -B verify_s77_mellin_wsp.py --check s77_mellin_wsp_certificate.json --json
python3 -I -B verify_s77_mellin_wsp.py --verify-lean MellinGluQuantMargin.lean --json
python3 -I -B test_s77_mellin_wsp_r5.py -v
```
