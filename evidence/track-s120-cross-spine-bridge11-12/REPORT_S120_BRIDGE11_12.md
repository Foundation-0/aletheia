# Track S120: Exact Pure-$\mathbb{Z}/\mathbb{Q}/\mathbb{Q}(\sqrt{5})$ Cross-Spine Operator Bridges `BRIDGE_11` & `BRIDGE_12`

**Track:** `S120` (CPU-only pure-$\mathbb{Z}/\mathbb{Q}/\mathbb{Q}(\sqrt{5})$ verification; `0` floats, `0` RNG, `0` GPU touch, `0` external dependencies)  
**Target Directory:** `track-s120-cross-spine-bridge11-12/`  
**Schema Version:** `aletheia.s120_bridge11_12_certificate.v1`  
**Canonical Certificate `payload_sha256`:** `ad8f57e0d5aeae5fbaf7a5703f63954a66ae10ef5d019e62fc2ff6aa7ab9e0c0`

---

## Executive Summary

Track `S120` proves, constructs, and adversarially verifies two exact cross-spine operator bridges ready for integration into `cartography/UNIFIED_OPERATOR_ATLAS.md` (without touching `cartography/verify_unified_atlas.py`):

1. **`BRIDGE_11` (`Portal 78` `M3` `vp-vnp` `Lem F.2` $\longleftrightarrow$ `Track S117` `H_256 × bent4` & `[16, 11, 4]` `A_16` SECDED + `BRIDGE_03` Carry-Cover Seam):**
   - Proves over exact $\mathbb{F}_2^4$ and $\mathbb{Z}$ that the Maiorana–McFarland quadratic form $q(x) = x_1 x_3 \oplus x_2 x_4$ realizing `S117`'s `bent4(lane)` has exact polar symplectic form $B(x, y) = q(x \oplus y) \oplus q(x) \oplus q(y) = x_1 y_3 \oplus x_3 y_1 \oplus x_2 y_4 \oplus x_4 y_2 \pmod 2$ (`256/256` exact, alternating, radical size `1`).
   - Constructs an **exact group isomorphism** $\Phi: \mathrm{Heis}_2(\mathbb{F}_2) \xrightarrow{\sim} \mathcal{H} \subset U_4(\mathbb{F}_2)$ (order `32`, `1,024/1,024` products) whose group commutator $[M(x,s), M(y,t)] = I + B(x,y) E_{0,3}$ (`1,024/1,024`), associated graded `M3` rank-1 shear Lie bracket $[\sum x_i G_i, \sum y_j G_j] = B(x,y) E_{0,3}$ (`256/256`), and exact 4×4 integer Weyl–Pauli commutator $P(x)P(y) = (-1)^{B(x,y)} P(y)P(x)$ (`256/256`) are **algebraically identical**.
   - Verifies exact self-dual flat Walsh–Hadamard spectrum $W_q(u) = 4(-1)^{q(u)}$ (`16/16`), exact `256×256` `H_256 × bent4` orthogonality (`32,640/32,640` zero off-diagonals), and **`0/2,048` constant warps** (`max |warp_sum| = 8`) vs **`64/2,048` constant warps** (`max |warp_sum| = 32`) for raw `H_256` without `bent4`.
   - Proves the **`[16, 11, 4]` `A_16` SECDED Carry-Cover Theorem & Explicit `BRIDGE_03` Obstruction ($\ker\pi = 2\mathbb{Z}^{16}$):** `2,048` codewords, `32,768/32,768` SEC, `120/120` weight-2 DED, `256/256` signed mod-2 lift invariance $(-1)^{q(x+2y)} = (-1)^{q(x)}$, contrasted explicitly against the `ker(pi) = 2Z^{16}` carry seam where `LSB-only SECDED` detects **`0/48`** upper-nibble faults ($b \in \{1,2,3\}$) while integer `H_16` shifts on **`48/48`** (`||H_16(z + 2^b e_j) - H_16(z)||_2^2 = 16 \cdot 4^b`), and bit-plane-rotated SECDED (`pi_b(z) = (z >> b) & 1`) recovers **`48/48` (`100%`)**.
2. **`BRIDGE_12` (Spine I `⦺` Krein Inertia `OP3_F3` $\longleftrightarrow$ Spine IV `⦷` Non-Abelian `SU(2)` Holonomy — Detector $K_t$):**
   - Proves constructively by exact $\mathbb{Q}(\sqrt{5})$ Gaussian elimination on $\mathrm{Sym}_3(\mathbb{Q}(\sqrt{5}))$ that the Schur commutant of $\rho(2I) \subset SO(3)$ has **`rank = 5/6 -> nullity = 1 = span{I_3}`**.
   - Cross-checks **two independent exact zero-float inertia engines** (Descartes real-root charpoly == Sylvester symmetric congruence $LDL^\top$) to prove:
     - **Scalar Blindness ($G = I_3$):** `charpoly(M_UL) == charpoly(M_LU)` and inertia `(2, 1, 0) == (2, 1, 0)` across all `4/4` rotations (`U_cyc = (0 1 2)` + Track `S119` generators $\rho(\tilde{\tau}_0), \rho(g_\alpha), \rho(g_\beta)$).
     - **Canonical $\mathbb{Q}$ Order Separation (`G_3 = diag(3, 1, 1)`, `L = diag(3/5, 6/5, 3/5)`):** Both `U_cyc` and `rho(g_beta)` exhibit an exact integer Krein signature jump **`n_-(UL) = 1 -> n_-(LU) = 2`**.
     - **Universal Anisotropic $\mathbb{Q}(\sqrt{5})$ Order Separation (`G_114 = diag(1, 1, 4)`):** Splits **ALL `4/4`** rotations simultaneously (`U_cyc`: `2 vs 1`, `rho(tau0)`: `1 vs 2`, `rho(g_alpha)`: `1 vs 2`, `rho(g_beta)`: `2 vs 1`).
     - **Exact 4th Scalar Holonomy Block $h(\Delta U) = 3 - |\operatorname{tr}(\Delta U)|^2$ on ALL `120` Elements of $2I$:** Strictly negative (`-1`) on the `2` central elements $\{\pm I\}$ (`FALSE = +I`) and strictly positive ($\ge \frac{3-\sqrt{5}}{2} = \phi^{-2} \approx +0.381966$) on ALL **`118/118` nontrivial elements** (`TRUE = +\tilde{\tau}_0`), while explicitly documenting its **Law-5 $\pm I$ sign-blindness boundary** (`h(-q) == h(q)` for `120/120` elements).

---

## 1. `BRIDGE_11`: `bent4` Symplectic Polar Form $\equiv$ `M3` `gr U_4(F_2)` Bracket & `A_16` Carry-Cover Seam

### 1.1 Exact Algebraic Isomorphisms (Zero Language Smuggling)

Writing $x = (x_1, x_2, x_3, x_4) \in \mathbb{F}_2^4$ with $x_{k+1} = (\text{lane} \gg k) \,\&\, 1$, the `S117` bit-exact phase is
$$q(x) = x_1 x_3 \oplus x_2 x_4 \in \mathbb{F}_2, \qquad \mathrm{bent4}(\text{lane}) = (-1)^{q(x)}.$$
Its exact polar bilinear form is
$$B(x, y) := q(x \oplus y) \oplus q(x) \oplus q(y) = x_1 y_3 \oplus x_3 y_1 \oplus x_2 y_4 \oplus x_4 y_2 \pmod 2.$$

Define the explicit `4×4` upper-triangular unipotent embedding $\Phi: \mathrm{Heis}_2(\mathbb{F}_2) \to U_4(\mathbb{F}_2)$ generated by `M3` (`Portal 78` `vp-vnp` `Lem F.2` / `Prop H.1`) rank-1 shears $I + E_{0,1}, I + E_{0,2}, I + E_{1,3}, I + E_{2,3}$ with central shear $I + E_{0,3}$:
$$M(x, s) = \begin{pmatrix} 1 & x_1 & x_2 & s \\ 0 & 1 & 0 & x_3 \\ 0 & 0 & 1 & x_4 \\ 0 & 0 & 0 & 1 \end{pmatrix} \in U_4(\mathbb{F}_2).$$
Direct matrix multiplication over $\mathbb{F}_2$ yields $M(x, s) M(y, t) = M(x \oplus y,\; s \oplus t \oplus x_1 y_3 \oplus x_2 y_4)$, whose commutator is identically $[M(x, s), M(y, t)] = I + B(x, y)\, E_{0, 3}$. Passing to the associated graded Lie algebra $\mathrm{gr}\,U_4(\mathbb{F}_2)$ with degree-1 shear generators $G_1 = E_{0,1}, G_2 = E_{0,2}, G_3 = E_{1,3}, G_4 = E_{2,3}$ yields $[\sum_i x_i G_i, \sum_j y_j G_j] = B(x, y)\, E_{0,3}$. Simultaneously, the exact 4×4 integer Weyl–Pauli matrices $P(x) = X_1^{x_1} X_2^{x_2} Z_1^{x_3} Z_2^{x_4} \in M_4(\{-1, 0, +1\})$ obey $P(x) P(y) = (-1)^{B(x, y)} P(y) P(x)$.

| `BRIDGE_11` Exact Algebraic Check | Verified Result |
|---|---|
| `S117` bit-exact match `q(lane) == popcount((lane&3)&((lane>>2)&3)) & 1` | `16 / 16` |
| Exact polarization $q(x \oplus y) \oplus q(x) \oplus q(y) == B(x, y)$ | `256 / 256` |
| Alternating ($B(x, x) = 0$) & non-degenerate radical size | `true`, `radical = 1` (`{0}`) |
| Group isomorphism $\Phi: \mathrm{Heis}_2(\mathbb{F}_2) \xrightarrow{\sim} \mathcal{H} \subset U_4(\mathbb{F}_2)$ | `32` unique matrices, `1,024 / 1,024` products, `32 / 32` inverses |
| Exact $U_4(\mathbb{F}_2)$ commutator $[M(x,s), M(y,t)] = I + B(x,y)E_{0,3}$ | `1,024 / 1,024` |
| Exact `M3` $\mathrm{gr}\,U_4(\mathbb{F}_2)$ shear Lie bracket $[\sum x_i G_i, \sum y_j G_j] = B(x,y)E_{0,3}$ | `256 / 256` |
| Exact 4×4 integer Weyl–Pauli commutator $P(x)P(y) = (-1)^{B(x,y)} P(y)P(x)$ | `256 / 256` |
| Self-dual flat Walsh–Hadamard spectrum $W_q(u) == 4(-1)^{q(u)}$ (`\|W_q(u)\| = 4`) | `16 / 16` (`100%` bent & self-dual) |
| `S117` `H_256 × bent4` exact `256×256` orthogonality | `256 / 256` diag (`4,128,768`), `32,640 / 32,640` zero off-diags |
| Constant warps across `2,048` byte-warp blocks (`H_256 × bent4` vs raw `H_256`) | **`0 / 2,048`** (`max \|sum\| = 8`) vs **`64 / 2,048`** (`max \|sum\| = 32`) |

### 1.2 `[16, 11, 4]` `A_16` SECDED Carry-Cover Theorem & Explicit `BRIDGE_03` Obstruction ($\ker\pi = 2\mathbb{Z}^{16}$)

Consider the canonical mod-2 reduction $\pi: \mathbb{Z}^{16} \to \mathbb{F}_2^{16}$ with $\ker\pi = 2\mathbb{Z}^{16}$ and the `S117` `[16, 11, 4]` extended Hamming syndrome map (`p0 = 0xFFFF`, `p1 = 0xAAAA`, `p2 = 0xCCCC`, `p3 = 0xF0F0`, `p4 = 0xFF00`):

- **Exact Quotient Factorization (`SECDED` + Signed Phases):**
  - `2,048` exact valid codewords (`2^{11}`), `32,768 / 32,768` exhaustive single-bit SEC (`(synd & 1) == 1` and `(synd >> 1) == j`), `120 / 120` weight-2 DED pairs (`synd != 0` and `(synd & 1) == 0`), and `32,768 / 32,768` $\mathbb{F}_2$-syndrome linearity checks.
  - Signed `bent4` phases factor cleanly through $\pi$: $(-1)^{q(x + 2y)} = (-1)^{q(x)}$ (`256 / 256` exact).
- **Explicit `BRIDGE_03` / Carry-Seam Non-Commutativity Obstruction (Law 5):**
  - In characteristic `2` (`BRIDGE_03`: `S22c`/`S40` Frobenius-Ducci $(a + b)^2 = a^2 + b^2$), cross-terms $2ab \in 2\mathbb{Z} = \ker\pi$ vanish identically. Over characteristic `0` (`Z`), integer `H_16`/`H_256` arithmetic retains $\ker\pi = 2\mathbb{Z}^{16}$ (e.g. for `base_codeword = 0x000f`, `(z_0 + 2)^2 - (z_0^2 + 4) = 4 != 0` in $\mathbb{Z}$ while `== 0 mod 2`).
  - **Concrete `48`-Fault Upper-Nibble Witness (`16` lanes × bits $b \in \{1, 2, 3\}$, $\delta = 2^b e_j \in \ker\pi$):**
    - `LSB-only A_16 SECDED` detects **`0 / 48`** faults (`syndrome == 0` identically, confirming the exact `0/48` `Vmin` carry-path blindspot of `S118` / Inquiry 1),
    - Integer `H_16` shifts on **`48 / 48`** faults with exact Parseval energy $\|H_{16}(z + 2^b e_j) - H_{16}(z)\|_2^2 = 16 \cdot 4^b > 0$ (`48 / 48`),
    - **Bit-plane-rotated SECDED (`pi_b(z) = (z >> b) & 1`)** detects and locates exact lane $j$ on **`48 / 48` (`100%`)** of upper-nibble faults.

---

## 2. `BRIDGE_12`: Non-Scalar Krein–Holonomy Phase Detector $K_t$ (Spine I `⦺` $\longleftrightarrow$ Spine IV `⦷`)

Define the unified $4 \times 4$ Krein–Holonomy operator over $\mathbb{K} \in \{\mathbb{Q},\, \mathbb{Q}(\sqrt{5})\}$:
$$K_t(U_t, L_t, \Delta U_t; G) = \operatorname{diag}\!\Big(G - (\rho(U_t) L_t)^\top G (\rho(U_t) L_t),\;\; 3 - |\operatorname{tr}(\Delta U_t)|^2\Big),$$
where $\rho: SU(2) \to SO(3)$ is the exact adjoint representation, $L_t$ is the local contraction/amplification matrix, and $G \succ 0$ is a symmetric positive-definite metric. Every $3 \times 3$ symmetric matrix inertia $(n_+, n_-, n_0)$ is verified by **two independent zero-float exact algorithms**: (A) exact Descartes real-root sign changes on $\det(\lambda I_3 - M)$ and (B) exact Sylvester congruence diagonalization $P^\top M P = D$ (`100%` agreement across all witnesses).

### 2.1 Exact Constructive Schur Commutant & Scalar Blindness Obstruction

1. **Constructive Schur's Lemma on $\mathrm{Sym}_3(\mathbb{Q}(\sqrt{5}))$:** Solving the exact linear system $U^\top G U - G = 0$ over $\mathbb{Q}(\sqrt{5})$ for the two `Track S119` generators $U \in \{\rho(\tilde{\tau}_0), \rho(g_\beta)\}$ yields **`rank = 5 / 6 -> nullity = 1`**, proving that $\operatorname{span}\{I_3\}$ is the **unique** $2I$-invariant symmetric metric.
2. **Exact Scalar Blindness ($G = I_3$):** Since $U^\top U = I_3$,
   $$I_3 - (U L)^\top (U L) = I_3 - L^\top L, \qquad I_3 - (L U)^\top (L U) = U^\top (I_3 - L^\top L) U.$$
   Thus $M_{\mathrm{LU}}(I_3)$ and $M_{\mathrm{UL}}(I_3)$ are orthogonally congruent with **identical characteristic polynomial** and identical inertia for **every** $U \in O(3)$ and $L$.

### 2.2 Exact Non-Scalar Order Separation Across $\mathbb{Q}$ and `S119` $2I \subset SU(2)$ over $\mathbb{Q}(\sqrt{5})$

With $L = \operatorname{diag}(\frac{3}{5}, \frac{6}{5}, \frac{3}{5})$, canonical metric $G_3 = \operatorname{diag}(3, 1, 1)$, and universal anisotropic metric $G_{114} = \operatorname{diag}(1, 1, 4)$:

| Rotation $U \in SO(3)$ | Exact $SO(3)$ & Dual-Inertia Match | Scalar $I_3$ (`UL` vs `LU`) | Canonical $G_3 = \mathrm{diag}(3,1,1)$ (`UL` vs `LU`) | Universal $G_{114} = \mathrm{diag}(1,1,4)$ (`UL` vs `LU`) |
|---|---|---|---|---|
| `U_cyc_012` $= (0\;1\;2)$ (exact $\mathbb{Q}$) | `true` (`Descartes == Sylvester`) | `(2,1,0)` vs `(2,1,0)` (blind) | **`(2,1,0)` vs `(1,2,0)` (`n_-: 1 -> 2`)** | **`(1,2,0)` vs `(2,1,0)` (`n_-: 2 -> 1`)** |
| `rho(tau0)` (`S119` $\mathcal{C}_{10}^+$ ord-5 in $SO(3)$) | `true` (`Descartes == Sylvester`) | `(2,1,0)` vs `(2,1,0)` (blind) | `(2,1,0)` vs `(2,1,0)` | **`(2,1,0)` vs `(1,2,0)` (`n_-: 1 -> 2`)** |
| `rho(g_alpha)` (`S119` acute conjugator) | `true` (`Descartes == Sylvester`) | `(2,1,0)` vs `(2,1,0)` (blind) | `(2,1,0)` vs `(2,1,0)` | **`(2,1,0)` vs `(1,2,0)` (`n_-: 1 -> 2`)** |
| `rho(g_beta)` (`S119` ord-3 conjugator) | `true` (`Descartes == Sylvester`) | `(2,1,0)` vs `(2,1,0)` (blind) | **`(2,1,0)` vs `(1,2,0)` (`n_-: 1 -> 2`)** | **`(1,2,0)` vs `(2,1,0)` (`n_-: 2 -> 1`)** |

### 2.3 Exact 4th Scalar Holonomy Block $h(\Delta U) = 3 - |\operatorname{tr}(\Delta U)|^2$ on All `120` Elements of $2I$

Exhaustive exact $\mathbb{Q}(\sqrt{5})$ evaluation across all `120` elements of $2I \subset SU(2)$ proves:
- **`h(q) = -1 < 0`** on the exact **`2` central elements** $\{\pm I\}$ (`Track S119` `FALSE = +I`),
- **`h(q) >= (3 - sqrt5)/2 = phi^{-2} ~= +0.381966 > 0`** on ALL **`118 / 118` nontrivial elements** of $2I \setminus \{\pm I\}$ (`0` zeros), with the exact minimum positive margin `(3/2 - 1/2*sqrt5)` attained on `Track S119`'s `TRUE = +\tilde{\tau}_0 \in \mathcal{C}_{10}^+`!
- **Explicit Law-5 Boundary ($\pm I$ Sign Blindness):** Because $|\operatorname{tr}(-q)|^2 = |\operatorname{tr}(q)|^2$ (`120 / 120` elements satisfy $h(-q) = h(q)$), the 4th block $h(\Delta U)$ is strictly an $SO(3) \cong A_5$ projective invariant and **cannot detect a spinor $-I$ sign flip alone** — establishing the exact complementarity with `Track S119`'s acute $\mathcal{C}_{10}^+$ sign-free closure theorem.
- **Full $4 \times 4$ Unified $K_t$ Inertia (`rho(tau0)`, `G_114`, `L = diag(3/5,6/5,3/5)`):**
  - `UL` + `FALSE (+I)`: `(2, 2, 0)` | `LU` + `FALSE (+I)`: `(1, 3, 0)` (`n_-: 2 -> 3`)
  - `UL` + `TRUE (+tau0)`: `(3, 1, 0)` | `LU` + `TRUE (+tau0)`: `(2, 2, 0)` (`n_-: 1 -> 2`)

---

## 3. Honest Law-4 Novelty Calibration (`CS-13`)

| Layer | Status | Scope & Attribution |
|---|---|---|
| Maiorana–McFarland bent quadratic forms, finite Heisenberg/Pauli symplectic polar forms, extended `[16, 11, 4]` Hamming SECDED, Frobenius characteristic-2 linearity | **`N0` (Prior Art)** | Classical coding theory & finite symplectic geometry (McFarland 1973; Rothaus 1976; Hamming 1950). |
| Orthogonal similarity invariance of $I - L^\top L$, Sylvester's Law of Inertia, Descartes' real-root sign rule, Schur's Lemma for $SO(3)$ irreps | **`N0` (Prior Art)** | Classical linear algebra & representation theory (Sylvester 1852; Schur 1905). |
| **`BRIDGE_11` Constructive Cross-Spine Certificate:** Explicit `4×4` $U_4(\mathbb{F}_2)$ shear isomorphism tying `Portal 78` `M3` (`vp-vnp` `Lem F.2`) to `S117`'s bit-exact `H_256 × bent4`, plus the **`[16, 11, 4]` `A_16` SECDED Carry-Cover & `BRIDGE_03` $\ker\pi = 2\mathbb{Z}^{16}$ Obstruction Theorem** (`0/48` LSB vs `48/48` integer `H_16` shift vs `48/48` rotated-plane recovery) | **`N1` / `N2`-Candidate (Constructive Cross-Spine Synthesis)** | Zero-float pure-$\mathbb{Z}$ machine-verified witness in `s120_bridge11_12_certifier.py` (`N2` promotion gated on external outside-observer ruling per `SOP`). |
| **`BRIDGE_12` Constructive Cross-Spine Certificate:** Exact $\mathbb{Q}(\sqrt{5})$ Schur-nullity proof + dual-method inertia separation across `S119`'s $2I \subset SU(2)$ generators + exact `2/118` spectral-gap sign separation of $3 - |\operatorname{tr}(\Delta U)|^2$ over all `120` elements of $2I$ (with explicit $\pm I$ boundary) | **`N1` (Constructive Cross-Spine Synthesis)** | Zero-float pure-$\mathbb{Q}/\mathbb{Q}(\sqrt{5})$ witness linking `S24`/`S37`/`OP3_F3` Krein inertia to `S116`/`S119` non-Abelian holonomy. |

---

## 4. `R1–R5` Verification, Mutation & Hygiene Receipts

| Artifact | Lines | SHA-256 |
|---|---:|---|
| `s120_bridge11_12_certifier.py` | `1,089` | `e70a3d072856ecf1afdcbd97632e1e519bd3e33ffd6698f7078ea75c2c7d9461` |
| `test_s120_bridge11_12_r5.py` | `225` | `2e59eb5e964732c3f52fc0be8c13ed3cf79859b02a32b933477b8a4ae8648970` |
| `lean/HoloSphereCrossSpineBridges.lean` | `1,113` | `2381dd26ca5c8411e5e8b427a820a50e277938b5c3e93f59d9e8143a8ab5b040` |

*(Complete `(path, lines, bytes, sha256)` manifest covering this report and all `lean/` files is pinned in [README.md](README.md).)*

- **Stock `/usr/bin/python3` 3-Mode `-I` Parity (`-I -B`, `-I -O -B`, `-I -B -W error`):**
  - `s120_bridge11_12_certifier.py`: **bit-identical stdout** (`0.72 s`, `payload_sha256 = ad8f57e0d5aeae5fbaf7a5703f63954a66ae10ef5d019e62fc2ff6aa7ab9e0c0`).
  - `test_s120_bridge11_12_r5.py`: **`0` stdout bytes**, exit code `0` across all 3 modes (`0` bare `assert`s).
- **Mutation Audit (`aletheia mutate --max-mutants 0 --guards require_ok`):**
  - **`27 / 27 KILLED` (`100.0%`, `survived = 0`, `truncated = false`, `verdict = PASS`)**.
- **Hygiene & Safety Gates:** Pure Python stdlib (`0` floats, `0` RNG, `0` bare `assert`s, `0` user-home path leaks, `0` CRLF, `0` `.pyc`/`__pycache__`), verified by dual external `aletheia audit-check --strict-ancestors --safety-scan --strict-unseeded`.
