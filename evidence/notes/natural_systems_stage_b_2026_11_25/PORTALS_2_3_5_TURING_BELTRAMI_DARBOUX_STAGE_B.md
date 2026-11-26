# Natural Systems Stage-B: Portals 2, 3 and 5 (Turing, Beltrami, Darboux)

**Date:** 2026-11-25 | **Owner:** `continuum-bridge` | **Discipline:** Aletheia Law-5 Stage A (strip the physics and biology nouns) then Stage B (exact operators, conservation laws, prototype oracles, obstructions) | **Compute:** CPU-only, pure `int`/`Fraction`, no floats

**Witness:** [`verify_portals_2_3_5_exact.py`](verify_portals_2_3_5_exact.py) runs **44/44** exact checks in about 3 s, with receipt `ead0952b39f9afeb63cfee8c62d7c287d47beb0d4f40ec868b49df7065787379`. Exit code 0 means every check passed. Results are identical under `-I -B`, `-I -O -B` and `-I -B -W error`. Section 5 lists the gate receipts.

> **Scope rule.** Everything stated as a theorem below is either a standard linear-algebra fact with its one-line proof given here, or it is checked exactly by the witness on the stated instances. Statements about learned models are **hypotheses**, and Section 4 phrases them as falsifiable `SOP-12` candidates. The track IDs come from the roadmap's portal list. This note does not re-verify what those tracks contain.

---

## Portal 2: Reaction-diffusion and Turing symmetry breaking

### Stage A (nouns stripped)
"Activator / inhibitor / morphogen / tissue" reduces to a **2-channel linear system on a graph**:

- `G` is a graph with Laplacian `L` (symmetric, PSD, `L 1 = 0`).
- `J` is a 2×2 reaction matrix.
- `D = diag(d_u, d_v)` is the non-negative per-channel coupling.

The full operator is

$$M \;=\; I_n \otimes J \;-\; L \otimes D \qquad (x \in \mathbb{Q}^{2n}).$$

### Stage B (exact operators)
1. **Mode factorisation.** If `L = Q Λ Qᵀ`, then `(Q ⊗ I₂)ᵀ M (Q ⊗ I₂) = ⊕_k (J − μ_k D)`. So `spec(M) = ∪_k spec(J − μ_k D)`. The witness checks `charpoly(M) = ∏_k charpoly(J − μ_k D)` exactly on `C_4` and `C_6`.
2. **Instability criterion.** Assume `tr J < 0` and `det J > 0`, so the system is stable without coupling. Because `tr(J − μD) = tr J − μ(d_u+d_v) < 0` for all `μ ≥ 0`, mode `k` is unstable **iff**
   $$\delta(\mu_k) := d_u d_v\,\mu_k^2 - (d_v j_{11} + d_u j_{22})\,\mu_k + \det J \;<\; 0 .$$
   This needs `d_v j₁₁ + d_u j₂₂ > 0` and a positive discriminant. Since `j₁₁ + j₂₂ < 0`, it also forces `j₁₁ j₂₂ < 0` and `d_u ≠ d_v`.
3. **Witness instance.** `J = [[7, 15], [−21/2, −10]]` and `D = diag(1, 10)` give `tr J = −3` and `det J = 175/2`. Then `δ(μ) = 10μ² − 60μ + 175/2`. Its roots `μ ∈ {5/2, 7/2}` are exact, which makes the unstable band `(5/2, 7/2)`, with `δ(3) = −5/2`.
4. **Exact band test.** Mode instability holds iff `spec(L) ∩ (μ₋, μ₊) ≠ ∅`. The witness decides this with a **Sturm count of `charpoly(L)` on the band**, with no eigenvalue approximation. Separately, it computes the number of distinct positive real eigenvalues of the full `2n×2n` operator `M`: 0 on `C_4`, 0 on `C_5` and 1 on `C_6`.

### Obstructions (where the analogy fails or is constrained)
- **O2.1 Equal coupling never breaks symmetry.** If `D = dI`, then `δ(μ) = d²μ² − d·tr J·μ + det J` has all coefficients positive, so `δ > 0` on `μ ≥ 0` for **every graph**. The witness confirms this with the coefficient certificate, and also finds 0 positive real eigenvalues of `I⊗J − dL⊗I` on `C_3`, `C_4`, `C_6` and `C_12` for `d ∈ {1/10, 1, 10}`. **Consequence:** an architecture that couples all channels with one shared rate (one shared mixing/attention temperature) **cannot** produce Turing differentiation, however it is wired.
- **O2.2 Spectral-band aliasing (no free wavelength).** Whether symmetry breaks depends on where `spec(L)` lands, and that is non-monotone in graph size:

  | Graph | Unstable (band hit) | Stable |
  |---|---|---|
  | Cycles `C_n`, `n = 3..16` | 3, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16 | **4, 5, 7** |
  | Paths `P_n`, `n = 2..8` | 3, 4, 5, 6, 7, 8 | 2 |

  On the ring, `μ = 2 − 2cos θ` lies in the band iff `cos θ ∈ (−3/4, −1/4)`, that is, `θ ∈ (104.48°, 138.59°)`. The band endpoints are never ring eigenvalues: by Niven's theorem, a rational cosine at a rational multiple of π lies in `{0, ±1/2, ±1}`. The witness also checks `charpoly(P_n) | charpoly(C_{2n})` exactly. **Consequence:** an "emergent patch length" is quantised by the discrete spectrum and can disappear entirely for some sizes (here `n = 4, 5, 7`).
- **O2.3 Complete graph: all-or-none.** `charpoly(K_5) = x(x−5)⁴`. There is one nonzero eigenvalue, with multiplicity `n−1`. Either every non-uniform pattern is unstable or none is, and the linear operator picks no pattern. On fully connected expert graphs, which experts specialise is **not** decided by the linear operator. It comes from nonlinearity or noise, outside this Stage-B scope.
- **O2.4 Not covered (stated honestly).** The linear analysis picks the unstable subspace only. It does not give amplitude, pattern selection or saturation. A discrete residual update `x ← x + ηMx` adds its own constraint (`|1 + ηλ| < 1` for the stable modes), which the witness does not check.

### Bridge to the active spine
- **`H8b` byte-patch boundary nucleation (`PREREG-S108`):** take positions as a path or ring graph, with a 2-channel boundary activator/inhibitor. The band test makes **exact pre-gate predictions**. For the witness band, the unstable ring angle `θ ∈ (104.48°, 138.59°)` gives a predicted boundary period `360°/θ ∈ (2.60, 3.45)` positions, and some sequence lengths cannot nucleate at all. O2.1 provides a ready null arm: equal `D`.
- **MoE / specialist micro-harness differentiation:** an expert-affinity graph with differential self-promotion vs. lateral inhibition. Expert differentiation needs `d_u ≠ d_v` (O2.1) and a band hit (O2.2). On dense affinity graphs, O2.3 says the linear layer cannot choose *which* experts differentiate.

---

## Portal 3: Beltrami force-free transport and helicity

### Stage A (nouns stripped)
"Velocity / vorticity / helicity / turbulence" reduces to a **vector field on a periodic lattice**:

- `v ∈ ℚ^{3n³}` on `ℤ_n³`.
- The central-difference curl `C` (entries in `{0, ±1/2}`).
- Energy `E(v) = vᵀv`, helicity `H(v) = vᵀCv` and higher moments `m_j(v) = vᵀCʲv`.

### Stage B (exact operators)
1. **Discrete vector calculus.** On `n = 3, 4` the witness checks `Cᵀ = C` (curl is self-adjoint on the torus), `div ∘ C = 0` and `C ∘ grad = 0`, all exactly on sparse integer matrices. Beltrami modes are eigenvectors of `C` with nonzero eigenvalue.
2. **Helicity conservation is an iff.** For a skew `K` (`Kᵀ = −K`), under `v̇ = Kv` we get `Ė = 0` and `Ḣ = vᵀ(CK − KC)v`. Since `C` is symmetric and `K` skew, `CK − KC = CK + (CK)ᵀ` is **symmetric**, so `vᵀ[C,K]v ≡ 0` iff `[C,K] = 0`. **Theorem:** a skew transport conserves helicity for all states **iff** it commutes with the curl.
3. **Exact discrete time.** With `[C,K] = 0`, the Cayley step `(I − hK)⁻¹(I + hK)` is orthogonal and commutes with `C`, so it conserves **every** moment `m_j`. The witness takes `K = T_x − T_xᵀ` (the translation generator) on `n = 3` (81-dim) and runs 3 rational Cayley steps with `h = 1/2`. All of `m₀..m₄` are unchanged exactly, `(14179/36, −6545/36, 17557/36, −2761/9, 121283/144)`, while `v` itself moves.
4. **Non-commuting control.** A single-site `x↔y` rotation (skew, `[C,K] ≠ 0`) keeps `E = 14179/36` exactly but moves `H` from `−6545/36` to `−31909/180`.

### Obstructions
- **O3.1 Commuting transport cannot cascade.** Conserving all `m_j` means each Beltrami eigenspace keeps its energy. A **linear** helicity-conserving transport moves nothing between shells, so an inverse cascade is impossible without nonlinearity (triadic interactions). The "helicity inverse cascade" side of the analogy has **no linear Stage-B counterpart**.
- **O3.2 Parity / non-chirality.** With point reflection `(Pv)_c(p) = −v_c(−p)`: `P² = I`, `PCP = −C`, and `P∘grad = grad∘R` (so `P` really is the polar-vector reflection; all checked on `n = 3, 4`). So `spec(C)` is symmetric about 0 and `H(Pv) = −H(v)`. A parity-equivariant layer cannot prefer one helicity sign. Chirality has to be injected explicitly, for example by gating on `sign(λ)`.
- **O3.3 Lattice aliasing and spurious dark modes.** In Fourier space, `rank C = 2(n³ − z)` with `z = 1` for odd `n` and `z = 8` for even `n`. The witness proves this exactly: a mod-p rank of `C` gives the lower bound, and explicit integer kernel generators give the upper bound. The results are rank 52 at `n = 3` and 112 at `n = 4`. For even `n` there are **`3z − 3 = 21` spurious curl-free modes** that are neither gradients nor constants (checkerboards). At `n = 2` the curl is **identically zero**. Even-period lattices therefore carry 21 dark modes that any curl-based gate cannot see.
- **O3.4 Finite dimension.** The `k = 0` shell (constants) lies in `ker C`. Energy that condenses at the largest scale has zero helicity eigenvalue, so "helicity piles up at large scale" has nowhere to land on a finite periodic lattice.
- **O3.5 Collapse mechanism (the H7c risk).** A **symmetric** residual `v ← (I + C/4)v` is not norm-preserving. It works as power iteration, and the helicity Rayleigh quotient `H/E` rises strictly every step: `−595/1289 → 24692/192061 → 17795255/27947142 → …`. This is the exact form of depth-loop mode collapse onto the top Beltrami eigenvector.

### Bridge to the active spine
- **`H7c` Clifford-torus looped core and `Geosphere-Net` residual transport (`PREREG-S107`/`S110`):** a depth-looped residual made of Cayley-orthogonal blocks that commute with a chosen symmetric "shell" operator `C` gives **provable no-collapse**: every shell occupancy `m_j` is invariant at every loop depth. The cost comes from O3.1: such a loop also cannot move information between shells. Any learned cross-shell component therefore has to be a separate gated term whose drift `vᵀ[C,K]v` is computed exactly, which is the measurable quantity for a preregistration.
- **Relation to `aletheia#98`:** the 2×2 block Cayley `SO(k)` operator already shipped there is the right primitive. The new content here is the **commutation condition** `[C,K] = 0` as the exact iff for helicity/moment conservation, plus the exact symmetric-residual collapse control.

---

## Portal 5: Darboux isospectral duals, dark modes, lapse and Hopf

### Stage A (nouns stripped)
"Potential / SUSY partner / lapse / fibration" reduces to a **factorised pair**:

- `L₁ = AᵀA + cI` (n×n) and `L₂ = AAᵀ + cI` (m×m), for any `A ∈ ℚ^{m×n}`.
- A positive diagonal reweighting `N`.
- Quaternion maps on `ℚ⁴`.

### Stage B (exact operators)
1. **Intertwining:** `A L₁ = L₂ A`, which is just associativity. **Spectrum:** for `rank A = m`, `charpoly(L₁) = (x − c)^{n−m} · charpoly(L₂)`. The witness uses an exact rational SVD `A = U Σ Vᵀ` with Cayley-rational orthogonal `U` (3×3) and `V` (5×5), `Σ = (2, 3/2, 1/3)` and `c = 1/7`.
2. **Eigenvector transport:** `L₁v = λv ⇒ L₂(Av) = λ(Av)`, with `‖Av‖² = (λ − c)‖v‖²` and the exact inverse `v = AᵀAv/(λ − c)` for `λ ≠ c`.
3. **Dark modes:** `ker A` (dimension `n − rank A = 2`) is exactly the `λ = c` eigenspace of `L₁` that has no partner in `L₂`, since `det(cI − L₂) ≠ 0`. `Ax = A(x + k)` for `k ∈ ker A` gives an explicit collision. The best reconstruction is `R = Aᵀ(AAᵀ)⁻¹A`, with `R² = R = Rᵀ` and `tr R = 3`, and its loss is **exactly** `‖P_{ker A}x‖²`. On the test vector this is `1377248837/234518596`.

### Obstructions
- **O5.1 Isospectral does not mean lossless.** A square singular SUSY pair `A = −diag(w) + shift` with `w = (1/2, 2, −1, 3/2, 0)` gives tridiagonal `L₁ = AᵀA` and `L₂ = AAᵀ`. They have **identical characteristic polynomials** and different "potentials" (diagonals `(1/4, 5, 2, 13/4, 1)` vs `(5/4, 5, 2, 13/4, 0)`), but `ker A = span(−2/3, −1/3, −2/3, 2/3, 1)` and `ker Aᵀ = span(e₅)` are **different, non-parallel vectors**. Transport kills one zero mode, and the other has no preimage. Spectral equivalence alone cannot certify a lossless converter. You must also audit `ker A`.
- **O5.2 Lapse preserves inertia, not spectrum.** For a positive diagonal `N`, `NL ∼ N^{1/2} L N^{1/2}`, which is congruent to `L`, so Sylvester's law keeps the inertia. Witness: `N = diag(2, 1/3, 5)` and `L = AAᵀ − 3I` give inertia `(1, 2, 0)` for both `L` and `NL`, with different characteristic polynomials. A time reparametrisation (lapse) keeps which modes are stable vs unstable, **but not their rates**.
- **O5.3 Hopf has an exact one-dimensional dark fibre.** Left multiplication `x ↦ qx` is an exact similarity (`L_qᵀL_q = |q|²I` with `|q|² = 25/4`), so it is a dark-mode-free converter on `ℚ⁴`. The Hopf readout `h(q) = q i q̄` gives `h(q) = (15/4, −3, 4)` with `|h| = |q|²`, and it is **exactly invariant** along the rational `S¹` fibre `q·(a + bi)` for the Pythagorean pairs `(3/5, 4/5)`, `(5/13, 12/13)` and `(8/17, 15/17)`, while moving off-fibre. Any `S³ → S²` readout loses exactly the phase.

### Bridge to the active spine
- **`PREREG-S109` external converter and zero-language minimal-medium core:** Portal 5 gives the exact bookkeeping. With a linearised converter `A`, the irrecoverable mass is `‖P_{ker A} x‖²`, and the dark dimension is `n − rank A`. A spectral match between converter-side and core-side operators (O5.1) is not evidence of losslessness on its own. The `CB-*` contracts should log the dark-mode mass directly.
- **`H6`/`H7` Hopf-`S³` coding:** an `S²`-valued readout of an `S³` core has an exact 1-dimensional dark fibre (O5.3). Phase-carried information needs a phase-sensitive readout, or it is lost by construction.
- **ADM lapse/shift:** per-layer positive rescaling (lapse-like step schedules) keeps the stability signature (O5.2). Claims that a schedule "preserves dynamics" are true for inertia only.

---

## 4. `SOP-12` preregistration candidates (falsifiable, **not yet registered or SHA-locked**)

**Candidate A: `TURING-BAND-H8b` (Portal 2 → `PREREG-S108` H8b)**
- *Design:* a 2-channel activator/inhibitor boundary layer on byte positions, with learnable `(J, D)` constrained to `tr J < 0` and `det J > 0`. Arms: (i) free `D`, (ii) equal `D = dI` (the O2.1 null arm), (iii) the standard `H8b` cosine router baseline. Matched params and FLOPs.
- *Exact pre-gate:* after training, the learned `(J, D)` must satisfy the Turing conditions, and the Sturm band count on the ring/path Laplacian of each sequence length must be > 0 wherever boundaries nucleate.
- *Prediction:* arm (i) beats arm (ii) on bits-per-byte by a pre-set margin, and the learned mean boundary period lies inside the exact interval `360°/θ` implied by the learned band.
- *Falsifier:* arm (ii) matches arm (i) within the margin, **or** boundaries nucleate where the exact band count is 0 (meaning nucleation is driven by something other than the linear Turing mechanism).

**Candidate B: `COMMUTING-HELICITY-LOOP` (Portal 3 → `H7c`, plus a Portal 5 dark-mode ledger for `S109`)**
- *Design:* a depth-looped core whose recurrent transport is a 2×2-block Cayley-orthogonal operator, in three arms: (i) constrained to `[C,K] = 0` for a fixed symmetric shell operator `C`, (ii) unconstrained orthogonal, (iii) symmetric residual `I + αC`. Matched params and FLOPs. Loop depths are `{1, 4, 16, 32}`.
- *Exact contract:* in arm (i), the per-shell occupancy `m_j` drift is 0 in exact rational replay, with an FP32 drift bound stated in advance. Arm (iii) must show strictly increasing `H/E` (O3.5).
- *Prediction:* the effective rank of the hidden state at depth 32 is ≥ 0.9× its depth-1 value in arm (i), and collapses in arm (iii). Arm (i) loses no more than a preset margin in task loss vs arm (ii).
- *Secondary S109 ledger:* for the linearised converter, the measured reconstruction error must equal `‖P_{ker A}x‖²` within FP32 tolerance. Any excess counts as nonlinear leakage and gets reported.
- *Falsifier:* arm (i) collapses anyway, **or** arm (iii) does not collapse at depth 32, **or** arm (i)'s task-loss penalty exceeds the margin. Any of these would show that shell conservation is not the operative no-collapse mechanism.

---

## 5. Verification receipts
- `python3 -I -B verify_portals_2_3_5_exact.py`, `-I -O -B` and `-I -B -W error`: **44/44 PASS ×3**, with an identical receipt `ead0952b…7379` across modes.
- Mutation controls: **7/7 killed**, with 0 survivors (equal diffusion, curl sign flip, Euler instead of Cayley, wrong Darboux shift `c + 1/1000`, a sign-indefinite lapse, a dropped polar sign in parity, a shifted band endpoint). Each turns at least one check to FAIL with exit code 1. The dropped-parity-sign mutant survived the first run, because `PCP = −C` alone does not pin the sign of `P`. The `P∘grad = grad∘R` check was added to kill it.
- Dual `aletheia audit-check --strict-ancestors --safety-scan` (`aletheia-fix-lean-gates-v2` and `aletheia-fast-mutate`) on this directory: PASS ×2 (`bare_assert=0`, `crlf=0`, `leak=0`, `pycache=0`).
