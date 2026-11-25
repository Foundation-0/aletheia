# Track S104 — Kronecker Product-Code Factored Embeddings, Rank-1 Obstruction, `EXP-Δ` Preregistration Audit, Composed Triple Gate & `RAM == WIRE == HASH`

**Scope:** CPU-only, `0` GPU touch, `0` dataset/weight copies, `PYTHONDONTWRITEBYTECODE=1`. External numeric anchors are SHA-256-pinned in `s104_kronecker_triple_gate_oracle.py` (`UPSTREAM_PINS`).

**Novelty (Law 4):** **`N0`**, `n2_claims = 0`. Kronecker/tensor-product embedding compression is prior art
(word2ket / word2ketXS, Panahi–Saeedi–Arodz, ICLR 2020; TT-embeddings, Hrinchuk et al., Findings of EMNLP 2020); the
Schur-complement-of-Kronecker identity and the Van Loan–Pitsianis rearrangement are textbook. This track's contribution is an
**audit**: exact steelman, exact falsification of four over-claims, exact repairs, and a corrected preregistration. Oracle class:
`exact` (pure `int`/`Fraction`) plus `anchor` (external numbers quoted from pinned peer-web excavations, not re-measured here).

---

## 1. Verdict on the Mistral Large 4 claims (13 findings, all in the certificate's `audit_findings`)

| ID | Sev | Verdict | Claim → exact result | Repair |
|---|---|---|---|---|
| `S104-KRON-01` | MED | **FALSE** | "Root sharing is a positive inner product independent of pattern." In rank-1 `A_r ⊗ B_p`, `⟨E(r,p),E(r,p′)⟩ = ‖A_r‖²·⟨B_p,B_p′⟩`; orthogonal patterns give **exactly `0`** (Lean Thm 8). With the natural calibrated pattern table (Hadamard `H_4` rows, all `‖B_p‖² = 4`, mutually orthogonal) every shared-root cross-pattern similarity is `0`. | Hybrid code `[A_r ⊗ B_p ; A_r ; B_p]`: Gram `⟨a,a′⟩⟨b,b′⟩ + ⟨a,a′⟩ + ⟨b,b′⟩` (Thm 14), shared-root similarity `= ‖A_r‖² = 9` even for orthogonal patterns (Thm 15), still equal row norms (Thm 16). |
| `S104-KRON-02` | MED | PARTIAL | "~7,900× `token_embd` collapse." Exact ratio `R·P·d1·d2 / (R·d1 + P·d2) = 2147483648/270336 = 262144/33 = 7943.758×` — but against a **hypothetical 2,097,152-row** `R×P` table (`16384/1187 = 13.8×` larger than the pinned Qwen2.5 padded vocab `151,936`, S100 cert). Against the real vocab at `d = 1024`: `155582464/270336 = 18992/33 = 575.515×`. | Report both ratios; a factored code must also cover the existing vocabulary, which rank-1 cannot express in general (Pillar 2). |
| `S104-KRON-03` | MED | PARTIAL | "S31 DPI concentration identically 1 for free." TRUE at table level: `C_row(E) = 1` exactly (12/12 rows `‖·‖² = 36`; appended root inherits calibration). But S31 DPI is a **patch** metric (`C_row = n·max‖ΔW_i‖²/Σ‖ΔW_i‖²`): a norm-preserving misfold of root 0 (`A_0 → (0,2,1,−2)`, same `‖·‖² = 9`) leaves `C_row(E) = 1` (**table-level DPI is blind**), while the patch has `C_row(ΔE) = R_0 = 4`; at ML4 scale a root patch has `C_row = R = 4096`, a pattern patch `P = 512`, a flat single-row patch `R·P = 2,097,152`. | Keep per-row SHA-256 locks; apply `C_row` to factor deltas, not to the calibrated table. |
| `S104-KRON-04` | LOW | TRUE | "Exact Schur quotient conductance preserved." Verified exactly on seeded rational factors (`4×5`, `3×4`): `144/144` pair identities, `12/12` norm identities, `G_E = G_A ⊗ G_B`, and `(G_A⊗G_B)/(G_A[S,S]⊗G_B) = (G_A/G_A[S,S]) ⊗ G_B` for `S = {roots 0,1}`. VLP rank: Kronecker Gram `1`, flat seeded table `9` (fracture). | Scope: a Gram-matrix statement; transfer to the S92 Laplacian Schur conductance needs an explicit Gram→Laplacian map (not provided by ML4). |
| `S104-EXPD-01` | **HIGH** | **FALSE** | `EXP-Δ` KILL thresholds have **no false-positive control**: an all-positive scorer reaches `r_hidden = 664`, `r_hidden_cross = 85` and "kills" the claim trivially. | Matched-FPR recall: `fp_hidden ≤ fp_budget` (surface stem-match FP count) else `ABSTAIN_FPR_UNMATCHED`. |
| `S104-EXPD-02` | MED | FALSE | "Cross-node determinism `|r(1.5B) − r(7B)| ≤ 2/664`" compares two different models (model agreement, not determinism). | Same Qwen2.5-1.5B arm on RTX 3080 and M1 Max for agreement; 7B is a separate replication arm. |
| `S104-EXPD-03` | MED | FALSE | Train on 74 pairs / test on held-out 74 cannot score all `664/85/220` edges (denominator inconsistency). | Edge-disjoint 2-fold cross-fit: every edge scored exactly once by a scorer that never saw its label. |
| `S104-EXPD-04` | LOW | FALSE | "Triangle KILL `44/220` is ≥ 2× surface." Surface independence model `220·(319/664)³ = 1785396745/73188736 = 24.3944`; `44` is `1.8037×`. | KILL at `⌈2·model⌉ = 49/220`. |
| `S104-EXPD-05` | LOW | PARTIAL | "PASS upgrades `r` to an information-theoretic ceiling." `I(edge;h(En)) ≤ I(edge;En)` holds, but a failed linear probe does not show absence. | Scope PASS to the probe class; Lean Thm 25 gives the exact surface-collision ceiling. |
| `S104-TG-01` | MED | **FALSE** (vocabulary) | "`[StaticProof, Holdout] ≠ 0` non-commutativity." Acceptance gates **commute** (Lean Thm 18; exhaustive `585` candidate lists × `6` gate orderings = `3510/3510` equal). | The live phenomenon is **non-implication** (legal ⇏ useful; Thms 19–21) plus **selection-order non-commutativity**: on the witness `c0(s=F,val=10)`, `c1(s=T,h=F,val=5)`, `c2(s=T,h=T,val=3)`: argmax→gate = `[]`, gate→argmax = `[c1]` (fails holdout), static∧holdout→argmax = `[c2]`. |
| `S104-TG-02` | LOW | NOT_SHOWN | T-C5 live NVML triple-pack on RTX 3080. | CPU-only track (GPU held by S95/S97); run under `mlos gpu-lease` later. |
| `S104-WIRE-01` | LOW | FALSE | "`hampack` 30.6 MB LUT is 7.65× the 4 MiB L2." Pinned `hampack` LUT size is `30,615,552 B`: `30615552/4194304 = 14949/2048 = 7.2993×` (7.65× only if 30.6 **MiB**). | Use `7.2993×`. |
| `S104-WIRE-02` | LOW | TRUE | "Lane-local ARX (spliceware v3 class) cannot pass a ≥ 50% avalanche gate." Lean Thm 24 for **any** lane-local map on ≥ 3 lanes; exact model run: all `8/8` single-bit word flips change exactly `8/32` digest bytes, all confined to the flipped word's lane `{4i..4i+3, 16+4i..19+4i}`. | ChaCha20-permutation sponge (`32/32` changed bytes per flip) or SHA-256 (`32/32`) passes. |

## 2. Pillar 1 — Exact Kronecker product-code algebra (`pillar1_kronecker_algebra`)
* **Budget:** `R=4096, P=512, d1=64, d2=16, d=1024`; full `2,147,483,648` vs factored `270,336` params (`540,672` fp16 bytes); exact ratio `262144/33`.
* **Gram/Schur:** see `S104-KRON-04` (seeds `104001..104003`, `det G_B = 70561/2304`, `det G_A[S,S] = 4197/64`).
* **DPI:** see `S104-KRON-03`; seeded flat table `C_row = 55728/30943`.

## 3. Pillar 2 — Law-5 rank-1 expressivity obstruction & rank-χ lift (`pillar2_rank1_obstruction`)
Every rank-1 product kernel `K((r,p),(r′,p′)) = α(r,r′)β(p,p′)` satisfies the 2×2 minor identity (Thm 9). The additive
"share-root-OR-share-pattern" kernel `δ(r,r′)+δ(p,p′)` violates it (`1·1 ≠ 2·0`), so **no rank-1 product kernel represents it**
(Thm 10); its VLP rank is exactly `2`. The rank-2 lift — concatenated one-hot `[e_r ; e_p]` — realizes it exactly (Thm 13; oracle:
Gram equals the additive kernel on the `3×3` grid), and a rank-2 CP concatenation of Kronecker blocks has the summed Gram (Thm 11).

## 4. Pillar 3 — `EXP-Δ` latent-repair preregistration (`pillar3_exp_delta`, `exp_delta_latent_repair_spec.json`)
* Surface facts (S92 cert `294e26e9…`): edges `319/664` retained (loss `345/664`), cross-discipline `7/85` (loss `78/85`), `(7/85)³ = 343/614125`.
* ML4 gate checks: `320 = 319+1` ✓, `8 = 7+1` ✓, `14 = 2·7` ✓, `24 = ⌊24.3944⌋` ✓, triangle KILL `44` ✗ (→ `49`).
* Holm resolution: `B = 250` permutations give minimum attainable `p = 1/251 ≤ α/m = 1/60` ✓.
* **Status `PREREGISTERED_NOT_EXECUTED`.** The spec (canonical JSON, `0o600`, SHA in certificate) pins S92/S100/ML4 SHAs, requires
  `HF_HUB_OFFLINE=1`, weights outside `expedition/`, `mlos gpu-lease --mode train` + `mlos stamp-run --zone B` on the RTX 3080 only
  after S95/S97 release the GPU, and the same 1.5B arm on the M1 Max. `verify_s104_kronecker_triple_gate.py --evaluate-results <json>`
  returns the exact three-valued verdict (`PASS` / `KILL` / `ABSTAIN_*` / `FAIL_CLOSED_RESOURCE`) with all repaired gates; the
  certificate's `evaluator_selftest` runs **synthetic** fixtures only (no measurement is claimed).

## 5. Pillar 4 — Composed triple gate (`pillar4_triple_gate`)
* Anchors (quoted from pinned `peer-web/weft_loom_data_and_mcproof_mining.md` `899e8ca0…` and `spliceware_weft_deep_excavation.md`
  `3e767e7e…`; **not re-measured**): weft#160 `178` Lean-proved edits with held-out regressions `1149→1216`, `884→949`;
  mcproof PR #3 `P2-B` val `2/48` (B0 `4/48`), sealed holdout `0/96`; T-C1 `≥ 1997/2000` CPU alignment → live retention `0`.
* Exact: `(31/32)^96 < 1/20`; one-sided 95% Clopper–Pearson upper limit for `0/96` bracketed in
  `[515457/16777216, 257729/8388608] = [0.030724, 0.030724]` (24-step bisection, independently recomputed in the verifier) `< 1/32`.
* `P2-B` (static ✓, receipt ✓, holdout ✗) is accepted by the static gate and rejected by the composed gate (Thm 21 instance).

## 6. Pillar 5 — `RAM == WIRE == HASH` (`pillar5_wire_hash`)
* **`[Q, S] ≠ 0` exact witness:** `v = 3/20`; its binary64 neighbour is `0x13333333333333 / 2^55 < v` (computed with integers only).
  `round_half_even(10·v) = 2` but after a float wire `round_half_even(10·fl(v)) = 1` → different int8 bytes and SHA-256
  (`dbc1b4c9…` vs `4bf5122f…`). Quantize in exact arithmetic **before** serializing.
* **Endianness:** `<6i` vs `>6i` of the same ints hash differently (`654d6b49…` vs `bfde9b5c…`); int8 LE round-trip `256/256`.
* **Avalanche:** see `S104-WIRE-02` (cell `1088` B, SHA `37775fc3…`). **Cross-device 3/3 GGUF digest: `NOT_SHOWN`** (needs the 3 nodes).

## 7. Pure-`Init` Lean 4.36.0 companion — `KroneckerFactoredEmbeddings.lean`
`0` imports, `0` `sorry`, `0` warnings; `#print axioms ⊆ {propext, Quot.sound}` for all 25 (`2` depend on no axioms). Vectors are
`List Int` and **everything is proved over ℤ** (the oracle replays over ℚ). `dot` truncates to the shorter list; theorems carry
length hypotheses where alignment matters. `11` auxiliary lemmas are not counted. Exactly what is proved:

| # | Theorem | Statement (all universally quantified) | Note |
|---|---|---|---|
| 1 | `dot_append` | `|a1|=|b1| → dot (a1++a2) (b1++b2) = dot a1 b1 + dot a2 b2` | |
| 2 | `dot_scale_scale` | `dot (scale x u) (scale y v) = x*y*dot u v` | |
| 3 | `kron_length` | `|kron a b| = |a|*|b|` | |
| 4 | `kron_dot` | `|b|=|b′| → dot (kron a b) (kron a′ b′) = dot a a′ * dot b b′` | Gram factorization |
| 5 | `kron_sqnorm` | `sqnorm (kron a b) = sqnorm a * sqnorm b` | |
| 6 | `kron_rows_equal_norm` | `(∀r, sqnorm (A r)=MA) → (∀p, sqnorm (B p)=MB) → sqnorm (kron (A r) (B p)) = sqnorm (kron (A r′) (B p′))` | table-level `C_row = 1` only |
| 7 | `shared_root_gram` | `|b|=|b′| → sqnorm a = MA → dot (kron a b) (kron a b′) = MA * dot b b′` | |
| 8 | `shared_root_annihilated_by_orthogonal_patterns` | `|b|=|b′| → dot b b′ = 0 → dot (kron a b) (kron a b′) = 0` | refutes KRON-01 |
| 9 | `rank1_minor_identity` | `(α r r′·β p p)(α r r·β p p′) = (α r r·β p p)(α r r′·β p p′)` | light (commutative-ring identity) |
| 10 | `additive_kernel_not_rank1` | `¬∃ α β : ℕ→ℕ→ℤ, ∀ r r′ p p′, α r r′ * β p p′ = δ r r′ + δ p p′` | Law-5 obstruction |
| 11 | `cp2_gram` | `|a1|=|a1′| → |b1|=|b1′| → |b2|=|b2′| → dot (kron a1 b1 ++ kron a2 b2) (kron a1′ b1′ ++ kron a2′ b2′) = ⟨a1,a1′⟩⟨b1,b1′⟩ + ⟨a2,a2′⟩⟨b2,b2′⟩` | rank-2 CP |
| 12 | `onehot_dot` | `i<n → j<n → dot (onehot n i) (onehot n j) = δ i j` | |
| 13 | `additive_kernel_rank2_realized` | `r,r′<R → p,p′<P → dot (onehot R r ++ onehot P p) (onehot R r′ ++ onehot P p′) = δ r r′ + δ p p′` | rank-2 lift |
| 14 | `hybrid_gram` | `|a|=|a′| → |b|=|b′| → dot (hybrid a b) (hybrid a′ b′) = ⟨a,a′⟩⟨b,b′⟩ + ⟨a,a′⟩ + ⟨b,b′⟩` | |
| 15 | `hybrid_shared_root_survives_orthogonal_patterns` | `|b|=|b′| → dot b b′ = 0 → dot (hybrid a b) (hybrid a b′) = sqnorm a` | repairs Thm 8 |
| 16 | `hybrid_rows_equal_norm` | calibrated factors → equal hybrid row norms | |
| 17 | `factored_params_le_full` | `2≤R → 2≤P → 1≤d1 → 1≤d2 → R*d1 + P*d2 ≤ R*P*(d1*d2)` (ℕ) | weak bound; exact ratio in oracle |
| 18 | `gate_filters_commute` | `(l.filter p).filter q = (l.filter q).filter p` | light; refutes TG-01 vocabulary |
| 19 | `triple_gate_le_static` | `|l.filter (s∧r∧h)| ≤ |l.filter s|` | |
| 20 | `triple_gate_strict_of_witness` | `c∈l → s c → r c → ¬h c → |l.filter (s∧r∧h)| < |l.filter s|` | |
| 21 | `holdout_zero_kills_composed` | `(∀c∈l, h c = false) → l.filter (s∧r∧h) = []` | |
| 22 | `zero_success_bound` | `96 ≤ n → 20 * 31^n < 32^n` (ℕ) | CP reading via the standard formula |
| 23 | `lane_local_nonexpansive` | `hamming (l.map f) (l′.map f) ≤ hamming l l′` | |
| 24 | `lane_local_fails_avalanche` | `3 ≤ |l| → 2 * hamming (l.map f) ((l.set i v).map f) < |l|` | any lane-local map; not the spliceware C source |
| 25 | `latent_repair_collision_ceiling` | `tok x = tok y → lab x ≠ lab y → ¬(g (tok x) = lab x ∧ g (tok y) = lab y)` | collision lemma only |

## 8. Verifier, tests & receipts
* **`verify_s104_kronecker_triple_gate.py`** — fail-closed `SEC` (field-complete: exact keysets, 13 zero-shared-code semantic
  re-derivations with unique codes incl. an independent integer CP bisection, then type-strict deep equality of **every** leaf
  against the oracle rebuild, so `True`↔`1` swaps are caught), enforced on both `FR0` and `FR1`; `FR1` adds live replay of
  toolchain/lakefile/spec bytes and the Lean source SHA. Hardened Zone-B I/O (`O_NOFOLLOW|O_NONBLOCK`, `fstat S_ISREG`, `nlink==1`,
  symlink-component and symlinked-`$PWD` rejection, size + stream caps, atomic `0o600` writes with `fsync`). Strict canonical JSON
  (ASCII, ≤ 80-digit ints, no floats/`NaN`/duplicate keys, rationals capped at 80 digits → no `>4300`-digit `ValueError`).
* **18-rule R11+/R12 static Lean scanner** (comment-stripped): strings/guillemets; `sorry|admit|axiom|sorryAx|mkSorry` (incl.
  `_root_.sorryAx`); `unsafe|partial|opaque|private|protected|noncomputable`; `native_decide|bv_decide|ofReduce*|trustCompiler|panic|panicCore|panicWithPos*|unreachable`;
  `extern|implemented_by|csimp`; `initialize|builtin_initialize`; `@[init]/@[builtin_init]/attribute [init]`; `export`;
  `macro|macro_rules|elab|elab_rules|syntax|declare_syntax_cat|run_cmd|run_elab|run_meta|term_elab|command_elab|builtin_*|@[tactic]`;
  `notation|prefix|infix*|postfix`; `import`; `set_option`; `debug.{skipKernelTC,byAsSorry,proofAsSorry,sorryAsError,terminalTacticsAsSorry}|warn.sorry`;
  `dbg_trace|dbgTrace*|dbgSleep|dbgStackTrace`; `#eval|#reduce|#exit|#check|#synth|#guard|#guard_msgs|#guard_expr`; `+native`
  (`decide +revert +native`); `native :=`/`config :=`/`{ native`/`DecideConfig`; multiline `decide⏎(`/`+`/`{`. Plus exact `#print axioms`
  list (order-pinned) and theorem-presence checks. **55 PoCs hit their rule (18/18 rules covered), 10 clean controls 0 FP.**
* **Live Lean:** `lean --stdin` on bytes read once (zero TOCTOU), `env` scrubbed of `LEAN_PATH`, `LEAN_OPTS`, `LEAN_SRC_PATH`,
  `LEAN_CC`, `LEAN_SYSROOT`, `ELAN_TOOLCHAIN`, `ELAN_HOME`; requires `version 4.36.0,`, `rc=0`, empty stderr, no `warning`,
  exactly the 25 pinned names with axioms ⊆ `{propext, Quot.sound}`.
* **Tests `test_s104_kronecker_triple_gate_r5.py`: `39/39 OK`, `0` skips** — re-signed tamper of **all `396/396` payload leaves**
  rejected on `SEC` and `FR0` (`0` bypasses), `18` targeted semantic forgeries rejected with their exact codes on `SEC`/`FR0`/`FR1`.
* **Parity (`0` skips):** tests `39/39 OK ×6` (3-mode R4 `-I -B`, `-I -O -B`, `-I -B -W error`, plus `PYTHONHASHSEED=42 -B`,
  `env -i PATH=/usr/bin:/bin HOME=/nonexistent ALETHEIA_LEAN_BIN=<4.36.0 toolchain binary>`, and read-only directory copy);
  `--check` OK across all 3 R4 modes, `env -i`, and RO dir (`cert_sha256=1886e37b…`); `--standalone | cmp` **EXACT**;
  `--verify-pins` `8/8` upstream pins (S92/S100/S31 certs, design critiques, peer-web excavations, and `hampack` LUT pin).
* **Zone-B fuzz (direct, 4 surfaces):** aletheia v2.1 fuzzer **`82/82`** (`25` CLI + `19` FR=True + `19` FR=False + `19` SEC,
  `bypasses=0, crashes=0`).
* **Official `aletheia mutate --guards require_ok --workers 2 --timeout 180 --max-mutants 0`:** verifier **`122/122`**,
  oracle **`77/77`** (`100.0%`, `truncated=False`, null-mutant passed).
* **Whole-file AST `BoolOp` operand-drop:** **`16/16`** killed (oracle + verifier).
* **Self-audit `aletheia audit-check . --strict-ancestors --safety-scan --lean-audit`:** **`status=PASS`** (`lean_findings=0`, `safety=0`, `leaks=0`, `ancestor_perm=0`).
* Hygiene: `0` floats, `0` bare `assert`s, `0` RNG modules, `0` forbidden path/mode literals, `0` CR, `0` home-path
  leaks, `PYC/.lake = 0`.

## 9. Manifest
| File | Lines | Bytes | Mode | SHA-256 |
|---|---|---|---|---|
| `KroneckerFactoredEmbeddings.lean` | 497 | 22,558 | `644` | `292b1593d433616b22a309aae12487a11ce1aef3ebc5269f99fc652a5463a740` |
| `lakefile.toml` | 5 | 137 | `644` | `f4fbfda92a6b09c65991d80910bcd3ff4bd5b41ab4581740c9dcc0ff0a30376e` |
| `lean-toolchain` | 1 | 25 | `644` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |
| `s104_kronecker_triple_gate_oracle.py` | 1153 | 52,573 | `644` | `b78d7ee4e0d605d066bed0d7f804266a5fd7236277592cf69ee0be2464b15e6e` |
| `verify_s104_kronecker_triple_gate.py` | 582 | 28,217 | `644` | `b8d475d1ffe978c4a5f8338f3173f1a2ea16c2daeb30e5f3e109ee726ea38c4c` |
| `test_s104_kronecker_triple_gate_r5.py` | 909 | 52,600 | `644` | `2b8110f04dcda27f3627d4042cfdd81fb85c31e0934588314fbb81eba7ccea42` |
| `exp_delta_latent_repair_spec.json` | 1 | 3,272 | `644` | `c65521748d3a44c2b93d9c4a25d80fa6466b346f4ec2e9a193f999b5a2bf35a4` |
| `s104_kronecker_triple_gate_certificate.json` | 1 | 15,204 | `644` | `634e1f54a3077f701928373e5d1839facc13259f1097f60419a318fcefb491fd` |

Certificate: `payload_sha256 = 5b6d7298326aec6aac4065bae69589dd6bdc0f7dd9502c5a448a0a4a9c5b0dc1`, `certificate_sha256 = 1886e37bbf14262b1ae0af878d57512c3e77f4e1fbe840163fe71a6d79ed970d`. `s104_kronecker_triple_gate_audit.py` and `README.md` provide `evidence-tracks` CI discovery and documentation alongside the verified core bundle above.
