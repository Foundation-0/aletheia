/-
Track S166 (`EXP-Q48`, `EXP-Q49`, `EXP-Q46b`): Pure-Init Lean 4.36.0 Formalization of
the CS-29 (`SOP-20`) Thin-Coordinator vs. Inline-Tool Context-Tax Crossover Theorem
(with Compaction-Frequency & Cold-Miss Amplification), plus CS-27 DAG Acyclicity
and CS-28 Law-5 Zero-Operator Obstruction Laws.

Zero external imports (pure `Init`), zero `sorry`/`admit`/`axiom`/`unsafe`/`native_decide`,
and zero `Classical.choice`. All 12 public theorems depend strictly on Lean kernel
primitives (`propext`, `Quot.sound`, or zero axioms).
-/

namespace ThinCoordInterpose

private theorem mul_pos_four (a b c d : Int)
    (ha : 0 < a) (hb : 0 < b) (hc : 0 < c) (hd : 0 < d) :
    0 < a * b * c * d := by
  exact Int.mul_pos (Int.mul_pos (Int.mul_pos ha hb) hc) hd

private theorem distrib_sub_mul (T B s c : Int) :
    T * B * c - T * s * c = T * (B - s) * c := by
  calc
    T * B * c - T * s * c = (T * B - T * s) * c := by rw [Int.sub_mul]
    _ = (T * (B - s)) * c := by rw [Int.mul_sub]

private theorem monotone_nonneg_mul (x y k : Int) (hk : 0 ≤ k) (hxy : x ≤ y) :
    x * k ≤ y * k := by
  have hd : 0 ≤ (y - x) * k := Int.mul_nonneg (by omega) hk
  rw [Int.sub_mul] at hd
  omega

private theorem monotone_pos_mul (x y k : Int) (hk : 0 < k) (hxy : x < y) :
    x * k < y * k := by
  have hd : 0 < (y - x) * k := Int.mul_pos (by omega) hk
  rw [Int.sub_mul] at hd
  omega

/- =========================================================================
   GROUP A (CS-29 / SOP-20): Thin-Coordinator vs Inline-Tool Context-Tax
   Crossover Theorem & Compaction-Frequency Amplification
   ========================================================================= -/

/-- Theorem 1 (CS-29 Base Context-Tax Crossover Equivalence):
    For remaining coordinator turns `T > 0`, inline payload `B`, condensed summary `s`,
    cached input price `c_hit = n_h / d_h` (`n_h > 0, d_h > 0`), and worker offload cost
    `W_worker = n_w / d_w` (`n_w >= 0, d_w > 0`), in exact cleared-denominator form:
      `T * B * c_hit > W_worker + T * s * c_hit`
    holds if and only if
      `T * (B - s) * c_hit > W_worker`. -/
theorem thin_coord_crossover_iff
    (T B s n_h d_h n_w d_w : Int) :
    let inline_num := T * B * (n_h * d_w)
    let offload_num := n_w * d_h + T * s * (n_h * d_w)
    (offload_num < inline_num) ↔ (n_w * d_h < T * (B - s) * (n_h * d_w)) := by
  intro inline_num offload_num
  have hdiff : inline_num - T * s * (n_h * d_w) = T * (B - s) * (n_h * d_w) :=
    distrib_sub_mul T B s (n_h * d_w)
  constructor
  · intro hlt
    omega
  · intro hlt
    omega

/-- Theorem 2 (CS-29 Exact Crossover Boundary Has Zero Strict Dominance):
    When `T * (B - s) * (n_h * d_w) = n_w * d_h`, the inline cost and offload cost
    are identically equal (`inline_num = offload_num`), so offload does not strictly win. -/
theorem thin_coord_equal_crossover_no_strict_dominance
    (T B s n_h d_h n_w d_w : Int)
    (heq : T * (B - s) * (n_h * d_w) = n_w * d_h) :
    let inline_num := T * B * (n_h * d_w)
    let offload_num := n_w * d_h + T * s * (n_h * d_w)
    inline_num = offload_num ∧ ¬(offload_num < inline_num) := by
  intro inline_num offload_num
  have hdiff : inline_num - T * s * (n_h * d_w) = T * (B - s) * (n_h * d_w) :=
    distrib_sub_mul T B s (n_h * d_w)
  constructor
  · omega
  · omega

/-- Theorem 3 (CS-29 No-Offload Boundary When Summary >= Payload):
    When `B ≤ s` (the condensed summary is no smaller than the raw payload), `T > 0`,
    `n_h > 0, d_h > 0`, `n_w ≥ 0, d_w > 0`, inline cost is always `≤` offload cost,
    so offloading never strictly reduces base context cost. -/
theorem thin_coord_no_offload_when_summary_ge_payload
    (T B s n_h d_h n_w d_w : Int)
    (hT : 0 < T) (hBs : B ≤ s)
    (hnh : 0 < n_h) (hdh : 0 < d_h) (hnw : 0 ≤ n_w) (hdw : 0 < d_w) :
    let inline_num := T * B * (n_h * d_w)
    let offload_num := n_w * d_h + T * s * (n_h * d_w)
    inline_num ≤ offload_num ∧ ¬(offload_num < inline_num) := by
  intro inline_num offload_num
  have hc_pos : 0 < n_h * d_w := Int.mul_pos hnh hdw
  have hT_nonneg : 0 ≤ T := by omega
  have hdiff_nonpos : T * (B - s) ≤ 0 := by
    have hneg : 0 ≤ T * (s - B) := Int.mul_nonneg hT_nonneg (by omega)
    rw [Int.mul_sub] at hneg ⊢
    omega
  have hprod_nonpos : T * (B - s) * (n_h * d_w) ≤ 0 := by
    have hnn : 0 ≤ (-(T * (B - s))) * (n_h * d_w) :=
      Int.mul_nonneg (by omega) (by omega)
    rw [Int.neg_mul] at hnn
    omega
  have hw_nonneg : 0 ≤ n_w * d_h := Int.mul_nonneg hnw (by omega)
  have hsplit : inline_num - T * s * (n_h * d_w) = T * (B - s) * (n_h * d_w) :=
    distrib_sub_mul T B s (n_h * d_w)
  exact ⟨by omega, by omega⟩

/-- Theorem 4 (CS-29 Payload Monotonicity):
    For `T > 0` and positive hit cost `n_h * d_w > 0`, increasing inline payload `B ≤ B'`
    monotonically increases offload savings `inline_num - offload_num` and preserves
    strict offload dominance. -/
theorem thin_coord_payload_monotone_dominance
    (T B B' s n_h d_h n_w d_w : Int)
    (hT : 0 < T) (hnh : 0 < n_h) (hdw : 0 < d_w) (hBB' : B ≤ B') :
    let savB := T * B * (n_h * d_w) - (n_w * d_h + T * s * (n_h * d_w))
    let savB' := T * B' * (n_h * d_w) - (n_w * d_h + T * s * (n_h * d_w))
    savB ≤ savB' ∧ (0 < savB → 0 < savB') := by
  intro savB savB'
  have hmul : T * (n_h * d_w) ≥ 0 := Int.mul_nonneg (by omega) (Int.mul_nonneg (by omega) (by omega))
  have hgap : T * B' * (n_h * d_w) - T * B * (n_h * d_w) = T * (B' - B) * (n_h * d_w) :=
    distrib_sub_mul T B' B (n_h * d_w)
  have hpos_gap : 0 ≤ T * (B' - B) * (n_h * d_w) := by
    have h1 : 0 ≤ T * (B' - B) := Int.mul_nonneg (by omega) (by omega)
    exact Int.mul_nonneg h1 (Int.mul_nonneg (by omega) (by omega))
  have _ := hmul
  have hle : savB ≤ savB' := by omega
  exact ⟨hle, fun h => by omega⟩

/-- Theorem 5 (CS-29 Turn-Horizon Monotonicity):
    When `B > s` and hit cost `n_h * d_w > 0`, extending the remaining turn horizon
    `T ≤ T'` monotonically increases offload savings and preserves strict dominance. -/
theorem thin_coord_turn_monotone_dominance
    (T T' B s n_h d_h n_w d_w : Int)
    (hsB : s < B) (hnh : 0 < n_h) (hdw : 0 < d_w) (hTT' : T ≤ T') :
    let savT := T * B * (n_h * d_w) - (n_w * d_h + T * s * (n_h * d_w))
    let savT' := T' * B * (n_h * d_w) - (n_w * d_h + T' * s * (n_h * d_w))
    savT ≤ savT' ∧ (0 < savT → 0 < savT') := by
  intro savT savT'
  have h1 : T * B * (n_h * d_w) - T * s * (n_h * d_w) = T * (B - s) * (n_h * d_w) :=
    distrib_sub_mul T B s (n_h * d_w)
  have h2 : T' * B * (n_h * d_w) - T' * s * (n_h * d_w) = T' * (B - s) * (n_h * d_w) :=
    distrib_sub_mul T' B s (n_h * d_w)
  have hdiff : T' * (B - s) * (n_h * d_w) - T * (B - s) * (n_h * d_w) =
      (T' - T) * (B - s) * (n_h * d_w) := by
    rw [← Int.sub_mul, ← Int.sub_mul]
  have hpos_step : 0 ≤ (T' - T) * (B - s) * (n_h * d_w) :=
    Int.mul_nonneg (Int.mul_nonneg (by omega) (by omega)) (Int.mul_nonneg (by omega) (by omega))
  have hle : savT ≤ savT' := by omega
  exact ⟨hle, fun h => by omega⟩

/-- Theorem 6 (CS-29 Amplified Context-Tax Crossover with Compaction & Cold-Miss Penalties):
    Including `dk = k_inline - k_offload` extra compactions at cost `K_comp = n_k / d_k`
    and `m_cold` cold-cache reactivation reads at price `c_miss = n_m / d_m` over the
    common positive denominator `D = d_h * d_w * d_m * d_k`, amplified inline cost
    strictly exceeds amplified offload cost if and only if the exact cleared-denominator
    sum of warm-turn savings, cold-miss savings, and compaction-avoidance savings
    strictly exceeds worker cost. -/
theorem thin_coord_compaction_amplification_iff
    (T B s m_cold dk n_h d_h n_w d_w n_m d_m n_k d_k : Int) :
    let inline_amp :=
      T * B * (n_h * d_w * d_m * d_k)
      + m_cold * B * (n_m * d_h * d_w * d_k)
      + dk * n_k * (d_h * d_w * d_m)
    let offload_amp :=
      n_w * (d_h * d_m * d_k)
      + T * s * (n_h * d_w * d_m * d_k)
      + m_cold * s * (n_m * d_h * d_w * d_k)
    (offload_amp < inline_amp) ↔
      (n_w * (d_h * d_m * d_k) <
        T * (B - s) * (n_h * d_w * d_m * d_k)
        + m_cold * (B - s) * (n_m * d_h * d_w * d_k)
        + dk * n_k * (d_h * d_w * d_m)) := by
  intro inline_amp offload_amp
  have hw : T * B * (n_h * d_w * d_m * d_k) - T * s * (n_h * d_w * d_m * d_k) =
      T * (B - s) * (n_h * d_w * d_m * d_k) :=
    distrib_sub_mul T B s (n_h * d_w * d_m * d_k)
  have hm : m_cold * B * (n_m * d_h * d_w * d_k) - m_cold * s * (n_m * d_h * d_w * d_k) =
      m_cold * (B - s) * (n_m * d_h * d_w * d_k) :=
    distrib_sub_mul m_cold B s (n_m * d_h * d_w * d_k)
  constructor
  · intro hlt
    omega
  · intro hlt
    omega

/-- Theorem 7 (CS-29 Compaction & Cold-Miss Amplification Strictly Lowers Offload Bar):
    When `s ≤ B`, `m_cold ≥ 0`, `dk ≥ 0`, and all rates/denominators are non-negative
    with positive denominators, amplified offload savings is always `≥` base offload
    savings (scaled by `d_m * d_k`), and if base costs already tie (`sav_base ≥ 0`)
    while `dk > 0` and `n_k > 0`, offload strictly dominates (`offload_amp < inline_amp`). -/
theorem thin_coord_compaction_amplification_strict_gain
    (T B s m_cold dk n_h d_h n_w d_w n_m d_m n_k d_k : Int)
    (hsB : s ≤ B) (hm_cold : 0 ≤ m_cold) (hdk : 0 ≤ dk)
    (hdh : 0 < d_h) (hdw : 0 < d_w) (hdm : 0 < d_m) (hdk_den : 0 < d_k)
    (hnm : 0 ≤ n_m) (hnk : 0 ≤ n_k) :
    let sav_base_scaled :=
      (T * (B - s) * (n_h * d_w) - n_w * d_h) * (d_m * d_k)
    let cold_gain := m_cold * (B - s) * (n_m * d_h * d_w * d_k)
    let comp_gain := dk * n_k * (d_h * d_w * d_m)
    let sav_amp := sav_base_scaled + cold_gain + comp_gain
    sav_base_scaled ≤ sav_amp ∧
    ((0 ≤ sav_base_scaled ∧ 0 < dk ∧ 0 < n_k) → 0 < sav_amp) := by
  intro sav_base_scaled cold_gain comp_gain sav_amp
  have hcold_nn : 0 ≤ cold_gain := by
    have h1 : 0 ≤ m_cold * (B - s) := Int.mul_nonneg hm_cold (by omega)
    have h2 : 0 ≤ n_m * d_h * d_w * d_k :=
      Int.mul_nonneg (Int.mul_nonneg (Int.mul_nonneg hnm (by omega)) (by omega)) (by omega)
    exact Int.mul_nonneg h1 h2
  have hcomp_nn : 0 ≤ comp_gain := by
    have h1 : 0 ≤ dk * n_k := Int.mul_nonneg hdk hnk
    have h2 : 0 ≤ d_h * d_w * d_m :=
      Int.mul_nonneg (Int.mul_nonneg (by omega) (by omega)) (by omega)
    exact Int.mul_nonneg h1 h2
  refine ⟨by omega, ?_⟩
  intro ⟨hbase, hdk_pos, hnk_pos⟩
  have h3 : 0 < d_h * d_w * d_m := Int.mul_pos (Int.mul_pos hdh hdw) hdm
  have hcomp_pos : 0 < comp_gain := Int.mul_pos (Int.mul_pos hdk_pos hnk_pos) h3
  omega

/-- Theorem 8 (CS-29 Concrete 40-Line Offload & Compaction Witness):
    Exact concrete witness matching the practical `> ~40`-line offload rule:
    for `T = 20`, `B = 2000`, `s = 120`, `c_hit = 1/10`, `W_worker = 2400`:
    inline cost is `4000 > 2640` token units (`40000 > 26400` in `10x`-cleared integers,
    saving `1360` token units = `13600` cleared units);
    and with `T = 12`, `dk = 1` compaction at `K_comp = 5000`, amplified inline
    cost `7400 > 2544` token units (`74000 > 25440` in `10x`-cleared integers,
    saving `4856` token units = `48560` cleared units) even before larger `T`. -/
theorem thin_coord_40line_rule_concrete_witness :
    let inline1 := 20 * 2000 * (1 * 1)
    let offload1 := 2400 * 10 + 20 * 120 * (1 * 1)
    let inline2 := 12 * 2000 * 1 + 1 * 5000 * 10
    let offload2 := 2400 * 10 + 12 * 120 * 1
    (offload1 < inline1 ∧ inline1 - offload1 = 13600) ∧
    (offload2 < inline2 ∧ inline2 - offload2 = 48560) := by
  decide

/- =========================================================================
   GROUP B (CS-27 / SOP-18 & CS-28 / SOP-19): Cycle-Safe DAG Depth Obstruction,
   Symmetric Portfolio Coverage Ratio, and Law-5 Operator Gate Laws
   ========================================================================= -/

/-- Non-empty directed walk in an arbitrary graph relation `edge`. -/
inductive DirWalk (edge : Nat → Nat → Prop) : Nat → Nat → Prop where
  | single : edge u v → DirWalk edge u v
  | step : edge u v → DirWalk edge v w → DirWalk edge u w

private theorem walk_depth_monotone
    (edge : Nat → Nat → Prop) (depth : Nat → Int)
    (hmono : ∀ a b, edge a b → depth a ≤ depth b)
    {u v : Nat} (hw : DirWalk edge u v) :
    depth u ≤ depth v := by
  induction hw with
  | single h => exact hmono _ _ h
  | step h _ ih => exact Int.le_trans (hmono _ _ h) ih

/-- Theorem 9 (CS-27 Strict-Increase Edge Acyclicity Obstruction):
    In any directed graph `(edge, depth)` satisfying non-decreasing edge depth
    `∀ a b, edge a b → depth a ≤ depth b`, any strictly increasing edge `depth u < depth v`
    followed by an arbitrary-length directed walk `DirWalk edge v w` yields `depth u < depth w`
    and `w ≠ u`, ruling out any directed cycle `DirWalk edge v u`.
    (Note: equal-depth cycles `depth a = depth b` are excluded orthogonally by Python's
    iterative 3-color DFS in `aletheia/portfolio_dag.py`.) -/
theorem cs27_strict_depth_dag_acyclic_obstruction
    (edge : Nat → Nat → Prop) (depth : Nat → Int)
    (hmono : ∀ a b, edge a b → depth a ≤ depth b)
    (u v w : Nat) (_huv : edge u v) (hstrict : depth u < depth v)
    (hwalk : DirWalk edge v w) :
    depth u < depth w ∧ w ≠ u ∧ ¬ DirWalk edge v u := by
  have hle : depth v ≤ depth w := walk_depth_monotone edge depth hmono hwalk
  have hlt : depth u < depth w := Int.lt_of_lt_of_le hstrict hle
  refine ⟨hlt, ?_, ?_⟩
  · intro heq
    subst heq
    exact Int.lt_irrefl _ hlt
  · intro hcyc
    have hle_u : depth v ≤ depth u := walk_depth_monotone edge depth hmono hcyc
    exact (Int.not_le.mpr hstrict) hle_u

/-- Theorem 10 (CS-27 Symmetric GitHub+HF Portfolio Coverage Gate):
    Given GitHub coverage `gh_enum / gh_exp` (`gh_exp > 0`) and Hugging Face coverage
    `hf_enum / hf_exp` (`hf_exp > 0`) both meeting rational threshold `req_num / req_den`
    (`req_den > 0`), the symmetric platform average `(gh_cov + hf_cov) / 2` meets
    `req_num / req_den` in exact cleared-denominator integers, and strict shortfall on
    either platform forces strict shortfall in the symmetric average when the other ties. -/
theorem cs27_symmetric_coverage_denominator_exact
    (gh_enum gh_exp hf_enum hf_exp req_num req_den : Int)
    (hgh : 0 < gh_exp) (hhf : 0 < hf_exp) (hden : 0 < req_den) :
    ((req_num * gh_exp ≤ gh_enum * req_den ∧ req_num * hf_exp ≤ hf_enum * req_den) →
      2 * req_num * (gh_exp * hf_exp) ≤ (gh_enum * hf_exp + hf_enum * gh_exp) * req_den) ∧
    ((gh_enum * req_den < req_num * gh_exp ∧ hf_enum * req_den ≤ req_num * hf_exp) →
      (gh_enum * hf_exp + hf_enum * gh_exp) * req_den < 2 * req_num * (gh_exp * hf_exp)) := by
  constructor
  · intro ⟨h1, h2⟩
    have s1 : req_num * gh_exp * hf_exp ≤ gh_enum * req_den * hf_exp :=
      monotone_nonneg_mul _ _ hf_exp (Int.le_of_lt hhf) h1
    have s2 : req_num * hf_exp * gh_exp ≤ hf_enum * req_den * gh_exp :=
      monotone_nonneg_mul _ _ gh_exp (Int.le_of_lt hgh) h2
    have hden_pos : 0 < req_den := hden
    have _ := hden_pos
    have hrw1 : req_num * hf_exp * gh_exp = req_num * gh_exp * hf_exp := by
      rw [Int.mul_assoc, Int.mul_comm hf_exp gh_exp, ← Int.mul_assoc]
    have htwo : 2 * req_num * (gh_exp * hf_exp) = req_num * gh_exp * hf_exp + req_num * hf_exp * gh_exp := by
      rw [Int.two_mul req_num, Int.add_mul, hrw1, Int.mul_assoc req_num gh_exp hf_exp]
    have hsum : req_num * gh_exp * hf_exp + req_num * hf_exp * gh_exp ≤
        gh_enum * req_den * hf_exp + hf_enum * req_den * gh_exp := by omega
    have hrhs : (gh_enum * hf_exp + hf_enum * gh_exp) * req_den =
        gh_enum * req_den * hf_exp + hf_enum * req_den * gh_exp := by
      rw [Int.add_mul]
      have a1 : gh_enum * hf_exp * req_den = gh_enum * req_den * hf_exp := by
        rw [Int.mul_assoc, Int.mul_comm hf_exp req_den, ← Int.mul_assoc]
      have a2 : hf_enum * gh_exp * req_den = hf_enum * req_den * gh_exp := by
        rw [Int.mul_assoc, Int.mul_comm gh_exp req_den, ← Int.mul_assoc]
      rw [a1, a2]
    omega
  · intro ⟨h1, h2⟩
    have s1 : gh_enum * req_den * hf_exp < req_num * gh_exp * hf_exp :=
      monotone_pos_mul _ _ hf_exp hhf h1
    have s2 : hf_enum * req_den * gh_exp ≤ req_num * hf_exp * gh_exp :=
      monotone_nonneg_mul _ _ gh_exp (Int.le_of_lt hgh) h2
    have hrw1 : req_num * hf_exp * gh_exp = req_num * gh_exp * hf_exp := by
      rw [Int.mul_assoc, Int.mul_comm hf_exp gh_exp, ← Int.mul_assoc]
    have htwo : 2 * req_num * (gh_exp * hf_exp) = req_num * gh_exp * hf_exp + req_num * hf_exp * gh_exp := by
      rw [Int.two_mul req_num, Int.add_mul, hrw1, Int.mul_assoc req_num gh_exp hf_exp]
    have hlhs : (gh_enum * hf_exp + hf_enum * gh_exp) * req_den =
        gh_enum * req_den * hf_exp + hf_enum * req_den * gh_exp := by
      rw [Int.add_mul]
      have a1 : gh_enum * hf_exp * req_den = gh_enum * req_den * hf_exp := by
        rw [Int.mul_assoc, Int.mul_comm hf_exp req_den, ← Int.mul_assoc]
      have a2 : hf_enum * gh_exp * req_den = hf_enum * req_den * gh_exp := by
        rw [Int.mul_assoc, Int.mul_comm gh_exp req_den, ← Int.mul_assoc]
      rw [a1, a2]
    omega

/-- CS-28 Law-5 disposition lattice matching `aletheia/portal_interpose.py`. -/
inductive Law5Disposition where
  | candidateOnly
  | exactOperatorTransfer
  | structuralObstruction
  deriving DecidableEq

/-- Law-5 bridge promotion predicate: only an unnegated `exactOperatorTransfer`
    with an explicit resolved operator witness `hasOpWitness` (abstracting Python's
    `¬is_refuted ∧ (has_rel ∨ (has_term ∧ buzzHits < 2))` witness gate) promotes
    `verified_bridge = true`, regardless of Turn-0 hit count `hits` or `buzzHits`. -/
def law5VerifiedBridge
    (disp : Law5Disposition) (hits buzzHits : Int)
    (hasOpWitness hasNegatedPhrase : Bool) : Bool :=
  match disp with
  | .candidateOnly => false
  | .exactOperatorTransfer =>
      decide (0 ≤ hits ∧ 0 ≤ buzzHits) && hasOpWitness && !hasNegatedPhrase
  | .structuralObstruction => false

/-- Theorem 11 (CS-28 Law-5 Zero-Operator & Negated-Witness Bridge Obstruction):
    For any Turn-0 hit count `hits > 0` and buzzword count `buzzHits ≥ 0`, no claim
    lacking a valid non-negated operator witness (`hasOpWitness = false ∨ hasNegatedPhrase = true`,
    including buzzword-smuggled claims with `buzzHits ≥ 2` and no relation witness)
    or having `candidateOnly`/`structuralObstruction` disposition can promote `verified_bridge = true`. -/
theorem cs28_law5_zero_operator_obstruction
    (disp : Law5Disposition) (hits buzzHits : Int)
    (hasOpWitness hasNegatedPhrase : Bool)
    (hhits : 0 < hits) (hbuzz : 0 ≤ buzzHits) :
    (law5VerifiedBridge disp hits buzzHits hasOpWitness hasNegatedPhrase = true ↔
      (disp = .exactOperatorTransfer ∧ hasOpWitness = true ∧ hasNegatedPhrase = false)) := by
  have _ := hhits
  have _ := hbuzz
  cases disp <;> cases hasOpWitness <;> cases hasNegatedPhrase <;>
    simp [law5VerifiedBridge, Int.le_of_lt hhits, hbuzz]

/-- Theorem 12 (CS-28 Non-Negativity & Monotonicity of Exact Cross-Pillar Score):
    For non-negative matched primitive count `0 ≤ num` and positive total primitive count
    `total > 0`, both `num / total` and `(num + delta) / total` are non-negative, and adding
    a new matched primitive family (`delta > 0`) strictly increases the rational score. -/
theorem cs28_cross_pillar_score_monotone
    (num delta total : Int)
    (hnum : 0 ≤ num) (htot : 0 < total) (hdelta : 0 < delta) :
    0 ≤ num * total ∧ 0 < (num + delta) * total ∧ num * total < (num + delta) * total := by
  have hnn : 0 ≤ num * total := Int.mul_nonneg hnum (Int.le_of_lt htot)
  have hpos : 0 < delta * total := Int.mul_pos hdelta htot
  rw [Int.add_mul]
  exact ⟨hnn, by omega, by omega⟩

#print axioms ThinCoordInterpose.thin_coord_crossover_iff
#print axioms ThinCoordInterpose.thin_coord_equal_crossover_no_strict_dominance
#print axioms ThinCoordInterpose.thin_coord_no_offload_when_summary_ge_payload
#print axioms ThinCoordInterpose.thin_coord_payload_monotone_dominance
#print axioms ThinCoordInterpose.thin_coord_turn_monotone_dominance
#print axioms ThinCoordInterpose.thin_coord_compaction_amplification_iff
#print axioms ThinCoordInterpose.thin_coord_compaction_amplification_strict_gain
#print axioms ThinCoordInterpose.thin_coord_40line_rule_concrete_witness
#print axioms ThinCoordInterpose.cs27_strict_depth_dag_acyclic_obstruction
#print axioms ThinCoordInterpose.cs27_symmetric_coverage_denominator_exact
#print axioms ThinCoordInterpose.cs28_law5_zero_operator_obstruction
#print axioms ThinCoordInterpose.cs28_cross_pillar_score_monotone

end ThinCoordInterpose
