/-
Track S168 (`EXP-Q56a`): Pure-Init Lean 4.36.0 Formalization of the Aletheia
Velocity Engine Acceleration & Exact-Losslessness Laws.

Scope note: These 14 public theorems certify abstract cleared-denominator integer
arithmetic and finite `List Bool` mathematical laws over explicit physical domain
hypotheses (`pd > 0`, `Tmono > 0`, `0 ≤ T1`, `0 ≤ T2`, `0 ≤ pn ≤ pd`). They are
mathematical specifications uncoupled from Python runtime internals; concrete runtime
parity is separately verified by the empirical A/B harness and R5 test suite.

Zero external imports (pure `Init`), zero `sorry`/`admit`/`axiom`/`unsafe`/`native_decide`,
and zero `Classical.choice`. All 14 public theorems depend strictly on Lean kernel
primitives (`propext`, `Quot.sound`, or zero axioms).
-/

namespace VelocityBounds

private theorem mul_le_mul_of_nonneg_left_int (a b c : Int) (ha : 0 ≤ a) (hbc : b ≤ c) :
    a * b ≤ a * c := by
  have h : 0 ≤ a * (c - b) := Int.mul_nonneg ha (by omega)
  rw [Int.mul_sub] at h
  omega

private theorem mul_le_mul_of_nonneg_right_int (a b c : Int) (hc : 0 ≤ c) (hab : a ≤ b) :
    a * c ≤ b * c := by
  have h : 0 ≤ (b - a) * c := Int.mul_nonneg (by omega) hc
  rw [Int.sub_mul] at h
  omega

private theorem mul_lt_mul_of_pos_right_int (a b c : Int) (hc : 0 < c) (hab : a < b) :
    a * c < b * c := by
  have h : 0 < (b - a) * c := Int.mul_pos (by omega) hc
  rw [Int.sub_mul] at h
  omega

/- =========================================================================
   GROUP A: Two-Stage Kill-Gate Expected-Time Acceleration (Exact Rationals)
   ========================================================================= -/

/-- Theorem 1 (Two-Stage Kill-Gate Exact Acceleration Threshold):
    Over the physical domain `0 ≤ T1`, `0 < Tmono`, `0 < pd`, and `0 ≤ pn ≤ pd`
    (representing Stage-1 latency `T1`, monolithic latency `Tmono`, and rational
    Stage-1 survival probability `p_surv = pn / pd ∈ [0, 1]`), when `T2 = Tmono`,
    the cleared-denominator expected two-stage time `T1 * pd + pn * Tmono`
    strictly beats `Tmono * pd` iff `pn * Tmono < pd * (Tmono - T1)`
    (equivalently `p_surv < 1 - T1 / Tmono` since `pd > 0` and `Tmono > 0`). -/
theorem two_stage_expected_time_strict_accel_iff
    (T1 Tmono pn pd : Int)
    (hT1 : 0 ≤ T1)
    (hTmono : 0 < Tmono)
    (hpn0 : 0 ≤ pn)
    (hpnle : pn ≤ pd)
    (hpd : 0 < pd) :
    (0 < Tmono * pd ∧ 0 ≤ T1 * pd + pn * Tmono) ∧
    ((T1 * pd + pn * Tmono < Tmono * pd) ↔ (pn * Tmono < pd * (Tmono - T1))) := by
  have hdom1 : 0 < Tmono * pd := Int.mul_pos hTmono hpd
  have hdom2 : 0 ≤ T1 * pd := Int.mul_nonneg hT1 (by omega)
  have hdom3 : 0 ≤ pn * Tmono := Int.mul_nonneg hpn0 (by omega)
  have hdom4 : pn * Tmono ≤ pd * Tmono := mul_le_mul_of_nonneg_right_int pn pd Tmono (by omega) hpnle
  have hsub : pd * (Tmono - T1) = Tmono * pd - T1 * pd := by
    rw [Int.mul_sub, Int.mul_comm pd Tmono, Int.mul_comm pd T1]
  refine ⟨⟨hdom1, by omega⟩, ?_⟩
  rw [hsub]
  constructor
  · intro h
    omega
  · intro h
    omega

/-- Theorem 2 (Unconditional General-`T2` Acceleration Equivalence & Monotone Sufficiency):
    Over the physical domain `0 ≤ T1`, `0 ≤ T2`, `0 < Tmono`, `0 < pd`, and `0 ≤ pn ≤ pd`
    (WITHOUT assuming `hprob` or `T2 ≤ Tmono` globally), proves:
      1. Non-negativity `0 ≤ T1 * pd + pn * T2`,
      2. The genuinely unconditional general-`T2` cleared-denominator equivalence
         `(T1 * pd + pn * T2 < Tmono * pd) ↔ (pn * T2 < pd * (Tmono - T1))`
         (holding both when acceleration succeeds and when it fails), and
      3. Sufficiency whenever `T2 ≤ Tmono` and the monolithic threshold
         `pn * Tmono < pd * (Tmono - T1)` holds. -/
theorem two_stage_general_T2_le_Tmono_accel
    (T1 T2 Tmono pn pd : Int)
    (hT1 : 0 ≤ T1)
    (hT2_nonneg : 0 ≤ T2)
    (hTmono : 0 < Tmono)
    (hpn0 : 0 ≤ pn)
    (hpnle : pn ≤ pd)
    (hpd : 0 < pd) :
    0 ≤ T1 * pd + pn * T2 ∧
    ((T1 * pd + pn * T2 < Tmono * pd) ↔ (pn * T2 < pd * (Tmono - T1))) ∧
    (T2 ≤ Tmono → pn * Tmono < pd * (Tmono - T1) →
      T1 * pd + pn * T2 < Tmono * pd ∧ pn * T2 < pd * (Tmono - T1)) := by
  have h3 : 0 ≤ T1 * pd := Int.mul_nonneg hT1 (by omega)
  have h4 : 0 ≤ pn * T2 := Int.mul_nonneg hpn0 hT2_nonneg
  have hsub : pd * (Tmono - T1) = Tmono * pd - T1 * pd := by
    rw [Int.mul_sub, Int.mul_comm pd Tmono, Int.mul_comm pd T1]
  have hiff : (T1 * pd + pn * T2 < Tmono * pd) ↔ (pn * T2 < pd * (Tmono - T1)) := by
    rw [hsub]
    constructor
    · intro h
      omega
    · intro h
      omega
  refine ⟨by omega, hiff, ?_⟩
  intro hT2 hprob
  have h1 : T1 * pd + pn * Tmono < Tmono * pd :=
    (two_stage_expected_time_strict_accel_iff T1 Tmono pn pd hT1 hTmono hpn0 hpnle hpd).2.2 hprob
  have h2 : pn * T2 ≤ pn * Tmono := mul_le_mul_of_nonneg_left_int pn T2 Tmono hpn0 hT2
  exact ⟨by omega, hiff.1 (by omega)⟩

/-- Theorem 3 (Exact Cleared-Denominator Expected Savings Identity):
    For `T2 = Tmono`, the cleared-denominator expected latency savings
    `Tmono * pd - (T1 * pd + pn * Tmono)` equals `(pd - pn) * Tmono - T1 * pd`. -/
theorem two_stage_expected_savings_exact
    (T1 Tmono pn pd : Int) :
    Tmono * pd - (T1 * pd + pn * Tmono) = (pd - pn) * Tmono - T1 * pd := by
  have h1 : (pd - pn) * Tmono = pd * Tmono - pn * Tmono := Int.sub_mul pd pn Tmono
  have h2 : pd * Tmono = Tmono * pd := Int.mul_comm pd Tmono
  rw [h1, h2]
  omega

/-- Theorem 4 (Monotonicity in Survival Probability):
    For `0 ≤ T2` and `pn1 ≤ pn2`, tighter Stage-1 kill-gates (`pn1 ≤ pn2`)
    never increase two-stage expected latency. -/
theorem two_stage_monotone_in_survival_prob
    (T1 T2 pn1 pn2 pd : Int)
    (hT2 : 0 ≤ T2)
    (hle : pn1 ≤ pn2) :
    T1 * pd + pn1 * T2 ≤ T1 * pd + pn2 * T2 := by
  have hm : pn1 * T2 ≤ pn2 * T2 := mul_le_mul_of_nonneg_right_int pn1 pn2 T2 hT2 hle
  omega

/-- Theorem 5 (No-Gain Boundary at Unit Survival `pn = pd`):
    If Stage-1 filters nothing (`pn = pd`, `pd > 0`) and incurs positive overhead
    `T1 > 0` with `T2 = Tmono`, two-stage expected time strictly exceeds `Tmono`. -/
theorem two_stage_no_gain_at_unit_survival
    (T1 Tmono pd : Int)
    (hT1 : 0 < T1)
    (hpd : 0 < pd) :
    Tmono * pd < T1 * pd + pd * Tmono := by
  have hpos : 0 < T1 * pd := Int.mul_pos hT1 hpd
  have hcomm : pd * Tmono = Tmono * pd := Int.mul_comm pd Tmono
  omega

/- =========================================================================
   GROUP B: Lossless Pass-2 Mutant Deduplication & Fail-Fast Equivalence
   ========================================================================= -/

/-- Theorem 6 (Boolean-Predicate Pass-2 Deduplication Union Identity):
    For any decidable killed-set membership predicates `k1, k2 : α → Bool`,
    `K_1 ∪ K_2 = K_1 ∪ (K_2 \ K_1)` holds pointwise without `Classical.choice`. -/
theorem pass2_dedup_bool_union_exact
    {α : Type} (k1 k2 : α → Bool) (x : α) :
    (k1 x || k2 x) = (k1 x || (k2 x && !k1 x)) := by
  cases k1 x <;> cases k2 x <;> rfl

/-- Executable Pass-2 deduplication filter skipping signatures already in `k1`. -/
def dedupPass2 {α : Type} [BEq α] (k1 m2 : List α) : List α :=
  m2.filter (fun s => !(k1.contains s))

/-- Theorem 7 (Executable List Pass-2 Deduplication Set Equivalence):
    For any `[BEq α] [LawfulBEq α]` and Pass-1 killed list `k1` and Pass-2 list `m2`,
    an element belongs to `k1 ++ m2` iff it belongs to `k1 ++ dedupPass2 k1 m2`. -/
theorem pass2_dedup_list_mem_exact
    {α : Type} [BEq α] [LawfulBEq α] (k1 m2 : List α) (x : α) :
    x ∈ (k1 ++ m2) ↔ x ∈ (k1 ++ dedupPass2 k1 m2) := by
  unfold dedupPass2
  simp only [List.mem_append, List.mem_filter, Bool.not_eq_true', List.contains_eq_mem,
    decide_eq_false_iff_not]
  constructor
  · intro h
    cases h with
    | inl h1 => exact Or.inl h1
    | inr h2 =>
      cases hdec : decide (x ∈ k1) with
      | true =>
        exact Or.inl (of_decide_eq_true hdec)
      | false =>
        exact Or.inr ⟨h2, of_decide_eq_false hdec⟩
  · intro h
    cases h with
    | inl h1 => exact Or.inl h1
    | inr h2 => exact Or.inr h2.1

/-- Theorem 8 (Exact Pass-2 Subprocess Partition Conservation):
    Every Pass-2 site is either skipped (reused from `k1`) or executed in `dedupPass2`,
    so `skipped + executed = m2.length` and `executed ≤ m2.length`. -/
theorem pass2_dedup_eval_count_exact
    {α : Type} [BEq α] (k1 m2 : List α) :
    (m2.filter (fun s => k1.contains s)).length + (dedupPass2 k1 m2).length = m2.length ∧
    (dedupPass2 k1 m2).length ≤ m2.length := by
  unfold dedupPass2
  have hsum : (m2.filter (fun s => k1.contains s)).length +
      (m2.filter (fun s => !(k1.contains s))).length = m2.length := by
    induction m2 with
    | nil => rfl
    | cons a t ih =>
      simp only [List.filter_cons]
      cases h : k1.contains a with
      | true =>
        simp only [Bool.not_true, ↓reduceIte, Bool.false_eq_true, List.length_cons]
        omega
      | false =>
        simp only [Bool.not_false, ↓reduceIte, Bool.false_eq_true, List.length_cons]
        omega
  exact ⟨hsum, by omega⟩

/-- Theorem 9 (Zero Pass-2 Re-Execution When `m2 ⊆ k1`):
    When every Pass-2 mutant signature was already killed in Pass 1,
    deduplicated Pass 2 performs exactly `0` redundant subprocess executions. -/
theorem pass2_dedup_zero_evals_when_subset
    {α : Type} [BEq α] (k1 m2 : List α)
    (hsub : ∀ s, s ∈ m2 → k1.contains s = true) :
    (dedupPass2 k1 m2).length = 0 := by
  unfold dedupPass2
  induction m2 with
  | nil => rfl
  | cons a t ih =>
    have ha : k1.contains a = true := hsub a (List.Mem.head t)
    have ht : ∀ s, s ∈ t → k1.contains s = true := fun s hs => hsub s (List.Mem.tail a hs)
    simp only [List.filter_cons, ha, Bool.not_true]
    exact ih ht

/-- Full-suite mutant kill predicate (`true` iff any test returns `false`). -/
def fullSuiteKilled (ts : List Bool) : Bool :=
  match ts with
  | [] => false
  | r :: rest => (!r) || fullSuiteKilled rest

/-- Fail-fast mutant kill predicate: halts immediately on the first failing (`false`) test. -/
def failFastKilled (ts : List Bool) : Bool :=
  match ts with
  | [] => false
  | false :: _ => true
  | true :: rest => failFastKilled rest

/-- Exact number of test methods executed under `--failfast`. -/
def failFastSteps (ts : List Bool) : Nat :=
  match ts with
  | [] => 0
  | false :: _ => 1
  | true :: rest => 1 + failFastSteps rest

private theorem failfast_strict_lt_of_early_fail (pre suf : List Bool) (hsuf : suf ≠ []) :
    failFastSteps (pre ++ false :: suf) < (pre ++ false :: suf).length := by
  induction pre with
  | nil =>
    cases suf with
    | nil => exact absurd rfl hsuf
    | cons s rest =>
      simp only [List.nil_append, failFastSteps, List.length_cons]
      omega
  | cons b rest ih =>
    cases b with
    | false =>
      simp only [List.cons_append, failFastSteps, List.length_cons, List.length_append]
      omega
    | true =>
      simp only [List.cons_append, failFastSteps, List.length_cons] at ih ⊢
      omega

/-- Theorem 10 (Lossless `--failfast` Kill Equivalence, Upper Bound, & Strict Early-Fail Savings):
    For every finite test-result list `ts : List Bool`:
      1. `failFastKilled ts = fullSuiteKilled ts` (100% lossless verdict equivalence),
      2. `failFastSteps ts ≤ ts.length` (never executes more tests than full suite), and
      3. Whenever an early (non-final) test fails (`ts = pre ++ false :: suf` with `suf ≠ []`),
         `failFastSteps ts < ts.length` strictly. -/
theorem failfast_kill_equivalence_and_bound (ts : List Bool) :
    failFastKilled ts = fullSuiteKilled ts ∧
    failFastSteps ts ≤ ts.length ∧
    (∀ pre suf : List Bool, suf ≠ [] → ts = pre ++ false :: suf → failFastSteps ts < ts.length) := by
  have hmain : failFastKilled ts = fullSuiteKilled ts ∧ failFastSteps ts ≤ ts.length := by
    induction ts with
    | nil => exact ⟨rfl, Nat.le_refl 0⟩
    | cons r rest ih =>
      cases r with
      | false =>
        simp only [failFastKilled, fullSuiteKilled, failFastSteps, Bool.not_false,
          Bool.true_or, List.length_cons]
        exact ⟨trivial, by omega⟩
      | true =>
        simp only [failFastKilled, fullSuiteKilled, failFastSteps, Bool.not_true,
          Bool.false_or, List.length_cons]
        exact ⟨ih.1, by omega⟩
  refine ⟨hmain.1, hmain.2, ?_⟩
  intro pre suf hsuf heq
  rw [heq]
  exact failfast_strict_lt_of_early_fail pre suf hsuf

/- =========================================================================
   GROUP C: Shared `trust_core` N-Track Amortized Boilerplate & Audit Savings
   ========================================================================= -/

/-- Theorem 11 (Shared `trust_core` N-Track Break-Even Equivalence):
    Building one pre-certified `trust_core` of cost `C_core` with per-track wiring
    cost `b_drop` strictly beats re-implementing `B_dup` boilerplate across `N` tracks
    iff `C_core < N * (B_dup - b_drop)`. -/
theorem trust_core_amortized_savings_iff
    (N C_core B_dup b_drop : Int) :
    (C_core + N * b_drop < N * B_dup) ↔ (C_core < N * (B_dup - b_drop)) := by
  have h : N * (B_dup - b_drop) = N * B_dup - N * b_drop := Int.mul_sub N B_dup b_drop
  rw [h]
  constructor
  · intro hlt
    omega
  · intro hlt
    omega

/-- Theorem 12 (Strict Monotone Amortization Across Additional Tracks):
    When `b_drop < B_dup` and break-even holds at `N` tracks, adding `k > 0` more tracks
    strictly increases total net savings (`(N + k) * (B_dup - b_drop) - C_core`). -/
theorem trust_core_monotone_in_tracks
    (N k C_core B_dup b_drop : Int)
    (hk : 0 < k)
    (hdrop : b_drop < B_dup)
    (hbe : C_core < N * (B_dup - b_drop)) :
    (N * (B_dup - b_drop) - C_core) < ((N + k) * (B_dup - b_drop) - C_core) ∧
    C_core + (N + k) * b_drop < (N + k) * B_dup := by
  have hpos : 0 < k * (B_dup - b_drop) := Int.mul_pos hk (by omega)
  have hexp : (N + k) * (B_dup - b_drop) = N * (B_dup - b_drop) + k * (B_dup - b_drop) :=
    Int.add_mul N k (B_dup - b_drop)
  have hbe2 : C_core < (N + k) * (B_dup - b_drop) := by omega
  have htot : C_core + (N + k) * b_drop < (N + k) * B_dup :=
    (trust_core_amortized_savings_iff (N + k) C_core B_dup b_drop).2 hbe2
  exact ⟨by omega, htot⟩

/-- Theorem 13 (Shift-Left Preflight Audit-Round Savings Equivalence):
    Running a preflight gate of cost `P` that reduces external audit rounds from
    `R_mono` to `R_pre` (at cost `A` per round) strictly saves audit time iff
    `P < (R_mono - R_pre) * A`. -/
theorem preflight_audit_round_savings_iff
    (P A R_mono R_pre : Int) :
    (P + R_pre * A < R_mono * A) ↔ (P < (R_mono - R_pre) * A) := by
  have h : (R_mono - R_pre) * A = R_mono * A - R_pre * A := Int.sub_mul R_mono R_pre A
  rw [h]
  constructor
  · intro hlt
    omega
  · intro hlt
    omega

/- =========================================================================
   GROUP D: Concrete Exact-Integer Witnesses (Zero Axioms via `decide`)
   ========================================================================= -/

/-- Theorem 14 (Concrete Wave-22 Velocity Engine Witnesses, Zero Axioms):
    Certifies exact integer witnesses for Wave-22 model inputs and measured `trust_core.py` LOC:
      (a) Two-stage kill gate (`T1=10m, Tmono=180m, p_surv=1/3`: `210 < 540`) and
          dual-accelerated Stage-2 (`T1=10m, T2=60m, Tmono=180m, p_surv=1/2`, cleared-ratio
          bound `(Tmono - T1)/T2 = 17/6 > 1` so every `p_surv ∈ [0, 1]` accelerates: `80 < 360`),
      (b) Shared `trust_core` illustrative minimal model (`C_core=540, B_dup=420, b_drop=20`:
          break-even at `N=2`, saving `1860` LOC at `N=6`) and exact measured hardened kernel
          (`C_core=1436` non-empty LOC of `trust_core.py`, `B_dup=420, b_drop=20`: tight break-even
          at `N=4` with `N=3` non-breakeven, saving `964` LOC at `N=6`),
      (c) Shift-left `preflight` (`P=2s, A=900s, 3 -> 1` rounds: `902 < 2700`),
      (d) Concrete `--failfast` early-kill witness (`[true, false, true, true, true]`:
          `failFastKilled = fullSuiteKilled = true` in `2 < 5` steps). -/
theorem velocity_engine_concrete_witnesses :
    (10 * 3 + 1 * 180 < 180 * 3) ∧
    (10 * 2 + 1 * 60 < 180 * 2) ∧
    (540 + 2 * 20 < 2 * 420) ∧
    (6 * 420 - (540 + 6 * 20) = 1860) ∧
    (3 * 420 ≤ 1436 + 3 * 20) ∧
    (1436 + 4 * 20 < 4 * 420) ∧
    (6 * 420 - (1436 + 6 * 20) = 964) ∧
    (2 + 1 * 900 < 3 * 900) ∧
    (failFastKilled [true, false, true, true, true] = fullSuiteKilled [true, false, true, true, true]) ∧
    (failFastSteps [true, false, true, true, true] = 2) ∧
    (failFastSteps [true, false, true, true, true] < [true, false, true, true, true].length) := by
  decide

end VelocityBounds
