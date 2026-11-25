# Track S106 Phase 3 Report: Amendments 1 & 2 (`H5a`, `H5b`, `H6a`, `H6b`, `H6c`)

- **Parent Preregistration SHA-256:** `ac3e62116bc4841320d2c713787c23568beed1ae738bf9b284b7f0c2a118d72a` — **UNVERIFIABLE (file not shipped in any reachable repo)**
- **Amendment 1 (`H5`) SHA-256:** `c83910a0e1a98e2afe473e5b15109fcbaf8e16bf85a08188b10fbdecfd75a05f` — **UNVERIFIABLE (not shipped)** (`h5_locked_protocol.json` locked `2026-11-25T13:37:02Z`, `mlos_zone_b_h5_receipt.json` `clean_hardware_run=true`, `anomalies=[]`, `1534369.0 ms`, `57°C -> 67°C`, `compute_vram_mib: 0 -> 0`)
- **Amendment 2 (`H6`) SHA-256:** `b676cc556c9bbfa0849c29c3326ebd13e8f43e9c65960ddb5eb508fdead21d85` — **UNVERIFIABLE (not shipped)** (`h6_locked_protocol.json` locked `2026-11-25T14:09:23Z`, `mlos_zone_b_h6_receipt.json` `clean_hardware_run=true`, `anomalies=[]`, `1106793.1 ms`, `53°C -> 71°C`, `compute_vram_mib: 0 -> 0`)
- **Verifier status fields:** `verify_s106_phase3.py --json` reports `amendment_status=UNVERIFIABLE_NOT_SHIPPED` unless the amendment markdowns are supplied via `--amendment1/2`, in which case their **full** SHA-256 must equal the pinned 64-hex constants (`AMENDMENT_FILE_SHA_MISMATCH` otherwise; previously a 16-hex prefix match sufficed).
- **Post-run receipt rewrite (disclosed):** the H5/H6 Zone-B receipts (`mlos_zone_b_h5/h6_receipt.json`) were re-signed after the runs to add the `bound_file_sha256` results-binding link; the verifier checks that binding, and the raw run-time receipt bytes are therefore not the shipped bytes.
- **Isolation & Integrity:** Executed exclusively in sibling dir `gpu_eval_phase3_h5_h6/` (leaving audited Phase-2 `gpu_eval/` 100% untouched); `74/74` LLM arms (`48` H5 + `26` H6) + `4/4` matched-param `10,818,432`-param micro-LMs completed with **`0` syndrome errors, `0` out-of-ball groups, `0` non-block diffs, `WEIGHTS=0`, `0` GitHub pushes**.

---

## 1. Literal Locked-Rule Verdicts

| Hypothesis | Locked Verdict | Exact Held-Out Summary (Phase 3 is NOT blind on these models) |
| :--- | :---: | :--- |
| **`H5a` (Zero-Extra-Bit `Flow-SphereMap`)** | **`FALSIFIED`** | **Exact Law-5 Algebraic Obstruction Discovered:** Right-multiplying $W$ by any positive diagonal $D_{\text{flow}}$ before Sinkhorn L2 whitening is **gauge-annihilated** by Sinkhorn's column normalization step: $D_r^{-1} (W D_{\text{flow}}) (D_c D_{\text{flow}})^{-1} \equiv D_r^{-1} W D_c^{-1}$ identically for exact real-valued Sinkhorn — in the shipped FP16 implementation, up to FP16 scale rounding and finite-iteration Sinkhorn (CPU control: 0.04–0.29% relative). Across `3/3` models × `3/3` configs, `static`, `flownoise`, `flowreal`, and `flownull` match in weight SNR to 3 decimal places (`15.385` / `15.378` / `14.985 dB`) with `< 1.5%` FP16 rounding jitter. |
| **`H5b` (Depth-Time Cone & Bit Schedule)** | **`FALSIFIED`** | Q1/Q4 causal perturbation amplification passes `>= 2.0×` on `1/3` models (`SmolLM2`: **`2.226×`**, `Qwen1.5B`: `1.454×`, `Qwen3B`: `0.895×`). Matched-`bpw` (`2.9989` vs `2.9990`) Q1-heavy schedule (`3.5/3.0/2.5 bpw`) passes `>= 8%` KL on `1/3` models — **producing a huge `-16.4% Wiki / -55.4% Python` KL cut on `Qwen2.5-3B` (`0.433/0.319` vs `0.518/0.716`, while reversed `Q1 @ 2.5b` explodes `10×` to `4.188/4.236`!)** because Layers 1–5 carry `Qwen3B`'s extreme column outliers. |
| **`H6a` ($S^3$ Polar-Curvature Depth Foliation)** | **`FALSIFIED`** | Locked pilot fraction `1/4` (`Qwen2.5-0.5B`). **Polar beats Equatorial on `3/3` models (`0/3` Equatorial wins!)**, and exhibits sharp scale emergence against Flat uniform `3.00 bpw`: `SmolLM2-360M` trails (`0.480/0.420` vs `0.437/0.378`), `Qwen2.5-1.5B` cuts WikiKL `-5.6%` (`0.294` vs `0.311`), and **`Qwen2.5-3B` cuts WikiKL `-28.8%` (`0.518 -> 0.368`, `8.8 SE`) and Python KL `-60.8%` (`0.716 -> 0.280`, `18.6 SE` — `13.4×` better than Equatorial `4.397/4.314`!)**. Fails locked `>= 10%` on `>= 2/3` models (`1/3`) -> honest `FALSIFIED`. |
| **`H6b` Part 1 (Hopf-Fiber `EQ(S^2) × S^1`)** | **`FALSIFIED`** | Exact $U(1)$ fiber-phase equivariance verified at **`1.000000` / `1.000000` / `0.999998`** across `1.10B` 4-blocks (`32×8` split locked on Gaussian), but factored encode directional SNR (`10.778 dB`) trails direct `EQ(S^3)` (`13.487 dB`) by `-2.708 dB` (`> 0.15 dB` kill gate). |
| **`H6b` Part 2 (Zero-Cost `down_proj` Flow Order)** | **`FALSIFIED`** | Descending-$D_{\text{flow}}$ ordering beats random permutation on `SmolLM2` (`-14.5%` at `3.0b`) and beats both native and random on `Qwen1.5B` `3.0b` (`0.305/0.203` vs `0.311/0.219` / `0.318/0.220`), but fails the locked `>= 5%` gate across `>= 2/3` models at both `2.0` and `3.0 bpw`. |
| **`H6c` (Native Hopf-$S^3$ Residual Micro-LM)** | **`CONFIRMED`** | **CONFIRMED on Criterion A (`NLL`/`BPB`) at exact `10,818,432`-param parity (`0` extra params, identical tokens/optimizer/seeds):** BOTH Hopf seeds decisively beat BOTH flat-residual seeds (**`2.6612` & `2.6197` vs `2.9348` & `3.0295` val BPB — mean `-0.342 BPB` / `-11.5%` reduction!**). Even post-3-bit-PTQ Hopf (`2.663 BPB`) beats FP32 flat (`2.982 BPB`). **Honest Law-4/5 Caveats:** Criterion B (`>= 15%` lower PTQ KL) failed (`0.0135` vs `0.0063` nats), and un-fused PyTorch quaternion ops ran `2.57×` slower wall-clock (`55.4 s` vs `21.6 s`). |

---

## 2. Amendment 1 (`H5a` + `H5b`) Held-Out Table (not blind: H5b was motivated by Phase-2 Qwen3B outliers)

| Model | `E_8 3b` WikiKL (Static / FlowNoise) | `A_16 3b` WikiKL (Static / FlowNoise) | `H5b` Cone Q1/Q4 | `p128` Uniform `3b` (Wiki / Py) | `p128` Depth `3.5/3.0/2.5` (Wiki / Py) | `p128` Reverse `2.5/3.0/3.5` (Wiki / Py) |
| :--- | :---: | :---: | ---: | :---: | :---: | :---: |
| `HuggingFaceTB/SmolLM2-360M` | `1.25032` / `1.25888` | `1.46433` / `1.47031` | `2.226×` | `0.43727` / `0.37812` | `0.55220` / `0.50188` | `0.53298` / `0.47623` |
| `Qwen/Qwen2.5-1.5B` | `0.58884` / `0.59092` | `0.74824` / `0.74088` | `1.454×` | `0.31135` / `0.21872` | `0.37928` / `0.25549` | `0.41958` / `0.25377` |
| `Qwen/Qwen2.5-3B` | `15.73533` / `15.62251` | `19.08496` / `19.28569` | `0.895×` | `0.51768` / `0.71552` | `0.43289` / `0.31919` | `4.18796` / `4.23582` |

- **Exploratory `p128_A16_3b_flownoise` (ungraded, column scale billed at `+16/m` bpw):** Raw `sqrt(E[x^2])` (spread up to `5.19×10^6×` on `Qwen3B`) hurts static SNR (`-7.2` to `-12.9 dB`) and degrades `SmolLM2`/`Qwen1.5B` KL (`0.773/0.781`, `0.428/0.323`), while slashing `Qwen3B` Python KL by **`-45.8%`** (`0.716 -> 0.388`).

---

## 3. Amendment 2 (`H6a` + `H6b`) Held-Out Table (not blind)

| Model | `flat_3b` (Wiki / Py) | `polar_3b` (Wiki / Py) | `equatorial_3b` (Wiki / Py) | `floworder_3b` (Wiki / Py) | `H6b-1` Hopf vs `EQ(S^3)` dB (Equiv.) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `HuggingFaceTB/SmolLM2-360M` | `0.43727` / `0.37812` | `0.48047` / `0.42038` | `0.71261` / `0.57819` | `0.43704` / `0.36606` | `10.778` vs `13.487` (`1.000000`) |
| `Qwen/Qwen2.5-1.5B` | `0.31135` / `0.21872` | `0.29377` / `0.21967` | `0.44513` / `0.27661` | `0.30488` / `0.20336` | `10.779` vs `13.487` (`1.000000`) |
| `Qwen/Qwen2.5-3B` | `0.51768` / `0.71552` | `0.36840` / `0.28040` | `4.39725` / `4.31447` | `0.55964` / `0.75089` | `10.778` vs `13.487` (`0.999998`) |

---

## 4. Amendment 2 (`H6c`) Matched-Parameter Micro-LM Pilot (`10,818,432` Params, `WEIGHTS=0`)

| Mode | Seed | Params | Final Train Loss | Val BPB (FP32) | Val BPB (3-bit PTQ) | 3-bit PTQ KL (nats) | Wall Time |
| :--- | :---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `flat` | `11` | `10,818,432` | `2.0208` | `2.934806` | `2.944518` | `0.005788` | `21.65 s` |
| `flat` | `12` | `10,818,432` | `2.0715` | `3.029539` | `3.042559` | `0.006887` | `21.51 s` |
| `hopf` | `11` | `10,818,432` | `1.7288` | `2.661224` | `2.681181` | `0.012160` | `55.12 s` |
| `hopf` | `12` | `10,818,432` | `1.7233` | `2.619703` | `2.645367` | `0.014791` | `55.72 s` |

---

## 5. Frozen Artifact Manifest (`gpu_eval_phase3_h5_h6/` — `10` Sibling Files + `REPORT_PHASE3_H5_H6.md` = `11` Files)

> **R5 mutation kill rate (this head):** `aletheia mutate --guards require_ok raise --max-mutants 0` on `verify_s106_phase3.py` kills **19/40 (47.5%)** (18/39 at the reviewed head `efdc334`); null mutant passes.

| File | Lines | Bytes | Mode | SHA-256 (Full 64-Hex) | Role |
| :--- | ---: | ---: | :---: | :--- | :--- |
| `h5_locked_protocol.json` | `1` | `2,250` | `0o644` (git 100644) | `546c14f449f693452144e1f1417d62043d47c0127aba7bad872716611ea82edd` | Runtime-emitted H5 protocol constants (locked at run start, inside the receipt window — NOT a pre-registration) & grading rules |
| `h6_locked_protocol.json` | `1` | `2,483` | `0o644` (git 100644) | `82f6e4cccb3e96bbd0943bd6f77d128b24d941a1e53fbf26d5efabb22f683806` | Runtime-emitted H6 protocol constants (locked at run start, inside the receipt window — NOT a pre-registration) & grading rules |
| `mlos_zone_b_h5_receipt.json` | `92` | `2,718` | `0o644` (git 100644) | `679fa3ccecc0f468644798e3402c00584b77accd90cc994f11cb20ab41de74ec` | mlos Zone B H5 receipt (`clean_hardware_run=true`, re-signed with `bound_file_sha256`, `receipt=e7002c8d...`) |
| `mlos_zone_b_h6_receipt.json` | `92` | `2,722` | `0o644` (git 100644) | `60126b2a475f4cc06f5d6f77c6a22bead22b536c877742dcb13d53a73c91f156` | mlos Zone B H6 receipt (`clean_hardware_run=true`, re-signed with `bound_file_sha256`, `receipt=dbed1c50...`) |
| `s106_h5_flow_sphere_eval.py` | `418` | `22,023` | `0o644` (git 100644) | `074d46ec797f799448586918adfeb205a93d6bfa5258651765cbdc07b6e737fb` | Amendment 1 (H5a/H5b) held-out RTX 3080 evaluator |
| `s106_h5_results.json` | `1` | `31,727` | `0o644` (git 100644) | `0acb1c3e4fd7d7e6675a636e61dd31d102c4ec4b0d5e7f229217875253db0a9b` | Canonical H5 results (`48/48` arms, `result_sha256=676b4674...`) |
| `s106_h6_hypersphere_arrangement_eval.py` | `558` | `29,946` | `0o644` (git 100644) | `639529b2019234f9722a4ed1d2715a03bf02bb7c77b02e725c77c571f1504d85` | Amendment 2 (H6a/H6b/H6c) held-out + micro-LM evaluator |
| `s106_h6_results.json` | `1` | `17,711` | `0o644` (git 100644) | `f8b6e2a163f88c95d518a51a2f94af02acd24fcb450ede55a9742f6de2664fc4` | Canonical H6 results (`26/26` arms + `4` micro-LMs, `result_sha256=5ab86f4b...`) |
| `test_s106_phase3_r5.py` | `225` | `12,160` | `0o644` (git 100644) | `0e83813d96e2a457348bcd0fea72e1c8679e101b0539ecde7d40b3269565d4e0` | Pure-stdlib R5 adversarial + hygiene test suite (7/7 tests incl. test_07 full-sha amendment flags, 0 bare asserts) |
| `verify_s106_phase3.py` | `297` | `14,660` | `0o644` (git 100644) | `2c7862199284307c687b203709d7981f5d297ff53ddadc420fe24c84c29e0694` | Pure-stdlib integrity, receipt re-sign + bound-link, and literal locked-rule verdict verifier; amendment files now compared by FULL sha256 (not 16-hex prefix) |
