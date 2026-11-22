# Aletheia Research — Quick Reference

Compact cheat-sheet for agents running **The Aletheia Method** (`https://github.com/Foundation-0/aletheia`). For complete formal definitions see [spec/LAWS_AND_GATES.md](../../../../../../spec/LAWS_AND_GATES.md) and [THEORY.md](../../../../../../THEORY.md).

## 1. Oracle-Class Decision Matrix

| Problem Class | Oracle Class | Mandatory Standard | Disallowed Shortcuts |
|---|---|---|---|
| Algebraic/combinatorial bounds, inertia, SOS/Farkas duals, symbolic reductions, formal proofs | **`exact`** | Pure `int` / `Fraction` / $\mathbb{Q}(i)$ / $\mathbb{Z}[\sqrt{2}]$ / `isqrt` / exact `SymPy` / Lean/Coq + zero-shared-code cross-check + R5 must-fail controls. | Float tolerances (`eigvalsh > 1e-12`), trusting black-box `"optimal"` flags without dual certificate verification, proxy substitution. |
| Dynamical systems, empirical datasets, cohorts, Monte Carlo, time-series detectors | **`sampled`** | Logged RNG seeds, held-out / sample-disjoint splits, matched adversarial nulls (IAAFT, twin uncoupled systems, shuffled/decoy controls), unseen-seed replay, pre-adaptation latch reporting. | Tuning thresholds on the test seed, claiming universal proof from finite sweeps, treating post-fit residual drop as misspecification closure. |
| Parity against live external simulator or reference implementation | **`anchor`** | Execute untouched upstream code/CLI live and verify quantitative agreement. | Copying constants manually without executing the live upstream model. |

## 2. Novelty & Verdict Tags

- **Verdicts (logged permanently in `verification/AUDIT_LOG.md`):** `VERIFIED` | `PARTIAL/FRAGILE` | `FALSIFIED`
- **Novelty Bar (default `N0` until full-text prior-art audit):**
  - `N0`: Known result, restatement, or repackaging of known parts.
  - `N1`: Hardened repair, sharpened boundary/counterexample, or concrete empirical falsification.
  - `N2`: Genuinely new verified theorem, exact certificate, constructive obstruction, or cross-domain operator unification absent from checked full-text prior art.

## 3. The 12 Cave-Shadow Anti-Patterns (Flagged by `aletheia diagnose`)

1. **Static-Map Trap (`CS-01`):** Cartographer/Portal-Keeper parks after Round 1 instead of re-entering portals on probe anomalies.
2. **Premature Dismissal Bias (`CS-02`):** String of `FALSIFIED`/`N0` reports with zero steelmanned/repaired versions tested.
3. **Language Smuggling (`CS-03`):** Shared vocabulary ("sheaf", "duality", "emergence") claimed as unity with no executable map or defect.
4. **Substitution Shadow (`CS-04`):** Testing a simplified synthetic proxy instead of the actual upstream equation or dataset.
5. **Glass Gate (`CS-05`):** Validation checks built with bare `assert`s (stripped under `-O`), loose R3 parsing (`"007"`, `bool`, floats), or untested reject branches surviving R5 mutation.
6. **Local-Optimum Closure (`CS-06`):** Treating a sharpness wall or counterexample as termination instead of elevating the obstruction into a theorem or spawning the next-order invariant.
7. **Provenance Inflation (`CS-07`):** Calling a Draft PR "merged", `uncompiled_source` "machine-checked", or a local arc "global."
8. **Compute-Leakage Simpson's Paradox (`CS-08`):** Comparing arms by round count without a fixed compute/token survival cap, letting slow format-breaking CoT escapes invert the true fixed-budget winner (`AUDIT-023` `N2`).
9. **Finite-Sample / Support-Truncation Mirage (`CS-09`):** Claiming asymptotic laws from finite-$M$ / top-$p$ truncated trajectories without tail-mass extinction checks (`AUDIT-032` `N2`).
10. **Sparse-Collision Denominator Collapse (`CS-10`):** Averaging sparse updates or filtered evals by collision count $c_j$ (`scatter_reduce_("mean", include_self=False)`) instead of global denominator $W$ (`AUDIT-039` `N2`, `AUDIT-037`).
11. **Unit-Gauge / Radix Fragility (`CS-11`):** Unscaled raw-unit regularization or base-10/float64 math grading without coordinate-free gauge/radix invariance (`AUDIT-039` `N2`, `AUDIT-036`).
12. **Trust-Boundary Shadow (`CS-12`):** Hidden local refusal wrappers escaping R5 mutation, `$` vs `\Z` trailing-newline digest regexes, loose `json.loads` accepting duplicate keys / `NaN`, unbound escape hatches, or writable ancestor directories (`AUDIT-061R`–`065`, `v1.4`).

## 4. R1–R5 Gate Contracts & R4 Parity Command

- **R1 Default Reject:** Empty/blank/malformed inputs fail closed.
- **R2 Omission Monotonicity:** Deleting required evidence never flips `reject` to `accept`.
- **R3 Canonical Encoding & Strict Typing:** Reject loose spellings (`bool` for `int`, non-reduced fractions `"2/4"`, whitespace/newlines, floats in exact contracts).
- **R4 Optimizer & Warning Parity:** Identical exit code and canonical output under:
  ```bash
  python3 -I -B <script.py> && python3 -I -O -B <script.py> && python3 -I -B -W error <script.py>
  ```
- **R5 Refusal-Site Isolation:** Every guard has a must-fail fixture; single-site mutation testing (`aletheia mutate`) targets 100% kill rate.

## 5. 8-Glyph Exact Operator Calculus (v1.3 — `aletheia calculus`)

Reported audit across `227,540` Lean 4 files (`0` collisions, all Unicode `Sm`; not reproduced here), executable in exact $\mathbb{Q}/\mathbb{Z}$ via `python3 -m aletheia calculus [--list | --eval EXPR | --self-test] [--json]`:

| Glyph | ASCII | Operator | Meaning |
|---|---|---|---|
| `⧄` (`U+29C4`) | `\|/\|` | Schur Pushforward | $M_{AA} - M_{AB}M_{BB}^+M_{BA}$ (`SF-01`) |
| `⧅` (`U+29C5`) | `\|\\\|` | Dark-Mode Shadow | $(\ker M_{BB}, M_{AB}|_{\ker}, \dim_{\mathrm{dark}}, r_{\mathrm{cross}})$ |
| `⦷` (`U+29B7`) | `(||)` | Holonomy Unmasking | $(L^\chi \mathbin{⧄} I) - (L \mathbin{⧄} I)$ |
| `⟠` (`U+27E0`) | `<=>` | Observer Equalizer | Reynolds / Mellin regulator-net invariant (`SF-07`) |
| `⧇` (`U+29C7`) | `[o]` | Cohom. Obstruction | $\|\omega_{\mathrm{harm}}\|_w^2 / \|\omega\|_w^2 \in [0,1]\cap\mathbb{Q}$ (`SF-05`) |
| `⦺` (`U+29BA`) | `(+-0)` | Krein Inertia | Exact $(n_+, n_0, n_-)$ (and `⦺_+`, `⦺_0`, `⦺_-`) |
| `⩩` (`U+2A69`) | `=#=` | Exact Null-Equiv | $X - Y = 0$ identically (forbids floats; `CS-11`) |
| `⫩` (`U+2AE9`) | `_|T` | R5 Refusal Gate | $T(x) \land \forall m \in M(x), \neg T(m)$ (`SF-04`) |

## 6. Key Repository Paths

- Role prompts: [prompts/coordinator.md](../../../../../../prompts/coordinator.md), [prompts/portal-keeper.md](../../../../../../prompts/portal-keeper.md), [prompts/domain-probe.md](../../../../../../prompts/domain-probe.md), [prompts/synthesizer.md](../../../../../../prompts/synthesizer.md), [prompts/verifier-tomography.md](../../../../../../prompts/verifier-tomography.md), [prompts/peer-weaver.md](../../../../../../prompts/peer-weaver.md)
- Domain packs: [domains/README.md](../../../../../../domains/README.md)
- Platform adapters: [adapters/README.md](../../../../../../adapters/README.md)
- Worked 3-second demo: [examples/worked_resonance_cycle/README.md](../../../../../../examples/worked_resonance_cycle/README.md)
