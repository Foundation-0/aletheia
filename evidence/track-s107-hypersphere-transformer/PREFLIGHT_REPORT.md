# `PREREG-S107` + `AMENDMENT1` — CPU-Only Pre-Flight & RTX 3080 Harness Report

- **Track:** `track-s107-hypersphere-transformer/` (`EXP-Q08a..c`: Native 4D Hypersphere-Transformer `H7a`, `H7b`, `H7c`)
- **Locked Protocol Sources:**
  - `notes/sphere_pi_forces_2026_11_25/PREREG_S107_NATIVE_HYPERSPHERE_TRANSFORMER.md` (`6e197152...`)
  - `notes/sphere_pi_forces_2026_11_25/PREREG_S107_S108_AMENDMENT1_COUNCIL_HARDENING.md` (`5a9ddf08...`, mandatory overrides applied)
- **Execution Posture:** Strictly CPU-only (`CUDA_VISIBLE_DEVICES=""`, `nice -n 15`, `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`, `torch.set_num_threads(1)`, `0` GPU touch, `WEIGHTS=0` inside repository tree, `0` GitHub writes)
- **Pre-Flight Verdict:** **`9/9` MANDATORY CPU GATES PASS** (`3`-mode `-I` bit-identical `payload_sha256 = fc493a4f4beaf24707052d099c5bef46109194e580428fd851622490662ed0c1`; wall-clock `~7–9 s` per full run)

---

## 1. Module Architecture & Amendment-1 Compliance

1. **`s107_models.py`** — Modular PyTorch implementations of all `21` amended `H7a`/`H7b`/`H7c` arms, deterministic per-module `torch.Generator(seed)` initialization (zero global-RNG leakage), analytical MAC-to-FLOP/token accounting, exact RTN symmetric per-output-channel group-128 PTQ (`3`-bit / `4`-bit, embeddings excluded, zero post-quant renorm), and the `Track S96` `M1-H1` empirical contraction ($\rho_t$) & $G_3(\rho)$ drift monitor:
   - **`H7a` (`10` arms):** `Cyl`, `S3-Polar` ($a(1+\cos^2\psi_\ell)$), `S3-Equatorial` ($a(1+\sin^2\psi_\ell)$), AND **both** dual permuted-width adversarial nulls (`S3-Permuted-Pol` and `S3-Permuted-Eq`), crossed with Pre-Norm+RoPE (`Std`) and unit-hypersphere `nGPT` (`Loshchilov et al. 2024`, `N0` anchor). Width schedules enforce exact integer sum conservation ($\sum_\ell d_{\mathrm{ff}}(\ell) = 12 \times 864 = 10,368$).
   - **`H7b` (`5` arms, `AMENDMENT1 §1` complete redesign):** Retracts fixed-axis `Quat-SU2-Rel` and cancelling right-multiplied $\tau_\ell$ permanently. Implements **Data-Dependent Path-Ordered $SU(2)$ Holonomy** ($U(t) = \Delta u_0 \star \Delta u_1 \star \dots \star \Delta u_t \in SU(2)$ via associative Hillis–Steele parallel prefix scan in $\lceil \log_2 T \rceil$ steps, giving exact interval holonomy $U(s)^{-1} U(t) = \Delta u_{s+1} \star \dots \star \Delta u_t$ free of prefix leakage) head-to-head against `RoPE-2D-Std`, `RoPE-2D-nGPT`, **`LieRE-4D-Abelian-nGPT`** (`N0` anchor, fixed learned $\Omega_b \in \mathfrak{so}(4)$), and `Block4-RandOrtho-nGPT` (frozen Haar $SO(4)$ + 2D RoPE). `W_omega` parameters (`76,800`/layer) are offset exactly via `d_ff: 864 -> 784`.
   - **`H7c` (`6` arms, `AMENDMENT1 §3` + `COLLAB-INKLING2`/`COLLAB-CLAUDE`):** `CliffordTorus-HopfLoop` (`2` pre + `4` shared core × `R` passes + `2` suffix) with antipodal-safe SLERP ($\sqrt{\|x\|^2 + \varepsilon^2}$ floor, $\varepsilon = 10^{-4}$), clamped $\hat{\alpha}_r = \operatorname{sigmoid}(\tilde{\alpha}_r)\cdot 0.45\pi$, **non-degenerate inter-pass Hopf fiber rotation** (`unaliased_coprime` $\phi_r = 2\pi r / 11$ default + explicit `pinned_train_step` $\phi_r = 2\pi r / 3$ option), pinned **per-pass KV recompute** (zero cross-pass KV caching), and `use_reentrant=False` gradient-checkpointed BPTT, head-to-head against `Unlooped-16L` (FLOP-matched upper bound), `Unlooped-8L` (`P_physical` iso-param control), `FlatLoop-Std`, `SphereLoop-NoClock`, and `SphereLoop-RandRotClock` (frozen Haar $O(d)$ orthogonal matrix per pass via QR with positive diagonal $R$, `det = ±1`).
2. **`s107_train_eval.py`** — Offline-ready (`HF_HUB_OFFLINE=1`) RTX 3080 & CPU runner with exact UTF-8 byte BPB scoring (`fp32` log-softmax, BOS excluded, EOS scored, `decode(encode(x)) == x`), deterministic non-Abelian $S_3$ (order `6`) & $A_5$ (order `60`) group-word state-tracking generator (`8..64` train / `65..192` OOD test), `H7c` bracket-depth extrapolation probe, `3`-bit/`4`-bit RTN PTQ, `M1-H1` $G_3(\rho)$ checkpoint diagnostics, and JSON-only output (`WEIGHTS=0`).
3. **`s107_cpu_preflight.py`** + **`s107_cpu_preflight_receipt.json`** — Self-contained `9`-gate CPU-only verification suite confirming every algebraic, numerical, and `CS-08` parity contract before authorizing any GPU lease.

---

## 2. Exact Full-Scale `CS-08` Parameter & FLOP/Token Parity Tables (`seq_len = 512`, `V = 260`)

### 2.1 `H7a` (`L = 12`, `d_model = 320`, `n_heads = 8`, mean `d_ff = 864`)
- **Width Multisets:**
  - `S3-Polar`: `[1136, 1072, 944, 784, 656, 592, 592, 656, 784, 944, 1072, 1136]` (contrast `1136/592 = 1.9189`)
  - `S3-Equatorial`: `[592, 656, 784, 944, 1072, 1136, 1136, 1072, 944, 784, 656, 592]` (contrast `1.9189`)
  - `S3-Permuted-Pol`: exact multiset match, Spearman $\rho_S = \mathbf{0.0000}$ (`<= 0.30`)
  - `S3-Permuted-Eq`: exact multiset match, Spearman $\rho_S = \mathbf{-0.1429}$ (`<= 0.30`)
- **Verified Parity Across All `10` Arms:**
  - Max non-embedding parameter deviation: **`0.1631%`** (`<= 0.50%` gate)
  - Max forward FLOPs/token deviation: **`0.0000%`** (`<= 1.00%` gate)

### 2.2 `H7b` (`L = 12`, `d_model = 320`, `n_heads = 8`, `d_head = 40` = `10` quaternion 4-blocks/head)

| Arm | Non-Emb Params | Total Params | Fwd FLOPs / Tok (`T=512`) | Param Diff vs `RoPE-2D-nGPT` | FLOP Diff vs `RoPE-2D-nGPT` |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `RoPE-2D-Std` | `14,876,480` | `14,959,680` | `33,835,520` | `-0.1628%` | `0.0000%` |
| `RoPE-2D-nGPT` | `14,900,737` | `14,983,937` | `33,835,520` | `0.0000%` | `0.0000%` |
| `LieRE-4D-Abelian-nGPT` (`N0`) | `14,906,497` | `14,989,697` | `33,866,240` | `+0.0387%` | `+0.0908%` |
| `Block4-RandOrtho-nGPT` | `14,900,737` | `14,983,937` | `33,866,240` | `0.0000%` | `+0.0908%` |
| **`SU2-Holonomy-Scan-nGPT`** | **`14,898,817`** | **`14,982,017`** | **`34,131,200`** | **`-0.0129%`** | **`+0.8739%`** |

All `5` arms pass strict `<= 0.50%` non-embedding parameter parity (`max = 0.1628%`) AND `<= 1.00%` FLOP/token parity (`max = 0.8739%`).

### 2.3 `H7c` (`2` Pre + `4` Core × `R=3` + `2` Suffix = `16` Eff. Layers; `d_model = 256`, `n_heads = 8`, `d_ff = 688`)

| Arm | Non-Emb Params | Total Params | Fwd FLOPs/Tok (`R=3`) | Fwd FLOPs/Tok (`R=8`) | Role / Parity Status |
| :--- | ---: | ---: | ---: | ---: | :--- |
| `Unlooped-16L` | `12,656,896` | `12,723,456` | `29,624,320` | — | `16L` FLOP upper bound (`2.00x` phys / `3.00x` core) |
| `Unlooped-8L` | `6,328,576` | `6,395,136` | `14,878,720` | — | Iso-param `P_physical` control (`8` phys layers) |
| `FlatLoop-Std` | `6,328,577` | `6,395,137` | `29,624,320` | `66,488,320` | `+0.0000%` vs `8L` params · `0.0000%` vs `16L` FLOPs |
| `SphereLoop-NoClock` | `6,341,378` | `6,407,938` | `29,624,320` | `66,488,320` | `+0.2023%` vs `8L` params · `0.0000%` vs `16L` FLOPs |
| `SphereLoop-RandRotClock` | `6,341,378` | `6,407,938` | `30,017,536` | `67,536,896` | `+0.2023%` vs `8L` params · `+1.3273%` vs `16L` FLOPs |
| **`CliffordTorus-HopfLoop`** | **`6,341,378`** | **`6,407,938`** | **`29,628,928`** | **`66,500,608`** | **`+0.2023%` vs `8L` params · `+0.0156%` vs `16L` FLOPs** |

All looped arms pass strict `<= 0.50%` physical-param parity (`max = 0.2023%`) and `<= 5.0%` `R=3` FLOP parity (`max = 1.3273%`; `CliffordTorus-HopfLoop` is `+0.0156%`).

---

## 3. All `9/9` Mandatory CPU Pre-Flight Gates (`s107_cpu_preflight_receipt.json`)

| Gate | Locked Requirement (`AMENDMENT1` / `COLLAB` Audits) | Key Machine-Verified Measurements | Verdict |
| :--- | :--- | :--- | :---: |
| **`G1`** | `H7c` SLERP antipodal `Norm(0)` zero-NaN fwd/bwd & $\alpha_r$ clamp | Exact $\delta = -h, \alpha = \pi/4$: `0.0` out, `0.0` grads, zero NaN/Inf in **FP32 & BF16** | **PASS** |
| **`G2`** | Explicit Hopf clock law (`R_test={3,4,6,8}`) & non-cancellation | `pinned` aliases at `r=3`; `coprime` `8/8` distinct phases; isometry err `1.2e-7`; state diff vs NoClock `3.4813` (logit diff `57.3242`) | **PASS** |
| **`G3`** | Unit-norm drift `<= 1e-3` across `R_test in {3, 4, 6, 8}` | FP32 max `|\|h\| - 1| <= 2.0e-7` across all 3 spherical looped modes; BF16 `<= 0.00597` | **PASS** |
| **`G4`** | Per-pass KV recompute justification & iso-param / iso-FLOP audit | Pass state mutation L2 `[0.1703, 0.7187, 1.3255]` (`> 0`); `max_param=0.2023%`, `max_flop=1.3273%` | **PASS** |
| **`G5`** | `H7a` profiles, dual `Permuted-Pol`/`Eq` nulls, Spearman `<= 0.30` | Contrast `1.9189`; Spearman `0.0` (`Pol`), `-0.1429` (`Eq`); `max_param=0.1631%`, `max_flop=0.0000%` | **PASS** |
| **`G6`** | `H7b` $SU(2)$ parallel scan exactness, interval holonomy, non-Abelian | Parallel vs seq err `5.7e-7`; unit err `1.2e-7`; prefix leak `2.4e-7`; $SU(2)$ comm `0.9243` vs `LieRE` `2.4e-7`; `max_flop=0.8739%` | **PASS** |
| **`G7`** | `H7b` $S_3$/$A_5$ group axioms & holonomy `W_omega` grad flow | `S_3` (`order=6`, `18` non-comm) & `A_5` (`order=60`, `3,300` non-comm) assoc exact; `W_omega` grad L2 `[0.0291, 0.0280]` | **PASS** |
| **`G8`** | `H7c` `M1-H1` $\rho_t$, $G_3(\rho)$ monitor & RTN group-128 PTQ | Embed diff `0.0`; finite 3b/4b KL & $\rho_t$ in FP32/BF16 (init `delta_3/delta_1 ≈ 2.84–3.04`, flagging untrained `M1-H1` regime cleanly) | **PASS** |
| **`G9`** | Micro-train, checkpointed BPTT (`R=3/8`), UTF-8 BPB, determinism | Loss drops across `H7a`/`H7b`/`H7c` (incl. `R={3,4,6,8}` extrap); UTF-8 round-trip exact; CPU determinism `0.0`; `4/4` neg controls | **PASS** |

---

## 4. Ready-to-Launch RTX 3080 Commands (Authorized Only After `EXP-Q06` Releases GPU Lease)

Recommended execution order per `COLLAB-CLAUDE M8`: **`H7a -> H7c -> H7b`**, `HF_HUB_OFFLINE=1`, `WEIGHTS=0`, `mlos gpu-lease --mode train`, `mlos stamp-run --zone B`:

```bash
# 1. H7a (10 arms x 5 seeds, offline wikitext-2 or multi-domain corpus)
mlos gpu-lease --mode train -- mlos stamp-run --zone B --out track-s107-hypersphere-transformer/mlos_zone_b_h7a.json -- \
  env HF_HUB_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 "$VENV_PY" -I -B \
  track-s107-hypersphere-transformer/s107_train_eval.py \
  --track H7a --device cuda --amp-bf16 --seq-len 512 --steps 2000 --batch-size 8 \
  --seeds 42 137 2026 31415 27182 \
  --corpus-path "$LOCAL_CORPUS_PARQUET" \
  --out-json track-s107-hypersphere-transformer/h7a_gpu_results.json

# 2. H7c (6 arms x 5 seeds, checkpointed BPTT + unaliased coprime Hopf clock + M1-H1 monitor)
mlos gpu-lease --mode train -- mlos stamp-run --zone B --out track-s107-hypersphere-transformer/mlos_zone_b_h7c.json -- \
  env HF_HUB_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 "$VENV_PY" -I -B \
  track-s107-hypersphere-transformer/s107_train_eval.py \
  --track H7c --device cuda --amp-bf16 --grad-checkpoint --clock-law unaliased_coprime \
  --seq-len 512 --steps 2000 --batch-size 8 --seeds 42 137 2026 31415 27182 \
  --corpus-path "$LOCAL_CORPUS_PARQUET" \
  --out-json track-s107-hypersphere-transformer/h7c_gpu_results.json

# 3. H7b (5 arms x 5 seeds, redesigned Data-Dependent SU(2) Holonomy vs RoPE-2D / LieRE-4D / Block4-RandOrtho)
mlos gpu-lease --mode train -- mlos stamp-run --zone B --out track-s107-hypersphere-transformer/mlos_zone_b_h7b.json -- \
  env HF_HUB_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 "$VENV_PY" -I -B \
  track-s107-hypersphere-transformer/s107_train_eval.py \
  --track H7b --device cuda --amp-bf16 --seq-len 512 --steps 2000 --batch-size 8 \
  --seeds 42 137 2026 31415 27182 \
  --corpus-path "$LOCAL_CORPUS_PARQUET" \
  --out-json track-s107-hypersphere-transformer/h7b_gpu_results.json
```
