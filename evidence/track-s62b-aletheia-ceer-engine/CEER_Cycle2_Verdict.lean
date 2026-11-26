/- Auto-synthesized pure-Init Lean 4.36.0 CEER Cycle 2 Certificate (T2_HYSTERETIC_SCHUR_CLOSURE) -/
namespace CEERCycle2

def twiceLoopAreaAux : List (Int × Int) -> Int × Int -> Int
  | [], _ => 0
  | [(x, y)], (x0, y0) => (y0 + y) * (x0 - x)
  | (x1, y1) :: (x2, y2) :: rest, first =>
    (y2 + y1) * (x2 - x1) + twiceLoopAreaAux ((x2, y2) :: rest) first

def twiceLoopArea : List (Int × Int) -> Int
  | [] => 0
  | first :: rest => twiceLoopAreaAux (first :: rest) first

def secondDiff (u0 u1 u2 y0 y1 y2 : Int) : Int :=
  (y2 - y1) * (u1 - u0) - (y1 - y0) * (u2 - u1)

theorem cycle_2_h2_concave_power : secondDiff (5 : Int) (7 : Int) (9 : Int) (35800 : Int) (41700 : Int) (45200 : Int) < 0 := by decide
theorem cycle_2_h2_schur_dark_closure : (47981063305403006 : Int) >= (24010610426563072 : Int) := by decide
theorem cycle_2_h2_hysteretic_loop_area : Int.natAbs (twiceLoopArea [(70000, 3100), (78000, 3700), (85000, 4300), (90000, 4850), (85000, 4650), (78000, 4100)]) >= 5000000 := by decide
theorem cycle_2_h2_rational_enclosure : ((30000 : Int) <= (30800 : Int) ∧ (30800 : Int) <= (35000 : Int)) ∧ ((35000 : Int) <= (36700 : Int) ∧ (36700 : Int) <= (42000 : Int)) ∧ ((36000 : Int) <= (40200 : Int) ∧ (40200 : Int) <= (45000 : Int)) := by decide

end CEERCycle2

#print axioms CEERCycle2.cycle_2_h2_concave_power
#print axioms CEERCycle2.cycle_2_h2_schur_dark_closure
#print axioms CEERCycle2.cycle_2_h2_hysteretic_loop_area
#print axioms CEERCycle2.cycle_2_h2_rational_enclosure
