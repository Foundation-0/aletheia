# Evidence Track S114 — Bare-Metal `sm_86` Fused `SU(2)` Holonomy-Scan & `HoloSphere` (`PREREG-S114`)

This evidence package contains the complete bare-metal NVIDIA GeForce RTX 3080 Laptop (`GA104M`, `8 GiB`, `sm_86`) empirical evaluation of Track S114 (`EXP-Q18a..c`): V1 (`9/9` `0 B`-spill) and post-V1 V2 (`27/27` `0 B`-spill) CUDA/PTX + Triton kernel foundry benchmarks, `51/51` full training runs (`21` `H14b` equal-wall-clock + equal-step `15M` LM runs and `30` `H14c` $S_3$/$A_5$ group tracking runs across seeds `{42, 137, 2026}`), `3/3` clean Zone-B `mlos` hardware telemetry receipts (`WEIGHTS=0`, `ELF=0`), both immutable preregistration documents (`PREREG_S114_SILISPHERE_FUSED_ENTITY.md` & queued `PREREG_S114_AMENDMENT1_S107_S108_CONVERGENCE.md`), and a pure-stdlib fail-closed certificate verifier (`s114_holosphere_audit.py`) with `131/131` (`100.0%`) mutation-killed R5 tests (`test_s114_holosphere_audit_r5.py`).

## Honest Literal-Gate Scorecard (`N1`, `n2_claims = 0`)

| Hypothesis | Scope (`3` Seeds `{42,137,2026}`) | Locked Verdict | Machine-Verified Outcome |
| :--- | :--- | :---: | :--- |
| **`H14a` (`EXP-Q18a`)** | V1 (`9/9` `0 B`-spill, `cu=8c9c40ff`) + Post-V1 V2 (`27/27`, `cu=15f9b3a2`) | **`CONFIRMED`** (`4/4` V1 gates) | Locked V1: `9/9` `0 B` spills, FP32 `max_abs <= 7.82e-6`, BF16 `max_abs <= 1.953e-3`, `12L` step `0.6765×` `RoPE-2D-nGPT` (`5.83×` vs eager `H7b`), gated BHTD speedup `37.86×` (`T=512`) / `46.05×` (`T=2048`). Post-V1 V2: `27/27` `0 B` spills, `0.6313×` `RoPE-2D-nGPT` (`6.35×` vs eager). |
| **`H14b` (`EXP-Q18b`)** | `21/21` runs (`7` arms × `3` seeds, equal-wall-clock `CS-08` + equal-step) | **`CONFIRMED`** (independently on preregistered `HoloSphere-V2-SU2-Unlooped`) | Preregistered **`HoloSphere-V2-SU2-Unlooped`** passes `C1/C2/C3`: `T=2048` `2.6484` (`-10.00%` vs `RoPE-2D-nGPT`, `p_t=0.00076`; `-18.98%` vs `RoPE-2D-Std`, `p_t=0.00090`), `T=512` `2.6545` (`-3.56%`), `0.7632×`/`0.8318×` `mJ/tok` vs `RoPE-2D-nGPT`. Exploratory trig-free `CayleySU2` leads `T=2048` (`2.6098`, `-11.31%`). `RoPE-2D-Std` leads in-distribution `T=512` (`2.5846`) and absolute inference energy (`0.4755 mJ/tok`), with `4×` collapse (`3.2687`). |
| **`H14c` (`EXP-Q18c`)** | `30/30` runs (`5` arms × `S_3/A_5` × `3` seeds) | **`FALSIFIED`** (`0/2` group gates) | `Full-Covariant-QKV-Untransport` reaches `35.30%` OOD on $S_3$ (`< 50.0%` floor; `+4.24 pp` vs `H7b-QK-Only`, `p_t=0.291`) and `2.58%` on $A_5$ (`< 15.0%` floor, near `1.67%` chance), consistent with (not directly ablated) a softmax convex-hull closure obstruction. |

## Verification (Pure Python Stdlib, Zero External Dependencies)

```bash
python3 -I -B evidence/track-s114-silisphere-fused-kernel-transformer/s114_holosphere_audit.py --check evidence/track-s114-silisphere-fused-kernel-transformer/s114_holosphere_certificate.json
python3 -I -B evidence/track-s114-silisphere-fused-kernel-transformer/test_s114_holosphere_audit_r5.py
```

Full evaluation details, explicit deviations, and limitations live in [REPORT_S114_HOLOSPHERE_GPU_EVAL.md](REPORT_S114_HOLOSPHERE_GPU_EVAL.md).
