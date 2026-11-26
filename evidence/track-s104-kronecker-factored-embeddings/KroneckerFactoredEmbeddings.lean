/-
  Track S104: Kronecker product-code factored embeddings, the rank-1 expressivity
  obstruction and its rank-2 lift, composed triple-gate counting, a zero-success
  holdout bound, lane-local avalanche obstruction, and a latent-repair collision
  ceiling.

  Pure Init: zero imports, zero Mathlib. Every vector is a `List Int`, so every
  identity below is proved over the integers (the Python oracle replays the same
  identities over the rationals). All theorems are universally quantified.
-/

namespace KroneckerFactoredEmbeddings

-- ---------------------------------------------------------------------------
-- Definitions
-- ---------------------------------------------------------------------------

/-- Integer dot product of two lists (truncates to the shorter list). -/
def dot : List Int → List Int → Int
  | a :: as, b :: bs => a * b + dot as bs
  | _, _ => 0

/-- Squared Euclidean norm. -/
def sqnorm (v : List Int) : Int := dot v v

/-- Scalar multiple of a vector. -/
def scale (c : Int) : List Int → List Int
  | [] => []
  | x :: xs => c * x :: scale c xs

/-- Kronecker (tensor) product of two vectors, row-major: blocks `a_i * b`. -/
def kron : List Int → List Int → List Int
  | [], _ => []
  | a :: as, b => scale a b ++ kron as b

/-- Hybrid (Kronecker plus concatenation) embedding row `[a ⊗ b ; a ; b]`. -/
def hybrid (a b : List Int) : List Int := kron a b ++ (a ++ b)

/-- Zero vector of length `n`. -/
def zeros : Nat → List Int
  | 0 => []
  | n + 1 => 0 :: zeros n

/-- One-hot vector of length `n` with a one at position `i` (all zeros if `i ≥ n`). -/
def onehot : Nat → Nat → List Int
  | 0, _ => []
  | n + 1, 0 => 1 :: zeros n
  | n + 1, i + 1 => 0 :: onehot n i

/-- Kronecker-delta indicator as an integer. -/
def delta (i j : Nat) : Int := if i = j then 1 else 0

/-- Number of positions where two lists differ (truncates to the shorter list). -/
def hamming {β : Type} [DecidableEq β] : List β → List β → Nat
  | a :: as, b :: bs => (if a = b then 0 else 1) + hamming as bs
  | _, _ => 0

-- ---------------------------------------------------------------------------
-- Auxiliary lemmas (not counted among the 25 named theorems; no `#print` line)
-- ---------------------------------------------------------------------------

theorem mul4_comm (A B C D : Int) : (A * B) * (C * D) = (A * C) * (B * D) := by
  rw [Int.mul_assoc, Int.mul_left_comm B C D, ← Int.mul_assoc]

theorem length_scale (c : Int) (v : List Int) : (scale c v).length = v.length := by
  induction v with
  | nil => rfl
  | cons x xs ih => exact congrArg Nat.succ ih

theorem dot_nil_right (a : List Int) : dot a [] = 0 := by
  cases a <;> rfl

theorem dot_zeros_left (n : Nat) (v : List Int) : dot (zeros n) v = 0 := by
  induction n generalizing v with
  | zero => rfl
  | succ n ih =>
    cases v with
    | nil => rfl
    | cons b bs =>
      show 0 * b + dot (zeros n) bs = 0
      rw [ih bs, Int.zero_mul]
      rfl

theorem dot_zeros_right (n : Nat) (v : List Int) : dot v (zeros n) = 0 := by
  induction n generalizing v with
  | zero => exact dot_nil_right v
  | succ n ih =>
    cases v with
    | nil => rfl
    | cons b bs =>
      show b * 0 + dot bs (zeros n) = 0
      rw [ih bs, Int.mul_zero]
      rfl

theorem length_zeros (t : Nat) : (zeros t).length = t := by
  induction t with
  | zero => rfl
  | succ t iht => exact congrArg Nat.succ iht

theorem length_onehot (n k : Nat) : (onehot n k).length = n := by
  induction n generalizing k with
  | zero => rfl
  | succ m ihm =>
    cases k with
    | zero => exact congrArg Nat.succ (length_zeros m)
    | succ k' => exact congrArg Nat.succ (ihm k')

theorem hamming_self {β : Type} [DecidableEq β] (l : List β) : hamming l l = 0 := by
  induction l with
  | nil => rfl
  | cons x xs ih =>
    show (if x = x then 0 else 1) + hamming xs xs = 0
    rw [ite_eq_left rfl, ih]

theorem hamming_set_le_one {β : Type} [DecidableEq β] (l : List β) (i : Nat) (v : β) :
    hamming l (l.set i v) ≤ 1 := by
  induction l generalizing i with
  | nil => exact Nat.zero_le 1
  | cons a as ih =>
    cases i with
    | zero =>
      show (if a = v then 0 else 1) + hamming as as ≤ 1
      rw [hamming_self]
      cases decEq a v with
      | isTrue h => rw [ite_eq_left h]; decide
      | isFalse h => rw [ite_eq_right h]; decide
    | succ k =>
      show (if a = a then 0 else 1) + hamming as (as.set k v) ≤ 1
      rw [ite_eq_left rfl, Nat.zero_add]
      exact ih k

theorem triple_eq_static_then {γ : Type} (l : List γ) (s r h : γ → Bool) :
    l.filter (fun x => s x && r x && h x) = (l.filter s).filter (fun x => r x && h x) := by
  rw [List.filter_filter]
  congr 1
  funext x
  cases s x <;> cases r x <;> cases h x <;> rfl

theorem zero_success_aux (k : Nat) : 20 * 31 ^ (96 + k) < 32 ^ (96 + k) := by
  induction k with
  | zero => decide
  | succ k ih =>
    rw [Nat.add_succ, Nat.pow_succ, Nat.pow_succ]
    omega

-- ---------------------------------------------------------------------------
-- Pillar 1: exact Kronecker algebra (Gram factorization, DPI = 1)
-- ---------------------------------------------------------------------------

/-- Theorem 1: the dot product splits over aligned concatenations. -/
theorem dot_append (a1 a2 b1 b2 : List Int) (h : a1.length = b1.length) :
    dot (a1 ++ a2) (b1 ++ b2) = dot a1 b1 + dot a2 b2 := by
  induction a1 generalizing b1 with
  | nil =>
    cases b1 with
    | nil => exact (Int.zero_add _).symm
    | cons b bs => cases h
  | cons a as ih =>
    cases b1 with
    | nil => cases h
    | cons b bs =>
      show a * b + dot (as ++ a2) (bs ++ b2) = (a * b + dot as bs) + dot a2 b2
      rw [ih bs (Nat.succ.inj h), Int.add_assoc]

/-- Theorem 2: scaling both arguments multiplies the dot product by the product of scalars. -/
theorem dot_scale_scale (x y : Int) (u v : List Int) :
    dot (scale x u) (scale y v) = x * y * dot u v := by
  induction u generalizing v with
  | nil => exact (Int.mul_zero _).symm
  | cons a as ih =>
    cases v with
    | nil => exact (Int.mul_zero _).symm
    | cons b bs =>
      show (x * a) * (y * b) + dot (scale x as) (scale y bs) = x * y * (a * b + dot as bs)
      rw [ih bs, Int.mul_add, mul4_comm]

/-- Theorem 3: the Kronecker product has length `|a| * |b|` (the `d = d1 * d2` budget). -/
theorem kron_length (a b : List Int) : (kron a b).length = a.length * b.length := by
  induction a with
  | nil => exact (Nat.zero_mul _).symm
  | cons x xs ih =>
    show (scale x b ++ kron xs b).length = (xs.length + 1) * b.length
    rw [List.length_append, length_scale, ih, Nat.succ_mul, Nat.add_comm]

/-- Theorem 4 (Kronecker Gram factorization): for equal-length pattern factors,
    `⟨a ⊗ b, a' ⊗ b'⟩ = ⟨a, a'⟩ * ⟨b, b'⟩` (no length hypothesis on the root factors). -/
theorem kron_dot (a a' b b' : List Int) (hb : b.length = b'.length) :
    dot (kron a b) (kron a' b') = dot a a' * dot b b' := by
  induction a generalizing a' with
  | nil => exact (Int.zero_mul _).symm
  | cons x xs ih =>
    cases a' with
    | nil =>
      show dot (kron (x :: xs) b) [] = 0 * dot b b'
      rw [dot_nil_right, Int.zero_mul]
    | cons y ys =>
      show dot (scale x b ++ kron xs b) (scale y b' ++ kron ys b')
        = (x * y + dot xs ys) * dot b b'
      have hl : (scale x b).length = (scale y b').length := by
        rw [length_scale, length_scale, hb]
      rw [dot_append _ _ _ _ hl, dot_scale_scale, ih ys, Int.add_mul]

/-- Theorem 5 (norm multiplicativity): `‖a ⊗ b‖² = ‖a‖² * ‖b‖²`. -/
theorem kron_sqnorm (a b : List Int) : sqnorm (kron a b) = sqnorm a * sqnorm b :=
  kron_dot a a b b rfl

/-- Theorem 6 (DPI = 1 by construction): if every root row and every pattern row is
    norm-calibrated, then every pair of Kronecker embedding rows has equal squared norm. -/
theorem kron_rows_equal_norm (A B : Nat → List Int) (MA MB : Int)
    (hA : ∀ r, sqnorm (A r) = MA) (hB : ∀ p, sqnorm (B p) = MB) (r p r' p' : Nat) :
    sqnorm (kron (A r) (B p)) = sqnorm (kron (A r') (B p')) := by
  rw [kron_sqnorm, kron_sqnorm, hA r, hB p, hA r', hB p']

/-- Theorem 7: shared-root similarity equals the calibrated root mass times pattern similarity. -/
theorem shared_root_gram (a b b' : List Int) (MA : Int) (hb : b.length = b'.length)
    (hA : sqnorm a = MA) :
    dot (kron a b) (kron a b') = MA * dot b b' := by
  have hA' : dot a a = MA := hA
  rw [kron_dot a a b b' hb, hA']

/-- Theorem 8 (honest correction): in the rank-1 Kronecker code, orthogonal patterns
    annihilate shared-root similarity, so root sharing is a multiplicative gate,
    NOT a pattern-independent positive floor. -/
theorem shared_root_annihilated_by_orthogonal_patterns (a b b' : List Int)
    (hb : b.length = b'.length) (horth : dot b b' = 0) :
    dot (kron a b) (kron a b') = 0 := by
  rw [kron_dot a a b b' hb, horth, Int.mul_zero]

-- ---------------------------------------------------------------------------
-- Pillar 2: rank-1 expressivity obstruction and the rank-2 lift
-- ---------------------------------------------------------------------------

/-- Theorem 9: every rank-1 product kernel `K = α ⊗ β` satisfies the 2x2 multiplicative
    minor identity `K(r r' | p p) K(r r | p p') = K(r r | p p) K(r r' | p p')`. -/
theorem rank1_minor_identity (α β : Nat → Nat → Int) (r r' p p' : Nat) :
    (α r r' * β p p) * (α r r * β p p') = (α r r * β p p) * (α r r' * β p p') := by
  rw [mul4_comm, Int.mul_comm (α r r') (α r r), ← mul4_comm]

/-- Theorem 10 (Law-5 obstruction): the additive share-root-OR-share-pattern kernel
    `δ(r,r') + δ(p,p')` is not representable by any rank-1 product kernel. -/
theorem additive_kernel_not_rank1 :
    ¬ ∃ α β : Nat → Nat → Int, ∀ r r' p p', α r r' * β p p' = delta r r' + delta p p' := by
  intro ⟨α, β, h⟩
  have hm := rank1_minor_identity α β 0 1 0 1
  rw [h 0 1 0 0, h 0 0 0 1, h 0 0 0 0, h 0 1 0 1] at hm
  exact absurd hm (by decide)

/-- Theorem 11 (rank-2 CP Gram): the concatenation of two Kronecker blocks has Gram
    equal to the sum of the two factored Grams. -/
theorem cp2_gram (a1 b1 a2 b2 a1' b1' a2' b2' : List Int)
    (ha1 : a1.length = a1'.length) (hb1 : b1.length = b1'.length)
    (hb2 : b2.length = b2'.length) :
    dot (kron a1 b1 ++ kron a2 b2) (kron a1' b1' ++ kron a2' b2')
      = dot a1 a1' * dot b1 b1' + dot a2 a2' * dot b2 b2' := by
  have hl : (kron a1 b1).length = (kron a1' b1').length := by
    rw [kron_length, kron_length, ha1, hb1]
  rw [dot_append _ _ _ _ hl, kron_dot _ _ _ _ hb1, kron_dot _ _ _ _ hb2]

/-- Theorem 12: one-hot vectors of equal length are orthonormal: `⟨e_i, e_j⟩ = δ(i,j)`
    for in-range indices. -/
theorem onehot_dot (n i j : Nat) (hi : i < n) (hj : j < n) :
    dot (onehot n i) (onehot n j) = delta i j := by
  induction n generalizing i j with
  | zero => exact absurd hi (Nat.not_lt_zero i)
  | succ m ih =>
    cases i with
    | zero =>
      cases j with
      | zero =>
        show 1 * 1 + dot (zeros m) (zeros m) = delta 0 0
        rw [dot_zeros_left]
        rfl
      | succ j' =>
        show 1 * 0 + dot (zeros m) (onehot m j') = delta 0 (j' + 1)
        rw [dot_zeros_left]
        show (0 : Int) = if 0 = j' + 1 then 1 else 0
        rw [ite_eq_right (Nat.succ_ne_zero j').symm]
    | succ i' =>
      cases j with
      | zero =>
        show 0 * 1 + dot (onehot m i') (zeros m) = delta (i' + 1) 0
        rw [dot_zeros_right]
        show (0 : Int) = if i' + 1 = 0 then 1 else 0
        rw [ite_eq_right (Nat.succ_ne_zero i')]
      | succ j' =>
        show 0 * 0 + dot (onehot m i') (onehot m j') = delta (i' + 1) (j' + 1)
        rw [ih i' j' (Nat.lt_of_succ_lt_succ hi) (Nat.lt_of_succ_lt_succ hj), Int.zero_mul,
          Int.zero_add]
        show (if i' = j' then 1 else 0 : Int) = if i' + 1 = j' + 1 then 1 else 0
        cases decEq i' j' with
        | isTrue e => rw [ite_eq_left e, ite_eq_left (congrArg Nat.succ e)]
        | isFalse e => rw [ite_eq_right e, ite_eq_right (fun e' => e (Nat.succ.inj e'))]

/-- Theorem 13 (rank-2 lift realizes the obstructed kernel): the concatenated one-hot
    embedding `[e_r ; e_p]` has Gram exactly `δ(r,r') + δ(p,p')`. -/
theorem additive_kernel_rank2_realized (R P r r' p p' : Nat)
    (hr : r < R) (hr' : r' < R) (hp : p < P) (hp' : p' < P) :
    dot (onehot R r ++ onehot P p) (onehot R r' ++ onehot P p') = delta r r' + delta p p' := by
  have hl : (onehot R r).length = (onehot R r').length := by
    rw [length_onehot, length_onehot]
  rw [dot_append _ _ _ _ hl, onehot_dot R r r' hr hr', onehot_dot P p p' hp hp']

/-- Theorem 14 (hybrid Gram): `⟨[a⊗b; a; b], [a'⊗b'; a'; b']⟩ = ⟨a,a'⟩⟨b,b'⟩ + ⟨a,a'⟩ + ⟨b,b'⟩`. -/
theorem hybrid_gram (a b a' b' : List Int) (ha : a.length = a'.length) (hb : b.length = b'.length) :
    dot (hybrid a b) (hybrid a' b') = dot a a' * dot b b' + dot a a' + dot b b' := by
  have hl : (kron a b).length = (kron a' b').length := by
    rw [kron_length, kron_length, ha, hb]
  show dot (kron a b ++ (a ++ b)) (kron a' b' ++ (a' ++ b'))
    = dot a a' * dot b b' + dot a a' + dot b b'
  rw [dot_append _ _ _ _ hl, kron_dot _ _ _ _ hb, dot_append _ _ _ _ ha, Int.add_assoc]

/-- Theorem 15 (hybrid repairs Theorem 8): with orthogonal patterns, the hybrid code keeps
    shared-root similarity equal to the full root mass `‖a‖²`. -/
theorem hybrid_shared_root_survives_orthogonal_patterns (a b b' : List Int)
    (hb : b.length = b'.length) (horth : dot b b' = 0) :
    dot (hybrid a b) (hybrid a b') = sqnorm a := by
  rw [hybrid_gram a b a b' rfl hb, horth, Int.mul_zero, Int.zero_add, Int.add_zero]
  rfl

/-- Theorem 16 (hybrid keeps DPI = 1): calibrated factors give equal hybrid row norms. -/
theorem hybrid_rows_equal_norm (A B : Nat → List Int) (MA MB : Int)
    (hA : ∀ r, sqnorm (A r) = MA) (hB : ∀ p, sqnorm (B p) = MB) (r p r' p' : Nat) :
    sqnorm (hybrid (A r) (B p)) = sqnorm (hybrid (A r') (B p')) := by
  have e1 : dot (A r) (A r) = MA := hA r
  have e2 : dot (B p) (B p) = MB := hB p
  have e3 : dot (A r') (A r') = MA := hA r'
  have e4 : dot (B p') (B p') = MB := hB p'
  show dot (hybrid (A r) (B p)) (hybrid (A r) (B p))
    = dot (hybrid (A r') (B p')) (hybrid (A r') (B p'))
  rw [hybrid_gram _ _ _ _ rfl rfl, hybrid_gram _ _ _ _ rfl rfl, e1, e2, e3, e4]

/-- Theorem 17 (parameter budget): for at least two roots and two patterns and positive
    factor widths, the factored table `R*d1 + P*d2` never exceeds the full table
    `R*P*(d1*d2)`. -/
theorem factored_params_le_full (R P d1 d2 : Nat) (hR : 2 ≤ R) (hP : 2 ≤ P)
    (h1 : 1 ≤ d1) (h2 : 1 ≤ d2) :
    R * d1 + P * d2 ≤ R * P * (d1 * d2) := by
  have hx : 2 * 1 ≤ R * d1 := Nat.mul_le_mul hR h1
  have hy : 2 * 1 ≤ P * d2 := Nat.mul_le_mul hP h2
  rw [Nat.mul_mul_mul_comm]
  have e1 : 2 * (P * d2) ≤ (R * d1) * (P * d2) := Nat.mul_le_mul_right _ hx
  have e2 : (R * d1) * 2 ≤ (R * d1) * (P * d2) := Nat.mul_le_mul_left _ hy
  omega

-- ---------------------------------------------------------------------------
-- Pillar 3: composed triple gate (StaticProof ∧ Receipt ∧ Holdout)
-- ---------------------------------------------------------------------------

/-- Theorem 18 (anti-language-smuggling): pure acceptance gates COMMUTE; any genuine
    non-commutativity must come from selection operators, not from the gates. -/
theorem gate_filters_commute {γ : Type} (l : List γ) (p q : γ → Bool) :
    (l.filter p).filter q = (l.filter q).filter p := by
  rw [List.filter_filter, List.filter_filter]
  congr 1
  funext x
  exact Bool.and_comm _ _

/-- Theorem 19: the composed triple gate never accepts more candidates than the static gate. -/
theorem triple_gate_le_static {γ : Type} (l : List γ) (s r h : γ → Bool) :
    (l.filter (fun x => s x && r x && h x)).length ≤ (l.filter s).length := by
  rw [triple_eq_static_then]
  exact List.length_filter_le _ _

/-- Theorem 20: a single statically-proved, receipt-valid candidate that fails holdout
    makes the composed gate strictly stricter than the static gate. -/
theorem triple_gate_strict_of_witness {γ : Type} (l : List γ) (s r h : γ → Bool) (c : γ)
    (hc : c ∈ l) (hs : s c = true) (hr : r c = true) (hh : h c = false) :
    (l.filter (fun x => s x && r x && h x)).length < (l.filter s).length := by
  rw [triple_eq_static_then]
  have key : ∀ (m : List γ), c ∈ m → s c = true →
      ((m.filter s).filter (fun x => r x && h x)).length < (m.filter s).length := by
    intro m
    induction m with
    | nil => intro hm; cases hm
    | cons y ys ih =>
      intro hm _
      cases hsy : s y with
      | false =>
        rw [List.filter_cons_of_neg (by rw [hsy]; decide)]
        cases hm with
        | head => rw [hs] at hsy; cases hsy
        | tail _ ht => exact ih ht hs
      | true =>
        rw [List.filter_cons_of_pos hsy]
        cases hrh : (r y && h y) with
        | true =>
          rw [List.filter_cons_of_pos (p := fun x => r x && h x) hrh]
          cases hm with
          | head => rw [hr, hh] at hrh; cases hrh
          | tail _ ht => exact Nat.succ_lt_succ (ih ht hs)
        | false =>
          rw [List.filter_cons_of_neg (p := fun x => r x && h x) (by rw [hrh]; decide)]
          exact Nat.lt_succ_of_le (List.length_filter_le _ _)
  exact key l hc hs

/-- Theorem 21: if no candidate passes the sealed holdout, the composed gate accepts none,
    regardless of how many pass the static proof and receipt gates. -/
theorem holdout_zero_kills_composed {γ : Type} (l : List γ) (s r h : γ → Bool)
    (hz : ∀ c ∈ l, h c = false) :
    l.filter (fun x => s x && r x && h x) = [] := by
  induction l with
  | nil => rfl
  | cons y ys ih =>
    have hy : h y = false := hz y (List.Mem.head ys)
    have hneg : ¬ ((s y && r y && h y) = true) := by
      rw [hy, Bool.and_false]
      decide
    rw [List.filter_cons_of_neg (p := fun x => s x && r x && h x) hneg]
    exact ih (fun c hc => hz c (List.Mem.tail y hc))

/-- Theorem 22 (exact zero-success bound): for every sealed holdout of size `n ≥ 96`,
    `20 * 31^n < 32^n`, i.e. `(31/32)^n < 1/20`, so `0/n` successes bounds the one-sided
    95% Clopper-Pearson upper limit of `P(utility | legal ∧ receipt)` strictly below `1/32`. -/
theorem zero_success_bound (n : Nat) (hn : 96 ≤ n) : 20 * 31 ^ n < 32 ^ n := by
  have h := zero_success_aux (n - 96)
  rw [Nat.add_sub_of_le hn] at h
  exact h

-- ---------------------------------------------------------------------------
-- Pillar 4: RAM == WIRE == HASH lane-local avalanche obstruction
-- ---------------------------------------------------------------------------

/-- Theorem 23: any lane-local (per-lane) map can never amplify the number of differing
    lanes: `hamming (map f l) (map f l') ≤ hamming l l'`. -/
theorem lane_local_nonexpansive {α β : Type} [DecidableEq α] [DecidableEq β]
    (f : α → β) (l l' : List α) :
    hamming (l.map f) (l'.map f) ≤ hamming l l' := by
  induction l generalizing l' with
  | nil => exact Nat.zero_le _
  | cons a as ih =>
    cases l' with
    | nil => exact Nat.zero_le _
    | cons b bs =>
      show (if f a = f b then 0 else 1) + hamming (as.map f) (bs.map f)
        ≤ (if a = b then 0 else 1) + hamming as bs
      have hrec := ih bs
      cases decEq a b with
      | isTrue hab =>
        rw [ite_eq_left hab, ite_eq_left (congrArg f hab)]
        omega
      | isFalse hab =>
        rw [ite_eq_right hab]
        cases decEq (f a) (f b) with
        | isTrue hf => rw [ite_eq_left hf]; omega
        | isFalse hf => rw [ite_eq_right hf]; omega

/-- Theorem 24 (avalanche obstruction): for any lane-local digest over at least three
    lanes, changing one input lane changes strictly fewer than half of the output lanes,
    so the `≥ 50%` avalanche gate is unpassable (the 4-lane case gives `≤ 1/4`). -/
theorem lane_local_fails_avalanche {α β : Type} [DecidableEq α] [DecidableEq β]
    (f : α → β) (l : List α) (i : Nat) (v : α) (hl : 3 ≤ l.length) :
    2 * hamming (l.map f) ((l.set i v).map f) < l.length := by
  have h1 := lane_local_nonexpansive f l (l.set i v)
  have h2 := hamming_set_le_one l i v
  omega

-- ---------------------------------------------------------------------------
-- Pillar 5: EXP-Δ latent-repair collision ceiling
-- ---------------------------------------------------------------------------

/-- Theorem 25 (latent-repair ceiling): any scorer that sees only the English surface
    (`g ∘ tok`) must misclassify at least one of two items that share an identical
    English surface but carry different edge labels. -/
theorem latent_repair_collision_ceiling {X T : Type} (tok : X → T) (g : T → Bool)
    (lab : X → Bool) (x y : X) (hsurf : tok x = tok y) (hlab : lab x ≠ lab y) :
    ¬ (g (tok x) = lab x ∧ g (tok y) = lab y) := by
  intro ⟨hx, hy⟩
  rw [hsurf] at hx
  exact hlab (hx.symm.trans hy)

end KroneckerFactoredEmbeddings

#print axioms KroneckerFactoredEmbeddings.dot_append
#print axioms KroneckerFactoredEmbeddings.dot_scale_scale
#print axioms KroneckerFactoredEmbeddings.kron_length
#print axioms KroneckerFactoredEmbeddings.kron_dot
#print axioms KroneckerFactoredEmbeddings.kron_sqnorm
#print axioms KroneckerFactoredEmbeddings.kron_rows_equal_norm
#print axioms KroneckerFactoredEmbeddings.shared_root_gram
#print axioms KroneckerFactoredEmbeddings.shared_root_annihilated_by_orthogonal_patterns
#print axioms KroneckerFactoredEmbeddings.rank1_minor_identity
#print axioms KroneckerFactoredEmbeddings.additive_kernel_not_rank1
#print axioms KroneckerFactoredEmbeddings.cp2_gram
#print axioms KroneckerFactoredEmbeddings.onehot_dot
#print axioms KroneckerFactoredEmbeddings.additive_kernel_rank2_realized
#print axioms KroneckerFactoredEmbeddings.hybrid_gram
#print axioms KroneckerFactoredEmbeddings.hybrid_shared_root_survives_orthogonal_patterns
#print axioms KroneckerFactoredEmbeddings.hybrid_rows_equal_norm
#print axioms KroneckerFactoredEmbeddings.factored_params_le_full
#print axioms KroneckerFactoredEmbeddings.gate_filters_commute
#print axioms KroneckerFactoredEmbeddings.triple_gate_le_static
#print axioms KroneckerFactoredEmbeddings.triple_gate_strict_of_witness
#print axioms KroneckerFactoredEmbeddings.holdout_zero_kills_composed
#print axioms KroneckerFactoredEmbeddings.zero_success_bound
#print axioms KroneckerFactoredEmbeddings.lane_local_nonexpansive
#print axioms KroneckerFactoredEmbeddings.lane_local_fails_avalanche
#print axioms KroneckerFactoredEmbeddings.latent_repair_collision_ceiling
