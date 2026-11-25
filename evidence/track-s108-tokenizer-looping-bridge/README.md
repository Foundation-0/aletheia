# Evidence Track S108 — Tokenizer-Looping Bridge (`PREREG-S108` + `AMENDMENT1`)

This evidence package contains the complete `51`-run live RTX 3080 empirical evaluation (`+ 3`-seed `Part 3` `nullmodem` benchmark), locked preregistration and amendment documents, `3/3` clean Zone-B `mlos` provenance receipts (`WEIGHTS=0`), GPU training/pre-flight harnesses under `gpu_harnesses/`, and a pure-stdlib fail-closed certificate auditor for `Track S108` (`H8a`, `H8b`, `H8c`).

## Honest Literal-Gate Scorecard (`3` Seeds `[42, 137, 2026]`, `n2_claims = 0`)

| Sub-Track | Scope (`3` Seeds) | Verdict | Key Machine-Verified Finding |
| :--- | :--- | :---: | :--- |
| **`H8a`** | `6 × 3` (`18` runs) | **`FALSIFIED`** | Unit-norm `HybridKronSphereEmbedding` + `BlockStructuredProj` eliminates scale-gauge collapse and compresses embeddings **`28.98×`** (`1,572,864 -> 54,272`; `-14.85%` params, `+0.00%` FLOPs), but loses to `flat_bpe` by **`+8.55%` (`z=+30.43`)** on `arabic+abios` (`2.6878` vs `2.4762` BPB) and **`+5.28%` (`z=+35.04`)** on `english+python` (`2.7968` vs `2.6565`); `hybrid_kron_sphere_reinvest` (`L=7`, `-3.31%` params, **`+14.00%`** FLOPs) still trails (`2.7092`). |
| **`H8b`** | `5 × 3` (`15` runs) | **`FALSIFIED`** | Zero-`arccos` 2nd-order geodesic turning (`spherepatch_geodesic2`) collapses to measured **`avg_plen = 1.020`** (`4.9569` BPB, losing **`+11.18%` `z=+6.17`** vs `hnet_cosine`, **`+14.10%` `z=+9.81`** vs `fixed_byte4`, **`+17.40%` `z=+16.16`** vs `blt_entropy`, **`+87.85%` `z=+40.59`** vs `bpe_std`). Independently, the Portal-2 Turing diagnostic nucleates for `D=(1,10)` (`growth_ratio=1.3318`, `mean_boundary_period=3.2222` in `[2.60, 3.45]`) and decays for `D=(5,5)` (`growth_ratio=0.0`, `num_peaks=0`, `mean_boundary_period=32.0` sentinel). |
| **`H8c` Part 1** | `3 × 3` (`9` runs) | **`FALSIFIED`** | Exact-budget adaptive loop pacing maintains `exact_mean_r = 2.0000` and contractive `SafeHopfLoopCore` (`rho = 0.8765–0.9601`), but `adaptive` (`3.6329` BPB) is indistinguishable from `uniform` (`3.6338`, `-0.026%`, `z=-0.18`) and `random` (`3.6309`, `+0.054%`, `z=+0.54`). |
| **`H8c` Part 2** | `3 × 3` (`9` runs) | **`CONFIRMED`** *(vs Parallel; `PARTIAL` vs `LocalAR`)* | `markov_mtp8` (`3.7008` TF BPB) beats independent `parallel_mtp8` (`4.5879`) by **`-19.34%` (`-0.8871` BPB, `z=-63.31`)** while also improving primary loop-exit BPB (`3.6316` vs `3.6930`). `local_ar` leads TF (`3.6088`, `+2.55%`, `z=+6.21`), whereas `markov_mtp8` cuts unrolled exposure-bias BPB by **`-12.37%`** (`5.2840` vs `6.0296`). |
| **`H8c` Part 3** | `3` seeds (`256` eval/seed) | **`PARTIAL`** | Unconfounded `nullmodem` Block-8 `E_8` `RAM==WIRE==HASH` cell bus achieves `100.0%` SHA-256 verification, **`99.74%`** frozen-judge field acc, **`98.96%`** exact 4-field acc, and **`99.87%`** counterfactual edit acc in **`32` payload bits** (`4.5×` smaller than `ABIOS/3` `144` bits), but the `320`-bit per-cell header+SHA-256 pushes single-message total wire to `352` bits (`> 144`), requiring `>= 4`-state batching for total-wire Pareto dominance. |

## Verification (Pure Python Stdlib, Zero External Dependencies)

```bash
python3 -I -B evidence/track-s108-tokenizer-looping-bridge/s108_tokenizer_loop_audit.py --check evidence/track-s108-tokenizer-looping-bridge/s108_tokenizer_loop_certificate.json
python3 -I -B evidence/track-s108-tokenizer-looping-bridge/test_s108_tokenizer_loop_audit_r5.py
```

Full evaluation details live in [REPORT_S108_GPU_EVAL.md](REPORT_S108_GPU_EVAL.md). PyTorch GPU training/evaluation and `7`-gate CPU pre-flight scripts live under `gpu_harnesses/` (`s108_tokenizer_loop_ops.py`, `s108_train_eval.py`, `s108_cpu_preflight.py`).
