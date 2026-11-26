/-
  Track S48 — Theorem 4 (Portal 54 / Tracks S38 & S44):
  1. DeepMind CS-21 Classical-Control & Landauer Offloading Net-Regression Theorem:
       With exact rational boundary weights (w_T = 1, w_ctrl = 1/10, w_landauer = 1/2),
       scaled by common denominator 10:
         scaledCost(T, C, E) = 10 * T + C + 5 * E.
       Circuit A (Silq clean):       (T=400, C=10,   E=0)   -> full cost 401
       Circuit B (offloaded):        (T=100, C=4000, E=200) -> full cost 600 (5/6 hidden!)
       Circuit C (genuine speedup):  (T=100, C=20,   E=0)   -> full cost 102
       Proves 4x T-gate reduction hides 5/6 classical/Landauer cost yielding 600/401 > 1 net regression,
       plus universal parametric net-regression criterion for arbitrary circuits.
  2. Landauer Erasure Exact Rational Bracket for 2-input classical AND gate:
       From the exact Boolean truth table of AND, preimage fiber sizes are (3, 1),
       giving 2^(4 * H(X|Y)) = 3^3 * 1^1 = 27, proving strictly in pure integer arithmetic:
         19/16 < H(X|Y) < 6/5  (equivalently 2^19 < 27^4 and 27^5 < 2^24),
       contrasted against reversible 3-bit Toffoli (CCX) bijection (P = 1, H = 0)
       and 1-bit constant erasure (P = 4, H = 1).
-/

namespace AletheiaKernelCerts.Theorem4

/-! ### Part 1: CS-21 Classical-Control Offloading Net-Regression -/

/-- Exact boundary cost scaled by 10: 10 * (1 * T + (1/10) * C + (1/2) * E). -/
def scaledBoundaryCost (tGates ctrlOps erasedBits : Nat) : Nat :=
  10 * tGates + ctrlOps + 5 * erasedBits

/-- Exact offloaded (non-T-gate) classical + Landauer cost scaled by 10. -/
def scaledHiddenCost (ctrlOps erasedBits : Nat) : Nat :=
  ctrlOps + 5 * erasedBits

/-- Universal CS-21 net-regression theorem: apparent T-gate reduction causes strict full-cost regression
    whenever offloaded classical + Landauer boundary cost exceeds the T-gate savings. -/
theorem cs21_parametric_net_regression :
    ∀ (tA tB cA cB eA eB : Nat),
      tB < tA →
      scaledHiddenCost cB eB > scaledHiddenCost cA eA + 10 * (tA - tB) →
      scaledBoundaryCost tB cB eB > scaledBoundaryCost tA cA eA := by
  intro tA tB cA cB eA eB hT hHide
  unfold scaledBoundaryCost scaledHiddenCost at *
  omega

/-- Exact S44 CS-21 witness: 4x T-gate reduction hides 5/6 boundary cost, yielding 600/401 > 1 regression,
    while genuine speedup Circuit C drops full cost from 401 to 102. -/
theorem cs21_s44_offloading_witness :
    -- 4x apparent T-gate reduction (400 -> 100)
    400 = 4 * 100 ∧
    -- Exact full scaled costs (4010 = 10*401, 6000 = 10*600, 1020 = 10*102)
    scaledBoundaryCost 400 10 0 = 4010 ∧
    scaledBoundaryCost 100 4000 200 = 6000 ∧
    scaledBoundaryCost 100 20 0 = 1020 ∧
    -- Exact 5/6 hidden cost share on Circuit B: hidden / full = 5000 / 6000 = 5 / 6
    6 * scaledHiddenCost 4000 200 = 5 * scaledBoundaryCost 100 4000 200 ∧
    -- Exact net-regression ratio 600/401 > 1 (cross-multiplied)
    scaledBoundaryCost 100 4000 200 * 401 = 600 * scaledBoundaryCost 400 10 0 ∧
    scaledBoundaryCost 100 4000 200 > scaledBoundaryCost 400 10 0 ∧
    -- Genuine speedup negative control: Circuit C strictly beats Circuit A
    scaledBoundaryCost 100 20 0 < scaledBoundaryCost 400 10 0 := by
  unfold scaledBoundaryCost scaledHiddenCost
  omega

/-! ### Part 2: Landauer Erasure Rational Bracket 19/16 < H(X|Y) < 6/5 -/

/-- Exact integer entropy-power product 2^(N * H(X|Y)) = ∏_y |f⁻¹(y)|^(|f⁻¹(y)|) for a finite map. -/
def landauerPowerProduct {nIn nOut : Nat} (f : Fin nIn → Fin nOut) : Nat :=
  (List.finRange nOut).foldl
    (fun acc y =>
      let cnt := (List.finRange nIn).countP (fun x => f x == y)
      acc * (cnt ^ cnt))
    1

/-- 2-input classical AND gate truth table on Fin 4 → Fin 2. -/
def andGate (x : Fin 4) : Fin 2 :=
  if x.val == 3 then ⟨1, by decide⟩ else ⟨0, by decide⟩

/-- 1-bit irreversible constant erasure on Fin 2 → Fin 2. -/
def eraseGate (_ : Fin 2) : Fin 2 :=
  ⟨0, by decide⟩

/-- 3-bit reversible Toffoli (CCX) gate on Fin 8 → Fin 8: flips bit 0 iff bits 1 and 2 are both 1. -/
def toffoliGate (x : Fin 8) : Fin 8 :=
  if x.val == 6 then ⟨7, by decide⟩
  else if x.val == 7 then ⟨6, by decide⟩
  else x

/-- Exact Landauer power product of 2-input AND is 3^3 * 1^1 = 27. -/
theorem landauer_and_power_product_27 :
    landauerPowerProduct andGate = 27 := by
  decide

/-- Exact sharp rational bracket 19/16 < H_AND < 6/5 via monotone integer powers:
      19/16 < H  ⇔  2^19 < (2^(4H))^4 = 27^4  (524,288 < 531,441)
      H < 6/5    ⇔  (2^(4H))^5 = 27^5 < 2^24  (14,348,907 < 16,777,216). -/
theorem landauer_and_exact_rational_bracket :
    let pAnd := landauerPowerProduct andGate
    2 ^ 19 < pAnd ^ 4 ∧ pAnd ^ 5 < 2 ^ 24 := by
  decide

/-- Exact contrast: Toffoli (CCX) is a bijection with 0 Landauer erasure (P = 1 = 2^0),
    whereas 1-bit erasure has exact 1-bit Landauer cost (P = 4 = 2^(2*1)). -/
theorem landauer_toffoli_zero_vs_erase_one :
    (∀ x : Fin 8, toffoliGate (toffoliGate x) = x) ∧
    landauerPowerProduct toffoliGate = 1 ∧
    landauerPowerProduct eraseGate = 4 := by
  decide

#print axioms cs21_parametric_net_regression
#print axioms cs21_s44_offloading_witness
#print axioms landauer_and_power_product_27
#print axioms landauer_and_exact_rational_bracket
#print axioms landauer_toffoli_zero_vs_erase_one

end AletheiaKernelCerts.Theorem4
