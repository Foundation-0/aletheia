"""
`aletheia init <dir> [--domain <name>]`: Scaffold a clean, non-colliding Aletheia
research expedition workspace with exclusive write boundaries, active portals,
9-gate verification protocol, audit ledger, and Wave 2+ handoff template.
"""
from __future__ import annotations

from datetime import date
import errno
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Iterable

from .handoff import build_handoff_template_dict
from .strict_io import AletheiaError, require_ok, write_lf_text

_DOMAIN_RE = re.compile(r"\A[a-z0-9][a-z0-9_-]{0,47}\Z", re.ASCII)


def _lstat_refuse_symlink(path: Path, *, role: str, detail: str) -> None:
    """Refuse a path with SYMLINK_REFUSED when lstat reports a symlink or symlink loop."""
    try:
        st = os.lstat(path)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise AletheiaError(
                "SYMLINK_REFUSED",
                f"refusing to traverse symlink loop in {role} {detail} {path} (force never follows links; pass a real directory)",
            ) from exc
        return
    if stat.S_ISLNK(st.st_mode):
        raise AletheiaError(
            "SYMLINK_REFUSED",
            f"refusing to traverse symlinked {role} {detail} {path} (force never follows links; pass a real directory)",
        )


def _require_no_symlink_target(
    target: Path,
    *,
    role: str,
    anchor_root: Path | None = None,
) -> Path:
    """Refuse symlinked targets and symlinked ancestors via a single left-to-right stack walk.

    Boundary:
      - Checks `target` itself with `os.lstat()` first (catching leaf symlinks
        and direct `ELOOP` chains).
      - Walks `target` (anchored at `Path.cwd()` when relative, or the
        filesystem root / `anchor_root` when absolute) strictly left-to-right
        with an explicit component stack.
      - Every pushed component at depth >= 2 below the root is checked
        immediately with `os.lstat()` BEFORE any subsequent `..` can pop it,
        so nonexistent segments (`no_such/..`), regular files (`reg_file/..`),
        and trailing `..` (`link_sub/..`) cannot mask a symlink or loop.
      - The depth-1 root entry (such as macOS `/var -> /private/var`,
        `/tmp -> /private/tmp`, `/etc -> /private/etc`) is permitted solely as
        a strict downward ancestor; traversing `..` directly out of a depth-1
        symlink (e.g. `/var/..`) and targeting a symlink leaf at any depth are
        both refused with `SYMLINK_REFUSED`.
      - Resolves and returns the verified `..`-free stack path.
    """
    target = Path(target)
    _lstat_refuse_symlink(target, role=role, detail="target")
    base = target if target.is_absolute() else Path.cwd()
    root = Path(base.anchor) if anchor_root is None else anchor_root
    if target.is_absolute():
        stack: list[str] = []
        raw_parts = target.relative_to(root).parts
    else:
        stack = list(base.relative_to(root).parts)
        raw_parts = target.parts

    for part in raw_parts:
        if part == "..":
            if len(stack) == 1:
                _lstat_refuse_symlink(root / stack[0], role=role, detail="component")
            if stack:
                stack.pop()
            continue
        stack.append(part)
        if len(stack) >= 2:
            _lstat_refuse_symlink(root.joinpath(*stack), role=role, detail="component")

    final_path = root.joinpath(*stack) if stack else root
    _lstat_refuse_symlink(final_path, role=role, detail="target")
    return final_path.resolve()


def _symlink_offenders(root: Path, rel_paths: Iterable[str]) -> list[str]:
    """Return sorted relative paths whose existing component under root is a symlink.

    Every existing component (directories and the final path) is checked with
    lstat, so a link is reported by its own relative path and is never followed.
    Missing components end the walk for that path because nothing below them
    can exist yet."""
    offenders: set[str] = set()
    for rel in rel_paths:
        parts = [p for p in rel.split("/") if p not in ("", ".")]
        current = root
        for i, part in enumerate(parts):
            current = current / part
            try:
                st = os.lstat(current)
            except OSError:
                break
            if stat.S_ISLNK(st.st_mode):
                offenders.add("/".join(parts[: i + 1]))
                break
    return sorted(offenders)


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
    """Scaffold a clean Aletheia expedition workspace in `target_dir`.

    Refuses symlinked targets, symlinked relative components, symlinked
    absolute ancestors at depth >= 2 (exempting only depth-1 OS-managed root
    links such as macOS /var, /tmp, /etc), and symlinked workspace subpaths,
    with or without `force`.
    """
    require_ok(
        isinstance(domain, str) and _DOMAIN_RE.match(domain) is not None,
        "INVALID_DOMAIN_NAME",
        f"domain must match [a-z0-9][a-z0-9_-]{{0,47}}, got {domain!r}",
    )
    root = _require_no_symlink_target(target_dir, role="workspace")

    created_dirs = [
        "cartography",
        f"probes/{domain}",
        "synthesis",
        "peer-web",
        "verification/checks",
        "manifests",
    ]
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

    # Refuse before creating anything: no write may pass through a symlinked
    # component under the root, with or without --force.
    symlinked = _symlink_offenders(root, [*created_dirs, *(rel for rel, _ in files_to_write)])
    if symlinked:
        raise AletheiaError(
            "SYMLINK_REFUSED",
            f"refusing to write through symlinked path component(s) in {root}: {', '.join(symlinked)} (force never follows links; remove the symlink and retry)",
        )

    # Refuse before creating anything: no target file may be overwritten without --force.
    conflicts = [rel for rel, _ in files_to_write if os.path.lexists(root / rel)]
    if conflicts and not force:
        raise AletheiaError(
            "WORKSPACE_EXISTS",
            f"refusing to overwrite existing file(s) in {root}: {', '.join(conflicts)} (pass --force to overwrite)",
        )

    # A regular file where a directory is needed cannot be overwritten, with or without --force.
    blockers = [root] + [
        root / "/".join(parts[: i + 1])
        for rel in created_dirs
        for parts in [rel.split("/")]
        for i in range(len(parts))
    ]
    blocked = sorted({str(b.relative_to(root)) if b != root else "." for b in blockers if os.path.lexists(b) and not b.is_dir()})
    if blocked:
        raise AletheiaError(
            "WORKSPACE_EXISTS",
            f"a regular file is in the way of a directory in {root}: {', '.join(blocked)} (--force does not replace it; remove or rename it)",
        )

    for rel in created_dirs:
        (root / rel).mkdir(parents=True, exist_ok=True)

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
