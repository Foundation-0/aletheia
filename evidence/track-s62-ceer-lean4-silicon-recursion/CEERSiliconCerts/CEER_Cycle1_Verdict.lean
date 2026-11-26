/-
  CEER_Cycle1_Verdict.lean — Auto-Synthesized Live Silicon Kernel Verdict for Cycle 1.

  Raw integer witness extracted directly from cycle_1_telemetry.json
  (telemetry SHA-256: df2993b47a8bd7c88be2cfc4c127adf485431dcd12558438ae3a3205089bf8b6;
   preregistration SHA-256: 6a75abdc1ab0efa2662704b11e10ddced86bc507d8582e58a902cc8c50b04d8a).

  Honest Mixed Verdict on Disjoint Out-of-Sample Micro-Levers:
    - H1a (PL1-saturated efficiency scaling p in {3,6}): CORROBORATED (1.87x >= 1.60x)
    - H1b (8 MiB -> 32 MiB cliff >= 1.50x + dark power): FALSIFIED on magnitude (1.32x < 1.50x;
      shared-L3/STLB contention already degraded 8 MiB, while on-package dark power held > 4 W)
    - H1c (die-interior spatial anisotropy (2,3) vs (2,7)): CORROBORATED (+532 mC margin,
      +3390 mC interior-minus-edge; both contrasts negative -> static die gradient dominates)
    - H1d (open-loop thermal lag T_down > T_up): FALSIFIED on sign (-2063 mC; delayed EC fan
      surge to 3355 RPM + pre-soak relaxation reversed the hysteresis loop area to +30444)

  Zero external packages, zero sorry, zero admit, zero native_decide.
-/

namespace CEERSiliconCerts.Cycle1Verdict

structure Cycle1Obs where
  pkgMwP3 : Nat
  pkgMwP6 : Nat
  pkgUjP3 : Nat
  pkgUjP6 : Nat
  opsP3 : Nat
  opsP6 : Nat
  pkgUj8m : Nat
  ops8m : Nat
  pkgUj32m : Nat
  ops32m : Nat
  pkgDarkMw8m : Int
  pkgDarkMw32m : Int
  contrast23Mc : Int
  contrast27Mc : Int
  interiorMinusEdgeMc : Int
  twiceThermalLoadArea : Int
  tempUpMeanMc : Int
  tempDownMeanMc : Int
  deriving Repr

def obs1 : Cycle1Obs :=
  { pkgMwP3 := 69989,
    pkgMwP6 := 69832,
    pkgUjP3 := 126595501,
    pkgUjP6 := 126321271,
    opsP3 := 9151168512,
    opsP6 := 17114628096,
    pkgUj8m := 127962319,
    ops8m := 14524416,
    pkgUj32m := 133298059,
    ops32m := 11403264,
    pkgDarkMw8m := 4420,
    pkgDarkMw32m := 4212,
    contrast23Mc := -793,
    contrast27Mc := -1325,
    interiorMinusEdgeMc := 3390,
    twiceThermalLoadArea := 30444,
    tempUpMeanMc := 88173,
    tempDownMeanMc := 86110 }

def H1a_PL1EfficiencyScaling (o : Cycle1Obs) : Prop :=
  20 * ((o.pkgMwP6 : Int) - (o.pkgMwP3 : Int)) <= (o.pkgMwP3 : Int) ∧
  20 * ((o.pkgMwP3 : Int) - (o.pkgMwP6 : Int)) <= (o.pkgMwP3 : Int) ∧
  10 * o.opsP6 * o.pkgUjP3 >= 16 * o.opsP3 * o.pkgUjP6

def H1b_L3DramCliffAndDarkPower (o : Cycle1Obs) : Prop :=
  2 * o.pkgUj32m * o.ops8m >= 3 * o.pkgUj8m * o.ops32m ∧
  o.pkgDarkMw8m > 0 ∧ o.pkgDarkMw32m > 0

def H1c_DieInteriorAnisotropy (o : Cycle1Obs) : Prop :=
  o.contrast23Mc > o.contrast27Mc ∧ o.interiorMinusEdgeMc > 1500

def H1d_ThermalLoadHysteresis (o : Cycle1Obs) : Prop :=
  o.twiceThermalLoadArea ≠ 0 ∧ o.tempDownMeanMc > o.tempUpMeanMc

/-- Constructive Live-Silicon Corroboration of H1a: package power stayed flat within 0.22%
    under the 70 W PL1 ceiling while ops/uJ scaled by 1.874x (>= 1.60x pre-registered bound). -/
theorem cycle1_corroborates_H1a : H1a_PL1EfficiencyScaling obs1 := by
  dsimp [H1a_PL1EfficiencyScaling, obs1]
  omega

/-- Constructive Live-Silicon Disproof of H1b: under live 8-core shared-L3/STLB contention,
    the incremental 8 MiB -> 32 MiB cliff is 1.326x < 1.50x, refuting the single-core isolated
    L3 step assumption and motivating Cycle 2's two-regime TLB+L3 cliff hypothesis. -/
theorem cycle1_disproof_H1b : ¬ H1b_L3DramCliffAndDarkPower obs1 := by
  intro ⟨h1, _, _⟩
  dsimp [obs1] at h1
  omega

/-- Residual empirical structure from H1b: although < 1.50x, the 8 MiB -> 32 MiB cliff still
    exceeds 1.30x and on-package dark power exceeds 4000 mW at both footprints. -/
theorem cycle1_H1b_residual_cliff_and_dark_power :
    100 * obs1.pkgUj32m * obs1.ops8m >= 130 * obs1.pkgUj8m * obs1.ops32m ∧
    obs1.pkgDarkMw8m > 4000 ∧ obs1.pkgDarkMw32m > 4000 := by
  dsimp [obs1]
  omega

/-- Constructive Live-Silicon Corroboration of H1c: interior pair (2,3) beats edge-spanning
    (2,7) by +532 mC and interior cores {2,3,4,5} exceed edge cores {0,1,6} by +3390 mC. -/
theorem cycle1_corroborates_H1c : H1c_DieInteriorAnisotropy obs1 := by
  dsimp [H1c_DieInteriorAnisotropy, obs1]
  omega

/-- Static die-gradient obstruction discovered in Cycle 1: both (2,3) and (2,7) active-minus-
    inactive contrasts are negative, proving static die-interior hotspots (Cores 4,5) dominate
    2-core self-heating and motivating Cycle 2's extreme-pair (4,5) vs (1,6) sign-reversal test. -/
theorem cycle1_H1c_static_dominance_obstruction :
    obs1.contrast23Mc < 0 ∧ obs1.contrast27Mc < 0 := by
  dsimp [obs1]
  omega

/-- Constructive Live-Silicon Disproof of H1d: delayed EC fan surge (3300 -> 3355 RPM) plus
    pre-soak relaxation made the descending branch 2063 mC cooler than the ascending branch. -/
theorem cycle1_disproof_H1d : ¬ H1d_ThermalLoadHysteresis obs1 := by
  intro ⟨_, h2⟩
  dsimp [obs1] at h2
  omega

/-- Reversed-sign hysteresis obstruction from Cycle 1: signed 2*Area(T_pkg, load_p) flipped
    to +30444 (from -8000 in Cycle 0) with cooling lag > 2000 mC, motivating Cycle 2's
    coordinate-free Schur-complement hidden-mode electro-thermal closure. -/
theorem cycle1_H1d_reversed_loop_obstruction :
    obs1.twiceThermalLoadArea > 30000 ∧ obs1.tempUpMeanMc - obs1.tempDownMeanMc > 2000 := by
  dsimp [obs1]
  omega

end CEERSiliconCerts.Cycle1Verdict

#print axioms CEERSiliconCerts.Cycle1Verdict.cycle1_corroborates_H1a
#print axioms CEERSiliconCerts.Cycle1Verdict.cycle1_disproof_H1b
#print axioms CEERSiliconCerts.Cycle1Verdict.cycle1_H1b_residual_cliff_and_dark_power
#print axioms CEERSiliconCerts.Cycle1Verdict.cycle1_corroborates_H1c
#print axioms CEERSiliconCerts.Cycle1Verdict.cycle1_H1c_static_dominance_obstruction
#print axioms CEERSiliconCerts.Cycle1Verdict.cycle1_disproof_H1d
#print axioms CEERSiliconCerts.Cycle1Verdict.cycle1_H1d_reversed_loop_obstruction
