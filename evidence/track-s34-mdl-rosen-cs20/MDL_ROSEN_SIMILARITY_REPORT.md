# Track S34 (Portal 31): Exact Pure-$\mathbb{Z}/\mathbb{Q}$ Two-Part MDL, Prequential/Requential Coding & Robert Rosen Similarity/Bifurcation Extrapolation Obstruction (`CS-20`)

- **Track / Portal ID:** `Track S34` (`TRACK-S34-MDL-ROSEN`) / Portal 31 (`R2` Dual-Continent Closure)
- **Oracle Class:** `exact` (100% pure Python 3 stdlib `int`, `fractions.Fraction`, `hashlib`, `hmac`; **zero IEEE-754 floats in production AST** across `mdl_rosen_similarity_oracle.py`, `mdl_rosen_similarity_audit.py`, and `mdl_rosen_similarity_certificate.json`, and zero AST float literals or `float()` calls in `test_mdl_rosen_similarity_r5.py` where deliberate negative test fixtures use `json.loads("1.5")` / `json.loads("NaN")` / `json.loads("1.0")` solely to verify fail-closed float rejection; zero bare `assert`s; zero scientific/simulation RNG — `secrets.token_hex(8)` is used solely for unguessable atomic temp filenames; zero external dependencies)
- **Honest Law-4 Novelty Classification:** **`N1`** (clean-room unified pure-$\mathbb{Z}/\mathbb{Q}$ exact-operator certificate engine bridging offline two-part MDL / prequential regret / `arXiv:2607.11883` requential coding, `siliquant` `Gemma 3 4B IT` two-part MDL Pareto dominance & log-convex bitrate law $b^*(T/N)$, Rosen 1983 corresponding-states commutation & exact Sturm/discriminant bifurcation obstruction, synthetic `64 × 16` iso-MDL / iso-Frobenius weight-space misfolding blindness vs. `DPI` separation, and an executable Aletheia v2.2 `CS-20` *Bifurcation-Blind Extrapolation* Gate across 5 live expedition witnesses; all classical theorems and cited prior papers strictly quarantined as **`N0`** below)
- **Canonical R2 Certificate Digests (`mdl_rosen_similarity_certificate.json`):**
  - File / zero-arg / `--standalone --json` SHA-256: `ad03c2fb0977f8fae30849eb18e86b9050d03c4793cbb9e6295891d28b67d242`
  - `payload_sha256`: `43306270647192181d8eb378ce39cca08e7b9cc8ca8867e627ba2126b576afef`
  - `certificate_sha256`: `c666b80121bfa727bd4ecc08eb316e04248bd1f9d28e4f1e316f0acee7e45b54`

---

## 1. Strict Law-4 `N0` Prior-Art Quarantine & Scope Boundaries

| Classical Theorem / Cited Prior Work | Primary Attribution (`N0`) | Exact Role in `Track S34` |
|---|---|---|
| Algorithmic probability, MDL, & prequential coding | Solomonoff (1964); Rissanen (1978/1984); Dawid (1984) | Pillar 1 exact dyadic cancellation $L_{\mathrm{offline}} - L_{\mathrm{online}} \equiv b|\theta| - R(X)$ & hardcoding no-profit theorem |
| Offline vs. online MDL synthesis & Requential Coding | Greene (`greene.sh/compression-and-intelligence/`, 2026); `arXiv:2607.11883` | Pillar 1 three-way separation (Two-Part MDL vs. Prequential vs. noise-invariant Requential KL) |
| Dimensional analysis, corresponding states, & catastrophe theory | Buckingham (1914); van der Waals (1873); Thom (1972); Rosen (1983, `PMID:6846566`) | Pillar 3 exact power-law & reduced van der Waals commutation, critical triple root $(1,1,1)$, & cusp $1 \ne 3$ real-solution-set bijection obstruction |
| Spherical-lattice quantization, weight-space misfolding, & metascience confounds | `Track S30` (`gemma-3-{270m,1b,4b}-it.jsonl`); `2611.weight-space-misfolding`; `2611.society-ai-scientists`; `siliquant#60/#61` | Pillar 2 Pareto dominance & $b^*(T/N)$, Pillar 4 synthetic `64 × 16` iso-MDL misfolding witness vs. `DPI`, & Pillar 5 `CS-20` expedition witnesses |

> **Honest Law-5 Scope Boundary:** Zero metaphorical "language smuggling" between information theory and morphogenesis. Every claim below is a finite, machine-certified algebraic identity or exact rational bracket over $\mathbb{Z}/\mathbb{Q}$ on explicit finite models and SHA-256-pinned empirical tables.

---

## 2. Pillar 1 — Offline Two-Part MDL vs. Prequential Regret & Requential Coding (`arXiv:2607.11883`)

Over a 4-symbol alphabet ($L_u(X) = 2T$) with exact dyadic probabilities $p(x) = 2^{-k}$ (so $-\log_2 p(x) \in \mathbb{Z}_{\ge 0}$ and $\mathrm{KL}(Q \Vert P) \in \mathbb{Q}_{\ge 0}$ identically with zero floats):

1. **Exact Cancellation Identity & Regime Crossover ($T = 32$, $L_u = 64$, $L_{\theta_T} = 56$, $L_{\mathrm{online,raw}} = 60 < 64$, $R(X) = 4$, $c = 2$):**
   $$L_{\mathrm{offline}}(X) - L_{\mathrm{online}}(X) \equiv b|\theta| - R(X) \quad (\text{residual } = 0 \text{ across all 3 regimes}).$$
   - Large-model regime ($b|\theta| = 12 > 4$): $L_{\mathrm{offline}} = 70 > 62 = L_{\mathrm{online}}$ (`L_diff = +8`, online wins).
   - Exact crossover ($b|\theta| = 4 = R(X)$): $L_{\mathrm{offline}} = L_{\mathrm{online}} = 62$ (`L_diff = 0`).
   - Compact-model regime ($b|\theta| = 2 < 4$): $L_{\mathrm{offline}} = 60 < 62 = L_{\mathrm{online}}$ (`L_diff = -2`, offline wins).
2. **Exact Verbatim Hardcoding No-Profit Theorem:** Hardcoding $T \in \{1, 4, 16, 32\}$ verbatim symbols costs $2T$ table bits plus decoder overhead $c_{\mathrm{dec}} = 2$, yielding $L_{\mathrm{hardcode}}(X) = 2T + 2 > 2T = L_u(X)$ strictly (zero net gain even at $c_{\mathrm{dec}} = 0$). A reusable 2-bit pattern saves $2m - 2 > 0$ bits iff reused across $m \ge 2$ predictions (`m = 1 -> 0`, `m = 2 -> +2`, `m = 4 -> +6`, `m = 8 -> +14`).
3. **Exact Three-Way Compression Separation ($T = 16$, tensoring with uniform 1-bit noise channel $H(Z) = 1$):**
   - **Two-Part MDL:** grows linearly by $+T \cdot H(Z) = +16$ bits (`40 -> 56`) while still paying $b|\theta| = 12$.
   - **Prequential Coding:** grows linearly by $+T \cdot H(Z) = +16$ bits (`29 -> 45`), paying irreducible data entropy $H(Q_t) + H(Z)$ even after convergence.
   - **Requential Coding (`arXiv:2607.11883`):** $\sum_{t=1}^{16} \mathrm{KL}(\tilde{Q}_t \Vert \tilde{P}_t) = 1$ bit before AND after tensoring with $Z$ (**exact invariance `delta_req = 0`**).

---

## 3. Pillar 2 — Exact `siliquant` Two-Part MDL Pareto Dominance & Optimal Bitrate Law (`Gemma 3 4B IT`)

Grounded directly on pinned `Track S30` `gemma-3-4b-it.jsonl` (source SHA-256 `5895d850aff01a154a3b57e1c47468c90121e34316fa6e850ae866f6ec4dc23e`; `N_act = 3,208,642,560`, `238` active matrices) using a live-computed 14-term pure-$\mathbb{Q}$ artanh enclosure proving $\ln 2 \in [0.693147180559, 0.693147180560]$:

- **Explicit Units & $\ln 2$ Conversion Convention:** All `kl_mean` values in `gemma-3-4b-it.jsonl` are in **nats** (`kl_mean_units = "nats"`). Converting to bits gives the two-part MDL data term $(T / \ln 2) \cdot \mathrm{KL}_{\mathrm{nats}}$, so the per-weight objective in bits is $L(b) = b + \frac{T/N}{\ln 2}\,\mathrm{KL}_{\mathrm{nats}}(b)$. Under $\mathrm{KL}_{\mathrm{nats}}(b) = C \cdot 2^{-\alpha b}$, the $\frac{1}{\ln 2}$ unit conversion **cancels identically** with $\ln 2$ from $\frac{d}{db}(2^{-\alpha b}) = -\alpha(\ln 2)\,2^{-\alpha b}$, giving the exact first-order optimality condition $\frac{dL}{db} = 1 - (T/N)(\alpha C)\,2^{-\alpha b} = 0 \iff (T/N)(b^*) = 2^{\alpha b^*}/(\alpha C)$.

1. **Strict Two-Part MDL Pareto Dominance (`EBG128:b560s16` vs. `file:Q4_K_M` for ALL $T \ge 0$):**
   - Model-term savings: $\Delta b = -0.315202\text{ bpw}$ (`1.011 Gbits` saved on active weights).
   - Data-term savings: $\Delta\mathrm{KL}_{\mathrm{wiki}} = -57{,}011/1{,}000{,}000\text{ nats}$ (`0.094284 < 0.151295`) and $\Delta\mathrm{KL}_{\mathrm{py}} = -6{,}283/250{,}000\text{ nats}$ (`0.039951 < 0.065083`).
   - Hence $L_{\mathrm{offline}}(\mathrm{EBG128}; T) < L_{\mathrm{offline}}(\mathrm{Q4\_K\_M}; T)$ strictly for **every** corpus size $T \ge 0$.
2. **Exact Pure-$\mathbb{Q}$ Break-Even Corpus Enclosures vs. `BF16` (`16 bpw`):**

| Variant | `bpw` | Wiki `kl_mean` (nats) | Wiki Break-Even $T/N$ (tok/param; total tokens) | Python `kl_mean` (nats) | Python Break-Even $T/N$ (tok/param; total tokens) |
|---|---:|---:|---:|---:|---:|
| `file:Q4_K_M` | `4.815104` | `0.151295` | `51.242797` (`164.420B`) | `0.065083` | `119.121414` (`382.218B`) |
| `ZBG128:b560s16` | `4.499796` | `0.112601` | `70.792744` (`227.149B`) | `0.041972` | `189.920275` (`609.386B`) |
| `EBG128:b560s16` | `4.499902` | `0.094284` | **`84.545206` (`271.275B`)** | `0.039951` | **`199.525923` (`640.207B`)** |
| `hZBG128:b560s16` | `4.504050` | `0.071645` | `111.220399` (`356.867B`) | `0.031101` | `256.209945` (`822.086B`) |

3. **Exact Log-Convex Two-Part MDL Bitrate Law ($\mathrm{KL}_{\mathrm{nats}}(b) = C \cdot 2^{-\alpha b}$, $\alpha = 18821/10000$, $C = 199517/5000$):**
   - **Certified `ZBG128` Empirical Fit Residuals (all `< 0.25%` relative error):**
     - `ZBG128:b496s16` (`3.999902 bpw`): observed `0.215755` vs. predicted `0.216168` (`rel_err_upper <= 0.1913%`).
     - `ZBG128:b560s16` (`4.499796 bpw`): observed `0.112601` vs. predicted `0.112607` (`rel_err_upper <= 0.0057%`).
     - `ZBG128:b624s16` (`4.999956 bpw`): observed `0.058527` vs. predicted `0.058640` (`rel_err_upper <= 0.1926%`).
   - **Certified First-Order & Second-Order Optimality:** At ALL `5/5` schedule points, the pure-$\mathbb{Q}$ derivative enclosure satisfies $0 \in [dL/db_{\mathrm{lo}}, dL/db_{\mathrm{hi}}]$ with width $< 10^{-11}$ (`[0.000000000000, 0.000000000000]` to 12 decimals). Exact strict convexity holds everywhere: $\left.\frac{d^2 L_{\mathrm{offline}}}{db^2}\right|_{b^*} = \alpha \ln 2 \approx 1.304572 > 0$, with proven strict local-minimum margins at $b^* \pm 1/4$ (`+0.036675` / `+0.045586`).
   - **Exact Pure-$\mathbb{Q}$ Taylor-Certified Schedule $T/N(b^*) = 2^{\alpha b^*}/(\alpha C)$:** `b = 4.0 -> 2.458225` (`7.888B` tok), **`b = 4.5 -> 4.719608` (`15.144B` tok)**, `b = 5.0 -> 9.061293` (`29.074B` tok), `b = 6.0 -> 33.400943` (`107.172B` tok), `b = 8.0 -> 453.832760` (`1456.187B` tok).

---

## 4. Pillar 3 — Rosen (1983, `PMID:6846566`) Similarity Principle & Bifurcation Obstruction

1. **Within-Phase Commuting Diagrams:**
   - Monomial power law $\Phi(a, x) = x^2 - a = 0$: commutes identically under $(T_a, T_x) = (\lambda^2 a, \lambda x)$ with $\partial_x \Phi = 2x \ne 0$.
   - Reduced van der Waals equation of state $F(V_r) = 3 P_r V_r^3 - (P_r + 8 T_r) V_r^2 + 9 V_r - 3 = 0$: commutes identically across distinct rational physical gas prototypes under linear critical-constant scaling, and hits an exact rational triple root at $(P_r, V_r, T_r) = (1, 1, 1)$ ($F = F' = F'' = \Delta = 0$).
   - Exact cubic discriminants: supercritical $(P_r=1, T_r=2) \implies \Delta = -21{,}696 < 0$ and $(1, 3) \implies \Delta = -111{,}360 < 0$ (1-root single phase), versus subcritical $(P_r=1/2, T_r=7/8) \implies \Delta = +81/2 > 0$ with 3 distinct certified physical roots in $(1/3, \infty)$ ($V_r = 1$ plus sign changes on $(1/2, 3/4)$ and $(3, 4)$).
2. **Exact Cusp/Pitchfork Real-Solution-Set Bijection Obstruction ($\Phi(a,b,x) = x^3 + ax + b = 0$, $\Delta = -4a^3 - 27b^2$):**
   - Supercritical phase ($\Delta < 0$): $(1, 0) \implies \Delta = -4$, Sturm real-root count **`1`**; $(2, 3) \implies \Delta = -275$, count **`1`**.
   - Fold/cusp manifold ($\Delta = 0$): $(-3, \pm 2) \implies \Delta = 0$, exact double root at $x = \pm 1$ with $\partial_x \Phi = 0$ (Implicit Function Theorem fails).
   - Multi-phase region ($\Delta > 0$): $(-4, 0) \implies \Delta = 256$, Sturm count **`3`** ($\{-2, 0, +2\}$); $(-7, 6) \implies \Delta = 400$, count **`3`** ($\{-3, 1, 2\}$).
   - Since $|\mathcal{S}(1, 0)| = 1 \ne 3 = |\mathcal{S}(-4, 0)|$, **no bijection of real solution sets** — and hence no root-preserving homeomorphism, diffeomorphism, or Buckingham-$\Pi$ similarity map $T_x$ — can map one phase onto the other across the bifurcation boundary.

---

## 5. Pillar 4 — Global MDL Blindness on a Synthetic `64 × 16` Weight-Matrix Misfolding Witness

On a **synthetic `64 × 16` weight-matrix witness** (`model_scope = "synthetic_64x16_weight_matrix_witness"`, inspired by `token_embd` misfolding; `64` rows × `16` dims + `64,512` body weights = `65,536` weights, `1,048,576` base bits):
- Benign diffuse quantization $\Delta W_{\mathrm{quant}}$ (uniform $1/16$ everywhere) and surgical single-row misfolding patch $\Delta W_{\mathrm{mis}}$ (nonzero only on row `63`) have **identical global Frobenius norm squared $\|\Delta W\|_F^2 = 4$**.
- The misfolding patch adds only `262` sparse description bits (`131/524288 <= 1/1000` relative model-bit overhead) and leaves all **`12/12`** generic control queries (rows `0..11`) bit-identical: $\Delta L_\theta(X_{\mathrm{ctrl}}) = 0$ and Requential $\mathrm{KL}_{\mathrm{ctrl}}(P_0 \Vert P_1) = 0$.
- Yet on out-of-support trigger row `63`, the predicted argmax flips (`0 -> 1`), trigger $\mathrm{KL} = 5/8 > 0$, exact readout $L_1$ defect $\delta_{\mathrm{comm}} = \|P_1 - P_0\|_1 = 3/4 \ne 0$, and exact Row-Energy Concentration spikes **`64×`** (`DPI = 64` vs. benign `DPI = 1`, exceeding `32×`).

---

## 6. Pillar 5 — Executable Aletheia v2.2 `CS-20` (*Bifurcation-Blind Extrapolation*) Gate

`evaluate_cs20_extrapolation_gate(prototype_spec, target_spec)` enforces **`4` exact structural invariant checks** (`DISCRETE_REGIME_CLIFF`, `SINGULAR_BIFURCATION_MANIFOLD` / `DISCRIMINANT_SIGN_FLIP`, `BOTTLENECK_PHASE_CROSSING`, `DPI_STRUCTURAL_CONCENTRATION_SPIKE`). All witness discriminants and phases are derived live from pinned rational inputs (`Track S30` `gemma-3-270m-it.jsonl` `dafe50f9...`, `gemma-3-1b-it.jsonl` `040717b2...`, `gemma-3-4b-it.jsonl` `5895d850...`; TPU v5e exact ridge $B^* = 19700/273$; Pillar 3 vdW discriminants; Pillar 4 `DPI`; `CS-16` LoRA forgetting ratios):
- **3 Clean Within-Phase Pairs -> `ALLOW_EXTRAPOLATION` (`reason_codes = []`):**
  1. `siliquant` Gemma 3 `270M -> 1B` `Q4_K_M` (both `promoted_6_of_7`, HBM-bound, positive `EBG128 - Q4_K_M` Wiki KL advantage `+6333/250000` -> `+3221/200000` nats);
  2. TPU v5e BF16 decode `B = 1 -> B = 32` (both strictly below exact ridge $B^* = 19700/273 \approx 72.161$);
  3. Reduced van der Waals supercritical `T_r = 2 -> T_r = 3` at `P_r = 1` (both $\Delta < 0$).
- **5 Live Expedition Cross-Boundary Witnesses -> `DENY_PHASE_BIFURCATION`:**
  1. `siliquant` `1B -> 4B` `Q4_K_M` fallback cliff (`6/7 -> 0/7`, Wiki KL advantage flips `+3221/200000 -> -57011/1000000` nats): `["DISCRETE_REGIME_CLIFF", "DISCRIMINANT_SIGN_FLIP"]`;
  2. TPU v5e `B = 32 -> B = 73` MXU ridge crossing ($B^* = 19700/273$): `["DISCRIMINANT_SIGN_FLIP", "BOTTLENECK_PHASE_CROSSING"]`;
  3. van der Waals `(1, 2) -> (1/2, 7/8)` (`-21696 -> +81/2`): `["DISCRIMINANT_SIGN_FLIP", "BOTTLENECK_PHASE_CROSSING"]`;
  4. `2611.weight-space-misfolding` synthetic `64 × 16` iso-MDL patch (`DPI 1 -> 64 > 16`): `["DPI_STRUCTURAL_CONCENTRATION_SPIKE"]`;
  5. `2611.society-ai-scientists` (`CS-16`) unmatched-gain LoRA forgetting sign-flip (`703/1000 -> 264/100`, relative delta `-297/1000 -> +41/25`): `["DISCRETE_REGIME_CLIFF", "DISCRIMINANT_SIGN_FLIP", "BOTTLENECK_PHASE_CROSSING"]`.

---

## 7. Uniform Zone-B Hardening & R2 Verification Receipts

- **Verification Semantics & Honest Threat Model:** `mdl_rosen_similarity_audit.py --check <path>` performs atomic per-component `dir_fd` `openat` regular-file reading (including atomic `dir_fd` `O_DIRECTORY | O_NOFOLLOW` traversal of `PWD`, `ELOOP`/`ENOTDIR` handling, leaf `O_NOFOLLOW | O_NONBLOCK`, `fstat S_ISREG`, and streaming 64 KiB capped `os.read` with `max_bytes <= 64 MiB`), strict zero-float / zero-BOM / zero-CRLF / zero-surrogate / ASCII-only-digit JSON parsing (rejecting `"-0"` and leading zeros), strict `_validate_json_tree` enforcement inside `canonical_json_bytes` (rejecting `10**4300`, floats/`NaN`, and cyclic graphs without `ValueError`/`RecursionError`), strict 64-char lowercase hex check before `hmac.compare_digest`, self-consistent SHA-256 + schema-safe exact-int `secondary_audit_payload` (enforced even under `verify_certificate_dict(..., full_replay=False)`), plus **deterministic full pure-$\mathbb{Q}$ replay** (`full_replay=True` default). Note honestly that `--check` shares parsers and replay primitives with `mdl_rosen_similarity_oracle.py`; zero-shared-code re-derivation is reserved for independent external verifiers. Atomic writes validate `type(payload) is bytes` before touching disk, check `dir_fd` `lstat` (`SYMLINK_FORBIDDEN`, `NOT_A_REGULAR_FILE`, `HARDLINK_FORBIDDEN` for `st_nlink > 1`), create an exclusive `0o600` temp file with thread-locked CSPRNG name `secrets.token_hex(8)` (`O_CREAT | O_EXCL | O_NOFOLLOW | O_NONBLOCK`), call `os.fsync(tmp_fd)`, re-verify `os.fstat(tmp_fd).st_nlink == 1` before `os.replace(..., src_dir_fd=dfd, dst_dir_fd=dfd)`, and call `os.fsync(dfd)` (protecting against cross-user snooping and temp link tampering under the standard POSIX same-UID directory-write threat boundary).
- **5-Mode Parity (`-I -B`, `-I -O -B`, `-I -B -W error`, `-I -O -B -W error`, `PYTHONHASHSEED=42 -B` [without `-I`]):**
  - Zero-arg & `--standalone --json`: bit-identical `ad03c2fb0977f8fae30849eb18e86b9050d03c4793cbb9e6295891d28b67d242` ×5 (exact match to on-disk `mdl_rosen_similarity_certificate.json`).
  - `--check mdl_rosen_similarity_certificate.json`: bit-identical `b5a9488ca2abb84ef6c069e427f372794a5a9889e4e5eace70cd6a36c54cdb48` ×5 (`valid: true`).
  - `test_mdl_rosen_similarity_r5.py`: **`4/4 OK`** ×5 (`0` warnings, `0` bare `assert`s, `0` AST floats), including live `520`-iter concurrent `renameat2(RENAME_EXCHANGE)` (`0` leaks, `0` clobbers), `420`-iter concurrent `os.link`/`os.unlink` hardlink inode-immutability race (`0` clobbers, `0` leftover temps), `16T` distinct + `16T` same-target + `80T` synchronized barrier burst concurrent writes (`0` errors, `0` leftovers, `0o600`), live pre-replace temp hardlink injection (`HARDLINK_FORBIDDEN`), `0o600` & `EEXIST` CSPRNG retry, `70 KB` streaming read, `canonical_json_bytes` int-cap/float/`NaN`/cycle rejection, `full_replay=False` + exact-int `secondary_audit_payload` bool/float-for-int rejection, atomic `dir_fd` `PWD` refusal, deleted-CWD `CWD_UNAVAILABLE` (`rc=2`), and strict space- & equals-syntax CLI path refusal (`rc=2`, `0` files).
- **Live Default-CLI `aletheia v2.0.0 mutate --max-mutants 0 --work-root . --add-cwd`:** **`80/80` (`audit`) + `73/73` (`oracle`) = `153/153` (`100.0%`, `survived=0`, `truncated=False`) KILLED**.
- **Exhaustive `SWAP + SUBCOND_DEL` AST `BoolOp` Sweep (`timeout=30`):** **`30/30` (`audit`, `10/10` SWAP + `20/20` SUBCOND_DEL) + `9/9` (`oracle`, `3/3` SWAP + `6/6` SUBCOND_DEL) = `39/39` (`100.0%`, `surv=[]`) KILLED**.
- **Live `Track S19c` Zone-B Adversarial Fuzzer:** **`23/23` CLI + `18/18` `verify_certificate_dict(full_replay=True)` + `18/18` `verify_certificate_dict(full_replay=False)` = `59/59` (`100.0%`, `bypasses=0`, `crashes=0`) `PASS`**.
- **Static & Hygiene Gate:** `aletheia v2.0.0 audit-check . --strict-ancestors --safety-scan --scripts mdl_rosen_similarity_audit.py test_mdl_rosen_similarity_r5.py` **`PASS`** (`5` files, `2/2` R4, `0` findings, `PYC=0`, `0` personal-path/private-org leaks, `0` bare `assert`s, `0` AST floats across all `3/3` `.py` files and JSON certificate).
