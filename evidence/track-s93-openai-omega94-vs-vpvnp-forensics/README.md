# Exact Pure-$\mathbb{Z}/\mathbb{Q}$ Forensic & `CAT(0)` Geometry Tomography of $\omega_F = 9/4$ & `SpectralFlatLaw` vs. `pequalnp-proofs` & `vp-vnp` (`18/18` Pure-`Init` Lean `4.36.0`)

Self-contained Aletheia evidence bundle providing exact pure-$\mathbb{Z}/\mathbb{Q}$ operator analysis, live forensic statement-fidelity and trust-gate (`T-13..T-15`) verification, Law-5 `CAT(0)` negative-Gram reconciliation, and **`18/18` universally quantified pure-`Init` Lean `4.36.0` theorems** (`0` external imports, `0` warnings, `2` `[]` + `1` `[propext]` + `15` `[propext, Quot.sound]`, `0` `Classical.choice`, `0` `sorryAx`):

1. **Pillar 1 — Exact Pure-$\mathbb{Q}$ Rectangular Matrix Multiplication Formula $\omega_F(a,b,c)$:** Verifies square exponent $\omega_F(1,1,1) = 9/4$, dual exponent $\alpha_F = 1/2$ (exact $O(n^2)$ flat regime vs strict penalty $(2t-1)^2/(4t)$), $6/6$ $S_3$ permutation invariance, harmonic flat threshold $xy/(x+y)$, strict midpoint Jensen convexity, historical rational benchmark ordering, and finite-size $n = k^4$ rank and nonscalar gate floors.
2. **Pillar 2 — Live Forensic Trust & Statement-Fidelity Audit (`T-13..T-15`):** Resolves the dual-model structure in `openai/math` (`ComparatorChallenges/MatrixExponent.lean` division-free `MvPolynomial` stubs vs internal `RationalCircuits.lean` + `FieldFormula.lean` `Build.div` proofs) and `open-goat/pequalnp-proofs` (`CheckLemma.lean` + `outside-guard.mjs`), recording honest single-kernel `T-14 = False` grading where no independent `nanoda` receipt exists.
3. **Pillar 3 — Exact Law-5 `CAT(0)` Reconciliation (`SpectralFlatLaw` vs. `vp-vnp` `Rem D.3` & `Thm D.2`):** Proves Euclidean charts enforce ratio $P / (P/2) = 2 < 9/4$, while both OpenAI's unit-arm `CAT(0)` tripod (`det G = -4 < 0`, $v^\top G v = -3 < 0$, CN slack `2 > 0`, ratio `9/4`) and Anthropic `vp-vnp` `Rem D.3`'s $\mathrm{Mat}_2(\mathbb{F}_2)$ witness (`det G = -1/4 < 0`, $u^\top G u = -1 < 0$) exhibit the identical negative-Gram non-Euclidean obstruction signature.
4. **Pillar 4 — `pequalnp.com/papers/note-1` (`10` Edge-Function Bounds), `CircuitLowerBounds` Helpers & Pure-`Init` Lean `4.36.0` Companion:** Pins all `10` `MetaComplexity/L*.lean` bounds, exact $C_4$ biclique 3-gate collapse (`16/16` truth table), `5` helper modules (`Depth3`, `Discriminator`, `Lindsey`, `ParitySmol`, `SatFive`), and `18/18` universal Lean `4.36.0` theorems verified via field-complete `SEC`/`FR0`/`FR1` replay, R12 static scanning (blocking `\bLean\.` and `Char := '"'` quote-desync bypasses), and strict 5-key env-allowlisted live `lean --stdin` elaboration.

## Honest Scope & Novelty Classification (`N0`/`N1`)

- **Novelty Classification:** **`N1`** (`N0` published monuments in `openai/math`, `open-goat/pequalnp-proofs`, and `vp-vnp`, read strictly read-only with zero external repository copies; `N1` exact pure-$\mathbb{Z}/\mathbb{Q}$ synthesis, forensic audit, negative-Gram reconciliation, and `18/18` pure-`Init` Lean `4.36.0` companion).

## Files

- `OmegaNineFourthsAndSpectrum.lean` — `18/18` universal pure-`Init` Lean `4.36.0` theorems (`0` external imports, `0` warnings)
- `lean-toolchain` / `lakefile.toml` — Pinned `leanprover/lean4:v4.36.0` build specification
- `s93_omega94_vpvnp_oracle.py` — Pure-$\mathbb{Z}/\mathbb{Q}$ exact oracle and canonical certificate builder
- `verify_s93_omega94_vpvnp.py` — Zone-B hardened verifier, field-complete `SEC`/`FR0`/`FR1` auditor, R12 static Lean scanner, and strict 5-key env-allowlisted live `lean --stdin` verifier
- `s93_omega94_vpvnp_audit.py` — `*_audit.py` CLI wrapper for `evidence-tracks` CI discovery
- `s93_omega94_vpvnp_certificate.json` — Committed canonical zero-float certificate (`21,800` bytes)
- `test_s93_omega94_vpvnp_r5.py` — Assertion-free verification, tamper, Zone-B, R12 Lean gate, env-allowlist, and live Lean test suite (`0` skips)
- `REPORT.md` — Complete 4-pillar forensic ledger, theorem table, and frozen file manifest

## Quickstart

```bash
# Verify certificate, full deterministic replay, and live Lean 4.36.0 kernel (18/18 theorems)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s93_omega94_vpvnp.py --check s93_omega94_vpvnp_certificate.json --json

# Run CI audit wrapper
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B s93_omega94_vpvnp_audit.py --check s93_omega94_vpvnp_certificate.json

# Run full test suite across all three isolated Python modes
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B test_s93_omega94_vpvnp_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -O -B test_s93_omega94_vpvnp_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B -W error test_s93_omega94_vpvnp_r5.py
```
