# Track S21c: Cross-Org `aska-physical` Zone-B, `NaN`-Swallowing & `-O` Bare-`assert` Tomography

Self-contained zero-float ($\mathbb{Z}/\mathbb{Q}$) static AST tomography and live-reproduction evidence bundle auditing all `9` public engineering repositories of `aska-physical` across four orthogonal verification-trust defect families:

1. **`F1_BARE_ASSERT_O_STRIP` (`8/9` repos, `86` sites):** Bare `assert` statements on verification paths silently stripped under `python3 -O`.
2. **`F2_NAN_SWALLOW_MAXMIN` (`8/9` repos, `76` sites / `29` constant-first):** Unchecked Python `max(c, NaN) == c` / `min(c, NaN) == c` calls converting `NaN` demands, capacities, or margins into finite passing bounds.
3. **`F3_ZONEB_CERT_DICT_EQ` (`9/9` repos, `11` sites):** Parsed-dict equality accepting `ZB06` (`bool`/`int` coercion), `ZB07` (duplicate JSON keys), `ZB08` (`.0` float coercion), `ZB10` (CRLF), and `ZB14` (symlinked certificates).
4. **`F4_ZONEB_UNGUARDED_JSON_IO` (`9/9` repos, `17` sites):** Unguarded JSON parsing crashing with raw Python tracebacks on `ZB03` (oversized integers), `ZB15` (directories), and `ZB16` (invalid UTF-8 / truncated JSON).

Across all `9 × 4 = 36` repo-family cells at the pinned Nov 11–17 snapshot, **`34/36` (`17/18`)** were exposed and only `2/36` (`1/18`) were clean; on live `main` after the Nov 22–24 remediation commits the residual is **`9/36` (upper bound)** — this track is a dated historical audit, not a live-main claim. Exhaustive search over all $2^3 - 1 = 7$ subsets of three pure-stdlib primitives (`require_no_assert`, `strict_finite_clamp`, `verify_canonical_cert_bytes`) certifies a unique minimal hitting set of size `3` closing `34/34` (`100.0%`) exposures (`0/36` residual), verified live on the `7`-snippet `MINIMAL_REPRO_CORPUS`.

## Quick Verification

```bash
cd evidence/track-s21c-aska-physical-zone-b-tomography

# 1. Zero-skip R5 suite across all three isolated R4 modes
python3 -I -B test_aska_zoneb_tomography_r5.py
python3 -I -O -B test_aska_zoneb_tomography_r5.py
python3 -I -B -W error test_aska_zoneb_tomography_r5.py

# 2. Byte-exact standalone certificate replay & fail-closed audit check
python3 -I -B aska_zoneb_tomography_audit.py --standalone --json | cmp -s - aska_zoneb_tomography_certificate.json
python3 -I -B aska_zoneb_tomography_audit.py --check aska_zoneb_tomography_certificate.json
```

See [`ASKA_ZONEB_TOMOGRAPHY_REPORT.md`](ASKA_ZONEB_TOMOGRAPHY_REPORT.md) for the exact 9-repo exposure matrix, minimal live defect witnesses, Law-2b micro-shim proof, and frozen SHA-256 manifest.
