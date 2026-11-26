# `PREREG-S107` + `AMENDMENT1` (`EXP-Q08a..c`) — Live RTX 3080 Evaluation Report

- **Protocol Documents (in this directory):** `PREREG_S107_HYPERSPHERE_TRANSFORMER.md` (`6e197152372fb08a4f239d2132b990b0e61ce77db772951cb4e48931fb9289cd`) + `PREREG_S107_S108_AMENDMENT1.md` (`5a9ddf089adb378c339d6f0e85b40cab673e80e6161f0f6725aef52728483194`). *(Authoring copies were created locally before staging into this repository; see Provenance Disclosure below.)*
- **Preregistration Lock-Time Provenance Disclosure:** Both protocol files claim pre-run lock on `2026-11-25`, **however pre-run lock time cannot be independently verified from repository git history alone**. The earliest repository commit adding this track (`0da35e4c`, `2026-11-25 11:10:02 -0600` / `17:10:02 UTC`) post-dates all three RTX 3080 execution windows recorded in the `mlos` Zone-B receipts (`H7a`: `14:49:38–15:27:26 UTC` / `08:49–09:27 CT`; `H7c`: `15:28:10–15:52:30 UTC` / `09:28–09:52 CT`; `H7b`: `15:57:25–16:40:38 UTC` / `09:57–10:40 CT`), and the run JSON artifacts (`h7{a,b,c}_gpu_results.json`) do not embed preregistration SHA-256 digests.
- **Hardware & Provenance:** NVIDIA GeForce RTX 3080 Laptop GPU (`8 GiB` VRAM), serialized under `flock` + `mlos gpu-lease --mode train` + `mlos stamp-run --zone B --require-gpu`, `HF_HUB_OFFLINE=1`, `WEIGHTS=0` (zero weight checkpoints saved). All `3/3` `mlos` Zone-B receipts pass full cryptographic self-verification (`receipt_sha256` recomputed from canonical body), `exit_code = 0`, `clean_hardware_run = true`, `anomalies = []`, and clean GPU thermal/clock telemetry.
- **Offline Multi-Domain Corpus Digests & Reconstructibility (`corpus_manifest.json`, `8519c6c3...`):**
  - **Public WikiText-2-raw-v1 Parquets (`Salesforce/wikitext`, rev `b08601e04326c79dfdd32d625aee71d232d685c3`):** `validation-00000-of-00001.parquet` (`657,209` B, SHA-256 `204929b7ff9d6184953f867dedb860e40aa69c078fc1e54b3baaa8fb28511c4c`, extracted UTF-8 `1,146,708` B) and `test-00000-of-00001.parquet` (`732,610` B, SHA-256 `5f1bea067869d04849c0f975a2b29c4ff47d867f484f5010ea5e861eab246d91`, extracted UTF-8 `1,290,546` B — `76.4%` of `H7a` eval and `75.1%` of `H7b/H7c` eval).
  - **`H7a`:** Disjoint `2,568,794` B train (`43a81400291ee8fe50f3d88b226b9577e8d7284e7bc1b235498578a418b3aa6b`) vs strictly held-out `1,690,185` B domain sum (`1,690,187` B joined with `\n` separators, SHA-256 `ee88d7b3f67b5676563372b8dc8ce154e94dc7e2198247cf4f7d8515e1fba57b`: `wikitext2_test` `1,290,546` B + `python_code` `273,445` B + `json_traces` `126,194` B).
  - **`H7c` & `H7b`:** Disjoint `2,590,339` B train (`ea2f47fad9c28635bee8834989d9fd7958c2889d65334945b990067be81d3d70`) vs strictly held-out `1,719,483` B domain sum (`1,719,485` B joined, SHA-256 `10024fe40bd4d1b23aa5e69cf6ecbaafeaf399cf432e3b4e4875b9dce6641dff`: `wikitext2_test` `1,290,546` B + `python_code` `302,743` B + `json_traces` `126,194` B).
  - **Honest Non-Reconstructibility Disclosure:** Because the `python_code` and `json_traces` slices were globbed from a live local expedition workspace (`track-s*/*.py`, `track-s*/*.json`) outside this repository and concurrent tracks modified local files during `H7a` and after `H7b/H7c`, **the full `H7a` train stream and `H7b/H7c` train/eval streams cannot be reconstructed byte-for-byte from repository history alone** (`reconstructible_from_repo_alone = false` in `corpus_manifest.json`). Within each track, every arm and seed shared the exact bit-identical train/eval byte stream.
  - Scored by exact raw UTF-8 BPB (`fp32` log-softmax, BOS excluded, EOS scored).
- **Pre-Flight Parity Lock:** `s107_cpu_preflight.py` passes `9/9` gates bit-identically across `-I -B`, `-I -O -B`, and `-I -B -W error` (`payload_sha256 = fc493a4f4beaf24707052d099c5bef46109194e580428fd851622490662ed0c1`).

---

## 1. Master Scorecard — Literal Prereg vs. Graded Verdict (`111/111` Live RTX 3080 Runs, `n2_claims = 0`)

All paired statistics across the `3` locked seeds `[42, 137, 2026]` are **paired `t` statistics (`df = 2`)**. The table reports BOTH the **literal prereg verdict** (computed strictly from the locked `PREREG-S107` gate booleans) AND our **graded verdict** (accounting for post-hoc controls and failure modes).

| Track | Scope & Runs | Literal Prereg Verdict | Graded Verdict | Headline Quantitative Outcome (`3` Seeds `[42, 137, 2026]`, paired `t`, `df = 2`) |
| :--- | :--- | :---: | :---: | :--- |
| **`H7a`** (`EXP-Q08a`) | `10` arms × `3` seeds (`30` LM runs, `2,194s`) | **`FALSIFIED`** | **`FALSIFIED`** | `0/4` `BPB_PASS`, `0/4` `KL_PASS`. Neither `S3-Polar` nor `S3-Equatorial` beats BOTH `Cyl` AND matched `S3-Permuted` nulls at `>= 1.5%` BPB (`t <= -2`) or `>= 15%` 3-bit PTQ KL. `S3-Equatorial-Std` worsens BPB by `+3.40%` (`paired t = +2.61, df = 2`, two-sided `p = 0.12`, not significant at `α = 0.05`). |
| **`H7c`** (`EXP-Q08c`) | `6` arms × `3` seeds (`18` LM + `18` bracket runs, `1,371s`) | **`CONFIRMED`** *(OR-gate Criterion 1 fires)* | **`PARTIAL`** *(post-hoc downgrade)* | Literal `PREREG-S107:81` OR-gate Criterion 1 **FIRES** (`-5.29% t=-4.65` vs `FlatLoop-Std`, `-9.44% t=-42.46` vs `SphereLoop-NoClock`, `-12.53% t=-14.44` vs `Unlooped-16L` — note `Unlooped-16L` appears undertrained at `600` steps). Downgraded post-hoc to **`PARTIAL`** because added control `SphereLoop-RandRotClock` (Haar $O(d)$ per pass) matches/beats it (`2.6378` vs `2.6621`, `M1-H1` `2.20` vs `3.07`) proving **general orthogonal pass-symmetry breaking** rather than Hopf-specific superiority (Hopf's sole edge is `O(d)` `+0.0156%` FLOPs vs `O(d^2)` `+1.33%`), AND `R_test=6` & `M1-H1` fail (antipodal phase flip $\phi_5 = 10\pi/11 \approx \pi$). |
| **`H7b`** (`EXP-Q08b`) | `5` arms × `3` seeds (`15` LM + `30` $S_3$/$A_5$ runs, `2,522s`) | **`FALSIFIED`** *(fails `T=512` no-regression)* | **`PARTIAL`** *(mixed signal)* | Literal `PREREG-S107:52` is **`FALSIFIED`** because `SU2-Holonomy-Scan-nGPT` trails `RoPE-2D-nGPT` at `T=512` (`+1.22% t=+1.28`), failing the mandatory no-regression clause. Graded **`PARTIAL`** because on the identical paired `T=2048` tail slice (`2.7462 BPB`), `SU2` beats `RoPE-2D-nGPT` by **`-7.37% (t=-13.32)`**, `Block4-RandOrtho` by **`-8.13% (t=-18.17)`**, `RoPE-2D-Std` by **`-15.38% (t=-12.30)`**, and `LieRE-4D` (`N0`) by **`-4.93% (t=-3.91)`**; ties `T=1024` (`-0.03%`), shows `0` gain on `400`-step $S_3$/$A_5$ tracking (`~22.0%` / `4.23%`), and runs **`3.913×` slower** in eager PyTorch (`276.55s` vs `70.68s`). |

---

## 2. Explicit Preregistration Deviations

Three concrete deviations from `PREREG_S107_HYPERSPHERE_TRANSFORMER.md` and `PREREG_S107_S108_AMENDMENT1.md` occurred in the live GPU implementation and evaluation:

1. **`H7c` Hopf Clock Law ($\phi_r = 2\pi r / 11$ vs. prereg $\phi_r = 2\pi r / R$):** `PREREG_S107_HYPERSPHERE_TRANSFORMER.md:68` specified $\phi_r = 2\pi r / R$ (`pinned_train_step`, which aliases identically for $r \ge R_{\text{train}} = 3$). The live `H7c` GPU run instead used `clock_law = "unaliased_coprime"` ($\phi_r = 2\pi r / 11$, `gpu_harnesses/s107_models.py:106-107`) to avoid aliasing at $R_{\text{test}} > 3$; this choice directly produced the unseen antipodal rotation $\phi_5 = 10\pi/11 \approx \pi$ responsible for the `R_test = 6` collapse (`8.07 BPB`, `21.1%` bracket accuracy).
2. **Dropped Classical-Arabic (`S92`) Evaluation Domain:** `PREREG_S107_HYPERSPHERE_TRANSFORMER.md:5` listed classical Arabic `S92` treatises alongside Wikipedia prose, Python source code, and JSON traces. The live offline bundle (`gpu_harnesses/s107_train_eval.py:343-415`) evaluated only three domains (`wikitext2_test`, `python_code`, `json_traces`) and omitted classical Arabic.
3. **Added Post-Hoc `SphereLoop-RandRotClock` Control Arm (`H7c`):** Neither `PREREG_S107_HYPERSPHERE_TRANSFORMER.md` nor `PREREG_S107_S108_AMENDMENT1.md` listed `SphereLoop-RandRotClock`. It was added prior to GPU execution as an orthogonal per-pass symmetry-breaking control (frozen Haar-random $Q_r \in O(d)$ via QR with positive diagonal $R$, $\det = \pm 1$), and its parity with `CliffordTorus-HopfLoop` is the primary basis for downgrading `H7c` from literal `CONFIRMED` to graded `PARTIAL`.

---

## 3. Track `H7a` (`h7a_gpu_results.json`, `561572d9...`) — Literal: `FALSIFIED` / Graded: `FALSIFIED`

Pilot LR calibration (`COLLAB-CLAUDE A7`) locked `lr_std = 1.2e-3`, `lr_ngpt = 2.5e-3` (`steps = 800`, `seq = 512`, `batch = 8`, `P_nonemb = 14,876,480` `Std` / `14,900,737` `nGPT`, `0.1631%` param diff, `0.0000%` FLOP diff). All `t` values are paired `t (df = 2)`.

| Arm | Val BPB (`mean ± SE`) | `3`-bit PTQ KL (`nats`) | Paired vs `Cyl` (`BPB / KL`, `t`, `df=2`) | Paired vs Matching `Permuted` (`BPB / KL`, `t`, `df=2`) |
| :--- | :---: | :---: | :---: | :---: |
| `Cyl-Std` | `2.5336 ± 0.0465` | `0.016555 ± 0.000630` | ref | — |
| `S3-Polar-Std` | `2.5119 ± 0.0292` | `0.017068 ± 0.000390` | `-0.86% (t=-1.17)` / `+3.09%` | `-0.41% (t=-0.48)` / `-4.85% (t=-1.58)` |
| `S3-Equatorial-Std` | `2.6197 ± 0.0302` | `0.017178 ± 0.001222` | `+3.40% (t=+2.61)` / `+3.76%` | `+1.67% (t=+3.20)` / `+13.08%` |
| `S3-Permuted-Pol-Std` | `2.5223 ± 0.0154` | `0.017937 ± 0.000558` | null (Pol) | — |
| `S3-Permuted-Eq-Std` | `2.5766 ± 0.0428` | `0.015191 ± 0.000812` | null (Eq) | — |
| `Cyl-nGPT` (`N0`) | `2.4907 ± 0.0170` | `0.020201 ± 0.000815` | ref | — |
| `S3-Polar-nGPT` | `2.4862 ± 0.0283` | `0.018735 ± 0.001101` | `-0.18% (t=-0.36)` / `-7.25%` | `-0.23% (t=-0.35)` / `-4.87%` |
| `S3-Equatorial-nGPT` | `2.4652 ± 0.0074` | `0.019232 ± 0.001758` | `-1.02% (t=-1.53)` / `-4.80%` | `-0.57% (t=-1.08)` / `+4.01%` |
| `S3-Permuted-Pol-nGPT` | `2.4921 ± 0.0148` | `0.019695 ± 0.000531` | null (Pol) | — |
| `S3-Permuted-Eq-nGPT` | `2.4794 ± 0.0177` | `0.018491 ± 0.001009` | null (Eq) | — |

**Non-Gate Observations:** `nGPT` (`N0`) outperforms Pre-Norm `Std` across all `5` schedules (`-1.7%` to `-5.9%` BPB) at `~2.08×` wall-clock (`~96s` vs `~46s`/run) and slightly higher `3`-bit PTQ KL (`~0.019` vs `~0.017` nats). For `S3-Equatorial-Std` vs `Cyl-Std`, `+3.40%` has `paired t = +2.61` (`df = 2`, two-sided `p = 0.12`), which is not statistically significant at `α = 0.05`.

---

## 4. Track `H7c` (`h7c_gpu_results.json`, `81f00fd4...`) — Literal: `CONFIRMED` / Graded: `PARTIAL`

Pilot LR calibration locked `lr_std = lr_ngpt = 2.5e-3` (`2+4×3+2 = 16` eff. layers, `d=256, d_ff=688`, `steps=600`, checkpointed BPTT, `clock_law=unaliased_coprime` $\phi_r = 2\pi r / 11$).  
*Eval Slice Note:* Primary `Val BPB (R=3)` is evaluated over `64` held-out multi-domain windows (`val_chunks[:64]`), whereas `R_test` extrapolation BPB (`R3/R4/R6/R8`) is evaluated over the leading `16`-window slice (`val_chunks[:16]`, dominated by `json_traces` prefix bytes, which is why `R3` reads `3.12` vs `64`-window `2.66` identically across all arms). `SphereLoop-RandRotClock` uses frozen Haar-random orthogonal matrices $Q_r \in O(d)$ via QR with positive diagonal $R$ (`det = ±1`, orthogonal per-pass symmetry breaking without determinant restriction to $SO(d)$).

| Arm | `P_nonemb` | Val BPB (`R=3`, `64`w) | `R_test` BPB (`16`w: `R3/R4/R6/R8`) | Bracket Acc (`R3/R4/R6/R8`) | `M1-H1` `Δ3/Δ1` (`4b / 3b`, $\rho$) |
| :--- | ---: | :---: | :---: | :---: | :---: |
| `Unlooped-16L` *(undertrained caveat)* | `12,656,896` | `3.0435 ± 0.0185` | — | `80.38%` | — |
| `Unlooped-8L` | `6,328,576` | `2.9548 ± 0.0299` | — | `76.53%` | — |
| `FlatLoop-Std` | `6,328,577` | `2.8109 ± 0.0254` | `3.26 / 3.27 / 3.35 / 3.43` | `76.1 / 76.3 / 76.0 / 75.8%` | `3.58 / 3.57` ($\rho=1.26$) |
| `SphereLoop-NoClock` | `6,341,378` | `2.9397 ± 0.0040` | `3.42 / 3.49 / 3.97 / 4.65` | `84.6 / 79.7 / 66.7 / 57.8%` | `2.92 / 2.88` ($\rho=0.96$) |
| `SphereLoop-RandRotClock` *(added control)* | `6,341,378` | `2.6378 ± 0.0039` | `3.09 / 3.35 / 4.04 / 5.08` | `85.1 / 74.7 / 68.9 / 47.6%` | `2.20 / 2.25` ($\rho=1.01$) |
| `CliffordTorus-HopfLoop` | `6,341,378` | `2.6621 ± 0.0102` | `3.12 / 3.80 / 8.07 / 5.38` | `85.7 / 60.6 / 21.1 / 52.3%` | `3.07 / 3.10` ($\rho=1.67$) |

**Key Mechanisms, Undertraining Caveat & Graded `PARTIAL` Rationale (paired `t`, `df = 2`):**
1. Orthogonal per-pass clocking (`HopfLoop` `-9.44% t=-42.46`, `RandRotClock` `-10.27%` vs `NoClock`; `HopfLoop` `-5.29% t=-4.65` vs `FlatLoop-Std`) yields a strong `R=3` BPB gain over unclocked shared-core loops, firing literal `PREREG-S107:81` OR-gate Criterion 1 (`literal_prereg_verdict = CONFIRMED`).
2. **`Unlooped-16L` Undertraining Caveat:** `Unlooped-16L` (`12.66M` non-embedding params, `3.0435 ± 0.0185 BPB`) scores worst of all `6` `H7c` arms — worse even than `Unlooped-8L` (`2.9548 BPB`). With `2×` the non-embedding parameters under the same `600`-step budget and LR, `Unlooped-16L` appears undertrained at `600` steps; the `-12.53% (t=-14.44)` gap vs `Unlooped-16L` should NOT be read as looped models outperforming a converged `16`-layer upper bound.
3. **Post-Hoc Downgrade to `PARTIAL`:** `SphereLoop-RandRotClock` ($Q_r \in O(d)$) matches/slightly beats `CliffordTorus-HopfLoop` on both `R=3` BPB (`2.6378` vs `2.6621`, `+0.92% t=+1.86`) and `M1-H1` drift (`2.20` vs `3.07`) — demonstrating that the `R=3` gain comes from **general orthogonal pass-symmetry breaking** rather than Hopf-specific fiber geometry, with Hopf's sole advantage being **`O(d)` cost (`+0.0156%` FLOPs, `0` buffer) vs `O(d^2)` (`+1.33%` FLOPs)**.
4. Unseen pass `r=5` ($\phi_5 = 10\pi/11 \approx \pi$) antipodally flips `core_out`, causing `HopfLoop`'s sharp `R=6` dip (`8.07 BPB` / `21.1%` bracket acc) with partial rebound at `R=8` (`5.38 BPB` / `52.3%`), while `FlatLoop-Std` stays stable (`76.1% -> 75.8%`). All looped arms remain above `M1-H1` `2.0` (`2.20–3.58`), consistent with `Track S96 Thm 18`.

---

## 5. Track `H7b` (`h7b_gpu_results.json`, `0775dd1c...`) — Literal: `FALSIFIED` / Graded: `PARTIAL`

Pilot LR calibration locked `lr_std = 1.2e-3`, `lr_ngpt = 2.5e-3` (`L=12, d=320, steps=600, seq=512`, `0.1628%` max param diff, `0.8739%` max FLOP diff; dedicated `6L` $S_3$/$A_5$ group probes `steps=400`, train lengths `8..64`, OOD `65..192`).

| Arm | `P_nonemb` | `T=512` BPB (`64`w) | `T=1024` BPB (`16`w tail) | `T=2048` BPB (`16`w tail) | `3b` PTQ KL | $S_3$ ID / OOD (`16.7%` ch.) | $A_5$ ID / OOD (`1.7%` ch.) |
| :--- | ---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `RoPE-2D-Std` | `14,876,480` | `2.8485 ± 0.0359` | `3.4165` | `3.2453` | `0.01150` | `21.90% / 18.00%` | `4.44% / 2.50%` |
| `RoPE-2D-nGPT` | `14,900,737` | `2.7216 ± 0.0161` | `3.2623` | `2.9648` | `0.01223` | `22.22% / 17.93%` | `4.23% / 2.47%` |
| `LieRE-4D-Abelian-nGPT` (`N0`) | `14,906,497` | `2.7757 ± 0.0202` | `3.3191` | `2.8886` | `0.01129` | `21.96% / 17.99%` | `4.23% / 2.47%` |
| `Block4-RandOrtho-nGPT` | `14,900,737` | `2.7284 ± 0.0228` | `3.2823` | `2.9893` | `0.01276` | `22.22% / 17.92%` | `4.23% / 2.47%` |
| **`SU2-Holonomy-Scan-nGPT`** | **`14,898,817`** | **`2.7547 ± 0.0395`** | **`3.2614`** | **`2.7462`** | **`0.01728`** | **`22.01% / 18.06%`** | **`4.23% / 2.47%`** |

**Paired `SU2-Holonomy-Scan-nGPT` Comparisons (paired `t`, `df = 2`):**
- **Paired Arm-vs-Arm `T = 2048` Win (Same `16`-Window Tail Slice):** `-7.37% (t=-13.32)` vs `RoPE-2D-nGPT`, `-8.13% (t=-18.17)` vs `Block4-RandOrtho-nGPT`, `-15.38% (t=-12.30)` vs `RoPE-2D-Std`, and `-4.93% (t=-3.91)` vs `LieRE-4D-Abelian-nGPT`. **Cross-length comparability caveat:** `T=512` (`val_chunks[:64]`, `gpu_harnesses/s107_train_eval.py:519`) and `T=1024`/`T=2048` (`16` long windows scored on their final `512` bytes, `gpu_harnesses/s107_train_eval.py:543-552`) evaluate **different byte slices** and are **not directly comparable** (note `T=1024` reads `~3.26` vs `T=512` `~2.72` across all arms due to slice composition). Accordingly, we do NOT claim `SU2` matches its own `T=512` BPB at `T=2048`; only the **paired arm-vs-arm `T=2048` wins on the identical `16`-window slice** stand.
- **Literal `FALSIFIED` / Honest Failure Axes:** `PREREG-S107:52` requires no regression on standard `T=512` BPB; `SU2` trails `RoPE-2D-nGPT` by `+1.22% (t=+1.28)` at `T=512` (`literal_prereg_verdict = FALSIFIED`), ties at `T=1024` (`-0.03%`), shows `0` gain on `400`-step $S_3$/$A_5$ group tracking (all `5` arms near chance, showing QK-only non-Abelian transport alone does not unlock finite-group composition without value-path readout or longer curriculum), raises `3`-bit PTQ KL (`0.0173` vs `0.0122`), and runs **`3.913×` slower** (`276.55s` vs `70.68s`/run) in unfused eager PyTorch.

---

## 6. Artifact Provenance (Zero Weights, Clean Zone-B Receipts)

- `h7a_gpu_results.json`: `561572d9ace9df3cf76c1ba6e2a52b62809c6c9df2698fdd18e7904c5f4bede6` · `mlos_zone_b_h7a.json`: `f246750c415f2a30672f745928a2f3f84a56f4599d9b71f46f57ddf6d677948e` (`receipt_sha256 = b6165dfe34f3ca8861f5c94e6dca2c7d6654cd0e06dcdd241e3ea223fce0e6c4`)
- `h7c_gpu_results.json`: `81f00fd481a5c146b02568d1da3124cb0c60f77fe2b2f545940200c505a38bd9` · `mlos_zone_b_h7c.json`: `7ec656018d8458a530fa211aa32e83f9ec5b6928caa384192775d03f2bf7968b` (`receipt_sha256 = 1adafc333c06905cbe70a99e895a6c8220ba71477063d9fb50a306e440b0a694`)
- `h7b_gpu_results.json`: `0775dd1c4bf14311f84714f1681a0944fb9775fefe1d2e3c80c5d78f54e606d5` · `mlos_zone_b_h7b.json`: `a9aeecbf9b4e71dea5f188a236ec8974021d56099c259bb9519df94dfbeaa556` (`receipt_sha256 = 1b5d9ce8691288fe4b35e9bce63ac5ec17747ab3635a32c42c45a6c19b9c05af`)
- `corpus_manifest.json`: `8519c6c3e308285c91ca93b96996417e08f9600dd68ff17bac8f434464e9cc57`
