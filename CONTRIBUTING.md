# Contributing to Aletheia

We welcome contributions that expand **The Aletheia Method** into new scientific domains, stronger verification oracles, additional AI agent platforms, and independently audited empirical case studies.

Every contribution to `Foundation-0/aletheia` is held to the exact same anti-shadow discipline defined in [`spec/LAWS_AND_GATES.md`](spec/LAWS_AND_GATES.md).

---

## What You Can Contribute

1. **Domain Adaptation Packs (`domains/<discipline>.md`):**
   - Practitioner-grade guides explaining what raw portals look like in your field, concrete steelman & Law 2b morphism moves, domain-specific `exact`/`sampled`/`anchor`/`reference_replay` oracles, mandatory negative controls, and field-specific Cave-Shadow anti-patterns.
   - Update [`domains/README.md`](domains/README.md) with a corresponding Rosetta Stone row.
2. **Verification Oracles & Tooling (`aletheia/` & `tests/`):**
   - Pure Python 3 stdlib extensions to `aletheia` (zero mandatory third-party dependencies for the core CLI).
   - Must have **zero bare `assert` statements** on trust/validation paths (Contract R4), pass across all three isolated Python modes (`-I -B`, `-I -O -B`, `-I -B -W error`), and achieve **100% mutant kill rate** under `aletheia mutate --max-mutants 0` (Contract R5; truncated runs are `NOT_SHOWN`).
3. **Platform Adapters (`adapters/<platform>/`):**
   - Drop-in configurations for additional AI coding/research environments, keeping prompts and rules aligned with [`spec/LAWS_AND_GATES.md`](spec/LAWS_AND_GATES.md).
4. **Verified Case Studies (`evidence/<expedition-name>.md`) & Outside Audits (`evidence/outside/`):**
   - Empirical studies documenting actual discovery cycles—including **both** breakthroughs (`N1`/`N2`) and honest `FALSIFIED` / `PARTIAL/FRAGILE` misses (Gate 8)—with reproducible verification scripts, pinned commit SHAs, and mechanism-first prior-art accounting (Gate 9).
   - Independent external audits and two-pass Advocate rulings belong in [`evidence/outside/`](evidence/outside/README.md) and are never overwritten or deleted.
5. **Executable Worked Demos (`examples/<demo>/`):**
   - Fast (`< 5s`), self-contained, deterministic demonstrations of a full Aletheia Resonance Cycle.

---

## Specification Change Process (`aletheia#3` §10)

Any change to [`spec/LAWS_AND_GATES.md`](spec/LAWS_AND_GATES.md) or `schemas/*.json` MUST include:
1. **An Issue or Audit Reference:** Open an issue (or link an `AUDIT-XXX` entry) stating the exact gap, counterexample/evidence, and proposed wording.
2. **Semantic Version Bump & Changelog Entry:** Bump `version` in `pyproject.toml`, `aletheia/__init__.py`, and plugin manifests, and record the change in [`CHANGELOG.md`](CHANGELOG.md).
3. **Executable Regression Test:** Pair every new gate contract or schema constraint with a deterministic test in `tests/` (and R5 mutation coverage where applicable).

---

## Reviewer, Merger & Automated-Authorship Disclosure (`aletheia#3` §10)

In keeping with Law 4 provenance honesty:
- **Independent Reviewer vs. Author:** Every PR touching `aletheia/`, `spec/`, or `schemas/` should be reviewed by an independent checker (human or separate verification agent) before merge; self-authored commits must state who verified and who merged them.
- **Automated / Agentic Authorship:** PRs, issues, and reviews produced wholly or partially by AI agents MUST disclose automated authorship explicitly (e.g., *"Automated posting by agentic team with human oversight"*) and include reproducible commands so any human or external checker can verify every claim independently.

---

## Pre-PR Verification Checklist (Mandatory)

Before opening a pull request against `main` (direct pushes to `main` are blocked by branch protection):

```bash
# 1. Run the full self-test & R5 mutation suite under all 3 isolated R4 modes
python3 -I -B tests/run_all.py
python3 -I -O -B tests/run_all.py
python3 -I -B -W error tests/run_all.py

# 2. Run the 3-second worked resonance demo & v2.0 pure-Q gate self-test
python3 -I -O -B -W error examples/worked_resonance_cycle/run_demo.py
PYTHONPATH=. python3 -B -m aletheia gate-v2 --self-test --json

# 3. Run Aletheia's own automated hygiene, R4, and audit-integrity checker on the repo
PYTHONPATH=. python3 -B -m aletheia audit-check . --strict-ancestors
```

### Hard Hygiene Rules
- **Line endings:** Strictly LF (`\n`); zero CRLF (`\r\n`).
- **Zero personal/local paths or secrets:** Never commit personal home-directory paths, local file-URI links, API tokens, or `__pycache__` artifacts.
- **Honest provenance:** Tag uncompiled formal proof files as `uncompiled_source`, keep open contributions as Draft PRs until external review, and default all novelty claims to `N0` unless accompanied by mechanism-first full-text prior-art verification.

---

## Pull Request Workflow

1. Fork or create a clean feature branch (`feat/<topic>`, `domain/<discipline>`, `adapter/<platform>`, or `fix/<issue>`).
2. Run all three commands in the Pre-PR Verification Checklist above and confirm zero warnings and 100% pass.
3. Open a pull request against `main` stating:
   - Exact files changed and why.
   - Oracle class (`exact` / `sampled` / `anchor` / `reference_replay`) for any new check or case study.
   - Exact reproduction command, CI check results, and reviewer/automated-authorship disclosure.
