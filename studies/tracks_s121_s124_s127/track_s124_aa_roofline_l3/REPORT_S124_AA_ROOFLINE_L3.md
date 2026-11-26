# `Track S124` (`EXP-Q30a`) — Pure-$\mathbb{Q}$ A/A Noise-Floor, Looped-Visit Roofline, & `HoloSphere-V3` `24 MiB` L3 Ceiling Oracle

- **Protocol Anchor:** `PREREG-W14` (`PREREG_WAVE14_INF_OPT_BAREMETAL.md`, SHA-256: `871900e5d6c860ac159f43ca6b4767e7c128d0b4f7748edf788d56e9cb535d3e`)
- **Oracle Class:** **`exact`** (`0` IEEE-754 floats, `0` float literals in AST across both oracle and test suite, `100.0%` `aletheia mutate`, 3-mode `-I` deterministic parity)
- **Literal Law-4 Verdicts:** **`G1 = CONFIRMED`**, **`G2 = CONFIRMED`**, **`G3 = CONFIRMED`**

---

## 1. `G1` (`W14-OBS-3`) — Exact $S_3$ Interleaved-Triple A/A Illusion & Coalesced-Mirage Gate (`PR #11` & `PR #9`)

1. **Exact Combinatorial Proof over $\mathbb{Q}$ (`PR #11`):**
   - Over all $|S_3| = 6$ strict rank permutations of `(ctl_left, cand, ctl_right)` under exchangeable continuous i.i.d. noise, `cand > max(ctl_left, ctl_right)` holds on exactly **`2 / 6 = 1 / 3`** (`33.33%`) of triples — matching `sybil-solutions/inference-optimisation-skill#11`'s measured **`15 / 43`** (`34.88%`, exact deviation `15/43 - 1/3 = 2/129`) on 45 unchanged Mac Studio M4 Max runs.
   - Across $m$ independent `ctl / cand / ctl` triples, the joint false-win rate is **`(1/3)^m`**: $m = 1 \mapsto 1/3$, $m = 2 \mapsto 1/9 > 1/20$, and **`m = 3 \mapsto 1/27` (`3.70% <= 5.00%`)** is the exact minimum independent-triple count for $\alpha = 1/20$.
2. **Fail-Closed Pure-$\mathbb{Q}$ Benchmark Gate (`evaluate_decode_benchmark_gate_q`):**
   - Enforces `>= 10` A/A calibration runs (`INSUFFICIENT_AA_RUNS`), **`m >= 3` independent interleaved `ctl / cand / ctl` triples** (`INSUFFICIENT_INDEPENDENT_TRIPLES`, guaranteeing $\alpha \le 1/27 = 3.70\% \le 5\%$), a **strictly positive calibrated empirical floor** (`sf * max(max_false_win_rel_margin, max_adjacent_rel_spread, min_rel_floor_q > 0)` — never collapsing to `0` on monotone/constant zero-false-win A/A ledgers, rejecting both `+1%` sub-floor runs against `77/5000 = 1.54%` A/A noise and `+0.1%` jitter on `false_wins == 0` ledgers while accepting genuine `+25%` wins), `MIN_DECODE_WINDOW = 1/20 s` (`COALESCED_CHUNK_MIRAGE`: rejects `PR #9`'s `64`-token / `7e-5 s` `863k–900k tok/s` single-chunk mirage on a `20 tok/s` M1 Max; requires `>= 2,325` tokens at `46,468 tok/s`), and character-alphabet diversity (`DEGENERATE_OUTPUT_ALPHABET`: rejects whitespace-free `64 * '!'` collapse that bypassed word-ngram `looping()`).

---

## 2. `G2` — Exact Looped-Visit, MoE VRAM-ROI, & Batched-Draft Rooflines (`PR #22`, `PR #12`, `PR #13`)

| Open PR Source | Physical vs. True Operator Accounting | Exact Rational Result Certified |
| :--- | :--- | :--- |
| **`PR #22`** (`Inkling-2-Mini` looped rooflines) | `6` prelude + `12 × 3` looped core + `6` postlude = **`48` visits** vs. `24` physical layers (`0.1 GB/visit`); `2:4`-sparse spec peak vs. dense GEMM peak | Decode overstatement **`2/1`** (**`2350/3 ≈ 783.3` vs `1175/3 ≈ 391.7 tok/s`** @ `1880 GB/s`); prefill sparse-phys vs. dense-visit overstatement **`4/1`** |
| **`PR #12`** (Loop-aware MoE `-ot` VRAM ROI) | Top-`8 / 128` (`1/16`) active experts: `1×` boundary (`3.44 GB` pre + `4.46 GB` post) vs. `3×` looped core (`6.88 GB`) | Core **`375/2 = 187.5 MB/tok/GB`** vs. boundary **`125/2 = 62.5 MB/tok/GB`** = exact **`3/1` ROI**; core carries **`1032/1427` (`72.32%`)** of active expert traffic (`1,290` / `1,783.75 MB/tok`) |
| **`PR #13`** (Batched single-read draft weights) | `N = 4` requests, `k = 1` draft, `a = 2` accepted/req (`8` emitted tok/step), `1 GB` verify + `1/4 GB` draft @ `100 GB/s` | True step read **`5/4 GB -> 640/1 tok/s`** vs. buggy `N × draft` **`2/1 GB -> 400/1 tok/s`** = exact **`3/8` (`37.5%`)** underestimate |

---

## 3. `G3` (`W14-OBS-2`) — Per-Component Roofline & `24 MiB` L3 Residency for Live HF `ahrazzle/holosphere-v3-unified-sm86-15m`

Exact byte-for-byte audit of `model.safetensors` (`8,963,044 B` = `14,176 B` header + `8,948,868 B` tensor payload across `945,280` `[16,11,4]` `A_16` codewords, `15,234,817` active params):
- **Component Breakdown:** `input_embedding = 0 B` (`H_256 × bent4`), `byte_conv = 8,192 B`, `6 × CellOp/Ring/Holonomy = 4,718,592 B`, `6 × SwiGLU FFN = 4,147,200 B`, `lm_head = 74,880 B` (`0 B` in `v3_d512` tied `FWHT_256 × bent4` mode), `logit_scale = 4 B`, plus **`262,144 B` (`256 KiB`) $O(1)$ persistent state** (`kv_bytes_per_token = 0 B`).
- **L3 Cache Residency vs. `alesha-pro/llm.asm/02-baremetal-os` (`Qwen3-0.6B`):**
  - Total live resident footprint (`file + state`): **`9,225,188 B` (`2,306,297 / 262,144 MiB ≈ 8.80 MiB`)**, occupying **`2,306,297 / 6,291,456` (`36.66%`) of the `24 MiB` (`25,165,824 B`) `i9-11900H` L3 cache** (`5` `2 MiB` huge pages / `2,253` `4 KiB` pages), vs. `llm.asm` `Qwen3-0.6B`'s `614 MiB + 449 MiB = 1,063 MiB` (`1.038 GiB` / `1.115 GB`; `278,659,072 / 2,306,297 ≈ 120.83×` larger; `532` `2 MiB` huge pages / `272,128` `4 KiB` pages).
- **Exact Hardware Decode Ceilings:**
  - **RTX 3080 Laptop GPU (`GA104M`, `sm_86`):** Unpinned GDDR6 (`356.6 GB/s`) caps single-stream decode at `89,150,000,000 / 2,368,289 ≈ 37,643.2 tok/s` (`37,943.1 tok/s` tied `0 B` head), whereas empirical `ScopedAmpereL2Pin` (`525.46 GB/s`, `Track S116`) lifts the ceiling to **`131,365,000,000 / 2,349,569 ≈ 55,910.3 tok/s`** — proving our live `46,468 tok/s` (`v3_d512` CUDA graph) reaches **`122.47%` (`1.225×`) of unpinned GDDR6** and **`83.11%` of the L2-pinned ceiling**!
  - **Intel Core `i9-11900H` (`24 MiB` L3 vs. DDR4-3200):** L3 residency lifts bandwidth ceiling by exact **`160 / 21` (`7.62×`)** from `4,433.6 tok/s` (`42 GB/s` DDR4) to `33,779.7 tok/s` (`320 GB/s` 8C L3; `6,755.9 tok/s` 1C L3), shifting single-core execution decisively into the compute/SWAR-unpack regime (**`33,600,000,000 / 15,234,817 ≈ 2,205.5 tok/s`** 1C 50% practical FP32 FMA ceiling on client Willow Cove `1 × 512`-bit `32 FP32 FLOPs/cycle` < `6,755.9 tok/s` 1C L3 bandwidth ceiling; `Track S125` accelerates decode via `AVX-512 VNNI` `VPDPBUSD`).
