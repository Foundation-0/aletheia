# Pure-Z/Q Zero-Delta-W State-Transport & Yield-Surface Tomography Operator

**Candidate Gate for `Foundation-0/aletheia` v2.2**  
**Schema:** `aletheia.zero_dw_state_transport.v1` | **Oracle Class:** `exact` | **Novelty Tier:** `N1`  
**Arithmetic Kernel:** Pure Python 3 standard library `int` and `Fraction` exclusively (`0` floating-point literals, `0` `float()` casts, `0` bare `assert`s, `0` mathematical RNG, `0` third-party dependencies).

---

## 1. Executive Summary & Core Theorem

Static parameter checksums verify only weight immutability ($\Delta W = 0$) and are structurally blind to inference-time phase crossings induced inside recurrent fast-weight memory or piecewise-linear yield surfaces. Scalar Frobenius-norm budgets are likewise blind whenever a rank-1 targeted perturbation and a diffuse nullspace perturbation carry identical Frobenius energy.

This package certifies a single **coordinate-free pure-$\mathbb{Z}/\mathbb{Q}$ Zero-$\Delta W$ State-Transport & Yield-Surface Tomography Operator** $\mathcal{T}_{\mathrm{st}}(S_0, S_1, w_{\mathrm{cls}}, b_0, q)$ paired with an executable fail-closed **4-Channel State-Transport Airlock** (`evaluate_state_transport_airlock`) over $(\Delta W, \Delta KV, \Delta S_{\mathrm{rec}}, \Delta P_{\mathrm{data}})$:

1. **Coordinate-Free Basis Invariance ($\Delta W = 0$):** For any square state transition $S_0 \mapsto S_1 = S_0 + \Delta S \in \mathbb{Q}^{d\times d}$, frozen readout $(w_{\mathrm{cls}}, b_0)$, query $q$, and exact rational orthogonal change of basis $Q \in O(d, \mathbb{Q})$ ($Q^\top Q = I_d$), all invariants of $\mathcal{T}_{\mathrm{st}}$ — exact rank $r = \operatorname{rank}_{\mathbb{Q}}(\Delta S)$, Frobenius energy $\|\Delta S\|_F^2 = \operatorname{tr}(\Delta S^\top \Delta S)$, Schatten-4 dominance ratio
   $$S_4(\Delta S) = \frac{\operatorname{tr}\!\big((\Delta S^\top \Delta S)^2\big)}{\big(\operatorname{tr}(\Delta S^\top \Delta S)\big)^2} \in \left[\frac{1}{r},\, 1\right],$$
   pre-/post-transition margins $m_t = w_{\mathrm{cls}}^\top S_t q + b_0$, margin transport $\Delta m = m_1 - m_0$, ReLU outputs $\operatorname{ReLU}(m_t)$, and the directional Cauchy–Schwarz envelope $(\Delta m)^2 \le \|w_{\mathrm{cls}}\|_2^2 \|q\|_2^2 \|\Delta S\|_F^2$ — are preserved bit-for-bit identically.
2. **Recurrent Latent-Memory Poisoning (`GDN-2` Channel-2B, Pillar 1):** Under strictly frozen weights ($\Delta W = 0$, identical weight SHA-256), a single rank-1 Pythagorean delta-rule update $k_5 = (3/5, 4/5, 0, 0)$, $v_5 = (0, 6, 0, 0)$ applied to an exact 4-key Hadamard-initialized state $S_4$ ($\ell_4$ error $= 0$) produces $\operatorname{rank}(\Delta S) = 1$, $S_4(\Delta S) = 1$, $\|\Delta S\|_F^2 = 212/5 \ge 106/5$ (universal fixed-rank Cauchy–Schwarz capacity lower bound), and flips the benign readout margin from **`+2` to `-83/25`** ($\Delta m = -133/25$, $m_0 m_1 = -166/25 < 0$). The poisoned margin persists unchanged after an intervening benign orthogonal turn $k_{\mathrm{orth}} = (4/5, -3/5, 0, 0)$, and all invariants remain bit-identical under $Q = H_4/2 \in O(4, \mathbb{Q})$ conjugation. General rank-$r$ trace/nuclear-norm bounds $\|\Delta S\|_F^2 \le \|\Delta S\|_*^2 \le r \|\Delta S\|_F^2$ and $S_4(\Delta S) \ge 1/r$ are certified across $r \in \{1, 2, 4\}$ alongside a benign nullspace control ($\|\Delta S\|_F^2 = 1/16$, $\Delta m = 0$).
3. **Viscoplastic ReLU Yield-Wall Advection & Discrete $S^2$ Cohomological Obstruction (Pillar 2):** Under frozen feedforward parameters $w_0 = (1, 0)$, $b_0 = -1$ ($\Delta W = 0$), a rank-1 delta-rule update advects the active ReLU yield hyperplane from **`x = 1` to `x = 4`** ($\Delta x = 3$), collapsing the fixed query $q = (3/2, 0)$ from active pre-activation $+1/2$ ($\operatorname{ReLU} = 1/2$) to dead pre-activation $-5/8$ ($\operatorname{ReLU} = 0$) under both $(\alpha = 1/2, \beta = 1)$ and the pure rank-1 lift $(\alpha = 1, \beta = 1$, $\|\Delta S\|_F^2 = 9/16$, $S_4 = 1)$, with exact $SO(2, \mathbb{Q})$ Pythagorean rotation invariance. On the closed $S^2$ cube cellular complex ($V=8, E=12, F=6, \chi=2, d_1 d_0 = 0, \beta = (1,0,1)$), linear discrete Gauss–Stokes divergence $\delta_1 = -d_0^\top$ cancels identically across all 12 basis fluxes and yields **`+13 + (-13) = 0`** on the asymmetric stress flux, whereas piecewise-linear ReLU projection on $[-1, 1]^2$ collapses area to $1/4$ with global divergence residual **`-4 != 0`** and breaks commutativity with $\delta_1$ ($\sum [\operatorname{ReLU}, \delta_1](u_{\mathrm{asym}}) = +13 \ne 0$).
4. **Iso-Frobenius Blindness & Executable 4-Channel Airlock Separation (Pillar 3):** At strictly identical $\Delta W = 0$ and strictly matched Frobenius energy $\|\Delta S\|_F^2 = 212/5$ (energy gap $= 0$), the rank-1 Channel-2B perturbation ($S_4 = 1$) flips margin `+2 -> -83/25` while a matched-energy rank-2 nullspace perturbation ($S_4 = 35657/70225$) produces $\Delta m = 0$. In weight space, exact $64 \times 16$ Deep Patch Inspection certifies a `32x` row-concentration separation at zero Frobenius gap (`E_F = 64`), scaling analytically to **`75,968x`** ($151,936 / 2$) on a 2-row localized patch of a $151,936 \times 1,536$ embedding table. The executable 4-channel gate `evaluate_state_transport_airlock` admits all `3/3` benign controls (`ALLOW`) and rejects all `5/5` attack controls (`DENY`), including both $\Delta W = 0$ state-space attacks where parameter-only hashing, Frobenius-only budgeting, and legacy 3-channel checks all return `ALLOW`.

---

## 2. Exact Mathematical Witnesses & Verified Constants

### 2.1 Pillar 1 — Recurrent Latent-Memory State Transport & General Rank-$r$ Bounds

| Witness / Invariant | Exact Pure-$\mathbb{Q}$ Value | Verification Meaning |
| :--- | :--- | :--- |
| Parameter drift $\Delta W$ | `0` (identical SHA-256) | Static parameter checksum sees zero change |
| Hadamard $K_4$ orthonormality & $\ell_4$ error | $K_4^\top K_4 = I_4$, $\text{err}_{\ell_4} = 0$ | Exact $d=4$ initialization baseline |
| Rank-1 `GDN-2` update $\Delta S = S_5 - S_4$ | $\operatorname{rank} = 1$, $S_4 = 1$, $\|\Delta S\|_F^2 = 212/5$ | Exact rank-1 dominance; Parseval error $= 212/5 \ge 106/5$ |
| Benign readout margin flip | `+2 -> -83/25` ($\Delta m = -133/25$) | Exact phase crossing under $\Delta W = 0$ |
| Directional Cauchy–Schwarz envelope | $17689/625 \le 424/5$ (`True`) | Exact rational transport bound satisfied |
| Intervening orthogonal turn $k_{\mathrm{orth}} = (4/5, -3/5, 0, 0)$ | $S_5' = S_5$, margin $= -83/25$ | Poisoning persists across benign orthogonal turns |
| $O(4, \mathbb{Q})$ conjugation ($Q = H_4/2$) | All invariants bit-identical | Coordinate-free theorem verified executably |
| Rank-2 anisotropic $(3, 1)$ bound | $\|\Delta S\|_F^2 = 10 < \|\Delta S\|_*^2 = 16 < 20$, $S_4 = 41/50 > 1/2$ | Strict interior of nuclear/Frobenius & Schatten brackets |
| Rank-2 isotropic $(2, 2)$ saturation | $\|\Delta S\|_F^2 = 8$, $\|\Delta S\|_*^2 = 16 = 2 \cdot 8$, $S_4 = 1/2$ | Sharp Cauchy–Schwarz & $S_4 = 1/r$ equality |
| Rank-4 Hadamard $H_4/2$ saturation | $\|\Delta S\|_F^2 = 4$, $\|\Delta S\|_*^2 = 16 = 4 \cdot 4$, $S_4 = 1/4$ | Sharp full-rank equality |
| Benign nullspace control $\frac{1}{4} e_2 e_2^\top$ | $\|\Delta S\|_F^2 = 1/16$, $\Delta m = 0$, $m_1 = +2$ | Non-zero benign state drift without phase crossing |

### 2.2 Pillar 2 — Yield-Wall Advection & Discrete $S^2$ Cohomological Obstruction

| Witness / Invariant | Exact Pure-$\mathbb{Q}$ Value | Verification Meaning |
| :--- | :--- | :--- |
| Yield-wall position ($w_0=(1,0), b_0=-1, \Delta W=0$) | `x = 1 -> 4` ($\Delta x = 3$) | Inference-time hyperplane advection with frozen weights |
| Query $q=(3/2, 0)$ pre-activation & ReLU | `+1/2 -> -5/8`; $\operatorname{ReLU}: 1/2 \to 0$ | Active-yielding to dead-face phase crossing |
| Injection & pure rank-1 lift ($\alpha=1$) | $\operatorname{rank} = 1$, $S_4 = 1$, $\|\Delta S\|_F^2 = 9/16$ | Pure rank-1 transport reproduces exact `1 -> 4` crossing |
| $SO(2, \mathbb{Q})$ rotation $Q_2 = \frac{1}{5}\begin{pmatrix}3&-4\\4&3\end{pmatrix}$ | All invariants bit-identical | Coordinate-free yield-wall invariance verified |
| $S^2$ cube cellular cochain complex | $V=8, E=12, F=6, \chi=2, d_1 d_0 = 0, \beta=(1,0,1)$ | Closed oriented 2-sphere discrete exterior calculus |
| Hodge orthogonality on $S^2$ | $\langle u_{\mathrm{pol}}, u_{\mathrm{tor}}\rangle = 0$, $E_{\mathrm{eq}} = 4 + 4 = 8$ | Exact discrete Pythagorean energy split |
| Discrete Gauss–Stokes on $S^2$ (`12/12` basis + stress) | `+13 + (-13) = 0` | Exact conservation on linear smooth divergence $\delta_1 = -d_0^\top$ |
| Piecewise-linear ReLU on $[-1, 1]^2$ | Area ratio $= 1/4$, global divergence $= -4 \ne 0$ | Exact cohomological failure of smooth conservation |
| Commutator $[\operatorname{ReLU}, \delta_1](u_{\mathrm{asym}})$ | Sum $= +13 \ne 0$ | Proves $\operatorname{ReLU}$ does not commute with $\delta_1$ |

### 2.3 Pillar 3 — Iso-Frobenius Blindness & 4-Channel State-Transport Airlock

| Control Case | Param-Only | Frob-Only | Legacy 3-Ch | 4-Ch Airlock | Exact Role |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `benign_clean_zero_drift` | `ALLOW` | `ALLOW` | `ALLOW` | **`ALLOW`** | Zero-drift clean baseline |
| `benign_nullspace_subthreshold_state_update` | `ALLOW` | `ALLOW` | `ALLOW` | **`ALLOW`** | Non-zero benign drift ($\|\Delta S\|_F^2=1/16$, $\Delta m=0$) |
| `benign_iso_frobenius_rank2_nullspace_212_over_5` | `ALLOW` | `ALLOW` | `ALLOW` | **`ALLOW`** | Matched energy $212/5$, rank 2, $S_4=35657/70225$, $\Delta m=0$ |
| `ch1_weight_hash_or_dpi_spike_32x` | `ALLOW` | `ALLOW` | `DENY` | **`DENY`** | Channel 1 `32x` localized weight concentration spike |
| `ch2a_kv_cross_model_reuse` | `ALLOW` | `ALLOW` | `DENY` | **`DENY`** | Channel 2A KV-cache cross-model leakage |
| `ch2b_gdn2_rank1_margin_poisoning_plus2_to_neg83_over_25` | `ALLOW` | `ALLOW` | `ALLOW` | **`DENY`** | Channel 2B rank-1 poisoning (`+2 -> -83/25`, $\Delta W=0$, matched $212/5$) |
| `ch2b_relu_yield_wall_advection_1_to_4_and_coh_neg4` | `ALLOW` | `ALLOW` | `ALLOW` | **`DENY`** | Channel 2B yield-wall crossing (`1 -> 4`, residual `-4`, $\Delta W=0$) |
| `ch3_data_mode_transfer_gap_exceeded` | `ALLOW` | `ALLOW` | `DENY` | **`DENY`** | Channel 3 mode-transfer provenance gap (`77/500 > 1/20`) |

---

## 3. Honest Novelty Scope (`N1`) & Explicit Prior-Art Quarantine

All constituent mathematical structures are established prior art and are explicitly quarantined as `N0`:

| Prior-Art Anchor | Classification | Scope Quarantined as Established Prior Art |
| :--- | :---: | :--- |
| Schlag, Irie & Schmidhuber (2021) — Fast-Weight Programmers | `N0` | Outer-product associative fast-weight state updates |
| Yang et al. (2024) — Gated DeltaNet (`GDN`) | `N0` | Rank-1 delta-rule recurrence $S_{t+1} = \alpha S_t + \beta (v - \alpha S_t k) k^\top$ |
| Bingham (1916); Duvaut & Lions (1976) | `N0` | Viscoplastic yield surfaces and variational inequalities |
| Montufar et al. (2014); Zhang et al. (2018) | `N0` | Piecewise-linear ReLU regions and tropical hyperplane geometry |
| Hirani (2003); Desbrun et al. (2005) | `N0` | Discrete Exterior Calculus (DEC), $d_1 d_0 = 0$, and $S^2$ Hodge decomposition |
| Arditi et al. (2024); `MemTensor/MemT-1.0-Pro` | `N0` | Directional weight-space refusal abliteration and `GDN-2` architecture naming |

**Scoped `N1` Contribution:** The novelty claim is restricted strictly to:
1. Unifying recurrent latent-memory poisoning, piecewise-linear ReLU yield-wall advection, discrete $S^2$ Gauss–Stokes vs. ReLU non-commutativity, and iso-Frobenius blindness under one coordinate-free pure-$\mathbb{Z}/\mathbb{Q}$ tomography operator $\mathcal{T}_{\mathrm{st}}$ with executable $O(d, \mathbb{Q})$ conjugation certificates; and
2. Packaging this operator as a fail-closed, symlink- and schema-hardened pure-$\mathbb{Z}/\mathbb{Q}$ 4-channel state-transport airlock candidate gate for `Foundation-0/aletheia` v2.2.

**Empirical Boundary Disclosures (Explicit Negative Flags in Certificate):**
- `measured_live_model_weights: false` — no live LLM checkpoint weights were loaded or mutated.
- `measured_live_serving_endpoint: false` — no live inference server was queried.
- `measured_live_mantle_gcm: false` — no live planetary convection simulation was executed.

---

## 4. Verification, Hardening & CLI Usage

### 4.1 Executable CLI Modes (`zero_dw_state_transport_audit.py`)
- `python3 -I -B zero_dw_state_transport_audit.py` — emit canonical single-line LF-only certificate JSON to `stdout`.
- `python3 -I -B zero_dw_state_transport_audit.py --standalone --json` — emit bit-identical canonical certificate JSON to `stdout`.
- `python3 -I -B zero_dw_state_transport_audit.py --write <path>` — atomically write `0o600` certificate via `dir_fd` `O_DIRECTORY | O_NOFOLLOW` ancestor walk (with verified root-owned macOS `/var`, `/tmp`, `/etc` -> `/private/*` ancestor prefix normalization), `O_CREAT | O_EXCL | O_NOFOLLOW` temp file, `os.fsync`, pre-replace `st_nlink` hardlink defense, and `os.replace`.
- `python3 -I -B zero_dw_state_transport_audit.py --check <path>` — verify regular-file strict streaming read, canonical single-line LF-only UTF-8/ASCII JSON bytes, SHA-256 digests, full pure-$\mathbb{Q}$ oracle replay, independent division-free algebraic cross-checks, and iterative bijective strict-typed full-schema equality.

### 4.2 Verified Receipts
- **3-Mode Isolated Parity (`-I -B`, `-I -O -B`, `-I -B -W error`) plus `PYTHONHASHSEED=42 -B`:** Zero-arg and `--standalone --json` outputs are bit-identical to `zero_dw_state_transport_certificate.json` (`12,803` bytes, `0o600`), `--check` returns `valid: true`, and `test_zero_dw_state_transport_r5.py` passes `17/17 OK` across all modes.
- **Live `aletheia mutate --guards require_ok --max-mutants 0 --work-root . --add-cwd`:**
  - `zero_dw_state_transport_oracle.py`: **`176/176` (`100.0%`, `survived=0`, `truncated=False`, `PASS`)**.
  - `zero_dw_state_transport_audit.py`: **`103/103` (`100.0%`, `survived=0`, `truncated=False`, `PASS`)**.
- **Whole-File DFS AST `BoolOp` Mutation Sweep (`OP_SWAP + SUBCOND_DEL`):** `30/30` (`oracle.py`) + `18/18` (`audit.py`) = **`48/48` (`100.0%`, `survived=[]`)**.
- **4-Surface Adversarial Certificate Fuzzer:** **`77/77 PASS`** (`23/23` CLI + `18/18` `full_replay=True` + `18/18` `full_replay=False` + `18/18` direct `secondary_audit_payload`; `bypasses=0`, `crashes=0`).
- **Exhaustive Tamper Walk (`531` cases: `405` leaves, zero/negative denominators, `32` nested-dict extra-key & container-collapse mutations, runtime floats, and Python scalar/container subclasses):** `0` accepted under `verify_certificate_dict(full_replay=False)`, `0` accepted under direct `secondary_audit_payload`, `0` raw crashes, `0` accepted and `0` tracebacks under live CLI `--check`.
- **Kernel & Concurrency Stress Suite:** `16T` distinct + `16T` same-target + `80T` barrier burst atomic `0o600` writes with `os.fsync`, `520`-iter Linux `renameat2(RENAME_EXCHANGE)` decoy-swap race (`0` escapes, cleanly skipped on non-Linux hosts), `420`-iter concurrent hardlink race, verified root-owned macOS `/var`/`/tmp`/`/etc` prefix normalization, `/proc/kallsyms` streaming read-cap defense, scratch `os.mkfifo` non-regular rejection, `chmod 000`, deleted CWD, symlinked `$PWD`, and raw non-UTF-8 CLI bytes (`rc=2`, structured JSON).
- **Certificate Digests:**
  - `payload_sha256`: `6e2ee73ca4bb29834ab192443a9506c20517b50e8e293f78d767131358ece7ef`
  - `certificate_sha256`: `1b719d4fc17416537c76f3fdbde515d09270d45f8458ce25957579244a5d2145`

---

## 5. Frozen Artifact Manifest

| File | Lines | Bytes | Mode | SHA-256 |
| :--- | ---: | ---: | :---: | :--- |
| `zero_dw_state_transport_oracle.py` | `1422` | `60883` | `0644` | `a5444772fa803f5972294eb9f8bd86b7d5f8fcc7fd7a58f4985a83cfd84a51aa` |
| `zero_dw_state_transport_audit.py` | `522` | `23173` | `0644` | `c45d11303349562f031f3ae9b9ce8afb624938f580eb8e0c79d7b2c360e37c1a` |
| `test_zero_dw_state_transport_r5.py` | `1157` | `63347` | `0644` | `30bcdccf8dc6bba35a7f31adeed129fb9832c3648515ca9034b95a5bc045a492` |
| `zero_dw_state_transport_certificate.json` | `1` | `12803` | `0600` | `1316eede91b66c309c427fec60e36374350d65b6649eba7154de8e4ea4431320` |
| `ZERO_DW_STATE_TRANSPORT_REPORT.md` | *(this report)* | *(verified post-write)* | `0644` | *(verified by `audit-check`)* |
