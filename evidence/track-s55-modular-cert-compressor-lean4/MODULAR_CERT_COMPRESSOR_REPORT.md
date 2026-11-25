# Modular Pure-Z/Q Algebraic Certificate Compressor & Live Lean 4.36.0 Soundness Gate

## Executive Summary

- **Schema & Track ID:** `aletheia.modular_cert_compressor.certificate.v1` (`TRACK-S55-MODULAR-CERT-COMPRESSOR-LEAN4`)
- **Novelty Classification:** **`N1`** (engineering synthesis combining exact $\mathbb{Z}/\mathbb{Q}/\mathbb{F}_p$ polynomial compression, fraction-free Bareiss rank/minor verification, arbitrary-depth $O(n)$ Lean 4 anti-bypass lexing, and a live-compiled zero-import `Lean 4.36.0` kernel soundness companion; all underlying mathematical theorems and benchmark comparators are explicitly attributed as `N0` prior literature below).
- **Oracle Class:** **`exact`** (`100%` pure Python 3 standard library + pure-`Init` `Lean 4.36.0`; zero IEEE-754 floats on any trust path, zero bare `assert`s, zero `.isdigit()`, zero `os.path.islink`, zero mathematical RNG).
- **Certificate Size & Digests (`modular_cert_compressor_certificate.json`, written `0o600` by `--write`; `0644` in git since git cannot store `0600`):**
  - **On-disk size:** **`3,558` B (`3.47 KiB`, strictly `< 10 KiB`)**
  - **File SHA-256:** `7e87af3d3e40228c6609ccb2e7e7f70573fa5961609e4ef59c3c684661b66d59`
  - **`payload_sha256`:** `433511e86663cb05834368d5c4b08f78f8995d664fba1b7292e03c8af60b8cd1`
  - **`certificate_sha256`:** `68e8e5ee31c1029e94b9d1c33d74265ca0242285e7d07add56fd296f17c56fc1`
- **Live `Lean 4.36.0` Companion (`ModularCertSoundness.lean`):** `10/10` kernel-checked theorems verified with strict `#print axioms` allowlist (`<= {propext, Classical.choice, Quot.sound}`; `4/10` depend on **zero** axioms and `6/10` depend strictly on Lean's standard kernel axioms).

---

## 1. Pillar 1 — Modular Pure-Z/Q Hodge Sextic Compression (`hodge.computer`)

Following the symmetric sextic involution reduction of Diamond and Voisin (`hodge-computer/sextics`, `N0`), we encode the cleared integer sextic `7F` (`cleared_scale = 7`, `q_exponent = 1`, `mod_prime = 5`) as a canonical sparse monomial list `[[e_0, e_1, e_2, e_3, e_4, e_5], c]` and perform **zero-trust algebraic replay** directly from the compressed packet (recomputing every invariant from scratch rather than trusting cached summaries):

| Invariant | Exact Replayed Value | Verification Basis |
| :--- | :--- | :--- |
| Case ID | `symmetric-sextic-residual` | Canonical sparse sextic packet |
| Cleared monomials & sum | `42` monomials, `sum(7F) = 447`, `sum(F) = 447/7` | Exact integer sum + `Fraction(447, 7)` |
| Reflection-basis substitution `(F, A)` | `F`: `46` terms (`0` odd-$s$, `0` odd-$t$); `A`: `4` terms (`0` odd-$s$, `0` odd-$t$) | Exact binomial expansion in `(u, s, w, v, t, z)` |
| Involution determinants | `det(tau_X) = -1`, `det(tau_Y) = -1`, `det(tau_X * tau_Y) = 1` | Exact fraction-free Bareiss elimination |
| Mod-5 Jacobian smoothness | `6` nonzero terms (`2 * sum Z_k^6` over $\mathbb{F}_5$), unique origin critical point `true` | Exhaustive $\mathbb{F}_5$ verification + Lean 4 theorem |
| Compressed packet size & SHA-256 | **`923` B** (`1ffede92228c423d11002be9863e7de1e4578ec10aee072ca2b9dbbf894a694a`) | Canonical ASCII JSON bytes |
| Ratio vs. cited `233 GB` reference envelope (`[230, 233]` GB) | Exact `233000000000/923` (`~252.4M x`, strictly `> 20,000,000 x`) | Cited `N0` literature envelope (`arXiv:2611.09822v3`); **never enumerated or measured here** |

> **Scope Honesty (`measured_live_deepmind_233gb_comparator = false`):** The `[230, 233]` GB figure is cited strictly as a published `N0` literature reference envelope from Shirobokov et al. (`arXiv:2611.09822v3`) and was **not** live-benchmarked on this host.

---

## 2. Pillar 2 — Adversarial Cheat-Blocking & Exact Algebraic Obstructions

The compressor and secondary auditor enforce strict exact-rank, canonical-rational, and non-hollow replay gates targeting four documented verification failure modes:

1. **Praxis Rank-2 SOS Cheat Blocking (`RANK_GAP_VIOLATION`):**
   - For the UNSAT Boolean quadratic system $w_1 w_3 = 1$, $w_2(w_1 + w_3) = 1$ over $\{0, 1\}^3$, exhaustive enumeration confirms `0/8` Boolean witnesses.
   - An honest rank-1 witness $G_1 = u_1 u_1^\top$ (`u_1 = (1, 1, 0, 1)`) has exact Bareiss rank `1` and all `6` $2 \times 2$ principal minors equal to `0`.
   - The adversarial rank-2 Sum-of-Squares (SOS) Gram matrix $G_2 = u_1 u_1^\top + u_2 u_2^\top$ (`u_2 = (1, 1, 1, 1)`) satisfies **every** UNSAT moment equality and has all `15` principal minors non-negative (`size_1 = [2, 2, 1, 2]`, `size_2 = [0, 1, 0, 1, 0, 1]`, `size_3 = [0, 0, 0, 0]`, `size_4 = [0]`), yet fails exact rank-1 verification with witness $2 \times 2$ minor $M_{0,2} = 1$ ($1 \bmod 101 = 1 \neq 0$). `verify_rank1_bqs_gram_witness(G_2)` deterministically rejects $G_2$ with `RANK_GAP_VIOLATION`.
2. **Pólya (1913) $3 \times 3$ Permanent-to-Determinant Sign Obstruction:**
   - Across all `512` sign matrices in $\{\pm 1\}^{3 \times 3}$, `512/512` satisfy the $\mathbb{F}_2$ parity collapse, while **`0/512`** realize $\operatorname{perm}(A) = \det(S \odot A)$ over $\mathbb{Z}$ (maximum `5/6` permutation signs matched), proven both exhaustively and algebraically in Lean 4 (`+1 = -1` product-of-6-diagonals contradiction).
3. **Hollow Packet & Non-Canonical Rational Rejection:**
   - Tampering a single monomial inside the compressed sextic packet is rejected by full replay (`REPLAY_MISMATCH`).
   - Non-canonical unit denominators (`"3/1"`) and zero denominators (`"1/0"`) are rejected fail-closed (`NON_CANONICAL_DEN`), and every leaf in the certificate payload is exhaustively checked under both `full_replay=True` and `full_replay=False` (`0` bypasses, `0` raw exceptions).
4. **$\mathbb{F}_2[x]$ vs. $\mathbb{Z}$ Carry-Propagation Obstruction:**
   - At $(a, b) = (1, 2)$, Freshman's Dream holds modulo $2$ (`(1 + 2)^2 ≡ 1^2 + 2^2 (mod 2)`), whereas over $\mathbb{Z}$ the carry cross-term is strictly nonzero (`(1 + 2)^2 - (1^2 + 2^2) = 4`).

---

## 3. Pillar 3 — Live `Lean 4.36.0` Soundness Companion & Anti-Bypass Gate

### 3.1 Live `Lean 4.36.0` Kernel Verification & `#print axioms` Receipts

`ModularCertSoundness.lean` (`167` lines, `8,043` B, `0` imports, `0` `sorry`, `0` `native_decide`, SHA-256 `b5990eaf048919d3e77c037f3cf68067cbf2fd931c93422692256f6448546148`) was compiled live on **`Lean 4.36.0`** (`x86_64-unknown-linux-gnu, commit 611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9, Release`, `rc=0`, `0` warnings) and audited via `modular_cert_compressor_audit.py --verify-lean ModularCertSoundness.lean --json`:

| # | Kernel-Checked Theorem (`TrackS55.ModularCertSoundness.*`) | Live `#print axioms` Output |
| :-: | :--- | :--- |
| 1 | `hodge_mod5_fermat_coeff_collapse` | `[propext, Quot.sound]` |
| 2 | `hodge_mod5_partial_zero_iff` | *does not depend on any axioms* |
| 3 | `hodge_mod5_unique_origin_smooth` | *does not depend on any axioms* |
| 4 | `hodge_sextic_coeff_sum_and_sign_char` | *does not depend on any axioms* |
| 5 | `praxis_unsat_bqs_zero_boolean_witnesses` | *does not depend on any axioms* |
| 6 | `rank1_gram_2x2_minor_zero` | `[propext, Quot.sound]` |
| 7 | `praxis_rank2_gram_passes_sos_yet_fails_rank1` | `[propext, Quot.sound]` |
| 8 | `polya_1913_zero_of_512_sign_patterns` | `[propext, Classical.choice, Quot.sound]` |
| 9 | `polya_1913_algebraic_parity_obstruction` | `[propext, Quot.sound]` |
| 10 | `f2_frobenius_vs_z_carry_obstruction` | `[propext, Quot.sound]` |

> **Finite-check labeling:** `5` of the `10` theorems (e.g. #8 `polya_1913_zero_of_512_sign_patterns`, which enumerates all `512` sign patterns) are kernel `decide` over finite domains, i.e. finite exhaustive checks, not symbolic proofs. Theorem #9 (`polya_1913_algebraic_parity_obstruction`) is the non-enumerative algebraic proof.

### 3.2 Hardened Static Lean 4 Anti-Bypass Pre-Filter & Strict Axiom Allowlist

Before invoking the live `lean` kernel, `scan_lean4_anti_bypass` strips nested block comments, line comments, plain strings, `Char` literals (guarded against identifier primes), zero- and multi-hash raw strings (`r"..."`, `r#"..."#` with full Lean identifier boundary checking `_.'!?`), and interpolated strings (`s!"..."`, `m!"..."`, `f!"..."` with brace-depth tracking), normalizes ASCII French-guillemet identifiers (`«...»`), and scans for `15` forbidden trust-escape tokens plus a **single-pass $O(n)$ arbitrary-depth balanced-parenthesis `decide` scanner** (`_scan_lean4_decide_native`) with fail-closed plain-record-literal allowlisting and bound `DecideConfig` detection. After compilation, `verify_lean_companion_file` parses every `#print axioms` line and enforces the strict allowlist `<= {propext, Classical.choice, Quot.sound}`:

- **Positive controls:** **`7/7` passed** (including `decide`, `decide +kernel`, `decide (native := false)`, `decide (native := ((Bool.false)))`, `panic!"bad {sorry} state"`, nested comments/raw strings, and `def f (decide : Nat) : Nat := decide+1`).
- **Adversarial trust-escape fixtures:** **`21/21` rejected** (cert-pinned `adversarial_fixtures_total: 21`, `adversarial_fixtures_rejected: 21`; this is the shipped fixture set counted by `modular_cert_compressor_oracle.py`). The larger `40+` probe count quoted in some external receipts is an external one-off run over extra probe variants; that script is not shipped in this track. Coverage of the shipped `21`: `sorry`, `native_decide`, `Char`/raw-string/interpolated-string escape probes, guillemet `+«native»` / `(«native» := true)` / `(«config» := ...)`, anonymous constructor `⟨...⟩`, `.mk` / `DecideConfig.mk`, indirect variable and `{ c0 with ... }` record updates, `{ native }` punning, `:+` / `,+` custom infix operators, unbalanced braces, nested-paren `decide` forms, and non-standard `#print axioms` outputs).

---

## 4. Pillar 4 — Honest Scope & Prior Literature Attribution (`N0`)

- **Integer, JSON & Filesystem Bounds:** Exact integer cap `MAX_INT_BITS = 3321` (pre-parse ASCII ceiling `MAX_INT_DIGITS = 1000`), `MAX_JSON_DEPTH = 32`, `MAX_JSON_BYTES = 1,048,576`, strict canonical JSON byte checking, constant-time `hmac.compare_digest` verification, strict `exact-bool` `full_replay` validation, atomic `dir_fd` (`O_DIRECTORY | O_NOFOLLOW`) traversal, `(st_dev, st_ino)` logical `$PWD` parity, verified root-owned macOS system-root prefix normalization, streaming `65,536`-B capped regular-file reads enforcing `st_nlink <= 1`, durable `0o600` atomic writes enforcing `st_nlink <= 1` and pre-replace re-verification, and fail-closed `ModularCertError` wrapping for all CLI argument, I/O, and subprocess errors.
- **Non-Claims:** `measured_live_pequalnp_desk_submission = false` and `measured_live_deepmind_233gb_comparator = false`. This artifact does **not** prove or disprove the Hodge Conjecture or $\mathrm{P} \neq \mathrm{NP}$; it certifies a self-contained, auditable certificate compression and kernel-checked soundness pipeline.
- **Prior Literature Attributed (`N0`):**
  1. Diamond, Voisin: `hodge-computer/sextics` symmetric sextic involution reduction.
  2. `brilliant-hq/pequalnp-proofs`: `pequalnp.com` Lean 4 lemma-leasing architecture.
  3. Shirobokov et al. (`arXiv:2611.09822v3`): `formal-quantum-computation` 230–233 GB comparator envelope.
  4. Tse, Vanjani, Vesely (Nov 2026): Praxis witness encryption rank-gap model.
  5. Lasserre (2001) / Schoenebeck (2008): Sum-of-Squares semidefinite hierarchy.
  6. Pólya (1913): *Aufgabe 424* $3 \times 3$ permanent-to-determinant sign obstruction.
  7. Bareiss (1968): Sylvester's identity and fraction-free integer determinant elimination.

---

## 5. Verification Summary & Frozen File Manifest

All checks below ran after the final edit with `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1`:

- **R4 3-Mode Isolated Parity (`-I -B`, `-I -O -B`, `-I -B -W error`) + `PYTHONHASHSEED=42 -B` + `umask 077`:**
  - `--standalone --json` matches on-disk `modular_cert_compressor_certificate.json` (`7e87af3d...`) across all modes.
  - Zero-arg self-check (`7febd825...`), `--check --json` (`4c04c6f1...`, `valid=true`), and `test_modular_cert_compressor_r5.py` (`7/7 OK`, including live `Lean 4.36.0`, exhaustive leaf zero-denominator sweep, `16T`/`80T` `0o600` concurrency burst, `>= 500` hardlink flips, `>= 550` `renameat2(RENAME_EXCHANGE)` swaps, and scratch `os.mkfifo` non-regular refusal with zero null-device writes) pass across every mode.
- **5-Surface Adversarial Certificate Fuzzer (`CLI`, `FR1`, `FR0`, `RT_FR0`, `SEC_DIRECT`):** `101/101` (`25/25` CLI + `19/19` `FR1` + `19/19` `FR0` + `19/19` `RT_FR0` + `19/19` `SEC_DIRECT`; `100.0%`, `bypasses=0`, `crashes=0`) is an **external one-off receipt - the fuzzer script is not shipped**; the shipped tamper coverage is the targeted re-signed tamper list in `test_05`/`test_06` of `test_modular_cert_compressor_r5.py` plus the cert-pinned full-replay gates.
- **Exhaustive Mutation Testing (`--max-mutants 0`; the `--workers 4` flag quoted in earlier receipts does not exist in this CLI):**
  - `modular_cert_compressor_oracle.py`: **`81/81` (`100.0%`, `survived=0`, `truncated=False`, `PASS`)**.
  - `modular_cert_compressor_audit.py`: **`118/118` (`100.0%`, `survived=0`, `truncated=False`, `PASS`)**.
  - **Combined:** **`199/199` (`100.0%`, `0` survivors)**.
- **Exhaustive Whole-File DFS AST `BoolOp` Sweep (`OP_SWAP` + `SUBCOND_DEL`):**
  - `modular_cert_compressor_oracle.py`: **`45/45` `OP_SWAP` + `99/99` `SUBCOND_DEL` = `144/144` (`100.0%`, `survived=0`)**.
  - `modular_cert_compressor_audit.py`: **`20/20` `OP_SWAP` + `73/73` `SUBCOND_DEL` = `93/93` (`100.0%`, `survived=0`)**.
  - **Combined:** **`237/237` (`100.0%`, `0` survivors)**.
- **Static Hygiene & Lean Audit (track-scoped):** `audit-check evidence/track-s55-modular-cert-compressor-lean4 --lean-audit --strict-ancestors --safety-scan` **`PASS`** (`0` findings, `0` bare `assert`s, `0` AST floats, `0` `.isdigit()`, `0` CRLF, `0` host-path leaks, `PYC=0`). Repo-wide `--safety-scan` fails on `48` pre-existing base findings outside this track (CI's `audit-check` does not pass `--safety-scan`).

### Frozen 5-File Artifact Manifest (Sibling to This Report)

| File | Lines | Bytes | Mode | SHA-256 |
| :--- | ---: | ---: | :---: | :--- |
| `ModularCertSoundness.lean` | `167` | `8,043` | `0o644` | `b5990eaf048919d3e77c037f3cf68067cbf2fd931c93422692256f6448546148` |
| `modular_cert_compressor_oracle.py` | `1,149` | `46,022` | `0o644` | `d619f7f7002f0049ed1bd2a8d25551f83bfb4fd3a43966a153369af7fa32489b` |
| `modular_cert_compressor_audit.py` | `768` | `36,930` | `0o644` | `197e4033855f07034e3ef087d9fcee714b45a5813bf20652dbbc7c0e7728b30e` |
| `test_modular_cert_compressor_r5.py` | `1,289` | `72,810` | `0o644` | `1a4ceb5236769527ee98aeb5dbf5e2f58f3369f3d55bb98da66ce928979b60e2` |
| `modular_cert_compressor_certificate.json` | `1` | `3,558` | `0o600` on `--write`; `0644` in git | `7e87af3d3e40228c6609ccb2e7e7f70573fa5961609e4ef59c3c684661b66d59` |
