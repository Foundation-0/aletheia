# Weight-Space Misfolding `DPI`/`BWI` & Aletheia v2.2 Governance Oracles (`CS-15..CS-19`)

- **Track ID:** `TRACK-S31-ALETHEIA-V22-SOCIETY-MISFOLDING-TOMOGRAPHY`
- **Oracle Class:** Mixed — pure Python 3 stdlib `exact` $\mathbb{Z}/\mathbb{Q}$ (`fractions.Fraction`) arithmetic, `definitional/fixture` protocol checks, and `anchor` figures cited from external papers (see Section 1.1; zero IEEE-754 floats, zero bare `assert`s, zero RNG on verification paths).
- **Novelty Rating (Gate 9 Default):** **`N0`** (no full-text prior-art audit record ships in this PR; underlying mechanisms — Hadamard incoherence, `pass@k`/`pass^k`, TOST equivalence, Herfindahl–Hirschman index, Schatten ratios, rank-1 directional edits, and matched-gain forgetting — are established prior work).
- **Verification Scope:** Self-consistent, deterministic, and reproducible in-PR via `--standalone --json`, `--check` (full pure-$\mathbb{Q}$ replay + schema-safe secondary checks + constant-time canonical byte comparison), and `test_aletheia_v22_misfolding_r5.py`.
- **Certificate Digests:**
  - `file_sha256`: `f4f7f8abff0c7eae0d5678016c1041ab34870ef2de57a2f83e4cbb9a529f8a9b`
  - `payload_sha256`: `8c815db0050d9af05c0837db114e6cfe0f029b1612f5c1406361f5523f241545`
  - `certificate_sha256`: `2fc5d382b44cea1e5d695c60a9c0bb518b340b78920df09d16455a7d8bb265fd`

---

## 1. Executive Summary & Oracle-Class Accounting

This evidence package implements standalone, zero-float pure-$\mathbb{Z}/\mathbb{Q}$ arithmetic checks and executable governance fixtures supporting the Aletheia v2.2 proposal in `#27` (engaging Ahmad et al., *A Society of AI Scientists*, `2611.society-ai-scientists`, and von Csefalvay et al., *Weight space misfolding*, `2611.weight-space-misfolding`).

### 1.1 Claim-by-Claim Oracle-Class & Scope Table

| Claim / Quantity | Oracle Class | Scope & Assumptions |
| :--- | :--- | :--- |
| Empirical paper figures (`68%` diagnosis-only, `29.7% -> 12.2%`, `2.64x`, `88%` vs `30%`, `+16.2 pp`, `290/300`, `68%` null-overstatement, `83–94%` / `86%` KV persistence, `95.4% -> 80.0%` CoT drop, `-5` rank-1 reversal; `3,066` & `2,266` param edits, `12/12` controls, `1/22` defect rate) | **`anchor`** *(unverified externally in this PR)* | Cited from `2611.society-ai-scientists` and `2611.weight-space-misfolding`; source papers and live models are not executed in this PR. |
| `64×16` iso-Frobenius `DPI` separation (`32x`), `S_4` Schatten ratio (`1` vs `1/4`), `pass@k + pass^k == 1`, `k*(1/22) = 15`, `k*(1/100) = 69`, `k*(1/1000) = 693`, Sylvester $H_8^2 = 8I_8$, `1/8` spike coherence drop, `256x` / `32768/383` 128-weight group scale inflation, per-row SHA-256 manifest detection, TOST interval inequalities, HHI & linear interpolation arithmetic | **`exact`** | Pure-$\mathbb{Z}/\mathbb{Q}$ computations reproducible deterministically from the shipped oracle. |
| `Qwen2.5-1.5B` `token_embd` concentration `>= 75,968` | **`exact` (conditional)** | Holds **under the 2-row confinement assumption** (`151,936 / 2 = 75,968`); if `2,266` changed entries are distributed across `2,266` distinct rows, the pigeonhole lower bound drops to `151,936 / 2,266 ≈ 67.05`. |
| `survival_fraction = 1` for unquantized `token_embd` | **`definitional / fixture`** | Holds by construction of the modeled block-only quantizer $Q_{\mathrm{blk}}(W_{\mathrm{embd}}, W_{\mathrm{blk}}) = (W_{\mathrm{embd}}, Q(W_{\mathrm{blk}}))$, which leaves `W_embd` untouched regardless of `W_blk`. |
| `66/25 = 2.64x` LoRA-vs-Full-FT sign-flip (`F_full(3/10) = 5/88`) | **`definitional / fixture`** | Illustrative rational fixture curve hand-constructed to reproduce the `2.64x` sign-flip structure; `5/88` is a synthetic fixture value, not measured from primary-paper raw logs. |
| `300/300` `UNDETERMINABLE` abstention check (`SYN-MIS-000..299`) | **`definitional / fixture`** | Synthetic protocol test whose `300` mismatched `(query_topic, abstract_topic)` fixtures never match by construction, exercising abstention wiring. |
| `CS-19` `scan_ast_answer_key_leaks` (`0` FP on benign fixtures) | **`fixture-scoped`** | Direct-store syntactic AST check scoped strictly to the tested fixtures (see Section 5 for known syntactic blind spots). |

---

## 2. Pillar 1 — Deep Patch Inspection (`DPI`) & Rank-1 Reversal Checks

### 2.1 Iso-Frobenius Blindness & Row-Concentration Separation (`exact`)

For any nonzero weight-matrix patch $\Delta W = W_1 - W_0 \in \mathbb{Q}^{R \times C}$, define:
$$\mathcal{C}_{\mathrm{row}}(\Delta W) := \frac{R \cdot \max_{r} \|\Delta W_{r,:}\|_2^2}{\|\Delta W\|_F^2} \in [1, R], \qquad \rho_{\mathrm{nnz}}(\Delta W) := \frac{\mathrm{nnz}(\Delta W)}{RC} \in (0, 1].$$

Over $\mathbb{Q}^{64 \times 16}$, the oracle constructs exact rational patches with identical global Frobenius energy ($\|\Delta W_{\mathrm{mis}}\|_F^2 - \|\Delta W_{\mathrm{quant}}\|_F^2 \equiv 0$, hence identical global `W-err dB`):

| Patch ($64 \times 16$) | Construction | $\|\Delta W\|_F^2$ | $\max_r \|\Delta W_{r,:}\|_2^2$ | $\mathcal{C}_{\mathrm{row}}$ | $\rho_{\mathrm{nnz}}$ |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Diffuse quantization fixture** $\Delta W_{\mathrm{quant}}$ | $(\Delta W)_{r,c} = (-1)^{r+c} \cdot \frac{1}{4}$ | `64` | `1` | **`1`** | **`1`** |
| **2-row localized patch** $\Delta W_{\mathrm{mis}}$ | Rows `{7, 42}`, Pythagorean pairs `(6/5, 8/5)` ($\frac{36+64}{25}=4$) | `64` | `32` | **`32`** | **`1/32`** |
| **Single-row saturation fixture** $\Delta W_{\mathrm{1row}}$ | Row `7`, all 16 entries `2` | `64` | `64` | **`64`** | **`1/64`** |

- **Exact Separation Factor:** `32x` on $64 \times 16$ (`frobenius_energy_residual = 0`).
- **Conditional `Qwen2.5-1.5B` `token_embd` (`151,936 × 1,536 = 233,373,696` params) Scaling (`anchor` counts, `exact` arithmetic under stated row-confinement assumptions):**
  - `3,066`-param edit confined to `2` rows: exact support density `511/38895616`, pigeonhole minimum concentration $\mathcal{C}_{\mathrm{row}} \ge 151{,}936 / 2 = \mathbf{75{,}968}$ (vs `1` for uniform diffuse quantization).
  - `2,266`-param edit: exact support density `1133/116686848`. **Under the 2-row confinement assumption**, an even split (`1,133 + 1,133`) achieves the 2-row pigeonhole lower bound $\mathcal{C}_{\mathrm{row}} = 151{,}936 / 2 = \mathbf{75{,}968}$ and a 1-full-row-saturated split (`1,536 + 730`) with uniform entry amplitude gives $\mathcal{C}_{\mathrm{row}} = 151{,}936 \cdot \frac{1{,}536}{2{,}266} = \frac{116{,}686{,}848}{1{,}133}$ ($> 102{,}989\times$). Without 2-row confinement — e.g., if `2,266` changed entries sit in `2,266` distinct rows — the pigeonhole lower bound drops to $151{,}936 / 2{,}266 \approx \mathbf{67.05}$.

### 2.2 Rank-1 Spectral Dominance & Direction Reversal Check (`exact`)

Using the pure-$\mathbb{Q}$ Schatten ratio $S_4(\Delta W) := \frac{\operatorname{tr}((\Delta W^\top \Delta W)^2)}{(\operatorname{tr}(\Delta W^\top \Delta W))^2}$ ($S_4 \equiv 1 \iff \operatorname{rank}(\Delta W) = 1$; isotropic rank-$r$ gives $S_4 \equiv 1/r$) and directional projection ratio $\gamma_u := \frac{u^\top W_1 v}{u^\top W_0 v}$:
- **Isotropic rank-4 control ($H_4$):** $S_4 = \mathbf{1/4}$ (`is_exact_rank_1 = False`).
- **Orthogonal abliteration fixture:** $S_4 = \mathbf{1}$, $\gamma_u = \mathbf{0}$ (`regime = "orthogonal_abliteration"`).
- **5× Mechanism reversal fixture (modeled on `2611.society-ai-scientists` §4.3 `anchor`):** $S_4 = \mathbf{1}$, $\gamma_u = \mathbf{-5}$ (`baseline_projection = 5`, `edited_projection = -25`, `regime = "mechanism_reversal"`).

---

## 3. Pillar 2 — Exact-$\mathbb{Q}$ `pass@k` vs. `pass^k` Risk Asymmetry & Bellwether Fixtures

### 3.1 Rational Crossing Thresholds (`exact`, $k^*(1/22) = 15$)

Over exact `Fraction` with conservation identity $P_{\mathrm{att}}(p,k) + P_{\mathrm{def}}(p,k) - 1 \equiv 0$ across $p \in \{1/22, 1/100, 1/1000\}$ and $k \in \{1, 10, 22, 50, 100\}$:

| Defect Rate $p$ | Exact Threshold $k^*(p)$ (`pass@k* > 1/2`) | `k=1` (`bps`) | `k=10` (`bps`) | `k=22` (`bps`) | `k=50` (`bps`) | `k=100` (`bps`) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`1/22`** | **`15`** | `454` | `3,719` | `6,406` | `9,023` | **`9,904`** (`> 99%`) |
| **`1/100`** | **`69`** | `100` | `956` | `1,983` | `3,949` | `6,339` |
| **`1/1000`** | **`693`** | `10` | `99` | `217` | `487` | `952` |

Evaluating $(21/22)^k$ over $\mathbb{Q}$ gives minimal threshold **`k*(1/22) = 15`**:
- At $k = 14$: $P_{\mathrm{att}}(1/22, 14) = \frac{2977901340906311863}{6221821273427820544} < \frac{1}{2}$.
- At $k = 15$: $P_{\mathrm{att}}(1/22, 15) = \frac{68757749432460369667}{136880068015412051968} > \frac{1}{2} > \frac{68122318582951682301}{136880068015412051968} = P_{\mathrm{def}}(1/22, 15)$.
- At $k = 16$: $P_{\mathrm{att}}(1/22, 16) = \frac{1580792806097079814975}{3011361496339065143296} > \frac{1}{2}$.

### 3.2 Completeness & Relational-Closure Bellwether Fixtures (`definitional / fixture`)

1. **Multiset Cardinality & Bijection Check (`Brindle Supply` fixture):**
   - *Omission witness:* Dropping `"Brindle Supply"` passes naive positive-existence (`naive_positive_existence_pass = True`) while failing cardinality & bijection (`omission_detected = True`, `missing_items = ["Brindle Supply"]`, `exact_recall = 3/4`).
   - *Duplicate substitution witness:* Replacing `"Brindle Supply"` with duplicate `"Acme Hardware"` preserves `len == 4` (`cardinality_conserved = True`) and positive-existence while failing exact multiset bijection (`missing = ["Brindle Supply"]`, `extra = ["Acme Hardware"]`).
   - *Clean control:* Passes `bijection_exact = True`, `exact_recall = 1`.
2. **Relational-Closure Consistency Fixture (`"Buenos Aires, Australia"`):**
   - Both entities exist in the toy KB and `("Canberra", "Australia")` passes capital probing, while `kb["Buenos Aires"] == "Argentina" != "Australia"` flags `relational_mismatch` (`consistent = False`); the clean control passes `consistent = True`.

---

## 4. Pillar 3 — Hadamard $H_8$ Spreading, `BWI` Scale Alarm & Unquantized `token_embd` Bypass Model

1. **Sylvester Hadamard $H_8 \in \{\pm 1\}^{8 \times 8}$ (`exact`):** Verified `symmetric = True` and $H_8^2 \equiv 8 I_8$ over $\mathbb{Z}$.
2. **Spike $H_8$-Spreading Identity (`exact`):** For $\Delta w = 15 e_0 \in \mathbb{Q}^8$, exact $\ell_\infty^2 / \ell_2^2$ coherence drops from **`1`** to **`1/8`** identically (`coherence_ratio_drop = 1/8`).
3. **128-Weight Group MLP Spike `BWI` Scale-Inflation Check (`exact`):** Injecting $\Delta w = 15 e_0$ into a uniform $\pm 1$ 128-weight group inflates squared group scale $\|w\|_\infty^2$ by **`256x`** (`1 -> 256`) and raises squared peak-to-mean overload ratio from `1` to `32768/383` ($\approx 85.56 > 25$). On block 0 (`8` weights), $H_8$ preserves exact energy ($2104 = 8 \cdot 263$) while reducing peak coherence from `256/263` to `529/2104`.
4. **Unquantized `token_embd.weight` Bypass Model & Per-Row SHA-256 Lock (`definitional / fixture` + `exact` hashing):** Under a block-only quantization map $Q_{\mathrm{blk}}(W_{\mathrm{embd}}, W_{\mathrm{blk}}) = (W_{\mathrm{embd}}, Q(W_{\mathrm{blk}}))$, any embedding patch $\Delta W_{\mathrm{embd}}$ survives unchanged **by construction of $Q_{\mathrm{blk}}$** (`survival_fraction = post_quant_embd_energy_sq / dw_embd_energy_sq = (21/500) / (21/500) = 1`, `block_matrices_unchanged = True`; altering block weights does not affect `W_embd`). Independently, `token_embd_row_hashes_exact` computes per-row SHA-256 digests (`per_row_sha256_base`, `per_row_sha256_patched`) and manifest digests (`base_manifest_sha256 != patched_manifest_sha256`), isolating the modified row (`changed_rows_detected = [2]`, `unchanged_rows_count = 3`).

---

## 5. Pillar 4 — Executable Aletheia v2.2 Governance Fixtures (`CS-15..CS-19`)

- **`CS-15` Constructive Generalization & Scope Gate (`definitional / fixture`):** Enforces constructive fixes, strongest-baseline comparison, and cross-family scope (`>= 2` families or explicit single-family scoping); passes compliant controls and flags diagnosis-only unscoped failures.
- **`CS-16` Matched-Gain Pareto Comparator (`exact` interpolation over `definitional / fixture` curves):** Exact rational piecewise-linear interpolation on `(G, F)` curves reproduces the `anchor` Korean vocab-freeze confound (`297/1000` vs `61/500`, overstatement `7/40 = 17.5 pp`) and an **illustrative synthetic fixture** for the `66/25 = 2.64x` LoRA-vs-Full-FT sign-flip (`F_lora_end = 3/20 < 1/4 = F_full_end` unmatched; at matched gain `3/10`, hand-constructed fixture value `F_full(3/10) = 5/88` gives `F_lora(3/10) = 3/20 = (66/25) * (5/88) > F_full(3/10)`).
- **`CS-17` Herding & Sunk-Cost Escalation Detector (`exact` HHI over `anchor`/`fixture` inputs):** Flags score-visible herding (`22/25 = 88%`, `HHI = 487/625`) vs coordinate-only control (`3/10 = 30%`, `HHI = 13/50`), and rejects `+16.2 pp = 81/500` escalation (`119/500 -> 2/5`) against zero-shift preregistered allocation.
- **`CS-18` Mandatory 4-State Abstention & Rational TOST Gate (`definitional / fixture` + `exact` interval checks):** Runs a **synthetic `300`-case protocol test** over `300` mismatched `(record_id, query_topic, abstract_topic)` fixture records (`SYN-MIS-000..299`, mismatched by construction), returning `300/300` `"UNDETERMINABLE"` with zero forced `"no"` outputs; accepts `[-9/100, 9/100] subset (-1/10, 1/10)` as `"EQUIVALENT_NULL"`, and blocks `[-3/10, 2/10]` (plus exact boundaries `±1/10`) as `"UNDETERMINABLE"`.
- **`CS-19` Syntactic Direct-Store AST Scanner & Full-64-Hex SHA-256 Gate (`fixture-scoped` + `exact` hex check):** `scan_ast_answer_key_leaks` is a **syntactic direct-store AST check** (not inter-procedural dataflow analysis) inspecting target root/attribute names across `Assign`, `AnnAssign`, `AugAssign`, `NamedExpr`, and `Attribute`/`Subscript` targets.
  - *Tested fixture scope:* Flags direct answer-key leaks (`s_curr = s_exact`, `s_curr: int = s_exact`, `s_curr += s_exact`, `(s_curr := s_exact)`, `obj.s_curr = s_exact`, `arr[0] = s_exact`) and has `0` false positives on the **two shipped benign fixtures** (`err = abs(s_curr - s_exact)` and `buf[s_curr] = s_exact`).
  - *Known syntactic limits:* Does **not** track indirect aliasing (`x = s_exact; s_curr = x`), loop targets, function default arguments, or dict literal values; conversely, assigning expressions referencing `s_exact` to a tracked target name (e.g., `est = abs(pred - s_exact)` or `output = compare(model_out, ground_truth)`) is flagged by the syntactic rule.
  - Paired with exact full-64-hex SHA-256 verification catching 8-char-prefix / 56-char-mismatched digests (`prefix8_match = True, full_match = False, mismatched_hex_chars = 54`).

---

## 6. Pillar 5 — 3-Channel Persistence & Provenance Airlock Fixture (`definitional / fixture`)

`evaluate_three_channel_airlock` checks structured attestations across **$\Delta W$** (immutable `token_embd` SHA-256 lock + block `DPI` threshold), **$\Delta\mathrm{KV}$** (zero cross-model KV reuse + zero residual evicted entity mentions), and **$\Delta P_{\mathrm{data}}$** (corpus provenance + PII binding + CoT-off/CoT-on recall gap $\le 1/20$). The compliant fixture returns **`ALLOW`** (`mode_transfer_gap = 3/125`); all `5` single-channel negative controls (`token_embd` tamper, `32x` `DPI` spike, cross-model KV reuse, residual KV entity mention, and `954/1000 -> 800/1000` CoT gap) fail closed with **`DENY`**.

---

## 7. In-PR Reproducible Verification Commands & Receipts

All checks below run directly from files committed in this PR using standard Python 3 stdlib (zero external tools or unshipped scripts required):

- **3-Mode R4 Parity (`-I -B`, `-I -O -B`, `-I -B -W error`) plus `PYTHONHASHSEED=42 -B`:**
  ```bash
  cd evidence/track-s31-aletheia-v22-misfolding
  for flags in "-I -B" "-I -O -B" "-I -B -W error"; do
    python3 $flags aletheia_v22_misfolding_audit.py --standalone --json | sha256sum
    python3 $flags aletheia_v22_misfolding_audit.py --check aletheia_v22_misfolding_certificate.json --json
    python3 $flags test_aletheia_v22_misfolding_r5.py
  done
  PYTHONHASHSEED=42 python3 -B aletheia_v22_misfolding_audit.py --standalone --json | sha256sum
  ```
  - `--standalone --json` matches committed `aletheia_v22_misfolding_certificate.json` bit-for-bit across all modes (`f4f7f8abff0c7eae0d5678016c1041ab34870ef2de57a2f83e4cbb9a529f8a9b`).
  - `--check aletheia_v22_misfolding_certificate.json --json` exits `0` with `"valid": true` across all modes.
  - `test_aletheia_v22_misfolding_r5.py` runs `6` test cases (including `test_05` exact boundary witnesses for comparison-operator flips at oracle lines 398, 631, 844, 904 and audit line 162; on non-Linux hosts `test_04` and `test_06` explicitly call `unittest.skipTest` rather than silently returning).
- **Repository Self-Verification (`tests/run_all.py` & `aletheia audit-check`):**
  ```bash
  python3 -I -B tests/run_all.py
  python3 -I -O -B tests/run_all.py
  python3 -I -B -W error tests/run_all.py
  python3 -I -B -m aletheia audit-check evidence/track-s31-aletheia-v22-misfolding --strict-ancestors --safety-scan --scripts aletheia_v22_misfolding_audit.py test_aletheia_v22_misfolding_r5.py
  ```

---

## 8. Shipped Artifact Manifest

| File | Lines | Bytes | SHA-256 |
| :--- | :---: | :---: | :--- |
| `aletheia_v22_misfolding_oracle.py` | `1,248` | `57,360` | `e4b0ecb9a6e308306b5938cea12353553212420055505e735a635f476055e2cb` |
| `aletheia_v22_misfolding_audit.py` | `527` | `23,484` | `d58f9eb5dba204afbf8251a2d59793ee7a802d8b76f32582dd3941014b6d63eb` |
| `test_aletheia_v22_misfolding_r5.py` | `825` | `62,803` | `ac09664e42f8a3e7b972a4a77fe45d1c4a1bd762ec403dd2fcc2e4566f1556c9` |
| `aletheia_v22_misfolding_certificate.json` | `1` | `12,707` | `f4f7f8abff0c7eae0d5678016c1041ab34870ef2de57a2f83e4cbb9a529f8a9b` |
| `ALETHEIA_V22_MISFOLDING_REPORT.md` | *(this report)* | *(this report)* | *(omitted to prevent self-hash cycle)* |
