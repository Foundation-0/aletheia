# Track S38 — Portal 36: Nested Simulation & `silq-lang/silq` Boundary-Typing Calculus Over Exact $\mathbb{Z}[\frac{1}{\sqrt{2}}, i]$

- **Track ID:** `TRACK-S38-SILQ-NESTED-BOUNDARY-CALCULUS`
- **Schema:** `aletheia.silq_boundary_calculus.certificate.v1`
- **Novelty Classification:** `N1` (unified pure-$\mathbb{Z}/\mathbb{Q}$ exact $\mathbb{D}[i,\sqrt{2}]$ Clifford+T engine, executable core Silq static boundary type-checker, exact reduced-density partial-trace uncomputation equivalence, and pure-$\mathbb{Z}$ Landauer/nested-simulation certification)
- **Prior Literature Anchors (`N0`):**
  - Bichsel, Baader, Gehr & Vechev, *"Silq: A High-Level Quantum Language with Safe Uncomputation and Intuitive Semantics"*, PLDI 2020 (`N0`).
  - Landauer, *"Irreversibility and Heat Generation in the Computing Process"*, IBM J. Res. Dev. 1961 (`N0`).
- **Arithmetic & Dependencies:** Pure Python 3 standard library (`int`, `fractions.Fraction`); `0` AST float literals, `0` `float()` calls, `0` bare `assert` statements, `0` `.isdigit()`/`.isnumeric()`/`.isdecimal()` calls, `0` mathematical/Monte-Carlo RNG calls (`secrets.token_hex(8)` used exclusively for collision-free atomic temp file naming under concurrent writers), `0` external dependencies across all three Python modules (`silq_boundary_calculus_oracle.py`, `silq_boundary_calculus_audit.py`, `test_silq_boundary_calculus_r5.py`).

## Certified Digests & Artifact Manifest

| Digest | SHA-256 |
| --- | --- |
| `payload_sha256` | `09c3bc57ea7a14ba37fdd72ce0d431173a946af01b7f9220765a44aa857f09de` |
| `certificate_sha256` | `4e6a9385a078926735dc74bd83c1094dd1181e1753d6be845835dfffe98b3a2e` |
| `canonical_sha256` (no trailing LF) | `4e9bd6427b1304775542788c95fd240effdd1ae699f0cfd2e631d83ccd8b5dcb` |
| `file_sha256` (`silq_boundary_calculus_certificate.json`) | `4d924ecbad830f49298488c46f792d828101e1c66d4cab27e0cb6b09b2cc9a21` |

| Frozen Code / Certificate Artifact | Lines | Bytes | SHA-256 |
| --- | --- | --- | --- |
| `silq_boundary_calculus_oracle.py` | `1682` | `70220` | `764df2a1cde2ce4bc5a8fff363baabe769fd8abe7b789775741de3f68ad06127` |
| `silq_boundary_calculus_audit.py` | `812` | `35766` | `ba816861cef49b0a05a02e9af038a3d1a4004b48adb033caf1d7c96c43ff5c7c` |
| `test_silq_boundary_calculus_r5.py` | `1092` | `73332` | `bf823187ad40d9c99f4755c11b6c779a0c1e2e056ac93284ff62120eb71938e9` |
| `silq_boundary_calculus_certificate.json` | `1` | `11152` | `4d924ecbad830f49298488c46f792d828101e1c66d4cab27e0cb6b09b2cc9a21` |

---

## Pillar 1 — Exact Dyadic Cyclotomic Ring $\mathbb{D}[i, \sqrt{2}] = \mathbb{Z}[\frac{1}{2}, \sqrt{2}, i]$ (`Clifford + T` Engine)

1. **Exact Ring Representation:** Every quantum amplitude is represented without floating-point approximation as an exact 4-tuple $(a, b, c, d) \in \mathbb{Q}^4$ denoting
   $$z = (a + b\sqrt{2}) + i(c + d\sqrt{2}), \qquad |z|^2 = z\bar{z} = (a^2 + 2b^2 + c^2 + 2d^2) + 2(ab + cd)\sqrt{2} \in \mathbb{Q}[\sqrt{2}].$$
   In particular, $\frac{1}{\sqrt{2}} = (0, \frac{1}{2}, 0, 0)$ and $\omega_8 = e^{i\pi/4} = (0, \frac{1}{2}, 0, \frac{1}{2})$, so the entire `Clifford + T` universal gate set lies strictly inside the dyadic cyclotomic ring $\mathbb{D}[i, \sqrt{2}]$ (all denominators powers of `2`).
2. **Unitarity & Group Relations Certified Live:**
   - All **9/9** canonical gates (`X`, `Y`, `Z`, `H`, `S`, `T`, `CNOT`, `CZ`, `CCX`) satisfy exact unitarity $U^\dagger U = I$ (hence $U U^\dagger = I$ for finite square matrices over $\mathbb{Q}(\sqrt{2}, i)$) and exact dyadic membership.
   - All **14/14** group relations verified by exact matrix multiplication: `X^2 = I`, `Y^2 = I`, `Z^2 = I`, `H^2 = I`, `T^2 = S`, `S^2 = Z`, `T^4 = Z`, `T^8 = I`, `H X H = Z`, `H Z H = X`, `CNOT^2 = I`, `CZ^2 = I`, `(I ⊗ H) CNOT (I ⊗ H) = CZ`, `CCX^2 = I`.
   - **Negative control:** Non-unitary shear `[[1, 1], [0, 1]]` is cleanly rejected (`is_unitary_cyc == False`).
3. **Exact Born Probability Conservation (Zero Floats):** All 4 Clifford+T witnesses satisfy exact unit norm `(sum_q, sum_sqrt2) = (1, 0)` and exact algebraic non-negativity $u + v\sqrt{2} \ge 0$:
   - `bell_pair` ($\text{CNOT}(H \otimes I)|00\rangle$): `[1/2, 0, 0, 1/2]`.
   - `magic_HTH_ket0` ($H T H |0\rangle$): $P(|0\rangle) = \frac{1}{2} + \frac{1}{4}\sqrt{2}$, $P(|1\rangle) = \frac{1}{2} - \frac{1}{4}\sqrt{2}$ (exact positivity $\frac{1}{4} \ge \frac{1}{8}$, exact sum `(1, 0)`).
   - `ghz_3q`: `[1/2, 0, 0, 0, 0, 0, 0, 1/2]`.
   - `toffoli_superposed` ($\text{CCX}(H \otimes H \otimes I)|000\rangle$): `[1/4, 0, 1/4, 0, 1/4, 0, 0, 1/4]`.

---

## Pillar 2 — Executable Static `silq-lang/silq` Core Type-Checker (`!B`, `B`, `const`, `qfree`, `lifted`, `mfree`, `forget`, `measure`)

`typecheck_silq_program` implements a zero-float static type-checker enforcing all four core Silq safety laws (Bichsel et al., PLDI 2020 `N0`):
- **Classical `!B` vs Linear Quantum `B`:** Classical `!B` variables may be freely duplicated (`dup`) and dropped; quantum `B` variables forbid cloning (`QUANTUM_CLONING_FORBIDDEN`) and forbid silent dropping (`UNCONSUMED_QUANTUM_DROP`).
- **`qfree` & `lifted`:** `qfree` permits reversible basis operations (`X`, `CNOT`, `CCX`, `lifted_and`) and rejects superposition/phase gates (`NON_QFREE_OP_IN_QFREE`) and measurement (`MEASURE_IN_MFREE_OR_QFREE`). `lifted` additionally requires every quantum parameter to be `const` (`LIFTED_REQUIRES_CONST_QPARAMS`).
- **`mfree`:** Permits unitary operations (`H`, `T`, `CZ`, `phase`, `CNOT`, `CCX`) and rejects `measure` (`MEASURE_IN_MFREE_OR_QFREE`).
- **`const`, Control Arity & Automatic Uncomputation (`forget` / LIFO Block Exit):** Mutating (`X`, `CNOT`, `CCX`, `H`, `Y`), applying unitary/phase gates (`Z`, `S`, `T`, `CZ`, `phase`), returning (`CONST_CONSUMPTION_FORBIDDEN`), or measuring a `const` quantum `B` parameter is rejected; classical `!B` wires are forbidden as controls on `lifted_and`, `qfree_gate`, and `unitary_gate` (`TYPE_MISMATCH`); and exact gate control arities (`X`/`Y`/`Z`/`H`/`S`/`T`/`phase`: `0`, `CNOT`/`CZ`: `1`, `CCX`: `2`) are enforced (`GATE_ARITY_MISMATCH`). A `lifted_and` temporary (`tmp := a & b`) is automatically uncomputed (synthesizing `CCX(a,b,tmp)`) iff neither its dependencies `(a, b)` nor `tmp` itself were mutated by a non-diagonal or `qfree` gate (`UNCOMPUTATION_FAILED` on explicit `forget`, `UNCONSUMED_QUANTUM_DROP` on block exit).

| Suite | Count | Certified Programs & Verdicts |
| --- | --- | --- |
| **Valid Typed Programs** | `6/6` | `bell_pair_mfree` (`mfree` $\to [B, B]$), `deutsch_jozsa_kickback_mfree` (`mfree` $\to [B, B]$), `toffoli_lifted_auto_uncompute` (`mfree` $\to []$, synthesizes `CCX(a,b,tmp)`), `grover_2q_diffusion_mfree` (`mfree` $\to [B, B]$), `observe_4d_slice_explicit_measure` (`general` $\to [B, !B]$), `classical_dup_and_lifted_oracle` (`lifted` $\to [B]$) |
| **Must-Fail Ill-Typed Programs** | `7/7` | `fail_silent_drop_entangled_H` (`UNCONSUMED_QUANTUM_DROP`), `fail_clone_quantum_wire` (`QUANTUM_CLONING_FORBIDDEN`), `fail_H_inside_qfree` (`NON_QFREE_OP_IN_QFREE`), `fail_measure_inside_mfree` (`MEASURE_IN_MFREE_OR_QFREE`), `fail_forget_after_dep_mutated` (`UNCOMPUTATION_FAILED`), `fail_modify_const_param` (`CONST_MODIFICATION_FORBIDDEN`), `fail_nonconst_param_in_lifted` (`LIFTED_REQUIRES_CONST_QPARAMS`) |

---

## Pillar 3 — Exact Uncomputation vs. Garbage Entanglement & Portal 35 Partial-Trace Theorem

For a bipartite state $|\Psi\rangle_{OH}$ split into observed register $O$ and hidden/garbage register $H$, exact reduced density matrix $\rho_O = \operatorname{Tr}_H(|\Psi\rangle\langle\Psi|)$, purity $\operatorname{Tr}(\rho_O^2) \in \mathbb{Q}$, and linear entropy $S_L(\rho_O) = 1 - \operatorname{Tr}(\rho_O^2) \in \mathbb{Q}$ are computed live in $\mathbb{D}[i, \sqrt{2}]$ (confirming exact Hermiticity $\rho_O^\dagger = \rho_O$, $\operatorname{Tr}(\rho_O) = 1$, and vanishing imaginary and $\sqrt{2}$ parts):

| Circuit & Boundary Condition | $\dim(\rho_O)$ | Exact Purity $\operatorname{Tr}(\rho_O^2)$ | Exact Linear Entropy $S_L$ | Exact Diagonal Probabilities | Effect on Interference |
| --- | --- | --- | --- | --- | --- |
| **Deutsch–Jozsa (`O=[0], H=[1]`) + Silq `forget(H)`** | `2` | **`1`** | **`0`** | `["0", "1"]` | **100% preserved** (`P(\|1>) = 1`) |
| **Deutsch–Jozsa (`O=[0], H=[1]`) — Dropped Garbage `H`** | `2` | **`1/2`** | **`1/2`** | `["1/2", "1/2"]` | **100% destroyed** (`\rho_O = I/2`) |
| **3-Qubit Toffoli–Grover (`O=[0,1], H=[2]`) + Silq `forget(tmp)`** | `4` | **`1`** | **`0`** | `["0", "0", "0", "1"]` | **100% preserved** (`P(\|11>) = 1`) |
| **3-Qubit Toffoli–Grover (`O=[0,1], H=[2]`) — Dropped Garbage `tmp`** | `4` | **`5/8`** | **`3/8`** | `["1/8", "1/8", "1/8", "5/8"]` | **Degraded** (`3/8` leaked to wrong states) |

This establishes quantitatively that Silq's compile-time automatic uncomputation law (`forget`) and Portal 35's partial-trace decoherence operator ($\operatorname{Tr}_H$) are dual faces of the exact same linear-algebraic boundary map: silently dropping an entangled ancilla leaks state into the container environment $H$, reducing $\operatorname{Tr}(\rho_O^2)$ strictly below `1`.

---

## Pillar 4 — Exact Landauer Erasure vs. Reversibility & Nested-Simulation Complexity Gap

1. **Pure-$\mathbb{Z}/\mathbb{Q}$ Landauer Erasure Accounting (Landauer 1961 `N0`):** For any Boolean map $f: \{0,1\}^{n_{\text{in}}} \to \{0,1\}^{n_{\text{out}}}$ on uniform inputs ($N = 2^{n_{\text{in}}}$), exact conditional preimage entropy satisfies $2^{N H(X \mid Y)} = \prod_y |f^{-1}(y)|^{|f^{-1}(y)|} \in \mathbb{Z}_{>0}$:
   - **Irreversible Classical `AND` ($2 \to 1$):** Exact output fibers `{0: 3, 1: 1}` (`is_bijection = false`), $2^{4 H(X \mid Y)} = 3^3 = \mathbf{27} > 1$, so $H(X \mid Y) = \frac{3}{4}\log_2(3)$ bits. Pure-$\mathbb{Z}$ power inequalities $2^{19} = 524{,}288 < 27^4 = 531{,}441$ and $27^5 = 14{,}348{,}907 < 2^{24} = 16{,}777{,}216$ certify the exact rational Landauer erasure bracket **`19/16 < H(X|Y) < 6/5`** bits (`1.1875 < 1.18872 < 1.2000`, zero floats).
   - **Irreversible 1-Bit Reset `ERASE` ($1 \to 1$):** Fibers `{0: 2}`, $2^{2 H(X \mid Y)} = 4 \implies H(X \mid Y) = 1$ exact bit ($\Delta Q_{\min} = k_B T \ln 2$).
   - **Reversible Toffoli `CCX` ($3 \to 3$):** Exact bijection over all 8 states (all fibers size `1`), exact involution `CCX(CCX(x)) = x` for all `8/8` states, $2^{8 H(X \mid Y)} = \mathbf{1} \implies H(X \mid Y) = \mathbf{0}$ (zero logical erasure).
2. **Level-0 / Level-1 / Level-2 Nested-Simulation Separation (`n = 1 .. 20`):** Across the canonical generator set (`H`, `T`, `CNOT`, `CCX`), Level-0 continuum unitary evolution and Level-2 Silq `mfree` `Clifford+T` dynamics satisfy the identical shared unitary law $U^\dagger U = I$ (recorded in the certificate key `algebraic_group_isomorphic_l0_l2 = true`, certifying this shared generator-set unitary law rather than claiming an abstract full-group isomorphism), while simulating an $n$-qubit Level-2 state inside a Level-1 deterministic `!T` host requires exact classical state-vector dimension $2^n$ (`4 * 2^n` rational components in $\mathbb{D}[i, \sqrt{2}]$, $4^n$ density-matrix entries), with strictly increasing overhead $2^n / n$ for $n \ge 2$:

| $n$ Qubits | Hilbert Dim $2^n$ | Exact $\mathbb{Q}$ Components $4 \cdot 2^n$ | Density Matrix $4^n$ | Exact Ratio $2^n / n$ | Truncated Decimal |
| --- | --- | --- | --- | --- | --- |
| `1` | `2` | `8` | `4` | `2` | `2.00` |
| `2` | `4` | `16` | `16` | `2` | `2.00` |
| `4` | `16` | `64` | `256` | `4` | `4.00` |
| `8` | `256` | `1,024` | `65,536` | `32` | `32.00` |
| `10` | `1,024` | `4,096` | `1,048,576` | `512/5` | `102.40` |
| `16` | `65,536` | `262,144` | `4,294,967,296` | `4096` | `4096.00` |
| `20` | `1,048,576` | `4,194,304` | `1,099,511,627,776` | `262144/5` | `52428.80` |

---

## Pillar 5 — Zone-B Architecture, Honest Threat Scope & Verification Summary

- **Auditor Architecture & Honest Scope (`silq_boundary_calculus_audit.py`):** `silq_boundary_calculus_audit.py` shares exact parsers and deterministic certificate replay (`build_standalone_certificate`, `validate_certificate_payload`) with `silq_boundary_calculus_oracle.py`; accordingly, `--check` performs **full pure-$\mathbb{Q}$ deterministic replay complemented by `secondary_audit_payload`** (not independent zero-shared-code recomputation). Under both `full_replay=True` and `full_replay=False`, `validate_certificate_payload` enforces `_validate_payload_structure` (exact top-level and per-pillar key-sets, metadata, and bijective bool-vs-int enforcement rejecting both `BOOL_IN_NON_BOOL_FIELD` and `NON_BOOL_IN_BOOL_FIELD`). `secondary_audit_payload` enforces strict nested key-sets across all 4 pillars and every nested sub-object (gates, Born witnesses, valid/must-fail programs, P3 witnesses, P4 `AND`/`ERASE`/`CCX`/simulation rows), exact `literature_anchors_n0` and `ring_representation`, exact 14-key Clifford+T relations, exact power-of-2 dyadic Born denominators (`AUDIT_P1_NON_DYADIC`) + non-negativity + all 4 exact Born vectors (`bell_pair`, `magic_HTH_ket0`, `ghz_3q`, `toffoli_superposed`), exact P2 valid/must-fail tuples (`name`, `annotation`, `return_types`, `synthesized_uncomputations`, `expected_error_code`, `type_error_code`, `type_error_detail`), P3 Hermiticity/trace/interference flags, and P4 metadata (`n_in_bits`, `n_out_bits`, `input_state_count`, `distinct_output_count`, `max_fiber_size`, `AND`/`ERASE`/`CCX`/table checks). Integer parsing enforces `MAX_INT_BITS = 2048` as the exact binding cap (with `MAX_INT_DIGITS = 617`, `parse_bounded_int` character cap `MAX_INT_DIGITS + 1 = 618`, and `MAX_RATIONAL_CHARS = 2 * MAX_INT_DIGITS + 2 = 1236` so `±((1<<2048)-1)` and full 2048-bit reduced rationals parse cleanly by default, while `617`-digit integers exceeding `2^2048 - 1` such as `10^617 - 1` fail closed with `INT_TOO_LARGE`/`RATIONAL_TOO_LARGE`), and `parse_strict_json_text` enforces UTF-8 byte caps.
- **POSIX File I/O Hardening & Honest Same-UID Boundary:** All path traversal uses atomic per-component `dir_fd` (`openat` with `O_RDONLY | O_DIRECTORY | O_NOFOLLOW` + `lstat` symlink classification on `ELOOP`/`ENOTDIR`) and `dir_fd` `PWD` checking; reads use `read_regular_bytes_capped` (`max_bytes <= 64 MiB`, `65536`-byte streaming chunks); writes enforce `type(payload) is bytes` before path traversal, reject target hardlinks (`st_nlink > 1`, safely handling transient `st_nlink <= 1`), create `0o600` temp files under `threading.Lock()` + monotonic counter + `secrets.token_hex(8)` + bounded 32-attempt `EEXIST` retry (`TEMP_RETRY_EXHAUSTED`), call real `os.fsync(tmp_fd)`, verify `os.fstat(tmp_fd).st_nlink == 1` immediately before `os.replace(..., src_dir_fd=dfd, dst_dir_fd=dfd)`, and call `os.fsync(dfd)`. *Honest POSIX threat boundary:* within a single UID without kernel MAC confinement, a hostile co-privileged process can always alter user files or attach via `ptrace`; these atomic `dir_fd`/`0o600`/`O_EXCL`/`fstat`/`fsync` invariants specifically defend against accidental concurrent-writer collisions, symlink/hardlink clobbers, partial writes, and directory-swap TOCTOU races.
- **Verification Gates Passed (Post-Final-Edit, Strictly Sequential):**
  - **R4 Isolated 3-Mode Parity (`python3 -I -B`, `python3 -I -O -B`, `python3 -I -B -W error`, plus `PYTHONHASHSEED=42` non-isolated check):** Bit-identical `4d924ecbad830f49298488c46f792d828101e1c66d4cab27e0cb6b09b2cc9a21`, `--check` `valid=true` & `secondary_audit_passed=true`, `test_silq_boundary_calculus_r5.py` `13/13 OK`.
  - **Live `aletheia v2.0.0 mutate --max-mutants 0`:** `70/70` (`100.0%`, `survived=0`) on `silq_boundary_calculus_audit.py` + `111/111` (`100.0%`, `survived=0`) on `silq_boundary_calculus_oracle.py` = **`181/181` (`100.0%`)**.
  - **Exhaustive `SWAP + SUBCOND_DEL` AST `BoolOp` Sweep (`timeout=45`):** `21/21` (`100.0%`) on `silq_boundary_calculus_audit.py` + `110/110` (`100.0%`) on `silq_boundary_calculus_oracle.py` = **`131/131` (`100.0%`)**.
  - **Live Zone-B Adversarial Fuzzer:** `23/23` CLI + `18/18` in-memory (`full_replay=True`) + `18/18` in-memory (`full_replay=False`) + `18/18` combined (`full_replay=False` + `secondary_audit_payload`) = **`77/77` (`100.0%`, `0` bypasses, `0` crashes)**.
  - **Live Concurrency & Kernel Races:** `16T` distinct-target (`640` writes, `0o600`) + `16T` same-target (`640` writes) + `80T` barrier burst (`80` writes) + `>= 500` `renameat2(RENAME_EXCHANGE)` swaps (`550` R/W cycles) + `>= 420` `os.link`/`os.unlink` hardlink race cycles (`0` errors, `0` clobbers, `0` leftover temp files).
  - **Aletheia Static & Safety Gate:** `aletheia v2.0.0 audit-check . --strict-ancestors --safety-scan --scripts silq_boundary_calculus_audit.py test_silq_boundary_calculus_r5.py` -> `PASS` (`5` files, `2/2` R4, `0` findings, `0` `__pycache__`).
