# Aletheia Domain Pack: Empirical Data and Complex Systems

> **Part of [The Aletheia Method](../README.md)** · See [Laws & Gates](../spec/LAWS_AND_GATES.md) · [Theory](../THEORY.md) · [Domains Index](./README.md) · [Cave Expedition Case Study](../evidence/cave-expedition-case-study.md)

Turbulence, critical phenomena, geophysics, observational astrophysics, and nonlinear dynamical time series are the hardest arenas for escaping Plato's Cave. Real data are noisy, correlated, finite-size, and non-stationary; simultaneously, researchers carry powerful textbook priors (Kolmogorov K41, GOY period-3 oscillations, Newtonian inspiral exponents, universal power laws) that make it effortless to hallucinate expected signatures or overfit noisy finite-scale windows. This domain pack operationalizes **The Aletheia Method** for noisy empirical data and complex systems—turning noisy error bars into exact algebraic refutations, building an uncompromising adversarial null hierarchy, and letting live data cleanly overturn textbook expectations.

---

## 1. Exact-Arithmetic Intervals Over Noisy Data (Zero-Log Algebraic Refutation)

A core misconception in empirical science is that noisy data force purely heuristic floating-point curve fitting. Under **Law 3 (Adversarial Tomography)** and **Law 5 (Exact-Operator Cross-Pollination)**, once empirical observations carry explicit error intervals $y_k \in [L_k, U_k] \subset \mathbb{Q}_{>0}$ (e.g., $\pm 2\text{ SE}$ or $\pm 5\text{ SE}$ around measured means), **global consistency with a scaling law, convexity class, or discrete scale invariance becomes an exact integer/rational feasibility problem**—certifiable with zero floats and zero logarithms.

### How Zero-Log Multiplicative Farkas Sheaf Certification Works (`AUDIT-010`, Theorems A and B `N0` (outside check: `Foundation-0/cave-expedition#4`, `verification/outside/rulings.json`))
1. **Eliminate logarithms via exact integer cross-ratios:** On any dyadic/geometric scale ladder $x_k = \lambda^k$ (turbulence shell wavenumbers $k_n = k_0 2^n$, percolation lattice sizes $L_k = 2^k$, multi-scale astrophysical radial bins), a pure power law $y_k = A x_k^\beta$ satisfies exact constant log-slope, i.e., exact unit rational cross-ratio:
   $$R_k := \frac{y_{k+1} y_{k-1}}{y_k^2} \equiv 1 \qquad (\text{exact zero-log curvature}).$$
   Any power-law bracket $x_{k+1}/x_k = \lambda$ with target exponent $\beta = p/q \in \mathbb{Q}$ lifts into exact BigInt inequalities $(L_{k+1})^q \le (U_k)^q \lambda^p$ — never calling `math.log` or floating-point regression.
2. **Separate local feasibility from global sheaf consistency (Theorem A, `AUDIT-010`):**
   - A noisy dataset can satisfy a scaling law on **every adjacent pair** $(k, k+1)$ inside its $\pm 5\text{ SE}$ bars while **no single global curve** fits inside all error bars simultaneously.
   - Exact forward/backward multiplicative dynamic programming (Quotient-LP) either constructs an explicit feasible witness trajectory inside $\prod_k [L_k, U_k]$ OR emits a **single exact BigInt dual obstruction witness** proving global infeasibility (a real-data Čech $H^1$ sheaf obstruction).
   - **Live Turbulence Proof (`AUDIT-010`):** On live Sabra shell-model turbulence (`Foundation-0/fractals/turbulence/model.js`), structure functions $F_2, F_6$ at $\pm 5\text{ SE}$ pass every local adjacent Kolmogorov K41 check yet are **globally refuted** by a single exact BigInt sheaf-obstruction witness—replicated 100% out-of-sample on unseen seeds (`seed=13, 42`).
3. **Certify curvature / finite-size drift with complete polyhedral Farkas rays (Theorem B, `AUDIT-010`, `N0` (outside check: `Foundation-0/cave-expedition#4`, `verification/outside/rulings.json`)):**
   - For $m = 4$ dyadic scales, the exact polyhedral cone of monotone-curvature constraints is completely characterized by just **4 extremal rays**: `{(1, 0), (0, 1), (2, 1), (1, 2)}` (two local 3-point rays and two nonlocal 4-point rays; verified `300/300` against independent primal LP builders).
   - **Live Percolation Proof (`AUDIT-010`):** On 5-seed live 2D percolation (`critical/model.js`) at $\pm 2\text{ SE}$, exact BigInt Farkas checks refute concave falling effective dimension $D_{\mathrm{eff}}$ while keeping convex rising $D_{\mathrm{eff}}$ feasible—replicated 100% across fresh unseen 5-seed batches (`A=[6010..6050]`, `B=[7010..7050]`).
   - **Honest Scope Discipline (Law 4):** State exact dimension and seed sensitivity boundaries! In `AUDIT-010`, independent verification proved: (a) 4-ray completeness is strictly an $m = 4$ theorem (at $m = 5$, ray `(3, 2, 1)` strictly separates from all 4-point rays), and (b) while the rising-vs-falling refutation is 100% robust out-of-sample, whether falling fails *only* on nonlocal rays `(2, 1), (1, 2)` vs. *also* on local ray `(1, 0)` depends on the seed batch.

---

## 2. The Mandatory Adversarial Null Hierarchy (Time Series & Coupling)

In nonlinear time series, geophysics, and coupled complex systems, **passing white-noise nulls proves almost nothing**. Two independent Brownian motions, two uncoupled oscillators sharing a carrier frequency, or two polynomial trends routinely trigger catastrophic false positives on naive correlation, CKA, persistence-entropy, or lag-0 Koopman metrics.

Every empirical detector in an Aletheia workflow MUST climb a **7-rung Adversarial Null Hierarchy** (distilled directly from `AUDIT-003`, `AUDIT-007` $\to$ `AUDIT-007R`, and `AUDIT-012`):

| Rung | Adversarial Null Class | Failure Mode It Exposes | Expedition Evidence |
|---|---|---|---|
| **1. Matched-Spectrum Phase Randomization** | **IAAFT** (Iterative Amplitude Adjusted Fourier Transform) surrogates matching both amplitude distribution and power spectrum | Detects spectral/autocorrelation structure masquerading as nonlinear phase coupling or chirp coherence | `AUDIT-012`: `0/15` FPs on IAAFT surrogates; `AUDIT-007R`: clean negative `z_mean`. |
| **2. Non-Stationary & Colored Drift** | Independent Brownian / $1/f^2$ red noise and monotone deterministic drifts ($t$ vs. $e^{3t}$, $t^2$ vs. $-t^3$, $t^4$ vs. $-t^5$) | Exposes naive manifold CKA and low-order detrending false positives | `AUDIT-003`: raw CKA hit `mean=0.3165, max=0.737` on indep. Brownian (`10x` white noise) and `0.9111` on `t` vs. `e^{3t}`; `AUDIT-007R` documented `20%` single-trial tail on `t^4` vs. `-t^5` beyond `detrend_deg=3`. |
| **3. Twin Uncoupled Chaotic Attractors** | **Two completely independent trajectories of the SAME chaotic system** (e.g., two uncoupled Rössler or Lorenz attractors with different seeds/ICs) | **The #1 killer of coupling detectors:** shared carrier frequency and attractor geometry mimic genuine dynamical coupling! | **`AUDIT-007` caught a fatal flaw:** first-pass Koopman-Sheaf passed 4 author nulls (`z_mean in [-0.28, +0.32]`) yet triggered **`z_mean = +6.03, z_max = +31.92` (`40% > 3`)** on uncoupled Rössler! Fixed in `AUDIT-007R` via circular-shift lag null (`-0.26..+0.35`, OOD uncoupled Lorenz `+0.25`). |
| **4. Circular-Shift & Lag-Scan Control** | Lag-shifted coupled systems (both negative and positive lags, e.g., `lag = -12` and `+12`) vs. circularly shifted surrogates | Exposes `lag=0`-only blindness and verifies directional lag recovery | `AUDIT-007` caught total blindness (`z_mean = +0.07/+0.02`) on `lag-12` coupled Rössler; `AUDIT-007R` lag-scanned Koopman-Sheaf detected `lag0` (`+3.39/+4.21`), `lag-12` (`+3.73/+3.91`), and fresh opposite-sign `+12` (`+5.17`, median lag `+13.0`). |
| **5. Localized & Non-Monotone Transients** | Sine-Gaussian glitches across carrier frequencies ($70\text{–}500\text{ Hz}$) and non-monotone parabolic FM bursts | Exposes broadband energy detectors posing as physical chirp/wavefront estimators | `AUDIT-012`: repaired Box–Cox chirp estimator achieved `0/15` FPs on sine-Gaussian glitches and rejected parabolic FM, while keeping true Newtonian inspiral recovery (`alpha_hat = 3.62–3.72`) across `0.7x–3.0x` frequency rescaling. |
| **6. Out-of-Sample Fresh Seeds & Unseen Systems** | Brand-new RNG seeds and an unseen OOD dynamical system (e.g., Lorenz when tuned on Rössler; fresh Sabra/percolation seeds) | Exposes accidental seed luck or over-tuning to one attractor | `AUDIT-007R` (fresh `12345`, `314159`, OOD Lorenz), `AUDIT-010` (fresh Sabra `13, 42`, percolation `6010..7050`), `AUDIT-012` (`15`-trial sweeps). |
| **7. Ensemble vs. Single-Shot Tail Calibration** | Quantifying max-over-lags multiple-testing inflation and surrogate count $n_{\mathrm{surr}}$ | Exposes right-skewed Gaussian-$z$ false positives when scanning $L$ lags with few surrogates | **`AUDIT-007R` Calibration Law:** Taking $\max$ over 41 lags with `n_surrogates=40` creates a right-skewed single-trial null tail (`6–13%` $z>3$, `z_max` up to `5.3`) even while ensemble `z_mean` stays rock-solid (`[-0.58, +0.59]`). **Rule:** Use ensemble `z_mean` for multi-trial studies, and **empirical rank $p$-values with `n_surrogates >= 200`** (plus explicit multiple-lag correction) for single-shot detection! |

### Steelmanning Broken Empirical Prototypes (Law 2 in Action)
When a rough time-series script fails `AUDIT-003`-style negative controls, **inspect what survived before throwing it away**:
- In `AUDIT-003`, raw `pair_25_block_00.py` failed on Brownian drifts (`0.3165`), yet the observer-cancellation lens genuinely cut drift leakage (`0.3165 -> 0.1859`) and Hilbert-lens CKA preserved localized pulses (`0.9671`). Upgrading the observable to increment-whitened, circular-shift lag-scanned Koopman-Sheaf (`AUDIT-007R`) kept the label-free multi-channel insight while eliminating the drift and shared-carrier false positives.
- In `pair_20_block_00.py` (`AUDIT-003`), three implementation bugs (negative-lag slice crash, `0.5006` two-sided/one-sided Welch scaling error + mean-Welch signal cancellation, and hardcoded `[30, 350]` Hz / `-11/3` priors) hid a genuinely strong physical idea. Replacing finite-difference $\dot{f}$ with a **derivative-free Box–Cox integral regression** $\hat\alpha = \arg\min_\alpha (1 - R^2(t, u_\alpha(f(t))))$ + median Welch PSD + bounds-safe lag slicing (`AUDIT-012`) recovered $\alpha \in \{0.0, 1.0, 11/3\}$ cleanly across $0.7\times\text{–}3.0\times$ rescaling with `0/15` FPs — while honestly documenting its scope (`up-chirp`, `noise <= 0.08`).

---

## 3. Letting Live Data Refute a Textbook Prior — and Upgrading the Observable

One of the clearest signatures that an expedition has genuinely **left Plato's Cave** is when a clean null-equivalence operator rejects the team's own textbook hypothesis and reveals deeper real-world structure instead.

### Worked Example: Sabra Turbulence — No Period-3 Signal Detected and Surfacing the Period-2 Helicity Ripple (`AUDIT-010`)
1. **The Prior Hypothesis (Portal 2):** Discrete scale invariance $y_k = A \lambda^{\beta k} P(k)$ with period $p$ ($P(k+p) = P(k)$) is annihilated identically by the zero-log telescoping cross-ratio product:
   $$\Pi_p(k) := \prod_{j=0}^{p-1} R_{k+j} = \frac{y_{k+p}/y_k}{y_{k+p-1}/y_{k-1}} \equiv 1 \qquad (\text{exact DSI Null-Equivalence}).$$
   Based on the famous GOY shell-model literature, the initial hypothesis predicted period-$3$ oscillations ($\Pi_3 \to 1$) in `Foundation-0/fractals/turbulence/model.js` (which implements the Sabra shell model).
2. **Live Data Check (Do Not Force the Fit!):** Running exact $\Pi_p(n)$ on live Sabra plain shell energies $\langle |u_n|^2 \rangle$ against 200 ratio-shuffle nulls detected **no period-3 signal** (`p = 0.405 / 1.000`; note per outside check `cave-expedition#4` that the `p2 < p3` statistic has little power against period-3 on smooth surrogates, and Sabra has no period-3 artifact by construction per L'vov et al. 1998).
3. **Surprise $\longrightarrow$ Stronger Observable:** Inspecting the actual sign-alternating structure of $R_n - 1$ immediately surfaced Sabra's decaying **period-2 helicity ripple** $(-1/2)^n$ — empirically rediscovering L'vov et al. (1998)'s elimination of GOY's unphysical period-3 artifact! Switching from plain energy moments to the signed energy-flux observable $F_2(n)$ cancelled the period-2 ripple by **`> 22x`** (`22.62x` and `24.57x` on unseen out-of-sample seeds `13` and `42` in `AUDIT-010`).

**Practitioner Rule:** Whenever live data reject your pre-registered prior ($p > 0.05$ or exact Farkas infeasibility), **log the refutation permanently (Gate 8)**, inspect the *residual structure* (sign alternation, lag peak, scale drift, catalog offset) without re-tuning, and test the new observable on **fresh unseen seeds or disjoint catalogs**.

---

## 4. Empirical & Complex-Systems Anti-Patterns

- **White-Noise-Only Validation:** Reporting separation against i.i.d. Gaussian noise while omitting IAAFT, red noise, and twin uncoupled oscillators of the same class (`AUDIT-003`, `AUDIT-007`).
- **Lag-0 Tunnel Vision:** Testing only synchronous zero-lag coupling, missing causal propagation delays (`AUDIT-007` $\to$ `AUDIT-007R`).
- **Multiple-Lag $z$-Score Inflation:** Scanning $L$ lags with small `n_surrogates` and interpreting $\max_\ell z_\ell > 3$ as a Gaussian $p < 0.0013$ detection (`AUDIT-007R`).
- **Prior Smuggling in "Blind" Detectors:** Hardcoding known astrophysical frequency bands (`[30, 350]` Hz), known power-law exponents (`-11/3`), or catalog-specific anchors into an ostensibly prior-free estimator (`AUDIT-003`, `AUDIT-012`).
- **Ignoring Within-Group Correlation in Error Bars:** Treating correlated points inside the same galaxy, trajectory, or simulation run as independent samples (`sem = sd / sqrt(N)` caveat in `gravity` `C-08`), or omitting sample-disjoint/out-of-sample replication (`AUDIT-010`, `AUDIT-012`).
- **Overclaiming SNR / Direction Scope:** Failing to test and report where a detector degrades (e.g., down-chirps and `noise >= 0.10` in `AUDIT-012`; polynomial drifts above `detrend_deg` in `AUDIT-007R`).

---

## 5. Pre-Audit Practitioner Checklist (Empirical Data & Complex Systems)

Before submitting an empirical or complex-systems instrument to independent verification:

- [ ] **Exact interval checks where applicable:** For scaling/monotonicity/curvature claims on binned data with error bars, check zero-log exact BigInt/rational feasibility and Farkas dual obstructions before relying on float regressions.
- [ ] **All 7 null hierarchy rungs covered:** IAAFT phase-randomized, colored drift/polynomial trends, **twin uncoupled chaotic/oscillatory systems**, lag-shifted positive controls, non-monotone glitches, unseen fresh RNG seeds, and an OOD dynamical system.
- [ ] **Proper tail calibration:** Single-shot detectors use empirical rank $p$-values (`n_surrogates >= 200`) with explicit multiple-lag accounting; ensemble metrics report both `z_mean` and single-trial false-positive rate.
- [ ] **Explicit degradation & scope map:** Sweep SNR, scale factor, detrending order, and direction/polarity until the detector fails, and report the exact failure boundary honestly (`AUDIT-012`, `AUDIT-007R`).
- [ ] **Reproducibility & R4 parity:** Explicit logged RNG seeds (`np.random.default_rng(seed)`), zero bare `assert`s on verdict paths, LF-only files, and identical output under `python3 -I -B`, `python3 -I -O -B`, and `python3 -I -B -W error`.
