"""
`aletheia.portal_interpose`: CS-28 (`SOP-19`) Standalone Turn-0 Domain-Stripped
Full-Portfolio Interposition Engine & Fail-Closed Law-5 Guard.

Strips surface disciplinary labels into coordinate-/domain-free mathematical
primitives (`Stage A`), scores every orthogonal active portfolio pillar in
exact `fractions.Fraction` arithmetic, optionally queries a persistent read-only
SQLite epistemic archive, and enforces the fail-closed Law-5 guard requiring
either an explicit typed operator map or an explicit structural obstruction
before any Turn-0 hit can advance beyond `CANDIDATE_NEEDS_PROOF`.

Stdlib-only, zero hardcoded host paths, zero bare asserts, safe across all
R4 isolated modes (`-I -B`, `-I -O -B`, `-I -B -W error`).
"""
from __future__ import annotations

from fractions import Fraction
import os
from pathlib import Path
import re
import sqlite3
import stat
from typing import Any, Sequence
import urllib.parse

from aletheia import _strict_zone_b as _zb

__all__ = [
    "DEFAULT_PILLAR_SPECS",
    "PILLAR_ARCHIVE_ANCHORS",
    "PortalInterposeError",
    "strip_domain_labels",
    "score_domain_stripped_pillars",
    "query_sqlite_archive",
    "enforce_law5_interpose_guard",
    "interpose_portal",
    "run_cs28_regression_fixtures",
]

_DOMAIN_LABEL_RE = re.compile(
    r"\b(?:"
    r"neuroscience|neurobiology|prefrontal\s+cortex|drosophila|fly\s+brain|connectomics?"
    r"|computational\s+geometry|convex\s+geometry|pure\s+mathematics|condensed\s+matter"
    r"|high[- ]energy\s+physics|machine\s+learning|deep\s+learning|large\s+language\s+models?"
    r"|quantization\s+benchmark|neural\s+networks?"
    r")\b",
    re.IGNORECASE,
)

_OPERATOR_REL_RE = re.compile(
    r"[A-Za-z0-9_)\]}]\s*(?:=|:=|<=|>=|<->|->|\\to|\\le|\\ge)\s*[A-Za-z0-9_(\[{|\\]"
)
_OPERATOR_TERM_RE = re.compile(
    r"(?:\bFraction\b|\bcommutes\b|\b(?:exact|explicit|constructive)\s+(?:identity|equation|theorem|bound|map|operator)\b)"
)
_NEGATED_WITNESS_RE = re.compile(
    r"\bthere\s+(?:is|are)\s+no\b"
    r"|\b(?:does|do|did)\s+not\s+hold\b"
    r"|\bfails\s+to\s+hold\b"
    r"|\b(?:never|no\s+longer)\s+holds?\b"
    r"|\b(?:cannot|can't)\s+hold\b"
    r"|\bnot\s+valid\b"
    r"|\bis\s+(?:false|invalid)\b"
    r"|\b(?:no|not|without|never|none|nothing|neither|nor|lacks?|missing|absent|vacuous|pseudo|fake|cannot|can't)\b"
    r"(?:\s+[A-Za-z0-9_-]+){0,3}\s+"
    r"(?:identity|equation|map|operator|bridge|transfer|witness|theorem|bound|commutes|obstruction|impossibility|counterexample|wall)\b",
    re.IGNORECASE,
)
_REFUTED_TRANSFER_RE = re.compile(
    r"\b(?:refut\w*|disprov\w*|falsif\w*|counterexample\w*|impossib\w*|obstruct\w*|no[- ]go|invalid|fails)\b",
    re.IGNORECASE,
)
_OBSTRUCTION_WITNESS_RE = re.compile(
    r"(?:\bobstruct\w*|\bimpossib\w*|\bfails\b|\bwall\b|\bcounterexample\b|\bno[- ]go\b|\bstrict(?:ly)?\s+(?:larger|smaller|>|<)\b)"
    r"|(?:[A-Za-z0-9_)\]}]\s*(?:<|>|!=)\s*[A-Za-z0-9_(\[{|\\-])",
    re.IGNORECASE,
)
_SMUGGLE_BUZZWORDS = (
    "sheaf",
    "duality",
    "curvature",
    "emergence",
    "holonomy",
    "topological",
    "isomorphism",
    "cohomology",
    "functor",
    "homotopy",
)

PILLAR_ARCHIVE_ANCHORS: dict[str, tuple[str, ...]] = {
    "optimization_quantization": ("siliquant", "blockh4", "weft", "quadlpt", "quantization", "codebook"),
    "architecture_silicon": ("holosphere", "silikernels", "fwht", "monarch", "cayley", "sm_86", "holoemit"),
    "pure_math_formal": ("math0", "quotient-lp-bounds", "incentre-lattices", "point-charges", "track-s105", "track-s161"),
    "bio_connectome": ("malecns", "track-s102", "drosophila", "connectome", "biosignal", "track-s162"),
    "physical_engineering": ("optifab", "point-charges", "gravity", "truss", "thermal"),
    "verification_swarm": ("Foundation-0/aletheia", "audit-check", "mutate", "track-s160", "cs-26"),
    "historical_heritage": ("bayt-al-hikma", "al-kashi", "ibn al-nafis", "ibn sina", "al-tusi", "al-biruni"),
}

# Tuple: (pillar_id, label, target_repos, tuple[(primitive_name, regex_pattern)])
DEFAULT_PILLAR_SPECS: tuple[tuple[str, str, str, tuple[tuple[str, str], ...]], ...] = (
    (
        "optimization_quantization",
        "Optimization & Quantization (SiliQuant / Weft)",
        "Moissanite-Labs/siliquant, Moissanite-Labs/weft, Track S20b/S73/S86/S163",
        (
            ("convex_covering_packing", r"\b(cover(?:ing|ed)?|homothet(?:ic|s)?|pack(?:ing|ed)?|voronoi|lattice|codebook|quantiz\w*|covering\s+radius|metric\s+entropy)\b"),
            ("ellipsoid_affine_whitening", r"\b(john(?:'s)?\s+(?:position|ellipsoid|contact)|l[oö]wner|ellipsoid|whiten\w*|precondition\w*|mean\s+width|anisotrop\w*|difference\s+body|support\s+function|orthogon\w*\s+cube)\b"),
            ("minimax_lp_chebyshev", r"\b(helly|chebyshev|minimax|l_?inf|linear\s+program|farkas|dual\s+cut|convex\s+hull|polytop\w*)\b"),
            ("discrete_sign_pruning_mask", r"\b(prun\w*|carv\w*|spars\w*|sign[- ]?flip|ternary|mask\w*|bit[- ]?pack\w*|rollback|low[- ]?rank|outlier)\b"),
        ),
    ),
    (
        "architecture_silicon",
        "Architecture & Silicon (HoloSphere / SiliKernels / HoloEmit / SiliSense)",
        "Moissanite-Labs/holosphere, Moissanite-Labs/silikernels, Moissanite-Labs/holoemit, Moissanite-Labs/silisense",
        (
            ("fast_transform_fourier_hadamard", r"\b(fourier|hadamard|fwht|walsh|monarch|butterfly|spectral|convolution|kernel)\b"),
            ("recurrent_loop_state_transport", r"\b(loop(?:ed|s|ing)?|recurren\w*|state[- ]?space|holonomy|cayley|su\(2\)|woodbury|fixed[- ]?point|contraction|multi[- ]?token|speculative)\b"),
            ("hardware_memory_sparsity", r"\b(hbm|sram|smem|cache|roofline|bandwidth|spill|cuda|ptx|avx|bitmap|paging|fault|syndrome|secded|canary)\b"),
        ),
    ),
    (
        "pure_math_formal",
        "Pure Math & Formal Proofs (math0 / quotient-lp-bounds / point-charges / incentre-lattices)",
        "Foundation-0/math0, Foundation-0/quotient-lp-bounds, Foundation-0/point-charges, Foundation-0/incentre-lattices",
        (
            ("combinatorial_matroid_polytope", r"\b(matroid|kazhdan|lusztig|z[- ]?polynomial|log[- ]?concav\w*|chow|gabidulin|spread\s+pack\w*|cross[- ]?polytope|simplex|polytop\w*|cauchy\s+perimeter|shadow\s+boundary)\b"),
            ("spectral_inertia_duality", r"\b(krein|sylvester|inertia|schur\s+complement|hodge|harmonic|laplacian|ghost\s+parity|self[- ]?adjoint|mellin|zeta|divisor|sieve|fluctuation)\b"),
            ("formal_lean_certificate", r"\b(lean\s*4|mathlib|formal(?:iz\w*|ly\s+verified)|axiom|certificate|unconditional|rigidity)\b"),
        ),
    ),
    (
        "bio_connectome",
        "Biological & Connectome Systems (MaleCNS Connectome / Biosignals)",
        "Track S102 (Drosophila MaleCNS), Track S162, Track S20c, cave-expedition",
        (
            ("neural_belief_message_passing", r"\b(belief\s+propagation|planning|factor\s+graph|cavity|bethe|message\s+passing|damping|loopy)\b"),
            ("signed_connectome_topology", r"\b(connectome|neuron\w*|synap\w*|dale(?:'s)?|excitatory|inhibitory|frustrat\w*|reciprocity|triad|motif|topology|routing\s+graph|carv\w*|signed\s+feedback\s+loops?)\b"),
            ("physiological_biosignal_dynamics", r"\b(ecg|cardiac|pulse|rhythmic|biosignal|liquid|continuous[- ]?time|lif|spik\w*|sensorimotor)\b"),
        ),
    ),
    (
        "physical_engineering",
        "Physical & Manufacturing Systems (OptiFab / Gravity / Mechanics)",
        "aska-physical/optifab, Foundation-0/point-charges, Track S153",
        (
            ("physical_mechanics_field", r"\b(gravity|gravimeter|channel\s+capacity|ostrogradsky|hamiltonian|symplectic|truss|thermal|aerospace|structural|equilibrium|electrostatic|fluid)\b"),
        ),
    ),
    (
        "verification_swarm",
        "Verification, Governance & Swarm Efficiency (Aletheia / CS-01..CS-29)",
        "Foundation-0/aletheia, Track S160, Track S166",
        (
            ("eval_governance_efficiency", r"\b(perplexity|benchmark|compaction|context\s+window|cache|swarm|collusion|reciprocity|verifier|audit|harness|mutation|fail[- ]?closed|prior[- ]?tilt|backdoor)\b"),
        ),
    ),
    (
        "historical_heritage",
        "Historical & Foundational Corpora (Bayt al-Hikma / SOP-16)",
        "Foundation-0/bayt-al-hikma, Tracks S89-S92/S150/S162",
        (
            ("classical_exact_operators", r"\b(fixed[- ]?radix|al[- ]?kashi|al[- ]?tusi|ibn\s+al[- ]?nafis|ibn\s+sina|septal|cavity|pulse|rotational|divisor|sieve|recurrence|iterative\s+contraction|convex\s+geometry|polyhedr\w*)\b"),
        ),
    ),
)

_VALID_DISPOSITIONS = frozenset({"CANDIDATE_ONLY", "EXACT_OPERATOR_TRANSFER", "STRUCTURAL_OBSTRUCTION"})


class PortalInterposeError(ValueError):
    """Fail-closed validation error for CS-28 Turn-0 interposition & Law-5 guard."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _require(cond: bool, code: str, message: str) -> None:
    if not cond:
        raise PortalInterposeError(code, message)


def _frac_str(val: Fraction) -> str:
    return f"{val.numerator}/{val.denominator}"


def _require_nonempty_str(val: Any, label: str) -> str:
    _require(type(val) is str and len(val.strip()) > 0, "EMPTY_OR_INVALID_TEXT", f"{label} must be non-empty str")
    return val


def _require_exact_int(val: Any, label: str, minimum: int = 0) -> int:
    _require(type(val) is int and val >= minimum, "INVALID_INT", f"{label} must be exact int >= {minimum}")
    return val


def strip_domain_labels(text: Any) -> dict[str, Any]:
    """Strip disciplinary labels into a domain-neutral text payload (`Law 5 Stage A`)."""
    raw = _require_nonempty_str(text, "text")
    found = sorted({m.group(0).strip().lower() for m in _DOMAIN_LABEL_RE.finditer(raw)})
    stripped = _DOMAIN_LABEL_RE.sub("[DOMAIN_LABEL]", raw)
    return {
        "stripped_text": stripped,
        "stripped_labels": found,
        "stripped_label_count": len(found),
    }


def score_domain_stripped_pillars(
    title: Any,
    text: Any,
    *,
    pillar_specs: Sequence[tuple[str, str, str, tuple[tuple[str, str], ...]]] = DEFAULT_PILLAR_SPECS,
) -> dict[str, Any]:
    """Strip disciplinary nouns and score orthogonal active portfolio pillars in exact `Fraction`."""
    clean_title = _require_nonempty_str(title, "title")
    clean_text = _require_nonempty_str(text, "text")
    _require(len(pillar_specs) > 0, "EMPTY_PILLAR_SPECS", "pillar_specs must be non-empty")

    stage_a = strip_domain_labels(f"{clean_title}\n{clean_text}")
    lowered = stage_a["stripped_text"].lower()

    rows: list[dict[str, Any]] = []
    for pid, label, repos, rules in pillar_specs:
        _require(len(rules) > 0, "EMPTY_PILLAR_RULES", f"pillar {pid!r} must have >= 1 primitive rule")
        matched: list[dict[str, Any]] = []
        term_hits = 0
        for prim_name, pat in rules:
            found = sorted({m.group(0).strip() for m in re.finditer(pat, lowered)})
            if found:
                matched.append({"primitive": prim_name, "terms": found[:8], "count": len(found)})
                term_hits += len(found)
        cov = Fraction(len(matched), len(rules))
        rows.append({
            "pillar": pid,
            "label": label,
            "repos": repos,
            "hit": term_hits > 0,
            "matched_primitive_count": len(matched),
            "total_primitives": len(rules),
            "primitive_coverage_q": _frac_str(cov),
            "score_hits": term_hits,
            "matched_primitives": matched,
            "required_action": (
                "AUDIT_EXACT_OPERATOR_TRANSFER_OR_OBSTRUCTION"
                if term_hits > 0
                else "CONFIRM_NA_OR_CHECK_DEEPER_PRIMITIVE"
            ),
            "_sort_cov": cov,
        })

    rows.sort(key=lambda r: (-r["_sort_cov"], -r["score_hits"], r["pillar"]))
    for row in rows:
        del row["_sort_cov"]

    return {
        "schema": "aletheia.turn0_interpose.v1",
        "law5_guard": "TURN0_CANDIDATES_ONLY_REQUIRE_EXACT_OPERATOR_OR_OBSTRUCTION",
        "title": clean_title,
        "stripped_labels": stage_a["stripped_labels"],
        "pillars_hit": sum(1 for r in rows if r["hit"]),
        "pillars_total": len(rows),
        "pillar_matrix": rows,
    }


def _verify_sqlite_sidecars(db_path: Path) -> None:
    """Reject symlinked `-wal`/`-shm` sidecars before opening SQLite read-only."""
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{db_path}{suffix}")
        try:
            st = os.lstat(sidecar)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise PortalInterposeError("ARCHIVE_IO_ERROR", f"sidecar lstat failed: {exc}") from exc
        _require(stat.S_ISREG(st.st_mode), "NOT_REGULAR_ARCHIVE", f"sidecar {sidecar.name} is not a regular file")


def query_sqlite_archive(
    rag_db_path: Any,
    pillar_id: Any,
    *,
    limit: int = 4,
    anchors_by_pillar: dict[str, tuple[str, ...]] = PILLAR_ARCHIVE_ANCHORS,
) -> list[dict[str, str]]:
    """Query an optional persistent SQLite epistemic archive strictly read-only (`?mode=ro` + `PRAGMA query_only`)."""
    pid = _require_nonempty_str(pillar_id, "pillar_id")
    lim = _require_exact_int(limit, "limit", 1)
    safe_p = _zb.verify_regular_file_path(
        rag_db_path,
        "rag_db_path",
        err_cls=PortalInterposeError,
        path_code="INVALID_ARCHIVE_PATH",
        not_reg_code="NOT_REGULAR_ARCHIVE",
        io_code="ARCHIVE_IO_ERROR",
    )
    _verify_sqlite_sidecars(safe_p)
    anchors = anchors_by_pillar.get(pid, ())
    if not anchors:
        return []

    priority = {"track": 0, "repo": 1, "portal": 2, "primary_treatise": 3, "hf_artifact": 4}
    encoded_path = urllib.parse.quote(str(safe_p), safe="/:")
    con: sqlite3.Connection | None = None
    try:
        before_st = os.lstat(safe_p)
        con = sqlite3.connect(f"file:{encoded_path}?mode=ro", uri=True)
        con.execute("PRAGMA query_only = ON")
        after_st = os.lstat(safe_p)
        _require(
            stat.S_ISREG(before_st.st_mode)
            and stat.S_ISREG(after_st.st_mode)
            and after_st.st_dev == before_st.st_dev
            and after_st.st_ino == before_st.st_ino,
            "NOT_REGULAR_ARCHIVE",
            "archive path changed during read-only open",
        )
        _verify_sqlite_sidecars(safe_p)
        seen: set[str] = set()
        candidates: list[tuple[int, str, str, str]] = []
        for kw in anchors:
            esc_kw = kw.lower().replace("!", "!!").replace("%", "!%").replace("_", "!_")
            like = f"%{esc_kw}%"
            rows = con.execute(
                "SELECT id, node_type, title FROM nodes "
                "WHERE lower(id) LIKE ? ESCAPE '!' OR lower(title) LIKE ? ESCAPE '!' OR lower(summary) LIKE ? ESCAPE '!' "
                "LIMIT 12",
                (like, like, like),
            ).fetchall()
            for nid, ntype, ntitle in rows:
                snid = str(nid)
                if snid not in seen:
                    seen.add(snid)
                    candidates.append((priority.get(str(ntype), 9), snid, str(ntype), str(ntitle)))
        candidates.sort(key=lambda item: (item[0], item[1]))
        return [{"node_id": nid, "kind": ntype, "title": ntitle[:115]} for _, nid, ntype, ntitle in candidates[:lim]]
    except OSError as exc:
        raise PortalInterposeError("ARCHIVE_IO_ERROR", f"archive lstat failed: {exc}") from exc
    except sqlite3.Error as exc:
        raise PortalInterposeError("ARCHIVE_SQLITE_ERROR", f"sqlite query failed: {exc}") from exc
    finally:
        if con is not None:
            con.close()


def enforce_law5_interpose_guard(claim_obj: Any) -> dict[str, Any]:
    """
    Fail-closed Law-5 guard separating Turn-0 candidate leads from verified bridges.

    Rejects:
      - Unknown dispositions (`INVALID_DISPOSITION`)
      - Promoting `EXACT_OPERATOR_TRANSFER` without typed objects and a non-negated
        operator witness or with buzzword-only smuggling (`LAW5_SMUGGLE_REJECTED` /
        `LAW5_MISSING_OPERATOR_WITNESS`)
      - Claiming `STRUCTURAL_OBSTRUCTION` without a non-negated obstruction witness
        (`LAW5_MISSING_OBSTRUCTION_WITNESS`).
    """
    _require(type(claim_obj) is dict, "INVALID_CLAIM_TYPE", "claim_obj must be a dict")
    pillar = _require_nonempty_str(claim_obj.get("pillar"), "pillar")
    disp = _require_nonempty_str(claim_obj.get("disposition"), "disposition")
    _require(disp in _VALID_DISPOSITIONS, "INVALID_DISPOSITION", f"invalid Law-5 disposition: {disp!r}")

    if disp == "CANDIDATE_ONLY":
        return {
            "schema": "aletheia.law5_interpose_guard.v1",
            "pillar": pillar,
            "status": "CANDIDATE_NEEDS_PROOF",
            "verified_bridge": False,
        }

    src = _require_nonempty_str(claim_obj.get("source_object"), "source_object")
    dst = _require_nonempty_str(claim_obj.get("target_object"), "target_object")
    witness = _require_nonempty_str(claim_obj.get("witness"), "witness")
    lowered = witness.lower()
    buzz_hits = sum(lowered.count(bw) for bw in _SMUGGLE_BUZZWORDS)
    is_negated = _NEGATED_WITNESS_RE.search(witness) is not None

    if disp == "EXACT_OPERATOR_TRANSFER":
        has_rel = _OPERATOR_REL_RE.search(witness) is not None
        has_term = _OPERATOR_TERM_RE.search(witness) is not None
        is_refuted = _REFUTED_TRANSFER_RE.search(witness) is not None
        has_op = (not is_negated) and (not is_refuted) and (has_rel or (has_term and buzz_hits < 2))
        if buzz_hits >= 2 and not has_op:
            raise PortalInterposeError("LAW5_SMUGGLE_REJECTED", "vocabulary smuggling without exact operator witness")
        _require(has_op, "LAW5_MISSING_OPERATOR_WITNESS", "exact operator transfer requires non-negated identity/map witness")
        return {
            "schema": "aletheia.law5_interpose_guard.v1",
            "pillar": pillar,
            "status": "EXACT_OPERATOR_VERIFIED",
            "verified_bridge": True,
            "source_object": src,
            "target_object": dst,
        }

    has_obs = (not is_negated) and (_OBSTRUCTION_WITNESS_RE.search(witness) is not None)
    _require(has_obs, "LAW5_MISSING_OBSTRUCTION_WITNESS", "structural obstruction requires non-negated impossibility/bound witness")
    return {
        "schema": "aletheia.law5_interpose_guard.v1",
        "pillar": pillar,
        "status": "STRUCTURAL_OBSTRUCTION_RECORDED",
        "verified_bridge": False,
        "source_object": src,
        "target_object": dst,
    }


def interpose_portal(
    title: Any,
    text: Any,
    *,
    rag_db_path: Any = None,
    archive_limit: int = 4,
    require_any_hit: bool = True,
) -> dict[str, Any]:
    """Run full CS-28 Turn-0 domain-stripped interposition with optional read-only SQLite archive."""
    scored = score_domain_stripped_pillars(title, text)
    if require_any_hit:
        _require(scored["pillars_hit"] > 0, "NO_PILLAR_HIT", "portal matched 0 active pillars after domain stripping")
    for row in scored["pillar_matrix"]:
        if row["hit"] and rag_db_path is not None:
            row["archive_nodes"] = query_sqlite_archive(rag_db_path, row["pillar"], limit=archive_limit)
        else:
            row["archive_nodes"] = []
    scored["archive_queried"] = rag_db_path is not None
    return scored


def run_cs28_regression_fixtures() -> dict[str, Any]:
    """
    Execute built-in live regression fixtures proving zero-keyword cross-pillar
    detection on (1) Hadwiger 3D -> Optimization/Quantization and (2) PFC BP/Carving
    -> Biological/Connectome, plus Law-5 anti-smuggle rejection controls.
    """
    hadwiger_title = "Homothetic Covering via John Contact Decomposition and Polytope Rigidity"
    hadwiger_text = (
        "Given a compact polytope, consider its halved difference body S and maximal volume "
        "ellipsoid contact vectors achieving isotropic frame rigidity, bounding support "
        "function by mean width and covering shadow boundary arcs via minimax Chebyshev scales."
    )
    hadwiger_forbidden = ("quantiz", "siliquant", "codebook", "blockh4", "neural", "bpw")
    hadwiger_clean_kw = all(tok not in (hadwiger_title + hadwiger_text).lower() for tok in hadwiger_forbidden)
    hadwiger_res = interpose_portal(hadwiger_title, hadwiger_text)
    hadwiger_hits = {r["pillar"]: r for r in hadwiger_res["pillar_matrix"] if r["hit"]}

    pfc_title = "Damped Loopy Message Passing and Structural Carving on Sparse Factor Graphs"
    pfc_text = (
        "Comparing exact max-sum message passing with Bethe cavity damping against local "
        "recurrence trajectories on sparse directed graphs with frustrated triads, feedback "
        "loops, and iterative edge carving."
    )
    pfc_forbidden = ("malecns", "drosophila", "fly", "connectome", "neuron", "track s102", "synap")
    pfc_clean_kw = all(tok not in (pfc_title + pfc_text).lower() for tok in pfc_forbidden)
    pfc_res = interpose_portal(pfc_title, pfc_text)
    pfc_hits = {r["pillar"]: r for r in pfc_res["pillar_matrix"] if r["hit"]}

    smuggle_blocked = False
    try:
        enforce_law5_interpose_guard({
            "pillar": "optimization_quantization",
            "disposition": "EXACT_OPERATOR_TRANSFER",
            "source_object": "halved difference body",
            "target_object": "16-d weight block",
            "witness": "deep duality sheaf isomorphism and holonomy emergence across spaces",
        })
    except PortalInterposeError as exc:
        smuggle_blocked = exc.code == "LAW5_SMUGGLE_REJECTED"

    verified_transfer = enforce_law5_interpose_guard({
        "pillar": "optimization_quantization",
        "disposition": "EXACT_OPERATOR_TRANSFER",
        "source_object": "John diagonal frame M = diag((max - min) / 2)",
        "target_object": "A16_BlockH4 weight block W",
        "witness": "h_{M^{-1}(S)}(u) <= sum c_s |<v_s, u>| with exact minimax Chebyshev scale lambda_0",
    })

    checks = {
        "hadwiger_zero_target_keywords": hadwiger_clean_kw,
        "hadwiger_hits_optimization_quantization": "optimization_quantization" in hadwiger_hits,
        "hadwiger_hits_pure_math_formal": "pure_math_formal" in hadwiger_hits,
        "pfc_zero_target_keywords": pfc_clean_kw,
        "pfc_hits_bio_connectome": "bio_connectome" in pfc_hits,
        "pfc_hits_optimization_quantization": "optimization_quantization" in pfc_hits,
        "law5_smuggle_rejected": smuggle_blocked,
        "law5_verified_transfer": verified_transfer["verified_bridge"] is True,
    }
    passed = all(checks.values())
    return {
        "schema": "aletheia.cs28_regression.v1",
        "passed": passed,
        "checks": checks,
        "hadwiger_pillars_hit": sorted(hadwiger_hits),
        "pfc_pillars_hit": sorted(pfc_hits),
    }
