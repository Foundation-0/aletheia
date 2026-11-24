# Domain-Agnostic CEER Engine (`aletheia ceer`) — Technical Report

## 1. Overview & Architecture

The **Calculational-Experimental Epistemic Recursion (CEER)** engine implements a reusable, domain-agnostic, pure-$\mathbb{Z}/\mathbb{Q}$ and pure-`Init` Lean `4.36.0` primitive for closed-loop formal theory refinement:

$$\text{Formal Theory } T_k \;\longrightarrow\; \text{Pre-Registered Held-Out Levers } \mathcal{U}_k \;\longrightarrow\; \text{Exact } \mathbb{Z}/\mathbb{Q} \text{ Adjudication} \;\longrightarrow\; \text{Lean 4 Proof / Disproof} \;\longrightarrow\; \text{Obstruction Lift } T_{k+1}.$$

The module has **zero external Python dependencies**, **zero floating-point literals or arithmetic** in all production and test ASTs, **zero bare `assert` statements**, and **zero Mathlib dependencies** in synthesized Lean 4 proof certificates:

- **`ceer_engine.py`** (`839` L): Typed `CEERCycle` state machine (`commit_preregistration` with full per-kind prediction schema/type validation, pre-`int()` rational digit-cap enforcement in `parse_q`, `adapt_external_sensor_cycle`, `evaluate_cycle` with fail-closed observation/prior-cycle validation, `build_self_demo_cycles`) plus five exact pure-$\mathbb{Z}/\mathbb{Q}$ adjudication operators:
  1. `eval_linear_scaling`: exact cross-multiplied linear response test within rational tolerance $\varepsilon \in \mathbb{Q}_{\ge 0}$.
  2. `eval_concave_second_diff`: exact integer divided second difference $\Delta^2 = (y_2 - y_1)(u_1 - u_0) - (y_1 - y_0)(u_2 - u_1) < 0$.
  3. `eval_schur_dark_drop` / `compute_normalized_schur_eta_q`: exact rational Gauss-Jordan Schur complement $S = G_{AA} - G_{AB} G_{BB}^{-1} G_{BA}$ with per-channel normalized residual $\bar{\eta}$ and verified Stage-A coordinate-permutation + independent positive rational affine gauge invariance ($\text{deviation} = 0$).
  4. `eval_hysteresis_loop`: exact discrete signed Green/Shoelace twice-area $2\mathcal{A}_{\text{loop}} = \sum_t (y_{t+1} + y_t)(x_{t+1} - x_t) \in \mathbb{Z}$.
  5. `eval_rational_enclosure`: exact cross-multiplied interval enclosure $L_k \le n_k / d_k \le U_k$ on held-out rational observations.
- **`ceer_lean4_synth.py`** (`636` L): Deterministic pure-`Init` Lean `4.36.0` certificate synthesizer (`synthesize_cycle_lean4`), hardened $O(n)$ static anti-bypass gate (`scan_lean4_trust_escapes` — supporting Lean 4 `Char` literals including `\xHH`/`\uHHHH` escapes guarded against identifier primes `_'»!?`, French-guillemet `«...»` lexical state blanking non-identifier interiors while normalizing plain guillemet identifiers, raw strings `r"..."`/`r#"..."#`, interpolated strings `s!"..."`/`m!"..."`/`f!"..."` with unterminated interpolation-brace rejection, fail-closed plain-record-literal allowlist on `(config := <expr>)` including field punning `{ native }`, inline `{ native := ... : DecideConfig }`, custom `:+`/`,+` infix operators, `Lean.trustCompiler`/`mkSorry`/`ofReduceBool`/`ofReduceNat`, glued `#eval`/`#eval!`/`#reduce`/`#exit`/`run_cmd`/non-`#print axioms <ident>` command blocking, and module-aware external `import` blocking), and live `lean` compiler verifier (`verify_lean4_source_live`) failing closed on non-empty `stderr`, compiler warnings, or unexpected `stdout` while enforcing a strict multiline-aware `#print axioms` allowlist $\subseteq \{\text{propext}, \text{Classical.choice}, \text{Quot.sound}\}$.
- **`ceer_audit.py`** (`614` L): Independent hardened auditor and CLI (`--standalone`, `--write`, `--check`, `--emit-lean-dir`, `--verify-lean`) featuring iterative depth/digit-bounded strict JSON validation (`MAX_JSON_DEPTH=64`, `MAX_INT_DIGITS=1000`, `allow_nan=False`), non-blocking symlink/hardlink/inode-verified I/O (`O_NOFOLLOW | O_NONBLOCK`, `st_nlink == 1`, wrapped `os.getcwd()`, `(st_dev, st_ino)` `$PWD` parity, root-owned macOS `/var`/`/tmp`/`/etc` prefix normalization, CSPRNG-suffixed atomic `0o600` writes with unified temp cleanup, short-write guard, and wrapped `os.replace`), domain-agnostic chain verification (`verify_cycle_chain_integrity`), and full canonical-byte secondary audit (`secondary_audit_payload`).

## 2. Fail-Closed Epistemic Invariants

- **Cryptographic Pre-Registration Latch:** `commit_preregistration(prereg)` returns `SHA-256(canonical_json_bytes(prereg))` before any experiment executes; `evaluate_cycle` rejects digest mismatches with `CEER_PREREG_MISMATCH`.
- **Strict Out-of-Sample Disjointness:** For every cycle $k \ge 1$, `train_levers` must contain all previously evaluated lever tuples and `eval_levers ∩ train_levers == ∅`, refusing in-sample reuse fail-closed with `CEER_INSAMPLE_LEAK`.
- **Obstruction-Lift Continuity:** Every cycle $k \ge 1$ must bind `prior_cycle_sha256` to cycle $k - 1$'s exact `cycle_sha256` AND cite a `prior_obstruction_code` present in cycle $k - 1$'s `falsified_predicates` (refusing static or disconnected loops with `CEER_BROKEN_CHAIN`).
- **Pluggable External Sensor Adapter:** `adapt_external_sensor_cycle(...)` validates and normalizes external raw integer sensor dictionaries (e.g., RAPL/coretemp/fan tables) directly into `evaluate_cycle`, `verify_cycle_chain_integrity`, and `synthesize_cycle_lean4`.

## 3. Built-In 3-Cycle Self-Demo & Live Lean `4.36.0` Receipts

| Cycle | Theory ID | Held-Out Levers | Verdict | Exact Pure-$\mathbb{Z}/\mathbb{Q}$ Witnesses | Lean `4.36.0` File & Theorems (`#print axioms`) |
|---:|---|---|---|---|---|
| `0` | `T0_LINEAR_SINGLE_VALUED` | `[[1,16],[2,256],[4,4096]]` | **`FALSIFIED`** (`0/3`) | `H0_LINEAR_CORE`: rel err `23/90 > 1/20`; `H0_FLAT_DARK_MODE`: dark drop `22831526435029672/22832393395803255 > 1/10` (gauge dev `0`); `H0_ZERO_HYSTERESIS`: $2\mathcal{A} = -20,650,000 \neq 0$ | `CEER_Cycle0_Verdict.lean` (`3/3` disproofs, `[]` zero axioms) |
| `1` | `T1_CONCAVE_SCHUR_SINGLE_BRANCH` | `[[3,8192],[6,32768],[8,65536]]` | **`FALSIFIED`** (`2/3`) | Lifted `H0_LINEAR_CORE`: `H1_CONCAVE_POWER` $\Delta^2 = -7,900 < 0$ (`PASS`); `H1_SCHUR_DARK_COUPLING` drop `1197145919941037/1198444136342720 >= 1/2` (`PASS`, gauge dev `0`); residual `H1_ZERO_HYSTERESIS` $2\mathcal{A} = -12,800,000 \neq 0$ (`FAIL`) | `CEER_Cycle1_Verdict.lean` (`2` corroborations + `1` disproof, `[]` zero axioms) |
| `2` | `T2_HYSTERETIC_SCHUR_CLOSURE` | `[[5,16384],[7,49152],[9,98304]]` | **`CORROBORATED`** (`4/4`) | Lifted `H1_ZERO_HYSTERESIS`: `H2_CONCAVE_POWER` $\Delta^2 = -4,800 < 0$; `H2_SCHUR_DARK_CLOSURE` drop `23990531652701503/24010610426563072 >= 1/2` (gauge dev `0`); `H2_HYSTERETIC_LOOP_AREA` $|2\mathcal{A}| = 10,200,000 \ge 5,000,000$; `H2_RATIONAL_ENCLOSURE` `3/3` enclosed | `CEER_Cycle2_Verdict.lean` (`4/4` corroborations, `[]` zero axioms) |

- **Compiler:** `Lean (version 4.36.0, x86_64-unknown-linux-gnu, commit 611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9, Release)`
- **Axiom Footprint:** All **`10/10`** theorems across `CEER_Cycle0_Verdict.lean`, `CEER_Cycle1_Verdict.lean`, and `CEER_Cycle2_Verdict.lean` compile cleanly (`rc = 0`, `0` warnings) and report **`does not depend on any axioms` (`[]`)**.
- **Certificate Digests (`ceer_engine_certificate.json`, `0o600`):**
  - `file_sha256`: `8e8daa35e2fbf2a154546e584a9ffe444031a354264d8997570483954fb526c9`
  - `payload_sha256`: `f4bc02b70d05e3d9bbd25d3681e5ec0cfc57ad123430629f55eb8e3f5dac2f56`
  - `certificate_sha256`: `7b78a89dee35cbb60817a23e8690775ace5f6bdf7cc4638b501dc891d3eafb92`

## 4. Verification Summary

- **R4 Isolated Execution Parity (`-I -B`, `-I -O -B`, `-I -B -W error`) + `PYTHONHASHSEED=42 -B` + `umask 077`:**
  - `ceer_audit.py` (zero-arg & `--standalone --json`): bit-identical `8e8daa35e2fbf2a154546e584a9ffe444031a354264d8997570483954fb526c9` matching `ceer_engine_certificate.json`
  - `ceer_audit.py --check ceer_engine_certificate.json --json`: bit-identical `ab2f6db0926e84f5e1d0361b119e06da9b42ade91c8f033fcef36c4a415dd95f`
  - `test_ceer_engine_r5.py`: **`9/9 OK`** across all modes and under `umask 077`
- **Adversarial Surface Fuzzing (`zone_b_fuzzer`, 4 surfaces):** **`82/82 PASS`** (`25/25` CLI, `19/19` `full_replay=True`, `19/19` `full_replay=False`, `19/19` direct `secondary_audit_payload`; `bypasses = 0`, `crashes = 0`).
- **Live Mutation Gate (`aletheia mutate --guards require_ok --workers 4 --timeout 180 --max-mutants 0`):** **`194/194` (`100.0%`, `survived = 0`, `timeout = 0`, `truncated = False`, `PASS`)** across `ceer_engine.py` (`87/87`), `ceer_lean4_synth.py` (`27/27`), and `ceer_audit.py` (`80/80`).
- **Whole-File AST Boolean-Operator Sweep (Operator Swap + Subcondition Deletion, Null-Mutant Verified):** **`280/280` (`100.0%`, `86` nodes, `survived = 0`)** across `ceer_engine.py` (`96/96`), `ceer_lean4_synth.py` (`140/140`), and `ceer_audit.py` (`44/44`).
- **Hardened `aletheia audit-check --lean-audit --strict-ancestors --safety-scan --scripts ceer_audit.py test_ceer_engine_r5.py`:** **`PASS`** (`2/2` R4 scripts, `3/3` Lean files clean, `0` findings, `0` notices, `0` CRLF, `0` bare `assert`s, `0` AST float literals, `0` `.isdigit()` calls, `0` leaks).

## 5. Frozen Artifact Manifest

| File | Lines | Bytes | Mode | SHA-256 |
|---|---:|---:|:---:|---|
| `ceer_engine.py` | `839` | `37,188` | `0o644` | `9c61cdefa2a27f4b955cb4298e5aca934e383e0ac996d0d819856d6cff815f18` |
| `ceer_lean4_synth.py` | `636` | `25,882` | `0o644` | `8cc4c8a7a3a285cd4ac6ab0c29554a9a716884ffd95b7c106976142e69c5ab91` |
| `ceer_audit.py` | `614` | `25,538` | `0o644` | `3f1776f817be775b77238734bbb4914d8df2bb619d18f85e8adbd2d49787d016` |
| `test_ceer_engine_r5.py` | `1,056` | `71,292` | `0o644` | `ffbc2019b8ae4fb64657a63fc5c9968efde52b87b096eed96cfea7df8fc68235` |
| `CEER_Cycle0_Verdict.lean` | `25` | `1,100` | `0o644` | `3e4abcb55f8ac48333ba225636096cf4f6d144d76047af4b6f71bf4305068e2b` |
| `CEER_Cycle1_Verdict.lean` | `25` | `1,161` | `0o644` | `c202ec9af325d52fd07372d76e019a98d9156115b31a103fa57e5934f1afc525` |
| `CEER_Cycle2_Verdict.lean` | `27` | `1,502` | `0o644` | `d5c303dcde5ed11292cdc8dc7219561681bb2fce89be811c73a54eaa54355878` |
| `ceer_engine_certificate.json` | `1` | `10,347` | `0o600` | `8e8daa35e2fbf2a154546e584a9ffe444031a354264d8997570483954fb526c9` |
