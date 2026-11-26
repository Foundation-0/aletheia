/-
  Track S48 — Theorem 5 (Portal 57 / Tracks S41 & S44):
  1. Pólya (1913) Permanent-to-Determinant Sign-Flip Obstruction for n = 3:
       - Universal theorem: ∀ S : Fin 3 → Fin 3 → Bool, ¬ IsPolyaSignMatrix S
         (proved algebraically by testing the 6 permutation matrices and multiplying:
          LHS = ∏ (s_ij)^2 = +1 ≠ -1 = ∏ sgn(σ)).
       - Exhaustive 512 sign-matrix verification matching Track S41:
         exactly 0/512 sign matrices match all 6 permutations, max matches = 5/6 (attained).
  2. `hodge.computer` Symmetric Sextic Mod-5 Smoothness (Track S44):
       Cleared integral sextic 7*F(X0,X1,X2,Y0,Y1,Y2) = 7*∑ Z_k^6 + 5*Q_X^2*Q_Y + 10*Q_X*Q_Y^2
       satisfies 7*F ≡ 2*∑ Z_k^6 (mod 5) and ∂(7F)/∂Z_k ≡ 2*Z_k^5 (mod 5) identically,
       proving universal projective smoothness in P^5(F_5): all 6 Jacobian partials vanish
       mod 5 iff Z_0 ≡ ... ≡ Z_5 ≡ 0 (mod 5) (origin only).
-/

namespace AletheiaKernelCerts.Theorem5

/-! ### Part 1: Pólya (1913) 3x3 Sign-Matrix Impossibility (0/512) -/

/-- Sign map Bool → {-1, +1}. -/
def signVal (b : Bool) : Int :=
  if b then 1 else -1

/-- Exact 3x3 permanent over Int. -/
def perm3 (A : Fin 3 → Fin 3 → Int) : Int :=
  A 0 0 * A 1 1 * A 2 2 +
  A 0 1 * A 1 2 * A 2 0 +
  A 0 2 * A 1 0 * A 2 1 +
  A 0 0 * A 1 2 * A 2 1 +
  A 0 1 * A 1 0 * A 2 2 +
  A 0 2 * A 1 1 * A 2 0

/-- Exact 3x3 determinant over Int. -/
def det3 (A : Fin 3 → Fin 3 → Int) : Int :=
  A 0 0 * A 1 1 * A 2 2 +
  A 0 1 * A 1 2 * A 2 0 +
  A 0 2 * A 1 0 * A 2 1 -
  A 0 0 * A 1 2 * A 2 1 -
  A 0 1 * A 1 0 * A 2 2 -
  A 0 2 * A 1 1 * A 2 0

/-- Entrywise sign-flip action S ⊙ A. -/
def applySign3 (S : Fin 3 → Fin 3 → Bool) (A : Fin 3 → Fin 3 → Int) : Fin 3 → Fin 3 → Int :=
  fun i j => signVal (S i j) * A i j

/-- Pólya sign-matrix predicate: perm_3(A) = det_3(S ⊙ A) for ALL integer 3x3 matrices A. -/
def IsPolyaSignMatrix (S : Fin 3 → Fin 3 → Bool) : Prop :=
  ∀ A : Fin 3 → Fin 3 → Int, perm3 A = det3 (applySign3 S A)

/-- Permutation matrix P_σ associated with a permutation σ : Fin 3 → Fin 3. -/
def permMat (σ : Fin 3 → Fin 3) : Fin 3 → Fin 3 → Int :=
  fun i j => if j == σ i then 1 else 0

private def pId (i : Fin 3) : Fin 3 :=
  if i.val == 0 then 0 else if i.val == 1 then 1 else 2

private def pCyc1 (i : Fin 3) : Fin 3 :=
  if i.val == 0 then 1 else if i.val == 1 then 2 else 0

private def pCyc2 (i : Fin 3) : Fin 3 :=
  if i.val == 0 then 2 else if i.val == 1 then 0 else 1

private def pSwap12 (i : Fin 3) : Fin 3 :=
  if i.val == 0 then 0 else if i.val == 1 then 2 else 1

private def pSwap01 (i : Fin 3) : Fin 3 :=
  if i.val == 0 then 1 else if i.val == 1 then 0 else 2

private def pSwap02 (i : Fin 3) : Fin 3 :=
  if i.val == 0 then 2 else if i.val == 1 then 1 else 0

private theorem eval_perm_det_id (S : Fin 3 → Fin 3 → Bool) :
    perm3 (permMat pId) = 1 ∧
    det3 (applySign3 S (permMat pId)) = signVal (S 0 0) * signVal (S 1 1) * signVal (S 2 2) := by
  unfold perm3 det3 applySign3 permMat pId
  simp

private theorem eval_perm_det_cyc1 (S : Fin 3 → Fin 3 → Bool) :
    perm3 (permMat pCyc1) = 1 ∧
    det3 (applySign3 S (permMat pCyc1)) = signVal (S 0 1) * signVal (S 1 2) * signVal (S 2 0) := by
  unfold perm3 det3 applySign3 permMat pCyc1
  simp

private theorem eval_perm_det_cyc2 (S : Fin 3 → Fin 3 → Bool) :
    perm3 (permMat pCyc2) = 1 ∧
    det3 (applySign3 S (permMat pCyc2)) = signVal (S 0 2) * signVal (S 1 0) * signVal (S 2 1) := by
  unfold perm3 det3 applySign3 permMat pCyc2
  simp

private theorem eval_perm_det_swap12 (S : Fin 3 → Fin 3 → Bool) :
    perm3 (permMat pSwap12) = 1 ∧
    det3 (applySign3 S (permMat pSwap12)) = -(signVal (S 0 0) * signVal (S 1 2) * signVal (S 2 1)) := by
  unfold perm3 det3 applySign3 permMat pSwap12
  simp

private theorem eval_perm_det_swap01 (S : Fin 3 → Fin 3 → Bool) :
    perm3 (permMat pSwap01) = 1 ∧
    det3 (applySign3 S (permMat pSwap01)) = -(signVal (S 0 1) * signVal (S 1 0) * signVal (S 2 2)) := by
  unfold perm3 det3 applySign3 permMat pSwap01
  simp

private theorem eval_perm_det_swap02 (S : Fin 3 → Fin 3 → Bool) :
    perm3 (permMat pSwap02) = 1 ∧
    det3 (applySign3 S (permMat pSwap02)) = -(signVal (S 0 2) * signVal (S 1 1) * signVal (S 2 0)) := by
  unfold perm3 det3 applySign3 permMat pSwap02
  simp

/-- Universal Pólya (1913) obstruction: NO 3x3 sign matrix converts det_3 into perm_3. -/
theorem polya_no_3x3_sign_matrix :
    ∀ S : Fin 3 → Fin 3 → Bool, ¬ IsPolyaSignMatrix S := by
  intro S hS
  have h1 := hS (permMat pId)
  have h2 := hS (permMat pCyc1)
  have h3 := hS (permMat pCyc2)
  have h4 := hS (permMat pSwap12)
  have h5 := hS (permMat pSwap01)
  have h6 := hS (permMat pSwap02)
  rw [(eval_perm_det_id S).1, (eval_perm_det_id S).2] at h1
  rw [(eval_perm_det_cyc1 S).1, (eval_perm_det_cyc1 S).2] at h2
  rw [(eval_perm_det_cyc2 S).1, (eval_perm_det_cyc2 S).2] at h3
  rw [(eval_perm_det_swap12 S).1, (eval_perm_det_swap12 S).2] at h4
  rw [(eval_perm_det_swap01 S).1, (eval_perm_det_swap01 S).2] at h5
  rw [(eval_perm_det_swap02 S).1, (eval_perm_det_swap02 S).2] at h6
  have hprod :
      (signVal (S 0 0) * signVal (S 1 1) * signVal (S 2 2)) *
      (signVal (S 0 1) * signVal (S 1 2) * signVal (S 2 0)) *
      (signVal (S 0 2) * signVal (S 1 0) * signVal (S 2 1)) *
      (-(signVal (S 0 0) * signVal (S 1 2) * signVal (S 2 1))) *
      (-(signVal (S 0 1) * signVal (S 1 0) * signVal (S 2 2))) *
      (-(signVal (S 0 2) * signVal (S 1 1) * signVal (S 2 0))) = 1 := by
    rw [← h1, ← h2, ← h3, ← h4, ← h5, ← h6]
    decide
  have hparity : ∀ (a00 a01 a02 a10 a11 a12 a20 a21 a22 : Bool),
      (signVal a00 * signVal a11 * signVal a22) *
      (signVal a01 * signVal a12 * signVal a20) *
      (signVal a02 * signVal a10 * signVal a21) *
      (-(signVal a00 * signVal a12 * signVal a21)) *
      (-(signVal a01 * signVal a10 * signVal a22)) *
      (-(signVal a02 * signVal a11 * signVal a20)) = -1 := by
    decide
  have hneg1 := hparity (S 0 0) (S 0 1) (S 0 2) (S 1 0) (S 1 1) (S 1 2) (S 2 0) (S 2 1) (S 2 2)
  rw [hneg1] at hprod
  omega

/-- Count how many of the 6 permutations in S_3 are matched by a 3x3 sign matrix over Bool^9. -/
def matchedPerms9 (a00 a01 a02 a10 a11 a12 a20 a21 a22 : Bool) : Nat :=
  let b1 := (signVal a00 * signVal a11 * signVal a22) == 1
  let b2 := (signVal a01 * signVal a12 * signVal a20) == 1
  let b3 := (signVal a02 * signVal a10 * signVal a21) == 1
  let b4 := (-(signVal a00 * signVal a12 * signVal a21)) == 1
  let b5 := (-(signVal a01 * signVal a10 * signVal a22)) == 1
  let b6 := (-(signVal a02 * signVal a11 * signVal a20)) == 1
  (if b1 then 1 else 0) + (if b2 then 1 else 0) + (if b3 then 1 else 0) +
  (if b4 then 1 else 0) + (if b5 then 1 else 0) + (if b6 then 1 else 0)

/-- Depth-9 binary census over all 2^9 = 512 sign matrices (zero deep recursion). -/
def countOverBools9 (p : Bool → Bool → Bool → Bool → Bool → Bool → Bool → Bool → Bool → Bool) : Nat :=
  let sum1 (f : Bool → Nat) : Nat := f false + f true
  sum1 fun a00 => sum1 fun a01 => sum1 fun a02 =>
  sum1 fun a10 => sum1 fun a11 => sum1 fun a12 =>
  sum1 fun a20 => sum1 fun a21 => sum1 fun a22 =>
    if p a00 a01 a02 a10 a11 a12 a20 a21 a22 then 1 else 0

/-- Exact Track S41 exhaustive census: 0 of 512 sign matrices match all 6 permutations, max is 5/6. -/
theorem polya_512_zero_valid_and_max_5 :
    countOverBools9 (fun _ _ _ _ _ _ _ _ _ => true) = 512 ∧
    countOverBools9 (fun a00 a01 a02 a10 a11 a12 a20 a21 a22 =>
      matchedPerms9 a00 a01 a02 a10 a11 a12 a20 a21 a22 == 6) = 0 ∧
    (∀ a00 a01 a02 a10 a11 a12 a20 a21 a22 : Bool,
      matchedPerms9 a00 a01 a02 a10 a11 a12 a20 a21 a22 ≤ 5) ∧
    matchedPerms9 true true true false true true true false true = 5 := by
  decide

/-! ### Part 2: `hodge.computer` Symmetric Sextic Mod-5 Smoothness (Track S44) -/

/-- Exact cleared integral sextic 7*F(X0,X1,X2,Y0,Y1,Y2) = 7*∑ Z_k^6 + 5*Q_X^2*Q_Y + 10*Q_X*Q_Y^2. -/
def hodgeSextic7F (z : Fin 6 → Int) : Int :=
  let x0 := z 0; let x1 := z 1; let x2 := z 2
  let y0 := z 3; let y1 := z 4; let y2 := z 5
  let qx := x0 * x1 + x0 * x2 + x1 * x2
  let qy := y0 * y1 + y0 * y2 + y1 * y2
  7 * (x0 ^ 6 + x1 ^ 6 + x2 ^ 6 + y0 ^ 6 + y1 ^ 6 + y2 ^ 6) +
  5 * (qx * qx * qy) + 10 * (qx * qy * qy)

/-- Exact algebraic partial derivative ∂(7F)/∂Z_k over Int. -/
def hodgeSextic7FPartial (k : Fin 6) (z : Fin 6 → Int) : Int :=
  let x0 := z 0; let x1 := z 1; let x2 := z 2
  let y0 := z 3; let y1 := z 4; let y2 := z 5
  let qx := x0 * x1 + x0 * x2 + x1 * x2
  let qy := y0 * y1 + y0 * y2 + y1 * y2
  match k.val with
  | 0 => 42 * (x0 ^ 5) + 5 * (2 * qx * (x1 + x2) * qy + 2 * (x1 + x2) * qy * qy)
  | 1 => 42 * (x1 ^ 5) + 5 * (2 * qx * (x0 + x2) * qy + 2 * (x0 + x2) * qy * qy)
  | 2 => 42 * (x2 ^ 5) + 5 * (2 * qx * (x0 + x1) * qy + 2 * (x0 + x1) * qy * qy)
  | 3 => 42 * (y0 ^ 5) + 5 * (qx * qx * (y1 + y2) + 4 * qx * qy * (y1 + y2))
  | 4 => 42 * (y1 ^ 5) + 5 * (qx * qx * (y0 + y2) + 4 * qx * qy * (y0 + y2))
  | _ => 42 * (y2 ^ 5) + 5 * (qx * qx * (y0 + y1) + 4 * qx * qy * (y0 + y1))

/-- Mod-5 polynomial collapse: 7*F(z) ≡ 2 * ∑ Z_k^6 (mod 5) for ALL z ∈ Z^6. -/
theorem hodge_sextic_7F_mod5_fermat :
    ∀ z : Fin 6 → Int,
      hodgeSextic7F z % 5 =
        (2 * ((z 0) ^ 6 + (z 1) ^ 6 + (z 2) ^ 6 + (z 3) ^ 6 + (z 4) ^ 6 + (z 5) ^ 6)) % 5 := by
  intro z
  dsimp only [hodgeSextic7F]
  omega

/-- Mod-5 Jacobian collapse: every exact partial ∂(7F)/∂Z_k ≡ 2 * Z_k^5 (mod 5) for ALL z ∈ Z^6. -/
theorem hodge_sextic_7F_partials_mod5 :
    ∀ (k : Fin 6) (z : Fin 6 → Int),
      hodgeSextic7FPartial k z % 5 = (2 * ((z k) ^ 5)) % 5 := by
  intro k z
  match k with
  | ⟨0, _⟩ => simp only [hodgeSextic7FPartial]; change _ = (2 * (z 0) ^ 5) % 5; omega
  | ⟨1, _⟩ => simp only [hodgeSextic7FPartial]; change _ = (2 * (z 1) ^ 5) % 5; omega
  | ⟨2, _⟩ => simp only [hodgeSextic7FPartial]; change _ = (2 * (z 2) ^ 5) % 5; omega
  | ⟨3, _⟩ => simp only [hodgeSextic7FPartial]; change _ = (2 * (z 3) ^ 5) % 5; omega
  | ⟨4, _⟩ => simp only [hodgeSextic7FPartial]; change _ = (2 * (z 4) ^ 5) % 5; omega
  | ⟨5, _⟩ => simp only [hodgeSextic7FPartial]; change _ = (2 * (z 5) ^ 5) % 5; omega

/-- Fermat's Little Theorem over F_5 and non-degeneracy of 2 * z^5 (mod 5). -/
theorem fermat_little_mod5_and_jacobian_nondeg :
    (∀ r : Fin 5, (r.val ^ 5) % 5 = r.val) ∧
    (∀ r : Fin 5, (2 * (r.val ^ 5)) % 5 = 0 ↔ r.val = 0) := by
  decide

private theorem int_pow5_mod5 (x : Int) : (2 * (x ^ 5)) % 5 = (2 * ((x % 5) ^ 5)) % 5 := by
  have h5 : x ^ 5 = x * (x * (x * (x * (x * 1)))) := by
    simp [Int.pow_succ, Int.mul_comm]
  have h5r : (x % 5) ^ 5 = (x % 5) * ((x % 5) * ((x % 5) * ((x % 5) * ((x % 5) * 1)))) := by
    simp [Int.pow_succ, Int.mul_comm]
  rw [h5, h5r]
  simp only [Int.mul_emod, Int.emod_emod]

/-- Universal projective smoothness of `hodge.computer` symmetric sextic over F_5:
    if all 6 Jacobian partials of 7*F vanish mod 5 at z ∈ Z^6, then z ≡ 0 (mod 5)
    (unique origin solution, hence ZERO singular points in P^5(F_5)). -/
theorem hodge_sextic_mod5_smooth :
    ∀ z : Fin 6 → Int,
      (∀ k : Fin 6, hodgeSextic7FPartial k z % 5 = 0) →
      ∀ k : Fin 6, z k % 5 = 0 := by
  intro z hjac k
  have hk := hjac k
  rw [hodge_sextic_7F_partials_mod5 k z, int_pow5_mod5 (z k)] at hk
  have hlt : 0 ≤ z k % 5 ∧ z k % 5 < 5 :=
    ⟨Int.emod_nonneg (z k) (by decide), Int.emod_lt_of_pos (z k) (by decide)⟩
  have hr : z k % 5 = 0 ∨ z k % 5 = 1 ∨ z k % 5 = 2 ∨ z k % 5 = 3 ∨ z k % 5 = 4 := by omega
  rcases hr with h0 | h1 | h2 | h3 | h4
  · exact h0
  · rw [h1] at hk; omega
  · rw [h2] at hk; omega
  · rw [h3] at hk; omega
  · rw [h4] at hk; omega

#print axioms polya_no_3x3_sign_matrix
#print axioms polya_512_zero_valid_and_max_5
#print axioms hodge_sextic_7F_mod5_fermat
#print axioms hodge_sextic_7F_partials_mod5
#print axioms fermat_little_mod5_and_jacobian_nondeg
#print axioms hodge_sextic_mod5_smooth

end AletheiaKernelCerts.Theorem5
