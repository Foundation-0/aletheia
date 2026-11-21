# Worked Resonance Cycle: Live 3-Second Aletheia Demo

> **Parent framework:** [The Aletheia Method](../../README.md) · [First-Principles Theory](../../THEORY.md) · [Canonical Laws & Gates](../../spec/LAWS_AND_GATES.md) · [Cave Expedition Case Study](../../evidence/cave-expedition-case-study.md) · [Mathematics Domain Pack](../../domains/mathematics-and-formal-proof.md)

This directory contains a **100% self-contained, zero-dependency, zero-float executable demonstration** of **The Aletheia Method** running our real Cave Expedition **Chain 1** breakthrough (`AUDIT-001` $\to$ `AUDIT-002` $\to$ `AUDIT-014`) live in miniature.

Anyone who clones `Foundation-0/aletheia` can run **one command** and experience — in under 1 second, with exact rational arithmetic over $\mathbb{Q}(i)$ — why **Portal-Driven Resonance & Adversarial Tomography** escapes Plato's Cave where static Pass-1 critique stalls at `N0`.

---

## 1. Quickstart (One Command)

Run from the repository root:

```bash
python3 -I -O -B -W error examples/worked_resonance_cycle/run_demo.py
```

For deterministic, machine-verifiable canonical JSON output:

```bash
python3 -I -O -B -W error examples/worked_resonance_cycle/run_demo.py --json
```

Verify **R4 4-mode isolated parity** (all four Python execution modes produce bit-identical output with zero bare `assert`s and zero warnings):

```bash
for flags in "-I -B" "-I -O -B" "-I -B -W error" "-I -O -B -W error"; do
  python3 $flags examples/worked_resonance_cycle/run_demo.py --json | sha256sum
done
```

---

## 2. What the 5 Live Stages Prove

[`run_demo.py`](./run_demo.py) executes the complete Aletheia Resonance Cycle end to end using only Python 3's standard library (`fractions.Fraction`, `int`, and exact Gaussian rationals $\mathbb{Q}(i)$ — **zero floats**, **zero `assert`s**):

| Stage | Aletheia Phase | Exact Mathematical Demonstration in `run_demo.py` | Key Result |
|---|---|---|---|
| **Stage 1** | **Pass-1 Prototype Bug** (`AUDIT-001` `FALSIFIED`) | Replays the real Pass-1 bug from `pair_06_block_00.py`: omitting the $P = H - Q \succeq 0$ check lets $H = \operatorname{diag}(1,0)$, $Q = \operatorname{diag}(10,0)$ ($b=1, c=2$) **forge $\operatorname{rank}(P) \ge 117$ on a $2\times 2$ matrix** (and $\ge 140$ for $Q = \operatorname{diag}(11,0)$). | Static critique stops here (`N0`). Aletheia logs `FALSIFIED` honestly and invokes **Law 2**. |
| **Stage 2** | **Steelman Projection** (`AUDIT-002` `VERIFIED` `N2`) | Repairs $P \succeq 0$ and steelmans Lemma 3.2 on $W \oplus W^\perp$ ($W = \operatorname{range}(Q_+)$), deriving the guarded, scale-invariant two-regime envelope $R_{\mathrm{opt}}(u,t,S,b)$. Verifies the exact 6-term nonnegative slack identity, exact scale invariance ($\lambda = 17/5$), both boundary guards (`0/0` at $u=0$, negative else-branch), and exact lift on Scan 23848 Mode B ($\rho=0$: `R_opt = 1` vs. fixed $c=2 \approx 0.876$; $\rho=3/4$: fixed $c=2$ collapses to `0`). | Turns a broken $2\times 2$ script into a strictly stronger scale-invariant theorem. |
| **Stage 3** | **Observer Tomography & Sharpness Wall** ($\mathcal{G}_{\mathrm{obs}}$, `AUDIT-002`) | Runs a **zero-shared-code** exact Hermitian inertia oracle (**Faddeev–LeVerrier** characteristic polynomial + internal **Cayley–Hamilton** check + exact **Descartes' rule of signs**) on a dense, strictly complex, strictly non-commuting indefinite $4\times 4$ matrix $H = P + Q \in \mathbb{Q}(i)^{4\times 4}$ (spectrum $\{16, 4, 4, -1\}$, $\operatorname{rank}(P)=2$, $n_+(H_\perp)=2$, $n_+(Q)=b=1$). On this matrix, fixed $c=2$ collapses to `0` and $R_{\mathrm{opt}} = \frac{240}{289} \approx 0.8304 \le 1$. Then constructs an **exact rational rank-1 decoy** $(P_{\mathrm{decoy}}, Q_{\mathrm{decoy}}) = (\operatorname{diag}(0, \tfrac{392}{25}), \operatorname{diag}(15, -\tfrac{192}{25}))$ matching $(u, t, S, b) = (\tfrac{392}{25}, \tfrac{183}{25}, 289, 1)$ **identically** (an $(8,15,17)$ Pythagorean triple!). | Proves mathematically that **no** 2nd-moment theorem can surpass $\max(1, \lceil R_{\mathrm{opt}} \rceil) = 1$ here — turning the wall into a branch trigger! |
| **Stage 4** | **Resonance Breakthrough** (`AUDIT-014` `VERIFIED` `N2`) | Applies **Theorem A2 (4th-Moment Stieltjes–Hankel Bound $R_{H4}$)** using exact moments $(S_1, S_2, S_3, S_4)$ and nonnegative witness $(s^*, p^*) \in \mathbb{Q}_{>0}^2$ ($\phi_{s,p}(\lambda) = 1 - (1 - s\lambda + p\lambda^2)^2 \le \mathbf{1}_{(0,\infty)}(\lambda)$ on all of $\mathbb{R}$, including $\lambda = -1 < 0$!). On the **exact same** non-commuting indefinite matrix $H$, $R_{H4}(H, 1) > 1$ (breaking straight through the quadratic wall to certify **$\operatorname{rank}(P) \ge n_+(H_\perp) \ge 2$**), while correctly returning exact `1` on the rank-1 decoy! | Higher-moment resonance breaks the proven 2nd-moment wall without losing exactness. |
| **Stage 5** | **R5 Must-Fail Controls & Live Mutation Check** (Gate 7) | Runs **7 must-fail controls** (missing $P\succeq 0$, non-Hermitian $H$, negative Hankel weight $a_2 < 0$, Python `bool` leak, `float` leak, negative $b$, dimension mismatch) AND **3 live refusal-site mutations** proving that deleting the $P\succeq 0$ guard, Hermitian guard, or $a_k \ge 0$ guard immediately lets an explicit forgery slip through (including forging $\operatorname{rank} \ge 2$ on a rank-1 indefinite matrix $\operatorname{diag}(1, -10)$ via $a = (1, -11/100)$) — and that the intact verifier kills **3/3 mutants**. | Proves the verification gate is real steel, not decorative "glass gate" theater. |

---

## 3. Why Every Detail Is Exact (Zero Floats, Zero Shortcuts)

- **Complex Non-Commuting Indefinite Benchmark Matrix:** Built from $H_0 = \operatorname{diag}(16, 4, 4, -1)$, $v = (\tfrac{12}{5}, \tfrac{8}{5}i, 0, 0)^\top$ ($v^* \operatorname{diag}(16, 4, 4)^{-1} v = \tfrac{9}{25} + \tfrac{16}{25} = 1$), $Q_0 = v v^* - e_4 e_4^*$, $P_0 = H_0 - Q_0 \succeq 0$, then conjugated by an exact $\mathbb{Q}(i)$ unitary $U = U_{12} U_{34} U_{23}$ built from exact $(3,4,5)$ Pythagorean unitary blocks so $H, P, Q$ are dense, complex, indefinite, and strictly non-commuting ($[P, Q] \ne 0$).
- **Exact Pythagorean Rank-1 Decoy:** Because $S_1 = 23$ and $S_2 = 289 = 17^2$ satisfy $2 S_2 - S_1^2 = 49 = 7^2$, the rank-1 decoy eigenvalues $h_{\mathrm{hi}} = 15, h_{\mathrm{lo}} = 8$ are **exact integers** — proving the quadratic sharpness wall with zero square roots and zero floating-point error.
- **Zero-Shared-Code Independent Oracle:** The Faddeev–LeVerrier + Cayley–Hamilton + Descartes inertia checker operates purely on raw `(Fraction, Fraction)` tuples with its own standalone matrix algebra, sharing zero helpers with the certificate producer.
