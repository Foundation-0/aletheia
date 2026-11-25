# Track S84: Full-Expedition $K_{16}$ Higher-Order All-to-All Interlocking Epistemic Mesh (Orders 1–4 Convergences Across Spines I–V)

- **Track ID:** `TRACK-S84-HIGHER-ORDER-K16-MESH`
- **Schema Version:** `aletheia.track_s84.higher_order_k16_mesh.certificate.v1`
- **Oracle Class / Novelty Tier:** `exact` / `N1` (100% pure-$\mathbb{Z}/\mathbb{Q}$ `int` / `fractions.Fraction` exact linear algebra, exact Sylvester inertia, and exhaustive simplicial topology across all `120` edges, `560` triangles, `1,820` tetrahedra, and `4,368` 5-cells; `0` AST floats, `0` `float()`, `0` bare `assert`s, `0` RNG)
- **Live Formal Proof Kernel:** `Lean 4.36.0` (`leanprover/lean4:v4.36.0`) — `18/18` pure-`Init` theorems (`16` universally quantified `∀` + `2` exact ground witnesses `Thms 10, 14`; `0` external imports, `0` compiler warnings, `4` literal zero-axiom `[]` + `1` `[propext]` + `13` `[propext, Quot.sound]`, `0` `Classical.choice`, `0` banned axioms; R10+ comment-only static scanner + strict quote/guillemet ban + `EXPECTED_LEAN_SHA256` pin + `lean --stdin` zero-TOCTOU execution)
- **Certificate Digests:**
  - `payload_sha256`: `f302d7d38434177286238fafb1077b3ee8a4cdfd716aae579a4085ce467ef88d`
  - `certificate_sha256`: `b0d35075947dd3c9d29baf3cc9a2ff7e276f9089d0cf6c288bdd066ab58585c7`

---

## 1. Epistemic Scope & Pinned 16-Node Provenance (SHA-256-Pinned, Cross-Repo)

All `16` nodes `n00..n15` span all five verified research spines (`S1–S83`), extending `Track S83`'s Wave-4 $K_8$ mesh (`n00..n07`) with eight cross-spine foundational anchors (`n08..n15`). Every node certificate is pinned by SHA-256 against the upstream expedition trees (cross-repo); `verify_s84_higher_order_k16.py --expedition-root <dir>` verifies those pins strictly read-only where the upstream trees are present. In this repo only `5/16` pinned files are present by SHA on current main (`n03` track-s77, `n06` track-s80, `n10` track-s54 and `n11` track-s50 landed via #56/#55, and `n12` under a renamed directory — note `n12`'s pinned path `track-s31-aletheia-v22-society-misfolding-tomography/` is the historical name; the file now lives at `track-s31-aletheia-v22-misfolding/`); the other `11` are external pins: `n09` and `n15` are pinned to specific historical PR commits (`Foundation-0/aletheia#71@d9f0be20` and `#68@8de8309d` — at those PRs' current heads the bytes differ, and will differ again on merge), and the remaining `9` resolve to sibling-repo trees (`Foundation-0/math0` studies / cave-expedition) or nowhere readable. `--expedition-root` fails closed (`INVALID_PARENT_DIR:2`) when they are absent:

| Node | Spine | Track | Pinned Certificate Relative Path | Bytes | Exact SHA-256 |
|---|---|---|---|---:|---|
| `n00` | Spine I | `Track S73` | `track-s73-lowbit-and-sharednorm-quad-snake/rtx3080_s73_certificate.json` | `5202` | `33dfb4153fe974e9ef13120190c14ada6dda63ffbee6caa46047d274f32d36cf` |
| `n01` | Spine II | `Track S75+S82` | `track-s75-vp-vnp-formal-audit/s75_vp_vnp_certificate.json` | `1982` | `7e383c1cfe04937277be7f8f4ff4305984d51ecd81858eebdd67e45238823224` |
| `n02` | Spine III | `Track S76` | `track-s76-circular-pc-loop-schur-holonomy/s76_circular_pc_certificate.json` | `7006` | `d30805fcb876de096d9b387a8274ecd8063b7906f4feb36124b38a05aefadc95` |
| `n03` | Spine IV | `Track S77` | `track-s77-mellin-glu-wsp-quantization-tomography/s77_mellin_wsp_certificate.json` | `11729` | `d1b9121c435331053b7ab28b915a2062ae7c93b4197d203c63dba42cce5dd74d` |
| `n04` | Spine IV | `Track S81` | `track-s81-motifbench-esmfold-grafting-duality/s81_motifbench_certificate.json` | `4058` | `bc3b9222c47b2ab93c4b5256501d87f8b6483186766e03dba6f1501670936fe0` |
| `n05` | Spine V | `Track S78` | `track-s78-engram-lora-capacity-siliquant-mdl/s78_engram_lora_siliquant_certificate.json` | `18553` | `3b8341ef5f588f970accb9a9d28f0b683af9747be045e69196e6c19d3fa58378` |
| `n06` | Spine V | `Track S80` | `track-s80-rocket-songe-unsloth-optimizations/s80_certificate.json` | `6098` | `95681a29ca577c4e3040f8ba63f8516b1cbb2bf1ebfdcda06277f21bb2aa2cb7` |
| `n07` | Spine I | `Track S79` | `track-s79-2dsd-multipole-dense-sparse-laws/s79_2dsd_multipole_certificate.json` | `6460` | `9c30539e6d585141a9b1a5111935ca86de0f740e80749a622547a18242465ad8` |
| `n08` | Spine I | `Track S59+S47` | `track-s59-exact-e8-vs-a16-hadamard-law/e8_vs_a16_hadamard_certificate.json` | `6360` | `914a84512d7026b23af0672d4b175128534a7d3c8a0fbc9152b28bc38ea8f1ed` |
| `n09` | Spine I | `Track S71+S65` | `track-s71-proximity-barrier-silicon-unlock/s71_proximity_certificate.json` | `2982` | `7774fedfd575f48451aae0722cdbaf8015673585786dc43dc8e35402580efe6d` — pinned to historical commit `Foundation-0/aletheia#71@d9f0be20` |
| `n10` | Spine II | `Track S54+S38` | `track-s54-silq-cs21-boundary-compiler/silq_cs21_compiler_certificate.json` | `12813` | `94b9c34f196afc031e6169032eb42d2fe2ddd120d2dc137bc52c0ee2bebf3850` |
| `n11` | Spine III | `Track S50+S42/43` | `track-s50-zero-dw-state-transport-tomography/zero_dw_state_transport_certificate.json` | `12803` | `1316eede91b66c309c427fec60e36374350d65b6649eba7154de8e4ea4431320` |
| `n12` | Spine V | `Track S31+S34` | `track-s31-aletheia-v22-society-misfolding-tomography/aletheia_v22_misfolding_certificate.json` | `12707` | `f4f7f8abff0c7eae0d5678016c1041ab34870ef2de57a2f83e4cbb9a529f8a9b` |
| `n13` | Spine III | `Track S28+S23b/33` | `track-s28-alcubierre-adm-slemma-tomography/alcubierre_adm_certificate.json` | `7831` | `6d5579f52d176f39d6f160a405873843ff616ca7d1d76c95f1a3d340237bbc9f` |
| `n14` | Spine II | `Track S40+S22c/41` | `track-s40-mozart-perfect-numbers-bridge/mozart_perfect_bridge_certificate.json` | `11634` | `3c6b226b43804befdd102a4f02800421087ed851009967bc20b2e72479ce336e` |
| `n15` | Spine V | `Track S62+S56/57` | `track-s62-ceer-lean4-silicon-recursion/ceer_silicon_certificate.json` | `11121` | `cef74336a38edc2d7c0b05007952690c0f8608607bc800036292aa4642665b53` — pinned to historical commit `Foundation-0/aletheia#68@8de8309d` |

---

## 2. Pillar 1 — Order-1 Convergences (`120` All-to-All Pairs, $L_0$, & Wave-4 $K_8$ Synergy Lift)

The $120$ undirected pathways of $K_{16}$ strictly preserve all `28` Wave-4 $K_8$ edge classes on `n00..n07` (`10` `EXACT_COMMUTE`, `12` `CONDITIONAL_BRIDGE`, `6` `EXACT_OBSTRUCTION`, $\sum w = 70$) and add `92` cross-spine typed pathways:

- **Edge Class Census (`120` total, $\sum w = 333$):** `54` `EXACT_COMMUTE` ($w = 4$), `51` `CONDITIONAL_BRIDGE` ($w = 2$), `15` `EXACT_OBSTRUCTION` ($w = 1$).
- **Operator Census:** `REFUSAL_GATE` (`⫩`, `30`), `BOUNDARY_WALL` (`⧇`, `18`), `SCHUR_PUSHFORWARD` (`⧄`, `17`), `KREIN_INERTIA` (`⦺`, `17`), `PHASE_CROSSOVER` (`⟠`, `16`), `GAUGE_QUOTIENT` (`⧂`, `13`), `HOLONOMY_CURVATURE` (`⦷`, `9`).
- **Exact $16 \times 16$ Weighted Laplacian $L_0$:** Pure-$\mathbb{Q}$ Sylvester inertia **`[15, 0, 1]`**, exact Foster identity $\sum_{e} w_e R^{\mathrm{eff}}_e = \mathbf{15}$ (`== N - 1`), independently cross-checked via grounded Green's function $Z$ (`L[1:,1:]^{-1}`) and explicit 2-node Schur pushforwards $S_{\{i,j\}}$ on `(n00, n01)`, `(n00, n15)`, and `(n06, n07)`.
- **Strict All-to-All Compounding (`120/120` Pairs):** Every pair achieves $G^{\mathrm{eff}}_{ij}/w_{ij} > 1$, ranging from **`4.4697×`** (`n04–n12`, $w = 4$) up to **`21.9371×`** (`n06–n07`, $w = 1$).
- **Wave-4 $K_8$ Sub-Mesh Amplification Inside $K_{16}$:** Eliminating `n08..n15` via the exact $8 \times 8$ Schur pushforward $S_{\{0..7\}}$ (inertia `[7, 0, 1]`) strictly amplifies **ALL `28/28`** Wave-4 pairs relative to isolated $K_8$, by **`1.9346×`** (`n00–n06`) up to **`2.3624×`** (`n03–n05`).

---

## 3. Pillar 2 — Order-2 Convergences (`560` Triangles, Exact Hodge-1 `B_1 B_2 = 0`, & Disjoint Natural Transformations)

- **Exhaustive `560`-Triangle Holonomy Census ($\binom{16}{3} = 560$):**
  - `68` `EXACT_TRANSITIVE_CLOSURE` (`3/3` `EXACT_COMMUTE`, $\mathbb{Z}_2$ holonomy `0`)
  - `320` `CONDITIONAL_COMPOUNDING_CLOSURE` (`0` walls, $\ge 1$ conditional bridge, $\mathbb{Z}_2$ holonomy `0`)
  - `137` `FRUSTRATED_CURVATURE_LOOP` (exactly `1` obstruction wall, odd $\mathbb{Z}_2$ holonomy `1` — automatic repair generators)
  - `35` `MULTI_WALL_BOUNDARY_SECTOR` ($\ge 2$ obstruction walls)
- **Exact Simplicial Hodge-1 Identity:** Boundary-of-boundary $B_1 B_2 = 0$ proven identically zero by Lean Thm 12 (d^2 = 0; shapes/traces by construction, not entry-checked in Python); unweighted $B_1 B_1^\top$ has inertia `[15, 0, 1]`, yielding exact orthogonal edge-flow decomposition $120 = 15_{\mathrm{grad}} + 105_{\mathrm{curl}} + 0_{\mathrm{harm}}$ with $\mathrm{tr}(B_1^\top B_1) = 240$ and $\mathrm{tr}(B_2 B_2^\top) = 1,680$.
- **Disjoint-Edge 2nd-Order Natural Transformations:** `630` exhaustive vertex-disjoint same-operator pairs across $K_{16}$, anchored by `8` curated natural transformations (`NT01..NT08`) pairing disjoint edges with identical operator tags across distinct spines (e.g., `NT01`: `(n00, n08)` `E_8/A_16` Hadamard `8×` flip $\leftrightarrow$ `(n09, n13)` `64 B` MESI/Krein flip [`⦺`]; `NT02`: `(n03, n04)` Mellin width vs $\mathbb{R}^3$ wall $\leftrightarrow$ `(n00, n14)` $\mathbb{F}_2[x]$ vs $\mathbb{Z}$ carry wall [`⧇`]; `NT04`: `(n05, n06)` `CS-15`/`songe` ratchet $\leftrightarrow$ `(n10, n12)` `CS-21`/DPI proxy-gaming closure [`⫩`]).

---

## 4. Pillar 3 — Order-3 Convergences (`1,820` Tetrahedra, Exact $\mathbb{Z}_2$ Bianchi, $K_4$ Locks, & Paired-Frustration Repair)

- **Exhaustive Discrete Bianchi Conservation:** All **`1,820/1,820`** tetrahedra ($\binom{16}{4}$) satisfy $\delta^2 = 0$ (`z2_bianchi_nonzero_count = 0`).
- **Exact Order-3 Census (`1,820` total):**
  - **`40` `K4_EXACT_LOCK`** (all `6/6` edges `EXACT_COMMUTE` — zero obstructions, zero conditional bridges)
  - `880` `K4_CLEAN_CLOSURE` (`0` walls)
  - **`545` `PAIRED_FRUSTRATION_REPAIR_TET`** (exact `1` wall generating `2` frustrated faces simultaneously cured by `1` mediator blow-up, e.g., Sovereign `8 GiB` Stack tetrahedron `{n00, n05, n06, n07}` cured by resolving `(n06, n07)` `tl.atomic_cas` ULP non-associativity)
  - `355` `MULTI_WALL_TET` ($\ge 2$ walls)
- **Top Single-Wall Order-3 Repair Leverage Ranking:**
  1. Tied #1 (`65` paired-repair tetrahedra each): `(n06, n07)` (`tl.atomic_cas` ULP vs `2DSD`/Multipole) and `(n06, n09)` (`atomic_cas` `16.973×` `64 B` MESI repulsion)
  2. Tied #3 (`61` paired-repair tetrahedra each): `(n01, n05)` (`Thm D.2` hyperfilter vs finite-rank $C_{\mathrm{MP}}$) and `(n01, n08)` (`vp-vnp` CNOT real shear $\kappa_2 = \phi^2$ vs `S59` $O_{16}(\mathbb{Q})$)
  3. Tied #5 (`51` paired-repair tetrahedra each): `(n00, n14)` and `(n03, n14)` ($\mathbb{F}_2[x]$ carry-free splitting vs $\mathbb{Z}$ quantization/GLU carries)

---

## 5. Pillar 4 — Order-4 Convergences (`4,368` 5-Cells, 4th-Order Meta-Mesh $M_4$, Exponential Silo-Cut Law, & Law-3 Firewall)

### 5.1 Exhaustive `4,368` 5-Cell Census ($\binom{16}{5} = 4,368$)
- **`11` `K5_EXACT_LOCK`** (all `10/10` edges `EXACT_COMMUTE`, e.g., `{n00, n03, n07, n08, n09}`, `{n00, n03, n07, n08, n15}`, `{n00, n05, n06, n12, n15}`)
- `1,482` `K5_CLEAN_CLOSURE` (`0` walls)
- **`1,283` `SINGLE_WALL_3FACE_CASCADE_5CELL`** (exact `1` wall frustrating `3/10` triangular faces simultaneously)
- `1,592` `MULTI_WALL_5CELL` ($\ge 2$ walls)
- **Frustrated-Face Histogram (Sums to `4,368`; `{1, 2, 8, 9}` Absent by Bianchi Parity):** `0`: `1,525`, `3`: `1,576`, `4`: `743`, `5`: `80`, `6`: `306`, `7`: `132`, `10`: `6`.

### 5.2 Explicit 4th-Order Meta-Mesh $M_4 = P^\top L_0 P$ (Compounding Between Order-3 Clusters)
Partitioning all `16` nodes into four pairwise-disjoint Order-3 $K_4$ clusters (`C0 = {n00, n03, n08, n09}`, `C1 = {n01, n02, n07, n13}`, `C2 = {n05, n06, n10, n12}` — all three `K4_EXACT_LOCK` — plus `C3 = {n04, n11, n14, n15}` `MULTI_WALL_TET`) yields the exact algebraic quotient Laplacian $L^{(4)} = P^\top L_0 P$ (inertia `[3, 0, 1]`, Foster sum `= 3`) with **all `6/6` meta-pairs strictly Schur-compounded**:

| Meta-Edge (Order-3 Cluster Pair) | Direct Weight $W_{ab}$ | Exact $G^{\mathrm{eff},(4)}_{ab}$ | Compounding Ratio (`dec4`) |
|---|---:|---:|---:|
| `C0_SILICON_LATTICE_GRAFT` $\leftrightarrow$ `C1_SPECTRAL_SCHUR_KREIN` | `43` | `1137784/13725` | `1.9279×` |
| `C0_SILICON_LATTICE_GRAFT` $\leftrightarrow$ `C2_MDL_RATCHET_BOUNDARY` | `47` | `1137784/13069` | `1.8523×` *(min)* |
| `C0_SILICON_LATTICE_GRAFT` $\leftrightarrow$ `C3_WALL_TRANSPORT_CEER` | `39` | `142223/1714` | `2.1276×` |
| `C1_SPECTRAL_SCHUR_KREIN` $\leftrightarrow$ `C2_MDL_RATCHET_BOUNDARY` | `34` | `284446/3651` | **`2.2914×`** *(max)* |
| `C1_SPECTRAL_SCHUR_KREIN` $\leftrightarrow$ `C3_WALL_TRANSPORT_CEER` | `41` | `1137784/14045` | `1.9759×` |
| `C2_MDL_RATCHET_BOUNDARY` $\leftrightarrow$ `C3_WALL_TRANSPORT_CEER` | `45` | `1137784/13373` | `1.8907×` |

### 5.3 Exact $k$-Simplex Silo-Cut Exponential Destruction Law (`8 | 8` Split on $K_{16}$)

| Order | Simplex $k$ | Total $\binom{16}{k}$ | Surviving $2\binom{8}{k}$ | Destroyed $\Delta_k(16,8)$ | Destroyed Ratio | Surviving vs. $2^{1-k}$ Ceiling |
|---:|---:|---:|---:|---:|---:|---:|
| Order 1 | `2` (edges) | `120` | `56` | **`64`** | `8/15 = 53.33%` | `7/15 < 1/2` |
| Order 2 | `3` (triangles) | `560` | `112` | **`448`** | `4/5 = 80.00%` | `1/5 < 1/4` |
| Order 3 | `4` (tetrahedra) | `1,820` | `140` | **`1,680`** | `12/13 = 92.31%` | `1/13 < 1/8` |
| Order 4 | `5` (5-cells) | `4,368` | `112` | **`4,256`** | `38/39 = 97.44%` | `1/39 < 1/16` |

### 5.4 Honest Law-5 Contagion Obstruction vs. Law-3 Per-Edge Refusal Firewall (`⫩`, $K_{16} \to K_{15}$)
Injecting bias $\varepsilon = 1$ at compromised node `n06` with clean anchor `n00` (`0`):
- **Ungated $K_{16}$:** Corrupting flux equals $J_{\mathrm{ungated}} = G^{\mathrm{eff}}_{0,6} = \mathbf{22.7432}$ (**`5.6858×`** the direct edge $w_{0,6} = 4$), strictly corrupting **all `14/14`** innocent interior nodes ($u_i \in [0.4432, 0.5019]$).
- **Law-3 `⫩` Per-Edge Refusal Firewall:** Exact **`0`** flux and **`0`** interior corruption; the remaining verified $K_{15}$ sub-mesh preserves `105/120` (`87.50%`) edges, `455/560` (`81.25%`) triangles, `1,365/1,820` (`75.00%`) tetrahedra, `3,003/4,368` (`68.75%`) 5-cells, and strict compounding across all `105/105` remaining pairs (minimum **`4.1344×`**).

---

## 6. Live Kernel-Checked `Lean 4.36.0` Theorem Ledger (`18/18`, `0` Banned Axioms, `0` `Classical.choice`)

Compiled live via `lean --stdin` (`rc = 0`, `0` stderr bytes, `0` warnings) and isolated `lake build` (`4 jobs`, `0` warnings); axioms strictly inside `{"propext", "Quot.sound"}` (`4` literal `[]`, `1` `[propext]`, `13` `[propext, Quot.sound]`):

1. `schur_3node_conductance_exact` — cleared 3-node Schur determinant identity
2. `schur_3node_strict_compounding` — strict positive 2-hop compounding
3. `schur_uniform_kn_conductance_strict` — `2 * w < N * w` (`∀ N ≥ 3, w > 0`)
4. `foster_uniform_kn_exact` — cleared uniform $K_N$ Foster sum identity (`[propext]`)
5. `prop_e10_balanced_edge_cut_bound` — universal `2 * N^2 ≤ 9 * S * (N - S)`
6. `k16_edge_destruction_exact` — sharp $K_{16}$ balanced edge lower bound (`≥ 57`, `64/63/60` exact)
7. `kn_triangle_destruction_exact_identity` — universal Order-2 `6 * Δ_3 = 3*S*T*(S+T-2)`
8. `kn_tetrahedron_destruction_exact_identity` — universal Order-3 cleared Chu–Vandermonde identity
9. `kn_5cell_destruction_exact_identity` — universal Order-4 cleared Chu–Vandermonde identity
10. `k16_balanced_exponential_destruction_exact` — exact `8|8` `64/120 < 448/560 < 1680/1820 < 4256/4368` (`[]`)
11. `balanced_halving_survival_strict_exponential_bound` — universal `∀ m ≥ 5` strict `2^(1-k)` survival ceiling (`k = 2..5`)
12. `simplicial_hodge_b1_b2_zero` — universal oriented boundary-of-boundary `(fv - fu) + (fw - fv) - (fw - fu) = 0`
13. `tetrahedral_z2_bianchi_zero` — universal `∀ e01..e23 : Bool` tetrahedral $\delta^2 = 0$ (`[]`)
14. `paired_frustration_repair_cancels_two_triangles` — single-wall Order-3 paired repair witness (`[]`)
15. `five_cell_single_wall_frustrates_exactly_three_faces` — single-wall Order-4 3-face cascade law (`[]`)
16. `ungated_k16_contagion_amplification` — `2 * (w * eps) < 16 * (w * eps)` (`8×` uniform amplification)
17. `gated_refusal_firewall_zero_contagion` — Law-3 isolation forces `u_int = 0 ∧ J_gated = 0`
18. `gated_k15_submesh_preserves_higher_order_compounding` — exact $K_{15}$ survival (`105/455/1365/3003`) & `2 * w < 15 * w`

---

## 7. Aletheia R1–R5 & R10+ Verification Gate Summary

- **3-Mode R4 Parity (`-I -B`, `-I -O -B`, `-I -B -W error`) + `PYTHONHASHSEED=42` + `umask 077` + CI `chmod 644` / RO-Dir Sim + No-Lean `env -i PATH=/usr/bin:/bin` `0`-Skip Parity:** `test_s84_higher_order_k16_r5.py` `8/8 OK` across all modes (`0` skips); live `--check --lean --json` `PASS` (`18/18` theorems live-verified); the `--expedition-root` pin check is cross-repo (3/16 pinned files present in this repo by SHA, the rest verified where the upstream expedition trees are present; fails closed `INVALID_PARENT_DIR:2` otherwise).
- **Direct 4-Surface `S19c` v2.1 `zone_b_fuzzer` (Zero Wrappers):** **`82/82 PASS`** (`CLI 25/25`, `FR1 19/19`, `FR0 [full_replay=False] 19/19`, `SEC [secondary_audit_payload] 19/19`; `byp=0, cr=0`) — one-off local run, fuzzer script not shipped in this repo.
- **Live stock `aletheia mutate --guards require_ok --max-mutants 0 --timeout 180` (no `--workers` flag exists on the stock CLI):** **`234/234 KILLED = 100.0%`** (`verify_s84_higher_order_k16.py 219/219`, `s84_higher_order_k16_oracle.py 15/15`; `survived=0, timeout=0, truncated=False, null_mutant=passed ×2`).
- **Null-Checked Whole-File DFS AST `BoolOp` (`OP_SWAP + SUBCOND_DEL`):** **`36/36 KILLED = 100.0%`** (`verify_s84_higher_order_k16.py 22/22`, `s84_higher_order_k16_oracle.py 14/14`; `survived=0, timeout=0`) — one-off local run, BoolOp harness not shipped in this repo.
- **Dual `aletheia audit-check <track> --lean-audit --strict-ancestors --safety-scan --scripts ...` (scoped to the track directory):** **`PASS ×2`** (`0` findings, `0` notices, `0` bare asserts, `0` AST floats, `0` leaks, `0` CRLF, `PYC=0, LAKE=0, ELF=0`).

---

## 8. Frozen 8-File Manifest

| File | Lines | Bytes | Mode | SHA-256 |
|---|---:|---:|:---:|---|
| `HigherOrderEpistemicMesh.lean` | `495` | `28960` | `0o644` | `00238fb5e82cbb64e1b0877c4962a7cac1dec3332871dd9471b3fe6636bdb831` |
| `lakefile.toml` | `6` | `146` | `0o644` | `2c9fa4e2bf0c8da196d9ed8633d0489c314892ffc2eed36ea8937b751122296a` |
| `lean-toolchain` | `1` | `25` | `0o644` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |
| `s84_higher_order_k16_oracle.py` | `1,216` | `58,313` | `0o644` | `712f6b7ca2eeb43bdb837f6c0447841a61d819d252d007100ec132132afa5e65` |
| `verify_s84_higher_order_k16.py` | `818` | `34,264` | `0o644` | `a1c25cae025cbb0887e848bed43b9488e745d53a8fa278cc7983d358e8840ec6` |
| `test_s84_higher_order_k16_r5.py` | `977` | `61,328` | `0o644` | `a85065981fab45845bb2d8d79d3b1e2ad97d5cc6c8a29eff2ab061aad1fee734` |
| `s84_higher_order_k16_certificate.json` | `1` | `43,632` | `0o644` (`0o600` on `--write`) | `f1a52d94c90389b123dd64b4fe15b13b4cc15587af30e3d3f670b6a6a9269149` |
| `REPORT.md` | *(self)* | *(self)* | `0o644` | *(computed externally post-write)* |
