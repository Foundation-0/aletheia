/-
  CEERFoundations.Module1_UniversalHysteresisAndConcavity
  Track S62c — Pure-Init Lean 4.36.0 Universal Foundations for CEER:
  1. Universal Zero-Area Memoryless-Loop Theorem (for ALL g : Int -> Int)
     & Unconditional Hysteresis Refutation Corollary.
  2. Universal Affine Closed-Loop Zero-Area & Collinearity / Concavity Refutation.
  3. Universal Lipschitz Phase-Cliff Refutation Lemma.
  4. Constructive Concrete CEER Cycle Witnesses (non-vacuous disproofs).
  Zero Mathlib, zero sorry/admit/axiom, zero native_decide, zero external imports.
-/

namespace CEERFoundations.Module1

/-- Exact integer discrete Green's-theorem trapezoid signed area (2x signed area):
    sum_i (y_{i+1} + y_i) * (x_{i+1} - x_i). -/
def pathArea : List (Int × Int) → Int
  | [] => 0
  | [_] => 0
  | p :: q :: rest =>
      (q.2 + p.2) * (q.1 - p.1) + pathArea (q :: rest)

/-- Graph trajectory obtained by evaluating a single-valued memoryless law g : Int -> Int. -/
def graphPath (g : Int → Int) (xs : List Int) : List (Int × Int) :=
  xs.map (fun x => (x, g x))

/-- Symmetric up-then-down closed lever sweep: [x0, ..., xk, xk, ..., x0]. -/
def symSweep (xs : List Int) : List Int :=
  xs ++ xs.reverse

/-- Exact integer L-Lipschitz predicate on f : Int -> Int. -/
def IsLipschitz (L : Int) (f : Int → Int) : Prop :=
  ∀ x y : Int, (Int.natAbs (f y - f x) : Int) ≤ L * (Int.natAbs (y - x) : Int)

private theorem seg_reverse_neg (p q : Int × Int) :
    (p.2 + q.2) * (p.1 - q.1) = -((q.2 + p.2) * (q.1 - p.1)) := by
  have h1 : p.2 + q.2 = q.2 + p.2 := Int.add_comm p.2 q.2
  have h2 : p.1 - q.1 = -(q.1 - p.1) := by omega
  rw [h1, h2, Int.mul_neg]

private theorem pathArea_append_two (ps : List (Int × Int)) (p q : Int × Int) :
    pathArea (ps ++ [p, q]) = pathArea (ps ++ [p]) + (q.2 + p.2) * (q.1 - p.1) := by
  induction ps with
  | nil =>
      simp [pathArea]
  | cons a rest ih =>
      cases rest with
      | nil =>
          simp only [List.cons_append, List.nil_append, pathArea]
          omega
      | cons b bs =>
          simp only [List.cons_append, pathArea] at ih ⊢
          omega

private theorem pathArea_append_self_join (ps qs : List (Int × Int)) (p : Int × Int) :
    pathArea (ps ++ p :: p :: qs) = pathArea (ps ++ [p]) + pathArea (p :: qs) := by
  induction ps with
  | nil =>
      simp only [List.nil_append, pathArea]
      have hz : (p.2 + p.2) * (p.1 - p.1) = 0 := by
        have h0 : p.1 - p.1 = 0 := by omega
        rw [h0, Int.mul_zero]
      omega
  | cons a rest ih =>
      cases rest with
      | nil =>
          simp only [List.cons_append, List.nil_append, pathArea] at ih ⊢
          have hz : (p.2 + p.2) * (p.1 - p.1) = 0 := by
            have h0 : p.1 - p.1 = 0 := by omega
            rw [h0, Int.mul_zero]
          omega
      | cons b bs =>
          simp only [List.cons_append, pathArea] at ih ⊢
          omega

private theorem pathArea_reverse_neg :
    ∀ ps : List (Int × Int), pathArea ps.reverse = -pathArea ps
  | [] => by simp [pathArea]
  | [_] => by simp [pathArea]
  | p :: q :: rest => by
      have ih := pathArea_reverse_neg (q :: rest)
      have hrev : (p :: q :: rest).reverse = rest.reverse ++ [q, p] := by
        simp [List.reverse_cons, List.append_assoc]
      have hrev2 : (q :: rest).reverse = rest.reverse ++ [q] := by
        simp [List.reverse_cons]
      rw [hrev, pathArea_append_two, ← hrev2, ih]
      simp only [pathArea]
      have hseg := seg_reverse_neg p q
      omega

private theorem pathArea_sym_pairs :
    ∀ ps : List (Int × Int), pathArea (ps ++ ps.reverse) = 0
  | [] => by simp [pathArea]
  | p :: rest => by
      have hne : (p :: rest).reverse ≠ [] := by simp
      have hsplit : ∃ mid init, p :: rest = init ++ [mid] := by
        cases hrev : (p :: rest).reverse with
        | nil => exact False.elim (hne hrev)
        | cons mid tail =>
            refine ⟨mid, tail.reverse, ?_⟩
            have h2 := congrArg List.reverse hrev
            rw [List.reverse_reverse, List.reverse_cons] at h2
            exact h2
      rcases hsplit with ⟨mid, init, hEq⟩
      have hrev : (p :: rest).reverse = mid :: init.reverse := by
        rw [hEq, List.reverse_append]
        simp
      rw [hEq]
      have h2 : (init ++ [mid]) ++ (init ++ [mid]).reverse =
          init ++ mid :: mid :: init.reverse := by
        rw [List.reverse_append]
        simp [List.append_assoc]
      rw [h2, pathArea_append_self_join]
      have h3 : mid :: init.reverse = (init ++ [mid]).reverse := by
        rw [List.reverse_append]
        simp
      rw [h3, pathArea_reverse_neg]
      omega

private theorem graphPath_symSweep (g : Int → Int) (xs : List Int) :
    graphPath g (symSweep xs) = graphPath g xs ++ (graphPath g xs).reverse := by
  simp [graphPath, symSweep, List.map_append, List.map_reverse]

/-- Theorem 1.1 (Universal): Zero-Area Memoryless-Loop Theorem.
    For EVERY single-valued function g : Int -> Int and EVERY lever trajectory xs : List Int,
    the exact integer trapezoid signed area on the symmetric up-down sweep is identically 0. -/
theorem memoryless_symmetric_loop_zero_area (g : Int → Int) (xs : List Int) :
    pathArea (graphPath g (symSweep xs)) = 0 := by
  rw [graphPath_symSweep]
  exact pathArea_sym_pairs (graphPath g xs)

private theorem zip_map_eq_graphPath (g : Int → Int) :
    ∀ xs : List Int, List.zip xs (xs.map g) = graphPath g xs
  | [] => rfl
  | x :: rest => by
      simp only [List.map, List.zip, List.zipWith, graphPath]
      exact congrArg (List.cons (x, g x)) (zip_map_eq_graphPath g rest)

/-- Theorem 1.2 (Universal): Unconditional Hysteresis Refutation Corollary.
    ANY symmetric lever-sweep sensor trace with nonzero integer signed area unconditionally
    disproves ALL single-valued memoryless functions g : Int -> Int. -/
theorem hysteresis_disproves_all_single_valued
    (xs ys : List Int)
    (harea : pathArea (List.zip (symSweep xs) ys) ≠ 0) :
    ¬ (∃ g : Int → Int, ys = (symSweep xs).map g) := by
  intro hex
  rcases hex with ⟨g, hg⟩
  rw [hg, zip_map_eq_graphPath] at harea
  exact harea (memoryless_symmetric_loop_zero_area g xs)

private theorem affine_trapezoid_telescope (a b : Int) :
    ∀ (x0 : Int) (xs : List Int) (xLast : Int),
      pathArea (graphPath (fun x => a + b * x) (x0 :: xs ++ [xLast])) =
        2 * a * (xLast - x0) + b * (xLast * xLast - x0 * x0)
  | x0, [], xLast => by
      change (a + b * xLast + (a + b * x0)) * (xLast - x0) + 0 =
        2 * a * (xLast - x0) + b * (xLast * xLast - x0 * x0)
      have h1 : (a + b * xLast + (a + b * x0)) * (xLast - x0) =
          (2 * a) * (xLast - x0) + b * (xLast + x0) * (xLast - x0) := by
        have hadd : a + b * xLast + (a + b * x0) = 2 * a + b * (xLast + x0) := by
          rw [Int.mul_add]
          omega
        rw [hadd, Int.add_mul]
      have h2 : (xLast + x0) * (xLast - x0) = xLast * xLast - x0 * x0 := by
        rw [Int.add_mul, Int.mul_sub, Int.mul_sub]
        have hc : x0 * xLast = xLast * x0 := Int.mul_comm x0 xLast
        omega
      have h3 : b * (xLast + x0) * (xLast - x0) = b * (xLast * xLast - x0 * x0) := by
        rw [Int.mul_assoc b (xLast + x0) (xLast - x0), h2]
      rw [h1, h3]
      omega
  | x0, x1 :: rest, xLast => by
      have ih := affine_trapezoid_telescope a b x1 rest xLast
      simp only [List.cons_append, graphPath, List.map, pathArea] at ih ⊢
      have hstep : (a + b * x1 + (a + b * x0)) * (x1 - x0) =
          2 * a * (x1 - x0) + b * (x1 * x1 - x0 * x0) := by
        have hadd : a + b * x1 + (a + b * x0) = 2 * a + b * (x1 + x0) := by
          rw [Int.mul_add]
          omega
        have hsq : (x1 + x0) * (x1 - x0) = x1 * x1 - x0 * x0 := by
          rw [Int.add_mul, Int.mul_sub, Int.mul_sub]
          have hc : x0 * x1 = x1 * x0 := Int.mul_comm x0 x1
          omega
        rw [hadd, Int.add_mul, Int.mul_assoc b (x1 + x0) (x1 - x0), hsq]
      have ha1 : 2 * a * (x1 - x0) + 2 * a * (xLast - x1) = 2 * a * (xLast - x0) := by
        rw [← Int.mul_add]
        have hsub : (x1 - x0) + (xLast - x1) = xLast - x0 := by omega
        rw [hsub]
      have hb1 : b * (x1 * x1 - x0 * x0) + b * (xLast * xLast - x1 * x1) =
          b * (xLast * xLast - x0 * x0) := by
        rw [← Int.mul_add]
        have hsub : (x1 * x1 - x0 * x0) + (xLast * xLast - x1 * x1) =
            xLast * xLast - x0 * x0 := by omega
        rw [hsub]
      rw [hstep, ih]
      omega

/-- Theorem 1.3 (Universal): Every affine law g(x) = a + b*x has identically zero trapezoid
    signed area around EVERY closed loop (even on arbitrary non-symmetric lever grids). -/
theorem affine_arbitrary_closed_loop_zero_area (a b x0 : Int) (xs : List Int) :
    pathArea (graphPath (fun x => a + b * x) (x0 :: xs ++ [x0])) = 0 := by
  rw [affine_trapezoid_telescope a b x0 xs x0]
  have h1 : x0 - x0 = 0 := by omega
  have h2 : x0 * x0 - x0 * x0 = 0 := by omega
  rw [h1, h2, Int.mul_zero, Int.mul_zero]
  omega

/-- Theorem 1.4 (Universal): Every affine law satisfies exact vanishing second difference
    on equally spaced triples p1 + p3 = 2 * p2. -/
theorem affine_vanishing_second_diff (a b p1 p2 p3 : Int) (heq : p1 + p3 = 2 * p2) :
    (a + b * p1) + (a + b * p3) = 2 * (a + b * p2) := by
  have h1 : b * p1 + b * p3 = b * (2 * p2) := by
    rw [← Int.mul_add, heq]
  have h2 : b * (2 * p2) = 2 * (b * p2) := by
    rw [← Int.mul_assoc, Int.mul_comm b 2, Int.mul_assoc]
  omega

/-- Theorem 1.5 (Universal): Every affine law satisfies exact cross-multiplied slope equality
    across arbitrary (non-uniform) triples (p1, p2, p3). -/
theorem affine_general_collinearity (a b p1 p2 p3 : Int) :
    ((a + b * p2) - (a + b * p1)) * (p3 - p2) =
      ((a + b * p3) - (a + b * p2)) * (p2 - p1) := by
  have h1 : (a + b * p2) - (a + b * p1) = b * (p2 - p1) := by
    rw [Int.mul_sub]
    omega
  have h2 : (a + b * p3) - (a + b * p2) = b * (p3 - p2) := by
    rw [Int.mul_sub]
    omega
  rw [h1, h2, Int.mul_assoc, Int.mul_assoc, Int.mul_comm (p2 - p1) (p3 - p2)]

/-- Theorem 1.6 (Universal): Unconditional Affine-Scaling Refutation Lemma.
    Any three non-collinear integer sensor measurements unconditionally disprove ALL
    affine scaling laws P(p) = a + b * p over Z. -/
theorem noncollinear_disproves_all_affine (p1 p2 p3 y1 y2 y3 : Int)
    (hne : (y2 - y1) * (p3 - p2) ≠ (y3 - y2) * (p2 - p1)) :
    ¬ (∃ a b : Int, y1 = a + b * p1 ∧ y2 = a + b * p2 ∧ y3 = a + b * p3) := by
  intro hex
  rcases hex with ⟨a, b, h1, h2, h3⟩
  rw [h1, h2, h3] at hne
  exact hne (affine_general_collinearity a b p1 p2 p3)

/-- Theorem 1.7 (Universal): Unconditional Lipschitz Phase-Cliff Refutation Lemma.
    A single two-point integer jump exceeding L * |s2 - s1| unconditionally refutes
    ALL L-Lipschitz energy-per-op laws f : Int -> Int. -/
theorem lipschitz_cliff_disproves_all_L (L s1 s2 e1 e2 : Int)
    (hjump : (Int.natAbs (e2 - e1) : Int) > L * (Int.natAbs (s2 - s1) : Int)) :
    ¬ (∃ f : Int → Int, IsLipschitz L f ∧ f s1 = e1 ∧ f s2 = e2) := by
  intro hex
  rcases hex with ⟨f, hlip, hs1, hs2⟩
  have hbound := hlip s1 s2
  rw [hs1, hs2] at hbound
  omega

/-- Concrete CEER Cycle 0-2 integer witnesses demonstrating non-vacuous universal refutations. -/
def thermalSweepX : List Int := [15, 25, 35, 45]
def thermalLoopY : List Int := [48, 56, 65, 75, 75, 69, 62, 53]

/-- Theorem 1.8 (Concrete): Non-vacuous CEER witness bundle proving:
    (a) thermalLoopY has signed area -250 != 0 -> refutes ALL single-valued g : Int -> Int;
    (b) concave power trace (15,150), (30,270), (45,340) -> refutes ALL affine laws;
    (c) L3->DRAM jump (16,120) -> (24,480) -> refutes ALL 40-Lipschitz laws. -/
theorem ceer_cycle_hysteresis_concavity_cliff_witnesses :
    pathArea (List.zip (symSweep thermalSweepX) thermalLoopY) = -250 ∧
    ¬ (∃ g : Int → Int, thermalLoopY = (symSweep thermalSweepX).map g) ∧
    ¬ (∃ a b : Int, (150 : Int) = a + b * 15 ∧ (270 : Int) = a + b * 30 ∧ (340 : Int) = a + b * 45) ∧
    ¬ (∃ f : Int → Int, IsLipschitz 40 f ∧ f 16 = 120 ∧ f 24 = 480) := by
  refine ⟨by decide, ?_, ?_, ?_⟩
  · exact hysteresis_disproves_all_single_valued thermalSweepX thermalLoopY (by decide)
  · exact noncollinear_disproves_all_affine 15 30 45 150 270 340 (by decide)
  · exact lipschitz_cliff_disproves_all_L 40 16 24 120 480 (by decide)

end CEERFoundations.Module1

#print axioms CEERFoundations.Module1.memoryless_symmetric_loop_zero_area
#print axioms CEERFoundations.Module1.hysteresis_disproves_all_single_valued
#print axioms CEERFoundations.Module1.affine_arbitrary_closed_loop_zero_area
#print axioms CEERFoundations.Module1.affine_vanishing_second_diff
#print axioms CEERFoundations.Module1.affine_general_collinearity
#print axioms CEERFoundations.Module1.noncollinear_disproves_all_affine
#print axioms CEERFoundations.Module1.lipschitz_cliff_disproves_all_L
#print axioms CEERFoundations.Module1.ceer_cycle_hysteresis_concavity_cliff_witnesses
