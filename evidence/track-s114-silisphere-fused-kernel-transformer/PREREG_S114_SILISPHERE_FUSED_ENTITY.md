# `PREREG-S114`: Bare-Metal `sm_86` Fused `SU(2)` Holonomy-Scan & Kernel-Isomorphic `SiliSphere` Transformer Entity (`EXP-Q18a..c`)

- **Document ID:** `PREREG-S114-SILISPHERE-FUSED-ENTITY-V1`
- **Status:** **IMMUTABLE PRE-RUN LOCK** (written & SHA-256-logged in `verification/AUDIT_LOG.md` strictly BEFORE any GPU execution or benchmark run)
- **Date (UTC):** `2026-11-25`
- **Owner:** `silicon-architect` (kernel foundry & verification), coordinated with `claude-architect` (`silisphere` unified repo architecture)
- **Target Hardware:** NVIDIA GeForce RTX 3080 Laptop GPU (`GA104M`, CC `8.6`, `48` SMs, `100 KiB` shmem/SM, `4 MiB` L2, `8 GiB` GDDR6, `110W` AC `P0`), serialized under `flock` + `mlos gpu-lease --mode train` + `mlos stamp-run --zone B --require-gpu`, `HF_HUB_OFFLINE=1`, `WEIGHTS=0`, `0` GitHub pushes without external-CLI sign-off.
- **Anchored Empirical Baselines (Immutable Prior Receipts):**
  - `Track S106` Phase 3 (`H6c`, `s106_h6_results.json` `5ab86f4b...`): Native Hopf-$S^3$ residual micro-LM (`-0.342 BPB` / `-11.5%` at exact `10,818,432` params, `2.57×` unfused eager slowdown).
  - `Track S107` (`H7b`, `h7b_gpu_results.json` `0775dd1c...`): `SU2-Holonomy-Scan-nGPT` eliminates `4×` (`T=2048`) extrapolation blowup (`2.7462 BPB`, `-7.37% z=-13.32` vs `RoPE-2D-nGPT` `2.9648`, `-8.13% z=-18.17` vs `Block4-RandOrtho`, `-15.38% z=-12.30` vs `RoPE-2D-Std`, `-4.93% z=-3.91` vs `LieRE-4D`), but runs **`3.913×` slower** (`276.55s` vs `70.68s`/run) in unfused eager PyTorch and stays near chance on `400`-step QK-only $S_3$/$A_5$ tracking (`22.01%/18.06%`, `4.23%/2.47%`).
  - `Track S107` (`H7c`, `h7c_gpu_results.json` `81f00fd4...`, `W10-OBS-31`): `O(d)` orthogonal per-pass Hopf clocking cuts `R=3` BPB `-9.44%` vs `NoClock` and `-12.53%` vs `Unlooped-16L`, but `unaliased_coprime` $\phi_5 = 10\pi/11 \approx \pi$ triggers an antipodal sign-flip at `R_test=6` (`8.07 BPB` / `21.1%` bracket acc). Fixed here by strictly acute non-antipodal Safe-Hopf angles $\phi_r = \frac{\pi (r + 1)}{2 R_{\max} + 1} \in (0, \pi/2)$ ($\cos \phi_r > 0$ unconditionally).
  - `Track S108` (`H8c` Part 2, `gpu_results_h8c/s108_gpu_full_results.json` `b65bec15...`): `Markov-MTP8` cuts multi-token patch BPB by `-19.34%` (`z=-63.31`) over `Parallel-MTP8`.

---

## 1. Architectural Principle & Honest Novelty Classification (`N1`)

- **Silicon-Geometry Isomorphism:** One unit quaternion $q = (w, x, y, z) \in SU(2) \cong S^3$ maps 1-to-1 onto one Ampere `sm_86` `float4` (`LDG.E.128` 128-bit single-transaction vector load, 4 FP32 registers). A 32-lane warp executes a 32-step right-accumulating non-Abelian prefix product $U(t) = \delta u_0 \otimes \delta u_1 \otimes \dots \otimes \delta u_t$ in 5 `__shfl_up_sync` warp shuffles with zero register spills, and its exact reverse-mode adjoint reduces algebraically to a 3-float Lie-algebraic $\mathfrak{su}(2)$ additive suffix sum:
  $$\bar{U}_t = S_t \otimes U_t, \qquad S_t = \sum_{s=t}^{T-1} \operatorname{Im}\!\left(g_s \otimes \overline{U_s}\right) \in \mathfrak{su}(2) \cong \mathbb{R}^3, \qquad \frac{\partial \mathcal{L}}{\partial \delta u_t} = \overline{U_{t-1}} \otimes (0, S_t) \otimes U_t.$$
  This collapses $\sim 60$ eager PyTorch kernel launches per layer (`ceil(log2 T)` scan passes + norms + Hamilton products) into a single warp-native forward kernel and a single warp-native backward kernel, fusing covariant $(Q, K, V)$ parallel transport and inverse un-transport $\overline{U_t} \otimes O_t$ in registers without HBM round-trips.
- **Novelty Classification (`N1`, `n2_claims = 0`):** Hillis–Steele warp-shuffle prefix scans, unit-quaternion Hamilton multiplication, nGPT hyperspherical SLERP, Lie-group parallel transport, and Markov multi-token prediction are established mathematical/systems primitives (`N0`). This track's contribution is their zero-spill `sm_86` PTX/Triton co-fusion, exact $\mathfrak{su}(2)$ additive-suffix-sum reverse-mode adjoint kernel, and preregistered equal-wall-clock (`CS-08`), `mJ/tok`, and $S_3/A_5$ empirical verification.

---

## 2. Locked Falsifiable Hypotheses & Literal Kill Gates

All seeds (`[42, 137, 2026]`), disjoint corpus splits (matching `Track S107` byte-level UTF-8 train/eval discipline), exact parameter/FLOP parity (`<= 0.5%` non-embedding parameter delta), and strict paired statistics (`mean ± SE`, paired `z`-score) are frozen prior to GPU execution.

### `H14a` (`EXP-Q18a`) — Bare-Metal `sm_86` CUDA/PTX + Triton Fused `SU(2)` Holonomy-Scan Parity, `0 B` Spill, & Wall-Clock Speedup
- **Claim:** Our bare-metal `sm_86` CUDA/PTX kernel (`su2_holonomy_scan_sm86.cu`) and Triton kernel (`su2_holonomy_triton.py`) match `s107_models.py::SU2PathOrderedHolonomy` forward and backward outputs within numerical tolerance, compile with `0 B` register/stack spills across every kernel, and collapse `H7b`'s `3.913×` eager slowdown down to near-parity with `RoPE-2D-nGPT`.
- **Locked Pass Criteria (ALL 4 required for `CONFIRMED`):**
  1. **Zero-Spill Compiler Gate:** `nvcc -O3 -std=c++17 -arch=sm_86 --ptxas-options=-v` reports `0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads` on 100% of kernel instantiations (`forward`, `backward`, `untransport_fwd/bwd`, `spherical_slerp_hopf_fwd/bwd`).
  2. **Exact Numerical Parity Gate:** Across `T ∈ {32, 256, 512, 1024, 2048}`, max absolute forward AND backward error vs FP64/FP32 exact reference is `<= 1e-4` (FP32) and `<= 5e-3` (BF16), with `0` NaNs/Infs and unit-norm drift `max | ||U||_2 - 1 | <= 1e-5`.
  3. **End-to-End Training Speedup Gate (RTX 3080, Zone B):** On the exact `H7b` `12L, d=320, B=8, T=512` training step benchmark (`bf16` autocast), fused `SU2-Holonomy-Scan-nGPT` achieves **`<= 1.15×` step wall-clock of `RoPE-2D-nGPT`** AND **`>= 3.40×` speedup over unfused eager `H7b`** (`3.913×` baseline).
  4. **Microbenchmark Kernel Throughput Gate:** Standalone fused `SU(2)` holonomy scan + $(Q,K,V)$ transport achieves `>= 5.0×` speedup over eager PyTorch `s107_models.py` at `T=512` and `T=2048`.
- **Literal Kill / Grading Rule:**
  - `CONFIRMED`: Criteria 1, 2, 3, and 4 ALL pass.
  - `PARTIAL`: Criteria 1 and 2 pass, AND speedup over eager `H7b` is `>= 2.0×`, but end-to-end ratio vs `RoPE-2D-nGPT` remains `> 1.15×` (e.g., if `w_omega` GEMM + SDPA overhead bounds total ratio to `1.16×–1.40×`).
  - `FALSIFIED`: Any spill `> 0 B`, parity violation, or `< 2.0×` speedup over eager `H7b`.

### `H14b` (`EXP-Q18b`) — Unified Kernel-Isomorphic `SiliSphere` Entity at Equal Wall-Clock (`CS-08`) & `mJ/tok`
- **Claim:** Co-fusing our verified spherical/holonomy primitives (`H6c` Native Hopf-$S^3$ + `H7b` fused `SU(2)` holonomy scan + `H7c` non-antipodal acute-cone Safe-Hopf loop + `H8c2` `Markov-MTP8` auxiliary head + fused `rsqrtf` spherical SLERP) into one warp-native `SiliSphere` entity beats both `RoPE-2D-Std` and `RoPE-2D-nGPT` at **equal wall-clock training time (`CS-08` budget = exact `RoPE-2D-nGPT` `600`-step wall-clock seconds)** AND equal non-embedding parameters (`±0.5%`), without increasing `mJ/tok` inference energy beyond `+15%`.
- **Arms (3 seeds `[42, 137, 2026]`, equal wall-clock budget `T_budget` locked on `RoPE-2D-nGPT` `600` steps):**
  1. `RoPE-2D-Std` (Pre-Norm baseline, `N0`)
  2. `RoPE-2D-nGPT` (Hyperspherical baseline, `N0`)
  3. `SiliSphere-Fused-Unlooped` (`H7b` fused `SU(2)` holonomy + fused spherical SLERP + optional `Markov-MTP8` head)
  4. `SiliSphere-Fused-Entity` (Full entity: fused `SU(2)` holonomy + fused spherical SLERP + non-antipodal Safe-Hopf loop + `Markov-MTP8`)
- **Locked Pass Criteria (`CONFIRMED` requires BOTH 1 and 2 + Energy Bound 3):**
  1. **Equal-Wall-Clock `T=2048` (`4×`) Extrapolation:** `SiliSphere-Fused-*` beats BOTH `RoPE-2D-Std` and `RoPE-2D-nGPT` by **`>= 5.0%` relative BPB (`z <= -2.0`)** at `T=2048`.
  2. **Equal-Wall-Clock `T=512` Non-Regression:** `SiliSphere-Fused-*` matches or beats `RoPE-2D-nGPT` at `T=512` (`<= +0.5%` BPB regression ceiling, or beats it by `z <= -2.0`).
  3. **Energy Efficiency (`mJ/tok` via `mlos` Zone B / NVML):** Inference `mJ/tok` of fused `SiliSphere` is `<= 1.15×` of `RoPE-2D-nGPT` at `T=512` and `T=2048`.
- **Literal Kill / Grading Rule:**
  - `CONFIRMED`: Criteria 1, 2, and 3 ALL pass on `>= 1` `SiliSphere-Fused-*` arm at equal wall-clock.
  - `PARTIAL`: Criterion 1 passes (`>= 5.0%`, `z <= -2.0` at `T=2048`), but Criterion 2 (`T=512` regresses `> +0.5%`) OR Criterion 3 (`mJ/tok > 1.15×`) fails.
  - `FALSIFIED`: Fails Criterion 1 at equal wall-clock.

### `H14c` (`EXP-Q18c`) — Full Covariant $(Q, K, V)$ Register-Fused $SU(2)$ Parallel Transport + Inverse Un-Transport $\overline{U_t} \otimes O_t$ on $S_3$/$A_5$ State Tracking
- **Claim:** In `Track S107 H7b`, $SU(2)$ transport was applied only to $(Q, K)$ (not $V$, and no inverse un-transport on attention output $O$), leaving $S_3$/$A_5$ group word-problem tracking at chance (`18.06%` / `2.47%` OOD). Applying the *same* in-register prefix holonomy $U_t$ covariantly to $(Q_t, K_t, V_t)$ AND un-transporting attention output $O^{\text{cov}}_t = \overline{U_t} \otimes O_t$ (so value $V_s$ arriving at query $t$ undergoes exact non-Abelian parallel transport $\overline{U_t} U_s V_s = (\delta u_{s+1} \cdots \delta u_t)^{-1} V_s$ at zero extra scan cost!) rescues non-Abelian group state tracking on $S_3$ and $A_5$.
- **Arms (3 seeds `[42, 137, 2026]`, matched params `±0.5%`, `6L, d=256`, `steps=1200` with curriculum `L ∈ [4..64]` train / `L ∈ [65..192]` OOD):**
  1. `RoPE-2D-nGPT` (Abelian control)
  2. `SU2-QK-Only-nGPT` (`H7b` ablation — transport on $Q, K$ only)
  3. `SU2-Covariant-QKV-nGPT` (Full covariant $Q, K, V$ transport + $\overline{U_t} O_t$ un-transport)
- **Locked Pass Criteria:**
  1. **$S_3$ OOD (`L=65..192`, chance `16.67%`):** `SU2-Covariant-QKV-nGPT` achieves **`>= 50.0%` OOD exact accuracy** AND beats BOTH `RoPE-2D-nGPT` and `SU2-QK-Only-nGPT` by **`>= +15.0` percentage points (`z >= 2.0`)**.
  2. **$A_5$ OOD (`L=65..192`, chance `1.67%`):** `SU2-Covariant-QKV-nGPT` achieves **`>= 15.0%` OOD exact accuracy** AND beats BOTH controls by **`>= +8.0` percentage points (`z >= 2.0`)**.
- **Literal Kill / Grading Rule:**
  - `CONFIRMED`: BOTH Criterion 1 ($S_3$) AND Criterion 2 ($A_5$) pass.
  - `PARTIAL`: Exactly ONE of Criterion 1 or Criterion 2 passes (e.g., $S_3$ solvable group breaks out cleanly while $A_5$ simple non-solvable group remains hard at `1200` steps).
  - `FALSIFIED`: Neither Criterion 1 nor Criterion 2 passes.

---

## 3. Anti-Snooping, Reproducibility, & Hygiene Guardrails

- **Zero GPU Touch in Phase 1:** Phase 1 builds, compiles (`nvcc -arch=sm_86 --ptxas-options=-v`), inspects SASS (`cuobjdump -sass`), and executes CPU-only parity + `gradcheck` preflight (`CUDA_VISIBLE_DEVICES=""`) strictly without acquiring the GPU lease.
- **Zone-B GPU Execution (Phase 2):** Runs ONLY after `PREREG-S114` SHA-256 is logged in `verification/AUDIT_LOG.md`, Phase-1 CPU preflight passes `3-mode -I`, and `mlos gpu-lease --mode train` is acquired cleanly with `mlos stamp-run --zone B --require-gpu`.
- **Artifact Discipline:** `WEIGHTS=0`, `0` bare `assert`s, `0` `/home/` or `~/` leaks, `0` CRLF, `0` `__pycache__`, `0` ELF/`.so` binaries committed to git repos, `aletheia audit-check --strict-ancestors --safety-scan PASS`.
