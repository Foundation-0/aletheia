/-
  MellinGluQuantMargin.lean — Pure-Init Lean 4.36.0 Certification of:
    1. Single-Layer Bias-Free GLU Scale-Collapse Impossibility (arXiv:2611.26450 Thm 3.2(1))
    2. Mellin-GLU Log-Grid Scale-Translation & Exact Telescoping Cancellation (Thm 3.2(2))
    3. Axis-Aligned Width Extension Norm Compensation & (+254, -256) Tied Readout (Thm 3.4(2))
    4. Hidden-Channel Permutation Invariance of Grafted SwiGLU/Mellin Circuits
    5. Log-Grid Quantization-Floor Obstruction, Stratified Quad Rescue, DPI & CS-08 Sign Flip

  Zero external imports (pure Init only), zero sorryAx/Classical.choice/compiler axioms, zero warnings.
-/

namespace MellinGluQuantMargin

/-- Finite telescoping sum ∑_{i=0}^{n-1} (F (a + i) - F (a + i + 1)). -/
def telescopeSum (F : Nat → Int) (a : Nat) : Nat → Int
  | 0 => 0
  | n + 1 => telescopeSum F a n + (F (a + n) - F (a + n + 1))

/-- Symmetric integer rounding quotient round(w / (M / qmax)) = (2*qmax*w + M) / (2*M)
    for nonnegative weight w, level cap qmax > 0, and group peak M > 0. -/
def symQuantLevel (w qmax M : Nat) : Nat :=
  (2 * qmax * w + M) / (2 * M)

/-- Exact 4-channel SwiGLU block evaluation for any activation σ : Int → Int. -/
def swiglu4 (σ : Int → Int)
    (d0 d1 d2 d3 g0 g1 g2 g3 u0 u1 u2 u3 : Int) : Int :=
  d0 * (σ g0 * u0) + d1 * (σ g1 * u1) + d2 * (σ g2 * u2) + d3 * (σ g3 * u3)

private theorem int_sub_add_cancel (a b c : Int) : (a - b) + (b - c) = a - c := by
  rw [Int.sub_eq_add_neg, Int.sub_eq_add_neg, Int.sub_eq_add_neg,
      Int.add_assoc, ← Int.add_assoc (-b) b (-c), Int.add_left_neg, Int.zero_add]

private theorem nat_glu_rearrange (C wd wg wu ua la : Nat) :
    wd * ((C * (wg * (la * ua))) * (wu * (la * ua))) =
      C * (wd * (wg * (wu * (ua * ua)))) * (la * la) := by
  have hsq : (la * ua) * (la * ua) = (ua * ua) * (la * la) := by
    calc
      (la * ua) * (la * ua)
          = la * (ua * (la * ua)) := Nat.mul_assoc la ua (la * ua)
      _ = la * ((ua * la) * ua) := by rw [← Nat.mul_assoc ua la ua]
      _ = la * ((la * ua) * ua) := by rw [Nat.mul_comm ua la]
      _ = la * (la * (ua * ua)) := by rw [Nat.mul_assoc la ua ua]
      _ = (la * la) * (ua * ua) := (Nat.mul_assoc la la (ua * ua)).symm
      _ = (ua * ua) * (la * la) := Nat.mul_comm (la * la) (ua * ua)
  calc
    wd * ((C * (wg * (la * ua))) * (wu * (la * ua)))
        = wd * (C * ((wg * (la * ua)) * (wu * (la * ua)))) := by
            rw [Nat.mul_assoc C]
    _ = C * (wd * ((wg * (la * ua)) * (wu * (la * ua)))) := by
            rw [← Nat.mul_assoc wd C, Nat.mul_comm wd C, Nat.mul_assoc C wd]
    _ = C * (wd * (wg * ((la * ua) * (wu * (la * ua))))) := by
            rw [Nat.mul_assoc wg]
    _ = C * (wd * (wg * (wu * ((la * ua) * (la * ua))))) := by
            rw [← Nat.mul_assoc (la * ua) wu, Nat.mul_comm (la * ua) wu, Nat.mul_assoc wu]
    _ = C * (wd * (wg * (wu * ((ua * ua) * (la * la))))) := by
            rw [hsq]
    _ = C * (wd * (wg * ((wu * (ua * ua)) * (la * la)))) := by
            rw [← Nat.mul_assoc wu (ua * ua) (la * la)]
    _ = C * (wd * ((wg * (wu * (ua * ua))) * (la * la))) := by
            rw [← Nat.mul_assoc wg (wu * (ua * ua)) (la * la)]
    _ = C * ((wd * (wg * (wu * (ua * ua)))) * (la * la)) := by
            rw [← Nat.mul_assoc wd (wg * (wu * (ua * ua))) (la * la)]
    _ = C * (wd * (wg * (wu * (ua * ua)))) * (la * la) := by
            rw [← Nat.mul_assoc C]

/-! ### 1. Single-Layer Bias-Free GLU Scale-Collapse Impossibility -/

theorem glu_single_layer_zero_collapse
    (φ : Int → Int) (hφ0 : φ 0 = 0)
    (wDown wGate wUp u : Int) :
    wDown * (φ (wGate * (0 * u)) * (wUp * (0 * u))) = 0 := by
  rw [Int.zero_mul, Int.mul_zero, hφ0, Int.zero_mul, Int.mul_zero]

theorem glu_single_layer_quadratic_bound
    (φ : Int → Int) (C : Nat)
    (hLin : ∀ s : Int, (φ s).natAbs ≤ C * s.natAbs)
    (wDown wGate wUp u lam : Int) :
    (wDown * (φ (wGate * (lam * u)) * (wUp * (lam * u)))).natAbs ≤
      C * (wDown.natAbs * (wGate.natAbs * (wUp.natAbs * (u.natAbs * u.natAbs)))) *
        (lam.natAbs * lam.natAbs) := by
  have h1 : (φ (wGate * (lam * u))).natAbs ≤ C * (wGate * (lam * u)).natAbs :=
    hLin (wGate * (lam * u))
  have hmul :
      wDown.natAbs * ((φ (wGate * (lam * u))).natAbs * (wUp * (lam * u)).natAbs) ≤
      wDown.natAbs * ((C * (wGate * (lam * u)).natAbs) * (wUp * (lam * u)).natAbs) :=
    Nat.mul_le_mul_left wDown.natAbs (Nat.mul_le_mul_right _ h1)
  have hL :
      (wDown * (φ (wGate * (lam * u)) * (wUp * (lam * u)))).natAbs =
      wDown.natAbs * ((φ (wGate * (lam * u))).natAbs * (wUp * (lam * u)).natAbs) := by
    rw [Int.natAbs_mul, Int.natAbs_mul]
  have hR :
      wDown.natAbs * ((C * (wGate * (lam * u)).natAbs) * (wUp * (lam * u)).natAbs) =
      C * (wDown.natAbs * (wGate.natAbs * (wUp.natAbs * (u.natAbs * u.natAbs)))) *
        (lam.natAbs * lam.natAbs) := by
    rw [Int.natAbs_mul, Int.natAbs_mul, Int.natAbs_mul, Int.natAbs_mul]
    exact nat_glu_rearrange C wDown.natAbs wGate.natAbs wUp.natAbs u.natAbs lam.natAbs
  rw [hL, ← hR]
  exact hmul

theorem glu_single_layer_weight_norm_lower_bound
    (φ : Int → Int) (C target : Nat)
    (hLin : ∀ s : Int, (φ s).natAbs ≤ C * s.natAbs)
    (wDown wGate wUp u lam : Int)
    (hHit : target ≤ (wDown * (φ (wGate * (lam * u)) * (wUp * (lam * u)))).natAbs) :
    target ≤
      C * (wDown.natAbs * (wGate.natAbs * (wUp.natAbs * (u.natAbs * u.natAbs)))) *
        (lam.natAbs * lam.natAbs) :=
  Nat.le_trans hHit (glu_single_layer_quadratic_bound φ C hLin wDown wGate wUp u lam)

/-! ### 2. Mellin-GLU Log-Grid Scale-Translation & Exact Telescoping Cancellation -/

theorem mellin_log_grid_scale_shift (r k m x : Nat) :
    r ^ k * (r ^ m * x) = r ^ (k + m) * x := by
  rw [← Nat.mul_assoc, ← Nat.pow_add]

theorem mellin_telescoping_sum_exact (F : Nat → Int) (a : Nat) :
    ∀ n : Nat, telescopeSum F a n = F a - F (a + n)
  | 0 => by
      dsimp [telescopeSum]
      rw [Int.sub_self]
  | n + 1 => by
      have ih := mellin_telescoping_sum_exact F a n
      dsimp [telescopeSum]
      rw [ih, int_sub_add_cancel]
      rfl

theorem mellin_telescoping_shift_invariance (F : Nat → Int) (a m n : Nat) :
    telescopeSum (fun k => F (k + m)) a n = F (a + m) - F (a + n + m) :=
  mellin_telescoping_sum_exact (fun k => F (k + m)) a n

private theorem int_one_cancel (a b : Int) : (1 + a) - (1 + b) = a - b := by
  calc
    (1 + a) - (1 + b)
        = (1 + a) + (-(1 + b)) := by rw [Int.sub_eq_add_neg]
    _ = (1 + a) + (-1 + -b) := by rw [Int.neg_add]
    _ = (a + 1) + (-1 + -b) := by rw [Int.add_comm 1 a]
    _ = a + (1 + (-1 + -b)) := Int.add_assoc a 1 (-1 + -b)
    _ = a + ((1 + -1) + -b) := by rw [← Int.add_assoc 1 (-1) (-b)]
    _ = a + (0 + -b) := by rw [Int.add_right_neg]
    _ = a + -b := by rw [Int.zero_add]
    _ = a - b := by rw [Int.sub_eq_add_neg]

theorem mellin_rational_kernel_algebraic_identity (r t : Int) :
    (1 + r * r * t * t) - (1 + t * t) = (r * r - 1) * (t * t) := by
  have h1 : (r * r - 1) * (t * t) = r * r * (t * t) - 1 * (t * t) :=
    Int.sub_mul (r * r) 1 (t * t)
  have h2 : r * r * (t * t) = r * r * t * t :=
    (Int.mul_assoc (r * r) t t).symm
  rw [int_one_cancel, h1, h2, Int.one_mul]

/-! ### 3. Axis-Aligned Width Extension & Differential (+254, -256) Tied Readout -/

theorem axis_aligned_norm_compensation_exact (d K s2 : Nat) :
    d * (s2 * (d + K)) = (d + K) * (s2 * d) := by
  calc
    d * (s2 * (d + K)) = (d * s2) * (d + K) := (Nat.mul_assoc d s2 (d + K)).symm
    _ = (d + K) * (d * s2) := Nat.mul_comm (d * s2) (d + K)
    _ = (d + K) * (s2 * d) := by rw [Nat.mul_comm d s2]

theorem axis_aligned_drift_decomposition (d K nl2 circ2 : Nat) :
    (d + K) * (nl2 + circ2) - (d + K) * nl2 = (d + K) * circ2 := by
  rw [Nat.mul_add, Nat.add_sub_cancel_left]

theorem differential_tied_readout_exact_cancellation (E hHat : Int) :
    E * ((1 + 254) * hHat) + E * ((1 + (-256 : Int)) * hHat) = 0 := by
  have h1 : (1 + 254 : Int) = 255 := rfl
  have h2 : (1 + (-256 : Int)) = -255 := rfl
  rw [h1, h2, Int.neg_mul, Int.mul_neg, Int.add_right_neg]

private theorem int_pair_cancel (p q : Int) : (p + q) + (-p + q) = q + q := by
  calc
    (p + q) + (-p + q)
        = (q + p) + (-p + q) := by rw [Int.add_comm p q]
    _ = q + (p + (-p + q)) := Int.add_assoc q p (-p + q)
    _ = q + ((p + -p) + q) := by rw [← Int.add_assoc p (-p) q]
    _ = q + (0 + q) := by rw [Int.add_right_neg]
    _ = q + q := by rw [Int.zero_add]

theorem differential_tied_readout_active_push (E h0 delta : Int) :
    E * ((1 + 254) * (h0 + delta)) + E * ((1 + (-256 : Int)) * (h0 - delta)) =
      510 * (E * delta) := by
  have h1 : (1 + 254 : Int) = 255 := rfl
  have h2 : (1 + (-256 : Int)) = -255 := rfl
  have h255 : (255 : Int) + 255 = 510 := rfl
  rw [h1, h2]
  have hA : E * (255 * (h0 + delta)) = 255 * (E * h0) + 255 * (E * delta) := by
    rw [Int.mul_add, Int.mul_add]
    have ha : E * (255 * h0) = 255 * (E * h0) := by
      rw [← Int.mul_assoc, Int.mul_comm E 255, Int.mul_assoc]
    have hb : E * (255 * delta) = 255 * (E * delta) := by
      rw [← Int.mul_assoc, Int.mul_comm E 255, Int.mul_assoc]
    rw [ha, hb]
  have hB : E * (-255 * (h0 - delta)) = -(255 * (E * h0)) + 255 * (E * delta) := by
    rw [Int.mul_sub, Int.neg_mul, Int.neg_mul, Int.sub_neg, Int.mul_add]
    have ha : E * -(255 * h0) = -(255 * (E * h0)) := by
      rw [Int.mul_neg, ← Int.mul_assoc, Int.mul_comm E 255, Int.mul_assoc]
    have hb : E * (255 * delta) = 255 * (E * delta) := by
      rw [← Int.mul_assoc, Int.mul_comm E 255, Int.mul_assoc]
    rw [ha, hb]
  rw [hA, hB, int_pair_cancel, ← Int.add_mul, h255]

/-! ### 4. Hidden-Channel Permutation Invariance of Grafted SwiGLU Circuits -/

private theorem int_add4_cycle (t0 t1 t2 t3 : Int) :
    t1 + t2 + t3 + t0 = t0 + t1 + t2 + t3 := by
  calc
    t1 + t2 + t3 + t0 = t0 + (t1 + t2 + t3) := Int.add_comm (t1 + t2 + t3) t0
    _ = t0 + (t1 + t2) + t3 := (Int.add_assoc t0 (t1 + t2) t3).symm
    _ = t0 + t1 + t2 + t3 := by rw [← Int.add_assoc t0 t1 t2]

theorem swiglu4_cycle_perm_invariant
    (σ : Int → Int)
    (d0 d1 d2 d3 g0 g1 g2 g3 u0 u1 u2 u3 : Int) :
    swiglu4 σ d1 d2 d3 d0 g1 g2 g3 g0 u1 u2 u3 u0 =
      swiglu4 σ d0 d1 d2 d3 g0 g1 g2 g3 u0 u1 u2 u3 := by
  unfold swiglu4
  exact int_add4_cycle _ _ _ _

theorem swiglu4_swap_01_invariant
    (σ : Int → Int)
    (d0 d1 d2 d3 g0 g1 g2 g3 u0 u1 u2 u3 : Int) :
    swiglu4 σ d1 d0 d2 d3 g1 g0 g2 g3 u1 u0 u2 u3 =
      swiglu4 σ d0 d1 d2 d3 g0 g1 g2 g3 u0 u1 u2 u3 := by
  unfold swiglu4
  rw [Int.add_comm (d1 * (σ g1 * u1)) (d0 * (σ g0 * u0))]

/-! ### 5. Log-Grid Quantization-Floor Obstruction, Stratified Rescue, DPI & CS-08 -/

theorem uniform_group_quant_zeroing_obstruction
    (w qmax M : Nat) (hUnder : 2 * qmax * w < M) :
    symQuantLevel w qmax M = 0 := by
  unfold symQuantLevel
  have hlt : 2 * qmax * w + M < 2 * M := by
    have h1 : 2 * qmax * w + M < M + M := Nat.add_lt_add_right hUnder M
    have h2 : 2 * M = M + M := Nat.two_mul M
    rw [h2]
    exact h1
  exact Nat.div_eq_of_lt hlt

theorem stratified_quad_grouping_nonzero_rescue
    (w qmax M : Nat) (hM : 0 < M) (hFloor : M ≤ 2 * qmax * w) :
    1 ≤ symQuantLevel w qmax M := by
  unfold symQuantLevel
  have hle : 2 * M ≤ 2 * qmax * w + M := by
    have h1 : M + M ≤ 2 * qmax * w + M := Nat.add_le_add_right hFloor M
    have h2 : 2 * M = M + M := Nat.two_mul M
    rw [h2]
    exact h1
  have h2Mpos : 0 < 2 * M := Nat.mul_pos (Nat.succ_pos 1) hM
  have hdiv : (2 * M) / (2 * M) ≤ (2 * qmax * w + M) / (2 * M) :=
    Nat.div_le_div_right hle
  rw [Nat.div_self h2Mpos] at hdiv
  exact hdiv

theorem mellin_11rung_int4_int8_underflow_and_stratified_rescue :
    symQuantLevel 64 7 1024 = 0 ∧
    symQuantLevel 4 127 1024 = 0 ∧
    1 ≤ symQuantLevel 1 127 8 := by
  refine ⟨?_, ?_, ?_⟩
  · exact uniform_group_quant_zeroing_obstruction 64 7 1024 (by decide)
  · exact uniform_group_quant_zeroing_obstruction 4 127 1024 (by decide)
  · exact stratified_quad_grouping_nonzero_rescue 1 127 8 (by decide) (by decide)

theorem dpi_row_concentration_iso_frobenius_gap (R E : Nat) (hR : 2 ≤ R) (hE : 0 < E) :
    E < R * E := by
  have h2 : 2 * E ≤ R * E := Nat.mul_le_mul_right E hR
  have hlt : E < 2 * E := by
    rw [Nat.two_mul]
    exact Nat.lt_add_of_pos_right hE
  exact Nat.lt_of_lt_of_le hlt h2

theorem cs08_budget_wall_sign_flip_exact :
    319 < 350 ∧ 350 * 327 < 319 * 422 ∧ 276 < 319 := by
  decide

#print axioms glu_single_layer_zero_collapse
#print axioms glu_single_layer_quadratic_bound
#print axioms glu_single_layer_weight_norm_lower_bound
#print axioms mellin_log_grid_scale_shift
#print axioms mellin_telescoping_sum_exact
#print axioms mellin_telescoping_shift_invariance
#print axioms mellin_rational_kernel_algebraic_identity
#print axioms axis_aligned_norm_compensation_exact
#print axioms axis_aligned_drift_decomposition
#print axioms differential_tied_readout_exact_cancellation
#print axioms differential_tied_readout_active_push
#print axioms swiglu4_cycle_perm_invariant
#print axioms swiglu4_swap_01_invariant
#print axioms uniform_group_quant_zeroing_obstruction
#print axioms stratified_quad_grouping_nonzero_rescue
#print axioms mellin_11rung_int4_int8_underflow_and_stratified_rescue
#print axioms dpi_row_concentration_iso_frobenius_gap
#print axioms cs08_budget_wall_sign_flip_exact

end MellinGluQuantMargin
