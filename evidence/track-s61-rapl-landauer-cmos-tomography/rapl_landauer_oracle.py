#!/usr/bin/env python3
"""Pure-Z/Q Exact Oracle for Millisecond intel-rapl Silicon Physics & Landauer-CMOS Tomography.

100% pure Python 3 stdlib (int, fractions.Fraction, hashlib, hmac, json).
ZERO IEEE-754 floats, ZERO float() calls, ZERO bare asserts, ZERO .isdigit(),
ZERO random imports, ZERO external dependencies.

Three strictly separated pillars:
  1. Pillar 1 (exact): Algebraic proof of R1/R3 bijectivity (0 erased bits; 3 vs 127
     bits/step Hamming toggle density) vs R2 strict many-to-one irreversibility.
  2. Pillar 2 (exact over sampled integer telemetry): Per-regime exact-Q power across
     all 5 unlocked intel-rapl domains, in-package dark-mode conservation residual
     (P_pkg - P_core - P_uncore), honest psys vendor-scale check, exact time-aligned
     pJ/op, exact SI-2019 Landauer ratio interval on R2, and deterministic permutation tests.
  3. Pillar 3 (exact coordinate-free blind tomography): Stage-A/B blind R^2 graph
     partition, exact square-root-free rational Schur complement & Sylvester inertia,
     exact 0-diff Stage-A permutation + positive rational affine gauge invariance,
     and deterministic block-circular-shift null.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import hmac
import json
from typing import Any

SCHEMA_VERSION = "aletheia.track_s61.rapl_landauer_cmos.v1"
TRACK_ID = "TRACK-S61-RAPL-LANDAUER-CMOS-TOMOGRAPHY"

MAX_INT_BITS = 3_321
MAX_INT_DIGITS = 1_000
MAX_STR_LEN = 512
MAX_JSON_DEPTH = 64

# Exact SI-2019 Boltzmann constant: k_B = 1.380649e-23 J/K = 1380649 / 10^29 J/K
KB_SI_2019_Q = Fraction(1_380_649, 10**29)
# Exact rational interval bracket for ln(2) = 0.6931471805599453094...
LN2_LO_Q = Fraction(693_147_180_559_945, 10**15)
LN2_HI_Q = Fraction(693_147_180_559_946, 10**15)
# Exact Celsius-to-Kelvin offset: 273.15 K = 27315 / 100
KELVIN_OFFSET_Q = Fraction(27_315, 100)

SCHUR_RIDGE_LAMBDA_Q = Fraction(1, 20)
BLIND_R2_EDGE_THRESHOLD_Q = Fraction(1, 4)
PERM_TEST_REPS = 99
CIRC_SHIFT_REPS = 39
PRNG_SEED_PERM = 0x61C8864680B583EB
PRNG_SEED_CIRC = 0x9E3779B97F4A7C15
MASK64 = (1 << 64) - 1

EXPECTED_REGIME_IDS: tuple[str, ...] = (
    "R0_IDLE",
    "R1_BIJECTIVE_FEISTEL_LOW_H",
    "R2_ERASE_DESTRUCTIVE_LOW_H",
    "R3_BIJECTIVE_FEISTEL_HIGH_H",
    "R4_AVX512_FMA_L1",
    "R5_AVX512_VNNI_L1",
    "R6_DRAM_STREAM_L3_MISS",
)

EXPECTED_RAPL_CHANNELS: tuple[str, ...] = (
    "rapl_package_0_duj",
    "rapl_core_duj",
    "rapl_uncore_duj",
    "rapl_psys_duj",
    "rapl_mmio_0_duj",
)

_HEX_LOWER = frozenset("0123456789abcdef")


class RaplLandauerError(ValueError):
    """Fail-closed typed error for all Track S61 oracle and verifier violations."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def require_ok(cond: Any, code: str, message: str) -> None:
    if type(cond) is not bool:
        raise RaplLandauerError("INVALID_CONDITION", f"require_ok expects exact bool, got {type(cond).__name__}")
    if not cond:
        raise RaplLandauerError(code, message)


def require_bool(val: Any, label: str = "bool") -> bool:
    require_ok(type(val) is bool, "INVALID_BOOL", f"{label}: exact bool required")
    return val


def require_exact_int(val: Any, label: str = "int", *, lo: int | None = None, hi: int | None = None) -> int:
    require_ok(type(val) is int, "INVALID_INT", f"{label}: exact int required")
    require_ok(abs(val).bit_length() <= MAX_INT_BITS, "INT_BIT_LIMIT", f"{label}: exceeds {MAX_INT_BITS} bits")
    if lo is not None:
        require_ok(type(lo) is int, "INVALID_BOUND", f"{label}: lo must be exact int")
        require_ok(val >= lo, "INT_OUT_OF_RANGE", f"{label}: {val} < {lo}")
    if hi is not None:
        require_ok(type(hi) is int, "INVALID_BOUND", f"{label}: hi must be exact int")
        require_ok(val <= hi, "INT_OUT_OF_RANGE", f"{label}: {val} > {hi}")
    return val


def require_str(val: Any, label: str = "str", *, max_len: int = MAX_STR_LEN, non_empty: bool = False) -> str:
    require_ok(type(val) is str, "INVALID_STR", f"{label}: exact str required")
    try:
        val.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise RaplLandauerError("INVALID_UTF8_SURROGATE", f"{label}: lone UTF-16 surrogate forbidden") from exc
    require_ok("\x00" not in val, "NUL_BYTE_FORBIDDEN", f"{label}: NUL byte forbidden")
    require_ok(len(val) <= max_len, "STR_TOO_LONG", f"{label}: exceeds max length {max_len}")
    if non_empty:
        require_ok(len(val.strip()) > 0, "EMPTY_STR", f"{label}: non-empty string required")
    return val


def is_valid_hex64(val: Any) -> bool:
    if type(val) is not str or len(val) != 64:
        return False
    for ch in val:
        if ch not in _HEX_LOWER:
            return False
    return True


def require_hex64(val: Any, label: str = "sha256") -> str:
    require_ok(is_valid_hex64(val), "INVALID_HEX64", f"{label}: 64-char lowercase ASCII hex required")
    return val


def format_rational(q: Fraction) -> str:
    require_ok(type(q) is Fraction, "INVALID_RATIONAL", "exact Fraction required")
    return str(q.numerator) if q.denominator == 1 else f"{q.numerator}/{q.denominator}"


def q_quantize_floor(q: Fraction, scale_pow10: int = 6) -> Fraction:
    """Deterministic exact floor quantization to 10^(-scale_pow10) for compact rational pins."""
    require_ok(type(q) is Fraction, "INVALID_RATIONAL", "exact Fraction required")
    factor = 10**scale_pow10
    scaled = q * factor
    floored = scaled.numerator // scaled.denominator
    return Fraction(floored, factor)


def format_decimal(q: Fraction, places: int = 4) -> str:
    """Exact pure-integer half-up decimal formatter with -0 suppression (zero float)."""
    require_ok(type(q) is Fraction, "INVALID_RATIONAL", "exact Fraction required")
    require_exact_int(places, "places", lo=0, hi=12)
    neg = q.numerator < 0
    num = -q.numerator if neg else q.numerator
    den = q.denominator
    scale = 10**places
    scaled_num = num * scale
    quot, rem = divmod(scaled_num, den)
    if rem * 2 >= den:
        quot += 1
    if quot == 0:
        neg = False
    sign = "-" if neg else ""
    if places == 0:
        return f"{sign}{quot}"
    whole, frac = divmod(quot, scale)
    return f"{sign}{whole}.{frac:0{places}d}"


def validate_strict_json_tree(root: Any, label: str = "json") -> None:
    """Iterative depth-bounded exact-type JSON tree validator (rejects floats, subclasses, surrogates, NUL)."""
    stack: list[tuple[Any, int]] = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        require_ok(depth <= MAX_JSON_DEPTH, "JSON_DEPTH_EXCEEDED", f"{label}: depth > {MAX_JSON_DEPTH}")
        t = type(node)
        if t is dict:
            for k, v in node.items():
                require_ok(type(k) is str, "INVALID_JSON_KEY_TYPE", f"{label}: key must be exact str")
                require_str(k, f"{label}.key", max_len=MAX_STR_LEN * 16)
                stack.append((v, depth + 1))
        elif t is list:
            for item in node:
                stack.append((item, depth + 1))
        elif t is int:
            require_ok(abs(node).bit_length() <= MAX_INT_BITS, "INT_BIT_LIMIT", f"{label}: int bit limit")
        elif t is str:
            require_str(node, f"{label}.str", max_len=MAX_STR_LEN * 16)
        elif t is bool or node is None:
            continue
        else:
            raise RaplLandauerError("FORBIDDEN_JSON_TYPE", f"{label}: forbidden type {t.__name__}")


def canonical_json_bytes(obj: Any) -> bytes:
    """Canonical sorted-key ASCII+LF JSON serialization (strict zero-float/subclass tree check)."""
    validate_strict_json_tree(obj, "canonical_json")
    return (
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n"
    ).encode("ascii")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Deterministic Pure-Z xorshift64* PRNG (zero random import)
# ---------------------------------------------------------------------------

def _xorshift64star_next(state: int) -> tuple[int, int]:
    s = state & MASK64
    s ^= (s >> 12) & MASK64
    s ^= (s << 25) & MASK64
    s ^= (s >> 27) & MASK64
    out = (s * 2685821657736338717) & MASK64
    return s, out


# ---------------------------------------------------------------------------
# Pillar 1 (exact): Algebraic Bijection vs Irreversible Erasure Proof
# ---------------------------------------------------------------------------

def step_r1_bijective_low(a: int, b: int) -> tuple[int, int]:
    a1 = (a ^ ((b & 1) | 2)) & MASK64
    b1 = (b ^ ((a1 & 1) | 2)) & MASK64
    return a1, b1


def inv_r1_bijective_low(a1: int, b1: int) -> tuple[int, int]:
    b = (b1 ^ ((a1 & 1) | 2)) & MASK64
    a = (a1 ^ ((b & 1) | 2)) & MASK64
    return a, b


def step_r3_bijective_high(a: int, b: int) -> tuple[int, int]:
    a1 = (a ^ ((~(b & 1)) & MASK64)) & MASK64
    b1 = (b ^ ((~(a1 & 1)) & MASK64)) & MASK64
    return a1, b1


def inv_r3_bijective_high(a1: int, b1: int) -> tuple[int, int]:
    b = (b1 ^ ((~(a1 & 1)) & MASK64)) & MASK64
    a = (a1 ^ ((~(b & 1)) & MASK64)) & MASK64
    return a, b


def step_r2_erase_low(a: int, b: int, ctr: int) -> tuple[int, int]:
    t = ((a & b) ^ (ctr & 3)) & MASK64
    a1 = (t | 2) & MASK64
    b1 = ((b & 1) ^ a1) & MASK64
    return a1, b1


def prove_step_algebra() -> dict[str, Any]:
    """Pure-Z proof of R1/R3 bijectivity, exact Hamming switching ratio, and R2 irreversibility."""
    witness_pairs: tuple[tuple[int, int], ...] = (
        (0x0123456789ABCDEF, 0xFEDCBA9876543210),
        (0x5555555555555555, 0xAAAAAAAAAAAAAAAA),
        (0, 0),
        (0, 1),
        (1, 0),
        (1, 1),
        (MASK64, 0),
        (MASK64, MASK64),
    )
    r1_flips: list[int] = []
    r3_flips: list[int] = []
    for a, b in witness_pairs:
        a1, b1 = step_r1_bijective_low(a, b)
        ra, rb = inv_r1_bijective_low(a1, b1)
        require_ok(ra == a and rb == b, "ALGEBRA_R1_NOT_BIJECTIVE", "R1 inverse mismatch")
        r1_flips.append((a ^ a1).bit_count() + (b ^ b1).bit_count())

        a3, b3 = step_r3_bijective_high(a, b)
        ra3, rb3 = inv_r3_bijective_high(a3, b3)
        require_ok(ra3 == a and rb3 == b, "ALGEBRA_R3_NOT_BIJECTIVE", "R3 inverse mismatch")
        r3_flips.append((a ^ a3).bit_count() + (b ^ b3).bit_count())

    # Explicit collision witness proving R2 is strictly many-to-one irreversible
    o1 = step_r2_erase_low(0x100, 0x200, 1)
    o2 = step_r2_erase_low(0x300, 0x400, 1)
    require_ok(o1 == o2, "ALGEBRA_R2_COLLISION_FAIL", "R2 collision proof failed")

    r1_mean = Fraction(sum(r1_flips), len(r1_flips))
    r3_mean = Fraction(sum(r3_flips), len(r3_flips))
    switch_ratio = r3_mean / r1_mean
    return {
        "witness_pair_count": len(witness_pairs),
        "r1_bijection_verified": True,
        "r1_erased_bits_per_step": 0,
        "r1_hamming_flips_min": min(r1_flips),
        "r1_hamming_flips_max": max(r1_flips),
        "r1_hamming_flips_mean_q": format_rational(r1_mean),
        "r3_bijection_verified": True,
        "r3_erased_bits_per_step": 0,
        "r3_hamming_flips_min": min(r3_flips),
        "r3_hamming_flips_max": max(r3_flips),
        "r3_hamming_flips_mean_q": format_rational(r3_mean),
        "r3_over_r1_switching_ratio_q": format_rational(switch_ratio),
        "r3_over_r1_switching_ratio_dec4": format_decimal(switch_ratio, 4),
        "r2_irreversible_collision_verified": True,
        "r2_collision_output": [o1[0], o1[1]],
        "r2_erased_bits_per_step_lower_bound": 2,
    }


# ---------------------------------------------------------------------------
# Snapshot Validation & Pillar 2 (Exact Per-Regime Silicon Power & Landauer)
# ---------------------------------------------------------------------------

def validate_snapshot_structure(snap: Any) -> dict[str, Any]:
    """Validate live pure-integer silicon snapshot structure (zero floats)."""
    require_ok(type(snap) is dict, "INVALID_SNAPSHOT_TYPE", "snapshot must be exact dict")
    require_str(snap.get("schema_version"), "schema_version", non_empty=True)
    require_ok(
        snap["schema_version"] == "aletheia.track_s61.rapl_landauer_snapshot.v1",
        "INVALID_SNAPSHOT_SCHEMA",
        "unexpected snapshot schema_version",
    )
    pl = snap.get("privacy_locks")
    require_ok(type(pl) is dict, "INVALID_PRIVACY_LOCKS", "privacy_locks must be exact dict")
    require_ok(
        require_bool(pl.get("audio_capture_accessed"), "audio_capture_accessed") is False
        and require_bool(pl.get("camera_accessed"), "camera_accessed") is False
        and require_bool(pl.get("display_modified"), "display_modified") is False,
        "PRIVACY_LOCK_VIOLATION",
        "all hardware privacy locks must be strictly False",
    )
    require_hex64(snap.get("microkernels_c_sha256"), "microkernels_c_sha256")
    require_ok(
        require_bool(snap.get("step_algebra_self_checked"), "step_algebra_self_checked") is True,
        "STEP_ALGEBRA_UNCHECKED",
        "harness step algebra self-check must be True",
    )
    channels = snap.get("channels")
    regimes = snap.get("regimes")
    labels = snap.get("regime_labels")
    dt_us = snap.get("dt_us")
    x_mat = snap.get("X_anonymous")

    require_ok(type(channels) is list and len(channels) == 20, "INVALID_CHANNELS", "expected 20 channels")
    for idx, ch in enumerate(channels):
        require_ok(type(ch) is dict, "INVALID_CHANNEL_ITEM", f"channel {idx} must be dict")
        require_exact_int(ch.get("idx"), f"ch[{idx}].idx", lo=idx, hi=idx)
        require_str(ch.get("name"), f"ch[{idx}].name", non_empty=True)
        require_str(ch.get("modality"), f"ch[{idx}].modality", non_empty=True)
        if idx < 5:
            require_ok(
                ch["name"] == EXPECTED_RAPL_CHANNELS[idx],
                "INVALID_RAPL_ORDER",
                f"expected RAPL channel {EXPECTED_RAPL_CHANNELS[idx]} at idx {idx}",
            )

    require_ok(type(regimes) is list and len(regimes) == 7, "INVALID_REGIMES", "expected 7 regimes")
    for r_idx, reg in enumerate(regimes):
        require_ok(type(reg) is dict, "INVALID_REGIME_ITEM", f"regime {r_idx} must be dict")
        require_exact_int(reg.get("idx"), f"reg[{r_idx}].idx", lo=r_idx, hi=r_idx)
        require_ok(
            require_str(reg.get("id"), f"reg[{r_idx}].id", non_empty=True) == EXPECTED_REGIME_IDS[r_idx],
            "INVALID_REGIME_ID",
            f"unexpected regime id at {r_idx}",
        )
        require_exact_int(reg.get("n_samples"), f"reg[{r_idx}].n_samples", lo=1, hi=2048)
        require_exact_int(reg.get("wall_ns"), f"reg[{r_idx}].wall_ns", lo=1)
        require_exact_int(reg.get("total_ops"), f"reg[{r_idx}].total_ops", lo=0)
        require_exact_int(reg.get("total_erased_bits"), f"reg[{r_idx}].total_erased_bits", lo=0)
        require_exact_int(reg.get("total_toggle_bits"), f"reg[{r_idx}].total_toggle_bits", lo=0)

    require_ok(type(x_mat) is list and len(x_mat) >= 21, "INVALID_X_MATRIX", "X_anonymous must have >= 21 rows")
    n_rows = len(x_mat)
    require_ok(
        type(labels) is list and len(labels) == n_rows and type(dt_us) is list and len(dt_us) == n_rows,
        "INVALID_ROW_LENGTHS",
        "regime_labels/dt_us length mismatch",
    )
    for t in range(n_rows):
        require_exact_int(labels[t], f"regime_labels[{t}]", lo=0, hi=6)
        require_exact_int(dt_us[t], f"dt_us[{t}]", lo=1, hi=10_000_000)
        row = x_mat[t]
        require_ok(type(row) is list and len(row) == 20, "INVALID_X_ROW", f"row {t} must have 20 ints")
        for c in range(20):
            if c < 5:
                require_exact_int(row[c], f"X[{t}][{c}]", lo=0)
            elif c == 5:
                require_exact_int(row[c], f"X[{t}][{c}]", lo=0, hi=150_000)
            else:
                require_exact_int(row[c], f"X[{t}][{c}]", lo=-1_000_000)
    return snap


def _two_sample_perm_pvalue_q(xs: list[Fraction], ys: list[Fraction], *, seed: int, reps: int) -> Fraction:
    """Exact deterministic two-sided permutation p-value p = (1 + ge) / (1 + reps)."""
    n_x = len(xs)
    n_y = len(ys)
    require_ok(n_x >= 1 and n_y >= 1, "EMPTY_PERM_SAMPLE", "permutation sample must be non-empty")
    obs = abs(Fraction(sum(xs), n_x) - Fraction(sum(ys), n_y))
    pooled = list(xs) + list(ys)
    n_tot = n_x + n_y
    total_sum = sum(pooled)
    state = seed
    ge_count = 0
    for _ in range(reps):
        arr = list(pooled)
        for i in range(n_tot - 1, 0, -1):
            state, rv = _xorshift64star_next(state)
            j = rv % (i + 1)
            arr[i], arr[j] = arr[j], arr[i]
        sum_x = sum(arr[:n_x])
        sum_y = total_sum - sum_x
        diff = abs(Fraction(sum_x, n_x) - Fraction(sum_y, n_y))
        if diff >= obs:
            ge_count += 1
    return Fraction(1 + ge_count, 1 + reps)


def evaluate_regime_physics_and_landauer(snap: dict[str, Any]) -> dict[str, Any]:
    """Compute exact pure-Q per-regime power, conservation residuals, pJ/op, and SI-2019 Landauer ratio."""
    x_mat: list[list[int]] = snap["X_anonymous"]
    labels: list[int] = snap["regime_labels"]
    dt_us: list[int] = snap["dt_us"]
    regimes: list[dict[str, Any]] = snap["regimes"]

    per_regime_rows: list[dict[str, Any]] = []
    # Keep per-tick exact power series for permutation tests
    core_w_series: dict[int, list[Fraction]] = {}
    uncore_w_series: dict[int, list[Fraction]] = {}
    pkg_dark_w_series: dict[int, list[Fraction]] = {}
    psys_w_series: dict[int, list[Fraction]] = {}
    summary_q: dict[int, dict[str, Fraction]] = {}

    for r_idx in range(7):
        reg = regimes[r_idx]
        idxs = [t for t, lbl in enumerate(labels) if lbl == r_idx]
        require_ok(len(idxs) == reg["n_samples"], "REGIME_SAMPLE_COUNT_MISMATCH", f"regime {r_idx} count mismatch")

        tot_dt = sum(dt_us[t] for t in idxs)
        duj_sums = [sum(x_mat[t][c] for t in idxs) for c in range(5)]
        pkg_w = Fraction(duj_sums[0], tot_dt)
        core_w = Fraction(duj_sums[1], tot_dt)
        uncore_w = Fraction(duj_sums[2], tot_dt)
        psys_w = Fraction(duj_sums[3], tot_dt)
        mmio_w = Fraction(duj_sums[4], tot_dt)

        pkg_dark_w = pkg_w - core_w - uncore_w
        psys_minus_pkg_w = psys_w - pkg_w
        pkg_minus_mmio_w = pkg_w - mmio_w

        mean_temp_pkg_mc = Fraction(sum(x_mat[t][5] for t in idxs), len(idxs))
        mean_temp_pkg_k = mean_temp_pkg_mc / 1000 + KELVIN_OFFSET_Q
        mean_freq_mhz = Fraction(sum(x_mat[t][c] for t in idxs for c in range(14, 18)), 4 * len(idxs) * 1000)
        mean_fan_cpu = Fraction(sum(x_mat[t][18] for t in idxs), len(idxs))
        mean_fan_gpu = Fraction(sum(x_mat[t][19] for t in idxs), len(idxs))

        core_w_series[r_idx] = [Fraction(x_mat[t][1], dt_us[t]) for t in idxs]
        uncore_w_series[r_idx] = [Fraction(x_mat[t][2], dt_us[t]) for t in idxs]
        pkg_dark_w_series[r_idx] = [Fraction(x_mat[t][0] - x_mat[t][1] - x_mat[t][2], dt_us[t]) for t in idxs]
        psys_w_series[r_idx] = [Fraction(x_mat[t][3], dt_us[t]) for t in idxs]

        wall_s_q = Fraction(reg["wall_ns"], 10**9)
        total_ops = reg["total_ops"]
        if total_ops > 0:
            ops_per_s = Fraction(total_ops, 1) / wall_s_q
            pkg_pj_per_op = (pkg_w / ops_per_s) * 10**12
            core_pj_per_op = (core_w / ops_per_s) * 10**12
        else:
            ops_per_s = Fraction(0, 1)
            pkg_pj_per_op = Fraction(0, 1)
            core_pj_per_op = Fraction(0, 1)

        summary_q[r_idx] = {
            "pkg_w": pkg_w,
            "core_w": core_w,
            "uncore_w": uncore_w,
            "psys_w": psys_w,
            "mmio_w": mmio_w,
            "pkg_dark_w": pkg_dark_w,
            "psys_minus_pkg_w": psys_minus_pkg_w,
            "pkg_minus_mmio_w": pkg_minus_mmio_w,
            "temp_pkg_k": mean_temp_pkg_k,
            "freq_mhz": mean_freq_mhz,
            "ops_per_s": ops_per_s,
            "pkg_pj_per_op": pkg_pj_per_op,
            "core_pj_per_op": core_pj_per_op,
        }

        per_regime_rows.append({
            "idx": r_idx,
            "id": reg["id"],
            "n_samples": len(idxs),
            "total_dt_us": tot_dt,
            "wall_ns": reg["wall_ns"],
            "total_ops": total_ops,
            "total_erased_bits": reg["total_erased_bits"],
            "total_toggle_bits": reg["total_toggle_bits"],
            "pkg_w_q": format_rational(q_quantize_floor(pkg_w, 6)),
            "pkg_w_dec3": format_decimal(pkg_w, 3),
            "core_w_q": format_rational(q_quantize_floor(core_w, 6)),
            "core_w_dec3": format_decimal(core_w, 3),
            "uncore_w_q": format_rational(q_quantize_floor(uncore_w, 6)),
            "uncore_w_dec3": format_decimal(uncore_w, 3),
            "psys_w_q": format_rational(q_quantize_floor(psys_w, 6)),
            "psys_w_dec3": format_decimal(psys_w, 3),
            "mmio_w_q": format_rational(q_quantize_floor(mmio_w, 6)),
            "mmio_w_dec3": format_decimal(mmio_w, 3),
            "pkg_in_package_dark_w_q": format_rational(q_quantize_floor(pkg_dark_w, 6)),
            "pkg_in_package_dark_w_dec3": format_decimal(pkg_dark_w, 3),
            "psys_minus_pkg_w_q": format_rational(q_quantize_floor(psys_minus_pkg_w, 6)),
            "psys_minus_pkg_w_dec3": format_decimal(psys_minus_pkg_w, 3),
            "pkg_minus_mmio_w_q": format_rational(q_quantize_floor(pkg_minus_mmio_w, 6)),
            "pkg_minus_mmio_w_dec3": format_decimal(pkg_minus_mmio_w, 3),
            "mean_temp_pkg_k_q": format_rational(q_quantize_floor(mean_temp_pkg_k, 4)),
            "mean_temp_pkg_k_dec3": format_decimal(mean_temp_pkg_k, 3),
            "mean_freq_mhz_q": format_rational(q_quantize_floor(mean_freq_mhz, 3)),
            "mean_freq_mhz_dec1": format_decimal(mean_freq_mhz, 1),
            "mean_fan_cpu_rpm_dec1": format_decimal(mean_fan_cpu, 1),
            "mean_fan_gpu_rpm_dec1": format_decimal(mean_fan_gpu, 1),
            "ops_per_sec_dec0": format_decimal(ops_per_s, 0),
            "pkg_pj_per_op_q": format_rational(q_quantize_floor(pkg_pj_per_op, 6)),
            "pkg_pj_per_op_dec4": format_decimal(pkg_pj_per_op, 4),
            "core_pj_per_op_q": format_rational(q_quantize_floor(core_pj_per_op, 6)),
            "core_pj_per_op_dec4": format_decimal(core_pj_per_op, 4),
        })

    # Exact SI-2019 Landauer limit on R2_ERASE_DESTRUCTIVE_LOW_H
    r2_reg = regimes[2]
    r2_erased = r2_reg["total_erased_bits"]
    require_ok(r2_erased > 0, "ZERO_ERASED_BITS_R2", "R2 must erase > 0 bits")
    r2_wall_s = Fraction(r2_reg["wall_ns"], 10**9)
    r2_t_k = summary_q[2]["temp_pkg_k"]
    require_ok(r2_t_k > 0, "INVALID_TEMP_RANGE", "R2 package temperature must be > 0 K")
    kt_ln2_lo = KB_SI_2019_Q * r2_t_k * LN2_LO_Q
    kt_ln2_hi = KB_SI_2019_Q * r2_t_k * LN2_HI_Q
    r2_core_j_total = summary_q[2]["core_w"] * r2_wall_s
    r2_pkg_j_total = summary_q[2]["pkg_w"] * r2_wall_s
    r2_net_core_w = summary_q[2]["core_w"] - summary_q[0]["core_w"]
    r2_net_core_j = (r2_net_core_w if r2_net_core_w > 0 else Fraction(0, 1)) * r2_wall_s

    # eta = E_measured / (N_erased * k_B * T * ln 2) -> conservative [lo, hi] interval
    denom_hi = r2_erased * kt_ln2_hi
    denom_lo = r2_erased * kt_ln2_lo
    eta_gross_core_lo = r2_core_j_total / denom_hi
    eta_gross_core_hi = r2_core_j_total / denom_lo
    eta_gross_pkg_lo = r2_pkg_j_total / denom_hi
    eta_gross_pkg_hi = r2_pkg_j_total / denom_lo
    eta_net_core_lo = r2_net_core_j / denom_hi
    eta_net_core_hi = r2_net_core_j / denom_lo

    # Exact Landauer bit-capacity upper bound of R2 package energy: E / (k_B T ln 2)
    r2_pkg_landauer_bits_lo = int(r2_pkg_j_total // kt_ln2_hi)
    r2_pkg_landauer_bits_hi = int((r2_pkg_j_total.numerator * kt_ln2_lo.denominator + (r2_pkg_j_total.denominator * kt_ln2_lo.numerator - 1)) // (r2_pkg_j_total.denominator * kt_ln2_lo.numerator))

    # Pairwise physical contrasts & exact deterministic permutation tests
    r2_vs_r1_core_diff = summary_q[2]["core_w"] - summary_q[1]["core_w"]
    r3_vs_r1_core_diff = summary_q[3]["core_w"] - summary_q[1]["core_w"]
    r4_vs_r1_core_diff = summary_q[4]["core_w"] - summary_q[1]["core_w"]
    r4_vs_r1_freq_diff = summary_q[4]["freq_mhz"] - summary_q[1]["freq_mhz"]
    r5_vs_r4_core_diff = summary_q[5]["core_w"] - summary_q[4]["core_w"]
    r6_vs_r1_uncore_diff = summary_q[6]["uncore_w"] - summary_q[1]["uncore_w"]
    r6_vs_r1_pkg_dark_diff = summary_q[6]["pkg_dark_w"] - summary_q[1]["pkg_dark_w"]
    r6_vs_r4_pkg_dark_diff = summary_q[6]["pkg_dark_w"] - summary_q[4]["pkg_dark_w"]
    r6_vs_r1_psys_diff = summary_q[6]["psys_w"] - summary_q[1]["psys_w"]

    r4_pj = summary_q[4]["core_pj_per_op"]
    r5_pj = summary_q[5]["core_pj_per_op"]
    r4_over_r5_pj_ratio = (r4_pj / r5_pj) if r5_pj > 0 else Fraction(0, 1)

    p_r2_vs_r1_core = _two_sample_perm_pvalue_q(core_w_series[2], core_w_series[1], seed=PRNG_SEED_PERM ^ 1, reps=PERM_TEST_REPS)
    p_r3_vs_r1_core = _two_sample_perm_pvalue_q(core_w_series[3], core_w_series[1], seed=PRNG_SEED_PERM ^ 2, reps=PERM_TEST_REPS)
    p_r4_vs_r1_core = _two_sample_perm_pvalue_q(core_w_series[4], core_w_series[1], seed=PRNG_SEED_PERM ^ 3, reps=PERM_TEST_REPS)
    p_r6_vs_r1_uncore = _two_sample_perm_pvalue_q(uncore_w_series[6], uncore_w_series[1], seed=PRNG_SEED_PERM ^ 4, reps=PERM_TEST_REPS)
    p_r6_vs_r1_pkg_dark = _two_sample_perm_pvalue_q(pkg_dark_w_series[6], pkg_dark_w_series[1], seed=PRNG_SEED_PERM ^ 5, reps=PERM_TEST_REPS)
    p_r6_vs_r4_pkg_dark = _two_sample_perm_pvalue_q(pkg_dark_w_series[6], pkg_dark_w_series[4], seed=PRNG_SEED_PERM ^ 6, reps=PERM_TEST_REPS)
    p_r6_vs_r1_psys = _two_sample_perm_pvalue_q(psys_w_series[6], psys_w_series[1], seed=PRNG_SEED_PERM ^ 7, reps=PERM_TEST_REPS)

    psys_scale_obstruction = summary_q[4]["psys_w"] < summary_q[4]["pkg_w"]
    landauer_obstruction_confirmed = int(eta_gross_core_lo) >= 10**6

    return {
        "per_regime": per_regime_rows,
        "landauer_r2_bridge": {
            "r2_temp_pkg_k_q": format_rational(q_quantize_floor(r2_t_k, 4)),
            "r2_temp_pkg_k_dec3": format_decimal(r2_t_k, 3),
            "r2_erased_bits": r2_erased,
            "r2_core_j_dec6": format_decimal(r2_core_j_total, 6),
            "r2_pkg_j_dec6": format_decimal(r2_pkg_j_total, 6),
            "eta_gross_core_floor_int": int(eta_gross_core_lo),
            "eta_gross_core_ceil_int": int(eta_gross_core_hi) + 1,
            "eta_gross_pkg_floor_int": int(eta_gross_pkg_lo),
            "eta_gross_pkg_ceil_int": int(eta_gross_pkg_hi) + 1,
            "eta_net_core_floor_int": int(eta_net_core_lo),
            "eta_net_core_ceil_int": int(eta_net_core_hi) + 1,
            "r2_pkg_landauer_bits_lo": r2_pkg_landauer_bits_lo,
            "r2_pkg_landauer_bits_hi": r2_pkg_landauer_bits_hi,
            "h1_cmos_landauer_obstruction_confirmed": landauer_obstruction_confirmed,
        },
        "pairwise_contrasts": {
            "perm_reps": PERM_TEST_REPS,
            "r2_minus_r1_core_w_q": format_rational(q_quantize_floor(r2_vs_r1_core_diff, 6)),
            "r2_minus_r1_core_w_dec3": format_decimal(r2_vs_r1_core_diff, 3),
            "p_r2_vs_r1_core_q": format_rational(p_r2_vs_r1_core),
            "r3_minus_r1_core_w_q": format_rational(q_quantize_floor(r3_vs_r1_core_diff, 6)),
            "r3_minus_r1_core_w_dec3": format_decimal(r3_vs_r1_core_diff, 3),
            "p_r3_vs_r1_core_q": format_rational(p_r3_vs_r1_core),
            "r4_minus_r1_core_w_q": format_rational(q_quantize_floor(r4_vs_r1_core_diff, 6)),
            "r4_minus_r1_core_w_dec3": format_decimal(r4_vs_r1_core_diff, 3),
            "p_r4_vs_r1_core_q": format_rational(p_r4_vs_r1_core),
            "r4_minus_r1_freq_mhz_q": format_rational(q_quantize_floor(r4_vs_r1_freq_diff, 3)),
            "r4_minus_r1_freq_mhz_dec1": format_decimal(r4_vs_r1_freq_diff, 1),
            "r5_minus_r4_core_w_q": format_rational(q_quantize_floor(r5_vs_r4_core_diff, 6)),
            "r5_minus_r4_core_w_dec3": format_decimal(r5_vs_r4_core_diff, 3),
            "r4_fp64_over_r5_vnni_pj_per_op_q": format_rational(q_quantize_floor(r4_over_r5_pj_ratio, 6)),
            "r4_fp64_over_r5_vnni_pj_per_op_dec3": format_decimal(r4_over_r5_pj_ratio, 3),
            "r6_minus_r1_uncore_w_q": format_rational(q_quantize_floor(r6_vs_r1_uncore_diff, 6)),
            "r6_minus_r1_uncore_w_dec3": format_decimal(r6_vs_r1_uncore_diff, 3),
            "p_r6_vs_r1_uncore_q": format_rational(p_r6_vs_r1_uncore),
            "r6_minus_r1_pkg_dark_w_q": format_rational(q_quantize_floor(r6_vs_r1_pkg_dark_diff, 6)),
            "r6_minus_r1_pkg_dark_w_dec3": format_decimal(r6_vs_r1_pkg_dark_diff, 3),
            "p_r6_vs_r1_pkg_dark_q": format_rational(p_r6_vs_r1_pkg_dark),
            "r6_minus_r4_pkg_dark_w_q": format_rational(q_quantize_floor(r6_vs_r4_pkg_dark_diff, 6)),
            "r6_minus_r4_pkg_dark_w_dec3": format_decimal(r6_vs_r4_pkg_dark_diff, 3),
            "p_r6_vs_r4_pkg_dark_q": format_rational(p_r6_vs_r4_pkg_dark),
            "r6_minus_r1_psys_w_q": format_rational(q_quantize_floor(r6_vs_r1_psys_diff, 6)),
            "r6_minus_r1_psys_w_dec3": format_decimal(r6_vs_r1_psys_diff, 3),
            "p_r6_vs_r1_psys_q": format_rational(p_r6_vs_r1_psys),
            "psys_vendor_scale_obstruction_detected": psys_scale_obstruction,
        },
    }


# ---------------------------------------------------------------------------
# Pillar 3 (exact coordinate-free Stage-A/B): Blind R^2, Schur, Inertia & Gauge
# ---------------------------------------------------------------------------

def _centered_gram_q(cols: list[list[Fraction]]) -> tuple[list[int], list[int], list[list[Fraction]]]:
    """Exact pure-Q centered Gram matrix and active/zero-variance channel indices."""
    d_tot = len(cols)
    t_len = len(cols[0])
    centered: list[list[Fraction]] = []
    active: list[int] = []
    zero_var: list[int] = []
    for j in range(d_tot):
        col = cols[j]
        mean_j = Fraction(sum(col), t_len)
        c_col = [v - mean_j for v in col]
        var_num = sum(v * v for v in c_col)
        if var_num == 0:
            zero_var.append(j)
        else:
            active.append(j)
            centered.append(c_col)
    m = len(active)
    gram: list[list[Fraction]] = [[Fraction(0, 1)] * m for _ in range(m)]
    for i in range(m):
        ci = centered[i]
        gram[i][i] = sum(v * v for v in ci)
        for j in range(i + 1, m):
            cj = centered[j]
            dot = sum(a * b for a, b in zip(ci, cj))
            gram[i][j] = dot
            gram[j][i] = dot
    return active, zero_var, gram


def _r2_matrix_from_gram(gram: list[list[Fraction]]) -> tuple[list[list[Fraction]], Fraction]:
    m = len(gram)
    r2: list[list[Fraction]] = [[Fraction(0, 1)] * m for _ in range(m)]
    off_sum = Fraction(0, 1)
    off_cnt = 0
    for i in range(m):
        r2[i][i] = Fraction(1, 1)
        gii = gram[i][i]
        for j in range(i + 1, m):
            val = (gram[i][j] * gram[i][j]) / (gii * gram[j][j])
            r2[i][j] = val
            r2[j][i] = val
            off_sum += val
            off_cnt += 1
    mean_off = (off_sum / off_cnt) if off_cnt > 0 else Fraction(0, 1)
    return r2, mean_off


def _blind_connected_components(r2: list[list[Fraction]], thresh: Fraction) -> tuple[list[int], Fraction]:
    """Deterministic coordinate-free connected components on R^2 >= thresh + Newman modularity Q."""
    m = len(r2)
    labels = [-1] * m
    comp_id = 0
    for start in range(m):
        if labels[start] != -1:
            continue
        stack = [start]
        labels[start] = comp_id
        while stack:
            u = stack.pop()
            for v in range(m):
                if labels[v] == -1 and r2[u][v] >= thresh:
                    labels[v] = comp_id
                    stack.append(v)
        comp_id += 1

    # Exact weighted Newman modularity on off-diagonal R^2 adjacency
    deg = [sum(r2[i][j] for j in range(m) if j != i) for i in range(m)]
    two_m = sum(deg)
    if two_m == 0:
        return labels, Fraction(0, 1)
    q_sum = Fraction(0, 1)
    for i in range(m):
        for j in range(m):
            if i != j and labels[i] == labels[j]:
                q_sum += r2[i][j] - (deg[i] * deg[j]) / two_m
    return labels, q_sum / two_m


def _invert_spd_q(mat: list[list[Fraction]]) -> list[list[Fraction]]:
    """Exact pure-Q Gauss-Jordan inversion for SPD ridge-regularized Gram block."""
    n = len(mat)
    aug = [list(mat[i]) + [Fraction(1 if i == j else 0, 1) for j in range(n)] for i in range(n)]
    for col in range(n):
        piv = col
        while piv < n and aug[piv][col] == 0:
            piv += 1
        require_ok(piv < n, "SINGULAR_MATRIX", "cannot invert singular block")
        if piv != col:
            aug[col], aug[piv] = aug[piv], aug[col]
        pval = aug[col][col]
        row_c = aug[col]
        for j in range(col, 2 * n):
            row_c[j] /= pval
        for r in range(n):
            if r == col:
                continue
            fac = aug[r][col]
            if fac != 0:
                row_r = aug[r]
                for j in range(col, 2 * n):
                    row_r[j] -= fac * row_c[j]
    return [row[n:] for row in aug]


def _symmetric_inertia_q(mat: list[list[Fraction]]) -> list[int]:
    """Exact Sylvester inertia [n_pos, n_zero, n_neg] via pure-Q symmetric congruence (Bunch-Kaufman 1x1/2x2)."""
    n = len(mat)
    a = [list(row) for row in mat]
    pos = zero = neg = 0
    k = 0
    while k < n:
        piv = -1
        for i in range(k, n):
            if a[i][i] != 0:
                piv = i
                break
        if piv != -1:
            if piv != k:
                a[k], a[piv] = a[piv], a[k]
                for r in range(n):
                    a[r][k], a[r][piv] = a[r][piv], a[r][k]
            d = a[k][k]
            if d > 0:
                pos += 1
            else:
                neg += 1
            for i in range(k + 1, n):
                fac = a[i][k] / d
                if fac != 0:
                    for j in range(i, n):
                        val = a[i][j] - fac * a[k][j]
                        a[i][j] = val
                        a[j][i] = val
            k += 1
        else:
            # Find non-zero off-diagonal 2x2 hyperbolic pivot (always contributes +1, -1)
            found_pair: tuple[int, int] | None = None
            for i in range(k, n):
                for j in range(i + 1, n):
                    if a[i][j] != 0:
                        found_pair = (i, j)
                        break
                if found_pair is not None:
                    break
            if found_pair is None:
                zero += n - k
                break
            p1, p2 = found_pair
            if p1 != k:
                a[k], a[p1] = a[p1], a[k]
                for r in range(n):
                    a[r][k], a[r][p1] = a[r][p1], a[r][k]
                if p2 == k:
                    p2 = p1
            if p2 != k + 1:
                a[k + 1], a[p2] = a[p2], a[k + 1]
                for r in range(n):
                    a[r][k + 1], a[r][p2] = a[r][p2], a[r][k + 1]
            bval = a[k][k + 1]
            pos += 1
            neg += 1
            for i in range(k + 2, n):
                u1 = a[i][k]
                u2 = a[i][k + 1]
                for j in range(i, n):
                    v1 = a[j][k]
                    v2 = a[j][k + 1]
                    val = a[i][j] - (u1 * v2 + u2 * v1) / bval
                    a[i][j] = val
                    a[j][i] = val
            k += 2
    return [pos, zero, neg]


def _exact_schur_diagnostics_q(
    gram: list[list[Fraction]],
    a_pos: list[int],
    b_pos: list[int],
    ridge: Fraction,
) -> dict[str, Any]:
    """Square-root-free exact scale-invariant Schur complement S_{A|B} diagnostics."""
    na = len(a_pos)
    nb = len(b_pos)
    require_ok(na >= 2 and nb >= 1, "INVALID_SCHUR_PARTITION", "need |A| >= 2 and |B| >= 1")

    g_aa = [[gram[i][j] for j in a_pos] for i in a_pos]
    g_ab = [[gram[i][j] for j in b_pos] for i in a_pos]
    g_bb_reg = [
        [gram[b_pos[i]][b_pos[j]] + (ridge * gram[b_pos[i]][b_pos[i]] if i == j else Fraction(0, 1)) for j in range(nb)]
        for i in range(nb)
    ]
    g_bb_inv = _invert_spd_q(g_bb_reg)

    # S_tilde = G_AA - G_AB * G_BB_reg^{-1} * G_BA
    ab_inv = [
        [sum(g_ab[i][k] * g_bb_inv[k][j] for k in range(nb)) for j in range(nb)]
        for i in range(na)
    ]
    s_tilde = [
        [g_aa[i][j] - sum(ab_inv[i][k] * g_ab[j][k] for k in range(nb)) for j in range(na)]
        for i in range(na)
    ]

    inertia = _symmetric_inertia_q(s_tilde)
    for i in range(na):
        require_ok(s_tilde[i][i] > 0, "SCHUR_NON_POS_DIAG", "Schur complement diagonal must be > 0")
    eta_terms = [s_tilde[i][i] / g_aa[i][i] for i in range(na)]
    eta_mean = Fraction(sum(eta_terms), na)

    raw_r2_sum = Fraction(0, 1)
    res_rho2_sum = Fraction(0, 1)
    pair_cnt = 0
    for i in range(na):
        sii = s_tilde[i][i]
        for j in range(i + 1, na):
            raw_r2_sum += (g_aa[i][j] * g_aa[i][j]) / (g_aa[i][i] * g_aa[j][j])
            res_rho2_sum += (s_tilde[i][j] * s_tilde[i][j]) / (sii * s_tilde[j][j])
            pair_cnt += 1
    raw_r2_mean = raw_r2_sum / pair_cnt
    res_rho2_mean = res_rho2_sum / pair_cnt
    return {
        "na": na,
        "nb": nb,
        "inertia": inertia,
        "eta_mean": eta_mean,
        "raw_r2_mean": raw_r2_mean,
        "res_rho2_mean": res_rho2_mean,
    }


def _ari_exact_q(lbl_a: list[int], lbl_b: list[int]) -> Fraction:
    """Exact pure-Q Adjusted Rand Index between two labelings of equal length."""
    n = len(lbl_a)
    require_ok(len(lbl_b) == n and n >= 2, "INVALID_ARI_INPUT", "ARI needs equal lengths >= 2")
    ca: dict[int, int] = {}
    cb: dict[int, int] = {}
    cab: dict[tuple[int, int], int] = {}
    for a, b in zip(lbl_a, lbl_b):
        ca[a] = ca.get(a, 0) + 1
        cb[b] = cb.get(b, 0) + 1
        cab[(a, b)] = cab.get((a, b), 0) + 1

    def _c2(k: int) -> int:
        return k * (k - 1) // 2

    sum_ab = sum(_c2(v) for v in cab.values())
    sum_a = sum(_c2(v) for v in ca.values())
    sum_b = sum(_c2(v) for v in cb.values())
    tot = _c2(n)
    exp = Fraction(sum_a * sum_b, tot)
    mx = Fraction(sum_a + sum_b, 2)
    denom = mx - exp
    if denom == 0:
        return Fraction(1, 1) if sum_ab == mx else Fraction(0, 1)
    return (Fraction(sum_ab, 1) - exp) / denom


def _check_gauge_zero_exact(
    max_r2_diff: Fraction,
    gauge_eta_diff: Fraction,
    gauge_res_diff: Fraction,
    g_inertia: list[int],
    inertia: list[int],
    gauge_ari: Fraction,
    g_mod: Fraction,
    mod: Fraction,
    g_mean: Fraction,
    mean: Fraction,
) -> bool:
    return (
        max_r2_diff == 0
        and gauge_eta_diff == 0
        and gauge_res_diff == 0
        and g_inertia == inertia
        and gauge_ari == 1
        and g_mod == mod
        and g_mean == mean
    )


def _pair_r2_or_zero(r2_mat: list[list[Fraction]], pos_map: dict[int, int], idx_a: int, idx_b: int) -> Fraction:
    if idx_a in pos_map and idx_b in pos_map:
        return r2_mat[pos_map[idx_a]][pos_map[idx_b]]
    return Fraction(0, 1)


def evaluate_blind_schur_tomography(
    snap: dict[str, Any],
    *,
    gauge_perm: list[int] | None = None,
) -> dict[str, Any]:
    """Coordinate-free Stage-A/B blind tomography on stripped X_anonymous + Stage-C evaluation."""
    x_mat: list[list[int]] = snap["X_anonymous"]
    n_rows = len(x_mat)
    n_cols = len(x_mat[0])
    cols_q = [[Fraction(x_mat[t][j], 1) for t in range(n_rows)] for j in range(n_cols)]

    active, zero_var, gram = _centered_gram_q(cols_q)
    r2_mat, mean_off_r2 = _r2_matrix_from_gram(gram)
    blind_labels, blind_mod_q = _blind_connected_components(r2_mat, BLIND_R2_EDGE_THRESHOLD_Q)

    # Physical partition derived strictly from snapshot modalities (Stage-C held-out labels)
    channels = snap["channels"]
    active_pos_by_orig = {orig_j: pos for pos, orig_j in enumerate(active)}
    phys_rapl_b = [active_pos_by_orig[j] for j in active if channels[j]["modality"] == "intel_rapl_energy"]
    phys_non_rapl_a = [active_pos_by_orig[j] for j in active if channels[j]["modality"] != "intel_rapl_energy"]
    schur_phys = _exact_schur_diagnostics_q(gram, phys_non_rapl_a, phys_rapl_b, SCHUR_RIDGE_LAMBDA_Q)

    # Blind evaluation: check best blind cluster's precision/recall on intel_rapl channels
    rapl_pos_set = set(phys_rapl_b)
    best_prec = Fraction(0, 1)
    best_rec = Fraction(0, 1)
    best_cid = -1
    for cid in sorted(set(blind_labels)):
        members = {p for p, c in enumerate(blind_labels) if c == cid}
        inter = len(members & rapl_pos_set)
        prec = Fraction(inter, len(members))
        rec = Fraction(inter, len(rapl_pos_set)) if rapl_pos_set else Fraction(0, 1)
        if (rec, prec) > (best_rec, best_prec):
            best_rec = rec
            best_prec = prec
            best_cid = cid

    # Stage-A Exact Gauge Invariance Test: deterministic column permutation + positive rational affine scaling
    perm = [(j * 7 + 3) % n_cols for j in range(n_cols)] if gauge_perm is None else list(gauge_perm)
    require_ok(len(set(perm)) == n_cols, "GAUGE_PERM_INVALID", "gauge permutation must be bijective")
    scales = [Fraction(2 * j + 3, (j % 5) + 2) for j in range(n_cols)]
    shifts = [Fraction((j * 17) - 50, 3) for j in range(n_cols)]
    cols_gauged = [
        [scales[orig_j] * cols_q[orig_j][t] + shifts[orig_j] for t in range(n_rows)]
        for orig_j in perm
    ]
    g_active, g_zero_var, g_gram = _centered_gram_q(cols_gauged)
    g_r2, g_mean_off_r2 = _r2_matrix_from_gram(g_gram)
    g_blind_labels, g_blind_mod_q = _blind_connected_components(g_r2, BLIND_R2_EDGE_THRESHOLD_Q)

    # Map original active index -> gauged active position
    orig_of_g_pos = [perm[gj] for gj in g_active]
    g_pos_by_orig = {orig_j: gp for gp, orig_j in enumerate(orig_of_g_pos)}
    require_ok(set(orig_of_g_pos) == set(active), "GAUGE_ACTIVE_DRIFT", "active set drifted under gauge")
    max_r2_diff = Fraction(0, 1)
    for i_p, orig_i in enumerate(active):
        gi = g_pos_by_orig[orig_i]
        for j_p, orig_j in enumerate(active):
            gj = g_pos_by_orig[orig_j]
            diff = abs(r2_mat[i_p][j_p] - g_r2[gi][gj])
            if diff > max_r2_diff:
                max_r2_diff = diff
    aligned_g_labels = [g_blind_labels[g_pos_by_orig[orig_i]] for orig_i in active]
    gauge_ari = _ari_exact_q(blind_labels, aligned_g_labels)

    g_phys_a = [g_pos_by_orig[active[p]] for p in phys_non_rapl_a]
    g_phys_b = [g_pos_by_orig[active[p]] for p in phys_rapl_b]
    g_schur_phys = _exact_schur_diagnostics_q(g_gram, g_phys_a, g_phys_b, SCHUR_RIDGE_LAMBDA_Q)
    gauge_eta_diff = abs(schur_phys["eta_mean"] - g_schur_phys["eta_mean"])
    gauge_res_diff = abs(schur_phys["res_rho2_mean"] - g_schur_phys["res_rho2_mean"])
    gauge_exact_zero = _check_gauge_zero_exact(
        max_r2_diff,
        gauge_eta_diff,
        gauge_res_diff,
        g_schur_phys["inertia"],
        schur_phys["inertia"],
        gauge_ari,
        g_blind_mod_q,
        blind_mod_q,
        g_mean_off_r2,
        mean_off_r2,
    )
    require_ok(gauge_exact_zero, "GAUGE_INVARIANCE_BROKEN", "Stage-A gauge invariance must be exact 0")

    # Exact Circular-Shift Null on integer active columns (pure int Gram for speed!)
    int_active_cols: list[list[int]] = []
    int_var_denom: list[int] = []
    for orig_j in active:
        raw_col = [x_mat[t][orig_j] for t in range(n_rows)]
        s_col = sum(raw_col)
        c_col = [n_rows * v - s_col for v in raw_col]
        int_active_cols.append(c_col)
        int_var_denom.append(sum(v * v for v in c_col))
    m_act = len(active)
    off_pairs = m_act * (m_act - 1) // 2
    state = PRNG_SEED_CIRC
    ge_circ = 0
    for _ in range(CIRC_SHIFT_REPS):
        shifted: list[list[int]] = []
        for idx_c in range(m_act):
            state, rv = _xorshift64star_next(state)
            off = 1 + (rv % (n_rows - 1))
            col = int_active_cols[idx_c]
            shifted.append(col[off:] + col[:off])
        r2_sum = Fraction(0, 1)
        for i in range(m_act):
            ci = shifted[i]
            vi = int_var_denom[i]
            for j in range(i + 1, m_act):
                dot = sum(a * b for a, b in zip(ci, shifted[j]))
                r2_sum += Fraction(dot * dot, vi * int_var_denom[j])
        if (r2_sum / off_pairs) >= mean_off_r2:
            ge_circ += 1
    circ_p_q = Fraction(1 + ge_circ, 1 + CIRC_SHIFT_REPS)

    # Extract exact psys-vs-package & uncore-vs-package R^2 (invariant to psys vendor scale!)
    psys_pkg_r2 = _pair_r2_or_zero(r2_mat, active_pos_by_orig, 0, 3)
    uncore_pkg_r2 = _pair_r2_or_zero(r2_mat, active_pos_by_orig, 0, 2)

    return {
        "n_rows": n_rows,
        "n_cols": n_cols,
        "active_indices": active,
        "zero_var_indices": zero_var,
        "mean_offdiag_r2_q": format_rational(q_quantize_floor(mean_off_r2, 6)),
        "mean_offdiag_r2_dec4": format_decimal(mean_off_r2, 4),
        "psys_vs_pkg_r2_q": format_rational(q_quantize_floor(psys_pkg_r2, 6)),
        "psys_vs_pkg_r2_dec4": format_decimal(psys_pkg_r2, 4),
        "uncore_vs_pkg_r2_q": format_rational(q_quantize_floor(uncore_pkg_r2, 6)),
        "uncore_vs_pkg_r2_dec4": format_decimal(uncore_pkg_r2, 4),
        "blind_r2_threshold_q": format_rational(BLIND_R2_EDGE_THRESHOLD_Q),
        "blind_cluster_labels": blind_labels,
        "blind_cluster_count": len(set(blind_labels)),
        "blind_modularity_q": format_rational(q_quantize_floor(blind_mod_q, 6)),
        "blind_modularity_dec4": format_decimal(blind_mod_q, 4),
        "blind_rapl_best_cluster_id": best_cid,
        "blind_rapl_precision_q": format_rational(best_prec),
        "blind_rapl_recall_q": format_rational(best_rec),
        "physical_partition_schur": {
            "ridge_lambda_q": format_rational(SCHUR_RIDGE_LAMBDA_Q),
            "a_active_positions": phys_non_rapl_a,
            "b_active_positions": phys_rapl_b,
            "inertia": schur_phys["inertia"],
            "mean_unexplained_variance_eta_q": format_rational(q_quantize_floor(schur_phys["eta_mean"], 6)),
            "mean_unexplained_variance_eta_dec4": format_decimal(schur_phys["eta_mean"], 4),
            "mean_raw_offdiag_r2_q": format_rational(q_quantize_floor(schur_phys["raw_r2_mean"], 6)),
            "mean_raw_offdiag_r2_dec4": format_decimal(schur_phys["raw_r2_mean"], 4),
            "mean_residual_rho2_q": format_rational(q_quantize_floor(schur_phys["res_rho2_mean"], 6)),
            "mean_residual_rho2_dec4": format_decimal(schur_phys["res_rho2_mean"], 4),
        },
        "stage_a_gauge_invariance": {
            "exact_zero_deviation": gauge_exact_zero,
            "max_r2_diff_q": format_rational(max_r2_diff),
            "eta_diff_q": format_rational(gauge_eta_diff),
            "res_rho2_diff_q": format_rational(gauge_res_diff),
            "blind_cluster_gauge_ari_q": format_rational(gauge_ari),
            "inertia_exact_match": g_schur_phys["inertia"] == schur_phys["inertia"],
        },
        "circular_shift_null": {
            "reps": CIRC_SHIFT_REPS,
            "ge_count": ge_circ,
            "p_mean_offdiag_r2_q": format_rational(circ_p_q),
            "p_mean_offdiag_r2_dec4": format_decimal(circ_p_q, 4),
        },
    }


def build_certificate_from_snapshot(snap: Any, *, mlos_receipt_sha256: str | None = None) -> dict[str, Any]:
    """Build canonical pure-Z/Q Track S61 certificate deterministically from live snapshot."""
    validated = validate_snapshot_structure(snap)
    snap_bytes = canonical_json_bytes(validated)
    snap_sha = sha256_hex(snap_bytes)
    x_anon_sha = sha256_hex(canonical_json_bytes(validated["X_anonymous"]))
    if mlos_receipt_sha256 is not None:
        require_hex64(mlos_receipt_sha256, "mlos_receipt_sha256")

    p1 = prove_step_algebra()
    p2 = evaluate_regime_physics_and_landauer(validated)
    p3 = evaluate_blind_schur_tomography(validated)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "measured_live_silicon": True,
        "privacy_locks": dict(validated["privacy_locks"]),
        "snapshot_sha256": snap_sha,
        "x_anonymous_sha256": x_anon_sha,
        "microkernels_c_sha256": validated["microkernels_c_sha256"],
        "mlos_receipt_sha256": mlos_receipt_sha256 if mlos_receipt_sha256 is not None else "0" * 64,
        "pillar1_step_algebra": p1,
        "pillar2_regime_physics_and_landauer": p2,
        "pillar3_blind_schur_tomography": p3,
    }
    payload_sha = sha256_hex(canonical_json_bytes(payload))
    cert_envelope_body = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": payload_sha,
        "payload": payload,
    }
    cert_sha = sha256_hex(canonical_json_bytes(cert_envelope_body))
    return {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": payload_sha,
        "certificate_sha256": cert_sha,
        "payload": payload,
    }
