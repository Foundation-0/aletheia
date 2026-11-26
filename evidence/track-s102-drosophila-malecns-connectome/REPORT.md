# Track S102 — Exact Integer/Rational Operators & Lean 4.36.0 Formalization of the FlyEM *Drosophila* MaleCNS v1.0 Whole-CNS Connectome

- **Track ID:** `S102` (`track-s102-drosophila-malecns-connectome/`)
- **Certificate Schema:** `s102-malecns-connectome-cert-v1`
- **Certificate File SHA-256 (`s102_malecns_connectome_certificate.json`):** `5238ce3f81099bd93145600b728d8af490a753447e089babf7ce035deb3bd945` (`20,226` B, `0o644`)
- **Certificate Envelope `certificate_sha256`:** `25148049f59bef777a9ded709e0b8fc0ae758766d2a91513feda001072aaa472`
- **Payload SHA-256:** `c1bc6d50bc4a2acf030c96e12ffda550a306bcedb64a1e258c9b11bcb39bee90`
- **Anchor SHA-256 (`s102_malecns_anchor.json`):** `067638e0f8529df79e68e9869abcb26d4cde61f9648488310c1436432540e41c` (payload `f72c14e984f0c247fb44f9d5049a7575d8962eef6f16cacd243231f2a6a553ad`)
- **Oracle Class:** `EXACT_INTEGER_RATIONAL_AND_LEAN4` (pure stdlib `int`/`Fraction`, zero production IEEE-754 floats, zero raw dataset copies inside `expedition/`)
- **Inertia Tuple Convention Note (`D1` Cross-Track Alignment):** Throughout Track S102 (`inertia_from_pivots` in `s102_malecns_connectome_oracle.py`, certificate JSON, and verifier), every Sylvester/Krein inertia triple is reported in **`[n_pos, n_neg, n_zero]` (`[n_+, n_-, n_0]`)** order. Cross-track readers comparing against `Track S99` (`track-s99-optifab-5org-convergence/`, which returns `(n_pos, n_zero, n_neg)`) must permute indices `1 <-> 2`.
- **Honest Novelty Classification:** `N0_N1_CONNECTOME_EXACT_OPERATORS` (`N0` verified live empirical extraction from FlyEM MaleCNS v1.0 `CC-BY-4.0` + `N1` formal exact-operator synthesis & `18/18` pure-`Init` `Lean 4.36.0` theorems; **`n2_open_claims_count = 0`**).

---

## 1. Pillar 1 — Whole-CNS Live Exact Integer Topology & Dale's-Law Partition

Extracted directly from the read-only external FlyEM MaleCNS v1.0 `.feather` release (`~534.0 MiB`, `CC-BY-4.0`, zero copies inside `expedition/`, all 3 external `.feather` SHA-256s pinned in `s102_malecns_anchor.json` and live-verified via `--verify-data`):

- **Scale:** `211,577` annotated bodies (`166,700` with `superclass`, `11,751` distinct annotated cell types), `1,835,518` neurotransmitter rows, **`164,740`** active connected neurons, **`25,568,639`** directed edges (`101` self-loops), and **`124,039,080`** synapses (`min = 1`, `max = 2,591`).
- **Exact Rational Means:**
  - Mean synaptic weight per edge: `124039080/25568639` (`4.8512`)
  - Mean out-degree per active neuron: `25568639/164740` (`155.2060`)
  - Mean synapses per active neuron: `6201954/8237` (`752.9384`)
- **Whole-CNS Dale's-Law Exact Partition** (CNS-internal conventions: `ACh = +1`; `GABA`, `Glu` via GluCl-alpha, `His = -1`; modulatory `DA/OA/5HT` & `unclear/missing = 0`):
  - **Excitatory (`ACh`, `+1`):** `14,740,266` edges, `73,479,194` synapses
  - **Inhibitory (`GABA + Glu + His`, `-1`):** `9,802,754` edges, `47,323,246` synapses
  - **Modulatory (`DA + OA + 5HT`):** `435,559` edges, `1,183,807` synapses
  - **Unclear / Missing:** `590,060` edges, `2,052,833` synapses
  - **Signed Synapses Conservation:** `E + I = 120,802,440`, `E - I = +26,155,948`, Excitatory share `E/(E+I) = 36739597/60401220` (`60.83%`), Inhibitory share `I/(E+I) = 23661623/60401220` (`39.17%`), exact E:I ratio `E/I = 36739597/23661623` (`1.5527`).

### Heavy-Tail Integer Weight Thresholds & Top-k% Concentration vs. Track S86 Hessian-CSR

| Threshold | Directed Edges | Edge Share | Synapses | Synapse Share |
|---|---:|---|---:|---|
| `w >= 1` | `25,568,639` | `1` (100.00%) | `124,039,080` | `1` (100.00%) |
| `w >= 2` | `15,273,176` | `15273176/25568639` (59.73%) | `113,743,617` | `37914539/41346360` (91.70%) |
| `w >= 5` | `6,236,426` | `6236426/25568639` (24.39%) | `89,737,406` | `4078973/5638140` (72.35%) |
| `w >= 10` | `2,749,558` | `2749558/25568639` (10.75%) | `67,175,216` | `8396902/15504885` (54.16%) |
| `w >= 20` | `1,060,450` | `1060450/25568639` (4.15%) | `44,729,169` | `14909723/41346360` (36.06%) |
| `w >= 50` | `227,938` | `227938/25568639` (0.89%) | `20,441,631` | `6813877/41346360` (16.48%) |
| `w >= 100` | `55,500` | `55500/25568639` (0.22%) | `8,922,326` | `4461163/62019540` (7.19%) |
| `w >= 500` | `515` | `515/25568639` (0.00%) | `362,868` | `2749/939690` (0.29%) |

| Slice | Edges | Synapses | Exact Synapse Capture | Uniform Density Lift |
|---|---:|---:|---|---:|
| `top_0p5pct` (`w >= 67`) | `127,843` | `14,726,110` | `1472611/12403908` (11.8722%) | `23.74x` |
| `top_1p0pct` (`w >= 46`) | `255,686` | `21,771,152` | `2721394/15504885` (17.5518%) | `17.55x` |
| `top_5p0pct` (`w >= 17`) | `1,278,431` | `48,695,053` | `4426823/11276280` (39.2578%) | `7.85x` |
| `top_10p0pct` (`w >= 10`) | `2,556,863` | `65,248,266` | `10874711/20673180` (52.6030%) | `5.26x` |

- **Biological Synaptic Redundancy vs. LLM Hessian Curvature (`Track S86` Bridge):** MaleCNS top-`0.5%` edges (`127,843` edges, `w >= 67`) capture `11.8722%` of synapses (`23.74x` uniform), whereas `Track S86` Hessian-CSR top-`0.500%` weights capture `3101/10000` (`31.0100%`, `62.02x` uniform). The exact concentration ratio is `1373732811/525932500` (`2.6120x` sharper in LLM parameter curvature than biological synaptic weight; exact gap `5934602177/31009770000` = `19.1378%`, formalized in Lean Theorem 18).

---

## 2. Pillar 2 — 8×8 Functional Supergraph, 6×6 Central-Complex Core, Schur Complement, Krein Inertia & Signed Triad Frustration

### 2.1 Whole-CNS 8×8 Functional Supergraph (`M0_Sensory..M7_VNC_Motor`)

Covers `25,559,990 / 25,568,639` edges (`99.9662%`) and `124,013,127 / 124,039,080` synapses (`99.9791%`; only `313` unannotated active neurons):

| Module | Active Neurons | Self Unsigned Syn | Self Dale-Signed Net | Row Unsigned Total | Row Dale-Signed Net |
|---|---:|---:|---:|---:|---:|
| `M0_Sensory` | `15,783` | `769,342` | `+602,687` | `6,496,803` | `+5,147,407` |
| `M1_OpticLobe` | `99,149` | `48,946,901` | `+10,202,848` | `53,463,515` | `+13,317,649` |
| `M2_MushroomBody` | `4,501` | `2,222,611` | `+1,872,812` | `2,851,284` | `+2,231,851` |
| `M3_CentralComplex` | `2,950` | `2,791,696` | `-428,494` | `2,982,340` | `-324,127` |
| `M4_CentralBrainOther` | `24,789` | `27,140,839` | `+4,050,405` | `33,317,713` | `+4,037,538` |
| `M5_Ascending` | `1,854` | `660,326` | `+116,180` | `5,149,203` | `+1,631,793` |
| `M6_Descending` | `1,318` | `598,888` | `+176,030` | `4,092,431` | `+1,457,860` |
| `M7_VNC_Motor` | `14,083` | `13,436,249` | `-635,137` | `15,659,838` | `-1,351,819` |

- **Exact Biological Sign-Inversion Witnesses:**
  - `M0_Sensory -> M1_OpticLobe`: **`-476,368`** (histaminergic photoreceptor R1–R8 inhibition).
  - `M3_CentralComplex -> M3_CentralComplex`: **`-428,494`** (net inhibitory compass ring clamp).
  - `M7_VNC_Motor -> M7_VNC_Motor`: **`-635,137`** (CNS-internal glutamatergic GluCl-alpha + GABAergic premotor/motor circuitry; note peripheral NMJs are excitatory and lie outside CNS-internal synapses).
- **Exact Operator Decomposition (`W8_s`):**
  - Frobenius `||W8_s||_F^2 = 145,586,864,588,280`, Pythagorean skew energy share `8.5298%`, normalized non-normal commutator ratio `0.065952`.
  - **Signed Laplacian `L_sigma(W8_s)` exact rational LDL^T inertia (`[n_+, n_-, n_0]`):** **`[8, 0, 0]` (`8/8` strictly positive pivots -> mathematically proved structurally frustrated, zero balanced harmonic nullspace)**.
  - **Symmetrized Dale Interaction `H_s = W8_s + W8_s^T` exact rational Krein inertia (`[n_+, n_-, n_0]`):** **`[5, 3, 0]`** (`5` positive, `3` negative, `0` zero).
- **Exact 8->3 Boundary Schur Complement & Dark-Mode Shadow (`B = {M0_Sensory, M6_Descending, M7_VNC_Motor}`, eliminating interior brain `I = {M1..M5}`):**
  - Interior `L_II` exact LDL^T inertia (`[n_+, n_-, n_0]`): `[5, 0, 0]` (`5/5` positive pivots); reduced `3×3` Schur complement `S_B = L_BB - L_BI L_II^-1 L_IB` exact LDL^T inertia (`[n_+, n_-, n_0]`): `[3, 0, 0]` (`3/3` positive pivots).
  - Exact trace conservation: `tr(L_BB) = 9,873,146` = `tr(S_B) (8,535,100.02) + tr(shadow) (1,338,045.98)`, yielding an exact interior dark-mode conductance shadow fraction of **`13.5524%`**.

### 2.2 Central-Complex 6×6 Ring-Attractor Core (`EPG, PEN, Delta7, PEG, ER, PFL`)

Every single row is **100% Dale-sign homogeneous** (`|W6_s[r][c]| == W6_u[r][c]` across all `36/36` entries):

| Population | Active Neurons | Dale Sign | Signed Outflow Vector `[EPG, PEN, Delta7, PEG, ER, PFL]` |
|---|---:|---|---|
| `EPG` | `46` | `+1 (ACh)` | `[+11,486, +12,330, +19,896, +6,154, +20,053, +2,756]` |
| `PEN` | `42` | `+1 (ACh)` | `[+24,069, +17,916, +29, +459, +9,613, +21]` |
| `Delta7` | `42` | `-1 (Glu)` | `[-4,294, -7,239, -26,539, -3,926, +0, -13,618]` |
| `PEG` | `18` | `+1 (ACh)` | `[+994, +2,424, +6, +543, +4,642, +14]` |
| `ER` | `282` | `-1 (GABA)` | `[-123,998, -7,538, +0, -4,194, -269,271, -12]` |
| `PFL` | `50` | `+1 (ACh)` | `[+43, +1, +10, +12, +133, +2,122]` |

- **Exact Operator Amplification vs. Whole Brain:**
  - `W6_s` skew energy share = **`12.1521%`** (`1.42x` whole-brain `8.53%`), and normalized non-normal commutator ratio = **`0.473676`** — **`7.182x` MORE NON-NORMAL** than the whole-brain `8×8` supergraph!
  - `L_sigma(W6_s)` exact LDL^T inertia (`[n_+, n_-, n_0]`): **`[6, 0, 0]`** (`6/6` positive -> frustrated compass). Independently dual-witnessed via exact rational Farkas multiplier `q = L_{sigma,6}^-1 * 1` (`L_{sigma,6} * q == 1` exact, `q^T L_{sigma,6} q = 1^T q = 0.00024257 > 0`), confirming `L_{sigma,6} * 1 != 0` and zero balanced harmonic nullspace.
  - `H_s(W6_s)` exact Krein inertia (`[n_+, n_-, n_0]`): **`[4, 2, 0]`** — matching the exact `4` excitatory (`EPG, PEN, PEG, PFL`) vs `2` inhibitory (`Delta7, ER`) compass populations!

| Al-Tusi / Feedforward Pair `(i, j)` | `W_s[i,j]` | `W_s[j,i]` | Directional Ratio | Opposing Signs | Exact 2×2 `||[W, W^T]||_F^2` |
|---|---:|---:|---|---:|---:|
| `EPG_ER` | `+20,053` | `-123,998` | `123998/20053` (6.18x) | `True` | `3,719,729,622,902,507,520,948` |
| `EPG_Delta7` | `+19,896` | `-4,294` | `9948/2147` (4.63x) | `True` | `1,977,035,350,579,653,800` |
| `PEN_EPG` | `+24,069` | `+12,330` | `8023/4110` (1.95x) | `False` | `376,544,827,520,576,442` |
| `Delta7_PFL` | `-13,618` | `+10` | `6809/5` (1,361.80x) | `True` | `373,907,664,107,029,280` |
| `EPG_PFL` | `+2,756` | `+43` | `2756/43` (64.09x) | `False` | `1,406,108,656,785,986` |

### 2.3 Exact Central-Complex (`w >= 10`) Directed & Signed Triad Frustration vs. Degree-Preserving Null

Across all `2,924` CX nodes (`72,904` directed edges, `1,820,401` synapses) vs. deterministic pure-integer LCG Maslov–Sneppen degree- & neurotransmitter-preserving null (`seed=102`, `652,723` accepted swaps):

- **Topological Enrichment:**
  - Reciprocity: `25,306` (`34.71%`) vs. null `2,260` (`3.10%`) -> **`11.197x`** (`12653/1130`).
  - Feedforward loops (FFL): `881,633` vs. null `176,953` -> **`4.982x`** (`881633/176953`).
  - Directed 3-cycles: `182,673` vs. null `34,296` -> **`5.326x`** (`60891/11432`).
  - FFL-to-3-cycle ratio: `881633/182673` (`4.8263`).
- **Dale's-Law Signed Frustration Excess (Primary Discovery):**
  - **Signed FFLs (`783,900`):** **`66.53%`** incoherent (`-1`: `521,567`) vs. null **`49.76%`** (`76,107/152,933`). Incoherent FFLs are enriched **`6.853x`** vs. only `3.415x` for coherent FFLs!
  - **Signed 3-Cycles (`145,779`):** **`62.43%`** negative-feedback/frustrated (`-1`: `91,007`) vs. null **`50.40%`** (`13,284/26,358`). Negative-feedback 3-cycles are enriched **`6.851x`** vs. only `4.189x` for positive-feedback 3-cycles!

---

## 3. Pillar 3 — Wave-9 Cross-Portal Engineering Synthesis & Upstream Bridges

All 14 external Wave-9 portal & author-portfolio metadata files are SHA-256 pinned in `s102_malecns_anchor.json` (zero repo clones inside `expedition/`):

1. **`evnsnclr/fruitfly-calculator` (Embedded Integer Connectome Engine):**
   - Entropy-coded `30.9 MB` vs. `205 MB` plain 8-byte edges = **`2050/309` (`6.634x`)** compression, **`12360/1279` (`9.6638`) bits/edge** across `25,580,000` edges; RAM/flash split `65/103` / `38/103`.
   - Recursive bisection log2 target-gap compression: `5/2` (`2.5x`); two-level active bitmap quiet-step speedup: **`55x`** (`550 us -> 10 us`); bit-identical boot self-check `260` steps / `2,900,000` events.
   - **Mechanized Discrete Integer LIF `may_fire` Lyapunov Theorem (Lean Theorems 6 & 7):** For `20*v' <= 19*v + g` and `5*g' <= 4*g`, `E(v,g) = 4*max(v,0) + max(g,0)` is provably non-increasing for all integer trajectories. Concrete witnesses: pruned `(v0=120, g0=600, theta=300)` has `E0 = 1080 < 1200 = 4*theta` and peak `v = 180 < 300`; active `(v0=200, g0=1200, theta=300)` has `E0 = 2000 >= 1200` and reaches peak `v = 335 >= 300`.
2. **`zhengxuyu/nfly` (Law-5 SpMV Memory-Bandwidth Bridge to Track S94 `b_crit = 325/171`):**
   - From the pinned `zhengxuyu/nfly` README empirical measurements (`NFLY_CONSTANTS` in `s102_malecns_connectome_oracle.py`), `8,400,000`-edge SpMV vs. `8,500,000`-param dense MLP incurs `4x` arithmetic ops yet `35x..57x` observed CPU wall time, yielding exact pinned ratios **`35/4` (`8.75x`) to `57/4` (`14.25x`)** wall-time penalty per op. *(Formal scope boundary: Lean Theorem 16 `spmv_bandwidth_intensity_crossover` proves only the generic conditional integer cross-product crossover gap `bytes_mlp * ops_spmv < bytes_spmv * ops_mlp -> 1 <= bytes_spmv * ops_mlp - bytes_mlp * ops_spmv`; it does not prove the empirical CPU timings or hardware bandwidth mechanism.)*
3. **`supat-roong/fly-racer` (Tier S `3,350` Neurons / `164,773` Edges, 4-Arm `CarRacing-v3` 100-Episode Tail-Risk Collapse):**

| Arm | Mean | Std Dev | Worst Episode | 3-Sigma Lower Floor (`mean - 3*sd`) |
|---|---:|---:|---:|---:|
| `fly` | `903.2` | `23.2` | `796.3` | `833.6` |
| `signs` | `896.9` | `28.2` | `745.0` | `812.3` |
| `mlp` | `894.0` | `75.9` | `351.2` | `666.3` |
| `random` | `883.7` | `82.0` | `430.9` | `637.7` |

   - Exact rational variance collapse: `MLP / fly = 576081/53824` (**`10.703x`**), `random / fly = 42025/3364` (**`12.493x`**), `MLP / signs = 64009/8836` (**`7.244x`**).
   - Worst-case floor lift: `fly - MLP = +445.1` (`2.267x`); exact 3-sigma floor margin `fly - MLP = +167.3` (Lean Theorem 17).
4. **SOP-10 Author Portfolio Cross-Pollination & Pinned Upstream Bridges:**

| Sibling Repo | Portal Author | Expedition Bridge Target |
|---|---|---|
| `evnsnclr/wvc` | `evnsnclr` | S97/weft weight-space version control & snapshot provenance |
| `zhengxuyu/softmax1p` | `zhengxuyu` | S86 CCE-Det numerical stability & collapse-free softmax |
| `zhengxuyu/HDM-code` | `zhengxuyu` | S95 hybrid zero-token vs reasoning-budget routing |
| `joey-david/fly-fpv` | `joey-david` | S96 4-arm retinotopic sparse residual connectome control |
| `joey-david/latent-correctness-probe` | `joey-david` | S94 neuron-basis latent calibration & probe interpretability |

| Upstream Track | Frozen Certificate | SHA-256 Prefix | Exact Bridge |
|---|---|---|---|
| `S86` | `track-s86-sovereign-8gb-fourth-order-stack/s86_sovereign_stack_certificate.json` | `675bf68c1291a3cf...` | Top-0.5% Hessian-CSR sensitivity capture (3101/10000) vs MaleCNS top-0.5% synaptic capture (11.87%) and softmax1p CCE-Det link |
| `S91` | `track-s91-transhistorical-k26-convergence/s91_transhistorical_k26_certificate.json` | `ca826006990bd883...` | Al-Tusi dual-loop rotational non-normal dynamics mirrored in Central Complex EPG/PEN/Delta7/ER ring attractor |
| `S94` | `track-s94-neuron-basis-bonsai-sleep-convergence/s94_wave6_convergence_certificate.json` | `1ad705c23646b65d...` | Law-5 memory-bandwidth crossover b_crit=325/171 bridged to nfly SpMV 35-57x CPU wall-time bottleneck |
| `S96` | `track-s96-beyond-lora-and-inkling2-loop/s96_beyond_lora_inkling_certificate.json` | `5de85fe677a714f1...` | Sparse structured residual connectivity (fly-fpv/fly-racer) vs Beyond-LoRA BlockH4-Butterfly structured sparsity |

---

## 4. Pillar 4 — Pure-`Init` `Lean 4.36.0` Formalization (`DrosophilaConnectomeOperators.lean`)

- **Toolchain:** `leanprover/lean4:v4.36.0` (`lean-toolchain` SHA `582a63f8f9c51280...`, `lakefile.toml` SHA `738c966ec2176d02...`, `DrosophilaConnectomeOperators.lean` SHA `144440b279d640ff...`).
- **Kernel Axioms:** `0` external imports, `0` warnings, `0` stderr bytes, **`0` `Classical.choice`**, **`0` `sorryAx`** (`2 [propext]` + `16 [propext, Quot.sound]`); scratch `lake build` passes (`4 jobs`).
- **Single-Kernel Honesty:** Verified by live `Lean 4.36.0` (`lean --stdin`, zero-TOCTOU, 10-var scrubbed `LEAN_PATH`/`LEAN_OPTS`/`LEAN_SRC_PATH`/`LEAN_SYSROOT`/`ELAN_TOOLCHAIN`/`ELAN_HOME`/`LAKE_HOME`/`LEAN_CC`/`LD_PRELOAD`/`LD_LIBRARY_PATH`) + R12-grade static scanner (`scan_lean4_source_r12`; single kernel, no `nanoda` claim).

| # | Theorem (`DrosophilaConnectomeOperators.*`) | Exact Proven Universal Statement | Axioms |
|---:|---|---|---|
| 1 | `dale_signed_partition_identity` | ∀ exc, inh, total, net ∈ ℤ: exc + inh = total ∧ exc - inh = net → 2·exc = total + net ∧ 2·inh = total - net | `[propext, Quot.sound]` |
| 2 | `dale_row_sign_homogeneity_bound` | ∀ w1, w2, w3, s ∈ ℤ, s ∈ {+1, -1}: s·(s·w1 + s·w2 + s·w3) = w1 + w2 + w3 and squared norm identity | `[propext, Quot.sound]` |
| 3 | `heavy_tail_concentration_lift` | ∀ e_top < e_tot, s_top ≤ s_tot, s_top·e_tot > s_tot·e_top: residual tail strictly under-indexes global mean | `[propext, Quot.sound]` |
| 4 | `entropy_coding_bit_savings` | ∀ m > 0, b_enc < b_raw ∈ ℕ: m·b_enc + m·(b_raw - b_enc) = m·b_raw ∧ m·b_enc < m·b_raw | `[propext]` |
| 5 | `active_bitmap_two_level_work_bound` | ∀ n_blocks, b_size ≥ 2, 2·k_active < n_blocks: n_blocks + k_active·b_size < n_blocks·b_size | `[propext, Quot.sound]` |
| 6 | `lif_may_fire_one_step_envelope` | ∀ v, g, v', g' ∈ ℤ: 20·v' ≤ 19·v + g ∧ 5·g' ≤ 4·g → 4·max(v',0) + max(g',0) ≤ 4·max(v,0) + max(g,0) | `[propext, Quot.sound]` |
| 7 | `lif_may_fire_horizon_safety` | ∀ trajectory (v, g) obeying LIF step inequalities with 4·max(v 0,0) + max(g 0,0) < 4·θ: ∀ k ∈ ℕ, v k < θ | `[propext, Quot.sound]` |
| 8 | `al_tusi_pythagorean_frobenius_2x2` | ∀ a, b, c, d ∈ ℤ: exact cleared-denominator symmetric/skew Frobenius identity on 2×2 blocks | `[propext, Quot.sound]` |
| 9 | `nonnormal_commutator_2x2_exact` | ∀ a, b, c, d ∈ ℤ: ‖[W, W^T]‖_F^2 = 2·(b - c)^2·((b + c)^2 + (a - d)^2) | `[propext, Quot.sound]` |
| 10 | `nonnormal_commutator_strict_pos` | ∀ a, b, c, d ∈ ℤ: b ≠ c ∧ b + c ≠ 0 → ‖[W, W^T]‖_F^2 > 0 | `[propext, Quot.sound]` |
| 11 | `al_tusi_ei_loop_oscillatory_obstruction` | ∀ α, β > 0, λ ∈ ℤ: λ^2 + α·β > 0 (no real integer fixed-point eigenvalue on E-I opposing loop) | `[propext, Quot.sound]` |
| 12 | `signed_laplacian_energy_and_frustration` | ∀ w_pos, w_neg ≥ 0, x, y ∈ ℤ: signed Laplacian quadratic form ≥ 0; if w_pos > 0 ∧ w_neg > 0 then energy = 0 → x = y = 0 | `[propext, Quot.sound]` |
| 13 | `signed_triad_switching_invariance` | ∀ g1, g2, g3 ∈ {+1,-1}, s12, s23, s31 ∈ ℤ: Zaslavsky gauge switching leaves closed 3-cycle sign product invariant | `[propext]` |
| 14 | `schur_complement_2x2_completion` | ∀ a, b, d, x, y ∈ ℤ: a·(a·x^2 + 2·b·x·y + d·y^2) = (a·x + b·y)^2 + (a·d - b^2)·y^2 | `[propext, Quot.sound]` |
| 15 | `krein_indefinite_signature_witness` | ∀ a > 0, a·d - b^2 < 0: quadratic form attains strictly positive value at (1,0) and strictly negative value at (-b,a) | `[propext, Quot.sound]` |
| 16 | `spmv_bandwidth_intensity_crossover` | ∀ ops_spmv, ops_mlp, bytes_spmv, bytes_mlp ∈ ℕ: bytes_mlp·ops_spmv < bytes_spmv·ops_mlp → strict integer crossover gap ≥ 1 | `[propext, Quot.sound]` |
| 17 | `four_arm_tail_risk_dominance` | ∀ μ_m ≤ μ_f, sd_f < sd_m, k > 0 ∈ ℤ: μ_m - k·sd_m < μ_f - k·sd_f | `[propext, Quot.sound]` |
| 18 | `bio_vs_hessian_concentration_gap` | ∀ num_bio·den_hess < num_hess·den_bio ∈ ℕ: strictly positive cross-multiplied concentration gap | `[propext, Quot.sound]` |

---

## 5. Verification & Audit-Gate Receipts (Post-Last-Edit)

| Gate | Exact Receipt |
|---|---|
| Live `--check --verify-data` | `PASS` (`3/3` MaleCNS `.feather` + `14/14` Wave-9 external pins + `4/4` track companion pins + `18/18` live `Lean 4.36.0` thms) |
| 9-Environment Isolated Suite (`-I -B`, `-I -O -B`, `-I -B -W error`, `PYTHONHASHSEED=42`, `umask 077`, bare `env -i PATH=/usr/bin:/bin`, `env -i HOME=/nonexistent`, RO-dir `0o500` live & Lean-less) | **`8/8 OK ×9` (`0` skips)** + **`--standalone` `cmp -s ×4 PASS`** |
| Direct 4-Surface v2.1 `zone_b_fuzzer` (`CLI`, `FR1`, `FR0`, `SEC`, zero wrappers) | **`82/82 PASS`** (`25 + 19 + 19 + 19`; `bypasses=0, crashes=0, baseline_ok=True ×4`) |
| Null-Checked Whole-File DFS AST Boolean-Operator Mutation (`workers=2`) | **`58/58 KILLED = 100.0%`** (`3/3` oracle + `55/55` verifier; `survived=0, null_ok=True ×2`) |
| Official `aletheia-fast-mutate --guards require_ok --workers 1 --timeout 180 --max-mutants 0` | **`197/197 KILLED = 100.0%`** (`41/41` oracle + `156/156` verifier; `survived=0, truncated=False ×2, null_mutant=passed ×2`) |
| R12 Static Lean 4 Scanner + 10-Var Env Scrub | `57` attack snippets blocked (`scan_lean4_source_r12`, incl. `dbg_trace`, `dbgTrace*`, `dbgSleep`, `dbgStackTrace`, `dbg_sleep`, `dbg_stack_trace`, `panic!`, `unreachable!`, `panicWithPosWithDecl`, `@[export]`/`@[init]`/`@[builtin_init]`/`@[term_elab]`/`@[command_elab]`/`@[tactic]`/`@[macro]`, `set_option`/`warn.sorry`, `_root_.sorryAx`, `terminalTacticsAsSorry`, `decide +revert +native`, multiline `decide`, `config := { native }`, `#guard_msgs`, `opaque`, `partial`, `bv_decide`), `0/10` FP on clean controls, 10-var `LEAN_*`/`ELAN_*`/`LAKE_HOME`/`LD_*` env scrub verified |
| Field-Complete `SEC`/`FR0`/`FR1`, Anchor DoS Cap & Global Immutability | `40/40` re-signed domain/operator/bool-as-int/non-dict/missing-key/provenance forgeries + `>4300`-digit certificate rational strings AND anchor parser `4,301`-digit ints/strings (`ANCHOR_MAX_INT_DIGITS=80`, `ANCHOR_MAX_STR_LEN=256`, `ANCHOR_MAX_DEPTH=32`) rejected cleanly with typed `S102Error` (`0` bypasses, `0` raw `TypeError`/`KeyError`/`ValueError`); all module-level oracle tables frozen via `MappingProxyType` + `copy.deepcopy` output isolation across all 4 pillars |
| Dual Static Audit Gate (`aletheia-fix-lean-gates-v2` R12 & `aletheia-fast-mutate`) | `aletheia audit-check --lean-audit --strict-ancestors --safety-scan --scripts verify_s102_malecns_connectome.py test_s102_malecns_connectome_r5.py` **`PASS ×2`** (`0` Lean findings/notices, `0` safety findings, `0` leaks, `0` bare `assert`s, `0` CRLF) |

---

## 6. Frozen Track File Inventory (`9` Companion Files + `REPORT.md`)

| File | Lines | Bytes | Mode | SHA-256 |
|---|---:|---:|---|---|
| `DrosophilaConnectomeOperators.lean` | `443` | `20,838` | `0o644` | `144440b279d640ffeb32ad1f432339cef7840015892aee5469e30896ca5877a1` |
| `lakefile.toml` | `6` | `163` | `0o644` | `738c966ec2176d0250f19be54833958dded055da13c198292b26b46577a2c339` |
| `lean-toolchain` | `1` | `25` | `0o644` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |
| `s102_extract_malecns_anchor.py` | `522` | `18,718` | `0o644` | `2a1b211dbc49bef990c7712bb9a1b52553997169cfb919b7f743bb3f6275307b` |
| `s102_malecns_anchor.json` | `1` | `7,949` | `0o644` | `067638e0f8529df79e68e9869abcb26d4cde61f9648488310c1436432540e41c` |
| `s102_malecns_connectome_certificate.json` | `1` | `20,226` | `0o644` | `5238ce3f81099bd93145600b728d8af490a753447e089babf7ce035deb3bd945` |
| `s102_malecns_connectome_oracle.py` | `923` | `37,847` | `0o644` | `db2afa83bd1bfcbd5aa6b0f8ed7db01580c6985b8bd0d47ea73dcd2e7adc8016` |
| `verify_s102_malecns_connectome.py` | `989` | `40,166` | `0o644` | `d7e5c3f948a32b8df5e098b4b883cfd62ab97fbda3385b07f2caa31c7f15b260` |
| `test_s102_malecns_connectome_r5.py` | `1,073` | `58,665` | `0o644` | `d816922e995739925d1fda08ff1004662f2e8b2c2b8aca78ddb7573ef6fef2f9` |

*(Note: `REPORT.md` is the 10th file in the track directory; its own SHA-256 is recorded externally in the frozen R2 completion receipt.)*
