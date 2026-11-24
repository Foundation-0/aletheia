"""
`aletheia install --target <antigravity|claude-code|codex|cursor|gemini-cli|repo> [--dest <path>] [--dry-run]`:
Deploy The Aletheia Method adapters, rules, and skills cleanly onto any agent platform or repo.

Automatically reads from the enclosing Aletheia repository's `adapters/` and `.agents/` trees
when present, and falls back to clean built-in stdlib templates when installed standalone via pip.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .scaffold import (
    _audit_log_markdown,
    _protocol_markdown,
    _require_no_symlink_target,
    _symlink_offenders,
)
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

# Commit of Foundation-0/aletheia that the generated CI installs: the v2.1.0 release
# commit on main (#19). A pinned full SHA cannot move; bump it when a later release
# should be installed instead.
_CI_ALETHEIA_REPO = "https://github.com/Foundation-0/aletheia"
_CI_ALETHEIA_COMMIT = "a07d7db02018ab852d7653f08678ee7c692f3a33"

_EMBEDDED_CI_YML = f"""name: Aletheia Verification Gate

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
      - name: Install aletheia-method at a pinned commit (zero external dependencies)
        run: |
          python3 -m pip install --no-deps "aletheia-method @ git+{_CI_ALETHEIA_REPO}@{_CI_ALETHEIA_COMMIT}"
      - name: Run aletheia audit-check (R1-R4 hygiene; R5 is aletheia mutate; R6/R7 not automated by this command)
        run: |
          python3 -m aletheia audit-check .
"""


def _detect_repo_root(source_dir: Path | None) -> Path | None:
    if source_dir is not None:
        return _require_no_symlink_target(source_dir, role="source directory")
    # Package is at <repo>/aletheia/installer.py
    cand = Path(__file__).resolve().parent.parent
    if (cand / "adapters").is_dir() or (cand / ".agents").is_dir():
        return cand
    return None


def _resolve_source_path(repo_root: Path | None, rel: str) -> Path | None:
    """Return repo_root / rel after refusing any symlinked component along rel (even if broken)."""
    if repo_root is None:
        return None
    offenders = _symlink_offenders(repo_root, [rel])
    if offenders:
        raise AletheiaError(
            "SYMLINK_REFUSED",
            f"refusing to read through symlinked source component(s) in {repo_root}: {', '.join(offenders)} (force never follows links; replace the symlink with a real file or directory)",
        )
    return repo_root / rel


def _read_source_text(path: Path) -> str:
    """Read a single source file, refusing to follow a symlink out of the tree."""
    require_ok(
        not path.is_symlink(),
        "SYMLINK_REFUSED",
        f"refusing to read symlinked source file {path} (force never follows links; replace the symlink with a regular file)",
    )
    return path.read_text(encoding="utf-8")


def _collect_tree(src_dir: Path, dest_prefix: str = "") -> list[tuple[str, str]]:
    """Collect all UTF-8 text files under src_dir as (relative_dest_path, content).

    Symlinked files or directories anywhere in the tree are refused with
    SYMLINK_REFUSED instead of being copied, so a planted link can never pull
    content from outside the source tree into an install."""
    require_ok(
        not src_dir.is_symlink(),
        "SYMLINK_REFUSED",
        f"refusing to collect symlinked source directory {src_dir} (force never follows links; replace the symlink with a real directory)",
    )
    files: list[tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(src_dir, followlinks=False):
        dirnames.sort()
        kept_dirs: list[str] = []
        for name in dirnames:
            entry = Path(dirpath) / name
            require_ok(
                not entry.is_symlink(),
                "SYMLINK_REFUSED",
                f"refusing to copy symlinked source directory {entry} (force never follows links; replace the symlink with a real directory)",
            )
            if name != "__pycache__":
                kept_dirs.append(name)
        dirnames[:] = kept_dirs
        for name in sorted(filenames):
            entry = Path(dirpath) / name
            require_ok(
                not entry.is_symlink(),
                "SYMLINK_REFUSED",
                f"refusing to copy symlinked source file {entry} (force never follows links; replace the symlink with a regular file)",
            )
            rel = str(entry.relative_to(src_dir)).replace("\\", "/")
            out_rel = f"{dest_prefix}/{rel}".lstrip("/") if dest_prefix else rel
            files.append((out_rel, entry.read_text(encoding="utf-8")))
    return sorted(files)


def _build_install_plan(target: str, repo_root: Path | None) -> list[tuple[str, str]]:
    """Return deterministic list of (relative_path_under_dest, content) for target platform."""
    from . import __version__

    if target == "antigravity":
        ag_dir = _resolve_source_path(repo_root, ".agents/plugins/aletheia-research")
        if ag_dir is not None and ag_dir.is_dir():
            return _collect_tree(ag_dir)
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
        cc_dir = _resolve_source_path(repo_root, "adapters/claude-code")
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
        codex_src = _resolve_source_path(repo_root, "adapters/codex/AGENTS.md")
        if codex_src is not None and codex_src.is_file():
            return [("AGENTS.md", _read_source_text(codex_src))]
        root_agents = _resolve_source_path(repo_root, "AGENTS.md")
        if root_agents is not None and root_agents.is_file():
            return [("AGENTS.md", _read_source_text(root_agents))]
        return [("AGENTS.md", _EMBEDDED_AGENTS_MD)]

    if target == "cursor":
        cursor_src = _resolve_source_path(repo_root, "adapters/cursor/.cursor/rules/aletheia-research.mdc")
        if cursor_src is not None and cursor_src.is_file():
            return [(".cursor/rules/aletheia-research.mdc", _read_source_text(cursor_src))]
        return [(".cursor/rules/aletheia-research.mdc", _EMBEDDED_CURSOR_MDC)]

    if target == "gemini-cli":
        gemini_src = _resolve_source_path(repo_root, "adapters/gemini-cli/GEMINI.md")
        if gemini_src is not None and gemini_src.is_file():
            return [("GEMINI.md", _read_source_text(gemini_src))]
        return [("GEMINI.md", _EMBEDDED_AGENTS_MD)]

    if target == "repo":
        agents_text = _EMBEDDED_AGENTS_MD
        repo_agents = _resolve_source_path(repo_root, "AGENTS.md")
        if repo_agents is not None and repo_agents.is_file():
            agents_text = _read_source_text(repo_agents)
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
            cwd = Path.cwd()
            offenders = _symlink_offenders(cwd, [".agents/plugins/aletheia-research"])
            if offenders:
                raise AletheiaError(
                    "SYMLINK_REFUSED",
                    f"refusing to install through symlinked default destination component(s) in {cwd}: {', '.join(offenders)} (force never follows links; remove the symlink and retry)",
                )
            dest_root = (cwd / ".agents" / "plugins" / "aletheia-research").resolve()
        else:
            dest_root = Path.cwd().resolve()
    else:
        dest_root = _require_no_symlink_target(dest, role="destination")

    repo_root = _detect_repo_root(source_dir)
    plan = _build_install_plan(target, repo_root)

    actions: list[dict[str, Any]] = []
    conflicts: list[str] = []
    symlink_conflicts: list[str] = []

    for rel, content in plan:
        out_path = dest_root / rel
        # lexists counts a broken symlink as existing, so it can never be
        # reported as CREATE or written through to its target.
        exists = os.path.lexists(out_path)
        offenders = _symlink_offenders(dest_root, [rel])
        if offenders:
            symlink_conflicts.extend(offenders)
            conflicts.append(rel)
            action = "CONFLICT_EXISTS"
        elif exists and not force:
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

    if symlink_conflicts and not dry_run:
        raise AletheiaError(
            "SYMLINK_REFUSED",
            f"refusing to write through symlinked path component(s) in {dest_root}: {', '.join(sorted(set(symlink_conflicts)))} (force never follows links; remove the symlink and retry)",
        )

    if conflicts and not dry_run:
        raise AletheiaError(
            "INSTALL_CONFLICT",
            f"refusing to overwrite existing files without --force: {conflicts}",
        )

    if not dry_run:
        for rel, content in plan:
            out_path = dest_root / rel
            parent = out_path.parent.resolve()
            require_ok(
                parent == dest_root or dest_root in parent.parents,
                "SYMLINK_REFUSED",
                f"refusing to write outside destination root {dest_root}: {rel} resolves under {parent} (force never follows links)",
            )
            write_lf_text(out_path, content)

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
