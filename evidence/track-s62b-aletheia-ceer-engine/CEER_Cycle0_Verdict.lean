/- Auto-synthesized pure-Init Lean 4.36.0 CEER Cycle 0 Certificate (T0_LINEAR_SINGLE_VALUED) -/
namespace CEERCycle0

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

theorem cycle_0_h0_linear_core : Not ((184000 : Int) <= (36000 : Int)) := by decide
theorem cycle_0_h0_flat_dark_mode : Not ((228315264350296720 : Int) <= (22832393395803255 : Int)) := by decide
theorem cycle_0_h0_zero_hysteresis : Not (twiceLoopArea [(54000, 2100), (64000, 2600), (76000, 3400), (83000, 4100), (76000, 3850), (64000, 3150)] = 0) := by decide

end CEERCycle0

#print axioms CEERCycle0.cycle_0_h0_linear_core
#print axioms CEERCycle0.cycle_0_h0_flat_dark_mode
#print axioms CEERCycle0.cycle_0_h0_zero_hysteresis
