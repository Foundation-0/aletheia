# Mellin-GLU Quadrature × `WSP-Gym` × `siliquant` Quantization & `DPI`/`BWI` Tomography

Self-contained Aletheia R1–R5 evidence bundle uniting exact $\mathbb{Z}/\mathbb{Q}$ analysis (`0` floats, pure Python stdlib) and **`18/18` pure-`Init` Lean `4.36.0` theorems** (`2` strictly axiom-free `[]`, `16` strictly `[propext]`, `0` Mathlib, `0` warnings) across three intersecting domains:

1. **Mellin-GLU Exact Quadrature & `siliquant` Scale-Stratified Quantization Rescue (`arXiv:2611.26450`):**
   - Certifies single-layer bias-free GLU quadratic scale collapse ($0 < F_1(\lambda) \le 3\lambda^2$, forcing weight-norm product $\ge 98304/5 = 19660.8$ at $\lambda_{\min} = 1/256$), a runnable `21`-rung exact-$\mathbb{Q}$ Mellin-GLU telescoping quadrature across a $1{,}024\times$ RMSNorm swing ($\max |e| = 0.07902441 < 0.5$, `5/5` exact carry), a `24/24` exact 2-layer Boolean gate, exact axis-aligned width-extension norm compensation (`Granite 4.2 3B` $\gamma_{\mathrm{NL}}^2 = 128/185$; `Qwen 3.5 4B` $\gamma_{\mathrm{NL}}^2 = 512/1023$) with differential $(+254, -256)$ tied readout, and `24/24` SwiGLU hidden-channel permutation invariance.
   - Reproduces uniform `INT4`/`INT8` and unsorted `BlockH4` quantization collapse on a `16`-rung, `4 × 4`-quad Mellin circuit (`12/16`, `8/16`, and `4/16` rungs zeroed; max error `80.996216`, `79.772966`, and `18.010635`), and proves that **scale-stratified `4 × 4` quad grouping** (intra-quad span `8x`) **rescues `5/5` exact carry in pure `INT8`** (`0/16` rungs zeroed, `max_err = 0.162721 < 0.5`) without an FP32 sidecar (while proving why `INT4` still fails at `1.904832` due to step resolution).
2. **Three-Regime `DPI`/`BWI` Structural Weight-Auditing Boundary:**
   - Establishes an honest positive/negative boundary: single-snapshot row-energy concentration $C_{\mathrm{row}}$ cleanly exposes high-dynamic-range Mellin-GLU grafts ($C_{\mathrm{row}} = 7.9675$, `BWI` span `1024x`, `offblock_nnz = 0`, norm-pair squared overload `65,025x`), whereas small symmetry-hidden edits (`sign_flip_in`, `swap_out_cols`, `bias_shift`) are mathematically invisible to single-snapshot $C_{\mathrm{row}}$ (`1.0000` vs. `1.0000` exact; `2.3736` vs. `2.4777` on `WSP-Gym`) and require white-box diff-`DPI` ($\Delta W = W_{\mathrm{faulty}} - W_{\mathrm{clean}}$, spiking `1.0000 -> 4.0000` exact and `2.4777 -> 7.7241` empirically).
3. **`emeraldant/WSP-Gym` (`d050d16d`) Compute-Budget & Random-Edit Walls:**
   - **`CS-08` Compute-Budget Sign Flip (`test_id`, `422` faulty + `78` clean):** While `scale_rl` achieves a `278.3333x` token reduction (`19,035` vs. `5,298,074` tokens) and leads overall (`350/422 = 82.9384%` vs. `319/422 = 75.5924%`, $+7.3460$ pp), `74/77` (`96.10%`) of its exclusive wins occur strictly on `untrained_thinking`'s `95` length cutoffs. Conditioning on the `327` finished faulty networks yields a strict sign flip: `untrained_thinking = 319/327` (`97.5535%`) vs. `scale_rl = 276/327` (`84.4037%`, **`-13.1498 pp`**, exact two-sided McNemar $p = 6.981 \times 10^{-11}$).
   - **`CS-15`/`CS-18` Random-Edit Baseline Wall (`Qwen3.5-0.8B` `MATH-500`, `N = 500`):** Every weight-space editor (`37.00%–38.20%`) is statistically indistinguishable from a random layer-23 row swap `random_L23` (`188/500 = 37.60%`, exact McNemar $p \in [0.854630, 1.000000]$), while a zero-weight-edit `"Wait"` logit ban reaches `194/500` (`38.80%`).

## Honest Scope & Novelty Classification

- **N0 (Prior Literature & Benchmarks):** `arXiv:2611.26450` (*"A CPU Inside an LLM"*, Thms. 3.2–3.4, Tables 3 & 6(b)); `emeraldant/WSP-Gym` (`HEAD = d050d16dda5ed3243f5c59d115e931e44ef3da53`); prior `siliquant` stratified quad grouping and `DPI`/`BWI` definitions.
- **N1 (Synthesized Formal Proofs & Exact Witness Bundle):** Pure-`Init` Lean `4.36.0` formalization (`18/18` theorems, `<= {propext}`, `0` Mathlib, `0` warnings), pure-$\mathbb{Z}/\mathbb{Q}$ quantization-margin and `DPI`/`BWI` collision oracle, and hardened R10 verifier/test suite.

## Files

- `MellinGluQuantMargin.lean` — `18/18` pure-`Init` Lean `4.36.0` theorems (`2` `[]`, `16` `[propext]`)
- `lean-toolchain` / `lakefile.toml` — Pinned `leanprover/lean4:v4.36.0` build specification
- `s77_mellin_wsp_tomography.py` — Pure-$\mathbb{Z}/\mathbb{Q}$ stdlib oracle (`0` floats, `0` bare asserts, `0` RNG)
- `verify_s77_mellin_wsp.py` — Hardened 4-surface verifier (`--standalone`, `--write`, `--check`, `--verify-lean`) + R10 Lean 4 auditor
- `s77_mellin_wsp_audit.py` — `*_audit.py` CLI wrapper delegating to `verify_s77_mellin_wsp.main()` for CI `evidence-tracks` discovery
- `s77_mellin_wsp_certificate.json` — Committed canonical zero-float JSON certificate (`certificate_sha256 = fd571ef4...`)
- `test_s77_mellin_wsp_r5.py` — Assertion-free R5 verification, tamper, filesystem, and live-Lean test suite (`9` test groups)
- `REPORT.md` — Complete quantitative tables, steelman critiques, and theorem inventory

## Reproduction Commands

Run from `evidence/track-s77-mellin-glu-wsp-quantization-tomography/`:

```bash
# Verify certificate (both verifier and CI audit wrapper) and live Lean 4.36.0 kernel (18/18 theorems)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s77_mellin_wsp.py --check s77_mellin_wsp_certificate.json --json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B s77_mellin_wsp_audit.py --check s77_mellin_wsp_certificate.json --json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s77_mellin_wsp.py --verify-lean MellinGluQuantMargin.lean --json

# Run full R5 suite across all three isolated R4 Python modes
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B test_s77_mellin_wsp_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -O -B test_s77_mellin_wsp_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B -W error test_s77_mellin_wsp_r5.py
```
