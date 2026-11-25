# Rocket × Songe × Unsloth Cut-Cross-Entropy Formal Optimization Laws

Self-contained Aletheia R1–R5 evidence bundle uniting exact $\mathbb{Z}/\mathbb{Q}$ analysis and **`18/18` literal zero-axiom `[]` pure-`Init` Lean `4.36.0` theorems** across three modern LLM post-training and local self-improvement stacks:

1. **Microsoft AI `Rocket` Async-RL Staleness & Bitwise-Parity Laws:** Proves the inference-scaling staleness paradox ($\tau=3, D=720\,\mathrm{s}, \Delta t: 60\to 30\,\mathrm{s}$ raises staleness $15\to 27$, exact ratio $9/5 = 1.80\times$), exponential importance-ratio explosion ($e^{10} \in (22026.4490, 22026.4659)$ at $T=10^4, \delta=10^{-3}$), Kish effective-sample-size collapse strictly below $9/4 = 2.25$ for $R \ge 2(N-1)$, and bitwise-parity invariance at $\delta=0$.
2. **`sous-labs/songe` (`3aba168b`) Idle Self-Improvement vs. `aletheia` Ratchet Gate 2:** Formalizes multi-scale family-wise error inflation ($1 - (19/20)^2 = 39/400 = 9.75\%$ per cycle, $1.95\times$; $>87\%$ across $20$ cycles), unclustered $6$-moment pure-noise false-accept rate ($1/64 = 1.5625\%$), unbounded sub-threshold looping drift, and zero cumulative orthogonal drift under `aletheia` Ratchet Gate 2.
3. **`Unsloth` / Apple Cut-Cross-Entropy (`65643289`) & `8 GiB` Consumer-GPU Roofline:** Proves exact chunked online log-sum-exp conservation/associativity alongside the finite-precision `tl.atomic_cas` ULP non-associativity obstruction (showing stock spinlock CCE breaks Rocket bitwise parity unless replaced by deterministic fixed-order reduction), exact `Qwen2.5-3B` logit compression (`2,489,319,424 B` vs. `32,896 B`, $75{,}672.4047\times$), `Qwen2.5-3B` OPSD-QLoRA `4.5 bpw` OOM rescue (`8,256 -> 3,540 MiB`), and `Inkling-2-Mini` active-expert streaming fit (`4,821 <= 8,192 MiB`).

## Honest Scope & Novelty Classification

- **N0 (Prior Literature Foundations):** Bernoulli (1689), Kish (1965), Bonferroni (1936) / Sidak (1967), Goodhart (1975) / Manheim & Garrabrant (2018), Milakov & Gimelshein (2018), Goldberg (1991), Wijmans et al. (2024, Apple Cut-Cross-Entropy), Dettmers et al. (2023, QLoRA).
- **N1 (Synthesized Formal Laws & Exact Witness Bundle):** Pure-`Init` Lean `4.36.0` formalization (`0` Mathlib, `0` warnings, `18/18` literal `[]` axioms) + pure Python 3 stdlib $\mathbb{Z}/\mathbb{Q}$ oracle, hardened R9+ verifier, and R5 test suite (`measured_live_gpu_in_this_bundle = false`).

## Files

- `RocketSongeUnslothLaws.lean` — `18/18` pure-`Init` Lean `4.36.0` theorems (all `[]` axioms)
- `lean-toolchain` / `lakefile.toml` — Pinned `leanprover/lean4:v4.36.0` build specification
- `s80_rocket_songe_unsloth_oracle.py` — Pure-$\mathbb{Z}/\mathbb{Q}$ exact oracle and canonical certificate builder
- `verify_s80_rocket_songe_unsloth.py` — Hardened standalone verifier, secondary auditor, R9+ static Lean 4 scanner, and live Lean kernel verifier
- `s80_rocket_songe_unsloth_audit.py` — `*_audit.py` CLI wrapper delegating to `verify_s80_rocket_songe_unsloth.main()` for CI `evidence-tracks` discovery
- `s80_certificate.json` — Committed canonical zero-float certificate (`6,098` bytes)
- `test_s80_r5.py` — Assertion-free R5 verification, tamper, filesystem, and live-Lean test suite
- `REPORT.md` — Full quantitative tables, theorem inventory, and engineering transpositions

## Reproduction Commands

```bash
# Verify certificate and live Lean 4.36.0 kernel (18/18 zero-axiom theorems)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s80_rocket_songe_unsloth.py --check s80_certificate.json --json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s80_rocket_songe_unsloth.py --verify-lean . --json

# Run full R5 suite across all three isolated R4 Python modes
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B test_s80_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -O -B test_s80_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B -W error test_s80_r5.py
```
