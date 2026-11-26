# Multimodal Historical Exact-Operator Interposition Study

Self-contained, offline-verifiable empirical study testing seven exact-operator hypotheses (`H20-A1`–`H20-C2`) on an anonymized, 100% passive 65-minute pre-dawn open-room 5-modality sensor window (`3,898` synchronized 1 Hz multi-modal invariant frames; honest scorecard: **`2 CONFIRMED`, `4 PARTIAL`, `1 FALSIFIED`**).

## Bundle Contents

| File | Role |
|---|---|
| [ANALYSIS_PLAN.md](ANALYSIS_PLAN.md) | Frozen public analysis plan, kill gates, privacy-by-design rules, and energy-policy scope (committed post-acquisition, not a pre-data timestamped registration) |
| [open_room_interposition_results.json](open_room_interposition_results.json) | Anonymized aggregate summary JSON (`3,898` frames, `B = 2,500` nulls, dual SHA-256 self-bound to `ANALYSIS_PLAN.md` and raw-bytes pinned) |
| [verify_multimodal_interposition.py](verify_multimodal_interposition.py) | Pure-stdlib fail-closed verifier (`--check-bundle`, `--selftest`, `--check <json>`) |
| [REPORT.md](REPORT.md) | Full empirical summary with honest Law-4 scorecard (`2 CONFIRMED`, `4 PARTIAL`, `1 FALSIFIED`) |

## Provenance, Shutdown Tail, & Privacy Transparency

- **100% Passive & Zero Raw Media:** Zero video frames, zero images, zero raw audio waveforms, zero Wi-Fi SSIDs, and zero MAC/BSSID identifiers were written to disk or committed here. All streams were reduced in memory to anonymized mathematical invariants.
- **Shutdown Tail Disclosure (`+5.1 s` Drain):** Acquisition triggered automatic shutdown at `HARD_STOP_EPOCH = 1795693500` (`05:45:00 CST`), with final subprocess drain finishing `+5.1 s` later at `1795693505.109` (`05:45:05.1 CST`, recorded honestly as `stopped_before_hard_stop = false`), well within (`114.9 s` ahead of) the `1795693620` (`05:47:00 CST`) shutoff ceiling.
- **Strict Default-Ladder Grading (`H20-C2 = PARTIAL`):** `H20-C2` is graded strictly against the pre-specified default `70/78/85 deg C` hysteresis ladder (`4.50x < 5.0x` gate -> `PARTIAL`), while exploratory operating-band `91/93/95 deg C` sensitivity profiles (`5.63x` and `12.57x`) are preserved transparently without overriding the primary kill gate.
- **Energy & Power Guard Policy (`UNCONTROLLED_LAPTOP_NOT_CLAIMED`):** Zero uncontrolled laptop wattage or per-token energy claims are read, logged, or permitted in verified JSON artifacts. The verifier enforces NFKC/NFKD/casefold normalization, non-ASCII homoglyph rejection (except micro sign), unit/metric value and key guards (including hex-prefixed magnitudes and `hp`), plus host-path/MAC/email leak guards. Thermal/atomic energy units (`kcal`, `BTU`, `eV`) and spelled-out numbers (`forty-five watts`) remain out of scope for the regex value guard by design.

## Verifier Modes: `--check-bundle` vs. `--check` vs. `--selftest`

- **`--check-bundle [DIR]` (default):** Verifies the **entire committed on-disk study bundle** — raw file bytes SHA-256 of `ANALYSIS_PLAN.md`, raw file bytes SHA-256 of `open_room_interposition_results.json` (blocking whitespace/key-order/duplicate-key rewrites), strict duplicate-key & finite-float JSON parsing, exact pure-$\mathbb{Z}/\mathbb{Q}$ operator witnesses, Holm–Bonferroni & Law-4 verdict re-derivation, and pinned canonical `results_sha256`.
- **`--check PATH`:** Standalone schema, duplicate-key, leak/energy guard, exact-operator, Holm–Bonferroni, Law-4 verdict, and internal `payload_sha256`/`results_sha256` verification of any results JSON file (does **not** enforce the committed bundle's pinned raw-bytes digest).
- **`--selftest`:** Validates an in-memory deterministic contract fixture without touching disk.

## Reproducibility & Offline Verification Commands

Run from the repository root with zero external dependencies across all three isolated Python modes (`-I -B`, `-I -O -B`, `-I -B -W error`):

```bash
# 1. Verify committed ANALYSIS_PLAN.md + open_room_interposition_results.json bundle (raw bytes + schema)
python3 -I -B studies/multimodal_historical_interposition/verify_multimodal_interposition.py --check-bundle
python3 -I -O -B studies/multimodal_historical_interposition/verify_multimodal_interposition.py --check-bundle
python3 -I -B -W error studies/multimodal_historical_interposition/verify_multimodal_interposition.py --check-bundle

# 2. Run standalone pure-stdlib contract selftest
python3 -I -B studies/multimodal_historical_interposition/verify_multimodal_interposition.py --selftest

# 3. Run full R5 adversarial, AST zero-float, & boundary test suite
python3 -I -B tests/test_study_multimodal_historical_interposition.py

# 4. Run full repository test & audit suite
python3 -I -B tests/run_all.py

# 5. Run R5 refusal-site mutation audit (100.0% kill rate)
python3 -I -B -c "import sys; sys.path.insert(0, '.'); from aletheia.cli import main; raise SystemExit(main(['mutate', 'studies/multimodal_historical_interposition/verify_multimodal_interposition.py', '--work-root', '.', '--workers', '4', '--timeout', '25', '--max-mutants', '0', '--test-cmd', 'python3 -I -B tests/test_study_multimodal_historical_interposition.py']))"

# 6. Run R1-R4 hygiene, safety, and strict-ancestor audit
python3 -I -B -c "import sys; sys.path.insert(0, '.'); from aletheia.cli import main; raise SystemExit(main(['audit-check', 'studies/multimodal_historical_interposition', '--strict-ancestors', '--safety-scan', '--strict-unseeded', '--scripts', 'verify_multimodal_interposition.py']))"
```
