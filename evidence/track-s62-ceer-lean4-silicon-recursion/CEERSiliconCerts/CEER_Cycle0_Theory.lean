/-
  CEER_Cycle0_Theory.lean — Pure-Init Lean 4.36.0 Formalization of Classical Idealized Theory T_0.

  Zero external packages (no Mathlib), zero sorry, zero admit, zero native_decide.
  Formalizes four falsifiable idealized hypotheses for a coupled multi-core silicon system
  and proves constructive falsification criteria over exact integers (Z / N):
    - H0a: Linear non-concave core power scaling across physical core counts (p = 1, 2, 4, 8)
    - H0b: Flat memory energy/op across L1 (16 KiB) -> DRAM (64 MiB) (<= 2x) with zero
           platform dark-mode (P_psys - P_pkg) elevation
    - H0c: Spatial die-topology invariance (adjacent vs distant core-pair thermal rise
           equal within 500 mC = 0.5 C)
    - H0d: Single-valued non-hysteretic cooling (zero signed discrete Green's-theorem
           hysteresis loop area and matched ascending vs descending fan RPM within 50 RPM)
-/

namespace CEERSiliconCerts.Cycle0Theory

/-- Raw integer summary of a Cycle-0 live silicon observation record (all values exact integers). -/
structure Cycle0Obs where
  -- Package power in mW (exact integer floor of delta_uj * 1000 / delta_us) at p = 1, 2, 4, 8 cores
  pkgMwP1 : Nat
  pkgMwP2 : Nat
  pkgMwP4 : Nat
  pkgMwP8 : Nat
  -- Memory pointer-chase energy (uJ) and completed chases at S = 16 KiB (L1) and S = 64 MiB (DRAM)
  pkgUj16k : Nat
  ops16k : Nat
  pkgUj64m : Nat
  ops64m : Nat
  -- Platform dark-mode power P_dark = P_psys - P_pkg (in mW, Int) at S = 16 KiB vs S = 64 MiB
  darkMw16k : Int
  darkMw64m : Int
  -- Spatial die-topology: baseline-subtracted thermal cross-talk (mC) on inactive cores
  -- for adjacent pair (0,1) vs distant pair (0,7), plus active-pair rise delta
  adjRiseMc : Int
  distRiseMc : Int
  -- Up-down hysteresis ramp: signed 2 * Area = sum (rpm_{t+1} + rpm_t) * (T_{t+1} - T_t)
  -- and branch mean RPM (exact integer RPM) on ascending vs descending halves
  twiceHystArea : Int
  rpmUpMean : Int
  rpmDownMean : Int
  deriving Repr

/-- H0a (Idealized Linear Non-Concave Core Scaling):
    Incremental package power per core on [4, 8] is at least the marginal slope on [1, 4],
    i.e. (P(8) - P(4)) / 4 >= (P(4) - P(1)) / 3, cross-multiplied over Z so constant
    background power P_bg cancels identically. -/
def H0a_LinearPowerScaling (o : Cycle0Obs) : Prop :=
  3 * ((o.pkgMwP8 : Int) - (o.pkgMwP4 : Int)) >= 4 * ((o.pkgMwP4 : Int) - (o.pkgMwP1 : Int))

/-- H0b (Idealized Flat Memory Hierarchy):
    Energy per completed chase at 64 MiB is at most 2x energy per chase at 16 KiB
    (cross-multiplied strictly over N: pkgUj64m * ops16k <= 2 * pkgUj16k * ops64m)
    AND platform dark-mode overhead does not increase at 64 MiB. -/
def H0b_FlatMemoryEnergy (o : Cycle0Obs) : Prop :=
  o.pkgUj64m * o.ops16k <= 2 * o.pkgUj16k * o.ops64m ∧ o.darkMw64m <= o.darkMw16k

/-- H0c (Idealized Lumped Spatial Die Invariance):
    Adjacent and distant 2-core heating produce identical thermal elevation within +-500 mC. -/
def H0c_SpatialInvariance (o : Cycle0Obs) : Prop :=
  o.adjRiseMc - o.distRiseMc <= 500 ∧ o.distRiseMc - o.adjRiseMc <= 500

/-- H0d (Idealized Single-Valued Non-Hysteretic Cooling):
    Signed discrete Green's-theorem hysteresis area vanishes identically AND
    descending-branch mean fan RPM matches ascending-branch mean RPM within +-50 RPM. -/
def H0d_SingleValuedCooling (o : Cycle0Obs) : Prop :=
  o.twiceHystArea = 0 ∧ o.rpmDownMean - o.rpmUpMean <= 50 ∧ o.rpmUpMean - o.rpmDownMean <= 50

/-- Constructive universal falsification rule for H0a. -/
theorem falsify_H0a (o : Cycle0Obs)
    (h : 4 * ((o.pkgMwP4 : Int) - (o.pkgMwP1 : Int)) > 3 * ((o.pkgMwP8 : Int) - (o.pkgMwP4 : Int))) :
    ¬ H0a_LinearPowerScaling o := by
  unfold H0a_LinearPowerScaling
  omega

/-- Constructive universal falsification rule for H0b via energy-per-op cliff. -/
theorem falsify_H0b_energy (o : Cycle0Obs)
    (h : o.pkgUj64m * o.ops16k > 2 * o.pkgUj16k * o.ops64m) :
    ¬ H0b_FlatMemoryEnergy o := by
  intro ⟨h1, _⟩
  omega

/-- Constructive universal falsification rule for H0b via platform dark-mode jump. -/
theorem falsify_H0b_dark (o : Cycle0Obs)
    (h : o.darkMw64m > o.darkMw16k) :
    ¬ H0b_FlatMemoryEnergy o := by
  intro ⟨_, h2⟩
  omega

/-- Constructive universal falsification rule for H0c via positive or negative spatial asymmetry. -/
theorem falsify_H0c (o : Cycle0Obs)
    (h : o.adjRiseMc - o.distRiseMc > 500 ∨ o.distRiseMc - o.adjRiseMc > 500) :
    ¬ H0c_SpatialInvariance o := by
  intro ⟨h1, h2⟩
  cases h with
  | inl hl => omega
  | inr hr => omega

/-- Constructive universal falsification rule for H0d via nonzero Green's-theorem loop area. -/
theorem falsify_H0d_area (o : Cycle0Obs)
    (h : o.twiceHystArea ≠ 0) :
    ¬ H0d_SingleValuedCooling o := by
  intro ⟨ha, _⟩
  exact h ha

/-- Constructive universal falsification rule for H0d via branch RPM split > 50 RPM. -/
theorem falsify_H0d_rpm (o : Cycle0Obs)
    (h : o.rpmDownMean - o.rpmUpMean > 50 ∨ o.rpmUpMean - o.rpmDownMean > 50) :
    ¬ H0d_SingleValuedCooling o := by
  intro ⟨_, h1, h2⟩
  cases h with
  | inl hl => omega
  | inr hr => omega

/-- Exact discrete Green's-theorem trapezoidal area helper for constant fan RPM `c`
    along a trajectory closing back to `t0`. -/
def closedConstTrapArea (c t0 : Int) : Int → List Int → Int
  | prev, [] => (c + c) * (t0 - prev)
  | prev, x :: xs => (c + c) * (x - prev) + closedConstTrapArea c t0 x xs

theorem closedConstTrapArea_eq (c t0 : Int) :
    ∀ (cur : Int) (xs : List Int), closedConstTrapArea c t0 cur xs = (c + c) * (t0 - cur) := by
  intro cur xs
  induction xs generalizing cur with
  | nil => rfl
  | cons x xs ih =>
    simp only [closedConstTrapArea, ih x]
    rw [← Int.mul_add]
    have hsub : (x - cur) + (t0 - x) = t0 - cur := by omega
    rw [hsub]

/-- Exact discrete Green's theorem identity: if a cooling map is constant (`rpm_t = c` for all `t`),
    the signed trapezoidal area over any closed temperature trajectory (`T_end = T_start`) is 0. -/
theorem constant_fan_zero_hyst_area (c t0 : Int) (ts : List Int) :
    closedConstTrapArea c t0 t0 ts = 0 := by
  rw [closedConstTrapArea_eq, Int.sub_self, Int.mul_zero]

end CEERSiliconCerts.Cycle0Theory

#print axioms CEERSiliconCerts.Cycle0Theory.falsify_H0a
#print axioms CEERSiliconCerts.Cycle0Theory.falsify_H0b_energy
#print axioms CEERSiliconCerts.Cycle0Theory.falsify_H0b_dark
#print axioms CEERSiliconCerts.Cycle0Theory.falsify_H0c
#print axioms CEERSiliconCerts.Cycle0Theory.falsify_H0d_area
#print axioms CEERSiliconCerts.Cycle0Theory.falsify_H0d_rpm
#print axioms CEERSiliconCerts.Cycle0Theory.constant_fan_zero_hyst_area
#print axioms CEERSiliconCerts.Cycle0Theory.closedConstTrapArea_eq
