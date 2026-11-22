# Aletheia Domain Pack: Computer Science & Systems

> **Scope:** Algorithms & combinatorial optimization, formal verification & certificate checkers, AI/ML safety & multi-adapter composition, planning/abstraction heuristics, and distributed/runtime systems.  
> **Core Challenge:** Software and ML systems silently fail through **permissive parsing, stripped `assert`s, dead validation guards, loose worst-case bounds, uncompiled proof claims, and metaphorical architecture prose** ("alignment sheaf", "emergent abstraction") disconnected from executable invariants.

---

## 1. Raw Portals in CS & Systems (Law 1)

In CS and systems, bugs, tightness gaps, and security bypasses are rarely mere engineering blemishes—they are **portals into exact structural theory**:

| Raw Friction / Failure | Cave-Shadow Default (Avoid) | Aletheia Portal Question |
|---|---|---|
| A certificate checker accepts a forged input (`rank >= 117` on a $2\times 2$ matrix, `AUDIT-001`) | Patch the single symptom and stop at `FALSIFIED` | What minimal TCB architecture + R1–R5 gate contract makes **every** forgery class unrepresentable, and what is the tightest provable theorem underneath? |
| Composing abstractions or LoRA/zone adapters loses $O(N^2)$ sharpness (`warp#15`, `quotient-lp-bounds`) | Accept conservative Cauchy–Schwarz or additive bounds as inevitable | Can exact Gram matrices ($Q_{\mathrm{stack}}(s)$) or sequential 1-cochain residual peeling ($c^{(j)} = c^{(j-1)} + d^0(\pi_j^* h_j^*)$) recover exact sharpness? |
| "Emergent coarse-graining = commutation" fails on counterexamples | Declare the concept dead or keep using the slogan informally | Which exact algebraic **semiring**—linear $(+,\times)$ Markov vs. tropical $(\min,+)$ Bellman—fails, and what exact parameter family ($q = e^{-\beta}$) connects them? |
| Post-hoc alignment patching fixes one eval benchmark while regressing unseen probes | Add more patches to the prompt/weights | Does fixed-spec adaptation strictly inflate out-of-distribution KL/Bregman divergence—proving a missing feature/specification dimension $\Psi$? |

---

## 2. The R1–R5 Executable Gate Contract (Law 3)

Every verifier, security boundary, certificate checker, and formal-audit tool in CS/systems **must** satisfy all five refusal-and-runtime contracts—never treating tests as decorative:

### R1 — Default-Reject (Fail-Closed)
- Any unrecognized schema version, missing field, unexpected key, unsupported branch, or unverified solver `"optimal"` status **must raise an explicit error** (never default to `True`, `0`, or a fallback heuristic).
- Separate the **untrusted producer** (LP solver, factorization search, neural heuristic) from the **minimal trusted verifier (TCB)** that independently checks exact algebraic identities (`primal == dual`, `P M P^T == L D L^T`, `C C_inv == I`).

### R2 — Omission Monotonicity
- Deleting or zeroing any certificate field, dual witness, constraint, or matrix entry can **never** turn a `REJECT` into an `ACCEPT` (nor strengthen a certified bound).

### R3 — Canonical Lowest-Terms & Type-Strict Parsing
Real exploits caught during the Cave Expedition (`AUDIT-001`, `AUDIT-006`, `AUDIT-015`, `AUDIT-016`) prove how easily Python's permissive coercions break exact TCBs:
- **Reject `bool` explicitly:** In Python, `isinstance(True, int)` is `True`! Every integer/rational validator must test `if isinstance(x, bool): raise ValueError(...)` *before* `isinstance(x, int)`.
- **Reject raw `float`, `NaN`/`Inf`, and duplicate JSON keys:** Use `json.loads(..., parse_float=reject, parse_constant=reject, object_pairs_hook=no_dupes)` on JSON inputs AND enforce direct-API matrix guards (`_require_exact_square_matrix`) so direct Python callers cannot slip floats/bools/ragged rows past string parsers (`AUDIT-006R`: `6/6` direct-API forgeries blocked).
- **Enforce strict canonical lowest-terms ASCII rationals:** Reject leading zeros (`"007"`, `"01/2"`), signed zero (`"-0"`), unreduced or unit-denominator fractions (`"2/4"`, `"0/5"`, `"3/1"`), underscores (`"1_000"`), whitespace, newlines, and Unicode digits (`"١/٢"`) (`AUDIT-006R`: `23/23` bad strings blocked; `AUDIT-016R`: `7/7` non-reduced strings blocked).
- **Enforce symbolic invariants on structured objects:** In `AUDIT-015`, `PolyMatrix` and `RatMatrix` checked only the upper triangle `j >= i` at evaluation time, allowing non-Hermitian forgeries (`[[1 + i x, 0], [0, 1]]`) with a Hermitian midpoint to certify `(2, 0, 0)`. `AUDIT-015R` closed all `8/8` symbolic and interval forgeries by enforcing symbolic conjugate symmetry and real diagonals in `__post_init__`.

### R4 — Isolated Multi-Mode Parity & Zero Bare `assert`s
- **Zero bare `assert`s on any trust, validation, or verification path:** Python's `-O` flag silently deletes every `assert` statement. Use explicit `if not cond: raise ValueError("EXPLICIT_CODE")` checks everywhere.
- **Bit-identical 3-mode isolated execution:** Every standalone script and test suite must use LF-only line endings (`0` CRLF) and pass identically under:
  ```bash
  python3 -I -B <script.py> && \
  python3 -I -O -B <script.py> && \
  python3 -I -B -W error <script.py>
  ```
  Running with `-I` (isolated `sys.path`) catches hidden working-directory imports; `-W error` catches Python 3.14 invalid escape `SyntaxWarning`s and deprecation traps; `-O` catches stripped assertions.

### R5 — Refusal-Site Mutation Suites (Kill 100% of Check Deletions)
- A guard without a failing test is indistinguishable from dead code. Pair every refusal branch in the TCB with an automated mutation suite (`aletheia mutate`) that systematically bypasses or deletes each guard one at a time and verifies that the test suite **kills 100% of mutants (`0` survivors)**.
- *Reference benchmark (`AUDIT-016R`, `Foundation-0/spectral-inertia`):* **`41/41` refusal-site mutants killed (`100.0%`, `0` survivors)** across `-I -B` and `-I -O -B`.

---

## 3. Cross-Domain Operator Rigor in Algorithms & AI Safety (Law 5)

Aletheia forbids claiming algorithmic or safety unifications from shared vocabulary. Every bridge must compile to an exact operator, certificate, or counterexample:

### Pattern A: Exact LP / Farkas Dual Certificates & Iterative Multi-Quotient Peeling (`AUDIT-004` `N2`)
In heuristic search, model checking, and quotient abstraction (`Foundation-0/quotient-lp-bounds`, `ahrazzle/soko`):
- **Cohomological Optimality & Sequential Peeling:** Rather than combining abstraction heuristics only via `zeroSelfLoop_deficit` (which yields `+0` when moves modify multiple resources simultaneously), solve exact-rational 1-Lipschitz quotient LPs sequentially with independent Farkas dual flow certificates (`primal == dual`) and update concrete edge costs by the **exact 1-cochain gauge shift**:
  $$c^{(j)}(s, s') = c^{(j-1)}(s, s') + h_j^*(\pi_j(s')) - h_j^*(\pi_j(s)) \ge 0.$$
- **Verified Result (`Foundation-0/quotient-lp-bounds#5`):** On a coupled 32-state 2-resource system (exact micro-distance sum `124`), single quotient $\pi_x$ and $\pi_x$ + best `zeroSelfLoop_deficit` both stall at `64`, whereas **2-layer Peeling ($\pi_x \to \pi_y$) reaches `112` (`+48`)** and **3-layer Peeling (+ 4-state imbalance quotient) reaches `124` (100% exact micro-optimal, $\delta_{\mathrm{emg}}^{\mathrm{trop}} \equiv 0$)**. On asymmetric costs, peeling order is non-commutative ($H_{xy}=88, H_{yx}=76$), and pointwise $\max(H_{xy}, H_{yx}) = 203/2$ remains globally 1-Lipschitz.

### Pattern B: Semiring Split & Exact $\mathbb{Q}[q]$ Maslov–Doob Homotopy (`AUDIT-004`, `AUDIT-008R`)
- **Anti-Shadow Counterexamples:** Exact rational witnesses prove that linear Markov lumpability ($\delta^{\mathrm{lin}} = \|(I-\Pi)P\Pi\|_{\mathrm{HS}}^2 = 0$, $(+,\times)$ semiring) and tropical Bellman commutation ($\delta^{\mathrm{trop}} = 0$, $(\min,+)$ semiring) are **mathematically inequivalent in both directions** (`dir1: trop=0, lin=1/4`; `dir2: lin=0, trop=2`).
- **Steelmanned Bridge:** Setting $q = e^{-\beta} \in \mathbb{Q} \cap (0, 1)$ turns 1-cochain Farkas peeling identically into the **Doob $h$-transform similarity** $K_q' = D_h^{-1} K_q D_h$ (`Tr(K^1..4)` exact match, suboptimal entries decay as $q^2$). Exact 5-state **row-normalized stochastic Boltzmann** witnesses show that lumpability can hold *accidentally* at a single temperature ($P_q(1\to Y) - P_q(2\to Y) = \frac{1-2q}{2(2q+1)} = 0 \iff q=1/2$, tropical defect `1`), whereas all-$\beta$ multiset rigidity enforces zero defect at every $q$ and in the tropical limit $q \to 0^+$.

### Pattern C: Contextual Compute Sheaves & Stacked-Adapter Spectral Certification (`SEAM-06`, `AUDIT-004` Part C, `AUDIT-006R` Check 9)
For multi-domain LLM routing, LoRA/adapter composition, and modular AI safety (`siliconcordat/loom#5`, `warp#15`):
1. **Eliminating the $1/N^2$ Stacked-Adapter Cauchy–Schwarz Tax:** Bounding stacked low-rank adapters $\Delta W = \sum_{k=1}^N B_k A_k$ via Cauchy–Schwarz ($\sigma_{\max}^2 \le N \sum_k \sigma_k^2$) imposes an $N^2$ squared penalty ($16\times$ for $N=4$ orthogonal adapters!). Concatenating $B_{\mathrm{stack}} = [B_1, \dots, B_N]$, $A_{\mathrm{stack}} = [A_1; \dots; A_N]$ and certifying the exact rational Gram matrix
   $$Q_{\mathrm{stack}}(s) \;=\; s\,G_B - G_B G_A G_B \;\succeq\; 0$$
   via block-$LDL^\top$ certifies **exact $s = 1$** for disjoint orthogonal zone adapters (eliminating the $16\times$ tax), rejects $s = 99/100$, immediately flags constructive interference on a shared `"fluid dynamics"` carrier between open `bio` + `astro` (`inertia = [0, 1, 3]` at $s=1$, PSD at $s=4$), and restores exact $s=1$ (`[0, 0, 2]`) when contextual gating closes `astro`.
2. **Cellular Sheaf Cohomology for Overlapping Contexts:** Modeling overlapping domain patches (`bio`, `astro`, overlap `fluid_dynamics`) as a cellular sheaf distinguishes compatible flat gluing (`inertia = (4, 0, 2)`, $\dim H^0 = 2$) from conflicting domain transport (`(6, 0, 0)`, $\dim H^0 = 0$, certified spectral-gap obstruction $\lambda_{\min}(\Delta_{\mathcal{F}}) \in [97/1024, 389/4096]$) and verifies exact obstruction removal under open-star contextual gating (`(2, 0, 2)`).
3. **Two-Loop Alignment & Specification Expansion (`AUDIT-005`, `AUDIT-008R`):** Exact Euclidean & KL/Bregman Pythagoras proves that forcing a fixed-capacity policy/representation $\Phi$ to patch a failing safety probe $a_1$ strictly inflates global loss ($+\,D_F(q^* \| q_{\mathrm{adapt}})$) and induces targeted regressions outside $0 < \rho_{\Phi, G}/\kappa_\perp < 2$—separating *symptom patching* from genuine *specification revision*.

---

## 4. Strict Provenance & Proof-Assistant Honesty (Law 4)

CS & formal-methods claims suffer acutely from **status inflation**. Aletheia enforces exact labels:

| Artifact State | Required Honest Label | Forbidden Overclaim |
|---|---|---|
| Branch pushed to GitHub for peer review | **`Draft PR`** (with exact PR URL & commit SHA) | "Merged", "landed upstream", "accepted by maintainers" |
| Lean 4 / Coq / Isabelle file written where compiler is absent on host | **`uncompiled_source`** (as in `Foundation-0/spectral-inertia` `lean/SpectralInertia/Basic.lean`, `AUDIT-016R`) | "Formally verified in Lean 4", "machine-checked proof" |
| Lean 4 file compiled locally with `lake env lean` | **`compiled_formal`** + exact toolchain version + `#print axioms` output confirming zero `sorry` / custom axioms | Claiming verification without printing axioms |
| Exact rational Python verifier passed independent clean-room audit | **`VERIFIED` (`exact`)** with exact `AUDIT-NNN`, R4 commands, and mutant kill rate | Claiming formal theorem-prover equivalence |
| Toy/synthetic problem solved instead of live target repo | **`FALSIFIED` / Substitution Shadow** (`AUDIT-013`) | Presenting toy-model passes as upstream benchmarks |

---

## 5. CS & Systems Anti-Patterns

1. **Assertion-Only Verification:** Using bare `assert` inside checkers so `python3 -O` silently passes every forgery. *Fix:* Explicit `if ...: raise ValueError(...)` + R4 `-I -O -B` parity.
2. **String-Only Input Validation:** Hardening a JSON parser while leaving direct Python function calls open to raw `float`/`bool`/asymmetric matrices (`AUDIT-006`, `AUDIT-013`, `AUDIT-015`). *Fix:* Enforce type/shape/symmetry guards at the TCB core boundary AND test with direct-API forgeries.
3. **Untested Refusal Branches:** Writing defensive `if` checks that no test exercises. *Fix:* Automated R5 refusal-site mutation suite (`aletheia mutate`, target `100%` kill rate).
4. **Trusting Floating-Point Tolerances or Unverified Solver Flags:** Treating `eigvalsh(M).min() > -1e-10` or `scipy.optimize.linprog().success == True` as mathematical certificates. *Fix:* Emit exact rational primal-dual / congruence witnesses checked by a zero-float TCB.
5. **Conflating Verbal Architecture with Operator Equivalence:** Claiming two systems are "isomorphic sheaves" without an executable restriction map, intertwining defect, or Schur complement. *Fix:* Law 5 executable map or explicit counterexample.

---

## 6. Quickstart Workflow

```bash
# 1. Scaffold a CS/systems/verification expedition workspace
aletheia init ./my-sys-expedition --domain cs-systems

# 2. Run R1-R4 hygiene, AST zero-assert, JSON/schema, and provenance gates
aletheia audit-check ./my-sys-expedition

# 3. Run R5 refusal-site mutation testing against your TCB verifier
aletheia mutate ./my-sys-expedition/path/to/tcb.py --test-cmd "python3 -I -O -B -W error ./my-sys-expedition/tests/run_all.py"

# 4. Diagnose Cave-Shadow relapses (uncompiled proof overclaims, missing negative controls)
aletheia diagnose ./my-sys-expedition
```

See also: [Domains Rosetta Stone](./README.md) · [Laws & Gates Specification](../spec/LAWS_AND_GATES.md) · [Aletheia Theory](../THEORY.md) · [Cave Expedition Case Study](../evidence/cave-expedition-case-study.md)

---

## 7. Reference Evidence from the Cave Expedition

- **`AUDIT-001` & `AUDIT-016R` (`Foundation-0/spectral-inertia`):** 6 TCB exploits caught and closed; hardened dual-oracle $\mathbb{Q}(i)$ certifier + **`41/41` R5 mutants killed (`0` survivors)** + honestly tagged `uncompiled_source` Lean 4 module.
- **`AUDIT-015R` (`Foundation-0/spectral-inertia`):** Complex-Hermitian Bernstein box certifier hardened against `8/8` symbolic & callable non-Hermitian forgeries.
- **`AUDIT-004` (`VERIFIED`, `exact`, `N2` — `Foundation-0/quotient-lp-bounds#5`):** Iterative Multi-Quotient Farkas Peeling Tower, bidirectional linear-vs-tropical emergence separation, and `docs/08` Contextual Compute cellular sheaf.
- **`AUDIT-006R` (`VERIFIED`, `exact`, `N1`/`N2` — `Foundation-0/project-asma#101`):** Hardened canonical R3/direct-API TCB + `SEAM-06` `warp#15` stacked-adapter Gram eliminating $16\times$ Cauchy–Schwarz tax.
- **`AUDIT-008R` (`VERIFIED`, `exact`, `N1` — `Foundation-0/quotient-lp-bounds#5`):** $\mathbb{Q}[q]$ Maslov–Doob homotopy + row-normalized Boltzmann accidental single-$q$ lumpability witness.
