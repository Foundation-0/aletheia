/-
  CEER_Cycle2_Theory.lean — Pure-Init Lean 4.36.0 Formalization of Second-Order Coupled
  Electro-Thermal & Coordinate-Free Schur-Complement Closure Theory T_2.

  Constructively lifts BOTH Cycle-1 falsifications (H1b shared-L3/STLB cliff magnitude;
  H1d delayed EC fan + thermal-soak sign flip) AND Cycle-1's static die-gradient discovery
  onto strictly disjoint unseen out-of-sample micro-levers:
    - u1: p in {5, 7}                 (disjoint from C0 {1,2,4,8} and C1 {3,6})
    - u2: pairs (4,5) vs (1,6)        (disjoint from C0 {(0,1),(0,7)} and C1 {(2,3),(2,7)})
    - u3: S in {512 KiB, 12 MiB, 48 MiB} (disjoint from C0 {16K,256K,4M,64M} and C1 {8M,32M})
    - u4: ramp 1,3,6,8,6,3,1 @ 1500ms (disjoint from C0 1,2,4,8,8,4,2,1@1200ms and C1 0,2,4,8,8,4,2,0@1800ms)

  Includes a universal algebraic proof of the 3x3 exact integer Schur-complement variance-
  reduction identity:
      (Syy * Suu - Syu^2) * (Suu * Svv - Suv^2) - det(G) * Suu = (Suu * Syv - Suv * Syu)^2 >= 0
  with strict reduction R2 < R1 iff the Schur-projected covariance delta = Suu*Syv - Suv*Syu != 0.

  Zero external packages, zero sorry, zero admit, zero native_decide.
-/

namespace CEERSiliconCerts.Cycle2Theory

/-- Raw integer summary of a Cycle-2 out-of-sample live silicon observation record. -/
structure Cycle2Obs where
  -- u1 unseen cores p=5 and p=7: power (mW), delta energy (uJ), retired ops, mean freq (kHz)
  pkgMwP5 : Nat
  pkgMwP7 : Nat
  pkgUjP5 : Nat
  pkgUjP7 : Nat
  opsP5 : Nat
  opsP7 : Nat
  freqKhzP5 : Nat
  freqKhzP7 : Nat
  -- u3 unseen two-regime TLB+L3+DRAM footprints: 512 KiB, 12 MiB, 48 MiB
  pkgUj512k : Nat
  ops512k : Nat
  pkgUj12m : Nat
  ops12m : Nat
  pkgUj48m : Nat
  ops48m : Nat
  pkgDarkMw512k : Int
  pkgDarkMw12m : Int
  pkgDarkMw48m : Int
  -- u2 unseen extreme die-topology pairs: interior hotspot (4,5) vs edge cool (1,6)
  contrast45Mc : Int
  contrast16Mc : Int
  -- u4 unseen 7-step ramp (1,3,6,8,6,3,1 @ 1500ms): hysteresis + exact 3x3 centered integer Gram entries
  twiceThermalLoadArea : Int
  syy : Int
  suu : Int
  syu : Int
  -- Hidden mode 1: thermal soak time v_soak = t_ms
  svvSoak : Int
  suvSoak : Int
  syvSoak : Int
  -- Hidden mode 2: internal spatial die-gradient v_spread = max_c T_c - min_c T_c
  svvSpread : Int
  suvSpread : Int
  syvSpread : Int
  deriving Repr

/-- Exact 2x2 predictor Gram determinant det(A) = Suu * Svv - Suv^2. -/
def detA (suu svv suv : Int) : Int :=
  suu * svv - suv * suv

/-- Exact 3x3 augmented Gram determinant det(G) for [y, u, v]. -/
def detG (syy suu svv syu syv suv : Int) : Int :=
  syy * detA suu svv suv - syu * (syu * svv - syv * suv) + syv * (syu * suv - syv * suu)

/-- Exact 1-feature residual numerator R1_num = Syy * Suu - Syu^2 (= R1 * Suu). -/
def r1Num (syy suu syu : Int) : Int :=
  syy * suu - syu * syu

/-- Exact Schur-projected cross-covariance delta = Suu * Syv - Suv * Syu. -/
def schurDelta (suu syu syv suv : Int) : Int :=
  suu * syv - suv * syu

/-- H2a: Under PL1 ceiling on unseen p in {5, 7}, P_pkg stays within +-5%, raw ops/uJ scales
    >= 1.25x, AND frequency-normalized efficiency ops/(uJ*freq) scales >= 1.20x. -/
def H2a_FreqNormalizedPL1Efficiency (o : Cycle2Obs) : Prop :=
  20 * ((o.pkgMwP7 : Int) - (o.pkgMwP5 : Int)) <= (o.pkgMwP5 : Int) ∧
  20 * ((o.pkgMwP5 : Int) - (o.pkgMwP7 : Int)) <= (o.pkgMwP5 : Int) ∧
  100 * o.opsP7 * o.pkgUjP5 >= 125 * o.opsP5 * o.pkgUjP7 ∧
  100 * o.opsP7 * o.pkgUjP5 * o.freqKhzP5 >= 120 * o.opsP5 * o.pkgUjP7 * o.freqKhzP7

/-- H2b: Two-regime TLB+L3+DRAM energy-per-chase cliff across unseen {512 KiB, 12 MiB, 48 MiB}:
    512K->48M >= 8x, 512K->12M >= 4x, 12M->48M >= 1.10x, and P_pkg_dark > 0 at all three. -/
def H2b_TwoRegimeTLBL3CliffAndDarkPower (o : Cycle2Obs) : Prop :=
  o.pkgUj48m * o.ops512k >= 8 * o.pkgUj512k * o.ops48m ∧
  o.pkgUj12m * o.ops512k >= 4 * o.pkgUj512k * o.ops12m ∧
  10 * o.pkgUj48m * o.ops12m >= 11 * o.pkgUj12m * o.ops48m ∧
  o.pkgDarkMw512k > 0 ∧ o.pkgDarkMw12m > 0 ∧ o.pkgDarkMw48m > 0

/-- H2c: Static die-topology thermal resistance causes sign reversal on unseen extreme pairs:
    interior (4,5) contrast > 0, edge (1,6) contrast < 0, and total swing > 3000 mC. -/
def H2c_DieTopologySignReversal (o : Cycle2Obs) : Prop :=
  o.contrast45Mc > 0 ∧ o.contrast16Mc < 0 ∧ o.contrast45Mc - o.contrast16Mc > 3000

/-- H2d: Coordinate-free Schur-complement hidden-mode closure on unseen 7-step ramp:
    nonzero hysteresis loop, non-degenerate Gram blocks, >= 5% Schur variance reduction
    from thermal soak mode, and strict positive Schur variance reduction from die-gradient mode. -/
def H2d_SchurComplementHiddenModeClosure (o : Cycle2Obs) : Prop :=
  let r1 := r1Num o.syy o.suu o.syu
  let dA_soak := detA o.suu o.svvSoak o.suvSoak
  let dl_soak := schurDelta o.suu o.syu o.syvSoak o.suvSoak
  let dA_spr := detA o.suu o.svvSpread o.suvSpread
  let dl_spr := schurDelta o.suu o.syu o.syvSpread o.suvSpread
  o.twiceThermalLoadArea ≠ 0 ∧
  o.syy > 0 ∧ o.suu > 0 ∧ r1 > 0 ∧ dA_soak > 0 ∧ dA_spr > 0 ∧
  100 * dl_soak * dl_soak >= 5 * r1 * dA_soak ∧
  dl_spr ≠ 0

/-- Universal 3x3 Exact Integer Schur-Complement Variance Identity (Jacobi-Sylvester form):
    For ALL integer Gram entries,
      R1_num * det(A) - det(G) * Suu = (Suu * Syv - Suv * Syu)^2.
    Proved completely in pure Init Lean 4 without Mathlib or ring. -/
theorem schur_3x3_variance_identity (syy suu svv syu syv suv : Int) :
    r1Num syy suu syu * detA suu svv suv - detG syy suu svv syu syv suv * suu =
    schurDelta suu syu syv suv * schurDelta suu syu syv suv := by
  dsimp [r1Num, detA, detG, schurDelta]
  -- Normalize every 4-factor monomial into canonical sorted factor order
  have hL1 : (syy * suu - syu * syu) * (suu * svv - suv * suv) =
      syy * (suu * (suu * svv - suv * suv)) -
      (suu * svv * syu * syu - suv * suv * syu * syu) := by
    rw [Int.sub_mul, Int.mul_sub (syu * syu)]
    have ha : syy * suu * (suu * svv - suv * suv) = syy * (suu * (suu * svv - suv * suv)) := by
      rw [Int.mul_assoc]
    have hb : syu * syu * (suu * svv) = suu * svv * syu * syu := by
      rw [Int.mul_comm (syu * syu) (suu * svv), ← Int.mul_assoc]
    have hc : syu * syu * (suv * suv) = suv * suv * syu * syu := by
      rw [Int.mul_comm (syu * syu) (suv * suv), ← Int.mul_assoc]
    rw [ha, hb, hc]
  have hL2 : (syy * (suu * svv - suv * suv) - syu * (syu * svv - syv * suv) +
        syv * (syu * suv - syv * suu)) * suu =
      syy * (suu * (suu * svv - suv * suv)) -
      (suu * svv * syu * syu - suu * suv * syu * syv) +
      (suu * suv * syu * syv - suu * suu * syv * syv) := by
    rw [Int.add_mul, Int.sub_mul]
    have h0 : syy * (suu * svv - suv * suv) * suu = syy * (suu * (suu * svv - suv * suv)) := by
      rw [Int.mul_assoc, Int.mul_comm (suu * svv - suv * suv) suu]
    have h1 : syu * (syu * svv - syv * suv) * suu =
        suu * svv * syu * syu - suu * suv * syu * syv := by
      rw [Int.mul_sub, Int.sub_mul]
      have h1a : syu * (syu * svv) * suu = suu * svv * syu * syu := by
        rw [Int.mul_comm (syu * (syu * svv)) suu, Int.mul_comm syu (syu * svv),
            Int.mul_comm syu svv, ← Int.mul_assoc, ← Int.mul_assoc]
      have h1b : syu * (syv * suv) * suu = suu * suv * syu * syv := by
        rw [Int.mul_comm (syu * (syv * suv)) suu, Int.mul_comm syv suv,
            ← Int.mul_assoc, ← Int.mul_assoc, Int.mul_assoc suu syu suv,
            Int.mul_comm syu suv, ← Int.mul_assoc]
      rw [h1a, h1b]
    have h2 : syv * (syu * suv - syv * suu) * suu =
        suu * suv * syu * syv - suu * suu * syv * syv := by
      rw [Int.mul_sub, Int.sub_mul]
      have h2a : syv * (syu * suv) * suu = suu * suv * syu * syv := by
        rw [Int.mul_comm (syv * (syu * suv)) suu, Int.mul_comm syv (syu * suv),
            Int.mul_comm syu suv, ← Int.mul_assoc, ← Int.mul_assoc]
      have h2b : syv * (syv * suu) * suu = suu * suu * syv * syv := by
        rw [Int.mul_comm (syv * (syv * suu)) suu, Int.mul_comm syv suu,
            Int.mul_comm syv (suu * syv), ← Int.mul_assoc, ← Int.mul_assoc]
      rw [h2a, h2b]
    rw [h0, h1, h2]
  have hR : (suu * syv - suv * syu) * (suu * syv - suv * syu) =
      (suu * suu * syv * syv - suu * suv * syu * syv) -
      (suu * suv * syu * syv - suv * suv * syu * syu) := by
    rw [Int.sub_mul, Int.mul_sub, Int.mul_sub]
    have hr1 : suu * syv * (suu * syv) = suu * suu * syv * syv := by
      rw [← Int.mul_assoc, Int.mul_assoc suu syv suu, Int.mul_comm syv suu, ← Int.mul_assoc]
    have hr2 : suu * syv * (suv * syu) = suu * suv * syu * syv := by
      rw [← Int.mul_assoc, Int.mul_assoc suu syv suv, Int.mul_comm syv suv,
          ← Int.mul_assoc, Int.mul_assoc (suu * suv) syv syu, Int.mul_comm syv syu, ← Int.mul_assoc]
    have hr3 : suv * syu * (suu * syv) = suu * suv * syu * syv := by
      rw [Int.mul_comm (suv * syu) (suu * syv)]
      exact hr2
    have hr4 : suv * syu * (suv * syu) = suv * suv * syu * syu := by
      rw [← Int.mul_assoc, Int.mul_assoc suv syu suv, Int.mul_comm syu suv, ← Int.mul_assoc]
    rw [hr1, hr2, hr3, hr4]
  rw [hL1, hL2, hR]
  omega

/-- Universal strict Schur-complement variance reduction theorem:
    Whenever delta = Suu * Syv - Suv * Syu != 0, conditioning on hidden mode v strictly
    reduces residual variance below u alone (det(G) * Suu < R1_num * det(A)). -/
theorem schur_strict_variance_reduction (syy suu svv syu syv suv : Int)
    (h_nz : schurDelta suu syu syv suv ≠ 0) :
    detG syy suu svv syu syv suv * suu < r1Num syy suu syu * detA suu svv suv := by
  have hid := schur_3x3_variance_identity syy suu svv syu syv suv
  have hsq : schurDelta suu syu syv suv * schurDelta suu syu syv suv > 0 := by
    rcases Int.lt_trichotomy (schurDelta suu syu syv suv) 0 with hlt | heq | hgt
    · exact Int.mul_pos_of_neg_of_neg hlt hlt
    · exact False.elim (h_nz heq)
    · exact Int.mul_pos hgt hgt
  omega

/-- Universal falsification rule for H2d if Schur-projected covariance vanishes. -/
theorem falsify_H2d_zero_delta (o : Cycle2Obs)
    (h : schurDelta o.suu o.syu o.syvSpread o.suvSpread = 0) :
    ¬ H2d_SchurComplementHiddenModeClosure o := by
  intro ⟨_, _, _, _, _, _, _, h8⟩
  exact h8 h

/-- Universal falsification rule for H2c if extreme-pair sign reversal fails. -/
theorem falsify_H2c_sign (o : Cycle2Obs)
    (h : o.contrast45Mc <= 0) :
    ¬ H2c_DieTopologySignReversal o := by
  intro ⟨h1, _, _⟩
  omega

/-- Universal falsification rule for H2b if the 512 KiB -> 48 MiB cliff is weaker than 8x. -/
theorem falsify_H2b_cliff (o : Cycle2Obs)
    (h : o.pkgUj48m * o.ops512k < 8 * o.pkgUj512k * o.ops48m) :
    ¬ H2b_TwoRegimeTLBL3CliffAndDarkPower o := by
  intro ⟨h1, _, _, _, _, _⟩
  omega

end CEERSiliconCerts.Cycle2Theory

#print axioms CEERSiliconCerts.Cycle2Theory.schur_3x3_variance_identity
#print axioms CEERSiliconCerts.Cycle2Theory.schur_strict_variance_reduction
#print axioms CEERSiliconCerts.Cycle2Theory.falsify_H2d_zero_delta
#print axioms CEERSiliconCerts.Cycle2Theory.falsify_H2c_sign
#print axioms CEERSiliconCerts.Cycle2Theory.falsify_H2b_cliff
