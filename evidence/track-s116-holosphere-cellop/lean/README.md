# HoloSphere `CellOp` Co-Design Invariants — Pure-`Init` Lean 4.36.0 (`#37–#40` + `#40b`)

Staged pure-`Init` `Lean 4.36.0` proofs for `Moissanite-Labs/holosphere` (`PR #2` candidate), mechanizing the mathematical cornerstones of the `CellOp` persistent megakernel co-design (`0` external imports, `0` Mathlib, `0` `Classical.choice`, `0` `Lean.ofReduceBool` / `native_decide`, `0` `sorryAx`, `0` warnings).

## Theorem Catalog (`HoloSphereCellOpInvariants.lean`)

| # | Lean 4 Theorem | Axioms | Exact Algebraic Statement & Hardware Consequence |
|---|---|---|---|
| 37 | `p1_blockh4_involutory_and_int8_bounds` | `[propext, Quot.sound]` | For all signed 4-bit nibbles `-8 ≤ u_i ≤ 7`: `H_4(H_4 u) = 4 u` (justifying exact `0.5 *` involutory scale), `‖H_4 u‖² = 4‖u‖²`, tight componentwise `int8` bounds `-32 ≤ r_k ≤ 30`, and boundary witnesses `(-8,-8,-8,-8) → (-32,0,0,0)`, `(7,7,7,7) → (28,0,0,0)`, `(7,-8,7,-8) → (-2,30,0,0)`. |
| 38 | `p2_cayley_unit_ball_so3_involution_and_even` | `[propext, Quot.sound]` | For unit-norm `‖w‖² = 1` (and homogeneous rational `‖w‖² = d²` for `w/d ∈ ℚ³`), `cayleyHomNum(d, w)` has exact scalar part `0` and square `(-4 d⁴, 0, 0, 0)` (`180°` `SO(3)` involution at finite `‖w‖ = 1`), `so3Adj(-q) = so3Adj(q)` (`±I` evenness covering `A_5 = 2I/{±I}` in 1 step), and `q (0, v) q̄ = (0, so3Act q v)`. |
| 39 | `p3_cayley_exact_inverse_reversibility` | `[propext, Quot.sound]` | Proves `0 < 1 + ‖w‖²`, exact algebraic inverse `qmul (cayleyNum w) (cayleyNum (-w)) = ((1 + ‖w‖²)², 0, 0, 0)` (and homogeneous `((d² + ‖w‖²)², 0, 0, 0)`), and `κ = 1` `O(1)`-VRAM backward holonomy recovery `q(-w) (q(w) U) = (d² + ‖w‖²)² U`. |
| 40 | `p4_hadamard256_byte_orthogonality` | `[propext, Quot.sound]` | Proves by `k`-bit character-sum induction (`0` `native_decide`) over both `Fin 256` and `UInt8` that `∑_{d=0}^{255} (-1)^{popc(b_1 ∧ d)} (-1)^{popc(b_2 ∧ d)} = 256 δ_{b_1, b_2}`, with `127 e_d ∈ [-128, 127]` (`e_d² = 16,129`, row norm² `= 4,129,024`). |
| 40b | `p4b_bent_phase_preserves_orthogonality` | `[propext, Quot.sound]` | Proves that multiplying `H_256` channels by any `±1` diagonal sign `s(d)² = 1` — and specifically the Maiorana–McFarland bent phase `bent4(d)` (`0/2048` constant warps) — preserves `100%` exact `256 × 256` pairwise orthogonality over `Fin 256` and `UInt8`. |

## Reproducible CPU-Only Verification

```bash
python3 -I -B lean/verify_cellop_lean.py --verify-lean
python3 -I -B lean/test_cellop_lean_r5.py -v
python3 -I -O -B lean/test_cellop_lean_r5.py -v
python3 -I -B -W error lean/test_cellop_lean_r5.py -v
```
