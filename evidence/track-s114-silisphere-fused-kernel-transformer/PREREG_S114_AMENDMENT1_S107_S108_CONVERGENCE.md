# `PREREG-S114-AMENDMENT1`: Deep `S107` & `S108` Convergence Probes Into `HoloSphere` (`H14d` & `H14e`)

- **Document ID:** `PREREG-S114-AMENDMENT1-S107-S108-CONVERGENCE-V1`
- **Status:** **IMMUTABLE PRE-RUN AMENDMENT LOCK** *(2026-11-25; parent `PREREG_S114_SILISPHERE_FUSED_ENTITY.md` SHA-256 `5fa927a06933c3cff057b65f75c1d2f190e10f1e420303d582dfb7c802ee69a4` remains 100% immutable and unmutated; logged in `verification/AUDIT_LOG.md` strictly BEFORE any GPU execution)*
- **Linked Queue Items:** `EXP-Q20d` (`H14d-1`, `H14d-2`) & `EXP-Q20e` (`H14e-1`, `H14e-2`)
- **Target Repository & Owned Harness Files:** `holosphere/` (`benchmarks/s114_s107_s108_convergence.py`, `tests/test_s114_convergence_r5.py`)
- **Hardware & Provenance Discipline (`CS-08` Strict Parity):** Single NVIDIA RTX 3080 (`8 GiB` VRAM), serialized under `flock` + `mlos gpu-lease --mode train` + `mlos stamp-run --zone B --require-gpu`, `HF_HUB_OFFLINE=1`, `WEIGHTS=0`, exact non-embedding parameter parity (`<= 0.5%`), identical disjoint offline multi-domain UTF-8 byte corpora (`WikiText-2-raw-v1` + local Python + JSON traces), exact raw UTF-8 BPB (`fp32` log-softmax, BOS excluded, EOS scored), `0` bare `assert`s, `n2_claims = 0`.
- **Anchored Empirical Baselines (Immutable Prior Receipts):**
  - `Track S107 H7a` (`h7a_gpu_results.json` `561572d9…`): `FALSIFIED` overall, but revealed **`W10-OBS-30`** — `S3-Equatorial-nGPT` attained the lowest raw BPB across all `10` arms (`2.4652 ± 0.0074`) and `2.3×` lower cross-seed SE (`0.0074` vs `Cyl-nGPT` `0.0170`), whereas Euclidean `S3-Equatorial-Std` degraded significantly (`+3.40%, z=+2.61`).
  - `Track S107 H7b` (`h7b_gpu_results.json` `0775dd1c…`): `SU2-Holonomy-Scan-nGPT` eliminated `4×` (`T=2048`) extrapolation blowup (`2.7462 BPB`, `-7.37% z=-13.32` vs `RoPE-2D-nGPT`, `-8.13% z=-18.17` vs `Block4-RandOrtho`, `-4.93% z=-3.91` vs `LieRE-4D`), with nominal `+1.22% (z=+1.28)` trail at `T=512`.
  - `Track S107 H7c` (`h7c_gpu_results.json` `81f00fd4…`): `CliffordTorus-HopfLoop` cut `R=3` BPB `-9.44% (z=-42.46)` vs `SphereLoop-NoClock` and `-12.53% (z=-14.44)` vs `Unlooped-16L`, but revealed **`W10-OBS-31`** — `unaliased_coprime` ($\phi_r = 2\pi r / 11$) hit $\phi_5 = 10\pi/11 \approx \pi$ ($\cos\phi_5 = -0.9595$) at `R_test = 6`, collapsing BPB to `8.07` and bracket-depth accuracy to `21.1%`.
  - `Track S108 H8b` (`W10-OBS-33`): Second-order discrete geodesic dynamic chunking collapsed to `avg_plen = 1.02` bytes/patch because raw byte embeddings on $S^{d-1}$ have nearly mutually orthogonal consecutive tangents ($c_t \approx 0.50$ everywhere).
  - `Track S108 H8c2` (`s108_gpu_full_results.json` `b65bec15…`): `Markov-MTP8` `CONFIRMED` (`-19.34%, z=-63.31` teacher-forced block BPB vs `Parallel-MTP8`; `-12.37%` unrolled exposure-bias reduction vs `LocalAR`).

---

## 1. `H14d` (`EXP-Q20d`) — Deep `Track S107` Convergence Into `HoloSphere`

### `H14d-1` — `W10-OBS-31` Antipodal Cure Proof Across `R_test ∈ {3, 4, 6, 8, 12}`
- **Stage-B Mathematical Mechanism:** Replace `unaliased_coprime` ($\phi_r = 2\pi r / 11$, crossing $\pi$ at $r=5$) with two provably non-antipodal acute-cone Safe-Hopf loop clocks:
  1. **`cayley_acute` (SFU-free pure-rational clock):** $t_r = t_{\max}\frac{r}{r + \tau}$ ($t_{\max} = 4/5 < 1, \tau = 2$), $(c_r, s_r) = \left(\frac{1 - t_r^2}{1 + t_r^2}, \frac{2 t_r}{1 + t_r^2}\right)$, requiring zero `cos`/`sin`/`tanh` SFU calls, satisfying $c_r^2 + s_r^2 \equiv 1$, and strictly guaranteeing $c_r > \frac{1 - t_{\max}^2}{1 + t_{\max}^2} = \frac{9}{41} \approx 0.2195 > 0$ for EVERY unseen pass $r \ge 0$.
  2. **`acute_cone` (smooth angle clock):** $\phi_r = \phi_{\max} \frac{r}{r + \tau}$ ($\phi_{\max} = 0.42\pi < \pi/2, \tau = 2$), strictly guaranteeing $\cos\phi_r > \cos(0.42\pi) \approx 0.2487 > 0$ for EVERY $r \ge 0$.
- **Arms (`5` arms × `3` seeds `[42, 137, 2026]`, `2` pre + `4` core × `R_train=3` + `2` suffix, `d=256, n_heads=8, d_ff=688`, `P_nonemb` parity `<= 0.5%`, pinned per-pass KV recompute, evaluated at `R_test ∈ {3, 4, 6, 8, 12}` on BOTH multi-domain val BPB and bracket-depth tracking):**
  1. `FlatLoop-Std` (unclocked Euclidean loop control, `N0`)
  2. `SphereLoop-NoClock` (unclocked spherical SLERP loop control)
  3. `Clifford-Coprime` (`unaliased_coprime` $\phi_r = 2\pi r / 11$ — `H7c` antipodal-collapse control)
  4. `SafeHopf-AcuteCone` (smooth acute-cone clock)
  5. `SafeHopf-CayleyAcute` (SFU-free rational Cayley acute clock)
- **Literal Pass / Kill Gates (`H14d-1`):**
  - **`CONFIRMED`:** `SafeHopf-CayleyAcute` (or `SafeHopf-AcuteCone`) simultaneously:
    1. Retains `R=3` BPB win: beats `SphereLoop-NoClock` by **`>= 5.0%` (`z <= -2.0`)** AND beats `FlatLoop-Std` by **`>= 2.0%` (`z <= -2.0`)**; AND
    2. Eliminates `R_test ∈ {6, 8, 12}` antipodal collapse: `max_{R ∈ {6,8,12}} BPB(SafeHopf) <= 0.65 × BPB(Clifford-Coprime at R=6)` AND `bracket_acc(R=6) >= 60.0%` (beating `Clifford-Coprime` by `>= +30 pp`, `z >= 2.0`).
  - **`PARTIAL`:** Passes Criterion 1 (`R=3` win) AND eliminates the `R=6` antipodal cliff vs `Clifford-Coprime` (`>= +30 pp` bracket / `<= 0.65×` BPB), but degrades below `FlatLoop-Std` at `R=12`.
  - **`FALSIFIED`:** Loses the `R=3` BPB gain (`< 2.0%` vs `FlatLoop-Std` or `< 5.0%` vs `NoClock`) OR still exhibits collapse at `R=6` (`bracket_acc < 45%` or `BPB > 5.0`).

### `H14d-2` — `W10-OBS-30` Hyperspherical Equatorial Foliation × Covariant `SU(2)` Holonomy
- **Stage-B Mathematical Mechanism:** On hyperspherical residuals (`hopf_s3` / `slerp`), entry/exit pole projections are norm-bounded (`||h|| = 1`), removing the Euclidean bottleneck that hurt `S3-Equatorial-Std` (`+3.40%`). Concentrating MLP capacity in the mid-depth equator ($w_{\mathrm{eq}}(\psi_\ell) = a(1 + \sin^2\psi_\ell)$, exact integer sum $\sum_\ell d_{\mathrm{ff}}(\ell) = L \cdot d_{\mathrm{ff}}$) where path-ordered $SU(2)$ holonomy representations accumulate tests whether equatorial tapering compounds with `SU(2)` holonomy to improve BOTH mean BPB and cross-seed variance.
- **Arms (`4` arms × **`5` seeds `[42, 137, 2026, 31415, 27182]`** for variance power, `L=12, d=320, n_heads=8, base_d_ff=864`, covariant `SU(2)` holonomy `transport_v=True`, `residual_mode="slerp"`, exact `0.0000%` param & FLOP parity across all `4` arms!):**
  1. `Cyl-SU2-Holonomy` (uniform cylinder control)
  2. `Eq-SU2-Holonomy` (`S3-Equatorial` width profile)
  3. `Pol-SU2-Holonomy` (`S3-Polar` width profile)
  4. `PermEq-SU2-Holonomy` (`S3-Permuted-Eq` exact-multiset adversarial null, $|\rho_S| \le 0.30$)
- **Literal Pass / Kill Gates (`H14d-2`):**
  - **`CONFIRMED`:** Across `5` seeds, `Eq-SU2-Holonomy` beats BOTH `Cyl-SU2-Holonomy` AND `PermEq-SU2-Holonomy` by **`>= 1.5%` relative BPB (`z <= -2.0`)** at `T=512` OR `T=2048` (`4×`), **OR** reduces cross-seed BPB variance by **`>= 2.0×`** (`Var(Cyl) / Var(Eq) >= 2.0` AND `Var(PermEq) / Var(Eq) >= 2.0`) with strictly lower mean BPB than BOTH controls.
  - **`FALSIFIED`:** Fails both BPB and variance gates against `Cyl-SU2` + `PermEq-SU2` (retiring equatorial tapering as a 3-seed fluctuation and locking uniform cylinder as HoloSphere default).

---

## 2. `H14e` (`EXP-Q20e`) — Deep `Track S108` Convergence Into `HoloSphere`

### `H14e-1` — Curing `W10-OBS-33` Raw-Byte Tangent Orthogonality via Holonomy-Smoothed Geodesic & Causal Portal-2 Two-Rate Reaction-Diffusion (`D=(1, 10)`) Chunking
- **Stage-B Mathematical Mechanism:** Raw UTF-8 byte embeddings on $S^{d-1}$ sit nearly mutually orthogonal, yielding flat turning score $c_t \approx 0.50$ everywhere (`avg_plen = 1.02` collapse in `S108 H8b`). We test a two-stage strictly causal geometric cure (`0` `acos`/`arccos` calls, `0.0` future-byte leakage):
  1. **Causal $SU(2)$ Holonomy-Transported Latent Trajectory:** Map input bytes through a lightweight causal byte encoder + 1-layer causal $SU(2)$ path-ordered holonomy transport $u_t = \operatorname{Norm}(L(U(t))\, h_{\mathrm{causal}}(t)) \in S^{d-1}$, placing consecutive token states into a smoothly varying parallel-transported tangent frame (`<v_t, P(v_{t-1})>` spreads away from `0` along coherent subwords/morphemes while spiking at semantic/syntactic transitions).
  2. **Causal Portal-2 Two-Rate Activator-Inhibitor Filter (`D = (1, 10)` vs `D = (5, 5)` Null):** Filter the smoothed 2nd-order turning signal $c_t = \frac{1 - \langle v_t, \mathcal{P}(v_{t-1})\rangle}{2}$ through a strictly causal two-timescale activator-inhibitor reaction-diffusion recurrence (`fast` local activator decay $D_u = 1$ vs `slow` broad lateral inhibitor $D_v = 10$), imposing refractory spacing aligned with Portal 2's Turing unstable band (`period ∈ [2.60, 3.45]`) — contrasted directly against an equal-diffusion `D = (5, 5)` null (`O2.1` symmetry-breaking obstruction).
- **Arms (`5` arms + `1` equal-diffusion null × `3` seeds `[42, 137, 2026]`, identical raw UTF-8 byte context `L_ctx = 512`, strict raw UTF-8 BPB, matched FLOPs/byte `±5%`):**
  1. `BPE-Std` (deterministic byte-level BPE baseline, `N0`)
  2. `Fixed-4B` (fixed `4`-byte uniform patching baseline)
  3. `HNet-1stOrder` (`H-Net` 1st-order cosine routing `N0` control on identical causal encoder)
  4. `Holonomy-Geodesic-2ndOrder` (holonomy-smoothed 2nd-order parallel-transport turning chunker, target `C* = 4.0`)
  5. `Holonomy-Turing-RD-D1_10` (holonomy-smoothed + causal two-rate activator-inhibitor `D=(1, 10)` chunker)
  6. `Holonomy-Turing-RD-D5_5-Null` (equal-diffusion `D=(5, 5)` ablation null testing `O2.1`)
- **Literal Pass / Kill Gates (`H14e-1`):**
  - **Mandatory Anti-Collapse Prerequisite:** `avg_plen ∈ [2.5, 6.0]` bytes/patch (curing `1.02` collapse), future-byte causality leak `< 1e-6`, and `0` `acos`/`arccos` calls.
  - **`CONFIRMED`:** `Holonomy-Geodesic-2ndOrder` OR `Holonomy-Turing-RD-D1_10` passes the anti-collapse prerequisite AND beats BOTH `Fixed-4B` AND `HNet-1stOrder` (`N0`) by **`>= 1.5%` raw UTF-8 BPB (`z <= -2.0`)** (and for `D=(1,10)`, strictly beats `D=(5,5)` null on boundary-period stability or BPB).
  - **`PARTIAL`:** Passes the anti-collapse prerequisite (`avg_plen ∈ [2.5, 6.0]`) AND beats `Fixed-4B` by `>= 1.5%` (`z <= -2.0`), but matches `HNet-1stOrder` (`N0`) or trails `BPE-Std`.
  - **`FALSIFIED`:** Collapses (`avg_plen < 1.8` or `> 8.0`) OR fails to beat `Fixed-4B`.

### `H14e-2` — `Markov-MTP8` Coupled Directly Onto `HoloSphereTransformer` (`T=512` & `T=2048` `4×`)
- **Stage-B Mathematical Mechanism:** Attach `Track S108`'s `CONFIRMED` low-rank coupled `MarkovMTP8Head` ($\mathcal{L} = \mathcal{L}_{\mathrm{primary}} + \lambda_{\mathrm{mtp}}\mathcal{L}_{\mathrm{mtp8}}$, $\lambda_{\mathrm{mtp}} = 0.2$) to `HoloSphereTransformer` (`pos_mode="su2_holonomy"`, `transport_v=True`, `residual_mode="hopf_s3"`), measuring primary `BPB` strictly from the exit chain-rule next-byte head (zero auxiliary contamination, per `COLLAB-INKLING2 B11`) and multi-token block BPB separately (both teacher-forced and unrolled) at `T=512` and `T=2048` (`4×`).
- **Arms (`4` arms × `3` seeds `[42, 137, 2026]`, `L=12, d=320, n_heads=8, base_d_ff=864`, matched non-embedding core params `±0.5%`):**
  1. `RoPE-nGPT-NoMTP` (standard hypersphere baseline without MTP, `N0`)
  2. `HoloSphere-SU2-NoMTP` (`SU(2)` covariant holonomy + `hopf_s3`, no MTP)
  3. `HoloSphere-SU2-ParallelMTP8` (`SU(2)` covariant holonomy + independent `ParallelMTP8Head` control)
  4. `HoloSphere-SU2-MarkovMTP8` (`SU(2)` covariant holonomy + coupled `MarkovMTP8Head`)
- **Literal Pass / Kill Gates (`H14e-2`):**
  - **`CONFIRMED`:** `HoloSphere-SU2-MarkovMTP8` satisfies ALL THREE:
    1. Beats `HoloSphere-SU2-ParallelMTP8` by **`>= 12.0%` (`z <= -2.0`)** on `MTP-8` block BPB at BOTH `T=512` AND `T=2048`;
    2. Shows zero primary-head regression vs `HoloSphere-SU2-NoMTP` at `T=512` (`<= +0.0%` delta, or beats `RoPE-nGPT-NoMTP`); AND
    3. Maintains **`>= 5.0%` (`z <= -2.0`)** primary `T=2048` (`4×`) BPB win over `RoPE-nGPT-NoMTP`.
  - **`PARTIAL`:** Satisfies Criteria 1 and 3, but primary `T=512` BPB regresses `> 0.5%` vs `HoloSphere-SU2-NoMTP`.
  - **`FALSIFIED`:** Fails Criterion 1 (`< 12.0%` MTP-8 win) OR loses the `T=2048` (`4×`) primary extrapolation win.

---

## 3. Honest Law-4 Classification & Pre-GPU Guardrails

- **Novelty Classification:** Strictly **`N1`** (`n2_claims = 0`) — every constituent primitive (Cayley rational rotation, $S^3$ width tapering, $SU(2)$ parallel transport, 2nd-order spherical turning, two-rate activator-inhibitor filtering, low-rank Markov MTP) builds on documented `N0` / prior verified `S107`/`S108` foundations.
- **Pre-GPU Gate:** All `4` probe harnesses MUST pass CPU-only 3-mode `-I` preflight (`tests/test_s114_convergence_r5.py` + `tests/run_all.py`, `CUDA_VISIBLE_DEVICES=""`, `0` bare `assert`s, `0` `/home/` leaks, `0` `acos`/`arccos` calls) before any RTX 3080 lease is requested.
