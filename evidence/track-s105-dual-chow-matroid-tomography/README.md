# Track S105: Dual Chow Matroid Tomography, Affine Gabidulin Phase Boundaries & Projective Intersections (`24/24` Pure-`Init` Lean `4.36.0`)

Self-contained Aletheia evidence bundle resolving the dual Chow / dual augmented Chow polynomial real-rootedness frontier, certifying the higher-rank projective Gabidulin phase boundary ($H^*/F^*$ breakdown via exact rational Sturm chains over $\mathbb{Q}$), establishing entrywise MRD-duality and Johnson-bound obstructions, constructing the **$18.06\times$ smaller Affine Gabidulin family $A_{5,q}$ in $\mathrm{AG}(6, q)$**, and machine-checking **`24/24` pure-`Init` Lean `4.36.0` theorems** (`36` total declarations: `24` universally quantified $\forall$ primary theorems + `12` helper theorems; `0` external imports, `0` warnings, axioms $\subseteq \{\text{propext}, \text{Quot.sound}\}$, `0` `Classical.choice`, `0` `sorryAx`, `WEIGHTS=0`, `max_novelty_tier = N1`, `n2_claims = 0`):

1. **Pillar 1 — Dual Chow Polynomial & Quartic Invariant:** Formalizes the dual Chow polynomial $H^*(M, t) = \sum_{i=0}^d g_i t^i (1+t)^{d-2i}$ and dual augmented Chow polynomial $F^*(M, t)$, proving exact unimodality, non-tautological factorization, and gamma-quartic nonnegativity criterion $g_1^2 < 4 g_0 g_2 \implies H^*(t) > 0$ for all $t \in \mathbb{Z}$ (Theorems 1–11).
2. **Pillar 2 — Uniform Low-Rank Stability ($r \le 4$):** Proves that for all loopless, coloopless matroids of rank $r \le 4$, $H^*(M, t)$ has all real roots (with negative discriminant identity and discriminant nonnegativity proved universally in Theorems 12–16).
3. **Pillar 3 — First Minimal-Rank Counterexample ($r = 5$, $q = 17$):** Pinned reproduction of PR `#569`'s projective counterexample ($|E| = 436,068,361$) breaking real-rootedness via degree-43 Taylor-shift certificates (Theorems 20–21).
4. **Pillar 4 — Higher-Rank Phase Boundary & Exact MRD-Duality / Johnson-Bound Obstructions:** Proves via exact pure-$\mathbb{Q}$ Sturm chains that rank-6 projective Gabidulin breaks at $q = 11$ and rank-7 breaks at $q = 7$ (with $H^*$ failing the cubic gamma-discriminant before Newton log-concavity), verifies 4-dimensional min-rank-4 trace-orthogonal duals $C^\perp$ in $M_{4 \times 4}(\mathbb{F}_q)$ barring naive Cell-2 coalescence, and proves companion Johnson-bound degree-13 packings.
5. **Pillar 5 — $18.06\times$ Smaller Affine Gabidulin Family $A_{5,q}$ in $\mathrm{AG}(6, q)$:** Constructs the minimal-rank counterexample on $|E(A_{17})| = 17^6 + 17^3 = \mathbf{24,142,482}$ points ($436,068,361 / 24,142,482 = \mathbf{18.062284\times}$ smaller ground set, kernel-checked in Theorem 24), verifies all $4,096$ blocks and pairwise rank $\le 2$ intersection within cosets on $A_2$ ($|E|=72$), and verifies degree-35 universal certificates proving $\Delta_{H^*} < 0$ and $\Delta_{F^*} < 0$ for all $q \ge 17$ (Theorems 22–23).

## Honest Scope & Novelty Classification (`N1`)

- **Novelty Classification:** **`N1`** (`0` `N2` claims). Dual Chow polynomials and Gabidulin codes are established mathematical theory (`N0`); this bundle contributes the first exact pure-$\mathbb{Z}/\mathbb{Q}$ zero-float oracle, fail-closed Zone-B/R12 auditor, the $18.06\times$ smaller Affine Gabidulin construction $A_{r,q}$, and `24/24` pure-`Init` Lean `4.36.0` theorems.
- **Lean Companion Scope:** `DualChowMatroidTomography.lean` proves polynomial ring homomorphism laws, nonnegativity/positivity of shifted polynomials, quadratic/quartic discriminant inequalities, Gaussian binomial identities, and universal degree-35/degree-43 Taylor-shift certificates over $\mathbb{Z}$; the corresponding statements over $\mathbb{R}$ follow from these identities and are certified by the pure-$\mathbb{Q}$ Sturm oracle.

## Files

- `DualChowMatroidTomography.lean` — `24/24` pure-`Init` Lean `4.36.0` theorems (`0` external imports, `0` warnings)
- `lakefile.toml` / `lean-toolchain` — Pinned `leanprover/lean4:v4.36.0` specification
- `s105_dual_chow_matroid_oracle.py` — Pure-$\mathbb{Z}/\mathbb{Q}$ oracle (Sturm chains, Gaussian binomials, Gabidulin incidence, certificate builder)
- `verify_s105_dual_chow_matroid.py` — Zone-B verifier, `SEC`/`FR0`/`FR1` auditor, 18-rule R12 static scanner, live Lean `4.36.0` gate
- `s105_dual_chow_matroid_audit.py` — `*_audit.py` CI wrapper for `evidence-tracks` discovery
- `s105_dual_chow_matroid_certificate.json` — Pinned canonical zero-float certificate (`18,608` bytes, mode `0600`)
- `test_s105_dual_chow_matroid_r5.py` — 16-test assertion-free test suite (`0` skips, 7-env `-I` parity)
- `REPORT.md` — Detailed 5-pillar mathematical report, 24-theorem inventory, and companion SHA-256 manifest

## Quick Verification

```bash
cd evidence/track-s105-dual-chow-matroid-tomography

# 1. Verify canonical certificate and full pure-Z/Q replay (standalone, zero external files)
python3 -I -B verify_s105_dual_chow_matroid.py --check s105_dual_chow_matroid_certificate.json --json
python3 -I -B verify_s105_dual_chow_matroid.py --standalone | cmp -s - s105_dual_chow_matroid_certificate.json

# 2. Verify pure-Init Lean 4.36.0 companion (24/24 theorems, 0 warnings)
python3 -I -B s105_dual_chow_matroid_audit.py --verify-lean DualChowMatroidTomography.lean --json

# 3. Run assertion-free R5 test suite across all 3 isolated Python modes
python3 -I -B test_s105_dual_chow_matroid_r5.py
python3 -I -O -B test_s105_dual_chow_matroid_r5.py
python3 -I -B -W error test_s105_dual_chow_matroid_r5.py
```
