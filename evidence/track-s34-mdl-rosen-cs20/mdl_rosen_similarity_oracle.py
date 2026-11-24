#!/usr/bin/env python3
"""Track S34 (Portal 31): Exact Pure-Z/Q Unification of Greene (2026) Two-Part MDL /
Prequential Regret + Requential Coding (arXiv:2607.11883) with Robert Rosen (1983,
PMID:6846566) Similarity Principles, Bifurcation Extrapolation Obstruction, and
Executable Aletheia v2.2 CS-20 Gate.

100% pure Python 3 stdlib (fractions.Fraction, hashlib, typing).
ZERO floating-point arithmetic, ZERO bare assert statements, ZERO RNG calls,
ZERO third-party imports, ZERO personal-path or private-repo references.

Honest Law-4 Novelty: N1 (clean-room unified pure-Z/Q exact-operator certifier
bridging two-part MDL / prequential / requential coding, siliquant Gemma 3 4B IT
Pareto dominance & log-convex bitrate law, Rosen commuting-diagram similarity &
Sturm/discriminant bifurcation obstruction, iso-MDL weight-space misfolding vs
DPI separation, and executable Aletheia v2.2 CS-20 gate; all classical theorems
and cited prior work strictly quarantined as N0).
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any

TRACK_ID = "TRACK-S34-MDL-ROSEN"
SCHEMA_VERSION = "1.0.0"
MAX_RATIONAL_BITS = 16_384
MAX_JSON_INT_BITS = 4_096
MAX_STR_LEN = 512

# Pinned empirical Gemma 3 IT constants from Track S30 (pinned_inputs/gemma-3-{270m,1b,4b}-it.jsonl)
SILIQUANT_SOURCE_DATASET = "pinned_from_s30_gemma_3_4b_it_jsonl"
SILIQUANT_SOURCE_FILE_SHA256 = "5895d850aff01a154a3b57e1c47468c90121e34316fa6e850ae866f6ec4dc23e"
SILIQUANT_270M_SOURCE_SHA256 = "dafe50f93262be5628b97a83b915a0f65aa4eaa52f09b1b9bfd36381c4b34a83"
SILIQUANT_1B_SOURCE_SHA256 = "040717b2d9c24d47e64fcc3b41156a375d651f180cd7b9f558ec603c60f7733f"
GEMMA_4B_ACTIVE_WEIGHTS = 3_208_642_560
GEMMA_4B_ACTIVE_MATRICES = 238
BF16_BPW = Fraction(16, 1)

# Exact rational pinned Wiki KL (nats) for Gemma 3 270M & 1B Q4_K_M vs EBG128:b560s16
SILIQUANT_GEMMA_270M_WIKI_KL_NATS: dict[str, Fraction] = {
    "file:Q4_K_M": Fraction(153_572, 1_000_000),
    "EBG128:b560s16": Fraction(178_904, 1_000_000),
}
SILIQUANT_GEMMA_1B_WIKI_KL_NATS: dict[str, Fraction] = {
    "file:Q4_K_M": Fraction(82_847, 1_000_000),
    "EBG128:b560s16": Fraction(98_952, 1_000_000),
}

# Exact rational pinned variant metrics (bits_per_weight_active, wiki kl_mean, py kl_mean)
SILIQUANT_GEMMA_4B_VARIANTS: dict[str, dict[str, Fraction]] = {
    "file:Q4_K_M": {
        "bpw": Fraction(1849, 384),
        "kl_wiki": Fraction(151_295, 1_000_000),
        "kl_py": Fraction(65_083, 1_000_000),
    },
    "EBG128:b560s16": {
        "bpw": Fraction(44_999_024_905_563_285, 10_000_000_000_000_000),
        "kl_wiki": Fraction(94_284, 1_000_000),
        "kl_py": Fraction(39_951, 1_000_000),
    },
    "ZBG128:b496s16": {
        "bpw": Fraction(39_999_024_905_563_285, 10_000_000_000_000_000),
        "kl_wiki": Fraction(215_755, 1_000_000),
        "kl_py": Fraction(95_986, 1_000_000),
    },
    "ZBG128:b560s16": {
        "bpw": Fraction(4_499_796_302_901_858, 1_000_000_000_000_000),
        "kl_wiki": Fraction(112_601, 1_000_000),
        "kl_py": Fraction(41_972, 1_000_000),
    },
    "ZBG128:b624s16": {
        "bpw": Fraction(49_999_564_480_866, 10_000_000_000_000),
        "kl_wiki": Fraction(58_527, 1_000_000),
        "kl_py": Fraction(24_128, 1_000_000),
    },
    "hZBG128:b560s16": {
        "bpw": Fraction(4_504_049_775_124_081, 1_000_000_000_000_000),
        "kl_wiki": Fraction(71_645, 1_000_000),
        "kl_py": Fraction(31_101, 1_000_000),
    },
}

# Log-convex Wiki bitrate law KL(b) = C * 2^(-alpha * b) from Track S30 / Portal 31
LOG_CONVEX_ALPHA_WIKI = Fraction(18_821, 10_000)
LOG_CONVEX_C_WIKI = Fraction(399_034, 10_000)
BITRATE_LAW_GRID: tuple[Fraction, ...] = (
    Fraction(4, 1),
    Fraction(9, 2),
    Fraction(5, 1),
    Fraction(6, 1),
    Fraction(8, 1),
)

# Exact TPU v5e BF16 decode ridge batch B* = 197,000 GFLOP/s / (2 * 1,365 GB/s) = 19700 / 273 ~ 72.161
TPU_V5E_BF16_RIDGE_B_STAR = Fraction(19_700, 273)

_CS20_SPEC_KEYS = frozenset(
    {
        "name",
        "discrete_regime_sig",
        "jacobian_discriminant",
        "active_bottleneck_phase",
        "dpi_concentration",
        "dpi_threshold",
    }
)


class MdlRosenError(ValueError):
    """Typed fail-closed error for Track S34 domain, algebraic, and Zone-B checks."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.detail = message


# ============================================================================
# 1. Strict Type, Domain, and Exact Rational Primitives
# ============================================================================

def require_ok(cond: bool, code: str, message: str) -> None:
    if type(cond) is not bool:
        raise MdlRosenError("INVALID_CONDITION_TYPE", f"{code}: condition must be exact bool")
    if not cond:
        raise MdlRosenError(code, message)


def require_exact_int(
    val: Any,
    name: str,
    lo: int | None = None,
    hi: int | None = None,
) -> int:
    if type(val) is not int:
        raise MdlRosenError("INVALID_INT_TYPE", f"{name} must be exact int")
    if val.bit_length() > MAX_RATIONAL_BITS:
        raise MdlRosenError("INT_BIT_LIMIT", f"{name} exceeds {MAX_RATIONAL_BITS}-bit cap")
    if lo is not None:
        if type(lo) is not int:
            raise MdlRosenError("INVALID_BOUND_TYPE", f"{name}: lo must be exact int")
        if val < lo:
            raise MdlRosenError("INT_OUT_OF_RANGE", f"{name} must be >= {lo}")
    if hi is not None:
        if type(hi) is not int:
            raise MdlRosenError("INVALID_BOUND_TYPE", f"{name}: hi must be exact int")
        if val > hi:
            raise MdlRosenError("INT_OUT_OF_RANGE", f"{name} must be <= {hi}")
    return val


def require_exact_bool(val: Any, name: str) -> bool:
    if type(val) is not bool:
        raise MdlRosenError("INVALID_BOOL_TYPE", f"{name} must be exact bool")
    return val


def require_exact_str(val: Any, name: str, *, min_len: int = 1, max_len: int = MAX_STR_LEN) -> str:
    if type(val) is not str:
        raise MdlRosenError("INVALID_STR_TYPE", f"{name} must be exact str")
    if "\x00" in val:
        raise MdlRosenError("NUL_BYTE_FORBIDDEN", f"{name} contains NUL byte")
    try:
        val.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise MdlRosenError("INVALID_UTF8_SURROGATE", f"{name} contains lone UTF-16 surrogate") from exc
    if len(val) < min_len:
        raise MdlRosenError("STR_TOO_SHORT", f"{name} length must be >= {min_len}")
    if len(val) > max_len:
        raise MdlRosenError("STR_TOO_LONG", f"{name} length exceeds {max_len}")
    return val


def require_exact_fraction(
    val: Any,
    name: str,
    *,
    lo: Fraction | None = None,
    hi: Fraction | None = None,
) -> Fraction:
    if type(val) is not Fraction:
        raise MdlRosenError("INVALID_FRACTION_TYPE", f"{name} must be exact Fraction")
    if val.numerator.bit_length() > MAX_RATIONAL_BITS:
        raise MdlRosenError("RATIONAL_BIT_LIMIT", f"{name} numerator exceeds {MAX_RATIONAL_BITS}-bit cap")
    if val.denominator.bit_length() > MAX_RATIONAL_BITS:
        raise MdlRosenError("RATIONAL_BIT_LIMIT", f"{name} denominator exceeds {MAX_RATIONAL_BITS}-bit cap")
    if lo is not None:
        if type(lo) is not Fraction:
            raise MdlRosenError("INVALID_BOUND_TYPE", f"{name}: lo must be exact Fraction")
        if val < lo:
            raise MdlRosenError("FRACTION_OUT_OF_RANGE", f"{name} below lower bound")
    if hi is not None:
        if type(hi) is not Fraction:
            raise MdlRosenError("INVALID_BOUND_TYPE", f"{name}: hi must be exact Fraction")
        if val > hi:
            raise MdlRosenError("FRACTION_OUT_OF_RANGE", f"{name} above upper bound")
    return val


def format_fraction(q: Fraction) -> str:
    q = require_exact_fraction(q, "q")
    if q.denominator == 1:
        return str(q.numerator)
    return f"{q.numerator}/{q.denominator}"


def format_decimal_rounded(q: Fraction, digits: int = 6) -> str:
    """Exact pure-integer half-up decimal formatter for Fraction (zero floats)."""
    q = require_exact_fraction(q, "q")
    digits = require_exact_int(digits, "digits", lo=1, hi=12)
    neg = q < 0
    aq = -q if neg else q
    scale = 10**digits
    scaled_x10 = (aq.numerator * scale * 10) // aq.denominator
    rounded = (scaled_x10 + 5) // 10
    if rounded == 0:
        neg = False
    whole = rounded // scale
    frac = rounded % scale
    prefix = "-" if neg else ""
    return f"{prefix}{whole}.{frac:0{digits}d}"


# ============================================================================
# 2. Pure-Q Elementary Enclosures (ln 2 via Artanh & 2^r via Taylor)
# ============================================================================

def certify_ln2_enclosure(terms: int = 14) -> tuple[Fraction, Fraction]:
    """Proven pure-Q bracket [lo, hi] for ln(2) = 2 * artanh(1/3) = 2 * sum 1/((2k+1)*3^(2k+1))."""
    terms = require_exact_int(terms, "terms", lo=4, hi=32)
    total = Fraction(0, 1)
    pow3 = 3
    for k in range(terms):
        total += Fraction(2, (2 * k + 1) * pow3)
        pow3 *= 9
    # Geometric remainder bound: sum_{j>=terms} 2/((2j+1)*3^(2j+1)) < (2/((2*terms+1)*3^(2*terms+1))) / (1 - 1/9)
    rem_upper = Fraction(9, 4 * (2 * terms + 1) * pow3)
    return (total, total + rem_upper)


def certify_exp_enclosure(x_lo: Fraction, x_hi: Fraction, terms: int = 18) -> tuple[Fraction, Fraction]:
    """Proven pure-Q bracket [lo, hi] for exp(x) given 0 <= x_lo <= x_hi < 1."""
    x_lo = require_exact_fraction(x_lo, "x_lo", lo=Fraction(0, 1), hi=Fraction(99, 100))
    x_hi = require_exact_fraction(x_hi, "x_hi", lo=x_lo, hi=Fraction(99, 100))
    terms = require_exact_int(terms, "terms", lo=6, hi=32)
    lo_sum = Fraction(0, 1)
    hi_sum = Fraction(0, 1)
    term_lo = Fraction(1, 1)
    term_hi = Fraction(1, 1)
    for k in range(terms):
        lo_sum += term_lo
        hi_sum += term_hi
        term_lo = term_lo * x_lo / (k + 1)
        term_hi = term_hi * x_hi / (k + 1)
    # Tail bound for 0 <= x < 1: sum_{j>=terms} x^j/j! <= (x^terms / terms!) / (1 - x/(terms+1))
    rem_upper = term_hi / (Fraction(1, 1) - x_hi / (terms + 1))
    return (lo_sum, hi_sum + rem_upper)


def certify_pow2_rational_enclosure(exp_q: Fraction, ln2_lo: Fraction, ln2_hi: Fraction) -> tuple[Fraction, Fraction]:
    """Proven pure-Q bracket [lo, hi] for 2^(exp_q) for rational exp_q >= 0."""
    exp_q = require_exact_fraction(exp_q, "exp_q", lo=Fraction(0, 1), hi=Fraction(64, 1))
    ln2_lo = require_exact_fraction(ln2_lo, "ln2_lo", lo=Fraction(1, 2), hi=Fraction(9, 10))
    ln2_hi = require_exact_fraction(ln2_hi, "ln2_hi", lo=ln2_lo, hi=Fraction(9, 10))
    int_part = exp_q.numerator // exp_q.denominator
    frac_part = exp_q - int_part
    base_scale = Fraction(1 << int_part, 1)
    if frac_part == 0:
        return (base_scale, base_scale)
    e_lo, e_hi = certify_exp_enclosure(frac_part * ln2_lo, frac_part * ln2_hi)
    return (base_scale * e_lo, base_scale * e_hi)


# ============================================================================
# 3. Pillar 1 — Exact Two-Part MDL vs Prequential Regret & Requential Coding
# ============================================================================

def exact_dyadic_codelength(prob: Fraction) -> int:
    """Exact codelength -log2(p) in Z_>=0 for a dyadic probability p = 2^(-k)."""
    prob = require_exact_fraction(prob, "prob", lo=Fraction(1, 1 << 30), hi=Fraction(1, 1))
    require_ok(prob.numerator == 1, "NON_DYADIC_PROB", "dyadic probability must have numerator 1")
    den = prob.denominator
    require_ok((den & (den - 1)) == 0, "NON_DYADIC_PROB", "dyadic probability denominator must be a power of 2")
    return den.bit_length() - 1


def _validate_dyadic_dist(dist: Any, name: str) -> list[Fraction]:
    if type(dist) is not list:
        raise MdlRosenError("INVALID_DIST_TYPE", f"{name} must be exact list")
    require_ok(len(dist) >= 2, "INVALID_DIST_LEN", f"{name} must have length >= 2")
    out: list[Fraction] = []
    total = Fraction(0, 1)
    for i, p in enumerate(dist):
        fp = require_exact_fraction(p, f"{name}[{i}]", lo=Fraction(0, 1), hi=Fraction(1, 1))
        if fp > 0:
            exact_dyadic_codelength(fp)
        out.append(fp)
        total += fp
    require_ok(total == Fraction(1, 1), "DIST_NOT_NORMALIZED", f"{name} probabilities must sum to 1")
    return out


def exact_dyadic_entropy_bits(q_dist: list[Fraction]) -> Fraction:
    """Exact Shannon entropy H(Q) in bits (pure Fraction) for dyadic distribution Q."""
    qs = _validate_dyadic_dist(q_dist, "q_dist")
    total = Fraction(0, 1)
    for q in qs:
        if q > 0:
            total += q * exact_dyadic_codelength(q)
    return total


def exact_dyadic_kl_bits(q_dist: list[Fraction], p_dist: list[Fraction]) -> Fraction:
    """Exact KL(Q || P) in bits (pure Fraction) for dyadic distributions Q, P."""
    qs = _validate_dyadic_dist(q_dist, "q_dist")
    ps = _validate_dyadic_dist(p_dist, "p_dist")
    require_ok(len(qs) == len(ps), "DIST_LEN_MISMATCH", "q_dist and p_dist lengths must match")
    total = Fraction(0, 1)
    for q, p in zip(qs, ps):
        if q > 0:
            require_ok(p > 0, "KL_SUPPORT_MISMATCH", "p must be positive wherever q is positive")
            total += q * (exact_dyadic_codelength(p) - exact_dyadic_codelength(q))
    return total


def exact_dyadic_cross_entropy_bits(q_dist: list[Fraction], p_dist: list[Fraction]) -> Fraction:
    """Exact cross-entropy H(Q, P) = sum q_i (-log2 p_i) in bits (pure Fraction)."""
    qs = _validate_dyadic_dist(q_dist, "q_dist")
    ps = _validate_dyadic_dist(p_dist, "p_dist")
    require_ok(len(qs) == len(ps), "DIST_LEN_MISMATCH", "q_dist and p_dist lengths must match")
    total = Fraction(0, 1)
    for q, p in zip(qs, ps):
        if q > 0:
            require_ok(p > 0, "KL_SUPPORT_MISMATCH", "p must be positive wherever q is positive")
            total += q * exact_dyadic_codelength(p)
    return total


def _tensor_dyadic_dist(d1: list[Fraction], d2: list[Fraction]) -> list[Fraction]:
    return [p * q for p in d1 for q in d2]


def verify_pillar1_mdl_prequential_requential() -> dict[str, Any]:
    """Certify Greene (2026) offline vs online MDL cancellation, hardcoding no-profit theorem,
    and arXiv:2607.11883 three-way Requential Coding noise-channel invariance."""
    p_unif = [Fraction(1, 4), Fraction(1, 4), Fraction(1, 4), Fraction(1, 4)]
    p_conv = [Fraction(1, 2), Fraction(1, 4), Fraction(1, 8), Fraction(1, 8)]

    # 32-symbol stream whose exact empirical distribution equals p_conv = (1/2, 1/4, 1/8, 1/8)
    block = [0, 0, 0, 0, 1, 1, 2, 3]
    stream = block + block + block + block
    t_len = len(stream)
    l_uniform = t_len * exact_dyadic_codelength(Fraction(1, 4))

    # Online learner starts uniform for first 4 steps (0,0,0,0), then converges to p_conv
    online_dists = [p_unif if idx < 4 else p_conv for idx in range(t_len)]
    l_theta_t = sum(exact_dyadic_codelength(p_conv[x]) for x in stream)
    l_online_raw = sum(exact_dyadic_codelength(online_dists[idx][x]) for idx, x in enumerate(stream))
    regret_r = sum(
        exact_dyadic_codelength(online_dists[idx][x]) - exact_dyadic_codelength(p_conv[x])
        for idx, x in enumerate(stream)
    )
    overhead_c = 2

    regimes: list[dict[str, Any]] = []
    cancellation_all_exact = True
    crossover_iff_all_exact = True
    for label, b_theta in (("large_model_online_wins", 12), ("exact_crossover_tie", 4), ("compact_model_offline_wins", 2)):
        l_off = l_theta_t + b_theta + overhead_c
        l_on = l_online_raw + overhead_c
        lhs_diff = l_off - l_on
        rhs_diff = b_theta - regret_r
        residual = lhs_diff - rhs_diff
        if residual != 0:
            cancellation_all_exact = False
        online_beats = l_on < l_off
        if online_beats != (regret_r < b_theta):
            crossover_iff_all_exact = False
        regimes.append(
            {
                "regime": label,
                "b_theta_bits": b_theta,
                "regret_R_bits": regret_r,
                "L_offline_bits": l_off,
                "L_online_bits": l_on,
                "L_diff_bits": lhs_diff,
                "cancellation_residual": residual,
                "online_beats_offline": online_beats,
            }
        )

    # 1b. Exact Verbatim Hardcoding No-Profit Theorem & Reuse Threshold (m >= 2)
    decoder_overhead = 2
    hardcode_checks: list[dict[str, Any]] = []
    hardcode_no_profit_ok = True
    for t_sz in (1, 4, 16, 32):
        lu_t = 2 * t_sz
        l_hc_zero = 2 * t_sz
        l_hc_dec = 2 * t_sz + decoder_overhead
        if not all((l_hc_zero >= lu_t, l_hc_dec > lu_t)):
            hardcode_no_profit_ok = False
        hardcode_checks.append(
            {
                "T": t_sz,
                "L_uniform_bits": lu_t,
                "L_hardcode_zero_overhead": l_hc_zero,
                "L_hardcode_with_decoder": l_hc_dec,
                "no_net_profit": l_hc_dec > lu_t,
            }
        )
    reuse_checks: list[dict[str, Any]] = []
    reuse_threshold_ok = True
    pattern_cost = 2
    for m_reuse in (1, 2, 4, 8):
        net_saving = 2 * m_reuse - pattern_cost
        strict_profit = net_saving > 0
        if strict_profit != (m_reuse >= 2):
            reuse_threshold_ok = False
        reuse_checks.append({"reuse_count_m": m_reuse, "net_saving_bits": net_saving, "strict_profit": strict_profit})

    # 1c. Exact Three-Way Separation: Two-Part MDL vs Prequential vs Requential (arXiv:2607.11883)
    # 16 steps: steps 0..3 student is uniform (KL=1/4 bit/step), steps 4..15 student matches teacher (KL=0)
    t_req = 16
    q_seq = [p_conv for _ in range(t_req)]
    p_seq = [p_unif if idx < 4 else p_conv for idx in range(t_req)]
    noise_u = [Fraction(1, 2), Fraction(1, 2)]
    h_noise = exact_dyadic_entropy_bits(noise_u)

    h_teacher_sum = sum((exact_dyadic_entropy_bits(q) for q in q_seq), Fraction(0, 1))
    preq_base = sum((exact_dyadic_cross_entropy_bits(q, p) for q, p in zip(q_seq, p_seq)), Fraction(0, 1))
    req_base = sum((exact_dyadic_kl_bits(q, p) for q, p in zip(q_seq, p_seq)), Fraction(0, 1))
    mdl_base = h_teacher_sum + Fraction(12, 1)

    q_noisy = [_tensor_dyadic_dist(q, noise_u) for q in q_seq]
    p_noisy = [_tensor_dyadic_dist(p, noise_u) for p in p_seq]
    h_teacher_noisy = sum((exact_dyadic_entropy_bits(q) for q in q_noisy), Fraction(0, 1))
    preq_noisy = sum((exact_dyadic_cross_entropy_bits(q, p) for q, p in zip(q_noisy, p_noisy)), Fraction(0, 1))
    req_noisy = sum((exact_dyadic_kl_bits(q, p) for q, p in zip(q_noisy, p_noisy)), Fraction(0, 1))
    mdl_noisy = h_teacher_noisy + Fraction(12, 1)

    delta_preq = preq_noisy - preq_base
    delta_mdl = mdl_noisy - mdl_base
    delta_req = req_noisy - req_base
    expected_noise_growth = Fraction(t_req, 1) * h_noise

    three_way_ok = all(
        (
            preq_base == h_teacher_sum + req_base,
            preq_noisy == h_teacher_noisy + req_noisy,
            delta_mdl == expected_noise_growth,
            delta_preq == expected_noise_growth,
            delta_req == Fraction(0, 1),
            req_base == Fraction(1, 1),
            mdl_base != preq_base,
            preq_base != req_base,
        )
    )

    all_verified = all(
        (
            l_uniform == 64,
            l_theta_t == 56,
            l_online_raw == 60,
            regret_r == 4,
            l_online_raw < l_uniform,
            cancellation_all_exact,
            crossover_iff_all_exact,
            hardcode_no_profit_ok,
            reuse_threshold_ok,
            three_way_ok,
        )
    )
    return {
        "alphabet_size": 4,
        "stream_length_T": t_len,
        "L_uniform_bits": l_uniform,
        "L_theta_T_bits": l_theta_t,
        "L_online_raw_bits": l_online_raw,
        "cumulative_regret_R_bits": regret_r,
        "overhead_c_bits": overhead_c,
        "offline_vs_online_regimes": regimes,
        "hardcode_no_profit_checks": hardcode_checks,
        "reuse_threshold_checks": reuse_checks,
        "three_way_separation": {
            "steps_T": t_req,
            "noise_channel_entropy_bits": format_fraction(h_noise),
            "expected_noise_growth_bits": format_fraction(expected_noise_growth),
            "mdl_two_part_base_bits": format_fraction(mdl_base),
            "mdl_two_part_noisy_bits": format_fraction(mdl_noisy),
            "mdl_two_part_delta_bits": format_fraction(delta_mdl),
            "prequential_base_bits": format_fraction(preq_base),
            "prequential_noisy_bits": format_fraction(preq_noisy),
            "prequential_delta_bits": format_fraction(delta_preq),
            "requential_kl_base_bits": format_fraction(req_base),
            "requential_kl_noisy_bits": format_fraction(req_noisy),
            "requential_kl_delta_bits": format_fraction(delta_req),
            "requential_invariant_under_noise": delta_req == 0,
        },
        "all_verified": all_verified,
    }


# ============================================================================
# 4. Pillar 2 — Exact siliquant Two-Part MDL Pareto & Optimal Bitrate Law
# ============================================================================

def verify_pillar2_siliquant_mdl_pareto() -> dict[str, Any]:
    """Certify Gemma 3 4B IT EBG128 strict two-part MDL Pareto dominance over Q4_K_M,
    proven pure-Q break-even corpus enclosures vs BF16, and log-convex bitrate law b*(T/N)."""
    ln2_lo, ln2_hi = certify_ln2_enclosure(14)
    ref_ln2_lo = Fraction(693_147_180_559, 1_000_000_000_000)
    ref_ln2_hi = Fraction(693_147_180_560, 1_000_000_000_000)
    ln2_bracket_verified = all((ref_ln2_lo < ln2_lo, ln2_lo < ln2_hi, ln2_hi < ref_ln2_hi))

    q4km = SILIQUANT_GEMMA_4B_VARIANTS["file:Q4_K_M"]
    ebg = SILIQUANT_GEMMA_4B_VARIANTS["EBG128:b560s16"]
    delta_bpw = ebg["bpw"] - q4km["bpw"]
    delta_kl_wiki = ebg["kl_wiki"] - q4km["kl_wiki"]
    delta_kl_py = ebg["kl_py"] - q4km["kl_py"]
    model_bits_saved = (q4km["bpw"] - ebg["bpw"]) * GEMMA_4B_ACTIVE_WEIGHTS

    ebg_strict_pareto = all(
        (
            delta_bpw < 0,
            delta_kl_wiki < 0,
            delta_kl_py < 0,
        )
    )

    # Proven pure-Q break-even corpus ratios T/N = (16 - b) * ln(2) / KL vs BF16
    breakeven: dict[str, dict[str, Any]] = {}
    for vname in ("EBG128:b560s16", "file:Q4_K_M", "ZBG128:b560s16", "hZBG128:b560s16"):
        v = SILIQUANT_GEMMA_4B_VARIANTS[vname]
        b_saved = BF16_BPW - v["bpw"]
        wiki_tn_lo = b_saved * ln2_lo / v["kl_wiki"]
        wiki_tn_hi = b_saved * ln2_hi / v["kl_wiki"]
        py_tn_lo = b_saved * ln2_lo / v["kl_py"]
        py_tn_hi = b_saved * ln2_hi / v["kl_py"]
        breakeven[vname] = {
            "bpw_dec6": format_decimal_rounded(v["bpw"], 6),
            "bpw_saved_vs_bf16_dec6": format_decimal_rounded(b_saved, 6),
            "kl_wiki_q": format_fraction(v["kl_wiki"]),
            "kl_py_q": format_fraction(v["kl_py"]),
            "wiki_T_over_N_lo_dec6": format_decimal_rounded(wiki_tn_lo, 6),
            "wiki_T_over_N_hi_dec6": format_decimal_rounded(wiki_tn_hi, 6),
            "wiki_tokens_lo_billions_dec3": format_decimal_rounded(wiki_tn_lo * GEMMA_4B_ACTIVE_WEIGHTS / 10**9, 3),
            "wiki_tokens_hi_billions_dec3": format_decimal_rounded(wiki_tn_hi * GEMMA_4B_ACTIVE_WEIGHTS / 10**9, 3),
            "py_T_over_N_lo_dec6": format_decimal_rounded(py_tn_lo, 6),
            "py_T_over_N_hi_dec6": format_decimal_rounded(py_tn_hi, 6),
            "py_tokens_lo_billions_dec3": format_decimal_rounded(py_tn_lo * GEMMA_4B_ACTIVE_WEIGHTS / 10**9, 3),
            "py_tokens_hi_billions_dec3": format_decimal_rounded(py_tn_hi * GEMMA_4B_ACTIVE_WEIGHTS / 10**9, 3),
        }

    # Check exact break-even ordering: EBG128 > Q4_K_M strictly on BOTH Wiki and Python
    ebg_beats_q4_breakeven = all(
        (
            (BF16_BPW - ebg["bpw"]) * ln2_lo / ebg["kl_wiki"] > (BF16_BPW - q4km["bpw"]) * ln2_hi / q4km["kl_wiki"],
            (BF16_BPW - ebg["bpw"]) * ln2_lo / ebg["kl_py"] > (BF16_BPW - q4km["bpw"]) * ln2_hi / q4km["kl_py"],
        )
    )

    # ZBG128 empirical monotonicity & log-convexity check across b496 -> b560 -> b624
    z4 = SILIQUANT_GEMMA_4B_VARIANTS["ZBG128:b496s16"]
    z45 = SILIQUANT_GEMMA_4B_VARIANTS["ZBG128:b560s16"]
    z5 = SILIQUANT_GEMMA_4B_VARIANTS["ZBG128:b624s16"]
    zbg_wiki_monotone = all((z4["kl_wiki"] > z45["kl_wiki"], z45["kl_wiki"] > z5["kl_wiki"]))
    zbg_py_monotone = all((z4["kl_py"] > z45["kl_py"], z45["kl_py"] > z5["kl_py"]))

    # Closed-form Log-Convex Bitrate Law: KL_nats(b) = C * 2^(-alpha * b)
    # Per-weight MDL (bits): L(b) = b + (T / (N * ln(2))) * C * 2^(-alpha * b)
    # Exact first derivative (1/ln(2) cancels ln(2) from d/db 2^(-alpha*b) identically):
    #   dL/db = 1 - (T/N) * (alpha * C) * 2^(-alpha * b) = 0  <=>  T/N(b*) = 2^(alpha * b*) / (alpha * C)
    # Second derivative at b*: d^2 L / db^2 = alpha * ln(2) > 0
    alpha = LOG_CONVEX_ALPHA_WIKI
    c_val = LOG_CONVEX_C_WIKI
    alpha_c = alpha * c_val
    second_deriv_at_opt_lo = alpha * ln2_lo
    second_deriv_at_opt_hi = alpha * ln2_hi

    # Certify ZBG128 empirical log-convex fit residuals across b496, b560, b624 (< 0.25% relative error)
    zbg_fit_residuals: list[dict[str, Any]] = []
    zbg_fit_residuals_ok = True
    for vname in ("ZBG128:b496s16", "ZBG128:b560s16", "ZBG128:b624s16"):
        v = SILIQUANT_GEMMA_4B_VARIANTS[vname]
        zp2_lo, zp2_hi = certify_pow2_rational_enclosure(alpha * v["bpw"], ln2_lo, ln2_hi)
        pred_lo = c_val / zp2_hi
        pred_hi = c_val / zp2_lo
        abs_err_hi = max(abs(v["kl_wiki"] - pred_lo), abs(v["kl_wiki"] - pred_hi))
        rel_err_pct_hi = abs_err_hi * 100 / v["kl_wiki"]
        within_bound = rel_err_pct_hi < Fraction(1, 4)
        if not within_bound:
            zbg_fit_residuals_ok = False
        zbg_fit_residuals.append(
            {
                "variant": vname,
                "bpw_dec6": format_decimal_rounded(v["bpw"], 6),
                "kl_wiki_obs_nats_q": format_fraction(v["kl_wiki"]),
                "kl_wiki_pred_lo_dec6": format_decimal_rounded(pred_lo, 6),
                "kl_wiki_pred_hi_dec6": format_decimal_rounded(pred_hi, 6),
                "rel_err_upper_pct_dec4": format_decimal_rounded(rel_err_pct_hi, 4),
                "within_0_25_pct": within_bound,
            }
        )

    bitrate_schedule: list[dict[str, Any]] = []
    prev_tn_hi = Fraction(0, 1)
    schedule_strictly_increasing = True
    schedule_convex_ok = True
    schedule_first_order_ok = True
    delta_step = Fraction(1, 4)
    step_pow_lo, step_pow_hi = certify_pow2_rational_enclosure(alpha * delta_step, ln2_lo, ln2_hi)
    # At optimal T/N = 2^(alpha*b)/(alpha*C), f(b + d) - f(b) = d + (2^(-alpha*d) - 1)/(alpha*ln2)
    # and f(b - d) - f(b) = -d + (2^(alpha*d) - 1)/(alpha*ln2); both strictly > 0 by convexity!
    plus_diff_lo = delta_step + (Fraction(1, 1) / step_pow_hi - 1) / (alpha * ln2_lo)
    minus_diff_lo = -delta_step + (step_pow_lo - 1) / (alpha * ln2_hi)

    for b_q in BITRATE_LAW_GRID:
        p2_lo, p2_hi = certify_pow2_rational_enclosure(alpha * b_q, ln2_lo, ln2_hi)
        tn_lo = p2_lo / alpha_c
        tn_hi = p2_hi / alpha_c
        dL_db_lo = Fraction(1, 1) - tn_hi * alpha_c / p2_lo
        dL_db_hi = Fraction(1, 1) - tn_lo * alpha_c / p2_hi
        first_order_pt_ok = all((dL_db_lo <= 0, 0 <= dL_db_hi, dL_db_hi - dL_db_lo < Fraction(1, 10**11)))
        if not first_order_pt_ok:
            schedule_first_order_ok = False
        if tn_lo <= prev_tn_hi:
            schedule_strictly_increasing = False
        prev_tn_hi = tn_hi
        if not all((second_deriv_at_opt_lo > 0, plus_diff_lo > 0, minus_diff_lo > 0)):
            schedule_convex_ok = False
        bitrate_schedule.append(
            {
                "bitrate_b_q": format_fraction(b_q),
                "T_over_N_lo_dec6": format_decimal_rounded(tn_lo, 6),
                "T_over_N_hi_dec6": format_decimal_rounded(tn_hi, 6),
                "tokens_billions_lo_dec3": format_decimal_rounded(tn_lo * GEMMA_4B_ACTIVE_WEIGHTS / 10**9, 3),
                "tokens_billions_hi_dec3": format_decimal_rounded(tn_hi * GEMMA_4B_ACTIVE_WEIGHTS / 10**9, 3),
                "dL_db_lo_dec12": format_decimal_rounded(dL_db_lo, 12),
                "dL_db_hi_dec12": format_decimal_rounded(dL_db_hi, 12),
                "first_order_zero_certified": first_order_pt_ok,
                "d2L_db2_at_opt_lo_dec6": format_decimal_rounded(second_deriv_at_opt_lo, 6),
            }
        )

    all_verified = all(
        (
            ln2_bracket_verified,
            ebg_strict_pareto,
            ebg_beats_q4_breakeven,
            zbg_wiki_monotone,
            zbg_py_monotone,
            zbg_fit_residuals_ok,
            schedule_strictly_increasing,
            schedule_convex_ok,
            schedule_first_order_ok,
        )
    )
    return {
        "model_id": "gemma-3-4b-it",
        "source_provenance": {
            "dataset": SILIQUANT_SOURCE_DATASET,
            "source_file_sha256": SILIQUANT_SOURCE_FILE_SHA256,
        },
        "kl_mean_units": "nats",
        "data_term_bits_formula": "(T / ln(2)) * kl_mean_nats",
        "first_order_ln2_cancellation_exact": True,
        "active_weights_N": GEMMA_4B_ACTIVE_WEIGHTS,
        "active_matrices": GEMMA_4B_ACTIVE_MATRICES,
        "ln2_enclosure_lo_dec12": format_decimal_rounded(ln2_lo, 12),
        "ln2_enclosure_hi_dec12": format_decimal_rounded(ln2_hi, 12),
        "ln2_within_reference_bracket": ln2_bracket_verified,
        "pareto_EBG128_vs_Q4_K_M": {
            "delta_bpw_dec6": format_decimal_rounded(delta_bpw, 6),
            "model_Gbits_saved_dec3": format_decimal_rounded(model_bits_saved / 10**9, 3),
            "delta_kl_wiki_q": format_fraction(delta_kl_wiki),
            "delta_kl_py_q": format_fraction(delta_kl_py),
            "strict_pareto_dominance_all_T_ge_0": ebg_strict_pareto,
        },
        "breakeven_vs_bf16": breakeven,
        "zbg128_rate_kl_monotone": all((zbg_wiki_monotone, zbg_py_monotone)),
        "zbg128_log_convex_fit_residuals": zbg_fit_residuals,
        "log_convex_bitrate_law": {
            "alpha_q": format_fraction(alpha),
            "C_q": format_fraction(c_val),
            "d2L_db2_at_opt_lo_dec6": format_decimal_rounded(second_deriv_at_opt_lo, 6),
            "d2L_db2_at_opt_hi_dec6": format_decimal_rounded(second_deriv_at_opt_hi, 6),
            "local_min_margin_plus_quarter_bpw_lo_dec6": format_decimal_rounded(plus_diff_lo, 6),
            "local_min_margin_minus_quarter_bpw_lo_dec6": format_decimal_rounded(minus_diff_lo, 6),
            "first_order_optimality_all_certified": schedule_first_order_ok,
            "strictly_convex": schedule_convex_ok,
            "strictly_monotone_T_over_N": schedule_strictly_increasing,
            "schedule": bitrate_schedule,
        },
        "all_verified": all_verified,
    }


# ============================================================================
# 5. Pillar 3 — Exact Rosen (1983) Similarity & Bifurcation Obstruction
# ============================================================================

def cubic_discriminant_exact(a3: Fraction, a2: Fraction, a1: Fraction, a0: Fraction) -> Fraction:
    """Exact cubic discriminant Delta = b^2 c^2 - 4 a c^3 - 4 b^3 d - 27 a^2 d^2 + 18 a b c d."""
    a = require_exact_fraction(a3, "a3")
    b = require_exact_fraction(a2, "a2")
    c = require_exact_fraction(a1, "a1")
    d = require_exact_fraction(a0, "a0")
    require_ok(a != 0, "DEGENERATE_CUBIC", "leading cubic coefficient must be nonzero")
    return b * b * c * c - 4 * a * c * c * c - 4 * b * b * b * d - 27 * a * a * d * d + 18 * a * b * c * d


def vdw_reduced_poly_eval(p_r: Fraction, v_r: Fraction, t_r: Fraction) -> tuple[Fraction, Fraction, Fraction]:
    """Evaluate exact reduced van der Waals polynomial F(V_r), F'(V_r), F''(V_r) for
    F(V_r) = 3 P_r V_r^3 - (P_r + 8 T_r) V_r^2 + 9 V_r - 3."""
    pr = require_exact_fraction(p_r, "p_r")
    vr = require_exact_fraction(v_r, "v_r")
    tr = require_exact_fraction(t_r, "t_r")
    f0 = 3 * pr * vr * vr * vr - (pr + 8 * tr) * vr * vr + 9 * vr - 3
    f1 = 9 * pr * vr * vr - 2 * (pr + 8 * tr) * vr + 9
    f2 = 18 * pr * vr - 2 * (pr + 8 * tr)
    return (f0, f1, f2)


def vdw_cubic_discriminant(p_r: Fraction, t_r: Fraction) -> Fraction:
    """Exact discriminant of reduced van der Waals cubic 3 P_r V_r^3 - (P_r + 8 T_r) V_r^2 + 9 V_r - 3."""
    pr = require_exact_fraction(p_r, "p_r", lo=Fraction(1, 10_000))
    tr = require_exact_fraction(t_r, "t_r", lo=Fraction(1, 10_000))
    return cubic_discriminant_exact(3 * pr, -(pr + 8 * tr), Fraction(9, 1), Fraction(-3, 1))


def _poly_trim(p: list[Fraction]) -> list[Fraction]:
    out = list(p)
    while len(out) > 1 and out[-1] == 0:
        out.pop()
    return out


def _poly_rem(a: list[Fraction], b: list[Fraction]) -> list[Fraction]:
    rem = _poly_trim(a)
    div = _poly_trim(b)
    db = len(div) - 1
    lb = div[-1]
    while len(rem) - 1 >= db:
        shift = (len(rem) - 1) - db
        coeff = rem[-1] / lb
        for i in range(db + 1):
            rem[shift + i] -= coeff * div[i]
        rem = _poly_trim(rem)
    return rem


def _sign_variations(signs: list[int]) -> int:
    nz = [s for s in signs if s != 0]
    changes = 0
    for i in range(len(nz) - 1):
        if nz[i] * nz[i + 1] < 0:
            changes += 1
    return changes


def sturm_real_root_count_depressed_cubic(a: Fraction, b: Fraction) -> int:
    """Exact pure-Q Sturm real-root counter for square-free depressed cubic x^3 + a x + b = 0."""
    a = require_exact_fraction(a, "a")
    b = require_exact_fraction(b, "b")
    disc = -4 * a * a * a - 27 * b * b
    require_ok(disc != 0, "NON_SQUAREFREE_CUBIC", "Sturm count requires nonzero cubic discriminant")
    f0 = [b, a, Fraction(0, 1), Fraction(1, 1)]
    f1 = [a, Fraction(0, 1), Fraction(3, 1)]
    seq = [f0, f1]
    while len(seq[-1]) > 1:
        r = _poly_rem(seq[-2], seq[-1])
        seq.append([-c for c in r])
    signs_neg_inf: list[int] = []
    signs_pos_inf: list[int] = []
    for poly in seq:
        deg = len(poly) - 1
        lead = poly[-1]
        s_pos = 1 if lead > 0 else -1
        s_neg = -s_pos if (deg % 2 == 1) else s_pos
        signs_pos_inf.append(s_pos)
        signs_neg_inf.append(s_neg)
    return _sign_variations(signs_neg_inf) - _sign_variations(signs_pos_inf)


def verify_pillar3_rosen_similarity_bifurcation() -> dict[str, Any]:
    """Certify Rosen (1983) within-phase prototype commutation (power law + reduced van der Waals),
    exact critical point (1,1,1), and exact cusp/pitchfork topological cardinality obstruction (1 != 3)."""
    # 3a. Power-law Buckingham-Pi exact similarity Phi(a, x) = x^2 - a = 0 under (T_a, T_x) = (lam^2 a, lam x)
    power_cases = [
        (Fraction(1, 1), Fraction(1, 1), Fraction(2, 1)),
        (Fraction(4, 1), Fraction(2, 1), Fraction(3, 2)),
        (Fraction(9, 4), Fraction(3, 2), Fraction(5, 3)),
    ]
    power_ok = True
    for a0, x0, lam in power_cases:
        phi0 = x0 * x0 - a0
        a1 = lam * lam * a0
        x1 = lam * x0
        phi1 = x1 * x1 - a1
        jac0 = 2 * x0
        jac1 = 2 * x1
        if not all((phi0 == 0, phi1 == 0, jac0 != 0, jac1 != 0)):
            power_ok = False

    # 3b. Reduced van der Waals corresponding-states commutation & exact critical point (1, 1, 1)
    gas1 = (Fraction(3, 1), Fraction(2, 1), Fraction(5, 1))
    gas2 = (Fraction(11, 2), Fraction(7, 3), Fraction(13, 2))
    vdw_comm_ok = True
    for vr in (Fraction(2, 1), Fraction(3, 1), Fraction(4, 1)):
        pr = Fraction(1, 1)
        tr = (pr + Fraction(3, 1) / (vr * vr)) * (3 * vr - 1) / 8
        # Physical states in Gas 1 and similarity-mapped Gas 2
        p1, v1, t1 = pr * gas1[0], vr * gas1[1], tr * gas1[2]
        p2 = p1 * (gas2[0] / gas1[0])
        v2 = v1 * (gas2[1] / gas1[1])
        t2 = t1 * (gas2[2] / gas1[2])
        res1 = (p1 + 3 * gas1[0] * gas1[1] * gas1[1] / (v1 * v1)) * (3 * v1 - gas1[1]) - 8 * gas1[0] * gas1[1] * (t1 / gas1[2])
        res2 = (p2 + 3 * gas2[0] * gas2[1] * gas2[1] / (v2 * v2)) * (3 * v2 - gas2[1]) - 8 * gas2[0] * gas2[1] * (t2 / gas2[2])
        f_red, df_red, _ = vdw_reduced_poly_eval(pr, vr, tr)
        if not all((res1 == 0, res2 == 0, f_red == 0, df_red != 0)):
            vdw_comm_ok = False

    # Exact rational critical point (P_r, V_r, T_r) = (1, 1, 1)
    crit_f0, crit_f1, crit_f2 = vdw_reduced_poly_eval(Fraction(1, 1), Fraction(1, 1), Fraction(1, 1))
    crit_disc = vdw_cubic_discriminant(Fraction(1, 1), Fraction(1, 1))
    crit_ok = all((crit_f0 == 0, crit_f1 == 0, crit_f2 == 0, crit_disc == 0))

    # Van der Waals supercritical vs subcritical discriminant sign flip & physical root separation
    vdw_super_t2 = vdw_cubic_discriminant(Fraction(1, 1), Fraction(2, 1))
    vdw_super_t3 = vdw_cubic_discriminant(Fraction(1, 1), Fraction(3, 1))
    vdw_sub_t78 = vdw_cubic_discriminant(Fraction(1, 2), Fraction(7, 8))
    # Verify 3 distinct physical roots in (1/3, inf) at (P_r=1/2, T_r=7/8) via exact rational sign changes + exact root V_r=1
    f_half, _, _ = vdw_reduced_poly_eval(Fraction(1, 2), Fraction(1, 2), Fraction(7, 8))
    f_3q, _, _ = vdw_reduced_poly_eval(Fraction(1, 2), Fraction(3, 4), Fraction(7, 8))
    f_one, _, _ = vdw_reduced_poly_eval(Fraction(1, 2), Fraction(1, 1), Fraction(7, 8))
    f_three, _, _ = vdw_reduced_poly_eval(Fraction(1, 2), Fraction(3, 1), Fraction(7, 8))
    f_four, _, _ = vdw_reduced_poly_eval(Fraction(1, 2), Fraction(4, 1), Fraction(7, 8))
    vdw_sub_3roots_ok = all(
        (
            vdw_super_t2 < 0,
            vdw_super_t3 < 0,
            vdw_sub_t78 > 0,
            f_half * f_3q < 0,
            f_one == 0,
            f_three * f_four < 0,
        )
    )

    # 3c. Cusp/Pitchfork normal form Phi(a, b, x) = x^3 + a x + b = 0, Delta = -4a^3 - 27b^2
    disc_super = cubic_discriminant_exact(Fraction(1, 1), Fraction(0, 1), Fraction(1, 1), Fraction(0, 1))
    roots_super = sturm_real_root_count_depressed_cubic(Fraction(1, 1), Fraction(0, 1))
    disc_super2 = cubic_discriminant_exact(Fraction(1, 1), Fraction(0, 1), Fraction(2, 1), Fraction(3, 1))
    roots_super2 = sturm_real_root_count_depressed_cubic(Fraction(2, 1), Fraction(3, 1))

    # Fold bifurcation points (a=-3, b=+2) -> (x-1)^2(x+2) and (a=-3, b=-2) -> (x+1)^2(x-2)
    disc_fold_pos = cubic_discriminant_exact(Fraction(1, 1), Fraction(0, 1), Fraction(-3, 1), Fraction(2, 1))
    fold_pos_val = Fraction(1, 1) ** 3 - 3 * Fraction(1, 1) + 2
    fold_pos_jac = 3 * Fraction(1, 1) ** 2 - 3
    disc_fold_neg = cubic_discriminant_exact(Fraction(1, 1), Fraction(0, 1), Fraction(-3, 1), Fraction(-2, 1))
    fold_neg_val = Fraction(-1, 1) ** 3 - 3 * Fraction(-1, 1) - 2
    fold_neg_jac = 3 * Fraction(-1, 1) ** 2 - 3
    disc_cusp = cubic_discriminant_exact(Fraction(1, 1), Fraction(0, 1), Fraction(0, 1), Fraction(0, 1))

    # Multi-phase 3-real-root points: (a=-4, b=0) -> {-2, 0, +2} and (a=-7, b=6) -> {-3, 1, 2}
    disc_multi = cubic_discriminant_exact(Fraction(1, 1), Fraction(0, 1), Fraction(-4, 1), Fraction(0, 1))
    roots_multi = sturm_real_root_count_depressed_cubic(Fraction(-4, 1), Fraction(0, 1))
    multi_explicit_ok = all((r**3 - 4 * r == 0 for r in (-2, 0, 2)))
    disc_multi2 = cubic_discriminant_exact(Fraction(1, 1), Fraction(0, 1), Fraction(-7, 1), Fraction(6, 1))
    roots_multi2 = sturm_real_root_count_depressed_cubic(Fraction(-7, 1), Fraction(6, 1))
    multi2_explicit_ok = all((r**3 - 7 * r + 6 == 0 for r in (-3, 1, 2)))

    bifurcation_ok = all(
        (
            disc_super == Fraction(-4, 1),
            roots_super == 1,
            disc_super2 < 0,
            roots_super2 == 1,
            disc_fold_pos == 0,
            fold_pos_val == 0,
            fold_pos_jac == 0,
            disc_fold_neg == 0,
            fold_neg_val == 0,
            fold_neg_jac == 0,
            disc_cusp == 0,
            disc_multi == Fraction(256, 1),
            roots_multi == 3,
            multi_explicit_ok,
            disc_multi2 == Fraction(400, 1),
            roots_multi2 == 3,
            multi2_explicit_ok,
            roots_super != roots_multi,
        )
    )

    all_verified = all((power_ok, vdw_comm_ok, crit_ok, vdw_sub_3roots_ok, bifurcation_ok))
    return {
        "power_law_buckingham_pi_commutation_exact": power_ok,
        "vdw_corresponding_states_commutation_exact": vdw_comm_ok,
        "vdw_critical_point_1_1_1": {
            "F_val": format_fraction(crit_f0),
            "dF_dVr": format_fraction(crit_f1),
            "d2F_dVr2": format_fraction(crit_f2),
            "discriminant": format_fraction(crit_disc),
            "exact_triple_root": crit_ok,
        },
        "vdw_phase_discriminants": {
            "supercritical_Pr1_Tr2": format_fraction(vdw_super_t2),
            "supercritical_Pr1_Tr3": format_fraction(vdw_super_t3),
            "subcritical_Pr_half_Tr_7_8": format_fraction(vdw_sub_t78),
            "subcritical_three_physical_roots_verified": vdw_sub_3roots_ok,
        },
        "cusp_normal_form_obstruction": {
            "supercritical_a1_b0": {"discriminant": format_fraction(disc_super), "sturm_real_roots": roots_super},
            "supercritical_a2_b3": {"discriminant": format_fraction(disc_super2), "sturm_real_roots": roots_super2},
            "fold_a_neg3_b_pos2": {"discriminant": format_fraction(disc_fold_pos), "double_root_x": 1, "jacobian_dx": format_fraction(fold_pos_jac)},
            "fold_a_neg3_b_neg2": {"discriminant": format_fraction(disc_fold_neg), "double_root_x": -1, "jacobian_dx": format_fraction(fold_neg_jac)},
            "multi_phase_a_neg4_b0": {"discriminant": format_fraction(disc_multi), "sturm_real_roots": roots_multi, "explicit_roots": [-2, 0, 2]},
            "multi_phase_a_neg7_b6": {"discriminant": format_fraction(disc_multi2), "sturm_real_roots": roots_multi2, "explicit_roots": [-3, 1, 2]},
            "topological_cardinality_obstruction_1_ne_3": roots_super != roots_multi,
        },
        "all_verified": all_verified,
    }


# ============================================================================
# 6. Pillar 4 — Global MDL Blindness to Surgical Weight-Space Misfolding
# ============================================================================

def compute_row_energy_dpi(delta_matrix: list[list[Fraction]]) -> Fraction:
    """Exact Row-Energy Concentration DPI = max_r ||Delta[r]||_2^2 / mean_r ||Delta[r]||_2^2."""
    if type(delta_matrix) is not list:
        raise MdlRosenError("INVALID_MATRIX_TYPE", "delta_matrix must be exact list")
    n_rows = len(delta_matrix)
    require_ok(n_rows >= 2, "INVALID_MATRIX_DIM", "delta_matrix must have at least 2 rows")
    row_energies: list[Fraction] = []
    expected_cols: int | None = None
    for r_idx, row in enumerate(delta_matrix):
        if type(row) is not list:
            raise MdlRosenError("INVALID_MATRIX_ROW", f"row {r_idx} must be exact list")
        if expected_cols is None:
            require_ok(len(row) >= 1, "INVALID_MATRIX_DIM", "matrix rows must be non-empty")
            expected_cols = len(row)
        else:
            require_ok(len(row) == expected_cols, "INVALID_MATRIX_ROW", "all matrix rows must share column count")
        e_r = Fraction(0, 1)
        for c_idx, val in enumerate(row):
            fv = require_exact_fraction(val, f"delta[{r_idx}][{c_idx}]")
            e_r += fv * fv
        row_energies.append(e_r)
    total_e = sum(row_energies, Fraction(0, 1))
    require_ok(total_e > 0, "ZERO_PERTURBATION", "delta_matrix must have nonzero Frobenius energy")
    max_e = max(row_energies)
    mean_e = total_e / n_rows
    return max_e / mean_e


def _row_to_dyadic_distribution(row: list[Fraction]) -> list[Fraction]:
    """Exact pure-Q readout mapping row state (row[0], row[1]) to 4-symbol dyadic distribution."""
    # Truthful state: row[0] >= row[1] -> (1/2, 1/4, 1/8, 1/8); misfolded flip: row[1] > row[0] -> (1/8, 1/2, 1/4, 1/8)
    if row[0] >= row[1]:
        return [Fraction(1, 2), Fraction(1, 4), Fraction(1, 8), Fraction(1, 8)]
    return [Fraction(1, 8), Fraction(1, 2), Fraction(1, 4), Fraction(1, 8)]


def verify_pillar4_mdl_blindness_to_misfolding() -> dict[str, Any]:
    """Certify iso-MDL / iso-Frobenius blindness of global MDL & Requential KL on a synthetic
    64x16 weight-matrix misfolding witness (inspired by token_embd misfolding) vs exact Rosen
    readout defect & 64x DPI concentration spike."""
    vocab_rows = 64
    hidden_d = 16
    body_weights = 64_512
    total_weights = vocab_rows * hidden_d + body_weights  # 65,536
    base_bits_per_weight = 16
    base_model_bits = total_weights * base_bits_per_weight  # 1,048,576

    # Baseline embedding W_0: each row r has (1, 0, ..., 0)
    w0 = [[Fraction(1, 1) if j == 0 else Fraction(0, 1) for j in range(hidden_d)] for _ in range(vocab_rows)]

    # Benign diffuse quantization noise Delta_W_quant: every entry = 1/16 -> ||Delta||_F^2 = 1024 / 256 = 4
    dw_quant = [[Fraction(1, 16) for _ in range(hidden_d)] for _ in range(vocab_rows)]
    frob2_quant = sum((v * v for row in dw_quant for v in row), Fraction(0, 1))
    dpi_quant = compute_row_energy_dpi(dw_quant)

    # Surgical misfolding patch Delta_W_mis: nonzero ONLY on row 63 -> (-1, 1, 1, 1, 0, ...) -> ||Delta||_F^2 = 4!
    dw_mis = [[Fraction(0, 1) for _ in range(hidden_d)] for _ in range(vocab_rows)]
    dw_mis[63][0] = Fraction(-1, 1)
    dw_mis[63][1] = Fraction(1, 1)
    dw_mis[63][2] = Fraction(1, 1)
    dw_mis[63][3] = Fraction(1, 1)
    frob2_mis = sum((v * v for row in dw_mis for v in row), Fraction(0, 1))
    dpi_mis = compute_row_energy_dpi(dw_mis)

    w1 = [[w0[r][j] + dw_mis[r][j] for j in range(hidden_d)] for r in range(vocab_rows)]

    # Sparse patch model description bits: 6-bit row index + 16*16 payload bits = 262 bits
    patch_desc_bits = 6 + hidden_d * base_bits_per_weight
    rel_model_bits = Fraction(patch_desc_bits, base_model_bits)

    # Evaluate 12/12 generic control queries (rows 0..11) + out-of-support trigger query (row 63)
    ctrl_rows = list(range(12))
    ctrl_target_tokens = [0, 0, 1, 2, 0, 0, 1, 3, 0, 0, 1, 2]
    ctrl_l_w0 = 0
    ctrl_l_w1 = 0
    ctrl_kl_sum = Fraction(0, 1)
    ctrl_identical_count = 0
    for r, tok in zip(ctrl_rows, ctrl_target_tokens):
        p0 = _row_to_dyadic_distribution(w0[r])
        p1 = _row_to_dyadic_distribution(w1[r])
        ctrl_l_w0 += exact_dyadic_codelength(p0[tok])
        ctrl_l_w1 += exact_dyadic_codelength(p1[tok])
        ctrl_kl_sum += exact_dyadic_kl_bits(p0, p1)
        if p0 == p1:
            ctrl_identical_count += 1

    p0_trig = _row_to_dyadic_distribution(w0[63])
    p1_trig = _row_to_dyadic_distribution(w1[63])
    trig_kl = exact_dyadic_kl_bits(p0_trig, p1_trig)
    trig_l1_defect = sum((abs(a - b) for a, b in zip(p0_trig, p1_trig)), Fraction(0, 1))
    trig_argmax_w0 = p0_trig.index(max(p0_trig))
    trig_argmax_w1 = p1_trig.index(max(p1_trig))

    dpi_ratio = dpi_mis / dpi_quant
    all_verified = all(
        (
            frob2_quant == frob2_mis,
            frob2_mis == Fraction(4, 1),
            rel_model_bits <= Fraction(1, 1_000),
            ctrl_identical_count == 12,
            ctrl_l_w1 - ctrl_l_w0 == 0,
            ctrl_kl_sum == 0,
            trig_argmax_w0 == 0,
            trig_argmax_w1 == 1,
            trig_kl > 0,
            trig_l1_defect > 0,
            dpi_quant == Fraction(1, 1),
            dpi_mis == Fraction(64, 1),
            dpi_ratio >= Fraction(32, 1),
        )
    )
    return {
        "model_scope": "synthetic_64x16_weight_matrix_witness",
        "vocab_rows": vocab_rows,
        "hidden_dim": hidden_d,
        "total_model_weights": total_weights,
        "base_model_bits": base_model_bits,
        "patch_description_bits": patch_desc_bits,
        "relative_model_bit_overhead_q": format_fraction(rel_model_bits),
        "frobenius_norm_sq_benign_quant": format_fraction(frob2_quant),
        "frobenius_norm_sq_misfolding_patch": format_fraction(frob2_mis),
        "iso_frobenius_exact": frob2_quant == frob2_mis,
        "control_queries_checked": len(ctrl_rows),
        "control_queries_identical": ctrl_identical_count,
        "control_delta_L_theta_bits": ctrl_l_w1 - ctrl_l_w0,
        "control_requential_kl_bits": format_fraction(ctrl_kl_sum),
        "trigger_argmax_W0": trig_argmax_w0,
        "trigger_argmax_W1": trig_argmax_w1,
        "trigger_kl_bits": format_fraction(trig_kl),
        "trigger_rosen_commutation_l1_defect": format_fraction(trig_l1_defect),
        "dpi_benign_quant": format_fraction(dpi_quant),
        "dpi_misfolding_patch": format_fraction(dpi_mis),
        "dpi_separation_ratio": format_fraction(dpi_ratio),
        "all_verified": all_verified,
    }


# ============================================================================
# 7. Pillar 5 — Executable Aletheia v2.2 CS-20 Extrapolation-Boundary Gate
# ============================================================================

def _validate_cs20_spec(spec: Any, label: str) -> dict[str, Any]:
    if type(spec) is not dict:
        raise MdlRosenError("INVALID_CS20_SPEC", f"{label} must be exact dict")
    require_ok(set(spec.keys()) == _CS20_SPEC_KEYS, "INVALID_CS20_SPEC_KEYS", f"{label} has missing or unexpected keys")
    name = require_exact_str(spec["name"], f"{label}.name")
    regime = require_exact_str(spec["discrete_regime_sig"], f"{label}.discrete_regime_sig")
    disc = require_exact_fraction(spec["jacobian_discriminant"], f"{label}.jacobian_discriminant")
    bottleneck = require_exact_str(spec["active_bottleneck_phase"], f"{label}.active_bottleneck_phase")
    dpi_val = require_exact_fraction(spec["dpi_concentration"], f"{label}.dpi_concentration", lo=Fraction(1, 1))
    dpi_thr = require_exact_fraction(spec["dpi_threshold"], f"{label}.dpi_threshold", lo=Fraction(1, 1))
    return {
        "name": name,
        "discrete_regime_sig": regime,
        "jacobian_discriminant": disc,
        "active_bottleneck_phase": bottleneck,
        "dpi_concentration": dpi_val,
        "dpi_threshold": dpi_thr,
    }


def evaluate_cs20_extrapolation_gate(
    prototype_spec: dict[str, Any],
    target_spec: dict[str, Any],
) -> dict[str, Any]:
    """Executable Aletheia v2.2 CS-20 (Bifurcation-Blind Extrapolation) Gate.

    Returns ALLOW_EXTRAPOLATION iff all 4 exact structural invariant checks pass;
    otherwise returns DENY_PHASE_BIFURCATION with exact non-empty reason_codes.
    """
    proto = _validate_cs20_spec(prototype_spec, "prototype_spec")
    tgt = _validate_cs20_spec(target_spec, "target_spec")
    reasons: list[str] = []

    if proto["discrete_regime_sig"] != tgt["discrete_regime_sig"]:
        reasons.append("DISCRETE_REGIME_CLIFF")

    d_p = proto["jacobian_discriminant"]
    d_t = tgt["jacobian_discriminant"]
    if d_p == 0 or d_t == 0:
        reasons.append("SINGULAR_BIFURCATION_MANIFOLD")
    elif (d_p > 0) != (d_t > 0):
        reasons.append("DISCRIMINANT_SIGN_FLIP")

    if proto["active_bottleneck_phase"] != tgt["active_bottleneck_phase"]:
        reasons.append("BOTTLENECK_PHASE_CROSSING")

    if proto["dpi_concentration"] > proto["dpi_threshold"] or tgt["dpi_concentration"] > tgt["dpi_threshold"]:
        reasons.append("DPI_STRUCTURAL_CONCENTRATION_SPIKE")

    allowed = len(reasons) == 0
    return {
        "prototype": proto["name"],
        "target": tgt["name"],
        "verdict": "ALLOW_EXTRAPOLATION" if allowed else "DENY_PHASE_BIFURCATION",
        "allowed": allowed,
        "reason_codes": reasons,
    }


def _make_siliquant_q4km_spec(
    name: str,
    promoted_kinds: int,
    total_kinds: int,
    kl_ref_nats: Fraction,
    kl_q4km_nats: Fraction,
) -> dict[str, Any]:
    p_k = require_exact_int(promoted_kinds, "promoted_kinds", lo=0, hi=64)
    t_k = require_exact_int(total_kinds, "total_kinds", lo=1, hi=64)
    require_ok(p_k <= t_k, "INVALID_PROMOTED_COUNT", "promoted_kinds cannot exceed total_kinds")
    k_ref = require_exact_fraction(kl_ref_nats, "kl_ref_nats", lo=Fraction(0, 1))
    k_q4 = require_exact_fraction(kl_q4km_nats, "kl_q4km_nats", lo=Fraction(0, 1))
    regime = f"Q4_K_M:promoted_{p_k}_of_{t_k}" if p_k > 0 else f"Q4_K_M:fallback_0_of_{t_k}"
    return {
        "name": name,
        "discrete_regime_sig": regime,
        "jacobian_discriminant": k_ref - k_q4,
        "active_bottleneck_phase": "HBM_BOUND",
        "dpi_concentration": Fraction(1, 1),
        "dpi_threshold": Fraction(16, 1),
    }


def _make_cs16_lora_spec(
    name: str,
    protocol_sig: str,
    lora_forgetting: Fraction,
    full_ft_forgetting: Fraction,
) -> dict[str, Any]:
    proto_s = require_exact_str(protocol_sig, "protocol_sig")
    lf = require_exact_fraction(lora_forgetting, "lora_forgetting", lo=Fraction(0, 1))
    ff = require_exact_fraction(full_ft_forgetting, "full_ft_forgetting", lo=Fraction(1, 1_000_000))
    rel_delta = (lf - ff) / ff
    phase = "UNMATCHED_GAIN_APPARENT_WIN" if rel_delta < 0 else "GAIN_MATCHED_FORGETTING_REVERSAL"
    return {
        "name": name,
        "discrete_regime_sig": proto_s,
        "jacobian_discriminant": rel_delta,
        "active_bottleneck_phase": phase,
        "dpi_concentration": Fraction(1, 1),
        "dpi_threshold": Fraction(16, 1),
    }


def _make_tpu_v5e_spec(name: str, batch_b: int) -> dict[str, Any]:
    b_val = require_exact_int(batch_b, "batch_b", lo=1, hi=4096)
    margin = Fraction(b_val, 1) - TPU_V5E_BF16_RIDGE_B_STAR
    phase = "HBM_BOUND" if margin < 0 else "MXU_BOUND"
    return {
        "name": name,
        "discrete_regime_sig": "TPU_V5E_BF16_DECODE",
        "jacobian_discriminant": margin,
        "active_bottleneck_phase": phase,
        "dpi_concentration": Fraction(1, 1),
        "dpi_threshold": Fraction(16, 1),
    }


def verify_pillar5_cs20_extrapolation_gate(p4_res: dict[str, Any]) -> dict[str, Any]:
    """Certify executable Aletheia v2.2 CS-20 gate on 3 clean within-phase pairs (ALLOW)
    and 5 live expedition cross-boundary witnesses (DENY with exact reason codes)."""
    # Live van der Waals discriminants from Pillar 3
    vdw_d_t2 = vdw_cubic_discriminant(Fraction(1, 1), Fraction(2, 1))
    vdw_d_t3 = vdw_cubic_discriminant(Fraction(1, 1), Fraction(3, 1))
    vdw_d_sub = vdw_cubic_discriminant(Fraction(1, 2), Fraction(7, 8))

    # Live DPI from Pillar 4
    dpi_clean = Fraction(p4_res["dpi_benign_quant"])
    dpi_misfold = Fraction(p4_res["dpi_misfolding_patch"])
    dpi_thr = Fraction(16, 1)

    # Live siliquant Q4_K_M vs EBG128 KL specs from pinned Track S30 Gemma 3 270M, 1B, 4B JSONLs
    sq_270m = _make_siliquant_q4km_spec(
        "gemma3_270m_q4km_6of7",
        6,
        7,
        SILIQUANT_GEMMA_270M_WIKI_KL_NATS["EBG128:b560s16"],
        SILIQUANT_GEMMA_270M_WIKI_KL_NATS["file:Q4_K_M"],
    )
    sq_1b = _make_siliquant_q4km_spec(
        "gemma3_1b_q4km_6of7",
        6,
        7,
        SILIQUANT_GEMMA_1B_WIKI_KL_NATS["EBG128:b560s16"],
        SILIQUANT_GEMMA_1B_WIKI_KL_NATS["file:Q4_K_M"],
    )
    sq_4b = _make_siliquant_q4km_spec(
        "gemma3_4b_q4km_0of7",
        0,
        7,
        SILIQUANT_GEMMA_4B_VARIANTS["EBG128:b560s16"]["kl_wiki"],
        SILIQUANT_GEMMA_4B_VARIANTS["file:Q4_K_M"]["kl_wiki"],
    )

    # 3 Clean within-phase pairs -> MUST return ALLOW_EXTRAPOLATION
    clean_pairs = [
        ("siliquant_270M_to_1B_same_Q4KM_regime", sq_270m, sq_1b),
        (
            "tpu_v5e_B1_to_B32_both_HBM_bound",
            _make_tpu_v5e_spec("tpu_v5e_B1", 1),
            _make_tpu_v5e_spec("tpu_v5e_B32", 32),
        ),
        (
            "vdw_supercritical_Tr2_to_Tr3",
            {
                "name": "vdw_Pr1_Tr2",
                "discrete_regime_sig": "VDW_REDUCED_EOS",
                "jacobian_discriminant": vdw_d_t2,
                "active_bottleneck_phase": "SINGLE_PHASE_SUPERCRITICAL",
                "dpi_concentration": Fraction(1, 1),
                "dpi_threshold": dpi_thr,
            },
            {
                "name": "vdw_Pr1_Tr3",
                "discrete_regime_sig": "VDW_REDUCED_EOS",
                "jacobian_discriminant": vdw_d_t3,
                "active_bottleneck_phase": "SINGLE_PHASE_SUPERCRITICAL",
                "dpi_concentration": Fraction(1, 1),
                "dpi_threshold": dpi_thr,
            },
        ),
    ]
    clean_results: list[dict[str, Any]] = []
    clean_all_allow = True
    for case_id, p_spec, t_spec in clean_pairs:
        res = evaluate_cs20_extrapolation_gate(p_spec, t_spec)
        res["case_id"] = case_id
        if not all((res["verdict"] == "ALLOW_EXTRAPOLATION", res["allowed"] is True, res["reason_codes"] == [])):
            clean_all_allow = False
        clean_results.append(res)

    # 5 Live Expedition Cross-Boundary Witnesses -> MUST return DENY_PHASE_BIFURCATION
    deny_pairs = [
        (
            "W1_siliquant_1B_to_4B_Q4KM_fallback_cliff",
            sq_1b,
            sq_4b,
            ["DISCRETE_REGIME_CLIFF", "DISCRIMINANT_SIGN_FLIP"],
        ),
        (
            "W2_tpu_v5e_B32_to_B73_MXU_ridge_crossing",
            _make_tpu_v5e_spec("tpu_v5e_B32", 32),
            _make_tpu_v5e_spec("tpu_v5e_B73", 73),
            ["DISCRIMINANT_SIGN_FLIP", "BOTTLENECK_PHASE_CROSSING"],
        ),
        (
            "W3_vdw_supercritical_Tr2_to_subcritical_Tr_7_8",
            {
                "name": "vdw_Pr1_Tr2",
                "discrete_regime_sig": "VDW_REDUCED_EOS",
                "jacobian_discriminant": vdw_d_t2,
                "active_bottleneck_phase": "SINGLE_PHASE_SUPERCRITICAL",
                "dpi_concentration": Fraction(1, 1),
                "dpi_threshold": dpi_thr,
            },
            {
                "name": "vdw_Pr_half_Tr_7_8",
                "discrete_regime_sig": "VDW_REDUCED_EOS",
                "jacobian_discriminant": vdw_d_sub,
                "active_bottleneck_phase": "TWO_PHASE_SUBCRITICAL",
                "dpi_concentration": Fraction(1, 1),
                "dpi_threshold": dpi_thr,
            },
            ["DISCRIMINANT_SIGN_FLIP", "BOTTLENECK_PHASE_CROSSING"],
        ),
        (
            "W4_misfolding_iso_MDL_synthetic_64x16_DPI_spike",
            {
                "name": "model_W0_synthetic_64x16_benign_quant",
                "discrete_regime_sig": "SYNTHETIC_64X16_WEIGHT_EVAL",
                "jacobian_discriminant": Fraction(1, 1),
                "active_bottleneck_phase": "ISO_MDL_CONTROL",
                "dpi_concentration": dpi_clean,
                "dpi_threshold": dpi_thr,
            },
            {
                "name": "model_W1_synthetic_64x16_misfolded_row63",
                "discrete_regime_sig": "SYNTHETIC_64X16_WEIGHT_EVAL",
                "jacobian_discriminant": Fraction(1, 1),
                "active_bottleneck_phase": "ISO_MDL_CONTROL",
                "dpi_concentration": dpi_misfold,
                "dpi_threshold": dpi_thr,
            },
            ["DPI_STRUCTURAL_CONCENTRATION_SPIKE"],
        ),
        (
            "W5_society_ai_scientists_unmatched_gain_LoRA_sign_flip",
            _make_cs16_lora_spec(
                "lora_r16_unmatched_gain",
                "CS16_UNMATCHED_GAIN_PROTOCOL",
                Fraction(703, 1_000),
                Fraction(1, 1),
            ),
            _make_cs16_lora_spec(
                "lora_r16_gain_matched_2_64x",
                "CS16_GAIN_MATCHED_PROTOCOL",
                Fraction(264, 100),
                Fraction(1, 1),
            ),
            ["DISCRETE_REGIME_CLIFF", "DISCRIMINANT_SIGN_FLIP", "BOTTLENECK_PHASE_CROSSING"],
        ),
    ]
    deny_results: list[dict[str, Any]] = []
    deny_all_exact = True
    for case_id, p_spec, t_spec, exp_reasons in deny_pairs:
        res = evaluate_cs20_extrapolation_gate(p_spec, t_spec)
        res["case_id"] = case_id
        if not all((res["verdict"] == "DENY_PHASE_BIFURCATION", res["allowed"] is False, res["reason_codes"] == exp_reasons)):
            deny_all_exact = False
        deny_results.append(res)

    all_verified = all((clean_all_allow, deny_all_exact))
    return {
        "gate_id": "CS-20",
        "gate_name": "Bifurcation-Blind Extrapolation Gate",
        "siliquant_witness_provenance_sha256": {
            "gemma_3_270m_it": SILIQUANT_270M_SOURCE_SHA256,
            "gemma_3_1b_it": SILIQUANT_1B_SOURCE_SHA256,
            "gemma_3_4b_it": SILIQUANT_SOURCE_FILE_SHA256,
        },
        "siliquant_kl_advantage_nats_q": {
            "270m": format_fraction(sq_270m["jacobian_discriminant"]),
            "1b": format_fraction(sq_1b["jacobian_discriminant"]),
            "4b": format_fraction(sq_4b["jacobian_discriminant"]),
        },
        "tpu_v5e_bf16_ridge_B_star_q": format_fraction(TPU_V5E_BF16_RIDGE_B_STAR),
        "tpu_v5e_bf16_ridge_B_star_dec3": format_decimal_rounded(TPU_V5E_BF16_RIDGE_B_STAR, 3),
        "clean_within_phase_pairs_checked": len(clean_results),
        "clean_within_phase_results": clean_results,
        "cross_boundary_witnesses_checked": len(deny_results),
        "cross_boundary_witness_results": deny_results,
        "all_verified": all_verified,
    }


# ============================================================================
# 8. Unified Five-Pillar Payload Assembly
# ============================================================================

def compute_s34_payload() -> dict[str, Any]:
    """Compute the complete zero-float pure-Z/Q Track S34 five-pillar payload."""
    p1 = verify_pillar1_mdl_prequential_requential()
    p2 = verify_pillar2_siliquant_mdl_pareto()
    p3 = verify_pillar3_rosen_similarity_bifurcation()
    p4 = verify_pillar4_mdl_blindness_to_misfolding()
    p5 = verify_pillar5_cs20_extrapolation_gate(p4)
    all_ok = all((p1["all_verified"], p2["all_verified"], p3["all_verified"], p4["all_verified"], p5["all_verified"]))
    return {
        "track_id": TRACK_ID,
        "schema_version": SCHEMA_VERSION,
        "oracle_class": "exact",
        "novelty_class": "N1",
        "pillar1_mdl_prequential_requential": p1,
        "pillar2_siliquant_mdl_pareto": p2,
        "pillar3_rosen_similarity_bifurcation": p3,
        "pillar4_mdl_blindness_misfolding": p4,
        "pillar5_cs20_extrapolation_gate": p5,
        "all_pillars_verified": all_ok,
    }
