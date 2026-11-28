# Track S168 (`EXP-Q56a`): Aletheia Velocity Engine — Shared `trust_core`, 2-Second `preflight`, and Exact Lossless `fast_mutate`

- **Certificate Schema:** `s168.q56a.aletheia_velocity_certificate.v2` (Delta-5 Hardened)
- **Oracle Class:** `exact` (pure arbitrary-precision $\mathbb{Z}/\mathbb{Q}$, stdlib-only Python, zero floats on trust paths, zero bare asserts)
- **Novelty Classification:** `N1` (engineering acceleration & formal exactness proofs over the Aletheia verification stack; `0` fabricated claims, `CPU-only`, `0` `.lake/` / `__pycache__/` / symlink residue)
- **Lean 4.36.0 Formalization:** `VelocityBounds.lean` (`leanprover/lean4:v4.36.0`, `370` total lines / `340` non-empty lines, `14/14` public pure-`Init` theorems audited via `#print axioms`: `2` `[]`, `1` `[propext]`, `11` `[propext, Quot.sound]`; `0` `Classical.choice`, `0` `sorry`, `0` warnings, `0` external dependencies)

---

## 1. Executive Summary & Measured Problem

Forensic analysis of multi-round Wave-22 external audits across `S161`, `S163`, `S164`, `S165`, `S166`, and `S167` showed two structural bottlenecks causing `2.5–4 hour` certification loops:
1. **Repeated Zone-B / Lean / Provenance Boilerplate (>70% of multi-round failures):** Tracks repeatedly re-implemented `--write` path walking (`O_NOFOLLOW` + `st_nlink == 1` + `O_EXCL` + `os.replace`), recursive exact-type JSON equality (`bool == int` key & value spoofs), strict UTF-8 tool capture (`UnicodeDecodeError` `RC=1`), empirical `results.json` freshness/engine-SHA binding (exact keysets, RO provenance flags, fixture & permutation invariants), prose-vs-Lean theorem citation parity, scientific-notation `10^k` parity, and Lean 4.36.0 static+live hardening (dual-projection Init-only interpolation `s!`/`f!`/`println!` with nested arg-macro tracking across `s!"..."`/`r#"..."#`/`'c'` and `*At` prefixes `throwErrorAt`/`logInfoAt`/`logWarningAt`/`logErrorAt`/`logAt`, `Lean.Elab`/`Lean.Meta`, `macro`/`macro_rules`/`elab`/`syntax`/`notation`, `decide (config := ...)` / `decide (native := ...)`, unconditional proof-file `stop` ban closing `by open Nat in ... stop`, `_root_.«sorryAx»`, guillemet-wrapped `«debug.skipKernelTC»`, multiline `@[\nextern\n]`, `debug.skipKernelTC`/`byAsSorry`/`proofAsSorry`/`terminalTacticsAsSorry`, `variable`+`include`, per-segment nested `namespace A.B ... end B` scope tracking, declarative `lakefile.toml` with `_SKIP_DIR_SEGS` on `defaultTargets`/`lean_lib.name`/`roots`/`globs`, and 4-byte native ELF binary header verification).
2. **Slow Dual-Pass Mutation Loops (`20–40 min` per delta):** Uncapped `aletheia mutate --max-mutants 0` re-ran full test suites without `--failfast` (`-f`) and re-executed already-killed Pass-1 mutants in Pass 2 (`--guards`).

Track S168 delivers three drop-in, pre-certified stdlib-only engines plus a 14-theorem pure-`Init` Lean 4.36.0 formalization and an independent zero-shared-code verifier:
- **`trust_core.py` (`1,436` non-empty LOC):** Single pre-certified Zone-B I/O, exact JSON, fail-closed empirical provenance (enforcing exact `engine_source_sha256` keyset equality), isolated Lean 4.36.0 dual-projection static+live native-ELF kernel replay (4-byte ELF magic check), and fail-closed JSON CLI kernel. Illustrative minimal-kernel model (`C_core=540`, `B_dup=420`, `b_drop=20`) breaks even at `N=2` tracks (`1,860` LOC saved at `N=6`); exact measured hardened `trust_core.py` (`1,436` non-empty LOC, formally witnessed in Lean T14 and dynamically machine-bound by `verify_s168_velocity.py` against comment-stripped `VelocityBounds.lean`) has tight break-even at `N=4` tracks (`N=3` non-breakeven, `964` LOC saved at `N=6`).
- **`preflight.py`:** Sub-second (`279 ms` on `S161`, `295 ms` on `S166`, enforced `1 <= budget_ms <= 60000` with `< 2000 ms` default budget gate, bounded O(1) directory FDs) shift-left pre-audit gate catching `5/5 (100.0%)` synthetic Wave-22 defect fixtures plus `2` real `MISSING_ALLOW_ABBREV_FALSE` findings on `Track S166`.
- **`fast_mutate.py`:** Exact-parity accelerated mutation engine (matching `aletheia.mutator` across all bare/module/alias/`self`/`cls` guards — `547/547` across all 5 S168 scripts and `61/61` on S166, while intentionally skipping unrelated non-namespace instance `.check(...)` calls unless locally/imported-discovered or passed via `--guards`) with complete golden-baseline slot restoration across every tracked file, target `st_mode` (`target_spec`), and baseline directory (`expected_rel_dirs`, including empty baseline dirs and post-restore SHA/`mtime_ns`/`st_mode` re-verification `SLOT_RESTORE_MISMATCH` — closing `H1_UNLINK`, `H1_CHMOD`, `H1_TARGET_CHMOD`, `H1_SAME_SIZE_MTIME`, and empty-dir `NULL_MUTANT_KILLED`), achieving across 3 randomized CLI-vs-CLI trials (all decimal multiples consistently truncated to 3 d.p. matching exact floor milli-speedups): **`2.328x`** (`13847/5947`) iso-worker `w1 vs w1` speedup, **`1.737x`** (`8380/4823`) iso-worker `w8 vs w8` speedup, and **`5.742x`** (`27694/4823`) end-to-end `base w1 vs fast w8` speedup, with **100.0% bit-identical killed/survived mutant sets** on both `Track S166` (`61/61`) and a mixed killed/survived + non-redundant Pass-2 guard benchmark (`3/5` Pass-1 killed, `4/9` Pass-2 killed, `4` new Pass-2 sites, `3` dedup skipped).

---

## 2. Architecture & Component Deliverables

### 2.1 Shared Pre-Certified Trust Kernel (`trust_core.py`)
- `atomic_write_json_nofollow(path, obj, allow_float=False)`: Rejects `".."` traversal and NUL bytes, walks ancestor directories via `O_RDONLY | O_DIRECTORY | O_NOFOLLOW`, enforces `S_ISREG` and `st_nlink == 1` via `os.lstat(..., dir_fd=dfd)`, preserves existing file mode (`0o600` preserved), uses bounded-length CSPRNG `O_CREAT | O_EXCL | O_NOFOLLOW` temp names, calls `fsync`, and commits via `os.replace(..., src_dir_fd=dfd, dst_dir_fd=dfd)`.
- `strict_read_bytes_nofollow` & `parse_strict_json_bytes`: Enforces `O_NOFOLLOW` ancestor walk, `S_ISREG`, `st_nlink == 1`, bounded reads, zero BOM/CR/CRLF, trailing LF, duplicate-key rejection, finite-only constants, depth (`<= 64`) and integer-digit (`<= 1024`) bounds on both parse and write paths, catches `ArithmeticError`/`decimal.InvalidOperation`, and forbids floats on trust paths.
- `strict_json_equal(a, b)`: Iterative exact-type equality on BOTH dict keys and values (`type(k_a) is type(k_b)` and `type(v_a) is type(v_b)`), blocking `True == 1`, `False == 0`, and `{1: x} == {True: x}`.
- `bind_empirical_artifact`: Defaults fail closed (`allow_float_results=False`, `require_embedded_bench_sha=True`), requires dict root, enforces exact keyset equality on `engine_source_sha256` (rejecting extra unknown keys), binds both `bench_script` and `extra_source_paths` (`trust_core.py`, `preflight.py`, `fast_mutate.py`) mtimes + embedded SHA-256 digests, and returns verified `results_obj`. *(Note: mtime freshness `results > bench/engines` requires timestamp-preserving copies such as `cp -p` / `shutil.copy2` and is reinforced on disk by embedded SHA-256 digests.)*
- `audit_lean4_source_static`, `audit_lakefile_bytes`, & `run_isolated_live_lean`: Dual-projection static Lean 4.36.0 auditor treating ONLY Init-reserved `s!`/`f!`/`println!` as unconditional interpolation keywords while lexing all ambiguous non-Init prefixes (`m!`, `throwError`, `throwErrorAt`, `logInfoAt`, `logWarningAt`, `logErrorAt`, `logAt`, `dbg_trace`, `log*`, arg macros with nested `s!"..."`/`r#"..."#`/`'c'`/`#[...]`/`⟨...⟩`/projection arg tracking, arbitrary `<ident>!`) as plain strings, rejecting `{`/`}` (`LEAN4_AMBIG_INTERP_ESCAPE`), and re-scanning under interpolated-string expansion; bans `stop` unconditionally across proof files (closing `by open Nat in ... stop`), bans `Lean.Elab`/`Lean.Meta`, `macro`/`macro_rules`/`elab`/`syntax`/`notation`, `decide (config := ...)` / `decide (native := ...)`, `opaque`, `instance` overrides; tracks per-segment `namespace A.B ... end B` scopes cleanly; enforces pure declarative `lakefile.toml` allowlist only; requires exact bijection `declared == expected`; verifies native ELF `lean`/`lake` headers directly via 4-byte `O_NOFOLLOW` read (immune to `PATH` shims without reading 128 MiB binaries); rejects `lake build` warnings on stdout/stderr; and verifies isolated tempdir cleanup (`0` `.lake/` residue).
- `StrictArgumentParser` & `run_fail_closed_cli`: Requires `StrictArgumentParser` (`allow_abbrev=False`), emits canonical single-line JSON on `--help` (`RC=0`), and catches all exceptions including `SystemExit` into single-line JSON stderr (`RC=2`).

### 2.2 Two-Second Shift-Left Pre-Audit Gate (`preflight.py`)
Live strictly read-only execution on clean RO snapshots (`s168_ab_results.json`, `cd2ba5691f53d350854464335fe3b1ac396f230f4bfcf789a865052b63be64db`):

| Target / Defect Fixture | Elapsed | Status / Codes Detected | Gate (`< 2000 ms`) |
|---|---:|---|---|
| Real `Track S161` RO snapshot (`10` files, `62` unique Lean theorems) | `279 ms` | `PASS` (`0` findings, `0` false alarms) | `PASS` |
| Real `Track S166` RO snapshot (`18` files, `12` unique Lean theorems) | `295 ms` | `2` genuine findings (`MISSING_ALLOW_ABBREV_FALSE` at `aletheia/lean_audit_hardening.py:1495`, `verify_s166_cs27_cs29.py:1450`) | `PASS` |
| Synthetic `S161 HIGH-1` (`10^67` vs cert `10^64`) | `< 1 ms` | Caught: `SCI_NOTATION_MISMATCH` | `PASS` |
| Synthetic `S161 MED-3` (ghost Lean theorems) | `< 1 ms` | Caught: `GHOST_LEAN_THEOREM` | `PASS` |
| Synthetic `S165 HIGH-1` (dropped passing gate / `FALSIFIED` drift) | `< 1 ms` | Caught: `CERT_VERDICT_CONTRADICTION`, `DROPPED_GATE_VARIABLE` | `PASS` |
| Synthetic `S167 MED-1` (`results.json` older than `bench.py`) | `< 1 ms` | Caught: `STALE_RESULTS_JSON`, `MISSING_VERIFIER_FOR_RESULTS` | `PASS` |
| Synthetic `S167 MED-2` (`results.json` unhashed on disk) | `< 1 ms` | Caught: `UNHASHED_RESULTS_JSON` | `PASS` |
| Self-check on `Track S168` (`13` regular files) | `< 400 ms` | `PASS` (`0` findings, `14` unique Lean theorems; verified live via `preflight.py`, not persisted in `s168_ab_results.json` since `preflight.py` checks `s168_ab_results.json` freshness post-write) | `PASS` |

Synthetic catch rate: **`5/5 (100.0%)`**; real-track latency: **`279 ms` / `295 ms`** (`6x` faster than the enforced `2000 ms` default budget, capped at `MAX_BUDGET_MS = 60000`). Delta-4/Delta-5 AST & coverage hardening closes `from argparse import ArgumentParser as AP` and local variable aliases (`P = ArgumentParser; P()`), module-qualified (`import mod; mod.UnsafeSub()`) and cross-file imported unsafe parser subclasses, enforces unconditional top-level-only `__init__` `allow_abbrev=False` (rejecting `setdefault` and conditional `if` guards), requires an AST `os.replace(...)` / `atomic_write_*nofollow(...)` call on sync and `async def write_json_*/write_cert_*` functions, widens `BOOL_INT_EQ_RISK` to `Name`/`Call`/`Subscript`/`Attribute` cert comparisons (`cert.x == payload.y`), enforces BOM/CRLF on extensionless UTF-8 files, detects integer-mantissa and `exp >= 7` unbacked scientific notation, and uses bounded O(1) directory FDs across the DFS walk.

### 2.3 Exact Zero-Loss Accelerated Mutation Engine (`fast_mutate.py`) & Multi-Trial Live A/B
Randomized 3-trial CLI-vs-CLI CPU-only A/B benchmark (`seed=168`, `s168_ab_results.json`) on `Track S166` (`aletheia/portfolio_dag.py` `f34cbea9...` + `tests/test_cs27_cs29_hardening_r5.py`, Pass 1 default + Pass 2 `--guards _require`, `61 + 61 = 122` pass-level mutants; `fast_mutate.py` stages from a live-verified `chmod -R a-w` RO source copy into private `0o700` writable slots preserving exact file/dir `mtime` and `+x` bits, isolates `TMPDIR`/`HOME`, strips `PYTHONPATH`/`PYTHONSTARTUP`/`PYTHONWARNINGS`, binds `context_sha256` to `timeout` & `sys.executable`, restricts Case-2 `-f` injection strictly to direct `python [flags] script.py` calls, preserves and restores EVERY baseline directory (`expected_rel_dirs`, including empty dirs with bottom-up `st_mode`/`mtime_ns` re-pin) and EVERY tracked baseline file plus the target itself (`target_spec`, never leaving `0o200` after `os.chmod(__file__, 0o000)`) by existence/`st_nlink == 1`/`st_mode`/`mtime_ns`/exact SHA-256 content with post-restore re-verification (`SLOT_RESTORE_MISMATCH`) — closing `H1_UNLINK`, `H1_CHMOD`, `H1_TARGET_CHMOD`, `H1_SAME_SIZE_MTIME`, and empty-dir `NULL_MUTANT_KILLED` — unlinks stray symlinks safely without chmodding targets, and kills timed-out child process groups via `os.killpg(..., SIGKILL)`):

| Engine Configuration (3 Randomized CLI Trials) | Median (`ms`) | Trials (`ms`) | Mutant / Total Evals | Pass-2 Dedup | Exact Parity | Speedup vs Same Workers ($\mathbb{Q}$, 3 d.p. floor) | Speedup vs Base `w1` ($\mathbb{Q}$, 3 d.p. floor) |
|---|---:|---|---:|---:|---|---:|---:|
| Baseline `aletheia mutate` (`w=1`, no `-f`, full Pass 2) | `27,694` | `24730, 27885, 27694` | `122 / 126` | `0/61` | Reference | `1` (`1.000x`) | `1` (`1.000x`) |
| `fast_mutate.py` CLI (`w=1`, `-f` + Pass-2 dedup, RO staged) | `11,894` | `11894, 11236, 14238` | `61 / 65` | `61/61` | **100.0% exact** | **`13847/5947` (`2.328x`)** | `13847/5947` (`2.328x`) |
| Baseline `aletheia mutate` (`w=8`, no `-f`, full Pass 2) | `8,380` | `7258, 8380, 9241` | `122 / 126` | `0/61` | **100.0% exact** | `1` (`1.000x`) | `13847/4190` (`3.304x`) |
| `fast_mutate.py` CLI (`w=8`, `-f` + Pass-2 dedup, RO staged) | `4,823` | `4205, 4823, 6131` | `61 / 65` | `61/61` | **100.0% exact** | **`8380/4823` (`1.737x`)** | **`27694/4823` (`5.742x`)** |

Subprocess reductions: **`2/1`** mutant-only (`122 -> 61`) and **`126/65`** control-inclusive (`4` control evals = 2 passes × (baseline + null-mutant), derived live from `null_mutant == "passed"`). Note that S166 `portfolio_dag.py` Pass 2 (`_require`) adds `0` new sites (`61 == 61`), so it is explicitly supplemented by the mixed killed/survived + non-redundant Pass-2 guard benchmark (`mixed_parity_check`, invoking `fast_mutate.run_dual_fast_mutation` for full survivor-report capture while baseline runs `aletheia mutate` CLI): **`100.0%` exact parity** (`Pass 1: 3/5 killed, 2 survived`, `Pass 2: 4/9 killed, 5 survived, 4 new sites, exact pass2_dedup_skipped == pass1_killed == 3`, SHAs `834d4c11...` / `ccd2b0db...`). Partial-scope flags (`--changed-only`, `--changed-lines`, `--no-boundaries`, `--max-mutants > 0`) strictly emit `PARTIAL_SCOPE_NOT_FINAL` (`final_signoff_eligible = false`, `passed = false`, `RC=2`); timeouts report `TIMEOUT` (`FAIL`, never `KILLED`).

---

## 3. Pure-`Init` Lean 4.36.0 Formalization (`VelocityBounds.lean`, `14/14` Theorems)

Scope note: All 14 public theorems prove abstract cleared-denominator integer arithmetic (with explicit physical domain hypotheses `0 < pd`, `0 < Tmono`, `0 ≤ T1`, `0 ≤ T2`, `0 ≤ pn ≤ pd`, including the genuinely unconditional general-`T2` `iff` in T2 proved WITHOUT assuming `hprob` or `T2 ≤ Tmono` globally, and exact measured `trust_core.py` `C_core = 1436` tight break-even witness in T14 machine-verified against `trust_core.py` by `verify_s168_velocity.py`) and finite `List Bool` exactness laws (including strict `<` early-fail savings in T10) uncoupled from Python runtime internals. Verified via live native ELF `Lean (version 4.36.0, x86_64-unknown-linux-gnu, commit 611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9, Release)` (`lake build` + `#print axioms`, `0` warnings on stdout/stderr, `0` `.lake/` residue):

| # | Public Theorem | Axioms Used |
|---:|---|---|
| 1 | `VelocityBounds.two_stage_expected_time_strict_accel_iff` | `[propext, Quot.sound]` |
| 2 | `VelocityBounds.two_stage_general_T2_le_Tmono_accel` | `[propext, Quot.sound]` |
| 3 | `VelocityBounds.two_stage_expected_savings_exact` | `[propext, Quot.sound]` |
| 4 | `VelocityBounds.two_stage_monotone_in_survival_prob` | `[propext, Quot.sound]` |
| 5 | `VelocityBounds.two_stage_no_gain_at_unit_survival` | `[propext, Quot.sound]` |
| 6 | `VelocityBounds.pass2_dedup_bool_union_exact` | `[]` |
| 7 | `VelocityBounds.pass2_dedup_list_mem_exact` | `[propext, Quot.sound]` |
| 8 | `VelocityBounds.pass2_dedup_eval_count_exact` | `[propext, Quot.sound]` |
| 9 | `VelocityBounds.pass2_dedup_zero_evals_when_subset` | `[propext]` |
| 10 | `VelocityBounds.failfast_kill_equivalence_and_bound` | `[propext, Quot.sound]` |
| 11 | `VelocityBounds.trust_core_amortized_savings_iff` | `[propext, Quot.sound]` |
| 12 | `VelocityBounds.trust_core_monotone_in_tracks` | `[propext, Quot.sound]` |
| 13 | `VelocityBounds.preflight_audit_round_savings_iff` | `[propext, Quot.sound]` |
| 14 | `VelocityBounds.velocity_engine_concrete_witnesses` | `[]` |

The shipped `s168_velocity_certificate.json` is strictly `STATIC_ONLY` (`lean_static_status = "STATIC_PASS"`, `lean_live_mode = "STATIC_ONLY"`, `live_lean_checked = false`, `null` axiom counts; offline `--check` rejects forged `LIVE_LEAN_4_36_0_PASS` at `RC=2`). Live `--check --live-lean` executes real Lean 4.36.0 and dynamically verifies the exact axiom partition (`2` `[]`, `1` `[propext]`, `11` `[propext, Quot.sound]`, `0` `Classical.choice`, `0` `sorryAx`).

---

## 4. Artifact SHA-256 Manifest & Verification Gates (`13` Delivered Files)

| File | Bytes | SHA-256 |
|---|---:|---|
| `trust_core.py` | `69,565` | `0aa076c0129a60ab36c193f099982853bddc6e641f97e0b7f6dcb1b0c9057045` |
| `preflight.py` | `50,799` | `51993142ff8c294ca96b7231e9b427ef1c0076dfa58fa0fa31ae11be6013db5a` |
| `fast_mutate.py` | `77,342` | `7041e51a428ef9c817511b18f19164d235fcd4044fca1fda598a625ab1761dae` |
| `s168_velocity_bench.py` | `31,133` | `e5c01ebae2d831fd4643d917928780fcd81144afd5422616f430cf6a67b73622` |
| `s168_ab_results.json` | `5,997` | `cd2ba5691f53d350854464335fe3b1ac396f230f4bfcf789a865052b63be64db` |
| `VelocityBounds.lean` | `16,836` | `7f59807150db917473dce3272caff1d25b029e75db5b663a7efa2fcda3c5d2e1` |
| `lean-toolchain` | `25` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |
| `lakefile.toml` | `98` | `109cae510505ae5660b0bc6885c3f4ed6e128b662b2ad7bade201ba2a4e301d4` |
| `lake-manifest.json` | `128` | `9eddcd49ac0dad2e15ab3f20e1b6f81189471c5e6999e8ef6075298abd14c6e9` |
| `verify_s168_velocity.py` | `80,557` | `55f6e5a725a7276574be8d92aa0c0976632a5e004ea7886e7c084a40317d4449` |
| `test_s168_velocity_r5.py` | `167,989` | `bdfd2a36932a3c5ccc8f5462f095cb8c7f9c9edd854f28ea2750c7a5d13864d3` |
| `s168_velocity_certificate.json` | `4,423` | `7e65691786ffa26fc98b363f01dd506de2372ac2cadc19556d609424a9ae33f1` |
| `REPORT.md` | — | *(this manifest document; 13th delivered regular file)* |

- **Certificate `payload_sha256`:** `658b496b66d5927810c098215f63ab833f2cd664f7175df2f9512a8bf2d287ba` (`STATIC_ONLY`, pinning all `6/6` Python files and all `4/4` Lean bundle files).
- **`3x -I` Isolated Parity (`-I -B`, `-I -O -B`, `-I -B -W error`) on BOTH RW & `chmod -R a-w` RO Snapshot:** Bit-identical `RC=0` across ALL 4 CLIs (`verify_s168_velocity.py --check`, `preflight.py <dir> --json`, `fast_mutate.py --help`, `s168_velocity_bench.py --help`), and `test_s168_velocity_r5.py` **`7/7 OK` x3** on BOTH RW dir AND fresh `chmod -R a-w` RO copy (`0` skips, `0` bare asserts, `0` warnings).
- **RW & RO (`chmod -R a-w`) `--live-lean --check`:** Both `RC=0` with bit-identical live stdout (`14/14` pure-`Init` Lean 4.36.0 theorems, `2` `[]` / `1` `[propext]` / `11` `[propext, Quot.sound]`, `0` warnings, `0` `.lake/` residue).
- **Dual Uncapped Refusal & Boundary Mutation (`aletheia mutate --max-mutants 0 --workers 8`, `null_mutant = passed`, `truncated = false` across ALL `5/5` owned Python scripts):**
  - `trust_core.py`: **`174/174`** (`default`) + **`174/174`** (`--guards require_tc`)
  - `preflight.py`: **`63/63`** (`default`) + **`63/63`** (`--guards require_tc`)
  - `fast_mutate.py`: **`62/62`** (`default`) + **`62/62`** (`--guards require_tc`)
  - `s168_velocity_bench.py`: **`15/15`** (`default`) + **`15/15`** (`--guards require_tc`)
  - `verify_s168_velocity.py`: **`233/233`** (`default`) + **`233/233`** (`--guards need`)
  - **Combined:** **`547` unique AST sites** (`1,094 / 1,094` dual pass-level evaluations, **`100.0%`, `0` survivors**).
- **Directory Hygiene, Safety, & Lean Audit (`aletheia audit-check --lean-audit --strict-ancestors --safety-scan --strict-unseeded`):** **`PASS`** (`13` regular files, `0` findings, `0` leaks, `0` bare asserts, `0` AST floats, `0` unseeded RNG, `0` `.lake/` / `__pycache__/` / symlinks / CRLF).
