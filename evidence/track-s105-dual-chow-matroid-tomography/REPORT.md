# Track S105 — Dual Chow Matroid Tomography: Independent Audit of `solved-conjectures#569`/`#597`, Exact Phase Transitions, MRD/Johnson Obstructions, and the 18.06× Smaller Affine Gabidulin Rank-5 Family

**Author:** `@claude-architect` · **Portals:** Caiolo–Ferroni–Hoster ([arXiv:2605.28474v1](https://arxiv.org/html/2605.28474v1), Conjecture 7.3 & Theorem 4.9), Cinna Davis's merged Lean 4.35 disproof (`1337isnot1337/solved-conjectures#569` @ `e39974c8`), Keith Adler's all-ranks supplement (`#597` @ `20571eb9`), and Bérczi–Coron–Eur–Li ([arXiv:2610.17135v1](https://arxiv.org/html/2610.17135v1), Proposition 3.11 & Sections 4.1–4.5) · **Scope:** CPU-only, `0` GPU touch, `0` GitHub pushes, `0` external repo clones inside `track-s105-*`, `PYTHONDONTWRITEBYTECODE=1`.

**Novelty (Law 4):** **`N1`** (`n2_claims = 0`). The underlying hyperplane coalescence / absorption machinery (BCEL Prop 3.11), Gabidulin MRD codes (Delsarte 1978 / Gabidulin 1985), dual Chow $\gamma$-expansion (CFH Thm 4.9), rank-5 `PG(7, q)` disproof (`#569`), and sharp rank threshold $r \le 4$ (`#597`) are prior art. Track S105 contributes:
1. A zero-shared-code flag-functional incidence-algebra audit verifying every sign from CFH Definitions 2.4/2.7/2.8/3.1 through Propositions 4.6–4.7 and Theorem 4.9 to `#569`'s `chowWeight`/`augmentedWeight` across ranks $r \in \{2, 3, 4, 5, 6\}$.
2. Exact Sturm-chain 3-way phase-transition tomography separating Bergman $h_{M_q}$, Dual Chow $H^*_{M_q}$/$F^*_{M_q}$, and Ordinary Chow $H_{M_q}$ across ranks $r \in \{5, 6, 7\}$.
3. Exact MRD-duality + Johnson-bound obstructions barring naive 2-cell $q = 16$ coalescence.
4. **The Affine Gabidulin Rank-$r$ Counterexample Family $A_{r,q}$ in $\mathrm{AG}(2r-4, q)$** — absent from CFH, BCEL, `solved-conjectures` (`main` + `origin/research`), and `RealRooted#1394` — which shrinks the minimal rank-5 counterexample ground set by **`18.06×`** (`|E(A_17)| = 24,142,482` vs `|E(M_17)| = 436,068,361`, with a degree-35 kernel-checked shifted discriminant certificate in pure-`Init` Lean 4.36.0) and shrinks ranks 6 and 7 by `12.10×` and `8.17×`.

---

## 1. Pillar 1 — Independent Audit of PR `#569` & Trust-Boundary Bridge (`CFH Def 3.1 ↔ Prop 4.6–4.7`)

- **Flag-Functional Incidence Algebra (zero shared code with `#569`):** Implementing CFH Def 2.4 (`H = -(\bar\kappa)^{-1}`), Def 2.7 (`F = H f^{\mathrm{rev}}`), Def 2.8 (`\chi = \mu \zeta^{\mathrm{rev}}`), and Def 3.1 (`\kappa^* = (\chi^{\mathrm{rev}})^{\mathrm{sgn}}`) directly on the universal graded-poset flag algebra confirms for ALL ranks $r \in \{2, 3, 4, 5, 6\}$ (`2 + 4 + 8 + 16 + 32 = 62` rank subsets):
  - $(\kappa^*)^{-1} = (\kappa^*)^{\mathrm{rev}}$ (kernel involution axiom);
  - $\kappa^* = (f^*)^{\mathrm{rev}} (f^*)^{-1}$ with $f^* = \mu^{\mathrm{sgn}}$ and $\deg f^*_{st} < \rho_{st}/2$ (right KLS);
  - Exact coefficientwise equality of Def-3.1 $H^*$/$F^*$ with CFH Thm 4.9 AND with `#569`'s `chowWeight`/`augmentedWeight`;
  - Exact coefficientwise equality of Def-2.4 ordinary Chow $H$ with the Feichtner–Yuzvinsky chain weight.
- **Honest Trust-Boundary Accounting (`#569` + `#597`):** PR `#569` (`CaioloFerroniHoster.lean` @ `243d002f`, `CaioloFerroniHosterArithmetic.lean` @ `13ec4ec9`) defines `matroidDualChow` directly via CFH Prop 4.6–4.7 chain weights without deriving Prop 4.6–4.7 from Def 3.1 inside its 9 modules. SOP-9 inspection confirmed that Keith Adler's merged supplement PR `#597` (`CaioloFerroniHosterRankBridge.lean` @ `e4569a01`, commit `20571eb9`) subsequently proved the kernel bridge (`dualChow_eq_kernel`, `dualAug_eq_kernel`) for all ranks in Lean, while `CaioloFerroniHoster.lean` itself does not import `RankBridge`.
- **Exact Replay of $M_q$ (`PG(7, q)`, $|E(M_q)| = [8]_q + q^4$):**
  - At $q = 16$ (`|E| = 286,396,689`): $\gamma_1^2 / (4 \gamma_0 \gamma_2) = 1.031916 > 1$ (`H*`), `1.031917 > 1` (`F*`).
  - At $q = 17$ (`|E| = 436,068,361`): $\gamma(H^*) = (1367432169863264385040621589,\; 677031173160167651396287043,\; 85823997163784007690567699)$, $\Delta_{H^*} = -11062769241414341239970603495681493737981374532130995 < 0$ (ratio `0.976434 < 1`); $\Delta_{F^*} = -11061733404916469626152098526056073213151599377977031 < 0$ (ratio `0.976437 < 1`).
  - Symbolic Taylor shift at $q = 17 + s$: both $-D_{H^*}(17+s)$ and $-D_{F^*}(17+s)$ (common denominator `576`) have degree **`43`**, leading coefficient **`4`**, and **all `44/44` coefficients strictly positive** (kernel-checked in Lean Theorems 20 & 21!).

## 2. Pillar 2 — Sharp Minimum Rank Theorem ($r = 5$ Sharp for $H^*_M$) & Rank-4 $F^*$ Frontier

- **Minimum Rank $r = 5$ Sharpness:** For any rank $r \le 4$ lattice with nonnegative flag $h$-vector ($\beta \ge 0$, including every matroid lattice), CFH Thm 4.9 gives $H^*_M(x)$ of $\gamma$-degree $\le 1$: at $r = 4$, $H^*_M(x) = g_0(1+x)^3 + g_1 x(1+x) = (1+x)(g_0 x^2 + (2g_0 + g_1)x + g_0)$, whose quadratic discriminant is $(2g_0 + g_1)^2 - 4g_0^2 = g_1(4g_0 + g_1) \ge 0$ unconditionally (Lean Theorems 12–14).
- **Rank-4 $F^*$ & Interlacing Frontier (`OPEN_NOT_FALSIFIED`):**
  - Rank-4 Gabidulin $G_{4,q}$: symbolic $F^*$ discriminant shifted at $q = 2 + s$ (deg 22) has **all coefficients strictly positive**, and the interlacing slack $\beta(12)(\beta(13)+\beta(23)) - \beta(123)\beta(2)$ shifted at $q = 2 + s$ (deg 20) has **all coefficients nonnegative**.
  - BCEL §4.1 Affine Klein (`14` odd prime powers up to `97`, min $F^*$ disc ratio `7.747765`, min interlacing ratio `2.004456`) and Affine Packing (`16` prime powers up to `81`, min $F^*$ disc ratio `10.765024`, min interlacing ratio `2.503212`): **`0` failures**.
  - `PG(3, q)`, `AG(3, q)` ($q \in [2, 19]$), uniform $U_{4, n}$ ($4 \le n \le 20$): all $F^*$ remain `4/4` real-rooted. Consistent with `RANKS.md`, rank-4 $F^*$ real-rootedness and interlacing remain open.

## 3. Pillar 3 — Exact 3-Way Real-Rootedness Phase Transition on $M_q$ (Exact Sturm Chains)

| $q$ | $|E(M_q)|$ | Bergman $h_{M_q}$ (`/4`) | Chain $f_{M_q}$ (`/4`) | Dual Chow $H^*_{M_q}$ (`/4`) | Dual Aug $F^*_{M_q}$ (`/5`) | Ordinary Chow $H_{M_q}$ (`/4`) |
|---:|---:|---:|---:|---:|---:|---:|
| `2..7` | `271..963,201` | `4/4` | `4/4` | `4/4` | `5/5` | **`4/4`** |
| **`8`** | **`2,400,841`** | **`2/4` (BREAKS)** | **`2/4`** | `4/4` | `5/5` | **`4/4`** |
| `9..16` | `5,387,401..286,396,689` | `2/4` | `2/4` | `4/4` | `5/5` | **`4/4`** |
| **`17`** | **`436,068,361`** | `2/4` | `2/4` | **`0/4` (BREAKS)** | **`1/5` (at `-1`)** | **`4/4`** |
| `19` | `943,661,601` | `2/4` | `2/4` | `0/4` | `1/5` | **`4/4`** |

Ordinary Chow $H_{M_q}(x)$ has $g_0(H) = 1$ (vs $g_0(H^*) = |\mu(\hat 0, \hat 1)| \sim q^{22}$) and stays **`4/4` real-rooted across ALL 12 tested prime powers $q \in [2, 19]$**, cleanly separating primal vs. dual Chow real-rootedness at minimal rank 5.

## 4. Pillar 4 — Higher-Rank Phase Boundary & Exact MRD-Duality / Johnson-Bound Obstructions

- **Higher-Rank Projective Gabidulin Thresholds (Sturm chains over $\mathbb{Q}$):**
  - **Rank 6 ($k=5$):** $H^*/F^*$ break at **$q = 11$** (`|E| = 2,593,903,511`, `1/5` and `2/6` real roots; Bergman breaks at $q = 7$; ordinary Chow stays `5/5`). At $q = 11$, $H^*$ fails the quadratic $\gamma$-discriminant $g_1^2 < 4 g_0 g_2$ while Newton log-concavity $g_1^2 \ge 2 g_0 g_2$ still holds!
  - **Rank 7 ($k=6$):** $H^*/F^*$ break at **$q = 7$** (`|E| = 2,306,998,849`, `2/6` and `3/7` real roots; ordinary Chow stays `6/6`). At **$q = 7$** (and $q = 8$), $H^*$ **fails the cubic $\gamma$-discriminant ($\Delta_{\mathrm{cubic}} < 0$) BEFORE Newton log-concavity** ($g_1^2 \ge 3 g_0 g_2$ and $g_2^2 \ge 3 g_1 g_3$ both hold)!
- **MRD-Duality Obstruction (`M_{4×4}(F_q)`):** The 12-dim min-rank-2 Gabidulin code $C$ has entrywise trace-orthogonal dual $C^\perp$ of dimension `4` and **minimum rank `4`** (exhaustively verified over $\mathbb{F}_2$, $\mathbb{F}_3$, $\mathbb{F}_5$, matching Delsarte's theorem $d(C^\perp) = 4 - 2 + 2 = 4$). Since every single-entry hyperplane $\{M_{i,j} = 0\}$ is dual to a rank-1 matrix $E_{i,j} \notin C^\perp$, **`dim(C ∩ {M[i,j] = 0}) = 11` for all 16 entries `(i,j)`** — barring naive 12-dim Cell-2 coalescence at $q = 16$.
- **Companion Johnson-Bound Obstruction:** In $\mathrm{PG}(7, q)$, one Gabidulin coset of $q^{12}$ 4-spaces leaves only $\binom{8}{3}_q - q^{12}[4]_q = q^{13} + 2q^{12} + 4q^{11} + \dots + 1$ uncovered 3-spaces (degree 13), packing at most $O(q^{10})$ additional 4-spaces per family — never the $q^{11}$ of a full second Schubert cell. The same holds in $\mathrm{AG}(6, q)$ ($\binom{6}{2}_q - q^6[3]_q = q^6 + 2q^5 + 3q^4 + \dots + 1$, packing at most $O(q^4)$ extra 3-spaces).

## 5. Pillar 5 — The 18.06× Smaller Affine Gabidulin Family $A_{r,q}$ in $\mathrm{AG}(2r-4, q)$ & BCEL Frontier

- **Construction ($r = 5$, $d = 6$):** Let $K = \mathbb{F}_{q^3}$, $V = K \oplus K \cong \mathbb{F}_q^6$, and start from $G = \mathrm{Tr}^2(\mathrm{AG}(6, q))$ (rank 5, $q^6$ points). Partition the $q^9$ graph 3-spaces $W_{a,u,v} = \{(t, ut + vt^q + at^{q^2}) : t \in K\}$ into $m = q^3$ Gabidulin cosets $\mathcal{S}_a$ (each of size $q^6$, pairwise linear intersection $\dim \le 1$). Lift every direction $W \in \mathcal{S}_a$ to all $q^3$ parallel affine translates $v_0 + W$, forming $q^6 \cdot q^3 = q^9$ blocks in each coset family $\mathcal{F}_a$ (`512` at $q=2$), so $b = q^{12}$ (`4,096`) is the total union across all $m = q^3$ cosets.
  - **BCEL Prop 3.11 verification:** Distinct translates of the same direction are disjoint (rank $0 \le 2$); distinct directions in $\mathcal{S}_a$ meet in $\dim \le 1$, so their translates meet in at most an affine line (rank $\le 2$ holding within each $\mathcal{F}_a$; cross-coset blocks meet in up to `4` points, harmless via distinct $e_a$). Both $N_4 - b$ and $N_{\mathrm{U}} = m N_3 - b q[3]_q$ have all Taylor coefficients at $q = 2 + s$ strictly positive.
  - **Exhaustive Finite Ground-Truth Check on $A_2$ (`|E| = 72`):** Constructed all `512` graph 3-spaces and all `4,096` blocks explicitly; checked all $\binom{512}{2} = 130,816$ block pairs in family $a=0$ (`max_intersection = 2` points $\implies$ rank $\le 2$); verified all `512 × 14 = 7,168` absorbed affine planes pairwise distinct; verified direct hyperplane count `W_4 = 97,246` equals the symbolic formula.
- **18.06× Smaller Counterexample at Minimal Rank 5 ($q \ge 17$):**
  - **Ground set:** $|E(A_{17})| = 17^6 + 17^3 = \mathbf{24,142,482}$ vs PR `#569`'s $436,068,361$ — exact ratio **`436068361 / 24142482 = 18.062284×`** (and Lean Theorem 24 proves $q^6 + q^3 < [8]_q + q^4$ for all $q \ge 2$!).
  - **Exact $q = 17$ witness:** $\gamma(H^*_{A_{17}}) = (15349600526709754544356,\; 7671555032664686456016,\; 971618705289721182159)$, $\Delta_{H^*} = -803079342701737648941812651155060982786160 < 0$ (ratio `0.986538 < 1` vs `1.043058 > 1` at $q = 16$); $\Delta_{F^*} = -801221140302196159085049505807058587771120 < 0$.
  - **Degree-35 universal certificate ($q \ge 17$):** Both $-D_{H^*}(17+s)$ and $-D_{F^*}(17+s)$ (common denominator `576`) have degree **`35`**, leading coefficient **`4`**, and **all `36/36` coefficients strictly positive** (kernel-checked in Lean Theorems 22 & 23!).
  - **Same 3-way transition at 9×–18× smaller $|E|$:** Bergman breaks at $q = 8$ (`|E| = 262,656`), $H^*/F^*$ break at $q = 17$ (`|E| = 24,142,482`, `0/4` and `1/5`), ordinary Chow stays `4/4` for all tested $q \in [2, 19]$.
  - **Higher-Rank Collapse:** Rank 6 ($q = 11$, $\mathrm{AG}(8, 11)$): **`214,373,522`** (`12.0999×` smaller, `1/5` & `2/6` real roots); Rank 7 ($q = 7$, $\mathrm{AG}(10, 7)$): **`282,492,056`** (`8.1666×` smaller, `2/6` & `3/7` real roots).
- **BCEL §4.3 Projective $\mathcal{C}(q, q^3)$ Frontier:** Spot-checked at $q \in \{3, 5, 17, 149\}$ (up to $|E| = 73.9\text{B}$): $H^*$ stays `6/6` and $F^*$ stays `7/7` real-rooted throughout (no leading-term cancellation in $(k-1,1)$ hyperplanes).

## 6. Pure-`Init` Lean 4.36.0 Companion — `DualChowMatroidTomography.lean`

Zero imports, zero Mathlib, zero `sorry`, zero warnings, `rc = 0` under scrubbed `lean --stdin`, all 24 named `#print axioms` theorems $\subseteq \{\text{propext}, \text{Quot.sound}\}$ (`0` `Classical.choice`). **Honest scope:** all statements are polynomial identities, Taylor-shift certificates, and integer inequalities over $\mathbb{Z}$ (the corresponding statements over $\mathbb{R}$ follow from the same sum-of-squares / Taylor-shift identities, which are NOT formalized over $\mathbb{R}$ here; the matroid flag enumeration is certified in the pure-$\mathbb{Z}/\mathbb{Q}$ oracle). `12` helper theorems (`36` total = `24` listed in `#print axioms` + `12` helpers) are not counted in the 24 primary theorems.

| # | Theorem | Exact Lean Statement (all universally quantified) |
|---|---|---|
| 1–5 | `evalP_{addP,scaleP,negP,mulP,shiftP}` | Horner `evalP` is a ring homomorphism and satisfies `evalP (shiftP p a) x = evalP p (x + a)` |
| 6–7 | `evalP_{nonneg,pos}_of_coeffs_{nonneg,pos}` | Nonnegative/positive coefficients imply `0 ≤ evalP p x` / `0 < evalP p x` for `0 ≤ x` |
| 8 | `neg_of_shifted_neg_coeffs_pos` | Positive coefficients of `shiftP (negP p) a` imply `∀ q ≥ a, evalP p q < 0` |
| 9 | `quad_pos_of_neg_disc` | `0 < a → b^2 < 4ac → ∀ x : Int, 0 < a*x^2 + b*x + c` |
| 10 | `dual_chow_quartic_pos` | `0 < g0 → g1^2 < 4*g0*g2 → ∀ x : Int, 0 < g0*(1+x)^4 + g1*x*(1+x)^2 + g2*x^2` |
| 11 | `dual_aug_quintic_root_only_neg_one` | `0 < h0 → h1^2 < 4*h0*h2 → (1+x)*(h0*(1+x)^4 + h1*x*(1+x)^2 + h2*x^2) = 0 → x = -1` |
| 12–14 | `rank_four_{factorization,disc_identity,disc_nonneg}` | Rank-4 $H^*$ factors as `(1+x)(g0*x^2 + (2g0+g1)x + g0)` with disc `g1*(4g0+g1) ≥ 0` for `g0, g1 ≥ 0` |
| 15 | `quartic_gamma_coeffs` | Exact monomial expansion `[g0, 4g0+g1, 6g0+2g1+g2, 4g0+g1, g0]` of the $\gamma$-quartic |
| 16 | `rank_six_only_root_neg_one` | `0 < g0 → g1^2 < 4*g0*g2 → g0*(1+x)^5 + g1*x*(1+x)^3 + g2*x^2*(1+x) = 0 → x = -1` |
| 17–19 | `gaussQ_{one_mul,eq_zero_of_lt,self}` | `(q - 1) * gaussQ q n 1 = q^n - 1`, `n < k → gaussQ q n k = 0`, `gaussQ q n n = 1` |
| 20–21 | `pr569_{Hstar,Fstar}_disc_neg_for_all_q_ge_17` | `∀ q : Int, 17 ≤ q → evalP pr569{Hstar,Fstar}Disc576 q < 0` (exact degree-43 `shiftFast` certificate) |
| 22–23 | `affine_gabidulin_{Hstar,Fstar}_disc_neg_for_all_q_ge_17` | `∀ q : Int, 17 ≤ q → evalP affineGab{Hstar,Fstar}Disc576 q < 0` (exact degree-35 `shiftFast` certificate) |
| 24 | `affine_gabidulin_strictly_smaller_ground_set` | `∀ q : Int, 2 ≤ q → q^6 + q^3 < gaussQ q 8 1 + q^4` |

## 7. Verification Receipts

All receipts below were recorded strictly post-last-edit on the frozen code, Lean, and certificate files (`0` skips, `0` GPU touch, `0` GitHub pushes, `PYTHONDONTWRITEBYTECODE=1`):

- **Canonical Certificate & Replay Parity:**
  - `payload_sha256`: `82682c2b4799b7ab050e6fc9f8bbae21cb068bca6153adece3d75af875ca1094`
  - `certificate_sha256` (envelope digest): `27a7bdd1022f308d83692d45ebb43bc6bb2f9ed6b6f5f3467d39c6db0959f419`
  - `verify_s105_dual_chow_matroid.py --standalone | cmp -s - s105_dual_chow_matroid_certificate.json`: **`EXACT`** (`18,608` bytes, mode `0o600`).
  - `verify_s105_dual_chow_matroid.py --verify-pins <solved-conjectures>`: **`PINS_OK external=8`** (`solved-conjectures @ c3f33dba2971f63b85a18345893acb36108ca97e`).
- **Live Lean `4.36.0` Kernel & R12 Static Pre-Filter:**
  - `DualChowMatroidTomography.lean` compiles with `rc = 0`, `0` warnings, `0` stderr under allowlist-scrubbed `lean --stdin`; all **`24/24`** named `#print axioms` theorems depend only on $\subseteq \{\text{propext}, \text{Quot.sound}\}$ (`0` `Classical.choice`, `0` `sorryAx`).
  - Static R12 pre-filter (defense-in-depth alongside mandatory live `lean --stdin` + `#print axioms`): **`18/18`** rule categories covered across `55` attack PoCs (including `Char := '"'` quote-desync, `r#"\"#`, `s!"x"`, `«"»`, `dbg_*`, `warn.sorry`, `terminalTacticsAsSorry`, `+native`, multiline `decide`, `config := { native }`, `@[export]`/`@[init]`/`@[builtin_init]`, `#guard_msgs`, `_root_.sorryAx`) and `9/9` clean controls (`0` FP). Because `strip_lean4_comments` strips only comments and `R01_STRING_OR_GUILLEMET` forbids `"` and `«»` anywhere outside comments, string/char quote-desync bypasses fail closed on `R01`.
  - **Live `Init.olean` Hijack Immunity:** Compiling a 3-line adversarial `Init.lean` into `Init.olean` and injecting `LEAN_PATH`, `LEAN_OPTS`, and `ELAN_TOOLCHAIN` causes raw `lean --stdin` to fail (`rc != 0`), while `verify_lean4_file_live` stays 100% immune (`24/24` verified) via allowlist `scrubbed_lean_env()`.
- **Exhaustive Every-Leaf Re-Signed Forgery Battery (`SEC` / `FR0` / `FR1`) & DoS Caps:**
  - **`746/746` leaves** (`1,492/1,492` single-leaf re-signed tamper rejections across `SEC` and `FR0`, **`0` bypasses**, **`0` crashes**, zero input mutation) + `24` targeted semantic & `4,500`-digit int/decimal/rational DoS probes (`INVALID_INT_STR`/`INVALID_DEC_STR`/`INVALID_RATIONAL_STR`) + `5` structural type-confusion probes (`SEC_SHAPE_MISMATCH`, `0` raw crashes) verified across `SEC`, `FR0`, and `FR1`.
- **Direct 4-Surface v2.1 Zone-B Fuzzer (`zone_b_fuzzer`):** **`82/82 PASS`** (`CLI 25/25`, `FR1 19/19`, `FR0 19/19`, `SEC 19/19`; `bypasses = 0`, `crashes = 0`).
- **Official `aletheia-fast-mutate` (`--guards require_ok --workers 2 --timeout 180 --max-mutants 0`):** **`170/170 KILLED = 100.0%`** (`35/35` on `s105_dual_chow_matroid_oracle.py` + `135/135` on `verify_s105_dual_chow_matroid.py`; `survived = 0`, `truncated = False`, `null_mutant = passed` on both).
- **Whole-File AST `BoolOp` Mutation (`OP_SWAP + SUBCOND_DEL`):** **`49/49 KILLED = 100.0%`** (`16` `BoolOp` nodes across oracle + verifier = `16` `OP_SWAP` + `33` `SUBCOND_DEL`; `survivors = []`).
- **Multi-Env & RO-Dir Parity (`15/15`, `0` skips):**
  - `test_s105_dual_chow_matroid_r5.py`: **`16/16 OK`** (across `-I -B`, `-I -O -B`, `-I -B -W error`, `PYTHONHASHSEED=42 -B`, `env -i HOME=/nonexistent`, and read-only directory `-I -B`).
  - `verify_s105_dual_chow_matroid.py --check`: **`OK`** (across `-I -B`, `-I -O -B`, `-I -B -W error`, `env -i HOME=/nonexistent`, and read-only directory).
- **Dual `aletheia audit-check --strict-ancestors --safety-scan --lean-audit` (`aletheia-fix-lean-gates-v2` & `aletheia-fast-mutate`):** **`PASS ×2`** (`files=8`, `lean=1 (f=0, n=0)`, `r4=2/2`, `safety=0`, `leak=0`, `bare_assert=0`, `crlf=0`, `pycache=0`).

## 8. Frozen Companion Manifest

*(The 7 sibling artifacts below are cryptographically frozen; `REPORT.md`'s own digest is reported externally in the completion handoff.)*

| File | Lines | Bytes | Mode | SHA-256 |
|---|---:|---:|---:|---|
| `DualChowMatroidTomography.lean` | `496` | `20,907` | `0644` | `71f98cb504814ee8baddb33d94e75172e4278b8f2f32dbe128e9937f95b5f2b4` |
| `lakefile.toml` | `5` | `131` | `0644` | `88b02bd23fb6d2831ac9e80a3a5336d807d125e0d4f0ade2b5f37cbc56be3dd6` |
| `lean-toolchain` | `1` | `25` | `0644` | `582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a` |
| `s105_dual_chow_matroid_oracle.py` | `1,242` | `52,398` | `0644` | `2e85890e9c647bffcc998e5ee94d0d638e710a8380991e080d4b470b69ad051b` |
| `verify_s105_dual_chow_matroid.py` | `612` | `29,003` | `0644` | `fb5af0b8e2fef911fb62803f60c32d8e9fa53af19de6e5fab9248ad9faed69d7` |
| `test_s105_dual_chow_matroid_r5.py` | `763` | `43,301` | `0644` | `4a89b89ae8786ef9b559fe4c5e6aad8bab7ede5670e77cfe5540fc257fa2f066` |
| `s105_dual_chow_matroid_certificate.json` | `1` | `18,608` | `0600` | `906cd228010c16093644a4fc13650367648c9333dd027a183112573a6a315c26` |
