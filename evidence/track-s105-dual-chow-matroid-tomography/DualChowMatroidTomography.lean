/-
  DualChowMatroidTomography

  Pure `Init` Lean 4 development over the integers ℤ (no imports, no Mathlib).
  Polynomials are little-endian `List Int` (index i is the coefficient of x^i).
  All statements are polynomial identities or integer inequalities over ℤ.
  The corresponding real-rootedness / root-location statements over ℝ follow
  from the very same identities (sum-of-squares certificates, Taylor shifts),
  but the real-number versions are NOT formalized here.

  Contents:
  * computable polynomial arithmetic: evalP, addP, scaleP, negP, mulP, shiftP
  * evaluation homomorphism lemmas and the Taylor-shift evaluation lemma
  * positivity from coefficient signs (and from shifted coefficient signs)
  * discriminant / sum-of-squares positivity for quadratics and the dual Chow
    (gamma-expanded) quartic, root location of the augmented quintic/sextic
  * rank-four factorization and discriminant identity
  * Gaussian q-binomials gaussQ and basic facts
-/

namespace DualChowMatroidTomography

/-! ## Polynomial arithmetic on little-endian coefficient lists -/

/-- Horner evaluation. -/
def evalP : List Int → Int → Int
  | [], _ => 0
  | c :: cs, x => c + x * evalP cs x

/-- Pointwise sum; the longer tail is kept. -/
def addP : List Int → List Int → List Int
  | [], r => r
  | a :: as, [] => a :: as
  | a :: as, b :: bs => (a + b) :: addP as bs

/-- Scalar multiple. -/
def scaleP (k : Int) : List Int → List Int
  | [] => []
  | c :: cs => (k * c) :: scaleP k cs

/-- Negation. -/
def negP : List Int → List Int
  | [] => []
  | c :: cs => (-c) :: negP cs

/-- Convolution product. -/
def mulP : List Int → List Int → List Int
  | [], _ => []
  | c :: cs, r => addP (scaleP c r) (0 :: mulP cs r)

/-- Taylor shift: the coefficient list of p(x + a), computed by Horner. -/
def shiftP : List Int → Int → List Int
  | [], _ => []
  | c :: cs, a => addP [c] (mulP [a, 1] (shiftP cs a))

/-! ## Evaluation lemmas -/

theorem evalP_addP (p r : List Int) (x : Int) :
    evalP (addP p r) x = evalP p x + evalP r x := by
  induction p generalizing r with
  | nil => simp only [addP, evalP]; omega
  | cons a as ih =>
    cases r with
    | nil => simp only [addP, evalP]; omega
    | cons b bs =>
      simp only [addP, evalP]
      rw [ih bs, Int.mul_add]
      omega

theorem evalP_scaleP (k : Int) (p : List Int) (x : Int) :
    evalP (scaleP k p) x = k * evalP p x := by
  induction p with
  | nil => simp only [scaleP, evalP, Int.mul_zero]
  | cons c cs ih =>
    simp only [scaleP, evalP]
    rw [ih, Int.mul_add, Int.mul_left_comm]

theorem evalP_negP (p : List Int) (x : Int) :
    evalP (negP p) x = - evalP p x := by
  induction p with
  | nil => simp only [negP, evalP]; omega
  | cons c cs ih =>
    simp only [negP, evalP]
    rw [ih, Int.mul_neg]
    omega

theorem evalP_mulP (p r : List Int) (x : Int) :
    evalP (mulP p r) x = evalP p x * evalP r x := by
  induction p with
  | nil => simp only [mulP, evalP, Int.zero_mul]
  | cons c cs ih =>
    simp only [mulP]
    rw [evalP_addP, evalP_scaleP]
    simp only [evalP]
    rw [ih, Int.add_mul, Int.mul_assoc]
    omega

theorem evalP_shiftP (p : List Int) (a x : Int) :
    evalP (shiftP p a) x = evalP p (x + a) := by
  induction p with
  | nil => simp only [shiftP, evalP]
  | cons c cs ih =>
    simp only [shiftP]
    rw [evalP_addP, evalP_mulP, ih]
    simp only [evalP]
    rw [Int.mul_zero, Int.add_zero, Int.add_zero, Int.mul_one, Int.add_comm a x]

/-! ## Positivity from coefficient signs -/

theorem evalP_nonneg_of_coeffs_nonneg (p : List Int) (x : Int)
    (hp : ∀ c ∈ p, 0 ≤ c) (hx : 0 ≤ x) : 0 ≤ evalP p x := by
  induction p with
  | nil => simp only [evalP]; omega
  | cons c cs ih =>
    simp only [evalP]
    have hc : 0 ≤ c := hp c (List.mem_cons.mpr (Or.inl rfl))
    have hcs : 0 ≤ evalP cs x :=
      ih (fun d hd => hp d (List.mem_cons.mpr (Or.inr hd)))
    have hm : 0 ≤ x * evalP cs x := Int.mul_nonneg hx hcs
    omega

theorem evalP_pos_of_coeffs_pos (p : List Int) (x : Int)
    (hp : ∀ c ∈ p, 0 < c) (hne : p ≠ []) (hx : 0 ≤ x) : 0 < evalP p x := by
  cases p with
  | nil => exact absurd rfl hne
  | cons c cs =>
    simp only [evalP]
    have hc : 0 < c := hp c (List.mem_cons.mpr (Or.inl rfl))
    have hcs : 0 ≤ evalP cs x :=
      evalP_nonneg_of_coeffs_nonneg cs x
        (fun d hd => Int.le_of_lt (hp d (List.mem_cons.mpr (Or.inr hd)))) hx
    have hm : 0 ≤ x * evalP cs x := Int.mul_nonneg hx hcs
    omega

theorem neg_of_shifted_neg_coeffs_pos (p : List Int) (a : Int)
    (hp : ∀ c ∈ shiftP (negP p) a, 0 < c) (hne : shiftP (negP p) a ≠ []) :
    ∀ q, a ≤ q → evalP p q < 0 := by
  intro q hq
  have hx : 0 ≤ q - a := by omega
  have hpos := evalP_pos_of_coeffs_pos (shiftP (negP p) a) (q - a) hp hne hx
  rw [evalP_shiftP, Int.sub_add_cancel, evalP_negP] at hpos
  omega

/-! ## Sum-of-squares certificates -/

theorem sq_nonneg' (a : Int) : 0 ≤ a * a := by
  cases Int.le_total 0 a with
  | inl h => exact Int.mul_nonneg h h
  | inr h =>
    have h' : 0 ≤ -a := by omega
    have := Int.mul_nonneg h' h'
    rw [Int.neg_mul_neg] at this
    exact this

theorem sq_pos_of_ne_zero (a : Int) (h : a ≠ 0) : 0 < a * a := by
  cases Int.lt_or_gt_of_ne h with
  | inl hl =>
    have h' : 0 < -a := by omega
    have := Int.mul_pos h' h'
    rw [Int.neg_mul_neg] at this
    exact this
  | inr hr => exact Int.mul_pos hr hr

theorem pos_of_mul_pos_left (a b : Int) (ha : 0 < a) (h : 0 < a * b) : 0 < b := by
  have h0 : a * 0 < a * b := by rw [Int.mul_zero]; exact h
  exact Int.lt_of_mul_lt_mul_left h0 (Int.le_of_lt ha)

theorem quad_sos_identity (a b c x : Int) :
    4 * a * (a * x * x + b * x + c)
      = (2 * a * x + b) * (2 * a * x + b) + (4 * a * c - b * b) := by
  have h4 : (4:Int) = 1 + 1 + 1 + 1 := rfl
  have h2 : (2:Int) = 1 + 1 := rfl
  rw [h4, h2]
  simp only [Int.mul_add, Int.mul_one, Int.mul_comm, Int.mul_left_comm]
  omega

theorem quad_pos_of_neg_disc (a b c : Int) (ha : 0 < a) (hd : b * b < 4 * a * c) :
    ∀ x, 0 < a * x * x + b * x + c := by
  intro x
  have key := quad_sos_identity a b c x
  have hs := sq_nonneg' (2 * a * x + b)
  have h4 : 0 < 4 * a * (a * x * x + b * x + c) := by omega
  have h4a : 0 < 4 * a := by omega
  exact pos_of_mul_pos_left (4 * a) _ h4a h4

theorem quartic_sos_identity (g0 g1 g2 x y : Int) :
    4 * g0 * (g0 * (y * y * y * y) + g1 * x * (y * y) + g2 * (x * x))
      = (2 * g0 * (y * y) + g1 * x) * (2 * g0 * (y * y) + g1 * x)
        + (4 * g0 * g2 - g1 * g1) * (x * x) := by
  have h4 : (4:Int) = 1 + 1 + 1 + 1 := rfl
  have h2 : (2:Int) = 1 + 1 := rfl
  rw [h4, h2]
  simp only [Int.mul_add, Int.mul_sub, Int.mul_one, Int.mul_comm, Int.mul_left_comm]
  omega

theorem dual_chow_quartic_pos (g0 g1 g2 : Int) (h0 : 0 < g0)
    (hd : g1 * g1 < 4 * g0 * g2) :
    ∀ x, 0 < g0 * ((1 + x) * (1 + x) * (1 + x) * (1 + x))
              + g1 * x * ((1 + x) * (1 + x)) + g2 * (x * x) := by
  intro x
  cases Decidable.em (x = 0) with
  | inl hx =>
    subst hx
    simp only [Int.add_zero, Int.mul_one, Int.mul_zero]
    exact h0
  | inr hx =>
    have key := quartic_sos_identity g0 g1 g2 x (1 + x)
    have hs := sq_nonneg' (2 * g0 * ((1 + x) * (1 + x)) + g1 * x)
    have hxx := sq_pos_of_ne_zero x hx
    have hdpos : 0 < 4 * g0 * g2 - g1 * g1 := by omega
    have hprod := Int.mul_pos hdpos hxx
    have h4a : 0 < 4 * g0 := by omega
    apply pos_of_mul_pos_left (4 * g0) _ h4a
    omega

theorem dual_aug_quintic_root_only_neg_one (h0 h1 h2 x : Int) (hh0 : 0 < h0)
    (hd : h1 * h1 < 4 * h0 * h2)
    (hz : (1 + x) * (h0 * ((1 + x) * (1 + x) * (1 + x) * (1 + x))
              + h1 * x * ((1 + x) * (1 + x)) + h2 * (x * x)) = 0) :
    x = -1 := by
  have hpos := dual_chow_quartic_pos h0 h1 h2 hh0 hd x
  cases Int.mul_eq_zero.mp hz with
  | inl h => omega
  | inr h => omega

/-! ## Rank-four and gamma-vector identities -/

theorem rank_four_factorization (g0 g1 x : Int) :
    g0 * ((1 + x) * (1 + x) * (1 + x)) + g1 * x * (1 + x)
      = (1 + x) * (g0 * x * x + (2 * g0 + g1) * x + g0) := by
  have h2 : (2:Int) = 1 + 1 := rfl
  rw [h2]
  simp only [Int.mul_add, Int.mul_one, Int.mul_comm, Int.mul_left_comm]
  omega

theorem rank_four_disc_identity (g0 g1 : Int) :
    (2 * g0 + g1) * (2 * g0 + g1) - 4 * g0 * g0 = g1 * (4 * g0 + g1) := by
  have h4 : (4:Int) = 1 + 1 + 1 + 1 := rfl
  have h2 : (2:Int) = 1 + 1 := rfl
  rw [h4, h2]
  simp only [Int.mul_add, Int.mul_one, Int.mul_comm]
  omega

theorem rank_four_disc_nonneg (g0 g1 : Int) (h0 : 0 ≤ g0) (h1 : 0 ≤ g1) :
    0 ≤ (2 * g0 + g1) * (2 * g0 + g1) - 4 * g0 * g0 := by
  rw [rank_four_disc_identity]
  exact Int.mul_nonneg h1 (by omega)

theorem quartic_gamma_coeffs (g0 g1 g2 x : Int) :
    g0 * ((1 + x) * (1 + x) * (1 + x) * (1 + x)) + g1 * x * ((1 + x) * (1 + x))
        + g2 * (x * x)
      = evalP [g0, 4 * g0 + g1, 6 * g0 + 2 * g1 + g2, 4 * g0 + g1, g0] x := by
  simp only [evalP]
  have h6 : (6:Int) = 1 + 1 + 1 + 1 + 1 + 1 := rfl
  have h4 : (4:Int) = 1 + 1 + 1 + 1 := rfl
  have h2 : (2:Int) = 1 + 1 := rfl
  rw [h6, h4, h2]
  simp only [Int.mul_add, Int.mul_one, Int.mul_zero, Int.add_zero, Int.mul_comm, Int.mul_left_comm]
  omega

theorem rank_six_factor (g0 g1 g2 x : Int) :
    g0 * ((1 + x) * (1 + x) * (1 + x) * (1 + x) * (1 + x))
        + g1 * x * ((1 + x) * (1 + x) * (1 + x)) + g2 * (x * x) * (1 + x)
      = (1 + x) * (g0 * ((1 + x) * (1 + x) * (1 + x) * (1 + x))
              + g1 * x * ((1 + x) * (1 + x)) + g2 * (x * x)) := by
  simp only [Int.mul_add, Int.mul_one, Int.mul_comm, Int.mul_left_comm]
  omega

theorem rank_six_only_root_neg_one (g0 g1 g2 x : Int) (h0 : 0 < g0)
    (hd : g1 * g1 < 4 * g0 * g2)
    (hz : g0 * ((1 + x) * (1 + x) * (1 + x) * (1 + x) * (1 + x))
        + g1 * x * ((1 + x) * (1 + x) * (1 + x)) + g2 * (x * x) * (1 + x) = 0) :
    x = -1 := by
  rw [rank_six_factor] at hz
  exact dual_aug_quintic_root_only_neg_one g0 g1 g2 x h0 hd hz

/-! ## Gaussian q-binomial coefficients -/

/-- Gaussian binomial coefficient via the q-Pascal recursion. -/
def gaussQ (q : Int) : Nat → Nat → Int
  | 0, 0 => 1
  | 0, _ + 1 => 0
  | _ + 1, 0 => 1
  | n + 1, k + 1 => gaussQ q n k + q ^ (k + 1) * gaussQ q n (k + 1)

theorem gaussQ_zero_right (q : Int) (n : Nat) : gaussQ q n 0 = 1 := by
  cases n <;> rfl

theorem gaussQ_one_mul (q : Int) (n : Nat) :
    (q - 1) * gaussQ q n 1 = q ^ n - 1 := by
  induction n with
  | zero => simp only [gaussQ, Int.mul_zero, Int.pow_zero]; omega
  | succ n ih =>
    simp only [gaussQ]
    rw [gaussQ_zero_right, Int.pow_succ, Int.pow_zero, Int.one_mul, Int.mul_add,
      Int.mul_one, Int.mul_left_comm, ih, Int.mul_sub, Int.mul_one, Int.mul_comm q,
      Int.pow_succ q n]
    omega

theorem gaussQ_eq_zero_of_lt (q : Int) (n k : Nat) (h : n < k) : gaussQ q n k = 0 := by
  induction n generalizing k with
  | zero =>
    cases k with
    | zero => omega
    | succ k => rfl
  | succ n ih =>
    cases k with
    | zero => omega
    | succ k =>
      simp only [gaussQ]
      rw [ih k (by omega), ih (k + 1) (by omega), Int.mul_zero]
      rfl

theorem gaussQ_self (q : Int) (n : Nat) : gaussQ q n n = 1 := by
  induction n with
  | zero => rfl
  | succ n ih =>
    simp only [gaussQ]
    rw [ih, gaussQ_eq_zero_of_lt q n (n + 1) (by omega), Int.mul_zero]
    rfl


/-! ## Fast linear-pass Taylor shift and concrete universal certificates (q >= 17) -/

def pr569HstarDisc576 : List Int := [0, 0, 0, 0, 0, 0, 576, 960, 1492, 8528, 26272, 77280, 205180, 451304, 925240, 1710912, 2944269, 4758888, 7248984, 10511640, 14526088, 19211784, 24386160, 29720208, 34815666, 39233328, 42486048, 44239344, 44233108, 42444408, 38978088, 34237104, 28633757, 22731064, 17047640, 11974488, 7810440, 4668760, 2501744, 1177344, 461424, 138912, 27792, -2304]
def pr569FstarDisc576 : List Int := [0, 0, 0, 0, 0, 0, 1152, 1920, 2452, 8960, 25792, 79440, 216652, 485360, 1014880, 1887336, 3257565, 5262264, 7992216, 11526312, 15841096, 20801256, 26220528, 31728240, 36912594, 41315952, 44458512, 46007472, 45737188, 43641744, 39870720, 34849320, 29018477, 22942840, 17150216, 12010776, 7821864, 4669144, 2502320, 1177920, 461424, 138912, 27792, -2304]
def affineGabHstarDisc576 : List Int := [2880, 0, 0, 7968, -5760, -6912, -50684, 96, -4800, 41500, 58416, 75984, 86821, -72048, -88296, -192256, -94992, -63000, 120330, 293088, 318096, 266300, -23184, -219792, -475171, -476016, -386568, -144056, 122400, 311640, 397616, 315936, 216288, 89664, 32400, -2304]
def affineGabFstarDisc576 : List Int := [2304, 0, 0, 10752, -4608, -6912, -43052, -6144, -5472, 28420, 43872, 58752, 69397, -47376, -67800, -151720, -44496, -11928, 139506, 255360, 266928, 198092, -77952, -255648, -473707, -450960, -354072, -109832, 136032, 311928, 391088, 314208, 216864, 89664, 32400, -2304]

/-- Linear-pass shift helper: `evalP (shiftAdd a p r) x = a * evalP p x + evalP r x`. -/
def shiftAdd (a : Int) : List Int → List Int → List Int
  | [], r => r
  | b :: bs, [] => (a * b) :: shiftAdd a bs []
  | b :: bs, y :: ys => (y + a * b) :: shiftAdd a bs ys

/-- Single Horner step for `c + (x + a) * r(x)`. -/
def shiftStep (a c : Int) (r : List Int) : List Int :=
  match r with
  | [] => [c]
  | b :: bs => (c + a * b) :: shiftAdd a bs (b :: bs)

/-- Linear-pass Taylor shift `p(x + a)`. -/
def shiftFast : List Int → Int → List Int
  | [], _ => []
  | c :: cs, a => shiftStep a c (shiftFast cs a)

theorem evalP_shiftAdd (a : Int) (p r : List Int) (x : Int) :
    evalP (shiftAdd a p r) x = a * evalP p x + evalP r x := by
  induction p generalizing r with
  | nil => simp only [shiftAdd, evalP, Int.mul_zero]; omega
  | cons b bs ih =>
    cases r with
    | nil =>
      simp only [shiftAdd, evalP]
      rw [ih [], Int.mul_add, Int.mul_add, Int.mul_left_comm]
      simp only [evalP]
      omega
    | cons y ys =>
      simp only [shiftAdd, evalP]
      rw [ih ys, Int.mul_add, Int.mul_add, Int.mul_left_comm x a]
      omega

theorem evalP_shiftStep (a c : Int) (r : List Int) (x : Int) :
    evalP (shiftStep a c r) x = c + (x + a) * evalP r x := by
  cases r with
  | nil => simp only [shiftStep, evalP, Int.mul_zero]
  | cons b bs =>
    simp only [shiftStep, evalP]
    rw [evalP_shiftAdd]
    simp only [evalP]
    rw [Int.mul_add, Int.add_mul, Int.mul_add, Int.mul_add, Int.mul_left_comm x a]
    omega

theorem evalP_shiftFast (p : List Int) (a x : Int) :
    evalP (shiftFast p a) x = evalP p (x + a) := by
  induction p with
  | nil => simp only [shiftFast, evalP]
  | cons c cs ih =>
    simp only [shiftFast, evalP]
    rw [evalP_shiftStep, ih]

theorem all_pos_of_all_gt_zero (l : List Int) (h : l.all (fun c => decide (0 < c)) = true) :
    ∀ c ∈ l, 0 < c := by
  induction l with
  | nil => intro c hc; cases hc
  | cons a as ih =>
    intro c hc
    simp only [List.all_cons, Bool.and_eq_true, decide_eq_true_eq] at h
    cases List.mem_cons.mp hc with
    | inl e => subst e; exact h.1
    | inr tl => exact ih h.2 c tl

theorem neg_of_shiftFast_neg_coeffs_pos (p : List Int) (a : Int)
    (hp : ∀ c ∈ shiftFast (negP p) a, 0 < c) (hne : shiftFast (negP p) a ≠ []) :
    ∀ q, a ≤ q → evalP p q < 0 := by
  intro q hq
  have hx : 0 ≤ q - a := by omega
  have hpos := evalP_pos_of_coeffs_pos (shiftFast (negP p) a) (q - a) hp hne hx
  rw [evalP_shiftFast, Int.sub_add_cancel, evalP_negP] at hpos
  omega

/-- PR #569 PG(7,q) dual Chow discriminant 576 * D_H*(q) < 0 for every integer q >= 17. -/
theorem pr569_Hstar_disc_neg_for_all_q_ge_17 (q : Int) (hq : 17 ≤ q) :
    evalP pr569HstarDisc576 q < 0 :=
  neg_of_shiftFast_neg_coeffs_pos pr569HstarDisc576 17
    (all_pos_of_all_gt_zero _ (by decide)) (by decide) q hq

/-- PR #569 PG(7,q) dual right augmented discriminant 576 * D_F*(q) < 0 for every integer q >= 17. -/
theorem pr569_Fstar_disc_neg_for_all_q_ge_17 (q : Int) (hq : 17 ≤ q) :
    evalP pr569FstarDisc576 q < 0 :=
  neg_of_shiftFast_neg_coeffs_pos pr569FstarDisc576 17
    (all_pos_of_all_gt_zero _ (by decide)) (by decide) q hq

/-- Affine Gabidulin AG(6,q) dual Chow discriminant 576 * D_H*(q) < 0 for every integer q >= 17. -/
theorem affine_gabidulin_Hstar_disc_neg_for_all_q_ge_17 (q : Int) (hq : 17 ≤ q) :
    evalP affineGabHstarDisc576 q < 0 :=
  neg_of_shiftFast_neg_coeffs_pos affineGabHstarDisc576 17
    (all_pos_of_all_gt_zero _ (by decide)) (by decide) q hq

/-- Affine Gabidulin AG(6,q) dual right augmented discriminant 576 * D_F*(q) < 0 for every integer q >= 17. -/
theorem affine_gabidulin_Fstar_disc_neg_for_all_q_ge_17 (q : Int) (hq : 17 ≤ q) :
    evalP affineGabFstarDisc576 q < 0 :=
  neg_of_shiftFast_neg_coeffs_pos affineGabFstarDisc576 17
    (all_pos_of_all_gt_zero _ (by decide)) (by decide) q hq

/-- Ground-set collapse: for every q >= 2, |E(A_q)| = q^6 + q^3 < [8]_q + q^4 = |E(M_q)|. -/
theorem affine_gabidulin_strictly_smaller_ground_set (q : Int) (hq : 2 ≤ q) :
    q * q * q * q * q * q + q * q * q < gaussQ q 8 1 + q * q * q * q := by
  have h1 : (q - 1) * gaussQ q 8 1 = q ^ 8 - 1 := gaussQ_one_mul q 8
  have hqpos : 0 < q - 1 := by omega
  have hpow : q ^ 8 = q * q * q * q * q * q * q * q := by
    simp only [Int.pow_succ, Int.pow_zero, Int.one_mul]
  have hdiff : 0 < (q - 1) * (gaussQ q 8 1 + q * q * q * q - (q * q * q * q * q * q + q * q * q)) := by
    rw [Int.mul_sub, Int.mul_add, h1, hpow]
    have hq2 : 4 ≤ q * q := Int.mul_le_mul hq hq (by omega) (by omega)
    have hq3 : 8 ≤ q * q * q := Int.mul_le_mul hq2 hq (by omega) (by omega)
    have hq4 : 16 ≤ q * q * q * q := Int.mul_le_mul hq3 hq (by omega) (by omega)
    have hq5 : 32 ≤ q * q * q * q * q := Int.mul_le_mul hq4 hq (by omega) (by omega)
    have hq6 : 64 ≤ q * q * q * q * q * q := Int.mul_le_mul hq5 hq (by omega) (by omega)
    have hq7 : 2 * (q * q * q * q * q * q) ≤ q * q * q * q * q * q * q := by
      have := Int.mul_le_mul_of_nonneg_left hq (by omega : 0 ≤ q * q * q * q * q * q)
      rw [Int.mul_comm] at this
      exact this
    have hq8 : 2 * (q * q * q * q * q * q * q) ≤ q * q * q * q * q * q * q * q := by
      have := Int.mul_le_mul_of_nonneg_left hq (by omega : 0 ≤ q * q * q * q * q * q * q)
      rw [Int.mul_comm] at this
      exact this
    have hq4_le_q5 : q * q * q * q ≤ q * q * q * q * q := by
      have := Int.mul_le_mul_of_nonneg_left (by omega : 1 ≤ q) (by omega : 0 ≤ q * q * q * q)
      rw [Int.mul_one] at this
      exact this
    have hq5_le_q6 : q * q * q * q * q ≤ q * q * q * q * q * q := by
      have := Int.mul_le_mul_of_nonneg_left (by omega : 1 ≤ q) (by omega : 0 ≤ q * q * q * q * q)
      rw [Int.mul_one] at this
      exact this
    have hq3_le_q4 : q * q * q ≤ q * q * q * q := by
      have := Int.mul_le_mul_of_nonneg_left (by omega : 1 ≤ q) (by omega : 0 ≤ q * q * q)
      rw [Int.mul_one] at this
      exact this
    have hexp : (q - 1) * (q * q * q * q) = q * q * q * q * q - q * q * q * q := by
      rw [Int.sub_mul, Int.one_mul, Int.mul_comm q]
    have hexp2 : (q - 1) * (q * q * q * q * q * q + q * q * q)
        = (q * q * q * q * q * q * q - q * q * q * q * q * q) + (q * q * q * q - q * q * q) := by
      rw [Int.mul_add, Int.sub_mul, Int.sub_mul, Int.one_mul, Int.one_mul,
        Int.mul_comm q (q * q * q * q * q * q), Int.mul_comm q (q * q * q)]
    rw [hexp, hexp2]
    omega
  have hpos := pos_of_mul_pos_left (q - 1) _ hqpos hdiff
  omega

end DualChowMatroidTomography

#print axioms DualChowMatroidTomography.evalP_addP
#print axioms DualChowMatroidTomography.evalP_scaleP
#print axioms DualChowMatroidTomography.evalP_negP
#print axioms DualChowMatroidTomography.evalP_mulP
#print axioms DualChowMatroidTomography.evalP_shiftP
#print axioms DualChowMatroidTomography.evalP_nonneg_of_coeffs_nonneg
#print axioms DualChowMatroidTomography.evalP_pos_of_coeffs_pos
#print axioms DualChowMatroidTomography.neg_of_shifted_neg_coeffs_pos
#print axioms DualChowMatroidTomography.quad_pos_of_neg_disc
#print axioms DualChowMatroidTomography.dual_chow_quartic_pos
#print axioms DualChowMatroidTomography.dual_aug_quintic_root_only_neg_one
#print axioms DualChowMatroidTomography.rank_four_factorization
#print axioms DualChowMatroidTomography.rank_four_disc_identity
#print axioms DualChowMatroidTomography.rank_four_disc_nonneg
#print axioms DualChowMatroidTomography.quartic_gamma_coeffs
#print axioms DualChowMatroidTomography.rank_six_only_root_neg_one
#print axioms DualChowMatroidTomography.gaussQ_one_mul
#print axioms DualChowMatroidTomography.gaussQ_eq_zero_of_lt
#print axioms DualChowMatroidTomography.gaussQ_self
#print axioms DualChowMatroidTomography.pr569_Hstar_disc_neg_for_all_q_ge_17
#print axioms DualChowMatroidTomography.pr569_Fstar_disc_neg_for_all_q_ge_17
#print axioms DualChowMatroidTomography.affine_gabidulin_Hstar_disc_neg_for_all_q_ge_17
#print axioms DualChowMatroidTomography.affine_gabidulin_Fstar_disc_neg_for_all_q_ge_17
#print axioms DualChowMatroidTomography.affine_gabidulin_strictly_smaller_ground_set
