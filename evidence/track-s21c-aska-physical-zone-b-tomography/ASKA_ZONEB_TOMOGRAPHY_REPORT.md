# Track S21c — Cross-Org `aska-physical` Zone-B, `NaN`-Swallowing & `-O` Bare-`assert` Tomography

- **Track ID:** `TRACK-S21C-ASKA-PHYSICAL-ZONE-B-TOMOGRAPHY`
- **Oracle Class:** `pure-Z/Q-ast-tomography+zone-b-hardened` (Python 3 standard library only: `ast`, `fractions.Fraction`, `hashlib`, `hmac`, `json`, `os`, `pathlib`; **zero IEEE-754 floats**, **zero external dependencies**, **zero bare `assert`s**, **zero RNG**)
- **Law-4 Novelty Accounting:** `N1` cross-org systematic static AST + live-reproduction tomography over all `9` public engineering repositories of `aska-physical` (`isPrivate: false` verified live on every repo), cross-pollinating the `FR3-NEW-01` (`max(0.0, NaN) == 0.0`) discovery and `Track S19c` (`ZB01`..`ZB16`) Zone-B adversarial corpus.

---

## 1. OWN_TERMS_FIRST — Problem Statement, Exact Exposure Matrix & Scope Boundary

Every public engineering repository in `aska-physical` ships a standalone verification script (`verify.py`, or `results/track-1-flexure/verify.py` + `src/flexure440.py` in `cfrp-strengthening`) that recomputes structural/thermal/electrical checks and compares them against a committed JSON certificate. We audited all **`9` public `aska-physical` engineering `main` branches** across **four orthogonal verification-trust defect families**:

1. **`F1_BARE_ASSERT_O_STRIP`:** Bare `assert` statements on verification trust paths (silently stripped under `python3 -O`).
2. **`F2_NAN_SWALLOW_MAXMIN`:** Unchecked Python built-in `max(...)` / `min(...)` calls on float demands, capacities, margins, or residuals — in Python, `max(c, float("nan")) == c` and `min(c, float("nan")) == c` whenever the finite bound `c` is the first argument (or accumulator), silently converting `NaN` into a finite passing value.
3. **`F3_ZONEB_CERT_DICT_EQ`:** Parsed-dict equality (`json.loads(...) != cert`, `read_json(...) != cert`, `saved != cert`, `fresh != saved`), which silently accepts `ZB06` (`true`/`false` replaced by `1`/`0`), `ZB07` (duplicate JSON keys), `ZB08` (`int` replaced by `.0` float), `ZB10` (CRLF/non-canonical JSON), and `ZB14` (symlinked certificate files).
4. **`F4_ZONEB_UNGUARDED_JSON_IO`:** Unguarded `json.loads` / `json.load` calls lacking fail-closed `(OSError, UnicodeDecodeError, ValueError)` handling, crashing with raw Python tracebacks on `ZB03` (5,000-digit integer `ValueError`), `ZB15` (directory `IsADirectoryError`), and `ZB16` (invalid UTF-8 `UnicodeDecodeError`, truncated JSON `JSONDecodeError`).

### Exact Cross-Org Exposure Table — DATED HISTORICAL AUDIT of the pinned Nov 11–17 snapshot (NOT live `main`; see the remediation note below)

| Repository (`isPrivate=false`) | Pinned HEAD (Nov 11–17) | Checker File(s) & SHA-256 (prefix) | `F1` Asserts | `F2` `max/min` (`const-1st`) | `F3` Dict Eq | `F4` Unguarded JSON | Live Verification Surface |
|---|---|---|---:|---:|---:|---:|---|
| `fibral-rigidity` | `06520520dff2` | `verify.py` (`750182ff...`) | `28` | `4` (`0`) | `1` | `3` | AST + live non-SymPy `NaN` repro |
| `cfrp-truss` | `3c11631e223b` | `verify.py` (`77d0df43...`) | `7` | `36` (`14`) | `1` | `1` | AST + live non-SymPy `NaN` repro |
| `cfrp-masts` | `a12b665f2baf` | `verify.py` (`2dc0bc54...`) | `5` | **`0`** (`0`) | `1` | `1` | Live subprocess Zone-B (`4` bypasses, `4` crashes) |
| `cfrp-strengthening` | `3f68cccf1955` | `results/track-1-flexure/verify.py` (`fe082e2c...`), `src/flexure440.py` (`77583629...`) | **`0`** | `5` (`1`) | `2` | `5` | Live subprocess Zone-B (`5` bypasses incl. `DATE_ECHO_FORGERY`, `4` crashes) |
| `funi-floors` | `00eba18ceea0` | `verify.py` (`274d87ce...`) | `5` | `7` (`6`) | `1` | `1` | AST + live non-SymPy `NaN` repro |
| `funi-frame` | `97b326d237de` | `verify.py` (`cef9e47d...`) | `7` | `2` (`2`) | `1` | `1` | AST + live non-SymPy `NaN` repro |
| `impedence-analyzers` | `ed0a5e10e87e` | `verify.py` (`c1bd1f45...`) | `9` | `7` (`4`) | `1` | `1` | Live subprocess Zone-B (`4` bypasses, `4` crashes) + `NaN` `TypeError` |
| `venturi-collars` | `d53f85a35d17` | `verify.py` (`4d3ef709...`) | `5` | `1` (`1`) | `1` | `1` | Live subprocess Zone-B (`5` bypasses incl. `ZB08`, `4` crashes) + `-O` `NaN` repro |
| `optifab` | `74d68ea15ab7` | `verify.py` (`e1a898de...`) | `20` | `14` (`1`) | `2` | `3` | AST + live non-SymPy `NaN` repro (`ball_in_box` & `plant_radius`) |
| **Total (`9` repos)** | — | **`10` Python files + `9` certs** | **`86`** (`8/9`) | **`76`** (`29` const-1st, `8/9`) | **`11`** (`9/9`) | **`17`** (`9/9`) | **`34/36 = 17/18`** exposure cells at the pinned snapshot (`94.44%`) |

> **Remediation status (reviewed 2026-11-25):** between Nov 22–24 CT, all `9` repos merged fixes touching these families on their live `main` (partial: see the 9/36 residual below) — e.g. funi-floors `dac97fc`, cfrp-masts `ba3221c`, cfrp-strengthening `e4f3ed5`, venturi-collars `5891060`, fibral-rigidity `f56ae83`, cfrp-truss `1f0b662`, impedence-analyzers `e3e1073`, optifab `67cabe6` (PR #16), funi-frame `d3e3cb6`. Re-scanning current `main` with this PR's own scanner definitions (reviewer rescan, 2026-11-25 — not reproduced by this bundle) gives **9/36 exposed (upper bound; F2 counts any builtin max/min)** — F1 0/9, F2 3/9, F3 3/9, F4 3/9. The table above is therefore a dated historical audit of the pinned snapshot, not a live-main claim.

- **Exact Pure-$\mathbb{Q}$ Prevalence & Density (at the pinned snapshot):** `F1 = 8/9`, `F2 = 8/9` (`7/9` const-first), `F3 = 1` (`9/9`), `F4 = 1` (`9/9`). Across `9 x 4 = 36` repo-family cells, **`34/36` (`17/18`)** were exposed and only **`2/36` (`1/18`)** were clean at the pinned heads: `(cfrp-strengthening, F1)` and `(cfrp-masts, F2)`. On live `main` today the residual is `9/36` (upper bound; reviewer rescan 2026-11-25, not reproduced by this bundle) after the Nov 22–24 remediation commits listed above. Every single repo (`9/9`) exhibited `>= 3` families, and **`7/9`** exhibited all `4/4` at the pinned snapshot.

### Explicit Scope Boundary (Law-4 Honesty)
- `5/9` repos (`fibral-rigidity`, `cfrp-truss`, `funi-floors`, `funi-frame`, `optifab`) import `sympy` at top level (`sympy` is absent on this clean-room audit host). On those `5`, AST tomography, SHA-256 verification, and non-SymPy function-level live `NaN` reproductions were run directly; on the `4/9` stdlib/NumPy-only repos (`cfrp-masts`, `cfrp-strengthening`, `impedence-analyzers`, `venturi-collars`), full end-to-end subprocess Zone-B fuzzing was additionally executed (`18/18` live bypasses and `16/16` raw traceback crashes confirmed).
- In `--standalone --json` mode, `aska_zoneb_tomography_audit.py` replays the pinned 9-repo snapshot alongside live AST execution on the `7`-snippet `MINIMAL_REPRO_CORPUS` (explicitly tagged `"audit_mode": "pinned_snapshot_plus_live_ast_repro_corpus"`). Live disk extraction against cloned repos is performed explicitly via `--live-dir <snap_root>` (verified `9/9` against fresh read-only `main` clones before cleanup).

---

## 2. Minimal Defect Witnesses (reproduced live at the PINNED heads; all fixed on current `main` — historical witnesses, not live ones: W1 now raises `ValueError fc_MPa must be finite`, W2 `ValueError u0 must be finite`, W3 `CheckFailure U_duct_m_s must be finite`, with and without `-O`)

1. **`aska-physical/funi-floors` (`verify.py:178`) — `NaN` Concrete Strength Passes the Binding Campus Margin:**
   - Calling `evaluate_punching_shear_collar(fc_MPa=float("nan"))` evaluates `min(35.0, fc_MPa) == 35.0`, returning `phi_Vn_active_collar_kN = 2756.4`, `utilization_active_collar = 0.8009`, and **`active_collar_passes = True`** (the exact binding margin governing `optifab`'s `R* = 0.1989` plant radius!).
2. **`aska-physical/optifab` (`verify.py:311, 332-336`) — `NaN` Margin Admitted by `ball_in_box_check` & Ignored by `plant_radius`:**
   - Passing `u_nan = [0.1791, float("nan"), ...]` into `ball_in_box_check(u_nan, 0.1989)` evaluates `max(axis, worst) <= 1.0` to **`all_within_limits = True`** (because `u0[0]` is finite, `max()` silently drops `NaN`!). Likewise `plant_radius(margins_nan)` returns **`plant_radius = 0.1989`, `binding = "m6"`**, ignoring the `NaN` margin. *(Note: `contract_check()` at `L626` properly checks `all(map(math.isfinite, ...))` first — only `plant_radius`, `ball_in_box_check`, and `L676` omit it.)*
3. **`aska-physical/venturi-collars` (`verify.py:55, 69, 89`) — `NaN` Duct Velocity Generates `0.9244 mW` Under `python3 -O`:**
   - Calling `evaluate_venturi_collar(0.20, 0.64, 7.0, float("nan"), hybrid_em_coil=True)` under `-O`: `L55` (`U_throat <= U_crit_throat`) fails open (`False`), `L69` (`min(0.0040, 0.0026 * nan)`) clamps `tip_amp_m = 0.0040 m`, and `L89`'s bare `assert` is stripped by `-O`, returning **`P_total_harvested_mW = 0.9244 mW`** (`11.55x` sensor demand!).
4. **`aska-physical/fibral-rigidity` (`verify.py:206-207`) — `NaN` Stiffness Entry Silently Passes `err < 1e-11`:**
   - Planting `C_mat[0, 1] = float("nan")` produces `max(abs(C[0,0]-c11), nan, 0.0) == 1.6315e-16 < 1e-11` (`True`), and `max_err = max(max_err, err)` drops `NaN` whenever `max_err` is finite.
5. **`aska-physical/cfrp-truss` (`verify.py:119, 276-277`) — `NaN` Pryout Demand Zeroed to `0.0` & `NaN` Concrete Strength Clamped to `beta1 = 0.85`:**
   - `evaluate_aci318_ch17_anchor_group(..., theta_deg=90.0, F_horiz_ult_kN=float("nan"), F_horiz_sus_kN=0.0)` swallows `V_pry = nan` at `L276` (`max(0.0, nan) == 0.0`), reporting **`interaction_5_3 = 0.0`**; at `L119`, `max(0.65, min(0.85, nan)) == 0.85`.
6. **`aska-physical/cfrp-strengthening` (`results/track-1-flexure/verify.py:160`) — `DATE_ECHO_FORGERY` (`rc=0`) + `flexure440.py:109` `beta1(nan)=0.65`:**
   - Line `160` passes `saved["date"]` straight into `fresh = build(saved["date"])`, so tampering `"date": "9999-99-99"` in `certificate.json` exits **`0` (`RESULT: PASS`)**.
7. **`aska-physical/impedence-analyzers` (`verify.py:55, 65`) — Uncaught `TypeError` on `NaN` Measurement:**
   - `fit_cole_with_artifact_gate(freqs, z_with_nan)` fails every `cost < best_cost` comparison, leaving `p = None` and crashing at `L55` with `TypeError: cannot unpack non-iterable NoneType object`.
8. **All `9/9` Repos (`F3` & `F4`) — Zone-B Certificate Bypasses & Raw Traceback Crashes:**
   - Live subprocess fuzzing on all `4/4` non-SymPy repos (`cfrp-masts`, `cfrp-strengthening`, `impedence-analyzers`, `venturi-collars`) confirmed `4/4` silent `rc=0` bypasses on `ZB06` (`true/false -> 1/0`), `ZB07` (duplicate keys), `ZB10` (CRLF), `ZB14` (symlink cert), plus `ZB08` (`int -> float`) on `venturi-collars` and `DATE_ECHO_FORGERY` on `cfrp-strengthening`; and `4/4` raw traceback crashes on `ZB03` (5,000-digit int), `ZB15` (directory), `ZB16` (invalid UTF-8 & truncated JSON).

---

## 3. Law-2b Transformational Steelman — 3-Primitive Zero-Exposure Micro-Shim

Exhaustive search over all $2^3 - 1 = 7$ non-empty subsets of three stdlib primitives yields a unique minimal hitting set of size **`3`** closing **`34/34` (`100.0%`)** org-wide exposures at the pinned snapshot (`0/36` residual). *Scope note:* the "uniqueness" is by construction — the three `SHIM_PRIMITIVES` cover disjoint family sets (`{F1}`, `{F2}`, `{F3, F4}`) and all four families are active, so only the full set can cover them; and the "`34/34` closed" figure is checked on the shim snippet in `MINIMAL_REPRO_CORPUS`, not on any upstream repo. It is a coverage statement about the shim, not an independent proof over repo code:

1. `require_no_assert` (`if not ok: raise RuntimeError(msg)`) -> closes **`F1`** (`8/34 = 4/17` of exposed cells, `86` sites).
2. `strict_finite_clamp` (`require(math.isfinite(x))` before clamp/aggregation) -> closes **`F2`** (`8/34 = 4/17` of exposed cells, `76` sites).
3. `verify_canonical_cert_bytes` (non-symlink regular-file check + `try/except OSError` + `hmac.compare_digest(raw, rendered_bytes)`) -> simultaneously closes **`F3` & `F4`** (`18/34 = 9/17` of exposed cells, `28` sites).

Running `scan_python_source_exact` live on the `law2b_hardened_micro_shim` reference implementation in `MINIMAL_REPRO_CORPUS` certifies exact **`(0, 0, 0, 0, 0)`** counts across all four families.

---

## 4. Verification, Mutation, Zone-B Hardening & Frozen Manifest

- **Live Disk Cross-Check (`--live-dir <9-repo snap>`):** `live_verified: true`, **`9/9`** repos verified bit-for-bit on file SHA-256s, cert SHA-256s, and AST counts prior to snapshot cleanup (`S21C_SNAP_LEFT=0`).
- **Isolated `-I` & Hash-Seed Parity (`-I -B`, `-I -O -B`, `-I -B -W error`, `PYTHONHASHSEED=42 -I -B`):**
  - `aska_zoneb_tomography_audit.py --standalone --json` matches `aska_zoneb_tomography_certificate.json` byte-for-byte across all `4` runs (`payload_sha256: 6bdea899a68832fc36e8651872c228c6225cae10eb300149f59dd030fcbf8aa0`, `certificate_sha256: 85aed4f7f901f430a39ef36b0acd9ae63710af8b1e3bbdd55fd7c4dbfc79bc4f`).
  - `--check aska_zoneb_tomography_certificate.json`: `valid: true` × 4; `test_aska_zoneb_tomography_r5.py`: **`5/5 OK`** × 4.
- **Live `aletheia mutate --guards require_ok --max-mutants 0 --work-root . --add-cwd` (`-I -O -B -W error`, track test as test-cmd; re-run at review time on main `214cff65`):**
  - `aska_zoneb_tomography_oracle.py`: **`36/36` (`100.0%`, `survived=0`, `truncated=False`, null mutant PASS) KILLED**.
  - `aska_zoneb_tomography_audit.py`: **`42/42` (`100.0%`, `survived=0`, `truncated=False`, null mutant PASS) KILLED**.
  - **Combined:** **`78/78` (`100.0%`) KILLED**.
- **Exhaustive AST `BoolOp` (`and` <-> `or`) Sweep (`-I -O -B -W error`):**
  - `aska_zoneb_tomography_oracle.py`: **`21/21` (`100.0%`, `survived=[]`) KILLED**.
  - `aska_zoneb_tomography_audit.py`: **`7/7` (`100.0%`, `survived=[]`) KILLED**.
  - **Combined:** **`28/28` (`100.0%`) KILLED**.
- **Live `Track S19c` Zone-B Adversarial Fuzzer (`zone_b_fuzzer.py`, `ZB01`..`ZB16`):**
  - CLI surface (`--target-cli aska_zoneb_tomography_audit.py`): **`23/23` `REJECTED_CLEAN`** (`bypasses=0, crashes=0`).
  - In-memory surface (`verify_certificate_dict`): **`18/18` `REJECTED_CLEAN`** (`bypasses=0, crashes=0`).
  - **Combined:** **`41/41` (`100.0%`) `REJECTED_CLEAN`**.
- **`aletheia v2.0.0 audit-check . --strict-ancestors --safety-scan --scripts aska_zoneb_tomography_audit.py test_aska_zoneb_tomography_r5.py`:** **`PASS`** (`5` files, `2/2` R4, `0` bare asserts/CRLF/pycache/leaks/safety).

### Frozen File Manifest (excluding self-hash of this report)

| File | Lines | Bytes | SHA-256 |
|---|---:|---:|---|
| `aska_zoneb_tomography_oracle.py` | `721` | `30,088` | `72209635798ea5ef6cd26db4413fc747cd8a1f2135308341d71a6f2e71594676` |
| `aska_zoneb_tomography_audit.py` | `264` | `10,279` | `497fde3afaa06ed4a68ca266b4466d636b229eafb5b4c6fcd5cc4a57745af113` |
| `test_aska_zoneb_tomography_r5.py` | `520` | `26,271` | `aee100a0c13b9c11b253ebbd5e502d29288d5a6846a224c521e091fcaae683fe` |
| `aska_zoneb_tomography_certificate.json` | `1` | `11,276` | `8ef522a8d014ce58dc1f7e95d57a4855e600415d15bc0591a2844aa35427f497` |
| `ASKA_ZONEB_TOMOGRAPHY_REPORT.md` | — | — | Verified in handoff receipt |
