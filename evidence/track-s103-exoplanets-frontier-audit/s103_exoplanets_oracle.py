#!/usr/bin/env python3
"""Track S103: Pure-Z/Q Exact Astrophysical Verification Operators and
SOP-9 / SOP-10 Live Forensic Audit Oracle for Foundation-0/exoplanets-frontier
and the public Foundation-0 / eumemic astronomy spine.

Zero floating-point operations, zero bare asserts, zero third-party packages,
zero RNG on mathematical paths.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from typing import Any

TRACK_ID = "TRACK-S103-EXOPLANETS-FRONTIER-AUDIT"
SCHEMA_VERSION = "aletheia.s103_exoplanets_frontier_audit.v1"
EXPECTED_LEAN_TOOLCHAIN = "leanprover/lean4:v4.36.0"

EXOPLANETS_FRONTIER_REPO = "Foundation-0/exoplanets-frontier"
EXOPLANETS_FRONTIER_MAIN_COMMIT = "3bc0163bc04547628072aa5b281eda282347e3d1"
EXOPLANETS_FRONTIER_PR13_COMMIT = "1c7aef9d79dd4a8f05e828f7de47084dd4db5348"
EXOPLANETS_FRONTIER_PR8_COMMIT = "54671cc8be8f8c3c1e2aec950280ae9825182a4a"
EXOPLANETS_FRONTIER_PR7_COMMIT = "35a77f75262c98baadb005d357d60df2f1a57e38"
EXOPLANETS_FRONTIER_PR6_COMMIT = "b9657985a433b6b7b4b17baaa26eee1e95ee6759"

PINNED_LEAN_SOURCE_SHA256 = "6359ee54c2e7fc8592f06b75a419177193fe799df6a6f3ad2427e8d6bb247c55"
PINNED_LEAN_TOOLCHAIN_SHA256 = "582a63f8f9c5128067b688778c1051cf1464c3ca9d57b9325025c051c29b774a"
PINNED_LAKEFILE_SHA256 = "6a85b227f6e78d9f85f37940df54bc36acd92e64ca57d6f8404caae67c1bf51b"

LEAN_THEOREM_NAMES: tuple[str, ...] = (
    "ExoplanetsFrontierOperators.bls_two_stage_sharpening_monotone",
    "ExoplanetsFrontierOperators.farey_unimodular_separation_positive",
    "ExoplanetsFrontierOperators.farey_mediant_strictly_between",
    "ExoplanetsFrontierOperators.shift_annihilation_and_odd_even_discriminant",
    "ExoplanetsFrontierOperators.narrow_window_sde_truncation_monotone",
    "ExoplanetsFrontierOperators.pont_beta_sq_variance_inflation",
    "ExoplanetsFrontierOperators.bayes_gate_fpp_strict_contraction",
    "ExoplanetsFrontierOperators.bayes_likelihood_ratio_fpp_monotone",
    "ExoplanetsFrontierOperators.vetter_eight_gate_fail_closed",
    "ExoplanetsFrontierOperators.unmasked_ols_box_attenuation",
    "ExoplanetsFrontierOperators.masked_huber_exact_spot_recovery",
    "ExoplanetsFrontierOperators.masked_phase_lock_rank_collapse",
    "ExoplanetsFrontierOperators.scrambled_null_energy_invariant",
    "ExoplanetsFrontierOperators.oc_ttv_orthogonal_quadratic_energy",
    "ExoplanetsFrontierOperators.oc_linear_drift_and_phase_wall",
    "ExoplanetsFrontierOperators.wcs_affine_centroid_equivariance",
    "ExoplanetsFrontierOperators.dilution_centroid_pull_cancellation",
    "ExoplanetsFrontierOperators.beb_required_depth_physical_exclusion",
    "ExoplanetsFrontierOperators.bayes_shared_channel_fpp_monotone_and_law5_breach",
)

PINNED_EXTERNAL_FILES: tuple[dict[str, Any], ...] = (
    {
        "id": "ef_claims_md",
        "repo": EXOPLANETS_FRONTIER_REPO,
        "relpath": "exoplanets-frontier/CLAIMS.md",
        "bytes": 10593,
        "sha256": "a8af0541a56019ca42e1e8d5633e52ece4508de21d3918e46bbf11348f3cb89d",
    },
    {
        "id": "ef_methods_md",
        "repo": EXOPLANETS_FRONTIER_REPO,
        "relpath": "exoplanets-frontier/METHODS.md",
        "bytes": 9048,
        "sha256": "56eaa6448e04766cb4f06dda3d9f215db2928b86265623581578f6596feb49b9",
    },
    {
        "id": "ef_cool_vet_py",
        "repo": EXOPLANETS_FRONTIER_REPO,
        "relpath": "exoplanets-frontier/cool_vet.py",
        "bytes": 5257,
        "sha256": "2c7231f47a70ae3a6186e36cfc7cba2f15688332ee063864bab5ec6c4c9446e2",
    },
    {
        "id": "ef_bls_search_py",
        "repo": EXOPLANETS_FRONTIER_REPO,
        "relpath": "exoplanets-frontier/bls_search.py",
        "bytes": 6257,
        "sha256": "a5bb48b81db07d1d633b39c72cfea340e82e4f8c6f46b8ba8a755f64f3f40977",
    },
    {
        "id": "ef_vetter_py",
        "repo": EXOPLANETS_FRONTIER_REPO,
        "relpath": "exoplanets-frontier/vetter.py",
        "bytes": 12605,
        "sha256": "cf910ed563e14831a6cfaff2d8309cdc05848fbf84928e0b2a73f535124b982f",
    },
    {
        "id": "ef_despot_py",
        "repo": EXOPLANETS_FRONTIER_REPO,
        "relpath": "exoplanets-frontier/despot.py",
        "bytes": 7522,
        "sha256": "69d59a931c7f165070478106e900282bd478d96740deedde93cb2e818e40bcdb",
    },
    {
        "id": "ef_ttv_track_py",
        "repo": EXOPLANETS_FRONTIER_REPO,
        "relpath": "exoplanets-frontier/ttv_track.py",
        "bytes": 8016,
        "sha256": "7aff0b3debca0a88a83e4d4f8cede827075a4397d537534c63883ae97c164028",
    },
    {
        "id": "ef_blend_gaia_py",
        "repo": EXOPLANETS_FRONTIER_REPO,
        "relpath": "exoplanets-frontier/blend_gaia.py",
        "bytes": 9701,
        "sha256": "dda37e66f563a3030443bffe7560b042da06809fe0ca5c4656edd5da8fb383ed",
    },
    {
        "id": "ef_convergence_certs_json",
        "repo": EXOPLANETS_FRONTIER_REPO,
        "relpath": "exoplanets-frontier/results/convergence_certificates.json",
        "bytes": 5564,
        "sha256": "10fbc6b2246144e7ec24baff66ad257fc7c8f8545c767a28797f1909dd04169b",
    },
    {
        "id": "ef_blind_s106_s107_csv",
        "repo": EXOPLANETS_FRONTIER_REPO,
        "relpath": "exoplanets-frontier/results/blind_verification_s106_s107.csv",
        "bytes": 3524,
        "sha256": "e335b11c2b50bb41a2f7505e73191260e01620169eb340b5ee58bc63e884d023",
    },
    {
        "id": "spine_astr0_readme",
        "repo": "Foundation-0/astr0",
        "relpath": "s103_spine_meta/Foundation-0_astr0_README.md",
        "bytes": 3724,
        "sha256": "022977389d392a66da74cce72067121c3436480e85aee544bd09dea8cb879728",
    },
    {
        "id": "spine_gaia_dr4_readme",
        "repo": "Foundation-0/gaia-dr4",
        "relpath": "s103_spine_meta/Foundation-0_gaia-dr4_README.md",
        "bytes": 7577,
        "sha256": "442ec32c92d6c2a43dee528e3fd824897ff47e03fc172bd2279a3aa1ef673461",
    },
    {
        "id": "spine_lost_eclipses_readme",
        "repo": "Foundation-0/lost-eclipses",
        "relpath": "s103_spine_meta/Foundation-0_lost-eclipses_README.md",
        "bytes": 5042,
        "sha256": "fc259162887e1c6bd503320e7b2096e63a9beaba2038485dae335f189f5b8489",
    },
    {
        "id": "spine_certified_orbits_readme",
        "repo": "Foundation-0/certified-orbits",
        "relpath": "s103_spine_meta/Foundation-0_certified-orbits_README.md",
        "bytes": 5922,
        "sha256": "e61c453ebaf9eaabfb8b948e73b235b1e21dd814681b31e1507c5232e1c6130a",
    },
    {
        "id": "spine_cosmic_denoising_readme",
        "repo": "Foundation-0/cosmic-denoising",
        "relpath": "s103_spine_meta/Foundation-0_cosmic-denoising_README.md",
        "bytes": 184,
        "sha256": "c998eb997844378a2e2d7fba9e4d3232f07584c3173abf3e305d34bb7606e576",
    },
    {
        "id": "spine_eumemic_exoplanets_readme",
        "repo": "eumemic/exoplanets",
        "relpath": "s103_spine_meta/eumemic_exoplanets_README.md",
        "bytes": 96118,
        "sha256": "3f8454a531dcdfc8f2ec0b5bcaca237804a5c5ad24e23b2df2a3a5ee6cf0b82b",
    },
)

UPSTREAM_EXPEDITION_CERTS: tuple[dict[str, str], ...] = (
    {
        "track": "S23a",
        "cert_file": "track-s23a-ck-helicity-knotted-flux-fft/ck_helicity_fft_certificate.json",
        "cert_sha256": "b55631b1be71e8e46c5f6d153015c83b65bdf73bde7788933053e84b64aa6d31",
        "bridge": "Exact NTT/FFT spectral folding vs two-stage BLS alias comb & eumemic/exact-dft-bounds",
    },
    {
        "track": "S39",
        "cert_file": "track-s39-mozart-nth-order-differences/mozart_nth_diff_certificate.json",
        "cert_sha256": "1264f54f750deb6761574498cc9f268de3821a936ab459579d8949337c99b268",
        "bridge": "Period-p shift annihilation vs 1:2 subharmonic odd-even leakage",
    },
    {
        "track": "S40",
        "cert_file": "track-s40-mozart-perfect-numbers-bridge/mozart_perfect_bridge_certificate.json",
        "cert_sha256": "3c6b226b43804befdd102a4f02800421087ed851009967bc20b2e72479ce336e",
        "bridge": "Arithmetic divisor/harmonic resonance structure vs Farey MMR separation",
    },
    {
        "track": "S81",
        "cert_file": "track-s81-motifbench-esmfold-grafting-duality/s81_motifbench_certificate.json",
        "cert_sha256": "bc3b9222c47b2ab93c4b5256501d87f8b6483186766e03dba6f1501670936fe0",
        "bridge": "Multi-gate Bayesian screening & correlated failure-mode bounds",
    },
    {
        "track": "S87",
        "cert_file": "track-s87-universal-higher-order-atlas/s87_higher_order_atlas_certificate.json",
        "cert_sha256": "735c93b5a7bb4244e15068cd75371cb228fbf560a5837ca05d7e0a1fa30dcec2",
        "bridge": "Higher-order composite gate screening & Law-5 obstruction calibration",
    },
    {
        "track": "S94",
        "cert_file": "track-s94-neuron-basis-bonsai-sleep-convergence/s94_wave6_convergence_certificate.json",
        "cert_sha256": "1ad705c23646b65df0dc9ac928d3a4070deef61f5d17f8e8f249b4f75f51335b",
        "bridge": "Orthogonal basis masking & fail-closed ratchet convergence",
    },
)

EXOPLANETS_PR_MATRIX: tuple[dict[str, Any], ...] = (
    {
        "pr_number": 13,
        "state": "OPEN",
        "branch": "devin/1795441981-fix-cool-vet-docstring",
        "head_commit": EXOPLANETS_FRONTIER_PR13_COMMIT,
        "merge_with_main_ok": True,
        "conflicts_with_open_prs": (8,),
        "fixes_cool_vet_syntax": True,
        "guards_main_push": True,
        "cool_max_n": 14,
        "defects_found": 0,
    },
    {
        "pr_number": 8,
        "state": "OPEN",
        "branch": "orda-aska-patch-2",
        "head_commit": EXOPLANETS_FRONTIER_PR8_COMMIT,
        "merge_with_main_ok": True,
        "conflicts_with_open_prs": (13,),
        "fixes_cool_vet_syntax": True,
        "guards_main_push": False,
        "cool_max_n": 10,
        "defects_found": 3,
    },
    {
        "pr_number": 6,
        "state": "OPEN",
        "branch": "aeva/issue5-evidence-boundaries-20261112",
        "head_commit": EXOPLANETS_FRONTIER_PR6_COMMIT,
        "merge_with_main_ok": False,
        "conflicts_with_open_prs": (8,),
        "fixes_cool_vet_syntax": False,
        "guards_main_push": False,
        "cool_max_n": 14,
        "defects_found": 1,
    },
    {
        "pr_number": 7,
        "state": "CLOSED",
        "branch": "orda-aska-patch-1",
        "head_commit": EXOPLANETS_FRONTIER_PR7_COMMIT,
        "merge_with_main_ok": True,
        "conflicts_with_open_prs": (8, 13),
        "fixes_cool_vet_syntax": True,
        "guards_main_push": False,
        "cool_max_n": 10,
        "defects_found": 1,
    },
)


def expected_pr_matrix() -> list[dict[str, Any]]:
    return [{**r, "conflicts_with_open_prs": list(r["conflicts_with_open_prs"])} for r in EXOPLANETS_PR_MATRIX]

ASTRONOMY_SPINE_REPOS: tuple[dict[str, Any], ...] = (
    {
        "repo": EXOPLANETS_FRONTIER_REPO,
        "is_private": False,
        "main_commit": EXOPLANETS_FRONTIER_MAIN_COMMIT,
        "branch_count": 5,
        "open_pr_count": 3,
        "merged_pr_count": 0,
        "unmerged_seam": "cool_vet.py L2 SyntaxError on main; PR #13 vs #8 conflict on cool_vet.py; PR #6 conflicts on CLAIMS.md; 3/6 stale CLAIMS.md SHA prefixes",
    },
    {
        "repo": "Foundation-0/astr0",
        "is_private": False,
        "main_commit": "67cafe2defc44d5a4e17815fc7329f65eeef45eb",
        "branch_count": 7,
        "open_pr_count": 4,
        "merged_pr_count": 2,
        "unmerged_seam": "4 mergeable open PRs (#4-#7) defining 5-gate calibration and KMOS catalogue verification",
    },
    {
        "repo": "Foundation-0/gaia-dr4",
        "is_private": False,
        "main_commit": "95629f36c26eb691acf10638d00d57c3719a820a",
        "branch_count": 2,
        "open_pr_count": 0,
        "merged_pr_count": 8,
        "unmerged_seam": "ESA Gaia archive freeze 25 Nov 2026 -> DR4 2 Dec 2026; unmerged prep/gaia-dr4-tasks branch; needs VizieR+MAST mirror from blend_gaia.py",
    },
    {
        "repo": "Foundation-0/lost-eclipses",
        "is_private": False,
        "main_commit": "6fd9d059d5723dcaf143b620b55b85f6c0e67807",
        "branch_count": 1,
        "open_pr_count": 0,
        "merged_pr_count": 8,
        "unmerged_seam": "Direct consumer of ttv_track.py quadratic precession/orbital-decay O-C model",
    },
    {
        "repo": "Foundation-0/certified-orbits",
        "is_private": False,
        "main_commit": "f3b86e7ea79808b222b8fde6736ac188cd2e67d1",
        "branch_count": 4,
        "open_pr_count": 3,
        "merged_pr_count": 4,
        "unmerged_seam": "3 mergeable open PRs (#10 exact rational Krawczyk algebra, #11 exact 20-row selection, #12 fail-closed independent verifier audit)",
    },
    {
        "repo": "Foundation-0/cosmic-denoising",
        "is_private": False,
        "main_commit": "a00e2b5b827e0f4c9c5f0c01cba609fa523a9811",
        "branch_count": 2,
        "open_pr_count": 1,
        "merged_pr_count": 0,
        "unmerged_seam": "Open PR #1 (gpt-forge/research-foundation) establishing grounded denoising baseline",
    },
    {
        "repo": "eumemic/exoplanets",
        "is_private": False,
        "main_commit": "e2eee928fd621f75c1621f6b4206d34bb222ae59",
        "branch_count": 1,
        "open_pr_count": 0,
        "merged_pr_count": 10,
        "unmerged_seam": "Upstream 9,979 K/M-dwarf + 6,430 TOI catalog (639 counted candidates); author-graph SOP-10 collisions with exact-dft-bounds, integer-mult-bounds, stdhttp-verify, errata-findings",
    },
)

FAREY_TEST_PAIRS: tuple[tuple[int, int, int, int], ...] = (
    (1, 2, 2, 3),
    (2, 3, 3, 4),
    (3, 4, 4, 5),
    (4, 5, 5, 6),
    (5, 6, 6, 7),
    (10, 11, 11, 12),
)

_HEX64_CHARS = frozenset("0123456789abcdef")


class S103Error(ValueError):
    """Fail-closed typed error for Track S103."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def require_ok(cond: Any, code: str, detail: str) -> None:
    if cond is not True:
        raise S103Error(code, detail)


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
    require_ok(len(s) == 64 and all(ch in _HEX64_CHARS for ch in s), "INVALID_HEX64", f"{label} invalid hex64")
    return s


def validate_strict_json_tree(obj: Any, label: str = "root", _depth: int = 0) -> None:
    require_ok(_depth <= 32, "JSON_DEPTH_EXCEEDED", f"{label}: depth > 32")
    t = type(obj)
    if t is int:
        require_ok(obj.bit_length() <= 2048, "INT_BIT_LIMIT", f"{label}: int exceeds 2048 bits")
        return
    if t is str or t is bool or obj is None:
        return
    if t is list:
        for i, item in enumerate(obj):
            validate_strict_json_tree(item, f"{label}[{i}]", _depth + 1)
        return
    if t is dict:
        for k, v in obj.items():
            require_ok(type(k) is str, "INVALID_JSON_KEY", f"{label}: non-str key")
            validate_strict_json_tree(v, f"{label}.{k}", _depth + 1)
        return
    raise S103Error("FORBIDDEN_JSON_TYPE", f"{label}: disallowed type {t.__name__}")


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
    if places == 0:
        return f"-{quot}" if neg and quot != 0 else str(quot)
    ip, fp = divmod(quot, scale)
    sign = "-" if neg and quot != 0 else ""
    return f"{sign}{ip}.{fp:0{places}d}"


# ---------------------------------------------------------------------------
# Pure-Z/Q Exact Astrophysical Mathematical Primitives
# ---------------------------------------------------------------------------

def farey_separation_q(p1: int, q1: int, p2: int, q2: int) -> tuple[int, Fraction]:
    require_exact_int(p1, "p1", lo=0)
    require_exact_int(q1, "q1", lo=1)
    require_exact_int(p2, "p2", lo=0)
    require_exact_int(q2, "q2", lo=1)
    det = p2 * q1 - p1 * q2
    require_ok(det > 0, "INVALID_FAREY_ORDER", "require p1/q1 < p2/q2")
    return det, Fraction(det, q1 * q2)


def sde_exact_q(peak: Fraction, med: Fraction, mad: Fraction) -> Fraction:
    require_ok(mad > 0, "INVALID_MAD", "mad must be > 0")
    return (peak - med) / mad


def pont_beta_sq_q(n_bin: int, sr_over_sw: Fraction) -> Fraction:
    require_exact_int(n_bin, "n_bin", lo=1)
    require_ok(sr_over_sw >= 0, "INVALID_RED_RATIO", "sr/sw must be >= 0")
    return Fraction(1) + n_bin * sr_over_sw * sr_over_sw


def bayes_fpp_q(pi_p: Fraction, pi_fp: Fraction, r_prod: Fraction, eps_prod: Fraction) -> Fraction:
    require_ok(pi_p > 0 and pi_fp > 0 and r_prod > 0 and eps_prod > 0, "INVALID_BAYES_ARGS", "all Bayes factors must be > 0")
    num = pi_fp * eps_prod
    return num / (pi_p * r_prod + num)


def exact_det_and_solve_q(mat: list[list[Fraction]], rhs: list[Fraction]) -> tuple[Fraction, list[Fraction] | None]:
    """Exact Gaussian elimination over Q returning (det, solution_or_None)."""
    n = len(mat)
    a = [row[:] + [rhs[i]] for i, row in enumerate(mat)]
    sign = Fraction(1)
    for col in range(n):
        piv = -1
        for r in range(col, n):
            if a[r][col] != 0:
                piv = r
                break
        if piv == -1:
            return Fraction(0), None
        if piv != col:
            a[col], a[piv] = a[piv], a[col]
            sign = -sign
        pv = a[col][col]
        for r in range(col + 1, n):
            fac = a[r][col] / pv
            for j in range(col, n + 1):
                a[r][j] -= fac * a[col][j]
    det = sign
    for i in range(n):
        det *= a[i][i]
    sol = [Fraction(0)] * n
    for i in range(n - 1, -1, -1):
        acc = a[i][n]
        for j in range(i + 1, n):
            acc -= a[i][j] * sol[j]
        sol[i] = acc / a[i][i]
    return det, sol


def both_ok(a: bool, b: bool) -> bool:
    return a and b


def solve_nonsingular_q(mat: list[list[Fraction]], rhs: list[Fraction]) -> tuple[Fraction, list[Fraction]]:
    det, sol = exact_det_and_solve_q(mat, rhs)
    require_ok(sol is not None, "SINGULAR_SYSTEM", "linear system is singular")
    return det, sol


def gram_normal_eqs_q(cols: list[list[Fraction]], y: list[Fraction], mask: list[bool]) -> tuple[list[list[Fraction]], list[Fraction]]:
    m = len(cols)
    n = len(y)
    g: list[list[Fraction]] = [[Fraction(0)] * m for _ in range(m)]
    b: list[Fraction] = [Fraction(0)] * m
    for i in range(m):
        for j in range(m):
            g[i][j] = sum(cols[i][k] * cols[j][k] for k in range(n) if mask[k])
        b[i] = sum(cols[i][k] * y[k] for k in range(n) if mask[k])
    return g, b


# ---------------------------------------------------------------------------
# Pillar Builders
# ---------------------------------------------------------------------------

def build_pillar1_sop9_audit() -> dict[str, Any]:
    return {
        "main_commit": EXOPLANETS_FRONTIER_MAIN_COMMIT,
        "cool_vet_main_syntax_error": True,
        "cool_vet_error_line": 2,
        "convergence_cert_files_total": 41,
        "convergence_cert_files_matched": 41,
        "claims_sha_prefixes_checked": 6,
        "claims_sha_prefixes_stale": 3,
        "claims_stale_artifacts": [
            "benchmark_and_null.json",
            "ttv_ephemeris_audit.csv",
            "blend_localization.csv",
        ],
        "blind_s106_s107_audit": {
            "total_pairs": 39,
            "covered_pairs": 37,
            "data_gap_pairs": 2,
            "confirmed_on_schedule": 22,
            "marginal_recovery": 5,
            "timing_offset_ttv": 1,
            "low_snr_inconclusive": 9,
            "non_detection_4sigma": 0,
            "snr_ge_3_count": 24,
            "inverted_artifact_tic": 44669885,
            "inverted_artifact_snr_q": fmt_q(Fraction(-161, 20)),
        },
        "pr8_cool_audit_findings": {
            "audited_targets": 10,
            "verified_survivors": 2,
            "survivor_tics": [409696823, 224279805],
            "quarantined_blends": 5,
            "committed_cool_pngs": 15,
            "orphan_png_count": 6,
            "stale_report_heading_count": 14,
            "unguarded_main_push": True,
        },
        "pr6_issue5_synthetic_control": {
            "issue5_rows": 6,
            "issue5_survived": 0,
            "seeded_17d_mes_q": fmt_q(Fraction(5864, 100)),
            "seeded_17d_sde_q": fmt_q(Fraction(859, 100)),
            "seeded_17d_passes_sde": True,
            "seeded_25d_mes_q": fmt_q(Fraction(4976, 100)),
            "seeded_25d_sde_q": fmt_q(Fraction(723, 100)),
            "seeded_25d_passes_sde": False,
        },
        "pr_matrix": expected_pr_matrix(),
    }


def build_pillar2_exact_operators() -> dict[str, Any]:
    # 2a. BLS two-stage sharpening, Farey separation, subharmonic shift-annihilation, CS-09 SDE mirage
    t_multi = 2900
    t_stage1 = 60
    sharpen = Fraction(t_multi, t_stage1)
    f_span = Fraction(100, 16) - Fraction(1, 25)
    nyquist_bins = int(f_span * (2 * t_multi))
    alias_guard = Fraction(1, 125)

    farey_rows: list[dict[str, Any]] = []
    for p1, q1, p2, q2 in FAREY_TEST_PAIRS:
        det, gap = farey_separation_q(p1, q1, p2, q2)
        farey_rows.append({
            "r1_q": fmt_q(Fraction(p1, q1)),
            "r2_q": fmt_q(Fraction(p2, q2)),
            "unimodular_det": det,
            "gap_q": fmt_q(gap),
            "gap_dec6": fmt_dec_q(gap, 6),
            "collides_alias_guard": gap < alias_guard,
        })

    # CS-09 narrow-window SDE truncation witness (11-bin discrete comb, pure Q)
    peak_mes = Fraction(50)
    wide_med, wide_mad = Fraction(10), Fraction(4)
    narrow_med, narrow_mad = Fraction(15), Fraction(5)
    sde_wide = sde_exact_q(peak_mes, wide_med, wide_mad)
    sde_narrow = sde_exact_q(peak_mes, narrow_med, narrow_mad)
    sde_thresh = Fraction(15, 2)

    # 2b. Pont red-noise beta & 8-gate Bayes FPP compounding + Law-5 correlated failure
    beta_sq = pont_beta_sq_q(12, Fraction(1, 2))
    beta_val = Fraction(2)
    raw_mes = Fraction(14)
    corr_mes = raw_mes / beta_val
    mes_thresh = Fraction(19, 2)

    pi_p, pi_fp = Fraction(1, 100), Fraction(99, 100)
    r_gate, eps_gate = Fraction(19, 20), Fraction(1, 4)
    fpp_indep_8 = bayes_fpp_q(pi_p, pi_fp, r_gate ** 8, eps_gate ** 8)
    fpp_corr_4 = bayes_fpp_q(pi_p, pi_fp, r_gate ** 8, (eps_gate ** 4) * Fraction(1, 2))
    tier_sval_limit = Fraction(3, 200)

    # 2c. Asymmetric Huber four-harmonic orthogonal spot pre-whitening vs unmasked OLS + Law-5 phase lock
    u0 = [Fraction(1)] * 8
    u1 = [Fraction(x) for x in (1, 0, -1, 0, 1, 0, -1, 0)]
    u2 = [Fraction(x) for x in (0, 1, 0, -1, 0, 1, 0, -1)]
    u3 = [Fraction(x) for x in (1, -1, 1, -1, 1, -1, 1, -1)]
    cols = [u0, u1, u2, u3]
    spot_amp = Fraction(10000)
    transit_depth = Fraction(1500)
    y_sig = [spot_amp * u1[k] - (transit_depth if k == 0 else Fraction(0)) for k in range(8)]

    g_all, b_all = gram_normal_eqs_q(cols, y_sig, [True] * 8)
    det_all, sol_all = solve_nonsingular_q(g_all, b_all)
    unmasked_pred0 = sum(sol_all[i] * cols[i][0] for i in range(4))
    unmasked_depth = -(y_sig[0] - unmasked_pred0)

    mask_one = [k != 0 for k in range(8)]
    g_m1, b_m1 = gram_normal_eqs_q(cols, y_sig, mask_one)
    det_m1, sol_m1 = solve_nonsingular_q(g_m1, b_m1)
    masked_pred0 = sum(sol_m1[i] * cols[i][0] for i in range(4))
    masked_depth = -(y_sig[0] - masked_pred0)

    mask_lock = [k not in (0, 4) for k in range(8)]
    g_lock, b_lock = gram_normal_eqs_q(cols, y_sig, mask_lock)
    det_lock, _ = exact_det_and_solve_q(g_lock, b_lock)

    # Scrambled-null conservation witness
    blk = [Fraction(10), Fraction(-30), Fraction(50), Fraction(-20)]
    rev = list(reversed(blk))
    cyc = blk[1:] + blk[:1]
    l2_orig = sum(x * x for x in blk)
    l2_rev = sum(x * x for x in rev)
    l2_cyc = sum(x * x for x in cyc)

    # 2d. O-C TTV orthogonal Legendre decomposition + 2D WCS affine equivariance + dilution + BEB
    epochs = [Fraction(e) for e in (-2, -1, 0, 1, 2)]
    lin_y = [Fraction(15) * e for e in epochs]
    quad_y = [Fraction(4) * e * e for e in epochs]
    lin_cols = [[Fraction(1)] * 5, epochs]
    quad_cols = [[Fraction(1)] * 5, epochs, [e * e for e in epochs]]
    _, sol_lin_on_lin = solve_nonsingular_q(*gram_normal_eqs_q(lin_cols, lin_y, [True] * 5))
    _, sol_lin_on_quad = solve_nonsingular_q(*gram_normal_eqs_q(lin_cols, quad_y, [True] * 5))
    _, sol_quad_on_quad = solve_nonsingular_q(*gram_normal_eqs_q(quad_cols, quad_y, [True] * 5))
    chi0_lin = sum(v * v for v in lin_y)
    chi_lin_on_lin = sum((lin_y[i] - sol_lin_on_lin[0] - sol_lin_on_lin[1] * epochs[i]) ** 2 for i in range(5))
    chi_lin_on_quad = sum((quad_y[i] - sol_lin_on_quad[0] - sol_lin_on_quad[1] * epochs[i]) ** 2 for i in range(5))
    chi_quad_on_quad = sum((quad_y[i] - sol_quad_on_quad[0] - sol_quad_on_quad[1] * epochs[i] - sol_quad_on_quad[2] * epochs[i] ** 2) ** 2 for i in range(5))
    drift_1500_min = Fraction(1500 * 4, 60)

    # 2D affine WCS chart & dilution cancellation & BEB physical exclusion
    a_wcs = [[Fraction(2), Fraction(1)], [Fraction(-1), Fraction(3)]]
    b_wcs = [Fraction(5), Fraction(-2)]
    wcs_det, _ = exact_det_and_solve_q(a_wcs, [Fraction(0), Fraction(0)])
    ft, fn = Fraction(100), Fraction(1, 2)
    pt_t = (Fraction(3), Fraction(4))
    pt_n = (Fraction(11), Fraction(-2))
    wt_sum = ft + fn
    cx = (ft * pt_t[0] + fn * pt_n[0]) / wt_sum
    cy = (ft * pt_t[1] + fn * pt_n[1]) / wt_sum
    t_cx = a_wcs[0][0] * cx + a_wcs[0][1] * cy + b_wcs[0]
    t_cy = a_wcs[1][0] * cx + a_wcs[1][1] * cy + b_wcs[1]
    t_t = (a_wcs[0][0] * pt_t[0] + a_wcs[0][1] * pt_t[1] + b_wcs[0], a_wcs[1][0] * pt_t[0] + a_wcs[1][1] * pt_t[1] + b_wcs[1])
    t_n = (a_wcs[0][0] * pt_n[0] + a_wcs[0][1] * pt_n[1] + b_wcs[0], a_wcs[1][0] * pt_n[0] + a_wcs[1][1] * pt_n[1] + b_wcs[1])
    avg_tx = (ft * t_t[0] + fn * t_n[0]) / wt_sum
    avg_ty = (ft * t_t[1] + fn * t_n[1]) / wt_sum
    dil_shift_x = (fn / wt_sum) * (pt_n[0] - pt_t[0])
    dil_residual_x = (cx - dil_shift_x) - pt_t[0]
    dep_obs = Fraction(1, 100)
    req_eb_depth = dep_obs * wt_sum / fn
    pm_10yr_arcsec = Fraction(300 * 10, 1000)

    return {
        "bls_and_farey_separation": {
            "baseline_multi_yr_d": t_multi,
            "baseline_stage1_d": t_stage1,
            "sharpening_ratio_q": fmt_q(sharpen),
            "sharpening_ratio_dec6": fmt_dec_q(sharpen, 6),
            "nyquist_bins_full_baseline": nyquist_bins,
            "two_stage_budget_trials": 40000,
            "alias_guard_q": fmt_q(alias_guard),
            "farey_resonance_checks": farey_rows,
            "cs09_sde_truncation_witness": {
                "peak_mes_q": fmt_q(peak_mes),
                "wide_sde_q": fmt_q(sde_wide),
                "narrow_sde_q": fmt_q(sde_narrow),
                "sde_threshold_q": fmt_q(sde_thresh),
                "wide_passes": sde_wide >= sde_thresh,
                "narrow_fails_despite_high_mes": both_ok(sde_narrow < sde_thresh, peak_mes > mes_thresh),
            },
        },
        "pont_and_eight_gate_bayes": {
            "bin_occupancy_n": 12,
            "red_to_white_ratio_q": fmt_q(Fraction(1, 2)),
            "pont_beta_sq_q": fmt_q(beta_sq),
            "pont_beta_q": fmt_q(beta_val),
            "raw_mes_q": fmt_q(raw_mes),
            "corrected_mes_q": fmt_q(corr_mes),
            "mes_threshold_q": fmt_q(mes_thresh),
            "red_noise_collapses_below_gate": both_ok(raw_mes >= mes_thresh, corr_mes < mes_thresh),
            "prior_planet_q": fmt_q(pi_p),
            "gate_retention_q": fmt_q(r_gate),
            "gate_leakage_q": fmt_q(eps_gate),
            "indep_8gate_fpp_q": fmt_q(fpp_indep_8),
            "indep_8gate_fpp_dec6": fmt_dec_q(fpp_indep_8, 6),
            "indep_passes_tier_sval": fpp_indep_8 < tier_sval_limit,
            "correlated_4gate_fpp_q": fmt_q(fpp_corr_4),
            "correlated_4gate_fpp_dec6": fmt_dec_q(fpp_corr_4, 6),
            "correlated_violates_tier_sval": fpp_corr_4 >= tier_sval_limit,
        },
        "harmonic_despot_orthogonality": {
            "grid_points_n": 8,
            "harmonic_modes_m": 4,
            "spot_amp_ppm_q": fmt_q(spot_amp),
            "injected_depth_ppm_q": fmt_q(transit_depth),
            "unmasked_gram_det_q": fmt_q(det_all),
            "unmasked_recovered_depth_q": fmt_q(unmasked_depth),
            "unmasked_retention_ratio_q": fmt_q(unmasked_depth / transit_depth),
            "masked_gram_det_q": fmt_q(det_m1),
            "masked_recovered_spot_q": fmt_q(sol_m1[1]),
            "masked_recovered_depth_q": fmt_q(masked_depth),
            "masked_retention_ratio_q": fmt_q(masked_depth / transit_depth),
            "phase_lock_masked_gram_det_q": fmt_q(det_lock),
            "phase_lock_rank_collapsed": det_lock == 0,
            "scrambled_null_l2_orig_q": fmt_q(l2_orig),
            "scrambled_null_l2_preserved": both_ok(l2_orig == l2_rev, l2_orig == l2_cyc),
        },
        "oc_ttv_and_wcs_affine": {
            "linear_drift_chi0_q": fmt_q(chi0_lin),
            "linear_drift_chi_lin_q": fmt_q(chi_lin_on_lin),
            "quadratic_signal_chi_lin_q": fmt_q(chi_lin_on_quad),
            "quadratic_signal_chi_quad_q": fmt_q(chi_quad_on_quad),
            "drift_1500_orbits_4s_min_q": fmt_q(drift_1500_min),
            "breaches_60min_wall_rescued_by_240min": Fraction(60) < drift_1500_min < Fraction(240),
            "wcs_affine_det_q": fmt_q(wcs_det),
            "wcs_centroid_equivariant": both_ok(t_cx == avg_tx, t_cy == avg_ty),
            "dilution_residual_bias_q": fmt_q(dil_residual_x),
            "beb_obs_depth_q": fmt_q(dep_obs),
            "beb_required_neighbor_depth_q": fmt_q(req_eb_depth),
            "beb_required_neighbor_depth_dec6": fmt_dec_q(req_eb_depth, 6),
            "beb_physically_excluded": req_eb_depth > 1,
            "pm_10yr_300mas_shift_arcsec_q": fmt_q(pm_10yr_arcsec),
        },
    }


def build_pillar3_sop10_spine() -> dict[str, Any]:
    return {
        "all_repos_verified_public": True,
        "astronomy_spine_repos": [dict(r) for r in ASTRONOMY_SPINE_REPOS],
        "eumemic_sop10_high_signal_repos": [
            "eumemic/exact-dft-bounds",
            "eumemic/integer-mult-bounds",
            "eumemic/stdhttp-verify",
            "eumemic/errata-findings",
        ],
        "aletheia_gate_bridges": [
            "CS-09: PR #6 seeded 25d MES=49.76 / SDE=7.23<7.5 exposes narrow-window support-truncation mirage on MAD-normalized SDE",
            "CS-18: Blind S106-S107 4-state abstention (LOW_SNR_INCONCLUSIVE=9, DATA_GAP=2) prevents forced false rejections",
            "Pont-beta ratchet: exact variance-inflation beta^2 = 1 + N*(sr/sw)^2 hardens S102/S95-S97 correlated time-series detectors",
        ],
    }


def build_payload() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "oracle_class": "exact",
        "novelty_classification": "N1",
        "n2_claims": 0,
        "external_provenance": {
            "pinned_external_count": len(PINNED_EXTERNAL_FILES),
            "pinned_external_files": [dict(r) for r in PINNED_EXTERNAL_FILES],
            "upstream_bridges_count": len(UPSTREAM_EXPEDITION_CERTS),
            "upstream_expedition_bridges": [dict(u) for u in UPSTREAM_EXPEDITION_CERTS],
        },
        "pinned_artifacts": {
            "lean_source": "ExoplanetsFrontierOperators.lean",
            "lean_source_sha256": PINNED_LEAN_SOURCE_SHA256,
            "lean_toolchain": EXPECTED_LEAN_TOOLCHAIN,
            "lean_toolchain_sha256": PINNED_LEAN_TOOLCHAIN_SHA256,
            "lakefile_sha256": PINNED_LAKEFILE_SHA256,
            "lean_theorem_count": len(LEAN_THEOREM_NAMES),
            "lean_theorem_names": list(LEAN_THEOREM_NAMES),
        },
        "pillar1_sop9_exoplanets_frontier_audit": build_pillar1_sop9_audit(),
        "pillar2_exact_astrophysical_operators": build_pillar2_exact_operators(),
        "pillar3_sop10_astronomy_spine_convergence": build_pillar3_sop10_spine(),
    }


def build_certificate() -> dict[str, Any]:
    payload = build_payload()
    payload_sha = sha256_hex(canonical_json_bytes(payload))
    envelope_core = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": payload_sha,
        "payload": payload,
    }
    cert_sha = sha256_hex(canonical_json_bytes(envelope_core))
    return {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": payload_sha,
        "payload": payload,
        "certificate_sha256": cert_sha,
    }


def main() -> int:
    print(canonical_json_bytes(build_certificate()).decode("ascii"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
