/-
  CEER_Cycle1_Theory.lean — Pure-Init Lean 4.36.0 Formalization of Obstruction-Lifted Theory T_1.

  Constructively lifts all four Cycle-0 live silicon obstructions onto strictly disjoint
  unseen out-of-sample micro-levers (p in {3, 6}; S in {8 MiB, 32 MiB} straddling the
  24 MiB L3 boundary; core pairs (2,3) vs (2,7); ramp 0,2,4,8,8,4,2,0 at 1800 ms/step):
    - H1a: PL1-saturated computational efficiency scaling (|P6 - P3| <= 5% while
           efficiency ops/uJ increases >= 1.60x from p=3 to p=6)
    - H1b: Discontinuous L3->DRAM energy-per-op cliff (>= 1.50x across 8 MiB -> 32 MiB)
           with strictly positive on-package dark power P_pkg - P_core - P_uncore > 0
    - H1c: Common-mode-cancelled die-interior spatial thermal anisotropy
           (interior pair (2,3) active-minus-inactive contrast > edge-spanning (2,7),
            and interior cores {2,3,4,5} hotter than edge cores {0,1,6} by > 1500 mC)
    - H1d: Two-branch die-temperature thermal-load hysteresis (nonzero signed
           Green's-theorem (T_pkg, load_p) area AND T_down_mean > T_up_mean)

  Zero external packages, zero sorry, zero admit, zero native_decide.
-/

namespace CEERSiliconCerts.Cycle1Theory

/-- Raw integer summary of a Cycle-1 out-of-sample live silicon observation record. -/
structure Cycle1Obs where
  -- u1 unseen cores p=3 and p=6: package power (mW), delta energy (uJ), retired ops
  pkgMwP3 : Nat
  pkgMwP6 : Nat
  pkgUjP3 : Nat
  pkgUjP6 : Nat
  opsP3 : Nat
  opsP6 : Nat
  -- u3 unseen L3-cliff straddling footprints S = 8 MiB vs S = 32 MiB
  pkgUj8m : Nat
  ops8m : Nat
  pkgUj32m : Nat
  ops32m : Nat
  -- On-package dark power P_pkg - P_core - P_uncore (mW, Int) at 8 MiB and 32 MiB
  pkgDarkMw8m : Int
  pkgDarkMw32m : Int
  -- u2 unseen core pairs (2,3) vs (2,7): within-window active-minus-inactive contrast (mC)
  contrast23Mc : Int
  contrast27Mc : Int
  -- Interior mean (Cores 2..5) minus edge mean (Cores 0,1,6) during u2 windows (mC)
  interiorMinusEdgeMc : Int
  -- u4 unseen symmetric ramp (0,2,4,8,8,4,2,0 at 1800 ms/step):
  -- signed Green's-theorem 2*Area(T_pkg, load_p) and branch mean T_pkg (mC)
  twiceThermalLoadArea : Int
  tempUpMeanMc : Int
  tempDownMeanMc : Int
  deriving Repr

/-- H1a: Under PL1 ceiling, package power stays within +-5% between p=3 and p=6 while
    exact computational efficiency (ops / uJ) scales by at least 16/10 = 1.60x. -/
def H1a_PL1EfficiencyScaling (o : Cycle1Obs) : Prop :=
  20 * ((o.pkgMwP6 : Int) - (o.pkgMwP3 : Int)) <= (o.pkgMwP3 : Int) ∧
  20 * ((o.pkgMwP3 : Int) - (o.pkgMwP6 : Int)) <= (o.pkgMwP3 : Int) ∧
  10 * o.opsP6 * o.pkgUjP3 >= 16 * o.opsP3 * o.pkgUjP6

/-- H1b: Crossing the 24 MiB L3 boundary (8 MiB -> 32 MiB) causes >= 3/2 = 1.50x
    energy-per-chase jump AND strictly positive on-package dark power at both footprints. -/
def H1b_L3DramCliffAndDarkPower (o : Cycle1Obs) : Prop :=
  2 * o.pkgUj32m * o.ops8m >= 3 * o.pkgUj8m * o.ops32m ∧
  o.pkgDarkMw8m > 0 ∧ o.pkgDarkMw32m > 0

/-- H1c: Die-interior spatial thermal anisotropy persists on unseen pairs (2,3) vs (2,7). -/
def H1c_DieInteriorAnisotropy (o : Cycle1Obs) : Prop :=
  o.contrast23Mc > o.contrast27Mc ∧ o.interiorMinusEdgeMc > 1500

/-- H1d: Unseen symmetric ramp exhibits nonzero (T_pkg, load_p) Green's-theorem loop area
    AND strictly warmer descending-branch mean package temperature. -/
def H1d_ThermalLoadHysteresis (o : Cycle1Obs) : Prop :=
  o.twiceThermalLoadArea ≠ 0 ∧ o.tempDownMeanMc > o.tempUpMeanMc

/-- Universal algebraic law: if P_pkg is clamped flat (P6 <= P3 + eps) while per-core
    throughput stays strictly proportional (ops6 = 2 * ops3) over equal time windows,
    then ops/uJ scales inversely with power ratio (>= 1.60x whenever 5*uJ6 <= 6*uJ3). -/
theorem pl1_flat_power_implies_eff_gain (ops3 uJ3 uJ6 : Nat)
    (h_uJ : 5 * uJ6 <= 6 * uJ3) :
    10 * (2 * ops3) * uJ3 >= 16 * ops3 * uJ6 := by
  have h20 : (10 * 2 : Nat) = 20 := rfl
  have h1 : 10 * (2 * ops3) * uJ3 = ops3 * (20 * uJ3) := by
    rw [← Nat.mul_assoc 10 2 ops3, h20, Nat.mul_comm 20 ops3, Nat.mul_assoc]
  have h2 : 16 * ops3 * uJ6 = ops3 * (16 * uJ6) := by
    rw [Nat.mul_comm 16 ops3, Nat.mul_assoc]
  rw [h1, h2]
  have h_coeff : 16 * uJ6 <= 20 * uJ3 := by omega
  exact Nat.mul_le_mul_left ops3 h_coeff

/-- Universal falsification rule for H1d if descending thermal lag fails to hold. -/
theorem falsify_H1d_temp_lag (o : Cycle1Obs)
    (h : o.tempDownMeanMc <= o.tempUpMeanMc) :
    ¬ H1d_ThermalLoadHysteresis o := by
  intro ⟨_, h2⟩
  omega

/-- Universal falsification rule for H1c if contrast fails to satisfy (2,3) > (2,7). -/
theorem falsify_H1c_contrast (o : Cycle1Obs)
    (h : o.contrast23Mc <= o.contrast27Mc) :
    ¬ H1c_DieInteriorAnisotropy o := by
  intro ⟨h1, _⟩
  omega

/-- Universal falsification rule for H1b if L3->DRAM cliff is weaker than 1.50x. -/
theorem falsify_H1b_cliff (o : Cycle1Obs)
    (h : 2 * o.pkgUj32m * o.ops8m < 3 * o.pkgUj8m * o.ops32m) :
    ¬ H1b_L3DramCliffAndDarkPower o := by
  intro ⟨h1, _, _⟩
  omega

end CEERSiliconCerts.Cycle1Theory

#print axioms CEERSiliconCerts.Cycle1Theory.pl1_flat_power_implies_eff_gain
#print axioms CEERSiliconCerts.Cycle1Theory.falsify_H1d_temp_lag
#print axioms CEERSiliconCerts.Cycle1Theory.falsify_H1c_contrast
#print axioms CEERSiliconCerts.Cycle1Theory.falsify_H1b_cliff
