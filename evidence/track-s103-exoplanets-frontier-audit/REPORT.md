# Track S103 — SOP-9 / SOP-10 Live Forensic Audit of `Foundation-0/exoplanets-frontier` & Public Astronomy Spine + Pure-$\mathbb{Z}/\mathbb{Q}$ Exact Verification Operators & Pure-`Init` `Lean 4.36.0` Companion

- **Track ID:** `TRACK-S103-EXOPLANETS-FRONTIER-AUDIT`
- **Schema Version:** `aletheia.s103_exoplanets_frontier_audit.v1`
- **Oracle Class / Novelty:** `exact` / **`N1`** (`n2_claims = 0`; CPU-only, `0` GPU touch, `0` GitHub writes, `0` repo copies inside `expedition/`)
- **External Scope:** Strictly public repositories (`isPrivate == false` verified on all `7/7` audited repositories; `16/16` external files + `6/6` upstream expedition certificates pinned by exact SHA-256)

---

## 1. Pillar 1 — SOP-9 Live Forensic Audit of `Foundation-0/exoplanets-frontier`

Auditing `Foundation-0/exoplanets-frontier` (`main @ 3bc0163bc04547628072aa5b281eda282347e3d1`) across **all `5` branches (`main` + `4` non-main)** and **`3` open PRs (`#13`, `#8`, `#6`) + closed `#7`** exposed `4` concrete defects and exact merge-conflict seams:

1. **Live `SyntaxError` on `main` (`cool_vet.py:2`):** Line 2 begins with two quotes instead of three (`""Vet ..."""`), causing `ast.parse` to fail with `SyntaxError: unterminated triple-quoted string literal (detected at line 115)`.
2. **Exact Conflict & Defect Matrix Across Open PRs `#13`, `#8`, `#6` (plus closed `#7`):**

| PR | State | Branch (`head_commit`) | `merge-tree main` | Conflicts With | Key Forensic Findings |
|---|---|---|---|---|---|
| `#13` | `OPEN` | `devin/1795441981-fix-cool-vet-docstring` (`1c7aef9d...`) | **`RC=0`** | `#8` (`cool_vet.py`) | Cleanest minimal 2-file fix (`"" -> """` + `if: github.ref == 'refs/heads/main'` push guard in `.github/workflows/cool_vet.yml`); keeps `max_n=14`; **`0` defects** |
| `#8` | `OPEN` | `orda-aska-patch-2` (`54671cc8...`) | **`RC=0`** | `#13` (`cool_vet.py`), `#6` (`CLAIMS.md`) | Runs live S1–S108 cool audit (`10` audited, `2` survivors: `TIC 409696823` & `TIC 224279805`, `5` quarantined blends), **BUT carries `3` live bugs:** (1) drops `max_n: 14 -> 10` while leaving stale heading `"All 14 Coolest"` in `COOL_SURVIVORS_REPORT.md` (which closed `#7` had fixed!), (2) removes branch guard via `git push origin HEAD:main \|\| git push` (`unguarded_main_push = True`), (3) commits `15` `cool_TIC*.png` cards for only `10` CSV rows (`6` orphan PNGs: `117798466`, `118244692`, `193718989`, `26432942`, `399695544`, `435255286`) |
| `#6` | `OPEN` | `aeva/issue5-evidence-boundaries-20261112` (`b9657985...`) | **`CONFLICT RC=1`** (`CLAIMS.md`) | `main`, `#8` (`CLAIMS.md`) | Branched prior to `C-08` (`33fcc6d`); rightly qualifies `C-07` provenance limits AND reproduces a genuine seeded-transit `SDE` gate failure (`17 d`: `MES=58.64`, `SDE=8.59 >= 7.5` PASS; `25 d`: `MES=49.76`, `SDE=7.23 < 7.5` FAIL — a textbook `CS-09` narrow-window truncation mirage) |
| `#7` | `CLOSED` | `orda-aska-patch-1` (`35a77f75...`) | `RC=0` | `#8`, `#13` | Fixed heading count `14 -> 10` cleanly; superseded by `#8` without carrying over the heading fix |

3. **`results/convergence_certificates.json` vs. `CLAIMS.md` SHA-256 Audit:**
   - All **`41/41`** files listed in `results/convergence_certificates.json` match their exact SHA-256 on disk on `main`.
   - However, **`3/6` inline SHA-256 prefixes quoted in `CLAIMS.md` are stale** relative to `main`'s live `results/convergence_certificates.json`: `benchmark_and_null.json` (`CLAIMS.md` `6c2a1823` vs live `2c6d4454`), `ttv_ephemeris_audit.csv` (`a81f7b1c` vs `50640b01`), and `blend_localization.csv` (`7f735d0b` vs `a73e65e1`). (`hz_issue5_audit.csv`, `eumemic_gaia_dr4_readiness.csv`, and `platinum_followup_targets.csv` match `3/3`.)
4. **Out-of-Sample `results/blind_verification_s106_s107.csv` Verification (`39` Pairs):**
   - `39` total rows = `37` covered (`n_cov > 0`) + `2` `DATA_GAP`.
   - Exact verdict breakdown across the `37` covered pairs: **`22` `CONFIRMED_ON_SCHEDULE`**, **`5` `MARGINAL_RECOVERY`**, **`1` `TIMING_OFFSET_TTV`**, **`9` `LOW_SNR_INCONCLUSIVE`**, **`0` `NON_DETECTION_4SIGMA`** (`22 + 5 + 1 + 9 + 0 = 37`).
   - `24` rows satisfy `snr >= 3.0` (`22` confirmed + `2` demoted to `MARGINAL_RECOVERY` for `cent_sig >= 3.2`), while `TIC 44669885` (S107 FFI) exhibits an inverted brightening artifact at `snr = -161/20` (`-8.05`, `LOW_SNR_INCONCLUSIVE`).
5. **Live-Verified Pipeline Bugs & Astrophysical Blind Spots for Upstream PR Remediation (`0` Pushes Executed):**
   - **Code Bugs Reproduced Live on `main`:**
     - `cool_vet.py:114–115`: **Duplicate `main()` invocation** inside `if __name__ == "__main__":` — Pass 1 quarantines `5` blends in place inside `platinum_followup_targets.csv` and writes PNGs, then Pass 2 re-runs on the mutated queue and overwrites `cool_platinum_vetted.csv`, directly root-causing `PR #8`'s `6` orphan PNGs (`15` PNGs vs `10` CSV rows)!
     - `hz_core.py:23`: `"sap": r["f"].copy()` clones detrended flux into `sap` (making SAP concordance vacuously pass) with hardcoded `"crowd": 0.92` vs `L41` `0.95`.
     - `mdwarf_hunt.py:18`: `out = np.ones_like(sap, dtype=float)` silently turns `NaN` / `<= 0` cadences into valid `1.0` flux instead of `np.nan`.
     - `cool_io.py:75`: `sde` compares fine-grid `pw_f` peak against coarse-grid background `mp_b`/`mad_b`.
     - `ttv_track.py:64–68`: `140`-trial periodogram search omits look-elsewhere penalty from `dBIC_ttv` and leaves `amp_t` unbounded.
     - `report_v3.py:30–35`: embeds wall-clock `el_s` inside SHA-256-hashed `CONVERGENCE_REPORT.md` (preventing bit-exact SHA reproduction).
   - **Astrophysical / Statistical Blind Spots Reproduced Live:**
     - **Alias Amnesty (`vetter.py:20`):** the alias veto `|P - a|/a < 0.008` fires **only when `mes_c < 15.0`**, allowing strong (`MES >= 15`) `0.5/1.0/6.85/13.7 d` TESS aliases to bypass alias rejection, while Farey resonance density exceeds the 4-value list (`1/132 < 1/125`).
     - **White-Noise-Only Blind SNR, ACF-Preserving Null, & Unresolved Close-BEB `nfpp` Collapse (`vetter.py:77,104–107`, `despot.py:71–77`):** Pont $\beta$ corrects `MES` only (never `blind_check_sector` `snr` or `FPP`); time-reversal + cyclic roll preserves the autocorrelation function (ACF), so the scrambled null tests white noise rather than red noise; and `nfpp` collapses to a flat `0.18` factor precisely when no centroid shift is detected (`csig <= 2.0` and `tpf_off <= 8"` — the Gaia DR3 unresolved `< 2–3"` close-BEB regime).
     - **Single-Epoch Blind Confirmations (`vetter.py:95–126`, `blind_verification_s106_s107.csv`):** **`4/22` `CONFIRMED_ON_SCHEDULE` rows have `n_cov == 1`** (`TIC 224279805` S106, `TIC 170788495` S106 & S107, `TIC 170638116` S106) because `blind_check_sector` lacks `vet_signal`'s `single_ev` guard and scans only `±60 min` (vs `ttv_track.py`'s `±240 min`).
6. **Recommended Clean Merge Resolution:** Land `#13` first (`cool_vet.py` syntax + `if: github.ref == 'refs/heads/main'` workflow guard), remove duplicate `main()` at `cool_vet.py:115`, rebase `#8`'s verified `2/10` cool-survivor data while pruning the `6` orphan PNGs and fixing the `14 -> 10` heading, rebase `#6` onto `C-08` in `CLAIMS.md`, refresh the `3` stale SHA-256 prefixes in `CLAIMS.md`, and patch the `6` pipeline bugs + `3` vetter blind spots above.

---

## 2. Pillar 2 — Pure-$\mathbb{Z}/\mathbb{Q}$ Exact Astrophysical Verification Operators

All quantities below are computed identically in `s103_exoplanets_oracle.py` and independently recomputed in `verify_s103_exoplanets.py` with `0` floats:

### 2.1 Two-Stage BLS Sharpening, Farey Resonance Separation & `CS-09` SDE Truncation
- **Multi-Year Resolution Sharpening (`bls_search.py`):** $T_{\text{multi}} = 2900\text{ d}$ vs. $T_{\text{stage1}} = 60\text{ d}$ sharpens frequency bins by exact ratio **`145/3`** (`48.333333`); full-baseline Nyquist count over $f \in [1/25, 100/16]\text{ d}^{-1}$ is **`36,018`** bins vs. two-stage budget **`40,000`** trials.
- **Unimodular Farey Period-Ratio Separation vs. Alias Guard `1/125` (`0.008`):**

| Farey Pair $(r_1, r_2)$ | $\det(p_2 q_1 - p_1 q_2)$ | Exact Gap `gap_q` | Decimal (`dec6`) | Collides `< 1/125` |
|---|---:|---|---:|---|
| `(1/2, 2/3)` | `1` | `1/6` | `0.166667` | `False` |
| `(2/3, 3/4)` | `1` | `1/12` | `0.083333` | `False` |
| `(3/4, 4/5)` | `1` | `1/20` | `0.050000` | `False` |
| `(4/5, 5/6)` | `1` | `1/30` | `0.033333` | `False` |
| `(5/6, 6/7)` | `1` | `1/42` | `0.023810` | `False` |
| `(10/11, 11/12)` | `1` | **`1/132`** | **`0.007576`** | **`True`** |

- **`CS-09` Narrow-Window SDE Truncation Witness (Explaining `PR #6` `25 d` Failure):** At `peak_mes = 50` (`>> 19/2`), a wide search comb (`med = 10, mad = 4`) gives **`SDE_wide = 10 >= 15/2`** (PASS), whereas a narrow seeded window (`med = 15, mad = 5`) depresses **`SDE_narrow = 7 < 15/2`** (FAIL despite `MES = 50`).

### 2.2 Pont Red-Noise $\beta$ Inflation & 8-Gate Bayes FPP Compounding (`S81`/`S87` Bridge)
- **Pont Variance Inflation:** For bin occupancy $N = 12$ and correlated noise ratio $\sigma_r / \sigma_w = 1/2$, exact $\beta^2 = 1 + 12 (1/2)^2 =$ **`4`** $\implies \beta =$ **`2`**, collapsing `raw_mes = 14 >= 19/2` to **`corrected_mes = 7 < 19/2`**.
- **8-Gate Bayes FPP vs. Law-5 Correlated-Failure Blowup ($\pi_P = 1/100$, $r = 19/20$, $\varepsilon = 1/4$, `Tier S-Val` $< 3/200 = 0.015$):**
  - `8` conditionally independent gates: exact $\mathrm{FPP}_8 =$ **`38671875/17022234916`** (**`0.002272 < 0.015`**, PASS).
  - Law-5 `4`-gate shared correlated failure ($\varepsilon_{\text{shared}} = 1/2$ replacing $(1/4)^4 = 1/256$): exact $\mathrm{FPP}_{\text{corr}} =$ **`4950000000/21933563041`** (**`0.225682 >= 0.015`**, FAIL — `128×` odds blowup).

### 2.3 Asymmetric Huber Four-Harmonic Spot Pre-Whitening (`despot.py`) & Phase-Lock Obstruction
- On the `8`-point rational orthogonal basis $(u_0, u_1, u_2, u_3)$ with starspot amplitude `10,000 ppm` on $u_1$ and `1,500 ppm` 1-bin transit at $k = 0$:
  - **Unmasked OLS:** $\det G = 1024$; recovers depth **`750 ppm`** (exact attenuation **`1/2`**).
  - **Asymmetric Huber 1-Bin Masked IRLS:** $\det G_{\setminus\{0\}} = 512 > 0$; recovers exact spot amplitude **`10,000 ppm`** and exact transit depth **`1,500 ppm`** (retention **`1`** = `100%`).
  - **Law-5 Phase-Lock Rank Collapse (`k in {0, 4}` masked):** $\det G_{\setminus\{0,4\}} =$ **`0`** (exact kernel vector $u_0 + 2 u_1 + u_3$ leaves all `6` unmasked bins identical while shifting masked transit predictions by $+4\delta$).
  - **Scrambled-Null Conservation:** Time-reversal and cyclic shift preserve exact $L^2$ energy **`3,900`** (`delta = 0`).

### 2.4 O–C TTV Orthogonal Legendre Decomposition & 2D Affine WCS Blend Triangulation
- **5-Epoch Orthogonal Legendre O–C (`E in {-2,-1,0,1,2}`):**
  - Pure linear drift $15 E$: constant $\chi^2_0 =$ **`2,250`** $\to$ linear $\chi^2_{\text{lin}} =$ **`0`**.
  - Pure quadratic decay $4 E^2$: linear residual $\chi^2_{\text{lin}} = 14 \cdot 4^2 =$ **`224`** $\to$ quadratic $\chi^2_{\text{quad}} =$ **`0`**.
  - Phase-clipping wall: $1,500\text{ orbits} \times 4\text{ s} / 60 =$ **`100 min`** (`> 60 min` Phase 1 wall, rescued by `240 min` `ttv_track.py` wall).
- **2D Affine WCS Equivariance, Dilution Cancellation & BEB Physical Exclusion (`blend_gaia.py`):**
  - Invertible 2D affine WCS map $A = \begin{pmatrix}2&1\\-1&3\end{pmatrix}$ ($\det A =$ **`7`**): exact centroid equivariance $T(\bar{p}) = \overline{T(p)}$.
  - Scene-model dilution subtraction leaves exact **`0`** residual bias on target.
  - Observed diluted depth $\delta_{\text{obs}} = 1/100$ with $F_T = 100, F_N = 1/2$ requires neighbor eclipse depth **`201/100`** (`2.010000 > 1`) $\implies$ neighbor physically excluded as BEB.
  - Proper motion `300 mas/yr` over `10 yr` (`J2016.0 -> J2026.0`) shifts coordinates by **`3 arcsec`** (`> 1.93"` / `2.04"` WCS errors on verified cool survivors).

---

## 3. Pillar 3 — SOP-10 Public Astronomy Spine & `Aletheia` Gate Convergence

All `7/7` audited repositories were verified public (`isPrivate == false`):

| Public Repository | Main Commit | Branches | Open PRs | Merged PRs | Primary Unmerged Seam / Convergence Link |
|---|---|---:|---:|---:|---|
| `Foundation-0/exoplanets-frontier` | `3bc0163bc0...` | `5` | `3` | `0` | `cool_vet.py` L2 `SyntaxError`; PR `#13`/`#8`/`#6` conflicts; `3/6` stale `CLAIMS.md` SHAs |
| `Foundation-0/astr0` | `67cafe2def...` | `7` | `4` | `2` | `4` mergeable open PRs (`#4`–`#7`) defining 5-gate calibration & KMOS verification |
| `Foundation-0/gaia-dr4` | `95629f36c2...` | `2` | `0` | `8` | ESA freeze 25 Nov 2026 $\to$ DR4 2 Dec 2026; unmerged `prep/gaia-dr4-tasks`; VizieR/MAST mirror |
| `Foundation-0/lost-eclipses` | `6fd9d059d5...` | `1` | `0` | `8` | Direct consumer of `ttv_track.py` quadratic precession O–C model |
| `Foundation-0/certified-orbits` | `f3b86e7ea7...` | `4` | `3` | `4` | `3` mergeable open PRs (`#10` exact rational Krawczyk, `#11` exact 20-row selection, `#12` fail-closed verifier audit) |
| `Foundation-0/cosmic-denoising` | `a00e2b5b82...` | `2` | `1` | `0` | Open PR `#1` (`gpt-forge/research-foundation`) establishing denoising baseline |
| `eumemic/exoplanets` | `e2eee928fd...` | `1` | `0` | `10` | Upstream `9,979` K/M-dwarf + `6,430` TOI catalog (`639` counted candidates) |

- **SOP-10 Author-Graph High-Signal Public Collisions (`eumemic/*`):** `eumemic/exact-dft-bounds` (exact DFT exponent $\theta = 1 - 607/1250000$, colliding with `S23a`/`S93`), `eumemic/integer-mult-bounds`, `eumemic/stdhttp-verify` (kernel-checked Lean `Std.Http`), and `eumemic/errata-findings`. Also observed `Foundation-0/plate-eclipses` (public scaffolding).
- **Direct `Aletheia` Gate Strengthening:** (`CS-09`) `PR #6`'s `25 d` `MES=49.76` / `SDE=7.23 < 7.5` formalizes narrow-window support-truncation mirages; (`CS-18`) blind `S106–S107` 4-state abstention (`9` `LOW_SNR_INCONCLUSIVE`, `2` `DATA_GAP`) prevents forced false rejections; (`Pont-beta`) exact variance inflation hardens correlated time-series ratchets across `S102`/`S95–S97`.

---

## 4. Pillar 4 — Pure-`Init` `Lean 4.36.0` Companion & R12 Verification Gate

- **`ExoplanetsFrontierOperators.lean`:** **`19/19` universally quantified (`∀`) pure-`Init` `Lean 4.36.0` theorems** (`16` full structural algebraic theorems — including Theorem 19 `bayes_shared_channel_fpp_monotone_and_law5_breach` proving strict FPP monotonicity in shared correlated-failure rate `eps_shared` and the exact Tier S-Val `3/200` Law-5 breach criterion `197*(piFP*e4*es2) >= 3*(piP*r8)` — plus `3` exact definitional/conservation lemmas [Thm 4 conj 1 telescoping identity, Thm 9 256-case Bool 8-gate fail-closed conjunction, Thm 13 4-block reversal/shift energy conservation]; **`0` imports, `0` ground-only, `0` hypothesis-echoing conjuncts; axioms `1 [] + 18 [propext, Quot.sound]`, `0` `Classical.choice`, `0` `sorryAx`, `0` warnings, `lean --stdin` exact, scratch `lake build` `4 jobs` PASS**).
- **`verify_s103_exoplanets.py`:** Field-complete `SEC`/`FR0`/`FR1` semantic auditor (`0` re-signed semantic bypasses across all numeric, algebraic, provenance, and narrative fields — including `unmerged_seam`, `aletheia_gate_bridges`, and upstream `bridge`; fresh deep copies from `build_certificate()` with `0` shared mutable container aliasing to module tables; `MAX_RATIONAL_STR_LEN = 162` capping rational strings against `>4300`-digit `int()` `ValueError`) + full **R12** static Lean scanner (blocking `_root_.sorryAx`, `warn.sorry`, `set_option`, `noncomputable`, `panic!`/`panicWithPos*`/`unreachable!`/`assert!`/`debug_assert!`, `dbg_trace`/`dbg_sleep`/`dbg_stack_trace`, `dbgTrace*`/`dbgTraceValId`, `dbgSleep`, `dbgStackTrace`, `@[init]`/`@[builtin_init]`/`@[export]`/`@[term_elab]`/`@[command_elab]`/`@[tactic]`/`@[macro]`/`@[macro_rules]`, `declare_syntax_cat`, `macro_rules`, `elab_rules`, `#guard`, `bv_decide`, `decide +revert +native`, multiline `decide (native := ...)`, `config := { native }`, `0` FP on clean controls including `decide (config := { native := false })`, `export Nat (succ)`, `attribute [simp] init_eq`) + zero-TOCTOU `lean --stdin` with strict allowlist subprocess environment (`PATH`/`HOME`/`USER`/`LOGNAME`/`TMPDIR`/`LANG`/`LC_ALL`, blocking `LEAN_*`/`ELAN_*`/`LAKE_*`/`LD_PRELOAD`/`LD_LIBRARY_PATH`, verified live against forged `Init.olean` hijack) + `82/82` direct 4-surface v2.1 ZBF + `100.0%` `aletheia-fast-mutate` + `100.0%` whole-file DFS AST `BoolOp` + `0`-skip dual-environment CI + dual `audit-check PASS ×2`.

---

## 5. Frozen Companion Artifact Manifest (`7` Companion Files + `REPORT.md` Hashed Externally)

| File | Lines | Bytes | Mode | SHA-256 |
|---|---:|---:|:---:|---|
| `ExoplanetsFrontierOperators.lean` | `436` | `23,248` | `0o644` | `6359ee54c2e7fc8592f06b75a419177193fe799df6a6f3ad2427e8d6bb247c55` |
| `lakefile.toml` | `5` | `137` | `0o644` | `6a85b227f6e78d9f85f37940df54bc36acd92e64ca57d6f8404caae67c1bf51b` |
| `lean-toolchain` | `1` | `25` | `0o644` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |
| `s103_exoplanets_oracle.py` | `834` | `34,229` | `0o644` | `c3475601a8329f8a1a869a78e5c16b55dd89a5a20aaa46d6f2bd2c8ebc4d7fc6` |
| `verify_s103_exoplanets.py` | `947` | `49,105` | `0o644` | `4badebb533f7a656dac9de63b4c9e04ef94159e711c93b215b73bc1d8f56264e` |
| `test_s103_exoplanets_r5.py` | `908` | `63,358` | `0o644` | `806bd8b4b5a576a498dc73848ade729de09bcdbad2d514eed1d69a180f5fca0e` |
| `s103_exoplanets_certificate.json` | `1` | `14,992` | `0o644` | `bfd79ee0ba84d83ac0a1c548a43175a9056b4c10cd62c37ebc0bf3f4e85d6397` |

*(Note: `s103_exoplanets_audit.py` and `README.md` provide `evidence-tracks` CI discovery and documentation alongside the core bundle above. Certificate internal hashes: `payload_sha256 = 2953651ac77d2e2e86df4474e9bc64114d849fc664c2fd7e4e541990246ae645`, `certificate_sha256 = 9249b9ddd1f5a231912ce3fc7ade021a56fcecf8b9e569e3c9876756cd7f4cce`.)*
