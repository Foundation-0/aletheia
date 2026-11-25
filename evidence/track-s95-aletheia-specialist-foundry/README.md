# Track S95: Local Aletheia Specialist Foundry & Live RTX 3080 Beyond-LoRA Matched-Budget Showdown (`16/16` Pure-`Init` Lean `4.36.0` Universal Theorems)

Self-contained Aletheia evidence bundle certifying a live bare-metal RTX 3080 (`8 GiB`) Zone-B matched-parameter-budget (`8,798,208` exact trainable parameters across all `168` target projections) `3 × 3` specialist showdown on `Qwen/Qwen2.5-0.5B` (`apache-2.0`), wrapped in a mandatory fail-closed Law-3 (`⫩`) deterministic verification router (`aletheia_specialist_router.py`), pure-$\mathbb{Z}/\mathbb{Q}$ zero-float certificate replay (`s95_specialist_foundry_oracle.py`, `verify_s95_specialist_foundry.py`), and **`16/16` universally quantified (`∀`) pure-`Init` `Lean 4.36.0` kernel-checked theorems** (`SpecialistFoundryCerts.lean`, `0` external imports, `0` warnings, `1 [] + 3 [propext] + 12 [propext, Quot.sound]`, `0` `Classical.choice`, `0` `sorryAx`, `WEIGHTS = 0` in repo):

1. **Pillar 1 — Strictly Disjoint Datasets, Matched Budget & Zone-B Hardware Provenance:** `847` strictly disjoint train/eval rows (`553,151` B `< 5 MiB`, zero overlap across `Scribe`, `Weaver`, `Prover`), exact parameter parity $P = 24 \cdot 16 \cdot (2(896+896) + 2(896+128) + 3(896+4864)) = 8{,}798{,}208$, and pinned `mlos stamp-run --zone B --require-gpu` hardware receipt (`mlos_zone_b_receipt.json`, `clean_hardware_run = true`, `exit_code = 0`, `anomalies = []`).
2. **Pillar 2 — Live RTX 3080 `3 × 3` Matched-Budget Beyond-LoRA Showdown (`standard_lora` vs. `blockh4_butterfly` vs. `privsparse_ortho`):** Base `Qwen/Qwen2.5-0.5B` scores `0/157` (`0.00%`) across all Law-3 gates while fine-tuned winners reach `138/157` (`87.90%`) with zero false accepts (`Scribe standard_lora 48/48`, `Weaver privsparse_ortho 41/60 pathway / 15/15 CS-03 / 60/60 JSON`, `Prover standard_lora 5/24 live Lean 4.36.0 + 25/25 R10+ audit`). Full-rank orthogonal `blockh4_butterfly` cuts forgetting-to-learning ratio `F/L` by **`8.74×–22.58×`** vs. LoRA (`0.0606` Scribe, `0.0108` Weaver, `0.0251` Prover with lower Prover NLL `1.3562` vs. `1.6570`), while documenting three explicit Law-4 failure modes (`FM-01` Householder privileged-basis drift, `FM-02` unfused `25–32×` wall-clock slowdown & `bf16` `<0.5 ULP` merge zeroing, `FM-03` `0.5B` multi-step tactic ceiling).
3. **Pillar 3 — Mandatory Fail-Closed Law-3 (`⫩`) Deterministic Router:** `aletheia_specialist_router.py` enforces deterministic schema, arithmetic, CS-03 smuggling, and live Lean kernel verification so zero unverified micro-model output passes downstream (`0` false accepts, clean escalation on rejection).
4. **Pillar 4 — `thinkingmachines/Inkling-2-Mini` (`inkling2_loop`) Scaling Transfer:** Exact zero-padding `BlockH4` divisibility (`2304`, `1152`), `2×` effective depth reuse (`48 / 24 = 2`, `3×` loop-core adapter leverage), and honest `20 GB` NVFP4 vs. `8 GiB` RTX 3080 hardware roofline (`5/2×`).
5. **Pillar 5 — `16/16` Pure-`Init` `Lean 4.36.0` Companion & Complete Zone-B / R12 Hardening:** All `476/476` (`100.0%`) single-leaf re-signed payload tampers rejected across `SEC`, `FR0`, AND `FR1` (`1,428/1,428`), `82/82` 4-surface `zone_b_fuzzer`, `244/244` (`100.0%`) live `aletheia-fast-mutate`, `74/74` (`100.0%`) whole-file DFS AST `BoolOp`, `0`-skip isolated `-I` + Lean-less CI + RO-dir parity, `max_novelty_tier = N1`, `n2_claims_count = 0`.

## Quick Verification

```bash
cd evidence/track-s95-aletheia-specialist-foundry

# 1. Zero-skip R5 suite across all 3 isolated R4 modes
python3 -I -B test_s95_specialist_foundry_r5.py
python3 -I -O -B test_s95_specialist_foundry_r5.py
python3 -I -B -W error test_s95_specialist_foundry_r5.py

# 2. Standalone byte-exact certificate replay, CI audit check & pinned artifacts
python3 -I -B s95_specialist_foundry_audit.py --standalone | cmp -s - s95_specialist_foundry_certificate.json
python3 -I -B s95_specialist_foundry_audit.py --check s95_specialist_foundry_certificate.json --json
python3 -I -B s95_specialist_foundry_audit.py --verify-artifacts . --json

# 3. Live R12 static + scrubbed Lean 4.36.0 kernel verification (16/16 universal theorems)
python3 -I -B s95_specialist_foundry_audit.py --verify-lean SpecialistFoundryCerts.lean --json
```

See [`REPORT.md`](REPORT.md) for the complete empirical showdown tables, failure-mode analyses, theorem inventory, and frozen SHA-256 manifest.
