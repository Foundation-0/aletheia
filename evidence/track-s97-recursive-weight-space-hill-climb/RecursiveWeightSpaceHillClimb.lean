/-
  Track S97: ALETHEIA-WSE-HC — Recursive Weight-Space Editing Hill-Climb Companion
  Pure-Init Lean 4.36.0 Formalization (0 external imports, 0 Classical.choice, 0 sorry)
  All 18 theorems are universally quantified over arbitrary natural/integer parameters.
-/

namespace TrackS97RecursiveWSEHC

-- ============================================================================
-- Helper definitions (pure Init, zero floats, zero external libraries)
-- ============================================================================

/-- Discrete non-differentiable step oracle: 1 if weight >= threshold else 0. -/
def stepOracle (tau w : Int) : Nat :=
  if w >= tau then 1 else 0

/-- 2D integer-scaled Householder reflection: H_u(x) = ||u||^2 * x - 2 * <u, x> * u. -/
def householder2X (u0 u1 x0 x1 : Int) : Int :=
  (u0 * u0 + u1 * u1) * x0 - 2 * (u0 * x0 + u1 * x1) * u0

def householder2Y (u0 u1 x0 x1 : Int) : Int :=
  (u0 * u0 + u1 * u1) * x1 - 2 * (u0 * x0 + u1 * x1) * u1

/-- 2D integer-scaled orthogonal nullspace projection onto ker(x^T):
    P_perp(w; x) = ||x||^2 * w - <w, x> * x. -/
def nullProj2X (x0 x1 w0 w1 : Int) : Int :=
  (x0 * x0 + x1 * x1) * w0 - (w0 * x0 + w1 * x1) * x0

def nullProj2Y (x0 x1 w0 w1 : Int) : Int :=
  (x0 * x0 + x1 * x1) * w1 - (w0 * x0 + w1 * x1) * x1

/-- 5-gate Aletheia ratchet acceptance predicate (integer/rational scaled). -/
def fiveGateAccept
    (targetOld targetNew baseOld baseNew epsDrift dpiNew dpiMax : Nat)
    (oracleOk : Bool) : Bool :=
  decide (targetNew >= targetOld) &&
  decide (baseNew <= baseOld + epsDrift) &&
  decide (dpiNew <= dpiMax) &&
  oracleOk

/-- Natural power helper (pure Init). -/
def natPow (b : Nat) : Nat -> Nat
  | 0 => 1
  | n + 1 => b * natPow b n

-- ============================================================================
-- Block A: Subspace Dimensionality Collapse & Privileged-Basis SNR Lift (1-4)
-- ============================================================================

/-- Thm 1: Universal SNR collapse of D-dim isotropic ES vs d-dim privileged subspace.
    For any d < D and signal energy s > 0, cross-multiplied subspace SNR (s / d)
    strictly dominates isotropic SNR (s / D), i.e., s * D > s * d, with exact gap (D - d) * s > 0. -/
theorem thm01_isotropic_es_snr_collapse_universal
    (D d s : Nat) (hlt : d < D) (hs : 0 < s) :
    s * D > s * d /\ (D - d) * s > 0 /\ s * D = s * d + (D - d) * s := by
  have h1 : s * D > s * d := Nat.mul_lt_mul_of_pos_left hlt hs
  have hsub : D - d > 0 := Nat.sub_pos_of_lt hlt
  have h2 : (D - d) * s > 0 := Nat.mul_pos hsub hs
  have hadd : d + (D - d) = D := Nat.add_sub_of_le (Nat.le_of_lt hlt)
  have h3 : s * D = s * d + (D - d) * s := by
    calc s * D = s * (d + (D - d)) := by rw [hadd]
      _ = s * d + s * (D - d) := Nat.mul_add s d (D - d)
      _ = s * d + (D - d) * s := by rw [Nat.mul_comm s (D - d)]
  exact ⟨h1, ⟨h2, h3⟩⟩

/-- Thm 2: Universal exact Householder isometry over Z (kappa_2 = 1).
    ||H_u(x)||^2 = ||u||^4 * ||x||^2 for all u, x in Z^2. -/
theorem thm02_householder_exact_isometry_norm_preserving
    (u0 u1 x0 x1 : Int) :
    (householder2X u0 u1 x0 x1) * (householder2X u0 u1 x0 x1) +
    (householder2Y u0 u1 x0 x1) * (householder2Y u0 u1 x0 x1) =
    (u0 * u0 + u1 * u1) * (u0 * u0 + u1 * u1) * (x0 * x0 + x1 * x1) := by
  simp only [householder2X, householder2Y]
  have h :
      ((u0 * u0 + u1 * u1) * x0 - 2 * (u0 * x0 + u1 * x1) * u0) *
      ((u0 * u0 + u1 * u1) * x0 - 2 * (u0 * x0 + u1 * x1) * u0) +
      ((u0 * u0 + u1 * u1) * x1 - 2 * (u0 * x0 + u1 * x1) * u1) *
      ((u0 * u0 + u1 * u1) * x1 - 2 * (u0 * x0 + u1 * x1) * u1) =
      (u0 * u0 + u1 * u1) * (u0 * u0 + u1 * u1) * (x0 * x0 + x1 * x1) := by
    have ha : (u0 * u0 + u1 * u1) * x0 - 2 * (u0 * x0 + u1 * x1) * u0 =
              (u1 * u1 - u0 * u0) * x0 - 2 * u0 * u1 * x1 := by
      simp only [Int.add_mul, Int.mul_add, Int.sub_mul]
      have c1 : 2 * (u0 * x0) * u0 = 2 * (u0 * u0 * x0) := by ac_rfl
      have c2 : 2 * (u1 * x1) * u0 = 2 * u0 * u1 * x1 := by ac_rfl
      rw [c1, c2]
      omega
    have hb : (u0 * u0 + u1 * u1) * x1 - 2 * (u0 * x0 + u1 * x1) * u1 =
              (u0 * u0 - u1 * u1) * x1 - 2 * u0 * u1 * x0 := by
      simp only [Int.add_mul, Int.mul_add, Int.sub_mul]
      have c1 : 2 * (u1 * x1) * u1 = 2 * (u1 * u1 * x1) := by ac_rfl
      have c2 : 2 * (u0 * x0) * u1 = 2 * u0 * u1 * x0 := by ac_rfl
      rw [c1, c2]
      omega
    rw [ha, hb]
    let a := u1 * u1 - u0 * u0
    let b := 2 * u0 * u1
    have hna : u0 * u0 - u1 * u1 = -a := by omega
    rw [hna]
    have hsum : (a * x0 - b * x1) * (a * x0 - b * x1) +
                ((-a) * x1 - b * x0) * ((-a) * x1 - b * x0) =
                (a * a + b * b) * (x0 * x0 + x1 * x1) := by
      have h1 : (a * x0 - b * x1) * (a * x0 - b * x1) =
                a * a * (x0 * x0) - 2 * (a * b * x0 * x1) + b * b * (x1 * x1) := by
        simp only [Int.sub_mul, Int.mul_sub]
        have t1 : a * x0 * (a * x0) = a * a * (x0 * x0) := by ac_rfl
        have t2 : b * x1 * (b * x1) = b * b * (x1 * x1) := by ac_rfl
        have t3 : a * x0 * (b * x1) = a * b * x0 * x1 := by ac_rfl
        have t4 : b * x1 * (a * x0) = a * b * x0 * x1 := by ac_rfl
        rw [t1, t2, t3, t4]
        omega
      have h2 : ((-a) * x1 - b * x0) * ((-a) * x1 - b * x0) =
                a * a * (x1 * x1) + 2 * (a * b * x0 * x1) + b * b * (x0 * x0) := by
        simp only [Int.sub_mul, Int.mul_sub, Int.neg_mul, Int.mul_neg]
        have t1 : a * x1 * (a * x1) = a * a * (x1 * x1) := by ac_rfl
        have t2 : b * x0 * (b * x0) = b * b * (x0 * x0) := by ac_rfl
        have t3 : a * x1 * (b * x0) = a * b * x0 * x1 := by ac_rfl
        have t4 : b * x0 * (a * x1) = a * b * x0 * x1 := by ac_rfl
        rw [t1, t2, t3, t4]
        omega
      rw [h1, h2]
      have h3 : (a * a + b * b) * (x0 * x0 + x1 * x1) =
                a * a * (x0 * x0) + a * a * (x1 * x1) + b * b * (x0 * x0) + b * b * (x1 * x1) := by
        simp only [Int.add_mul, Int.mul_add]
        omega
      rw [h3]
      omega
    have hab : a * a + b * b = (u0 * u0 + u1 * u1) * (u0 * u0 + u1 * u1) := by
      dsimp only [a, b]
      simp only [Int.sub_mul, Int.mul_sub, Int.add_mul, Int.mul_add]
      have p1 : u0 * u0 * (u1 * u1) = u0 * u1 * (u0 * u1) := by ac_rfl
      have p2 : u1 * u1 * (u0 * u0) = u0 * u1 * (u0 * u1) := by ac_rfl
      have p3 : 2 * u0 * u1 * (2 * u0 * u1) = 4 * (u0 * u1 * (u0 * u1)) := by
        have q1 : 2 * u0 * u1 * (2 * u0 * u1) = (2 * 2) * (u0 * u1 * (u0 * u1)) := by ac_rfl
        rw [q1]
        rfl
      rw [p1, p2, p3]
      omega
    rw [hsum, hab]
  exact h

/-- Thm 3: Universal exact Householder involution over Z (Q^2 = I).
    H_u(H_u(x)) = ||u||^4 * x for all u, x in Z^2. -/
theorem thm03_householder_exact_involution
    (u0 u1 x0 x1 : Int) :
    householder2X u0 u1 (householder2X u0 u1 x0 x1) (householder2Y u0 u1 x0 x1) =
      (u0 * u0 + u1 * u1) * (u0 * u0 + u1 * u1) * x0 /\
    householder2Y u0 u1 (householder2X u0 u1 x0 x1) (householder2Y u0 u1 x0 x1) =
      (u0 * u0 + u1 * u1) * (u0 * u0 + u1 * u1) * x1 := by
  let s := u0 * u0 + u1 * u1
  let d := u0 * x0 + u1 * x1
  have hdot : u0 * (s * x0 - 2 * d * u0) + u1 * (s * x1 - 2 * d * u1) = -(s * d) := by
    simp only [Int.mul_sub]
    have t1 : u0 * (s * x0) = s * (u0 * x0) := by ac_rfl
    have t2 : u1 * (s * x1) = s * (u1 * x1) := by ac_rfl
    have t3 : u0 * (2 * d * u0) = 2 * d * (u0 * u0) := by ac_rfl
    have t4 : u1 * (2 * d * u1) = 2 * d * (u1 * u1) := by ac_rfl
    have t5 : s * (u0 * x0) + s * (u1 * x1) = s * d := by
      dsimp only [d]; rw [<- Int.mul_add]
    have t6 : 2 * d * (u0 * u0) + 2 * d * (u1 * u1) = 2 * (s * d) := by
      have q : 2 * d * (u0 * u0) + 2 * d * (u1 * u1) = 2 * d * s := by
        dsimp only [s]; rw [<- Int.mul_add]
      rw [q]; ac_rfl
    rw [t1, t2, t3, t4]
    omega
  have hx : householder2X u0 u1 (householder2X u0 u1 x0 x1) (householder2Y u0 u1 x0 x1) =
            s * s * x0 := by
    simp only [householder2X, householder2Y]
    change s * (s * x0 - 2 * d * u0) - 2 * (u0 * (s * x0 - 2 * d * u0) + u1 * (s * x1 - 2 * d * u1)) * u0 = s * s * x0
    rw [hdot]
    simp only [Int.mul_sub, Int.mul_neg, Int.neg_mul]
    have c1 : s * (s * x0) = s * s * x0 := by ac_rfl
    have c2 : s * (2 * d * u0) = 2 * (s * d) * u0 := by ac_rfl
    rw [c1, c2]
    omega
  have hy : householder2Y u0 u1 (householder2X u0 u1 x0 x1) (householder2Y u0 u1 x0 x1) =
            s * s * x1 := by
    simp only [householder2X, householder2Y]
    change s * (s * x1 - 2 * d * u1) - 2 * (u0 * (s * x0 - 2 * d * u0) + u1 * (s * x1 - 2 * d * u1)) * u1 = s * s * x1
    rw [hdot]
    simp only [Int.mul_sub, Int.mul_neg, Int.neg_mul]
    have c1 : s * (s * x1) = s * s * x1 := by ac_rfl
    have c2 : s * (2 * d * u1) = 2 * (s * d) * u1 := by ac_rfl
    rw [c1, c2]
    omega
  exact ⟨hx, hy⟩

/-- Thm 4: Universal 4-point BlockH4 Parseval exact energy conservation over Z. -/
theorem thm04_blockh4_parseval_exact_energy
    (x0 x1 x2 x3 : Int) :
    (x0 + x1 + x2 + x3) * (x0 + x1 + x2 + x3) +
    (x0 - x1 + x2 - x3) * (x0 - x1 + x2 - x3) +
    (x0 + x1 - x2 - x3) * (x0 + x1 - x2 - x3) +
    (x0 - x1 - x2 + x3) * (x0 - x1 - x2 + x3) =
    4 * (x0 * x0 + x1 * x1 + x2 * x2 + x3 * x3) := by
  let a := x0 + x2
  let b := x1 + x3
  let c := x0 - x2
  let d := x1 - x3
  have e1 : x0 + x1 + x2 + x3 = a + b := by dsimp only [a, b]; omega
  have e2 : x0 - x1 + x2 - x3 = a - b := by dsimp only [a, b]; omega
  have e3 : x0 + x1 - x2 - x3 = c + d := by dsimp only [c, d]; omega
  have e4 : x0 - x1 - x2 + x3 = c - d := by dsimp only [c, d]; omega
  rw [e1, e2, e3, e4]
  have p2 : ∀ u v : Int, (u + v) * (u + v) + (u - v) * (u - v) = 2 * (u * u + v * v) := by
    intro u v
    simp only [Int.add_mul, Int.mul_add, Int.sub_mul, Int.mul_sub]
    have hcomm : v * u = u * v := Int.mul_comm v u
    rw [hcomm]
    omega
  have hab := p2 a b
  have hcd := p2 c d
  have s1 : a * a + c * c = 2 * (x0 * x0 + x2 * x2) := p2 x0 x2
  have s2 : b * b + d * d = 2 * (x1 * x1 + x3 * x3) := p2 x1 x3
  omega

-- ============================================================================
-- Block B: Non-Differentiable Discrete-Oracle Dominance & DPI Bound (5-8)
-- ============================================================================

/-- Thm 5: Universal discrete step-oracle gradient blindness vs hill-climb progress.
    For any w < tau, small perturbation eps with w + eps < tau has 0 finite difference
    (backprop blind), whereas discrete jump delta with w + delta >= tau achieves +1 gain. -/
theorem thm05_step_oracle_zero_gradient_vs_hillclimb_progress
    (tau w eps delta : Int)
    (hbelow : w < tau) (hsmall : w + eps < tau) (hjump : w + delta >= tau) :
    stepOracle tau (w + eps) = stepOracle tau w /\
    stepOracle tau (w + delta) = stepOracle tau w + 1 := by
  unfold stepOracle
  have h1 : ¬ (w >= tau) := by omega
  have h2 : ¬ (w + eps >= tau) := by omega
  have h3 : w + delta >= tau := hjump
  have g1 : (if w + eps >= tau then 1 else 0) = (if w >= tau then 1 else 0) := by
    simp only [h1, h2, ite_false]
  have g2 : (if w + delta >= tau then 1 else 0) = (if w >= tau then 1 else 0) + 1 := by
    simp only [h1, h3, ite_false, ite_true]
  exact ⟨g1, g2⟩

/-- Thm 6: Universal discrete quantized-lattice monotone hill-climb ratchet.
    Any monotone ratcheted chain s0 < s1 <= s2 <= smax preserves strict improvement
    and strictly shrinks the optimality gap. -/
theorem thm06_discrete_lattice_grid_monotone_ratchet
    (s0 s1 s2 smax : Nat)
    (hgain : s0 < s1) (hmono : s1 <= s2) (hbound : s2 <= smax) :
    s0 < s2 /\ smax - s2 <= smax - s1 /\ smax - s1 < smax - s0 := by
  exact ⟨by omega, ⟨by omega, by omega⟩⟩

/-- Thm 7: Universal Track S31 DPI concentration ceiling preservation.
    For any parameter count N > 0, support sizes k1 < k2, and ceiling tau:
    expanding active edit support strictly lowers concentration ratio (N/k2 < N/k1)
    and preserves any concentration ceiling N <= tau * k1. -/
theorem thm07_dpi_concentration_bound_preserved
    (N k1 k2 tau : Nat)
    (hN : 0 < N) (hgrow : k1 < k2) (hceil : N <= tau * k1) :
    N * k1 < N * k2 /\ N <= tau * k2 := by
  have h1 : N * k1 < N * k2 := Nat.mul_lt_mul_of_pos_left hgrow hN
  have h2 : tau * k1 <= tau * k2 := Nat.mul_le_mul_left tau (Nat.le_of_lt hgrow)
  exact ⟨h1, Nat.le_trans hceil h2⟩

/-- Thm 8: Universal surrogate-vs-discrete Goodhart rejection separation.
    Even when a differentiable surrogate strictly drops (surrNew < surrOld, so
    surrogate descent accepts), if the discrete oracle regresses (targetNew < targetOld),
    the 5-gate ratchet strictly rejects. -/
theorem thm08_surrogate_goodhart_rejected_by_ratchet
    (surrOld surrNew targetOld targetNew baseOld baseNew eps dpiNew dpiMax : Nat)
    (hsurr : surrNew < surrOld) (hreg : targetNew < targetOld) (oracleOk : Bool) :
    decide (surrNew < surrOld) = true /\
    fiveGateAccept targetOld targetNew baseOld baseNew eps dpiNew dpiMax oracleOk = false := by
  have hacc : decide (surrNew < surrOld) = true := decide_eq_true hsurr
  have hrej : fiveGateAccept targetOld targetNew baseOld baseNew eps dpiNew dpiMax oracleOk = false := by
    unfold fiveGateAccept
    have hnot : ¬ (targetNew >= targetOld) := by omega
    have hdec : decide (targetNew >= targetOld) = false := decide_eq_false hnot
    rw [hdec]
    rfl
  exact ⟨hacc, hrej⟩

-- ============================================================================
-- Block C: Anti-Goodhart Ratchet & Nullspace Anti-Forgetting (9-13)
-- ============================================================================

/-- Thm 9: Universal unratcheted FWER strict inflation (Track S80 songe law).
    For any per-step non-false-positive rate 0 < q < D (q/D < 1), each additional
    unratcheted step strictly decreases the joint clean survival probability (q/D)^n
    and strictly increases 2-step vs 1-step FWER. -/
theorem thm09_unratcheted_fwer_strictly_grows
    (q D n : Nat) (hq : 0 < q) (hlt : q < D) :
    natPow q (n + 1) < D * natPow q n /\
    (D - q) * D < D * D - q * q := by
  have hpowPos : ∀ m : Nat, 0 < natPow q m := by
    intro m
    induction m with
    | zero => exact Nat.zero_lt_one
    | succ k ih => exact Nat.mul_pos hq ih
  have h1 : natPow q (n + 1) < D * natPow q n := by
    change q * natPow q n < D * natPow q n
    exact Nat.mul_lt_mul_of_pos_right hlt (hpowPos n)
  have h2 : (D - q) * D < D * D - q * q := by
    have hqq : q * q < q * D := Nat.mul_lt_mul_of_pos_left hlt hq
    have hle1 : q * D <= D * D := Nat.mul_le_mul_right D (Nat.le_of_lt hlt)
    have hsubmul : (D - q) * D = D * D - q * D := Nat.sub_mul D q D
    rw [hsubmul]
    omega
  exact ⟨h1, h2⟩

/-- Thm 10: Universal 2-step (transitive) 5-gate Aletheia ratchet invariance.
    If two consecutive transitions pass fiveGateAccept, target score is monotone
    (t0 <= t2), base drift is bounded by 2 * eps, and zero-drift eps = 0 enforces b2 <= b0. -/
theorem thm10_five_gate_ratchet_zero_regression_invariant
    (t0 t1 t2 b0 b1 b2 eps d1 d2 dmax : Nat)
    (h1 : fiveGateAccept t0 t1 b0 b1 eps d1 dmax true = true)
    (h2 : fiveGateAccept t1 t2 b1 b2 eps d2 dmax true = true) :
    t0 <= t2 /\ b2 <= b0 + 2 * eps /\ (eps = 0 -> b2 <= b0) := by
  unfold fiveGateAccept at h1 h2
  have p1 : (t1 >= t0) /\ (b1 <= b0 + eps) := by
    cases c1 : decide (t1 >= t0) <;>
    cases c2 : decide (b1 <= b0 + eps) <;>
    cases c3 : decide (d1 <= dmax)
    all_goals simp only [c1, c2, c3, Bool.and_true, Bool.and_false] at h1
    all_goals try exact Bool.noConfusion h1
    exact ⟨of_decide_eq_true c1, of_decide_eq_true c2⟩
  have p2 : (t2 >= t1) /\ (b2 <= b1 + eps) := by
    cases c1 : decide (t2 >= t1) <;>
    cases c2 : decide (b2 <= b1 + eps) <;>
    cases c3 : decide (d2 <= dmax)
    all_goals simp only [c1, c2, c3, Bool.and_true, Bool.and_false] at h2
    all_goals try exact Bool.noConfusion h2
    exact ⟨of_decide_eq_true c1, of_decide_eq_true c2⟩
  rcases p1 with ⟨ht1, hb1⟩
  rcases p2 with ⟨ht2, hb2⟩
  exact ⟨by omega, ⟨by omega, fun he => by omega⟩⟩

/-- Thm 11: Universal exact zero base-task interference under nullspace projection.
    For ALL base activations x and proposed updates w in Z^2, <P_perp(w; x), x> = 0,
    breaking Track S78's Forgetting/Learning = 1.00 wall on the calibration subspace. -/
theorem thm11_nullspace_projection_exact_zero_forgetting
    (x0 x1 w0 w1 : Int) :
    nullProj2X x0 x1 w0 w1 * x0 + nullProj2Y x0 x1 w0 w1 * x1 = 0 := by
  simp only [nullProj2X, nullProj2Y, Int.sub_mul, Int.add_mul]
  have t1 : x0 * x0 * w0 * x0 = w0 * x0 * x0 * x0 := by ac_rfl
  have t2 : x1 * x1 * w0 * x0 = w0 * x0 * x1 * x1 := by ac_rfl
  have t3 : x0 * x0 * w1 * x1 = w1 * x1 * x0 * x0 := by ac_rfl
  have t4 : x1 * x1 * w1 * x1 = w1 * x1 * x1 * x1 := by ac_rfl
  rw [t1, t2, t3, t4]
  omega

/-- Thm 12: Universal Pythagorean norm contraction of nullspace projection.
    ||P_perp(w; x)||^2 + ||x||^2 * <w, x>^2 = ||x||^4 * ||w||^2 for all x, w in Z^2. -/
theorem thm12_nullspace_projection_pythagorean_contraction
    (x0 x1 w0 w1 : Int) :
    nullProj2X x0 x1 w0 w1 * nullProj2X x0 x1 w0 w1 +
    nullProj2Y x0 x1 w0 w1 * nullProj2Y x0 x1 w0 w1 +
    (x0 * x0 + x1 * x1) * ((w0 * x0 + w1 * x1) * (w0 * x0 + w1 * x1)) =
    (x0 * x0 + x1 * x1) * (x0 * x0 + x1 * x1) * (w0 * w0 + w1 * w1) := by
  simp only [nullProj2X, nullProj2Y]
  have e1 : (x0 * x0 + x1 * x1) * w0 - (w0 * x0 + w1 * x1) * x0 =
            (w0 * x1 - w1 * x0) * x1 := by
    simp only [Int.add_mul, Int.sub_mul]
    have c1 : x0 * x0 * w0 = w0 * x0 * x0 := by ac_rfl
    have c2 : x1 * x1 * w0 = w0 * x1 * x1 := by ac_rfl
    have c3 : w1 * x1 * x0 = w1 * x0 * x1 := by ac_rfl
    rw [c1, c2, c3]
    omega
  have e2 : (x0 * x0 + x1 * x1) * w1 - (w0 * x0 + w1 * x1) * x1 =
            -(w0 * x1 - w1 * x0) * x0 := by
    simp only [Int.add_mul, Int.sub_mul, Int.neg_mul]
    have c1 : x1 * x1 * w1 = w1 * x1 * x1 := by ac_rfl
    have c2 : x0 * x0 * w1 = w1 * x0 * x0 := by ac_rfl
    have c3 : w0 * x0 * x1 = w0 * x1 * x0 := by ac_rfl
    rw [c1, c2, c3]
    omega
  rw [e1, e2]
  let cross := w0 * x1 - w1 * x0
  let dot := w0 * x0 + w1 * x1
  have hlag : cross * cross + dot * dot = (x0 * x0 + x1 * x1) * (w0 * w0 + w1 * w1) := by
    dsimp only [cross, dot]
    simp only [Int.sub_mul, Int.mul_sub, Int.add_mul, Int.mul_add]
    have k1 : w0 * x1 * (w0 * x1) = x1 * x1 * (w0 * w0) := by ac_rfl
    have k2 : w1 * x0 * (w1 * x0) = x0 * x0 * (w1 * w1) := by ac_rfl
    have k3 : w0 * x0 * (w0 * x0) = x0 * x0 * (w0 * w0) := by ac_rfl
    have k4 : w1 * x1 * (w1 * x1) = x1 * x1 * (w1 * w1) := by ac_rfl
    have m1 : w0 * x1 * (w1 * x0) = w0 * w1 * x0 * x1 := by ac_rfl
    have m2 : w1 * x0 * (w0 * x1) = w0 * w1 * x0 * x1 := by ac_rfl
    have m3 : w0 * x0 * (w1 * x1) = w0 * w1 * x0 * x1 := by ac_rfl
    have m4 : w1 * x1 * (w0 * x0) = w0 * w1 * x0 * x1 := by ac_rfl
    rw [k1, k2, k3, k4, m1, m2, m3, m4]
    omega
  have hfac :
      (cross * x1) * (cross * x1) + ((-cross) * x0) * ((-cross) * x0) +
      (x0 * x0 + x1 * x1) * (dot * dot) =
      (x0 * x0 + x1 * x1) * (cross * cross + dot * dot) := by
    simp only [Int.neg_mul, Int.mul_neg, Int.neg_neg]
    have q1 : cross * x1 * (cross * x1) = (x1 * x1) * (cross * cross) := by ac_rfl
    have q2 : cross * x0 * (cross * x0) = (x0 * x0) * (cross * cross) := by ac_rfl
    rw [q1, q2]
    simp only [Int.add_mul, Int.mul_add]
    omega
  change (cross * x1) * (cross * x1) + ((-cross) * x0) * ((-cross) * x0) +
         (x0 * x0 + x1 * x1) * (dot * dot) =
         (x0 * x0 + x1 * x1) * (x0 * x0 + x1 * x1) * (w0 * w0 + w1 * w1)
  rw [hfac, hlag]
  ac_rfl

/-- Thm 13: Universal Law-5 full-rank nullspace collapse over Z^2 (Cramer obstruction).
    If two base activation vectors u = (u0, u1) and v = (v0, v1) span Z^2 with nonzero
    determinant u0 * v1 - u1 * v0 != 0, then any update w = (w0, w1) orthogonal to both
    base vectors MUST vanish identically (w0 = 0 /\ w1 = 0), proving zero dark-mode capacity
    once base activations saturate the ambient dimension. -/
theorem thm13_nullspace_capacity_exhaustion_law5_obstruction
    (u0 u1 v0 v1 w0 w1 : Int)
    (hdet : u0 * v1 - u1 * v0 ≠ 0)
    (hu : w0 * u0 + w1 * u1 = 0)
    (hv : w0 * v0 + w1 * v1 = 0) :
    w0 = 0 /\ w1 = 0 := by
  have hcw0 : (u0 * v1 - u1 * v0) * w0 = 0 := by
    have e1 : (w0 * u0 + w1 * u1) * v1 = 0 := by rw [hu]; simp
    have e2 : (w0 * v0 + w1 * v1) * u1 = 0 := by rw [hv]; simp
    simp only [Int.add_mul] at e1 e2
    simp only [Int.sub_mul]
    have t1 : u0 * v1 * w0 = w0 * u0 * v1 := by ac_rfl
    have t2 : u1 * v0 * w0 = w0 * v0 * u1 := by ac_rfl
    have t3 : w1 * u1 * v1 = w1 * v1 * u1 := by ac_rfl
    rw [t1, t2]
    rw [t3] at e1
    omega
  have hcw1 : (u0 * v1 - u1 * v0) * w1 = 0 := by
    have e1 : (w0 * v0 + w1 * v1) * u0 = 0 := by rw [hv]; simp
    have e2 : (w0 * u0 + w1 * u1) * v0 = 0 := by rw [hu]; simp
    simp only [Int.add_mul] at e1 e2
    simp only [Int.sub_mul]
    have t1 : u0 * v1 * w1 = w1 * v1 * u0 := by ac_rfl
    have t2 : u1 * v0 * w1 = w1 * u1 * v0 := by ac_rfl
    have t3 : w0 * v0 * u0 = w0 * u0 * v0 := by ac_rfl
    rw [t1, t2]
    rw [t3] at e1
    omega
  have hw0 : w0 = 0 := by
    rcases Int.mul_eq_zero.mp hcw0 with hd | hz
    · exact False.elim (hdet hd)
    · exact hz
  have hw1 : w1 = 0 := by
    rcases Int.mul_eq_zero.mp hcw1 with hd | hz
    · exact False.elim (hdet hd)
    · exact hz
  exact ⟨hw0, hw1⟩

-- ============================================================================
-- Block D: Recursive Re-Linearization, Cross-Layer Coupling & Hybrid B (14-18)
-- ============================================================================

/-- Thm 14: Universal 2-layer bilinear non-additivity identity (Track S68/S70).
    (w2 + d2) * (w1 + d1) - w2 * w1 = d2 * w1 + w2 * d1 + d2 * d1. -/
theorem thm14_cross_layer_bilinear_nonadditivity_identity
    (w1 w2 d1 d2 : Int) :
    (w2 + d2) * (w1 + d1) - w2 * w1 = d2 * w1 + w2 * d1 + d2 * d1 := by
  simp only [Int.add_mul, Int.mul_add]
  omega

/-- Thm 15: Universal static 1-shot residual error vs exact recursive re-linearization.
    Given 2-layer target T = w1 * w2 + (d2 * w1 + w2 * d1), static 1-shot applying both
    (d1, d2) simultaneously leaves nonzero bilinear residual d2 * d1 when d1 != 0, d2 != 0,
    whereas recursive re-linearization solving layer 2 against live w1' = w1 + d1 achieves 0 error. -/
theorem thm15_static_oneshot_vs_recursive_relinearization
    (w1 w2 d1 d2 : Int) (hd1 : d1 ≠ 0) (hd2 : d2 ≠ 0) :
    (w2 + d2) * (w1 + d1) - (w2 * w1 + d2 * w1 + w2 * d1) = d2 * d1 /\
    d2 * d1 ≠ 0 /\
    (w2 * (w1 + d1) + d2 * w1) - (w2 * w1 + d2 * w1 + w2 * d1) = 0 := by
  have h1 : (w2 + d2) * (w1 + d1) - (w2 * w1 + d2 * w1 + w2 * d1) = d2 * d1 := by
    simp only [Int.add_mul, Int.mul_add]
    omega
  have hprod : d2 * d1 ≠ 0 := by
    intro hp
    rcases Int.mul_eq_zero.mp hp with h2 | h1z
    · exact hd2 h2
    · exact hd1 h1z
  have h3 : (w2 * (w1 + d1) + d2 * w1) - (w2 * w1 + d2 * w1 + w2 * d1) = 0 := by
    simp only [Int.mul_add]
    omega
  exact ⟨h1, ⟨hprod, h3⟩⟩

/-- Thm 16: Universal recursive re-linearization strict squared-residual contraction.
    If 0 < a < b, r0 > 0, and b * r1 <= a * r0, then b^2 * r1^2 <= a^2 * r0^2 < b^2 * r0^2. -/
theorem thm16_recursive_relinearization_monotone_contraction
    (a b r0 r1 : Nat) (ha : 0 < a) (hab : a < b) (hr0 : 0 < r0) (hstep : b * r1 <= a * r0) :
    (b * r1) * (b * r1) <= (a * r0) * (a * r0) /\
    (a * r0) * (a * r0) < (b * r0) * (b * r0) := by
  have h1 : (b * r1) * (b * r1) <= (a * r0) * (a * r0) :=
    Nat.mul_le_mul hstep hstep
  have har : a * r0 < b * r0 := Nat.mul_lt_mul_of_pos_right hab hr0
  have hpos : 0 < a * r0 := Nat.mul_pos ha hr0
  have h2 : (a * r0) * (a * r0) < (b * r0) * (b * r0) := by
    have stepA : (a * r0) * (a * r0) < (a * r0) * (b * r0) :=
      Nat.mul_lt_mul_of_pos_left har hpos
    have stepB : (a * r0) * (b * r0) <= (b * r0) * (b * r0) :=
      Nat.mul_le_mul_right (b * r0) (Nat.le_of_lt har)
    exact Nat.lt_of_lt_of_le stepA stepB
  exact ⟨h1, h2⟩

/-- Thm 17: Universal Law-5 Hybrid Mode B multiplicative Pareto dominance over both
    Pure-Backprop and Pure-ZO. If 0 < sZO < sGrad and bHyb <= eps < bBP, then
    Hybrid strictly beats Pure-Backprop on forgetting (bHyb < bBP, margin >= bBP - eps)
    AND strictly dominates on joint SNR-per-forgetting ratio: sZO * bHyb < sGrad * bBP. -/
theorem thm17_hybrid_mode_b_beats_pure_backprop_and_pure_zo
    (sZO sGrad bHyb eps bBP : Nat)
    (hspos : 0 < sZO) (hsnr : sZO < sGrad)
    (hratchet : bHyb <= eps) (hbp : eps < bBP) :
    bHyb < bBP /\ (bBP - bHyb) >= (bBP - eps) /\ sZO * bHyb < sGrad * bBP := by
  have hltb : bHyb < bBP := by omega
  have hgap : (bBP - bHyb) >= (bBP - eps) := by omega
  have hm1 : sZO * bHyb < sZO * bBP := Nat.mul_lt_mul_of_pos_left hltb hspos
  have hm2 : sZO * bBP <= sGrad * bBP := Nat.mul_le_mul_right bBP (Nat.le_of_lt hsnr)
  exact ⟨hltb, ⟨hgap, Nat.lt_of_lt_of_le hm1 hm2⟩⟩

/-- Thm 18: Universal Backprop-Free VRAM roofline savings bound and identity.
    With base weights M, autograd activations A > 0, LoRA params P, grad buffer G >= P,
    optimizer multiplier kOpt >= 2, and subspace buffer Psub <= P:
    V_pure = M + Psub < M + A + P + G + kOpt * P = V_bp, exact savings equal
    A + G + kOpt * P + (P - Psub), and savings are guaranteed >= A + 3 * P + (P - Psub). -/
theorem thm18_backprop_free_vram_savings_exact
    (M A P G kOpt Psub : Nat)
    (hA : 0 < A) (hG : P <= G) (hk : 2 <= kOpt) (hsub : Psub <= P) :
    M + Psub < M + A + P + G + kOpt * P /\
    (M + A + P + G + kOpt * P) - (M + Psub) = A + G + kOpt * P + (P - Psub) /\
    (M + A + P + G + kOpt * P) - (M + Psub) >= A + 3 * P + (P - Psub) := by
  have hkP : 2 * P <= kOpt * P := Nat.mul_le_mul_right P hk
  exact ⟨by omega, ⟨by omega, by omega⟩⟩

end TrackS97RecursiveWSEHC
