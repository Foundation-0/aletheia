/-
Track S102: Exact Integer & Rational Operators for the Drosophila MaleCNS v1.0
Connectome, Central-Complex Ring Attractor, Discrete LIF Pruning Invariants,
and Cross-Portal Engineering Bounds.

Pure-Init Lean 4.36.0 formalization (zero external imports, zero sorry/admit/
axiom/unsafe/native_decide/Classical.choice). All 18 theorems are universally
quantified (`∀`) algebraic or inductive operator laws.
-/

namespace DrosophilaConnectomeOperators

/-- Helper: square of any integer is non-negative (constructive, zero Classical.choice). -/
private theorem sq_nonneg (x : Int) : 0 ≤ x * x := by
  by_cases h : 0 ≤ x
  · exact Int.mul_nonneg h h
  · have hneg : 0 ≤ -x := by omega
    have hmul : 0 ≤ (-x) * (-x) := Int.mul_nonneg hneg hneg
    have heq : (-x) * (-x) = x * x := by
      rw [Int.neg_mul, Int.mul_neg, Int.neg_neg]
    rw [heq] at hmul
    exact hmul

/-- Helper: square of a nonzero integer is strictly positive. -/
private theorem sq_pos_of_ne_zero (x : Int) (hx : x ≠ 0) : 0 < x * x := by
  by_cases h : 0 < x
  · exact Int.mul_pos h h
  · have hneg : 0 < -x := by omega
    have hmul : 0 < (-x) * (-x) := Int.mul_pos hneg hneg
    have heq : (-x) * (-x) = x * x := by
      rw [Int.neg_mul, Int.mul_neg, Int.neg_neg]
    rw [heq] at hmul
    exact hmul

/-- Theorem 1 (Dale's-Law Partition Recovery):
    From unsigned signed-synapse total `T = E + I` and signed net balance `N = E - I`,
    both excitatory (`E`) and inhibitory (`I`) totals are uniquely recovered. -/
theorem dale_signed_partition_identity
    (exc inh total net : Int)
    (h_tot : exc + inh = total)
    (h_net : exc - inh = net) :
    2 * exc = total + net ∧ 2 * inh = total - net := by
  constructor
  · omega
  · omega

/-- Theorem 2 (Dale's-Law Row Sign-Homogeneity):
    When a presynaptic neuron or uniform population emits all outgoing synapses with a
    single Dale sign `s ∈ {+1, -1}`, multiplying signed net outflow by `s` recovers the
    exact unsigned outflow, and the squared net outflow equals the squared total outflow. -/
theorem dale_row_sign_homogeneity_bound
    (w1 w2 w3 s : Int)
    (hs : s = 1 ∨ s = -1) :
    s * (s * w1 + s * w2 + s * w3) = w1 + w2 + w3 ∧
    (s * w1 + s * w2 + s * w3) * (s * w1 + s * w2 + s * w3) =
      (w1 + w2 + w3) * (w1 + w2 + w3) := by
  cases hs with
  | inl h1 =>
    subst h1
    constructor
    · omega
    · simp [Int.one_mul]
  | inr h2 =>
    subst h2
    have h1 : (-1 : Int) * ((-1) * w1 + (-1) * w2 + (-1) * w3) = w1 + w2 + w3 := by omega
    have h2' : (-1 : Int) * w1 + (-1) * w2 + (-1) * w3 = -(w1 + w2 + w3) := by omega
    refine ⟨h1, ?_⟩
    rw [h2', Int.neg_mul, Int.mul_neg, Int.neg_neg]

/-- Theorem 3 (Heavy-Tail Synaptic Concentration vs Tail Depletion):
    If a top subset of `e_top < e_tot` edges captures strictly more than its uniform
    synapse share (`s_top * e_tot > s_tot * e_top`), then the remaining `e_tot - e_top > 0`
    edges carry `s_tot - s_top ≥ 0` synapses and strictly under-index the connectome mean. -/
theorem heavy_tail_concentration_lift
    (e_top e_tot s_top s_tot : Int)
    (he_lt : e_top < e_tot)
    (hs_le : s_top ≤ s_tot)
    (h_conc : s_top * e_tot > s_tot * e_top) :
    0 < e_tot - e_top ∧ 0 ≤ s_tot - s_top ∧
    (s_tot - s_top) * e_tot < s_tot * (e_tot - e_top) := by
  have hlhs : (s_tot - s_top) * e_tot = s_tot * e_tot - s_top * e_tot := Int.sub_mul s_tot s_top e_tot
  have hrhs : s_tot * (e_tot - e_top) = s_tot * e_tot - s_tot * e_top := Int.mul_sub s_tot e_tot e_top
  refine ⟨by omega, by omega, by omega⟩

/-- Theorem 4 (Entropy-Coded Connectome Storage Conservation):
    For `m` edges compressed from `b_raw` bits/edge to `b_enc < b_raw` bits/edge,
    encoded bits plus saved bits equal raw storage, and strict bit reduction implies
    strictly smaller encoded storage whenever `m > 0`. -/
theorem entropy_coding_bit_savings
    (m b_raw b_enc : Nat)
    (hm : 0 < m)
    (h_lt : b_enc < b_raw) :
    m * b_enc + m * (b_raw - b_enc) = m * b_raw ∧ m * b_enc < m * b_raw := by
  have h_le : b_enc ≤ b_raw := Nat.le_of_lt h_lt
  have h1 : m * b_enc + m * (b_raw - b_enc) = m * b_raw := by
    rw [← Nat.mul_add, Nat.add_sub_of_le h_le]
  have h2 : m * b_enc < m * b_raw := Nat.mul_lt_mul_of_pos_left h_lt hm
  exact ⟨h1, h2⟩

/-- Theorem 5 (Two-Level Active-Bitmap Quiet-Step Speedup):
    Scanning `n_blocks` summary words plus `k_active` populated blocks of width `b_size`
    performs strictly fewer operations than a full `n_blocks * b_size` neuron sweep
    whenever `b_size ≥ 2` and strictly fewer than half the blocks are active (`2 * k_active < n_blocks`). -/
theorem active_bitmap_two_level_work_bound
    (n_blocks b_size k_active : Nat)
    (hb : 2 ≤ b_size)
    (hk : 2 * k_active < n_blocks) :
    n_blocks + k_active * b_size < n_blocks * b_size := by
  have h2 : (n_blocks - k_active) * 2 ≤ (n_blocks - k_active) * b_size :=
    Nat.mul_le_mul_left (n_blocks - k_active) hb
  have h3 : n_blocks < (n_blocks - k_active) * 2 := by omega
  have h_strict : n_blocks < (n_blocks - k_active) * b_size := Nat.lt_of_lt_of_le h3 h2
  have h_split : k_active * b_size + (n_blocks - k_active) * b_size = n_blocks * b_size := by
    rw [← Nat.add_mul, Nat.add_sub_of_le (by omega : k_active ≤ n_blocks)]
  omega

/-- Theorem 6 (Discrete Integer LIF `may_fire` One-Step Lyapunov Invariant):
    Under the discrete leaky integrate-and-fire dynamics `20 * v' ≤ 19 * v + g` and
    `5 * g' ≤ 4 * g` (exact integer discretization of `dv = (g - v)/20`, `dg = -g/5`),
    the scaled envelope `4 * max(v, 0) + max(g, 0)` is strictly non-increasing for ALL
    integer states `(v, g, v', g')`. -/
theorem lif_may_fire_one_step_envelope
    (v g v' g' : Int)
    (hv : 20 * v' ≤ 19 * v + g)
    (hg : 5 * g' ≤ 4 * g) :
    4 * max v' 0 + max g' 0 ≤ 4 * max v 0 + max g 0 := by
  omega

/-- Theorem 7 (Discrete Integer LIF `may_fire` Infinite-Horizon Pruning Theorem):
    By induction on step count `k : Nat`, if a quiescent neuron starts with
    `4 * max(v 0, 0) + max(g 0, 0) < 4 * theta` and receives no external spikes,
    then `v k < theta` for EVERY future time step `k : Nat` (soundness of `may_fire`). -/
theorem lif_may_fire_horizon_safety
    (v g : Nat → Int)
    (theta : Int)
    (h_step : ∀ t, 20 * v (t + 1) ≤ 19 * v t + g t ∧ 5 * g (t + 1) ≤ 4 * g t)
    (h_init : 4 * max (v 0) 0 + max (g 0) 0 < 4 * theta) :
    ∀ k : Nat, v k < theta := by
  have h_env : ∀ k : Nat, 4 * max (v k) 0 + max (g k) 0 ≤ 4 * max (v 0) 0 + max (g 0) 0 := by
    intro k
    induction k with
    | zero => exact Int.le_refl _
    | succ t ih =>
      have ⟨hv, hg⟩ := h_step t
      have h1 := lif_may_fire_one_step_envelope (v t) (g t) (v (t + 1)) (g (t + 1)) hv hg
      exact Int.le_trans h1 ih
  intro k
  have hk := h_env k
  omega

/-- Theorem 8 (Al-Tusi Symmetric / Skew Pythagorean Frobenius Identity on `2×2` Blocks):
    Clearing denominators by `4`, any directed coupling block `W = [[a, b], [c, d]]`
    decomposes orthogonally into symmetric `(W + W^T)/2` and skew `(W - W^T)/2` parts. -/
theorem al_tusi_pythagorean_frobenius_2x2
    (a b c d : Int) :
    4 * (a * a + b * b + c * c + d * d) =
      (2 * a) * (2 * a) + (2 * d) * (2 * d) + 2 * ((b + c) * (b + c)) + 2 * ((b - c) * (b - c)) := by
  have hbc : (b + c) * (b + c) + (b - c) * (b - c) = 2 * (b * b + c * c) := by
    have h1 : (b + c) * (b + c) = b * b + b * c + (c * b + c * c) := by
      rw [Int.add_mul, Int.mul_add, Int.mul_add]
    have h2 : (b - c) * (b - c) = b * b - b * c - (c * b - c * c) := by
      rw [Int.sub_mul, Int.mul_sub, Int.mul_sub]
    have hcb : c * b = b * c := Int.mul_comm c b
    omega
  have ha : (2 * a) * (2 * a) = 4 * (a * a) := by
    rw [Int.mul_assoc, Int.mul_left_comm a 2 a, ← Int.mul_assoc 2 2]
    rfl
  have hd : (2 * d) * (2 * d) = 4 * (d * d) := by
    rw [Int.mul_assoc, Int.mul_left_comm d 2 d, ← Int.mul_assoc 2 2]
    rfl
  omega

/-- Theorem 9 (Exact Non-Normal Commutator Frobenius Norm on `2×2` Blocks):
    For `W = [[a, b], [c, d]]`, the commutator `[W, W^T] = W W^T - W^T W` has exact
    squared Frobenius norm `2 * (b - c)^2 * ((b + c)^2 + (a - d)^2)`, which is
    strictly positive whenever `b ≠ c` and `b + c ≠ 0` (asymmetric feedforward necks). -/
theorem nonnormal_commutator_2x2_exact
    (a b c d : Int) :
    let c11 := b * b - c * c
    let c12 := (a - d) * (c - b)
    (c11 * c11 + c12 * c12 + c12 * c12 + (-c11) * (-c11)) =
      2 * ((b - c) * (b - c)) * ((b + c) * (b + c) + (a - d) * (a - d)) := by
  dsimp only
  have hneg : (-(b * b - c * c)) * (-(b * b - c * c)) = (b * b - c * c) * (b * b - c * c) := by
    rw [Int.neg_mul, Int.mul_neg, Int.neg_neg]
  have hdiff : b * b - c * c = (b - c) * (b + c) := by
    have h1 : (b - c) * (b + c) = b * b + b * c - (c * b + c * c) := by
      rw [Int.sub_mul, Int.mul_add, Int.mul_add]
    have hcb : c * b = b * c := Int.mul_comm c b
    omega
  have hcb_flip : c - b = -(b - c) := by omega
  have h12 : ((a - d) * (c - b)) * ((a - d) * (c - b)) =
      ((b - c) * (b - c)) * ((a - d) * (a - d)) := by
    rw [hcb_flip, Int.mul_neg, Int.neg_mul, Int.mul_neg, Int.neg_neg]
    rw [Int.mul_assoc, Int.mul_left_comm (b - c) (a - d) (b - c)]
    rw [← Int.mul_assoc (a - d) (a - d), Int.mul_comm ((a - d) * (a - d))]
  have h11 : (b * b - c * c) * (b * b - c * c) =
      ((b - c) * (b - c)) * ((b + c) * (b + c)) := by
    rw [hdiff]
    rw [Int.mul_assoc, Int.mul_left_comm (b + c) (b - c) (b + c), ← Int.mul_assoc (b - c) (b - c)]
  have hrhs :
      2 * ((b - c) * (b - c)) * ((b + c) * (b + c) + (a - d) * (a - d)) =
      2 * (((b - c) * (b - c)) * ((b + c) * (b + c))) +
      2 * (((b - c) * (b - c)) * ((a - d) * (a - d))) := by
    rw [Int.mul_add, Int.mul_assoc 2, Int.mul_assoc 2]
  rw [hneg, h11, h12, hrhs]
  omega

/-- Theorem 10 (Strict Non-Normality of Asymmetric Directed Feedforward Coupling):
    Any `2×2` coupling block with `b ≠ c` and `b + c ≠ 0` has strictly positive
    commutator Frobenius norm `||[W, W^T]||_F^2 > 0`. -/
theorem nonnormal_commutator_strict_pos
    (a b c d : Int)
    (h_asym : b ≠ c)
    (h_non_skew : b + c ≠ 0) :
    0 < 2 * ((b - c) * (b - c)) * ((b + c) * (b + c) + (a - d) * (a - d)) := by
  have h1 : 0 < (b - c) * (b - c) := sq_pos_of_ne_zero (b - c) (by omega)
  have h2 : 0 < (b + c) * (b + c) := sq_pos_of_ne_zero (b + c) h_non_skew
  have h3 : 0 ≤ (a - d) * (a - d) := sq_nonneg (a - d)
  have h4 : 0 < (b + c) * (b + c) + (a - d) * (a - d) := by omega
  have h5 : 0 < 2 * ((b - c) * (b - c)) := by omega
  exact Int.mul_pos h5 h4

/-- Theorem 11 (Al-Tusi E–I Opposing Loop Real-Eigenvalue Obstruction):
    For an excitatory-inhibitory feedback pair `[[0, alpha], [-beta, 0]]` with
    `alpha > 0, beta > 0` (such as `EPG ↔ ER` / `EPG ↔ Delta7`), the characteristic
    polynomial `λ^2 + alpha * beta` is strictly positive for all `λ : Int` (oscillatory
    rotational mode, zero real integer fixed-point eigenvalues). -/
theorem al_tusi_ei_loop_oscillatory_obstruction
    (alpha beta lam : Int)
    (ha : 0 < alpha)
    (hb : 0 < beta) :
    0 < lam * lam + alpha * beta := by
  have hsq : 0 ≤ lam * lam := sq_nonneg lam
  have hab : 0 < alpha * beta := Int.mul_pos ha hb
  omega

/-- Theorem 12 (Signed Laplacian Quadratic Form PSD & Zero-Mode Characterization):
    On any Dale's-law signed edge pair `(w_pos ≥ 0, w_neg ≥ 0)`, the signed Laplacian
    energy `w_pos * (x - y)^2 + w_neg * (x + y)^2` is non-negative for all potentials
    `x, y : Int`; when both `w_pos > 0` and `w_neg > 0`, energy vanishes iff `x = 0 ∧ y = 0`
    (frustrated conflict kills all nonzero harmonic modes). -/
theorem signed_laplacian_energy_and_frustration
    (w_pos w_neg x y : Int)
    (hp : 0 ≤ w_pos)
    (hn : 0 ≤ w_neg) :
    0 ≤ w_pos * ((x - y) * (x - y)) + w_neg * ((x + y) * (x + y)) ∧
    (0 < w_pos → 0 < w_neg →
      w_pos * ((x - y) * (x - y)) + w_neg * ((x + y) * (x + y)) = 0 →
      x = 0 ∧ y = 0) := by
  have h1 : 0 ≤ w_pos * ((x - y) * (x - y)) := Int.mul_nonneg hp (sq_nonneg (x - y))
  have h2 : 0 ≤ w_neg * ((x + y) * (x + y)) := Int.mul_nonneg hn (sq_nonneg (x + y))
  refine ⟨by omega, ?_⟩
  intro hp_pos hn_pos hzero
  have hz1 : w_pos * ((x - y) * (x - y)) = 0 := by omega
  have hz2 : w_neg * ((x + y) * (x + y)) = 0 := by omega
  have hxy1 : x - y = 0 := by
    by_cases hne : x - y = 0
    · exact hne
    · have hpos := Int.mul_pos hp_pos (sq_pos_of_ne_zero (x - y) hne)
      omega
  have hxy2 : x + y = 0 := by
    by_cases hne : x + y = 0
    · exact hne
    · have hpos := Int.mul_pos hn_pos (sq_pos_of_ne_zero (x + y) hne)
      omega
  exact ⟨by omega, by omega⟩

/-- Theorem 13 (Signed Triad Coherent / Incoherent Exact Gauge Invariance):
    For any vertex gauge `(g1, g2, g3) ∈ {+1, -1}^3`, switching edge signs via
    `s'_ij = g_i * s_ij * g_j` leaves every closed 3-cycle sign product strictly
    invariant (Zaslavsky's signed-graph switching theorem on 3-cycles). -/
theorem signed_triad_switching_invariance
    (g1 g2 g3 s12 s23 s31 : Int)
    (hg1 : g1 = 1 ∨ g1 = -1)
    (hg2 : g2 = 1 ∨ g2 = -1)
    (hg3 : g3 = 1 ∨ g3 = -1) :
    (g1 * s12 * g2) * (g2 * s23 * g3) * (g3 * s31 * g1) = s12 * s23 * s31 := by
  cases hg1 with
  | inl h1 =>
    subst h1
    cases hg2 with
    | inl h2 =>
      subst h2
      cases hg3 with
      | inl h3 =>
        subst h3
        simp [Int.one_mul, Int.mul_one]
      | inr h3 =>
        subst h3
        simp [Int.one_mul, Int.mul_one, Int.mul_neg, Int.neg_mul, Int.neg_neg]
    | inr h2 =>
      subst h2
      cases hg3 with
      | inl h3 =>
        subst h3
        simp [Int.one_mul, Int.mul_one, Int.mul_neg, Int.neg_mul, Int.neg_neg]
      | inr h3 =>
        subst h3
        simp [Int.one_mul, Int.mul_one, Int.mul_neg, Int.neg_mul, Int.neg_neg]
  | inr h1 =>
    subst h1
    cases hg2 with
    | inl h2 =>
      subst h2
      cases hg3 with
      | inl h3 =>
        subst h3
        simp [Int.one_mul, Int.mul_one, Int.mul_neg, Int.neg_mul, Int.neg_neg]
      | inr h3 =>
        subst h3
        simp [Int.one_mul, Int.mul_one, Int.mul_neg, Int.neg_mul, Int.neg_neg]
    | inr h2 =>
      subst h2
      cases hg3 with
      | inl h3 =>
        subst h3
        simp [Int.one_mul, Int.mul_one, Int.mul_neg, Int.neg_mul, Int.neg_neg]
      | inr h3 =>
        subst h3
        simp [Int.one_mul, Int.mul_one, Int.mul_neg, Int.neg_mul, Int.neg_neg]

/-- Theorem 14 (Schur Complement `⧄` Exact Quadratic Completion):
    For any symmetric `2×2` integer operator `[[a, b], [b, d]]`, clearing the Schur
    pivot denominator by `a` gives `a * (a x^2 + 2 b x y + d y^2) = (a x + b y)^2 + (a d - b^2) y^2`. -/
theorem schur_complement_2x2_completion
    (a b d x y : Int) :
    a * (a * (x * x) + 2 * b * x * y + d * (y * y)) =
      (a * x + b * y) * (a * x + b * y) + (a * d - b * b) * (y * y) := by
  have h1 : (a * x + b * y) * (a * x + b * y) =
      (a * x) * (a * x) + (a * x) * (b * y) + ((b * y) * (a * x) + (b * y) * (b * y)) := by
    rw [Int.add_mul, Int.mul_add, Int.mul_add]
  have h2 : (a * x) * (a * x) = a * (a * (x * x)) := by
    rw [Int.mul_assoc, Int.mul_left_comm x a x, ← Int.mul_assoc]
  have h3 : (b * y) * (b * y) = (b * b) * (y * y) := by
    rw [Int.mul_assoc, Int.mul_left_comm y b y, ← Int.mul_assoc]
  have h4 : (a * x) * (b * y) = a * (b * x * y) := by
    rw [Int.mul_assoc a x (b * y), ← Int.mul_assoc x b y, Int.mul_comm x b]
  have h5 : (b * y) * (a * x) = a * (b * x * y) := by
    rw [Int.mul_comm (b * y) (a * x), h4]
  have h6 : (a * d - b * b) * (y * y) = a * (d * (y * y)) - (b * b) * (y * y) := by
    rw [Int.sub_mul, Int.mul_assoc]
  have h7 : a * (a * (x * x) + 2 * b * x * y + d * (y * y)) =
      a * (a * (x * x)) + a * (2 * b * x * y) + a * (d * (y * y)) := by
    rw [Int.mul_add, Int.mul_add]
  have h8 : a * (2 * b * x * y) = 2 * (a * (b * x * y)) := by
    have h2b : 2 * b * x * y = 2 * (b * x * y) := by
      rw [Int.mul_assoc 2 b x, Int.mul_assoc 2 (b * x) y]
    rw [h2b, Int.mul_left_comm]
  rw [h1, h2, h3, h4, h5, h6, h7, h8]
  omega

/-- Theorem 15 (Krein Indefinite Inertia `⦺` Witness on Negative Schur Pivot):
    Whenever `a > 0` and the Schur complement determinant `a * d - b^2 < 0`, the symmetric
    form `Q(x, y) = a x^2 + 2 b x y + d y^2` attains `Q(1, 0) > 0` and `Q(-b, a) < 0`,
    certifying indefinite Krein signature `(n_pos ≥ 1, n_neg ≥ 1)`. -/
theorem krein_indefinite_signature_witness
    (a b d : Int)
    (ha : 0 < a)
    (hdet : a * d - b * b < 0) :
    (a * (1 * 1) + 2 * b * 1 * 0 + d * (0 * 0) > 0) ∧
    (a * ((-b) * (-b)) + 2 * b * (-b) * a + d * (a * a) < 0) := by
  constructor
  · omega
  · have hcomp := schur_complement_2x2_completion a b d (-b) a
    have hcancel : a * (-b) + b * a = 0 := by
      rw [Int.mul_neg, Int.mul_comm b a]
      omega
    rw [hcancel] at hcomp
    have hsqa : 0 < a * a := Int.mul_pos ha ha
    have hneg_prod : (a * d - b * b) * (a * a) < 0 := by
      have hpos : 0 < (-(a * d - b * b)) * (a * a) := Int.mul_pos (by omega) hsqa
      rw [Int.neg_mul] at hpos
      omega
    have hq_neg : a * (a * ((-b) * (-b)) + 2 * b * (-b) * a + d * (a * a)) < 0 := by
      omega
    by_cases hq : a * ((-b) * (-b)) + 2 * b * (-b) * a + d * (a * a) < 0
    · exact hq
    · have hge : 0 ≤ a * (a * ((-b) * (-b)) + 2 * b * (-b) * a + d * (a * a)) :=
        Int.mul_nonneg (by omega) (by omega)
      omega

/-- Theorem 16 (Law-5 SpMV Memory-Bandwidth Crossover Bound — `nfly` vs `S94` `b_crit`):
    When sparse indirect SpMV traffic satisfies `bytes_mlp * ops_spmv < bytes_spmv * ops_mlp`,
    the sparse kernel's byte-per-op intensity strictly exceeds dense GEMM by at least `1`
    in integer cross-product form. -/
theorem spmv_bandwidth_intensity_crossover
    (ops_spmv ops_mlp bytes_spmv bytes_mlp : Nat)
    (h_int : bytes_mlp * ops_spmv < bytes_spmv * ops_mlp) :
    bytes_mlp * ops_spmv + 1 ≤ bytes_spmv * ops_mlp ∧
    0 < bytes_spmv * ops_mlp := by
  constructor
  · omega
  · omega

/-- Theorem 17 (4-Arm Connectome Tail-Risk Dominance — `fly-racer` Lens):
    If a connectome-constrained policy achieves mean `mu_f ≥ mu_m` with strictly lower
    dispersion `sd_f < sd_m` than an unconstrained MLP baseline, then for EVERY
    positive risk multiplier `k > 0`, its `k`-sigma lower floor strictly dominates. -/
theorem four_arm_tail_risk_dominance
    (mu_f sd_f mu_m sd_m k : Int)
    (hmu : mu_m ≤ mu_f)
    (hsd : sd_f < sd_m)
    (hk : 0 < k) :
    mu_m - k * sd_m < mu_f - k * sd_f := by
  have hdiff : 0 < k * (sd_m - sd_f) := Int.mul_pos hk (by omega)
  have hmul : k * (sd_m - sd_f) = k * sd_m - k * sd_f := Int.mul_sub k sd_m sd_f
  omega

/-- Theorem 18 (Biological Redundancy vs LLM Hessian Sensitivity Concentration Gap):
    When biological top-`p` synaptic capture `(num_bio / den_bio)` satisfies
    `num_bio * den_hess < num_hess * den_bio` relative to LLM Hessian-CSR capture
    `(num_hess / den_hess)`, the exact rational concentration gap is strictly positive
    and sums back to `num_hess * den_bio`. -/
theorem bio_vs_hessian_concentration_gap
    (num_bio den_bio num_hess den_hess : Nat)
    (h_lt : num_bio * den_hess < num_hess * den_bio) :
    0 < num_hess * den_bio - num_bio * den_hess ∧
    num_bio * den_hess + (num_hess * den_bio - num_bio * den_hess) = num_hess * den_bio := by
  constructor
  · omega
  · omega

#print axioms DrosophilaConnectomeOperators.dale_signed_partition_identity
#print axioms DrosophilaConnectomeOperators.dale_row_sign_homogeneity_bound
#print axioms DrosophilaConnectomeOperators.heavy_tail_concentration_lift
#print axioms DrosophilaConnectomeOperators.entropy_coding_bit_savings
#print axioms DrosophilaConnectomeOperators.active_bitmap_two_level_work_bound
#print axioms DrosophilaConnectomeOperators.lif_may_fire_one_step_envelope
#print axioms DrosophilaConnectomeOperators.lif_may_fire_horizon_safety
#print axioms DrosophilaConnectomeOperators.al_tusi_pythagorean_frobenius_2x2
#print axioms DrosophilaConnectomeOperators.nonnormal_commutator_2x2_exact
#print axioms DrosophilaConnectomeOperators.nonnormal_commutator_strict_pos
#print axioms DrosophilaConnectomeOperators.al_tusi_ei_loop_oscillatory_obstruction
#print axioms DrosophilaConnectomeOperators.signed_laplacian_energy_and_frustration
#print axioms DrosophilaConnectomeOperators.signed_triad_switching_invariance
#print axioms DrosophilaConnectomeOperators.schur_complement_2x2_completion
#print axioms DrosophilaConnectomeOperators.krein_indefinite_signature_witness
#print axioms DrosophilaConnectomeOperators.spmv_bandwidth_intensity_crossover
#print axioms DrosophilaConnectomeOperators.four_arm_tail_risk_dominance
#print axioms DrosophilaConnectomeOperators.bio_vs_hessian_concentration_gap

end DrosophilaConnectomeOperators
