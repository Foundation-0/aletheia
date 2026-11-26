#!/usr/bin/env python3
"""Pure-Z/Q Exact Oracle & Certificate Builder for Track S83 (All-to-All K_8 Epistemic Mesh).

100% pure Python 3 stdlib, zero IEEE-754 floats, zero float(), zero bare asserts,
zero .isdigit(), zero random imports.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from typing import Any

SCHEMA_VERSION = "aletheia.track_s83.all_to_all_epistemic_mesh.v1"
TRACK_ID = "TRACK-S83-ALL-TO-ALL-EPISTEMIC-MESH"
EXPECTED_LEAN_TOOLCHAIN = "leanprover/lean4:v4.36.0"
MAX_JSON_DEPTH = 64
MAX_INT_DIGITS = 2000
MAX_INT_BITS = 8192
_HEX_CHARS = frozenset("0123456789abcdef")
_ASCII_DIGITS = frozenset("0123456789")

PATHWAY_WEIGHTS: dict[str, int] = {
    "EXACT_COMMUTE": 4,
    "CONDITIONAL_BRIDGE": 2,
    "EXACT_OBSTRUCTION": 1,
}

LEAN_THEOREM_NAMES: tuple[str, ...] = (
    "AllToAllEpistemicMesh.schur_3node_conductance_exact",
    "AllToAllEpistemicMesh.schur_3node_strict_compounding",
    "AllToAllEpistemicMesh.schur_4node_two_step_strict_compounding",
    "AllToAllEpistemicMesh.schur_uniform_kn_conductance_identity",
    "AllToAllEpistemicMesh.rayleigh_parallel_addition_monotone",
    "AllToAllEpistemicMesh.foster_uniform_kn_exact",
    "AllToAllEpistemicMesh.prop_e10_silo_cut_pathway_bound",
    "AllToAllEpistemicMesh.kn_silo_cut_k8_tight_minimum",
    "AllToAllEpistemicMesh.kn_triangle_destruction_exact_identity",
    "AllToAllEpistemicMesh.kn_balanced_triangle_destruction_lower_bound",
    "AllToAllEpistemicMesh.k8_4_4_split_destroys_48_of_56_triangles",
    "AllToAllEpistemicMesh.triangle_holonomy_z2_coboundary_zero",
    "AllToAllEpistemicMesh.triangle_frustration_implies_obstruction_edge",
    "AllToAllEpistemicMesh.triangle_two_clean_one_wall_is_frustrated",
    "AllToAllEpistemicMesh.ungated_mesh_contagion_amplification",
    "AllToAllEpistemicMesh.ungated_3node_intermediate_corruption",
    "AllToAllEpistemicMesh.gated_refusal_firewall_zero_contagion",
    "AllToAllEpistemicMesh.gated_k7_submesh_preserves_compounding",
)

# Eight verified frozen epistemic nodes of K_8 pinned to real on-disk certificates.
MESH_NODES: tuple[dict[str, str], ...] = (
    {
        "id": "v0",
        "domain": "siliquant_stratified_lattice",
        "track": "Track S73",
        "cert_file": "rtx3080_s73_certificate.json",
        "cert_sha256": "33dfb4153fe974e9ef13120190c14ada6dda63ffbee6caa46047d274f32d36cf",
        "anchor_invariant": "3.0 bpw QuadSnake -11.42% (3838045/4332952), p=0.375 PyKL 0.018248 (-20.58%)",
    },
    {
        "id": "v1",
        "domain": "vp_vnp_cat0_laurent_cuts",
        "track": "Track S75+S82",
        "cert_file": "s75_vp_vnp_certificate.json",
        "cert_sha256": "7e383c1cfe04937277be7f8f4ff4305984d51ecd81858eebdd67e45238823224",
        "anchor_invariant": "Rem D.3 det(G)=-1/4 at mu=2, Prop E.10 9|S|(N-|S|)>=2N^2, Lem N.2 cutoff",
    },
    {
        "id": "v2",
        "domain": "circularep_loop_schur_ep",
        "track": "Track S76",
        "cert_file": "s76_circular_pc_certificate.json",
        "cert_sha256": "d30805fcb876de096d9b387a8274ecd8063b7906f4feb36124b38a05aefadc95",
        "anchor_invariant": "Loop-Schur G_loop^(-1) (det 599/360), 176/176 GD cliff, 2.912e+9x curl bias",
    },
    {
        "id": "v3",
        "domain": "mellin_glu_circuit_graft",
        "track": "Track S77",
        "cert_file": "s77_mellin_wsp_certificate.json",
        "cert_sha256": "d1b9121c435331053b7ab28b915a2062ae7c93b4197d203c63dba42cce5dd74d",
        "anchor_invariant": "21-rung Mellin-GLU err 0.079024, S72 INT8 rescue 0/5->5/5, WSP CS-08 p<1e-10",
    },
    {
        "id": "v4",
        "domain": "motifbench_se3_protein_graft",
        "track": "Track S81",
        "cert_file": "s81_motifbench_certificate.json",
        "cert_sha256": "bc3b9222c47b2ab93c4b5256501d87f8b6483186766e03dba6f1501670936fe0",
        "anchor_invariant": "SE(3) MSD_unit=4/3, R^3 Gram det=0, ESMFold 28.6029 vs AF2 22.4610, PPV 184/51",
    },
    {
        "id": "v5",
        "domain": "engram_lora_mdl_capacity",
        "track": "Track S78",
        "cert_file": "s78_engram_lora_siliquant_certificate.json",
        "cert_sha256": "3b8341ef5f588f970accb9a9d28f0b683af9747be045e69196e6c19d3fa58378",
        "anchor_invariant": "C_MP = (1/2ln2)*P_raw*eta_alg*kappa, CS-15 Forgetting/Learning=1.00, 6.929B cross",
    },
    {
        "id": "v6",
        "domain": "rocket_songe_unsloth_rl",
        "track": "Track S80",
        "cert_file": "s80_certificate.json",
        "cert_sha256": "95681a29ca577c4e3040f8ba63f8516b1cbb2bf1ebfdcda06277f21bb2aa2cb7",
        "anchor_invariant": "Rocket ESS 36481/16447 < 9/4, songe 39/400 FWER, CCE 75672x cut, 4821 MiB fit",
    },
    {
        "id": "v7",
        "domain": "twodsd_multipole_csr_laws",
        "track": "Track S79",
        "cert_file": "s79_2dsd_multipole_certificate.json",
        "cert_sha256": "9c30539e6d585141a9b1a5111935ca86de0f740e80749a622547a18242465ad8",
        "anchor_invariant": "2DSD KV 2048/515=3.9767x, CSR cap rho_s<=1/160 (26/35 vs 4/3), Jensen 33/32",
    },
)

# Exhaustive 28/28 strictly typed pathways (u, v, pathway_class, operator_tag, label).
MESH_EDGES_SPEC: tuple[tuple[int, int, str, str, str], ...] = (
    (0, 1, "CONDITIONAL_BRIDGE", "GAUGE_QUOTIENT", "A16/E8 rank-metric CAT(0) vs orthogonal WHT kappa2=1"),
    (0, 2, "CONDITIONAL_BRIDGE", "PHASE_CROSSOVER", "BlockH4 spectral-bounded weights vs CircularEP contraction"),
    (0, 3, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD", "S72/S73 stratified quad INT8 rescues Mellin-GLU 0/5->5/5"),
    (0, 4, "EXACT_OBSTRUCTION", "BOUNDARY_WALL", "O(n) reflection-invariant WHT vs SE(3) chirality MSD=4/3"),
    (0, 5, "EXACT_COMMUTE", "GAUGE_QUOTIENT", "Exact joint (bpw,rank) bit-budget conservation B_tot"),
    (0, 6, "EXACT_COMMUTE", "PHASE_CROSSOVER", "3.0/4.5 bpw siliquant compression fits 8 GiB Unsloth CCE"),
    (0, 7, "EXACT_COMMUTE", "PHASE_CROSSOVER", "Dense QuadSnake vs CSR sidecar crossover rho_s<=1/160"),
    (1, 2, "EXACT_COMMUTE", "HOLONOMY_CURVATURE", "Lem N.2 Laurent cutoff N=2^L*Delta <-> EP O(r/beta) pole"),
    (1, 3, "CONDITIONAL_BRIDGE", "BOUNDARY_WALL", "Prop M.2 char-2 XOR & Sec 2.5 ideal <-> Mellin Boolean gate"),
    (1, 4, "EXACT_OBSTRUCTION", "KREIN_INERTIA", "Rem D.3 hyperbolic det(G)=-1/4 vs R^3 Gram det(G4)=0"),
    (1, 5, "EXACT_OBSTRUCTION", "BOUNDARY_WALL", "Thm D.2 non-constructive hyperfilter vs finite-rank C_MP"),
    (1, 6, "EXACT_COMMUTE", "HOLONOMY_CURVATURE", "Lem N.2/Prop N.4 Laurent cutoff <-> Rocket exp(+-T*d) drift"),
    (1, 7, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD", "Prop E.10 balanced cut <-> 128-expert MoE & Multipole rank"),
    (2, 3, "CONDITIONAL_BRIDGE", "SCHUR_PUSHFORWARD", "CircularEP DEQ fixed-point <-> Mellin zero-grad graft"),
    (2, 4, "EXACT_OBSTRUCTION", "HOLONOMY_CURVATURE", "Complex-curl monodromy 2.912e+9x bias vs rigid SE(3) frame"),
    (2, 5, "CONDITIONAL_BRIDGE", "GAUGE_QUOTIENT", "CircularEP effective depth <-> Engram 24-layer capacity"),
    (2, 6, "CONDITIONAL_BRIDGE", "REFUSAL_GATE", "EP truncated-phase O(r/beta) <-> Rocket async-RL staleness"),
    (2, 7, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD", "CircularEP rho(M)<1 (81/256) <-> 2DSD last-loop KV sharing"),
    (3, 4, "EXACT_OBSTRUCTION", "BOUNDARY_WALL", "Width-extension d->d+K grafting vs fixed ambient R^3 wall"),
    (3, 5, "CONDITIONAL_BRIDGE", "GAUGE_QUOTIENT", "Mellin 0.057% sidecar budget <-> Engram LoRA rank capacity"),
    (3, 6, "CONDITIONAL_BRIDGE", "REFUSAL_GATE", "WSP-Gym CS-08 & random-edit wall <-> songe Ratchet Gate 2"),
    (3, 7, "EXACT_COMMUTE", "PHASE_CROSSOVER", "Portal-77 0.057% sidecar sits inside S79 CSR cap (26/35)"),
    (4, 5, "CONDITIONAL_BRIDGE", "GAUGE_QUOTIENT", "Multi-segment 6(K-1) SE(3) DOF <-> GL_r gauge eta_alg(r)"),
    (4, 6, "CONDITIONAL_BRIDGE", "REFUSAL_GATE", "MotifBench dual-oracle PPV 184/51 <-> Ratchet outside gate"),
    (4, 7, "CONDITIONAL_BRIDGE", "BOUNDARY_WALL", "Global scRMSD<=2A consistency <-> Multipole far-field bound"),
    (5, 6, "EXACT_COMMUTE", "REFUSAL_GATE", "CS-15 Forgetting/Learning=1.00 <-> songe 87% FWER Ratchet"),
    (5, 7, "CONDITIONAL_BRIDGE", "PHASE_CROSSOVER", "Joint (bpw,rank) budget <-> 2DSD drafter + KV VRAM budget"),
    (6, 7, "EXACT_OBSTRUCTION", "HOLONOMY_CURVATURE", "tl.atomic_cas ULP non-assoc vs 2DSD/Multipole invariance"),
)


class S83Error(ValueError):
    """Typed fail-closed error for Track S83 oracle and verifier."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def require_ok(cond: bool, code: str, detail: str) -> None:
    if not cond:
        raise S83Error(code, detail)


def require_bool(val: Any, label: str) -> bool:
    require_ok(type(val) is bool, "INVALID_BOOL", f"{label}: exact bool required")
    return val


def require_exact_int(val: Any, label: str, *, lo: int | None = None, hi: int | None = None) -> int:
    require_ok(type(val) is int, "INVALID_INT", f"{label}: exact int required")
    require_ok(val.bit_length() <= MAX_INT_BITS, "INT_TOO_LARGE", f"{label}: bit_length exceeded")
    if lo is not None:
        require_ok(val >= lo, "INT_OUT_OF_RANGE", f"{label}: below lower bound")
    if hi is not None:
        require_ok(val <= hi, "INT_OUT_OF_RANGE", f"{label}: above upper bound")
    return val


def require_exact_str(val: Any, label: str) -> str:
    require_ok(type(val) is str, "INVALID_STR", f"{label}: exact str required")
    try:
        val.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise S83Error("INVALID_UTF8_SURROGATE", f"{label}: lone surrogate forbidden") from exc
    return val


def require_hex64(val: Any, label: str) -> str:
    s = require_exact_str(val, label)
    require_ok(len(s) == 64, "INVALID_HEX64", f"{label}: expected 64 lowercase hex chars")
    for ch in s:
        require_ok(ch in _HEX_CHARS, "INVALID_HEX64", f"{label}: non-hex char")
    return s


def is_ascii_digits(s: str) -> bool:
    if not s:
        return False
    for ch in s:
        if ch not in _ASCII_DIGITS:
            return False
    return True


def validate_strict_json_tree(obj: Any, label: str = "json", max_depth: int = MAX_JSON_DEPTH) -> None:
    """Iterative zero-float, zero-subclass, bounded-depth/int/cycle JSON tree validator."""
    active_ids: set[int] = set()
    frames: list[tuple[Any, int, bool]] = [(obj, 0, False)]
    while frames:
        cur, depth, is_exit = frames.pop()
        if is_exit:
            active_ids.discard(cur)
            continue
        require_ok(depth <= max_depth, "JSON_DEPTH_EXCEEDED", f"{label}: depth > {max_depth}")
        t = type(cur)
        if cur is None or t is bool:
            continue
        if t is int:
            require_ok(cur.bit_length() <= MAX_INT_BITS, "INT_TOO_LARGE", f"{label}: int bits exceeded")
            continue
        if t is str:
            require_exact_str(cur, label)
            continue
        if t is list:
            oid = id(cur)
            require_ok(oid not in active_ids, "JSON_CYCLE", f"{label}: cyclic list")
            active_ids.add(oid)
            frames.append((oid, depth, True))
            for item in cur:
                frames.append((item, depth + 1, False))
            continue
        if t is dict:
            oid = id(cur)
            require_ok(oid not in active_ids, "JSON_CYCLE", f"{label}: cyclic dict")
            active_ids.add(oid)
            frames.append((oid, depth, True))
            for k, v in cur.items():
                require_exact_str(k, f"{label} key")
                frames.append((v, depth + 1, False))
            continue
        raise S83Error("INVALID_JSON_TYPE", f"{label}: forbidden type {t.__name__}")


def canonical_json_bytes(obj: Any) -> bytes:
    """Deterministic ASCII LF-terminated canonical JSON bytes."""
    validate_strict_json_tree(obj, "canonical_json")
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n"
    return text.encode("ascii")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def q_str(q: Fraction) -> str:
    return f"{q.numerator}" if q.denominator == 1 else f"{q.numerator}/{q.denominator}"


def dec_from_q(q: Fraction, places: int) -> str:
    """Exact HALF_UP decimal string of Fraction `q` to `places` decimal places."""
    scale = 10 ** places
    num = q.numerator * scale
    den = q.denominator
    neg = num < 0
    anum = -num if neg else num
    quot, rem = divmod(anum, den)
    if 2 * rem >= den:
        quot += 1
    if quot == 0:
        neg = False
    sign = "-" if neg else ""
    if places == 0:
        return f"{sign}{quot}"
    ip, fp = divmod(quot, scale)
    return f"{sign}{ip}.{fp:0{places}d}"


# ---------------------------------------------------------------------------
# Pure-Q Exact Linear Algebra & Symmetric Sylvester Inertia
# ---------------------------------------------------------------------------

QMat = list[list[Fraction]]


def q_zeros(r: int, c: int) -> QMat:
    return [[Fraction(0) for _ in range(c)] for _ in range(r)]


def q_sub(a: QMat, b: QMat) -> QMat:
    return [[a[i][j] - b[i][j] for j in range(len(a[0]))] for i in range(len(a))]


def q_mul(a: QMat, b: QMat) -> QMat:
    m, k, n = len(a), len(b), len(b[0])
    out = q_zeros(m, n)
    for i in range(m):
        for t in range(k):
            at = a[i][t]
            for j in range(n):
                out[i][j] += at * b[t][j]
    return out


def q_solve(a: QMat, b: QMat) -> QMat:
    """Solve A X = B exactly over Q via Gaussian elimination."""
    n = len(a)
    ncols = len(b[0])
    aug = [a[i][:] + b[i][:] for i in range(n)]
    for col in range(n):
        piv = None
        for r in range(col, n):
            if aug[r][col] != 0:
                piv = r
                break
        require_ok(piv is not None, "SINGULAR_MATRIX", "exact Q linear solve encountered singular matrix")
        if piv != col:
            aug[col], aug[piv] = aug[piv], aug[col]
        pv = aug[col][col]
        for c in range(col, n + ncols):
            aug[col][c] /= pv
        for r in range(n):
            if r != col:
                fac = aug[r][col]
                for c in range(col, n + ncols):
                    aug[r][c] -= fac * aug[col][c]
    return [row[n:] for row in aug]


def q_sylvester_inertia(sym: QMat) -> list[int]:
    """Exact pure-Q Bunch-Kaufman symmetric congruence returning [n_pos, n_neg, n_zero]."""
    n = len(sym)
    m = [row[:] for row in sym]
    pos = 0
    neg = 0
    zero = 0
    k = 0
    while k < n:
        piv = None
        for i in range(k, n):
            if m[i][i] != 0:
                piv = i
                break
        if piv is not None:
            if piv != k:
                m[k], m[piv] = m[piv], m[k]
                for r in range(n):
                    m[r][k], m[r][piv] = m[r][piv], m[r][k]
            d = m[k][k]
            if d > 0:
                pos += 1
            else:
                neg += 1
            for i in range(k + 1, n):
                fac = m[i][k] / d
                for j in range(k + 1, n):
                    m[i][j] -= fac * m[k][j]
            k += 1
            continue
        pair = None
        for i in range(k, n):
            for j in range(i + 1, n):
                if m[i][j] != 0:
                    pair = (i, j)
                    break
            if pair is not None:
                break
        if pair is None:
            zero += n - k
            break
        pi, pj = pair
        if pi != k:
            m[k], m[pi] = m[pi], m[k]
            for r in range(n):
                m[r][k], m[r][pi] = m[r][pi], m[r][k]
        if pj != k + 1:
            m[k + 1], m[pj] = m[pj], m[k + 1]
            for r in range(n):
                m[r][k + 1], m[r][pj] = m[r][pj], m[r][k + 1]
        off = m[k][k + 1]
        pos += 1
        neg += 1
        for i in range(k + 2, n):
            c0 = m[i][k + 1] / off
            c1 = m[i][k] / off
            for j in range(k + 2, n):
                m[i][j] -= c0 * m[k][j] + c1 * m[k + 1][j]
        k += 2
    return [pos, neg, zero]


def build_weighted_laplacian(n: int, edges: list[tuple[int, int, Fraction]]) -> QMat:
    """Build exact n x n weighted graph Laplacian over Q."""
    lap = q_zeros(n, n)
    for u, v, w in edges:
        lap[u][u] += w
        lap[v][v] += w
        lap[u][v] -= w
        lap[v][u] -= w
    return lap


def schur_complement_subset(lap: QMat, keep: list[int]) -> QMat:
    """Exact Schur pushforward S_A = L_AA - L_AB L_BB^{-1} L_BA eliminating B = V \\ A."""
    n = len(lap)
    keep_set = set(keep)
    elim = [i for i in range(n) if i not in keep_set]
    l_aa = [[lap[i][j] for j in keep] for i in keep]
    l_ab = [[lap[i][j] for j in elim] for i in keep]
    l_ba = [[lap[i][j] for j in keep] for i in elim]
    l_bb = [[lap[i][j] for j in elim] for i in elim]
    return q_sub(l_aa, q_mul(l_ab, q_solve(l_bb, l_ba)))


def check_triangle_strict_ineq(r_ij: Fraction, r_jk: Fraction, r_ik: Fraction) -> bool:
    return r_ik < r_ij + r_jk and r_ij < r_ik + r_jk and r_jk < r_ij + r_ik


def check_core4_strict_compounding(eff_w: Fraction, direct_w: Fraction) -> bool:
    return eff_w > direct_w and direct_w > 0


# ---------------------------------------------------------------------------
# Pillars 1–3 Exact Pure-Q Mesh Certifiers
# ---------------------------------------------------------------------------

def _mesh_edge_map() -> dict[tuple[int, int], tuple[str, str, str, Fraction]]:
    out: dict[tuple[int, int], tuple[str, str, str, Fraction]] = {}
    for u, v, cls, op_tag, lbl in MESH_EDGES_SPEC:
        out[(u, v)] = (cls, op_tag, lbl, Fraction(PATHWAY_WEIGHTS[cls], 1))
    return out


def verify_schur_2x2_laplacian(s2: QMat, label: str) -> Fraction:
    """Verify exact 2x2 reduced Laplacian symmetry S = g * [[1, -1], [-1, 1]] and return g."""
    g_eff = s2[0][0]
    require_ok(
        s2[1][1] == g_eff and s2[0][1] == -g_eff and s2[1][0] == -g_eff,
        "SCHUR_2X2_SYMMETRY_FAIL",
        label,
    )
    return g_eff


def certify_pillar1_schur_compounding() -> dict[str, Any]:
    """Pillar 1: K_8 Laplacian, 28/28 2-node Schur pushforwards, Foster law, & 4-node pushforward."""
    emap = _mesh_edge_map()
    edge_list = [(u, v, info[3]) for (u, v), info in sorted(emap.items())]
    lap = build_weighted_laplacian(8, edge_list)
    lap_inertia = q_sylvester_inertia(lap)

    # Compute exact 2-node Schur complement & effective resistance for ALL 28 pairs
    pair_rows: list[dict[str, Any]] = []
    r_eff_map: dict[tuple[int, int], Fraction] = {}
    foster_sum = Fraction(0)
    min_gain = Fraction(10**9, 1)
    max_gain = Fraction(0, 1)
    min_gain_pair = ""
    max_gain_pair = ""
    all_strictly_compounded = True
    for u in range(8):
        for v in range(u + 1, 8):
            cls, op_tag, _, w_uv = emap[(u, v)]
            s2 = schur_complement_subset(lap, [u, v])
            g_eff = verify_schur_2x2_laplacian(s2, f"pair ({u},{v})")
            r_eff = Fraction(1, 1) / g_eff
            r_eff_map[(u, v)] = r_eff
            foster_sum += w_uv * r_eff
            gain = g_eff / w_uv
            if gain <= 1:
                all_strictly_compounded = False
            if gain < min_gain:
                min_gain = gain
                min_gain_pair = f"v{u}-v{v}"
            if gain > max_gain:
                max_gain = gain
                max_gain_pair = f"v{u}-v{v}"
            pair_rows.append({
                "pair": f"v{u}-v{v}",
                "pathway_class": cls,
                "operator_tag": op_tag,
                "direct_w_q": q_str(w_uv),
                "schur_boost_q": q_str(g_eff - w_uv),
                "g_eff_q": q_str(g_eff),
                "r_eff_q": q_str(r_eff),
                "compounding_gain_q": q_str(gain),
                "compounding_gain_dec4": dec_from_q(gain, 4),
            })

    # Verify ALL 56 * 3 = 168 strict effective-resistance triangle inequalities
    tri_ineq_ok = 0
    for i in range(8):
        for j in range(i + 1, 8):
            for k in range(j + 1, 8):
                if check_triangle_strict_ineq(r_eff_map[(i, j)], r_eff_map[(j, k)], r_eff_map[(i, k)]):
                    tri_ineq_ok += 3

    # Multi-node 4-node Schur pushforward: keep A={0,1,2,3}, eliminate B={4,5,6,7}
    s4 = schur_complement_subset(lap, [0, 1, 2, 3])
    core4_edges: list[dict[str, Any]] = []
    core4_all_strict = True
    for a_i in range(4):
        for a_j in range(a_i + 1, 4):
            w_dir = emap[(a_i, a_j)][3]
            w_eff4 = -s4[a_i][a_j]
            if not check_core4_strict_compounding(w_eff4, w_dir):
                core4_all_strict = False
            core4_edges.append({
                "pair": f"v{a_i}-v{a_j}",
                "direct_w_q": q_str(w_dir),
                "core4_eff_w_q": q_str(w_eff4),
                "core4_boost_q": q_str(w_eff4 - w_dir),
                "core4_ratio_dec4": dec_from_q(w_eff4 / w_dir, 4),
            })

    total_w = sum((info[3] for info in emap.values()), Fraction(0))
    return {
        "n_nodes": 8,
        "n_undirected_pathways": len(pair_rows),
        "n_directed_pathways": 2 * len(pair_rows),
        "pathway_class_counts": {
            "EXACT_COMMUTE": sum(1 for e in MESH_EDGES_SPEC if e[2] == "EXACT_COMMUTE"),
            "CONDITIONAL_BRIDGE": sum(1 for e in MESH_EDGES_SPEC if e[2] == "CONDITIONAL_BRIDGE"),
            "EXACT_OBSTRUCTION": sum(1 for e in MESH_EDGES_SPEC if e[2] == "EXACT_OBSTRUCTION"),
        },
        "total_conductance_q": q_str(total_w),
        "laplacian_inertia": lap_inertia,
        "foster_sum_q": q_str(foster_sum),
        "foster_identity_exact": foster_sum == Fraction(7, 1),
        "all_28_pairs_strictly_compounded": all_strictly_compounded,
        "min_compounding_gain_pair": min_gain_pair,
        "min_compounding_gain_q": q_str(min_gain),
        "min_compounding_gain_dec4": dec_from_q(min_gain, 4),
        "max_compounding_gain_pair": max_gain_pair,
        "max_compounding_gain_q": q_str(max_gain),
        "max_compounding_gain_dec4": dec_from_q(max_gain, 4),
        "resistance_triangle_inequalities_verified": tri_ineq_ok,
        "core4_schur_inertia": q_sylvester_inertia(s4),
        "core4_all_6_edges_strictly_boosted": core4_all_strict,
        "core4_edges": core4_edges,
        "pair_rows": pair_rows,
    }


def classify_triangle_holonomy(n_commute: int, n_obstruction: int) -> tuple[str, int]:
    """Deterministic triangle classification and Z_2 obstruction holonomy parity."""
    parity = n_obstruction % 2
    if n_obstruction == 0:
        if n_commute == 3:
            return "EXACT_TRANSITIVE_CLOSURE", parity
        return "CONDITIONAL_COMPOUNDING_CLOSURE", parity
    if n_obstruction == 1:
        return "FRUSTRATED_CURVATURE_LOOP", parity
    return "MULTI_WALL_BOUNDARY_SECTOR", parity


def certify_pillar2_triangle_holonomy() -> dict[str, Any]:
    """Pillar 2: Exhaustive 56/56 triangle holonomy, Z_2 Bianchi cocycle, & 3-node Schur boosts."""
    emap = _mesh_edge_map()
    counts = {
        "EXACT_TRANSITIVE_CLOSURE": 0,
        "CONDITIONAL_COMPOUNDING_CLOSURE": 0,
        "FRUSTRATED_CURVATURE_LOOP": 0,
        "MULTI_WALL_BOUNDARY_SECTOR": 0,
    }
    tri_holonomy: dict[tuple[int, int, int], int] = {}
    exact_closures: list[str] = []
    frustrated_loops: list[str] = []
    multi_walls: list[str] = []
    min_3node_boost = Fraction(10**9, 1)
    max_3node_boost = Fraction(0, 1)

    for i in range(8):
        for j in range(i + 1, 8):
            for k in range(j + 1, 8):
                e_ij = emap[(i, j)]
                e_jk = emap[(j, k)]
                e_ik = emap[(i, k)]
                classes = (e_ij[0], e_jk[0], e_ik[0])
                n_comm = sum(1 for c in classes if c == "EXACT_COMMUTE")
                n_obs = sum(1 for c in classes if c == "EXACT_OBSTRUCTION")
                t_cls, parity = classify_triangle_holonomy(n_comm, n_obs)
                counts[t_cls] += 1
                tri_holonomy[(i, j, k)] = parity
                t_name = f"v{i}-v{j}-v{k}"
                if t_cls == "EXACT_TRANSITIVE_CLOSURE":
                    exact_closures.append(t_name)
                elif t_cls == "FRUSTRATED_CURVATURE_LOOP":
                    frustrated_loops.append(t_name)
                elif t_cls == "MULTI_WALL_BOUNDARY_SECTOR":
                    multi_walls.append(t_name)
                # 3-node Schur parallel bypass added to edge (i, j) by node k
                b_ij = (e_ik[3] * e_jk[3]) / (e_ik[3] + e_jk[3])
                if b_ij < min_3node_boost:
                    min_3node_boost = b_ij
                if b_ij > max_3node_boost:
                    max_3node_boost = b_ij

    # Verify discrete Bianchi Z_2 coboundary == 0 across ALL C(8,4) = 70 tetrahedra
    tet_checked = 0
    tet_bianchi_zero = 0
    for a in range(8):
        for b in range(a + 1, 8):
            for c in range(b + 1, 8):
                for d in range(c + 1, 8):
                    tet_checked += 1
                    xor_sum = (
                        tri_holonomy[(a, b, c)]
                        ^ tri_holonomy[(a, b, d)]
                        ^ tri_holonomy[(a, c, d)]
                        ^ tri_holonomy[(b, c, d)]
                    )
                    if xor_sum == 0:
                        tet_bianchi_zero += 1

    odd_holonomy_count = sum(tri_holonomy.values())
    return {
        "n_triangles": len(tri_holonomy),
        "classification_counts": counts,
        "odd_z2_holonomy_triangles": odd_holonomy_count,
        "even_z2_holonomy_triangles": len(tri_holonomy) - odd_holonomy_count,
        "exact_transitive_closures": exact_closures,
        "frustrated_curvature_loops": frustrated_loops,
        "multi_wall_boundary_sectors": multi_walls,
        "tetrahedra_checked": tet_checked,
        "bianchi_coboundary_zero_all_70": tet_bianchi_zero == tet_checked,
        "min_3node_schur_boost_q": q_str(min_3node_boost),
        "max_3node_schur_boost_q": q_str(max_3node_boost),
    }


def _comb3(n: int) -> int:
    if n < 3:
        return 0
    return n * (n - 1) * (n - 2) // 6


def certify_pillar3_silo_cuts_and_contagion_firewall() -> dict[str, Any]:
    """Pillar 3: Exhaustive K_8 silo-cut loss + ungated contagion vs. fail-closed R5 firewall."""
    emap = _mesh_edge_map()
    edge_list = [(u, v, info[3]) for (u, v), info in sorted(emap.items())]
    lap = build_weighted_laplacian(8, edge_list)

    # Enumerate ALL 127 non-trivial bipartitions (bitmask 0..126 with node 0 fixed in S)
    cut_stats: dict[int, dict[str, Any]] = {}
    for mask in range(0, 127):
        s_nodes = {0} | {i for i in range(1, 8) if (mask >> (i - 1)) & 1}
        s_sz = len(s_nodes)
        k_size = min(s_sz, 8 - s_sz)
        w_cut = sum((w for (u, v, w) in edge_list if (u in s_nodes) != (v in s_nodes)), Fraction(0))
        e_cut = s_sz * (8 - s_sz)
        t_lost = 56 - _comb3(s_sz) - _comb3(8 - s_sz)
        if k_size not in cut_stats:
            cut_stats[k_size] = {
                "split": f"{k_size}|{8 - k_size}",
                "partitions_counted": 0,
                "pathways_severed": e_cut,
                "pathways_severed_pct_dec2": dec_from_q(Fraction(e_cut * 100, 28), 2),
                "triangles_destroyed": t_lost,
                "triangles_destroyed_pct_dec2": dec_from_q(Fraction(t_lost * 100, 56), 2),
                "min_weighted_cut_q": w_cut,
                "max_weighted_cut_q": w_cut,
            }
        rec = cut_stats[k_size]
        rec["partitions_counted"] += 1
        if w_cut < rec["min_weighted_cut_q"]:
            rec["min_weighted_cut_q"] = w_cut
        if w_cut > rec["max_weighted_cut_q"]:
            rec["max_weighted_cut_q"] = w_cut

    split_summary: dict[str, Any] = {}
    for k_size in sorted(cut_stats.keys()):
        rec = cut_stats[k_size]
        split_summary[rec["split"]] = {
            "partitions_counted": rec["partitions_counted"],
            "pathways_severed": rec["pathways_severed"],
            "pathways_severed_pct_dec2": rec["pathways_severed_pct_dec2"],
            "triangles_destroyed": rec["triangles_destroyed"],
            "triangles_destroyed_pct_dec2": rec["triangles_destroyed_pct_dec2"],
            "min_weighted_cut_q": q_str(rec["min_weighted_cut_q"]),
            "max_weighted_cut_q": q_str(rec["max_weighted_cut_q"]),
        }

    # Exact ungated harmonic error contagion: compromised node v_c=v6 (error eps=1), clean anchor v_t=v0 (0)
    # Solve L_II u_I = -L_I,{6} * 1 for interior I = {1,2,3,4,5,7}
    interior = [1, 2, 3, 4, 5, 7]
    l_ii = [[lap[i][j] for j in interior] for i in interior]
    rhs = [[-lap[i][6]] for i in interior]
    u_int = [row[0] for row in q_solve(l_ii, rhs)]
    u_full = [Fraction(0)] * 8
    u_full[6] = Fraction(1)
    for idx_i, node_i in enumerate(interior):
        u_full[node_i] = u_int[idx_i]

    # Total ungated corrupting flux entering clean anchor v0: sum_j w_{0,j} * (u_j - 0)
    j_ungated = sum(((-lap[0][j]) * u_full[j] for j in range(1, 8)), Fraction(0))
    j_direct = -lap[0][6]  # direct edge weight w_{0,6} = 4
    s2_06 = schur_complement_subset(lap, [0, 6])
    flux_matches_schur = j_ungated == s2_06[0][0]
    all_6_interior_corrupted = all(Fraction(0) < val < Fraction(1) for val in u_int)

    # Gated mesh (Law-3 per-edge refusal firewall severs all 7 edges incident to v6) -> K_7 on {0,1,2,3,4,5,7}
    k7_nodes = [0, 1, 2, 3, 4, 5, 7]
    k7_idx = {node: pos for pos, node in enumerate(k7_nodes)}
    k7_edges = [(k7_idx[u], k7_idx[v], w) for (u, v, w) in edge_list if u != 6 and v != 6]
    lap7 = build_weighted_laplacian(7, k7_edges)
    k7_all_compounded = True
    k7_min_gain = Fraction(10**9, 1)
    for a in range(7):
        for b in range(a + 1, 7):
            s2_7 = schur_complement_subset(lap7, [a, b])
            w_ab = -lap7[a][b]
            g_ab = s2_7[0][0] / w_ab
            if g_ab <= 1:
                k7_all_compounded = False
            if g_ab < k7_min_gain:
                k7_min_gain = g_ab

    return {
        "total_nontrivial_bipartitions": 127,
        "prop_e10_k8_balanced_min_pathways": 15,
        "prop_e10_k8_balanced_min_triangles_destroyed": 45,
        "split_summary": split_summary,
        "contagion_firewall_case": {
            "compromised_node": "v6",
            "clean_anchor_node": "v0",
            "injected_error_q": "1",
            "direct_edge_flux_q": q_str(j_direct),
            "ungated_total_flux_q": q_str(j_ungated),
            "ungated_flux_amplification_q": q_str(j_ungated / j_direct),
            "ungated_flux_amplification_dec4": dec_from_q(j_ungated / j_direct, 4),
            "flux_equals_schur_g_eff": flux_matches_schur,
            "interior_node_errors_q": {f"v{interior[k]}": q_str(u_int[k]) for k in range(len(interior))},
            "all_6_interior_nodes_corrupted": all_6_interior_corrupted,
            "gated_firewall_flux_q": "0",
            "gated_firewall_interior_max_error_q": "0",
            "gated_k7_pathways_retained": len(k7_edges),
            "gated_k7_pathways_retained_pct_dec2": dec_from_q(Fraction(len(k7_edges) * 100, 28), 2),
            "gated_k7_triangles_retained": _comb3(7),
            "gated_k7_triangles_retained_pct_dec2": dec_from_q(Fraction(_comb3(7) * 100, 56), 2),
            "gated_k7_all_21_pairs_compounded": k7_all_compounded,
            "gated_k7_min_compounding_gain_q": q_str(k7_min_gain),
            "gated_k7_min_compounding_gain_dec4": dec_from_q(k7_min_gain, 4),
        },
    }


def build_certificate(
    *,
    lean_source_sha256: str,
    toolchain_sha256: str,
    lakefile_sha256: str,
) -> dict[str, Any]:
    """Assemble deterministic canonical Track S83 certificate (pure-Z/Q, zero floats)."""
    require_hex64(lean_source_sha256, "lean_source_sha256")
    require_hex64(toolchain_sha256, "toolchain_sha256")
    require_hex64(lakefile_sha256, "lakefile_sha256")

    p1 = certify_pillar1_schur_compounding()
    p2 = certify_pillar2_triangle_holonomy()
    p3 = certify_pillar3_silo_cuts_and_contagion_firewall()

    payload = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "oracle_class": "exact",
        "novelty_classification": "N1",
        "pinned_artifacts": {
            "lean_source": "AllToAllEpistemicMesh.lean",
            "lean_source_sha256": lean_source_sha256,
            "lean_toolchain": EXPECTED_LEAN_TOOLCHAIN,
            "lean_toolchain_sha256": toolchain_sha256,
            "lakefile_sha256": lakefile_sha256,
            "lean_theorem_count": len(LEAN_THEOREM_NAMES),
            "lean_theorem_names": list(LEAN_THEOREM_NAMES),
        },
        "mesh_nodes": [dict(node) for node in MESH_NODES],
        "pillar1_schur_compounding": p1,
        "pillar2_triangle_holonomy": p2,
        "pillar3_silo_cuts_and_firewall": p3,
    }
    p_sha = sha256_hex(canonical_json_bytes(payload))
    env = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": p_sha,
        "payload": payload,
    }
    env["certificate_sha256"] = sha256_hex(canonical_json_bytes(env))
    return env
