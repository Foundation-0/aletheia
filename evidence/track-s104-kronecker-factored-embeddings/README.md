# Kronecker Product-Code Factored Embeddings, Rank-1 Obstruction, `EXP-Delta` Preregistration Audit, Composed Triple Gate & `RAM == WIRE == HASH`

Self-contained Aletheia evidence bundle providing an exact pure-$\mathbb{Z}/\mathbb{Q}$ mathematical audit alongside **`25/25` universal pure-`Init` Lean `4.36.0` theorems** (`0` Mathlib, `0` imports, `0` warnings, `0` banned axioms: `2` `[]`, `23` `⊆ {propext, Quot.sound}`):

1. **Pillar 1 — Exact Kronecker Product-Code Algebra & Calibration Audit:** Re-derives exact rational parameter ratios (`262144/33 = 7943.758x` against a hypothetical `2,097,152`-row `R*P` table vs `18992/33 = 575.515x` against the `151,936`-row padded vocabulary), exact Gram/Schur factorization `(G_A kron G_B)/(G_A[S,S] kron G_B) = (G_A/G_A[S,S]) kron G_B` (`144/144` pair identities), and exposes two exact pitfalls: orthogonal patterns annihilate shared-root inner products (`0`, repaired by hybrid code `[A_r kron B_p ; A_r ; B_p]` with shared-root inner product `||A_r||^2`), and table-level `C_row(E) = 1` is blind to norm-preserving factor misfolds (requiring factor-delta `C_row` and per-row SHA-256 locks).
2. **Pillar 2 — Rank-1 Expressivity Obstruction & Rank-2 Lift:** Proves the 2x2 minor obstruction showing no rank-1 product kernel `alpha(r,r')*beta(p,p')` can represent the additive share-root-OR-share-pattern kernel `delta(r,r') + delta(p,p')` (VLP rank `2`), and realizes it exactly via the rank-2 lift `[e_r ; e_p]`.
3. **Pillar 3 — `EXP-Delta` Preregistration Audit (`PREREGISTERED_NOT_EXECUTED`):** Identifies four protocol flaws (missing FPR control allowing an all-positive scorer to trigger KILL trivially, cross-model agreement mislabelled as determinism, train/test denominator mismatch, and triangle KILL `44/220 = 1.8037x` below `2x` surface model `24.3944` -> repaired to `49/220`) and ships a fail-closed canonical preregistration spec (`exp_delta_latent_repair_spec.json`) plus `--evaluate-results` evaluator tested on synthetic fixtures only.
4. **Pillar 4 — Composed Triple Gate (`StaticProof /\ Receipt /\ Holdout`):** Proves acceptance filters commute (`3510/3510` orderings) while selection-order (`argmax` vs gate) does not commute and static legality does not imply held-out usefulness; verifies exact `(31/32)^96 < 1/20` and integer Clopper-Pearson 95% upper bound for `0/96` (`[515457/16777216, 257729/8388608] < 1/32`).
5. **Pillar 5 — `RAM == WIRE == HASH` Quantization & Avalanche Audit:** Gives an exact integer witness (`v = 3/20`) where pre-wire vs post-float-wire round-half-even quantization diverges (`2` vs `1`) with distinct SHA-256 digests, demonstrates endianness digest divergence (`<6i` vs `>6i`), and proves that no lane-local map on `>= 3` lanes can satisfy a `>= 50%` avalanche gate.

## Honest Scope & Novelty Classification (`N0`)

- **Novelty Classification:** **`N0`** (`n2_claims = 0`). Kronecker/tensor-product embedding compression (`word2ket`/`word2ketXS`, Panahi-Saeedi-Arodz, ICLR 2020; TT-embeddings, Hrinchuk et al., Findings of EMNLP 2020), Van Loan-Pitsianis rearrangement, and Schur complements of Kronecker products are established prior art. This bundle's contribution is a reproducible exact-arithmetic and formal-proof audit: steelmanning the construction, falsifying four over-claims, supplying exact repairs, and locking a corrected preregistration.

## Files

- `KroneckerFactoredEmbeddings.lean` — `25/25` universal pure-`Init` Lean `4.36.0` theorems (`0` external imports, `0` warnings)
- `lean-toolchain` / `lakefile.toml` — Pinned `leanprover/lean4:v4.36.0` build specification
- `s104_kronecker_triple_gate_oracle.py` — Pure-$\mathbb{Z}/\mathbb{Q}$ exact oracle and canonical certificate builder
- `verify_s104_kronecker_triple_gate.py` — Zone-B hardened standalone verifier, field-complete `SEC`/`FR0`/`FR1` auditor, `18`-rule R12 static Lean scanner, and live scrubbed `lean --stdin` kernel verifier
- `s104_kronecker_triple_gate_audit.py` — `*_audit.py` CLI wrapper for `evidence-tracks` CI discovery
- `s104_kronecker_triple_gate_certificate.json` — Committed canonical zero-float certificate (`15,204` bytes)
- `exp_delta_latent_repair_spec.json` — Canonical `PREREGISTERED_NOT_EXECUTED` experimental specification (`3,272` bytes)
- `test_s104_kronecker_triple_gate_r5.py` — Assertion-free verification, every-leaf tamper (`396/396` leaves), Zone-B, R12 Lean gate, and live Lean test suite (`39` tests, `0` skips)
- `REPORT.md` — Complete `13`-finding verdict ledger, `5`-pillar summary, `25`-theorem table, and file manifest

## Quickstart

```bash
# Verify certificate, full deterministic replay, and live Lean 4.36.0 kernel (25/25 theorems)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s104_kronecker_triple_gate.py --check s104_kronecker_triple_gate_certificate.json --json

# Run CI audit wrapper
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B s104_kronecker_triple_gate_audit.py --check s104_kronecker_triple_gate_certificate.json

# Run full test suite across all three isolated Python modes
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B test_s104_kronecker_triple_gate_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -O -B test_s104_kronecker_triple_gate_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B -W error test_s104_kronecker_triple_gate_r5.py
```
