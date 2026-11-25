-- Track S112 — Pure-Init Lean 4.36.0 Formalization of All 5 Natural-Systems Stage-B Portals
-- Zero external imports, zero Mathlib, zero sorry, zero Classical.choice.
-- Covers Portals 1 (Homeostasis/LIF), 2 (Turing), 3 (Beltrami/Helicity),
-- 4 (Murray/Physarum/Schur-Thomson/Braess), and 5 (Darboux/One-Sided Lapse Trace/Hopf).

namespace NaturalSystemsConservation

-- ============================================================================
-- 0. Constructive Finite-Dimensional Linear Algebra over Int (Pure Init)
-- ============================================================================

def sumN : Nat → (Nat → Int) → Int
  | 0, _ => 0
  | n + 1, f => sumN n f + f n

def dotN (n : Nat) (u v : Nat → Int) : Int :=
  sumN n (fun i => u i * v i)

def normSqN (n : Nat) (u : Nat → Int) : Int :=
  dotN n u u

def matVecRect (_m n : Nat) (A : Nat → Nat → Int) (x : Nat → Int) (i : Nat) : Int :=
  sumN n (fun j => A i j * x j)

def matVec (n : Nat) (A : Nat → Nat → Int) (x : Nat → Int) (i : Nat) : Int :=
  matVecRect n n A x i

def matMulRect (_m k _n : Nat) (A B : Nat → Nat → Int) (i j : Nat) : Int :=
  sumN k (fun r => A i r * B r j)

def matMul (n : Nat) (A B : Nat → Nat → Int) (i j : Nat) : Int :=
  matMulRect n n n A B i j

def transposeMat (A : Nat → Nat → Int) (i j : Nat) : Int :=
  A j i

def scaleMat (c : Int) (A : Nat → Nat → Int) (i j : Nat) : Int :=
  c * A i j

def commMat (n : Nat) (A B : Nat → Nat → Int) (i j : Nat) : Int :=
  matMul n A B i j - matMul n B A i j

def matPow (n : Nat) (A : Nat → Nat → Int) : Nat → Nat → Nat → Int
  | 0, i, j => if i = j then 1 else 0
  | k + 1, i, j => matMul n (matPow n A k) A i j

def IsSym (n : Nat) (A : Nat → Nat → Int) : Prop :=
  ∀ i j, i < n → j < n → A i j = A j i

def IsSkew (n : Nat) (K : Nat → Nat → Int) : Prop :=
  ∀ i j, i < n → j < n → K i j = -(K j i)

def MatComm (n : Nat) (A B : Nat → Nat → Int) : Prop :=
  ∀ i j, i < n → j < n → matMul n A B i j = matMul n B A i j

def basisVec (idx : Nat) (i : Nat) : Int :=
  if i = idx then 1 else 0

-- Private constructive algebra helpers (zero Classical.choice)

private theorem int_sq_nonneg (a : Int) : 0 ≤ a * a := by
  if h : 0 ≤ a then
    exact Int.mul_nonneg h h
  else
    have hna : 0 ≤ -a := by omega
    have hmul : 0 ≤ (-a) * (-a) := Int.mul_nonneg hna hna
    rw [Int.neg_mul_neg] at hmul
    exact hmul

private theorem int_sq_pos_of_ne_zero (a : Int) (ha : a ≠ 0) : 0 < a * a := by
  if h : 0 < a then
    exact Int.mul_pos h h
  else
    have hna : 0 < -a := by omega
    have hmul : 0 < (-a) * (-a) := Int.mul_pos hna hna
    rw [Int.neg_mul_neg] at hmul
    exact hmul

private theorem int_mul_le_left_nonneg (c a b : Int) (hc : 0 ≤ c) (hab : a ≤ b) :
    c * a ≤ c * b := by
  have hdiff : 0 ≤ b - a := by omega
  have hmul : 0 ≤ c * (b - a) := Int.mul_nonneg hc hdiff
  rw [Int.mul_sub] at hmul
  omega

private theorem int_mul_cancel_left_nz (s a b : Int) (hs : s ≠ 0) (heq : s * a = s * b) :
    a = b := by
  have h0 : s * (a - b) = 0 := by rw [Int.mul_sub]; omega
  cases Int.mul_eq_zero.mp h0 with
  | inl h => exact absurd h hs
  | inr h => omega

private theorem sumN_congr (n : Nat) (f g : Nat → Int)
    (h : ∀ i, i < n → f i = g i) : sumN n f = sumN n g := by
  induction n with
  | zero => rfl
  | succ k ih =>
    simp only [sumN]
    have h1 := ih (fun i hi => h i (Nat.lt_succ_of_lt hi))
    have h2 := h k (Nat.lt_succ_self k)
    omega

private theorem sumN_zero (n : Nat) : sumN n (fun _ => 0) = 0 := by
  induction n with
  | zero => rfl
  | succ k ih => simp only [sumN]; omega

private theorem sumN_add (n : Nat) (f g : Nat → Int) :
    sumN n (fun i => f i + g i) = sumN n f + sumN n g := by
  induction n with
  | zero => rfl
  | succ k ih => simp only [sumN]; omega

private theorem sumN_sub (n : Nat) (f g : Nat → Int) :
    sumN n (fun i => f i - g i) = sumN n f - sumN n g := by
  induction n with
  | zero => rfl
  | succ k ih => simp only [sumN]; omega

private theorem sumN_neg (n : Nat) (f : Nat → Int) :
    sumN n (fun i => -(f i)) = -(sumN n f) := by
  induction n with
  | zero => rfl
  | succ k ih => simp only [sumN]; omega

private theorem sumN_mul_left (n : Nat) (c : Int) (f : Nat → Int) :
    sumN n (fun i => c * f i) = c * sumN n f := by
  induction n with
  | zero => simp only [sumN, Int.mul_zero]
  | succ k ih => simp only [sumN]; rw [ih, Int.mul_add]

private theorem sumN_mul_right (n : Nat) (c : Int) (f : Nat → Int) :
    sumN n (fun i => f i * c) = sumN n f * c := by
  induction n with
  | zero => simp only [sumN, Int.zero_mul]
  | succ k ih => simp only [sumN]; rw [ih, Int.add_mul]

private theorem sumN_comm (m n : Nat) (f : Nat → Nat → Int) :
    sumN m (fun i => sumN n (fun j => f i j)) =
    sumN n (fun j => sumN m (fun i => f i j)) := by
  induction m with
  | zero => simp only [sumN]; exact (sumN_zero n).symm
  | succ k ih => simp only [sumN]; rw [ih, ← sumN_add]

private theorem sumN_nonneg (n : Nat) (f : Nat → Int)
    (h : ∀ i, i < n → 0 ≤ f i) : 0 ≤ sumN n f := by
  induction n with
  | zero => exact Int.le_refl 0
  | succ k ih =>
    simp only [sumN]
    have h1 := ih (fun i hi => h i (Nat.lt_succ_of_lt hi))
    have h2 := h k (Nat.lt_succ_self k)
    omega

private theorem sumN_kronecker_right (n idx : Nat) (f : Nat → Int) (hidx : idx < n) :
    sumN n (fun j => f j * basisVec idx j) = f idx := by
  induction n with
  | zero => omega
  | succ k ih =>
    simp only [sumN]
    if hlt : idx < k then
      have hne : k ≠ idx := by omega
      have hb : basisVec idx k = 0 := by unfold basisVec; exact ite_eq_right_iff.mpr (fun h => absurd h hne)
      rw [hb, Int.mul_zero, ih hlt]
      omega
    else
      have heq : k = idx := by omega
      have hb : basisVec idx k = 1 := by unfold basisVec; exact ite_eq_left_iff.mpr (fun h => absurd heq h)
      have hzero : sumN k (fun j => f j * basisVec idx j) = 0 := by
        calc sumN k (fun j => f j * basisVec idx j)
            = sumN k (fun _ => 0) := by
                apply sumN_congr
                intro j hj
                have hne : j ≠ idx := by omega
                have hbj : basisVec idx j = 0 := by unfold basisVec; exact ite_eq_right_iff.mpr (fun h => absurd h hne)
                rw [hbj, Int.mul_zero]
          _ = 0 := sumN_zero k
      rw [hzero, hb, Int.mul_one, heq]
      omega

private theorem sumN_kronecker_left (n idx : Nat) (f : Nat → Int) (hidx : idx < n) :
    sumN n (fun j => basisVec idx j * f j) = f idx := by
  have h1 : sumN n (fun j => basisVec idx j * f j) = sumN n (fun j => f j * basisVec idx j) :=
    sumN_congr n _ _ (fun j _ => Int.mul_comm _ _)
  rw [h1]
  exact sumN_kronecker_right n idx f hidx

private theorem dotN_comm (n : Nat) (u v : Nat → Int) : dotN n u v = dotN n v u :=
  sumN_congr n _ _ (fun i _ => Int.mul_comm (u i) (v i))

private theorem dotN_matVecRect_adj (m n : Nat) (A : Nat → Nat → Int) (u v : Nat → Int) :
    dotN m u (matVecRect m n A v) = dotN n (matVecRect n m (transposeMat A) u) v := by
  unfold dotN matVecRect transposeMat
  calc sumN m (fun i => u i * sumN n (fun j => A i j * v j))
      = sumN m (fun i => sumN n (fun j => u i * (A i j * v j))) :=
          sumN_congr m _ _ (fun i _ => (sumN_mul_left n (u i) _).symm)
    _ = sumN n (fun j => sumN m (fun i => u i * (A i j * v j))) := sumN_comm m n _
    _ = sumN n (fun j => sumN m (fun i => (A i j * u i) * v j)) := by
          apply sumN_congr; intro j _; apply sumN_congr; intro i _
          rw [← Int.mul_assoc, Int.mul_comm (u i) (A i j)]
    _ = sumN n (fun j => sumN m (fun i => A i j * u i) * v j) :=
          sumN_congr n _ _ (fun j _ => sumN_mul_right m (v j) _)

private theorem matVec_sym_adj (n : Nat) (C : Nat → Nat → Int) (u v : Nat → Int)
    (hsym : IsSym n C) : dotN n u (matVec n C v) = dotN n (matVec n C u) v := by
  unfold matVec
  rw [dotN_matVecRect_adj n n C u v]
  unfold dotN matVecRect transposeMat
  apply sumN_congr; intro i hi
  have h1 : sumN n (fun j => C j i * u j) = sumN n (fun j => C i j * u j) :=
    sumN_congr n _ _ (fun j hj => by rw [hsym j i hj hi])
  rw [h1]

private theorem matVec_matMul (n : Nat) (A B : Nat → Nat → Int) (x : Nat → Int) (i : Nat) :
    matVec n A (matVec n B x) i = matVec n (matMul n A B) x i := by
  unfold matVec matVecRect matMul matMulRect
  calc sumN n (fun r => A i r * sumN n (fun j => B r j * x j))
      = sumN n (fun r => sumN n (fun j => A i r * (B r j * x j))) :=
          sumN_congr n _ _ (fun r _ => (sumN_mul_left n (A i r) _).symm)
    _ = sumN n (fun j => sumN n (fun r => A i r * (B r j * x j))) := sumN_comm n n _
    _ = sumN n (fun j => sumN n (fun r => (A i r * B r j) * x j)) :=
          sumN_congr n _ _ (fun j _ => sumN_congr n _ _ (fun r _ => (Int.mul_assoc _ _ _).symm))
    _ = sumN n (fun j => sumN n (fun r => A i r * B r j) * x j) :=
          sumN_congr n _ _ (fun j _ => sumN_mul_right n (x j) _)

private theorem matMul_assoc (m p q n : Nat) (A B C : Nat → Nat → Int) (i j : Nat) :
    matMulRect m p n A (matMulRect p q n B C) i j =
    matMulRect m q n (matMulRect m p q A B) C i j := by
  unfold matMulRect
  calc sumN p (fun r => A i r * sumN q (fun s => B r s * C s j))
      = sumN p (fun r => sumN q (fun s => A i r * (B r s * C s j))) :=
          sumN_congr p _ _ (fun r _ => (sumN_mul_left q (A i r) _).symm)
    _ = sumN q (fun s => sumN p (fun r => A i r * (B r s * C s j))) := sumN_comm p q _
    _ = sumN q (fun s => sumN p (fun r => (A i r * B r s) * C s j)) :=
          sumN_congr q _ _ (fun s _ => sumN_congr p _ _ (fun r _ => (Int.mul_assoc _ _ _).symm))
    _ = sumN q (fun s => sumN p (fun r => A i r * B r s) * C s j) :=
          sumN_congr q _ _ (fun s _ => sumN_mul_right p (C s j) _)

private theorem dotN_matVec_skew_zero (n : Nat) (K : Nat → Nat → Int) (h : Nat → Int)
    (hskew : IsSkew n K) : dotN n h (matVec n K h) = 0 := by
  have h1 : dotN n h (matVec n K h) =
      sumN n (fun i => sumN n (fun j => h i * (K i j * h j))) := by
    unfold dotN matVec matVecRect
    exact sumN_congr n _ _ (fun i _ => (sumN_mul_left n (h i) _).symm)
  have h2 : sumN n (fun i => sumN n (fun j => h i * (K i j * h j))) =
      -(sumN n (fun i => sumN n (fun j => h i * (K i j * h j)))) := by
    calc sumN n (fun i => sumN n (fun j => h i * (K i j * h j)))
        = sumN n (fun j => sumN n (fun i => h i * (K i j * h j))) := sumN_comm n n _
      _ = sumN n (fun j => sumN n (fun i => -(h j * (K j i * h i)))) := by
            apply sumN_congr; intro j hj; apply sumN_congr; intro i hi
            rw [hskew i j hi hj, Int.neg_mul, Int.mul_neg]
            have hr : h i * (K j i * h j) = h j * (K j i * h i) := by
              rw [← Int.mul_assoc, Int.mul_comm (h i) (K j i), Int.mul_assoc,
                  Int.mul_comm (h i) (h j), ← Int.mul_assoc, Int.mul_comm (K j i) (h j),
                  Int.mul_assoc]
            rw [hr]
      _ = sumN n (fun j => -(sumN n (fun i => h j * (K j i * h i)))) :=
            sumN_congr n _ _ (fun j _ => sumN_neg n _)
      _ = -(sumN n (fun j => sumN n (fun i => h j * (K j i * h i)))) := sumN_neg n _
  omega

-- ============================================================================
-- PORTAL 1: Biological Homeostasis, Sleep Renormalization & Integer LIF
-- ============================================================================

def reluInt (x : Int) : Int := if 0 ≤ x then x else 0
def bingham (tau u : Int) : Int := reluInt (u - tau) - reluInt (-u - tau)

/-- Theorem 1 (Portal 1 — P1.1): Multiplicative scaling preserves Track S31/S110
    row concentration C_row(λ ΔW) <= C_max identically for EVERY non-zero λ. -/
theorem p1_mult_crow_invariance (lam rowNormSq totalNormSq cNum cDen : Int)
    (hlam : lam ≠ 0) :
    rowNormSq * cDen ≤ cNum * totalNormSq ↔
    (lam * lam * rowNormSq) * cDen ≤ cNum * (lam * lam * totalNormSq) := by
  have hpos : 0 < lam * lam := int_sq_pos_of_ne_zero lam hlam
  have hl : (lam * lam * rowNormSq) * cDen = (lam * lam) * (rowNormSq * cDen) := Int.mul_assoc _ _ _
  have hr : cNum * (lam * lam * totalNormSq) = (lam * lam) * (cNum * totalNormSq) := by
    rw [← Int.mul_assoc, Int.mul_comm cNum (lam * lam), Int.mul_assoc]
  rw [hl, hr]
  constructor
  · intro h; exact int_mul_le_left_nonneg (lam * lam) _ _ (Int.le_of_lt hpos) h
  · intro h
    if hle : rowNormSq * cDen ≤ cNum * totalNormSq then
      exact hle
    else
      have hgt : 0 < rowNormSq * cDen - cNum * totalNormSq := by omega
      have hmul : 0 < (lam * lam) * (rowNormSq * cDen - cNum * totalNormSq) := Int.mul_pos hpos hgt
      rw [Int.mul_sub] at hmul
      omega

/-- Theorem 2 (Portal 1 Obstruction P1-O1): Subtractive/Bingham pruning at tau = 3
    on Pythagorean rows [(3,4), (0,3)x3] (C_row = 25/52 <= 1/2) spikes C_row to 1 > 1/2
    and breaks additivity [S_3, +] != 0. -/
theorem p1_subtractive_bingham_crow_breach_and_nonadd :
    let r0 := 3 * 3 + 4 * 4
    let r1 := 0 * 0 + 3 * 3
    let tot := r0 + r1 + r1 + r1
    let p0 := bingham 3 3 * bingham 3 3 + bingham 3 4 * bingham 3 4
    let p1 := bingham 3 0 * bingham 3 0 + bingham 3 3 * bingham 3 3
    let ptot := p0 + p1 + p1 + p1
    (r0 * 2 ≤ tot) ∧ (ptot < p0 * 2) ∧
    (bingham 3 (3 + 3) ≠ bingham 3 3 + bingham 3 3) := by
  unfold bingham reluInt
  decide

def had4 (i j : Nat) : Int :=
  match i, j with
  | 0, 0 => 1 | 0, 1 => 1 | 0, 2 => 1 | 0, 3 => 1
  | 1, 0 => 1 | 1, 1 => -1 | 1, 2 => 1 | 1, 3 => -1
  | 2, 0 => 1 | 2, 1 => 1 | 2, 2 => -1 | 2, 3 => -1
  | 3, 0 => 1 | 3, 1 => -1 | 3, 2 => -1 | 3, 3 => 1
  | _, _ => 0

def diag4 (d0 d1 d2 d3 : Int) (i j : Nat) : Int :=
  if i = j then
    match i with
    | 0 => d0 | 1 => d1 | 2 => d2 | 3 => d3 | _ => 0
  else 0

/-- Theorem 3 (Portal 1 Obstruction P1-O3 — BlockH4 Commutation vs Anisotropic Breach):
    Isotropic scalar scaling λ I_4 commutes identically with BlockH4 for ALL λ : Int,
    whereas anisotropic D = diag(4, 1, 1, 1) fails to commute with H_4 (entry (0,1) = -3 != 0). -/
theorem p1_blockh4_isotropic_commutes_anisotropic_breaches (lam : Int) :
    (∀ i j, i < 4 → j < 4 →
      matMul 4 had4 (diag4 lam lam lam lam) i j = matMul 4 (diag4 lam lam lam lam) had4 i j) ∧
    commMat 4 had4 (diag4 4 1 1 1) 0 1 ≠ 0 := by
  constructor
  · intro i j hi hj
    unfold matMul matMulRect
    have hdiag : ∀ a b, a < 4 → diag4 lam lam lam lam a b = if a = b then lam else 0 := by
      intro a b ha
      unfold diag4
      if heq : a = b then
        rw [ite_eq_left_iff.mpr (fun h => absurd heq h), ite_eq_left_iff.mpr (fun h => absurd heq h)]
        cases a with
        | zero => rfl
        | succ a1 =>
          cases a1 with
          | zero => rfl
          | succ a2 =>
            cases a2 with
            | zero => rfl
            | succ a3 =>
              cases a3 with
              | zero => rfl
              | succ _ => omega
      else
        rw [ite_eq_right_iff.mpr (fun h => absurd h heq), ite_eq_right_iff.mpr (fun h => absurd h heq)]
    have hl : sumN 4 (fun r => had4 i r * diag4 lam lam lam lam r j) = had4 i j * lam := by
      have h1 : sumN 4 (fun r => had4 i r * diag4 lam lam lam lam r j) =
          sumN 4 (fun r => (had4 i r * lam) * basisVec j r) := by
        apply sumN_congr; intro r hr; rw [hdiag r j hr]; unfold basisVec
        if h : r = j then
          rw [ite_eq_left_iff.mpr (fun h0 => absurd h h0), ite_eq_left_iff.mpr (fun h0 => absurd h h0), Int.mul_one]
        else
          rw [ite_eq_right_iff.mpr (fun h0 => absurd h0 h), ite_eq_right_iff.mpr (fun h0 => absurd h0 h), Int.mul_zero, Int.mul_zero]
      rw [h1, sumN_kronecker_right 4 j (fun r => had4 i r * lam) hj]
    have hr : sumN 4 (fun r => diag4 lam lam lam lam i r * had4 r j) = lam * had4 i j := by
      have h1 : sumN 4 (fun r => diag4 lam lam lam lam i r * had4 r j) =
          sumN 4 (fun r => basisVec i r * (lam * had4 r j)) := by
        apply sumN_congr; intro r _; rw [hdiag i r hi]; unfold basisVec
        if h : r = i then
          subst h
          rw [ite_eq_left_iff.mpr (fun h0 => absurd rfl h0), ite_eq_left_iff.mpr (fun h0 => absurd rfl h0), Int.one_mul]
        else
          have h' : i ≠ r := fun h0 => h h0.symm
          rw [ite_eq_right_iff.mpr (fun h0 => absurd h0 h'), ite_eq_right_iff.mpr (fun h0 => absurd h0 h), Int.zero_mul, Int.zero_mul]
      rw [h1, sumN_kronecker_left 4 i (fun r => lam * had4 r j) hi]
    rw [hl, hr, Int.mul_comm]
  · unfold commMat matMul matMulRect sumN had4 diag4
    decide

/-- Theorem 4 (Portal 1 — P1.2): Isotropic scalar consolidation λ (G P_perp) preserves
    exact zero base forgetting (G P_perp X_base = 0) in EVERY dimension n and for ALL λ : Int. -/
theorem p1_isotropic_dark_mode_commutation (n : Nat) (lam : Int) (G P X : Nat → Nat → Int)
    (hnull : ∀ i k, i < n → k < n → matMul n P X i k = 0) :
    ∀ i k, i < n → k < n → matMul n (scaleMat lam (matMul n G P)) X i k = 0 := by
  intro i k hi hk
  unfold scaleMat matMul matMulRect
  calc sumN n (fun r => (lam * matMul n G P i r) * X r k)
      = sumN n (fun r => lam * (matMul n G P i r * X r k)) :=
          sumN_congr n _ _ (fun r _ => Int.mul_assoc _ _ _)
    _ = lam * sumN n (fun r => matMul n G P i r * X r k) := sumN_mul_left n lam _
    _ = lam * matMulRect n n n (matMulRect n n n G P) X i k := rfl
    _ = lam * matMulRect n n n G (matMulRect n n n P X) i k := by rw [← matMul_assoc n n n n G P X i k]
    _ = lam * sumN n (fun r => G i r * matMul n P X r k) := rfl
    _ = lam * sumN n (fun _ => 0) := by
          have hs : sumN n (fun r => G i r * matMul n P X r k) = sumN n (fun _ => 0) :=
            sumN_congr n _ _ (fun r hr => by rw [hnull r k hr hk, Int.mul_zero])
          rw [hs]
    _ = 0 := by rw [sumN_zero, Int.mul_zero]

/-- Theorem 5 (Portal 1 Obstruction P1-O3 — Input-Side Anisotropic Nullspace Shatter):
    On rank-2 X_base with dark-mode projector 2*P_perp = [[1,0,-1,0],[0,1,0,-1],[-1,0,1,0],[0,-1,0,1]],
    P_perp X_base = 0, yet input-side D = diag(4,1,1,1) breaks (P_perp D X_base)_{0,0} = 3 != 0. -/
theorem p1_anisotropic_input_shatters_nullspace :
    let pPerp2 : Nat → Nat → Int := fun i j =>
      if i = j then 1 else if (i = 0 ∧ j = 2) ∨ (i = 2 ∧ j = 0) ∨ (i = 1 ∧ j = 3) ∨ (i = 3 ∧ j = 1) then -1 else 0
    let xBase : Nat → Nat → Int := fun i j =>
      if (i = 0 ∧ j = 0) ∨ (i = 2 ∧ j = 0) ∨ (i = 1 ∧ j = 1) ∨ (i = 3 ∧ j = 1) then 1 else 0
    (matMul 4 pPerp2 xBase 0 0 = 0) ∧
    (matMul 4 (matMul 4 pPerp2 (diag4 4 1 1 1)) xBase 0 0 ≠ 0) := by
  unfold matMul matMulRect sumN diag4
  decide

/-- Theorem 6 (Portal 1 Obstruction P1-O5 & Cosine Repair):
    Multiplicative scaling by 0 < num/den < 1 preserves positive sign yet crosses any
    nonzero safety margin tau whenever num * m < den * tau (witness: 3/4 * 5/2 = 15/8 < 2),
    while squared cosine (dot^2 / norm^2) and its threshold gate are identically invariant
    for ALL λ != 0. The fixed `decide` conjuncts (3*5 < 4*4, 0 < 3*5) are literal witnesses,
    not quantified structural statements. -/
theorem p1_mult_safety_margin_crossing_and_cos_repair (lam dotVal normSq cNum cDen : Int)
    (hlam : lam ≠ 0) :
    ((3 : Int) * 5 < 4 * 4 ∧ 0 < (3 : Int) * 5) ∧
    ((lam * dotVal) * (lam * dotVal) * normSq = dotVal * dotVal * (lam * lam * normSq)) ∧
    (dotVal * dotVal * cDen ≤ cNum * normSq ↔
      (lam * dotVal) * (lam * dotVal) * cDen ≤ cNum * (lam * lam * normSq)) := by
  have h1 : (lam * dotVal) * (lam * dotVal) = (lam * lam) * (dotVal * dotVal) := by
    rw [Int.mul_assoc lam dotVal, ← Int.mul_assoc dotVal lam dotVal, Int.mul_comm dotVal lam,
        Int.mul_assoc lam dotVal dotVal, ← Int.mul_assoc lam lam]
  refine ⟨⟨by omega, by omega⟩, ?_, ?_⟩
  · rw [h1, Int.mul_assoc (lam * lam), Int.mul_comm (lam * lam) (dotVal * dotVal * normSq),
        Int.mul_assoc (dotVal * dotVal) normSq (lam * lam), Int.mul_comm normSq (lam * lam)]
  · rw [h1]
    exact p1_mult_crow_invariance lam (dotVal * dotVal) normSq cNum cDen hlam

def lifV1 (v g : Nat) : Nat := (19 * v + g) / 20
def lifG1 (g : Nat) : Nat := (4 * g) / 5
def lifE (v g : Nat) : Nat := 4 * v + g

/-- Theorem 7 (Portal 1 — Track S102 Universal Integer LIF 2-Step LaSalle Lyapunov):
    Universally for ALL natural numbers v, g : Nat (infinite state space!),
    1. E(v1, g1) <= E(v, g) (1-step non-increasing),
    2. Exact lossless transfer tie at (0, 20): E(lifV1 0 20, lifG1 20) = E(0, 20) = 20,
    3. Strict 2-step LaSalle contraction: for EVERY (v, g) != (0, 0), E(v2, g2) < E(v, g). -/
theorem p1_lif_lyapunov_universal_2step_lasalle (v g : Nat) :
    lifE (lifV1 v g) (lifG1 g) ≤ lifE v g ∧
    lifE (lifV1 0 20) (lifG1 20) = lifE 0 20 ∧
    ((v ≠ 0 ∨ g ≠ 0) → lifE (lifV1 (lifV1 v g) (lifG1 g)) (lifG1 (lifG1 g)) < lifE v g) := by
  refine ⟨?_, ?_, ?_⟩
  · unfold lifE lifV1 lifG1; omega
  · unfold lifE lifV1 lifG1; decide
  · intro hne
    unfold lifE lifV1 lifG1
    omega

-- ============================================================================
-- PORTAL 2: Turing Morphogenesis & Discrete Reaction-Diffusion
-- ============================================================================

/-- Theorem 8 (Portal 2 Obstruction O2.1 — Universal Equal-Diffusion Impossibility):
    If tr(J) < 0 and det(J) > 0, then for EVERY equal diffusion d >= 0 and EVERY
    Laplacian eigenvalue mu >= 0, tr(J - d*mu*I) < 0 and det(J - d*mu*I) > 0 identically.
    Equal-rate coupling can NEVER produce Turing symmetry breaking on ANY graph. -/
theorem p2_equal_diffusion_turing_impossible (j11 j12 j21 j22 d mu : Int)
    (htr : j11 + j22 < 0) (hdet : 0 < j11 * j22 - j12 * j21)
    (hd : 0 ≤ d) (hmu : 0 ≤ mu) :
    (j11 - d * mu) + (j22 - d * mu) < 0 ∧
    0 < (j11 - d * mu) * (j22 - d * mu) - j12 * j21 := by
  have hdmu : 0 ≤ d * mu := Int.mul_nonneg hd hmu
  have htr_neg : 0 ≤ -(j11 + j22) := by omega
  have hlin : 0 ≤ (d * mu) * (-(j11 + j22)) := Int.mul_nonneg hdmu htr_neg
  have hsq : 0 ≤ (d * mu) * (d * mu) := int_sq_nonneg (d * mu)
  have hexp :
      (j11 - d * mu) * (j22 - d * mu) - j12 * j21 =
      (j11 * j22 - j12 * j21) + (d * mu) * (-(j11 + j22)) + (d * mu) * (d * mu) := by
    simp only [Int.sub_mul, Int.mul_sub, Int.mul_neg, Int.mul_add]
    rw [Int.mul_comm j11 (d * mu)]
    omega
  exact ⟨by omega, by omega⟩

/-- Theorem 9 (Portal 2): Under tr(J) < 0 and non-negative diffusion du, dv, mu >= 0,
    the coupled mode trace tr(J - mu*D) remains strictly negative for ALL modes. -/
theorem p2_turing_trace_stays_negative (j11 j22 du dv mu : Int)
    (htr : j11 + j22 < 0) (hdu : 0 ≤ du) (hdv : 0 ≤ dv) (hmu : 0 ≤ mu) :
    (j11 - du * mu) + (j22 - dv * mu) < 0 := by
  have h1 : 0 ≤ du * mu := Int.mul_nonneg hdu hmu
  have h2 : 0 ≤ dv * mu := Int.mul_nonneg hdv hmu
  omega

/-- Theorem 10 (Portal 2 — Universal Turing Necessity Theorem):
    If a stable reaction matrix J (tr < 0, det > 0) becomes Turing-unstable at some
    mode mu >= 0 with du, dv >= 0 (det(J - mu*D) < 0), then NECESSARILY:
    1. dv * j11 + du * j22 > 0,
    2. du != dv (differential diffusion required), and
    3. j11 * j22 < 0 (activator/inhibitor sign opposition required). -/
theorem p2_turing_instability_necessity (j11 j12 j21 j22 du dv mu : Int)
    (htr : j11 + j22 < 0) (hdet : 0 < j11 * j22 - j12 * j21)
    (hdu : 0 ≤ du) (hdv : 0 ≤ dv) (hmu : 0 ≤ mu)
    (hinst : (j11 - du * mu) * (j22 - dv * mu) - j12 * j21 < 0) :
    0 < dv * j11 + du * j22 ∧ du ≠ dv ∧ j11 * j22 < 0 := by
  have hquad :
      (j11 - du * mu) * (j22 - dv * mu) - j12 * j21 =
      (du * mu) * (dv * mu) - mu * (dv * j11 + du * j22) + (j11 * j22 - j12 * j21) := by
    simp only [Int.sub_mul, Int.mul_sub, Int.mul_add]
    have e1 : j11 * (dv * mu) = mu * (dv * j11) := by
      rw [← Int.mul_assoc, Int.mul_comm j11 dv, Int.mul_comm (dv * j11) mu]
    have e2 : du * mu * j22 = mu * (du * j22) := by
      rw [Int.mul_assoc du mu j22, Int.mul_comm mu j22, ← Int.mul_assoc, Int.mul_comm (du * j22) mu]
    rw [e1, e2]
    omega
  have hduv : 0 ≤ (du * mu) * (dv * mu) := Int.mul_nonneg (Int.mul_nonneg hdu hmu) (Int.mul_nonneg hdv hmu)
  have hmu_term : 0 < mu * (dv * j11 + du * j22) := by omega
  have hlin_pos : 0 < dv * j11 + du * j22 := by
    if h : 0 < dv * j11 + du * j22 then
      exact h
    else
      have hle : dv * j11 + du * j22 ≤ 0 := by omega
      have hprod : mu * (dv * j11 + du * j22) ≤ 0 := by
        have := Int.mul_nonneg hmu (show 0 ≤ -(dv * j11 + du * j22) by omega)
        rw [Int.mul_neg] at this
        omega
      omega
  have hne : du ≠ dv := by
    intro heq
    subst heq
    have hcontra := (p2_equal_diffusion_turing_impossible j11 j12 j21 j22 du mu htr hdet hdu hmu).2
    omega
  have hopp : j11 * j22 < 0 := by
    if h1 : 0 < j11 then
      have h2 : j22 < 0 := by omega
      have hpos : 0 < j11 * (-j22) := Int.mul_pos h1 (by omega)
      rw [Int.mul_neg] at hpos
      omega
    else
      have h1le : j11 ≤ 0 := by omega
      if h2 : 0 < j22 then
        have h1neg : j11 < 0 := by omega
        have hpos : 0 < (-j11) * j22 := Int.mul_pos (by omega) h2
        rw [Int.neg_mul] at hpos
        omega
      else
        have h2le : j22 ≤ 0 := by omega
        have p1 : dv * j11 ≤ 0 := by
          have := Int.mul_nonneg hdv (show 0 ≤ -j11 by omega); rw [Int.mul_neg] at this; omega
        have p2 : du * j22 ≤ 0 := by
          have := Int.mul_nonneg hdu (show 0 ≤ -j22 by omega); rw [Int.mul_neg] at this; omega
        omega
  exact ⟨hlin_pos, hne, hopp⟩

/-- Theorem 11 (Portal 2 — Arbitrary-Dim Mode Factorization Identity):
    For any graph Laplacian eigenmode L q = mu * q in arbitrary dimension n,
    the coupled 2-channel operator (I_n ⊗ J - L ⊗ D) acts on (u * q, v * q) exactly
    as the 2x2 mode matrix (J - mu * D) on (u, v). -/
theorem p2_mode_factorization_identity (n : Nat) (L : Nat → Nat → Int) (q : Nat → Int)
    (mu j11 j12 j21 j22 du dv u v : Int)
    (heig : ∀ i, i < n → matVec n L q i = mu * q i) :
    ∀ i, i < n →
      (j11 * (u * q i) + j12 * (v * q i) - du * matVec n L (fun r => u * q r) i =
        ((j11 - du * mu) * u + j12 * v) * q i) ∧
      (j21 * (u * q i) + j22 * (v * q i) - dv * matVec n L (fun r => v * q r) i =
        (j21 * u + (j22 - dv * mu) * v) * q i) := by
  intro i hi
  have hlu : matVec n L (fun r => u * q r) i = u * (mu * q i) := by
    unfold matVec matVecRect
    calc sumN n (fun j => L i j * (u * q j))
        = sumN n (fun j => u * (L i j * q j)) :=
            sumN_congr n _ _ (fun j _ => by rw [← Int.mul_assoc, Int.mul_comm (L i j) u, Int.mul_assoc])
      _ = u * matVec n L q i := sumN_mul_left n u _
      _ = u * (mu * q i) := by rw [heig i hi]
  have hlv : matVec n L (fun r => v * q r) i = v * (mu * q i) := by
    unfold matVec matVecRect
    calc sumN n (fun j => L i j * (v * q j))
        = sumN n (fun j => v * (L i j * q j)) :=
            sumN_congr n _ _ (fun j _ => by rw [← Int.mul_assoc, Int.mul_comm (L i j) v, Int.mul_assoc])
      _ = v * matVec n L q i := sumN_mul_left n v _
      _ = v * (mu * q i) := by rw [heig i hi]
  rw [hlu, hlv]
  constructor
  · simp only [Int.add_mul, Int.sub_mul]
    have t1 : j11 * (u * q i) = j11 * u * q i := (Int.mul_assoc _ _ _).symm
    have t2 : j12 * (v * q i) = j12 * v * q i := (Int.mul_assoc _ _ _).symm
    have t3 : du * (u * (mu * q i)) = du * mu * u * q i := by
      rw [← Int.mul_assoc du u, ← Int.mul_assoc (du * u) mu (q i),
          Int.mul_assoc du u mu, Int.mul_comm u mu, ← Int.mul_assoc du mu u]
    rw [t1, t2, t3]; omega
  · simp only [Int.add_mul, Int.sub_mul]
    have t1 : j21 * (u * q i) = j21 * u * q i := (Int.mul_assoc _ _ _).symm
    have t2 : j22 * (v * q i) = j22 * v * q i := (Int.mul_assoc _ _ _).symm
    have t3 : dv * (v * (mu * q i)) = dv * mu * v * q i := by
      rw [← Int.mul_assoc dv v, ← Int.mul_assoc (dv * v) mu (q i),
          Int.mul_assoc dv v mu, Int.mul_comm v mu, ← Int.mul_assoc dv mu v]
    rw [t1, t2, t3]; omega

/-- Theorem 12 (Portal 2 Obstruction O2.2 — Exact Witness Band Factorization & C_4 vs C_6 Aliasing):
    For witness 2*delta(mu) = 20*mu^2 - 120*mu + 175 = 5*(2*mu - 5)*(2*mu - 7):
    mode mu = 3 (present on C_6) is strictly unstable (-5 < 0), while all C_4 eigenvalues
    {0, 2, 4} remain strictly stable (> 0). -/
theorem p2_witness_band_exact_factorization (mu : Int) :
    (20 * mu * mu - 120 * mu + 175 = 5 * (2 * mu - 5) * (2 * mu - 7)) ∧
    ((20 : Int) * 3 * 3 - 120 * 3 + 175 < 0) ∧
    (0 < (20 : Int) * 0 * 0 - 120 * 0 + 175 ∧ 0 < (20 : Int) * 2 * 2 - 120 * 2 + 175 ∧ 0 < (20 : Int) * 4 * 4 - 120 * 4 + 175) := by
  refine ⟨?_, by decide, ⟨by decide, by decide, by decide⟩⟩
  simp only [Int.sub_mul, Int.mul_sub]
  have h1 : 5 * (2 * mu) * (2 * mu) = 20 * mu * mu := by
    rw [← Int.mul_assoc 5 2 mu]
    have h52 : (5 : Int) * 2 = 10 := rfl
    rw [h52, Int.mul_assoc 10 mu (2 * mu), ← Int.mul_assoc mu 2 mu, Int.mul_comm mu 2,
        Int.mul_assoc 2 mu mu, ← Int.mul_assoc 10 2 (mu * mu)]
    have h102 : (10 : Int) * 2 = 20 := rfl
    rw [h102, Int.mul_assoc]
  have h2 : 5 * (2 * mu) * 7 = 70 * mu := by
    rw [← Int.mul_assoc 5 2 mu]; have h52 : (5 : Int) * 2 = 10 := rfl
    rw [h52, Int.mul_assoc 10 mu 7, Int.mul_comm mu 7, ← Int.mul_assoc 10 7 mu]; rfl
  have h3 : 5 * 5 * (2 * mu) = 50 * mu := by
    rw [← Int.mul_assoc (5 * 5) 2 mu]; rfl
  rw [h1, h2, h3]
  omega

def completeLap (n : Nat) (i j : Nat) : Int :=
  if i = j then Int.ofNat n - 1 else -1

/-- Theorem 13 (Portal 2 Obstruction O2.3 — Complete Graph K_n Exact Two-Eigenspace Spectrum):
    For the explicit K_n graph Laplacian matrix `completeLap n` (n-1 on diagonal, -1 off-diagonal):
    1. Every constant vector (c, ..., c) is an eigenvector with eigenvalue 0: (L_Kn c)_i = 0;
    2. Every zero-sum vector (sumN n x = 0) is an eigenvector with identical degenerate
       eigenvalue n: (L_Kn x)_i = n * x_i for all i < n (all-or-none spectrum). -/
theorem p2_complete_graph_all_or_none_spectrum (n : Nat) (c : Int) (x : Nat → Int) :
    (∀ i, i < n → matVec n (completeLap n) (fun _ => c) i = 0) ∧
    (sumN n x = 0 → ∀ i, i < n → matVec n (completeLap n) x i = Int.ofNat n * x i) := by
  have hact : ∀ (u : Nat → Int) (i : Nat), i < n →
      matVec n (completeLap n) u i = Int.ofNat n * u i - sumN n u := by
    intro u i hi
    unfold matVec matVecRect completeLap
    have hsplit : sumN n (fun j => (if i = j then Int.ofNat n - 1 else -1) * u j) =
        sumN n (fun j => basisVec i j * (Int.ofNat n * u j) - u j) := by
      apply sumN_congr; intro j _; unfold basisVec
      if h : j = i then
        subst h
        rw [ite_eq_left_iff.mpr (fun h0 => absurd rfl h0), ite_eq_left_iff.mpr (fun h0 => absurd rfl h0),
            Int.one_mul, Int.sub_mul, Int.one_mul]
      else
        have h' : i ≠ j := fun h0 => h h0.symm
        rw [ite_eq_right_iff.mpr (fun h0 => absurd h0 h'), ite_eq_right_iff.mpr (fun h0 => absurd h0 h),
            Int.zero_mul, Int.neg_mul, Int.one_mul]
        omega
    rw [hsplit, sumN_sub, sumN_kronecker_left n i (fun j => Int.ofNat n * u j) hi]
  have hsum_const : ∀ m : Nat, sumN m (fun _ => c) = Int.ofNat m * c := by
    intro m
    induction m with
    | zero => simp only [sumN]; change (0 : Int) = 0 * c; rw [Int.zero_mul]
    | succ k ih =>
      simp only [sumN]
      rw [ih]
      have hof : Int.ofNat (k + 1) = Int.ofNat k + 1 := rfl
      rw [hof, Int.add_mul, Int.one_mul]
  constructor
  · intro i hi
    rw [hact (fun _ => c) i hi, hsum_const n]
    omega
  · intro hzero i hi
    rw [hact x i hi, hzero]
    omega

-- ============================================================================
-- PORTAL 3: Beltrami Force-Free Helicity Conservation & Collapse Obstructions
-- ============================================================================

/-- Theorem 14 (Portal 3): For symmetric C and skew-symmetric K in ANY dimension n,
    the commutator [C, K] = C K - K C is symmetric. -/
theorem p3_commutator_sym_of_sym_skew (n : Nat) (C K : Nat → Nat → Int)
    (hsym : IsSym n C) (hskew : IsSkew n K) : IsSym n (commMat n C K) := by
  intro i j hi hj
  unfold commMat matMul matMulRect
  have h1 : sumN n (fun r => C i r * K r j) = -(sumN n (fun r => K j r * C r i)) := by
    calc sumN n (fun r => C i r * K r j)
        = sumN n (fun r => -(K j r * C r i)) := by
            apply sumN_congr; intro r hr
            rw [hsym i r hi hr, hskew r j hr hj, Int.mul_neg, Int.mul_comm (C r i) (K j r)]
      _ = -(sumN n (fun r => K j r * C r i)) := sumN_neg n _
  have h2 : sumN n (fun r => K i r * C r j) = -(sumN n (fun r => C j r * K r i)) := by
    calc sumN n (fun r => K i r * C r j)
        = sumN n (fun r => -(C j r * K r i)) := by
            apply sumN_congr; intro r hr
            rw [hskew i r hi hr, hsym r j hr hj, Int.neg_mul, Int.mul_comm (K r i) (C j r)]
      _ = -(sumN n (fun r => C j r * K r i)) := sumN_neg n _
  omega

/-- Theorem 15 (Portal 3 — Exact Helicity Rate Identity & Conservation Under [C, K] = 0):
    For symmetric C and skew K in ANY dimension n and ANY state v:
    2 * <K v, C v> = <v, [C, K] v>; hence [C, K] = 0 implies <K v, C v> = 0 identically. -/
theorem p3_helicity_conservation_of_commuting (n : Nat) (C K : Nat → Nat → Int) (v : Nat → Int)
    (hsym : IsSym n C) (hskew : IsSkew n K) :
    (2 * dotN n (matVec n K v) (matVec n C v) = dotN n v (matVec n (commMat n C K) v)) ∧
    (MatComm n C K → dotN n (matVec n K v) (matVec n C v) = 0) := by
  have h_ck : dotN n (matVec n K v) (matVec n C v) = dotN n v (matVec n (matMul n C K) v) := by
    rw [dotN_comm, ← matVec_sym_adj n C v (matVec n K v) hsym]
    unfold dotN
    exact sumN_congr n _ _ (fun i _ => by rw [matVec_matMul n C K v i])
  have h_kc : dotN n (matVec n K v) (matVec n C v) = -(dotN n v (matVec n (matMul n K C) v)) := by
    have hadj : dotN n (matVec n K v) (matVec n C v) = -(dotN n v (matVec n K (matVec n C v))) := by
      rw [dotN_comm]
      unfold matVec
      rw [dotN_matVecRect_adj n n K (matVecRect n n C v) v]
      have hneg : dotN n (matVecRect n n (transposeMat K) (matVecRect n n C v)) v =
          -(dotN n (matVecRect n n K (matVecRect n n C v)) v) := by
        unfold dotN matVecRect transposeMat
        calc sumN n (fun i => sumN n (fun j => K j i * matVecRect n n C v j) * v i)
            = sumN n (fun i => -(sumN n (fun j => K i j * matVecRect n n C v j) * v i)) := by
                apply sumN_congr; intro i hi
                have hs : sumN n (fun j => K j i * matVecRect n n C v j) =
                    -(sumN n (fun j => K i j * matVecRect n n C v j)) := by
                  rw [← sumN_neg]
                  apply sumN_congr; intro j hj
                  rw [hskew j i hj hi, Int.neg_mul]
                rw [hs, Int.neg_mul]
          _ = -(sumN n (fun i => sumN n (fun j => K i j * matVecRect n n C v j) * v i)) := sumN_neg n _
      rw [hneg, dotN_comm]
    rw [hadj]
    have hmul : dotN n v (matVec n K (matVec n C v)) = dotN n v (matVec n (matMul n K C) v) := by
      unfold dotN
      exact sumN_congr n _ _ (fun i _ => by rw [matVec_matMul n K C v i])
    rw [hmul]
  have hdiff : dotN n v (matVec n (commMat n C K) v) =
      dotN n v (matVec n (matMul n C K) v) - dotN n v (matVec n (matMul n K C) v) := by
    unfold dotN matVec matVecRect commMat
    rw [← sumN_sub]
    apply sumN_congr; intro i _
    rw [← Int.mul_sub, ← sumN_sub]
    apply congrArg (fun z => v i * z)
    apply sumN_congr; intro j _
    exact Int.sub_mul _ _ _
  have hid : 2 * dotN n (matVec n K v) (matVec n C v) = dotN n v (matVec n (commMat n C K) v) := by
    omega
  constructor
  · exact hid
  · intro hcomm
    have hzero : dotN n v (matVec n (commMat n C K) v) = 0 := by
      unfold dotN matVec matVecRect commMat
      calc sumN n (fun i => v i * sumN n (fun j => (matMul n C K i j - matMul n K C i j) * v j))
          = sumN n (fun _ => 0) := by
              apply sumN_congr; intro i hi
              have hs : sumN n (fun j => (matMul n C K i j - matMul n K C i j) * v j) = 0 := by
                calc sumN n (fun j => (matMul n C K i j - matMul n K C i j) * v j)
                    = sumN n (fun _ => 0) := by
                        apply sumN_congr; intro j hj
                        rw [hcomm i j hi hj, Int.sub_self, Int.zero_mul]
                  _ = 0 := sumN_zero n
              rw [hs, Int.mul_zero]
        _ = 0 := sumN_zero n
    omega

/-- Theorem 16 (Portal 3 — Full Universal Iff Helicity Characterization):
    For symmetric C and skew-symmetric K in ANY dimension n,
    <K v, C v> = 0 for all v  IFF  [C, K] = 0 (via constructive polarization). -/
theorem p3_helicity_conservation_iff_commuting (n : Nat) (C K : Nat → Nat → Int)
    (hsym : IsSym n C) (hskew : IsSkew n K) :
    (∀ v, dotN n (matVec n K v) (matVec n C v) = 0) ↔ MatComm n C K := by
  constructor
  · intro hall i j hi hj
    let A := commMat n C K
    have hAsym : IsSym n A := p3_commutator_sym_of_sym_skew n C K hsym hskew
    have hAquad : ∀ v, dotN n v (matVec n A v) = 0 := by
      intro v
      have h1 := (p3_helicity_conservation_of_commuting n C K v hsym hskew).1
      rw [hall v, Int.mul_zero] at h1
      exact h1.symm
    have h_basis_eval : ∀ a b, a < n → b < n → dotN n (basisVec a) (matVec n A (basisVec b)) = A a b := by
      intro a b ha hb
      unfold dotN matVec matVecRect
      rw [sumN_kronecker_left n a _ ha]
      exact sumN_kronecker_right n b (fun j => A a j) hb
    have hAii : A i i = 0 := by
      rw [← h_basis_eval i i hi hi]
      exact hAquad (basisVec i)
    have hAjj : A j j = 0 := by
      rw [← h_basis_eval j j hj hj]
      exact hAquad (basisVec j)
    let u : Nat → Int := fun r => basisVec i r + basisVec j r
    have hAuu : dotN n u (matVec n A u) = 0 := hAquad u
    have hexp : dotN n u (matVec n A u) = A i i + A i j + A j i + A j j := by
      have hlin : ∀ r, matVec n A u r = matVec n A (basisVec i) r + matVec n A (basisVec j) r := by
        intro r; unfold matVec matVecRect; rw [← sumN_add]
        exact sumN_congr n _ _ (fun c _ => Int.mul_add (A r c) _ _)
      unfold dotN
      calc sumN n (fun r => (basisVec i r + basisVec j r) * matVec n A u r)
          = sumN n (fun r => basisVec i r * matVec n A (basisVec i) r +
                basisVec i r * matVec n A (basisVec j) r +
                basisVec j r * matVec n A (basisVec i) r +
                basisVec j r * matVec n A (basisVec j) r) := by
              apply sumN_congr; intro r _
              rw [hlin r, Int.add_mul, Int.mul_add, Int.mul_add]; omega
        _ = dotN n (basisVec i) (matVec n A (basisVec i)) +
            dotN n (basisVec i) (matVec n A (basisVec j)) +
            dotN n (basisVec j) (matVec n A (basisVec i)) +
            dotN n (basisVec j) (matVec n A (basisVec j)) := by
              unfold dotN; rw [sumN_add, sumN_add, sumN_add]
        _ = A i i + A i j + A j i + A j j := by
              rw [h_basis_eval i i hi hi, h_basis_eval i j hi hj,
                  h_basis_eval j i hj hi, h_basis_eval j j hj hj]
    have hAji : A j i = A i j := hAsym j i hj hi
    have hAij0 : A i j = 0 := by omega
    have : matMul n C K i j - matMul n K C i j = 0 := hAij0
    omega
  · intro hcomm v
    exact (p3_helicity_conservation_of_commuting n C K v hsym hskew).2 hcomm

/-- Theorem 17 (Portal 3 — Exact Cayley Conservation of BOTH Energy and Helicity):
    For any symmetric C, skew K with [C, K] = 0, scale s != 0, and Cayley step
    (s I + K) y = (s I - K) x in arbitrary dimension n, BOTH energy ‖y‖^2 = ‖x‖^2
    and helicity <y, C y> = <x, C x> are conserved identically. -/
theorem p3_cayley_preserves_energy_and_helicity (n : Nat) (C K : Nat → Nat → Int)
    (s : Int) (x y : Nat → Int) (hsym : IsSym n C) (hskew : IsSkew n K)
    (hcomm : MatComm n C K) (hs : s ≠ 0)
    (hcay : ∀ i, i < n → s * y i + matVec n K y i = s * x i - matVec n K x i) :
    normSqN n y = normSqN n x ∧ dotN n y (matVec n C y) = dotN n x (matVec n C x) := by
  let u : Nat → Int := fun i => y i + x i
  have hstep : ∀ i, i < n → matVec n K u i = -(s * (y i - x i)) := by
    intro i hi
    have hlin : matVec n K u i = matVec n K y i + matVec n K x i := by
      unfold matVec matVecRect; rw [← sumN_add]
      exact sumN_congr n _ _ (fun j _ => Int.mul_add (K i j) (y j) (x j))
    have hci := hcay i hi
    rw [Int.mul_sub]; omega
  -- 1. Energy conservation
  have hE : normSqN n y = normSqN n x := by
    have hwork : dotN n u (matVec n K u) = 0 := dotN_matVec_skew_zero n K u hskew
    have hdot : dotN n u (matVec n K u) = -(s * (normSqN n y - normSqN n x)) := by
      calc dotN n u (matVec n K u)
          = sumN n (fun i => u i * (-(s * (y i - x i)))) := by
              unfold dotN; exact sumN_congr n _ _ (fun i hi => by rw [hstep i hi])
        _ = sumN n (fun i => -(s * (y i * y i - x i * x i))) := by
              apply sumN_congr; intro i _; rw [Int.mul_neg]
              rw [← Int.mul_assoc, Int.mul_comm (y i + x i) s, Int.mul_assoc]
              have hsq : (y i + x i) * (y i - x i) = y i * y i - x i * x i := by
                rw [Int.add_mul, Int.mul_sub, Int.mul_sub, Int.mul_comm (x i) (y i)]; omega
              rw [hsq]
        _ = -(s * (normSqN n y - normSqN n x)) := by
              rw [sumN_neg, sumN_mul_left]; unfold normSqN dotN; rw [sumN_sub]
    have hs0 : s * normSqN n y = s * normSqN n x := by
      have : s * (normSqN n y - normSqN n x) = 0 := by omega
      rw [Int.mul_sub] at this; omega
    exact int_mul_cancel_left_nz s _ _ hs hs0
  -- 2. Helicity conservation
  have hH : dotN n y (matVec n C y) = dotN n x (matVec n C x) := by
    have hhel : dotN n (matVec n K u) (matVec n C u) = 0 :=
      (p3_helicity_conservation_of_commuting n C K u hsym hskew).2 hcomm
    have hCu : ∀ i, matVec n C u i = matVec n C y i + matVec n C x i := by
      intro i; unfold matVec matVecRect; rw [← sumN_add]
      exact sumN_congr n _ _ (fun j _ => Int.mul_add (C i j) (y j) (x j))
    have hcross : dotN n y (matVec n C x) = dotN n x (matVec n C y) := by
      rw [matVec_sym_adj n C y x hsym, dotN_comm]
    have hdotH : dotN n (matVec n K u) (matVec n C u) =
        -(s * (dotN n y (matVec n C y) - dotN n x (matVec n C x))) := by
      calc dotN n (matVec n K u) (matVec n C u)
          = sumN n (fun i => (-(s * (y i - x i))) * (matVec n C y i + matVec n C x i)) := by
              unfold dotN; exact sumN_congr n _ _ (fun i hi => by rw [hstep i hi, hCu i])
        _ = sumN n (fun i => -(s * ((y i * matVec n C y i + y i * matVec n C x i) -
                (x i * matVec n C y i + x i * matVec n C x i)))) := by
              apply sumN_congr; intro i _
              rw [Int.neg_mul, Int.mul_assoc s]
              have ha : (y i - x i) * (matVec n C y i + matVec n C x i) =
                  (y i * matVec n C y i + y i * matVec n C x i) -
                  (x i * matVec n C y i + x i * matVec n C x i) := by
                simp only [Int.sub_mul, Int.mul_add]; omega
              rw [ha]
        _ = -(s * ((dotN n y (matVec n C y) + dotN n y (matVec n C x)) -
                (dotN n x (matVec n C y) + dotN n x (matVec n C x)))) := by
              rw [sumN_neg, sumN_mul_left, sumN_sub, sumN_add, sumN_add]; rfl
        _ = -(s * (dotN n y (matVec n C y) - dotN n x (matVec n C x))) := by
              rw [hcross]; have : ∀ a b c : Int, (a + b) - (b + c) = a - c := by intro a b c; omega
              rw [this]
    have hs0 : s * dotN n y (matVec n C y) = s * dotN n x (matVec n C x) := by
      have : s * (dotN n y (matVec n C y) - dotN n x (matVec n C x)) = 0 := by omega
      rw [Int.mul_sub] at this; omega
    exact int_mul_cancel_left_nz s _ _ hs hs0
  exact ⟨hE, hH⟩

private theorem matPow_comm_self (n : Nat) (C : Nat → Nat → Int) :
    ∀ k, MatComm n (matPow n C k) C := by
  intro k
  induction k with
  | zero =>
    intro a b ha hb
    unfold matMul matMulRect matPow
    have hl : sumN n (fun r => (if a = r then 1 else 0) * C r b) = C a b := by
      have h1 : sumN n (fun r => (if a = r then 1 else 0) * C r b) =
          sumN n (fun r => basisVec a r * C r b) := by
        apply sumN_congr; intro r _; unfold basisVec
        if h : r = a then
          subst h; rw [ite_eq_left_iff.mpr (fun h0 => absurd rfl h0)]
        else
          have h' : a ≠ r := fun h0 => h h0.symm
          rw [ite_eq_right_iff.mpr (fun h0 => absurd h0 h'), ite_eq_right_iff.mpr (fun h0 => absurd h0 h)]
      rw [h1]; exact sumN_kronecker_left n a (fun r => C r b) ha
    have hr : sumN n (fun r => C a r * (if r = b then 1 else 0)) = C a b :=
      sumN_kronecker_right n b (fun r => C a r) hb
    rw [hl, hr]
  | succ m ihm =>
    intro a b ha hb
    show matMul n (matMul n (matPow n C m) C) C a b = matMul n C (matMul n (matPow n C m) C) a b
    calc matMul n (matMul n (matPow n C m) C) C a b
        = matMul n (matMul n C (matPow n C m)) C a b := by
            show sumN n (fun r => matMul n (matPow n C m) C a r * C r b) =
                 sumN n (fun r => matMul n C (matPow n C m) a r * C r b)
            apply sumN_congr; intro r hr
            rw [ihm a r ha hr]
      _ = matMul n C (matMul n (matPow n C m) C) a b :=
            (matMul_assoc n n n n C (matPow n C m) C a b).symm

private theorem matPow_sym_and_comm (n : Nat) (C K : Nat → Nat → Int)
    (hsym : IsSym n C) (hcomm : MatComm n C K) :
    ∀ j, IsSym n (matPow n C j) ∧ MatComm n (matPow n C j) K := by
  intro j
  induction j with
  | zero =>
    constructor
    · intro a b _ _
      unfold matPow
      if hab : a = b then
        rw [hab]
      else
        have hba : b ≠ a := fun h => hab h.symm
        rw [ite_eq_right_iff.mpr (fun h => absurd h hab), ite_eq_right_iff.mpr (fun h => absurd h hba)]
    · intro a b ha hb
      unfold matMul matMulRect matPow
      have hl : sumN n (fun r => (if a = r then 1 else 0) * K r b) = K a b := by
        have h1 : sumN n (fun r => (if a = r then 1 else 0) * K r b) =
            sumN n (fun r => basisVec a r * K r b) := by
          apply sumN_congr; intro r _; unfold basisVec
          if h : r = a then
            subst h; rw [ite_eq_left_iff.mpr (fun h0 => absurd rfl h0)]
          else
            have h' : a ≠ r := fun h0 => h h0.symm
            rw [ite_eq_right_iff.mpr (fun h0 => absurd h0 h'), ite_eq_right_iff.mpr (fun h0 => absurd h0 h)]
        rw [h1]; exact sumN_kronecker_left n a (fun r => K r b) ha
      have hr : sumN n (fun r => K a r * (if r = b then 1 else 0)) = K a b :=
        sumN_kronecker_right n b (fun r => K a r) hb
      rw [hl, hr]
  | succ k ih =>
    have hsym_k := ih.1
    have hcomm_k := ih.2
    have hcomm_C : MatComm n (matPow n C k) C := matPow_comm_self n C k
    constructor
    · intro a b ha hb
      show matMul n (matPow n C k) C a b = matMul n (matPow n C k) C b a
      calc matMul n (matPow n C k) C a b
          = sumN n (fun r => C b r * matPow n C k r a) := by
              unfold matMul matMulRect
              apply sumN_congr; intro r hr
              rw [hsym_k a r ha hr, hsym r b hr hb, Int.mul_comm]
        _ = matMul n C (matPow n C k) b a := rfl
        _ = matMul n (matPow n C k) C b a := (hcomm_C b a hb ha).symm
    · intro a b ha hb
      show matMul n (matMul n (matPow n C k) C) K a b =
           matMul n K (matMul n (matPow n C k) C) a b
      calc matMul n (matMul n (matPow n C k) C) K a b
          = matMul n (matPow n C k) (matMul n C K) a b := (matMul_assoc n n n n _ _ _ a b).symm
        _ = matMul n (matPow n C k) (matMul n K C) a b := by
              show sumN n (fun r => matPow n C k a r * matMul n C K r b) =
                   sumN n (fun r => matPow n C k a r * matMul n K C r b)
              apply sumN_congr; intro r hr
              rw [hcomm r b hr hb]
        _ = matMul n (matMul n (matPow n C k) K) C a b := matMul_assoc n n n n _ _ _ a b
        _ = matMul n (matMul n K (matPow n C k)) C a b := by
              show sumN n (fun r => matMul n (matPow n C k) K a r * C r b) =
                   sumN n (fun r => matMul n K (matPow n C k) a r * C r b)
              apply sumN_congr; intro r hr
              rw [hcomm_k a r ha hr]
        _ = matMul n K (matMul n (matPow n C k) C) a b := (matMul_assoc n n n n _ _ _ a b).symm

/-- Theorem 18 (Portal 3 — Obstruction O3.1 / All Moments Conserved):
    Under [C, K] = 0, the Cayley step preserves EVERY moment m_j(v) = <v, C^j v> for
    ALL j : Nat (no linear cross-shell cascade is possible without breaking [C, K] = 0). -/
theorem p3_cayley_preserves_all_moments (n : Nat) (C K : Nat → Nat → Int)
    (s : Int) (x y : Nat → Int) (hsym : IsSym n C) (hskew : IsSkew n K)
    (hcomm : MatComm n C K) (hs : s ≠ 0)
    (hcay : ∀ i, i < n → s * y i + matVec n K y i = s * x i - matVec n K x i) :
    ∀ j, dotN n y (matVec n (matPow n C j) y) = dotN n x (matVec n (matPow n C j) x) := by
  intro j
  have hp := matPow_sym_and_comm n C K hsym hcomm j
  exact (p3_cayley_preserves_energy_and_helicity n (matPow n C j) K s x y hp.1 hskew hp.2 hs hcay).2

/-- Theorem 19 (Portal 3 Obstruction O3.2 — Parity Flips Helicity):
    Any symmetric parity operator P with P C P = -C negates helicity identically
    for ALL states v: H(P v) = -H(v) (chirality must be explicitly broken). -/
theorem p3_parity_flips_helicity (n : Nat) (P C : Nat → Nat → Int) (v : Nat → Int)
    (hPsym : IsSym n P)
    (hanti : ∀ i j, i < n → j < n → matMul n P (matMul n C P) i j = -(C i j)) :
    dotN n (matVec n P v) (matVec n C (matVec n P v)) = -(dotN n v (matVec n C v)) := by
  rw [dotN_comm, matVec_sym_adj n P (matVec n C (matVec n P v)) v hPsym, dotN_comm]
  have h1 : ∀ i, i < n → matVec n P (matVec n C (matVec n P v)) i = -(matVec n C v i) := by
    intro i hi
    have hCP : matVec n P (matVec n C (matVec n P v)) i =
        matVec n P (matVec n (matMul n C P) v) i := by
      show sumN n (fun r => P i r * matVec n C (matVec n P v) r) =
           sumN n (fun r => P i r * matVec n (matMul n C P) v r)
      exact sumN_congr n _ _ (fun r _ => by rw [matVec_matMul n C P v r])
    rw [hCP, matVec_matMul n P (matMul n C P) v i]
    unfold matVec matVecRect
    rw [← sumN_neg]
    apply sumN_congr; intro j hj
    rw [hanti i j hi hj, Int.neg_mul]
  unfold dotN
  rw [← sumN_neg]
  apply sumN_congr; intro i hi
  rw [h1 i hi, Int.mul_neg]

/-- Theorem 20 (Portal 3 Obstruction O3.5 — Symmetric Residual Collapse / Rayleigh Increase):
    For any diagonal Beltrami eigenbasis lam : Nat -> Int, positive step c > 0, and
    amplitude v : Nat -> Int where every pair satisfies 2 + c*(lam_i + lam_j) >= 0,
    the symmetric residual step w_i = (1 + c * lam_i) * v_i satisfies
    H(w) * E(v) >= H(v) * E(w) (strict increase on two distinct nonzero modes with
    2 + c*(lam_0 + lam_1) > 0, driving depth-loop mode collapse). -/
theorem p3_symmetric_residual_rayleigh_increase (n : Nat) (c : Int) (lam v : Nat → Int)
    (hc : 0 < c)
    (hstep : ∀ i j, i < n → j < n → 0 ≤ 2 + c * (lam i + lam j)) :
    let w : Nat → Int := fun i => (1 + c * lam i) * v i
    let E_v := sumN n (fun i => v i * v i)
    let H_v := sumN n (fun i => lam i * (v i * v i))
    let E_w := sumN n (fun i => w i * w i)
    let H_w := sumN n (fun i => lam i * (w i * w i))
    H_v * E_w ≤ H_w * E_v := by
  let w : Nat → Int := fun i => (1 + c * lam i) * v i
  have hdiff :
      2 * (sumN n (fun i => lam i * (w i * w i)) * sumN n (fun j => v j * v j) -
           sumN n (fun i => lam i * (v i * v i)) * sumN n (fun j => w j * w j)) =
      sumN n (fun i => sumN n (fun j =>
        c * (v i * v i) * (v j * v j) * ((lam i - lam j) * (lam i - lam j)) *
        (2 + c * (lam i + lam j)))) := by
    have hprod : ∀ f g : Nat → Int,
        sumN n f * sumN n g = sumN n (fun i => sumN n (fun j => f i * g j)) := by
      intro f g
      rw [← sumN_mul_right]
      apply sumN_congr; intro i _
      exact (sumN_mul_left n (f i) g).symm
    have hA := hprod (fun i => lam i * (w i * w i)) (fun j => v j * v j)
    have hB := hprod (fun i => lam i * (v i * v i)) (fun j => w j * w j)
    rw [hA, hB, ← sumN_sub]
    have hsub : sumN n (fun i => sumN n (fun j => lam i * (w i * w i) * (v j * v j)) -
        sumN n (fun j => lam i * (v i * v i) * (w j * w j))) =
        sumN n (fun i => sumN n (fun j =>
          lam i * (w i * w i) * (v j * v j) - lam i * (v i * v i) * (w j * w j))) :=
      sumN_congr n _ _ (fun i _ => (sumN_sub n _ _).symm)
    rw [hsub]
    let term : Nat → Nat → Int := fun i j =>
      lam i * (w i * w i) * (v j * v j) - lam i * (v i * v i) * (w j * w j)
    have hsym_sum : 2 * sumN n (fun i => sumN n (fun j => term i j)) =
        sumN n (fun i => sumN n (fun j => term i j + term j i)) := by
      have htw : 2 * sumN n (fun i => sumN n (fun j => term i j)) =
          sumN n (fun i => sumN n (fun j => term i j)) +
          sumN n (fun j => sumN n (fun i => term i j)) := by
        rw [sumN_comm n n term, Int.two_mul]
      rw [htw, ← sumN_add]
      apply sumN_congr; intro i _
      exact (sumN_add n _ _).symm
    rw [hsym_sum]
    apply sumN_congr; intro i _; apply sumN_congr; intro j _
    -- Pointwise algebraic identity: term i j + term j i = c * v_i^2 * v_j^2 * (l_i - l_j)^2 * (2 + c*(l_i+l_j))
    have hwi : w i * w i = (1 + c * lam i) * (1 + c * lam i) * (v i * v i) := by
      show ((1 + c * lam i) * v i) * ((1 + c * lam i) * v i) = _
      rw [Int.mul_assoc (1 + c * lam i) (v i), ← Int.mul_assoc (v i) (1 + c * lam i) (v i),
          Int.mul_comm (v i) (1 + c * lam i), Int.mul_assoc (1 + c * lam i) (v i) (v i),
          ← Int.mul_assoc (1 + c * lam i) (1 + c * lam i)]
    have hwj : w j * w j = (1 + c * lam j) * (1 + c * lam j) * (v j * v j) := by
      show ((1 + c * lam j) * v j) * ((1 + c * lam j) * v j) = _
      rw [Int.mul_assoc (1 + c * lam j) (v j), ← Int.mul_assoc (v j) (1 + c * lam j) (v j),
          Int.mul_comm (v j) (1 + c * lam j), Int.mul_assoc (1 + c * lam j) (v j) (v j),
          ← Int.mul_assoc (1 + c * lam j) (1 + c * lam j)]
    simp only [term]
    rw [hwi, hwj]
    let a := lam i; let b := lam j; let vi2 := v i * v i; let vj2 := v j * v j
    let s1 := (1 + c * a) * (1 + c * a); let s2 := (1 + c * b) * (1 + c * b)
    have hfactor :
        (a * (s1 * vi2) * vj2 - a * vi2 * (s2 * vj2)) +
        (b * (s2 * vj2) * vi2 - b * vj2 * (s1 * vi2)) =
        (vi2 * vj2) * ((a - b) * (s1 - s2)) := by
      have p1 : a * (s1 * vi2) * vj2 = (vi2 * vj2) * (a * s1) := by
        rw [← Int.mul_assoc a s1 vi2, Int.mul_assoc (a * s1) vi2 vj2, Int.mul_comm (a * s1)]
      have p2 : a * vi2 * (s2 * vj2) = (vi2 * vj2) * (a * s2) := by
        rw [Int.mul_assoc a vi2 (s2 * vj2), ← Int.mul_assoc vi2 s2 vj2, Int.mul_comm vi2 s2,
            Int.mul_assoc s2 vi2 vj2, ← Int.mul_assoc a s2 (vi2 * vj2), Int.mul_comm (a * s2)]
      have p3 : b * (s2 * vj2) * vi2 = (vi2 * vj2) * (b * s2) := by
        rw [← Int.mul_assoc b s2 vj2, Int.mul_assoc (b * s2) vj2 vi2, Int.mul_comm vj2 vi2, Int.mul_comm (b * s2)]
      have p4 : b * vj2 * (s1 * vi2) = (vi2 * vj2) * (b * s1) := by
        rw [Int.mul_assoc b vj2 (s1 * vi2), ← Int.mul_assoc vj2 s1 vi2, Int.mul_comm vj2 s1,
            Int.mul_assoc s1 vj2 vi2, Int.mul_comm vj2 vi2, ← Int.mul_assoc b s1 (vi2 * vj2), Int.mul_comm (b * s1)]
      rw [p1, p2, p3, p4]
      simp only [Int.sub_mul, Int.mul_sub]
      omega
    have hsdiff : s1 - s2 = c * (a - b) * (2 + c * (a + b)) := by
      simp only [s1, s2, Int.add_mul, Int.mul_add, Int.sub_mul, Int.mul_sub, Int.one_mul, Int.mul_one]
      have q1 : c * a * (c * a) = c * c * (a * a) := by
        rw [Int.mul_assoc c a (c * a), ← Int.mul_assoc a c a, Int.mul_comm a c,
            Int.mul_assoc c a a, ← Int.mul_assoc c c]
      have q2 : c * b * (c * b) = c * c * (b * b) := by
        rw [Int.mul_assoc c b (c * b), ← Int.mul_assoc b c b, Int.mul_comm b c,
            Int.mul_assoc c b b, ← Int.mul_assoc c c]
      have q3 : c * a * (c * b) = c * c * (a * b) := by
        rw [Int.mul_assoc c a (c * b), ← Int.mul_assoc a c b, Int.mul_comm a c,
            Int.mul_assoc c a b, ← Int.mul_assoc c c]
      have q4 : c * b * (c * a) = c * c * (a * b) := by
        rw [Int.mul_comm (c * b) (c * a)]; exact q3
      have q5 : c * a * 2 = c * a + c * a := by rw [Int.mul_comm (c * a) 2, Int.two_mul]
      have q6 : c * b * 2 = c * b + c * b := by rw [Int.mul_comm (c * b) 2, Int.two_mul]
      rw [q1, q2, q3, q4, q5, q6]
      omega
    rw [hfactor, hsdiff]
    have hfin :
        (vi2 * vj2) * ((a - b) * (c * (a - b) * (2 + c * (a + b)))) =
        c * vi2 * vj2 * ((a - b) * (a - b)) * (2 + c * (a + b)) := by
      rw [← Int.mul_assoc (a - b) (c * (a - b)), Int.mul_comm (a - b) (c * (a - b)),
          Int.mul_assoc c (a - b) (a - b), ← Int.mul_assoc (vi2 * vj2),
          ← Int.mul_assoc (vi2 * vj2) c, Int.mul_comm (vi2 * vj2) c, Int.mul_assoc c vi2 vj2]
    exact hfin
  have hnn : 0 ≤ sumN n (fun i => sumN n (fun j =>
      c * (v i * v i) * (v j * v j) * ((lam i - lam j) * (lam i - lam j)) *
      (2 + c * (lam i + lam j)))) := by
    apply sumN_nonneg; intro i hi
    apply sumN_nonneg; intro j hj
    exact Int.mul_nonneg
      (Int.mul_nonneg
        (Int.mul_nonneg (Int.mul_nonneg (Int.le_of_lt hc) (int_sq_nonneg (v i))) (int_sq_nonneg (v j)))
        (int_sq_nonneg (lam i - lam j)))
      (hstep i j hi hj)
  dsimp only [w] at hdiff
  dsimp only
  omega

-- ============================================================================
-- PORTAL 4: Murray's Law, Physarum Conductance, Schur-Thomson & Braess
-- ============================================================================

/-- Theorem 21 (Portal 4 — Plato 3^3 + 4^3 + 5^3 = 6^3 Murray Trifurcation & SOS Witness):
    Exact integer cube trifurcation and closed-form SOS optimality certificate at Q=216, c=2:
    J(u) - 108 = 2*(u - 36)^2*(u + 18) / u^2 >= 0 for all u > 0. -/
theorem p4_plato_murray_trifurcation (u : Int) (hu : 0 < u) :
    (3 * 3 * 3 + 4 * 4 * 4 + 5 * 5 * 5 = 6 * 6 * 6) ∧
    (216 * 216 + 2 * (u * u * u) - 108 * (u * u) = 2 * ((u - 36) * (u - 36)) * (u + 18)) ∧
    (108 * (u * u) ≤ 216 * 216 + 2 * (u * u * u)) := by
  have hsos : 216 * 216 + 2 * (u * u * u) - 108 * (u * u) = 2 * ((u - 36) * (u - 36)) * (u + 18) := by
    simp only [Int.sub_mul, Int.mul_sub, Int.mul_add]
    have c1 : 2 * (u * u) * u = 2 * (u * u * u) := Int.mul_assoc 2 (u * u) u
    have c2 : 2 * (u * 36) * u = 72 * (u * u) := by
      rw [Int.mul_comm u 36, ← Int.mul_assoc 2 36 u, Int.mul_assoc (2 * 36) u u]; rfl
    have c3 : 2 * (36 * u) * u = 72 * (u * u) := by
      rw [← Int.mul_assoc 2 36 u, Int.mul_assoc (2 * 36) u u]; rfl
    have c4 : 2 * (u * u) * 18 = 36 * (u * u) := by
      rw [Int.mul_comm (2 * (u * u)) 18, ← Int.mul_assoc 18 2 (u * u)]; rfl
    have c5 : 2 * (u * 36) * 18 = 1296 * u := by
      rw [Int.mul_comm u 36, ← Int.mul_assoc 2 36 u, Int.mul_comm (2 * 36 * u) 18,
          ← Int.mul_assoc 18 (2 * 36) u]; rfl
    have c6 : 2 * (36 * u) * 18 = 1296 * u := by
      rw [← Int.mul_assoc 2 36 u, Int.mul_comm (2 * 36 * u) 18, ← Int.mul_assoc 18 (2 * 36) u]; rfl
    have c7 : 2 * (36 * 36) * u = 2592 * u := rfl
    rw [c1, c2, c3, c4, c5, c6, c7]
    omega
  have hnn : 0 ≤ 2 * ((u - 36) * (u - 36)) * (u + 18) :=
    Int.mul_nonneg (Int.mul_nonneg (by omega) (int_sq_nonneg (u - 36))) (by omega)
  exact ⟨by decide, hsos, by omega⟩

/-- Theorem 22 (Portal 4 — Universal Murray's Law SOS Optimality for EVERY r : Int, u > 0):
    For Q = r^3 and c = 2 (optimal u* = r^2, J* = 3*r^2):
    Q^2 + 2*u^3 - 3*r^2*u^2 = (u - r^2)^2 * (2*u + r^2) >= 0 universally! -/
theorem p4_murray_general_sos_optimality (r u : Int) (hu : 0 < u) :
    let r2 := r * r
    let q := r * r * r
    (q * q + 2 * (u * u * u) - 3 * r2 * (u * u) = (u - r2) * (u - r2) * (2 * u + r2)) ∧
    (3 * r2 * (u * u) ≤ q * q + 2 * (u * u * u)) := by
  let r2 := r * r
  let q := r * r * r
  have hq2 : q * q = r2 * r2 * r2 := by
    simp only [q, r2]
    rw [Int.mul_assoc (r * r) r (r * r * r), ← Int.mul_assoc r (r * r) r,
        Int.mul_comm r (r * r), Int.mul_assoc (r * r) r r, ← Int.mul_assoc (r * r) (r * r)]
  have hsos : q * q + 2 * (u * u * u) - 3 * r2 * (u * u) = (u - r2) * (u - r2) * (2 * u + r2) := by
    rw [hq2]
    simp only [Int.sub_mul, Int.mul_sub, Int.mul_add]
    have e1 : u * u * (2 * u) = 2 * (u * u * u) := by
      rw [Int.mul_comm (u * u) (2 * u), Int.mul_assoc 2 u (u * u), Int.mul_comm u (u * u)]
    have e2 : u * r2 * (2 * u) = 2 * (r2 * (u * u)) := by
      rw [Int.mul_comm u r2, Int.mul_assoc r2 u (2 * u), Int.mul_comm u (2 * u),
          Int.mul_assoc 2 u u, ← Int.mul_assoc r2 2 (u * u), Int.mul_comm r2 2, Int.mul_assoc 2 r2 (u * u)]
    have e3 : r2 * u * (2 * u) = 2 * (r2 * (u * u)) := by
      rw [Int.mul_assoc r2 u (2 * u), Int.mul_comm u (2 * u), Int.mul_assoc 2 u u,
          ← Int.mul_assoc r2 2 (u * u), Int.mul_comm r2 2, Int.mul_assoc 2 r2 (u * u)]
    have e4 : r2 * r2 * (2 * u) = 2 * (r2 * r2 * u) := by
      rw [Int.mul_comm (r2 * r2) (2 * u), Int.mul_assoc 2 u (r2 * r2), Int.mul_comm u (r2 * r2)]
    have e5 : u * u * r2 = r2 * (u * u) := Int.mul_comm _ _
    have e6 : u * r2 * r2 = r2 * r2 * u := by rw [Int.mul_assoc u r2 r2, Int.mul_comm u (r2 * r2)]
    have e7 : r2 * u * r2 = r2 * r2 * u := by rw [Int.mul_assoc r2 u r2, Int.mul_comm u r2, ← Int.mul_assoc]
    have e8 : 3 * r2 * (u * u) = 3 * (r2 * (u * u)) := Int.mul_assoc 3 r2 (u * u)
    rw [e1, e2, e3, e4, e5, e6, e7, e8]
    omega
  have hr2 : 0 ≤ r2 := int_sq_nonneg r
  have hnn : 0 ≤ (u - r2) * (u - r2) * (2 * u + r2) :=
    Int.mul_nonneg (int_sq_nonneg (u - r2)) (by omega)
  dsimp only [r2, q] at hsos hnn
  dsimp only
  exact ⟨hsos, by omega⟩

/-- Theorem 23 (Portal 4 — Universal Schur-Thomson Dirichlet Minimum-Power Excess):
    For symmetric PSD interior block L_II and equilibrium phi satisfying L_II phi = rhs
    (i.e. 2*<L_II phi - rhs, delta> = 0), any perturbation phi + delta increases quadratic
    dissipation by exact Schur excess <delta, L_II delta> >= 0. -/
theorem p4_thomson_dirichlet_minimum_power (n : Nat) (L : Nat → Nat → Int)
    (phi rhs delta : Nat → Int) (hsym : IsSym n L)
    (hpsd : ∀ d, 0 ≤ dotN n d (matVec n L d))
    (heq : ∀ i, i < n → matVec n L phi i = rhs i) :
    let quad := fun x => dotN n x (matVec n L x) - 2 * dotN n x rhs
    quad (fun i => phi i + delta i) = quad phi + dotN n delta (matVec n L delta) ∧
    quad phi ≤ quad (fun i => phi i + delta i) := by
  have hlin : ∀ i, matVec n L (fun r => phi r + delta r) i = matVec n L phi i + matVec n L delta i := by
    intro i; unfold matVec matVecRect; rw [← sumN_add]
    exact sumN_congr n _ _ (fun j _ => Int.mul_add (L i j) (phi j) (delta j))
  have h1 : dotN n (fun i => phi i + delta i) (matVec n L (fun i => phi i + delta i)) =
      dotN n phi (matVec n L phi) + 2 * dotN n delta (matVec n L phi) +
      dotN n delta (matVec n L delta) := by
    have hcr : dotN n phi (matVec n L delta) = dotN n delta (matVec n L phi) := by
      rw [matVec_sym_adj n L phi delta hsym, dotN_comm]
    unfold dotN
    calc sumN n (fun i => (phi i + delta i) * matVec n L (fun r => phi r + delta r) i)
        = sumN n (fun i => (phi i * matVec n L phi i + phi i * matVec n L delta i) +
            (delta i * matVec n L phi i + delta i * matVec n L delta i)) := by
            apply sumN_congr; intro i _
            rw [hlin i, Int.add_mul, Int.mul_add, Int.mul_add]
      _ = (dotN n phi (matVec n L phi) + dotN n phi (matVec n L delta)) +
          (dotN n delta (matVec n L phi) + dotN n delta (matVec n L delta)) := by
            unfold dotN; rw [sumN_add, sumN_add, sumN_add]
      _ = dotN n phi (matVec n L phi) + 2 * dotN n delta (matVec n L phi) +
          dotN n delta (matVec n L delta) := by
            rw [hcr, Int.two_mul]; omega
  have h2 : dotN n (fun i => phi i + delta i) rhs = dotN n phi rhs + dotN n delta rhs := by
    unfold dotN; rw [← sumN_add]
    exact sumN_congr n _ _ (fun i _ => Int.add_mul (phi i) (delta i) (rhs i))
  have h3 : dotN n delta (matVec n L phi) = dotN n delta rhs := by
    unfold dotN; exact sumN_congr n _ _ (fun i hi => by rw [heq i hi])
  have hpos := hpsd delta
  dsimp only
  exact ⟨by rw [h1, h2, h3]; omega, by rw [h1, h2, h3]; omega⟩

/-- Theorem 24 (Portal 4 — P4.3 Physarum gamma=1 Global Shortest-Path Convergence):
    On L_1 = 1 < L_2 = 2, for EVERY positive (D1, D2), gamma=1 reinforcement
    strictly increases the conductance ratio D1'/D2' > D1/D2. -/
theorem p4_physarum_gamma1_global_ratio_increase (D1 D2 : Int) (h1 : 0 < D1) (h2 : 0 < D2) :
    let S := 2 * D1 + D2
    let num1 := D1 * S + 2 * D1
    let num2 := D2 * S + D2
    D1 * num2 < D2 * num1 := by
  have hp : 0 < D1 * D2 := Int.mul_pos h1 h2
  have h1eq : D1 * (D2 * (2 * D1 + D2) + D2) = D1 * D2 * (2 * D1 + D2) + D1 * D2 := by
    rw [Int.mul_add, Int.mul_assoc]
  have h2eq : D2 * (D1 * (2 * D1 + D2) + 2 * D1) = D1 * D2 * (2 * D1 + D2) + 2 * (D1 * D2) := by
    rw [Int.mul_add, ← Int.mul_assoc D2 D1, Int.mul_comm D2 D1,
        ← Int.mul_assoc D2 2 D1, Int.mul_comm D2 2, Int.mul_assoc 2 D2 D1, Int.mul_comm D2 D1]
  dsimp only
  rw [h1eq, h2eq]
  omega

/-- Theorem 25 (Portal 4 Obstruction P4-O1 — Physarum gamma=2 Two-Sided Separatrix Instability):
    On L_1 = 1 < L_2 = 2 with gamma=2, for EVERY positive (D1, D2):
    1. Above the separatrix (D2 > 4*D1), the ratio D1'/D2' STRICTLY DECREASES (suboptimal lock-in),
    2. Below the separatrix (D2 < 4*D1), the ratio D1'/D2' STRICTLY INCREASES (optimal basin),
    3. Exact unstable separatrix fixed point at (D1, D2) = (1/9, 4/9).
    Conjunct 3 is a fixed literal fixed-point witness (`decide`), not a quantified statement. -/
theorem p4_physarum_gamma2_separatrix_lockin (D1 D2 : Int)
    (h1 : 0 < D1) (h2 : 0 < D2) :
    let S := 2 * D1 + D2
    let num1 := D1 * (S * S) + 4 * (D1 * D1)
    let num2 := D2 * (S * S) + D2 * D2
    (4 * D1 < D2 → D2 * num1 < D1 * num2) ∧
    (D2 < 4 * D1 → D1 * num2 < D2 * num1) ∧
    (let fpS := 2 * 1 + 4; (1 * (fpS * fpS) + 4 * 9 * (1 * 1) = 2 * 1 * (fpS * fpS)) ∧
                           (4 * (fpS * fpS) + 9 * (4 * 4) = 2 * 4 * (fpS * fpS))) := by
  let S := 2 * D1 + D2
  have hdiff : D1 * (D2 * (S * S) + D2 * D2) - D2 * (D1 * (S * S) + 4 * (D1 * D1)) =
      (D1 * D2) * (D2 - 4 * D1) := by
    rw [Int.mul_add D1, Int.mul_add D2, Int.mul_sub (D1 * D2)]
    have e1 : D1 * (D2 * (S * S)) = D2 * (D1 * (S * S)) := by
      rw [← Int.mul_assoc D1 D2, Int.mul_comm D1 D2, Int.mul_assoc D2 D1]
    have e2 : D1 * (D2 * D2) = (D1 * D2) * D2 := (Int.mul_assoc D1 D2 D2).symm
    have e3 : D2 * (4 * (D1 * D1)) = (D1 * D2) * (4 * D1) := by
      rw [← Int.mul_assoc D2 4 (D1 * D1), Int.mul_comm D2 4, Int.mul_assoc 4 D2 (D1 * D1),
          ← Int.mul_assoc D2 D1 D1, Int.mul_comm D2 D1, Int.mul_comm 4 (D1 * D2 * D1),
          Int.mul_assoc (D1 * D2) D1 4, Int.mul_comm D1 4]
    rw [e1, e2, e3]
    omega
  have hprod_pos : 0 < D1 * D2 := Int.mul_pos h1 h2
  dsimp only [S] at hdiff
  dsimp only
  refine ⟨?_, ?_, ⟨by decide, by decide⟩⟩
  · intro hsep
    have hpos : 0 < (D1 * D2) * (D2 - 4 * D1) := Int.mul_pos hprod_pos (by omega)
    omega
  · intro hsep
    have hpos : 0 < (D1 * D2) * (4 * D1 - D2) := Int.mul_pos hprod_pos (by omega)
    have hneg : (D1 * D2) * (D2 - 4 * D1) = -((D1 * D2) * (4 * D1 - D2)) := by
      rw [← Int.mul_neg]
      have : D2 - 4 * D1 = -(4 * D1 - D2) := by omega
      rw [this]
    omega

/-- Theorem 26 (Portal 4 Obstruction P4-O2 — Rayleigh Monotonicity vs Braess Paradox):
    Exact rational cross-product witnesses separating Ohmic Wheatstone resistance reduction
    (4/3 < 43/32 < 3/2, improvement 3/2 - 43/32 = 5/32) from selfish Wardrop latency
    degradation (3/2 -> 2, penalty +1/2). All five conjuncts are fixed literal witnesses
    (`decide`), not quantified structural statements. -/
theorem p4_rayleigh_vs_braess_separation :
    (4 * 32 < 43 * 3) ∧ (43 * 2 < 3 * 32) ∧ (3 * 16 - 43 = 5) ∧
    (3 < 2 * 2) ∧ (2 * 2 - 3 = 1) := by
  decide

/-- Theorem 27 (Portal 4 Obstruction P4-O3 — Portal-B Density Chasm & Conductance Floor):
    For ALL vertex counts n0 >= 2001 (m_PB = 1000*n0 vs spanning tree m_tree = n0 - 1),
    the exact density ratio m_PB / m_tree satisfies 1000 < m_PB / m_tree <= 2001/2
    (tight iff n0 = 2001, where 2*m_PB = 2001*m_tree), and floor D_min = 1/16 gives 32/33 < 1.
    The last two conjuncts are fixed literal witnesses (`decide`/`omega` on constants),
    not quantified structural statements. -/
theorem p4_physarum_tree_portal_b_density_chasm (n0 : Nat) (hn : 2001 ≤ n0) :
    (1000 * (n0 - 1) < 1000 * n0) ∧
    (2 * (1000 * n0) ≤ 2001 * (n0 - 1)) ∧
    (2 * (1000 * 2001) = 2001 * (2001 - 1)) ∧
    (32 < 33) := by
  exact ⟨by omega, by omega, by decide, by omega⟩

-- ============================================================================
-- PORTAL 5: Darboux Isospectrality, Dark Modes, One-Sided Lapse Trace & Hopf Fiber
-- ============================================================================

def darbouxL1 (m n : Nat) (A : Nat → Nat → Int) (c : Int) (i j : Nat) : Int :=
  matMulRect n m n (transposeMat A) A i j + if i = j then c else 0

def darbouxL2 (m n : Nat) (A : Nat → Nat → Int) (c : Int) (i j : Nat) : Int :=
  matMulRect m n m A (transposeMat A) i j + if i = j then c else 0

/-- Theorem 28 (Portal 5 — Universal Rectangular Darboux Intertwining):
    For EVERY m, n : Nat, EVERY matrix A (m x n), and EVERY shift c : Int:
    A (A^T A + c I_n) = (A A^T + c I_m) A identically! -/
theorem p5_darboux_intertwining (m n : Nat) (A : Nat → Nat → Int) (c : Int) :
    ∀ i j, i < m → j < n →
      matMulRect m n n A (darbouxL1 m n A c) i j =
      matMulRect m m n (darbouxL2 m n A c) A i j := by
  intro i j hi hj
  unfold matMulRect darbouxL1 darbouxL2
  have hl : sumN n (fun r => A i r * (matMulRect n m n (transposeMat A) A r j + if r = j then c else 0)) =
      matMulRect m n n A (matMulRect n m n (transposeMat A) A) i j + A i j * c := by
    calc sumN n (fun r => A i r * (matMulRect n m n (transposeMat A) A r j + if r = j then c else 0))
        = sumN n (fun r => A i r * matMulRect n m n (transposeMat A) A r j +
              A i r * (if r = j then c else 0)) :=
            sumN_congr n _ _ (fun r _ => Int.mul_add _ _ _)
      _ = matMulRect m n n A (matMulRect n m n (transposeMat A) A) i j +
          sumN n (fun r => A i r * (if r = j then c else 0)) := sumN_add n _ _
      _ = matMulRect m n n A (matMulRect n m n (transposeMat A) A) i j + A i j * c := by
            have hc : sumN n (fun r => A i r * (if r = j then c else 0)) =
                sumN n (fun r => (A i r * c) * basisVec j r) := by
              apply sumN_congr; intro r _; unfold basisVec
              if h : r = j then
                rw [ite_eq_left_iff.mpr (fun h0 => absurd h h0), ite_eq_left_iff.mpr (fun h0 => absurd h h0), Int.mul_one]
              else
                rw [ite_eq_right_iff.mpr (fun h0 => absurd h0 h), ite_eq_right_iff.mpr (fun h0 => absurd h0 h), Int.mul_zero, Int.mul_zero]
            rw [hc, sumN_kronecker_right n j (fun r => A i r * c) hj]
  have hr : sumN m (fun r => (matMulRect m n m A (transposeMat A) i r + if i = r then c else 0) * A r j) =
      matMulRect m m n (matMulRect m n m A (transposeMat A)) A i j + c * A i j := by
    calc sumN m (fun r => (matMulRect m n m A (transposeMat A) i r + if i = r then c else 0) * A r j)
        = sumN m (fun r => matMulRect m n m A (transposeMat A) i r * A r j +
              (if i = r then c else 0) * A r j) :=
            sumN_congr m _ _ (fun r _ => Int.add_mul _ _ _)
      _ = matMulRect m m n (matMulRect m n m A (transposeMat A)) A i j +
          sumN m (fun r => (if i = r then c else 0) * A r j) := sumN_add m _ _
      _ = matMulRect m m n (matMulRect m n m A (transposeMat A)) A i j + c * A i j := by
            have hc : sumN m (fun r => (if i = r then c else 0) * A r j) =
                sumN m (fun r => basisVec i r * (c * A r j)) := by
              apply sumN_congr; intro r _; unfold basisVec
              if h : r = i then
                subst h; rw [ite_eq_left_iff.mpr (fun h0 => absurd rfl h0), ite_eq_left_iff.mpr (fun h0 => absurd rfl h0), Int.one_mul]
              else
                have h' : i ≠ r := fun h0 => h h0.symm
                rw [ite_eq_right_iff.mpr (fun h0 => absurd h0 h'), ite_eq_right_iff.mpr (fun h0 => absurd h0 h), Int.zero_mul, Int.zero_mul]
            rw [hc, sumN_kronecker_left m i (fun r => c * A r j) hi]
  rw [hl, hr, matMul_assoc m n m n A (transposeMat A) A i j, Int.mul_comm (A i j) c]

/-- Theorem 29 (Portal 5 — Darboux Eigenvector Transport & Exact Norm Scaling):
    If L_1 v = lam * v, then L_2 (A v) = lam * (A v) AND ‖A v‖^2 = (lam - c) * ‖v‖^2. -/
theorem p5_darboux_eigenvector_transport_and_norm (m n : Nat) (A : Nat → Nat → Int)
    (c lam : Int) (v : Nat → Int)
    (heig : ∀ j, j < n → matVec n (darbouxL1 m n A c) v j = lam * v j) :
    (∀ i, i < m → matVec m (darbouxL2 m n A c) (matVecRect m n A v) i =
      lam * matVecRect m n A v i) ∧
    normSqN m (matVecRect m n A v) = (lam - c) * normSqN n v := by
  constructor
  · intro i hi
    have hL2 : matVec m (darbouxL2 m n A c) (matVecRect m n A v) i =
        matVecRect m n (matMulRect m m n (darbouxL2 m n A c) A) v i := by
      unfold matVec matVecRect matMulRect
      calc sumN m (fun r => darbouxL2 m n A c i r * sumN n (fun j => A r j * v j))
          = sumN m (fun r => sumN n (fun j => darbouxL2 m n A c i r * (A r j * v j))) :=
              sumN_congr m _ _ (fun r _ => (sumN_mul_left n _ _).symm)
        _ = sumN n (fun j => sumN m (fun r => darbouxL2 m n A c i r * (A r j * v j))) := sumN_comm m n _
        _ = sumN n (fun j => sumN m (fun r => (darbouxL2 m n A c i r * A r j) * v j)) :=
              sumN_congr n _ _ (fun j _ => sumN_congr m _ _ (fun r _ => (Int.mul_assoc _ _ _).symm))
        _ = sumN n (fun j => sumN m (fun r => darbouxL2 m n A c i r * A r j) * v j) :=
              sumN_congr n _ _ (fun j _ => sumN_mul_right m (v j) _)
    have hL1 : matVecRect m n A (matVec n (darbouxL1 m n A c) v) i =
        matVecRect m n (matMulRect m n n A (darbouxL1 m n A c)) v i := by
      unfold matVec matVecRect matMulRect
      calc sumN n (fun r => A i r * sumN n (fun j => darbouxL1 m n A c r j * v j))
          = sumN n (fun r => sumN n (fun j => A i r * (darbouxL1 m n A c r j * v j))) :=
              sumN_congr n _ _ (fun r _ => (sumN_mul_left n _ _).symm)
        _ = sumN n (fun j => sumN n (fun r => A i r * (darbouxL1 m n A c r j * v j))) := sumN_comm n n _
        _ = sumN n (fun j => sumN n (fun r => (A i r * darbouxL1 m n A c r j) * v j)) :=
              sumN_congr n _ _ (fun j _ => sumN_congr n _ _ (fun r _ => (Int.mul_assoc _ _ _).symm))
        _ = sumN n (fun j => sumN n (fun r => A i r * darbouxL1 m n A c r j) * v j) :=
              sumN_congr n _ _ (fun j _ => sumN_mul_right n (v j) _)
    rw [hL2]
    have hint : matVecRect m n (matMulRect m m n (darbouxL2 m n A c) A) v i =
        matVecRect m n (matMulRect m n n A (darbouxL1 m n A c)) v i := by
      unfold matVecRect
      exact sumN_congr n _ _ (fun j hj => by rw [p5_darboux_intertwining m n A c i j hi hj])
    rw [hint, ← hL1]
    unfold matVecRect
    calc sumN n (fun j => A i j * matVec n (darbouxL1 m n A c) v j)
        = sumN n (fun j => A i j * (lam * v j)) := sumN_congr n _ _ (fun j hj => by rw [heig j hj])
      _ = sumN n (fun j => lam * (A i j * v j)) :=
            sumN_congr n _ _ (fun j _ => by rw [← Int.mul_assoc, Int.mul_comm (A i j) lam, Int.mul_assoc])
      _ = lam * sumN n (fun j => A i j * v j) := sumN_mul_left n lam _
  · have hnorm : normSqN m (matVecRect m n A v) =
        dotN n v (matVec n (darbouxL1 m n A c) v) - c * normSqN n v := by
      have hadj : normSqN m (matVecRect m n A v) =
          dotN n (matVecRect n m (transposeMat A) (matVecRect m n A v)) v := by
        unfold normSqN; exact dotN_matVecRect_adj m n A (matVecRect m n A v) v
      have hAtA : ∀ j, j < n →
          matVecRect n m (transposeMat A) (matVecRect m n A v) j + c * v j =
          matVec n (darbouxL1 m n A c) v j := by
        intro j hj
        unfold matVec matVecRect darbouxL1 matMulRect
        have hstep1 : sumN m (fun r => transposeMat A j r * sumN n (fun q => A r q * v q)) =
            sumN n (fun q => sumN m (fun r => transposeMat A j r * A r q) * v q) := by
          calc sumN m (fun r => transposeMat A j r * sumN n (fun q => A r q * v q))
              = sumN m (fun r => sumN n (fun q => transposeMat A j r * (A r q * v q))) :=
                  sumN_congr m _ _ (fun r _ => (sumN_mul_left n _ _).symm)
            _ = sumN n (fun q => sumN m (fun r => transposeMat A j r * (A r q * v q))) := sumN_comm m n _
            _ = sumN n (fun q => sumN m (fun r => (transposeMat A j r * A r q) * v q)) :=
                  sumN_congr n _ _ (fun q _ => sumN_congr m _ _ (fun r _ => (Int.mul_assoc _ _ _).symm))
            _ = sumN n (fun q => sumN m (fun r => transposeMat A j r * A r q) * v q) :=
                  sumN_congr n _ _ (fun q _ => sumN_mul_right m (v q) _)
        have hstep2 : sumN n (fun q => (if j = q then c else 0) * v q) = c * v j := by
          have hc : sumN n (fun q => (if j = q then c else 0) * v q) =
              sumN n (fun q => basisVec j q * (c * v q)) := by
            apply sumN_congr; intro q _; unfold basisVec
            if h : q = j then
              subst h; rw [ite_eq_left_iff.mpr (fun h0 => absurd rfl h0), ite_eq_left_iff.mpr (fun h0 => absurd rfl h0), Int.one_mul]
            else
              have h' : j ≠ q := fun h0 => h h0.symm
              rw [ite_eq_right_iff.mpr (fun h0 => absurd h0 h'), ite_eq_right_iff.mpr (fun h0 => absurd h0 h), Int.zero_mul, Int.zero_mul]
          rw [hc, sumN_kronecker_left n j (fun q => c * v q) hj]
        rw [hstep1, ← hstep2, ← sumN_add]
        exact sumN_congr n _ _ (fun q _ => (Int.add_mul _ _ _).symm)
      rw [hadj, dotN_comm]
      have htot : dotN n v (matVec n (darbouxL1 m n A c) v) =
          dotN n v (matVecRect n m (transposeMat A) (matVecRect m n A v)) + c * normSqN n v := by
        unfold normSqN; unfold dotN
        rw [← sumN_mul_left n c, ← sumN_add]
        apply sumN_congr; intro j hj
        rw [← hAtA j hj, Int.mul_add, ← Int.mul_assoc (v j) c (v j), Int.mul_comm (v j) c, Int.mul_assoc c]
      omega
    rw [hnorm]
    have hlam : dotN n v (matVec n (darbouxL1 m n A c) v) = lam * normSqN n v := by
      unfold normSqN; unfold dotN
      rw [← sumN_mul_left n lam]
      apply sumN_congr; intro j hj
      rw [heig j hj, ← Int.mul_assoc (v j) lam (v j), Int.mul_comm (v j) lam, Int.mul_assoc lam]
    rw [hlam, Int.sub_mul]

/-- Theorem 30 (Portal 5 — Dark-Mode Kernel Collision, Eigenvalue c, and Row-Space Orthogonality):
    For any k in ker(A) (A k = 0) in arbitrary dimensions (m, n):
    1. Exact collision: A (x + k) = A x for every x,
    2. Dark eigenvalue: L_1 k = c * k,
    3. Exact orthogonality to row space Im(A^T): <A^T y, k> = 0 for every y. -/
theorem p5_dark_mode_kernel_collision_and_orthogonality (m n : Nat) (A : Nat → Nat → Int)
    (c : Int) (k : Nat → Int) (hker : ∀ i, i < m → matVecRect m n A k i = 0) :
    (∀ x i, i < m → matVecRect m n A (fun j => x j + k j) i = matVecRect m n A x i) ∧
    (∀ j, j < n → matVec n (darbouxL1 m n A c) k j = c * k j) ∧
    (∀ y, dotN n (matVecRect n m (transposeMat A) y) k = 0) := by
  refine ⟨?_, ?_, ?_⟩
  · intro x i hi
    unfold matVecRect
    calc sumN n (fun j => A i j * (x j + k j))
        = sumN n (fun j => A i j * x j + A i j * k j) := sumN_congr n _ _ (fun j _ => Int.mul_add _ _ _)
      _ = sumN n (fun j => A i j * x j) + matVecRect m n A k i := sumN_add n _ _
      _ = sumN n (fun j => A i j * x j) := by rw [hker i hi]; omega
  · intro j hj
    unfold matVec matVecRect darbouxL1 matMulRect
    have h1 : sumN n (fun q => (sumN m (fun r => transposeMat A j r * A r q) + if j = q then c else 0) * k q) =
        sumN m (fun r => transposeMat A j r * matVecRect m n A k r) +
        sumN n (fun q => (if j = q then c else 0) * k q) := by
      have ha : sumN n (fun q => (sumN m (fun r => transposeMat A j r * A r q) + if j = q then c else 0) * k q) =
          sumN n (fun q => sumN m (fun r => transposeMat A j r * A r q) * k q) +
          sumN n (fun q => (if j = q then c else 0) * k q) := by
        rw [← sumN_add]; exact sumN_congr n _ _ (fun q _ => Int.add_mul _ _ _)
      rw [ha]
      have hb : sumN n (fun q => sumN m (fun r => transposeMat A j r * A r q) * k q) =
          sumN m (fun r => transposeMat A j r * matVecRect m n A k r) := by
        unfold matVecRect
        calc sumN n (fun q => sumN m (fun r => transposeMat A j r * A r q) * k q)
            = sumN n (fun q => sumN m (fun r => (transposeMat A j r * A r q) * k q)) :=
                sumN_congr n _ _ (fun q _ => (sumN_mul_right m (k q) _).symm)
          _ = sumN m (fun r => sumN n (fun q => (transposeMat A j r * A r q) * k q)) := sumN_comm n m _
          _ = sumN m (fun r => sumN n (fun q => transposeMat A j r * (A r q * k q))) :=
                sumN_congr m _ _ (fun r _ => sumN_congr n _ _ (fun q _ => Int.mul_assoc _ _ _))
          _ = sumN m (fun r => transposeMat A j r * sumN n (fun q => A r q * k q)) :=
                sumN_congr m _ _ (fun r _ => sumN_mul_left n _ _)
      rw [hb]
    have hz : sumN m (fun r => transposeMat A j r * matVecRect m n A k r) = 0 := by
      calc sumN m (fun r => transposeMat A j r * matVecRect m n A k r)
          = sumN m (fun _ => 0) := sumN_congr m _ _ (fun r hr => by rw [hker r hr, Int.mul_zero])
        _ = 0 := sumN_zero m
    have hck : sumN n (fun q => (if j = q then c else 0) * k q) = c * k j := by
      have hc : sumN n (fun q => (if j = q then c else 0) * k q) =
          sumN n (fun q => basisVec j q * (c * k q)) := by
        apply sumN_congr; intro q _; unfold basisVec
        if h : q = j then
          subst h; rw [ite_eq_left_iff.mpr (fun h0 => absurd rfl h0), ite_eq_left_iff.mpr (fun h0 => absurd rfl h0), Int.one_mul]
        else
          have h' : j ≠ q := fun h0 => h h0.symm
          rw [ite_eq_right_iff.mpr (fun h0 => absurd h0 h'), ite_eq_right_iff.mpr (fun h0 => absurd h0 h), Int.zero_mul, Int.zero_mul]
      rw [hc, sumN_kronecker_left n j (fun q => c * k q) hj]
    rw [h1, hz, hck]; omega
  · intro y
    rw [← dotN_matVecRect_adj m n A y k]
    unfold dotN
    calc sumN m (fun i => y i * matVecRect m n A k i)
        = sumN m (fun _ => 0) := sumN_congr m _ _ (fun i hi => by rw [hker i hi, Int.mul_zero])
      _ = 0 := sumN_zero m

/-- Theorem 31 (Portal 5 — Exact Kernel Reconstruction-Loss Lower Bound):
    For any x = A^T y_opt + x_ker with x_ker in ker(A) and ANY reconstruction A^T y in Im(A^T):
    ‖x - A^T y‖^2 = ‖A^T(y_opt - y)‖^2 + ‖x_ker‖^2 >= ‖x_ker‖^2 identically! -/
theorem p5_kernel_reconstruction_loss_lower_bound (m n : Nat) (A : Nat → Nat → Int)
    (yOpt y xKer : Nat → Int) (hker : ∀ i, i < m → matVecRect m n A xKer i = 0) :
    let x := fun j => matVecRect n m (transposeMat A) yOpt j + xKer j
    let xHat := matVecRect n m (transposeMat A) y
    let xDiff := matVecRect n m (transposeMat A) (fun i => yOpt i - y i)
    normSqN n (fun j => x j - xHat j) = normSqN n xDiff + normSqN n xKer ∧
    normSqN n xKer ≤ normSqN n (fun j => x j - xHat j) := by
  let xDiff := matVecRect n m (transposeMat A) (fun i => yOpt i - y i)
  have hsub : ∀ j, matVecRect n m (transposeMat A) yOpt j + xKer j -
      matVecRect n m (transposeMat A) y j = xDiff j + xKer j := by
    intro j
    have hlin : matVecRect n m (transposeMat A) yOpt j - matVecRect n m (transposeMat A) y j = xDiff j := by
      unfold xDiff matVecRect
      rw [← sumN_sub]
      exact sumN_congr m _ _ (fun r _ => (Int.mul_sub _ _ _).symm)
    omega
  have horth : dotN n xDiff xKer = 0 :=
    (p5_dark_mode_kernel_collision_and_orthogonality m n A 0 xKer hker).2.2 (fun i => yOpt i - y i)
  have hpyth : normSqN n (fun j => xDiff j + xKer j) = normSqN n xDiff + normSqN n xKer := by
    unfold normSqN dotN
    calc sumN n (fun j => (xDiff j + xKer j) * (xDiff j + xKer j))
        = sumN n (fun j => (xDiff j * xDiff j + 2 * (xDiff j * xKer j)) + xKer j * xKer j) := by
            apply sumN_congr; intro j _
            simp only [Int.add_mul, Int.mul_add]; rw [Int.mul_comm (xKer j) (xDiff j), Int.two_mul]; omega
      _ = (sumN n (fun j => xDiff j * xDiff j) + 2 * dotN n xDiff xKer) +
          sumN n (fun j => xKer j * xKer j) := by
            rw [sumN_add, sumN_add, sumN_mul_left]; rfl
      _ = sumN n (fun j => xDiff j * xDiff j) + sumN n (fun j => xKer j * xKer j) := by
            rw [horth, Int.mul_zero]; omega
  have heq : normSqN n (fun j => matVecRect n m (transposeMat A) yOpt j + xKer j -
      matVecRect n m (transposeMat A) y j) = normSqN n xDiff + normSqN n xKer := by
    rw [← hpyth]
    unfold normSqN; unfold dotN
    exact sumN_congr n _ _ (fun j _ => by dsimp only; rw [hsub j])
  have hnn : 0 ≤ normSqN n xDiff := sumN_nonneg n _ (fun j _ => int_sq_nonneg _)
  dsimp only
  exact ⟨heq, by omega⟩

def congMat (d : Nat → Int) (L : Nat → Nat → Int) (i j : Nat) : Int :=
  d i * L i j * d j

/-- Theorem 32 (Portal 5 Obstruction O5.2 — Diagonal Congruence Bilinear Sign Identity vs Trace Shift):
    For any diagonal scaling D = diag(d_i) and operator L in ANY dimension n,
    <v, (D L D) v> = <(D v), L (D v)> (exact quadratic-form sign/definiteness preservation
    under congruence), while on L = diag(1, -1) with D = diag(2, 3), the congruence trace
    tr(D L D) = 4*1 + 9*(-1) = -5 != tr(L) = 0 (and one-sided tr(D L) = 2*1 + 3*(-1) = -1 != 0). -/
theorem p5_sylvester_congruence_sign_preservation (n : Nat) (d : Nat → Int)
    (L : Nat → Nat → Int) (v : Nat → Int) :
    (dotN n v (matVec n (congMat d L) v) =
      dotN n (fun i => d i * v i) (matVec n L (fun i => d i * v i))) ∧
    ((1 : Int) + (-1) ≠ (2 * 2) * 1 + (3 * 3) * (-1)) ∧
    ((1 : Int) + (-1) ≠ 2 * 1 + 3 * (-1)) := by
  refine ⟨?_, by omega, by omega⟩
  unfold dotN matVec matVecRect congMat
  apply sumN_congr; intro i _
  calc v i * sumN n (fun j => d i * L i j * d j * v j)
      = sumN n (fun j => v i * (d i * L i j * d j * v j)) := (sumN_mul_left n (v i) _).symm
    _ = sumN n (fun j => (d i * v i) * (L i j * (d j * v j))) := by
          apply sumN_congr; intro j _
          rw [Int.mul_assoc (d i) (L i j) (d j), Int.mul_assoc (d i) (L i j * d j) (v j),
              ← Int.mul_assoc (v i) (d i), Int.mul_comm (v i) (d i),
              Int.mul_assoc (L i j) (d j) (v j)]
    _ = (d i * v i) * sumN n (fun j => L i j * (d j * v j)) := sumN_mul_left n (d i * v i) _

def susyA2 (i j : Nat) : Int :=
  match i, j with
  | 0, 0 => -1 | 0, 1 => 2
  | 1, 1 => -4 | 1, 2 => 2
  | 2, 2 => 2  | 2, 3 => 2
  | 3, 3 => -3 | 3, 4 => 2
  | _, _ => 0

def susyK1 : Nat → Int
  | 0 => -2 | 1 => -1 | 2 => -2 | 3 => 2 | 4 => 3 | _ => 0

def susyK2 : Nat → Int
  | 4 => 1 | _ => 0

/-- Theorem 33 (Portal 5 Obstruction O5.1 — Singular SUSY Distinct Non-Parallel Zero Modes):
    On the 5x5 singular SUSY factor 2*A = -diag(1,4,-2,3,0) + 2*shift,
    k1 = (-2,-1,-2,2,3) lies in ker(A) and k2 = e_5 lies in ker(A^T), yet
    A^T k1 != 0 and A k2 != 0 (isospectrality of A^T A and A A^T does NOT certify losslessness). -/
theorem p5_singular_susy_distinct_zero_modes :
    (∀ i, i < 5 → matVec 5 susyA2 susyK1 i = 0) ∧
    (∀ i, i < 5 → matVec 5 (transposeMat susyA2) susyK2 i = 0) ∧
    (matVec 5 (transposeMat susyA2) susyK1 0 ≠ 0) ∧
    (matVec 5 susyA2 susyK2 3 ≠ 0) := by
  refine ⟨?_, ?_, by unfold matVec matVecRect transposeMat sumN susyA2 susyK1; decide,
                 by unfold matVec matVecRect sumN susyA2 susyK2; decide⟩
  · intro i hi
    unfold matVec matVecRect sumN susyA2 susyK1
    cases i with
    | zero => decide
    | succ i1 => cases i1 with | zero => decide | succ i2 => cases i2 with | zero => decide | succ i3 => cases i3 with | zero => decide | succ i4 => cases i4 with | zero => decide | succ _ => omega
  · intro i hi
    unfold matVec matVecRect transposeMat sumN susyA2 susyK2
    cases i with
    | zero => decide
    | succ i1 => cases i1 with | zero => decide | succ i2 => cases i2 with | zero => decide | succ i3 => cases i3 with | zero => decide | succ i4 => cases i4 with | zero => decide | succ _ => omega

-- Hopf readout h(q) = q i q_bar on Q^4 and right S^1 fiber multiplication q * (a + b i)
def hopfH0 (q0 q1 q2 q3 : Int) : Int := q0 * q0 + q1 * q1 - q2 * q2 - q3 * q3
def hopfH1 (q0 q1 q2 q3 : Int) : Int := 2 * (q1 * q2 + q0 * q3)
def hopfH2 (q0 q1 q2 q3 : Int) : Int := 2 * (q1 * q3 - q0 * q2)

def qMulR0 (q0 q1 a b : Int) : Int := q0 * a - q1 * b
def qMulR1 (q0 q1 a b : Int) : Int := q0 * b + q1 * a
def qMulR2 (q2 q3 a b : Int) : Int := q2 * a + q3 * b
def qMulR3 (q2 q3 a b : Int) : Int := q3 * a - q2 * b

/-- Theorem 34 (Portal 5 Obstruction O5.3 — Exact 1D Hopf S^1 Dark Fiber Invariance):
    Universally for ALL q = (q0, q1, q2, q3) and ANY Pythagorean S^1 fiber phase
    a^2 + b^2 = D^2, right multiplication q*(a + b*i) scales all three Hopf S^2 readout
    coordinates h(q) = q i q_bar identically by D^2 (any S^3 -> S^2 readout is blind
    to the S^1 fiber phase). -/
theorem p5_hopf_dark_fiber_phase_invariance (q0 q1 q2 q3 a b D : Int)
    (hpyth : a * a + b * b = D * D) :
    hopfH0 (qMulR0 q0 q1 a b) (qMulR1 q0 q1 a b) (qMulR2 q2 q3 a b) (qMulR3 q2 q3 a b) =
      D * D * hopfH0 q0 q1 q2 q3 ∧
    hopfH1 (qMulR0 q0 q1 a b) (qMulR1 q0 q1 a b) (qMulR2 q2 q3 a b) (qMulR3 q2 q3 a b) =
      D * D * hopfH1 q0 q1 q2 q3 ∧
    hopfH2 (qMulR0 q0 q1 a b) (qMulR1 q0 q1 a b) (qMulR2 q2 q3 a b) (qMulR3 q2 q3 a b) =
      D * D * hopfH2 q0 q1 q2 q3 := by
  have cr : ∀ p q r s : Int, (p * r) * (q * s) = (r * s) * (p * q) := by
    intro p q r s
    rw [Int.mul_assoc p r (q * s), ← Int.mul_assoc r q s, Int.mul_comm r q,
        Int.mul_assoc q r s, ← Int.mul_assoc p q (r * s), Int.mul_comm (p * q) (r * s)]
  have brah : ∀ x y : Int, (x * a - y * b) * (x * a - y * b) + (x * b + y * a) * (x * b + y * a) =
      (a * a + b * b) * (x * x + y * y) := by
    intro x y
    simp only [Int.sub_mul, Int.mul_sub, Int.add_mul, Int.mul_add]
    rw [cr x x a a, cr y y b b, cr x x b b, cr y y a a,
        cr x y a b, cr y x b a, cr x y b a, cr y x a b,
        Int.mul_comm b a, Int.mul_comm y x]
    omega
  refine ⟨?_, ?_, ?_⟩
  · unfold hopfH0 qMulR0 qMulR1 qMulR2 qMulR3
    have h1 := brah q0 q1
    have h2 : (q2 * a + q3 * b) * (q2 * a + q3 * b) + (q3 * a - q2 * b) * (q3 * a - q2 * b) =
        (a * a + b * b) * (q2 * q2 + q3 * q3) := by
      have hb := brah q3 q2
      rw [Int.add_comm ((q3 * a - q2 * b) * (q3 * a - q2 * b)),
          Int.add_comm (q3 * b) (q2 * a), Int.add_comm (q3 * q3) (q2 * q2)] at hb
      exact hb
    rw [← hpyth]
    have hsplit : ∀ u1 u2 u3 u4 : Int, u1 + u2 - u3 - u4 = (u1 + u2) - (u3 + u4) := by
      intro u1 u2 u3 u4; omega
    rw [hsplit, h1, h2, ← Int.mul_sub, hsplit]
  · unfold hopfH1 qMulR0 qMulR1 qMulR2 qMulR3
    rw [← hpyth]
    have hmid :
        (q0 * b + q1 * a) * (q2 * a + q3 * b) + (q0 * a - q1 * b) * (q3 * a - q2 * b) =
        (a * a + b * b) * (q1 * q2 + q0 * q3) := by
      simp only [Int.add_mul, Int.mul_add, Int.sub_mul, Int.mul_sub]
      rw [cr q0 q2 b a, cr q0 q3 b b, cr q1 q2 a a, cr q1 q3 a b,
          cr q0 q3 a a, cr q0 q2 a b, cr q1 q3 b a, cr q1 q2 b b,
          Int.mul_comm b a]
      omega
    rw [hmid, ← Int.mul_assoc 2, Int.mul_comm 2 (a * a + b * b), Int.mul_assoc]
  · unfold hopfH2 qMulR0 qMulR1 qMulR2 qMulR3
    rw [← hpyth]
    have hmid :
        (q0 * b + q1 * a) * (q3 * a - q2 * b) - (q0 * a - q1 * b) * (q2 * a + q3 * b) =
        (a * a + b * b) * (q1 * q3 - q0 * q2) := by
      simp only [Int.add_mul, Int.mul_add, Int.sub_mul, Int.mul_sub]
      rw [cr q0 q3 b a, cr q0 q2 b b, cr q1 q3 a a, cr q1 q2 a b,
          cr q0 q2 a a, cr q0 q3 a b, cr q1 q2 b a, cr q1 q3 b b,
          Int.mul_comm b a]
      omega
    rw [hmid, ← Int.mul_assoc 2, Int.mul_comm 2 (a * a + b * b), Int.mul_assoc]

end NaturalSystemsConservation

#print axioms NaturalSystemsConservation.p1_mult_crow_invariance
#print axioms NaturalSystemsConservation.p1_subtractive_bingham_crow_breach_and_nonadd
#print axioms NaturalSystemsConservation.p1_blockh4_isotropic_commutes_anisotropic_breaches
#print axioms NaturalSystemsConservation.p1_isotropic_dark_mode_commutation
#print axioms NaturalSystemsConservation.p1_anisotropic_input_shatters_nullspace
#print axioms NaturalSystemsConservation.p1_mult_safety_margin_crossing_and_cos_repair
#print axioms NaturalSystemsConservation.p1_lif_lyapunov_universal_2step_lasalle
#print axioms NaturalSystemsConservation.p2_equal_diffusion_turing_impossible
#print axioms NaturalSystemsConservation.p2_turing_trace_stays_negative
#print axioms NaturalSystemsConservation.p2_turing_instability_necessity
#print axioms NaturalSystemsConservation.p2_mode_factorization_identity
#print axioms NaturalSystemsConservation.p2_witness_band_exact_factorization
#print axioms NaturalSystemsConservation.p2_complete_graph_all_or_none_spectrum
#print axioms NaturalSystemsConservation.p3_commutator_sym_of_sym_skew
#print axioms NaturalSystemsConservation.p3_helicity_conservation_of_commuting
#print axioms NaturalSystemsConservation.p3_helicity_conservation_iff_commuting
#print axioms NaturalSystemsConservation.p3_cayley_preserves_energy_and_helicity
#print axioms NaturalSystemsConservation.p3_cayley_preserves_all_moments
#print axioms NaturalSystemsConservation.p3_parity_flips_helicity
#print axioms NaturalSystemsConservation.p3_symmetric_residual_rayleigh_increase
#print axioms NaturalSystemsConservation.p4_plato_murray_trifurcation
#print axioms NaturalSystemsConservation.p4_murray_general_sos_optimality
#print axioms NaturalSystemsConservation.p4_thomson_dirichlet_minimum_power
#print axioms NaturalSystemsConservation.p4_physarum_gamma1_global_ratio_increase
#print axioms NaturalSystemsConservation.p4_physarum_gamma2_separatrix_lockin
#print axioms NaturalSystemsConservation.p4_rayleigh_vs_braess_separation
#print axioms NaturalSystemsConservation.p4_physarum_tree_portal_b_density_chasm
#print axioms NaturalSystemsConservation.p5_darboux_intertwining
#print axioms NaturalSystemsConservation.p5_darboux_eigenvector_transport_and_norm
#print axioms NaturalSystemsConservation.p5_dark_mode_kernel_collision_and_orthogonality
#print axioms NaturalSystemsConservation.p5_kernel_reconstruction_loss_lower_bound
#print axioms NaturalSystemsConservation.p5_sylvester_congruence_sign_preservation
#print axioms NaturalSystemsConservation.p5_singular_susy_distinct_zero_modes
#print axioms NaturalSystemsConservation.p5_hopf_dark_fiber_phase_invariance
