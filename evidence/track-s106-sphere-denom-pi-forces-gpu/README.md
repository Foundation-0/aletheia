# Track S106 GPU Empirical Evidence — Phase 1B, Phase 2 (`H1`–`H4`), & Phase 3 (`H5a`–`H6c`)

Self-contained empirical evidence bundle pairing two frozen bare-metal NVIDIA GeForce RTX 3080 Laptop (`8 GiB`) evaluation suites under locked preregistrations (`HF_HUB_OFFLINE=1`, `WEIGHTS=0`, Zone-B hardware telemetry receipts `clean_hardware_run=true`, `anomalies=[]`, `compute_vram_mib: 0 -> 0`):

- **Parent Preregistration (`H1`–`H4`):** [`PREREG_SPHERE_PI_FORCES_V1.md`](PREREG_SPHERE_PI_FORCES_V1.md) (`10,800` B, SHA-256 `ac3e62116bc4841320d2c713787c23568beed1ae738bf9b284b7f0c2a118d72a`) — shipped in this track directory and verified on disk by full 64-hex SHA-256 (`prereg_status="VERIFIED"` in both verifiers) and cross-checked against the run-time JSON artifacts *(committed to git in this PR after the GPU run windows)*.
- **Amendment 1 (`H5a`, `H5b`):** [`PREREG_SPHERE_PI_FORCES_AMENDMENT1_H5.md`](PREREG_SPHERE_PI_FORCES_AMENDMENT1_H5.md) (`3,658` B, SHA-256 `c83910a0e1a98e2afe473e5b15109fcbaf8e16bf85a08188b10fbdecfd75a05f`) — shipped in this track directory and verified on disk by full 64-hex SHA-256 (`amendment_status="VERIFIED"`).
- **Amendment 2 (`H6a`, `H6b`, `H6c`):** [`PREREG_SPHERE_PI_FORCES_AMENDMENT2_H6.md`](PREREG_SPHERE_PI_FORCES_AMENDMENT2_H6.md) (`4,794` B, SHA-256 `b676cc556c9bbfa0849c29c3326ebd13e8f43e9c65960ddb5eb508fdead21d85`) — shipped in this track directory and verified on disk by full 64-hex SHA-256 (`amendment_status="VERIFIED"`).
- **Held-Out Models (zero tuning; Phase 2 pilot locks strictly on synthetic Gaussian + `Qwen/Qwen2.5-0.5B` with strict UTC ordering before blind execution — Phase 2 is blind on the three held-out models):** `HuggingFaceTB/SmolLM2-360M`, `Qwen/Qwen2.5-1.5B`, `Qwen/Qwen2.5-3B`. **Phase 3 (H5/H6) is NOT blind on these three models** (H5b was motivated by Phase-2 Qwen3B layer-1–5 outliers); all Phase-3 verdicts on them are FALSIFIED and H6c uses micro-LMs.
- **Global Bit-Level Integrity (`191/191` full-model LLM arms + `4/4` matched-parameter `10,818,432`-param micro-LMs):** `0` syndrome errors, `0` out-of-ball groups, `0` non-block tensor diffs, exact bitrate accounting (`CS-08`), `WEIGHTS=0`.

---

## 1. Honest Literal Locked-Rule Scorecard (`H1`–`H6c`)

| Hypothesis | Phase | Literal Locked-Rule Verdict | Key Held-Out Measurement (Phase 2 blind; Phase 3 H5/H6 NOT blind on the held-out models) |
| :--- | :---: | :---: | :--- |
| **`H1`** (Static `SphereMap` vs per-128 `A_16` @ `3.0 bpw`) | Phase 2 | **`FALSIFIED`** | Loses end-to-end KL to per-128 `A_16` on `3/3` models (WikiKL `1.014`/`0.567`/`15.735` vs `0.437`/`0.311`/`0.518`); `H1-P2` Spearman $\rho \le 0.332 < 0.60$. |
| **`H2a`** (Denominator-$\pi$ `EQ(S^3)` vs `Num-pi` / k-means / `Cart-LM`) | Phase 2 | **`FALSIFIED`** | Kill gate fires (`2.0 bpw` KL loses to `Cart-LM + SphereMap` on `3/3`). Sub-claims that held: `+2.195..+2.206 dB` over Numerator-$\pi$ at `2.5 bpw`, `+0.027..+0.031 dB` over 20-iter k-means with `0` codebook bytes, and `1.355×` faster GPU decode than a **reference re-implementation** of `A_16` hampack bit-unpacking (not siliquant's kernel; `2.529` vs `1.866 Gw/s`). |
| **`H3a`** (Zero-bit `Power-0.7` radial warp) | Phase 2 | **`PARTIAL`** | Typical-layer SNR `+0.247..+0.248 dB` (`3/3` $\ge +0.15$) and KL $\ge 3\%$ @ $\ge 2\mathrm{SE}$ on `2/3` (`SmolLM2` `E_8` `-19.4%`/`-31.9%`, `Qwen1.5B` `A_16` `-14.8%`/`-10.8%`); misses heavy-layer `+0.40 dB` gate (`+0.27..+0.37 dB`). |
| **`H3b`** (EM / Hodge orthogonal splitting) | Phase 2 | **`FALSIFIED`** | No significant KL gain on `Qwen1.5B` or `Qwen3B`; improves only `SmolLM2` `A_16` (`-12.0%`/`-13.0%` per `s106_blind_gauntlet_results.json`: WikiKL `1.28918` vs `1.46433` = `-11.96%`, PyKL `2.06013` vs `2.36876` = `-13.03%`). |
| **`H3c`** (Yukawa screened $S^3$ centroids) | Phase 2 | **`FALSIFIED`** | Trails spherical k-means in KL on `SmolLM2` and `Qwen1.5B` (beats both k-means and Coulomb in SNR by $\ge +0.075\text{ dB}$ on `3/3`, KL win on `Qwen3B` only). |
| **`H4`** (Conjunction `SphereMap + A_16^8 + Hodge`) | Phase 2 | **`FALSIFIED`** | Beaten by `sp_E8_pow07_3b` and by per-128 `A_16` on `3/3` models. |
| **`H5a`** (Zero-extra-bit `Flow-SphereMap`) | Phase 3 | **`FALSIFIED`** | **Exact algebraic obstruction:** right-multiplying $W$ by any positive diagonal $D_{\text{flow}}$ before Sinkhorn L2 whitening is gauge-annihilated by Sinkhorn's column normalization step: $D_r^{-1}(W D_{\text{flow}})(D_c D_{\text{flow}})^{-1} \equiv D_r^{-1} W D_c^{-1}$ identically **for exact real-valued Sinkhorn; the shipped `ellipsoid_whiten_sinkhorn` is row-first, runs 8 iterations and quantizes scales to FP16, so invariance holds only up to FP16 scale rounding and finite-iteration Sinkhorn** (CPU control: `w_ell(W)` vs `w_ell(W·D)` differ by 0.04–0.29% relative). |
| **`H5b`** (Depth-time cone & matched-`bpw` schedule) | Phase 3 | **`FALSIFIED`** | Q1/Q4 causal amplification passes $\ge 2.0\times$ on `1/3` (`SmolLM2` `2.226×`). Matched-`bpw` (`2.9989` vs `2.9990`) `3.5/3.0/2.5` schedule wins decisively on `Qwen2.5-3B` (WikiKL `0.518 -> 0.433`, `-16.4%`; Python KL `0.716 -> 0.319`, `-55.4%`; reversed `Q1 @ 2.5b` explodes `10×` to `4.188/4.236`), failing `>= 2/3`. |
| **`H6a`** ($S^3$ Polar-curvature depth foliation, pilot `f=1/4`) | Phase 3 | **`FALSIFIED`** | Polar beats Equatorial on `3/3` (`0/3` Equatorial wins) with sharp scale emergence on `Qwen2.5-3B`: WikiKL `0.518 -> 0.368` (`-28.8%`, `8.8 SE`), Python KL `0.716 -> 0.280` (`-60.8%`, `18.6 SE` — `13.4×` better than Equatorial `4.397/4.314`); fails `>= 2/3` (`1/3`). |
| **`H6b_part1`** (Hopf-fiber `EQ(S^2) × S^1`, `32×8` split) | Phase 3 | **`FALSIFIED`** | Exact $U(1)$ fiber-phase equivariance verified at `1.000000 / 1.000000 / 0.999998` across `1.10B` 4-blocks, but factored directional SNR (`10.778 dB`) trails direct `EQ(S^3)` (`13.487 dB`) by `-2.708 dB`. |
| **`H6b_part2`** (Zero-cost `down_proj` flow channel order) | Phase 3 | **`FALSIFIED`** | Fails locked `>= 5%` over both native and random permutation on `>= 2/3` models at both `2.0` and `3.0 bpw`. |
| **`H6c`** (Native Hopf-fiber / quaternionic $SU(2)$-coupled $S^3$ residual micro-LM) | Phase 3 | **`CONFIRMED`** | **Confirmed on Criterion A (`NLL`/`BPB`) at exact `10,818,432`-param parity (`0` extra params, `800` steps × `16` × `256`, seeds `11, 12`):** BOTH Hopf seeds beat BOTH flat-residual seeds (**`2.6612` & `2.6197` vs `2.9348` & `3.0295` val BPB — mean `-0.342 BPB` / `-11.5%`**); post-3-bit-PTQ Hopf (`2.681`/`2.645 BPB`) still beats FP32 flat (`2.935`/`3.030 BPB`). **Honest caveats:** Criterion B (`>= 15%` lower PTQ KL) failed (`0.0135` vs `0.0063` nats) and un-fused PyTorch quaternion ops took `2.57×` wall-clock (`55.4 s` vs `21.6 s`). |

---

## 2. Exact Obstructions Isolated

1. **Static `SphereMap` Cross-Column Outlier Amplification (`Qwen/Qwen2.5-3B`, Layers 1–5)** — *console observations not serialized in the shipped JSONs (only the aggregate `kurtosis_summary` is)*: round-trip error is `3.57e-13` (no implementation bug), yet `model.layers.1.mlp.gate_proj.weight` exhibits `dc ∈ [1.19e-2, 4.43e+1]` (`3,722×` column spread, `dc_max = 44.3`). Static Sinkhorn divides column $j^*$ by `44.3`, mixes 64 columns through `H_64`, injects uniform whitened quantization noise, and rescales back by `44.3` (`1,962×` squared error amplification). Early-layer (`Layers 1–5`) outlier localization also explains why `H5b`/`H6a` `3.5 bpw` entry-layer allocation cuts `Qwen2.5-3B` Python KL by `55.4%`–`60.8%` while `2.5 bpw` on Layer 1 explodes `10×`.
2. **Sinkhorn Diagonal Gauge Annihilation (`H5a`):** Any column pre-weighting $W \mapsto W D_{\text{flow}}$ with positive diagonal $D_{\text{flow}}$ before Sinkhorn L2 whitening satisfies $D_r^{-1}(W D_{\text{flow}})(D_c D_{\text{flow}})^{-1} \equiv D_r^{-1} W D_c^{-1}$ for exact real-valued Sinkhorn (in the shipped FP16 implementation, up to FP16 scale rounding and finite-iteration Sinkhorn), proving mathematically why zero-extra-bit diagonal flow weighting before Sinkhorn cannot alter the whitened lattice representation.

---

## 3. Honest Scope & Novelty Classification (`N1`)

- **Novelty Classification:** **`N1`** (`n2_claims = 0`). Sinkhorn matrix scaling, Hadamard mixing, $E_8$/$A_{16}$ lattice quantization, equal-area $S^3$ partitioning, Hopf fibration coordinates, and quaternion neural residual updates build on established prior art (`N0`). This bundle contributes preregistered, anti-snooping-locked empirical measurements across `191` LLM arms and `4` matched-parameter micro-LMs, isolating exact failure obstructions and a pilot architectural confirmation (`H6c`) with full pure-stdlib verifiers and R5 test suites.

---

## 4. Layout & Quickstart (CPU-Only Pure-Stdlib Verification)

- `gpu_eval/` (`10` frozen files): Phase 1B pilot lock + Phase 2 (`H1`–`H4`) evaluator, JSON receipts, `mlos` Zone-B hardware receipts, `REPORT_GPU_EVAL.md`, `verify_s106_gpu_eval.py`, `test_s106_gpu_eval_r5.py`.
- `gpu_eval_phase3_h5_h6/` (`11` frozen files): Phase 3 Amendment 1 (`H5a`/`H5b`) + Amendment 2 (`H6a`/`H6b`/`H6c`) evaluators, locked protocols, JSON receipts, `mlos` Zone-B hardware receipts, `REPORT_PHASE3_H5_H6.md`, `verify_s106_phase3.py`, `test_s106_phase3_r5.py`.
- `test_s106_gpu_phase2_3_r5.py`: Top-level pure-stdlib R5 CI runner executing both child R5 suites and bundle hygiene checks across all three isolated Python modes.

| Top-Level File | Lines | Bytes | Mode | SHA-256 |
| :--- | ---: | ---: | :---: | :--- |
| `PREREG_SPHERE_PI_FORCES_V1.md` | `68` | `10,800` | `0o644` | `ac3e62116bc4841320d2c713787c23568beed1ae738bf9b284b7f0c2a118d72a` |
| `PREREG_SPHERE_PI_FORCES_AMENDMENT1_H5.md` | `20` | `3,658` | `0o644` | `c83910a0e1a98e2afe473e5b15109fcbaf8e16bf85a08188b10fbdecfd75a05f` |
| `PREREG_SPHERE_PI_FORCES_AMENDMENT2_H6.md` | `24` | `4,794` | `0o644` | `b676cc556c9bbfa0849c29c3326ebd13e8f43e9c65960ddb5eb508fdead21d85` |
| `test_s106_gpu_phase2_3_r5.py` | `75` | `3,285` | `0o644` | `b84ce99fcb8bd6d452f1b26223ad6a73a57fefe4462d57263406dee9f5ba9ef5` |

```bash
# Independent integrity & literal locked-rule verdict verification (Phase 2 + Phase 3)
PYTHONDONTWRITEBYTECODE=1 python3 -I -B gpu_eval/verify_s106_gpu_eval.py
PYTHONDONTWRITEBYTECODE=1 python3 -I -B gpu_eval_phase3_h5_h6/verify_s106_phase3.py

# Run complete R5 verification & adversarial suites across all three isolated Python modes
PYTHONDONTWRITEBYTECODE=1 python3 -I -B test_s106_gpu_phase2_3_r5.py
PYTHONDONTWRITEBYTECODE=1 python3 -I -O -B test_s106_gpu_phase2_3_r5.py
PYTHONDONTWRITEBYTECODE=1 python3 -I -B -W error test_s106_gpu_phase2_3_r5.py
```
