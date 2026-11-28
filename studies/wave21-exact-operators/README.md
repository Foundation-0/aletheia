# Exact Operators & Verification Gates (`EXP-Q42b` & `EXP-Q42c`)

This directory contains two self-contained, pure-Python stdlib (`int`/`Fraction`) and pure-`Init` Lean `4.36.0` verification bundles with zero external dependencies, zero production IEEE-754 floats, and zero bare `assert` statements.

## Bundles

1. **`q42b_prior_tilt/` (`EXP-Q42b` — Prior-Tilt Logit-Bias Obstruction & Fixed-Scale Lattice Remainder Contraction)**
   - **Mathematical Result:** Demonstrates how a single additive shift on imbalanced comparable-pair cohorts yields positive net improvement on both raw and flipped objectives without resolving imbalance (`real_net = 77`, `rate = 11/58`; `flipped_net = 52`, `rate = 26/203`), contrasts this against the equal-weight balanced-cohort gate (`balancedNumerator = 0`), and certifies fixed-scale remainder contraction (`b = 1/50`, `p = 3/4`, `factor = 1/625`) in `3` exact cleared-integer steps.
   - **Lean Package (`q42b_prior_tilt/lean/`):** `PriorTilt` (Lean `4.36.0`, pure `Init`, zero external packages), `9` public theorems + `AxiomAudit.lean` (`[propext, Quot.sound]` only).
   - **Artifacts:** `verify_s160_q42b_prior_tilt.py`, `test_s160_q42b_r5.py` (`10` R5 tests), `s160_q42b_prior_tilt_certificate.json`, `REPORT_S160_Q42B.md`.

2. **`q42c_reciprocity_gate/` (`EXP-Q42c` — Anti-Collusion Reciprocity-Cycle & Correlated-Verifier Hodge Gate)**
   - **Mathematical Result:** Certifies the exact correlated false-accept mixture law $P_{\mathrm{joint}} = \rho \min(\epsilon_1, \epsilon_2) + (1 - \rho)\epsilon_1\epsilon_2 \ge \epsilon_1\epsilon_2$ (collation factor `5/1` at $\epsilon = (1/10, 1/5)$), the combinatorial reciprocity trace / skew-curl Hodge split $\mathrm{skew} + \mathrm{tr}(A^2) = |E|$, and a seeded (`16042`) degree-matched configuration-model benchmark (`AUROC = 1/1`, `FPR = 0/1`, `TPR = 1/1`).
   - **Lean Package (`q42c_reciprocity_gate/lean/`):** `ReciprocityGate` (Lean `4.36.0`, pure `Init`, zero external packages), `9` public theorems + `AxiomAudit.lean` (`[propext, Quot.sound]` only).
   - **Artifacts:** `verify_s160_q42c_reciprocity_gate.py`, `test_s160_q42c_r5.py` (`15` R5 tests), `s160_q42c_reciprocity_certificate.json`, `REPORT_S160_Q42C.md`.

## Quick Verification (3-Mode Isolated `-I` Parity & Live Lean)

```bash
for sub in q42b_prior_tilt q42c_reciprocity_gate; do
  for flags in "-I -B" "-I -O -B" "-I -B -W error"; do
    CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 python3 ${flags} \
      "studies/wave21-exact-operators/${sub}/verify_s160_${sub}.py" --check --json
  done
done

# Run R5 test suites across all 3 isolated R4 modes
for flags in "-I -B" "-I -O -B" "-I -B -W error"; do
  CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 python3 ${flags} \
    studies/wave21-exact-operators/q42b_prior_tilt/test_s160_q42b_r5.py
  CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 python3 ${flags} \
    studies/wave21-exact-operators/q42c_reciprocity_gate/test_s160_q42c_r5.py
done

# Live Lean 4.36.0 build & AxiomAudit verification (runs in an isolated tempdir, zero .lake/ residue)
CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 python3 -I -B \
  studies/wave21-exact-operators/q42b_prior_tilt/verify_s160_q42b_prior_tilt.py --check --json --live-lean
CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 python3 -I -B \
  studies/wave21-exact-operators/q42c_reciprocity_gate/verify_s160_q42c_reciprocity_gate.py --check --json --live-lean
```
