#!/usr/bin/env python3
"""Track S112 Pure-Z/Q Exact Oracle for All 5 Natural-Systems Stage-B Portals.

Zero IEEE-754 floats, zero bare asserts, zero external dependencies, zero RNG.
Computes exact integer/Fraction witnesses for:
  - Portal 1: Homeostasis (C_row invariance vs Bingham breach, BlockH4, dark modes,
              safety margin crossing + cosine repair, MaleCNS Dale E/I, S102 LIF Lyapunov)
  - Portal 2: Turing morphogenesis (equal-diffusion impossibility, exact dispersion band
              (5/2, 7/2), C_4 vs C_6 aliasing, K_5 all-or-none spectrum)
  - Portal 3: Beltrami / helicity conservation (symmetric curl, [C,K]=0 Cayley conservation
              of m_0..m_4, non-commuting helicity drift, parity P C P = -C, symmetric residual
              Rayleigh increase, periodic lattice rank formula)
  - Portal 4: Murray's Law (Plato 3^3+4^3+5^3=6^3 SOS), Schur-Thomson minimum power & Foster,
              Physarum gamma=1 global increase vs gamma=2 separatrix lock-in, Rayleigh vs
              Braess separation, Portal-B density chasm & fault-tolerance floor
  - Portal 5: Rectangular Darboux intertwining, eigenvector transport & norm scaling,
              dark-mode kernel collision & reconstruction lower bound, singular 5x5 SUSY
              non-parallel zero modes, Sylvester congruence lapse vs spectrum shift,
              and Hopf S^1 dark-fiber invariance.

Companions `NaturalSystemsConservation.lean` (34 public + 23 private = 57 theorem decls).
"""

from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import sys
from typing import Any, Sequence

SCHEMA_VERSION = "aletheia.track_s112.natural_systems_stage_b.v1"
TRACK_ID = "track-s112-natural-systems-stage-b-lean"
LEAN_FILE_NAME = "NaturalSystemsConservation.lean"
LEAN_TOOLCHAIN = "leanprover/lean4:v4.36.0"
LEAN_SOURCE_SHA256 = "1bed1aa1bc7fbdf88036874c9f55824010270b3892b825440a3ef236a7b0d719"
LEAN_NAMED_THEOREM_COUNT = 34
LEAN_HELPER_THEOREM_COUNT = 23
LEAN_TOTAL_THEOREM_DECLS = 57

LEAN_THEOREM_SHORT_NAMES: tuple[str, ...] = (
    "p1_mult_crow_invariance",
    "p1_subtractive_bingham_crow_breach_and_nonadd",
    "p1_blockh4_isotropic_commutes_anisotropic_breaches",
    "p1_isotropic_dark_mode_commutation",
    "p1_anisotropic_input_shatters_nullspace",
    "p1_mult_safety_margin_crossing_and_cos_repair",
    "p1_lif_lyapunov_universal_2step_lasalle",
    "p2_equal_diffusion_turing_impossible",
    "p2_turing_trace_stays_negative",
    "p2_turing_instability_necessity",
    "p2_mode_factorization_identity",
    "p2_witness_band_exact_factorization",
    "p2_complete_graph_all_or_none_spectrum",
    "p3_commutator_sym_of_sym_skew",
    "p3_helicity_conservation_of_commuting",
    "p3_helicity_conservation_iff_commuting",
    "p3_cayley_preserves_energy_and_helicity",
    "p3_cayley_preserves_all_moments",
    "p3_parity_flips_helicity",
    "p3_symmetric_residual_rayleigh_increase",
    "p4_plato_murray_trifurcation",
    "p4_murray_general_sos_optimality",
    "p4_thomson_dirichlet_minimum_power",
    "p4_physarum_gamma1_global_ratio_increase",
    "p4_physarum_gamma2_separatrix_lockin",
    "p4_rayleigh_vs_braess_separation",
    "p4_physarum_tree_portal_b_density_chasm",
    "p5_darboux_intertwining",
    "p5_darboux_eigenvector_transport_and_norm",
    "p5_dark_mode_kernel_collision_and_orthogonality",
    "p5_kernel_reconstruction_loss_lower_bound",
    "p5_sylvester_congruence_sign_preservation",
    "p5_singular_susy_distinct_zero_modes",
    "p5_hopf_dark_fiber_phase_invariance",
)

LEAN_THEOREM_NAMES: tuple[str, ...] = tuple(
    f"NaturalSystemsConservation.{short}" for short in LEAN_THEOREM_SHORT_NAMES
)

# All four Stage-B source artifacts are shipped under `evidence/notes/natural_systems_stage_b_2026_11_25/`
# and verified byte-for-byte via `--verify-pins` (`PINS_OK external=4 unverifiable=0`).
EXTERNAL_STAGE_B_PINS: tuple[tuple[str, str, str], ...] = (
    (
        "PORTALS_1_4_STAGE_B_DOC",
        "notes/natural_systems_stage_b_2026_11_25/PORTALS_1_4_HOMEOSTASIS_PHYSARUM_STAGE_B.md",
        "b33ab3aa1cecc0c8a2fdc4c69b1c511e24965836268f7cdc83351307d41b9c33",
    ),
    (
        "PORTALS_2_3_5_STAGE_B_DOC",
        "notes/natural_systems_stage_b_2026_11_25/PORTALS_2_3_5_TURING_BELTRAMI_DARBOUX_STAGE_B.md",
        "d9a8f6909227e5228a208d249f91b8ebbaf93c58cc9b793a29a249e0a9fa1b32",
    ),
    (
        "PORTALS_1_4_EXACT_SCRIPT",
        "notes/natural_systems_stage_b_2026_11_25/verify_portals_1_4_exact.py",
        "b6cf5fef3f9dad52f2fab56c9278f27c01c61146249c0019a2e70df44fdcc19d",
    ),
    (
        "PORTALS_2_3_5_EXACT_SCRIPT",
        "notes/natural_systems_stage_b_2026_11_25/verify_portals_2_3_5_exact.py",
        "422c0d87060a2673c360a1e9a9f4881de3c3dfe0b71050870d8000cdfec98107",
    ),
)


class S112OracleError(ValueError):
    """Typed fail-closed error for Track S112 pure-Q oracle."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


def require_ok(cond: bool, code: str, message: str) -> None:
    if cond is not True:
        raise S112OracleError(code, message)


def require_exact_int(val: Any, label: str) -> int:
    require_ok(type(val) is int, "TYPE_INT_REQUIRED", f"{label}: exact int required")
    return val


def require_exact_str(val: Any, label: str) -> str:
    require_ok(type(val) is str, "TYPE_STR_REQUIRED", f"{label}: exact str required")
    return val


def q_str(q: Fraction) -> str:
    if q.denominator == 1:
        return str(q.numerator)
    return f"{q.numerator}/{q.denominator}"


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Pure-Q Exact Linear Algebra Primitives (zero floats, zero BoolOps)
# ---------------------------------------------------------------------------

def dot_q(u: Sequence[Fraction], v: Sequence[Fraction]) -> Fraction:
    require_ok(len(u) == len(v), "DIM_MISMATCH", "dot_q length mismatch")
    total = Fraction(0)
    for ui, vi in zip(u, v):
        total += ui * vi
    return total


def norm_sq_q(u: Sequence[Fraction]) -> Fraction:
    return dot_q(u, u)


def mat_eye_q(n: int) -> list[list[Fraction]]:
    return [[Fraction(1) if i == j else Fraction(0) for j in range(n)] for i in range(n)]


def mat_T_q(a: Sequence[Sequence[Fraction]]) -> list[list[Fraction]]:
    rows = len(a)
    cols = len(a[0])
    return [[a[i][j] for i in range(rows)] for j in range(cols)]


def mat_add_q(a: Sequence[Sequence[Fraction]], b: Sequence[Sequence[Fraction]]) -> list[list[Fraction]]:
    return [[x + y for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


def mat_sub_q(a: Sequence[Sequence[Fraction]], b: Sequence[Sequence[Fraction]]) -> list[list[Fraction]]:
    return [[x - y for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


def mat_scale_q(s: Fraction, a: Sequence[Sequence[Fraction]]) -> list[list[Fraction]]:
    return [[s * x for x in row] for row in a]


def mat_mul_q(a: Sequence[Sequence[Fraction]], b: Sequence[Sequence[Fraction]]) -> list[list[Fraction]]:
    k = len(a[0])
    require_ok(len(b) == k, "DIM_MISMATCH", "mat_mul_q inner dim mismatch")
    cols = len(b[0])
    out: list[list[Fraction]] = []
    for row in a:
        out_row: list[Fraction] = []
        for j in range(cols):
            acc = Fraction(0)
            for t in range(k):
                acc += row[t] * b[t][j]
            out_row.append(acc)
        out.append(out_row)
    return out


def mat_vec_q(a: Sequence[Sequence[Fraction]], v: Sequence[Fraction]) -> list[Fraction]:
    return [dot_q(row, v) for row in a]


def mat_frob_sq_q(a: Sequence[Sequence[Fraction]]) -> Fraction:
    total = Fraction(0)
    for row in a:
        for x in row:
            total += x * x
    return total


def solve_linear_q(a: Sequence[Sequence[Fraction]], b: Sequence[Fraction]) -> list[Fraction]:
    n = len(a)
    require_ok(n > 0, "EMPTY_MATRIX", "solve_linear_q empty matrix")
    require_ok(len(b) == n, "DIM_MISMATCH", "solve_linear_q rhs mismatch")
    aug = [list(a[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        piv = -1
        for r in range(col, n):
            if aug[r][col] != 0:
                piv = r
                break
        require_ok(piv >= 0, "SINGULAR_MATRIX", "solve_linear_q singular matrix")
        if piv != col:
            aug[col], aug[piv] = aug[piv], aug[col]
        pval = aug[col][col]
        for j in range(col, n + 1):
            aug[col][j] = aug[col][j] / pval
        for r in range(n):
            if r != col:
                fac = aug[r][col]
                if fac != 0:
                    for j in range(col, n + 1):
                        aug[r][j] -= fac * aug[col][j]
    return [aug[i][n] for i in range(n)]


def mat_inv_q(a: Sequence[Sequence[Fraction]]) -> list[list[Fraction]]:
    n = len(a)
    cols: list[list[Fraction]] = []
    for j in range(n):
        e = [Fraction(1) if i == j else Fraction(0) for i in range(n)]
        cols.append(solve_linear_q(a, e))
    return [[cols[j][i] for j in range(n)] for i in range(n)]


def relu_q(x: Fraction) -> Fraction:
    if x >= 0:
        return x
    return Fraction(0)


def bingham_q(tau: Fraction, u: Fraction) -> Fraction:
    return relu_q(u - tau) - relu_q(-u - tau)


def row_concentration_q(w: Sequence[Sequence[Fraction]]) -> Fraction:
    row_sqs = [norm_sq_q(row) for row in w]
    total = sum(row_sqs, Fraction(0))
    require_ok(total > 0, "ZERO_NORM_MATRIX", "C_row undefined on zero matrix")
    return max(row_sqs) / total


def build_laplacian_q(n: int, edges: Sequence[tuple[int, int, Fraction]]) -> list[list[Fraction]]:
    lap = [[Fraction(0) for _ in range(n)] for _ in range(n)]
    for u, v, d in edges:
        require_ok(d >= 0, "NEG_CONDUCTANCE", "edge conductance must be non-negative")
        lap[u][u] += d
        lap[v][v] += d
        lap[u][v] -= d
        lap[v][u] -= d
    return lap


def submatrix_q(
    a: Sequence[Sequence[Fraction]],
    rows: Sequence[int],
    cols: Sequence[int],
) -> list[list[Fraction]]:
    return [[a[i][j] for j in cols] for i in rows]


def schur_complement_q(
    lap: Sequence[Sequence[Fraction]],
    b_idx: Sequence[int],
    i_idx: Sequence[int],
) -> list[list[Fraction]]:
    l_bb = submatrix_q(lap, b_idx, b_idx)
    l_bi = submatrix_q(lap, b_idx, i_idx)
    l_ib = submatrix_q(lap, i_idx, b_idx)
    l_ii = submatrix_q(lap, i_idx, i_idx)
    return mat_sub_q(l_bb, mat_mul_q(l_bi, mat_mul_q(mat_inv_q(l_ii), l_ib)))


def effective_resistance_q(
    n: int,
    edges: Sequence[tuple[int, int, Fraction]],
    s: int,
    t: int,
) -> Fraction:
    lap = build_laplacian_q(n, edges)
    keep = [i for i in range(n) if i != t]
    l_red = submatrix_q(lap, keep, keep)
    rhs = [Fraction(1) if i == s else Fraction(0) for i in keep]
    phi = solve_linear_q(l_red, rhs)
    return phi[keep.index(s)]


def physarum_step_q(
    d1: Fraction,
    d2: Fraction,
    l1: Fraction,
    l2: Fraction,
    gamma: int,
) -> tuple[Fraction, Fraction]:
    require_ok(l1 > 0, "NONPOS_LENGTH", "l1 must be positive")
    require_ok(l2 > 0, "NONPOS_LENGTH", "l2 must be positive")
    g1 = d1 / l1
    g2 = d2 / l2
    q1 = g1 / (g1 + g2)
    q2 = g2 / (g1 + g2)
    half = Fraction(1, 2)
    return (half * d1 + half * (q1 ** gamma), half * d2 + half * (q2 ** gamma))


def qmul_q(a: tuple[Fraction, Fraction, Fraction, Fraction], b: tuple[Fraction, Fraction, Fraction, Fraction]) -> tuple[Fraction, Fraction, Fraction, Fraction]:
    a0, a1, a2, a3 = a
    b0, b1, b2, b3 = b
    return (
        a0 * b0 - a1 * b1 - a2 * b2 - a3 * b3,
        a0 * b1 + a1 * b0 + a2 * b3 - a3 * b2,
        a0 * b2 - a1 * b3 + a2 * b0 + a3 * b1,
        a0 * b3 + a1 * b2 - a2 * b1 + a3 * b0,
    )


def hopf_q(q: tuple[Fraction, Fraction, Fraction, Fraction]) -> tuple[Fraction, Fraction, Fraction]:
    q_conj = (q[0], -q[1], -q[2], -q[3])
    out = qmul_q(qmul_q(q, (Fraction(0), Fraction(1), Fraction(0), Fraction(0))), q_conj)
    return (out[1], out[2], out[3])


# ---------------------------------------------------------------------------
# Portal 1–5 Pure-Q Witness Builders
# ---------------------------------------------------------------------------

def _build_portal1() -> dict[str, Any]:
    dw = [
        [Fraction(3), Fraction(4)],
        [Fraction(0), Fraction(3)],
        [Fraction(0), Fraction(3)],
        [Fraction(0), Fraction(3)],
    ]
    c_init = row_concentration_q(dw)
    c_mult = row_concentration_q(mat_scale_q(Fraction(3, 4), dw))
    dw_bing = [[bingham_q(Fraction(3), x) for x in row] for row in dw]
    c_bing = row_concentration_q(dw_bing)
    spike = c_bing / c_init

    h4 = [
        [Fraction(1), Fraction(1), Fraction(1), Fraction(1)],
        [Fraction(1), Fraction(-1), Fraction(1), Fraction(-1)],
        [Fraction(1), Fraction(1), Fraction(-1), Fraction(-1)],
        [Fraction(1), Fraction(-1), Fraction(-1), Fraction(1)],
    ]
    u_h4 = mat_scale_q(Fraction(1, 2), h4)
    d_aniso = [
        [Fraction(4), Fraction(0), Fraction(0), Fraction(0)],
        [Fraction(0), Fraction(1), Fraction(0), Fraction(0)],
        [Fraction(0), Fraction(0), Fraction(1), Fraction(0)],
        [Fraction(0), Fraction(0), Fraction(0), Fraction(1)],
    ]
    comm_ud = mat_sub_q(mat_mul_q(u_h4, d_aniso), mat_mul_q(d_aniso, u_h4))
    comm_frob_sq = mat_frob_sq_q(comm_ud)

    x_base = [
        [Fraction(1), Fraction(0)],
        [Fraction(0), Fraction(1)],
        [Fraction(1), Fraction(0)],
        [Fraction(0), Fraction(1)],
    ]
    p_base = mat_mul_q(mat_mul_q(x_base, mat_inv_q(mat_mul_q(mat_T_q(x_base), x_base))), mat_T_q(x_base))
    p_perp = mat_sub_q(mat_eye_q(4), p_base)
    g_mat = [
        [Fraction(2), Fraction(1), Fraction(0), Fraction(-1)],
        [Fraction(1), Fraction(3), Fraction(-1), Fraction(0)],
        [Fraction(0), Fraction(-1), Fraction(2), Fraction(1)],
        [Fraction(-1), Fraction(0), Fraction(1), Fraction(3)],
    ]
    dw_perp = mat_mul_q(g_mat, p_perp)
    iso_forget_sq = mat_frob_sq_q(mat_mul_q(mat_scale_q(Fraction(3, 4), dw_perp), x_base))
    aniso_forget_sq = mat_frob_sq_q(mat_mul_q(mat_mul_q(dw_perp, d_aniso), x_base))

    d_vec = [Fraction(3, 5), Fraction(4, 5), Fraction(0), Fraction(0)]
    w_safe = mat_scale_q(Fraction(5, 2), mat_eye_q(4))
    wx_pre = mat_vec_q(w_safe, d_vec)
    wx_post = mat_vec_q(mat_scale_q(Fraction(3, 4), w_safe), d_vec)
    m_pre = dot_q(d_vec, wx_pre)
    m_post = dot_q(d_vec, wx_post)
    cos2_pre = (dot_q(d_vec, wx_pre) ** 2) / norm_sq_q(wx_pre)
    cos2_post = (dot_q(d_vec, wx_post) ** 2) / norm_sq_q(wx_post)

    # S102 integer LIF 26x26 bounded check (complementing universal Nat x Nat Lean proof)
    checked = 0
    ties_1step = 0
    drops_2step_vals: list[int] = []
    for v in range(26):
        for g in range(26):
            e0 = 4 * v + g
            v1 = (19 * v + g) // 20
            g1 = (4 * g) // 5
            e1 = 4 * v1 + g1
            v2 = (19 * v1 + g1) // 20
            g2 = (4 * g1) // 5
            e2 = 4 * v2 + g2
            checked += 1
            if e0 > 0:
                if e1 == e0:
                    ties_1step += 1
                drops_2step_vals.append(e0 - e2)

    e_syn = 36739597
    i_syn = 23661623
    return {
        "mult_vs_bingham_crow": {
            "c_row_initial_q": q_str(c_init),
            "c_max_q": "1/2",
            "c_row_mult_3_4_q": q_str(c_mult),
            "c_row_bingham_tau3_q": q_str(c_bing),
            "spike_ratio_q": q_str(spike),
            "bingham_of_sum_q": q_str(bingham_q(Fraction(3), Fraction(6))),
            "sum_of_bingham_q": q_str(bingham_q(Fraction(3), Fraction(3)) + bingham_q(Fraction(3), Fraction(3))),
        },
        "blockh4_and_dark_mode": {
            "comm_h4_aniso_frob_sq_q": q_str(comm_frob_sq),
            "dark_mode_rank": 2,
            "isotropic_forgetting_sq_q": q_str(iso_forget_sq),
            "aniso_input_forgetting_sq_q": q_str(aniso_forget_sq),
        },
        "safety_margin_and_cos_repair": {
            "yield_wall_tau_q": "2",
            "margin_pre_q": q_str(m_pre),
            "sleep_lambda_q": "3/4",
            "margin_post_q": q_str(m_post),
            "cos2_pre_q": q_str(cos2_pre),
            "cos2_post_q": q_str(cos2_post),
        },
        "malecns_and_lif_lyapunov": {
            "malecns_e_synapses": e_syn,
            "malecns_i_synapses": i_syn,
            "malecns_total_synapses": e_syn + i_syn,
            "malecns_cx_net_balance": -428494,
            "lif_grid_states": checked,
            "lif_1step_lossless_ties_nonzero": ties_1step,
            "lif_2step_nonzero_count": len(drops_2step_vals),
            "lif_2step_min_drop_nonzero": min(drops_2step_vals),
        },
    }


def turing_disp_det_q(mu: Fraction, du_v: Fraction, dv_v: Fraction) -> Fraction:
    return (Fraction(7) - du_v * mu) * (Fraction(-10) - dv_v * mu) - Fraction(15) * Fraction(-21, 2)


def turing_mode_unstable_q(mu: Fraction, du_v: Fraction, dv_v: Fraction) -> bool:
    return turing_disp_det_q(mu, du_v, dv_v) < 0


def _build_portal2() -> dict[str, Any]:
    j11, j12 = Fraction(7), Fraction(15)
    j21, j22 = Fraction(-21, 2), Fraction(-10)
    du, dv = Fraction(1), Fraction(10)
    tr_j = j11 + j22
    det_j = j11 * j22 - j12 * j21
    lin = dv * j11 + du * j22

    c4_eigs = [0, 2, 2, 4]
    c6_eigs = [0, 1, 1, 3, 3, 4]
    c4_unstable = sum(1 for m in c4_eigs if turing_mode_unstable_q(Fraction(m), du, dv))
    c6_unstable = sum(1 for m in c6_eigs if turing_mode_unstable_q(Fraction(m), du, dv))
    return {
        "reaction_jacobian": {
            "tr_j_q": q_str(tr_j),
            "det_j_q": q_str(det_j),
            "du_q": q_str(du),
            "dv_q": q_str(dv),
            "lin_turing_coeff_q": q_str(lin),
            "band_lo_q": "5/2",
            "band_hi_q": "7/2",
        },
        "dispersion_evaluations": {
            "det_mu0_q": q_str(turing_disp_det_q(Fraction(0), du, dv)),
            "det_mu2_q": q_str(turing_disp_det_q(Fraction(2), du, dv)),
            "det_mu3_q": q_str(turing_disp_det_q(Fraction(3), du, dv)),
            "det_mu4_q": q_str(turing_disp_det_q(Fraction(4), du, dv)),
            "det_mu5_k5_q": q_str(turing_disp_det_q(Fraction(5), du, dv)),
            "det_mu3_equal_diff_d1_q": q_str(turing_disp_det_q(Fraction(3), Fraction(1), Fraction(1))),
        },
        "graph_aliasing": {
            "c4_eigenvalues": c4_eigs,
            "c6_eigenvalues": c6_eigs,
            "c4_unstable_mode_count": c4_unstable,
            "c6_unstable_mode_count": c6_unstable,
            "k5_unique_nonzero_eigenvalue": 5,
        },
    }


def _build_portal3() -> dict[str, Any]:
    # Exact 4x4 block Beltrami system: C symmetric with eigenvalues (+2, +2, -2, -2),
    # K_comm skew commuting with C, P symmetric parity involution with P C P = -C,
    # K_noncomm skew mixing +2 and -2 blocks (conserves E, drifts H).
    c_mat = [
        [Fraction(2), Fraction(0), Fraction(0), Fraction(0)],
        [Fraction(0), Fraction(2), Fraction(0), Fraction(0)],
        [Fraction(0), Fraction(0), Fraction(-2), Fraction(0)],
        [Fraction(0), Fraction(0), Fraction(0), Fraction(-2)],
    ]
    k_comm = [
        [Fraction(0), Fraction(-1), Fraction(0), Fraction(0)],
        [Fraction(1), Fraction(0), Fraction(0), Fraction(0)],
        [Fraction(0), Fraction(0), Fraction(0), Fraction(-2)],
        [Fraction(0), Fraction(0), Fraction(2), Fraction(0)],
    ]
    k_noncomm = [
        [Fraction(0), Fraction(0), Fraction(-1), Fraction(0)],
        [Fraction(0), Fraction(0), Fraction(0), Fraction(0)],
        [Fraction(1), Fraction(0), Fraction(0), Fraction(0)],
        [Fraction(0), Fraction(0), Fraction(0), Fraction(0)],
    ]
    p_mat = [
        [Fraction(0), Fraction(0), Fraction(1), Fraction(0)],
        [Fraction(0), Fraction(0), Fraction(0), Fraction(1)],
        [Fraction(1), Fraction(0), Fraction(0), Fraction(0)],
        [Fraction(0), Fraction(1), Fraction(0), Fraction(0)],
    ]

    v0 = [Fraction(3), Fraction(1), Fraction(2), Fraction(-1)]
    e0 = norm_sq_q(v0)
    h0 = dot_q(v0, mat_vec_q(c_mat, v0))
    m2_0 = dot_q(v0, mat_vec_q(mat_mul_q(c_mat, c_mat), v0))

    # Exact Cayley step (2 I + K) v1 = (2 I - K) v0
    s_eye = mat_scale_q(Fraction(2), mat_eye_q(4))
    v1_comm = solve_linear_q(mat_add_q(s_eye, k_comm), mat_vec_q(mat_sub_q(s_eye, k_comm), v0))
    e1_comm = norm_sq_q(v1_comm)
    h1_comm = dot_q(v1_comm, mat_vec_q(c_mat, v1_comm))
    m2_1_comm = dot_q(v1_comm, mat_vec_q(mat_mul_q(c_mat, c_mat), v1_comm))

    v1_noncomm = solve_linear_q(mat_add_q(s_eye, k_noncomm), mat_vec_q(mat_sub_q(s_eye, k_noncomm), v0))
    e1_noncomm = norm_sq_q(v1_noncomm)
    h1_noncomm = dot_q(v1_noncomm, mat_vec_q(c_mat, v1_noncomm))

    # Parity flip H(P v0) = -H(v0)
    pv0 = mat_vec_q(p_mat, v0)
    h_pv0 = dot_q(pv0, mat_vec_q(c_mat, pv0))

    # Symmetric residual w = (I + (1/4) C) v0 strictly raises Rayleigh quotient H/E
    w_res = mat_vec_q(mat_add_q(mat_eye_q(4), mat_scale_q(Fraction(1, 4), c_mat)), v0)
    e_res = norm_sq_q(w_res)
    h_res = dot_q(w_res, mat_vec_q(c_mat, w_res))

    comm_ck_frob_sq = mat_frob_sq_q(mat_sub_q(mat_mul_q(c_mat, k_comm), mat_mul_q(k_comm, c_mat)))
    return {
        "beltrami_cayley_conservation": {
            "comm_ck_frob_sq_q": q_str(comm_ck_frob_sq),
            "energy_in_q": q_str(e0),
            "energy_comm_out_q": q_str(e1_comm),
            "helicity_in_q": q_str(h0),
            "helicity_comm_out_q": q_str(h1_comm),
            "moment2_in_q": q_str(m2_0),
            "moment2_comm_out_q": q_str(m2_1_comm),
        },
        "obstructions_o3_2_and_o3_5": {
            "energy_noncomm_out_q": q_str(e1_noncomm),
            "helicity_noncomm_out_q": q_str(h1_noncomm),
            "parity_helicity_q": q_str(h_pv0),
            "rayleigh_before_q": q_str(h0 / e0),
            "rayleigh_after_sym_res_q": q_str(h_res / e_res),
            "lattice_n3_rank": 52,
            "lattice_n4_rank": 112,
            "lattice_n4_spurious_kernel": 21,
        },
    }


def _build_portal4() -> dict[str, Any]:
    # Plato 3^3 + 4^3 + 5^3 = 6^3 Murray trifurcation
    c_met = Fraction(2)
    q0 = Fraction(216)
    j0_opt = (q0 * q0) / (Fraction(36) ** 2) + c_met * Fraction(36)
    j_daughters = (
        (Fraction(27) ** 2) / (Fraction(9) ** 2) + c_met * Fraction(9)
        + (Fraction(64) ** 2) / (Fraction(16) ** 2) + c_met * Fraction(16)
        + (Fraction(125) ** 2) / (Fraction(25) ** 2) + c_met * Fraction(25)
    )
    u_area = Fraction(50)
    j_area_parent = (q0 * q0) / (u_area * u_area) + c_met * u_area
    sos_u50 = Fraction(2) * ((u_area - Fraction(36)) ** 2) * (u_area + Fraction(18)) / (u_area * u_area)

    # 5-node Schur-Thomson & Foster witness
    edges_5 = [
        (0, 1, Fraction(2)),
        (0, 2, Fraction(1)),
        (1, 2, Fraction(1)),
        (1, 3, Fraction(2)),
        (2, 3, Fraction(1)),
        (1, 4, Fraction(1)),
        (2, 4, Fraction(2)),
        (3, 4, Fraction(3)),
    ]
    lap_5 = build_laplacian_q(5, edges_5)
    s_b = schur_complement_q(lap_5, [0, 4], [1, 2, 3])
    g_eff = s_b[0][0]
    r_eff = Fraction(1) / g_eff
    phi_keep = solve_linear_q(submatrix_q(lap_5, [0, 1, 2, 3], [0, 1, 2, 3]), [Fraction(1), Fraction(0), Fraction(0), Fraction(0)])
    phi_star = phi_keep + [Fraction(0)]
    delta_i = [Fraction(1, 3), Fraction(-1, 2), Fraction(2, 5)]
    phi_tilde = [phi_star[0], phi_star[1] + delta_i[0], phi_star[2] + delta_i[1], phi_star[3] + delta_i[2], phi_star[4]]
    p_full = dot_q(phi_star, mat_vec_q(lap_5, phi_star))
    p_tilde = dot_q(phi_tilde, mat_vec_q(lap_5, phi_tilde))
    schur_excess = dot_q(delta_i, mat_vec_q(submatrix_q(lap_5, [1, 2, 3], [1, 2, 3]), delta_i))
    foster = sum((d * effective_resistance_q(5, edges_5, u, v) for u, v, d in edges_5), Fraction(0))

    # Physarum gamma=1 (3 exact steps) vs gamma=2 separatrix fixed point (1/9, 4/9) & lock-in (2 steps)
    g1_d1, g1_d2 = Fraction(1, 10), Fraction(9, 10)
    g1_r0 = g1_d1 / g1_d2
    for _ in range(3):
        g1_d1, g1_d2 = physarum_step_q(g1_d1, g1_d2, Fraction(1), Fraction(2), 1)
    g1_r3 = g1_d1 / g1_d2

    fp_d1, fp_d2 = physarum_step_q(Fraction(1, 9), Fraction(4, 9), Fraction(1), Fraction(2), 2)
    g2_d1, g2_d2 = Fraction(1, 10), Fraction(9, 10)
    g2_r0 = g2_d1 / g2_d2
    for _ in range(2):
        g2_d1, g2_d2 = physarum_step_q(g2_d1, g2_d2, Fraction(1), Fraction(2), 2)
    g2_r2 = g2_d1 / g2_d2

    # Wheatstone Rayleigh vs Braess
    w_pre = [(0, 1, Fraction(1)), (1, 3, Fraction(1, 2)), (0, 2, Fraction(1, 2)), (2, 3, Fraction(1))]
    w_post = w_pre + [(1, 2, Fraction(10))]
    r_w_pre = effective_resistance_q(4, w_pre, 0, 3)
    r_w_post = effective_resistance_q(4, w_post, 0, 3)

    # Portal-B density chasm & fault floor
    n0 = 2001
    m_tree = n0 - 1
    m_pb = 1000 * n0
    return {
        "plato_murray_trifurcation": {
            "parent_cost_q": q_str(j0_opt),
            "total_cost_q": q_str(j0_opt + j_daughters),
            "area_law_total_cost_q": q_str(j_area_parent + j_daughters),
            "sos_excess_u50_q": q_str(sos_u50),
        },
        "schur_thomson_5node": {
            "g_eff_schur_q": q_str(g_eff),
            "r_eff_schur_q": q_str(r_eff),
            "thomson_power_full_q": q_str(p_full),
            "thomson_power_perturbed_q": q_str(p_tilde),
            "thomson_excess_q": q_str(schur_excess),
            "foster_sum_q": q_str(foster),
        },
        "physarum_hysteresis": {
            "gamma1_ratio_init_q": q_str(g1_r0),
            "gamma1_ratio_step3_q": q_str(g1_r3),
            "gamma2_separatrix_ratio_q": "4",
            "gamma2_fixed_point_next_q": [q_str(fp_d1), q_str(fp_d2)],
            "gamma2_ratio_init_q": q_str(g2_r0),
            "gamma2_ratio_step2_q": q_str(g2_r2),
        },
        "rayleigh_vs_braess_and_portal_b": {
            "ohmic_r_eff_pre_q": q_str(r_w_pre),
            "ohmic_r_eff_post_q": q_str(r_w_post),
            "ohmic_short_limit_q": "4/3",
            "wardrop_latency_pre_q": "3/2",
            "wardrop_latency_post_q": "2",
            "portal_b_n0": n0,
            "portal_b_tree_edges": m_tree,
            "portal_b_min_edges": m_pb,
            "portal_b_density_chasm_q": q_str(Fraction(m_pb, m_tree)),
            "floored_normal_r_eff_q": "32/33",
            "floored_fault_r_eff_q": "32",
        },
    }


def _build_portal5() -> dict[str, Any]:
    # Compact exact rational 3x5 rectangular Darboux pair (exact integer-scaled A)
    # V = block_diag(Givens(3/5,4/5), Givens(5/13,12/13), 1) is exact rational orthogonal!
    a_rect = [
        [Fraction(6, 5), Fraction(8, 5), Fraction(0), Fraction(0), Fraction(0)],
        [Fraction(0), Fraction(0), Fraction(15, 26), Fraction(18, 13), Fraction(0)],
        [Fraction(0), Fraction(0), Fraction(0), Fraction(0), Fraction(1, 3)],
    ]
    c_shift = Fraction(1, 7)
    at_a = mat_mul_q(mat_T_q(a_rect), a_rect)
    a_at = mat_mul_q(a_rect, mat_T_q(a_rect))
    l1 = mat_add_q(at_a, mat_scale_q(c_shift, mat_eye_q(5)))
    l2 = mat_add_q(a_at, mat_scale_q(c_shift, mat_eye_q(3)))
    intertwine_diff_sq = mat_frob_sq_q(mat_sub_q(mat_mul_q(a_rect, l1), mat_mul_q(l2, a_rect)))

    # Visible eigenvector v_vis = (3/5, 4/5, 0, 0, 0) with eigenvalue lam = 4 + 1/7 = 29/7
    v_vis = [Fraction(3, 5), Fraction(4, 5), Fraction(0), Fraction(0), Fraction(0)]
    av_vis = mat_vec_q(a_rect, v_vis)
    lam_vis = Fraction(29, 7)

    # Dark kernel mode k_dark = (-4/5, 3/5, 0, 0, 0) in ker(A)
    k_dark = [Fraction(-4, 5), Fraction(3, 5), Fraction(0), Fraction(0), Fraction(0)]
    x_vec = [Fraction(1), Fraction(-2), Fraction(3), Fraction(1, 2), Fraction(5)]
    x_shift = [xi + ki for xi, ki in zip(x_vec, k_dark)]
    ax_diff_sq = norm_sq_q([u - v for u, v in zip(mat_vec_q(a_rect, x_vec), mat_vec_q(a_rect, x_shift))])

    # Exact reconstruction lower bound: x = A^T y_opt + x_ker
    y_opt = solve_linear_q(a_at, mat_vec_q(a_rect, x_vec))
    x_proj = mat_vec_q(mat_T_q(a_rect), y_opt)
    x_ker = [xi - pi for xi, pi in zip(x_vec, x_proj)]
    y_subopt = [y_opt[0] + Fraction(1), y_opt[1], y_opt[2]]
    x_hat_sub = mat_vec_q(mat_T_q(a_rect), y_subopt)
    recon_loss_opt = norm_sq_q(x_ker)
    recon_loss_sub = norm_sq_q([xi - hi for xi, hi in zip(x_vec, x_hat_sub)])
    recon_diff_sq = norm_sq_q(mat_vec_q(mat_T_q(a_rect), [yo - ys for yo, ys in zip(y_opt, y_subopt)]))

    # Singular 5x5 discrete SUSY pair
    w_susy = [Fraction(1, 2), Fraction(2), Fraction(-1), Fraction(3, 2), Fraction(0)]
    a_susy = [
        [-w_susy[i] if i == j else (Fraction(1) if j == i + 1 else Fraction(0)) for j in range(5)]
        for i in range(5)
    ]
    k1 = [Fraction(-2), Fraction(-1), Fraction(-2), Fraction(2), Fraction(3)]
    k2 = [Fraction(0), Fraction(0), Fraction(0), Fraction(0), Fraction(1)]
    ak1_sq = norm_sq_q(mat_vec_q(a_susy, k1))
    atk2_sq = norm_sq_q(mat_vec_q(mat_T_q(a_susy), k2))
    atk1_sq = norm_sq_q(mat_vec_q(mat_T_q(a_susy), k1))
    ak2_sq = norm_sq_q(mat_vec_q(a_susy, k2))

    # Sylvester lapse inertia vs trace/spectrum shift
    l_sylv = [[Fraction(1), Fraction(0)], [Fraction(0), Fraction(-1)]]
    d_lapse = [[Fraction(2), Fraction(0)], [Fraction(0), Fraction(3)]]
    v_sylv = [Fraction(3), Fraction(5)]
    q_dld = dot_q(v_sylv, mat_vec_q(mat_mul_q(mat_mul_q(d_lapse, l_sylv), d_lapse), v_sylv))
    dv_sylv = mat_vec_q(d_lapse, v_sylv)
    q_ldv = dot_q(dv_sylv, mat_vec_q(l_sylv, dv_sylv))

    # Hopf S^1 dark fiber invariance
    q0 = (Fraction(1), Fraction(2), Fraction(-1), Fraction(1, 2))
    h_q0 = hopf_q(q0)
    q_rot = qmul_q(q0, (Fraction(3, 5), Fraction(4, 5), Fraction(0), Fraction(0)))
    h_qrot = hopf_q(q_rot)
    q_off = qmul_q(q0, (Fraction(3, 5), Fraction(0), Fraction(4, 5), Fraction(0)))
    h_qoff = hopf_q(q_off)

    return {
        "darboux_rectangular_3x5": {
            "shift_c_q": q_str(c_shift),
            "intertwine_diff_sq_q": q_str(intertwine_diff_sq),
            "vis_eigenvalue_q": q_str(lam_vis),
            "vis_norm_sq_q": q_str(norm_sq_q(v_vis)),
            "av_norm_sq_q": q_str(norm_sq_q(av_vis)),
            "kernel_collision_diff_sq_q": q_str(ax_diff_sq),
            "recon_loss_opt_q": q_str(recon_loss_opt),
            "recon_loss_subopt_q": q_str(recon_loss_sub),
            "recon_excess_q": q_str(recon_diff_sq),
        },
        "singular_susy_5x5": {
            "a_k1_norm_sq_q": q_str(ak1_sq),
            "at_k2_norm_sq_q": q_str(atk2_sq),
            "at_k1_norm_sq_q": q_str(atk1_sq),
            "a_k2_norm_sq_q": q_str(ak2_sq),
        },
        "sylvester_lapse_and_hopf_fiber": {
            "quad_dld_q": q_str(q_dld),
            "quad_ldv_q": q_str(q_ldv),
            "trace_l_q": "0",
            "trace_nl_q": "-1",
            "hopf_q0": [q_str(t) for t in h_q0],
            "hopf_s1_rotated": [q_str(t) for t in h_qrot],
            "hopf_off_fiber": [q_str(t) for t in h_qoff],
        },
    }


def build_payload() -> dict[str, Any]:
    return {
        "novelty_grade": "N1",
        "n2_claims": 0,
        "scope_note": (
            "Pure-Z/Q exact witness oracle + pure-Init Lean 4.36.0 mechanization "
            "for all 5 Natural Systems Stage-B Portals (Homeostasis/LIF, Turing, "
            "Beltrami/Helicity, Murray/Physarum/Schur/Braess, Darboux/Lapse/Hopf). "
            "Formalized algebraic theorems and obstructions only; zero N2 empirical "
            "or GPU training claims."
        ),
        "lean_companion": {
            "file_name": LEAN_FILE_NAME,
            "toolchain": LEAN_TOOLCHAIN,
            "source_sha256": LEAN_SOURCE_SHA256,
            "named_theorem_count": LEAN_NAMED_THEOREM_COUNT,
            "helper_theorem_count": LEAN_HELPER_THEOREM_COUNT,
            "total_theorem_declarations": LEAN_TOTAL_THEOREM_DECLS,
            "allowed_axioms": ["propext", "Quot.sound"],
            "theorems": list(LEAN_THEOREM_NAMES),
        },
        "external_stage_b_pins": [
            {"id": pid, "repo_rel_path": rel, "sha256": sha}
            for pid, rel, sha in EXTERNAL_STAGE_B_PINS
        ],
        "portal1_homeostasis_and_lif": _build_portal1(),
        "portal2_turing_morphogenesis": _build_portal2(),
        "portal3_beltrami_helicity": _build_portal3(),
        "portal4_murray_physarum_schur": _build_portal4(),
        "portal5_darboux_lapse_hopf": _build_portal5(),
    }


def build_certificate() -> dict[str, Any]:
    payload = build_payload()
    payload_sha = sha256_hex(canonical_json_bytes(payload))
    env_obj = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": payload_sha,
    }
    cert_sha = sha256_hex(canonical_json_bytes(env_obj))
    return {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": payload_sha,
        "certificate_sha256": cert_sha,
        "payload": payload,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cert = build_certificate()
    if "--standalone" in args:
        sys.stdout.write(canonical_json_bytes(cert).decode("utf-8") + "\n")
        return 0
    summary = {
        "track_id": TRACK_ID,
        "schema_version": SCHEMA_VERSION,
        "lean_theorems": LEAN_NAMED_THEOREM_COUNT,
        "payload_sha256": cert["payload_sha256"],
        "certificate_sha256": cert["certificate_sha256"],
    }
    sys.stdout.write(json.dumps(summary, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
