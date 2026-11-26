-- Track S110 Stage 3 (H10c) — Pure-Init Lean 4.36.0 Exact Conservation & Weft-Safety Certificate
-- Zero external imports, zero Mathlib, zero sorry, zero Classical.choice.
-- Formalizes per-factor exact finite-dimensional conservation laws & Law-5 obstructions over Nat/Int
-- grounding PREREG-S110, PREREG-S110-AMENDMENT1, and PREREG-S111 (Weft-Geosphere / Weft-Smith).

namespace GeosphereWeftConservation

-- ============================================================================
-- 0. Constructive Finite-Dimensional Vector & Matrix Algebra over Int
-- ============================================================================

def sumN : Nat → (Nat → Int) → Int
  | 0, _ => 0
  | n + 1, f => sumN n f + f n

def dotN (n : Nat) (u v : Nat → Int) : Int :=
  sumN n (fun i => u i * v i)

def normSqN (n : Nat) (u : Nat → Int) : Int :=
  dotN n u u

def matVec (n : Nat) (A : Nat → Nat → Int) (x : Nat → Int) (i : Nat) : Int :=
  sumN n (fun j => A i j * x j)

def IsSkew (n : Nat) (Ω : Nat → Nat → Int) : Prop :=
  ∀ i j, i < n → j < n → Ω i j = -(Ω j i)

def rank2Skew (u v : Nat → Int) (i j : Nat) : Int :=
  u i * v j - v i * u j

-- Auxiliary constructive lemmas (pure Init, zero Classical.choice)

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

private theorem sumN_congr (n : Nat) (f g : Nat → Int)
    (h : ∀ i, i < n → f i = g i) : sumN n f = sumN n g := by
  induction n with
  | zero => rfl
  | succ k ih =>
    simp only [sumN]
    have h1 : sumN k f = sumN k g := ih (fun i hi => h i (Nat.lt_succ_of_lt hi))
    have h2 : f k = g k := h k (Nat.lt_succ_self k)
    omega

private theorem sumN_zero (n : Nat) : sumN n (fun _ => 0) = 0 := by
  induction n with
  | zero => rfl
  | succ k ih =>
    simp only [sumN]
    omega

private theorem sumN_add (n : Nat) (f g : Nat → Int) :
    sumN n (fun i => f i + g i) = sumN n f + sumN n g := by
  induction n with
  | zero => rfl
  | succ k ih =>
    simp only [sumN]
    omega

private theorem sumN_sub (n : Nat) (f g : Nat → Int) :
    sumN n (fun i => f i - g i) = sumN n f - sumN n g := by
  induction n with
  | zero => rfl
  | succ k ih =>
    simp only [sumN]
    omega

private theorem sumN_neg (n : Nat) (f : Nat → Int) :
    sumN n (fun i => -(f i)) = -(sumN n f) := by
  induction n with
  | zero => rfl
  | succ k ih =>
    simp only [sumN]
    omega

private theorem sumN_mul_left (n : Nat) (c : Int) (f : Nat → Int) :
    sumN n (fun i => c * f i) = c * sumN n f := by
  induction n with
  | zero =>
    simp only [sumN, Int.mul_zero]
  | succ k ih =>
    simp only [sumN]
    rw [ih, Int.mul_add]

private theorem sumN_mul_right (n : Nat) (c : Int) (f : Nat → Int) :
    sumN n (fun i => f i * c) = sumN n f * c := by
  induction n with
  | zero =>
    simp only [sumN, Int.zero_mul]
  | succ k ih =>
    simp only [sumN]
    rw [ih, Int.add_mul]

private theorem sumN_comm (m n : Nat) (f : Nat → Nat → Int) :
    sumN m (fun i => sumN n (fun j => f i j)) =
    sumN n (fun j => sumN m (fun i => f i j)) := by
  induction m with
  | zero =>
    simp only [sumN]
    exact (sumN_zero n).symm
  | succ k ih =>
    simp only [sumN]
    rw [ih, ← sumN_add]

private theorem sumN_nonneg (n : Nat) (f : Nat → Int)
    (h : ∀ i, i < n → 0 ≤ f i) : 0 ≤ sumN n f := by
  induction n with
  | zero => exact Int.le_refl 0
  | succ k ih =>
    simp only [sumN]
    have h1 : 0 ≤ sumN k f := ih (fun i hi => h i (Nat.lt_succ_of_lt hi))
    have h2 : 0 ≤ f k := h k (Nat.lt_succ_self k)
    omega

private theorem sumN_le (n : Nat) (f g : Nat → Int)
    (h : ∀ i, i < n → f i ≤ g i) : sumN n f ≤ sumN n g := by
  induction n with
  | zero => exact Int.le_refl 0
  | succ k ih =>
    simp only [sumN]
    have h1 : sumN k f ≤ sumN k g := ih (fun i hi => h i (Nat.lt_succ_of_lt hi))
    have h2 : f k ≤ g k := h k (Nat.lt_succ_self k)
    omega

private theorem sumN_const (n : Nat) (c : Int) :
    sumN n (fun _ => c) = Int.ofNat n * c := by
  induction n with
  | zero =>
    show (0 : Int) = (0 : Int) * c
    rw [Int.zero_mul]
  | succ k ih =>
    simp only [sumN]
    rw [ih]
    have hs : Int.ofNat (k + 1) = Int.ofNat k + 1 := rfl
    rw [hs, Int.add_mul, Int.one_mul]

private theorem sumN_eq_zero_of_nonneg (n : Nat) (f : Nat → Int)
    (hnn : ∀ i, i < n → 0 ≤ f i) (hsum : sumN n f = 0) :
    ∀ i, i < n → f i = 0 := by
  induction n with
  | zero =>
    intro i hi
    omega
  | succ k ih =>
    simp only [sumN] at hsum
    have hsk : 0 ≤ sumN k f := sumN_nonneg k f (fun i hi => hnn i (Nat.lt_succ_of_lt hi))
    have hfk : 0 ≤ f k := hnn k (Nat.lt_succ_self k)
    have hsk0 : sumN k f = 0 := by omega
    have hfk0 : f k = 0 := by omega
    intro i hi
    if hlt : i < k then
      exact ih (fun j hj => hnn j (Nat.lt_succ_of_lt hj)) hsk0 i hlt
    else
      have heq : i = k := by omega
      rw [heq]
      exact hfk0

private theorem normSqN_nonneg (n : Nat) (u : Nat → Int) : 0 ≤ normSqN n u :=
  sumN_nonneg n (fun i => u i * u i) (fun i _ => int_sq_nonneg (u i))

private theorem int_mul_cancel_left_nz (s a b : Int) (hs : s ≠ 0) (heq : s * a = s * b) :
    a = b := by
  have h0 : s * (a - b) = 0 := by
    rw [Int.mul_sub]
    omega
  have hdisj := Int.mul_eq_zero.mp h0
  cases hdisj with
  | inl h => exact absurd h hs
  | inr h => omega

-- ============================================================================
-- PILLAR 1: Workless Core Geodynamo Lorentz Isometry & Exact Rational Cayley
-- ============================================================================

/-- Theorem 1: Every diagonal entry of a skew-symmetric matrix vanishes identically. -/
theorem skew_diag_zero (n : Nat) (Ω : Nat → Nat → Int)
    (hskew : IsSkew n Ω) (i : Nat) (hi : i < n) : Ω i i = 0 := by
  have h := hskew i i hi hi
  omega

/-- Theorem 2: Workless Core Geodynamo Lorentz Law in arbitrary dimension n:
    every skew-symmetric operator performs identically zero radial work. -/
theorem geodynamo_lorentz_workless (n : Nat) (Ω : Nat → Nat → Int) (h : Nat → Int)
    (hskew : IsSkew n Ω) : dotN n h (matVec n Ω h) = 0 := by
  have h1 : dotN n h (matVec n Ω h) =
      sumN n (fun i => sumN n (fun j => h i * (Ω i j * h j))) := by
    unfold dotN matVec
    exact sumN_congr n _ _ (fun i _ => (sumN_mul_left n (h i) (fun j => Ω i j * h j)).symm)
  have h2 : sumN n (fun i => sumN n (fun j => h i * (Ω i j * h j))) =
      -(sumN n (fun i => sumN n (fun j => h i * (Ω i j * h j)))) := by
    calc sumN n (fun i => sumN n (fun j => h i * (Ω i j * h j)))
        = sumN n (fun j => sumN n (fun i => h i * (Ω i j * h j))) := sumN_comm n n _
      _ = sumN n (fun j => sumN n (fun i => -(h j * (Ω j i * h i)))) := by
            apply sumN_congr
            intro j hj
            apply sumN_congr
            intro i hi
            rw [hskew i j hi hj]
            rw [Int.neg_mul, Int.mul_neg]
            have hr : h i * (Ω j i * h j) = h j * (Ω j i * h i) := by
              rw [← Int.mul_assoc, Int.mul_comm (h i) (Ω j i), Int.mul_assoc,
                  Int.mul_comm (h i) (h j), ← Int.mul_assoc, Int.mul_comm (Ω j i) (h j),
                  Int.mul_assoc]
            rw [hr]
      _ = sumN n (fun j => -(sumN n (fun i => h j * (Ω j i * h i)))) := by
            apply sumN_congr
            intro j _
            exact sumN_neg n _
      _ = -(sumN n (fun j => sumN n (fun i => h j * (Ω j i * h i)))) := sumN_neg n _
  omega

/-- Theorem 3: Arbitrary-dimension scaled Cayley transport equation
    (s I + Ω) y = (s I - Ω) x preserves s * ‖·‖^2 identically. -/
theorem geodynamo_cayley_isometry_scaled (n : Nat) (Ω : Nat → Nat → Int)
    (s : Int) (x y : Nat → Int) (hskew : IsSkew n Ω)
    (hcay : ∀ i, i < n → s * y i + matVec n Ω y i = s * x i - matVec n Ω x i) :
    s * normSqN n y = s * normSqN n x := by
  let u : Nat → Int := fun i => y i + x i
  have hwork : dotN n u (matVec n Ω u) = 0 := geodynamo_lorentz_workless n Ω u hskew
  have hstep : ∀ i, i < n → matVec n Ω u i = -(s * (y i - x i)) := by
    intro i hi
    have hlin : matVec n Ω u i = matVec n Ω y i + matVec n Ω x i := by
      unfold matVec
      rw [← sumN_add]
      apply sumN_congr
      intro j _
      exact Int.mul_add (Ω i j) (y j) (x j)
    have hci := hcay i hi
    rw [Int.mul_sub]
    omega
  have hdot : dotN n u (matVec n Ω u) = -(s * (normSqN n y - normSqN n x)) := by
    calc dotN n u (matVec n Ω u)
        = sumN n (fun i => u i * (-(s * (y i - x i)))) := by
            unfold dotN
            exact sumN_congr n _ _ (fun i hi => by rw [hstep i hi])
      _ = sumN n (fun i => -(s * (y i * y i - x i * x i))) := by
            apply sumN_congr
            intro i _
            rw [Int.mul_neg]
            have hdiff : (y i + x i) * (s * (y i - x i)) = s * (y i * y i - x i * x i) := by
              rw [← Int.mul_assoc, Int.mul_comm (y i + x i) s, Int.mul_assoc]
              have hsq : (y i + x i) * (y i - x i) = y i * y i - x i * x i := by
                rw [Int.add_mul, Int.mul_sub, Int.mul_sub, Int.mul_comm (x i) (y i)]
                omega
              rw [hsq]
            rw [hdiff]
      _ = -(sumN n (fun i => s * (y i * y i - x i * x i))) := sumN_neg n _
      _ = -(s * sumN n (fun i => y i * y i - x i * x i)) := by rw [sumN_mul_left]
      _ = -(s * (normSqN n y - normSqN n x)) := by
            unfold normSqN dotN
            rw [sumN_sub]
  have hs0 : s * (normSqN n y - normSqN n x) = 0 := by omega
  rw [Int.mul_sub] at hs0
  omega

/-- Theorem 4: Universal exact rational Cayley isometry in arbitrary dimension n
    for every non-zero scale s and skew-symmetric Ω. -/
theorem geodynamo_cayley_isometry (n : Nat) (Ω : Nat → Nat → Int)
    (s : Int) (x y : Nat → Int) (hskew : IsSkew n Ω) (hs : s ≠ 0)
    (hcay : ∀ i, i < n → s * y i + matVec n Ω y i = s * x i - matVec n Ω x i) :
    normSqN n y = normSqN n x :=
  int_mul_cancel_left_nz s (normSqN n y) (normSqN n x) hs
    (geodynamo_cayley_isometry_scaled n Ω s x y hskew hcay)

/-- Theorem 5: Rank-2 skew-symmetric generator Ω = u v^T - v u^T is skew-symmetric
    in every dimension n (O(d) Woodbury-friendly skew generator). -/
theorem rank2_skew_is_skew (n : Nat) (u v : Nat → Int) : IsSkew n (rank2Skew u v) := by
  intro i j _ _
  unfold rank2Skew
  rw [Int.mul_comm (u i) (v j), Int.mul_comm (v i) (u j)]
  omega

def cayley2Num0 (w x0 x1 : Int) : Int := (1 - w * w) * x0 - 2 * w * x1
def cayley2Num1 (w x0 x1 : Int) : Int := 2 * w * x0 + (1 - w * w) * x1

/-- Theorem 6: Explicit closed-form 2x2 block-diagonal Cayley SO(2) rational isometry
    (4 FMAs per pair, zero matrix inversion, strictly positive denominator 1 + w^2 >= 1). -/
theorem cayley2_exact_isometry (w x0 x1 : Int) :
    1 ≤ 1 + w * w ∧
    cayley2Num0 w x0 x1 * cayley2Num0 w x0 x1 + cayley2Num1 w x0 x1 * cayley2Num1 w x0 x1 =
    (1 + w * w) * (1 + w * w) * (x0 * x0 + x1 * x1) := by
  constructor
  · have h := int_sq_nonneg w
    omega
  · unfold cayley2Num0 cayley2Num1
    have h1 :
        ((1 - w * w) * x0 - 2 * w * x1) * ((1 - w * w) * x0 - 2 * w * x1) +
        (2 * w * x0 + (1 - w * w) * x1) * (2 * w * x0 + (1 - w * w) * x1) =
        ((1 - w * w) * (1 - w * w) + (2 * w) * (2 * w)) * (x0 * x0 + x1 * x1) := by
      have ha : ∀ A B : Int, (A * x0 - B * x1) * (A * x0 - B * x1) +
          (B * x0 + A * x1) * (B * x0 + A * x1) = (A * A + B * B) * (x0 * x0 + x1 * x1) := by
        intro A B
        simp only [Int.sub_mul, Int.mul_sub, Int.add_mul, Int.mul_add]
        have p1 : A * x0 * (A * x0) = A * A * (x0 * x0) := by
          rw [Int.mul_assoc A x0 (A * x0), ← Int.mul_assoc x0 A x0, Int.mul_comm x0 A,
              Int.mul_assoc A x0 x0, ← Int.mul_assoc A A (x0 * x0)]
        have p2 : B * x1 * (B * x1) = B * B * (x1 * x1) := by
          rw [Int.mul_assoc B x1 (B * x1), ← Int.mul_assoc x1 B x1, Int.mul_comm x1 B,
              Int.mul_assoc B x1 x1, ← Int.mul_assoc B B (x1 * x1)]
        have p3 : B * x0 * (B * x0) = B * B * (x0 * x0) := by
          rw [Int.mul_assoc B x0 (B * x0), ← Int.mul_assoc x0 B x0, Int.mul_comm x0 B,
              Int.mul_assoc B x0 x0, ← Int.mul_assoc B B (x0 * x0)]
        have p4 : A * x1 * (A * x1) = A * A * (x1 * x1) := by
          rw [Int.mul_assoc A x1 (A * x1), ← Int.mul_assoc x1 A x1, Int.mul_comm x1 A,
              Int.mul_assoc A x1 x1, ← Int.mul_assoc A A (x1 * x1)]
        have c1 : A * x0 * (B * x1) = B * x0 * (A * x1) := by
          rw [Int.mul_assoc A x0 (B * x1), ← Int.mul_assoc x0 B x1, Int.mul_comm x0 B,
              Int.mul_assoc B x0 x1, ← Int.mul_assoc A B (x0 * x1), Int.mul_comm A B,
              Int.mul_assoc B A (x0 * x1), ← Int.mul_assoc A x0 x1, Int.mul_comm A x0,
              Int.mul_assoc x0 A x1, ← Int.mul_assoc B x0 (A * x1)]
        have c2 : B * x1 * (A * x0) = A * x1 * (B * x0) := by
          rw [Int.mul_comm (B * x1) (A * x0), Int.mul_comm (A * x1) (B * x0)]
          exact c1
        rw [p1, p2, p3, p4, c1, c2]
        omega
      exact ha (1 - w * w) (2 * w)
    have h2 : (1 - w * w) * (1 - w * w) + (2 * w) * (2 * w) = (1 + w * w) * (1 + w * w) := by
      simp only [Int.sub_mul, Int.mul_sub, Int.add_mul, Int.mul_add, Int.one_mul, Int.mul_one]
      have h22 : (2 : Int) * 2 = 4 := rfl
      have h4 : 2 * w * (2 * w) = 4 * (w * w) := by
        rw [Int.mul_assoc 2 w (2 * w), ← Int.mul_assoc w 2 w, Int.mul_comm w 2,
            Int.mul_assoc 2 w w, ← Int.mul_assoc 2 2 (w * w), h22]
      rw [h4]
      omega
    rw [h1, h2]

/-- Theorem 7: Universal strict invertibility of (I_4 + Ω) for EVERY 4x4 skew-symmetric
    matrix Ω over Z via Pfaffian expansion:
    det(I_4 + Ω) = 1 + (a^2+b^2+c^2+d^2+e^2+f^2) + (af - be + cd)^2 >= 1. -/
theorem det4_I_plus_skew_pos (a b c d e f : Int) :
    1 ≤ 1 + (a * a + b * b + c * c + d * d + e * e + f * f) +
        (a * f - b * e + c * d) * (a * f - b * e + c * d) := by
  have ha := int_sq_nonneg a
  have hb := int_sq_nonneg b
  have hc := int_sq_nonneg c
  have hd := int_sq_nonneg d
  have he := int_sq_nonneg e
  have hf := int_sq_nonneg f
  have hp := int_sq_nonneg (a * f - b * e + c * d)
  omega

def cayley4QDen (b c d : Int) : Int := 1 + b * b + c * c + d * d
def cayley4Q0 (b c d x0 x1 x2 x3 : Int) : Int :=
  (1 - b * b - c * c - d * d) * x0 + 2 * (b * x1 + c * x2 + d * x3)
def cayley4Q1 (b c d x0 x1 x2 x3 : Int) : Int :=
  (1 - b * b - c * c - d * d) * x1 + 2 * (-(b * x0) + d * x2 - c * x3)
def cayley4Q2 (b c d x0 x1 x2 x3 : Int) : Int :=
  (1 - b * b - c * c - d * d) * x2 + 2 * (-(c * x0) - d * x1 + b * x3)
def cayley4Q3 (b c d x0 x1 x2 x3 : Int) : Int :=
  (1 - b * b - c * c - d * d) * x3 + 2 * (-(d * x0) + c * x1 - b * x2)

private theorem quat_cayley_sq_helper (k b c d x0 x1 x2 x3 : Int) :
    (k * x0 + 2 * (b * x1 + c * x2 + d * x3)) * (k * x0 + 2 * (b * x1 + c * x2 + d * x3)) +
    (k * x1 + 2 * (-(b * x0) + d * x2 - c * x3)) * (k * x1 + 2 * (-(b * x0) + d * x2 - c * x3)) +
    (k * x2 + 2 * (-(c * x0) - d * x1 + b * x3)) * (k * x2 + 2 * (-(c * x0) - d * x1 + b * x3)) +
    (k * x3 + 2 * (-(d * x0) + c * x1 - b * x2)) * (k * x3 + 2 * (-(d * x0) + c * x1 - b * x2)) =
    (k * k + 4 * (b * b + c * c + d * d)) * (x0 * x0 + x1 * x1 + x2 * x2 + x3 * x3) := by
  let v0 := b * x1 + c * x2 + d * x3
  let v1 := -(b * x0) + d * x2 - c * x3
  let v2 := -(c * x0) - d * x1 + b * x3
  let v3 := -(d * x0) + c * x1 - b * x2
  have hxv : x0 * v0 + x1 * v1 + x2 * v2 + x3 * v3 = 0 := by
    simp only [v0, v1, v2, v3, Int.mul_add, Int.mul_sub, Int.mul_neg]
    have t1 : x0 * (b * x1) = x1 * (b * x0) := by
      rw [← Int.mul_assoc, Int.mul_comm x0 b, Int.mul_assoc, Int.mul_comm x0 x1,
          ← Int.mul_assoc, Int.mul_comm b x1, Int.mul_assoc]
    have t2 : x0 * (c * x2) = x2 * (c * x0) := by
      rw [← Int.mul_assoc, Int.mul_comm x0 c, Int.mul_assoc, Int.mul_comm x0 x2,
          ← Int.mul_assoc, Int.mul_comm c x2, Int.mul_assoc]
    have t3 : x0 * (d * x3) = x3 * (d * x0) := by
      rw [← Int.mul_assoc, Int.mul_comm x0 d, Int.mul_assoc, Int.mul_comm x0 x3,
          ← Int.mul_assoc, Int.mul_comm d x3, Int.mul_assoc]
    have t4 : x1 * (d * x2) = x2 * (d * x1) := by
      rw [← Int.mul_assoc, Int.mul_comm x1 d, Int.mul_assoc, Int.mul_comm x1 x2,
          ← Int.mul_assoc, Int.mul_comm d x2, Int.mul_assoc]
    have t5 : x1 * (c * x3) = x3 * (c * x1) := by
      rw [← Int.mul_assoc, Int.mul_comm x1 c, Int.mul_assoc, Int.mul_comm x1 x3,
          ← Int.mul_assoc, Int.mul_comm c x3, Int.mul_assoc]
    have t6 : x2 * (b * x3) = x3 * (b * x2) := by
      rw [← Int.mul_assoc, Int.mul_comm x2 b, Int.mul_assoc, Int.mul_comm x2 x3,
          ← Int.mul_assoc, Int.mul_comm b x3, Int.mul_assoc]
    omega
  have hvv : v0 * v0 + v1 * v1 + v2 * v2 + v3 * v3 =
      (b * b + c * c + d * d) * (x0 * x0 + x1 * x1 + x2 * x2 + x3 * x3) := by
    have sq3 : ∀ p q r : Int, (p + q + r) * (p + q + r) =
        p * p + q * q + r * r + 2 * (p * q) + 2 * (p * r) + 2 * (q * r) := by
      intro p q r
      simp only [Int.add_mul, Int.mul_add]
      rw [Int.mul_comm q p, Int.mul_comm r p, Int.mul_comm r q]
      omega
    have h0 : v0 * v0 = (b * x1) * (b * x1) + (c * x2) * (c * x2) + (d * x3) * (d * x3) +
        2 * ((b * x1) * (c * x2)) + 2 * ((b * x1) * (d * x3)) + 2 * ((c * x2) * (d * x3)) :=
      sq3 (b * x1) (c * x2) (d * x3)
    have hv1eq : v1 = -(b * x0) + d * x2 + -(c * x3) := by simp only [v1]; omega
    have hv2eq : v2 = -(c * x0) + -(d * x1) + b * x3 := by simp only [v2]; omega
    have hv3eq : v3 = -(d * x0) + c * x1 + -(b * x2) := by simp only [v3]; omega
    have h1 : v1 * v1 = (-(b * x0)) * (-(b * x0)) + (d * x2) * (d * x2) + (-(c * x3)) * (-(c * x3)) +
        2 * ((-(b * x0)) * (d * x2)) + 2 * ((-(b * x0)) * (-(c * x3))) + 2 * ((d * x2) * (-(c * x3))) := by
      rw [hv1eq]; exact sq3 _ _ _
    have h2 : v2 * v2 = (-(c * x0)) * (-(c * x0)) + (-(d * x1)) * (-(d * x1)) + (b * x3) * (b * x3) +
        2 * ((-(c * x0)) * (-(d * x1))) + 2 * ((-(c * x0)) * (b * x3)) + 2 * ((-(d * x1)) * (b * x3)) := by
      rw [hv2eq]; exact sq3 _ _ _
    have h3 : v3 * v3 = (-(d * x0)) * (-(d * x0)) + (c * x1) * (c * x1) + (-(b * x2)) * (-(b * x2)) +
        2 * ((-(d * x0)) * (c * x1)) + 2 * ((-(d * x0)) * (-(b * x2))) + 2 * ((c * x1) * (-(b * x2))) := by
      rw [hv3eq]; exact sq3 _ _ _
    have psq : ∀ p q : Int, (p * q) * (p * q) = (p * p) * (q * q) := by
      intro p q
      rw [Int.mul_assoc p q (p * q), ← Int.mul_assoc q p q, Int.mul_comm q p,
          Int.mul_assoc p q q, ← Int.mul_assoc p p (q * q)]
    have cr : ∀ p q r s : Int, (p * r) * (q * s) = (q * r) * (p * s) := by
      intro p q r s
      rw [Int.mul_assoc p r (q * s), ← Int.mul_assoc r q s, Int.mul_comm r q,
          Int.mul_assoc q r s, ← Int.mul_assoc p q (r * s), Int.mul_comm p q,
          Int.mul_assoc q p (r * s), ← Int.mul_assoc p r s, Int.mul_comm p r,
          Int.mul_assoc r p s, ← Int.mul_assoc q r (p * s)]
    rw [h0, h1, h2, h3]
    simp only [Int.neg_mul, Int.mul_neg, Int.neg_neg]
    rw [psq b x1, psq c x2, psq d x3,
        psq b x0, psq d x2, psq c x3,
        psq c x0, psq d x1, psq b x3,
        psq d x0, psq c x1, psq b x2]
    rw [cr b c x1 x2, cr b d x1 x3, cr c d x2 x3, cr b d x0 x2, cr b c x0 x3, cr c d x0 x1]
    simp only [Int.add_mul, Int.mul_add]
    omega
  have hexp : ∀ xi vi : Int, (k * xi + 2 * vi) * (k * xi + 2 * vi) =
      k * k * (xi * xi) + 4 * k * (xi * vi) + 4 * (vi * vi) := by
    intro xi vi
    simp only [Int.add_mul, Int.mul_add]
    have h22 : (2 : Int) * 2 = 4 := rfl
    have e1 : k * xi * (k * xi) = k * k * (xi * xi) := by
      rw [Int.mul_assoc k xi (k * xi), ← Int.mul_assoc xi k xi, Int.mul_comm xi k,
          Int.mul_assoc k xi xi, ← Int.mul_assoc k k (xi * xi)]
    have e2 : k * xi * (2 * vi) = 2 * k * (xi * vi) := by
      rw [Int.mul_assoc k xi (2 * vi), ← Int.mul_assoc xi 2 vi, Int.mul_comm xi 2,
          Int.mul_assoc 2 xi vi, ← Int.mul_assoc k 2 (xi * vi), Int.mul_comm k 2]
    have e3 : 2 * vi * (k * xi) = 2 * k * (xi * vi) := by
      rw [Int.mul_comm (2 * vi) (k * xi)]; exact e2
    have e4 : 2 * vi * (2 * vi) = 4 * (vi * vi) := by
      rw [Int.mul_assoc 2 vi (2 * vi), ← Int.mul_assoc vi 2 vi, Int.mul_comm vi 2,
          Int.mul_assoc 2 vi vi, ← Int.mul_assoc 2 2 (vi * vi), h22]
    have e5 : 2 * k * (xi * vi) + 2 * k * (xi * vi) = 4 * k * (xi * vi) := by
      rw [← Int.add_mul, ← Int.add_mul]
      have : (2 : Int) + 2 = 4 := rfl
      rw [this]
    rw [e1, e2, e3, e4]
    omega
  show (k * x0 + 2 * v0) * (k * x0 + 2 * v0) +
       (k * x1 + 2 * v1) * (k * x1 + 2 * v1) +
       (k * x2 + 2 * v2) * (k * x2 + 2 * v2) +
       (k * x3 + 2 * v3) * (k * x3 + 2 * v3) = _
  rw [hexp x0 v0, hexp x1 v1, hexp x2 v2, hexp x3 v3]
  have hsum :
      (k * k * (x0 * x0) + 4 * k * (x0 * v0) + 4 * (v0 * v0)) +
      (k * k * (x1 * x1) + 4 * k * (x1 * v1) + 4 * (v1 * v1)) +
      (k * k * (x2 * x2) + 4 * k * (x2 * v2) + 4 * (v2 * v2)) +
      (k * k * (x3 * x3) + 4 * k * (x3 * v3) + 4 * (v3 * v3)) =
      k * k * (x0 * x0 + x1 * x1 + x2 * x2 + x3 * x3) +
      4 * k * (x0 * v0 + x1 * v1 + x2 * v2 + x3 * v3) +
      4 * (v0 * v0 + v1 * v1 + v2 * v2 + v3 * v3) := by
    simp only [Int.mul_add]
    omega
  rw [hsum, hxv, Int.mul_zero, hvv, ← Int.mul_assoc 4, Int.add_mul]
  omega

/-- Theorem 8: Explicit dense d = 4 SO(4)/Hopf quaternion Cayley isometry over Z^4
    with strictly positive denominator D = 1 + b^2 + c^2 + d^2 >= 1. -/
theorem cayley4_hopf_quat_isometry (b c d x0 x1 x2 x3 : Int) :
    1 ≤ cayley4QDen b c d ∧
    cayley4Q0 b c d x0 x1 x2 x3 * cayley4Q0 b c d x0 x1 x2 x3 +
    cayley4Q1 b c d x0 x1 x2 x3 * cayley4Q1 b c d x0 x1 x2 x3 +
    cayley4Q2 b c d x0 x1 x2 x3 * cayley4Q2 b c d x0 x1 x2 x3 +
    cayley4Q3 b c d x0 x1 x2 x3 * cayley4Q3 b c d x0 x1 x2 x3 =
    cayley4QDen b c d * cayley4QDen b c d * (x0 * x0 + x1 * x1 + x2 * x2 + x3 * x3) := by
  constructor
  · unfold cayley4QDen
    have hb := int_sq_nonneg b
    have hc := int_sq_nonneg c
    have hd := int_sq_nonneg d
    omega
  · unfold cayley4Q0 cayley4Q1 cayley4Q2 cayley4Q3 cayley4QDen
    rw [quat_cayley_sq_helper (1 - b * b - c * c - d * d) b c d x0 x1 x2 x3]
    have hcoeff :
        (1 - b * b - c * c - d * d) * (1 - b * b - c * c - d * d) +
        4 * (b * b + c * c + d * d) =
        (1 + b * b + c * c + d * d) * (1 + b * b + c * c + d * d) := by
      let s := b * b + c * c + d * d
      have h1 : 1 - b * b - c * c - d * d = 1 - s := by simp only [s]; omega
      have h2 : 1 + b * b + c * c + d * d = 1 + s := by simp only [s]; omega
      rw [h1, h2]
      simp only [Int.sub_mul, Int.mul_sub, Int.add_mul, Int.mul_add, Int.one_mul, Int.mul_one]
      omega
    rw [hcoeff]

-- ============================================================================
-- PILLAR 2: Oceanic Mass Conservation, B1 Causal Obstruction, SO(d)∩B_d, Darcy
-- ============================================================================

/-- Theorem 9: Arbitrary-dimension bidirectional column-stochastic (and doubly-stochastic)
    transport preserves total state mass identically: 1^T (T x) = D * (1^T x). -/
theorem oceanic_column_stochastic_mass_conservation (n : Nat) (D : Int)
    (T : Nat → Nat → Int) (x : Nat → Int)
    (hcol : ∀ j, j < n → sumN n (fun i => T i j) = D) :
    sumN n (matVec n T x) = D * sumN n x := by
  unfold matVec
  calc sumN n (fun i => sumN n (fun j => T i j * x j))
      = sumN n (fun j => sumN n (fun i => T i j * x j)) := sumN_comm n n _
    _ = sumN n (fun j => sumN n (fun i => T i j) * x j) := by
          apply sumN_congr
          intro j _
          exact sumN_mul_right n (x j) (fun i => T i j)
    _ = sumN n (fun j => D * x j) := by
          apply sumN_congr
          intro j hj
          rw [hcol j hj]
    _ = D * sumN n x := sumN_mul_left n D x

/-- Theorem 10 (Law-5 Obstruction B1 / PREREG-S110-AMENDMENT1 Discovery 1):
    Every non-negative lower-triangular (causal) doubly-stochastic matrix of ANY size n
    must equal D * I_n identically! Causal attention cannot be doubly-stochastic without
    collapsing to attend-to-self or leaking future tokens. -/
theorem causal_doubly_stochastic_is_identity (n : Nat) (D : Int) (T : Nat → Nat → Int)
    (hnn : ∀ i j, i < n → j < n → 0 ≤ T i j)
    (hlt : ∀ i j, i < n → j < n → i < j → T i j = 0)
    (hrow : ∀ i, i < n → sumN n (fun j => T i j) = D)
    (hcol : ∀ j, j < n → sumN n (fun i => T i j) = D) :
    ∀ i j, i < n → j < n → T i j = if i = j then D else 0 := by
  induction n with
  | zero =>
    intro i _ hi _
    omega
  | succ k ih =>
    have hcolk := hcol k (Nat.lt_succ_self k)
    simp only [sumN] at hcolk
    have hcolk_top : sumN k (fun i => T i k) = 0 := by
      calc sumN k (fun i => T i k)
          = sumN k (fun _ => 0) :=
              sumN_congr k _ _ (fun i hi => hlt i k (Nat.lt_succ_of_lt hi) (Nat.lt_succ_self k) hi)
        _ = 0 := sumN_zero k
    have hTkk : T k k = D := by omega
    have hrowk := hrow k (Nat.lt_succ_self k)
    simp only [sumN] at hrowk
    have hrowk_left : sumN k (fun j => T k j) = 0 := by omega
    have hTkj : ∀ j, j < k → T k j = 0 :=
      sumN_eq_zero_of_nonneg k (fun j => T k j)
        (fun j hj => hnn k j (Nat.lt_succ_self k) (Nat.lt_succ_of_lt hj)) hrowk_left
    have hsub : ∀ i j, i < k → j < k → T i j = if i = j then D else 0 := by
      apply ih
      · intro i j hi hj
        exact hnn i j (Nat.lt_succ_of_lt hi) (Nat.lt_succ_of_lt hj)
      · intro i j hi hj hij
        exact hlt i j (Nat.lt_succ_of_lt hi) (Nat.lt_succ_of_lt hj) hij
      · intro i hi
        have hr := hrow i (Nat.lt_succ_of_lt hi)
        simp only [sumN] at hr
        have hTik : T i k = 0 := hlt i k (Nat.lt_succ_of_lt hi) (Nat.lt_succ_self k) hi
        omega
      · intro j hj
        have hc := hcol j (Nat.lt_succ_of_lt hj)
        simp only [sumN] at hc
        have hTkj0 : T k j = 0 := hTkj j hj
        omega
    intro i j hi hj
    if hik : i < k then
      if hjk : j < k then
        exact hsub i j hik hjk
      else
        have hjeq : j = k := by omega
        have hne : i ≠ j := by omega
        rw [hjeq, ite_eq_right_iff.mpr (fun h => absurd h (by omega))]
        exact hlt i k (Nat.lt_succ_of_lt hik) (Nat.lt_succ_self k) hik
    else
      have hieq : i = k := by omega
      if hjk : j < k then
        rw [hieq, ite_eq_right_iff.mpr (fun h => absurd h (by omega))]
        exact hTkj j hjk
      else
        have hjeq : j = k := by omega
        rw [hieq, hjeq, ite_eq_left_iff.mpr (fun h => absurd rfl h)]
        exact hTkk

/-- Theorem 11 (Law-5 Obstruction / PREREG-S110-AMENDMENT1 Discovery 2):
    In arbitrary dimension n, every non-negative matrix whose rows have both L1-sum D
    and squared L2-norm D^2 (i.e. O(n) ∩ Birkhoff_n) has ONLY {0, D} entries (permutation
    entries only — zero continuous doubly-stochastic orthogonal mixing on the same axis!). -/
theorem orthogonal_birkhoff_is_permutation_entries (n : Nat) (D : Int) (Q : Nat → Nat → Int)
    (hnn : ∀ i j, i < n → j < n → 0 ≤ Q i j)
    (hrow : ∀ i, i < n → sumN n (fun j => Q i j) = D)
    (hnorm : ∀ i, i < n → normSqN n (fun j => Q i j) = D * D) :
    ∀ i j, i < n → j < n → Q i j = 0 ∨ Q i j = D := by
  intro i j hi hj
  have hleD : ∀ r, r < n → Q i r ≤ D := by
    intro r hr
    have hsplit : sumN n (fun c => Q i c) - Q i r =
        sumN n (fun c => if c = r then 0 else Q i c) := by
      have hpoint : ∀ c, c < n → Q i c = (if c = r then Q i r else 0) + (if c = r then 0 else Q i c) := by
        intro c _
        if hcr : c = r then
          rw [hcr, ite_eq_left_iff.mpr (fun h => absurd rfl h), ite_eq_left_iff.mpr (fun h => absurd rfl h)]
          omega
        else
          rw [ite_eq_right_iff.mpr (fun h => absurd h hcr), ite_eq_right_iff.mpr (fun h => absurd h hcr)]
          omega
      have hkronecker : ∀ m, r < m → sumN m (fun c => if c = r then Q i r else 0) = Q i r := by
        intro m
        induction m with
        | zero => intro h; omega
        | succ t iht =>
          intro hrt
          simp only [sumN]
          if hrt' : r < t then
            have hne : t ≠ r := by omega
            rw [ite_eq_right_iff.mpr (fun h => absurd h hne), iht hrt']
            omega
          else
            have heq : t = r := by omega
            rw [heq, ite_eq_left_iff.mpr (fun h => absurd rfl h)]
            have hz : sumN r (fun c => if c = r then Q i r else 0) = 0 := by
              calc sumN r (fun c => if c = r then Q i r else 0)
                  = sumN r (fun _ => 0) :=
                      sumN_congr r _ _ (fun c hc => ite_eq_right_iff.mpr (fun h => absurd h (by omega)))
                _ = 0 := sumN_zero r
            rw [hz]
            omega
      have htot : sumN n (fun c => Q i c) =
          sumN n (fun c => if c = r then Q i r else 0) +
          sumN n (fun c => if c = r then 0 else Q i c) := by
        rw [← sumN_add]
        exact sumN_congr n _ _ hpoint
      rw [hkronecker n hr] at htot
      omega
    have hrem : 0 ≤ sumN n (fun c => if c = r then 0 else Q i c) := by
      apply sumN_nonneg
      intro c hc
      if hcr : c = r then
        rw [ite_eq_left_iff.mpr (fun h => absurd hcr h)]
        exact Int.le_refl 0
      else
        rw [ite_eq_right_iff.mpr (fun h => absurd h hcr)]
        exact hnn i c hi hc
    have hri := hrow i hi
    omega
  have hsum0 : sumN n (fun c => Q i c * (D - Q i c)) = 0 := by
    calc sumN n (fun c => Q i c * (D - Q i c))
        = sumN n (fun c => Q i c * D - Q i c * Q i c) :=
            sumN_congr n _ _ (fun c _ => Int.mul_sub (Q i c) D (Q i c))
      _ = sumN n (fun c => Q i c * D) - sumN n (fun c => Q i c * Q i c) := sumN_sub n _ _
      _ = sumN n (fun c => Q i c) * D - normSqN n (fun c => Q i c) := by
            rw [sumN_mul_right]
            rfl
      _ = D * D - D * D := by rw [hrow i hi, hnorm i hi]
      _ = 0 := by omega
  have hprod0 : Q i j * (D - Q i j) = 0 :=
    sumN_eq_zero_of_nonneg n (fun c => Q i c * (D - Q i c))
      (fun c hc => Int.mul_nonneg (hnn i c hi hc) (by have := hleD c hc; omega))
      hsum0 j hj
  cases Int.mul_eq_zero.mp hprod0 with
  | inl h0 => exact Or.inl h0
  | inr hD => exact Or.inr (by omega)

/-- Theorem 12 (Discovery 2 Non-Commutation Witness):
    An explicit d = 2 Cayley rotation Q (w = 1, 90-degree quarter turn) and a doubly-stochastic
    Birkhoff matrix T = (1/4) [[1,3],[3,1]] fail to commute on the same axis (QT != TQ),
    necessitating feature-axis SO(k) vs position-axis separation. -/
theorem so2_birkhoff_non_commutation :
    let q00 : Int := 0; let q01 : Int := -1; let q10 : Int := 1; let q11 : Int := 0
    let t00 : Int := 1; let t01 : Int := 3; let t10 : Int := 3; let t11 : Int := 1
    q00 * t00 + q01 * t10 ≠ t00 * q00 + t01 * q10 ∧
    q10 * t01 + q11 * t11 ≠ t10 * q01 + t11 * q11 := by
  exact ⟨by omega, by omega⟩

/-- Theorem 13: Cleared-denominator Darcy porous aquifer coordinate contraction under
    non-expansive input bound |s| <= B and |K(x)| <= B. -/
theorem darcy_convex_coord_bound (D a s y B : Int)
    (ha0 : 0 ≤ a) (haD : a ≤ D)
    (hsLo : -B ≤ s) (hsHi : s ≤ B)
    (hyLo : -B ≤ y) (hyHi : y ≤ B) :
    -(D * B) ≤ (D - a) * s + a * y ∧ (D - a) * s + a * y ≤ D * B := by
  have hda : 0 ≤ D - a := by omega
  have h1 : (D - a) * (-B) ≤ (D - a) * s := int_mul_le_left_nonneg (D - a) (-B) s hda hsLo
  have h2 : (D - a) * s ≤ (D - a) * B := int_mul_le_left_nonneg (D - a) s B hda hsHi
  have h3 : a * (-B) ≤ a * y := int_mul_le_left_nonneg a (-B) y ha0 hyLo
  have h4 : a * y ≤ a * B := int_mul_le_left_nonneg a y B ha0 hyHi
  have hlo : (D - a) * (-B) + a * (-B) = -(D * B) := by
    rw [← Int.add_mul, Int.mul_neg]
    have : D - a + a = D := by omega
    rw [this]
  have hhi : (D - a) * B + a * B = D * B := by
    rw [← Int.add_mul]
    have : D - a + a = D := by omega
    rw [this]
  exact ⟨by omega, by omega⟩

/-- Theorem 14: Exact arbitrary-dimension Euclidean parallelogram/convexity identity
    for the Darcy porous update s' = (D - a) s + a y over Z^n. -/
theorem darcy_euclidean_parallelogram_identity (n : Nat) (D a : Int) (s y : Nat → Int) :
    normSqN n (fun i => (D - a) * s i + a * y i) +
    a * (D - a) * normSqN n (fun i => s i - y i) =
    D * ((D - a) * normSqN n s + a * normSqN n y) := by
  unfold normSqN dotN
  rw [← sumN_mul_left n (a * (D - a)), ← sumN_add,
      ← sumN_mul_left n (D - a), ← sumN_mul_left n a, ← sumN_add, ← sumN_mul_left n D]
  apply sumN_congr
  intro i _
  have h1d : ∀ p q : Int,
      ((D - a) * p + a * q) * ((D - a) * p + a * q) +
      a * (D - a) * ((p - q) * (p - q)) =
      D * ((D - a) * (p * p) + a * (q * q)) := by
    intro p q
    let b := D - a
    have hD : D = b + a := by simp only [b]; omega
    rw [hD]
    simp only [Int.add_mul, Int.mul_add, Int.sub_mul, Int.mul_sub]
    have e1 : b * p * (b * p) = b * b * (p * p) := by
      rw [Int.mul_assoc b p (b * p), ← Int.mul_assoc p b p, Int.mul_comm p b,
          Int.mul_assoc b p p, ← Int.mul_assoc b b (p * p)]
    have e2 : a * q * (a * q) = a * a * (q * q) := by
      rw [Int.mul_assoc a q (a * q), ← Int.mul_assoc q a q, Int.mul_comm q a,
          Int.mul_assoc a q q, ← Int.mul_assoc a a (q * q)]
    have e3 : b * p * (a * q) = a * b * (p * q) := by
      rw [Int.mul_assoc b p (a * q), ← Int.mul_assoc p a q, Int.mul_comm p a,
          Int.mul_assoc a p q, ← Int.mul_assoc b a (p * q), Int.mul_comm b a]
    have e4 : a * q * (b * p) = a * b * (p * q) := by
      rw [Int.mul_comm (a * q) (b * p)]; exact e3
    have e5 : a * b * (q * p) = a * b * (p * q) := by
      rw [Int.mul_comm q p]
    have e6 : b * (a * (q * q)) = a * b * (q * q) := by
      rw [← Int.mul_assoc b a (q * q), Int.mul_comm b a]
    have e7 : a * (b * (p * p)) = a * b * (p * p) := by
      rw [← Int.mul_assoc a b (p * p)]
    have e8 : b * (b * (p * p)) = b * b * (p * p) := (Int.mul_assoc b b (p * p)).symm
    have e9 : a * (a * (q * q)) = a * a * (q * q) := (Int.mul_assoc a a (q * q)).symm
    rw [e1, e2, e3, e4, e5, e6, e7, e8, e9]
    omega
  exact h1d (s i) (y i)

/-- Theorem 15: Arbitrary-dimension L2 ball invariance of the Darcy porous aquifer update
    under non-expansive input ‖K(x)‖^2 <= R. -/
theorem darcy_l2_ball_invariance (n : Nat) (D a R : Int) (s y : Nat → Int)
    (ha0 : 0 ≤ a) (haD : a ≤ D)
    (hsR : normSqN n s ≤ R) (hyR : normSqN n y ≤ R) :
    normSqN n (fun i => (D - a) * s i + a * y i) ≤ D * D * R := by
  have hid := darcy_euclidean_parallelogram_identity n D a s y
  have hda : 0 ≤ D - a := by omega
  have hD : 0 ≤ D := by omega
  have hdiff : 0 ≤ a * (D - a) * normSqN n (fun i => s i - y i) :=
    Int.mul_nonneg (Int.mul_nonneg ha0 hda) (normSqN_nonneg n _)
  have h1 : (D - a) * normSqN n s ≤ (D - a) * R := int_mul_le_left_nonneg (D - a) _ R hda hsR
  have h2 : a * normSqN n y ≤ a * R := int_mul_le_left_nonneg a _ R ha0 hyR
  have hsum : (D - a) * normSqN n s + a * normSqN n y ≤ D * R := by
    have hDR : (D - a) * R + a * R = D * R := by
      rw [← Int.add_mul]
      have : D - a + a = D := by omega
      rw [this]
    omega
  have hmul : D * ((D - a) * normSqN n s + a * normSqN n y) ≤ D * (D * R) :=
    int_mul_le_left_nonneg D _ (D * R) hD hsum
  rw [← Int.mul_assoc] at hmul
  omega

/-- Theorem 16 (Law-5 Obstruction M1): Omitting the non-expansive hypothesis ‖K_porous‖ <= 1
    allows the Darcy porous aquifer update to escape the prior state bound B. -/
theorem darcy_unbounded_K_obstruction :
    ∃ D a s y B : Int, 0 < a ∧ a < D ∧ -B ≤ s ∧ s ≤ B ∧ D * B < (D - a) * s + a * y := by
  exact ⟨4, 1, 1, 2, 1, by omega, by omega, by omega, by omega, by omega⟩

/-- Theorem 17: Strict diagonal EMA error contraction toward equilibrium for every 0 < a. -/
theorem darcy_step_error_strict_contraction (D a s target : Int)
    (ha0 : 0 < a) (hpos : 0 < s - target) :
    (D - a) * (s - target) < D * (s - target) := by
  rw [Int.sub_mul]
  have hmul : 0 < a * (s - target) := Int.mul_pos ha0 hpos
  omega

-- ============================================================================
-- PILLAR 3: Bingham Viscoplasticity, Vector-Proximal S_Y^H, B5/S50 & Airlock
-- ============================================================================

def reluInt (x : Int) : Int :=
  if 0 ≤ x then x else 0

def bingham (tau u : Int) : Int :=
  reluInt (u - tau) - reluInt (-u - tau)

def clipInt (B u : Int) : Int :=
  if B < u then B else if u < -B then -B else u

def polBingham (D g : Int) (uPol uTor : Nat → Int) (i : Nat) : Int :=
  g * uPol i + D * uTor i

/-- Theorem 18: Exact odd symmetry of the Bingham two-sided ReLU proximal operator. -/
theorem bingham_odd (tau u : Int) : bingham tau (-u) = -(bingham tau u) := by
  unfold bingham reluInt
  if h1 : 0 ≤ -u - tau then
    if h2 : 0 ≤ u - tau then
      have h1' : 0 ≤ - -u - tau := by omega
      rw [ite_eq_left_iff.mpr (fun h => absurd h1 h),
          ite_eq_left_iff.mpr (fun h => absurd h1' h),
          ite_eq_left_iff.mpr (fun h => absurd h2 h)]
      omega
    else
      have h1' : ¬ (0 ≤ - -u - tau) := by omega
      rw [ite_eq_left_iff.mpr (fun h => absurd h1 h),
          ite_eq_right_iff.mpr (fun h => absurd h h1'),
          ite_eq_right_iff.mpr (fun h => absurd h h2)]
      omega
  else
    if h2 : 0 ≤ u - tau then
      have h1' : 0 ≤ - -u - tau := by omega
      rw [ite_eq_right_iff.mpr (fun h => absurd h h1),
          ite_eq_left_iff.mpr (fun h => absurd h1' h),
          ite_eq_left_iff.mpr (fun h => absurd h2 h)]
      omega
    else
      have h1' : ¬ (0 ≤ - -u - tau) := by omega
      rw [ite_eq_right_iff.mpr (fun h => absurd h h1),
          ite_eq_right_iff.mpr (fun h => absurd h h1'),
          ite_eq_right_iff.mpr (fun h => absurd h h2)]
      omega

/-- Theorem 19: Exact sub-yield rigid plug-flow zero-leakage:
    whenever |u| <= tau, Bingham_tau(u) = 0 identically. -/
theorem bingham_sub_yield_plug_zero (tau u : Int)
    (hlo : -tau ≤ u) (hhi : u ≤ tau) : bingham tau u = 0 := by
  unfold bingham reluInt
  if h1 : 0 ≤ u - tau then
    if h2 : 0 ≤ -u - tau then
      rw [ite_eq_left_iff.mpr (fun h => absurd h1 h),
          ite_eq_left_iff.mpr (fun h => absurd h2 h)]
      omega
    else
      rw [ite_eq_left_iff.mpr (fun h => absurd h1 h),
          ite_eq_right_iff.mpr (fun h => absurd h h2)]
      omega
  else
    if h2 : 0 ≤ -u - tau then
      rw [ite_eq_right_iff.mpr (fun h => absurd h h1),
          ite_eq_left_iff.mpr (fun h => absurd h2 h)]
      omega
    else
      rw [ite_eq_right_iff.mpr (fun h => absurd h h1),
          ite_eq_right_iff.mpr (fun h => absurd h h2)]
      omega

private theorem sq_sub_shift (u tau : Int) :
    u * u - (u - tau) * (u - tau) = tau * (2 * u - tau) := by
  simp only [Int.sub_mul, Int.mul_sub]
  have h1 : tau * (2 * u) = u * tau + tau * u := by
    rw [Int.mul_comm u tau, Int.two_mul, Int.mul_add]
  rw [h1]
  omega

private theorem sq_add_shift (u tau : Int) :
    u * u - (u + tau) * (u + tau) = tau * (-(2 * u) - tau) := by
  simp only [Int.add_mul, Int.mul_add, Int.mul_sub, Int.mul_neg]
  have h1 : tau * (2 * u) = u * tau + tau * u := by
    rw [Int.mul_comm u tau, Int.two_mul, Int.mul_add]
  rw [h1]
  omega

/-- Theorem 20: Exact L2 non-expansion of Bingham viscoplastic soft-thresholding. -/
theorem bingham_sq_nonexpansive (tau u : Int) (htau : 0 ≤ tau) :
    bingham tau u * bingham tau u ≤ u * u := by
  unfold bingham reluInt
  if h1 : 0 ≤ u - tau then
    if h2 : 0 ≤ -u - tau then
      have hu : u = 0 := by omega
      have ht : tau = 0 := by omega
      rw [hu, ht]; decide
    else
      rw [ite_eq_left_iff.mpr (fun h => absurd h1 h),
          ite_eq_right_iff.mpr (fun h => absurd h h2)]
      have h0 : u - tau - 0 = u - tau := by omega
      rw [h0]
      have hsub := sq_sub_shift u tau
      have hp : 0 ≤ tau * (2 * u - tau) := Int.mul_nonneg htau (by omega)
      omega
  else
    if h2 : 0 ≤ -u - tau then
      rw [ite_eq_right_iff.mpr (fun h => absurd h h1),
          ite_eq_left_iff.mpr (fun h => absurd h2 h)]
      have h0 : 0 - (-u - tau) = u + tau := by omega
      rw [h0]
      have hsub := sq_add_shift u tau
      have hp : 0 ≤ tau * (-(2 * u) - tau) := Int.mul_nonneg htau (by omega)
      omega
    else
      rw [ite_eq_right_iff.mpr (fun h => absurd h h1),
          ite_eq_right_iff.mpr (fun h => absurd h h2)]
      have hsq := int_sq_nonneg u
      omega

/-- Theorem 21: Strict L2 shrinkage of Bingham soft-thresholding whenever tau > 0 and u != 0. -/
theorem bingham_strict_shrinkage (tau u : Int) (htau : 0 < tau) (hu : u ≠ 0) :
    bingham tau u * bingham tau u < u * u := by
  unfold bingham reluInt
  if h1 : 0 ≤ u - tau then
    if h2 : 0 ≤ -u - tau then
      omega
    else
      rw [ite_eq_left_iff.mpr (fun h => absurd h1 h),
          ite_eq_right_iff.mpr (fun h => absurd h h2)]
      have h0 : u - tau - 0 = u - tau := by omega
      rw [h0]
      have hsub := sq_sub_shift u tau
      have hp : 0 < tau * (2 * u - tau) := Int.mul_pos htau (by omega)
      omega
  else
    if h2 : 0 ≤ -u - tau then
      rw [ite_eq_right_iff.mpr (fun h => absurd h h1),
          ite_eq_left_iff.mpr (fun h => absurd h2 h)]
      have h0 : 0 - (-u - tau) = u + tau := by omega
      rw [h0]
      have hsub := sq_add_shift u tau
      have hp : 0 < tau * (-(2 * u) - tau) := Int.mul_pos htau (by omega)
      omega
    else
      rw [ite_eq_right_iff.mpr (fun h => absurd h h1),
          ite_eq_right_iff.mpr (fun h => absurd h h2)]
      have hpos := int_sq_pos_of_ne_zero u hu
      omega

/-- Theorem 22: Exact monotone 1-Lipschitz regularity of Bingham viscoplasticity. -/
theorem bingham_one_lipschitz (tau u1 u2 : Int) (htau : 0 ≤ tau) (hle : u1 ≤ u2) :
    bingham tau u1 ≤ bingham tau u2 ∧ bingham tau u2 - bingham tau u1 ≤ u2 - u1 := by
  unfold bingham reluInt
  if h1 : 0 ≤ u1 - tau then
    have h3 : 0 ≤ u2 - tau := by omega
    rw [ite_eq_left_iff.mpr (fun h => absurd h1 h),
        ite_eq_left_iff.mpr (fun h => absurd h3 h)]
    if h2 : 0 ≤ -u1 - tau then
      rw [ite_eq_left_iff.mpr (fun h => absurd h2 h)]
      if h4 : 0 ≤ -u2 - tau then
        rw [ite_eq_left_iff.mpr (fun h => absurd h4 h)]; exact ⟨by omega, by omega⟩
      else
        rw [ite_eq_right_iff.mpr (fun h => absurd h h4)]; exact ⟨by omega, by omega⟩
    else
      have h4 : ¬ (0 ≤ -u2 - tau) := by omega
      rw [ite_eq_right_iff.mpr (fun h => absurd h h2),
          ite_eq_right_iff.mpr (fun h => absurd h h4)]; exact ⟨by omega, by omega⟩
  else
    rw [ite_eq_right_iff.mpr (fun h => absurd h h1)]
    if h2 : 0 ≤ -u1 - tau then
      rw [ite_eq_left_iff.mpr (fun h => absurd h2 h)]
      if h3 : 0 ≤ u2 - tau then
        rw [ite_eq_left_iff.mpr (fun h => absurd h3 h)]
        if h4 : 0 ≤ -u2 - tau then
          rw [ite_eq_left_iff.mpr (fun h => absurd h4 h)]; exact ⟨by omega, by omega⟩
        else
          rw [ite_eq_right_iff.mpr (fun h => absurd h h4)]; exact ⟨by omega, by omega⟩
      else
        rw [ite_eq_right_iff.mpr (fun h => absurd h h3)]
        if h4 : 0 ≤ -u2 - tau then
          rw [ite_eq_left_iff.mpr (fun h => absurd h4 h)]; exact ⟨by omega, by omega⟩
        else
          rw [ite_eq_right_iff.mpr (fun h => absurd h h4)]; exact ⟨by omega, by omega⟩
    else
      have h4 : ¬ (0 ≤ -u2 - tau) := by omega
      rw [ite_eq_right_iff.mpr (fun h => absurd h h2),
          ite_eq_right_iff.mpr (fun h => absurd h h4)]
      if h3 : 0 ≤ u2 - tau then
        rw [ite_eq_left_iff.mpr (fun h => absurd h3 h)]; exact ⟨by omega, by omega⟩
      else
        rw [ite_eq_right_iff.mpr (fun h => absurd h h3)]; exact ⟨by omega, by omega⟩

/-- Theorem 23 (Stagnant Lid Fix + Law-5 Obstruction B5):
    Per-example max threshold tau_max >= |u_i| yields exact Stagnant Lid Q = 0
    for every coordinate i < n; whereas tau = 1 < 2 leaks non-zero flux (bingham 1 2 != 0). -/
theorem bingham_stagnant_lid_and_b5_obstruction :
    (∀ n tauMax (u : Nat → Int), (∀ i, i < n → -tauMax ≤ u i ∧ u i ≤ tauMax) →
      ∀ i, i < n → bingham tauMax (u i) = 0) ∧
    bingham 1 2 ≠ 0 := by
  constructor
  · intro n tauMax u hbound i hi
    exact bingham_sub_yield_plug_zero tauMax (u i) (hbound i hi).1 (hbound i hi).2
  · unfold bingham reluInt
    decide

/-- Theorem 24 (Track S50 Law-5 Obstruction): Bingham/ReLU soft-thresholding does NOT
    commute with linear sums / discrete divergence: [Bingham, +] != 0. -/
theorem bingham_non_commuting_obstruction :
    bingham 1 (2 + (-1)) ≠ bingham 1 2 + bingham 1 (-1) := by
  unfold bingham reluInt
  decide

/-- Theorem 25 (PREREG-S110-AMENDMENT1 Discovery 3 — Repaired Vector-Proximal Poloidal
    Bingham Operator S_Y^H): preserves Poloidal/Toroidal Hodge orthogonality, satisfies
    the exact Pythagorean energy law without post-renorm, contracts L2 energy whenever
    0 <= g <= D, and cleanly zeros poloidal flux at sub-yield plug flow (g = 0). -/
theorem poloidal_bingham_orthogonality_and_energy (n : Nat) (D g : Int)
    (uPol uTor : Nat → Int) (horth : dotN n uPol uTor = 0)
    (hg0 : 0 ≤ g) (hgD : g ≤ D) :
    dotN n (fun i => g * uPol i) (fun i => D * uTor i) = 0 ∧
    normSqN n (polBingham D g uPol uTor) = g * g * normSqN n uPol + D * D * normSqN n uTor ∧
    normSqN n (polBingham D g uPol uTor) ≤ D * D * normSqN n (fun i => uPol i + uTor i) ∧
    (∀ i, polBingham D 0 uPol uTor i = D * uTor i) := by
  have h1 : dotN n (fun i => g * uPol i) (fun i => D * uTor i) = 0 := by
    calc dotN n (fun i => g * uPol i) (fun i => D * uTor i)
        = sumN n (fun i => (g * D) * (uPol i * uTor i)) := by
            unfold dotN
            apply sumN_congr
            intro i _
            rw [Int.mul_assoc g (uPol i), ← Int.mul_assoc (uPol i) D (uTor i),
                Int.mul_comm (uPol i) D, Int.mul_assoc D (uPol i) (uTor i),
                ← Int.mul_assoc g D]
      _ = (g * D) * dotN n uPol uTor := sumN_mul_left n (g * D) (fun i => uPol i * uTor i)
      _ = 0 := by rw [horth, Int.mul_zero]
  have h2 : normSqN n (polBingham D g uPol uTor) =
      g * g * normSqN n uPol + D * D * normSqN n uTor := by
    unfold normSqN dotN polBingham
    calc sumN n (fun i => (g * uPol i + D * uTor i) * (g * uPol i + D * uTor i))
        = sumN n (fun i => (g * g * (uPol i * uPol i) +
            2 * (g * D) * (uPol i * uTor i)) + D * D * (uTor i * uTor i)) := by
            apply sumN_congr
            intro i _
            simp only [Int.add_mul, Int.mul_add]
            have e1 : g * uPol i * (g * uPol i) = g * g * (uPol i * uPol i) := by
              rw [Int.mul_assoc g (uPol i), ← Int.mul_assoc (uPol i) g (uPol i),
                  Int.mul_comm (uPol i) g, Int.mul_assoc g (uPol i) (uPol i), ← Int.mul_assoc g g]
            have e2 : D * uTor i * (D * uTor i) = D * D * (uTor i * uTor i) := by
              rw [Int.mul_assoc D (uTor i), ← Int.mul_assoc (uTor i) D (uTor i),
                  Int.mul_comm (uTor i) D, Int.mul_assoc D (uTor i) (uTor i), ← Int.mul_assoc D D]
            have e3 : g * uPol i * (D * uTor i) = (g * D) * (uPol i * uTor i) := by
              rw [Int.mul_assoc g (uPol i), ← Int.mul_assoc (uPol i) D (uTor i),
                  Int.mul_comm (uPol i) D, Int.mul_assoc D (uPol i) (uTor i), ← Int.mul_assoc g D]
            have e4 : D * uTor i * (g * uPol i) = (g * D) * (uPol i * uTor i) := by
              rw [Int.mul_comm (D * uTor i) (g * uPol i)]; exact e3
            have e5 : 2 * (g * D) * (uPol i * uTor i) =
                (g * D) * (uPol i * uTor i) + (g * D) * (uPol i * uTor i) := by
              rw [Int.mul_assoc 2, Int.two_mul]
            rw [e1, e2, e3, e4, e5]
            omega
      _ = (sumN n (fun i => g * g * (uPol i * uPol i)) +
           sumN n (fun i => 2 * (g * D) * (uPol i * uTor i))) +
          sumN n (fun i => D * D * (uTor i * uTor i)) := by
            rw [sumN_add, sumN_add]
      _ = (g * g * sumN n (fun i => uPol i * uPol i) +
           2 * (g * D) * dotN n uPol uTor) +
          D * D * sumN n (fun i => uTor i * uTor i) := by
            rw [sumN_mul_left, sumN_mul_left, sumN_mul_left]
            rfl
      _ = g * g * sumN n (fun i => uPol i * uPol i) +
          D * D * sumN n (fun i => uTor i * uTor i) := by
            rw [horth, Int.mul_zero]; omega
  have hsum_orth : normSqN n (fun i => uPol i + uTor i) = normSqN n uPol + normSqN n uTor := by
    unfold normSqN dotN
    calc sumN n (fun i => (uPol i + uTor i) * (uPol i + uTor i))
        = sumN n (fun i => (uPol i * uPol i + 2 * (uPol i * uTor i)) + uTor i * uTor i) := by
            apply sumN_congr
            intro i _
            simp only [Int.add_mul, Int.mul_add]
            rw [Int.mul_comm (uTor i) (uPol i), Int.two_mul]
            omega
      _ = (sumN n (fun i => uPol i * uPol i) + sumN n (fun i => 2 * (uPol i * uTor i))) +
          sumN n (fun i => uTor i * uTor i) := by rw [sumN_add, sumN_add]
      _ = (sumN n (fun i => uPol i * uPol i) + 2 * dotN n uPol uTor) +
          sumN n (fun i => uTor i * uTor i) := by rw [sumN_mul_left]; rfl
      _ = sumN n (fun i => uPol i * uPol i) + sumN n (fun i => uTor i * uTor i) := by
            rw [horth, Int.mul_zero]; omega
  have h3 : normSqN n (polBingham D g uPol uTor) ≤ D * D * normSqN n (fun i => uPol i + uTor i) := by
    rw [h2, hsum_orth, Int.mul_add]
    have hgsq : g * g ≤ D * D := by
      have hd : D * D - g * g = (D - g) * (D + g) := by
        simp only [Int.sub_mul, Int.mul_add]; rw [Int.mul_comm g D]; omega
      have hnn : 0 ≤ (D - g) * (D + g) := Int.mul_nonneg (by omega) (by omega)
      omega
    have hnp : 0 ≤ normSqN n uPol := normSqN_nonneg n uPol
    have hle : g * g * normSqN n uPol ≤ D * D * normSqN n uPol := by
      rw [Int.mul_comm (g * g), Int.mul_comm (D * D)]
      exact int_mul_le_left_nonneg (normSqN n uPol) (g * g) (D * D) hnp hgsq
    omega
  have h4 : ∀ i, polBingham D 0 uPol uTor i = D * uTor i := by
    intro i
    unfold polBingham
    rw [Int.zero_mul, Int.zero_add]
  exact ⟨h1, h2, h3, h4⟩

/-- Theorem 26 (Discovery 3 — Exact SO(k) Equivariance of S_Y^H vs Coordinate-ReLU Failure):
    Vector-Proximal Poloidal Bingham commutes identically with EVERY linear / SO(k) map Q
    in arbitrary dimension n; in contrast, coordinate-wise Bingham breaks SO(2) equivariance
    on the 45-degree rotation of (2, 0) -> (1, 1) (scaled by sqrt(2)). -/
theorem poloidal_bingham_so_equivariance (n : Nat) (D g : Int)
    (Q : Nat → Nat → Int) (uPol uTor : Nat → Int) :
    (∀ i, matVec n Q (polBingham D g uPol uTor) i =
      polBingham D g (matVec n Q uPol) (matVec n Q uTor) i) ∧
    (bingham 1 2 * bingham 1 2 + bingham 1 0 * bingham 1 0) * 2 ≠
      bingham 1 1 * bingham 1 1 + bingham 1 1 * bingham 1 1 := by
  constructor
  · intro i
    unfold matVec polBingham
    calc sumN n (fun j => Q i j * (g * uPol j + D * uTor j))
        = sumN n (fun j => g * (Q i j * uPol j) + D * (Q i j * uTor j)) := by
            apply sumN_congr
            intro j _
            rw [Int.mul_add, ← Int.mul_assoc (Q i j) g, Int.mul_comm (Q i j) g, Int.mul_assoc g,
                ← Int.mul_assoc (Q i j) D, Int.mul_comm (Q i j) D, Int.mul_assoc D]
      _ = sumN n (fun j => g * (Q i j * uPol j)) + sumN n (fun j => D * (Q i j * uTor j)) :=
            sumN_add n _ _
      _ = g * sumN n (fun j => Q i j * uPol j) + D * sumN n (fun j => Q i j * uTor j) := by
            rw [sumN_mul_left, sumN_mul_left]
  · unfold bingham reluInt
    decide

/-- Theorem 27: Constructive arbitrary-dimension Cauchy-Schwarz inequality over Z^n
    via incremental Lagrange sum-of-squares identity (zero square roots, zero choice). -/
theorem cauchy_schwarz_int_n (n : Nat) (w d : Nat → Int) :
    dotN n w d * dotN n w d ≤ normSqN n w * normSqN n d := by
  induction n with
  | zero =>
    unfold normSqN dotN sumN
    omega
  | succ k ih =>
    have hstep :
        normSqN (k + 1) w * normSqN (k + 1) d - dotN (k + 1) w d * dotN (k + 1) w d =
        (normSqN k w * normSqN k d - dotN k w d * dotN k w d) +
        sumN k (fun i => (w i * d k - w k * d i) * (w i * d k - w k * d i)) := by
      have hlag :
          sumN k (fun i => (w i * d k - w k * d i) * (w i * d k - w k * d i)) =
          normSqN k w * (d k * d k) - 2 * (w k * d k) * dotN k w d + normSqN k d * (w k * w k) := by
        have hterm : ∀ i : Nat,
            (w i * d k - w k * d i) * (w i * d k - w k * d i) =
            (w i * w i) * (d k * d k) - 2 * (w k * d k) * (w i * d i) + (d i * d i) * (w k * w k) := by
          intro i
          simp only [Int.sub_mul, Int.mul_sub]
          have p1 : w i * d k * (w i * d k) = w i * w i * (d k * d k) := by
            rw [Int.mul_assoc (w i) (d k), ← Int.mul_assoc (d k) (w i) (d k), Int.mul_comm (d k) (w i),
                Int.mul_assoc (w i) (d k) (d k), ← Int.mul_assoc (w i) (w i)]
          have p2 : w k * d i * (w k * d i) = d i * d i * (w k * w k) := by
            rw [Int.mul_assoc (w k) (d i), ← Int.mul_assoc (d i) (w k) (d i), Int.mul_comm (d i) (w k),
                Int.mul_assoc (w k) (d i) (d i), ← Int.mul_assoc (w k) (w k), Int.mul_comm (w k * w k)]
          have p3 : w i * d k * (w k * d i) = (w k * d k) * (w i * d i) := by
            rw [Int.mul_assoc (w i) (d k), ← Int.mul_assoc (d k) (w k) (d i), Int.mul_comm (d k) (w k),
                Int.mul_assoc (w k) (d k) (d i), ← Int.mul_assoc (w i) (w k) (d k * d i),
                Int.mul_comm (w i) (w k), Int.mul_assoc (w k) (w i) (d k * d i),
                ← Int.mul_assoc (w i) (d k) (d i), Int.mul_comm (w i) (d k),
                Int.mul_assoc (d k) (w i) (d i), ← Int.mul_assoc (w k) (d k) (w i * d i)]
          have p4 : w k * d i * (w i * d k) = (w k * d k) * (w i * d i) := by
            rw [Int.mul_comm (w k * d i) (w i * d k)]; exact p3
          rw [p1, p2, p3, p4]
          have h2 : 2 * (w k * d k) * (w i * d i) =
              (w k * d k) * (w i * d i) + (w k * d k) * (w i * d i) := by
            rw [Int.mul_assoc 2, Int.two_mul]
          rw [h2]
          omega
        calc sumN k (fun i => (w i * d k - w k * d i) * (w i * d k - w k * d i))
            = sumN k (fun i => (w i * w i) * (d k * d k) -
                  2 * (w k * d k) * (w i * d i) + (d i * d i) * (w k * w k)) :=
                sumN_congr k _ _ (fun i _ => hterm i)
          _ = sumN k (fun i => (w i * w i) * (d k * d k) - 2 * (w k * d k) * (w i * d i)) +
              sumN k (fun i => (d i * d i) * (w k * w k)) := sumN_add k _ _
          _ = sumN k (fun i => (w i * w i) * (d k * d k)) -
              sumN k (fun i => 2 * (w k * d k) * (w i * d i)) +
              sumN k (fun i => (d i * d i) * (w k * w k)) := by rw [sumN_sub]
          _ = normSqN k w * (d k * d k) - 2 * (w k * d k) * dotN k w d +
              normSqN k d * (w k * w k) := by
                unfold normSqN dotN
                rw [sumN_mul_right, sumN_mul_left, sumN_mul_right]
      rw [hlag]
      have hnw : normSqN (k + 1) w = normSqN k w + w k * w k := rfl
      have hnd : normSqN (k + 1) d = normSqN k d + d k * d k := rfl
      have hdt : dotN (k + 1) w d = dotN k w d + w k * d k := rfl
      rw [hnw, hnd, hdt]
      simp only [Int.add_mul, Int.mul_add]
      have hs1 : w k * w k * (d k * d k) = w k * d k * (w k * d k) := by
        rw [Int.mul_assoc (w k) (w k), ← Int.mul_assoc (w k) (d k) (d k),
            Int.mul_comm (w k) (d k), Int.mul_assoc (d k) (w k) (d k),
            ← Int.mul_assoc (w k) (d k) (w k * d k), Int.mul_comm (d k) (w k)]
      have hs2 : w k * w k * normSqN k d = normSqN k d * (w k * w k) := Int.mul_comm _ _
      have hs3 : dotN k w d * (w k * d k) = (w k * d k) * dotN k w d := Int.mul_comm _ _
      have hs4 : 2 * (w k * d k) * dotN k w d =
          (w k * d k) * dotN k w d + (w k * d k) * dotN k w d := by
        rw [Int.mul_assoc 2, Int.two_mul]
      rw [hs1, hs2, hs3, hs4]
      omega
    have hnn : 0 ≤ sumN k (fun i => (w i * d k - w k * d i) * (w i * d k - w k * d i)) :=
      sumN_nonneg k _ (fun i _ => int_sq_nonneg _)
    omega

private theorem clipInt_sq_le (B u : Int) :
    clipInt B u * clipInt B u ≤ B * B := by
  unfold clipInt
  if h1 : B < u then
    rw [ite_eq_left_iff.mpr (fun h => absurd h1 h)]
    exact Int.le_refl _
  else
    rw [ite_eq_right_iff.mpr (fun h => absurd h h1)]
    if h2 : u < -B then
      rw [ite_eq_left_iff.mpr (fun h => absurd h2 h), Int.neg_mul_neg]
      exact Int.le_refl _
    else
      rw [ite_eq_right_iff.mpr (fun h => absurd h h2)]
      have hdiff : B * B - u * u = (B - u) * (B + u) := by
        simp only [Int.sub_mul, Int.mul_add]; rw [Int.mul_comm u B]; omega
      have hnn : 0 ≤ (B - u) * (B + u) := Int.mul_nonneg (by omega) (by omega)
      omega

/-- Theorem 28: Track S50 Ozone / Channel-2B frozen-weight (ΔW = 0) advection airlock bound
    and strict monotonicity in the band-pass/clip cap 0 <= B1 <= B2 over arbitrary Z^n. -/
theorem ozone_channel2b_advection_airlock_bound (n : Nat) (tau B1 B2 : Int)
    (w d : Nat → Int) (htau : 0 ≤ tau) (hB1 : 0 ≤ B1) (hB12 : B1 ≤ B2) :
    dotN n w (fun i => bingham tau (clipInt B1 (d i))) *
      dotN n w (fun i => bingham tau (clipInt B1 (d i))) ≤
      normSqN n w * (Int.ofNat n * (B1 * B1)) ∧
    normSqN n w * (Int.ofNat n * (B1 * B1)) ≤
      normSqN n w * (Int.ofNat n * (B2 * B2)) := by
  have hcs := cauchy_schwarz_int_n n w (fun i => bingham tau (clipInt B1 (d i)))
  have hnorm : normSqN n (fun i => bingham tau (clipInt B1 (d i))) ≤ Int.ofNat n * (B1 * B1) := by
    calc normSqN n (fun i => bingham tau (clipInt B1 (d i)))
        ≤ sumN n (fun _ => B1 * B1) := by
            unfold normSqN dotN
            apply sumN_le
            intro i _
            exact Int.le_trans (bingham_sq_nonexpansive tau (clipInt B1 (d i)) htau)
              (clipInt_sq_le B1 (d i))
      _ = Int.ofNat n * (B1 * B1) := sumN_const n (B1 * B1)
  have hnw : 0 ≤ normSqN n w := normSqN_nonneg n w
  have hcap1 : normSqN n w * normSqN n (fun i => bingham tau (clipInt B1 (d i))) ≤
      normSqN n w * (Int.ofNat n * (B1 * B1)) :=
    int_mul_le_left_nonneg (normSqN n w) _ _ hnw hnorm
  have hBsq : B1 * B1 ≤ B2 * B2 := by
    have hd : B2 * B2 - B1 * B1 = (B2 - B1) * (B2 + B1) := by
      simp only [Int.sub_mul, Int.mul_add]; rw [Int.mul_comm B1 B2]; omega
    have hnn : 0 ≤ (B2 - B1) * (B2 + B1) := Int.mul_nonneg (by omega) (by omega)
    omega
  have hcap2 : normSqN n w * (Int.ofNat n * (B1 * B1)) ≤
      normSqN n w * (Int.ofNat n * (B2 * B2)) :=
    int_mul_le_left_nonneg (normSqN n w) _ _ hnw
      (int_mul_le_left_nonneg (Int.ofNat n) _ _ (Int.natCast_nonneg n) hBsq)
  exact ⟨Int.le_trans hcs hcap1, hcap2⟩

-- ============================================================================
-- PILLAR 4: Weft-Smith Composed Triple Gate, Householder C_row & O(1) Rollback
-- ============================================================================

def householderCleared (n : Nat) (u v : Nat → Int) (i : Nat) : Int :=
  normSqN n u * v i - 2 * dotN n u v * u i

/-- Theorem 29: Universal arbitrary-dimension Householder orthogonal reflection isometry
    over Z^n: ‖H_u^{cl} v‖^2 = ‖u‖^4 * ‖v‖^2. -/
theorem householder_reflection_norm_sq (n : Nat) (u v : Nat → Int) :
    normSqN n (householderCleared n u v) = normSqN n u * normSqN n u * normSqN n v := by
  let s := normSqN n u
  let p := dotN n u v
  unfold normSqN dotN householderCleared
  calc sumN n (fun i => (s * v i - 2 * p * u i) * (s * v i - 2 * p * u i))
      = sumN n (fun i => s * s * (v i * v i) - 4 * s * p * (u i * v i) + 4 * p * p * (u i * u i)) := by
          apply sumN_congr
          intro i _
          simp only [Int.sub_mul, Int.mul_sub]
          have h22 : (2 : Int) * 2 = 4 := rfl
          have e1 : s * v i * (s * v i) = s * s * (v i * v i) := by
            rw [Int.mul_assoc s (v i), ← Int.mul_assoc (v i) s (v i), Int.mul_comm (v i) s,
                Int.mul_assoc s (v i) (v i), ← Int.mul_assoc s s]
          have e2 : 2 * p * u i * (2 * p * u i) = 4 * p * p * (u i * u i) := by
            rw [Int.mul_assoc (2 * p) (u i), ← Int.mul_assoc (u i) (2 * p) (u i),
                Int.mul_comm (u i) (2 * p), Int.mul_assoc (2 * p) (u i) (u i),
                ← Int.mul_assoc (2 * p) (2 * p), Int.mul_assoc 2 p (2 * p),
                ← Int.mul_assoc p 2 p, Int.mul_comm p 2, Int.mul_assoc 2 p p,
                ← Int.mul_assoc 2 2 (p * p), h22, ← Int.mul_assoc 4 p p]
          have e3 : s * v i * (2 * p * u i) = 2 * s * p * (u i * v i) := by
            rw [Int.mul_assoc s (v i), ← Int.mul_assoc (v i) (2 * p) (u i),
                Int.mul_comm (v i) (2 * p), Int.mul_assoc (2 * p) (v i) (u i),
                Int.mul_comm (v i) (u i), ← Int.mul_assoc s (2 * p),
                ← Int.mul_assoc s 2 p, Int.mul_comm s 2]
          have e4 : 2 * p * u i * (s * v i) = 2 * s * p * (u i * v i) := by
            rw [Int.mul_comm (2 * p * u i) (s * v i)]; exact e3
          have e5 : 4 * s * p * (u i * v i) =
              2 * s * p * (u i * v i) + 2 * s * p * (u i * v i) := by
            rw [← Int.add_mul, ← Int.add_mul, ← Int.add_mul]
            have : (2 : Int) + 2 = 4 := rfl
            rw [this]
          rw [e1, e2, e3, e4, e5]
          omega
    _ = sumN n (fun i => s * s * (v i * v i) - 4 * s * p * (u i * v i)) +
        sumN n (fun i => 4 * p * p * (u i * u i)) := sumN_add n _ _
    _ = sumN n (fun i => s * s * (v i * v i)) -
        sumN n (fun i => 4 * s * p * (u i * v i)) +
        sumN n (fun i => 4 * p * p * (u i * u i)) := by rw [sumN_sub]
    _ = s * s * sumN n (fun i => v i * v i) -
        4 * s * p * p + 4 * p * p * s := by
          rw [sumN_mul_left, sumN_mul_left, sumN_mul_left]
          rfl
    _ = s * s * sumN n (fun i => v i * v i) := by
          have hc : 4 * s * p * p = 4 * p * p * s := by
            rw [Int.mul_assoc 4 s p, Int.mul_comm s p, ← Int.mul_assoc 4 p s,
                Int.mul_assoc (4 * p) s p, Int.mul_comm s p, ← Int.mul_assoc (4 * p) p s]
          omega

/-- Theorem 30: Exact Track S31 DPI row-concentration cap C_row(ΔW) <= C_max is preserved
    identically under any non-zero cleared-denominator orthogonal / Householder reflection
    (scaling every row norm^2 and total norm^2 by s^2 > 0). -/
theorem weft_crow_preserved_under_reflection (s rowNormSq totalNormSq cNum cDen : Int)
    (hs : s ≠ 0) :
    rowNormSq * cDen ≤ cNum * totalNormSq ↔
    (s * s * rowNormSq) * cDen ≤ cNum * (s * s * totalNormSq) := by
  have hspos : 0 < s * s := int_sq_pos_of_ne_zero s hs
  have hl : (s * s * rowNormSq) * cDen = (s * s) * (rowNormSq * cDen) := Int.mul_assoc _ _ _
  have hr : cNum * (s * s * totalNormSq) = (s * s) * (cNum * totalNormSq) := by
    rw [← Int.mul_assoc, Int.mul_comm cNum (s * s), Int.mul_assoc]
  rw [hl, hr]
  constructor
  · intro h
    exact int_mul_le_left_nonneg (s * s) _ _ (Int.le_of_lt hspos) h
  · intro h
    if hle : rowNormSq * cDen ≤ cNum * totalNormSq then
      exact hle
    else
      have hgt : 0 < rowNormSq * cDen - cNum * totalNormSq := by omega
      have hmul : 0 < (s * s) * (rowNormSq * cDen - cNum * totalNormSq) :=
        Int.mul_pos hspos hgt
      rw [Int.mul_sub] at hmul
      omega

inductive WriteDomain where
  | core
  | rewriter
  | plate
deriving DecidableEq

structure WeftState where
  coreW : Nat → Int
  rewriterPsi : Nat → Int
  plateW : Nat → Int
  anchorErr : Int
  rewriterCanEmitText : Bool
  rewriterCanInvokeTool : Bool

structure WeftPatch where
  target : WriteDomain
  proposedPlateW : Nat → Int
  postAnchorErr : Int
  staticOk : Bool
  receiptOk : Bool

def weftGatePasses (pre : WeftState) (p : WeftPatch) : Bool :=
  p.staticOk && p.receiptOk && decide (p.target = WriteDomain.plate) &&
    decide (p.postAnchorErr ≤ pre.anchorErr)

def weftStep (pre : WeftState) (p : WeftPatch) : WeftState :=
  if weftGatePasses pre p then
    { pre with plateW := p.proposedPlateW, anchorErr := p.postAnchorErr }
  else
    pre

def weftRun : WeftState → List WeftPatch → WeftState
  | st, [] => st
  | st, p :: ps => weftRun (weftStep st p) ps

/-- Theorem 31: Strict Shell-1 / Shell-2 Capability Isolation:
    every gated Weft-Smith step leaves Inner Core W_core and Rewriter ψ identically unchanged. -/
theorem weft_step_capability_isolation (pre : WeftState) (p : WeftPatch) :
    (weftStep pre p).coreW = pre.coreW ∧ (weftStep pre p).rewriterPsi = pre.rewriterPsi := by
  unfold weftStep
  cases weftGatePasses pre p <;> exact ⟨rfl, rfl⟩

/-- Theorem 32: Non-Generative Capability Mask Invariance:
    Weft-Smith never acquires text-emission or tool-invocation capabilities across steps. -/
theorem weft_step_non_generative_mask (pre : WeftState) (p : WeftPatch)
    (ht : pre.rewriterCanEmitText = false) (hi : pre.rewriterCanInvokeTool = false) :
    (weftStep pre p).rewriterCanEmitText = false ∧
    (weftStep pre p).rewriterCanInvokeTool = false := by
  unfold weftStep
  cases weftGatePasses pre p <;> exact ⟨ht, hi⟩

/-- Theorem 33: Exact O(1) Rollback Soundness:
    failing StaticGate, failing ReceiptGate, targeting Core/Rewriter, OR triggering
    any held-out anchor regression restores pre-state identically (post = pre). -/
theorem weft_step_rollback_soundness (pre : WeftState) (p : WeftPatch)
    (hfail : p.staticOk = false ∨ p.receiptOk = false ∨
             p.target ≠ WriteDomain.plate ∨ pre.anchorErr < p.postAnchorErr) :
    weftStep pre p = pre := by
  have hg : weftGatePasses pre p = false := by
    unfold weftGatePasses
    rcases hfail with h | h | h | h
    · rw [h]; rfl
    · rw [h]; cases p.staticOk <;> rfl
    · have hd : decide (p.target = WriteDomain.plate) = false := decide_eq_false h
      rw [hd]; cases p.staticOk <;> cases p.receiptOk <;> rfl
    · have hnot : ¬ (p.postAnchorErr ≤ pre.anchorErr) := by omega
      have hd : decide (p.postAnchorErr ≤ pre.anchorErr) = false := decide_eq_false hnot
      rw [hd]; cases p.staticOk <;> cases p.receiptOk <;>
        cases decide (p.target = WriteDomain.plate) <;> rfl
  unfold weftStep
  rw [hg]
  rfl

/-- Theorem 34: Exact Commit Soundness under the Composed Triple Gate:
    when all three gates pass on Shell-3 plate, plateW updates and anchorErr never regresses. -/
theorem weft_step_commit_soundness (pre : WeftState) (p : WeftPatch)
    (hs : p.staticOk = true) (hr : p.receiptOk = true)
    (ht : p.target = WriteDomain.plate) (ha : p.postAnchorErr ≤ pre.anchorErr) :
    (weftStep pre p).plateW = p.proposedPlateW ∧
    (weftStep pre p).anchorErr = p.postAnchorErr ∧
    (weftStep pre p).anchorErr ≤ pre.anchorErr := by
  have hg : weftGatePasses pre p = true := by
    unfold weftGatePasses
    rw [hs, hr, decide_eq_true ht, decide_eq_true ha]
    rfl
  unfold weftStep
  rw [hg]
  exact ⟨rfl, rfl, ha⟩

/-- Theorem 35 (Track S104 Composed Triple-Gate Non-Redundancy):
    universally over any pre-state and proposed plate patch, dropping ANY ONE of the three
    gates (Anchor, Receipt, or Static) while the other two pass triggers exact rollback. -/
theorem weft_triple_gate_non_redundancy (pre : WeftState) (prop : Nat → Int) :
    weftStep pre ⟨WriteDomain.plate, prop, pre.anchorErr + 1, true, true⟩ = pre ∧
    weftStep pre ⟨WriteDomain.plate, prop, pre.anchorErr, true, false⟩ = pre ∧
    weftStep pre ⟨WriteDomain.plate, prop, pre.anchorErr, false, true⟩ = pre := by
  refine ⟨?_, ?_, ?_⟩
  · have hlt : pre.anchorErr < pre.anchorErr + 1 := by omega
    exact weft_step_rollback_soundness pre
      ⟨WriteDomain.plate, prop, pre.anchorErr + 1, true, true⟩
      (Or.inr (Or.inr (Or.inr hlt)))
  · exact weft_step_rollback_soundness pre
      ⟨WriteDomain.plate, prop, pre.anchorErr, true, false⟩
      (Or.inr (Or.inl rfl))
  · exact weft_step_rollback_soundness pre
      ⟨WriteDomain.plate, prop, pre.anchorErr, false, true⟩
      (Or.inl rfl)

private theorem weft_step_anchor_monotone (pre : WeftState) (p : WeftPatch) :
    (weftStep pre p).anchorErr ≤ pre.anchorErr := by
  unfold weftStep
  cases hg : weftGatePasses pre p with
  | false =>
    exact Int.le_refl _
  | true =>
    unfold weftGatePasses at hg
    have h4 : decide (p.postAnchorErr ≤ pre.anchorErr) = true := by
      cases h1 : p.staticOk <;> cases h2 : p.receiptOk <;>
        cases h3 : decide (p.target = WriteDomain.plate) <;>
        cases h4' : decide (p.postAnchorErr ≤ pre.anchorErr)
      all_goals simp only [h1, h2, h3, h4', Bool.false_and, Bool.true_and, Bool.and_false] at hg
      all_goals first | rfl | exact absurd hg (by decide)
    exact of_decide_eq_true h4

/-- Theorem 36 (H11c Multi-Cycle Stability Invariant):
    across ANY finite sequence of T >= 0 adaptation cycles with arbitrary interleaved clean
    and poisoned patches, Core W_core, Rewriter ψ, and the non-generative capability mask
    remain identically invariant, and anchorErr is monotonically non-increasing. -/
theorem weft_multicycle_safety_invariant (init : WeftState) (patches : List WeftPatch) :
    (weftRun init patches).coreW = init.coreW ∧
    (weftRun init patches).rewriterPsi = init.rewriterPsi ∧
    (weftRun init patches).rewriterCanEmitText = init.rewriterCanEmitText ∧
    (weftRun init patches).rewriterCanInvokeTool = init.rewriterCanInvokeTool ∧
    (weftRun init patches).anchorErr ≤ init.anchorErr := by
  induction patches generalizing init with
  | nil =>
    exact ⟨rfl, rfl, rfl, rfl, Int.le_refl _⟩
  | cons p ps ih =>
    simp only [weftRun]
    have hstep := ih (weftStep init p)
    have hiso := weft_step_capability_isolation init p
    have hmask : (weftStep init p).rewriterCanEmitText = init.rewriterCanEmitText ∧
        (weftStep init p).rewriterCanInvokeTool = init.rewriterCanInvokeTool := by
      unfold weftStep
      cases weftGatePasses init p <;> exact ⟨rfl, rfl⟩
    have hanc := weft_step_anchor_monotone init p
    exact ⟨Eq.trans hstep.1 hiso.1,
           Eq.trans hstep.2.1 hiso.2,
           Eq.trans hstep.2.2.1 hmask.1,
           Eq.trans hstep.2.2.2.1 hmask.2,
           Int.le_trans hstep.2.2.2.2 hanc⟩

/-- Theorem 37 (PREREG-S111 Convergence #1 Law-5 Obstruction — C_row Cancellation Attack):
    Universally for every non-zero amplitude a != 0, two patches d1 = (a, a) and d2 = (a, -a)
    EACH individually obey C_row <= 1/2 (row_i^2 * 2 <= total_sq), yet their composed sum
    d1 + d2 = (2a, 0) violates C_row <= 1/2 strictly (row0^2 * 2 > total_sq), proving that
    per-patch C_row caps are insufficient and C_row MUST be gated on composed Σ ΔW_k. -/
theorem weft_crow_cancellation_obstruction (a : Int) (ha : a ≠ 0) :
    let d1r0 := a; let d1r1 := a
    let d2r0 := a; let d2r1 := -a
    let c0 := d1r0 + d2r0; let c1 := d1r1 + d2r1
    (d1r0 * d1r0 * 2 ≤ d1r0 * d1r0 + d1r1 * d1r1) ∧
    (d2r0 * d2r0 * 2 ≤ d2r0 * d2r0 + d2r1 * d2r1) ∧
    (c0 * c0 + c1 * c1 < c0 * c0 * 2) := by
  have hpos : 0 < a * a := int_sq_pos_of_ne_zero a ha
  have hneg : (-a) * (-a) = a * a := Int.neg_mul_neg a a
  have h2a : (a + a) * (a + a) = 4 * (a * a) := by
    simp only [Int.add_mul, Int.mul_add]
    omega
  refine ⟨?_, ?_, ?_⟩
  · omega
  · rw [hneg]; omega
  · have hz : a + -a = 0 := by omega
    rw [hz, Int.zero_mul, h2a]
    omega

structure WeftLedgerState where
  coreW : Nat → Int
  rewriterPsi : Nat → Int
  plateW : Nat → Int
  cumNormSq : Int
  cumCapSq : Int
  cumCrowOk : Bool
  kvEpoch : Nat
  anchorErr : Int

structure WeftLedgerPatch where
  target : WriteDomain
  proposedPlateW : Nat → Int
  proposedCumNormSq : Int
  proposedCumCrowOk : Bool
  proposedKvEpoch : Nat
  postAnchorErr : Int
  receiptOk : Bool

def weftLedgerGatePasses (pre : WeftLedgerState) (p : WeftLedgerPatch) : Bool :=
  p.receiptOk &&
  p.proposedCumCrowOk &&
  decide (p.proposedCumNormSq ≤ pre.cumCapSq) &&
  decide (p.target = WriteDomain.plate) &&
  decide (p.postAnchorErr ≤ pre.anchorErr)

def weftLedgerStep (pre : WeftLedgerState) (p : WeftLedgerPatch) : WeftLedgerState :=
  if weftLedgerGatePasses pre p then
    { pre with
      plateW := p.proposedPlateW,
      cumNormSq := p.proposedCumNormSq,
      cumCrowOk := p.proposedCumCrowOk,
      kvEpoch := p.proposedKvEpoch,
      anchorErr := p.postAnchorErr }
  else
    pre

def weftLedgerRun : WeftLedgerState → List WeftLedgerPatch → WeftLedgerState
  | st, [] => st
  | st, p :: ps => weftLedgerRun (weftLedgerStep st p) ps

private theorem weft_ledger_step_preserves (pre : WeftLedgerState) (p : WeftLedgerPatch)
    (hcap : pre.cumNormSq ≤ pre.cumCapSq) (hcrow : pre.cumCrowOk = true) :
    (weftLedgerStep pre p).coreW = pre.coreW ∧
    (weftLedgerStep pre p).rewriterPsi = pre.rewriterPsi ∧
    (weftLedgerStep pre p).cumCapSq = pre.cumCapSq ∧
    (weftLedgerStep pre p).cumNormSq ≤ (weftLedgerStep pre p).cumCapSq ∧
    (weftLedgerStep pre p).cumCrowOk = true ∧
    (weftLedgerStep pre p).anchorErr ≤ pre.anchorErr := by
  unfold weftLedgerStep
  cases hg : weftLedgerGatePasses pre p with
  | false =>
    exact ⟨rfl, rfl, rfl, hcap, hcrow, Int.le_refl _⟩
  | true =>
    unfold weftLedgerGatePasses at hg
    have hparts : p.proposedCumCrowOk = true ∧
        decide (p.proposedCumNormSq ≤ pre.cumCapSq) = true ∧
        decide (p.postAnchorErr ≤ pre.anchorErr) = true := by
      cases h1 : p.receiptOk <;> cases h2 : p.proposedCumCrowOk <;>
        cases h3 : decide (p.proposedCumNormSq ≤ pre.cumCapSq) <;>
        cases h4 : decide (p.target = WriteDomain.plate) <;>
        cases h5 : decide (p.postAnchorErr ≤ pre.anchorErr)
      all_goals simp only [h1, h2, h3, h4, h5, Bool.false_and, Bool.true_and, Bool.and_false] at hg
      all_goals first | exact ⟨rfl, rfl, rfl⟩ | exact absurd hg (by decide)
    exact ⟨rfl, rfl, rfl, of_decide_eq_true hparts.2.1, hparts.1, of_decide_eq_true hparts.2.2⟩

/-- Theorem 38 (PREREG-S111 Convergence #1 & #5 — Composed Cumulative Drift Cap,
    Composed C_row Invariance & Full Rollback-State Equality Across T Cycles):
    Across any sequence of T >= 0 patches gated on composed Σ ΔW_k, Core W_core, Rewriter ψ,
    cumulative Frobenius budget, composed C_row, and monotonic anchorErr are preserved
    inductively, and any failing patch leaves the ENTIRE ledger state (including kvEpoch)
    bit-for-bit identical (post = pre). -/
theorem weft_cumulative_budget_multicycle (init : WeftLedgerState) (patches : List WeftLedgerPatch)
    (hcap : init.cumNormSq ≤ init.cumCapSq) (hcrow : init.cumCrowOk = true) :
    (weftLedgerRun init patches).coreW = init.coreW ∧
    (weftLedgerRun init patches).rewriterPsi = init.rewriterPsi ∧
    (weftLedgerRun init patches).cumNormSq ≤ init.cumCapSq ∧
    (weftLedgerRun init patches).cumCrowOk = true ∧
    (weftLedgerRun init patches).anchorErr ≤ init.anchorErr ∧
    (∀ st p, weftLedgerGatePasses st p = false → weftLedgerStep st p = st) := by
  have hrb : ∀ st p, weftLedgerGatePasses st p = false → weftLedgerStep st p = st := by
    intro st p hfalse
    unfold weftLedgerStep
    rw [hfalse]
    rfl
  induction patches generalizing init with
  | nil =>
    exact ⟨rfl, rfl, hcap, hcrow, Int.le_refl _, hrb⟩
  | cons p ps ih =>
    simp only [weftLedgerRun]
    have hs := weft_ledger_step_preserves init p hcap hcrow
    have hr := ih (weftLedgerStep init p) hs.2.2.2.1 hs.2.2.2.2.1
    rw [hs.2.2.1] at hr
    exact ⟨Eq.trans hr.1 hs.1,
           Eq.trans hr.2.1 hs.2.1,
           hr.2.2.1,
           hr.2.2.2.1,
           Int.le_trans hr.2.2.2.2.1 hs.2.2.2.2.2,
           hr.2.2.2.2.2⟩

end GeosphereWeftConservation

#print axioms GeosphereWeftConservation.skew_diag_zero
#print axioms GeosphereWeftConservation.geodynamo_lorentz_workless
#print axioms GeosphereWeftConservation.geodynamo_cayley_isometry_scaled
#print axioms GeosphereWeftConservation.geodynamo_cayley_isometry
#print axioms GeosphereWeftConservation.rank2_skew_is_skew
#print axioms GeosphereWeftConservation.cayley2_exact_isometry
#print axioms GeosphereWeftConservation.det4_I_plus_skew_pos
#print axioms GeosphereWeftConservation.cayley4_hopf_quat_isometry
#print axioms GeosphereWeftConservation.oceanic_column_stochastic_mass_conservation
#print axioms GeosphereWeftConservation.causal_doubly_stochastic_is_identity
#print axioms GeosphereWeftConservation.orthogonal_birkhoff_is_permutation_entries
#print axioms GeosphereWeftConservation.so2_birkhoff_non_commutation
#print axioms GeosphereWeftConservation.darcy_convex_coord_bound
#print axioms GeosphereWeftConservation.darcy_euclidean_parallelogram_identity
#print axioms GeosphereWeftConservation.darcy_l2_ball_invariance
#print axioms GeosphereWeftConservation.darcy_unbounded_K_obstruction
#print axioms GeosphereWeftConservation.darcy_step_error_strict_contraction
#print axioms GeosphereWeftConservation.bingham_odd
#print axioms GeosphereWeftConservation.bingham_sub_yield_plug_zero
#print axioms GeosphereWeftConservation.bingham_sq_nonexpansive
#print axioms GeosphereWeftConservation.bingham_strict_shrinkage
#print axioms GeosphereWeftConservation.bingham_one_lipschitz
#print axioms GeosphereWeftConservation.bingham_stagnant_lid_and_b5_obstruction
#print axioms GeosphereWeftConservation.bingham_non_commuting_obstruction
#print axioms GeosphereWeftConservation.poloidal_bingham_orthogonality_and_energy
#print axioms GeosphereWeftConservation.poloidal_bingham_so_equivariance
#print axioms GeosphereWeftConservation.cauchy_schwarz_int_n
#print axioms GeosphereWeftConservation.ozone_channel2b_advection_airlock_bound
#print axioms GeosphereWeftConservation.householder_reflection_norm_sq
#print axioms GeosphereWeftConservation.weft_crow_preserved_under_reflection
#print axioms GeosphereWeftConservation.weft_step_capability_isolation
#print axioms GeosphereWeftConservation.weft_step_non_generative_mask
#print axioms GeosphereWeftConservation.weft_step_rollback_soundness
#print axioms GeosphereWeftConservation.weft_step_commit_soundness
#print axioms GeosphereWeftConservation.weft_triple_gate_non_redundancy
#print axioms GeosphereWeftConservation.weft_multicycle_safety_invariant
#print axioms GeosphereWeftConservation.weft_crow_cancellation_obstruction
#print axioms GeosphereWeftConservation.weft_cumulative_budget_multicycle
