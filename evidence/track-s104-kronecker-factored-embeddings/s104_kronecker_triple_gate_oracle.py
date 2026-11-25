#!/usr/bin/env python3
"""Track S104 oracle: Kronecker product-code factored embeddings, the rank-1 expressivity
obstruction and its rank-2/hybrid lift, the EXP-Delta latent-repair preregistration audit,
the composed StaticProof/Receipt/Holdout triple gate, and the RAM == WIRE == HASH
quantize/serialize/avalanche witnesses.

Pure standard library: `int`, `fractions.Fraction`, `hashlib`, `struct`, `json`.
Zero floating-point arithmetic, zero bare asserts, zero RNG modules (deterministic LCG only),
zero GPU, zero network. Every rational leaves the oracle as a canonical `"p/q"` string.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import re
import struct
from typing import Any

TRACK_ID = "TRACK-S104-KRONECKER-FACTORED-EMBEDDINGS-AND-TRIPLE-GATE"
SCHEMA_VERSION = "aletheia.s104_kronecker_triple_gate.v1"
SPEC_SCHEMA_VERSION = "aletheia.s104_exp_delta_latent_repair_spec.v1"
RESULTS_SCHEMA_VERSION = "aletheia.s104_exp_delta_results.v1"
EXPECTED_LEAN_TOOLCHAIN = "leanprover/lean4:v4.36.0"
LEAN_MODULE = "KroneckerFactoredEmbeddings"
LEAN_SOURCE_NAME = "KroneckerFactoredEmbeddings.lean"
SPEC_FILE_NAME = "exp_delta_latent_repair_spec.json"
CERT_FILE_NAME = "s104_kronecker_triple_gate_certificate.json"

PINNED_LEAN_SOURCE_SHA256 = "292b1593d433616b22a309aae12487a11ce1aef3ebc5269f99fc652a5463a740"
PINNED_LEAN_TOOLCHAIN_SHA256 = "582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a"
PINNED_LAKEFILE_SHA256 = "f4fbfda92a6b09c65991d80910bcd3ff4bd5b41ab4581740c9dcc0ff0a30376e"

LEAN_THEOREM_SHORT_NAMES: tuple[str, ...] = (
    "dot_append",
    "dot_scale_scale",
    "kron_length",
    "kron_dot",
    "kron_sqnorm",
    "kron_rows_equal_norm",
    "shared_root_gram",
    "shared_root_annihilated_by_orthogonal_patterns",
    "rank1_minor_identity",
    "additive_kernel_not_rank1",
    "cp2_gram",
    "onehot_dot",
    "additive_kernel_rank2_realized",
    "hybrid_gram",
    "hybrid_shared_root_survives_orthogonal_patterns",
    "hybrid_rows_equal_norm",
    "factored_params_le_full",
    "gate_filters_commute",
    "triple_gate_le_static",
    "triple_gate_strict_of_witness",
    "holdout_zero_kills_composed",
    "zero_success_bound",
    "lane_local_nonexpansive",
    "lane_local_fails_avalanche",
    "latent_repair_collision_ceiling",
)
LEAN_THEOREM_NAMES: tuple[str, ...] = tuple(f"{LEAN_MODULE}.{n}" for n in LEAN_THEOREM_SHORT_NAMES)

# Upstream pins (paths relative to the expedition root; verified on disk by `--verify-pins`).
UPSTREAM_PINS: tuple[dict[str, Any], ...] = (
    {"id": "S92_CERT", "relpath": "track-s92-raw-arabic-scientific-mesh/s92_raw_arabic_mesh_certificate.json",
     "bytes": 26339, "sha256": "294e26e91bfa8cae6c3e48c44a8e9acea37404932eaf4855c05f2e8eaad0738b"},
    {"id": "S100_CERT", "relpath": "track-s100-tokenpage-abios-scry-and-m1max-handoff/s100_tokenpage_handoff_certificate.json",
     "bytes": 21363, "sha256": "0c478d77f191491f18f06968a9563ef117c765d982c6abc6e03d27c2ef75dd4d"},
    {"id": "S31_CERT", "relpath": "track-s31-aletheia-v22-society-misfolding-tomography/aletheia_v22_misfolding_certificate.json",
     "bytes": 12707, "sha256": "f4f7f8abff0c7eae0d5678016c1041ab34870ef2de57a2f83e4cbb9a529f8a9b"},
    {"id": "ML4_FACTORED_EMBEDDINGS", "relpath": "verification/reports/COLLAB-ML4-S92-S100-FACTORED-EMBEDDINGS.md",
     "bytes": 10420, "sha256": "4f9ddaca01064d1ff4f80bff1b50647899a6ea3557de577699b7e06d5bc20d2c"},
    {"id": "ML4_5ORG_OPTIFAB", "relpath": "verification/reports/COLLAB-ML4-5ORG-OPTIFAB-SYNTHESIS.md",
     "bytes": 8134, "sha256": "e59ea01ed52630b866b59183267de593b2fa20870d388617b7584b793304168b"},
    {"id": "PEER_WEFT_MCPROOF_MINING", "relpath": "peer-web/weft_loom_data_and_mcproof_mining.md",
     "bytes": 48720, "sha256": "899e8ca001539ef397105f13319c84ab8df01b21e89215a4df88aa019da67d43"},
    {"id": "PEER_SPLICEWARE_EXCAVATION", "relpath": "peer-web/spliceware_weft_deep_excavation.md",
     "bytes": 41799, "sha256": "3e767e7efe5372bf6aba1eb67b759b49c71ecdc32a986fb88564ef1b891c7050"},
    {"id": "AUDIT_149_HAMPACK", "relpath": "verification/reports/AUDIT-149.md",
     "bytes": 11002, "sha256": "10258a6da1563a710077bcc398f3f89e6a9eaa64fda59cc467cc61788f399e3c"},
)

_HEX64_CHARS = frozenset("0123456789abcdef")
_LEAF_TYPES = frozenset({str, bool, type(None)})
_MATRIX_ENTRY_TYPES = frozenset({int, Fraction})
M32 = 0xFFFFFFFF


class S104Error(ValueError):
    """Fail-closed typed error for Track S104."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def require_ok(cond: Any, code: str, detail: str) -> None:
    if cond is not True:
        raise S104Error(code, detail)


def require_bool(val: Any, label: str) -> bool:
    require_ok(type(val) is bool, "INVALID_BOOL", f"{label} must be exact bool")
    return val


def require_exact_int(val: Any, label: str, *, lo: int | None = None, hi: int | None = None) -> int:
    require_ok(type(val) is int, "INVALID_INT", f"{label} must be exact int")
    if lo is not None:
        require_ok(val >= lo, "INT_OUT_OF_RANGE", f"{label} < {lo}")
    if hi is not None:
        require_ok(val <= hi, "INT_OUT_OF_RANGE", f"{label} > {hi}")
    return val


def require_exact_str(val: Any, label: str) -> str:
    require_ok(type(val) is str, "INVALID_STR", f"{label} must be exact str")
    return val


def require_hex64(val: Any, label: str) -> str:
    s = require_exact_str(val, label)
    require_ok(len(s) == 64, "INVALID_HEX64", f"{label} must have 64 chars")
    require_ok(frozenset(s) <= _HEX64_CHARS, "INVALID_HEX64", f"{label} must be lowercase hex")
    return s


def validate_strict_json_tree(obj: Any, label: str = "root") -> None:
    """Iterative strict JSON-tree validator: exact dict/list/str/int/bool/None only, depth <= 32."""
    stack: list[tuple[Any, str, int]] = [(obj, label, 0)]
    while stack:
        cur, lab, depth = stack.pop()
        require_ok(depth <= 32, "JSON_DEPTH_EXCEEDED", f"{lab}: depth > 32")
        t = type(cur)
        if t is int:
            require_ok(cur.bit_length() <= 2048, "INT_BIT_LIMIT", f"{lab}: int exceeds 2048 bits")
        elif t is list:
            for i, item in enumerate(cur):
                stack.append((item, f"{lab}[{i}]", depth + 1))
        elif t is dict:
            for k, v in cur.items():
                require_ok(type(k) is str, "INVALID_JSON_KEY", f"{lab}: non-str key")
                stack.append((v, f"{lab}.{k}", depth + 1))
        else:
            require_ok(t in _LEAF_TYPES, "FORBIDDEN_JSON_TYPE", f"{lab}: disallowed type {t.__name__}")


def canonical_json_bytes(obj: Any) -> bytes:
    validate_strict_json_tree(obj)
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return (text + "\n").encode("ascii")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fmt_q(q: Fraction) -> str:
    require_ok(type(q) is Fraction, "INVALID_FRACTION", "expected Fraction")
    if q.denominator == 1:
        return str(q.numerator)
    return f"{q.numerator}/{q.denominator}"


def fmt_dec_q(q: Fraction, places: int) -> str:
    """Round-half-up decimal rendering of an exact rational (display only)."""
    require_ok(type(q) is Fraction, "INVALID_FRACTION", "expected Fraction")
    require_exact_int(places, "places", lo=0, hi=18)
    scale = 10 ** places
    scaled = q * scale
    num = scaled.numerator
    den = scaled.denominator
    neg = num < 0
    if neg:
        num = -num
    quot, rem = divmod(num, den)
    if 2 * rem >= den:
        quot += 1
    sign = "-" if neg else ""
    if places == 0:
        return f"{sign}{quot}"
    ip, fp = divmod(quot, scale)
    return f"{sign}{ip}.{fp:0{places}d}"


def round_half_even(q: Fraction) -> int:
    require_ok(type(q) is Fraction, "INVALID_FRACTION", "expected Fraction")
    fl = q.numerator // q.denominator
    rem = q - fl
    if rem > Fraction(1, 2):
        return fl + 1
    if rem < Fraction(1, 2):
        return fl
    return fl + (fl % 2)


# ---------------------------------------------------------------------------
# Exact linear algebra over Q
# ---------------------------------------------------------------------------

def _require_matrix(m: Any, label: str) -> tuple[int, int]:
    require_ok(type(m) is list, "INVALID_MATRIX", f"{label} must be a list")
    require_ok(len(m) > 0, "EMPTY_MATRIX", f"{label} must be non-empty")
    require_ok(type(m[0]) is list, "INVALID_MATRIX_ROW", f"{label} rows must be lists")
    ncols = len(m[0])
    require_ok(ncols > 0, "EMPTY_MATRIX_ROW", f"{label} rows must be non-empty")
    for row in m:
        require_ok(type(row) is list, "INVALID_MATRIX_ROW", f"{label} rows must be lists")
        require_ok(len(row) == ncols, "RAGGED_MATRIX", f"{label} is ragged")
        for x in row:
            require_ok(type(x) in _MATRIX_ENTRY_TYPES, "INVALID_MATRIX_ENTRY", f"{label} entry must be int/Fraction")
    return len(m), ncols


def dot_q(u: list[Any], v: list[Any]) -> Fraction:
    require_ok(len(u) == len(v), "DIM_MISMATCH", "dot dimension mismatch")
    acc = Fraction(0)
    for a, b in zip(u, v):
        acc += Fraction(a) * Fraction(b)
    return acc


def kron_vec(a: list[Any], b: list[Any]) -> list[Fraction]:
    return [Fraction(x) * Fraction(y) for x in a for y in b]


def kron_mat(a: list[list[Any]], b: list[list[Any]]) -> list[list[Fraction]]:
    ra, ca = _require_matrix(a, "kron_a")
    rb, cb = _require_matrix(b, "kron_b")
    return [[Fraction(a[i // rb][j // cb]) * Fraction(b[i % rb][j % cb]) for j in range(ca * cb)] for i in range(ra * rb)]


def gram(rows: list[list[Any]]) -> list[list[Fraction]]:
    _require_matrix(rows, "gram_rows")
    return [[dot_q(u, v) for v in rows] for u in rows]


def rank_q(m: list[list[Any]]) -> int:
    nr, nc = _require_matrix(m, "rank_input")
    a = [[Fraction(x) for x in row] for row in m]
    rank = 0
    for col in range(nc):
        piv = -1
        for r in range(rank, nr):
            if a[r][col] != 0:
                piv = r
                break
        if piv < 0:
            continue
        a[rank], a[piv] = a[piv], a[rank]
        for r in range(nr):
            if r != rank:
                f = a[r][col] / a[rank][col]
                a[r] = [x - f * y for x, y in zip(a[r], a[rank])]
        rank += 1
    return rank


def inverse_q(m: list[list[Any]]) -> list[list[Fraction]]:
    nr, nc = _require_matrix(m, "inverse_input")
    require_ok(nr == nc, "NOT_SQUARE", "inverse requires square matrix")
    a = [[Fraction(x) for x in row] + [Fraction(1 if i == j else 0) for j in range(nr)] for i, row in enumerate(m)]
    for col in range(nr):
        piv = -1
        for r in range(col, nr):
            if a[r][col] != 0:
                piv = r
                break
        require_ok(piv >= 0, "SINGULAR_MATRIX", "matrix is singular")
        a[col], a[piv] = a[piv], a[col]
        p = a[col][col]
        a[col] = [x / p for x in a[col]]
        for r in range(nr):
            if r != col:
                f = a[r][col]
                a[r] = [x - f * y for x, y in zip(a[r], a[col])]
    return [row[nr:] for row in a]


def mat_mul(a: list[list[Any]], b: list[list[Any]]) -> list[list[Fraction]]:
    _, ca = _require_matrix(a, "mul_a")
    rb, cb = _require_matrix(b, "mul_b")
    require_ok(ca == rb, "DIM_MISMATCH", "matmul dimension mismatch")
    return [[sum((Fraction(row[k]) * Fraction(b[k][j]) for k in range(ca)), Fraction(0)) for j in range(cb)] for row in a]


def submatrix(m: list[list[Any]], rows: list[int], cols: list[int]) -> list[list[Fraction]]:
    return [[Fraction(m[i][j]) for j in cols] for i in rows]


def schur_complement_q(m: list[list[Any]], elim: list[int]) -> list[list[Fraction]]:
    """Exact Schur complement M / M[S,S] = M[T,T] - M[T,S] M[S,S]^{-1} M[S,T]."""
    n, nc = _require_matrix(m, "schur_input")
    require_ok(n == nc, "NOT_SQUARE", "schur requires square matrix")
    keep = [i for i in range(n) if i not in elim]
    require_ok(len(keep) > 0, "EMPTY_SCHUR_KEEP", "kept block must be non-empty")
    require_ok(len(elim) > 0, "EMPTY_SCHUR_ELIM", "eliminated block must be non-empty")
    corr = mat_mul(mat_mul(submatrix(m, keep, elim), inverse_q(submatrix(m, elim, elim))), submatrix(m, elim, keep))
    base = submatrix(m, keep, keep)
    return [[base[i][j] - corr[i][j] for j in range(len(keep))] for i in range(len(keep))]


def vlp_rearrange(g: list[list[Any]], r0: int, p0: int) -> list[list[Fraction]]:
    """Van Loan-Pitsianis rearrangement: rank 1 iff g = G_A (r0 x r0) kron G_B (p0 x p0)."""
    n, nc = _require_matrix(g, "vlp_input")
    require_ok(n == nc, "NOT_SQUARE", "vlp requires square matrix")
    require_ok(n == r0 * p0, "VLP_SHAPE_MISMATCH", "vlp shape mismatch")
    return [[Fraction(g[r * p0 + p][rp * p0 + pp]) for p in range(p0) for pp in range(p0)]
            for r in range(r0) for rp in range(r0)]


def row_concentration_q(rows: list[list[Any]]) -> Fraction:
    """S31 DPI row concentration C_row = n * max_i ||row_i||^2 / sum_i ||row_i||^2 (>= 1, == 1 iff flat)."""
    _require_matrix(rows, "c_row_input")
    energies = [dot_q(r, r) for r in rows]
    total = sum(energies, Fraction(0))
    require_ok(total > 0, "ZERO_ENERGY", "row energies sum to zero")
    return Fraction(len(rows)) * max(energies) / total


def lcg_stream(seed: int, count: int, lo: int, hi: int) -> list[int]:
    """Deterministic 64-bit LCG (Knuth MMIX constants); no RNG module."""
    x = seed & 0xFFFFFFFFFFFFFFFF
    span = hi - lo + 1
    out: list[int] = []
    for _ in range(count):
        x = (6364136223846793005 * x + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        out.append(lo + ((x >> 33) % span))
    return out


def lcg_matrix(seed: int, nr: int, nc: int) -> list[list[Fraction]]:
    nums = lcg_stream(seed, nr * nc, -6, 6)
    dens = lcg_stream(seed ^ 0x5A5A5A5A, nr * nc, 1, 4)
    return [[Fraction(nums[i * nc + j], dens[i * nc + j]) for j in range(nc)] for i in range(nr)]


# ---------------------------------------------------------------------------
# Pillar 1: Kronecker product-code algebra (budget, Gram, Schur, DPI)
# ---------------------------------------------------------------------------

ML4_R, ML4_P, ML4_D1, ML4_D2 = 4096, 512, 64, 16
QWEN25_PADDED_VOCAB = 151936  # pinned in S100 certificate (`padded_vocab_size`)

# Calibrated factor rows: every A row has ||.||^2 = 9, every B row (Hadamard H4 rows) ||.||^2 = 4.
CAL_A: tuple[tuple[int, ...], ...] = ((2, 1, 2, 0), (1, -2, 0, 2), (0, 2, -1, 2), (2, 0, -2, -1))
CAL_B: tuple[tuple[int, ...], ...] = ((1, 1, 1, 1), (1, -1, 1, -1), (1, 1, -1, -1))
CAL_A_APPENDED_ROOT: tuple[int, ...] = (0, 0, 3, 0)


def build_param_budget() -> dict[str, Any]:
    full = ML4_R * ML4_P * ML4_D1 * ML4_D2
    fact = ML4_R * ML4_D1 + ML4_P * ML4_D2
    ratio = Fraction(full, fact)
    flat_real = QWEN25_PADDED_VOCAB * ML4_D1 * ML4_D2
    ratio_real = Fraction(flat_real, fact)
    return {
        "roots_R": ML4_R, "patterns_P": ML4_P, "d1": ML4_D1, "d2": ML4_D2, "d": ML4_D1 * ML4_D2,
        "full_table_rows": ML4_R * ML4_P,
        "full_table_params": full,
        "factored_params": fact,
        "reduction_ratio_q": fmt_q(ratio),
        "reduction_ratio_dec3": fmt_dec_q(ratio, 3),
        "ml4_7900x_headline_is_valid_lower_bound": Fraction(7900) <= ratio,
        "factored_fp16_bytes": 2 * fact,
        "qwen25_padded_vocab_rows": QWEN25_PADDED_VOCAB,
        "qwen25_flat_params_at_d1024": flat_real,
        "realistic_reduction_ratio_q": fmt_q(ratio_real),
        "realistic_reduction_ratio_dec3": fmt_dec_q(ratio_real, 3),
        "hypothetical_rows_over_real_vocab_q": fmt_q(Fraction(ML4_R * ML4_P, QWEN25_PADDED_VOCAB)),
    }


def build_kronecker_identities() -> dict[str, Any]:
    r0, p0, d1, d2 = 4, 3, 5, 4
    a = lcg_matrix(104001, r0, d1)
    b = lcg_matrix(104002, p0, d2)
    rows = [kron_vec(a[r], b[p]) for r in range(r0) for p in range(p0)]
    pairs_ok = 0
    norms_ok = 0
    for i, u in enumerate(rows):
        r, p = divmod(i, p0)
        if dot_q(u, u) == dot_q(a[r], a[r]) * dot_q(b[p], b[p]):
            norms_ok += 1
        for j, v in enumerate(rows):
            rp, pp = divmod(j, p0)
            if dot_q(u, v) == dot_q(a[r], a[rp]) * dot_q(b[p], b[pp]):
                pairs_ok += 1
    g_a = gram(a)
    g_b = gram(b)
    g_e = gram(rows)
    elim_roots = [0, 1]
    elim_idx = [r * p0 + p for r in elim_roots for p in range(p0)]
    lhs = schur_complement_q(g_e, elim_idx)
    rhs = kron_mat(schur_complement_q(g_a, elim_roots), g_b)
    flat = lcg_matrix(104003, r0 * p0, d1 * d2)
    g_flat = gram(flat)
    return {
        "roots_r0": r0, "patterns_p0": p0, "d1": d1, "d2": d2,
        "seeds": [104001, 104002, 104003],
        "pair_identities_checked": len(rows) * len(rows),
        "pair_identities_hold": pairs_ok,
        "norm_identities_checked": len(rows),
        "norm_identities_hold": norms_ok,
        "gram_equals_kron_of_grams": g_e == kron_mat(g_a, g_b),
        "det_gram_b_q": fmt_q(_det_q(g_b)),
        "det_gram_a_elim_block_q": fmt_q(_det_q(submatrix(g_a, elim_roots, elim_roots))),
        "schur_eliminated_roots": elim_roots,
        "schur_kron_commutes": lhs == rhs,
        "schur_trace_q": fmt_q(sum((lhs[i][i] for i in range(len(lhs))), Fraction(0))),
        "kron_gram_vlp_rank": rank_q(vlp_rearrange(g_e, r0, p0)),
        "flat_table_gram_vlp_rank": rank_q(vlp_rearrange(g_flat, r0, p0)),
        "flat_table_fractures_root_quotient": rank_q(vlp_rearrange(g_flat, r0, p0)) > 1,
    }


def _det_q(m: list[list[Any]]) -> Fraction:
    n, nc = _require_matrix(m, "det_input")
    require_ok(n == nc, "NOT_SQUARE", "det requires square matrix")
    a = [[Fraction(x) for x in row] for row in m]
    det = Fraction(1)
    for col in range(n):
        piv = -1
        for r in range(col, n):
            if a[r][col] != 0:
                piv = r
                break
        if piv < 0:
            return Fraction(0)
        if piv != col:
            a[col], a[piv] = a[piv], a[col]
            det = -det
        det *= a[col][col]
        for r in range(col + 1, n):
            f = a[r][col] / a[col][col]
            a[r] = [x - f * y for x, y in zip(a[r], a[col])]
    return det


def build_dpi_calibration() -> dict[str, Any]:
    a = [list(r) for r in CAL_A]
    b = [list(r) for r in CAL_B]
    r0, p0 = len(a), len(b)
    table = [kron_vec(a[r], b[p]) for r in range(r0) for p in range(p0)]
    appended = table + [kron_vec(list(CAL_A_APPENDED_ROOT), b[p]) for p in range(p0)]
    flat = lcg_matrix(104004, r0 * p0, len(a[0]) * len(b[0]))
    # Norm-preserving misfold of root 0: replace A_0 by a signed permutation (same ||.||^2 = 9).
    a0_new = [0, 2, 1, -2]
    delta = [Fraction(x - y) for x, y in zip(a0_new, a[0])]
    table_patched = [kron_vec(a0_new if r == 0 else a[r], b[p]) for r in range(r0) for p in range(p0)]
    delta_rows = [[x - y for x, y in zip(u, v)] for u, v in zip(table_patched, table)]
    flat_patch = [[Fraction(0)] * len(flat[0]) for _ in flat]
    flat_patch[0] = [Fraction(1)] * len(flat[0])
    return {
        "a_row_sqnorms": [int(dot_q(r, r)) for r in a],
        "b_row_sqnorms": [int(dot_q(r, r)) for r in b],
        "table_rows": len(table),
        "table_row_sqnorms_distinct": sorted({int(dot_q(r, r)) for r in table}),
        "table_c_row_q": fmt_q(row_concentration_q(table)),
        "appended_root_inherits_calibration": row_concentration_q(appended) == 1,
        "flat_lcg_table_c_row_q": fmt_q(row_concentration_q(flat)),
        "misfold_delta_a0": [int(x) for x in delta],
        "misfold_preserves_a0_sqnorm": dot_q(a0_new, a0_new) == dot_q(a[0], a[0]),
        "patched_table_c_row_q": fmt_q(row_concentration_q(table_patched)),
        "table_level_dpi_blind_to_norm_preserving_misfold": row_concentration_q(table_patched) == 1,
        "patch_c_row_q": fmt_q(row_concentration_q(delta_rows)),
        "patch_c_row_equals_r0": row_concentration_q(delta_rows) == r0,
        "flat_single_row_patch_c_row_q": fmt_q(row_concentration_q(flat_patch)),
        "ml4_scale_root_patch_c_row": ML4_R,
        "ml4_scale_pattern_patch_c_row": ML4_P,
        "ml4_scale_flat_single_row_patch_c_row": ML4_R * ML4_P,
    }


def build_pillar1_kronecker_algebra() -> dict[str, Any]:
    return {
        "param_budget": build_param_budget(),
        "kronecker_identities": build_kronecker_identities(),
        "dpi_calibration": build_dpi_calibration(),
    }


# ---------------------------------------------------------------------------
# Pillar 2: rank-1 expressivity obstruction and rank-2 / hybrid lift
# ---------------------------------------------------------------------------

def delta_int(i: int, j: int) -> int:
    return 1 if i == j else 0


def onehot_vec(n: int, i: int) -> list[int]:
    return [delta_int(k, i) for k in range(n)]


def build_pillar2_rank1_obstruction() -> dict[str, Any]:
    r0, p0 = 3, 3
    idx = [(r, p) for r in range(r0) for p in range(p0)]
    additive = [[delta_int(r, rp) + delta_int(p, pp) for (rp, pp) in idx] for (r, p) in idx]
    concat_rows = [onehot_vec(r0, r) + onehot_vec(p0, p) for (r, p) in idx]
    kron_rows = [kron_vec(onehot_vec(r0, r), onehot_vec(p0, p)) for (r, p) in idx]
    hybrid_rows = [kron_vec(onehot_vec(r0, r), onehot_vec(p0, p)) + [Fraction(x) for x in onehot_vec(r0, r) + onehot_vec(p0, p)]
                   for (r, p) in idx]
    # 2x2 minor on the additive kernel at (r,r')=(0,1), (p,p')=(0,1)
    k_01_00 = delta_int(0, 1) + delta_int(0, 0)
    k_00_01 = delta_int(0, 0) + delta_int(0, 1)
    k_00_00 = delta_int(0, 0) + delta_int(0, 0)
    k_01_01 = delta_int(0, 1) + delta_int(0, 1)
    # Theorem 8 vs Theorem 15 on calibrated factors (Hadamard pattern rows are mutually orthogonal)
    a0 = list(CAL_A[0])
    b0, b1 = list(CAL_B[0]), list(CAL_B[1])
    kron_shared = dot_q(kron_vec(a0, b0), kron_vec(a0, b1))
    hyb0 = kron_vec(a0, b0) + [Fraction(x) for x in a0 + b0]
    hyb1 = kron_vec(a0, b1) + [Fraction(x) for x in a0 + b1]
    return {
        "grid_r0": r0, "grid_p0": p0,
        "additive_minor_lhs": k_01_00 * k_00_01,
        "additive_minor_rhs": k_00_00 * k_01_01,
        "additive_kernel_violates_rank1_minor": k_01_00 * k_00_01 != k_00_00 * k_01_01,
        "additive_kernel_vlp_rank": rank_q(vlp_rearrange(additive, r0, p0)),
        "kron_onehot_gram_vlp_rank": rank_q(vlp_rearrange(gram(kron_rows), r0, p0)),
        "concat_onehot_gram_equals_additive": gram(concat_rows) == [[Fraction(x) for x in row] for row in additive],
        "hybrid_onehot_gram_vlp_rank": rank_q(vlp_rearrange(gram(hybrid_rows), r0, p0)),
        "calibrated_pattern_rows_orthogonal": dot_q(b0, b1) == 0,
        "kron_shared_root_cross_pattern_similarity_q": fmt_q(kron_shared),
        "hybrid_shared_root_cross_pattern_similarity_q": fmt_q(dot_q(hyb0, hyb1)),
        "hybrid_row_sqnorm_q": fmt_q(dot_q(hyb0, hyb0)),
        "ml4_root_floor_claim_holds_for_rank1": kron_shared > 0,
        "hybrid_restores_root_floor": dot_q(hyb0, hyb1) == dot_q(a0, a0),
    }


# ---------------------------------------------------------------------------
# Pillar 3: EXP-Delta latent-repair preregistration audit, spec & exact evaluator
# ---------------------------------------------------------------------------

S92_EDGES_TOTAL = 664
S92_EDGES_SURFACE = 319
S92_CROSS_TOTAL = 85
S92_CROSS_SURFACE = 7
S92_TRIANGLES_TOTAL = 220
ALPHA = Fraction(1, 20)
PERMUTATIONS_B = 250
HOLM_M = 3

REPAIRED_GATES: dict[str, int] = {
    "pass_overall_max": 320,
    "kill_overall_min": 340,
    "pass_cross_max": 8,
    "kill_cross_min": 14,
    "pass_tri_max": 24,
    "kill_tri_min": 49,
    "node_agreement_max_abs": 2,
    "vram_3080_max_mib": 7680,
    "wall_3080_max_s": 600,
    "ram_m1_max_mib": 20480,
    "wall_m1_max_s": 1800,
}


def surface_triangle_model_q() -> Fraction:
    return S92_TRIANGLES_TOTAL * Fraction(S92_EDGES_SURFACE, S92_EDGES_TOTAL) ** 3


def build_pillar3_exp_delta() -> dict[str, Any]:
    tri = surface_triangle_model_q()
    tri_floor = tri.numerator // tri.denominator
    kill_tri_repaired = -((-2 * tri.numerator) // tri.denominator)
    min_p = Fraction(1, PERMUTATIONS_B + 1)
    spec_sha = sha256_hex(canonical_json_bytes(build_exp_delta_spec()))
    return {
        "surface": {
            "edges_total": S92_EDGES_TOTAL, "edges_surface_retained": S92_EDGES_SURFACE,
            "edge_loss_q": fmt_q(Fraction(S92_EDGES_TOTAL - S92_EDGES_SURFACE, S92_EDGES_TOTAL)),
            "cross_total": S92_CROSS_TOTAL, "cross_surface_retained": S92_CROSS_SURFACE,
            "cross_loss_q": fmt_q(Fraction(S92_CROSS_TOTAL - S92_CROSS_SURFACE, S92_CROSS_TOTAL)),
            "triangles_total": S92_TRIANGLES_TOTAL,
            "triangle_independence_model_q": fmt_q(tri),
            "triangle_independence_model_dec4": fmt_dec_q(tri, 4),
            "cross_triangle_independence_q": fmt_q(Fraction(S92_CROSS_SURFACE, S92_CROSS_TOTAL) ** 3),
        },
        "ml4_gate_checks": {
            "pass_overall_is_surface_plus_one": 320 == S92_EDGES_SURFACE + 1,
            "pass_cross_is_surface_plus_one": 8 == S92_CROSS_SURFACE + 1,
            "kill_cross_is_twice_surface": 14 == 2 * S92_CROSS_SURFACE,
            "pass_tri_is_floor_of_model": 24 == tri_floor,
            "ml4_kill_tri": 44,
            "ml4_kill_tri_over_model_q": fmt_q(Fraction(44) / tri),
            "ml4_kill_tri_over_model_dec4": fmt_dec_q(Fraction(44) / tri, 4),
            "ml4_kill_tri_is_at_least_twice_model": Fraction(44) >= 2 * tri,
            "repaired_kill_tri_ceil_twice_model": kill_tri_repaired,
        },
        "holm_resolution": {
            "permutations_B": PERMUTATIONS_B, "hypotheses_m": HOLM_M, "alpha_q": fmt_q(ALPHA),
            "min_attainable_p_q": fmt_q(min_p),
            "holm_first_step_threshold_q": fmt_q(ALPHA / HOLM_M),
            "permutation_budget_resolves_holm": min_p <= ALPHA / HOLM_M,
        },
        "repaired_gates": dict(REPAIRED_GATES),
        "spec_file": SPEC_FILE_NAME,
        "spec_sha256": spec_sha,
        "evaluator_selftest": evaluator_selftest(),
        "executed": False,
    }


def build_exp_delta_spec() -> dict[str, Any]:
    pins = {r["id"]: r["sha256"] for r in UPSTREAM_PINS}
    return {
        "schema_version": SPEC_SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "status": "PREREGISTERED_NOT_EXECUTED",
        "pins": {
            "s92_certificate_sha256": pins["S92_CERT"],
            "s100_certificate_sha256": pins["S100_CERT"],
            "ml4_critique_sha256": pins["ML4_FACTORED_EMBEDDINGS"],
        },
        "assets": {
            "catalog_pairs": 148,
            "edge_set": "S92 K12 stem_v1 (664 edges, 85 cross-discipline, 220 triangles)",
            "models": ["Qwen2.5-1.5B (primary, both nodes)", "Qwen2.5-7B (M1 Max scale-replication arm)"],
            "weights_location": "outside expedition/ only; HF_HUB_OFFLINE=1; zero dataset or weight copies inside expedition/",
        },
        "procedure": [
            "Mean-pool layer-normalized hidden states at layers L/2 and L over content tokens for every catalog entry, Arabic and English.",
            "Edge-disjoint 2-fold cross-fit: split the 664 positive edges and the matched non-edges into two folds; train an L2-logistic scorer f(h_ar(u), h_ar(v)) on Arabic states of fold k and score English states of fold 1-k, so every edge is scored exactly once by a scorer that never saw its label.",
            "Calibrate the decision threshold on the Arabic training fold so that the English non-edge false-positive count does not exceed the surface stem-match false-positive count (matched-FPR recall; an all-positive scorer cannot reach KILL).",
            "Count r_hidden (of 664), r_hidden_cross (of 85), t_hidden (of 220) on the cross-fitted predictions.",
            "Null: B = 250 pair-permutations of the English-to-Arabic alignment; Holm-Bonferroni over m = 3 rows at alpha = 1/20.",
            "Node agreement: run the SAME Qwen2.5-1.5B arm on RTX 3080 and M1 Max; the 7B arm is a separate replication with its own gates.",
        ],
        "gates": {
            "pass_all": "r_hidden <= 320/664 and r_hidden_cross <= 8/85 and t_hidden <= 24/220",
            "kill_any": "r_hidden_cross >= 14/85 or r_hidden >= 340/664 or t_hidden >= 49/220, each with Holm p_adj <= 1/20",
            "abstain": "anything between PASS and KILL, any unmatched FPR, or same-model node disagreement > 2/664",
            "fail_closed": "any OOM, timeout, or resource-cap breach",
            "thresholds": dict(REPAIRED_GATES),
        },
        "hardware": {
            "rtx3080": "8 GiB; forward-only fp16, seq 512, batch 8; wrap in mlos gpu-lease --mode train + mlos stamp-run --zone B; start only after S95/S97 release the GPU; check AC power before sustained runs",
            "m1max": "64 GiB; same 1.5B arm for node agreement plus the 7B replication arm",
        },
        "scope": "PASS supports only: not recoverable by a matched-FPR L2-logistic probe at this capacity. It does not by itself establish an information-theoretic ceiling.",
        "results_schema_version": RESULTS_SCHEMA_VERSION,
        "results_int_fields": [[name, hi] for name, hi in _RESULT_INT_FIELDS],
        "results_rational_fields": list(_RESULT_Q_FIELDS),
    }


_RESULT_INT_FIELDS: tuple[tuple[str, int], ...] = (
    ("r_hidden", S92_EDGES_TOTAL),
    ("r_hidden_cross", S92_CROSS_TOTAL),
    ("t_hidden", S92_TRIANGLES_TOTAL),
    ("fp_hidden", 1 << 32),
    ("fp_budget", 1 << 32),
    ("r_hidden_node_a", S92_EDGES_TOTAL),
    ("r_hidden_node_b", S92_EDGES_TOTAL),
    ("peak_vram_mib", 1 << 20),
    ("wall_3080_s", 1 << 20),
    ("ram_m1_mib", 1 << 22),
    ("wall_m1_s", 1 << 20),
)
_RESULT_Q_FIELDS: tuple[str, ...] = ("p_adj_overall", "p_adj_cross", "p_adj_tri")
_UNIT_RAT_RE = re.compile(r"([0-9]{1,40})/([1-9][0-9]{0,39})")


def parse_unit_rational(val: Any, label: str) -> Fraction:
    s = require_exact_str(val, label)
    m = _UNIT_RAT_RE.fullmatch(s)
    require_ok(m is not None, "INVALID_RATIONAL_STR", f"{label}: expected p/q with ASCII digits")
    q = Fraction(int(m.group(1)), int(m.group(2)))
    require_ok(q <= 1, "P_VALUE_OUT_OF_RANGE", f"{label}: p-value above 1")
    return q


def evaluate_exp_delta_results(results: Any) -> str:
    """Exact three-valued EXP-Delta verdict under the repaired preregistration."""
    require_ok(type(results) is dict, "INVALID_RESULTS", "results must be exact dict")
    expected = frozenset([n for n, _ in _RESULT_INT_FIELDS] + list(_RESULT_Q_FIELDS) + ["schema_version"])
    require_ok(frozenset(results.keys()) == expected, "RESULTS_KEYSET_MISMATCH", "results keyset mismatch")
    require_ok(results["schema_version"] == RESULTS_SCHEMA_VERSION, "RESULTS_SCHEMA_MISMATCH", "results schema")
    v: dict[str, int] = {}
    for name, hi in _RESULT_INT_FIELDS:
        v[name] = require_exact_int(results[name], name, lo=0, hi=hi)
    p = {name: parse_unit_rational(results[name], name) for name in _RESULT_Q_FIELDS}
    g = REPAIRED_GATES
    if v["peak_vram_mib"] > g["vram_3080_max_mib"]:
        return "FAIL_CLOSED_RESOURCE"
    if v["wall_3080_s"] > g["wall_3080_max_s"]:
        return "FAIL_CLOSED_RESOURCE"
    if v["ram_m1_mib"] > g["ram_m1_max_mib"]:
        return "FAIL_CLOSED_RESOURCE"
    if v["wall_m1_s"] > g["wall_m1_max_s"]:
        return "FAIL_CLOSED_RESOURCE"
    if abs(v["r_hidden_node_a"] - v["r_hidden_node_b"]) > g["node_agreement_max_abs"]:
        return "ABSTAIN_NODE_DISAGREEMENT"
    if v["fp_hidden"] > v["fp_budget"]:
        return "ABSTAIN_FPR_UNMATCHED"
    if v["r_hidden_cross"] >= g["kill_cross_min"]:
        if p["p_adj_cross"] <= ALPHA:
            return "KILL"
    if v["r_hidden"] >= g["kill_overall_min"]:
        if p["p_adj_overall"] <= ALPHA:
            return "KILL"
    if v["t_hidden"] >= g["kill_tri_min"]:
        if p["p_adj_tri"] <= ALPHA:
            return "KILL"
    if v["r_hidden"] > g["pass_overall_max"]:
        return "ABSTAIN_INTERMEDIATE"
    if v["r_hidden_cross"] > g["pass_cross_max"]:
        return "ABSTAIN_INTERMEDIATE"
    if v["t_hidden"] > g["pass_tri_max"]:
        return "ABSTAIN_INTERMEDIATE"
    return "PASS"


def synthetic_results(**overrides: Any) -> dict[str, Any]:
    """SYNTHETIC evaluator fixture (not a measurement): the surface-only baseline."""
    base: dict[str, Any] = {
        "schema_version": RESULTS_SCHEMA_VERSION,
        "r_hidden": S92_EDGES_SURFACE, "r_hidden_cross": S92_CROSS_SURFACE, "t_hidden": 24,
        "fp_hidden": 10, "fp_budget": 10, "r_hidden_node_a": S92_EDGES_SURFACE, "r_hidden_node_b": S92_EDGES_SURFACE,
        "peak_vram_mib": 3500, "wall_3080_s": 120, "ram_m1_mib": 16000, "wall_m1_s": 900,
        "p_adj_overall": "1/2", "p_adj_cross": "1/2", "p_adj_tri": "1/2",
    }
    base.update(overrides)
    return base


def evaluator_selftest() -> list[dict[str, str]]:
    cases: tuple[tuple[str, dict[str, Any]], ...] = (
        ("surface_baseline", {}),
        ("cross_repair_significant", {"r_hidden_cross": 14, "p_adj_cross": "1/251"}),
        ("cross_repair_not_significant", {"r_hidden_cross": 14, "p_adj_cross": "1/10"}),
        ("all_positive_scorer", {"r_hidden": 664, "r_hidden_cross": 85, "fp_hidden": 9000}),
        ("intermediate", {"r_hidden_cross": 11}),
        ("node_disagreement", {"r_hidden_node_b": S92_EDGES_SURFACE + 3}),
        ("vram_breach", {"peak_vram_mib": 7681}),
    )
    return [{"case": name, "verdict": evaluate_exp_delta_results(synthetic_results(**ov))} for name, ov in cases]


# ---------------------------------------------------------------------------
# Pillar 4: composed triple gate, zero-success bound, selection non-commutativity
# ---------------------------------------------------------------------------

def zero_success_upper_bracket(n: int, alpha: Fraction, iters: int) -> tuple[Fraction, Fraction]:
    """Bisection bracket [lo, hi] for the one-sided Clopper-Pearson upper limit p_u, (1 - p_u)^n = alpha."""
    require_exact_int(n, "n", lo=1, hi=100000)
    require_exact_int(iters, "iters", lo=1, hi=64)
    lo, hi = Fraction(0), Fraction(1)
    for _ in range(iters):
        mid = (lo + hi) / 2
        if (1 - mid) ** n > alpha:
            lo = mid
        else:
            hi = mid
    return lo, hi


def gate_filter(cands: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    out = []
    for c in cands:
        if all(c[k] is True for k in keys):
            out.append(c)
    return out


def argmax_val(cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not cands:
        return []
    best = cands[0]
    for c in cands[1:]:
        if c["val"] > best["val"]:
            best = c
    return [best]


def exhaustive_gate_commutation() -> dict[str, int]:
    types = [(s, r, h) for s in (False, True) for r in (False, True) for h in (False, True)]
    lists: list[list[tuple[bool, bool, bool]]] = [[]]
    frontier: list[list[tuple[bool, bool, bool]]] = [[]]
    for _ in range(3):
        frontier = [lst + [t] for lst in frontier for t in types]
        lists.extend(frontier)
    perms = (("s", "r", "h"), ("s", "h", "r"), ("r", "s", "h"), ("r", "h", "s"), ("h", "s", "r"), ("h", "r", "s"))
    checks = 0
    commute = 0
    le_static = 0
    strict_when_witness = 0
    witness_lists = 0
    for lst in lists:
        cands = [{"s": t[0], "r": t[1], "h": t[2]} for t in lst]
        ref = gate_filter(cands, ("s", "r", "h"))
        for perm in perms:
            checks += 1
            cur = cands
            for k in perm:
                cur = gate_filter(cur, (k,))
            if cur == ref:
                commute += 1
        if len(ref) <= len(gate_filter(cands, ("s",))):
            le_static += 1
        if any(t[0] and t[1] and not t[2] for t in lst):
            witness_lists += 1
            if len(ref) < len(gate_filter(cands, ("s",))):
                strict_when_witness += 1
    return {
        "candidate_lists": len(lists),
        "ordering_checks": checks,
        "orderings_commute": commute,
        "composed_le_static": le_static,
        "witness_lists": witness_lists,
        "strict_when_witness": strict_when_witness,
    }


def build_pillar4_triple_gate() -> dict[str, Any]:
    n = 96
    lo, hi = zero_success_upper_bracket(n, ALPHA, 24)
    # Selection non-commutativity witness (synthetic candidates, labels only):
    cands = [
        {"id": "c0", "s": False, "h": True, "val": 10},
        {"id": "c1", "s": True, "h": False, "val": 5},
        {"id": "c2", "s": True, "h": True, "val": 3},
    ]
    select_then_gate = [c["id"] for c in gate_filter(argmax_val(cands), ("s",))]
    gate_then_select = [c["id"] for c in argmax_val(gate_filter(cands, ("s",)))]
    holdout_aware = [c["id"] for c in argmax_val(gate_filter(cands, ("s", "h")))]
    p2b = {"s": True, "r": True, "h": False}
    return {
        "anchors": {
            "oracle_class": "anchor",
            "weft160_lean_proved_edits": 178,
            "weft160_holdout_cost_pairs": [[1149, 1216], [884, 949]],
            "weft160_holdout_regressions": [1216 - 1149, 949 - 884],
            "mcproof_pr3_p2b_val": [2, 48],
            "mcproof_pr3_b0_val": [4, 48],
            "mcproof_pr3_sealed_holdout": [0, 96],
            "mcproof_tc1_cpu_alignment_min_q": fmt_q(Fraction(9985, 10000)),
            "mcproof_tc1_live_retention_q": fmt_q(Fraction(0)),
        },
        "zero_success_bound": {
            "holdout_n": n,
            "alpha_q": fmt_q(ALPHA),
            "rule_of_three_bound_q": fmt_q(Fraction(1, 32)),
            "survival_at_bound_lt_alpha": Fraction(31, 32) ** n < ALPHA,
            "cp_upper_bracket_lo_q": fmt_q(lo),
            "cp_upper_bracket_hi_q": fmt_q(hi),
            "cp_upper_bracket_lo_dec6": fmt_dec_q(lo, 6),
            "cp_upper_bracket_hi_dec6": fmt_dec_q(hi, 6),
            "cp_upper_strictly_below_one_32nd": hi < Fraction(1, 32),
        },
        "gate_commutation": exhaustive_gate_commutation(),
        "selection_noncommutation": {
            "candidates": cands,
            "select_then_static_gate": select_then_gate,
            "static_gate_then_select": gate_then_select,
            "static_and_holdout_gate_then_select": holdout_aware,
            "select_and_gate_do_not_commute": select_then_gate != gate_then_select,
        },
        "mcproof_p2b_composed_gate_accepts": gate_filter([p2b], ("s", "r", "h")) != [],
        "mcproof_p2b_static_gate_accepts": gate_filter([p2b], ("s",)) != [],
    }


# ---------------------------------------------------------------------------
# Pillar 5: RAM == WIRE == HASH (quantize/serialize order, endianness, avalanche)
# ---------------------------------------------------------------------------

def nearest_binary64(q: Fraction) -> tuple[int, int]:
    """Exact round-to-nearest-even binary64 of a positive normal rational: returns (mantissa m, exponent e), value m/2^e."""
    require_ok(type(q) is Fraction, "INVALID_FRACTION", "expected Fraction")
    require_ok(q > 0, "NONPOSITIVE", "positive rational required")
    e = 52 - (q.numerator.bit_length() - q.denominator.bit_length())
    if q * (Fraction(2) ** e) < (1 << 52):
        e += 1
    m = round_half_even(q * (Fraction(2) ** e))
    if m == (1 << 53):
        m //= 2
        e -= 1
    return m, e


def require_cell(cell: Any) -> None:
    require_ok(type(cell) is bytes, "INVALID_CELL_TYPE", "cell must be bytes")
    require_ok(len(cell) == 1088, "INVALID_CELL_LENGTH", "cell must be 1088 bytes")


def rotl32(x: int, n: int) -> int:
    return ((x << n) | (x >> (32 - n))) & M32


_IV8 = (0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A, 0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19)


def lane_local_v3_digest(cell: bytes) -> bytes:
    """Model of the reported spliceware v3 class: arx_permute mixes only (s[i], s[i+4]); constants only cross lanes."""
    require_cell(cell)
    words = struct.unpack("<272I", cell)
    s = list(_IV8)
    for blk in range(0, 272, 8):
        for k in range(8):
            s[k] ^= words[blk + k]
        for rnd in range(8):
            for i in range(4):
                a, b = s[i], s[i + 4]
                a = (a + b) & M32
                b = rotl32(b ^ a, 7)
                a = (a + rotl32(b, 13)) & M32
                b = rotl32(b ^ a, 16)
                s[i], s[i + 4] = a, b
                s[(i + 1) & 3] ^= (rnd * 0x9E3779B9) & M32
    return struct.pack("<8I", *s)


def _chacha_qr(s: list[int], a: int, b: int, c: int, d: int) -> None:
    s[a] = (s[a] + s[b]) & M32
    s[d] = rotl32(s[d] ^ s[a], 16)
    s[c] = (s[c] + s[d]) & M32
    s[b] = rotl32(s[b] ^ s[c], 12)
    s[a] = (s[a] + s[b]) & M32
    s[d] = rotl32(s[d] ^ s[a], 8)
    s[c] = (s[c] + s[d]) & M32
    s[b] = rotl32(s[b] ^ s[c], 7)


def full_diffusion_digest(cell: bytes) -> bytes:
    """ChaCha20-permutation sponge (8-word rate, 8-word capacity): cross-lane diffusion every round."""
    require_cell(cell)
    words = struct.unpack("<272I", cell)
    s = [0x61707865, 0x3320646E, 0x79622D32, 0x6B206574] + [0] * 12
    for blk in range(0, 272, 8):
        for k in range(8):
            s[4 + k] ^= words[blk + k]
        for _ in range(10):
            _chacha_qr(s, 0, 4, 8, 12)
            _chacha_qr(s, 1, 5, 9, 13)
            _chacha_qr(s, 2, 6, 10, 14)
            _chacha_qr(s, 3, 7, 11, 15)
            _chacha_qr(s, 0, 5, 10, 15)
            _chacha_qr(s, 1, 6, 11, 12)
            _chacha_qr(s, 2, 7, 8, 13)
            _chacha_qr(s, 3, 4, 9, 14)
    return struct.pack("<8I", *s[:8])


def sha256_digest(cell: bytes) -> bytes:
    return hashlib.sha256(cell).digest()


def changed_byte_positions(d0: bytes, d1: bytes) -> list[int]:
    require_ok(len(d0) == len(d1), "DIM_MISMATCH", "digest length mismatch")
    return [i for i, (x, y) in enumerate(zip(d0, d1)) if x != y]


def avalanche_counts(digest_fn: Any, cell: bytes) -> list[list[int]]:
    base = digest_fn(cell)
    out: list[list[int]] = []
    for j in range(8):
        mut = bytearray(cell)
        mut[4 * j] ^= 1
        out.append(changed_byte_positions(base, digest_fn(bytes(mut))))
    return out


def build_avalanche() -> dict[str, Any]:
    cell = bytes(lcg_stream(104005, 1088, 0, 255))
    v3 = avalanche_counts(lane_local_v3_digest, cell)
    fd = avalanche_counts(full_diffusion_digest, cell)
    sh = avalanche_counts(sha256_digest, cell)
    lane_ok = 0
    for j, pos in enumerate(v3):
        i = j % 4
        allowed = set(range(4 * i, 4 * i + 4)) | set(range(16 + 4 * i, 20 + 4 * i))
        if set(pos) <= allowed:
            lane_ok += 1
    return {
        "cell_bytes": len(cell),
        "cell_sha256": sha256_hex(cell),
        "digest_bytes": 32,
        "flipped_words": 8,
        "gate_min_changed_bytes": 16,
        "lane_local_v3_changed_bytes": [len(p) for p in v3],
        "lane_local_v3_flips_confined_to_own_lane": lane_ok,
        "lane_local_v3_max_fraction_q": fmt_q(Fraction(max(len(p) for p in v3), 32)),
        "lane_local_v3_passes_gate": min(len(p) for p in v3) >= 16,
        "full_diffusion_changed_bytes": [len(p) for p in fd],
        "full_diffusion_passes_gate": min(len(p) for p in fd) >= 16,
        "sha256_changed_bytes": [len(p) for p in sh],
        "sha256_passes_gate": min(len(p) for p in sh) >= 16,
    }


def build_pillar5_wire_hash() -> dict[str, Any]:
    v = Fraction(3, 20)
    m, e = nearest_binary64(v)
    b = Fraction(m, 1 << e)
    q_exact = round_half_even(10 * v)
    q_wire = round_half_even(10 * b)
    ints = [1, -2, 300, -40000, 2147483647, -2147483648]
    le = struct.pack("<6i", *ints)
    be = struct.pack(">6i", *ints)
    int8_roundtrip = sum(1 for x in range(-128, 128) if struct.unpack("<b", struct.pack("<b", x))[0] == x)
    hampack_bytes = 30615552
    l2_bytes = 4 * 1024 * 1024
    return {
        "quantize_serialize_order": {
            "value_q": fmt_q(v),
            "binary64_mantissa": m,
            "binary64_exponent": e,
            "binary64_mantissa_hex": format(m, "x"),
            "binary64_value_below_exact": b < v,
            "q_exact_round_half_even_10v": q_exact,
            "q_after_float_wire_10v": q_wire,
            "sha256_int8_exact": sha256_hex(struct.pack("<b", q_exact)),
            "sha256_int8_after_float_wire": sha256_hex(struct.pack("<b", q_wire)),
            "quantize_then_serialize_differs": q_exact != q_wire,
        },
        "endianness": {
            "ints": ints,
            "sha256_le": sha256_hex(le),
            "sha256_be": sha256_hex(be),
            "host_order_must_be_pinned": le != be,
            "int8_le_roundtrip_exact": int8_roundtrip,
        },
        "avalanche": build_avalanche(),
        "hampack_locality": {
            "dp_table_bytes_audit149": hampack_bytes,
            "l2_bytes": l2_bytes,
            "ratio_q": fmt_q(Fraction(hampack_bytes, l2_bytes)),
            "ratio_dec4": fmt_dec_q(Fraction(hampack_bytes, l2_bytes), 4),
            "ml4_claimed_ratio_q": fmt_q(Fraction(765, 100)),
            "ml4_ratio_matches": Fraction(hampack_bytes, l2_bytes) == Fraction(765, 100),
        },
        "cross_device_3of3_digest": "NOT_SHOWN",
    }


# ---------------------------------------------------------------------------
# Audit findings registry (steelman of the two Mistral Large 4 critiques)
# ---------------------------------------------------------------------------

AUDIT_FINDINGS: tuple[dict[str, str], ...] = (
    {"id": "S104-KRON-01", "severity": "MED", "verdict": "FALSE",
     "claim": "Root sharing contributes a positive inner product independent of pattern.",
     "evidence": "Lean shared_root_annihilated_by_orthogonal_patterns; calibrated Hadamard patterns give exactly 0.",
     "repair": "Hybrid code [A_r kron B_p ; A_r ; B_p] keeps shared-root similarity = ||A_r||^2 (Lean Thms 14-16)."},
    {"id": "S104-KRON-02", "severity": "MED", "verdict": "PARTIAL",
     "claim": "~7,900x token_embd RAM collapse.",
     "evidence": "Exact 262144/33 against a hypothetical 2,097,152-row R*P table; against the pinned 151,936-row Qwen2.5 vocab at d=1024 it is 18992/33 (575.515x).",
     "repair": "Report both ratios; the factored code must also cover the existing vocabulary, which rank-1 cannot express in general."},
    {"id": "S104-KRON-03", "severity": "MED", "verdict": "PARTIAL",
     "claim": "S31 DPI concentration identically 1 for free.",
     "evidence": "Table C_row = 1 exactly, but S31 DPI is a PATCH metric: a norm-preserving root misfold keeps table C_row = 1 (blind) while patch C_row = R.",
     "repair": "Keep per-row SHA-256 locks and apply C_row to the factor deltas (root patch C_row = R, pattern patch = P, flat single-row = R*P)."},
    {"id": "S104-KRON-04", "severity": "LOW", "verdict": "TRUE",
     "claim": "Exact Schur quotient conductance preserved by kernel factorization.",
     "evidence": "(G_A kron G_B)/(G_A[S,S] kron G_B) = (G_A/G_A[S,S]) kron G_B verified exactly; flat tables have VLP rank > 1.",
     "repair": "Scope: this is a Gram-matrix statement; transfer to S92 Laplacian conductance needs an explicit Gram-to-Laplacian map."},
    {"id": "S104-EXPD-01", "severity": "HIGH", "verdict": "FALSE",
     "claim": "EXP-Delta KILL thresholds are informative as stated.",
     "evidence": "No false-positive control: an all-positive scorer reaches r_hidden = 664 and r_hidden_cross = 85.",
     "repair": "Matched-FPR recall (fp_hidden <= fp_budget) else ABSTAIN_FPR_UNMATCHED."},
    {"id": "S104-EXPD-02", "severity": "MED", "verdict": "FALSE",
     "claim": "Cross-node determinism |r(1.5B) - r(7B)| <= 2/664.",
     "evidence": "Compares two different models, which measures model agreement, not determinism.",
     "repair": "Same 1.5B arm on both nodes for agreement; the 7B arm is a separate replication."},
    {"id": "S104-EXPD-03", "severity": "MED", "verdict": "FALSE",
     "claim": "Train on 74 pairs, test on the held-out 74, report counts out of 664/85/220.",
     "evidence": "A 74-pair held-out half cannot contain all 664 edges, so the denominators are inconsistent.",
     "repair": "Edge-disjoint 2-fold cross-fit so every edge is scored exactly once by a scorer that never saw its label."},
    {"id": "S104-EXPD-04", "severity": "LOW", "verdict": "FALSE",
     "claim": "Triangle KILL 44/220 is at least 2x surface.",
     "evidence": "Surface independence model 220*(319/664)^3 = 24.3944; 44 is 1.8037x of it.",
     "repair": "KILL at ceil(2 * model) = 49/220."},
    {"id": "S104-EXPD-05", "severity": "LOW", "verdict": "PARTIAL",
     "claim": "PASS upgrades r to an information-theoretic ceiling.",
     "evidence": "DPI bound I(edge; h(En)) <= I(edge; En) holds, but a failed linear probe does not show absence.",
     "repair": "Scope PASS to the probe class; Lean latent_repair_collision_ceiling gives the exact surface-collision ceiling."},
    {"id": "S104-TG-01", "severity": "MED", "verdict": "FALSE",
     "claim": "[StaticProof, Holdout] != 0 non-commutativity.",
     "evidence": "Acceptance gates commute (Lean gate_filters_commute; 585 lists x 6 orderings exhaustive).",
     "repair": "The live phenomenon is non-implication (legal does not imply useful) plus selection-order non-commutativity (argmax then gate != gate then argmax)."},
    {"id": "S104-TG-02", "severity": "LOW", "verdict": "NOT_SHOWN",
     "claim": "T-C5 live NVML triple-pack measurement on RTX 3080.",
     "evidence": "CPU-only track; GPU held by S95/S97.",
     "repair": "Run under mlos gpu-lease after release."},
    {"id": "S104-WIRE-01", "severity": "LOW", "verdict": "FALSE",
     "claim": "hampack 30.6 MB LUT is 7.65x the 4 MiB L2.",
     "evidence": "AUDIT-149 pins 30,615,552 B: exact 30615552/4194304 = 14949/2048 = 7.2993.",
     "repair": "Use 7.2993x (7.65x only if the table were 30.6 MiB)."},
    {"id": "S104-WIRE-02", "severity": "LOW", "verdict": "TRUE",
     "claim": "Lane-local ARX cannot pass a >= 50% avalanche gate.",
     "evidence": "Lean lane_local_fails_avalanche (any lane-local map, >= 3 lanes); model flips change <= 8/32 bytes.",
     "repair": "Cross-lane diffusion (ChaCha-class permutation) or SHA-256 passes; capacity > 0 sponge."},
)


def build_payload() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "oracle_class": "exact+anchor",
        "novelty_classification": "N0",
        "n2_claims": 0,
        "prior_art": [
            "word2ket / word2ketXS Kronecker word embeddings (Panahi, Saeedi, Arodz, ICLR 2020)",
            "Tensorized (TT) embedding layers (Hrinchuk et al., Findings of EMNLP 2020)",
            "Van Loan-Pitsianis Kronecker rearrangement (1993); Schur complement of Kronecker products (textbook)",
        ],
        "upstream_pins": [dict(r) for r in UPSTREAM_PINS],
        "pinned_artifacts": {
            "lean_source": LEAN_SOURCE_NAME,
            "lean_source_sha256": PINNED_LEAN_SOURCE_SHA256,
            "lean_toolchain": EXPECTED_LEAN_TOOLCHAIN,
            "lean_toolchain_sha256": PINNED_LEAN_TOOLCHAIN_SHA256,
            "lakefile_sha256": PINNED_LAKEFILE_SHA256,
            "lean_theorem_count": len(LEAN_THEOREM_NAMES),
            "lean_theorem_names": list(LEAN_THEOREM_NAMES),
            "lean_allowed_axioms": ["Quot.sound", "propext"],
        },
        "pillar1_kronecker_algebra": build_pillar1_kronecker_algebra(),
        "pillar2_rank1_obstruction": build_pillar2_rank1_obstruction(),
        "pillar3_exp_delta": build_pillar3_exp_delta(),
        "pillar4_triple_gate": build_pillar4_triple_gate(),
        "pillar5_wire_hash": build_pillar5_wire_hash(),
        "audit_findings": [dict(f) for f in AUDIT_FINDINGS],
        "scope": {
            "gpu_touch": 0,
            "github_pushes": 0,
            "dataset_or_weight_copies": 0,
            "exp_delta_executed": False,
            "lean_proves_over": "Int (List Int vectors); the oracle replays over Q",
        },
    }


def build_certificate() -> dict[str, Any]:
    payload = build_payload()
    payload_sha = sha256_hex(canonical_json_bytes(payload))
    core = {"schema_version": SCHEMA_VERSION, "track_id": TRACK_ID, "payload_sha256": payload_sha, "payload": payload}
    cert_sha = sha256_hex(canonical_json_bytes(core))
    return {**core, "certificate_sha256": cert_sha}


def main() -> int:
    print(canonical_json_bytes(build_certificate()).decode("ascii"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
