# Beyond-LoRA Epistemic-Native Adapters & `Inkling-2-Mini` (`inkling2_loop`) Exact Theory (`20/20` Pure-`Init` Lean `4.36.0`)

Self-contained Aletheia evidence bundle unifying exact pure-$\mathbb{Z}/\mathbb{Q}$ analysis of LoRA's algebraic bottlenecks, epistemic-native Beyond-LoRA adapters, `Inkling-2-Mini` (`inkling2_loop`) 3-pass looped-core mechanics, per-pass quantization-noise accumulation, and hardware rooflines with **`20/20` pure-`Init` Lean `4.36.0` theorems** (`19` universal `∀` theorems + `1` 18-conjunct ground witness suite; `0` external imports, `0` warnings, `6` `[]` + `14` `[propext]`, `0` `Quot.sound`, `0` `Classical.choice`, `0` `sorryAx`):

1. **Pillar 1 — Standard LoRA's Three Exact Mathematical Bottlenecks:** Proves exact rank starvation (`Qwen2.5-0.5B` `896×896 r=16` leaves `880/896 = 55/56 = 98.21%` unreachable), $GL_r$ gauge redundancy (`d_eff = r(m+n) - r^2 < P_raw`, `11/12` at `r=128`, `2/3` at full rank `r=512`), privileged-basis commutator smearing ($\|[H_4, D]\|_F^2 = 54 > 0$ under anisotropy vs `0` under isotropy), and `1:1` unprojected forgetting/learning unit conservation (`229/5 KB`).
2. **Pillar 2 — Three Epistemic-Native Beyond-LoRA Adapters, Law-5 Obstructions & `ButterflyHead-8+8` Preregistration:**
   - Matched-budget exact showdown ($d=8, r=2 \implies P=32$): `Aletheia-BlockH4-Butterfly` reaches full rank **`8`** (`4×` LoRA rank `2`, $H_{\mathrm{blk}}^\top H_{\mathrm{blk}} = 4 I_8$), proves the exact Law-5 block-diagonal locality obstruction (`0` unpermuted cross-block energy) and `QuadSnake` stride-interleave cure (`0 -> 660` preserving rank `8`); `Aletheia-PrivSparse-Householder` proves exact orthogonal involution ($Q^\top Q = Q^2 = I_4$, $\det Q = -1$, $\kappa_2 = 1$); `Aletheia-NullSpace-Projected` proves exact zero base-task forgetting (`46 -> 0`) with retained energy `11 > 0` alongside its Law-5 full-rank saturation wall (`0`).
   - Exact pure-$\mathbb{Q}$ formalization of the `S95` bf16 `< ½-ULP` (`1/256`) merge annihilation figures (`407/500 = 81.40%` Butterfly vs `873/10000 = 8.73%` LoRA, ratio `8140/873 = 9.3242×`; external collab report, not shipped/reproduced here), budget-matched `ButterflyHead-8+8` (`14,336 + 14,336 = 28,672` params/proj on `d=896`, `10×` decoupled LRs `3e-4`/`3e-3`), optional `S104` rank-2 Kronecker head (`3,616` params, `448/113 = 3.9646×` compression), and preregistered PASS/KILL gates.
3. **Pillar 3 — `Inkling-2-Mini` (`inkling2_loop`) Architecture, Per-Pass Quantization-Noise Separation & Roofline:** Verifies exact `24 -> 48` looped depth (`6 + 3×12 + 6`, `2×` depth reuse, `3×` loop-core adapter leverage, `128/8` MoE sparsity), proves exact per-pass quantization-noise amplification $G_3(\rho) = 1 + \rho + \rho^2$ vs initial-error contraction $\rho^3$ (`G_3(1/4) = 21/16 = 1.3125 <= 2` vs contractive `rho = 3/4`: `rho^3 = 27/64 < 1` yet `G_3 = 37/16 = 2.3125 > 2`, golden-ratio bracket `3/5 -> 49/25 < 2` vs `5/8 -> 129/64 > 2`), preregisters the falsifiable `M1-H1` kill gate ($\Delta_3 / \Delta_{1,\mathrm{ctrl}} \le 2 \land \Delta_3 \le 1/20$), and proves honest `8 GiB` (`20 > 8`, `12 GB` overflow, tiered `32/128` hot-expert streaming feasible) vs `32 GiB` rooflines.
4. **Pillar 4 — Pure-`Init` Lean `4.36.0` Companion & R12/R13 Verification Gate:** `BeyondLoraAndInklingLoop.lean` (`20/20` theorems) verified by field-complete `SEC`/`FR0`/`FR1` replay (`332/332` scalar leaves × `3` surfaces = `996/996` rejected), `O(1)` `in_ident` R12 static Lean scanner + live allowlist-scrubbed `lean --stdin` kernel verifier, and zero-skip R5 test suite.

## Honest Scope & Novelty Classification (`N1`)

- **Novelty Classification:** **`N1`** (`n2_claims = 0`). Standard LoRA, Monarch/Butterfly structured matrices, Householder reflections, nullspace continual-learning projection, and `Inkling-2-Mini` are established prior art (`N0`); this bundle's contribution is a reproducible zero-float pure-$\mathbb{Z}/\mathbb{Q}$ oracle, fail-closed Zone-B/R12 verifier, and `20`-theorem pure-`Init` Lean `4.36.0` formalization unifying those laws under strict Law-4/Law-5 honesty.

## Files

- `BeyondLoraAndInklingLoop.lean` — `20/20` pure-`Init` Lean `4.36.0` theorems (`0` external imports, `0` warnings)
- `lean-toolchain` / `lakefile.toml` — Pinned `leanprover/lean4:v4.36.0` build specification
- `s96_beyond_lora_inkling_oracle.py` — Pure-$\mathbb{Z}/\mathbb{Q}$ exact oracle and canonical zero-aliasing certificate builder
- `verify_s96_beyond_lora_inkling.py` — Zone-B hardened standalone verifier, field-complete `SEC`/`FR0`/`FR1` auditor, `O(1)` `in_ident` R12 static Lean scanner, and live scrubbed `lean --stdin` kernel verifier
- `s96_beyond_lora_inkling_audit.py` — `*_audit.py` CLI wrapper for `evidence-tracks` CI discovery
- `s96_beyond_lora_inkling_certificate.json` — Committed canonical zero-float certificate (`11,179` bytes)
- `test_s96_r5.py` — Assertion-free verification, tamper, Zone-B, R12 Lean gate, and dual-mode live/CI test suite (`0` skips)
- `REPORT.md` — Complete 4-pillar technical report, verbatim `20/20` theorem index, and 7-companion-file SHA-256 manifest

## Quickstart

```bash
# Verify certificate, full deterministic replay, and live Lean 4.36.0 kernel (20/20 theorems)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s96_beyond_lora_inkling.py --check s96_beyond_lora_inkling_certificate.json --json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s96_beyond_lora_inkling.py --verify-lean BeyondLoraAndInklingLoop.lean --json

# Run CI audit wrapper
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B s96_beyond_lora_inkling_audit.py --check s96_beyond_lora_inkling_certificate.json

# Run full test suite across all three isolated Python modes
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B test_s96_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -O -B test_s96_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B -W error test_s96_r5.py
```
