# Track S108 Live RTX 3080 Evaluation Report (`PREREG-S108` + `AMENDMENT1`: `H8a`, `H8b`, `H8c`)

- **Protocol Anchor:** `PREREG-S108` (`f0343be88c9f0702855b0631abcf68199bebae93b36e4690aa5ada7eab3628a8`) + `PREREG-S107-S108-AMENDMENT1` (`5a9ddf089adb378c339d6f0e85b40cab673e80e6161f0f6725aef52728483194`)
- **Date (UTC):** `2026-11-25` | **Owner:** `continuum-bridge`
- **Hardware & Provenance:** Live bare-metal NVIDIA GeForce RTX 3080 Laptop GPU (`8 GiB` VRAM), serialized via `flock` + `mlos gpu-lease --mode train` + `mlos stamp-run --zone B --require-gpu`, `HF_HUB_OFFLINE=1`, `PYTHONDONTWRITEBYTECODE=1`, `WEIGHTS=0`.
- **Zone-B Hardware Receipts (`3/3` `clean_hardware_run=true`, `anomalies=[]`):**
  - `H8a`: `mlos_zone_b_h8a_receipt.json` (`receipt_sha256=d5cd2703f3d21fcf38a344cf1030e2f297810077d9a2c8d30438867adda5439a`, `159.336 s`)
  - `H8b`: `mlos_zone_b_h8b_receipt.json` (`receipt_sha256=deff7ac71176175258109219e1c51c6c0c99ce60f7b7c868f58d751187ea4909`, `71.841 s`)
  - `H8c`: `mlos_zone_b_h8c_receipt.json` (`receipt_sha256=1cea02ffa9b8a10ab8e17e8481d9a4e20f553e2d1fa8edd815769dd08dec75aa`, `111.541 s`)
- **GPU Lease & Telemetry:** Pre-run `held=false` (`54 °C`, `2 MiB / 8192 MiB`); Post-run `held=false` (`68 °C`, `2 MiB / 8192 MiB`, `0%` util). Total live GPU time: `342.72 s` (`5m 43s`) across `51` full training runs + `3`-seed Part-3 benchmark (`seeds = [42, 137, 2026]`).

---

## 1. Executive Scorecard (Strict Kill-Gate Verdicts)

| Sub-Track | Core Question (`PREREG-S108` + `AMENDMENT1`) | Strict Verdict | Primary Quantitative Evidence (`3` Seeds `[42, 137, 2026]`, Paired SE) |
| :--- | :--- | :--- | :--- |
| **`H8a`** | Scale-gauge-proof unit-norm Hybrid Kronecker-Spherical `[A_r ⊗ B_p; A_r; B_p]` + `BlockStructuredProj` vs Flat BPE, Rank-1 Kron, RandPair null | **`FALSIFIED`** | Compresses embeddings **`28.98×`** (`1,572,864 -> 54,272`; `-14.85%` total params, `+0.00%` FLOPs), but loses to `flat_bpe` by **`+8.55%` (`z=+30.43`)** on `arabic+abios` (`2.6878` vs `2.4762` BPB) and **`+5.28%` (`z=+35.04`)** on `english+python` (`2.7968` vs `2.6565`); `hybrid_kron_sphere_reinvest` (`L=7`, `-3.31%` params, `+14.00%` FLOPs) still trails (`2.7092`); indistinguishable from `rank1_kron` (`2.6794`, `z=+0.65`) and `randpair` (`2.6819`, `z=+1.07`). |
| **`H8b`** | Zero-`arccos` 2nd-order parallel-transport geodesic turning vs `H-Net` cosine (`N0`), `BLT-Entropy`, `Fixed-4B`, `BPE-Std` on identical `512 B` UTF-8 windows | **`FALSIFIED`** | Measured **`avg_plen = 1.020`** (`4.9569` BPB — boundary collapse explained geometrically by near-orthogonal adjacent byte tangents on $S^{95}$, where $c_t \approx 0.50$, not separately logged): loses by **`+11.18%` (`z=+6.17`)** vs `hnet_cosine` (`4.4584`), **`+14.10%` (`z=+9.81`)** vs `fixed_byte4` (`4.3443`), **`+17.40%` (`z=+16.16`)** vs `blt_entropy` (`4.2223`), **`+87.85%` (`z=+40.59`)** vs `bpe_std` (`2.6388`). |
| **`H8c` Part 1** | Exact-budget adaptive loop pacing (`r_bar = 2.0`, `SafeHopfLoopCore`) vs uniform `r = 2` and random `r_bar = 2.0` | **`FALSIFIED`** | Exact `sum(r) == 2N` and contractive `SafeHopfLoopCore` (`rho = 0.88–0.97`) hold cleanly, but `adaptive` (`3.6329` BPB) is indistinguishable from `uniform` (`3.6338`, `-0.026%`, `z=-0.18`) and `random` (`3.6309`, `+0.054%`, `z=+0.54`). |
| **`H8c` Part 2** | Intra-patch coupling obstruction: `Markov-MTP8` vs independent `Parallel-MTP8` vs non-strawman `LocalAR` byte decoder | **`FALSIFIED`** *(preregistered gate; TF-coupling leg exploratory N0)* | Under PREREG:89 as written: no BPE arm was run at equal total params, head params are `1.61M–1.91M` (spread `18.3%`) vs the preregistered matched `~15M ± 0.5%` budget, and primary loop-exit BPB improves only `-1.66%` (`3.6316` vs `3.6930`, under the `≥ 5%` bar). The TF `MTP-8` coupling leg (`3.7008` vs `4.5879`, `-19.34%`, `z=-63.31`) and unrolled `-12.37%` (`5.2840` vs `6.0296`) survive only as post-hoc exploratory N0; `local_ar` leads TF (`3.6088`, `+2.55%`). |
| **`H8c` Part 3** | Unconfounded `nullmodem` Block-8 `E_8` `RAM==WIRE==HASH` cell bus vs `English JSON`, `ABIOS/3`, `Direct-Binary` at equal wire bits + frozen judge | **`FALSIFIED`** *(preregistered total-wire gate; payload-only result exploratory N0)* | `100.0%` SHA-256 verified; **`99.74%`** field / **`98.96%`** exact / **`99.87%`** edit acc in **`32` payload bits** — but under `AMENDMENT1 §6` total-wire accounting (payload + framing + hash) single-message wire is **`352` bits `> 144`** (`ABIOS/3`, acc `1.0`), so the preregistered verdict is FALSIFIED and the `≥ 4`-state batching fix is an untested design change; the prereg's required `0.4272` gauge-gap reduction was never measured. |

---

## 2. Locked File-Disjoint 4-Domain Corpus (`262,144 B` Train / `87,381 B` Held-Out Eval Per Domain)

Every train/eval split is strictly file-disjoint, valid UTF-8, zero synthetic repetition, and `100%` lossless under `FastByteLevelBPE` (`V = 4,096`, `decode(encode(window)) == window` verified on every evaluation window):

| Domain Key | Source Composition (Strictly File-Disjoint Train vs Eval) | Train Bytes | Eval Bytes | BPE-4096 Bytes/Tok | Split SHA-256 Prefix |
| :--- | :--- | ---: | ---: | ---: | :--- |
| `english` | WikiText-2 validation (train) vs WikiText-2 test (eval) | 262,144 | 87,381 | 3.012 | `c7767b125fd4` |
| `python` | Disjoint Python 3.12 stdlib modules (`ast/fractions/decimal/inspect/difflib` vs `json/argparse/unittest`) — note: the GPU harness ran under **CPython 3.12.x** (digest-proven: this split rebuilds byte-exact on 3.12.10/11/12, not on 3.14.8; 3.14.8 is the mlos receipt interpreter); `corpus_manifest.json` carries the full per-domain manifest and recipes | 262,144 | 87,381 | 3.294 | `eb47ed59b433` |
| `arabic` | Multi-byte UTF-8 Unicode/Arabic/Lean formal corpus (`bayt-al-hikma` reports/JSON + `68` `.lean` files, `i % 4 == 3` held out) | 262,144 | 87,381 | 2.238 | `6d5afa8819f4` |
| `abios_calculus` | `ABIOS/3` specs, schemas, and `SYM-2P` JSONL agent traces (`104` files: `78` train / `26` eval, `i % 4 == 3` held out) | 262,144 | 87,381 | 3.076 | `2773d7b08fba` |

*Transparency note:* The `arabic` domain evaluates a real non-repeating multi-byte UTF-8 Unicode/Lean/Arabic formal corpus (`bayt-al-hikma` markdown/JSON + Lean sources — **not** the prereg's `S92` Classical Arabic, an out-of-band substitution), with `2.238` bytes/tok fertility reproducing elevated UTF-8 token fragmentation of non-ASCII scripts, rather than standalone classical OpenITI treatises (not cached on this workstation). The `english`, `arabic`, and `abios_calculus` split digests (`c7767b125fd4`, `6d5afa8819f4`, `2773d7b08fba`) are lab-recorded values that do not independently re-derive on the audit workstation (HF caches absent); only the `python` domain digest rebuilds byte-exact. In `gpu-full` mode the harness now **fails closed** (`CORPUS_SOURCE_MISSING`) instead of falling back to synthetic bytes when a domain cache is absent.

---

## 3. Detailed Results & Mechanistic Analysis

### 3.1 Track `H8a`: Hybrid Kronecker-Spherical Embeddings (`gpu_results_h8a/s108_gpu_full_results.json`, `result_sha256=704f2bef…`)

Config: `V=4,096` (`64 × 64` injective morph-structural factorization), `d_a=d_b=16`, `d_model=384`, `n_heads=6`, `L=6` (`L=7` for iso-param `hybrid_kron_sphere_reinvest`), `batch_size=16`, `seq_tok=256`, `400` steps (`bf16` autocast, cosine LR with 10% warmup), evaluated in `fp32` on `32 × 512 B` held-out UTF-8 windows per domain.

| Arm | `P_total` (`Δ%`) | `P_embed` | `FLOPs/Tok` (`Δ%`) | English BPB | Python BPB | Unicode/Ar BPB | ABIOS BPB | Ar+ABIOS BPB | En+Py BPB | Mean BPB |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `flat_bpe` | 10,228,608 (`+0.00%`) | 1,572,864 | 19,660,800 (`+0.00%`) | 2.7927 | 2.5202 | 2.4312 | 2.5212 | **2.4762** | **2.6565** | **2.5663** |
| `flat_bpe_sphere` | 10,228,608 (`+0.00%`) | 1,572,864 | 19,660,800 (`+0.00%`) | 2.7937 | 2.5272 | 2.4342 | 2.5169 | 2.4756 | 2.6605 | 2.5680 |
| `rank1_kron` | 8,756,096 (`-14.40%`) | 100,352 | 19,660,800 (`+0.00%`) | 2.9464 | 2.6349 | 2.6324 | 2.7263 | 2.6794 | 2.7906 | 2.7350 |
| `hybrid_kron_randpair` | 8,710,016 (`-14.85%`) | 54,272 | 19,660,800 (`+0.00%`) | 2.9561 | 2.6395 | 2.6281 | 2.7357 | 2.6819 | 2.7978 | 2.7398 |
| `hybrid_kron_sphere` | 8,710,016 (`-14.85%`) | 54,272 | 19,660,800 (`+0.00%`) | 2.9486 | 2.6449 | 2.6414 | 2.7343 | 2.6878 | 2.7968 | 2.7423 |
| `hybrid_kron_sphere_reinvest` (`L=7`) | 9,890,432 (`-3.31%`) | 54,272 | 22,413,312 (`+14.00%`) | 2.9582 | 2.6469 | 2.6633 | 2.7550 | 2.7092 | 2.8026 | 2.7559 |

- **Param/FLOP Budget Disclosure:** `hybrid_kron_sphere` and `hybrid_kron_randpair` match `flat_bpe` transformer FLOPs identically (`19,660,800`, `+0.00%`) while carrying `-14.85%` fewer total parameters (`8,710,016` vs `10,228,608`, `28.98×` embedding compression); `rank1_kron` carries `-14.40%` fewer parameters (`8,756,096`, `+0.00%` FLOPs). To test whether reinvesting the saved embedding parameters into depth recovers the gap, `hybrid_kron_sphere_reinvest` adds a 7th transformer layer (`L=7`: `9,890,432` params, `-3.31%`, and `22,413,312` FLOPs/tok, **`+14.00%`** FLOP advantage over `flat_bpe`) — yet it still trailed `flat_bpe` (`2.7092` vs `2.4762` on `ar+abios`), preserving the strict `FALSIFIED` verdict.
- **Paired-seed deltas (`hybrid_kron_sphere` vs controls):**
  - vs `flat_bpe` (`ar+abios`): **`+0.2116` BPB (`+8.55%`, `SE=0.0070`, `z=+30.43`)** — FAIL.
  - vs `flat_bpe` (`en+py`): **`+0.1403` BPB (`+5.28%`, `SE=0.0040`, `z=+35.04`)** — FAIL.
  - vs `rank1_kron` (`ar+abios`): `+0.0085` BPB (`+0.32%`, `z=+0.65`) — no empirical advantage over rank-1 at `V=4,096`.
  - vs `hybrid_kron_randpair` (`ar+abios`): `+0.0059` BPB (`+0.22%`, `z=+1.07`) — byte-hash morph factoring did not beat random bijective pairs.
- **Finding (`FALSIFIED`):** The `AMENDMENT1 §4` unit-normalized block-weighted repair genuinely eliminates scale-gauge collapse (`s108_cpu_preflight.py` Gate 2) and compresses the input table `28.98×` (`1,572,864 -> 54,272`), **but** compressing input embeddings under an untied `4,096`-way flat `lm_head` imposes a clear `+5.28%` to `+8.55%` BPB penalty that adding `+1` transformer layer (`+14.00%` FLOPs) did not recover in `400` steps. Furthermore, `flat_bpe_sphere` (`2.5680`) matches `flat_bpe` (`2.5663`), confirming `C_row(E)=1` is not hybrid-exclusive.

### 3.2 Track `H8b`: 2nd-Order Geodesic Curvature vs `H-Net` Cosine (`N0`) & `BLT-Entropy` (`gpu_results_h8b/s108_gpu_full_results.json`, `result_sha256=b397ebda…`)

Config: Identical `512`-byte raw UTF-8 windows across ALL `5` arms (`d_model=256, L=4, n_heads=4, d_b=96, batch_size=16, 400 steps`), zero `arccos` calls anywhere in the graph, strict causality verified (`<1e-5` streaming-vs-TF BPB).

| Arm | `P_total` | Avg Patch/Tok Len (B) | English BPB | Python BPB | Unicode/Ar BPB | ABIOS BPB | Mean BPB | Ar−En Gap |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `bpe_std` | 4,196,608 | 2.974 | 2.8386 | 2.5796 | 2.5553 | 2.5816 | **2.6388** | -0.2833 |
| `blt_entropy` (`N0`) | 2,242,674 | 1.302 | 4.0838 | 4.0276 | 4.4273 | 4.3505 | **4.2223** | +0.3435 |
| `fixed_byte4` | 2,217,602 | 4.000 | 4.2272 | 4.0100 | 4.7120 | 4.4281 | 4.3443 | +0.4848 |
| `hnet_cosine` (`N0`) | 2,217,602 | 3.250 | 4.2689 | 4.1067 | 4.9774 | 4.4805 | 4.4584 | +0.7085 |
| `spherepatch_geodesic2` | 2,217,602 | **1.020** | 4.6223 | 4.5212 | 5.8677 | 4.8164 | 4.9569 | +1.2454 |

- **Paired-seed deltas (`spherepatch_geodesic2` vs controls):**
  - vs `hnet_cosine` (`N0`): **`+0.4985` BPB (`+11.18%`, `z=+6.17`)**
  - vs `fixed_byte4`: **`+0.6126` BPB (`+14.10%`, `z=+9.81`)**
  - vs `blt_entropy`: **`+0.7346` BPB (`+17.40%`, `z=+16.16`)**
  - vs `bpe_std`: **`+2.3181` BPB (`+87.85%`, `z=+40.59`)**
- **Exact Mechanistic Root Cause (`FALSIFIED`):** The directly measured collapse metric is **`avg_plen = 1.020`** (`98%` single-byte boundary emission, starving the causal patch transformer of multi-byte pooling). As a geometric mechanism explanation (note: mean $c_t$ is not separately logged as a JSON scalar), in high-dimensional unit byte embedding space ($S^{95}$), consecutive byte trajectories do NOT trace smooth 1D great circles — adjacent unit tangents $v_t, \mathcal{P}(v_{t-1})$ are nearly orthogonal ($\langle v_t, \mathcal{P}(v_{t-1})\rangle \approx 0 \implies c_t \approx 0.50$ at almost every byte). By contrast, `blt_entropy` (`4.2223`) outperformed both `fixed_byte4` (`4.3443`) and `hnet_cosine` (`4.4584`), confirming `COLLAB-GROK47`'s analysis that predictive Shannon entropy is a genuinely distinct signal from local geometric step/turning angles.
- **Strict Causality Note (`BLTAuxEntropyRouter`):** In `DynamicBytePatchLM`, `BLTAuxEntropyRouter` receives the already right-shifted byte sequence (`shifted`), introducing an intentional 1-step lag so boundary decision $b_t$ depends strictly on prior bytes $x_{<t}$ with zero future leakage (verified `<1e-5` streaming-vs-TF parity in `s108_cpu_preflight.py` `test_05`).
- **Portal-2 Turing Boundary-Nucleation Diagnostic:** Independently verified on `P_32` (`J=[[7,15],[-21/2,-10]]`): differential coupling `D = diag(1, 10)` nucleates cleanly (`growth_ratio = 1.3318`, `num_peaks = 10`, **`mean_boundary_period = 3.2222`**, squarely inside the exact Portal-2 theoretical band `[2.60, 3.45]`), whereas equal diffusion `D = diag(5, 5)` decays identically (`growth_ratio = 0.0`, `nucleated = False`, `num_peaks = 0`, and `mean_boundary_period = 32.0`, the `seq_len` sentinel emitted whenever `< 2` peaks exist).

### 3.3 Track `H8c`: Adaptive Loop Pacing, Markov `MTP-8` vs `LocalAR`, & `nullmodem` Block-8 `E_8` Bus (`gpu_results_h8c/s108_gpu_full_results.json`, `result_sha256=3e60b8f4…`)

#### Part 1 — Exact-Budget Adaptive Loop Pacing (`SafeHopfLoopCore`, `d_model=256`, `350` steps × `B=16`)

| Pacing Mode | Exact Mean `r` | Depth Histogram (Seed 42, `4,096` patches) | Empirical Contraction `rho` | Mean Primary BPB (`3` seeds) | Paired Delta vs Control |
| :--- | ---: | :--- | ---: | ---: | :--- |
| `adaptive` | **2.0000** | `{1: 679, 2: 2741, 3: 673, 4: 3}` | 0.8765–0.9601 | 3.6329 | vs `uniform`: `-0.026%` (`z=-0.18`) |
| `uniform` | **2.0000** | `{1: 0, 2: 4096, 3: 0, 4: 0}` | 0.9460–0.9737 | 3.6338 | baseline |
| `random` | **2.0000** | `{1: 1870, 2: 1028, 3: 526, 4: 672}` | 0.9022–0.9218 | 3.6309 | `adaptive - random`: `+0.054%` (`z=+0.54`) |

- **Verdict (`FALSIFIED`):** Exact per-batch `CS-08` FLOP parity (`sum r == 2N`), non-collapsed routing diversity, and `SafeHopfLoopCore` contraction (`rho < 1`, zero NaN) all held cleanly, but adaptive pacing produced zero BPB improvement over uniform or random pacing at this scale.

#### Part 2 — Intra-Patch Coupling: `Markov-MTP8` vs `Parallel-MTP8` vs `LocalAR`

| Head Architecture | `P_total` | Primary Loop-Exit BPB | Aux `MTP-8` TF BPB | Aux `MTP-8` Unrolled BPB | Exposure-Bias Drift (`Un - TF`) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `local_ar` (out-of-band `COLLAB-CLAUDE B6` anchor — not a preregistered arm) | 1,610,119 | **3.6047** | **3.6088** | 6.0296 | +2.4208 |
| `markov_mtp8` (low-rank Markov) | 1,756,423 | 3.6316 | 3.7008 | 5.2840 | +1.5832 |
| `parallel_mtp8` (independent) | 1,905,415 | 3.6930 | 4.5879 | **4.5879** | **0.0000** |

- **Paired-seed deltas:**
  - `markov_mtp8` vs `parallel_mtp8` (TF `MTP-8` BPB): **`-0.8871` BPB (`-19.34%`, `SE=0.0140`, `t=-63.31`)** — post-hoc exploratory N0 only; the preregistered Part-2 gate (equal-total-param BPE comparison + `≥ 5%` multi-domain BPB) is **FALSIFIED** (see Deviation Register).
  - `markov_mtp8` vs `local_ar` (TF `MTP-8` BPB): `+0.0920` BPB (`+2.55%`, `z=+6.21`) — `local_ar` wins teacher-forced NLL at fewer params, whereas `markov_mtp8` cuts unrolled exposure-bias BPB by **`-12.37%`** (`5.2840` vs `6.0296`).
- **Control Scope Disclosure:** `H8c` Part 2 isolates intra-patch byte-head coupling (`local_ar`, `markov_mtp8`, `parallel_mtp8`) on identical byte-patch loop latents; there is no separate BPE arm inside `H8c` Part 2 (`BPE-4096` anchors live in `H8a` and `H8b`), so the prereg's equal-total-param BPE comparison was never executed for this track.
- **Statistics note:** all deltas use paired seeds `n = 3` (`42, 137, 2026`); the reported `z` values are therefore paired-`t` statistics with `df = 2` (a `z` label would assume known variance — with `n = 3` the `t_{0.975,2} = 4.303` critical value applies, and every `|t| > 4.303` reported here remains significant, but `z`-style `±1.96` thresholds would overstate significance).

#### Part 3 — Unconfounded `nullmodem` Block-8 `E_8` `RAM==WIRE==HASH` Cell Bus (`12`-Bit Structured State, `1,024` Samples, `3` Seeds)

| Wire Arm | Payload Bits | Framing + SHA-256 Bits | Total Wire Bits | Hash Verified | Frozen-Judge Field Acc | Frozen-Judge Exact Acc | Counterfactual Edit Acc |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `direct_binary_oracle` (floor) | 16 | 0 | 16.0 | n/a | 1.0000 | 1.0000 | 1.0000 |
| `abios_3` (unauthenticated symbolic) | 144 | 0 | 144.0 | n/a | 1.0000 | 1.0000 | 1.0000 |
| `english_json` (unauthenticated text) | 344 | 0 | 344.0 | n/a | 1.0000 | 1.0000 | 1.0000 |
| **`nullmodem_sphere_cell` (`4×E_8`)** | **32** | **320** | **352.0** | **1.0000** | **0.9974** | **0.9896** | **0.9987** |

- **Verdict (`FALSIFIED` under the preregistered gate):** Block-8 `E_8` sphere quantization recovers **`99.74%`** per-field accuracy, **`98.96%`** exact 4-field accuracy, and **`99.87%`** counterfactual latent-edit fidelity in just **`32` payload bits** (`4.5×` smaller payload than `ABIOS/3`, `10.75×` smaller than `English JSON`, `100%` SHA-256 verified) — a genuine post-hoc N0 result. However, under `AMENDMENT1 §6`'s mandatory total-wire accounting (`wire_bits` = framing + hash + quantized payload), the standalone `320`-bit header+SHA-256 wrapper pushes single-message wire to **`352` bits `> 144`** (`ABIOS/3`, acc `1.0`), so `ABIOS/3` dominates on total wire and the preregistered Part-3 verdict is **FALSIFIED**. The proposed `>= 4`-state batching amortization is an untested design change, and the prereg's required `0.4272` gauge-gap measurement was never taken.

---

## 3.4 Preregistration Deviation Register (audit-facing)

| # | Prereg Requirement | As Executed | Deviation |
| :--- | :--- | :--- | :--- |
| D1 | Matched total model params `~15M ± 0.5%` across all arms | H8c heads run at `1,610,119 / 1,756,423 / 1,905,415` params (`1.61M–1.91M`) | Budget missed by ~`8–9×`; head-to-head spread `18.3%` `≫ 0.5%` |
| D2 | Part 2: equal-total-param BPE arm comparison | No BPE arm in `H8c` Part 2 | Gate untestable as run |
| D3 | Part 2: primary multi-domain BPB improvement `≥ 5%` | `-1.66%` (`3.6316` vs `3.6930`) | Under threshold → FALSIFIED |
| D4 | `arabic` domain = `S92` Classical Arabic | `bayt-al-hikma` markdown/JSON + Lean sources | Out-of-band substitution |
| D5 | Part 3: gauge-gap (`0.4272`) reduction measured | Never measured | Missing required control |
| D6 | Part 3: total wire bits = payload + framing + hash | Reported payload-only `32` bits | Total wire `352` bits `> 144` → FALSIFIED |
| D7 | `z`-statistics with `n = 3` seeds | Reported as `z` | Actually paired `t`, `df = 2` (`t_{0.975,2} = 4.303`) |
| D8 | Corpus: WikiText-2 + Python 3.12 stdlib caches | Harness interpreter **CPython 3.12.x** (digest-proven); mlos receipts record CPython 3.14.8; both now recorded in each `s108_locked_protocol.json` (`harness_interpreter` / `mlos_interpreter`) and in `corpus_manifest.json` | `python` (`python/cpython@v3.12.12`) and `abios_calculus` (`Moissanite-Labs/abios@753300553abd`, `104` files) rebuild byte-exact from public repos; `english` lists both HF `wikitext-2-v1` file hashes + recipe; `arabic` lists all `78` run-time file hashes (`10` `Foundation-0/bayt-al-hikma@15d48261df82` + `68` `.lean` files); `gpu-full` fails closed (`CORPUS_SOURCE_MISSING`) |
| D9 | No post-run edits to run artifacts | Results `grading` verdicts + exploratory notes, receipt `bound_*` fields, and protocol interpreter fields (`harness_interpreter`, `mlos_interpreter`) were edited **post-run** (19:09 UTC and 20:15 UTC, against runs at 16:52–16:58 UTC; 1:09 PM and 2:15 PM CT vs 10:52–10:58 AM CT) and re-signed; the `s108_locked_protocol.json` files are therefore no longer the run-time bytes; harness grading now mirrors the audit gates and emits `harness_interpreter`, `mlos_interpreter`, and `part2/part3_exploratory_note` at this head | Measured values untouched (reviewer diffed key-by-key); full-chain unkeyed re-sign remains an inherent residual (Low) |
| D10 | AMENDMENT1 §6: independent frozen judge across ALL arms | `ABIOS/3` and `English JSON` arms are scored by `lossless_text_acc` (text-equality), not an independent frozen judge; the audit gate now uses that accuracy (`nm_exact >= abios_acc`) | Judge confound for those two arms disclosed |
| D11 | Matched total params `~15M ± 0.5%` across all arms | H8b `bpe_std` ran at `4,196,608` vs `2,217,602` params for the other H8b arms (REPORT:70) | H8b param mismatch disclosed |

---

## 4. Verification & Hygiene Receipts

- **CPU Pre-Flight Suite (`s108_cpu_preflight.py`, `CUDA_VISIBLE_DEVICES=""`):** `7/7 OK` across all 3 isolated `-I` modes (`-I -B`, `-I -O -B`, `-I -B -W error`, bit-identical R4 stdout); zero bare `assert`s; zero `acos`/`arccos` calls.
- **Dual `aletheia audit-check --strict-ancestors --safety-scan --scripts s108_cpu_preflight.py` (`aletheia-fix-lean-gates-v2` & `aletheia-fast-mutate`):** `PASS ×2` (`r4_scripts_passed=1/1`, `bare_assert=0, crlf=0, leak=0, pycache=0, safety_findings=0, ancestors=0`).
- **Artifacts (`WEIGHTS=0`, `0` GitHub pushes):**
  - `s108_tokenizer_loop_ops.py`, `s108_train_eval.py`, `s108_cpu_preflight.py`, `REPORT_S108_GPU_EVAL.md`, `corpus_manifest.json`
  - `mlos_zone_b_h8a_receipt.json`, `mlos_zone_b_h8b_receipt.json`, `mlos_zone_b_h8c_receipt.json`
  - `gpu_results_h8a/`, `gpu_results_h8b/`, `gpu_results_h8c/` (each containing `s108_locked_protocol.json` and `s108_gpu_full_results.json`)
