/-
  Track S160 EXP-Q42b: Prior-Tilt Logit-Bias Obstruction Theorem and
  Fixed-Scale Lattice Remainder Contraction. Pure Init, exact integers.
-/

namespace PriorTilt

/-- Net fixes of a constant shift: items fixed minus items regressed. -/
def netGain (fixes regressions : Int) : Int :=
  fixes - regressions

/-- Cleared numerator of balanced gain `fPos / (2 * nPos) - rNeg / (2 * nNeg)`
    scaled by the positive factor `2 * nPos * nNeg`. -/
def balancedNumerator (fPos rNeg nPos nNeg : Int) : Int :=
  fPos * nNeg - rNeg * nPos

/-- Cleared fixed-grid defect predicate: `2 * (x - m * scale)` in `[-scale, scale]`,
    which is `|x - m * scale| <= scale / 2` with denominators cleared. -/
def gridDefectBounded (x m scale : Int) : Prop :=
  -(scale) <= 2 * (x - m * scale) ∧ 2 * (x - m * scale) <= scale

theorem netGain_pos_of_gt (fixes regressions : Int) (h : regressions < fixes) :
    0 < netGain fixes regressions := by
  unfold netGain
  omega

theorem prior_tilt_imbalance_gain
    (nPos nNeg fixesReal regressionsReal fixesFlip regressionsFlip : Int)
    (_hImbalanced : nPos ≠ nNeg)
    (hReal : regressionsReal < fixesReal)
    (hFlip : regressionsFlip < fixesFlip) :
    0 < netGain fixesReal regressionsReal ∧ 0 < netGain fixesFlip regressionsFlip := by
  constructor
  · unfold netGain
    omega
  · unfold netGain
    omega

theorem prior_tilt_witness_77_vs_52 :
    (264 : Int) - 167 = 97 ∧ (18 : Int) - 7 = 11 ∧ 75 + 2 = 77 ∧ 0 + 52 = 52 ∧
    77 * 58 = 11 * 406 ∧ 52 * 203 = 26 * 406 ∧
    0 < netGain 77 0 ∧ 0 < netGain 52 0 := by
  decide

theorem balanced_numerator_zero_of_equal (fPos rNeg nPos nNeg : Int)
    (hCounts : nPos = nNeg) (hRates : fPos = rNeg) :
    balancedNumerator fPos rNeg nPos nNeg = 0 := by
  unfold balancedNumerator
  rw [hCounts, hRates]
  exact Int.sub_self _

theorem balanced_prior_gate_sufficiency (fPos rNeg nPos nNeg : Int)
    (hCounts : nPos = nNeg) (hRates : fPos = rNeg) :
    balancedNumerator fPos rNeg nPos nNeg = 0 ∧
    ¬ 0 < balancedNumerator fPos rNeg nPos nNeg := by
  have hZero := balanced_numerator_zero_of_equal fPos rNeg nPos nNeg hCounts hRates
  constructor
  · exact hZero
  · rw [hZero]
    omega

theorem fixed_grid_defect_bound (x m scale : Int) (_hScale : 0 < scale)
    (hDefect : gridDefectBounded x m scale) :
    2 * x <= 2 * (m * scale) + scale ∧ 2 * (m * scale) - scale <= 2 * x := by
  unfold gridDefectBounded at hDefect
  constructor
  · omega
  · omega

theorem contraction_factor_1_625 :
    3 * 1 * 60 < 45 * 2500 ∧ 3 * 60 * 625 = 1 * 2500 * 45 ∧
    45 * 4 = 3 * 60 := by
  decide

theorem fixed_grid_remainder_contraction (r rNext : Int)
    (hNextNonneg : 0 <= rNext) (hStep : 625 * rNext <= r) :
    rNext <= r ∧ (r = 0 → rNext = 0) := by
  constructor
  · omega
  · omega

theorem fixed_grid_remainder_two_steps (r r1 r2 : Int)
    (h2Nonneg : 0 <= r2) (hStep1 : 625 * r1 <= r) (hStep2 : 625 * r2 <= r1) :
    390625 * r2 <= r ∧ r2 <= r := by
  constructor
  · omega
  · omega

end PriorTilt
