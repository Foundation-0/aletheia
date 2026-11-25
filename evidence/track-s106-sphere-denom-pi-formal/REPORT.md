# Track S106 Phase 1A — Hypersphere Geometry, Denominator-$\pi$ Equal-Sphere-Fraction `EQ(S^{d-1})`, EM/Hodge Splitting, & Paired `H2b` Physics Benchmarks

**Author:** `@claude-architect` · **Protocol:** `PREREG-SPHERE-PI-FORCES-V1` (SHA-256 `ac3e62116bc4841320d2c713787c23568beed1ae738bf9b284b7f0c2a118d72a` recorded in the oracle; the prereg file itself is NOT shipped in this PR and no repo@sha is named, so the hash is an unverifiable external-historical pin — the "locked prior to execution" claim is not independently checkable) · **Scope:** Phase 1A formal + analytical physics track (`formal_and_physics/`), strictly CPU-only, `0` GPU touch, `0` external downloads, `0` GitHub pushes, `0` IEEE-754 floats (`int`/`Fraction`/`Decimal` `prec=30` only), `PYTHONDONTWRITEBYTECODE=1`.

**Novelty (Law 4):** **`N1`** (`n2_claims = 0`). Archimedes' Hat-Box projection on $S^2$, Hopf's $S^3$ fibration, Zador's ball second moment $G(B^d)$, Fock–Moser $SO(4)$ Hydrogen/Kepler regularization, Gauss–Legendre quadrature, Fibonacci lattices, Halton QMC, and the 600-cell (`2I`) spherical 11-design are classical prior art. Track S106 Phase 1A contributes:
1. A self-contained, zero-import pure-`Init` `Lean 4.36.0` formalization (`34/34` named `#print axioms` theorems, `0` `Classical.choice`, `0` `sorryAx`, `0` warnings) covering $\mathbb{Q}[\pi]$ graded-period cancellation, a universal proof that $B^{2k}$ strictly beats the $2k$-cube in Zador moment across all even dimensions $d = 2k \ge 2$ using only $\pi > 314/100$, arbitrary-dimension cleared-denominator EM/Hodge orthogonal splitting & radial-rescaling invariance over $\mathbb{Z}^d$, exact Hopf `EQ(S^3)` linear and quadratic midpoint moment laws, exact Hopf Fibration $\pi: S^3 \to S^2$ norm and $U(1)$ fiber-phase invariance (`EXP-Q06` formal companion), and universal $2^B$ slot-waste obstructions for exceptional spherical designs divisible by 3 or 5.
2. A zero-float, 30-digit deterministic `Decimal` execution of the preregistered **`H2b` Paired Analytical Physics Testbed** (`s106_physics_denom_pi_bench.py`) across matched node counts `N ∈ {64, 256, 1024}` on both 3D electrostatics/multipoles ($S^2$) and Fock–Moser regularized Hydrogen/Kepler ($S^3$), graded honestly as **`PARTIAL`** against the locked `>= 3×` gate while exposing the exact $\sqrt{1-z^2}$ / $\sqrt{u(1-u)}$ endpoint-singularity obstruction of tensor-product equal-area quadrature.

---

## 1. Pillar 1 — Sphere-Unit Coordinates ($\operatorname{Vol}(B^d) \equiv 1$) & Graded-Period $\mathbb{Q}[\pi]$ Algebra

- Measuring length in sphere-unit radii ($\operatorname{Vol}(B^d) \equiv 1$) maps Zador's dimensionless normalized second moment of the $d$-ball to the **pure rational sequence** $G_{\text{su}}(B^d) = \frac{1}{d+2}$ (`1/4, 1/6, 1/8, 1/10, 1/18, 1/26, 1/66, 1/130` for $d \in \{2,4,6,8,16,24,64,128\}$), moving every factor of $\pi$ onto hypercubes.
- In even dimension $d = 2k$, $\operatorname{Vol}(B^{2k}) = \frac{1}{k!}\pi^k$ and $\omega_{2k-1} = \frac{2}{(k-1)!}\pi^k$, so $\pi^k$ cancels identically in $\omega_{2k-1} / \operatorname{Vol}(B^{2k}) = 2k = d$ (Lean Theorem 2).
- Using only the rational lower bound $\pi > 314/100$, Lean Theorem 5 (`ball_beats_cube_zador_all_even_dims`) proves universally for **every even dimension $d = 2k \ge 2$** that $12^k \cdot k! \cdot 100^k < (2k+2)^k \cdot 314^k$, i.e., $G(B^{2k}) < G([-1,1]^{2k}) = \frac{1}{12}$. Using $\pi < 22/7$, Lean Theorem 6 proves the cube-to-ball volume ratio $(4/\pi)^k k!$ strictly grows at every step $k \to k+1$.

## 2. Pillar 2 — Exact Cleared-Denominator EM / Hodge Orthogonal Splitting over $\mathbb{Z}^d$

For any non-zero reference vector $x \in \mathbb{Z}^d$ ($S = \|x\|^2$) and arbitrary error vector $\delta \in \mathbb{Z}^d$, define the cleared components $\delta_\parallel^{\text{cl}} = \langle \delta, x \rangle x$ and $\delta_\perp^{\text{cl}} = S \delta - \langle \delta, x \rangle x$. Lean Theorems 7–16 prove universally over **arbitrary dimension (`List Int`)**:
- **Exact reconstruction & orthogonality:** $\delta_\parallel^{\text{cl}} + \delta_\perp^{\text{cl}} = S \delta$, $\langle x, \delta_\perp^{\text{cl}} \rangle = 0$, and $\langle \delta_\parallel^{\text{cl}}, \delta_\perp^{\text{cl}} \rangle = 0$.
- **Exact Pythagorean / Lagrange identity:** $S^2 \|\delta\|^2 = \|\delta_\parallel^{\text{cl}}\|^2 + \|\delta_\perp^{\text{cl}}\|^2$, and for all transverse weights $\lambda_\perp \ge 1$, $D_{\lambda_\perp}(x, \delta) = \|\delta_\parallel^{\text{cl}}\|^2 + \lambda_\perp \|\delta_\perp^{\text{cl}}\|^2 \ge S^2 \|\delta\|^2$.
- **Radial-rescaling invariance:** For all $c \in \mathbb{Z}$, $D_{\lambda_\perp}(c x, \delta) = c^4 D_{\lambda_\perp}(x, \delta)$, so for every $c \ne 0$ the selection order $D_{\lambda_\perp}(c x, \delta_1) \le D_{\lambda_\perp}(c x, \delta_2)$ depends solely on the unit direction $\hat{x} \in S^{d-1}$.
- **Zero transverse leakage under radial warp:** Any radial-only error $\delta = k x$ satisfies $\|\delta_\perp^{\text{cl}}\|^2 = 0$ identically.
- Pure-$\mathbb{Q}$ oracle witnesses confirm all four identities across $d \in \{3, 4, 8, 16\}$ (`S2_R3`, `S3_R4`, `S7_R8`, `S15_R16`) with exact rational radial fractions `289/1014`, `40/117`, `1/3`, and `289/798` vs. isotropic expectation $1/d$.

## 3. Pillar 3 — Denominator-$\pi$ Equal-Sphere-Fraction (`EQ(S^2)`, `EQ_Hopf(S^3)`) & $2^B$ Slot Utilization

- **Archimedes Hat-Box (`EQ(S^2)`):** Partitioning $z \in [-1, 1]$ into $M_z$ strips of constant scaled width `2` (Lean Theorems 17–18) yields exact sphere fraction $1/(M_z M_\phi)$ per cell with zero $\pi$ in cell measure.
- **Hopf Equal-Measure Cube (`EQ_Hopf(S^3)`):** Under the Hopf fibration $(u, v_1, v_2) \in [0, 1]^3 \mapsto (\sqrt{1-u}\cos 2\pi v_1, \sqrt{1-u}\sin 2\pi v_1, \sqrt{u}\cos 2\pi v_2, \sqrt{u}\sin 2\pi v_2)$, normalized Haar measure on $S^3$ is literally Lebesgue $du\,dv_1\,dv_2$ (zero transcendental CDF inverse!). Lean Theorems 19–22 prove universally for all $a \in \mathbb{N}$:
  - $\sum_{i=0}^{a-1}(2i+1) = a^2$ and $\sum_{i=0}^{a-1}(2a-(2i+1)) = a^2 \implies \frac{1}{a}\sum u_i = \frac{1}{a}\sum (1 - u_i) = \frac{1}{2}$ **identically**, explaining why `EQ_Hopf(S^3)` integrates all 5 Fock–Moser `1s/2s/2p` Hydrogen states with **exact `0` error** for all $a \ge 1$.
  - $3 \sum_{i=0}^{a-1}(2i+1)^2 = a(4a^2 - 1) \implies \frac{1}{a}\sum u_i^2 = \frac{1}{3} - \frac{1}{12 a^2}$, explaining the exact **`4.0000×`** error reduction from $a = 4$ (`N = 256`) to $a = 8$ (`N = 1024`) on the `3s/3p/3d` states!
- **Hopf Fibration $\pi: S^3 \to S^2$ Algebraic Invariance (`EXP-Q06` Companion):** For $\pi(a, b, c, d) = (2(ac+bd), 2(bc-ad), a^2+b^2-c^2-d^2)$, Lean Theorems 31–34 prove universally over $\mathbb{Z}$ that $\|\pi(z)\|^2 = (a^2+b^2+c^2+d^2)^2$ and that rotating both complex components by $(u, v)$ scales the $S^3$ norm-squared and all three Hopf image coordinates uniformly by $u^2 + v^2$ (exact $U(1)$ fiber-phase invariance for any Pythagorean phase $u^2 + v^2 = D^2$, verified in the pure-$\mathbb{Z}$ oracle on `(3, 4, 5)` and `(5, 12, 13)`).
- **Universal $2^B$ Slot-Waste Obstruction:** Lean Theorems 23–25 prove $\forall b,\; 3 \nmid 2^b$ and $5 \nmid 2^b$, obstructing every exceptional spherical design divisible by 3 or 5 from ever achieving zero waste in $2^B$-indexed tables: `DenomPi_EQ` achieves `0` wasted slots (`1.000000`), whereas `D4` 24-cell wastes `8/32` (`3/4`), 600-cell `2I` wastes `8/128` (`15/16`), $E_8$ shell-1 wastes `16/256` (`15/16`), $E_8$ shell-1+2 wastes `1,696/4,096` (`75/128`), and Leech shell-1 wastes `65,584/262,144` (`12285/16384`).

## 4. Pillar 4 — Hypersphere Thin-Shell Concentration & Coxeter/Weyl Rational Sphere Fractions

- Asymptotic squared radial width $\mathrm{CV}^2(d) = \frac{1}{2d}$ (`1/4 -> 1/256`) and exact $\chi^2_d$ relative variance $\frac{\mathrm{Var}(R^2)}{(\mathbb{E}[R^2])^2} = \frac{2}{d}$ (`1 -> 1/64`) strictly decrease across $d \in \{2, 4, 8, 16, 24, 64, 128\}$ (Chebyshev thin-shell monotonicity proved universally in Lean Theorem 26).
- Hyperoctahedral sort+sign folding $|W(B_d)| = 2^d d!$ (`8, 48, 384, 10,321,920` for $d = 2, 3, 4, 8$) satisfies $0 < |W(B_d)| < |W(B_{d+1})|$ and $2^d \mid |W(B_d)|$ for all $d$ (Lean Theorems 27–29), while $|W(H_3)| = 120$, $|W(H_4)| = 14,400 = 120^2$, $|W(E_8)| = 696,729,600$, and $2 |W(E_8)| = 135 |W(B_8)|$ (`[W(E_8) : W(D_8)] = 135`, Lean Theorem 30).

## 5. Pillar 5 — `H2b` Paired Analytical Physics Benchmarks (`s106_physics_denom_pi_bench.py`, 30-Digit Zero-Float `Decimal`)

**Preregistered `H2b` Verdict: `PARTIAL` (`>= 3×` gate strictly applied across ALL baselines and controls).**

### 5.1 Benchmark (a) — 3D Electrostatics / Gravity ($S^2$: Off-Center Gauss Flux & $\ell = 0..6$ Multipoles at `N = 1024`)

| Grid (`N = 1024`; cube-face `1014`) | Gauss Flux RMS | SH Gram RMS (`49×49`) | SH Gram Max | `EQ(S^2)` Speedup / Ratio vs Grid |
|---|---:|---:|---:|---|
| **`DenomPi_EQ_S2` (equal-wt `1/N`)** | `1.566337e-3` | `3.498043e-3` | `8.203629e-2` | Baseline (`1.0000×`) |
| `NumPi_Unweighted` (equal-wt `1/N`) | `1.277330e-1` | `9.566768e-2` | `1.223013e+0` | **`81.5489×` flux / `27.3489×` SH (`PASS >= 3×`)** |
| `CartBox_Vol_S2` (equal-wt `1/N`) | `2.296501e-2` | `4.244915e-2` | `3.740916e-1` | **`14.6616×` flux / `12.1351×` SH (`PASS >= 3×`)** |
| `CartCubeFace_Unw` (`1014`, equal-wt) | `2.151927e-2` | `4.011336e-2` | `3.460843e-1` | `13.74×` flux / `11.47×` SH |
| `NumPi_SinWeight` ($\sin\theta$ Jacobian wt) | `2.902707e-4` | `2.872762e-4` | `5.011243e-3` | **`0.1853×` flux / `0.0821×` SH (`FAIL < 3×`!)** |
| `CartCubeFace_Jac` (`1014`, Jacobian wt) | `1.133285e-4` | `2.520473e-4` | `2.500450e-3` | `0.0724×` flux / `0.0721×` SH |
| `Ctrl_Fibonacci` (non-tensor equal-area `1/N`) | `1.097292e-5` | `1.059528e-4` | `1.235829e-3` | **Beats `NumPi_SinWeight` by `26.4534×` flux / `2.7114×` SH!** |
| `Ctrl_GaussLegendre` (spectral control) | `1.197814e-9` | **`0`** | **`0`** | Spectral optimum (`0` error to $>24$ digits on $\ell \le 6$) |
| `Ctrl_HaltonQMC` (QMC equal-area `1/N`) | `1.107057e-3` | `6.571497e-3` | `2.440432e-2` | Mixed (`0.71×` flux / `1.88×` SH) |

*(At `N = 256`: `DenomPi_EQ_S2` beats `NumPi_Unweighted` by `23.5704×` flux / `8.0204×` SH and `CartBox_Vol_S2` by `4.7427×` / `4.3130×`, while trailing `NumPi_SinWeight` at `0.2230×` / `0.1036×`. At `N = 64`, all $8\times 8$ tensor grids alias azimuthal $m = 4$ for $\ell \le 6$, giving `SH_Gram_Max = 1.0` even for Gauss–Legendre, while `Ctrl_Fibonacci` avoids aliasing at `2.279848e-2`.)*

### 5.2 Benchmark (b) — Fock–Moser Regularized 3D Hydrogen / Kepler ($S^3$ at `N = 256, 1024`)

| Grid (`N = 1024`, plus `600-cell` `N = 120`) | `1s/2s/2p` RMS (`5×5`) | `n=1..3` RMS (`14×14`) | Poisson Kernel RMS | `EQ_Hopf(S^3)` Speedup / Ratio vs Grid |
|---|---:|---:|---:|---|
| **`DenomPi_EQ_Hopf_S3` (equal-wt `1/N`)** | **`0`** | `1.674107e-3` | `8.542838e-4` | Baseline (`1.0000×`; `0` error on `1s/2s/2p` for ALL $N$!) |
| `DenomPi_EQ_Cap_S3` (equal-wt `1/N`) | `9.588183e-3` | `1.687820e-2` | `2.749900e-2` | `EQ_Hopf` beats `EQ_Cap` by `10.1×`–`32.2×` |
| `NumPi_Unweighted` (equal-wt `1/N`) | `2.449490e-1` | `2.163855e-1` | `3.953531e-1` | **`EXACT_INF` / `129.2543×` / `462.7889×` (`PASS >= 3×`)** |
| `CartBox_Vol_S3` (equal-wt `1/N`) | `2.838600e-3` | `5.056238e-2` | `3.416440e-2` | **`EXACT_INF` / `30.2026×` / `39.9919×` (`PASS >= 3×`)** |
| `NumPi_JacWeight` ($\sin^2\psi\sin\theta$ wt) | `3.273737e-3` | `3.195961e-3` | `4.280634e-4` | **`EXACT_INF` `1s/2s/2p` / `1.9091×` `n=1..3` / `0.5011×` Poisson (`FAIL < 3×` on Poisson!)** |
| `Ctrl_GL_Hopf_S3` (spectral control) | **`0`** | **`0`** | `2.877177e-4` | Spectral optimum (`0` on `n=1..3`) |
| `Ctrl_HaltonQMC_S3` (QMC equal-wt) | `1.559963e-3` | `4.623929e-3` | `1.233967e-3` | `EQ_Hopf` beats Halton QMC across all 3 metrics |
| `Ctrl_600Cell_11Design` (`N = 120`, non-$2^B$) | **`0`** | **`0`** | `5.215683e-4` | Exact 11-design (`0` on all `n=1..3` with `120` nodes) |

*(At `N = 256`: `DenomPi_EQ_Hopf_S3` achieves `h_1s2s2p_rms = 0`, `h_n123_rms = 6.696429e-3` — exactly **`4.0000×`** the `N = 1024` value `1.674107e-3`, matching Lean Theorem 22 — and beats `NumPi_Unweighted` by `32.3136×` / `73.5322×`, `CartBox_Vol_S3` by `8.2690×` / `6.9508×`, and `NumPi_JacWeight` on Poisson by `3.5219×`.)*

### 5.3 Honest Law-3 / Law-5 Diagnosis of the `PARTIAL` Verdict
- **Where Denominator-$\pi$ `EQ` wins decisively (`CONFIRMED >> 3×`):** Whenever every cell carries uniform measure $1/N$ with zero stored per-node Jacobian weights (matching equal-probability quantization / `EQ` coding), `DenomPi_EQ_S2` and `DenomPi_EQ_Hopf_S3` crush equal-weight Numerator-$\pi$ grids (`27×`–`463×` and `EXACT_INF`) and equal-weight Cartesian box projections (`12×`–`40×`).
- **Exact Obstruction (`FALSIFIED < 3×` vs. Jacobian-weighted smooth angle quadrature):** Tensor-product equal-area maps ($z \in [-1,1] \mapsto \sqrt{1-z^2}$ on $S^2$, $u \in [0,1] \mapsto \sqrt{u(1-u)}$ on $S^3$) have **endpoint derivative singularities** at the poles, capping midpoint convergence at $O(M^{-3/2})$ vs. $O(M^{-2})$ for Jacobian-weighted smooth angle grids and exponential convergence for Gauss–Legendre / 600-cell designs. Non-tensor equal-area `Ctrl_Fibonacci` breaks the $M_z \times M_\phi$ polar-ring curse on $S^2$ (`26.4534×` over `NumPi_SinWeight` on Gauss flux), isolating exact `N0`/`N1` scope cleanly.

---

## 6. Pure-`Init` Lean `4.36.0` Companion — `SphereDenomPiOperators.lean`

Zero imports, zero Mathlib, zero `sorry`, zero warnings, `rc = 0` under scrubbed `lean --stdin`, all **`34/34`** named `#print axioms` theorems $\subseteq \{\text{propext}, \text{Quot.sound}\}$ (`3 [] + 2 [propext] + 29 [propext, Quot.sound]`, `0` `Classical.choice`, `0` `sorryAx`; `12` auxiliary helper theorems not counted, `46` `theorem` declarations total). **Honest scope:** all theorems are formalized over `Nat` and `Int` (cleared-denominator polynomial, inner-product, Hopf-fibration, and rational-bracket identities over $\mathbb{Z}$/$\mathbb{N}$; transcendental $\mathbb{R}$ continuity and 30-digit quadrature integrals are evaluated in `s106_physics_denom_pi_bench.py`, NOT formalized over $\mathbb{R}$ in Lean).

| # | Theorem | Exact Lean Statement |
|---|---|---|
| 1 | `fact_pos` | `∀ n, 0 < fact n` |
| 2 | `even_sphere_area_to_ball_vol_ratio` | `∀ k ≥ 1, sphereAreaNum k * ballVolDen k = 2 * k * (ballVolNum k * sphereAreaDen k)` |
| 3–4 | `binom_linear_lower_bound`, `zador_step_factor` | `∀ a n, a^n * (a + n) ≤ (a + 1)^n * a`; `∀ k, 1200*(k+1)^2 < 628*(k+2)*(2k+1)` |
| 5 | `ball_beats_cube_zador_all_even_dims` | `∀ k ≥ 1, 12^k * fact k * 100^k < (2k + 2)^k * 314^k` ($G(B^{2k}) < 1/12$ under $\pi > 3.14$) |
| 6 | `cube_to_ball_vol_ratio_even_strict_growth` | `∀ k, 22 * (4^k * fact k) < 7 * (4^(k+1) * fact (k+1))` (under $\pi < 22/7$) |
| 7–8 | `vDot_comm`, `normSq_nonneg` | `∀ u v : List Int, vDot u v = vDot v u`; `∀ v, 0 ≤ normSq v` |
| 9–11 | `hodge_{reconstruction,orthogonality_ref,orthogonality}` | Arbitrary-dim $\mathbb{Z}^d$ (`x.length = d.length`): $\delta_\parallel^{\text{cl}} + \delta_\perp^{\text{cl}} = \|x\|^2 \delta$, $\langle x, \delta_\perp^{\text{cl}} \rangle = 0$, $\langle \delta_\parallel^{\text{cl}}, \delta_\perp^{\text{cl}} \rangle = 0$ |
| 12–13 | `hodge_{pythagorean_split,weighted_distortion_ge_euclidean}` | `x.length = d.length`: $\|x\|^4 \|\delta\|^2 = \|\delta_\parallel^{\text{cl}}\|^2 + \|\delta_\perp^{\text{cl}}\|^2$; $\lambda \ge 1 \implies \|x\|^4\|\delta\|^2 \le D_\lambda(x, \delta)$ |
| 14–15 | `hodge_radial_rescaling_{invariance,order_invariant}` | $D_\lambda(c x, \delta) = c^4 D_\lambda(x, \delta)$; $c \ne 0 \implies (D_\lambda(cx,\delta_1) \le D_\lambda(cx,\delta_2) \leftrightarrow D_\lambda(x,\delta_1) \le D_\lambda(x,\delta_2))$ |
| 16 | `hodge_radial_warp_zero_transverse` | `∀ x k, normSq (hodgePerp x (vScale k x)) = 0` |
| 17–18 | `eq_s2_hatbox_{strip_width_invariant,total_partition}` | `hatboxEnd m i - hatboxStart m i = 2`; `hatboxWidthSum m m = 2 * m` |
| 19–20 | `eq_hopf_{u_midpoint_sum,complementary_midpoint_sum}` | `∀ a, sumOdd a = a * a` and `sumRevOdd a a = a * a` (exact `1s/2s/2p` Hopf norms!) |
| 21–22 | `eq_hopf_3s_quadratic_moment_{nat,exact}` | `∀ a, 3 * sumOddSq a + a = 4 * a^3` and `3 * sumOddSq a = a * (4 * a^2 - 1)` |
| 23–25 | `pow2_not_div_by_{three,five}`, `exceptional_design_slot_waste_universal` | `∀ b, ¬(3 ∣ 2^b)`, `¬(5 ∣ 2^b)`, and `2^b ∉ {24, 120, 240, 2400, 196560}` |
| 26 | `thin_shell_chebyshev_monotone` | `∀ d1 d2 epsDen, d1 < d2 → 1 ≤ epsDen → 2*epsDen^2*d1 < 2*epsDen^2*d2` |
| 27–29 | `weylBn_{step_and_pos,strict_mono,div_pow2}` | `0 < weylBn d < weylBn (d+1) = 2*(d+1)*weylBn d` and `2^d ∣ weylBn d` |
| 30 | `coxeter_weyl_e8_b8_index` | `weylBn 8 = 10321920 ∧ weylE8 = 696729600 ∧ 2 * weylE8 = 135 * weylBn 8 ∧ weylH3^2 = weylH4` |
| 31 | `hopf_map_norm_sq` | `∀ a b c d : Int, hopfX^2 + hopfY^2 + hopfZ^2 = (a^2 + b^2 + c^2 + d^2)^2` |
| 32 | `hopf_fiber_norm_sq_scaling` | `∀ a b c d u v : Int`, rotating `(a,b)` & `(c,d)` by `(u,v)` scales $S^3$ norm-squared by `u^2 + v^2` |
| 33–34 | `hopf_map_u1_fiber_{scaling,invariance}` | Rotating both complex coords by `(u,v)` scales `(hopfX, hopfY, hopfZ)` by `u^2 + v^2` (`= D^2` when `u^2 + v^2 = D^2`) |

*Note:* Theorems 26 (`thin_shell_chebyshev_monotone`, a direct monotone Chebyshev bound) and 30 (`coxeter_weyl_e8_b8_index`, fixed-`d` integer arithmetic) are near-trivial and are still counted among the `34/34`; excluding them leaves 32 substantive theorems.

---

## 7. Verification Receipts

All post-last-edit verification gates passed **`100.0%`** (CPU-only, `0` GPU touch, `PYTHONDONTWRITEBYTECODE=1`):

- **Live Lean `4.36.0` (`SphereDenomPiOperators.lean`):** `34/34` named `#print axioms` theorems verified live under scrubbed allowlist `lean --stdin` (`3 [] + 2 [propext] + 29 [propext, Quot.sound]`, `0` `Classical.choice`, `0` `sorryAx`, `0` warnings, `0 B` stderr, `18/18` static Lean 4 pre-filter rules `0` findings, live poisoned `Init.olean` hijack blocked).
- **Canonical Certificate (`s106_formal_physics_certificate.json`, `0o644` (git 100644)):** `payload_sha256 = f1248b8722342f0856a394c86ee60a5e00f945404663431aa791aa52beb1e749`, `certificate_sha256 = af42a3077b0a64b953d0eed937c07d7fedfe98ff59777b36490e26f7ca62af05`, `--standalone | cmp` `EXACT`, `--verify-pins` NOT reproducible (pinned files not shipped, no repo@sha).
- **Exhaustive Scalar-Leaf Re-Signed Tamper Sweep (`690` payload leaves):** `690/690` rejected on `SEC`, `690/690` rejected on `FR0`, and `690/690` rejected on `FR1` (`2,070/2,070 = 100.0%`, `0` bypasses, `0` crashes, `caller_immutable = True`, plus `>4,300`-digit integer DoS rejected with typed error).
- **Direct 4-Surface v2.1 `zone_b_fuzzer` (zero wrappers):** **`82/82 PASS`** (`CLI 25/25`, `FR1 19/19`, `FR0 19/19`, `SEC 19/19`; `bypasses = 0`, `crashes = 0`).
- **Official `aletheia-fast-mutate` (`--guards require_ok --workers 2 --timeout 180 --max-mutants 0`):** **`167/167 KILLED = 100.0%`** across all 3 executable `.py` targets (`s106_physics_denom_pi_bench.py` `16/16`, `s106_sphere_denom_pi_oracle.py` `26/26`, `verify_s106_sphere_denom_pi.py` `125/125`; `survived = 0`, `truncated = False ×3`, `null_mutant = passed ×3`).
- **Whole-File AST `BoolOp` (`OP_SWAP + SUBCOND_DEL` across all 3 `.py` files):** **`19/19 KILLED = 100.0%`** (`0` survivors; `0` `BoolOp` nodes in bench/oracle, `19/19` killed in verifier).
- **Multi-Env `-I` & Read-Only Directory Parity (`0` Skips):** **`15/15 OK ×6`** (`-I -B`, `-I -O -B`, `-I -B -W error`, `PYTHONHASHSEED=42`, `env -i HOME=/nonexistent`, RO-dir), `--check ×6` matching `af42a307...`, `--standalone | cmp EXACT`, `--verify-pins` not reproducible (files not shipped), `TMP_LEFTOVER = 0`, `PYC_OR_LAKE = 0`.
- **Dual `aletheia audit-check` (`aletheia-fix-lean-gates-v2` & `aletheia-fast-mutate`, `--strict-ancestors --safety-scan --lean-audit --scripts verify_s106_sphere_denom_pi.py test_s106_sphere_denom_pi_r5.py`):** **`PASS ×2`** (`files_scanned = 9`, `r4 = 2/2`, `lean_findings = 0`, `safety_findings = 0`, `bare_assert = 0`, `leaks = 0`, `crlf = 0`, `pycache = 0`).

## 8. Frozen Companion Manifest

| File | Lines | Bytes | Mode | SHA-256 |
|---|---:|---:|---:|---|
| `SphereDenomPiOperators.lean` | `765` | `31,902` | `0o644` | `3184a96268417396b9583bdecfca941a0b2489f57a5eac7f47939e73cab4908d` |
| `lakefile.toml` | `5` | `122` | `0o644` | `46e7baa5d7019b638f5c00391c7b0965a407504b87a8892c02e27e87899e54ff` |
| `lean-toolchain` | `1` | `25` | `0o644` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |
| `s106_physics_denom_pi_bench.py` | `720` | `29,370` | `0o644` | `230b76208e6a9f1cbceeffae8d4ed555438380c06fcf7c316a8a77cabd3ecafb` |
| `s106_sphere_denom_pi_oracle.py` | `464` | `19,841` | `0o644` | `c105f9453e3f7cdafc12558c2e0b340a4f88826fa605dfb87d099cf5dadaf325` |
| `verify_s106_sphere_denom_pi.py` | `615` | `28,958` | `0o644` | `7804407397177b57fc9e4edf0d7a303350ef91238c011623661394c9aed0b8d1` |
| `test_s106_sphere_denom_pi_r5.py` | `723` | `40,784` | `0o644` | `a0e8a58dc71924d1de16f8c963e7ae14cc795419d912c6fc9755ec1e88d504a0` |
| `s106_formal_physics_certificate.json` | `1` | `20,592` | `0o644` | `bb19e74ca41ad1cb388d3862961ec648ce52df8009cc8fba74d5e94983d6101e` |
