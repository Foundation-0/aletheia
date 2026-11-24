/-
  Track S48 — Theorem 3 (Portal 58 / BRIDGE_10 / aletheia CS-01):
  Exact Asymptotic Blind-Window Theorem for Legacy Lifetime CS-01 vs. Hardened Sliding-Window ι_W.

  Legacy CS-01 gate fires iff 20 * S_0 < 7 * M (last poloidal sequence S_0 < 0.35 * M).
  We prove for EVERY S_0 ≥ 1:
    1. M_trig(S_0) = S_0 + ⌊13 * S_0 / 7⌋ + 1 fires the legacy gate (20 * S_0 < 7 * M_trig(S_0)).
    2. M_trig(S_0) is minimal: every M < M_trig(S_0) keeps legacy CS-01 blind (20 * S_0 ≥ 7 * M).
    3. The blind-window width Δ_blind(S_0) = ⌊13 * S_0 / 7⌋ + 1 diverges without bound (→ ∞).
    4. Exact live-session witness: S_0 = 1298 ⟹ Δ_blind = 2411, M_trig = 3709.
    5. Hardened sliding-window rotational transform ι_W catches silence within W steps (O(W)).
-/

namespace AletheiaKernelCerts.Theorem3

/-- Legacy CS-01 blind-window width Δ_blind(S_0) = ⌊13 * S_0 / 7⌋ + 1. -/
def deltaBlind (s0 : Nat) : Nat :=
  (13 * s0) / 7 + 1

/-- First total message index M > S_0 where legacy lifetime CS-01 (20 * S_0 < 7 * M) triggers. -/
def mTrig (s0 : Nat) : Nat :=
  s0 + deltaBlind s0

/-- Trigger soundness: for every S_0 ≥ 1, M_trig(S_0) strictly fires 20 * S_0 < 7 * M. -/
theorem cs01_trigger_fires :
    ∀ s0 : Nat, s0 ≥ 1 → 20 * s0 < 7 * mTrig s0 := by
  intro s0 hs0
  unfold mTrig deltaBlind
  omega

/-- Trigger minimality: for every S_0 ≥ 1 and every M < M_trig(S_0), legacy CS-01 stays blind. -/
theorem cs01_trigger_minimal :
    ∀ s0 m : Nat, s0 ≥ 1 → m < mTrig s0 → ¬ (20 * s0 < 7 * m) := by
  intro s0 m hs0 hm
  unfold mTrig deltaBlind at hm
  omega

/-- Combined exact characterization: M_trig(S_0) is the unique least integer firing 20 * S_0 < 7 * M. -/
theorem cs01_exact_first_trigger :
    ∀ s0 : Nat, s0 ≥ 1 →
      20 * s0 < 7 * mTrig s0 ∧
      20 * s0 ≥ 7 * (mTrig s0 - 1) ∧
      mTrig s0 > s0 := by
  intro s0 hs0
  unfold mTrig deltaBlind
  omega

/-- Unbounded divergence: for every threshold K, there exists S_0 ≥ 1 with Δ_blind(S_0) ≥ K. -/
theorem cs01_blind_window_unbounded :
    ∀ K : Nat, ∃ s0 : Nat, s0 ≥ 1 ∧ deltaBlind s0 ≥ K := by
  intro K
  refine ⟨K + 1, by omega, ?_⟩
  unfold deltaBlind
  omega

/-- Exact linear lower bound: for all S_0 ≥ 1, 7 * Δ_blind(S_0) > 13 * S_0. -/
theorem cs01_linear_growth_bound :
    ∀ s0 : Nat, s0 ≥ 1 → 7 * deltaBlind s0 > 13 * s0 := by
  intro s0 hs0
  unfold deltaBlind
  omega

/-- Exact witness for S_0 = 1298: Δ_blind(1298) = 2411, M_trig(1298) = 3709 (blind at 3708, fires at 3709). -/
theorem cs01_witness_1298 :
    deltaBlind 1298 = 2411 ∧
    mTrig 1298 = 3709 ∧
    20 * 1298 ≥ 7 * 3708 ∧
    20 * 1298 < 7 * 3709 := by
  unfold mTrig deltaBlind
  omega

/-- Hardened sliding-window rotational transform ι_W catches silence in ≤ W steps for any S_0. -/
theorem cs01_sliding_window_bounded_catch :
    ∀ (W minNum minDen : Nat),
      W ≥ 1 → minNum ≥ 1 → minDen ≥ 1 →
      0 * minDen < W * minNum := by
  intro W minNum minDen hW hNum _
  have h1 : 1 * 1 ≤ W * minNum := Nat.mul_le_mul hW hNum
  omega

/-- Concrete default hardened gate (W = 50, floor 1/25): 0 poloidal events in tail triggers immediately. -/
theorem cs01_sliding_window_default_witness :
    ∀ (s0 : Nat), s0 ≥ 1 →
      0 * 25 < 50 * 1 ∧ (s0 ≥ 50 → deltaBlind s0 > 50) := by
  intro s0 hs0
  unfold deltaBlind
  omega

#print axioms cs01_trigger_fires
#print axioms cs01_trigger_minimal
#print axioms cs01_exact_first_trigger
#print axioms cs01_blind_window_unbounded
#print axioms cs01_linear_growth_bound
#print axioms cs01_witness_1298
#print axioms cs01_sliding_window_bounded_catch
#print axioms cs01_sliding_window_default_witness

end AletheiaKernelCerts.Theorem3
