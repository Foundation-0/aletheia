# Sphere / Hypersphere Geometry, Denominator-$\pi$ Division, & Physical-Force Operators for `Moissanite-Labs/siliquant`

- **Date:** 2026-11-25 (`ahraz` / `aletheion`, pure CPU exact-`bpw` benchmarks on live `Qwen/Qwen2.5-0.5B` `model.safetensors`, zero hidden per-block scales, zero weight files copied)
- **Status:** Empirically probed (`sampled` + `exact` identities; `N1` candidate operators pending full end-to-end RTX 3080 KL/PPL verification & clean-room audit)
- **Reproducible Probe Scripts (this directory):**
  - `bench_sphere_pi_siliquant.py` — Exact-`bpw` apples-to-apples benchmark (Cartesian Uniform/Lloyd-Max vs. 2D Polar $\pi$-Phase vs. 8D Clifford-Torus $\pi$ vs. $E_8$ Ball vs. Pure-Shell $S^7$ Gain-Shape, raw vs. `SphereMap`)
  - `bench_gersho_sphere_warp.py` — $SO(8)$-equivariant radial sphere warping (Gersho CDF vs. Power-Law $r^\gamma$ + integer shell-radius LUT $\rho[m]$)
  - `probe_hypersphere_forces.py` — Hypersphere measure concentration ($d = 2 \dots 128$), $SU(2) \cong S^3$ 600-cell (`2I`, 11-design), Gravity + Yukawa ($e^{-\mu r}/r$) repulsive spherical codebooks, gravitational multipole decomposition ($\ell = 0,1,2,4+$), and EM/Hodge radial-vs-transverse error split

---

## 1. Algebraic Progression: Base-$\pi$ $\to$ Numerator $\pi\mathbb{Z}$ $\to$ Denominator-$\pi$ ("Sphere = Whole = 1")

1. **Obstruction of Positional Base-$\pi$ (`W10-OBS-8`):** By Lindemann's theorem ($\pi$ transcendental over $\mathbb{Q}$), positional base-$\pi$ breaks integer carries ($4 = 10.2201220211\dots_\pi$) and loses uniqueness ($1 = 0.30110211100\dots_\pi$).
2. **Numerator $\pi$-Ruler ($\pi\mathbb{Z}$, half-turns $\mathbb{Q}\cdot\pi$):** Captures standing-wave nodes ($k_n L = n\pi$), Bohr–Sommerfeld/Maslov WKB action ($(2n + \mu/2)\pi$), Levinson scattering phase shifts ($\delta_\ell(0)-\delta_\ell(\infty) = N_\ell\pi$), superconducting flux ($\Phi_0 = \pi\hbar/e$), spin-$\tfrac{1}{2}$ $2\pi$/$4\pi$ phase, Bloch-sphere Berry phase ($\Omega/2$), and Fock (1935) / Moser (1970) $S^3$ regularization of Hydrogen & Kepler orbits. Fails on $\ell \ge 1$ spherical Bessel zeros ($\tan x = x$, $x_1 \approx 1.4303\pi$), dimensionless couplings ($\alpha^{-1}, m_p/m_e$), and discrete multiplicities — nature's true duality is Pontryagin $\widehat{S^1} \cong \mathbb{Z}$.
3. **Denominator-$\pi$ ("Sphere = Whole = 1", normalizing by $\omega_{d-1} = \frac{2\pi^{d/2}}{\Gamma(d/2)}$):**
   - **Physics & QFT:** $|\nabla G_d(r)| = \frac{1}{\omega_{d-1} r^{d-1}}$ (1 unit charge emits literally 1 whole sphere of flux), $\hbar = \frac{h}{2\pi}$, 4D $L$-loop factor $\frac{1}{(4\pi)^{2L}}$, Haar measure $d\mu_{S^{d-1}} = d\Omega/\omega_{d-1}$.
   - **Topology (Chern–Weil):** Winding number $\frac{1}{2\pi i}\oint \frac{dz}{z} \in \mathbb{Z}$, Gauss–Bonnet $\frac{1}{4\pi}\iint K\,dA = 1-g \in \mathbb{Z}$, Chern number $\frac{i}{2\pi}\int F \in \mathbb{Z}$, 4D QCD instanton $\frac{1}{8\pi^2}\int \operatorname{tr}(F\wedge F) \in \mathbb{Z}$.
   - **Integral Geometry & Modular Periods:** Buffon/Crofton $\frac{2}{\pi}$; Ramanujan/Chudnovsky $1/\pi$ series ($E_2^*(\tau) = E_2(\tau) - \frac{3}{\pi \operatorname{Im}\tau} = 0$).
   - **Sphere-Unit Coordinates ($\operatorname{Vol}(B^d) \equiv 1$):** Measuring length in unit-volume sphere radii $R_{\text{unit}} = \Gamma(\frac{d}{2}+1)^{1/d}/\sqrt{\pi}$ turns Zador's normalized second moment $G(B^d) = \frac{\Gamma(d/2+1)^{2/d}}{(d+2)\pi} \to \frac{1}{2\pi e}$ into the **pure rational constant $\frac{1}{d+2}$** (`1/10` in 8D, `1/18` in 16D, `1/26` in 24D) with zero $\pi$, moving $\pi$ exclusively onto hypercubes.
   - **Coxeter / Weyl Rational Folding ($S^{d-1}/W$):** Splits $S^{d-1}$ into exact congruent fractions (`1/120` of $S^2$, `1/14,400` of $S^3$, `1/696,729,600` of $S^7$ via $W(E_8)$, or fast $O(d\log d)$ $B_d$ sort+sign folding into `1/(2^d d!)` = `1/10,321,920` of $S^7$).

---

## 2. Live Exact-BPW Findings on `Qwen/Qwen2.5-0.5B` for `Moissanite-Labs/siliquant`

### A. Deformed-Sphere Inversion (`SphereMap = Sinkhorn dual_scale + H64`) + $SO(8)$-Equivariant `Power-0.7` Radial Sphere Warp + Zero-Bit Shell-LUT

- **Ellipsoid-to-Sphere Collapse (`+0.021–0.036 bpw` FP16 row/col radii, `6×–24×` cheaper than per-128 / per-32 block scales):**
  - `L0 down_proj`: kurtosis `4.58 -> 3.010` (`+0.0211 bpw`)
  - `L12 gate_proj`: kurtosis `5.58 -> 3.008` (`+0.0211 bpw`)
  - `L12 down_proj`: kurtosis `4.99 -> 3.010` (`+0.0211 bpw`)
  - `L12 q_proj`: kurtosis `5.29 -> 3.002` (`+0.0357 bpw`)
  - `L23 o_proj`: kurtosis `42.56 -> 3.785` (`+0.0357 bpw`)
- **Exact-Bisection Pullback Ablation (strictly out-of-sample Gaussian-fitted universal shell LUT $\rho[m]$, `0.0000` extra bits per block, zero runtime transcendentals):**

| Target (`3.0 bpw`, `E_8 = 2.9992 bpw`, 22 shells, $R^2 \le 44$) | Cart. Lloyd-Max RAW | $E_8$ Linear RAW | $E_8$ Linear + `SphereMap` | $E_8$ Linear + `SphereMap` + Shell-LUT | **$E_8$ `Power-0.7` Radial Warp + `SphereMap` (`+0b`)** |
|---|---:|---:|---:|---:|---:|
| Isotropic Gaussian $N(0,1)$ | `14.618 dB` | `15.646 dB` | `15.646 dB` | `15.759 dB` (`+0.113`) | **`15.818 dB` (`+0.172 dB` free)** |
| `Qwen2.5-0.5B` `L12 gate_proj` (`+0.0211b`) | `11.954 dB` | `12.393 dB` | `15.560 dB` | `15.677 dB` (`+0.117`) | **`15.736 dB` (`+0.176` vs Lin+Sp / `+3.34` vs RAW)** |
| `Qwen2.5-0.5B` `L23 o_proj` (`+0.0357b`, `kurt 42.56`) | `8.929 dB` | `9.190 dB` | `13.804 dB` | `14.029 dB` (`+0.225`) | **`14.336 dB` (`+0.532` vs Lin+Sp / `+5.15` vs RAW)** |

- **Honest Obstruction & Ablation Note:**
  - Gaussian CDF radial companding (`gammainc`) **fails on heavy-tailed `L23 o_proj`** (`-1.89 dB` saturation penalty at large $r$), whereas power-law radial warping $\Phi_{0.7}(x) = \|x\|_2^{-0.3} x$ never saturates.
  - At `2.0 bpw` (`E_8 = 1.9745 bpw`, 5 shells, $R^2 \le 10$) with exact bisection pullback: `Linear + SphereMap` hits `10.043` (Gauss) / `10.030` (`L12`) / `9.222 dB` (`L23`); 5-float Shell-LUT lifts Gaussian/`L12` to `10.090` / `10.080 dB` (`+0.05 dB`), and `Power-0.7` lifts `L23` to `9.267 dB` (`+0.045 dB`). *(Earlier `+0.39 dB` prototype reading was caught & eliminated by Law-3 ablation as a naive shell-1 overflow-fallback artifact.)*

### B. Denominator-$\pi$ Equal-Sphere-Fraction Partitioning (`EQ(S^{d-1})`) vs. Numerator-$\pi$ Angle Grids

Live directional SNR on `Qwen/Qwen2.5-0.5B` `L12 gate_proj + SphereMap`:
- **`S^2` (`K=64`, `6b`):** Numerator-$\pi$ grid `13.332 dB` (`mean_cos=0.97679`) $\to$ **Denominator-$\pi$ `EQ(S^2)` `14.924 dB` (`+1.592 dB`, `mean_cos=0.98391`)**.
- **`S^3` (`K=64`, `6b`):** Numerator-$\pi$ grid `7.400 dB` (`mean_cos=0.90902`) $\to$ **Denominator-$\pi$ `EQ(S^3)` `9.446 dB` (`+2.046 dB`, `mean_cos=0.94320`)**.
- **`S^3` (`K=256`, `8b`):** Pure closed-form analytical **`EQ(S^3)`** (zero training, zero LUT, exact `0..255` integer index!) achieved **`13.529 dB` (`mean_cos = 0.97782`)**, **beating 20-iteration trained spherical k-means (`0.97743`)** out of the box!

### C. Hypersphere Soap-Bubble Concentration ($d = 2 \dots 128$) & Physical-Force Operators

1. **Zero-Radial-Bit Surface Ceiling ($S^{d-1}$):**
   - `d=2`: `6.67` (Gauss) / `6.66` (`L12+Sp`) / `5.94 dB` (`L23+Sp`)
   - `d=8` ($S^7$): `12.17` / `12.04` / `9.66 dB`
   - `d=16` ($S^{15}$): `15.07` / `14.82` / `10.97 dB`
   - `d=24` ($S^{23}$, Leech): `16.83` / `16.44` / `11.86 dB`
   - `d=64` ($S^{63}$): `21.05` / `19.86` (vs `11.26` raw) / `12.35 dB`
   - **`d=128` ($S^{127}$): `24.00` / `22.96 dB` (`+11.40 dB` over `11.56 dB` raw!) / `15.18 dB`**
2. **Weak-Force Lie Group $SU(2) \cong S^3$ (600-Cell `2I` 11-Design) & Gravity + Yukawa ($e^{-\mu r}/r$) Codebook:**
   - 600-cell (`120` pts, `36.0°` min sep) + `1b` rad (`1.9767 bpw`): **`9.694 dB`** (Gauss) / **`9.680 dB`** (`L12+Sp`).
   - `K=256` on $S^3$ (`2.50 bpw` with `2b` rad): adding short-range **Yukawa repulsion ($e^{-\mu r}/r$)** to spherical k-means ("gravity") widened minimum separation **`19.0° -> 21.9°`**, improved mean cosine (`0.97743 -> 0.97812`) & worst covering (`0.9361 -> 0.9399`), and lifted SNR across all 3 targets: **`+0.094 dB`** (Gauss `12.472 -> 12.566`), **`+0.087 dB`** (`L12+Sp` `12.444 -> 12.531`), **`+0.076 dB`** (`L23+Sp` `11.705 -> 11.781`).
3. **Gravitational Multipole Spectrum & Electromagnetic / Hodge Decomposition of $E_8$ Error (`3.0 bpw`):**
   - Multipoles: dipole $\ell=1$ negligible (`10^{-6}..10^{-8}`), quadrupole $\ell=2$ dominates (`row_var CV = 0.678..1.172`), residual $\ell \ge 4$ excess kurtosis drops `2.58 -> 0.008` (`L12`) and `39.56 -> 0.785` (`L23`).
   - **EM / Hodge radial-vs-transverse error split on $E_8$ (isotropic expectation = `12.50%` radial / `87.50%` transverse):**
     - Gaussian: **`27.80%` radial** (`2.2×`) / `72.20%` transverse
     - `L12 gate_proj + SphereMap`: **`29.66%` radial** (`2.4×`) / `70.34%` transverse
     - **`L23 o_proj + SphereMap`: `54.01%` radial (`4.3×`!!)** / `45.99%` transverse — proving why `Power-0.7` radial warping directly unlocked `+0.532 dB` on `L23 o_proj`!
