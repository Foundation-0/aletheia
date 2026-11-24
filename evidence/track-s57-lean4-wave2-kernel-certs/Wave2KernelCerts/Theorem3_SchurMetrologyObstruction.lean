/-
  Wave2KernelCerts.Theorem3_SchurMetrologyObstruction
  Track S57 — Pure-Init Lean 4.36.0 Kernel Certificate for Track S51
  (Diagonal PlantGate vs Coupled Schur-Complement Metrology Obstruction & Venturi Power Closure).
  Zero Mathlib, zero sorry/admit/axiom, zero native_decide, zero external imports.
-/

namespace Wave2KernelCerts.Theorem3

/-! ### Universal Symmetric 2x2, 3x3, and 4x4 Integer Sylvester Positive-Definiteness -/

structure Sym2 where
  a00 : Int
  a01 : Int
  a11 : Int

structure Sym3 where
  a00 : Int
  a01 : Int
  a02 : Int
  a11 : Int
  a12 : Int
  a22 : Int

structure Sym4 where
  a00 : Int
  a01 : Int
  a02 : Int
  a03 : Int
  a11 : Int
  a12 : Int
  a13 : Int
  a22 : Int
  a23 : Int
  a33 : Int

def quad2 (M : Sym2) (x0 x1 : Int) : Int :=
  M.a00 * x0 * x0 + 2 * M.a01 * x0 * x1 + M.a11 * x1 * x1

def quad3 (M : Sym3) (x0 x1 x2 : Int) : Int :=
  M.a00 * x0 * x0 + 2 * M.a01 * x0 * x1 + 2 * M.a02 * x0 * x2 +
  M.a11 * x1 * x1 + 2 * M.a12 * x1 * x2 + M.a22 * x2 * x2

def quad4 (M : Sym4) (x0 x1 x2 x3 : Int) : Int :=
  M.a00 * x0 * x0 + 2 * M.a01 * x0 * x1 + 2 * M.a02 * x0 * x2 + 2 * M.a03 * x0 * x3 +
  M.a11 * x1 * x1 + 2 * M.a12 * x1 * x2 + 2 * M.a13 * x1 * x3 +
  M.a22 * x2 * x2 + 2 * M.a23 * x2 * x3 + M.a33 * x3 * x3

def det2 (M : Sym2) : Int := M.a00 * M.a11 - M.a01 * M.a01

def schur3 (M : Sym3) : Sym2 :=
  { a00 := M.a00 * M.a11 - M.a01 * M.a01
    a01 := M.a00 * M.a12 - M.a01 * M.a02
    a11 := M.a00 * M.a22 - M.a02 * M.a02 }

def schur4 (M : Sym4) : Sym3 :=
  { a00 := M.a00 * M.a11 - M.a01 * M.a01
    a01 := M.a00 * M.a12 - M.a01 * M.a02
    a02 := M.a00 * M.a13 - M.a01 * M.a03
    a11 := M.a00 * M.a22 - M.a02 * M.a02
    a12 := M.a00 * M.a23 - M.a02 * M.a03
    a22 := M.a00 * M.a33 - M.a03 * M.a03 }

private theorem int_mul_pos_iff_right (a b : Int) (ha : 0 < a) (hab : 0 < a * b) : 0 < b := by
  by_cases hb : 0 < b
  · exact hb
  · have hle : b ≤ 0 := by omega
    have hmul : a * b ≤ 0 := by
      have h1 : 0 ≤ a * (-b) := Int.mul_nonneg (by omega) (by omega)
      rw [Int.mul_neg] at h1
      omega
    omega

private theorem sq_nonneg (x : Int) : 0 ≤ x * x := by
  by_cases h : 0 ≤ x
  · exact Int.mul_nonneg h h
  · have hn : 0 ≤ -x := by omega
    have hp : 0 ≤ (-x) * (-x) := Int.mul_nonneg hn hn
    rw [Int.neg_mul_neg] at hp
    exact hp

private theorem sq_pos_of_ne_zero (x : Int) (hx : x ≠ 0) : 0 < x * x := by
  by_cases h : 0 < x
  · exact Int.mul_pos h h
  · have hneg : 0 < -x := by omega
    have hpos : 0 < (-x) * (-x) := Int.mul_pos hneg hneg
    rw [Int.neg_mul_neg] at hpos
    exact hpos

private theorem quad2_complete_square (M : Sym2) (x0 x1 : Int) :
    M.a00 * quad2 M x0 x1 =
      (M.a00 * x0 + M.a01 * x1) * (M.a00 * x0 + M.a01 * x1) + det2 M * (x1 * x1) := by
  simp only [quad2, det2]
  have hlhs :
      M.a00 * (M.a00 * x0 * x0 + 2 * M.a01 * x0 * x1 + M.a11 * x1 * x1) =
      M.a00 * x0 * (M.a00 * x0) + 2 * (M.a00 * x0 * (M.a01 * x1)) +
      M.a00 * M.a11 * (x1 * x1) := by
    rw [Int.mul_add, Int.mul_add]
    have t1 : M.a00 * (M.a00 * x0 * x0) = M.a00 * x0 * (M.a00 * x0) := by
      calc
        M.a00 * (M.a00 * x0 * x0) = (M.a00 * (M.a00 * x0)) * x0 := (Int.mul_assoc _ _ _).symm
        _ = (M.a00 * x0 * M.a00) * x0 := by
              rw [Int.mul_comm M.a00 (M.a00 * x0)]
        _ = M.a00 * x0 * (M.a00 * x0) := Int.mul_assoc _ _ _
    have t2 : M.a00 * (2 * M.a01 * x0 * x1) = 2 * (M.a00 * x0 * (M.a01 * x1)) := by
      calc
        M.a00 * (2 * M.a01 * x0 * x1)
            = (M.a00 * (2 * M.a01 * x0)) * x1 := (Int.mul_assoc _ _ _).symm
        _ = (M.a00 * (2 * (M.a01 * x0))) * x1 := by rw [Int.mul_assoc 2 M.a01 x0]
        _ = (2 * (M.a00 * (M.a01 * x0))) * x1 := by
              rw [← Int.mul_assoc M.a00 2 (M.a01 * x0), Int.mul_comm M.a00 2,
                  Int.mul_assoc 2 M.a00 (M.a01 * x0)]
        _ = (2 * (M.a00 * (x0 * M.a01))) * x1 := by rw [Int.mul_comm M.a01 x0]
        _ = (2 * ((M.a00 * x0) * M.a01)) * x1 := by rw [← Int.mul_assoc M.a00 x0 M.a01]
        _ = 2 * ((M.a00 * x0 * M.a01) * x1) := Int.mul_assoc _ _ _
        _ = 2 * (M.a00 * x0 * (M.a01 * x1)) := by rw [Int.mul_assoc (M.a00 * x0) M.a01 x1]
    have t3 : M.a00 * (M.a11 * x1 * x1) = M.a00 * M.a11 * (x1 * x1) := by
      rw [Int.mul_assoc M.a11 x1 x1, ← Int.mul_assoc M.a00 M.a11 (x1 * x1)]
    rw [t1, t2, t3]
  have hrhs :
      (M.a00 * x0 + M.a01 * x1) * (M.a00 * x0 + M.a01 * x1) +
        (M.a00 * M.a11 - M.a01 * M.a01) * (x1 * x1) =
      M.a00 * x0 * (M.a00 * x0) + 2 * (M.a00 * x0 * (M.a01 * x1)) +
        M.a00 * M.a11 * (x1 * x1) := by
    rw [Int.add_mul, Int.mul_add, Int.mul_add, Int.sub_mul]
    have hc : M.a01 * x1 * (M.a00 * x0) = M.a00 * x0 * (M.a01 * x1) := Int.mul_comm _ _
    have hsq : M.a01 * x1 * (M.a01 * x1) = M.a01 * M.a01 * (x1 * x1) := by
      calc
        M.a01 * x1 * (M.a01 * x1) = (M.a01 * x1 * M.a01) * x1 := (Int.mul_assoc _ _ _).symm
        _ = (M.a01 * M.a01 * x1) * x1 := by
              rw [Int.mul_assoc M.a01 x1 M.a01, Int.mul_comm x1 M.a01,
                  ← Int.mul_assoc M.a01 M.a01 x1]
        _ = M.a01 * M.a01 * (x1 * x1) := Int.mul_assoc _ _ _
    omega
  omega

/-- Theorem 3.1 (Universal): Sylvester positive-definiteness for all 2x2 symmetric integer matrices. -/
theorem sym2_sylvester_spd (M : Sym2) (h0 : 0 < M.a00) (hd : 0 < det2 M)
    (x0 x1 : Int) (hne : x0 ≠ 0 ∨ x1 ≠ 0) : 0 < quad2 M x0 x1 := by
  have hcs := quad2_complete_square M x0 x1
  have hsq1 : 0 ≤ (M.a00 * x0 + M.a01 * x1) * (M.a00 * x0 + M.a01 * x1) :=
    sq_nonneg _
  have hsq2 : 0 ≤ det2 M * (x1 * x1) := Int.mul_nonneg (by omega) (sq_nonneg x1)
  have hpos : 0 < M.a00 * quad2 M x0 x1 := by
    by_cases hx1 : x1 = 0
    · subst hx1
      have hx0 : x0 ≠ 0 := by
        rcases hne with h | h
        · exact h
        · exact False.elim (h rfl)
      have hl : M.a00 * x0 ≠ 0 := by
        intro hzero
        have : M.a00 = 0 ∨ x0 = 0 := Int.mul_eq_zero.mp hzero
        rcases this with h | h <;> omega
      have hlp : 0 < (M.a00 * x0 + M.a01 * 0) * (M.a00 * x0 + M.a01 * 0) := by
        have hsimp : M.a00 * x0 + M.a01 * 0 = M.a00 * x0 := by
          rw [Int.mul_zero, Int.add_zero]
        rw [hsimp]
        exact sq_pos_of_ne_zero (M.a00 * x0) hl
      omega
    · have hx1p : 0 < det2 M * (x1 * x1) := Int.mul_pos hd (sq_pos_of_ne_zero x1 hx1)
      omega
  exact int_mul_pos_iff_right M.a00 (quad2 M x0 x1) h0 hpos

private theorem complete_sq_linear (a x L : Int) :
    a * (a * x * x + 2 * x * L) = (a * x + L) * (a * x + L) - L * L := by
  have h1 : (a * x + L) * (a * x + L) =
      a * x * (a * x) + a * x * L + L * (a * x) + L * L := by
    rw [Int.add_mul, Int.mul_add, Int.mul_add]
    omega
  have s1 : a * (a * x * x) = a * x * (a * x) := by
    calc
      a * (a * x * x) = (a * (a * x)) * x := (Int.mul_assoc _ _ _).symm
      _ = (a * x * a) * x := by rw [Int.mul_comm a (a * x)]
      _ = a * x * (a * x) := Int.mul_assoc _ _ _
  have s2 : a * (2 * x * L) = a * x * L + L * (a * x) := by
    have c1 : L * (a * x) = a * x * L := Int.mul_comm _ _
    have c2 : a * (2 * x * L) = 2 * (a * x * L) := by
      calc
        a * (2 * x * L) = a * (2 * (x * L)) := by rw [Int.mul_assoc]
        _ = (a * 2) * (x * L) := (Int.mul_assoc _ _ _).symm
        _ = (2 * a) * (x * L) := by rw [Int.mul_comm a 2]
        _ = 2 * (a * (x * L)) := Int.mul_assoc _ _ _
        _ = 2 * (a * x * L) := by rw [Int.mul_assoc]
    omega
  rw [Int.mul_add, s1, s2, h1]
  omega

private theorem quad3_complete_square (M : Sym3) (x0 x1 x2 : Int) :
    M.a00 * quad3 M x0 x1 x2 =
      (M.a00 * x0 + M.a01 * x1 + M.a02 * x2) * (M.a00 * x0 + M.a01 * x1 + M.a02 * x2) +
      quad2 (schur3 M) x1 x2 := by
  let L : Int := M.a01 * x1 + M.a02 * x2
  have hq3 : quad3 M x0 x1 x2 =
      M.a00 * x0 * x0 + 2 * x0 * L +
      (M.a11 * x1 * x1 + 2 * M.a12 * x1 * x2 + M.a22 * x2 * x2) := by
    simp only [quad3, L]
    rw [Int.mul_add]
    have t1 : 2 * x0 * (M.a01 * x1) = 2 * M.a01 * x0 * x1 := by
      calc
        2 * x0 * (M.a01 * x1) = (2 * x0 * M.a01) * x1 := (Int.mul_assoc _ _ _).symm
        _ = (2 * (x0 * M.a01)) * x1 := by rw [Int.mul_assoc 2 x0 M.a01]
        _ = (2 * (M.a01 * x0)) * x1 := by rw [Int.mul_comm x0 M.a01]
        _ = 2 * M.a01 * x0 * x1 := by rw [← Int.mul_assoc 2 M.a01 x0]
    have t2 : 2 * x0 * (M.a02 * x2) = 2 * M.a02 * x0 * x2 := by
      calc
        2 * x0 * (M.a02 * x2) = (2 * x0 * M.a02) * x2 := (Int.mul_assoc _ _ _).symm
        _ = (2 * (x0 * M.a02)) * x2 := by rw [Int.mul_assoc 2 x0 M.a02]
        _ = (2 * (M.a02 * x0)) * x2 := by rw [Int.mul_comm x0 M.a02]
        _ = 2 * M.a02 * x0 * x2 := by rw [← Int.mul_assoc 2 M.a02 x0]
    omega
  have h1 := complete_sq_linear M.a00 x0 L
  have h2 : M.a00 * (M.a11 * x1 * x1 + 2 * M.a12 * x1 * x2 + M.a22 * x2 * x2) - L * L =
      quad2 (schur3 M) x1 x2 := by
    simp only [quad2, schur3, L]
    rw [Int.mul_add, Int.mul_add, Int.add_mul, Int.mul_add, Int.mul_add]
    have r1 : (M.a00 * M.a11 - M.a01 * M.a01) * x1 * x1 =
        M.a00 * M.a11 * x1 * x1 - M.a01 * M.a01 * x1 * x1 := by
      rw [Int.sub_mul, Int.sub_mul]
    have r2 : 2 * (M.a00 * M.a12 - M.a01 * M.a02) * x1 * x2 =
        2 * (M.a00 * M.a12) * x1 * x2 - 2 * (M.a01 * M.a02) * x1 * x2 := by
      rw [Int.mul_sub, Int.sub_mul, Int.sub_mul]
    have r3 : (M.a00 * M.a22 - M.a02 * M.a02) * x2 * x2 =
        M.a00 * M.a22 * x2 * x2 - M.a02 * M.a02 * x2 * x2 := by
      rw [Int.sub_mul, Int.sub_mul]
    rw [r1, r2, r3]
    have p1 : M.a00 * (M.a11 * x1 * x1) = M.a00 * M.a11 * x1 * x1 := by
      rw [← Int.mul_assoc M.a00 (M.a11 * x1) x1, ← Int.mul_assoc M.a00 M.a11 x1]
    have p2 : M.a00 * (2 * M.a12 * x1 * x2) = 2 * (M.a00 * M.a12) * x1 * x2 := by
      calc
        M.a00 * (2 * M.a12 * x1 * x2) = (M.a00 * (2 * M.a12 * x1)) * x2 := (Int.mul_assoc _ _ _).symm
        _ = ((M.a00 * (2 * M.a12)) * x1) * x2 := by rw [← Int.mul_assoc M.a00 (2 * M.a12) x1]
        _ = (((M.a00 * 2) * M.a12) * x1) * x2 := by rw [← Int.mul_assoc M.a00 2 M.a12]
        _ = (((2 * M.a00) * M.a12) * x1) * x2 := by rw [Int.mul_comm M.a00 2]
        _ = (2 * (M.a00 * M.a12)) * x1 * x2 := by rw [Int.mul_assoc 2 M.a00 M.a12]
    have p3 : M.a00 * (M.a22 * x2 * x2) = M.a00 * M.a22 * x2 * x2 := by
      rw [← Int.mul_assoc M.a00 (M.a22 * x2) x2, ← Int.mul_assoc M.a00 M.a22 x2]
    have q1 : M.a01 * x1 * (M.a01 * x1) = M.a01 * M.a01 * x1 * x1 := by
      calc
        M.a01 * x1 * (M.a01 * x1) = (M.a01 * x1 * M.a01) * x1 := (Int.mul_assoc _ _ _).symm
        _ = (M.a01 * M.a01 * x1) * x1 := by
              rw [Int.mul_assoc M.a01 x1 M.a01, Int.mul_comm x1 M.a01, ← Int.mul_assoc]
    have q2 : M.a02 * x2 * (M.a02 * x2) = M.a02 * M.a02 * x2 * x2 := by
      calc
        M.a02 * x2 * (M.a02 * x2) = (M.a02 * x2 * M.a02) * x2 := (Int.mul_assoc _ _ _).symm
        _ = (M.a02 * M.a02 * x2) * x2 := by
              rw [Int.mul_assoc M.a02 x2 M.a02, Int.mul_comm x2 M.a02, ← Int.mul_assoc]
    have q3 : M.a01 * x1 * (M.a02 * x2) = M.a01 * M.a02 * x1 * x2 := by
      calc
        M.a01 * x1 * (M.a02 * x2) = (M.a01 * x1 * M.a02) * x2 := (Int.mul_assoc _ _ _).symm
        _ = (M.a01 * (x1 * M.a02)) * x2 := by rw [Int.mul_assoc M.a01 x1 M.a02]
        _ = (M.a01 * (M.a02 * x1)) * x2 := by rw [Int.mul_comm x1 M.a02]
        _ = M.a01 * M.a02 * x1 * x2 := by rw [← Int.mul_assoc M.a01 M.a02 x1]
    have q4 : M.a02 * x2 * (M.a01 * x1) = M.a01 * M.a02 * x1 * x2 := by
      rw [Int.mul_comm (M.a02 * x2) (M.a01 * x1), q3]
    have q5 : 2 * (M.a01 * M.a02) * x1 * x2 =
        M.a01 * M.a02 * x1 * x2 + M.a01 * M.a02 * x1 * x2 := by
      have ha : 2 * (M.a01 * M.a02) = M.a01 * M.a02 + M.a01 * M.a02 := by omega
      rw [ha, Int.add_mul, Int.add_mul]
    omega
  have hadd : M.a00 * x0 + M.a01 * x1 + M.a02 * x2 = M.a00 * x0 + L := by
    simp only [L]
    omega
  rw [hq3, Int.mul_add, h1, hadd]
  omega

private theorem sym3_sylvester_spd (M : Sym3)
    (h0 : 0 < M.a00) (h1 : 0 < (schur3 M).a00) (h2 : 0 < det2 (schur3 M))
    (x0 x1 x2 : Int) (hne : x0 ≠ 0 ∨ x1 ≠ 0 ∨ x2 ≠ 0) :
    0 < quad3 M x0 x1 x2 := by
  have hcs := quad3_complete_square M x0 x1 x2
  have hsq : 0 ≤ (M.a00 * x0 + M.a01 * x1 + M.a02 * x2) *
      (M.a00 * x0 + M.a01 * x1 + M.a02 * x2) := sq_nonneg _
  have hpos : 0 < M.a00 * quad3 M x0 x1 x2 := by
    by_cases htail : x1 ≠ 0 ∨ x2 ≠ 0
    · have hq2 := sym2_sylvester_spd (schur3 M) h1 h2 x1 x2 htail
      omega
    · have hx1 : x1 = 0 := by
        by_cases h : x1 = 0
        · exact h
        · exact False.elim (htail (Or.inl h))
      have hx2 : x2 = 0 := by
        by_cases h : x2 = 0
        · exact h
        · exact False.elim (htail (Or.inr h))
      subst hx1
      subst hx2
      have hx0 : x0 ≠ 0 := by
        rcases hne with h | h | h
        · exact h
        · exact False.elim (h rfl)
        · exact False.elim (h rfl)
      have hl : M.a00 * x0 ≠ 0 := by
        intro hzero
        have : M.a00 = 0 ∨ x0 = 0 := Int.mul_eq_zero.mp hzero
        rcases this with h | h <;> omega
      have hlp : 0 < (M.a00 * x0 + M.a01 * 0 + M.a02 * 0) *
          (M.a00 * x0 + M.a01 * 0 + M.a02 * 0) := by
        have hsimp : M.a00 * x0 + M.a01 * 0 + M.a02 * 0 = M.a00 * x0 := by
          rw [Int.mul_zero, Int.mul_zero, Int.add_zero, Int.add_zero]
        rw [hsimp]
        exact sq_pos_of_ne_zero (M.a00 * x0) hl
      have hq2z : quad2 (schur3 M) 0 0 = 0 := by simp [quad2]
      omega
  exact int_mul_pos_iff_right M.a00 (quad3 M x0 x1 x2) h0 hpos

private theorem mul4_pair (a b x y : Int) :
    a * x * (b * y) = a * b * x * y := by
  calc
    a * x * (b * y) = (a * x * b) * y := (Int.mul_assoc _ _ _).symm
    _ = (a * (x * b)) * y := by rw [Int.mul_assoc a x b]
    _ = (a * (b * x)) * y := by rw [Int.mul_comm x b]
    _ = a * b * x * y := by rw [← Int.mul_assoc a b x]

private theorem mul4_two (c a x y : Int) :
    c * (2 * a * x * y) = 2 * (c * a) * x * y := by
  calc
    c * (2 * a * x * y) = (c * (2 * a * x)) * y := (Int.mul_assoc _ _ _).symm
    _ = ((c * (2 * a)) * x) * y := by rw [← Int.mul_assoc c (2 * a) x]
    _ = (((c * 2) * a) * x) * y := by rw [← Int.mul_assoc c 2 a]
    _ = (((2 * c) * a) * x) * y := by rw [Int.mul_comm c 2]
    _ = 2 * (c * a) * x * y := by rw [Int.mul_assoc 2 c a]

private theorem quad4_complete_square (M : Sym4) (x0 x1 x2 x3 : Int) :
    M.a00 * quad4 M x0 x1 x2 x3 =
      (M.a00 * x0 + M.a01 * x1 + M.a02 * x2 + M.a03 * x3) *
      (M.a00 * x0 + M.a01 * x1 + M.a02 * x2 + M.a03 * x3) +
      quad3 (schur4 M) x1 x2 x3 := by
  let L : Int := M.a01 * x1 + M.a02 * x2 + M.a03 * x3
  let R : Int := M.a11 * x1 * x1 + 2 * M.a12 * x1 * x2 + 2 * M.a13 * x1 * x3 +
                 M.a22 * x2 * x2 + 2 * M.a23 * x2 * x3 + M.a33 * x3 * x3
  have hq4 : quad4 M x0 x1 x2 x3 = M.a00 * x0 * x0 + 2 * x0 * L + R := by
    simp only [quad4, L, R]
    rw [Int.mul_add, Int.mul_add]
    have t1 : 2 * x0 * (M.a01 * x1) = 2 * M.a01 * x0 * x1 := by
      calc
        2 * x0 * (M.a01 * x1) = (2 * x0 * M.a01) * x1 := (Int.mul_assoc _ _ _).symm
        _ = (2 * (x0 * M.a01)) * x1 := by rw [Int.mul_assoc 2 x0 M.a01]
        _ = (2 * (M.a01 * x0)) * x1 := by rw [Int.mul_comm x0 M.a01]
        _ = 2 * M.a01 * x0 * x1 := by rw [← Int.mul_assoc 2 M.a01 x0]
    have t2 : 2 * x0 * (M.a02 * x2) = 2 * M.a02 * x0 * x2 := by
      calc
        2 * x0 * (M.a02 * x2) = (2 * x0 * M.a02) * x2 := (Int.mul_assoc _ _ _).symm
        _ = (2 * (x0 * M.a02)) * x2 := by rw [Int.mul_assoc 2 x0 M.a02]
        _ = (2 * (M.a02 * x0)) * x2 := by rw [Int.mul_comm x0 M.a02]
        _ = 2 * M.a02 * x0 * x2 := by rw [← Int.mul_assoc 2 M.a02 x0]
    have t3 : 2 * x0 * (M.a03 * x3) = 2 * M.a03 * x0 * x3 := by
      calc
        2 * x0 * (M.a03 * x3) = (2 * x0 * M.a03) * x3 := (Int.mul_assoc _ _ _).symm
        _ = (2 * (x0 * M.a03)) * x3 := by rw [Int.mul_assoc 2 x0 M.a03]
        _ = (2 * (M.a03 * x0)) * x3 := by rw [Int.mul_comm x0 M.a03]
        _ = 2 * M.a03 * x0 * x3 := by rw [← Int.mul_assoc 2 M.a03 x0]
    omega
  have h1 := complete_sq_linear M.a00 x0 L
  have h2 : M.a00 * R - L * L = quad3 (schur4 M) x1 x2 x3 := by
    let u1 : Int := M.a01 * x1
    let u2 : Int := M.a02 * x2
    let u3 : Int := M.a03 * x3
    have hLL : L * L = u1 * u1 + 2 * (u1 * u2) + 2 * (u1 * u3) +
        u2 * u2 + 2 * (u2 * u3) + u3 * u3 := by
      have hL : L = u1 + u2 + u3 := rfl
      rw [hL, Int.add_mul, Int.add_mul, Int.mul_add, Int.mul_add, Int.mul_add,
          Int.mul_add, Int.mul_add, Int.mul_add]
      have c12 : u2 * u1 = u1 * u2 := Int.mul_comm u2 u1
      have c13 : u3 * u1 = u1 * u3 := Int.mul_comm u3 u1
      have c23 : u3 * u2 = u2 * u3 := Int.mul_comm u3 u2
      omega
    have hu11 : u1 * u1 = M.a01 * M.a01 * x1 * x1 := mul4_pair M.a01 M.a01 x1 x1
    have hu22 : u2 * u2 = M.a02 * M.a02 * x2 * x2 := mul4_pair M.a02 M.a02 x2 x2
    have hu33 : u3 * u3 = M.a03 * M.a03 * x3 * x3 := mul4_pair M.a03 M.a03 x3 x3
    have hu12 : u1 * u2 = M.a01 * M.a02 * x1 * x2 := mul4_pair M.a01 M.a02 x1 x2
    have hu13 : u1 * u3 = M.a01 * M.a03 * x1 * x3 := mul4_pair M.a01 M.a03 x1 x3
    have hu23 : u2 * u3 = M.a02 * M.a03 * x2 * x3 := mul4_pair M.a02 M.a03 x2 x3
    have hd12 : 2 * (M.a01 * M.a02) * x1 * x2 = 2 * (M.a01 * M.a02 * x1 * x2) := by
      rw [Int.mul_assoc 2 (M.a01 * M.a02) x1, Int.mul_assoc 2 (M.a01 * M.a02 * x1) x2]
    have hd13 : 2 * (M.a01 * M.a03) * x1 * x3 = 2 * (M.a01 * M.a03 * x1 * x3) := by
      rw [Int.mul_assoc 2 (M.a01 * M.a03) x1, Int.mul_assoc 2 (M.a01 * M.a03 * x1) x3]
    have hd23 : 2 * (M.a02 * M.a03) * x2 * x3 = 2 * (M.a02 * M.a03 * x2 * x3) := by
      rw [Int.mul_assoc 2 (M.a02 * M.a03) x2, Int.mul_assoc 2 (M.a02 * M.a03 * x2) x3]
    have hMR : M.a00 * R =
        M.a00 * M.a11 * x1 * x1 + 2 * (M.a00 * M.a12) * x1 * x2 +
        2 * (M.a00 * M.a13) * x1 * x3 + M.a00 * M.a22 * x2 * x2 +
        2 * (M.a00 * M.a23) * x2 * x3 + M.a00 * M.a33 * x3 * x3 := by
      simp only [R]
      rw [Int.mul_add, Int.mul_add, Int.mul_add, Int.mul_add, Int.mul_add]
      have r11 : M.a00 * (M.a11 * x1 * x1) = M.a00 * M.a11 * x1 * x1 := by
        rw [← Int.mul_assoc M.a00 (M.a11 * x1) x1, ← Int.mul_assoc M.a00 M.a11 x1]
      have r22 : M.a00 * (M.a22 * x2 * x2) = M.a00 * M.a22 * x2 * x2 := by
        rw [← Int.mul_assoc M.a00 (M.a22 * x2) x2, ← Int.mul_assoc M.a00 M.a22 x2]
      have r33 : M.a00 * (M.a33 * x3 * x3) = M.a00 * M.a33 * x3 * x3 := by
        rw [← Int.mul_assoc M.a00 (M.a33 * x3) x3, ← Int.mul_assoc M.a00 M.a33 x3]
      rw [r11, r22, r33, mul4_two M.a00 M.a12 x1 x2, mul4_two M.a00 M.a13 x1 x3,
          mul4_two M.a00 M.a23 x2 x3]
    simp only [quad3, schur4]
    have s11 : (M.a00 * M.a11 - M.a01 * M.a01) * x1 * x1 =
        M.a00 * M.a11 * x1 * x1 - M.a01 * M.a01 * x1 * x1 := by rw [Int.sub_mul, Int.sub_mul]
    have s12 : 2 * (M.a00 * M.a12 - M.a01 * M.a02) * x1 * x2 =
        2 * (M.a00 * M.a12) * x1 * x2 - 2 * (M.a01 * M.a02) * x1 * x2 := by
      rw [Int.mul_sub, Int.sub_mul, Int.sub_mul]
    have s13 : 2 * (M.a00 * M.a13 - M.a01 * M.a03) * x1 * x3 =
        2 * (M.a00 * M.a13) * x1 * x3 - 2 * (M.a01 * M.a03) * x1 * x3 := by
      rw [Int.mul_sub, Int.sub_mul, Int.sub_mul]
    have s22 : (M.a00 * M.a22 - M.a02 * M.a02) * x2 * x2 =
        M.a00 * M.a22 * x2 * x2 - M.a02 * M.a02 * x2 * x2 := by rw [Int.sub_mul, Int.sub_mul]
    have s23 : 2 * (M.a00 * M.a23 - M.a02 * M.a03) * x2 * x3 =
        2 * (M.a00 * M.a23) * x2 * x3 - 2 * (M.a02 * M.a03) * x2 * x3 := by
      rw [Int.mul_sub, Int.sub_mul, Int.sub_mul]
    have s33 : (M.a00 * M.a33 - M.a03 * M.a03) * x3 * x3 =
        M.a00 * M.a33 * x3 * x3 - M.a03 * M.a03 * x3 * x3 := by rw [Int.sub_mul, Int.sub_mul]
    rw [s11, s12, s13, s22, s23, s33, hMR, hLL, hu11, hu22, hu33, hu12, hu13, hu23, hd12, hd13, hd23]
    omega
  have hadd : M.a00 * x0 + M.a01 * x1 + M.a02 * x2 + M.a03 * x3 = M.a00 * x0 + L := by
    simp only [L]
    omega
  rw [hq4, Int.mul_add, h1, hadd]
  omega

/-- Theorem 3.2 (Universal): Sylvester positive-definiteness for all 4x4 symmetric integer matrices. -/
theorem sym4_sylvester_spd (M : Sym4)
    (h0 : 0 < M.a00)
    (h1 : 0 < (schur4 M).a00)
    (h2 : 0 < (schur3 (schur4 M)).a00)
    (h3 : 0 < det2 (schur3 (schur4 M)))
    (x0 x1 x2 x3 : Int)
    (hne : x0 ≠ 0 ∨ x1 ≠ 0 ∨ x2 ≠ 0 ∨ x3 ≠ 0) :
    0 < quad4 M x0 x1 x2 x3 := by
  have hcs := quad4_complete_square M x0 x1 x2 x3
  have hsq : 0 ≤ (M.a00 * x0 + M.a01 * x1 + M.a02 * x2 + M.a03 * x3) *
      (M.a00 * x0 + M.a01 * x1 + M.a02 * x2 + M.a03 * x3) := sq_nonneg _
  have hpos : 0 < M.a00 * quad4 M x0 x1 x2 x3 := by
    by_cases htail : x1 ≠ 0 ∨ x2 ≠ 0 ∨ x3 ≠ 0
    · have hq3 := sym3_sylvester_spd (schur4 M) h1 h2 h3 x1 x2 x3 htail
      omega
    · have hx1 : x1 = 0 := by
        by_cases h : x1 = 0
        · exact h
        · exact False.elim (htail (Or.inl h))
      have hx2 : x2 = 0 := by
        by_cases h : x2 = 0
        · exact h
        · exact False.elim (htail (Or.inr (Or.inl h)))
      have hx3 : x3 = 0 := by
        by_cases h : x3 = 0
        · exact h
        · exact False.elim (htail (Or.inr (Or.inr h)))
      subst hx1
      subst hx2
      subst hx3
      have hx0 : x0 ≠ 0 := by
        rcases hne with h | h | h | h
        · exact h
        · exact False.elim (h rfl)
        · exact False.elim (h rfl)
        · exact False.elim (h rfl)
      have hl : M.a00 * x0 ≠ 0 := by
        intro hzero
        have : M.a00 = 0 ∨ x0 = 0 := Int.mul_eq_zero.mp hzero
        rcases this with h | h <;> omega
      have hlp : 0 < (M.a00 * x0 + M.a01 * 0 + M.a02 * 0 + M.a03 * 0) *
          (M.a00 * x0 + M.a01 * 0 + M.a02 * 0 + M.a03 * 0) := by
        have hsimp : M.a00 * x0 + M.a01 * 0 + M.a02 * 0 + M.a03 * 0 = M.a00 * x0 := by
          rw [Int.mul_zero, Int.mul_zero, Int.mul_zero, Int.add_zero, Int.add_zero, Int.add_zero]
        rw [hsimp]
        exact sq_pos_of_ne_zero (M.a00 * x0) hl
      have hq3z : quad3 (schur4 M) 0 0 0 = 0 := by simp [quad3]
      omega
  exact int_mul_pos_iff_right M.a00 (quad4 M x0 x1 x2 x3) h0 hpos

/-! ### Exact optifab PlantGate & Coupled Schur-Complement Blocks (Zero Precomputed Literals) -/

def plantLimitPpm : Int := 1000000
def plantRadiusPpm : Int := 198947

def u0Ppm : Fin 4 → Int
  | ⟨0, _⟩ => 801053 | ⟨1, _⟩ => 769564 | ⟨2, _⟩ => 616000 | ⟨3, _⟩ => 284589

def ucPpm : Fin 4 → Int
  | ⟨0, _⟩ => 901053 | ⟨1, _⟩ => 879564 | ⟨2, _⟩ => 696000 | ⟨3, _⟩ => 379589

/-- Diagonal PlantGate margin numerator A_uc = diag((1000000 - uc_i) / 1000000). -/
def aDiagNum (i : Fin 4) : Int := plantLimitPpm - ucPpm i

/-- Coupling matrix B = bNum / 20 (exact: [[1/5, 0], [1/4, 1/4], [1/5, 0], [0, 1/2]]). -/
def bNum (i : Fin 4) (j : Fin 2) : Int :=
  match i.val, j.val with
  | 0, 0 => 4 | 0, 1 => 0
  | 1, 0 => 5 | 1, 1 => 5
  | 2, 0 => 4 | 2, 1 => 0
  | 3, 0 => 0 | _, _ => 10

/-- Sensor precision block D = dNum / 19410000 (exact: [[8209/10000, 1/10], [1/10, 474037/970500]]). -/
def dScale : Int := 19410000

def dSymNum : Sym2 :=
  { a00 := 15933669
    a01 := 1941000
    a11 := 9480740 }

def detDNum : Int := det2 dSymNum

/-- Adjugate of dSymNum (satisfies D * adjD = detD * I_2). -/
def adjDEntry (r c : Fin 2) : Int :=
  match r.val, c.val with
  | 0, 0 => dSymNum.a11
  | 0, 1 => -dSymNum.a01
  | 1, 0 => -dSymNum.a01
  | _, _ => dSymNum.a00

/-- Exact cleared-integer entry of C = B * D^{-1} * B^T multiplied by (400 * detDNum / dScale),
    i.e., numC i j = (bNum * adjD * bNum^T) i j, so C = (dScale / (400 * detDNum)) * numC. -/
def numC (i j : Fin 4) : Int :=
  (bNum i 0 * adjDEntry 0 0 + bNum i 1 * adjDEntry 1 0) * bNum j 0 +
  (bNum i 0 * adjDEntry 0 1 + bNum i 1 * adjDEntry 1 1) * bNum j 1

/-- Exact integer scaled Schur complement:
    For S = A_uc - (cNum / 4) * B * D^{-1} * B^T (cNum = 2 uncalibrated, cNum = 1 calibrated),
    multiply by 4 * 1000000 * detDNum:
    S_int i j = (if i = j then 4 * detDNum * aDiagNum i else 0) - cNum * 2500 * dScale * numC i j.
    Since 1000000 / 400 = 2500 and common factor 4 * 1000000 * detDNum > 0, signs are exact! -/
def schurScaledEntry (cNum : Int) (i j : Fin 4) : Int :=
  (if i = j then 4 * detDNum * aDiagNum i else 0) - cNum * 2500 * dScale * numC i j

def buildSym4 (cNum : Int) : Sym4 :=
  { a00 := schurScaledEntry cNum 0 0
    a01 := schurScaledEntry cNum 0 1
    a02 := schurScaledEntry cNum 0 2
    a03 := schurScaledEntry cNum 0 3
    a11 := schurScaledEntry cNum 1 1
    a12 := schurScaledEntry cNum 1 2
    a13 := schurScaledEntry cNum 1 3
    a22 := schurScaledEntry cNum 2 2
    a23 := schurScaledEntry cNum 2 3
    a33 := schurScaledEntry cNum 3 3 }

def sUncalSym : Sym4 := buildSym4 2
def sCalSym : Sym4 := buildSym4 1

/-- Exact 4x4 leading principal minor determinant (via 3-step Schur reduction):
    det2 (schur3 (schur4 M)) = M_1^2 * M_2 * M_4, so its sign matches M_4 identically
    whenever M_1 > 0 and M_2 > 0! -/
def pivot1 (M : Sym4) : Int := M.a00
def pivot2 (M : Sym4) : Int := (schur4 M).a00
def pivot3 (M : Sym4) : Int := (schur3 (schur4 M)).a00
def pivot4 (M : Sym4) : Int := det2 (schur3 (schur4 M))

/-- Theorem 3.3 (Concrete): Diagonal optifab PlantGate admits ucPpm strictly inside the L2 ball
    and strictly below plantLimitPpm on every channel. -/
theorem optifab_diagonal_plant_gate_admits_uc :
    let d0 := ucPpm 0 - u0Ppm 0
    let d1 := ucPpm 1 - u0Ppm 1
    let d2 := ucPpm 2 - u0Ppm 2
    let d3 := ucPpm 3 - u0Ppm 3
    let distSq := d0 * d0 + d1 * d1 + d2 * d2 + d3 * d3
    distSq = 37525000000 ∧
    plantRadiusPpm * plantRadiusPpm = 39579908809 ∧
    distSq ≤ plantRadiusPpm * plantRadiusPpm ∧
    (∀ i : Fin 4, ucPpm i < plantLimitPpm) ∧
    (∀ i : Fin 4, 0 < aDiagNum i) := by
  decide

/-- Theorem 3.4 (Universal): Sensor precision block D is strictly SPD on all of Z^2 \ {0},
    with exact D * adjD = detD * I_2 and detD = 147295492035060 > 0. -/
theorem optifab_sensor_block_D_spd :
    detDNum = 147295492035060 ∧
    0 < detDNum ∧
    dSymNum.a00 * adjDEntry 0 0 + dSymNum.a01 * adjDEntry 1 0 = detDNum ∧
    dSymNum.a00 * adjDEntry 0 1 + dSymNum.a01 * adjDEntry 1 1 = 0 ∧
    dSymNum.a01 * adjDEntry 0 0 + dSymNum.a11 * adjDEntry 1 0 = 0 ∧
    dSymNum.a01 * adjDEntry 0 1 + dSymNum.a11 * adjDEntry 1 1 = detDNum ∧
    (∀ y0 y1 : Int, (y0 ≠ 0 ∨ y1 ≠ 0) → 0 < quad2 dSymNum y0 y1) := by
  refine ⟨by decide, by decide, by decide, by decide, by decide, by decide, ?_⟩
  intro y0 y1 hne
  exact sym2_sylvester_spd dSymNum (by decide) (by decide) y0 y1 hne

/-- Theorem 3.5 (Concrete): Uncalibrated Schur complement S_uncal (tau = 1/2, eta = 0)
    computed directly from A_uc, B, D has exact Sylvester pivot signs (+, +, +, -) => inertia (3, 0, 1). -/
theorem optifab_uncalibrated_schur_minors_3_0_1 :
    0 < pivot1 sUncalSym ∧
    0 < pivot2 sUncalSym ∧
    0 < pivot3 sUncalSym ∧
    pivot4 sUncalSym < 0 := by
  decide

/-- Theorem 3.6 (Concrete): Explicit low-integer destabilizing direction w = (0, 3, 0, 1)
    is strictly positive under diagonal PlantGate (w^T A_uc w > 0), strictly negative under
    uncalibrated Schur complement (w^T S_uncal w < 0), and restored positive under calibrated S_cal! -/
theorem optifab_uncalibrated_negative_witness :
    let wA : Int := 0 * 0 * aDiagNum 0 + 3 * 3 * aDiagNum 1 +
                    0 * 0 * aDiagNum 2 + 1 * 1 * aDiagNum 3
    wA = 1704335 ∧
    0 < wA ∧
    quad4 sUncalSym 0 3 0 1 < 0 ∧
    0 < quad4 sCalSym 0 3 0 1 := by
  decide

/-- Theorem 3.7 (Universal): Calibrated Schur complement S_cal (tau = 1/2, eta = 1)
    has strictly positive pivots (+, +, +, +) and is UNIVERSALLY strictly positive definite
    for EVERY nonzero integer (hence rational) vector x in Z^4 \ {0}! -/
theorem optifab_calibrated_schur_universal_spd :
    0 < pivot1 sCalSym ∧
    0 < pivot2 sCalSym ∧
    0 < pivot3 sCalSym ∧
    0 < pivot4 sCalSym ∧
    (∀ x0 x1 x2 x3 : Int, (x0 ≠ 0 ∨ x1 ≠ 0 ∨ x2 ≠ 0 ∨ x3 ≠ 0) →
      0 < quad4 sCalSym x0 x1 x2 x3) := by
  refine ⟨by decide, by decide, by decide, by decide, ?_⟩
  intro x0 x1 x2 x3 hne
  exact sym4_sylvester_spd sCalSym (by decide) (by decide) (by decide) (by decide) x0 x1 x2 x3 hne

/-- Theorem 3.8 (Universal): Venturi-collars dual-sensor power closure:
    single sensor demand / single collar capacity = (2311/28875) / (13/125) = 2311/3003 < 1,
    so two sensor nodes require 4622/3003 > 1 collars, hence k collars close the dual-sensor
    power budget (k * 3003 >= 4622) if and only if k >= 2. -/
theorem venturi_collars_min_two_universal :
    2311 * 125 * 3003 = 2311 * 13 * 28875 ∧
    2311 < 3003 ∧
    1 * 3003 < 4622 ∧
    2 * 3003 ≥ 4622 ∧
    (∀ k : Nat, k * 3003 ≥ 4622 ↔ k ≥ 2) := by
  refine ⟨by decide, by decide, by decide, by decide, ?_⟩
  intro k
  omega

end Wave2KernelCerts.Theorem3

#print axioms Wave2KernelCerts.Theorem3.sym2_sylvester_spd
#print axioms Wave2KernelCerts.Theorem3.sym4_sylvester_spd
#print axioms Wave2KernelCerts.Theorem3.optifab_diagonal_plant_gate_admits_uc
#print axioms Wave2KernelCerts.Theorem3.optifab_sensor_block_D_spd
#print axioms Wave2KernelCerts.Theorem3.optifab_uncalibrated_schur_minors_3_0_1
#print axioms Wave2KernelCerts.Theorem3.optifab_uncalibrated_negative_witness
#print axioms Wave2KernelCerts.Theorem3.optifab_calibrated_schur_universal_spd
#print axioms Wave2KernelCerts.Theorem3.venturi_collars_min_two_universal
