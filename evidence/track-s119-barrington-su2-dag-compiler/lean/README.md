# Spinor-Barrington $2I \subset SU(2)$ Theorems (`#46–#48`) — Pure-`Init` Lean 4.36.0 (`46 -> 49/49`)

Pure-`Init` `Lean 4.36.0` formalization of the exact $\mathbb{Z}[\sqrt{5}]$ Spinor-Barrington $2I \cong SL(2, 5) \subset SU(2)$ algebra from `Track S119`, expanding the verified HoloSphere theorem library from `46` to **`49/49` zero-`Classical.choice` theorems** (`0` external imports, `0` Mathlib, `0` IEEE-754 floats, `0` `Classical.choice`, `0` `Lean.ofReduceBool` / `native_decide`, `0` `sorryAx`, `0` warnings).

## Theorem Catalog (`HoloSphereSpinorBarrington.lean`)

| # | Lean 4 Theorem | Axioms | Exact Algebraic Statement & Hardware Consequence |
|---|---|---|---|
| 46 | `p46_spinor_barrington_c10_exact_closure` | `[]` *(zero axioms!)* | Over scale-`4` $\mathbb{Z}[\sqrt{5}]$ quaternions (`normSq = 16`): exact unit norms for `τ0`, `gα`, `gβ`; exact spinor order `10` (`τ0^5 = -I`, `τ0^10 = +I`, proper divisors `≠ +I`); lossless scale-`4` integrality + exact sign-free `AND` commutator `[gα τ0 gα†, gβ τ0 gβ†] = +τ0` (`0` sign canonicalization, `0` `-I` leakage); and full `{+I, +τ0}` `AND`/`NOT` truth table. |
| 47 | `p47_su2_commutator_trace_and_order5_obstruction` | `[propext, Quot.sound]` | Proves universally over **both `QuatZ` (`Int`) and `QuatZ5` ($\mathbb{Z}[\sqrt{5}]$)** that $\mathrm{Re}(a b \bar{a} \bar{b}) = \|a\|^2 \|b\|^2 - 2 \|\vec{a} \times \vec{b}\|^2$, and proves the order-`5` $\mathbb{Z}_2$ spinor obstruction on `σ0 = -τ0` (`σ0^5 = +I`): `[gα σ0 gα†, gβ σ0 gβ†] = +τ0 = -σ0 ≠ +σ0` (`Re(σ0) < 0 < Re(+τ0)`). |
| 48 | `p48_spinor_barrington_acute_cayley_ball` | `[propext, Quot.sound]` | Proves order asymmetry of `z5Pos`, tight rational bracketing $223/100 < \sqrt{5} < 224/100$, strict acute $q_0 > 0$ and cleared-denominator Cayley bounded-ball $25 \|\vec{Q}\|^2 < 16 (4 + Q_0)^2$ ($\|\omega\| < 4/5 = 0.8$) for `τ0`, `gα`, `gβ`, `α`, and `β`, plus exact radii $\|\omega(\tau_0)\|^2 = (5 - 2\sqrt{5})/5 < 16/25$ and $\|\omega(g_\beta)\|^2 = 1/3 < 16/25$. |

## Reproducible CPU-Only Verification

```bash
python3 -I -B lean/verify_s119_lean_r5.py --verify-lean
python3 -I -B lean/verify_s119_lean_r5.py -v
python3 -I -O -B lean/verify_s119_lean_r5.py -v
python3 -I -B -W error lean/verify_s119_lean_r5.py -v
```
