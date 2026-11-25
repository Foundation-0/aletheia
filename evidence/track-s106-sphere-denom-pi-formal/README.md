# Track S106 Phase 1A — Hypersphere Geometry, Denominator-$\pi$ Equal-Sphere-Fraction `EQ(S^{d-1})`, EM/Hodge Splitting, & Paired `H2b` Physics Benchmarks

Self-contained Aletheia evidence bundle providing an exact pure-$\mathbb{Z}/\mathbb{Q}$ mathematical framework, 30-digit deterministic `Decimal` analytical physics benchmarks, and **`34/34` universal pure-`Init` Lean `4.36.0` theorems** (`0` external imports, `0` warnings, `0` `sorryAx`, `0` `Classical.choice`: `3` `[]`, `2` `[propext]`, `29` `[propext, Quot.sound]`):

1. **Pillar 1 — Sphere-Unit Coordinates & Graded-Period $\mathbb{Q}[\pi]$ Algebra:** Maps dimensionless ball second moments to the pure rational sequence $G_{\mathrm{su}}(B^d) = \frac{1}{d+2}$ (`1/4, 1/6, 1/8, 1/10...`), proves exact $\pi^k$ surface-to-volume ratio cancellation $\omega_{2k-1} / \operatorname{Vol}(B^{2k}) = 2k = d$, and proves universally for all even dimensions $d = 2k \ge 2$ that $B^{2k}$ strictly beats the $2k$-cube in Zador moment using only $\pi > 314/100$.
2. **Pillar 2 — Cleared-Denominator EM / Hodge Orthogonal Splitting over $\mathbb{Z}^d$:** Proves arbitrary-dimension cleared-component exact reconstruction $\delta_\parallel^{\mathrm{cl}} + \delta_\perp^{\mathrm{cl}} = S \delta$, exact orthogonality $\langle x, \delta_\perp^{\mathrm{cl}} \rangle = 0$, exact Pythagorean decomposition $S^2 \|\delta\|^2 = \|\delta_\parallel^{\mathrm{cl}}\|^2 + \|\delta_\perp^{\mathrm{cl}}\|^2$, radial-rescaling $c^4$-homogeneity $D_{\lambda_\perp}(cx, \delta) = c^4 D_{\lambda_\perp}(x, \delta)$ establishing scale-invariant direction selection, and zero transverse leakage under radial error.
3. **Pillar 3 — Denominator-$\pi$ Equal-Sphere-Fraction `EQ(S^{d-1})` & $2^B$ Slot-Waste Obstructions:** Establishes exact coordinate maps $z \in [-1,1] \mapsto \sqrt{1-z^2}$ on $S^2$ and $u \in [0,1] \mapsto \sqrt{u(1-u)}$ on $S^3$, proves Hopf $S^3$ linear and quadratic midpoint moment laws, and proves the universal $2^B$ slot-waste obstruction $\forall b,\; 3 \nmid 2^b \wedge 5 \nmid 2^b$ (Lean: $2^b \ne 24, 120, 240, 2400, 196560$), with certificate slot utilization `D4` 24-cell `24/32` (8 wasted, `1/4`), `H4` 600-cell `120/128` (8 wasted, `1/16`), `E8` shell-1 `240/256` (16 wasted, `1/16`) vs `DenomPi_EQ` `0` wasted.
4. **Pillar 4 — Hypersphere Thin-Shell Concentration & Coxeter/Weyl Order Arithmetic:** Proves exact squared radial width $\mathrm{CV}^2(d) = 1/(2d)$ and $\chi^2_d$ relative variance $2/d$ strictly decreasing in $d$ (Chebyshev thin-shell monotonicity, Lean Theorem 26), and exact Coxeter/Weyl group orders $|W(B_d)| = 2^d d!$, $|W(H_3)| = 120$, $|W(H_4)| = 14400 = 120^2$, $|W(E_8)| = 696729600$ with $[W(E_8):W(D_8)] = 135$ (Lean Theorems 27–30).
5. **Pillar 5 — Paired Analytical Physics Benchmarks (`H2b`) & Honest `PARTIAL` Verdict:** Deterministic zero-float 30-digit `Decimal` execution of matched-node $N \in \{64, 256, 1024\}$ benchmarks on 3D electrostatics ($S^2$) and Fock–Moser regularized Hydrogen/Kepler ($S^3$); confirms decisive superiority over equal-weight Numerator-$\pi$ grids (`27×`–`463×` and exact zero on `1s/2s/2p`) and equal-weight box projections (`12×`–`40×`), while honestly identifying the endpoint derivative singularity obstruction of tensor-product equal-area maps vs. smooth Jacobian-weighted quadrature, isolating exact scope.

## Honest Scope & Novelty Classification (`N1`)

- **Novelty Classification:** **`N1`** (`n2_claims = 0`). Archimedes' Hat-Box projection on $S^2$, Hopf's $S^3$ fibration, Zador's ball second moment, Fock–Moser $SO(4)$ Hydrogen/Kepler regularization, Gauss–Legendre quadrature, Fibonacci lattices, Halton QMC, and the 600-cell spherical 11-design are established prior art (`N0`). This bundle's contribution is a reproducible zero-float pure-$\mathbb{Z}/\mathbb{Q}$ oracle, fail-closed Zone-B/R12 verifier, and `34`-theorem pure-`Init` Lean `4.36.0` formalization unifying those laws under strict Law-4/Law-5 honesty.

## Files

- `SphereDenomPiOperators.lean` — `34/34` pure-`Init` Lean `4.36.0` theorems (`0` external imports, `0` warnings)
- `lean-toolchain` / `lakefile.toml` — Pinned `leanprover/lean4:v4.36.0` build specification
- `s106_sphere_denom_pi_oracle.py` — Pure-$\mathbb{Z}/\mathbb{Q}$ exact oracle and canonical zero-aliasing certificate builder
- `verify_s106_sphere_denom_pi.py` — Zone-B hardened standalone verifier, field-complete `SEC`/`FR0`/`FR1` auditor, `18`-rule R12 static Lean scanner, and live scrubbed `lean --stdin` kernel verifier
- `s106_sphere_denom_pi_audit.py` — `*_audit.py` CLI wrapper for `evidence-tracks` CI discovery
- `s106_formal_physics_certificate.json` — Committed canonical zero-float certificate (`20,592` bytes)
- `s106_physics_denom_pi_bench.py` — Zero-float 30-digit `Decimal` analytical physics testbed for `H2b` ($S^2$ and $S^3$)
- `test_s106_sphere_denom_pi_r5.py` — Assertion-free verification, every-leaf tamper (`690/690` leaves), Zone-B, R12 Lean gate, and live Lean test suite (`0` skips)
- `REPORT.md` — Complete technical report, verbatim `34/34` theorem index, analytical physics tables, and 7-companion-file SHA-256 manifest

## Quickstart

```bash
# Verify certificate, full deterministic replay, and live Lean 4.36.0 kernel (34/34 theorems)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s106_sphere_denom_pi.py --check s106_formal_physics_certificate.json --json

# Run live Lean 4.36.0 kernel check directly
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B s106_sphere_denom_pi_audit.py --verify-lean SphereDenomPiOperators.lean

# Run CI audit wrapper
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B s106_sphere_denom_pi_audit.py --check s106_formal_physics_certificate.json

# Run full test suite across all three isolated Python modes
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B test_s106_sphere_denom_pi_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -O -B test_s106_sphere_denom_pi_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B -W error test_s106_sphere_denom_pi_r5.py
```
