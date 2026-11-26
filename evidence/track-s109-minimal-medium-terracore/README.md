# Evidence Track S109 — Minimal-Medium Zero-Language Core & Geodynamic TerraCore (`PREREG-S109` + `Amendments 1–3`)

This evidence package contains the complete `114`-model live RTX 3080 empirical evaluation (`+ 18` `PlateSeamRouter` calibrations) across `3` locked seeds `[42, 137, 2026]`, all `4` immutable preregistration and amendment specifications, `3/3` clean Zone-B `mlos` provenance receipts (`weights_saved = 0`), the preserved unmodified pre-Amendment-3 prototype baseline (`gpu_results_h9a/`), PyTorch GPU training/pre-flight harnesses under `gpu_harnesses/`, and a pure-stdlib fail-closed certificate auditor for `Track S109` (`H9a`, `H9b`, `H9c`, `H9d`).

## Honest Literal-Gate Scorecard (`3` Seeds `[42, 137, 2026]`, `0%` Tuple Overlap, Exact `15.0M` Triple Parity, `n2_claims = 0`)

| Hypothesis | Scope (`3` Seeds) | Strict Verdict | Key Machine-Verified Finding |
| :--- | :--- | :---: | :--- |
| **`H9a`** | `18` prototype + `18` steelman models | **`CONFIRMED`** *(with CoT dissection)* | Amendment-3 `Arm A` (`English-CoT-15M`, 2-step CoT layers `0..2 -> 3..6`) hits **`100.00%`** (R1) / **`99.82%`** (R2) vs raw-deflate `Arm B` **`14.16%`** (**`+85.84 pp, z=+51.13`**) and **`7.11%`** (**`+92.71 pp, z=+160.40`**), transparently reported alongside non-CoT `Arm A'` (`15.17% / 8.04%`). Independently of CoT, matched `15M` Decompressor Emulation fails (`0.20%` R1 / **`0.00%`** R2 exact string inversion, `0/6,144`) and Probe-LM unpredictability jumps **`13.95×`** (`0.6088` vs `0.0436` bits/bit). |
| **`H9b`** | `Arm C` / `Y = 1.00` Stagnant Lid | **`FALSIFIED`** | Native Regime I (`CB-6` syntactic transducer + `ir_len = 12`) reaches **`15.09% ± 7.54%`** (`29.64% / 11.23% / 4.39%`) vs `Arm A` `100.00%` (**`-84.91 pp, z=-11.26`**). Native wall latency is **`1.614×`** faster (`0.1309` vs `0.2113 ms/prob`, `< 2.0×` gate) at **`2.46×` lower peak VRAM** (`349.8` vs `862.1 MiB`). `MHPlate` hits **`100.00%`** English & Arabic IR match; bottleneck is tied-weight looped Core stochastic grokking. |
| **`H9c`** | `Arm D` (`<= 96`-bit $S^{31}$ residual) + `Arm D-mono` | **`FALSIFIED`** | All modularity & anti-smuggling invariants pass (`100%` frozen Core SHA-256 across `72` Stage-2 plates, `0` skip paths, `0/18` `CS21_RESIDUAL_LEAK` max `+0.0068`, `CB-1..CB-6` clean, Seed-42 zero-oracle DPI recovery **`93.98%`**, outperforming unfrozen `Arm D-mono` `5.52% / 6.07%`), but best R2 **`12.30%`** trails `Arm A` (`-87.52 pp, z=-18.05`), R2 speed is `0.759×`, and counterfactual $h^{(r)}$ audit faithfulness is `16.6%–18.1% << 85%`. |
| **`H9d`** | `5`-point Bingham sweep `Y ∈ {0, 1/4, 1/2, 3/4, 1}` + `Y_0.50_NoHodge` | **`FALSIFIED`** | Exact monotone Bingham flux (`1.000 -> 0.1173 -> 0.0625 -> 0.0625 -> 0.000`), Hodge orthogonality (`<= 4.06e-3` vs `0.939` `NoHodge`), Portal-5 Darboux (`rank=32, dark_dim=448, err <= 3.37e-15`), and cocycle routing (`99.95%–100.00%, err <= 1.79e-7`) verify cleanly — yet `Y = 0.00` already passes leak (`+0.0015`) & `§SWAP` (`-0.02 pp`) with `12.08% >= Y = 0.50 10.79%`, `Y_0.50` ties `Y_0.50_NoHodge` (`-0.16 pp, z=-0.47`), and audit faithfulness fails `< 85%`. |

## Verification (Pure Python Stdlib, Zero External Dependencies)

```bash
python3 -I -B evidence/track-s109-minimal-medium-terracore/s109_terracore_audit.py --check evidence/track-s109-minimal-medium-terracore/s109_terracore_certificate.json
python3 -I -B evidence/track-s109-minimal-medium-terracore/test_s109_terracore_audit_r5.py
```

Full evaluation details live in [REPORT_S109_GPU_EVAL.md](REPORT_S109_GPU_EVAL.md). PyTorch GPU training/evaluation and `7`-gate CPU pre-flight scripts live under `gpu_harnesses/` (`s109_terracore_models.py`, `s109_train_eval.py`, `s109_cpu_preflight.py`).
