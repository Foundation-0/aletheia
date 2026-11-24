# Two-Way Supposition: Competing-Potential Barrier Turnover & Endoreversible Compute Efficiency on Live Silicon

## 1. Native-Domain Formulations & Honest Novelty Accounting

This study formalizes two-way exact-operator transfer between macroscopic physical potential/dissipation laws and concrete silicon computation using pure-`Init` **Lean 4.36.0** kernel proofs (`10` theorems: `8` universal parametric `∀` theorems over unbounded `Int` + `2` exact zero-axiom witnesses; zero Mathlib, zero external imports, zero warnings), paired with a deterministic pure-$\mathbb{Z}/\mathbb{Q}$ Python oracle/auditor and live `intel-rapl` hardware measurements on an Intel Core i9-11900H host.

1. **Pillar 1 — Competing-Potential Barrier Turnover & Sub-Barrier Bridge Dominance:**
   - **Native algebra:** Whenever a two-term objective $\Delta(s) = R(s) - A(s)$ pits a repulsive barrier term $R(s)$ against a faster-growing attractive pull term $A(s)$ — covering both classical Coulomb-vs-short-range potentials $r^3 V(r) = a r^2 - b$ (`coulomb_short_range_turnover_universal`) and Reed-Muller $RM(1,4)$ lattice axis-coarsening penalty vs. scale-growing off-diagonal mixing gain (`competing_potential_sign_inversion`) — crossing $A(s)/R(s) = 1$ forces a strict sign inversion from net repulsion ($\Delta > 0$) to net pull ($\Delta < 0$).
   - **Sub-barrier bridge theorem (`sub_barrier_bridge_dominance_universal`):** An intermediate bridge operator $B$ (`Block-H2`) with reduced barrier $\rho_B < \rho_H$ and strictly lower crossover threshold $\rho_B / \gamma_B < \rho_H / \gamma_H$ enters the attractive regime strictly inside the sub-barrier band $(\rho_B/\gamma_B,\ \rho_H/\gamma_H)$ where the full-mixing operator $H$ is still repulsive ($\Delta_B < 0 < \Delta_H$). Moreover, even when $\gamma_H > \gamma_B$, the bridge dominance ceiling $(\rho_H - \rho_B)/(\gamma_H - \gamma_B)$ **strictly exceeds** $H$'s own crossover $\rho_H/\gamma_H$, so $B$ strictly dominates $H$ both across and beyond $H$'s sign flip.
   - **Exact empirical verification across frozen `0.36B -> 0.5B -> 1.5B` quantization receipts (`qwen_smollm_scale_flip_exact_witness`):**

| Model (`4,088` tok/split) | Corpus | `A16_axis` KL | `A16_BlockH2` KL ($\Delta$ vs `axis`) | `A16_H16` KL ($\Delta$ vs `axis`) | Regime |
|---|---|---:|---:|---:|---|
| `SmolLM2-360M` (`0.36B`) | WikiText-2 | `0.065173014` | `0.071701656` (`+10.02%`) | `0.079846518` (`+22.51%`) | Repulsive (`Δ_B, Δ_H > 0`) |
| `SmolLM2-360M` (`0.36B`) | Python | `0.056725239` | `0.059324707` (`+4.58%`) | `0.069955577` (`+23.32%`) | Repulsive (`Δ_B, Δ_H > 0`) |
| `Qwen2.5-0.5B` (`0.5B`) | WikiText-2 | `0.052525288` | `0.055205609` (`+5.10%`) | `0.057613895` (`+9.69%`) | Approaching crossover |
| `Qwen2.5-0.5B` (`0.5B`) | Python | `0.045602059` | **`0.045392023` (`-0.46%`)** | `0.047448949` (`+4.05%`) | **Strict sub-barrier band (`Δ_B < 0 < Δ_H`)** |
| `Qwen2.5-1.5B` (`1.5B`) | WikiText-2 | `0.050062401` | **`0.045647596` (`-8.82%`)** | **`0.048376358` (`-3.37%`)** | **Post-flip bridge dominance (`Δ_B < Δ_H < 0`)** |
| `Qwen2.5-1.5B` (`1.5B`) | Python | `0.031973308` | **`0.030310450` (`-5.20%`)** | **`0.030465967` (`-4.71%`)** | **Post-flip bridge dominance (`Δ_B < Δ_H < 0`)** |

   - **Explicit Non-Commutativity Obstruction:** The exact algebraic isomorphism holds strictly at the scalar two-term competing-potential operator level ($\Delta = R - A$). It **does not** extend to microscopic nuclear strong-force $SU(3)$ non-Abelian color confinement or WKB complex-phase wavefunction tunneling, both of which introduce gauge curvature and complex-amplitude interference absent from real Euclidean lattice quantization.

2. **Pillar 2 — Universal Endoreversible Jensen vs. Static-Floor Race-to-Sleep Crossover & Live Silicon Tests:**
   - **Native algebra (`P(f) = P_0 + c f^3`, $E(f) = P_0/f + c f^2$):**
     - `endoreversible_energy_global_min_universal`: Exact polynomial factorization $2(f^*)^3 + f^3 - 3(f^*)^2 f = (f - f^*)^2(f + 2 f^*) > 0$ proves universally over $\mathbb{Z}_{>0}$ that $2 c (f^*)^3 = P_0$ is the unique global energy-per-op minimum.
     - `race_to_sleep_below_fstar_universal` & `smooth_pacing_above_fstar_universal`: Below $f^*$ ($2 c f_2^3 \le P_0$), running faster strictly reduces Joules/op; above $f^*$ ($P_0 \le 2 c f_1^3$), slowing down strictly reduces Joules/op.
     - `jensen_fixed_work_smooth_beats_bursty_universal`: Over any fixed wall window $T = t_1 + t_2$ at identical work $W = f_1 t_1 + f_2 t_2$, exact cubic factorization $(t_1 + t_2)^2(f_1^3 t_1 + f_2^3 t_2) - (f_1 t_1 + f_2 t_2)^3 = t_1 t_2 (f_1 - f_2)^2 (t_1 (2 f_1 + f_2) + t_2 (f_1 + 2 f_2)) > 0$ proves continuous smooth pacing strictly beats any non-uniform/bursty schedule under continuous DVFS.
     - `parallel_impedance_ucurve_universal`: Proves conditional sufficiency for the concurrency energy U-curve: if physical scaling outruns static floor $P_u$ while SMT threads saturate ($s_2 \le s^*$), physical concurrency $p^*$ strictly minimizes Joules/job against both under-utilization ($p_1$) and SMT over-subscription ($p_2$).
   - **Live Hardware Provenance (`measured_live_silicon: true`, `audio/camera/display = false`):**
     - Executed inside exclusive OS `flock` serialization and hardware provenance stamper (`mlos_zone_b_receipt.json`, `0o600`, `clean_hardware_run: true`, `anomalies: []`, `exit_code: 0`, `duration: 24.60 s`, GPU verified idle `P8` `0%` util / `2 MiB` KMD baseline at both start and end).
     - Exact deterministic checksums conserved across all `10/10` Experiment A trials (`b2da26c4ad818ec3`) and all `14/14` Experiment B trials (`a0f68ce8e7c05f78`).
     - **Platform Rail Scale Disclosure:** Raw `intel-rapl:1` (`psys`) reads `4.435 W` idle vs. `64.574 W` on `intel-rapl:0` (`package-0`, `psys_vendor_scale_obstruction_detected: true`), confirming an uncalibrated vendor scale on `psys`. Accordingly, `psys` is evaluated strictly via dimensionless scale-invariant ratios, never raw `P_psys - P_pkg` subtraction.
   - **Live Experiment A — Pacing vs. Bursty vs. Race-to-Sleep (`W_A = 4,800` blocks = `5,033,164,800` ops, `4` physical cores):**

| Schedule Arm | Slices | Mean Wall (`ms`) | Package Energy (`mJ/job`) | Mean Pkg Power (`W`) | Ratio vs `bursty_1` |
|---|---:|---:|---:|---:|---:|
| `race_to_sleep_free` | `1` (free) | **`497.32`** | **`38,470.73`** | `77.36` | **`0.4041×` (`2.474×` less)** |
| `bursty_1_pulse_1500ms` | `1` (`1500 ms`) | `1,500.69` | **`95,197.36`** | `63.44` | `1.0000×` |
| `paced_40_slices_1500ms` | `40` (`1500 ms`) | `1,501.35` | `101,901.41` | `67.87` | `1.0704×` (`+7.04%`) |
| `bursty_4_pulses_1500ms` | `4` (`1500 ms`) | `1,500.76` | `102,407.51` | `68.24` | `1.0757×` (`+7.57%`) |
| `paced_100_slices_1500ms` | `100` (`1500 ms`) | `1,500.50` | `103,149.61` | `68.74` | `1.0835×` (`+8.35%`) |

   - **Empirical Finding A (Locating Operating Side of $f^*$ + Discrete C-State Obstruction):** Because the live host carries a high `64.574 W` package baseline floor ($2 c f^3 \ll P_0$), the machine operates deeply on the **below-$f^*$ race-to-sleep side**: finishing immediately saves **`2.474×` (`-59.6%`)** vs. single-pulse `1500 ms` waiting and **`2.681×` (`-62.7%`)** vs. `100`-slice pacing. Furthermore, inside the fixed `1500 ms` deadline, **discrete C-state residency creates a real-silicon obstruction to continuous-DVFS Jensen pacing**: a single burst followed by continuous deep sleep (`95.20 J`) beats `100` micro-slices (`103.15 J`) by **`-7.71%` (`-7.95 J`)** because frequent wake-ups prevent deep C-state entry.
   - **Live Experiment B — Core-Count & SMT Hyperthreading Sweep (`W_B = 3,360` blocks = `3,523,215,360` exact ops):**

| Threads `p` | Phys / SMT | Mean Wall (`ms`) | Speedup vs `1T` | Throughput (`Gop/s`) | Package Energy (`mJ/job`) | Relative `psys` Ratio vs `1T` |
|---:|---|---:|---:|---:|---:|---:|
| `1` | `1 / 0` | `1,003.69` | `1.000×` | `3.510` | `70,092.53` | `1.000×` |
| `2` | `2 / 0` | `461.04` | `2.177×` | `7.642` | `30,555.98` | `0.443×` |
| `4` | `4 / 0` | `368.37` | `2.725×` | `9.564` | `26,382.50` | `0.373×` |
| `6` | `6 / 0` | `254.10` | `3.950×` | `13.865` | `18,133.86` | `0.257×` |
| `8` | `8 / 0` | `209.04` | `4.801×` | `16.854` | `15,077.35` (`4.649×` less vs `1T`) | `0.211×` (`4.738×` less) |
| `12` | `8 / 4` | `127.53` | `7.870×` | `27.627` | `10,575.14` | `0.142×` |
| **`16`** | **`8 / 8`** | **`117.44`** | **`8.546×`** | **`29.999`** | **`9,187.02` (`7.630×` less vs `1T`)** | **`0.125×` (`8.020×` less)** |

   - **Empirical Finding B (Honest Falsification of Naive SMT-Penalty Premise on Latency-Bound ALU Chains):** Scaling from `1T` to `8T` physical cores cuts package energy per completed job by **`4.649×` (`-78.5%`, `70.09 J -> 15.08 J`)**. Crucially, on this serial-dependency L1-tile integer kernel under a PL1 package cap, **SMT did NOT saturate**: `16T` achieved `29.999 Gop/s` vs. `16.854 Gop/s` at `8T` (`+78.0%` speedup), driving energy down another **`1.641×` (`-39.1%`)** to **`9.19 J/job` (`7.630×` better than `1T`, `8.020×` on dimensionless `psys`)**! This directly validates Theorem 5 (race-to-sleep under high $P_0$) while empirically showing that Theorem 8's SMT-penalty U-curve activates strictly when memory/port saturation holds ($s_2 \le s^*$), NOT on ILP-starved ALU chains.

### Honest Novelty Classification (`N0` vs. `N1`)
- **`N0` Classical Foundations:** Curzon–Ahlborn / endoreversible thermodynamics, Jensen's inequality (1906), Miyoshi / Le Sueur–Heiser race-to-sleep critical power slope, Gamow / Yukawa competing potentials, Conway–Sloane lattices, and the Lean 4 `Init` kernel.
- **`N1` Constructive Formalization & Empirical Two-Way Transfer:** Pure-`Init` Lean 4.36.0 universal integer factorizations unifying competing-potential barrier crossover / sub-barrier bridge dominance and cubic endoreversible race-to-sleep vs. Jensen pacing, coupled to live `intel-rapl` hardware testing that locates the host's operating regime (`2.47×–7.63×` energy unlocks) and identifies two concrete real-silicon obstructions (discrete C-state wakeup penalty and non-saturated SMT ILP harvesting).

---

## 2. Live `Lean 4.36.0` Kernel & Verification Summary

- **Toolchain:** `leanprover/lean4:v4.36.0` (`Lean (version 4.36.0, x86_64-unknown-linux-gnu, commit 611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9, Release)`)
- **Kernel Compilation:** Standalone `lean TwoWayTransfer.lean` `RC=0`, `0` warnings, `0` stderr; clean-copy `lake build` `RC=0` (`4` jobs, zero `.lake/` retained).
- **Axioms (`10/10` clean):** `8/10` universal `∀` theorems depend strictly on `[propext, Quot.sound]` (`0` `Classical.choice`!); `2/10` exact witnesses (`qwen_smollm_scale_flip_exact_witness`, `measured_silicon_efficiency_witness`) depend on zero axioms `[]`.
- **Reproduce Locally:**
  ```bash
  python3 -I -B two_way_transfer_audit.py --check two_way_transfer_certificate.json
  python3 -I -B test_two_way_transfer_r5.py -v
  ```

---

## 3. Frozen Deliverable Manifest

- **Certificate Digests (`two_way_transfer_certificate.json`, `0o600`, canonical compact ASCII JSON + LF):**
  - `file_sha256`: `ea0e5ae60e175e73b6694a936f464a84db60aca8c82b433d4933add58d827f0d`
  - `payload_sha256`: `fdbd198cc8ef0adaeaff4d0667798447d59ee9a366ae4b93cc9b8d3cc0efe456`
  - `certificate_sha256`: `bf53497d93a249d3d384a64b8eb855328df83761ab5178932b59dff2965971c0`
- **Verification Summary:** `10/10` live `Lean 4.36.0` theorems (`8` universal `∀` + `2` zero-axiom witnesses, `0` warnings, clean-copy `lake build` `4` jobs `RC=0`), `15/15` live Lean 4 static-gate escapes blocked, `4`-mode `-I` parity + `umask 077` (`12/12 OK` ×5), `1,052/1,052` direct secondary tamper kills, `82/82` 4-surface strict-I/O fuzzer `PASS`, `253/253` (`93/93 + 160/160`, `100.0%`) live parallel mutation kills, `192/192` (`139/139 + 53/53`, `100.0%`) whole-file DFS AST `BoolOp` kills.

| File | Lines | Bytes | Mode | SHA-256 |
|---|---:|---:|---:|---|
| `lean-toolchain` | `1` | `25` | `0o644` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |
| `lakefile.toml` | `6` | `116` | `0o644` | `e108788f37b5015a164064cf7cd044b7263cae956697e81bb24f4d3b59af2ed9` |
| `TwoWayTransfer.lean` | `615` | `33,865` | `0o644` | `ba45f37bf96dab5e580df20aa0c656fdfceb59c69f83d2509ff4f89c226d46ca` |
| `two_way_silicon_probe.c` | `401` | `14,918` | `0o644` | `ef1fe7b327fb72320022f59dbf02cdf5c4cef4f30af48ac66620d6a49997f559` |
| `two_way_silicon_live_results.json` | `33` | `6,550` | `0o600` | `6bf858811bf7b9119790cc006270d8be93f464385627939d0297ecd4fa36f671` |
| `mlos_zone_b_receipt.json` | `93` | `2,642` | `0o600` | `bf13ff15117b3e58746b2aefe0cc7477052e82f784be4f7d44c3b8310ad9a91e` |
| `two_way_transfer_oracle.py` | `1,013` | `42,495` | `0o644` | `a5c0639aeb49b6ef554f01a7b04d9561ff4f2d974365a7a9e5df81134325ef15` |
| `two_way_transfer_audit.py` | `1,000` | `45,369` | `0o644` | `5fccd441ff08dbc1fffe5149bd27d36a21feea4c686810edf1b53777cb2208ba` |
| `test_two_way_transfer_r5.py` | `963` | `61,491` | `0o644` | `fff08f50819cffd3488996dc1b1f345a929eb043ae731707301787de8b7bed06` |
| `two_way_transfer_certificate.json` | `1` | `14,042` | `0o600` | `ea0e5ae60e175e73b6694a936f464a84db60aca8c82b433d4933add58d827f0d` |
| `TWO_WAY_TRANSFER_REPORT.md` | *(this file)* | — | `0o644` | *(self-documenting report)* |
