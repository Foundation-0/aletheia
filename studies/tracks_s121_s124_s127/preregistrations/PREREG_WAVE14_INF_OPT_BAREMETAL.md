# Preregistration Amendment — Wave-14 Portals (`PREREG-W14`: `sybil-solutions/inference-optimisation-skill` & `alesha-pro/llm.asm/02-baremetal-os`)

- **Date (UTC):** `2026-11-26T07:10Z`
- **Status:** `LOCKED_PRE_EXECUTION` (`SOP-12` Preregistration Amendment; mutates zero prior locked preregistrations)
- **Portals Archived:**
  - **Portal 147:** `sybil-solutions/inference-optimisation-skill @ fda968e7fc` (`★2,723`, MIT) + `SOP-9` (`22` open PRs: `#25` forecast-first, `#22` looped-model rooflines & sparse FP4 `2×` gap, `#19` MTP draft count by output type, `#12` `3.0×` loop-aware MoE placement, `#11` A/A noise floor `15/43 = 35%` false-win proof, `#9` `863k tok/s` coalesced-chunk mirage, `#13` batched draft-read fix) + `SOP-10` (`local-ai-registry`, `trellis-serve`, `exl3xpu`, `moetier`, `skill-distill`, `prefill-cost`).
  - **Portal 148:** `alesha-pro/llm.asm @ 48feccbfd5` (`★637`, MIT, `02-baremetal-os/` `24 KB` Multiboot-1 `2 MiB`-huge-page bare-metal `Qwen3-0.6B` OS, `74–94 ms` boot, `134.94 tok/s` KVM `+31%` vs `llama.cpp` / `+10%` vs Linux `mmap()`) + `SOP-9` (`PR #1 [arm64-qwen3-port]`) + `SOP-10` (`inference-optimization-playbook` `138` hypotheses on `4× RTX 3090`, `vllm-cross-model-kv` `arXiv:2608.03893` `inv_RoPE -> ridge -> target_RoPE`, `atlas`, `maya-inkling-mini`, `llama.cpp-mirai-s`, `project-maya`).

## Exact Obstructions Identified (`W14-OBS-1..3`)

- **`W14-OBS-1` (Abelian RoPE-Strip vs. Non-Abelian `SU(2)` State Transport):** `alesha-pro/vllm-cross-model-kv` (`arXiv:2608.03893`) strips Abelian scalar-phase `RoPE` per token ($O(T)$) to fit content-space ridge maps (`K R²=0.760, V R²=0.625`); by contrast, `HoloSphere` `S_fast` is $O(1)$ in $T$ (`215.58×` smaller at `T=8192`), while non-Abelian `CayleySU2` holonomy $U_t = \prod_\tau q(w_\tau)$ is path-dependent and requires a proper $SO(3)$ intertwiner ($\det R = +1$; improper reflections invert non-Abelian commutator signs).
- **`W14-OBS-2` (`24 MiB` L3-Resident Bare-Metal `HoloSphere-V3` Envelope):** `llm.asm/02-baremetal-os` requires `614 MiB` weights + `449 MiB` KV arena (`~1.06 GiB` RAM) for `Qwen3-0.6B` and gains `+10%` from `2 MiB` huge pages eliminating 4 KiB TLB walks. By contrast, live HF `ahrazzle/holosphere-v3-unified-sm86-15m` packs into `8.55 MiB` weights (`0` input emb) + `0.25 MiB` $O(1)$ persistent state = **`8.80 MiB < 24 MiB` i9-11900H L3 cache** (zero DRAM weight/KV traffic after warmup!).
- **`W14-OBS-3` (Interleaved-Triple A/A Illusion & Looped-Visit Roofline):** Naive `"candidate beats both neighbouring controls"` accepts pure i.i.d. noise with exact probability $1/3$ (`33.33%`, matching `PR #11`'s `15/43 = 34.9%`), and naive physical-layer ceilings overstate looped-core models by the loop multiplicity (`2×` on `Inkling-2-Mini`, `3.0×` VRAM ROI on looped core `PR #12/#22`).

## Pre-Registered Experiments (`EXP-Q30a..c`)

1. **`EXP-Q30a` (`Track S124` — Exact Pure-$\mathbb{Q}$ A/A Noise-Floor, Looped-Roofline & `HoloSphere-V3` Ceiling Certifier):**
   - **Oracle Class:** `exact` (zero floats, `100%` `aletheia mutate`, 3-mode `-I` parity).
   - **Hypotheses & Kill Gates:**
     - `G1`: Exact combinatorial proof over $\mathbb{Q}$ of single-triple A/B/A false-win probability $1/3$ ($2/6$ permutations), $m$-independent-triple survival $(1/3)^m$, and rank-order floor needed for $\alpha \le 0.05$ (`m >= 3` gives `1/27 = 3.70%`).
     - `G2`: Exact rational verification of looped-model visit-count decode/prefill ceilings (`PR #22`), batched single-read draft-weight correction (`PR #13`: `640` vs `400` tok/s = `37.5%` error when over-multiplied), and `3.0×` looped-core VRAM ROI (`PR #12`).
     - `G3`: Exact rational component-wise roofline for live HF `ahrazzle/holosphere-v3-unified-sm86-15m` (`8,963,044 B` packed `A_16`, `0 B` emb/LM-head table, `256 KiB` $O(1)$ state) on RTX 3080 (`356.6 GB/s` HBM / `L2`-pinned) and i9-11900H (`24 MiB` L3 vs DDR4).
   - **Controls:** R5 must-fail mutation fixtures on every inequality, `PR #9` coalesced-chunk `MIN_DECODE_WINDOW` / degenerate-alphabet guard (`863k` mirage rejection), and `PR #13` buggy `N × draft_bytes` counterexample.

2. **`EXP-Q30b` (`Track S125` — Zero-Dep C11 + `AVX-512` `VPDPBUSD` + `2 MiB` Huge-Page `HoloSphere-V3` L3-Resident CPU Engine Benchmark on i9-11900H):**
   - **Oracle Class:** `sampled` (CPU-only, `CUDA_VISIBLE_DEVICES=""`, interleaved `A/B/A` + empirical A/A noise floor from `EXP-Q30a`, UBSan + `-Wall -Wextra -Werror`, zero-shared-code FP64 parity).
   - **Hypotheses & Kill Gates:**
     - `G1`: Exact FP64 parity (`max_abs_diff <= 1e-5`, bit-identical greedy tokens across `1T`, `4T`, `8T`) for zero-dep C11 `AVX-512 VNNI` (`_mm512_dpbusd_epi32`) `A_16 Block-H4` `[16,11,4]` decode + SFU-free `CayleySU2` + `S_fast` Woodbury + `FWHT_256 × bent4` LM head at exact `HoloSphere-V3` `15M` geometry (`D=512, H=16, L=6`).
     - `G2`: Total live weight + $O(1)$ state footprint `< 12 MiB` (`< 50%` of `24 MiB` i9-11900H L3 cache) and `>= 1.5×` decode speedup over scalar C11 baseline on real `i9-11900H`, with honest interleaved `4 KiB` vs `2 MiB` `MADV_HUGEPAGE` measurement (testing whether `llm.asm`'s `+10%` huge-page gain holds inside an L3-resident `8.80 MiB` footprint or vanishes when L3 absorbs TLB misses!).
     - **Kill / Honesty Gate:** Report exact A/A noise floor (`>= 10` back-to-back control runs) before declaring any `2 MiB` huge-page win; if `MADV_HUGEPAGE` delta is within the A/A noise floor, report `NEUTRAL / L3-ABSORBED` honestly!

3. **`EXP-Q30c` (Folded into Active `Track S123`):**
   - Contrast `alesha-pro/vllm-cross-model-kv` (`arXiv:2608.03893` Abelian `inv_RoPE -> ridge -> target_RoPE`, $O(T)$) directly against `HoloSphere` $O(1)$ `S_fast` gauge transport & `W14-OBS-1` non-Abelian `SO(3)` conjugation obstruction (`det R = +1` vs `-1`).
