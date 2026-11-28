"""
`aletheia.portfolio_dag`: CS-27 (`SOP-18`) Cycle-Safe Recursive Nested-Link DAG
Validator & Symmetric GitHub + Hugging Face Portfolio Coverage Gate.

Stdlib-only, pure `int` / `fractions.Fraction`, zero bare asserts, safe across
all R4 isolated Python modes (`-I -B`, `-I -O -B`, `-I -B -W error`).
"""
from __future__ import annotations

from collections import deque
from fractions import Fraction
from pathlib import Path
from typing import Any

from aletheia import _strict_zone_b as _zb

__all__ = [
    "MAX_FILE_BYTES",
    "MAX_JSON_DEPTH",
    "MAX_JSON_INT_DIGITS",
    "PortfolioDagError",
    "validate_nested_link_dag",
    "validate_nested_link_dag_file",
    "evaluate_portfolio_coverage",
    "evaluate_portfolio_coverage_file",
]

MAX_FILE_BYTES = _zb.MAX_FILE_BYTES
MAX_JSON_DEPTH = _zb.MAX_JSON_DEPTH
MAX_JSON_INT_DIGITS = _zb.MAX_JSON_INT_DIGITS
_HF_KINDS = frozenset({"model", "dataset", "space", "collection"})
_NODE_DEPTH_KEYS = ("depth", "min_depth")
_EDGE_ENDPOINT_PAIRS = (("from", "to"), ("source", "target"), ("src", "dst"))
_EDGE_REL_KEYS = ("relation", "edge_type", "rel")


class PortfolioDagError(ValueError):
    """Fail-closed validation error for CS-27 nested-link DAG & portfolio checks."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _require(cond: bool, code: str, message: str) -> None:
    if not cond:
        raise PortfolioDagError(code, message)


def _frac_str(val: Fraction) -> str:
    return f"{val.numerator}/{val.denominator}"


def _require_exact_int(val: Any, label: str, minimum: int = 0) -> int:
    _require(type(val) is int and val >= minimum, "INVALID_INT", f"{label} must be exact int >= {minimum}")
    return val


def _require_nonempty_str(val: Any, label: str) -> str:
    _require(type(val) is str and len(val.strip()) > 0, "INVALID_STR", f"{label} must be non-empty str")
    return val


def _require_exact_bool(val: Any, label: str) -> bool:
    _require(type(val) is bool, "INVALID_BOOL", f"{label} must be bool")
    return val


def _to_unit_fraction(val: Any, label: str) -> Fraction:
    if type(val) is int:
        q = Fraction(val, 1)
    elif type(val) is Fraction:
        q = val
    else:
        raise PortfolioDagError("INVALID_FRACTION", f"{label} must be exact int or Fraction")
    _require(Fraction(0, 1) <= q <= Fraction(1, 1), "OUT_OF_RANGE_FRACTION", f"{label} must be in [0, 1]")
    return q


def _loads_regular_json(path: Any, label: str) -> Any:
    raw = _zb.open_regular_file(
        path,
        label,
        err_cls=PortfolioDagError,
        max_bytes=MAX_FILE_BYTES,
    )
    return _zb.parse_strict_json_bytes(
        raw,
        label,
        err_cls=PortfolioDagError,
        max_depth=MAX_JSON_DEPTH,
        max_int_digits=MAX_JSON_INT_DIGITS,
    )


def _resolve_node_key(node: dict[str, Any], index: int) -> str:
    if "id" in node:
        return _require_nonempty_str(node["id"], f"nodes[{index}].id")
    _require("url" in node, "MISSING_NODE_KEY", f"nodes[{index}] must declare 'id' or 'url'")
    return _require_nonempty_str(node["url"], f"nodes[{index}].url")


def _resolve_node_depth(node: dict[str, Any], index: int) -> int:
    for dkey in _NODE_DEPTH_KEYS:
        if dkey in node:
            return _require_exact_int(node[dkey], f"nodes[{index}].{dkey}", 0)
    raise PortfolioDagError("MISSING_NODE_DEPTH", f"nodes[{index}] missing 'depth'")


def _resolve_edge_fields(edge: dict[str, Any], index: int) -> tuple[str, str, str]:
    src = ""
    dst = ""
    found = False
    for sk, dk in _EDGE_ENDPOINT_PAIRS:
        if sk in edge and dk in edge:
            src = _require_nonempty_str(edge[sk], f"edges[{index}].{sk}")
            dst = _require_nonempty_str(edge[dk], f"edges[{index}].{dk}")
            found = True
            break
    _require(found, "MISSING_EDGE_ENDPOINT", f"edges[{index}] requires endpoint pair ('from'/'to', 'source'/'target', or 'src'/'dst')")
    rel = "links_to"
    for rkey in _EDGE_REL_KEYS:
        if rkey in edge:
            rel = _require_nonempty_str(edge[rkey], f"edges[{index}].{rkey}")
            break
    return src, dst, rel


def _find_cycle_iterative(adj: dict[str, list[str]]) -> list[str] | None:
    color: dict[str, int] = {nid: 0 for nid in adj}
    parent: dict[str, str | None] = {nid: None for nid in adj}
    for root in sorted(adj):
        if color[root] != 0:
            continue
        color[root] = 1
        stack: list[tuple[str, int]] = [(root, 0)]
        while stack:
            cur, pos = stack[-1]
            nbrs = adj[cur]
            if pos < len(nbrs):
                stack[-1] = (cur, pos + 1)
                nxt = nbrs[pos]
                if color[nxt] == 1:
                    cycle = [nxt]
                    walk: str | None = cur
                    while walk is not None and walk != nxt:
                        cycle.append(walk)
                        walk = parent[walk]
                    cycle.append(nxt)
                    cycle.reverse()
                    return cycle
                if color[nxt] == 0:
                    color[nxt] = 1
                    parent[nxt] = cur
                    stack.append((nxt, 0))
            else:
                color[cur] = 2
                stack.pop()
    return None


def validate_nested_link_dag(
    graph_obj: Any,
    *,
    require_recursive: bool = True,
    enforce_depth_monotone: bool = True,
    min_deep_ratio_q: Any = Fraction(0, 1),
) -> dict[str, Any]:
    """
    Validate a recursive nested-link portal graph as a cycle-safe DAG (`CS-27` / `SOP-18`).

    Enforces:
      - Fail-closed type/container validation (`R1`-`R3`, zero bool-as-int leaks)
      - Explicit anti-bot guard refusal (`zero_antibot_bypass=False` or `anti_bot_bypass=True`)
      - Iterative 3-color DFS cycle detection returning an explicit cycle witness
      - Root existence (`depth == 0`), reachability of deep nodes (`depth >= 1`), and
        non-decreasing edge depth progression (`depth[to] >= depth[from]`)
      - Anti-shallow-crawl guard (`SHALLOW_PORTAL_BLINDNESS`) when `deep_nodes == 0`
        without `exhaustion_verified=True`.
    """
    _require(type(graph_obj) is dict, "INVALID_GRAPH_TYPE", "graph_obj must be a dict")
    _require_exact_bool(require_recursive, "require_recursive")
    _require_exact_bool(enforce_depth_monotone, "enforce_depth_monotone")
    min_ratio = _to_unit_fraction(min_deep_ratio_q, "min_deep_ratio_q")

    if "zero_antibot_bypass" in graph_obj:
        zb = _require_exact_bool(graph_obj["zero_antibot_bypass"], "zero_antibot_bypass")
        _require(zb, "ANTIBOT_BYPASS_FORBIDDEN", "anti-bot bypass prohibited")

    _require("nodes" in graph_obj and type(graph_obj["nodes"]) is list, "MISSING_NODES", "nodes must be a list")
    _require("edges" in graph_obj and type(graph_obj["edges"]) is list, "MISSING_EDGES", "edges must be a list")
    raw_nodes = graph_obj["nodes"]
    raw_edges = graph_obj["edges"]
    _require(len(raw_nodes) > 0, "EMPTY_NODES", "nodes list must be non-empty")

    node_depths: dict[str, int] = {}
    roots: list[str] = []
    max_depth = 0
    depth_hist: dict[int, int] = {}

    for idx, node in enumerate(raw_nodes):
        _require(type(node) is dict, "INVALID_NODE", f"nodes[{idx}] must be a dict")
        key = _resolve_node_key(node, idx)
        _require(key not in node_depths, "DUPLICATE_NODE_ID", f"duplicate node key: {key!r}")
        depth = _resolve_node_depth(node, idx)
        if "anti_bot_bypass" in node:
            ab = _require_exact_bool(node["anti_bot_bypass"], f"nodes[{idx}].anti_bot_bypass")
            _require(not ab, "ANTIBOT_BYPASS_FORBIDDEN", f"nodes[{idx}] declares anti_bot_bypass=True")
        node_depths[key] = depth
        depth_hist[depth] = depth_hist.get(depth, 0) + 1
        if depth == 0:
            roots.append(key)
        max_depth = max(max_depth, depth)

    _require(len(roots) > 0, "NO_ROOT_PORTAL", "at least one depth == 0 root node is required")

    adj: dict[str, list[str]] = {nid: [] for nid in node_depths}
    seen_edges: set[tuple[str, str, str]] = set()
    for idx, edge in enumerate(raw_edges):
        _require(type(edge) is dict, "INVALID_EDGE", f"edges[{idx}] must be a dict")
        src, dst, rel = _resolve_edge_fields(edge, idx)
        _require(src in node_depths, "DANGLING_EDGE_ENDPOINT", f"edges[{idx}] unknown source node {src!r}")
        _require(dst in node_depths, "DANGLING_EDGE_ENDPOINT", f"edges[{idx}] unknown target node {dst!r}")
        edge_key = (src, dst, rel)
        _require(edge_key not in seen_edges, "DUPLICATE_EDGE", f"duplicate edge {edge_key!r}")
        seen_edges.add(edge_key)
        adj[src].append(dst)

    for nid in adj:
        adj[nid].sort()

    cycle = _find_cycle_iterative(adj)
    _require(cycle is None, "CYCLE_DETECTED", f"cycle detected in portal graph: {' -> '.join(cycle or [])}")

    reachable: set[str] = set(roots)
    q: deque[str] = deque(sorted(roots))
    while q:
        cur = q.popleft()
        for nxt in adj[cur]:
            if nxt not in reachable:
                reachable.add(nxt)
                q.append(nxt)

    if enforce_depth_monotone:
        for src, dst, _ in sorted(seen_edges):
            _require(
                node_depths[dst] >= node_depths[src],
                "DEPTH_REGRESSION",
                f"edge {src!r} (depth {node_depths[src]}) -> {dst!r} (depth {node_depths[dst]}) regresses depth",
            )
        for nid, depth in node_depths.items():
            if depth > 0:
                _require(nid in reachable, "UNREACHABLE_DEEP_NODE", f"deep node {nid!r} unreachable from depth-0 roots")

    deep_nodes = sum(1 for d in node_depths.values() if d >= 1)
    exhaustion_verified = graph_obj.get("exhaustion_verified") is True
    if require_recursive and deep_nodes == 0:
        _require(
            exhaustion_verified,
            "SHALLOW_PORTAL_BLINDNESS",
            "0 recursive depth >= 1 nodes and exhaustion_verified != True",
        )

    deep_ratio = Fraction(deep_nodes, len(node_depths))
    _require(
        deep_ratio >= min_ratio,
        "INSUFFICIENT_DEEP_COVERAGE",
        f"deep_node_ratio {_frac_str(deep_ratio)} < required {_frac_str(min_ratio)}",
    )
    mean_out = Fraction(len(seen_edges), len(node_depths))
    return {
        "schema": "aletheia.portfolio_dag.v1",
        "dag_verified": True,
        "total_nodes": len(node_depths),
        "total_edges": len(seen_edges),
        "root_count": len(roots),
        "deep_nodes": deep_nodes,
        "reachable_nodes": len(reachable),
        "max_depth": max_depth,
        "depth_histogram": {str(k): depth_hist[k] for k in sorted(depth_hist)},
        "deep_node_ratio_q": _frac_str(deep_ratio),
        "mean_out_degree_q": _frac_str(mean_out),
    }


def validate_nested_link_dag_file(path: Any, **kwargs: Any) -> dict[str, Any]:
    """Fail-closed regular-file loader and validator for a CS-27 nested-link DAG JSON."""
    return validate_nested_link_dag(_loads_regular_json(path, "nested_link_dag"), **kwargs)


def evaluate_portfolio_coverage(
    portfolio_obj: Any,
    *,
    min_github_coverage_q: Any = Fraction(1, 1),
    min_hf_coverage_q: Any = Fraction(1, 1),
    require_branch_pr_enumeration: bool = True,
) -> dict[str, Any]:
    """
    Validate symmetric GitHub + Hugging Face author-portfolio coverage (`CS-27` / `SOP-18b`).

    Enforces:
      - Both `github` and `huggingface` sections present with `checked=True`
      - Zero private repositories (`is_private=False` on GitHub, `private=False` on HF)
      - Branch & PR enumeration (`SOP-9`) when GitHub repos > 0
      - Explicit disambiguation query when Hugging Face artifact count is 0
      - Exact pure-`Fraction` coverage ratios >= configured rational thresholds.
    """
    _require(type(portfolio_obj) is dict, "INVALID_PORTFOLIO_TYPE", "portfolio_obj must be a dict")
    _require_exact_bool(require_branch_pr_enumeration, "require_branch_pr_enumeration")
    min_gh = _to_unit_fraction(min_github_coverage_q, "min_github_coverage_q")
    min_hf = _to_unit_fraction(min_hf_coverage_q, "min_hf_coverage_q")

    _require("author" in portfolio_obj, "MISSING_AUTHOR", "portfolio missing 'author'")
    author = _require_nonempty_str(portfolio_obj["author"], "author")

    _require("github" in portfolio_obj and type(portfolio_obj["github"]) is dict, "SINGLE_PLATFORM_BLINDNESS", "missing github section")
    _require("huggingface" in portfolio_obj and type(portfolio_obj["huggingface"]) is dict, "SINGLE_PLATFORM_BLINDNESS", "missing huggingface section")

    gh = portfolio_obj["github"]
    hf = portfolio_obj["huggingface"]

    _require("checked" in gh, "MISSING_GH_CHECKED", "github.checked missing")
    _require(_require_exact_bool(gh["checked"], "github.checked"), "SINGLE_PLATFORM_BLINDNESS", "github.checked must be True")
    _require("expected_public_repos" in gh, "MISSING_GH_EXPECTED", "github.expected_public_repos missing")
    exp_gh = _require_exact_int(gh["expected_public_repos"], "github.expected_public_repos", 0)
    _require("repos" in gh and type(gh["repos"]) is list, "MISSING_GH_REPOS", "github.repos must be a list")

    gh_names: set[str] = set()
    for idx, repo in enumerate(gh["repos"]):
        _require(type(repo) is dict, "INVALID_GH_REPO", f"github.repos[{idx}] must be a dict")
        rname = _require_nonempty_str(repo.get("name"), f"github.repos[{idx}].name")
        _require(rname not in gh_names, "DUPLICATE_GH_REPO", f"duplicate GitHub repo {rname!r}")
        gh_names.add(rname)
        _require("is_private" in repo, "MISSING_GH_PRIVATE_FLAG", f"github.repos[{idx}].is_private missing")
        is_priv = _require_exact_bool(repo["is_private"], f"github.repos[{idx}].is_private")
        _require(not is_priv, "PRIVATE_REPO_LEAK", f"private GitHub repo forbidden in public portfolio: {rname!r}")

    if exp_gh == 0 and len(gh_names) == 0:
        _require(
            "zero_gh_disambiguation_query" in gh,
            "UNVERIFIED_ZERO_GH",
            "0 GitHub repos requires explicit zero_gh_disambiguation_query",
        )
        _require_nonempty_str(gh["zero_gh_disambiguation_query"], "github.zero_gh_disambiguation_query")

    if require_branch_pr_enumeration and len(gh_names) > 0:
        _require("branches_enumerated" in gh and "prs_enumerated" in gh, "SHALLOW_MAIN_ONLY", "github branches_enumerated and prs_enumerated required")
        b_ok = _require_exact_bool(gh["branches_enumerated"], "github.branches_enumerated")
        p_ok = _require_exact_bool(gh["prs_enumerated"], "github.prs_enumerated")
        _require(b_ok and p_ok, "SHALLOW_MAIN_ONLY", "SOP-9 requires non-main branch and open-PR enumeration")

    _require("checked" in hf, "MISSING_HF_CHECKED", "huggingface.checked missing")
    _require(_require_exact_bool(hf["checked"], "huggingface.checked"), "SINGLE_PLATFORM_BLINDNESS", "huggingface.checked must be True")
    _require("expected_public_artifacts" in hf, "MISSING_HF_EXPECTED", "huggingface.expected_public_artifacts missing")
    exp_hf = _require_exact_int(hf["expected_public_artifacts"], "huggingface.expected_public_artifacts", 0)
    _require("artifacts" in hf and type(hf["artifacts"]) is list, "MISSING_HF_ARTIFACTS", "huggingface.artifacts must be a list")

    hf_keys: set[tuple[str, str]] = set()
    for idx, art in enumerate(hf["artifacts"]):
        _require(type(art) is dict, "INVALID_HF_ARTIFACT", f"huggingface.artifacts[{idx}] must be a dict")
        aid = _require_nonempty_str(art.get("id"), f"huggingface.artifacts[{idx}].id")
        kind = _require_nonempty_str(art.get("kind"), f"huggingface.artifacts[{idx}].kind")
        _require(kind in _HF_KINDS, "INVALID_HF_KIND", f"huggingface.artifacts[{idx}].kind invalid: {kind!r}")
        akey = (kind, aid)
        _require(akey not in hf_keys, "DUPLICATE_HF_ARTIFACT", f"duplicate HF artifact {akey!r}")
        hf_keys.add(akey)
        _require("private" in art, "MISSING_HF_PRIVATE_FLAG", f"huggingface.artifacts[{idx}].private missing")
        is_priv = _require_exact_bool(art["private"], f"huggingface.artifacts[{idx}].private")
        _require(not is_priv, "PRIVATE_HF_LEAK", f"private HF artifact forbidden: {aid!r}")

    if exp_hf == 0 and len(hf_keys) == 0:
        _require(
            "zero_hf_disambiguation_query" in hf,
            "UNVERIFIED_ZERO_HF",
            "0 HF artifacts requires explicit zero_hf_disambiguation_query",
        )
        _require_nonempty_str(hf["zero_hf_disambiguation_query"], "huggingface.zero_hf_disambiguation_query")

    gh_cov = Fraction(len(gh_names), exp_gh) if exp_gh > 0 else Fraction(1, 1)
    hf_cov = Fraction(len(hf_keys), exp_hf) if exp_hf > 0 else Fraction(1, 1)
    _require(
        gh_cov >= min_gh,
        "GITHUB_COVERAGE_BELOW_THRESHOLD",
        f"GitHub coverage {_frac_str(gh_cov)} < {_frac_str(min_gh)}",
    )
    _require(
        hf_cov >= min_hf,
        "HF_COVERAGE_BELOW_THRESHOLD",
        f"HF coverage {_frac_str(hf_cov)} < {_frac_str(min_hf)}",
    )

    gh_unit = min(Fraction(1, 1), gh_cov)
    hf_unit = min(Fraction(1, 1), hf_cov)
    symmetry = Fraction(1, 2) * (gh_unit + hf_unit)
    return {
        "schema": "aletheia.portfolio_coverage.v1",
        "author": author,
        "passed": True,
        "github_enumerated": len(gh_names),
        "github_expected": exp_gh,
        "github_coverage_q": _frac_str(gh_cov),
        "hf_enumerated": len(hf_keys),
        "hf_expected": exp_hf,
        "hf_coverage_q": _frac_str(hf_cov),
        "platform_symmetry_q": _frac_str(symmetry),
    }


def evaluate_portfolio_coverage_file(path: Any, **kwargs: Any) -> dict[str, Any]:
    """Fail-closed regular-file loader and validator for CS-27 symmetric portfolio coverage."""
    return evaluate_portfolio_coverage(_loads_regular_json(path, "portfolio_coverage"), **kwargs)
