/-
  Track S160 EXP-Q42c: Anti-Collusion Reciprocity-Cycle and
  Correlated-Verifier Hodge Gate. Pure Init, exact integers.
  Error rates are eps_i = e_i / D and correlation is rho = r / R;
  every statement is denominators-cleared.
-/

namespace ReciprocityGate

/-- Cleared joint false-accept numerator: `P_joint * (R * D * D)` where
    `P_joint = rho * min(eps1, eps2) + (1 - rho) * eps1 * eps2`. -/
def jointCleared (e1 e2 D r R : Int) : Int :=
  r * (min e1 e2) * D + (R - r) * (e1 * e2)

/-- Cleared independent joint false-accept numerator: `eps1 * eps2 * (R * D * D)`
    with the common factor `D * D` suppressed on both sides of comparisons
    against `jointCleared` scaled identically. -/
def indepCleared (e1 e2 R : Int) : Int :=
  R * (e1 * e2)

theorem min_mul_ge_prod (e1 e2 D : Int)
    (h1nn : 0 <= e1) (h2nn : 0 <= e2) (h1le : e1 <= D) (h2le : e2 <= D) :
    e1 * e2 <= (min e1 e2) * D := by
  rcases Int.le_total e1 e2 with h | h
  · rw [Int.min_eq_left h]
    exact Int.mul_le_mul_of_nonneg_left h2le h1nn
  · rw [Int.min_eq_right h, Int.mul_comm e1 e2]
    exact Int.mul_le_mul_of_nonneg_left h1le h2nn

theorem correlated_verifier_false_accept_bound (e1 e2 D r R : Int)
    (h1nn : 0 <= e1) (h2nn : 0 <= e2) (h1le : e1 <= D) (h2le : e2 <= D)
    (_hD : 0 < D) (hrnn : 0 <= r) (_hrle : r <= R) :
    jointCleared e1 e2 D r R - indepCleared e1 e2 R =
      r * ((min e1 e2) * D - e1 * e2) ∧
    indepCleared e1 e2 R <= jointCleared e1 e2 D r R := by
  have hmin := min_mul_ge_prod e1 e2 D h1nn h2nn h1le h2le
  have hId : jointCleared e1 e2 D r R - indepCleared e1 e2 R =
      r * ((min e1 e2) * D - e1 * e2) := by
    unfold jointCleared indepCleared
    have ha : r * (min e1 e2) * D = r * ((min e1 e2) * D) :=
      Int.mul_assoc r (min e1 e2) D
    have hb : (R - r) * (e1 * e2) = R * (e1 * e2) - r * (e1 * e2) :=
      Int.sub_mul R r (e1 * e2)
    have hc : r * ((min e1 e2) * D - e1 * e2) =
        r * ((min e1 e2) * D) - r * (e1 * e2) :=
      Int.mul_sub r ((min e1 e2) * D) (e1 * e2)
    omega
  have hnn : 0 <= r * ((min e1 e2) * D - e1 * e2) :=
    Int.mul_nonneg hrnn (by omega)
  constructor
  · exact hId
  · omega

theorem correlated_strict_excess (e1 e2 D r R : Int)
    (hr : 0 < r) (hgap : e1 * e2 < (min e1 e2) * D) :
    indepCleared e1 e2 R < jointCleared e1 e2 D r R := by
  have hId : jointCleared e1 e2 D r R - indepCleared e1 e2 R =
      r * ((min e1 e2) * D - e1 * e2) := by
    unfold jointCleared indepCleared
    have ha : r * (min e1 e2) * D = r * ((min e1 e2) * D) :=
      Int.mul_assoc r (min e1 e2) D
    have hb : (R - r) * (e1 * e2) = R * (e1 * e2) - r * (e1 * e2) :=
      Int.sub_mul R r (e1 * e2)
    have hc : r * ((min e1 e2) * D - e1 * e2) =
        r * ((min e1 e2) * D) - r * (e1 * e2) :=
      Int.mul_sub r ((min e1 e2) * D) (e1 * e2)
    omega
  have hpos : 0 < r * ((min e1 e2) * D - e1 * e2) :=
    Int.mul_pos hr (by omega)
  omega

theorem collation_independence_collapse (s ea eb D : Int)
    (hsnn : 0 <= s) (hann : 0 <= ea) (hbnn : 0 <= eb)
    (hale : ea <= D) (hble : eb <= D) :
    s * (ea * eb) <= s * ((min ea eb) * D) ∧
    (s * ((min ea eb) * D)) * (ea * eb) = (s * (ea * eb)) * ((min ea eb) * D) := by
  have hmin := min_mul_ge_prod ea eb D hann hbnn hale hble
  constructor
  · exact Int.mul_le_mul_of_nonneg_left hmin hsnn
  · have gen : ∀ x y : Int, (s * x) * y = (s * y) * x := by
      intro x y
      rw [Int.mul_assoc, Int.mul_assoc, Int.mul_comm x y]
    exact gen ((min ea eb) * D) (ea * eb)

theorem collation_strict_collapse (s ea eb D : Int)
    (hs : 0 < s) (hgap : ea * eb < (min ea eb) * D) :
    s * (ea * eb) < s * ((min ea eb) * D) :=
  Int.mul_lt_mul_of_pos_left hgap hs

theorem reciprocity_2cycle_trace_identity
    (a01 a10 a02 a20 a12 a21 : Int) :
    (a01 * a10 + a10 * a01 + a02 * a20 + a20 * a02 + a12 * a21 + a21 * a12) =
      2 * (a01 * a10 + a02 * a20 + a12 * a21) := by
  rw [Int.mul_comm a10 a01, Int.mul_comm a20 a02, Int.mul_comm a21 a12]
  omega

theorem skew_curl_pair_identity (a b : Int)
    (ha : a = 0 ∨ a = 1) (hb : b = 0 ∨ b = 1) :
    (a - b) * (a - b) = a + b - 2 * (a * b) ∧ a * a = a ∧ b * b = b := by
  rcases ha with h | h <;> rcases hb with g | g <;> rw [h, g] <;> decide

theorem hodge_defect_decomposition_3node
    (a01 a10 a02 a20 a12 a21 : Int)
    (h01 : a01 = 0 ∨ a01 = 1) (h10 : a10 = 0 ∨ a10 = 1)
    (h02 : a02 = 0 ∨ a02 = 1) (h20 : a20 = 0 ∨ a20 = 1)
    (h12 : a12 = 0 ∨ a12 = 1) (h21 : a21 = 0 ∨ a21 = 1) :
    ((a01 - a10) * (a01 - a10) + (a02 - a20) * (a02 - a20) +
      (a12 - a21) * (a12 - a21)) +
      2 * (a01 * a10 + a02 * a20 + a12 * a21) =
    (a01 + a10) + (a02 + a20) + (a12 + a21) := by
  have p1 := (skew_curl_pair_identity a01 a10 h01 h10).1
  have p2 := (skew_curl_pair_identity a02 a20 h02 h20).1
  have p3 := (skew_curl_pair_identity a12 a21 h12 h21).1
  omega

theorem reciprocity_witness_sand_scarlet :
    jointCleared 1 2 10 1 2 = 12 ∧ indepCleared 1 2 2 = 4 ∧
    (1 : Int) * 2 < (min 1 2) * 10 ∧
    indepCleared 1 2 2 < jointCleared 1 2 10 1 2 ∧
    jointCleared 1 2 10 0 2 = indepCleared 1 2 2 ∧
    jointCleared 1 2 10 2 2 = 20 := by
  decide

end ReciprocityGate
