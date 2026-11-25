# Transhistorical `K_26` Convergence & Two-Way Classical-to-Modern Algorithmic Transpositions (`18/18` Pure-`Init` Lean `4.36.0`)

Self-contained Aletheia evidence bundle combining live CPU real-weight tomography on `rel-int/CircularEP` (`best.json`, `300/300` equilibria), exact pure-$\mathbb{Z}/\mathbb{Q}$ classical-to-modern algorithmic transpositions and $K_{26}$ interlocking-mesh operators (`16` modern certificates $\cup$ `10` classical primary-source nodes), explicit Law-5 non-commutativity obstructions, and **`18/18` kernel-checked pure-`Init` Lean `4.36.0` theorems** (`16` universal `∀` + `2` exact ground integer witnesses, `0` imports, `0` warnings, axioms strictly `[propext, Quot.sound]`, `0` `Classical.choice`, `0` `sorryAx`):

1. **Pillar 1 — Al-Tusi Counter-Rotating Dual-Loop Operator (`1261 CE`) $\times$ Live `CircularEP`:** Applied live across all `300/300` equilibria $M = BA \in \mathbb{R}^{256\times 256}$, $T_{\mathrm{Tusi}}(M) = \frac{1}{2}(M+M^\top)$. The headline gains are properties of the symmetrisation construction, not data findings: a real symmetric matrix has a real spectrum (`0/300` complex-dominant after, `39/300` before; `max |Im| = 0`), $\|T\|_2 \le \|M\|_2$ on `300/300` (`-31.96%` median) is the triangle inequality, and Bendixson holds by theorem. The 60-step PI error drop `4.225905e+06x` (`0.069364 -> 1.641392e-08`) and disparity collapse `1.413460e+09x` (`2.912e+09x -> 2.0604x`) are measured against `rho(T)`; against the loop's real contraction rate `rho(M)`, PI on `T` is worse on `39/39` complex cases (median miss `100.8%` vs `6.9%` raw PI on `M`). The non-trivial live number is the Law-5 spectral-radius **cost** (`+47.82%` median lift; shear $s \ge 3$ destabilization; `2x` JVP cost), plus the `H_2` twin-loop block split (`6.938894e-18`).
2. **Pillar 2 — Al-Kashi Contractive Fixed-Point Cubic (`1427 CE`) vs. Newton/Chebyshev:** Proves exact division-free contraction $L = 3R^2/p < 1$ (`2` steps / `0` FDIVs reach `9.874e-12` at `p=45`, `3` steps reach `7e-15`), alongside exact Law-5 near-cliff (`>2,100x` Newton win at $x^* = 9/10$) and post-cliff repulsion boundaries ($x^* = 6/5$, slope $36/25 > 1$).
3. **Pillar 3 — Banu Musa Hysteretic Regulator (`~850 CE`) & Ibn al-Nafis Septal Firewall (`1242 CE`):** Maps positive conical-float deadband to pinned `aletheion` CPU/GPU thermal hysteresis (`9 -> 0` chatter switches) and impermeable septum ($w_{\mathrm{sep}}=0$) to zero-shunt pulmonary transit (`-50%` Rayleigh conductance drop, `2 -> 1`), with explicit Law-5 analog/discrete and valved-asymmetry obstructions.
4. **Pillar 4 — Full Pure-$\mathbb{Z}/\mathbb{Q}$ `K_26` Transhistorical Mesh (`325` Edges, `65,780` 5-Cells) & Lean `4.36.0` Companion:** Exact inertia `[25, 0, 1]`, Foster `= 25`, Kirchhoff `11.5226`, Schur-conductance boosts on all pairs (`+57.72%` modern / `+146.16%` classical median) — Rayleigh-monotonicity properties of the complete-graph construction (reproduced under random edge labellings), not findings about the texts or certificates; the `16` modern nodes are SHA pins (`5/16` on-disk in this repo, `11/16` external pins (math0@main / historical PR commits / nowhere readable)) and the `10` classical nodes pin an external non-public corpus, `14,950/14,950` discrete $\mathbb{Z}_2$ Bianchi `= 0`, `96.09%` (`13|13`) and `92.98%` (`16|10`) 5-cell silo-cut collapse, and exact Sherman–Morrison `T_3` blow-up ranking. Verified by field-complete `SEC`/`FR0`/`FR1` auditor (`492/492` single-leaf re-signed tamper rejections, `0` bypasses), R12+ comment-only Lean scanner, allowlisted env scrubbing, and zero-skip R5 suite.

## Honest Scope & Novelty Classification (`N1`)

- **Novelty Classification:** **`N1`** (`n2_claims = 0`; explicit `N0` prior-art attribution to `Foundation-0/bayt-al-hikma`, classical matrix theory, `rel-int/CircularEP`, and prior tracks).

## Files

- `TranshistoricalK26AndTusiCure.lean` — `18/18` pure-`Init` Lean `4.36.0` theorems (`0` external imports, `0` warnings)
- `lean-toolchain` / `lakefile.toml` — Pinned `leanprover/lean4:v4.36.0` build specification
- `s91_live_tusi_anchor_capture.py` / `s91_tusi_circularep_live_anchor.json` — Offline CPU `CircularEP` capture script and frozen anchor (`3,079` bytes)
- `s91_transhistorical_k26_oracle.py` — Pure-$\mathbb{Z}/\mathbb{Q}$ exact oracle and canonical certificate builder
- `verify_s91_transhistorical_k26.py` — Zone-B hardened verifier, `492/492` field-complete `SEC`/`FR0`/`FR1` auditor with constant-time canonical payload pin, R12+ Lean scanner, and live scrubbed Lean `4.36.0` verifier
- `s91_transhistorical_k26_audit.py` — `*_audit.py` CLI wrapper for `evidence-tracks` CI discovery
- `s91_transhistorical_k26_certificate.json` — Committed canonical zero-float certificate (`21,635` bytes)
- `test_s91_transhistorical_k26_r5.py` — Assertion-free verification, tamper, Zone-B, R12+ Lean gate, and live Lean test suite (`0` skips)
- `REPORT.md` — Complete 4-pillar technical report, Lean companion index, and file manifest

## Quickstart

```bash
# Verify certificate, full deterministic replay, and live Lean 4.36.0 kernel (18/18 theorems)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s91_transhistorical_k26.py --check s91_transhistorical_k26_certificate.json --json

# Run CI audit wrapper
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B s91_transhistorical_k26_audit.py --check s91_transhistorical_k26_certificate.json

# Run full test suite across all three isolated Python modes
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B test_s91_transhistorical_k26_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -O -B test_s91_transhistorical_k26_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B -W error test_s91_transhistorical_k26_r5.py
```
