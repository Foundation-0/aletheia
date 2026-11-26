# Track S127 (`EXP-Q31a` / `PREREG-W15`): Pure-$\mathbb{Q}$ Certification of `Rat NCAP` Antagonistic Cone Linearization, Commissural `V0/V3` `⦺` Gait Bifurcation & `HoloSphere` Dual-Pole Gate Transfer

- **Track:** `track-s127-ratncap-antagonistic-cone-gait` (`EXP-Q31a`, Wave-15 Portal 152)
- **Locked Preregistration:** `PREREG-W15` (`../preregistrations/PREREG_WAVE15_TENSORFOLD_RATNCAP_PSYCHOSCRIPT.md`, `SHA-256 = 6c938ddb41b912f01dba3ccb58e3f8cb54ebe60f93f6bc0eaec134bc93f189a0`)
- **Primary Source:** `rat-ncap/rat-ncap @ 4a561eecdb` & Bhattasali, Cui, Pinto, & Lindsay, *"Neural Circuit Architectural Priors for Rat Locomotion"* (`arXiv:2611.23364v1`, NeurIPS 2026, CC BY 4.0 paper / MIT code / Apache-2.0 Rat body).
- **Novelty Classification (Law 4):** `N1` (exact coordinate-free pure-$\mathbb{Q}$ algebraic certification + $T^4/S^1$ exact rational Krein-inertia proof + explicit `HoloSphere` dual-pole contractive gate transfer; classical foundations in Shadmehr 1993, Ekeberg 1993, Dickinson et al. 2000, Bellardita & Kiehn 2015, and Danner et al. 2017 are explicitly credited).
- **Hardening & Verification (`100.0%`):** Strictly CPU-only (`CUDA_VISIBLE_DEVICES=""`, `OPENBLAS_NUM_THREADS=1`), `0` float literals in AST, `0` bare `assert`s, `51/51 = 100.0%` `aletheia mutate --max-mutants 0`, `10/10 = 100.0%` exhaustive AST `BoolOp` sweep, `3`-mode `-I` parity (`certificate_sha256 = dd1aeb8309fa259ffeb5947eb0419dd152ccd9aa4f05e52e02d332cf569f4e06`), fail-closed `validate_certificate_payload()` enforced on both `--write` and `--check` (verified against in-memory monkeypatch attacks), dual `aletheia audit-check PASS`, `PYC=0, ELF=0, WEIGHTS=0`.

---

## 1. Own-Terms Steelman (`OWN_TERMS_FIRST`, Law 2b)

In `Rat NCAP` (`arXiv:2611.23364v1`), a biologically grounded mammalian spinal circuit (Rhythm Generation `RG` with frozen half-center + commissural synapses, Brainstem Command `BC`, Afferent Feedback `AF`, Pattern Formation `PF`) controls 31 of 38 active DOFs of a MuJoCo rat (`Rat v2`) trained purely with Augmented Random Search (`ARS`) and simple velocity/pose rewards — achieving stand, walk, trot, bound, and zero-shot mid-episode gait transitions **without imitation learning** (`§4.1–§4.2`). Two mechanistic findings stand out on their own terms:
1. **Flexor-Extensor Actuation (`§3.3`, `§4.3`, Fig. 3D & Fig. 6):** Replacing direct torque, fixed-stiffness position, or explicit bilinear position-stiffness control ($\tau = k_{\mathrm{eq}}(q_{\mathrm{eq}} - q)$) with antagonistic muscle springs ($\tau = a_{\mathrm{ext}} k_{\mathrm{ext}}(q_{\mathrm{ext}} - q) + a_{\mathrm{flx}} k_{\mathrm{flx}}(q_{\mathrm{flx}} - q)$) yields the highest training return, tightest speed tracking, rounded ground-contact trajectories, and markedly higher negative (braking/storage) and positive (elastic return) mechanical power.
2. **Commissural Cell-Type Ablations (`§4.4`, Fig. 7B–C):** Scaling inhibitory commissural `V0v+V0d` down through $k \approx 0.35 \to 0.1$ abruptly flips anti-phase **Trot** to in-phase **Bound** (reproducing Bellardita & Kiehn 2015 mouse knockouts at $k=0$), whereas scaling excitatory `V3f+V3a` to zero leaves Trot intact.

---

## 2. Certified Pure-$\mathbb{Q}$ Theorems (`verify_ratncap_cone_gait.py`, `0` Floats)

### 2.1 `G1` (`W15-OBS-3`) — Antagonistic Cone Bijection, Hessian Saddle Elimination & Elastic Conservation

For fixed mechanical spring poles $k_{\mathrm{ext}} = 7/2, k_{\mathrm{flx}} = 5/2 > 0$ and pole angles $q_{\mathrm{flx}} = -3/4 < q_{\mathrm{ext}} = 5/4$:
- **Exact Cone Bijection (`8/8` boundary + interior samples, `32/32` torque identities):**
  $$\Phi(a_{\mathrm{ext}}, a_{\mathrm{flx}}) = \left(K_{\mathrm{eff}},\; q_{\mathrm{eq}}\right) = \left(a_{\mathrm{ext}} k_{\mathrm{ext}} + a_{\mathrm{flx}} k_{\mathrm{flx}},\;\; \frac{a_{\mathrm{ext}} k_{\mathrm{ext}} q_{\mathrm{ext}} + a_{\mathrm{flx}} k_{\mathrm{flx}} q_{\mathrm{flx}}}{K_{\mathrm{eff}}}\right)$$
  is an exact rational bijection between the punctured nonnegative cone $\mathbb{Q}_{\ge 0}^2 \setminus \{(0,0)\}$ and $(K_{\mathrm{eff}} > 0,\; q_{\mathrm{eq}} \in [q_{\mathrm{flx}}, q_{\mathrm{ext}}])$, with exact rational inverse
  $$a_{\mathrm{ext}} = \frac{K_{\mathrm{eff}}(q_{\mathrm{eq}} - q_{\mathrm{flx}})}{k_{\mathrm{ext}}(q_{\mathrm{ext}} - q_{\mathrm{flx}})},\qquad a_{\mathrm{flx}} = \frac{K_{\mathrm{eff}}(q_{\mathrm{ext}} - q_{\mathrm{eq}})}{k_{\mathrm{flx}}(q_{\mathrm{ext}} - q_{\mathrm{flx}})},$$
  and exact torque equivalence $\tau(a_{\mathrm{ext}}, a_{\mathrm{flx}}; q) \equiv K_{\mathrm{eff}}(q_{\mathrm{eq}} - q)$.
- **Zero Hessian vs. Indefinite Bilinear Position-Stiffness Saddle:**
  - Antagonistic control $\tau_{\mathrm{ant}}(a_{\mathrm{ext}}, a_{\mathrm{flx}}; q)$ is strictly affine in $(a_{\mathrm{ext}}, a_{\mathrm{flx}})$: midpoint Jensen defect = **`0/1`** identically ($H_{\mathrm{ant}} \equiv 0$).
  - Explicit position-stiffness control $\tau_{\mathrm{ps}}(k_{\mathrm{eq}}, q_{\mathrm{eq}}; q) = k_{\mathrm{eq}}(q_{\mathrm{eq}} - q)$ has indefinite saddle Hessian $H_{\mathrm{ps}} = \bigl(\begin{smallmatrix} 0 & 1 \\ 1 & 0 \end{smallmatrix}\bigr)$ (derived via exact rational 2nd-order central finite differences!) with **$\det H_{\mathrm{ps}} = -1/1$**, real symmetric Sylvester inertia **`[1, 1, 0]`** (exported in `position_stiffness_hessian_inertia`), and exact midpoint defect $-\frac{1}{4}(k_1 - k_2)(q_1 - q_2) =$ **`-1/1`** on $(k_1, q_1)=(2,-1/2),\;(k_2, q_2)=(6,1/2)$.
- **Exact Passive Elastic Energy Return:** For co-activation $(1, 1)$ ($K_{\mathrm{eff}} = 6, q_{\mathrm{eq}} = 5/12$) deflected by $\Delta q = -1/2$ during stance braking and rebounding back:
  $$\Delta W_{\mathrm{store}} = -\frac{3}{4} < 0\;\text{(braking absorption)}, \qquad \Delta W_{\mathrm{return}} = +\frac{3}{4} > 0\;\text{(propulsive return)}, \qquad \Delta W_{\mathrm{cycle}} = \frac{0}{1}.$$

### 2.2 `G2` (`W15-OBS-4`) — Commissural `V0/V3` $\mathbb{Z}_2$ Gait Symmetry-Breaking `⦺` Bifurcation

- **1D Interlimb Phase Potential ($V(\phi) = (k w_{V0} - w_{V3})\cos\phi$, $w_{V0} = 4, w_{V3} = 1 \implies k_{\mathrm{crit}} = 1/4$):**
  - Intact ($k = 1$): $\kappa_{\mathrm{Trot}} = +3/1 > 0$ (`⦺_- = 0`, **Trot stable**), $\kappa_{\mathrm{Bound}} = -3/1 < 0$ (`⦺_- = 1`, Bound unstable).
  - Exact critical threshold ($k = k_{\mathrm{crit}} = 1/4$): $\kappa_{\mathrm{Trot}} = \kappa_{\mathrm{Bound}} = 0/1$.
  - `V0` knockout ($k = 0$): $\kappa_{\mathrm{Trot}} = -1/1 < 0$ (`⦺_- = 1`, Trot unstable), $\kappa_{\mathrm{Bound}} = +1/1 > 0$ (`⦺_- = 0`, **Bound stable**).
  - **`V3` Ablation Theorem (Fig. 7C):** Ablating $w_{V3}: 1 \to 0$ raises Trot restoring curvature from `3/1` to `4/1` (exact gain **`+1/1 = +w_{V3} > 0`**).
- **4-Limb Quadruped $T^4 / S^1$ Exact $3\times 3$ Reduced Hessian & Rational Congruence (Real Symmetric Sylvester) Inertia (`w_side = 1/2, w_diag = 1/4`, $k_{\mathrm{crit}, 4D} = (w_{V3}-w_{\mathrm{diag}})/w_{V0} = 3/16$, $c_{\mathrm{crit},4D} = k_{\mathrm{crit},4D} w_{V0} - w_{V3} = -1/4$):**

| Regime ($w_{V0}=4, w_{V3}=1, w_{\mathrm{side}}=1/2, w_{\mathrm{diag}}=1/4$) | `⦺(H_Trot)` (`pos, neg, zero`) | `⦺(H_Bound)` (`pos, neg, zero`) | Stable Gait |
| :--- | :---: | :---: | :--- |
| Intact (`k = 1`, $c = 3$) | **`[3, 0, 0]`** | `[1, 2, 0]` | **Trot** |
| Critical (`k = 3/16`, $c = -1/4$) | `[2, 0, 1]` | `[2, 0, 1]` | Bifurcation |
| `V0` Knockout (`k = 0`, $c = -1$) | `[1, 2, 0]` | **`[3, 0, 0]`** | **Bound** |
| `V3` Knockout (`k = 1, w_V3 = 0`, $c = 4$) | **`[3, 0, 0]`** (`tr +3/1`) | `[1, 2, 0]` | **Trot (stronger!)** |

### 2.3 `G3` — `HoloSphere` Antagonistic Dual-Pole Gate Transfer

Replacing unconstrained multiplicative gating with nonnegative antagonistic pole pulls $x' = x + g_+(u_+ - x) + g_-(u_- - x)$ ($g_+, g_- \ge 0,\; g_+ + g_- \le 1$):
- **Exact Contractive Damping (`5/5` gate pairs):** $\lambda_{\mathrm{eff}} = 1 - (g_+ + g_-) \in [0, 1]$ satisfies $\|x'_1 - x'_2\|_2^2 \equiv \lambda_{\mathrm{eff}}^2 \|x_1 - x_2\|_2^2 \le \|x_1 - x_2\|_2^2$ identically over $\mathbb{Q}$.
- **Smooth Convex-Hull & Unit-Ball Invariance (`5/5` pairs):** Coordinate-wise $\min(x_i, u_{+,i}, u_{-,i}) \le x'_i \le \max(x_i, u_{+,i}, u_{-,i})$ and $\|x'\|_2^2 \le 1$ whenever $\|x\|_2^2, \|u_+\|_2^2, \|u_-\|_2^2 \le 1$, with smooth affine Jacobian (no hard-clipping dead zone) and exact cone equivalence $x' = (1 - K_{\mathrm{gate}})x + K_{\mathrm{gate}} u_{\mathrm{eq}}$.
- **Negative Control (Unconstrained Over-Gating):** At $(g_+, g_-) = (3/2, 1)$, $\lambda_{\mathrm{eff}} = -3/2$, pairwise distance expands by **`9/4` (`2.25×`)**, and $\|x'_1\|_2^2 > 1$ escapes the unit ball $B^4$.

---

## 3. Scope & Honest Limitations (Aletheia Law 4)

- This track certifies the exact algebraic, Hessian, conservation, Krein-inertia, and gate-contraction structure of the `Rat NCAP` neuromechanical and commissural abstractions over $\mathbb{Q}$. It does **not** simulate 38-DOF MuJoCo rigid-body contact dynamics, muscle force-velocity Hill curves, or full ARS RL policy training (`arXiv:2611.23364v1` §5 notes rigid-body compliance and parameter unidentifiability limitations).

---

## 4. Artifact SHA-256 Manifest (`0644`, `PYC=0, ELF=0, WEIGHTS=0`)

| File | SHA-256 |
| :--- | :--- |
| `verify_ratncap_cone_gait.py` | `a2cabfa25e638edda3a08a3001fb28fa9e0863569ce1fff32cd4b32a632e63ba` |
| `test_ratncap_cone_gait_r5.py` | `10d90a9f4e390f2b8fae9512f1e5f865d311cd5b3fb7d458cd46886e06c30a98` |
| `s127_ratncap_cone_gait_certificate.json` | `15ea0d8b755a390488d4a8ea87ef48f782fdacdf320179751fe72fd53c480793` |
