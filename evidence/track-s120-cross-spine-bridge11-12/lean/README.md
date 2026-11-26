# Track S120 Pure-`Init` Lean 4.36.0 Formalization: `BRIDGE_11` (`#49`) & `BRIDGE_12` (`#50`)

Machine-checked Pure-`Init` `Lean 4.36.0` proofs of Track `S120`'s two exact cross-spine operator bridges (`BRIDGE_11` and `BRIDGE_12`), advancing the verified `Project HoloSphere` / Cave Expedition theorem library from **`49/49` to `51/51`** (`0` external imports, `0` Mathlib, `0` IEEE-754 floats, `0` `Classical.choice`, `0` `Lean.ofReduceBool` / `native_decide`, `0` `sorryAx`, `0` warnings).

## Public Theorems (`HoloSphereCrossSpineBridges.lean`)

1. **`p49_bridge11_bent4_u4_symplectic_and_flat_wht` (`#49` — `BRIDGE_11`):**
   - Bit-exact identity between Maiorana–McFarland $q(x) = (x_0 \land x_2) \oplus (x_1 \land x_3)$ and `S117` hardware `popcount((lane & 3) & ((lane >> 2) & 3)) & 1` (`16/16`).
   - Exact symplectic polarization $q(x \oplus y) \oplus q(x) \oplus q(y) = B(x, y)$ (`256/256`), alternating $B(x, x) = \mathrm{false}$, and non-degenerate radical $\{x \mid \forall y,\, B(x,y)=\mathrm{false}\} = \{0\}$.
   - Exact group isomorphism $\mathrm{Heis}_2(\mathbb{F}_2) \xrightarrow{\sim} \mathcal{H} \subset U_4(\mathbb{F}_2)$ (`32` distinct unipotent matrices, `1,024/1,024` homomorphism products, `32/32` inverses $M(x, s)^{-1} = M(x, s \oplus q(x))$, and `1,024/1,024` commutators $[M(x, s), M(y, t)] = I_4 + B(x, y) E_{0,3}$).
   - Exact `Portal 78` `M3` (`vp-vnp` `Lem F.2`) associated graded shear Lie bracket $[\mathrm{gr}(x), \mathrm{gr}(y)] = B(x, y) E_{0,3}$ (`256/256`) and exact $4 \times 4$ integer Weyl–Pauli commutation $P(x) P(y) = (-1)^{B(x, y)} P(y) P(x)$ (`256/256`).
   - Exact self-dual flat Walsh–Hadamard spectrum $W_q(u) = 4(-1)^{q(u)}$ (`16/16`).
   - Exact $\ker\pi = 2\mathbb{Z}^{16}$ carry-cover seam & `BRIDGE_03` cross-term $(z + 2k)^2 - (z^2 + 4k^2) = 4zk$: mod-2 lift invariance $q(x + 2y) \bmod 2 = q(x)$ (`256/256`), contrasted against all `48` upper-nibble faults $2^p e_j$ ($p \in \{1,2,3\}, j \in \{0..15\}$) on codeword `0x000F` where LSB-only `A_16` SECDED sees syndrome `0` (`0/48`), integer $H_{16}$ shifts by exact Parseval energy $16 \cdot 4^p$ (`48/48`), and bit-plane-rotated SECDED locates exact lane $j$ (`48/48`).
2. **`p50_bridge12_nonscalar_krein_holonomy_order_split` (`#50` — `BRIDGE_12`):**
   - Universal quadratic-form congruence conservation $\mathrm{quadForm}_3(P^\top M P, v) = \mathrm{quadForm}_3(M, P v)$ for all $P, M \in M_3(\mathbb{Z})$ and $v \in \mathbb{Z}^3$.
   - **Exact Scalar Blindness ($G = I_3$):** For both cyclic $U_{\mathrm{cyc}} = (0\;1\;2)$ and `S119` $\rho(g_\beta) \in SO(3, \mathbb{Z})$ with $L_5 = \mathrm{diag}(3, 6, 3)$, $25 I_3 - (U L_5)^\top (U L_5)$ and $25 I_3 - (L_5 U)^\top (L_5 U)$ share identical characteristic polynomial `(21, -96, -2816)`, explicit orthogonal congruence, and identical diagonal inertia `(2, 1, 0) == (2, 1, 0)`.
   - **Exact Non-Scalar Order Split ($G_3 = \mathrm{diag}(3, 1, 1)$ & $G_{114} = \mathrm{diag}(1, 1, 4)$):** $M_{\mathrm{UL}}(G_3) = \mathrm{diag}(66, -83, 16)$ has inertia `(2, 1, 0)` ($n_- = 1$) while $M_{\mathrm{LU}}(G_3) = \mathrm{diag}(66, -2, -11)$ has inertia `(1, 2, 0)` ($n_- = 2$), together with a **universal bi-directional Sylvester non-congruence proof** showing that for **all** $P \in M_3(\mathbb{Z})$ and $c_1, c_2 > 0$, $c_1 P^\top M_{\mathrm{UL}}(G_3) P \ne c_2 M_{\mathrm{LU}}(G_3)$ and $c_1 P^\top M_{\mathrm{LU}}(G_3) P \ne c_2 M_{\mathrm{UL}}(G_3)$.
   - **Universal 4th-Block Holonomy Separator $h(\Delta U) = 3 - (2 q_0)^2$:** Over all unit integer quaternions $q \in \mathrm{QuatZ}$ ($\|q\|^2 = 1$), $h(-q) = h(q)$, $h(q) \ne 0$, and $h(q) < 0 \iff q \in \{\pm I\}$; across all `120` scale-`4` elements of $2I \subset SU(2)$ over $\mathbb{Z}[\sqrt{5}]$, exact `2 / 0 / 118` neg/zero/pos trichotomy (`-16` on $\{\pm I_4\}$ vs $\ge 24 - 8\sqrt{5} > 0$ attained at $\tilde{\tau}_0 \in \mathcal{C}_{10}^+$) and `120/120` $h(-Q) = h(Q)$.

## Verification Commands

```bash
CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -I -B verify_s120_lean_r5.py --verify-lean
CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -I -B verify_s120_lean_r5.py -v
```
