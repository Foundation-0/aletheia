# Track S124 (`EXP-Q30a`) — Pure-$\mathbb{Q}$ A/A Noise-Floor, Looped-Roofline & `HoloSphere-V3` L3 Ceiling Oracle

Locked to sanitized in-tree `PREREG-W14` (`../preregistrations/PREREG_WAVE14_INF_OPT_BAREMETAL.md`, `SHA-256: 4994ae816d852856cfb4c32713c1ca8aea08a2be4abf1f8186d3bd531f0d604d`; original pre-sanitization lock `871900e5d6c860ac159f43ca6b4767e7c128d0b4f7748edf788d56e9cb535d3e`). Pure Python stdlib (`0` floats / `0` float literals in AST, `certificate_sha256: 7e0724b4bff0e7567bec4285f7e0996027e7aac10d05ecf8da57cb5a04a5b6e9`, `47/47 = 100.0%` `aletheia mutate`, 3-mode `-I` parity).

## Verification
```bash
python3 -I -B verify_s124_aa_roofline_l3.py --check
python3 -I -B test_s124_aa_roofline_l3_r5.py
```
