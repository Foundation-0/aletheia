# Preregistration Amendment 1 (`PREREG-S107-S108-AMENDMENT1-COUNCIL-HARDENING`: Pre-GPU Lie-Algebra, Geometry, `H-Net` & `CS-08` Repairs)

- **Status:** `LOCKED_PREREGISTRATION_AMENDMENT_1` *(2026-11-25; parent protocols `PREREG-S107` SHA `6e197152...` and `PREREG-S108` SHA `f0343be8...` remain 100% immutable and unmutated)*
- **Source Pre-Flight Audits (Unanimous 3-Family Consensus, `#2818`):**
  1. `verification/reports/COLLAB-INKLING2-S107-S108-LOOP-PREFLIGHT.md` (`REVISE_BEFORE_GPU`)
  2. `verification/reports/COLLAB-CLAUDE-S107-S108-CS08-PREFLIGHT.md` (`AMEND_BEFORE_GPU`; `H7b` & `H8c-P3` = `BLOCK_INVALID_DESIGN`)
  3. `verification/reports/COLLAB-GROK47-S107-S108-MATH-PREFLIGHT.md` (`NEEDS_THEORY_AMENDMENT`)

All 6 unanimous pre-GPU repairs below are **mandatory overrides** before ANY RTX 3080 execution of `EXP-Q08a..c` or `EXP-Q09a..c`:

---

## 1. `H7b` Complete Redesign (`BLOCK_INVALID_DESIGN` Closure — True Path-Ordered $SU(2)$ Holonomy vs. Abelian `LieRE`)
- **Algebraic Obstructions Proven Unanimously:**
  1. Fixed-axis left $SU(2)$ (`Quat-SU2-Rel`) is unitarily conjugate to $\mathrm{diag}(R_\phi, R_\phi)$ — **Abelian tied-frequency 4D RoPE** (contained in `LieRE`, strictly `N0`), NOT non-Abelian!
  2. Right-multiplied depth phase $R(e^{i\tau_\ell})$ **commutes identically** with left sequence multiplication ($[L_u, R_r] = 0$, zero BCH term!) AND **cancels identically out of every intra-layer QK inner product** ($\langle Qr, Kr\rangle = \operatorname{Re}(\bar r \bar Q K r) = \langle Q, K\rangle$)!
  3. Static non-commuting products $U(t)$ break exact shift-relativity via $(n^2-m^2)[A,B]$ leakage.
- **Mandatory Repaired `H7b` Formulation:** Retract `Quat-SU2-Rel` and right-multiplied $R(e^{i\tau_\ell})$ permanently! Replace `H7b` with a clean test of **Data-Dependent Path-Ordered $SU(2)$ Holonomy** (cumulative quaternionic state transport $U(t) = \prod_{s \le t} \exp(\Omega(x_s)) \in SU(2)$ — genuinely non-Abelian, associative parallel scan!) head-to-head against (a) standard 2D RoPE, (b) `LieRE` / tied-frequency 4D Abelian RoPE (`N0` anchor), and (c) `Block4-RandOrtho` on non-Abelian group-word tracking ($S_3$/$A_5$) & language BPB!

## 2. `H7a` Differential-Geometry & Control Precision
- **Precision Correction:** Round $S^3$ has constant intrinsic sectional curvature $+1$ everywhere; $1/\sin^2\psi = 1 + \cot^2\psi$ is the **extrinsic curvature of latitude $S^2(\sin\psi)$ slices**. The clamped $2:1$ schedules $a(1+\cos^2\psi_\ell)$ and $a(1+\sin^2\psi_\ell)$ test depth-ordered width multisets (not intrinsic $S^3$ curvature blowup).
- **Mandatory Control Addition:** Permute **both** the polar AND equatorial width multisets in `S3-Permuted` (`S3-Permuted-Pol` and `S3-Permuted-Eq`), and match exact total parameters AND training/inference FLOPs (`±1%`).

## 3. `H7c` Loop Clock, KV-Cache, & Iso-Param/Iso-FLOP Fixes (`COLLAB-INKLING2` & `COLLAB-CLAUDE`)
- Enforce strict **9 `<5 min` CPU sanity gates** before GPU training: verify non-degenerate Hopf clock coupling (must apply *between* consecutive loop passes on hidden state $h^{(r)}$ rather than cancelling in QK!), pin exact KV-cache sharing vs. per-pass KV policy across `FlatLoop-Std`, `SphereLoop-NoClock`, and `CliffordTorus-HopfLoop`, and match BOTH `P_physical` (among looped arms) AND `F_train_total` / `F_infer` (`±5%`) against `Unlooped-16L`.

## 4. `H8a` Kronecker Scale-Gauge Collapse Repair
- **Obstruction Proven:** Pre-norm `[A_r ⊗ B_p; A_r; B_p]` restores positive cosine ONLY at fixed block norms; letting $\|B_p\| \to \infty$ drives normalized cosine back to `0` (recovering `S104 Thm 8` annihilation!), and a dense post-projection can zero the side blocks. Furthermore, `C_row(E) = 1` holds trivially for ANY row-normalized table and is NOT hybrid-specific.
- **Mandatory Repair:** Normalize each factor separately ($\|A_r\|_2 = \|B_p\|_2 = 1$) with **fixed positive block weights** $(\gamma_k, \gamma_a, \gamma_b)$ summing $\gamma_k^2 + \gamma_a^2 + \gamma_b^2 = 1$, enforce block-structured projection (preventing side-block zeroing), and retract `C_row=1` as a hybrid-only advantage.

## 5. `H8b` `H-Net` Equivalence, Divergent $\arccos$ Gradient & Byte-Context Parity
- **Obstruction Proven:** $\theta_t = \arccos\langle u_t, u_{t-1}\rangle$ is **step length** (NOT geodesic curvature), is strictly monotone-equivalent to **`H-Net`'s cosine routing $1 - \langle u_t, u_{t-1}\rangle$**, and suffers divergent gradient $d\arccos/dc \to -\infty$ as $c \to 1$.
- **Mandatory Repair:**
  1. Drop $\arccos$ backprop immediately; use smooth cosine step distance $s_t = 1 - \langle u_t, u_{t-1}\rangle$ as an explicit **`H-Net` (`N0`) control arm** alongside `BLT-Entropy`!
  2. To test genuine **second-order discrete geodesic curvature** beyond `H-Net`, define the turning metric on **consecutive tangent displacements** $v_t = \operatorname{Norm}(u_t - \langle u_t, u_{t-1}\rangle u_{t-1})$, $c_t = 1 - \langle v_t, v_{t-1}\rangle$ (bounded smooth gradient everywhere!), and require beating `H-Net` cosine routing by $\ge 2$ SE!
  3. Match **identical raw UTF-8 byte context windows** across BPE and byte-patching arms (preventing BPE from seeing `4×` more bytes per training window!).

## 6. `H8c` Part 3 (`BLOCK_INVALID_DESIGN` Closure — Unconfounded `nullmodem` Evaluation)
- Enforce identical underlying models, identical training compute, identical bit budgets (`wire_bits` counting framing + hash + quantized sphere payload), and an **independent frozen judge/probe** across English JSON, `ABIOS/3`, and `NullModem-SphereCell` so zero arm-specific readout confound contaminates the `0.4272` gauge-gap measurement!
