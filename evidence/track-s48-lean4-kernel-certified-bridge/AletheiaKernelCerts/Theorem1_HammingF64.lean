/-
  Track S48 — Theorem 1 (Portal 53 / Track S47):
  1. Sharp IEEE-754 binary64 (53-bit significand) exact integer decode boundary:
       - ∀ w ≤ 64, w * 2^47 ≤ 2^53  while  65 * 2^47 > 2^53
       - Group-128 x finite binary16 (max scaled 65504 * 2^24):
         ∀ w ≤ 64, ∀ a ≤ 65504 * 2^24, 128 * w * a ≤ 2^53
         while w = 65 yields odd witness 9,072,036,617,912,321 > 2^53 (inexact in binary64).
  2. Extended Hamming [16, 11, 4] linear code C_16 over GF(2):
       - Exact 5 x 16 parity-check matrix H_16 and 11 x 16 systematic generator G_16
       - Kernel-verified H_16 * G_16^T = 0 (mod 2) and self-orthogonality H_16 * H_16^T = 0 (mod 2)
       - Universal minimum distance proof: ∀ v ∈ C_16, v ≠ 0 → wt(v) ≥ 4, plus tight wt = 4 witness.
-/

namespace AletheiaKernelCerts.Theorem1

/-- Scaled maximum finite IEEE-754 binary16 value: 65504 * 2^24. -/
def f16MaxScaled : Nat := 65504 * (2 ^ 24)

/-- IEEE-754 binary64 exact consecutive integer boundary: 2^53. -/
def f64ExactIntLimit : Nat := 2 ^ 53

/-- Sharp power-of-two significand upper bound: every w ≤ 64 fits within 2^53 at stride 2^47. -/
theorem f64_pow2_significand_sharp_upper :
    ∀ w : Nat, w ≤ 64 → w * (2 ^ 47) ≤ 2 ^ 53 := by
  intro w hw
  omega

/-- Sharp power-of-two significand break: w = 65 strictly exceeds 2^53 at stride 2^47. -/
theorem f64_pow2_significand_sharp_break :
    65 * (2 ^ 47) > 2 ^ 53 := by
  omega

/-- Universal group-128 x finite-f16 exact decode guarantee for all weight bounds w ≤ 64. -/
theorem f64_group128_f16_exact_w64 :
    ∀ w a : Nat, w ≤ 64 → a ≤ f16MaxScaled → 128 * w * a ≤ f64ExactIntLimit := by
  intro w a hw ha
  have h1 : 128 * w ≤ 128 * 64 := Nat.mul_le_mul_left 128 hw
  have h2 : (128 * w) * a ≤ (128 * 64) * f16MaxScaled := Nat.mul_le_mul h1 ha
  have h3 : (128 * 64) * f16MaxScaled ≤ f64ExactIntLimit := by decide
  exact Nat.le_trans h2 h3

/-- Exact sharp w = 64 maximum scaled sum equals 9,002,801,208,229,888 ≤ 2^53. -/
theorem f64_w64_max_scaled_sum_exact :
    128 * 64 * f16MaxScaled = 9002801208229888 ∧ 9002801208229888 ≤ f64ExactIntLimit := by
  decide

/-- Sharp w = 65 failure witness: 9,072,036,617,912,321 exceeds 2^53 and is odd (binary64 ULP = 2). -/
theorem f64_group128_f16_w65_odd_overflow :
    127 * 65 * f16MaxScaled + 1 = 9072036617912321 ∧
    127 * 65 * f16MaxScaled + 1 > f64ExactIntLimit ∧
    (127 * 65 * f16MaxScaled + 1) % 2 = 1 := by
  decide

/-! ### Extended Hamming [16, 11, 4] Code over GF(2) -/

/-- Exact 5 x 16 parity-check matrix H_16 (row 0 = overall parity; rows 1..4 = bit planes 0..3). -/
def H16 (r : Fin 5) (j : Fin 16) : Bool :=
  if r.val == 0 then
    true
  else
    ((j.val >>> (r.val - 1)) &&& 1) == 1

/-- The 11 non-pivot information columns of systematic [16, 11, 4] extended Hamming code. -/
def infoCol16 (k : Fin 11) : Nat :=
  match k.val with
  | 0 => 3
  | 1 => 5
  | 2 => 6
  | 3 => 7
  | 4 => 9
  | 5 => 10
  | 6 => 11
  | 7 => 12
  | 8 => 13
  | 9 => 14
  | _ => 15

/-- Exact 11 x 16 systematic generator matrix G_16 matching Track S47 `build_generator_matrix(4)`. -/
def G16 (k : Fin 11) (j : Fin 16) : Bool :=
  let c := infoCol16 k
  let b0 := (c &&& 1) == 1
  let b1 := ((c >>> 1) &&& 1) == 1
  let b2 := ((c >>> 2) &&& 1) == 1
  let b3 := ((c >>> 3) &&& 1) == 1
  let pc := (if b0 then 1 else 0) + (if b1 then 1 else 0) +
            (if b2 then 1 else 0) + (if b3 then 1 else 0)
  (j.val == c) ||
  (j.val == 1 && b0) ||
  (j.val == 2 && b1) ||
  (j.val == 4 && b2) ||
  (j.val == 8 && b3) ||
  (j.val == 0 && (pc % 2 == 0))

/-- Exact GF(2) dot product on binary 16-vectors. -/
def dotMod2_16 (u v : Fin 16 → Bool) : Bool :=
  (List.finRange 16).foldl (fun acc j => xor acc (u j && v j)) false

/-- Exact 5-bit syndrome of v under H_16. -/
def syndrome16 (v : Fin 16 → Bool) (r : Fin 5) : Bool :=
  dotMod2_16 (H16 r) v

/-- Membership predicate v ∈ C_16 ⇔ H_16 v = 0 (mod 2). -/
def inCode16 (v : Fin 16 → Bool) : Bool :=
  (List.finRange 5).all (fun r => !(syndrome16 v r))

/-- Hamming weight of a binary 16-vector. -/
def hammingWeight16 (v : Fin 16 → Bool) : Nat :=
  (List.finRange 16).countP v

/-- Standard basis vector e_i ∈ GF(2)^16. -/
def basis16 (i : Fin 16) : Fin 16 → Bool :=
  fun j => j == i

/-- Coordinatewise XOR of two vectors in GF(2)^16. -/
def xor16 (u v : Fin 16 → Bool) : Fin 16 → Bool :=
  fun j => xor (u j) (v j)

/-- Exact parity-check / generator orthogonality: H_16 * G_16^T = 0 (mod 2). -/
theorem hamming16_H_G_orthogonal :
    ∀ (r : Fin 5) (k : Fin 11), dotMod2_16 (H16 r) (G16 k) = false := by
  decide

/-- Dual containment / self-orthogonality: H_16 * H_16^T = 0 (mod 2) (RM(1,4) ⊆ C_16). -/
theorem hamming16_H_self_orthogonal :
    ∀ (r1 r2 : Fin 5), dotMod2_16 (H16 r1) (H16 r2) = false := by
  decide

/-- No weight-1 vector lies in C_16. -/
theorem hamming16_no_weight_1 :
    ∀ i : Fin 16, inCode16 (basis16 i) = false := by
  decide

/-- No weight-2 vector lies in C_16. -/
theorem hamming16_no_weight_2 :
    ∀ (i j : Fin 16), i < j → inCode16 (xor16 (basis16 i) (basis16 j)) = false := by
  decide

private theorem foldl_xor_eq_countP_mod2 {α : Type} (f : α → Bool) :
    ∀ (l : List α) (acc : Bool),
      l.foldl (fun a x => xor a (f x)) acc = xor acc (l.countP f % 2 == 1)
  | [], acc => by
    simp
  | x :: xs, acc => by
    simp only [List.foldl_cons, List.countP_cons]
    rw [foldl_xor_eq_countP_mod2 f xs (xor acc (f x))]
    rcases Nat.mod_two_eq_zero_or_one (xs.countP f) with h0 | h1
    · have h01 : (xs.countP f + 1) % 2 = 1 := by omega
      cases acc <;> cases f x <;> simp [h0, h01]
    · have h11 : (xs.countP f + 1) % 2 = 0 := by omega
      cases acc <;> cases f x <;> simp [h1, h11]

private theorem syndrome0_eq_weight_parity (v : Fin 16 → Bool) :
    syndrome16 v ⟨0, by decide⟩ = (hammingWeight16 v % 2 == 1) := by
  unfold syndrome16 dotMod2_16 hammingWeight16 H16
  have hfn : (fun j : Fin 16 => true && v j) = v := by
    funext j; simp
  simpa [hfn] using foldl_xor_eq_countP_mod2 v (List.finRange 16) false

private theorem countP_eq_two_nodup {α : Type} (f : α → Bool) :
    ∀ (l : List α), l.Nodup → l.countP f = 2 →
      ∃ a b : α, a ∈ l ∧ b ∈ l ∧ a ≠ b ∧ f a = true ∧ f b = true ∧
        ∀ x ∈ l, f x = true → x = a ∨ x = b
  | [], _, h => by simp at h
  | x :: xs, hnd, h => by
    have ⟨hxnot, hnd_xs⟩ := List.nodup_cons.mp hnd
    cases hfx : f x
    · simp only [List.countP_cons, hfx, Bool.false_eq_true, ↓reduceIte, Nat.add_zero] at h
      obtain ⟨a, b, ha, hb, hab, hfa, hfb, huniq⟩ := countP_eq_two_nodup f xs hnd_xs h
      refine ⟨a, b, List.mem_cons_of_mem x ha, List.mem_cons_of_mem x hb, hab, hfa, hfb, ?_⟩
      intro y hy hfy
      rcases List.mem_cons.mp hy with rfl | hmem
      · rw [hfx] at hfy; cases hfy
      · exact huniq y hmem hfy
    · simp only [List.countP_cons, hfx, ↓reduceIte] at h
      have h1 : xs.countP f = 1 := by omega
      have h1_ex : ∀ (m : List α), m.countP f = 1 →
          ∃ b : α, b ∈ m ∧ f b = true ∧ ∀ y ∈ m, f y = true → y = b := by
        intro m
        induction m with
        | nil => intro hm; simp at hm
        | cons z zs ih =>
          intro hm
          cases hfz : f z
          · simp only [List.countP_cons, hfz, Bool.false_eq_true, ↓reduceIte, Nat.add_zero] at hm
            obtain ⟨b, hb, hfb, hun⟩ := ih hm
            refine ⟨b, List.mem_cons_of_mem z hb, hfb, ?_⟩
            intro y hy hfy
            rcases List.mem_cons.mp hy with rfl | hzm
            · rw [hfz] at hfy; cases hfy
            · exact hun y hzm hfy
          · simp only [List.countP_cons, hfz, ↓reduceIte] at hm
            have hz0 : zs.countP f = 0 := by omega
            refine ⟨z, List.mem_cons_self, hfz, ?_⟩
            intro y hy hfy
            rcases List.mem_cons.mp hy with rfl | hzm
            · rfl
            · have hfalse := List.countP_eq_zero.mp hz0 y hzm
              exact absurd hfy hfalse
      obtain ⟨b, hb, hfb, huniq_b⟩ := h1_ex xs h1
      have hxb : x ≠ b := fun heq => hxnot (heq ▸ hb)
      refine ⟨x, b, List.mem_cons_self, List.mem_cons_of_mem x hb, hxb, hfx, hfb, ?_⟩
      intro y hy hfy
      rcases List.mem_cons.mp hy with rfl | hmem
      · left; rfl
      · right; exact huniq_b y hmem hfy

/-- Universal minimum distance lower bound: every nonzero codeword in C_16 has weight ≥ 4. -/
theorem hamming16_dmin_ge_4 :
    ∀ v : Fin 16 → Bool, inCode16 v = true → hammingWeight16 v ≠ 0 → hammingWeight16 v ≥ 4 := by
  intro v hcode hne0
  have hsyn0 : syndrome16 v ⟨0, by decide⟩ = false := by
    have hall := List.all_eq_true.mp hcode ⟨0, by decide⟩ (List.mem_finRange _)
    simpa using hall
  have heven : hammingWeight16 v % 2 = 0 := by
    rw [syndrome0_eq_weight_parity v] at hsyn0
    have : ¬ (hammingWeight16 v % 2 = 1) := by
      intro h1; simp [h1] at hsyn0
    omega
  have hne2 : hammingWeight16 v ≠ 2 := by
    intro hwt2
    obtain ⟨a, b, _, _, hab, hfa, hfb, huniq⟩ :=
      countP_eq_two_nodup v (List.finRange 16) (List.nodup_finRange 16) hwt2
    have heq_xor : ∀ u1 u2 : Fin 16, u1 ≠ u2 → v u1 = true → v u2 = true →
        (∀ t : Fin 16, v t = true → t = u1 ∨ t = u2) →
        v = xor16 (basis16 u1) (basis16 u2) := by
      intro u1 u2 hne hu1 hu2 hu
      funext t
      unfold xor16 basis16
      by_cases ht1 : t = u1
      · subst ht1
        have : (t == u2) = false := beq_false_of_ne hne
        simp [hu1, this]
      · by_cases ht2 : t = u2
        · subst ht2
          have : (t == u1) = false := beq_false_of_ne (Ne.symm hne)
          simp [hu2, this]
        · have hvfalse : v t = false := by
            cases hvt : v t with
            | false => rfl
            | true =>
              rcases hu t hvt with h | h
              · exact absurd h ht1
              · exact absurd h ht2
          have h1f : (t == u1) = false := beq_false_of_ne ht1
          have h2f : (t == u2) = false := beq_false_of_ne ht2
          simp [hvfalse, h1f, h2f]
    have huniq_all : ∀ t : Fin 16, v t = true → t = a ∨ t = b :=
      fun t ht => huniq t (List.mem_finRange t) ht
    rcases Nat.lt_or_gt_of_ne (Fin.val_ne_of_ne hab) with hlt | hgt
    · have hv : v = xor16 (basis16 a) (basis16 b) := heq_xor a b hab hfa hfb huniq_all
      rw [hv] at hcode
      have hno := hamming16_no_weight_2 a b hlt
      rw [hno] at hcode; cases hcode
    · have huniq_sym : ∀ t : Fin 16, v t = true → t = b ∨ t = a :=
        fun t ht => (huniq_all t ht).symm
      have hv : v = xor16 (basis16 b) (basis16 a) := heq_xor b a (Ne.symm hab) hfb hfa huniq_sym
      rw [hv] at hcode
      have hno := hamming16_no_weight_2 b a hgt
      rw [hno] at hcode; cases hcode
  omega

/-- Tightness witness: row 0 of G_16 is a codeword of exact Hamming weight 4 (supports {0,1,2,3}). -/
theorem hamming16_weight_4_witness :
    inCode16 (G16 ⟨0, by decide⟩) = true ∧ hammingWeight16 (G16 ⟨0, by decide⟩) = 4 := by
  decide

#print axioms f64_pow2_significand_sharp_upper
#print axioms f64_pow2_significand_sharp_break
#print axioms f64_group128_f16_exact_w64
#print axioms f64_w64_max_scaled_sum_exact
#print axioms f64_group128_f16_w65_odd_overflow
#print axioms hamming16_H_G_orthogonal
#print axioms hamming16_H_self_orthogonal
#print axioms hamming16_dmin_ge_4
#print axioms hamming16_weight_4_witness
#print axioms hamming16_no_weight_1
#print axioms hamming16_no_weight_2

end AletheiaKernelCerts.Theorem1
