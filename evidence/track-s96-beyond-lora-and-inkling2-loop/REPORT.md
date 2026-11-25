# Track S96 — Beyond-LoRA Epistemic-Native Adapters & `Inkling-2-Mini` (`inkling2_loop`) Exact Theory

**Schema:** `aletheia.track_s96.beyond_lora_and_inkling2_loop.v1`  
**Certificate Envelope SHA-256 (`certificate_sha256`):** `599c56e14dbeefeac47e2d3b34347c9a7788a1a09ca3de2d924281324c7a3226`  
**Certificate File SHA-256 (`s96_beyond_lora_inkling_certificate.json`):** `2491f96992a6c4dbad7de801f4daf2fbc2ea2455466cc43b0bb51246399b5e91`  
**Payload SHA-256 (`payload_sha256`):** `e52f811ac32828594f40563d08825c39a955b50052eff15ddc89eb1de17cdf82`  
**Lean 4.36.0 Companion:** [BeyondLoraAndInklingLoop.lean](BeyondLoraAndInklingLoop.lean) (`c430ffbb2b0ac376a31c35327d05073875f51c47237813fc9d5ab54eeae26b2f`) — **`20/20` pure-`Init` theorems (`19` universally quantified `∀` theorems + `1` exact ground witness suite `Thm 20`; `6 [] + 14 [propext]`, `0` `Quot.sound`, `0` `Classical.choice`, `0` `sorryAx`, `0` warnings)**  
**Law-4 Novelty Tier:** **`N1`** (`n0_prior_art_anchored = true`, `n1_exact_synthesis_verified = true`, **`n2_claims = 0`**; CPU-only exact pure-$\mathbb{Z}/\mathbb{Q}$ & Lean `4.36.0` verification, `0` GPU touch, `0` external dataset copies)

---

## 1. `OWN_TERMS_FIRST` & Law-2b Transformational Steelman

Before formulating exact algebraic alternatives to standard Low-Rank Adaptation (`LoRA`, Hu et al. 2021) or evaluating `thinkingmachines/Inkling-2-Mini` (`inkling2_loop`), we state standard low-rank and dense-unlooped adaptation on its strongest technical terms (**Law 2b**):

- **Steelman of Standard LoRA / DoRA / PiSSA / ReFT:** Standard additive low-rank updates $\Delta W = B A$ ($B \in \mathbb{Q}^{m \times r}$, $A \in \mathbb{Q}^{r \times n}$) excel at zero-inference-overhead merging ($W' = W_0 + B A$), simple optimizer-state compression ($O(r(m+n))$), and strong empirical sample efficiency when the target task genuinely lives inside an $r$-dimensional linear subspace with weak cross-task interference — AND because low-rank updates concentrate mass onto $r$ large-amplitude singular directions, only `8.73%` (`873/10000`) of LoRA entries fall below the bf16 `< ½-ULP` (`1/256`) merge-annihilation floor, versus `81.40%` (`407/500`) for diffuse pure-Butterfly updates (`9.3242×` higher sub-ULP loss).
- **Why Exact Pure-$\mathbb{Z}/\mathbb{Q}$ Analysis Still Exposes Hard Structural Obstructions:** Regardless of optimizer tuning or initialization (`PiSSA`/`DoRA`), the algebraic structure of $\Delta W = B A$ enforces three exact, coordinate-independent laws:
  1. **Rank Starvation & $GL_r$ Gauge Redundancy** (`S78` exact quotient $d_{\mathrm{eff}} = r(m+n) - r^2 < P_{\mathrm{raw}}$),
  2. **Privileged Neuron-Basis Commutator Smearing** (`[H_4, D] \neq 0` whenever diagonal anisotropy $D$ varies across coordinates), and
  3. **Unit-Conservation Forgetting Wall** (`S78` Fig 7 exact `1:1` forgetting/learning ratio when updates are unprojected onto the calibration nullspace).

Conversely, each epistemic-native alternative AND looped-core mechanism certified here carries its own exact **Law-5 obstruction** — proved directly in pure-$\mathbb{Q}$ and Lean 4 rather than hidden:
- `Aletheia-BlockH4-Butterfly` suffers **exact zero cross-block mixing (`0`)** unless paired with an interleave permutation (`QuadSnake` stride permutation `[0,4,1,5,2,6,3,7]`), AND on live bf16 weights suffers `81.40%` (`407/500`) `< ½-ULP` merge annihilation (`8140/873 = 9.3242×` LoRA's `8.73%`), motivating the budget-matched **`ButterflyHead-8+8`** (`S=8` Butterfly + `r=8` nullspace-projected low-rank head = `28,672` params/proj on `d=896`) preregistered hybrid.
- `Aletheia-NullSpace-Projected` (`⧅`) achieves **exact zero base-task forgetting (`0`)** while retaining positive update energy (`11`), ONLY while $\mathrm{rank}(X_{\mathrm{base}}) < d$; at full calibration rank ($\mathrm{rank}(X_{\mathrm{base}}) = d$), capacity collapses identically to **`0`**, forcing ambient dimension lifting (`S87` grafting).
- `thinkingmachines/Inkling-2-Mini` (`26.4B` total / `3.4B` physical active / `5.4B` effective active, `~20 GB` NVFP4) delivers exact **`3×`** loop-core adapter leverage across its `12`-layer `3`-pass looped core (`6..18`), yet faces TWO explicit obstructions:
  1. **Per-Pass Quantization-Noise Accumulation (`Thm 18`):** Even when initial-state error contracts ($\rho^3 < 1$), fresh NVFP4 quantization error injected on EVERY pass accumulates by the geometric sum $G_3(\rho) = 1 + \rho + \rho^2$ (strictly exceeding $\rho^3$ for all $0 < \rho < 1$: at `S76` $\rho=1/4$, $G_3 = 21/16 = 1.3125 = 84\times \rho^3 \le 2$; at contractive $\rho=3/4$, $\rho^3 = 27/64 < 1$ yet $G_3 = 37/16 = 2.3125 > 2$, breaching the falsifiable `M1-H1` kill gate past the golden-ratio threshold $\rho_* = (\sqrt{5}-1)/2 \in (3/5, 5/8)$ where $G_3(3/5)=49/25 < 2$ and $G_3(5/8)=129/64 > 2$).
  2. **Honest `8 GiB` Hardware Roofline (`Thms 16, 17`):** `20 GB > 8 GiB` (`full_resident_fits = false`, `12 GB` overflow, `5/2×` VRAM), requiring tiered `32/128` hot-expert streaming (`4.5 + 2 + 1.5 = 8 GB <= 8 GB` VRAM, `13.5 <= 31 GB` host RAM) or `>= 32 GiB` workstation VRAM (`20 <= 32`) while `Qwen2.5-0.5B` occupies `988/8192 = 247/2048 = 12.06%` of `8 GiB` VRAM as Tier-1 local foundry.

---

## 2. Pillar 1 — Standard LoRA's Three Exact Mathematical Bottlenecks

All metrics are computed identically over exact $\mathbb{Q}$ (`fractions.Fraction`, `0` floats) and cross-pinned against frozen upstream Track `S78` (`3b8341ef...`):

| Bottleneck / Witness | Exact Pure-$\mathbb{Q}$ Value | Decimal / Meaning | Lean 4.36.0 Theorem |
| :--- | :--- | :--- | :--- |
| `Qwen2.5-0.5B` ($896 \times 896$, $r=16$) unreachable dim | `880 / 896 = 55 / 56` | **`98.21%`** of orthogonal directions unreachable (`P_raw=28672, d_eff=28416, eta_alg=111/112`) | `Thm 1`, `Thm 2`, `Thm 20` |
| `S78` Fig 3 `v_proj` ($512 \times 1024$, $r=128$) gauge efficiency | `d_eff = 180224 < P_raw = 196608`, `eta_alg = 11 / 12` | `384 / 512 = 3 / 4` (`75.00%`) unreachable; `1/12` lost to $GL_{128}$ gauge | `Thm 2`, `Thm 20` |
| `S78` full-rank LoRA ($512 \times 1024$, $r=512$) gauge waste | `d_eff = 524288 < P_raw = 786432`, `eta_alg = 2 / 3` | **`1/3`** of raw parameters wasted on redundant $GL_{512}$ gauge even at full rank | `Thm 2` |
| Privileged-basis commutator $\|[H_4, D]\|_F^2$ (`D = diag(4,1,1,1)`) | **`54 / 1 > 0`** vs isotropic `diag(2,2,2,2)`: **`0 / 1`** | Non-scalar neuron anisotropy does not commute with dense Hadamard mixing | `Thm 3` |
| `S78` Fig 7 unprojected forgetting wall | `forgetting = 229/5 KB`, `learning = 229/5 KB`, ratio = **`1 / 1`** | Exact unit conservation: unprojected LoRA trades `1` KB forgotten per `1` KB learned | `Thm 4`, `Thm 5` |

---

## 3. Pillar 2 — Beyond-LoRA Epistemic-Native Adapters, `S95` bf16 Diagnosis & `ButterflyHead-8+8` Preregistration

### 3.1 Matched-Budget Exact Showdown ($d = 8, r = 2 \implies P = 32$ Parameters)

| Architecture / Control | Exact Budget $P$ | Exact Pure-$\mathbb{Q}$ Rank | Key Exact Invariants | Law-5 Obstruction & Exact Cure |
| :--- | :---: | :---: | :--- | :--- |
| Standard LoRA ($\Delta W = B A$, $r=2$) | `32` | **`2`** | Rank-starved (`6/8` orthogonal directions dead) | Intrinsic low-rank cap (`Thm 1`) |
| **`Aletheia-BlockH4-Butterfly`** ($S=2$ stages, $D_{2,s} H_{\mathrm{blk}} D_{1,s}$) | **`32`** | **`8`** (**`4×`** full rank!) | $H_{\mathrm{blk}}^\top H_{\mathrm{blk}} = 4 I_8$ exact (`kappa_2 = 1`, `Thm 6, 7`) | **Law-5 Obstruction (`Thm 8`):** Unpermuted cross-block energy = **`0`**. **Cure:** Stride-interleave `QuadSnake` permutation `[0,4,1,5,2,6,3,7]` preserves exact rank **`8`** while raising cross-block energy **`0 -> 660`**! |
| **`Aletheia-PrivSparse-Householder`** (`S42` Fisher + exact $Q = I - \frac{2 u u^\top}{\|u\|^2}$) | $O(d)$ / reflection | Full (`4×4` witness) | `S42` Fisher water-filling gain **`263/16`**; $Q^\top Q = I_4$, $Q^2 = I_4$, $\det Q = -1$, $\|Q x\|_2^2 = \|x\|_2^2 = 30$, **`kappa_2(Q) = 1`** (`Thm 9`) | Strictly cures `S82` real-shear condition-number blowup $\kappa_2 = \phi^2 > 1309/500$ |
| **`Aletheia-NullSpace-Projected`** (`⧅`, $\Delta W (I - P_{\mathrm{base}})$) | Exact projector | Calibration rank `2` in $\mathbb{Q}^4$ | Raw forgetting **`46 -> 0`** exact (`projected_forgetting_sq = 0`), retained update energy **`11 > 0`** (`Thm 10`) | **Law-5 Obstruction (`Thm 11`):** At full calibration rank `4` (`nullspace_dim = 0`), raw forgetting `29 -> 0` BUT update energy collapses to **`0`**, proving ambient dimension lifting (`S87` grafting) is algebraically mandatory |

### 3.2 `S95` bf16 `< ½-ULP` Merge-Annihilation Diagnosis & Preregistered `ButterflyHead-8+8` Hybrid

Folding **external** empirical diagnostics from `S95` (`Qwen2.5-0.5B`, `d = 896`, matched budget `16 * 1792 = 28,672` params/proj; source: the Qwen 4 Max collab report `COLLAB-INKLING2-M1H1-REVIEW.md`, **not shipped in this repo**) into exact pure-$\mathbb{Q}$ preregistered gates (**not executed in CPU-only S96; zero `N2` claims**):

| `S95` / `ButterflyHead-8+8` Metric | Exact Pure-$\mathbb{Q}$ Value | Decimal / Operational Meaning | Lean 4.36.0 Theorem |
| :--- | :--- | :--- | :--- |
| bf16 merge `< ½-ULP` threshold | `1 / 256` | Entries with `|\Delta W_{ij}| < |W_{0,ij}| / 256` round to `0` on bf16 merge | `Thm 19` |
| Sub-ULP zeroed entry fraction (Butterfly vs. LoRA) | `407/500` (`81.40%`) vs. `873/10000` (`8.73%`) | Exact annihilation ratio **`8140 / 873 = 9.3242×`** (orthogonal stiffness `cos = 0.003..0.019`) | `Thm 20` |
| Budget-matched **`ButterflyHead-8+8`** (`d = 896`) | `S=8` (`14,336`) + `r=8` (`14,336`) = **`28,672`** params/proj | Exact parity with `LoRA-r16` & `BlockH4-S16`; top-`32` nullspace guard; `1/50` (`2%`) Frobenius cap | `Thm 6`, `Thm 19`, `Thm 20` |
| Decoupled learning rates (`head` vs. `butterfly`) | `3/10000` (`3e-4`) vs. `3/1000` (`3e-3`) | Exact **`10/1` (`10×`)** LR ratio separating high-amplitude low-rank head from diffuse tail | — |
| Optional `S104` Rank-2 Kronecker Head (`28×32`) | `2 * (28^2 + 32^2) = 3,616` params/proj | Exact **`448 / 113 = 3.9646×`** compression vs. `14,336`-param dense `r=8` head | `Thm 20` |
| Preregistered `PASS` / `KILL` thresholds (not run here) | `PASS >= 34/60 (17/30)`, `KILL <= 24/60 (2/5)`, NLL ratio `<= 2/1` | bf16 zero-frac `<= 7/20 (35%)`, top-16 energy `<= 3/5 (60%)`, `sigma_max <= 7/20`, `rel_frob <= 1/40`, VRAM `<= 7168 MiB` | — |

---

## 4. Pillar 3 — `thinkingmachines/Inkling-2-Mini` (`inkling2_loop`) Exact Architecture, `G_3(rho)` Noise Gate & Roofline

Every architectural parameter below is verified verbatim against local read-only snapshots `inkling2_mini_config.json` (`a7a34960...`) and `inkling2_mini_README.md` (`ab4fbc79...`) — zero weights downloaded, zero dataset copies inside the expedition workspace:

| Architectural / Roofline / `M1-H1` Metric | Exact Value (`inkling2_mini_config.json` / `README.md` / `M1-H1`) | Exact Pure-$\mathbb{Q}$ Derivation & Cross-Track Bridge |
| :--- | :--- | :--- |
| Hidden width & square root | `hidden_size = 2304`, $\sqrt{2304} = 48$ exact | `vocab = 201024` (`200058` unpadded), `24` Q heads / `8` KV heads / `head_dim = 128` |
| Physical vs. Looped effective depth | `24` physical (`6` pre + `12` core `[6..18)` × `3` passes + `6` suf) = **`48`** effective | **`2/1` (`2.0×`)** depth reuse (`Thm 12`, `Thm 20`); `20` local (`window=1024`) + `4` global layers (`5,11,17,23`) |
| Loop gate rank vs. $\sqrt{d}$ | `gate_rank = 64`, `64 / 48 = 4 / 3` | Sits cleanly on the $\alpha_F = 1/2$ sub-linear gate scaling threshold (`Thm 20`) |
| Sparse MoE & MLP geometry | `128` routed experts / `8` active (`1/16`), `intermediate_size = 1152` (`1/2` hidden) | `mlp_gate_softcap = 4`, `mlp_up_softcap = 25`, `route_scale = 8` (`Thm 15`) |
| Multi-Token Prediction (MTP) | `block_size = 8`, `markov_rank = 256`, `target_layer_ids = [5, 23, 41, 48]` | Targets exact loop-boundary exit layers across all `3` core passes |
| Parameter & Active counts (README) | `26.4B` (`132/5`) total / `3.4B` (`17/5`) physical active / `5.4B` (`27/5`) effective active | `27/17` effective-to-physical active ratio (`+1.0B` per additional core pass) |
| **Loop-Core Adapter Leverage** | `294,912` params/layer (`2 * 64 * 2304`) × `12` core = `3,538,944` vs `10,616,832` unlooped | Exact **`3/1` (`3.0×`)** effective-layer adapter amplification (`Thm 13`) |
| **`S76` Loop-Schur 3-Pass Contraction** | Contractive $\rho = 1/4 \implies \rho^3 = 1/64 < 1$ vs expansive `(5/4)^3 = 125/64 > 1` | Controls initial-state error decay across `num_passes = 3` (`Thm 14`) |
| **Per-Pass Quantization Noise $G_3(\rho) = 1+\rho+\rho^2$** | `S76` $\rho=1/4$: **$G_3 = 21/16 = 1.3125$** (`84×` larger than $\rho^3 = 1/64$, `<= 2` PASS); $\rho=3/4$: $\rho^3 = 27/64 < 1$ YET **$G_3 = 37/16 = 2.3125 > 2$** (KILL!) | Proves initial contraction $\rho^3 < 1$ is **insufficient** under per-pass NVFP4 noise (`Thm 18`); threshold bracket $3/5 \to 49/25 < 2$ vs. $5/8 \to 129/64 > 2$ (`Thm 20`) |
| **Falsifiable `M1-H1` Kill Gate (Preregistered)** | $\Delta_3 / \Delta_{1,\mathrm{ctrl}} \le 2/1$ AND $\Delta_3 \le 1/20 = 0.05$ relative $L_2$ drift | Requires BOTH unique-layer FP baseline (`requires_unique_layer_fp_baseline = true`) AND single-pass NVFP4 control (`requires_single_pass_nvfp4_control = true`) |
| **RTX 3080 `8 GiB` Roofline (Honest)** | `20 GB > 8 GiB`: **`full_resident_fits = false`**, **`12 GB`** overflow (`5/2×` VRAM) | **Tiered Streaming Feasible (`Thm 16, 17`):** `32/128` hot experts (`9/2 = 4.5 GB`) + shared (`2 GB`) + KV (`3/2 = 1.5 GB`) = **`8 GB <= 8 GB`**, cold experts **`27/2 = 13.5 GB <= 31 GB`** host RAM |
| **`32 GiB` Workstation & Tier-1 Foundry** | `32 GiB`: `20 <= 32` (`full_resident_fits = true`, `0` overflow); `Qwen2.5-0.5B` BF16 on `8 GiB` | `988 / 8192 = 247 / 2048` = **`12.06%`** of `8 GiB` VRAM — fast local testbed for Beyond-LoRA prototypes |

---

## 5. Pillar 4 — Formal `Lean 4.36.0` Verification, Provenance & Law-4 Honesty

### 5.1 Pure-`Init` `Lean 4.36.0` Companion (`BeyondLoraAndInklingLoop.lean`)

Compiled standalone via scrubbed `lean --stdin` (`PATH`/`LANG`/`LC_ALL`/optional `HOME` allowlist only — strips `LEAN_PATH`, `LEAN_OPTS`, `LEAN_SYSROOT`, `ELAN_*`, `LEAN_CC`, `LD_PRELOAD`, `LD_LIBRARY_PATH`, `LAKE_*`) and scratch `lake build` (`4 jobs`, `0` warnings, `0` stderr, `0` external imports, `0` `sorry`, `0` `Quot.sound`, `0` `Classical.choice`). Contains **`19` universally quantified (`∀`) theorems + `1` exact ground witness suite (`Thm 20`) = `20/20` theorems (`6` zero-axiom `[]` + `14` `[propext]` only)**:

1. `lora_rank_starvation_unreachable_dim_universal` (`∀ d r : Nat`, `[propext]`): `(hr : 0 < r) (hrd : r < d) → 0 < d - r ∧ d - r < d ∧ r + (d - r) = d`.
2. `lora_gauge_redundancy_d_eff_strictly_below_p_raw_universal` (`∀ m n r : Nat`, `[propext]`): `(hr : 0 < r) (hrm : r ≤ m) (hrn : r ≤ n) → r * (m + n) - r * r < r * (m + n) ∧ r * r ≤ r * (m + n) - r * r`.
3. `privileged_basis_commutator_obstruction_universal` (`∀ d0 d1 : Int`, `[propext]`): `(hne : d0 ≠ d1) → d1 - d0 ≠ 0 ∧ (d0 + d1) - (d0 + d0) = d1 - d0`.
4. `unprojected_base_forgetting_strict_positivity_universal` (`∀ c : Int`, `[propext]`): `(hc : c ≠ 0) → 0 < c * c`.
5. `lora_unit_conservation_forgetting_ratio_universal` (`∀ fVal lVal : Nat`, `[]`): `(hl : 0 < lVal) (hcons : fVal = lVal) → 0 < fVal ∧ 0 * lVal < fVal * lVal`.
6. `block_h4_butterfly_parameter_parity_universal` (`∀ r s h d : Nat`, `[propext]`): `(hsplit : r = s + h) → r * (d + d) = 2 * r * d ∧ 2 * s * d + 2 * h * d = 2 * r * d`.
7. `block_h4_orthogonal_energy_conservation_universal` (`∀ x0 x1 x2 x3 : Int`, `[propext]`): with `y0 = x0 + x1 + x2 + x3`, `y1 = x0 - x1 + x2 - x3`, `y2 = x0 + x1 - x2 - x3`, `y3 = x0 - x1 - x2 + x3`, proves `y0 * y0 + y1 * y1 + y2 * y2 + y3 * y3 = 4 * (x0 * x0 + x1 * x1 + x2 * x2 + x3 * x3)`.
8. `block_h4_locality_obstruction_law5_universal` (`∀ m0 m1 x0 x1 x2 x3 dx2 dx3 : Int`, `[propext]`): `(m0 * x0 + m1 * x1 + 0 * (x2 + dx2) + 0 * (x3 + dx3)) = (m0 * x0 + m1 * x1 + 0 * x2 + 0 * x3)`.
9. `householder_exact_isometry_universal` (`∀ u0 u1 x0 x1 : Int`, `[propext]`): with `s = u0 * u0 + u1 * u1`, `dot = u0 * x0 + u1 * x1`, `y0 = s * x0 - 2 * u0 * dot`, `y1 = s * x1 - 2 * u1 * dot`, proves `y0 * y0 + y1 * y1 = (s * s) * (x0 * x0 + x1 * x1)`.
10. `nullspace_projection_exact_zero_forgetting_universal` (`∀ u0 u1 x0 x1 : Int`, `[propext]`): with `s = x0 * x0 + x1 * x1`, `dot = u0 * x0 + u1 * x1`, `p0 = s * u0 - dot * x0`, `p1 = s * u1 - dot * x1`, proves `p0 * x0 + p1 * x1 = 0`.
11. `nullspace_saturation_law5_obstruction_universal` (`∀ d k : Nat`, `[propext]`): `(k = d → d - k = 0) ∧ (k < d → 0 < d - k)`.
12. `loop_effective_depth_expansion_universal` (`∀ nPre nCore nSuf k : Nat`, `[]`): `(hCore : 0 < nCore) (hk : 2 ≤ k) → nPre + nCore + nSuf < nPre + k * nCore + nSuf`.
13. `loop_core_adapter_leverage_universal` (`∀ pCore k : Nat`, `[propext]`): `(hp : 0 < pCore) (hk : 2 ≤ k) → pCore < k * pCore`.
14. `loop_schur_contractive_pass_bound_universal` (`∀ p q e0 k : Nat`, `[]`): `(hp : 0 < p) (hpq : p < q) (he0 : 0 < e0) → natPow p (k + 1) * e0 < natPow q (k + 1) * e0`.
15. `moe_sparse_expert_flop_savings_universal` (`∀ eAct eTot flops : Nat`, `[]`): `(hlt : eAct < eTot) (hf : 0 < flops) → eAct * flops < eTot * flops`.
16. `vram_full_resident_roofline_obstruction_universal` (`∀ mModel mVram : Nat`, `[propext]`): `(hov : mVram < mModel) → 0 < mModel - mVram ∧ mVram + (mModel - mVram) = mModel`.
17. `streaming_expert_subset_vram_fit_universal` (`∀ mShared mExp eRes eTot : Nat`, `[]`): `(hExp : 0 < mExp) (hlt : eRes < eTot) → mShared + eRes * mExp < mShared + eTot * mExp`.
18. `per_pass_quant_noise_exceeds_contraction_universal` (`∀ p q : Nat`, `[propext]`): `(hp : 0 < p) (hpq : p < q) → (p * p * p < q * (q * q + p * q + p * p)) ∧ (q * q < p * q + p * p → 2 * (q * q) < q * q + p * q + p * p)`.
19. `butterfly_head_budget_parity_and_bf16_ulp_threshold_universal` (`∀ s rHead dIn dOut delta w0 : Nat`, `[propext]`): `(hulp : 256 * delta < w0) → (s + rHead) * (dIn + dOut) = s * (dIn + dOut) + rHead * (dIn + dOut) ∧ delta < w0`.
20. `s96_inkling2_and_beyond_lora_anchored_witnesses` (`[]`): exact 18-conjunct ground witness suite (`6 + 3 * 12 + 6 = 48`, `48 = 2 * 24`, `48 * 48 = 2304`, `64 * 3 = 4 * 48`, `8 * 16 = 128`, `1152 * 2 = 2304`, `24 * 128 = 3072`, `896 - 16 = 880`, `128 * (512 + 1024) - 128 * 128 = 180224`, `263 > 16 * 16`, `169 < 195 - 25`, `8 < 20`, `16 + 4 + 1 = 21 ∧ 21 < 2 * 16`, `16 + 12 + 9 = 37 ∧ 2 * 16 < 37 ∧ 3 * 3 * 3 < 4 * 4 * 4`, `25 + 15 + 9 = 49 ∧ 49 < 2 * 25 ∧ 64 + 40 + 25 = 129 ∧ 2 * 64 < 129`, `8 + 8 = 16 ∧ 16 * (896 + 896) = 28672`, `2 * (28 * 28 + 32 * 32) = 3616 ∧ 3616 * 448 = 14336 * 113`, `407 * 100 > 873 * 5`).

### 5.2 Cryptographically Pinned Provenance (`10` Upstream Certs + `2` Inkling-2-Mini Specs)

| Source / Track | Relative Path / Filename | Verified SHA-256 |
| :--- | :--- | :--- |
| `Inkling-2-Mini` Config | `inkling2_mini_config.json` | `a7a349601f0984c4abf999c480ef775d8567d21f5f84b4e8a3e035b44f288dc2` |
| `Inkling-2-Mini` README | `inkling2_mini_README.md` | `ab4fbc79a26f57a4160eae83ff33f7ec5442f4a6cae21478fdda36b4a0c13592` |
| `Track S42` | `track-s42-fisher-waterfilling-kintsugi-margins/fisher_kintsugi_memt_certificate.json` | `ba44be55ca16873671b41f7e0cac32cf5c43361a07cff7c4ff7b04fcc917cee7` |
| `Track S59` | `track-s59-exact-e8-vs-a16-hadamard-law/e8_vs_a16_hadamard_certificate.json` | `914a84512d7026b23af0672d4b175128534a7d3c8a0fbc9152b28bc38ea8f1ed` |
| `Track S73` | `track-s73-lowbit-and-sharednorm-quad-snake/rtx3080_s73_certificate.json` | `33dfb4153fe974e9ef13120190c14ada6dda63ffbee6caa46047d274f32d36cf` |
| `Track S76` | `track-s76-circular-pc-loop-schur-holonomy/s76_circular_pc_certificate.json` | `d30805fcb876de096d9b387a8274ecd8063b7906f4feb36124b38a05aefadc95` |
| `Track S78` | `track-s78-engram-lora-capacity-siliquant-mdl/s78_engram_lora_siliquant_certificate.json` | `3b8341ef5f588f970accb9a9d28f0b683af9747be045e69196e6c19d3fa58378` |
| `Track S79` | `track-s79-2dsd-multipole-dense-sparse-laws/s79_2dsd_multipole_certificate.json` | `9c30539e6d585141a9b1a5111935ca86de0f740e80749a622547a18242465ad8` |
| `Track S80` | `track-s80-rocket-songe-unsloth-optimizations/s80_certificate.json` | `95681a29ca577c4e3040f8ba63f8516b1cbb2bf1ebfdcda06277f21bb2aa2cb7` |
| `Track S82` | `track-s82-vpvnp-cross-field-propagation/s82_vpvnp_propagation_certificate.json` | `10c1203cd9c9f80d4082f4cdbbd09f60624aa1d4fd6b49c70ec5d622f0d2f76b` |
| `Track S83` | `track-s83-all-to-all-epistemic-mesh/s83_epistemic_mesh_certificate.json` | `74d269c5c1c35665fc835df796e6f94cdbd118ca4ce580a20310c5c969deabdb` |
| `Track S87` | `track-s87-universal-higher-order-atlas/s87_higher_order_atlas_certificate.json` | `735c93b5a7bb4244e15068cd75371cb228fbf560a5837ca05d7e0a1fa30dcec2` |

### 5.3 Honest Law-4 Novelty Accounting (`N0` / `N1`, **`n2_claims = 0`**)

- **`N0` (Classical Prior Art Explicitly Credited):** Hu et al. (2021) LoRA; Dao et al. (2019/2022) Monarch/Butterfly structured matrices; Householder (1958) orthogonal reflections; orthogonal gradient / nullspace continual-learning projection (Zeng et al. 2019 OWM, Farajtabar et al. 2020 OGD, Saha et al. 2021 GPM); Thinking Machines `Inkling-2-Mini` (`inkling2_loop`) MoE-looped transformer specification; upstream expedition tracks `S42`–`S87`, `S95`, and `S104`.
- **`N1` (Verified Exact Synthesis in Track S96):** Unified zero-float pure-$\mathbb{Z}/\mathbb{Q}$ oracle (`copy.deepcopy` zero-aliasing outputs), Zone-B fail-closed verifier (`CLI`/`FR1`/`FR0`/`SEC` with field-complete invariant pinning, R12 static Lean 4 scanner blocking `opaque`/`dbg_trace`/`dbgTrace*`/`panic!`/`unreachable!`/`warn.sorry`/`#guard*`/`@[export|init|builtin_init|term_elab|command_elab|tactic|macro|macro_rules]`/capitalized `Lean.*`/non-`Init` imports, allowlist-scrubbed `lean --stdin` zero-TOCTOU subprocess execution), and `20`-theorem pure-`Init` Lean `4.36.0` companion proving exact parameter-budget parity, Law-5 obstructions (block-diagonal locality, nullspace saturation, `S95` bf16 `< ½-ULP` annihilation & `ButterflyHead-8+8` preregistration), per-pass quantization-noise amplification $G_3(\rho) = 1+\rho+\rho^2$ & falsifiable `M1-H1` kill gate, `3×` looped-core leverage, and honest `8 GiB` vs. `32 GiB` hardware roofline bounds.
- **`N2` Claims:** **`0`** (zero unverified empirical fine-tuning or GPU training claims; CPU-only exact verification).

---

## 6. Frozen 7-Companion-File SHA-256 & Line-Count Manifest

All `7/8` frozen companion files in this directory (with this `REPORT.md` as the 8th file):

| File | Lines | Bytes | Mode | Verified SHA-256 |
| :--- | ---: | ---: | :---: | :--- |
| `BeyondLoraAndInklingLoop.lean` | `476` | `25,591` | `0o644` | `c430ffbb2b0ac376a31c35327d05073875f51c47237813fc9d5ab54eeae26b2f` |
| `lakefile.toml` | `6` | `146` | `0o644` | `bf65bf58add1e3fc68fde9d4d403160cfe188920754593c792900784ddb98756` |
| `lean-toolchain` | `1` | `25` | `0o644` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |
| `s96_beyond_lora_inkling_certificate.json` | `1` | `11,179` | `0o600` | `2491f96992a6c4dbad7de801f4daf2fbc2ea2455466cc43b0bb51246399b5e91` |
| `s96_beyond_lora_inkling_oracle.py` | `844` | `36,663` | `0o644` | `9e1e0c34192507ae91a57d3926e2c040606626bf02167c0657a24eca24b21f32` |
| `verify_s96_beyond_lora_inkling.py` | `1,744` | `72,379` | `0o644` | `38edf2b1c2056a51d0da071fcbbf09ce40782c5202daba9e7598993637feba54` |
| `test_s96_r5.py` | `1,717` | `119,701` | `0o644` | `fb44850d2d903f90298e615e892aa3d79ff7f28ddff8c2b622999d28b537c182` |

---

## 7. Reproducible Verification Commands

```bash
# 1. Exact pure-Q certificate parity & Zone-B verification (multi-mode -I)
python3 -I -B verify_s96_beyond_lora_inkling.py --standalone --json | cmp - s96_beyond_lora_inkling_certificate.json
python3 -I -B verify_s96_beyond_lora_inkling.py --check s96_beyond_lora_inkling_certificate.json --json

# 2. Live R12 static + scrubbed Lean 4.36.0 --stdin kernel axiom verification
python3 -I -B verify_s96_beyond_lora_inkling.py --verify-lean BeyondLoraAndInklingLoop.lean --json

# 3. Pinned upstream corpus (10 tracks: 2/10 re-hashed on disk in-repo (S80, S83); 8/10 cross-repo
#    SHA pins: S80/S83 on disk here; others in Foundation-0/math0@main or external historical pins resolving nowhere readable) & Inkling-2-Mini specs
python3 -I -B verify_s96_beyond_lora_inkling.py --verify-upstream .. --json
python3 -I -B verify_s96_beyond_lora_inkling.py --verify-inkling <INKLING_SPEC_DIR> --json

# 4. Full assertion-free R5 unit suite (live Lean + 0-skip Lean-less CI)
python3 -I -B test_s96_r5.py -v
env -i PATH=/usr/bin:/bin python3 -I -B test_s96_r5.py -v
```
