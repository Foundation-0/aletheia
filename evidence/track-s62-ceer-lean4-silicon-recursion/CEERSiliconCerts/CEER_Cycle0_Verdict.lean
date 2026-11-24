/-
  CEER_Cycle0_Verdict.lean — Auto-Synthesized Live Silicon Kernel Verdict for Cycle 0.

  Raw integer witness extracted directly from cycle_0_telemetry.json
  (telemetry SHA-256: 6d0333826c23cdaff3643ca12b27b4b34242c31dd2c3cd823ecc23dd697a5a95).
  Zero external packages, zero sorry, zero admit, zero native_decide.
-/

namespace CEERSiliconCerts.Cycle0Verdict

structure Cycle0Obs where
  pkgMwP1 : Nat
  pkgMwP2 : Nat
  pkgMwP4 : Nat
  pkgMwP8 : Nat
  opsP1 : Nat
  opsP8 : Nat
  pkgUj16k : Nat
  ops16k : Nat
  pkgUj64m : Nat
  ops64m : Nat
  darkMw16k : Int
  darkMw64m : Int
  pkgDarkMw16k : Int
  pkgDarkMw64m : Int
  adjInactRiseMc : Int
  distInactRiseMc : Int
  twiceFanHystArea : Int
  rpmUpMean : Int
  rpmDownMean : Int
  tempUpMeanMc : Int
  tempDownMeanMc : Int
  twiceThermalLoadArea : Int
  deriving Repr

def obs0 : Cycle0Obs :=
  { pkgMwP1 := 69984,
     pkgMwP2 := 69857,
     pkgMwP4 := 69802,
     pkgMwP8 := 69884,
     opsP1 := 2839756800,
     opsP8 := 22734471168,
     pkgUj16k := 105425939,
     ops16k := 722436096,
     pkgUj64m := 118664247,
     ops64m := 10010624,
     darkMw16k := -65202,
     darkMw64m := -65286,
     pkgDarkMw16k := 4313,
     pkgDarkMw64m := 4051,
     adjInactRiseMc := -343,
     distInactRiseMc := 985,
     twiceFanHystArea := 0,
     rpmUpMean := 3300,
     rpmDownMean := 3300,
     tempUpMeanMc := 86270,
     tempDownMeanMc := 87371,
     twiceThermalLoadArea := -8000 }

def H0a_LinearPowerScaling (o : Cycle0Obs) : Prop :=
  3 * ((o.pkgMwP8 : Int) - (o.pkgMwP4 : Int)) >= 4 * ((o.pkgMwP4 : Int) - (o.pkgMwP1 : Int))

def H0b_FlatMemoryEnergy (o : Cycle0Obs) : Prop :=
  o.pkgUj64m * o.ops16k <= 2 * o.pkgUj16k * o.ops64m ∧ o.darkMw64m <= o.darkMw16k

def H0c_SpatialInvariance (o : Cycle0Obs) : Prop :=
  o.adjInactRiseMc - o.distInactRiseMc <= 500 ∧ o.distInactRiseMc - o.adjInactRiseMc <= 500

def H0d_SingleValuedFanCooling (o : Cycle0Obs) : Prop :=
  o.twiceFanHystArea = 0 ∧ o.rpmDownMean - o.rpmUpMean <= 50 ∧ o.rpmUpMean - o.rpmDownMean <= 50

/-- Constructive Live-Silicon Disproof of H0b: 64 MiB DRAM pointer-chasing consumes > 80x
    more package energy per completed access than 16 KiB L1 (far exceeding the 2x bound). -/
theorem cycle0_disproof_H0b : ¬ H0b_FlatMemoryEnergy obs0 := by
  intro ⟨h1, _⟩
  dsimp [obs0] at h1
  omega

/-- Constructive sharp lower bound: energy/op cliff across 16 KiB -> 64 MiB exceeds 80x. -/
theorem cycle0_H0b_cliff_gt_80x : obs0.pkgUj64m * obs0.ops16k > 80 * obs0.pkgUj16k * obs0.ops64m := by
  dsimp [obs0]
  omega

/-- Constructive Live-Silicon Disproof of H0c: inactive-core baseline-subtracted cross-talk
    between adjacent (0,1) and distant (0,7) differs by 1328 mC > 500 mC. -/
theorem cycle0_disproof_H0c : ¬ H0c_SpatialInvariance obs0 := by
  intro ⟨_, h2⟩
  dsimp [obs0] at h2
  omega

/-- Honest PL1-Saturation Obstruction on H0a: H0a holds degenerately ONLY because package
    power is clamped within +-200 mW of the 70 W PL1 wall while retired ops scale > 7x. -/
theorem cycle0_H0a_degenerate_pl1_saturation :
    H0a_LinearPowerScaling obs0 ∧
    ((obs0.pkgMwP1 : Int) - (obs0.pkgMwP8 : Int) <= 200) ∧
    ((obs0.pkgMwP8 : Int) - (obs0.pkgMwP1 : Int) <= 200) ∧
    obs0.opsP8 >= 7 * obs0.opsP1 := by
  dsimp [H0a_LinearPowerScaling, obs0]
  omega

/-- Honest EC Fan Plateau vs Die-Temperature Hysteresis on H0d: fan RPM remained quantized
    at 3300 RPM (so H0d_SingleValuedFanCooling holds), yet die temperature lagged warmer on
    descent by > 1000 mC with strictly nonzero signed (T_pkg, load_p) loop area. -/
theorem cycle0_H0d_fan_plateau_and_thermal_lag :
    H0d_SingleValuedFanCooling obs0 ∧
    obs0.tempDownMeanMc - obs0.tempUpMeanMc > 1000 ∧
    obs0.twiceThermalLoadArea ≠ 0 := by
  dsimp [H0d_SingleValuedFanCooling, obs0]
  omega

/-- Honest Platform Dark-Power Obstruction: on-package P_pkg - P_core - P_uncore exceeds
    4000 mW at both memory endpoints while ACPI psys reads strictly below package-0. -/
theorem cycle0_on_package_dark_power_positive :
    obs0.pkgDarkMw16k > 4000 ∧ obs0.pkgDarkMw64m > 4000 ∧ obs0.darkMw16k < 0 := by
  dsimp [obs0]
  omega

end CEERSiliconCerts.Cycle0Verdict

#print axioms CEERSiliconCerts.Cycle0Verdict.cycle0_disproof_H0b
#print axioms CEERSiliconCerts.Cycle0Verdict.cycle0_H0b_cliff_gt_80x
#print axioms CEERSiliconCerts.Cycle0Verdict.cycle0_disproof_H0c
#print axioms CEERSiliconCerts.Cycle0Verdict.cycle0_H0a_degenerate_pl1_saturation
#print axioms CEERSiliconCerts.Cycle0Verdict.cycle0_H0d_fan_plateau_and_thermal_lag
#print axioms CEERSiliconCerts.Cycle0Verdict.cycle0_on_package_dark_power_positive
