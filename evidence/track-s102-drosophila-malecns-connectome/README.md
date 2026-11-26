# Exact Integer/Rational Operators & Lean 4.36.0 Formalization of the FlyEM *Drosophila* MaleCNS v1.0 Whole-CNS Connectome (`18/18` Pure-`Init` Lean `4.36.0`)

Self-contained Aletheia evidence bundle extracting exact pure-$\mathbb{Z}/\mathbb{Q}$ topological, Dale's-law, Schur-complement, Krein-inertia, and signed-frustration operators from the FlyEM *Drosophila* MaleCNS v1.0 connectome (`164,740` active neurons, `25,568,639` directed edges, `124,039,080` synapses) alongside **`18/18` universally quantified pure-`Init` Lean `4.36.0` theorems** (`0` imports, `0` warnings, `2` `[propext]` + `16` `[propext, Quot.sound]`, `0` `Classical.choice`, `0` `sorryAx`):

1. **Pillar 1 — Whole-CNS Exact Topology & Dale's-Law Partition:** Computes exact Dale's-law partition (`E = 73,479,194` ACh vs `I = 47,323,246` GABA+Glu+His; `E:I = 36739597/23661623 = 1.5527`), heavy-tail integer thresholds (`w >= 1..500`), and top-`0.5%` synaptic capture (`11.8722%`, `23.74x` uniform) vs LLM Hessian-CSR curvature (`31.0100%`, `2.6120x` sharper).
2. **Pillar 2 — 8x8 Functional Supergraph, 6x6 Central-Complex Core & Signed Triad Frustration:** Proves structural frustration via exact LDL^T inertia (`L_sigma(W8_s)`: `[8, 0, 0]`; `L_sigma(W6_s)`: `[6, 0, 0]` + exact Farkas multiplier `L_sigma * q == 1`), Krein inertia (`H_s(W8_s)`: `[5, 3, 0]`; `H_s(W6_s)`: `[4, 2, 0]` matching `4` excitatory vs `2` inhibitory compass populations), `8 -> 3` boundary Schur complement (`13.5524%` dark-mode shadow), `7.182x` non-normal commutator amplification in the CX ring attractor, and `6.853x` incoherent FFL / `6.851x` frustrated 3-cycle enrichment against a degree- & neurotransmitter-preserving Maslov-Sneppen null.
3. **Pillar 3 — Cross-Portal Engineering Bridges:** Connects exact integer LIF `may_fire` Lyapunov bounds (`E(v,g) = 4*max(v,0) + max(g,0)`), SpMV bandwidth crossover ratios (`35/4` to `57/4`), and 4-arm connectome tail-risk variance collapse (`10.703x` MLP/fly).
4. **Pillar 4 — Pure-`Init` Lean `4.36.0` Companion (`DrosophilaConnectomeOperators.lean`):** `18/18` universal theorems verified by field-complete `SEC`/`FR0`/`FR1` replay (`702/702` leaf tamper rejections), bounded anchor parser, R12 static + 10-var scrubbed live `lean --stdin` verifier, and zero-skip R5 test suite.

## Honest Scope & Novelty Classification (`N0`/`N1`)

- **Novelty Classification:** **`N0`/`N1`** (`n2_open_claims_count = 0`). Primary connectome measurements come from FlyEM MaleCNS v1.0 (`CC-BY-4.0`, pinned externally with zero raw `.feather` dataset copies in this bundle); the contribution is a reproducible exact-$\mathbb{Z}/\mathbb{Q}$ and pure-`Init` Lean `4.36.0` formal verification suite.

## Files

- `DrosophilaConnectomeOperators.lean` — `18/18` universal pure-`Init` Lean `4.36.0` theorems (`0` external imports, `0` warnings)
- `lean-toolchain` / `lakefile.toml` — Pinned `leanprover/lean4:v4.36.0` build specification
- `s102_extract_malecns_anchor.py` / `s102_malecns_anchor.json` — Offline anchor extractor and frozen MaleCNS anchor (`7,949` bytes)
- `s102_malecns_connectome_oracle.py` — Pure-$\mathbb{Z}/\mathbb{Q}$ exact oracle and canonical certificate builder
- `verify_s102_malecns_connectome.py` — Zone-B hardened verifier, field-complete `SEC`/`FR0`/`FR1` auditor, R12 static Lean scanner, and live scrubbed `lean --stdin` kernel verifier
- `s102_malecns_connectome_audit.py` — `*_audit.py` CLI wrapper for `evidence-tracks` CI discovery
- `s102_malecns_connectome_certificate.json` — Committed canonical zero-float certificate (`20,226` bytes)
- `test_s102_malecns_connectome_r5.py` — Assertion-free verification, tamper, Zone-B, R12 Lean gate, and live Lean test suite (`0` skips)
- `REPORT.md` — Complete 4-pillar connectome operator ledger, theorem table, and file manifest

## Quickstart

```bash
# Verify certificate, full deterministic replay, and live Lean 4.36.0 kernel (18/18 theorems)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s102_malecns_connectome.py --check s102_malecns_connectome_certificate.json --json

# Run CI audit wrapper
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B s102_malecns_connectome_audit.py --check s102_malecns_connectome_certificate.json

# Run full test suite across all three isolated Python modes
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B test_s102_malecns_connectome_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -O -B test_s102_malecns_connectome_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B -W error test_s102_malecns_connectome_r5.py
```
