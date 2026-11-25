/-
  CEERFoundations.Module2_UniversalSchurDarkModeDrop
  Track S62c — Pure-Init Lean 4.36.0 Universal Foundations for CEER:
  1. Universal Exact Schur-Complement Variance-Reduction Theorems (1+1, 1+2, nested 2-stage,
     and 2+1 Loewner/trace drops with exact iff strict-drop conditions).
  2. Universal Stage-A Coordinate / Affine Gauge Invariance Theorem for arbitrary integer
     sensor streams (exact centered covariance shift invariance, scale homogeneity, and
     residual-variance ratio eta invariance under all positive affine gauges c*x + d).
  3. Concrete non-vacuous dark-mode unveiling and gauge-invariance witness.
  Zero Mathlib, zero sorry/admit/axiom, zero native_decide, zero external imports.
-/

namespace CEERFoundations.Module2

private theorem sq_nonneg (x : Int) : 0 ≤ x * x := by
  by_cases h : 0 ≤ x
  · exact Int.mul_nonneg h h
  · have hn : 0 ≤ -x := by omega
    have hp : 0 ≤ (-x) * (-x) := Int.mul_nonneg hn hn
    rw [Int.neg_mul_neg] at hp
    exact hp

private theorem sq_pos_iff_ne_zero (x : Int) : 0 < x * x ↔ x ≠ 0 := by
  constructor
  · intro hpos hx
    subst hx
    omega
  · intro hne
    by_cases h : 0 < x
    · exact Int.mul_pos h h
    · have hn : 0 < -x := by omega
      have hp : 0 < (-x) * (-x) := Int.mul_pos hn hn
      rw [Int.neg_mul_neg] at hp
      exact hp

private theorem int_mul_pos_iff_right (a b : Int) (ha : 0 < a) : 0 < a * b ↔ 0 < b := by
  constructor
  · intro hab
    by_cases hb : 0 < b
    · exact hb
    · have h1 : 0 ≤ a * (-b) := Int.mul_nonneg (by omega) (by omega)
      rw [Int.mul_neg] at h1
      omega
  · intro hb
    exact Int.mul_pos ha hb

private theorem int_mul_nonneg_iff_right (a b : Int) (ha : 0 < a) : 0 ≤ a * b ↔ 0 ≤ b := by
  constructor
  · intro hab
    by_cases hb : 0 ≤ b
    · exact hb
    · have h1 : 0 < a * (-b) := Int.mul_pos ha (by omega)
      rw [Int.mul_neg] at h1
      omega
  · intro hb
    exact Int.mul_nonneg (by omega) hb

/-- Theorem 2.1 (Universal): 1+1 Exact Schur-Complement Variance Reduction.
    For any target variance a, cross-coupling b, and unveiled sensor variance d > 0:
    the cleared-denominator Schur residual d * a - b^2 <= d * a ALWAYS, with
    STRICT variance drop iff cross-coupling b != 0. -/
theorem schur_1plus1_variance_drop_universal (a b d : Int) (_hd : 0 < d) :
    d * a - b * b ≤ d * a ∧ (d * a - b * b < d * a ↔ b ≠ 0) := by
  have hnn : 0 ≤ b * b := sq_nonneg b
  have hpos := sq_pos_iff_ne_zero b
  constructor
  · omega
  · constructor <;> intro h <;> omega

/-- Exact cleared-denominator Schur reduction term b^T adj(D) b for a 1+2 block Gram matrix. -/
def drop12 (b1 b2 d11 d12 d22 : Int) : Int :=
  b1 * b1 * d22 - 2 * b1 * b2 * d12 + b2 * b2 * d11

/-- Determinant of a 2x2 symmetric sensor precision/Gram block D. -/
def det2 (d11 d12 d22 : Int) : Int :=
  d11 * d22 - d12 * d12

private theorem drop12_complete_square (b1 b2 d11 d12 d22 : Int) :
    d11 * drop12 b1 b2 d11 d12 d22 =
      det2 d11 d12 d22 * (b1 * b1) + (d11 * b2 - d12 * b1) * (d11 * b2 - d12 * b1) := by
  simp only [drop12, det2]
  have hlhs :
      d11 * (b1 * b1 * d22 - 2 * b1 * b2 * d12 + b2 * b2 * d11) =
      d11 * d22 * (b1 * b1) - 2 * ((d11 * b2) * (d12 * b1)) + (d11 * b2) * (d11 * b2) := by
    rw [Int.mul_add, Int.mul_sub]
    have t1 : d11 * (b1 * b1 * d22) = d11 * d22 * (b1 * b1) := by
      calc
        d11 * (b1 * b1 * d22) = d11 * (d22 * (b1 * b1)) := by rw [Int.mul_comm (b1 * b1) d22]
        _ = d11 * d22 * (b1 * b1) := (Int.mul_assoc _ _ _).symm
    have t2 : d11 * (2 * b1 * b2 * d12) = 2 * ((d11 * b2) * (d12 * b1)) := by
      calc
        d11 * (2 * b1 * b2 * d12)
            = (d11 * (2 * b1 * b2)) * d12 := (Int.mul_assoc _ _ _).symm
        _ = ((d11 * (2 * b1)) * b2) * d12 := by rw [← Int.mul_assoc d11 (2 * b1) b2]
        _ = (((d11 * 2) * b1) * b2) * d12 := by rw [← Int.mul_assoc d11 2 b1]
        _ = (((2 * d11) * b1) * b2) * d12 := by rw [Int.mul_comm d11 2]
        _ = ((2 * (d11 * b1)) * b2) * d12 := by rw [Int.mul_assoc 2 d11 b1]
        _ = (2 * ((d11 * b1) * b2)) * d12 := by rw [Int.mul_assoc 2 (d11 * b1) b2]
        _ = 2 * ((d11 * b1 * b2) * d12) := Int.mul_assoc _ _ _
        _ = 2 * ((d11 * (b1 * b2)) * d12) := by rw [Int.mul_assoc d11 b1 b2]
        _ = 2 * ((d11 * (b2 * b1)) * d12) := by rw [Int.mul_comm b1 b2]
        _ = 2 * (((d11 * b2) * b1) * d12) := by rw [← Int.mul_assoc d11 b2 b1]
        _ = 2 * ((d11 * b2) * (b1 * d12)) := by rw [Int.mul_assoc (d11 * b2) b1 d12]
        _ = 2 * ((d11 * b2) * (d12 * b1)) := by rw [Int.mul_comm b1 d12]
    have t3 : d11 * (b2 * b2 * d11) = (d11 * b2) * (d11 * b2) := by
      calc
        d11 * (b2 * b2 * d11) = d11 * (b2 * (b2 * d11)) := by rw [Int.mul_assoc]
        _ = d11 * (b2 * (d11 * b2)) := by rw [Int.mul_comm b2 d11]
        _ = (d11 * b2) * (d11 * b2) := (Int.mul_assoc _ _ _).symm
    rw [t1, t2, t3]
  have hrhs :
      (d11 * d22 - d12 * d12) * (b1 * b1) + (d11 * b2 - d12 * b1) * (d11 * b2 - d12 * b1) =
      d11 * d22 * (b1 * b1) - 2 * ((d11 * b2) * (d12 * b1)) + (d11 * b2) * (d11 * b2) := by
    rw [Int.sub_mul, Int.sub_mul, Int.mul_sub, Int.mul_sub]
    have hc : (d12 * b1) * (d11 * b2) = (d11 * b2) * (d12 * b1) := Int.mul_comm _ _
    have hs : (d12 * b1) * (d12 * b1) = d12 * d12 * (b1 * b1) := by
      calc
        (d12 * b1) * (d12 * b1) = ((d12 * b1) * d12) * b1 := (Int.mul_assoc _ _ _).symm
        _ = (d12 * (b1 * d12)) * b1 := by rw [Int.mul_assoc d12 b1 d12]
        _ = (d12 * (d12 * b1)) * b1 := by rw [Int.mul_comm b1 d12]
        _ = ((d12 * d12) * b1) * b1 := by rw [← Int.mul_assoc d12 d12 b1]
        _ = d12 * d12 * (b1 * b1) := Int.mul_assoc _ _ _
    omega
  omega

/-- Theorem 2.2 (Universal): 1+2 Exact Schur-Complement Variance-Reduction Theorem.
    For ANY symmetric 1+2 block Gram matrix with SPD 2x2 sensor block D (d11 > 0, det2 D > 0):
    unveiling both sensors ALWAYS lowers or preserves residual variance
    (det D * a - drop12 <= det D * a), with STRICT drop iff (b1 != 0 \/ b2 != 0). -/
theorem schur_1plus2_variance_drop_universal
    (a b1 b2 d11 d12 d22 : Int)
    (hd11 : 0 < d11)
    (hdet : 0 < det2 d11 d12 d22) :
    det2 d11 d12 d22 * a - drop12 b1 b2 d11 d12 d22 ≤ det2 d11 d12 d22 * a ∧
    (det2 d11 d12 d22 * a - drop12 b1 b2 d11 d12 d22 < det2 d11 d12 d22 * a ↔
      (b1 ≠ 0 ∨ b2 ≠ 0)) := by
  have hcs := drop12_complete_square b1 b2 d11 d12 d22
  have hnn1 : 0 ≤ det2 d11 d12 d22 * (b1 * b1) := Int.mul_nonneg (by omega) (sq_nonneg b1)
  have hnn2 : 0 ≤ (d11 * b2 - d12 * b1) * (d11 * b2 - d12 * b1) := sq_nonneg _
  have hdrop_nn : 0 ≤ drop12 b1 b2 d11 d12 d22 :=
    (int_mul_nonneg_iff_right d11 _ hd11).mp (by omega)
  constructor
  · omega
  · constructor
    · intro hlt
      have hdrop_pos : 0 < drop12 b1 b2 d11 d12 d22 := by omega
      have hmul_pos : 0 < d11 * drop12 b1 b2 d11 d12 d22 := Int.mul_pos hd11 hdrop_pos
      by_cases hb1 : b1 = 0
      · subst hb1
        right
        intro hb2
        subst hb2
        simp [drop12] at hdrop_pos
      · exact Or.inl hb1
    · intro hne
      have hmul_pos : 0 < d11 * drop12 b1 b2 d11 d12 d22 := by
        rcases hne with hb1 | hb2
        · have hp1 : 0 < det2 d11 d12 d22 * (b1 * b1) :=
            Int.mul_pos hdet ((sq_pos_iff_ne_zero b1).mpr hb1)
          omega
        · by_cases hb1 : b1 = 0
          · subst hb1
            have hlin : d11 * b2 - d12 * 0 ≠ 0 := by
              rw [Int.mul_zero, Int.sub_zero]
              intro hz
              rcases Int.mul_eq_zero.mp hz with h | h <;> omega
            have hp2 : 0 < (d11 * b2 - d12 * 0) * (d11 * b2 - d12 * 0) :=
              (sq_pos_iff_ne_zero _).mpr hlin
            omega
          · have hp1 : 0 < det2 d11 d12 d22 * (b1 * b1) :=
              Int.mul_pos hdet ((sq_pos_iff_ne_zero b1).mpr hb1)
            omega
      have hdrop_pos : 0 < drop12 b1 b2 d11 d12 d22 :=
        (int_mul_pos_iff_right d11 _ hd11).mp hmul_pos
      omega

/-- Theorem 2.3 (Universal): Exact 2-Stage Nested Sensor-Unveiling Monotonicity Law.
    Stage 0 -> Stage 1 (sensor 1) -> Stage 2 (sensors 1+2) satisfies the exact polynomial identity
      d11 * (det D * a - drop12) = det D * (d11 * a - b1^2) - (d11 * b2 - d12 * b1)^2,
    hence S_2 <= S_1 ALWAYS, with STRICT second-stage drop iff partial coupling d11*b2 - d12*b1 != 0. -/
theorem schur_monotonic_nested_sensor_unveiling
    (a b1 b2 d11 d12 d22 : Int)
    (_hd11 : 0 < d11)
    (_hdet : 0 < det2 d11 d12 d22) :
    d11 * (det2 d11 d12 d22 * a - drop12 b1 b2 d11 d12 d22) =
      det2 d11 d12 d22 * (d11 * a - b1 * b1) - (d11 * b2 - d12 * b1) * (d11 * b2 - d12 * b1) ∧
    d11 * (det2 d11 d12 d22 * a - drop12 b1 b2 d11 d12 d22) ≤
      det2 d11 d12 d22 * (d11 * a - b1 * b1) ∧
    (d11 * (det2 d11 d12 d22 * a - drop12 b1 b2 d11 d12 d22) <
      det2 d11 d12 d22 * (d11 * a - b1 * b1) ↔ d11 * b2 - d12 * b1 ≠ 0) := by
  have hcs := drop12_complete_square b1 b2 d11 d12 d22
  have hid :
      d11 * (det2 d11 d12 d22 * a - drop12 b1 b2 d11 d12 d22) =
      det2 d11 d12 d22 * (d11 * a - b1 * b1) -
        (d11 * b2 - d12 * b1) * (d11 * b2 - d12 * b1) := by
    rw [Int.mul_sub, Int.mul_sub, hcs]
    have hcomm : d11 * (det2 d11 d12 d22 * a) = det2 d11 d12 d22 * (d11 * a) := by
      calc
        d11 * (det2 d11 d12 d22 * a) = (d11 * det2 d11 d12 d22) * a := (Int.mul_assoc _ _ _).symm
        _ = (det2 d11 d12 d22 * d11) * a := by rw [Int.mul_comm d11 (det2 d11 d12 d22)]
        _ = det2 d11 d12 d22 * (d11 * a) := Int.mul_assoc _ _ _
    omega
  have hnn := sq_nonneg (d11 * b2 - d12 * b1)
  have hpos := sq_pos_iff_ne_zero (d11 * b2 - d12 * b1)
  refine ⟨hid, by omega, ?_⟩
  constructor <;> intro h <;> omega

/-- Theorem 2.4 (Universal): 2+1 Multi-Output Schur Trace & Loewner Order Contraction.
    Unveiling a single coupled sensor (d > 0) lowers or preserves the residual trace
    (strictly iff b1 != 0 \/ b2 != 0) AND contracts EVERY directional quadratic form w^T S w <= w^T A w. -/
theorem schur_2plus1_trace_and_loewner_drop
    (a11 a12 a22 b1 b2 d : Int) (_hd : 0 < d) :
    d * (a11 + a22) - (b1 * b1 + b2 * b2) ≤ d * (a11 + a22) ∧
    (d * (a11 + a22) - (b1 * b1 + b2 * b2) < d * (a11 + a22) ↔ (b1 ≠ 0 ∨ b2 ≠ 0)) ∧
    (∀ w1 w2 : Int,
      let qA := a11 * w1 * w1 + 2 * a12 * w1 * w2 + a22 * w2 * w2
      d * qA - (b1 * w1 + b2 * w2) * (b1 * w1 + b2 * w2) ≤ d * qA) := by
  have hn1 := sq_nonneg b1
  have hn2 := sq_nonneg b2
  have hp1 := sq_pos_iff_ne_zero b1
  have hp2 := sq_pos_iff_ne_zero b2
  refine ⟨by omega, ?_, ?_⟩
  · constructor
    · intro hlt
      by_cases h1 : b1 = 0
      · subst h1
        right
        omega
      · exact Or.inl h1
    · intro hne
      rcases hne with h1 | h2
      · have := hp1.mpr h1
        omega
      · have := hp2.mpr h2
        omega
  · intro w1 w2
    have hnw := sq_nonneg (b1 * w1 + b2 * w2)
    omega

/-! ### Universal Stage-A Coordinate / Affine Gauge Invariance over Arbitrary Integer Streams -/

def sumList : List Int → Int
  | [] => 0
  | x :: xs => x + sumList xs

def sumProd : List Int → List Int → Int
  | [], _ => 0
  | _, [] => 0
  | x :: xs, y :: ys => x * y + sumProd xs ys

/-- Exact integer scaled centered covariance: n * sum(x_i y_i) - (sum x_i)(sum y_i). -/
def centeredCov (xs ys : List Int) : Int :=
  (xs.length : Int) * sumProd xs ys - sumList xs * sumList ys

/-- Exact integer scaled centered variance: n * sum(x_i^2) - (sum x_i)^2. -/
def centeredVar (xs : List Int) : Int :=
  centeredCov xs xs

/-- Exact numerator and denominator of the Schur residual ratio eta = 1 - r^2 = (Vx*Vy - Cxy^2) / (Vx*Vy). -/
def etaNum (xs ys : List Int) : Int :=
  centeredVar xs * centeredVar ys - centeredCov xs ys * centeredCov xs ys

def etaDen (xs ys : List Int) : Int :=
  centeredVar xs * centeredVar ys

private theorem sumList_map_add (d : Int) :
    ∀ xs : List Int, sumList (xs.map (fun x => x + d)) = sumList xs + (xs.length : Int) * d
  | [] => by simp [sumList]
  | x :: rest => by
      have ih := sumList_map_add d rest
      simp only [List.map, sumList, List.length]
      have hlen : ((rest.length + 1 : Nat) : Int) * d = (rest.length : Int) * d + d := by
        have h1 : ((rest.length + 1 : Nat) : Int) = (rest.length : Int) + 1 := by omega
        rw [h1, Int.add_mul, Int.one_mul]
      omega

private theorem sumList_map_mul (c : Int) :
    ∀ xs : List Int, sumList (xs.map (fun x => c * x)) = c * sumList xs
  | [] => by simp [sumList]
  | x :: rest => by
      have ih := sumList_map_mul c rest
      simp only [List.map, sumList]
      rw [ih, Int.mul_add]

private theorem sumProd_map_add (dx dy : Int) :
    ∀ (xs ys : List Int), xs.length = ys.length →
      sumProd (xs.map (fun x => x + dx)) (ys.map (fun y => y + dy)) =
        sumProd xs ys + dy * sumList xs + dx * sumList ys + (xs.length : Int) * (dx * dy)
  | [], [], _ => by simp [sumProd, sumList]
  | _ :: _, [], h => by simp at h
  | [], _ :: _, h => by simp at h
  | x :: xs, y :: ys, h => by
      have h' : xs.length = ys.length := by
        simp only [List.length] at h
        omega
      have ih := sumProd_map_add dx dy xs ys h'
      simp only [List.map, sumProd, sumList, List.length]
      have hterm : (x + dx) * (y + dy) = x * y + dy * x + dx * y + dx * dy := by
        rw [Int.add_mul, Int.mul_add, Int.mul_add]
        have hc : x * dy = dy * x := Int.mul_comm x dy
        omega
      have hlen : ((xs.length + 1 : Nat) : Int) * (dx * dy) =
          (xs.length : Int) * (dx * dy) + dx * dy := by
        have h1 : ((xs.length + 1 : Nat) : Int) = (xs.length : Int) + 1 := by omega
        rw [h1, Int.add_mul, Int.one_mul]
      rw [hterm, ih, hlen, Int.mul_add, Int.mul_add]
      omega

private theorem sumProd_map_mul (cx cy : Int) :
    ∀ (xs ys : List Int),
      sumProd (xs.map (fun x => cx * x)) (ys.map (fun y => cy * y)) =
        cx * cy * sumProd xs ys
  | [], _ => by simp [sumProd]
  | _ :: _, [] => by simp [sumProd]
  | x :: xs, y :: ys => by
      have ih := sumProd_map_mul cx cy xs ys
      simp only [List.map, sumProd]
      have hterm : cx * x * (cy * y) = cx * cy * (x * y) := by
        calc
          cx * x * (cy * y) = (cx * x * cy) * y := (Int.mul_assoc _ _ _).symm
          _ = (cx * (x * cy)) * y := by rw [Int.mul_assoc cx x cy]
          _ = (cx * (cy * x)) * y := by rw [Int.mul_comm x cy]
          _ = ((cx * cy) * x) * y := by rw [← Int.mul_assoc cx cy x]
          _ = cx * cy * (x * y) := Int.mul_assoc _ _ _
      rw [hterm, ih, Int.mul_add]

/-- Theorem 2.5 (Universal): Exact Integer Centered Covariance Shift Invariance.
    Adding arbitrary offsets dx, dy to arbitrary equal-length sensor streams leaves centeredCov unchanged. -/
theorem centered_cov_shift_invariant (xs ys : List Int) (dx dy : Int)
    (hlen : xs.length = ys.length) :
    centeredCov (xs.map (fun x => x + dx)) (ys.map (fun y => y + dy)) = centeredCov xs ys := by
  simp only [centeredCov, List.length_map]
  rw [sumProd_map_add dx dy xs ys hlen, sumList_map_add dx xs, sumList_map_add dy ys, ← hlen]
  let n : Int := xs.length
  let sx : Int := sumList xs
  let sy : Int := sumList ys
  have hlhs : n * (sumProd xs ys + dy * sx + dx * sy + n * (dx * dy)) =
      n * sumProd xs ys + n * (dy * sx) + n * (dx * sy) + n * (n * (dx * dy)) := by
    rw [Int.mul_add, Int.mul_add, Int.mul_add]
  have hrhs : (sx + n * dx) * (sy + n * dy) =
      sx * sy + n * (dy * sx) + n * (dx * sy) + n * (n * (dx * dy)) := by
    rw [Int.add_mul, Int.mul_add, Int.mul_add]
    have t1 : sx * (n * dy) = n * (dy * sx) := by
      calc
        sx * (n * dy) = (n * dy) * sx := Int.mul_comm _ _
        _ = n * (dy * sx) := Int.mul_assoc _ _ _
    have t2 : n * dx * sy = n * (dx * sy) := Int.mul_assoc _ _ _
    have t3 : n * dx * (n * dy) = n * (n * (dx * dy)) := by
      calc
        n * dx * (n * dy) = n * (dx * (n * dy)) := Int.mul_assoc _ _ _
        _ = n * ((dx * n) * dy) := by rw [← Int.mul_assoc dx n dy]
        _ = n * ((n * dx) * dy) := by rw [Int.mul_comm dx n]
        _ = n * (n * (dx * dy)) := by rw [Int.mul_assoc n dx dy]
    omega
  rw [hlhs, hrhs]
  change (xs.length : Int) * sumProd xs ys + (xs.length : Int) * (dy * sumList xs) +
      (xs.length : Int) * (dx * sumList ys) + (xs.length : Int) * ((xs.length : Int) * (dx * dy)) -
      (sumList xs * sumList ys + (xs.length : Int) * (dy * sumList xs) +
      (xs.length : Int) * (dx * sumList ys) + (xs.length : Int) * ((xs.length : Int) * (dx * dy))) =
      (xs.length : Int) * sumProd xs ys - sumList xs * sumList ys
  omega

/-- Theorem 2.6 (Universal): Exact Integer Centered Covariance Scale Homogeneity. -/
theorem centered_cov_scale_homogeneous (xs ys : List Int) (cx cy : Int) :
    centeredCov (xs.map (fun x => cx * x)) (ys.map (fun y => cy * y)) =
      cx * cy * centeredCov xs ys := by
  simp only [centeredCov, List.length_map]
  rw [sumProd_map_mul cx cy xs ys, sumList_map_mul cx xs, sumList_map_mul cy ys]
  rw [Int.mul_sub]
  have t1 : (xs.length : Int) * (cx * cy * sumProd xs ys) =
      cx * cy * ((xs.length : Int) * sumProd xs ys) := by
    calc
      (xs.length : Int) * (cx * cy * sumProd xs ys)
          = ((xs.length : Int) * (cx * cy)) * sumProd xs ys := (Int.mul_assoc _ _ _).symm
      _ = ((cx * cy) * (xs.length : Int)) * sumProd xs ys := by rw [Int.mul_comm (xs.length : Int) (cx * cy)]
      _ = cx * cy * ((xs.length : Int) * sumProd xs ys) := Int.mul_assoc _ _ _
  have t2 : cx * sumList xs * (cy * sumList ys) = cx * cy * (sumList xs * sumList ys) := by
    calc
      cx * sumList xs * (cy * sumList ys)
          = (cx * sumList xs * cy) * sumList ys := (Int.mul_assoc _ _ _).symm
      _ = (cx * (sumList xs * cy)) * sumList ys := by rw [Int.mul_assoc cx (sumList xs) cy]
      _ = (cx * (cy * sumList xs)) * sumList ys := by rw [Int.mul_comm (sumList xs) cy]
      _ = ((cx * cy) * sumList xs) * sumList ys := by rw [← Int.mul_assoc cx cy (sumList xs)]
      _ = cx * cy * (sumList xs * sumList ys) := Int.mul_assoc _ _ _
  rw [t1, t2]

private theorem centered_cov_affine (xs ys : List Int) (cx dx cy dy : Int)
    (hlen : xs.length = ys.length) :
    centeredCov (xs.map (fun x => cx * x + dx)) (ys.map (fun y => cy * y + dy)) =
      cx * cy * centeredCov xs ys := by
  have hx : xs.map (fun x => cx * x + dx) = (xs.map (fun x => cx * x)).map (fun z => z + dx) := by
    rw [List.map_map]
    rfl
  have hy : ys.map (fun y => cy * y + dy) = (ys.map (fun y => cy * y)).map (fun z => z + dy) := by
    rw [List.map_map]
    rfl
  rw [hx, hy]
  have hlen' : (xs.map (fun x => cx * x)).length = (ys.map (fun y => cy * y)).length := by
    simp [hlen]
  rw [centered_cov_shift_invariant _ _ dx dy hlen', centered_cov_scale_homogeneous]

/-- Theorem 2.7 (Universal): Stage-A Coordinate / Affine Gauge Invariance of Schur Ratio eta.
    For EVERY equal-length integer dataset (xs, ys) and EVERY positive affine rescaling
    x |-> cx*x + dx, y |-> cy*y + dy (cx > 0, cy > 0), the exact rational Schur residual ratio
    eta = etaNum / etaDen is IDENTICALLY INVARIANT (cross-multiplied exact equality + preserved positivity). -/
theorem stageA_affine_gauge_invariance_eta
    (xs ys : List Int) (cx dx cy dy : Int)
    (hlen : xs.length = ys.length)
    (hcx : 0 < cx) (hcy : 0 < cy) :
    let xs' := xs.map (fun x => cx * x + dx)
    let ys' := ys.map (fun y => cy * y + dy)
    let k : Int := (cx * cx) * (cy * cy)
    0 < k ∧
    etaNum xs' ys' = k * etaNum xs ys ∧
    etaDen xs' ys' = k * etaDen xs ys ∧
    etaNum xs' ys' * etaDen xs ys = etaNum xs ys * etaDen xs' ys' := by
  intro xs' ys' k
  have hk : 0 < k := Int.mul_pos (Int.mul_pos hcx hcx) (Int.mul_pos hcy hcy)
  have hvx : centeredVar xs' = (cx * cx) * centeredVar xs := by
    exact centered_cov_affine xs xs cx dx cx dx rfl
  have hvy : centeredVar ys' = (cy * cy) * centeredVar ys := by
    exact centered_cov_affine ys ys cy dy cy dy rfl
  have hcxy : centeredCov xs' ys' = (cx * cy) * centeredCov xs ys := by
    exact centered_cov_affine xs ys cx dx cy dy hlen
  have hden : etaDen xs' ys' = k * etaDen xs ys := by
    simp only [etaDen, hvx, hvy, k]
    calc
      cx * cx * centeredVar xs * (cy * cy * centeredVar ys)
          = (cx * cx * centeredVar xs * (cy * cy)) * centeredVar ys := (Int.mul_assoc _ _ _).symm
      _ = (cx * cx * (centeredVar xs * (cy * cy))) * centeredVar ys := by
            rw [Int.mul_assoc (cx * cx) (centeredVar xs) (cy * cy)]
      _ = (cx * cx * ((cy * cy) * centeredVar xs)) * centeredVar ys := by
            rw [Int.mul_comm (centeredVar xs) (cy * cy)]
      _ = ((cx * cx * (cy * cy)) * centeredVar xs) * centeredVar ys := by
            rw [← Int.mul_assoc (cx * cx) (cy * cy) (centeredVar xs)]
      _ = cx * cx * (cy * cy) * (centeredVar xs * centeredVar ys) := Int.mul_assoc _ _ _
  have hsq : centeredCov xs' ys' * centeredCov xs' ys' =
      k * (centeredCov xs ys * centeredCov xs ys) := by
    rw [hcxy]
    have hcc : (cx * cy) * (cx * cy) = k := by
      simp only [k]
      calc
        cx * cy * (cx * cy) = (cx * cy * cx) * cy := (Int.mul_assoc _ _ _).symm
        _ = (cx * (cy * cx)) * cy := by rw [Int.mul_assoc cx cy cx]
        _ = (cx * (cx * cy)) * cy := by rw [Int.mul_comm cy cx]
        _ = ((cx * cx) * cy) * cy := by rw [← Int.mul_assoc cx cx cy]
        _ = (cx * cx) * (cy * cy) := Int.mul_assoc _ _ _
    calc
      cx * cy * centeredCov xs ys * (cx * cy * centeredCov xs ys)
          = (cx * cy * centeredCov xs ys * (cx * cy)) * centeredCov xs ys := (Int.mul_assoc _ _ _).symm
      _ = (cx * cy * (centeredCov xs ys * (cx * cy))) * centeredCov xs ys := by
            rw [Int.mul_assoc (cx * cy) (centeredCov xs ys) (cx * cy)]
      _ = (cx * cy * ((cx * cy) * centeredCov xs ys)) * centeredCov xs ys := by
            rw [Int.mul_comm (centeredCov xs ys) (cx * cy)]
      _ = ((cx * cy * (cx * cy)) * centeredCov xs ys) * centeredCov xs ys := by
            rw [← Int.mul_assoc (cx * cy) (cx * cy) (centeredCov xs ys)]
      _ = k * (centeredCov xs ys * centeredCov xs ys) := by rw [hcc, Int.mul_assoc]
  have hnum : etaNum xs' ys' = k * etaNum xs ys := by
    simp only [etaNum]
    have hdv : centeredVar xs' * centeredVar ys' = k * (centeredVar xs * centeredVar ys) := hden
    rw [hdv, hsq, ← Int.mul_sub]
  refine ⟨hk, hnum, hden, ?_⟩
  rw [hnum, hden]
  calc
    k * etaNum xs ys * etaDen xs ys
        = (etaNum xs ys * k) * etaDen xs ys := by rw [Int.mul_comm k (etaNum xs ys)]
    _ = etaNum xs ys * (k * etaDen xs ys) := Int.mul_assoc _ _ _

/-- Concrete 1+2 dark-mode unveiling & Stage-A affine gauge invariance witnesses. -/
def sampleX : List Int := [10, 20, 35, 50, 65]
def sampleY : List Int := [42, 55, 68, 84, 96]

/-- Theorem 2.8 (Concrete): Non-vacuous 2-stage Schur drop (S0 = 100 > S1 = 64 > S2 = 60,
    i.e., eta: 100% -> 64% -> 60%) and exact affine gauge invariance under (x |-> 7x - 13, y |-> 5y + 29). -/
theorem ceer_s53_dark_mode_drop_witness :
    let a : Int := 100
    let b1 : Int := 12
    let b2 : Int := 10
    let d11 : Int := 4
    let d12 : Int := 2
    let d22 : Int := 5
    let xs' := sampleX.map (fun x => 7 * x - 13)
    let ys' := sampleY.map (fun y => 5 * y + 29)
    0 < d11 ∧
    0 < det2 d11 d12 d22 ∧
    det2 d11 d12 d22 * a - drop12 b1 b2 d11 d12 d22 = 960 ∧
    d11 * (det2 d11 d12 d22 * a - drop12 b1 b2 d11 d12 d22) <
      det2 d11 d12 d22 * (d11 * a - b1 * b1) ∧
    det2 d11 d12 d22 * (d11 * a - b1 * b1) < det2 d11 d12 d22 * (d11 * a) ∧
    0 < etaDen sampleX sampleY ∧
    etaNum xs' ys' * etaDen sampleX sampleY = etaNum sampleX sampleY * etaDen xs' ys' := by
  decide

end CEERFoundations.Module2

#print axioms CEERFoundations.Module2.schur_1plus1_variance_drop_universal
#print axioms CEERFoundations.Module2.schur_1plus2_variance_drop_universal
#print axioms CEERFoundations.Module2.schur_monotonic_nested_sensor_unveiling
#print axioms CEERFoundations.Module2.schur_2plus1_trace_and_loewner_drop
#print axioms CEERFoundations.Module2.centered_cov_shift_invariant
#print axioms CEERFoundations.Module2.centered_cov_scale_homogeneous
#print axioms CEERFoundations.Module2.stageA_affine_gauge_invariance_eta
#print axioms CEERFoundations.Module2.ceer_s53_dark_mode_drop_witness
