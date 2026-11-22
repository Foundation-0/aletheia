"""
`aletheia install --target <antigravity|claude-code|codex|cursor|gemini-cli|repo> [--dest <path>] [--dry-run]`:
Deploy The Aletheia Method adapters, rules, and skills cleanly onto any agent platform or repo.

Automatically reads from the enclosing Aletheia repository's `adapters/` and `.agents/` trees
when present, and falls back to clean built-in stdlib templates when installed standalone via pip.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .scaffold import _audit_log_markdown, _protocol_markdown
from .strict_io import AletheiaError, require_ok, write_lf_text

VALID_TARGETS = ("antigravity", "claude-code", "codex", "cursor", "gemini-cli", "repo")

_EMBEDDED_AGENTS_MD = """# The Aletheia Method — Default Research Protocol

Apply **The Aletheia Method** (*Portal-Driven Resonance & Adversarial Tomography*) whenever conducting scientific, mathematical, physical, or cross-repository discovery:

1. **Active Portal-Keeper Loop (Never Park Cartography):** Keep raw sources/transcripts/datasets open as live portals; re-enter whenever any probe hits an anomaly, coincidence, or sharpness wall.
2. **Steelman Before Falsifying:** Separate prototype friction from underlying mathematical/scientific truth; test the strongest repaired statement before closing a direction.
3. **Adversarial Verification as Multi-Basis Tomography:** Use zero-shared-code exact oracles (`int`, `Fraction`, `isqrt`, exact symbolic) or matched adversarial nulls/OOD seeds. Enforce R4 parity (`-I -B`, `-I -O -B`, `-I -B -W error`, zero bare `assert`s) and R5 refusal-site mutation testing.
4. **Honest Novelty & Scope (`N0`/`N1`/`N2`):** Default to `N0` until full-text prior-art audit confirms `N1` or `N2`. Never conflate `Draft PR` with merged or `uncompiled_source` with kernel-verified.
5. **Exact-Operator Cross-Pollination:** Transfer insights across domains only via typed objects, executable maps, exact identities, or provable obstructions (zero language smuggling).
"""

_EMBEDDED_SKILL_MD = """---
name: aletheia-research
description: >-
  The Aletheia Method (Portal-Driven Resonance & Adversarial Tomography) for open-ended
  scientific, mathematical, physical, and cross-repository discovery.
---

# The Aletheia Method Runbook

1. **Portal Phase:** Mine raw sources into `cartography/frontier_portals.md` with steelmanned exact hypotheses.
2. **Probe Phase:** Realize concrete hypotheses against live upstream equations/data in `probes/`.
3. **Tomography Phase:** Audit with zero-shared-code exact/null oracles in `verification/checks/` and log permanently in `verification/AUDIT_LOG.md`.
4. **Resonance Phase:** Feed every anomaly, obstruction, or sharpness wall back to the Portal Phase.
5. **CLI Gates:** Run `aletheia audit-check .`, `aletheia mutate`, and `aletheia diagnose .` before publishing.
"""

_EMBEDDED_CURSOR_MDC = """---
description: The Aletheia Method (Portal-Driven Resonance & Adversarial Tomography) for scientific and mathematical research
globs: ["**/*"]
alwaysApply: true
---

""" + _EMBEDDED_AGENTS_MD

_EMBEDDED_CLAUDE_CMD = """# /aletheia — Execute One Aletheia Resonance Cycle

1. Read `cartography/frontier_portals.md` and `verification/AUDIT_LOG.md`.
2. Steelman the sharpest open portal into an explicit typed hypothesis with a falsification criterion.
3. Test against live upstream equations/data (zero synthetic proxy substitution).
4. Run independent verification (`aletheia audit-check .` + `aletheia mutate`) under `-I -B`, `-I -O -B`, `-I -B -W error`.
5. Loop any anomaly or obstruction back into `cartography/frontier_portals.md`.
"""

_EMBEDDED_CI_YML = """name: Aletheia Verification Gate

on:
  push:
  pull_request:

jobs:
  aletheia-r4-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Run Aletheia R1-R5 audit check
        run: |
          python3 -m aletheia audit-check .
"""


def _detect_repo_root(source_dir: Path | None) -> Path | None:
    if source_dir is not None:
        return source_dir.resolve()
    # Package is at <repo>/aletheia/installer.py
    cand = Path(__file__).resolve().parent.parent
    if (cand / "adapters").is_dir() or (cand / ".agents").is_dir():
        return cand
    return None


def _collect_tree(src_dir: Path, dest_prefix: str = "") -> list[tuple[str, str]]:
    """Collect all UTF-8 text files under src_dir as (relative_dest_path, content)."""
    files: list[tuple[str, str]] = []
    for p in sorted(src_dir.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            rel = str(p.relative_to(src_dir)).replace("\\", "/")
            out_rel = f"{dest_prefix}/{rel}".lstrip("/") if dest_prefix else rel
            files.append((out_rel, p.read_text(encoding="utf-8")))
    return files


def _build_install_plan(target: str, repo_root: Path | None) -> list[tuple[str, str]]:
    """Return deterministic list of (relative_path_under_dest, content) for target platform."""
    from . import __version__

    if target == "antigravity":
        if repo_root is not None and (repo_root / ".agents" / "plugins" / "aletheia-research").is_dir():
            return _collect_tree(repo_root / ".agents" / "plugins" / "aletheia-research")
        plugin_json = json.dumps(
            {
                "name": "aletheia-research",
                "version": __version__,
                "description": "The Aletheia Method: Portal-Driven Resonance & Adversarial Tomography",
                "homepage": "https://github.com/Foundation-0/aletheia",
                "rules": ["rules/AGENTS.md"],
                "skills": ["skills/aletheia-research"],
            },
            indent=2,
        ) + "\n"
        return [
            ("plugin.json", plugin_json),
            ("rules/AGENTS.md", _EMBEDDED_AGENTS_MD),
            ("skills/aletheia-research/SKILL.md", _EMBEDDED_SKILL_MD),
        ]

    if target == "claude-code":
        cc_dir = repo_root / "adapters" / "claude-code" if repo_root is not None else None
        if cc_dir is not None and cc_dir.is_dir():
            files: list[tuple[str, str]] = []
            for rel, content in _collect_tree(cc_dir):
                if rel == "README.md":
                    continue
                if rel.startswith("commands/") or rel.startswith("agents/"):
                    files.append((f".claude/{rel}", content))
                else:
                    files.append((rel, content))
            return files
        c_plugin = json.dumps(
            {
                "name": "aletheia-research",
                "version": __version__,
                "description": "The Aletheia Method adapter for Claude Code",
                "homepage": "https://github.com/Foundation-0/aletheia",
                "commands": [".claude/commands/aletheia.md"],
            },
            indent=2,
        ) + "\n"
        return [
            ("CLAUDE.md", _EMBEDDED_AGENTS_MD),
            (".claude-plugin/plugin.json", c_plugin),
            (".claude/commands/aletheia.md", _EMBEDDED_CLAUDE_CMD),
        ]

    if target == "codex":
        if repo_root is not None and (repo_root / "adapters" / "codex" / "AGENTS.md").is_file():
            return [("AGENTS.md", (repo_root / "adapters" / "codex" / "AGENTS.md").read_text(encoding="utf-8"))]
        if repo_root is not None and (repo_root / "AGENTS.md").is_file():
            return [("AGENTS.md", (repo_root / "AGENTS.md").read_text(encoding="utf-8"))]
        return [("AGENTS.md", _EMBEDDED_AGENTS_MD)]

    if target == "cursor":
        if repo_root is not None and (repo_root / "adapters" / "cursor" / ".cursor" / "rules" / "aletheia-research.mdc").is_file():
            src = repo_root / "adapters" / "cursor" / ".cursor" / "rules" / "aletheia-research.mdc"
            return [(".cursor/rules/aletheia-research.mdc", src.read_text(encoding="utf-8"))]
        return [(".cursor/rules/aletheia-research.mdc", _EMBEDDED_CURSOR_MDC)]

    if target == "gemini-cli":
        if repo_root is not None and (repo_root / "adapters" / "gemini-cli" / "GEMINI.md").is_file():
            return [("GEMINI.md", (repo_root / "adapters" / "gemini-cli" / "GEMINI.md").read_text(encoding="utf-8"))]
        return [("GEMINI.md", _EMBEDDED_AGENTS_MD)]

    if target == "repo":
        agents_text = _EMBEDDED_AGENTS_MD
        if repo_root is not None and (repo_root / "AGENTS.md").is_file():
            agents_text = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
        return [
            ("AGENTS.md", agents_text),
            ("verification/PROTOCOL.md", _protocol_markdown("repo")),
            ("verification/AUDIT_LOG.md", _audit_log_markdown("repo")),
            (".github/workflows/aletheia-ci.yml", _EMBEDDED_CI_YML),
        ]

    raise AletheiaError("INVALID_INSTALL_TARGET", f"unsupported target {target!r}; choose from {VALID_TARGETS}")


def install_adapter(
    target: str,
    *,
    dest: Path | None = None,
    source_dir: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Install (or dry-run plan) Aletheia adapters for the specified platform target."""
    require_ok(target in VALID_TARGETS, "INVALID_INSTALL_TARGET", f"target {target!r} not in {VALID_TARGETS}")

    if dest is None:
        if target == "antigravity":
            dest_root = (Path.cwd() / ".agents" / "plugins" / "aletheia-research").resolve()
        else:
            dest_root = Path.cwd().resolve()
    else:
        dest_root = dest.resolve()

    repo_root = _detect_repo_root(source_dir)
    plan = _build_install_plan(target, repo_root)

    actions: list[dict[str, Any]] = []
    conflicts: list[str] = []

    for rel, content in plan:
        out_path = dest_root / rel
        exists = out_path.exists()
        if exists and not force:
            conflicts.append(rel)
            action = "CONFLICT_EXISTS"
        else:
            action = "OVERWRITE" if exists else "CREATE"
        actions.append({
            "relative_path": rel,
            "destination": str(out_path),
            "bytes": len(content.encode("utf-8")),
            "action": action,
        })

    if conflicts and not dry_run:
        raise AletheiaError(
            "INSTALL_CONFLICT",
            f"refusing to overwrite existing files without --force: {conflicts}",
        )

    if not dry_run:
        for rel, content in plan:
            write_lf_text(dest_root / rel, content)

    return {
        "status": "DRY_RUN" if dry_run else "INSTALLED",
        "target": target,
        "destination": str(dest_root),
        "source_mode": "repo_adapters" if repo_root is not None else "embedded_templates",
        "dry_run": dry_run,
        "file_count": len(actions),
        "conflicts": conflicts,
        "files": actions,
    }
