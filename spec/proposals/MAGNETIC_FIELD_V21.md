# Proposal (`v2.1`): Zone-B Adversarial Fuzzer, Claim-to-Witness Binding, & Magnetic-Field Operational Gates

**Status:** **Executable `v2.1` Additive Modules Ready for Review** (pure Python 3 standard library, exact $\mathbb{Z}/\mathbb{Q}$ arithmetic, zero floats in production AST, zero bare `assert`s, zero external dependencies, strictly additive over `v2.0.0`).

---

## 1. Motivation: Three Orthogonal Gaps Observed Beyond `v2.0.0`

Aletheia `v2.0.0` established isolated `-I`/`-O`/`-W error` parity (R4), AST refusal-site mutation testing (R5), owner-pinned byte verification (R6/R7), Gate-8 subspace latching, Law 2b Transformational Steelman, and Own-Terms-First gates (`aletheia/gates_v2.py`). Multi-domain clean-room audits since `v2.0.0` surfaced three recurring orthogonal failure surfaces that benefit from reusable executable primitives:

1. **Zone-B Hostile Input & Parser/Container Surface (`aletheia.zone_b_fuzzer`):** Independent validators repeatedly broke on the same 16 boundary classes — non-ASCII digests crashing `hmac.compare_digest`, unpaired UTF-16 surrogates in values or dictionary keys, `5,000`-digit integers hitting Python's `4,300`-digit `ValueError` (including during f-string error formatting), `1,500`-deep lists triggering `RecursionError`, `1 == True` re-signed SHA forgeries, lying `Sequence`/`Mapping` containers and builtin subclasses, CRLF/non-canonical bytes, symlink targets/ancestors, signal terminations (`proc.returncode < 0`), and hollow re-signed self-consistent payloads.
2. **Claim-to-Witness Semantic Boundary (`aletheia.claim_witness`):** Even when internal algebraic checks, isolated parity, and Zone-B fuzzing all pass, prose claims can still drift from their underlying artifacts: prorated vs. whole-slot bitrate formulas, stale summary ranges, omitted hot C working-set tables flipping cache-fit claims, surrogate operators or cross-experiment metrics overclaimed as direct measurements, incomplete upstream specification coverage, and hollow witness checkers that verify self-hash consistency without semantic payload binding.
3. **Operational Field-Coupling, Gate-8 Pre-Registration Ordering, & Pre-Push Hygiene (`aletheia.magnetic_field_v21`):** Closing a defect in one repository leaves parallel workstreams exposed unless the fix propagates uniformly across all unhardened active workstreams (Law 1b omni-vein dispatch, maintaining the finite-set partition conservation accounting invariant `|already_hardened| + |dispatch_targets| == |active_veins|`). Separately, verifier queues starve under static role pinning without exact-$\mathbb{Q}$ load balancing and starvation caps, pre-registered predictions require strict timestamp-order verification (`observation_epoch_s > prereg_epoch_s`, Gate 8), and public PR hygiene requires linear-time deterministic pre-push checks ($O(n)$ DCO sign-off parsing, repo visibility, GraphQL 100-file truncation, `OPENBLAS_NUM_THREADS=1`, self-authored review `HTTP 422` guard, `.gitignore`-dropped manifest detection, and programmatic leak scanning).

---

## 2. Additive Executable Modules

All three modules live directly inside `aletheia/` with zero edits to existing `v2.0.0` core modules (`cli.py`, `strict_io.py`, `audit_check.py`, `scaffold.py`, `installer.py`, `ratchet.py`, `gates_v2.py`) so this proposal composes conflict-free with concurrent `v2.0.x` bugfix PRs. Each module exposes both a typed Python API and a standalone `-I`-safe CLI script (`python3 -I -B aletheia/<module>.py`).

### 2.1 `aletheia.zone_b_fuzzer` — 16-Vector Zone-B Adversarial Fuzzer

- **Canonical 16-Vector Corpus (`ZB01`..`ZB16`):** Covers non-ASCII digests (`ZB01`), lone UTF-16 surrogates in digests and keys (`ZB02`), `5,000`-digit integers (`ZB03`), `100`- and `1,500`-deep nesting (`ZB04`), `1 == True` re-signed SHA forgeries (`ZB05`), raw bool-as-int injection (`ZB06`), Unicode-escaped duplicate keys (`ZB07`), floats/`NaN`/`±Infinity` (`ZB08`), non-dict roots (`ZB09`), CR/CRLF & non-canonical formatting (`ZB10`), lying `Sequence` containers (`ZB11`), hostile `Mapping`/subclasses/non-`str` keys (`ZB12`), hollow re-signed payloads (`ZB13`), symlink targets & ancestors (`ZB14`), missing & directory paths (`ZB15`), and invalid UTF-8 / truncated JSON (`ZB16`).
- **Dual Execution Surfaces & Hardened Primitives:**
  - `fuzz_cli_checker(script_path, cert_path, *, check_flag="--check", timeout_sec=30)` runs the target script under forced `python3 -I -O -B -W error` (targets must be standalone or add their own root path under `-I`), materializes `25` hostile CLI probes (including re-signed `ZB07`/`ZB08` valid-cert variants and baseline-distinct `ZB10` CRLF/non-canonical probes) inside an ephemeral temporary directory resolved via `os.path.realpath(tempfile.gettempdir())`, classifies baseline tracebacks as `NOISY_BASELINE`, classifies `TimeoutExpired`, Python tracebacks, AND negative signal return codes (`proc.returncode < 0`, e.g. `SIGSEGV`/`SIGABRT`/`SIGKILL`) as `CRASH`, and decodes subprocess output with `errors="replace"`.
  - `fuzz_python_validator(validator_fn, valid_cert, *, expected_exc_types=(ValueError,))` executes `19` hostile in-memory probes (including re-signed `ZB08` float-forgery probes), re-raises `KeyboardInterrupt`/`SystemExit`, and flags masked `ValueError` crash subclasses (`UnicodeError`, `json.JSONDecodeError`, and raw `Exceeds the limit` 4,300-digit `ValueError`) as `CRASH` rather than clean rejections.
  - `validate_json_tree_iterative` enforces `MAX_INT_BITS = 2048` on every integer leaf, `parse_strict_json` enforces `MAX_JSON_BYTES` UTF-8 byte caps and `MAX_INT_DIGITS = 620`, all file readers use atomic `dir_fd` step-down (`O_RDONLY | O_DIRECTORY | O_NOFOLLOW`) + `$PWD` symlink ancestor verification + leaf `O_RDONLY | O_NOFOLLOW | O_NONBLOCK` + `os.fstat(fd)` `S_ISREG` + `65,536`-byte streaming `os.read` capped at `MAX_JSON_BYTES`, `require_no_symlink_path` enforces concrete `Path` (`type(path) in (Path, type(Path()))`), and `write_certificate_file` uses atomic `0o600` `dir_fd` temp files (`threading.Lock` + `secrets.token_hex(8)`, `O_CREAT | O_EXCL | O_NOFOLLOW | O_NONBLOCK`, `os.fsync`, pre-replace `os.fstat(fd).st_nlink == 1`, target `st_nlink <= 1`, `os.replace(..., dir_fd)`, and directory `os.fsync` under the standard POSIX same-UID directory-write boundary).
- **Five-Way Verdict Taxonomy:** Strictly separates `BASELINE_FAILED`, `NOISY_BASELINE`, `REJECTED_CLEAN`, `BYPASS`, and `CRASH`.
- **Self-Certification (`build_certificate`, `check_certificate_file`):** Verifies a built-in hardened reference checker (`25/25` CLI + `19/19` memory `REJECTED_CLEAN`) alongside `8` deliberately vulnerable foils (including a bool-safe, SHA-verifying float-tolerant foil catching `ZB08` `BYPASS`, and an iterative `str()` int-digit foil independent of Python 3.11–3.14 recursion depth) proving each failure class (`CRASH`, `BYPASS`, `BASELINE_FAILED`) is actively caught.

### 2.2 `aletheia.claim_witness` — 3-Pillar Claim-to-Witness Binding Operator (`P_CTW`)

Implements three orthogonal, exact-$\mathbb{Z}/\mathbb{Q}$ executable gates with concrete `Path` checks, ASCII-only digit parsing (zero `.isdigit()`), and `OSError`-safe CLI error handling:

1. **Pillar 1 — Quantitative Prose-to-Artifact Binding (`verify_prose_artifact_bindings`):**
   - `slot_packing_bpw`: computes exact integer-ceiling scale slots `(n_values + scale_group_size - 1) // scale_group_size` and exact rational bitrate `actual_bpw`, reporting exact `delta_bpw` on mismatch (`PROSE_BPW_ARITHMETIC_MISMATCH`).
   - `integer_range_binding`: enforces exact `(count, min, max)` identity between prose summaries and pinned artifact statistics (`PROSE_COUNT_MISMATCH`, `PROSE_RANGE_MISMATCH`).
   - `c_allocation_table`: sums every `hot_read=True` allocation against claimed hot working-set bytes (`C_HOT_FOOTPRINT_MISMATCH`) and checks qualitative cache-budget claims `actual_hot_bytes <= claimed_cache_limit_bytes` (`CACHE_FIT_CLAIM_MISMATCH`).
   - `prose_invariant_binding`: checks concrete boundary inputs against stated prose invariants such as `min_non_whitespace_chars` (`PROSE_INVARIANT_MISMATCH`).
2. **Pillar 2 — Operator, Spec & Attribution Provenance Typing (`verify_provenance_claims`):**
   - `operator_equivalence`: separates `exact_operator` from `surrogate_operator`, enforces operator identity, gradient coverage, and distributional-vs-causal separation.
   - `metric_attribution`: separates `same_experiment_measurement`, `cross_experiment_anchor`, and `unmeasured_hypothesis`, blocking cross-experiment metric smuggling when `measured_subject != claimed_subject` or the claimed subject was not executed.
   - `spec_completeness`: rejects `claimed_exact_spec_equivalence=True` whenever any declared upstream specification or statistical-assumption clause is unimplemented.
   - `delivery_scope`: enforces monotonic scope tiers (`research_prototype < ctypes_benchmark_harness < packed_file_integration < production_deployment`).
3. **Pillar 3 — Law 2b Semantic Destruction Sensitivity Gate (`run_semantic_destruction_gate`):**
   - Confirms `verifier_fn` accepts an unmodified deep copy of `valid_witness` (returning exact `bool` `True`), then applies deterministic semantic destructions (`empty_mapping_field`, `replace_list_with_arbitrary_dict`, `drop_required_field`, `corrupt_pinned_hash`, `invert_numeric_claim`, with optional `resign_hash_field`), rejecting hollow verifiers with `HOLLOW_WITNESS_VERIFIER` if any destroyed witness survives.
- **Honest Law-4 Residual Blind-Spot Lower Bound:** Built-in tomography (`compute_blind_spot_tomography`) explicitly notes that `14/14` in-sample recall over `8` baseline signatures plus `6` canonical escape classes is **not** proof of zero universal blind spot; unextracted prose claims, undiscovered upstream spec edge cases, unrecorded external measurements, and novel mathematical counterexamples remain irreducible residual classes.

### 2.3 `aletheia.magnetic_field_v21` — Strict Certificate I/O, Law-1b Field Coupling, Gate-8 Order, & Pre-Push Gate

1. **Unified Zone-B-Hardened Strict Certificate I/O:** Strict `type()` guards rejecting bool-as-int and builtin/Path subclasses, `MAX_INT_BITS = 2048` / `MAX_INT_DIGITS = 620` with zero untrusted-int decimal formatting in exceptions, iterative `MAX_JSON_DEPTH = 64` tree validation, strict 64-lowercase-ASCII-hex pre-check before `hmac.compare_digest`, LF-only JSONL splitting (`text.split("\n")`, never splitting inside Unicode line separators `\u2028`/`\u2029`), and fail-closed symlink/NUL/surrogate/CR/size-capped JSON, JSONL, and canonical certificate file loaders.
2. **Law-1b Omni-Vein Dispatch & Starvation-Capped Routing:**
   - `compute_field_coupling_dispatch`: computes the unhardened target set across all active workstreams and, when supplied an independent `dispatched_veins` list, audits finite-set conservation (`zero_sink_conserved`: `active_veins - (already_hardened | dispatched_veins) == empty`, reporting `uncovered_veins` and exact rational `post_coupling_coverage_q`) to detect single-repo hardening silos.
   - `route_verification_task`: deterministic exact-$\mathbb{Q}$ (`queue_depth / max_concurrent`) load balancer across $N \ge 2$ verifiers with hard starvation rerouting (`oldest_wait_s > starvation_cap_s`).
   - `evaluate_monitor_cadence`: exact-$\mathbb{Q}$ polling-drag detector (`turns / post` and polling-task share ceilings).
3. **Gate-8 Pre-Registration Timestamp-Order Guard (`verify_gate8_prereg_order`):** Enforces strict integer UTC precedence `observation_epoch_s > prereg_epoch_s` and `observation_epoch_s - prereg_epoch_s >= max(1, min_lead_s)`, ensuring equal timestamps `(t, t)` are rejected as `POST_HOC_OR_INSUFFICIENT_LEAD`.
4. **7-Gate Deterministic Pre-Push & Hygiene Bundle (`evaluate_pre_push_bundle`):** Enforces exact allowed/required bundle key sets (`UNKNOWN_BUNDLE_KEYS` / `MISSING_BUNDLE_KEYS`, making `staged_text` required so renamed fields cannot silently bypass leak scanning) and combines $O(n)$ linear `check_dco_signoff` (zero backtracking regexes), `check_repo_visibility`, `check_graphql_file_completeness`, `check_openblas_pin`, `check_pr_review_action`, `check_gitignore_receipt_integrity`, and programmatic `check_text_hygiene` (personal paths, credentials, CR/CRLF, `Co-Authored-By:` trailers).

---

## 3. Standalone Verification Commands

```bash
# 1. Self-test all three v2.1 additive modules in isolated zero-bytecode mode
python3 -I -B aletheia/zone_b_fuzzer.py --self-test --json
python3 -I -B aletheia/claim_witness.py --self-test --json
python3 -I -B aletheia/magnetic_field_v21.py --self-test --json

# 2. Fuzz any external `--check` CLI certificate verifier
python3 -I -O -B -W error aletheia/zone_b_fuzzer.py \
  --target-cli /path/to/audit_script.py --cert /path/to/certificate.json --json

# 3. Run full test & self-audit suite across all 3 canonical R4 isolated modes (+ PYTHONHASHSEED parity)
python3 -I -B tests/run_all.py
python3 -I -O -B tests/run_all.py
python3 -I -B -W error tests/run_all.py
PYTHONHASHSEED=42 python3 -B tests/run_all.py
```

Follow-up CLI wiring into `aletheia/cli.py` (`aletheia zone-b-fuzz`, `aletheia claim-witness`, `aletheia pre-push-gate`) is intentionally deferred to a thin wiring PR once concurrent `aletheia/cli.py` fixes land cleanly on `main`.
