# External evidence index

Where each verification script or record held in a sibling repository, and cited by this repository as evidence, can be found. Read on 2026-11-24 from main-only clones of `Foundation-0/cave-expedition` at `9729839` and `Foundation-0/project-asma` at `de88b12`. A row records location only. It does not say that the artifact's claim holds.

Status values:

- `main`: on that repository's main branch at the revision read.
- `PR-only`: on an open pull request branch only, according to the source named in the row. A main-only clone cannot confirm it.
- `not on main at 9729839`: not on cave-expedition main at that revision. It may exist on cave PR 1 or elsewhere; a main-only clone cannot check that. Rows past `AUDIT-019` live on PR 1 according to cave `verification/outside/README.md:18-28` and `docs/ledger/index.html:130`.

`tests/test_external_evidence.py` checks that every `check_NNN` script cited in `README.md`, `THEORY.md`, `CHANGELOG.md`, `spec/`, `domains/`, `evidence/` and `docs/` has a row here, and that no line calls a script of status `not on main at 9729839` archived. It reads only this repository. It cannot detect a change in a sibling repository; refresh this table by hand when one moves.

| Cited as | Repo | Status | Revision read | Path | sha256 |
|---|---|---|---|---|---|
| `check_001`–`check_014` | Foundation-0/cave-expedition | main | `9729839` | `verification/checks/check_001_*.py` to `check_014_*.py` | one file each; pinned by the commit |
| `verify_round10_standalone.py` and the round-10 arm reports | Foundation-0/cave-expedition | main | `9729839` | `verification/checks/verify_round10_standalone.py`, `symbiosis/round10/arm1-*` to `arm5-*` | `1b290b5faa9da393bb70045503ae18b131b766774a6f103bbec43a3dcaf7f8cd` (verifier) |
| two-pass outside check, `cave-expedition#4` | Foundation-0/cave-expedition | main | `9729839` | `verification/outside/rulings.json` (with `OUTSIDE_AUDIT.md`, `SOURCES.md`, `check_totals.py`) | `792b25bac6d83bb877c82c4c6c99115c7b03382415423b6acd96ed2121efff75` (`rulings.json`) |
| Gate-5 outside audit, `cave-expedition#5` | Foundation-0/cave-expedition | main | `9729839` | `verification/outside/gate5-unification/` | `673f006ea3ffad6ecd9c16db2f0fc5f67469b9bcbb5991d7043b3ef567149de7` (`RULINGS.json`) |
| ledger rows `AUDIT-020`, `AUDIT-020R`, `AUDIT-021` | Foundation-0/cave-expedition | PR-only | not read | `verification/AUDIT_LOG.md` on PR 1, branch `expedition/sync-audit-020r-and-pr-links` (cave `verification/outside/README.md:22-28`) | none |
| `check_016`–`check_025` | Foundation-0/cave-expedition | not on main at 9729839 | `9729839` | none on main | none |
| `check_026`–`check_030` | Foundation-0/cave-expedition | not on main at 9729839 | `9729839` | none on main | none |
| `check_040`, `check_042`, `check_045` | Foundation-0/cave-expedition | not on main at 9729839 | `9729839` | none on main | none |
| `NEXT_WAVES_COMPUTE.md` | Foundation-0/cave-expedition | not on main at 9729839 | `9729839` | none on main | none |
| `AUDIT-006R` instrument, `project-asma#101` | Foundation-0/project-asma | main (merged as `f2f92ee`, 2026-11-22) | `de88b12` | `studies/expedition-mobius-ropt/optimal_inertia_rank.py` | `84aba2bdce27c1243ee5e3de2a2d248126c17ad2337269c43c227e099367f7c9` |
