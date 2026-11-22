# Changelog

All notable changes to `Foundation-0/aletheia` are documented in this file. Specification changes follow [`CONTRIBUTING.md`](CONTRIBUTING.md) (issue/audit reference, version bump, and regression tests).

## [2.0.0] — 2026-11-21

Major governance, gate-contract, CLI, schema, and epistemic-honesty release integrating the complete external cross-model review (`aletheia#1`–`#9`, PR `#7` merged at `aa471867`, PR `#8` merged at `aa920b1a`, PR `#9` merged at `ffa0ed42`), owner-confirmed `OWN_TERMS_FIRST`, **Law 2b (Transformational Steelman)** (`AUDIT-088R`), and deterministic safety-surface scanning (`CYA-GAP-01..06`, `AUDIT-078R`).

### Added
- **Pure-$\mathbb{Q}$ v2.0 Gate-Contract Engine (`aletheia/gates_v2.py`, CLI `aletheia gate-v2 --self-test`):**
  - `evaluate_r6_r7_gate` — Contracts **R6 (Pinned Checks)** & **R7 (Measured, Not Declared)** (`aletheia#3` §1).
  - `certify_two_direction_r3` — **Two-Direction R3** (Direction (i) accept $\to$ reject & costly Direction (ii) reject stays reject, with strict typed non-noop equality & case-insensitive unique labels; `aletheia#3` §2).
  - `evaluate_sampled_integrity` — Sampled gate-integrity with `0` hits reports **`NOT_SHOWN`**, never `PASS` (`aletheia#3` §4).
  - `certify_oracle_contract` — Enforces `exact` arithmetic $\ne$ `exact` oracle, splits `anchor` vs. `reference_replay`, and enforces oracle-class-dependent feedback channels (`aletheia#3` §§5–7).
  - `certify_gate8_subspace_latch` — Full pure-$\mathbb{Q}$ Gate-8 $\operatorname{col}(\Phi)$ projection, $\sin^2\theta$ attenuation, **`BLIND_AUDIT_IN_COL_PHI`** halt when $\sin^2\theta = 0$, and $(m - \operatorname{rank}(\Phi)) s^2$ post-fit residual latch (`aletheia#3` §8).
  - `certify_transformational_steelman` — **Law 2b (Transformational Steelman / Morphism-Before-Dismissal)** across 7 typed morphism families (`T1`–`T7`) and 4 anti-epicycle guards (`G1`–`G4`, `AUDIT-088R`).
  - `certify_own_terms_phase1` — **Own-Terms-First** Phase-1 gate integrating `OTF-TIGHT-01..05` (R6 pre-pinned nets, Bonferroni FWER, Tier-4A/4B nulls, Rule-5 signal-over-control dominance, Rule-6 no-float return-to-author; `aletheia#9`, `AUDIT-084R`).
- **Deterministic Agent Safety-Surface Scanner (`aletheia/safety.py`, CLI `aletheia safety-scan` & `aletheia audit-check --safety-scan`):**
  - Implements `CYA-GAP-01..06` (`AUDIT-078R`): Trojan-Source hidden Unicode, unpinned MCP/`--yolo`/`SessionStart`, unguarded `rm -rf "$VAR"` tracking `set -u`/`+u`, `pull_request_target` + secrets/write, prose-only governance + `~/` host paths, and optional `--include-host-hygiene` (`alias rm=` & cloud-sync stubs).
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
