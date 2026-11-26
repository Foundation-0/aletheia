/-
  CEERFoundations.Module3_UniversalLaplacianThermalCoupling
  Track S62c — Pure-Init Lean 4.36.0 Universal Foundations for CEER:
  1. Universal Discrete 1D 8-Core Die-Chain Graph-Laplacian (g*L + h*I) Steady-State Theorems:
     - Exact Energy Conservation (h * sum T_i = q)
     - Universal Strict Temperature Monotonicity (T_0 > T_1 > ... > T_7 > 0) for ALL g, h, q > 0
     - Universal Strict Flux Decay / Convexity (T_0 - T_1 > T_1 - T_2 > ... > T_6 - T_7 > 0)
     - Universal Non-Vacuous Constructive Green's Function Existence for ALL g, h > 0
     - Universal Anisotropic Heat-Pipe Falsification Corollary (T_j >= T_i for i < j refutes ALL g,h,q > 0)
  2. Exact Concrete g=2, h=1 Benchmark & Anisotropic Counterexample Witness.
  Zero Mathlib, zero sorry/admit/axiom, zero native_decide, zero external imports.
-/

namespace CEERFoundations.Module3

/-- Steady-state discrete heat balance (g * L_path8 + h * I_8) T = q * e_0 on the 8-core die chain. -/
def IsDie8SteadyState (g h q : Int) (T : Fin 8 → Int) : Prop :=
  (g + h) * T 0 - g * T 1 = q ∧
  (2 * g + h) * T 1 - g * T 0 - g * T 2 = 0 ∧
  (2 * g + h) * T 2 - g * T 1 - g * T 3 = 0 ∧
  (2 * g + h) * T 3 - g * T 2 - g * T 4 = 0 ∧
  (2 * g + h) * T 4 - g * T 3 - g * T 5 = 0 ∧
  (2 * g + h) * T 5 - g * T 4 - g * T 6 = 0 ∧
  (2 * g + h) * T 6 - g * T 5 - g * T 7 = 0 ∧
  (g + h) * T 7 - g * T 6 = 0

def sum8 (T : Fin 8 → Int) : Int :=
  T 0 + T 1 + T 2 + T 3 + T 4 + T 5 + T 6 + T 7

private theorem int_pos_of_mul_pos_right (a b : Int) (ha : 0 < a) (hab : 0 < a * b) : 0 < b := by
  by_cases hb : 0 < b
  · exact hb
  · have h1 : 0 ≤ a * (-b) := Int.mul_nonneg (by omega) (by omega)
    rw [Int.mul_neg] at h1
    omega

private theorem int_le_zero_of_mul_le_zero_right (a b : Int) (ha : 0 < a) (hab : a * b ≤ 0) : b ≤ 0 := by
  by_cases hb : b ≤ 0
  · exact hb
  · have h1 : 0 < a * b := Int.mul_pos ha (by omega)
    omega

private theorem balance_interior_flux (g h a b c : Int)
    (heq : (2 * g + h) * b - g * a - g * c = 0) :
    g * (a - b) = g * (b - c) + h * b := by
  rw [Int.add_mul] at heq
  rw [Int.mul_sub, Int.mul_sub]
  have h2 : 2 * g * b = g * b + g * b := by
    have h2g : 2 * g = g + g := by omega
    rw [h2g, Int.add_mul]
  omega

private theorem balance_end_flux (g h a b : Int)
    (heq : (g + h) * b - g * a = 0) :
    g * (a - b) = h * b := by
  rw [Int.add_mul] at heq
  rw [Int.mul_sub]
  omega

private theorem balance_src_flux (g h q a b : Int)
    (heq : (g + h) * a - g * b = q) :
    g * (a - b) + h * a = q := by
  rw [Int.add_mul] at heq
  rw [Int.mul_sub]
  omega

/-- Theorem 3.1 (Universal): Exact Discrete Thermal Energy Conservation on the 8-Core Die Chain.
    For EVERY conductance g, sink h, injected power q, and steady state T: h * sum(T_i) = q. -/
theorem die8_laplacian_energy_conservation (g h q : Int) (T : Fin 8 → Int)
    (hss : IsDie8SteadyState g h q T) :
    h * sum8 T = q := by
  rcases hss with ⟨e0, e1, e2, e3, e4, e5, e6, e7⟩
  have f0 := balance_src_flux g h q (T 0) (T 1) e0
  have f1 := balance_interior_flux g h (T 0) (T 1) (T 2) e1
  have f2 := balance_interior_flux g h (T 1) (T 2) (T 3) e2
  have f3 := balance_interior_flux g h (T 2) (T 3) (T 4) e3
  have f4 := balance_interior_flux g h (T 3) (T 4) (T 5) e4
  have f5 := balance_interior_flux g h (T 4) (T 5) (T 6) e5
  have f6 := balance_interior_flux g h (T 5) (T 6) (T 7) e6
  have f7 := balance_end_flux g h (T 6) (T 7) e7
  simp only [sum8, Int.mul_add]
  omega

/-- Theorem 3.2 (Universal): Far-End Positivity T_7 > 0 for ALL g > 0, h > 0, q > 0. -/
theorem die8_far_end_strictly_positive (g h q : Int) (T : Fin 8 → Int)
    (hg : 0 < g) (hh : 0 < h) (hq : 0 < q)
    (hss : IsDie8SteadyState g h q T) :
    0 < T 7 := by
  rcases hss with ⟨e0, e1, e2, e3, e4, e5, e6, e7⟩
  have f0 := balance_src_flux g h q (T 0) (T 1) e0
  have f1 := balance_interior_flux g h (T 0) (T 1) (T 2) e1
  have f2 := balance_interior_flux g h (T 1) (T 2) (T 3) e2
  have f3 := balance_interior_flux g h (T 2) (T 3) (T 4) e3
  have f4 := balance_interior_flux g h (T 3) (T 4) (T 5) e4
  have f5 := balance_interior_flux g h (T 4) (T 5) (T 6) e5
  have f6 := balance_interior_flux g h (T 5) (T 6) (T 7) e6
  have f7 := balance_end_flux g h (T 6) (T 7) e7
  by_cases h7 : 0 < T 7
  · exact h7
  · have le7 : T 7 ≤ 0 := by omega
    have h_ht7 : h * T 7 ≤ 0 := by
      have := Int.mul_nonneg (a := h) (b := -T 7) (by omega) (by omega)
      rw [Int.mul_neg] at this; omega
    have d67 : T 6 - T 7 ≤ 0 := int_le_zero_of_mul_le_zero_right g _ hg (by omega)
    have le6 : T 6 ≤ 0 := by omega
    have h_ht6 : h * T 6 ≤ 0 := by
      have := Int.mul_nonneg (a := h) (b := -T 6) (by omega) (by omega)
      rw [Int.mul_neg] at this; omega
    have d56 : T 5 - T 6 ≤ 0 := int_le_zero_of_mul_le_zero_right g _ hg (by omega)
    have le5 : T 5 ≤ 0 := by omega
    have h_ht5 : h * T 5 ≤ 0 := by
      have := Int.mul_nonneg (a := h) (b := -T 5) (by omega) (by omega)
      rw [Int.mul_neg] at this; omega
    have d45 : T 4 - T 5 ≤ 0 := int_le_zero_of_mul_le_zero_right g _ hg (by omega)
    have le4 : T 4 ≤ 0 := by omega
    have h_ht4 : h * T 4 ≤ 0 := by
      have := Int.mul_nonneg (a := h) (b := -T 4) (by omega) (by omega)
      rw [Int.mul_neg] at this; omega
    have d34 : T 3 - T 4 ≤ 0 := int_le_zero_of_mul_le_zero_right g _ hg (by omega)
    have le3 : T 3 ≤ 0 := by omega
    have h_ht3 : h * T 3 ≤ 0 := by
      have := Int.mul_nonneg (a := h) (b := -T 3) (by omega) (by omega)
      rw [Int.mul_neg] at this; omega
    have d23 : T 2 - T 3 ≤ 0 := int_le_zero_of_mul_le_zero_right g _ hg (by omega)
    have le2 : T 2 ≤ 0 := by omega
    have h_ht2 : h * T 2 ≤ 0 := by
      have := Int.mul_nonneg (a := h) (b := -T 2) (by omega) (by omega)
      rw [Int.mul_neg] at this; omega
    have d12 : T 1 - T 2 ≤ 0 := int_le_zero_of_mul_le_zero_right g _ hg (by omega)
    have le1 : T 1 ≤ 0 := by omega
    have h_ht1 : h * T 1 ≤ 0 := by
      have := Int.mul_nonneg (a := h) (b := -T 1) (by omega) (by omega)
      rw [Int.mul_neg] at this; omega
    have d01 : T 0 - T 1 ≤ 0 := int_le_zero_of_mul_le_zero_right g _ hg (by omega)
    have le0 : T 0 ≤ 0 := by omega
    have h_ht0 : h * T 0 ≤ 0 := by
      have := Int.mul_nonneg (a := h) (b := -T 0) (by omega) (by omega)
      rw [Int.mul_neg] at this; omega
    omega

/-- Theorem 3.3 (Universal): Strict Temperature Monotonicity T_0 > T_1 > ... > T_7 > 0
    for EVERY g > 0, h > 0, q > 0 and EVERY steady state of the 8-core isotropic die chain. -/
theorem die8_laplacian_strict_monotonicity (g h q : Int) (T : Fin 8 → Int)
    (hg : 0 < g) (hh : 0 < h) (hq : 0 < q)
    (hss : IsDie8SteadyState g h q T) :
    T 0 > T 1 ∧ T 1 > T 2 ∧ T 2 > T 3 ∧ T 3 > T 4 ∧
    T 4 > T 5 ∧ T 5 > T 6 ∧ T 6 > T 7 ∧ T 7 > 0 := by
  have p7 : 0 < T 7 := die8_far_end_strictly_positive g h q T hg hh hq hss
  rcases hss with ⟨_, e1, e2, e3, e4, e5, e6, e7⟩
  have f1 := balance_interior_flux g h (T 0) (T 1) (T 2) e1
  have f2 := balance_interior_flux g h (T 1) (T 2) (T 3) e2
  have f3 := balance_interior_flux g h (T 2) (T 3) (T 4) e3
  have f4 := balance_interior_flux g h (T 3) (T 4) (T 5) e4
  have f5 := balance_interior_flux g h (T 4) (T 5) (T 6) e5
  have f6 := balance_interior_flux g h (T 5) (T 6) (T 7) e6
  have f7 := balance_end_flux g h (T 6) (T 7) e7
  have h7 : 0 < h * T 7 := Int.mul_pos hh p7
  have d67 : 0 < T 6 - T 7 := int_pos_of_mul_pos_right g _ hg (by omega)
  have h6 : 0 < h * T 6 := Int.mul_pos hh (by omega)
  have d56 : 0 < T 5 - T 6 := int_pos_of_mul_pos_right g _ hg (by omega)
  have h5 : 0 < h * T 5 := Int.mul_pos hh (by omega)
  have d45 : 0 < T 4 - T 5 := int_pos_of_mul_pos_right g _ hg (by omega)
  have h4 : 0 < h * T 4 := Int.mul_pos hh (by omega)
  have d34 : 0 < T 3 - T 4 := int_pos_of_mul_pos_right g _ hg (by omega)
  have h3 : 0 < h * T 3 := Int.mul_pos hh (by omega)
  have d23 : 0 < T 2 - T 3 := int_pos_of_mul_pos_right g _ hg (by omega)
  have h2 : 0 < h * T 2 := Int.mul_pos hh (by omega)
  have d12 : 0 < T 1 - T 2 := int_pos_of_mul_pos_right g _ hg (by omega)
  have h1 : 0 < h * T 1 := Int.mul_pos hh (by omega)
  have d01 : 0 < T 0 - T 1 := int_pos_of_mul_pos_right g _ hg (by omega)
  omega

/-- Theorem 3.4 (Universal): Strict Discrete Flux Decay / Convexity along the 8-Core Die Chain.
    Temperature drops strictly decrease with distance from the heated core 0. -/
theorem die8_laplacian_strict_flux_decay (g h q : Int) (T : Fin 8 → Int)
    (hg : 0 < g) (hh : 0 < h) (hq : 0 < q)
    (hss : IsDie8SteadyState g h q T) :
    T 0 - T 1 > T 1 - T 2 ∧
    T 1 - T 2 > T 2 - T 3 ∧
    T 2 - T 3 > T 3 - T 4 ∧
    T 3 - T 4 > T 4 - T 5 ∧
    T 4 - T 5 > T 5 - T 6 ∧
    T 5 - T 6 > T 6 - T 7 ∧
    T 6 - T 7 > 0 := by
  have hm := die8_laplacian_strict_monotonicity g h q T hg hh hq hss
  rcases hm with ⟨_, _, _, _, _, _, _, p7⟩
  rcases hss with ⟨_, e1, e2, e3, e4, e5, e6, e7⟩
  have f1 := balance_interior_flux g h (T 0) (T 1) (T 2) e1
  have f2 := balance_interior_flux g h (T 1) (T 2) (T 3) e2
  have f3 := balance_interior_flux g h (T 2) (T 3) (T 4) e3
  have f4 := balance_interior_flux g h (T 3) (T 4) (T 5) e4
  have f5 := balance_interior_flux g h (T 4) (T 5) (T 6) e5
  have f6 := balance_interior_flux g h (T 5) (T 6) (T 7) e6
  have f7 := balance_end_flux g h (T 6) (T 7) e7
  have c67 : 0 < T 6 - T 7 := int_pos_of_mul_pos_right g _ hg (by rw [f7]; exact Int.mul_pos hh p7)
  have c56 : 0 < (T 5 - T 6) - (T 6 - T 7) := by
    have hsub : g * ((T 5 - T 6) - (T 6 - T 7)) = h * T 6 := by rw [Int.mul_sub]; omega
    exact int_pos_of_mul_pos_right g _ hg (by rw [hsub]; exact Int.mul_pos hh (by omega))
  have c45 : 0 < (T 4 - T 5) - (T 5 - T 6) := by
    have hsub : g * ((T 4 - T 5) - (T 5 - T 6)) = h * T 5 := by rw [Int.mul_sub]; omega
    exact int_pos_of_mul_pos_right g _ hg (by rw [hsub]; exact Int.mul_pos hh (by omega))
  have c34 : 0 < (T 3 - T 4) - (T 4 - T 5) := by
    have hsub : g * ((T 3 - T 4) - (T 4 - T 5)) = h * T 4 := by rw [Int.mul_sub]; omega
    exact int_pos_of_mul_pos_right g _ hg (by rw [hsub]; exact Int.mul_pos hh (by omega))
  have c23 : 0 < (T 2 - T 3) - (T 3 - T 4) := by
    have hsub : g * ((T 2 - T 3) - (T 3 - T 4)) = h * T 3 := by rw [Int.mul_sub]; omega
    exact int_pos_of_mul_pos_right g _ hg (by rw [hsub]; exact Int.mul_pos hh (by omega))
  have c12 : 0 < (T 1 - T 2) - (T 2 - T 3) := by
    have hsub : g * ((T 1 - T 2) - (T 2 - T 3)) = h * T 2 := by rw [Int.mul_sub]; omega
    exact int_pos_of_mul_pos_right g _ hg (by rw [hsub]; exact Int.mul_pos hh (by omega))
  have c01 : 0 < (T 0 - T 1) - (T 1 - T 2) := by
    have hsub : g * ((T 0 - T 1) - (T 1 - T 2)) = h * T 1 := by rw [Int.mul_sub]; omega
    exact int_pos_of_mul_pos_right g _ hg (by rw [hsub]; exact Int.mul_pos hh (by omega))
  omega

private theorem chain_mono_step (T : Fin 8 → Int)
    (hstep : ∀ (k : Nat) (hk : k + 1 < 8), T ⟨k, by omega⟩ > T ⟨k + 1, hk⟩) :
    ∀ (d iv : Nat) (hj : iv + d + 1 < 8),
      T ⟨iv, by omega⟩ > T ⟨iv + d + 1, hj⟩
  | 0, iv, hj => hstep iv hj
  | d + 1, iv, hj =>
      have h1 : T ⟨iv, by omega⟩ > T ⟨iv + d + 1, by omega⟩ :=
        chain_mono_step T hstep d iv (by omega)
      have h2 : T ⟨iv + d + 1, by omega⟩ > T ⟨iv + d + 2, hj⟩ :=
        hstep (iv + d + 1) hj
      Int.lt_trans h2 h1

/-- Theorem 3.5 (Universal): Strict Distance-Ordered Pairwise Inequality T i > T j for ALL 0 <= i < j < 8. -/
theorem die8_pairwise_distance_monotonicity (g h q : Int) (T : Fin 8 → Int)
    (hg : 0 < g) (hh : 0 < h) (hq : 0 < q)
    (hss : IsDie8SteadyState g h q T)
    (i j : Fin 8) (hij : i.val < j.val) :
    T i > T j := by
  have hm := die8_laplacian_strict_monotonicity g h q T hg hh hq hss
  rcases hm with ⟨h01, h12, h23, h34, h45, h56, h67, _⟩
  have hstep : ∀ (k : Nat) (hk : k + 1 < 8), T ⟨k, by omega⟩ > T ⟨k + 1, hk⟩ := by
    intro k hk
    match k with
    | 0 => exact h01
    | 1 => exact h12
    | 2 => exact h23
    | 3 => exact h34
    | 4 => exact h45
    | 5 => exact h56
    | 6 => exact h67
    | n + 7 => omega
  rcases i with ⟨iv, hi⟩
  rcases j with ⟨jv, hj⟩
  change iv < jv at hij
  have heq : iv + (jv - iv - 1) + 1 = jv := by omega
  have hres := chain_mono_step T hstep (jv - iv - 1) iv (by omega)
  have hfin : (⟨iv + (jv - iv - 1) + 1, by omega⟩ : Fin 8) = ⟨jv, hj⟩ := Fin.ext heq
  rw [hfin] at hres
  exact hres

/-- Theorem 3.6 (Universal): Anisotropic Heat-Pipe Falsification Corollary.
    ANY observed temperature inversion T j >= T i with i < j unconditionally disproves
    ALL isotropic 1D die-chain diffusion models (g > 0, h > 0, q > 0). -/
theorem anisotropic_coupling_refutes_isotropic_chain (T : Fin 8 → Int)
    (i j : Fin 8) (hij : i.val < j.val) (hinv : T j ≥ T i) :
    ¬ (∃ g h q : Int, 0 < g ∧ 0 < h ∧ 0 < q ∧ IsDie8SteadyState g h q T) := by
  intro hex
  rcases hex with ⟨g, h, q, hg, hh, hq, hss⟩
  have hgt := die8_pairwise_distance_monotonicity g h q T hg hh hq hss i j hij
  omega

/-- Constructive exact integer Green's-function polynomial sequence for arbitrary (g, h):
    u_7 = 1, u_6 = g + h, u_k = (2*g + h) * u_{k+1} - g^2 * u_{k+2}, T_k = g^k * u_k. -/
def greensU (g h : Int) : Nat → Int
  | 0 => 1
  | 1 => g + h
  | k + 2 => (2 * g + h) * greensU g h (k + 1) - g * g * greensU g h k

def powInt (g : Int) : Nat → Int
  | 0 => 1
  | k + 1 => g * powInt g k

def greensCol8 (g h : Int) (i : Fin 8) : Int :=
  powInt g i.val * greensU g h (7 - i.val)

def greensQ8 (g h : Int) : Int :=
  (g + h) * greensCol8 g h 0 - g * greensCol8 g h 1

private theorem powInt_pos (g : Int) (hg : 0 < g) : ∀ k : Nat, 0 < powInt g k
  | 0 => by simp [powInt]
  | k + 1 => Int.mul_pos hg (powInt_pos g hg k)

private theorem greens_step_eq (g h : Int) (k m : Nat) :
    (2 * g + h) * (powInt g (k + 1) * greensU g h (m + 1)) -
      g * (powInt g k * greensU g h (m + 2)) -
      g * (powInt g (k + 2) * greensU g h m) = 0 := by
  let p : Int := g * powInt g k
  have hp1 : powInt g (k + 1) = p := rfl
  have hp2 : powInt g (k + 2) = g * p := rfl
  have h1 : (2 * g + h) * (p * greensU g h (m + 1)) =
      p * ((2 * g + h) * greensU g h (m + 1)) := by
    calc
      (2 * g + h) * (p * greensU g h (m + 1))
          = ((2 * g + h) * p) * greensU g h (m + 1) := (Int.mul_assoc _ _ _).symm
      _ = (p * (2 * g + h)) * greensU g h (m + 1) := by rw [Int.mul_comm (2 * g + h) p]
      _ = p * ((2 * g + h) * greensU g h (m + 1)) := Int.mul_assoc _ _ _
  have h2 : g * (powInt g k * greensU g h (m + 2)) =
      p * ((2 * g + h) * greensU g h (m + 1)) - p * (g * g * greensU g h m) := by
    rw [← Int.mul_assoc g (powInt g k) (greensU g h (m + 2))]
    change p * greensU g h (m + 2) = _
    simp only [greensU]
    rw [Int.mul_sub]
  have h3 : g * (g * p * greensU g h m) = p * (g * g * greensU g h m) := by
    calc
      g * (g * p * greensU g h m)
          = (g * (g * p)) * greensU g h m := (Int.mul_assoc _ _ _).symm
      _ = ((g * g) * p) * greensU g h m := by rw [← Int.mul_assoc g g p]
      _ = (p * (g * g)) * greensU g h m := by rw [Int.mul_comm (g * g) p]
      _ = p * (g * g * greensU g h m) := Int.mul_assoc _ _ _
  rw [hp1, hp2, h1, h2, h3]
  omega

private theorem greens_end_eq (g h : Int) :
    (g + h) * greensCol8 g h 7 - g * greensCol8 g h 6 = 0 := by
  change (g + h) * (g * powInt g 6 * 1) - g * (powInt g 6 * (g + h)) = 0
  have h1 : (g + h) * (g * powInt g 6 * 1) = g * powInt g 6 * (g + h) := by
    rw [Int.mul_one, Int.mul_comm (g + h) (g * powInt g 6)]
  have h2 : g * (powInt g 6 * (g + h)) = g * powInt g 6 * (g + h) :=
    (Int.mul_assoc g (powInt g 6) (g + h)).symm
  rw [h1, h2]
  omega

/-- Theorem 3.7 (Universal): Non-Vacuous Constructive Green's Function Existence for ALL g, h > 0.
    Constructs an exact integer steady state greensCol8 g h with strictly positive heat input
    greensQ8 g h > 0, satisfying IsDie8SteadyState and strict monotonicity T_0 > ... > T_7 > 0. -/
theorem die8_greens_exact_solution_exists (g h : Int) (hg : 0 < g) (hh : 0 < h) :
    0 < greensQ8 g h ∧
    IsDie8SteadyState g h (greensQ8 g h) (greensCol8 g h) ∧
    greensCol8 g h 0 > greensCol8 g h 7 ∧
    greensCol8 g h 7 > 0 := by
  have e0 : (g + h) * greensCol8 g h 0 - g * greensCol8 g h 1 = greensQ8 g h := rfl
  have e1 : (2 * g + h) * greensCol8 g h 1 - g * greensCol8 g h 0 - g * greensCol8 g h 2 = 0 :=
    greens_step_eq g h 0 5
  have e2 : (2 * g + h) * greensCol8 g h 2 - g * greensCol8 g h 1 - g * greensCol8 g h 3 = 0 :=
    greens_step_eq g h 1 4
  have e3 : (2 * g + h) * greensCol8 g h 3 - g * greensCol8 g h 2 - g * greensCol8 g h 4 = 0 :=
    greens_step_eq g h 2 3
  have e4 : (2 * g + h) * greensCol8 g h 4 - g * greensCol8 g h 3 - g * greensCol8 g h 5 = 0 :=
    greens_step_eq g h 3 2
  have e5 : (2 * g + h) * greensCol8 g h 5 - g * greensCol8 g h 4 - g * greensCol8 g h 6 = 0 :=
    greens_step_eq g h 4 1
  have e6 : (2 * g + h) * greensCol8 g h 6 - g * greensCol8 g h 5 - g * greensCol8 g h 7 = 0 :=
    greens_step_eq g h 5 0
  have e7 : (g + h) * greensCol8 g h 7 - g * greensCol8 g h 6 = 0 :=
    greens_end_eq g h
  have hss : IsDie8SteadyState g h (greensQ8 g h) (greensCol8 g h) :=
    ⟨e0, e1, e2, e3, e4, e5, e6, e7⟩
  -- Prove T_7 = g^7 > 0 directly, then propagate strictly upward to deduce greensQ8 g h > 0!
  have p7 : 0 < greensCol8 g h 7 := by
    change 0 < powInt g 7 * 1
    rw [Int.mul_one]
    exact powInt_pos g hg 7
  have f0 := balance_src_flux g h (greensQ8 g h) (greensCol8 g h 0) (greensCol8 g h 1) e0
  have f1 := balance_interior_flux g h (greensCol8 g h 0) (greensCol8 g h 1) (greensCol8 g h 2) e1
  have f2 := balance_interior_flux g h (greensCol8 g h 1) (greensCol8 g h 2) (greensCol8 g h 3) e2
  have f3 := balance_interior_flux g h (greensCol8 g h 2) (greensCol8 g h 3) (greensCol8 g h 4) e3
  have f4 := balance_interior_flux g h (greensCol8 g h 3) (greensCol8 g h 4) (greensCol8 g h 5) e4
  have f5 := balance_interior_flux g h (greensCol8 g h 4) (greensCol8 g h 5) (greensCol8 g h 6) e5
  have f6 := balance_interior_flux g h (greensCol8 g h 5) (greensCol8 g h 6) (greensCol8 g h 7) e6
  have f7 := balance_end_flux g h (greensCol8 g h 6) (greensCol8 g h 7) e7
  have h7 : 0 < h * greensCol8 g h 7 := Int.mul_pos hh p7
  have d67 : 0 < greensCol8 g h 6 - greensCol8 g h 7 := int_pos_of_mul_pos_right g _ hg (by omega)
  have h6 : 0 < h * greensCol8 g h 6 := Int.mul_pos hh (by omega)
  have d56 : 0 < greensCol8 g h 5 - greensCol8 g h 6 := int_pos_of_mul_pos_right g _ hg (by omega)
  have h5 : 0 < h * greensCol8 g h 5 := Int.mul_pos hh (by omega)
  have d45 : 0 < greensCol8 g h 4 - greensCol8 g h 5 := int_pos_of_mul_pos_right g _ hg (by omega)
  have h4 : 0 < h * greensCol8 g h 4 := Int.mul_pos hh (by omega)
  have d34 : 0 < greensCol8 g h 3 - greensCol8 g h 4 := int_pos_of_mul_pos_right g _ hg (by omega)
  have h3 : 0 < h * greensCol8 g h 3 := Int.mul_pos hh (by omega)
  have d23 : 0 < greensCol8 g h 2 - greensCol8 g h 3 := int_pos_of_mul_pos_right g _ hg (by omega)
  have h2 : 0 < h * greensCol8 g h 2 := Int.mul_pos hh (by omega)
  have d12 : 0 < greensCol8 g h 1 - greensCol8 g h 2 := int_pos_of_mul_pos_right g _ hg (by omega)
  have h1 : 0 < h * greensCol8 g h 1 := Int.mul_pos hh (by omega)
  have d01 : 0 < greensCol8 g h 0 - greensCol8 g h 1 := int_pos_of_mul_pos_right g _ hg (by omega)
  have h0 : 0 < h * greensCol8 g h 0 := Int.mul_pos hh (by omega)
  have hq : 0 < greensQ8 g h := by omega
  exact ⟨hq, hss, by omega, p7⟩

/-- Concrete anisotropic vapor-chamber / heat-pipe temperature profile where distant core 7 (64)
    exceeds adjacent core 1 (58) under heat injection at core 0. -/
def heatPipeProfile : Fin 8 → Int
  | ⟨0, _⟩ => 78 | ⟨1, _⟩ => 58 | ⟨2, _⟩ => 52 | ⟨3, _⟩ => 49
  | ⟨4, _⟩ => 48 | ⟨5, _⟩ => 51 | ⟨6, _⟩ => 56 | ⟨7, _⟩ => 64

/-- Theorem 3.8 (Concrete): Exact g=2, h=1 Green's column benchmark & anisotropic heat-pipe refutation. -/
theorem die8_g2_h1_and_heatpipe_refutation :
    greensCol8 2 1 0 = 10923 ∧
    greensCol8 2 1 1 = 5462 ∧
    greensCol8 2 1 7 = 128 ∧
    greensQ8 2 1 = 21845 ∧
    1 * sum8 (greensCol8 2 1) = greensQ8 2 1 ∧
    ¬ (∃ g h q : Int, 0 < g ∧ 0 < h ∧ 0 < q ∧ IsDie8SteadyState g h q heatPipeProfile) := by
  refine ⟨by decide, by decide, by decide, by decide, by decide, ?_⟩
  exact anisotropic_coupling_refutes_isotropic_chain heatPipeProfile ⟨1, by decide⟩ ⟨7, by decide⟩ (by decide) (by decide)

end CEERFoundations.Module3

#print axioms CEERFoundations.Module3.die8_laplacian_energy_conservation
#print axioms CEERFoundations.Module3.die8_far_end_strictly_positive
#print axioms CEERFoundations.Module3.die8_laplacian_strict_monotonicity
#print axioms CEERFoundations.Module3.die8_laplacian_strict_flux_decay
#print axioms CEERFoundations.Module3.die8_pairwise_distance_monotonicity
#print axioms CEERFoundations.Module3.anisotropic_coupling_refutes_isotropic_chain
#print axioms CEERFoundations.Module3.die8_greens_exact_solution_exists
#print axioms CEERFoundations.Module3.die8_g2_h1_and_heatpipe_refutation
