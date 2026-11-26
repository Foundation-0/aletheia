# Multi-Tokenizer / Protocol / Non-English Density Engine & 3-Node M1 Max Handoff Pack (`18/18` Pure-`Init` Lean `4.36.0`)

Self-contained Aletheia evidence bundle combining live offline CPU Rust-`tokenizers` measurements (`Qwen2.5-0.5B` & `SmolLM2-360M`), exact pure-$\mathbb{Z}/\mathbb{Q}$ protocol/vocabulary/handoff verification, and **`18/18` universally quantified pure-`Init` Lean `4.36.0` theorems** (`0` imports, `0` warnings, `1` `[]` + `17` `[propext]`, `0` `Quot.sound`, `0` `Classical.choice`, `0` `sorryAx`):

1. **Pillar 1 — Live Multi-Tokenizer & Cross-Language Density Audit:** Captures `4` lossless renderings of `Moissanite-Labs/abios` `review-fix-verify-merge.jsonl` (`ABIOS/3` full saves `41.29%` on `Qwen2.5` / `41.11%` on `SmolLM2` vs Markdown; `N* = 3` break-even vs `SYM-2P`), exposes `2-3` BPE token fragmentation across all `8` Aletheia calculus glyphs (`46.88%`/`48.48%` collapse when reserved), proves the **Vocabulary-Tax × Translation-Loss Compounding Law** on `12` classical Arabic scientific treatises + `148` bilingual pairs (`2.74x-6.10x` English overhead at `k=1` and `404x-899x` at `k=2` on cross-discipline edges), quantifies the `490858/1149000 = 0.4272` representation-vs-readout gauge gap, and fixes `3` lossless round-trip bugs in `wire_lists.py`.
2. **Pillar 2 — Reserved Protocol-Token Surgery & `DPI` Safety Bounds:** Computes exact tied/untied parameter overhead for `K in {16, 32, 64, 128}` reserved tokens (`N* = 2-7` turns), proves mean-norm initialization keeps `DPI` concentration identically `1` while a single `16*M` spike drives `~16x` concentration, and verifies exact `S94` Householder reflection isometry (`delta = 0`).
3. **Pillar 3 — Preregistered 3-Node `aletheia handoff` Pack (`M1-H1..M1-H3`, `EDGE-H1`):** Pins `4` canonical SHA-256 zero-float handoff manifests for `64 GiB` M1 Max (`Inkling-2-Mini`, `weft` E8 + `weft-loom` E11c, `Bonsai 2.5 27B` vs `FP16` dual-load `62.73 <= 64 GB` with `+3.00 GB` OS budget) and `16 GiB` CPU edge (`exyber` + `nullmodem` `8.6732x` LAN speedup at `4,096` tok), with explicit execution-phase drift-ratio kill gates (`M1-H1`: `Delta_3 / Delta_1_control <= 2` and `Delta_3 <= 5e-2`).
4. **Pillar 4 — Pure-`Init` Lean `4.36.0` Companion (`TokenpageAbiosHandoff.lean`):** `18/18` universal theorems verified by field-complete `SEC`/`FR0`/`FR1` replay (`574/574` single-leaf tamper rejections), R12 static + scrubbed-env live `lean --stdin` verifier, and zero-skip R5 test suite.

## Honest Scope & Novelty Classification (`N1`)

- **Novelty Classification:** **`N1`** (`n2_claims = 0`; explicit `N0` credit to `Moissanite-Labs/{tokenpage,abios,scry}`, `Foundation-0/bayt-al-hikma`, and prior tracks). Handoff manifests are preregistered zero-float specifications, not live remote execution receipts.

## Files

- `TokenpageAbiosHandoff.lean` — `18/18` universal pure-`Init` Lean `4.36.0` theorems (`0` external imports, `0` warnings)
- `lean-toolchain` / `lakefile.toml` — Pinned `leanprover/lean4:v4.36.0` build specification
- `s100_live_tokenizer_capture.py` / `s100_tokenizer_anchor.json` — Offline CPU tokenizer capture script and frozen anchor (`18,642` bytes)
- `s100_tokenpage_handoff_oracle.py` — Pure-$\mathbb{Z}/\mathbb{Q}$ exact oracle and canonical certificate builder
- `verify_s100_tokenpage_handoff.py` — Zone-B hardened verifier, `574/574` field-complete `SEC`/`FR0`/`FR1` auditor, R12 static Lean scanner, and live scrubbed `lean --stdin` kernel verifier
- `s100_tokenpage_handoff_audit.py` — `*_audit.py` CLI wrapper for `evidence-tracks` CI discovery
- `s100_tokenpage_handoff_certificate.json` — Committed canonical zero-float certificate (`21,363` bytes)
- `test_s100_tokenpage_handoff_r5.py` — Assertion-free verification, tamper, Zone-B, R12 Lean gate, and live Lean test suite (`0` skips)
- `REPORT.md` — Complete 4-pillar audit ledger and file manifest

## Quickstart

```bash
# Verify certificate, full deterministic replay, and live Lean 4.36.0 kernel (18/18 theorems)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s100_tokenpage_handoff.py --check s100_tokenpage_handoff_certificate.json --json

# Run CI audit wrapper
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B s100_tokenpage_handoff_audit.py --check s100_tokenpage_handoff_certificate.json

# Run full test suite across all three isolated Python modes
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B test_s100_tokenpage_handoff_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -O -B test_s100_tokenpage_handoff_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B -W error test_s100_tokenpage_handoff_r5.py
```
