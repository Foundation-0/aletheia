# Aletheia Domain Pack: Theoretical and Computational Physics

> **Part of [The Aletheia Method](../README.md)** · See [Laws & Gates](../spec/LAWS_AND_GATES.md) · [Theory](../THEORY.md) · [Domains Index](./README.md) · [Cave Expedition Case Study](../evidence/cave-expedition-case-study.md)

Theoretical and computational physics sits on a razor's edge between two familiar cave shadows: **formalism without contact** (coordinate-dependent algebra or verbal "dualities" that evaporate under a change of variables or against a live action) and **numerical tuning without physics** (fitting extra parameters inside a fixed ansatz until residuals vanish, masking omitted degrees of freedom). This domain pack adapts **The Aletheia Method** (*Portal-Driven Resonance & Adversarial Tomography*) into an actionable workflow for field theory, modified gravity, cosmology, open quantum systems, Hamiltonian dynamics, and computational astrophysics.

---

## 1. What Counts as a Live Portal in Physics

Under **Law 1 (Active Portal-Keeper Loop)** and **Law 2 (Steelman Before Falsifying)**, never discard an unexplained numerical match, limit-case paradox, or broken prototype as coincidence or failure until you have extracted its strongest exact operator form. High-yield physics portals fall into four recurring classes:

| Raw Physics Portal | Shadow Reflex (Avoid) | Aletheia Steelman Move |
|---|---|---|
| **Exact dimensionless coincidence** (e.g., two thresholds or scales matching to $1.000000\dots$ across parameter variations) | Dismiss as "just a re-parameterization" or celebrate numerically without deriving why | Compute the exact symbolic ratio in full symbolic parameters; check whether an eliminated fast sector or Schur complement forces the ratio to be identically $1$. |
| **Limit-case or boundary paradox** (e.g., $\lambda_s \to 0^+$, $c_s \to 0$, $N \to \infty$, or a panel split between $N=1$ and $N=10^{93}$) | Treat the boundary as singular and stay safely in the interior | Take the limit directly in the exact action, Hamiltonian, or generator; check whether a non-local kernel, Yukawa cutoff, or Zeno sealing regime emerges cleanly at the boundary. |
| **Local closure failure** (e.g., zero-pressure and adiabatic fluid closures both miss the full action ODE by $25\%\text{–}185\%$) | Fit phenomenological viscosity/sound-speed parameters to patch the curve | Eliminate the fast variables algebraically via a slow-manifold lift $y = H(t)x$ and solve the exact Riccati/invariance defect $\mathcal{R}[H] = 0$ with zero free parameters. |
| **Apparent cross-code or cross-paper constant mismatch** (e.g., $2.6794$ vs. $3.9251$ for the same Schrödinger–Poisson soliton) | Assume one codebase has an ODE bug and ignore the discrepancy | Replay both dimensionless normalizations verbatim; test whether two different physical definitions (half-density $r_c$ vs. half-mass $r_{1/2}$) reconcile the ratio to $< 10^{-5}$. |

---

## 2. Worked Resonance Case Studies (Verified in `AUDIT_LOG`)

### Case 1: Dimensionless Coincidence $r_{\mathrm{zero}}/\mu^2 \equiv 1$ + $\lambda_s \to 0^+$ $\longrightarrow$ Exact AeST Hamiltonian Schur-Complement Theorem (`AUDIT-011` / `AUDIT-011R`, `N2`)

1. **Raw Portal:** In constrained linear Aether-Scalar-Tensor (AeST) cosmology (`Foundation-0/gravity`, `research/aest-response-gate-20261112/slow-mode`), both local fluid closures failed the 1% benchmark catastrophically (`24.6%–27.4%` for zero-pressure; `117.6%–185.4%` for adiabatic pressure).
2. **Steelman Closure (Zero Free Parameters):** Eliminating the fast scalar-vector pair $(\chi, Z)$ directly from the exact quadratic ADM action with $\mathcal{F}(\mathcal{Y},\mathcal{Q}) = (2-K_B)\lambda_s \mathcal{Y} - \mathcal{K}(\mathcal{Q})$ yielded a **non-local Helmholtz pressure law**:
   $$\left(M_{\mathrm{scr}}^2 - \frac{\nabla^2}{a^2}\right)\delta P = c_a^2 M_{\mathrm{scr}}^2\,\delta\rho, \qquad M_{\mathrm{scr}}^2 \equiv \frac{\mathcal{K}'' Q^2 (1 + \lambda_s)}{2 + K_B \lambda_s},$$
   and an exact scale-dependent AeST self-gravity law:
   $$\frac{G_{AA}(k/a)}{\widetilde{G}} = \frac{\mathcal{K}'' Q^2 (1+\lambda_s) - (2-K_B)\lambda_s (k/a)^2}{\mathcal{K}'' Q^2 (1+\lambda_s) + (2+K_B\lambda_s)(k/a)^2}.$$
   Solving the continuous-time Riccati invariance commutation defect $\mathcal{R}[H] := C + FH - \dot{H} - H(A + BH) = 0$ via recursive Chebyshev Fenichel lifts $H_0 \to H_3$ dropped the slow-mode error across all $k/Q_0 \in \{6,9,12,18,24\}$ to **`0.55%–0.59%`** at $H_0$ against the upstream frozen-subspace initial condition (exposing a `0.37%` hidden off-manifold IC leak in the upstream benchmark itself) and **`0.000083%–0.001263%`** at $H_3$ against the invariant IC.
3. **Resonance Re-Entry (The Coincidence Portal):** The wavenumber $r_{\mathrm{zero}}$ where $G_{AA}(k/a)$ flips sign from attractive to self-repulsive matched Skordis & Zlosnik's Minkowski UV-stability threshold $\mu^2$ identically: $r_{\mathrm{zero}}/\mu^2 \equiv 1$. Instead of stopping at the coincidence, re-entering the Minkowski quadratic Hamiltonian $H_2(\chi, p, P)$ ($P = -2D$) and computing the exact Schur complement eliminating the fast canonical pair $(\chi, p)$ produced the **Exact AeST Hamiltonian Schur-Complement Theorem**:
   $$\min_{(\chi, p)} H_2(\chi, p, P) \;=\; \frac{1}{2} S_P P^2 \;\equiv\; -\left(\frac{G_{AA}(k)}{\widetilde{G}}\right)\frac{D^2}{2k^2} \qquad (\text{exact } 0 \text{ symbolic residual}).$$
   - **Physical meaning:** UV Hamiltonian positivity ($\Delta_3 > 0$, Sylvester inertia `[3, 0, 0]` for $k > \mu$) is *mathematically identical* to positive gravitational self-energy $\iff$ **self-repulsive anti-gravity** ($G_{AA} < 0$), while the IR `[2, 0, 1]` inertia ($k < \mu$) is negative gravitational binding energy ($G_{AA} > 0$).
   - **Boundary Portal ($\lambda_s \to 0^+$):** Pushing to $\lambda_s = 0$ sends $\mu^2 \to +\infty$, leaving $S_P = -\frac{\mathcal{K}''}{4r(\mathcal{K}''+2r)} < 0$ strictly for all finite $r > 0$ — a **zero-sound-speed spatial Yukawa cutoff** $G_{AA}/\widetilde{G} = M_0^2/(M_0^2 + k^2/a^2)$ with uniform inertia `[2, 0, 1]` (certified with zero floats on $[9/10, 11/10] \times [-1/10, 1/10] \times [1, 4]$ in `907` boxes in `AUDIT-013R`), evading Wave-10's local barotropic sound-speed no-go (`C-25`).
   - **Coupled Baryon Duality:** Minimally coupled baryons leave the fast $(\chi, Z)$ block identically independent of $D_b$, giving $\Phi_{\mathrm{static}}/\Phi_{\mathrm{Newton}} \equiv 1 - 1/G_{AA}(k/a)$ and out-of-sample 6-state ODE agreement `err_b <= 0.0087%`, `err_A <= 0.21%` on 4 untested $(K_B, \lambda_s, k)$ tuples.

### Case 2: Reconciling a Two-Panel Quantum/Astrophysical Paradox via Exact $16\times 16$ GKSL Zeno Schur Complement (`AUDIT-018`, `N2`)

1. **Raw Portal:** In `Foundation-0/fractals/witness-map/model.js`, single-particle decoherence (`rates()`, witness number $W = \Gamma \cdot m\Delta x^2/\hbar$) and $N \sim 10^{93}$ wave dark-matter lumps (`crowd()`) were split into two disconnected panels: a single particle has $W \ll 1$, a crowd has overwhelming gravitational witnessing, yet internal wave interference lumps survive.
2. **Exact Operator Realization (Pure $\mathbb{Q}$ / $\mathbb{Q}(i)$, Zero Floats):**
   - **Multipole & Huygens–Steiner Split:** For any zero-CM cluster ($\sum_{j=1}^N \xi_j = 0$), coherent CM coupling gives $\Gamma_{\mathrm{CM}} = N^2 \Gamma_1$ and $t_{\mathrm{wave}}^{\mathrm{CM}} = N t_{\mathrm{wave}}^{(1)}$, forcing exact **$W_{\mathrm{CM}}(N) \equiv N^3 W_{\mathrm{single}}$**; meanwhile $O(k^0)$ and $O(k^2)$ cancel identically on internal modes, leaving quadrupole tidal rate $\Gamma_{\mathrm{int}}^{(4)} = \frac{\gamma_0 k^4}{8}(\Delta I_{\mathrm{int}})^2$, and the mass quadrupole splits additively $Q(R, \xi) = N m R^2 + m I_{\mathrm{int}}(\xi)$ with zero cross-term iff $\sum_j \xi_j = 0$.
   - **First-Principles $16\times 16$ GKSL Lindblad Superoperator:** Built directly from $4\times 4$ matrix commutators/dissipators over $\mathbb{Q}(i)$ on $\mathcal{H}_{\mathrm{CM}} \otimes \mathcal{H}_{\mathrm{rel}}$, eliminating fast-decohering $\mathcal{V}_{\mathrm{wit}}$ via exact rational Schur complement yields:
     - Exact Tomita–Takesaki modular flow commutation $[\mathcal{D}[Z\otimes I], \Delta_{\rho_S}] \equiv 0$ and KMS detailed balance on non-diagonal, non-product faithful $\rho_S \in \mathcal{V}_{\mathrm{inv}}$;
     - Exact **$1/N^2$ Quantum-Zeno sealing** of internal coherences (`IX`, `IY` decay rate $2\gamma_{\mathrm{tid}} + 2g^2/(N^2 \gamma_1)$) alongside exact `0` decay on $\mathcal{F}^{\mathrm{inv}}$ (`IZ`);
     - Exact degenerate `(12, 8)` and split `(14, 12)` EP2 Jordan blocks at $\gamma_{\mathrm{CM}} - \gamma_{\mathrm{tid}} = 2g$, exact Riccati slow-manifold bridge to Case 1 (`R[H_6] = 2.36e-15`), and exact commutation $[\mathcal{L}_{\mathrm{bare}}, \mathcal{L}_{\mathrm{clock}}] \equiv 0$ for coherent soliton oscillations $H_{\mathrm{rel}} = \omega(I\otimes Z)$.
3. **Live Upstream Anchor Discovery (`node` parity `0.0` / `6.43e-16`):** Running the exact model against live `witness-map/model.js` both **reconciled the cross-repo soliton constant** (`model.js` half-density $M_{\mathrm{sol}} r_c = 2.6794\,\hbar^2/(Gm^2)$ vs. `gravity` `C-03` half-mass $M_{\mathrm{sol}} r_{1/2} = 3.9251\,\hbar^2/(Gm^2)$, relative diff `1.45e-6`, $r_{1/2}/r_c = 1.4649$) AND uncovered an exact **Sgr A* horizon scaling law** at $b = 8.18\text{ kpc}$: $\Gamma_{\mathrm{BH}}^{\mathrm{CM}} \propto m^{-10}$, $\Gamma_{\mathrm{BH}}^{\mathrm{CM}} t_{\mathrm{lump}} \propto m^{-11}$, $W_{\mathrm{BH}}^{\mathrm{CM}} \propto m^{-15}$, giving sharp crossover boson masses **`m*(tau = tLump) = 2.83e-20 eV`** and **`m*(tau = 13.8 Gyr) = 1.34e-19 eV`** (a `1e-22 eV` lump's CM decoheres in `24 fs`, whereas `3e-19 eV` takes `3,263x` cosmic age; verified by plugging both crossover masses back into live `model.js`: `tau/tLump = 1.0000000000000002`, `tau/AGE = 1.0000000000000042`).

---

## 3. Exact Symbolic, Invariance, and Anchor Oracles for Physics

Physics claims fail most subtly when tested only in one coordinate gauge, one floating-point eigensolver, or one simplified toy equation. Enforce **Law 3 (Active Multi-Basis Tomography $\mathcal{G}_{\mathrm{obs}}$)** across three complementary oracle classes:

### 3.1 Exact Symbolic & Rational Oracles (`exact`)
- **Zero-residual symbolic derivation:** Derive reduced equations, Schur complements, static–dynamical dualities, and commutators from the **full symbolic action/Hamiltonian/Lindbladian** in `SymPy` over general parameters (never specialize to $K_B = 1, \lambda_s = 1$ first) and require literal `sp.simplify(lhs - rhs) == 0`.
- **Exact inertia & stability certification:** Never certify positivity, ghost-freedom, or Morse indices from `np.linalg.eigvalsh > 1e-12`. Use exact rational Bunch–Kaufman / $LDL^\top$ congruence ($C M C^\top = D$ verified identically over $\mathbb{Q}$ or $\mathbb{Q}(i)$), independent Faddeev–LeVerrier + Descartes/Sturm inertia checks (`AUDIT-011`, `AUDIT-016R`), and exact interval Gershgorin/Bernstein box subdivision over continuous parameter domains (`AUDIT-013R`, `AUDIT-015R`).
- **Gauge, basis, and scaling invariance (Gate 2):** Twist the state vector by arbitrary invertible / orthogonal / unitary transforms ($GL(n)$, $O(n, \mathbb{Q})$, $U(n)$) and rescale frequencies/units ($0.7\times\text{–}3.0\times$ in `AUDIT-012`); require physical observables, closure defects, and trace spectra to stay invariant within machine precision (`< 1e-11`) or exact `0` over $\mathbb{Q}$.

### 3.2 Live Upstream Anchor Oracles (`anchor`)
- **Direct Jacobian / RHS parity:** Never re-type a simplified ODE system from memory and claim it represents an upstream physics code. Compare your symbolic/analytical Jacobian directly against the untouched upstream script across multiple $(k, a)$ or parameter points (e.g., `AUDIT-011` verified `5.68e-14` max Jacobian diff against `slow-mode/probe.py` across $k\in\{6,12,24\}, a\in[1,2]$).
- **Live upstream simulator execution:** When unifying or reconciling an existing physics model (`model.js`, `wave7`, `point-charges`), execute the untouched upstream simulator/data loader live and verify quantitative agreement (`AUDIT-018` ran live `node` on `witness-map/model.js`).
- **Out-of-sample parameter regimes:** Always verify reduced ODE/PDE closures on **untested** parameter tuples outside the benchmark grid (`AUDIT-011` tested 4 new $(K_B, \lambda_s, k)$ tuples).

### 3.3 Pre-Adaptation Latch Detection & Sample-Disjoint Holdouts (`sampled`)
In phenomenological astrophysics and cosmology, a fitted threshold or scaling law can look overwhelmingly significant in-sample purely because two disjoint catalogs sit at opposite ends of an axis (**The Latch**).

- **Exact Latch Geometry (`AUDIT-005`):** Fitting inside a fixed basis $\Phi$ forces every stationary in-span diagnostic to read zero ($\sin^2(w, \operatorname{Col}(\Phi)) = 0$); forcing a fixed-span model to absorb one failed outside-span anchor $a_1$ strictly inflates global residual error by exact Pythagoras $\|r_{\mathrm{adapt}}\|^2 = \|r^*\|^2 + e_1^2/\|p_1\|^2$ (and shifts a second outside anchor $a_2$ favorably only inside the sharp Falsifier #6 window $0 < \rho_\Phi/\kappa_\perp < 2$).
- **Mandatory Astrophysical Protocol (`AUDIT-012`):**
  1. **Report pre-adaptation holdout error first:** Freeze parameters trained on one catalog/regime and evaluate on a **truly sample-disjoint outside anchor** without re-tuning.
  2. **Leave-One-Catalog-Out (LOCO) stress test:** Hold out each catalog class completely. In `AUDIT-012` on `Foundation-0/gravity`'s 126-system compilation, holding out ONLY the 6 galaxy anchors (`SPARC_HSB` + `KiDS_WL`) collapsed the fitted `~185–190 km/s` scale threshold to `73.9 km/s` (Hill), `131.0 km/s` (Jeans 2p), and **`60.15 km/s`** under `wave7`'s native correlated ODR (`cov_on=True`, holdout Hill $\chi^2 = 61.23$ vs. MOND `0.34`), while a smooth threshold-free sigmoid beat the sharp Hill threshold on held-out `Kettula2015_WL` and `Milgrom2019_opt` and a 5,000-trial global permutation test flagged cross-catalog offsets at $p = 0.0002$.
  3. **Disjoint-anchor refutation of in-sample overfitting:** On SPARC 14-bin RAR, free `d_s = 0.94` improved in-sample $\chi^2$ (`25.91` vs. `30.49` for `d_s = 1.00`), yet failed decisively on the truly disjoint KiDS-1000 1 Mpc weak-lensing anchor (`chi2 = 75.51` vs. `31.53`).
  4. **Likelihood-metric invariance:** Verify whether qualitative conclusions survive switching between diagonal $\chi^2$ and native correlated ODR (`AUDIT-012` confirmed the galaxy-holdout collapse sharpened under native ODR).

---

## 4. Physics-Specific Cave-Shadow Anti-Patterns

| Anti-Pattern | How It Happens in Physics | Concrete Expedition Lesson & Cure |
|---|---|---|
| **Substitution Shadow** | Certifying a clean toy proxy matrix/potential instead of the messy real upstream Hessian or action. | **`AUDIT-013` $\to$ `AUDIT-013R`:** Initial Probe 3 certified synthetic `M_truss = [[2, s], [s, s^2]]` (isolated singularity at `(9/10, 11/10)`) instead of the real `fibral-rigidity#5` piecewise Hessian (entire singular line $L_1 + L_2 = 2$). **Cure:** Wire the exact upstream piecewise formula directly and verify all published points verbatim. |
| **Coordinate / Frame Artifact** | Treating a gauge-dependent variable, unnormalized basis, or lab-frame $s=0$ Schur complement as a physical invariant. | In Probe 4 (`AUDIT-018`), evaluating the static $s=0$ Schur complement with coherent internal frequency $\omega \ne 0$ shows an apparent Lorentzian Lamb shift, whereas transforming to the rotating frame ($s = \pm 2i\omega$) proves exact zero Lamb shift because $[\mathcal{L}_{\mathrm{bare}}, \mathcal{L}_{\mathrm{clock}}] \equiv 0$. **Cure:** Always test $GL(n)/O(n)/U(n)$ invariance and compare Schur complements against exact eigenvalues. |
| **Post-Fit Tuning Masking Omitted Physics** | Adjusting free constants inside an incomplete model to silence a single failed test point (The Latch). | `AUDIT-005` proves exact Pythagorean residual inflation under in-span adaptation; `AUDIT-012` shows the `185 km/s` cluster threshold is held in place by 6 galaxy anchors. **Cure:** Freeze parameters before touching outside anchors; compare against smooth threshold-free baselines and report pre-adaptation $\chi^2$. |
| **Conflating Local / Linear Stability with Global Nonlinear Behavior** | Claiming a linear dispersion relation, Minkowski UV positivity, or local unjamming arc establishes global nonlinear/cosmological viability. | `AUDIT-011R` proved Minkowski UV stability `[3, 0, 0]` is linear self-repulsion ($G_{AA} < 0$), and honestly flagged nonlinear spherical-collapse caustic stability on the $\lambda_s = 0$ Yukawa branch as an open Wave 2 problem (`caustic_control.py`). **Cure:** Tag linear/local theorems explicitly as `local` / `linear` and never extrapolate past the verified regime. |
| **Silent Symmetrization / Weak TCB Guards** | Averaging `(M[i][j] + M[j][i]) / 2` or accepting `float`/`bool` inside an "exact" rational certifier. | Caught in `AUDIT-013` (`QI.pt(True)`, `QI.pt(1.5)`) and `AUDIT-015` (non-Hermitian forgeries passing as Hermitian PD). **Cure:** Enforce strict R3 type & symmetry rejection with explicit must-fail controls (`AUDIT-013R`, `AUDIT-015R`); document black-box callable limitations honestly (e.g., interval equality alone cannot detect skew-symmetric `[[1, t], [-t, 1]]` over `[-1/2, 1/2]` without symbolic matrix structure). |

---

## 5. Pre-Audit Practitioner Checklist (Physics)

Before handing a physics probe to adversarial verification (`aletheia audit-check` + clean-room verifier):

- [ ] **Real upstream target:** Equations, Hessians, and catalogs come directly from the untouched upstream repo/action (zero toy proxy substitution); Jacobian/simulator parity checked to `< 1e-12` (or exact `0`).
- [ ] **Exact symbolic & inertia checks:** All identities verified symbolically over general parameters (`SymPy` residual `0`) and numerically/rationally without trusting float eigensolvers for sign/rank verdicts.
- [ ] **Invariance & negative controls:** Tested under basis/gauge transforms ($GL/O/U$), unit/frequency rescaling, wrong-sign/flipped-closure controls, and broken conservation laws (e.g., broken $\sum \xi_j = 0$, wrong witness jump operator).
- [ ] **Outside-anchor discipline:** Any empirical fit reports pre-adaptation LOCO / sample-disjoint holdout error, likelihood-metric sensitivity, and permuted-null $p$-values.
- [ ] **R4 runtime parity & honest scope:** Zero bare `assert`s on validation paths; bit-identical output under `python3 -I -B`, `python3 -I -O -B`, and `python3 -I -B -W error`; explicit scope boundaries (`linear` vs. `nonlinear`, `local` vs. `global`, `high-SNR up-chirp`, `Draft PR`).
