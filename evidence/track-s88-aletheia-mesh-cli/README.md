# `aletheia_mesh` — Reusable Higher-Order Convergence & Structural Transformation Engine (`Orders 1–4`, `T_1`–`T_6`, Law-3 Firewall & `16/16` Pure-`Init` Lean `4.36.0`)

Self-contained Aletheia evidence bundle providing an exact pure-$\mathbb{Z}/\mathbb{Q}$ higher-order mesh convergence and transformation engine (`Orders 1–4`, `T_1`–`T_6`, Law-3 contagion firewall, and generic typed $K_N$ CLI for $4 \le N \le 16$) alongside **`16/16` live kernel-checked pure-`Init` Lean `4.36.0` theorems** (`14` universally quantified `∀` theorems + `2` exact ground combinatorial witnesses; `5` `[]` + `11` `[propext, Quot.sound]`, `0` `Classical.choice`, `0` external imports, `0` warnings):

1. **Orders 1–4 & Parametric Silo-Cut Scaling ($K_4, K_6, K_8, K_{16}$):** Verifies exact Foster resistance sums, `100%` Schur compounding (`28/28` on $K_8$), discrete Bianchi $\delta^2 = 0$ on all `70/70` tetrahedra, and exact balanced silo-cut extinction scaling across edges, triangles, tetrahedra, and 5-cells (`56/56 = 100%` on $K_8$).
2. **`T_1`–`T_3` Hodge Lift, Signed Gauge Double Cover & Auto-Blow-Up Mediator Ranker:** Verifies $B_1 B_2 = 0$, $L_1 = 8 I_{28}$, orthogonal Hodge energy split `13/4 + 11/4 = 6`, strict signed SPD inertia `[8, 0, 0]` (`det(L_sigma) = 1,841,101,056`), 2-sheeted double cover lifting `22` frustrated triangles to `22` open 6-cycles, and the Law-5 `v4` multi-wall star Pareto obstruction (`v6-v7` resolves `6/6` frustrated triangles with `0` regressions vs `v1-v4`/`v2-v4` maximizing spectral/conductance gain while exposing `3`–`4` adjacent multi-wall loops).
3. **`T_4`–`T_6` Directed Loop-Schur Curl, Borromean Hyperedges & Kron Curvature Tomography:** Certifies non-normal 3-node CEER discrete Lyapunov stability (`P - M^T P M = I`) and Law-3 refusal damping (`gamma = 2/5`), `4`-way `8 GiB` sovereign-stack Borromean irreducibility (`14/14` proper subsets fail vs `4821 MiB < 8192 MiB`), $K_8 \to K_4$ Kron effective-resistance invariance (`det(G) = 3218/7036691 > 0`), and Law-3 zero-flux firewall isolation.
4. **Pure-`Init` Lean `4.36.0` Companion (`AletheiaMeshEngine.lean`):** `16/16` theorems verified by Zone-B hardened `SEC`/`FR0`/`FR1` replay, R12 static scanning (blocking dot-qualified escapes, `Char := '"'` quote-desync, raw strings, guillemets, and `private theorem` shadowing), and env-allowlisted live `Lean 4.36.0` elaboration.

## Honest Scope & Novelty Classification (`N1`)

- **Novelty Classification:** **`N1`** (`oracle_class: exact`). Anchored against the frozen sibling `Track S83` $K_8$ epistemic mesh (`evidence/track-s83-all-to-all-epistemic-mesh/`) with exact pure-$\mathbb{Z}/\mathbb{Q}$ replay and `16/16` pure-`Init` Lean `4.36.0` theorems (`14` universal algebraic/scalar/Boolean laws + `2` closed ground `decide` witnesses `Thms 4–5`, with `Thms 14(b), 15(b)` as integer numeric anchors and `Thm 16` as scalar firewall identities).
- **CLI Verification Split:** `--check` verifies Zone-B canonical JSON, full pure-$\mathbb{Z}/\mathbb{Q}$ replay, and the static R12 Lean gate (safe on Lean-less runners); `--verify-lean AletheiaMeshEngine.lean --json` executes live `Lean 4.36.0` kernel elaboration (given a trusted `lean` executable on `PATH` or `ALETHEIA_LEAN_BIN`).

## Files

- `AletheiaMeshEngine.lean` — `16/16` pure-`Init` Lean `4.36.0` theorems (`0` external imports, `0` warnings)
- `lean-toolchain` / `lakefile.toml` — Pinned `leanprover/lean4:v4.36.0` build specification
- `aletheia_mesh_engine.py` — Pure-$\mathbb{Z}/\mathbb{Q}$ higher-order mesh engine (`Orders 1–4`, `T_1`–`T_6`, Law-3 firewall, parametric $K_N$)
- `verify_aletheia_mesh.py` — Zone-B hardened CLI (`--analyze`, `--parametric`, `--check`, `--verify-lean`, `--standalone`, `--write`), R12 static Lean gate, and env-allowlisted live Lean verifier
- `s88_aletheia_mesh_audit.py` — `*_audit.py` CLI wrapper for `evidence-tracks` CI discovery
- `s88_aletheia_mesh_certificate.json` — Committed canonical zero-float certificate (`17,513` bytes)
- `test_s88_aletheia_mesh_r5.py` — Assertion-free verification, tamper, Zone-B, R12 Lean gate, env-allowlist, and live Lean test suite (`0` skips)
- `REPORT.md` — Complete `T_1`–`T_6` operator ledger, theorem table, and frozen file inventory

## Quickstart

```bash
# Verify certificate and full deterministic replay
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_aletheia_mesh.py --check s88_aletheia_mesh_certificate.json --json

# Verify live Lean 4.36.0 kernel (16/16 theorems)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_aletheia_mesh.py --verify-lean AletheiaMeshEngine.lean --json

# Run CI audit wrapper
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B s88_aletheia_mesh_audit.py --check s88_aletheia_mesh_certificate.json

# Run full test suite across all three isolated Python modes
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B test_s88_aletheia_mesh_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -O -B test_s88_aletheia_mesh_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B -W error test_s88_aletheia_mesh_r5.py
```
