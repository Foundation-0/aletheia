# Track S110 Stage 3: Geosphere Weft Conservation (`38/38` Pure-`Init` Lean `4.36.0` Theorems)

Self-contained Aletheia evidence bundle certifying the exact pure-$\mathbb{Z}/\mathbb{Q}$ conservation laws, Law-5 mathematical obstructions, and `Weft-Smith` safety state machine for the coupled Planetary Architecture across four formal pillars (**`38/38` pure-`Init` `Lean 4.36.0` kernel-checked theorems**, `0` external imports, `0` warnings, `4 [] + 2 [propext] + 32 [propext, Quot.sound]`, `0` `Classical.choice`, `0` `sorryAx`, `WEIGHTS=0`, `max_novelty_tier = N1`, `n2_claims = 0`):

1. **Pillar 1 — Core Geodynamo Lorentz Isometry & Exact Rational Cayley Transport (Theorems 1–8):** Arbitrary-dimension skew-symmetric worklessness ($\langle h, \Omega h\rangle = 0$), exact cleared-denominator Cayley norm preservation ($\|y\|^2 = \|x\|^2$), low-rank $O(d)$ Woodbury generators, closed-form `2×2` block-diagonal Cayley (`4` FMAs per pair, zero matrix inversion), universal Pfaffian positivity $\det(I_4 + \Omega) \ge 1$, and explicit $SO(4)$/Hopf quaternion Cayley isometry.
2. **Pillar 2 — Oceanic Mass Conservation, Law-5 `B1` Causal Collapse, $O(n)\cap B_n$ & Darcy Contraction (Theorems 9–17):** Column-stochastic bidirectional mass conservation, exact Law-5 obstruction `B1` proving any causal lower-triangular doubly-stochastic matrix is identically $D \cdot I_n$ (Sinkhorn attention collapse), $O(n)\cap B_n \subseteq \mathrm{Perm}(n)$ permutation-only restriction, non-commuting $SO(2)$ rotation vs Birkhoff transport, and Darcy porous aquifer EMA contraction with explicit `M1` unbounded-$K$ escape obstruction.
3. **Pillar 3 — Bingham Viscoplasticity, Repaired Vector-Proximal $\mathcal{S}_Y^H(u)$ & Ozone/Channel-2B Airlock (Theorems 18–28):** Scalar Bingham proximal odd symmetry, sub-yield plug-flow zero-leakage, $L^2$ contraction, strict shrinkage, monotone 1-Lipschitz regularity, $\tau_{\max}$ Stagnant Lid vs `B5` $\sigma$-leak, council-repaired Vector-Proximal Poloidal Bingham $\mathcal{S}_Y^H(u)$ preserving Poloidal/Toroidal Hodge orthogonality, Pythagorean energy contraction without post-renorm, and exact $SO(k)$ equivariance, plus constructive arbitrary-dimension Cauchy–Schwarz and Channel-2B frozen-weight airlock bounds.
4. **Pillar 4 — `Weft-Smith` (`PREREG-S111`) Composed Triple Gate, Cumulative `C_row` & `O(1)` Rollback (Theorems 29–38):** Arbitrary-dimension Householder reflection invariance of $C_{\text{row}}(\Delta W)$, universal Law-5 $C_{\text{row}}$ cancellation obstruction proving composed gating necessity ($(a, a) + (a, -a) = (2a, 0)$), Shell-1/Shell-2 capability isolation ($\Delta W_{\text{core}} = 0 \land \Delta\psi = 0$), non-generative mask preservation, bit-exact $O(1)$ rollback on gate failure (`post = pre`), triple-gate non-redundancy, and multi-cycle cumulative drift / $C_{\text{row}}$ / `kvEpoch` ledger safety.

## Quick Verification

```bash
cd evidence/track-s110-geosphere-weft-conservation

# 1. Zero-skip R5 suite across all 3 isolated R4 modes
python3 -I -B test_s110_geosphere_weft_r5.py
python3 -I -O -B test_s110_geosphere_weft_r5.py
python3 -I -B -W error test_s110_geosphere_weft_r5.py

# 2. Standalone byte-exact certificate replay + CI audit check
python3 -I -B s110_geosphere_weft_audit.py --standalone | cmp -s - s110_geosphere_weft_certificate.json
python3 -I -B s110_geosphere_weft_audit.py --check s110_geosphere_weft_certificate.json --json

# 3. Live pure-Init Lean 4.36.0 kernel verification (38/38 theorems)
python3 -I -B s110_geosphere_weft_audit.py --verify-lean GeosphereWeftConservation.lean --json

# 4. Pinned external preregistration verification (4/4 protocols)
python3 -I -B s110_geosphere_weft_audit.py --verify-pins
```

See [`REPORT.md`](REPORT.md) for the complete mathematical specification, `38/38` theorem inventory, adversarial hardening receipts (`140/140` AST mutation kill, `28/28` AST `BoolOp` kill, `82/82` direct 4-surface `zone_b_fuzzer`, `705/705` leaf sweep), and frozen companion SHA-256 manifest.
