"""
`aletheia diagnose <expedition-dir> [--board <jsonl>]`: Quantitative Anti-Cave Relapse Detector.

Scans `frontier_portals.md`, `AUDIT_LOG.md`, verification/probe scripts, and an optional
swarm board JSONL feed to detect and score all 12 Cave-Shadow Anti-Patterns from The Aletheia Method:
  1. Static-Map Trap (cartographer/portal-keeper parks after Round 1)
  2. Premature Dismissal Bias (strings of FALSIFIED/N0 without steelmanned repairs)
  3. Language Smuggling (buzzword density without executable operators/equations)
  4. Substitution Shadow (toy/synthetic proxies passing for real upstream targets)
  5. Glass Gate (bare asserts, float epsilon cutoffs in exact checks, missing R4 parity)
  6. Local-Optimum Closure (sharpness walls / obstructions terminating without elevation)
  7. Provenance Inflation (merged vs Draft PR, uncompiled Lean claimed verified, N2 without prior art)
  8. Compute-Leakage Simpson's Paradox (unbounded-budget / format-breaking CoT inversion without survival cap)
  9. Finite-Sample / Support-Truncation Mirage (asymptotic claim from truncated/finite-M trajectories without cutoff check)
 10. Sparse-Collision Denominator Collapse (averaging sparse/filtered items by collision count c_j instead of global W)
 11. Unit-Gauge / Radix Fragility (unscaled raw-unit regularization or base-10/float-tolerance grading without gauge invariance)
 12. Trust-Boundary Shadow (trailing-newline `$` digest regexes, loose `json.loads` on ledgers, unbound escape hatches, or unverified ancestor permissions)
"""
from __future__ import annotations

import ast
from pathlib import Path
import re
from typing import Any

from .audit_check import SKIP_DIRS, validate_audit_log_markdown
from .strict_io import AletheiaError, loads_strict_json, require_ok

_BUZZWORDS = (
    "sheaf", "duality", "curvature", "emergence", "holonomy",
    "topological", "isomorphism", "cohomology", "functor", "homotopy",
)
_OPERATOR_MARKERS = re.compile(r"(=|:=|->|\\to|\\ge|\\le|\\equiv|def\s+\w+|\.py\b|check_[0-9]+|```)")
_FLOAT_CUTOFF_RE = re.compile(r"(?:1e-(?:9|10|11|12|13|14|15)|math\.isclose|np\.allclose|eigvalsh)")
_PROXY_HINT_RE = re.compile(r"\b(?:synthetic\s+proxy|toy\s+stub|mock\s+matrix|placeholder\s+model)\b", re.IGNORECASE)
_OBSTRUCTION_RE = re.compile(r"\b(?:sharpness\s+wall|obstructions?|counterexamples?|no-go|impossib\w*)\b", re.IGNORECASE)
_ELEVATION_RE = re.compile(r"\b(?:theorems?|higher[- ]moment|spawn\w*|branch(?:es)?|elevat\w*|new\s+invariants?|generaliz\w*)\b", re.IGNORECASE)
_PORTAL_HEADING_RE = re.compile(r"^#{1,3}\s+Portal\s+[0-9A-Za-z]+", re.MULTILINE)
_COMPUTE_LEAK_RE = re.compile(
    r"\b(?:unbounded\s+(?:compute|budget|retries|wall[- ]clock)|no\s+wall[- ]clock\s+cap|"
    r"format[- ]breaking\s+cot\s+escape|unbounded\s+cot\s+scratchpad|compute[- ]leakage\s+confound)\b",
    re.IGNORECASE,
)
_TRUNCATION_MIRAGE_RE = re.compile(
    r"\b(?:top[- ]p\s+truncation\s+mirage|finite[- ]sample\s+mirage|"
    r"asymptotic\s+fixed\s+point\s+from\s+finite\s+sample|tail[- ]mass\s+extinction\s+ignored)\b",
    re.IGNORECASE,
)
_SCATTER_MEAN_RE = re.compile(
    r"scatter_reduce_\s*\(\s*['\"]mean['\"][^)]*include_self\s*=\s*False",
    re.DOTALL,
)
_COLLISION_DENOM_RE = re.compile(
    r"\b(?:divide\s+by\s+collision\s+count|sparse[- ]collision\s+denominator\s+collapse|"
    r"dropped\s+invalid\s+denominator)\b",
    re.IGNORECASE,
)
_UNIT_RADIX_FRAGILE_RE = re.compile(
    r"\b(?:unscaled\s+raw[- ]unit\s+ridge|unit[- ]gauge\s+fragil|radix[- ]dependent\s+grad|"
    r"include_percentage\s*=\s*True)\b",
    re.IGNORECASE,
)
_TRAILING_NEWLINE_DIGEST_RE = re.compile(
    r"re\.compile\(\s*r?['\"]\^(?:\(\?:sha256:\)\?|sha256:)?\[(?:0-9a-f(?:A-F)?|a-f(?:A-F)?0-9)\]\{(?:40|64)\}\$['\"]"
)


def _require_board_seq(msg: dict[str, Any], fallback_seq: int, context: str) -> int:
    if "seq" not in msg:
        return fallback_seq
    raw = msg["seq"]
    require_ok(
        type(raw) is int and raw >= 0,
        "INVALID_BOARD_SEQ",
        f"{context}: board seq must be non-negative int, got {raw!r} ({type(raw).__name__})",
    )
    return raw


def _load_board_jsonl(board_path: Path | None) -> list[dict[str, Any]]:
    if board_path is None:
        return []
    require_ok(board_path.is_file(), "BOARD_NOT_FOUND", f"board file not found: {board_path}")
    try:
        raw_text = board_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise AletheiaError("INVALID_BOARD_UTF8", f"invalid UTF-8 in {board_path}: {exc}") from exc
    msgs: list[dict[str, Any]] = []
    for lineno, line in enumerate(raw_text.splitlines(), start=1):
        s = line.strip()
        if not s:
            continue
        try:
            obj = loads_strict_json(s, allow_float=True, require_object=False)
        except Exception as exc:
            raise AletheiaError("INVALID_BOARD_JSONL", f"invalid JSONL on line {lineno} of {board_path}: {exc}") from exc
        if isinstance(obj, dict):
            _require_board_seq(obj, len(msgs) + 1, f"{board_path}:{lineno}")
            msgs.append(obj)
    return msgs


def _status_from_risk(risk: int) -> str:
    if risk >= 50:
        return "ALERT"
    if risk >= 20:
        return "WARNING"
    return "CLEAR"


def diagnose_expedition(
    expedition_dir: Path,
    *,
    board_path: Path | None = None,
    portals_file: Path | None = None,
) -> dict[str, Any]:
    """Run quantitative 12-pattern Cave-Shadow relapse diagnosis on an expedition directory."""
    root = expedition_dir.resolve()
    require_ok(root.is_dir(), "EXPEDITION_DIR_NOT_FOUND", f"directory not found: {root}")

    if portals_file is not None:
        portals_path = portals_file.resolve()
    else:
        cand_cart = root / "cartography" / "frontier_portals.md"
        cand_root = root / "frontier_portals.md"
        portals_path = cand_cart if cand_cart.is_file() else (cand_root if cand_root.is_file() else cand_cart)
    audit_log_path = root / "verification" / "AUDIT_LOG.md"
    board_msgs = _load_board_jsonl(board_path)

    portals_text = portals_path.read_text(encoding="utf-8") if portals_path.is_file() else ""
    audit_text = audit_log_path.read_text(encoding="utf-8") if audit_log_path.is_file() else ""
    audit_info = validate_audit_log_markdown(audit_log_path) if audit_log_path.is_file() else None

    patterns: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # 1. Static-Map Trap
    # ------------------------------------------------------------------
    r1 = 0
    ev1: list[str] = []
    portal_headers = _PORTAL_HEADING_RE.findall(portals_text)
    if not portals_path.is_file():
        r1 += 60
        ev1.append("cartography/frontier_portals.md is missing")
    elif len(portal_headers) < 2 and len(portals_text) < 1200:
        r1 += 30
        ev1.append(f"frontier_portals.md has only {len(portal_headers)} portal section(s) (possible static Pass-1 map)")

    if board_msgs:
        keeper_msgs = [
            m for m in board_msgs
            if any(k in str(m.get("agent", "")).lower() for k in ("cartographer", "portal-keeper", "portal_keeper"))
        ]
        total_msgs = len(board_msgs)
        if not keeper_msgs:
            r1 += 50
            ev1.append("board JSONL has 0 posts from cartographer / portal-keeper")
        else:
            last_seq = max(_require_board_seq(m, i + 1, "keeper_msg") for i, m in enumerate(keeper_msgs))
            max_seq = max(_require_board_seq(m, i + 1, "board_msg") for i, m in enumerate(board_msgs))
            if len(keeper_msgs) == 1 and "[done]" in str(keeper_msgs[0].get("text", "")).lower() and max_seq >= 4:
                r1 += 60
                ev1.append("portal-keeper posted [done] once in Round 1 and went silent")
            elif max_seq >= 8 and last_seq * 20 < max_seq * 7:
                r1 += 35
                ev1.append(f"portal-keeper last posted at seq {last_seq}/{max_seq} (inactive in later waves)")

    r1 = min(100, r1)
    patterns.append({
        "id": "CS-01",
        "name": "Static-Map Trap",
        "risk_score": r1,
        "status": _status_from_risk(r1),
        "evidence": ev1,
        "remediation": "Keep portal-keeper active across every wave; loop every probe anomaly back into frontier_portals.md.",
    })

    # ------------------------------------------------------------------
    # 2. Premature Dismissal Bias
    # ------------------------------------------------------------------
    r2 = 0
    ev2: list[str] = []
    if audit_info is not None:
        vc = audit_info["verdict_counts"]
        n_fals = vc.get("FALSIFIED", 0)
        n_part = vc.get("PARTIAL/FRAGILE", 0)
        n_ver = vc.get("VERIFIED", 0)
        n_n2 = audit_info["novelty_counts"].get("N2", 0)
        if (n_fals + n_part) >= 2 and n_ver == 0:
            r2 += 70
            ev2.append(f"{n_fals} FALSIFIED and {n_part} PARTIAL/FRAGILE audits with 0 VERIFIED repaired hypotheses")
        elif n_fals >= 2 and n_n2 == 0 and n_ver <= 1:
            r2 += 35
            ev2.append(f"high rejection ratio ({n_fals} FALSIFIED vs {n_ver} VERIFIED, 0 N2)")
    if board_msgs:
        dismissals = sum(
            1 for m in board_msgs
            if any(w in str(m.get("text", "")).lower() for w in ("falsified", "no new ground", "repackaging", "dead end"))
        )
        steelmans = sum(
            1 for m in board_msgs
            if any(w in str(m.get("text", "")).lower() for w in ("steelman", "repaired", "strengthened", "upgraded"))
        )
        if dismissals >= 3 and steelmans == 0:
            r2 += 55
            ev2.append(f"board shows {dismissals} dismissal messages with 0 steelman/repair follow-ups")

    r2 = min(100, r2)
    patterns.append({
        "id": "CS-02",
        "name": "Premature Dismissal Bias",
        "risk_score": r2,
        "status": _status_from_risk(r2),
        "evidence": ev2,
        "remediation": "Invoke Law 2 (Steelman-Before-Falsify): separate prototype bugs from core math and test the strongest repaired statement.",
    })

    # ------------------------------------------------------------------
    # 3. Language Smuggling
    # ------------------------------------------------------------------
    r3 = 0
    ev3: list[str] = []
    md_files: list[Path] = []
    for sub in ("cartography", "synthesis", "probes"):
        sp = root / sub
        if sp.is_dir():
            md_files.extend(sorted(sp.rglob("*.md")))
    smuggled_sections = 0
    for mf in md_files:
        txt = mf.read_text(encoding="utf-8", errors="replace")
        sections = re.split(r"^#{1,3}\s+", txt, flags=re.MULTILINE)
        for sec in sections[1:]:
            lower = sec.lower()
            bw_hits = sum(lower.count(bw) for bw in _BUZZWORDS)
            has_op = _OPERATOR_MARKERS.search(sec) is not None
            if bw_hits >= 3 and not has_op:
                smuggled_sections += 1
                title = sec.splitlines()[0][:60] if sec.splitlines() else "<untitled>"
                ev3.append(f"{mf.relative_to(root)} section {title!r}: {bw_hits} analogy buzzwords with no equation/operator")
    if smuggled_sections >= 2:
        r3 = min(100, 35 * smuggled_sections)
    elif smuggled_sections == 1:
        r3 = 30
    patterns.append({
        "id": "CS-03",
        "name": "Language Smuggling",
        "risk_score": r3,
        "status": _status_from_risk(r3),
        "evidence": ev3,
        "remediation": "Enforce Law 5 / Gate 5: require typed objects, executable map code, and exact identity or quantitative closure defect.",
    })

    # ------------------------------------------------------------------
    # 4. Substitution Shadow
    # ------------------------------------------------------------------
    r4 = 0
    ev4: list[str] = []
    for mf in [audit_log_path] + md_files:
        if not mf.is_file():
            continue
        for lineno, line in enumerate(mf.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if _PROXY_HINT_RE.search(line) is not None:
                # Ignore lines explicitly noting a repaired/rejected substitution shadow!
                low = line.lower()
                if any(ok in low for ok in ("replaced", "rejected", "falsified", "caught", "avoid", "never", "anti-pattern")):
                    continue
                r4 += 40
                ev4.append(f"{mf.relative_to(root)}:{lineno}: possible unaddressed toy/proxy substitution")
    r4 = min(100, r4)
    patterns.append({
        "id": "CS-04",
        "name": "Substitution Shadow",
        "risk_score": r4,
        "status": _status_from_risk(r4),
        "evidence": ev4,
        "remediation": "Run verifiers directly against real upstream equations, data, or reference simulators (zero synthetic proxy substitution).",
    })

    # ------------------------------------------------------------------
    # 5. Glass Gate
    # ------------------------------------------------------------------
    r5 = 0
    ev5: list[str] = []
    py_scan_dirs = [root / "verification", root / "probes", root / "synthesis"]
    bare_assert_files = 0
    float_exact_hits = 0
    for d in py_scan_dirs:
        if not d.is_dir():
            continue
        for pf in sorted(d.rglob("*.py")):
            if any(part in SKIP_DIRS or part == "__pycache__" for part in pf.relative_to(root).parts):
                continue
            txt = pf.read_text(encoding="utf-8", errors="replace")
            try:
                tree = ast.parse(txt, filename=str(pf))
                n_asserts = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Assert))
            except SyntaxError:
                n_asserts = 0
            if n_asserts > 0:
                bare_assert_files += 1
                ev5.append(f"{pf.relative_to(root)}: {n_asserts} bare assert statement(s) stripped by python3 -O")
            if "exact" in txt.lower() and "Fraction" in txt and _FLOAT_CUTOFF_RE.search(txt) is not None:
                # Flag standalone zero-float verifiers that sneak in float epsilon cutoffs
                # (do not false-positive on hybrid multi-probe scripts that import numpy/scipy for numerical cross-checks)
                has_numerical_lib = bool(re.search(r"^\s*(?:import|from)\s+(?:numpy|scipy)\b", txt, re.MULTILINE))
                if not has_numerical_lib and ("zero-float" in txt.lower() or "zero float" in txt.lower()):
                    float_exact_hits += 1
                    ev5.append(f"{pf.relative_to(root)}: claims zero-float while containing float threshold/eigvalsh")

    if bare_assert_files > 0:
        r5 += min(70, 35 * bare_assert_files)
    if float_exact_hits > 0:
        r5 += min(50, 30 * float_exact_hits)
    r5 = min(100, r5)
    patterns.append({
        "id": "CS-05",
        "name": "Glass Gate",
        "risk_score": r5,
        "status": _status_from_risk(r5),
        "evidence": ev5,
        "remediation": "Eliminate bare asserts on trust paths, verify exact claims in Fraction/int/SymPy, and run R4 3-mode parity + R5 mutation testing.",
    })

    # ------------------------------------------------------------------
    # 6. Local-Optimum Closure
    # ------------------------------------------------------------------
    r6 = 0
    ev6: list[str] = []
    combined_corpus = portals_text + "\n" + audit_text + "\n" + "\n".join(str(m.get("text", "")) for m in board_msgs)
    obs_hits = len(_OBSTRUCTION_RE.findall(combined_corpus))
    elev_hits = len(_ELEVATION_RE.findall(combined_corpus))
    if obs_hits >= 2 and elev_hits == 0:
        r6 = 60
        ev6.append(f"{obs_hits} obstruction/sharpness-wall mentions with 0 elevated obstruction theorems or follow-up branches")
    elif obs_hits >= 1 and elev_hits == 0:
        r6 = 25
        ev6.append(f"{obs_hits} obstruction mention(s) without documented theorem elevation or next-invariant branch")
    patterns.append({
        "id": "CS-06",
        "name": "Local-Optimum Closure",
        "risk_score": r6,
        "status": _status_from_risk(r6),
        "evidence": ev6,
        "remediation": "Elevate obstructions into exact impossibility theorems or spawn a targeted branch adding the missing invariant.",
    })

    # ------------------------------------------------------------------
    # 7. Provenance Inflation
    # ------------------------------------------------------------------
    r7 = 0
    ev7: list[str] = []
    if audit_info is not None:
        for err in audit_info["errors"]:
            if err["code"] == "PROVENANCE_INFLATION":
                r7 += 60
                ev7.append(f"AUDIT_LOG line {err['line']}: {err['message']}")
        for warn in audit_info["warnings"]:
            if warn["code"] == "N2_MISSING_PRIOR_ART_NOTE":
                r7 += 25
                ev7.append(f"AUDIT_LOG line {warn['line']} ({warn['audit_id']}): {warn['message']}")
    for mf in [audit_log_path] + md_files:
        if not mf.is_file():
            continue
        low = mf.read_text(encoding="utf-8", errors="replace").lower()
        if "draft pr" in low and "merged into main" in low and "never merged" not in low and "not merged" not in low:
            r7 += 50
            ev7.append(f"{mf.relative_to(root)}: mentions both 'Draft PR' and 'merged into main'")
    r7 = min(100, r7)
    patterns.append({
        "id": "CS-07",
        "name": "Provenance Inflation",
        "risk_score": r7,
        "status": _status_from_risk(r7),
        "evidence": ev7,
        "remediation": "Enforce Law 4: distinguish Draft PR vs merged, uncompiled_source vs compiler-checked, and cite full-text prior art for every N2.",
    })

    # ------------------------------------------------------------------
    # 8. Compute-Leakage Simpson's Paradox (CS-08, Wave 2 AUDIT-023)
    # ------------------------------------------------------------------
    r8 = 0
    ev8: list[str] = []
    mitigation_tokens = ("fixed-compute", "fixed compute", "survival cap", "avoid", "never", "repaired", "caught", "anti-pattern", "prevent")
    for mf in [audit_log_path] + md_files:
        if not mf.is_file():
            continue
        for lineno, line in enumerate(mf.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if _COMPUTE_LEAK_RE.search(line) is not None:
                low = line.lower()
                if any(tok in low for tok in mitigation_tokens):
                    continue
                r8 += 50
                ev8.append(f"{mf.relative_to(root)}:{lineno}: possible unbounded-compute / format-breaking CoT confound")
    for m in board_msgs:
        txt = str(m.get("text", ""))
        if _COMPUTE_LEAK_RE.search(txt) is not None and not any(tok in txt.lower() for tok in mitigation_tokens):
            r8 += 40
            ev8.append(f"board seq {m.get('seq', '?')}: unbounded-compute confound reported without fixed-compute cap")
    # Also scan structured benchmark JSONs under probes/ & synthesis/ for explicit Simpson inversion without cap
    for sub in ("probes", "synthesis"):
        sp = root / sub
        if not sp.is_dir():
            continue
        for jf in sorted(sp.rglob("*.json")):
            if any(part in SKIP_DIRS for part in jf.relative_to(root).parts):
                continue
            try:
                jobj = loads_strict_json(jf.read_text(encoding="utf-8", errors="replace"), allow_float=True, require_object=False)
            except Exception:
                continue
            if isinstance(jobj, dict):
                fw = jobj.get("fixed_compute_winner")
                uw = jobj.get("unbounded_winner")
                cap_ok = jobj.get("fixed_compute_cap_enforced")
                if fw is not None and uw is not None and fw != uw and cap_ok is not True:
                    r8 += 60
                    ev8.append(
                        f"{jf.relative_to(root)}: Simpson reversal (fixed_compute_winner={fw!r} != unbounded_winner={uw!r}) without fixed_compute_cap_enforced=true"
                    )
    r8 = min(100, r8)
    patterns.append({
        "id": "CS-08",
        "name": "Compute Leakage",
        "risk_score": r8,
        "status": _status_from_risk(r8),
        "evidence": ev8,
        "remediation": "Enforce fixed-compute wall-clock survival caps alongside round counts; report format-preserving solves separately from long open-reasoning escapes.",
    })

    # ------------------------------------------------------------------
    # 9. Finite-Sample / Support-Truncation Mirage (CS-09, AUDIT-032)
    # ------------------------------------------------------------------
    r9 = 0
    ev9: list[str] = []
    cs09_ok = ("finite-m", "finite m", "tail extinction checked", "avoid", "never", "repaired", "caught", "anti-pattern", "prevent", "mitigated")
    for mf in [audit_log_path] + md_files:
        if not mf.is_file():
            continue
        for lineno, line in enumerate(mf.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if _TRUNCATION_MIRAGE_RE.search(line) is not None and not any(tok in line.lower() for tok in cs09_ok):
                r9 += 50
                ev9.append(f"{mf.relative_to(root)}:{lineno}: possible finite-sample / support-truncation mirage")
    for sub in ("probes", "synthesis"):
        sp = root / sub
        if not sp.is_dir():
            continue
        for jf in sorted(sp.rglob("*.json")):
            if any(part in SKIP_DIRS for part in jf.relative_to(root).parts):
                continue
            try:
                jobj = loads_strict_json(jf.read_text(encoding="utf-8", errors="replace"), allow_float=True, require_object=False)
            except Exception:
                continue
            if isinstance(jobj, dict):
                if (jobj.get("asymptotic_claim") is True and jobj.get("finite_sample_checked") is False) or (
                    jobj.get("support_truncated") is True and jobj.get("tail_extinction_checked") is False
                ):
                    r9 += 60
                    ev9.append(f"{jf.relative_to(root)}: asymptotic/truncated claim without finite-M / tail-extinction check")
    r9 = min(100, r9)
    patterns.append({
        "id": "CS-09",
        "name": "Finite-Sample / Support-Truncation Mirage",
        "risk_score": r9,
        "status": _status_from_risk(r9),
        "evidence": ev9,
        "remediation": "Check finite-M sample cutoffs and tail-mass extinction (e.g. exact PGL(2,Q) support truncation) before claiming asymptotic laws.",
    })

    # ------------------------------------------------------------------
    # 10. Sparse-Collision Denominator Collapse (CS-10, AUDIT-039 / AUDIT-037)
    # ------------------------------------------------------------------
    r10 = 0
    ev10: list[str] = []
    cs10_ok = ("fixed-denominator", "fixed denominator", "sum/w", "avoid", "never", "repaired", "caught", "anti-pattern", "prevent")
    for d in py_scan_dirs:
        if not d.is_dir():
            continue
        for pf in sorted(d.rglob("*.py")):
            if any(part in SKIP_DIRS or part == "__pycache__" for part in pf.relative_to(root).parts):
                continue
            txt = pf.read_text(encoding="utf-8", errors="replace")
            if _SCATTER_MEAN_RE.search(txt) is not None and not any(tok in txt.lower() for tok in ("fixed_denominator", "sum_over_w")):
                r10 += 60
                ev10.append(f"{pf.relative_to(root)}: scatter_reduce_('mean', include_self=False) divides by collision count c_j instead of global W")
    for mf in [audit_log_path] + md_files:
        if not mf.is_file():
            continue
        for lineno, line in enumerate(mf.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if _COLLISION_DENOM_RE.search(line) is not None and not any(tok in line.lower() for tok in cs10_ok):
                r10 += 50
                ev10.append(f"{mf.relative_to(root)}:{lineno}: possible sparse-collision or shrinking-denominator collapse")
    for sub in ("probes", "synthesis"):
        sp = root / sub
        if not sp.is_dir():
            continue
        for jf in sorted(sp.rglob("*.json")):
            if any(part in SKIP_DIRS for part in jf.relative_to(root).parts):
                continue
            try:
                jobj = loads_strict_json(jf.read_text(encoding="utf-8", errors="replace"), allow_float=True, require_object=False)
            except Exception:
                continue
            if isinstance(jobj, dict):
                if jobj.get("denominator_mode") == "collision_count" or jobj.get("fixed_denominator_enforced") is False:
                    r10 += 60
                    ev10.append(f"{jf.relative_to(root)}: sparse/filtered aggregation lacks fixed global denominator W")
    r10 = min(100, r10)
    patterns.append({
        "id": "CS-10",
        "name": "Sparse-Collision Denominator Collapse",
        "risk_score": r10,
        "status": _status_from_risk(r10),
        "evidence": ev10,
        "remediation": "Aggregate sparse/filtered updates or eval scores over the fixed global denominator W (e.g. sum/W), never local collision count c_j.",
    })

    # ------------------------------------------------------------------
    # 11. Unit-Gauge / Radix Fragility (CS-11, AUDIT-039 / AUDIT-036)
    # ------------------------------------------------------------------
    r11 = 0
    ev11: list[str] = []
    cs11_ok = ("gauge-invariant", "unit-invariant", "coordinate-free", "exact fraction", "avoid", "never", "repaired", "caught", "anti-pattern", "prevent")
    for mf in [audit_log_path] + md_files:
        if not mf.is_file():
            continue
        for lineno, line in enumerate(mf.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if _UNIT_RADIX_FRAGILE_RE.search(line) is not None and not any(tok in line.lower() for tok in cs11_ok):
                r11 += 50
                ev11.append(f"{mf.relative_to(root)}:{lineno}: possible unit-gauge or radix-dependent fragility")
    for sub in ("probes", "synthesis"):
        sp = root / sub
        if not sp.is_dir():
            continue
        for jf in sorted(sp.rglob("*.json")):
            if any(part in SKIP_DIRS for part in jf.relative_to(root).parts):
                continue
            try:
                jobj = loads_strict_json(jf.read_text(encoding="utf-8", errors="replace"), allow_float=True, require_object=False)
            except Exception:
                continue
            if isinstance(jobj, dict):
                if jobj.get("unit_gauge_invariant") is False or jobj.get("radix_invariant") is False:
                    r11 += 60
                    ev11.append(f"{jf.relative_to(root)}: benchmark/grader fails coordinate-free unit-gauge or radix invariance gate")
    r11 = min(100, r11)
    patterns.append({
        "id": "CS-11",
        "name": "Unit-Gauge / Radix Fragility",
        "risk_score": r11,
        "status": _status_from_risk(r11),
        "evidence": ev11,
        "remediation": "Enforce Stage-B coordinate-free null-equivalence: standardize/scale-normalize features before regularization and grade mathematical equivalence over exact Q, never base-10/float64 heuristics.",
    })

    # ------------------------------------------------------------------
    # 12. Trust-Boundary Shadow (CS-12, Round 6 warp-drive AUDIT-061R..065)
    # ------------------------------------------------------------------
    r12 = 0
    ev12: list[str] = []
    for d in py_scan_dirs:
        if not d.is_dir():
            continue
        for pf in sorted(d.rglob("*.py")):
            if any(part in SKIP_DIRS or part == "__pycache__" for part in pf.relative_to(root).parts):
                continue
            txt = pf.read_text(encoding="utf-8", errors="replace")
            if _TRAILING_NEWLINE_DIGEST_RE.search(txt) is not None:
                r12 += 60
                ev12.append(
                    f"{pf.relative_to(root)}: hex-digest regex uses `$` instead of `\\Z` (allows trailing-newline smuggling)"
                )
    for sub in ("probes", "synthesis"):
        sp = root / sub
        if not sp.is_dir():
            continue
        for jf in sorted(sp.rglob("*.json")):
            if any(part in SKIP_DIRS for part in jf.relative_to(root).parts):
                continue
            try:
                jobj = loads_strict_json(jf.read_text(encoding="utf-8", errors="replace"), allow_float=True, require_object=False)
            except Exception:
                continue
            if isinstance(jobj, dict):
                if (
                    jobj.get("escape_hatch_bound") is False
                    or jobj.get("strict_json_duplicate_keys_checked") is False
                    or jobj.get("ancestor_dir_modes_checked") is False
                ):
                    r12 += 60
                    ev12.append(
                        f"{jf.relative_to(root)}: trust-boundary shadow (unbound escape hatch, unguarded JSON keys, or unchecked ancestor modes)"
                    )
    r12 = min(100, r12)
    patterns.append({
        "id": "CS-12",
        "name": "Trust-Boundary Shadow",
        "risk_score": r12,
        "status": _status_from_risk(r12),
        "evidence": ev12,
        "remediation": "Use `\\A...\\Z` digest regexes, `loads_strict_json` (rejecting duplicate keys & NaN), cryptographic/policy binding on every escape hatch, and `--strict-ancestors` directory-mode verification.",
    })

    avg_risk = sum(p["risk_score"] for p in patterns) / len(patterns)
    health_score = round(max(0.0, 100.0 - avg_risk), 1)
    alert_count = sum(1 for p in patterns if p["status"] == "ALERT")
    warn_count = sum(1 for p in patterns if p["status"] == "WARNING")

    if alert_count > 0:
        overall = "RELAPSE_DETECTED"
    elif warn_count > 0:
        overall = "WATCH"
    else:
        overall = "HEALTHY"

    return {
        "expedition_dir": str(root),
        "overall_status": overall,
        "health_score": health_score,
        "alert_count": alert_count,
        "warning_count": warn_count,
        "patterns": patterns,
    }
