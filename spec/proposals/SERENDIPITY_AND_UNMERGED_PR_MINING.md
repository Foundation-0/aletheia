# Proposal: Law 1b — Blind-Spot-Free Cross-Repo Serendipity & Unmerged-PR Portal Mining

**Status:** Proposal, not adopted. Adoption is for the method's maintainers. Written against `aletheia.spec.v2.0` (`spec/LAWS_AND_GATES.md`), aligned with `spec/proposals/EMPIRICAL_CLAIMS.md` (`aletheia#10`), and backed by dual-continent verified unmerged-PR portal-mining evidence (`N0` protocol formalization and pure-$\mathbb{Z}/\mathbb{Q}$ re-formulation over upstream open and closed-unmerged mechanisms).  
**Reference Implementation:** [`aletheia/supervision_airlock.py`](../../aletheia/supervision_airlock.py) (`certify_law1b_serendipity_mining`, schema `aletheia.law1b.v1`), verified by [`tests/test_supervision_airlock_r5.py`](../../tests/test_supervision_airlock_r5.py).

---

## 1. Motivation: Closing Anti-Pattern `CS-15` (Merged-Only Tunnel Vision)

Standard research audits and repository reviews inspect only a repository's default branch (`main`) and published releases. Across eight active research and engineering repositories audited read-only in the Law-1b portal-mining study (`1,437` total pull requests fetched on `2026-11-22`), **`387 / 1,437` (`129 / 479`, ~26.9%)** of pull requests were **unmerged** (`296` open + `91` closed-unmerged).

Empirical mining of those unmerged branches shows that high-signal mathematical defects, negative controls, lexer/parser security counterexamples, multi-seed empirical refutations, pre-freeze cancellations, and alternate architectural prototypes frequently live *outside* `main`:

- **Closed-unmerged bugfixes and exact reproducers:** nearest-rank quantile `+1` overshoot at every multiple of `20` (`NandhaKishorM/laya#698`); self-cancelling minimum-offset drop (`laya#693`/`#683`); `10**400` JSON `OverflowError` (`laya#1411`); presence-file peer-key forgery (`Moissanite-Labs/exo#428`); backtick backslash-newline lexing collapse (`exo#490`); `gh` option-value target smuggling (`exo#402`).
- **Closed-unmerged architectural prototypes:** browser WebGPU hidden-state steering with counterfactual unsteered replay (`chuanqisun/spaceship#5`); 4-pane comparison arena (`spaceship#3`).
- **Open empirical refutations, cancellations, and exact tools:** micro-batch item-count weighting closing `CS-10` denominator collapse (`laya#1465`); 3-seed refutation of single-seed soft-CE gains (`laya#1210`); pre-freeze experiment cancellation (`Moissanite-Labs/weft-loom#25`); direct span-pooling kernel equivalence (`NandhaKishorM/vegaml#57`); stdlib `GF(q)` minimum-distance certifier (`Foundation-0/math0#3`).

Inspecting only `main` — or even inspecting only `open` PRs while ignoring `closed_unmerged` PRs — creates a systematic discovery blind spot:

| Anti-Pattern ID | Name | Observable Symptom | Structural Remedy |
|---|---|---|---|
| **`CS-15`** | **Merged-Only Tunnel Vision** | Portal audit reads only `main` / releases (or `open` PRs only), silently skipping `closed_unmerged` PRs, drafts, and open issues where counterexamples, refutations, and discarded prototypes live. | Enforce **Law 1b**: enumerate `open` + `closed_unmerged` PRs and issues read-only (`external_writes == 0`), pin snapshots by SHA-256, and extract exact non-metaphorical witnesses under Law 5. |

---

## 2. Proposed Statement of Law 1b

> **Law 1b — Blind-Spot-Free Cross-Repo Serendipity & Unmerged-PR Portal Mining:**
> 1. **Leave no read-only portal path unexplored:** Whenever a portal repository, anomaly, or cross-domain operator surfaces, execute a strictly read-only exploration pass (`external_writes == 0`) rather than gating read-only curiosity on pre-justified payoff.
> 2. **Mine BOTH `open` and `closed_unmerged` PRs (plus issues/discussions) on every portal:** Query `state=all` PRs, record `merged`, `open`, and `closed_unmerged` counts explicitly, and inspect high-signal candidates from **both** unmerged buckets whenever present. "Blind-spot-free" is certified as >=1 open AND >=1 closed-unmerged PR mined overall (not per-repo, no coverage fraction); executed-witness `honest_novelty` is caller-declared.
> 3. **Couple serendipity to Law 4 & Law 5 (zero metaphor inflation):** Classify every mined entry explicitly as either an **`EXECUTED_EXACT_WITNESS`** (backed by an independent zero-float executable reproducer and negative control) or a **`CATALOGED_LEAD`** (strictly capped at honest novelty **`N0`** until independently executed and full-text prior-art checked).

---

## 3. Fail-Closed Machine-Checkable Guards (`G-1b.1` – `G-1b.4`)

Implemented in pure Python 3 stdlib (`int` / `Fraction`, zero floats, zero bare asserts) by `aletheia.supervision_airlock.certify_law1b_serendipity_mining(spec)` (schema `aletheia.law1b.v1`):

1. **`G-1b.1` — Anti-Merged-Only, Anti-Open-Only & Per-Repo Cap Guard:**
   - Every scanned repository row satisfies exact non-negative integer conservation `open + closed_unmerged + merged == fetched` with `fetched > 0`, and unique case-insensitive `repo` names.
   - If `sum(closed_unmerged) > 0`, mined entries MUST include at least one `closed_unmerged` PR (`L1B_CLOSED_UNMERGED_BLIND_SPOT`).
   - If `sum(open) > 0`, mined entries MUST include at least one `open` PR (`L1B_OPEN_PR_BLIND_SPOT`).
   - Per-repository mined counts MUST NOT exceed that repository's scanned `open` or `closed_unmerged` totals (`L1B_REPO_OPEN_COUNT_EXCEEDED`, `L1B_REPO_CLOSED_UNMERGED_COUNT_EXCEEDED`).
2. **`G-1b.2` — Exact Provenance Pinning & Closed Mechanism Taxonomy:**
   - Every scanned repository pins a non-uniform 64-char lowercase hex `prs_json_sha256`.
   - Every mined PR entry belongs to a scanned repository, has unique `(repo.lower(), number)` with positive integer `number`, `status in {"open", "closed_unmerged"}`, non-uniform 40-hex `head_sha`, non-uniform 64-hex `snapshot_sha256`, clean ASCII `operator_summary`, and `mechanism_class` from the closed 9-class taxonomy (`DENOMINATOR_OR_WEIGHT_BIAS`, `QUANTILE_OR_INDEX_BOUNDARY`, `AFFINE_OR_RANGE_PROJECTION`, `ALGEBRAIC_KERNEL_EQUIVALENCE`, `LEXER_OR_PARSER_SECURITY_BYPASS`, `CRYPTO_PIN_OR_STATE_MACHINE`, `EMPIRICAL_REFUTATION_OR_FREEZE`, `INTERNAL_STEERING_OR_ARCHITECTURE`, `EXACT_CERTIFIER_OR_DOMAIN_TOOL`).
3. **`G-1b.3` — Non-Metaphorical Operator Discipline:**
   - At least one mined entry MUST have `evidence_standing == "EXECUTED_EXACT_WITNESS"` (`L1B_ZERO_EXECUTED_WITNESSES`).
   - Every entry with `evidence_standing == "CATALOGED_LEAD"` MUST have `honest_novelty == "N0"` (`L1B_LEAD_CANNOT_CLAIM_ABOVE_N0`).
4. **`G-1b.4` — Zero-Write Portal Integrity:**
   - `external_writes` MUST equal strict integer `0` (`L1B_NONZERO_EXTERNAL_WRITES`).

> **Declared-Record Scope Boundary (Consistent with `spec/LAWS_AND_GATES.md` & `EMPIRICAL_CLAIMS.md` R7):** `certify_law1b_serendipity_mining(spec)` certifies that a caller-supplied Law-1b mining record is structurally valid and satisfies guards `G-1b.1`–`G-1b.4`. It does **not** establish from the dict alone that the referenced GitHub snapshot files exist on disk or match their pinned SHA-256 digests; live byte-level re-hashing of frozen intake JSON snapshots is performed by a separate byte-verifying runner against the pinned intake directory.

---

## 4. Concrete `aletheia.safety` v2.1 Hardening Roadmap Derived From Unmerged PRs

Law-1b mining of unmerged `Moissanite-Labs/exo` PRs surfaced four concrete deterministic static-analysis upgrades for a follow-up `aletheia/safety.py` v2.1 PR:

1. **Backtick backslash-newline stripping (`exo#490` [closed_unmerged]):** Collapse odd backslash-newline pairs inside backticks before splitting command tokens so split dangerous commands cannot evade `CYA-GAP-03`.
2. **Unquoted heredoc logical-line terminators (`exo#911` [open]):** Join physical lines ending in odd backslash runs before matching unquoted heredoc delimiters, and strip leading tabs for `<<-` only on the joined logical line.
3. **Full GNU/BSD `xargs` getopt parsing (`exo#1136` [open]):** Parse long options, unambiguous prefixes, clustered short options ending in an argument-taking flag, and BSD `-J`/`-R`/`-S` flags so option arguments are never misclassified as invoked binaries.
4. **Operand-only CLI target resolution (`exo#402` [closed_unmerged]):** Resolve target repositories strictly from explicit `-R`/`--repo` flags or positional URL operands, ignoring URLs embedded in `--body`, `--comment`, or `--duplicate-of` option values.
