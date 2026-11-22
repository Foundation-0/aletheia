# Domain Adaptation Pack: Pure & Computational Mathematics and Formal Proof

> **Parent framework:** [The Aletheia Method](../README.md) · [First-Principles Theory](../THEORY.md) · [Canonical Laws & Gates](../spec/LAWS_AND_GATES.md) · [Cave Expedition Case Study](../evidence/cave-expedition-case-study.md) · [Domain Index](./README.md)  
> **Companion pack:** [Materials, Geometry & Engineering](./materials-geometry-and-engineering.md) · **Live 3-second demo:** [`examples/worked_resonance_cycle/`](../examples/worked_resonance_cycle/README.md)

Pure and computational mathematics is the sharpest testing ground for **The Aletheia Method** (*Portal-Driven Resonance & Adversarial Tomography*), because mathematical truth admits zero-tolerance exact oracles — yet AI agents and human reviewers routinely fall into **Plato's Cave** in mathematics anyway.

A static critical prior reads a rough proof sketch or messy exploratory script, spots a missing hypothesis or a floating-point/TCB bug, declares the claim `FALSIFIED` or `N0`, and stops. Aletheia turns that reflex inside out: **never hide the bug, never stop at the bug.** Isolate the failure cleanly, ask what stronger exact invariant sits five millimeters beside the broken formula, prove or falsify *that* steelmanned claim in exact arithmetic with a zero-shared-code dual oracle, and convert every sharpness wall or impossibility barrier into either a theorem or a new branch trigger.

---

## 1. Mapping Aletheia's Five Laws to Mathematical Research

| Aletheia Law | Conventional Failure Mode ("Cave Shadow") | Mathematical Practice Under Aletheia |
|---|---|---|
| **Law 1 — Active Portal Keeper** | Treating raw proof drafts, exploratory notebooks, and messy preprints as finished papers to grade once and file away. | Keep an active navigator re-entering rough notes and peer repos whenever a calculation uncovers a new algebraic invariant (e.g., $C_4^{\mathrm{nilp}}$ triggering $F_8 \to E_8$; linear-vs-tropical split triggering $\mathbb{Q}[q]$ Maslov–Doob homotopy). |
| **Law 2 — Steelman Before Falsify** | Dismissing an inequality or construction because the prototype code omits a guard (e.g., missing $P \succeq 0$ check in `AUDIT-001`) or an initial lemma assumes an over-strong premise. | Log the prototype bug honestly (`FALSIFIED` / `PARTIAL`), then repair and **strengthen** the underlying mathematical target via block decomposition, explicit slack identities, or hypothesis tightening (`AUDIT-002`, `AUDIT-020R`). |
| **Law 3 — Multi-Basis Observer Tomography ($\mathcal{G}_{\mathrm{obs}}$)** | Verifying an algebraic certificate using the same solver that produced it, or checking equality/positivity up to `1e-12` IEEE float noise. | Run independent, **zero-shared-code** exact oracles over exact rings ($\mathbb{Z}$, $\mathbb{Q}$, $\mathbb{Q}(i)$, $\mathbb{Z}[\sqrt{2}]$, `SymPy`), enforce strict R1–R5 gate integrity, and verify every boundary guard with must-fail controls and refusal-site mutation tests. |
| **Law 4 — Honest `N0`/`N1`/`N2` & Full-Text Prior Art** | Judging novelty from titles/abstracts in memory, or claiming "proven in Lean" when no compiler was run. | Default every theorem to `N0` until full-text comparison against exact lemmas in prior papers/PRs establishes the exact delta. Tag uncompiled formalization files strictly as `uncompiled_source` and state every scope boundary explicitly. |
| **Law 5 — Exact-Operator Cross-Pollination** | Claiming two fields are unified because both mention "sheaves", "duality", or "curvature". | Bridge fields *only* through an explicit operator identity or functorial map transferring a quantitative bound or obstruction (e.g., Schur-complement fiber elimination unifying spectral inertia, cellular elastic sheaves, tropical peeling, and Lindblad dynamics). |

---

## 2. Portals in Pure & Computational Mathematics (Law 1)

In mathematical discovery, the highest-yield **portals** are rarely polished theorems. They are four recurring signals that static critique almost always throws away:

1. **Broken Prototype Verifiers & Guardless Inequalities:** A script that forges an impossible conclusion often wraps a genuine inequality whose domain or scaling was never maximized. In `AUDIT-001`, a prototype rank certifier omitted $P = H - Q \succeq 0$ and forged $\operatorname{rank}(P) \ge 117$ on a $2\times 2$ matrix. Instead of archiving the thread, steelmanning the underlying Lemma 3.2 formula on $W \oplus W^\perp$ unlocked `AUDIT-002` (`N2`) and directly spawned the higher-moment theorems of `AUDIT-014` (`N2`).
2. **Low-Dimensional Algebraic Coincidences:** When a general formula exhibits an unexpected simplification at one dimension or parameter value, treat it as a portal into hidden symmetry. In `AUDIT-009`, while proving the all-dimension $F_n \to D_n$ fold ($n \ge 3$), an unexpected 4D generator satisfied $(C_4^{\mathrm{nilp}})^2 = 0$ and $\det L_4(s) \equiv d(s)^4$. Asking *why* $2^n = 4n$ singled out $n=4$ immediately led to half-integer spinor roots $(\pm\tfrac{1}{2})^n$ having squared length $2$ **uniquely at $n=8$**, unlocking the landmark Sylvester–Hadamard $F_8 \to E_8$ fold (`AUDIT-017`, `N2`).
3. **Semiring & Representation Splits:** When two candidate formalisms disagree on a concrete example (e.g., exact linear lumpability with nonzero tropical defect, and vice versa in `AUDIT-004`), do not pick one and discard the other. Re-enter the portal to search for a one-parameter homotopy unifying both extremes (e.g., $\mathbb{Q}[q]$ Maslov–Doob kernels $K_q(i,j) = q^{c_{ij}}$ in `AUDIT-008R`).
4. **Sharpness Walls & Counterexample Obstructions:** When a verifier proves that an inequality is **pointwise sharp**, that wall is a portal telling you *which exact missing invariant* is needed to go further. Proving integer-exact sharpness $\min\operatorname{rank}(P) = \max(1, \lceil R_{\mathrm{opt}} \rceil)$ from 2nd-moment data $(u, t, S, b)$ in `AUDIT-002` proved that any stronger bound *must* introduce 3rd and 4th spectral moments ($S_3, S_4$) — triggering `AUDIT-014` (`R_{H4}, R_{H6}, \Phi_{x_0,\tau}, R_{W4}`).

---

## 3. Steelmanning Broken Lemmas: Four Concrete Algebraic Moves (Law 2)

When an initial lemma or script breaks under Gate 1–4 scrutiny, apply these four exact algebraic repair patterns before declaring the direction dead:

### Move A — Orthogonal Block Decomposition ($W \oplus W^\perp$)
Isolate the nuisance or indefinite subspace explicitly before bounding. For Hermitian $H = P + Q$ with $P \succeq 0$ and $n_+(Q) \le b$, decomposing $Q = Q_+ - Q_-$ and setting $W = \operatorname{range}(Q_+)$ ($\dim W = b_+ \le b$) replaces total $\operatorname{rank}(P)$ with the strictly stronger projected-inertia chain (`AUDIT-002`):
$$\operatorname{rank}(P) \;\ge\; \operatorname{rank}(\Pi_{W^\perp} P \Pi_{W^\perp}) \;\ge\; n_+(\Pi_{W^\perp} H \Pi_{W^\perp}) \;\ge\; R_{\mathrm{opt}}(u, t, S, b).$$
Jointly optimizing the scale parameter and weight $c \ge 1$ removes arbitrary constants (like fixed $c = 2$) and produces a scale-invariant two-regime envelope:
$$R_{\mathrm{opt}}(u, t, S, b) = \begin{cases} 0, & u \le 0 \text{ or } u+t \le 0, \\ \dfrac{u^2}{S - t^2/b}, & u > 0,\; b > 0,\; t > 0,\; t(u+t) \ge bS, \\ \max\!\left(0,\; \dfrac{(u+t)^2}{S} - b\right), & \text{otherwise.} \end{cases}$$

### Move B — Slack-Identity & Sum-of-Squares (SOS) Excavation
Convert opaque inequalities into **explicit nonnegative algebraic identities**. Every term in a slack identity serves two purposes: it makes machine verification trivial over $\mathbb{Q}$, and setting the slack terms to zero immediately exhibits the exact equality/sharpness family.
- **Quadratic 6-term slack (`AUDIT-002`):** Writing $n_+(H_\perp) + c^2 b - (2u + 2ct - S)$ as a sum of six explicitly nonnegative Frobenius/trace terms exposed both boundary guards ($u=0, t^2=bS$ zero-division and negative else-branch) and produced the exact sharpness construction.
- **Quartic rational SOS (`AUDIT-014`):** Replacing floating-point eigenvalue optimization with exact rational SOS certificates — such as $\phi_a(\lambda) = 1 - q_a(\lambda)^2 \le \mathbf{1}_{(0,\infty)}(\lambda)$ for $a \in \mathbb{Q}_{\ge 0}^m$ (Theorem A2, Stieltjes–Hankel $R_{H,2m}$) and the double-zero noise-annihilating quartic $\Phi_{x_0,\tau}(\lambda)$ (Theorem A3) — makes every rank lower bound verifiable by polynomial coefficient comparison alone.

### Move C — Obstruction Elevation (Turning "Impossible" into a Theorem)
Whenever a search or construction hits an impassable wall, do not report *"failed to find a solution."* Prove *why* no solution exists:
- **Determinant-square & parity obstructions (`AUDIT-017`):** Proved exact algebraic obstructions blocking bar-preserving $F_n \to E_6, E_7, D_n^+$ ($n \ne 8$) embeddings via Cartan determinant parity ($\det E_6 = 3, \det E_7 = 2, \det E_8 = 1$) and spinor norm arithmetic.
- **Irreducible Root-Graph Obstruction (`AUDIT-020R`):** Proved $F_{16} \not\to E_8 \oplus E_8$ — and in general $F_n \not\to \Gamma_1 \oplus \Gamma_2$ for *any* nontrivial orthogonal direct sum and *any* rotation $R \in O(n)$ — directly redirecting the 16D/24D frontier to the irreducible optimal lattices Barnes–Wall $\Lambda_{16}$ and Leech $\Lambda_{24}/\sqrt{2}$.

### Move D — Hypothesis & Gate Tightening Under Adversarial Refutation
When a clean-room audit catches a genuine gap in a proof's lemma, fix the **algebraic premise and its runtime gate together**, never by weakening the theorem informally:
- **Case study (`AUDIT-020` $\to$ `AUDIT-020R`):** The initial proof of global-$\mathbb{Z}^n$ non-overlap along expanding Cayley arcs for rescaled $\Lambda_{16}/\sqrt{2}$ and $\Lambda_{24}/\sqrt{2}$ assumed the rescaled lattices were **even** ($\|w\|^2 \ge 4$ outside the root shell). Independent tomography produced explicit **norm$^2 = 3$ witnesses** (BW16 vector $v_2 = (-1, 1^7, 2, 0^7)$ with $\|v_2/2\|^2 = 3$; Leech weight-12 Golay dodecad $u = 2\cdot\mathbf{1}_D$ with $\|u/4\|^2 = 3$) and a concrete `K_X * tau^2 = 2/75` bypass accepted by the loose Gate (2) bound $\|A\|_2 \le 1/4$ (since $\sqrt{3} - 2(1/4) \approx 1.232 < \sqrt{2}$).
- **The exact repair:** Replaced the false evenness claim with explicit mod-4 and mod-16 **integral-norm proofs** ($\|w\|^2 \in \mathbb{Z}_{\ge 2}$), tightened Gate (2) to $\|A\|_2 \le 1/8$ (`K_X * tau^2 <= 1/144`, `lam0 * tau / 2 <= 1/24`, using the zero-float inequality $\sqrt{3} - \sqrt{2} > 1/4$), and added a 9th must-fail control (`C9_norm3_gate2_boundary_rejected`). Both certified arcs already cleared the tightened gate by orders of magnitude (`8.63e-7` and `2.01e-19`), upgrading the landmark result cleanly to `VERIFIED` `N2`.

---

## 4. Exact-Arithmetic Oracles & Zero-Shared-Code Tomography (Law 3)

In mathematics, **Oracle Class `exact`** requires that every inequality, sign, rank, inertia, and polynomial identity in the Trusted Computing Base (TCB) be decided without IEEE-754 floating-point approximation.

### Choosing the Right Exact Number Ring & Oracle Pair

| Mathematical Domain | Primary Exact Ring / Engine | Independent Zero-Shared-Code Oracle ($\mathcal{G}_{\mathrm{obs}}$) | Cave Expedition Reference |
|---|---|---|---|
| Real symmetric / rational LP / Farkas / sheaves | `int`, `fractions.Fraction` | Independent primal witness builder + Dijkstra / Gauss elimination / `SymPy` | `AUDIT-004`, `005`, `010`, `019` |
| Complex Hermitian matrices & inertia | Gaussian rationals $\mathbb{Q}(i)$ (`(Fraction, Fraction)`) | Sylvester congruence (`PLDL*` / `C M C* = D`) **paired with** Faddeev–LeVerrier + Cayley–Hamilton + Descartes & Sturm square-free peel | `AUDIT-002`, `014`, `016R` |
| Algebraic folding curves & Bernstein non-overlap | Quadratic field $\mathbb{Z}[\sqrt{2}]$ / $\mathbb{Q}(\sqrt{2})$ | Full symbolic `SymPy` block-diagonalization + direct combinatorial lattice-shell bijection + direct $\mathbb{Q}(\sqrt{2})$ point evaluations | `AUDIT-009`, `017` |
| Parametric non-affine stability boxes | Exact rational intervals `QI` + `math.isqrt` outer square-root brackets + multivariate Bernstein tensors | Independent interior Descartes sampling across hundreds of rational points + adversarial non-Hermitian symbolic forgery suite | `AUDIT-013R`, `015R` |
| One-parameter homotopies & symbolic superoperators | Polynomial ring $\mathbb{Q}[q]$ / `SymPy` symbolic rational functions | Independent clean-room symbolic derivation from upstream definitions + exact rational specialization checks | `AUDIT-008R`, `011R`, `018` |
| Formal proof assistants | Lean 4 / Coq / Isabelle source files | Actual compiler invocation (`lake build`, `coqc`, `isabelle build`) with zero `sorry`/`admit`/unreviewed axioms | `AUDIT-016R` (tagged `uncompiled_source` when `lean` absent) |

### Strict R1–R5 Gate Contracts for Mathematical Certifiers
Every executable mathematical verifier in an Aletheia project must satisfy:
- **R1 (Default-Reject):** Every certificate returns an explicit structured refusal unless *all* hypotheses pass. Never fall through silently on edge cases.
- **R2 (Omission Monotonicity):** Deleting any required field, moment, or certificate component must strictly produce a rejection, never a weaker fallback pass.
- **R3 (Canonical Type & Encoding Strictness):**
  - Reject Python `bool` explicitly (`isinstance(x, bool)` is `True` for `int` subclasses — a notorious silent bug in Python `Fraction` TCBs!).
  - Reject `float` explicitly on exact trust paths (never silently call `Fraction(1.5)` inside a certifier).
  - Parse rational strings strictly in lowest terms with no leading zeros, whitespace, underscores, decimal notation, or non-ASCII digits (`AUDIT-006R`, `AUDIT-016R`).
- **R4 (Isolated 3-Mode Determinism & Zero Bare `assert`s):**
  - Never use bare Python `assert` on any trust or verification path — `python3 -O` strips every `assert` statement! Always use an explicit `require(cond, code, msg)` function raising `ValueError`/`TypeError`.
  - Verify bit-identical deterministic output across all three isolated execution modes:
    ```bash
    python3 -I -B script.py --json
    python3 -I -O -B script.py --json
    python3 -I -B -W error script.py --json
    ```
- **R5 (Must-Fail Controls & Refusal-Site Mutation Suite):**
  - Ship concrete negative controls covering every failure mode (non-PSD $P$, non-Hermitian $H$, negative Hankel weights $a_k < 0$, wrong dimensions, `bool`/`float` leaks, boundary violations).
  - Verify via an automated mutation suite that **deleting or weakening any single guard causes at least one control to fail** (`41/41` mutants killed, `0` survivors in `AUDIT-015R`/`016R`).

### Strict Formal-Proof Standing Rule (`uncompiled_source`)
Writing a `.lean` or `.v` file next to a Python verifier does **not** earn a "formally verified in Lean" badge unless the actual compiler checked it with zero `sorry` / `admit` placeholders and zero custom axioms in a reproducible build log. When the compiler is unavailable in the current environment, Aletheia enforces **strict provenance honesty**:
- Mark the file explicitly as **`uncompiled_source`** (as done for `Basic.lean` in `AUDIT-016` / `AUDIT-016R`),
- Keep the authoritative `VERIFIED` claim anchored to the executed exact-arithmetic & symbolic oracles, and
- Queue machine compilation as an explicit next-wave verification task.

---

## 5. Worked Case-Study Ledger from the Cave Expedition

Every technique above is battle-tested in our audited ledger ([`evidence/cave-expedition-case-study.md`](../evidence/cave-expedition-case-study.md)):

| Audit ID | Portal Trigger | Steelman / Exact Move | Independent Oracle ($\mathcal{G}_{\mathrm{obs}}$) | Defect / Wall Overcome | Standing & Honest Scope |
|---|---|---|---|---|---|
| **`AUDIT-002`** | `AUDIT-001` $2\times 2$ rank $\ge 117$ forgery | $W \oplus W^\perp$ block slack identity $\to$ scale-invariant $R_{\mathrm{opt}}(u,t,S,b)$ | 420 $\mathbb{Q}(i)$ matrices vs. zero-shared-code Faddeev–LeVerrier + Descartes | Fixed 2 boundary bugs (`0/0` at $u=0$, neg else-branch); proved sharpness wall $\min\operatorname{rank}(P) = \max(1,\lceil R_{\mathrm{opt}}\rceil)$ | `VERIFIED` `N2` (full-text checked vs. `arXiv:2610.08965v1`, `2608.13637`, `loom#7`) |
| **`AUDIT-009`** | 3D/4D folding & $2^n=4n$ curiosity | Universal all-$n$ twisted-cycle $F_n \to D_n$ + Clifford-nilpotent $C_4^{\mathrm{nilp}}$ | Hand proof audit of Lemmas 1–5 + 375 $\mathbb{Q}(\sqrt{2})$ Bernstein evals + Descartes + 4D census (`20,736` matrices) | Replaced computer-assisted low-$n$ search with computer-free all-$n$ Sobolev + degree-4 Bernstein proof | `VERIFIED` `N2` (checked vs. Borcea–Streinu 2021 §7 & `incentre-lattices#7`) |
| **`AUDIT-014`** | `AUDIT-002` 2nd-moment sharpness wall | Higher-moment Stieltjes–Hankel $R_{H,2m}$, noise-annihilating $\Phi_{x_0,\tau}$, weighted $R_{W4}$ | `SymPy` zero-residual SOS + 300 fresh non-commuting $\mathbb{Q}(i)$ trials vs. Descartes + 41-mutant R5 suite | Broke past $\lceil R_{\mathrm{opt}}\rceil$ on Scan 23848 Mode A/B and fresh non-commuting $4\times 4$ matrices | `VERIFIED` `N2` (`Basic.lean` honestly tagged `uncompiled_source`) |
| **`AUDIT-017`** | 4D $C_4^{\mathrm{nilp}}$ $\to$ 8D spinor root match | Canonical Sylvester–Hadamard $F_8 \to E_8$ fold + $E_6/E_7/D_n^+$ obstructions | Full $8\times 8$ `SymPy` + direct combinatorial $E_8$ shell4/shell8 bijection + 32,640-pair / 293,760-coeff deg-8 $\mathbb{Z}[\sqrt{2}]$ Bernstein | Zero-subdivision global-$\mathbb{Z}^8$ non-overlap proof; caught `-J_8` reflection control (`det=-256`) | `VERIFIED` `N2` LANDMARK (open Draft PR `incentre-lattices#106`) |
| **`AUDIT-020R`** | Portal 9 open 24D Leech question | Irreducible Root-Graph Obstruction + exact $\Lambda_{16}$ & $\Lambda_{24}/\sqrt{2}$ Cayley unjamming | Full 138,240 BW16 pairs + 98,280-root Leech + `SymPy` + `10,000` random lattice vectors | Caught norm$^2=3$ odd-shell bug in `AUDIT-020`; proved integral-norm & tightened Gate (2) to $\|A\|_2 \le 1/8$ | `VERIFIED` `N2` LANDMARK (explicitly scoped to local global-$\mathbb{Z}^n$ arcs $[0, \tau_*]$) |

---

## 6. Math-Specific Cave-Shadow Anti-Patterns

Watch for these seven failure modes during any pure or computational math workflow:

1. **Epsilon-Rank Theater:** Deciding `eigval > 1e-12` or `np.linalg.matrix_rank` on a claim about exact rank, positivity, or zero-mode counts. *Fix:* Switch the TCB to exact `Fraction` / $\mathbb{Q}(i)$ / $\mathbb{Z}[\sqrt{2}]$ congruence or Descartes/Sturm inertia.
2. **Self-Certifying Oracle Circularity:** Checking a theorem with the same matrix-factorization helper used to construct the witness. *Fix:* Require a zero-shared-code second mathematical method (e.g., Faddeev–LeVerrier + Descartes against `PLDL*`).
3. **Silent `bool`/`float` Coercion in Python TCBs:** Accepting `True` as `1` or `1.5` as `3/2` in an exact verifier (`AUDIT-001`, `AUDIT-006`, `AUDIT-013`). *Fix:* Explicitly guard `if isinstance(x, bool) or not isinstance(x, (int, Fraction)): raise TypeError(...)`.
4. **Midpoint-Only Symbolic Checks:** Checking Hermitianity or symmetry at the center of a box while skipping symbolic verification of off-center entries (`AUDIT-015` caught `[[1+ix, 0], [0, 1]]` certifying `(2,0,0)`!). *Fix:* Validate symbolic symmetry/Hermitianity identically across all monomials.
5. **Rescaling Parity Slip:** Assuming a property (such as lattice evenness $\|w\|^2 \in 2\mathbb{Z}$) survives rescaling by $1/\sqrt{2}$ (`AUDIT-020`). *Fix:* Prove integrality/parity directly on the rescaled lattice and test random lattice combinations explicitly.
6. **Memory-Based Novelty Claims:** Declaring `N2` from an abstract or recollection without reading the exact lemmas of prior papers and sibling PRs. *Fix:* Cite the exact theorem/lemma number in the full text and state the sharp mathematical delta.
7. **Uncompiled Formalization Inflation:** Reporting a proof as "Lean-verified" when `lean` / `lake build` was never executed. *Fix:* Enforce the `uncompiled_source` tag until a recorded compiler log exists.

---

## 7. Practitioner Pre-Submission Checklist (Mathematics)

Before marking any mathematical discovery `VERIFIED` or promoting it to `N1`/`N2`, verify every box:

- [ ] **Exact statement & full hypothesis list:** Every implicit precondition (co-reachability, $P \succeq 0$, Hermitianity, positive orientation $\det > 0$, integral vs. even norm) is written explicitly in the theorem statement.
- [ ] **Boundary & edge-case coverage:** Zero-trace, zero-rank, $b = 0$, $b > n$, degenerate eigenvalues, and division-by-zero boundaries are checked both analytically and in code.
- [ ] **Zero-float TCB:** No `float`, `math.sqrt`, or `numpy` tolerance appears inside any `exact` decision path.
- [ ] **Zero-shared-code dual oracle:** A second, mathematically independent checker agrees 100% across all test cases and fresh out-of-sample randomized exact inputs.
- [ ] **R4 3-mode isolated parity:** Script contains `0` bare `assert`s and produces bit-identical canonical JSON under `-I -B`, `-I -O -B`, and `-I -B -W error`.
- [ ] **R5 must-fail & mutation suite:** Every hypothesis guard has a failing negative control, and mutating/deleting each guard is caught live.
- [ ] **Full-text prior-art delta (Gate 9):** Checked against the actual text of closest papers/PRs; `N0`/`N1`/`N2` label matches the proven delta.
- [ ] **Honest scope & standing tags:** Uncompiled Lean/Coq files tagged `uncompiled_source`; open PRs tagged `Draft PR`; local-vs-global limits stated upfront.

---

## 8. Experience the Complete Cycle Live in 3 Seconds

Run the zero-dependency executable demonstration of Chain 1 (`AUDIT-001` $\to$ `AUDIT-002` $\to$ `AUDIT-014`) right from the repository root:

```bash
python3 -I -O -B -W error examples/worked_resonance_cycle/run_demo.py
```

See [`examples/worked_resonance_cycle/README.md`](../examples/worked_resonance_cycle/README.md) for the stage-by-stage mathematical walkthrough and `--json` verification commands.
