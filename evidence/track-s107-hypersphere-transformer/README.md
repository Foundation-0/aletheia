# Evidence Track S107 — Native 4D Hypersphere-Transformer (`PREREG-S107` + `AMENDMENT1`)

This evidence package contains the complete `111`-run live RTX 3080 empirical evaluation, locked preregistration and amendment documents, `9/9`-gate CPU pre-flight suite, `3/3` clean Zone-B `mlos` provenance receipts (`WEIGHTS=0`), and a pure-stdlib fail-closed certificate auditor for `Track S107` (`H7a`, `H7c`, `H7b`).

## Honest Literal-Gate Scorecard (`3` Seeds `[42, 137, 2026]`, `n2_claims = 0`)

| Track | Arms × Seeds | Verdict | Key Machine-Verified Finding |
| :--- | :--- | :---: | :--- |
| **`H7a`** | `10 × 3` (`30` LM runs) | **`FALSIFIED`** | `0/4` `BPB_PASS`, `0/4` `KL_PASS`. Neither `S3-Polar` nor `S3-Equatorial` beats BOTH `Cyl` and matching `S3-Permuted` nulls (`>= 1.5%` BPB or `>= 15%` `3`-bit PTQ KL, `z <= -2`). `S3-Equatorial-Std` significantly degrades BPB (`+3.40% z=+2.61`). |
| **`H7c`** | `6 × 3` (`18` LM + `18` bracket) | **`PARTIAL`** | Raw `PREREG-S107:81` `R=3` BPB Criterion 1 fires strongly (`-5.29% z=-4.65` vs `FlatLoop-Std`, `-9.44% z=-42.46` vs `SphereLoop-NoClock`, `-12.53% z=-14.44` vs `Unlooped-16L`), **BUT** graded conservatively `PARTIAL` because `SphereLoop-RandRotClock` (Haar $O(d)$ per pass) matches/beats it (`2.6378` vs `2.6621`, `M1-H1` `2.20` vs `3.07`) proving general orthogonal pass-symmetry breaking (Hopf advantage is strictly `O(d)` `+0.0156%` FLOPs vs `O(d^2)` `+1.33%`), while `R_test=6` collapses via $\phi_5 = 10\pi/11 \approx \pi$ antipodal flip. |
| **`H7b`** | `5 × 3` (`15` LM + `30` $S_3$/$A_5$) | **`PARTIAL`** | Redesigned associative parallel-scan **Data-Dependent Path-Ordered $SU(2)$ Holonomy** eliminates `4×` (`T=2048`) extrapolation blowup (`2.7462` vs `T=512` `2.7547`), beating `RoPE-2D-nGPT` by **`-7.37% (z=-13.32)`**, `Block4-RandOrtho` by **`-8.13% (z=-18.17)`**, `RoPE-2D-Std` by **`-15.38% (z=-12.30)`**, and `LieRE-4D` (`N0`) by **`-4.93% (z=-3.91)`** — yet fails strict no-regression at `T=512` (`+1.22% z=+1.28`), ties at `T=1024`, shows `0` gain on `400`-step $S_3$/$A_5$ tracking, and runs `3.913×` slower in unfused eager PyTorch. |

## Verification (Pure Python Stdlib, Zero External Dependencies)

```bash
python3 -I -B evidence/track-s107-hypersphere-transformer/s107_hypersphere_audit.py --check evidence/track-s107-hypersphere-transformer/s107_hypersphere_certificate.json
python3 -I -B evidence/track-s107-hypersphere-transformer/test_s107_hypersphere_audit_r5.py
```

PyTorch GPU training/evaluation and `9`-gate CPU pre-flight scripts live under `gpu_harnesses/` (`s107_models.py`, `s107_train_eval.py`, `s107_cpu_preflight.py`).
