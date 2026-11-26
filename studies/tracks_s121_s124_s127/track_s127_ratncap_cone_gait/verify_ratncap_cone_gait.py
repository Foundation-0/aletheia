#!/usr/bin/env python3
"""Track S127 (EXP-Q31a / PREREG-W15): Pure-Q Exact Oracle for Rat NCAP Antagonistic Cone Linearization,
Commissural V0/V3 Z_2 Gait Symmetry-Breaking Krein-Inertia Bifurcation, and HoloSphere Dual-Pole Gate Transfer.

Zero IEEE-754 floats (zero float literals in AST; int / fractions.Fraction only).
Zero bare asserts. Fail-closed RatNCAPError on all invalid/tampered inputs.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import hmac
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA_S127 = "aletheia.s127.ratncap_antagonistic_cone_gait.v1"
PREREG_W15_SHA256 = "6c938ddb41b912f01dba3ccb58e3f8cb54ebe60f93f6bc0eaec134bc93f189a0"
MAX_JSON_DEPTH = 32
MAX_INT_ABS = 10**18


class RatNCAPError(ValueError):
    """Fail-closed error for Track S127 pure-Q geometry verification."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"[{code}] {detail}")


def require_ok(cond: bool, code: str, detail: str) -> None:
    if not cond:
        raise RatNCAPError(code, detail)


def check_frac(val: Any, name: str) -> Fraction:
    if type(val) is Fraction:
        require_ok(abs(val.numerator) <= MAX_INT_ABS and val.denominator <= MAX_INT_ABS, "FRAC_RANGE", name)
        return val
    if type(val) is int:
        require_ok(abs(val) <= MAX_INT_ABS, "INT_RANGE", name)
        return Fraction(val, 1)
    raise RatNCAPError("BAD_FRAC", f"{name} must be Fraction or int")


def frac_str(x: Fraction) -> str:
    return f"{x.numerator}/{x.denominator}"


def _canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def validate_json_tree_no_floats(root: Any, max_depth: int = MAX_JSON_DEPTH) -> None:
    """Iterative depth-capped JSON tree check rejecting floats and non-str keys."""
    stack: List[Tuple[Any, int]] = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        require_ok(depth <= max_depth, "JSON_DEPTH", "JSON nesting exceeds cap")
        t = type(node)
        if t is float:
            raise RatNCAPError("FLOAT_FORBIDDEN", "Float forbidden in pure-Q certificate")
        if t is dict:
            for k, v in node.items():
                require_ok(type(k) is str, "BAD_KEY", "Dict key must be str")
                stack.append((v, depth + 1))
        elif t is list:
            for item in node:
                stack.append((item, depth + 1))
        elif t in (int, str, bool) or node is None:
            continue
        else:
            raise RatNCAPError("BAD_JSON_TYPE", f"Unsupported type {t.__name__}")


# ---------------------------------------------------------------------------
# G1 (W15-OBS-3): Antagonistic Flexor-Extensor Cone Linearization & Elasticity
# ---------------------------------------------------------------------------


def antagonistic_forward_q(
    a_ext: Any,
    a_flx: Any,
    k_ext: Any,
    k_flx: Any,
    q_ext: Any,
    q_flx: Any,
) -> Tuple[Fraction, Fraction]:
    """Forward cone map (a_ext, a_flx) in Q_{>=0}^2 \\ {(0,0)} -> (K_eff > 0, q_eq in [q_flx, q_ext])."""
    ae = check_frac(a_ext, "a_ext")
    af = check_frac(a_flx, "a_flx")
    ke = check_frac(k_ext, "k_ext")
    kf = check_frac(k_flx, "k_flx")
    qe = check_frac(q_ext, "q_ext")
    qf = check_frac(q_flx, "q_flx")

    require_ok(ke > 0 and kf > 0, "BAD_SPRING_K", "Spring constants k_ext, k_flx must be > 0")
    require_ok(qf < qe, "BAD_POLE_ORDER", "Pole angles must satisfy q_flx < q_ext")
    require_ok(ae >= 0 and af >= 0, "NEG_ACTIVATION", "Muscle activations must be >= 0")
    require_ok(ae + af > 0, "ZERO_CONE_ORIGIN", "(a_ext, a_flx) cannot both be zero")

    k_eff = ae * ke + af * kf
    q_eq = (ae * ke * qe + af * kf * qf) / k_eff
    return k_eff, q_eq


def antagonistic_inverse_q(
    k_eff: Any,
    q_eq: Any,
    k_ext: Any,
    k_flx: Any,
    q_ext: Any,
    q_flx: Any,
) -> Tuple[Fraction, Fraction]:
    """Exact inverse map (K_eff > 0, q_eq in [q_flx, q_ext]) -> (a_ext, a_flx) in Q_{>=0}^2 \\ {(0,0)}."""
    keff = check_frac(k_eff, "k_eff")
    qeq = check_frac(q_eq, "q_eq")
    ke = check_frac(k_ext, "k_ext")
    kf = check_frac(k_flx, "k_flx")
    qe = check_frac(q_ext, "q_ext")
    qf = check_frac(q_flx, "q_flx")

    require_ok(ke > 0 and kf > 0, "BAD_SPRING_K", "Spring constants k_ext, k_flx must be > 0")
    require_ok(qf < qe, "BAD_POLE_ORDER", "Pole angles must satisfy q_flx < q_ext")
    require_ok(keff > 0, "NONPOS_KEFF", "Effective stiffness K_eff must be > 0")
    require_ok(qf <= qeq <= qe, "QEQ_OUT_OF_HULL", "Equilibrium q_eq must lie in [q_flx, q_ext]")

    span = qe - qf
    a_ext = (keff * (qeq - qf)) / (ke * span)
    a_flx = (keff * (qe - qeq)) / (kf * span)
    return a_ext, a_flx


def antagonistic_torque_q(
    a_ext: Fraction,
    a_flx: Fraction,
    k_ext: Fraction,
    k_flx: Fraction,
    q_ext: Fraction,
    q_flx: Fraction,
    q: Fraction,
) -> Fraction:
    return a_ext * k_ext * (q_ext - q) + a_flx * k_flx * (q_flx - q)


def spring_work_q(k_eff: Any, q_eq: Any, q_start: Any, q_end: Any) -> Fraction:
    """Exact actuator work W = int_{q_start}^{q_end} K_eff*(q_eq - q) dq = -1/2 K_eff [(q_end-q_eq)^2 - (q_start-q_eq)^2]."""
    keff = check_frac(k_eff, "k_eff")
    qeq = check_frac(q_eq, "q_eq")
    q0 = check_frac(q_start, "q_start")
    q1 = check_frac(q_end, "q_end")
    require_ok(keff > 0, "NONPOS_KEFF", "K_eff must be > 0")
    d0 = q0 - qeq
    d1 = q1 - qeq
    return Fraction(-1, 2) * keff * (d1 * d1 - d0 * d0)


def verify_g1_antagonistic_cone_linearization() -> Dict[str, Any]:
    """Certify G1: exact cone bijection, zero Hessian vs bilinear saddle, and exact elastic energy return."""
    k_ext = Fraction(7, 2)
    k_flx = Fraction(5, 2)
    q_flx = Fraction(-3, 4)
    q_ext = Fraction(5, 4)

    # Grid including boundary rays (a_ext=0, a_flx>0) and (a_ext>0, a_flx=0) plus interior activations
    cone_samples: Tuple[Tuple[Fraction, Fraction], ...] = (
        (Fraction(0, 1), Fraction(1, 1)),
        (Fraction(1, 1), Fraction(0, 1)),
        (Fraction(1, 4), Fraction(3, 4)),
        (Fraction(1, 2), Fraction(1, 2)),
        (Fraction(3, 5), Fraction(2, 5)),
        (Fraction(2, 1), Fraction(1, 3)),
        (Fraction(1, 3), Fraction(5, 2)),
        (Fraction(4, 3), Fraction(7, 5)),
    )
    q_probes: Tuple[Fraction, ...] = (Fraction(-1, 1), Fraction(-1, 4), Fraction(1, 3), Fraction(3, 2))

    bijection_matches = 0
    pos_stiff_matches = 0
    hull_matches = 0
    torque_identities = 0
    for ae, af in cone_samples:
        keff, qeq = antagonistic_forward_q(ae, af, k_ext, k_flx, q_ext, q_flx)
        ae2, af2 = antagonistic_inverse_q(keff, qeq, k_ext, k_flx, q_ext, q_flx)
        keff2, qeq2 = antagonistic_forward_q(ae2, af2, k_ext, k_flx, q_ext, q_flx)
        if (ae2, af2, keff2, qeq2) == (ae, af, keff, qeq):
            bijection_matches += 1
        if keff > 0:
            pos_stiff_matches += 1
        if q_flx <= qeq <= q_ext:
            hull_matches += 1
        for qp in q_probes:
            t_ant = antagonistic_torque_q(ae, af, k_ext, k_flx, q_ext, q_flx, qp)
            t_eq = keff * (qeq - qp)
            if t_ant == t_eq:
                torque_identities += 1

    # Exact Hessian / midpoint linearity comparison:
    # Antagonistic law: midpoint defect == 0/1 identically (Hessian = [[0, 0], [0, 0]], det = 0).
    a1 = (Fraction(1, 2), Fraction(3, 2))
    a2 = (Fraction(5, 2), Fraction(1, 2))
    q_test = Fraction(1, 5)
    t_mid_ant = antagonistic_torque_q(
        (a1[0] + a2[0]) / 2, (a1[1] + a2[1]) / 2, k_ext, k_flx, q_ext, q_flx, q_test
    )
    t_avg_ant = (
        antagonistic_torque_q(a1[0], a1[1], k_ext, k_flx, q_ext, q_flx, q_test)
        + antagonistic_torque_q(a2[0], a2[1], k_ext, k_flx, q_ext, q_flx, q_test)
    ) / 2
    ant_midpoint_defect = t_mid_ant - t_avg_ant

    # Bilinear position-stiffness law tau_ps(k, q_eq; q) = k*(q_eq - q):
    # Derive exact 2x2 Hessian H_ps via exact rational 2nd-order finite differences over Q!
    k1, q1 = Fraction(2, 1), Fraction(-1, 2)
    k2, q2 = Fraction(6, 1), Fraction(1, 2)
    t_mid_ps = ((k1 + k2) / 2) * (((q1 + q2) / 2) - q_test)
    t_avg_ps = (k1 * (q1 - q_test) + k2 * (q2 - q_test)) / 2
    ps_midpoint_defect = t_mid_ps - t_avg_ps
    ps_expected_defect = Fraction(-1, 4) * (k1 - k2) * (q1 - q2)

    def _tau_ps(kv: Fraction, qv: Fraction) -> Fraction:
        return kv * (qv - q_test)

    hk = Fraction(1, 2)
    hq = Fraction(1, 2)
    h_kk = (_tau_ps(k1 + hk, q1) - 2 * _tau_ps(k1, q1) + _tau_ps(k1 - hk, q1)) / (hk * hk)
    h_qq = (_tau_ps(k1, q1 + hq) - 2 * _tau_ps(k1, q1) + _tau_ps(k1, q1 - hq)) / (hq * hq)
    h_kq = (_tau_ps(k1 + hk, q1 + hq) - _tau_ps(k1 + hk, q1 - hq) - _tau_ps(k1 - hk, q1 + hq) + _tau_ps(k1 - hk, q1 - hq)) / (4 * hk * hq)
    h_ps_det = h_kk * h_qq - h_kq * h_kq
    # Pad 2x2 H_ps into 3x3 with 0 to derive exact Sylvester inertia via symmetric_inertia_3x3_q (subtract 1 zero!)
    in_ps_3 = symmetric_inertia_3x3_q(((h_kk, h_kq, Fraction(0)), (h_kq, h_qq, Fraction(0)), (Fraction(0), Fraction(0), Fraction(0))))
    h_ps_inertia = [in_ps_3[0], in_ps_3[1], in_ps_3[2] - 1]

    # Exact elastic storage & return over stance-loading (q_eq -> q_peak) and rebound (q_peak -> q_eq)
    keff_el, qeq_el = antagonistic_forward_q(Fraction(1, 1), Fraction(1, 1), k_ext, k_flx, q_ext, q_flx)
    q_peak = qeq_el - Fraction(1, 2)
    dw_store = spring_work_q(keff_el, qeq_el, qeq_el, q_peak)  # strictly negative (braking absorption!)
    dw_return = spring_work_q(keff_el, qeq_el, q_peak, qeq_el)  # strictly positive (elastic propulsion!)
    dw_cycle = dw_store + dw_return

    g1_passed = (
        bijection_matches,
        pos_stiff_matches,
        hull_matches,
        torque_identities,
        ant_midpoint_defect,
        ps_midpoint_defect == ps_expected_defect,
        h_ps_det,
        h_ps_inertia,
        dw_store < 0,
        dw_return > 0,
        dw_cycle == 0,
    ) == (len(cone_samples), len(cone_samples), len(cone_samples), len(cone_samples) * len(q_probes), Fraction(0), True, Fraction(-1), [1, 1, 0], True, True, True)

    return {
        "gate": "G1_W15_OBS_3_ANTAGONISTIC_CONE_LINEARIZATION",
        "cone_samples_tested": len(cone_samples),
        "bijection_exact_matches": bijection_matches,
        "positive_stiffness_matches": pos_stiff_matches,
        "convex_hull_matches": hull_matches,
        "torque_identity_matches": torque_identities,
        "antagonistic_midpoint_defect": frac_str(ant_midpoint_defect),
        "position_stiffness_midpoint_defect": frac_str(ps_midpoint_defect),
        "position_stiffness_defect_formula_exact": ps_midpoint_defect == ps_expected_defect,
        "position_stiffness_hessian_det": frac_str(h_ps_det),
        "position_stiffness_hessian_inertia": h_ps_inertia,
        "elastic_k_eff": frac_str(keff_el),
        "elastic_q_eq": frac_str(qeq_el),
        "elastic_dw_store": frac_str(dw_store),
        "elastic_dw_return": frac_str(dw_return),
        "elastic_dw_cycle": frac_str(dw_cycle),
        "elastic_braking_negative": dw_store < 0,
        "elastic_return_positive": dw_return > 0,
        "elastic_cycle_zero": dw_cycle == 0,
        "passed": g1_passed,
    }


# ---------------------------------------------------------------------------
# G2 (W15-OBS-4): Commissural V0v/V0d vs V3 Z_2 Gait Bifurcation & Krein Inertia
# ---------------------------------------------------------------------------


def symmetric_inertia_3x3_q(mat: Sequence[Sequence[Fraction]]) -> Tuple[int, int, int]:
    """Exact pure-Q Sylvester / congruence inertia (n_pos, n_neg, n_zero) of any symmetric 3x3 Q-matrix."""
    require_ok(len(mat) == 3 and all(len(r) == 3 for r in mat), "BAD_MAT3", "Expected 3x3 matrix")
    a: List[List[Fraction]] = [[check_frac(mat[i][j], "m") for j in range(3)] for i in range(3)]
    for i in range(3):
        for j in range(i + 1, 3):
            require_ok(a[i][j] == a[j][i], "NOT_SYMMETRIC", "Hessian must be symmetric")

    # Exact congruence reduction (diagonalize via symmetric row/col elimination with 1x1 or 2x2 hyperbolic pivots)
    n_pos = 0
    n_neg = 0
    n_zero = 0
    idx = 0
    while idx < 3:
        # Look for a nonzero diagonal entry at or after idx
        piv = -1
        for k in range(idx, 3):
            if a[k][k] != 0:
                piv = k
                break
        if piv != -1:
            if piv != idx:
                a[idx], a[piv] = a[piv], a[idx]
                for r in range(3):
                    a[r][idx], a[r][piv] = a[r][piv], a[r][idx]
            d = a[idx][idx]
            if d > 0:
                n_pos += 1
            else:
                n_neg += 1
            for r in range(idx + 1, 3):
                fac = a[r][idx] / d
                if fac != 0:
                    for c in range(idx + 1, 3):
                        a[r][c] -= fac * a[idx][c]
            idx += 1
        else:
            # Remaining block has all-zero diagonal; check for nonzero off-diagonal (hyperbolic 2x2 block -> +1, -1!)
            off: Optional[Tuple[int, int]] = None
            for r in range(idx, 3):
                for c in range(r + 1, 3):
                    if a[r][c] != 0:
                        off = (r, c)
                        break
                if off is not None:
                    break
            if off is None:
                n_zero += 3 - idx
                break
            r0, c0 = off
            # Congruence x_r0 -> x_r0 + x_c0 puts 2*a[r0][c0] != 0 onto diagonal a[r0][r0]!
            for k in range(idx, 3):
                a[r0][k] += a[c0][k]
            for k in range(idx, 3):
                a[k][r0] += a[k][c0]
    return n_pos, n_neg, n_zero


def gait_1d_curvatures_q(k_v0: Any, w_v0: Any, w_v3: Any) -> Dict[str, Any]:
    """Exact 1D interlimb potential V(phi) = (k*w_V0 - w_V3)*cos(phi) curvatures & stability swap."""
    kv = check_frac(k_v0, "k_v0")
    wv0 = check_frac(w_v0, "w_v0")
    wv3 = check_frac(w_v3, "w_v3")
    require_ok(wv0 > 0 and wv3 >= 0 and kv >= 0, "BAD_GAIT_WEIGHTS", "Require w_V0 > 0, w_V3 >= 0, k_v0 >= 0")

    k_crit = wv3 / wv0
    curv_trot = kv * wv0 - wv3
    curv_bound = -curv_trot
    trot_neg = 1 if curv_trot < 0 else 0
    bound_neg = 1 if curv_bound < 0 else 0
    return {
        "k_v0": frac_str(kv),
        "k_crit": frac_str(k_crit),
        "curv_trot": frac_str(curv_trot),
        "curv_bound": frac_str(curv_bound),
        "trot_krein_neg": trot_neg,
        "bound_krein_neg": bound_neg,
        "trot_stable": curv_trot > 0,
        "bound_stable": curv_bound > 0,
    }


def quadruped_t4_reduced_hessian_q(
    w_lr: Fraction,
    w_side: Fraction,
    w_diag: Fraction,
    gait: str,
) -> Tuple[Tuple[Fraction, Fraction, Fraction], ...]:
    """Exact 3x3 reduced Hessian on T^4/S^1 (theta_HR = 0 gauge) at Trot (0,pi,pi,0) or Bound (pi,pi,0,0)."""
    require_ok(gait in ("trot", "bound"), "BAD_GAIT", "gait must be 'trot' or 'bound'")
    if gait == "trot":
        e_lr = w_lr
        e_side = w_side
        e_diag = w_diag
    else:
        e_lr = -w_lr
        e_side = w_side
        e_diag = -w_diag
    # Reduced graph Laplacian on vertices (0=FL, 1=FR, 2=HL) with vertex 3=HR grounded:
    # Edges: LR=(0,1),(2,3); side=(0,2),(1,3); diag=(0,3),(1,2)
    return (
        (e_lr + e_side + e_diag, -e_lr, -e_side),
        (-e_lr, e_lr + e_side + e_diag, -e_diag),
        (-e_side, -e_diag, e_lr + e_side + e_diag),
    )


def verify_g2_commissural_gait_bifurcation() -> Dict[str, Any]:
    """Certify G2: 1D & 4-limb T^4/S^1 V0/V3 Krein-inertia stability swap & V3 ablation theorem."""
    w_v0 = Fraction(4, 1)
    w_v3 = Fraction(1, 1)
    k_crit = w_v3 / w_v0  # exact 1/4 = 0.25 (matching Rat NCAP Fig. 7B transition zone!)

    # 1D phase potential across k = 1 (intact), k = 1/4 (exact critical), k = 0 (V0 knockout)
    g1d_intact = gait_1d_curvatures_q(Fraction(1, 1), w_v0, w_v3)
    g1d_crit = gait_1d_curvatures_q(k_crit, w_v0, w_v3)
    g1d_ko = gait_1d_curvatures_q(Fraction(0, 1), w_v0, w_v3)

    # V3 ablation theorem (Fig. 7C): scaling w_V3 from 1 -> 0 strictly increases Trot curvature by +w_V3
    g1d_v3_ablated = gait_1d_curvatures_q(Fraction(1, 1), w_v0, Fraction(0, 1))
    v3_ablation_curv_gain = Fraction(g1d_v3_ablated["curv_trot"]) - Fraction(g1d_intact["curv_trot"])

    # 4-limb T^4/S^1 exact 3x3 reduced Hessian Sylvester inertia (s = 1/2, d = 1/4)
    w_side = Fraction(1, 2)
    w_diag = Fraction(1, 4)
    k_crit_4d = (w_v3 - w_diag) / w_v0  # exact 3/16
    c_intact = Fraction(1, 1) * w_v0 - w_v3  # 3
    c_crit_4d = k_crit_4d * w_v0 - w_v3  # -1/4
    c_ko = Fraction(0, 1) * w_v0 - w_v3  # -1
    c_v3_ko = Fraction(1, 1) * w_v0  # 4

    h_trot_intact = quadruped_t4_reduced_hessian_q(c_intact, w_side, w_diag, "trot")
    h_bound_intact = quadruped_t4_reduced_hessian_q(c_intact, w_side, w_diag, "bound")
    h_trot_crit = quadruped_t4_reduced_hessian_q(c_crit_4d, w_side, w_diag, "trot")
    h_bound_crit = quadruped_t4_reduced_hessian_q(c_crit_4d, w_side, w_diag, "bound")
    h_trot_ko = quadruped_t4_reduced_hessian_q(c_ko, w_side, w_diag, "trot")
    h_bound_ko = quadruped_t4_reduced_hessian_q(c_ko, w_side, w_diag, "bound")
    h_trot_v3ko = quadruped_t4_reduced_hessian_q(c_v3_ko, w_side, w_diag, "trot")

    in_trot_intact = list(symmetric_inertia_3x3_q(h_trot_intact))
    in_bound_intact = list(symmetric_inertia_3x3_q(h_bound_intact))
    in_trot_crit = list(symmetric_inertia_3x3_q(h_trot_crit))
    in_bound_crit = list(symmetric_inertia_3x3_q(h_bound_crit))
    in_trot_ko = list(symmetric_inertia_3x3_q(h_trot_ko))
    in_bound_ko = list(symmetric_inertia_3x3_q(h_bound_ko))
    in_trot_v3ko = list(symmetric_inertia_3x3_q(h_trot_v3ko))

    tr_trot_intact = sum((h_trot_intact[i][i] for i in range(3)), Fraction(0))
    tr_trot_v3ko = sum((h_trot_v3ko[i][i] for i in range(3)), Fraction(0))
    trace_gain = tr_trot_v3ko - tr_trot_intact

    g2_passed = (
        g1d_intact["trot_stable"],
        g1d_intact["bound_stable"],
        g1d_crit["curv_trot"],
        g1d_ko["trot_stable"],
        g1d_ko["bound_stable"],
        v3_ablation_curv_gain,
        in_trot_intact,
        in_bound_intact,
        in_trot_crit,
        in_bound_crit,
        in_trot_ko,
        in_bound_ko,
        in_trot_v3ko,
        trace_gain > 0,
    ) == (True, False, "0/1", False, True, w_v3, [3, 0, 0], [1, 2, 0], [2, 0, 1], [2, 0, 1], [1, 2, 0], [3, 0, 0], [3, 0, 0], True)

    return {
        "gate": "G2_W15_OBS_4_COMMISSURAL_V0_V3_GAIT_BIFURCATION",
        "w_v0": frac_str(w_v0),
        "w_v3": frac_str(w_v3),
        "k_crit_1d": frac_str(k_crit),
        "k_crit_4d_with_diag": frac_str(k_crit_4d),
        "gait_1d_intact": g1d_intact,
        "gait_1d_critical": g1d_crit,
        "gait_1d_v0_knockout": g1d_ko,
        "gait_1d_v3_ablated": g1d_v3_ablated,
        "v3_ablation_curv_gain_1d": frac_str(v3_ablation_curv_gain),
        "t4_inertia_trot_intact": in_trot_intact,
        "t4_inertia_bound_intact": in_bound_intact,
        "t4_inertia_trot_at_crit": in_trot_crit,
        "t4_inertia_bound_at_crit": in_bound_crit,
        "t4_inertia_trot_v0_ko": in_trot_ko,
        "t4_inertia_bound_v0_ko": in_bound_ko,
        "t4_inertia_trot_v3_ko": in_trot_v3ko,
        "t4_trot_trace_intact": frac_str(tr_trot_intact),
        "t4_trot_trace_v3_ko": frac_str(tr_trot_v3ko),
        "t4_v3_ablation_trace_gain": frac_str(trace_gain),
        "passed": g2_passed,
    }


# ---------------------------------------------------------------------------
# G3: HoloSphere Antagonistic Dual-Pole Gate Transfer
# ---------------------------------------------------------------------------


def antagonistic_dual_pole_step_q(
    x: Sequence[Any],
    u_pos: Sequence[Any],
    u_neg: Sequence[Any],
    g_pos: Any,
    g_neg: Any,
) -> Tuple[Tuple[Fraction, ...], Fraction]:
    """Fail-closed HoloSphere dual-pole antagonistic update: x' = x + g+(u+-x) + g-(u--x)."""
    xv = tuple(check_frac(v, "x") for v in x)
    up = tuple(check_frac(v, "u_pos") for v in u_pos)
    un = tuple(check_frac(v, "u_neg") for v in u_neg)
    gp = check_frac(g_pos, "g_pos")
    gn = check_frac(g_neg, "g_neg")

    require_ok(len(xv) >= 1 and len(xv) == len(up) and len(xv) == len(un), "GATE_DIM", "Vectors must have equal nonzero length")
    require_ok(gp >= 0 and gn >= 0, "NEG_GATE", "Antagonistic gates g_pos, g_neg must be >= 0")
    require_ok(gp + gn <= Fraction(1, 1), "GATE_SUM_GT_ONE", "Require g_pos + g_neg <= 1 for contractive convex hull")

    lam = Fraction(1, 1) - gp - gn
    x_next = tuple(xv[i] + gp * (up[i] - xv[i]) + gn * (un[i] - xv[i]) for i in range(len(xv)))
    return x_next, lam


def _vec_norm_sq_q(v: Sequence[Fraction]) -> Fraction:
    return sum((c * c for c in v), Fraction(0))


def verify_g3_holosphere_antagonistic_gate() -> Dict[str, Any]:
    """Certify G3: exact contractive damping 0 <= lam <= 1, convex-hull & B^d clamping, vs unconstrained blowup."""
    u_pos = (Fraction(3, 5), Fraction(4, 5), Fraction(0, 1), Fraction(0, 1))  # ||u+||^2 == 1
    u_neg = (Fraction(-3, 5), Fraction(0, 1), Fraction(4, 5), Fraction(0, 1))  # ||u-||^2 == 1
    x1 = (Fraction(1, 2), Fraction(-1, 2), Fraction(1, 2), Fraction(-1, 2))  # ||x1||^2 == 1
    x2 = (Fraction(-1, 2), Fraction(1, 2), Fraction(-1, 4), Fraction(1, 4))  # ||x2||^2 == 5/8 <= 1

    gate_pairs: Tuple[Tuple[Fraction, Fraction], ...] = (
        (Fraction(0, 1), Fraction(0, 1)),
        (Fraction(1, 2), Fraction(1, 2)),
        (Fraction(1, 4), Fraction(1, 2)),
        (Fraction(3, 5), Fraction(1, 5)),
        (Fraction(2, 7), Fraction(3, 7)),
    )

    contraction_exact = 0
    non_expansive_ok = 0
    coord_hull_ok = 0
    ball_invariant_ok = 0
    equiv_cone_ok = 0
    for gp, gn in gate_pairs:
        x1_next, lam = antagonistic_dual_pole_step_q(x1, u_pos, u_neg, gp, gn)
        x2_next, _ = antagonistic_dual_pole_step_q(x2, u_pos, u_neg, gp, gn)
        d0_sq = _vec_norm_sq_q(tuple(a - b for a, b in zip(x1, x2)))
        d1_sq = _vec_norm_sq_q(tuple(a - b for a, b in zip(x1_next, x2_next)))
        if d1_sq == lam * lam * d0_sq:
            contraction_exact += 1
        if d1_sq <= d0_sq:
            non_expansive_ok += 1
        if all(min(x1[i], u_pos[i], u_neg[i]) <= x1_next[i] <= max(x1[i], u_pos[i], u_neg[i]) for i in range(4)):
            if all(min(x2[i], u_pos[i], u_neg[i]) <= x2_next[i] <= max(x2[i], u_pos[i], u_neg[i]) for i in range(4)):
                coord_hull_ok += 1
        if max(_vec_norm_sq_q(x1_next), _vec_norm_sq_q(x2_next)) <= Fraction(1, 1):
            ball_invariant_ok += 1
        # Verify exact equivalence x' == (1 - K_gate) x + K_gate u_eq when K_gate = gp + gn > 0
        k_gate = gp + gn
        if k_gate > 0:
            u_eq = tuple((gp * u_pos[i] + gn * u_neg[i]) / k_gate for i in range(4))
            x1_eq = tuple((Fraction(1, 1) - k_gate) * x1[i] + k_gate * u_eq[i] for i in range(4))
            if x1_eq == x1_next:
                equiv_cone_ok += 1
        else:
            if x1_next == x1:
                equiv_cone_ok += 1

    # Unconstrained multiplicative counterexample (g_pos = 3/2, g_neg = 1 -> lam = -3/2 -> lam^2 = 9/4 > 1, escapes B^d!)
    gp_bad, gn_bad = Fraction(3, 2), Fraction(1, 1)
    lam_bad = Fraction(1, 1) - gp_bad - gn_bad
    x1_bad = tuple(x1[i] + gp_bad * (u_pos[i] - x1[i]) + gn_bad * (u_neg[i] - x1[i]) for i in range(4))
    x2_bad = tuple(x2[i] + gp_bad * (u_pos[i] - x2[i]) + gn_bad * (u_neg[i] - x2[i]) for i in range(4))
    d0_sq_b = _vec_norm_sq_q(tuple(a - b for a, b in zip(x1, x2)))
    d1_sq_b = _vec_norm_sq_q(tuple(a - b for a, b in zip(x1_bad, x2_bad)))
    escapes_ball = _vec_norm_sq_q(x1_bad) > Fraction(1, 1)

    n_gp = len(gate_pairs)
    g3_passed = (
        contraction_exact,
        non_expansive_ok,
        coord_hull_ok,
        ball_invariant_ok,
        equiv_cone_ok,
        escapes_ball,
    ) == (n_gp, n_gp, n_gp, n_gp, n_gp, True)

    return {
        "gate": "G3_HOLOSPHERE_ANTAGONISTIC_DUAL_POLE_GATE",
        "gate_pairs_tested": n_gp,
        "contraction_exact_matches": contraction_exact,
        "non_expansive_matches": non_expansive_ok,
        "coord_convex_hull_matches": coord_hull_ok,
        "unit_ball_invariant_matches": ball_invariant_ok,
        "cone_equivalence_matches": equiv_cone_ok,
        "unconstrained_lam_eff": frac_str(lam_bad),
        "unconstrained_expansion_ratio_sq": frac_str(d1_sq_b / d0_sq_b),
        "unconstrained_x1_norm_sq": frac_str(_vec_norm_sq_q(x1_bad)),
        "unconstrained_escapes_unit_ball": escapes_ball,
        "passed": g3_passed,
    }


def validate_certificate_payload(payload: Dict[str, Any]) -> None:
    """Fail-closed B1 gate validator enforcing every G1/G2/G3 invariant and boolean before signing/accepting."""
    g1 = payload["g1_antagonistic_cone_linearization"]
    require_ok(
        (
            g1["bijection_exact_matches"],
            g1["positive_stiffness_matches"],
            g1["convex_hull_matches"],
            g1["torque_identity_matches"],
            g1["antagonistic_midpoint_defect"],
            g1["position_stiffness_defect_formula_exact"],
            g1["position_stiffness_hessian_det"],
            g1["position_stiffness_hessian_inertia"],
            g1["elastic_braking_negative"],
            g1["elastic_return_positive"],
            g1["elastic_cycle_zero"],
            g1["passed"],
        ) == (8, 8, 8, 32, "0/1", True, "-1/1", [1, 1, 0], True, True, True, True),
        "G1_CERT_INVALID",
        "G1 antagonistic cone invariants failed",
    )
    g2 = payload["g2_commissural_gait_bifurcation"]
    require_ok(
        (
            g2["k_crit_1d"],
            g2["k_crit_4d_with_diag"],
            g2["v3_ablation_curv_gain_1d"],
            g2["t4_inertia_trot_intact"],
            g2["t4_inertia_bound_intact"],
            g2["t4_inertia_trot_at_crit"],
            g2["t4_inertia_bound_at_crit"],
            g2["t4_inertia_trot_v0_ko"],
            g2["t4_inertia_bound_v0_ko"],
            g2["t4_inertia_trot_v3_ko"],
            g2["t4_v3_ablation_trace_gain"],
            g2["passed"],
        ) == ("1/4", "3/16", "1/1", [3, 0, 0], [1, 2, 0], [2, 0, 1], [2, 0, 1], [1, 2, 0], [3, 0, 0], [3, 0, 0], "3/1", True),
        "G2_CERT_INVALID",
        "G2 commissural gait bifurcation invariants failed",
    )
    g3 = payload["g3_holosphere_antagonistic_gate"]
    require_ok(
        (
            g3["contraction_exact_matches"],
            g3["non_expansive_matches"],
            g3["coord_convex_hull_matches"],
            g3["unit_ball_invariant_matches"],
            g3["cone_equivalence_matches"],
            g3["unconstrained_escapes_unit_ball"],
            g3["passed"],
        ) == (5, 5, 5, 5, 5, True, True),
        "G3_CERT_INVALID",
        "G3 HoloSphere dual-pole gate invariants failed",
    )
    require_ok(payload["all_passed"] is True, "ALL_PASSED_INVALID", "all_passed must be True")


def build_certificate() -> Dict[str, Any]:
    g1 = verify_g1_antagonistic_cone_linearization()
    g2 = verify_g2_commissural_gait_bifurcation()
    g3 = verify_g3_holosphere_antagonistic_gate()
    payload: Dict[str, Any] = {
        "schema": SCHEMA_S127,
        "prereg_w15_sha256": PREREG_W15_SHA256,
        "g1_antagonistic_cone_linearization": g1,
        "g2_commissural_gait_bifurcation": g2,
        "g3_holosphere_antagonistic_gate": g3,
        "all_passed": (g1["passed"], g2["passed"], g3["passed"]) == (True, True, True),
    }
    validate_certificate_payload(payload)
    validate_json_tree_no_floats(payload)
    payload_sha = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    cert: Dict[str, Any] = {"payload": payload, "payload_sha256": payload_sha}
    cert["certificate_sha256"] = hashlib.sha256(_canonical_json_bytes(cert)).hexdigest()
    return cert


def check_certificate_file(cert_path: Path) -> Dict[str, Any]:
    """Fail-closed verification of saved certificate against invariants, canonical SHA-256, and fresh replay."""
    try:
        obj = json.loads(cert_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise RatNCAPError("CERT_LOAD_FAIL", str(exc)) from exc

    validate_json_tree_no_floats(obj)
    require_ok(type(obj) is dict, "CERT_NOT_DICT", "Certificate must be JSON object")
    require_ok(set(obj.keys()) == {"payload", "payload_sha256", "certificate_sha256"}, "CERT_KEYS", "Unexpected keys")
    payload = obj["payload"]
    p_sha = obj["payload_sha256"]
    c_sha = obj["certificate_sha256"]
    require_ok(type(p_sha) is str and type(c_sha) is str, "CERT_HASH_TYPE", "Hashes must be str")

    exp_p = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    require_ok(hmac.compare_digest(p_sha, exp_p), "PAYLOAD_SHA_MISMATCH", "payload_sha256 mismatch")

    inner = {"payload": payload, "payload_sha256": p_sha}
    exp_c = hashlib.sha256(_canonical_json_bytes(inner)).hexdigest()
    require_ok(hmac.compare_digest(c_sha, exp_c), "CERT_SHA_MISMATCH", "certificate_sha256 mismatch")

    validate_certificate_payload(payload)
    fresh = build_certificate()
    require_ok(hmac.compare_digest(c_sha, fresh["certificate_sha256"]), "REPLAY_MISMATCH", "Replay mismatch")
    return obj


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Track S127 pure-Q Rat NCAP cone & gait bifurcation oracle")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", type=Path, default=None)
    parser.add_argument("--check", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        if args.check is not None:
            cert = check_certificate_file(args.check)
        else:
            cert = build_certificate()
            if args.write is not None:
                args.write.write_text(
                    json.dumps(cert, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
                    encoding="utf-8",
                )
    except RatNCAPError as exc:
        sys.stderr.write(f"FAIL {exc.code}: {exc.detail}\n")
        return 2

    if args.json:
        sys.stdout.write(json.dumps(cert, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n")
    else:
        sys.stdout.write(f"PASS {SCHEMA_S127} certificate_sha256={cert['certificate_sha256']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
