# EXP-Q42c — Anti-Collusion Reciprocity-Cycle and Correlated-Verifier Hodge Gate

## Claim

Two reviewers of a large swarm look independent only on paper. If their
false-accept events are mixed with correlation weight rho toward the shared
(common-mode) event, the joint false-accept probability is

    P_joint = rho * min(eps1, eps2) + (1 - rho) * eps1 * eps2  >=  eps1 * eps2,

strictly above the independent product whenever rho > 0 and
min(eps1, eps2) > eps1 * eps2. A blinded cross-lane assignment that admits a
mutual review swap (a reciprocity 2-cycle, A_uv = A_vu = 1) therefore loses
exactly the suppression factor min(eps_a, eps_b) / (eps_a * eps_b) that
multi-translator independent collation was supposed to buy. The gate below
detects such 2-cycles combinatorially: over a binary review adjacency matrix
with zero diagonal, tr(A^2) = sum_{i,j} A_ij A_ji equals twice the number of
mutual swap edges, and the skew-curl (antisymmetric Hodge) part satisfies
(A_ij - A_ji)^2 = A_ij + A_ji - 2 A_ij A_ji per unordered pair, separating
honest one-way cross-lane flow from symmetric reciprocity.

## Lean package (pure Init, Lean 4.36.0, zero external packages)

Package `lean/` (`ReciprocityGate`), 3 files, 9 public theorems, all in
denominators-cleared integer form (eps_i = e_i / D, rho = r / R):

- `min_mul_ge_prod`: e1 * e2 <= min(e1, e2) * D for 0 <= e_i <= D.
- `correlated_verifier_false_accept_bound`: exact excess identity
  jointCleared - indepCleared = r * (min(e1, e2) * D - e1 * e2), hence
  indepCleared <= jointCleared.
- `correlated_strict_excess`: strict inflation when r > 0 and e1 * e2 < min(e1, e2) * D.
- `collation_independence_collapse`: s * (ea * eb) <= s * (min(ea, eb) * D)
  with the exact factor identity (s * (min * D)) * (ea * eb) =
  (s * (ea * eb)) * (min * D), i.e. collapse factor min(eps) / (eps_a * eps_b).
- `collation_strict_collapse`: strict form for s > 0 under the gap hypothesis.
- `reciprocity_2cycle_trace_identity`: for a 3-node binary adjacency,
  sum_{i,j} A_ij A_ji = 2 * (A_01 A_10 + A_02 A_20 + A_12 A_21).
- `skew_curl_pair_identity`: (a - b)^2 = a + b - 2ab and a^2 = a for a, b in {0, 1}.
- `hodge_defect_decomposition_3node`: skew sum plus twice the mutual sum
  equals the unordered edge sum.
- `reciprocity_witness_sand_scarlet`: concrete witness e = (1, 2), D = 10:
  jointCleared at r/R = 1/2 is 12 vs independent 4 (cleared), 20 at full
  collusion, and equality at r = 0.

`AxiomAudit.lean` prints axioms for all 9 theorems; only `propext` and
`Quot.sound` occur. No sorry, axiom, native_decide, eval, metaprogramming
escape, or IO construct appears in the package (machine-checked by the
verifier's comment/string-stripping trust-escape guard).

## Exact auditor (pure int / Fraction, stdlib only)

`verify_s160_q42c_reciprocity_gate.py`:

- `evaluate_correlated_false_accept(eps1, eps2, rho)`: exact rational mixture
  law. Canonical witness `sand-sail` (eps = 1/10) vs `scarlet-nail`
  (eps = 1/5): independent joint 1/50, half-correlated joint 3/50
  (excess 1/25), full collusion 1/10; collation factor 5/1.
- `audit_review_graph_reciprocity(edges, assignments)`: fail-closed gate.
  Rejects self-reviews (`SELF_REVIEW_FORBIDDEN`), same-lane review
  (`NON_DISJOINT_LANE`), duplicate edges, unassigned agents, and mutual
  swaps (`RECIPROCITY_2CYCLE_DETECTED`); admits honest acyclic cross-lane
  DAGs. `reciprocity_decomposition` exposes the exact symmetric/antisymmetric
  defect split (mutual pairs, tr(A^2), skew pairs) with the identity
  skew + tr(A^2) = total edges.
- `run_reciprocity_benchmark`: seeded (`random.Random(16042)` only inside
  the sweep) planted 2-cycle review graphs (24 nodes, 6 planted mutual
  pairs, 20 trials) against degree-matched configuration-model nulls built
  by stub matching on the planted in/out degree sequences. Exact rational
  Mann-Whitney AUROC = 1/1 (>= 95/100), FPR at threshold 4 = 0/1 (< 1/100),
  TPR = 1/1; honest cross-lane graphs are admitted.
- Fail-closed I/O: O_DIRECTORY|O_NOFOLLOW directory open, O_NOFOLLOW|O_NONBLOCK
  file open, S_ISREG check, streaming 1 MiB cap, strict UTF-8/LF, float-free
  and duplicate-free JSON pre-parse with nesting depth <= 32 and integer
  digits <= 256 (RecursionError maps to RC=2), symlink-ancestor rejection.
- CLI: `--check [path] [--json]`, `--write [path] [--json]`,
  `--standalone [--json]`, `--live-lean`. All failures are single-line JSON
  on stderr with RC=2 and no tracebacks.

## Certificate

`s160_q42c_reciprocity_certificate.json` (schema `s160.q42c.reciprocity_gate.v1`)
carries the correlated witness, honest/colluding graph decompositions, full
benchmark score lists, Lean package summary, and a payload SHA-256 over the
canonical compact encoding.

## Verification

- **Deterministic & Mutation Verification:** `lake build` and `AxiomAudit.lean` pass under `--live-lean` (`RC=0`); `--check --json` output SHA-256 `527d2c31ce568b281849fd535c4de97880cf604eb03618ea4b11a1edcc360c6c` is bit-identical across `-I -B`, `-I -O -B`, and `-I -B -W error`; `test_s160_q42c_r5.py` runs **`15/15 OK ×3`** (`0` skipped); `aletheia audit-check --lean-audit --allow-project-import ReciprocityGate --strict-ancestors --safety-scan --strict-unseeded` **`PASS`** (`10` files, `2/2` R4, `3` Lean, `0` findings); dual `aletheia mutate` **`110/110 = 100.0%` (`default`) & `110/110 = 100.0%` (`--guards require_ok`), `0` survived** (`0` `ast.BoolOp` sites).
