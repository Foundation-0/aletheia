#!/usr/bin/env python3
"""Track S102 Pure-Stdlib Exact Integer/Rational Oracle:
Drosophila MaleCNS v1.0 Whole-CNS Connectome, Central-Complex Ring Attractor,
Dale's-Law Signed Operators, Schur Complement / Krein Inertia, and Wave-9
Cross-Portal Engineering Synthesis.

Zero production floats, zero third-party dependencies, runs cleanly under
`python3 -I -B`. Consumes the deterministic pure-integer anchor
`s102_malecns_anchor.json` extracted from the external FlyEM MaleCNS v1.0
`.feather` dataset (zero raw dataset copies inside `expedition/`).
"""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

TRACK_ID = "S102"
SCHEMA_VERSION = "s102-malecns-connectome-cert-v1"
ANCHOR_SCHEMA_VERSION = "s102-malecns-anchor-v1"
ORACLE_CLASS = "EXACT_INTEGER_RATIONAL_AND_LEAN4"
NOVELTY_CLASSIFICATION = "N0_N1_CONNECTOME_EXACT_OPERATORS"

TRACK_DIR = Path(__file__).resolve().parent
ANCHOR_FILENAME = "s102_malecns_anchor.json"
DEFAULT_CERT_FILENAME = "s102_malecns_connectome_certificate.json"

PINNED_ANCHOR_FILE_SHA256 = (
    "067638e0f8529df79e68e9869abcb26d4cde61f9648488310c1436432540e41c"
)
PINNED_ANCHOR_PAYLOAD_SHA256 = (
    "f72c14e984f0c247fb44f9d5049a7575d8962eef6f16cacd243231f2a6a553ad"
)

PINNED_LEAN_FILES: MappingProxyType[str, str] = MappingProxyType({
    "lean_source": "DrosophilaConnectomeOperators.lean",
    "lean_source_sha256": (
        "144440b279d640ffeb32ad1f432339cef7840015892aee5469e30896ca5877a1"
    ),
    "lean_toolchain": "leanprover/lean4:v4.36.0",
    "lean_toolchain_sha256": (
        "582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a"
    ),
    "lakefile_sha256": (
        "738c966ec2176d0250f19be54833958dded055da13c198292b26b46577a2c339"
    ),
})

LEAN_THEOREM_NAMES: tuple[str, ...] = (
    "DrosophilaConnectomeOperators.dale_signed_partition_identity",
    "DrosophilaConnectomeOperators.dale_row_sign_homogeneity_bound",
    "DrosophilaConnectomeOperators.heavy_tail_concentration_lift",
    "DrosophilaConnectomeOperators.entropy_coding_bit_savings",
    "DrosophilaConnectomeOperators.active_bitmap_two_level_work_bound",
    "DrosophilaConnectomeOperators.lif_may_fire_one_step_envelope",
    "DrosophilaConnectomeOperators.lif_may_fire_horizon_safety",
    "DrosophilaConnectomeOperators.al_tusi_pythagorean_frobenius_2x2",
    "DrosophilaConnectomeOperators.nonnormal_commutator_2x2_exact",
    "DrosophilaConnectomeOperators.nonnormal_commutator_strict_pos",
    "DrosophilaConnectomeOperators.al_tusi_ei_loop_oscillatory_obstruction",
    "DrosophilaConnectomeOperators.signed_laplacian_energy_and_frustration",
    "DrosophilaConnectomeOperators.signed_triad_switching_invariance",
    "DrosophilaConnectomeOperators.schur_complement_2x2_completion",
    "DrosophilaConnectomeOperators.krein_indefinite_signature_witness",
    "DrosophilaConnectomeOperators.spmv_bandwidth_intensity_crossover",
    "DrosophilaConnectomeOperators.four_arm_tail_risk_dominance",
    "DrosophilaConnectomeOperators.bio_vs_hessian_concentration_gap",
)

UPSTREAM_EXPEDITION_BRIDGES: tuple[MappingProxyType[str, str], ...] = tuple(
    MappingProxyType(row)
    for row in (
        {
            "track": "S86",
            "cert_file": "track-s86-sovereign-8gb-fourth-order-stack/s86_sovereign_stack_certificate.json",
            "cert_sha256": "675bf68c1291a3cf7aeef9beb9a5efc316b55f44a6823a0a94f2ffef7754cb12",
            "bridge": "Top-0.5% Hessian-CSR sensitivity capture (3101/10000) vs MaleCNS top-0.5% synaptic capture (11.87%) and softmax1p CCE-Det link",
        },
        {
            "track": "S91",
            "cert_file": "track-s91-transhistorical-k26-convergence/s91_transhistorical_k26_certificate.json",
            "cert_sha256": "ca826006990bd883d6f38dbae7b290a28c82d00da5969afd9525e79f004b5ce1",
            "bridge": "Al-Tusi dual-loop rotational non-normal dynamics mirrored in Central Complex EPG/PEN/Delta7/ER ring attractor",
        },
        {
            "track": "S94",
            "cert_file": "track-s94-neuron-basis-bonsai-sleep-convergence/s94_wave6_convergence_certificate.json",
            "cert_sha256": "1ad705c23646b65df0dc9ac928d3a4070deef61f5d17f8e8f249b4f75f51335b",
            "bridge": "Law-5 memory-bandwidth crossover b_crit=325/171 bridged to nfly SpMV 35-57x CPU wall-time bottleneck",
        },
        {
            "track": "S96",
            "cert_file": "track-s96-beyond-lora-and-inkling2-loop/s96_beyond_lora_inkling_certificate.json",
            "cert_sha256": "5de85fe677a714f1af93722a7034947d13bd3938519d17a94508e1a008cfdd44",
            "bridge": "Sparse structured residual connectivity (fly-fpv/fly-racer) vs Beyond-LoRA BlockH4-Butterfly structured sparsity",
        },
    )
)

# Pinned Wave-9 engineering constants (exact integers/rationals from pinned READMEs)
S86_TOP_0P5PCT_CAPTURE_Q = Fraction(3101, 10000)
S94_B_CRIT_Q = Fraction(325, 171)

FRUITFLY_CALC_CONSTANTS: MappingProxyType[str, Any] = MappingProxyType({
    "repo": "evnsnclr/fruitfly-calculator",
    "edges_reported": 25_580_000,
    "encoded_mb_num": 309,
    "encoded_mb_den": 10,
    "encoded_w_ge_2_mb_num": 199,
    "encoded_w_ge_2_mb_den": 10,
    "encoded_w_eq_1_mb_num": 110,
    "encoded_w_eq_1_mb_den": 10,
    "raw_8byte_mb": 205,
    "ram_mb_num": 195,
    "ram_mb_den": 10,
    "flash_mb_num": 114,
    "flash_mb_den": 10,
    "bisection_gap_before_num": 15,
    "bisection_gap_before_den": 2,
    "bisection_gap_after_num": 3,
    "bisection_gap_after_den": 1,
    "full_sweep_us": 550,
    "quiet_step_us": 10,
    "boot_selftest_steps": 260,
    "boot_selftest_events": 2_900_000,
})

NFLY_CONSTANTS: MappingProxyType[str, Any] = MappingProxyType({
    "repo": "zhengxuyu/nfly",
    "spmv_edges": 8_400_000,
    "mlp_params": 8_500_000,
    "ops_ratio": 4,
    "cpu_wall_ratio_lo": 35,
    "cpu_wall_ratio_hi": 57,
})

FLY_RACER_ARMS: tuple[MappingProxyType[str, Any], ...] = tuple(
    MappingProxyType(row)
    for row in (
        {"arm": "fly", "mean_x10": 9032, "sd_x10": 232, "worst_x10": 7963},
        {"arm": "signs", "mean_x10": 8969, "sd_x10": 282, "worst_x10": 7450},
        {"arm": "mlp", "mean_x10": 8940, "sd_x10": 759, "worst_x10": 3512},
        {"arm": "random", "mean_x10": 8837, "sd_x10": 820, "worst_x10": 4309},
    )
)

FLY_RACER_TIER_S: MappingProxyType[str, Any] = MappingProxyType({
    "repo": "supat-roong/fly-racer",
    "tier": "S",
    "neurons": 3350,
    "edges": 164773,
    "heldout_episodes": 100,
    "risk_sigma_k": 3,
})

SOP10_SIBLING_PORTFOLIO: tuple[MappingProxyType[str, str], ...] = tuple(
    MappingProxyType(row)
    for row in (
        {
            "repo": "evnsnclr/wvc",
            "portal_author": "evnsnclr",
            "bridge_target": "S97/weft weight-space version control & snapshot provenance",
        },
        {
            "repo": "zhengxuyu/softmax1p",
            "portal_author": "zhengxuyu",
            "bridge_target": "S86 CCE-Det numerical stability & collapse-free softmax",
        },
        {
            "repo": "zhengxuyu/HDM-code",
            "portal_author": "zhengxuyu",
            "bridge_target": "S95 hybrid zero-token vs reasoning-budget routing",
        },
        {
            "repo": "joey-david/fly-fpv",
            "portal_author": "joey-david",
            "bridge_target": "S96 4-arm retinotopic sparse residual connectome control",
        },
        {
            "repo": "joey-david/latent-correctness-probe",
            "portal_author": "joey-david",
            "bridge_target": "S94 neuron-basis latent calibration & probe interpretability",
        },
    )
)

SCHUR_BOUNDARY_INDICES: tuple[int, ...] = (0, 6, 7)
SCHUR_INTERIOR_INDICES: tuple[int, ...] = (1, 2, 3, 4, 5)
CX_EXPECTED_ROW_SIGNS: tuple[int, ...] = (1, 1, -1, 1, -1, 1)
CX_PAIRS_OF_INTEREST: tuple[tuple[str, int, int], ...] = (
    ("EPG_ER", 0, 4),
    ("EPG_Delta7", 0, 2),
    ("PEN_EPG", 1, 0),
    ("Delta7_PFL", 2, 5),
    ("EPG_PFL", 0, 5),
)


class S102Error(ValueError):
    """Structured fail-closed error for Track S102."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def require_ok(cond: bool, code: str, message: str) -> None:
    if type(cond) is not bool or not cond:
        raise S102Error(code, message)


def require_exact_int(
    val: Any, label: str, *, lo: int | None = None, hi: int | None = None
) -> int:
    require_ok(type(val) is int, "TYPE_ERROR", f"{label}: expected exact int")
    if lo is not None:
        require_ok(val >= lo, "RANGE_ERROR", f"{label}: {val} < {lo}")
    if hi is not None:
        require_ok(val <= hi, "RANGE_ERROR", f"{label}: {val} > {hi}")
    return val


def require_exact_str(val: Any, label: str) -> str:
    require_ok(type(val) is str, "TYPE_ERROR", f"{label}: expected exact str")
    return val


def require_exact_bool(val: Any, label: str) -> bool:
    require_ok(type(val) is bool, "TYPE_ERROR", f"{label}: expected exact bool")
    return val


def fmt_q(val: Fraction) -> str:
    require_ok(isinstance(val, Fraction), "TYPE_ERROR", "expected Fraction")
    if val.denominator == 1:
        return str(val.numerator)
    return f"{val.numerator}/{val.denominator}"


def canonical_json_bytes(obj: Any) -> bytes:
    return (
        json.dumps(
            obj,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


ANCHOR_MAX_INT_DIGITS = 80
ANCHOR_MAX_STR_LEN = 256
ANCHOR_MAX_DEPTH = 32


def _reject_float(token: str) -> Any:
    raise S102Error("FLOAT_FORBIDDEN", f"non-integer JSON float token: {token}")


def _reject_constant(token: str) -> Any:
    raise S102Error("JSON_CONSTANT_FORBIDDEN", f"invalid JSON constant: {token}")


def _reject_large_int(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    require_ok(
        len(digits) <= ANCHOR_MAX_INT_DIGITS,
        "ANCHOR_INT_TOO_LARGE",
        f"anchor integer exceeds {ANCHOR_MAX_INT_DIGITS} digits",
    )
    return int(token)


def _reject_dup_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise S102Error("DUPLICATE_JSON_KEY", f"duplicate key: {k}")
        out[k] = v
    return out


def _validate_anchor_tree(root: Any) -> None:
    stack: list[tuple[Any, int]] = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        require_ok(
            depth <= ANCHOR_MAX_DEPTH,
            "ANCHOR_TOO_DEEP",
            f"anchor depth exceeds {ANCHOR_MAX_DEPTH}",
        )
        t = type(node)
        if t is str:
            require_ok(
                len(node) <= ANCHOR_MAX_STR_LEN,
                "ANCHOR_STR_TOO_LONG",
                f"anchor string exceeds {ANCHOR_MAX_STR_LEN} chars",
            )
        elif t is dict:
            for k, v in node.items():
                require_ok(
                    len(k) <= ANCHOR_MAX_STR_LEN,
                    "ANCHOR_STR_TOO_LONG",
                    f"anchor key exceeds {ANCHOR_MAX_STR_LEN} chars",
                )
                stack.append((v, depth + 1))
        elif t is list:
            for item in node:
                stack.append((item, depth + 1))


def load_anchor_from_bytes(raw: bytes, *, check_pinned_sha: bool = True) -> dict[str, Any]:
    if check_pinned_sha:
        got_file_sha = sha256_bytes(raw)
        require_ok(
            got_file_sha == PINNED_ANCHOR_FILE_SHA256,
            "ANCHOR_FILE_SHA_MISMATCH",
            f"anchor file sha mismatch: {got_file_sha}",
        )
    try:
        text = raw.decode("utf-8", "strict")
        env = json.loads(
            text,
            parse_int=_reject_large_int,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_dup_keys,
        )
    except S102Error:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise S102Error("ANCHOR_JSON_INVALID", str(exc)) from exc
    _validate_anchor_tree(env)
    require_ok(type(env) is dict, "ANCHOR_TYPE_ERROR", "anchor root must be dict")
    require_ok(
        env.get("schema_version") == ANCHOR_SCHEMA_VERSION,
        "ANCHOR_SCHEMA_MISMATCH",
        "unexpected anchor schema",
    )
    require_ok(env.get("track_id") == TRACK_ID, "ANCHOR_TRACK_MISMATCH", "unexpected anchor track")
    payload = env.get("payload")
    require_ok(type(payload) is dict, "ANCHOR_PAYLOAD_ERROR", "anchor payload must be dict")
    got_payload_sha = sha256_bytes(canonical_json_bytes(payload))
    require_ok(
        env.get("payload_sha256") == got_payload_sha,
        "ANCHOR_PAYLOAD_SHA_MISMATCH",
        "anchor payload sha mismatch",
    )
    return payload


def load_anchor_default(anchor_path: Path | None = None) -> dict[str, Any]:
    p = TRACK_DIR / ANCHOR_FILENAME if anchor_path is None else anchor_path
    return load_anchor_from_bytes(p.read_bytes(), check_pinned_sha=True)


# ---------------------------------------------------------------------------
# Pure-Integer / Exact-Rational Linear Algebra Operators
# ---------------------------------------------------------------------------


def sym_signed_laplacian(mat: list[list[int]]) -> list[list[int]]:
    n = len(mat)
    sym_off = [
        [mat[i][j] + mat[j][i] if i != j else 0 for j in range(n)]
        for i in range(n)
    ]
    lap = [[0] * n for _ in range(n)]
    for i in range(n):
        lap[i][i] = sum(abs(sym_off[i][j]) for j in range(n) if j != i)
        for j in range(n):
            if i != j:
                lap[i][j] = -sym_off[i][j]
    return lap


def exact_ldlt_pivots(mat: list[list[Any]]) -> list[Fraction]:
    n = len(mat)
    a_mat = [[Fraction(mat[i][j]) for j in range(n)] for i in range(n)]
    l_mat = [[Fraction(1 if i == j else 0) for j in range(n)] for i in range(n)]
    diag = [Fraction(0)] * n
    for j in range(n):
        s_val = sum(l_mat[j][k] * l_mat[j][k] * diag[k] for k in range(j))
        piv = a_mat[j][j] - s_val
        require_ok(piv != 0, "LDLT_ZERO_PIVOT", f"zero pivot at index {j}")
        diag[j] = piv
        for i in range(j + 1, n):
            s2 = sum(l_mat[i][k] * l_mat[j][k] * diag[k] for k in range(j))
            l_mat[i][j] = (a_mat[i][j] - s2) / piv
    return diag


def inertia_from_pivots(pivots: list[Fraction]) -> list[int]:
    """Return exact Sylvester/Krein inertia triple in `[n_pos, n_neg, n_zero]` (`[n_+, n_-, n_0]`) order.
    Note: Cross-track comparison with Track S99 must account for S99's `(n_pos, n_zero, n_neg)` order.
    """
    n_pos = sum(1 for p in pivots if p > 0)
    n_neg = sum(1 for p in pivots if p < 0)
    n_zero = sum(1 for p in pivots if p == 0)
    return [n_pos, n_neg, n_zero]


def exact_mat_inv(mat: list[list[Fraction]]) -> list[list[Fraction]]:
    n = len(mat)
    aug = [
        [Fraction(mat[i][j]) for j in range(n)]
        + [Fraction(1 if i == j else 0) for j in range(n)]
        for i in range(n)
    ]
    for col in range(n):
        piv_row = -1
        for r in range(col, n):
            if aug[r][col] != 0:
                piv_row = r
                break
        require_ok(piv_row >= 0, "SINGULAR_MATRIX", f"singular column {col}")
        aug[col], aug[piv_row] = aug[piv_row], aug[col]
        pv = aug[col][col]
        aug[col] = [x / pv for x in aug[col]]
        for r in range(n):
            if r != col:
                fac = aug[r][col]
                aug[r] = [aug[r][k] - fac * aug[col][k] for k in range(2 * n)]
    return [row[n:] for row in aug]


def exact_mat_mul_q(a_mat: list[list[Fraction]], b_mat: list[list[Fraction]]) -> list[list[Fraction]]:
    m = len(a_mat)
    k_dim = len(b_mat)
    n = len(b_mat[0])
    return [
        [sum(a_mat[i][t] * b_mat[t][j] for t in range(k_dim)) for j in range(n)]
        for i in range(m)
    ]


def operator_frobenius_and_commutator(mat: list[list[int]]) -> dict[str, Any]:
    n = len(mat)
    frob2 = sum(mat[i][j] * mat[i][j] for i in range(n) for j in range(n))
    sym2_x4 = sum((mat[i][j] + mat[j][i]) ** 2 for i in range(n) for j in range(n))
    skew2_x4 = sum((mat[i][j] - mat[j][i]) ** 2 for i in range(n) for j in range(n))
    wwt = [
        [sum(mat[i][k] * mat[j][k] for k in range(n)) for j in range(n)]
        for i in range(n)
    ]
    wtw = [
        [sum(mat[k][i] * mat[k][j] for k in range(n)) for j in range(n)]
        for i in range(n)
    ]
    comm2 = sum((wwt[i][j] - wtw[i][j]) ** 2 for i in range(n) for j in range(n))
    return {
        "dim": n,
        "frobenius_norm_sq": frob2,
        "sym_norm_sq_x4": sym2_x4,
        "skew_norm_sq_x4": skew2_x4,
        "skew_energy_fraction_q": fmt_q(Fraction(skew2_x4, 4 * frob2)),
        "commutator_norm_sq": comm2,
        "normalized_commutator_ratio_q": fmt_q(Fraction(comm2, frob2 * frob2)),
    }


def simulate_integer_lif_may_fire(v0: int, g0: int, theta: int, steps: int) -> dict[str, Any]:
    """Exact discrete integer LIF simulation matching `fruitfly-calculator`:
    dv = (g - v) // 20 (truncated toward 0 for nonneg/exact floor), dg = -(g // 5),
    verifying Lyapunov envelope `4 * max(v, 0) + max(g, 0)` non-increasing at every step.
    """
    v = v0
    g = g0
    env0 = 4 * max(v, 0) + max(g, 0)
    peak_v = v
    prev_env = env0
    monotone_all = True
    below_bound_all = True
    for _ in range(steps):
        # Exact floor division satisfies 20 * v' <= 19 * v + g and 5 * g' <= 4 * g
        v_next = (19 * v + g) // 20
        g_next = (4 * g) // 5
        env_next = 4 * max(v_next, 0) + max(g_next, 0)
        if env_next > prev_env:
            monotone_all = False
        if 4 * v_next > env0:
            below_bound_all = False
        if v_next > peak_v:
            peak_v = v_next
        v, g, prev_env = v_next, g_next, env_next
    return {
        "v0": v0,
        "g0": g0,
        "theta": theta,
        "steps": steps,
        "initial_envelope_4v_plus_g": env0,
        "threshold_4theta": 4 * theta,
        "may_fire_pruned": env0 < 4 * theta,
        "simulated_peak_v": peak_v,
        "never_reached_theta": peak_v < theta,
        "envelope_monotone_all_steps": monotone_all,
        "peak_bounded_by_envelope": below_bound_all,
    }


# ---------------------------------------------------------------------------
# Four-Pillar Certificate Builder
# ---------------------------------------------------------------------------


def build_pillar1_whole_cns(anchor: dict[str, Any]) -> dict[str, Any]:
    topo = anchor["whole_cns_topology"]
    edges = topo["directed_edges"]
    syn = topo["total_synapses"]
    act = topo["active_connected_neurons"]
    dale = topo["dale_edge_synapse_partition"]

    exc_e = dale["excitatory_ach"]["edges"]
    exc_s = dale["excitatory_ach"]["synapses"]
    inh_e = dale["inhibitory_gaba_glu_his"]["edges"]
    inh_s = dale["inhibitory_gaba_glu_his"]["synapses"]
    mod_e = dale["modulatory_da_oa_5ht"]["edges"]
    mod_s = dale["modulatory_da_oa_5ht"]["synapses"]
    unc_e = dale["unclear_missing"]["edges"]
    unc_s = dale["unclear_missing"]["synapses"]

    require_ok(exc_e + inh_e + mod_e + unc_e == edges, "DALE_EDGE_SUM", "dale edge sum mismatch")
    require_ok(exc_s + inh_s + mod_s + unc_s == syn, "DALE_SYN_SUM", "dale syn sum mismatch")

    signed_syn_total = exc_s + inh_s
    signed_syn_net = exc_s - inh_s

    thresholds_out = [
        {
            "min_weight": row["min_weight"],
            "edges": row["edges"],
            "synapses": row["synapses"],
            "edge_fraction_q": fmt_q(Fraction(row["edges"], edges)),
            "synapse_fraction_q": fmt_q(Fraction(row["synapses"], syn)),
        }
        for row in topo["weight_thresholds"]
    ]

    top_k_out = []
    top_0p5_q: Fraction | None = None
    for row in topo["top_k_concentration"]:
        e_frac = Fraction(row["edge_count"], edges)
        s_frac = Fraction(row["synapses"], syn)
        lift = s_frac / e_frac
        if row["label"] == "top_0p5pct":
            top_0p5_q = s_frac
        top_k_out.append({
            "label": row["label"],
            "permille": row["permille"],
            "edge_count": row["edge_count"],
            "cutoff_weight": row["cutoff_weight"],
            "synapses": row["synapses"],
            "edge_fraction_q": fmt_q(e_frac),
            "synapse_fraction_q": fmt_q(s_frac),
            "uniform_density_lift_q": fmt_q(lift),
        })
    require_ok(top_0p5_q is not None, "MISSING_TOP_0P5", "missing top_0p5pct entry")

    return {
        "annotation_rows": topo["annotation_rows"],
        "annotation_with_superclass": topo["annotation_with_superclass"],
        "distinct_annotated_cell_types": topo["distinct_annotated_cell_types"],
        "neurotransmitter_table_rows": topo["neurotransmitter_table_rows"],
        "active_connected_neurons": act,
        "directed_edges": edges,
        "total_synapses": syn,
        "min_edge_weight": topo["min_edge_weight"],
        "max_edge_weight": topo["max_edge_weight"],
        "self_loop_edges": topo["self_loop_edges"],
        "mean_weight_per_edge_q": fmt_q(Fraction(syn, edges)),
        "mean_out_degree_q": fmt_q(Fraction(edges, act)),
        "mean_synapses_per_active_neuron_q": fmt_q(Fraction(syn, act)),
        "active_neuron_neurotransmitters": copy.deepcopy(topo["active_neuron_neurotransmitters"]),
        "dale_edge_synapse_partition": copy.deepcopy(dale),
        "dale_signed_synapses_total": signed_syn_total,
        "dale_signed_net_balance": signed_syn_net,
        "dale_exc_share_of_signed_q": fmt_q(Fraction(exc_s, signed_syn_total)),
        "dale_inh_share_of_signed_q": fmt_q(Fraction(inh_s, signed_syn_total)),
        "dale_exc_to_inh_ratio_q": fmt_q(Fraction(exc_s, inh_s)),
        "weight_thresholds": thresholds_out,
        "top_k_concentration": top_k_out,
        "s86_hessian_top_0p5pct_capture_q": fmt_q(S86_TOP_0P5PCT_CAPTURE_Q),
        "s86_vs_malecns_top_0p5pct_ratio_q": fmt_q(S86_TOP_0P5PCT_CAPTURE_Q / top_0p5_q),
        "s86_minus_malecns_top_0p5pct_gap_q": fmt_q(S86_TOP_0P5PCT_CAPTURE_Q - top_0p5_q),
    }


def build_pillar2_cx_and_supergraph(anchor: dict[str, Any]) -> dict[str, Any]:
    topo = anchor["whole_cns_topology"]
    sg = anchor["functional_supergraph_8x8"]
    cx = anchor["central_complex_core_6x6"]
    tr = anchor["central_complex_triads_w10"]

    w8_u = sg["unsigned_synapses_8x8"]
    w8_s = sg["dale_signed_synapses_8x8"]
    w6_u = cx["unsigned_synapses_6x6"]
    w6_s = cx["dale_signed_synapses_6x6"]

    ops_w8_u = operator_frobenius_and_commutator(w8_u)
    ops_w8_s = operator_frobenius_and_commutator(w8_s)
    ops_w6_u = operator_frobenius_and_commutator(w6_u)
    ops_w6_s = operator_frobenius_and_commutator(w6_s)

    # Exact signed Laplacians & Krein inertia
    l_sig_8 = sym_signed_laplacian(w8_s)
    piv_l8 = exact_ldlt_pivots(l_sig_8)
    h_s_8 = [[w8_s[i][j] + w8_s[j][i] for j in range(8)] for i in range(8)]
    piv_h8 = exact_ldlt_pivots(h_s_8)

    l_sig_6 = sym_signed_laplacian(w6_s)
    piv_l6 = exact_ldlt_pivots(l_sig_6)
    h_s_6 = [[w6_s[i][j] + w6_s[j][i] for j in range(6)] for i in range(6)]
    piv_h6 = exact_ldlt_pivots(h_s_6)

    # Exact 8->3 Schur complement onto B=(0,6,7) eliminating I=(1,2,3,4,5)
    b_idx = list(SCHUR_BOUNDARY_INDICES)
    i_idx = list(SCHUR_INTERIOR_INDICES)
    l_bb = [[Fraction(l_sig_8[r][c]) for c in b_idx] for r in b_idx]
    l_bi = [[Fraction(l_sig_8[r][c]) for c in i_idx] for r in b_idx]
    l_ib = [[Fraction(l_sig_8[r][c]) for c in b_idx] for r in i_idx]
    l_ii = [[Fraction(l_sig_8[r][c]) for c in i_idx] for r in i_idx]

    piv_lii = exact_ldlt_pivots(l_ii)
    l_ii_inv = exact_mat_inv(l_ii)
    shadow = exact_mat_mul_q(exact_mat_mul_q(l_bi, l_ii_inv), l_ib)
    s_b = [[l_bb[r][c] - shadow[r][c] for c in range(3)] for r in range(3)]
    piv_sb = exact_ldlt_pivots(s_b)

    tr_bb = sum(l_bb[r][r] for r in range(3))
    tr_sb = sum(s_b[r][r] for r in range(3))
    tr_shadow = sum(shadow[r][r] for r in range(3))

    # Verify 100% Dale row sign homogeneity in 6x6 CX core
    row_signs = list(CX_EXPECTED_ROW_SIGNS)
    for r in range(6):
        sgn = row_signs[r]
        for c in range(6):
            require_ok(
                w6_s[r][c] == sgn * w6_u[r][c],
                "CX_DALE_ROW_MISMATCH",
                f"CX row {r} col {c} violates pure Dale sign",
            )

    cx_pair_witnesses = []
    for label, i, j in CX_PAIRS_OF_INTEREST:
        a_ij = w6_s[i][j]
        a_ji = w6_s[j][i]
        a_ii = w6_s[i][i]
        a_jj = w6_s[j][j]
        c11 = a_ij * a_ij - a_ji * a_ji
        c12 = (a_ii - a_jj) * (a_ji - a_ij)
        comm2_2x2 = 2 * (c11 * c11 + c12 * c12)
        cx_pair_witnesses.append({
            "pair": label,
            "w_ij_signed": a_ij,
            "w_ji_signed": a_ji,
            "abs_directional_ratio_q": fmt_q(Fraction(max(abs(a_ij), abs(a_ji)), min(abs(a_ij), abs(a_ji)))),
            "opposing_dale_signs": (a_ij * a_ji) < 0,
            "commutator_2x2_norm_sq": comm2_2x2,
        })

    # CX w>=10 triad enrichment & signed frustration
    obs = tr["observed"]
    nul = tr["maslov_sneppen_null"]
    dir_e = tr["directed_edges"]

    cx_norm_comm_q = Fraction(ops_w6_s["commutator_norm_sq"], ops_w6_s["frobenius_norm_sq"] ** 2)
    w8_norm_comm_q = Fraction(ops_w8_s["commutator_norm_sq"], ops_w8_s["frobenius_norm_sq"] ** 2)

    return {
        "supergraph_8x8": {
            "module_names": list(sg["module_names"]),
            "active_neurons_per_module": list(sg["active_neurons_per_module"]),
            "unannotated_active_neurons": sg["unannotated_active_neurons"],
            "covered_edges": sg["covered_edges"],
            "covered_synapses": sg["covered_synapses"],
            "edge_coverage_q": fmt_q(Fraction(sg["covered_edges"], topo["directed_edges"])),
            "synapse_coverage_q": fmt_q(Fraction(sg["covered_synapses"], topo["total_synapses"])),
            "unsigned_synapses_8x8": copy.deepcopy(w8_u),
            "dale_signed_synapses_8x8": copy.deepcopy(w8_s),
            "unsigned_operators": ops_w8_u,
            "signed_operators": ops_w8_s,
            "signed_laplacian_ldlt_inertia": inertia_from_pivots(piv_l8),
            "signed_laplacian_structurally_frustrated": inertia_from_pivots(piv_l8) == [8, 0, 0],
            "symmetrized_dale_krein_inertia": inertia_from_pivots(piv_h8),
            "biological_sign_witnesses": {
                "sensory_to_optic_histamine_net": w8_s[0][1],
                "central_complex_self_net": w8_s[3][3],
                "vnc_motor_self_cns_glu_gaba_net": w8_s[7][7],
            },
            "schur_complement_io_boundary": {
                "boundary_indices": b_idx,
                "interior_indices": i_idx,
                "interior_ldlt_inertia": inertia_from_pivots(piv_lii),
                "schur_ldlt_inertia": inertia_from_pivots(piv_sb),
                "trace_L_BB": int(tr_bb),
                "trace_S_B_q": fmt_q(tr_sb),
                "trace_dark_shadow_q": fmt_q(tr_shadow),
                "dark_shadow_fraction_q": fmt_q(tr_shadow / tr_bb),
                "schur_matrix_3x3_q": [[fmt_q(x) for x in row] for row in s_b],
            },
        },
        "central_complex_6x6": {
            "population_names": list(cx["population_names"]),
            "active_neurons_per_population": list(cx["active_neurons_per_population"]),
            "dale_row_signs": row_signs,
            "dale_row_pure_homogeneous": True,
            "unsigned_synapses_6x6": copy.deepcopy(w6_u),
            "dale_signed_synapses_6x6": copy.deepcopy(w6_s),
            "unsigned_operators": ops_w6_u,
            "signed_operators": ops_w6_s,
            "signed_laplacian_ldlt_inertia": inertia_from_pivots(piv_l6),
            "signed_laplacian_structurally_frustrated": inertia_from_pivots(piv_l6) == [6, 0, 0],
            "symmetrized_dale_krein_inertia": inertia_from_pivots(piv_h6),
            "cx_vs_wholebrain_nonnormality_lift_q": fmt_q(cx_norm_comm_q / w8_norm_comm_q),
            "al_tusi_pair_witnesses": cx_pair_witnesses,
        },
        "central_complex_triads_w10": {
            "min_weight": tr["min_weight"],
            "active_nodes": tr["active_nodes"],
            "directed_edges": dir_e,
            "total_synapses": tr["total_synapses"],
            "observed": copy.deepcopy(obs),
            "maslov_sneppen_null": copy.deepcopy(nul),
            "observed_reciprocity_q": fmt_q(Fraction(obs["reciprocal_directed_edges"], dir_e)),
            "null_reciprocity_q": fmt_q(Fraction(nul["reciprocal_directed_edges"], dir_e)),
            "reciprocity_enrichment_q": fmt_q(
                Fraction(obs["reciprocal_directed_edges"], nul["reciprocal_directed_edges"])
            ),
            "ffl_enrichment_q": fmt_q(Fraction(obs["ffl_total"], nul["ffl_total"])),
            "directed_3cycles_enrichment_q": fmt_q(
                Fraction(obs["directed_3cycles_total"], nul["directed_3cycles_total"])
            ),
            "observed_ffl_to_3cycle_ratio_q": fmt_q(
                Fraction(obs["ffl_total"], obs["directed_3cycles_total"])
            ),
            "observed_incoherent_ffl_fraction_q": fmt_q(
                Fraction(obs["signed_ffl_incoherent_neg"], obs["signed_ffl_total"])
            ),
            "null_incoherent_ffl_fraction_q": fmt_q(
                Fraction(nul["signed_ffl_incoherent_neg"], nul["signed_ffl_total"])
            ),
            "incoherent_ffl_enrichment_q": fmt_q(
                Fraction(obs["signed_ffl_incoherent_neg"], nul["signed_ffl_incoherent_neg"])
            ),
            "coherent_ffl_enrichment_q": fmt_q(
                Fraction(obs["signed_ffl_coherent_pos"], nul["signed_ffl_coherent_pos"])
            ),
            "observed_neg_3cycle_fraction_q": fmt_q(
                Fraction(obs["signed_3cycles_negative_feedback"], obs["signed_3cycles_total"])
            ),
            "null_neg_3cycle_fraction_q": fmt_q(
                Fraction(nul["signed_3cycles_negative_feedback"], nul["signed_3cycles_total"])
            ),
            "neg_3cycle_enrichment_q": fmt_q(
                Fraction(
                    obs["signed_3cycles_negative_feedback"],
                    nul["signed_3cycles_negative_feedback"],
                )
            ),
            "pos_3cycle_enrichment_q": fmt_q(
                Fraction(
                    obs["signed_3cycles_positive_feedback"],
                    nul["signed_3cycles_positive_feedback"],
                )
            ),
        },
    }


def build_pillar3_wave9_engineering() -> dict[str, Any]:
    fc = FRUITFLY_CALC_CONSTANTS
    enc_mb = Fraction(fc["encoded_mb_num"], fc["encoded_mb_den"])
    ram_mb = Fraction(fc["ram_mb_num"], fc["ram_mb_den"])
    flash_mb = Fraction(fc["flash_mb_num"], fc["flash_mb_den"])
    raw_mb = Fraction(fc["raw_8byte_mb"], 1)

    bits_per_edge = (enc_mb * 8 * 1_000_000) / fc["edges_reported"]
    gap_before = Fraction(fc["bisection_gap_before_num"], fc["bisection_gap_before_den"])
    gap_after = Fraction(fc["bisection_gap_after_num"], fc["bisection_gap_after_den"])

    lif_pruned_witness = simulate_integer_lif_may_fire(v0=120, g0=600, theta=300, steps=40)
    lif_active_witness = simulate_integer_lif_may_fire(v0=200, g0=1200, theta=300, steps=40)

    nf = NFLY_CONSTANTS
    arms_by_name = {a["arm"]: a for a in FLY_RACER_ARMS}
    fly_arm = arms_by_name["fly"]
    signs_arm = arms_by_name["signs"]
    mlp_arm = arms_by_name["mlp"]
    rand_arm = arms_by_name["random"]
    k_sig = FLY_RACER_TIER_S["risk_sigma_k"]

    var_mlp_over_fly = Fraction(mlp_arm["sd_x10"] ** 2, fly_arm["sd_x10"] ** 2)
    var_rand_over_fly = Fraction(rand_arm["sd_x10"] ** 2, fly_arm["sd_x10"] ** 2)
    var_mlp_over_signs = Fraction(mlp_arm["sd_x10"] ** 2, signs_arm["sd_x10"] ** 2)

    return {
        "fruitfly_calculator": {
            "repo": fc["repo"],
            "edges_reported": fc["edges_reported"],
            "encoded_mb_q": fmt_q(enc_mb),
            "raw_8byte_mb_q": fmt_q(raw_mb),
            "compression_ratio_q": fmt_q(raw_mb / enc_mb),
            "encoded_bits_per_edge_q": fmt_q(bits_per_edge),
            "ram_paging_fraction_q": fmt_q(ram_mb / enc_mb),
            "flash_paging_fraction_q": fmt_q(flash_mb / enc_mb),
            "bisection_gap_compression_q": fmt_q(gap_before / gap_after),
            "active_bitmap_quiet_speedup_q": fmt_q(Fraction(fc["full_sweep_us"], fc["quiet_step_us"])),
            "boot_selftest_steps": fc["boot_selftest_steps"],
            "boot_selftest_events": fc["boot_selftest_events"],
            "lif_may_fire_pruned_witness": lif_pruned_witness,
            "lif_may_fire_active_witness": lif_active_witness,
        },
        "nfly_law5_bandwidth_bridge": {
            "repo": nf["repo"],
            "spmv_edges": nf["spmv_edges"],
            "mlp_params": nf["mlp_params"],
            "arithmetic_ops_ratio_q": fmt_q(Fraction(nf["ops_ratio"], 1)),
            "cpu_wall_ratio_lo_q": fmt_q(Fraction(nf["cpu_wall_ratio_lo"], 1)),
            "cpu_wall_ratio_hi_q": fmt_q(Fraction(nf["cpu_wall_ratio_hi"], 1)),
            "bandwidth_penalty_per_op_lo_q": fmt_q(Fraction(nf["cpu_wall_ratio_lo"], nf["ops_ratio"])),
            "bandwidth_penalty_per_op_hi_q": fmt_q(Fraction(nf["cpu_wall_ratio_hi"], nf["ops_ratio"])),
            "s94_law5_b_crit_q": fmt_q(S94_B_CRIT_Q),
        },
        "fly_racer_four_arm_tail_risk": {
            "repo": FLY_RACER_TIER_S["repo"],
            "tier_s_neurons": FLY_RACER_TIER_S["neurons"],
            "tier_s_edges": FLY_RACER_TIER_S["edges"],
            "heldout_episodes": FLY_RACER_TIER_S["heldout_episodes"],
            "arms": [dict(a) for a in FLY_RACER_ARMS],
            "variance_collapse_mlp_over_fly_q": fmt_q(var_mlp_over_fly),
            "variance_collapse_random_over_fly_q": fmt_q(var_rand_over_fly),
            "variance_collapse_mlp_over_signs_q": fmt_q(var_mlp_over_signs),
            "worst_case_floor_lift_fly_minus_mlp_q": fmt_q(
                Fraction(fly_arm["worst_x10"] - mlp_arm["worst_x10"], 10)
            ),
            "worst_case_floor_ratio_fly_over_mlp_q": fmt_q(
                Fraction(fly_arm["worst_x10"], mlp_arm["worst_x10"])
            ),
            "risk_sigma_k": k_sig,
            "fly_3sigma_floor_q": fmt_q(Fraction(fly_arm["mean_x10"] - k_sig * fly_arm["sd_x10"], 10)),
            "mlp_3sigma_floor_q": fmt_q(Fraction(mlp_arm["mean_x10"] - k_sig * mlp_arm["sd_x10"], 10)),
            "fly_minus_mlp_3sigma_margin_q": fmt_q(
                Fraction(
                    (fly_arm["mean_x10"] - k_sig * fly_arm["sd_x10"])
                    - (mlp_arm["mean_x10"] - k_sig * mlp_arm["sd_x10"]),
                    10,
                )
            ),
        },
        "sop10_sibling_portfolio": [dict(s) for s in SOP10_SIBLING_PORTFOLIO],
    }


def build_pillar4_lean4_and_provenance(anchor: dict[str, Any]) -> dict[str, Any]:
    return {
        "anchor_filename": ANCHOR_FILENAME,
        "anchor_file_sha256": PINNED_ANCHOR_FILE_SHA256,
        "anchor_payload_sha256": PINNED_ANCHOR_PAYLOAD_SHA256,
        "dataset_release": anchor["dataset_release"],
        "license": anchor["license"],
        "malecns_external_pins": copy.deepcopy(anchor["malecns_external_pins"]),
        "wave9_portal_pins": copy.deepcopy(anchor["wave9_portal_pins"]),
        "lean_artifacts": {
            **PINNED_LEAN_FILES,
            "lean_theorem_count": len(LEAN_THEOREM_NAMES),
            "lean_theorem_names": list(LEAN_THEOREM_NAMES),
            "allowed_axioms": ["propext", "Quot.sound"],
            "zero_classical_choice": True,
        },
        "upstream_expedition_bridges": [dict(b) for b in UPSTREAM_EXPEDITION_BRIDGES],
        "honest_novelty_scope": {
            "n0_verified_empirical": "Exact integer/rational topology, Dale's-law partition, 8x8/6x6 supergraphs, and CX w>=10 directed/signed triad motifs extracted live from FlyEM MaleCNS v1.0",
            "n1_formal_synthesis": "18 pure-Init Lean 4.36.0 operator laws (incl. discrete integer LIF may_fire Lyapunov pruning, Al-Tusi 2x2 commutator, Zaslavsky signed triad gauge invariance, Schur/Krein inertia) bridged to Wave-9 portals and S86/S91/S94/S96",
            "n2_open_claims_count": 0,
        },
    }


def build_certificate(anchor: dict[str, Any] | None = None) -> dict[str, Any]:
    anc = load_anchor_default() if anchor is None else anchor
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "oracle_class": ORACLE_CLASS,
        "novelty_classification": NOVELTY_CLASSIFICATION,
        "pillar1_whole_cns_topology": build_pillar1_whole_cns(anc),
        "pillar2_cx_attractor_and_supergraph": build_pillar2_cx_and_supergraph(anc),
        "pillar3_wave9_portal_engineering": build_pillar3_wave9_engineering(),
        "pillar4_lean4_and_provenance": build_pillar4_lean4_and_provenance(anc),
    }
    payload_sha = sha256_bytes(canonical_json_bytes(payload))
    body = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": payload_sha,
        "payload": payload,
    }
    cert_sha = sha256_bytes(canonical_json_bytes(body))
    return {**body, "certificate_sha256": cert_sha}


def main() -> int:
    cert = build_certificate()
    import sys

    sys.stdout.write(canonical_json_bytes(cert).decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
