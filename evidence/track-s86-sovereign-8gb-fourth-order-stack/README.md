# Live 4th-Order Sovereign 8 GiB Stack & $T_3$ Blow-Up Verification on Bare-Metal RTX 3080 (`17/17` Pure-`Init` Lean `4.36.0`)

Self-contained Aletheia evidence bundle certifying live bare-metal RTX 3080 (`8,192 MiB`, `sm_86`, Zone-B receipt `mlos_zone_b_receipt.json`) 4th-order Borromean convergence on `Qwen2.5-3B`, lock-free Triton `tl.atomic_cas` vs. deterministic `CCE-Det` $T_3$ blow-up, live `3.0 bpw` Hessian-CSR $\le 1/160$ KL & `S77` Mellin-GLU carry rescue, and **`17/17` live kernel-checked pure-`Init` Lean `4.36.0` theorems** (`16` universally quantified `∀` theorems + `1` anchored live witness; `9` `[]` + `8` `[propext]`, `0` `Classical.choice`, `0` `Quot.sound`, `0` external imports, `0` warnings):

1. **Pillar 1 — Live $T_3$ Blow-Up (`CCE-Det` vs. Materialized CE & Live Triton `3.9.0` Atomics):** On `Qwen2.5-3B` LM-head dimensions (`V = 151,936`, `H = 2,048`), materialized FP32 and BF16 CE hit live CUDA OOM at `N = 4,096` and `N = 8,192`, while Triton `3.9.0` unordered `tl.atomic_cas` produces `12/12` distinct hashes (`863/1,024 = 84.28%` divergent rows, `max_ulp = 15`). `CCE-Det` stays flat at `806.07 MiB` (`N = 4,096`) / `854.13 MiB` (`N = 8,192`) with `0` piconats loss error and `1/12` unique SHA-256 across all 4 tensors (`max_ulp = 0`).
2. **Pillar 2 — Live Borromean 4-Way `8,192 MiB` Training Ablation (`Qwen2.5-3B`, `N = 4,096`):** Every proper `< 4`-pillar subset fails (`No-S78`, `No-S73`, and `No-S80` hit live CUDA OOM; `No-S79` degrades loss/WikiKL `+10.97%` and fails `0/5` `S77` carry), while the full 4-way Sovereign Stack passes across `r = 16` (`3,632.18 MiB`), `r = 64` (`4,893.30 MiB` alloc, `-49.21%` 5-step loss descent, `2/2` bit-identical final parameter SHA-256 `22953dcb...`), and `r = 128` (`6,594.55 MiB`, `+1,597.45 MiB` headroom).
3. **Pillar 3 — Live `S79` $\le 1/160$ Hessian-CSR Sweep on `3.0 bpw QuadSnake`:** Monotonic KL drop across `0.125% -> 0.250% -> 0.500%` on disjoint WikiText-2 and CPython stdlib (`4,088` tokens each). At `0.500%` (`56.86 MiB`, $\rho_s = 128449/25690112 < 1/160$), Hessian-CSR captures `31.01%` sensitivity (`S79` crossover ratio `0.8624 < 1`) and beats same-byte Raw-`|E|` CSR by `2.0288×` (WikiText-2) and `7.6903×` (CPython).
4. **Pillar 4 — `S78` Joint-MDL Horizon Lift, Live `S77` Mellin-GLU Carry Rescue & `17/17` Pure-`Init` Lean `4.36.0` Companion:** Sensitivity-weighted `0.50%` Hessian-CSR rescues `5/5` Mellin-GLU carry scales (`0.315180 < 0.5`, exact FP32 parity) at `3.0 bpw` using `16/2,621` (`0.61%`) of budget where magnitude-only CSR fails `4/5`, paired with `17/17` pure-`Init` Lean `4.36.0` theorems verified by field-complete `203/203` `SEC`/`FR0`/`FR1` replay, R12 static scanner, and strict 5-key env-allowlisted live Lean verification.

## Honest Scope & Novelty Classification (`N1`)

- **Novelty Classification:** **`N1`** (zero model weight files committed; builds on `N0` Cut Cross-Entropy, QLoRA, SqueezeLLM, and pinned upstream expedition tracks `S73`/`S77`/`S78`/`S79`/`S80`/`S83`).

## Files

- `SovereignStackFourthOrder.lean` — `17/17` pure-`Init` Lean `4.36.0` theorems (`0` external imports, `0` warnings)
- `lean-toolchain` / `lakefile.toml` — Pinned `leanprover/lean4:v4.36.0` build specification
- `rtx3080_s86_sovereign_eval.py` — Bare-metal RTX 3080 Zone-B evaluation harness
- `rtx3080_s86_empirical_results.json` / `mlos_zone_b_receipt.json` — Frozen bare-metal empirical results and Zone-B hardware provenance receipt
- `s86_sovereign_stack_oracle.py` — Pure-$\mathbb{Z}/\mathbb{Q}$ exact oracle and canonical certificate builder
- `verify_s86_sovereign_stack.py` — Zone-B hardened verifier, field-complete `203/203` `SEC`/`FR0`/`FR1` auditor, empirical anchor cross-checker, R12 static Lean gate, and strict 5-key env-allowlisted live Lean verifier
- `s86_sovereign_stack_audit.py` — `*_audit.py` CLI wrapper for `evidence-tracks` CI discovery
- `s86_sovereign_stack_certificate.json` — Committed canonical zero-float certificate (`9,315` bytes)
- `test_s86_sovereign_stack_r5.py` — Assertion-free verification, tamper, Zone-B, R12 Lean gate, env-allowlist, and live Lean test suite (`0` skips)
- `REPORT.md` — Complete 4-pillar empirical & formal ledger, theorem table, and frozen file manifest

## Quickstart

```bash
# Verify certificate, full deterministic replay, and empirical anchor cross-check
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s86_sovereign_stack.py --check s86_sovereign_stack_certificate.json --json

# Verify live Lean 4.36.0 kernel (17/17 theorems)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s86_sovereign_stack.py --verify-lean SovereignStackFourthOrder.lean --json

# Run CI audit wrapper
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B s86_sovereign_stack_audit.py --check s86_sovereign_stack_certificate.json

# Run full test suite across all three isolated Python modes
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B test_s86_sovereign_stack_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -O -B test_s86_sovereign_stack_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B -W error test_s86_sovereign_stack_r5.py
```
