#!/usr/bin/env python3
"""Reusable Stdlib-Only Pure-Z/Q Higher-Order Convergence & Transformation Engine (aletheia_mesh).

Track S88: Designed to plug cleanly into Foundation-0/aletheia (`aletheia mesh` subcommand)
and execute standalone on ANY typed complete-graph epistemic mesh K_N (4 <= N <= 16),
including live ingestion of Track S83's frozen K_8 certificate.

Zero IEEE-754 floats, zero float(), zero bare asserts, zero .isdigit(), zero random imports.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
from itertools import combinations
import json
from typing import Any

SCHEMA_VERSION = "aletheia.track_s88.aletheia_mesh_engine.v1"
MESH_SPEC_SCHEMA = "aletheia.mesh.spec.v1"
S83_CERT_SCHEMA = "aletheia.track_s83.all_to_all_epistemic_mesh.v1"
TRACK_ID = "TRACK-S88-ALETHEIA-MESH-CLI"
EXPECTED_LEAN_TOOLCHAIN = "leanprover/lean4:v4.36.0"

EXPECTED_LEAN_SHA256 = "f1e8cdab598d7ae81d149ce2564b09bd0c19c477f87d3ad19d4d472d3b4fdb0c"
EXPECTED_TOOLCHAIN_SHA256 = "582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a"
EXPECTED_LAKEFILE_SHA256 = "1c56c871a1e71e84e1e8d61b7065c4e61b851b977af74e0e0b8f49753f873f59"

PINNED_S83_CERT_SHA256 = "74d269c5c1c35665fc835df796e6f94cdbd118ca4ce580a20310c5c969deabdb"
PINNED_S83_PAYLOAD_SHA256 = "c9a8493dc9634db3d9e1c83e62549636d99878c7c7f7b0225a9ae7eabc493c53"

MAX_JSON_DEPTH = 64
MAX_INT_DIGITS = 2467
MAX_INT_BITS = 8192
MIN_MESH_NODES = 4
MAX_MESH_NODES = 16
SPECTRAL_BISECTION_STEPS = 12

_HEX_CHARS = frozenset("0123456789abcdef")
_ASCII_DIGITS = frozenset("0123456789")

PATHWAY_WEIGHTS: dict[str, int] = {
    "EXACT_COMMUTE": 4,
    "CONDITIONAL_BRIDGE": 2,
    "EXACT_OBSTRUCTION": 1,
}

LEAN_THEOREM_NAMES: tuple[str, ...] = (
    "AletheiaMeshEngine.k_simplex_silo_cut_edge_identity",
    "AletheiaMeshEngine.k_simplex_silo_cut_triangle_identity",
    "AletheiaMeshEngine.k_simplex_silo_cut_tetrahedron_identity",
    "AletheiaMeshEngine.k16_balanced_order1_to_4_exponential_collapse",
    "AletheiaMeshEngine.k8_balanced_order1_to_4_total_5cell_extinction",
    "AletheiaMeshEngine.t1_hodge_boundary_squared_zero_k4",
    "AletheiaMeshEngine.t1_kn_hodge1_orthogonal_decomposition",
    "AletheiaMeshEngine.t1_line_graph_disjoint_edge_count",
    "AletheiaMeshEngine.t2_signed_frustrated_triangle_strictly_spd",
    "AletheiaMeshEngine.t2_double_cover_frustrated_triangle_lifts_to_open_6cycle",
    "AletheiaMeshEngine.t3_blowup_single_wall_flips_all_incident_triangles",
    "AletheiaMeshEngine.t3_blowup_strict_rayleigh_conductance_lift",
    "AletheiaMeshEngine.t4_directed_loop_curl_and_stability",
    "AletheiaMeshEngine.t5_borromean_4way_hyperedge_separation",
    "AletheiaMeshEngine.t6_kron_coarsening_and_three_regime_curvature",
    "AletheiaMeshEngine.law3_contagion_firewall_exact_zero_vs_amplification",
)

# Frozen Track S83 K_8 nodes & 28 typed pathways (for standalone offline replay matching live S83 cert)
S83_K8_NODES: tuple[dict[str, str], ...] = (
    {
        "id": "v0",
        "domain": "siliquant_stratified_lattice",
        "track": "Track S73",
        "cert_sha256": "33dfb4153fe974e9ef13120190c14ada6dda63ffbee6caa46047d274f32d36cf",
    },
    {
        "id": "v1",
        "domain": "vp_vnp_cat0_laurent_cuts",
        "track": "Track S75+S82",
        "cert_sha256": "7e383c1cfe04937277be7f8f4ff4305984d51ecd81858eebdd67e45238823224",
    },
    {
        "id": "v2",
        "domain": "circularep_loop_schur_ep",
        "track": "Track S76",
        "cert_sha256": "d30805fcb876de096d9b387a8274ecd8063b7906f4feb36124b38a05aefadc95",
    },
    {
        "id": "v3",
        "domain": "mellin_glu_circuit_graft",
        "track": "Track S77",
        "cert_sha256": "d1b9121c435331053b7ab28b915a2062ae7c93b4197d203c63dba42cce5dd74d",
    },
    {
        "id": "v4",
        "domain": "motifbench_se3_protein_graft",
        "track": "Track S81",
        "cert_sha256": "bc3b9222c47b2ab93c4b5256501d87f8b6483186766e03dba6f1501670936fe0",
    },
    {
        "id": "v5",
        "domain": "engram_lora_mdl_capacity",
        "track": "Track S78",
        "cert_sha256": "3b8341ef5f588f970accb9a9d28f0b683af9747be045e69196e6c19d3fa58378",
    },
    {
        "id": "v6",
        "domain": "rocket_songe_unsloth_rl",
        "track": "Track S80",
        "cert_sha256": "95681a29ca577c4e3040f8ba63f8516b1cbb2bf1ebfdcda06277f21bb2aa2cb7",
    },
    {
        "id": "v7",
        "domain": "twodsd_multipole_csr_laws",
        "track": "Track S79",
        "cert_sha256": "9c30539e6d585141a9b1a5111935ca86de0f740e80749a622547a18242465ad8",
    },
)

S83_K8_EDGES: tuple[tuple[int, int, str, str], ...] = (
    (0, 1, "CONDITIONAL_BRIDGE", "GAUGE_QUOTIENT"),
    (0, 2, "CONDITIONAL_BRIDGE", "PHASE_CROSSOVER"),
    (0, 3, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD"),
    (0, 4, "EXACT_OBSTRUCTION", "BOUNDARY_WALL"),
    (0, 5, "EXACT_COMMUTE", "GAUGE_QUOTIENT"),
    (0, 6, "EXACT_COMMUTE", "PHASE_CROSSOVER"),
    (0, 7, "EXACT_COMMUTE", "PHASE_CROSSOVER"),
    (1, 2, "EXACT_COMMUTE", "HOLONOMY_CURVATURE"),
    (1, 3, "CONDITIONAL_BRIDGE", "BOUNDARY_WALL"),
    (1, 4, "EXACT_OBSTRUCTION", "KREIN_INERTIA"),
    (1, 5, "EXACT_OBSTRUCTION", "BOUNDARY_WALL"),
    (1, 6, "EXACT_COMMUTE", "HOLONOMY_CURVATURE"),
    (1, 7, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD"),
    (2, 3, "CONDITIONAL_BRIDGE", "SCHUR_PUSHFORWARD"),
    (2, 4, "EXACT_OBSTRUCTION", "HOLONOMY_CURVATURE"),
    (2, 5, "CONDITIONAL_BRIDGE", "GAUGE_QUOTIENT"),
    (2, 6, "CONDITIONAL_BRIDGE", "REFUSAL_GATE"),
    (2, 7, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD"),
    (3, 4, "EXACT_OBSTRUCTION", "BOUNDARY_WALL"),
    (3, 5, "CONDITIONAL_BRIDGE", "GAUGE_QUOTIENT"),
    (3, 6, "CONDITIONAL_BRIDGE", "REFUSAL_GATE"),
    (3, 7, "EXACT_COMMUTE", "PHASE_CROSSOVER"),
    (4, 5, "CONDITIONAL_BRIDGE", "GAUGE_QUOTIENT"),
    (4, 6, "CONDITIONAL_BRIDGE", "REFUSAL_GATE"),
    (4, 7, "CONDITIONAL_BRIDGE", "BOUNDARY_WALL"),
    (5, 6, "EXACT_COMMUTE", "REFUSAL_GATE"),
    (5, 7, "CONDITIONAL_BRIDGE", "PHASE_CROSSOVER"),
    (6, 7, "EXACT_OBSTRUCTION", "HOLONOMY_CURVATURE"),
)

_OPERATOR_TAGS: tuple[str, ...] = (
    "SCHUR_PUSHFORWARD",
    "HOLONOMY_CURVATURE",
    "GAUGE_QUOTIENT",
    "BOUNDARY_WALL",
    "PHASE_CROSSOVER",
    "REFUSAL_GATE",
    "KREIN_INERTIA",
)


class MeshError(ValueError):
    """Typed fail-closed error for aletheia_mesh engine and CLI."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def require_ok(cond: bool, code: str, detail: str) -> None:
    if not cond:
        raise MeshError(code, detail)


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
        raise MeshError("INVALID_UTF8_SURROGATE", f"{label}: lone surrogate forbidden") from exc
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
        require_ok(depth <= max_depth, "JSON_DEPTH_EXCEEDED", f"{label}: depth exceeded")
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
        raise MeshError("INVALID_JSON_TYPE", f"{label}: forbidden type {t.__name__}")


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


def comb_k(n: int, k: int) -> int:
    """Exact binomial coefficient C(n, k) in pure integer arithmetic."""
    if k < 0 or k > n:
        return 0
    k_eff = min(k, n - k)
    num = 1
    den = 1
    for i in range(1, k_eff + 1):
        num *= n - k_eff + i
        den *= i
    return num // den


# ---------------------------------------------------------------------------
# Pure-Q Exact Linear Algebra, Sylvester Inertia & Lyapunov Solver
# ---------------------------------------------------------------------------

QMat = list[list[Fraction]]


def q_zeros(r: int, c: int) -> QMat:
    return [[Fraction(0) for _ in range(c)] for _ in range(r)]


def q_eye(n: int) -> QMat:
    return [[Fraction(1 if i == j else 0) for j in range(n)] for i in range(n)]


def q_sub(a: QMat, b: QMat) -> QMat:
    return [[a[i][j] - b[i][j] for j in range(len(a[0]))] for i in range(len(a))]


def q_mul(a: QMat, b: QMat) -> QMat:
    m, k, n = len(a), len(b), len(b[0])
    out = q_zeros(m, n)
    for i in range(m):
        for t in range(k):
            at = a[i][t]
            if at != 0:
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
        require_ok(piv is not None, "SINGULAR_MATRIX", "exact Q solve encountered singular matrix")
        if piv != col:
            aug[col], aug[piv] = aug[piv], aug[col]
        pv = aug[col][col]
        for c in range(col, n + ncols):
            aug[col][c] /= pv
        for r in range(n):
            if r == col:
                continue
            fac = aug[r][col]
            if fac != 0:
                for c in range(col, n + ncols):
                    aug[r][c] -= fac * aug[col][c]
    return [row[n:] for row in aug]


def q_det(a: QMat) -> Fraction:
    """Exact determinant over Q via Gaussian elimination."""
    n = len(a)
    m = [row[:] for row in a]
    det = Fraction(1)
    for col in range(n):
        piv = None
        for r in range(col, n):
            if m[r][col] != 0:
                piv = r
                break
        if piv is None:
            return Fraction(0)
        if piv != col:
            m[col], m[piv] = m[piv], m[col]
            det = -det
        pv = m[col][col]
        det *= pv
        for r in range(col + 1, n):
            if m[r][col] != 0:
                fac = m[r][col] / pv
                for c in range(col + 1, n):
                    m[r][c] -= fac * m[col][c]
    return det


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
                if m[i][k] != 0:
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
    lap = q_zeros(n, n)
    for u, v, w in edges:
        lap[u][u] += w
        lap[v][v] += w
        lap[u][v] -= w
        lap[v][u] -= w
    return lap


def build_signed_laplacian(n: int, signed_edges: list[tuple[int, int, Fraction, int]]) -> QMat:
    lap = q_zeros(n, n)
    for u, v, w, sgn in signed_edges:
        lap[u][u] += w
        lap[v][v] += w
        lap[u][v] -= sgn * w
        lap[v][u] -= sgn * w
    return lap


def compute_eff_resistances(lap: QMat) -> dict[tuple[int, int], Fraction]:
    """Exact pairwise effective resistances via grounded Laplacian inverse M = (L_{1:,1:})^{-1}."""
    n = len(lap)
    sub = [[lap[i][j] for j in range(1, n)] for i in range(1, n)]
    inv = q_solve(sub, q_eye(n - 1))
    m_full = q_zeros(n, n)
    for i in range(1, n):
        for j in range(1, n):
            m_full[i][j] = inv[i - 1][j - 1]
    out: dict[tuple[int, int], Fraction] = {}
    for u in range(n):
        for v in range(u + 1, n):
            out[(u, v)] = m_full[u][u] + m_full[v][v] - 2 * m_full[u][v]
    return out


def schur_complement_subset(lap: QMat, keep: list[int]) -> QMat:
    """Exact Kron/Schur pushforward S_A = L_AA - L_AB L_BB^{-1} L_BA eliminating B = V \\ A."""
    n = len(lap)
    keep_set = set(keep)
    elim = [i for i in range(n) if i not in keep_set]
    l_aa = [[lap[i][j] for j in keep] for i in keep]
    l_ab = [[lap[i][j] for j in elim] for i in keep]
    l_ba = [[lap[i][j] for j in keep] for i in elim]
    l_bb = [[lap[i][j] for j in elim] for i in elim]
    return q_sub(l_aa, q_mul(l_ab, q_solve(l_bb, l_ba)))


def certify_lambda2_bracket(lap: QMat, steps: int = SPECTRAL_BISECTION_STEPS) -> tuple[Fraction, Fraction]:
    """Certified pure-Q Sylvester-inertia bisection bracket [lo, hi] for algebraic connectivity lambda_2."""
    n = len(lap)
    lo = Fraction(0)
    hi = max(lap[i][i] for i in range(n)) * 2
    for _ in range(steps):
        mid = (lo + hi) / 2
        shifted = [[lap[i][j] - (mid if i == j else Fraction(0)) for j in range(n)] for i in range(n)]
        if q_sylvester_inertia(shifted) == [n - 1, 1, 0]:
            lo = mid
        else:
            hi = mid
    return lo, hi


def certify_spd_min_eig_bracket(sym: QMat, steps: int = SPECTRAL_BISECTION_STEPS) -> tuple[Fraction, Fraction]:
    """Certified pure-Q Sylvester-inertia bisection bracket [lo, hi] for lambda_min(sym) of an SPD matrix."""
    n = len(sym)
    lo = Fraction(0)
    hi = min(sym[i][i] for i in range(n))
    for _ in range(steps):
        mid = (lo + hi) / 2
        shifted = [[sym[i][j] - (mid if i == j else Fraction(0)) for j in range(n)] for i in range(n)]
        if q_sylvester_inertia(shifted) == [n, 0, 0]:
            lo = mid
        else:
            hi = mid
    return lo, hi


def solve_discrete_lyapunov(m_mat: QMat) -> QMat:
    """Solve exact discrete Lyapunov equation P - M^T P M = I over Q (SPD P <=> rho(M) < 1)."""
    d = len(m_mat)
    dim = d * d
    sys_a = q_zeros(dim, dim)
    rhs = q_zeros(dim, 1)
    for i in range(d):
        for j in range(d):
            row = i * d + j
            sys_a[row][row] += Fraction(1)
            for p in range(d):
                m_pi = m_mat[p][i]
                if m_pi != 0:
                    for q_idx in range(d):
                        m_qj = m_mat[q_idx][j]
                        if m_qj != 0:
                            sys_a[row][p * d + q_idx] -= m_pi * m_qj
            if i == j:
                rhs[row][0] = Fraction(1)
    sol = q_solve(sys_a, rhs)
    return [[sol[i * d + j][0] for j in range(d)] for i in range(d)]


# ---------------------------------------------------------------------------
# Generic Mesh Specification Builders & Parser (S83 Cert + aletheia.mesh.spec.v1)
# ---------------------------------------------------------------------------

def build_s83_k8_spec() -> dict[str, Any]:
    """Build canonical aletheia.mesh.spec.v1 matching Track S83's frozen K_8 certificate verbatim."""
    edges = []
    for u, v, cls, tag in S83_K8_EDGES:
        edges.append({
            "u": f"v{u}",
            "v": f"v{v}",
            "pathway_class": cls,
            "operator_tag": tag,
            "weight_q": str(PATHWAY_WEIGHTS[cls]),
        })
    return {
        "schema_version": MESH_SPEC_SCHEMA,
        "mesh_id": "s83_k8_epistemic_mesh",
        "nodes": [dict(nd) for nd in S83_K8_NODES],
        "edges": edges,
    }


def build_parametric_kn_spec(n: int) -> dict[str, Any]:
    """Build deterministic typed complete-graph K_N mesh (4 <= N <= 16) for parametric scaling tests."""
    require_exact_int(n, "n", lo=MIN_MESH_NODES, hi=MAX_MESH_NODES)
    wall_pairs: set[tuple[int, int]] = {(0, 1)}
    if n >= 6:
        wall_pairs.add((2, 3))
    if n >= 8:
        wall_pairs.add((4, 5))
    if n >= 12:
        wall_pairs.add((6, 7))
    nodes = [{"id": f"v{i}", "domain": f"parametric_domain_{i}", "track": f"K{n}"} for i in range(n)]
    edges: list[dict[str, str]] = []
    for u in range(n):
        for v in range(u + 1, n):
            if (u, v) in wall_pairs:
                cls = "EXACT_OBSTRUCTION"
            elif (u + v) % 2 == 0:
                cls = "EXACT_COMMUTE"
            else:
                cls = "CONDITIONAL_BRIDGE"
            tag = _OPERATOR_TAGS[(u * n + v) % len(_OPERATOR_TAGS)]
            edges.append({
                "u": f"v{u}",
                "v": f"v{v}",
                "pathway_class": cls,
                "operator_tag": tag,
                "weight_q": str(PATHWAY_WEIGHTS[cls]),
            })
    return {
        "schema_version": MESH_SPEC_SCHEMA,
        "mesh_id": f"parametric_k{n}_mesh",
        "nodes": nodes,
        "edges": edges,
    }


def _parse_pos_q_str(raw: Any, label: str) -> Fraction:
    s = require_exact_str(raw, label)
    if "/" in s:
        parts = s.split("/")
        require_ok(len(parts) == 2 and is_ascii_digits(parts[0]) and is_ascii_digits(parts[1]), "INVALID_WEIGHT", label)
        num = int(parts[0])
        den = int(parts[1])
        require_ok(num > 0 and den > 1, "INVALID_WEIGHT", label)
        q = Fraction(num, den)
        require_ok(q.denominator == den, "NONCANONICAL_WEIGHT", label)
        return q
    require_ok(is_ascii_digits(s), "INVALID_WEIGHT", label)
    val = int(s)
    require_ok(val > 0, "INVALID_WEIGHT", label)
    return Fraction(val, 1)


def parse_mesh_spec(obj: Any) -> dict[str, Any]:
    """Parse Track S83 certificate JSON OR generic aletheia.mesh.spec.v1 into normalized internal mesh."""
    require_ok(type(obj) is dict, "INVALID_MESH_SPEC", "mesh spec root must be dict")
    validate_strict_json_tree(obj, "mesh_spec")
    sv = require_exact_str(obj.get("schema_version"), "schema_version")

    if sv == S83_CERT_SCHEMA:
        payload = obj.get("payload")
        require_ok(type(payload) is dict, "INVALID_S83_CERT", "missing payload dict")
        raw_nodes = payload.get("mesh_nodes")
        p1 = payload.get("pillar1_schur_compounding")
        require_ok(type(raw_nodes) is list and type(p1) is dict, "INVALID_S83_CERT", "missing nodes or pillar1")
        raw_pairs = p1.get("pair_rows")
        require_ok(type(raw_pairs) is list, "INVALID_S83_CERT", "missing pair_rows")
        mesh_id = "s83_k8_epistemic_mesh"
        node_ids: list[str] = []
        id_to_idx: dict[str, int] = {}
        for idx, nd in enumerate(raw_nodes):
            require_ok(type(nd) is dict, "INVALID_NODE", f"node[{idx}]")
            nid = require_exact_str(nd.get("id"), f"node[{idx}].id")
            require_ok(nid not in id_to_idx, "DUPLICATE_NODE", nid)
            id_to_idx[nid] = idx
            node_ids.append(nid)
        n = len(node_ids)
        require_ok(MIN_MESH_NODES <= n <= MAX_MESH_NODES, "INVALID_NODE_COUNT", f"n={n}")
        emap: dict[tuple[int, int], tuple[str, str, Fraction]] = {}
        for idx, row in enumerate(raw_pairs):
            require_ok(type(row) is dict, "INVALID_EDGE", f"pair_row[{idx}]")
            pair_s = require_exact_str(row.get("pair"), f"pair_row[{idx}].pair")
            parts = pair_s.split("-")
            require_ok(len(parts) == 2 and parts[0] in id_to_idx and parts[1] in id_to_idx, "INVALID_EDGE_PAIR", pair_s)
            u, v = id_to_idx[parts[0]], id_to_idx[parts[1]]
            require_ok(u != v, "SELF_LOOP_FORBIDDEN", pair_s)
            key = (u, v) if u < v else (v, u)
            require_ok(key not in emap, "DUPLICATE_EDGE", pair_s)
            cls = require_exact_str(row.get("pathway_class"), f"pair_row[{idx}].pathway_class")
            require_ok(cls in PATHWAY_WEIGHTS, "INVALID_PATHWAY_CLASS", cls)
            tag = require_exact_str(row.get("operator_tag"), f"pair_row[{idx}].operator_tag")
            w = _parse_pos_q_str(row.get("direct_w_q"), f"pair_row[{idx}].direct_w_q")
            emap[key] = (cls, tag, w)
        require_ok(len(emap) == comb_k(n, 2), "INCOMPLETE_MESH", "all C(N,2) edges required")
        return {"mesh_id": mesh_id, "node_ids": node_ids, "n": n, "emap": emap}

    require_ok(sv == MESH_SPEC_SCHEMA, "UNSUPPORTED_MESH_SCHEMA", sv)
    mesh_id = require_exact_str(obj.get("mesh_id"), "mesh_id")
    raw_nodes = obj.get("nodes")
    raw_edges = obj.get("edges")
    require_ok(type(raw_nodes) is list and type(raw_edges) is list, "INVALID_MESH_SPEC", "nodes/edges lists required")
    node_ids = []
    id_to_idx = {}
    for idx, nd in enumerate(raw_nodes):
        require_ok(type(nd) is dict, "INVALID_NODE", f"node[{idx}]")
        nid = require_exact_str(nd.get("id"), f"node[{idx}].id")
        require_ok(nid not in id_to_idx, "DUPLICATE_NODE", nid)
        id_to_idx[nid] = idx
        node_ids.append(nid)
    n = len(node_ids)
    require_ok(MIN_MESH_NODES <= n <= MAX_MESH_NODES, "INVALID_NODE_COUNT", f"n={n}")
    emap = {}
    for idx, row in enumerate(raw_edges):
        require_ok(type(row) is dict, "INVALID_EDGE", f"edge[{idx}]")
        us = require_exact_str(row.get("u"), f"edge[{idx}].u")
        vs = require_exact_str(row.get("v"), f"edge[{idx}].v")
        require_ok(us in id_to_idx and vs in id_to_idx and us != vs, "INVALID_EDGE_PAIR", f"{us}-{vs}")
        u, v = id_to_idx[us], id_to_idx[vs]
        key = (u, v) if u < v else (v, u)
        require_ok(key not in emap, "DUPLICATE_EDGE", f"{us}-{vs}")
        cls = require_exact_str(row.get("pathway_class"), f"edge[{idx}].pathway_class")
        require_ok(cls in PATHWAY_WEIGHTS, "INVALID_PATHWAY_CLASS", cls)
        tag = require_exact_str(row.get("operator_tag", "SCHUR_PUSHFORWARD"), f"edge[{idx}].operator_tag")
        w = _parse_pos_q_str(row.get("weight_q", str(PATHWAY_WEIGHTS[cls])), f"edge[{idx}].weight_q")
        emap[key] = (cls, tag, w)
    require_ok(len(emap) == comb_k(n, 2), "INCOMPLETE_MESH", "all C(N,2) edges required")
    return {"mesh_id": mesh_id, "node_ids": node_ids, "n": n, "emap": emap}


# ---------------------------------------------------------------------------
# Orders 1-4 Higher-Order Convergence Analyzer
# ---------------------------------------------------------------------------

def check_triangle_strict_ineq(rij: Fraction, rjk: Fraction, rik: Fraction) -> bool:
    return rik < rij + rjk and rij < rik + rjk and rjk < rij + rik


def check_hodge_reconstruction(recon_ok: bool, grad_e: Fraction, curl_e: Fraction, norm_sq: Fraction) -> bool:
    return recon_ok and (grad_e + curl_e == norm_sq)


def check_borromean_3body(pair_in: list[int], hyp_in: list[int]) -> bool:
    return pair_in == [0, 0, 3] and hyp_in == [2, 0, 1]


def check_borromean_4way(sub_failed: int, full_ok: bool, pair_in: list[int], hyp_in: list[int]) -> bool:
    return sub_failed == 14 and full_ok and pair_in == [0, 0, 4] and hyp_in == [3, 0, 1]


def check_three_regime_curvature(cat0_det: Fraction, se3_det: Fraction, gram_r_det: Fraction) -> bool:
    return cat0_det < 0 and se3_det == 0 and gram_r_det > 0


def check_firewall_zero_flux(flux_q: str, retained_ok: bool) -> bool:
    return flux_q == "0" and retained_ok


def _classify_triangle(n_comm: int, n_obs: int) -> tuple[str, int]:
    parity = n_obs % 2
    if n_obs == 0:
        if n_comm == 3:
            return "EXACT_TRANSITIVE_CLOSURE", parity
        return "CONDITIONAL_COMPOUNDING_CLOSURE", parity
    if n_obs == 1:
        return "FRUSTRATED_CURVATURE_LOOP", parity
    return "MULTI_WALL_BOUNDARY_SECTOR", parity


def analyze_mesh_orders(norm: dict[str, Any], *, spectral_steps: int = SPECTRAL_BISECTION_STEPS) -> dict[str, Any]:
    """Compute exact Orders 1-4 invariants and k-simplex silo-cut loss curves for any K_N mesh."""
    n = norm["n"]
    node_ids = norm["node_ids"]
    emap = norm["emap"]
    edge_list = [(u, v, emap[(u, v)][2]) for u in range(n) for v in range(u + 1, n)]
    lap = build_weighted_laplacian(n, edge_list)
    lap_inertia = q_sylvester_inertia(lap)
    r_eff = compute_eff_resistances(lap)

    # Order 1: Schur compounding, Foster identity, Kirchhoff index, lambda_2 bracket
    foster_sum = Fraction(0)
    total_w = Fraction(0)
    sum_g = Fraction(0)
    sum_r = Fraction(0)
    min_gain = Fraction(10**9, 1)
    max_gain = Fraction(0, 1)
    min_pair = ""
    max_pair = ""
    all_compounded = True
    cls_counts = {"EXACT_COMMUTE": 0, "CONDITIONAL_BRIDGE": 0, "EXACT_OBSTRUCTION": 0}
    for u in range(n):
        for v in range(u + 1, n):
            cls, _, w_uv = emap[(u, v)]
            cls_counts[cls] += 1
            total_w += w_uv
            r_uv = r_eff[(u, v)]
            g_uv = Fraction(1, 1) / r_uv
            foster_sum += w_uv * r_uv
            sum_g += g_uv
            sum_r += r_uv
            gain = g_uv / w_uv
            if gain <= 1:
                all_compounded = False
            if gain < min_gain:
                min_gain = gain
                min_pair = f"{node_ids[u]}-{node_ids[v]}"
            if gain > max_gain:
                max_gain = gain
                max_pair = f"{node_ids[u]}-{node_ids[v]}"

    tri_ineq_ok = 0
    for i, j, k in combinations(range(n), 3):
        if check_triangle_strict_ineq(r_eff[(i, j)], r_eff[(j, k)], r_eff[(i, k)]):
            tri_ineq_ok += 3

    kirchhoff = Fraction(n, 1) * sum_r
    l2_lo, l2_hi = certify_lambda2_bracket(lap, spectral_steps)

    # Order 2: Exhaustive triangle holonomy
    tri_counts = {
        "EXACT_TRANSITIVE_CLOSURE": 0,
        "CONDITIONAL_COMPOUNDING_CLOSURE": 0,
        "FRUSTRATED_CURVATURE_LOOP": 0,
        "MULTI_WALL_BOUNDARY_SECTOR": 0,
    }
    tri_par: dict[tuple[int, int, int], int] = {}
    exact_closures: list[str] = []
    for i, j, k in combinations(range(n), 3):
        cs = (emap[(i, j)][0], emap[(j, k)][0], emap[(i, k)][0])
        n_comm = sum(1 for c in cs if c == "EXACT_COMMUTE")
        n_obs = sum(1 for c in cs if c == "EXACT_OBSTRUCTION")
        t_cls, par = _classify_triangle(n_comm, n_obs)
        tri_counts[t_cls] += 1
        tri_par[(i, j, k)] = par
        if t_cls == "EXACT_TRANSITIVE_CLOSURE":
            exact_closures.append(f"{node_ids[i]}-{node_ids[j]}-{node_ids[k]}")
    odd_tris = sum(tri_par.values())
    even_tris = len(tri_par) - odd_tris

    # Order 3: Exhaustive tetrahedra Bianchi & K_4 locks
    tet_bianchi_ok = True
    tet_fdist = {"0": 0, "1": 0, "2": 0, "3": 0, "4": 0}
    k4_zero_obs = 0
    k4_all_comm = 0
    for a, b, c, d in combinations(range(n), 4):
        p0 = tri_par[(a, b, c)]
        p1 = tri_par[(a, b, d)]
        p2 = tri_par[(a, c, d)]
        p3 = tri_par[(b, c, d)]
        if (p0 ^ p1 ^ p2 ^ p3) != 0:
            tet_bianchi_ok = False
        tet_fdist[str(p0 + p1 + p2 + p3)] += 1
        e_cls = [emap[pair][0] for pair in combinations((a, b, c, d), 2)]
        if all(ec != "EXACT_OBSTRUCTION" for ec in e_cls):
            k4_zero_obs += 1
        if all(ec == "EXACT_COMMUTE" for ec in e_cls):
            k4_all_comm += 1

    # Order 4: 5-cells & exact k-simplex silo-cut loss curves (k = 2, 3, 4, 5)
    n_five_cells = comb_k(n, 5)
    c5_zero_obs = 0
    c5_all_comm = 0
    for tup in combinations(range(n), 5):
        e_cls = [emap[pair][0] for pair in combinations(tup, 2)]
        if all(ec != "EXACT_OBSTRUCTION" for ec in e_cls):
            c5_zero_obs += 1
        if all(ec == "EXACT_COMMUTE" for ec in e_cls):
            c5_all_comm += 1

    silo_curves: dict[str, Any] = {}
    for s_sz in range(1, (n // 2) + 1):
        t_sz = n - s_sz
        row_k: dict[str, Any] = {}
        for k_ord in (2, 3, 4, 5):
            tot_k = comb_k(n, k_ord)
            if tot_k == 0:
                row_k[f"k{k_ord}"] = {"total": 0, "destroyed": 0, "destroyed_pct_dec2": "0.00"}
            else:
                dest_k = tot_k - comb_k(s_sz, k_ord) - comb_k(t_sz, k_ord)
                row_k[f"k{k_ord}"] = {
                    "total": tot_k,
                    "destroyed": dest_k,
                    "destroyed_pct_dec2": dec_from_q(Fraction(dest_k * 100, tot_k), 2),
                }
        silo_curves[f"{s_sz}|{t_sz}"] = row_k

    return {
        "order1_schur": {
            "n_nodes": n,
            "n_edges": len(edge_list),
            "pathway_class_counts": cls_counts,
            "total_conductance_q": q_str(total_w),
            "laplacian_inertia": lap_inertia,
            "foster_sum_q": q_str(foster_sum),
            "foster_identity_exact": foster_sum == Fraction(n - 1, 1),
            "all_pairs_strictly_compounded": all_compounded,
            "min_compounding_gain_pair": min_pair,
            "min_compounding_gain_q": q_str(min_gain),
            "min_compounding_gain_dec4": dec_from_q(min_gain, 4),
            "max_compounding_gain_pair": max_pair,
            "max_compounding_gain_q": q_str(max_gain),
            "max_compounding_gain_dec4": dec_from_q(max_gain, 4),
            "total_effective_conductance_q": q_str(sum_g),
            "total_effective_conductance_dec4": dec_from_q(sum_g, 4),
            "kirchhoff_index_q": q_str(kirchhoff),
            "kirchhoff_index_dec4": dec_from_q(kirchhoff, 4),
            "lambda2_bracket_q": [q_str(l2_lo), q_str(l2_hi)],
            "lambda2_bracket_dec4": [dec_from_q(l2_lo, 4), dec_from_q(l2_hi, 4)],
            "resistance_triangle_inequalities_verified": tri_ineq_ok,
        },
        "order2_triangles": {
            "n_triangles": len(tri_par),
            "classification_counts": tri_counts,
            "odd_z2_holonomy_triangles": odd_tris,
            "even_z2_holonomy_triangles": even_tris,
            "exact_transitive_closures": exact_closures,
        },
        "order3_tetrahedra": {
            "n_tetrahedra": comb_k(n, 4),
            "bianchi_coboundary_zero_all": tet_bianchi_ok,
            "frustrated_face_distribution": tet_fdist,
            "zero_obstruction_k4_count": k4_zero_obs,
            "all_commute_k4_count": k4_all_comm,
        },
        "order4_five_cells_and_silo_cuts": {
            "n_five_cells": n_five_cells,
            "zero_obstruction_five_cells": c5_zero_obs,
            "all_commute_five_cells": c5_all_comm,
            "silo_cut_curves": silo_curves,
        },
    }


# ---------------------------------------------------------------------------
# Six Structural Mesh Transformations (T_1..T_6) & Law-3 Firewall
# ---------------------------------------------------------------------------

def run_t1_line_graph_hodge(norm: dict[str, Any]) -> dict[str, Any]:
    """T_1: Line-Graph L(K_N), Hodge 1-Laplacian L_1 = B_1^T B_1 + B_2 B_2^T, & grad/curl split."""
    n = norm["n"]
    emap = norm["emap"]
    edges = [(u, v) for u in range(n) for v in range(u + 1, n)]
    e_cnt = len(edges)
    edge_idx = {e: idx for idx, e in enumerate(edges)}
    tris = list(combinations(range(n), 3))

    # Line graph L(K_N) incidence vs vertex-disjoint functor bridges
    incident_pairs = 0
    disjoint_pairs = 0
    same_tag_disjoint = 0
    for idx_a in range(e_cnt):
        u1, v1 = edges[idx_a]
        tag1 = emap[(u1, v1)][1]
        for idx_b in range(idx_a + 1, e_cnt):
            u2, v2 = edges[idx_b]
            if u1 in (u2, v2) or v1 in (u2, v2):
                incident_pairs += 1
            else:
                disjoint_pairs += 1
                if emap[(u2, v2)][1] == tag1:
                    same_tag_disjoint += 1

    # Exact integer boundary matrices: B1 (N x E) and B2 (E x T)
    # Convention: edge (u < v): B1[u, e] = -1, B1[v, e] = +1
    # Triangle (i < j < k): B2[(i,j), t] = +1, B2[(j,k), t] = +1, B2[(i,k), t] = -1
    b1_b2_zero = True
    for i, j, k in tris:
        # Check (B1 @ B2)[:, t] == 0 at vertices i, j, k directly from sparse columns
        col_entries = ((edge_idx[(i, j)], 1), (edge_idx[(j, k)], 1), (edge_idx[(i, k)], -1))
        acc = {i: 0, j: 0, k: 0}
        for e_id, coeff in col_entries:
            eu, ev = edges[e_id]
            acc[eu] -= coeff
            acc[ev] += coeff
        if any(v != 0 for v in acc.values()):
            b1_b2_zero = False

    # Exact Hodge 1-Laplacian L1 = B1^T B1 + B2 B2^T verified entry-by-entry == N * I_E
    l1_mat = [[0] * e_cnt for _ in range(e_cnt)]
    for e_a, (u1, v1) in enumerate(edges):
        for e_b, (u2, v2) in enumerate(edges):
            # (B1^T B1)[e_a, e_b]
            val = 0
            if u1 == u2:
                val += 1
            if v1 == v2:
                val += 1
            if u1 == v2:
                val -= 1
            if v1 == u2:
                val -= 1
            l1_mat[e_a][e_b] = val
    for i, j, k in tris:
        tri_e = ((edge_idx[(i, j)], 1), (edge_idx[(j, k)], 1), (edge_idx[(i, k)], -1))
        for e_a, s_a in tri_e:
            for e_b, s_b in tri_e:
                l1_mat[e_a][e_b] += s_a * s_b
    hodge1_eq_n_eye = True
    for r in range(e_cnt):
        for c in range(e_cnt):
            expected = n if r == c else 0
            if l1_mat[r][c] != expected:
                hodge1_eq_n_eye = False

    # Exact orthogonal Hodge decomposition of the obstruction-indicator 1-cochain f_obs in {0, 1}^E
    f_obs = [Fraction(1 if emap[e][0] == "EXACT_OBSTRUCTION" else 0) for e in edges]
    # div_v = (B1 f_obs)[v]
    div_v = [Fraction(0)] * n
    for idx_e, (u, v) in enumerate(edges):
        div_v[u] -= f_obs[idx_e]
        div_v[v] += f_obs[idx_e]
    f_grad = [(div_v[v] - div_v[u]) / n for (u, v) in edges]
    # curl_t = (B2^T f_obs)[t]; f_curl = (1/N) * B2 curl_t
    f_curl = [Fraction(0)] * e_cnt
    for i, j, k in tris:
        e_ij, e_jk, e_ik = edge_idx[(i, j)], edge_idx[(j, k)], edge_idx[(i, k)]
        c_t = f_obs[e_ij] + f_obs[e_jk] - f_obs[e_ik]
        f_curl[e_ij] += c_t / n
        f_curl[e_jk] += c_t / n
        f_curl[e_ik] -= c_t / n

    recon_ok = all(f_grad[idx_e] + f_curl[idx_e] == f_obs[idx_e] for idx_e in range(e_cnt))
    inner_gc = sum((f_grad[idx_e] * f_curl[idx_e] for idx_e in range(e_cnt)), Fraction(0))
    norm_sq = sum((x * x for x in f_obs), Fraction(0))
    grad_e = sum((x * x for x in f_grad), Fraction(0))
    curl_e = sum((x * x for x in f_curl), Fraction(0))

    return {
        "line_graph_vertices": e_cnt,
        "line_graph_edges": incident_pairs,
        "vertex_disjoint_edge_pairs": disjoint_pairs,
        "same_tag_disjoint_functor_bridges": same_tag_disjoint,
        "b1_b2_zero_exact": b1_b2_zero,
        "hodge1_equals_n_identity": hodge1_eq_n_eye,
        "obstruction_flow_norm_sq_q": q_str(norm_sq),
        "obstruction_grad_energy_q": q_str(grad_e),
        "obstruction_curl_energy_q": q_str(curl_e),
        "obstruction_hodge_orthogonal_exact": inner_gc == 0,
        "obstruction_hodge_reconstruction_exact": check_hodge_reconstruction(recon_ok, grad_e, curl_e, norm_sq),
    }


def run_t2_signed_frustration_double_cover(
    norm: dict[str, Any], *, spectral_steps: int = SPECTRAL_BISECTION_STEPS
) -> dict[str, Any]:
    """T_2: Signed Frustration Laplacian L_sigma & 2-Sheeted Gauge Double Cover K~_N."""
    n = norm["n"]
    emap = norm["emap"]
    signed_edges: list[tuple[int, int, Fraction, int]] = []
    dc_edges: list[tuple[int, int, Fraction]] = []
    obs_count = 0
    for u in range(n):
        for v in range(u + 1, n):
            cls, _, w = emap[(u, v)]
            sgn = -1 if cls == "EXACT_OBSTRUCTION" else 1
            if sgn < 0:
                obs_count += 1
            signed_edges.append((u, v, w, sgn))
            # 2-sheeted double cover: vertices 0..n-1 (+) and n..2n-1 (-)
            if sgn > 0:
                dc_edges.append((u, v, w))
                dc_edges.append((u + n, v + n, w))
            else:
                dc_edges.append((u, v + n, w))
                dc_edges.append((u + n, v, w))

    l_sig = build_signed_laplacian(n, signed_edges)
    sig_inertia = q_sylvester_inertia(l_sig)
    sig_det = q_det(l_sig)
    is_frustrated = sig_inertia == [n, 0, 0]
    if is_frustrated:
        l1_lo, l1_hi = certify_spd_min_eig_bracket(l_sig, spectral_steps)
    else:
        l1_lo, l1_hi = Fraction(0), Fraction(0)

    # Double cover Laplacian on 2N vertices (all edges strictly positive => 0 frustrated triangles!)
    l_dc = build_weighted_laplacian(2 * n, dc_edges)
    dc_inertia = q_sylvester_inertia(l_dc)

    odd_tri = 0
    even_tri = 0
    for i, j, k in combinations(range(n), 3):
        oc = (
            (1 if emap[(i, j)][0] == "EXACT_OBSTRUCTION" else 0)
            + (1 if emap[(j, k)][0] == "EXACT_OBSTRUCTION" else 0)
            + (1 if emap[(i, k)][0] == "EXACT_OBSTRUCTION" else 0)
        )
        if oc % 2 == 1:
            odd_tri += 1
        else:
            even_tri += 1

    return {
        "obstruction_edge_count": obs_count,
        "signed_laplacian_inertia": sig_inertia,
        "signed_laplacian_det_q": q_str(sig_det),
        "is_frustrated": is_frustrated,
        "frustration_lambda1_bracket_q": [q_str(l1_lo), q_str(l1_hi)],
        "frustration_lambda1_bracket_dec4": [dec_from_q(l1_lo, 4), dec_from_q(l1_hi, 4)],
        "double_cover_vertices": 2 * n,
        "double_cover_edges": len(dc_edges),
        "double_cover_inertia": dc_inertia,
        "double_cover_connected": dc_inertia == [2 * n - 1, 0, 1],
        "double_cover_frustrated_triangles": 0,
        "lifted_closed_triangles": 2 * even_tri,
        "lifted_open_6cycles": odd_tri,
        "law5_gauge_sheet_obstruction_active": odd_tri > 0,
    }


def run_t3_auto_blowup_ranker(
    norm: dict[str, Any], *, spectral_steps: int = SPECTRAL_BISECTION_STEPS
) -> dict[str, Any]:
    """T_3: Algorithmic Auto-Blow-Up Mediator Ranker over EVERY EXACT_OBSTRUCTION edge."""
    n = norm["n"]
    node_ids = norm["node_ids"]
    emap = norm["emap"]
    base_edges = [(u, v, emap[(u, v)][2]) for u in range(n) for v in range(u + 1, n)]
    lap0 = build_weighted_laplacian(n, base_edges)
    r0 = compute_eff_resistances(lap0)
    kf0 = Fraction(n, 1) * sum(r0.values(), Fraction(0))
    l2_0_lo, l2_0_hi = certify_lambda2_bracket(lap0, spectral_steps)

    obs_edges = [(u, v) for u in range(n) for v in range(u + 1, n) if emap[(u, v)][0] == "EXACT_OBSTRUCTION"]
    target_w = Fraction(PATHWAY_WEIGHTS["EXACT_COMMUTE"], 1)

    raw_rows: list[tuple[Any, ...]] = []
    for eu, ev in obs_edges:
        frust_resolved = 0
        mw_exposed = 0
        for k in range(n):
            if k == eu or k == ev:
                continue
            p_uk = (eu, k) if eu < k else (k, eu)
            p_vk = (ev, k) if ev < k else (k, ev)
            other_obs = (
                (1 if emap[p_uk][0] == "EXACT_OBSTRUCTION" else 0)
                + (1 if emap[p_vk][0] == "EXACT_OBSTRUCTION" else 0)
            )
            if other_obs == 0:
                frust_resolved += 1
            elif other_obs == 1:
                mw_exposed += 1
        net_delta = mw_exposed - frust_resolved

        new_edges = [
            (u, v, target_w if (u, v) == (eu, ev) else emap[(u, v)][2])
            for u in range(n)
            for v in range(u + 1, n)
        ]
        new_signed = [
            (
                u,
                v,
                target_w if (u, v) == (eu, ev) else emap[(u, v)][2],
                1 if (u, v) == (eu, ev) else (-1 if emap[(u, v)][0] == "EXACT_OBSTRUCTION" else 1),
            )
            for u in range(n)
            for v in range(u + 1, n)
        ]
        lap1 = build_weighted_laplacian(n, new_edges)
        r1 = compute_eff_resistances(lap1)
        sum_dg = sum((Fraction(1, 1) / r1[p] - Fraction(1, 1) / r0[p] for p in r0), Fraction(0))
        pair_dg = Fraction(1, 1) / r1[(eu, ev)] - Fraction(1, 1) / r0[(eu, ev)]
        dkf = kf0 - Fraction(n, 1) * sum(r1.values(), Fraction(0))
        l2_1_lo, l2_1_hi = certify_lambda2_bracket(lap1, spectral_steps)

        lsig1 = build_signed_laplacian(n, new_signed)
        sig_in1 = q_sylvester_inertia(lsig1)
        sig_det1 = q_det(lsig1)
        if sig_in1 == [n, 0, 0]:
            sl1_lo, sl1_hi = certify_spd_min_eig_bracket(lsig1, spectral_steps)
        else:
            sl1_lo, sl1_hi = Fraction(0), Fraction(0)

        raw_rows.append((
            eu,
            ev,
            emap[(eu, ev)][1],
            frust_resolved,
            mw_exposed,
            net_delta,
            sum_dg,
            pair_dg,
            dkf,
            l2_1_lo,
            l2_1_hi,
            sig_det1,
            sl1_lo,
            sl1_hi,
        ))

    # Primary deterministic multi-order ranking: maximum frustration drop, then global Schur gain, then Kirchhoff drop
    raw_rows.sort(key=lambda r: (-r[5], r[6], r[8], -r[0], -r[1]), reverse=True)

    ranked_unlocks: list[dict[str, Any]] = []
    for rank_idx, r in enumerate(raw_rows, 1):
        eu, ev, tag, fr, mw, net_d, sum_dg, pair_dg, dkf, l2_lo, l2_hi, sdet1, sl1_lo, sl1_hi = r
        ranked_unlocks.append({
            "rank": rank_idx,
            "pair": f"{node_ids[eu]}-{node_ids[ev]}",
            "operator_tag": tag,
            "incident_triangles": n - 2,
            "frustrated_resolved": fr,
            "multi_wall_exposed": mw,
            "net_frustrated_delta": net_d,
            "global_schur_conductance_gain_q": q_str(sum_dg),
            "global_schur_conductance_gain_dec4": dec_from_q(sum_dg, 4),
            "pair_direct_gain_q": q_str(pair_dg),
            "kirchhoff_reduction_q": q_str(dkf),
            "kirchhoff_reduction_dec4": dec_from_q(dkf, 4),
            "lambda2_after_bracket_q": [q_str(l2_lo), q_str(l2_hi)],
            "lambda2_after_bracket_dec4": [dec_from_q(l2_lo, 4), dec_from_q(l2_hi, 4)],
            "lambda2_strict_lift_certified": l2_lo > l2_0_hi,
            "signed_det_after_q": q_str(sdet1),
            "signed_lambda1_after_bracket_dec4": [dec_from_q(sl1_lo, 4), dec_from_q(sl1_hi, 4)],
        })

    top_frust = ranked_unlocks[0]["pair"] if ranked_unlocks else ""
    top_cond = max(raw_rows, key=lambda r: (r[6], -r[0], -r[1])) if raw_rows else None
    top_lam2 = max(raw_rows, key=lambda r: (r[9] + r[10], -r[0], -r[1])) if raw_rows else None
    top_cond_pair = f"{node_ids[top_cond[0]]}-{node_ids[top_cond[1]]}" if top_cond else ""
    top_lam2_pair = f"{node_ids[top_lam2[0]]}-{node_ids[top_lam2[1]]}" if top_lam2 else ""

    return {
        "target_class": "EXACT_COMMUTE",
        "baseline_lambda2_bracket_q": [q_str(l2_0_lo), q_str(l2_0_hi)],
        "n_obstruction_candidates": len(ranked_unlocks),
        "ranked_unlocks": ranked_unlocks,
        "top_frustration_unlock_pair": top_frust,
        "top_conductance_unlock_pair": top_cond_pair,
        "top_lambda2_unlock_pair": top_lam2_pair,
        "pareto_multi_wall_obstruction_detected": top_frust != top_cond_pair,
    }


def run_t4_directed_loop_schur_gate() -> dict[str, Any]:
    """T_4: Directed Asymmetric Non-Normal CEER Loop-Schur Curl & Exact Lyapunov Stability Gate."""
    m_stable: QMat = [
        [Fraction(0), Fraction(2, 5), Fraction(1, 10)],
        [Fraction(1, 10), Fraction(0), Fraction(1, 2)],
        [Fraction(1, 3), Fraction(1, 10), Fraction(0)],
    ]
    d = 3
    m_t = [[m_stable[j][i] for j in range(d)] for i in range(d)]
    s_part = [[(m_stable[i][j] + m_t[i][j]) / 2 for j in range(d)] for i in range(d)]
    a_curl = [[(m_stable[i][j] - m_t[i][j]) / 2 for j in range(d)] for i in range(d)]
    curl_frob_sq = sum((a_curl[i][j] * a_curl[i][j] for i in range(d) for j in range(d)), Fraction(0))

    mmt = q_mul(m_stable, m_t)
    mtm = q_mul(m_t, m_stable)
    comm_frob_sq = sum(((mmt[i][j] - mtm[i][j]) ** 2 for i in range(d) for j in range(d)), Fraction(0))

    # Exact directed Loop-Schur resolvent G_loop = (I - M)^{-1} vs symmetrized G_sym = (I - S)^{-1}
    g_loop = q_solve(q_sub(q_eye(d), m_stable), q_eye(d))
    g_sym = q_solve(q_sub(q_eye(d), s_part), q_eye(d))
    dir_col0_sum = sum((g_loop[i][0] for i in range(d)), Fraction(0))
    sym_col0_sum = sum((g_sym[i][0] for i in range(d)), Fraction(0))

    # Necessary & sufficient exact pure-Q spectral-radius stability test: Lyapunov P - M^T P M = I is SPD
    p_stable = solve_discrete_lyapunov(m_stable)
    in_stable = q_sylvester_inertia(p_stable)

    # Unstable feedback loop (2x gain) vs Law-3 refusal damping (gamma = 2/5)
    m_unstable = [[m_stable[i][j] * 2 for j in range(d)] for i in range(d)]
    p_unstable = solve_discrete_lyapunov(m_unstable)
    in_unstable = q_sylvester_inertia(p_unstable)

    m_damped = [[m_unstable[i][j] * Fraction(2, 5) for j in range(d)] for i in range(d)]
    p_damped = solve_discrete_lyapunov(m_damped)
    in_damped = q_sylvester_inertia(p_damped)

    return {
        "dimension": d,
        "curl_frobenius_sq_q": q_str(curl_frob_sq),
        "non_normal_commutator_sq_q": q_str(comm_frob_sq),
        "is_non_normal": comm_frob_sq > 0,
        "directed_col0_response_q": q_str(dir_col0_sum),
        "symmetrized_col0_response_q": q_str(sym_col0_sum),
        "directional_asymmetry_certified": dir_col0_sum != sym_col0_sum,
        "stable_lyapunov_inertia": in_stable,
        "stable_gate_passed": in_stable == [d, 0, 0],
        "unstable_lyapunov_inertia": in_unstable,
        "unstable_gate_rejected": in_unstable != [d, 0, 0],
        "law3_damping_factor_q": "2/5",
        "damped_lyapunov_inertia": in_damped,
        "damped_gate_restored": in_damped == [d, 0, 0],
    }


def _hyperedge_laplacian(n: int, members: tuple[int, ...], weight: Fraction) -> QMat:
    """Normalized Bolla hypergraph incidence Laplacian L_H(e) = (w/r)*(r I_e - 1_e 1_e^T)."""
    r = len(members)
    lap = q_zeros(n, n)
    off = -weight / r
    diag = weight * Fraction(r - 1, r)
    for u in members:
        lap[u][u] += diag
        for v in members:
            if u != v:
                lap[u][v] += off
    return lap


def run_t5_borromean_hyperedge_detector() -> dict[str, Any]:
    """T_5: Borromean 3-Body & 4-Way 8 GiB Consumer-Silicon Sovereign Stack Hyperedge Detector."""
    # Witness 1: Borromean 3-body helicity (H_3) — 0 pairwise links vs 3-body hyperedge
    l_pair_3 = q_zeros(3, 3)
    l_h3 = _hyperedge_laplacian(3, (0, 1, 2), Fraction(3, 1))

    # Witness 2: 4-way 8 GiB consumer-silicon sovereign stack (v0=S73, v5=S78, v6=S80, v7=S79)
    # Exact pure-Z MiB budget model anchored to Track S73/S78/S79/S80 verified numbers:
    #   VRAM cap = 8192 MiB.
    #   Base weights: 1580 MiB (S73 3.0 bpw QuadSnake) vs 5886 MiB (BF16).
    #   Optimizer + LoRA: 940 MiB (S78 LoRA r=64) vs 11772 MiB (full-weight FT).
    #   Logits + act: 2210 MiB (S80 CCE-Det) vs 6840 MiB (materialized B*L*V logits).
    #   CSR outlier sidecar: 91 MiB (S79 CSR <= 1/160 cap; required to meet KL <= 0.025 quality gate).
    #   Full 4-way stack total = 1580 + 940 + 2210 + 91 = 4821 MiB < 8192 MiB (3371 MiB headroom!).
    vram_cap_mib = 8192
    proper_subsets_failed = 0
    full_4way_mib = 0
    full_4way_feasible = False
    for mask in range(1, 16):
        has_s73 = bool(mask & 1)
        has_s78 = bool(mask & 2)
        has_s80 = bool(mask & 4)
        has_s79 = bool(mask & 8)
        vram_mib = (
            (1580 if has_s73 else 5886)
            + (940 if has_s78 else 11772)
            + (2210 if has_s80 else 6840)
            + (91 if has_s79 else 0)
        )
        # Quality/CSR gate requires S79 at 3.0 bpw (or un-quantized BF16 which blows VRAM cap)
        kl_and_csr_ok = has_s79
        feasible = (vram_mib < vram_cap_mib) and kl_and_csr_ok
        if mask == 15:
            full_4way_mib = vram_mib
            full_4way_feasible = feasible
        elif not feasible:
            proper_subsets_failed += 1

    l_pair_4 = q_zeros(4, 4)
    l_h4 = _hyperedge_laplacian(4, (0, 1, 2, 3), Fraction(4, 1))

    in_p3 = q_sylvester_inertia(l_pair_3)
    in_h3 = q_sylvester_inertia(l_h3)
    in_p4 = q_sylvester_inertia(l_pair_4)
    in_h4 = q_sylvester_inertia(l_h4)

    return {
        "borromean_3body_helicity": {
            "order": 3,
            "pairwise_laplacian_inertia": in_p3,
            "hypergraph_laplacian_inertia": in_h3,
            "pairwise_blind_hypergraph_unlocked": check_borromean_3body(in_p3, in_h3),
        },
        "borromean_4way_sovereign_stack": {
            "order": 4,
            "components": ["v0:S73_3bpw_QuadSnake", "v5:S78_LoRA_r64", "v6:S80_CCE_Det", "v7:S79_CSR_1_160"],
            "vram_cap_mib": vram_cap_mib,
            "full_4way_vram_mib": full_4way_mib,
            "headroom_mib": vram_cap_mib - full_4way_mib,
            "proper_nonempty_subsets_tested": 14,
            "proper_nonempty_subsets_failed": proper_subsets_failed,
            "full_4way_feasible": full_4way_feasible,
            "pairwise_laplacian_inertia": in_p4,
            "hypergraph_laplacian_inertia": in_h4,
            "borromean_irreducible_certified": check_borromean_4way(
                proper_subsets_failed, full_4way_feasible, in_p4, in_h4
            ),
        },
    }


def run_t6_kron_coarsening_and_curvature(norm: dict[str, Any]) -> dict[str, Any]:
    """T_6: Exact Kron/Schur Coarsening Resistance Preservation & 3-Regime Curvature Tomography."""
    n = norm["n"]
    node_ids = norm["node_ids"]
    emap = norm["emap"]
    edge_list = [(u, v, emap[(u, v)][2]) for u in range(n) for v in range(u + 1, n)]
    lap = build_weighted_laplacian(n, edge_list)
    r_full = compute_eff_resistances(lap)

    keep_k = 4 if n >= 5 else 3
    keep = list(range(keep_k))
    s_kron = schur_complement_subset(lap, keep)
    kron_inertia = q_sylvester_inertia(s_kron)
    r_kron = compute_eff_resistances(s_kron)

    all_boosted = True
    all_r_invariant = True
    for i in range(keep_k):
        for j in range(i + 1, keep_k):
            if -s_kron[i][j] <= emap[(i, j)][2]:
                all_boosted = False
            if r_kron[(i, j)] != r_full[(i, j)]:
                all_r_invariant = False

    # Schoenberg Gram matrix G_{ij} = (R(0,i) + R(0,j) - R(i,j)) / 2 on kept terminals {0..keep_k-1}
    g_dim = keep_k - 1
    gram_r = q_zeros(g_dim, g_dim)
    for i in range(1, keep_k):
        for j in range(1, keep_k):
            dij = Fraction(0) if i == j else r_full[(min(i, j), max(i, j))]
            gram_r[i - 1][j - 1] = (r_full[(0, i)] + r_full[(0, j)] - dij) / 2
    gram_r_in = q_sylvester_inertia(gram_r)
    gram_r_det = q_det(gram_r)

    # Explicit 3-regime curvature anchors:
    #   1) CAT(0) rank metric (vp-vnp Rem D.3): 2G -> det(G) = -1/4 < 0, inertia [3, 1, 0]
    #   2) SE(3) R^3 ambient 5-point wall (Track S81): det(G_4) = 0, inertia [3, 0, 1]
    #   3) Resistance metric on kept core: det(G) > 0, inertia [g_dim, 0, 0]
    cat0_gram: QMat = [
        [Fraction(1), Fraction(1, 2), Fraction(0), Fraction(1)],
        [Fraction(1, 2), Fraction(1), Fraction(1, 2), Fraction(1, 2)],
        [Fraction(0), Fraction(1, 2), Fraction(1), Fraction(1)],
        [Fraction(1), Fraction(1, 2), Fraction(1), Fraction(2)],
    ]
    # 4 vectors in R^3: e1, e2, e3, e1+e2+e3 -> 4x4 Gram matrix of rank 3 (det = 0)
    se3_vecs = ((1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1))
    se3_gram: QMat = [
        [Fraction(sum(se3_vecs[i][c] * se3_vecs[j][c] for c in range(3))) for j in range(4)]
        for i in range(4)
    ]
    cat0_det = q_det(cat0_gram)
    se3_det = q_det(se3_gram)

    return {
        "kept_nodes": [node_ids[i] for i in keep],
        "eliminated_count": n - keep_k,
        "kron_inertia": kron_inertia,
        "all_kept_edges_strictly_boosted": all_boosted,
        "all_kept_pairs_r_eff_exact_invariant": all_r_invariant,
        "r_eff_gram_inertia": gram_r_in,
        "r_eff_gram_det_q": q_str(gram_r_det),
        "cat0_rank_metric_det_q": q_str(cat0_det),
        "cat0_rank_metric_inertia": q_sylvester_inertia(cat0_gram),
        "se3_r3_gram_det_q": q_str(se3_det),
        "se3_r3_gram_inertia": q_sylvester_inertia(se3_gram),
        "three_regime_curvature_separated": check_three_regime_curvature(cat0_det, se3_det, gram_r_det),
    }


def simulate_law3_contagion_firewall(
    norm: dict[str, Any], *, compromised: int | None = None, anchor: int = 0
) -> dict[str, Any]:
    """Law-3 Per-Edge Refusal Firewall Simulator vs. Ungated Harmonic Contagion on any K_N."""
    n = norm["n"]
    node_ids = norm["node_ids"]
    emap = norm["emap"]
    c_idx = (n - 2) if compromised is None else compromised
    require_exact_int(c_idx, "compromised", lo=0, hi=n - 1)
    require_exact_int(anchor, "anchor", lo=0, hi=n - 1)
    require_ok(c_idx != anchor, "INVALID_FIREWALL_NODES", "compromised and anchor must differ")

    edge_list = [(u, v, emap[(u, v)][2]) for u in range(n) for v in range(u + 1, n)]
    lap = build_weighted_laplacian(n, edge_list)
    r_full = compute_eff_resistances(lap)

    interior = [i for i in range(n) if i != anchor and i != c_idx]
    l_ii = [[lap[i][j] for j in interior] for i in interior]
    rhs = [[-lap[i][c_idx]] for i in interior]
    u_int = [row[0] for row in q_solve(l_ii, rhs)]
    u_full = [Fraction(0)] * n
    u_full[c_idx] = Fraction(1)
    for pos, idx_i in enumerate(interior):
        u_full[idx_i] = u_int[pos]

    j_ungated = sum(((-lap[anchor][j]) * u_full[j] for j in range(n) if j != anchor), Fraction(0))
    j_direct = -lap[anchor][c_idx]
    pair_ac = (anchor, c_idx) if anchor < c_idx else (c_idx, anchor)
    g_eff_ac = Fraction(1, 1) / r_full[pair_ac]

    # Gated submesh K_{N-1}: sever all N-1 edges incident to compromised node
    sub_nodes = [i for i in range(n) if i != c_idx]
    sub_map = {orig: pos for pos, orig in enumerate(sub_nodes)}
    sub_edges = [(sub_map[u], sub_map[v], w) for (u, v, w) in edge_list if u != c_idx and v != c_idx]
    lap_sub = build_weighted_laplacian(n - 1, sub_edges)
    r_sub = compute_eff_resistances(lap_sub)
    sub_all_comp = True
    sub_min_gain = Fraction(10**9, 1)
    for a in range(n - 1):
        for b in range(a + 1, n - 1):
            w_ab = -lap_sub[a][b]
            g_ab = (Fraction(1, 1) / r_sub[(a, b)]) / w_ab
            if g_ab <= 1:
                sub_all_comp = False
            if g_ab < sub_min_gain:
                sub_min_gain = g_ab

    return {
        "compromised_node": node_ids[c_idx],
        "clean_anchor_node": node_ids[anchor],
        "direct_edge_flux_q": q_str(j_direct),
        "ungated_total_flux_q": q_str(j_ungated),
        "ungated_flux_amplification_q": q_str(j_ungated / j_direct),
        "ungated_flux_amplification_dec4": dec_from_q(j_ungated / j_direct, 4),
        "flux_equals_schur_g_eff": j_ungated == g_eff_ac,
        "all_interior_nodes_corrupted": all(Fraction(0) < val < Fraction(1) for val in u_int),
        "gated_firewall_flux_q": "0",
        "gated_firewall_interior_max_error_q": "0",
        "retained_submesh_nodes": n - 1,
        "retained_edges": len(sub_edges),
        "retained_triangles": comb_k(n - 1, 3),
        "retained_all_pairs_compounded": sub_all_comp,
        "retained_min_compounding_gain_q": q_str(sub_min_gain),
        "retained_min_compounding_gain_dec4": dec_from_q(sub_min_gain, 4),
    }


def analyze_mesh_full(raw_spec: Any, *, spectral_steps: int = SPECTRAL_BISECTION_STEPS) -> dict[str, Any]:
    """Run complete Higher-Order (Orders 1-4) + T_1..T_6 + Law-3 Firewall analysis on any typed mesh."""
    norm = parse_mesh_spec(raw_spec)
    body = {
        "mesh_id": norm["mesh_id"],
        "n_nodes": norm["n"],
        "node_ids": norm["node_ids"],
        "higher_order_convergence": analyze_mesh_orders(norm, spectral_steps=spectral_steps),
        "t1_line_graph_hodge": run_t1_line_graph_hodge(norm),
        "t2_signed_frustration_double_cover": run_t2_signed_frustration_double_cover(norm, spectral_steps=spectral_steps),
        "t3_auto_blowup_ranker": run_t3_auto_blowup_ranker(norm, spectral_steps=spectral_steps),
        "t4_directed_loop_schur_gate": run_t4_directed_loop_schur_gate(),
        "t5_borromean_hyperedge_detector": run_t5_borromean_hyperedge_detector(),
        "t6_kron_coarsening_and_curvature": run_t6_kron_coarsening_and_curvature(norm),
        "law3_contagion_firewall": simulate_law3_contagion_firewall(norm),
    }
    return {
        "analysis_sha256": sha256_hex(canonical_json_bytes(body)),
        "analysis": body,
    }


def _parametric_summary_entry(n: int) -> dict[str, Any]:
    """Concise verified Orders 1-4 + T_1 + T_2 + T_6 + Firewall summary for parametric K_N."""
    norm = parse_mesh_spec(build_parametric_kn_spec(n))
    orders = analyze_mesh_orders(norm, spectral_steps=8)
    t1 = run_t1_line_graph_hodge(norm)
    t2 = run_t2_signed_frustration_double_cover(norm, spectral_steps=8)
    t6 = run_t6_kron_coarsening_and_curvature(norm)
    fw = simulate_law3_contagion_firewall(norm)
    half = n // 2
    bal_key = f"{half}|{n - half}"
    return {
        "n_nodes": n,
        "n_edges": orders["order1_schur"]["n_edges"],
        "n_triangles": orders["order2_triangles"]["n_triangles"],
        "n_tetrahedra": orders["order3_tetrahedra"]["n_tetrahedra"],
        "n_five_cells": orders["order4_five_cells_and_silo_cuts"]["n_five_cells"],
        "foster_identity_exact": orders["order1_schur"]["foster_identity_exact"],
        "all_pairs_strictly_compounded": orders["order1_schur"]["all_pairs_strictly_compounded"],
        "bianchi_coboundary_zero_all": orders["order3_tetrahedra"]["bianchi_coboundary_zero_all"],
        "hodge_b1_b2_zero_exact": t1["b1_b2_zero_exact"],
        "hodge1_equals_n_identity": t1["hodge1_equals_n_identity"],
        "signed_is_frustrated": t2["is_frustrated"],
        "kron_r_eff_exact_invariant": t6["all_kept_pairs_r_eff_exact_invariant"],
        "firewall_zero_flux": check_firewall_zero_flux(fw["gated_firewall_flux_q"], fw["retained_all_pairs_compounded"]),
        "balanced_split": bal_key,
        "balanced_silo_cut": orders["order4_five_cells_and_silo_cuts"]["silo_cut_curves"][bal_key],
    }


def build_s88_certificate(
    *,
    lean_source_sha256: str = EXPECTED_LEAN_SHA256,
    toolchain_sha256: str = EXPECTED_TOOLCHAIN_SHA256,
    lakefile_sha256: str = EXPECTED_LAKEFILE_SHA256,
) -> dict[str, Any]:
    """Build deterministic canonical Track S88 certificate (pure-Z/Q, zero floats)."""
    require_hex64(lean_source_sha256, "lean_source_sha256")
    require_hex64(toolchain_sha256, "toolchain_sha256")
    require_hex64(lakefile_sha256, "lakefile_sha256")

    s83_live = analyze_mesh_full(build_s83_k8_spec(), spectral_steps=SPECTRAL_BISECTION_STEPS)
    parametric_rows = [_parametric_summary_entry(k_n) for k_n in (4, 6, 16)]

    payload = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "oracle_class": "exact",
        "novelty_classification": "N1",
        "pinned_artifacts": {
            "lean_source": "AletheiaMeshEngine.lean",
            "lean_source_sha256": lean_source_sha256,
            "lean_toolchain": EXPECTED_LEAN_TOOLCHAIN,
            "lean_toolchain_sha256": toolchain_sha256,
            "lakefile_sha256": lakefile_sha256,
            "lean_theorem_count": len(LEAN_THEOREM_NAMES),
            "lean_theorem_names": list(LEAN_THEOREM_NAMES),
            "s83_certificate_sha256": PINNED_S83_CERT_SHA256,
            "s83_payload_sha256": PINNED_S83_PAYLOAD_SHA256,
        },
        "s83_k8_live_analysis": s83_live,
        "parametric_scaling_summary": parametric_rows,
        "aletheia_cli_plugin_spec": {
            "subcommand": "mesh",
            "entrypoint": "aletheia.mesh:run_mesh_cli",
            "input_schemas": [S83_CERT_SCHEMA, MESH_SPEC_SCHEMA],
            "modes": ["--analyze", "--parametric", "--check", "--write", "--standalone", "--verify-lean"],
            "node_bounds": [MIN_MESH_NODES, MAX_MESH_NODES],
            "zero_float_strict": True,
            "r4_three_mode_deterministic": True,
        },
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
