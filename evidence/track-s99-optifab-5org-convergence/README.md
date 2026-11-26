# 5-Organization Physical-Digital OptiFab Convergence Megastructure (`18/18` Pure-`Init` Lean `4.36.0`)

Self-contained Aletheia evidence bundle uniting five public organizations (`Foundation-0`, `Moissanite-Labs`, `siliconcordat`, `proven-commons`, `aska-physical`) into an exact pure-$\mathbb{Z}/\mathbb{Q}$ certified physical-digital convergence architecture anchored to `aska-physical/optifab` (`v0.3.3`) alongside **`18/18` universally quantified pure-`Init` Lean `4.36.0` theorems** (`0` imports, `0` warnings, `0` `Classical.choice`, `0` `sorryAx`, axioms strictly `⊆ {propext, Quot.sound}`):

1. **Pillar 1 — Exact $\mathbb{Z}/\mathbb{Q}$ Diagnosis & Certified Repair of `aska-physical/optifab#14` (Defects 1–5):** Reproduces Defects `#14.1`–`#14.2` and formally diagnoses + repairs three open `v0.3.3` defects: `#14.3` equal-objective headroom decay (`accepts_lex` blocks `4/4` tie-decay steps while admitting headroom-widening `pcm = 2,580 kWh`), `#14.4` missing `WellFormed` predicate (`well_formed_plant_check` rejects negative outage margin and zero-floor exploits), and `#14.5` symmetric distance wall + trapped out-of-limit recovery (`gate_asymmetric_recovery` admits safe doubling `2,500 -> 5,000 kWh` and recovers out-of-limit `pcm = 2,350` in 1 Lyapunov step).
2. **Pillar 2 — Unified `64`-Byte Physical-Digital Coupled Gate & Exact Schur Polytope:** Couples `12` physical margins (binding floor punching collar headroom `0.198948`) with `8 GiB` VRAM headroom (`0.195001`) and exact `6 x 6` block Schur + Haynsworth-Sylvester inertia checking: nominal `eta = 1` gives `inertia(M) = [6, 0, 0]` (`ADMIT`), whereas overload `eta = 3` keeps both decoupled blocks SPD yet flips `det(S) < 0` (`inertia(M) = [5, 0, 1]`, explicit exact witness `v^T M v = -464071/1247200 < 0` -> `REFUSE_SCHUR_NEGATIVE_INERTIA`).
3. **Pillar 3 — `Proposals 1–8` $K_8$ 5-Org Interlocking Graph & 3-Node Execution Plan:** Verifies `28/28` Schur compounding (`c_eff = 4`, `R_eff = 1/4`, Foster sum `= 7`), `70/70` tetrahedral Bianchi `= 0`, `4|4` Physical-vs-Digital silo cut (`16` edges, `lambda_2: 8 -> 0`), and strict 5-org (`1/31`) + 3-node (`1/7`) Borromean closure.
4. **Pillar 4 — Pure-`Init` Lean `4.36.0` Companion & R12 Verification Gate:** `OptiFabFiveOrgConvergence.lean` (`18/18` universal theorems) verified by field-complete `SEC`/`FR0`/`FR1` replay, R12 static + live scrubbed `lean --stdin` verifier, and zero-skip R5 test suite.

## Honest Scope & Novelty Classification (`N1`)

- **Novelty Classification:** **`N1`** (`n2_claims = 0`; `2` `N0` elementary algebraic/graph components, `4` `N1` cross-domain synthesis pillars). No new physical hardware measurements or autonomous plant actuation are claimed.

## Files

- `OptiFabFiveOrgConvergence.lean` — `18/18` universal pure-`Init` Lean `4.36.0` theorems (`0` external imports, `0` warnings)
- `lean-toolchain` / `lakefile.toml` — Pinned `leanprover/lean4:v4.36.0` build specification
- `s99_optifab_convergence_oracle.py` — Pure-$\mathbb{Z}/\mathbb{Q}$ exact oracle and canonical certificate builder
- `verify_s99_optifab_convergence.py` — Zone-B hardened standalone verifier, field-complete `SEC`/`FR0`/`FR1` auditor, R12 static Lean scanner, and live scrubbed `lean --stdin` kernel verifier
- `s99_optifab_convergence_audit.py` — `*_audit.py` CLI wrapper for `evidence-tracks` CI discovery
- `s99_optifab_convergence_certificate.json` — Committed canonical zero-float certificate (`25,892` bytes)
- `test_s99_optifab_convergence_r5.py` — Assertion-free verification, tamper, Zone-B, R12 Lean gate, and live Lean test suite (`0` skips)
- `REPORT.md` — Complete 4-pillar technical ledger and file manifest

## Quickstart

```bash
# Verify certificate, full deterministic replay, and live Lean 4.36.0 kernel (18/18 theorems)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s99_optifab_convergence.py --check s99_optifab_convergence_certificate.json --json

# Run CI audit wrapper
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B s99_optifab_convergence_audit.py --check s99_optifab_convergence_certificate.json

# Run full test suite across all three isolated Python modes
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B test_s99_optifab_convergence_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -O -B test_s99_optifab_convergence_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B -W error test_s99_optifab_convergence_r5.py
```
