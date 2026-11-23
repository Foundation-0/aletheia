# Track S31 — Aletheia v2.2 Society-of-Scientists Governance (`CS-15..CS-19`), Weight-Space Misfolding `DPI`/`BWI` Separation & `siliquant` Quantization-Security Tomography (R2)

- **Track ID:** `TRACK-S31-ALETHEIA-V22-SOCIETY-MISFOLDING-TOMOGRAPHY`
- **Oracle Class:** Pure Python 3 stdlib exact $\mathbb{Z}/\mathbb{Q}$ (`fractions.Fraction`), zero IEEE-754 floats, zero bare `assert`s, zero RNG, Zone-B hardened CLI & verifier (full pure-$\mathbb{Q}$ deterministic replay + schema-safe secondary algebraic invariant checks on `--check`)
- **Novelty Rating (Law-4 Honest Accounting):** **`N1` exact-$\mathbb{Q}$ tomography operators, separation theorems, and executable Aletheia v2.2 governance gates compounding directly over `N0` empirical benchmarks from Portals 26, 27, and 28**
- **Certificate Digests (R2):**
  - `payload_sha256`: `8c815db0050d9af05c0837db114e6cfe0f029b1612f5c1406361f5523f241545`
  - `certificate_sha256`: `2fc5d382b44cea1e5d695c60a9c0bb518b340b78920df09d16455a7d8bb265fd`

---

## 1. Executive Summary & Law-4 Attribution Boundary

Track S31 unifies two foundational empirical portals with `Moissanite-Labs/siliquant` (Portal 26) and `Foundation-0/aletheia` v2.2 into a standalone, zero-float pure-$\mathbb{Z}/\mathbb{Q}$ operator and governance suite:
- **Portal 27 (`N0` Empirical Source):** Ahmad et al., *A Society of AI Scientists* (`2611.society-ai-scientists`, alphaXiv/OpenResearch, Nov 21, 2026) — `936` autonomous agents, `936` studies, `CS-15..CS-19` failure modes (`68%` diagnosis-only, `29.7% -> 12.2%` matched-gain drop, `2.64x` LoRA forgetting flip, `88%` vs `30%` herding, `+16.2 pp` sunk-cost escalation, `290/300` forced `"no"` abstention failure, `68%` null-overstatement, `s_curr = s_exact` answer-key leaks, memory-typed SHA-256 prefix hallucinations, `83–94%` / `86%` KV-cache persistence, `95.4% -> 80.0%` CoT mode-transfer drop, and `Qwen3.5-0.8B` `u^T W_edit = -5 u^T W_S` rank-1 mechanism reversal).
- **Portal 28 (`N0` Empirical Source):** von Csefalvay et al., *Weight space misfolding* (`2611.weight-space-misfolding`, HCLTech Robotics Intelligence CoE, Nov 2026) — gradient-free weight-space editing on `Qwen2.5-1.5B-Instruct` & `Gemma 3 4B IT` (`3,066`-param `Sydney -> Buenos Aires` `token_embd` patch, `2,266`-param `Brindle Supply` omission patch with `12/12` byte-identical 128-token controls and `1/22` defect rate, `pass@k` vs `pass^k` asymmetry, and §5.2 completeness / relational-closure blind spots).
- **Our `N1` Contribution:** Exact pure-$\mathbb{Z}/\mathbb{Q}$ separation theorems (`DPI` iso-Frobenius blindness, rank-1 Schatten dominance + directional reversal, `pass@k`/`pass^k` exact rational crossing thresholds, Hadamard $H_8$ spike spreading vs `token_embd.weight` bypass invariance with per-row SHA-256 locking), executable `CS-15..CS-19` governance oracles, and a fail-closed 3-channel persistence & provenance airlock specification hardened to the Uniform Zone-B Gold Standard.

---

## 2. Pillar 1 — Exact-$\mathbb{Q}$ Deep Patch Inspection (`DPI`) & Rank-1 Reversal Detection

### 2.1 Iso-Frobenius Blindness & Row-Concentration Separation Theorem

For any nonzero weight-matrix patch $\Delta W = W_1 - W_0 \in \mathbb{Q}^{R \times C}$, define:
$$\mathcal{C}_{\mathrm{row}}(\Delta W) := \frac{R \cdot \max_{r} \|\Delta W_{r,:}\|_2^2}{\|\Delta W\|_F^2} \in [1, R], \qquad \rho_{\mathrm{nnz}}(\Delta W) := \frac{\mathrm{nnz}(\Delta W)}{RC} \in (0, 1].$$

Over $\mathbb{Q}^{64 \times 16}$, Track S31 constructs two exact rational patches with **identically equal global Frobenius energy** ($\|\Delta W_{\mathrm{mis}}\|_F^2 - \|\Delta W_{\mathrm{quant}}\|_F^2 \equiv 0$, hence **identical global `W-err dB`**):

| Patch ($64 \times 16$) | Construction | $\|\Delta W\|_F^2$ | $\max_r \|\Delta W_{r,:}\|_2^2$ | $\mathcal{C}_{\mathrm{row}}$ | $\rho_{\mathrm{nnz}}$ |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Benign diffuse quantization** $\Delta W_{\mathrm{quant}}$ | $(\Delta W)_{r,c} = (-1)^{r+c} \cdot \frac{1}{4}$ | `64` | `1` | **`1`** | **`1`** |
| **Localized 2-row misfolding** $\Delta W_{\mathrm{mis}}$ | Rows `{7, 42}`, Pythagorean pairs `(6/5, 8/5)` ($\frac{36+64}{25}=4$) | `64` | `32` | **`32`** | **`1/32`** |
| **Single-row saturation bound** $\Delta W_{\mathrm{1row}}$ | Row `7`, all 16 entries `2` | `64` | `64` | **`64`** | **`1/64`** |

- **Exact Separation Factor:** `32x` on $64 \times 16$ (`frobenius_energy_residual = 0`).
- **Analytical `Qwen2.5-1.5B` `token_embd` (`151,936 × 1,536 = 233,373,696` params) Scaling (`N0` counts):**
  - `3,066`-param 2-row factual substitution: exact support density `511/38895616` and exact pigeonhole minimum concentration $\mathcal{C}_{\mathrm{row}} \ge 151{,}936 / 2 = \mathbf{75{,}968}$ (vs `1` for diffuse quantization at identical Frobenius energy).
  - `2,266`-param selective omission: exact support density `1133/116686848`; under uniform entry amplitude, the **1-full-row-saturated (`1,536 + 730` split)** upper bound gives $\mathcal{C}_{\mathrm{row}} = 151{,}936 \cdot \frac{1{,}536}{2{,}266} = \frac{116{,}686{,}848}{1{,}133} = \frac{RC}{2{,}266}$ ($> 102{,}989\times$), whereas an even 2-row split (`1,133 + 1,133`) achieves the pigeonhole lower bound $\mathcal{C}_{\mathrm{row}} = 151{,}936 / 2 = \mathbf{75{,}968}$.

### 2.2 Exact Rank-1 Spectral Dominance & Direction Reversal Detector

Define the pure-$\mathbb{Q}$ Schatten ratio $S_4(\Delta W) := \frac{\operatorname{tr}((\Delta W^\top \Delta W)^2)}{(\operatorname{tr}(\Delta W^\top \Delta W))^2}$ ($S_4 \equiv 1 \iff \operatorname{rank}(\Delta W) = 1$, whereas isotropic rank-$r$ noise satisfies $S_4 \equiv 1/r$) and the directional projection ratio $\gamma_u := \frac{u^\top W_1 v}{u^\top W_0 v}$:
- **Isotropic rank-4 control ($H_4$):** $S_4 = \mathbf{1/4}$ (`is_exact_rank_1 = False`).
- **Orthogonal abliteration (Arditi et al.):** $S_4 = \mathbf{1}$, $\gamma_u = \mathbf{0}$ (`regime = "orthogonal_abliteration"`).
- **5× Mechanism Reversal (`2611.society-ai-scientists` §4.3 `Qwen3.5-0.8B`):** $S_4 = \mathbf{1}$, $\gamma_u = \mathbf{-5}$ (`baseline_projection = 5`, `edited_projection = -25`, `regime = "mechanism_reversal"`).

---

## 3. Pillar 2 — Exact-$\mathbb{Q}$ `pass@k` vs. `pass^k` Risk Asymmetry & Bellwether Certifiers

### 3.1 Exact Rational Crossing Thresholds (Sharpening $k^*(1/22) = 15$)

Over exact `Fraction` with conservation residual $P_{\mathrm{att}}(p,k) + P_{\mathrm{def}}(p,k) - 1 \equiv 0$ across $p \in \{1/22, 1/100, 1/1000\}$ and $k \in \{1, 10, 22, 50, 100\}$:

| Defect Rate $p$ | Exact Threshold $k^*(p)$ (`pass@k* > 1/2`) | `k=1` (`bps`) | `k=10` (`bps`) | `k=22` (`bps`) | `k=50` (`bps`) | `k=100` (`bps`) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`1/22`** | **`15`** | `454` | `3,719` | `6,406` | `9,023` | **`9,904`** (`> 99%`) |
| **`1/100`** | **`69`** | `100` | `956` | `1,983` | `3,949` | `6,339` |
| **`1/1000`** | **`693`** | `10` | `99` | `217` | `487` | `952` |

> **Exact Pure-$\mathbb{Q}$ Threshold Refinement:** Evaluating $(21/22)^k$ exactly over $\mathbb{Q}$ proves that the minimal crossing threshold for $p = 1/22$ is **`k*(1/22) = 15`** (sharper than the heuristic estimate `16`):
> - At $k = 14$: $P_{\mathrm{att}}(1/22, 14) = \frac{2977901340906311863}{6221821273427820544} < \frac{1}{2}$.
> - At $k = 15$: $P_{\mathrm{att}}(1/22, 15) = \frac{68757749432460369667}{136880068015412051968} > \frac{1}{2} > \frac{68122318582951682301}{136880068015412051968} = P_{\mathrm{def}}(1/22, 15)$.
> - At $k = 16$: $P_{\mathrm{att}}(1/22, 16) = \frac{1580792806097079814975}{3011361496339065143296} > \frac{1}{2}$, and by $k = 100$ attacker victory exceeds `99%` (`9904 bps`).

### 3.2 Completeness & Relational-Closure Bellwether Certifiers (`2611.weight-space-misfolding` §5.2)

1. **Multiset Cardinality & Bijection Conservation (`Brindle Supply`):**
   - *Omission witness:* Dropping `"Brindle Supply"` passes naive positive-existence (`naive_positive_existence_pass = True`), yet fails cardinality & bijection (`omission_detected = True`, `missing_items = ["Brindle Supply"]`, `exact_recall = 3/4`).
   - *Duplicate substitution witness:* Replacing `"Brindle Supply"` with duplicate `"Acme Hardware"` preserves `len == 4` (`cardinality_conserved = True`) AND positive-existence, yet fails exact multiset bijection (`missing = ["Brindle Supply"]`, `extra = ["Acme Hardware"]`).
   - *Clean control:* Passes `bijection_exact = True`, `exact_recall = 1`.
2. **Relational-Closure Consistency (`"Buenos Aires, Australia"`):**
   - Both `"Buenos Aires"` and `"Australia"` are individually valid KB entities and `("Canberra", "Australia")` passes capital probing, yet `kb["Buenos Aires"] == "Argentina" != "Australia"` flags `relational_mismatch` (`consistent = False`), while the clean control passes `consistent = True`.

---

## 4. Pillar 3 — Exact-$\mathbb{Q}$ `siliquant` Spherical-Ball Quantization × Misfolding Interaction

1. **Exact Sylvester Hadamard $H_8 \in \{\pm 1\}^{8 \times 8}$:** Certified `symmetric = True` and $H_8^2 \equiv 8 I_8$ over exact $\mathbb{Z}$.
2. **Pure Spike $H_8$-Spreading Law:** For $\Delta w = 15 e_0 \in \mathbb{Q}^8$, exact $\ell_\infty^2 / \ell_2^2$ coherence drops from **`1`** to **`1/8`** identically (`coherence_ratio_drop = 1/8`, exact $1/\sqrt{8}$ amplitude spreading).
3. **128-Weight Group MLP Spike `BWI` Scale-Inflation Law:** Injecting $\Delta w = 15 e_0$ into a uniform $\pm 1$ 128-weight group inflates squared group scale $\|w\|_\infty^2$ by **`256x`** (`1 -> 256`) and raises squared peak-to-mean overload ratio from `1` to `32768/383` ($\approx 85.56 > 25$, tripping the $5\sigma$ overload alarm). On block 0 (`8` weights), $H_8$ preserves exact energy ($2104 = 8 \cdot 263$) while cutting peak coherence from `256/263` to `529/2104`.
4. **Unquantized `token_embd.weight` Bypass Theorem & Per-Row SHA-256 Lock (`RUN-BUG-02` Link):** Under block-matrix quantization $Q_{\mathrm{blk}}(W_{\mathrm{embd}}, W_{\mathrm{blk}}) = (W_{\mathrm{embd}}, Q(W_{\mathrm{blk}}))$, any embedding patch $\Delta W_{\mathrm{embd}}$ survives with live exact rational Frobenius energy ratio **`survival_fraction = post_quant_embd_energy_sq / dw_embd_energy_sq = (21/500) / (21/500) = 1`** (`post_quant_embd_patch_exact_invariant = True`, `block_matrices_unchanged = True`), whereas `token_embd_row_hashes_exact` computes genuine per-row SHA-256 digests (`per_row_sha256_base`, `per_row_sha256_patched`) plus overall manifest digests (`base_manifest_sha256 != patched_manifest_sha256`) and isolates the exact tampered row (`changed_rows_detected = [2]`, `unchanged_rows_count = 3`, `immutable_row_hash_lock_detected_edit = True`).

---

## 5. Pillar 4 — Exact-$\mathbb{Q}$ Aletheia v2.2 Governance Oracles (`CS-15..CS-19`)

- **`CS-15` Constructive Generalization & Scope Gate:** Enforces constructive fixes, strongest-baseline comparison, and cross-family scope (`>= 2` families or explicit single-family scoping); passes compliant controls and flags diagnosis-only unscoped failures.
- **`CS-16` Matched-Gain Pareto Comparator:** Certifies exact rational piecewise-linear interpolation on `(G, F)` curves: Korean vocab-freeze unmatched `297/1000` vs matched `61/500` (confound overstatement `7/40 = 17.5 pp`) AND the exact **`66/25 = 2.64x`** LoRA-vs-Full-FT sign-flip (`F_lora_end = 3/20 < 1/4 = F_full_end` unmatched, flipping to `F_lora(3/10) = 3/20 = (66/25) * (5/88) > F_full(3/10)` at matched gain `3/10`).
- **`CS-17` Herding & Sunk-Cost Escalation Detector:** Exact rational HHI & top-share gate flags score-visible herding (`22/25 = 88%`, `HHI = 487/625`) vs coordinate-only control (`3/10 = 30%`, `HHI = 13/50`), and rejects `+16.2 pp = 81/500` sunk-cost escalation (`119/500 -> 2/5`) against zero-shift preregistered allocation.
- **`CS-18` Mandatory 4-State Abstention & Exact Rational TOST Gate:** Performs a **synthetic `300`-case protocol verification** over `300` distinct `(record_id, query_topic, abstract_topic)` mismatched records (`SYN-MIS-000..299`, `distinct_synthetic_mismatched_records = 300`, modeled on `2611.society-ai-scientists` §5.3's `300`-abstract setup), returning `300/300` `"UNDETERMINABLE"` with zero forced `"no"` answers; accepts true equivalence `[-9/100, 9/100] subset (-1/10, 1/10)` as `"EQUIVALENT_NULL"`, and blocks non-significant wide CIs `[-3/10, 2/10]` (plus exact boundaries `±1/10`) as `"UNDETERMINABLE"` (`null_overstatement_blocked = True`).
- **`CS-19` Pure-AST Answer-Key Leak Scanner & Full-64-Hex SHA-256 Gate:** `scan_ast_answer_key_leaks` is a **syntactic direct-store AST detector** (not full inter-procedural dataflow analysis) covering all 5 Python store forms (`Assign`, `AnnAssign`, `AugAssign`, `NamedExpr`, and `Attribute`/`Subscript` target assignment, including `Tuple`/`List`/`Starred` unpacking). It inspects **only** assigned target root/attribute tokens — never subscript slice indices — catching direct answer-key leaks (`s_curr = s_exact`, `s_curr: int = s_exact`, `s_curr += s_exact`, `(s_curr := s_exact)`, `obj.s_curr = s_exact`, `arr[0] = s_exact`) with `0` false positives on both legitimate error calculation `err = abs(s_curr - s_exact)` and benign index usage `buf[s_curr] = s_exact`. Paired with full-64-hex SHA-256 verification that catches 8-char-prefix / 56-char-hallucinated digests (`prefix8_match = True, full_match = False, prefix8_hallucination_caught = True, mismatched_hex_chars = 54`).

---

## 6. Pillar 5 — Exact-$\mathbb{Q}$ 3-Channel Persistence & Provenance Airlock

`evaluate_three_channel_airlock` enforces fail-closed attestation across **$\Delta W$** (immutable `token_embd` SHA-256 lock + block `DPI` threshold), **$\Delta\mathrm{KV}$** (zero cross-model KV reuse + zero residual evicted entity mentions), and **$\Delta P_{\mathrm{data}}$** (corpus provenance + PII binding audit + CoT-off/CoT-on recall gap $\le 1/20$). The clean record returns **`ALLOW`** (`mode_transfer_gap = 3/125`), while all `5` single-channel negative controls — `token_embd` tamper, `32x` `DPI` spike, cross-model KV reuse, residual KV entity mention, and `954/1000 -> 800/1000` (`77/500 = 15.4 pp`) CoT recall collapse — fail closed with **`DENY`**.

---

## 7. R2 Hardening Closure, Verification, Mutation, Race Stress & Zone-B Security Receipts

### 7.1 R2 Dual-Continent Defect Closures (`AUDIT-131` + `AUDIT-131-DS`)

- **`S31-BUG-01` / `S31-DS-01` [HIGH] (CLOSED):** Rewrote `secondary_audit_payload` with schema-safe `_req_dict`/`_req_field` guards across all 5 pillars, enforcing exact `len(neg) == 5` (`AUDIT_P5_NEG_COUNT`), live `survival_fraction == 1` (`AUDIT_P3_SURV`), and `distinct_synthetic_mismatched_records == 300`, guaranteeing clean `ValueError` (`CLI rc=2`) with zero `rc=1` `KeyError`/`TypeError`/`AttributeError` tracebacks on any crafted JSON.
- **`S31-BUG-02` / `S31-DS-02` [MED] (CLOSED):** Capped `read_regular_bytes_capped(max_bytes)` to `1 <= max_bytes <= 64 MiB` (`INT_OUT_OF_RANGE` on `1 << 100` or `64 MiB + 1`) with bounded `65,536` B chunk reads; enforced upfront `type(payload) is bytes` (`INVALID_PAYLOAD_BYTES`) before `_open_dir_chain` in `write_regular_bytes_safe` (leaving zero temp files on `"str"`/`None`/`bytearray`); added real `os.fsync(fd)` and parent directory `os.fsync(dfd)`.
- **`S31-BUG-03` / `S31-DS-03` [MED] (CLOSED):** Upgraded `scan_ast_answer_key_leaks` across all 5 store forms (`Assign`, `AnnAssign`, `AugAssign`, `NamedExpr`, `Attribute`/`Subscript`) inspecting only target root/attr (zero FP on `buf[s_curr] = s_exact`), and replaced static `"survival_fraction": "1"` with live exact rational `post_quant_embd_energy_sq / dw_embd_energy_sq`.
- **`S31-DS-04` + `S31-DOC-01` [LOW/MED] (CLOSED):** Replaced whole-matrix hash with genuine per-row SHA-256 lock (`token_embd_row_hashes_exact`, `changed_rows_detected = [2]`), upgraded `CS-18` to `300` distinct synthetic records (`SYN-MIS-000..299`), fixed stale `oracle.py:8` docstring (`k*(1/22) = 15`), clarified §2.1 1-full-row-saturated bound (`116686848/1133` vs even 2-row `75,968`), scoped `CS-18`/`CS-19` honestly, and exercised the 5th parity mode as `PYTHONHASHSEED=42 -B` (without `-I`, since `-I` implies `-E` and ignores `PYTHONHASHSEED`).

### 7.2 Live R2 Gate Receipts

All gates ran sequentially under `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1` with zero `__pycache__`, zero temp leaks, and zero network/GitHub writes. Note that `--check` performs **full pure-$\mathbb{Q}$ deterministic replay + schema-safe secondary algebraic invariant cross-checks** (`secondary_audit_payload`) + constant-time `hmac.compare_digest` over canonical LF-only JSON bytes (external verifiers perform independent zero-shared-code re-derivation).

- **5-Mode Deterministic Parity (`-I -B`, `-I -O -B`, `-I -B -W error`, `-I -O -B -W error`, and `PYTHONHASHSEED=42 -B` without `-I`):**
  - `--standalone --json` and zero-arg stdout match committed `aletheia_v22_misfolding_certificate.json` bit-for-bit across all `5/5` modes (`f4f7f8abff0c7eae0d5678016c1041ab34870ef2de57a2f83e4cbb9a529f8a9b`).
  - `--check aletheia_v22_misfolding_certificate.json` returns `valid: true` across all `5/5` modes; `test_aletheia_v22_misfolding_r5.py` passes **`4/4 OK`** ×5 (`0` warnings, `~1.0–1.3s`).
- **Live Default-CLI `aletheia v2.0.0 mutate --max-mutants 0 --work-root . --add-cwd`:**
  - `aletheia_v22_misfolding_audit.py`: **`73/73` (`100.0%`, `survived=0`, `truncated=False`) KILLED**.
  - `aletheia_v22_misfolding_oracle.py`: **`169/169` (`100.0%`, `survived=0`, `truncated=False`) KILLED**.
  - **Combined:** **`242/242` (`100.0%`) KILLED**.
- **Exhaustive `SWAP + SUBCOND_DEL` AST `BoolOp` (`timeout=30s`):**
  - `aletheia_v22_misfolding_audit.py`: **`19/19` (`100.0%`, `SWAP=6, SUBCOND_DEL=13`, `survived=0`) KILLED**.
  - `aletheia_v22_misfolding_oracle.py`: **`27/27` (`100.0%`, `SWAP=9, SUBCOND_DEL=18`, `survived=0`) KILLED**.
  - **Combined:** **`46/46` (`100.0%`) KILLED**.
- **Live `Track S19c` Zone-B Adversarial Fuzzer (`zone_b_fuzzer.py`):**
  - CLI surface (`--target-cli aletheia_v22_misfolding_audit.py`): **`23/23 PASS`** (`bypasses=0, crashes=0`).
  - In-memory surface (`verify_certificate_dict`): **`18/18 PASS`** (`bypasses=0, crashes=0`).
  - **Combined:** **`41/41` (`100.0%`) PASS**.
- **Live Concurrent TOCTOU & Hardlink Race Stress (`test_04`, `500` Iterations × 5 Modes):**
  - Concurrent `renameat2(RENAME_EXCHANGE)` (leaf regular/symlink + intermediate dir/symlink) + concurrent `os.link`/`os.unlink` hardlink race: **`leaks=0, clobbers=0, hl_clobbers=0, leftover_tmps=0`**.
- **Static & Hygiene:** `aletheia v2.0.0 audit-check . --strict-ancestors --safety-scan --scripts aletheia_v22_misfolding_audit.py test_aletheia_v22_misfolding_r5.py` **`PASS`** (`5` files, `2/2` R4, `0` bare `assert`s, `0` AST float literals/`float()` calls, `0` `.isdigit()`, `0` path leaks, `0` CRLF, `0` `__pycache__`, `0` safety findings).

---

## 8. Frozen Artifact Manifest (R2)

| File | Lines | Bytes | SHA-256 |
| :--- | :---: | :---: | :--- |
| `aletheia_v22_misfolding_oracle.py` | `1,248` | `57,360` | `e4b0ecb9a6e308306b5938cea12353553212420055505e735a635f476055e2cb` |
| `aletheia_v22_misfolding_audit.py` | `527` | `23,484` | `d58f9eb5dba204afbf8251a2d59793ee7a802d8b76f32582dd3941014b6d63eb` |
| `test_aletheia_v22_misfolding_r5.py` | `778` | `59,133` | `0c072c8eb393404f948d1d80f99860dc2e469561323e1d6c21fa6a19cbb3fe97` |
| `aletheia_v22_misfolding_certificate.json` | `1` | `12,707` | `f4f7f8abff0c7eae0d5678016c1041ab34870ef2de57a2f83e4cbb9a529f8a9b` |
| `ALETHEIA_V22_MISFOLDING_REPORT.md` | *(this report)* | *(see delivery manifest)* | *(omitted to prevent self-hash cycle)* |
