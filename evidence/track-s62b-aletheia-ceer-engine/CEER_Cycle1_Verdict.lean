/- Auto-synthesized pure-Init Lean 4.36.0 CEER Cycle 1 Certificate (T1_CONCAVE_SCHUR_SINGLE_BRANCH) -/
namespace CEERCycle1

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

theorem cycle_1_h1_concave_power : secondDiff (3 : Int) (6 : Int) (8 : Int) (27600 : Int) (38900 : Int) (43800 : Int) < 0 := by decide
theorem cycle_1_h1_schur_dark_coupling : (2394291839882074 : Int) >= (1198444136342720 : Int) := by decide
theorem cycle_1_h1_zero_hysteresis : Not (twiceLoopArea [(65000, 2800), (74000, 3300), (81000, 3950), (88000, 4600), (81000, 4350), (74000, 3750)] = 0) := by decide

end CEERCycle1

#print axioms CEERCycle1.cycle_1_h1_concave_power
#print axioms CEERCycle1.cycle_1_h1_schur_dark_coupling
#print axioms CEERCycle1.cycle_1_h1_zero_hysteresis
