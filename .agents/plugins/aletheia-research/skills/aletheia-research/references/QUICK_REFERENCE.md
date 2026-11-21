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

## 3. The 7 Cave-Shadow Anti-Patterns (Flagged by `aletheia diagnose`)

1. **Static-Map Trap:** Cartographer/Portal-Keeper parks after Round 1 instead of re-entering portals on probe anomalies.
2. **Premature Dismissal Bias:** String of `FALSIFIED`/`N0` reports with zero steelmanned/repaired versions tested.
3. **Language Smuggling:** Shared vocabulary ("sheaf", "duality", "emergence") claimed as unity with no executable map or defect.
4. **Substitution Shadow:** Testing a simplified synthetic proxy instead of the actual upstream equation or dataset.
5. **Glass Gate:** Validation checks built with bare `assert`s (stripped under `-O`), loose R3 parsing (`"007"`, `bool`, floats), or untested reject branches surviving R5 mutation.
6. **Local-Optimum Closure:** Treating a sharpness wall or counterexample as termination instead of elevating the obstruction into a theorem or spawning the next-order invariant.
7. **Provenance Inflation:** Calling a Draft PR "merged", `uncompiled_source` "machine-checked", or a local arc "global."

## 4. R1–R5 Gate Contracts & R4 Parity Command

- **R1 Default Reject:** Empty/blank/malformed inputs fail closed.
- **R2 Omission Monotonicity:** Deleting required evidence never flips `reject` to `accept`.
- **R3 Canonical Encoding & Strict Typing:** Reject loose spellings (`bool` for `int`, non-reduced fractions `"2/4"`, whitespace/newlines, floats in exact contracts).
- **R4 Optimizer & Warning Parity:** Identical exit code and canonical output under:
  ```bash
  python3 -I -B <script.py> && python3 -I -O -B <script.py> && python3 -I -B -W error <script.py>
  ```
- **R5 Refusal-Site Isolation:** Every guard has a must-fail fixture; single-site mutation testing (`aletheia mutate`) targets 100% kill rate.

## 5. Key Repository Paths

- Role prompts: [prompts/coordinator.md](../../../../../../prompts/coordinator.md), [prompts/portal-keeper.md](../../../../../../prompts/portal-keeper.md), [prompts/domain-probe.md](../../../../../../prompts/domain-probe.md), [prompts/synthesizer.md](../../../../../../prompts/synthesizer.md), [prompts/verifier-tomography.md](../../../../../../prompts/verifier-tomography.md), [prompts/peer-weaver.md](../../../../../../prompts/peer-weaver.md)
- Domain packs: [domains/README.md](../../../../../../domains/README.md)
- Platform adapters: [adapters/README.md](../../../../../../adapters/README.md)
- Worked 3-second demo: [examples/worked_resonance_cycle/README.md](../../../../../../examples/worked_resonance_cycle/README.md)
