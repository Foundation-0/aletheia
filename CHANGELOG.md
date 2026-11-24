# Changelog

All notable changes to `Foundation-0/aletheia` are documented in this file. Specification changes follow [`CONTRIBUTING.md`](CONTRIBUTING.md) (issue/audit reference, version bump, and regression tests).

## [Unreleased]

### Added
- **Data rights, consent and disclosure rules (text only):** a new subsection in `domains/biology-and-life-sciences.md`, adapted from the public rule files of `Foundation-0/project-asma` (`AGENTS.md`, `docs/reproducibility-and-data.md`). It covers rights before opening a dataset, what may enter Git, one sorted-key SHA-256 instead of per-record hashes, aggregate-only disclosure, a dated human authorization before live acquisition of participant data, patient-grouped splits, outreach drafted by agents but sent by an accountable human, and labelled synthetic inputs. These are human-governance rules; aletheia's tools do not enforce them. A matching anti-pattern says that a clearly labelled synthetic input used because rights or authorization are not in place is not a Substitution Shadow (`CS-04`). `spec/proposals/EMPIRICAL_CLAIMS.md` gate 3 now says that pinning raw data by hash does not mean committing the bytes, and `prompts/peer-weaver.md` archives raw fetches only when their terms allow redistribution and they hold no personal data. `spec/LAWS_AND_GATES.md` is unchanged.

### Changed
- **`aletheia diagnose` `CS-04` (Substitution Shadow):** a proxy line that discloses that the real data are not used because rights, consent or authorization are not in place is no longer scored, matching the biology pack's rule that a clearly labelled synthetic input is not a Substitution Shadow. An undisclosed proxy line still scores `40`. The remediation now asks for real data "where rights and authorization allow" and otherwise for a synthetic input labelled in the same sentence. The match is a substring heuristic on the line (`rights`, `consent`, `authoriz`, `authoris`); it cannot tell whether the stated reason is true. Regression tests in `tests/test_data_rights.py`, which also add must-fail controls for the two `require_ok` refusal sites in `aletheia/diagnose.py` (missing expedition directory, missing board file); before them `aletheia mutate` killed `0/2` of those sites, and with them it kills `2/2`.
- **`aletheia install` built-in templates:** the standalone runbook (`SKILL.md`) and `/aletheia` command now say to probe live upstream data "where rights and authorization allow" and otherwise to label any synthetic input in the same sentence, instead of demanding live data unconditionally. The copies under `adapters/` and `.agents/` that a repo checkout installs are unchanged. Regression test in `tests/test_data_rights.py`.
- **Role prompts (text only):** `prompts/coordinator.md`, `peer-weaver.md`, `domain-probe.md` and `synthesizer.md` no longer let the coordinator agent sign off on posting. Any push, comment, issue or pull request outside the workspace, including peer-weaver's master index comment, needs sign-off from a named accountable human (`<ACCOUNTABLE_HUMAN>`), and each prompt says that aletheia's tools do not enforce this. A test in `tests/test_data_rights.py` keeps the phrase "coordinator sign-off" out of `prompts/`.

## [2.1.0] — 2026-11-22

Twin-coherence release. The method repo and the Cave Expedition ledger now machine-check the claims they make about each other, and the audit of 2026-11-22 (`aletheia#13`) closed its fail-open and label findings.

### Added
- **`aletheia twin-check` (`aletheia/twin_check.py`, contract `spec/twin_contract.json`):** machine-checks the claims the aletheia and cave-expedition repos make about each other. Nine checks cover the audit id range in the cave ledger, the audit ids aletheia cites, the number of check scripts each side counts, the set of results labelled `N2`, the seam and portal counts, the cave README claim that every track reached `VERIFIED`, the byte identity of the two `LICENSE` files, and the CI in each repo. Each check reports `OK`, `DRIFT`, `PENDING` or `SKIP` with the file and line it used, and a `PENDING` entry names the pull request that clears it. `DRIFT` exits `1`, `PENDING` and `SKIP` exit `0`, and a missing twin repo is `SKIP`, so a repo's own CI never fails because a sibling repo was not checked out. The contract pins every count, so a number that changes in one repo needs a reviewed edit in the other.
- **CI job `twin-coherence`:** checks out `Foundation-0/cave-expedition` next to this repo and runs `twin-check` on every push and pull request.

### Fixed
- **`aletheia audit-check` (`aletheia#13`, "Audit scan fails open"):** the file walk now fails closed. A scan root that is not a regular file or directory is refused with the coded error `TARGET_NOT_REGULAR`; every entry is classified with `os.lstat` before anything is read; symlinks are never followed; new codes `SYMLINK_DIR`, `SYMLINK_OUTSIDE_ROOT`, `BROKEN_SYMLINK`, `NON_REGULAR_FILE` and `UNREADABLE_FILE` fail the run; files are opened with `O_NONBLOCK` so a path swapped for a FIFO cannot block the scan. `--allow-symlinks` downgrades the three symlink codes, and the default is fail closed.
- **Strict JSON (`aletheia#13`):** a float literal that silently underflows to zero, such as `1e-999`, is now refused with `JSON_FLOAT_UNDERFLOW`, so a value cannot disappear into `0.0` without a trace.

### Changed
- **Novelty labels (`aletheia#13`, "Flat VERIFIED N2 wording"):** every label in the domain packs, the case study and the worked example now matches the outside two-pass check of the Cave Expedition ledger, which lowered several results from `N2` to `N1` or `N0` because the same mechanism exists under another name in a neighbouring field. Each changed label carries a pointer to the ruling.

### Changed
- Recorded the project owner's 2026-11-23 ruling that Own-Terms-First is adopted as a flexible rule (`spec/LAWS_AND_GATES.md` §1.1 and the status line of `spec/proposals/OWN_TERMS_FIRST.md`). Text only, no version bump.

## [2.0.0] — 2026-11-22

Major governance, gate-contract, CLI, schema, and epistemic-honesty release integrating the complete external cross-model review (`aletheia#1`–`#9`, PR `#7` merged at `aa471867`, PR `#8` merged at `aa920b1a`, PR `#9` head `d43cb1c7` merged at `0b60322` confirming direction points on 2026-11-22 followed by owner authorization of v2.0.0 adoption), **Law 2b (Transformational Steelman)** (`AUDIT-088R`), and deterministic safety-surface scanning (`CYA-GAP-01..06`, `AUDIT-078R`).

### Added
- **Pure-$\mathbb{Q}$ v2.0 Gate-Contract Engine (`aletheia/gates_v2.py`, CLI `aletheia gate-v2 --self-test`):**
  - `evaluate_r6_r7_gate` — Contracts **R6 (Pinned Registered Checks)** & **R7 (Measured, Not Declared)** (`aletheia#3` §1); verifies every pinned check ID against `R6_REGISTERED_CHECKS` and returns executed check statuses (rejecting unknown IDs with `R6_UNKNOWN_CHECK_ID`).
  - `certify_two_direction_r3` — **Two-Direction R3** (Direction (i) accept $\to$ reject & costly Direction (ii) reject stays reject, with strict typed non-noop equality & case-insensitive unique labels; `aletheia#3` §2).
  - `evaluate_sampled_integrity` — Sampled gate-integrity with `0` hits reports **`NOT_SHOWN`**, never `PASS` (`aletheia#3` §4).
  - `certify_oracle_contract` — Enforces `exact` arithmetic $\ne$ `exact` oracle, splits `anchor` vs. `reference_replay`, and enforces oracle-class-dependent feedback channels (`aletheia#3` §§5–7).
  - `certify_gate8_subspace_latch` — Full pure-$\mathbb{Q}$ Gate-8 $\operatorname{col}(\Phi)$ projection, $\sin^2\theta$ attenuation, **`BLIND_AUDIT_IN_COL_PHI`** halt when $\sin^2\theta = 0$, and $(m - \operatorname{rank}(\Phi)) s^2$ post-fit residual latch (`aletheia#3` §8).
  - `certify_transformational_steelman` — **Law 2b (Transformational Steelman / Morphism-Before-Dismissal)** aligned with `AUDIT-088R` (`T1_GAUGE_SIMILARITY`, `T2_AFFINE_BREGMAN`, `T3_METRIC_CHART`, `T4_SPECTRAL_PSD_SHIFT`, `T5_SEMIRING_TROPICAL`, `T6_SUBSPACE_PROJECTION`, `T7_ORDER_DOMAIN_RESIDUAL`; `G0`–`G4` guards raising on first failure and uniform G1 null resolution including `null_total >= 10` on `max_null_rate == 0` across rescues and `INVARIANT_FALSIFIED`). Pure-$\mathbb{Q}$ declared-record gate: certifies record well-formedness and inequalities, not that underlying measurements/null suites were executed.
  - `certify_own_terms_phase1`, `certify_own_terms_model_ladder`, & `certify_own_terms_symbol_utility` — Executable **Own-Terms-First** declared-record gates covering `OTF-TIGHT-01..04` and Rules 2–6 (`>= 2` pre-pinned nets across `>= 2` distinct axes, `held_out_verified`, `second_instrument_verified`, non-vacuous `per_net_alpha <= 1/10`, `max_fwer <= 1/4`, `observed_p_value <= per_net_alpha`, Tier-4A/4B nulls, Rule-5 controls, Rule-6 return, exact orthogonal model-ladder $\mathcal{M}_k^\perp$ projection, and 5-tier symbol operational-utility classifier; `OTF-TIGHT-05` documented as Phase-1/Phase-2 workflow separation). Certifies caller-supplied record well-formedness and inequalities; execution provenance requires separate clean-room replay / R6–R7 byte verification.
  - Dynamic `run_v2_gates_self_test()` verifying one accept and one rejection control per gate; `tests/test_gates_v2_r5.py` kills `156/156` raise-guard deletions, `213/213` `aletheia mutate` sites, and the targeted review `6012061680` sub-condition/classification regressions.
- **Deterministic Agent Safety-Surface Scanner (`aletheia/safety.py`, CLI `aletheia safety-scan` & `aletheia audit-check --safety-scan`):**
  - Implements `CYA-GAP-01..06` (`AUDIT-078R`): Trojan-Source hidden Unicode (`U+00AD`, `U+200B..200F`, `U+2060..2064`, `U+FEFF`, BiDi, variation selectors `U+FE00..FE0F`/`U+E0100..E01EF`, Tags), unpinned MCP/`npx -y` (shell + JSON/YAML)/`--yolo`/`SessionStart`, unguarded recursive force-delete across shell/YAML `run:`/`$(...)`/continuations/`xargs`/`sh -c`/Makefile `$(VAR)` (requiring top-level non-conditional/non-heredoc `set -u`, which guards unset only, or `${VAR:?}`), `pull_request_target` + secrets/`secrets: inherit`/write/untrusted PR head checkout (dot/bracket/step-output/`pull/N/head`/`gh pr checkout`), prose-only governance + `~/` host paths (incl. `.cursorrules`), UTF-16 decoding (with NUL-containing decoded text such as UTF-32 with BOM rejected fail-closed as `undecodable_files`), dotfiles/extensionless/vendor-dir scanning, non-blocking `stat.S_ISREG` skip of non-regular files (FIFOs/sockets/devices) to `skipped_files`, fail-closed reporting of `skipped_files`/`undecodable_files`/`unreadable_files` in both `--json` and plain-text CLI output, and optional `--include-host-hygiene`; `tests/test_safety_r5.py` kills `4/4` raise-guard deletions, `14/14` `aletheia mutate` sites, and all review `6012061680` safety regressions.
- **Prompts & Outside Evidence Governance:** `prompts/advocate.md`, `prompts/outside-observer.md` (`aletheia#2`), `evidence/outside/README.md` (`aletheia#3` §10), and expanded `CONTRIBUTING.md` spec-change & authorship-disclosure rules.

### Fixed (Closing All `aletheia#5` `#1`–`#13` + PR `#7`/`#8` Edge Cases)
- **`aletheia mutate` (`#1`, `#6`, `#7`, `#11`, `#12`, PR `#8` `#6`):**
  - Added cross-module AST imported-wrapper discovery (`from helpers import need`), explicit `--guards`, and `covered_lines` reporting (`#1`).
  - Added explicit `-I`/`--add-cwd` hint on `ModuleNotFoundError`/`ImportError` during baseline runs (`#6`).
  - Caught `subprocess.TimeoutExpired` on baseline runs as structured `BASELINE_TEST_TIMEOUT` (exit `2`, zero traceback; `#7`).
  - Expanded refusal-shape discovery to string returns (`"REJECTED"`, `"against"`, `"inconclusive"`, ...), tuple returns (`(False, ...)`), and multi-statement `if` branches (`print(...); raise ...`), covering `shapes.py` (`5/5`) and `rule.py` (`#11`).
  - Added self-check script mutation (`guard_selfcheck_negate` + `boundary_const_require`: `== 10` $\to$ `== 11`) so sound self-checking scripts reach `100.0%` kill (`#12`).
  - Upgraded `--max-mutants` truncation to return `verdict="NOT_SHOWN"` and `passed=False` (exit `1`) per `aletheia#3` §4.
- **`aletheia audit-check` (`#2`, `#3`, `#9`, `#13`, PR `#7` B4):**
  - Added R4 `unittest` skip-count & test-count parity across `-I -B`, `-I -O -B`, and `-I -B -W error` so `@unittest.skipIf(not __debug__, ...)` fails R4 (`#2`).
  - Extended `--strict-unseeded` AST scanning to `from random import ...`, `from numpy.random import ...`, and `from numpy import random`, with clarified global-RNG wording when `random.seed(...)` is present (`#9`, `#13`).
  - Added Lean 4 raw string (`r#"..."#`) support to `_strip_lean4_with_report` so valid raw strings with embedded quotes do not falsely trigger `LEAN4_UNTERMINATED_STRING`.
- **Schemas & `aletheia handoff` (`#3`, `#4`, `#5`):**
  - Replaced every `$` pattern anchor with `(?!\n)$` across all 3 JSON schemas (`#5`), aligned `audit_receipt.v1.schema.json` (`AUDIT-[0-9]{3,4}...`, `VERIFIED -> r4_parity: true`, `G1`–`G10`/`R1`–`R7`) with `audit_check.py` (`#3`), and allowed optional parenthetical qualifiers + `reference_replay` in `compute_handoff.v1.schema.json` so live `next_waves_manifest.json` validates cleanly (`#4`).
- **`aletheia diagnose` (`#8`):** Falls back to root `frontier_portals.md` when `cartography/frontier_portals.md` is absent and adds `--portals-path`; renamed `CS-08` to *Compute Leakage* (`aletheia#4`).
- **`aletheia install --target claude-code` (`#10`):** Aligned `.claude-plugin/plugin.json` paths (`.claude/commands/...`, `.claude/agents/...`) with installed file locations.

### Changed (Spec & Epistemic Corrections)
- Promoted `spec/proposals/OWN_TERMS_FIRST.md` into canonical `spec/LAWS_AND_GATES.md` (`aletheia.spec.v2.0`) alongside Law 2b, Gate 10 (Advocate Pass), `R6`/`R7`, Two-Direction `R3`, Anti-Patterns `CS-13` (Citation-Trail Search) & `CS-14` (One-Sided Verifier), and honest `7/8` operational-utility accounting for v1.3 glyphs (`AUDIT-084R`).
- Applied all `17` sentence corrections from `aletheia#4` (plus `CS-08` rename) across `README.md`, `THEORY.md`, `spec/LAWS_AND_GATES.md`, `evidence/cave-expedition-case-study.md`, and `domains/*.md`, and added prior-work, falsification-condition, and Pass-1-vs-Pass-2 confound sections to `THEORY.md` (`aletheia#3` §9).

## [1.4.0] — 2026-11-21
- Added AST local refusal-wrapper auto-detection, strict JSON/JSONL parsing, `--strict-ancestors`, `CS-12` Trust-Boundary Shadow, and Round-6 case study (`85830ca`, plus PR `#7` `aa471867` & PR `#8` `aa920b1a`).
