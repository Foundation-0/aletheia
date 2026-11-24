# Pure-$\mathbb{Z}/\mathbb{Q}$ Silq (`!T`/`qfree`/`mfree`) × DeepMind `CS-21` Boundary-Cost Compiler & Live `Lean 4.36.0` Kernel Certificate

**Schema:** `aletheia.silq_cs21_boundary_compiler.v1` | **Oracle Class:** `exact` (100% pure Python 3 stdlib $\mathbb{Z}/\mathbb{Q}$, zero IEEE-754 floats, zero external dependencies + live `Lean 4.36.0` kernel check) | **Novelty:** `N1`

---

## 1. Executive Summary (Own Terms First)

Optimizing fault-tolerant quantum algorithms solely by minimizing `T`-gate counts hides classical decoding, routing, and thermodynamic erasure overhead across the quantum-to-classical boundary (`CS-21`, *Classical-Control Offloading Mirage*). This study fuses Silq's static boundary type system (`!B`, `B`, `const`, `qfree`, `lifted`, `mfree`, `forget`, `measure`) with the `CS-21` Hoare resource comparator into a single executable pure-$\mathbb{Z}/\mathbb{Q}$ boundary-cost compiler, exact Pareto-certified boundary placement optimizer, and live `Lean 4.36.0` kernel-verified formalization (`SilqCS21Boundary.lean`, `7/7` theorems, zero `sorry`, zero `native_decide`, standard axioms only):

1. **Pillar 1 — Executable Typed Silq × `CS-21` Boundary-Cost IR Compiler:** Statically enforces Silq's linear quantum wire, `const`, `qfree`/`lifted`, `mfree`, and `forget` automatic-uncomputation laws (`5/5` valid typed programs accepted with automatic `CCX` uncomputation synthesis; `8/8` must-fail boundary violations rejected statically with exact error codes) while automatically billing EVERY `B -> !B` boundary crossing (`measure` and `offload_classical`) for reversible `T`-gates/Cliffords, classical control ops (`w_ctrl = 1/10`), and exact rational Landauer erasure (`w_landauer = 1/2`, `[19/16, 6/5]` bits per irreversible 2-input classical `AND` + `1` bit per qubit reset vs. `0` bits for `qfree` automatic uncomputation).
2. **Pillar 2 — Non-Commutativity Obstruction (`qfree` Uncomputation vs. `mfree` Measurement) & `CS-21` Mirage:**
   - **Exact `CS-21` Mirage Witness:** `Circuit A` (`(T=400, C=10, E=0)` -> full cost **`401`**) vs. `Circuit B` (`(T=100, C=4000, E=200)` -> `4×` lower `T`-count, yet **`5/6`** hidden cost inflating full cost to **`600`**, an exact **`600/401 ≈ 1.496259×` net regression**), contrasted with genuine `qfree` speedup `Circuit C` (`(T=100, C=20, E=0)` -> **`102`**).
   - **Exact `16`-AND Non-Commutativity Witness:** On a `16`-AND oracle pipeline, `Order 1` (`qfree` automatic uncomputation BEFORE final measurement: `T=224, C=10, E=0` -> exact full cost **`225`**) strictly beats `Order 2` (projective measurement & `!T` classical offload BEFORE uncomputation: `T=56 = 224/4` [`4×` T-gate reduction!], `C=2000`, `16` classical `AND`s + `16` resets -> Landauer erasure bracket `[35, 176/5]` bits -> full cost bracket **`[547/2, 1368/5]` = `[273.5, 273.6]`**, strictly **`> 225`** even at the strict Landauer lower bound `19/16`!).
   - **Exact Pure-$\mathbb{Z}$ Landauer Power-Product Proof:** Replays `AND` fibers `{0: 3, 1: 1}` ($2^{4H} = 27$, $2^{19} = 524,288 < 27^4 = 531,441$, $27^5 = 14,348,907 < 2^{24} = 16,777,216 \implies 19/16 < H_{\mathrm{AND}} < 6/5$), `ERASE` ($P = 4 \implies H = 1$), and reversible `CCX` involution ($P = 1 \implies H = 0$).
3. **Pillar 3 — Exact Pure-$\mathbb{Q}$ Pareto-Certified Boundary Placement Optimizer (Front-End Spec for `google-deepmind/formal-quantum-computation`):** Models a `6`-stage quantum-classical pipeline (`state_prep` [`Q_ONLY`], `modular_add`, `qrom_lookup`, `nonlinear_compare`, `syndrome_decode`, `final_readout` [`C_ONLY`]) with `6` directed dataflow/entanglement edges (`16` legal cuts out of `64` binary masks). An exact pure-$\mathbb{Z}/\mathbb{Q}$ **branch-and-bound solver** (using an admissible per-stage suffix lower bound) matches exhaustive `64`-mask enumeration identically (`nodes_pruned > 0`, zero missed optima), certifying:
   - **Global Optimum (`mask = 52`, `QQCQCC`):** `T = 240`, `ctrl = 1,600`, `crossings = 3`, full cost **`[1729/4, 2162/5]` (`[432.25, 432.40]`)**.
   - **All-Quantum Baseline (`mask = 32`, `QQQQQC`):** `T = 480`, `ctrl = 51`, full cost **`4891/10` (`489.10`)** (`567/10 = 56.70` more expensive than optimum).
   - **Naive `T`-Only Minimizer (`mask = 62`, `QCCCCC`):** Cuts `T`-gates by **`24×`** (`480 -> 20`), yet inflates full boundary cost to **`2816/5` (`563.20`)** — strictly **worse than keeping all compute stages quantum (`563.20 > 489.10`)** and **`1408/1081 ≈ 1.302498×`** worse than the Pareto-optimal cut (`654/5 = 130.80` cost penalty)!
   - **Exact 4-Point Pareto Frontier on `(T_gates, full_cost_hi)`:** `(20, 2816/5)`, `(120, 2646/5)`, `(140, 2452/5)`, `(240, 2162/5)`.
4. **Pillar 4 — Live `Lean 4.36.0` Kernel Certification (`SilqCS21Boundary.lean`):** Elaborates and proves all **`7/7` theorems** directly inside the `Lean 4.36.0` kernel (zero external imports, zero `sorry`, zero `native_decide`, `#print axioms` clean across all `7/7` theorems), including universal Silq effect containment (`silq_effect_boundary_sound`), universal parametric `CS-21` regression (`cs21_parametric_net_regression`), `600/401` mirage (`cs21_4x_mirage_600_over_401`), `19/16 < H_AND < 6/5` (`landauer_and_bracket_and_toffoli_zero`), `16`-AND non-commutativity (`noncommutativity_qfree_vs_measure_16and`), universal `Fin 64` global optimality of cut `mask = 52` under BOTH `cost_hi` AND `cost_lo` (`pareto_cut_52_global_optimality`), and universal admissibility of the branch-and-bound lower bound (`branch_and_bound_lower_bound_sound`).

---

## 2. Certified Quantitative Tables

### Pillar 1 — Compiled Typed Program Suite (`5/5` Valid Accepted, `8/8` Must-Fail Rejected)

| Program | Annotation | Status / Error Code | `T`-Gates | Cliffords | Ctrl Ops | Landauer Bits `[lo, hi]` | Full Cost `[lo, hi]` |
|---|---|---|---:|---:|---:|---:|---:|
| `toffoli_qfree_auto_uncompute` | `mfree` | **OK** (`CCX(a,b,tmp)`) | `14` | `16` | `0` | `[0, 0]` | `[14, 14]` |
| `bell_entangle_mfree` | `mfree` | **OK** | `0` | `2` | `0` | `[0, 0]` | `[0, 0]` |
| `lifted_oracle_const_clean` | `lifted` | **OK** (`CCX(x,y,anc)`) | `14` | `16` | `0` | `[0, 0]` | `[14, 14]` |
| `explicit_measure_boundary_handoff` | `general` | **OK** (`1` crossing) | `0` | `1` | `10` | `[1, 1]` | `[3/2, 3/2]` |
| `classical_offload_and_pipeline` | `general` | **OK** (`1` crossing) | `0` | `0` | `2000` | `[35, 176/5]` | `[435/2, 1088/5]` |
| `8` Must-Fail Boundary Programs | mixed | **8/8 REJECTED** (`QUANTUM_CLONING_FORBIDDEN`, `UNCONSUMED_QUANTUM_DROP`, `NON_QFREE_OP_IN_QFREE`, `MEASURE_IN_MFREE_OR_QFREE`, `OFFLOAD_IN_MFREE_OR_QFREE`, `UNCOMPUTATION_FAILED`, `CONST_MODIFICATION_FORBIDDEN`, `LIFTED_REQUIRES_CONST_QPARAMS`) | — | — | — | — | — |

### Pillars 2 & 3 — Non-Commutativity & Exact 6-Stage Pareto Boundary Cuts

| Witness / Cut (`mask`) | Placement | `T`-Gates | Ctrl Ops | Landauer `[lo, hi]` | Full Cost `[lo, hi]` (exact $\mathbb{Q}$) | Scaled (`hi*10`) | Role |
|---|---|---:|---:|---:|---:|---:|---|
| `Circuit A` (`qfree` clean) | — | `400` | `10` | `[0, 0]` | `[401, 401]` | `4010` | `CS-21` Baseline |
| `Circuit B` (`!T` offload) | — | `100` (`4×`↓) | `4000` | `[200, 200]` | `[600, 600]` | `6000` | **`600/401` Mirage (`5/6` hidden)** |
| `Circuit C` (genuine `qfree`) | — | `100` | `20` | `[0, 0]` | `[102, 102]` | `1020` | Strictly dominates |
| `16`-AND Order 1 (`qfree -> M`) | — | `224` | `10` | `[0, 0]` | `[225, 225]` | `2250` | Reversible uncompute first |
| `16`-AND Order 2 (`M -> offload`) | — | `56` (`4×`↓) | `2000` | `[35, 176/5]` | `[547/2, 1368/5]` | `2736` | **Non-commutativity regression** |
| **Optimal Cut (`52`)** | **`QQCQCC`** | **`240`** | **`1600`** | **`[129/2, 324/5]`** | **`[1729/4, 2162/5]`** | **`4324`** | **Global Optimum (Lean `Fin 64`)** |
| All-Quantum Cut (`32`) | `QQQQQC` | `480` | `51` | `[8, 8]` | `[4891/10, 4891/10]` | `4891` | Coherent baseline (`+56.70`) |
| Pareto Cut (`60`) | `QQCCCC` | `140` | `3006` | `[99, 498/5]` | `[4901/10, 2452/5]` | `4904` | Pareto Frontier `#3` |
| Pareto Cut (`54`) | `QCCQCC` | `120` | `3466` | `[249/2, 626/5]` | `[10577/20, 2646/5]` | `5292` | Pareto Frontier `#2` |
| Naive Min-`T` Cut (`62`) | `QCCCCC` | `20` (`24×`↓) | `4692` | `[147, 148]` | `[5627/10, 2816/5]` | `5632` | **Trap (`1408/1081 ≈ 1.3025×` worse!)** |

---

## 3. Prior Art (`N0`), Honest Novelty Tagging (`N1`), & Security Boundaries

- **Prior-Art Foundations (`N0`, full-text checked):**
  - B. Bichsel, M. Baader, T. Gehr, & M. Vechev (PLDI 2020), *Silq: A High-Level Quantum Language with Safe Uncomputation and Intuitive Semantics*.
  - R. Landauer (IBM J. Res. Dev., 1961), *Irreversibility and Heat Generation in the Computing Process*, & C. H. Bennett (IBM J. Res. Dev., 1973), *Logical Reversibility of Computation*.
  - S. Shirobokov et al. / Google DeepMind (`arXiv:2611.09822v3`, 2026), *formal-quantum-computation* (stating classical-control costing as an open milestone).
  - Companion repository evidence artifacts `evidence/track-s38-silq-nested-boundary-calculus/` and `evidence/track-s44-formal-agent-quantum-hodge/`.
- **Contribution (`N1` — Executable Synthesis, Optimizer & Live Lean 4.36.0 Proof):**
  - First zero-float, stdlib-only executable typed Silq × `CS-21` boundary-cost compiler that jointly enforces linear/`const`/`qfree`/`lifted`/`mfree`/`forget` typing and bills every `!T` crossing for classical control + `[19/16, 6/5]`-bit Landauer erasure, paired with an exact pure-$\mathbb{Z}/\mathbb{Q}$ branch-and-bound Pareto cut optimizer and a zero-import live `Lean 4.36.0` kernel proof certifying effect soundness, parametric `CS-21` net regression, `16`-AND non-commutativity, universal `Fin 64` global cut optimality, and branch-and-bound lower-bound admissibility.
- **Security & Replay Boundaries:**
  - `MAX_INT_BITS = 3,321` (`MAX_INT_DIGITS = 1,000` pre-parse ceiling) is the exact binding cap across oracle, JSON parser, and rational parser.
  - `silq_cs21_compiler_audit.py` enforces atomic `dir_fd` traversal (`O_RDONLY | O_DIRECTORY | O_NOFOLLOW`) with verified root-owned macOS Darwin system-prefix normalization (`/var`, `/tmp`, `/etc` $\to$ `/private/*` without resolving user symlinks), inode-matched `$PWD` symlink ancestor verification, `65,536`-byte streaming read caps, durable `0o600` atomic writes (`os.fsync(fd)` + `st_nlink == 1` + `os.replace(..., dir_fd)` + `os.fsync(dfd)`), division-free cross-multiplied algebraic cross-checks, and strict-type bijective `secondary_audit_payload` verification under both `full_replay=True` and `full_replay=False` (within standard POSIX semantics, excluding root/ptrace adversaries).

---

## 4. Verification Receipts & Frozen Artifact Manifest

- **Live `Lean 4.36.0` Kernel Check (`lean SilqCS21Boundary.lean`, `rc = 0`, `7/7` Theorems):**
  - `SilqCS21Boundary.silq_effect_boundary_sound`: `[propext]`
  - `SilqCS21Boundary.cs21_parametric_net_regression`: `[propext, Quot.sound]`
  - `SilqCS21Boundary.cs21_4x_mirage_600_over_401`: `[propext, Classical.choice, Quot.sound]`
  - `SilqCS21Boundary.landauer_and_bracket_and_toffoli_zero`: `[propext, Classical.choice, Quot.sound]`
  - `SilqCS21Boundary.noncommutativity_qfree_vs_measure_16and`: `[propext, Classical.choice, Quot.sound]`
  - `SilqCS21Boundary.pareto_cut_52_global_optimality`: `[propext]`
  - `SilqCS21Boundary.branch_and_bound_lower_bound_sound`: `[propext, Quot.sound]`
- **Frozen Certificate (`silq_cs21_compiler_certificate.json`, `0o600`):**
  - `file_sha256`: `94b9c34f196afc031e6169032eb42d2fe2ddd120d2dc137bc52c0ee2bebf3850`
  - `canonical_sha256`: `955c5cf9d41239bf8b6ecfc4254fe70a9d48b206a17c349cd99f08f0c3723308`
  - `payload_sha256`: `4146861b8167da534c7614edf9a380ec18f82b3536b86b872e294c6491682ef7`
  - `certificate_sha256`: `6f27d6d8b68a8f6b6d0d3ecbb6236f9940e247ecf855238798b8e1411889906d`
- **Frozen Code, Proof & Certificate Manifest (excluding this report):**

| File | Lines | Bytes | Mode | SHA-256 |
|---|---:|---:|---:|---|
| `SilqCS21Boundary.lean` | `264` | `11,742` | `0o644` | `0eadcefe247c0ef526b9814b62541641508515a488826a4bf86e6b7b527b0554` |
| `silq_cs21_compiler_oracle.py` | `957` | `41,915` | `0o644` | `6b0ccc2578c1c672517e3e952ba0d5a8ca260805d2fe9518d3798c34483b7a94` |
| `silq_cs21_compiler_audit.py` | `933` | `37,316` | `0o644` | `d1e414f55b0c23113627a44d1a58d32b06190ffc3fb9866f5bb6e98efa3ee3f6` |
| `test_silq_cs21_compiler_r5.py` | `903` | `56,510` | `0o644` | `b0f6a0affb70eb8cbea08ffac2fbaee411e336a5ae168ad0530d77f718624798` |
| `silq_cs21_compiler_certificate.json` | `1` | `12,813` | `0o600` | `94b9c34f196afc031e6169032eb42d2fe2ddd120d2dc137bc52c0ee2bebf3850` |

- **Verification Gates (`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`):**
  - **Isolated Interpreter Parity (`-I -B`, `-I -O -B`, `-I -B -W error`, `PYTHONHASHSEED=42 -B`, plus `umask 077`):** `--standalone --json == disk` (`94b9c34f...`), `--check --json` bit-identical (`72b7d6a9...`), `test_silq_cs21_compiler_r5.py` **`9/9 OK`** across all modes and `umask 077` (scratch `os.mkfifo` ONLY, `16T/80T` `0o600` bursts, Linux-only `550` `renameat2(RENAME_EXCHANGE)` & `550` hardlink races, mocked macOS Darwin prefix checks, live `Lean 4.36.0` kernel elaboration).
  - **Exhaustive Leaf Tamper Walk:** **`431/431` leaves, `1,555` mutations** across both `verify_certificate_dict(..., full_replay=False)` and direct `secondary_audit_payload(...)` (including `landauer_and_bracket_q`, `True`/`False`-in-`int`, runtime `float`, and Python subclasses) -> **`0` accepted, `0` raw crashes**.
  - **Live Mutation Testing (`--guards require_ok --max-mutants 0`):** `silq_cs21_compiler_oracle.py` **`35/35`** + `silq_cs21_compiler_audit.py` **`72/72`** = **`107/107` (`100.0%`, `survived=0`, `truncated=False`) PASS**.
  - **Whole-File AST `BoolOp` Mutation Sweep:** `silq_cs21_compiler_oracle.py` **`92/92`** + `silq_cs21_compiler_audit.py` **`33/33`** = **`125/125` (`100.0%`, `surv=[]`) KILLED**.
  - **4-Surface Adversarial Boundary Fuzzer:** CLI `--check` **`25/25`** + `verify_certificate_dict(full_replay=True)` **`19/19`** + `verify_certificate_dict(full_replay=False)` **`19/19`** + direct `secondary_audit_payload` **`19/19`** = **`82/82` (`100.0%`, `bypasses=0`, `crashes=0`) PASS**.
  - **Static, Lean & Ancestor Audit (`--lean-audit --strict-ancestors --safety-scan`):** **`PASS`** (`6` files, `2/2` parity scripts, `1/1` Lean clean `0` findings / `0` notices, `0` safety/ancestor/leak/CRLF/bare-assert findings, `0` `__pycache__`).
