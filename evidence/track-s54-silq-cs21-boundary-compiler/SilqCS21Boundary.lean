/-
  Track S54 (Portal 54): Executable Silq (!T / const / qfree / lifted / mfree / forget)
  x DeepMind CS-21 Classical-Control & Landauer Boundary-Cost Compiler.

  Zero external imports, zero sorry, zero native_decide, zero custom axioms.
  Verified directly under Lean 4.36.0 kernel elaboration and #print axioms.
-/

namespace SilqCS21Boundary

/-! ### Theorem 1: Silq Static Effect & Boundary Legality Judgment -/

/-- Silq function effect annotation hierarchy. -/
inductive SilqEffect where
  | qfree
  | lifted
  | mfree
  | general
  deriving DecidableEq, Repr

/-- Core quantum-classical boundary IR operation kinds. -/
inductive BoundaryOp where
  | xGate
  | cnotGate
  | ccxGate
  | liftedAnd
  | forgetAuto
  | hGate
  | sGate
  | tGate
  | measureOp
  | offloadClassical
  deriving DecidableEq, Repr

/-- Exact static admissibility judgment matching silq_cs21_compiler_oracle.py. -/
def opAllowed (eff : SilqEffect) (op : BoundaryOp) : Bool :=
  match eff, op with
  | .qfree, .xGate => true
  | .qfree, .cnotGate => true
  | .qfree, .ccxGate => true
  | .qfree, .liftedAnd => true
  | .qfree, .forgetAuto => true
  | .qfree, _ => false
  | .lifted, .xGate => true
  | .lifted, .cnotGate => true
  | .lifted, .ccxGate => true
  | .lifted, .liftedAnd => true
  | .lifted, .forgetAuto => true
  | .lifted, _ => false
  | .mfree, .measureOp => false
  | .mfree, .offloadClassical => false
  | .mfree, _ => true
  | .general, _ => true

/-- Universal Silq effect containment theorem: qfree and lifted reject superposition,
    phase, measurement, and classical offloading; mfree rejects measurement and offloading. -/
theorem silq_effect_boundary_sound :
    (∀ op : BoundaryOp, opAllowed .qfree op = true → opAllowed .mfree op = true) ∧
    (∀ op : BoundaryOp, opAllowed .lifted op = true → opAllowed .qfree op = true) ∧
    (∀ op : BoundaryOp, opAllowed .mfree op = true → opAllowed .general op = true) ∧
    opAllowed .qfree .hGate = false ∧
    opAllowed .qfree .tGate = false ∧
    opAllowed .qfree .measureOp = false ∧
    opAllowed .mfree .measureOp = false ∧
    opAllowed .mfree .offloadClassical = false := by
  refine ⟨?_, ?_, ?_, rfl, rfl, rfl, rfl, rfl⟩
  · intro op h; cases op <;> simp [opAllowed] at h ⊢
  · intro op h; cases op <;> simp [opAllowed] at h ⊢
  · intro op _; cases op <;> rfl

/-! ### Theorem 2 & 3: CS-21 Classical-Control Offloading Net-Regression (4x -> 600/401) -/

/-- Exact full boundary cost scaled by 10: 10 * (1 * T + (1/10) * C + (1/2) * E). -/
def scaledBoundaryCost10 (tGates ctrlOps erasedBits : Nat) : Nat :=
  10 * tGates + ctrlOps + 5 * erasedBits

/-- Exact hidden offloaded (classical control + Landauer) cost scaled by 10. -/
def scaledHiddenCost10 (ctrlOps erasedBits : Nat) : Nat :=
  ctrlOps + 5 * erasedBits

/-- Universal parametric CS-21 net-regression theorem over arbitrary natural resource counts. -/
theorem cs21_parametric_net_regression :
    ∀ (tA tB cA cB eA eB : Nat),
      tB < tA →
      scaledHiddenCost10 cB eB > scaledHiddenCost10 cA eA + 10 * (tA - tB) →
      scaledBoundaryCost10 tB cB eB > scaledBoundaryCost10 tA cA eA := by
  intro tA tB cA cB eA eB hT hHide
  unfold scaledBoundaryCost10 scaledHiddenCost10 at *
  omega

/-- Exact CS-21 4x T-gate mirage witness: 400 -> 100 T-gates hides 5/6 boundary cost,
    inflating full cost to 600/401 > 1, while genuine qfree speedup drops full cost to 102. -/
theorem cs21_4x_mirage_600_over_401 :
    400 = 4 * 100 ∧
    scaledBoundaryCost10 400 10 0 = 4010 ∧
    scaledBoundaryCost10 100 4000 200 = 6000 ∧
    scaledBoundaryCost10 100 20 0 = 1020 ∧
    6 * scaledHiddenCost10 4000 200 = 5 * scaledBoundaryCost10 100 4000 200 ∧
    scaledBoundaryCost10 100 4000 200 * 401 = 600 * scaledBoundaryCost10 400 10 0 ∧
    scaledBoundaryCost10 100 4000 200 > scaledBoundaryCost10 400 10 0 ∧
    scaledBoundaryCost10 100 20 0 < scaledBoundaryCost10 400 10 0 := by
  unfold scaledBoundaryCost10 scaledHiddenCost10
  omega

/-! ### Theorem 4 & 5: Landauer Bracket [19/16, 6/5] & qfree-vs-measure Non-Commutativity -/

/-- Exact integer entropy-power product 2^(N * H(X|Y)) = ∏_y |f⁻¹(y)|^(|f⁻¹(y)|). -/
def landauerPowerProduct {nIn nOut : Nat} (f : Fin nIn → Fin nOut) : Nat :=
  (List.finRange nOut).foldl
    (fun acc y =>
      let cnt := (List.finRange nIn).countP (fun x => f x == y)
      acc * (cnt ^ cnt))
    1

/-- 2-input classical AND gate on Fin 4 → Fin 2. -/
def andGate (x : Fin 4) : Fin 2 :=
  if x.val == 3 then ⟨1, by decide⟩ else ⟨0, by decide⟩

/-- 1-bit irreversible constant reset on Fin 2 → Fin 2. -/
def eraseGate (_ : Fin 2) : Fin 2 :=
  ⟨0, by decide⟩

/-- 3-bit reversible Toffoli (CCX) bijection on Fin 8 → Fin 8. -/
def toffoliGate (x : Fin 8) : Fin 8 :=
  if x.val == 6 then ⟨7, by decide⟩
  else if x.val == 7 then ⟨6, by decide⟩
  else x

/-- Exact Landauer power-product bracket 19/16 < H(X|Y) < 6/5 for irreversible AND,
    contrasted with reversible Toffoli (P = 1, 0 bits) and 1-bit erase (P = 4, 1 bit). -/
theorem landauer_and_bracket_and_toffoli_zero :
    landauerPowerProduct andGate = 27 ∧
    2 ^ 19 < (landauerPowerProduct andGate) ^ 4 ∧
    (landauerPowerProduct andGate) ^ 5 < 2 ^ 24 ∧
    (∀ x : Fin 8, toffoliGate (toffoliGate x) = x) ∧
    landauerPowerProduct toffoliGate = 1 ∧
    landauerPowerProduct eraseGate = 4 := by
  decide

/-- Full lower-bound boundary cost scaled by 160 (exact integer for w_T=1, w_ctrl=1/10,
    w_L=1/2, H_AND_lo=19/16): 160*T + 16*C + 95*N_and + 80*N_reset. -/
def scaledCostLo160 (tGates ctrlOps nAnd nReset : Nat) : Nat :=
  160 * tGates + 16 * ctrlOps + 95 * nAnd + 80 * nReset

/-- Full upper-bound boundary cost scaled by 10 (exact integer for H_AND_hi=6/5):
    10*T + C + 6*N_and + 5*N_reset. -/
def scaledCostHi10 (tGates ctrlOps nAnd nReset : Nat) : Nat :=
  10 * tGates + ctrlOps + 6 * nAnd + 5 * nReset

/-- Non-commutativity of qfree automatic uncomputation vs projective measurement on a 16-AND
    oracle pipeline: Order 1 (uncompute then measure: T=224, C=10, E=0 -> cost=225) strictly beats
    Order 2 (measure/offload before uncompute: T=56 = 224/4, C=2000, 16 AND + 16 resets ->
    cost in [547/2, 1368/5] = [273.5, 273.6]) even at the strict Landauer lower bound 19/16. -/
theorem noncommutativity_qfree_vs_measure_16and :
    224 = 4 * 56 ∧
    scaledCostLo160 224 10 0 0 = 36000 ∧
    scaledCostLo160 56 2000 16 16 = 43760 ∧
    scaledCostHi10 224 10 0 0 = 2250 ∧
    scaledCostHi10 56 2000 16 16 = 2736 ∧
    scaledCostLo160 56 2000 16 16 > scaledCostLo160 224 10 0 0 ∧
    scaledCostHi10 56 2000 16 16 > scaledCostHi10 224 10 0 0 := by
  unfold scaledCostLo160 scaledCostHi10
  omega

/-! ### Theorem 6 & 7: Exact Pareto Boundary Cut Global Optimality & Branch-and-Bound Soundness -/

/-- Check bit i of a 6-bit placement mask (false = Quantum qfree, true = Classical !T). -/
def cutBit (mask : Nat) (i : Nat) : Bool :=
  ((mask >>> i) &&& 1) == 1

/-- Silq legality predicate on 6-stage pipeline: stage 0 (state_prep) must be Q (false),
    stage 5 (final_readout) must be C (true). -/
def isLegalCut (mask : Fin 64) : Bool :=
  (!cutBit mask.val 0) && cutBit mask.val 5

/-- Stage T-gate count under placement mask. -/
def cutTGates (mask : Fin 64) : Nat :=
  (if cutBit mask.val 0 then 0 else 20) +
  (if cutBit mask.val 1 then 0 else 120) +
  (if cutBit mask.val 2 then 0 else 160) +
  (if cutBit mask.val 3 then 0 else 100) +
  (if cutBit mask.val 4 then 0 else 80)

/-- Stage + cross-cut edge classical control ops under placement mask. -/
def cutCtrlOps (mask : Fin 64) : Nat :=
  (if cutBit mask.val 0 then 0 else 2) +
  (if cutBit mask.val 1 then 1800 else 4) +
  (if cutBit mask.val 2 then 900 else 6) +
  (if cutBit mask.val 3 then 1500 else 4) +
  (if cutBit mask.val 4 then 400 else 5) +
  (if cutBit mask.val 5 then 10 else 0) +
  (if cutBit mask.val 0 != cutBit mask.val 1 then 80 else 0) +
  (if cutBit mask.val 1 != cutBit mask.val 2 then 100 else 0) +
  (if cutBit mask.val 2 != cutBit mask.val 3 then 120 else 0) +
  (if cutBit mask.val 3 != cutBit mask.val 4 then 60 else 0) +
  (if cutBit mask.val 4 != cutBit mask.val 5 then 20 else 0) +
  (if cutBit mask.val 1 != cutBit mask.val 3 then 90 else 0)

/-- Offloaded irreversible classical AND count under placement mask. -/
def cutAndCount (mask : Fin 64) : Nat :=
  (if cutBit mask.val 1 then 32 else 0) +
  (if cutBit mask.val 2 then 16 else 0) +
  (if cutBit mask.val 3 then 24 else 0) +
  (if cutBit mask.val 4 then 8 else 0)

/-- Offloaded stage + cross-cut edge 1-bit reset count under placement mask. -/
def cutResetCount (mask : Fin 64) : Nat :=
  (if cutBit mask.val 1 then 16 else 0) +
  (if cutBit mask.val 2 then 8 else 0) +
  (if cutBit mask.val 3 then 12 else 0) +
  (if cutBit mask.val 4 then 4 else 0) +
  (if cutBit mask.val 5 then 4 else 0) +
  (if cutBit mask.val 0 != cutBit mask.val 1 then 8 else 0) +
  (if cutBit mask.val 1 != cutBit mask.val 2 then 8 else 0) +
  (if cutBit mask.val 2 != cutBit mask.val 3 then 8 else 0) +
  (if cutBit mask.val 3 != cutBit mask.val 4 then 4 else 0) +
  (if cutBit mask.val 4 != cutBit mask.val 5 then 4 else 0) +
  (if cutBit mask.val 1 != cutBit mask.val 3 then 6 else 0)

/-- Exact full boundary upper-bound cost scaled by 10 for any placement mask. -/
def cutCostHi10 (mask : Fin 64) : Nat :=
  scaledCostHi10 (cutTGates mask) (cutCtrlOps mask) (cutAndCount mask) (cutResetCount mask)

/-- Exact full boundary lower-bound cost scaled by 160 for any placement mask. -/
def cutCostLo160 (mask : Fin 64) : Nat :=
  scaledCostLo160 (cutTGates mask) (cutCtrlOps mask) (cutAndCount mask) (cutResetCount mask)

/-- Kernel-checked global optimality of cut mask 52 (QQCQCC):
    - Legal cut mask 52 has exact cost_hi = 2162/5 (4324/10) and cost_lo = 1729/4 (69160/160).
    - Universally optimal over all 64 masks satisfying isLegalCut (both cost_hi and cost_lo!).
    - Strictly beats all-quantum mask 32 (QQQQQC: 4891/10) and naive min-T mask 62 (QCCCCC: 2816/5),
      even though mask 62 cuts T-gates by 24x (480 -> 20) vs mask 32. -/
theorem pareto_cut_52_global_optimality :
    isLegalCut ⟨52, by decide⟩ = true ∧
    cutCostHi10 ⟨52, by decide⟩ = 4324 ∧
    cutCostLo160 ⟨52, by decide⟩ = 69160 ∧
    cutCostHi10 ⟨32, by decide⟩ = 4891 ∧
    cutCostHi10 ⟨62, by decide⟩ = 5632 ∧
    cutTGates ⟨32, by decide⟩ = 24 * cutTGates ⟨62, by decide⟩ ∧
    cutCostHi10 ⟨52, by decide⟩ < cutCostHi10 ⟨32, by decide⟩ ∧
    cutCostHi10 ⟨32, by decide⟩ < cutCostHi10 ⟨62, by decide⟩ ∧
    (∀ mask : Fin 64, isLegalCut mask = true → cutCostHi10 ⟨52, by decide⟩ ≤ cutCostHi10 mask) ∧
    (∀ mask : Fin 64, isLegalCut mask = true → cutCostLo160 ⟨52, by decide⟩ ≤ cutCostLo160 mask) := by
  decide

/-- Universal soundness of the branch-and-bound admissible lower bound:
    adding per-stage min(qCost, cCost) and omitting non-negative cross-edge penalties
    never overestimates any legal completion cost. -/
theorem branch_and_bound_lower_bound_sound :
    ∀ (prefixCost qCost cCost edgePenalty : Nat) (chooseC : Bool),
      prefixCost + min qCost cCost ≤
        prefixCost + (if chooseC then cCost else qCost) + edgePenalty := by
  intro prefixCost qCost cCost edgePenalty chooseC
  cases chooseC <;> simp [Nat.min_def] <;> split <;> omega

#print axioms silq_effect_boundary_sound
#print axioms cs21_parametric_net_regression
#print axioms cs21_4x_mirage_600_over_401
#print axioms landauer_and_bracket_and_toffoli_zero
#print axioms noncommutativity_qfree_vs_measure_16and
#print axioms pareto_cut_52_global_optimality
#print axioms branch_and_bound_lower_bound_sound

end SilqCS21Boundary
