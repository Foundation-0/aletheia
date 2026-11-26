# Track S112 — Natural Systems Stage-B Conservation Laws & Obstructions (Pure-Init Lean 4.36.0 + Wave-10 Exact Oracle)

- **Track ID:** `track-s112-natural-systems-stage-b-lean`
- **Schema Version:** `aletheia.track_s112.natural_systems_stage_b.v1`
- **Novelty Grade:** `N1` (`n2_claims = 0`; constructive algebraic formalization + exact rational witnesses + fail-closed verifier; zero empirical GPU claims)
- **Lean Toolchain:** `leanprover/lean4:v4.36.0` (pure `Init`, `0` external imports, `0` Mathlib, `0` warnings, `0` bytes stderr)
- **Theorem Inventory (`NaturalSystemsConservation.lean`):** **`34`** public `#print axioms` theorems + **`23`** `private theorem` algebraic helper lemmas = **`57`** total theorem declarations (`2` zero-axiom `[]`, `32` `[propext, Quot.sound]`, `0` `Classical.choice`, `0` `sorryAx`)
- **Pinned Certificate Digest (`s112_natural_systems_certificate.json`, `0o644` in git / 100644):**
  - `payload_sha256`: `e6fbc1dfe5ca8d225d85a73798000efe4a9707fcf8feba912ebeb837abc4fa1a`
  - `certificate_sha256`: `b1d47d1efe006052cb8d3b952a5e07db2a0200bc9fef283f588e96b5308de076`

---

## 1. Scope & Pinned Stage-B Provenance

Track S112 mechanizes the conservation laws and Law-5 structural obstructions across all **5 Natural Systems Stage-B Portals** in pure-`Init` Lean `4.36.0` alongside a pure-`int`/`Fraction` oracle (`s112_natural_systems_oracle.py`) and Wave-10 fail-closed verifier (`verify_natural_systems_lean.py`).

All four Stage-B source artifacts are shipped in-repo under `evidence/notes/natural_systems_stage_b_2026_11_25/` and verified byte-for-byte against their pinned SHA-256 digests via `--verify-pins` (**`PINS_OK` (`external=4 unverifiable=0`)**, `rc = 0`):

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
| 6 | `p1_mult_safety_margin_crossing_and_cos_repair` | `[propext, Quot.sound]` | For all `0 < sNum < sDen` and `mNum > 0`, scaling preserves positive sign (`0 < sNum * mNum`) while strictly contracting (`sNum * mNum < sDen * mNum`), admits existential yield-wall crossing (`∃ a b m d τ` with `τ * d < m` yet `a * m < b * (τ * d)`), and for all `lam ≠ 0` preserves squared cosine cross-product and its threshold gate (`iff`). |
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
| 25 | `p4_physarum_gamma2_separatrix_lockin` | `[propext, Quot.sound]` | Obstruction `P4-O1`: for all `D1, D2 > 0` and `scale : Int`, two-sided separatrix instability at `D2 = 4 D1`: (1) `D2 > 4 D1 → D1'/D2' < D1/D2` (suboptimal lock-in), (2) `D2 < 4 D1 → D1'/D2' > D1/D2` (optimal basin), (3) `D2 = 4 D1 → D1'/D2' = D1/D2`, and (4) `physarumGamma2FixedPoint D1 (4 D1) scale ↔ scale = 9 D1` (uniquely pinning `(1/9, 4/9)`). |
| 26 | `p4_rayleigh_vs_braess_separation` | `[propext, Quot.sound]` | Obstruction `P4-O2`: for all `g1 ≤ g2` and node potentials `φ`, `wheatstoneDirichlet2 g1 φ ≤ wheatstoneDirichlet2 g2 φ`, `R_eff(g_b) = (3 + 4g_b)/(2 + 3g_b)` strictly decreases for `g1 < g2` with `R_eff(g_b) > 4/3`, while concrete 4-node Braess demand `F = 2` latency increases from `braessSideLatency 1 = 3` to `braessZigzagLatency 2 = 4`. |
| 27 | `p4_physarum_tree_portal_b_density_chasm` | `[propext, Quot.sound]` | Obstruction `P4-O3`: for all `n0 ≥ 2001` and `gMain, gFloor > 0`, `1000 * spanningTreeEdges n0 < portalBMinEdges n0`, `2 * portalBMinEdges n0 ≤ 2001 * spanningTreeEdges n0`, exact tightness `2 * portalBMinEdges n0 = 2001 * spanningTreeEdges n0 ↔ n0 = 2001`, and positive backup survival `gMain < gMain + gFloor ∧ gFloor < gMain + gFloor ∧ 0 < gFloor`. |

### Portal 5 — Darboux Isospectrality, Dark Modes, One-Sided Lapse Trace & Hopf Fiber (`7` Theorems)

| # | Lean Theorem Name (`NaturalSystemsConservation.*`) | Axioms | What Lean Proves (Exact Statement Scope) |
|---|---|---|---|
| 28 | `p5_darboux_intertwining` | `[propext, Quot.sound]` | Universally for all `m, n : Nat`, `m × n` matrix `A`, and shift `c : Int`: `A(AᵀA + cI_n) = (AAᵀ + cI_m)A`. |
| 29 | `p5_darboux_eigenvector_transport_and_norm` | `[propext, Quot.sound]` | If `L1 v = λ v`, then `L2 (A v) = λ (A v)` and `‖A v‖² = (λ - c)‖v‖²` identically. |
| 30 | `p5_dark_mode_kernel_collision_and_orthogonality` | `[propext, Quot.sound]` | For any `k ∈ ker(A)`: (1) `A(x + k) = A x`, (2) `L1 k = c k`, (3) `⟨Aᵀ y, k⟩ = 0` for all `x, y`. |
| 31 | `p5_kernel_reconstruction_loss_lower_bound` | `[propext, Quot.sound]` | For `x = Aᵀ y_opt + x_ker` (`x_ker ∈ ker(A)`) and any `y`, `‖x - Aᵀ y‖² = ‖Aᵀ(y_opt - y)‖² + ‖x_ker‖² ≥ ‖x_ker‖²`. |
| 32 | `p5_sylvester_congruence_sign_preservation` | `[propext, Quot.sound]` | Obstruction `O5.2`: universal `n`-dimensional bilinear congruence identity `⟨v, (D L D)v⟩ = ⟨Dv, L(Dv)⟩` for any diagonal scaling `D` and `L` (not full Sylvester law of inertia, which the theorem name overstates), paired with explicit `2 × 2` `traceMat` evaluations on `lapseWitnessL = diag(1, -1)` and `lapseWitnessD = diag(2, 3)` (`traceMat 2 L = 0`, `traceMat 2 (congMat D L) = -5`, `traceMat 2 (scaleRowMat D L) = -1`). |
| 33 | `p5_singular_susy_distinct_zero_modes` | `[propext, Quot.sound]` | Obstruction `O5.1`: on the `5 × 5` singular SUSY factor `2A`, `k1 = (-2,-1,-2,2,3) ∈ ker(A)` and `k2 = e_5 ∈ ker(Aᵀ)`, yet `Aᵀ k1 ≠ 0` and `A k2 ≠ 0`. |
| 34 | `p5_hopf_dark_fiber_phase_invariance` | `[propext, Quot.sound]` | Obstruction `O5.3`: for all `q = (q0,q1,q2,q3)` and any Pythagorean `a² + b² = D²`, right `S¹` fiber multiplication `q(a + bi)` scales all three Hopf `S²` coordinates `h(q) = q i q̄` identically by `D²`. |

**Private Constructive Helpers (`23` `private theorem` declarations):** `int_sq_nonneg`, `int_sq_pos_of_ne_zero`, `int_mul_le_left_nonneg`, `int_mul_cancel_left_nz`, `sumN_congr`, `sumN_zero`, `sumN_add`, `sumN_sub`, `sumN_neg`, `sumN_mul_left`, `sumN_mul_right`, `sumN_comm`, `sumN_nonneg`, `sumN_kronecker_right`, `sumN_kronecker_left`, `dotN_comm`, `dotN_matVecRect_adj`, `matVec_sym_adj`, `matVec_matMul`, `matMul_assoc`, `dotN_matVec_skew_zero`, `matPow_comm_self`, `matPow_sym_and_comm`.

---

## 3. Exact Verification & Wave-10 Hardening Receipts

| Gate | Command / Harness | Exact Result |
|---|---|---|
| Live Pure-Init Lean `4.36.0` | `verify_natural_systems_lean.py --verify-lean --json` | **`34/34` theorems verified**, `rc = 0`, `stderr = 0 B`, `0` warnings, `18/18` static rules PASS, `0` `Classical.choice`, `0` `sorryAx` |
| External Stage-B Pins | `verify_natural_systems_lean.py --verify-pins --json` | **`PINS_OK` (`external=4 unverifiable=0`)** — all 4 Stage-B source files shipped under `evidence/notes/natural_systems_stage_b_2026_11_25/` and verified byte-exact (`rc = 0`) |
| Standalone Byte Parity | `s112_natural_systems_oracle.py --standalone \| cmp -s - s112_natural_systems_certificate.json` | **PASS (`0` byte diff; mode `0o644` in git / 100644)** |
| Direct v2.1 Zone-B Fuzzer (4 Surfaces) | `aletheia-v21-upgrades` (`fuzz_cli_checker` + `fuzz_python_validator` on `FR1`, `FR0`, `SEC`) | **`82/82` PASS** (`cli 25/25`, `FR1 19/19`, `FR0 19/19`, `SEC 19/19`, `bypasses = 0`, `crashes = 0`) — **unshipped harness, not replayable from stock CLI** |
| `aletheia mutate` | stock CLI: `--guards require_ok --max-mutants 0 --json` | oracle **`21/21` KILLED** reproduced; verifier 30/30-sample KILLED of 189 sites. Claimed `207/207` used unshipped `aletheia-fast-mutate` (`--workers` is not a stock flag) — **not replayable from stock CLI** |
| Whole-File AST `BoolOp` (`OP_SWAP + SUBCOND_DEL`) | Isolated tempdir copy sweep across both `.py` targets | **`28/28` (`100.0%` KILLED, `0` survived)** — unshipped sweep harness, not replayable from stock CLI |
| R5 Adversarial Suite (`test_natural_systems_lean_r5.py`) | `177 × 3 = 531` re-signed leaf sweeps (`caller_immutable = True`), `54` `SEC_*` codes + exact boundaries, `18` static Lean rules + `X1..X3`, live `Init.olean` hijack, `s112_natural_systems_audit.py` CLI/tamper wrapper coverage, partial-ship pin checks, `4,500`-digit/`10^5000` DoS | **`16/16 OK`, `0` skips** across all 3 R4 isolated modes (`-I -B`, `-I -O -B`, `-I -B -W error`), combined optimize+warnings-as-error, `PYTHONHASHSEED=42`, `env -i HOME=/nonexistent` (direct `lean 4.36.0` bin), and RO-dir (`chmod -R a-w`) |

---

## 4. Companion Artifact Manifest (8 Companion Files; `REPORT.md` Self-Excluded)

| File | Lines | Bytes | SHA-256 |
|---|---:|---:|---|
| `lean-toolchain` | `1` | `25` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |
| `lakefile.toml` | `5` | `134` | `7cda47ebd1198c1dce3bf8f8884f530286d673bc4ee18ea9d2aa4a0aa4bc6ac7` |
| `NaturalSystemsConservation.lean` | `1,883` | `101,878` | `1bed1aa1bc7fbdf88036874c9f55824010270b3892b825440a3ef236a7b0d719` |
| `s112_natural_systems_oracle.py` | `851` | `33,810` | `8c753d26a1b1ef199de775c38e168cfe96979f825d5141267d035260cd5fb433` |
| `verify_natural_systems_lean.py` | `801` | `35,800` | `2c05147c91b100baacc81414cb4caa7e7b545ec18646c184fda91e6db987f0de` |
| `test_natural_systems_lean_r5.py` | `921` | `49,359` | `27ea396866890f2377a203bb720a8465766a59c47f24dcfd03eb09c4e7e39899` |
| `s112_natural_systems_audit.py` | `20` | `564` | `a92f9acdc14f8a4e0eb2c66d26cd07f6b459bf3f697ec9cdca3a84953b464818` |
| `s112_natural_systems_certificate.json` | `1` | `7,421` | `7811fa9af3e67e95591a916cc74ae99422be8bed3f3f86854fcc7c0c93703a0d` |
