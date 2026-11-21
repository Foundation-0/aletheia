# Contributing to Aletheia

We welcome contributions that expand **The Aletheia Method** into new scientific domains, stronger verification oracles, additional AI agent platforms, and independently audited empirical case studies.

Every contribution to `Foundation-0/aletheia` is held to the exact same anti-shadow discipline defined in [`spec/LAWS_AND_GATES.md`](spec/LAWS_AND_GATES.md).

---

## What You Can Contribute

1. **Domain Adaptation Packs (`domains/<discipline>.md`):**
   - Practitioner-grade guides explaining what raw portals look like in your field (e.g., chemistry, economics, formal hardware verification, neuroscience, climate modeling), concrete steelman moves, domain-specific exact/sampled/anchor oracles, mandatory negative controls, and field-specific Cave-Shadow anti-patterns.
   - Update [`domains/README.md`](domains/README.md) with a corresponding Rosetta Stone row.
2. **Verification Oracles & Tooling (`aletheia/` & `tests/`):**
   - Pure Python 3 stdlib extensions to `aletheia` (zero mandatory third-party dependencies for the core CLI).
   - Must have **zero bare `assert` statements** on trust/validation paths (Contract R4), pass across all three isolated Python modes (`-I -B`, `-I -O -B`, `-I -B -W error`), and achieve **100% mutant kill rate** under `aletheia mutate` (Contract R5).
3. **Platform Adapters (`adapters/<platform>/`):**
   - Drop-in configurations for additional AI coding/research environments, keeping prompts and rules aligned with the 5 Laws and 9 Gates in [`spec/LAWS_AND_GATES.md`](spec/LAWS_AND_GATES.md).
4. **Verified Aletheia Case Studies (`evidence/<expedition-name>.md`):**
   - Empirical studies documenting actual discovery cycles—including **both** breakthroughs (`N1`/`N2`) and honest `FALSIFIED` / `PARTIAL/FRAGILE` misses (Gate 8)—with reproducible verification scripts and explicit prior-art accounting (Gate 9).
5. **Executable Worked Demos (`examples/<demo>/`):**
   - Fast (`< 5s`), self-contained, deterministic demonstrations of a full Aletheia Resonance Cycle.

---

## Pre-PR Verification Checklist (Mandatory)

Before opening a pull request against `main` (direct pushes to `main` are blocked by branch protection):

```bash
# 1. Run the full self-test & R5 mutation suite under all 3 isolated R4 modes
python3 -I -B tests/run_all.py
python3 -I -O -B tests/run_all.py
python3 -I -B -W error tests/run_all.py

# 2. Run the 3-second worked resonance demo under R4 parity
python3 -I -O -B -W error examples/worked_resonance_cycle/run_demo.py

# 3. Run Aletheia's own automated hygiene, R4, and audit-integrity checker on the repo
PYTHONPATH=. python3 -I -O -B -W error -m aletheia audit-check .
```

### Hard Hygiene Rules
- **Line endings:** Strictly LF (`\n`); zero CRLF (`\r\n`).
- **Zero personal/local paths or secrets:** Never commit personal home-directory paths, local file-URI links, API tokens, or `__pycache__` artifacts.
- **Honest provenance:** Tag uncompiled formal proof files as `uncompiled_source`, keep open contributions as Draft PRs until external review, and default all novelty claims to `N0` unless accompanied by explicit full-text prior-art verification.

---

## Pull Request Workflow

1. Fork or create a clean feature branch (`feat/<topic>`, `domain/<discipline>`, `adapter/<platform>`, or `fix/<issue>`).
2. Run all three commands in the Pre-PR Verification Checklist above and confirm zero warnings and 100% pass.
3. Open a pull request against `main` stating:
   - Exact files changed and why.
   - Oracle class (`exact` / `sampled` / `anchor`) for any new check or case study.
   - Exact reproduction command and CI check results.
