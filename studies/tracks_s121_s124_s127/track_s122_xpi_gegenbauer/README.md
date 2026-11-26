# Track S122 (`EXP-Q26c`) — `Portal x/π` Spherical Multipole & Möbius-Gegenbauer Attention

Exact-$\mathbb{Q}$ operator verification (`0` floats, `53/53 = 100.0%` `aletheia mutate`) and matched-budget 3-seed CPU benchmark (`27,079` / `27,198` parameters, `17/17 = 100.0%` `aletheia mutate` on PyTorch-enabled hosts; `13/17 = 76.47%` on torch-free Python where `_train_one` is skipped) networking `Portal x/π` spherical harmonics over Pari–Agrawal–Kim (*Simplicity Bias in Attention*, 2026).

## Artifacts
- `verify_xpi_gegenbauer_attention.py` — Pure-stdlib zero-float rational oracle (`certificate_sha256: 16d2d039358dcdee1e1a85e9211603c48a3a1a808c1ba2129d95f3b15fd04ba3`) proving $g$-independent spherical denominator projection, exact convex Chebyshev decomposition of $\tilde{C}_r^{(\alpha)}(u)$, north-pole Möbius boost $1 - \psi_g(u)^2 \ge 0$ with bijective inverse $\psi_{1/g}$ and symbolic north-pole slope $\left.\frac{d}{du}\psi_g\right|_{u=1} = g$ in $\mathbb{Q}(g)[h]$, $239\times$ / $280\times$ monomial slack elimination, Mellin–Sphere–Heat $\frac{2}{\omega_{2k-1}} = \frac{(k-1)!}{\pi^k}$, unit-radius ball normalized second moment $\mathbb{E}[\|x\|^2]/(d R^2) = \frac{1}{d+2}$ vs. Euclidean unit-volume ($\operatorname{Vol}=1$) Zador $G(B^{2k})^{2k} = \frac{(k!)^2}{(2k+2)^{2k}\pi^{2k}}$ in $\mathbb{Q}[\pi,\pi^{-1}]$, and constructive 2D Joukowski $v(\pi/2)^2 - v(-\pi/2)^2 = \frac{4V_\infty\Gamma}{\pi a}$ vs. 3D `BRIDGE_12` non-commutativity.
- `test_xpi_gegenbauer_attention_r5.py` — Pure-stdlib R5 unit & tamper-refusal suite (`5/5 OK ×3 -I`, `53/53 = 100.0%` mutation kill).
- `bench_gegenbauer_vs_monomial_attn.py` — Matched single-thread CPU micro-benchmark (`result_sha256: 674c204da0a030e1cb6cc890dfa882f433d3c99b71f47de131de1b47182184b0`, honest Law-4 verdict `PARTIAL`).
- `test_bench_gegenbauer_r5.py` — R5 unit & smoke suite (`17/17 = 100.0%` mutation kill on PyTorch-enabled hosts; `13/17 = 76.47%` on torch-free Python where `_train_one` requires PyTorch).
- `s122_xpi_gegenbauer_results.json` — Canonical SHA-256-sealed empirical benchmark receipt.
- `REPORT_S122_XPI_GEGENBAUER_ATTN.md` — Full mathematical & empirical report.

## Verification (`CUDA_VISIBLE_DEVICES=""`, `OPENBLAS_NUM_THREADS=1`)
```bash
python3 -I -B verify_xpi_gegenbauer_attention.py
python3 -I -B test_xpi_gegenbauer_attention_r5.py
python3 -I -B bench_gegenbauer_vs_monomial_attn.py --check
python3 -I -B test_bench_gegenbauer_r5.py
```
