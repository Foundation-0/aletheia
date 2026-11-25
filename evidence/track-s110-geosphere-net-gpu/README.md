# Evidence Track S110 — Pruned 4-Operator "Geosphere-Net" (`PREREG-S110` + `AMENDMENT1`)

This evidence package contains the complete `42`-run live bare-metal NVIDIA GeForce RTX 3080 Laptop (`8 GiB`, `sm_86`) empirical evaluation (`14` matched `15M` arms × `3` seeds `[42, 137, 2026]`), `2` live `<2 min` `sm_86` operator microbenchmarks, `3/3` clean Zone-B `mlos` hardware provenance receipts (`WEIGHTS=0`), both immutable preregistration and pruning specifications, `10/10`-gate CPU pre-flight receipt, PyTorch GPU/pre-flight harnesses, and a pure-stdlib fail-closed certificate auditor (`s110_geosphere_audit.py`).

## Honest Literal-Gate Scorecard (`42` Full-Scale `15M` Runs + `2` `sm_86` Microbenches, `n2_claims = 0`)

| Stage / Component | Scope (`3` Seeds) | Verdict | Key Machine-Verified Finding |
| :--- | :--- | :---: | :--- |
| **`sm_86` Microbench Pre-Gate** | `5` ops + `6` full `15M` steps | **`PARTIAL`** | `BinghamProx` (`+1.41%` step), `ACT` (`1.21%`), and `MTP-8` (`+10.04%` combined step) pass `<= 15%` eager; unfused PyTorch `Cayley2x2` (`+15.55%` step) and cuFFT `DarcyEMA` (`+20.97%` step, down from `+96.33%` eager Hillis-Steele) motivate fused `sm_86` kernels. |
| **Stage 1 (`H10a`)** Single-Shell Isolation | `5 × 3` (`15` runs) | **`PARTIAL`** | **`H10a_Shell1_Cayley2x2` (`2.3033 ± 0.0266` BPB) is `#1` overall across all `14` arms**, beating `Baseline_Loop` (`-0.0943` BPB / **`-3.94%`, `z = +3.82`, `p_Holm = 0.000262`**) and all `4/4` `N0` baselines (`z = +2.47..+5.48`) with exact Beltrami `[C, K] = 0` (`m0..m4 <= 1.2e-7`, `|mean(H/E)| <= 0.0248`, per-seed `|H/E| <= 0.070645`), while hitting `R_test = 6` phase over-winding (`6.6218` BPB; small-sample `t(df=2)` sensitivity `p_Holm = 0.1239` disclosed). |
| **Stage 2 (`H10b`)** Coupled `Geosphere-Net` + LOSO | `9 × 3` (`27` runs) | **`FALSIFIED`** | **`H10b_Geosphere_Full` (`2.6976 ± 0.0229` BPB) loses to `Cayley2x2` (`+0.3943` BPB worse) and all `4/4` `N0` baselines (`0/4` LOSO shells positive on primary BPB)**, confirming surgical composition over kitchen-sink stacking; variable-depth ACT (`r in {1..4}`) cures `Cayley2x2`'s `R = 6` blowup (`6.62 -> 2.94` BPB), and `Cayley + Bingham + Darcy` reaches `M1-H1 = 1.012` & `+0.1104` BPB `2x` decay. |

## Verification (Pure Python Stdlib, Zero External Dependencies)

```bash
python3 -I -B evidence/track-s110-geosphere-net-gpu/s110_geosphere_audit.py --check evidence/track-s110-geosphere-net-gpu/s110_geosphere_certificate.json
python3 -I -B evidence/track-s110-geosphere-net-gpu/test_s110_geosphere_audit_r5.py
```

Full evaluation details live in [REPORT_S110_GPU_EVAL.md](REPORT_S110_GPU_EVAL.md) and [PREFLIGHT_REPORT.md](PREFLIGHT_REPORT.md).
