# Verified Pure-$\mathbb{Q}$ & Empirical Studies: Tracks `S121`, `S122`, `S123`, `S124`, and `S127`

This bundle collects five self-contained, pure-Python exact-rational (`int`/`Fraction`) verification studies, their byte-exact pre-execution preregistrations (`preregistrations/`), and companion benchmark records under `studies/tracks_s121_s124_s127/`. Every core verifier and its R5 adversarial test suite runs on stock Python 3 stdlib (`0` third-party dependencies, `0` bare `assert`s, `0` skips across `-I -B`, `-I -O -B`, and `-I -B -W error`).

> **Scope Note on Companion Wave-14/15 Tracks `S125` and `S126`:**
> - **Track `S125`** (zero-dependency C11 `AVX-512 VNNI` L3-resident `HoloSphere-V3` CPU engine referenced in `track_s124_aa_roofline_l3/REPORT_S124_AA_ROOFLINE_L3.md`) shipped and merged in [`Moissanite-Labs/silikernels#8`](https://github.com/Moissanite-Labs/silikernels/pull/8) (`7f7932f7fe1a`).
> - **Track `S126`** (`HoloEmit`, pure-`Init` `Lean 4.36.0` verified zero-spill `sm_86` PTX & 16-lane `AVX-512` `[16, 11, 4]` SECDED compiler) is published as the standalone repository [`Moissanite-Labs/holoemit`](https://github.com/Moissanite-Labs/holoemit) (`main @ e0e843e3a118`).

## Study Index, Taxonomy Labels, & Canonical Certificate Bindings

Under the repository's `PROVEN / VERIFIED / KNOWN / CONJECTURE` claim taxonomy (`PROVEN` reserved for Lean kernel theorems; `VERIFIED` for deterministic exact-$\mathbb{Q}$ / reproducible computational certificates; `KNOWN` for cited prior-art identities and baselines), each study maps its exact-$\mathbb{Q}$ oracle claims and preregistered empirical Law-4 gate outcomes (`CONFIRMED` / `PARTIAL` / `FALSIFIED`) as follows:

| Track | Subdirectory | Taxonomy Mapping (`VERIFIED` / `KNOWN` + Empirical Gate Grade) | Core Exact-$\mathbb{Q}$ Oracle & Key Results | Canonical SHA-256 Binding |
| :--- | :--- | :--- | :--- | :--- |
| **`S121`** | `track_s121_loopcd_platosphere/` | Exact-$\mathbb{Q}$ geometry: **`VERIFIED`**; Live Zone-B gates: `W11-A1`/`W11-A2` **`CONFIRMED`**, `W11-B3` **`FALSIFIED`** (`VERIFIED` negative result) | `verify_loopcd_sphere_geometry.py` — Spherical chord self-damping gap $\tan\frac{\pi-\theta}{2}-\tan\alpha = \frac{1+s^2}{s(1+(1+2\omega)s^2)} > 0$, palindromic Strang BCH quadratic cancellation in $\mathbb{H}_{\mathbb{Q}}/SU(2)$, acute-ball denominator floor $81/625 > 0$, plus live RTX 3080 Zone-B record (`W11-A1` `48.65x–173.23x` closer to right-ordered Strang BCH, `W11-A2` `L=3/4` `-0.3365/-0.2005` BPB, falsified `W11-B3 SphereMap` `-6.69 pp`). | `payload_sha256`: `373ff4d100e0ad7f6e71160b5bc557fb51ad52165f1d907a4fd3f95d3a35142f` |
| **`S122`** | `track_s122_xpi_gegenbauer/` | Exact-$\mathbb{Q}$ multipoles: **`VERIFIED`** (classical Chebyshev/Zador definitions **`KNOWN`**); CPU micro-bench: **`PARTIAL`** (`G1`, `G2a`, `G2b`, `G3` pass; `G4` `8x8` fails at `50.98%`) | `verify_xpi_gegenbauer_attention.py` — Exact spherical multipole / Gegenbauer vs. monomial attention conditioning, Möbius north-pole slope (`239x` / `280x` slack), and exact unit-volume vs. unit-radius Zador quantization constant bounds; `bench_gegenbauer_vs_monomial_attn.py --check` re-evaluates all seed metrics and `grade_s122_empirical` fail-closed. | `certificate_sha256`: `16d2d039358dcdee1e1a85e9211603c48a3a1a808c1ba2129d95f3b15fd04ba3` |
| **`S123`** | `track_s123_sfast_state_transport/` | Exact-$\mathbb{Q}$ Woodbury & $SO(3)$ intertwiner: **`VERIFIED`** (Cauchy–Schwarz / Kabsch **`KNOWN`**); 3-seed CPU bench: **`CONFIRMED`** | `verify_state_transport_geometry.py` — `100.0%` exact $O(1)$ `S_fast` Woodbury rank-1 state handoff, query-aware low-rank denoising, OLS vs. Frobenius shrinkage, and `W14-OBS-1` non-abelian $SO(3)$ / $A_5$ handedness anti-homomorphism (`100.0%` vs. `32.00% = 64/200` `rev(P) == P` prefixes). | `certificate_sha256`: `00022833acb4cdee03074af058860ff02bdd133b8a7bb493eff1ac46707abdbf` |
| **`S124`** | `track_s124_aa_roofline_l3/` | Exact-$\mathbb{Q}$ $S_3$ A/A law & rooflines: **`VERIFIED`** (`G1`, `G2`, `G3` derived verdicts = **`CONFIRMED`**) | `verify_s124_aa_roofline_l3.py` — Exact $S_3$ $1/3$ interleaved-triple A/A false-win law ($m \ge 3$ independent triples + coalesced-chunk/degenerate-alphabet gates), exact looped-visit / MoE VRAM-ROI / batched-draft rooflines, and `9,225,188 B` (`≈ 8.80 MiB`, `36.66%` of `24 MiB`) L3 residency roofline. | `certificate_sha256`: `7e0724b4bff0e7567bec4285f7e0996027e7aac10d05ecf8da57cb5a04a5b6e9` |
| **`S127`** | `track_s127_ratncap_cone_gait/` | Exact-$\mathbb{Q}$ cone bijection & $T^4/S^1$ Sylvester inertia: **`VERIFIED`** (`G1`, `G2`, `G3` = **`CONFIRMED`**) | `verify_ratncap_cone_gait.py` — Exact antagonistic cone linearization bijection, spring-mass elastic energy return, 4D $T^4/S^1$ commissural `[3,0,0] <-> [1,2,0]` gait bifurcation, and dual-pole $B^4$ gate certificate. | `certificate_sha256`: `dd1aeb8309fa259ffeb5947eb0419dd152ccd9aa4f05e52e02d332cf569f4e06` |

## In-Tree Preregistration Locks & Sanitization Provenance (`preregistrations/`)

All four pre-execution preregistration files referenced across Tracks `S121`, `S123`, `S124`, and `S127` are committed under `preregistrations/` and re-hashed directly on disk during verification (`MISSING_PREREG*` / `PREREG*_MISMATCH` / `PREREG_MISSING` / `ZONEB_PREREG_MISSING` on absence or tamper; no constant-SHA standalone fallback). Two files (`PREREG-W12` and `PREREG-W14`) had internal role handles stripped on one line each (`:50` and `:32`) for public hygiene while preserving all mathematical hypotheses, parameters, and kill gates verbatim. **Provenance note:** the pre-sanitization raw `PREREG-W12` and `PREREG-W14` byte streams are excluded from this public repository by design (so the original pre-sanitization lock SHA-256s below are recorded for historical traceability and are not re-hashed in-tree; the verifier actively re-hashes the committed sanitized files on disk).

| File (`studies/tracks_s121_s124_s127/preregistrations/`) | Track(s) | Original Pre-Sanitization Lock SHA-256 (Excluded by Design) | In-Tree Verified SHA-256 | Sanitization Note |
| :--- | :--- | :--- | :--- | :--- |
| `PREREG_W11_LIVE_LOOPCD_PLATOSPHERE.md` | `S121` | `b09baa4d6adab2b2883064b294b7e66656b135bca09ee672d50f60e14539ef05` | `b09baa4d6adab2b2883064b294b7e66656b135bca09ee672d50f60e14539ef05` | Unmodified byte-for-byte |
| `PREREG_WAVE12_FRONTIER_SYNTHESIS.md` | `S123` | `08ce3b2a752107b17fa67c3f530b6d28706b5115fc01349f146aaf18fa74f031` | `b012a39410e08f121f2beeab9f3af2e40ecab8f46ffe4ebffcfe080debdbb34e` | Line 50 internal role handle stripped |
| `PREREG_WAVE14_INF_OPT_BAREMETAL.md` | `S123`, `S124` | `871900e5d6c860ac159f43ca6b4767e7c128d0b4f7748edf788d56e9cb535d3e` | `4994ae816d852856cfb4c32713c1ca8aea08a2be4abf1f8186d3bd531f0d604d` | Line 32 internal role handle stripped |
| `PREREG_WAVE15_TENSORFOLD_RATNCAP_PSYCHOSCRIPT.md` | `S127` | `6c938ddb41b912f01dba3ccb58e3f8cb54ebe60f93f6bc0eaec134bc93f189a0` | `6c938ddb41b912f01dba3ccb58e3f8cb54ebe60f93f6bc0eaec134bc93f189a0` | Unmodified byte-for-byte |

## Hardware Receipt Scope, Energy Policy, CI Coverage, & Per-Module Mutation Verification

- All five exact-$\mathbb{Q}$ oracles and `tests/test_tracks_s121_s124_s127.py` execute deterministically on CPU with zero GPU access (`CUDA_VISIBLE_DEVICES=""`).
- Track `S121` ships the bound RTX 3080 Laptop GPU determinism stamp `track_s121_loopcd_platosphere/mlos_zone_b_w11_loopcd_platosphere.json` (`receipt_sha256 = 7f31de378b1b067c1edce9f5cc12400b1649ae3e95e6291568d90ccab0889fb0`, with paired `git_head: null` and `git_head_status: "not_captured_at_run_time"` recorded honestly with zero fabricated commit hash; receipts with a real 40-char hex `git_head` pair with `git_head_status: "captured"` or `"captured_dirty"`, must agree with `results["git_head"]`/`results["git_head_status"]`, and are verified against actual git repository commits via `git cat-file -e`), explicitly bound to `w11_live_loopcd_platosphere_results.json` (`payload_sha256 = 8d3000e3b45a17b0b8b8a68289d9d1755d2bc5d55cfbc7e6a1e4444ebb07f891`; historical committed run omits `git_head`/`git_head_status` under `not_captured_at_run_time` and external `.pt`/`eval.bin` checkpoints stay outside git per `WEIGHTS = 0`), `preregistrations/PREREG_W11_LIVE_LOOPCD_PLATOSPHERE.md` (`b09baa4d...`), and the committed hardware profile `track_s121_loopcd_platosphere/ux582hs-rtx3080-8gb.toml` (`profile_sha256 = 566c9192d38682a0ec4d652a63a3510aaefb9dc20ef91ae9bdc6d4abbbf5cbe2`), verified fail-closed via `run_w11_live_loopcd_platosphere.py --check-zone-b` (enforcing lowercase 64-hex digests, exact schema allowlists, `determinism_pins`, `host`, GPU telemetry & clean-run invariants, full Probe A & Probe B summary/gate recomputation from raw grids/pairs, and committed bundle SHA-256 pins by default; returning exit code `0` on pass and clean exit code `2` with structured `FAIL S121_ZONE_B code=...` and zero uncaught tracebacks on any tamper; `--selftest-stdlib` and `--run-gpu` are mutually exclusive CLI modes that likewise return clean exit code `2` with `FAIL S121_W11_PROBE code=...`, including `TORCH_MISSING` on torch-free hosts). That stamp certifies **determinism pins and functional provenance only** (`energy_power_status = "UNCONTROLLED_LAPTOP_TELEMETRY_NOT_AN_ENERGY_CLAIM"` — raw NVML `power_draw_w` telemetry fields are uncontrolled laptop telemetry, not energy or power claims).
- **CI Coverage Path:** GitHub Actions covers this entire bundle via the `verify-r4-r5` matrix (`Python 3.11, 3.12, 3.13` across `-I -B`, `-I -O -B`, and `-I -B -W error`), which invokes `tests/run_all.py` and discovers `tests/test_tracks_s121_s124_s127.py` (whereas the separate `evidence-tracks` workflow job globs `evidence/*/*_audit.py`).
- **Bundle `--work-root` Mutation Recipe & Verified Per-Module Counts:** Because in-tree preregistrations live in the sibling `studies/tracks_s121_s124_s127/preregistrations/` folder, `aletheia mutate` must be invoked with **`--work-root studies/tracks_s121_s124_s127`** (not a single track subdirectory):

```bash
# Example recipe (run from repo root with aletheia installed; substitute target & test path from table below)
CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 python3 -I -B -m aletheia mutate \
  studies/tracks_s121_s124_s127/track_s121_loopcd_platosphere/run_w11_live_loopcd_platosphere.py \
  --work-root studies/tracks_s121_s124_s127 --guards require_ok \
  --test-cmd "python3 -I -B track_s121_loopcd_platosphere/test_w11_live_loopcd_platosphere_r5.py" \
  --max-mutants 0 --timeout 25 --workers 4
```

| Track | Module (`studies/tracks_s121_s124_s127/...`) | R5 Test Suite (`--work-root studies/tracks_s121_s124_s127`) | Verified Mutate Kill Count (`--max-mutants 0`) | Runtime Dependency |
| :--- | :--- | :--- | :---: | :--- |
| **`S121`** | `track_s121_loopcd_platosphere/verify_loopcd_sphere_geometry.py` | `track_s121_loopcd_platosphere/test_loopcd_sphere_geometry_r5.py` | **`44 / 44` (`100.0%`)** | Pure stdlib (`-I -B`) |
| **`S121`** | `track_s121_loopcd_platosphere/run_w11_live_loopcd_platosphere.py` | `track_s121_loopcd_platosphere/test_w11_live_loopcd_platosphere_r5.py` | **`69 / 69` (`100.0%`)** | Pure stdlib (`-I -B`) |
| **`S122`** | `track_s122_xpi_gegenbauer/verify_xpi_gegenbauer_attention.py` | `track_s122_xpi_gegenbauer/test_xpi_gegenbauer_attention_r5.py` | **`53 / 53` (`100.0%`)** | Pure stdlib (`-I -B`) |
| **`S122`** | `track_s122_xpi_gegenbauer/bench_gegenbauer_vs_monomial_attn.py` | `track_s122_xpi_gegenbauer/test_bench_gegenbauer_r5.py` | **`37 / 37` (`100.0%`)** w/ PyTorch CPU (`33 / 37` torch-free) | PyTorch CPU (4 torch-loop guards) |
| **`S123`** | `track_s123_sfast_state_transport/verify_state_transport_geometry.py` | `track_s123_sfast_state_transport/test_state_transport_geometry_r5.py` | **`54 / 54` (`100.0%`)** | Pure stdlib (`-I -B`) |
| **`S123`** | `track_s123_sfast_state_transport/bench_sfast_cross_seed_transport.py` | `track_s123_sfast_state_transport/test_bench_sfast_transport_r5.py` | **`19 / 19` (`100.0%`)** | Pure stdlib (`-I -B`) |
| **`S124`** | `track_s124_aa_roofline_l3/verify_s124_aa_roofline_l3.py` | `track_s124_aa_roofline_l3/test_s124_aa_roofline_l3_r5.py` | **`47 / 47` (`100.0%`)** | Pure stdlib (`-I -B`) |
| **`S127`** | `track_s127_ratncap_cone_gait/verify_ratncap_cone_gait.py` | `track_s127_ratncap_cone_gait/test_ratncap_cone_gait_r5.py` | **`51 / 51` (`100.0%`)** | Pure stdlib (`-I -B`) |
| **Total** | **7 pure-stdlib modules / 8 total modules** | All `--work-root studies/tracks_s121_s124_s127` | **`337 / 337` stdlib (`374 / 374` w/ PyTorch CPU)** | `0` survived (`truncated = False`) in full runs; `4` torch-loop guards require PyTorch |

## Quick Verification (3-Mode Isolated `-I` Parity)

```bash
# Run the unified stdlib discovery suite across all 3 isolated R4 modes
for flags in "-I -B" "-I -O -B" "-I -B -W error"; do
  CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 python3 ${flags} tests/test_tracks_s121_s124_s127.py -v
done

# Run the repository master suite (discovers tests/test_tracks_s121_s124_s127.py automatically)
CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 python3 -I -B tests/run_all.py
```
