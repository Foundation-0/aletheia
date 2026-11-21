"""
`aletheia init <dir> [--domain <name>]`: Scaffold a clean, non-colliding Aletheia
research expedition workspace with exclusive write boundaries, active portals,
9-gate verification protocol, audit ledger, and Wave 2+ handoff template.
"""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re
from typing import Any

from .handoff import build_handoff_template_dict
from .strict_io import AletheiaError, require_ok, write_lf_text

_DOMAIN_RE = re.compile(r"\A[a-z0-9][a-z0-9_-]{0,47}\Z", re.ASCII)


def _protocol_markdown(domain: str) -> str:
    return f"""# Anti-Shadow Adversarial Verification Protocol (Aletheia v1)

**Domain:** `{domain}`
**Scope:** All instruments, calculations, proofs, certificates, and cross-domain bridges in this expedition.

## Verdict, Oracle-Class, and Novelty Taxonomy
- **Verdicts:** `VERIFIED`, `PARTIAL/FRAGILE`, `FALSIFIED`, `NOT_SHOWN`, `EXPOSED`
- **Oracle Classes:**
  - `exact`: universal proof, exact rational/integer/symbolic certificate, or exhaustive finite search.
  - `sampled`: finite statistical, multi-seed, or out-of-sample check (`not_shown` outside tested inputs).
  - `anchor`: independent held-out specification/simulator replay.
- **Novelty Bar (default `N0` until full-text prior-art audit confirms higher):**
  - `N0` (Known / Repackaging)
  - `N1` (Concrete Local Advance / Tightening / Verified Defect)
  - `N2` (Genuine New Ground — new theorem, sharp invariant, or exact cross-domain operator transfer)

## The Nine Verification Gates
1. **Gate 1 — Exact Reproducibility:** Explicit logged RNG seeds; clean-room replay from scratch.
2. **Gate 2 — Coordinate / Basis / Gauge / Scale Invariance:** Survives representation transformations.
3. **Gate 3 — Negative Controls & Null Models:** Matched adversarial nulls, boundary cases, falsification criteria.
4. **Gate 4 — Exact Arithmetic & Certified Checks:** Zero uncalibrated float thresholds for algebraic claims.
5. **Gate 5 — Anti-Language-Smuggling:** Typed objects, executable operator maps, quantitative closure defects.
6. **Gate 6 — Anti-Circularity & Non-Vacuity:** Beat trivial baselines; survive fresh out-of-sample seeds.
7. **Gate 7 — Gate Integrity (R1–R5):** Default-reject (R1), omission monotonicity (R2), canonical strict parsing (R3), `-I -B` / `-I -O -B` / `-I -B -W error` parity with zero bare `assert`s (R4), refusal-site mutation testing (R5).
8. **Gate 8 — Pre-Adaptation Latch & Permanent Miss Logging:** Record pre-fit diagnostics; never delete misses.
9. **Gate 9 — Strict Novelty & Prior-Art Bar:** Full-text prior-art comparison before awarding `N2`.
"""


def _audit_log_markdown(domain: str) -> str:
    return f"""# Expedition Verification Audit Log (`{domain}`)

Chronological ledger of independent adversarial audits under `verification/PROTOCOL.md`.
*(Per Gate 8, every `FALSIFIED` and `PARTIAL/FRAGILE` audit is logged permanently and never removed.)*

## Audits

| Audit ID | Date | Author | Target / Claim | Gates | Oracle Class | Novelty | Verdict | Evidence / Prior-Art Note |
|---|---|---|---|---|---|---|---|---|
"""


def _frontier_portals_markdown(domain: str) -> str:
    return f"""# Frontier Portals: Steelmanned Hypotheses & Resonance Log (`{domain}`)

**Owner:** `portal-keeper` (active continuously across all probe cycles — never park after Round 1!)

## Portal Discipline (Laws 1, 2, 5 & Beyond-Language Structural Perception)
1. Treat raw sources, failed drafts, and numerical coincidences as **portals**, not finished papers.
2. **Stage A (Label-Stripping):** Strip disciplinary nouns and base-10/coordinate numerology to perceive raw relational geometry, dualities, fixed points, and obstructions.
3. **Stage B (Coordinate-Free Null-Equivalence):** Compress each silhouette into a unit-free, basis-free, radix-free exact invariant or provable obstruction before testing.
4. Separate prototype bugs from underlying mathematical/scientific structures: write down the **strongest repaired formulation** before testing or dismissing, and elevate exact obstructions into a theorem or spawn a follow-up branch.

---

## Portal 1 — Initial Steelmanned Entry Point (Replace with First Concrete Portal)
- **Raw source / trigger:** `<exact read-only source reference>`
- **Coordinate-free structural signature:** `<basis/unit/radix-invariant object, e.g., Schur complement, PGL(2), exact inertia>`
- **Prototype friction to separate:** `<implementation bugs or missing guards>`
- **Steelmanned exact hypothesis:** `<typed objects, explicit operator/equation, falsification criterion>`
- **Target probe & oracle class:** `probes/{domain}/` (`exact` / `sampled` / `anchor`)
"""


def init_workspace(
    target_dir: Path,
    *,
    domain: str = "general",
    force: bool = False,
) -> dict[str, Any]:
    """Scaffold a clean Aletheia expedition workspace in `target_dir`."""
    require_ok(
        isinstance(domain, str) and _DOMAIN_RE.match(domain) is not None,
        "INVALID_DOMAIN_NAME",
        f"domain must match [a-z0-9][a-z0-9_-]{{0,47}}, got {domain!r}",
    )
    root = target_dir.resolve()
    config_path = root / "aletheia.json"
    if config_path.exists() and not force:
        raise AletheiaError(
            "WORKSPACE_EXISTS",
            f"aletheia.json already exists at {config_path} (pass --force to overwrite)",
        )

    created_dirs = [
        "cartography",
        f"probes/{domain}",
        "synthesis",
        "peer-web",
        "verification/checks",
        "manifests",
    ]
    for rel in created_dirs:
        (root / rel).mkdir(parents=True, exist_ok=True)

    today_str = date.today().isoformat()
    workspace_cfg = {
        "schema": "aletheia.workspace.v1",
        "domain": domain,
        "created_date": today_str,
        "roles": {
            "portal-keeper": {"write_scope": ["cartography/"], "continuous_loop": True},
            f"{domain}-probe": {"write_scope": [f"probes/{domain}/"], "read_only": ["cartography/", "peer-web/"]},
            "synthesizer": {"write_scope": ["synthesis/"], "read_only": ["cartography/", "probes/", "peer-web/"]},
            "verifier": {"write_scope": ["verification/"], "read_only": ["cartography/", "probes/", "synthesis/", "peer-web/"]},
            "peer-weaver": {"write_scope": ["peer-web/", "manifests/"], "read_only": ["cartography/", "verification/"]},
        },
        "r4_modes": ["-I -B", "-I -O -B", "-I -B -W error"],
    }

    handoff_tpl = build_handoff_template_dict(
        source_repo=f"local/{root.name}",
        snapshot_date=today_str,
        domain=domain,
    )

    files_to_write: list[tuple[str, str]] = [
        ("aletheia.json", json.dumps(workspace_cfg, indent=2) + "\n"),
        ("cartography/frontier_portals.md", _frontier_portals_markdown(domain)),
        ("verification/PROTOCOL.md", _protocol_markdown(domain)),
        ("verification/AUDIT_LOG.md", _audit_log_markdown(domain)),
        ("manifests/compute_handoff.v1.json", json.dumps(handoff_tpl, indent=2) + "\n"),
        (f"probes/{domain}/.gitkeep", ""),
        ("synthesis/.gitkeep", ""),
        ("peer-web/.gitkeep", ""),
        ("verification/checks/.gitkeep", ""),
    ]

    written: list[str] = []
    for rel, content in files_to_write:
        write_lf_text(root / rel, content)
        written.append(rel)

    return {
        "status": "INITIALIZED",
        "workspace": str(root),
        "domain": domain,
        "files_created": written,
    }
