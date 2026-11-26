/-
  Track S48 — Theorem 2 (Portal 53 / Track S32):
  Exact Block-H2 INT8 Safety (max_entry = 78 ≤ 127) vs. WHT_8 Overflow (max_entry = 156 > 127)
  on Doubled E_8 Lattice Shell Ball m ≤ 391 (||z||^2 ≤ 3128, EBG32:b136s8 regime).

  Proved universally over all z ∈ 2*E_8 with ||z||^2 ≤ 3128 via pure integer algebra
  (parity, mod-4 invariance, exact sum-of-squares Cauchy-Schwarz identity) plus tight witnesses.
-/

namespace AletheiaKernelCerts.Theorem2

/-- Signed INT8 symmetric maximum magnitude. -/
def int8Max : Int := 127

/-- EBG32:b136s8 shell bound m_max = 391 gives ||z||^2 ≤ 8 * 391 = 3128 for z ∈ 2*E_8. -/
def maxNormSq136b : Int := 8 * 391

/-- Membership in doubled E_8 lattice 2*E_8: uniform coordinate parity and sum ≡ 0 (mod 4). -/
def IsDoubledE8 (z : Fin 8 → Int) : Prop :=
  (∀ i : Fin 8, z i % 2 = z 0 % 2) ∧
  (z 0 + z 1 + z 2 + z 3 + z 4 + z 5 + z 6 + z 7) % 4 = 0

/-- Squared Euclidean norm of an integer 8-vector. -/
def normSq8 (z : Fin 8 → Int) : Int :=
  z 0 * z 0 + z 1 * z 1 + z 2 * z 2 + z 3 * z 3 +
  z 4 * z 4 + z 5 * z 5 + z 6 * z 6 + z 7 * z 7

/-- Exact 8x8 Block-H2 orthogonal rotation matrix (diag(H_2, H_2, H_2, H_2)). -/
def blockH2Mat (r c : Fin 8) : Int :=
  match r.val, c.val with
  | 0, 0 => 1  | 0, 1 => 1
  | 1, 0 => 1  | 1, 1 => -1
  | 2, 2 => 1  | 2, 3 => 1
  | 3, 2 => 1  | 3, 3 => -1
  | 4, 4 => 1  | 4, 5 => 1
  | 5, 4 => 1  | 5, 5 => -1
  | 6, 6 => 1  | 6, 7 => 1
  | 7, 6 => 1  | 7, 7 => -1
  | _, _ => 0

/-- Exact 8x8 Sylvester Walsh-Hadamard matrix H_8 (H_2^{⊗3} via popcount parity). -/
def wht8Mat (r c : Fin 8) : Int :=
  let pop := ((r.val &&& c.val) &&& 1) +
             (((r.val &&& c.val) >>> 1) &&& 1) +
             (((r.val &&& c.val) >>> 2) &&& 1)
  if pop % 2 == 0 then 1 else -1

/-- Apply Block-H2 to an integer 8-vector. -/
def applyBlockH2 (z : Fin 8 → Int) (r : Fin 8) : Int :=
  match r.val with
  | 0 => z 0 + z 1
  | 1 => z 0 - z 1
  | 2 => z 2 + z 3
  | 3 => z 2 - z 3
  | 4 => z 4 + z 5
  | 5 => z 4 - z 5
  | 6 => z 6 + z 7
  | _ => z 6 - z 7

/-- Apply WHT_8 (H_8) to an integer 8-vector. -/
def applyWht8 (z : Fin 8 → Int) (r : Fin 8) : Int :=
  wht8Mat r 0 * z 0 + wht8Mat r 1 * z 1 + wht8Mat r 2 * z 2 + wht8Mat r 3 * z 3 +
  wht8Mat r 4 * z 4 + wht8Mat r 5 * z 5 + wht8Mat r 6 * z 6 + wht8Mat r 7 * z 7

/-- Exact Block-H2 orthogonality: BlockH2^T * BlockH2 = 2 * I_8. -/
theorem blockH2_orthogonal_2I :
    ∀ i j : Fin 8,
      (List.finRange 8).foldl (fun acc k => acc + blockH2Mat k i * blockH2Mat k j) 0 =
        (if i == j then 2 else 0) := by
  decide

/-- Exact WHT_8 orthogonality: H_8^T * H_8 = 8 * I_8. -/
theorem wht8_orthogonal_8I :
    ∀ i j : Fin 8,
      (List.finRange 8).foldl (fun acc k => acc + wht8Mat k i * wht8Mat k j) 0 =
        (if i == j then 8 else 0) := by
  decide

private theorem int_sq_nonneg (x : Int) : 0 ≤ x * x := by
  rcases Int.le_total 0 x with h | h
  · exact Int.mul_nonneg h h
  · have hneg : 0 ≤ -x := by omega
    have hmul : 0 ≤ (-x) * (-x) := Int.mul_nonneg hneg hneg
    have heq : (-x) * (-x) = x * x := by
      rw [Int.neg_mul_neg]
    exact heq ▸ hmul

private theorem int_sq_ge_of_abs_ge (s B : Int) (hB : 0 ≤ B) (h : s ≥ B ∨ s ≤ -B) :
    s * s ≥ B * B := by
  rcases h with hpos | hneg
  · have h1 : B * B ≤ B * s := Int.mul_le_mul_of_nonneg_left hpos hB
    have h2 : B * s ≤ s * s := Int.mul_le_mul_of_nonneg_right hpos (by omega)
    exact Int.le_trans h1 h2
  · have hs : B ≤ -s := by omega
    have h1 : B * B ≤ B * (-s) := Int.mul_le_mul_of_nonneg_left hs hB
    have h2 : B * (-s) ≤ (-s) * (-s) := Int.mul_le_mul_of_nonneg_right hs (by omega)
    have heq : (-s) * (-s) = s * s := Int.neg_mul_neg s s
    exact heq ▸ Int.le_trans h1 h2

private theorem pair_sum_sq_le (a b : Int) :
    (a + b) * (a + b) ≤ 2 * (a * a + b * b) := by
  have hdiff : 0 ≤ (a - b) * (a - b) := int_sq_nonneg (a - b)
  have hid : 2 * (a * a + b * b) - (a + b) * (a + b) = (a - b) * (a - b) := by
    simp only [Int.mul_add, Int.add_mul, Int.mul_sub, Int.sub_mul]
    omega
  omega

private theorem pair_diff_sq_le (a b : Int) :
    (a - b) * (a - b) ≤ 2 * (a * a + b * b) := by
  have hsum : 0 ≤ (a + b) * (a + b) := int_sq_nonneg (a + b)
  have hid : 2 * (a * a + b * b) - (a - b) * (a - b) = (a + b) * (a + b) := by
    simp only [Int.mul_add, Int.add_mul, Int.mul_sub, Int.sub_mul]
    omega
  omega

private theorem even_sq_le_6256_bound (s : Int) (heven : s % 2 = 0) (hsq : s * s ≤ 6256) :
    -78 ≤ s ∧ s ≤ 78 := by
  have hlt80 : ¬ (s ≥ 80 ∨ s ≤ -80) := by
    intro hge
    have hbig := int_sq_ge_of_abs_ge s 80 (by omega) hge
    omega
  omega

/-- Universal Block-H2 INT8 safety and sharp 78 bound for ALL z ∈ 2*E_8 with shell m ≤ 391. -/
theorem blockH2_universal_le_78_and_int8_safe :
    ∀ z : Fin 8 → Int, IsDoubledE8 z → normSq8 z ≤ maxNormSq136b →
      ∀ r : Fin 8,
        -78 ≤ applyBlockH2 z r ∧ applyBlockH2 z r ≤ 78 ∧
        -int8Max ≤ applyBlockH2 z r ∧ applyBlockH2 z r ≤ int8Max := by
  intro z ⟨hpar, _⟩ hnorm r
  have hnn0 := int_sq_nonneg (z 0)
  have hnn1 := int_sq_nonneg (z 1)
  have hnn2 := int_sq_nonneg (z 2)
  have hnn3 := int_sq_nonneg (z 3)
  have hnn4 := int_sq_nonneg (z 4)
  have hnn5 := int_sq_nonneg (z 5)
  have hnn6 := int_sq_nonneg (z 6)
  have hnn7 := int_sq_nonneg (z 7)
  unfold normSq8 maxNormSq136b at hnorm
  have hbound : -78 ≤ applyBlockH2 z r ∧ applyBlockH2 z r ≤ 78 := by
    match r with
    | ⟨0, _⟩ =>
      simp only [applyBlockH2]
      have hp : (z 0 + z 1) % 2 = 0 := by have := hpar 1; omega
      have hs := pair_sum_sq_le (z 0) (z 1)
      exact even_sq_le_6256_bound (z 0 + z 1) hp (by omega)
    | ⟨1, _⟩ =>
      simp only [applyBlockH2]
      have hp : (z 0 - z 1) % 2 = 0 := by have := hpar 1; omega
      have hs := pair_diff_sq_le (z 0) (z 1)
      exact even_sq_le_6256_bound (z 0 - z 1) hp (by omega)
    | ⟨2, _⟩ =>
      simp only [applyBlockH2]
      have hp : (z 2 + z 3) % 2 = 0 := by have h2 := hpar 2; have h3 := hpar 3; omega
      have hs := pair_sum_sq_le (z 2) (z 3)
      exact even_sq_le_6256_bound (z 2 + z 3) hp (by omega)
    | ⟨3, _⟩ =>
      simp only [applyBlockH2]
      have hp : (z 2 - z 3) % 2 = 0 := by have h2 := hpar 2; have h3 := hpar 3; omega
      have hs := pair_diff_sq_le (z 2) (z 3)
      exact even_sq_le_6256_bound (z 2 - z 3) hp (by omega)
    | ⟨4, _⟩ =>
      simp only [applyBlockH2]
      have hp : (z 4 + z 5) % 2 = 0 := by have h4 := hpar 4; have h5 := hpar 5; omega
      have hs := pair_sum_sq_le (z 4) (z 5)
      exact even_sq_le_6256_bound (z 4 + z 5) hp (by omega)
    | ⟨5, _⟩ =>
      simp only [applyBlockH2]
      have hp : (z 4 - z 5) % 2 = 0 := by have h4 := hpar 4; have h5 := hpar 5; omega
      have hs := pair_diff_sq_le (z 4) (z 5)
      exact even_sq_le_6256_bound (z 4 - z 5) hp (by omega)
    | ⟨6, _⟩ =>
      simp only [applyBlockH2]
      have hp : (z 6 + z 7) % 2 = 0 := by have h6 := hpar 6; have h7 := hpar 7; omega
      have hs := pair_sum_sq_le (z 6) (z 7)
      exact even_sq_le_6256_bound (z 6 + z 7) hp (by omega)
    | ⟨7, _⟩ =>
      simp only [applyBlockH2]
      have hp : (z 6 - z 7) % 2 = 0 := by have h6 := hpar 6; have h7 := hpar 7; omega
      have hs := pair_diff_sq_le (z 6) (z 7)
      exact even_sq_le_6256_bound (z 6 - z 7) hp (by omega)
  unfold int8Max
  omega

/-- Exact 4-term Cauchy-Schwarz inequality over Int: (a+b+c+d)^2 ≤ 4*(a^2+b^2+c^2+d^2). -/
private theorem cs4_int (a b c d : Int) :
    (a + b + c + d) * (a + b + c + d) ≤ 4 * (a * a + b * b + c * c + d * d) := by
  have h1 := pair_sum_sq_le (a + b) (c + d)
  have h2 := pair_sum_sq_le a b
  have h3 := pair_sum_sq_le c d
  have heq : a + b + c + d = (a + b) + (c + d) := by omega
  rw [heq]
  omega

/-- Exact 8-term Cauchy-Schwarz inequality over Int: (∑ a_i)^2 ≤ 8 * ∑ a_i^2. -/
private theorem cs8_int (a0 a1 a2 a3 a4 a5 a6 a7 : Int) :
    (a0 + a1 + a2 + a3 + a4 + a5 + a6 + a7) * (a0 + a1 + a2 + a3 + a4 + a5 + a6 + a7) ≤
    8 * (a0 * a0 + a1 * a1 + a2 * a2 + a3 * a3 + a4 * a4 + a5 * a5 + a6 * a6 + a7 * a7) := by
  have h1 := pair_sum_sq_le (a0 + a1 + a2 + a3) (a4 + a5 + a6 + a7)
  have h2 := cs4_int a0 a1 a2 a3
  have h3 := cs4_int a4 a5 a6 a7
  have heq : a0 + a1 + a2 + a3 + a4 + a5 + a6 + a7 =
             (a0 + a1 + a2 + a3) + (a4 + a5 + a6 + a7) := by omega
  rw [heq]
  omega

private theorem mult4_sq_le_25024_bound (s : Int) (h4 : s % 4 = 0) (hsq : s * s ≤ 25024) :
    -156 ≤ s ∧ s ≤ 156 := by
  have hlt160 : ¬ (s ≥ 160 ∨ s ≤ -160) := by
    intro hge
    have hbig := int_sq_ge_of_abs_ge s 160 (by omega) hge
    omega
  omega

private theorem neg_mul_self (x : Int) : (-x) * (-x) = x * x :=
  Int.neg_mul_neg x x

private theorem wht8Mat_sq_one : ∀ r c : Fin 8, wht8Mat r c * wht8Mat r c = 1 := by
  decide

private theorem sign_mul_sq (s x : Int) (hs : s * s = 1) : (s * x) * (s * x) = x * x := by
  have h1 : (s * x) * (s * x) = (s * s) * (x * x) := by
    rw [Int.mul_assoc, Int.mul_left_comm x s x, ← Int.mul_assoc]
  rw [h1, hs, Int.one_mul]

private theorem wht8_row_sum_mod4_coeff :
    ∀ r : Fin 8,
      ((1 - wht8Mat r 0) / 2 + (1 - wht8Mat r 1) / 2 + (1 - wht8Mat r 2) / 2 + (1 - wht8Mat r 3) / 2 +
       (1 - wht8Mat r 4) / 2 + (1 - wht8Mat r 5) / 2 + (1 - wht8Mat r 6) / 2 + (1 - wht8Mat r 7) / 2) % 2 = 0 := by
  decide

private theorem wht8_entry_is_pm1 : ∀ r c : Fin 8, wht8Mat r c = 1 ∨ wht8Mat r c = -1 := by
  decide

private theorem wht8_term_diff_mod4 (s x p : Int) (hs : s = 1 ∨ s = -1) (hp : x % 2 = p) :
    (s * x - x + 2 * ((1 - s) / 2) * p) % 4 = 0 := by
  rcases hs with rfl | rfl
  · omega
  · have hdiv : (1 - (-1 : Int)) / 2 = 1 := rfl
    rw [hdiv]
    omega

private theorem wht8_apply_mod4 (z : Fin 8 → Int) (hE8 : IsDoubledE8 z) (r : Fin 8) :
    applyWht8 z r % 4 = 0 := by
  rcases hE8 with ⟨hpar, hsum4⟩
  have hcnt := wht8_row_sum_mod4_coeff r
  have d0 := wht8_term_diff_mod4 (wht8Mat r 0) (z 0) (z 0 % 2) (wht8_entry_is_pm1 r 0) rfl
  have d1 := wht8_term_diff_mod4 (wht8Mat r 1) (z 1) (z 0 % 2) (wht8_entry_is_pm1 r 1) (hpar 1)
  have d2 := wht8_term_diff_mod4 (wht8Mat r 2) (z 2) (z 0 % 2) (wht8_entry_is_pm1 r 2) (hpar 2)
  have d3 := wht8_term_diff_mod4 (wht8Mat r 3) (z 3) (z 0 % 2) (wht8_entry_is_pm1 r 3) (hpar 3)
  have d4 := wht8_term_diff_mod4 (wht8Mat r 4) (z 4) (z 0 % 2) (wht8_entry_is_pm1 r 4) (hpar 4)
  have d5 := wht8_term_diff_mod4 (wht8Mat r 5) (z 5) (z 0 % 2) (wht8_entry_is_pm1 r 5) (hpar 5)
  have d6 := wht8_term_diff_mod4 (wht8Mat r 6) (z 6) (z 0 % 2) (wht8_entry_is_pm1 r 6) (hpar 6)
  have d7 := wht8_term_diff_mod4 (wht8Mat r 7) (z 7) (z 0 % 2) (wht8_entry_is_pm1 r 7) (hpar 7)
  have hpar0 : z 0 % 2 = 0 ∨ z 0 % 2 = 1 := by omega
  unfold applyWht8
  rcases hpar0 with h0 | h1
  · rw [h0] at d0 d1 d2 d3 d4 d5 d6 d7
    omega
  · rw [h1] at d0 d1 d2 d3 d4 d5 d6 d7
    omega

/-- Universal WHT_8 sharp 156 upper bound for ALL z ∈ 2*E_8 with shell m ≤ 391. -/
theorem wht8_universal_le_156 :
    ∀ z : Fin 8 → Int, IsDoubledE8 z → normSq8 z ≤ maxNormSq136b →
      ∀ r : Fin 8, -156 ≤ applyWht8 z r ∧ applyWht8 z r ≤ 156 := by
  intro z hE8 hnorm r
  have hcs := cs8_int
    (wht8Mat r 0 * z 0) (wht8Mat r 1 * z 1) (wht8Mat r 2 * z 2) (wht8Mat r 3 * z 3)
    (wht8Mat r 4 * z 4) (wht8Mat r 5 * z 5) (wht8Mat r 6 * z 6) (wht8Mat r 7 * z 7)
  rw [sign_mul_sq _ _ (wht8Mat_sq_one r 0), sign_mul_sq _ _ (wht8Mat_sq_one r 1),
      sign_mul_sq _ _ (wht8Mat_sq_one r 2), sign_mul_sq _ _ (wht8Mat_sq_one r 3),
      sign_mul_sq _ _ (wht8Mat_sq_one r 4), sign_mul_sq _ _ (wht8Mat_sq_one r 5),
      sign_mul_sq _ _ (wht8Mat_sq_one r 6), sign_mul_sq _ _ (wht8Mat_sq_one r 7)] at hcs
  unfold normSq8 maxNormSq136b at hnorm
  have hsq : applyWht8 z r * applyWht8 z r ≤ 25024 := by
    unfold applyWht8
    omega
  exact mult4_sq_le_25024_bound (applyWht8 z r) (wht8_apply_mod4 z hE8 r) hsq

/-- Explicit S32 tight witness attaining Block-H2 maximum 78 at shell 381 ≤ 391. -/
def blockH2Witness : Fin 8 → Int
  | ⟨0, _⟩ => 38
  | ⟨1, _⟩ => 40
  | ⟨2, _⟩ => 2
  | _      => 0

/-- Explicit S32 tight witness attaining WHT_8 overflow 156 > 127 at shell 381 ≤ 391. -/
def wht8Witness : Fin 8 → Int
  | ⟨6, _⟩ => 18
  | ⟨7, _⟩ => 18
  | _      => 20

/-- Sharpness of Block-H2 bound: witness z_B ∈ 2*E_8 at shell 381 attains 78 ≤ 127. -/
theorem blockH2_witness_sharp_78 :
    IsDoubledE8 blockH2Witness ∧
    normSq8 blockH2Witness = 8 * 381 ∧
    normSq8 blockH2Witness ≤ maxNormSq136b ∧
    applyBlockH2 blockH2Witness 0 = 78 ∧
    applyBlockH2 blockH2Witness 0 ≤ int8Max := by
  refine ⟨⟨by decide, by decide⟩, by decide, by decide, by decide, by decide⟩

/-- Sharp separation: WHT_8 witness z_W ∈ 2*E_8 at shell 381 attains 156 > 127 (INT8 overflow). -/
theorem wht8_witness_overflow_156 :
    IsDoubledE8 wht8Witness ∧
    normSq8 wht8Witness = 8 * 381 ∧
    normSq8 wht8Witness ≤ maxNormSq136b ∧
    applyWht8 wht8Witness 0 = 156 ∧
    applyWht8 wht8Witness 0 > int8Max := by
  refine ⟨⟨by decide, by decide⟩, by decide, by decide, by decide, by decide⟩

#print axioms blockH2_orthogonal_2I
#print axioms wht8_orthogonal_8I
#print axioms blockH2_universal_le_78_and_int8_safe
#print axioms wht8_universal_le_156
#print axioms blockH2_witness_sharp_78
#print axioms wht8_witness_overflow_156

end AletheiaKernelCerts.Theorem2
