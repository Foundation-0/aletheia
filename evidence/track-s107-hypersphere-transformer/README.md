# Evidence Track S107 — Native 4D Hypersphere-Transformer (`PREREG-S107` + `AMENDMENT1`)

This evidence package contains the complete `111`-run live RTX 3080 empirical evaluation, preregistration and amendment documents, `9/9`-gate CPU pre-flight suite, `3/3` cryptographically verified Zone-B `mlos` provenance receipts (`WEIGHTS=0`), `corpus_manifest.json`, and a pure-stdlib fail-closed certificate auditor for `Track S107` (`H7a`, `H7c`, `H7b`).

> **Provenance & Scope Disclosures:**
> - **Lock-Time Verifiability:** Pre-run lock time of `PREREG_S107_HYPERSPHERE_TRANSFORMER.md` and `PREREG_S107_S108_AMENDMENT1.md` **cannot be independently verified from repository git history alone** (earliest commit `0da35e4c` at `17:10 UTC` post-dates the `14:49–16:40 UTC` GPU windows, and the run JSONs do not embed prereg hashes).
> - **Preregistration Deviations:** (1) `H7c` ran `clock_law = "unaliased_coprime"` ($\phi_r = 2\pi r / 11$) rather than prereg $\phi_r = 2\pi r / R$; (2) classical Arabic (`S92`) was omitted from the offline 3-domain eval bundle; (3) `SphereLoop-RandRotClock` was added as a post-hoc adversarial control arm in `H7c`. See `REPORT_S107_GPU_EVAL.md` §2.
> - **Corpus Reconstructibility:** `corpus_manifest.json` pins exact `Salesforce/wikitext` (`wikitext-2-raw-v1`) parquet SHA-256s (`validation` `204929b7...`, `test` `5f1bea06...`) and the `14` local files matching `H7a` eval, while explicitly disclosing `reconstructible_from_repo_alone = false` because the `python_code` and `json_traces` slices came from a live local workspace outside this repository whose intermediate `H7b/H7c` state was later modified.

## Honest Scorecard — Literal Prereg vs. Graded Verdict (`3` Seeds `[42, 137, 2026]`, `n2_claims = 0`)

All paired tests across the `3` locked seeds report **paired `t` (`df = 2`)**.

| Track | Arms × Seeds | Literal Prereg Verdict | Graded Verdict | Key Machine-Verified Finding |
| :--- | :--- | :---: | :---: | :--- |
| **`H7a`** | `10 × 3` (`30` LM runs) | **`FALSIFIED`** | **`FALSIFIED`** | `0/4` `BPB_PASS`, `0/4` `KL_PASS`. Neither `S3-Polar` nor `S3-Equatorial` beats BOTH `Cyl` and matching `S3-Permuted` nulls (`>= 1.5%` BPB or `>= 15%` `3`-bit PTQ KL, `t <= -2`). `S3-Equatorial-Std` degrades BPB by `+3.40%` (`paired t = +2.61, df = 2`, two-sided `p = 0.12`, not significant at `α = 0.05`). |
| **`H7c`** | `6 × 3` (`18` LM + `18` bracket) | **`CONFIRMED`** | **`PARTIAL`** | Literal `PREREG-S107:81` OR-gate Criterion 1 fires (`-5.29% t=-4.65` vs `FlatLoop-Std`, `-9.44% t=-42.46` vs `SphereLoop-NoClock`, `-12.53% t=-14.44` vs `Unlooped-16L`, which appears undertrained at `600` steps), **BUT** downgraded post-hoc to `PARTIAL` because added control `SphereLoop-RandRotClock` (Haar $O(d)$ per pass) matches/beats it (`2.6378` vs `2.6621`, `M1-H1` `2.20` vs `3.07`) proving general orthogonal pass-symmetry breaking (Hopf advantage is strictly `O(d)` `+0.0156%` FLOPs vs `O(d^2)` `+1.33%`), while `R_test=6` collapses via $\phi_5 = 10\pi/11 \approx \pi$ antipodal flip. |
| **`H7b`** | `5 × 3` (`15` LM + `30` $S_3$/$A_5$) | **`FALSIFIED`** | **`PARTIAL`** | Literal `PREREG-S107:52` is `FALSIFIED` because `SU2-Holonomy-Scan-nGPT` trails `RoPE-2D-nGPT` at `T=512` (`+1.22% t=+1.28`), failing the no-regression clause. Graded `PARTIAL` because on the identical paired `T=2048` `16`-window tail slice (`2.7462 BPB`; not directly comparable to the `64`-window `T=512` slice), `SU2` beats `RoPE-2D-nGPT` by **`-7.37% (t=-13.32)`**, `Block4-RandOrtho` by **`-8.13% (t=-18.17)`**, `RoPE-2D-Std` by **`-15.38% (t=-12.30)`**, and `LieRE-4D` (`N0`) by **`-4.93% (t=-3.91)`**; ties `T=1024`, shows `0` gain on `400`-step $S_3$/$A_5$ tracking, and runs `3.913×` slower in unfused eager PyTorch. |

## Verification (Pure Python Stdlib, Zero External Dependencies)

```bash
python3 -I -B evidence/track-s107-hypersphere-transformer/s107_hypersphere_audit.py --check evidence/track-s107-hypersphere-transformer/s107_hypersphere_certificate.json
python3 -I -B evidence/track-s107-hypersphere-transformer/test_s107_hypersphere_audit_r5.py
```

PyTorch GPU training/evaluation and `9`-gate CPU pre-flight scripts live under `gpu_harnesses/` (`s107_models.py`, `s107_train_eval.py`, `s107_cpu_preflight.py`).
