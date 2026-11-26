# Verified Pure-$\mathbb{Q}$ & Empirical Studies: Tracks `S121`, `S122`, `S123`, `S124`, and `S127`

This bundle collects five self-contained, pure-Python exact-rational (`int`/`Fraction`) verification studies and companion benchmark records under `studies/tracks_s121_s124_s127/`. Every core verifier and its R5 adversarial test suite runs on stock Python 3 stdlib (`0` third-party dependencies, `0` bare `assert`s, `0` skips across `-I -B`, `-I -O -B`, and `-I -B -W error`).

## Study Index & Canonical Certificate Bindings

| Track | Subdirectory | Core Exact-$\mathbb{Q}$ Oracle & Key Results | Canonical SHA-256 Binding |
| :--- | :--- | :--- | :--- |
| **`S121`** | `track_s121_loopcd_platosphere/` | `verify_loopcd_sphere_geometry.py` — Spherical chord self-damping gap $\tan\frac{\pi-\theta}{2}-\tan\alpha = \frac{1+s^2}{s(1+(1+2\omega)s^2)} > 0$, palindromic Strang BCH quadratic cancellation in $\mathbb{H}_{\mathbb{Q}}/SU(2)$, acute-ball denominator floor $81/625 > 0$, plus live RTX 3080 Zone-B record (`W11-A1` `48.65x–173.23x` closer to right-ordered Strang BCH, `W11-A2` `L=3/4` `-0.3365/-0.2005` BPB, falsified `W11-B3 SphereMap` `-6.69 pp`). | `payload_sha256`: `373ff4d100e0ad7f6e71160b5bc557fb51ad52165f1d907a4fd3f95d3a35142f` |
| **`S122`** | `track_s122_xpi_gegenbauer/` | `verify_xpi_gegenbauer_attention.py` — Exact spherical multipole / Gegenbauer vs. monomial attention conditioning, Möbius north-pole slope (`239x` / `280x` slack), and exact unit-volume vs. unit-radius Zador quantization constant bounds. | `certificate_sha256`: `16d2d039358dcdee1e1a85e9211603c48a3a1a808c1ba2129d95f3b15fd04ba3` |
| **`S123`** | `track_s123_sfast_state_transport/` | `verify_state_transport_geometry.py` — `100.0%` exact $O(1)$ `S_fast` Woodbury rank-1 state handoff, query-aware low-rank denoising, OLS vs. Frobenius shrinkage, and `W14-OBS-1` non-abelian $SO(3)$ / $A_5$ handedness anti-homomorphism (`100.0%` vs. `32.00% = 64/200` `rev(P) == P` prefixes). | `certificate_sha256`: `00022833acb4cdee03074af058860ff02bdd133b8a7bb493eff1ac46707abdbf` |
| **`S124`** | `track_s124_aa_roofline_l3/` | `verify_s124_aa_roofline_l3.py` — Exact $S_3$ $1/3$ interleaved-triple A/A false-win law ($m \ge 3$ independent triples + coalesced-chunk/degenerate-alphabet gates), exact looped-visit / MoE VRAM-ROI / batched-draft rooflines, and `9,225,188 B` (`≈ 8.80 MiB`, `36.66%` of `24 MiB`) L3 residency roofline. | `certificate_sha256`: `024edcdc7d153c9d254be3365ae24b7d6492eb1a7f9d59d64b18f27ef03dc091` |
| **`S127`** | `track_s127_ratncap_cone_gait/` | `verify_ratncap_cone_gait.py` — Exact antagonistic cone linearization bijection, spring-mass elastic energy return, 4D $T^4/S^1$ commissural `[3,0,0] <-> [1,2,0]` gait bifurcation, and dual-pole $B^4$ gate certificate. | `certificate_sha256`: `dd1aeb8309fa259ffeb5947eb0419dd152ccd9aa4f05e52e02d332cf569f4e06` |

## Hardware Receipt Scope (Energy & Power Policy)

- All five exact-$\mathbb{Q}$ oracles and `tests/test_tracks_s121_s124_s127.py` execute deterministically on CPU with zero GPU access (`CUDA_VISIBLE_DEVICES=""`).
- Track `S121` includes the recorded RTX 3080 Laptop GPU determinism stamp `track_s121_loopcd_platosphere/mlos_zone_b_w11_loopcd_platosphere.json` (`receipt_sha256 = 53b9670585299deff9f041ff060c1ccc43d21664dbb710e5e518900f338fe546`). That receipt certifies **determinism pins and functional provenance only** — any raw NVML `power_draw_w` telemetry fields present in the stamp reflect uncontrolled laptop telemetry and are **not** controlled energy or power claims.
- **Mutation Coverage Scope:** Across the `6` pure-stdlib track modules (`S121`, `S122` oracle, `S123` oracle + bench, `S124`, and `S127`), `aletheia mutate --max-mutants 0` kills **`262 / 262` (`100.0%`)** on stock torch-free Python; `S122`'s optional PyTorch micro-benchmark (`bench_gegenbauer_vs_monomial_attn.py`) kills **`17 / 17` (`100.0%`, `279 / 279` total)** on PyTorch-enabled hosts (`13 / 17` on torch-free Python where `_train_one` is skipped).

## Quick Verification (3-Mode Isolated `-I` Parity)

```bash
# Run the unified stdlib discovery suite across all 3 isolated R4 modes
for flags in "-I -B" "-I -O -B" "-I -B -W error"; do
  CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 python3 ${flags} tests/test_tracks_s121_s124_s127.py -v
done

# Run the repository master suite (discovers tests/test_tracks_s121_s124_s127.py automatically)
CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 python3 -I -B tests/run_all.py
```
