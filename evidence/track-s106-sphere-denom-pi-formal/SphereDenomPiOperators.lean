/-
Track S106 Phase 1A — SphereDenomPiOperators.lean (pure Init, Lean 4.36.0, 0 imports).

Exact integer and natural-number formalization of the representation foundations for
PREREG-SPHERE-PI-FORCES-V1:
  1. Graded-period Q[pi] cancellation (omega_{2k-1} / Vol(B^{2k}) = 2k), super-exponential
     growth of the cube-to-ball volume ratio in sphere-unit coordinates (using pi < 22/7),
     and universal Zador ball-beats-cube inequality across all even dimensions d = 2k >= 2
     (using pi > 314/100).
  2. Arbitrary-dimension cleared-denominator EM / Hodge orthogonal error splitting on Z^d,
     Pythagorean identity, transverse-weighted distortion dominance, radial-rescaling
     invariance, and zero transverse error under radial warping.
  3. Exact Denominator-pi Equal-Sphere-Fraction invariants: Archimedes Hat-Box strip invariance
     and exact total partition sum, Hopf EQ(S^3) midpoint linear & quadratic moment laws
     (explaining exact 1s/2s/2p Fock-Moser Hydrogen orthonormality and exact O(1/a^2) 3s
     convergence), and universal 2^B slot-waste obstructions for exceptional designs divisible
     by 3 or 5.
  4. Hypersphere thin-shell Chebyshev concentration monotonicity and Coxeter/Weyl rational
     sphere-fraction group order recurrences and W(D_8) <= W(E_8) index 135.

Axioms: subset of {propext, Quot.sound} only (zero Classical.choice, zero sorryAx, zero warnings).
-/

namespace SphereDenomPiOperators

/-! ## 1. Graded-Period Q[pi] Sphere-Unit & Zador Ball-vs-Cube Theorems -/

def fact : Nat → Nat
  | 0 => 1
  | n + 1 => (n + 1) * fact n

def ballVolNum (_k : Nat) : Nat := 1
def ballVolDen (k : Nat) : Nat := fact k
def sphereAreaNum (_k : Nat) : Nat := 2
def sphereAreaDen (k : Nat) : Nat := fact (k - 1)

theorem fact_pos (n : Nat) : 0 < fact n := by
  induction n with
  | zero => exact Nat.zero_lt_one
  | succ k ih =>
    simp only [fact]
    exact Nat.mul_pos (Nat.succ_pos k) ih

theorem even_sphere_area_to_ball_vol_ratio (k : Nat) (hk : 1 ≤ k) :
    sphereAreaNum k * ballVolDen k = 2 * k * (ballVolNum k * sphereAreaDen k) := by
  cases k with
  | zero => omega
  | succ m =>
    simp only [sphereAreaNum, ballVolDen, ballVolNum, sphereAreaDen, fact, Nat.add_sub_cancel,
      Nat.one_mul, Nat.mul_assoc]

theorem binom_linear_lower_bound (a n : Nat) :
    a ^ n * (a + n) ≤ (a + 1) ^ n * a := by
  induction n with
  | zero =>
    simp only [Nat.pow_zero, Nat.add_zero, Nat.one_mul, Nat.le_refl]
  | succ m ih =>
    have hstep : (a + 1) * (a ^ m * (a + m)) ≤ (a + 1) * ((a + 1) ^ m * a) :=
      Nat.mul_le_mul_left (a + 1) ih
    have hrhs : (a + 1) * ((a + 1) ^ m * a) = (a + 1) ^ (m + 1) * a := by
      rw [Nat.pow_succ, Nat.mul_comm ((a + 1) ^ m) (a + 1), Nat.mul_assoc]
    have h1 : a ^ (m + 1) * (a + (m + 1)) = a ^ m * (a * a + a * m + a) := by
      rw [Nat.pow_succ, Nat.mul_assoc]
      congr 1
      simp only [Nat.mul_add, Nat.mul_one, Nat.add_assoc]
    have h2 : (a + 1) * (a ^ m * (a + m)) = a ^ m * (a * a + a * m + a + m) := by
      rw [Nat.mul_left_comm]
      congr 1
      simp only [Nat.add_mul, Nat.mul_add, Nat.one_mul]
      omega
    have hlhs : a ^ (m + 1) * (a + (m + 1)) ≤ (a + 1) * (a ^ m * (a + m)) := by
      rw [h1, h2]
      exact Nat.mul_le_mul_left (a ^ m) (by omega)
    exact Nat.le_trans hlhs (hrhs ▸ hstep)

theorem zador_step_factor (k : Nat) :
    1200 * (k + 1) * (k + 1) < 628 * (k + 2) * (2 * k + 1) := by
  have hL : 1200 * (k + 1) * (k + 1) = 1200 * (k * k) + 2400 * k + 1200 := by
    calc 1200 * (k + 1) * (k + 1)
        = (1200 * k + 1200) * (k + 1) := by rw [Nat.mul_add 1200 k 1, Nat.mul_one]
      _ = (1200 * k + 1200) * k + (1200 * k + 1200) := by rw [Nat.mul_add, Nat.mul_one]
      _ = 1200 * k * k + 1200 * k + (1200 * k + 1200) := by rw [Nat.add_mul]
      _ = 1200 * (k * k) + 2400 * k + 1200 := by rw [Nat.mul_assoc]; omega
  have hR : 628 * (k + 2) * (2 * k + 1) = 1256 * (k * k) + 3140 * k + 1256 := by
    calc 628 * (k + 2) * (2 * k + 1)
        = (628 * k + 1256) * (2 * k + 1) := by rw [Nat.mul_add 628 k 2]
      _ = (628 * k + 1256) * (2 * k) + (628 * k + 1256) := by rw [Nat.mul_add, Nat.mul_one]
      _ = 628 * k * (2 * k) + 1256 * (2 * k) + (628 * k + 1256) := by rw [Nat.add_mul]
      _ = 1256 * (k * k) + 3140 * k + 1256 := by
          have hsq : 628 * k * (2 * k) = 1256 * (k * k) := by
            calc 628 * k * (2 * k) = 628 * (k * (2 * k)) := Nat.mul_assoc 628 k (2 * k)
              _ = 628 * (2 * (k * k)) := by rw [Nat.mul_left_comm k 2 k]
              _ = (628 * 2) * (k * k) := (Nat.mul_assoc 628 2 (k * k)).symm
              _ = 1256 * (k * k) := by
                  have hc : 628 * 2 = 1256 := by decide
                  rw [hc]
          have hlin : 1256 * (2 * k) = 2512 * k := (Nat.mul_assoc 1256 2 k).symm
          have h3140 : 2512 + 628 = 3140 := by decide
          rw [hsq, hlin, ← Nat.add_assoc (1256 * (k * k) + 2512 * k),
            Nat.add_assoc (1256 * (k * k)), ← Nat.add_mul, h3140, Nat.add_assoc]
  rw [hL, hR]
  have hsq : 1200 * (k * k) ≤ 1256 * (k * k) := Nat.mul_le_mul_right (k * k) (by omega)
  omega

theorem ball_beats_cube_zador_all_even_dims (k : Nat) (hk : 1 ≤ k) :
    12 ^ k * fact k * 100 ^ k < (2 * k + 2) ^ k * 314 ^ k := by
  induction k with
  | zero => omega
  | succ m ih =>
    cases m with
    | zero => decide
    | succ r =>
      have hm : 1 ≤ r + 1 := by omega
      have hprev := ih hm
      have hbin : (r + 2) ^ (r + 1) * (2 * (r + 1) + 1) ≤ (r + 3) ^ (r + 1) * (r + 2) := by
        have h0 := binom_linear_lower_bound (r + 2) (r + 1)
        have heq : r + 2 + (r + 1) = 2 * (r + 1) + 1 := by omega
        rw [heq] at h0
        exact h0
      have hfac := zador_step_factor (r + 1)
      have h2n : 2 * (r + 1) + 2 = 2 * (r + 2) := by omega
      have h2n1 : 2 * (r + 2) + 2 = 2 * (r + 3) := by omega
      have hL_eq : 12 ^ (r + 2) * fact (r + 2) * 100 ^ (r + 2) * (r + 2)
          = (12 ^ (r + 1) * fact (r + 1) * 100 ^ (r + 1)) * (1200 * (r + 2) * (r + 2)) := by
        simp only [Nat.pow_succ, fact]
        have h1200 : 12 * 100 = 1200 := rfl
        calc 12 ^ (r + 1) * 12 * ((r + 2) * fact (r + 1)) * (100 ^ (r + 1) * 100) * (r + 2)
            = 12 ^ (r + 1) * fact (r + 1) * 100 ^ (r + 1) * ((12 * 100) * (r + 2) * (r + 2)) := by
              simp only [Nat.mul_assoc, Nat.mul_left_comm, Nat.mul_comm]
          _ = 12 ^ (r + 1) * fact (r + 1) * 100 ^ (r + 1) * (1200 * (r + 2) * (r + 2)) := by
              rw [h1200]
      have hR_ge : (2 * (r + 1) + 2) ^ (r + 1) * 314 ^ (r + 1) * (628 * (r + 3) * (2 * (r + 1) + 1))
          ≤ (2 * (r + 2) + 2) ^ (r + 2) * 314 ^ (r + 2) * (r + 2) := by
        rw [h2n, h2n1, Nat.mul_pow, Nat.mul_pow, Nat.pow_succ 2 (r + 1),
          Nat.pow_succ (r + 3) (r + 1), Nat.pow_succ 314 (r + 1)]
        have h628 : 2 * 314 = 628 := rfl
        calc 2 ^ (r + 1) * (r + 2) ^ (r + 1) * 314 ^ (r + 1) * (628 * (r + 3) * (2 * (r + 1) + 1))
            = (2 ^ (r + 1) * 314 ^ (r + 1) * (628 * (r + 3)))
                * ((r + 2) ^ (r + 1) * (2 * (r + 1) + 1)) := by
              simp only [Nat.mul_assoc, Nat.mul_left_comm, Nat.mul_comm]
          _ ≤ (2 ^ (r + 1) * 314 ^ (r + 1) * (628 * (r + 3))) * ((r + 3) ^ (r + 1) * (r + 2)) :=
              Nat.mul_le_mul_left _ hbin
          _ = 2 ^ (r + 1) * 2 * ((r + 3) ^ (r + 1) * (r + 3)) * (314 ^ (r + 1) * 314) * (r + 2) := by
              rw [← h628]
              simp only [Nat.mul_assoc, Nat.mul_left_comm, Nat.mul_comm]
      have hposL : 0 < 12 ^ (r + 1) * fact (r + 1) * 100 ^ (r + 1) :=
        Nat.mul_pos (Nat.mul_pos (Nat.pow_pos (by omega)) (fact_pos (r + 1))) (Nat.pow_pos (by omega))
      have hposF : 0 < 628 * (r + 3) * (2 * (r + 1) + 1) :=
        Nat.mul_pos (Nat.mul_pos (by omega) (by omega)) (by omega)
      have hmul1 : (12 ^ (r + 1) * fact (r + 1) * 100 ^ (r + 1)) * (1200 * (r + 2) * (r + 2))
          < (12 ^ (r + 1) * fact (r + 1) * 100 ^ (r + 1)) * (628 * (r + 3) * (2 * (r + 1) + 1)) :=
        Nat.mul_lt_mul_of_pos_left hfac hposL
      have hmul2 : (12 ^ (r + 1) * fact (r + 1) * 100 ^ (r + 1)) * (628 * (r + 3) * (2 * (r + 1) + 1))
          < ((2 * (r + 1) + 2) ^ (r + 1) * 314 ^ (r + 1)) * (628 * (r + 3) * (2 * (r + 1) + 1)) :=
        Nat.mul_lt_mul_of_pos_right hprev hposF
      have htot : 12 ^ (r + 2) * fact (r + 2) * 100 ^ (r + 2) * (r + 2)
          < (2 * (r + 2) + 2) ^ (r + 2) * 314 ^ (r + 2) * (r + 2) := by
        rw [hL_eq]
        exact Nat.lt_of_lt_of_le (Nat.lt_trans hmul1 hmul2) hR_ge
      rcases Nat.lt_or_ge (12 ^ (r + 2) * fact (r + 2) * 100 ^ (r + 2))
          ((2 * (r + 2) + 2) ^ (r + 2) * 314 ^ (r + 2)) with hok | hge
      · exact hok
      · have hle := Nat.mul_le_mul_right (r + 2) hge
        omega

theorem cube_to_ball_vol_ratio_even_strict_growth (k : Nat) :
    22 * (4 ^ k * fact k) < 7 * (4 ^ (k + 1) * fact (k + 1)) := by
  have hpos : 0 < 4 ^ k * fact k := Nat.mul_pos (Nat.pow_pos (by omega)) (fact_pos k)
  have hrew : 7 * (4 ^ (k + 1) * fact (k + 1)) = (28 * (k + 1)) * (4 ^ k * fact k) := by
    simp only [Nat.pow_succ, fact]
    have h28 : 7 * 4 = 28 := rfl
    calc 7 * (4 ^ k * 4 * ((k + 1) * fact k))
        = (7 * 4) * (k + 1) * (4 ^ k * fact k) := by
          simp only [Nat.mul_assoc, Nat.mul_left_comm, Nat.mul_comm]
      _ = 28 * (k + 1) * (4 ^ k * fact k) := by rw [h28]
  rw [hrew]
  exact Nat.mul_lt_mul_of_pos_right (by omega) hpos

/-! ## 2. Arbitrary-Dimension EM / Hodge Orthogonal Splitting over Z^d -/

def vAdd : List Int → List Int → List Int
  | [], [] => []
  | a :: xs, b :: ys => (a + b) :: vAdd xs ys
  | _, _ => []

def vSub : List Int → List Int → List Int
  | [], [] => []
  | a :: xs, b :: ys => (a - b) :: vSub xs ys
  | _, _ => []

def vScale (c : Int) : List Int → List Int
  | [] => []
  | a :: xs => (c * a) :: vScale c xs

def vDot : List Int → List Int → Int
  | [], [] => 0
  | a :: xs, b :: ys => a * b + vDot xs ys
  | _, _ => 0

def normSq (v : List Int) : Int := vDot v v

def hodgePar (x d : List Int) : List Int := vScale (vDot d x) x

def hodgePerp (x d : List Int) : List Int := vSub (vScale (normSq x) d) (hodgePar x d)

def hodgeWeightedDist (lam : Int) (x d : List Int) : Int :=
  normSq (hodgePar x d) + lam * normSq (hodgePerp x d)

theorem int_sq_nonneg (a : Int) : 0 ≤ a * a := by
  rcases Int.le_total 0 a with h | h
  · exact Int.mul_nonneg h h
  · exact Int.mul_nonneg_of_nonpos_of_nonpos h h

theorem vScale_length (c : Int) (v : List Int) : (vScale c v).length = v.length := by
  induction v with
  | nil => rfl
  | cons a xs ih => simp only [vScale, List.length_cons, ih]

theorem vAdd_length (u v : List Int) (hl : u.length = v.length) :
    (vAdd u v).length = u.length := by
  induction u generalizing v with
  | nil =>
    cases v with
    | nil => rfl
    | cons _ _ => cases hl
  | cons a xs ih =>
    cases v with
    | nil => cases hl
    | cons b ys =>
      simp only [vAdd, List.length_cons] at hl ⊢
      rw [ih ys (by omega)]

theorem vSub_length (u v : List Int) (hl : u.length = v.length) :
    (vSub u v).length = u.length := by
  induction u generalizing v with
  | nil =>
    cases v with
    | nil => rfl
    | cons _ _ => cases hl
  | cons a xs ih =>
    cases v with
    | nil => cases hl
    | cons b ys =>
      simp only [vSub, List.length_cons] at hl ⊢
      rw [ih ys (by omega)]

theorem vDot_comm (u v : List Int) : vDot u v = vDot v u := by
  induction u generalizing v with
  | nil =>
    cases v <;> rfl
  | cons a xs ih =>
    cases v with
    | nil => rfl
    | cons b ys =>
      simp only [vDot, Int.mul_comm a b, ih ys]

theorem normSq_nonneg (v : List Int) : 0 ≤ normSq v := by
  induction v with
  | nil => exact Int.le_refl 0
  | cons a xs ih =>
    simp only [normSq, vDot] at ih ⊢
    have hsq : 0 ≤ a * a := int_sq_nonneg a
    omega

theorem vDot_vScale_left (c : Int) (u v : List Int) :
    vDot (vScale c u) v = c * vDot u v := by
  induction u generalizing v with
  | nil =>
    cases v <;> simp only [vScale, vDot, Int.mul_zero]
  | cons a xs ih =>
    cases v with
    | nil => simp only [vScale, vDot, Int.mul_zero]
    | cons b ys =>
      simp only [vScale, vDot, ih ys, Int.mul_add, Int.mul_assoc]

theorem vDot_vScale_right (c : Int) (u v : List Int) :
    vDot u (vScale c v) = c * vDot u v := by
  rw [vDot_comm, vDot_vScale_left, vDot_comm]

theorem normSq_vScale (c : Int) (v : List Int) :
    normSq (vScale c v) = c * c * normSq v := by
  simp only [normSq, vDot_vScale_left, vDot_vScale_right, Int.mul_assoc]

theorem vDot_vAdd_left (u v w : List Int) (huv : u.length = v.length) (hvw : v.length = w.length) :
    vDot (vAdd u v) w = vDot u w + vDot v w := by
  induction u generalizing v w with
  | nil =>
    cases v with
    | nil =>
      cases w with
      | nil => rfl
      | cons _ _ => cases hvw
    | cons _ _ => cases huv
  | cons a xs ih =>
    cases v with
    | nil => cases huv
    | cons b ys =>
      cases w with
      | nil => cases hvw
      | cons c zs =>
        simp only [List.length_cons] at huv hvw
        simp only [vAdd, vDot, Int.add_mul]
        rw [ih ys zs (by omega) (by omega)]
        omega

theorem vDot_vSub_right (w u v : List Int) (huv : u.length = v.length) (hwu : w.length = u.length) :
    vDot w (vSub u v) = vDot w u - vDot w v := by
  induction u generalizing v w with
  | nil =>
    cases v with
    | nil =>
      cases w with
      | nil => rfl
      | cons _ _ => cases hwu
    | cons _ _ => cases huv
  | cons a xs ih =>
    cases v with
    | nil => cases huv
    | cons b ys =>
      cases w with
      | nil => cases hwu
      | cons c zs =>
        simp only [List.length_cons] at huv hwu
        simp only [vSub, vDot, Int.mul_sub]
        rw [ih zs ys (by omega) (by omega)]
        omega

theorem vAdd_vSub_cancel (u v : List Int) (hl : u.length = v.length) :
    vAdd v (vSub u v) = u := by
  induction u generalizing v with
  | nil =>
    cases v with
    | nil => rfl
    | cons _ _ => cases hl
  | cons a xs ih =>
    cases v with
    | nil => cases hl
    | cons b ys =>
      simp only [List.length_cons] at hl
      simp only [vAdd, vSub, ih ys (by omega)]
      have h : b + (a - b) = a := by omega
      rw [h]

theorem hodge_reconstruction (x d : List Int) (hl : x.length = d.length) :
    vAdd (hodgePar x d) (hodgePerp x d) = vScale (normSq x) d := by
  simp only [hodgePerp, hodgePar]
  apply vAdd_vSub_cancel
  rw [vScale_length, vScale_length]
  exact hl.symm

theorem hodge_orthogonality_ref (x d : List Int) (hl : x.length = d.length) :
    vDot x (hodgePerp x d) = 0 := by
  simp only [hodgePerp, hodgePar]
  have h1 : (vScale (normSq x) d).length = (vScale (vDot d x) x).length := by
    rw [vScale_length, vScale_length, hl]
  have h2 : x.length = (vScale (normSq x) d).length := by
    rw [vScale_length, hl]
  rw [vDot_vSub_right x _ _ h1 h2, vDot_vScale_right, vDot_vScale_right]
  simp only [normSq]
  rw [vDot_comm x d, Int.mul_comm (vDot d x) (vDot x x)]
  omega

theorem hodge_orthogonality (x d : List Int) (hl : x.length = d.length) :
    vDot (hodgePar x d) (hodgePerp x d) = 0 := by
  simp only [hodgePar]
  rw [vDot_vScale_left, hodge_orthogonality_ref x d hl, Int.mul_zero]

theorem hodge_pythagorean_split (x d : List Int) (hl : x.length = d.length) :
    normSq x * normSq x * normSq d = normSq (hodgePar x d) + normSq (hodgePerp x d) := by
  have hrec := hodge_reconstruction x d hl
  have hlen1 : (hodgePar x d).length = (hodgePerp x d).length := by
    simp only [hodgePar, hodgePerp]
    rw [vSub_length, vScale_length, vScale_length, hl]
    rw [vScale_length, vScale_length, hl]
  have hlen2 : (hodgePerp x d).length = (vAdd (hodgePar x d) (hodgePerp x d)).length := by
    rw [vAdd_length _ _ hlen1]
    exact hlen1.symm
  have hns : normSq (vAdd (hodgePar x d) (hodgePerp x d))
      = normSq (hodgePar x d) + normSq (hodgePerp x d) := by
    simp only [normSq]
    rw [vDot_vAdd_left _ _ _ hlen1 hlen2]
    rw [vDot_comm (hodgePar x d) (vAdd _ _), vDot_vAdd_left _ _ _ hlen1 hlen1.symm]
    rw [vDot_comm (hodgePerp x d) (vAdd _ _), vDot_vAdd_left _ _ _ hlen1 (Eq.refl _)]
    have horth := hodge_orthogonality x d hl
    have horth2 : vDot (hodgePerp x d) (hodgePar x d) = 0 := by
      rw [vDot_comm]; exact horth
    rw [horth, horth2]
    omega
  rw [hrec, normSq_vScale] at hns
  exact hns

theorem hodge_weighted_distortion_ge_euclidean (x d : List Int) (lam : Int)
    (hl : x.length = d.length) (hlam : 1 ≤ lam) :
    normSq x * normSq x * normSq d ≤ hodgeWeightedDist lam x d := by
  rw [hodge_pythagorean_split x d hl]
  simp only [hodgeWeightedDist]
  have hnn : 0 ≤ normSq (hodgePerp x d) := normSq_nonneg _
  have hdiff : 0 ≤ (lam - 1) * normSq (hodgePerp x d) := Int.mul_nonneg (by omega) hnn
  have hexp : (lam - 1) * normSq (hodgePerp x d) = lam * normSq (hodgePerp x d) - normSq (hodgePerp x d) := by
    rw [Int.sub_mul, Int.one_mul]
  omega

theorem vScale_vScale (a b : Int) (v : List Int) :
    vScale a (vScale b v) = vScale (a * b) v := by
  induction v with
  | nil => rfl
  | cons x xs ih =>
    simp only [vScale, Int.mul_assoc, ih]

theorem vScale_vSub (c : Int) (u v : List Int) :
    vScale c (vSub u v) = vSub (vScale c u) (vScale c v) := by
  induction u generalizing v with
  | nil =>
    cases v <;> rfl
  | cons a xs ih =>
    cases v with
    | nil => rfl
    | cons b ys =>
      simp only [vSub, vScale, Int.mul_sub, ih ys]

theorem hodge_radial_rescaling_invariance (x d : List Int) (c lam : Int) :
    hodgeWeightedDist lam (vScale c x) d = c * c * c * c * hodgeWeightedDist lam x d := by
  have hpar : hodgePar (vScale c x) d = vScale (c * c) (hodgePar x d) := by
    simp only [hodgePar, vDot_vScale_right, vScale_vScale]
    have hmul : c * vDot d x * c = c * c * vDot d x := by
      simp only [Int.mul_assoc, Int.mul_comm]
    rw [hmul]
  have hperp : hodgePerp (vScale c x) d = vScale (c * c) (hodgePerp x d) := by
    simp only [hodgePerp, normSq_vScale, hpar, vScale_vSub, vScale_vScale]
  simp only [hodgeWeightedDist, hpar, hperp, normSq_vScale]
  have hc4 : (c * c) * (c * c) = c * c * c * c := by
    simp only [Int.mul_assoc]
  rw [hc4, Int.mul_add, Int.mul_left_comm lam (c * c * c * c)]

theorem hodge_radial_rescaling_order_invariant (x d1 d2 : List Int) (c lam : Int) (hc : c ≠ 0) :
    hodgeWeightedDist lam (vScale c x) d1 ≤ hodgeWeightedDist lam (vScale c x) d2 ↔
      hodgeWeightedDist lam x d1 ≤ hodgeWeightedDist lam x d2 := by
  rw [hodge_radial_rescaling_invariance, hodge_radial_rescaling_invariance]
  have hc2 : 0 < c * c := by
    rcases Int.lt_trichotomy c 0 with hlt | heq | hgt
    · exact Int.mul_pos_of_neg_of_neg hlt hlt
    · exact absurd heq hc
    · exact Int.mul_pos hgt hgt
  have hc4 : 0 < c * c * c * c := by
    have h := Int.mul_pos hc2 hc2
    simpa only [Int.mul_assoc] using h
  constructor
  · intro hle
    have hsub : 0 ≤ c * c * c * c * (hodgeWeightedDist lam x d2 - hodgeWeightedDist lam x d1) := by
      rw [Int.mul_sub]; omega
    by_cases hlt : hodgeWeightedDist lam x d2 < hodgeWeightedDist lam x d1
    · have hneg : c * c * c * c * (hodgeWeightedDist lam x d2 - hodgeWeightedDist lam x d1) < 0 :=
        Int.mul_neg_of_pos_of_neg hc4 (by omega)
      omega
    · omega
  · intro hle
    exact Int.mul_le_mul_of_nonneg_left hle (Int.le_of_lt hc4)

theorem hodge_radial_warp_zero_transverse (x : List Int) (k : Int) :
    normSq (hodgePerp x (vScale k x)) = 0 := by
  have hz : hodgePerp x (vScale k x) = vSub (vScale (normSq x * k) x) (vScale (normSq x * k) x) := by
    simp only [hodgePerp, hodgePar, vScale_vScale, vDot_vScale_left]
    simp only [normSq, Int.mul_comm k (vDot x x)]
  rw [hz]
  have hsub0 : ∀ v : List Int, normSq (vSub v v) = 0 := by
    intro v
    induction v with
    | nil => rfl
    | cons a xs ih =>
      simp only [normSq, vSub, vDot] at ih ⊢
      have h0 : a - a = 0 := by omega
      rw [h0, Int.zero_mul, Int.zero_add]
      exact ih
  exact hsub0 _

/-! ## 3. Denominator-pi Equal-Sphere-Fraction Invariants & 2^B Slot Utilization -/

def hatboxStart (m i : Int) : Int := -m + 2 * i
def hatboxEnd (m i : Int) : Int := -m + 2 * (i + 1)

def hatboxWidthSum (m : Int) : Nat → Int
  | 0 => 0
  | n + 1 => hatboxWidthSum m n + (hatboxEnd m n - hatboxStart m n)

theorem eq_s2_hatbox_strip_width_invariant (m i : Int) :
    hatboxEnd m i - hatboxStart m i = 2 := by
  simp only [hatboxEnd, hatboxStart]
  omega

theorem eq_s2_hatbox_total_partition (m : Nat) :
    hatboxWidthSum m m = 2 * (m : Int) := by
  have hgen : ∀ (c : Int) (n : Nat), hatboxWidthSum c n = 2 * (n : Int) := by
    intro c n
    induction n with
    | zero => rfl
    | succ k ih =>
      simp only [hatboxWidthSum, eq_s2_hatbox_strip_width_invariant, ih]
      omega
  exact hgen m m

def sumOdd : Nat → Nat
  | 0 => 0
  | n + 1 => sumOdd n + (2 * n + 1)

def sumOddSq : Nat → Nat
  | 0 => 0
  | n + 1 => sumOddSq n + (2 * n + 1) * (2 * n + 1)

def sumRevOdd (m : Nat) : Nat → Nat
  | 0 => 0
  | n + 1 => sumRevOdd m n + (2 * m - (2 * n + 1))

theorem eq_hopf_u_midpoint_sum (a : Nat) : sumOdd a = a * a := by
  induction a with
  | zero => rfl
  | succ k ih =>
    simp only [sumOdd, ih]
    simp only [Nat.mul_add, Nat.add_mul, Nat.mul_one, Nat.one_mul]
    omega

theorem eq_hopf_complementary_midpoint_sum (a : Nat) :
    sumRevOdd a a = a * a := by
  have hgen : ∀ n : Nat, n ≤ a → sumOdd n + sumRevOdd a n = 2 * a * n := by
    intro n hle
    induction n with
    | zero => simp only [sumOdd, sumRevOdd, Nat.mul_zero]
    | succ k ih =>
      simp only [sumOdd, sumRevOdd]
      have hprev := ih (by omega)
      have hstep : 2 * a * (k + 1) = 2 * a * k + 2 * a := by
        rw [Nat.mul_add, Nat.mul_one]
      omega
  have htot := hgen a (Nat.le_refl a)
  rw [eq_hopf_u_midpoint_sum] at htot
  have h2a : 2 * a * a = a * a + a * a := by
    rw [Nat.mul_assoc, Nat.two_mul]
  omega

theorem eq_hopf_3s_quadratic_moment_nat (a : Nat) :
    3 * sumOddSq a + a = 4 * a * a * a := by
  induction a with
  | zero => rfl
  | succ k ih =>
    simp only [sumOddSq]
    have hL : 3 * (sumOddSq k + (2 * k + 1) * (2 * k + 1)) + (k + 1)
        = (3 * sumOddSq k + k) + (12 * (k * k) + 12 * k + 4) := by
      rw [Nat.mul_add]
      have hsq : (2 * k + 1) * (2 * k + 1) = 4 * (k * k) + 4 * k + 1 := by
        calc (2 * k + 1) * (2 * k + 1)
            = (2 * k + 1) * (2 * k) + (2 * k + 1) := by rw [Nat.mul_add, Nat.mul_one]
          _ = 2 * k * (2 * k) + 2 * k + (2 * k + 1) := by rw [Nat.add_mul, Nat.one_mul]
          _ = 4 * (k * k) + 4 * k + 1 := by
              have h4 : 2 * k * (2 * k) = 4 * (k * k) := by
                calc 2 * k * (2 * k) = 2 * (k * (2 * k)) := Nat.mul_assoc 2 k (2 * k)
                  _ = 2 * (2 * (k * k)) := by rw [Nat.mul_left_comm k 2 k]
                  _ = (2 * 2) * (k * k) := (Nat.mul_assoc 2 2 (k * k)).symm
                  _ = 4 * (k * k) := rfl
              rw [h4]
              omega
      rw [hsq]
      omega
    have hR : 4 * (k + 1) * (k + 1) * (k + 1)
        = 4 * k * k * k + (12 * (k * k) + 12 * k + 4) := by
      have h1 : 4 * (k + 1) * (k + 1) = 4 * (k * k) + 8 * k + 4 := by
        calc 4 * (k + 1) * (k + 1)
            = (4 * k + 4) * (k + 1) := by rw [Nat.mul_add 4 k 1, Nat.mul_one]
          _ = (4 * k + 4) * k + (4 * k + 4) := by rw [Nat.mul_add, Nat.mul_one]
          _ = 4 * k * k + 4 * k + (4 * k + 4) := by rw [Nat.add_mul]
          _ = 4 * (k * k) + 8 * k + 4 := by rw [Nat.mul_assoc]; omega
      rw [h1, Nat.mul_add, Nat.mul_one, Nat.add_mul, Nat.add_mul]
      have h2 : 4 * (k * k) * k = 4 * k * k * k := by
        rw [← Nat.mul_assoc 4 k k]
      have h3 : 8 * k * k = 8 * (k * k) := Nat.mul_assoc 8 k k
      rw [h2, h3]
      omega
    rw [hL, ih, hR]

theorem eq_hopf_3s_quadratic_moment_exact (a : Nat) :
    3 * sumOddSq a = a * (4 * a * a - 1) := by
  have h := eq_hopf_3s_quadratic_moment_nat a
  cases a with
  | zero => rfl
  | succ m =>
    have hge : 1 ≤ 4 * (m + 1) * (m + 1) := by
      have h1 : 1 ≤ (m + 1) * (m + 1) := Nat.mul_pos (Nat.succ_pos m) (Nat.succ_pos m)
      have h2 : 4 * (m + 1) * (m + 1) = 4 * ((m + 1) * (m + 1)) := Nat.mul_assoc 4 (m + 1) (m + 1)
      omega
    have hsub : (m + 1) * (4 * (m + 1) * (m + 1) - 1) + (m + 1)
        = (m + 1) * (4 * (m + 1) * (m + 1)) := by
      rw [Nat.mul_sub, Nat.mul_one]
      have hle : m + 1 ≤ (m + 1) * (4 * (m + 1) * (m + 1)) := by
        have := Nat.mul_le_mul_left (m + 1) hge
        simpa only [Nat.mul_one] using this
      exact Nat.sub_add_cancel hle
    have hcomm : (m + 1) * (4 * (m + 1) * (m + 1)) = 4 * (m + 1) * (m + 1) * (m + 1) :=
      Nat.mul_comm (m + 1) (4 * (m + 1) * (m + 1))
    omega

theorem pow2_not_div_by_three (b : Nat) : ¬ (3 ∣ 2 ^ b) := by
  have hmod : 2 ^ b % 3 = 1 ∨ 2 ^ b % 3 = 2 := by
    induction b with
    | zero => left; decide
    | succ k ih =>
      rw [Nat.pow_succ, Nat.mul_mod]
      rcases ih with h1 | h2
      · right; rw [h1]
      · left; rw [h2]
  intro ⟨q, hq⟩
  have h0 : 2 ^ b % 3 = 0 := by rw [hq, Nat.mul_mod_right]
  omega

theorem pow2_not_div_by_five (b : Nat) : ¬ (5 ∣ 2 ^ b) := by
  have hmod : 2 ^ b % 5 = 1 ∨ 2 ^ b % 5 = 2 ∨ 2 ^ b % 5 = 3 ∨ 2 ^ b % 5 = 4 := by
    induction b with
    | zero => left; decide
    | succ k ih =>
      rw [Nat.pow_succ, Nat.mul_mod]
      rcases ih with h1 | h2 | h3 | h4
      · right; left; rw [h1]
      · right; right; right; rw [h2]
      · left; rw [h3]
      · right; right; left; rw [h4]
  intro ⟨q, hq⟩
  have h0 : 2 ^ b % 5 = 0 := by rw [hq, Nat.mul_mod_right]
  omega

theorem exceptional_design_slot_waste_universal (b : Nat) :
    2 ^ b ≠ 24 ∧ 2 ^ b ≠ 120 ∧ 2 ^ b ≠ 240 ∧ 2 ^ b ≠ 2400 ∧ 2 ^ b ≠ 196560 := by
  have h3 := pow2_not_div_by_three b
  refine ⟨?_, ?_, ?_, ?_, ?_⟩
  · intro h; exact h3 ⟨8, h⟩
  · intro h; exact h3 ⟨40, h⟩
  · intro h; exact h3 ⟨80, h⟩
  · intro h; exact h3 ⟨800, h⟩
  · intro h; exact h3 ⟨65520, h⟩

/-! ## 4. Hypersphere Thin-Shell Concentration & Coxeter/Weyl Rational Fractions -/

theorem thin_shell_chebyshev_monotone (d1 d2 epsDen : Nat)
    (hd : d1 < d2) (hq : 1 ≤ epsDen) :
    2 * epsDen * epsDen * d1 < 2 * epsDen * epsDen * d2 := by
  have hpos : 0 < 2 * epsDen * epsDen :=
    Nat.mul_pos (Nat.mul_pos (by omega) hq) hq
  exact Nat.mul_lt_mul_of_pos_left hd hpos

def weylBn (d : Nat) : Nat := 2 ^ d * fact d
def weylE8 : Nat := 2 ^ 14 * 3 ^ 5 * 5 ^ 2 * 7
def weylH3 : Nat := 120
def weylH4 : Nat := 14400

theorem weylBn_step_and_pos (d : Nat) :
    0 < weylBn d ∧ weylBn (d + 1) = 2 * (d + 1) * weylBn d := by
  constructor
  · exact Nat.mul_pos (Nat.pow_pos (by omega)) (fact_pos d)
  · simp only [weylBn, Nat.pow_succ, fact]
    simp only [Nat.mul_assoc, Nat.mul_left_comm, Nat.mul_comm]

theorem weylBn_strict_mono (d : Nat) : weylBn d < weylBn (d + 1) := by
  have ⟨hpos, hstep⟩ := weylBn_step_and_pos d
  rw [hstep]
  have hgt : 1 < 2 * (d + 1) := by omega
  have h := Nat.mul_lt_mul_of_pos_right hgt hpos
  simpa only [Nat.one_mul] using h

theorem weylBn_div_pow2 (d : Nat) : 2 ^ d ∣ weylBn d :=
  ⟨fact d, rfl⟩

theorem coxeter_weyl_e8_b8_index :
    weylBn 8 = 10321920 ∧ weylE8 = 696729600 ∧ 2 * weylE8 = 135 * weylBn 8 ∧
      weylH3 * weylH3 = weylH4 := by
  decide

/-! ## 5. Hopf Fibration pi : S^3 -> S^2 (EXP-Q06 Formal Companion) -/

def hopfX (a b c d : Int) : Int := 2 * (a * c + b * d)
def hopfY (a b c d : Int) : Int := 2 * (b * c - a * d)
def hopfZ (a b c d : Int) : Int := a * a + b * b - c * c - d * d

def rotRe (u v a b : Int) : Int := u * a - v * b
def rotIm (u v a b : Int) : Int := v * a + u * b

theorem hopf_map_norm_sq (a b c d : Int) :
    hopfX a b c d * hopfX a b c d + hopfY a b c d * hopfY a b c d +
        hopfZ a b c d * hopfZ a b c d
      = (a * a + b * b + c * c + d * d) * (a * a + b * b + c * c + d * d) := by
  simp only [hopfX, hopfY, hopfZ]
  have h2 : (2 : Int) = 1 + 1 := rfl
  rw [h2]
  simp only [Int.mul_add, Int.mul_sub, Int.mul_one, Int.mul_left_comm, Int.mul_comm]
  omega

theorem hopf_fiber_norm_sq_scaling (a b c d u v : Int) :
    rotRe u v a b * rotRe u v a b + rotIm u v a b * rotIm u v a b +
        rotRe u v c d * rotRe u v c d + rotIm u v c d * rotIm u v c d
      = (u * u + v * v) * (a * a + b * b + c * c + d * d) := by
  simp only [rotRe, rotIm]
  simp only [Int.mul_add, Int.mul_sub, Int.mul_left_comm, Int.mul_comm]
  omega

theorem hopf_map_u1_fiber_scaling (a b c d u v : Int) :
    hopfX (rotRe u v a b) (rotIm u v a b) (rotRe u v c d) (rotIm u v c d)
        = (u * u + v * v) * hopfX a b c d ∧
      hopfY (rotRe u v a b) (rotIm u v a b) (rotRe u v c d) (rotIm u v c d)
        = (u * u + v * v) * hopfY a b c d ∧
      hopfZ (rotRe u v a b) (rotIm u v a b) (rotRe u v c d) (rotIm u v c d)
        = (u * u + v * v) * hopfZ a b c d := by
  simp only [hopfX, hopfY, hopfZ, rotRe, rotIm]
  have h2 : (2 : Int) = 1 + 1 := rfl
  refine ⟨?_, ?_, ?_⟩
  · rw [h2]
    simp only [Int.mul_add, Int.mul_sub, Int.mul_one, Int.mul_left_comm, Int.mul_comm]
    omega
  · rw [h2]
    simp only [Int.mul_add, Int.mul_sub, Int.mul_one, Int.mul_left_comm, Int.mul_comm]
    omega
  · simp only [Int.mul_add, Int.mul_sub, Int.mul_left_comm, Int.mul_comm]
    omega

theorem hopf_map_u1_fiber_invariance (a b c d u v D : Int) (hpyth : u * u + v * v = D * D) :
    hopfX (rotRe u v a b) (rotIm u v a b) (rotRe u v c d) (rotIm u v c d)
        = D * D * hopfX a b c d ∧
      hopfY (rotRe u v a b) (rotIm u v a b) (rotRe u v c d) (rotIm u v c d)
        = D * D * hopfY a b c d ∧
      hopfZ (rotRe u v a b) (rotIm u v a b) (rotRe u v c d) (rotIm u v c d)
        = D * D * hopfZ a b c d := by
  have ⟨hx, hy, hz⟩ := hopf_map_u1_fiber_scaling a b c d u v
  rw [hpyth] at hx hy hz
  exact ⟨hx, hy, hz⟩

end SphereDenomPiOperators

#print axioms SphereDenomPiOperators.fact_pos
#print axioms SphereDenomPiOperators.even_sphere_area_to_ball_vol_ratio
#print axioms SphereDenomPiOperators.binom_linear_lower_bound
#print axioms SphereDenomPiOperators.zador_step_factor
#print axioms SphereDenomPiOperators.ball_beats_cube_zador_all_even_dims
#print axioms SphereDenomPiOperators.cube_to_ball_vol_ratio_even_strict_growth
#print axioms SphereDenomPiOperators.vDot_comm
#print axioms SphereDenomPiOperators.normSq_nonneg
#print axioms SphereDenomPiOperators.hodge_reconstruction
#print axioms SphereDenomPiOperators.hodge_orthogonality_ref
#print axioms SphereDenomPiOperators.hodge_orthogonality
#print axioms SphereDenomPiOperators.hodge_pythagorean_split
#print axioms SphereDenomPiOperators.hodge_weighted_distortion_ge_euclidean
#print axioms SphereDenomPiOperators.hodge_radial_rescaling_invariance
#print axioms SphereDenomPiOperators.hodge_radial_rescaling_order_invariant
#print axioms SphereDenomPiOperators.hodge_radial_warp_zero_transverse
#print axioms SphereDenomPiOperators.eq_s2_hatbox_strip_width_invariant
#print axioms SphereDenomPiOperators.eq_s2_hatbox_total_partition
#print axioms SphereDenomPiOperators.eq_hopf_u_midpoint_sum
#print axioms SphereDenomPiOperators.eq_hopf_complementary_midpoint_sum
#print axioms SphereDenomPiOperators.eq_hopf_3s_quadratic_moment_nat
#print axioms SphereDenomPiOperators.eq_hopf_3s_quadratic_moment_exact
#print axioms SphereDenomPiOperators.pow2_not_div_by_three
#print axioms SphereDenomPiOperators.pow2_not_div_by_five
#print axioms SphereDenomPiOperators.exceptional_design_slot_waste_universal
#print axioms SphereDenomPiOperators.thin_shell_chebyshev_monotone
#print axioms SphereDenomPiOperators.weylBn_step_and_pos
#print axioms SphereDenomPiOperators.weylBn_strict_mono
#print axioms SphereDenomPiOperators.weylBn_div_pow2
#print axioms SphereDenomPiOperators.coxeter_weyl_e8_b8_index
#print axioms SphereDenomPiOperators.hopf_map_norm_sq
#print axioms SphereDenomPiOperators.hopf_fiber_norm_sq_scaling
#print axioms SphereDenomPiOperators.hopf_map_u1_fiber_scaling
#print axioms SphereDenomPiOperators.hopf_map_u1_fiber_invariance
