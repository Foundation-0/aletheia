# Multimodal Historical Exact-Operator Interposition Study

Self-contained, offline-verifiable empirical study testing seven exact-operator hypotheses (`H20-A1`–`H20-C2`) on an anonymized, 100% passive 65-minute pre-dawn open-room 5-modality sensor window (`3,898` synchronized 1 Hz multi-modal invariant frames; honest scorecard: **`2 CONFIRMED`, `4 PARTIAL`, `1 FALSIFIED`**).

## Bundle Contents

| File | Role |
|---|---|
| [ANALYSIS_PLAN.md](ANALYSIS_PLAN.md) | Frozen public analysis plan, kill gates, privacy-by-design rules, and energy-policy scope (committed post-acquisition, not a pre-data timestamped registration) |
| [open_room_interposition_results.json](open_room_interposition_results.json) | Anonymized aggregate summary JSON (`3,898` frames, `B = 2,500` nulls, dual SHA-256 self-bound to `ANALYSIS_PLAN.md` and raw-bytes pinned) |
| [verify_multimodal_interposition.py](verify_multimodal_interposition.py) | Pure-stdlib fail-closed verifier (`--check-bundle`, `--selftest`, `--check <json>`) |
| [REPORT.md](REPORT.md) | Full empirical summary with honest Law-4 scorecard (`2 CONFIRMED`, `4 PARTIAL`, `1 FALSIFIED`) |

## Provenance, Shutdown Tail, Verification Scope, & Privacy Transparency

- **100% Passive Capture Policy & Zero Raw Media:** Zero video frames, zero images, zero raw audio waveforms, zero Wi-Fi SSIDs, and zero MAC/BSSID identifiers were written to disk or committed here. All streams were reduced in memory to anonymized mathematical invariants (`3,898` synchronized 1 Hz frames for `H20-A2`/`H20-C2`; `3,897` audio-aligned 1 Hz frames for audio-coupled `H20-B1`/`H20-C1`, where `1` frame lacked a synchronized `m3_mic` block). Because no raw sensor trace or capture harness is committed in-tree, `passive_zero_output_enforced = true` (alongside `video_handles_after_close = 0` and `raw_media_files_count = 0`) is a hashed capture-policy self-attestation (zero speaker output, zero active probing) — **not** an ML model run or ML output-invariance proof.
- **Verification Scope & Taxonomy Mapping:** This bundle verifies an anonymized aggregate JSON summary plus exact pure-$\mathbb{Z}/\mathbb{Q}$ operator witnesses (raw 65-minute sensor waveforms/frames are not shipped). Its empirical Law-4 scorecard (`CONFIRMED` / `PARTIAL` / `FALSIFIED`, plus unused `H20-A2` `NULL_STATIC_ROOM`) maps to summary-level empirical verification plus exact-$\mathbb{Q}$ witness replay, not raw-waveform replay or Lean formalization:
  - **`H20-B1` CRT Exemplars & 4-Null Binding:** `89` distinct `(RPM1, RPM2)` pairs were observed in memory; **`8` certified exact-$\mathbb{Q}$ exemplar witnesses** are embedded and re-verified in-repo (`unique_rpm_pairs_count >= len(witnesses)`, pairwise-distinct `(rpm1, rpm2)` pairs), and all four `p_raw_*` null fields are bound to the `CONFIRMED` gate (`< 0.01`).
  - **`H20-C1` Full Pair-Holm & Čech $H^1$ Recomputation:** All `21` pair-level Holm–Bonferroni p-values (`p_circ_holm`, `p_iaaft_holm`), all `5/21` survivor flags/counts, `p_raw`, and all `C(7,3) = 35` Čech $H^1$ lag holonomies (`mean |h| = 18.9143 s`, plus the `10` shipped sample triples) are recomputed directly from the `21` shipped `pair_couplings` entries — failing closed on any discrepancy.
  - **`H20-A2` / `H20-B3` Inertia & `H20-C2` Khipu / Pāṇini Witness Scope:** `H20-A2` (`12x12 = 4x4 + 8x8`) and `H20-B3` (`3x3` active) verify exact non-negative dimension-preserving Sylvester inertia triples from the summary JSON (raw frame/CSD matrices are not shipped). `H20-C2` Pāṇini `C1P` verifies all four monotone `[lo, hi]` interval witnesses (`0 <= lo <= hi < 64`, `0` obstructions), exact bitset compression ratio `16/3`, and positive gap counts on obstructed cross-modal tags (`28` & `26` gaps); Khipu `200/200` (`0` escapes) is an in-memory **summary attestation** (raw per-frame leaves are not shipped; verifier enforces non-negative tamper arithmetic, positive `root_value`, and non-zero 64-hex `root_merkle_sha256`).
- **Shutdown Tail Disclosure (`+5.1 s` Drain):** Acquisition triggered automatic shutdown at `HARD_STOP_EPOCH = 1795693500` (`05:45:00 CST`), with final subprocess drain finishing `+5.1 s` later at `1795693505.109` (`05:45:05.1 CST`, recorded honestly as `stopped_before_hard_stop = false`), well within (`114.9 s` ahead of) the `1795693620` (`05:47:00 CST`) shutoff ceiling.
- **Strict Default-Ladder Grading (`H20-C2 = PARTIAL`):** `H20-C2` is graded strictly against the pre-specified default `70/78/85 deg C` hysteresis ladder (`4.50x < 5.0x` gate -> `PARTIAL`), while exploratory operating-band `91/93/95 deg C` sensitivity profiles (`5.63x` and `12.57x`) are preserved transparently without overriding the primary kill gate.
- **Energy & Power Guard Policy (`UNCONTROLLED_LAPTOP_NOT_CLAIMED`) & Symlink/FIFO Safety:** Zero uncontrolled laptop wattage or per-token energy claims are read, logged, or permitted in verified JSON artifacts. The verifier enforces linear-time $O(N)$ NFKC/NFKD/casefold normalization, non-ASCII homoglyph rejection (except micro sign), unit/metric value and key guards (including hex-prefixed magnitudes, `hp`, `J/token`, `W/token`, spelled-out numbers like `forty-five watts`, `energy: 12`, and `nvml_power`), host-path/MAC/email leak guards, and strict `O_NOFOLLOW | O_NONBLOCK` + `S_ISREG` + byte-cap file loading (refusing symlinks and FIFOs). Thermal/atomic energy units (`kcal`, `BTU`, `eV`) remain out of scope for the regex value guard by design.

## Verifier Modes: `--check-bundle` vs. `--check` vs. `--selftest`

- **`--check-bundle [DIR]` (default):** Verifies the **entire committed on-disk study bundle** — raw file bytes SHA-256 of `ANALYSIS_PLAN.md`, raw file bytes SHA-256 of `open_room_interposition_results.json` (blocking whitespace/key-order/duplicate-key rewrites), strict duplicate-key & finite-float JSON parsing, exact pure-$\mathbb{Z}/\mathbb{Q}$ operator witnesses, `H20-B1` four-null-test binding, full `H20-C1` pair-Holm & all-`C(k,3)` Čech $H^1$ lag-holonomy recomputation, family Holm–Bonferroni & Law-4 verdict re-derivation, and pinned canonical `results_sha256`.
- **`--check PATH`:** Standalone schema, duplicate-key, leak/energy guard, exact-operator, `H20-B1` four-null-test, full `H20-C1` pair-Holm & lag-holonomy recomputation, family Holm–Bonferroni, Law-4 verdict, and internal `payload_sha256`/`results_sha256` verification of any results JSON file (does **not** enforce the committed bundle's pinned raw-bytes digest).
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

# 5. Run R5 refusal-site mutation audit (100.0% kill rate, default & --guards require_ok)
python3 -I -B -c "import sys; sys.path.insert(0, '.'); from aletheia.cli import main; raise SystemExit(main(['mutate', 'studies/multimodal_historical_interposition/verify_multimodal_interposition.py', '--work-root', '.', '--add-cwd', '--guards', 'require_ok', '--workers', '4', '--timeout', '25', '--max-mutants', '0', '--test-cmd', 'python3 -I -B tests/test_study_multimodal_historical_interposition.py']))"

# 6. Run R1-R4 hygiene, safety, and strict-ancestor audit
python3 -I -B -c "import sys; sys.path.insert(0, '.'); from aletheia.cli import main; raise SystemExit(main(['audit-check', 'studies/multimodal_historical_interposition', '--strict-ancestors', '--safety-scan', '--strict-unseeded', '--scripts', 'verify_multimodal_interposition.py']))"
```
