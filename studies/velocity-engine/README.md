# Track S168 (`EXP-Q56a`): Aletheia Velocity Engine

Verified pure-Python stdlib (`int`/`Fraction`) and pure-`Init` Lean `4.36.0` verification acceleration stack (`trust_core.py`, `preflight.py`, `fast_mutate.py`, and `VelocityBounds.lean`), staged cleanly under `studies/velocity-engine/`.

- **External Audit:** `AUDIT-S168-EXP-Q56A-DELTA5.md` (`SHA-256: feb69a3e95993c3a5cc59a2da44747c4361badfb66af604a03b9e49e0948a556`) — **`PASS` (`HIGH: 0`, `MED: 0`, `LOW: 7`)**
- **Lean `4.36.0` Formalization:** `VelocityBounds.lean` (`leanprover/lean4:v4.36.0`) — **`14/14` pure-`Init` theorems** (`2` `[]`, `1` `[propext]`, `11` `[propext, Quot.sound]`; `0` `Classical.choice`, `0` `sorry`, `0` warnings, `0` external packages)
- **Uncapped Dual Mutation Kill Rate:** **`1,094/1,094` (`100.0%`, `0` survivors)** across `547` unique AST sites in all `5/5` owned Python modules (`trust_core.py` `174×2`, `preflight.py` `63×2`, `fast_mutate.py` `62×2`, `s168_velocity_bench.py` `15×2`, `verify_s168_velocity.py` `233×2`)
- **Empirical A/B Speedup (`s168_ab_results.json`, `seed=168`, `3` randomized trials, CPU-only):** **`5.742x` E2E** (`27,694 ms` baseline `w=1` vs `4,823 ms` `fast_mutate.py w=8`, exact `27694/4823`), **`2.328x`** iso-worker `w=1` (`13847/5947`), and **`1.737x`** iso-worker `w=8` (`8380/4823`) at `100.0%` mutant set parity; `preflight.py` catches `5/5` synthetic defects and runs in `279 ms` (`S161`) / `295 ms` (`S166`) under the `2000 ms` budget
- **Hygiene & Provenance Invariants:** `0` `.lake/` residue, `0` `__pycache__`/`.pyc` artifacts, `0` personal home-path leaks, `0` symlinks, `0` CRLF files, `0` bare `assert`s, `0` AST floats on trust paths, `WEIGHTS=0`, `CPU-only`

## Contents (`13` Verified Artifacts + `README.md`)

| Artifact | Purpose |
|---|---|
| `trust_core.py` | Shared `1,436`-non-empty-LOC Zone-B `O_NOFOLLOW`/`os.replace` I/O, exact-type JSON equality, empirical provenance binder, dual-projection Lean `4.36.0` verifier, and fail-closed CLI kernel (tight break-even at `N=4`, `964` LOC saved at `N=6`) |
| `preflight.py` | Shift-left `< 2000 ms` static AST, Lean theorem-citation, witness, freshness, and public-hygiene gate (`run_preflight`) |
| `fast_mutate.py` | Exact-parity AST mutation runner (`547/547` parity on S168, `61/61` on S166) with `--failfast` injection, Pass-2 killed-site deduplication, and full slot restoration (`SLOT_RESTORE_MISMATCH`) |
| `VelocityBounds.lean` | Standalone `leanprover/lean4:v4.36.0` package (`lean-toolchain`, `lakefile.toml`, `lake-manifest.json`) proving all `14` cleared-denominator arithmetic, deduplication, and amortization laws |
| `s168_velocity_bench.py`, `s168_ab_results.json` | Reproducible 3-trial A/B benchmark harness and pinned empirical record (`cd2ba569...`) |
| `verify_s168_velocity.py`, `s168_velocity_certificate.json` | Zero-shared-code verifier (`STATIC_ONLY` cert `7e656917...`, `payload_sha256: 658b496b...`; `--live-lean` upgrades to live kernel replay and offline `--check` rejects forged live certs at `RC=2`) |
| `test_s168_velocity_r5.py` | Comprehensive R1–R5 adversarial test suite (`7/7` test groups, `0` skips across all `-I` modes) |
| `REPORT.md` | Full Track S168 (`EXP-Q56a`) engineering report and `SHA-256` manifest |

## Quick Verification

```bash
# 1. Verify certificate and R5 test suite across all 3 isolated -I modes (bit-identical)
for flags in "-I -B" "-I -O -B" "-I -B -W error"; do
  CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 python3 ${flags} \
    studies/velocity-engine/verify_s168_velocity.py --check
  CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 python3 ${flags} \
    studies/velocity-engine/test_s168_velocity_r5.py
done

# 2. Shift-left preflight & isolated live Lean 4.36.0 replay (0 .lake/ residue)
CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 python3 -I -B \
  studies/velocity-engine/preflight.py studies/velocity-engine --json
CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 python3 -I -B \
  studies/velocity-engine/verify_s168_velocity.py --check --live-lean

# 3. Full Aletheia hygiene, Lean, ancestor, and safety audit
PYTHONPATH=. python3 -B -m aletheia audit-check studies/velocity-engine \
  --lean-audit --strict-ancestors --safety-scan --strict-unseeded \
  --scripts verify_s168_velocity.py test_s168_velocity_r5.py
```
