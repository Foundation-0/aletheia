/-
  Wave2KernelCerts.Theorem1_BallF64CauchySchwarz
  Track S57 — Pure-Init Lean 4.36.0 Kernel Certificate for Track S49 (L2-ball f64 Margin).
  Zero Mathlib, zero sorry/admit/axiom, zero native_decide, zero external imports.
-/

namespace Wave2KernelCerts.Theorem1

/-- Exact IEEE-754 binary64 consecutive-integer significand ceiling: 2^53. -/
def f64ExactIntLimit : Int := 9007199254740992

/-- Maximum exact integer-scaled binary16 activation: 65504 * 2^24. -/
def f16MaxScaled : Int := 1098974756864

/-- L1 norm of an integer list: sum of absolute values. -/
def sumAbs : List Int → Int
  | [] => 0
  | x :: xs => (Int.natAbs x : Int) + sumAbs xs

/-- Squared L2 norm of an integer list: sum of squares. -/
def sumSq : List Int → Int
  | [] => 0
  | x :: xs => x * x + sumSq xs

/-- Plain integer sum of a list. -/
def sumList : List Int → Int
  | [] => 0
  | x :: xs => x + sumList xs

theorem sumAbs_nonneg : ∀ l : List Int, 0 ≤ sumAbs l
  | [] => by simp [sumAbs]
  | x :: xs => by
      have hxs := sumAbs_nonneg xs
      simp only [sumAbs]
      omega

private theorem sq_nonneg (x : Int) : 0 ≤ x * x := by
  by_cases h : 0 ≤ x
  · exact Int.mul_nonneg h h
  · have hn : 0 ≤ -x := by omega
    have hp : 0 ≤ (-x) * (-x) := Int.mul_nonneg hn hn
    rw [Int.neg_mul_neg] at hp
    exact hp

theorem sumSq_nonneg : ∀ l : List Int, 0 ≤ sumSq l
  | [] => by simp [sumSq]
  | x :: xs => by
      have hxs := sumSq_nonneg xs
      have hxx : 0 ≤ x * x := sq_nonneg x
      simp only [sumSq]
      omega

private theorem natAbs_mul_self_eq (x : Int) :
    (Int.natAbs x : Int) * (Int.natAbs x : Int) = x * x := by
  cases x with
  | ofNat n => simp [Int.natAbs]
  | negSucc n =>
      have h1 : (Int.natAbs (Int.negSucc n) : Int) = -(Int.negSucc n) := by omega
      rw [h1]
      exact Int.neg_mul_neg (Int.negSucc n) (Int.negSucc n)

private theorem two_mul_le_sq_sum (a b : Int) : 2 * a * b ≤ a * a + b * b := by
  have h : 0 ≤ (a - b) * (a - b) := sq_nonneg (a - b)
  have hexp : (a - b) * (a - b) = a * a + b * b - 2 * (a * b) := by
    rw [Int.sub_mul, Int.mul_sub, Int.mul_sub]
    have hcomm : b * a = a * b := Int.mul_comm b a
    omega
  rw [Int.mul_assoc 2 a b]
  omega

private theorem cross_bound (a : Int) :
    ∀ t : List Int,
      2 * (Int.natAbs a : Int) * sumAbs t ≤ (t.length : Int) * (a * a) + sumSq t
  | [] => by
      simp [sumAbs, sumSq]
  | b :: bs => by
      have ih := cross_bound a bs
      have hab := two_mul_le_sq_sum (Int.natAbs a : Int) (Int.natAbs b : Int)
      have ha2 : (Int.natAbs a : Int) * (Int.natAbs a : Int) = a * a := natAbs_mul_self_eq a
      have hb2 : (Int.natAbs b : Int) * (Int.natAbs b : Int) = b * b := natAbs_mul_self_eq b
      rw [ha2, hb2] at hab
      simp only [sumAbs, sumSq, List.length]
      have hlen : (((bs.length + 1 : Nat) : Int)) * (a * a) =
          (bs.length : Int) * (a * a) + a * a := by
        have h1 : ((bs.length + 1 : Nat) : Int) = (bs.length : Int) + 1 := by omega
        rw [h1, Int.add_mul, Int.one_mul]
      have hdist : 2 * (Int.natAbs a : Int) * ((Int.natAbs b : Int) + sumAbs bs) =
          2 * (Int.natAbs a : Int) * (Int.natAbs b : Int) +
          2 * (Int.natAbs a : Int) * sumAbs bs := Int.mul_add _ _ _
      omega

/-- Theorem 1.1 (Universal): Integer Cauchy-Schwarz inequality on arbitrary-length lists. -/
theorem int_list_cauchy_schwarz :
    ∀ l : List Int, sumAbs l * sumAbs l ≤ (l.length : Int) * sumSq l
  | [] => by simp [sumAbs, sumSq]
  | x :: xs => by
      have ih := int_list_cauchy_schwarz xs
      have hcross := cross_bound x xs
      have hx2 : (Int.natAbs x : Int) * (Int.natAbs x : Int) = x * x := natAbs_mul_self_eq x
      simp only [sumAbs, sumSq, List.length]
      have h2x : 2 * (Int.natAbs x : Int) * sumAbs xs =
          2 * ((Int.natAbs x : Int) * sumAbs xs) := Int.mul_assoc _ _ _
      have hsq : ((Int.natAbs x : Int) + sumAbs xs) * ((Int.natAbs x : Int) + sumAbs xs) =
          x * x + 2 * ((Int.natAbs x : Int) * sumAbs xs) + sumAbs xs * sumAbs xs := by
        rw [Int.add_mul, Int.mul_add, Int.mul_add, hx2]
        have hc : sumAbs xs * (Int.natAbs x : Int) = (Int.natAbs x : Int) * sumAbs xs :=
          Int.mul_comm _ _
        omega
      have hrhs : ((xs.length + 1 : Nat) : Int) * (x * x + sumSq xs) =
          x * x + (xs.length : Int) * (x * x) + sumSq xs + (xs.length : Int) * sumSq xs := by
        have h1 : ((xs.length + 1 : Nat) : Int) = (xs.length : Int) + 1 := by omega
        rw [h1, Int.add_mul, Int.mul_add, Int.one_mul]
        omega
      omega

private theorem sq_parity_constructionA (ci zi : Int) (hc : ci = 0 ∨ ci = 1) :
    ((ci + 2 * zi) * (ci + 2 * zi)) % 2 = ci % 2 := by
  rcases hc with rfl | rfl
  · have h : (0 + 2 * zi) * (0 + 2 * zi) = 2 * (2 * zi * zi) := by
      have h0 : 0 + 2 * zi = 2 * zi := Int.zero_add _
      rw [h0]
      have h1 : 2 * zi * (2 * zi) = 2 * (zi * (2 * zi)) := Int.mul_assoc 2 zi (2 * zi)
      have h2 : zi * (2 * zi) = 2 * zi * zi := by
        rw [← Int.mul_assoc, Int.mul_comm zi 2]
      rw [h1, h2]
    rw [h]
    omega
  · have h : (1 + 2 * zi) * (1 + 2 * zi) = 1 + 2 * (2 * zi + 2 * zi * zi) := by
      rw [Int.add_mul, Int.mul_add, Int.mul_add, Int.one_mul, Int.mul_one]
      have h1 : 2 * zi * (2 * zi) = 2 * (2 * zi * zi) := by
        rw [Int.mul_assoc, ← Int.mul_assoc zi 2 zi, Int.mul_comm zi 2, Int.mul_assoc]
      omega
    rw [h]
    omega

private theorem sumSq_zip_mod2 :
    ∀ (c z : List Int),
      c.length = z.length →
      (∀ x ∈ c, x = 0 ∨ x = 1) →
      sumSq (List.zipWith (fun ci zi => ci + 2 * zi) c z) % 2 = sumList c % 2
  | [], [], _, _ => by simp [sumSq, sumList]
  | _ :: _, [], hlen, _ => by simp at hlen
  | [], _ :: _, hlen, _ => by simp at hlen
  | ci :: cs, zi :: zs, hlen, hbin => by
      have hlen' : cs.length = zs.length := by
        simp only [List.length] at hlen
        omega
      have hci : ci = 0 ∨ ci = 1 := hbin ci (List.Mem.head cs)
      have hcs : ∀ x ∈ cs, x = 0 ∨ x = 1 := fun x hx => hbin x (List.Mem.tail ci hx)
      have ih := sumSq_zip_mod2 cs zs hlen' hcs
      have hsq := sq_parity_constructionA ci zi hci
      simp only [List.zipWith, sumSq, sumList]
      omega

/-- Theorem 1.2 (Universal): Construction-A 2x + 2x even-norm parity theorem.
    Any lattice vector v = c + 2z over an even-weight binary code C has even squared norm. -/
theorem constructionA_even_parity_norm_sq
    (c z : List Int)
    (hlen : c.length = z.length)
    (hbin : ∀ x ∈ c, x = 0 ∨ x = 1)
    (heven : sumList c % 2 = 0) :
    sumSq (List.zipWith (fun ci zi => ci + 2 * zi) c z) % 2 = 0 := by
  have h := sumSq_zip_mod2 c z hlen hbin
  omega

/-- Theorem 1.3 (Universal): Any even integer bounded by an odd ceiling tightens by 1. -/
theorem odd_bound_tightens_to_even (n b : Int) (heven : n % 2 = 0) (hle : n ≤ 2 * b + 1) :
    n ≤ 2 * b := by
  omega

private theorem le_of_sq_lt_succ_sq (s k : Int) (hs : 0 ≤ s) (hk : 0 ≤ k)
    (hlt : s * s < (k + 1) * (k + 1)) : s ≤ k := by
  by_cases h : s ≤ k
  · exact h
  · have hge : k + 1 ≤ s := by omega
    have h1 : (k + 1) * (k + 1) ≤ (k + 1) * s := Int.mul_le_mul_of_nonneg_left hge (by omega)
    have h2 : (k + 1) * s ≤ s * s := Int.mul_le_mul_of_nonneg_right hge hs
    omega

/-- Theorem 1.4 (Universal): 72B hammingindex (n = 128, even ||v||^2 <= 5213 => 5212)
    forces ||v||_1 <= 816 identically for every lattice vector in the L2 ball. -/
theorem ball_72B_sumAbs_le_816
    (v : List Int)
    (hlen : v.length = 128)
    (heven : sumSq v % 2 = 0)
    (hbound : sumSq v ≤ 5213) :
    sumAbs v ≤ 816 := by
  have h5212 : sumSq v ≤ 5212 := odd_bound_tightens_to_even (sumSq v) 2606 heven hbound
  have hcs := int_list_cauchy_schwarz v
  rw [hlen] at hcs
  have hlt : sumAbs v * sumAbs v < (816 + 1) * (816 + 1) := by omega
  exact le_of_sq_lt_succ_sq (sumAbs v) 816 (sumAbs_nonneg v) (by omega) hlt

/-- Theorem 1.5 (Universal): 72B hammingindex exact >10x binary64 accumulation margin,
    plus exact reduced rational ratio witness 1048576 / 104397 > 10. -/
theorem ball_72B_f64_margin_gt_10x
    (v : List Int) (a : Int)
    (hlen : v.length = 128)
    (heven : sumSq v % 2 = 0)
    (hbound : sumSq v ≤ 5213)
    (ha0 : 0 ≤ a)
    (hamax : a ≤ f16MaxScaled) :
    sumAbs v * a * 10 < f64ExactIntLimit ∧
    f64ExactIntLimit * 104397 = (816 * f16MaxScaled) * 1048576 ∧
    1048576 > 10 * 104397 := by
  have h816 := ball_72B_sumAbs_le_816 v hlen heven hbound
  have hnonneg := sumAbs_nonneg v
  have h1 : sumAbs v * a ≤ 816 * a := Int.mul_le_mul_of_nonneg_right h816 ha0
  have h2 : 816 * a ≤ 816 * f16MaxScaled := Int.mul_le_mul_of_nonneg_left hamax (by omega)
  have h3 : 816 * f16MaxScaled * 10 < f64ExactIntLimit := by decide
  have h4 : f64ExactIntLimit * 104397 = (816 * f16MaxScaled) * 1048576 := by decide
  have h5 : 1048576 > 10 * 104397 := by decide
  refine ⟨?_, h4, h5⟩
  omega

/-- Theorem 1.6 (Concrete): Naive L_inf <= 64 box fails on 72B hammingindex (max|v_i| = 72 > 64),
    proving L2-ball Cauchy-Schwarz is strictly required. -/
theorem ball_72B_max_coord_72_gt_64_witness :
    (72 : Int) * 72 ≤ 5212 ∧ (72 : Int) > 64 ∧ (74 : Int) * 74 > 5212 := by
  decide

/-- Theorem 1.7 (Universal): 18B hampack (n = 32, even ||v||^2 <= 1207 => 1206)
    forces ||v||_1 <= 196 identically for every lattice vector in the L2 ball. -/
theorem ball_18B_sumAbs_le_196
    (v : List Int)
    (hlen : v.length = 32)
    (heven : sumSq v % 2 = 0)
    (hbound : sumSq v ≤ 1207) :
    sumAbs v ≤ 196 := by
  have h1206 : sumSq v ≤ 1206 := odd_bound_tightens_to_even (sumSq v) 603 heven hbound
  have hcs := int_list_cauchy_schwarz v
  rw [hlen] at hcs
  have hlt : sumAbs v * sumAbs v < (196 + 1) * (196 + 1) := by omega
  exact le_of_sq_lt_succ_sq (sumAbs v) 196 (sumAbs_nonneg v) (by omega) hlt

/-- Theorem 1.8 (Universal): 18B hampack exact >41x binary64 accumulation margin,
    plus exact reduced rational ratio witness 4194304 / 100303 > 41 and max|v_i| = 34. -/
theorem ball_18B_f64_margin_gt_41x
    (v : List Int) (a : Int)
    (hlen : v.length = 32)
    (heven : sumSq v % 2 = 0)
    (hbound : sumSq v ≤ 1207)
    (ha0 : 0 ≤ a)
    (hamax : a ≤ f16MaxScaled) :
    sumAbs v * a * 41 < f64ExactIntLimit ∧
    f64ExactIntLimit * 100303 = (196 * f16MaxScaled) * 4194304 ∧
    4194304 > 41 * 100303 ∧
    (34 : Int) * 34 ≤ 1206 ∧ (36 : Int) * 36 > 1206 := by
  have h196 := ball_18B_sumAbs_le_196 v hlen heven hbound
  have h1 : sumAbs v * a ≤ 196 * a := Int.mul_le_mul_of_nonneg_right h196 ha0
  have h2 : 196 * a ≤ 196 * f16MaxScaled := Int.mul_le_mul_of_nonneg_left hamax (by omega)
  have h3 : 196 * f16MaxScaled * 41 < f64ExactIntLimit := by decide
  have h4 : f64ExactIntLimit * 100303 = (196 * f16MaxScaled) * 4194304 := by decide
  have h5 : 4194304 > 41 * 100303 := by decide
  have h6 : (34 : Int) * 34 ≤ 1206 := by decide
  have h7 : (36 : Int) * 36 > 1206 := by decide
  refine ⟨?_, h4, h5, h6, h7⟩
  omega

end Wave2KernelCerts.Theorem1

#print axioms Wave2KernelCerts.Theorem1.int_list_cauchy_schwarz
#print axioms Wave2KernelCerts.Theorem1.constructionA_even_parity_norm_sq
#print axioms Wave2KernelCerts.Theorem1.odd_bound_tightens_to_even
#print axioms Wave2KernelCerts.Theorem1.ball_72B_sumAbs_le_816
#print axioms Wave2KernelCerts.Theorem1.ball_72B_f64_margin_gt_10x
#print axioms Wave2KernelCerts.Theorem1.ball_72B_max_coord_72_gt_64_witness
#print axioms Wave2KernelCerts.Theorem1.ball_18B_sumAbs_le_196
#print axioms Wave2KernelCerts.Theorem1.ball_18B_f64_margin_gt_41x
