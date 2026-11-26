# Evidence Track S119 — Exact $\mathbb{Q}(\sqrt{5})$ Spinor-Barrington $2I \subset SU(2)$ DAG-to-`HoloSphere` Compiler & Pure-`Init` Lean 4.36.0 Theorems (`#46–#48`)

This self-contained, pure-Python-stdlib (`0` external dependencies, `0` GPU touch, `0` floats in exact algebra) evidence package proves, constructs, and adversarially verifies the **Exact $SL(2, 5) = 2I$ Spinor-Barrington Commutator Sign Dichotomy**, an **$O(S)$ Relational `V_ring` Boolean-DAG Compiler** collapsing Barrington's $4^d$ formula blowup to linear gate count inside `HoloSphere`'s single-step bounded-ball `CayleySU2` chart, and **three machine-checked Pure-`Init` `Lean 4.36.0` theorems (`#46–#48`, `#46` zero axioms `[]`)**.

- **Companion Public PR:** [Moissanite-Labs/holosphere#3](https://github.com/Moissanite-Labs/holosphere/pull/3) (head commit `6f75548d9e7e254955f98b6e6a00e997dc5699de`, `OPEN` at staging time; integrates Theorems `#46–#48` as part of the `51/51` pure-`Init` Lean 4.36.0 theorem suite).
- **Canonical Certificate `payload_sha256`:** `009dd43173448ca38adeea9240365f3e3532d98eb622d50a56ee2ae35f097f97`

## Headline Verified Results

| Pillar | Exact Verification Result |
|---|---|
| **Exact $\mathbb{Q}(\sqrt{5})$ Binary Icosahedral Group $2I \cong SL(2, 5) \subset SU(2)$** | `\|2I\| = 120`, `120/120` unit norm, `120/120` inverse closed, `14,400/14,400` closed products, exact quotient `\|2I / {±I}\| = 60` ($\cong A_5$), `75/75` exact `CayleySU2` roundtrips for $q_0 \ge 0$ (`45` acute with $\|\omega\| \le \tan(\pi/5) \approx 0.726543 < 0.8$; `30` equatorial with $\|\omega\| = 1$), `1` pole ($-I$). |
| **Exact $SL(2,5) = 2I$ Spinor-Barrington Commutator Sign Dichotomy** | Universal 2-line identity $\operatorname{Re}([a, b]) = 1 - 2\|\vec{a}\times\vec{b}\|^2$ verified `0/14,400` mismatches. **Both order-5 classes ($\tilde{\sigma}_0^5 = +I$) suffer a strict $\mathbb{Z}_2$ spinor obstruction (`0` positive / `10` negative pairs).** Switching to acute **order-10 class $\mathcal{C}_{10}^+$** ($\tilde{\tau}_0^5 = -I$, $q_0 = \frac{1+\sqrt{5}}{4}$) yields **`10` positive / `0` negative pairs**, closing `AND` and `NOT` on $\{+I, +\tilde{\tau}_0\}$ with **zero sign canonicalization**, **zero `-I` leakage**, and strict interior-ball invariant $\|\omega\| \le \tan(\pi/5) \approx 0.726543 < 0.8$ across **all** intermediate partial products. |
| **Constructive $O(S)$ Relational `V_ring` DAG Collapse (`7` Circuits, `354/354` All-$2^n$ Exact)** | `shared_diamond_d6`: `832 B` / `192` muls vs `4,096` ($4^6$, `21.33×`). `shared_diamond_d16`: `2,112 B` / `512` muls vs `4,294,967,296` ($4^{16}$, **`8,388,608.00×`**). `ripple_carry_adder_4bit`: `256/256` exact (`30.71×`). `lyapunov_self_and_d16`: `272 B` / `112` muls vs $4^{16}$ (**`38,347,922.29×`**). |
| **Honest 4-Regime Strict IEEE-754 FP32 Drift Taxonomy** | **Unnormalized raw FP32** explodes radially at rate $4^d$ (`7.62e+29` / `OVERFLOW` at `d=16`, `0/16` decoded). **`s3_norm` (`2.70e-7`) & `cayley_reproj` (`4.05e-8`)** hold `shared_diamond_d16` well under `1e-5` (`16/16` exact). On the adversarial all-(1,1) chain `lyapunov_self_and_d16`, exact $\mathfrak{su}(2)$ tangent spectral radius $\rho = \phi \approx 1.618034$ yields `1.52e-4` under `s3_norm` (`4,074×` below separation $\phi^{-1}$). **Branchless binary `V_ring` refresh** ($q_0 > 0.9045085$) clamps drift to **`1.16e-8`** at arbitrary depth. |
| **Pure-`Init` `Lean 4.36.0` Machine-Checked Proofs (`#46–#48`)** | `lean/HoloSphereSpinorBarrington.lean`: `3` public theorems (`p46` **`[]` zero axioms!**, `p47` & `p48` `[propext, Quot.sound]`) + `33` private helpers = `36` declarations; `0` `Classical.choice`, `0` `sorryAx`, `0` `native_decide`, `0` warnings. |

## Honest Law-4 Novelty Calibration (`N1`, `n2_claims = 0`)

- **`N0` (Established Prior Art):** Barrington (1989) width-5 branching programs over $A_5$ ($NC^1 = \mathrm{BWBP}$, $4^d$ formula blowup); Ben-Or & Cleve (1992) / Cleve (1991) $O(S)$ straight-line register programs; Merrill & Sabharwal (2023/2024) log-precision transformer $TC^0$ vs $NC^1$ bounds; classical finite subgroups of $SU(2)$ ($2I \cong SL(2,5)$) and the Cayley transform.
- **`N1` (Verified Constructive Synthesis):** (1) Exact 9-class $SL(2,5) = 2I$ spinor-commutator dichotomy proof (2-line $SU(2)$ trace identity + Lean 4.36.0 `#46–#48`) resolving order-5 obstruction via acute $\mathcal{C}_{10}^+$ sign-free interior-ball closure; (2) Concrete $O(S)$ `CayleySU2` + `16 B` `V_ring` compiler & 4-regime FP32 drift / $\phi^d$ Lyapunov analysis.
- **Explicit Non-Claims & Provenance Disclosures:** `V_ring` uses $O(S)$ addressable `16 B` register slots (straight-line register model, not $O(1)$-width streaming) and does not separate $TC^0$ from $NC^1$. All verification in this package is strictly CPU-only (`0` GPU execution, `0` corpus downloads, `0` weights/ELF). Any local expedition `verification/AUDIT_LOG.md` resides outside this repository; the first in-repo git commit records this staged evidence bundle.

## Reproducible Verification (Pure Python Stdlib + Optional Live Lean 4.36.0)

```bash
# 1. Exact Q(sqrt(5)) + IEEE-754 FP32 compiler & R5 test suite (all 3 isolated R4 modes, 0 skips)
python3 -I -B evidence/track-s119-barrington-su2-dag-compiler/barrington_su2_dag_compiler.py --check
python3 -I -B evidence/track-s119-barrington-su2-dag-compiler/test_s119_barrington_r5.py
python3 -I -O -B evidence/track-s119-barrington-su2-dag-compiler/test_s119_barrington_r5.py
python3 -I -B -W error evidence/track-s119-barrington-su2-dag-compiler/test_s119_barrington_r5.py

# 2. Pure-Init Lean 4.36.0 verifier (live Lean when installed; static R13b + SHA-256 + exact oracle always run)
python3 -I -B evidence/track-s119-barrington-su2-dag-compiler/test_s119_lean_r5.py -v
python3 -I -B evidence/track-s119-barrington-su2-dag-compiler/lean/verify_s119_lean_r5.py --verify-lean

# 3. Exhaustive R5 mutation audit (61/61 = 100.0% killed)
python3 -I -O -B -W error -m aletheia mutate \
  evidence/track-s119-barrington-su2-dag-compiler/barrington_su2_dag_compiler.py \
  --work-root evidence/track-s119-barrington-su2-dag-compiler \
  --test-cmd "python3 -I -B test_s119_barrington_r5.py" \
  --guards require_ok --max-mutants 0
```

## Staged File Manifest (`9` Track Files + This `README.md`)

| Path (relative to `evidence/track-s119-barrington-su2-dag-compiler/`) | Lines | Bytes | SHA-256 |
|---|---:|---:|---|
| `REPORT_S119_SPINOR_BARRINGTON_DAG.md` | `169` | `22191` | `7f74293da77e44a380432399e2bddc54bf3b272bd91b155021f2d6a03d533155` |
| `barrington_su2_dag_compiler.py` | `1207` | `46155` | `0b89e57a63502f4a2026ab9d871d2fbf30e1cefe04f72c0fcfc60f04694f6916` |
| `test_s119_barrington_r5.py` | `294` | `14108` | `33c6911d99816e8d9cfa65b3703cd0862b510b011b74dc4f25c093134cc54c31` |
| `test_s119_lean_r5.py` | `27` | `795` | `2fc1750eece37eb7cde06d9982342cd89a7eef64e3a1b4ca878f8c6f1f5a401b` |
| `lean/HoloSphereSpinorBarrington.lean` | `609` | `26396` | `972c14c36e991ab4b4c6a342bb24c499e8d7deb68749ba175d8af6893500e37e` |
| `lean/verify_s119_lean_r5.py` | `727` | `31760` | `3c17ad490705a0b0da2051912077e01bf2370d77ff110327e1f018d772ca653e` |
| `lean/README.md` | `20` | `2303` | `365564c2828c567e1f5a322fabf56257732b433c5b5f4291eccca45526f8926d` |
| `lean/lakefile.toml` | `7` | `165` | `0412f32d9a089cc57e422ed1bd04cc57ad4b4069f55c338a1b0fd496268e2501` |
| `lean/lean-toolchain` | `1` | `25` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |

Full mathematical derivations and drift tables live in [REPORT_S119_SPINOR_BARRINGTON_DAG.md](REPORT_S119_SPINOR_BARRINGTON_DAG.md) and [lean/README.md](lean/README.md).
