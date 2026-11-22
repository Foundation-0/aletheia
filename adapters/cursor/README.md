# Cursor Adapter

Cursor natively loads `.cursor/rules/*.mdc` rules with YAML frontmatter. The shipped rule [`aletheia-research.mdc`](.cursor/rules/aletheia-research.mdc) sets `alwaysApply: true` so every Composer/Agent session inherits **The Aletheia Method** automatically.

## Option 1 — Automated CLI Install (Recommended)

```bash
# Preview safely
python3 -m aletheia install --target cursor --dest /path/to/your-repo --dry-run

# Install .cursor/rules/aletheia-research.mdc into your repository
python3 -m aletheia install --target cursor --dest /path/to/your-repo
```

## Option 2 — Manual Install

```bash
mkdir -p /path/to/your-repo/.cursor/rules
cp adapters/cursor/.cursor/rules/aletheia-research.mdc /path/to/your-repo/.cursor/rules/
```

## Recommended Cursor Workflow

1. Keep `cartography/frontier_portals.md` and `verification/AUDIT_LOG.md` pinned in your workspace.
2. Run **Portal** and **Probe** phases in one Cursor Agent chat, then start a **fresh Cursor Agent chat** for the **Tomography** phase (quoting [`../../prompts/verifier-tomography.md`](../../prompts/verifier-tomography.md)) so verification runs with zero confirmation bias or shared helper assumptions.
3. Run `python3 -m aletheia audit-check .` and `python3 -m aletheia diagnose .` in Cursor's terminal before committing a Draft PR.
