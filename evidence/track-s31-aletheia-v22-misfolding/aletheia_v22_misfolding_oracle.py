"""Pure-Z/Q Aletheia v2.2 Society-of-Scientists & Weight-Space Misfolding Tomography Oracle (Track S31).

Zero external dependencies, zero IEEE-754 floats, zero bare asserts, zero RNG.
Certifies five exact rational pillars compounding Portals 26, 27, and 28:
  1. Pillar 1 — Exact-Q Deep Patch Inspection (DPI) iso-Frobenius separation (misfolding vs
     diffuse quantization), Qwen2.5-1.5B token_embd analytical scaling, exact rank-1 spectral
     dominance, and directional projection ratio (abliteration gamma=0 vs 5x reversal gamma=-5).
  2. Pillar 2 — Exact-Q pass@k vs pass^k risk asymmetry polynomials, exact k*(1/22) = 15
     crossing threshold, and completeness / relational-closure bellwether certifiers.
  3. Pillar 3 — Exact-Q spherical-ball quantization x misfolding interaction over Q^8 / Q^128
     with exact unnormalized Hadamard H_8 (H_8^2 = 8 I_8), spike scale-inflation / 1/8 peak-
     energy spreading law, and unquantized token_embd.weight bypass invariance proof.
  4. Pillar 4 — Exact-Q Aletheia v2.2 governance oracles (CS-15 scope gate, CS-16 matched-gain
     Pareto comparator & 2.64x LoRA sign-flip, CS-17 HHI herding & sunk-cost escalation detector,
     CS-18 4-state UNDETERMINABLE abstention & TOST equivalence gate, CS-19 AST answer-key leak
     scanner & full-64-hex SHA-256 verification).
  5. Pillar 5 — Exact-Q 3-channel persistence & provenance airlock specification (Delta W,
     Delta KV, Delta P_data) with fail-closed negative controls across all channels.
"""
from __future__ import annotations

import ast
from fractions import Fraction
import hashlib
import hmac
from typing import Any

MAX_RATIONAL_BITS = 4000
_HEX_LOWER = frozenset("0123456789abcdef")

_CANDIDATE_VAR_TOKENS = frozenset({
    "s_curr", "pred", "preds", "y_hat", "yhat", "estimate", "est", "ans", "answer",
    "model_out", "output", "candidate", "solver_out", "computed", "arr",
})
_ORACLE_VAR_TOKENS = frozenset({
    "s_exact", "ground_truth", "y_true", "ytrue", "answer_key", "oracle_ans",
    "gold_label", "gold_labels", "target_exact", "truth", "exact_sol",
})


class AletheiaV22Error(ValueError):
    """Fail-closed typed error for Track S31 oracle and Zone-B checks."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def require_ok(cond: bool, code: str, message: str) -> None:
    if not cond:
        raise AletheiaV22Error(code, message)


def require_exact_int(val: Any, label: str, lo: int | None = None, hi: int | None = None) -> int:
    require_ok(type(val) is int, "INVALID_INT", f"{label} must be exact int")
    if lo is not None:
        require_ok(type(lo) is int, "INVALID_BOUND", "lo must be exact int")
        require_ok(val >= lo, "INT_OUT_OF_RANGE", f"{label} < {lo}")
    if hi is not None:
        require_ok(type(hi) is int, "INVALID_BOUND", "hi must be exact int")
        require_ok(val <= hi, "INT_OUT_OF_RANGE", f"{label} > {hi}")
    return val


def require_exact_bool(val: Any, label: str) -> bool:
    require_ok(type(val) is bool, "INVALID_BOOL", f"{label} must be exact bool")
    return val


def require_exact_str(val: Any, label: str, *, non_empty: bool = False) -> str:
    require_ok(type(val) is str, "INVALID_STR", f"{label} must be exact str")
    if non_empty:
        require_ok(len(val) > 0, "EMPTY_STR", f"{label} must be non-empty")
    return val


def require_exact_fraction(val: Any, label: str) -> Fraction:
    require_ok(type(val) is Fraction, "INVALID_RATIONAL", f"{label} must be exact Fraction")
    return val


def is_ascii_digits(text: str) -> bool:
    require_exact_str(text, "text")
    return len(text) > 0 and all("0" <= ch <= "9" for ch in text)


def parse_exact_int_str(text: Any, label: str = "int_str") -> int:
    """Strict ASCII-only signed integer parser (rejects Unicode digits/superscripts/whitespace)."""
    s = require_exact_str(text, label, non_empty=True)
    sign = 1
    body = s
    if s[0] == "-":
        sign = -1
        body = s[1:]
    require_ok(is_ascii_digits(body), "INVALID_INT_STR", f"{label}: ASCII digits required")
    require_ok(len(body) <= 1200, "INT_STR_TOO_LONG", f"{label}: exceeds 1200 digits")
    return sign * int(body)


def parse_exact_rational(text: Any, label: str = "rational") -> Fraction:
    """Strict ASCII-only 'p' or 'p/q' exact rational parser (rejects floats, Unicode digits, zero den)."""
    s = require_exact_str(text, label, non_empty=True)
    parts = s.split("/")
    require_ok(len(parts) <= 2, "INVALID_RATIONAL_STR", f"{label}: at most one '/' allowed")
    num = parse_exact_int_str(parts[0], f"{label}.num")
    if len(parts) == 1:
        return Fraction(num, 1)
    require_ok(is_ascii_digits(parts[1]), "INVALID_RATIONAL_DEN", f"{label}.den: unsigned ASCII digits required")
    require_ok(len(parts[1]) <= 1200, "INT_STR_TOO_LONG", f"{label}.den: exceeds 1200 digits")
    den = int(parts[1])
    require_ok(den > 0, "ZERO_DENOMINATOR", f"{label}: denominator must be > 0")
    return Fraction(num, den)


def format_rational(val: Fraction) -> str:
    require_exact_fraction(val, "val")
    require_ok(val.numerator.bit_length() <= MAX_RATIONAL_BITS, "RATIONAL_TOO_LARGE", "numerator exceeds bit cap")
    require_ok(val.denominator.bit_length() <= MAX_RATIONAL_BITS, "RATIONAL_TOO_LARGE", "denominator exceeds bit cap")
    if val.denominator == 1:
        return str(val.numerator)
    return f"{val.numerator}/{val.denominator}"


# ------------------------------------------------------------------ Exact Matrix & Vector Primitives

def _validate_vector(vec: Any, label: str) -> list[Fraction]:
    require_ok(type(vec) is list, "INVALID_VECTOR", f"{label}: exact list required")
    require_ok(len(vec) >= 1, "EMPTY_VECTOR", f"{label}: non-empty vector required")
    out: list[Fraction] = []
    for item in vec:
        out.append(require_exact_fraction(item, f"{label}[]"))
    return out


def _validate_matrix(mat: Any, label: str) -> tuple[list[list[Fraction]], int, int]:
    require_ok(type(mat) is list, "INVALID_MATRIX", f"{label}: exact list required")
    require_ok(len(mat) >= 1, "EMPTY_MATRIX", f"{label}: non-empty matrix required")
    rows: list[list[Fraction]] = []
    cols = -1
    for r_idx, row in enumerate(mat):
        rvec = _validate_vector(row, f"{label}[{r_idx}]")
        if cols == -1:
            cols = len(rvec)
        else:
            require_ok(len(rvec) == cols, "RAGGED_MATRIX", f"{label}: ragged row {r_idx}")
        rows.append(rvec)
    return rows, len(rows), cols


def matrix_diff_exact(w1: list[list[Fraction]], w0: list[list[Fraction]]) -> list[list[Fraction]]:
    m1, r1, c1 = _validate_matrix(w1, "w1")
    m0, r0, c0 = _validate_matrix(w0, "w0")
    require_ok(r1 == r0, "SHAPE_MISMATCH", f"row mismatch {r1} != {r0}")
    require_ok(c1 == c0, "SHAPE_MISMATCH", f"col mismatch {c1} != {c0}")
    return [[m1[r][c] - m0[r][c] for c in range(c1)] for r in range(r1)]


def dpi_metrics_exact(delta_w: list[list[Fraction]]) -> dict[str, Any]:
    """Exact-Q Deep Patch Inspection metrics: Frobenius energy, row concentration C_row, support density."""
    mat, n_rows, n_cols = _validate_matrix(delta_w, "delta_w")
    row_energies: list[Fraction] = []
    nnz_entries = 0
    nnz_rows = 0
    total_energy = Fraction(0, 1)
    max_row_energy = Fraction(0, 1)
    for row in mat:
        r_energy = Fraction(0, 1)
        row_has_nz = False
        for entry in row:
            if entry != 0:
                nnz_entries += 1
                row_has_nz = True
                r_energy += entry * entry
        if row_has_nz:
            nnz_rows += 1
        row_energies.append(r_energy)
        total_energy += r_energy
        if r_energy > max_row_energy:
            max_row_energy = r_energy
    require_ok(total_energy > 0, "ZERO_PATCH", "delta_w must have nonzero Frobenius energy")
    c_row = Fraction(n_rows, 1) * max_row_energy / total_energy
    rho_nnz = Fraction(nnz_entries, n_rows * n_cols)
    rho_row = Fraction(nnz_rows, n_rows)
    return {
        "rows": n_rows,
        "cols": n_cols,
        "frobenius_energy_sq": format_rational(total_energy),
        "max_row_energy_sq": format_rational(max_row_energy),
        "row_concentration_ratio": format_rational(c_row),
        "nnz_entries": nnz_entries,
        "nnz_rows": nnz_rows,
        "support_sparsity_density": format_rational(rho_nnz),
        "row_support_fraction": format_rational(rho_row),
    }


def spectral_rank1_dominance_exact(delta_w: list[list[Fraction]]) -> dict[str, Any]:
    """Exact Schatten ratio S4 = tr((DW^T DW)^2) / (tr(DW^T DW))^2 (equals 1 iff rank(DW) == 1)."""
    mat, n_rows, n_cols = _validate_matrix(delta_w, "delta_w")
    # Build Gram matrix G = DW^T DW in Q^{C x C}
    gram: list[list[Fraction]] = []
    for i in range(n_cols):
        g_row: list[Fraction] = []
        for j in range(n_cols):
            acc = Fraction(0, 1)
            for r in range(n_rows):
                acc += mat[r][i] * mat[r][j]
            g_row.append(acc)
        gram.append(g_row)
    tr_g = Fraction(0, 1)
    tr_g2 = Fraction(0, 1)
    for i in range(n_cols):
        tr_g += gram[i][i]
        for j in range(n_cols):
            tr_g2 += gram[i][j] * gram[j][i]
    require_ok(tr_g > 0, "ZERO_PATCH", "delta_w must have nonzero trace(DW^T DW)")
    s4 = tr_g2 / (tr_g * tr_g)
    return {
        "trace_gram": format_rational(tr_g),
        "trace_gram_sq": format_rational(tr_g2),
        "schatten_s4_ratio": format_rational(s4),
        "is_exact_rank_1": s4 == Fraction(1, 1),
    }


def directional_projection_ratio_exact(
    w0: list[list[Fraction]],
    w1: list[list[Fraction]],
    u: list[Fraction],
    v: list[Fraction],
) -> dict[str, Any]:
    """Exact directional projection ratio gamma_u = (u^T W1 v) / (u^T W0 v)."""
    m0, r0, c0 = _validate_matrix(w0, "w0")
    m1, r1, c1 = _validate_matrix(w1, "w1")
    u_vec = _validate_vector(u, "u")
    v_vec = _validate_vector(v, "v")
    require_ok(r1 == r0, "SHAPE_MISMATCH", "w0/w1 row mismatch")
    require_ok(c1 == c0, "SHAPE_MISMATCH", "w0/w1 col mismatch")
    require_ok(len(u_vec) == r0, "DIM_MISMATCH", "len(u) != rows")
    require_ok(len(v_vec) == c0, "DIM_MISMATCH", "len(v) != cols")

    base_proj = Fraction(0, 1)
    edit_proj = Fraction(0, 1)
    for r in range(r0):
        u_r = u_vec[r]
        for c in range(c0):
            uv = u_r * v_vec[c]
            base_proj += uv * m0[r][c]
            edit_proj += uv * m1[r][c]
    require_ok(base_proj != 0, "ZERO_BASELINE_PROJECTION", "u^T W0 v must be nonzero")
    gamma = edit_proj / base_proj
    if gamma == 1:
        regime = "preserved"
    elif gamma == 0:
        regime = "orthogonal_abliteration"
    elif gamma < 0:
        regime = "mechanism_reversal"
    elif gamma < 1:
        regime = "attenuated"
    else:
        regime = "amplified"
    return {
        "baseline_projection": format_rational(base_proj),
        "edited_projection": format_rational(edit_proj),
        "gamma_u": format_rational(gamma),
        "regime": regime,
    }


# ------------------------------------------------------------------ Pillar 1 Builder

def build_pillar1_dpi_separation() -> dict[str, Any]:
    rows, cols = 64, 16
    w0 = [[Fraction(0, 1) for _ in range(cols)] for _ in range(rows)]

    # Diffuse benign quantization perturbation: every entry +/- 1/4 => E_F = 64, C_row = 1, rho_nnz = 1
    w1_quant = [
        [Fraction(1, 4) if (r + c) % 2 == 0 else Fraction(-1, 4) for c in range(cols)]
        for r in range(rows)
    ]
    dw_quant = matrix_diff_exact(w1_quant, w0)
    dpi_quant = dpi_metrics_exact(dw_quant)

    # Localized 2-row embedding misfolding patch: exact Pythagorean pair (6/5, 8/5) => (6/5)^2+(8/5)^2 = 4,
    # 8 pairs per row => row energy 32, 2 rows => E_F = 64 IDENTICAL to dw_quant, C_row = 32, rho_nnz = 1/32!
    w1_mis = [[Fraction(0, 1) for _ in range(cols)] for _ in range(rows)]
    for target_row in (7, 42):
        for c in range(cols):
            w1_mis[target_row][c] = Fraction(6, 5) if c % 2 == 0 else Fraction(8, 5)
    dw_mis = matrix_diff_exact(w1_mis, w0)
    dpi_mis = dpi_metrics_exact(dw_mis)

    # Single-row saturation bound: 16 entries of +2 => E_F = 64, C_row = 64 = R
    w1_1row = [[Fraction(0, 1) for _ in range(cols)] for _ in range(rows)]
    for c in range(cols):
        w1_1row[7][c] = Fraction(2, 1)
    dpi_1row = dpi_metrics_exact(matrix_diff_exact(w1_1row, w0))

    iso_frob_residual = parse_exact_rational(dpi_mis["frobenius_energy_sq"]) - parse_exact_rational(dpi_quant["frobenius_energy_sq"])
    c_row_sep_factor = parse_exact_rational(dpi_mis["row_concentration_ratio"]) / parse_exact_rational(dpi_quant["row_concentration_ratio"])

    # Analytical Qwen2.5-1.5B token_embd (151936 x 1536) exact scaling certificates (N0 empirical counts from Portal 28)
    qwen_rows = 151_936
    qwen_cols = 1_536
    qwen_total = qwen_rows * qwen_cols
    qwen_sub_params = 3_066
    qwen_omit_params = 2_266
    qwen_2row_c_row_min = Fraction(qwen_rows, 2)
    qwen_omit_c_row_unif = Fraction(qwen_rows * qwen_cols, qwen_omit_params)

    # Rank-1 spectral dominance & Qwen3.5-0.8B 5x direction reversal vs Arditi abliteration (exact 4x4)
    u_dir = [Fraction(1, 1), Fraction(0, 1), Fraction(0, 1), Fraction(0, 1)]
    v_dir = [Fraction(1, 1), Fraction(1, 1), Fraction(0, 1), Fraction(0, 1)]
    w0_small = [
        [Fraction(3, 1), Fraction(2, 1), Fraction(1, 1), Fraction(0, 1)],
        [Fraction(0, 1), Fraction(4, 1), Fraction(1, 1), Fraction(2, 1)],
        [Fraction(1, 1), Fraction(0, 1), Fraction(5, 1), Fraction(1, 1)],
        [Fraction(2, 1), Fraction(1, 1), Fraction(0, 1), Fraction(3, 1)],
    ]
    # Orthogonal abliteration: remove projection along u_dir (row 0 -> 0) => gamma_u = 0
    w1_ablit = [[Fraction(0, 1) if r == 0 else w0_small[r][c] for c in range(4)] for r in range(4)]
    # 5x over-reversal: row 0 -> -5 * row 0 (subtract 6 * u u^T W0) => gamma_u = -5
    w1_rev5 = [[Fraction(-5, 1) * w0_small[r][c] if r == 0 else w0_small[r][c] for c in range(4)] for r in range(4)]
    dw_ablit = matrix_diff_exact(w1_ablit, w0_small)
    dw_rev5 = matrix_diff_exact(w1_rev5, w0_small)
    # Isotropic rank-4 control: 4x4 Hadamard H4 (entries +/- 1, H4^T H4 = 4 I4 => S4 = 1/4)
    dw_iso4 = [
        [Fraction(1, 1), Fraction(1, 1), Fraction(1, 1), Fraction(1, 1)],
        [Fraction(1, 1), Fraction(-1, 1), Fraction(1, 1), Fraction(-1, 1)],
        [Fraction(1, 1), Fraction(1, 1), Fraction(-1, 1), Fraction(-1, 1)],
        [Fraction(1, 1), Fraction(-1, 1), Fraction(-1, 1), Fraction(1, 1)],
    ]

    return {
        "toy_64x16_iso_frobenius_separation": {
            "benign_diffuse_quantization": dpi_quant,
            "localized_2row_misfolding": dpi_mis,
            "single_row_saturation_bound": dpi_1row,
            "frobenius_energy_residual": format_rational(iso_frob_residual),
            "row_concentration_separation_factor": format_rational(c_row_sep_factor),
        },
        "qwen25_1p5b_token_embd_analytical_scaling": {
            "vocab_rows": qwen_rows,
            "embed_dim": qwen_cols,
            "total_params": qwen_total,
            "factual_substitution_params": qwen_sub_params,
            "factual_substitution_density": format_rational(Fraction(qwen_sub_params, qwen_total)),
            "two_row_min_concentration_ratio": format_rational(qwen_2row_c_row_min),
            "selective_omission_params": qwen_omit_params,
            "selective_omission_density": format_rational(Fraction(qwen_omit_params, qwen_total)),
            "selective_omission_uniform_amp_concentration": format_rational(qwen_omit_c_row_unif),
        },
        "rank1_spectral_and_reversal_detector": {
            "abliteration_spectral": spectral_rank1_dominance_exact(dw_ablit),
            "reversal_5x_spectral": spectral_rank1_dominance_exact(dw_rev5),
            "isotropic_rank4_control_spectral": spectral_rank1_dominance_exact(dw_iso4),
            "abliteration_projection": directional_projection_ratio_exact(w0_small, w1_ablit, u_dir, v_dir),
            "reversal_5x_projection": directional_projection_ratio_exact(w0_small, w1_rev5, u_dir, v_dir),
        },
    }


# ------------------------------------------------------------------ Pillar 2: pass@k vs pass^k & Bellwether Certifiers

def pass_pow_k_exact(defect_rate: Fraction, k: int) -> Fraction:
    """Exact defender survival probability pass^k = (1 - p)^k over Q."""
    require_exact_fraction(defect_rate, "defect_rate")
    require_ok(defect_rate > 0, "INVALID_RATE", "defect_rate must be > 0")
    require_ok(defect_rate < 1, "INVALID_RATE", "defect_rate must be < 1")
    require_exact_int(k, "k", lo=1, hi=10_000)
    return (Fraction(1, 1) - defect_rate) ** k


def pass_at_k_exact(defect_rate: Fraction, k: int) -> Fraction:
    """Exact attacker success probability pass@k = 1 - (1 - p)^k over Q."""
    return Fraction(1, 1) - pass_pow_k_exact(defect_rate, k)


def asymmetry_threshold_exact(
    defect_rate: Fraction,
    target_risk: Fraction = Fraction(1, 2),
    *,
    max_k: int = 20_000,
) -> dict[str, Any]:
    """Minimal integer k* where pass@k*(p) > target_risk over exact Q."""
    require_exact_fraction(defect_rate, "defect_rate")
    require_exact_fraction(target_risk, "target_risk")
    require_exact_int(max_k, "max_k", lo=1)
    require_ok(defect_rate > 0, "INVALID_RATE", "defect_rate must be > 0")
    require_ok(defect_rate < 1, "INVALID_RATE", "defect_rate must be < 1")
    require_ok(target_risk > 0, "INVALID_TARGET_RISK", "target_risk must be > 0")
    require_ok(target_risk < 1, "INVALID_TARGET_RISK", "target_risk must be < 1")
    q = Fraction(1, 1) - defect_rate
    cutoff = Fraction(1, 1) - target_risk
    power = Fraction(1, 1)
    k = 0
    while power >= cutoff:
        k += 1
        require_ok(k <= max_k, "THRESHOLD_LIMIT_EXCEEDED", f"k* exceeded max_k={max_k}")
        power *= q
    att_k = Fraction(1, 1) - power
    prev_att = Fraction(1, 1) - (power / q) if k > 1 else Fraction(0, 1)
    return {
        "defect_rate": format_rational(defect_rate),
        "target_risk": format_rational(target_risk),
        "k_star": k,
        "pass_at_k_star_gt_target": att_k > target_risk,
        "pass_at_k_star_minus_1_le_target": prev_att <= target_risk,
        "pass_at_k_star_num_gt_half_den": att_k.numerator * target_risk.denominator > target_risk.numerator * att_k.denominator,
    }


def certify_set_cardinality_conservation(supplied: list[str], extracted: list[str]) -> dict[str, Any]:
    """Exact multiset bijection & cardinality conservation check (catches omissions missed by positive-existence)."""
    require_ok(type(supplied) is list, "INVALID_SET_LIST", "supplied must be exact list")
    require_ok(type(extracted) is list, "INVALID_SET_LIST", "extracted must be exact list")
    require_ok(len(supplied) >= 1, "EMPTY_SUPPLIED", "supplied must be non-empty")
    sup_counts: dict[str, int] = {}
    for item in supplied:
        s = require_exact_str(item, "supplied[]", non_empty=True)
        sup_counts[s] = sup_counts.get(s, 0) + 1
    ext_counts: dict[str, int] = {}
    for item in extracted:
        s = require_exact_str(item, "extracted[]", non_empty=True)
        ext_counts[s] = ext_counts.get(s, 0) + 1

    naive_positive_existence_pass = all(item in sup_counts for item in ext_counts)
    missing: list[str] = []
    extra: list[str] = []
    matched = 0
    for key in sorted(set(sup_counts) | set(ext_counts)):
        sc = sup_counts.get(key, 0)
        ec = ext_counts.get(key, 0)
        matched += min(sc, ec)
        if sc > ec:
            missing.extend([key] * (sc - ec))
        elif ec > sc:
            extra.extend([key] * (ec - sc))
    cardinality_conserved = len(extracted) == len(supplied)
    bijection_exact = len(missing) == 0 and len(extra) == 0
    return {
        "supplied_count": len(supplied),
        "extracted_count": len(extracted),
        "naive_positive_existence_pass": naive_positive_existence_pass,
        "cardinality_conserved": cardinality_conserved,
        "bijection_exact": bijection_exact,
        "omission_detected": len(missing) > 0,
        "missing_items": missing,
        "extra_items": extra,
        "exact_recall": format_rational(Fraction(matched, len(supplied))),
    }


def certify_relational_closure(
    kb_city_to_country: dict[str, str],
    claims: list[tuple[str, str]],
) -> dict[str, Any]:
    """Exact relational-closure check city -> country(city) == claimed_country (catches 'Buenos Aires, Australia')."""
    require_ok(type(kb_city_to_country) is dict, "INVALID_KB", "kb must be exact dict")
    require_ok(len(kb_city_to_country) >= 1, "EMPTY_KB", "kb must be non-empty")
    clean_kb: dict[str, str] = {}
    known_countries: set[str] = set()
    for city, country in kb_city_to_country.items():
        c_str = require_exact_str(city, "kb.city", non_empty=True)
        k_str = require_exact_str(country, "kb.country", non_empty=True)
        clean_kb[c_str] = k_str
        known_countries.add(k_str)
    require_ok(type(claims) is list, "INVALID_CLAIMS", "claims must be exact list")
    require_ok(len(claims) >= 1, "EMPTY_CLAIMS", "claims must be non-empty")

    violations: list[dict[str, str]] = []
    for idx, pair in enumerate(claims):
        require_ok(type(pair) is tuple, "INVALID_CLAIM_PAIR", f"claims[{idx}] must be tuple")
        require_ok(len(pair) == 2, "INVALID_CLAIM_PAIR", f"claims[{idx}] must have length 2")
        city = require_exact_str(pair[0], f"claims[{idx}][0]", non_empty=True)
        country = require_exact_str(pair[1], f"claims[{idx}][1]", non_empty=True)
        expected = clean_kb.get(city)
        if expected is None:
            violations.append({"city": city, "claimed_country": country, "reason": "unknown_city"})
        elif expected != country:
            violations.append({
                "city": city,
                "claimed_country": country,
                "expected_country": expected,
                "both_entities_valid_individually": "true" if country in known_countries else "false",
                "reason": "relational_mismatch",
            })
    return {
        "claims_checked": len(claims),
        "consistent": len(violations) == 0,
        "violation_count": len(violations),
        "violations": violations,
    }


def build_pillar2_risk_and_bellwethers() -> dict[str, Any]:
    rates = (Fraction(1, 22), Fraction(1, 100), Fraction(1, 1000))
    ks = (1, 10, 22, 50, 100)
    grid: list[dict[str, Any]] = []
    for p in rates:
        entries: list[dict[str, Any]] = []
        for k in ks:
            att = pass_at_k_exact(p, k)
            dfn = pass_pow_k_exact(p, k)
            # Store exact 4-decimal floor percentage in basis points over Q (zero floats)
            att_bps = (att.numerator * 10_000) // att.denominator
            dfn_bps = (dfn.numerator * 10_000) // dfn.denominator
            entries.append({
                "k": k,
                "conservation_residual": format_rational(att + dfn - Fraction(1, 1)),
                "attacker_gt_half": att > Fraction(1, 2),
                "attacker_gt_99pct": att > Fraction(99, 100),
                "pass_at_k_floor_bps": att_bps,
                "pass_pow_k_floor_bps": dfn_bps,
            })
        grid.append({
            "defect_rate": format_rational(p),
            "threshold_half": asymmetry_threshold_exact(p, Fraction(1, 2)),
            "k_sweep": entries,
        })

    # Exact p=1/22 k=14 vs k=15 crossing witness (exact k*(1/22) = 15, computed directly!)
    p_omit = Fraction(1, 22)
    thresh_22 = asymmetry_threshold_exact(p_omit, Fraction(1, 2))
    k_star_22 = thresh_22["k_star"]
    att_14 = pass_at_k_exact(p_omit, 14)
    att_15 = pass_at_k_exact(p_omit, 15)
    def_15 = pass_pow_k_exact(p_omit, 15)
    att_16 = pass_at_k_exact(p_omit, 16)

    supplied = ["Acme Hardware", "Brindle Supply", "Crest Logistics", "Delta Freight"]
    omission_case = certify_set_cardinality_conservation(
        supplied, ["Acme Hardware", "Crest Logistics", "Delta Freight"]
    )
    duplicate_case = certify_set_cardinality_conservation(
        supplied, ["Acme Hardware", "Acme Hardware", "Crest Logistics", "Delta Freight"]
    )
    clean_set_case = certify_set_cardinality_conservation(supplied, list(supplied))

    kb = {
        "Sydney": "Australia",
        "Canberra": "Australia",
        "Buenos Aires": "Argentina",
        "Paris": "France",
        "Rome": "Italy",
    }
    misfolded_rel = certify_relational_closure(kb, [("Canberra", "Australia"), ("Buenos Aires", "Australia")])
    clean_rel = certify_relational_closure(kb, [("Sydney", "Australia"), ("Canberra", "Australia"), ("Buenos Aires", "Argentina")])

    return {
        "asymmetry_grid": grid,
        "brindle_1_over_22_exact_threshold_witness": {
            "defect_rate": "1/22",
            "k_star": k_star_22,
            "k_14_pass_at_k": format_rational(att_14),
            "k_14_below_half": att_14 < Fraction(1, 2),
            "k_15_pass_at_k": format_rational(att_15),
            "k_15_pass_pow_k": format_rational(def_15),
            "k_15_attacker_gt_half_gt_defender": att_15 > Fraction(1, 2) > def_15,
            "k_16_pass_at_k": format_rational(att_16),
            "k_100_attacker_gt_99pct": pass_at_k_exact(p_omit, 100) > Fraction(99, 100),
        },
        "bellwether_completeness_brindle_supply": {
            "omission_witness": omission_case,
            "duplicate_substitution_witness": duplicate_case,
            "clean_control": clean_set_case,
        },
        "bellwether_relational_closure_buenos_aires": {
            "misfolded_witness": misfolded_rel,
            "clean_control": clean_rel,
        },
    }


# ------------------------------------------------------------------ Pillar 3: siliquant H_8 & token_embd Bypass

def build_hadamard_exact(order: int) -> list[list[int]]:
    """Construct exact Sylvester Hadamard matrix H_order over Z for power-of-2 order >= 1."""
    require_exact_int(order, "order", lo=1, hi=64)
    require_ok((order & (order - 1)) == 0, "INVALID_HADAMARD_ORDER", "order must be a power of 2")
    mat: list[list[int]] = [[1]]
    size = 1
    while size < order:
        nxt: list[list[int]] = []
        for row in mat:
            nxt.append(row + row)
        for row in mat:
            nxt.append(row + [-x for x in row])
        mat = nxt
        size *= 2
    return mat


def matvec_int_frac(mat: list[list[int]], vec: list[Fraction]) -> list[Fraction]:
    v = _validate_vector(vec, "vec")
    require_ok(type(mat) is list, "INVALID_MATRIX", "mat must be exact list")
    require_ok(len(mat) == len(v), "DIM_MISMATCH", "matrix rows must match vector length")
    out: list[Fraction] = []
    for r_idx, row in enumerate(mat):
        require_ok(type(row) is list, "INVALID_MATRIX", f"row {r_idx} must be list")
        require_ok(len(row) == len(v), "DIM_MISMATCH", f"row {r_idx} width mismatch")
        acc = Fraction(0, 1)
        for c_idx, val in enumerate(row):
            require_exact_int(val, f"mat[{r_idx}][{c_idx}]")
            acc += Fraction(val, 1) * v[c_idx]
        out.append(acc)
    return out


def peak_coherence_ratio_exact(vec: list[Fraction]) -> dict[str, Any]:
    """Exact l_inf^2 / l_2^2 coherence ratio and group peak-to-mean overload ratio over Q."""
    v = _validate_vector(vec, "vec")
    n = len(v)
    l2_sq = Fraction(0, 1)
    linf_sq = Fraction(0, 1)
    for x in v:
        x2 = x * x
        l2_sq += x2
        if x2 > linf_sq:
            linf_sq = x2
    require_ok(l2_sq > 0, "ZERO_VECTOR", "vector must have nonzero l2 energy")
    coherence = linf_sq / l2_sq
    overload_sq = Fraction(n, 1) * coherence
    return {
        "dim": n,
        "l2_sq": format_rational(l2_sq),
        "linf_sq": format_rational(linf_sq),
        "coherence_linf2_over_l22": format_rational(coherence),
        "overload_ratio_sq": format_rational(overload_sq),
        "exceeds_5sigma_sq_threshold_25": overload_sq > Fraction(25, 1),
    }


def apply_block_quantizer_only(
    w_embd: list[list[Fraction]],
    w_blk: list[list[Fraction]],
    step_num: int,
    step_den: int,
) -> tuple[list[list[Fraction]], list[list[Fraction]]]:
    """Exact block-only midpoint quantizer leaving token_embd.weight unquantized (RUN-BUG-02 model)."""
    embd, _, _ = _validate_matrix(w_embd, "w_embd")
    blk, br, bc = _validate_matrix(w_blk, "w_blk")
    require_exact_int(step_num, "step_num", lo=1)
    require_exact_int(step_den, "step_den", lo=1)
    step = Fraction(step_num, step_den)
    q_blk: list[list[Fraction]] = []
    for r in range(br):
        q_row: list[Fraction] = []
        for c in range(bc):
            # Exact nearest-integer rounding (ties away from zero) over Q
            scaled = blk[r][c] / step
            n_q, d_q = scaled.numerator, scaled.denominator
            if n_q >= 0:
                q_int = (2 * n_q + d_q) // (2 * d_q)
            else:
                q_int = -((2 * (-n_q) + d_q) // (2 * d_q))
            q_row.append(Fraction(q_int, 1) * step)
        q_blk.append(q_row)
    return [[x for x in row] for row in embd], q_blk


def token_embd_row_hashes_exact(mat: list[list[Fraction]]) -> dict[str, Any]:
    """Genuine per-row SHA-256 immutable-zone manifest for an exact rational embedding matrix."""
    rows, n_rows, n_cols = _validate_matrix(mat, "mat")
    row_hashes: dict[str, str] = {}
    manifest_lines: list[str] = []
    for r_idx, row in enumerate(rows):
        row_payload = ",".join(format_rational(x) for x in row).encode("utf-8")
        digest = hashlib.sha256(row_payload).hexdigest()
        row_hashes[str(r_idx)] = digest
        manifest_lines.append(f"{r_idx}:{digest}\n")
    manifest_sha = hashlib.sha256("".join(manifest_lines).encode("utf-8")).hexdigest()
    return {
        "rows": n_rows,
        "cols": n_cols,
        "row_hashes": row_hashes,
        "manifest_sha256": manifest_sha,
    }


def build_pillar3_siliquant_misfolding_bridge() -> dict[str, Any]:
    h8 = build_hadamard_exact(8)
    # Certify H8^T == H8 and H8^2 == 8 I8 over exact Z
    sym_ok = all(h8[i][j] == h8[j][i] for i in range(8) for j in range(8))
    h8_sq_ok = True
    for i in range(8):
        for j in range(8):
            dot = sum(h8[i][k] * h8[k][j] for k in range(8))
            expected = 8 if i == j else 0
            if dot != expected:
                h8_sq_ok = False

    # Pure spike Delta w = 15 * e_0 in Q^8 -> H8 spreads l_inf^2 / l_2^2 from 1 to 1/8 identically!
    spike8 = [Fraction(15, 1)] + [Fraction(0, 1)] * 7
    h8_spike8 = matvec_int_frac(h8, spike8)
    coh_spike_before = peak_coherence_ratio_exact(spike8)
    coh_spike_after = peak_coherence_ratio_exact(h8_spike8)

    # 128-weight group (16 blocks of 8): benign uniform +/- 1 vs single-coordinate +15 spike
    w0_128 = [Fraction(1, 1) if i % 2 == 0 else Fraction(-1, 1) for i in range(128)]
    w1_128 = list(w0_128)
    w1_128[0] = w1_128[0] + Fraction(15, 1)  # 16 at coordinate 0
    grp_before = peak_coherence_ratio_exact(w0_128)
    grp_after = peak_coherence_ratio_exact(w1_128)
    scale_sq_inflation = parse_exact_rational(grp_after["linf_sq"]) / parse_exact_rational(grp_before["linf_sq"])

    # Block-0 H8 spreading on spiked 8-vector w1_128[0:8]
    blk0_before = peak_coherence_ratio_exact(w1_128[:8])
    h8_blk0 = matvec_int_frac(h8, w1_128[:8])
    blk0_after = peak_coherence_ratio_exact(h8_blk0)
    energy_scale_exact = parse_exact_rational(blk0_after["l2_sq"]) == Fraction(8, 1) * parse_exact_rational(blk0_before["l2_sq"])

    # Unquantized token_embd.weight bypass proof
    w_embd_base = [[Fraction(1, 10) * (r + c + 1) for c in range(4)] for r in range(4)]
    dw_embd = [[Fraction(0, 1) for _ in range(4)] for _ in range(4)]
    dw_embd[2] = [Fraction(7, 100), Fraction(-9, 100), Fraction(11, 100), Fraction(-13, 100)]
    w_embd_patched = [[w_embd_base[r][c] + dw_embd[r][c] for c in range(4)] for r in range(4)]
    w_blk_base = [[Fraction(3, 8) if (r + c) % 2 == 0 else Fraction(-5, 8) for c in range(4)] for r in range(4)]

    q_embd_0, q_blk_0 = apply_block_quantizer_only(w_embd_base, w_blk_base, 1, 2)
    q_embd_1, q_blk_1 = apply_block_quantizer_only(w_embd_patched, w_blk_base, 1, 2)
    post_q_embd_diff = matrix_diff_exact(q_embd_1, q_embd_0)
    embd_patch_residual_zero = all(
        post_q_embd_diff[r][c] == dw_embd[r][c] for r in range(4) for c in range(4)
    )
    blk_identical = all(q_blk_1[r][c] == q_blk_0[r][c] for r in range(4) for c in range(4))
    dw_embd_energy = parse_exact_rational(dpi_metrics_exact(dw_embd)["frobenius_energy_sq"])
    post_q_energy = parse_exact_rational(dpi_metrics_exact(post_q_embd_diff)["frobenius_energy_sq"])
    survival_frac = post_q_energy / dw_embd_energy

    # Genuine per-row SHA-256 immutable lock pinpoints modified row(s) with 100% certainty
    base_lock = token_embd_row_hashes_exact(w_embd_base)
    patched_lock = token_embd_row_hashes_exact(w_embd_patched)
    changed_rows = [
        r for r in range(len(w_embd_base))
        if not hmac.compare_digest(base_lock["row_hashes"][str(r)], patched_lock["row_hashes"][str(r)])
    ]

    return {
        "hadamard_h8_exact_identities": {
            "order": 8,
            "symmetric": sym_ok,
            "h8_squared_eq_8I": h8_sq_ok,
        },
        "pure_spike_h8_spreading_law": {
            "spike_before_h8": coh_spike_before,
            "spike_after_h8": coh_spike_after,
            "coherence_ratio_drop": format_rational(
                parse_exact_rational(coh_spike_after["coherence_linf2_over_l22"])
                / parse_exact_rational(coh_spike_before["coherence_linf2_over_l22"])
            ),
        },
        "group128_mlp_spike_bwi_detection": {
            "benign_group128": grp_before,
            "spiked_group128": grp_after,
            "group_scale_sq_inflation_factor": format_rational(scale_sq_inflation),
            "spiked_block0_before_h8": blk0_before,
            "spiked_block0_after_h8": blk0_after,
            "h8_energy_conservation_exact": energy_scale_exact,
        },
        "unquantized_token_embd_bypass_theorem": {
            "post_quant_embd_patch_exact_invariant": embd_patch_residual_zero,
            "block_matrices_unchanged": blk_identical,
            "dw_embd_energy_sq": format_rational(dw_embd_energy),
            "post_quant_embd_energy_sq": format_rational(post_q_energy),
            "survival_fraction": format_rational(survival_frac),
            "per_row_sha256_base": base_lock["row_hashes"],
            "per_row_sha256_patched": patched_lock["row_hashes"],
            "base_manifest_sha256": base_lock["manifest_sha256"],
            "patched_manifest_sha256": patched_lock["manifest_sha256"],
            "changed_rows_detected": changed_rows,
            "unchanged_rows_count": len(w_embd_base) - len(changed_rows),
            "immutable_row_hash_lock_detected_edit": not hmac.compare_digest(
                base_lock["manifest_sha256"], patched_lock["manifest_sha256"]
            ),
        },
    }


# ------------------------------------------------------------------ Pillar 4: Aletheia v2.2 Governance Oracles (CS-15..CS-19)

def certify_cs15_scope_gate(
    *,
    has_constructive_fix: bool,
    beats_strongest_baseline: bool,
    model_families_tested: int,
    scoped_single_family_honestly: bool,
) -> dict[str, Any]:
    """CS-15 Constructive Generalization & Cross-Family Scope Gate."""
    require_exact_bool(has_constructive_fix, "has_constructive_fix")
    require_exact_bool(beats_strongest_baseline, "beats_strongest_baseline")
    require_exact_int(model_families_tested, "model_families_tested", lo=1)
    require_exact_bool(scoped_single_family_honestly, "scoped_single_family_honestly")
    flags: list[str] = []
    if not has_constructive_fix:
        flags.append("DIAGNOSIS_ONLY_NO_FIX")
    if not beats_strongest_baseline:
        flags.append("BELOW_STRONGEST_BASELINE")
    if model_families_tested < 2 and not scoped_single_family_honestly:
        flags.append("UNSCOPED_SINGLE_FAMILY_OVERCLAIM")
    return {
        "passed": len(flags) == 0,
        "flags": flags,
        "model_families_tested": model_families_tested,
    }


def _interp_piecewise_linear_exact(curve: list[tuple[Fraction, Fraction]], g_star: Fraction, label: str) -> Fraction:
    require_ok(type(curve) is list, "INVALID_CURVE", f"{label}: exact list required")
    require_ok(len(curve) >= 2, "SHORT_CURVE", f"{label}: >= 2 points required")
    pts: list[tuple[Fraction, Fraction]] = []
    for idx, pt in enumerate(curve):
        require_ok(type(pt) is tuple, "INVALID_POINT", f"{label}[{idx}] must be tuple")
        require_ok(len(pt) == 2, "INVALID_POINT", f"{label}[{idx}] must have length 2")
        gx = require_exact_fraction(pt[0], f"{label}[{idx}].G")
        fy = require_exact_fraction(pt[1], f"{label}[{idx}].F")
        if pts:
            require_ok(gx > pts[-1][0], "NON_MONOTONE_GAIN", f"{label}: gains must be strictly increasing")
        pts.append((gx, fy))
    require_exact_fraction(g_star, "g_star")
    require_ok(pts[0][0] <= g_star, "OUT_OF_OVERLAP", f"{label}: g_star below curve domain")
    require_ok(g_star <= pts[-1][0], "OUT_OF_OVERLAP", f"{label}: g_star above curve domain")
    for idx in range(len(pts) - 1):
        g0, f0 = pts[idx]
        g1, f1 = pts[idx + 1]
        if g0 <= g_star <= g1:
            return f0 + (f1 - f0) * (g_star - g0) / (g1 - g0)
    raise AletheiaV22Error("INTERP_UNREACHABLE", "unreachable interpolation state")  # pragma: no cover


def matched_gain_pareto_compare_exact(
    curve_a: list[tuple[Fraction, Fraction]],
    curve_b: list[tuple[Fraction, Fraction]],
    g_star: Fraction,
) -> dict[str, Any]:
    """CS-16 Exact Matched-Gain Pareto Comparator (detects unmatched-endpoint sign flips)."""
    fa_matched = _interp_piecewise_linear_exact(curve_a, g_star, "curve_a")
    fb_matched = _interp_piecewise_linear_exact(curve_b, g_star, "curve_b")
    fa_end = curve_a[-1][1]
    fb_end = curve_b[-1][1]
    unmatched_diff = fa_end - fb_end
    matched_diff = fa_matched - fb_matched
    sign_flipped = (unmatched_diff < 0 and matched_diff > 0) or (unmatched_diff > 0 and matched_diff < 0)
    require_ok(fb_matched > 0, "NONPOSITIVE_BASELINE_FORGETTING", "curve_b matched forgetting must be > 0")
    ratio = fa_matched / fb_matched
    return {
        "g_star": format_rational(g_star),
        "fa_unmatched_end": format_rational(fa_end),
        "fb_unmatched_end": format_rational(fb_end),
        "fa_matched": format_rational(fa_matched),
        "fb_matched": format_rational(fb_matched),
        "matched_ratio_fa_over_fb": format_rational(ratio),
        "unmatched_vs_matched_sign_flipped": sign_flipped,
    }


def detect_herding_hhi_exact(counts: list[int], max_top_share: Fraction = Fraction(1, 2)) -> dict[str, Any]:
    """CS-17 Exact rational HHI / top-share herding detector."""
    require_ok(type(counts) is list, "INVALID_COUNTS", "counts must be exact list")
    require_ok(len(counts) >= 2, "TOO_FEW_BUCKETS", "counts requires >= 2 choices")
    require_exact_fraction(max_top_share, "max_top_share")
    require_ok(max_top_share > 0, "INVALID_THRESHOLD", "max_top_share must be > 0")
    require_ok(max_top_share < 1, "INVALID_THRESHOLD", "max_top_share must be < 1")
    total = 0
    sum_sq = 0
    top = 0
    for c in counts:
        ci = require_exact_int(c, "counts[]", lo=0)
        total += ci
        sum_sq += ci * ci
        if ci > top:
            top = ci
    require_ok(total > 0, "ZERO_TOTAL_COUNTS", "sum(counts) must be > 0")
    top_share = Fraction(top, total)
    hhi = Fraction(sum_sq, total * total)
    return {
        "total_agents": total,
        "top_share": format_rational(top_share),
        "hhi": format_rational(hhi),
        "herding_flagged": top_share > max_top_share,
    }


def detect_sunk_cost_escalation_exact(
    baseline_alloc: Fraction,
    sunk_alloc: Fraction,
    max_shift: Fraction = Fraction(1, 20),
) -> dict[str, Any]:
    """CS-17 Exact zero-sunk-cost preregistered allocation shift detector."""
    require_exact_fraction(baseline_alloc, "baseline_alloc")
    require_exact_fraction(sunk_alloc, "sunk_alloc")
    require_exact_fraction(max_shift, "max_shift")
    require_ok(baseline_alloc >= 0, "INVALID_ALLOC", "baseline_alloc >= 0 required")
    require_ok(baseline_alloc <= 1, "INVALID_ALLOC", "baseline_alloc <= 1 required")
    require_ok(sunk_alloc >= 0, "INVALID_ALLOC", "sunk_alloc >= 0 required")
    require_ok(sunk_alloc <= 1, "INVALID_ALLOC", "sunk_alloc <= 1 required")
    require_ok(max_shift >= 0, "INVALID_SHIFT", "max_shift >= 0 required")
    shift = sunk_alloc - baseline_alloc
    return {
        "baseline_alloc": format_rational(baseline_alloc),
        "sunk_alloc": format_rational(sunk_alloc),
        "escalation_shift": format_rational(shift),
        "escalation_rejected": shift > max_shift,
    }


def evaluate_four_state_tost_exact(
    *,
    evidence_matched: bool,
    ci_lo: Fraction,
    ci_hi: Fraction,
    equiv_delta: Fraction,
) -> dict[str, Any]:
    """CS-18 Mandatory 4-state verdict + exact rational TOST equivalence gate ([lo, hi] subset (-delta, +delta))."""
    require_exact_bool(evidence_matched, "evidence_matched")
    require_exact_fraction(ci_lo, "ci_lo")
    require_exact_fraction(ci_hi, "ci_hi")
    require_exact_fraction(equiv_delta, "equiv_delta")
    require_ok(ci_lo <= ci_hi, "INVALID_CI", "ci_lo must be <= ci_hi")
    require_ok(equiv_delta > 0, "INVALID_DELTA", "equiv_delta must be > 0")

    if not evidence_matched:
        return {
            "verdict": "UNDETERMINABLE",
            "reason": "evidence_mismatch_mandatory_abstention",
            "null_overstatement_blocked": False,
        }
    if ci_lo > 0:
        return {"verdict": "SUPPORTED", "reason": "ci_strictly_positive", "null_overstatement_blocked": False}
    if ci_hi < 0:
        return {"verdict": "REFUTED", "reason": "ci_strictly_negative", "null_overstatement_blocked": False}
    if ci_lo > -equiv_delta and ci_hi < equiv_delta:
        return {"verdict": "EQUIVALENT_NULL", "reason": "tost_interval_strictly_inside_delta", "null_overstatement_blocked": False}
    return {
        "verdict": "UNDETERMINABLE",
        "reason": "non_significant_ci_exceeds_tost_delta",
        "null_overstatement_blocked": True,
    }


def _collect_assigned_target_tokens(target: ast.AST) -> set[str]:
    """Collect assigned target root/attr tokens ONLY (never subscript index names)."""
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Attribute):
        return {target.attr}
    if isinstance(target, ast.Subscript):
        return _collect_assigned_target_tokens(target.value)
    if isinstance(target, (ast.Tuple, ast.List)):
        out: set[str] = set()
        for elt in target.elts:
            out |= _collect_assigned_target_tokens(elt)
        return out
    if isinstance(target, ast.Starred):
        return _collect_assigned_target_tokens(target.value)
    return set()


def _collect_rhs_tokens(node: ast.AST) -> set[str]:
    tokens: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            tokens.add(sub.id)
        elif isinstance(sub, ast.Attribute):
            tokens.add(sub.attr)
    return tokens


def scan_ast_answer_key_leaks(source_code: str) -> dict[str, Any]:
    """CS-19 Syntactic direct-store AST scanner across Assign/AnnAssign/AugAssign/NamedExpr/Attribute/Subscript."""
    src = require_exact_str(source_code, "source_code")
    try:
        tree = ast.parse(src, filename="<cs19_scan>")
    except SyntaxError as exc:
        raise AletheiaV22Error("INVALID_PYTHON_SOURCE", f"syntax error: {exc}") from exc
    findings: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        lhs_names: set[str] = set()
        rhs_node: ast.AST | None = None
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                lhs_names |= _collect_assigned_target_tokens(tgt)
            rhs_node = node.value
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            lhs_names |= _collect_assigned_target_tokens(node.target)
            rhs_node = node.value
        if rhs_node is None:
            continue
        rhs_names = _collect_rhs_tokens(rhs_node)
        hit_lhs = sorted(lhs_names & _CANDIDATE_VAR_TOKENS)
        hit_rhs = sorted(rhs_names & _ORACLE_VAR_TOKENS)
        if hit_lhs and hit_rhs:
            findings.append({
                "line": node.lineno,
                "store_kind": type(node).__name__,
                "candidate_vars": hit_lhs,
                "oracle_vars": hit_rhs,
            })
    findings.sort(key=lambda item: (item["line"], item["store_kind"]))
    return {
        "passed": len(findings) == 0,
        "leak_count": len(findings),
        "findings": findings,
    }


def verify_sha256_digest_exact(claimed_hex: str, payload_bytes: bytes) -> dict[str, Any]:
    """CS-19 Strict full-64-lowercase-hex SHA-256 verifier (catches 8-char-prefix / memory-typed hallucinations)."""
    claimed = require_exact_str(claimed_hex, "claimed_hex")
    require_ok(type(payload_bytes) is bytes, "INVALID_BYTES", "payload_bytes must be exact bytes")
    require_ok(len(claimed) == 64, "INVALID_SHA256_FORMAT", "claimed_hex must be 64 hex chars")
    require_ok(all(ch in _HEX_LOWER for ch in claimed), "INVALID_SHA256_FORMAT", "claimed_hex must be lowercase hex")
    actual = hashlib.sha256(payload_bytes).hexdigest()
    full_match = hmac.compare_digest(claimed, actual)
    prefix8_match = hmac.compare_digest(claimed[:8], actual[:8])
    diff_chars = sum(1 for a, b in zip(claimed, actual) if a != b)
    return {
        "actual_sha256": actual,
        "full_match": full_match,
        "prefix8_match": prefix8_match,
        "prefix8_hallucination_caught": prefix8_match and not full_match,
        "mismatched_hex_chars": diff_chars,
    }


def build_pillar4_v22_governance() -> dict[str, Any]:
    # CS-15 empirical benchmark ratios (N0 from 2611.society-ai-scientists §5.5) + scope gate controls
    cs15_pass = certify_cs15_scope_gate(
        has_constructive_fix=True, beats_strongest_baseline=True, model_families_tested=2, scoped_single_family_honestly=False
    )
    cs15_fail_diag = certify_cs15_scope_gate(
        has_constructive_fix=False, beats_strongest_baseline=False, model_families_tested=1, scoped_single_family_honestly=False
    )

    # CS-16 matched-gain Pareto comparator: Korean vocab-freeze + 2.64x LoRA forgetting flip
    vocab_unmatched = Fraction(297, 1000)
    vocab_matched = Fraction(122, 1000)
    curve_lora = [(Fraction(0, 1), Fraction(0, 1)), (Fraction(3, 10), Fraction(15, 100))]
    curve_full = [
        (Fraction(0, 1), Fraction(0, 1)),
        (Fraction(3, 10), Fraction(5, 88)),
        (Fraction(8, 10), Fraction(25, 100)),
    ]
    lora_flip = matched_gain_pareto_compare_exact(curve_lora, curve_full, Fraction(3, 10))

    # CS-17 herding (88% vs 30%) + sunk-cost escalation (+16.2 pp = 81/500)
    herding_score_vis = detect_herding_hhi_exact([22, 1, 1, 1])
    herding_coord_only = detect_herding_hhi_exact([3, 3, 2, 2])
    sunk_escalated = detect_sunk_cost_escalation_exact(Fraction(119, 500), Fraction(200, 500))
    sunk_clean = detect_sunk_cost_escalation_exact(Fraction(119, 500), Fraction(119, 500))

    # CS-18 mandatory 4-state UNDETERMINABLE abstention over 300 distinct synthetic mismatched abstract records
    synthetic_300_records = [
        (f"SYN-MIS-{i:03d}", f"q_topic_{i % 15}_{i}", f"abs_topic_{(i + 7) % 15}_{i}")
        for i in range(300)
    ]
    distinct_300_count = len(set(synthetic_300_records))
    mismatched_300_abstained = sum(
        1 for _, q_topic, a_topic in synthetic_300_records
        if evaluate_four_state_tost_exact(
            evidence_matched=(q_topic == a_topic),
            ci_lo=Fraction(1, 20),
            ci_hi=Fraction(3, 20),
            equiv_delta=Fraction(1, 10),
        )["verdict"] == "UNDETERMINABLE"
    )
    tost_equiv_pass = evaluate_four_state_tost_exact(
        evidence_matched=True, ci_lo=Fraction(-9, 100), ci_hi=Fraction(9, 100), equiv_delta=Fraction(1, 10)
    )
    tost_overstate_blocked = evaluate_four_state_tost_exact(
        evidence_matched=True, ci_lo=Fraction(-3, 10), ci_hi=Fraction(2, 10), equiv_delta=Fraction(1, 10)
    )
    tost_supported = evaluate_four_state_tost_exact(
        evidence_matched=True, ci_lo=Fraction(1, 20), ci_hi=Fraction(3, 20), equiv_delta=Fraction(1, 10)
    )
    tost_refuted = evaluate_four_state_tost_exact(
        evidence_matched=True, ci_lo=Fraction(-3, 20), ci_hi=Fraction(-1, 20), equiv_delta=Fraction(1, 10)
    )

    # CS-19 AST answer-key leak scanner + memory-typed SHA-256 8-char prefix hallucination witness
    leaked_src = "def step(s_prev, s_exact):\n    s_curr = s_exact\n    return s_curr\n"
    clean_src = "def step(s_prev, s_exact):\n    s_curr = s_prev + 1\n    err = abs(s_curr - s_exact)\n    return s_curr, err\n"
    ast_leaked = scan_ast_answer_key_leaks(leaked_src)
    ast_clean = scan_ast_answer_key_leaks(clean_src)

    sample_bytes = b"aletheia-v2.2-cs19-memory-typed-sha256-fixture\n"
    real_sha = hashlib.sha256(sample_bytes).hexdigest()
    hallucinated_sha = real_sha[:8] + ("0" * 56)
    sha_hallucinated = verify_sha256_digest_exact(hallucinated_sha, sample_bytes)
    sha_exact = verify_sha256_digest_exact(real_sha, sample_bytes)

    return {
        "cs15_constructive_scope_gate": {
            "pass_control": cs15_pass,
            "diagnosis_only_unscoped_failure": cs15_fail_diag,
            "empirical_n0_benchmarks": {
                "agent_diagnosis_only_pct": "68",
                "agent_beats_strongest_baseline_pct": "56/5",
                "agent_multi_family_pct": "7",
            },
        },
        "cs16_matched_gain_pareto": {
            "korean_vocab_freeze_unmatched_drop": format_rational(vocab_unmatched),
            "korean_vocab_freeze_matched_drop": format_rational(vocab_matched),
            "korean_vocab_freeze_confound_overstatement": format_rational(vocab_unmatched - vocab_matched),
            "lora_vs_full_ft_2p64x_flip": lora_flip,
        },
        "cs17_herding_and_sunk_cost": {
            "score_visible_herding_88pct": herding_score_vis,
            "coordinate_only_control_30pct": herding_coord_only,
            "sunk_cost_escalation_16p2pp": sunk_escalated,
            "zero_sunk_cost_control": sunk_clean,
        },
        "cs18_abstention_and_tost": {
            "distinct_synthetic_mismatched_records": distinct_300_count,
            "mismatched_300_abstained_count": mismatched_300_abstained,
            "tost_true_equivalence": tost_equiv_pass,
            "tost_null_overstatement_blocked": tost_overstate_blocked,
            "tost_strictly_supported": tost_supported,
            "tost_strictly_refuted": tost_refuted,
        },
        "cs19_ast_leak_and_sha256_gate": {
            "ast_leaked_fixture": ast_leaked,
            "ast_clean_control": ast_clean,
            "sha256_prefix8_hallucination_fixture": sha_hallucinated,
            "sha256_exact_control": sha_exact,
        },
    }


# ------------------------------------------------------------------ Pillar 5: 3-Channel Persistence & Provenance Airlock

def evaluate_three_channel_airlock(record: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed 3-channel (Delta W, Delta KV, Delta P_data) persistence & provenance airlock."""
    require_ok(type(record) is dict, "INVALID_AIRLOCK_RECORD", "record must be exact dict")
    req_keys = {
        "token_embd_immutable_lock",
        "token_embd_digest_match",
        "max_block_dpi_ratio",
        "dpi_threshold",
        "cross_model_kv_reuse",
        "evicted_entity_mentions_remaining",
        "corpus_provenance_tagged",
        "pii_binding_leak_tested",
        "recall_cot_off",
        "recall_cot_on",
        "max_mode_transfer_gap",
    }
    require_ok(set(record.keys()) == req_keys, "INVALID_AIRLOCK_KEYS", "missing or unexpected airlock keys")

    embd_lock = require_exact_bool(record["token_embd_immutable_lock"], "token_embd_immutable_lock")
    embd_match = require_exact_bool(record["token_embd_digest_match"], "token_embd_digest_match")
    dpi_ratio = require_exact_fraction(record["max_block_dpi_ratio"], "max_block_dpi_ratio")
    dpi_thresh = require_exact_fraction(record["dpi_threshold"], "dpi_threshold")
    require_ok(dpi_ratio >= 1, "INVALID_DPI", "max_block_dpi_ratio >= 1 required")
    require_ok(dpi_thresh >= 1, "INVALID_DPI", "dpi_threshold >= 1 required")

    kv_reuse = require_exact_bool(record["cross_model_kv_reuse"], "cross_model_kv_reuse")
    kv_rem = require_exact_int(record["evicted_entity_mentions_remaining"], "evicted_entity_mentions_remaining", lo=0)

    prov_tag = require_exact_bool(record["corpus_provenance_tagged"], "corpus_provenance_tagged")
    pii_tested = require_exact_bool(record["pii_binding_leak_tested"], "pii_binding_leak_tested")
    r_off = require_exact_fraction(record["recall_cot_off"], "recall_cot_off")
    r_on = require_exact_fraction(record["recall_cot_on"], "recall_cot_on")
    max_gap = require_exact_fraction(record["max_mode_transfer_gap"], "max_mode_transfer_gap")
    require_ok(r_off >= 0, "INVALID_RECALL", "recall_cot_off >= 0 required")
    require_ok(r_off <= 1, "INVALID_RECALL", "recall_cot_off <= 1 required")
    require_ok(r_on >= 0, "INVALID_RECALL", "recall_cot_on >= 0 required")
    require_ok(r_on <= 1, "INVALID_RECALL", "recall_cot_on <= 1 required")
    require_ok(max_gap >= 0, "INVALID_GAP", "max_mode_transfer_gap >= 0 required")

    violations: list[str] = []
    # Channel 1: Weight persistence (Delta W)
    if not embd_lock:
        violations.append("CH1_TOKEN_EMBD_LOCK_DISABLED")
    if not embd_match:
        violations.append("CH1_TOKEN_EMBD_MUTATION_BLOCKED")
    if dpi_ratio > dpi_thresh:
        violations.append("CH1_BLOCK_DPI_CONCENTRATION_EXCEEDED")
    # Channel 2: KV-cache persistence (Delta KV)
    if kv_reuse:
        violations.append("CH2_CROSS_MODEL_KV_REUSE_FORBIDDEN")
    if kv_rem > 0:
        violations.append("CH2_RESIDUAL_KV_ENTITY_MENTIONS")
    # Channel 3: Data / Distillation & Mode-Transfer persistence (Delta P_data)
    if not prov_tag:
        violations.append("CH3_MISSING_CORPUS_PROVENANCE")
    if not pii_tested:
        violations.append("CH3_MISSING_PII_BINDING_AUDIT")
    mode_gap = abs(r_off - r_on)
    if mode_gap > max_gap:
        violations.append("CH3_COT_MODE_TRANSFER_GAP_EXCEEDED")

    return {
        "verdict": "ALLOW" if len(violations) == 0 else "DENY",
        "mode_transfer_gap": format_rational(mode_gap),
        "violation_count": len(violations),
        "violations": violations,
    }


def build_pillar5_three_channel_airlock() -> dict[str, Any]:
    clean_base: dict[str, Any] = {
        "token_embd_immutable_lock": True,
        "token_embd_digest_match": True,
        "max_block_dpi_ratio": Fraction(1, 1),
        "dpi_threshold": Fraction(8, 1),
        "cross_model_kv_reuse": False,
        "evicted_entity_mentions_remaining": 0,
        "corpus_provenance_tagged": True,
        "pii_binding_leak_tested": True,
        "recall_cot_off": Fraction(954, 1000),
        "recall_cot_on": Fraction(930, 1000),
        "max_mode_transfer_gap": Fraction(1, 20),
    }

    def _with(**overrides: Any) -> dict[str, Any]:
        rec = dict(clean_base)
        rec.update(overrides)
        return rec

    return {
        "clean_compliant_record": evaluate_three_channel_airlock(clean_base),
        "negative_controls": {
            "ch1_token_embd_tamper": evaluate_three_channel_airlock(_with(token_embd_digest_match=False)),
            "ch1_block_dpi_spike_32x": evaluate_three_channel_airlock(_with(max_block_dpi_ratio=Fraction(32, 1))),
            "ch2_cross_model_kv_reuse": evaluate_three_channel_airlock(_with(cross_model_kv_reuse=True)),
            "ch2_residual_kv_entity": evaluate_three_channel_airlock(_with(evicted_entity_mentions_remaining=1)),
            "ch3_cot_mode_transfer_954_to_800": evaluate_three_channel_airlock(
                _with(recall_cot_off=Fraction(954, 1000), recall_cot_on=Fraction(800, 1000))
            ),
        },
    }


def compute_s31_payload() -> dict[str, Any]:
    """Compute the complete pure-Z/Q Track S31 certificate payload (zero floats)."""
    return {
        "track_id": "TRACK-S31-ALETHEIA-V22-SOCIETY-MISFOLDING-TOMOGRAPHY",
        "oracle_class": "pure-Z/Q-dpi-bwi-hadamard-v22-governance+zone-b-hardened",
        "novelty_tier": "N1-exact-Q-tomography-and-v22-governance-over-N0-portal-27-28-benchmarks",
        "pillar_1_dpi_misfolding_separation": build_pillar1_dpi_separation(),
        "pillar_2_risk_asymmetry_and_bellwethers": build_pillar2_risk_and_bellwethers(),
        "pillar_3_siliquant_hadamard_bypass_bridge": build_pillar3_siliquant_misfolding_bridge(),
        "pillar_4_aletheia_v22_governance_cs15_cs19": build_pillar4_v22_governance(),
        "pillar_5_three_channel_provenance_airlock": build_pillar5_three_channel_airlock(),
    }
