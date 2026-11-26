# Track S119: Exact $\mathbb{Q}(\sqrt{5})$ Spinor-Barrington $2I \subset SU(2)$ DAG-to-`HoloSphere` Compiler ($O(S)$ Relational `V_ring` Collapse of $4^d$ Formula Blowup)

**Track:** `S119` (CPU-only exact algebra, compilation, and IEEE-754 FP32 verification; `0` GPU touch, `0` external dependencies)  
**Target Directory:** `track-s119-barrington-su2-dag-compiler/`  
**Canonical Certificate `payload_sha256`:** `009dd43173448ca38adeea9240365f3e3532d98eb622d50a56ee2ae35f097f97`

---

## Executive Summary

1. **Exact $\mathbb{Q}(\sqrt{5})$ Construction of $2I \cong SL(2, 5) \subset SU(2)$ (`0` Floats):** All `120` unit quaternions of the binary icosahedral group $2I$ are constructed and verified in exact $\mathbb{Q}(\sqrt{5})$ arithmetic (`120 × 120 = 14,400` closed products, exact unit norm $N(q)=1$, inverse closure, and exact projective quotient $2I / \{\pm I\} \cong A_5$ of size `60`). Every element with $q_0 \ge 0$ (`75/75`: `45` strictly acute with $q_0 > 0$ and $\|\omega\| \le \tan(\pi/5) \approx 0.726543 < 0.8$; `30` equatorial with $q_0 = 0$ and $\|\omega\| = 1$) roundtrips identically through the single-step `CayleySU2` map $\omega(q) = (q_1, q_2, q_3)/(1 + q_0)$, leaving $-I$ as the unique antipodal pole.
2. **Exact $SL(2, 5) = 2I$ Spinor-Barrington Commutator Sign Dichotomy Theorem:**
   - **Strict $\mathbb{Z}_2$ Spinor Obstruction on Order-5 Classes ($\tilde{\sigma}_0^5 = +I$):** Across **both** order-5 conjugacy classes ($q_0 = -\frac{1+\sqrt{5}}{4}$ and $q_0 = +\frac{\sqrt{5}-1}{4}$), **zero** conjugate pairs satisfy $[\tilde{\alpha}, \tilde{\beta}] = +\tilde{\sigma}_0$, whereas **`10` pairs per class** satisfy $[\tilde{\alpha}, \tilde{\beta}] = -\tilde{\sigma}_0 \in \mathcal{C}_{10}$. Naive order-5 spinor lifts suffer an unavoidable $\mathbb{Z}_2$ Maslov/spinor sign flip on every `AND` gate.
   - **Sign-Free Exact Closure on Acute Order-10 Class $\mathcal{C}_{10}^+$ ($\tilde{\tau}_0^5 = -I$, $q_0 = +\frac{1+\sqrt{5}}{4}$):** Encoding `FALSE = +I` and `TRUE = +\tilde{\tau}_0` in the acute order-10 lift of a 5-cycle yields **`10` exact positive conjugate pairs (`0` negative hits)** satisfying $[\tilde{\alpha}, \tilde{\beta}] = +\tilde{\tau}_0$, closing **both `AND` and `NOT`** with **zero sign canonicalization** and **zero `-I` leakage**. Moreover, our optimal canonical witness $(\tilde{\tau}_0, g_\alpha, g_\beta)$ keeps **every** input, output, conjugator, and intermediate partial product strictly inside the acute `CayleySU2` ball $\|\omega\| \le \tan(\pi/5) \approx 0.726543 < 0.8 = t_{\max}$ ($q_0 \ge +\frac{\sqrt{5}-1}{4} \approx +0.309017$).
3. **Constructive $O(S)$ Relational `V_ring` DAG Collapse:** Compiling fan-in-2 Boolean DAGs to `HoloSphere`'s `CayleySU2` + `16 B` `V_ring` register slots (`7` Hamilton products per `AND`, `1` per `NOT`) collapses classic Barrington's $4^d$ unfolded formula length to strictly $O(S)$ gates (`21.33×` on `shared_diamond_d6`, **`8,388,608.00×`** = $2^{23}\times$ on `shared_diamond_d16` where $4^{16} = 4{,}294{,}967{,}296$, and **`38,347,922.29×`** on `lyapunov_self_and_d16`), verified `100.00%` exact over **all $2^n$ assignments** across all `7` benchmark DAGs (`354/354` total truth-table evaluations, including all `256/256` inputs of a 4-bit ripple-carry adder).
4. **Honest Law-5 IEEE-754 FP32 Drift Taxonomy (4 Regimes):**
   - **Unnormalized raw FP32:** Explodes radially as $4^d$ because $\|A B A^\dagger B^\dagger\| = \|A\|^2\|B\|^2$, hitting `7.62e+29` / `OVERFLOW` at `d = 16` (`0/16` decoded).
   - **`S^3` unit-norm & `CayleySU2`-reprojected FP32:** Eliminate the radial $4^d$ blowup completely, holding `shared_diamond_d16` max quaternion L2 error to **`2.70e-7`** (`s3_norm`) and **`4.05e-8`** (`cayley_reproj`), well below `1e-5` (`16/16` exact).
   - **Adversarial $\phi^d$ Tangential Lyapunov Mode:** At $q = \tilde{\tau}_0$, the $\mathfrak{su}(2)$ tangent Jacobian of $q \mapsto [g_\alpha q g_\alpha^\dagger, g_\beta q g_\beta^\dagger]$ has exact spectral radius $\rho = \phi = \frac{1+\sqrt{5}}{2} \approx 1.618034$, causing `s3_norm` to reach `1.52e-4` at `d = 16` on `lyapunov_self_and_d16` (still `4,074×` below the separation $\|I - \tilde{\tau}_0\|_2 = \phi^{-1} \approx 0.618034$).
   - **Branchless Binary `V_ring` Refresh ($q_0 > 0.9045085$):** Clamps FP32 error permanently to **`1.16e-8`** (`<= 1` ULP) at arbitrary depth.

---

## 1. Exact $\mathbb{Q}(\sqrt{5})$ Construction of $2I \cong SL(2, 5) \subset SU(2)$ & `CayleySU2` Geometry

All algebraic constructions execute in exact $\mathbb{Q}(\sqrt{5}) = \{a + b\sqrt{5} : a, b \in \mathbb{Q}\}$ using canonical integer tuples `(na, nb, den)` with `den > 0`, $\gcd(|n_a|, |n_b|, d) = 1$, and exact `(Fraction, Fraction)` projections (zero floating-point operations anywhere in the field, quaternion, or group proofs). Exact signs are decided via integer comparison of $n_a^2$ against $5 n_b^2$.

The `120` unit quaternions of $2I \subset SU(2)$ consist of:
- `8` axis units: $(\pm 1, 0, 0, 0)$ and permutations,
- `16` half-integer Hurwitz units: $(\pm\frac{1}{2}, \pm\frac{1}{2}, \pm\frac{1}{2}, \pm\frac{1}{2})$,
- `96` golden-ratio units: all even permutations of $\left(0,\, \pm\frac{1}{2},\, \pm\frac{\sqrt{5}-1}{4},\, \pm\frac{1+\sqrt{5}}{4}\right)$.

| Verification Property | Exact $\mathbb{Q}(\sqrt{5})$ Result |
|---|---|
| Group order $\|2I\|$ | `120` |
| Exact unit norm $N(q) = 1$ | `120 / 120` (`true`) |
| Exact inverse closure ($q^\dagger \in 2I$) | `120 / 120` (`true`) |
| Exact multiplicative closure ($p \cdot q \in 2I$) | `14,400 / 14,400` (`true`) |
| Projective quotient $\|2I / \{\pm I\}\| \cong \|A_5\|$ | `60` |
| `CayleySU2` closed hemisphere $q_0 \ge 0$ (`45` acute + `30` equatorial) | `75 / 75` exact roundtrip, `75 / 75` with $\|\omega\|^2 \le 1$ |
| Max acute `CayleySU2` radius ($q_0 > 0$, `45` elements) | $\|\omega\|^2 = 5 - 2\sqrt{5} \implies \|\omega\| = \tan(\pi/5) \approx 0.726542528 < 0.8$ |
| `CayleySU2` obtuse non-pole ($-1 < q_0 < 0$) | `44 / 44` exact roundtrip ($\|\omega\|^2 > 1$) |
| `CayleySU2` antipodal poles ($q_0 = -1$) | `1` (unique element $-I$) |

---

## 2. Exact $SL(2, 5) = 2I$ Spinor-Barrington Commutator Sign Dichotomy Theorem

### 2.1 Universal Two-Line $SU(2)$ Commutator Trace Identity

For any two unit quaternions $a, b \in SU(2)$,
$$[a, b] = a b a^\dagger b^\dagger = (a b)(b a)^\dagger, \qquad a b - b a = (0,\; 2\,\vec{a} \times \vec{b}).$$
Taking squared Euclidean norms on $\mathbb{R}^4$:
$$\|a b - b a\|^2 = \|a b\|^2 + \|b a\|^2 - 2\operatorname{Re}((a b)(b a)^\dagger) = 2 - 2\operatorname{Re}([a, b]) = 4\,\|\vec{a} \times \vec{b}\|^2$$
$$\Longrightarrow \quad \operatorname{Re}([a, b]) = 1 - 2\,\|\vec{a} \times \vec{b}\|^2.$$

Verified exhaustively in exact $\mathbb{Q}(\sqrt{5})$ across all `120 × 120 = 14,400` pairs of $2I$: **`0` mismatches**.

Because $\vec{(-a)} = -\vec{a}$ leaves $\|\vec{a} \times \vec{b}\|^2$ invariant, negating either input leaves $[a, b]$ unchanged. For any conjugacy class $\mathcal{C} \subset 2I$ with scalar part $q_0 = \pm\cos\theta$:
- For the 5-cycle lifts with $|q_0| = \frac{1+\sqrt{5}}{4} = \cos(\pi/5)$ ($\sin^2(\pi/5) = \frac{5-\sqrt{5}}{8}$), $2\sin^4(\pi/5) = \frac{15 - 5\sqrt{5}}{16} \approx 0.238732$, forcing $\operatorname{Re}([a, b]) \ge \frac{1 + 5\sqrt{5}}{16} \approx +0.761268 > 0$ for **every** pair $(a, b)$. Therefore $[a, b]$ can **never** hit $q_0 = -\frac{1+\sqrt{5}}{4}$ (order 5); at the unique icosahedral axis angle $\sin^2\psi = \frac{4}{5}$, it lands exclusively at $q_0 = +\frac{1+\sqrt{5}}{4}$ (order 10, $\mathcal{C}_{10}^+$).
- For the 5-cycle lifts with $|q_0| = \frac{\sqrt{5}-1}{4} = \cos(2\pi/5)$ ($\sin^2(2\pi/5) = \frac{5+\sqrt{5}}{8}$), at $\sin^2\psi = \frac{4}{5}$ we obtain $\operatorname{Re}([a, b]) = 1 - \frac{4}{5}\cdot\frac{15+5\sqrt{5}}{16} = \frac{1-\sqrt{5}}{4} = -\frac{\phi^{-1}}{2}$ (order 10, $\mathcal{C}_{10}^-$), again forbidding the order-5 class $q_0 = +\frac{\phi^{-1}}{2}$.
- For the 3-cycle lifts with $|q_0| = \frac{1}{2}$ ($\sin^2(\pi/3) = \frac{3}{4}$), $2\sin^4(\pi/3) = \frac{9}{8}$, giving $\operatorname{Re}([a, b]) \ge -\frac{1}{8} > -\frac{1}{2}$ and forbidding order 3 while closing order 6.

### 2.2 Complete Exhaustive Classification Across All 9 Conjugacy Classes of $2I$

| Order | $\|\mathcal{C}\|$ | Exact $q_0$ | $q_0$ (float) | $N^+(\mathcal{C})$ ($[a,b]=+c_0$) | $N^-(\mathcal{C})$ ($[a,b]=-c_0$) | Commutator Orders | Spinor Verdict |
|---:|---:|---|---:|---:|---:|---|---|
| `1` | `1` | `1` | `+1.000000` | `1` | `0` | `{1}` | Trivial `+I` |
| `2` | `1` | `-1` | `-1.000000` | `0` | `1` | `{1}` | Central `-I` obstruction |
| `3` | `20` | `-1/2` | `-0.500000` | `0` | `6` | `{1, 4, 6}` | **$\mathbb{Z}_2$ obstruction** |
| `4` | `30` | `0` | `+0.000000` | `0` | `0` | `{1, 2, 3, 5}` | Involution quotient ($A_5$ order 2) |
| `5` | `12` | `(-1 - sqrt5)/4` | `-0.809017` | **`0`** | **`10`** | `{1, 10}` | **$\mathbb{Z}_2$ obstruction** ($\tilde{\sigma}_0^5 = +I$) |
| `5` | `12` | `(-1 + sqrt5)/4` | `+0.309017` | **`0`** | **`10`** | `{1, 10}` | **$\mathbb{Z}_2$ obstruction** ($\tilde{\sigma}_0^5 = +I$) |
| `6` | `20` | `+1/2` | `+0.500000` | `6` | `0` | `{1, 4, 6}` | Sign-free positive (3-cycle lift) |
| `10` | `12` | `(1 - sqrt5)/4` | `-0.309017` | `10` | `0` | `{1, 10}` | Sign-free positive (obtuse, $\|\omega\| > 1$) |
| **`10`** | **`12`** | **`(1 + sqrt5)/4`** | **`+0.809017`** | **`10`** | **`0`** | **`{1, 10}`** | **Optimal acute sign-free lift $\mathcal{C}_{10}^+$** |

**Resolution of the Question in the Specification:** Lifting a 5-cycle in $A_5$ to an **order-5** element $\tilde{\sigma}_0 \in 2I$ ($\tilde{\sigma}_0^5 = +I$) ALWAYS incurs an exact $\mathbb{Z}_2$ spinor obstruction ($[\tilde{\alpha}, \tilde{\beta}] = -\tilde{\sigma}_0$, `0` positive / `10` negative pairs in both order-5 classes), which would require sign canonicalization `q -> sgn(q0) q` on every `AND` gate. Switching to the **acute order-10 lift** $\tilde{\tau}_0 \in \mathcal{C}_{10}^+$ ($q_0 = \frac{1+\sqrt{5}}{4} = \cos(\pi/5)$, $\tilde{\tau}_0^5 = -I$, $\tilde{\tau}_0^{10} = +I$, still projecting to a 5-cycle in $A_5$) **eliminates the sign obstruction completely**: BOTH `AND` and `NOT` close identically on $\{+I, +\tilde{\tau}_0\}$ with **zero sign canonicalization** and **zero `-I` leakage**.

### 2.3 Canonical Acute Witness & Strict Interior-Ball Invariant

Using canonical generator $\tilde{\tau}_0 \in \mathcal{C}_{10}^+$ and optimal acute conjugators $g_\alpha, g_\beta \in 2I$ (maximizing $\min(q_0(g_\alpha), q_0(g_\beta)) = \frac{1}{2}$ across all `10` exact positive pairs):

- $\tilde{\tau}_0 = \left(\frac{1+\sqrt{5}}{4},\; \frac{\sqrt{5}-1}{4},\; \frac{1}{2},\; 0\right)$ — exact order `10` ($\tilde{\tau}_0^5 = -I$), $\|\omega(\tilde{\tau}_0)\| = \tan(\pi/10) \approx 0.324920$.
- $g_\alpha = \left(\frac{1+\sqrt{5}}{4},\; \frac{1-\sqrt{5}}{4},\; \frac{1}{2},\; 0\right)$ — exact order `10`, $\|\omega(g_\alpha)\| = \tan(\pi/10) \approx 0.324920$.
- $g_\beta = \left(\frac{1}{2},\; -\frac{1}{2},\; \frac{1}{2},\; \frac{1}{2}\right)$ — exact order `6`, $\|\omega(g_\beta)\| = \frac{1}{\sqrt{3}} \approx 0.577350$.
- Gate semantics on $\Delta U \in \{+I, +\tilde{\tau}_0\}$:
  - **`NOT(a)` (`1` Hamilton product):** $\Delta U_{\neg a} = \tilde{\tau}_0 \cdot \Delta U_a^\dagger$ maps $+I \mapsto +\tilde{\tau}_0$ and $+\tilde{\tau}_0 \mapsto +I$.
  - **`AND(a, b)` (`7` factored Hamilton products + `2` sign-flip conjugations):** $A = (g_\alpha \Delta U_a) g_\alpha^\dagger$, $B = (g_\beta \Delta U_b) g_\beta^\dagger$, $\Delta U_{a \wedge b} = ((A B) A^\dagger) B^\dagger$ maps $(1,1) \mapsto +\tilde{\tau}_0$ and $(0,0), (0,1), (1,0) \mapsto +I$.
- **Strict Acute Interior-Ball Invariant:** Across all `4` `AND` truth inputs and all `7` intermediate partial products (`g_a U_a`, `A`, `g_b U_b`, `B`, `A B`, `A B A^\dagger`, `out`) plus both `NOT` inputs, the minimum scalar part is **$q_0 = \frac{\sqrt{5}-1}{4} \approx +0.309017 > 0$** and the maximum `CayleySU2` radius is **$\|\omega\| = \tan(\pi/5) \approx 0.726543 < 0.8 = t_{\max}$** (never approaching the Cayley equator or antipodal pole).

---

## 3. Constructive $O(S)$ Relational `V_ring` DAG Compiler & Compression vs $4^d$

Classic Barrington (1989) flattens a shared Boolean DAG of AND-depth $d_{\text{and}}$ into an unshared branching program obeying the exact recurrence $L(\text{INPUT}) = 1$, $L(\text{NOT}(a)) = L(a)$, $L(\text{AND}(a, b)) = 2 L(a) + 2 L(b)$ (yielding $4^{d_{\text{and}}}$ for balanced or diamond-shared DAGs).

Our compiler `compile_dag_to_holosphere_vring()` emits a straight-line `HoloSphere` program over `16 B` (`4 × float32`) Relational `V_ring` slots (`1` slot per DAG wire; static generators materialized via single-step bounded-ball `CayleySU2` vectors $\omega \in B^3(0.578)$), requiring only `7` Hamilton products per `AND` gate and `1` per `NOT` gate.

| Benchmark DAG | Inputs $n$ | Out | $d_{\text{and}}$ | `AND` / `NOT` | `V_ring` Slots (`Bytes`) | `V_ring` Quat Muls | Classic Barrington Exact Len | Compression Ratio | Exact $\mathbb{Q}(\sqrt{5})$ Match ($2^n$) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `xor_chain_4` | `4` | `1` | `6` | `9 / 12` | `25` (`400 B`) | `75` | `1,096` | `14.61×` | `16 / 16` (`100%`) |
| `ripple_carry_adder_4bit` | `8` | `5` | `8` | `24 / 37` | `69` (`1,104 B`) | `205` | `6,296` | `30.71×` | `256 / 256` (`100%`) |
| `shared_diamond_d6` | `4` | `1` | `6` | `24 / 24` | `52` (`832 B`) | `192` | `4,096` ($4^6$) | `21.33×` | `16 / 16` (`100%`) |
| `shared_diamond_d16` | `4` | `1` | `16` | `64 / 64` | `132` (`2,112 B`) | `512` | `4,294,967,296` ($4^{16}$) | **`8,388,608.00×`** | `16 / 16` (`100%`) |
| `three_sat_4var` | `4` | `1` | `5` | `14 / 34` | `52` (`832 B`) | `132` | `340` | `2.58×` | `16 / 16` (`100%`) |
| `majority_5` | `5` | `1` | `6` | `12 / 18` | `35` (`560 B`) | `102` | `388` | `3.80×` | `32 / 32` (`100%`) |
| `lyapunov_self_and_d16` | `1` | `1` | `16` | `16 / 0` | `17` (`272 B`) | `112` | `4,294,967,296` ($4^{16}$) | **`38,347,922.29×`** | `2 / 2` (`100%`) |

All `7` circuits are independently cross-checked against mathematical ground truth (exact 4-bit parity, exact `(a + b) mod 32` across all `256` pairs, exact 5-clause 3-SAT with `8` SAT / `8` UNSAT assignments, exact 5-input majority with `16/32` ones, and non-degenerate 4-wire diamond outputs with `4/16` ones on wire `0`).

---

## 4. Strict IEEE-754 FP32 `CayleySU2` Drift Audit Across 4 Numerical Regimes

Every arithmetic operation (`+`, `-`, `*`, `/`) in the FP32 VM is explicitly rounded to IEEE-754 `binary32` via `struct.pack('<f', ...)` with zero hidden FP64 accumulation. Static generators are reconstructed through `cayley_forward_f32(omega_f32)`.

| Benchmark DAG | `unnormalized` Max L2 (`SO(3)`) | `s3_norm` Max L2 (`SO(3)`) | `cayley_reproj` Max L2 (`SO(3)`) | `binary_refresh` Max L2 (`SO(3)`) | Projected Decode Exactness |
|---|---|---|---|---|---|
| `xor_chain_4` | `1.15e-5` (`1.02e-6`) | `2.71e-7` (`7.61e-7`) | `2.51e-7` (`6.85e-7`) | `1.16e-8` (`2.01e-8`) | `16 / 16` (`100%`) |
| `ripple_carry_adder_4bit` | `3.43e-5` (`1.43e-6`) | `5.93e-7` (`1.67e-6`) | `2.51e-7` (`6.94e-7`) | `1.16e-8` (`2.01e-8`) | `256 / 256` (`100%`) |
| `shared_diamond_d6` | `1.26e-4` (`1.07e-6`) | `1.01e-7` (`2.51e-7`) | `4.05e-8` (`1.15e-7`) | `1.16e-8` (`2.01e-8`) | `16 / 16` (`100%`) |
| `shared_diamond_d16` | **`7.62e+29` / `OVERFLOW`** (`0/16` ok) | **`2.70e-7`** (`7.30e-7`) | **`4.05e-8`** (`1.15e-7`) | **`1.16e-8`** (`2.01e-8`) | `16 / 16` (`100%`) |
| `three_sat_4var` | `6.67e-6` (`9.71e-7`) | `1.16e-7` (`3.19e-7`) | `1.33e-7` (`3.40e-7`) | `1.16e-8` (`2.01e-8`) | `16 / 16` (`100%`) |
| `majority_5` | `5.48e-6` (`7.52e-7`) | `1.15e-7` (`3.17e-7`) | `2.01e-7` (`5.67e-7`) | `1.16e-8` (`2.01e-8`) | `32 / 32` (`100%`) |
| `lyapunov_self_and_d16` | **`1.55e+20`** (`1/2` ok) | `1.52e-4` (`4.29e-4`) | `6.53e-8` (`1.65e-7`) | `1.16e-8` (`2.01e-8`) | `2 / 2` (`100%`) |

### Key Law-5 Numerical Findings (No Overclaiming)

1. **Unnormalized Radial $4^d$ Instability (Confirmed Failure Mode):** Because $A^\dagger$ is quaternion conjugation rather than $A^{-1} = A^\dagger / \|A\|^2$, any radial rounding error $\delta r$ satisfies $\|A B A^\dagger B^\dagger\| = \|A\|^2 \|B\|^2 \approx 1 + 4\delta r$. By `d = 16`, a single FP32 ULP explodes as $(1 \pm 10^{-7})^{4^{16}}$, causing both FP32 overflow (`> 3.4e38`) and radial collapse (`0.0`). **Projecting onto $S^3$ (`s3_norm` or `cayley_reproj`) on `V_ring` write is strictly mandatory** for deep circuits.
2. **Projected FP32 Drift `< 1e-5` on All Real DAGs Through `d = 16`:** With `s3_norm` or `cayley_reproj`, every benchmark circuit through `shared_diamond_d16` stays below `5.93e-7` (`s3_norm`) and `2.51e-7` (`cayley_reproj`), well under `1e-5`, with `100.00%` decode accuracy across all `354` truth assignments.
3. **Exact Tangential Lyapunov Boundary ($\rho = \phi \approx 1.618034$):** Linearizing $F(q, q) = [g_\alpha q g_\alpha^\dagger, g_\beta q g_\beta^\dagger]$ on the Lie algebra tangent space $T_{\tilde{\tau}_0} SU(2)$ gives $\operatorname{tr}(J_a) = \sqrt{5}$, $\operatorname{tr}(J_b) = \phi^{-1}$, $\operatorname{tr}(J_{\text{diag}}) = \frac{3\sqrt{5}-1}{2}$, $\det(J_{\text{diag}}) = \sqrt{5}-1$, and exact spectral radius **$\rho(J_{\text{diag}}) = \phi = \frac{1+\sqrt{5}}{2} \approx 1.618034 > 1$**. On an adversarial all-(1,1) deep chain (`lyapunov_self_and_d16`), generic tangential perturbations grow as $\epsilon_0 \phi^d$ (reaching `1.52e-4` at `d = 16` under `s3_norm`, hitting the midpoint `0.309` around $d \approx 31$; `cayley_reproj` happened to land on a tiny FP32 rounding cycle around `tau0_f32` of amplitude `6.53e-8`, which is finite-precision quantization rather than asymptotic contraction).
4. **Arbitrary-Depth Closure via Binary `V_ring` Refresh:** Because $\{+I, +\tilde{\tau}_0\}$ are separated in scalar coordinate by $1 - \frac{1+\sqrt{5}}{4} \approx 0.190983$ (Euclidean separation $\|I - \tilde{\tau}_0\|_2 = \phi^{-1} \approx 0.618034$), a single branchless FP32 compare (`q0 > 0.9045085 ? +I : +tau0`) inside `V_ring` clamps drift permanently to `1.16e-8` (`<= 1` ULP) at arbitrary depth $d$.

---

## 5. Honest Law-4 Novelty & Prior-Art Calibration (`CS-13`)

| Layer | Status | Attribution & Scope |
|---|---|---|
| Width-5 branching programs over $A_5$ ($NC^1 = \text{BWBP}$, $4^d$ formula blowup) | **`N0` (Prior Art)** | Barrington (1989), *Bounded-Width Polynomial-Size Branching Programs Recognize Exactly Those Languages in $NC^1$*, JCSS 38(1). |
| $O(S)$ straight-line group/ring register programs avoiding $4^d$ DAG blowup | **`N0` (Prior Art)** | Ben-Or & Cleve (1992), *Computing Algebraic Formulas Using a Constant Number of Registers*, SICOMP 21(1); Cleve (1991). |
| Log-precision transformer $TC^0$ vs $NC^1$ separation under recurrent/group state | **`N0` (Prior Art)** | Merrill & Sabharwal (2023/2024), *The Parallelism Tradeoff / Expressive Power of Transformers with Chain of Thought*. |
| Classification of $2I \cong SL(2, 5) \subset SU(2)$ and rational Cayley transform on $SU(2)$ | **`N0` (Prior Art)** | Classical finite subgroups of $SU(2)$ (Klein 1884; Hurwitz) and Cayley (1846). |
| **Exact 9-class $SL(2,5) = 2I$ Spinor-Barrington Commutator Sign Dichotomy** (2-line $SU(2)$ trace identity proving order-5 $\mathbb{Z}_2$ obstruction vs acute order-10 $\mathcal{C}_{10}^+$ sign-free lift + strict interior-ball invariant $\|\omega\| \le \tan(\pi/5) < 0.8$ across all intermediate gate states) | **`N1` (Verified Constructive Synthesis)** | Proved analytically and verified exhaustively in exact $\mathbb{Q}(\sqrt{5})$ (`0/14,400` trace mismatches) in `barrington_su2_dag_compiler.py`. |
| **Concrete $O(S)$ DAG-to-`HoloSphere` `CayleySU2` + `16 B` Relational `V_ring` compiler + 4-regime FP32 drift / $\phi^d$ Lyapunov characterization** | **`N1` (Verified Constructive Synthesis)** | Targets `HoloSphere`'s single-step bounded-ball `CayleySU2` + `16 B` `V_ring` register ABI (compatible with the `33.69 µs/tok` Ampere `CellOp` VM, verified CPU-only here). |

**Explicit Non-Claims:**
- Storing $O(S)$ intermediate `16 B` holonomy registers in `V_ring` places this compiler in the $O(S)$-space straight-line register model (analogous to Ben-Or–Cleve), **not** the $O(1)$-width streaming branching-program model; it does **not** separate $TC^0$ from $NC^1$ or resolve any open circuit lower bound.
- All verification in Track `S119` is strictly CPU-only (`0` GPU touch); Ampere kernel dispatch latencies cited above are architectural context from prior verified `HoloSphere` tracks, not newly measured GPU benchmarks of this compiler.

---

## 6. Verification, Mutation & Hygiene Receipts (`R1–R5`)

| Artifact | Lines | SHA-256 |
|---|---:|---|
| `barrington_su2_dag_compiler.py` | `1,207` | `0b89e57a63502f4a2026ab9d871d2fbf30e1cefe04f72c0fcfc60f04694f6916` |
| `test_s119_barrington_r5.py` | `294` | `33c6911d99816e8d9cfa65b3703cd0862b510b011b74dc4f25c093134cc54c31` |
| `lean/HoloSphereSpinorBarrington.lean` | `609` | `972c14c36e991ab4b4c6a342bb24c499e8d7deb68749ba175d8af6893500e37e` |

*(Complete `(path, lines, bytes, sha256)` manifest covering this report and all `lean/` files is pinned in [README.md](README.md).)*

- **Stock `/usr/bin/python3` 3-Mode `-I` Parity (`-I -B`, `-I -O -B`, `-I -B -W error`):**
  - `barrington_su2_dag_compiler.py`: **bit-identical stdout** across all 3 modes (`payload_sha256 = 009dd43173448ca38adeea9240365f3e3532d98eb622d50a56ee2ae35f097f97`).
  - `test_s119_barrington_r5.py`: **`0` stdout bytes**, exit code `0` across all 3 modes (`0` bare `assert`s).
- **Mutation Audit (`aletheia mutate --max-mutants 0 --guards require_ok`):**
  - **`61 / 61 KILLED` (`100.0%`, `survived = 0`, `truncated = false`, `verdict = PASS`)** across all guard deletions and comparison boundary flips on `barrington_su2_dag_compiler.py`.
- **Hygiene & Safety Gates:** Pure Python stdlib (`0` third-party imports, `0` RNG calls, `0` floats in exact $\mathbb{Q}(\sqrt{5})$ core, `0` bare `assert`s, `0` absolute user-home path leaks, `0` CRLF, `0` `.pyc`/`__pycache__`), verified by dual external `aletheia audit-check --strict-ancestors --safety-scan --strict-unseeded`.
