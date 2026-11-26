# Forensic Audit of `Foundation-0/exoplanets-frontier` & Public Astronomy Spine + Exact Verification Operators (`19/19` Pure-`Init` Lean `4.36.0`)

Self-contained Aletheia evidence bundle combining a live multi-branch/multi-PR forensic audit of `Foundation-0/exoplanets-frontier` and `6` related public astronomy repositories with exact pure-$\mathbb{Z}/\mathbb{Q}$ astrophysical verification operators and **`19/19` universal pure-`Init` Lean `4.36.0` theorems** (`0` Mathlib, `0` imports, `0` warnings, `0` banned axioms: `1` `[]`, `18` `[propext, Quot.sound]`):

1. **Pillar 1 — Multi-Branch & Multi-PR Forensic Audit (`Foundation-0/exoplanets-frontier`):** Audits `main @ 3bc0163b...`, `4` non-main branches, and open PRs `#13`, `#8`, `#6` (plus closed `#7`); diagnoses the `cool_vet.py:2` `SyntaxError`, `cool_vet.py:114-115` duplicate `main()` root-causing `6` orphan PNGs, `3/6` stale inline SHA-256 prefixes in `CLAIMS.md` vs `41/41` valid `results/convergence_certificates.json` pins, `39`-pair out-of-sample `S106-S107` breakdown (`22` confirmed, `5` marginal, `1` TTV, `9` low-SNR inconclusive, `0` non-detection, `2` data gap), and `6` code bugs + `3` astrophysical/statistical vetter blind spots.
2. **Pillar 2 — Pure-$\mathbb{Z}/\mathbb{Q}$ Exact Astrophysical Verification Operators:** Re-derives exact two-stage BLS sharpening (`145/3 = 48.333333x`, `36,018` Nyquist bins), unimodular Farey separation hitting `< 1/125` (`1/132 = 0.007576`), narrow-window `CS-09` SDE truncation (`MES = 50`, `SDE = 10 -> 7 < 15/2`), Pont red-noise $\beta = 2$ MES collapse (`14 -> 7`), 8-gate Bayes FPP (`0.002272 < 0.015`) vs 4-gate correlated-failure Law-5 breach (`0.225682 >= 0.015`, `128x` odds blowup), asymmetric Huber 1-bin masked IRLS spot pre-whitening + 2-bin phase-lock rank collapse (`det = 0`), 5-epoch orthogonal Legendre O-C decomposition, and 2D affine WCS equivariance + BEB physical exclusion (`201/100 > 1`).
3. **Pillar 3 — Public Astronomy Spine & Aletheia Gate Convergence:** Maps `7/7` strictly public repositories (`Foundation-0/exoplanets-frontier`, `astr0`, `gaia-dr4`, `lost-eclipses`, `certified-orbits`, `cosmic-denoising`, `eumemic/exoplanets`) and connects `CS-09`, `CS-18`, and Pont-$\beta$ variance inflation back to Aletheia's fail-closed gates.
4. **Pillar 4 — Pure-`Init` Lean `4.36.0` Companion (`ExoplanetsFrontierOperators.lean`):** `19/19` universally quantified (`∀`) pure-`Init` theorems covering Farey separation, SDE monotonicity/truncation, Pont $\beta$ scaling, 8-gate conjunction, Bayes FPP monotonicity under shared correlated failure (Thm 19), Huber OLS attenuation and rank collapse, Legendre O-C orthogonality, affine WCS equivariance, and BEB physical exclusion.

## Honest Scope & Novelty Classification (`N1`)

- **Novelty Classification:** **`N1`** (`n2_claims = 0`; `exact` pure-$\mathbb{Z}/\mathbb{Q}$ oracle). Classical BLS, Pont red-noise $\beta$, Bayes FPP, Huber IRLS, and Legendre O-C decompositions are established astrophysics foundations (`N0`). The contribution here is a reproducible, live-pinned forensic audit and pure-$\mathbb{Z}/\mathbb{Q}$ + pure-`Init` Lean `4.36.0` verification suite unifying those gates with fail-closed `SEC`/`FR0`/`FR1` replay and R12 Lean hardening.

## Files

- `ExoplanetsFrontierOperators.lean` — `19/19` universal pure-`Init` Lean `4.36.0` theorems (`0` external imports, `0` warnings)
- `lean-toolchain` / `lakefile.toml` — Pinned `leanprover/lean4:v4.36.0` build specification
- `s103_exoplanets_oracle.py` — Pure-$\mathbb{Z}/\mathbb{Q}$ exact oracle and canonical certificate builder
- `verify_s103_exoplanets.py` — Zone-B hardened standalone verifier, field-complete `SEC`/`FR0`/`FR1` auditor, R12 static Lean scanner, and live scrubbed `lean --stdin` kernel verifier
- `s103_exoplanets_audit.py` — `*_audit.py` CLI wrapper for `evidence-tracks` CI discovery
- `s103_exoplanets_certificate.json` — Committed canonical zero-float certificate (`14,992` bytes)
- `test_s103_exoplanets_r5.py` — Assertion-free verification, tamper, Zone-B, R12 Lean gate, and live Lean test suite (`0` skips)
- `REPORT.md` — Complete 4-pillar forensic ledger, exact operator tables, and file manifest

## Quickstart

```bash
# Verify certificate, full deterministic replay, and live Lean 4.36.0 kernel (19/19 theorems)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s103_exoplanets.py --check s103_exoplanets_certificate.json --json

# Run CI audit wrapper
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B s103_exoplanets_audit.py --check s103_exoplanets_certificate.json

# Run full test suite across all three isolated Python modes
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B test_s103_exoplanets_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -O -B test_s103_exoplanets_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B -W error test_s103_exoplanets_r5.py
```
