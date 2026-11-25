# Track S112 — Natural Systems Stage-B Conservation Laws & Obstructions (Pure-Init Lean 4.36.0 + Wave-10 Exact Oracle)

- **Track ID:** `track-s112-natural-systems-stage-b-lean`
- **Schema Version:** `aletheia.track_s112.natural_systems_stage_b.v1`
- **Novelty Grade:** `N1` (`n2_claims = 0`; constructive algebraic formalization + exact rational witnesses + fail-closed verifier; zero empirical GPU claims)
- **Lean Toolchain:** `leanprover/lean4:v4.36.0` (pure `Init`, `0` external imports, `0` Mathlib, `0` warnings, `0` bytes stderr)
- **Theorem Inventory (`NaturalSystemsConservation.lean`):** **`34`** public `#print axioms` theorems + **`23`** `private theorem` algebraic helper lemmas = **`57`** total theorem declarations (`3` zero-axiom `[]`, `31` `[propext, Quot.sound]`, `0` `Classical.choice`, `0` `sorryAx`)
- **Pinned Certificate Digest (`s112_natural_systems_certificate.json`, `0o644` in git / 100644):**
  - `payload_sha256`: `53806ade9dccb82c96c6060398582557d0440aa903036d94f1da37e009975675`
  - `certificate_sha256`: `9e033515d9b57ecb7224ece61f73bf3bb467e58b572f5bea2d4c65258e4c3b79`

---

## 1. Scope & Pinned Stage-B Provenance

Track S112 mechanizes the conservation laws and Law-5 structural obstructions across all **5 Natural Systems Stage-B Portals** in pure-`Init` Lean `4.36.0` alongside a pure-`int`/`Fraction` oracle (`s112_natural_systems_oracle.py`) and Wave-10 fail-closed verifier (`verify_natural_systems_lean.py`).

All four Stage-B source artifacts are pinned by repo-relative path and SHA-256, but the files **resolve nowhere** (no branch or PR head of siliquant, math0, cave-expedition or aletheia carries them; verified by blob-sha256 and filename search on 2026-11-25). `--verify-pins` therefore reports **`PINS_UNVERIFIABLE` (`external=0 unverifiable=4`)** — reported loudly (rc 0), never silently skipped, never claimed `PINS_OK`:

| Pin ID | Repo-Relative Path | SHA-256 |
|---|---|---|
| `PORTALS_1_4_STAGE_B_DOC` | `notes/natural_systems_stage_b_2026_11_25/PORTALS_1_4_HOMEOSTASIS_PHYSARUM_STAGE_B.md` | `b33ab3aa1cecc0c8a2fdc4c69b1c511e24965836268f7cdc83351307d41b9c33` |
| `PORTALS_2_3_5_STAGE_B_DOC` | `notes/natural_systems_stage_b_2026_11_25/PORTALS_2_3_5_TURING_BELTRAMI_DARBOUX_STAGE_B.md` | `d9a8f6909227e5228a208d249f91b8ebbaf93c58cc9b793a29a249e0a9fa1b32` |
| `PORTALS_1_4_EXACT_SCRIPT` | `notes/natural_systems_stage_b_2026_11_25/verify_portals_1_4_exact.py` | `b6cf5fef3f9dad52f2fab56c9278f27c01c61146249c0019a2e70df44fdcc19d` |
| `PORTALS_2_3_5_EXACT_SCRIPT` | `notes/natural_systems_stage_b_2026_11_25/verify_portals_2_3_5_exact.py` | `422c0d87060a2673c360a1e9a9f4881de3c3dfe0b71050870d8000cdfec98107` |

**Honest Scope Boundary (`N1`):**
- All 34 Lean theorems prove universal (`∀`) algebraic identities, inequalities, and exact integer/rational counterexamples over `Int` and `Nat`.
- No empirical training curves, hardware claims, or physical biological claims beyond the exact operator abstractions are asserted (`n2_claims = 0`).
- Where Portal 1 references Track S102 MaleCNS synapse totals (`36,739,597` E + `23,661,623` I = `60,401,220`, CX net balance `-428,494`) and Portal 2 references cycle spectra (`C_4`, `C_6`), those finite tables are copied from the S102 MaleCNS certificate and cross-checked fail-closed against its sha256-pinned values in the verifier (`SEC_P1_DALE_S102`, `S102_CERT_SHA256 = 5238ce3f…`) while the discrete integer LIF Lyapunov law is strengthened in Lean from a bounded `26 × 26` grid to an **unbounded universal theorem over all `v, g : Nat`** (`p1_lif_lyapunov_universal_2step_lasalle`).

---

## 2. Verbatim 34-Theorem Inventory (`NaturalSystemsConservation.lean`)

Every public theorem is checked by `#print axioms` under a scrubbed `env -i` Lean `4.36.0` subprocess (`0` warnings, `0` bytes stderr, `0` `Classical.choice`, `0` `sorryAx`).

### Portal 1 — Homeostasis, Sleep Renormalization & Integer LIF (`7` Theorems)

| # | Lean Theorem Name (`NaturalSystemsConservation.*`) | Axioms | What Lean Proves (Exact Statement Scope) |
|---|---|---|---|
| 1 | `p1_mult_crow_invariance` | `[propext, Quot.sound]` | For all `lam ≠ 0` and integer norms/bounds, `rowNormSq * cDen ≤ cNum * totalNormSq ↔ (lam² * rowNormSq) * cDen ≤ cNum * (lam² * totalNormSq)` (exact multiplicative `C_row` gate invariance). |
| 2 | `p1_subtractive_bingham_crow_breach_and_nonadd` | `[]` | On Pythagorean rows `[(3,4), (0,3)×3]`, initial `C_row = 25/52 ≤ 1/2`, whereas subtractive Bingham shrinkage at `τ = 3` spikes `C_row` to `1 > 1/2` and breaks additivity (`bingham 3 (3 + 3) ≠ bingham 3 3 + bingham 3 3`). |
| 3 | `p1_blockh4_isotropic_commutes_anisotropic_breaches` | `[propext, Quot.sound]` | For all `lam : Int`, isotropic `diag4 lam lam lam lam` commutes identically with `had4`, whereas anisotropic `diag4 4 1 1 1` fails to commute (`commMat 4 had4 (diag4 4 1 1 1) 0 1 ≠ 0`). |
| 4 | `p1_isotropic_dark_mode_commutation` | `[propext, Quot.sound]` | For every dimension `n`, scalar `lam`, and matrices `G, P, X` with `P X = 0`, `scaleMat lam (G P) X = 0` identically (zero base forgetting). |
| 5 | `p1_anisotropic_input_shatters_nullspace` | `[]` | On rank-2 `X_base` and dark projector `2 P_perp`, `P_perp X_base = 0` at `(0,0)`, whereas input-side anisotropic `diag4 4 1 1 1` gives `(P_perp D X_base)_{0,0} ≠ 0`. |
| 6 | `p1_mult_safety_margin_crossing_and_cos_repair` | `[propext, Quot.sound]` | Scaling witness `3/4 * 5/2 = 15/8` stays positive yet drops below nonzero yield wall `τ = 2` (`15 < 16 ∧ 0 < 15`), while for all `lam ≠ 0` both the squared cosine cross-product `(lam * dotVal)² * normSq = dotVal² * (lam² * normSq)` and its threshold gate `dotVal² * cDen ≤ cNum * normSq ↔ (lam * dotVal)² * cDen ≤ cNum * (lam² * normSq)` are identically invariant. |
| 7 | `p1_lif_lyapunov_universal_2step_lasalle` | `[propext, Quot.sound]` | Universally for all `v, g : Nat` (`lifE v g = 4v + g`, `v1 = (19v + g)/20`, `g1 = 4g/5`): (1) 1-step `E(v1,g1) ≤ E(v,g)`, (2) lossless 1-step tie at `(0, 20)`, (3) strict 2-step contraction `E(v2,g2) < E(v,g)` for every `(v,g) ≠ (0,0)`. |

### Portal 2 — Turing Morphogenesis & Discrete Reaction-Diffusion (`6` Theorems)

| # | Lean Theorem Name (`NaturalSystemsConservation.*`) | Axioms | What Lean Proves (Exact Statement Scope) |
|---|---|---|---|
| 8 | `p2_equal_diffusion_turing_impossible` | `[propext, Quot.sound]` | Obstruction `O2.1`: if `tr(J) < 0` and `det(J) > 0`, then for all `d ≥ 0` and `μ ≥ 0`, `tr(J - dμI) < 0` and `det(J - dμI) > 0` identically. |
| 9 | `p2_turing_trace_stays_negative` | `[propext, Quot.sound]` | Under `tr(J) < 0` and `du, dv, μ ≥ 0`, coupled mode trace `(j11 - du*μ) + (j22 - dv*μ) < 0`. |
| 10 | `p2_turing_instability_necessity` | `[propext, Quot.sound]` | If stable `J` (`tr < 0`, `det > 0`) has `det(J - μD) < 0` for `du, dv, μ ≥ 0`, then necessarily `dv*j11 + du*j22 > 0`, `du ≠ dv`, and `j11 * j22 < 0`. |
| 11 | `p2_mode_factorization_identity` | `[propext, Quot.sound]` | In arbitrary dimension `n`, on any Laplacian eigenmode `L q = μ q`, the coupled 2-channel operator `(I_n ⊗ J - L ⊗ D)` factors pointwise onto the 2×2 matrix `(J - μD)` times `q_i`. |
| 12 | `p2_witness_band_exact_factorization` | `[propext, Quot.sound]` | Obstruction `O2.2`: for all `μ : Int`, `20μ² - 120μ + 175 = 5(2μ - 5)(2μ - 7)`; mode `μ = 3` (on `C_6`) is strictly negative (`-5 < 0`), while `C_4` modes `{0, 2, 4}` are all strictly positive. |
| 13 | `p2_complete_graph_all_or_none_spectrum` | `[propext, Quot.sound]` | Obstruction `O2.3`: for the explicit `K_n` Laplacian matrix `completeLap n` (`n-1` on diagonal, `-1` off-diagonal) via `matVec`, (1) every constant vector `(c, ..., c)` has exact eigenvalue `0` (`matVec n (completeLap n) (fun _ => c) i = 0` for all `i < n`), and (2) every zero-sum vector (`sumN n x = 0`) has identical degenerate eigenvalue `n` (`matVec n (completeLap n) x i = n * x i` for all `i < n`). |

### Portal 3 — Beltrami Force-Free Helicity Conservation & Obstructions (`7` Theorems)

| # | Lean Theorem Name (`NaturalSystemsConservation.*`) | Axioms | What Lean Proves (Exact Statement Scope) |
|---|---|---|---|
| 14 | `p3_commutator_sym_of_sym_skew` | `[propext, Quot.sound]` | In any dimension `n`, for symmetric `C` and skew-symmetric `K`, `[C, K] = C K - K C` is symmetric. |
| 15 | `p3_helicity_conservation_of_commuting` | `[propext, Quot.sound]` | For symmetric `C`, skew `K`, and any `v` in dimension `n`, `2 ⟨Kv, Cv⟩ = ⟨v, [C,K]v⟩`; hence `[C, K] = 0 → ⟨Kv, Cv⟩ = 0`. |
| 16 | `p3_helicity_conservation_iff_commuting` | `[propext, Quot.sound]` | Constructive polarization iff in any dimension `n`: `(∀ v, ⟨Kv, Cv⟩ = 0) ↔ MatComm n C K`. |
| 17 | `p3_cayley_preserves_energy_and_helicity` | `[propext, Quot.sound]` | For symmetric `C`, skew `K` with `[C,K] = 0`, `s ≠ 0`, and Cayley step `(sI + K)y = (sI - K)x`, both `‖y‖² = ‖x‖²` and `⟨y, Cy⟩ = ⟨x, Cx⟩`. |
| 18 | `p3_cayley_preserves_all_moments` | `[propext, Quot.sound]` | Obstruction `O3.1`: under `[C,K] = 0`, the Cayley step preserves every moment `⟨y, C^j y⟩ = ⟨x, C^j x⟩` for all `j : Nat` (zero linear cross-shell cascade). |
| 19 | `p3_parity_flips_helicity` | `[propext, Quot.sound]` | Obstruction `O3.2`: any symmetric parity operator `P` with `P C P = -C` satisfies `⟨Pv, C(Pv)⟩ = -⟨v, Cv⟩` for every `v`. |
| 20 | `p3_symmetric_residual_rayleigh_increase` | `[propext, Quot.sound]` | Obstruction `O3.5`: in any diagonal eigenbasis with `c > 0` and `2 + c(λ_i + λ_j) ≥ 0`, the symmetric residual step `w_i = (1 + cλ_i)v_i` satisfies `H(v)E(w) ≤ H(w)E(v)` (Rayleigh collapse). |

### Portal 4 — Murray's Law, Schur-Thomson, Physarum & Braess (`7` Theorems)

| # | Lean Theorem Name (`NaturalSystemsConservation.*`) | Axioms | What Lean Proves (Exact Statement Scope) |
|---|---|---|---|
| 21 | `p4_plato_murray_trifurcation` | `[propext, Quot.sound]` | Exact Plato cube law `3³ + 4³ + 5³ = 6³` and SOS certificate `216² + 2u³ - 108u² = 2(u - 36)²(u + 18) ≥ 0` for all `u > 0`. |
| 22 | `p4_murray_general_sos_optimality` | `[propext, Quot.sound]` | Universal Murray SOS optimality for every `r : Int` and `u > 0` (`q = r³`, `r2 = r²`): `q² + 2u³ - 3 r² u² = (u - r²)²(2u + r²) ≥ 0`. |
| 23 | `p4_thomson_dirichlet_minimum_power` | `[propext, Quot.sound]` | For symmetric PSD interior block `L` and equilibrium `L φ = rhs` in any dimension `n`, `quad(φ + δ) = quad(φ) + ⟨δ, L δ⟩ ≥ quad(φ)`. |
| 24 | `p4_physarum_gamma1_global_ratio_increase` | `[propext, Quot.sound]` | For all `D1, D2 > 0` on lengths `(1, 2)`, `γ = 1` Physarum reinforcement strictly increases `D1'/D2' > D1/D2`. |
| 25 | `p4_physarum_gamma2_separatrix_lockin` | `[propext, Quot.sound]` | Obstruction `P4-O1`: for all `D1, D2 > 0`, two-sided separatrix instability at `D2 = 4 D1`: (1) `D2 > 4 D1 → D1'/D2' < D1/D2` (suboptimal lock-in), (2) `D2 < 4 D1 → D1'/D2' > D1/D2` (optimal basin), and (3) exact unstable fixed point `(1/9, 4/9)`. |
| 26 | `p4_rayleigh_vs_braess_separation` | `[]` | Obstruction `P4-O2`: exact integer cross-products separating Ohmic Wheatstone resistance reduction (`4/3 < 43/32 < 3/2`, reduction `3/2 - 43/32 = 5/32`) from selfish Wardrop Braess degradation (`3/2 → 2`, penalty `+1/2`). |
| 27 | `p4_physarum_tree_portal_b_density_chasm` | `[propext, Quot.sound]` | Obstruction `P4-O3`: for all `n0 ≥ 2001`, Portal-B density ratio satisfies the sharp two-sided bound `1000 < m_PB / m_tree ≤ 2001/2` (`1000(n0 - 1) < 1000 n0` and `2(1000 n0) ≤ 2001(n0 - 1)`), tight at `n0 = 2001`, plus backup floor `32/33 < 1`. |

### Portal 5 — Darboux Isospectrality, Dark Modes, One-Sided Lapse Trace & Hopf Fiber (`7` Theorems)

| # | Lean Theorem Name (`NaturalSystemsConservation.*`) | Axioms | What Lean Proves (Exact Statement Scope) |
|---|---|---|---|
| 28 | `p5_darboux_intertwining` | `[propext, Quot.sound]` | Universally for all `m, n : Nat`, `m × n` matrix `A`, and shift `c : Int`: `A(AᵀA + cI_n) = (AAᵀ + cI_m)A`. |
| 29 | `p5_darboux_eigenvector_transport_and_norm` | `[propext, Quot.sound]` | If `L1 v = λ v`, then `L2 (A v) = λ (A v)` and `‖A v‖² = (λ - c)‖v‖²` identically. |
| 30 | `p5_dark_mode_kernel_collision_and_orthogonality` | `[propext, Quot.sound]` | For any `k ∈ ker(A)`: (1) `A(x + k) = A x`, (2) `L1 k = c k`, (3) `⟨Aᵀ y, k⟩ = 0` for all `x, y`. |
| 31 | `p5_kernel_reconstruction_loss_lower_bound` | `[propext, Quot.sound]` | For `x = Aᵀ y_opt + x_ker` (`x_ker ∈ ker(A)`) and any `y`, `‖x - Aᵀ y‖² = ‖Aᵀ(y_opt - y)‖² + ‖x_ker‖² ≥ ‖x_ker‖²`. |
| 32 | `p5_sylvester_congruence_sign_preservation` | `[propext, Quot.sound]` | Obstruction `O5.2`: exact bilinear quadratic-form sign/definiteness congruence `⟨v, (D L D)v⟩ = ⟨Dv, L(Dv)⟩` for any diagonal scaling `D` and `L` in any dimension `n`, while the second and third conjuncts are closed integer literals on `L = diag(1, -1)`, `D = diag(2, 3)` (`1 + (-1) ≠ 8 - 9` and `1 + (-1) ≠ 2 - 3`, proved by `omega`) — illustrative trace arithmetic `tr(DLD) = -5 ≠ 0`, `tr(DL) = -1 ≠ 0`, not structural trace theorems; the structural content is conjunct 1, the bilinear congruence identity. The name `sylvester_…_sign_preservation` overstates it (this is not Sylvester's law of inertia). |
| 33 | `p5_singular_susy_distinct_zero_modes` | `[propext, Quot.sound]` | Obstruction `O5.1`: on the `5 × 5` singular SUSY factor `2A`, `k1 = (-2,-1,-2,2,3) ∈ ker(A)` and `k2 = e_5 ∈ ker(Aᵀ)`, yet `Aᵀ k1 ≠ 0` and `A k2 ≠ 0`. |
| 34 | `p5_hopf_dark_fiber_phase_invariance` | `[propext, Quot.sound]` | Obstruction `O5.3`: for all `q = (q0,q1,q2,q3)` and any Pythagorean `a² + b² = D²`, right `S¹` fiber multiplication `q(a + bi)` scales all three Hopf `S²` coordinates `h(q) = q i q̄` identically by `D²`. |

**Private Constructive Helpers (`23` `private theorem` declarations):** `int_sq_nonneg`, `int_sq_pos_of_ne_zero`, `int_mul_le_left_nonneg`, `int_mul_cancel_left_nz`, `sumN_congr`, `sumN_zero`, `sumN_add`, `sumN_sub`, `sumN_neg`, `sumN_mul_left`, `sumN_mul_right`, `sumN_comm`, `sumN_nonneg`, `sumN_kronecker_right`, `sumN_kronecker_left`, `dotN_comm`, `dotN_matVecRect_adj`, `matVec_sym_adj`, `matVec_matMul`, `matMul_assoc`, `dotN_matVec_skew_zero`, `matPow_comm_self`, `matPow_sym_and_comm`.

---

## 3. Exact Verification & Wave-10 Hardening Receipts

| Gate | Command / Harness | Exact Result |
|---|---|---|
| Live Pure-Init Lean `4.36.0` | `verify_natural_systems_lean.py --verify-lean --json` | **`34/34` theorems verified**, `rc = 0`, `stderr = 0 B`, `0` warnings, `18/18` static rules PASS, `0` `Classical.choice`, `0` `sorryAx` |
| External Stage-B Pins | `verify_natural_systems_lean.py --verify-pins --json` | **`PINS_UNVERIFIABLE` (`external=0 unverifiable=4`)** — files not shipped in any reachable repo; reported loudly (rc 0), not skipped |
| Standalone Byte Parity | `s112_natural_systems_oracle.py --standalone \| cmp -s - s112_natural_systems_certificate.json` | **PASS (`0` byte diff; mode `0o644` in git / 100644)** |
| Direct v2.1 Zone-B Fuzzer (4 Surfaces) | `aletheia-v21-upgrades` (`fuzz_cli_checker` + `fuzz_python_validator` on `FR1`, `FR0`, `SEC`) | **`82/82` PASS** (`cli 25/25`, `FR1 19/19`, `FR0 19/19`, `SEC 19/19`, `bypasses = 0`, `crashes = 0`) — **unshipped harness, not replayable from stock CLI** |
| `aletheia mutate` | stock CLI: `--guards require_ok --max-mutants 0 --json` | oracle **`21/21` KILLED** reproduced; verifier 30/30-sample KILLED of 186 sites. Claimed `207/207` used unshipped `aletheia-fast-mutate` (`--workers` is not a stock flag) — **not replayable from stock CLI** |
| Whole-File AST `BoolOp` (`OP_SWAP + SUBCOND_DEL`) | Isolated tempdir copy sweep across both `.py` targets | **`28/28` (`100.0%` KILLED, `0` survived)** — unshipped sweep harness, not replayable from stock CLI |
| R5 Adversarial Suite (`test_natural_systems_lean_r5.py`) | `177 × 3 = 531` re-signed leaf sweeps (`caller_immutable = True`), `54` `SEC_*` codes + exact boundaries, `18` static Lean rules + `X1..X3`, live `Init.olean` hijack, `4,500`-digit/`10^5000` DoS | **`15/15 OK`, `0` skips** across all 3 R4 isolated modes (`-I -B`, `-I -O -B`, `-I -B -W error`), combined optimize+warnings-as-error, `PYTHONHASHSEED=42`, `env -i HOME=/nonexistent` (direct `lean 4.36.0` bin), and RO-dir (`chmod -R a-w`) |

---

## 4. Companion Artifact Manifest (8 Companion Files; `REPORT.md` Self-Excluded)

| File | Lines | Bytes | SHA-256 |
|---|---:|---:|---|
| `lean-toolchain` | `1` | `25` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |
| `lakefile.toml` | `5` | `134` | `7cda47ebd1198c1dce3bf8f8884f530286d673bc4ee18ea9d2aa4a0aa4bc6ac7` |
| `NaturalSystemsConservation.lean` | `1,729` | `94,542` | `0f2accb66c6beed16cde96b9b11fdbfbae7d27a5e23bb4070de4835abf65090b` |
| `s112_natural_systems_oracle.py` | `854` | `33,983` | `57ca0ceca2e14c2bab1d37d4a7148984c9b7e912db3447dc1ef99c70669a2637` |
| `verify_natural_systems_lean.py` | `801` | `35,746` | `a6aee11f0ae4a31eec1ff3d4ba1eea1916e25dd7cfce0ecbc0f13a46ad0a92bf` |
| `test_natural_systems_lean_r5.py` | `813` | `44,214` | `1cd9c1738516804ee8dcb0704b74750ef45de0012815a49339bd06acef165ae4` |
| `s112_natural_systems_audit.py` | `20` | `564` | `a92f9acdc14f8a4e0eb2c66d26cd07f6b459bf3f697ec9cdca3a84953b464818` |
| `s112_natural_systems_certificate.json` | `1` | `7,421` | `93c550316c5b65bc43f196469fba20892d088a9777f80f10b6b0ebc6727b6217` |
