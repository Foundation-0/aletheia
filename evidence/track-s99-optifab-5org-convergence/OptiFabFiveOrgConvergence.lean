/-
  Track S99: OptiFab 5-Organization Physical-Digital Convergence Operators
  Pure Init Lean 4.36.0 companion (zero external imports, zero Classical.choice, zero sorryAx).
  Covers:
    - Pillar 1: Exact Z-arithmetic proofs and certified repairs for optifab#14 defects 1..5
    - Pillar 2: Tri-thermal Carnot recooling ceiling, load floor, VRAM residency cliff,
                exact 2x2 Schur negative-inertia witness and Haynsworth square-completion
    - Pillar 3: Complete-graph Foster divisibility, Schur parallel-bridge strict compounding,
                exact tetrahedral Bianchi identity (delta^2 = 0), balanced silo-cut AM-GM bound
    - Pillar 4: Law-5 non-commutativity between directed upward safety distance and symmetric squared distance
-/

namespace S99OptiFabFiveOrgConvergence

/-- Directed upward difference: zero whenever candidate improves or holds baseline. -/
def posDiff (base cand : Int) : Int :=
  if base < cand then cand - base else 0

/-- P1.1: Double-subtracted outage fixed-load constant is strictly positive when auxiliary+other utility exceeds passive savings. -/
theorem defect14_1_outage_constant_positive_error
    (aux other passive loopCop : Int)
    (hDom : passive * 1000 < (aux + other) * loopCop) :
    0 < (aux + other) * loopCop - passive * 1000 := by
  omega

/-- P1.2: Double-subtracting a strictly positive constant during outages strictly understates utility energy. -/
theorem defect14_1_buggy_used_strictly_less
    (uFull uLow uShed cConst tFull tLow tOut : Int)
    (hConst : 0 < cConst)
    (hOut : 0 < tOut) :
    uFull * tFull + uLow * tLow - (uShed + cConst) * tOut <
      uFull * tFull + uLow * tLow - uShed * tOut := by
  have hProd : 0 < cConst * tOut := Int.mul_pos hConst hOut
  have hExpand : (uShed + cConst) * tOut = uShed * tOut + cConst * tOut :=
    Int.add_mul uShed cConst tOut
  omega

/-- P1.3: Omitting strictly positive fixed envelope/overhead heat strictly understates outage thermal load. -/
theorem defect14_2_fixed_heat_raises_outage_num
    (pIt shed qFix outMin : Int)
    (hFix : 0 < qFix)
    (hOut : 0 < outMin) :
    pIt * (1000000 - shed) * outMin <
      (pIt * (1000000 - shed) + qFix) * outMin := by
  have hProd : 0 < qFix * outMin := Int.mul_pos hFix hOut
  have hExpand :
      (pIt * (1000000 - shed) + qFix) * outMin =
        pIt * (1000000 - shed) * outMin + qFix * outMin :=
    Int.add_mul (pIt * (1000000 - shed)) qFix outMin
  omega

/-- P1.4: Lexicographic Pareto acceptance strictly forbids equal-objective headroom decay or stasis. -/
theorem defect14_3_lex_forbids_tie_headroom_decay
    (objB objC hrB hrC : Int)
    (hEq : objB = objC)
    (hDecay : hrC ≤ hrB) :
    ¬ (objB < objC ∨ (objB = objC ∧ hrB < hrC)) := by
  omega

/-- P1.5: WellFormedPlant guarantees non-negative outage numerator and strictly positive PCM denominator. -/
theorem defect14_4_wellformed_nonneg_outage_and_pos_den
    (pIt shed qFix outMin pcm : Int)
    (hPit : 0 < pIt)
    (hShedLo : 0 ≤ shed)
    (hShedHi : shed ≤ 1000000)
    (hFix : 0 ≤ qFix)
    (hOut : 0 < outMin)
    (hPcm : 0 < pcm) :
    0 ≤ (pIt * (1000000 - shed) + qFix) * outMin ∧ 0 < 60000000000 * pcm := by
  have hRem : 0 ≤ 1000000 - shed := by omega
  have hItTerm : 0 ≤ pIt * (1000000 - shed) := Int.mul_nonneg (by omega) hRem
  have hSum : 0 ≤ pIt * (1000000 - shed) + qFix := by omega
  have hNum : 0 ≤ (pIt * (1000000 - shed) + qFix) * outMin := Int.mul_nonneg hSum (by omega)
  have hDen : 0 < 60000000000 * pcm := Int.mul_pos (by omega) hPcm
  exact And.intro hNum hDen

/-- P1.6: Asymmetric positive-part distance bound still guarantees every admitted coordinate stays within limit. -/
theorem defect14_5_pos_dist_sq_preserves_limit
    (b c limit r : Int)
    (hR : 0 ≤ r)
    (hHr : r ≤ limit - b)
    (hDist : posDiff b c * posDiff b c ≤ r * r) :
    c ≤ limit := by
  unfold posDiff at hDist
  by_cases hLt : b < c
  · simp [hLt] at hDist
    have hDiff : 0 ≤ c - b := by omega
    by_cases hBig : r < c - b
    · have h1 : r * r ≤ r * (c - b) := Int.mul_le_mul_of_nonneg_left (by omega) hR
      have h2 : r * (c - b) < (c - b) * (c - b) := Int.mul_lt_mul_of_pos_right hBig (by omega)
      omega
    · omega
  · omega

/-- P1.7: Any purely safety-improving or neutral move has zero upward distance and is never blocked by the radius wall. -/
theorem defect14_5_pure_safety_move_zero_pos_dist
    (b c : Int)
    (hSafe : c ≤ b) :
    posDiff b c = 0 := by
  unfold posDiff
  have hNot : ¬ (b < c) := by omega
  simp [hNot]

/-- P1.8: Strict Lyapunov contraction from an out-of-limit baseline strictly decreases excess violation. -/
theorem defect14_5_lyapunov_recovery_strict_descent
    (mB mC limit : Int)
    (hOut : limit < mB)
    (hDrop : mC < mB) :
    (if limit < mC then mC - limit else 0) < mB - limit := by
  by_cases hStill : limit < mC
  · simp [hStill]
    omega
  · simp [hStill]
    omega

/-- P2.1: Cleared-denominator tri-thermal Carnot reversible COP strictly decreases as recooling temperature rises. -/
theorem pillar2_carnot_recooling_ceiling_monotone
    (tDrive tChill tRec1 tRec2 : Int)
    (hLo : tChill < tRec1)
    (hStep : tRec1 < tRec2)
    (hHi : tRec2 < tDrive) :
    (tDrive - tRec2) * (tRec1 - tChill) < (tDrive - tRec1) * (tRec2 - tChill) := by
  have hDiffPos : 0 < (tDrive - tChill) * (tRec2 - tRec1) :=
    Int.mul_pos (by omega) (by omega)
  have hIdent :
      (tDrive - tRec1) * (tRec2 - tChill) - (tDrive - tRec2) * (tRec1 - tChill) =
        (tDrive - tChill) * (tRec2 - tRec1) := by
    have e1 : (tDrive - tRec1) * (tRec2 - tChill) =
        tDrive * tRec2 - tDrive * tChill - tRec1 * tRec2 + tRec1 * tChill := by
      rw [Int.sub_mul, Int.mul_sub, Int.mul_sub]
      omega
    have e2 : (tDrive - tRec2) * (tRec1 - tChill) =
        tDrive * tRec1 - tDrive * tChill - tRec2 * tRec1 + tRec2 * tChill := by
      rw [Int.sub_mul, Int.mul_sub, Int.mul_sub]
      omega
    have e3 : (tDrive - tChill) * (tRec2 - tRec1) =
        tDrive * tRec2 - tDrive * tRec1 - tChill * tRec2 + tChill * tRec1 := by
      rw [Int.sub_mul, Int.mul_sub, Int.mul_sub]
      omega
    have c1 : tRec1 * tRec2 = tRec2 * tRec1 := Int.mul_comm tRec1 tRec2
    have c2 : tRec1 * tChill = tChill * tRec1 := Int.mul_comm tRec1 tChill
    have c3 : tRec2 * tChill = tChill * tRec2 := Int.mul_comm tRec2 tChill
    omega
  omega

/-- P2.2: Higher fixed heat load forces a strictly higher self-cooling load floor whenever a lower floor fails. -/
theorem pillar2_load_floor_monotone_in_qfix
    (q1 q2 cg f1 f2 : Int)
    (hCg : 0 < cg)
    (hQ : q1 ≤ q2)
    (hOk2 : q2 * 1000 ≤ cg * f2)
    (hFail1 : cg * f1 < q1 * 1000) :
    f1 < f2 := by
  have hProd : cg * f1 < cg * f2 := by omega
  by_cases hGe : f2 ≤ f1
  · have hRev : cg * f2 ≤ cg * f1 := Int.mul_le_mul_of_nonneg_left hGe (by omega)
    omega
  · omega

/-- P2.3: Strict separation across the GPU VRAM residency cliff b_crit = 8 * budget / params. -/
theorem pillar2_residency_cliff_split
    (bpw1 bpw2 params budget : Int)
    (hParams : 0 < params)
    (hFit : bpw1 * params ≤ budget * 8)
    (hSpill : budget * 8 < bpw2 * params) :
    bpw1 < bpw2 := by
  have hProd : bpw1 * params < bpw2 * params := by omega
  by_cases hGe : bpw2 ≤ bpw1
  · have hRev : bpw2 * params ≤ bpw1 * params := Int.mul_le_mul_of_nonneg_right hGe (by omega)
    omega
  · omega

/-- P2.4: Whenever diagonal a > 0 and Schur complement (a*d - b^2) < 0, v = (-b, a) witnesses strict quadratic negativity. -/
theorem pillar2_schur_2x2_negative_inertia_witness
    (a b d : Int)
    (hA : 0 < a)
    (hNegSchur : a * d < b * b) :
    a * (-b) * (-b) + 2 * b * (-b) * a + d * a * a < 0 := by
  have hSchurNeg : a * d - b * b < 0 := by omega
  have hProdNeg : a * (a * d - b * b) < 0 := by
    have hPos : 0 < a * (b * b - a * d) := Int.mul_pos hA (by omega)
    have hSub : a * (b * b - a * d) = a * (b * b) - a * (a * d) := Int.mul_sub a (b * b) (a * d)
    have hSub2 : a * (a * d - b * b) = a * (a * d) - a * (b * b) := Int.mul_sub a (a * d) (b * b)
    omega
  have t1 : a * (-b) * (-b) = a * (b * b) := by
    rw [Int.mul_assoc, Int.neg_mul_neg]
  have t2 : 2 * b * (-b) * a = -(2 * (a * (b * b))) := by
    have s1 : b * (-b) = -(b * b) := Int.mul_neg b b
    have s2 : 2 * b * (-b) = 2 * (b * (-b)) := Int.mul_assoc 2 b (-b)
    rw [s2, s1, Int.mul_neg, Int.neg_mul, Int.mul_comm (2 * (b * b)) a]
    have s3 : a * (2 * (b * b)) = 2 * (a * (b * b)) := by
      rw [← Int.mul_assoc, Int.mul_comm a 2, Int.mul_assoc]
    rw [s3]
  have t3 : d * a * a = a * (a * d) := by
    rw [Int.mul_assoc, Int.mul_comm d (a * a), Int.mul_assoc, Int.mul_comm a d]
  have t4 : a * (a * d - b * b) = a * (a * d) - a * (b * b) := Int.mul_sub a (a * d) (b * b)
  omega

/-- P2.5: Exact algebraic Haynsworth-Schur square-completion identity for any 2x2 symmetric block form. -/
theorem pillar2_haynsworth_square_completion
    (a b d x y : Int) :
    a * (a * x * x + 2 * b * x * y + d * y * y) =
      (a * x + b * y) * (a * x + b * y) + (a * d - b * b) * y * y := by
  have lhs : a * (a * x * x + 2 * b * x * y + d * y * y) =
      a * (a * x * x) + a * (2 * b * x * y) + a * (d * y * y) := by
    rw [Int.mul_add, Int.mul_add]
  have sq : (a * x + b * y) * (a * x + b * y) =
      (a * x) * (a * x) + (a * x) * (b * y) + (b * y) * (a * x) + (b * y) * (b * y) := by
    rw [Int.add_mul, Int.mul_add, Int.mul_add]
    omega
  have sch : (a * d - b * b) * y * y = (a * d) * y * y - (b * b) * y * y := by
    rw [Int.sub_mul, Int.sub_mul]
  have m1 : a * (a * x * x) = (a * x) * (a * x) := by
    rw [Int.mul_assoc a x x, ← Int.mul_assoc a a (x * x)]
    have h1 : (a * x) * (a * x) = a * (x * (a * x)) := Int.mul_assoc a x (a * x)
    have h2 : x * (a * x) = (x * a) * x := (Int.mul_assoc x a x).symm
    have h3 : x * a = a * x := Int.mul_comm x a
    rw [h1, h2, h3, Int.mul_assoc a a (x * x), Int.mul_assoc a x x]
  have m2 : (a * x) * (b * y) = (b * y) * (a * x) := Int.mul_comm (a * x) (b * y)
  have m3 : a * (2 * b * x * y) = (a * x) * (b * y) + (a * x) * (b * y) := by
    have h1 : 2 * b * x * y = b * x * y + b * x * y := by
      have k : 2 * b = b + b := by omega
      rw [k, Int.add_mul, Int.add_mul]
    rw [h1, Int.mul_add]
    have h2 : a * (b * x * y) = (a * x) * (b * y) := by
      rw [Int.mul_assoc b x y, Int.mul_comm b (x * y), ← Int.mul_assoc a (x * y) b]
      rw [← Int.mul_assoc a x y, Int.mul_assoc (a * x) y b, Int.mul_comm y b]
    rw [h2]
  have m4 : a * (d * y * y) = (a * d) * y * y := by
    rw [← Int.mul_assoc a (d * y) y, ← Int.mul_assoc a d y]
  have m5 : (b * y) * (b * y) = (b * b) * y * y := by
    rw [Int.mul_assoc b y (b * y), ← Int.mul_assoc y b y, Int.mul_comm y b]
    rw [Int.mul_assoc b y y, ← Int.mul_assoc b b (y * y), ← Int.mul_assoc (b * b) y y]
  omega

/-- P3.1: Exact cleared Foster identity on complete graph K_n: 2 * |E(K_n)| = n * (n - 1). -/
theorem pillar3_foster_complete_graph_cleared
    (n : Nat) :
    ((n * (n - 1)) / 2) * 2 = n * (n - 1) := by
  have hEven : (n * (n - 1)) % 2 = 0 := by
    cases n with
    | zero => simp
    | succ k =>
      have hMod : k % 2 = 0 ∨ k % 2 = 1 := by omega
      rcases hMod with h0 | h1
      · have hk : k = 2 * (k / 2) := by omega
        have hEq : (k + 1) * k = 2 * ((k + 1) * (k / 2)) := by
          have s1 : (k + 1) * k = (k + 1) * (2 * (k / 2)) := congrArg ((k + 1) * ·) hk
          rw [s1, ← Nat.mul_assoc, Nat.mul_comm (k + 1) 2, Nat.mul_assoc]
        simp only [Nat.add_sub_cancel]
        rw [hEq]
        omega
      · have hk : k + 1 = 2 * ((k + 1) / 2) := by omega
        have hEq : (k + 1) * k = 2 * (((k + 1) / 2) * k) := by
          have s1 : (k + 1) * k = (2 * ((k + 1) / 2)) * k := congrArg (· * k) hk
          rw [s1, Nat.mul_assoc]
        simp only [Nat.add_sub_cancel]
        rw [hEq]
        omega
  omega

/-- P3.2: Schur parallel-bridge compounding strictly increases effective conductance over any direct edge. -/
theorem pillar3_schur_compounding_strict_gain
    (cDir cA cB : Int)
    (hA : 0 < cA)
    (hB : 0 < cB) :
    cDir * (cA + cB) < cDir * (cA + cB) + cA * cB := by
  have hProd : 0 < cA * cB := Int.mul_pos hA hB
  omega

/-- P3.3: Universal exact tetrahedral Bianchi identity (delta^2 = 0) for any 1-cochain on any 4-simplex. -/
theorem pillar3_tetrahedral_bianchi_exact_zero
    (w01 w02 w03 w12 w13 w23 : Int) :
    ((w12 + w23 - w13) - (w02 + w23 - w03) + (w01 + w13 - w03) - (w01 + w12 - w02)) = 0 := by
  omega

/-- P3.4: Exact AM-GM balanced silo-cut bound: 4*p*d <= (p+d)^2 with equality at the 4|4 Physical-Digital cut. -/
theorem pillar3_silo_cut_am_gm_bound
    (p d : Int) :
    4 * (p * d) ≤ (p + d) * (p + d) := by
  have hSq : 0 ≤ (p - d) * (p - d) := by
    by_cases h : 0 ≤ p - d
    · exact Int.mul_nonneg h h
    · have hNeg : 0 ≤ -(p - d) := by omega
      have hPos : 0 ≤ (-(p - d)) * (-(p - d)) := Int.mul_nonneg hNeg hNeg
      rw [Int.neg_mul_neg] at hPos
      exact hPos
  have e1 : (p + d) * (p + d) = p * p + p * d + d * p + d * d := by
    rw [Int.add_mul, Int.mul_add, Int.mul_add]
    omega
  have e2 : (p - d) * (p - d) = p * p - p * d - d * p + d * d := by
    rw [Int.sub_mul, Int.mul_sub, Int.mul_sub]
    omega
  have hc : d * p = p * d := Int.mul_comm d p
  omega

/-- P4.1: Law-5 non-commutativity: any strict safety improvement has strictly smaller upward distance than symmetric squared distance. -/
theorem pillar4_law5_non_commutativity_pos_vs_sym
    (b c : Int)
    (hImp : c < b) :
    posDiff b c < (c - b) * (c - b) := by
  unfold posDiff
  have hNot : ¬ (b < c) := by omega
  simp [hNot]
  have hPos : 0 < b - c := by omega
  have hSq : 0 < (b - c) * (b - c) := Int.mul_pos hPos hPos
  have hFlip : (c - b) * (c - b) = (b - c) * (b - c) := by
    have hNeg : c - b = -(b - c) := by omega
    rw [hNeg, Int.neg_mul_neg]
  omega

end S99OptiFabFiveOrgConvergence
