# `ALETHEIA-WSE-HC` — Recursive Weight-Space Editing Hill-Climb System (`18/18` Pure-`Init` Lean `4.36.0`)

Self-contained Aletheia evidence bundle combining exact pure-$\mathbb{Z}/\mathbb{Q}$ operator theory, a serialized bare-metal RTX 3080 (`8 GiB`, `mlos` Determinism Zone `B`) 4-way head-to-head benchmark on `Qwen/Qwen2.5-0.5B` (`0` model weights committed), and **`18/18` strictly universally quantified (`∀`) pure-`Init` Lean `4.36.0` theorems** (`2` `[]` + `1` `[propext]` + `15` `[propext, Quot.sound]`, `0` `Classical.choice`, `0` `sorryAx`, `0` external imports, `0` warnings):

1. **Pillar 1 — Exact Pure-$\mathbb{Z}/\mathbb{Q}$ Operator Theory:** Certifies subspace SNR dimensionality collapse (`4,816,896 -> 4,096 = 1,176×`), 4D Householder reflection isometry & involution (`kappa_2(Q) = 1`), `BlockH4` Parseval (`H_4^T H_4 = 4I`), step-oracle gradient blindness vs. discrete jump, `S31` `DPI` support-expansion monotonicity, `S80` 20-step unratcheted FWER inflation (`> 87%`) vs. 5-gate `⫩` ratchet invariance, exact `⧅` orthogonal nullspace projection (`||ΔW_perp X_base||_F^2 = 0`), Law-5 full-rank capacity exhaustion, 2-layer bilinear non-additivity vs. recursive re-linearization (`401/4608 -> 0/1`), and Hybrid Mode B Pareto dominance.
2. **Pillar 2 — Live Bare-Metal RTX 3080 4-Way Showdown (`Qwen/Qwen2.5-0.5B`, Zone-B Receipt `611d7232...`):**
   - **`Aletheia-WSE-HC-Pure` (Backprop-Free):** Cuts peak VRAM by **`1,408.01 MiB` (`-54.34%`)** vs. `Std-Backprop-LoRA` (`1,182.88` vs. `2,590.89 MiB`) and reduces held-out WikiText-2 forgetting by `15.66×` vs. LoRA (`+0.001347` vs. `+0.021094` nats), while honestly recording the Law-5 short-budget zeroth-order NLL descent boundary (`3.3959 -> 3.4062` test NLL).
   - **`Aletheia-WSE-HC-Hybrid` (Mode B Retention-Quality Pareto Winner):** Drops held-out `target_nll` from `3.3959 -> 0.6946`, outperforms `Std-Backprop-LoRA` on exact `151,936`-way `full_vocab_acc` (`56.25%` vs. `50.00%`) with `6.49×` smaller edit Frobenius norm (`0.3932` vs. `2.5526`), and slashes held-out WikiText-2 forgetting to `+0.001305` nats (`+0.0349 PPL`, **`16.16×`** less than LoRA and **`194.5×`** less than `Naive-WSE-HC`).
   - **`Naive-WSE-HC` (Unratcheted Control):** Inflates `||ΔW||_F` to `40.2352` and destroys WikiText-2 perplexity (`26.7628 -> 34.4973`, `+7.7345 PPL`).
3. **Pillar 3 — `18/18` Pure-`Init` Lean `4.36.0` Companion (`RecursiveWeightSpaceHillClimb.lean`):** Every theorem is load-bearing and universally quantified, paired with field-complete `SEC`/`FR0`/`FR1` verification (`682/682 + 341/341` leaf tampers rejected), `74`-probe R12+ static scanner (structurally immune to `Char := '"'` and `X1..X3` lexer desyncs), and `SAFE_LEAN_ENV_KEYS` 8-key env-allowlisted live `Lean 4.36.0` verification.

## Honest Scope & Novelty Classification (`N1`)

- **Novelty Classification:** **`N1`** (`0` `N2` claims, `0` committed model weight files; builds on `N0` MeZO/ES, OGD/nullspace projection, Householder/Hadamard, LoRA, and pinned upstream expedition certs `S31`/`S68`/`S70`/`S73`/`S77`/`S78`/`S80`).

## Files

- `RecursiveWeightSpaceHillClimb.lean` — `18/18` universal pure-`Init` Lean `4.36.0` theorems (`0` external imports, `0` warnings)
- `lean-toolchain` / `lakefile.toml` — Pinned `leanprover/lean4:v4.36.0` build specification
- `rtx3080_s97_wse_hc_bench.py` — Offline 4-way RTX 3080 `Qwen/Qwen2.5-0.5B` benchmark harness
- `rtx3080_s97_wse_hc_results.json` / `mlos_zone_b_receipt.json` — Frozen compact empirical receipt and `mlos` Determinism Zone `B` hardware provenance receipt
- `s97_wse_hc_oracle.py` — Pure-$\mathbb{Z}/\mathbb{Q}$ exact oracle and canonical certificate builder
- `verify_s97_wse_hc.py` — Zone-B hardened verifier, field-complete `SEC`/`FR0`/`FR1` auditor, R12+ static Lean scanner, and 8-key env-allowlisted live Lean verifier
- `s97_wse_hc_audit.py` — `*_audit.py` CLI wrapper for `evidence-tracks` CI discovery
- `s97_wse_hc_certificate.json` — Committed canonical zero-float certificate (`10,484` bytes)
- `test_s97_wse_hc_r5.py` — Assertion-free verification, tamper, Zone-B, R12+ Lean gate, env-allowlist, and live Lean test suite (`0` skips)
- `REPORT.md` — Complete 3-pillar theoretical, empirical, and formal ledger with frozen 11-file manifest

## Quickstart

```bash
# Verify certificate and full deterministic replay
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s97_wse_hc.py --check s97_wse_hc_certificate.json --json

# Verify live Lean 4.36.0 kernel (18/18 theorems)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s97_wse_hc.py --verify-lean RecursiveWeightSpaceHillClimb.lean --json

# Run CI audit wrapper
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B s97_wse_hc_audit.py --check s97_wse_hc_certificate.json

# Run full test suite across all three isolated Python modes
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B test_s97_wse_hc_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -O -B test_s97_wse_hc_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B -W error test_s97_wse_hc_r5.py
```
