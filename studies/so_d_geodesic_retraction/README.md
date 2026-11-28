# Verified Exact-$\mathbb{Q}$ & Empirical Study: $SO(d)$ Cayley Geodesic Step Retraction for Weight Editing

This directory provides a self-contained, pure-Python stdlib verification bundle for a two-phase study comparing unconstrained additive weight updates against flow-nullspace-projected $SO(d)$ Cayley tangent rotations with atomic 16-byte unit-spinor rollback and geodesic step retraction ($\gamma \in \{1, 1/2, 1/4\}$) on `HuggingFaceTB/SmolLM2-360M` and `Salesforce/wikitext-2-raw-v1`.

## Claim Taxonomy & On-Disk Certificate Binding

- **Exact-$\mathbb{Q}$ Algebraic Oracle (`VERIFIED`):** `verify_so_d_geodesic_retraction.py` enforces an internal pure-$\mathbb{Q}$ AST purity check (`verify_oracle_ast_purity`: `0` `ast.Div`, `0` floats/complex, `0` negative `ast.Pow`, `0` `Fraction(str)`/`from_float`, `0` imports inside all `7` oracle functions) and certifies over exact `fractions.Fraction` arithmetic that for a dense skew-symmetric matrix projected via $P_\perp = I_6 - \frac{1}{4}(u_1 u_1^\top + u_2 u_2^\top)$ onto the 4D orthogonal complement of a **non-axis-aligned** 2D protected subspace ($u_1 = (1,1,1,1,0,0)^\top$, $u_2 = (1,-1,0,0,1,-1)^\top$), $Q(\gamma S) = (I - \gamma S)(I + \gamma S)^{-1}$ satisfies exact orthogonality $Q^\top Q = I_6$, orientation $\det Q = 1/1$, spherical shell-norm invariance $\|Qx\|_2^2 = \|x\|_2^2$ (`0/1` residual), protected-subspace invariance $Qu_1 = u_1, Qu_2 = u_2$ (`0/1` drift), the explicit exact Cayley contraction upper bound $\|Q(\gamma S) - I_6\|_F^2 \le 4\gamma^2\|S\|_F^2$, and strictly monotone geodesic contraction across $\gamma \in \{1, 1/2, 1/4\}$ (`9703184/60189969 < 2489744/3992289 < 686384/310869`).
- **Phase 1 Empirical Record (`VERIFIED` negative result — literal `FALSIFIED`):** 3-seed (`[0, 1, 2]`) binary accept/reject gate evaluation (`phase1_binary_gate_results.json`) achieving `131.80x` lower `WikiText-2` prose KL, `18/18` (`100.0%`) live poison blocks, and `0.0` FP32 rollback drift (`G3 = PASS`), while honestly grading `FALSIFIED` (`G1 = FAIL`, `G2 = FAIL`) because binary rejection discarded Round 6 (`R6_triage`) on `3/3` seeds at `KL = 0.00535..0.00686 nats > 0.005`.
- **Phase 2 Empirical Record (`VERIFIED` positive result — literal `CONFIRMED`):** 5-seed (`[0, 1, 2, 3, 4]`, `df = 4`) exact $SO(d)$ Cayley geodesic step retraction (`phase2_geodesic_retraction_results.json`) passing all three locked gates (`G1 = PASS`, `G2 = PASS`, `G3 = PASS`): `77.70x` lower `WikiText-2` prose KL (`p_Holm = 0.000806 < 0.01`, max `Arm D` KL `0.004879 <= 0.005 nats`), `+2.97 pp` higher unseen sealed holdout than unconstrained additive `Arm A` (`60.31%` vs. `57.34%`, winning `5/5` seeds and passing **both** Phase 2's `2.0 pp` margin and Phase 1's dynamically parsed `1.0 pp` margin), `+18.80 pp` unseen holdout gain over unedited base (`41.51%`, `p_Holm = 1.739e-5`), `4/4` geodesic retraction rescues at $\gamma = 1/2$, `7.629e-6 = 2^-17 < 1e-5` unit-sphere shell norm error, `30/30` (`100.0%`) live poison blocks, and `0.0` exact FP32 drift across all `36/36` rollbacks.
- **Canonical On-Disk Certificate:** `so_d_geodesic_retraction_certificate.json` (`certificate_sha256: ef1cda74445458021f148cafc1a9f618eac909122da876143d73a9316ed56146`, `payload_sha256: 9c96cf0ac5fd8aec6c9aec25b264059da94e4a14cc7dde51d0b04c41ee6179a6`), pinned directly inside `verify_so_d_geodesic_retraction.py` (`--require-pinned`) and live-binding all six committed study artifacts on disk (`0` unbound external hashes) while uniquely parsing all `8` locked decision-gate thresholds (including `KL <= 0.005 nats`) directly from the hashed protocol Markdown files.

## Methodological Disclosures & Verification Scope

- **`G1` Margin Change (`1.0 pp -> 2.0 pp`) & Protocol Clarification Provenance:** Phase 2 widened the `G1` holdout parity margin from `1.0 pp` (Phase 1) to `2.0 pp` (Phase 2). `preregistration_phase2_geodesic_retraction.md` is a post-audit clarified protocol record (original pre-amendment lock SHA-256 `d505a3219240985cf66f508253a8c08eab3802f1cf087d1de09abfd62a1a0d84`) containing zero realized Phase 2 outcomes. The verifier dynamically checks `passes_stricter_phase1_g1_margin = true` using Phase 1's parsed `1.0 pp` threshold.
- **Phase 2 Seed Overlap (`0–2`) & Fresh Unseen Subset (`3–4`):** Phase 2 seeds `[0, 1, 2, 3, 4]` reuse seeds `0–2` from Phase 1 alongside `2` newly added unseen seeds `3–4`, so Phase 2 is a partially dependent extension rather than a fresh independent `n = 5` replication. The verifier filters fresh seeds explicitly by seed ID (`seed not in {0, 1, 2}`); on seeds `3–4` alone, `Arm D` achieved `59.24%` vs. `Arm A` `55.73%` (`+3.52 pp`) and `Base` `39.84%` (`+19.40 pp`) with `72.83x` lower prose KL.
- **Arm-D Acceptance Gate Scope:** The `KL <= 0.005 nats` cumulative acceptance gate applies selectively to `Arm D` (coupled with geodesic retraction and rollback), whereas `Arm A/B/C` commit all rounds under the matched `92,160`-parameter budget as baselines.
- **What `--check --require-pinned` Certifies:** Certifies pure-$\mathbb{Q}$ oracle AST purity, exact-$\mathbb{Q}$ Cayley identities, and end-to-end cryptographic/statistical/gate consistency of the committed on-disk study bundle against `PINNED_CERTIFICATE_SHA256` (it does not re-execute GPU model training).

## Hardware Provenance, Energy Policy, & CI Coverage

- Empirical measurements were recorded on an NVIDIA GeForce RTX 3080 Laptop GPU in deterministic FP32 mode (`allow_tf32 = False`, `CUBLAS_WORKSPACE_CONFIG=:4096:8`, `TORCH_USE_DETERMINISTIC_ALGORITHMS=1`).
- **Zero Uncontrolled Laptop Energy Claims:** Both determinism receipts (`phase1_hardware_determinism.json`, `phase2_hardware_determinism.json`) omit NVML power fields and set `energy_power_status = "UNCONTROLLED_LAPTOP_NOT_CLAIMED"`. The verifier enforces a fail-closed recursive energy-claim guard across all JSON keys and string values (including `RAPL`, `NVML`, `nvidia-smi`, `tok/J`, `mAh`, and SI power/energy units).
- **CI Coverage Path:** All pure-stdlib verification and adversarial R5 checks execute CPU-only with zero third-party dependencies via `tests/test_so_d_geodesic_retraction.py` (discovered automatically by `tests/run_all.py`).

## Quick Verification (3-Mode Isolated `-I` Parity)

```bash
for flags in "-I -B" "-I -O -B" "-I -B -W error"; do
  CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 python3 ${flags} \
    studies/so_d_geodesic_retraction/verify_so_d_geodesic_retraction.py \
    --check studies/so_d_geodesic_retraction/so_d_geodesic_retraction_certificate.json --require-pinned
  CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 python3 ${flags} \
    tests/test_so_d_geodesic_retraction.py -v
done
```
